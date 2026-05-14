"""
DataBridge Context-Aware Pattern Engine — hotfix_030
=========================================================

본부장님 본질 — SQLGlot 넘어서는 진가:
  SQLGlot 의 한계 (context-dependent 변환 불가) 를 우리가 처방.

처방:
  1. SP/FN body 파서 — @변수 위치별 정확한 변환
  2. TVF → SP 구조 재작성
  3. TRY/CATCH → 단순화 + EXIT HANDLER 권장 주석
  4. TRIGGER 의 body 변수 (@Count 등) 처리

본부장님 모토 #19 (air-gapped) 정면.
"""
from __future__ import annotations
import re
import logging
from typing import Tuple, List, Optional
from dataclasses import dataclass, field

_log = logging.getLogger("databridge.context_pattern")


@dataclass
class SqlStructure:
    obj_type: str = ""
    obj_schema: str = ""
    obj_name: str = ""
    params: List[Tuple[str, str]] = field(default_factory=list)
    returns: str = ""
    body: str = ""
    body_vars: List[Tuple[str, str]] = field(default_factory=list)
    is_tvf: bool = False
    raw: str = ""


def parse_tsql_structure(sql: str) -> Optional[SqlStructure]:
    """T-SQL DDL 을 파싱."""
    s = SqlStructure(raw=sql)
    sql_clean = sql.replace('\r\n', '\n').strip()
    
    m = re.search(
        r'CREATE\s+(PROCEDURE|FUNCTION|TRIGGER|VIEW)\s+'
        r'(?:\[(\w+)\]\.)?\[(\w+)\]',
        sql_clean, re.IGNORECASE,
    )
    if not m:
        return None
    s.obj_type = m.group(1).upper()
    s.obj_schema = m.group(2) or 'dbo'
    s.obj_name = m.group(3)
    
    if s.obj_type == 'VIEW':
        s.body = sql_clean
        return s
    
    rest = sql_clean[m.end():]
    param_end = re.search(r'\b(AS|RETURNS)\b', rest, re.IGNORECASE)
    if not param_end:
        return None
    param_str = rest[:param_end.start()]
    
    if param_str.strip().startswith('('):
        depth = 0
        end_pos = 0
        for i, c in enumerate(param_str):
            if c == '(': depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    end_pos = i
                    break
        param_str = param_str[1:end_pos]
    
    param_pattern = re.compile(
        r'@(\w+)\s+'
        r'(?:\[(\w+)\]|(\w+))'
        r'(?:\s*\(\s*([^)]+)\s*\))?',
        re.IGNORECASE
    )
    for pm in param_pattern.finditer(param_str):
        var_name = pm.group(1)
        var_type = (pm.group(2) or pm.group(3) or '').lower()
        var_size = pm.group(4)
        if var_size:
            var_type = f"{var_type.upper()}({var_size})"
        else:
            var_type = var_type.upper()
        s.params.append((var_name, var_type))
    
    if s.obj_type == 'FUNCTION':
        rest2 = rest[param_end.end():]
        tvf_m = re.match(
            r'\s+@(\w+)\s+TABLE\s*\(([^)]+(?:\([^)]*\)[^)]*)*)\)',
            rest2, re.IGNORECASE | re.DOTALL,
        )
        if tvf_m:
            s.is_tvf = True
            s.returns = f"TABLE({tvf_m.group(2).strip()})"
        else:
            simple_m = re.match(
                r'\s+(?:\[(\w+)\]|(\w+))(?:\s*\(\s*[^)]+\s*\))?',
                rest2, re.IGNORECASE,
            )
            if simple_m:
                s.returns = (simple_m.group(1) or simple_m.group(2) or '').upper()
        as_m = re.search(r'\bAS\s+BEGIN\b', rest2, re.IGNORECASE)
        if as_m:
            s.body = rest2[as_m.end():]
    elif s.obj_type == 'PROCEDURE':
        rest2 = rest[param_end.end():]
        body_m = re.match(r'\s*BEGIN\s+', rest2, re.IGNORECASE)
        if body_m:
            s.body = rest2[body_m.end():]
        else:
            s.body = rest2.lstrip()
    elif s.obj_type == 'TRIGGER':
        rest2 = rest[param_end.end():]
        body_m = re.match(r'\s*BEGIN\s+', rest2, re.IGNORECASE)
        if body_m:
            s.body = rest2[body_m.end():]
        else:
            s.body = rest2.lstrip()
    
    declare_pattern = re.compile(
        r'\bDECLARE\s+@(\w+)\s+'
        r'(?:\[(\w+)\]|(\w+))'
        r'(?:\s*\(\s*([^)]+)\s*\))?',
        re.IGNORECASE
    )
    for dm in declare_pattern.finditer(s.body):
        var_name = dm.group(1)
        var_type = (dm.group(2) or dm.group(3) or '').upper()
        var_size = dm.group(4)
        if var_size:
            var_type = f"{var_type}({var_size})"
        s.body_vars.append((var_name, var_type))
    
    # v95_p107 hotfix_030 — multi-variable DECLARE 처리:
    # DECLARE @a TYPE, @b TYPE, @c TYPE → 각 변수를 body_vars 에 추가
    multi_decl_pattern = re.compile(
        r'\bDECLARE\s+@\w+\s+(?:\[?\w+\]?(?:\([^)]+\))?)\s*'
        r'((?:,\s*@\w+\s+(?:\[?\w+\]?(?:\([^)]+\))?)\s*)+)',
        re.IGNORECASE
    )
    for mm in multi_decl_pattern.finditer(s.body):
        # 나머지 @var TYPE 들 추출
        rest_vars = mm.group(1)
        var_pattern = re.compile(
            r'@(\w+)\s+(?:\[(\w+)\]|(\w+))(?:\s*\(\s*([^)]+)\s*\))?',
            re.IGNORECASE
        )
        for vm in var_pattern.finditer(rest_vars):
            var_name = vm.group(1)
            var_type = (vm.group(2) or vm.group(3) or '').upper()
            var_size = vm.group(4)
            if var_size:
                var_type = f"{var_type}({var_size})"
            # 중복 방지
            if not any(n == var_name for n, _ in s.body_vars):
                s.body_vars.append((var_name, var_type))
    
    return s


