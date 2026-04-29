"""
pii_sampler.py — Phase F-1f-1 (2026-04-25)

PII 탐지를 위해 소스 DB 에서 안전하게 샘플 데이터를 가져오는 모듈.

설계 원칙:
  1. 안전 (Safety) 우선
     - 항상 LIMIT 적용 (기본 100건)
     - 큰 컬럼 (TEXT, BLOB, BINARY) 은 LEFT(N) 으로 절단
     - 타임아웃 강제 적용 (기본 10초)
     - 대상 테이블 전체 스캔 방지 (TOP/LIMIT)

  2. 성능 (Performance)
     - 컬럼별 개별 쿼리 X (한 번에 SELECT)
     - 무거운 컬럼 자동 제외
     - 결과 메모리 절약 위해 정수/날짜는 그대로, 문자열만 샘플링

  3. 격리 (Isolation)
     - 별도 connection 사용 (이관 작업과 분리)
     - read-only 보장 (SELECT 만)
     - 시작 후 즉시 닫기

  4. 보안 (Security)
     - 샘플 데이터는 메모리만, 디스크 X
     - 응답에 컬럼명 + 일부 값만 (전체 row 안 나감)

지원 DB:
  - MySQL / MariaDB / Aurora / TiDB
  - MSSQL / Azure
  - PostgreSQL

향후 추가:
  - Oracle, DB2 (필요 시)
"""

from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from contextlib import contextmanager

_log = logging.getLogger("databridge.pii.sampler")


# ════════════════════════════════════════════════════════════════════════════
# 설정 / 상수
# ════════════════════════════════════════════════════════════════════════════

DEFAULT_SAMPLE_COUNT = 100      # 컬럼당 샘플 row 수
DEFAULT_TIMEOUT_SEC = 10        # 쿼리 타임아웃
MAX_COL_VALUE_LENGTH = 200      # 단일 값 최대 길이 (이상 절단)
HEAVY_TYPE_KEYWORDS = (         # 무거운 컬럼 자동 제외
    'TEXT', 'BLOB', 'CLOB', 'IMAGE', 'BINARY', 'VARBINARY',
    'XML', 'JSON', 'GEOGRAPHY', 'GEOMETRY', 'NTEXT',
)
MAX_HEAVY_COL_LENGTH = 50       # 무거운 컬럼 강제 절단 길이


# ════════════════════════════════════════════════════════════════════════════
# 내부 헬퍼
# ════════════════════════════════════════════════════════════════════════════

def _is_heavy_column(col_type: str) -> bool:
    """무거운 타입 컬럼 (TEXT, BLOB 등) 여부"""
    if not col_type:
        return False
    upper = col_type.upper()
    return any(kw in upper for kw in HEAVY_TYPE_KEYWORDS)


def _sanitize_value(value: Any) -> Any:
    """
    샘플 값 정제:
      - 너무 긴 문자열은 절단
      - bytes 는 hex 문자열로
      - decimal 등은 str() 로
    """
    if value is None:
        return None
    
    if isinstance(value, bytes):
        try:
            # 텍스트로 디코딩 시도
            value = value.decode('utf-8', errors='replace')
        except Exception:
            return f"<bytes:{len(value)}>"
    
    if isinstance(value, str):
        if len(value) > MAX_COL_VALUE_LENGTH:
            return value[:MAX_COL_VALUE_LENGTH] + '...'
        return value
    
    # int, float, bool — 그대로
    if isinstance(value, (int, float, bool)):
        return value
    
    # datetime, date, decimal 등 — str() 로 변환
    return str(value)[:MAX_COL_VALUE_LENGTH]


