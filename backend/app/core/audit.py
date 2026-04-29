"""
app/core/audit.py
감사 로그 (Audit Log) — 누가 언제 무엇을 했는지 추적.

설계 원칙:
  - 실패-관대(fail-open): 감사 로그 쓰기 실패가 본 작업을 막으면 안 된다
  - 기록 대상: 인증 이벤트, 민감 리소스 변경(사용자/설정), 이관 Job 생명주기
  - 조회는 빠르게: SQLite 인덱스 활용 (timestamp DESC, username, action)
  - 보존 정책은 운영자 재량 (별도 정리 API 제공)

레코드 스키마:
  {
    "id":         "uuid",
    "ts":         ISO datetime (기록 시각),
    "username":   str | null,
    "role":       "admin" | "operator" | "viewer" | "anonymous",
    "action":     "login.success" | "job.create" | "settings.update" | ...
                  (dot-separated resource.verb 관례)
    "resource":   "job" | "user" | "settings" | "profile" | ...
    "resource_id": str | null,
    "status":     "ok" | "fail" | "denied",
    "ip":         str | null,
    "details":    dict (임의 메타데이터, 비밀번호 등 민감값 금지),
  }
"""
from __future__ import annotations
import hashlib
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

logger = logging.getLogger("databridge.audit")

_KST = timezone(timedelta(hours=9))

# v10 #21: 감사 로그 무결성 체인 — 마지막 레코드 해시 보관
# 이 값은 메모리에만 존재하며, 재기동 시 DB 의 최신 레코드에서 복원됨
_last_hash: str | None = None
_hash_lock = threading.Lock()


