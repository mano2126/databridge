"""
test_v90_78_select_fix.py — v90.78 (2026-04-28)

본부장님 호소:
  ① "각 오브젝트 컬럼명 선택하면 전체선택/해제 기능 만들자
     체크박스 찾아서 클릭하기 어려워."
  ② "전부 해제하고 프로시저 하나만 선택하고 검증 실행 했는데
     전체가 다 실행되버렸어. 선택이 좀 이상해 확인해보자."

v90.78 처방:
  ① 섹션 헤더 (vp-obj-sec-hdr) 전체를 클릭 영역으로 → toggleGrp 호출
     - 체크박스 영역만이 아닌 헤더 전체 클릭으로 전체 선택/해제
     - hover 시 시각적 피드백 (배경색 + label 색)
     - indeterminate 상태 (일부 선택) 표시
  ② runObjValidate 의 hadExisting 분기에서 _sel 기반 필터링 적용
     - 이전: objResults 전체 재사용 (선택 무관)
     - 이후: objGroups[*]._sel 로 selectedSet 만들어 objResults 필터링
"""

import os
import re
import pytest


_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)


class TestClickableHeader:
    """① 섹션 헤더 전체 클릭 가능."""
    
    VAL_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "Validate.vue"
    ))
    
    def _content(self):
        if not os.path.exists(self.VAL_FILE):
            pytest.skip("")
        return open(self.VAL_FILE, encoding='utf-8').read()
    
    def test_v90_78_marker(self):
        c = self._content()
        assert "v90.78" in c
        assert c.count("v90.78") >= 2
    
    def test_clickable_class_added(self):
        """vp-obj-sec-hdr-clickable 클래스 적용."""
        c = self._content()
        assert "vp-obj-sec-hdr-clickable" in c
    
    def test_header_has_click_handler(self):
        """헤더 div 에 @click 으로 toggleGrp 호출."""
        c = self._content()
        # template 영역에서 헤더 div 의 @click="toggleGrp(grp)"
        assert re.search(
            r'class="vp-obj-sec-hdr vp-obj-sec-hdr-clickable"\s*\n?\s*@click="toggleGrp\(grp\)"',
            c
        )
    
    def test_label_click_stop(self):
        """label 영역은 @click.stop 으로 중복 방지."""
        c = self._content()
        # label 안의 체크박스 클릭이 헤더 click 에 버블링 안 되도록
        assert "@click.stop" in c
    
    def test_indeterminate_state(self):
        """일부만 선택 시 indeterminate 표시."""
        c = self._content()
        assert "indeterminate.prop" in c
        # some(o=>o._sel) && !every(o=>o._sel) 패턴
        assert re.search(r"items\.some\(o=>o\._sel\)\s*&&\s*!grp\.items\.every", c)
    
    def test_hover_styling(self):
        """hover 시 시각적 피드백."""
        c = self._content()
        # CSS 정의 확인
        assert ".vp-obj-sec-hdr-clickable:hover" in c
        # cursor: pointer
        assert re.search(r"\.vp-obj-sec-hdr-clickable\s*\{[^}]*cursor:\s*pointer", c, re.DOTALL)
        # user-select: none (드래그 방지)
        assert "user-select: none" in c


class TestSelectionFilterFix:
    """② _sel 기반 필터링 (검증 실행 시 선택만 실행)."""
    
    VAL_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "Validate.vue"
    ))
    
    def _content(self):
        if not os.path.exists(self.VAL_FILE):
            pytest.skip("")
        return open(self.VAL_FILE, encoding='utf-8').read()
    
    def test_selectedSet_built(self):
        """objGroups 의 _sel 기반 selectedSet 생성."""
        c = self._content()
        assert "selectedSet" in c
        assert "selectedSet.add" in c
        # type::name 키 형식
        assert "${grp.type}::${obj.name}" in c
    
    def test_objResults_filtered(self):
        """objResults 가 selectedSet 으로 필터링됨."""
        c = self._content()
        assert "filteredResults" in c
        # filter(r => selectedSet.has(...))
        assert "selectedSet.has(key)" in c
    
    def test_empty_selection_warning(self):
        """선택 없을 때 경고 메시지."""
        c = self._content()
        assert "선택된 객체가 없습니다" in c
    
    def test_new_selection_added(self):
        """이전에 없던 객체를 새로 선택하면 추가됨."""
        c = self._content()
        # existingKeys 로 중복 회피
        assert "existingKeys" in c
        # 신규 선택 객체 push
        assert "filteredResults.push" in c
    
    def test_status_initialization_preserved(self):
        """기존 status='checking' 초기화 로직 보존."""
        c = self._content()
        # hadExisting 분기 안에서 r.status = 'checking' 보존
        assert "r.status = 'checking'" in c


class TestBackwardCompatibility:
    """회귀 안전 - 이전 패치들 보존."""
    
    VAL_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "Validate.vue"
    ))
    
    def _content(self):
        if not os.path.exists(self.VAL_FILE):
            pytest.skip("")
        return open(self.VAL_FILE, encoding='utf-8').read()
    
    def test_v90_69_auto_reconnect(self):
        c = self._content()
        assert "_autoReconnectIfPossible" in c
    
    def test_v90_70_name_variant(self):
        c = self._content()
        assert "_ckName" in c
    
    def test_v90_72_no_duplicate_indicator(self):
        c = self._content()
        assert '<div v-if="connector.bothConnected && !migratingNow" class="vp-conn-status">' not in c
    
    def test_v90_76_force_refresh(self):
        c = self._content()
        # runValidate 시작에 무조건 loadTables
        idx = c.find("async function runValidate()")
        body = c[idx:idx+1500] if idx > 0 else ""
        assert "v90.76" in body
        assert "await loadTables()" in body
    
    def test_toggleGrp_function_intact(self):
        c = self._content()
        assert "function toggleGrp" in c


