"""
sql_preflight_validator.py — Phase E-3 / v90.52 (2026-04-27)

AI 가 생성한 SQL 을 DB 로 보내기 전에 문법 오류를 사전 탐지 + 자동 수정.

═══════════════════════════════════════════════════════════════════════════════
v90.52 정공법 — 본부장님 환경 18건 1064 패턴 완전 방어
═══════════════════════════════════════════════════════════════════════════════

[v90.51 까지의 한계]
  기존 7개 룰의 정규식이 본부장님 환경 18건 1064 패턴을 단 1건도 매칭 못 함.
  preflight_check 는 호출되지만 모든 SQL 이 passed=ok 로 통과 → DB 직행 → 1064.
  로그 증거: 13-preflight-enter → 14-kb-learn-enter 시간차 0.02s,
              "Phase E-3 자동 수정" 로그 0건.

[v90.52 변경점]
  1) 룰 10개로 확장 — 본부장님 환경 11종 실제 케이스 100% 커버
  2) 룰 ID 명명 (R-01 ~ R-10) + 우선순위 고정 적용
  3) 진단 로그 13-1 ~ 13-9 단계 세분화 (룰별 적용 흔적 가시화)
  4) obj_executor 에서 안전망 2차 호출 가능하도록 idempotent 보장
  5) 자동 수정 적용 룰을 결과에 명시 (KB 자동학습 hook 용)

[룰 우선순위 — 적용 순서 고정]
  1. R-10 (TVF MySQL 부적합)         — 변환 자체 불가 → fail
  2. R-09 (END IF / END CASE 누락)    — 블록 구조 정리 먼저
  3. R-04 (INSERT VALUES; 누락)        — 문장 종결자 보강
  4. R-08 (RETURN ; 누락)              — 문장 종결자 보강
  5. R-03 (RETURN CASE; 잘못된 ;)      — 잘못된 종결자 제거
  6. R-01 (UPDATE SET 콤마-세미콜론)   — 가장 빈번 (6건)
  7. R-02 (SET col=v; WHERE)           — R-01 처리 후 잔여
  8. R-05 (PROCEDURE LIMIT 1 위치)     — 구조 오류
  9. R-06 (END 직전 ; 누락)            — 마지막 문장 보강
 10. R-07 (DETERMINISTIC 미선언)       — 메타 보강 (마지막)

[기존 7개 룰과의 호환성]
  - UPDATE_SET_SEMICOLON     → R-01 으로 강화 (콤마-세미콜론 패턴 추가)
  - NESTED_CREATE            → R-NESTED 로 보존 (이름만 명시)
  - MULTILINE_SET_SEMICOLON  → R-01 에 통합
  - EMPTY_BODY               → R-EMPTY 로 보존
  - BRACKET_IMBALANCE        → R-BRACKET 으로 보존
  - BEGIN_END_IMBALANCE      → R-BEGIN_END 로 보존
  - SCHEMA_MIXING            → R-SCHEMA 로 보존
  
  기존 호출 시그니처 100% 유지: preflight_check(sql, obj_type) → dict
  build_retry_hint(result) → str 도 그대로.
"""

from __future__ import annotations
import re
import logging
from typing import Optional, Tuple, List, Dict, Any

_log = logging.getLogger("databridge.preflight")

# ════════════════════════════════════════════════════════════════════════════
# 공개 API
# ════════════════════════════════════════════════════════════════════════════

