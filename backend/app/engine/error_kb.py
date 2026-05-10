"""
DataBridge 에러 프롬프트 지식 베이스 (KB)
============================================
에러 메시지 → 패턴 분류 → AI 프롬프트 지침 주입
성공/실패 피드백을 SQLite 에 누적하여 효과 측정

공개 API:
    from app.engine.error_kb import (
        match_error,          # 에러 메시지 → 매칭된 KB 엔트리 (또는 None)
        assemble_prompt_hint, # Job 의 error_history + KB 엔트리 → 프롬프트용 문자열
        record_attempt,       # 시도 결과 기록 (통계 누적)
        get_stats,            # 전체/패턴별 통계 조회
    )
"""
from __future__ import annotations

import os
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Iterable

try:
    import yaml  # PyYAML
except ImportError:
    yaml = None

# ─────────────────────────────────────────────────────
# 경로
# ─────────────────────────────────────────────────────
_THIS_DIR  = Path(__file__).parent
_KB_PATH   = _THIS_DIR / "error_kb.yml"
_STATS_DB  = Path(os.environ.get(
    "DATABRIDGE_KB_STATS_DB",
    str(_THIS_DIR.parent.parent / "data" / "kb_stats.db")
))

# ─────────────────────────────────────────────────────
# KB 로딩 (프로세스 1회, 필요 시 reload_kb() 로 재로드)
# ─────────────────────────────────────────────────────
_kb_cache: dict = {}       # { pattern_id: entry }
_kb_lock = threading.Lock()
_kb_mtime: float = 0

