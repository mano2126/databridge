"""
app/core/crypto.py
대칭키 암호화 헬퍼 — DB 비밀번호·API 키 등 민감 정보 암호화용

설계:
  - Fernet (AES-128-CBC + HMAC-SHA256) — 파이썬 cryptography 라이브러리 표준
  - 마스터 키는 최초 실행 시 backend/data/.master.key 에 자동 생성
  - 파일 권한 0600 (소유자만 읽기) — 리눅스/맥 한정, 윈도우는 ACL 불가
  - 마스터 키는 절대 git에 포함되지 않음 (.gitignore에 이미 backend/data/ 제외)
  - 암호화된 값은 prefix "enc::" 로 식별 → is_encrypted() 로 판별
  - 기존 평문 데이터가 있을 경우 migrate_plaintext() 로 일괄 업그레이드

보안 주의사항:
  - 마스터 키를 분실하면 암호화된 비밀번호 복호화 불가 → 프로파일 재입력 필요
  - 운영 환경에서는 환경변수 DATABRIDGE_MASTER_KEY 로도 주입 가능 (AWS KMS, Vault 연동 여지)
  - 키 로테이션은 현 버전 미지원 (v2.1 계획)
"""
from __future__ import annotations
import base64
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("databridge.crypto")

# ── Fernet 로딩 (의존성 없으면 graceful degrade) ────────────
try:
    from cryptography.fernet import Fernet, InvalidToken
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore
    logger.warning(
        "cryptography 미설치 — 비밀번호 평문 저장됨 (개발 전용). "
        "운영 전 'pip install cryptography' 필수."
    )

# 암호화된 값 식별 prefix
_PREFIX = "enc::"

# 마스터 키 경로 (backend/data/.master.key)
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_KEY_PATH = _DATA_DIR / ".master.key"

# 싱글턴 Fernet 인스턴스
_cipher: "Fernet | None" = None


# ── 마스터 키 관리 ────────────────────────────────────────

def _load_or_create_key() -> bytes:
    """
    마스터 키를 로드하거나 신규 생성.
    우선순위:
      1. 환경변수 DATABRIDGE_MASTER_KEY (base64 urlsafe 32바이트)
      2. 파일 backend/data/.master.key
      3. 신규 생성 → 파일 저장
    """
    # 1. 환경변수 우선
    env_key = os.environ.get("DATABRIDGE_MASTER_KEY", "").strip()
    if env_key:
        try:
            # 검증: Fernet이 받을 수 있는 형식인지
            Fernet(env_key.encode())
            logger.info("마스터 키: 환경변수 DATABRIDGE_MASTER_KEY 사용")
            return env_key.encode()
        except Exception as e:
            logger.warning("DATABRIDGE_MASTER_KEY 형식 오류 — 파일/신규 키로 대체: %s", e)

    # 2. 파일에서 로드
    _DATA_DIR.mkdir(exist_ok=True)
    if _KEY_PATH.exists():
        try:
            key = _KEY_PATH.read_bytes().strip()
            Fernet(key)  # 검증
            return key
        except Exception as e:
            logger.error("마스터 키 파일 손상 — 새 키 생성: %s", e)

    # 3. 신규 생성
    key = Fernet.generate_key()
    _KEY_PATH.write_bytes(key)
    try:
        os.chmod(_KEY_PATH, 0o600)  # rw------- (유닉스만 효과)
    except Exception:
        pass
    logger.warning(
        "새 마스터 키 생성 → %s. 이 파일을 분실하면 기존 암호화 데이터를 복호화할 수 없습니다.",
        _KEY_PATH,
    )
    return key


def _get_cipher() -> "Fernet | None":
    """싱글턴 Fernet 인스턴스"""
    global _cipher
    if _cipher is None and _HAS_CRYPTO:
        try:
            _cipher = Fernet(_load_or_create_key())
        except Exception as e:
            logger.error("Fernet 초기화 실패: %s", e)
            _cipher = None
    return _cipher


# ── 공개 API ──────────────────────────────────────────────