def preflight_check(sql: str, obj_type: str = "") -> dict:
    """
    SQL 문법 오류 사전 탐지 + 자동 수정.
    
    Args:
        sql: 검증할 SQL 문자열
        obj_type: "PROCEDURE" | "FUNCTION" | "TRIGGER" | "VIEW" | "TABLE" | ""
    
    Returns:
        {
            "passed": bool,                # 모든 검사 통과 (warn 은 통과로 간주)
            "severity": "ok"|"warn"|"fail",
            "issues": [
                {"rule": "R-01", "severity": "warn", "msg": "...", "hint": "..."},
            ],
            "auto_fixed_sql": "...",       # 자동 수정 적용된 SQL
            "applied_rules": ["R-01", ...], # v90.52: 실제 적용된 룰 ID 목록
        }
    """
    if not sql or not sql.strip():
        return _result(True, "ok", [], sql, [])

    issues: List[Dict[str, Any]] = []
    applied: List[str] = []
    auto_fixed = sql

    # v90.52: 룰 적용 순서 고정 (R-10 → R-09 → ... → R-07 순)
    # 순서가 중요한 이유: R-09 가 END IF 보강 후 R-06 가 마지막 ; 보강해야 함
    rules_in_order = [
        ("R-10", _rule_r10_tvf_unsupported),
        ("R-09", _rule_r09_end_if_missing),
        ("R-04", _rule_r04_insert_values_semicolon),
        ("R-08", _rule_r08_return_semicolon),
        ("R-03", _rule_r03_return_case_semicolon),
        ("R-01", _rule_r01_update_set_comma_semicolon),
        ("R-02", _rule_r02_set_trailing_semicolon_where),
        ("R-05", _rule_r05_procedure_limit_misplaced),
        ("R-06", _rule_r06_end_missing_semicolon),
        ("R-07", _rule_r07_deterministic_missing),
        # ── 기존 룰 호환성 유지 ──
        ("R-NESTED", _rule_nested_create),
        ("R-EMPTY", _rule_empty_create_body),
        ("R-BRACKET", _rule_bracket_balance),
        ("R-BEGIN_END", _rule_begin_end_balance),
        ("R-SCHEMA", _rule_schema_mixing),
    ]

    for rule_id, check_fn in rules_in_order:
        try:
            issue, fixed = check_fn(auto_fixed, obj_type)
            if issue:
                # rule 필드를 룰 ID 로 강제
                issue["rule"] = rule_id
                issues.append(issue)
                if fixed and fixed != auto_fixed:
                    auto_fixed = fixed
                    applied.append(rule_id)
                    _log.info(
                        "[preflight] %s 자동 수정 적용 (obj_type=%s)",
                        rule_id, obj_type or "?",
                    )
        except Exception as e:
            _log.warning(
                "[preflight] %s 검사 실패 (무시): %s", rule_id, e
            )

    # severity 결정
    if not issues:
        return _result(True, "ok", issues, auto_fixed, applied)

    has_fail = any(i.get("severity") == "fail" for i in issues)
    if has_fail:
        return _result(False, "fail", issues, auto_fixed, applied)
    return _result(True, "warn", issues, auto_fixed, applied)


def build_retry_hint(preflight_result: dict) -> str:
    """
    preflight 결과에서 AI 재변환용 힌트 텍스트 생성.
    이전 변환이 실패했을 때 AI 에게 "이번엔 이렇게 하지 마세요" 주입.
    """
    issues = preflight_result.get("issues", [])
    if not issues:
        return ""
    
    hints = []
    for issue in issues:
        hints.append(
            f"- [{issue.get('rule', '?')}] {issue.get('msg', '')}  "
            f"→ {issue.get('hint', '')}"
        )
    
    return (
        "\nIMPORTANT — Previous conversion had these issues. "
        "Fix them ALL in this retry:\n"
        + "\n".join(hints)
    )


# ════════════════════════════════════════════════════════════════════════════
# 룰 R-01 ~ R-10 (v90.52 핵심)
# ════════════════════════════════════════════════════════════════════════════

