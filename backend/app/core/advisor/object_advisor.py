"""
app/core/advisor/object_advisor.py — SP/Function/View/Trigger 최적화 Advisor
v88 P4 (2026-04-23)

역할:
    선택된 오브젝트의 DDL 을 정적 분석하여 안티패턴과 최적화 기회를 찾는다.

P4 범위 (정규식 기반 정적 분석):
    1. WHERE 컬럼 함수 래핑 — YEAR(col), SUBSTRING(col,..) (인덱스 무효화)
    2. CURSOR 사용 — Set-based 재작성 권고
    3. SELECT * — 명시적 컬럼 지정 권고
    4. WITH (NOLOCK) — MSSQL → MySQL 변환 시 위험성 고지
    5. 하드코딩 배치 크기 — TOP 1000 같은 매직 넘버

설계 원칙:
    - 정적 분석 (정규식 + 단순 파싱) — AI 없이 70% 커버
    - 소스 DDL 이 필요 → schema/objects 엔드포인트에서 이미 가져옴
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from app.core.advisor.base_advisor import (
    BaseAdvisor,
    JobSelection,
    AnalysisContext,
    AnalysisMode,
    Recommendation,
)

logger = logging.getLogger("databridge.advisor.object")


# ══════════════════════════════════════════════════════════════
# 정적 분석 패턴
# ══════════════════════════════════════════════════════════════
_RE_WHERE_FUNC_WRAP = re.compile(
    r"""
    \bWHERE\b[^;]*?
    \b(YEAR|MONTH|DAY|DATE|SUBSTRING|SUBSTR|LOWER|UPPER|TRIM|CAST|CONVERT|ISNULL|COALESCE)
    \s*\(\s*
    (?:[a-zA-Z_][\w.]*)
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)
_RE_CURSOR = re.compile(r"\bDECLARE\s+\w+\s+CURSOR\b", re.IGNORECASE)
_RE_SELECT_STAR = re.compile(r"\bSELECT\s+\*\s+FROM\b", re.IGNORECASE)
_RE_NOLOCK = re.compile(r"\bWITH\s*\(\s*NOLOCK\s*\)", re.IGNORECASE)
_RE_TOP_HARDCODE = re.compile(r"\bTOP\s+\(?\s*(\d{3,})\s*\)?", re.IGNORECASE)


# ══════════════════════════════════════════════════════════════
# DDL 조회 — 스키마 인식 (v88 hotfix3, 2026-04-23)
#
# 변경 이유:
#   기존 MSSQL 구현은 OBJECT_DEFINITION(OBJECT_ID(name)) 사용.
#   이 방식은 스키마 미지정 시 dbo 로 가정 → 사용자 스키마(collection/ref/
#   settlement 등) 에 있는 SP 는 모두 NULL 반환.
#   결과: 본부장님 환경에서 SP 15개, Function 11개 모두 DDL 조회 실패 →
#   ObjectAdvisor 권고 0건.
#
# 해결:
#   sys.sql_modules + sys.objects + sys.schemas JOIN 으로 한 번에 조회.
#   sp_ 접두사 문제도 우회 (시스템 검색 안 함).
#   암호화된 SP 는 definition IS NULL 로 명확히 구분.
# ══════════════════════════════════════════════════════════════

# 타입 코드 매핑 (MSSQL sys.objects.type)
_MSSQL_TYPE_TO_CAT = {
    'P':  'procedure',      # SQL_STORED_PROCEDURE
    'PC': 'procedure',      # CLR_STORED_PROCEDURE (DDL 없음 — definition NULL)
    'FN': 'function',       # SQL_SCALAR_FUNCTION
    'IF': 'function',       # SQL_INLINE_TABLE_VALUED_FUNCTION
    'TF': 'function',       # SQL_TABLE_VALUED_FUNCTION
    'V':  'view',           # VIEW
    'TR': 'trigger',        # SQL_TRIGGER
}


