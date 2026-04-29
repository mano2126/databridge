"""
test_v90_65_progress_kpi_fix.py — v90.65 (2026-04-28)

본부장님 호소: "전체 진행 상태바 안 움직여"

진단:
  화면 캡처에 따르면:
  - 전체 진행 0% (KPI 카드)
  - 테이블 0/0 완료
  - 함수 2/11, SP 0/15 (객체 진행률은 잘 동작)
  → backend job.progress 가 0 (테이블 이관 단계 기준)
  → 객체 변환 진행률이 KPI 카드에 반영 안 됨

v90.65 처방:
  effectiveProgress computed 추가 — backend progress 가 0 일 때
  객체 진행률 (objectsProgress.done + failed / total) 직접 계산.
  template 의 KPI 카드만 effectiveProgress 사용 (safeProgress 보존).
"""

import os
import re
import pytest

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)

JM_FILE = os.path.normpath(os.path.join(
    _BACKEND_DIR, "..", "frontend", "src", "pages", "JobMonitor.vue"
))


# ════════════════════════════════════════════════════════════════════════════
# Python 미러 — Vue computed 로직 시뮬레이션
# ════════════════════════════════════════════════════════════════════════════

def safeProgress_mirror(job):
    """safeProgress 의 Python 미러."""
    if not job:
        return 0
    p = job.get('progress', 0) or 0
    return min(100, max(0, round(p * 10) / 10))


def objectsProgress_mirror(job):
    """objectsProgress 의 Python 미러."""
    if not job or 'item_statuses' not in job:
        return None
    
    result = {
        'function':  {'done': 0, 'total': 0, 'running': 0, 'failed': 0},
        'procedure': {'done': 0, 'total': 0, 'running': 0, 'failed': 0},
        'view':      {'done': 0, 'total': 0, 'running': 0, 'failed': 0},
        'trigger':   {'done': 0, 'total': 0, 'running': 0, 'failed': 0},
    }
    
    for s in job['item_statuses'].values():
        if not s:
            continue
        t = (s.get('type', '') or '').lower()
        if t not in result:
            continue
        result[t]['total'] += 1
        status = s.get('status', '')
        if status in ('done', 'completed'):
            result[t]['done'] += 1
        elif status == 'running':
            result[t]['running'] += 1
        elif status in ('failed', 'error'):
            result[t]['failed'] += 1
    
    totalAll = sum(r['total'] for r in result.values())
    doneAll = sum(r['done'] for r in result.values())
    runningAll = sum(r['running'] for r in result.values())
    failedAll = sum(r['failed'] for r in result.values())
    
    if totalAll == 0:
        return None
    
    return {
        **result,
        'total': totalAll,
        'done': doneAll,
        'running': runningAll,
        'failed': failedAll,
    }


def effectiveProgress_mirror(job):
    """v90.65 effectiveProgress 의 Python 미러."""
    backend = safeProgress_mirror(job)
    if backend > 0:
        return backend
    
    op = objectsProgress_mirror(job)
    if op and op['total'] > 0:
        processedAll = op['done'] + op['failed']
        return min(100, round((processedAll / op['total']) * 100 * 10) / 10)
    
    return 0


# ════════════════════════════════════════════════════════════════════════════
# 본부장님 시나리오 검증
# ════════════════════════════════════════════════════════════════════════════

class TestPresidentScenario:
    """본부장님 화면 시나리오."""
    
    def test_president_screen_capture(self):
        """
        본부장님 화면:
        - 함수 2/11 완료
        - SP 0/15
        - View 0/10
        - 트리거 0/5
        - 함수 1개 진행 중 (fn_total_balance)
        - 함수 1개 오류 (fn_calc_monthly_payment)
        - backend progress = 0
        
        예상 effectiveProgress:
          (2 done + 1 failed) / 41 total = 3/41 = 7.3%
        """
        # item_statuses 시뮬레이션
        item_statuses = {}
        # 함수 11개 (2 done, 1 running, 1 failed, 7 pending)
        for i, name in enumerate([
            'fn_delinq_stage', 'tvf_delinq_ranking',  # 2 done
        ]):
            item_statuses[name] = {'type': 'function', 'status': 'done'}
        item_statuses['fn_total_balance'] = {'type': 'function', 'status': 'running'}
        item_statuses['fn_calc_monthly_payment'] = {'type': 'function', 'status': 'failed'}
        for i in range(7):
            item_statuses[f'fn_pending_{i}'] = {'type': 'function', 'status': 'pending'}
        # SP 15개 모두 pending
        for i in range(15):
            item_statuses[f'sp_p_{i}'] = {'type': 'procedure', 'status': 'pending'}
        # View 10개
        for i in range(10):
            item_statuses[f'v_p_{i}'] = {'type': 'view', 'status': 'pending'}
        # Trigger 5개
        for i in range(5):
            item_statuses[f'trg_p_{i}'] = {'type': 'trigger', 'status': 'pending'}
        
        job = {
            'progress': 0,
            'item_statuses': item_statuses,
        }
        
        # safeProgress (기존) = 0 (backend 가 0)
        assert safeProgress_mirror(job) == 0, "safeProgress 는 0 이어야 (backend 그대로)"
        
        # effectiveProgress (v90.65) > 0 (객체 진행률 반영)
        eff = effectiveProgress_mirror(job)
        assert eff > 0, f"effectiveProgress 가 0 — v90.65 fix 실패: {eff}"
        
        # 약 7.3% (3/41 * 100)
        op = objectsProgress_mirror(job)
        assert op['total'] == 41, f"객체 총 41 예상, 실제: {op['total']}"
        assert op['done'] == 2, f"완료 2 예상, 실제: {op['done']}"
        assert op['failed'] == 1, f"실패 1 예상, 실제: {op['failed']}"
        
        # 7.3% 또는 그 근처
        assert 7.0 <= eff <= 8.0, f"진행률 7.3% 근처 예상, 실제: {eff}%"


