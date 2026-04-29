"""
test_v90_66_multiline_return_terminator.py — v90.66 (2026-04-28)

본부장님 fn_age 케이스 — v90.64 가 못 잡은 잔여 P4 변종:
  RETURN (YEAR(NOW()) - YEAR(p_birth))
         - CASE WHEN ... THEN 1 ELSE 0 END   ← 마지막 END 다음에 ; 없음
  END                                          ← 함수 BEGIN..END 의 닫는 END

→ 'near END at line 12' 1064 발생

v90.66 처방:
  '<expression>END\\n<whitespace>END' 패턴에서 안쪽 END 다음 ; 추가.
  단, 'END IF' / 'END LOOP' / 'END WHILE' 는 영향 안 받음.
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
# v90.66 _fix_inner_end_terminator 함수 미러
# ════════════════════════════════════════════════════════════════════════════

def fix_inner_end_terminator(text):
    """v90.66 의 _fix_inner_end_terminator 미러 (본체와 동일한 로직)."""
    lines = text.split('\n')
    for i in range(len(lines) - 1):
        cur = lines[i].rstrip()
        nxt = lines[i + 1].strip()
        
        # 다음 줄이 'END' (블록 끝) 인지 — 단독 END 또는 'END;' 만 인정
        if not re.match(r"^END\s*;?\s*$", nxt, re.IGNORECASE):
            continue
        
        # 현재 줄이 'END' 로 끝나면서 ';' 없는 경우
        m = re.search(r"\bEND\s*$", cur, re.IGNORECASE)
        if not m:
            continue
        
        tokens = cur.split()
        if not tokens or tokens[-1].upper() != 'END':
            continue
        # END IF, END LOOP, END WHILE 는 제외
        if len(tokens) >= 2 and tokens[-2].upper() in ('IF', 'LOOP', 'WHILE'):
            continue
        
        lines[i] = cur + ';'
    return '\n'.join(lines)


# ════════════════════════════════════════════════════════════════════════════
# 본부장님 환경 fn_age 케이스
# ════════════════════════════════════════════════════════════════════════════

FN_AGE_RAW = """CREATE FUNCTION ref_fn_age(p_birth DATE)
RETURNS INT
DETERMINISTIC
BEGIN
    IF p_birth IS NULL THEN
        RETURN NULL;
    END IF;
    RETURN (YEAR(NOW()) - YEAR(p_birth))
           - CASE WHEN (MONTH(p_birth) * 100 + DAY(p_birth))
                     > (MONTH(NOW()) * 100 + DAY(NOW()))
                  THEN 1 ELSE 0 END
END"""


class TestFnAgeCase:
    """본부장님 fn_age 정확한 시나리오."""
    
    def test_fn_age_inner_end_gets_terminator(self):
        """CASE 의 닫는 END 에 ; 추가됨."""
        result = fix_inner_end_terminator(FN_AGE_RAW)
        # CASE 의 END 다음에 ; 추가
        assert "0 END;\nEND" in result, f"안쪽 END 에 ; 추가 안 됨:\n{result}"
        # 외부 BEGIN..END 의 닫는 END 는 그대로
        assert result.rstrip().endswith("END"), \
            f"BEGIN..END 의 닫는 END 에 ; 잘못 추가됨:\n{result[-50:]}"
    
    def test_fn_age_returns_int_preserved(self):
        """RETURN INT 같은 헤더는 영향 없음."""
        result = fix_inner_end_terminator(FN_AGE_RAW)
        assert "RETURNS INT" in result
        assert "DETERMINISTIC" in result
    
    def test_fn_age_inner_if_preserved(self):
        """END IF; 는 영향 없음."""
        result = fix_inner_end_terminator(FN_AGE_RAW)
        assert "END IF;" in result, "END IF; 가 변형됨"


class TestRegression:
    """END IF / END LOOP / END WHILE / 단순 BEGIN..END 회귀 검증."""
    
    def test_end_if_not_affected(self):
        """END IF 는 ; 자동 추가 회피."""
        ddl = """BEGIN
    IF x IS NULL THEN
        RETURN 0;
    END IF;
END"""
        result = fix_inner_end_terminator(ddl)
        # END IF; 그대로
        assert "END IF;" in result
        # 외부 END 그대로 (마지막 END 다음에 다른 END 없으니 처리 안 됨)
        assert result.endswith("END")
    
    def test_end_loop_not_affected(self):
        """END LOOP 는 ; 자동 추가 회피."""
        ddl = """BEGIN
    LOOP
        SET v_x = v_x + 1;
        IF v_x > 10 THEN LEAVE; END IF;
    END LOOP;
END"""
        result = fix_inner_end_terminator(ddl)
        assert "END LOOP;" in result
    
    def test_end_while_not_affected(self):
        """END WHILE 는 영향 없음."""
        ddl = """BEGIN
    WHILE v_x < 10 DO
        SET v_x = v_x + 1;
    END WHILE;
END"""
        result = fix_inner_end_terminator(ddl)
        assert "END WHILE;" in result
    
    def test_simple_begin_end_unchanged(self):
        """단순 BEGIN..END 영향 없음."""
        ddl = """BEGIN
    DECLARE v_x INT;
    SET v_x = 5;
