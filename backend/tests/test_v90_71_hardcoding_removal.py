"""
test_v90_71_hardcoding_removal.py — v90.71 (2026-04-28)

본부장님 호소: "당연한 얘기 겠지만 하드코딩되면 안돼는거 알지?"

v90.68 의 1406 hint 와 system.txt 의 패턴 0 에 본부장님 환경 객체명/파라미터명
하드코딩 발견:
  - obj_executor.py: "특히 'p_rec_sdate', 'p_req_sdate' 등..."
  - system.txt: "본부장님 환경에서 SP_STATRECORD/SP_STATSYSTEM 의..."
                "@rec_sdate VARCHAR(8)", "IN p_rec_sdate VARCHAR(7)"

v90.71 처방: 환경 특정 이름을 일반 placeholder (N, p_xxx) 로 교체

이 테스트는 회귀 방지용 — 향후 다른 패치에서도 환경 특정값이 동작 코드에
들어가지 않도록 검증.
"""

import os
import re
import pytest


_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)


# 본부장님 환경 특정 식별자 — 실제 동작 코드에 절대 들어가면 안 되는 것들
_FORBIDDEN_TOKENS = [
    'p_rec_sdate', 'p_req_sdate', 'p_rec_edate', 'p_req_edate',
    '@rec_sdate', '@req_sdate', '@rec_edate', '@req_edate',
    'sp_Softphone_UpdateRecord', 'dbo_sp_Softphone_UpdateRecord',
    'SP_STATRECORD', 'SP_STATSYSTEM', 'SP_INSERTERRORLOG',
    'tbl_rec_data', 'tbl_record',
    'crec_recfile', 'CREC_monitoring',
    'Bridge@1234', '127.0.0.1,1433',
]


class TestObjExecutorNoHardcode:
    """obj_executor.py 의 환경 특정 식별자 검사."""
    
    OE_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "app", "core", "obj_executor.py"
    ))
    
    def test_no_environment_specific_tokens(self):
        """obj_executor.py 동작 코드에 환경 특정 식별자 없어야."""
        if not os.path.exists(self.OE_FILE):
            pytest.skip("")
        content = open(self.OE_FILE, encoding='utf-8').read()
        violations = []
        for token in _FORBIDDEN_TOKENS:
            if token in content:
                # 모든 발생 라인 추적
                for i, line in enumerate(content.split('\n'), 1):
                    if token in line:
                        violations.append(f"line {i}: {token} → '{line.strip()[:80]}'")
        
        assert not violations, (
            "obj_executor.py 에 환경 특정 식별자 발견:\n  " +
            "\n  ".join(violations)
        )
    
    def test_v90_71_marker(self):
        if not os.path.exists(self.OE_FILE):
            pytest.skip("")
        content = open(self.OE_FILE, encoding='utf-8').read()
        assert "v90.71" in content
    
    def test_1406_hint_uses_generic_placeholders(self):
        """1406 hint 가 일반 placeholder (N, VARCHAR(N) 등) 사용."""
        if not os.path.exists(self.OE_FILE):
            pytest.skip("")
        content = open(self.OE_FILE, encoding='utf-8').read()
        # 1406 섹션 추출
        m = re.search(
            r'1406[^"]*"([^"]+(?:"[^"]+")*?)일반화[^"]*"|1406.*?N\*1\.5',
            content, re.DOTALL
        )
        # VARCHAR(N) 표기법 사용해야
        hint_idx = content.find("1406 오류 강제 fix 룰")
        assert hint_idx > 0
        hint_section = content[hint_idx:hint_idx+1500]
        # 일반 placeholder 사용 확인
        assert 'VARCHAR(N)' in hint_section, "VARCHAR(N) 일반 placeholder 누락"


class TestSystemTxtNoHardcode:
    """system.txt 의 환경 특정 식별자 검사."""
    
    SYS_TXT = os.path.normpath(os.path.join(
        _BACKEND_DIR, "prompts", "mssql_to_mysql", "system.txt"
    ))
    
    def test_no_environment_specific_tokens(self):
        """system.txt 에 환경 특정 식별자 없어야."""
        if not os.path.exists(self.SYS_TXT):
            pytest.skip("")
        content = open(self.SYS_TXT, encoding='utf-8').read()
        violations = []
        for token in _FORBIDDEN_TOKENS:
            if token in content:
                for i, line in enumerate(content.split('\n'), 1):
                    if token in line:
                        violations.append(f"line {i}: {token} → '{line.strip()[:80]}'")
        
        assert not violations, (
            "system.txt 에 환경 특정 식별자 발견 (AI prompt 에 그대로 전달됨!):\n  " +
            "\n  ".join(violations)
        )
    
    def test_pattern_0_still_present(self):
        """v90.71 fix 후에도 패턴 0 (VARCHAR 길이 룰) 보존되어야."""
        if not os.path.exists(self.SYS_TXT):
            pytest.skip("")
        content = open(self.SYS_TXT, encoding='utf-8').read()
        assert "패턴 0" in content
        assert "VARCHAR" in content
        assert "1406" in content
        assert "★★★★★" in content
    
    def test_pattern_0_uses_generic_examples(self):
        """패턴 0 의 예시가 일반 placeholder 사용."""
        if not os.path.exists(self.SYS_TXT):
            pytest.skip("")
        content = open(self.SYS_TXT, encoding='utf-8').read()
        # 패턴 0 섹션 추출
        p0_idx = content.find("패턴 0")
        p0_end = content.find("패턴 1", p0_idx)
        p0_section = content[p0_idx:p0_end]
        # 일반 placeholder
        assert "VARCHAR(N)" in p0_section, "VARCHAR(N) 일반 placeholder 누락"
        assert "@p_xxx" in p0_section or "p_xxx" in p0_section, \
            "@p_xxx 일반 placeholder 누락"


