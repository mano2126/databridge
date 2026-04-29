"""
app/core/auth.py
RBAC — 사용자·역할·세션 토큰 관리.

역할 정의:
  admin    : 모든 권한 (사용자 관리, 설정 변경, 이관 실행/편집, 삭제)
  operator : 이관 실행·편집·재개, 프로파일 관리 (설정/사용자 관리 불가)
  viewer   : 조회만 (잡 목록, 로그, 스키마 보기)

권한 매트릭스 (간략):
                  admin  operator  viewer  guest
  /settings PUT    O       X        X       X
  /users    *      O       X        X       X
  /jobs POST       O       O        X       X
  /jobs PUT        O       O        X       X
  /jobs DELETE     O       O        X       X
  /jobs resume     O       O        X       X
  /jobs GET        O       O        O       X   (인증 자체는 필요)
  /schema GET      O       O        O       X
  /connectors GET  O       O        O       X
  /health          O       O        O       O   (인증 불필요)

저장:
  users    Store에 { username: {password_hash, role, created_at, ...} }
  sessions Store에 { token: {username, role, expires_at, created_at} }
  비밀번호는 salt+pbkdf2 해시 (단방향, Fernet 아님)

기본 계정:
  첫 기동 시 users 스토어가 비어있으면 'admin' 계정 생성 후
  랜덤 비번을 WARNING 로그로 1회 출력. 운영자가 로그인 후 반드시 변경.
"""
from __future__ import annotations
import hashlib
import hmac
import logging
import os
import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("databridge.auth")

_KST = timezone(timedelta(hours=9))

# 세션 유효기간 (기본 24시간)
SESSION_TTL_SECONDS = int(os.environ.get("DATABRIDGE_SESSION_TTL", "86400"))

# PBKDF2 반복횟수 (NIST 권장 600,000 이상)
_PBKDF2_ITERS = 600_000

# 역할 계층 — 상위가 하위 권한 포함
ROLES = ("admin", "operator", "viewer")

_ROLE_RANK = {"admin": 3, "operator": 2, "viewer": 1, "guest": 0}


# ── 비밀번호 해시 ────────────────────────────────────────

def _hash_password(password: str, salt: bytes | None = None) -> str:
    """
    pbkdf2-hmac-sha256. 결과 포맷: "pbkdf2_sha256$<iters>$<salt_hex>$<hash_hex>"
    """
    if salt is None:
        salt = secrets.token_bytes(16)
    if isinstance(salt, str):
        salt = bytes.fromhex(salt)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERS)
    return f"pbkdf2_sha256${_PBKDF2_ITERS}${salt.hex()}${dk.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored_hash.split("$")
        if algo != "pbkdf2_sha256":
            return False
        iters = int(iters)
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


# ── Store 래퍼 (지연 import — 순환 의존 방지) ──────────────

def _users_store():
    from app.core.store import Store
    return Store("users")


def _sessions_store():
    from app.core.store import Store
    return Store("sessions")


# ── 사용자 관리 ──────────────────────────────────────────

def create_user(username: str, password: str, role: str = "viewer") -> dict:
    """신규 사용자 생성. 이미 있으면 ValueError."""
    if role not in ROLES:
        raise ValueError(f"유효하지 않은 역할: {role}")
    if not username or not password:
        raise ValueError("username/password 필수")
    s = _users_store()
    if username in s:
        raise ValueError(f"이미 존재하는 사용자: {username}")
    entry = {
        "username":   username,
        "password_hash": _hash_password(password),
        "role":       role,
        "created_at": datetime.now(_KST).isoformat(),
        "last_login": None,
        "disabled":   False,
    }
    s.set(username, entry)
    logger.info("사용자 생성: %s (role=%s)", username, role)
    return {"username": username, "role": role, "created_at": entry["created_at"]}


def update_user_password(username: str, new_password: str) -> bool:
    s = _users_store()
    u = s.get(username)
    if not u:
        return False
    u["password_hash"] = _hash_password(new_password)
    u["password_changed_at"] = datetime.now(_KST).isoformat()
    s.set(username, u)
    return True


