"""PIVOT → CASE WHEN 결정적 변환 — hotfix_026"""
from __future__ import annotations
import re
import logging
from typing import Tuple, List, Optional

_log = logging.getLogger("databridge.pivot_to_case_when")


def has_pivot(sql: str) -> bool:
    return bool(re.search(r'\bPIVOT\s*\(', sql, re.IGNORECASE))


def parse_pivot(sql: str) -> Optional[dict]:
    """PIVOT (agg(col) FOR pivot_col IN (v1,v2,..)) AS alias 추출."""
    pattern = re.compile(
        r'PIVOT\s*\(\s*'
        r'(\w+)\s*\(\s*([^)]+?)\s*\)\s*'
        r'FOR\s+([\w\.\[\]`]+)\s+'
        r'IN\s*\(\s*([^)]+?)\s*\)\s*'
        r'\)\s*AS\s+(\w+)',
        re.IGNORECASE | re.DOTALL
    )
    m = pattern.search(sql)
    if not m:
        return None
    return {
        'agg_func': m.group(1).strip(),
        'agg_col': m.group(2).strip(),
        'pivot_col': m.group(3).strip().strip('[]`'),
        'values': [v.strip().strip('[]`').strip("'") for v in m.group(4).split(',')],
        'pivot_alias': m.group(5).strip(),
        'pivot_full_text': m.group(0),
    }


def convert_pivot_to_case_when(sql: str) -> Tuple[str, List[str]]:
    fixes = []
    if not has_pivot(sql):
        return sql, fixes
    
    parsed = parse_pivot(sql)
    if not parsed:
        return sql, fixes
    
    agg = parsed['agg_func']
    agg_col = parsed['agg_col']
    pcol = parsed['pivot_col']
    values = parsed['values']
    palias = parsed['pivot_alias']
    
    # 1. CASE WHEN 컬럼
    case_cols = []
    for v in values:
        is_numeric = v.replace('.', '').replace('-', '').isdigit()
        v_match = v if is_numeric else f"'{v}'"
        case_cols.append(
            f"{agg}(CASE WHEN {pcol} = {v_match} THEN {agg_col} END) AS `{v}`"
        )
    
    new_sql = sql
    
    # 2. SELECT 의 pvt.[V1] → CASE WHEN 로 치환
    for i, v in enumerate(values):
        patterns = [
            rf'\b{re.escape(palias)}\.\[{re.escape(v)}\]',
            rf'\b{re.escape(palias)}\.`{re.escape(v)}`',
        ]
        for pat in patterns:
            new_sql = re.sub(pat, case_cols[i], new_sql)
    
    # 3. PIVOT (...) AS palias 통째로 제거
    new_sql = new_sql.replace(parsed['pivot_full_text'], '', 1)
    
    # 4. GROUP BY 자동 추가
    select_m = re.search(r'SELECT\s+(.+?)\s+FROM\s', new_sql, re.IGNORECASE | re.DOTALL)
    if select_m:
        select_cols_str = select_m.group(1)
        # CASE WHEN 부분 제거 후 남은 컬럼만
        cleaned = re.sub(
            r'\b(?:SUM|AVG|MIN|MAX|COUNT)\s*\(\s*CASE\s+WHEN\b.*?END\s*\)\s*AS\s+`\w+`',
            '', select_cols_str, flags=re.IGNORECASE | re.DOTALL
        )
        # palias.col 또는 일반 col 추출
        non_case_cols = re.findall(rf'\b{re.escape(palias)}\.\w+', cleaned)
        non_case_cols = list(dict.fromkeys(non_case_cols))
        
        if non_case_cols and not re.search(r'\bGROUP\s+BY\b', new_sql, re.IGNORECASE):
            gb_clause = ' GROUP BY ' + ', '.join(non_case_cols)
            # ORDER BY 앞 또는 ; 앞에 추가
            ob_m = re.search(r'\s*(ORDER\s+BY|HAVING|LIMIT)\s', new_sql, re.IGNORECASE)
            if ob_m:
                new_sql = new_sql[:ob_m.start()] + gb_clause + new_sql[ob_m.start():]
            else:
                if new_sql.rstrip().endswith(';'):
                    new_sql = new_sql.rstrip().rstrip(';') + gb_clause + ';'
                else:
                    new_sql = new_sql.rstrip() + gb_clause
    
    fixes.append(f"PIVOT → CASE WHEN ({len(values)}개 값)")
    return new_sql, fixes


def try_convert_pivot(stmts: list, obj_type: str = "", obj_name: str = "") -> Tuple[list, List[str]]:
    fixed = []
    all_fixes = []
    for s in stmts:
        new_s, fixes = convert_pivot_to_case_when(s)
        fixed.append(new_s)
        all_fixes.extend(fixes)
    return fixed, all_fixes