def is_available() -> bool:
    """암호화 사용 가능 여부 (cryptography 설치 + 마스터 키 OK)"""
    return _HAS_CRYPTO and _get_cipher() is not None


def is_encrypted(value: Any) -> bool:
    """이미 암호화된 값인지 (prefix 확인)"""
    return isinstance(value, str) and value.startswith(_PREFIX)


def encrypt(plaintext: str) -> str:
    """
    평문을 암호화. 빈 문자열/None은 그대로 반환.
    cryptography 미설치 시 경고 로그 후 평문 그대로 반환 (graceful degrade).
    """
    if not plaintext:
        return plaintext
    if is_encrypted(plaintext):
        return plaintext  # 이미 암호화됨 — 재암호화 방지

    cipher = _get_cipher()
    if cipher is None:
        logger.warning("암호화 불가 (cryptography 미설치) — 평문 저장")
        return plaintext

    try:
        token = cipher.encrypt(plaintext.encode("utf-8")).decode("ascii")
        return _PREFIX + token
    except Exception as e:
        logger.error("암호화 실패: %s", e)
        return plaintext


def decrypt(ciphertext: str) -> str:
    """
    암호문을 복호화. prefix가 없으면 평문으로 간주하고 그대로 반환
    (마이그레이션 전 데이터 호환용).
    """
    if not ciphertext:
        return ciphertext
    if not is_encrypted(ciphertext):
        return ciphertext  # 평문이거나 마이그레이션 전 데이터

    cipher = _get_cipher()
    if cipher is None:
        logger.error("복호화 불가 (cryptography 미설치)")
        return ""

    try:
        token = ciphertext[len(_PREFIX):].encode("ascii")
        return cipher.decrypt(token).decode("utf-8")
    except InvalidToken:
        logger.error("복호화 실패: 토큰 무효 — 마스터 키가 바뀌었을 가능성")
        return ""
    except Exception as e:
        logger.error("복호화 실패: %s", e)
        return ""


def mask(value: str, keep: int = 0) -> str:
    """
    API 응답 등에서 비밀번호를 마스킹해 반환.
    keep=0 → 전부 ●, keep=2 → 마지막 2자만 유지.
    암호화/평문 상관없이 고정 길이 마스크 반환 (존재 여부만 알림).
    """
    if not value:
        return ""
    if is_encrypted(value):
        return "●●●●●●●●"  # 존재는 알리되 내부 길이/내용 노출 안 함
    if keep <= 0 or len(value) <= keep:
        return "●" * 8
    return "●" * (len(value) - keep) + value[-keep:]


# ── 마이그레이션 유틸 ─────────────────────────────────────

def migrate_store_passwords(store_name: str, fields: list[str]) -> int:
    """
    Store 내 특정 필드들을 일괄 암호화.
    기존 평문 데이터를 첫 실행 시 업그레이드하는 용도.

    Args:
      store_name: Store 이름 (예: "profiles", "jobs")
      fields: 암호화할 필드 경로 리스트. 점(.)으로 중첩 표현.
              예) ["source.password", "target.password"] → profiles의 각 엔트리에서 source.password와 target.password 암호화

    Returns:
      업그레이드된 엔트리 수
    """
    from app.core.store import Store
    store = Store(store_name)
    upgraded = 0

    for key, entry in list(store.all().items()):
        if not isinstance(entry, dict):
            continue
        changed = False
        for field_path in fields:
            parts = field_path.split(".")
            # 중첩 dict에서 값 찾아 암호화
            cursor = entry
            for p in parts[:-1]:
                if not isinstance(cursor, dict) or p not in cursor:
                    cursor = None
                    break
                cursor = cursor[p]
            if not isinstance(cursor, dict):
                continue
            leaf = parts[-1]
            val = cursor.get(leaf)
            if isinstance(val, str) and val and not is_encrypted(val):
                cursor[leaf] = encrypt(val)
                changed = True
        if changed:
            store.set(key, entry)
            upgraded += 1

    if upgraded > 0:
        logger.info("Store '%s': %d개 엔트리 비밀번호 암호화 업그레이드", store_name, upgraded)
    return upgraded
