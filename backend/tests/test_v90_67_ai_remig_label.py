"""
test_v90_67_ai_remig_label.py — v90.67 (2026-04-28)

본부장님 호소:
  1. "AI 재이관으로 성공한 건 별도 라벨로 보여달라"
  2. "상태 카드 안에 테이블/객체 분리, 우측 KPI 폭 줄여달라"

v90.67 처방:
  Backend (migration_engine.py + schema.py):
    - item_statuses 에 had_error, attempts, via_ai_remig 필드 추가
    - AI 재이관 Job 의 객체는 via_ai_remig=True 마킹
    - 일반 Job 안의 retry 성공도 had_error=True 로 추적
  
  Frontend (JobMonitor.vue):
    - via_ai_remig=true 면 "AI 재이관 성공" 라벨 (보라색 + 🤖 아이콘)
    - had_error=true 면 "재시도 성공" 라벨 (청록색 + ↻ 아이콘)
    - 상태 카드 하단에 테이블/객체 분리 카운트 표시
    - kpi-grid 비율 조정 (상태 1.1→1.4, 우측 1→0.85)
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
# Backend 검증
# ════════════════════════════════════════════════════════════════════════════

class TestBackendStatusFields:
    """item_statuses 의 새 필드 검증."""
    
    ENGINE_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "app", "engine", "migration_engine.py"
    ))
    SCHEMA_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "app", "api", "routes", "schema.py"
    ))
    
    def test_engine_v90_67_marker(self):
        if not os.path.exists(self.ENGINE_FILE):
            pytest.skip(f"{self.ENGINE_FILE} 없음")
        content = open(self.ENGINE_FILE, encoding='utf-8').read()
        assert "v90.67" in content
    
    def test_engine_done_path_has_had_error_attempts(self):
        """객체 성공 path 에 had_error / attempts 보존 로직 있어야."""
        if not os.path.exists(self.ENGINE_FILE):
            pytest.skip("")
        content = open(self.ENGINE_FILE, encoding='utf-8').read()
        # done path 에 had_error / attempts 필드 set
        assert '"had_error"' in content, "had_error 필드 누락"
        assert '"attempts"' in content, "attempts 필드 누락"
    
    def test_engine_error_path_marks_had_error(self):
        """에러 path 도 had_error=True 마킹."""
        if not os.path.exists(self.ENGINE_FILE):
            pytest.skip("")
        content = open(self.ENGINE_FILE, encoding='utf-8').read()
        # error path 에 had_error: True
        assert re.search(r'"status":"error".*"had_error":\s*True', content, re.DOTALL), \
            "error path 의 had_error=True 마킹 누락"
    
    def test_schema_v90_67_marker(self):
        if not os.path.exists(self.SCHEMA_FILE):
            pytest.skip("")
        content = open(self.SCHEMA_FILE, encoding='utf-8').read()
        assert "v90.67" in content
    
    def test_remigrate_job_marks_via_ai_remig(self):
        """create_remigrate_job 의 item_statuses 에 via_ai_remig=True."""
        if not os.path.exists(self.SCHEMA_FILE):
            pytest.skip("")
        content = open(self.SCHEMA_FILE, encoding='utf-8').read()
        assert '"via_ai_remig": True' in content, \
            "create_remigrate_job 의 via_ai_remig=True 누락"
    
    def test_remigrate_update_increments_attempts(self):
        """update_remigrate_item 이 attempts 를 증가."""
        if not os.path.exists(self.SCHEMA_FILE):
            pytest.skip("")
        content = open(self.SCHEMA_FILE, encoding='utf-8').read()
        # update_remigrate_item 안에서 attempts 증가
        update_fn = content[content.find("def update_remigrate_item"):content.find("def update_remigrate_item") + 2000]
        assert 'item["attempts"]' in update_fn, "update_remigrate_item 에서 attempts 증가 누락"


# ════════════════════════════════════════════════════════════════════════════
# Frontend 검증
# ════════════════════════════════════════════════════════════════════════════

class TestFrontendLabels:
    """JobMonitor.vue 의 v90.67 라벨 + UI 변경."""
    
    JM_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "JobMonitor.vue"
    ))
    
    def test_v90_67_marker(self):
        if not os.path.exists(self.JM_FILE):
            pytest.skip("")
        content = open(self.JM_FILE, encoding='utf-8').read()
        assert "v90.67" in content
    
    def test_ai_remig_label_template(self):
        """AI 재이관 성공 라벨 (template)."""
        if not os.path.exists(self.JM_FILE):
            pytest.skip("")
        content = open(self.JM_FILE, encoding='utf-8').read()
        assert "via_ai_remig" in content, "via_ai_remig 조건 누락"
        assert "AI 재이관 성공" in content, "AI 재이관 성공 라벨 누락"
    
    def test_recovered_label_template(self):
        """재시도 후 성공 라벨 (template)."""
        if not os.path.exists(self.JM_FILE):
            pytest.skip("")
        content = open(self.JM_FILE, encoding='utf-8').read()
        assert "had_error" in content
        assert "재시도 성공" in content
    
    def test_stat_pill_via_ai_css(self):
        """stat-pill.via-ai 스타일 (보라)."""
        if not os.path.exists(self.JM_FILE):
            pytest.skip("")
        content = open(self.JM_FILE, encoding='utf-8').read()
        assert ".stat-pill.done.via-ai" in content
    
    def test_stat_pill_recovered_css(self):
        """stat-pill.recovered 스타일 (청록)."""
        if not os.path.exists(self.JM_FILE):
            pytest.skip("")
        content = open(self.JM_FILE, encoding='utf-8').read()
        assert ".stat-pill.done.recovered" in content
    
    def test_phase_counts_template(self):
        """상태 카드 하단 — 테이블/객체 분리 진행률."""
        if not os.path.exists(self.JM_FILE):
            pytest.skip("")
        content = open(self.JM_FILE, encoding='utf-8').read()
        assert "phase-counts" in content
        assert "phase-count-row" in content
    
    def test_phase_counts_css(self):
        """phase-counts CSS 정의."""
        if not os.path.exists(self.JM_FILE):
            pytest.skip("")
        content = open(self.JM_FILE, encoding='utf-8').read()
        assert ".phase-counts" in content
        assert ".phase-count-val" in content
    
    def test_kpi_grid_columns_adjusted(self):
        """kpi-grid 비율 조정: 상태 1.4, 우측 0.85."""
        if not os.path.exists(self.JM_FILE):
            pytest.skip("")
        content = open(self.JM_FILE, encoding='utf-8').read()
        # 새 비율 패턴
        assert "1.4fr 1.6fr 0.85fr 0.85fr 0.85fr" in content, \
            "kpi-grid 비율 조정 누락"
    
    def test_status_label_logic(self):
        """라벨 우선순위: AI 재이관 > 재시도 성공 > 일반 done."""
        if not os.path.exists(self.JM_FILE):
            pytest.skip("")
        content = open(self.JM_FILE, encoding='utf-8').read()
        # via_ai_remig 가 had_error 보다 먼저 검사되어야 (우선순위)
        ai_idx = content.find("AI 재이관 성공")
        retry_idx = content.find("재시도 성공")
        assert ai_idx > 0 and retry_idx > 0
        assert ai_idx < retry_idx, "AI 재이관 라벨이 재시도 성공 라벨보다 먼저 와야 (우선순위)"


class TestUiSimulation:
    """라벨 우선순위 로직 시뮬레이션."""
    
    def get_label(self, item):
        """v90.67 라벨 결정 로직 미러."""
        if item.get('status') == 'done' and item.get('via_ai_remig'):
            return 'AI 재이관 성공'
        if item.get('status') == 'done' and item.get('had_error'):
            return '재시도 성공'
        if item.get('status') == 'done':
            return '완료'
        if item.get('status') == 'error':
            return '오류'
        return '대기'
    
    def test_ai_remig_done_shows_ai_label(self):
        item = {'status': 'done', 'via_ai_remig': True, 'had_error': True, 'attempts': 2}
        assert self.get_label(item) == 'AI 재이관 성공'
    
    def test_first_try_done_shows_complete(self):
        item = {'status': 'done', 'had_error': False, 'attempts': 1}
        assert self.get_label(item) == '완료'
    
    def test_retry_done_shows_retry_success(self):
        """일반 Job 안에서 1차 실패 → 2차 성공."""
        item = {'status': 'done', 'had_error': True, 'attempts': 2, 'via_ai_remig': False}
        assert self.get_label(item) == '재시도 성공'
    
    def test_error_shows_error(self):
        item = {'status': 'error', 'had_error': True, 'attempts': 1}
        assert self.get_label(item) == '오류'


if __name__ == "__main__":
    print("=== v90.67 본부장님 시나리오 ===\n")
    
    cases = [
        ("1차 시도 성공",            {'status': 'done', 'attempts': 1, 'had_error': False}),
        ("재시도 후 성공",           {'status': 'done', 'attempts': 2, 'had_error': True}),
        ("AI 재이관으로 성공",       {'status': 'done', 'attempts': 2, 'had_error': True, 'via_ai_remig': True}),
        ("실패 (재이관 필요)",       {'status': 'error', 'attempts': 1, 'had_error': True}),
    ]
    
    test = TestUiSimulation()
    for name, item in cases:
        label = test.get_label(item)
        emoji = '✓' if item['status'] == 'done' else '✗'
        print(f"  {emoji} {name:25s} → 라벨: '{label}'")
