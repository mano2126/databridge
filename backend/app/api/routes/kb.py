"""
app/api/routes/kb.py — 에러 KB + 변환 KB (타입/오브젝트 매핑 자동 학습) 관리 API
v10 #18 — 2026-04-21

엔드포인트 (에러 KB):
  GET  /api/v1/kb/patterns        — 에러 패턴 목록
  GET  /api/v1/kb/stats?days=30   — 에러 KB 통계
  GET  /api/v1/kb/unmatched       — 미매칭 에러 샘플
  POST /api/v1/kb/reload          — 에러 YAML 재로드
  POST /api/v1/kb/test-match      — 에러 메시지 테스트

엔드포인트 (변환 KB — v10 #18 신규):
  GET  /api/v1/kb/conversion/overview    — 수동/AI학습/상태별 자산 요약
  GET  /api/v1/kb/conversion/metrics     — 일자별 AI호출 vs 로컬처리 추이
  POST /api/v1/kb/conversion/promote     — 규칙 수동 승격/거부
                                            body: {kind:'type'|'obj', rule_id, status:'active'|'shadow'|'rejected'}
  GET  /api/v1/kb/conversion/coverage    — DDL 로컬 커버리지 미리보기
                                            body: {src_ddl, src_db, tgt_db}
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional

router = APIRouter(prefix="/kb", tags=["kb"])

# 권한 의존성 (기존 방식 재사용)
try:
    from app.api.routes.auth import require_admin, require_operator
except Exception:
    def require_admin(): pass
    def require_operator(): pass


# ══════════════════════════════════════════════════════════
# [1] 에러 KB (기존)
# ══════════════════════════════════════════════════════════
@router.get("/patterns")
def list_patterns(_=Depends(require_operator)):
    """전체 패턴 목록 (관리자 UI 용)"""
    try:
        from app.engine.error_kb import get_all_patterns
        patterns = get_all_patterns()
        out = []
        for pid, entry in patterns.items():
            clean = {k: v for k, v in entry.items() if not k.startswith("_")}
            clean["id"] = pid
            out.append(clean)
        return {"patterns": out, "total": len(out)}
    except Exception as e:
        return {"patterns": [], "total": 0, "error": str(e)}


@router.get("/stats")
def get_kb_stats(
    days: int = Query(30, ge=1, le=365, description="최근 N일"),
    _=Depends(require_operator),
):
    """KB 통계 요약 (관리자 대시보드)"""
    try:
        from app.engine.error_kb import get_stats
        return get_stats(days=days)
    except Exception as e:
        return {"error": str(e)}


@router.get("/unmatched")
def get_unmatched(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=200),
    _=Depends(require_operator),
):
    """매칭되지 않은 에러 샘플 (신규 패턴 후보 발굴용)"""
    try:
        from app.engine.error_kb import get_unmatched_samples
        return {"samples": get_unmatched_samples(days=days, limit=limit)}
    except Exception as e:
        return {"samples": [], "error": str(e)}


@router.post("/reload")
def reload_kb(_=Depends(require_admin)):
    """YAML 파일 수동 재로드"""
    try:
        from app.engine.error_kb import reload_kb
        n = reload_kb()
        return {"ok": True, "patterns_loaded": n}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/test-match")
def test_match(body: dict, _=Depends(require_operator)):
    """에러 메시지를 넣어 어떤 패턴이 매칭되는지 테스트"""
    err = (body or {}).get("error", "")
    try:
        from app.engine.error_kb import match_error, assemble_prompt_hint
        matched = match_error(err)
        prompt_hint = assemble_prompt_hint(current_error=err)
        return {
            "matched": matched,
            "prompt_hint_preview": prompt_hint[:2000] if prompt_hint else "",
            "hint_chars": len(prompt_hint) if prompt_hint else 0,
        }
    except Exception as e:
        return {"matched": None, "error": str(e)}


# ══════════════════════════════════════════════════════════
# [2] 변환 KB — v10 #18 신규
# ══════════════════════════════════════════════════════════
@router.get("/conversion/overview")
def conversion_overview(_=Depends(require_operator)):
    """
    타입/오브젝트 매핑 자산 현황.
    {
      type_mapping:   {total, manual, ai_learned, active, shadow, rejected},
      object_mapping: {...},
    }
    """
    try:
        from app.engine.conversion_learner import get_kb_overview
        return get_kb_overview()
    except Exception as e:
        return {"error": str(e)}


@router.get("/conversion/metrics")
def conversion_metrics(
    days: int = Query(30, ge=1, le=365),
    _=Depends(require_operator),
):
    """
    AI 호출 vs 로컬 처리 일별 추이 + 학습 누적 패턴.
    목표: 시간이 지나면 AI 호출 비율이 감소하는 곡선 확인.
    """
    try:
        from app.engine.conversion_learner import get_metrics
        return get_metrics(days=days)
    except Exception as e:
        return {"error": str(e), "daily": [], "summary": {}}


@router.post("/conversion/promote")
def conversion_promote(body: dict, _=Depends(require_admin)):
    """
    관리자 수동 승격/거부.
    Body: {kind: 'type'|'obj', rule_id: str, status: 'active'|'shadow'|'rejected'}
    """
    try:
        from app.engine.conversion_learner import set_rule_status
        kind     = (body or {}).get("kind", "")
        rule_id  = (body or {}).get("rule_id", "")
        status   = (body or {}).get("status", "")
        if kind not in ("type", "obj"):
            raise HTTPException(400, "kind는 'type' 또는 'obj' 이어야 합니다")
        if not rule_id:
            raise HTTPException(400, "rule_id가 비었습니다")
        ok = set_rule_status(kind, rule_id, status)
        if not ok:
            raise HTTPException(404, "규칙을 찾을 수 없거나 status가 잘못되었습니다")
        return {"ok": True, "kind": kind, "rule_id": rule_id, "status": status}
    except HTTPException:
        raise
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/conversion/coverage")
def conversion_coverage(body: dict, _=Depends(require_operator)):
    """
    DDL 을 넣어 로컬 KB 커버리지 예상 비율 계산 (AI 호출 전 미리보기).
    Body: {src_ddl, src_db, tgt_db}
    """
    try:
        from app.engine.conversion_learner import estimate_local_coverage
        return estimate_local_coverage(
            (body or {}).get("src_ddl", ""),
            (body or {}).get("src_db", ""),
            (body or {}).get("tgt_db", ""),
        )
    except Exception as e:
        return {"error": str(e), "coverage": 0.0}
