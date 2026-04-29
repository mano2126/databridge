"""
app/api/routes/system_live.py — 실시간 멀티 타겟 모니터 API
v10 #22 — 2026-04-24 (Phase A-1)

제공 엔드포인트:
  GET    /api/v1/system/live                        — 모든 활성 대상 스냅샷 (메인)
  GET    /api/v1/system/targets                     — 등록된 대상 목록
  POST   /api/v1/system/targets                     — 새 대상 추가
  GET    /api/v1/system/targets/{id}                — 개별 대상 조회
  PUT    /api/v1/system/targets/{id}                — 대상 수정
  DELETE /api/v1/system/targets/{id}                — 대상 삭제
  POST   /api/v1/system/targets/{id}/test           — 연결 테스트 (즉시)
  GET    /api/v1/system/adapters                    — 사용 가능한 어댑터 타입
  GET    /api/v1/system/profiles                    — 연동 가능한 DataBridge 프로파일
  GET    /api/v1/system/health                      — 기능 가용성 체크

설계:
  - 2초 서버 사이드 캐시 (다중 클라이언트 폴링 안전)
  - /live 응답은 활성 Job 도 함께 포함
  - 어댑터 실패는 해당 스냅샷의 errors 필드로 노출 (서버 실패 아님)
"""
from __future__ import annotations

import threading
import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from app.monitor import get_registry, MonitorTarget

router = APIRouter()

# ══════════════════════════════════════════════════════════
# /live 응답 캐시 (2초 TTL)
# ══════════════════════════════════════════════════════════
_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, Any] = {"data": None, "ts": 0.0}
_CACHE_TTL_SEC = 2.0

# ══════════════════════════════════════════════════════════
# v90.59: 백그라운드 워밍업 + 비동기 갱신 (모니터 첫 응답 즉시 반환)
# ══════════════════════════════════════════════════════════
# 본부장님 호소: "모니터 버튼 누르면 한참 후에야 데이터 나옴"
# 진단:
#   - 첫 호출 시 fetch_all() 이 모든 어댑터 (Localhost / Docker / DB) 직렬 호출
#   - bootstrap_auto_detect() 도 처음 1회 실행 (Docker SDK 초기화 등)
#   - 결과: 첫 응답 5~15초
# 처방 (backend 측):
#   1. 모듈 import 시 백그라운드 스레드로 사전 워밍업 → 캐시 미리 채움
#   2. /live 응답 시 stale-while-revalidate: 캐시가 있으면 즉시 반환,
#      만료되어도 우선 stale 반환 후 백그라운드에서 갱신
#   3. fetch_all 자체는 registry.py 에서 병렬화 (별도 패치)
_REFRESH_LOCK = threading.Lock()
_REFRESH_IN_PROGRESS = False
_WARMUP_STARTED = False


def _refresh_cache_async() -> None:
    """백그라운드에서 캐시 갱신. 동시 호출 방지."""
    global _REFRESH_IN_PROGRESS
    with _REFRESH_LOCK:
        if _REFRESH_IN_PROGRESS:
            return  # 이미 다른 스레드가 갱신 중
        _REFRESH_IN_PROGRESS = True
    try:
        data = _build_live_payload()
        with _CACHE_LOCK:
            _CACHE["data"] = data
            _CACHE["ts"]   = time.time()
    except Exception as e:
        # 워밍업 실패는 조용히 — /live 호출 시 정상 경로로 다시 시도
        try:
            import logging
            logging.getLogger("system_live").warning(
                "백그라운드 캐시 갱신 실패: %s", e
            )
        except Exception:
            pass
    finally:
        with _REFRESH_LOCK:
            _REFRESH_IN_PROGRESS = False


def _start_warmup_once() -> None:
    """모듈 import 시 1회 호출 — 백그라운드로 워밍업 시작."""
    global _WARMUP_STARTED
    with _REFRESH_LOCK:
        if _WARMUP_STARTED:
            return
        _WARMUP_STARTED = True
    
    def _warmup_worker():
        # FastAPI 가 완전히 뜨기 전에 fetch 하면 일부 의존성 (DB 커넥션 등)
        # 이 준비 안 됐을 수 있어 살짝 대기 (총 2초 지연 — uvicorn 시작 직후 안전)
        time.sleep(2.0)
        try:
            _refresh_cache_async()
        except Exception:
            pass  # 워밍업 실패해도 /live 호출 시 정상 fallback
    
    threading.Thread(target=_warmup_worker, daemon=True, name="monitor-warmup").start()


# 모듈 import 시점 (= FastAPI 앱이 라우터를 등록할 때) 워밍업 시작
_start_warmup_once()


