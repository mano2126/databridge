"""
test_v90_68_varchar_length_kb.py — v90.68 (2026-04-28)

본부장님 SP_STATRECORD/SP_STATSYSTEM 의 1406 오류 반복 발생.
4월 11일에 KB 추가했지만 system.txt 에서 강조도 부족 + AI 가 무시.

v90.68 처방:
  1. system.txt — VARCHAR 길이 룰을 ★★★★★ 패턴 0 (최우선) 으로 승격
  2. system.txt — 체크리스트 최상단에 추가 ("줄이면 1406!")
  3. obj_executor.py — error_hint 의 1406/1270/1305 자동 hint 강화
  4. Validate.vue — _makeDummyValue 에 targetMaxLength 옵션 추가
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
# system.txt 검증
# ════════════════════════════════════════════════════════════════════════════

class TestSystemTxt:
    """system.txt 의 패턴 0 (VARCHAR 길이) 강화 검증."""
    
    SYS_TXT = os.path.normpath(os.path.join(
        _BACKEND_DIR, "prompts", "mssql_to_mysql", "system.txt"
    ))
    
    def test_pattern_0_exists(self):
        if not os.path.exists(self.SYS_TXT):
            pytest.skip("")
        content = open(self.SYS_TXT, encoding='utf-8').read()
        assert "패턴 0" in content, "패턴 0 누락"
        assert "★★★★★" in content, "★★★★★ 강조 누락"
    
    def test_pattern_0_is_first(self):
        """패턴 0 가 패턴 1 보다 앞에 와야 함 (최우선)."""
        if not os.path.exists(self.SYS_TXT):
            pytest.skip("")
        content = open(self.SYS_TXT, encoding='utf-8').read()
        idx_0 = content.find("패턴 0")
        idx_1 = content.find("패턴 1")
        assert idx_0 > 0 and idx_1 > 0
        assert idx_0 < idx_1, "패턴 0 가 패턴 1 보다 뒤에 있음"
    
    def test_v90_68_marker(self):
        if not os.path.exists(self.SYS_TXT):
            pytest.skip("")
        content = open(self.SYS_TXT, encoding='utf-8').read()
        assert "v90.68" in content
    
    def test_varchar_length_examples(self):
        """VARCHAR 길이 룰의 명확한 ❌/✅ 예시."""
        if not os.path.exists(self.SYS_TXT):
            pytest.skip("")
        content = open(self.SYS_TXT, encoding='utf-8').read()
        assert "VARCHAR(8)" in content
        assert "1406" in content
        assert "Data too long" in content
        # ❌ 와 ✅ 명시
        assert "❌" in content
        assert "✅" in content
    
    def test_checklist_has_pattern_0(self):
        """체크리스트 최상단에 패턴 0 추가."""
        if not os.path.exists(self.SYS_TXT):
            pytest.skip("")
        content = open(self.SYS_TXT, encoding='utf-8').read()
        # 체크리스트 부분 추출
        ck_idx = content.find("자체 검증 체크리스트")
        if ck_idx > 0:
            checklist = content[ck_idx:ck_idx+1500]
            assert "VARCHAR 파라미터 길이" in checklist, "체크리스트에 VARCHAR 길이 누락"
            assert "1406" in checklist, "체크리스트에 1406 명시 누락"
    
    def test_header_says_10_patterns(self):
        if not os.path.exists(self.SYS_TXT):
            pytest.skip("")
        content = open(self.SYS_TXT, encoding='utf-8').read()
        # 9대 → 10대 변경
        assert "10대" in content


# ════════════════════════════════════════════════════════════════════════════
# obj_executor.py 검증
# ════════════════════════════════════════════════════════════════════════════

class TestObjExecutor:
    """obj_executor.py 의 error_hint 자동 강화."""
    
    OE_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "app", "core", "obj_executor.py"
    ))
    
    def test_v90_68_marker(self):
        if not os.path.exists(self.OE_FILE):
            pytest.skip("")
        content = open(self.OE_FILE, encoding='utf-8').read()
        assert "v90.68" in content
    
    def test_1406_auto_hint(self):
        if not os.path.exists(self.OE_FILE):
            pytest.skip("")
        content = open(self.OE_FILE, encoding='utf-8').read()
        # 1406 자동 hint 포함
        assert '"1406"' in content
        assert "[1406 오류 강제 fix 룰]" in content
        assert "원본 MSSQL 그대로 유지" in content
    
    def test_1270_auto_hint(self):
        if not os.path.exists(self.OE_FILE):
            pytest.skip("")
        content = open(self.OE_FILE, encoding='utf-8').read()
        assert '"1270"' in content or "Illegal mix" in content.lower() or "illegal mix" in content
        assert "[1270 오류 강제 fix 룰]" in content
    
    def test_1305_auto_hint(self):
        if not os.path.exists(self.OE_FILE):
            pytest.skip("")
        content = open(self.OE_FILE, encoding='utf-8').read()
        assert "[1305 오류 강제 fix 룰]" in content


# ════════════════════════════════════════════════════════════════════════════
# Frontend Validate.vue 검증
# ════════════════════════════════════════════════════════════════════════════

class TestValidate:
    """Validate.vue 의 _makeDummyValue 강화."""
    
    VAL_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "Validate.vue"
    ))
    
    def test_v90_68_marker(self):
        if not os.path.exists(self.VAL_FILE):
            pytest.skip("")
        content = open(self.VAL_FILE, encoding='utf-8').read()
        assert "v90.68" in content
    
    def test_target_max_length_param(self):
        """_makeDummyValue 에 targetMaxLength 파라미터 추가."""
        if not os.path.exists(self.VAL_FILE):
            pytest.skip("")
        content = open(self.VAL_FILE, encoding='utf-8').read()
        assert "targetMaxLength" in content


# ════════════════════════════════════════════════════════════════════════════
# 시뮬레이션 — 1406 오류 시 prompt 강화 효과
# ════════════════════════════════════════════════════════════════════════════

class TestErrorHintEnhancement:
    """error_hint 자동 강화 로직 미러 (Python 시뮬레이션)."""
    
    def enhance(self, error_hint):
        """v90.68 의 _enhanced_hint 미러."""
        h = error_hint.lower()
        out = ""
        if "1406" in error_hint or "data too long" in h:
            out += "★★★★★ [1406 오류 강제 fix 룰]\n원본 MSSQL 그대로 유지\nVARCHAR 를 DATE 로 바꾸기 절대 금지"
        if "1270" in error_hint or "illegal mix" in h or "collation" in h:
            out += "\n★★★★★ [1270 오류 강제 fix 룰]\nCOLLATE utf8mb4_unicode_ci 명시"
        if "1305" in error_hint or "does not exist" in h:
            out += "\n★★★★★ [1305 오류 강제 fix 룰]\n언더스코어 평탄화"
        if "1064" in error_hint or "sql syntax" in h:
            out += "\n★★★ [1064 오류] 9대 패턴 검토"
        return out
    
    def test_1406_triggers_varchar_rule(self):
        err = '(1406, "Data too long for column \'p_rec_sdate\' at row 1")'
        result = self.enhance(err)
        assert "VARCHAR" in result
        assert "1406" in result
        assert "DATE 로 바꾸기 절대 금지" in result
    
    def test_1270_triggers_collation_rule(self):
        err = '(1270, "Illegal mix of collations for operation")'
        result = self.enhance(err)
        assert "COLLATE" in result
        assert "1270" in result
    
    def test_1305_triggers_naming_rule(self):
        err = '(1305, "PROCEDURE testdb.sp_Foo does not exist")'
        result = self.enhance(err)
        assert "언더스코어" in result or "1305" in result
    
    def test_1064_triggers_pattern_rule(self):
        err = '(1064, "You have an error in your SQL syntax")'
        result = self.enhance(err)
        assert "1064" in result
        assert "9대 패턴" in result
    
    def test_unknown_error_no_extra_hint(self):
        err = "(99999, 'unknown error')"
        result = self.enhance(err)
        # 매치 안 됨 — 빈 문자열
        assert result == ""
    
    def test_multiple_errors_all_enhanced(self):
        """1406 + 1270 둘 다 있으면 둘 다 hint 추가."""
        err = "(1406, 'Data too long') and (1270, 'collation')"
        result = self.enhance(err)
        assert "VARCHAR" in result
        assert "COLLATE" in result


if __name__ == "__main__":
    print("=== v90.68 본부장님 1406 시나리오 시뮬레이션 ===\n")
    
    test = TestErrorHintEnhancement()
    
    cases = [
        ('1406 (SP_STATRECORD)',  '(1406, "Data too long for column \'p_rec_sdate\' at row 1")'),
        ('1270 (Collation)',      '(1270, "Illegal mix of collations for operation")'),
        ('1305 (sp_Softphone)',   '(1305, "PROCEDURE testdb.sp_Foo does not exist")'),
        ('1064 (SQL syntax)',     '(1064, "You have an error in your SQL syntax")'),
        ('Unknown error',         '(99999, "something else")'),
    ]
    
    for name, err in cases:
        print(f"━━━ {name} ━━━")
        print(f"  입력: {err}")
        result = test.enhance(err)
        if result:
            print(f"  ✓ 자동 hint 추가됨:")
            for line in result.strip().split('\n'):
                print(f"    {line}")
        else:
            print(f"  - hint 추가 없음 (일반 오류)")
        print()
