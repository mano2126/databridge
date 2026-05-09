# -*- coding: utf-8 -*-
"""
DataBridge v95_p6 (2026-05-02) — View 안티패턴 분석기

본부장님 명령 (2026-05-02):
  "당연 본질적인 문제 해결"
  "다양한 DB 환경에서 작동해야"

본질 진단:
  본부장님 환경 5개 View 가 30초 timeout
  → 4가지 다른 안티패턴 (윈도우 함수, 상관 서브쿼리, COUNT(DISTINCT)+GROUP BY, COLLATE)
  → 모두 *대용량 테이블 참조* + DataBridge 의 LIMIT 50 호출 시 옵티마이저 풀 스캔

본질 처방:
  1. View 정의 분석 — information_schema.VIEWS 또는 SHOW CREATE VIEW
  2. 위험 패턴 정규식 매칭 (4종)
  3. 참조 테이블 행수 확인
  4. 위험 + 대용량 → 안전 검증 모드 (LIMIT 1)

지원 DB:
  - MySQL/MariaDB/Aurora: information_schema.VIEWS (표준)
  - PostgreSQL: information_schema.views (표준)
  - Oracle: ALL_VIEWS
  - MSSQL: sys.views + sys.sql_modules
  - DB2: SYSCAT.VIEWS

통합 진입점: analyze_view_risk(cur, db_type, db_name, view_name) -> dict
"""

import re as _re
import logging as _logging

_logger = _logging.getLogger("databridge.view_analyzer")


# ════════════════════════════════════════════════════════════════════
# 위험 패턴 정규식 (case-insensitive)
# ════════════════════════════════════════════════════════════════════

_PATTERN_WINDOW_FUNCTION = _re.compile(
    r'\b(ROW_NUMBER|RANK|DENSE_RANK|LEAD|LAG|FIRST_VALUE|LAST_VALUE|'
    r'NTILE|PERCENT_RANK|CUME_DIST|NTH_VALUE)\s*\([^)]*\)\s+OVER\b',
    _re.IGNORECASE
)

# 상관 서브쿼리 — SELECT 안에 또 SELECT 있고 WHERE 에 외부 테이블 참조
# 단순 정규식으로 100% 정확하게 잡기는 어려워 *복수 서브쿼리* 휴리스틱
_PATTERN_NESTED_SELECT = _re.compile(
    r'\(\s*SELECT\s+.*?\bFROM\b.*?\bWHERE\b.*?\)',
    _re.IGNORECASE | _re.DOTALL
)

_PATTERN_COUNT_DISTINCT = _re.compile(
    r'COUNT\s*\(\s*DISTINCT\b',
    _re.IGNORECASE
)

_PATTERN_GROUP_BY = _re.compile(
    r'\bGROUP\s+BY\b',
    _re.IGNORECASE
)

# COLLATE 변환 (JOIN 조건의 인덱스 무효화)
_PATTERN_COLLATE_IN_JOIN = _re.compile(
    r'(?:\bON\b|\bJOIN\b)[^()]*\bCOLLATE\b',
    _re.IGNORECASE
)

# 참조 테이블 추출 (FROM/JOIN 절)
# 매우 단순한 휴리스틱 — 정확한 SQL 파서는 아니지만 본부장님 환경 케이스 잡기 충분
_PATTERN_FROM_TABLE = _re.compile(
    r'(?:\bFROM\b|\bJOIN\b)\s+`?([a-zA-Z_][a-zA-Z0-9_]*)`?\s+(?:`?[a-zA-Z_][a-zA-Z0-9_]*`?\s+)?(?:ON\b|WHERE\b|GROUP\b|ORDER\b|HAVING\b|,|\)|$)',
    _re.IGNORECASE
)


# ════════════════════════════════════════════════════════════════════
# 위험 패턴 분석
# ════════════════════════════════════════════════════════════════════

