"""
app/api/routes/advisor.py — AI DBA Consultant Wizard 백엔드 엔드포인트
v88 P5 (2026-04-23)

Endpoints:
  POST  /advisor/estimate-cost     — 모드별 예상 비용 산정 (AI 호출 없음)
  POST  /advisor/analyze           — ✅ 4개 Advisor 모두 실제 분석
  POST  /advisor/refine            — [P6+] 특정 권고 AI 재질의
  POST  /advisor/apply-decision    — 권고 결정 기록 (KB 축적은 P6)
  GET   /advisor/health            — 라우터 헬스체크
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

from app.core.advisor import (
    JobSelection,
    AnalysisContext,
    AnalysisMode,
    estimate_analysis_cost,
    get_all_advisors,
)

logger = logging.getLogger("databridge.advisor")
router = APIRouter()


# ══════════════════════════════════════════════════════════════
# 요청/응답 스키마
# ══════════════════════════════════════════════════════════════
class SelectionBody(BaseModel):
    tables: list[str] = Field(default_factory=list)
    procedures: list[str] = Field(default_factory=list)
    functions: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    views: list[str] = Field(default_factory=list)


class EstimateCostBody(BaseModel):
    src_db: str
    tgt_db: str
    selection: SelectionBody


class AnalyzeBody(BaseModel):
    src_db: str
    tgt_db: str
    selection: SelectionBody
    mode: str = "smart"
    user_hints: str = ""
    # v88 hotfix (2026-04-23): 프론트에서 직접 연결 정보 전달
    # schema._conns fallback 에 의존하지 않고, 프론트가 connectorStore 의 정보를 실어 보냄.
    # 비밀번호 포함 — 전송은 이미 HTTPS/내부망 가정 (위저드의 다른 요청과 동일).
    source_conn: Optional[dict] = None
    target_conn: Optional[dict] = None
    # v88 hotfix2 (2026-04-23): 프로파일 ID — 마스킹된 비번 복원용
    # connectorStore.loadedProfileId 가 실어 보내는 값.
    # 있으면 resolve_password() 가 profile DB 에서 실제 암호문 조회해서 복호화.
    profile_id: Optional[str] = None


class DecisionItem(BaseModel):
    id: str
    decision: str
    edited_sql: Optional[str] = None
    # v10 #23: baseline 생성을 위한 권고 메타데이터 (선택 — 있으면 더 정확)
    category:    Optional[str] = None
    severity:    Optional[str] = None
    title:       Optional[str] = None
    description: Optional[str] = None


class ApplyDecisionBody(BaseModel):
    src_db: str
    tgt_db: str
    mode: str = "smart"
    decisions: list[DecisionItem]
    job_id: Optional[str] = None


_VALID_MODES = {"smart", "hybrid", "deep"}


def _to_selection(sel: SelectionBody) -> JobSelection:
    return JobSelection(
        tables=sel.tables or [],
        procedures=sel.procedures or [],
        functions=sel.functions or [],
        triggers=sel.triggers or [],
        views=sel.views or [],
    )


def _summarize(recommendations: list[dict]) -> dict:
    summary = {"total": len(recommendations), "high": 0, "med": 0, "low": 0, "by_category": {}}
    for r in recommendations:
        sev = r.get("severity", "low")
        if sev in ("high", "med", "low"):
            summary[sev] += 1
        cat = r.get("category", "unknown")
        summary["by_category"][cat] = summary["by_category"].get(cat, 0) + 1
    impact_pct = summary["high"] * 8 + summary["med"] * 3 + summary["low"] * 1
    summary["estimated_improvement_pct"] = min(impact_pct, 75)
    return summary


# ══════════════════════════════════════════════════════════════
# 소스 DB 연결 획득 (P5 + hotfix)
# ══════════════════════════════════════════════════════════════
def _get_source_connection(
    src_db: str,
    conn_info_body: Optional[dict] = None,
    profile_id: Optional[str] = None,
):
    """
    Advisor 분석용 소스 DB 연결 획득.

    우선순위:
      1. conn_info_body (프론트에서 body 로 직접 전달) — 2026-04-23 hotfix
      2. schema.py 의 _conns (레거시 /schema/connection 사용 시)

    비밀번호 해결 (v88 hotfix2, 2026-04-23):
      - 프로파일 로드 시 UI 가 마스킹 문자(●●●●●●●●) 를 password 로 보낼 수 있음.
      - resolve_password() 가 마스킹 감지 → profile_id 로 DB 에서 실제 암호문 조회/복호화.
      - 이 처리가 없으면 MSSQL 에 마스킹 문자로 로그인 시도 → "Login failed" 에러.

    실패 시 None 반환 (Advisor 는 메타 없이도 동작).
    """
    try:
        conn_info = conn_info_body or {}

        # body 에 없으면 schema._conns fallback
        if not conn_info or not conn_info.get("host"):
            try:
                from app.api.routes import schema as schema_mod
                conn_info = schema_mod._conns.get("source") or {}
            except Exception:
                pass

        if not conn_info or not conn_info.get("host"):
            logger.info("[advisor] 연결 정보 없음 (body/schema 모두)")
            return None

        host = conn_info.get("host")
        port = int(conn_info.get("port") or 3306)
        user = conn_info.get("username") or conn_info.get("user") or ""
        pw_raw = conn_info.get("password") or ""
        db   = conn_info.get("database") or ""
        src = (src_db or "").lower()

        # v88 hotfix2: 마스킹된 비밀번호 복원
        try:
            from app.core.password_resolver import resolve_password
            pw = resolve_password(
                pw_raw,
                profile_id=profile_id,
                side="source",
                host=host,
                username=user,
                database=db,
            )
            if pw != pw_raw:
                logger.info("[advisor] 비밀번호 복원 성공 (profile_id=%s)", profile_id or "(fallback)")
        except ImportError:
            # password_resolver 가 없으면 (구버전 환경) 그냥 원본 사용
            logger.warning("[advisor] password_resolver 없음 — 원본 비밀번호 사용")
            pw = pw_raw
        except Exception as e:
            logger.warning("[advisor] 비밀번호 복원 실패: %s — 원본 사용", e)
            pw = pw_raw

        if src in ("mysql", "mariadb", "aurora", "tidb", "cloudsql"):
            import pymysql
            return pymysql.connect(
                host=host, port=port, user=user, password=pw, database=db,
                charset="utf8mb4", connect_timeout=10,
            )
        elif src in ("mssql", "azure", "sqlserver"):
            try:
                import pyodbc
                driver = "{ODBC Driver 17 for SQL Server}"
                return pyodbc.connect(
                    f"DRIVER={driver};SERVER={host},{port};DATABASE={db};"
                    f"UID={user};PWD={pw};TrustServerCertificate=yes;",
                    timeout=10,
                )
            except Exception as e:
                logger.warning("MSSQL 연결 실패: %s", e)
                return None
        else:
            logger.info("[advisor] 미지원 src_db=%s", src)
            return None
    except Exception as e:
        logger.warning("[advisor] 소스 연결 획득 실패: %s", e)
        return None


# ══════════════════════════════════════════════════════════════
# 엔드포인트
# ══════════════════════════════════════════════════════════════
@router.get("/health")
def advisor_health():
    advisors = get_all_advisors()
    return {
        "ok": True,
        "phase": "P5",
        "description": "AI DBA Consultant — 4개 Advisor 모두 활성",
        "active_advisors": [a.category for a in advisors],
        "implemented": ["estimate-cost", "analyze", "apply-decision"],
        "pending": ["refine (AI 재질의)", "advisor_learner (KB 축적)"],
    }


@router.post("/estimate-cost")
def estimate_cost(body: EstimateCostBody):
    selection = _to_selection(body.selection)
    estimates: dict[str, Any] = {}
    for mode in ("smart", "hybrid", "deep"):
        try:
            estimates[mode] = estimate_analysis_cost(selection, mode)
        except Exception as e:
            logger.exception("estimate_analysis_cost failed: %s", e)
            estimates[mode] = {
                "mode": mode, "tokens_in": 0, "tokens_out": 0, "tokens_total": 0,
                "time_sec": 0, "cost_usd": 0.0, "cost_krw": 0, "error": str(e),
            }
    return {
        "estimates": estimates,
        "selection_summary": {
            "tables":     len(selection.tables),
            "procedures": len(selection.procedures),
            "functions":  len(selection.functions),
            "triggers":   len(selection.triggers),
            "views":      len(selection.views),
            "total":      selection.total,
        },
    }


@router.post("/analyze")
def analyze(body: AnalyzeBody):
    if body.mode not in _VALID_MODES:
        raise HTTPException(400, f"invalid mode: {body.mode}")

    selection = _to_selection(body.selection)
    src_conn = _get_source_connection(body.src_db, body.source_conn, body.profile_id)

    context = AnalysisContext(
        src_db=body.src_db,
        tgt_db=body.tgt_db,
        mode=body.mode,
        user_hints=body.user_hints,
        src_conn=src_conn,
        tgt_conn=None,
        query_log_available=False,
    )

    recommendations: list[dict] = []
    advisor_status: dict[str, str] = {}
    # v88 hotfix3 (2026-04-23): 진단 정보 수집
    diagnostics: dict[str, dict] = {}

    try:
        for advisor in get_all_advisors():
            cat = advisor.category
            try:
                if not advisor.supports(body.src_db, body.tgt_db):
                    advisor_status[cat] = "unsupported"
                    continue
                recs = advisor.analyze(selection, context)
                recommendations.extend([r.to_dict() for r in recs])
                advisor_status[cat] = "ok"
                logger.info("[advisor.analyze/P5] %s: %d recs", cat, len(recs))
            except Exception as e:
                logger.exception("[advisor.analyze/P5] %s failed: %s", cat, e)
                advisor_status[cat] = f"error: {type(e).__name__}"
    finally:
        # v88 hotfix3: context 에 기록된 DDL 조회 진단 정보 수집
        try:
            ddl_diag = getattr(context, "_ddl_fetch_diagnostics", None)
            if ddl_diag:
                diagnostics["object_ddl_fetch"] = ddl_diag
        except Exception:
            pass

        if src_conn is not None:
            try: src_conn.close()
            except Exception: pass

    summary = _summarize(recommendations)

    notice_msg = ""
    if summary["total"] == 0:
        if src_conn is None:
            notice_msg = (
                "권고가 생성되지 않았습니다. 소스 DB 연결이 확인되지 않아 상세 분석이 제한되었습니다. "
                "DB 선택 단계에서 연결 테스트를 완료하면 더 정확한 권고를 받을 수 있습니다."
            )
        else:
            notice_msg = "선택된 대상은 추가 최적화 권고가 없습니다 — 이미 좋은 구성입니다."
    elif src_conn is None:
        notice_msg = "소스 DB 연결 없이 일반 권고만 생성되었습니다. 정밀 분석을 위해 연결 테스트 권장."

    return {
        "phase": "P5",
        "mode": body.mode,
        "recommendations": recommendations,
        "summary": summary,
        "advisor_status": advisor_status,
        "src_conn_used": src_conn is not None,
        "notice": notice_msg,
        "diagnostics": diagnostics,   # v88 hotfix3: DDL 조회 상태 등
    }


@router.post("/apply-decision")
def apply_decision(body: ApplyDecisionBody):
    stats = {"applied": 0, "skipped": 0, "edited": 0, "invalid": 0}
    for d in body.decisions:
        if d.decision in ("applied", "skipped", "edited"):
            stats[d.decision] += 1
        else:
            stats["invalid"] += 1

    logger.info(
        "[advisor.apply-decision/P5] src=%s tgt=%s mode=%s job=%s stats=%s",
        body.src_db, body.tgt_db, body.mode, body.job_id, stats,
    )

    # v10 #23: Tracking Store 에 baseline 과 함께 기록
    # → 리포트에서 Before/After 비교 가능
    tracking_result = {"recorded": 0}
    try:
        from app.core.advisor_tracking import record_decisions

        # DecisionItem → dict 변환 + 권고 메타 그대로 전달
        decision_dicts = [d.dict() for d in body.decisions]
        # 각 권고의 메타데이터는 DecisionItem 자체에 있음 (category/severity/title/description)
        recommendations_by_id = {
            d.id: {
                "category":    d.category,
                "severity":    d.severity,
                "title":       d.title,
                "description": d.description,
            }
            for d in body.decisions
            if d.category or d.severity or d.title  # 메타 있는 것만
        }

        tracking_result = record_decisions(
            job_id=body.job_id or "",
            src_db=body.src_db,
            tgt_db=body.tgt_db,
            mode=body.mode,
            decisions=decision_dicts,
            recommendations_by_id=recommendations_by_id,
        )
        logger.info(
            "[advisor.apply-decision/v10#23] tracking 저장: %s",
            tracking_result,
        )
    except Exception as e:
        # tracking 실패해도 apply_decision 은 성공 반환 (하위 호환)
        logger.warning("[advisor.apply-decision/v10#23] tracking 저장 실패: %s", e)

    return {
        "ok": True,
        "phase": "P5",
        "stats": stats,
        "total_decisions": len(body.decisions),
        "tracking": tracking_result,    # v10 #23
        "note": "KB 축적은 P6 advisor_learner 에서 구현됩니다.",
    }


@router.post("/refine")
def refine(_body: dict = Body(...)):
    raise HTTPException(
        status_code=503,
        detail="refine endpoint is not yet implemented (planned: P6+)",
    )
