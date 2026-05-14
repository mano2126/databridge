"""
app/engine/conversion_learner.py — 변환 지식 자동 축적 엔진
v10 #18 — 2026-04-21

철학:
  - 에러 KB 와 동일한 원리. AI 가 변환하면서 배운 걸 TypeMapping/ObjectMapping
    규칙 저장소에 자동 축적 → 다음부터는 AI 없이 로컬 변환.
  - 시간이 지나면 AI 호출 횟수가 점점 감소하는 구조 (관리자 대시보드에서 검증).

핵심 훅:
  learn_from_ai_conversion(src_ddl, ai_result, obj_type, obj_name, src_db, tgt_db, job_id)
    → _ai_convert_ddl 성공 반환 직전에 호출. 예외는 삼켜서 본 흐름에 영향 X.

핵심 조회:
  apply_local_kb_first(src_ddl, obj_type, src_db, tgt_db)
    → 완전 로컬 변환 시도. coverage >= 0.95 면 AI 스킵 가능.
    (현재 버전은 훅/집계 중심. 실제 부분 변환은 후속 패치에서 확장.)

규칙 스키마 확장 (기존 필드 유지 + 아래 필드 소프트 추가):
  source:           "manual" | "ai_learned"   (default "manual" — 기존 규칙과 호환)
  status:           "active" | "shadow" | "rejected"  (ai_learned 기본 shadow)
  confidence:       int (등장 횟수, ai_learned 만 의미 있음)
  first_seen:       ISO datetime
  last_seen:        ISO datetime
  example_job_ids:  list[str] (최근 10건)

승격 규칙:
  confidence >= PROMOTE_THRESHOLD (기본 3) 이고 status=="shadow" → 자동 "active"
"""
from __future__ import annotations

import logging
import re
import datetime as _dt
from typing import Any

from app.core.store import Store

logger = logging.getLogger("databridge.learner")

# ── 설정 ──────────────────────────────────────────────────
PROMOTE_THRESHOLD = 3          # confidence 이 값 이상이면 shadow → active 자동 승격
MAX_EXAMPLE_JOBS  = 10         # 규칙별 최근 job_id 보존 개수
MAX_AUTO_PATTERNS_PER_CALL = 50  # 한번 AI 응답에서 추출할 수 있는 최대 패턴 수 (폭주 방지)

# ── 저장소 (mapping.py / obj_mapping.py 와 동일 key) ──────
_type_rules = Store("mapping_rules")
_obj_rules  = Store("obj_mapping_rules")
_metrics    = Store("learner_metrics")  # 일자별 AI/로컬 호출 카운트


# ══════════════════════════════════════════════════════════
# 유틸
# ══════════════════════════════════════════════════════════
def _now_iso() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d")


def _norm_type(t: str) -> str:
    """타입 문자열 정규화 — 길이/정밀도 제외하고 기본 키워드만."""
    if not t:
        return ""
    s = re.sub(r"\s+", " ", t.strip().upper())
    # 괄호 안 숫자/표현 제거: VARCHAR(200) -> VARCHAR, DECIMAL(19,4) -> DECIMAL
    s = re.sub(r"\([^)]*\)", "", s).strip()
    # 끝의 CHARACTER SET / COLLATE 는 유지 (변환 의미 있음)
    return s


# ══════════════════════════════════════════════════════════
# 1. AI 결과에서 타입 쌍 추출
# ══════════════════════════════════════════════════════════
# CREATE TABLE 컬럼 라인: `col_name` TYPE [constraints...]
#   - 백틱/대괄호/쌍따옴표 모두 허용
_IDENT_QUOTE = r"[`\[\]\"]?"
_COL_LINE_RE = re.compile(
    rf"^\s*{_IDENT_QUOTE}(\w+){_IDENT_QUOTE}\s+"
    r"([A-Za-z][A-Za-z0-9_]*(?:\s*\([^)]*\))?)"
    r"(?:\s+(?:CHARACTER\s+SET\s+\w+|COLLATE\s+\w+))*",
    re.IGNORECASE | re.MULTILINE,
)