def _parse_qualified_name(n: str) -> tuple[Optional[str], str]:
    """
    오브젝트 이름에서 스키마 접두사 분리.
      "sp_foo"          → (None, "sp_foo")
      "dbo.sp_foo"      → ("dbo", "sp_foo")
      "[dbo].[sp_foo]"  → ("dbo", "sp_foo")
    """
    if not n:
        return None, ""
    # 대괄호 제거
    cleaned = n.replace("[", "").replace("]", "")
    if "." in cleaned:
        parts = cleaned.split(".", 1)
        return parts[0], parts[1]
    return None, cleaned


def _fetch_object_ddl(
    objects_by_type: dict[str, list[str]],
    context: AnalysisContext,
) -> dict[str, str]:
    """
    DDL 텍스트 일괄 조회.

    Returns:
        { "procedure:원본이름": "CREATE PROCEDURE ...", ... }
        원본이름 = selection 에서 넘어온 형태 그대로 (매칭 일관성)

    실패한 이름은 context._advisor_ddl_failures 에 누적 (진단용).
    """
    if context.src_conn is None:
        return {}

    src_db = (context.src_db or "").lower()
    conn = context.src_conn
    result: dict[str, str] = {}

    # 선택된 모든 이름 (중복 제거, 스키마/이름 분리해서 매핑 유지)
    name_specs: list[tuple[str, str, Optional[str], str]] = []
    # (original_input, obj_type, schema_or_none, bare_name)
    for obj_type, names in [
        ("procedure", objects_by_type.get("procedures", [])),
        ("function",  objects_by_type.get("functions", [])),
        ("view",      objects_by_type.get("views", [])),
        ("trigger",   objects_by_type.get("triggers", [])),
    ]:
        for name in names:
            if not name:
                continue
            schema, bare = _parse_qualified_name(name)
            name_specs.append((name, obj_type, schema, bare))

    if not name_specs:
        return {}

    # 진단용 실패 목록 (context 에 저장)
    failures: list[str] = []

    try:
        if src_db in ("mysql", "mariadb", "aurora", "tidb", "cloudsql"):
            # MySQL — 단일 스키마 (DATABASE()) 내에서만 조회하므로 기존 방식 유지
            _fetch_mysql_ddl(conn, name_specs, result, failures)

        elif src_db in ("mssql", "azure", "sqlserver"):
            # MSSQL — sys.sql_modules 일괄 조회 방식
            _fetch_mssql_ddl(conn, name_specs, result, failures)

        else:
            logger.info("ObjectAdvisor: src_db=%s DDL 조회 미구현", src_db)
            failures = [n for n, _, _, _ in name_specs]

    except Exception as e:
        logger.warning("_fetch_object_ddl 전체 실패: %s", e)
        failures = [n for n, _, _, _ in name_specs]

    # 진단 정보 저장 (context 가 dataclass 지만 런타임 속성 추가 가능)
    try:
        setattr(context, "_ddl_fetch_diagnostics", {
            "total_requested": len(name_specs),
            "fetched": len(result),
            "failed": len(failures),
            "failed_names": failures[:20],  # 최대 20개만
        })
    except Exception:
        pass

    if failures:
        logger.warning(
            "ObjectAdvisor DDL 조회 실패 %d건 (총 %d건 중): %s%s",
            len(failures), len(name_specs),
            ", ".join(failures[:5]),
            " ..." if len(failures) > 5 else "",
        )

    return result


def _fetch_mysql_ddl(conn, name_specs, result, failures):
    """MySQL 용 — 한 오브젝트씩 SHOW CREATE (일괄 조회 API 없음)."""
    cur = conn.cursor()
    try:
        for original, obj_type, schema, bare in name_specs:
            # MySQL 은 schema.name 형식도 지원
            fq_name = f"{schema}.{bare}" if schema else bare
            try:
                if obj_type == "procedure":
                    cur.execute(f"SHOW CREATE PROCEDURE {fq_name}")
                    row = cur.fetchone()
                    ddl = row[2] if row and len(row) >= 3 else None
                elif obj_type == "function":
                    cur.execute(f"SHOW CREATE FUNCTION {fq_name}")
                    row = cur.fetchone()
                    ddl = row[2] if row and len(row) >= 3 else None
                elif obj_type == "view":
                    cur.execute(f"SHOW CREATE VIEW {fq_name}")
                    row = cur.fetchone()
                    ddl = row[1] if row and len(row) >= 2 else None
                elif obj_type == "trigger":
                    cur.execute(f"SHOW CREATE TRIGGER {fq_name}")
                    row = cur.fetchone()
                    ddl = row[2] if row and len(row) >= 3 else None
                else:
                    ddl = None

                if ddl:
                    result[f"{obj_type}:{original}"] = ddl
                else:
                    failures.append(original)
            except Exception as e:
                logger.debug("MySQL SHOW CREATE %s %s 실패: %s", obj_type, fq_name, e)
                failures.append(original)
    finally:
        try: cur.close()
        except Exception: pass


