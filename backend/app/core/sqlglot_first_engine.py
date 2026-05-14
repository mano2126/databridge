"""
DataBridge SQLGlot 우선 진입 엔진 — hotfix_026
====================================================

본부장님 12번째 본질 통찰 (2026-05-11 오후):
  "다운받은 모듈을 활용해서 질을 높이는게 목적 아냐?"

본부장님 환경 PoC 입증 (오전):
  SQLGlot 직접 변환 — 5/8 객체 성공
  - vJobCandidate, vJobCandidateEmployment, vAdditionalContactInfo,
    vProductModelCatalogDescription, vSalesPersonSalesByFiscalYears

처방: 큰 객체 (>2KB) 는 AI 호출 전에 SQLGlot 우선 시도.
  - 성공: AI 호출 0회로 변환 완료
  - 실패: 다음 Layer (AI) 로 위임

본부장님 4-Layer 정면:
  Layer 1: KB 매칭
  Layer 2: Rule Engine (TVF — hotfix_023)
  Layer 3: ⭐ SQLGlot 우선 (이 모듈 — hotfix_026)
  Layer 4: AI fallback
"""
from __future__ import annotations
import re
import time
import logging
from typing import Optional, Tuple

_log = logging.getLogger("databridge.sqlglot_first_engine")

try:
    import sqlglot
    _SQLGLOT_AVAILABLE = True
except ImportError:
    _SQLGLOT_AVAILABLE = False


# 본부장님 환경 검증된 전처리 규칙
def preprocess_tsql(sql: str) -> Tuple[str, list]:
    """T-SQL 전용 키워드 제거 — SQLGlot 가 못 다루는 것들."""
    fixes = []
    result = sql
    
    # OPTION (MAXRECURSION N) — T-SQL 재귀 제한 (오전 PoC 에서 발견)
    n = len(re.findall(r'OPTION\s*\(\s*MAXRECURSION\s+\d+\s*\)', result, re.IGNORECASE))
    if n:
        result = re.sub(r'OPTION\s*\(\s*MAXRECURSION\s+\d+\s*\)', '', result, flags=re.IGNORECASE)
        fixes.append(f"OPTION(MAXRECURSION) 제거 ({n}건)")
    
    # SET NOCOUNT ON — T-SQL 전용
    n = len(re.findall(r'\bSET\s+NOCOUNT\s+ON\s*;?', result, re.IGNORECASE))
    if n:
        result = re.sub(r'\bSET\s+NOCOUNT\s+ON\s*;?', '', result, flags=re.IGNORECASE)
        fixes.append(f"SET NOCOUNT ON 제거 ({n}건)")
    
    return result.strip(), fixes


def is_large_object(sql: str, threshold: int = 1500) -> bool:
    """SQLGlot 우선 진입 대상인가? (큰 객체 또는 복잡 패턴)"""
    if len(sql) >= threshold:
        return True
    # PIVOT, CTE, XML 등 SQLGlot 우선 검토 가치 있는 패턴
    for pat in (r'\bPIVOT\b', r'\bWITH\s+RECURSIVE\b',
                r'\bCROSS\s+APPLY\b', r'\bOUTER\s+APPLY\b'):
        if re.search(pat, sql, re.IGNORECASE):
            return True
    return False


