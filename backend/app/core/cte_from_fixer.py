"""
DataBridge CTE FROM 누락 자동 보강 — hotfix_026
==================================================

본부장님 환경 본질 (2026-05-11 오후 발견):
  Gemma 가 MSSQL CTE 변환 시 본문 끝의 FROM 절 빼먹음.
  
  결과:
    WITH RECURSIVE `BOM_cte` (...) AS (...)
    SELECT b.X, b.Y ORDER BY b.Z END;
                  ↑ FROM `BOM_cte` AS b 누락!
  
  → MySQL 1064 syntax error "near 'END'"

본부장님 환경 3개 객체에서 발견:
  - uspGetBillOfMaterials
  - uspGetManagerEmployees
  - uspGetWhereUsedProductID

처방: CTE PROCEDURE 의 마지막 SELECT 에 FROM 절 없으면 자동 추가.
"""
from __future__ import annotations
import re
import logging
from typing import Tuple, List

_log = logging.getLogger("databridge.cte_from_fixer")


def has_cte_with_recursive(sql: str) -> bool:
    """WITH RECURSIVE 가 있나?"""
    return bool(re.search(r'\bWITH\s+RECURSIVE\b', sql, re.IGNORECASE))


def extract_cte_name(sql: str) -> str:
    """WITH RECURSIVE `cte_name` (...) → cte_name 추출"""
    m = re.search(
        r'WITH\s+RECURSIVE\s+`?(\w+)`?\s*\(',
        sql, re.IGNORECASE
    )
    return m.group(1) if m else ""


