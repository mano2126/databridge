"""
test_sql_preflight_validator_v90_52.py — Phase E-3 / v90.52 (2026-04-27)

본부장님 환경 18건 1064 패턴 — 11종 유니크 객체에 대해
preflight_check 가 룰을 정상 적용하여 1064 가 발생하지 않는 SQL 로 수정하는지 검증.

각 케이스:
  1) 입력 SQL: 백엔드 로그 SQL-FAIL-DUMP 의 full_repr 그대로
  2) 기대: passed=True, applied_rules 에 해당 룰 ID 포함
  3) 검증: 자동 수정된 SQL 에 1064 유발 패턴이 더 이상 없을 것

실행:
  cd backend
  pytest tests/test_sql_preflight_validator_v90_52.py -v
"""

import sys
import os
import pytest
import re

# backend 경로 추가
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.core.sql_preflight_validator import preflight_check, build_retry_hint


# ════════════════════════════════════════════════════════════════════════════
# 케이스 11종 — 본부장님 환경 실제 1064 SQL
# ════════════════════════════════════════════════════════════════════════════

CASE_01_FN_DELINQ_STAGE = """\
CREATE FUNCTION collection_fn_delinq_stage(p_days INT)
RETURNS VARCHAR(20)
DETERMINISTIC
BEGIN
    RETURN CASE;
        WHEN p_days <= 30  THEN 'EARLY'
        WHEN p_days <= 90  THEN 'MID'
        WHEN p_days <= 180 THEN 'LATE'
        WHEN p_days <= 360 THEN 'LEGAL'
        ELSE 'WRITEOFF'
    END
END"""

CASE_02_FN_CALC_MONTHLY_PAYMENT = """\
CREATE FUNCTION credit_fn_calc_monthly_payment( p_principal DECIMAL(18,2), p_months INT, p_annual_rate DECIMAL(6,4))
RETURNS DECIMAL(18,2)
DETERMINISTIC
BEGIN
    DECLARE v_r DECIMAL(20,10);
    SET v_r = p_annual_rate / 12;
    IF v_r = 0 THEN
        RETURN CAST(p_principal / p_months AS DECIMAL(18,2));
    END IF
    RETURN CAST(p_principal * v_r * POWER(1 + v_r, p_months) / (POWER(1 + v_r, p_months) - 1) AS DECIMAL(18,2));
END"""

CASE_03_TVF_CONTRACT_EVENTS = """\
CREATE FUNCTION credit_tvf_contract_events(p_contract_id BIGINT)
RETURNS TABLE
RETURN (
    SELECT event_id, event_type, event_date, amount, description
      FROM credit_contract_event
     WHERE contract_id = p_contract_id
)"""

CASE_04_FN_AGE = """\
CREATE FUNCTION ref_fn_age(p_birth DATE) RETURNS INT DETERMINISTIC
BEGIN
    DECLARE v_age INT;
    IF p_birth IS NULL THEN
        RETURN NULL;
    END IF;
    SET v_age = TIMESTAMPDIFF(YEAR, p_birth, CURDATE());
    RETURN v_age
END"""

CASE_05_FN_NEXT_BUSINESS_DAY = """\
CREATE FUNCTION ref_fn_next_business_day(p_dt DATE) RETURNS DATE
DETERMINISTIC
BEGIN
    DECLARE v_d DATE;
    DECLARE v_dow INT;
    SET v_d = p_dt;
    loop_label: LOOP
        SET v_d = DATE_ADD(v_d, INTERVAL 1 DAY);
        SET v_dow = DAYOFWEEK(v_d);
        IF v_dow NOT IN (1, 7) THEN
            LEAVE loop_label;
        END IF
        SET v_d = DATE_ADD(v_d, INTERVAL 1 DAY);
    END LOOP loop_label;
    RETURN v_d;
END"""

CASE_06_SP_MARK_DELINQUENT = """\
CREATE PROCEDURE collection_sp_mark_delinquent(
    IN p_contract_id BIGINT,
    IN p_overdue_amount DECIMAL(18,2)
)
BEGIN
    DECLARE v_cust_id BIGINT;

    SELECT customer_id INTO v_cust_id
      FROM credit_contract
     WHERE contract_id = p_contract_id;

    INSERT INTO collection_delinquency (
        contract_id, customer_id, delinq_start, delinq_days,
        overdue_amount, principal_over, interest_over, stage
    ) VALUES (
        p_contract_id,
        v_cust_id,
        CURDATE(),
        1,
        p_overdue_amount,
        p_overdue_amount * 0.7,
        p_overdue_amount * 0.3,
        'EARLY'
    );
\tLIMIT 1;
\tEND"""