def try_sqlglot_convert(sql: str, obj_type: str = "", obj_name: str = "") -> Optional[dict]:
    """SQLGlot 우선 변환 시도.
    
    Returns:
        성공: {'final_sql': ..., 'elapsed_ms': ..., 'notes': ..., 'preprocess_fixes': ...}
        실패: None
    """
    if not _SQLGLOT_AVAILABLE:
        return None
    
    t0 = time.monotonic()
    
    # 전처리
    preprocessed, pre_fixes = preprocess_tsql(sql)
    
    try:
        # SQLGlot 변환
        result_list = sqlglot.transpile(
            preprocessed,
            read='tsql',
            write='mysql',
            pretty=False,
        )
        if not result_list:
            return None
        
        converted = result_list[0]
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        
        # ════════════════════════════════════════════════════════════════
        # v95_p107 hotfix_028 (2026-05-11 본부장님 13번째 본질 통찰):
        #   "SQLGlot 출력을 진짜 검증 후 KB 자산화. KB 가 살아있는 자산"
        #
        # SQLGlot 가 "Falling back to parsing as a 'Command'" 케이스:
        #   → MSSQL 원본을 그대로 반환 (변환 안 함)
        #   → ratio=0.98 같은 비율로 변환된 것처럼 보임
        #   → 그러나 MySQL 실행 시 1064 syntax error
        #
        # 본질 검증: MSSQL 잔재 패턴 검사 → 잔재 있으면 변환 실패로 판정
        # ════════════════════════════════════════════════════════════════
        mssql_residues = []
        # 1. T-SQL 변수 @name (MySQL 은 함수 파라미터에 @ 안 씀)
        if re.search(r'@\w+\s+\[?(int|varchar|nvarchar|datetime|char|bigint|bit|money)\b', converted, re.IGNORECASE):
            mssql_residues.append("@변수 정의")
        # 2. [Schema].[Object] T-SQL bracket 식별자
        if re.search(r'\[\w+\]\s*\.\s*\[\w+\]', converted):
            mssql_residues.append("[Schema].[Object]")
        # 3. T-SQL DDL 키워드 AS BEGIN (MySQL 은 BEGIN 만)
        if re.search(r'\bAS\s*\r?\n?\s*BEGIN\b', converted, re.IGNORECASE):
            mssql_residues.append("AS BEGIN (T-SQL)")
        # 4. OBJECT_ID DROP guard (TRIGGER 흔함)
        if re.search(r'IF\s+OBJECT_ID\s*\(\s*N?\'', converted, re.IGNORECASE):
            mssql_residues.append("IF OBJECT_ID DROP guard")
        # 5. CREATE PROCEDURE/TRIGGER/VIEW [name] 같은 bracket
        if re.search(r'CREATE\s+(?:PROCEDURE|TRIGGER|VIEW|FUNCTION)\s+\[', converted, re.IGNORECASE):
            mssql_residues.append("CREATE [bracket]")
        # 6. N'string' literal prefix
        if re.search(r"\bN'", converted):
            mssql_residues.append("N'string'")
        # 7. SET NOCOUNT ON (T-SQL 전용)
        if re.search(r'\bSET\s+NOCOUNT\s+ON\b', converted, re.IGNORECASE):
            mssql_residues.append("SET NOCOUNT ON")
        
        if mssql_residues:
            _log.info(
                "[sqlglot_first] %s [%s] MSSQL 잔재 검출 — 변환 실패로 판정 "
                "(잔재: %s) → AI 로 위임",
                obj_type, obj_name, mssql_residues,
            )
            return None
        
        # 결과 검증 — 너무 짧으면 (원본의 30% 미만) 실패로 간주
        ratio = len(converted) / len(sql) if sql else 0
        if ratio < 0.30:
            _log.warning(
                "[sqlglot_first] %s [%s] 변환 결과 비정상 짧음 (ratio=%.2f) — 실패 처리",
                obj_type, obj_name, ratio,
            )
            return None
        
        return {
            'final_sql': converted,
            'elapsed_ms': elapsed_ms,
            'ratio': ratio,
            'preprocess_fixes': pre_fixes,
            'notes': (
                f"SQLGlot 우선 변환 + 본부장님 13번째 본질 (MSSQL 잔재 검증 통과) — "
                f"{elapsed_ms}ms, ratio={ratio:.2f}, 전처리 {len(pre_fixes)}건"
            ),
        }
    except Exception as e:
        _log.info(
            "[sqlglot_first] %s [%s] SQLGlot 변환 실패 (%s) — AI 로 위임",
            obj_type, obj_name, type(e).__name__,
        )
        return None


# ════════════════════════════════════════════════════════════════
# 통계
# ════════════════════════════════════════════════════════════════
_stats = {
    'total_attempts': 0,
    'total_success': 0,
    'total_elapsed_ms': 0,
    'by_kind': {},
}


def get_stats() -> dict:
    return dict(_stats)


def _record(success: bool, elapsed_ms: int, obj_type: str):
    _stats['total_attempts'] += 1
    if success:
        _stats['total_success'] += 1
    _stats['total_elapsed_ms'] += elapsed_ms
    key = (obj_type or '?').upper()
    _stats['by_kind'][key] = _stats['by_kind'].get(key, 0) + 1


# ════════════════════════════════════════════════════════════════
# 외부 진입점
# ════════════════════════════════════════════════════════════════
def try_sqlglot_first(src_ddl: str, obj_type: str, obj_name: str,
                      error_hint: str = "") -> Optional[dict]:
    """schema._ai_convert_ddl 에서 호출.
    
    조건:
      - 큰 객체 (>= 1.5KB) 또는 PIVOT/CTE/CROSS APPLY 패턴
      - SQLGlot 사용 가능
      - error_hint 없음 (첫 시도) 또는 hint 가 SQLGlot 한계 아님
    
    Returns:
      성공: dict, 실패: None
    """
    if not src_ddl or not _SQLGLOT_AVAILABLE:
        return None
    
    # 큰 객체 또는 복잡 패턴만 대상
    if not is_large_object(src_ddl):
        return None
    
    # 진입 로그 (본부장님 모토 #13 정면)
    _log.info(
        "[v95_p107-SQLGLOT-ATTEMPT] %s [%s] size=%d sqlglot=%s",
        obj_type, obj_name, len(src_ddl), _SQLGLOT_AVAILABLE,
    )
    
    result = try_sqlglot_convert(src_ddl, obj_type, obj_name)
    _record(result is not None, result.get('elapsed_ms', 0) if result else 0, obj_type)
    
    if result:
        _log.info(
            "[v95_p107-SQLGLOT-OK] %s [%s] %s",
            obj_type, obj_name, result['notes'],
        )
    return result
