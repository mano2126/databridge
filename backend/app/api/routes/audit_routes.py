"""
app/api/routes/audit_routes.py
감사 로그 조회 REST API — admin 전용.

GET /audit/logs       — 필터 + 페이지네이션 조회
GET /audit/stats      — 요약 통계
GET /audit/actions    — 알려진 action 목록 (필터 드롭다운용)
DELETE /audit/purge   — 보관 정책 (N일 이전 삭제)
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Optional

from app.core import audit
from app.core.audit import Actions
from app.core.auth_deps import require_admin

router = APIRouter()


@router.get("/logs")
def list_logs(
    username: Optional[str] = Query(None, description="사용자명 필터"),
    action: Optional[str] = Query(None, description="정확한 action 일치"),
    action_prefix: Optional[str] = Query(None, description="action prefix (예: 'auth.', 'job.')"),
    resource: Optional[str] = Query(None, description="리소스 타입 (job/user/settings/profile)"),
    status: Optional[str] = Query(None, pattern="^(ok|fail|denied)$"),
    since_epoch: Optional[int] = Query(None, description="UNIX 시각 이후"),
    until_epoch: Optional[int] = Query(None, description="UNIX 시각 이전"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    admin=Depends(require_admin),
):
    """감사 로그 목록 조회"""
    return audit.query(
        username=username, action=action, action_prefix=action_prefix,
        resource=resource, status=status,
        since_epoch=since_epoch, until_epoch=until_epoch,
        limit=limit, offset=offset,
    )


@router.get("/stats")
def get_stats(
    since_epoch: Optional[int] = Query(None),
    admin=Depends(require_admin),
):
    """감사 이벤트 요약 통계 — 대시보드용"""
    return audit.stats(since_epoch=since_epoch)


@router.get("/actions")
def list_known_actions(admin=Depends(require_admin)):
    """정의된 action 상수 목록 — 프론트 필터 드롭다운용"""
    # Actions 클래스에서 public 속성만 추출
    return [
        getattr(Actions, k) for k in dir(Actions)
        if not k.startswith("_") and isinstance(getattr(Actions, k), str)
    ]


@router.delete("/purge")
def purge_old_logs(
    request: Request,
    days: int = Query(..., ge=1, le=3650, description="N일 이전 레코드 삭제"),
    admin=Depends(require_admin),
):
    """보관 정책 — N일 이전 감사 로그 일괄 삭제. 삭제 자체도 감사에 기록됨."""
    removed = audit.purge_older_than(days)
    # 자기 자신도 감사 대상
    audit.record(
        action="audit.purge", status="ok",
        user=admin, resource="audit", resource_id=None,
        ip=(request.client.host if request.client else None),
        details={"days": days, "removed": removed},
    )
    return {"ok": True, "removed": removed, "days": days}


@router.get("/verify")
def verify_audit_integrity(_admin=Depends(require_admin)):
    """
    v10 #21 — 감사 로그 해시 체인 무결성 검증.
    금융권 정기 감사 대응용. 체인이 깨진 지점이 있으면 broken_at/broken_reason 반환.
    """
    return audit.verify_integrity()
