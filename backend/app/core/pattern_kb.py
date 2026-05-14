"""
DataBridge Pattern-Based KB v2 — hotfix_030
================================================

본부장님 15번째 본질 통찰 (2026-05-11):
  "SQL 통째 KB 는 다양한 SQL 수용 불가. 패턴 자산화가 본질."

본부장님 환경 5쌍 데이터 분석 기반 24개 자산.
본부장님 모토 #4 (살아있는 자산) + #19 (air-gapped) 정면.
"""
from __future__ import annotations
import re
import json
import os
import logging
from typing import Tuple, List, Optional, Dict, Any
from datetime import datetime
from collections import Counter

_log = logging.getLogger("databridge.pattern_kb")

PATTERN_KB_VERSION = "3.0"


CORE_PATTERNS = [
    # ── Phase 1: Literal/Keyword Cleanup ───
    {'pattern_id': 'P001', 'priority': 1, 'category': 'literal',
     'name': "N'string' → 'string'",
     'src_regex': r"\bN'([^']*)'", 'tgt_template': r"'\1'",
     'confidence': 1.0},
    {'pattern_id': 'P002', 'priority': 2, 'category': 'statement',
     'name': 'SET NOCOUNT 제거',
     'src_regex': r'\bSET\s+NOCOUNT\s+(?:ON|OFF)\s*;?', 'tgt_template': '',
     'confidence': 1.0},
    {'pattern_id': 'P003', 'priority': 3, 'category': 'statement',
     'name': 'GO 배치 구분자 제거',
     'src_regex': r'^\s*GO\s*$', 'tgt_template': '',
     'flags_str': 'MULTILINE',
     'confidence': 1.0},
    {'pattern_id': 'P004', 'priority': 4, 'category': 'option',
     'name': 'OPTION(MAXRECURSION) 제거',
     'src_regex': r'OPTION\s*\(\s*MAXRECURSION\s+\d+\s*\)', 'tgt_template': '',
     'confidence': 1.0},
    {'pattern_id': 'P005', 'priority': 5, 'category': 'option',
     'name': 'NOT FOR REPLICATION 제거',
     'src_regex': r'\bNOT\s+FOR\s+REPLICATION\b', 'tgt_template': '',
     'confidence': 1.0},
    {'pattern_id': 'P006', 'priority': 6, 'category': 'statement',
     'name': 'IF OBJECT_ID DROP guard 제거',
     'src_regex': r"IF\s+OBJECT_ID\s*\([^)]+\)\s+IS\s+NOT\s+NULL\s+DROP\s+\w+\s+[`\[]?[\w\.\[\]`]+[`\]]?\s*;?",
     'tgt_template': '', 'confidence': 0.95},
    
    # v95_p107 hotfix_036 — 본부장님 환경 24개 실패 객체 정복 (16 NEW)
    {'pattern_id': 'P008', 'priority': 8, 'category': 'option',
     'name': 'WITH EXECUTE AS CALLER 제거',
     'src_regex': r'WITH\s+EXECUTE\s+AS\s+CALLER\s*',
     'tgt_template': '',
     'confidence': 1.0},
    {'pattern_id': 'P009', 'priority': 9, 'category': 'statement',
     'name': 'PRINT → SELECT (디버깅용)',
     'src_regex': r'\bPRINT\s+',
     'tgt_template': 'SELECT ',
     'confidence': 0.9},  # h036: 적용 활성
    {'pattern_id': 'P00A', 'priority': 10, 'category': 'function',
     'name': 'ERROR_NUMBER() → 0 (MySQL EXIT HANDLER 안에선 GET DIAGNOSTICS 사용)',
     'src_regex': r'\bERROR_NUMBER\s*\(\s*\)',
     'tgt_template': '0',
     'confidence': 0.7},
    {'pattern_id': 'P00B', 'priority': 11, 'category': 'function',
     'name': 'ERROR_MESSAGE() → \'\' (단순화)',
     'src_regex': r'\bERROR_MESSAGE\s*\(\s*\)',
     'tgt_template': "''",
     'confidence': 0.7},
    {'pattern_id': 'P00C', 'priority': 12, 'category': 'function',
     'name': 'ERROR_SEVERITY()/STATE()/LINE() → 0',
     'src_regex': r'\bERROR_(?:SEVERITY|STATE|LINE)\s*\(\s*\)',
     'tgt_template': '0',
     'confidence': 0.7},
    {'pattern_id': 'P00D', 'priority': 13, 'category': 'function',
     'name': 'ERROR_PROCEDURE() → \'unknown\'',
     'src_regex': r'\bERROR_PROCEDURE\s*\(\s*\)',
     'tgt_template': "'unknown'",
     'confidence': 0.7},
    {'pattern_id': 'P00E', 'priority': 14, 'category': 'function',
     'name': 'XACT_STATE() → 0 (정상)',
     'src_regex': r'\bXACT_STATE\s*\(\s*\)',
     'tgt_template': '0',
     'confidence': 0.7},
    
    # ── Phase 2: Data Type Bracket → 평문 ───
    {'pattern_id': 'P020', 'priority': 20, 'category': 'datatype',
     'name': '[int]/[datetime]/etc → 평문 (bracket 변환 전 선처리)',
     'src_regex': r'\[(int|INT|datetime|DATETIME|bigint|BIGINT|bit|BIT|tinyint|smallint|float|FLOAT|real|date|time|timestamp)\]',
     'tgt_template': r'\1',
     'confidence': 1.0},
    {'pattern_id': 'P021', 'priority': 21, 'category': 'datatype',
     'name': '[nvarchar](N) → VARCHAR(N)',
     'src_regex': r'\[(?:nvarchar|nchar)\]\s*\(\s*(\d+|MAX|max)\s*\)',
     'tgt_template': r'VARCHAR(\1)',
     'confidence': 1.0,
     'flags_str': 'IGNORECASE'},
    {'pattern_id': 'P022', 'priority': 22, 'category': 'datatype',
     'name': '[varchar](N) → VARCHAR(N)',
     'src_regex': r'\[(?:varchar|char)\]\s*\(\s*(\d+|MAX|max)\s*\)',
     'tgt_template': r'VARCHAR(\1)',
     'confidence': 1.0,
     'flags_str': 'IGNORECASE'},
    {'pattern_id': 'P023', 'priority': 23, 'category': 'datatype',
     'name': '[decimal](p,s) → DECIMAL(p,s)',
     'src_regex': r'\[(?:decimal|numeric)\]\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)',
     'tgt_template': r'DECIMAL(\1,\2)',
     'confidence': 1.0,
     'flags_str': 'IGNORECASE'},
    
    # v95_p107 hotfix_036 — 본부장님 환경 신규 타입
    {'pattern_id': 'P024', 'priority': 24, 'category': 'datatype',
     'name': '[money] → DECIMAL(19,4)',
     'src_regex': r'\[(?:money|MONEY)\]',
     'tgt_template': r'DECIMAL(19,4)',
     'confidence': 1.0,
     'flags_str': 'IGNORECASE'},
    {'pattern_id': 'P025', 'priority': 25, 'category': 'datatype',
     'name': '[hierarchyid] → VARCHAR(900) (계층 메서드 미지원)',
     'src_regex': r'\[(?:hierarchyid|HIERARCHYID)\]',
     'tgt_template': r'VARCHAR(900)',
     'confidence': 0.8,  # 계층 메서드 (.GetAncestor 등) 별도
     'flags_str': 'IGNORECASE'},
    {'pattern_id': 'P026', 'priority': 26, 'category': 'datatype',
     'name': '[sysname] → VARCHAR(128)',
     'src_regex': r'\[(?:sysname|SYSNAME)\]',
     'tgt_template': r'VARCHAR(128)',
     'confidence': 1.0,
     'flags_str': 'IGNORECASE'},
    {'pattern_id': 'P027', 'priority': 27, 'category': 'datatype',
     'name': '[dbo].[Flag] 사용자 정의 → BIT',
     'src_regex': r'\[(\w+)\]\.\[Flag\]',
     'tgt_template': r'BIT',
     'confidence': 0.9,
     'flags_str': 'IGNORECASE'},
    {'pattern_id': 'P028', 'priority': 28, 'category': 'datatype',
     'name': '[uniqueidentifier] → CHAR(36)',
     'src_regex': r'\[(?:uniqueidentifier|UNIQUEIDENTIFIER)\]',
     'tgt_template': r'CHAR(36)',
     'confidence': 1.0,
     'flags_str': 'IGNORECASE'},
    
    # ── Phase 3: Schema/Identifier ───
    {'pattern_id': 'P030', 'priority': 30, 'category': 'identifier',
     'name': '[Schema].[Object] → `Schema_Object`',
     'src_regex': r'\[(\w+)\]\.\[(\w+)\]',
     'tgt_template': r'`\1_\2`',
     'confidence': 1.0},
    {'pattern_id': 'P031', 'priority': 31, 'category': 'identifier',
     'name': '[Object] → `Object` (단일)',
     'src_regex': r'\[(\w+)\]',
     'tgt_template': r'`\1`',
     'confidence': 1.0},
    
    # ── Phase 4: Function ───
    {'pattern_id': 'P040', 'priority': 40, 'category': 'function',
     'name': 'GETDATE() → NOW()',
     'src_regex': r'\bGETDATE\s*\(\s*\)', 'tgt_template': 'NOW()',
     'confidence': 1.0},
    {'pattern_id': 'P041', 'priority': 41, 'category': 'function',
     'name': 'ISNULL → IFNULL',
     'src_regex': r'\bISNULL\s*\(', 'tgt_template': 'IFNULL(',
     'confidence': 1.0},
    {'pattern_id': 'P042', 'priority': 42, 'category': 'function',
     'name': '@@ROWCOUNT → ROW_COUNT()',
     'src_regex': r'@@ROWCOUNT', 'tgt_template': 'ROW_COUNT()',
     'confidence': 1.0},
    {'pattern_id': 'P043', 'priority': 43, 'category': 'function',
     'name': '@@IDENTITY → LAST_INSERT_ID()',
     'src_regex': r'@@IDENTITY', 'tgt_template': 'LAST_INSERT_ID()',
     'confidence': 1.0},
    {'pattern_id': 'P044', 'priority': 44, 'category': 'function',
     'name': 'LEN(x) → LENGTH(x)',
     'src_regex': r'\bLEN\s*\(', 'tgt_template': 'LENGTH(',
     'confidence': 1.0},
    {'pattern_id': 'P045', 'priority': 45, 'category': 'function',
     'name': 'NEWID() → UUID()',
     'src_regex': r'\bNEWID\s*\(\s*\)', 'tgt_template': 'UUID()',
     'confidence': 1.0},
    
    # v95_p107 hotfix_036 — 더 많은 함수 매핑
    {'pattern_id': 'P046', 'priority': 46, 'category': 'function',
     'name': 'SYSDATETIME() → NOW(6)',
     'src_regex': r'\bSYSDATETIME\s*\(\s*\)',
     'tgt_template': 'NOW(6)',
     'confidence': 1.0},
    {'pattern_id': 'P047', 'priority': 47, 'category': 'function',
     'name': 'GETUTCDATE() → UTC_TIMESTAMP()',
     'src_regex': r'\bGETUTCDATE\s*\(\s*\)',
     'tgt_template': 'UTC_TIMESTAMP()',
     'confidence': 1.0},
    {'pattern_id': 'P048', 'priority': 48, 'category': 'function',
     'name': 'CHARINDEX(needle, hay) → INSTR(hay, needle) (인자 순서 다름!)',
     'src_regex': r'\bCHARINDEX\s*\(\s*([^,]+?)\s*,\s*([^,)]+?)\s*\)',
     'tgt_template': r'INSTR(\2, \1)',
     'confidence': 0.9},
    {'pattern_id': 'P049', 'priority': 49, 'category': 'function',
     'name': 'SUBSTRING → SUBSTR',
     'src_regex': r'\bSUBSTRING\s*\(',
     'tgt_template': 'SUBSTR(',
     'confidence': 1.0},
    {'pattern_id': 'P04A', 'priority': 50, 'category': 'function',
     'name': 'IIF(cond, a, b) → IF(cond, a, b)',
     'src_regex': r'\bIIF\s*\(',
     'tgt_template': 'IF(',
     'confidence': 1.0},
    
    # v95_p107 hotfix_036 — CONVERT 변환 (가장 중요)
    {'pattern_id': 'P04B', 'priority': 51, 'category': 'function',
     'name': "CONVERT(datetime, 'YYYYMMDD', 112) → STR_TO_DATE('YYYYMMDD', '%Y%m%d')",
     'src_regex': r"\bCONVERT\s*\(\s*(?:\[?datetime\]?|\[?date\]?)\s*,\s*'(\d{8})'\s*,\s*112\s*\)",
     'tgt_template': r"STR_TO_DATE('\1', '%Y%m%d')",
     'confidence': 0.95,
     'flags_str': 'IGNORECASE'},
    {'pattern_id': 'P04C', 'priority': 52, 'category': 'function',
     'name': 'CONVERT(varchar(N), x) → CAST(x AS CHAR(N))',
     'src_regex': r'\bCONVERT\s*\(\s*\[?varchar\]?\s*\(\s*(\d+)\s*\)\s*,\s*([^,)]+?)\s*\)',
     'tgt_template': r'CAST(\2 AS CHAR(\1))',
     'confidence': 0.9,
     'flags_str': 'IGNORECASE'},
    {'pattern_id': 'P04D', 'priority': 53, 'category': 'function',
     'name': 'CONVERT(nvarchar(N), x) → CAST(x AS CHAR(N))',
     'src_regex': r'\bCONVERT\s*\(\s*\[?nvarchar\]?\s*\(\s*(\d+)\s*\)\s*,\s*([^,)]+?)\s*\)',
     'tgt_template': r'CAST(\2 AS CHAR(\1))',
     'confidence': 0.9,
     'flags_str': 'IGNORECASE'},
    {'pattern_id': 'P04E', 'priority': 54, 'category': 'function',
     'name': 'CONVERT(type, x) → CAST(x AS type) (일반)',
     'src_regex': r'\bCONVERT\s*\(\s*\[?(\w+(?:\([^)]+\))?)\]?\s*,\s*([^,)]+?)\s*\)',
     'tgt_template': r'CAST(\2 AS \1)',
     'confidence': 0.7,
     'flags_str': 'IGNORECASE'},
    
    # v95_p107 hotfix_036 — MSSQL 시스템 함수 (이제 P00A~P00E 에서 처리)
    {'pattern_id': 'P04I', 'priority': 58, 'category': 'function',
     'name': 'CURRENT_USER → USER()',
     'src_regex': r'\bCURRENT_USER\b(?!\s*\()',
     'tgt_template': 'USER()',
     'confidence': 0.9},
    
    # ── Phase 5: T-SQL Alias 형식 ───
    {'pattern_id': 'P050', 'priority': 60, 'category': 'alias',
     'name': '`Alias` = expr → expr AS Alias (식별자 변환 후)',
     'src_regex': r"(?:,|\s)\s*`(\w+)`\s*=\s*(\w+\.`?\w+`?)",
     'tgt_template': r', \2 AS `\1`',
     'confidence': 0.7,
     'context_dependent': True},
    
    # ── Phase 6: TRIGGER 변환 ───
    {'pattern_id': 'P060', 'priority': 70, 'category': 'structure',
     'name': 'CREATE TRIGGER ON tbl AFTER X AS BEGIN → AFTER X ON tbl FOR EACH ROW BEGIN',
     'src_regex': r'CREATE\s+TRIGGER\s+([`\w\.]+)\s+ON\s+([`\w\.]+)\s+(AFTER|BEFORE)\s+(INSERT|UPDATE|DELETE)\s+AS\s+BEGIN',
     'tgt_template': r'CREATE TRIGGER \1 \3 \4 ON \2 FOR EACH ROW BEGIN',
     'confidence': 0.85,
     'flags_str': 'IGNORECASE|DOTALL'},
    {'pattern_id': 'P061', 'priority': 71, 'category': 'function',
     'name': 'IF [NOT] UPDATE(col) → IF [NOT] (NEW.col <=> OLD.col)',
     'src_regex': r'IF\s+(NOT\s+)?UPDATE\s*\(\s*`?(\w+)`?\s*\)',
     'tgt_template': r'IF \1(NEW.\2 <=> OLD.\2)',
     'confidence': 0.85},
    {'pattern_id': 'P062', 'priority': 72, 'category': 'reference',
     'name': 'inserted.col / `inserted`.col → NEW.col',
     'src_regex': r'\b`?(inserted|INSERTED)`?\.`?(\w+)`?',
     'tgt_template': r'NEW.\2',
     'confidence': 1.0},
    {'pattern_id': 'P063', 'priority': 73, 'category': 'reference',
     'name': 'deleted.col / `deleted`.col → OLD.col',
     'src_regex': r'\b`?(deleted|DELETED)`?\.`?(\w+)`?',
     'tgt_template': r'OLD.\2',
     'confidence': 1.0},
    
    # ── Phase 7: SP/FN 시그니처 (context-dependent) ───
    {'pattern_id': 'P070', 'priority': 80, 'category': 'parameter',
     'name': '@param TYPE → IN p_param TYPE (헤더만)',
     'src_regex': r'@(\w+)\s+(int|datetime|bigint|bit|varchar|nvarchar|char|nchar|decimal|money|float)\b',
     'tgt_template': r'IN p_\1 \2',
     'confidence': 0.6,
     'context_dependent': True,
     'flags_str': 'IGNORECASE'},
    {'pattern_id': 'P071', 'priority': 81, 'category': 'variable',
     'name': '@var (body) → p_var',
     'src_regex': r'@(\w+)\b',
     'tgt_template': r'p_\1',
     'confidence': 0.5,
     'context_dependent': True},
    
    # v95_p107 hotfix_036 — 추가 정밀화
    {'pattern_id': 'P080', 'priority': 90, 'category': 'statement',
     'name': 'RETURN -1 (PROCEDURE) → 단순 RETURN',
     'src_regex': r'\bRETURN\s+-?\d+\s*;?',
     'tgt_template': 'RETURN;',
     'confidence': 0.8,
     'context_dependent': True},
    {'pattern_id': 'P081', 'priority': 91, 'category': 'statement',
     'name': "+ 문자열 연결 → CONCAT (간단)",
     # 'literal' + 'literal' 형태
     'src_regex': r"('[^']*')\s*\+\s*('[^']*')",
     'tgt_template': r"CONCAT(\1, \2)",
     'confidence': 0.9},
    {'pattern_id': 'P082', 'priority': 92, 'category': 'statement',
     'name': "+ 문자열 연결 (var + literal)",
     'src_regex': r"(p_\w+|\w+\.`?\w+`?)\s*\+\s*('[^']*')",
     'tgt_template': r"CONCAT(\1, \2)",
     'confidence': 0.85},
    {'pattern_id': 'P083', 'priority': 93, 'category': 'statement',
     'name': "+ 문자열 연결 (literal + var)",
     'src_regex': r"('[^']*')\s*\+\s*(p_\w+|\w+\.`?\w+`?)",
     'tgt_template': r"CONCAT(\1, \2)",
     'confidence': 0.85},
]


