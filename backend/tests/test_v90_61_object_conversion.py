"""
test_v90_61_object_conversion.py — v90.61 (2026-04-28)

본부장님 backend.log 에서 추출한 실제 41개 SP/FN/VW/TR 1064 / 1049 오류 케이스.

진단:
  - `schema`.name 형태 (schema 만 백틱) 가 enforce_schema_strategy 미커버 → 통과
  - obj_executor 의 객체명 추출 정규식이 점 뒤를 못 잡아서 DROP 망가짐
  - DATETIME2, IF...RETURN, DECLARE 인라인 등 MSSQL 잔재 통과
  - 문자열 + 결합 통과

v90.61 처방:
  1. enforce_schema_strategy 정규식 5개 변종 추가
  2. obj_executor _extract_obj_name 헬퍼로 schema.name 평탄화
  3. 후처리 변환 규칙 (DATETIME2, IF/RETURN, DECLARE 인라인, +CONCAT, DATEADD/DATEDIFF/DATEPART) 추가
  4. system.txt prompt 강화

이 테스트는 위 4가지 fix 가 본부장님 41개 케이스를 정확히 처리하는지 검증.
"""

import sys
import os
import re
import pytest

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


# ════════════════════════════════════════════════════════════════════════════
# 1. enforce_schema_strategy 검증 (`schema`.name 변종)
# ════════════════════════════════════════════════════════════════════════════

class TestSchemaConversionPolicy:
    """schema_conversion_policy.enforce_schema_strategy 의 v90.61 변종 처리."""
    
    def test_schema_only_backtick_pattern_v90_61(self):
        """본부장님 환경 핵심 케이스 — `schema`.name (schema 만 backtick)."""
        from app.core.schema_conversion_policy import enforce_schema_strategy
        
        sql = "CREATE FUNCTION `collection`.fn_delinq_stage(p_days INT) RETURNS VARCHAR(20)"
        result, fixes = enforce_schema_strategy(
            sql, "underscore",
            known_schemas=["collection", "credit", "customer", "ref", "settlement"]
        )
        
        # collection.fn_delinq_stage → collection_fn_delinq_stage 평탄화
        assert "`collection`.fn_delinq_stage" not in result, f"패턴 안 잡힘: {result}"
        assert "collection_fn_delinq_stage" in result, f"평탄화 실패: {result}"
        # fix 내역에 v90.61 마커
        assert any("v90.61" in f for f in fixes), f"v90.61 fix 마커 없음: {fixes}"
    
    def test_full_backtick_pattern(self):
        """기존 케이스: `schema`.`name` 도 정상 동작."""
        from app.core.schema_conversion_policy import enforce_schema_strategy
        
        sql = "FROM `customer`.`profile` WHERE id = 1"
        result, fixes = enforce_schema_strategy(
            sql, "underscore",
            known_schemas=["customer", "credit"]
        )
        assert "customer_profile" in result
    
    def test_no_backtick_pattern(self):
        """기존 케이스: schema.name (백틱 없음)."""
        from app.core.schema_conversion_policy import enforce_schema_strategy
        
        sql = "SELECT * FROM credit.contract WHERE active = 1"
        result, fixes = enforce_schema_strategy(
            sql, "underscore",
            known_schemas=["credit"]
        )
        assert "credit_contract" in result
    
    def test_mssql_brackets_pattern_v90_61(self):
        """v90.61 신규: [schema].[name] (MSSQL 잔재)."""
        from app.core.schema_conversion_policy import enforce_schema_strategy
        
        sql = "FROM [credit].[contract_event] WHERE id = 1"
        result, fixes = enforce_schema_strategy(
            sql, "underscore",
            known_schemas=["credit"]
        )
        assert "credit_contract_event" in result
        assert "[credit]" not in result
    
    def test_president_full_create_function_normalized(self):
        """본부장님 환경의 실제 fn_delinq_stage DDL 전체 변환."""
        from app.core.schema_conversion_policy import enforce_schema_strategy
        
        sql = """DROP FUNCTION IF EXISTS `collection`.fn_delinq_stage;
CREATE FUNCTION `collection`.fn_delinq_stage(p_days INT)
RETURNS VARCHAR(20)
DETERMINISTIC
BEGIN
    RETURN CASE
        WHEN p_days <= 30  THEN 'EARLY'
        WHEN p_days <= 90  THEN 'MID'
        ELSE 'WRITEOFF'
    END;
END"""
        result, fixes = enforce_schema_strategy(
            sql, "underscore",
            known_schemas=["collection", "credit", "customer", "ref", "settlement"]
        )
        
        # 모든 schema 표기가 underscore 형태로 변환됨
        assert "`collection`.fn_delinq_stage" not in result
        assert "collection_fn_delinq_stage" in result