def _extract_columns(ddl: str) -> list[tuple[str, str]]:
    """DDL 에서 (컬럼명, 타입표현식) 리스트 추출. CREATE TABLE 본문만."""
    if not ddl:
        return []
    # CREATE TABLE ... ( ... ) 괄호 블록만 추출
    m = re.search(r"CREATE\s+TABLE[^(]*\((.+)\)[^)]*$", ddl, re.IGNORECASE | re.DOTALL)
    body = m.group(1) if m else ddl

    cols: list[tuple[str, str]] = []
    for line in body.split(","):
        line = line.strip()
        if not line:
            continue
        # 제약조건 스킵
        upper = line.upper()
        if upper.startswith(("PRIMARY ", "UNIQUE ", "KEY ", "CONSTRAINT ",
                             "FOREIGN ", "INDEX ", "CHECK ", "FULLTEXT")):
            continue
        m2 = _COL_LINE_RE.match(line)
        if not m2:
            continue
        cols.append((m2.group(1), m2.group(2).strip()))
    return cols


def _extract_type_pairs(src_ddl: str, tgt_stmts: list[str]) -> list[tuple[str, str]]:
    """
    원본 DDL 과 AI 가 생성한 CREATE TABLE 문을 각각 파싱해서
    같은 컬럼명 기준으로 (원본타입, 타겟타입) 쌍 추출.
    """
    src_cols = dict(_extract_columns(src_ddl))
    if not src_cols:
        return []

    tgt_create = next(
        (s for s in tgt_stmts if re.search(r"CREATE\s+TABLE", s or "", re.IGNORECASE)),
        "",
    )
    if not tgt_create:
        return []

    tgt_cols = dict(_extract_columns(tgt_create))
    pairs: list[tuple[str, str]] = []
    for name, stype in src_cols.items():
        ttype = tgt_cols.get(name)
        if not ttype:
            continue
        sn, tn = _norm_type(stype), _norm_type(ttype)
        if not sn or not tn or sn == tn:
            continue
        pairs.append((sn, tn))
    return pairs


# ══════════════════════════════════════════════════════════
# 2. 오브젝트 변환 패턴 추출 (간이)
# ══════════════════════════════════════════════════════════
# 주요 syntax 변환: 함수 치환, 식별자 인용 부호 등
# hotfix_078 (2026-05-12 본부장님 본질 처방):
#   본부장님 13개 실패 직접 원인 패턴 추가 — 학습 KB 가 시간 갈수록 자람
#   메모리 #4 (변환 KB = 살아있는 자산, AI 호출 점점 감소) 정면 실현
_OBJ_PATTERNS = [
    # ── 함수 치환 (기존) ──
    ("GETDATE\\(\\)",        "NOW\\(\\)",              "함수", "GETDATE()", "NOW()"),
    ("ISNULL\\s*\\(",        "IFNULL\\s*\\(",          "함수", "ISNULL(", "IFNULL("),
    ("NEWID\\(\\)",          "UUID\\(\\)",             "함수", "NEWID()", "UUID()"),
    ("SYSTEM_USER",          "CURRENT_USER\\(\\)",     "함수", "SYSTEM_USER", "CURRENT_USER()"),
    ("RAISERROR",            "SIGNAL\\s+SQLSTATE",     "예외처리", "RAISERROR", "SIGNAL SQLSTATE"),
    ("NOW\\(\\)",            "GETDATE\\(\\)",          "함수", "NOW()", "GETDATE()"),
    ("IFNULL\\s*\\(",        "ISNULL\\s*\\(",          "함수", "IFNULL(", "ISNULL("),
    # ── 함수 치환 (hotfix_078 추가, 본부장님 환경 빈도 높은 7건) ──
    ("\\bLEN\\s*\\(",        "\\bCHAR_LENGTH\\s*\\(",  "함수", "LEN(", "CHAR_LENGTH("),
    ("GETUTCDATE\\(\\)",     "UTC_TIMESTAMP\\(\\)",    "함수", "GETUTCDATE()", "UTC_TIMESTAMP()"),
    ("\\bIIF\\s*\\(",        "\\bIF\\s*\\(",           "함수", "IIF(", "IF("),
    ("\\bCHARINDEX\\s*\\(",  "\\bLOCATE\\s*\\(",       "함수", "CHARINDEX(", "LOCATE("),
    ("\\bSUSER_SNAME\\b",    "\\bCURRENT_USER\\(\\)",  "함수", "SUSER_SNAME", "CURRENT_USER()"),
    ("DATEPART\\s*\\(\\s*yy", "\\bYEAR\\s*\\(",        "함수", "DATEPART(yy,)", "YEAR("),
    ("CONVERT\\s*\\(\\s*VARCHAR", "DATE_FORMAT\\s*\\(", "함수", "CONVERT(VARCHAR,d,fmt)", "DATE_FORMAT(d,fmt)"),
    # ── 식별자 인용 부호 (hotfix_078 핵심 — 13개 실패 직접 원인) ──
    ("\\[\\w+\\]\\.\\[\\w+\\]", "`\\w+_\\w+`",          "식별자", "[Schema].[Object]", "`Schema_Object`"),
    ("\\[[A-Za-z_]\\w*\\]",  "`[A-Za-z_]\\w*`",        "식별자", "[Identifier]", "`Identifier`"),
    # ── T-SQL 잔재 (hotfix_078 추가) ──
    ("\\bN'[^']*'",          "(?<!N)'[^']*'",          "리터럴", "N'string'", "'string'"),
    ("SET\\s+NOCOUNT\\s+ON", "",                       "지시어", "SET NOCOUNT ON", "(제거)"),
    # ── 데이터형/연산자 (hotfix_078 추가) ──
    ("\\bTOP\\s+\\d+",       "LIMIT\\s+\\d+",          "쿼리", "TOP N", "LIMIT N"),
    ("\\bCONCAT\\s*\\+",     "CONCAT\\s*\\(",          "연산자", "a + b (문자)", "CONCAT(a,b)"),
    ("WITH\\s+\\(\\s*NOLOCK\\s*\\)", "",               "힌트", "WITH (NOLOCK)", "(제거)"),
    ("WITH\\s+SCHEMABINDING", "",                      "지시어", "WITH SCHEMABINDING", "(제거)"),
]