def _backup_confidence(p):
    return {**p, 'use_count': 0}


# ════════════════════════════════════════════════════════════════
# Pattern KB 파일 관리
# ════════════════════════════════════════════════════════════════
def get_pattern_kb_path() -> str:
    return os.path.expanduser('~/project/databridge_full/data/pattern_kb.json')


def _flags_from_str(s: str) -> int:
    if not s: return re.IGNORECASE
    f = 0
    for token in s.split('|'):
        token = token.strip().upper()
        if hasattr(re, token):
            f |= getattr(re, token)
    return f


def load_pattern_kb() -> dict:
    path = get_pattern_kb_path()
    if os.path.exists(path):
        with open(path) as f:
            kb = json.load(f)
            if kb.get('version') != PATTERN_KB_VERSION:
                old_uses = {p['pattern_id']: p.get('use_count', 0)
                            for p in kb.get('patterns', [])}
                kb['patterns'] = [
                    {**p, 'use_count': old_uses.get(p['pattern_id'], 0)}
                    for p in CORE_PATTERNS
                ]
                kb['version'] = PATTERN_KB_VERSION
                save_pattern_kb(kb)
            return kb
    return {
        'version': PATTERN_KB_VERSION,
        'created_at': datetime.now().isoformat(),
        'patterns': [{**p, 'use_count': 0} for p in CORE_PATTERNS],
    }