# ════════════════════════════════════════════════════════════════════════════
# 2. obj_executor 의 mssql_to_mysql_ddl 검증
# ════════════════════════════════════════════════════════════════════════════

class TestObjExecutor:
    """obj_executor.mssql_to_mysql_ddl 의 v90.61 fix 검증."""
    
    def test_function_with_schema_dot_extraction(self):
        """본부장님 환경 케이스: `collection`.fn_delinq_stage 헤더 처리."""
        from app.core.obj_executor import mssql_to_mysql_ddl
        
        ddl = """CREATE FUNCTION `collection`.fn_delinq_stage(p_days INT)
RETURNS VARCHAR(20)
AS BEGIN
    RETURN CASE WHEN p_days <= 30 THEN 'EARLY' ELSE 'LATE' END;
END"""
        result, warnings = mssql_to_mysql_ddl(ddl, "FUNCTION")
        
        # DROP / CREATE 둘 다 collection_fn_delinq_stage (평탄화) 사용
        assert "DROP FUNCTION IF EXISTS `collection_fn_delinq_stage`" in result, \
            f"DROP 평탄화 안 됨:\n{result}"
        assert "CREATE FUNCTION `collection_fn_delinq_stage`" in result, \
            f"CREATE 평탄화 안 됨:\n{result}"
        # ❌ 이전 버그 재발 검증
        assert "DROP FUNCTION IF EXISTS `collection`;" not in result, \
            "v90.54 시점 버그 재발 — DROP 이름이 'collection' 만"
    
    def test_procedure_with_schema_dot(self):
        """SP 도 동일."""
        from app.core.obj_executor import mssql_to_mysql_ddl
        
        ddl = """CREATE PROCEDURE [credit].[sp_calc]
AS BEGIN
    SELECT 1;
END"""
        result, warnings = mssql_to_mysql_ddl(ddl, "PROCEDURE")
        
        assert "credit_sp_calc" in result
        # MSSQL 대괄호 잔재 없어야
        assert "[credit].[sp_calc]" not in result
    
    def test_view_with_schema_dot(self):
        """VIEW 도 동일."""
        from app.core.obj_executor import mssql_to_mysql_ddl
        
        ddl = "CREATE VIEW `customer`.v_customer_360 AS SELECT * FROM `customer`.profile"
        result, warnings = mssql_to_mysql_ddl(ddl, "VIEW")
        
        # 헤더 평탄화
        assert "customer_v_customer_360" in result
        # 본문도
        # (enforce_schema_strategy 가 이 단계 후에 적용되므로 obj_executor 만으로는 본문 변환 안 됨 - 정상)
    
    def test_datetime2_converted(self):
        """DATETIME2 → DATETIME(6) 변환."""
        from app.core.obj_executor import mssql_to_mysql_ddl
        
        ddl = "CREATE FUNCTION `f1`(p_dt DATETIME2(7), p_dt2 DATETIME2) RETURNS INT AS BEGIN RETURN 1; END"
        result, warnings = mssql_to_mysql_ddl(ddl, "FUNCTION")
        
        assert "DATETIME2" not in result, f"DATETIME2 잔존: {result}"
        assert "DATETIME(6)" in result
    
    def test_if_return_converted(self):
        """IF condition RETURN value; → IF...THEN RETURN value; END IF;"""
        from app.core.obj_executor import mssql_to_mysql_ddl
        
        ddl = """CREATE FUNCTION `fn_calc`(p_r DECIMAL) RETURNS DECIMAL
AS BEGIN
    IF p_r = 0 RETURN 0;
    RETURN p_r * 2;
END"""
        result, warnings = mssql_to_mysql_ddl(ddl, "FUNCTION")
        
        assert "IF p_r = 0 THEN RETURN 0;" in result, \
            f"IF/THEN/RETURN 변환 안 됨:\n{result}"
        assert "END IF" in result
    
    def test_declare_inline_init_converted(self):
        """DECLARE x TYPE = value; → DECLARE x TYPE; SET x = value;"""
        from app.core.obj_executor import mssql_to_mysql_ddl
        
        ddl = """CREATE FUNCTION `f1`() RETURNS DECIMAL
AS BEGIN
    DECLARE p_r DECIMAL(18,10) = 12.5;
    RETURN p_r;
END"""
        result, warnings = mssql_to_mysql_ddl(ddl, "FUNCTION")
        
        # DECLARE p_r DECIMAL(18,10);  (인라인 = 분리됨)
        assert re.search(r"DECLARE\s+p_r\s+DECIMAL\(18,10\)\s*;", result), \
            f"DECLARE 분리 안 됨:\n{result}"
        # SET p_r = 12.5;
        assert re.search(r"SET\s+p_r\s*=\s*12\.5\s*;", result), \
            f"SET 분리 안 됨:\n{result}"
    
    def test_string_concat_converted(self):
        """'X' + col → CONCAT('X', col)."""
        from app.core.obj_executor import mssql_to_mysql_ddl
        
        ddl = """CREATE FUNCTION `fn_mask`(p_rrn VARCHAR(14)) RETURNS VARCHAR(20)
AS BEGIN
    RETURN SUBSTRING(p_rrn, 1, 6) + '-' + REPEAT('*', 7);
END"""
        result, warnings = mssql_to_mysql_ddl(ddl, "FUNCTION")
        
        # + 가 모두 CONCAT 으로 변환됨 (적어도 일부)
        assert "CONCAT" in result, f"CONCAT 변환 안 됨:\n{result}"
    
    def test_dateadd_converted(self):
        """DATEADD(day, 1, p_dt) → DATE_ADD(p_dt, INTERVAL 1 DAY)."""
        from app.core.obj_executor import mssql_to_mysql_ddl
        
        ddl = """CREATE FUNCTION `fn_next_day`(p_dt DATE) RETURNS DATE
AS BEGIN
    DECLARE p_d DATE;
    SET p_d = DATEADD(day, 1, p_dt);
    RETURN p_d;
END"""
        result, warnings = mssql_to_mysql_ddl(ddl, "FUNCTION")
        
        assert "DATE_ADD" in result
        assert "INTERVAL 1 DAY" in result
        assert "DATEADD" not in result.upper().replace("DATE_ADD", "")  # 잔재 없어야
    
    def test_datediff_year_converted(self):
        """DATEDIFF(year, a, b) → TIMESTAMPDIFF(YEAR, a, b)."""
        from app.core.obj_executor import mssql_to_mysql_ddl
        
        ddl = """CREATE FUNCTION `fn_age`(p_birth DATE) RETURNS INT
AS BEGIN
    RETURN DATEDIFF(year, p_birth, NOW());
END"""
        result, warnings = mssql_to_mysql_ddl(ddl, "FUNCTION")
        
        assert "TIMESTAMPDIFF(YEAR" in result, f"TIMESTAMPDIFF 변환 안 됨:\n{result}"
    
    def test_datepart_weekday_converted(self):
        """DATEPART(weekday, x) → DAYOFWEEK(x)."""
        from app.core.obj_executor import mssql_to_mysql_ddl
        
        ddl = """CREATE FUNCTION `fn_biz_day`(p_d DATE) RETURNS INT
AS BEGIN
    RETURN DATEPART(weekday, p_d);
END"""
        result, warnings = mssql_to_mysql_ddl(ddl, "FUNCTION")
        
        assert "DAYOFWEEK" in result
    
    def test_tvf_warning(self):
        """RETURNS TABLE AS RETURN(...) → 경고 추가."""
        from app.core.obj_executor import mssql_to_mysql_ddl
        
        ddl = """CREATE FUNCTION `tvf_x`(p_id INT)
RETURNS TABLE AS RETURN (
    SELECT id, name FROM tbl WHERE id = p_id
)"""
        result, warnings = mssql_to_mysql_ddl(ddl, "FUNCTION")
        
        # 경고 추가됨
        assert any("TVF" in w for w in warnings), f"TVF 경고 없음: {warnings}"


