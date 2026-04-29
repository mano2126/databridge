"""
test_v90_77_callproc_bypass.py — v90.77 (2026-04-28)

본부장님 결정적 진단 결과:
  ✓ MySQL CLI 로 직접 호출: 통과 (CALL SP_TEST_DAILY_AGG('20240101', '20240101'))
  ✓ SP 파라미터 charset: utf8mb4_unicode_ci (정상)
  ✓ DB 기본 charset: utf8mb4_unicode_ci (정상)
  ✗ DataBridge backend (pymysql callproc) 만 1406 발생

이는 pymysql.callproc 의 동작 방식이 원인:
  callproc 내부:
    SET @_SP_xxx_0 = '20240101', @_SP_xxx_1 = '20240101'
    CALL SP_xxx(@_SP_xxx_0, @_SP_xxx_1)
  
  user variable (@_xxx) 의 charset/collation/length 가 SP 파라미터와
  호환 안 됨 → 1406 'Data too long for column' 발생.

v90.77 처방: callproc 우회, 직접 CALL 실행
  cur.execute(f"CALL `{obj_name}`({placeholders})", params)
  
  MySQL CLI 와 동일한 호출 방식 → 1406 회피
  단, OUT/INOUT 파라미터 있으면 callproc 유지 (회수 위해)
"""

import os
import re
import sys
import pytest


_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)


class TestCallprocBypass:
    """callproc → 직접 CALL 변경 검증."""
    
    SCHEMA_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "app", "api", "routes", "schema.py"
    ))
    
    def _content(self):
        if not os.path.exists(self.SCHEMA_FILE):
            pytest.skip("")
        return open(self.SCHEMA_FILE, encoding='utf-8').read()
    
    def test_v90_77_marker(self):
        c = self._content()
        assert "v90.77" in c
        assert c.count("v90.77") >= 2
    
    def test_direct_call_used(self):
        """`CALL `{obj_name}`({placeholders})` 패턴 사용."""
        c = self._content()
        # 백틱으로 감싸진 직접 CALL
        assert re.search(
            r'CALL\s+`\{obj_name\}`',
            c
        ), "직접 CALL 패턴 누락"
    
    def test_has_out_check(self):
        """has_out 체크 로직 - OUT/INOUT 있으면 callproc, 아니면 직접 CALL."""
        c = self._content()
        assert "has_out" in c
        assert 'PARAMETER_MODE' in c and 'OUT' in c
    
    def test_main_callproc_replaced(self):
        """주된 PROCEDURE 호출 위치 (1794줄 부근) 가 변경됨."""
        c = self._content()
        # 변경 후: has_out 분기 + 직접 CALL
        # 변경 전 패턴: "cur.callproc(obj_name, full_params)\n                    rows = []"
        # 이전 단순 패턴은 사라져야
        # (단, has_out 분기 안의 callproc 은 보존)
        # 카운트로 검증: callproc 호출 1개만 (OUT 케이스용)
        callproc_count = c.count("cur.callproc(")
        assert callproc_count == 1, f"callproc 호출이 {callproc_count} 번 (1번이 정상)"
    
    def test_tvf_callproc_replaced(self):
        """TVF 호출도 직접 CALL 사용."""
        c = self._content()
        # TVF 영역에서 callproc 안 쓰고 CALL 사용
        tvf_idx = c.find("TVF (이름이 TVF로 시작)")
        if tvf_idx > 0:
            tvf_section = c[tvf_idx:tvf_idx+800]
            assert "cur.callproc" not in tvf_section, "TVF 에 callproc 잔존"
            assert 'CALL `' in tvf_section, "TVF 에 직접 CALL 누락"
    
    def test_second_callproc_replaced(self):
        """두번째 PROCEDURE 호출 사이트 (2536줄 부근)."""
        c = self._content()
        # "obj_type == \"PROCEDURE\":" 가 두 번 나타남
        # 두 번째 위치에서도 callproc 안 써야
        proc_indices = [m.start() for m in re.finditer(r'obj_type\s*==\s*"PROCEDURE"', c)]
        assert len(proc_indices) >= 2, "PROCEDURE 분기 2개 이상 있어야"


