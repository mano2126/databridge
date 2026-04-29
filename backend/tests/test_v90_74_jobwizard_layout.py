"""
test_v90_74_jobwizard_layout.py — v90.74 (2026-04-28)

본부장님 호소: 
  "이관job생성에 테이블 보는게 너무 불편해, 안돼면 트리거와 뷰를 위아래 배치하고 
   테이블폭을 좀더 넓히더라도 좀더 보기 좋게 구성하자."

v90.74 처방:
  1. CSS Grid 재구성: 5컬럼 → 4컬럼 (트리거/뷰 같은 컬럼에 위아래 2행)
  2. 테이블 폭 확대: 1.5fr → 2.4fr (60% 증가)
  3. 테이블 행 폰트 11px → 11.5px (가독성)
  4. 행 수 컬럼 80px 고정폭 + 색상 강조
  5. 빈 테이블 (row_count=0) 시각적 dim (opacity 0.55)
  6. 큰 테이블 (M/K) 색상 구분 (is-million/is-thousand)
  7. 테이블 행에 title 속성 (hover 시 풀 이름)
"""

import os
import re
import pytest


_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)


class TestGridLayout:
    """CSS Grid 재구성 검증."""
    
    JW_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "JobWizard.vue"
    ))
    
    def _content(self):
        if not os.path.exists(self.JW_FILE):
            pytest.skip("")
        return open(self.JW_FILE, encoding='utf-8').read()
    
    def test_v90_74_marker(self):
        c = self._content()
        assert "v90.74" in c
    
    def test_4_columns_not_5(self):
        """grid-template-columns 가 4컬럼 (이전 5컬럼)."""
        c = self._content()
        # 이전 5컬럼 (1.5fr 1fr 1fr 1fr 1fr) 패턴 사라져야
        assert "grid-template-columns: 1.5fr 1fr 1fr 1fr 1fr" not in c
        # 새 4컬럼 (2.4fr 1fr 1fr 1fr) 패턴
        assert "grid-template-columns: 2.4fr 1fr 1fr 1fr" in c
    
    def test_grid_areas_defined(self):
        """grid-template-areas 정의 - 트리거/뷰 같은 컬럼."""
        c = self._content()
        # tbl proc func trig (1행) / tbl proc func view (2행)
        assert "grid-template-areas:" in c
        assert '"tbl proc func trig"' in c
        assert '"tbl proc func view"' in c
    
    def test_table_box_spans_two_rows(self):
        """테이블 박스 2행 높이 → min-height 580px (이전 280px)."""
        c = self._content()
        m = re.search(r"\.obj-box-tables\s*\{[^}]*?min-height:\s*(\d+)px", c, re.DOTALL)
        assert m, "obj-box-tables min-height 정의 누락"
        assert int(m.group(1)) >= 500, f"테이블 박스 높이 너무 작음: {m.group(1)}px"
    
    def test_grid_area_assignments(self):
        """각 박스에 grid-area 지정."""
        c = self._content()
        for area in ['tbl', 'proc', 'func', 'trig', 'view']:
            assert f"grid-area: {area}" in c
    
    def test_responsive_breakpoint(self):
        """1280px 미만 — 3컬럼으로 축소 (트리거/뷰 같은 컬럼)."""
        c = self._content()
        # @media (max-width: 1280px) 에서 grid-template-columns: 1.8fr 1fr 1fr
        assert "1.8fr 1fr 1fr" in c
    
    def test_mobile_layout(self):
        """768px 미만 — 2컬럼."""
        c = self._content()
        # 모바일 grid-template-areas 도 정의
        assert '"tbl  tbl"' in c or '"tbl tbl"' in c


