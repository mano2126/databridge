"""
test_v90_60_progress_fallback.py — v90.60 (2026-04-28)

본부장님 화면 캡처 진단 결과:
  - LIVE 배너:    kyc_document  31%  305,000 / 1,000,000 rows  (정상 표시)
  - 테이블 카드:  kyc_document  31%  0 → 0  20분 34초 진행중   (rows 비어있음)
  
  같은 데이터를 두 곳에서 표시하는데 한 쪽은 정확, 한 쪽은 0/0.
  → backend 의 item_statuses[].rows_src 갱신이 어떤 타이밍 / 경로에서 누락
  → top-level current_table_rows_done 은 정확히 갱신됨

v90.60 처방:
  Frontend 가 다음 우선순위로 표시:
    1. item.rows_tgt / item.rows_src (정상 케이스 - backend 가 정확히 갱신)
    2. top-level job.current_table_rows_done (현재 테이블이고 item 비어있을 때)
    3. 0
  
  total 도 동일 fallback (current_table_rows_total)

이 테스트는 fallback 로직의 Python 미러로 검증.
"""

import sys
import os
import re
import pytest

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)
JM_FILE = os.path.normpath(os.path.join(_BACKEND_DIR, '..', 'frontend', 'src', 'pages', 'JobMonitor.vue'))


# ════════════════════════════════════════════════════════════════════════════
# Python 미러 - JobMonitor.vue 의 fallback 로직
# ════════════════════════════════════════════════════════════════════════════

def is_current_table(item, job):
    """item.name === job.current_table"""
    return bool(job and job.get('current_table') 
                and item and item.get('name') == job['current_table'])


def display_rows_done(item, job):
    """
    표시용 처리 행수.
    우선순위: item.rows_tgt > item.rows_src > current_table_rows_done (현재 테이블)
    """
    v = int(item.get('rows_tgt') or item.get('rows_src') or 0)
    if v > 0:
        return v
    if is_current_table(item, job):
        return int(job.get('current_table_rows_done') or 0)
    return 0


def display_rows_total(item, job):
    """
    표시용 전체 행수.
    우선순위: item.rows_total > current_table_rows_total (현재 테이블)
    """
    v = int(item.get('rows_total') or 0)
    if v > 0:
        return v
    if is_current_table(item, job):
        return int(job.get('current_table_rows_total') or 0)
    return 0


# ════════════════════════════════════════════════════════════════════════════
# 본부장님 시나리오 검증
# ════════════════════════════════════════════════════════════════════════════

class TestPresidentScenario:
    """본부장님 캡처 시나리오 — kyc_document 305,000/1,000,000 진행 중."""
    
    def test_president_capture_scenario(self):
        """
        화면 캡처와 정확히 동일한 backend 응답 시뮬레이션:
          - top-level: current_table=kyc_document, current_table_rows_done=305000,
                       current_table_rows_total=1000000
          - item_statuses[kyc_document]: status=running, rows_src=0, rows_tgt=0
                                          (이게 0 → 0 표시의 원인)
        """
        job = {
            'current_table': 'kyc_document',
            'current_table_rows_done': 305000,
            'current_table_rows_total': 1000000,
            'item_statuses': {
                'kyc_document': {
                    'type': 'table',
                    'status': 'running',
                    'name': 'kyc_document',
                    'rows_src': 0,
                    'rows_tgt': 0,
                    # rows_total 도 비어있음
                }
            }
        }
        item = {
            'type': 'table',
            'status': 'running',
            'name': 'kyc_document',
            'rows_src': 0,
            'rows_tgt': 0,
        }
        
        # v90.60 fallback 동작 검증
        done = display_rows_done(item, job)
        total = display_rows_total(item, job)
        
        # 305,000 / 1,000,000 으로 정확히 표시되어야
        assert done == 305000, f"done={done} (예상: 305000)"
        assert total == 1000000, f"total={total} (예상: 1000000)"
    
    def test_normal_scenario_still_works(self):
        """정상 케이스 (backend 가 item rows 잘 갱신) 도 그대로 동작."""
        job = {
            'current_table': 'application',
            'current_table_rows_done': 1500000,
            'current_table_rows_total': 2000000,
            'item_statuses': {
                'application': {
                    'name': 'application',
                    'status': 'running',
                    'rows_src': 1500000,
                    'rows_tgt': 1500000,
                    'rows_total': 2000000,
                }
            }
        }
        item = {
            'name': 'application',
            'status': 'running',
            'rows_src': 1500000,
            'rows_tgt': 1500000,
            'rows_total': 2000000,
        }
        
        done = display_rows_done(item, job)
        total = display_rows_total(item, job)
        
        # 정상 데이터 그대로 사용 (fallback 안 발동)
        assert done == 1500000
        assert total == 2000000
    
    def test_other_table_not_current_no_fallback(self):
        """
        진행 중 테이블이 아닌 테이블 (대기/완료) 은 fallback 안 함.
        만약 fallback 하면 모든 행이 305,000 로 잘못 표시됨.
        """
        job = {
            'current_table': 'kyc_document',  # 진행 중인 건 kyc_document
            'current_table_rows_done': 305000,
            'current_table_rows_total': 1000000,
            'item_statuses': {}
        }
        item = {
            'name': 'org_unit',  # 다른 테이블
            'status': 'pending',
            'rows_src': 0,
            'rows_tgt': 0,
        }
        
        done = display_rows_done(item, job)
        total = display_rows_total(item, job)
        
        # 다른 테이블이니 fallback 안 함 (kyc_document 의 305,000 가 묻혀 들어가면 안 됨)
        assert done == 0
        assert total == 0
    
    def test_completed_table_uses_own_rows(self):
        """완료된 테이블은 자기 rows_src/tgt 사용 (현재 테이블 fallback X)."""
        job = {
            'current_table': 'kyc_document',
            'current_table_rows_done': 305000,
            'current_table_rows_total': 1000000,
            'item_statuses': {
                'application': {
                    'name': 'application', 'status': 'done',
                    'rows_src': 2000000, 'rows_tgt': 2000000,
                    'rows_total': 2000000,
                }
            }
        }
        item = {
            'name': 'application', 'status': 'done',
            'rows_src': 2000000, 'rows_tgt': 2000000, 'rows_total': 2000000,
        }
        
        done = display_rows_done(item, job)
        total = display_rows_total(item, job)
        
        # 자기 데이터 그대로
        assert done == 2000000
        assert total == 2000000
    
    def test_partial_data_in_item_statuses(self):
        """
        rows_src 는 일부 갱신됐지만 rows_tgt 는 비어있는 케이스.
        우선순위: rows_tgt > rows_src — rows_tgt 가 0이고 rows_src 가 있으면 rows_src 사용.
        """
        job = {
            'current_table': 'kyc_document',
            'current_table_rows_done': 400000,
            'current_table_rows_total': 1000000,
            'item_statuses': {}
        }
        item = {
            'name': 'kyc_document', 'status': 'running',
            'rows_src': 350000,  # 갱신됨
            'rows_tgt': 0,       # 아직 안 갱신
        }
        
        done = display_rows_done(item, job)
        # rows_src=350000 사용 (rows_tgt=0 이라 그 다음으로 넘어가서 src 사용)
        assert done == 350000