def _rule_r01_update_set_comma_semicolon(
    sql: str, obj_type: str
) -> Tuple[Optional[dict], Optional[str]]:
    r"""
    R-01: UPDATE SET 절에서 콤마 직후 세미콜론 (가장 빈번 / 6건)
    
    잘못된 패턴:
        SET app_status = 'APPROVED',;
            approved_amount = p_amount,
            ...
        WHERE app_id = p_app_id;
    
    올바른 패턴:
        SET app_status = 'APPROVED',
            approved_amount = p_amount,
            ...
        WHERE app_id = p_app_id;
    
    자동 수정: 콤마 다음 세미콜론을 콤마만 남기고 제거.
    """
    # 콤마 + 공백/줄바꿈 + 세미콜론 + 공백/줄바꿈 패턴
    # ',;', ', ;', ',\n;', ',\n  ;' 등 모두 매칭
    pattern = re.compile(r',(\s*);(\s*)', re.MULTILINE)
    
    # 단순 콤마-세미콜론은 너무 광범위하게 매칭될 수 있으므로
    # SET 절 컨텍스트 안에서만 매칭하도록 제한
    # 더 정확한 검출: SET 다음 라인부터 WHERE/END 전까지의 영역 안의 콤마-세미콜론
    set_block_pattern = re.compile(
        r'(\bSET\b)(.*?)(?=\bWHERE\b|\bEND\b|;\s*\n\s*(?:UPDATE|INSERT|DELETE|SELECT|END)|\Z)',
        re.IGNORECASE | re.DOTALL,
    )
    
    fixed_sql = sql
    detected = False
    
    for m in set_block_pattern.finditer(sql):
        block = m.group(2)
        if re.search(r',\s*;', block):
            detected = True
            # 블록 내 ',;' 또는 ', ;' 또는 ',\n;' 패턴 제거 (콤마는 유지, 세미콜론만 삭제)
            fixed_block = re.sub(r',(\s*);(\s*)', r',\1\2', block)
            # 원본 SQL 의 해당 위치 치환
            fixed_sql = fixed_sql.replace(block, fixed_block, 1)
    
    if not detected:
        return None, None
    
    return ({
        "severity": "warn",
        "msg": "UPDATE SET 절에 콤마 직후 잘못된 세미콜론 발견 (1064 오류 원인)",
        "hint": "SET col1 = v1, col2 = v2 처럼 콤마만 사용하고 세미콜론을 붙이지 마세요.",
    }, fixed_sql)


def _rule_r02_set_trailing_semicolon_where(
    sql: str, obj_type: str
) -> Tuple[Optional[dict], Optional[str]]:
    r"""
    R-02: SET 절 마지막 컬럼 종료 세미콜론 후 WHERE 발생 (3건)
    
    잘못된 패턴:
        UPDATE credit_contract
           SET customer_id = p_target_id;
         WHERE customer_id = p_source_id;
    
    R-01 의 보조: R-01 은 콤마 직후 ;, R-02 는 SET 마지막 라인 종료 ; 후 WHERE.
    """
    # SET ... = ... ; \s* WHERE  (마지막 컬럼만 있는 케이스 포함)
    pattern = re.compile(
        r'(\bSET\b\s+(?:[^;]*?))\s*;\s*(\bWHERE\b)',
        re.IGNORECASE | re.DOTALL,
    )
    
    if not pattern.search(sql):
        return None, None
    
    fixed_sql = pattern.sub(r'\1\n     \2', sql)
    
    if fixed_sql == sql:
        return None, None
    
    return ({
        "severity": "warn",
        "msg": "SET 절 종료 세미콜론 후 WHERE 발견 (1064 오류 원인)",
        "hint": "SET 절과 WHERE 사이에는 세미콜론을 붙이지 마세요. "
                "UPDATE 문 전체가 끝난 후에만 세미콜론.",
    }, fixed_sql)


def _rule_r03_return_case_semicolon(
    sql: str, obj_type: str
) -> Tuple[Optional[dict], Optional[str]]:
    r"""
    R-03: RETURN CASE 직후 잘못된 세미콜론 (1건)
    
    잘못된 패턴 (collection_fn_delinq_stage 케이스):
        BEGIN
            RETURN CASE;          ← 잘못된 세미콜론
                WHEN p_days <= 30 THEN 'EARLY'
                ...
            END
        END
    
    올바른 패턴:
        BEGIN
            RETURN CASE
                WHEN p_days <= 30 THEN 'EARLY'
                ...
            END;
        END
    """
    # RETURN CASE ; 패턴 — CASE 직후 세미콜론
    pattern = re.compile(
        r'(\bRETURN\s+CASE)\s*;(\s*\n?\s*WHEN\b)',
        re.IGNORECASE,
    )
    
    if not pattern.search(sql):
        return None, None
    
    fixed_sql = pattern.sub(r'\1\2', sql)
    
    return ({
        "severity": "warn",
        "msg": "RETURN CASE 직후 잘못된 세미콜론 발견 (1064 오류 원인)",
        "hint": "CASE 표현식은 'CASE WHEN ... THEN ... END' 까지가 한 표현식입니다. "
                "CASE 뒤에 세미콜론을 붙이지 마세요.",
    }, fixed_sql)