# ════════════════════════════════════════════════════════════════════════════
# 3. system.txt prompt 강화 검증
# ════════════════════════════════════════════════════════════════════════════

class TestSystemPromptEnhancement:
    """system.txt 가 본부장님 환경 패턴을 명시하는지."""
    
    SYSTEM_TXT = os.path.normpath(os.path.join(
        _BACKEND_DIR, "prompts", "mssql_to_mysql", "system.txt"
    ))
    
    def test_pattern_1_schema_name_explicit(self):
        if not os.path.exists(self.SYSTEM_TXT):
            pytest.skip(f"{self.SYSTEM_TXT} 없음")
        content = open(self.SYSTEM_TXT, encoding='utf-8').read()
        assert "패턴 1" in content, "패턴 1 (schema 표기) 명시 누락"
        assert "collection_fn_delinq_stage" in content, \
            "본부장님 환경 실제 케이스 명시 누락"
        assert "`collection`.fn_delinq_stage" in content, \
            "잘못된 패턴 명시 누락"
    
    def test_pattern_2_datetime2(self):
        if not os.path.exists(self.SYSTEM_TXT):
            pytest.skip("")
        content = open(self.SYSTEM_TXT, encoding='utf-8').read()
        assert "DATETIME2" in content
        assert "DATETIME(6)" in content
    
    def test_pattern_3_if_return(self):
        if not os.path.exists(self.SYSTEM_TXT):
            pytest.skip("")
        content = open(self.SYSTEM_TXT, encoding='utf-8').read()
        assert "IF condition RETURN" in content or "IF p_r = 0 RETURN" in content
        assert "THEN" in content
        assert "END IF" in content
    
    def test_pattern_4_declare_inline(self):
        if not os.path.exists(self.SYSTEM_TXT):
            pytest.skip("")
        content = open(self.SYSTEM_TXT, encoding='utf-8').read()
        assert "DECLARE" in content
        assert "인라인" in content
    
    def test_pattern_5_string_concat(self):
        if not os.path.exists(self.SYSTEM_TXT):
            pytest.skip("")
        content = open(self.SYSTEM_TXT, encoding='utf-8').read()
        assert "문자열" in content and "CONCAT" in content
    
    def test_self_check_checklist(self):
        """생성 전 체크리스트 추가됐는지."""
        if not os.path.exists(self.SYSTEM_TXT):
            pytest.skip("")
        content = open(self.SYSTEM_TXT, encoding='utf-8').read()
        assert "체크리스트" in content
        # 필수 항목들
        for marker in ["DATETIME2", "IF...RETURN", "DECLARE", "CONCAT"]:
            assert marker in content, f"체크리스트에 {marker} 누락"


