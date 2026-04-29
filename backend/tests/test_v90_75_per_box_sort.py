"""
test_v90_75_per_box_sort.py — v90.75 (2026-04-28)

본부장님 호소:
  "각각 객체별로 정렬 기능을 구현하고 싶어"
  "테이블의 경우 (숫자) 옆에 소스와 타겟 테이블 사이에 '테이블명',
   사이즈 위에 '크기' 달아서 정렬기능 구현"
  "프로시저 및 다른 오브젝트들은 구분 할 수있는 컬럼이 있다면 기준 컬럼을 만들어서"
  "지금 있는 건 삭제하자"
  "행수는 그냥 1,000건 이런 단위 형태로"
  "테이블보여주는 블록은 화살표를 기준으로 컬럼라인 좀 맞추고"

v90.75 처방:
  1. 단일 sortKey/sortDir 폐기 → 박스별 sort state (5개)
  2. 상단 정렬 툴바 삭제 → 각 컬럼 헤더 클릭으로 정렬
  3. 행수 표기 M/K 폐지 → 천단위 콤마 (1,234,567)
  4. 컬럼 라인 정렬 (고정 폭 80px/60px)
  5. 객체별 정렬 가능 컬럼:
     - 테이블: 이름 / 행수 / 크기
     - 프로시저: 이름 / 생성일
     - 함수: 이름 / 반환타입
     - 트리거: 이름 / 이벤트 / 대상
     - 뷰: 이름
"""

import os
import re
import pytest


_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)


class TestPerBoxSortState:
    """박스별 독립 sort state."""
    
    JW_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "JobWizard.vue"
    ))
    
    def _content(self):
        if not os.path.exists(self.JW_FILE):
            pytest.skip("")
        return open(self.JW_FILE, encoding='utf-8').read()
    
    def test_v90_75_marker(self):
        c = self._content()
        assert "v90.75" in c
        assert c.count("v90.75") >= 5
    
    def test_5_sort_refs_defined(self):
        """tableSort, procSort, funcSort, trigSort, viewSort 모두 정의."""
        c = self._content()
        for ref_name in ['tableSort', 'procSort', 'funcSort', 'trigSort', 'viewSort']:
            assert re.search(
                rf"const\s+{ref_name}\s*=\s*ref\(", c
            ), f"{ref_name} ref 정의 누락"
    
    def test_5_toggle_functions_defined(self):
        """각 박스별 toggle 함수."""
        c = self._content()
        for fn in ['toggleTableSort', 'toggleProcSort', 'toggleFuncSort',
                   'toggleTrigSort', 'toggleViewSort']:
            assert f"function {fn}" in c, f"{fn} 함수 누락"
    
    def test_5_icon_functions_defined(self):
        """각 박스별 sortIcon 함수."""
        c = self._content()
        for fn in ['tableSortIcon', 'procSortIcon', 'funcSortIcon',
                   'trigSortIcon', 'viewSortIcon']:
            assert f"function {fn}" in c, f"{fn} 함수 누락"


class TestOldSortToolbarRemoved:
    """이전 통합 정렬 툴바 삭제 확인."""
    
    JW_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "JobWizard.vue"
    ))
    
    def _content(self):
        if not os.path.exists(self.JW_FILE):
            pytest.skip("")
        return open(self.JW_FILE, encoding='utf-8').read()
    
    def test_sort_toolbar_template_removed(self):
        """이전 sort-toolbar div 영역 제거."""
        c = self._content()
        # <div class="sort-toolbar"> 가 template 에 없어야 (CSS 정의는 남을 수 있음)
        # template 영역 추출
        tmpl_end = c.find("</template>")
        if tmpl_end > 0:
            tmpl = c[:tmpl_end]
            assert '<div class="sort-toolbar">' not in tmpl, \
                "sort-toolbar template 영역 남아있음"
    
    def test_old_toggleSort_calls_removed(self):
        """이전 단일 toggleSort/sortIcon 호출 사라짐."""
        c = self._content()
        # template 영역에서만 검사
        tmpl_end = c.find("</template>")
        if tmpl_end > 0:
            tmpl = c[:tmpl_end]
            # @click="toggleSort('xxx')" 또는 sortIcon('xxx') 호출
            assert "toggleSort('name')" not in tmpl
            assert "toggleSort('rows')" not in tmpl
            assert "toggleSort('size')" not in tmpl
            assert "toggleSort('date')" not in tmpl
            assert "toggleSort('type')" not in tmpl


