"""
test_v90_70_name_variant_routing.py — v90.70 (2026-04-28)

본부장님 호소:
  sp_Softphone_UpdateRecord(dbo_sp_Softphone_UpdateRecord)
   ✓ 이관됨 ✓ 소스 성공 ✗ 타겟 실패 (1305 'does not exist')

진단:
  CHECK_EXISTS 가 타겟에서 실제 존재하는 이름은 r.name_variant 에 저장
  (예: 소스 'sp_Softphone_UpdateRecord' → 타겟 'dbo_sp_Softphone_UpdateRecord')
  
  그러나 _execObjOnDB / runObjTestWithParams 가 PROCEDURE 호출 시
  r.name (소스 원본) 만 사용 → 타겟 DB 에 없는 이름으로 호출 → 1305 오류

처방:
  side === 'tgt' && r.name_variant 면 → r.name_variant 우선
  side === 'src' 면 → r.name 그대로
"""

import os
import re
import pytest

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)


class TestNameVariantRouting:
    """Validate.vue 의 v90.70 fix 검증."""
    
    VAL_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "Validate.vue"
    ))
    
    def _content(self):
        if not os.path.exists(self.VAL_FILE):
            pytest.skip("")
        return open(self.VAL_FILE, encoding='utf-8').read()
    
    def test_v90_70_marker(self):
        c = self._content()
        assert "v90.70" in c
        # 최소 5 곳에 마커 (CHECK_EXISTS, VIEW, PROCEDURE, runObjTestWithParams)
        assert c.count("v90.70") >= 4
    
    def test_ckName_definition(self):
        """_ckName 변수 정의 — side='tgt' && name_variant 조건."""
        c = self._content()
        # _ckName 정의 패턴
        m = re.search(
            r"const\s+_ckName\s*=\s*\(\s*side\s*===\s*['\"]tgt['\"]\s*&&\s*r\s*&&\s*r\.name_variant\s*\)\s*\?\s*r\.name_variant\s*:\s*name",
            c
        )
        assert m, "_ckName 정의 누락 또는 패턴 불일치"
    
    def test_check_exists_uses_ckName(self):
        """TRIGGER CHECK_EXISTS 가 _ckName 사용."""
        c = self._content()
        # CHECK_EXISTS 호출 위치에서 obj_name 이 _ckName 인지
        # 패턴: obj_type: 'CHECK_EXISTS', obj_name: _ckName
        assert re.search(
            r"obj_type:\s*['\"]CHECK_EXISTS['\"].*?obj_name:\s*_ckName",
            c, re.DOTALL
        ), "CHECK_EXISTS 가 _ckName 사용 안 함"
    
    def test_view_uses_ckName(self):
        """VIEW 가 _ckName 사용."""
        c = self._content()
        assert re.search(
            r"obj_type:\s*['\"]VIEW['\"].*?obj_name:\s*_ckName",
            c, re.DOTALL
        ), "VIEW 가 _ckName 사용 안 함"
    
    def test_procedure_uses_ckName(self):
        """PROCEDURE/FUNCTION 호출 (variable t) 이 _ckName 사용."""
        c = self._content()
        # PROCEDURE / FUNCTION 호출은 obj_type: t 이고 _ckName 사용
        # 60000ms timeout 이 PROCEDURE 호출 식별자
        proc_section = c[c.find("v60: 12 → 60초"):c.find("v60: 12 → 60초")+1500]
        assert "obj_name: _ckName" in proc_section, \
            "PROCEDURE 호출이 _ckName 사용 안 함"
    
    def test_getParams_target_uses_variant(self):
        """_getParams 호출이 타겟이면 name_variant 사용."""
        c = self._content()
        # _getParams 호출 부분에 _paramName 변수 또는 name_variant 처리
        gp_section = c[c.find("else {", c.find("_getParams")):c.find("_getParams") + 500]
        assert "name_variant" in gp_section or "_paramName" in c, \
            "_getParams 호출이 타겟 시 name_variant 사용 안 함"
    
    def test_runObjTestWithParams_target_uses_variant(self):
        """runObjTestWithParams 의 타겟 호출이 r.name_variant 사용."""
        c = self._content()
        # _tgtName 변수 또는 r.name_variant || r.name
        assert "r.name_variant || r.name" in c or "_tgtName" in c, \
            "runObjTestWithParams 의 타겟 호출이 name_variant 사용 안 함"
    
    def test_source_side_uses_original_name(self):
        """소스 측은 항상 r.name (원본) 사용 — 회귀 검증."""
        c = self._content()
        # _ckName 정의 자체에 'src' 면 name 그대로 사용 보장
        # (side === 'tgt' && r.name_variant) ? variant : name
        # 즉 src 거나 name_variant 없으면 name 그대로
        assert ":\s*name" in str(re.search(r"_ckName\s*=\s*[^;]+;", c).group()) or \
               re.search(r"_ckName\s*=.*?\?\s*r\.name_variant\s*:\s*name", c), \
            "_ckName 의 src 측 fallback 누락"