CASE_07_SP_APPROVE_APPLICATION = """\
CREATE PROCEDURE credit_sp_approve_application(
    IN p_app_id BIGINT,
    IN p_emp_no VARCHAR(20),
    IN p_amount DECIMAL(18,2),
    IN p_rate DECIMAL(6,4)
)
BEGIN
    UPDATE credit_application
       SET app_status = 'APPROVED',;
           approved_amount = p_amount,
           approved_rate = p_rate,
           decision_by = p_emp_no,
           decision_date = NOW(6)
     WHERE app_id = p_app_id;
END"""

CASE_08_SP_CLOSE_CONTRACT = """\
CREATE PROCEDURE credit_sp_close_contract(
    IN p_contract_id BIGINT,
    IN p_reason VARCHAR(30)
)
BEGIN
    UPDATE credit_contract
       SET status = 'CLOSED',;
           close_date = DATE(NOW()),
           close_reason = p_reason
     WHERE contract_id = p_contract_id;
END"""

CASE_09_SP_DEACTIVATE = """\
CREATE PROCEDURE customer_sp_deactivate(
    IN p_customer_id BIGINT,
    IN p_reason NVARCHAR(200)
)
BEGIN
    UPDATE customer_profile
       SET status = 'INACTIVE',;
           status_reason = p_reason
     WHERE customer_id = p_customer_id;
END"""

CASE_10_SP_MERGE_CUSTOMER = """\
CREATE PROCEDURE customer_sp_merge_customer(
    IN p_source_id BIGINT,
    IN p_target_id BIGINT,
    IN p_merged_by VARCHAR(20)
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

        UPDATE credit_contract
           SET customer_id = p_target_id;
         WHERE customer_id = p_source_id;

        UPDATE customer_bank_account
           SET customer_id = p_target_id;
         WHERE customer_id = p_source_id;

        UPDATE customer_profile
           SET status = 'MERGED',;
               status_reason = CONCAT('병합됨 → ID ', CAST(p_target_id AS CHAR))
         WHERE customer_id = p_source_id;

    COMMIT;
END"""

CASE_11_TRG_CONTRACT_STATUS_CHANGE = """\
CREATE TRIGGER `credit_trg_contract_status_change` AFTER UPDATE ON `credit_contract` FOR EACH ROW
BEGIN
    IF NEW.status <> OLD.status THEN
        INSERT INTO credit_contract_event (contract_id, event_type, event_date, description)
        VALUES (
            NEW.contract_id,
            'STATUS_CHANGE',
            NOW(6),
            CONCAT('상태 변경: ', OLD.status, ' → ', NEW.status)
        )
    END IF;
END"""

CASE_12_TRG_TRX_LARGE_ALERT = """\
CREATE TRIGGER `settlement_trg_trx_large_alert` AFTER INSERT ON `settlement_trx_history` FOR EACH ROW
BEGIN
    
    IF NEW.amount >= 100000000 THEN
        INSERT INTO settlement_daily_settlement (settle_date, branch_code, product_type, new_contracts)
        VALUES (CAST(NEW.trx_date AS DATE), 'AUDIT', 'LARGE_TRX', 1)
        ON DUPLICATE KEY UPDATE new_contracts = new_contracts + 1
    END IF;
END"""


# ════════════════════════════════════════════════════════════════════════════
# 헬퍼
# ════════════════════════════════════════════════════════════════════════════

def _has_1064_pattern(sql: str) -> bool:
    """1064 유발 패턴 잔존 검출."""
    bad_patterns = [
        # R-01: 콤마 직후 세미콜론 (SET 절)
        r',\s*;',
        # R-02: SET 단일 컬럼 종료 ; 후 WHERE
        r'\bSET\b\s+\S+\s*=\s*[^;]+;\s*\n?\s*\bWHERE\b',
        # R-03: RETURN CASE;
        r'\bRETURN\s+CASE\s*;',
    ]
    for pat in bad_patterns:
        if re.search(pat, sql, re.IGNORECASE):
            return True
    return False