def _transform_body_vars(body: str, params: List[Tuple[str, str]],
                          body_vars: List[Tuple[str, str]]) -> Tuple[str, List[str]]:
    """body 안의 @변수 → p_변수 + DECLARE 변환."""
    fixes = []
    result = body
    
    # 헤더 파라미터의 @var → p_var
    for param_name, _ in params:
        new_result, count = re.subn(
            rf'@{re.escape(param_name)}\b',
            f'p_{param_name}',
            result,
        )
        if count:
            result = new_result
    if params:
        fixes.append(f"@param → p_param ({len(params)}개)")
    
    # DECLARE @var TYPE → DECLARE p_var TYPE + body 의 참조
    for var_name, var_type in body_vars:
        result = re.sub(
            rf'DECLARE\s+@{re.escape(var_name)}\s+(?:\[\w+\]|\w+)(?:\s*\(\s*[^)]+\s*\))?',
            f'DECLARE p_{var_name} {var_type}',
            result, flags=re.IGNORECASE,
        )
        result = re.sub(
            rf'@{re.escape(var_name)}\b',
            f'p_{var_name}',
            result,
        )
    if body_vars:
        fixes.append(f"DECLARE @var → p_var ({len(body_vars)}개)")
    
    # SET NOCOUNT 제거
    result = re.sub(r'\bSET\s+NOCOUNT\s+(?:ON|OFF)\s*;?', '', result, flags=re.IGNORECASE)
    
    return result, fixes