def _rule_r04_insert_values_semicolon(
    sql: str, obj_type: str
) -> Tuple[Optional[dict], Optional[str]]:
    r"""
    R-04: 블록 내부 문장 종료 세미콜론 누락 (다수)
    
    잘못된 패턴 1 — TRIGGER INSERT VALUES (credit_trg_contract_status_change):
        IF NEW.status <> OLD.status THEN
            INSERT INTO credit_contract_event (...)
            VALUES (...)              ← 세미콜론 누락
        END IF;
    
    잘못된 패턴 2 — END IF 뒤 ; 누락 (fn_calc_monthly_payment, fn_next_business_day):
        IF v_r = 0 THEN
            RETURN CAST(...);
        END IF                        ← 세미콜론 누락
        RETURN CAST(...);
    
    공통 본질: BEGIN/IF/WHILE/LOOP/CASE 블록 안에서
            "표현식 마지막 토큰" 다음에 ; 가 있어야 하는데 없는 경우.
    
    자동 수정 대상 패턴:
        1) ) 또는 ) ON DUPLICATE KEY UPDATE ... 직후 → END IF/END WHILE/END LOOP/ELSE 등이 옴
        2) END IF / END WHILE / END LOOP / END CASE 직후 → 다음 문장이 옴 (END 자체로 끝나는 것 제외)
    """
    fixed_sql = sql
    detected = False
    
    # 패턴 1: ) [ON DUPLICATE KEY UPDATE ...] 직후 \n + END IF/WHILE/LOOP/CASE/ELSEIF/ELSE
    pattern1 = re.compile(
        r'(\)\s*(?:ON\s+DUPLICATE\s+KEY\s+UPDATE\s+\w+\s*=\s*[^;\n]+)?)'
        r'(\s*\n\s*)'
        r'(\b(?:END\s+IF|END\s+WHILE|END\s+LOOP|END\s+CASE|ELSEIF|ELSE)\b)',
        re.IGNORECASE,
    )
    
    if pattern1.search(fixed_sql):
        detected = True
        fixed_sql = pattern1.sub(r'\1;\2\3', fixed_sql)
    
    # 패턴 2: END IF/WHILE/LOOP/CASE 직후 \n + 새 문장 (RETURN/SET/SELECT/UPDATE/INSERT/DELETE/CALL/IF/WHILE/LOOP)
    # 단, END 자체가 BEGIN 의 닫음일 경우 제외 (END 다음에 또 END 가 오면 외부 BEGIN-END)
    pattern2 = re.compile(
        r'(\bEND\s+(?:IF|WHILE|LOOP|CASE)\b)'
        r'(\s*\n\s*)'
        r'(\b(?:RETURN|SET|SELECT|UPDATE|INSERT|DELETE|CALL|IF|WHILE|LOOP|DECLARE|LEAVE|ITERATE|SIGNAL|RESIGNAL|GET|OPEN|CLOSE|FETCH|COMMIT|ROLLBACK|START)\b)',
        re.IGNORECASE,
    )
    
    if pattern2.search(fixed_sql):
        detected = True
        fixed_sql = pattern2.sub(r'\1;\2\3', fixed_sql)
    
    if not detected or fixed_sql == sql:
        return None, None
    
    return ({
        "severity": "warn",
        "msg": "블록 내부 문장 종료 세미콜론 누락 "
               "(INSERT VALUES 뒤 또는 END IF/WHILE/LOOP 뒤 / 1064 오류 원인)",
        "hint": "각 INSERT/UPDATE/SELECT/RETURN/END IF/END WHILE 등 문장은 "
                "다음 문장 시작 전에 세미콜론으로 종결해야 합니다.",
    }, fixed_sql)