def _fetch_mssql_ddl(conn, name_specs, result, failures):
    """
    MSSQL 용 — sys.sql_modules 일괄 조회.

    한 번의 쿼리로 모든 오브젝트 DDL 을 가져옴.
    스키마 미지정 시에도 sys.objects 에서 이름으로 찾음.
    """
    cur = conn.cursor()
    try:
        # 선택된 이름들의 bare name 집합
        bare_names = list({bare for _, _, _, bare in name_specs})
        if not bare_names:
            return

        # 일괄 조회 — 이름으로 필터링, 스키마는 결과에서 확인
        placeholders = ",".join(["?"] * len(bare_names))
        cur.execute(
            f"""
            SELECT
                s.name               AS schema_name,
                o.name               AS object_name,
                o.type               AS type_code,
                m.definition         AS ddl
            FROM sys.sql_modules m
            JOIN sys.objects o ON m.object_id = o.object_id
            JOIN sys.schemas s ON o.schema_id = s.schema_id
            WHERE o.type IN ('P','PC','FN','IF','TF','V','TR')
              AND o.name IN ({placeholders})
            """,
            tuple(bare_names),
        )

        # 결과를 (bare_name, schema) → {type, ddl} 맵으로 구성
        # 동명이인 처리: 같은 이름이 여러 스키마에 있을 수 있음
        fetched_map: dict[str, list[dict]] = {}  # bare_name → [{schema, type, ddl}, ...]
        for row in cur.fetchall():
            schema_n = row[0]
            obj_n    = row[1]
            type_c   = (row[2] or "").strip()
            ddl      = row[3]
            if obj_n not in fetched_map:
                fetched_map[obj_n] = []
            fetched_map[obj_n].append({
                "schema": schema_n,
                "type":   type_c,
                "ddl":    ddl,
                "category": _MSSQL_TYPE_TO_CAT.get(type_c, "procedure"),
            })

        # 요청한 각 이름에 매칭
        for original, obj_type, schema_hint, bare in name_specs:
            candidates = fetched_map.get(bare, [])
            if not candidates:
                failures.append(original)
                continue

            # 카테고리 필터 — 요청한 타입과 맞는 것만
            cat_filtered = [c for c in candidates if c["category"] == obj_type]
            if not cat_filtered:
                # 혹시 카테고리 정보 없이 매칭됐으면 그냥 첫 번째
                cat_filtered = candidates

            # 스키마 힌트 있으면 그걸 우선
            chosen = None
            if schema_hint:
                for c in cat_filtered:
                    if c["schema"].lower() == schema_hint.lower():
                        chosen = c
                        break

            # 스키마 힌트 없거나 매칭 안 되면 첫 번째
            if chosen is None:
                chosen = cat_filtered[0]
                if len(cat_filtered) > 1:
                    schemas = ", ".join(c["schema"] for c in cat_filtered)
                    logger.info(
                        "ObjectAdvisor: %s 동명이인 %d개 (%s) — %s 선택",
                        bare, len(cat_filtered), schemas, chosen["schema"]
                    )

            if chosen["ddl"]:
                result[f"{obj_type}:{original}"] = chosen["ddl"]
            else:
                # definition NULL = 암호화된 SP 또는 권한 부족
                logger.info("ObjectAdvisor: %s 는 definition NULL (암호화 또는 권한 부족)",
                           f"{chosen['schema']}.{bare}")
                failures.append(original)

    finally:
        try: cur.close()
        except Exception: pass