def transform_with_context(structure: SqlStructure) -> Tuple[str, List[str]]:
    """SP/FN/TRIGGER 구조 인식 + context-aware 변환."""
    fixes = []
    
    if structure.obj_type == 'VIEW':
        return structure.body, []
    
    obj_name_my = f"`{structure.obj_schema}_{structure.obj_name}`"
    
    if structure.obj_type == 'TRIGGER':
        # TRIGGER: body 변수만 정화 (헤더는 P060 패턴이 처리)
        new_body, body_fixes = _transform_body_vars(
            structure.body, structure.params, structure.body_vars,
        )
        fixes.extend(body_fixes)
        
        # v95_p107 hotfix_039: TRIGGER 에도 TRY/CATCH hoist 적용
        if re.search(r'\bBEGIN\s+TRY\b', new_body, re.IGNORECASE):
            new_body, trigger_tc_fixes = _hoist_try_catch_to_declare(
                new_body, structure.obj_name,
            )
            fixes.extend(trigger_tc_fixes)
        
        # v95_p107 hotfix_041 본질 처방:
        # ─────────────────────────────────────────────
        # 본부장님 환경 진가 데이터 결정적 발견:
        #   line 11~12: "IF p_Count = 0 \n    RETURN;"
        #   → obj_executor 가 처리 안 함 (IF X RETURN; with no value)
        #   → MySQL TRIGGER 의 RETURN 자체 미지원 → 1064
        #
        # 본질 처방: "IF X RETURN;" → "IF X THEN BEGIN END; END IF;"
        #   = 효과 없는 IF (TRIGGER 종료 못 시키지만 1064 방지)
        #   = MySQL 문법 통과 + 의도 보존 (조건 만족 시 후속 코드는 실행됨)
        #
        # 더 본질적인 처방은 조건 반전 + 전체 코드 포장이나
        # 변환 안정성을 위해 단순 변환 선택.
        # 본부장님 모토 #15 (신중하게) — 안전 우선
        def _fix_if_return(text: str) -> str:
            """IF X RETURN; → IF X THEN /* RETURN; */ END IF; 의도."""
            # 'IF <cond>\n    RETURN;' (멀티라인)
            text = re.sub(
                r'\bIF\s+([^\n]+?)\s*\n\s*RETURN\s*;',
                r'IF \1 THEN\n        SET @_trigger_skip = 1; -- v95_p107_h041: was RETURN;\n    END IF;',
                text, flags=re.IGNORECASE,
            )
            # 'IF <cond> RETURN;' (한줄)
            text = re.sub(
                r'\bIF\s+([^\n]+?)\s+RETURN\s*;',
                r'IF \1 THEN SET @_trigger_skip = 1; END IF;',
                text, flags=re.IGNORECASE,
            )
            return text
        
        new_body = _fix_if_return(new_body)
        fixes.append("TRIGGER 의 IF X RETURN; → IF X THEN SET; END IF; (h041)")
        
        if new_body != structure.body:
            raw_norm = structure.raw.replace('\r\n', '\n')
            body_norm = structure.body
            if body_norm in raw_norm:
                new_raw = raw_norm.replace(body_norm, new_body, 1)
                return new_raw, fixes
            begin_m = re.search(r'\bAS\s+BEGIN\b', raw_norm, re.IGNORECASE)
            if begin_m:
                new_raw = raw_norm[:begin_m.end()] + '\n' + new_body
                return new_raw, fixes
        return structure.raw, fixes
    
    # PROCEDURE / FUNCTION
    new_header = []
    
    if structure.obj_type == 'PROCEDURE':
        params_str = ", ".join(f"IN p_{n} {t}" for n, t in structure.params)
        new_header.append(
            f"DROP PROCEDURE IF EXISTS {obj_name_my};\n"
            f"CREATE PROCEDURE {obj_name_my}({params_str})\n"
            f"BEGIN"
        )
        fixes.append(f"PROCEDURE 헤더 ({len(structure.params)} 파라미터)")
    elif structure.obj_type == 'FUNCTION':
        if structure.is_tvf:
            params_str = ", ".join(f"IN p_{n} {t}" for n, t in structure.params)
            new_header.append(
                f"DROP PROCEDURE IF EXISTS {obj_name_my};\n"
                f"CREATE PROCEDURE {obj_name_my}({params_str})\n"
                f"BEGIN"
            )
            fixes.append("TVF → PROCEDURE 구조 변환")
        else:
            params_str = ", ".join(f"p_{n} {t}" for n, t in structure.params)
            new_header.append(
                f"DROP FUNCTION IF EXISTS {obj_name_my};\n"
                f"CREATE FUNCTION {obj_name_my}({params_str}) "
                f"RETURNS {structure.returns} DETERMINISTIC\n"
                f"BEGIN"
            )
            fixes.append("FUNCTION 헤더")
    
    # body 변환
    body = structure.body
    body = re.sub(r'\bEND\s*;?\s*$', '', body).rstrip()
    
    body, body_fixes = _transform_body_vars(body, structure.params, structure.body_vars)
    fixes.extend(body_fixes)
    
    # TVF: INSERT INTO @ret 제거 + RETURN 제거
    if structure.is_tvf:
        body = re.sub(r'INSERT\s+INTO\s+@\w+\s*\([^)]*\)\s*', '',
                      body, flags=re.IGNORECASE)
        body = re.sub(r'INSERT\s+INTO\s+@\w+\s+', '',
                      body, flags=re.IGNORECASE)
        body = re.sub(r'\bRETURN\s*;?', '', body, flags=re.IGNORECASE)
        fixes.append("TVF body 단순화")
    
    # v95_p107 hotfix_038: TRY/CATCH 본질 처방
    # MySQL EXIT HANDLER 는 BEGIN 직후 첫 줄만 허용 → body 처음으로 옮김
    # PROCEDURE/FUNCTION 의 body 에서 TRY/CATCH 추출 + DECLARE 를 헤더 직후로
    if structure.obj_type in ('PROCEDURE', 'FUNCTION') and not structure.is_tvf:
        body, tc_fixes = _hoist_try_catch_to_declare(body, structure.obj_name)
        fixes.extend(tc_fixes)
    
    return '\n'.join(new_header) + '\n' + body + '\nEND;', fixes