class TestPatchMarkers:
    """JobMonitor.vue 에 v90.60 패치 마커 확인."""
    
    def test_jm_v90_60_marker(self):
        if not os.path.exists(JM_FILE):
            pytest.skip(f"{JM_FILE} 없음")
        content = open(JM_FILE, encoding='utf-8').read()
        assert "v90.60" in content, "v90.60 마커 누락"
    
    def test_helper_functions_present(self):
        if not os.path.exists(JM_FILE):
            pytest.skip(f"{JM_FILE} 없음")
        content = open(JM_FILE, encoding='utf-8').read()
        assert "function _isCurrentTable" in content, "_isCurrentTable 함수 누락"
        assert "function _displayRowsDone" in content, "_displayRowsDone 함수 누락"
        assert "function _displayRowsTotal" in content, "_displayRowsTotal 함수 누락"
    
    def test_template_uses_helpers(self):
        if not os.path.exists(JM_FILE):
            pytest.skip(f"{JM_FILE} 없음")
        content = open(JM_FILE, encoding='utf-8').read()
        # template 의 진행 중 행에서 헬퍼 사용
        assert "_displayRowsDone(item)" in content, "template 에 _displayRowsDone 호출 누락"
        assert "_displayRowsTotal(item)" in content, "template 에 _displayRowsTotal 호출 누락"
    
    def test_progLabel_has_fallback(self):
        if not os.path.exists(JM_FILE):
            pytest.skip(f"{JM_FILE} 없음")
        content = open(JM_FILE, encoding='utf-8').read()
        # progLabel 함수 안에 v90.60 fallback 주석
        assert re.search(r"v90\.60 fallback", content), "progLabel fallback 주석 누락"
    
    def test_fmtItemEta_has_fallback(self):
        if not os.path.exists(JM_FILE):
            pytest.skip(f"{JM_FILE} 없음")
        content = open(JM_FILE, encoding='utf-8').read()
        # fmtItemEta 함수 안에 current_table_rows_total fallback
        assert re.search(
            r"v90\.60.*top-level current_table_rows_total fallback",
            content
        ), "fmtItemEta fallback 주석 누락"


if __name__ == "__main__":
    print("=== 본부장님 화면 시나리오 시뮬레이션 ===")
    job = {
        'current_table': 'kyc_document',
        'current_table_rows_done': 305000,
        'current_table_rows_total': 1000000,
        'item_statuses': {'kyc_document': {'name': 'kyc_document', 'status': 'running',
                                           'rows_src': 0, 'rows_tgt': 0}}
    }
    item = {'name': 'kyc_document', 'status': 'running',
            'rows_src': 0, 'rows_tgt': 0}
    
    print(f"backend 응답: rows_src=0, rows_tgt=0")
    print(f"top-level: current_table_rows_done=305000, total=1000000")
    print()
    print(f"v90.60 fallback 결과:")
    print(f"  표시 done:  {display_rows_done(item, job):,} (예상: 305,000)")
    print(f"  표시 total: {display_rows_total(item, job):,} (예상: 1,000,000)")
    print(f"  → 화면: 305,000 → 1,000,000 ✓")