def update_user_role(username: str, new_role: str) -> bool:
    if new_role not in ROLES:
        raise ValueError(f"유효하지 않은 역할: {new_role}")
    s = _users_store()
    u = s.get(username)
    if not u:
        return False
    u["role"] = new_role
    s.set(username, u)
    logger.info("사용자 역할 변경: %s → %s", username, new_role)
    return True


def disable_user(username: str) -> bool:
    s = _users_store()
    u = s.get(username)
    if not u:
        return False
    u["disabled"] = True
    s.set(username, u)
    # 해당 사용자의 모든 세션 폐기
    for token, sess in list(_sessions_store().all().items()):
        if sess.get("username") == username:
            _sessions_store().delete(token)
    return True


def list_users() -> list:
    """사용자 목록 (비밀번호 해시 제외)"""
    out = []
    for u in _users_store().values():
        out.append({
            "username":   u.get("username"),
            "role":       u.get("role"),
            "created_at": u.get("created_at"),
            "last_login": u.get("last_login"),
            "disabled":   u.get("disabled", False),
        })
    return out


def delete_user(username: str) -> bool:
    s = _users_store()
    if username not in s:
        return False
    s.delete(username)
    # 세션 정리
    for token, sess in list(_sessions_store().all().items()):
        if sess.get("username") == username:
            _sessions_store().delete(token)
    return True


# ── 로그인 / 세션 ────────────────────────────────────────

def authenticate(username: str, password: str) -> Optional[dict]:
    """
    로그인 시도. 성공 시 { token, role, username, expires_at } 반환.
    실패 시 None.
    """
    u = _users_store().get(username)
    if not u:
        return None
    if u.get("disabled"):
        logger.warning("비활성 사용자 로그인 시도: %s", username)
        return None
    if not _verify_password(password, u.get("password_hash", "")):
        return None

    token = secrets.token_urlsafe(32)
    now = int(time.time())
    sess = {
        "token":      token,
        "username":   username,
        "role":       u["role"],
        "created_at": now,
        "expires_at": now + SESSION_TTL_SECONDS,
    }
    _sessions_store().set(token, sess)

    # 마지막 로그인 기록
    u["last_login"] = datetime.now(_KST).isoformat()
    _users_store().set(username, u)

    return {
        "token":      token,
        "username":   username,
        "role":       u["role"],
        "expires_at": sess["expires_at"],
    }


def resolve_session(token: str) -> Optional[dict]:
    """
    토큰으로 세션 조회. 만료됐으면 자동 삭제 후 None.
    """
    if not token:
        return None
    sess = _sessions_store().get(token)
    if not sess:
        return None
    if sess.get("expires_at", 0) < int(time.time()):
        _sessions_store().delete(token)
        return None
    return sess


def logout(token: str) -> bool:
    s = _sessions_store()
    if token in s:
        s.delete(token)
        return True
    return False


# ── 권한 체크 ────────────────────────────────────────────

def has_role(current_role: str, required_role: str) -> bool:
    """상위 역할은 하위 권한 자동 포함"""
    return _ROLE_RANK.get(current_role, 0) >= _ROLE_RANK.get(required_role, 999)


# ── 첫 기동 초기화 ───────────────────────────────────────

def ensure_default_admin() -> Optional[str]:
    """
    사용자가 한 명도 없으면 기본 admin 계정 생성.
    생성한 임시 비밀번호를 반환 (운영자가 로그인 후 즉시 변경해야 함).
    이미 사용자가 있으면 None.
    """
    s = _users_store()
    if len(s) > 0:
        return None
    temp_pw = secrets.token_urlsafe(12)
    create_user("admin", temp_pw, role="admin")
    logger.warning("=" * 60)
    logger.warning("기본 admin 계정 생성됨 — 로그인 후 즉시 비밀번호 변경 필수")
    logger.warning("username: admin")
    logger.warning("password: %s", temp_pw)
    logger.warning("=" * 60)
    return temp_pw


def cleanup_expired_sessions() -> int:
    """만료된 세션 일괄 제거. shutdown/유지보수 시 호출 권장."""
    now = int(time.time())
    s = _sessions_store()
    removed = 0
    for token, sess in list(s.all().items()):
        if sess.get("expires_at", 0) < now:
            s.delete(token)
            removed += 1
    return removed
