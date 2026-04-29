"""
app/core/auth_deps.py
FastAPI 의존성 — 엔드포인트 보호.

사용 예:
    from app.core.auth_deps import require_role

    @router.post("/jobs/")
    def create_job(body: dict, user=Depends(require_role("operator"))):
        ...  # user는 {username, role, ...} 세션 정보

    @router.put("/settings/")
    def update_settings(body: dict, user=Depends(require_role("admin"))):
        ...

인증 없는 엔드포인트는 Depends를 생략 — 기존 코드 그대로 동작.

환경변수로 RBAC 비활성 가능:
    DATABRIDGE_RBAC_ENABLED=false
  → require_role 이 항상 관대한 admin 반환 (개발/POC 초기 편의)
"""
from __future__ import annotations
import os
from fastapi import Request, HTTPException, Header, Depends

from app.core.auth import resolve_session, has_role

# RBAC 비활성 모드 (기본: 활성)
_RBAC_ENABLED = os.environ.get("DATABRIDGE_RBAC_ENABLED", "true").lower() not in ("false", "0", "no")


def _extract_token(request: Request, x_auth_token: str | None) -> str | None:
    """
    토큰을 3가지 경로에서 찾음 (프론트 호환성):
      1. X-Auth-Token 헤더
      2. Authorization: Bearer <token>
      3. 쿼리 파라미터 ?token=...
    """
    if x_auth_token:
        return x_auth_token
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.query_params.get("token")


def current_user(
    request: Request,
    x_auth_token: str | None = Header(default=None, alias="X-Auth-Token"),
) -> dict | None:
    """
    현재 요청의 사용자 세션 반환. 로그인 안 됐으면 None.
    """
    if not _RBAC_ENABLED:
        return {"username": "admin", "role": "admin", "rbac_disabled": True}
    token = _extract_token(request, x_auth_token)
    if not token:
        return None
    return resolve_session(token)


def require_role(required: str):
    """
    데코레이터 용 factory. Depends(require_role("operator")) 식으로 사용.

    401/403 발생 시 app.core.audit 에 "auth.denied" 이벤트 기록.
    감사 기록 실패는 본 흐름 차단하지 않음 (fail-open).
    """
    def dep(request: Request,
            x_auth_token: str | None = Header(default=None, alias="X-Auth-Token")):
        if not _RBAC_ENABLED:
            return {"username": "admin", "role": "admin", "rbac_disabled": True}
        token = _extract_token(request, x_auth_token)
        if not token:
            _audit_deny(request, required, None, reason="no_token")
            raise HTTPException(401, "인증 필요 — 로그인하세요")
        sess = resolve_session(token)
        if not sess:
            _audit_deny(request, required, None, reason="invalid_or_expired")
            raise HTTPException(401, "세션 만료 또는 유효하지 않은 토큰")
        if not has_role(sess.get("role", "guest"), required):
            _audit_deny(request, required, sess, reason="insufficient_role")
            raise HTTPException(
                403,
                f"권한 부족 — 필요: {required}, 현재: {sess.get('role')}",
            )
        return sess
    return dep


def _audit_deny(request: Request, required: str, sess: dict | None, *, reason: str) -> None:
    """
    권한 거부 이벤트를 감사 로그에 기록.
    순환 import 회피를 위해 지연 import 사용.
    """
    try:
        from app.core import audit
        # 메소드와 경로에서 해당 리소스 추정
        path = str(request.url.path) if hasattr(request, "url") else ""
        # /api/v1/<resource>/... 에서 resource 추출
        parts = [p for p in path.split("/") if p and p not in ("api", "v1")]
        resource = parts[0] if parts else "unknown"
        audit.record(
            action="auth.denied",
            status="denied",
            user=sess,  # None이면 anonymous로 기록됨
            resource=resource,
            resource_id=None,
            ip=(request.client.host if request.client else None),
            details={
                "required_role": required,
                "method":        request.method if hasattr(request, "method") else "",
                "path":          path,
                "reason":        reason,
            },
        )
    except Exception:
        pass  # 감사 실패는 무시


# 편의 alias — 자주 쓰는 패턴
require_viewer   = require_role("viewer")
require_operator = require_role("operator")
require_admin    = require_role("admin")


def is_rbac_enabled() -> bool:
    return _RBAC_ENABLED