def _extract_obj_patterns(src_ddl: str, tgt_stmts: list[str]) -> list[dict]:
    """원본과 타겟에서 알려진 변환 패턴이 둘 다 일치하면 후보로 기록."""
    if not src_ddl or not tgt_stmts:
        return []
    tgt_all = "\n".join(s or "" for s in tgt_stmts)
    hits: list[dict] = []
    for src_re, tgt_re, cat, sp, tp in _OBJ_PATTERNS:
        # hotfix_078: tgt_re 가 빈 문자열이면 "제거 변환" — src 만 있고 tgt 에 없으면 학습
        if not tgt_re:
            if re.search(src_re, src_ddl, re.IGNORECASE) and not re.search(src_re, tgt_all, re.IGNORECASE):
                hits.append({
                    "category":   cat,
                    "src_syntax": sp,
                    "tgt_syntax": tp,
                    "note":       f"AI 학습 — {sp} → {tp}",
                })
            continue
        if re.search(src_re, src_ddl, re.IGNORECASE) and re.search(tgt_re, tgt_all, re.IGNORECASE):
            hits.append({
                "category":   cat,
                "src_syntax": sp,
                "tgt_syntax": tp,
                "note":       f"AI 학습 — {sp} → {tp}",
            })
    return hits


# ══════════════════════════════════════════════════════════
# 3. 규칙 upsert (confidence 증가 + 자동 승격)
# ══════════════════════════════════════════════════════════
def _find_type_rule(src_db: str, tgt_db: str, src_type: str, tgt_type: str):
    for rid, rule in _type_rules.all().items():
        if (rule.get("src_db") == src_db and
            rule.get("tgt_db") == tgt_db and
            _norm_type(rule.get("src_type", "")) == src_type and
            _norm_type(rule.get("tgt_type", "")) == tgt_type):
            return rid, rule
    return None, None


def _find_obj_rule(src_db: str, tgt_db: str, obj_type: str, src_syntax: str, tgt_syntax: str):
    for rid, rule in _obj_rules.all().items():
        if (rule.get("src_db") == src_db and
            rule.get("tgt_db") == tgt_db and
            rule.get("obj_type") == obj_type and
            rule.get("src_syntax") == src_syntax and
            rule.get("tgt_syntax") == tgt_syntax):
            return rid, rule
    return None, None


