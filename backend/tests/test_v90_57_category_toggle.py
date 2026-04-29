"""
test_v90_57_category_toggle.py — v90.57 (2026-04-28)

본부장님 요청: 카테고리 버튼 클릭 = 해당 카테고리 항목 전체 선택 ↔ 전체 해제

설계:
  - 다른 카테고리: 그 카테고리로 이동 (선택 변경 X)
  - 활성 카테고리 재클릭:
      none / partial → 전체 선택
      all            → 전체 해제 (토글)

이 테스트는 onCategoryClick / categorySelectionState / 
selectAllInCategory / deselectAllInCategory 의 Python 미러로 검증.

실행:
  cd backend
  pytest tests/test_v90_57_category_toggle.py -v
"""

import sys
import os
import pytest

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


# ════════════════════════════════════════════════════════════════════════════
# Vue 로직의 Python 미러
# ════════════════════════════════════════════════════════════════════════════

class AdvisorPanelMirror:
    """v90.57 의 카테고리 토글 로직 미러 (UI 무관 순수 로직)."""
    
    def __init__(self, recommendations, decision_map=None):
        self.recommendations = recommendations  # [{id, category, ...}]
        self.decision_map = decision_map or {}  # {id: 'pending'|'applied'|'edited'|'skipped'}
        self.active_category = 'server'
    
    def category_selection_state(self):
        """각 카테고리의 선택 상태 반환 — 'all' | 'partial' | 'none'."""
        state = {}
        cats = set(r['category'] for r in self.recommendations)
        # categoryTabs 와 동일한 4개 + 데이터에 있는 것
        for cat in (set(['server', 'table', 'object', 'index']) | cats):
            recs = [r for r in self.recommendations if r['category'] == cat]
            if not recs:
                state[cat] = 'none'
                continue
            sel = sum(1 for r in recs if self.decision_map.get(r['id']) in ('applied', 'edited'))
            if sel == 0:
                state[cat] = 'none'
            elif sel == len(recs):
                state[cat] = 'all'
            else:
                state[cat] = 'partial'
        return state
    
    def select_all_in_category(self, cat_id):
        touched = 0
        for r in self.recommendations:
            if r['category'] != cat_id:
                continue
            if self.decision_map.get(r['id']) != 'edited':
                self.decision_map[r['id']] = 'applied'
                touched += 1
        return touched
    
    def deselect_all_in_category(self, cat_id):
        touched = 0
        for r in self.recommendations:
            if r['category'] != cat_id:
                continue
            if self.decision_map.get(r['id']) in ('applied', 'edited'):
                self.decision_map[r['id']] = 'pending'
                touched += 1
        return touched
    
    def on_category_click(self, cat_id, cat_status='ok'):
        """카테고리 탭 클릭 핸들러 - v90.57 토글 로직."""
        if cat_status in ('pending', 'unsupported'):
            return 'no_op'  # disabled
        
        # 다른 카테고리 → 이동만
        if self.active_category != cat_id:
            self.active_category = cat_id
            return 'moved'
        
        # 활성 카테고리 재클릭 → 토글
        if cat_status != 'ok':
            return 'no_op'
        
        recs = [r for r in self.recommendations if r['category'] == cat_id]
        if not recs:
            return 'no_op'
        
        state = self.category_selection_state()[cat_id]
        if state == 'all':
            self.deselect_all_in_category(cat_id)
            return 'deselected'
        else:
            # none / partial → 전체 선택
            self.select_all_in_category(cat_id)
            return 'selected'


# ════════════════════════════════════════════════════════════════════════════
# 본부장님 화면 데이터 (서버 7 / 테이블 12 / SP 6 / 인덱스 25)
# ════════════════════════════════════════════════════════════════════════════

def _build_president_data():
    """본부장님 화면의 카테고리별 추천 항목 시뮬레이션."""
    recs = []
    # server: 7개
    for i in range(7):
        recs.append({'id': f'srv_{i}', 'category': 'server', 'severity': 'med'})
    # table: 12개
    for i in range(12):
        recs.append({'id': f'tbl_{i}', 'category': 'table', 'severity': 'high'})
    # object (SP/Function): 6개
    for i in range(6):
        recs.append({'id': f'obj_{i}', 'category': 'object', 'severity': 'low'})
    # index: 25개
    for i in range(25):
        recs.append({'id': f'idx_{i}', 'category': 'index', 'severity': 'med'})
    return recs