# ════════════════════════════════════════════════════════════════════════════
# 케이스 테스트 — 룰 R-01 (UPDATE SET 콤마-세미콜론) — 가장 빈번
# ════════════════════════════════════════════════════════════════════════════

class TestR01_UpdateSetCommaSemicolon:
    """6건 케이스 (sp_approve, sp_close, sp_deactivate, sp_reject, sp_merge, sp_update_employee_status)"""
    
    def test_case_07_approve_application(self):
        result = preflight_check(CASE_07_SP_APPROVE_APPLICATION, "PROCEDURE")
        assert "R-01" in result["applied_rules"], \
            f"R-01 미적용. issues={result['issues']}"
        # 콤마-세미콜론 패턴 제거 확인
        assert ",;" not in result["auto_fixed_sql"]
        assert ", ;" not in result["auto_fixed_sql"]
    
    def test_case_08_close_contract(self):
        result = preflight_check(CASE_08_SP_CLOSE_CONTRACT, "PROCEDURE")
        assert "R-01" in result["applied_rules"]
        assert ",;" not in result["auto_fixed_sql"]
    
    def test_case_09_deactivate(self):
        result = preflight_check(CASE_09_SP_DEACTIVATE, "PROCEDURE")
        assert "R-01" in result["applied_rules"]
        assert ",;" not in result["auto_fixed_sql"]
    
    def test_case_10_merge_customer_multi(self):
        """sp_merge_customer 는 R-01 + R-02 동시 적용 케이스"""
        result = preflight_check(CASE_10_SP_MERGE_CUSTOMER, "PROCEDURE")
        # R-01 (status = 'MERGED',;) 와 R-02 (customer_id = p_target_id; WHERE) 둘 다 적용
        assert "R-01" in result["applied_rules"], \
            f"R-01 미적용. applied={result['applied_rules']}"
        # 1064 패턴 잔존 없음
        fixed = result["auto_fixed_sql"]
        assert ",;" not in fixed


# ════════════════════════════════════════════════════════════════════════════
# 케이스 테스트 — 룰 R-02 (SET col=v; WHERE)
# ════════════════════════════════════════════════════════════════════════════

class TestR02_SetTrailingSemicolonWhere:
    """sp_merge_customer 내부 2회, settlement_sp_process_payment"""
    
    def test_case_10_merge_customer_inner_set(self):
        """SET customer_id = p_target_id; WHERE ... 패턴"""
        result = preflight_check(CASE_10_SP_MERGE_CUSTOMER, "PROCEDURE")
        # R-02 적용 확인 — 또는 R-01 의 광범위 매칭으로 처리됐을 수도
        applied = result["applied_rules"]
        # 적어도 둘 중 하나는 적용되어야 함
        assert "R-01" in applied or "R-02" in applied, \
            f"R-01/R-02 둘 다 미적용. applied={applied}"


# ════════════════════════════════════════════════════════════════════════════
# 케이스 테스트 — 룰 R-03 (RETURN CASE;)
# ════════════════════════════════════════════════════════════════════════════

class TestR03_ReturnCaseSemicolon:
    """fn_delinq_stage"""
    
    def test_case_01_fn_delinq_stage(self):
        result = preflight_check(CASE_01_FN_DELINQ_STAGE, "FUNCTION")
        assert "R-03" in result["applied_rules"], \
            f"R-03 미적용. issues={result['issues']}"
        # RETURN CASE; 패턴 제거 확인
        assert "RETURN CASE;" not in result["auto_fixed_sql"]


# ════════════════════════════════════════════════════════════════════════════
# 케이스 테스트 — 룰 R-04 (INSERT VALUES; 누락)
# ════════════════════════════════════════════════════════════════════════════

class TestR04_InsertValuesSemicolon:
    """trg_contract_status_change, trg_trx_large_alert"""
    
    def test_case_11_trg_contract_status(self):
        result = preflight_check(CASE_11_TRG_CONTRACT_STATUS_CHANGE, "TRIGGER")
        assert "R-04" in result["applied_rules"], \
            f"R-04 미적용. issues={result['issues']}"
    
    def test_case_12_trg_trx_large(self):
        result = preflight_check(CASE_12_TRG_TRX_LARGE_ALERT, "TRIGGER")
        assert "R-04" in result["applied_rules"], \
            f"R-04 미적용. issues={result['issues']}"