def _quote_identifier(name: str, db_type: str) -> str:
    """DB 별 식별자 인용 처리 (SQL injection 방지)"""
    if not name or not isinstance(name, str):
        return ""
    
    # 안전한 식별자만 허용 (숫자/문자/언더스코어/한글 등)
    # 따옴표 / 백틱 / 세미콜론 / 공백 등은 거부
    if any(c in name for c in '`"\';\\\n\r'):
        raise ValueError(f"Unsafe identifier: {name!r}")
    
    db = db_type.lower()
    if db in ('mysql', 'aurora', 'mariadb', 'tidb', 'cloudsql'):
        return f"`{name}`"
    elif db in ('mssql', 'azure', 'sqlserver'):
        return f"[{name}]"
    elif db in ('postgresql', 'postgres'):
        return f'"{name}"'
    else:
        return f"`{name}`"  # default


def _build_sample_sql(
    db_type: str,
    table_name: str,
    columns: List[Dict[str, Any]],
    sample_count: int,
) -> Tuple[str, List[str]]:
    """
    샘플 SELECT SQL 생성.
    
    Returns:
        (sql, included_column_names)
    """
    # 컬럼 select 절 빌드
    select_parts = []
    included_cols = []
    
    for col in columns:
        col_name = col.get('name') or col.get('column_name', '')
        col_type = col.get('type', '') or ''
        if not col_name:
            continue
        
        try:
            quoted = _quote_identifier(col_name, db_type)
        except ValueError as e:
            _log.warning(f"[Sampler] 안전하지 않은 컬럼명 스킵: {e}")
            continue
        
        if _is_heavy_column(col_type):
            # 무거운 컬럼은 강제 절단
            if db_type.lower() in ('mssql', 'azure', 'sqlserver'):
                expr = f"LEFT(CAST({quoted} AS NVARCHAR(MAX)), {MAX_HEAVY_COL_LENGTH})"
            elif db_type.lower() in ('postgresql', 'postgres'):
                expr = f"LEFT({quoted}::text, {MAX_HEAVY_COL_LENGTH})"
            else:
                expr = f"LEFT({quoted}, {MAX_HEAVY_COL_LENGTH})"
            select_parts.append(f"{expr} AS {quoted}")
        else:
            select_parts.append(quoted)
        
        included_cols.append(col_name)
    
    if not select_parts:
        return "", []
    
    select_clause = ", ".join(select_parts)
    
    # 테이블명 처리 (스키마 포함 가능: "schema.table")
    table_quoted = _quote_table(table_name, db_type)
    
    # DB 별 LIMIT 구문
    db = db_type.lower()
    if db in ('mssql', 'azure', 'sqlserver'):
        sql = f"SELECT TOP {int(sample_count)} {select_clause} FROM {table_quoted}"
    elif db in ('postgresql', 'postgres'):
        sql = f"SELECT {select_clause} FROM {table_quoted} LIMIT {int(sample_count)}"
    else:  # MySQL family
        sql = f"SELECT {select_clause} FROM {table_quoted} LIMIT {int(sample_count)}"
    
    return sql, included_cols


def _quote_table(table_name: str, db_type: str) -> str:
    """테이블명 인용 (스키마 . 테이블 분리)"""
    if not table_name:
        raise ValueError("table_name is empty")
    
    # 스키마 . 테이블 분리
    parts = table_name.split('.')
    if len(parts) == 1:
        return _quote_identifier(parts[0], db_type)
    elif len(parts) == 2:
        schema = _quote_identifier(parts[0], db_type)
        tbl = _quote_identifier(parts[1], db_type)
        return f"{schema}.{tbl}"
    else:
        raise ValueError(f"Invalid table name: {table_name}")


# ════════════════════════════════════════════════════════════════════════════
# DB 별 샘플링 함수
# ════════════════════════════════════════════════════════════════════════════