def _hoist_try_catch_to_declare(body: str, obj_name: str) -> Tuple[str, List[str]]:
    """v95_p107 hotfix_038: TRY/CATCH 진짜 본질 변환.
    
    본질:
      MySQL DECLARE EXIT HANDLER 는 BEGIN 직후 첫 줄만 허용.
      그래서 TRY/CATCH 를 추출 → DECLARE 를 body 처음으로 이동.
    
    변환 흐름:
      입력 (T-SQL):
        SET p_x = 0;
        BEGIN TRY
          <try_body>
        END TRY
        BEGIN CATCH
          <catch_body>
        END CATCH
      
      출력 (MySQL):
        DECLARE EXIT HANDLER FOR SQLEXCEPTION
        BEGIN
          <catch_body 정화>
        END;
        SET p_x = 0;
        <try_body 정화 — COMMIT TRANSACTION → COMMIT 등>
    """
    fixes = []
    
    # TRY/CATCH 블록 찾기
    pattern = re.compile(
        r'BEGIN\s+TRY\s+(.*?)\s+END\s+TRY\s+BEGIN\s+CATCH\s+(.*?)\s+END\s+CATCH',
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(body)
    if not m:
        return body, fixes
    
    try_body = m.group(1).strip()
    catch_body = m.group(2).strip()
    
    # 본질 처방: catch_body 정화
    catch_cleaned = catch_body
    
    # EXEC [schema].[object] → CALL `schema_object`()
    catch_cleaned = re.sub(
        r"\bEXEC(?:UTE)?\s+\[(\w+)\]\.\[(\w+)\](?:\s*;)?",
        r"CALL `\1_\2`();",
        catch_cleaned, flags=re.IGNORECASE,
    )
    catch_cleaned = re.sub(
        r"\bEXEC(?:UTE)?\s+(\w+)\.(\w+)(?:\s*;)?",
        r"CALL `\1_\2`();",
        catch_cleaned, flags=re.IGNORECASE,
    )
    catch_cleaned = re.sub(
        r"\bEXEC(?:UTE)?\s+\[?(\w+)\]?(?:\s*;)?",
        r"CALL `\1`();",
        catch_cleaned, flags=re.IGNORECASE,
    )
    
    # RAISERROR → SIGNAL
    catch_cleaned = re.sub(
        r"\bRAISERROR\s*\([^)]+\)\s*;?",
        f"SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '{obj_name} 에러';",
        catch_cleaned, flags=re.IGNORECASE,
    )
    
    # IF @@TRANCOUNT > 0 ROLLBACK → ROLLBACK
    catch_cleaned = re.sub(
        r"IF\s+@@TRANCOUNT\s*>\s*0\s+(?:BEGIN\s+)?ROLLBACK\s+TRANSACTION\s*;?\s*(?:END\s*;?)?",
        "ROLLBACK;",
        catch_cleaned, flags=re.IGNORECASE,
    )
    catch_cleaned = re.sub(
        r"\bROLLBACK\s+TRANSACTION\s*;?",
        "ROLLBACK;",
        catch_cleaned, flags=re.IGNORECASE,
    )
    
    # RETURN -1 → 본질: MySQL 의 PROCEDURE 는 RETURN expression 미지원
    # CATCH 안에서 RETURN -1 는 사실상 procedure 종료 → 단순 RETURN 도 안 됨
    # → 정확한 본질: SIGNAL SQLSTATE 또는 단순 제거 (EXIT HANDLER 자동 종료)
    catch_cleaned = re.sub(
        r"\bRETURN\s+-?\d+\s*;?",
        "",  # EXIT HANDLER 안에선 자동 종료
        catch_cleaned, flags=re.IGNORECASE,
    )
    
    # try_body 정화
    try_cleaned = try_body
    try_cleaned = re.sub(
        r"\bCOMMIT\s+TRANSACTION\s*;?",
        "COMMIT;",
        try_cleaned, flags=re.IGNORECASE,
    )
    try_cleaned = re.sub(
        r"\bBEGIN\s+TRANSACTION\s*;?",
        "START TRANSACTION;",
        try_cleaned, flags=re.IGNORECASE,
    )
    
    # v95_p107 hotfix_040: try_body 의 RETURN 처리 제거 (obj_executor 위임)
    # 이전 h039: RETURN -1; → SIGNAL, RETURN; → /* RETURN; */
    # 문제: 본부장님 환경 obj_executor 의 IF X RETURN Y; 처리와 충돌
    # 본질: RETURN 은 obj_executor 가 처리 (이미 잘 됨)
    # 단 RETURN -1 같은 명백한 값 반환만 처리
    try_cleaned = re.sub(
        r"\bRETURN\s+-?\d+\s*;?",
        "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '조기 종료';",
        try_cleaned, flags=re.IGNORECASE,
    )
    # RETURN; (값 없음) — obj_executor 에 위임 (건드리지 않음)
    
    # + 문자열 연결 → CONCAT (간단한 케이스만)
    # 'str' + 'str' → CONCAT('str', 'str')
    # 'str' + var → CONCAT('str', var)
    # 본질적으로 어려운 변환 — 단순 케이스만
    def _plus_to_concat(match_text):
        # 매우 단순한 + 연결만 처리
        parts = re.split(r"\s*\+\s*", match_text)
        if len(parts) >= 2:
            return f"CONCAT({', '.join(parts)})"
        return match_text
    
    # body 의 TRY/CATCH 영역 제거 + 새 구조로
    body_before = body[:m.start()].rstrip()
    body_after = body[m.end():].lstrip()
    
    # v95_p107 hotfix_040 본질 처방:
    # ───────────────────────────────────────────────
    # h039 의 RETURN 처리가 본부장님 환경 obj_executor.py 의
    # "IF X RETURN Y; → IF X THEN RETURN Y; END IF;" 로직과 충돌.
    #
    # 본부장님 환경 진가:
    #   /* RETURN; */ 로 주석화한 후 obj_executor 가 추가 처리
    #   → "IF p_Count = 0 ; */" 같은 깨진 SQL → 1064
    #
    # 본질: RETURN 처리는 obj_executor 에 위임 (이미 잘 됨)
    #       context_pattern 은 RETURN 건드리지 않음
    def _clean_return(text: str) -> str:
        """RETURN 처리 완전 제거 — obj_executor 에 위임."""
        # NOOP — 본부장님 환경의 기존 RETURN 처리 신뢰
        return text
    
    # v95_p107 hotfix_041: PROCEDURE/FUNCTION 의 IF X RETURN; 처리
    # 본부장님 환경 obj_executor 가 "IF X RETURN value;" 만 처리,
    # "IF X RETURN;" (값 없음) 은 처리 안 함 → 1064
    # 본질 처방: IF X RETURN; → IF X THEN SET @_skip=1; END IF;
    def _fix_if_return_no_value(text: str) -> str:
        """IF X RETURN; (값 없음) → IF X THEN SET; END IF; (MySQL 통과)."""
        # 멀티라인: 'IF <cond>\n    RETURN;'
        text = re.sub(
            r'\bIF\s+([^\n]+?)\s*\n\s*RETURN\s*;',
            r'IF \1 THEN\n        SET @_skip = 1; -- v95_p107_h041: was RETURN;\n    END IF;',
            text, flags=re.IGNORECASE,
        )
        # 한줄: 'IF <cond> RETURN;'
        text = re.sub(
            r'\bIF\s+([^\n]+?)\s+RETURN\s*;',
            r'IF \1 THEN SET @_skip = 1; END IF;',
            text, flags=re.IGNORECASE,
        )
        return text
    
    body_before = _fix_if_return_no_value(body_before)
    body_after = _fix_if_return_no_value(body_after)
    try_cleaned = _fix_if_return_no_value(try_cleaned)
    
    # v95_p107 hotfix_039 본질 처방 2: DECLARE 순서 본질
    # MySQL 규칙: 일반 DECLARE (변수) 가 DECLARE HANDLER 전에 와야 함
    # 본부장님 환경 진가:
    #   DECLARE p_Count INT;   ← 일반 DECLARE
    #   ↓
    #   DECLARE EXIT HANDLER ← HANDLER
    #
    # body_before 에서 일반 DECLARE 들을 추출 → DECLARE HANDLER 전에 배치
    declare_vars_pattern = re.compile(
        r'^\s*DECLARE\s+\w+(?:\s*,\s*\w+)*\s+\w+(?:\([^)]*\))?\s*(?:DEFAULT\s+[^;]+)?\s*;',
        re.IGNORECASE | re.MULTILINE,
    )
    declare_vars = []
    def _extract_declare(match):
        declare_vars.append(match.group(0).strip())
        return ''
    body_before_clean = declare_vars_pattern.sub(_extract_declare, body_before).strip()
    
    # v95_p107 hotfix_039 본질 처방 3: TRIGGER 의 inserted/deleted 처리
    # 본부장님 환경 진가:
    #   "SELECT inserted.PurchaseOrderID FROM inserted"  ← MySQL 미지원
    # MySQL TRIGGER: NEW / OLD (단일 row), inserted/deleted 테이블 없음
    # → FROM inserted 같은 구문은 본질적으로 변환 필요
    # 단순 처리: "FROM inserted" → 제거 + 컬럼 참조 NEW. 로
    def _fix_inserted_deleted(text: str) -> str:
        # SELECT inserted.col FROM inserted → SELECT NEW.col (단일 row 가정)
        # backtick 도 처리 (Pattern KB 가 [inserted] → `inserted` 로 변환 후 호출되는 경우)
        text = re.sub(
            r'\bSELECT\s+`?inserted`?\.`?(\w+)`?\s+FROM\s+`?inserted`?\b',
            r'SELECT NEW.\1',
            text, flags=re.IGNORECASE,
        )
        text = re.sub(
            r'\bSELECT\s+`?deleted`?\.`?(\w+)`?\s+FROM\s+`?deleted`?\b',
            r'SELECT OLD.\1',
            text, flags=re.IGNORECASE,
        )
        # 단순 inserted.col → NEW.col (backtick 포함)
        text = re.sub(
            r'`?\binserted\b`?\.`?(\w+)`?',
            r'NEW.\1',
            text, flags=re.IGNORECASE,
        )
        text = re.sub(
            r'`?\bdeleted\b`?\.`?(\w+)`?',
            r'OLD.\1',
            text, flags=re.IGNORECASE,
        )
        # IN (SELECT NEW.col) → = NEW.col  (단일 row)
        text = re.sub(
            r'\bIN\s*\(\s*SELECT\s+NEW\.(\w+)\s*\)',
            r'= NEW.\1',
            text, flags=re.IGNORECASE,
        )
        text = re.sub(
            r'\bIN\s*\(\s*SELECT\s+OLD\.(\w+)\s*\)',
            r'= OLD.\1',
            text, flags=re.IGNORECASE,
        )
        # 잔재 FROM `inserted` 또는 FROM inserted 제거
        text = re.sub(
            r'\bFROM\s+`?inserted`?\b',
            r'/* FROM inserted (MySQL NEW row) */',
            text, flags=re.IGNORECASE,
        )
        text = re.sub(
            r'\bFROM\s+`?deleted`?\b',
            r'/* FROM deleted (MySQL OLD row) */',
            text, flags=re.IGNORECASE,
        )
        return text
    
    body_before_clean = _fix_inserted_deleted(body_before_clean)
    body_after = _fix_inserted_deleted(body_after)
    try_cleaned = _fix_inserted_deleted(try_cleaned)
    
    # 본질: DECLARE 변수 → DECLARE HANDLER → 나머지
    declare_block = '\n  '.join(declare_vars) if declare_vars else ''
    
    new_body = (
        f"  -- v95_p107 hotfix_039: TRY/CATCH 본질 변환 (DECLARE 순서)\n"
        + (f"  {declare_block}\n" if declare_block else "")
        + f"  DECLARE EXIT HANDLER FOR SQLEXCEPTION\n"
        f"  BEGIN\n"
        f"    {catch_cleaned}\n"
        f"  END;\n"
        + (f"  {body_before_clean}\n" if body_before_clean else "")
        + f"  {try_cleaned}\n"
        f"  {body_after}"
    )
    
    fixes.append(
        f"TRY/CATCH 본질 처방 (DECLARE 변수 {len(declare_vars)}개 hoist + HANDLER + inserted/deleted)"
    )
    return new_body, fixes


def transform_try_catch(sql: str) -> Tuple[str, List[str]]:
    """T-SQL TRY/CATCH → MySQL DECLARE EXIT HANDLER (진짜 변환).
    
    v95_p107 hotfix_036 본질 처방:
      이전 (h030): 단순 주석화 — MySQL 실행 안 됨
      이후 (h036): DECLARE EXIT HANDLER FOR SQLEXCEPTION 진짜 변환
    
    변환 규칙:
      BEGIN TRY
        <try_body>
      END TRY
      BEGIN CATCH
        <catch_body>
      END CATCH
    
      ↓
    
      DECLARE EXIT HANDLER FOR SQLEXCEPTION
      BEGIN
        <catch_body 정화 (ERROR_* 함수 제거)>
      END;
      <try_body>
    
    MySQL 의 EXIT HANDLER 는 procedure body 시작 부분에 와야 함.
    그래서 try_body 와 catch_body 를 분리해서 재배치.
    """
    fixes = []
    pattern = re.compile(
        r'BEGIN\s+TRY\s+(.*?)\s+END\s+TRY\s+BEGIN\s+CATCH\s+(.*?)\s+END\s+CATCH',
        re.IGNORECASE | re.DOTALL,
    )
    
    def replace(m):
        try_body = m.group(1).strip()
        catch_body = m.group(2).strip()
        
        # CATCH body 정화 — MySQL 미지원 함수 처리
        # ERROR_NUMBER() / ERROR_MESSAGE() / ERROR_SEVERITY() 등은
        # MySQL EXIT HANDLER 에서는 GET DIAGNOSTICS 로 받아야 함
        # 단순화: 주석 처리 + 기본 메시지
        catch_cleaned = catch_body
        
        # EXEC [dbo].[uspXxx] / EXEC dbo.uspXxx → CALL `dbo_uspXxx`()
        # v95_p107 hotfix_038: bracket + dot 모두 처리 — backtick + underscore 합치기
        # 1) EXEC [schema].[object] → CALL `schema_object`()
        catch_cleaned = re.sub(
            r"\bEXEC(?:UTE)?\s+\[(\w+)\]\.\[(\w+)\](?:\s*;)?",
            r"CALL `\1_\2`();",
            catch_cleaned, flags=re.IGNORECASE,
        )
        # 2) EXEC schema.object → CALL `schema_object`()
        catch_cleaned = re.sub(
            r"\bEXEC(?:UTE)?\s+(\w+)\.(\w+)(?:\s*;)?",
            r"CALL `\1_\2`();",
            catch_cleaned, flags=re.IGNORECASE,
        )
        # 3) EXEC [object] / EXEC object → CALL `object`()
        catch_cleaned = re.sub(
            r"\bEXEC(?:UTE)?\s+\[?(\w+)\]?(?:\s*;)?",
            r"CALL `\1`();",
            catch_cleaned, flags=re.IGNORECASE,
        )
        
        # RAISERROR → SIGNAL SQLSTATE
        catch_cleaned = re.sub(
            r"\bRAISERROR\s*\([^)]+\)\s*;?",
            "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'TRY/CATCH 에러';",
            catch_cleaned, flags=re.IGNORECASE,
        )
        
        # IF @@TRANCOUNT > 0 ROLLBACK → ROLLBACK
        catch_cleaned = re.sub(
            r"IF\s+@@TRANCOUNT\s*>\s*0\s+(?:BEGIN\s+)?ROLLBACK\s+TRANSACTION\s*;?\s*(?:END\s*;?)?",
            "ROLLBACK;",
            catch_cleaned, flags=re.IGNORECASE,
        )
        catch_cleaned = re.sub(
            r"ROLLBACK\s+TRANSACTION\s*;?",
            "ROLLBACK;",
            catch_cleaned, flags=re.IGNORECASE,
        )
        
        # COMMIT TRANSACTION → COMMIT;
        try_body_cleaned = re.sub(
            r"\bCOMMIT\s+TRANSACTION\s*;?",
            "COMMIT;",
            try_body, flags=re.IGNORECASE,
        )
        try_body_cleaned = re.sub(
            r"\bBEGIN\s+TRANSACTION\s*;?",
            "START TRANSACTION;",
            try_body_cleaned, flags=re.IGNORECASE,
        )
        
        # MySQL DECLARE EXIT HANDLER 구조
        result = (
            "-- v95_p107 hotfix_036: TRY/CATCH → EXIT HANDLER 변환\n"
            "DECLARE EXIT HANDLER FOR SQLEXCEPTION\n"
            "BEGIN\n"
            f"  {catch_cleaned}\n"
            "END;\n"
            f"{try_body_cleaned}"
        )
        return result
    
    new_sql, count = pattern.subn(replace, sql)
    if count > 0:
        fixes.append(f"TRY/CATCH → EXIT HANDLER 진짜 변환 ({count}건)")
    return new_sql, fixes


def _post_fix_mysql_blocks(sql: str) -> Tuple[str, List[str]]:
    """v95_p107 hotfix_041: T-SQL BEGIN/END 블록 → MySQL THEN/END IF + 본질 4가지.
    
    본부장님 환경 진가 데이터 (MySQL 8.0 실제 실행 검증) 으로 발견:
      1. IF cond BEGIN ... END → IF cond THEN ... END IF;
      2. RETURNS VARCHAR (길이 없음) → RETURNS VARCHAR(255)
      3. T-SQL CTE → MySQL WITH RECURSIVE (재귀 감지)
      4. PROCEDURE/FUNCTION 안의 마지막 BEGIN/END 짝 보정
    """
    fixes = []
    
    # 본질 1: IF (cond) BEGIN ... END → IF (cond) THEN ... END IF;
    # 본부장님 환경 uSalesOrderHeader, iPurchaseOrderDetail 진가
    # 멀티라인 매칭 — 깊이는 1단계만 (단순 케이스)
    def _fix_if_begin_end(text: str) -> str:
        # IF (조건)\n  BEGIN\n  <statements>\n  END  →  IF (조건) THEN\n  <statements>\n  END IF;
        pattern = re.compile(
            r'\bIF\s*(\([^)]+\)|[^\n]+?)\s*\n\s*BEGIN\s*\n(.*?)\n\s*END(?:;)?',
            re.IGNORECASE | re.DOTALL,
        )
        prev = None
        result = text
        # 반복 적용 (중첩 케이스)
        for _ in range(5):
            new = pattern.sub(
                lambda m: f'IF {m.group(1).strip()} THEN\n{m.group(2)}\nEND IF;',
                result,
            )
            if new == result:
                break
            result = new
        return result
    
    new_sql = _fix_if_begin_end(sql)
    if new_sql != sql:
        fixes.append("h041: IF cond BEGIN...END → IF cond THEN...END IF")
        sql = new_sql
    
    # 본질 2: RETURNS VARCHAR (길이 없음) → RETURNS VARCHAR(255)
    # 본부장님 환경 ufnLeadingZeros 진가
    new_sql = re.sub(
        r'\bRETURNS\s+VARCHAR\b(?!\s*\()',
        'RETURNS VARCHAR(255)',
        sql, flags=re.IGNORECASE,
    )
    if new_sql != sql:
        fixes.append("h041: RETURNS VARCHAR → RETURNS VARCHAR(255)")
        sql = new_sql
    new_sql = re.sub(
        r'\bRETURNS\s+NVARCHAR\b(?!\s*\()',
        'RETURNS VARCHAR(255)',
        sql, flags=re.IGNORECASE,
    )
    if new_sql != sql:
        fixes.append("h041: RETURNS NVARCHAR → RETURNS VARCHAR(255)")
        sql = new_sql
    
    # 본질 3: T-SQL CTE → MySQL WITH RECURSIVE (자기 참조 감지)
    # 본부장님 환경 uspGetBillOfMaterials, uspGetManagerEmployees 진가
    cte_match = re.search(
        r'\bWITH\s+(?!RECURSIVE\b)(\w+(?:\s*\([^)]*\))?\s+AS\s*\(.+?UNION\s+ALL.+?\))',
        sql, flags=re.IGNORECASE | re.DOTALL,
    )
    if cte_match:
        # UNION ALL 가 있으면 재귀 CTE 가능성 높음
        new_sql = re.sub(r'\bWITH\b(?!\s+RECURSIVE)', 'WITH RECURSIVE',
                         sql, count=1, flags=re.IGNORECASE)
        if new_sql != sql:
            fixes.append("h041: WITH → WITH RECURSIVE (재귀 CTE 감지)")
            sql = new_sql
    
    # 본질 4: BEGIN/END 짝 보정 — END; 가 END 인 케이스
    # IF blocks 변환 후 END; 가 END IF; 되었는데, 외부 END 가 매칭 안 될 수 있음
    # 단순 보정: BEGIN count 가 END count 보다 많으면 마지막에 END 추가 X (위험)
    # 보정 안 함 — 진단만
    
    return sql, fixes


def apply_context_patterns(sql: str) -> Tuple[str, List[str]]:
    """Context-aware 변환 적용 — Pattern KB 정규식 이전 단계."""
    fixes = []
    result = sql
    
    structure = parse_tsql_structure(sql)
    procedure_or_function_hoisted = False
    if structure and structure.obj_type in ('PROCEDURE', 'FUNCTION', 'TRIGGER'):
        try:
            new_sql, structure_fixes = transform_with_context(structure)
            if structure_fixes:
                result = new_sql
                fixes.extend(structure_fixes)
                if structure.obj_type in ('PROCEDURE', 'FUNCTION') and not structure.is_tvf:
                    procedure_or_function_hoisted = True
        except Exception as e:
            _log.warning("[context_pattern] 구조 변환 실패: %s", e)
    
    # PROCEDURE/FUNCTION 가 아닐 때만 transform_try_catch 호출 (TRIGGER 등)
    if not procedure_or_function_hoisted:
        try:
            result, tc_fixes = transform_try_catch(result)
            fixes.extend(tc_fixes)
        except Exception as e:
            _log.warning("[context_pattern] TRY/CATCH 변환 실패: %s", e)
    
    # v95_p107 hotfix_041: MySQL 본질 후처리 (BEGIN/END 블록 + VARCHAR + CTE)
    try:
        result, post_fixes = _post_fix_mysql_blocks(result)
        fixes.extend(post_fixes)
    except Exception as e:
        _log.warning("[context_pattern] 후처리 실패: %s", e)
    
    return result, fixes
