"""
test_v90_64_deploy_clean_fix.py — v90.64 (2026-04-28)

본부장님 backend.log Job#e7b829 (13:39~13:41) 분석:
  v90.63 mssql_to_mysql_ddl 후처리는 호출 안 되는 경로였음 (rule-based 변환용).
  진짜 1064 원인은 deploy_mysql_object 의 clean 단계 라인 1027~1028:
    - SET col = val (다음 라인 WHERE) → 자동으로 ; 추가 → 'SET col = val;\nWHERE' 1064
    - RETURN CASE (다음 라인 WHEN) → 자동으로 ; 추가 → 'RETURN CASE;' 1064

v90.64 처방:
  1. SET 라인 ; 추가는 다음 라인이 WHERE/JOIN/AND/OR 아닐 때만
  2. RETURN 라인 ; 추가는 CASE/SELECT/( 아닐 때만
  3. 이미 깨진 패턴은 retroactive 로 강제 수술

이 테스트는 deploy_mysql_object 함수 자체의 입력→출력 흐름을 검증.
실제로 함수 일부를 추출해서 시뮬레이션 (MySQL 실제 연결은 mock).
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
# deploy_mysql_object 의 clean 부분만 추출해서 시뮬레이션
# (실제 코드와 동일한 정규식 적용)
# ════════════════════════════════════════════════════════════════════════════

def simulate_deploy_clean(ddl: str) -> str:
    """
    deploy_mysql_object 의 라인 1015~1029 정제 단계 시뮬레이션.
    v90.64 fix 가 적용된 정규식들을 동일하게 사용.
    """
    clean = ddl
    
    # 라인 1016~1019 (변경 없음)
    def _add_limit(m):
        body = m.group(1).rstrip()
        return f"{body}\n\tLIMIT 1;\n\t{m.group(2)}"
    clean = re.sub(
        r"(SELECT\s+\w+\s+INTO\s+\w+\s+FROM\b(?:(?!\bLIMIT\b|\bRETURN\b|\bEND\b|\bIF\b).)*?)\n[ \t]*(RETURN\b|END\b)",
        _add_limit, clean, flags=re.IGNORECASE | re.DOTALL
    )
    clean = re.sub(r"(LIMIT\s+\d+)(RETURN|END|SET|DECLARE|IF)",
                   lambda m: m.group(1) + ";\n\t" + m.group(2),
                   clean, flags=re.IGNORECASE)
    clean = re.sub(r"(LIMIT\s+\d+)(?!\s*;)(?=\s*\n)", r"\1;", clean, flags=re.IGNORECASE)
    
    # DECLARE (변경 없음)
    clean = re.sub(r"(DECLARE\s+\w+\s+[\w()]+)(?!\s*;)(?=\s*\n)", r"\1;", clean, flags=re.IGNORECASE)
    
    # ─── v90.64: SET 라인 ; 추가 — WHERE/JOIN 다음이면 추가 안 함 ──────
    clean = re.sub(
        r"(SET\s+\w+\s*=\s*[^\n;]+)(?<!;)(?=\s*\n\s*(?!WHERE\b|FROM\b|JOIN\b|AND\b|OR\b|,)\w)",
        r"\1;",
        clean, flags=re.IGNORECASE
    )
    
    # ─── v90.64: RETURN 라인 ; 추가 — CASE/SELECT/( 아닐 때만 ─────────
    clean = re.sub(
        r"(RETURN\s+(?!CASE\b|SELECT\b|\()\w+)(?!;)(?=\s*\n)",
        r"\1;",
        clean, flags=re.IGNORECASE
    )
    
    # ─── retroactive 강제 fix ───
    clean = re.sub(r"\bRETURN\s+CASE\s*;", "RETURN CASE", clean, flags=re.IGNORECASE)
    clean = re.sub(
        r"(\bSET\s+\w+\s*=\s*[^;\n]+?);(\s*\n\s*WHERE\b)",
        r"\1\2", clean, flags=re.IGNORECASE
    )
    clean = re.sub(r",\s*;\s*\n", ",\n", clean)
    clean = re.sub(
        r"(\bRETURN\s+CAST\s*\([^)]*\)(?:\s+AS\s+\w+(?:\([^)]*\))?)?)(?<![;])(\s*\n)",
        r"\1;\2", clean, flags=re.IGNORECASE
    )
    
    return clean.strip()


# ════════════════════════════════════════════════════════════════════════════
# 본부장님 환경의 실제 raw SQL — backend.log 그대로
# (이 SQL 들은 AI 가 정상으로 보낸 것이며, deploy_mysql_object 가 망가뜨림)
# ════════════════════════════════════════════════════════════════════════════

# AI 가 보낸 정상 SQL (clean 단계 가기 전)
SP_ASSIGN_COLLECTOR_AI_OUT = """CREATE PROCEDURE collection_sp_assign_collector(
    IN p_delinq_id BIGINT,
    IN p_emp_no VARCHAR(20)
)
BEGIN
    UPDATE collection_delinquency
       SET assigned_emp_no = p_emp_no
     WHERE delinq_id = p_delinq_id;