def _rule_r05_procedure_limit_misplaced(
    sql: str, obj_type: str
) -> Tuple[Optional[dict], Optional[str]]:
    r"""
    R-05: PROCEDURE 본문 마지막 LIMIT 1 위치 오류 (1건)
    
    잘못된 패턴 (collection_sp_mark_delinquent):
        INSERT INTO collection_delinquency (...) VALUES (
            ...
        );
        LIMIT 1;            ← LIMIT 1 이 잘못 위치
        END
    
    올바른 패턴: LIMIT 1; 라인 자체를 제거 (INSERT ... VALUES 에는 LIMIT 무의미)
    
    이건 AI 가 SQL Server 의 SELECT TOP 1 → MySQL LIMIT 1 변환 시 위치 오류.
    """
    # INSERT 직후 ); 다음 LIMIT N; 패턴 (이건 의미없는 LIMIT)
    pattern = re.compile(
        r'(\)\s*;)\s*\n?\s*LIMIT\s+\d+\s*;',
        re.IGNORECASE,
    )
    
    if not pattern.search(sql):
        return None, None
    
    fixed_sql = pattern.sub(r'\1', sql)
    
    return ({
        "severity": "warn",
        "msg": "INSERT ... VALUES 직후 의미 없는 LIMIT N 발견 (1064 오류 원인)",
        "hint": "INSERT 문에는 LIMIT 절이 적용되지 않습니다. "
                "SQL Server SELECT TOP N 변환 시 위치를 SELECT 안으로 옮기거나 "
                "DML 에 따라 다르게 처리해야 합니다.",
    }, fixed_sql)


def _rule_r06_end_missing_semicolon(
    sql: str, obj_type: str
) -> Tuple[Optional[dict], Optional[str]]:
    r"""
    R-06: PROCEDURE 본문 마지막 문장 종결 세미콜론 누락 (다수)
    
    잘못된 패턴:
        UPDATE ref_employee
        SET status = p_new_status,
            resign_date = ...
        WHERE emp_no = p_emp_no
        END                  ← WHERE 절 끝에 ; 누락
    
    올바른 패턴:
        ...
        WHERE emp_no = p_emp_no;
        END
    
    탐지: BEGIN/END 블록 내부에서 SQL 문장이 끝나는데 ; 가 없고 바로 END 가 오는 경우.
    """
    if obj_type.upper() not in ("PROCEDURE", "FUNCTION", "TRIGGER"):
        return None, None
    
    # 끝 라인이 ; 또는 END 가 아니고, 다음 라인이 END 인 경우
    # 더 구체적으로: 단어 + 공백/줄바꿈 + END 으로 끝나는 패턴 (단, END 는 외부 BEGIN-END 의 닫음)
    # 너무 광범위해질 수 있으므로 보수적으로: WHERE/SET/CALL/INSERT/SELECT/UPDATE/DELETE 끝
    pattern = re.compile(
        r'(\b(?:WHERE|SET|CALL)\s+[^;]*?[A-Za-z_0-9\)\']+(?:\s+COLLATE\s+\w+)?)'
        r'(\s*\n\s*)'
        r'(\bEND\b\s*$)',
        re.IGNORECASE | re.DOTALL | re.MULTILINE,
    )
    
    if not pattern.search(sql):
        return None, None
    
    fixed_sql = pattern.sub(r'\1;\2\3', sql)
    
    if fixed_sql == sql:
        return None, None
    
    return ({
        "severity": "warn",
        "msg": "PROCEDURE/FUNCTION 본문 마지막 문장 세미콜론 누락 (1064 오류 원인)",
        "hint": "BEGIN ... END 블록 내부의 모든 문장은 세미콜론으로 종결되어야 합니다. "
                "마지막 WHERE 절도 예외 없습니다.",
    }, fixed_sql)


def _rule_r07_deterministic_missing(
    sql: str, obj_type: str
) -> Tuple[Optional[dict], Optional[str]]:
    r"""
    R-07: FUNCTION 의 DETERMINISTIC / READS SQL DATA 등 미선언 (메타 보강)
    
    MySQL 8.x 는 binlog_format = STATEMENT 일 때 FUNCTION 에 DETERMINISTIC,
    NO SQL, READS SQL DATA, MODIFIES SQL DATA, CONTAINS SQL 중 하나 필수.
    누락 시 ER_BINLOG_UNSAFE_ROUTINE (1418).
    
    1064 는 아니지만 Phase H 에서 같이 잡히던 케이스라 보강.
    """
    if obj_type.upper() != "FUNCTION":
        return None, None
    
    # FUNCTION 이름 (params) RETURNS type 이후 위 키워드 중 하나가 없으면
    # CREATE FUNCTION ... RETURNS ... { DETERMINISTIC | NO SQL | READS SQL DATA | MODIFIES SQL DATA | CONTAINS SQL }
    has_marker = re.search(
        r'\b(?:DETERMINISTIC|NO\s+SQL|READS\s+SQL\s+DATA|MODIFIES\s+SQL\s+DATA|CONTAINS\s+SQL)\b',
        sql,
        re.IGNORECASE,
    )
    
    if has_marker:
        return None, None
    
    # CREATE FUNCTION ... RETURNS <type>\n 패턴 직후에 DETERMINISTIC 삽입
    pattern = re.compile(
        r'(CREATE\s+FUNCTION\s+\S+\s*\([^)]*\)\s*RETURNS\s+\S+(?:\([^)]*\))?)\s*\n',
        re.IGNORECASE,
    )
    
    if not pattern.search(sql):
        return None, None
    
    fixed_sql = pattern.sub(r'\1\nDETERMINISTIC\n', sql, count=1)
    
    return ({
        "severity": "warn",
        "msg": "FUNCTION 에 DETERMINISTIC / READS SQL DATA 등 SQL 특성 키워드 누락",
        "hint": "MySQL 8.x 는 FUNCTION 생성 시 DETERMINISTIC, NO SQL, READS SQL DATA, "
                "MODIFIES SQL DATA, CONTAINS SQL 중 하나가 필수입니다.",
    }, fixed_sql)