def _active_jobs_snapshot() -> list[dict[str, Any]]:
    """현재 실행 중인 Job 요약."""
    try:
        from app.core.store import Store
        jobs: list[dict[str, Any]] = []
        # Store 클래스는 .all() → dict 반환. .items() 는 없음.
        for jid, j in Store("jobs").all().items():
            if not isinstance(j, dict):
                continue
            if j.get("status") not in ("running", "queued"):
                continue

            items = j.get("item_statuses", {}) or {}
            running_items = []
            for name, v in items.items():
                if isinstance(v, dict) and v.get("status") == "running":
                    running_items.append({
                        "name":       name[:40],
                        "rows_src":   int(v.get("rows_src", 0) or 0),
                        "rows_tgt":   int(v.get("rows_tgt", 0) or 0),
                        "rows_total": int(v.get("rows_total", 0) or 0),
                    })
                    if len(running_items) >= 5:
                        break

            jobs.append({
                "id":             jid,
                "name":           (j.get("name") or "")[:40],
                "status":         j.get("status"),
                "progress":       round(float(j.get("progress", 0) or 0), 1),
                "rows_processed": int(j.get("rows_processed", 0) or 0),
                "rows_total":     int(j.get("rows_total", 0) or 0),
                "table_done":     int(j.get("table_done", 0) or 0),
                "table_total":    int(j.get("table_total", 0) or 0),
                "running_items":  running_items,
            })
        return jobs
    except Exception:
        return []


def _build_live_payload() -> dict[str, Any]:
    reg = get_registry()
    snapshots = reg.fetch_all(enabled_only=True)
    return {
        "ts":        int(time.time() * 1000),
        "targets":   [snap.to_dict() for snap in snapshots],
        "jobs":      _active_jobs_snapshot(),
        "cache_ttl": _CACHE_TTL_SEC,
    }


# ══════════════════════════════════════════════════════════
# 메인 엔드포인트
# ══════════════════════════════════════════════════════════
@router.get("/system/live")
def system_live():
    """모든 활성 모니터 대상의 최신 스냅샷 + 실행 중 Job.
    
    v90.59: stale-while-revalidate 패턴
      - 캐시 있고 TTL 안 지남 → 즉시 반환 (기존)
      - 캐시 있고 TTL 지남 → stale 캐시 즉시 반환 + 백그라운드 갱신 (★ 신규)
      - 캐시 없음 → 동기적 fetch (워밍업 실패 시에만 발생)
    """
    now = time.time()
    with _CACHE_LOCK:
        cached_data = _CACHE["data"]
        cached_ts   = _CACHE["ts"]
    
    if cached_data is not None:
        age = now - cached_ts
        if age < _CACHE_TTL_SEC:
            # 신선한 캐시 — 그대로 반환
            return cached_data
        # stale 캐시 — 즉시 반환하되 백그라운드에서 갱신 (★ v90.59)
        # 사용자는 최대 2초 + α 정도 오래된 데이터를 보지만 응답은 즉시
        threading.Thread(target=_refresh_cache_async, daemon=True,
                         name="monitor-refresh").start()
        # stale 임을 메타로 표시 (선택적 — 클라이언트가 활용 가능)
        out = dict(cached_data)
        out["_cache_age_sec"] = round(age, 2)
        out["_cache_stale"]   = True
        return out
    
    # 캐시 비어있음 — 워밍업이 아직 못 끝낸 경우 동기 fetch (느림)
    data = _build_live_payload()
    with _CACHE_LOCK:
        _CACHE["data"] = data
        _CACHE["ts"]   = time.time()
    return data


# ══════════════════════════════════════════════════════════
# 대상 CRUD
# ══════════════════════════════════════════════════════════
def _target_to_response(t: MonitorTarget) -> dict[str, Any]:
    """UI 응답용 — 민감 정보 마스킹."""
    cfg = dict(t.config or {})
    for sensitive in ("password", "tls_key", "ssh_password", "winrm_password"):
        if sensitive in cfg and cfg[sensitive]:
            cfg[sensitive] = "••••••••"
    return {
        "target_id":     t.target_id,
        "target_type":   t.target_type,
        "display_name":  t.display_name,
        "enabled":       t.enabled,
        "config":        cfg,
        "created_at":    t.created_at,
        "auto_detected": t.auto_detected,
        "profile_id":    t.profile_id,
    }


@router.get("/system/targets")
def list_targets():
    """등록된 모든 모니터 대상 (자동 감지 포함)."""
    reg = get_registry()
    reg.bootstrap_auto_detect()
    return {"targets": [_target_to_response(t) for t in reg.list_targets()]}


@router.post("/system/targets")
def create_target(body: dict):
    """새 모니터 대상 추가."""
    if not body.get("target_type"):
        raise HTTPException(400, "target_type 필수")
    if not body.get("display_name"):
        raise HTTPException(400, "display_name 필수")

    t = MonitorTarget(
        target_id    = "",
        target_type  = body["target_type"],
        display_name = body["display_name"],
        enabled      = bool(body.get("enabled", True)),
        config       = dict(body.get("config") or {}),
        profile_id   = body.get("profile_id"),
    )
    t = get_registry().add_target(t)
    with _CACHE_LOCK:
        _CACHE["data"] = None
    return _target_to_response(t)


@router.get("/system/targets/{target_id}")
def get_target(target_id: str):
    t = get_registry().get_target(target_id)
    if not t:
        raise HTTPException(404, "대상을 찾을 수 없음")
    return _target_to_response(t)