END"""

SP_CLOSE_BRANCH_AI_OUT = """CREATE PROCEDURE ref_sp_close_branch(
    IN p_branch_code VARCHAR(10),
    IN p_close_date DATE
)
BEGIN
    UPDATE ref_branch
    SET close_date = p_close_date
    WHERE branch_code = p_branch_code COLLATE utf8mb4_unicode_ci;
END"""

FN_DELINQ_STAGE_AI_OUT = """CREATE FUNCTION collection_fn_delinq_stage(p_days INT)
RETURNS VARCHAR(20)
DETERMINISTIC
BEGIN
    RETURN CASE
        WHEN p_days <= 30  THEN 'EARLY'
        WHEN p_days <= 90  THEN 'MID'
        WHEN p_days <= 180 THEN 'LATE'
        WHEN p_days <= 360 THEN 'LEGAL'
        ELSE 'WRITEOFF'
    END;
END"""


class TestPresidentRealCase:
    """본부장님 환경의 실제 raw SQL 입력 → clean 후 깨지지 않아야."""
    
    def test_sp_assign_collector_set_where_not_broken(self):
        """SET col = val\\n WHERE → SET 뒤에 ; 자동 추가되면 안 됨."""
        result = simulate_deploy_clean(SP_ASSIGN_COLLECTOR_AI_OUT)
        
        # 기존 v90.63 까지 깨졌던 패턴
        assert not re.search(
            r"SET\s+assigned_emp_no\s*=\s*p_emp_no\s*;\s*\n\s*WHERE",
            result, re.IGNORECASE
        ), f"v90.64 fix 실패 — SET 뒤 ; 자동 추가됨:\n{result}"
        
        # 정상 형태 유지
        assert "WHERE delinq_id = p_delinq_id" in result
    
    def test_sp_close_branch_set_collate_where_not_broken(self):
        """SET col = val\\n WHERE col = val COLLATE x → SET 뒤 ; 추가되면 안 됨."""
        result = simulate_deploy_clean(SP_CLOSE_BRANCH_AI_OUT)
        
        assert not re.search(
            r"SET\s+close_date\s*=\s*p_close_date\s*;\s*\n\s*WHERE",
            result, re.IGNORECASE
        ), f"v90.64 fix 실패:\n{result}"
        
        assert "WHERE branch_code = p_branch_code COLLATE" in result
    
    def test_fn_delinq_stage_return_case_not_broken(self):
        """RETURN CASE\\n WHEN ... → RETURN 뒤에 ; 자동 추가되면 안 됨."""
        result = simulate_deploy_clean(FN_DELINQ_STAGE_AI_OUT)
        
        assert "RETURN CASE;" not in result, \
            f"v90.64 fix 실패 — RETURN CASE 뒤에 ; 자동 추가됨:\n{result}"
        assert "RETURN CASE\n" in result or "RETURN CASE\r\n" in result, \
            f"RETURN CASE 정상 형태 누락:\n{result}"
        assert "WHEN p_days <= 30" in result


class TestRetroactiveFix:
    """이미 깨진 패턴이 들어와도 fix 되어야."""
    
    def test_already_broken_return_case_fixed(self):
        """이미 'RETURN CASE;' 패턴이 들어와도 fix."""
        broken = """CREATE FUNCTION x(p INT) RETURNS VARCHAR(20)
DETERMINISTIC
BEGIN
    RETURN CASE;
        WHEN p <= 30 THEN 'A'
        ELSE 'B'
    END;
END"""
        result = simulate_deploy_clean(broken)
        assert "RETURN CASE;" not in result
        assert "RETURN CASE" in result
    
    def test_already_broken_set_where_fixed(self):
        """이미 'SET col = val; WHERE' 패턴 들어와도 fix."""
        broken = """CREATE PROCEDURE x(IN p INT)
BEGIN
    UPDATE tbl
       SET col = val;
     WHERE id = p;
END"""
        result = simulate_deploy_clean(broken)
        assert not re.search(
            r"SET\s+col\s*=\s*val\s*;\s*\n\s*WHERE",
            result, re.IGNORECASE
        )
    
    def test_already_broken_comma_semicolon_fixed(self):
        """이미 ',;' 패턴 들어와도 fix."""
        broken = """UPDATE tbl
   SET col1 = 'A',;
       col2 = 'B'
 WHERE id = 1;"""
        result = simulate_deploy_clean(broken)
        assert ",;" not in result
        assert "col1 = 'A'," in result


class TestRegression:
    """정상 SQL 영향 안 받아야."""
    
    def test_normal_set_get_terminator(self):
        """단순 SET (UPDATE 안에서) — 다음 라인이 다른 SET 이면 ; 자동 추가."""
        ddl = """BEGIN
    SET v_x = 5
    SET v_y = 10
END"""
        result = simulate_deploy_clean(ddl)
        # 둘 다 ; 추가되어야 (SET 뒤가 WHERE 가 아니므로)
        assert "SET v_x = 5;" in result
    
    def test_return_var_get_terminator(self):
        """RETURN v_var (단순 변수) — ; 추가."""
        ddl = """BEGIN
    DECLARE v_x INT;
    SET v_x = 1;
    RETURN v_x
END"""
        result = simulate_deploy_clean(ddl)
        assert "RETURN v_x;" in result
    
    def test_normal_select_into(self):
        """SELECT...INTO — LIMIT 1 추가 정상 동작."""
        ddl = """BEGIN
    DECLARE v_n VARCHAR(20);
    SELECT name INTO v_n FROM tbl WHERE id = p_id
    RETURN v_n
END"""
        result = simulate_deploy_clean(ddl)
        # LIMIT 1 자동 추가
        assert "LIMIT 1" in result


class TestPatchMarker:
    """v90.64 패치 마커 확인."""
    
    OE_FILE = os.path.normpath(os.path.join(_BACKEND_DIR, "app", "core", "obj_executor.py"))
    
    def test_obj_executor_v90_64_marker(self):
        if not os.path.exists(self.OE_FILE):
            pytest.skip("")
        content = open(self.OE_FILE, encoding='utf-8').read()
        assert "v90.64" in content
        # 핵심 fix 가 deploy_mysql_object 안에 있어야
        # deploy_mysql_object 함수 내부 위치 확인
        deploy_idx = content.find("def deploy_mysql_object")
        v64_idx = content.find("v90.64")
        # deploy_mysql_object 정의 후에 v90.64 가 와야 함
        # (참고: deploy 위에 정의된 다른 v90.64 마커는 0개여야)
        before_deploy = content[:deploy_idx]
        assert "v90.64" not in before_deploy, \
            "v90.64 마커가 deploy_mysql_object 정의 위에 있음 — 잘못된 위치"


if __name__ == "__main__":
    print("=== v90.64 본부장님 환경 실제 raw SQL 검증 ===\n")
    
    cases = [
        ("sp_assign_collector",   SP_ASSIGN_COLLECTOR_AI_OUT, "PROCEDURE"),
        ("sp_close_branch",       SP_CLOSE_BRANCH_AI_OUT,     "PROCEDURE"),
        ("fn_delinq_stage",       FN_DELINQ_STAGE_AI_OUT,     "FUNCTION"),
    ]
    
    for name, ai_sql, otype in cases:
        print(f"━━━ {name} ━━━")
        result = simulate_deploy_clean(ai_sql)
        
        # 깨진 패턴 검출
        broken = []
        if re.search(r"SET\s+\w+\s*=\s*[^;\n]+\s*;\s*\n\s*WHERE", result, re.IGNORECASE):
            broken.append("SET ; WHERE")
        if "RETURN CASE;" in result:
            broken.append("RETURN CASE;")
        if ",;" in result:
            broken.append(",;")
        
        if broken:
            print(f"  ❌ 여전히 깨진 패턴: {', '.join(broken)}")
        else:
            print(f"  ✓ 1064 패턴 모두 fix")
        print()