class TestRegression:
    """기존 동작 영향 없음."""
    
    def test_backend_progress_50_keeps_50(self):
        """backend 가 50% 보내면 effectiveProgress 도 50."""
        job = {'progress': 50, 'item_statuses': {}}
        assert effectiveProgress_mirror(job) == 50
    
    def test_no_objects_returns_0(self):
        """객체도 없고 backend progress 도 0 이면 0."""
        job = {'progress': 0, 'item_statuses': {}}
        assert effectiveProgress_mirror(job) == 0
    
    def test_table_only_job_uses_backend_progress(self):
        """테이블만 있는 Job — backend progress 그대로."""
        job = {
            'progress': 35.5,
            'item_statuses': {
                'tbl1': {'type': 'table', 'status': 'running'},
            }
        }
        assert effectiveProgress_mirror(job) == 35.5
    
    def test_all_objects_done(self):
        """모든 객체 완료 — 100%."""
        job = {
            'progress': 0,  # backend 가 0 으로 멈춰있어도
            'item_statuses': {
                'fn_x': {'type': 'function', 'status': 'done'},
                'fn_y': {'type': 'function', 'status': 'done'},
                'sp_z': {'type': 'procedure', 'status': 'done'},
            }
        }
        assert effectiveProgress_mirror(job) == 100


class TestPatchMarkers:
    """JobMonitor.vue 의 v90.65 마커 확인."""
    
    def test_v90_65_marker(self):
        if not os.path.exists(JM_FILE):
            pytest.skip("")
        content = open(JM_FILE, encoding='utf-8').read()
        assert "v90.65" in content
    
    def test_effectiveProgress_defined(self):
        if not os.path.exists(JM_FILE):
            pytest.skip("")
        content = open(JM_FILE, encoding='utf-8').read()
        assert "const effectiveProgress" in content
    
    def test_template_uses_effectiveProgress(self):
        if not os.path.exists(JM_FILE):
            pytest.skip("")
        content = open(JM_FILE, encoding='utf-8').read()
        # KPI 카드의 progress 표시가 effectiveProgress 사용
        assert "{{ effectiveProgress }}%" in content
        assert "width:effectiveProgress" in content
    
    def test_safeProgress_preserved(self):
        """safeProgress 는 그대로 보존되어야 (다른 곳에서 사용)."""
        if not os.path.exists(JM_FILE):
            pytest.skip("")
        content = open(JM_FILE, encoding='utf-8').read()
        assert "const safeProgress" in content


if __name__ == "__main__":
    print("=== v90.65 본부장님 화면 시뮬레이션 ===\n")
    
    # 본부장님 화면 정확히 재현
    item_statuses = {}
    for name in ['fn_delinq_stage', 'tvf_delinq_ranking']:
        item_statuses[name] = {'type': 'function', 'status': 'done'}
    item_statuses['fn_total_balance'] = {'type': 'function', 'status': 'running'}
    item_statuses['fn_calc_monthly_payment'] = {'type': 'function', 'status': 'failed'}
    for i in range(7):
        item_statuses[f'fn_p_{i}'] = {'type': 'function', 'status': 'pending'}
    for i in range(15):
        item_statuses[f'sp_p_{i}'] = {'type': 'procedure', 'status': 'pending'}
    for i in range(10):
        item_statuses[f'v_p_{i}'] = {'type': 'view', 'status': 'pending'}
    for i in range(5):
        item_statuses[f'trg_p_{i}'] = {'type': 'trigger', 'status': 'pending'}
    
    job = {'progress': 0, 'item_statuses': item_statuses}
    
    print(f"Backend job.progress  = {job['progress']}")
    print(f"safeProgress (기존)    = {safeProgress_mirror(job)}%   ← KPI 가 0% 로 멈춤")
    print(f"effectiveProgress     = {effectiveProgress_mirror(job)}%  ← v90.65: 진짜 진행률")
    
    op = objectsProgress_mirror(job)
    print(f"\nobjectsProgress:")
    print(f"  total:   {op['total']}")
    print(f"  done:    {op['done']}")
    print(f"  running: {op['running']}")
    print(f"  failed:  {op['failed']}")
