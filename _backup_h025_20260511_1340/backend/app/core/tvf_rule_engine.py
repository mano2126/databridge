"""
DataBridge TVF Rule Engine — 본부장님 본질 처방 (hotfix_023)
==================================================================

본부장님 본질 통찰 6번째 (2026-05-10):
  "SQLGlot 에 너무 디펜던트 해지는 거 아닐까?"
본부장님 통찰 5번째 (2026-05-11 PoC 입증):
  "Gemma 와의 통신 문제 본질 — 토큰 한도 + 무한 반복"

처방: MSSQL TVF (RETURNS @x TABLE) → MySQL PROCEDURE 결정적 변환
  - AI 호출 0회
  - 0.05초/객체 (Gemma 7분 30초 대비 9,000배)
  - 결정적 (같은 입력 → 항상 같은 출력)
  - SQLGlot 의 좁은 활용 (컬럼/SELECT 만)

본부장님 PoC 검증 (2026-05-11 ~08:00):
  ✓ ufnGetContactInformation 변환 성공
  ✓ MySQL CREATE PROCEDURE 통과
  ✓ CALL dbo_ufnGetContactInformation(1) 정상 결과
  ✓ 게이트 8 (VARCHAR(N NULL) 등) 완전 통과
  ✓ 본부장님 KB 깨짐 본질 해결

아키텍처 (본부장님 4-Layer 의 Layer 2):
  - Layer 1 (KB)        → 이미 변환된 객체 즉시 매칭
  - Layer 2 (이 파일)   → TVF 같은 정형 패턴 결정적 변환
  - Layer 3 (SQLGlot)   → 컬럼/SELECT 등 좁은 보조
  - Layer 4 (AI)        → 정말 복잡한 본체만
"""
from __future__ import annotations
import re
import time
import logging
from typing import Optional

_log = logging.getLogger("databridge.tvf_rule_engine")

# SQLGlot 안전 import (없어도 동작 가능, 단 컬럼 변환은 fallback)
try:
    import sqlglot
    _SQLGLOT_AVAILABLE = True
except ImportError:
    _SQLGLOT_AVAILABLE = False
    _log.warning("[tvf_rule_engine] sqlglot 미설치 — 컬럼 변환은 정규식 fallback")


# ════════════════════════════════════════════════════════════════
# 패턴 감지 — TVF 여부 확인
# ════════════════════════════════════════════════════════════════
def is_tvf(src_ddl: str) -> bool:
    """TVF (Multi-statement Table-Valued Function) 패턴 감지.
    
    조건: RETURNS @변수명 TABLE (...) 형식
    예: RETURNS @retContactInformation TABLE (cols...)
    """
    if not src_ddl:
        return False
    return bool(re.search(r'RETURNS\s+@\w+\s+TABLE\s*\(', src_ddl, re.IGNORECASE))


# ════════════════════════════════════════════════════════════════
# 본부장님 비즈니스 로직 (캐피탈사 운영 환경)
# ════════════════════════════════════════════════════════════════
def flatten_schema(text: str) -> str:
    """본부장님 환경 스키마 평탄화: [Schema].[Table] → Schema_Table
    
    예: [Person].[Person] → Person_Person
        [HumanResources].[Employee] → HumanResources_Employee
        [Sales].[Customer] → Sales_Customer
    """
    # [Schema].[Table] 형식
    text = re.sub(r'\[(\w+)\]\.\[(\w+)\]', r'\1_\2', text)
    # [Schema].Table 형식 (bracket 한쪽만)
    text = re.sub(r'\[(\w+)\]\.(\w+)', r'\1_\2', text)
    # 남은 [Identifier] → MySQL backtick
    text = re.sub(r'\[(\w+)\]', r'`\1`', text)
    return text


def normalize_params(text: str) -> str:
    """T-SQL @변수 → MySQL p_ prefix
    
    예: @PersonID → p_PersonID
    """
    return re.sub(r'@(\w+)', r'p_\1', text)