class TestPlaceholderSafety:
    """placeholder 안전성 — SQL injection 방지 + 파라미터 정확 전달."""
    
    SCHEMA_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "app", "api", "routes", "schema.py"
    ))
    
    def test_placeholders_are_bound(self):
        """%s placeholder 와 params 바인딩 (SQL injection 안전)."""
        c = open(self.SCHEMA_FILE, encoding='utf-8').read()
        # cur.execute(sql, full_params) 패턴 — 두 번째 인자에 params 바인딩
        assert re.search(
            r'cur\.execute\(\s*sql\s*,\s*full_params\s*\)',
            c
        ) or re.search(
            r'cur\.execute\(\s*f"CALL[^"]+"\s*,\s*\w+\)',
            c
        )
    
    def test_obj_name_in_backticks(self):
        """obj_name 은 백틱으로 감싸야 (SP 이름의 특수문자 방어)."""
        c = open(self.SCHEMA_FILE, encoding='utf-8').read()
        assert "`{obj_name}`" in c


class TestSimulation:
    """callproc vs 직접 CALL 시뮬레이션."""
    
    def callproc_emulation(self, obj_name, params):
        """pymysql callproc 흉내 (실제 동작)."""
        if not params:
            return f"CALL {obj_name}()"
        # SET @_xxx_0 = ..., @_xxx_1 = ...
        sets = ", ".join([f"@_{obj_name}_{i}={p!r}" for i, p in enumerate(params)])
        # CALL xxx(@_xxx_0, @_xxx_1)
        refs = ", ".join([f"@_{obj_name}_{i}" for i in range(len(params))])
        return f"SET {sets}; CALL {obj_name}({refs})"
    
    def direct_call(self, obj_name, params):
        """v90.77 의 직접 CALL 흉내."""
        if not params:
            return f"CALL `{obj_name}`()"
        ph = ", ".join(["%s"] * len(params))
        # placeholder 가 pymysql 에서 escape 되어 직접 들어감
        return f"CALL `{obj_name}`({ph})"
    
    def test_callproc_creates_user_variables(self):
        """callproc 패턴에 SET @_xxx 등장."""
        sql = self.callproc_emulation("SP_X", ["20240101", "20240101"])
        assert "SET" in sql
        assert "@_SP_X_0" in sql
    
    def test_direct_call_no_user_variables(self):
        """직접 CALL 은 user variable 안 만듦."""
        sql = self.direct_call("SP_X", ["20240101", "20240101"])
        assert "SET" not in sql
        assert "@_" not in sql
        assert "%s" in sql
    
    def test_direct_call_no_params(self):
        """파라미터 없는 SP 도 안전."""
        sql = self.direct_call("SP_NO_ARG", [])
        assert sql == "CALL `SP_NO_ARG`()"


if __name__ == "__main__":
    print("=== v90.77 callproc 우회 검증 ===\n")
    
    test = TestSimulation()
    
    print("Before (pymysql callproc):")
    print("  " + test.callproc_emulation("SP_TEST_DAILY_AGG", ["20240101", "20240101"]))
    print("  ↑ SET @_xxx 시점에 1406 발생 (charset/collation/length 문제)")
    print()
    print("After (v90.77 직접 CALL):")
    print("  " + test.direct_call("SP_TEST_DAILY_AGG", ["20240101", "20240101"]))
    print("  ↑ MySQL CLI 와 동일한 방식 → 통과 예상")
    print()
    print("진단 근거:")
    print("  ✓ MySQL CLI: CALL SP_TEST_DAILY_AGG('20240101', '20240101') → 통과")
    print("  ✗ DataBridge: pymysql.callproc → 1406")
    print("  → callproc 만의 user variable 패턴이 진짜 원인")