# ════════════════════════════════════════════════════════════════════════════
# 핵심 시나리오 검증
# ════════════════════════════════════════════════════════════════════════════

class TestCategoryToggle:
    """v90.57 카테고리 토글 핵심 동작."""
    
    def test_other_category_just_moves(self):
        """다른 카테고리 클릭은 이동만 (선택 변경 X)."""
        panel = AdvisorPanelMirror(_build_president_data())
        panel.active_category = 'server'
        
        # 처음엔 모두 pending
        initial_state = dict(panel.decision_map)
        
        # table 카테고리 클릭 (다른 카테고리)
        result = panel.on_category_click('table')
        
        assert result == 'moved'
        assert panel.active_category == 'table'
        # 선택 상태 변경 없음
        assert panel.decision_map == initial_state
    
    def test_active_category_first_reclick_selects_all(self):
        """활성 카테고리 첫 재클릭 = 전체 선택."""
        panel = AdvisorPanelMirror(_build_president_data())
        panel.active_category = 'server'
        
        # server 활성 상태에서 server 재클릭
        result = panel.on_category_click('server')
        
        assert result == 'selected'
        # server 의 7개 모두 applied
        server_recs = [r for r in panel.recommendations if r['category'] == 'server']
        for r in server_recs:
            assert panel.decision_map[r['id']] == 'applied'
        # 다른 카테고리는 영향 없음
        for r in panel.recommendations:
            if r['category'] != 'server':
                assert panel.decision_map.get(r['id']) is None or \
                       panel.decision_map.get(r['id']) == 'pending'
    
    def test_active_category_second_reclick_deselects_all(self):
        """활성 카테고리 두 번째 재클릭 = 전체 해제 (토글)."""
        panel = AdvisorPanelMirror(_build_president_data())
        panel.active_category = 'table'
        
        # 1차 재클릭 → 전체 선택
        panel.on_category_click('table')
        assert panel.category_selection_state()['table'] == 'all'
        
        # 2차 재클릭 → 전체 해제
        result = panel.on_category_click('table')
        assert result == 'deselected'
        assert panel.category_selection_state()['table'] == 'none'
        
        # table 의 12개 모두 pending
        table_recs = [r for r in panel.recommendations if r['category'] == 'table']
        for r in table_recs:
            assert panel.decision_map[r['id']] == 'pending'
    
    def test_partial_state_first_reclick_selects_all(self):
        """일부 선택된 상태(partial) 에서 재클릭 = 전체 선택."""
        panel = AdvisorPanelMirror(_build_president_data())
        panel.active_category = 'index'
        
        # 25개 중 5개만 미리 선택
        index_recs = [r for r in panel.recommendations if r['category'] == 'index']
        for r in index_recs[:5]:
            panel.decision_map[r['id']] = 'applied'
        
        assert panel.category_selection_state()['index'] == 'partial'
        
        # 재클릭 → 전체 선택 (해제 아님!)
        result = panel.on_category_click('index')
        assert result == 'selected'
        assert panel.category_selection_state()['index'] == 'all'
        
        # 25개 모두 applied
        for r in index_recs:
            assert panel.decision_map[r['id']] == 'applied'
    
    def test_edited_recs_preserved_on_select_all(self):
        """이미 'edited' (사용자가 SQL 수정) 한 항목은 select 시 보존."""
        panel = AdvisorPanelMirror(_build_president_data())
        panel.active_category = 'server'
        
        # server 의 첫 항목을 edited 로 미리 셋팅 (사용자가 SQL 수정한 상태)
        server_recs = [r for r in panel.recommendations if r['category'] == 'server']
        panel.decision_map[server_recs[0]['id']] = 'edited'
        
        # 활성 카테고리 재클릭 → 전체 선택
        panel.on_category_click('server')
        
        # edited 는 그대로, 나머지는 applied
        assert panel.decision_map[server_recs[0]['id']] == 'edited'  # 보존!
        for r in server_recs[1:]:
            assert panel.decision_map[r['id']] == 'applied'
    
    def test_pending_status_no_op(self):
        """pending 상태 카테고리는 클릭해도 동작 없음."""
        panel = AdvisorPanelMirror(_build_president_data())
        panel.active_category = 'server'
        
        result = panel.on_category_click('table', cat_status='pending')
        assert result == 'no_op'
        assert panel.active_category == 'server'  # 이동도 안 함