# ════════════════════════════════════════════════════════════════
# 헤더 파싱
# ════════════════════════════════════════════════════════════════
def parse_function_header(src: str) -> Optional[dict]:
    """
    Returns dict with:
      schema, name, params, returns_var, columns_raw, body_start
    """
    # CREATE FUNCTION [schema].[name](@param type, ...)
    m_head = re.search(
        r'CREATE\s+(?:OR\s+ALTER\s+)?FUNCTION\s+\[?(\w+)\]?\.\[?(\w+)\]?\s*\(\s*(.*?)\s*\)\s*RETURNS',
        src, re.IGNORECASE | re.DOTALL
    )
    if not m_head:
        return None
    
    schema = m_head.group(1)
    name = m_head.group(2)
    params_raw = m_head.group(3).strip()
    
    # 파라미터 파싱
    params = []
    if params_raw:
        for p in re.split(r',\s*(?=@)', params_raw):
            mp = re.match(r'@(\w+)\s+(.+?)(?:\s*=.*)?$', p.strip())
            if mp:
                params.append({'name': mp.group(1), 'type': mp.group(2).strip()})
    
    # RETURNS @var TABLE (cols)
    m_ret = re.search(r'RETURNS\s+@(\w+)\s+TABLE\s*\(', src, re.IGNORECASE)
    if not m_ret:
        return None
    
    # 괄호 짝 맞추기로 컬럼 부분 정확히 추출
    start = m_ret.end() - 1
    depth = 0
    end = -1
    for i in range(start, len(src)):
        if src[i] == '(':
            depth += 1
        elif src[i] == ')':
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        return None
    
    columns_raw = src[start+1:end].strip()
    body_start = end + 1
    
    return {
        'schema': schema,
        'name': name,
        'params': params,
        'returns_var': m_ret.group(1),
        'columns_raw': columns_raw,
        'body_start': body_start,
    }


# ════════════════════════════════════════════════════════════════
# 컬럼 정의 → MySQL (SQLGlot 또는 fallback)
# ════════════════════════════════════════════════════════════════
def convert_columns_via_sqlglot(cols_raw: str) -> str:
    """[FirstName] [nvarchar](50) NULL → `FirstName` VARCHAR(50) NULL
    
    본부장님 환경 PoC 검증 완료:
      ✓ VARCHAR(50) NULL 절대 안 깨짐 (Gemma 의 VARCHAR(5 NULL) 본질 해결)
    """
    # 입력에서 -- 주석 제거 (SQLGlot 이 주석을 컬럼 사이 끼워넣는 문제 방지)
    cols_clean = re.sub(r'--[^\n]*', '', cols_raw)
    
    if not _SQLGLOT_AVAILABLE:
        # fallback: 기본 정규식 변환
        return _fallback_columns(cols_clean)
    
    wrapped = f"CREATE TABLE __tmp__ (\n{cols_clean}\n)"
    try:
        converted = sqlglot.transpile(wrapped, read="tsql", write="mysql", pretty=False)[0]
        # ( ... ) 만 추출
        mc = re.search(r'\(\s*(.*?)\s*\)\s*$', converted, re.DOTALL)
        result = mc.group(1).strip() if mc else converted
        # SQLGlot 끼워넣은 /* comment */ 제거
        result = re.sub(r'/\*.*?\*/', '', result, flags=re.DOTALL)
        # 다중 공백 정리
        result = re.sub(r'\s+', ' ', result)
        # 컴마 뒤 줄바꿈 복원
        result = re.sub(r',\s*', ',\n', result).strip()
        return result
    except Exception as e:
        _log.warning("[tvf_rule_engine] SQLGlot 컬럼 변환 실패, fallback: %s", e)
        return _fallback_columns(cols_clean)


def _fallback_columns(cols_clean: str) -> str:
    """SQLGlot 없을 때 기본 변환 (덜 정확하지만 작동)"""
    result = cols_clean
    # 데이터 타입 매핑
    result = re.sub(r'\[nvarchar\]', 'VARCHAR', result, flags=re.IGNORECASE)
    result = re.sub(r'\[varchar\]', 'VARCHAR', result, flags=re.IGNORECASE)
    result = re.sub(r'\[nchar\]', 'CHAR', result, flags=re.IGNORECASE)
    result = re.sub(r'\[int\]', 'INT', result, flags=re.IGNORECASE)
    result = re.sub(r'\bnvarchar\b', 'VARCHAR', result, flags=re.IGNORECASE)
    result = re.sub(r'\bnchar\b', 'CHAR', result, flags=re.IGNORECASE)
    result = re.sub(r'\bdatetime2\b', 'DATETIME', result, flags=re.IGNORECASE)
    # [Identifier] → `Identifier`
    result = re.sub(r'\[(\w+)\]', r'`\1`', result)
    return result.strip()