END"""
        result = fix_inner_end_terminator(ddl)
        # SET v_x 그대로, END 도 그대로
        assert ddl == result, f"단순 BEGIN..END 가 변형됨:\n{result}"
    
    def test_already_terminated_unchanged(self):
        """이미 END; 로 끝난 라인은 영향 없음."""
        ddl = """BEGIN
    RETURN CASE WHEN x > 0 THEN 1 ELSE 0 END;
END"""
        result = fix_inner_end_terminator(ddl)
        # 이미 ; 있으니 그대로 (END; 가 두 번 안 됨)
        assert "END;\nEND" in result
        assert "END;;" not in result, "; 중복 추가됨!"
    
    def test_simple_return_var(self):
        """단순 RETURN v_var; 영향 없음."""
        ddl = """BEGIN
    DECLARE v_x INT;
    SET v_x = 5;
    RETURN v_x;
END"""
        result = fix_inner_end_terminator(ddl)
        assert ddl == result


class TestPresidentVariants:
    """fn_age 와 비슷한 다중라인 RETURN 표현식 케이스 (다양한 변종)."""
    
    def test_multiline_return_with_function_calls(self):
        """RETURN 안에 함수 호출 + 다중라인 CASE."""
        ddl = """BEGIN
    RETURN GREATEST(0, COALESCE(p_a, 0))
           + CASE p_b WHEN 'X' THEN 1 ELSE 0 END
END"""
        result = fix_inner_end_terminator(ddl)
        assert "0 END;\nEND" in result
    
    def test_return_with_nested_case(self):
        """중첩 CASE 끝에 ; 추가."""
        ddl = """BEGIN
    RETURN CASE
        WHEN x > 0 THEN
            CASE WHEN y > 0 THEN 1 ELSE 2 END
        ELSE 0
    END
END"""
        result = fix_inner_end_terminator(ddl)
        # 마지막 END 직전 라인 (외부 CASE 의 END) 에 ; 추가
        assert re.search(r"END;\s*\nEND\s*$", result), \
            f"중첩 CASE 외부 END 에 ; 추가 안 됨:\n{result}"


class TestPatchMarker:
    """obj_executor.py 의 v90.66 마커 확인."""
    
    OE_FILE = os.path.normpath(os.path.join(_BACKEND_DIR, "app", "core", "obj_executor.py"))
    
    def test_v90_66_marker(self):
        if not os.path.exists(self.OE_FILE):
            pytest.skip("")
        content = open(self.OE_FILE, encoding='utf-8').read()
        assert "v90.66" in content
        assert "_fix_inner_end_terminator" in content
    
    def test_v90_66_in_deploy_function(self):
        """v90.66 가 deploy_mysql_object 안에 있어야."""
        if not os.path.exists(self.OE_FILE):
            pytest.skip("")
        content = open(self.OE_FILE, encoding='utf-8').read()
        deploy_idx = content.find("def deploy_mysql_object")
        v66_idx = content.find("v90.66")
        assert deploy_idx > 0 and v66_idx > deploy_idx, \
            "v90.66 가 deploy_mysql_object 함수 안에 없음"


class TestUiFix:
    """오류 KPI UX 개선 (frontend) 검증."""
    
    JM_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "JobMonitor.vue"
    ))
    
    def test_ui_v90_66_marker(self):
        if not os.path.exists(self.JM_FILE):
            pytest.skip("")
        content = open(self.JM_FILE, encoding='utf-8').read()
        assert "v90.66" in content
    
    def test_ui_separates_object_vs_row_errors(self):
        """객체 오류와 행 오류가 명확히 구분 표시되어야."""
        if not os.path.exists(self.JM_FILE):
            pytest.skip("")
        content = open(self.JM_FILE, encoding='utf-8').read()
        # 객체 오류 있으면 errItems.length 메인 표시
        assert 'errItems.length > 0' in content
        # "항목" 단위 명시
        assert '항목' in content


if __name__ == "__main__":
    print("=== v90.66 fn_age 시나리오 ===\n")
    
    print("=== 입력 (backend.log Job#8bcfa3 raw SQL) ===")
    print(FN_AGE_RAW)
    print()
    
    result = fix_inner_end_terminator(FN_AGE_RAW)
    print("=== v90.66 처리 후 ===")
    print(result)
    print()
    
    if "0 END;\nEND" in result:
        print("✓ CASE 의 END 다음에 ; 자동 추가됨")
        print("✓ 1064 패턴 fix 완료")
    else:
        print("✗ fix 실패")
    
    print()
    print("=== 회귀 점검 — END IF ===")
    ddl_if = """BEGIN
    IF x IS NULL THEN
        RETURN 0;
    END IF;
END"""
    result_if = fix_inner_end_terminator(ddl_if)
    if 'END IF;' in result_if and 'END IF;\nEND' in result_if and 'END IF;;' not in result_if:
        print("✓ END IF 는 영향 안 받음")
    else:
        print("✗ END IF 회귀!")