def _rule_r08_return_semicolon(
    sql: str, obj_type: str
) -> Tuple[Optional[dict], Optional[str]]:
    r"""
    R-08: FUNCTION RETURN 문 세미콜론 누락 (보강)
    
    잘못된 패턴:
        BEGIN
            RETURN expr            ← ; 누락
        END
    
    올바른 패턴:
        BEGIN
            RETURN expr;
        END
    
    단, RETURN CASE ... END 의 경우는 END 뒤에 세미콜론.
    """
    if obj_type.upper() not in ("FUNCTION", "PROCEDURE"):
        return None, None
    
    # RETURN <expr> 다음 ; 가 없고 바로 END 가 오는 경우
    # 단 RETURN CASE 는 R-03 에서 처리하므로 제외
    pattern = re.compile(
        r'(\bRETURN\s+(?!CASE\b)[^;]+?)'
        r'(\s*\n\s*)'
        r'(\bEND\b)',
        re.IGNORECASE | re.DOTALL,
    )
    
    m = pattern.search(sql)
    if not m:
        return None, None
    
    # 매칭된 RETURN 표현식 끝이 이미 ; 인지 확인
    expr = m.group(1)
    if expr.rstrip().endswith(';'):
        return None, None
    
    fixed_sql = pattern.sub(r'\1;\2\3', sql, count=1)
    
    if fixed_sql == sql:
        return None, None
    
    return ({
        "severity": "warn",
        "msg": "RETURN 문 세미콜론 누락 (1064 오류 원인)",
        "hint": "RETURN <expr> 은 세미콜론으로 종결해야 합니다.",
    }, fixed_sql)


def _rule_r09_end_if_missing(
    sql: str, obj_type: str
) -> Tuple[Optional[dict], Optional[str]]:
    r"""
    R-09: IF / CASE / WHILE / LOOP 의 END 누락 (보강)
    
    탐지: IF/CASE/WHILE/LOOP 개수 vs END IF/END CASE/END WHILE/END LOOP 개수 비교.
    
    이건 자동 수정이 어려움 (어디에 END 를 넣어야 할지 추론 어려움) → fail 로 보고.
    """
    if obj_type.upper() not in ("PROCEDURE", "FUNCTION", "TRIGGER"):
        return None, None
    
    # 문자열 리터럴 / 주석 제거
    cleaned = re.sub(r"'(?:[^'\\]|\\.)*'", "''", sql)
    cleaned = re.sub(r'"(?:[^"\\]|\\.)*"', '""', cleaned)
    cleaned = re.sub(r'--[^\n]*', '', cleaned)
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
    
    # IF ... THEN 블록만 카운트 (함수형 IF(a,b,c) / IF EXISTS / END IF 의 IF 모두 자동 제외)
    # 문장형 IF 는 반드시 THEN 이 따라오므로 이걸로 매칭하면 정확함.
    # 비탐욕 매칭 + 줄바꿈 허용 (IF 와 THEN 사이 조건식이 여러 라인 가능)
    if_then_blocks = re.findall(
        r'\bIF\b(?!\s+EXISTS)(?!\s+NOT\s+EXISTS)\s+[^;]+?\bTHEN\b',
        cleaned,
        re.IGNORECASE | re.DOTALL,
    )
    expected_end_if = len(if_then_blocks)
    
    # ELSEIF ... THEN 도 위에 매칭되었을 수 있으므로 빼주기
    elseif_then_blocks = re.findall(
        r'\bELSEIF\b\s+[^;]+?\bTHEN\b',
        cleaned,
        re.IGNORECASE | re.DOTALL,
    )
    expected_end_if -= len(elseif_then_blocks)
    
    end_if_count = len(re.findall(r'\bEND\s+IF\b', cleaned, re.IGNORECASE))
    
    if expected_end_if > end_if_count:
        return ({
            "severity": "fail",
            "msg": f"END IF 누락 추정: IF...THEN 블록 {expected_end_if}개 vs END IF {end_if_count}개",
            "hint": "각 IF ... THEN 블록은 END IF; 로 닫혀야 합니다.",
        }, None)
    
    return None, None