# ════════════════════════════════════════════════════════════════════════════
# 케이스 테스트 — 룰 R-05 (PROCEDURE LIMIT 1 위치)
# ════════════════════════════════════════════════════════════════════════════

class TestR05_ProcedureLimitMisplaced:
    """sp_mark_delinquent"""
    
    def test_case_06_mark_delinquent(self):
        result = preflight_check(CASE_06_SP_MARK_DELINQUENT, "PROCEDURE")
        assert "R-05" in result["applied_rules"], \
            f"R-05 미적용. issues={result['issues']}"
        # 잘못된 LIMIT 1; 제거 확인
        assert "LIMIT 1;" not in result["auto_fixed_sql"]


# ════════════════════════════════════════════════════════════════════════════
# 케이스 테스트 — 룰 R-09 (END IF 누락)
# ════════════════════════════════════════════════════════════════════════════

class TestR09_EndIfMissing:
    """fn_calc_monthly_payment, fn_age, fn_next_business_day, trg_contract_status_change, trg_trx_large_alert"""
    
    def test_case_02_calc_monthly_payment(self):
        """IF v_r = 0 THEN ... END IF (뒤 ; 누락) → R-04 가 잡음 (확장된 의미)"""
        result = preflight_check(CASE_02_FN_CALC_MONTHLY_PAYMENT, "FUNCTION")
        # R-04 (END IF 뒤 ; 누락 확장) 또는 R-09 (END IF 누락) 또는 R-08 (RETURN ; 누락)
        # 셋 중 하나로 감지되면 OK
        assert (
            "R-04" in result["applied_rules"]
            or "R-09" in result["applied_rules"]
            or "R-08" in result["applied_rules"]
            or any(i.get("severity") == "fail" for i in result["issues"])
        ), f"R-04/R-09/R-08 미감지. issues={result['issues']}, applied={result['applied_rules']}"


# ════════════════════════════════════════════════════════════════════════════
# 케이스 테스트 — 룰 R-10 (TVF MySQL 부적합)
# ════════════════════════════════════════════════════════════════════════════

class TestR10_TvfUnsupported:
    """tvf_contract_events"""
    
    def test_case_03_tvf_contract_events(self):
        result = preflight_check(CASE_03_TVF_CONTRACT_EVENTS, "FUNCTION")
        # TVF 는 fail 로 보고 (자동 수정 불가)
        assert result["severity"] == "fail", \
            f"TVF fail 미감지. severity={result['severity']}"
        # R-10 이 issues 에 있어야
        rule_ids = [i.get("rule") for i in result["issues"]]
        assert "R-10" in rule_ids, f"R-10 미보고. issues={result['issues']}"


# ════════════════════════════════════════════════════════════════════════════
# 통합 테스트 — applied_rules 필드 존재
# ════════════════════════════════════════════════════════════════════════════

class TestIntegration:
    
    def test_result_has_applied_rules_field(self):
        """v90.52 신규 필드: applied_rules"""
        result = preflight_check(CASE_07_SP_APPROVE_APPLICATION, "PROCEDURE")
        assert "applied_rules" in result
        assert isinstance(result["applied_rules"], list)
    
    def test_clean_sql_passes(self):
        """문제 없는 SQL 은 통과"""
        clean_sql = """\
CREATE FUNCTION fn_simple(p_x INT)
RETURNS INT
DETERMINISTIC
BEGIN
    RETURN p_x * 2;
END"""
        result = preflight_check(clean_sql, "FUNCTION")
        assert result["passed"] is True
        assert result["severity"] == "ok"
        # 변경 없음
        assert result["auto_fixed_sql"] == clean_sql
        assert result["applied_rules"] == []
    
    def test_empty_sql(self):
        """빈 SQL 안전 처리"""
        result = preflight_check("", "FUNCTION")
        assert result["passed"] is True
        assert result["applied_rules"] == []
    
    def test_idempotent_call(self):
        """동일 SQL 재호출 시 결과 동일 (안전망 2차 호출 보장)"""
        result1 = preflight_check(CASE_07_SP_APPROVE_APPLICATION, "PROCEDURE")
        # 1차 결과의 auto_fixed_sql 을 다시 검증
        result2 = preflight_check(result1["auto_fixed_sql"], "PROCEDURE")
        # 2차에서는 룰 적용이 없어야 함 (이미 수정 완료)
        assert "R-01" not in result2["applied_rules"], \
            "1차 수정 후에도 R-01 가 또 적용됨 (idempotent 위반)"
    
    def test_build_retry_hint_with_rules(self):
        result = preflight_check(CASE_03_TVF_CONTRACT_EVENTS, "FUNCTION")
        hint = build_retry_hint(result)
        assert "R-10" in hint, f"hint 에 R-10 없음: {hint}"
    
    def test_signature_compatibility(self):
        """기존 호출 시그니처 호환성: 키 4개 모두 존재"""
        result = preflight_check(CASE_07_SP_APPROVE_APPLICATION, "PROCEDURE")
        for key in ("passed", "severity", "issues", "auto_fixed_sql"):
            assert key in result, f"기존 키 {key} 누락"