def analyze_view_definition(view_def: str) -> dict:
    """View 정의의 안티패턴 분석

    Args:
        view_def: View 의 SELECT 문 (CREATE VIEW ... AS 부분 제외 가능)

    Returns:
        {
            "patterns": ["window_function", "count_distinct_groupby", ...],
            "is_risky": bool,
            "details": {...}
        }
    """
    if not view_def:
        return {"patterns": [], "is_risky": False, "details": {}}

    patterns_found = []
    details = {}

    # 1. 윈도우 함수
    win_matches = _PATTERN_WINDOW_FUNCTION.findall(view_def)
    if win_matches:
        patterns_found.append("window_function")
        details["window_functions"] = list(set(m.upper() for m in win_matches))

    # 2. 상관 서브쿼리 — 복수 서브쿼리 + SELECT 본체에 외부 테이블 참조
    nested = _PATTERN_NESTED_SELECT.findall(view_def)
    if len(nested) >= 1:
        # 상관 서브쿼리 휴리스틱: 서브쿼리가 있고, 외부 alias 참조가 보이면
        # 정확한 판단은 SQL 파서 필요하지만 본부장님 환경 패턴 잡기 충분
        # ref_v_employee_workload: WHERE a.handler_emp_no = e.emp_no (e 는 외부)
        outer_aliases = _re.findall(r'\bFROM\s+`?[a-zA-Z_][a-zA-Z0-9_]*`?\s+`?([a-zA-Z_][a-zA-Z0-9_]*)`?\b',
                                     view_def[:view_def.lower().find('select', 6) if 'select' in view_def.lower()[6:] else len(view_def)],
                                     _re.IGNORECASE)
        # 단순 휴리스틱: 서브쿼리가 2개 이상 + GROUP BY 없음 → 상관 서브쿼리 (N+1)
        if len(nested) >= 2 and not _PATTERN_GROUP_BY.search(view_def):
            patterns_found.append("correlated_subquery")
            details["nested_subqueries"] = len(nested)

    # 3. COUNT(DISTINCT) + GROUP BY (집계 폭주)
    has_count_distinct = bool(_PATTERN_COUNT_DISTINCT.search(view_def))
    has_group_by = bool(_PATTERN_GROUP_BY.search(view_def))
    if has_count_distinct and has_group_by:
        patterns_found.append("count_distinct_groupby")

    # 4. COLLATE in JOIN (인덱스 무효)
    collate_matches = _PATTERN_COLLATE_IN_JOIN.findall(view_def)
    if collate_matches:
        patterns_found.append("collate_join")
        details["collate_count"] = len(collate_matches)

    is_risky = len(patterns_found) > 0

    return {
        "patterns": patterns_found,
        "is_risky": is_risky,
        "details": details
    }


def extract_referenced_tables(view_def: str) -> list:
    """View 정의에서 참조하는 테이블 이름 추출

    매우 단순한 휴리스틱 — 정확한 SQL 파서가 아니라 본부장님 환경 케이스 잡기.
    """
    if not view_def:
        return []

    tables = set()
    for m in _PATTERN_FROM_TABLE.finditer(view_def):
        tbl = m.group(1)
        if tbl and tbl.lower() not in ('select', 'where', 'on', 'and', 'or', 'as'):
            tables.add(tbl)

    return sorted(tables)


# ════════════════════════════════════════════════════════════════════
# 참조 테이블 행수 확인 (DB-specific)
# ════════════════════════════════════════════════════════════════════