# ════════════════════════════════════════════════════════════════════════════
# 4. 본부장님 환경 41개 케이스 종합 시뮬레이션
# ════════════════════════════════════════════════════════════════════════════

PRESIDENT_OBJECTS = [
    # (obj_type, schema, name)
    ("FUNCTION", "collection", "fn_delinq_stage"),
    ("FUNCTION", "collection", "tvf_delinq_ranking"),  # TVF — 경고
    ("FUNCTION", "credit",     "fn_calc_monthly_payment"),
    ("FUNCTION", "credit",     "fn_total_balance"),
    ("FUNCTION", "credit",     "tvf_contract_events"),  # TVF — 경고
    ("FUNCTION", "customer",   "fn_mask_rrn"),
    ("FUNCTION", "ref",        "fn_age"),
    ("FUNCTION", "ref",        "fn_get_grade"),
    ("FUNCTION", "ref",        "fn_korean_date"),
    ("FUNCTION", "ref",        "fn_next_business_day"),
    ("FUNCTION", "settlement", "tvf_daily_trx"),  # TVF — 경고
    ("PROCEDURE", "collection", "sp_assign_collector"),
    ("PROCEDURE", "collection", "sp_mark_delinquent"),
    ("PROCEDURE", "credit",     "sp_approve_application"),
    ("PROCEDURE", "credit",     "sp_calculate_schedule"),
    ("PROCEDURE", "credit",     "sp_close_contract"),
    ("PROCEDURE", "credit",     "sp_reject_application"),
    ("PROCEDURE", "customer",   "sp_deactivate"),
    ("PROCEDURE", "customer",   "sp_merge_customer"),
    ("PROCEDURE", "customer",   "sp_update_credit_score"),
    ("PROCEDURE", "ref",        "sp_close_branch"),
    ("PROCEDURE", "ref",        "sp_refresh_fx"),
    ("PROCEDURE", "ref",        "sp_update_employee_status"),
    ("PROCEDURE", "settlement", "sp_daily_batch"),
    ("PROCEDURE", "settlement", "sp_process_payment"),
    ("PROCEDURE", "settlement", "sp_reverse_trx"),
    ("VIEW",     "collection", "v_delinq_summary"),
    ("VIEW",     "credit",     "v_active_contract"),
    ("VIEW",     "credit",     "v_maturing_soon"),
    ("VIEW",     "credit",     "v_product_delinq_rate"),
    ("VIEW",     "customer",   "v_customer_360"),
    ("VIEW",     "customer",   "v_new_customers"),
    ("VIEW",     "ref",        "v_branch_performance"),
    ("VIEW",     "ref",        "v_employee_workload"),
    ("VIEW",     "settlement", "v_monthly_disburse"),
    ("VIEW",     "settlement", "v_recent_trx"),
    ("TRIGGER",  "customer",   "trg_profile_updated"),
    ("TRIGGER",  "credit",     "trg_contract_status_change"),
    ("TRIGGER",  "collection", "trg_delinq_resolved"),
    ("TRIGGER",  "customer",   "trg_bank_primary"),
    ("TRIGGER",  "settlement", "trg_trx_large_alert"),
]