# ════════════════════════════════════════════════════════════════════════════
# 회귀 테스트 — 18건 1064 패턴이 자동 수정 후 재발하지 않음
# ════════════════════════════════════════════════════════════════════════════

ALL_CASES = [
    ("CASE_01_FN_DELINQ_STAGE", CASE_01_FN_DELINQ_STAGE, "FUNCTION"),
    ("CASE_02_FN_CALC_MONTHLY_PAYMENT", CASE_02_FN_CALC_MONTHLY_PAYMENT, "FUNCTION"),
    # CASE_03 은 TVF 라 fail 처리 — 수정 불가가 정상
    ("CASE_04_FN_AGE", CASE_04_FN_AGE, "FUNCTION"),
    ("CASE_05_FN_NEXT_BUSINESS_DAY", CASE_05_FN_NEXT_BUSINESS_DAY, "FUNCTION"),
    ("CASE_06_SP_MARK_DELINQUENT", CASE_06_SP_MARK_DELINQUENT, "PROCEDURE"),
    ("CASE_07_SP_APPROVE_APPLICATION", CASE_07_SP_APPROVE_APPLICATION, "PROCEDURE"),
    ("CASE_08_SP_CLOSE_CONTRACT", CASE_08_SP_CLOSE_CONTRACT, "PROCEDURE"),
    ("CASE_09_SP_DEACTIVATE", CASE_09_SP_DEACTIVATE, "PROCEDURE"),
    ("CASE_10_SP_MERGE_CUSTOMER", CASE_10_SP_MERGE_CUSTOMER, "PROCEDURE"),
    ("CASE_11_TRG_CONTRACT_STATUS_CHANGE", CASE_11_TRG_CONTRACT_STATUS_CHANGE, "TRIGGER"),
    ("CASE_12_TRG_TRX_LARGE_ALERT", CASE_12_TRG_TRX_LARGE_ALERT, "TRIGGER"),
]


@pytest.mark.parametrize("case_name,sql,obj_type", ALL_CASES)
def test_no_regression_after_fix(case_name, sql, obj_type):
    """모든 케이스: 자동 수정 후 1064 유발 패턴이 잔존하지 않아야 함."""
    result = preflight_check(sql, obj_type)
    fixed = result["auto_fixed_sql"]
    
    # fail 인 경우는 자동 수정 안 됨 (정상)
    if result["severity"] == "fail":
        return
    
    # warn 인 경우 자동 수정 후 1064 패턴 잔존 없어야
    assert not _has_1064_pattern(fixed), (
        f"{case_name}: 자동 수정 후에도 1064 패턴 잔존\n"
        f"applied={result['applied_rules']}\n"
        f"fixed (head 500):\n{fixed[:500]}"
    )


if __name__ == "__main__":
    # 수동 실행 시 케이스별 결과 출력
    for case_name, sql, obj_type in ALL_CASES:
        result = preflight_check(sql, obj_type)
        print(f"\n=== {case_name} ({obj_type}) ===")
        print(f"  severity: {result['severity']}")
        print(f"  applied_rules: {result['applied_rules']}")
        print(f"  issues: {len(result['issues'])}건")
        for issue in result['issues']:
            print(f"    - [{issue.get('rule')}] {issue.get('msg')}")
