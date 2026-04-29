"""
app/api/routes/auth.py
인증 · 사용자 관리 REST API.
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from typing import Optional

from app.core import auth
from app.core import audit
from app.core.audit import Actions
from app.core.auth_deps import require_admin, current_user

router = APIRouter()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


# ── 로그인 / 로그아웃 ──────────────────────────────────

@router.post("/login")
def login(body: dict, request: Request):
    """body: { username, password }"""
    username = body.get("username", "").strip()
    password = body.get("password", "")
    ip = _client_ip(request)
    if not username or not password:
        raise HTTPException(400, "username/password 필수")
    result = auth.authenticate(username, password)
    if not result:
        # 실패 기록
        audit.record(
            action=Actions.LOGIN_FAIL, status="fail",
            user={"username": username, "role": "anonymous"},
            resource="session", ip=ip,
        )
        raise HTTPException(401, "인증 실패 — username 또는 password 오류")
    # 성공 기록
    audit.record(
        action=Actions.LOGIN_OK, status="ok",
        user={"username": result["username"], "role": result["role"]},
        resource="session", ip=ip,
    )
    return result


@router.post("/logout")
def logout(request: Request,
           x_auth_token: Optional[str] = Header(default=None, alias="X-Auth-Token"),
           user=Depends(current_user)):
    token = x_auth_token or request.query_params.get("token") or ""
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
    if not token:
        return {"ok": False, "message": "토큰 없음"}
    ok = auth.logout(token)
    if ok and user:
        audit.record(action=Actions.LOGOUT, user=user, resource="session",
                     ip=_client_ip(request))
    return {"ok": ok}


# ── 내 정보 ───────────────────────────────────────────

@router.get("/me")
def me(user=Depends(current_user)):
    if not user:
        raise HTTPException(401, "로그인되지 않음")
    # 토큰은 응답에 포함하지 않음 (이미 클라이언트가 가지고 있음)
    return {
        "username": user.get("username"),
        "role":     user.get("role"),
        "expires_at": user.get("expires_at"),
        "rbac_disabled": user.get("rbac_disabled", False),
    }


@router.post("/change-password")
def change_password(body: dict, request: Request, user=Depends(current_user)):
    """
    body: { old_password, new_password }
    본인 비번 변경. admin이라도 다른 사용자 비번은 /reset-password 로.
    """
    if not user:
        raise HTTPException(401, "로그인되지 않음")
    old_pw = body.get("old_password", "")
    new_pw = body.get("new_password", "")
    if not old_pw or not new_pw:
        raise HTTPException(400, "old_password / new_password 필수")
    if len(new_pw) < 8:
        raise HTTPException(400, "새 비밀번호는 8자 이상이어야 합니다")

    username = user.get("username")
    # 기존 비번 확인
    re_auth = auth.authenticate(username, old_pw)
    if not re_auth:
        audit.record(action=Actions.PASSWORD_CHANGE, status="fail",
                     user=user, resource="user", resource_id=username,
                     ip=_client_ip(request))
        raise HTTPException(403, "기존 비밀번호가 일치하지 않습니다")

    auth.update_user_password(username, new_pw)
    audit.record(action=Actions.PASSWORD_CHANGE, status="ok",
                 user=user, resource="user", resource_id=username,
                 ip=_client_ip(request))
    return {"ok": True, "message": "비밀번호가 변경됐습니다"}


# ── 사용자 관리 (admin) ────────────────────────────────

@router.get("/users")
def list_users(admin=Depends(require_admin)):
    return auth.list_users()


@router.post("/users", status_code=201)
def create_user(body: dict, request: Request, admin=Depends(require_admin)):
    """body: { username, password, role }"""
    username = body.get("username", "").strip()
    password = body.get("password", "")
    role = body.get("role", "viewer")
    if not username or not password:
        raise HTTPException(400, "username/password 필수")
    if len(password) < 8:
        raise HTTPException(400, "비밀번호는 8자 이상이어야 합니다")
    if role not in auth.ROLES:
        raise HTTPException(400, f"role은 {auth.ROLES} 중 하나여야 합니다")
    try:
        result = auth.create_user(username, password, role=role)
        audit.record(action=Actions.USER_CREATE, status="ok",
                     user=admin, resource="user", resource_id=username,
                     ip=_client_ip(request), details={"role": role})
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/users/{username}")
def update_user(username: str, body: dict, request: Request,
                admin=Depends(require_admin)):
    """body: { role?, disabled? }"""
    changed = False
    details = {}
    if "role" in body:
        if not auth.update_user_role(username, body["role"]):
            raise HTTPException(404, "사용자를 찾을 수 없음")
        changed = True
        details["new_role"] = body["role"]
    if "disabled" in body:
        if body["disabled"]:
            auth.disable_user(username)
            audit.record(action=Actions.USER_DISABLE, status="ok",
                         user=admin, resource="user", resource_id=username,
                         ip=_client_ip(request))
        else:
            # 활성화
            s = auth._users_store()
            u = s.get(username)
            if u:
                u["disabled"] = False
                s.set(username, u)
            audit.record(action=Actions.USER_ENABLE, status="ok",
                         user=admin, resource="user", resource_id=username,
                         ip=_client_ip(request))
        changed = True
    if not changed:
        raise HTTPException(400, "수정할 필드 없음 (role 또는 disabled)")
    if "role" in body:
        audit.record(action=Actions.USER_UPDATE, status="ok",
                     user=admin, resource="user", resource_id=username,
                     ip=_client_ip(request), details=details)
    return {"ok": True}


@router.post("/users/{username}/reset-password")
def reset_password(username: str, body: dict, request: Request,
                   admin=Depends(require_admin)):
    """body: { new_password }"""
    new_pw = body.get("new_password", "")
    if len(new_pw) < 8:
        raise HTTPException(400, "비밀번호는 8자 이상이어야 합니다")
    if not auth.update_user_password(username, new_pw):
        raise HTTPException(404, "사용자를 찾을 수 없음")
    # 해당 사용자의 세션도 무효화 — 보안상 재로그인 유도
    for token, sess in list(auth._sessions_store().all().items()):
        if sess.get("username") == username:
            auth._sessions_store().delete(token)
    audit.record(action=Actions.PASSWORD_RESET, status="ok",
                 user=admin, resource="user", resource_id=username,
                 ip=_client_ip(request))
    return {"ok": True}


@router.delete("/users/{username}", status_code=204)
def delete_user(username: str, request: Request, admin=Depends(require_admin)):
    # 본인 삭제는 방지 — lockout 예방
    if username == admin.get("username"):
        raise HTTPException(400, "자기 자신은 삭제할 수 없습니다")
    if not auth.delete_user(username):
        raise HTTPException(404, "사용자를 찾을 수 없음")
    audit.record(action=Actions.USER_DELETE, status="ok",
                 user=admin, resource="user", resource_id=username,
                 ip=_client_ip(request))


# ── 상태 조회 ──────────────────────────────────────────

@router.get("/status")
def auth_status():
    """
    RBAC 활성 여부 + 등록된 사용자 수 (비인증도 접근 가능).
    프론트가 로그인 화면 표시 여부 결정할 때 사용.
    """
    from app.core.auth_deps import is_rbac_enabled
    return {
        "rbac_enabled": is_rbac_enabled(),
        "user_count":   len(auth._users_store()),
    }
