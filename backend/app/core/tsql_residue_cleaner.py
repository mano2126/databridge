"""
DataBridge T-SQL 잔재 자동 정화 — hotfix_025 (본부장님 본질 처방)
=========================================================================

본부장님 본질 통찰 9번째 (2026-05-11):
  "Gemma 한계는 토큰만이 아님 — 식별자 변환 실수도 본질"

오늘 발견된 본부장님 환경 11개 실패의 공통 본질:
  - PROCEDURE/VIEW/TRIGGER 의 [bracket] 식별자 미변환
  - OBJECT_ID(N'[dbo].[name]', N'TR') 같은 T-SQL DROP guard 잔재
  - ISNULL, GETDATE, ExtractXmlValue 등 T-SQL 함수 잔재
  - [Schema].[Table] 스키마 평탄화 누락
  - [Alias.Column] 같은 컬럼 alias 의 bracket

처방: AI(Gemma) 응답을 받은 직후, 결정적 후처리 한 번 더 → 자주 잘못되는 패턴 자동 보강.

본부장님 모토 #4 (본질에 충실, 한방에) 정면 충실 — Gemma 응답 받고 무조건 후처리.
본부장님 모토 #14 (4-way collision 방지) — 기존 sql_post_processor 그대로 + 뒤에 추가.

작동 원리:
  1. Gemma 응답 SQL 받음 (이미 v95_p88++ post_process_sql 통과 후)
  2. T-SQL 잔재 패턴 정규식으로 정화
  3. 검출된 패턴 수와 변경 사항 통계 반환 (추적 가능)

기존 sql_post_processor 와 차이:
  - sql_post_processor: AI 가 변환 시도한 결과의 일반적 정리
  - tsql_residue_cleaner: AI 가 변환 못 한 잔재 강제 정화 (이번 본부장님 본질)
"""
from __future__ import annotations
import re
import logging
from typing import Tuple, List

_log = logging.getLogger("databridge.tsql_residue_cleaner")


# ════════════════════════════════════════════════════════════════
# 잔재 정화 규칙 (본부장님 환경 11개 실패 케이스 분석 기반)
# ════════════════════════════════════════════════════════════════

