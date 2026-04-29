"""
app/core/license.py
라이선스 키 검증 — 상업 배포 관리.

핵심 원칙:
  1. **오프라인 검증** — Ed25519 공개키로 파일 서명만 확인, 외부 네트워크 불필요
  2. **graceful degrade** — 라이선스 없으면 "community" 모드 (제한된 기능)
  3. **만료 강제** — 만료된 라이선스는 community로 자동 폴백, 유예 기간 7일 경고
  4. **기능 플래그** — edition별로 on/off 할 기능들을 payload에 담음

Edition 체계:
  - community: 라이선스 없이 동작. Tier 1 DB만, 동시 잡 1개, 감사 30일 보존
  - standard:  중소기업용. Tier 1/2, 동시 잡 3개
  - enterprise: 대기업용. 모든 tier, 무제한 동시, 감사 1년

라이선스 파일 위치:
  - 우선순위 1: 환경변수 `DATABRIDGE_LICENSE_PATH`
  - 우선순위 2: `<project>/license.key`
  - 우선순위 3: `<backend>/data/license.key`

서명 검증:
  - Ed25519 공개키는 app/core/license_pubkey.pem 에 포함 (배포 시 교체)
  - 개인키는 Anthropic(또는 판매사) 내부 보관 — 절대 배포 금지
  - cryptography 라이브러리의 Ed25519PublicKey 사용

런타임 사용:
    from app.core.license import get_license, check_feature
    lic = get_license()  # 기동 시 1회 로드됨
    if lic.edition == "community":
        ...
    if check_feature("tier2_tier3_dbs"):
        ...
"""
from __future__ import annotations
import base64
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("databridge.license")

_KST = timezone(timedelta(hours=9))


# ── Edition 기본 기능 매트릭스 ──────────────────────────

COMMUNITY_FEATURES = {
    "max_concurrent_jobs":   1,
    "max_table_size_gb":     50,     # 50GB 까지
    "tier2_tier3_dbs":       False,
    "audit_retention_days":  30,
    "custom_sql_rules":      False,
    "websocket_monitor":     True,
    "resume_from_checkpoint": True,
    "rbac":                  True,
}

STANDARD_FEATURES = {
    "max_concurrent_jobs":   3,
    "max_table_size_gb":     500,
    "tier2_tier3_dbs":       True,
    "audit_retention_days":  90,
    "custom_sql_rules":      True,
    "websocket_monitor":     True,
    "resume_from_checkpoint": True,
    "rbac":                  True,
}

ENTERPRISE_FEATURES = {
    "max_concurrent_jobs":   None,    # 무제한
    "max_table_size_gb":     None,    # 무제한
    "tier2_tier3_dbs":       True,
    "audit_retention_days":  365,
    "custom_sql_rules":      True,
    "websocket_monitor":     True,
    "resume_from_checkpoint": True,
    "rbac":                  True,
}

_EDITION_DEFAULTS = {
    "community":  COMMUNITY_FEATURES,
    "standard":   STANDARD_FEATURES,
    "enterprise": ENTERPRISE_FEATURES,
}


@dataclass
class License:
    """현재 활성 라이선스 상태"""
    edition:         str           # community|standard|enterprise
    customer:        str = "—"
    issued_at:       str = ""
    expires_at:      str = ""      # ISO date or "" for community
    license_id:      str = ""
    features:        dict = field(default_factory=dict)
    valid:           bool = True   # 서명 검증 결과
    expired:         bool = False
    days_remaining:  Optional[int] = None   # None = 무제한
    warning:         str = ""      # 만료 임박 등
    source_path:     str = ""      # 라이선스 파일 경로 (있으면)

    def feature(self, name: str, default: Any = False) -> Any:
        return self.features.get(name, default)

    def to_dict(self) -> dict:
        return {
            "edition":        self.edition,
            "customer":       self.customer,
            "issued_at":      self.issued_at,
            "expires_at":     self.expires_at,
            "license_id":     self.license_id,
            "features":       self.features,
            "valid":          self.valid,
            "expired":        self.expired,
            "days_remaining": self.days_remaining,
            "warning":        self.warning,
        }


# ── 내부: 서명 검증 ────────────────────────────────────────

_PUBKEY_PEM_PATH = Path(__file__).parent / "license_pubkey.pem"


def _verify_signature(payload_bytes: bytes, signature_b64: str) -> bool:
    """
    Ed25519 서명 검증. 공개키 PEM 파일이 없으면 False 반환.
    """
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.exceptions import InvalidSignature
    except ImportError:
        logger.warning("cryptography 미설치 — 라이선스 서명 검증 불가")
        return False

    if not _PUBKEY_PEM_PATH.exists():
        logger.warning("라이선스 공개키 파일 없음: %s", _PUBKEY_PEM_PATH)
        return False

    try:
        pubkey_pem = _PUBKEY_PEM_PATH.read_bytes()
        pubkey = load_pem_public_key(pubkey_pem)
        signature = base64.b64decode(signature_b64)
        pubkey.verify(signature, payload_bytes)
        return True
    except Exception as e:
        logger.info("라이선스 서명 검증 실패: %s", type(e).__name__)
        return False


# ── 라이선스 로드 ──────────────────────────────────────────