def _load_kb() -> dict:
    """YAML 파일에서 KB 로드. 파일 수정 시간 변경되면 자동 재로드."""
    global _kb_cache, _kb_mtime
    if not _KB_PATH.exists():
        return {}
    if yaml is None:
        # PyYAML 없으면 KB 비활성화 (기존 동작 유지)
        return {}
    try:
        mtime = _KB_PATH.stat().st_mtime
        if mtime == _kb_mtime and _kb_cache:
            return _kb_cache
        with _KB_PATH.open("r", encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        patterns = (doc.get("patterns") or {})
        # 정규식 미리 컴파일
        out = {}
        for pid, entry in patterns.items():
            if not isinstance(entry, dict):
                continue
            regex = entry.get("regex")
            try:
                entry["_re"] = re.compile(regex, re.IGNORECASE | re.DOTALL) if regex else None
            except re.error:
                entry["_re"] = None
            out[pid] = entry
        with _kb_lock:
            _kb_cache = out
            _kb_mtime = mtime
        return out
    except Exception:
        return _kb_cache or {}

def reload_kb() -> int:
    """수동 재로드. 반환: 로드된 패턴 개수"""
    global _kb_mtime
    _kb_mtime = 0
    return len(_load_kb())

def get_all_patterns() -> dict:
    """모든 패턴 반환 (관리자 UI 용)"""
    return _load_kb()

# ─────────────────────────────────────────────────────
# 패턴 매칭
# ─────────────────────────────────────────────────────
def match_error(error_message: str) -> Optional[dict]:
    """
    에러 메시지를 받아 매칭된 KB 엔트리 반환.
    매칭 없으면 None.
    반환 dict 예:
        {
            "id": "1064_UPDATE_SET_COMMA",
            "error_code": "1064",
            "category": "SYNTAX",
            "cause": "...",
            "fix_type": "prompt_injection",
            "ai_skip": False,          # 있으면 True
            "fix_prompt": "...",        # fix_type == prompt_injection 인 경우
            "fix_config": {...},        # fix_type == config_change 인 경우
            "fix_engine_rule": "...",   # fix_type == engine_rule 인 경우
        }
    """
    if not error_message:
        return None
    patterns = _load_kb()
    for pid, entry in patterns.items():
        rx = entry.get("_re")
        if rx and rx.search(error_message):
            out = dict(entry)
            out["id"] = pid
            out.pop("_re", None)
            return out
    return None

def match_all_errors(errors: Iterable[str]) -> list:
    """여러 에러를 받아 각각 매칭. 중복 패턴은 한 번만."""
    seen = set()
    result = []
    for err in errors:
        ent = match_error(err or "")
        if ent and ent["id"] not in seen:
            seen.add(ent["id"])
            result.append(ent)
    return result

# ─────────────────────────────────────────────────────
# 프롬프트 조립
# ─────────────────────────────────────────────────────
def assemble_prompt_hint(
    current_error: str = "",
    error_history: Optional[list] = None,
) -> str:
    """
    AI 프롬프트에 주입할 '지침 섹션' 생성.
    - current_error 에서 패턴 매칭 → 해당 교정 지침
    - error_history 에 있는 각 시도의 에러도 매칭 → 여러 지침 모두 포함 (중복 제거)
    - Job 내 이전 시도 에러를 자연스럽게 요약

    반환: 프롬프트에 바로 붙일 수 있는 문자열. 매칭이 없으면 빈 문자열.
    """
    error_history = error_history or []

    # 1. 모든 관련 에러 수집
    all_errs = []
    if current_error:
        all_errs.append(current_error)
    for h in error_history:
        if isinstance(h, dict):
            err = h.get("error") or ""
        else:
            err = str(h)
        if err:
            all_errs.append(err)

    # 2. 매칭된 KB 엔트리 수집 (중복 제거)
    matched = match_all_errors(all_errs)

    # 3. 프롬프트 섹션 조립
    sections = []

    # KB 기반 지침
    if matched:
        sections.append("")
        sections.append("=" * 60)
        sections.append("[중요] 다음 패턴이 감지되었습니다. 반드시 주의하세요:")
        sections.append("=" * 60)
        for m in matched:
            # prompt_injection 타입만 AI 프롬프트에 반영
            if m.get("fix_type") == "prompt_injection" and m.get("fix_prompt"):
                sections.append("")
                sections.append(f"▶ 패턴: {m['id']} ({m.get('category','')})")
                sections.append(f"  원인: {m.get('cause','')}")
                sections.append(m["fix_prompt"].strip())

    # Job 내 이전 시도 에러 요약
    if error_history:
        sections.append("")
        sections.append("=" * 60)
        sections.append(f"[이전 시도 기록] 이번 항목은 {len(error_history)}회 시도 후 실패했습니다.")
        sections.append("=" * 60)
        sections.append("아래 에러들을 동일하게 발생시키지 마세요:")
        for i, h in enumerate(error_history, 1):
            if isinstance(h, dict):
                attempt = h.get("attempt", i)
                err = h.get("error", "")
            else:
                attempt = i
                err = str(h)
            # 에러 메시지 300자 제한
            err_short = err[:300] + ("..." if len(err) > 300 else "")
            sections.append(f"  [시도 {attempt}] {err_short}")

    return "\n".join(sections).strip()


# ════════════════════════════════════════════════════════════════════
# v94_p4 (2026-05-01): KB 사전 학습 적용 (Pre-Apply Mode)
#
# 본부장님 호소: "매번 똑같은 4개 객체에서 1차에 같은 에러 발생 — KB 학습이 안 되는가?"
#
# 진단 (정직): 기존 KB 는 *에러 발생 후* 그 에러 메시지로 매칭하는 사후 처방 모드.
#   → 깨끗한 1차 변환에는 누적 자산이 적용되지 않음
#
# 처방: 객체 타입 + DDL 시그니처 기반으로 error_cases.txt 검색 →
#       과거 같은 패턴에서 발생했던 에러의 fix_prompt 를 1차 prompt 에 사전 주입
# ════════════════════════════════════════════════════════════════════
def assemble_preflight_hint(
    obj_type: str = "",
    src_ddl: str = "",
    max_hints: int = 5,
    obj_name: str = "",
) -> str:
    """객체 타입 + DDL 패턴 분석 → 과거 KB 자산에서 관련된 fix_prompt 사전 추출.

    동작:
      1. obj_type (FUNCTION/PROCEDURE/TRIGGER/...) 으로 1차 필터
      2. src_ddl 의 위험 키워드 시그니처 추출 (TVF/AFTER UPDATE/WHILE+EXISTS/...)
      3. error_cases.txt 검색 — 같은 시그니처 케이스의 fix_prompt 들 수집
      4. 추출된 fix_prompt 들을 정리해서 prompt 추가 섹션 반환
      5. yml 의 정식 KB 패턴 중 obj_type 매칭되는 것도 포함

    v95_p107 hotfix_007 (2026-05-09 본부장님 본질 처방):
      obj_name 파라미터 추가 — RAG 의 핵심.
      "이전에 같은 객체가 어떻게 실패했는지" 가 다음 시도 프롬프트에 우선 주입되어
      본부장님 시나리오 (이관→실패→AI재이관성공→다시이관해도성공) 를 가능하게 함.
    """
    if not obj_type and not src_ddl:
        return ""

    obj_type_upper = (obj_type or "").upper()
    ddl_lower = (src_ddl or "").lower()

    # ─── Step 1: DDL 시그니처 추출 (위험 패턴 검출) ─────────
    signatures = _extract_ddl_signatures(obj_type_upper, ddl_lower)
    if not signatures:
        return ""  # 위험 패턴 없으면 사전 적용 불필요

    # ─── Step 2: error_cases.txt 검색 ─────────────────────
    # v95_p107 hotfix_007: obj_name 전달 — 같은 객체 과거 사례 우선 추출
    relevant_cases = _search_relevant_cases(
        obj_type_upper, signatures, limit=max_hints, obj_name=obj_name,
    )

    # ─── Step 3: yml 정식 패턴에서 obj_type 매칭되는 것도 포함 ─
    yml_patterns = _get_patterns_for_obj_type(obj_type_upper, signatures)

    if not relevant_cases and not yml_patterns:
        return ""

    # ─── Step 4: prompt 섹션 조립 ──────────────────────────
    sections = []
    sections.append("")
    sections.append("=" * 60)
    sections.append(f"[KB 사전 학습] 과거 같은 {obj_type_upper} 패턴에서 다음 에러가 발생했습니다.")
    sections.append("이번 변환 시 미리 회피하세요:")
    sections.append("=" * 60)

    # 시그니처 매칭 정보
    if signatures:
        sections.append(f"  감지된 위험 패턴: {', '.join(signatures)}")
        sections.append("")

    # yml 정식 패턴 (가중치 높음 — 검증된 처방)
    for p in yml_patterns:
        sections.append(f"▶ [정식 KB] {p['id']} (적중률 {p.get('hit_rate_pct', 0)}%)")
        if p.get("fix_prompt"):
            sections.append(p["fix_prompt"].strip())
        sections.append("")

    # ─── v95_p107 hotfix_007: obj_name 정확 매칭 케이스 우선 표시 ─
    # RAG 핵심 — "이전에 이 객체가 어떻게 실패했는가" 가 AI 의 1차 시도에 들어감
    exact_cases = [c for c in relevant_cases if c.get("is_exact_match")]
    other_cases = [c for c in relevant_cases if not c.get("is_exact_match")]

    if exact_cases and obj_name:
        sections.append("")
        sections.append("★ [최우선] 같은 객체 `{}` 의 과거 실패 사례 ★".format(obj_name))
        sections.append("이 사례에서 발생한 에러를 반드시 회피하세요:")
        sections.append("")
        for c in exact_cases:
            sections.append(f"  ▶ {c['timestamp']}")
            if c.get("error_summary"):
                sections.append(f"    발생했던 에러: {c['error_summary']}")
            if c.get("learned_fix"):
                sections.append(f"    학습된 처방: {c['learned_fix']}")
            sections.append("")

    # error_cases.txt 의 과거 케이스 (가중치 낮음 — 사후 누적)
    for c in other_cases:
        sections.append(f"▶ [과거 케이스] {c['timestamp']} {c['obj_name']}")
        if c.get("error_summary"):
            sections.append(f"  발생했던 에러: {c['error_summary']}")
        if c.get("learned_fix"):
            sections.append(f"  학습된 처방: {c['learned_fix']}")
        sections.append("")

    sections.append("=" * 60)
    sections.append("[중요] 위 패턴들을 1차 변환부터 적용하세요. 같은 에러 반복 회피.")
    sections.append("=" * 60)

    return "\n".join(sections).strip()


def _extract_ddl_signatures(obj_type: str, ddl_lower: str) -> list:
    """DDL 에서 위험 시그니처 추출 (과거 에러 패턴과 매칭용).

    각 시그니처는 짧은 키워드 (TVF, AFTER_UPDATE, WHILE_EXISTS 등).
    """
    sigs = []

    # FUNCTION 관련
    if obj_type in ("FUNCTION", "FUNC", "FN"):
        if "returns table" in ddl_lower or "returns @" in ddl_lower:
            sigs.append("TVF")
        if "while " in ddl_lower and "exists" in ddl_lower:
            sigs.append("WHILE_EXISTS")
        if "while " in ddl_lower and ("select" in ddl_lower):
            sigs.append("WHILE_SUBQUERY")
        # v94_p5: 본부장님 호소 처방 — LEAVE/ITERATE 패턴 → 세미콜론 누락 위험
        if "while " in ddl_lower or "loop" in ddl_lower:
            sigs.append("LEAVE_LOOP")  # 1064_LEAVE_MISSING_SEMI 매칭

    # TRIGGER 관련
    if obj_type in ("TRIGGER", "TRIG", "TR"):
        if "after update" in ddl_lower and ("set new" in ddl_lower or "new." in ddl_lower):
            sigs.append("AFTER_UPDATE_NEW")  # MySQL 1362 에러 발생 패턴
        if "inserted" in ddl_lower or "deleted" in ddl_lower:
            sigs.append("INSERTED_DELETED")  # MSSQL 의 INSERTED/DELETED 가상 테이블

    # PROCEDURE 관련
    if obj_type in ("PROCEDURE", "PROC", "SP"):
        # DECLARE 문에 SELECT 서브쿼리 (MySQL 미지원)
        if "declare" in ddl_lower and ("select" in ddl_lower):
            # DECLARE @var = (SELECT ...) 패턴
            import re as _re
            if _re.search(r"declare\s+\@\w+.*=\s*\(?\s*select", ddl_lower, _re.DOTALL):
                sigs.append("DECLARE_SUBQUERY")
        if "set nocount on" in ddl_lower:
            sigs.append("SET_NOCOUNT")

    # v94_p5: 모든 객체 타입 공통 — 변환 후 DELIMITER 추가 위험 (본부장님 호소)
    # MSSQL 소스에 BEGIN ... END 가 있으면 AI 가 MySQL 변환 시 DELIMITER 추가하기 쉬움
    if "begin" in ddl_lower and "end" in ddl_lower:
        sigs.append("DELIMITER_RISK")  # 1064_DELIMITER_NOT_SUPPORTED 매칭

    # 공통
    if "datetime2" in ddl_lower or "datetimeoffset" in ddl_lower:
        sigs.append("DATETIME2")
    if "sysdatetime" in ddl_lower:
        sigs.append("SYSDATETIME")
    if "@@identity" in ddl_lower or "scope_identity" in ddl_lower:
        sigs.append("IDENTITY_FN")
    if " top " in ddl_lower and " from " in ddl_lower:
        sigs.append("TOP_CLAUSE")

    return sigs


def _search_relevant_cases(obj_type: str, signatures: list, limit: int = 5,
                            obj_name: str = "") -> list:
    """error_cases.txt 에서 obj_type + 시그니처 매칭되는 케이스 추출.

    파일이 없거나 비어있으면 빈 리스트.

    v95_p107 hotfix_007 (2026-05-09 본부장님 본질 처방):
      obj_name 파라미터 추가 — RAG 핵심.
      우선순위:
        1) obj_name 정확 매칭 (지난번 이 객체 실패 사례) → 가중치 +10
        2) obj_name prefix 매칭 (idu_, iu_ 등 i/d/u 통합 트리거 패턴) → +3
        3) 시그니처 매칭 → +1
        4) 최근 (2026-04 이후) → +1
      1순위가 있으면 무조건 결과에 포함 (limit 무시).
    """
    try:
        from pathlib import Path
        # ─── v95_p107 hotfix_008: 경로 후보 확대 ───────────
        # 본부장님 환경: ~/project/databridge_full/backend/prompts/...
        # cwd 가 어디든 동작하도록 절대 경로 후보 추가
        cases_path = Path("backend/prompts/mssql_to_mysql/error_cases.txt")
        if not cases_path.exists():
            cases_path = Path("prompts/mssql_to_mysql/error_cases.txt")
        if not cases_path.exists():
            # 이 파일 위치 기준으로 추적 (engine/error_kb.py → ../../prompts/...)
            here = Path(__file__).resolve().parent
            cases_path = here.parent.parent / "prompts" / "mssql_to_mysql" / "error_cases.txt"
        if not cases_path.exists():
            return []

        text = cases_path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            return []

        # ─── v95_p107 hotfix_008: 라인 단위 파싱 ──────────
        # 본부장님 환경 실제 형식 (1962 라인 기준):
        #   [YYYY-MM-DD] obj_name | (error_code) error_msg...
        # 호환: [YYYY-MM-DD HH:MM:SS] 형식도 인식 (구버전)
        import re as _re
        cases = []
        # 한 줄에 한 케이스 — 핵심 정보 모두 추출
        line_pat_v1 = _re.compile(
            r"^\[(\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}:\d{2})?)\]\s+"
            r"(\S+)\s*\|\s*"
            r"\(([^)]+)\)\s*"
            r"(.*)$"
        )
        for raw_ln in text.split("\n"):
            ln = raw_ln.rstrip("\r")
            m = line_pat_v1.match(ln)
            if m:
                cases.append({
                    "timestamp": m.group(1),
                    "obj_name_raw": m.group(2),
                    "error_code": m.group(3).strip(),
                    "error_msg": m.group(4).strip(),
                    # 호환성을 위해 기존 필드도 채움
                    "summary": f"{m.group(2)} | ({m.group(3)}) {m.group(4)}",
                    "lines": [ln],
                })

        # ─── v95_p107 hotfix_007: obj_name prefix 추출 ─────
        # idu_/iu_/du_ 같은 통합 트리거 prefix 도 매칭하기 위함
        obj_name_lower = (obj_name or "").lower()
        obj_name_prefix = ""
        if obj_name_lower:
            _pm = _re.match(r"^(idu|iud|iu|du|ui|ud|udi|uid|di|id|usp|sp_|p_|ufn|fn_|f_|v_|vw_)",
                            obj_name_lower)
            if _pm:
                obj_name_prefix = _pm.group(1)

        # obj_type 필터 + 시그니처 매칭 점수
        scored = []
        for c in cases:
            content = "\n".join(c["lines"]).lower()
            summary_lower = (c.get("summary") or "").lower()
            c_obj_name_raw = (c.get("obj_name_raw") or "").lower()
            # ─── v95_p107 hotfix_008: obj_type 추론 ──────────
            # 본부장님 환경 라인엔 "타입:" 명시 없음 → 객체명 prefix 로 추론
            ot_match = _re.search(r"타입:\s*(\w+)", content)
            if ot_match:
                c_obj_type = ot_match.group(1).upper()
            else:
                # prefix 기반 추론
                _otp = _re.match(
                    r"^(usp|sp_|p_|proc_|ufn|fn_|f_|udf_|tvf_|"
                    r"v_|vw_|view_|"
                    r"idu|iud|iu|du|ui|ud|tr_|trg_)",
                    c_obj_name_raw
                )
                if _otp:
                    p = _otp.group(1)
                    if p in ("usp", "sp_", "p_", "proc_"):
                        c_obj_type = "PROCEDURE"
                    elif p in ("ufn", "fn_", "f_", "udf_", "tvf_"):
                        c_obj_type = "FUNCTION"
                    elif p in ("v_", "vw_", "view_"):
                        c_obj_type = "VIEW"
                    elif p in ("idu", "iud", "iu", "du", "ui", "ud", "tr_", "trg_"):
                        c_obj_type = "TRIGGER"
                    else:
                        c_obj_type = ""
                else:
                    c_obj_type = ""

            if obj_type and c_obj_type and obj_type != c_obj_type:
                # PROCEDURE != FUNCTION 같은 타입 다른 경우 제외
                # 단 FUNC/FN/FUNCTION 같은 별칭은 같다고 봐야 함 (위에서 통일했음)
                continue

            # ─── v95_p107 hotfix_007/008: 점수 계산 ──────────
            score = 0
            # [1순위] obj_name 정확 매칭 — RAG 핵심
            is_exact_match = False
            if obj_name_lower:
                # 정확 일치 우선
                if c_obj_name_raw and c_obj_name_raw == obj_name_lower:
                    score += 20
                    is_exact_match = True
                elif obj_name_lower in summary_lower or obj_name_lower in content:
                    score += 10
                    is_exact_match = True
            # [2순위] obj_name prefix 매칭
            if obj_name_prefix and c_obj_name_raw.startswith(obj_name_prefix):
                score += 3
            # [3순위] 시그니처 매칭
            for sig in signatures:
                if sig.lower() in content or sig.lower().replace("_", " ") in content:
                    score += 1
            # [4순위] 최근일수록 가중치
            if c["timestamp"] >= "2026-04":
                score += 1

            if score > 0:
                # 객체명 + 에러 요약 + 학습 fix 추출
                # v95_p107 hotfix_008: 새 형식이면 obj_name_raw 우선
                this_obj_name = c.get("obj_name_raw") or ""
                if not this_obj_name:
                    onm = _re.search(r"\[KB-CANDIDATE\]\s+(\S+)\s*\|", "\n".join(c["lines"]))
                    if onm:
                        this_obj_name = onm.group(1)
                    else:
                        sm = _re.match(r"(\S+)", c["summary"])
                        if sm: this_obj_name = sm.group(1)

                # 첫 에러 라인 — 새 형식이면 error_msg 직접 사용
                error_summary = c.get("error_msg") or ""
                if not error_summary:
                    for ln in c["lines"]:
                        if "1064" in ln or "1362" in ln or "1363" in ln or "Error" in ln:
                            error_summary = ln.strip()[:200]
                            break
                error_summary = error_summary[:200]

                # 학습된 처방 (AI 변환 완료 라인 — 있다면)
                learned_fix = ""
                for ln in c["lines"]:
                    if "AI 변환 완료" in ln or "변환 완료" in ln:
                        learned_fix = ln.split("변환 완료", 1)[-1].strip(" —")[:300]
                        break

                scored.append({
                    "timestamp": c["timestamp"],
                    "obj_name": this_obj_name,
                    "obj_type": c_obj_type,
                    "score": score,
                    "error_summary": error_summary,
                    "learned_fix": learned_fix,
                    "is_exact_match": is_exact_match,
                })

        # ─── v95_p107 hotfix_007: obj_name 정확 매칭 우선 ─────
        # 1순위: 같은 obj_name 의 과거 케이스 (RAG 핵심) — 모두 포함
        # 2순위: 점수순 정렬, 최신순 보조
        exact_hits = [s for s in scored if s.get("is_exact_match")]
        other_hits = [s for s in scored if not s.get("is_exact_match")]
        # 정확 매칭은 시간 역순 (최신 실패 우선)
        exact_hits.sort(key=lambda x: x["timestamp"], reverse=True)
        # 기타는 점수순 + 최신순
        other_hits.sort(key=lambda x: (-x["score"], x["timestamp"]), reverse=False)
        other_hits.sort(key=lambda x: x["score"], reverse=True)

        # 정확 매칭 최대 3건 + 기타로 limit 채움
        result = exact_hits[:3]
        remaining = max(0, limit - len(result))
        result.extend(other_hits[:remaining])
        return result
    except Exception as e:
        # 사전 학습 실패는 조용히 무시 (1차 시도는 KB 없이도 가능)
        try:
            import logging
            logging.getLogger("databridge.kb").warning(
                "[KB Pre-Apply] _search_relevant_cases 실패: %s", e)
        except Exception:
            pass
        return []


def _get_patterns_for_obj_type(obj_type: str, signatures: list) -> list:
    """yml 정식 KB 패턴 중 obj_type/시그니처 매칭되는 것 추출."""
    try:
        all_p = get_all_patterns()
        matched = []
        for pid, entry in all_p.items():
            # category 가 obj_type 매칭되거나, 시그니처 키워드가 패턴 ID 에 포함
            entry_cat = (entry.get("category") or "").upper()
            applies_to = (entry.get("applies_to") or [])
            if isinstance(applies_to, str):
                applies_to = [applies_to]
            applies_to_upper = [str(x).upper() for x in applies_to]

            type_match = (
                obj_type and (
                    obj_type in applies_to_upper or
                    obj_type in entry_cat or
                    entry_cat in ("ALL", "ANY", "")
                )
            )
            sig_match = any(sig.upper() in pid.upper() for sig in signatures)

            if type_match or sig_match:
                # 통계로 적중률 계산
                stats = get_stats(days=90).get("patterns", {}).get(pid, {})
                attempts = stats.get("attempts", 0)
                success = stats.get("success", 0)
                hit_rate = round((success / attempts * 100), 0) if attempts else 0

                matched.append({
                    "id": pid,
                    "category": entry_cat,
                    "fix_prompt": entry.get("fix_prompt", ""),
                    "hit_rate_pct": hit_rate,
                    "attempts": attempts,
                })

        # 적중률 높은 순
        matched.sort(key=lambda x: x.get("hit_rate_pct", 0), reverse=True)
        return matched[:5]  # 최대 5개
    except Exception:
        return []


# ─────────────────────────────────────────────────────
# 통계 기록 (SQLite)
# ─────────────────────────────────────────────────────
def _ensure_stats_db():
    """SQLite DB 준비"""
    _STATS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_STATS_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kb_attempts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_id      TEXT,
            error_code      TEXT,
            category        TEXT,
            job_id          TEXT,
            item_name       TEXT,
            attempt_num     INTEGER,
            success         INTEGER,
            ai_used         INTEGER,
            prompt_chars    INTEGER,
            ts              TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pattern ON kb_attempts(pattern_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON kb_attempts(ts)")
    conn.commit()
    conn.close()

def record_attempt(
    pattern_id: Optional[str],
    error_code: str = "",
    category: str = "",
    job_id: str = "",
    item_name: str = "",
    attempt_num: int = 1,
    success: bool = False,
    ai_used: bool = False,
    prompt_chars: int = 0,
) -> None:
    """
    시도 결과 기록. 예외를 밖으로 내지 않음 (메인 흐름 방해 금지).
    pattern_id 가 None 이면 "_UNMATCHED_" 로 기록.
    """
    try:
        _ensure_stats_db()
        conn = sqlite3.connect(str(_STATS_DB))
        conn.execute(
            """INSERT INTO kb_attempts
               (pattern_id, error_code, category, job_id, item_name,
                attempt_num, success, ai_used, prompt_chars, ts)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pattern_id or "_UNMATCHED_",
                error_code,
                category,
                job_id,
                item_name,
                attempt_num,
                1 if success else 0,
                1 if ai_used else 0,
                prompt_chars,
                datetime.now().isoformat(timespec="seconds"),
            )
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # 통계 기록 실패는 무시

def get_stats(days: int = 30) -> dict:
    """
    통계 요약. 관리자 UI 용.
    반환:
        {
            "total_attempts": 125,
            "total_success": 89,
            "overall_rate": 0.712,
            "ai_attempts": 98,
            "ai_saved": 27,      # AI 호출 안 한 경우 (config_change / engine_rule)
            "by_pattern": [
                {
                    "pattern_id": "1064_UPDATE_SET_COMMA",
                    "error_code": "1064",
                    "category": "SYNTAX",
                    "attempts": 45, "success": 42, "rate": 0.933,
                    "last_seen": "2026-04-20T18:58:02",
                },
                ...
            ],
            "by_category": { "SYNTAX": {...}, "PERMISSION": {...}, ... }
        }
    """
    try:
        _ensure_stats_db()
        conn = sqlite3.connect(str(_STATS_DB))
        conn.row_factory = sqlite3.Row
        # 전체 카운트
        total = conn.execute(
            "SELECT COUNT(*) AS n, SUM(success) AS s, SUM(ai_used) AS a "
            "FROM kb_attempts WHERE ts >= datetime('now', ?)",
            (f"-{days} days",)
        ).fetchone()
        total_n = total["n"] or 0
        total_s = total["s"] or 0
        ai_a    = total["a"] or 0
        ai_saved = total_n - ai_a   # AI 사용 안 함 = 설정/엔진 규칙 기반

        # 패턴별
        rows = conn.execute(
            """SELECT pattern_id, error_code, category,
                      COUNT(*) AS attempts, SUM(success) AS success, MAX(ts) AS last_seen
               FROM kb_attempts
               WHERE ts >= datetime('now', ?)
               GROUP BY pattern_id, error_code, category
               ORDER BY attempts DESC""",
            (f"-{days} days",)
        ).fetchall()

        by_pattern = []
        for r in rows:
            attempts = r["attempts"] or 0
            success  = r["success"] or 0
            by_pattern.append({
                "pattern_id": r["pattern_id"],
                "error_code": r["error_code"] or "",
                "category":   r["category"]   or "",
                "attempts":   attempts,
                "success":    success,
                "rate":       (success / attempts) if attempts else 0.0,
                "last_seen":  r["last_seen"] or "",
            })

        # 카테고리별
        by_cat = {}
        for r in rows:
            c = r["category"] or "UNKNOWN"
            if c not in by_cat:
                by_cat[c] = {"attempts": 0, "success": 0}
            by_cat[c]["attempts"] += r["attempts"] or 0
            by_cat[c]["success"]  += r["success"] or 0
        for c, v in by_cat.items():
            v["rate"] = (v["success"] / v["attempts"]) if v["attempts"] else 0.0

        conn.close()
        return {
            "total_attempts": total_n,
            "total_success":  total_s,
            "overall_rate":   (total_s / total_n) if total_n else 0.0,
            "ai_attempts":    ai_a,
            "ai_saved":       ai_saved,
            "by_pattern":     by_pattern,
            "by_category":    by_cat,
            "days":           days,
        }
    except Exception as e:
        return {
            "total_attempts": 0, "total_success": 0, "overall_rate": 0.0,
            "ai_attempts": 0, "ai_saved": 0,
            "by_pattern": [], "by_category": {},
            "error": str(e),
        }

def get_unmatched_samples(days: int = 30, limit: int = 20) -> list:
    """
    매칭되지 않은 에러 샘플 (신규 패턴 후보).
    관리자 UI 에서 '새 패턴 후보' 탐색용.
    """
    try:
        _ensure_stats_db()
        conn = sqlite3.connect(str(_STATS_DB))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT job_id, item_name, attempt_num, success, ts
               FROM kb_attempts
               WHERE pattern_id = '_UNMATCHED_'
                 AND ts >= datetime('now', ?)
               ORDER BY ts DESC LIMIT ?""",
            (f"-{days} days", limit)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []
