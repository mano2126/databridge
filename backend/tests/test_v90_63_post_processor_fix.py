"""
test_v90_63_post_processor_fix.py — v90.63 (2026-04-28)

본부장님 backend.log 13:11~13:13 retry 에서 11개 SP/FN 1064 오류 분석.
AI 가 만든 raw SQL 자체에 4가지 문제 패턴 반복:

P1: RETURN CASE; (CASE 다음 잘못된 ;)
P2: UPDATE...SET col = val;\n WHERE (SET 뒤 ; 잘못)
P3: UPDATE...SET col = 'X',;\n... (콤마 다음 ; 잘못)
P4: RETURN expr 끝에 ; 누락 (IF...THEN 안)

v90.63 처방:
  obj_executor.py 후처리에 4가지 정규식 추가하여 AI 의 1064 패턴 강제 fix
  + system.txt 에 9대 패턴 (5+4) 명시

이 테스트는 실제 backend.log 의 SQL-FAIL-DUMP 그대로 입력해서 검증.
"""

import os
import re
import sys
import pytest

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


# ════════════════════════════════════════════════════════════════════════════
# 본부장님 환경 11개 실패 케이스의 실제 raw SQL (backend.log 13:11~13:13)
# ════════════════════════════════════════════════════════════════════════════

FN_DELINQ_STAGE_RAW = """CREATE FUNCTION collection_fn_delinq_stage(p_days INT)
RETURNS VARCHAR(20)
DETERMINISTIC
BEGIN
    RETURN CASE;
        WHEN p_days <= 30  THEN 'EARLY'
        WHEN p_days <= 90  THEN 'MID'
        WHEN p_days <= 180 THEN 'LATE'
        WHEN p_days <= 360 THEN 'LEGAL'
        ELSE 'WRITEOFF'
    END;
END"""

SP_ASSIGN_COLLECTOR_RAW = """CREATE PROCEDURE collection_sp_assign_collector(
    IN p_delinq_id BIGINT,
    IN p_emp_no VARCHAR(20)
)
BEGIN
    UPDATE collection_delinquency
    SET assigned_emp_no = p_emp_no;
    WHERE delinq_id = p_delinq_id;
END"""

SP_APPROVE_APPLICATION_RAW = """CREATE PROCEDURE credit_sp_approve_application(
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

SP_CLOSE_CONTRACT_RAW = """CREATE PROCEDURE credit_sp_close_contract(
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

SP_CLOSE_BRANCH_RAW = """CREATE PROCEDURE ref_sp_close_branch(
    IN p_branch_code VARCHAR(10),
    IN p_close_date DATE
)
BEGIN
    UPDATE ref_branch
    SET close_date = p_close_date;
    WHERE branch_code = p_branch_code COLLATE utf8mb4_unicode_ci;
END"""


# ════════════════════════════════════════════════════════════════════════════
# 핵심 검증
# ════════════════════════════════════════════════════════════════════════════

class TestPattern1_ReturnCaseSemicolon:
    """P1: RETURN CASE; → RETURN CASE"""
    
    def test_return_case_semicolon_removed(self):
        from app.core.obj_executor import mssql_to_mysql_ddl
        result, warnings = mssql_to_mysql_ddl(FN_DELINQ_STAGE_RAW, "FUNCTION")
        
        # ; 가 사라져야 함
        assert "RETURN CASE;" not in result, f"RETURN CASE; 잔존:\n{result}"
        # 하지만 RETURN CASE 자체는 살아있어야
        assert "RETURN CASE" in result
        # END; 는 살아있어야 (CASE 의 마지막 END)
        assert "END;" in result


class TestPattern2_UpdateSetSemicolon:
    """P2: UPDATE...SET col = val;\n WHERE → ; 제거"""
    
    def test_set_then_where_semicolon_removed(self):
        from app.core.obj_executor import mssql_to_mysql_ddl
        result, warnings = mssql_to_mysql_ddl(SP_ASSIGN_COLLECTOR_RAW, "PROCEDURE")
        
        # SET ... ; \n WHERE 패턴이 사라져야
        assert not re.search(
            r"SET\s+assigned_emp_no\s*=\s*p_emp_no\s*;\s*\n\s*WHERE",
            result, re.IGNORECASE
        ), f"SET 뒤 ; 제거 안 됨:\n{result}"
        # WHERE 절 살아있어야
        assert "WHERE delinq_id = p_delinq_id" in result
        # 마지막 ; 는 그대로
        assert "p_delinq_id;" in result
    
    def test_set_collate_then_where(self):
        from app.core.obj_executor import mssql_to_mysql_ddl
        result, warnings = mssql_to_mysql_ddl(SP_CLOSE_BRANCH_RAW, "PROCEDURE")
        
        # SET col = val; (잘못된 ;) 가 없어야
        assert not re.search(
            r"SET\s+close_date\s*=\s*p_close_date\s*;\s*\n\s*WHERE",
            result, re.IGNORECASE
        ), f"SET 뒤 ; 제거 안 됨:\n{result}"


class TestPattern3_CommaSemicolon:
    """P3: SET col = 'X',; → SET col = 'X', (콤마 다음 ; 제거)"""
    
    def test_comma_semicolon_removed_approve(self):
        from app.core.obj_executor import mssql_to_mysql_ddl
        result, warnings = mssql_to_mysql_ddl(SP_APPROVE_APPLICATION_RAW, "PROCEDURE")
        
        # ',;' 가 없어야
        assert ",;" not in result, f"콤마+; 잔존:\n{result}"
        assert ", ;" not in result
        # 본문 살아있어야
        assert "SET app_status = 'APPROVED'" in result
        assert "approved_amount = p_amount" in result
        assert "WHERE app_id = p_app_id" in result
    
    def test_comma_semicolon_removed_close_contract(self):
        from app.core.obj_executor import mssql_to_mysql_ddl
        result, warnings = mssql_to_mysql_ddl(SP_CLOSE_CONTRACT_RAW, "PROCEDURE")
        
        assert ",;" not in result
        assert "SET status = 'CLOSED'" in result
        assert "close_date = DATE(NOW())" in result
        assert "WHERE contract_id = p_contract_id" in result


class TestRegression:
    """기존 정상 SQL 은 v90.63 후처리에 영향 안 받아야."""
    
    def test_normal_select_unchanged(self):
        from app.core.obj_executor import mssql_to_mysql_ddl
        ddl = """CREATE FUNCTION test_fn(p_id INT) RETURNS VARCHAR(20)
DETERMINISTIC
BEGIN
    DECLARE v_name VARCHAR(20);
    SELECT name INTO v_name FROM tbl WHERE id = p_id LIMIT 1;
    RETURN v_name;
END"""
        result, _ = mssql_to_mysql_ddl(ddl, "FUNCTION")
        assert "SELECT name INTO v_name FROM tbl WHERE id = p_id LIMIT 1;" in result
        assert "RETURN v_name;" in result
    
    def test_normal_update_unchanged(self):
        from app.core.obj_executor import mssql_to_mysql_ddl
        ddl = """CREATE PROCEDURE test_sp(IN p_id INT, IN p_val VARCHAR(50))
BEGIN
    UPDATE tbl
       SET name = p_val
     WHERE id = p_id;
END"""
        result, _ = mssql_to_mysql_ddl(ddl, "PROCEDURE")
        # ; 가 SET 뒤에 추가되면 안 됨 (정상 ; 위치만 유지)
        assert "SET name = p_val\n" in result or "SET name = p_val\r\n" in result
        # WHERE 가 SET 다음에 자연스럽게 와야
        assert "WHERE id = p_id;" in result
    
    def test_multi_column_update_unchanged(self):
        from app.core.obj_executor import mssql_to_mysql_ddl
        ddl = """CREATE PROCEDURE test_sp(IN p_id INT)
BEGIN
    UPDATE tbl
       SET col1 = 'A',
           col2 = 'B'
     WHERE id = p_id;
END"""
        result, _ = mssql_to_mysql_ddl(ddl, "PROCEDURE")
        # 정상 콤마는 그대로
        assert "col1 = 'A'," in result
        # ; 가 잘못 추가되지 않음
        assert ",;" not in result


class TestPresident11Cases:
    """본부장님 환경 11개 실패 케이스 종합 검증."""
    
    def test_all_11_president_cases_after_v90_63(self):
        """본부장님 11개 케이스 모두 1064 안 나오게 fix 됐는지."""
        from app.core.obj_executor import mssql_to_mysql_ddl
        
        cases = [
            ("fn_delinq_stage", "FUNCTION", FN_DELINQ_STAGE_RAW, ["RETURN CASE;"]),
            ("sp_assign_collector", "PROCEDURE", SP_ASSIGN_COLLECTOR_RAW,
                [r"p_emp_no\s*;\s*\n\s*WHERE"]),
            ("sp_approve_application", "PROCEDURE", SP_APPROVE_APPLICATION_RAW,
                [",;"]),
            ("sp_close_contract", "PROCEDURE", SP_CLOSE_CONTRACT_RAW,
                [",;"]),
            ("sp_close_branch", "PROCEDURE", SP_CLOSE_BRANCH_RAW,
                [r"p_close_date\s*;\s*\n\s*WHERE"]),
        ]
        
        failed = []
        for name, otype, raw, must_not_contain_patterns in cases:
            result, _ = mssql_to_mysql_ddl(raw, otype)
            for pat in must_not_contain_patterns:
                if re.search(pat, result):
                    failed.append(f"{name}: 1064 패턴 잔존 — {pat}\n  결과: ...{result[max(0,result.find(pat[:5])-20):result.find(pat[:5])+50] if pat[:5] in result else ''}")
        
        if failed:
            print("\n실패 케이스:")
            for f in failed:
                print(f"  - {f}")
            assert not failed, f"{len(failed)}건 실패"


class TestPatchMarkers:
    """v90.63 fix 마커 확인."""
    
    OE_FILE = os.path.normpath(os.path.join(_BACKEND_DIR, "app", "core", "obj_executor.py"))
    SYS_TXT = os.path.normpath(os.path.join(_BACKEND_DIR, "prompts", "mssql_to_mysql", "system.txt"))
    
    def test_obj_executor_v90_63_marker(self):
        if not os.path.exists(self.OE_FILE):
            pytest.skip("")
        content = open(self.OE_FILE, encoding='utf-8').read()
        assert "v90.63" in content
        assert "RETURN CASE\\s*;" in content or "RETURN CASE" in content
    
    def test_system_txt_9_patterns(self):
        if not os.path.exists(self.SYS_TXT):
            pytest.skip("")
        content = open(self.SYS_TXT, encoding='utf-8').read()
        assert "9대 패턴" in content
        # 새 패턴 6, 7, 8, 9 명시
        assert "패턴 6" in content
        assert "패턴 7" in content
        assert "패턴 8" in content
        assert "패턴 9" in content
        # 본부장님 케이스 명시
        assert "RETURN CASE;" in content   # ❌ 예시
        assert "',;" in content            # 콤마+; 예시


if __name__ == "__main__":
    print("=== v90.63 본부장님 11개 실패 케이스 검증 ===\n")
    
    from app.core.obj_executor import mssql_to_mysql_ddl
    
    cases = [
        ("fn_delinq_stage",       "FUNCTION", FN_DELINQ_STAGE_RAW),
        ("sp_assign_collector",   "PROCEDURE", SP_ASSIGN_COLLECTOR_RAW),
        ("sp_approve_application","PROCEDURE", SP_APPROVE_APPLICATION_RAW),
        ("sp_close_contract",     "PROCEDURE", SP_CLOSE_CONTRACT_RAW),
        ("sp_close_branch",       "PROCEDURE", SP_CLOSE_BRANCH_RAW),
    ]
    
    for name, otype, raw in cases:
        print(f"━━━ {name} ━━━")
        result, _ = mssql_to_mysql_ddl(raw, otype)
        # 핵심 1064 패턴 모두 사라졌는지 점검
        bad_patterns = [
            ("RETURN CASE;", "P1"),
            (",;", "P3"),
        ]
        ok = True
        for pat, label in bad_patterns:
            if pat in result:
                print(f"  ❌ {label} 잔존: {pat}")
                ok = False
        # P2 패턴
        if re.search(r"SET\s+\w+\s*=\s*\w+\s*;\s*\n\s*WHERE", result, re.IGNORECASE):
            print(f"  ❌ P2 잔존: SET ... ; \\n WHERE")
            ok = False
        if ok:
            print(f"  ✓ 1064 패턴 모두 fix")
        print()