# ════════════════════════════════════════════════════════════════
# 본체 분할 — IF EXISTS 블록 단위
# ════════════════════════════════════════════════════════════════
def split_body_into_blocks(body: str) -> list:
    """
    AS BEGIN ... END 안의 IF EXISTS(...) INSERT INTO @retVar ... 블록 분리.
    
    본부장님 환경 검증: ufnGetContactInformation 의 4개 블록 모두 정확 분리.
    """
    blocks = []
    i = 0
    while i < len(body):
        m = re.search(r'IF\s+EXISTS\s*\(', body[i:], re.IGNORECASE)
        if not m:
            break
        paren_start = i + m.end() - 1
        
        # 괄호 짝 맞추기
        depth = 0
        cond_end = -1
        for j in range(paren_start, len(body)):
            if body[j] == '(':
                depth += 1
            elif body[j] == ')':
                depth -= 1
                if depth == 0:
                    cond_end = j
                    break
        if cond_end == -1:
            break
        
        condition = body[paren_start+1:cond_end]
        
        # INSERT INTO @retVar ... ; 추출
        rest = body[cond_end+1:]
        m_insert = re.match(
            r'\s*INSERT\s+INTO\s+@(\w+)\s+(.*?);',
            rest, re.IGNORECASE | re.DOTALL
        )
        if m_insert:
            blocks.append({
                'kind': 'if_exists_insert',
                'condition': condition.strip(),
                'returns_var': m_insert.group(1),
                'insert_select': m_insert.group(2).strip(),
            })
            i = cond_end + 1 + m_insert.end()
        else:
            i = cond_end + 1
    
    return blocks


# ════════════════════════════════════════════════════════════════
# SELECT 변환 (정규화 + SQLGlot 보조)
# ════════════════════════════════════════════════════════════════
def convert_select_via_sqlglot(select_sql: str) -> str:
    """정적 SELECT — 스키마 평탄화 + 파라미터 정규화 + SQLGlot 변환"""
    normalized = normalize_params(flatten_schema(select_sql))
    
    if not _SQLGLOT_AVAILABLE:
        return normalized
    
    try:
        result = sqlglot.transpile(normalized, read="tsql", write="mysql", pretty=False)[0]
        return result
    except Exception:
        # SQLGlot 실패 시 정규화만 적용
        return normalized


# ════════════════════════════════════════════════════════════════
# 타입 매핑 (파라미터용)
# ════════════════════════════════════════════════════════════════
_TYPE_MAP_INLINE = [
    (r'\bnvarchar\s*\(\s*(\d+|max)\s*\)', lambda m: f"VARCHAR({m.group(1) if m.group(1) != 'max' else '65535'})"),
    (r'\bnvarchar\b',  'VARCHAR'),
    (r'\bvarchar\b',   'VARCHAR'),
    (r'\bnchar\b',     'CHAR'),
    (r'\bint\b',       'INT'),
    (r'\bbigint\b',    'BIGINT'),
    (r'\bsmallint\b',  'SMALLINT'),
    (r'\btinyint\b',   'TINYINT'),
    (r'\bbit\b',       'BOOLEAN'),
    (r'\bdatetime2\b', 'DATETIME'),
    (r'\bdatetime\b',  'DATETIME'),
    (r'\bdate\b',      'DATE'),
    (r'\bmoney\b',     'DECIMAL(19,4)'),
]

def _map_type(t: str) -> str:
    """T-SQL 타입 → MySQL 타입"""
    result = t
    for pat, repl in _TYPE_MAP_INLINE:
        if callable(repl):
            result = re.sub(pat, repl, result, flags=re.IGNORECASE)
        else:
            result = re.sub(pat, repl, result, flags=re.IGNORECASE)
    return result.upper()