class TestSimulation:
    """선택 필터링 로직 시뮬레이션."""
    
    def filter_selected(self, obj_groups, prev_results):
        """v90.78 의 _sel 기반 필터링 미러."""
        sel_set = set()
        for grp in obj_groups:
            for obj in grp['items']:
                if obj.get('_sel'):
                    sel_set.add(f"{grp['type']}::{obj['name']}")
        
        filtered = [r for r in prev_results
                    if f"{r['type']}::{r['name']}" in sel_set]
        existing_keys = set(f"{r['type']}::{r['name']}" for r in filtered)
        
        for grp in obj_groups:
            for obj in grp['items']:
                k = f"{grp['type']}::{obj['name']}"
                if obj.get('_sel') and k not in existing_keys:
                    filtered.append({
                        'name': obj['name'], 'type': grp['type'],
                        'status': 'checking',
                    })
        return filtered
    
    def test_one_selected_only_one_validated(self):
        """본부장님 케이스: 1개만 선택 → 1개만 검증."""
        groups = [
            {'type': 'PROCEDURE', 'items': [
                {'name': 'SP_A', '_sel': False},
                {'name': 'SP_B', '_sel': True},   # ← 1개만 체크
                {'name': 'SP_C', '_sel': False},
            ]},
            {'type': 'FUNCTION', 'items': [
                {'name': 'FN_X', '_sel': False},
            ]},
        ]
        prev = [
            {'type': 'PROCEDURE', 'name': 'SP_A', 'status': 'pass'},
            {'type': 'PROCEDURE', 'name': 'SP_B', 'status': 'fail'},
            {'type': 'PROCEDURE', 'name': 'SP_C', 'status': 'pass'},
            {'type': 'FUNCTION', 'name': 'FN_X', 'status': 'pass'},
        ]
        filtered = self.filter_selected(groups, prev)
        assert len(filtered) == 1
        assert filtered[0]['name'] == 'SP_B'
    
    def test_all_deselected_returns_empty(self):
        """모두 해제 → 빈 결과."""
        groups = [
            {'type': 'PROCEDURE', 'items': [
                {'name': 'SP_A', '_sel': False},
            ]},
        ]
        prev = [{'type': 'PROCEDURE', 'name': 'SP_A', 'status': 'pass'}]
        filtered = self.filter_selected(groups, prev)
        assert len(filtered) == 0
    
    def test_new_selection_added(self):
        """이전 결과에 없던 객체 새로 선택 → 추가됨."""
        groups = [
            {'type': 'PROCEDURE', 'items': [
                {'name': 'SP_A', '_sel': True},
                {'name': 'SP_NEW', '_sel': True},   # 신규
            ]},
        ]
        prev = [{'type': 'PROCEDURE', 'name': 'SP_A', 'status': 'pass'}]
        filtered = self.filter_selected(groups, prev)
        assert len(filtered) == 2
        names = [r['name'] for r in filtered]
        assert 'SP_A' in names
        assert 'SP_NEW' in names
    
    def test_existing_results_preserved(self):
        """선택된 객체의 이전 결과는 보존됨."""
        groups = [{'type': 'PROCEDURE', 'items': [{'name': 'SP_A', '_sel': True}]}]
        prev = [{'type': 'PROCEDURE', 'name': 'SP_A', 'status': 'pass'}]
        filtered = self.filter_selected(groups, prev)
        assert filtered[0]['status'] == 'pass'  # 보존


if __name__ == "__main__":
    print("=== v90.78 선택 필터링 + 헤더 클릭 ===\n")
    
    test = TestSimulation()
    
    print("Before (v90.76):")
    print("  사용자: 모두 해제 + SP_B 만 체크 → 검증 실행")
    print("  코드:   hadExisting=true → objResults 전체 재사용 (선택 무관)")
    print("          → SP_A, SP_B, SP_C 모두 실행 ★ 버그 ★")
    print()
    print("After (v90.78):")
    print("  사용자: 동일 흐름")
    print("  코드:   selectedSet = {'PROCEDURE::SP_B'}")
    print("          objResults filter → SP_B 만 남음")
    print("          → SP_B 만 실행 ✓")
    print()
    
    groups = [{'type': 'PROCEDURE', 'items': [
        {'name': 'SP_A', '_sel': False},
        {'name': 'SP_B', '_sel': True},
        {'name': 'SP_C', '_sel': False},
    ]}]
    prev = [
        {'type': 'PROCEDURE', 'name': n, 'status': 's'}
        for n in ['SP_A', 'SP_B', 'SP_C']
    ]
    filtered = test.filter_selected(groups, prev)
    print(f"시뮬레이션 결과: {[r['name'] for r in filtered]}")
    print()
    print("UX 개선:")
    print("  - 섹션 헤더 전체 영역 클릭 가능 (이전: 체크박스만)")
    print("  - hover 시 색상 변경 (피드백)")
    print("  - indeterminate 상태 (일부 선택) 표시")