class TestPresidentScenario:
    """본부장님 화면 시나리오 (서버 7 / 테이블 12 / SP 6 / 인덱스 25)."""
    
    def test_president_screen_full_flow(self):
        """본부장님 시나리오 전체 흐름:
        1. 처음 server 활성, 모두 pending
        2. server 재클릭 → server 7개 선택
        3. table 클릭 → table 로 이동, server 선택 보존
        4. table 재클릭 → table 12개 선택
        5. server 클릭 → server 로 돌아감, 양쪽 선택 모두 보존
        6. server 재클릭 → server 전체 해제
        """
        panel = AdvisorPanelMirror(_build_president_data())
        
        # 1. 초기 상태
        assert panel.active_category == 'server'
        assert all(panel.decision_map.get(r['id']) is None or
                   panel.decision_map.get(r['id']) == 'pending'
                   for r in panel.recommendations)
        
        # 2. server 재클릭 → 7개 선택
        panel.on_category_click('server')
        states = panel.category_selection_state()
        assert states['server'] == 'all'
        assert states['table'] == 'none'
        
        # 3. table 클릭 → 이동 (server 선택 유지)
        panel.on_category_click('table')
        assert panel.active_category == 'table'
        states = panel.category_selection_state()
        assert states['server'] == 'all'  # 보존!
        assert states['table'] == 'none'
        
        # 4. table 재클릭 → 12개 선택
        panel.on_category_click('table')
        states = panel.category_selection_state()
        assert states['server'] == 'all'
        assert states['table'] == 'all'
        
        # 5. server 클릭 → 이동, 양쪽 선택 보존
        panel.on_category_click('server')
        assert panel.active_category == 'server'
        states = panel.category_selection_state()
        assert states['server'] == 'all'
        assert states['table'] == 'all'
        
        # 6. server 재클릭 → 전체 해제
        panel.on_category_click('server')
        states = panel.category_selection_state()
        assert states['server'] == 'none'
        assert states['table'] == 'all'  # table 은 영향 없음
    
    def test_no_cross_category_pollution(self):
        """카테고리 간 오염 없음 — server 토글이 다른 카테고리 영향 X."""
        panel = AdvisorPanelMirror(_build_president_data())
        
        # server 전체 선택
        panel.on_category_click('server')
        # 다른 모든 카테고리는 none 이어야
        states = panel.category_selection_state()
        assert states['server'] == 'all'
        assert states['table'] == 'none'
        assert states['object'] == 'none'
        assert states['index'] == 'none'
        
        # server 전체 해제
        panel.on_category_click('server')
        states = panel.category_selection_state()
        assert states['server'] == 'none'
        # 다른 것들 여전히 none
        assert states['table'] == 'none'


if __name__ == "__main__":
    print("=== 본부장님 화면 시나리오 시뮬레이션 ===")
    panel = AdvisorPanelMirror(_build_president_data())
    
    print(f"\n초기: active={panel.active_category}, "
          f"states={panel.category_selection_state()}")
    
    print("\n[1] 서버설정 재클릭 → 7개 선택")
    panel.on_category_click('server')
    print(f"  active={panel.active_category}, states={panel.category_selection_state()}")
    
    print("\n[2] 테이블구조 클릭 → 이동")
    panel.on_category_click('table')
    print(f"  active={panel.active_category}, states={panel.category_selection_state()}")
    
    print("\n[3] 테이블구조 재클릭 → 12개 선택")
    panel.on_category_click('table')
    print(f"  active={panel.active_category}, states={panel.category_selection_state()}")
    
    print("\n[4] 인덱스 클릭 → 이동")
    panel.on_category_click('index')
    print(f"  active={panel.active_category}, states={panel.category_selection_state()}")
    
    print("\n[5] 인덱스 재클릭 → 25개 선택")
    panel.on_category_click('index')
    print(f"  active={panel.active_category}, states={panel.category_selection_state()}")
    
    print("\n[6] 인덱스 다시 재클릭 → 25개 해제")
    panel.on_category_click('index')
    print(f"  active={panel.active_category}, states={panel.category_selection_state()}")