def _sample_mysql(
    profile: Dict[str, Any],
    table_name: str,
    columns: List[Dict[str, Any]],
    sample_count: int,
    timeout: int,
) -> Dict[str, List[Any]]:
    """MySQL 패밀리 샘플링"""
    import pymysql
    
    sql, included_cols = _build_sample_sql(
        profile['db_type'], table_name, columns, sample_count
    )
    if not sql:
        return {}
    
    conn = pymysql.connect(
        host=profile['host'], port=int(profile['port']),
        user=profile['username'], password=profile['password'],
        database=profile['database'], charset='utf8mb4',
        connect_timeout=timeout, read_timeout=timeout,
    )
    
    try:
        cur = conn.cursor()
        # 세션 타임아웃 (안전망)
        try:
            cur.execute(f"SET SESSION MAX_EXECUTION_TIME={timeout * 1000}")
        except Exception:
            pass  # 일부 MariaDB 미지원
        
        cur.execute(sql)
        rows = cur.fetchall()
    finally:
        conn.close()
    
    return _rows_to_column_dict(rows, included_cols)


def _sample_mssql(
    profile: Dict[str, Any],
    table_name: str,
    columns: List[Dict[str, Any]],
    sample_count: int,
    timeout: int,
) -> Dict[str, List[Any]]:
    """MSSQL / Azure SQL 샘플링"""
    from app.core.db_conn import make_mssql_conn
    
    sql, included_cols = _build_sample_sql(
        profile['db_type'], table_name, columns, sample_count
    )
    if not sql:
        return {}
    
    conn = make_mssql_conn(
        profile['host'], int(profile['port']),
        profile['username'], profile['password'],
        profile['database'], timeout=timeout,
    )
    
    try:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
    finally:
        conn.close()
    
    return _rows_to_column_dict(rows, included_cols)


def _sample_postgres(
    profile: Dict[str, Any],
    table_name: str,
    columns: List[Dict[str, Any]],
    sample_count: int,
    timeout: int,
) -> Dict[str, List[Any]]:
    """PostgreSQL 샘플링"""
    import psycopg2
    
    sql, included_cols = _build_sample_sql(
        profile['db_type'], table_name, columns, sample_count
    )
    if not sql:
        return {}
    
    conn = psycopg2.connect(
        host=profile['host'], port=int(profile['port']),
        user=profile['username'], password=profile['password'],
        dbname=profile['database'], connect_timeout=timeout,
    )
    
    try:
        # statement_timeout 설정
        cur = conn.cursor()
        cur.execute(f"SET statement_timeout = {timeout * 1000}")
        cur.execute(sql)
        rows = cur.fetchall()
    finally:
        conn.close()
    
    return _rows_to_column_dict(rows, included_cols)


def _rows_to_column_dict(rows: List[Tuple], col_names: List[str]) -> Dict[str, List[Any]]:
    """
    row 튜플 리스트 → 컬럼별 dict.
    
    [(1, 'a'), (2, 'b')]  with cols ['id', 'name']
    → {'id': [1, 2], 'name': ['a', 'b']}
    """
    result: Dict[str, List[Any]] = {col: [] for col in col_names}
    
    for row in rows:
        for i, col_name in enumerate(col_names):
            if i < len(row):
                result[col_name].append(_sanitize_value(row[i]))
    
    return result


# ════════════════════════════════════════════════════════════════════════════
# 메인 API
# ════════════════════════════════════════════════════════════════════════════

