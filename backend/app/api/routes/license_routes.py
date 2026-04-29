"""
app/api/routes/license_routes.py
라이선스 상태 조회 + 교체 엔드포인트.

GET  /license         — 현재 라이선스 상태 (모든 사용자 — 자기가 쓰는 edition 알 필요 있음)
POST /license/reload  — 라이선스 파일 재로드 (admin)
POST /license/upload  — 새 라이선스 파일 업로드 (admin)
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from pathlib import Path

from app.core import license as lic_mod
from app.core.auth_deps import require_admin, current_user
from app.core import audit as _audit

router = APIRouter()


@router.get("/")
def get_license_info(user=Depends(current_user)):
    """
    현재 라이선스 상태.
    인증된 사용자라면 누구나 조회 가능 (자기가 어떤 edition 쓰는지 알아야 하므로).
    """
    lic = lic_mod.get_license()
    d = lic.to_dict()
    # source_path 등 내부 정보는 admin 에게만
    if not user or user.get("role") != "admin":
        d.pop("source_path", None)
    return d


@router.post("/reload")
def reload_license_endpoint(request: Request, admin=Depends(require_admin)):
    """admin이 라이선스 파일을 수정한 뒤 서버 재기동 없이 반영."""
    lic = lic_mod.reload_license()
    _audit.record(
        action="license.reload", status="ok",
        user=admin, resource="license",
        resource_id=lic.license_id,
        ip=(request.client.host if request.client else None),
        details={"edition": lic.edition, "customer": lic.customer},
    )
    return lic.to_dict()


@router.post("/upload")
async def upload_license(request: Request, admin=Depends(require_admin)):
    """
    새 라이선스 파일 업로드.
    body는 JSON 문자열 또는 raw JSON.
    """
    try:
        body = await request.body()
        text = body.decode("utf-8")
        # JSON 유효성 검사
        import json
        parsed = json.loads(text)
        if "payload" not in parsed or "signature" not in parsed:
            raise HTTPException(400, "잘못된 라이선스 형식 (payload/signature 필수)")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"JSON 파싱 실패: {e}")

    # 라이선스 저장 경로 결정
    import os
    target = os.environ.get("DATABRIDGE_LICENSE_PATH", "").strip()
    if target:
        target_path = Path(target)
    else:
        # 기본: backend/data/license.key
        target_path = Path(__file__).resolve().parents[2] / "data" / "license.key"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(text, encoding="utf-8")

    # 즉시 재로드 검증
    lic = lic_mod.reload_license()

    _audit.record(
        action="license.upload", status="ok" if lic.valid else "fail",
        user=admin, resource="license",
        resource_id=lic.license_id or None,
        ip=(request.client.host if request.client else None),
        details={"edition": lic.edition, "customer": lic.customer,
                 "path": str(target_path)},
    )

    if not lic.valid or lic.edition == "community":
        raise HTTPException(400,
            f"라이선스 검증 실패 — community 모드로 폴백됨. "
            f"(warning: {lic.warning})")

    return lic.to_dict()