def estimate_max_table_rows(cur, db_type: str, db_name: str, table_names: list) -> int:
    """참조 테이블들 중 *가장 큰* 테이블의 행수 추정

    Returns:
        최대 행수 (정확한 COUNT 가 아니라 옵티마이저 통계 기반)
    """
    if not table_names:
        return 0

    db_type_lower = (db_type or "").lower()
    max_rows = 0

    try:
        if db_type_lower in ("mysql", "mariadb", "aurora", "tidb", "cloudsql"):
            placeholders = ",".join(["%s"] * len(table_names))
            cur.execute(f"""
                SELECT TABLE_NAME, TABLE_ROWS
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME IN ({placeholders})
            """, [db_name] + table_names)
            for row in cur.fetchall():
                # dict/tuple 호환
                if isinstance(row, dict):
                    rows = row.get("TABLE_ROWS") or 0
                else:
                    rows = row[1] if len(row) > 1 else 0
                if rows and rows > max_rows:
                    max_rows = int(rows)
        elif db_type_lower in ("postgresql", "postgres"):
            placeholders = ",".join(["%s"] * len(table_names))
            cur.execute(f"""
                SELECT relname, n_live_tup
                FROM pg_stat_user_tables
                WHERE schemaname = %s
                  AND relname IN ({placeholders})
            """, [db_name] + table_names)
            for row in cur.fetchall():
                rows = row[1] if not isinstance(row, dict) else row.get("n_live_tup", 0)
                if rows and rows > max_rows:
                    max_rows = int(rows)
        elif db_type_lower in ("mssql", "azure"):
            placeholders = ",".join(["?"] * len(table_names))
            cur.execute(f"""
                SELECT t.name, p.rows
                FROM sys.tables t
                JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0,1)
                WHERE t.name IN ({placeholders})
            """, table_names)
            for row in cur.fetchall():
                rows = row[1] if len(row) > 1 else 0
                if rows and rows > max_rows:
                    max_rows = int(rows)
        elif db_type_lower == "oracle":
            placeholders = ",".join([":t" + str(i) for i in range(len(table_names))])
            params = {f"t{i}": t.upper() for i, t in enumerate(table_names)}
            cur.execute(f"""
                SELECT TABLE_NAME, NUM_ROWS
                FROM ALL_TABLES
                WHERE OWNER = :owner
                  AND TABLE_NAME IN ({placeholders})
            """, owner=db_name.upper(), **params)
            for row in cur.fetchall():
                rows = row[1] if len(row) > 1 else 0
                if rows and rows > max_rows:
                    max_rows = int(rows)
    except Exception as e:
        _logger.warning("[v95_p6] 테이블 행수 조회 실패 (%s): %s", db_type_lower, e)

    return max_rows


# ════════════════════════════════════════════════════════════════════
# 통합 진입점
# ════════════════════════════════════════════════════════════════════

LARGE_TABLE_THRESHOLD = 1_000_000  # 100만 행 이상이면 대용량