def save_pattern_kb(kb: dict) -> None:
    path = get_pattern_kb_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    kb['updated_at'] = datetime.now().isoformat()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(kb, f, indent=2, ensure_ascii=False)


# ════════════════════════════════════════════════════════════════
# Pattern Matcher
# ════════════════════════════════════════════════════════════════
def apply_patterns(src_sql: str, kb: Optional[dict] = None,
                   skip_context_dependent: bool = True) -> Tuple[str, List[Dict[str, Any]]]:
    """T-SQL → MySQL 변환 (Pattern KB 순차 적용)."""
    if kb is None:
        kb = load_pattern_kb()
    
    result = src_sql
    applied = []
    sorted_patterns = sorted(kb.get('patterns', []), key=lambda p: p.get('priority', 999))
    
    for pat in sorted_patterns:
        if skip_context_dependent and pat.get('context_dependent', False):
            continue
        if pat.get('confidence', 0) < 0.7:
            continue
        
        try:
            regex = pat['src_regex']
            template = pat['tgt_template']
            if template is None:
                continue
            flags = _flags_from_str(pat.get('flags_str', 'IGNORECASE'))
            
            new_result, count = re.subn(regex, template, result, flags=flags)
            if count > 0:
                applied.append({
                    'pattern_id': pat['pattern_id'],
                    'name': pat['name'],
                    'match_count': count,
                })
                result = new_result
        except Exception as e:
            _log.warning("[pattern_kb] %s 적용 실패: %s", pat.get('name', '?'), e)
    
    return result, applied


# ════════════════════════════════════════════════════════════════
# 통계
# ════════════════════════════════════════════════════════════════
def kb_value_report(kb: Optional[dict] = None) -> dict:
    if kb is None:
        kb = load_pattern_kb()
    patterns = kb.get('patterns', [])
    return {
        'version': kb.get('version'),
        'total_patterns': len(patterns),
        'total_uses': sum(p.get('use_count', 0) for p in patterns),
        'high_confidence': sum(1 for p in patterns if p.get('confidence', 0) >= 0.9),
        'context_dependent': sum(1 for p in patterns if p.get('context_dependent', False)),
        'by_category': dict(Counter(p.get('category', '?') for p in patterns)),
        'top_used': sorted(
            [(p['pattern_id'], p['name'], p.get('use_count', 0)) for p in patterns],
            key=lambda x: x[2], reverse=True
        )[:5],
    }


def record_pattern_use(pattern_ids: List[str], kb: Optional[dict] = None) -> None:
    if kb is None:
        kb = load_pattern_kb()
    id_set = set(pattern_ids)
    for p in kb.get('patterns', []):
        if p.get('pattern_id') in id_set:
            p['use_count'] = p.get('use_count', 0) + 1
    save_pattern_kb(kb)