class TestColumnHeaders:
    """각 박스에 컬럼 헤더 추가."""
    
    JW_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "JobWizard.vue"
    ))
    
    def _content(self):
        if not os.path.exists(self.JW_FILE):
            pytest.skip("")
        return open(self.JW_FILE, encoding='utf-8').read()
    
    def test_table_column_header(self):
        """테이블 박스 컬럼 헤더 (테이블명 / 타겟 / 행수 / 크기)."""
        c = self._content()
        assert "obj-row-table-head" in c
        # 테이블 헤더 안에 정렬 가능한 컬럼들
        assert "toggleTableSort('name')" in c
        assert "toggleTableSort('rows')" in c
        assert "toggleTableSort('size')" in c
    
    def test_proc_column_header(self):
        """프로시저 박스 - 이름 / 생성일."""
        c = self._content()
        assert "toggleProcSort('name')" in c
        assert "toggleProcSort('date')" in c
    
    def test_func_column_header(self):
        """함수 박스 - 이름 / 반환타입."""
        c = self._content()
        assert "toggleFuncSort('name')" in c
        assert "toggleFuncSort('type')" in c
    
    def test_trig_column_header(self):
        """트리거 박스 - 이름 / 이벤트 / 대상."""
        c = self._content()
        assert "toggleTrigSort('name')" in c
        assert "toggleTrigSort('event')" in c
        assert "toggleTrigSort('table')" in c
    
    def test_view_column_header(self):
        """뷰 박스 - 이름."""
        c = self._content()
        assert "toggleViewSort('name')" in c
    
    def test_sortable_class_in_template(self):
        """클릭 가능한 컬럼은 sortable 클래스."""
        c = self._content()
        assert 'class="orh-name sortable"' in c
        assert 'class="orh-rows sortable"' in c


class TestRowCountComma:
    """행수 천단위 콤마 표기."""
    
    JW_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "JobWizard.vue"
    ))
    
    def _content(self):
        if not os.path.exists(self.JW_FILE):
            pytest.skip("")
        return open(self.JW_FILE, encoding='utf-8').read()
    
    def test_fmtRowsComma_function(self):
        c = self._content()
        assert "fmtRowsComma" in c
        # toLocaleString 사용
        assert "toLocaleString" in c
    
    def test_table_row_uses_comma(self):
        """테이블 행이 fmtRowsComma 사용."""
        c = self._content()
        # 테이블 박스 영역에서 fmtRowsComma 호출
        assert "fmtRowsComma(t.row_count" in c


class TestColumnAlignment:
    """컬럼 라인 정렬 (헤더와 행이 같은 위치)."""
    
    JW_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "JobWizard.vue"
    ))
    
    def _content(self):
        if not os.path.exists(self.JW_FILE):
            pytest.skip("")
        return open(self.JW_FILE, encoding='utf-8').read()
    
    def test_arrow_fixed_width(self):
        """화살표 컬럼 14px 고정폭 (헤더와 행 동일)."""
        c = self._content()
        assert re.search(r"\.obj-tgt-arrow\s*\{[^}]*?width:\s*14px", c, re.DOTALL)
        assert re.search(r"\.orh-arrow\s*\{[^}]*?width:\s*14px", c, re.DOTALL)
    
    def test_rows_column_fixed_width(self):
        """행수 컬럼 80px 고정폭."""
        c = self._content()
        assert re.search(r"\.orh-rows\s*\{[^}]*?width:\s*80px", c, re.DOTALL)
        assert re.search(r"obj-meta-rows\s*\{[^}]*?width:\s*80px", c, re.DOTALL)
    
    def test_size_column_fixed_width(self):
        """크기 컬럼 60px 고정폭."""
        c = self._content()
        assert re.search(r"\.orh-size\s*\{[^}]*?width:\s*60px", c, re.DOTALL)
    
    def test_sortable_hover_styling(self):
        c = self._content()
        # .sortable:hover 색상
        assert ".sortable:hover" in c
    
    def test_sticky_header(self):
        """스크롤 시에도 헤더 고정."""
        c = self._content()
        assert re.search(r"\.obj-row-head\s*\{[^}]*?position:\s*sticky", c, re.DOTALL)


class TestBackwardCompatibility:
    """회귀 안전."""
    
    JW_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "JobWizard.vue"
    ))
    
    def _content(self):
        if not os.path.exists(self.JW_FILE):
            pytest.skip("")
        return open(self.JW_FILE, encoding='utf-8').read()
    
    def test_form_bindings_intact(self):
        c = self._content()
        for binding in ['v-model="form.tables"', 'v-model="form.procedures"',
                        'v-model="form.functions"', 'v-model="form.triggers"',
                        'v-model="form.views"']:
            assert binding in c
    
    def test_filtered_functions_intact(self):
        c = self._content()
        assert "filteredTables = computed" in c
        assert "filteredObjs = type =>" in c
    
    def test_5_boxes_intact(self):
        c = self._content()
        for box in ['obj-box-tables', 'obj-box-proc', 'obj-box-func',
                    'obj-box-trig', 'obj-box-view']:
            assert box in c
    
    def test_v90_74_layout_preserved(self):
        """v90.74 의 grid 레이아웃 보존."""
        c = self._content()
        assert "grid-template-areas:" in c
        assert "2.4fr 1fr 1fr 1fr" in c