def _upsert(store: Store, rid, rule, new_data: dict, job_id: str) -> tuple[bool, str]:
    """
    규칙 insert/update 후 (is_new, status) 반환.
    is_new=True → 새로 생성된 ai_learned 규칙
    """
    import uuid as _uuid
    now = _now_iso()

    if rule is None:
        rid = str(_uuid.uuid4())[:8]
        rule = {
            "id": rid,
            **new_data,
            "custom":           False,
            "source":           "ai_learned",
            "status":           "shadow",
            "confidence":       1,
            "first_seen":       now,
            "last_seen":        now,
            "example_job_ids":  [job_id] if job_id else [],
        }
        store.set(rid, rule)
        return True, "shadow"

    # 기존 규칙
    conf = int(rule.get("confidence") or 0) + 1
    examples = list(rule.get("example_job_ids") or [])
    if job_id and job_id not in examples:
        examples.append(job_id)
        examples = examples[-MAX_EXAMPLE_JOBS:]

    status = rule.get("status", "active" if rule.get("source") != "ai_learned" else "shadow")
    # 자동 승격: ai_learned + shadow + confidence 임계치 이상
    if (rule.get("source") == "ai_learned"
            and status == "shadow"
            and conf >= PROMOTE_THRESHOLD):
        status = "active"

    rule.update({
        "confidence":      conf,
        "last_seen":       now,
        "example_job_ids": examples,
        "status":          status,
        "source":          rule.get("source", "manual"),
    })
    store.set(rid, rule)
    return False, status


# ══════════════════════════════════════════════════════════
# 4. 메트릭 (AI 호출 vs 로컬 처리)
# ══════════════════════════════════════════════════════════
def _bump_metric(kind: str, n: int = 1) -> None:
    """kind: 'ai_calls' | 'local_hits' | 'patterns_learned'"""
    try:
        day = _today()
        row = _metrics.get(day) or {"date": day, "ai_calls": 0, "local_hits": 0, "patterns_learned": 0}
        row[kind] = int(row.get(kind, 0)) + n
        _metrics.set(day, row)
    except Exception as e:
        logger.warning("metric 기록 실패: %s", e)


# ══════════════════════════════════════════════════════════
# 5. 외부 공개 — 학습 훅
# ══════════════════════════════════════════════════════════
def learn_from_ai_conversion(
    src_ddl: str,
    ai_result: dict,
    obj_type: str,
    obj_name: str,
    src_db: str,
    tgt_db: str,
    job_id: str = "",
) -> dict:
    """
    _ai_convert_ddl 의 성공 반환 직전에 호출.
    실패해도 본 흐름에 영향 없도록 안전 예외 처리.

    반환: {"new_type_rules": N, "new_obj_rules": N, "updated": N}
    """
    summary = {"new_type_rules": 0, "new_obj_rules": 0, "updated": 0}

    try:
        _bump_metric("ai_calls", 1)

        if not ai_result or not isinstance(ai_result, dict):
            return summary
        stmts = ai_result.get("statements") or []
        if not stmts:
            return summary

        src_db = (src_db or "").lower()
        tgt_db = (tgt_db or "").lower()
        obj_type = (obj_type or "").upper()

        learned_count = 0

        # ── 타입 매핑 추출 (TABLE 인 경우만 의미 있음) ──
        if obj_type in ("TABLE", "", None):
            pairs = _extract_type_pairs(src_ddl, stmts)
            for (stype, ttype) in pairs[:MAX_AUTO_PATTERNS_PER_CALL]:
                rid, rule = _find_type_rule(src_db, tgt_db, stype, ttype)
                is_new, _st = _upsert(_type_rules, rid, rule, {
                    "src_db":   src_db,
                    "tgt_db":   tgt_db,
                    "src_type": stype,
                    "tgt_type": ttype,
                    "note":     f"AI 학습 ({obj_name})",
                    "warning":  False,
                }, job_id)
                if is_new:
                    summary["new_type_rules"] += 1
                    learned_count += 1
                else:
                    summary["updated"] += 1

        # ── 오브젝트 매핑 추출 (함수/구문) ──
        obj_hits = _extract_obj_patterns(src_ddl, stmts)
        for h in obj_hits[:MAX_AUTO_PATTERNS_PER_CALL]:
            rid, rule = _find_obj_rule(src_db, tgt_db, obj_type or "SYNTAX",
                                        h["src_syntax"], h["tgt_syntax"])
            is_new, _st = _upsert(_obj_rules, rid, rule, {
                "src_db":     src_db,
                "tgt_db":     tgt_db,
                "obj_type":   obj_type or "SYNTAX",
                "category":   h["category"],
                "src_syntax": h["src_syntax"],
                "tgt_syntax": h["tgt_syntax"],
                "note":       h["note"],
                "warning":    False,
                "is_regex":   False,
            }, job_id)
            if is_new:
                summary["new_obj_rules"] += 1
                learned_count += 1
            else:
                summary["updated"] += 1

        if learned_count:
            _bump_metric("patterns_learned", learned_count)
            logger.info(
                "[KB 학습] %s (%s→%s): 타입 신규 %d, 오브젝트 신규 %d, 갱신 %d",
                obj_name, src_db, tgt_db,
                summary["new_type_rules"], summary["new_obj_rules"], summary["updated"],
            )

    except Exception as e:
        logger.warning("conversion_learner 실패 (무시): %s", e)

    return summary