# ══════════════════════════════════════════════════════════════
# 규칙 엔진
# ══════════════════════════════════════════════════════════════
def _rule_where_func_wrap(obj_key: str, ddl: str) -> Optional[Recommendation]:
    matches = _RE_WHERE_FUNC_WRAP.findall(ddl)
    if not matches:
        return None

    func_counts: dict[str, int] = {}
    for fn in matches:
        func_counts[fn.upper()] = func_counts.get(fn.upper(), 0) + 1

    obj_type, obj_name = obj_key.split(":", 1)
    top_funcs = sorted(func_counts.items(), key=lambda x: -x[1])[:3]
    top_desc = ", ".join([f"{fn}({cnt}회)" for fn, cnt in top_funcs])

    return Recommendation(
        id=f"obj.where_func.{obj_key.replace(':', '.')}",
        category="object",
        severity="high" if len(matches) >= 3 else "med",
        title=f"{obj_name} — WHERE 절 컬럼 함수 래핑 {len(matches)}건",
        target=f"{obj_type} {obj_name}",
        reason=(
            f"WHERE 절에서 컬럼을 함수로 감싸면 MySQL 옵티마이저가 인덱스를 사용하지 못합니다. "
            f"테이블 풀스캔으로 전락하는 대표적 안티패턴입니다.\n\n"
            f"• 탐지된 함수 사용: {top_desc}\n"
            f"• 효과: 해당 쿼리가 인덱스 스캔으로 전환 → 10~100배 가속 가능\n\n"
            f"재작성 패턴:\n"
            f"  ❌ WHERE YEAR(created_at) = 2024\n"
            f"  ✓  WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01'\n\n"
            f"  ❌ WHERE LOWER(email) = 'abc@x.com'\n"
            f"  ✓  WHERE email = 'abc@x.com' (컬럼 자체를 case-insensitive collation 으로)\n\n"
            f"  ❌ WHERE SUBSTRING(code, 1, 3) = 'ABC'\n"
            f"  ✓  WHERE code LIKE 'ABC%'"
        ),
        before=f"-- {obj_name} 내부 WHERE 절 예 (탐지):\n-- WHERE YEAR(col) = 2024 등",
        after=(
            f"-- 재작성 예:\n"
            f"-- WHERE col >= '2024-01-01' AND col < '2025-01-01'\n"
            f"-- (각 쿼리를 개별 검토 필요 — AI 변환 또는 수동 리팩터링)"
        ),
        estimated_impact=f"해당 쿼리 10~100배 가속 (인덱스 활용)",
        auto_applicable=False,
        default_action="review",
        source="rule",
        confidence=0.85,
        rule_id="obj.where_func.v1",
    )


def _rule_cursor_usage(obj_key: str, ddl: str) -> Optional[Recommendation]:
    matches = _RE_CURSOR.findall(ddl)
    if not matches:
        return None
    obj_type, obj_name = obj_key.split(":", 1)

    return Recommendation(
        id=f"obj.cursor.{obj_key.replace(':', '.')}",
        category="object",
        severity="high",
        title=f"{obj_name} — CURSOR 사용 {len(matches)}건 (Set-based 재작성 권고)",
        target=f"{obj_type} {obj_name}",
        reason=(
            f"CURSOR 는 행 단위 반복 처리로 대용량에서 매우 느립니다. "
            f"대부분의 경우 하나의 UPDATE/INSERT..SELECT 쿼리로 재작성 가능합니다.\n\n"
            f"• 탐지: DECLARE CURSOR {len(matches)}건\n"
            f"• 일반적 효과: 10~1000배 가속 (데이터량에 따라)\n\n"
            f"재작성 예시:\n"
            f"  ❌ CURSOR 로 한 행씩 순회하며 UPDATE\n"
            f"  ✓ UPDATE t SET t.x = s.new_val FROM target t JOIN source s ON t.id = s.id;\n\n"
            f"⚠ MySQL 은 UPDATE..JOIN 문법이 다름 (UPDATE t JOIN s ON ... SET ...)"
        ),
        before=f"-- {obj_name}: CURSOR 기반 루프 구조",
        after=(
            f"-- 재작성 전략: 집합 연산 (UPDATE..JOIN / INSERT..SELECT)\n"
            f"-- 개별 분석 필요 — Stage 3 Claude AI 엔진 선택 시 자동 변환 시도"
        ),
        estimated_impact="10~1000배 가속 (데이터량에 비례)",
        auto_applicable=False,
        default_action="review",
        source="rule",
        confidence=0.92,
        rule_id="obj.cursor.v1",
    )