def fetch_sample_data(
    profile: Dict[str, Any],
    table_name: str,
    columns: List[Dict[str, Any]],
    sample_count: int = DEFAULT_SAMPLE_COUNT,
    timeout: int = DEFAULT_TIMEOUT_SEC,
) -> Dict[str, Any]:
    """
    소스 DB 에서 샘플 데이터 fetch.
    
    Args:
        profile: 복호화된 프로파일 dict
                 {'db_type': 'mysql', 'host': ..., 'port': ..., 
                  'username': ..., 'password': ..., 'database': ...}
        table_name: 'schema.table' 또는 'table'
        columns: [{'name': 'col1', 'type': 'VARCHAR'}, ...]
        sample_count: 가져올 row 수 (기본 100)
        timeout: 쿼리 타임아웃 초 (기본 10)
    
    Returns:
        {
            'success': True,
            'sample_data': {col_name: [v1, v2, ...]},
            'rows_fetched': 73,
            'columns_sampled': 12,
            'columns_skipped': ['big_text_col'],   # 안전상 스킵된 것
            'duration_ms': 234,
            'error': None,
        }
    """
    if not profile or not profile.get('db_type'):
        return _error_result("프로파일 정보 누락")
    
    if not table_name or not columns:
        return _error_result("테이블명 또는 컬럼 정보 누락")
    
    db_type = profile['db_type'].lower()
    start = time.monotonic()
    
    try:
        if db_type in ('mysql', 'aurora', 'cloudsql', 'tidb', 'mariadb'):
            sample_data = _sample_mysql(profile, table_name, columns, sample_count, timeout)
        elif db_type in ('mssql', 'azure', 'sqlserver'):
            sample_data = _sample_mssql(profile, table_name, columns, sample_count, timeout)
        elif db_type in ('postgresql', 'postgres'):
            sample_data = _sample_postgres(profile, table_name, columns, sample_count, timeout)
        else:
            return _error_result(f"지원되지 않는 DB 타입: {db_type}")
    
    except Exception as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        _log.warning(f"[Sampler] {table_name} 샘플링 실패: {e}")
        return {
            'success': False,
            'sample_data': {},
            'rows_fetched': 0,
            'columns_sampled': 0,
            'columns_skipped': [],
            'duration_ms': duration_ms,
            'error': str(e)[:200],
        }
    
    duration_ms = int((time.monotonic() - start) * 1000)
    
    # 통계
    rows_fetched = max((len(v) for v in sample_data.values()), default=0)
    requested_cols = {c.get('name') or c.get('column_name', '') for c in columns}
    sampled_cols = set(sample_data.keys())
    skipped = sorted(requested_cols - sampled_cols)
    
    return {
        'success': True,
        'sample_data': sample_data,
        'rows_fetched': rows_fetched,
        'columns_sampled': len(sampled_cols),
        'columns_skipped': skipped,
        'duration_ms': duration_ms,
        'error': None,
    }


def fetch_samples_for_tables(
    profile: Dict[str, Any],
    tables: List[Dict[str, Any]],
    sample_count: int = DEFAULT_SAMPLE_COUNT,
    timeout: int = DEFAULT_TIMEOUT_SEC,
) -> Dict[str, Dict[str, Any]]:
    """
    여러 테이블 일괄 샘플링.
    
    Args:
        tables: [{'table_name': 'a.b', 'columns': [...]}, ...]
    
    Returns:
        {table_name: fetch_sample_data 결과}
    """
    results = {}
    for tbl in tables:
        table_name = tbl.get('table_name', '')
        cols = tbl.get('columns', [])
        if not table_name:
            continue
        
        results[table_name] = fetch_sample_data(
            profile, table_name, cols, sample_count, timeout
        )
    
    return results


def _error_result(msg: str) -> Dict[str, Any]:
    return {
        'success': False,
        'sample_data': {},
        'rows_fetched': 0,
        'columns_sampled': 0,
        'columns_skipped': [],
        'duration_ms': 0,
        'error': msg,
    }


# ════════════════════════════════════════════════════════════════════════════
# 통계
# ════════════════════════════════════════════════════════════════════════════

def summarize_sampling(
    results: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """샘플링 결과 종합 요약 (audit/log 용)"""
    total_tables = len(results)
    success_tables = sum(1 for r in results.values() if r.get('success'))
    total_rows = sum(r.get('rows_fetched', 0) for r in results.values())
    total_cols = sum(r.get('columns_sampled', 0) for r in results.values())
    skipped_cols = sum(len(r.get('columns_skipped', [])) for r in results.values())
    total_duration = sum(r.get('duration_ms', 0) for r in results.values())
    errors = [
        {'table': t, 'error': r.get('error')}
        for t, r in results.items() if not r.get('success')
    ]
    
    return {
        'total_tables': total_tables,
        'success_tables': success_tables,
        'failed_tables': total_tables - success_tables,
        'total_rows_sampled': total_rows,
        'total_columns_sampled': total_cols,
        'columns_skipped': skipped_cols,
        'total_duration_ms': total_duration,
        'errors': errors,
    }