class TestTableRowReadability:
    """테이블 행 가독성 개선 검증."""
    
    JW_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "JobWizard.vue"
    ))
    
    def _content(self):
        if not os.path.exists(self.JW_FILE):
            pytest.skip("")
        return open(self.JW_FILE, encoding='utf-8').read()
    
    def test_obj_row_empty_class(self):
        """빈 테이블 dim 클래스."""
        c = self._content()
        assert "obj-row-empty" in c
        # CSS opacity 0.55 정의
        m = re.search(r"\.obj-row-table\.obj-row-empty\s*\{[^}]*?opacity:\s*([\d.]+)", c, re.DOTALL)
        assert m, "obj-row-empty opacity 정의 누락"
        assert float(m.group(1)) < 1.0, "빈 테이블 dim 효과 없음"
    
    def test_million_thousand_classes(self):
        """행 수 강조 클래스."""
        c = self._content()
        assert "is-million" in c
        assert "is-thousand" in c
        # 색상 정의
        assert re.search(r"\.is-million\s*\{[^}]*color:", c)
    
    def test_rowCountClass_function(self):
        """_rowCountClass 함수 정의."""
        c = self._content()
        assert "_rowCountClass" in c
        # 1e6 / 1e3 분기 로직
        m = re.search(r"_rowCountClass\s*=\s*n\s*=>", c)
        assert m, "_rowCountClass 함수 정의 누락"
    
    def test_table_font_increased(self):
        """테이블 행 폰트 11.5px (이전 11px)."""
        c = self._content()
        # obj-row-table 의 폰트 크기 정의
        assert "11.5px" in c
    
    def test_row_count_width_fixed(self):
        """행 수 컬럼 80px 고정폭."""
        c = self._content()
        m = re.search(r"\.obj-row-table\s+\.obj-meta-rows\s*\{[^}]*?width:\s*(\d+)px", c, re.DOTALL)
        assert m, "obj-meta-rows width 정의 누락"
        assert int(m.group(1)) >= 70


class TestTitleAttribute:
    """테이블 행에 title 속성 (hover 시 풀 이름)."""
    
    JW_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "JobWizard.vue"
    ))
    
    def test_table_row_has_title(self):
        if not os.path.exists(self.JW_FILE):
            pytest.skip("")
        c = open(self.JW_FILE, encoding='utf-8').read()
        # 테이블 label 의 :title 바인딩
        # `${t.schema_name}.${t.table_name}` 같은 패턴
        assert "schema_name}.${t.table_name}" in c
    
    def test_dynamic_class_for_empty(self):
        """빈 테이블 클래스 동적 부여."""
        if not os.path.exists(self.JW_FILE):
            pytest.skip("")
        c = open(self.JW_FILE, encoding='utf-8').read()
        # :class="{'obj-row-empty': (t.row_count||0) === 0}"
        assert "obj-row-empty" in c
        assert "row_count||0) === 0" in c or "row_count || 0) === 0" in c


class TestBackwardCompatibility:
    """회귀 안전 검증."""
    
    JW_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "JobWizard.vue"
    ))
    
    def _content(self):
        if not os.path.exists(self.JW_FILE):
            pytest.skip("")
        return open(self.JW_FILE, encoding='utf-8').read()
    
    def test_all_5_boxes_still_exist(self):
        """5개 박스 모두 존재."""
        c = self._content()
        for box in ['obj-box-tables', 'obj-box-proc', 'obj-box-func', 'obj-box-trig', 'obj-box-view']:
            assert box in c, f"{box} 박스 누락"
    
    def test_existing_check_logic_intact(self):
        """체크박스 + form binding 그대로."""
        c = self._content()
        assert 'v-model="form.tables"' in c
        assert 'v-model="form.procedures"' in c
        assert 'v-model="form.triggers"' in c
        assert 'v-model="form.views"' in c
    
    def test_fmtRows_function_intact(self):
        """fmtRows 함수 기존 로직 보존."""
        c = self._content()
        assert "fmtRows= n =>" in c or "fmtRows = n =>" in c
        # 1e6 / 1e3 분기
        assert "1e6" in c
        assert "1e3" in c


if __name__ == "__main__":
    print("=== v90.74 JobWizard 화면 구조 변경 ===\n")
    print("변경 전 (5컬럼 가로):")
    print("  [테이블 1.5fr] [PROC] [FN] [트리거] [뷰]")
    print("                                      ↑ 모두 같은 폭")
    print()
    print("변경 후 (4컬럼 + 트리거/뷰 같은 컬럼):")
    print("  [테이블 2.4fr] [PROC] [FN] [트리거]")
    print("                              [뷰   ]   ← 위아래")
    print()
    print("기대 효과:")
    print("  ✓ 테이블 폭 60% 증가 (1.5 → 2.4)")
    print("  ✓ 테이블 이름 잘림 해결 (B02_LoanProd… 풀 표시)")
    print("  ✓ 빈 테이블 시각적 구분 (opacity 0.55)")
    print("  ✓ 큰 테이블 색상 강조 (M=청록, K=틸)")
    print("  ✓ hover 시 title 으로 풀 정보")