def _find_license_path() -> Optional[Path]:
    """설정 우선순위대로 라이선스 파일 경로를 찾음"""
    # 1. 환경변수
    env_path = os.environ.get("DATABRIDGE_LICENSE_PATH", "").strip()
    if env_path:
        p = Path(env_path).expanduser()
        if p.exists():
            return p

    # 2. 프로젝트 루트
    # backend 기준으로 ../license.key
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / "license.key",   # 프로젝트 루트
        here.parents[2] / "license.key",   # backend 루트
        here.parents[2] / "data" / "license.key",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _load_license_file(path: Path) -> Optional[License]:
    """파일에서 라이선스 로드 + 서명 검증"""
    try:
        content = path.read_text(encoding="utf-8").strip()
        data = json.loads(content)
        payload = data.get("payload") or {}
        signature = data.get("signature") or ""

        # 서명 검증
        payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if not _verify_signature(payload_bytes, signature):
            logger.error("라이선스 서명 무효: %s", path)
            return None

        # 필수 필드 확인
        edition = (payload.get("edition") or "community").lower()
        if edition not in ("standard", "enterprise"):
            logger.warning("알 수 없는 edition 값: %s — community 폴백", edition)
            return None

        # 만료 계산
        expires_at = payload.get("expires_at", "")
        expired = False
        days_remaining = None
        warning = ""
        if expires_at:
            try:
                # "2027-04-18" 같은 ISO date 지원
                exp_dt = datetime.fromisoformat(expires_at)
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=_KST)
                now = datetime.now(_KST)
                delta = exp_dt - now
                days_remaining = delta.days
                if delta.total_seconds() <= 0:
                    expired = True
                    warning = f"라이선스 만료됨 ({expires_at}) — community 모드로 동작"
                elif days_remaining <= 7:
                    warning = f"라이선스 {days_remaining}일 후 만료 ({expires_at})"
            except Exception as e:
                logger.warning("expires_at 파싱 실패: %s — %s", expires_at, e)

        # 기능 병합: edition 기본값 + payload의 override
        features = dict(_EDITION_DEFAULTS.get(edition, COMMUNITY_FEATURES))
        features.update(payload.get("features") or {})

        return License(
            edition=edition if not expired else "community",
            customer=payload.get("customer", "—"),
            issued_at=payload.get("issued_at", ""),
            expires_at=expires_at,
            license_id=payload.get("license_id", ""),
            features=features if not expired else COMMUNITY_FEATURES,
            valid=True,
            expired=expired,
            days_remaining=days_remaining,
            warning=warning,
            source_path=str(path),
        )
    except Exception as e:
        logger.error("라이선스 파일 로드 실패 %s: %s", path, e)
        return None


# ── 싱글톤 상태 ────────────────────────────────────────────

_CURRENT: Optional[License] = None


def load_license() -> License:
    """
    기동 시 한 번 호출 — 라이선스 파일 탐색 → 검증 → 메모리 캐싱.
    실패 시 community 라이선스로 폴백.

    v10 #3 (2026-04-20): DEV MODE 추가
      환경변수 DATABRIDGE_DEV_MODE=1 설정 시 라이선스 파일 유무와 무관하게
      모든 제한을 풀고 enterprise 무제한 모드로 동작.
      개발/테스트 중 라이선스 때문에 테스트가 막히는 것 방지용.
      상용 배포 시엔 환경변수를 빼기만 하면 원래 동작 복원 (코드 수정 불필요).
    """
    global _CURRENT

    # v10 #3: 개발 모드 — 환경변수 1 회 체크, 강제 enterprise 무제한
    dev_mode = os.environ.get("DATABRIDGE_DEV_MODE", "").strip().lower()
    if dev_mode in ("1", "true", "yes", "on"):
        _CURRENT = License(
            edition="enterprise",
            customer="개발모드 (DEV MODE)",
            features=dict(ENTERPRISE_FEATURES),
            valid=True,
            warning="⚠️ DEV MODE — 라이선스 체크 비활성화 (상용 배포 전 DATABRIDGE_DEV_MODE 제거 필요)",
        )
        logger.warning(
            "=" * 70 + "\n"
            "[라이선스] ⚠️  DEV MODE 활성 — 모든 라이선스 제한 해제됨\n"
            "           상용 배포 시 환경변수 DATABRIDGE_DEV_MODE 반드시 제거\n"
            + "=" * 70
        )
        return _CURRENT

    path = _find_license_path()
    if path is not None:
        lic = _load_license_file(path)
        if lic is not None:
            _CURRENT = lic
            if lic.warning:
                logger.warning("[라이선스] %s", lic.warning)
            logger.info("[라이선스] %s edition (%s, %s) 활성",
                        lic.edition, lic.customer, lic.license_id or "no-id")
            return lic

    # 폴백: community
    _CURRENT = License(
        edition="community",
        customer="커뮤니티 사용자",
        features=dict(COMMUNITY_FEATURES),
        valid=True,
        warning="라이선스 파일 없음 — community 모드 (제한된 기능)",
    )
    logger.info("[라이선스] community 모드 — %s",
                "유효 라이선스 파일 없음" if path is None else "로드 실패")
    return _CURRENT


def get_license() -> License:
    """현재 활성 라이선스 반환. 아직 로드 안 됐으면 즉시 로드."""
    global _CURRENT
    if _CURRENT is None:
        return load_license()
    return _CURRENT


def reload_license() -> License:
    """파일을 다시 읽어 갱신 — 라이선스 교체 후 재기동 없이 반영"""
    global _CURRENT
    _CURRENT = None
    return load_license()


def check_feature(name: str) -> bool:
    """특정 기능이 허용됐는지 — True/False"""
    lic = get_license()
    v = lic.features.get(name, False)
    if v is None:         # None = 무제한
        return True
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v > 0
    return bool(v)


def check_limit(name: str, current_value: int) -> tuple[bool, Optional[int]]:
    """
    수치 제한 검사. (허용여부, limit) 튜플 반환.
    limit None 이면 무제한.

    예: check_limit("max_concurrent_jobs", running_count)
    """
    lic = get_license()
    limit = lic.features.get(name)
    if limit is None:
        return (True, None)
    if isinstance(limit, (int, float)):
        return (current_value < limit, int(limit))
    return (True, None)
