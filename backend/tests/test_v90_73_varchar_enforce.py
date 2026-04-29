"""
test_v90_73_varchar_enforce.py — v90.73 (2026-04-28)

본부장님 SP_STATRECORD/SP_STATSYSTEM 의 1406 오류:
  - v90.71 의 prompt 강화 (system.txt 패턴 0 + obj_executor 의 1406 hint) 적용 후에도
    AI 가 VARCHAR 길이 줄여서 1406 재발.
  - prompt 만으론 한계 → 코드 레벨에서 무조건 보정 필요.

v90.73 처방: _enforce_varchar_length() 함수
  1. 원본 DDL 의 @param VARCHAR(N) 추출
  2. 변환 결과의 IN p_param VARCHAR(M) 비교
  3. M < N 이면 M = N 으로 자동 보정
  4. AI 가 DATE 로 바꿨으면 VARCHAR(N) 으로 복원
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
# _enforce_varchar_length 미러 (테스트 격리)
# ════════════════════════════════════════════════════════════════════════════

def _enforce_varchar_length(src_ddl, tgt_ddl, obj_name=""):
    """obj_executor.py 의 _enforce_varchar_length 미러."""
    changes = []
    if not src_ddl or not tgt_ddl:
        return tgt_ddl, changes
    
    src_lengths = {}
    for m in re.finditer(r"@(\w+)\s+(?:N?VARCHAR|N?CHAR)\s*\(\s*(\d+)\s*\)", src_ddl, re.IGNORECASE):
        param_name = m.group(1).lower()
        length = int(m.group(2))
        src_lengths[param_name] = length
        src_lengths[f"p_{param_name}"] = length
    
    if not src_lengths:
        return tgt_ddl, changes
    
    corrected = tgt_ddl
    
    def _fix_varchar(match):
        prefix = match.group(1) or ""
        name = match.group(2)
        var_type = match.group(3)
        m_length = int(match.group(4))
        n_length = None
        name_lower = name.lower()
        if name_lower in src_lengths:
            n_length = src_lengths[name_lower]
        else:
            stripped = re.sub(r"^p_", "", name_lower)
            if stripped in src_lengths:
                n_length = src_lengths[stripped]
        if n_length is None or m_length >= n_length:
            return match.group(0)
        new_segment = f"{prefix}{name} {var_type}({n_length})"
        changes.append(f"★ VARCHAR 길이 강제 보정 [{name}]: VARCHAR({m_length}) → VARCHAR({n_length})")
        return new_segment
    
    corrected = re.sub(
        r"((?:\bIN\s+|\bOUT\s+|\bINOUT\s+)?)(\w+)\s+(VARCHAR|CHAR)\s*\(\s*(\d+)\s*\)",
        _fix_varchar, corrected, flags=re.IGNORECASE
    )
    
    def _fix_date(match):
        prefix = match.group(1) or ""
        name = match.group(2)
        date_type = match.group(3)
        n_length = None
        name_lower = name.lower()
        if name_lower in src_lengths:
            n_length = src_lengths[name_lower]
        else:
            stripped = re.sub(r"^p_", "", name_lower)
            if stripped in src_lengths:
                n_length = src_lengths[stripped]
        if n_length is None:
            return match.group(0)
        new_segment = f"{prefix}{name} VARCHAR({n_length})"
        changes.append(f"★ DATE 강제 복원 [{name}]: {date_type} → VARCHAR({n_length})")
        return new_segment
    
    corrected = re.sub(
        r"((?:\bIN\s+|\bOUT\s+|\bINOUT\s+)?)(\w+)\s+(DATE|DATETIME)\b(?!\s*\()",
        _fix_date, corrected, flags=re.IGNORECASE
    )
    return corrected, changes


# ════════════════════════════════════════════════════════════════════════════
# 코어 시나리오 — 본부장님 케이스
# ════════════════════════════════════════════════════════════════════════════

class TestVarcharShorten:
    """AI 가 VARCHAR 길이 줄임 → 코드가 자동 보정."""
    
    def test_simple_shorten(self):
        """VARCHAR(8) → VARCHAR(7) 자동 보정."""
        src = "CREATE PROCEDURE SP_X @rec_sdate VARCHAR(8) AS BEGIN ... END"
        tgt = "CREATE PROCEDURE SP_X(IN p_rec_sdate VARCHAR(7)) BEGIN ... END"
        corrected, changes = _enforce_varchar_length(src, tgt)
        assert "VARCHAR(8)" in corrected
        assert "VARCHAR(7)" not in corrected
        assert len(changes) == 1
        assert "VARCHAR(7) → VARCHAR(8)" in changes[0]
    
    def test_multiple_params_shorten(self):
        """여러 파라미터 동시 보정."""
        src = """CREATE PROCEDURE SP_TWO
            @rec_sdate VARCHAR(8),
            @rec_edate VARCHAR(8)
        AS BEGIN ... END"""
        tgt = """CREATE PROCEDURE SP_TWO(
            IN p_rec_sdate VARCHAR(5),
            IN p_rec_edate VARCHAR(6)
        ) BEGIN ... END"""
        corrected, changes = _enforce_varchar_length(src, tgt)
        assert corrected.count("VARCHAR(8)") == 2
        assert "VARCHAR(5)" not in corrected
        assert "VARCHAR(6)" not in corrected
        assert len(changes) == 2
    
    def test_extreme_shorten(self):
        """VARCHAR(100) → VARCHAR(10) 큰 차이도 보정."""
        src = "CREATE PROCEDURE SP_X @desc VARCHAR(100) AS BEGIN ... END"
        tgt = "CREATE PROCEDURE SP_X(IN p_desc VARCHAR(10)) BEGIN ... END"
        corrected, changes = _enforce_varchar_length(src, tgt)
        assert "VARCHAR(100)" in corrected
        assert "VARCHAR(10)" not in corrected


class TestDateRestore:
    """AI 가 VARCHAR → DATE 바꿨을 때 자동 복원."""
    
    def test_varchar_to_date_restored(self):
        """VARCHAR(10) → DATE 변경된 경우 VARCHAR(10) 복원."""
        src = "CREATE PROCEDURE SP_X @order_date VARCHAR(10) AS BEGIN ... END"
        tgt = "CREATE PROCEDURE SP_X(IN p_order_date DATE) BEGIN ... END"
        corrected, changes = _enforce_varchar_length(src, tgt)
        assert "VARCHAR(10)" in corrected
        assert " DATE)" not in corrected and " DATE\n" not in corrected
        assert any("DATE 강제 복원" in c for c in changes)
    
    def test_varchar_to_datetime_restored(self):
        """VARCHAR → DATETIME 도 복원."""
        src = "CREATE PROCEDURE SP_X @ts VARCHAR(20) AS BEGIN ... END"
        tgt = "CREATE PROCEDURE SP_X(IN p_ts DATETIME) BEGIN ... END"
        corrected, changes = _enforce_varchar_length(src, tgt)
        assert "VARCHAR(20)" in corrected


class TestRegressionSafety:
    """정상 변환은 영향 없어야."""
    
    def test_same_length_unchanged(self):
        """같은 길이면 변경 없음."""
        src = "CREATE PROCEDURE SP_X @code VARCHAR(20) AS BEGIN ... END"
        tgt = "CREATE PROCEDURE SP_X(IN p_code VARCHAR(20)) BEGIN ... END"
        corrected, changes = _enforce_varchar_length(src, tgt)
        assert tgt == corrected
        assert len(changes) == 0
    
    def test_longer_unchanged(self):
        """더 긴 길이는 영향 없음 (안전 룰)."""
        src = "CREATE PROCEDURE SP_X @desc VARCHAR(100) AS BEGIN ... END"
        tgt = "CREATE PROCEDURE SP_X(IN p_desc VARCHAR(200)) BEGIN ... END"
        corrected, changes = _enforce_varchar_length(src, tgt)
        assert "VARCHAR(200)" in corrected
        assert len(changes) == 0
    
    def test_no_varchar_in_source_no_changes(self):
        """원본에 VARCHAR 파라미터 없으면 영향 없음."""
        src = "CREATE PROCEDURE SP_X @x INT, @y INT AS BEGIN ... END"
        tgt = "CREATE PROCEDURE SP_X(IN p_x INT, IN p_y INT) BEGIN ... END"
        corrected, changes = _enforce_varchar_length(src, tgt)
        assert tgt == corrected
        assert len(changes) == 0
    
    def test_int_param_not_affected(self):
        """INT/BIGINT 파라미터는 영향 없음."""
        src = "CREATE PROCEDURE SP_X @id INT, @code VARCHAR(20) AS BEGIN ... END"
        tgt = "CREATE PROCEDURE SP_X(IN p_id INT, IN p_code VARCHAR(20)) BEGIN ... END"
        corrected, changes = _enforce_varchar_length(src, tgt)
        # INT 는 그대로, VARCHAR 도 같은 길이 → 영향 없음
        assert "p_id INT" in corrected
        assert "VARCHAR(20)" in corrected
        assert len(changes) == 0
    
    def test_date_in_source_stays_date(self):
        """원본이 DATE 면 → 타겟도 DATE 유지 (DATE 강제 복원 안 함)."""
        src = "CREATE PROCEDURE SP_X @d DATE AS BEGIN ... END"
        tgt = "CREATE PROCEDURE SP_X(IN p_d DATE) BEGIN ... END"
        corrected, changes = _enforce_varchar_length(src, tgt)
        assert "p_d DATE" in corrected
        assert len(changes) == 0


class TestEdgeCases:
    """엣지 케이스."""
    
    def test_empty_inputs(self):
        result, changes = _enforce_varchar_length("", "")
        assert result == ""
        assert changes == []
    
    def test_no_match_in_target_unchanged(self):
        """파라미터 이름이 다르면 영향 없음."""
        src = "CREATE PROCEDURE SP_X @rec_sdate VARCHAR(8) AS BEGIN ... END"
        tgt = "CREATE PROCEDURE SP_X(IN totally_different VARCHAR(5)) BEGIN ... END"
        corrected, changes = _enforce_varchar_length(src, tgt)
        # totally_different 이 src 에 없으니 영향 없음
        assert "VARCHAR(5)" in corrected
        assert len(changes) == 0
    
    def test_nvarchar_normalized(self):
        """NVARCHAR 도 인식 (MySQL 은 VARCHAR 로 변환)."""
        src = "CREATE PROCEDURE SP_X @name NVARCHAR(50) AS BEGIN ... END"
        tgt = "CREATE PROCEDURE SP_X(IN p_name VARCHAR(20)) BEGIN ... END"
        corrected, changes = _enforce_varchar_length(src, tgt)
        assert "VARCHAR(50)" in corrected


class TestSourceCodePatched:
    """obj_executor.py 가 v90.73 패치 적용됐는지."""
    
    OE_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "app", "core", "obj_executor.py"
    ))
    
    def test_v90_73_marker(self):
        if not os.path.exists(self.OE_FILE):
            pytest.skip("")
        content = open(self.OE_FILE, encoding='utf-8').read()
        assert "v90.73" in content
    
    def test_function_defined(self):
        """_enforce_varchar_length 함수 정의."""
        if not os.path.exists(self.OE_FILE):
            pytest.skip("")
        content = open(self.OE_FILE, encoding='utf-8').read()
        assert "def _enforce_varchar_length" in content
    
    def test_called_from_ai_convert(self):
        """ai_convert_ddl 의 return 직전에 호출."""
        if not os.path.exists(self.OE_FILE):
            pytest.skip("")
        content = open(self.OE_FILE, encoding='utf-8').read()
        ai_idx = content.find("def ai_convert_ddl")
        ai_end = content.find("def ", ai_idx + 100)
        ai_section = content[ai_idx:ai_end] if ai_end > 0 else content[ai_idx:]
        assert "_enforce_varchar_length(" in ai_section


if __name__ == "__main__":
    print("=== v90.73 본부장님 SP_STATRECORD 시나리오 ===\n")
    
    cases = [
        ("AI 가 VARCHAR(8) → VARCHAR(7) 줄임 (본부장님 케이스)",
         "CREATE PROCEDURE SP @rec_sdate VARCHAR(8), @rec_edate VARCHAR(8) AS BEGIN ... END",
         "CREATE PROCEDURE SP(IN p_rec_sdate VARCHAR(7), IN p_rec_edate VARCHAR(7)) BEGIN ... END"),
        
        ("AI 가 VARCHAR → DATE 바꿈",
         "CREATE PROCEDURE SP @order_date VARCHAR(10) AS BEGIN ... END",
         "CREATE PROCEDURE SP(IN p_order_date DATE) BEGIN ... END"),
        
        ("정상 변환 (회귀 안전)",
         "CREATE PROCEDURE SP @code VARCHAR(20) AS BEGIN ... END",
         "CREATE PROCEDURE SP(IN p_code VARCHAR(20)) BEGIN ... END"),
        
        ("AI 가 더 늘림 (회귀 안전)",
         "CREATE PROCEDURE SP @desc VARCHAR(100) AS BEGIN ... END",
         "CREATE PROCEDURE SP(IN p_desc VARCHAR(200)) BEGIN ... END"),
    ]
    
    for name, src, tgt in cases:
        result, changes = _enforce_varchar_length(src, tgt)
        emoji = "🔧" if changes else "✓"
        print(f"  {emoji} {name}")
        for c in changes:
            print(f"      {c}")
        if not changes:
            print(f"      → 변경 없음 (안전)")
        print()