@router.put("/system/targets/{target_id}")
def update_target(target_id: str, body: dict):
    t = get_registry().update_target(target_id, body)
    if not t:
        raise HTTPException(404, "대상을 찾을 수 없음")
    with _CACHE_LOCK:
        _CACHE["data"] = None
    return _target_to_response(t)


@router.delete("/system/targets/{target_id}", status_code=204)
def delete_target(target_id: str):
    ok = get_registry().delete_target(target_id)
    if not ok:
        raise HTTPException(404, "대상을 찾을 수 없음")
    with _CACHE_LOCK:
        _CACHE["data"] = None
    return None


@router.post("/system/targets/{target_id}/test")
def test_target(target_id: str):
    """단일 대상 즉시 조회 (캐시 무시)."""
    adapter = get_registry().get_adapter(target_id)
    if adapter is None:
        raise HTTPException(404, "대상/어댑터를 찾을 수 없음")
    try:
        snap = adapter.fetch_snapshot()
        return snap.to_dict()
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {str(e)[:120]}")


# ══════════════════════════════════════════════════════════
# 메타 API
# ══════════════════════════════════════════════════════════
@router.get("/system/adapters")
def list_adapters():
    """UI 용 어댑터 타입 목록."""
    return {
        "adapters": [
            {"type": "localhost",
             "name": "이 PC (로컬 시스템)",
             "description": "DataBridge 가 실행되는 OS 자신의 CPU/메모리/디스크",
             "needs_auth": False,
             "phase": "A"},
            {"type": "docker",
             "name": "Docker 컨테이너",
             "description": "로컬 또는 원격 Docker 데몬의 컨테이너 stats/health",
             "needs_auth": False,
             "phase": "A"},
            {"type": "db_native",
             "name": "DB 자체 성능 뷰 (Migration-Aware)",
             "description": "MSSQL DMV / MySQL SHOW STATUS 등 이관 성능 직결 지표",
             "needs_auth": True,
             "supports_profile_reuse": True,
             "phase": "A"},
            {"type": "ssh",
             "name": "원격 Linux 서버 (SSH)",
             "description": "SSH 로 원격 호스트의 시스템 지표 수집",
             "needs_auth": True,
             "phase": "C",
             "available": False},
            {"type": "winrm",
             "name": "원격 Windows 서버 (WinRM)",
             "description": "Windows Remote Management",
             "needs_auth": True,
             "phase": "C",
             "available": False},
        ],
    }


@router.get("/system/profiles")
def list_profiles_for_monitor():
    """DataBridge Connection Profile 목록 (비밀번호 제외)."""
    out: list[dict] = []
    try:
        from app.core.store import Store
        # Store 클래스는 .all() → dict 반환. .items() 는 없음.
        for pid, p in Store("profiles").all().items():
            if not isinstance(p, dict):
                continue
            for which in ("source", "target"):
                cfg = p.get(which)
                if not isinstance(cfg, dict):
                    continue
                out.append({
                    "profile_id":   pid,
                    "profile_name": p.get("name", pid),
                    "which":        which,
                    "db_type":      cfg.get("db_type"),
                    "host":         cfg.get("host"),
                    "database":     cfg.get("database"),
                    "version":      cfg.get("version"),
                })
    except Exception:
        pass
    return {"profiles": out}


@router.get("/system/health")
def monitor_self_health():
    """모니터 기능 자체 가용성."""
    # v10 #22 Phase A-3: try_import 로 런타임 설치도 즉시 감지
    from app.monitor.import_retry import try_import, get_status as retry_status

    psutil_mod = try_import("psutil")
    docker_mod = try_import("docker")

    psutil_ok = psutil_mod is not None
    docker_ok = False
    psutil_err: Optional[str] = None
    docker_err: Optional[str] = None

    if psutil_mod is None:
        psutil_err = "psutil not installed (or retry cooldown)"

    if docker_mod is not None:
        try:
            c = docker_mod.from_env(timeout=2)
            c.ping()
            docker_ok = True
            try: c.close()
            except: pass
        except Exception as e:
            docker_err = f"{type(e).__name__}: {str(e)[:120]}"
    else:
        docker_err = "docker SDK not installed (or retry cooldown)"

    reg = get_registry()
    targets = reg.list_targets()
    by_type: dict[str, int] = {}
    for t in targets:
        by_type[t.target_type] = by_type.get(t.target_type, 0) + 1

    return {
        "ok": psutil_ok,
        "psutil": {"available": psutil_ok, "error": psutil_err},
        "docker": {"available": docker_ok, "error": docker_err},
        "registry": {
            "target_count":    len(targets),
            "enabled_count":   sum(1 for t in targets if t.enabled),
            "by_type":         by_type,
        },
        "cache_ttl_sec": _CACHE_TTL_SEC,
        # v10 #22 Phase A-3: import 재시도 상태 (디버깅/투명성)
        "import_retry": retry_status(),
    }