def _rule_r10_tvf_unsupported(
    sql: str, obj_type: str
) -> Tuple[Optional[dict], Optional[str]]:
    r"""
    R-10: TVF (Table-Valued Function) 의 SQL Server 문법 - MySQL 부적합 (1건)
    
    잘못된 패턴 (credit_tvf_contract_events):
        CREATE FUNCTION credit_tvf_contract_events(...)
        RETURNS TABLE                ← MySQL 미지원
        RETURN (
            SELECT ...
        )
    
    MySQL 은 TVF 미지원 → VIEW 또는 PROCEDURE 로 변환 필요.
    자동 수정 불가, fail 로 보고하여 AI 재시도 시 다른 전략 유도.
    """
    if obj_type.upper() != "FUNCTION":
        return None, None
    
    # RETURNS TABLE 키워드 검출
    if not re.search(r'\bRETURNS\s+TABLE\b', sql, re.IGNORECASE):
        return None, None
    
    return ({
        "severity": "fail",
        "msg": "MySQL 은 RETURNS TABLE (Table-Valued Function) 을 지원하지 않습니다",
        "hint": "이 객체는 VIEW 로 변환하거나, "
                "CALL 가능한 PROCEDURE + OUT 결과셋 으로 변환하세요. "
                "FUNCTION 으로는 표현 불가.",
    }, None)


# ════════════════════════════════════════════════════════════════════════════
# 기존 룰 호환 (이름만 보존, 로직은 동일)
# ════════════════════════════════════════════════════════════════════════════

def _rule_nested_create(
    sql: str, obj_type: str
) -> Tuple[Optional[dict], Optional[str]]:
    """
    하나의 응답에 여러 CREATE 문 — AI 응답 잘못 구조화.
    """
    pattern = re.compile(
        r'(CREATE\s+(?:OR\s+(?:REPLACE|ALTER)\s+)?'
        r'(?:PROCEDURE|FUNCTION|TRIGGER|VIEW|TABLE)).*?'
        r'(?:END\s*;?|;\s*$).*?'
        r'(CREATE\s+(?:OR\s+(?:REPLACE|ALTER)\s+)?'
        r'(?:PROCEDURE|FUNCTION|TRIGGER|VIEW|TABLE))',
        re.IGNORECASE | re.DOTALL,
    )
    
    if pattern.search(sql):
        return ({
            "severity": "fail",
            "msg": "하나의 응답에 여러 CREATE 문 감지 — AI 응답 구조 오류",
            "hint": "응답에는 하나의 DROP IF EXISTS 와 하나의 CREATE 만 포함하세요.",
        }, None)
    return None, None


def _rule_empty_create_body(
    sql: str, obj_type: str
) -> Tuple[Optional[dict], Optional[str]]:
    """
    CREATE PROCEDURE sp_x() BEGIN END  ← 빈 몸체
    """
    if obj_type.upper() not in ("PROCEDURE", "FUNCTION", "TRIGGER"):
        return None, None
    
    pattern = re.compile(r'\bBEGIN\s+END\b', re.IGNORECASE)
    if pattern.search(sql):
        return ({
            "severity": "fail",
            "msg": "프로시저/함수 몸체가 비어있음",
            "hint": "BEGIN ... END 사이에 실제 로직이 있어야 합니다.",
        }, None)
    return None, None