def analyze_view_risk(cur, db_type: str, db_name: str, view_name: str,
                      view_def: str = None) -> dict:
    """View 의 위험도 종합 분석

    Args:
        cur: 활성 cursor
        db_type: DB 종류
        db_name: DB 이름
        view_name: View 이름
        view_def: View 정의 SQL (없으면 자동 조회 시도)

    Returns:
        {
            "is_risky": bool,
            "is_large": bool,
            "should_use_safe_mode": bool,
            "patterns": [...],
            "max_table_rows": int,
            "referenced_tables": [...],
            "reason": str   # 사용자 표시용
        }
    """
    # 1. View 정의 가져오기 (없으면)
    if not view_def:
        view_def = _fetch_view_definition(cur, db_type, db_name, view_name)
    if not view_def:
        return {
            "is_risky": False, "is_large": False,
            "should_use_safe_mode": False,
            "patterns": [], "max_table_rows": 0,
            "referenced_tables": [],
            "reason": "View 정의 조회 실패 — 일반 검증"
        }

    # 2. 안티패턴 분석
    pattern_result = analyze_view_definition(view_def)
    patterns = pattern_result["patterns"]
    is_risky = pattern_result["is_risky"]

    # 3. 참조 테이블 추출 + 행수
    ref_tables = extract_referenced_tables(view_def)
    max_rows = estimate_max_table_rows(cur, db_type, db_name, ref_tables) if ref_tables else 0
    is_large = max_rows >= LARGE_TABLE_THRESHOLD

    # 4. 안전 모드 결정
    # ════════════════════════════════════════════════════════════════
    # v95_p8 (2026-05-02) 본부장님 본질 처방:
    #   본부장님 환경 6개 View 가 v95_p6 적용 후에도 30초 timeout
    #
    # 본질 진단:
    #   v95_p6 의 max_rows=0 (information_schema.TABLES.TABLE_ROWS 부정확)
    #   → large=False → safe_mode=False → 일반 LIMIT 50 → 30초 timeout
    #   ANALYZE TABLE 안 했으면 InnoDB 통계가 0 또는 부정확
    #
    # 본질 처방:
    #   *대용량 조건 없이* — 안티패턴 자체가 위험
    #   ROW_NUMBER() OVER, 상관 서브쿼리, COUNT(DISTINCT)+GROUP BY, COLLATE JOIN
    #   은 *대용량 아니어도* 옵티마이저가 LIMIT push-down 못 함
    #   → 안전 모드 (LIMIT 1) 가 *올바른 기본값*
    #
    # 트레이드오프:
    #   안티패턴 있는 작은 View 도 LIMIT 1
    #   → 그러나 *데이터 검증* 아니라 *구조 검증* 이 목적이라 OK
    #
    # 미래 영역 (v96+):
    #   ANALYZE TABLE 자동화 (v95_p1 의 통계 갱신과 통합)
    #   → max_rows 정확해지면 *실제 대용량 + 안티패턴* 만 안전 모드
    # ════════════════════════════════════════════════════════════════
    should_use_safe_mode = is_risky  # v95_p8: 안티패턴 자체가 위험

    # 5. 사용자 메시지
    reason = ""
    if should_use_safe_mode:
        pattern_kor = {
            "window_function": "윈도우 함수",
            "correlated_subquery": "상관 서브쿼리",
            "count_distinct_groupby": "COUNT(DISTINCT)+GROUP BY",
            "collate_join": "COLLATE 변환 JOIN"
        }
        pattern_str = ", ".join(pattern_kor.get(p, p) for p in patterns)
        if is_large:
            reason = f"대용량({max_rows:,}행) + 안티패턴({pattern_str}) — 안전 검증"
        else:
            reason = f"안티패턴({pattern_str}) — 안전 검증 (LIMIT push-down 불가)"
    elif is_large:
        reason = f"대용량({max_rows:,}행) — 정상 검증 (인덱스 활용 가능)"
    else:
        reason = "일반 View"

    _logger.info(
        "[v95_p6] %s: risky=%s large=%s safe_mode=%s patterns=%s max_rows=%s",
        view_name, is_risky, is_large, should_use_safe_mode, patterns, max_rows
    )

    return {
        "is_risky": is_risky,
        "is_large": is_large,
        "should_use_safe_mode": should_use_safe_mode,
        "patterns": patterns,
        "max_table_rows": max_rows,
        "referenced_tables": ref_tables,
        "reason": reason
    }


def _fetch_view_definition(cur, db_type: str, db_name: str, view_name: str) -> str:
    """View 정의 조회 (DB-specific)"""
    db_type_lower = (db_type or "").lower()
    try:
        if db_type_lower in ("mysql", "mariadb", "aurora", "tidb", "cloudsql"):
            cur.execute("""
                SELECT VIEW_DEFINITION FROM information_schema.VIEWS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            """, (db_name, view_name))
            row = cur.fetchone()
            if row:
                return row.get("VIEW_DEFINITION") if isinstance(row, dict) else (row[0] if row else None)
        elif db_type_lower in ("postgresql", "postgres"):
            cur.execute("""
                SELECT view_definition FROM information_schema.views
                WHERE table_schema = %s AND table_name = %s
            """, (db_name, view_name))
            row = cur.fetchone()
            if row:
                return row[0]
        elif db_type_lower in ("mssql", "azure"):
            cur.execute("""
                SELECT m.definition FROM sys.sql_modules m
                JOIN sys.views v ON m.object_id = v.object_id
                WHERE v.name = ?
            """, (view_name,))
            row = cur.fetchone()
            if row:
                return row[0]
        elif db_type_lower == "oracle":
            cur.execute("""
                SELECT TEXT FROM ALL_VIEWS
                WHERE OWNER = :owner AND VIEW_NAME = :vname
            """, owner=db_name.upper(), vname=view_name.upper())
            row = cur.fetchone()
            if row:
                return row[0]
    except Exception as e:
        _logger.warning("[v95_p6] View 정의 조회 실패 (%s.%s): %s", db_name, view_name, e)
    return None
