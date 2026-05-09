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


# ══════════════════════════════════════════════════════════
# v93_D2 (2026-05-01): KB 후보 자동 등록 + KB 자산 가시화
# 본부장님 통찰: "KB 가 살아있는 자산이어야 함"
# ══════════════════════════════════════════════════════════

@router.post("/register-candidate")
def register_kb_candidate(body: dict, _=Depends(require_operator)):
    """객체 검증/이관에서 발견한 새 오류 케이스를 KB 후보로 등록.
    
    프론트가 1클릭으로 호출 → error_cases.txt 에 케이스 누적.
    Body: {
        item_name: '...',
        obj_type: 'FUNCTION'|'PROCEDURE'|...,
        error_message: '...',
        src_ddl: '...',
        suggested_pattern_id: 'XXX_XXX_XXX' (optional),
        notes: '...' (optional)
    }
    """
    try:
        from datetime import datetime
        from pathlib import Path
        item_name   = (body or {}).get("item_name", "unknown")
        obj_type    = (body or {}).get("obj_type", "")
        error_msg   = (body or {}).get("error_message", "")
        src_ddl     = (body or {}).get("src_ddl", "")
        pattern_id  = (body or {}).get("suggested_pattern_id", "")
        notes       = (body or {}).get("notes", "")
        
        if not error_msg:
            raise HTTPException(400, "error_message 가 필요합니다")
        
        # error_cases.txt 에 누적
        cases_path = Path("backend/prompts/mssql_to_mysql/error_cases.txt")
        if not cases_path.exists():
            cases_path = Path("prompts/mssql_to_mysql/error_cases.txt")
        cases_path.parent.mkdir(parents=True, exist_ok=True)
        
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        block = f"""
# ════════════════════════════════════════════════════════════════
# [{ts}] {item_name} | KB 후보 등록 (v93_D2)
#   타입: {obj_type}
#   추정 패턴 ID: {pattern_id or '(미지정 — 사람 검토 필요)'}
{f"#   메모: {notes}" if notes else ""}
# ════════════════════════════════════════════════════════════════
[KB-CANDIDATE] {item_name} | ({obj_type}) {error_msg[:300]}

소스 DDL:
{src_ddl[:2000] if src_ddl else '(미제공)'}

오류 메시지 (전체):
{error_msg[:1500]}

검토 필요 항목:
  - regex 패턴 작성 (이 메시지에 매칭되도록)
  - fix_prompt 작성 (AI 가 다음에 안 깨지도록)
  - error_kb.yml 에 정식 패턴 추가
  - 변환 예시 (function.txt / procedure.txt) 누적
"""
        with open(cases_path, "a", encoding="utf-8") as f:
            f.write(block)
        
        return {
            "ok": True,
            "registered_at": ts,
            "file": str(cases_path),
            "candidate_id": f"{item_name}_{ts.replace(' ','_').replace(':','-')}",
            "next_steps": [
                "error_cases.txt 에 케이스 누적됨",
                "다음 세션에 본부장님 검토 후 정식 KB 패턴 등록",
                "또는 AI 분석 자동 패턴 추출 (Phase 2)",
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/cases-recent")
def get_recent_cases(
    limit: int = Query(20, ge=1, le=200),
    q: str = Query("", description="검색어 (객체명/에러메시지/소스 DDL 매칭)"),
    obj_type: str = Query("", description="객체 타입 필터 (FUNCTION/PROCEDURE/...)"),
    date_from: str = Query("", description="시작 날짜 YYYY-MM-DD"),
    date_to: str = Query("", description="종료 날짜 YYYY-MM-DD"),
    error_code: str = Query("", description="에러 코드 필터 (1064/1362/...)"),
    group_by: str = Query("", description="그룹화: ''(none) | 'object' | 'date' | 'error_code'"),
    _=Depends(require_operator)
):
    """error_cases.txt 의 케이스 조회 (v94_p3 강화).
    
    - 검색: 객체명/에러메시지/소스 DDL 매칭
    - 필터: 객체 타입, 날짜 범위, 에러 코드
    - 그룹: 객체별/날짜별/에러 코드별 카운트
    """
    try:
        from pathlib import Path
        from datetime import datetime
        cases_path = Path("backend/prompts/mssql_to_mysql/error_cases.txt")
        if not cases_path.exists():
            cases_path = Path("prompts/mssql_to_mysql/error_cases.txt")
        if not cases_path.exists():
            return {"cases": [], "total": 0, "matched": 0, "file": str(cases_path)}
        
        text = cases_path.read_text(encoding="utf-8", errors="replace")
        # 케이스 단위 파싱 — '[YYYY-MM-DD' 시작 패턴
        import re as _re
        cases = []
        lines = text.split("\n")
        current = None
        for ln in lines:
            m = _re.match(r"\[(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2})\]\s*(.*)", ln)
            if m:
                if current:
                    cases.append(current)
                current = {
                    "timestamp": m.group(1),
                    "summary": m.group(2)[:300],
                    "lines": [],
                    # v94_p3: 풍부한 메타 추출
                    "obj_type": "",
                    "obj_name": "",
                    "error_code": "",
                    "first_error_line": "",
                    "src_ddl_preview": "",
                }
            elif current is not None:
                if len(current["lines"]) < 100:  # 케이스당 최대 100줄로 늘림
                    current["lines"].append(ln)
        if current:
            cases.append(current)
        
        # v94_p3: 각 케이스에서 메타 추출
        for c in cases:
            content = "\n".join(c["lines"])
            # 객체 타입
            mt = _re.search(r"타입:\s*(\w+)", content)
            if mt: c["obj_type"] = mt.group(1)
            # 객체명 (summary 의 처음 단어 또는 KB-CANDIDATE 라인에서)
            mc = _re.search(r"\[KB-CANDIDATE\]\s+(\S+)\s*\|", content)
            if mc:
                c["obj_name"] = mc.group(1)
            else:
                # summary 의 처음 단어 추출
                ms = _re.match(r"(\S+)", c["summary"])
                if ms: c["obj_name"] = ms.group(1)
            # 에러 코드 (1064 / 1362 / ...)
            me = _re.search(r"\((\d{3,5}),\s*[\"\']", content)
            if me: c["error_code"] = me.group(1)
            # 첫 에러 라인 (요약용)
            for ln in c["lines"]:
                if "1064" in ln or "1362" in ln or "ERROR" in ln or "Error" in ln:
                    c["first_error_line"] = ln.strip()[:300]
                    break
            # 소스 DDL 미리보기
            ddl_start = False
            ddl_lines = []
            for ln in c["lines"]:
                if "소스 DDL:" in ln or "src_ddl" in ln.lower():
                    ddl_start = True
                    continue
                if ddl_start:
                    if "오류 메시지" in ln or "검토 필요" in ln or ln.strip().startswith("#"):
                        break
                    ddl_lines.append(ln)
                    if len(ddl_lines) >= 8: break
            c["src_ddl_preview"] = "\n".join(ddl_lines).strip()[:500]
        
        # v94_p3: 필터 적용
        filtered = cases
        if q:
            ql = q.lower()
            filtered = [c for c in filtered if 
                ql in c["summary"].lower() or 
                ql in c["obj_name"].lower() or 
                ql in c["first_error_line"].lower() or
                ql in c["src_ddl_preview"].lower()]
        if obj_type:
            filtered = [c for c in filtered if c["obj_type"].upper() == obj_type.upper()]
        if error_code:
            filtered = [c for c in filtered if c["error_code"] == error_code]
        if date_from:
            filtered = [c for c in filtered if c["timestamp"] >= date_from]
        if date_to:
            # YYYY-MM-DD → YYYY-MM-DD 23:59:59 까지
            filtered = [c for c in filtered if c["timestamp"] <= (date_to + " 23:59:59")]
        
        # v94_p3: 그룹화 (count only)
        groups = {}
        if group_by == "object":
            for c in filtered:
                key = c["obj_name"] or "(unknown)"
                groups[key] = groups.get(key, 0) + 1
        elif group_by == "date":
            for c in filtered:
                key = c["timestamp"][:10]  # YYYY-MM-DD 만
                groups[key] = groups.get(key, 0) + 1
        elif group_by == "error_code":
            for c in filtered:
                key = c["error_code"] or "(unknown)"
                groups[key] = groups.get(key, 0) + 1
        
        # 최신순 정렬
        filtered.sort(key=lambda c: c.get("timestamp", ""), reverse=True)
        
        return {
            "cases": filtered[:limit],
            "total": len(cases),         # 전체 케이스 수
            "matched": len(filtered),    # 필터링 후 매칭 수
            "groups": groups,            # 그룹 카운트
            "group_by": group_by,
            "file": str(cases_path),
            "file_size_bytes": cases_path.stat().st_size,
            # v94_p3: 메타 통계
            "all_obj_types": sorted(set(c["obj_type"] for c in cases if c["obj_type"])),
            "all_error_codes": sorted(set(c["error_code"] for c in cases if c["error_code"])),
            "all_dates": sorted(set(c["timestamp"][:10] for c in cases), reverse=True)[:30],
        }
    except Exception as e:
        return {"cases": [], "total": 0, "error": str(e)}


# v94_p3 (2026-05-01): 단일 케이스 상세 조회 (전체 본문)
@router.get("/cases-detail")
def get_case_detail(
    timestamp: str = Query(..., description="조회할 케이스의 timestamp"),
    _=Depends(require_operator)
):
    """타임스탬프로 특정 케이스의 전체 본문 조회 (검토용)."""
    try:
        from pathlib import Path
        cases_path = Path("backend/prompts/mssql_to_mysql/error_cases.txt")
        if not cases_path.exists():
            cases_path = Path("prompts/mssql_to_mysql/error_cases.txt")
        if not cases_path.exists():
            raise HTTPException(404, "error_cases.txt 파일 없음")
        
        text = cases_path.read_text(encoding="utf-8", errors="replace")
        import re as _re
        lines = text.split("\n")
        current = None
        for ln in lines:
            m = _re.match(r"\[(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2})\]\s*(.*)", ln)
            if m:
                if current and current["timestamp"] == timestamp:
                    return {"timestamp": current["timestamp"],
                            "full_content": "\n".join(current["lines"])}
                current = {"timestamp": m.group(1), "lines": [ln]}
            elif current is not None:
                current["lines"].append(ln)
        if current and current["timestamp"] == timestamp:
            return {"timestamp": current["timestamp"],
                    "full_content": "\n".join(current["lines"])}
        raise HTTPException(404, f"timestamp={timestamp} 케이스 없음")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"케이스 상세 조회 실패: {e}")


@router.get("/dashboard")
def get_kb_dashboard(_=Depends(require_operator)):
    """KB 자산 종합 대시보드 — 통계 + 패턴 + 최근 케이스 요약"""
    try:
        from app.engine.error_kb import get_stats, get_all_patterns
        stats = get_stats(days=30)
        patterns = get_all_patterns()
        
        # 패턴 categorize
        by_category = {}
        for pid, entry in patterns.items():
            cat = entry.get("category", "OTHER")
            by_category.setdefault(cat, []).append(pid)
        
        # 최근 통계 패턴 (적중률 높은 순)
        top_patterns = sorted(
            stats.get("by_pattern", []),
            key=lambda p: (p.get("attempts", 0), p.get("rate", 0)),
            reverse=True
        )[:10]
        
        # 미매칭 케이스 (UNMATCHED) 우선 (KB 보강 후보)
        try:
            from app.engine.error_kb import get_unmatched_samples
            unmatched = get_unmatched_samples(limit=10)
        except Exception:
            unmatched = []
        
        return {
            "summary": {
                "total_patterns":  len(patterns),
                "total_attempts":  stats.get("total_attempts", 0),
                "total_success":   stats.get("total_success", 0),
                "overall_rate":    round(stats.get("overall_rate", 0) * 100, 1),
                "ai_attempts":     stats.get("ai_attempts", 0),
                "ai_saved":        stats.get("ai_saved", 0),
                "ai_saved_rate":   round(
                    stats.get("ai_saved", 0) / max(stats.get("total_attempts", 1), 1) * 100, 1
                ),
            },
            "patterns_by_category": {k: len(v) for k, v in by_category.items()},
            "top_patterns": top_patterns,
            "unmatched_recent": unmatched,
        }
    except Exception as e:
        return {"error": str(e)}