def _rule_select_star(obj_key: str, ddl: str) -> Optional[Recommendation]:
    matches = _RE_SELECT_STAR.findall(ddl)
    if not matches:
        return None
    obj_type, obj_name = obj_key.split(":", 1)
    sev = "med" if obj_type == "view" else "low"

    return Recommendation(
        id=f"obj.select_star.{obj_key.replace(':', '.')}",
        category="object",
        severity=sev,
        title=f"{obj_name} — SELECT * 사용 {len(matches)}건",
        target=f"{obj_type} {obj_name}",
        reason=(
            f"SELECT * 사용은 유지보수·성능·호환성 모두에 불리합니다.\n\n"
            f"• 테이블 구조 변경 시 의도치 않은 동작\n"
            f"• 필요 없는 컬럼까지 전송 → 네트워크/메모리 낭비\n"
            f"• 뷰에서는 컬럼 추가 시 뷰 재생성 필요 (MySQL)"
            + ("\n\n⚠ 뷰는 이관 후 컬럼 추가되어도 자동 반영 안 됨 (DROP+CREATE 필요)"
               if obj_type == "view" else "")
        ),
        before=f"-- {obj_name} 내부:\nSELECT * FROM ...",
        after=f"-- 명시적 컬럼 지정:\nSELECT col1, col2, col3 FROM ...",
        estimated_impact="유지보수성 개선, 네트워크 전송량 감소",
        auto_applicable=False,
        default_action="review",
        source="rule",
        confidence=0.80,
        rule_id="obj.select_star.v1",
    )


def _rule_nolock(obj_key: str, ddl: str, tgt_db: str) -> Optional[Recommendation]:
    if "mysql" not in tgt_db and "maria" not in tgt_db and "aurora" not in tgt_db:
        return None
    matches = _RE_NOLOCK.findall(ddl)
    if not matches:
        return None
    obj_type, obj_name = obj_key.split(":", 1)

    return Recommendation(
        id=f"obj.nolock.{obj_key.replace(':', '.')}",
        category="object",
        severity="high",
        title=f"{obj_name} — WITH (NOLOCK) {len(matches)}건 (MySQL 호환성 주의)",
        target=f"{obj_type} {obj_name}",
        reason=(
            f"MSSQL 의 WITH (NOLOCK) 은 MySQL 에 직접 대응되지 않습니다. "
            f"단순 삭제는 '락 대기'를 유발할 수 있고, READ UNCOMMITTED 대체도 권장 안 됨.\n\n"
            f"• 탐지: WITH (NOLOCK) {len(matches)}건\n"
            f"• 권고 방향:\n"
            f"  1. 단순 삭제 (MySQL MVCC 로 대부분 문제 없음) — 기본 REPEATABLE READ 가 NOLOCK 보다 합리적\n"
            f"  2. SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED — 비추천 (일관성 깨짐)\n"
            f"  3. 실제 락 경합이 있다면 인덱스 개선 / 쿼리 최적화가 정공법"
        ),
        before=f"-- MSSQL:\nSELECT * FROM t WITH (NOLOCK) WHERE ...",
        after=(
            f"-- MySQL (권장):\nSELECT * FROM t WHERE ...\n\n"
            f"-- 또는 (꼭 필요할 때):\n"
            f"SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;\n"
            f"SELECT * FROM t WHERE ...;\n"
            f"SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;"
        ),
        estimated_impact="호환성 확보 — 문법 오류 방지",
        auto_applicable=False,
        default_action="review",
        source="rule",
        confidence=0.95,
        rule_id="obj.nolock.v1",
    )