def fix_cte_missing_from(sql: str) -> Tuple[str, List[str]]:
    """
    CTE PROCEDURE 의 마지막 SELECT 에 FROM 절 누락 시 자동 보강.
    
    패턴:
        WITH RECURSIVE `xyz_cte` (...) AS (...)
        SELECT cols ORDER BY ... [END;]
                   ↑ FROM 누락
    
    →   WITH RECURSIVE `xyz_cte` (...) AS (...)
        SELECT cols FROM `xyz_cte` AS b ORDER BY ... [END;]
                       ↑ 자동 추가
    """
    fixes = []
    
    if not has_cte_with_recursive(sql):
        return sql, fixes
    
    cte_name = extract_cte_name(sql)
    if not cte_name:
        return sql, fixes
    
    # CTE 본문의 마지막 ) 위치 찾기 — 그 다음에 SELECT 가 와야 함
    # AS ( ... ) SELECT 패턴
    # 단순화: WITH ... AS ( anchor UNION ALL recursive ) SELECT ...
    # 본부장님 환경에선 ) SELECT cols ORDER BY ... END; 형태
    
    # `cte_name` 또는 cte_name 의 alias (보통 b, e, cte) 찾기 — 본문 안에서
    # 첫 anchor SELECT 의 FROM table alias 찾아서 그게 자주 사용됨
    
    # 1. 마지막 SELECT 찾기: "...) SELECT ..." 패턴
    # 괄호 짝 맞춰서 CTE 본문 끝의 ) 위치 찾기
    
    # WITH RECURSIVE `cte_name` ( 부터 시작
    start_m = re.search(r'WITH\s+RECURSIVE\s+`?\w+`?\s*\(', sql, re.IGNORECASE)
    if not start_m:
        return sql, fixes
    
    # 컬럼 정의 괄호 끝 찾기
    pos = start_m.end() - 1
    depth = 1
    while pos < len(sql) - 1 and depth > 0:
        pos += 1
        if sql[pos] == '(':
            depth += 1
        elif sql[pos] == ')':
            depth -= 1
    # pos = 컬럼 정의 ) 위치
    
    # 그 다음 AS ( 찾기
    as_m = re.search(r'\s*AS\s*\(', sql[pos+1:], re.IGNORECASE)
    if not as_m:
        return sql, fixes
    
    cte_body_start = pos + 1 + as_m.end() - 1  # AS 의 ( 위치
    depth = 1
    cte_body_end = cte_body_start + 1
    while cte_body_end < len(sql) and depth > 0:
        if sql[cte_body_end] == '(':
            depth += 1
        elif sql[cte_body_end] == ')':
            depth -= 1
            if depth == 0:
                break
        cte_body_end += 1
    
    if cte_body_end >= len(sql):
        return sql, fixes
    
    # cte_body_end = CTE 본문의 ) 위치
    # 그 다음부터 마지막 SELECT 시작
    after_cte = sql[cte_body_end+1:].strip()
    
    # SELECT 로 시작하는지
    if not re.match(r'^\s*SELECT\b', after_cte, re.IGNORECASE):
        return sql, fixes
    
    # FROM 절이 이미 있는지 (마지막 SELECT 안에)
    # END 또는 ; 전까지가 마지막 SELECT
    # 보통 형식: SELECT ... FROM ... [WHERE ...] [ORDER BY ...] [END;]
    
    # 끝의 END 또는 ; 위치 찾기
    end_m = re.search(r'\bEND\s*;?\s*$', after_cte, re.IGNORECASE)
    if end_m:
        last_select = after_cte[:end_m.start()].strip()
    else:
        last_select = after_cte.rstrip(';').strip()
    
    # 이 마지막 SELECT 에 FROM 절이 있나?
    if re.search(r'\bFROM\b', last_select, re.IGNORECASE):
        return sql, fixes  # FROM 이미 있음
    
    # FROM 누락 — 자동 보강
    # alias 추정: 컬럼 표현에서 자주 쓰이는 alias 찾기 (b.col, e.col 등)
    # 예약어 제외 — 정확한 alias 추출
    RESERVED = {'AS', 'ASC', 'DESC', 'SUM', 'COUNT', 'AVG', 'MAX', 'MIN',
                'CASE', 'WHEN', 'THEN', 'END', 'AND', 'OR', 'NOT', 'IN',
                'SELECT', 'FROM', 'WHERE', 'GROUP', 'ORDER', 'BY', 'HAVING',
                'JOIN', 'INNER', 'OUTER', 'LEFT', 'RIGHT', 'ON', 'IS', 'NULL'}
    alias_candidates = re.findall(r'\b(\w+)\.`?\w', last_select)
    alias_candidates = [a for a in alias_candidates if a.upper() not in RESERVED]
    if alias_candidates:
        from collections import Counter
        alias = Counter(alias_candidates).most_common(1)[0][0]
    else:
        alias = 'cte_alias'
    
    # ORDER BY 앞에 FROM 추가
    order_by_m = re.search(r'\bORDER\s+BY\b', last_select, re.IGNORECASE)
    if order_by_m:
        # SELECT cols FROM `cte` AS alias ORDER BY ...
        new_select = (
            last_select[:order_by_m.start()].rstrip() +
            f' FROM `{cte_name}` AS {alias} ' +
            last_select[order_by_m.start():]
        )
    else:
        # SELECT cols FROM `cte` AS alias
        new_select = last_select + f' FROM `{cte_name}` AS {alias}'
    
    fixes.append(f"CTE FROM 절 누락 자동 보강 (cte=`{cte_name}`, alias={alias})")
    
    # 재조합
    if end_m:
        new_sql = (
            sql[:cte_body_end+1] + ' ' +
            new_select + ' ' +
            after_cte[end_m.start():]
        )
    else:
        new_sql = sql[:cte_body_end+1] + ' ' + new_select + (';' if sql.rstrip().endswith(';') else '')
    
    return new_sql, fixes


def try_fix_cte(stmts: list, obj_type: str = "", obj_name: str = "") -> Tuple[list, List[str]]:
    """statements 리스트 전체에 CTE FROM 보강 적용."""
    fixed = []
    all_fixes = []
    for s in stmts:
        new_s, fixes = fix_cte_missing_from(s)
        fixed.append(new_s)
        all_fixes.extend(fixes)
    return fixed, all_fixes