# ══════════════════════════════════════════════════════════
# 6. 로컬 우선 조회 — coverage 계산용
# ══════════════════════════════════════════════════════════
def estimate_local_coverage(src_ddl: str, src_db: str, tgt_db: str) -> dict:
    """
    DDL 의 컬럼 중 active 규칙으로 커버 가능한 비율 계산.
    후속 패치에서 '부분 AI 호출' 로직에 활용.
    """
    src_db = (src_db or "").lower()
    tgt_db = (tgt_db or "").lower()
    cols = _extract_columns(src_ddl)
    if not cols:
        return {"total": 0, "covered": 0, "coverage": 0.0}

    active_rules = [
        r for r in _type_rules.values()
        if r.get("src_db") == src_db
        and r.get("tgt_db") == tgt_db
        and r.get("status", "active") == "active"
    ]
    key_set = {_norm_type(r.get("src_type", "")) for r in active_rules}

    covered = sum(1 for _, t in cols if _norm_type(t) in key_set)
    return {
        "total":    len(cols),
        "covered":  covered,
        "coverage": round(covered / len(cols), 3),
    }


# ══════════════════════════════════════════════════════════
# 7. 로컬 히트 기록 (향후 부분 변환이 성공했을 때 호출)
# ══════════════════════════════════════════════════════════
def record_local_hit(n: int = 1) -> None:
    _bump_metric("local_hits", n)


# ══════════════════════════════════════════════════════════
# 8. 메트릭 조회 (대시보드용)
# ══════════════════════════════════════════════════════════
def get_metrics(days: int = 30) -> dict:
    """최근 N일 AI/로컬 호출 추이."""
    cutoff = _dt.date.today() - _dt.timedelta(days=days - 1)
    rows = []
    for k, v in _metrics.all().items():
        try:
            d = _dt.date.fromisoformat(k)
            if d >= cutoff:
                rows.append(v)
        except Exception:
            continue
    rows.sort(key=lambda r: r.get("date", ""))

    total_ai    = sum(int(r.get("ai_calls", 0))         for r in rows)
    total_local = sum(int(r.get("local_hits", 0))       for r in rows)
    total_learn = sum(int(r.get("patterns_learned", 0)) for r in rows)
    total = total_ai + total_local
    return {
        "days":    days,
        "daily":   rows,
        "summary": {
            "ai_calls":         total_ai,
            "local_hits":       total_local,
            "patterns_learned": total_learn,
            "local_ratio":      round(total_local / total, 3) if total else 0.0,
        },
    }


def get_kb_overview() -> dict:
    """KB 자산 현황 — 수동/AI학습/상태별 집계."""
    def _agg(store: Store) -> dict:
        rules = store.values()
        return {
            "total":      len(rules),
            "manual":     sum(1 for r in rules if r.get("source", "manual") == "manual"),
            "ai_learned": sum(1 for r in rules if r.get("source") == "ai_learned"),
            "active":     sum(1 for r in rules if r.get("status", "active") == "active"),
            "shadow":     sum(1 for r in rules if r.get("status") == "shadow"),
            "rejected":   sum(1 for r in rules if r.get("status") == "rejected"),
        }
    return {
        "type_mapping":   _agg(_type_rules),
        "object_mapping": _agg(_obj_rules),
    }


def set_rule_status(kind: str, rule_id: str, status: str) -> bool:
    """관리자 수동 승격/거부. kind: 'type' | 'obj'. status: 'active'|'shadow'|'rejected'."""
    if status not in ("active", "shadow", "rejected"):
        return False
    store = _type_rules if kind == "type" else _obj_rules
    rule = store.get(rule_id)
    if not rule:
        return False
    rule["status"] = status
    store.set(rule_id, rule)
    return True