def _rule_top_hardcode(obj_key: str, ddl: str) -> Optional[Recommendation]:
    matches = _RE_TOP_HARDCODE.findall(ddl)
    if not matches:
        return None
    obj_type, obj_name = obj_key.split(":", 1)
    nums = sorted(set(int(n) for n in matches), reverse=True)[:3]

    return Recommendation(
        id=f"obj.top_hardcode.{obj_key.replace(':', '.')}",
        category="object",
        severity="low",
        title=f"{obj_name} — TOP {nums} 하드코딩 배치 크기",
        target=f"{obj_type} {obj_name}",
        reason=(
            f"TOP 절에 하드코딩된 배치 크기가 있습니다. "
            f"매직 넘버는 요구사항 변경 시 유지보수 부담이 됩니다.\n\n"
            f"• 탐지된 숫자: {nums}\n"
            f"• MySQL 변환 시 TOP → LIMIT 전환 필요 (문법 차이)\n"
            f"• 권고: 파라미터 또는 설정값으로 외부화"
        ),
        before=f"-- 예: SELECT TOP 1000 ...",
        after=(
            f"-- MySQL: LIMIT 사용\n"
            f"-- 권고: 파라미터화\n"
            f"--   CREATE PROCEDURE xxx (IN batch_size INT) BEGIN\n"
            f"--     SELECT ... LIMIT batch_size;\n"
            f"--   END"
        ),
        estimated_impact="유지보수성 개선",
        auto_applicable=False,
        default_action="review",
        source="rule",
        confidence=0.70,
        rule_id="obj.top_hardcode.v1",
    )


# ══════════════════════════════════════════════════════════════
# ObjectAdvisor 본체
# ══════════════════════════════════════════════════════════════
class ObjectAdvisor(BaseAdvisor):
    """SP / Function / View / Trigger 안티패턴 탐지."""
    category = "object"

    def supports(self, src_db: str, tgt_db: str) -> bool:
        return True

    def analyze(self, selection: JobSelection, context: AnalysisContext) -> list[Recommendation]:
        obj_total = (
            len(selection.procedures) + len(selection.functions)
            + len(selection.views) + len(selection.triggers)
        )
        if obj_total == 0:
            return []

        ddls = _fetch_object_ddl(
            {
                "procedures": selection.procedures,
                "functions":  selection.functions,
                "views":      selection.views,
                "triggers":   selection.triggers,
            },
            context,
        )
        if not ddls:
            logger.info("ObjectAdvisor: DDL 조회 실패/없음 — 권고 생략")
            return []

        logger.info("ObjectAdvisor: %d개 오브젝트 DDL 분석", len(ddls))
        tgt_db = (context.tgt_db or "").lower()
        recs: list[Recommendation] = []

        for obj_key, ddl in ddls.items():
            if not ddl or len(ddl) < 20:
                continue

            for rule_fn in [_rule_where_func_wrap, _rule_cursor_usage,
                            _rule_select_star, _rule_top_hardcode]:
                try:
                    rec = rule_fn(obj_key, ddl)
                    if rec:
                        recs.append(rec)
                except Exception as e:
                    logger.warning("rule %s failed on %s: %s", rule_fn.__name__, obj_key, e)

            try:
                rec = _rule_nolock(obj_key, ddl, tgt_db)
                if rec:
                    recs.append(rec)
            except Exception as e:
                logger.warning("_rule_nolock failed on %s: %s", obj_key, e)

        logger.info("ObjectAdvisor: %d개 권고 생성", len(recs))
        return recs

    def estimate_tokens(self, selection: JobSelection, mode: AnalysisMode) -> dict:
        obj_total = selection.total_objects
        if mode == "smart":
            return {"tokens_in": 0, "tokens_out": 0}
        elif mode == "hybrid":
            candidates = max(1, obj_total // 3)
            return {"tokens_in": 3500 * candidates, "tokens_out": 1200 * candidates}
        else:
            return {"tokens_in": 3500 * obj_total, "tokens_out": 1200 * obj_total}