# ════════════════════════════════════════════════════════════════
# 메인 변환 함수
# ════════════════════════════════════════════════════════════════
def convert_tvf_to_procedure(src_ddl: str, obj_name: str = "") -> dict:
    """TVF → MySQL PROCEDURE 결정적 변환.
    
    Returns:
      {
        'success': bool,
        'final_sql': str,
        'elapsed_ms': int,
        'notes': str,
        'reason': str (실패 시),
      }
    """
    t0 = time.monotonic()
    result = {
        'success': False,
        'final_sql': '',
        'elapsed_ms': 0,
        'notes': '',
        'reason': '',
    }
    
    # 1. 헤더 파싱
    header = parse_function_header(src_ddl)
    if not header:
        result['reason'] = 'header_parse_failed'
        result['elapsed_ms'] = int((time.monotonic() - t0) * 1000)
        return result
    
    # 2. 컬럼 정의 → MySQL
    cols_mysql = convert_columns_via_sqlglot(header['columns_raw'])
    if not cols_mysql:
        result['reason'] = 'columns_convert_failed'
        result['elapsed_ms'] = int((time.monotonic() - t0) * 1000)
        return result
    
    # 3. 본체 추출 (AS 이후 전체)
    body = src_ddl[header['body_start']:].strip()
    body = re.sub(r'^AS\s*', '', body, flags=re.IGNORECASE).strip()
    
    # 4. IF EXISTS 블록 분할
    blocks = split_body_into_blocks(body)
    if not blocks:
        result['reason'] = 'no_if_exists_blocks'
        result['elapsed_ms'] = int((time.monotonic() - t0) * 1000)
        return result
    
    # 5. PROCEDURE 합치기
    proc_name = f"{header['schema']}_{header['name']}"
    
    # 파라미터: @PersonID int → IN p_PersonID INT
    params_my = []
    for p in header['params']:
        my_type = _map_type(p['type'])
        params_my.append(f"IN p_{p['name']} {my_type}")
    params_str = ', '.join(params_my)
    
    # 본체 작성
    lines = []
    lines.append(f"DROP PROCEDURE IF EXISTS `{proc_name}`;")
    lines.append("DELIMITER //")
    lines.append(f"CREATE PROCEDURE `{proc_name}`({params_str})")
    lines.append("BEGIN")
    lines.append(f"    -- v95_p107 hotfix_023: TVF → SP 결정적 변환 (Rule Engine)")
    lines.append(f"    -- 본부장님 본질 처방 — Gemma 호출 0회, 0.05초/객체")
    lines.append(f"    DROP TEMPORARY TABLE IF EXISTS temp_result;")
    lines.append(f"    CREATE TEMPORARY TABLE temp_result (")
    
    # 컬럼 정의 들여쓰기
    col_lines = [l.strip() for l in cols_mysql.split(',') if l.strip()]
    for idx, col_line in enumerate(col_lines):
        suffix = ',' if idx < len(col_lines) - 1 else ''
        lines.append(f"        {col_line}{suffix}")
    lines.append(f"    );")
    lines.append("")
    
    # 각 IF EXISTS 블록
    for idx, blk in enumerate(blocks, 1):
        if blk['kind'] == 'if_exists_insert':
            cond_mysql = convert_select_via_sqlglot(blk['condition'])
            insert_mysql = convert_select_via_sqlglot(blk['insert_select'])
            # INSERT 끝 세미콜론 정리 (중복 방지)
            insert_mysql = insert_mysql.rstrip().rstrip(';')
            
            lines.append(f"    -- 블록 {idx}")
            lines.append(f"    IF EXISTS({cond_mysql}) THEN")
            lines.append(f"        INSERT INTO temp_result")
            for il in insert_mysql.split('\n'):
                lines.append(f"        {il}")
            lines.append(f"        ;")
            lines.append(f"    END IF;")
            lines.append("")
    
    lines.append(f"    SELECT * FROM temp_result;")
    lines.append("END //")
    lines.append("DELIMITER ;")
    
    final_sql = '\n'.join(lines)
    
    result['success'] = True
    result['final_sql'] = final_sql
    result['elapsed_ms'] = int((time.monotonic() - t0) * 1000)
    result['notes'] = (f"TVF→SP 결정적 변환 — "
                       f"컬럼 {len(col_lines)}개, IF EXISTS 블록 {len(blocks)}개, "
                       f"{result['elapsed_ms']}ms")
    
    return result


# ════════════════════════════════════════════════════════════════
# 통계 (관찰용)
# ════════════════════════════════════════════════════════════════
_stats = {
    'total_attempts': 0,
    'total_success':  0,
    'total_elapsed_ms': 0,
}


def get_stats() -> dict:
    """Rule Engine 통계 (관리자 페이지용)"""
    return dict(_stats)


def _record(success: bool, elapsed_ms: int):
    _stats['total_attempts'] += 1
    if success:
        _stats['total_success'] += 1
    _stats['total_elapsed_ms'] += elapsed_ms


# ════════════════════════════════════════════════════════════════
# 외부 진입점 (schema._ai_convert_ddl 에서 호출)
# ════════════════════════════════════════════════════════════════
def try_convert_tvf(src_ddl: str, obj_type: str, obj_name: str) -> Optional[dict]:
    """schema._ai_convert_ddl 에서 호출하는 진입점.
    
    Returns:
      성공 시: {'final_sql': ..., 'notes': ..., 'elapsed_ms': ...}
      실패 시: None (Layer 4 AI fallback 으로 위임)
    """
    # 1. obj_type 필터링 — FUNCTION/FN 만
    if obj_type and obj_type.upper() not in ('FUNCTION', 'FN', 'FN_T'):
        return None
    
    # 2. TVF 패턴 감지
    if not is_tvf(src_ddl):
        return None
    
    # 3. 변환 시도
    result = convert_tvf_to_procedure(src_ddl, obj_name)
    _record(result['success'], result['elapsed_ms'])
    
    if result['success']:
        _log.info(
            "[tvf_rule_engine] %s [%s] 결정적 변환 성공 — %s",
            obj_type, obj_name, result['notes']
        )
        return {
            'final_sql': result['final_sql'],
            'notes': result['notes'],
            'elapsed_ms': result['elapsed_ms'],
        }
    else:
        _log.info(
            "[tvf_rule_engine] %s [%s] 미적용 (reason=%s) — AI fallback",
            obj_type, obj_name, result['reason']
        )
        return None