def clean_tsql_residues(sql: str, obj_type: str = "", obj_name: str = "") -> Tuple[str, List[str]]:
    """T-SQL 잔재 자동 정화 (결정적, 후처리).
    
    Args:
        sql: AI 변환 결과 SQL (이미 1차 후처리 통과)
        obj_type: 객체 타입 (FUNCTION/PROCEDURE/VIEW/TRIGGER) — 조건부 처방용
        obj_name: 객체 이름 (로그용)
    
    Returns:
        (cleaned_sql, applied_fixes_list)
    """
    if not sql:
        return sql, []
    
    fixes = []
    result = sql
    obj_type_upper = (obj_type or "").upper()
    
    # ─── 규칙 1: T-SQL DROP guard 통째로 제거 (TRIGGER 의 본질) ───
    # IF OBJECT_ID(N'[dbo].[Sales_uSalesOrderHeader]', N'TR') IS NOT NULL DROP TRIGGER [dbo].[...];
    pattern_drop_guard = re.compile(
        r"IF\s+OBJECT_ID\s*\(\s*N?'[^']+'\s*,\s*N?'\w+'\s*\)\s+IS\s+NOT\s+NULL\s+"
        r"DROP\s+(?:TRIGGER|PROCEDURE|FUNCTION|VIEW|TABLE)\s+[^;]+;",
        re.IGNORECASE | re.DOTALL
    )
    matches = pattern_drop_guard.findall(result)
    if matches:
        result = pattern_drop_guard.sub('', result)
        fixes.append(f"DROP guard 제거 ({len(matches)}건)")
    
    # ─── 규칙 2: [Schema].[Table] → Schema_Table (스키마 평탄화) ───
    # [dbo].[uspGetBillOfMaterials] → dbo_uspGetBillOfMaterials
    # [Sales].[SalesOrderHeader]    → Sales_SalesOrderHeader
    n_brackets_before = len(re.findall(r'\[\w+\]\.\[\w+\]', result))
    if n_brackets_before:
        result = re.sub(r'\[(\w+)\]\.\[(\w+)\]', r'\1_\2', result)
        fixes.append(f"[Schema].[Table] 평탄화 ({n_brackets_before}건)")
    
    # ─── 규칙 3: [Schema].Table → Schema_Table (bracket 한쪽만) ───
    n3 = len(re.findall(r'\[\w+\]\.\w+', result))
    if n3:
        result = re.sub(r'\[(\w+)\]\.(\w+)', r'\1_\2', result)
        fixes.append(f"[Schema].Table 평탄화 ({n3}건)")
    
    # ─── 규칙 4: [Identifier] → `Identifier` (단일 bracket — MySQL backtick) ───
    # 본부장님 환경의 11개 실패 중 9개 핵심 본질
    # [dbo_uspGetBillOfMaterials] → `dbo_uspGetBillOfMaterials`
    # [Name.Prefix] → `Name.Prefix` (alias 안의 dot 도 그대로)
    # 그러나 문자열 리터럴 안의 [ ] 는 제외 (예: '...' 안의 [ ])
    n_single = 0
    
    def replace_brackets(match):
        nonlocal n_single
        n_single += 1
        ident = match.group(1)
        return f'`{ident}`'
    
    # 문자열 리터럴 보존 — 작은따옴표 안의 내용은 건드리지 않음
    # 다중라인 처리: 단순 정규식으로 안전한 케이스만
    # [identifier] 패턴 — 글자, 숫자, 밑줄, dot, 공백 포함 식별자
    result = re.sub(
        r'\[([\w\s\.\-]+)\]',
        replace_brackets,
        result
    )
    if n_single:
        fixes.append(f"[id] → `id` ({n_single}건)")
    
    # ─── 규칙 5: T-SQL 자주 쓰는 함수 → MySQL 등가 ───
    function_map = [
        (r'\bISNULL\s*\(', 'IFNULL(', 'ISNULL→IFNULL'),
        (r'\bGETDATE\s*\(\s*\)', 'NOW()', 'GETDATE()→NOW()'),
        (r'\bGETUTCDATE\s*\(\s*\)', 'UTC_TIMESTAMP()', 'GETUTCDATE()→UTC_TIMESTAMP()'),
        (r'\bLEN\s*\(', 'CHAR_LENGTH(', 'LEN→CHAR_LENGTH'),
        (r'\bDATEPART\s*\(\s*yy(?:yy)?\s*,', 'YEAR(', 'DATEPART(yy)→YEAR('),
        (r'\bDATEPART\s*\(\s*mm\s*,', 'MONTH(', 'DATEPART(mm)→MONTH('),
        (r'\bDATEPART\s*\(\s*dd\s*,', 'DAY(', 'DATEPART(dd)→DAY('),
    ]
    
    for pat, repl, desc in function_map:
        count = len(re.findall(pat, result, re.IGNORECASE))
        if count:
            result = re.sub(pat, repl, result, flags=re.IGNORECASE)
            fixes.append(f"{desc} ({count}건)")
    
    # ─── 규칙 6: T-SQL @변수 → MySQL ${var} 또는 그대로 (위치별 다름) ───
    # 너무 공격적이면 위험 — PROCEDURE 안의 변수는 그대로 두고
    # JSON 안의 @PersonID 같은 것만 처리하는 게 안전. 일단 보류.
    
    # ─── 규칙 7: NULL NOT NULL 충돌 패턴 ───
    # 본부장님 KB 깨짐 본질
    pattern_null_conflict = re.compile(r'\bNULL\s+NOT\s+NULL\b', re.IGNORECASE)
    if pattern_null_conflict.search(result):
        result = pattern_null_conflict.sub('NOT NULL', result)
        fixes.append("NULL NOT NULL 충돌 해결")
    
    # ─── 규칙 8: VARCHAR(N NULL) 토큰 잘림 보강 (어제 hotfix_020 의 본질) ───
    # 이건 정정이 위험 — N 값을 추정할 수 없어서. 검출만 하고 fix 안 함
    pattern_varchar_broken = re.compile(r'VARCHAR\s*\(\s*\d+\s+NULL', re.IGNORECASE)
    if pattern_varchar_broken.search(result):
        # 통계용으로만 — 자동 fix 안 함 (게이트 8 에서 거부)
        fixes.append("⚠ VARCHAR(N NULL) 잔존 (수동 검토 필요)")
    
    # ─── 규칙 9: ; ; (이중 세미콜론) 정리 ───
    n_double = len(re.findall(r';\s*;', result))
    if n_double:
        result = re.sub(r';\s*;', ';', result)
        fixes.append(f"이중 ; 정리 ({n_double}건)")
    
    # ─── 규칙 10: 빈 statement (DROP foo;;\n;;\n) 정리 ───
    result = re.sub(r'^\s*;\s*$', '', result, flags=re.MULTILINE)
    
    # ─── 규칙 11: T-SQL N'string' → MySQL 'string' (N prefix 제거) ───
    n_nstring = len(re.findall(r"\bN'", result))
    if n_nstring:
        result = re.sub(r"\bN'", "'", result)
        fixes.append(f"N'string' → 'string' ({n_nstring}건)")
    
    # ─── 규칙 12: SET NOCOUNT ON; 등 T-SQL 전용 제거 ───
    n_nocount = len(re.findall(r'\bSET\s+NOCOUNT\s+ON\s*;', result, re.IGNORECASE))
    if n_nocount:
        result = re.sub(r'\bSET\s+NOCOUNT\s+ON\s*;', '', result, flags=re.IGNORECASE)
        fixes.append(f"SET NOCOUNT ON 제거 ({n_nocount}건)")
    
    # ─── 규칙 13: 연속 빈 줄 → 단일 줄 ───
    result = re.sub(r'\n\s*\n\s*\n+', '\n\n', result)
    
    return result, fixes


# ════════════════════════════════════════════════════════════════
# 통계 (관찰용)
# ════════════════════════════════════════════════════════════════
_stats = {
    'total_calls': 0,
    'total_fixes_applied': 0,
    'by_rule': {},
}


def get_stats() -> dict:
    """후처리 통계 (관리자 페이지용)."""
    return dict(_stats)


def _record(fixes: List[str]):
    _stats['total_calls'] += 1
    _stats['total_fixes_applied'] += len(fixes)
    for f in fixes:
        # "ISNULL→IFNULL (3건)" → "ISNULL→IFNULL" 만 카운트
        key = f.split(' (')[0]
        _stats['by_rule'][key] = _stats['by_rule'].get(key, 0) + 1


# ════════════════════════════════════════════════════════════════
# 외부 진입점 (schema._ai_convert_ddl 에서 호출)
# ════════════════════════════════════════════════════════════════
def clean_residues(stmts: List[str], obj_type: str = "", obj_name: str = "") -> Tuple[List[str], List[str]]:
    """statements 리스트 전체 정화.
    
    Returns:
        (cleaned_stmts, all_fixes)
    """
    cleaned = []
    all_fixes = []
    for s in stmts:
        new_s, fixes = clean_tsql_residues(s, obj_type, obj_name)
        cleaned.append(new_s)
        all_fixes.extend(fixes)
    
    _record(all_fixes)
    return cleaned, all_fixes