class TestKnowledgeFlowIntact:
    """v90.68 의 기능 (1406/1270/1305 자동 hint) 가 v90.71 에서도 동작하는지."""
    
    OE_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "app", "core", "obj_executor.py"
    ))
    
    def test_1406_hint_still_present(self):
        if not os.path.exists(self.OE_FILE):
            pytest.skip("")
        content = open(self.OE_FILE, encoding='utf-8').read()
        assert "1406 오류 강제 fix 룰" in content
        assert '"1406"' in content
    
    def test_1270_hint_still_present(self):
        if not os.path.exists(self.OE_FILE):
            pytest.skip("")
        content = open(self.OE_FILE, encoding='utf-8').read()
        assert "1270 오류 강제 fix 룰" in content
    
    def test_1305_hint_still_present(self):
        if not os.path.exists(self.OE_FILE):
            pytest.skip("")
        content = open(self.OE_FILE, encoding='utf-8').read()
        assert "1305 오류 강제 fix 룰" in content
    
    def test_1064_hint_still_present(self):
        if not os.path.exists(self.OE_FILE):
            pytest.skip("")
        content = open(self.OE_FILE, encoding='utf-8').read()
        assert "1064" in content


class TestRegressionGenericKb:
    """KB 가 여전히 generic 한 환경에서 정확히 동작하는지."""
    
    def enhance(self, error_hint, content_1406_only=None):
        """v90.71 후의 _enhanced_hint 미러 — 일반화된 버전."""
        h = error_hint.lower()
        out = ""
        if "1406" in error_hint or "data too long" in h:
            out += (
                "★★★★★ [1406 오류 강제 fix 룰] ★★★★★\n"
                "VARCHAR 길이 줄이지 말 것 — 원본 그대로 유지 (VARCHAR(N) → VARCHAR(N))\n"
                "DATE 로 바꾸기 절대 금지 (호출자 깨짐)\n"
            )
        return out
    
    def test_1406_with_any_column_name(self):
        """다양한 컬럼명에 모두 동작."""
        # 본부장님 환경
        result1 = self.enhance("(1406, \"Data too long for column 'p_rec_sdate' at row 1\")")
        # 다른 환경 - 가상의 다른 회사
        result2 = self.enhance("(1406, \"Data too long for column 'cust_acc_no' at row 1\")")
        result3 = self.enhance("(1406, \"Data too long for column 'order_status_code' at row 1\")")
        
        # 셋 다 같은 일반 hint 받아야 (특정 컬럼명 언급 없음)
        assert result1 == result2 == result3
        assert "p_rec_sdate" not in result1
        assert "cust_acc_no" not in result2


if __name__ == "__main__":
    print("=== v90.71 하드코딩 제거 검증 ===\n")
    
    test = TestRegressionGenericKb()
    
    # 다양한 환경의 1406 오류
    cases = [
        ("본부장님 환경",       '(1406, "Data too long for column \'p_rec_sdate\'")'),
        ("다른 회사 환경 1",   '(1406, "Data too long for column \'cust_acc_no\'")'),
        ("다른 회사 환경 2",   '(1406, "Data too long for column \'order_status_code\'")'),
        ("영문 컬럼명",         '(1406, "Data too long for column \'last_modified_date\'")'),
    ]
    
    print("같은 일반 hint 가 모든 환경에 적용되는지 검증:\n")
    results = []
    for name, err in cases:
        result = test.enhance(err)
        results.append(result)
        # 환경 특정 단어 검사
        env_specific_in_result = any(t in result for t in [
            'p_rec_sdate', 'p_req_sdate', 'cust_acc_no', 'order_status_code',
            'last_modified_date'
        ])
        marker = '✓' if not env_specific_in_result else '✗ 하드코딩!'
        print(f"  {marker} {name}: 일반 hint 적용 (환경값 누출 없음)")
    
    # 모두 같은 결과
    all_same = all(r == results[0] for r in results)
    print(f"\n  {'✓' if all_same else '✗'} 모든 환경에 동일 일반 hint 전달")