class TestPresident41Objects:
    """본부장님 환경 41개 SP/FN/VW/TR 모두 정확한 변환 검증."""
    
    def test_all_41_objects_normalized(self):
        """41개 객체 모두 schema_name 평탄화 헤더 생성 확인."""
        from app.core.obj_executor import mssql_to_mysql_ddl
        
        failed = []
        for obj_type, schema, name in PRESIDENT_OBJECTS:
            # 본부장님 환경의 실제 형태 (AI 가 만든 잘못된 형태) 시뮬레이션
            if obj_type == "FUNCTION":
                ddl = f"CREATE FUNCTION `{schema}`.{name}() RETURNS INT AS BEGIN RETURN 1; END"
            elif obj_type == "PROCEDURE":
                ddl = f"CREATE PROCEDURE `{schema}`.{name}() AS BEGIN SELECT 1; END"
            elif obj_type == "VIEW":
                ddl = f"CREATE VIEW `{schema}`.{name} AS SELECT 1 AS x"
            else:  # TRIGGER
                ddl = f"CREATE TRIGGER `{schema}`.{name} AFTER INSERT ON tbl FOR EACH ROW BEGIN SELECT 1; END"
            
            result, _ = mssql_to_mysql_ddl(ddl, obj_type)
            
            # 평탄화된 이름으로 변환됐는지
            flat_name = f"{schema}_{name}"
            if flat_name not in result:
                failed.append(f"{obj_type} {schema}.{name}: 평탄화 실패\n  결과: {result[:200]}")
            
            # 이전 버그 (`schema`.name 그대로) 재발 안 됐는지
            if f"`{schema}`.{name}" in result:
                failed.append(f"{obj_type} {schema}.{name}: 원본 패턴 잔존 (버그!)")
        
        if failed:
            print("\n실패 케이스:")
            for f in failed[:5]:
                print(f"  - {f}")
            assert not failed, f"41개 중 {len(failed)}건 실패"


if __name__ == "__main__":
    print("=== v90.61 본부장님 41개 객체 종합 검증 ===")
    
    from app.core.obj_executor import mssql_to_mysql_ddl
    from app.core.schema_conversion_policy import enforce_schema_strategy
    
    success = 0
    fail = 0
    failures = []
    
    for obj_type, schema, name in PRESIDENT_OBJECTS:
        if obj_type == "FUNCTION":
            ddl = f"CREATE FUNCTION `{schema}`.{name}() RETURNS INT AS BEGIN RETURN 1; END"
        elif obj_type == "PROCEDURE":
            ddl = f"CREATE PROCEDURE `{schema}`.{name}() AS BEGIN SELECT 1; END"
        elif obj_type == "VIEW":
            ddl = f"CREATE VIEW `{schema}`.{name} AS SELECT 1 AS x"
        else:
            ddl = f"CREATE TRIGGER `{schema}`.{name} AFTER INSERT ON tbl FOR EACH ROW BEGIN SELECT 1; END"
        
        result, _ = mssql_to_mysql_ddl(ddl, obj_type)
        flat_name = f"{schema}_{name}"
        
        if flat_name in result and f"`{schema}`.{name}" not in result:
            success += 1
        else:
            fail += 1
            failures.append(f"{obj_type} {schema}.{name}")
    
    print(f"\n  성공: {success}/{len(PRESIDENT_OBJECTS)}")
    print(f"  실패: {fail}/{len(PRESIDENT_OBJECTS)}")
    if failures:
        print(f"  실패 항목:")
        for f in failures[:10]:
            print(f"    - {f}")