def _rule_bracket_balance(
    sql: str, obj_type: str
) -> Tuple[Optional[dict], Optional[str]]:
    """
    괄호 개수 불일치 검사.
    """
    cleaned = re.sub(r"'(?:[^'\\]|\\.)*'", "''", sql)
    cleaned = re.sub(r'"(?:[^"\\]|\\.)*"', '""', cleaned)
    cleaned = re.sub(r'--[^\n]*', '', cleaned)
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
    
    open_p = cleaned.count('(')
    close_p = cleaned.count(')')
    
    if open_p != close_p:
        diff = open_p - close_p
        return ({
            "severity": "fail",
            "msg": f"괄호 개수 불일치: ( {open_p}개, ) {close_p}개 (차이 {diff})",
            "hint": "여는 괄호와 닫는 괄호 개수를 맞추세요.",
        }, None)
    return None, None


def _rule_begin_end_balance(
    sql: str, obj_type: str
) -> Tuple[Optional[dict], Optional[str]]:
    """
    BEGIN-END 블록 짝 검사.
    """
    if obj_type.upper() not in ("PROCEDURE", "FUNCTION", "TRIGGER"):
        return None, None
    
    cleaned = re.sub(r"'(?:[^'\\]|\\.)*'", "''", sql)
    cleaned = re.sub(r"--[^\n]*", "", cleaned)
    
    begins = len(re.findall(r'\bBEGIN\b(?!\s+TRANSACTION)', cleaned, re.IGNORECASE))
    
    all_ends = re.finditer(r'\bEND\b', cleaned, re.IGNORECASE)
    pure_end_count = 0
    keywords_after_end = {'IF', 'WHILE', 'LOOP', 'CASE', 'REPEAT', 'CURSOR'}
    
    for match in all_ends:
        after = cleaned[match.end():].lstrip()
        next_token = re.match(r'\w+', after)
        if next_token and next_token.group().upper() in keywords_after_end:
            continue
        pure_end_count += 1
    
    case_count = len(re.findall(r'\bCASE\b', cleaned, re.IGNORECASE))
    adjusted_end_count = pure_end_count - case_count
    
    if begins > 0 and begins != adjusted_end_count:
        return ({
            "severity": "fail",
            "msg": f"BEGIN ({begins}) 와 (CASE/IF/LOOP 제외) END ({adjusted_end_count}) 개수 불일치",
            "hint": "모든 BEGIN 은 대응되는 END 로 닫혀야 합니다.",
        }, None)
    return None, None


def _rule_schema_mixing(
    sql: str, obj_type: str
) -> Tuple[Optional[dict], Optional[str]]:
    """
    스키마 표기 혼재 검사.
    """
    variants = {
        "underscore": set(),
        "dot": set(),
        "backtick_dot": set(),
        "double_underscore": set(),
    }
    
    known_schemas = ["customer", "credit", "collection", "ref", "settlement", "config"]
    
    for schema in known_schemas:
        if re.search(rf'\b{schema}_\w+', sql, re.IGNORECASE):
            variants["underscore"].add(schema)
        if re.search(rf'\b{schema}\.\w+', sql, re.IGNORECASE):
            variants["dot"].add(schema)
        if re.search(rf'`{schema}`\.`\w+`', sql, re.IGNORECASE):
            variants["backtick_dot"].add(schema)
        if re.search(rf'\b{schema}__\w+', sql, re.IGNORECASE):
            variants["double_underscore"].add(schema)
    
    used_styles = [k for k, v in variants.items() if v]
    if len(used_styles) > 1:
        return ({
            "severity": "warn",
            "msg": f"스키마 표기 혼재: {used_styles}",
            "hint": "한 가지 스타일로 통일 필요. "
                    "schema_conversion_policy.enforce_schema_strategy() 로 자동 수정 권장",
        }, None)
    
    return None, None


# ════════════════════════════════════════════════════════════════════════════
# 결과 생성
# ════════════════════════════════════════════════════════════════════════════

def _result(
    passed: bool,
    severity: str,
    issues: list,
    auto_fixed_sql: str,
    applied_rules: List[str],
) -> dict:
    return {
        "passed": passed,
        "severity": severity,
        "issues": issues,
        "auto_fixed_sql": auto_fixed_sql,
        "applied_rules": applied_rules,  # v90.52 신규
    }