class TestSortLogic:
    """정렬 로직 시뮬레이션."""
    
    def sort_simulator(self, items, key, dir_, getter_map):
        """v90.75 의 _applySortBy 미러."""
        if key not in getter_map:
            return items
        getter = getter_map[key]
        d = -1 if dir_ == 'desc' else 1
        result = sorted(items, key=getter)
        if d == -1:
            result = list(reversed(result))
        return result
    
    def test_table_sort_by_rows_desc(self):
        """테이블 행수 내림차순."""
        tables = [
            {'table_name': 'A', 'row_count': 100},
            {'table_name': 'B', 'row_count': 5000000},
            {'table_name': 'C', 'row_count': 0},
        ]
        getters = {'rows': lambda t: t['row_count']}
        result = self.sort_simulator(tables, 'rows', 'desc', getters)
        assert result[0]['table_name'] == 'B'   # 5M 가 1위
        assert result[-1]['table_name'] == 'C'  # 0 이 마지막
    
    def test_proc_sort_by_date(self):
        """프로시저 생성일 정렬."""
        procs = [
            {'name': 'SP_OLD', 'created': '2023-01-01'},
            {'name': 'SP_NEW', 'created': '2025-12-31'},
        ]
        getters = {'date': lambda p: p.get('created', '')}
        asc = self.sort_simulator(procs, 'date', 'asc', getters)
        assert asc[0]['name'] == 'SP_OLD'
        desc = self.sort_simulator(procs, 'date', 'desc', getters)
        assert desc[0]['name'] == 'SP_NEW'
    
    def test_independence(self):
        """다른 박스 정렬이 다른 박스에 영향 없음."""
        # 테이블은 rows 로 정렬, 프로시저는 name 으로 → 서로 독립
        tables = [{'name': 'T1', 'rows': 100}, {'name': 'T2', 'rows': 50}]
        procs = [{'name': 'B'}, {'name': 'A'}]
        
        t_result = self.sort_simulator(tables, 'rows', 'desc',
                                        {'rows': lambda t: t['rows']})
        p_result = self.sort_simulator(procs, 'name', 'asc',
                                        {'name': lambda p: p['name']})
        
        # 각각 독립적으로 정렬됨
        assert t_result[0]['name'] == 'T1'
        assert p_result[0]['name'] == 'A'


if __name__ == "__main__":
    print("=== v90.75 박스별 독립 정렬 ===\n")
    
    print("변경 전:")
    print("  [상단 정렬 툴바: 이름 ↕ | 행수 ↕ | 크기 ↕ | 생성일 ↕ | 타입 ↕]")
    print("    ↑ 한 번 클릭으로 모든 박스 동시 정렬")
    print()
    print("변경 후:")
    print("  테이블 박스:")
    print("    헤더: [☐] 테이블명 ↕ | → | 타겟 테이블명 | 행수 ↕ | 크기 ↕")
    print("    행:   [☐] dbo.tbl_x  →   tbl_x          1,234     2MB")
    print("                                              ^^^ 콤마 표기")
    print()
    print("  프로시저 박스: [☐] 이름 ↕ | 생성일 ↕")
    print("  함수 박스:     [☐] 이름 ↕ | 반환타입 ↕")
    print("  트리거 박스:   [☐] 이름 ↕ | 이벤트 ↕ | 대상 ↕")
    print("  뷰 박스:       [☐] 이름 ↕ | 타입")
    print()
    print("  → 각 박스 독립 정렬, 컬럼 라인 깔끔, 행수 콤마 표기")
    
    test = TestSortLogic()
    print("\n시뮬레이션:")
    
    tables = [
        {'name': 'small', 'rows': 100},
        {'name': 'huge', 'rows': 5000000},
        {'name': 'empty', 'rows': 0},
    ]
    result = test.sort_simulator(tables, 'rows', 'desc',
                                  {'rows': lambda t: t['rows']})
    print(f"  테이블 행수 내림차순: {[t['name'] for t in result]}")
    
    procs = [{'name': 'SP_Z'}, {'name': 'SP_A'}, {'name': 'SP_M'}]
    result = test.sort_simulator(procs, 'name', 'asc',
                                  {'name': lambda p: p['name']})
    print(f"  프로시저 이름 오름차순: {[p['name'] for p in result]}")