class TestSimulation:
    """타겟 호출 시 name 결정 로직 시뮬레이션."""
    
    def resolve_obj_name(self, side, name, name_variant):
        """v90.70 의 _ckName 결정 로직 미러."""
        if side == 'tgt' and name_variant:
            return name_variant
        return name
    
    def test_target_with_variant_uses_variant(self):
        """본부장님 sp_Softphone 케이스."""
        result = self.resolve_obj_name(
            side='tgt',
            name='sp_Softphone_UpdateRecord',
            name_variant='dbo_sp_Softphone_UpdateRecord'
        )
        assert result == 'dbo_sp_Softphone_UpdateRecord', \
            f"타겟 측은 name_variant 써야 함: {result}"
    
    def test_target_no_variant_falls_back_to_name(self):
        """name_variant 없으면 name 사용 (회귀 안전)."""
        result = self.resolve_obj_name(
            side='tgt',
            name='SP_NORMAL',
            name_variant=None
        )
        assert result == 'SP_NORMAL'
    
    def test_source_always_uses_name(self):
        """소스 측은 항상 원본 name 사용."""
        result = self.resolve_obj_name(
            side='src',
            name='sp_Softphone_UpdateRecord',
            name_variant='dbo_sp_Softphone_UpdateRecord'
        )
        assert result == 'sp_Softphone_UpdateRecord', \
            "소스 측은 원본 name 사용해야 함"
    
    def test_target_empty_variant_uses_name(self):
        """name_variant 빈 문자열도 name 사용."""
        result = self.resolve_obj_name(
            side='tgt',
            name='SP_TEST',
            name_variant=''
        )
        assert result == 'SP_TEST'


if __name__ == "__main__":
    print("=== v90.70 본부장님 sp_Softphone 시나리오 ===\n")
    
    test = TestSimulation()
    
    cases = [
        ("타겟 + name_variant 있음 (sp_Softphone)",
         'tgt', 'sp_Softphone_UpdateRecord', 'dbo_sp_Softphone_UpdateRecord'),
        ("타겟 + name_variant 없음 (SP_INSERTERRORLOG)",
         'tgt', 'SP_INSERTERRORLOG', None),
        ("소스 + name_variant 있음 (소스 원본 그대로)",
         'src', 'sp_Softphone_UpdateRecord', 'dbo_sp_Softphone_UpdateRecord'),
        ("소스 + name_variant 없음 (정상 케이스)",
         'src', 'SP_NORMAL', None),
    ]
    
    for name, side, n, nv in cases:
        result = test.resolve_obj_name(side, n, nv)
        emoji = '✓' if (
            (side == 'tgt' and nv and result == nv) or
            (side == 'tgt' and not nv and result == n) or
            (side == 'src' and result == n)
        ) else '✗'
        print(f"  {emoji} {name}")
        print(f"      입력: side={side}, name={n!r}, variant={nv!r}")
        print(f"      결정: obj_name={result!r}")