def _canonical(entry: dict) -> str:
    """해시 입력용 canonical JSON (키 정렬, 공백 제거)."""
    # hash/prev_hash 필드는 제외하고 직렬화
    src = {k: v for k, v in entry.items() if k not in ("this_hash", "prev_hash")}
    return json.dumps(src, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def _compute_hash(entry: dict, prev_hash: str | None) -> str:
    """SHA-256 해시 체인 — prev_hash + canonical(entry)"""
    h = hashlib.sha256()
    h.update((prev_hash or "").encode("utf-8"))
    h.update(_canonical(entry).encode("utf-8"))
    return h.hexdigest()


def _get_last_hash() -> str | None:
    """메모리 캐시된 마지막 해시. 없으면 DB 에서 복원."""
    global _last_hash
    if _last_hash is not None:
        return _last_hash
    try:
        rows = sorted(_store().values(), key=lambda r: r.get("ts_epoch", 0), reverse=True)
        if rows:
            _last_hash = rows[0].get("this_hash")
    except Exception:
        pass
    return _last_hash


# 자주 쓰는 action 상수 (오타 방지)
class Actions:
    LOGIN_OK          = "auth.login.success"
    LOGIN_FAIL        = "auth.login.fail"
    LOGOUT            = "auth.logout"
    PASSWORD_CHANGE   = "auth.password.change"
    PASSWORD_RESET    = "auth.password.reset"   # admin이 타인 비번 리셋
    AUTH_DENIED       = "auth.denied"           # 인증 실패 또는 권한 부족

    USER_CREATE       = "user.create"
    USER_UPDATE       = "user.update"
    USER_DELETE       = "user.delete"
    USER_DISABLE      = "user.disable"
    USER_ENABLE       = "user.enable"

    JOB_CREATE        = "job.create"
    JOB_DELETE        = "job.delete"
    JOB_BULK_DELETE   = "job.bulk_delete"
    JOB_RESTART       = "job.restart"
    JOB_RESUME        = "job.resume_from_checkpoint"
    JOB_STOP          = "job.stop"
    JOB_PAUSE         = "job.pause"

    PROFILE_CREATE    = "profile.create"
    PROFILE_UPDATE    = "profile.update"
    PROFILE_DELETE    = "profile.delete"

    SETTINGS_UPDATE   = "settings.update"
    API_KEY_SET       = "settings.api_key.set"
    API_KEY_DELETE    = "settings.api_key.delete"


def _store():
    """지연 import — 순환 의존 방지"""
    from app.core.store import Store
    return Store("audit_logs")


def record(
    *,
    action: str,
    user: Optional[dict] = None,
    resource: str = "",
    resource_id: Optional[str] = None,
    status: str = "ok",
    ip: Optional[str] = None,
    details: Optional[dict] = None,
) -> None:
    """
    감사 이벤트 1건 기록. 실패해도 조용히 로그에만 남기고 호출자 방해하지 않음.

    Args:
        action:      "resource.verb" 형식 (Actions 상수 권장)
        user:        auth_deps.current_user 결과 또는 None (비인증 이벤트)
        resource:    리소스 타입 (job/user/settings/profile/...)
        resource_id: 리소스 식별자 (job id, username 등)
        status:      "ok" | "fail" | "denied"
        ip:          요청 IP (fastapi Request.client.host)
        details:     추가 메타데이터 (비밀번호·토큰 등 민감값 넣지 말 것)
    """
    try:
        # 민감값 방어 — details 에 password/token/secret 키가 있으면 마스크
        safe_details = dict(details or {})
        for k in list(safe_details.keys()):
            if any(sensitive in k.lower() for sensitive in ("password", "token", "secret", "api_key")):
                safe_details[k] = "***REDACTED***"

        eid = str(uuid.uuid4())
        entry = {
            "id":          eid,
            "ts":          datetime.now(_KST).isoformat(),
            "ts_epoch":    int(time.time()),
            "username":    (user or {}).get("username"),
            "role":        (user or {}).get("role", "anonymous"),
            "action":      action,
            "resource":    resource,
            "resource_id": resource_id,
            "status":      status,
            "ip":          ip,
            "details":     safe_details,
        }
        # v10 #21: 감사 로그 무결성 해시 체인
        # - prev_hash = 직전 레코드의 this_hash (없으면 None)
        # - this_hash = sha256(prev_hash || canonical(entry without hash fields))
        # 누군가 중간 레코드를 변조하면 이후 모든 레코드의 해시가 깨짐 → 변조 탐지 가능.
        with _hash_lock:
            global _last_hash
            prev = _get_last_hash()
            entry["prev_hash"] = prev
            entry["this_hash"] = _compute_hash(entry, prev)
            _last_hash = entry["this_hash"]
        _store().set(eid, entry)
    except Exception as e:
        # 감사 실패는 warn 로그만 — 본 작업을 방해하지 않음
        logger.warning("감사 로그 기록 실패 (action=%s): %s", action, e)


def query(
    *,
    username: Optional[str] = None,
    action: Optional[str] = None,
    action_prefix: Optional[str] = None,
    resource: Optional[str] = None,
    status: Optional[str] = None,
    since_epoch: Optional[int] = None,
    until_epoch: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """
    감사 로그 조회 (필터 + 페이지네이션).

    SQLite 쿼리 레벨 최적화 없이 메모리 필터링 사용 — 대량 감사 이력에서는
    별도 인덱스 테이블이 필요하지만, POC 수준에서는 충분.

    Returns:
        {"total": N, "items": [...], "offset": offset, "limit": limit}
    """
    all_entries = list(_store().values())

    # 필터
    def keep(e):
        if not isinstance(e, dict):
            return False
        if username and e.get("username") != username:
            return False
        if action and e.get("action") != action:
            return False
        if action_prefix and not (e.get("action") or "").startswith(action_prefix):
            return False
        if resource and e.get("resource") != resource:
            return False
        if status and e.get("status") != status:
            return False
        ts = e.get("ts_epoch", 0)
        if since_epoch and ts < since_epoch:
            return False
        if until_epoch and ts > until_epoch:
            return False
        return True

    filtered = [e for e in all_entries if keep(e)]
    # 최신순
    filtered.sort(key=lambda e: e.get("ts_epoch", 0), reverse=True)

    total = len(filtered)
    page = filtered[offset:offset + limit]
    return {"total": total, "items": page, "offset": offset, "limit": limit}


def stats(*, since_epoch: Optional[int] = None) -> dict:
    """
    감사 이벤트 요약 통계 — 대시보드용.
    """
    all_entries = list(_store().values())
    if since_epoch:
        all_entries = [e for e in all_entries
                       if isinstance(e, dict) and e.get("ts_epoch", 0) >= since_epoch]

    by_action: dict = {}
    by_user: dict = {}
    by_status: dict = {"ok": 0, "fail": 0, "denied": 0}
    for e in all_entries:
        if not isinstance(e, dict):
            continue
        a = e.get("action", "unknown")
        u = e.get("username") or "anonymous"
        s = e.get("status", "ok")
        by_action[a] = by_action.get(a, 0) + 1
        by_user[u]   = by_user.get(u, 0) + 1
        by_status[s] = by_status.get(s, 0) + 1

    return {
        "total":      len(all_entries),
        "by_action":  by_action,
        "by_user":    by_user,
        "by_status":  by_status,
    }


def purge_older_than(days: int) -> int:
    """
    N일 이전 감사 이력 삭제 — 보관 정책 운영용.
    Returns: 삭제된 레코드 수
    """
    cutoff = int(time.time()) - (days * 86400)
    s = _store()
    removed = 0
    for eid, entry in list(s.all().items()):
        if isinstance(entry, dict) and entry.get("ts_epoch", 0) < cutoff:
            s.delete(eid)
            removed += 1
    if removed > 0:
        logger.info("감사 로그 정리: %d일 이전 %d건 삭제", days, removed)
    return removed


# ══════════════════════════════════════════════════════════
# v10 #21 — 무결성 검증 (변조 탐지)
# ══════════════════════════════════════════════════════════
def verify_integrity() -> dict:
    """
    전체 감사 로그의 해시 체인을 처음부터 재계산하여 변조 여부 확인.

    Returns:
        {
          "ok":            bool,
          "total":         int,      # 검사된 레코드 수
          "legacy":        int,      # 해시 체인 이전 레코드 (this_hash 없음)
          "broken_at":     str|None, # 깨진 레코드 id (있으면)
          "broken_reason": str|None, # "prev_mismatch" | "hash_mismatch"
        }

    운영 가이드:
        금융권 정기 감사 대응 — /api/v1/audit/verify 엔드포인트에서 호출.
        깨진 구간이 있으면 broken_at 과 broken_reason 확인하고
        그 시각의 시스템 로그 / 백업과 대조 필요.
    """
    rows = sorted(_store().values(), key=lambda r: r.get("ts_epoch", 0))
    total  = 0
    legacy = 0
    prev   = None
    for entry in rows:
        if not isinstance(entry, dict):
            continue
        total += 1
        if "this_hash" not in entry:
            # v10 #21 이전에 기록된 레코드 → 해시 검증 대상 아님
            legacy += 1
            continue
        # prev_hash 연결성
        if entry.get("prev_hash") != prev:
            return {
                "ok": False, "total": total, "legacy": legacy,
                "broken_at":     entry.get("id"),
                "broken_reason": "prev_mismatch",
                "expected_prev": prev,
                "actual_prev":   entry.get("prev_hash"),
            }
        # 레코드 자체 해시 재계산 일치
        expected = _compute_hash(entry, prev)
        if expected != entry.get("this_hash"):
            return {
                "ok": False, "total": total, "legacy": legacy,
                "broken_at":     entry.get("id"),
                "broken_reason": "hash_mismatch",
                "expected_hash": expected,
                "actual_hash":   entry.get("this_hash"),
            }
        prev = entry["this_hash"]
    return {"ok": True, "total": total, "legacy": legacy, "broken_at": None, "broken_reason": None}
