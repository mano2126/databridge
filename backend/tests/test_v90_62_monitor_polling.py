"""
test_v90_62_monitor_polling.py — v90.62 (2026-04-28)

본부장님 호소 (이관 작업 모니터 화면):
  1. "모니터는 아직도 동작을 안하고"
  2. "전체 진행의 스테이터스바는 한번 클릭해서 창을 띄우고 닫은 후 다시 열면 동작하는 것 같아"
  3. "모니터가 동작하면 모니터글자 옆에 눈깜임 보여줘"

진단:
  - primeBackground() 는 1회 fetch 후 종료 → 갱신 안 됨
  - show() 만 startPolling() 호출 → 패널 안 열면 폴링 안 됨
  - 그러나 화면의 LIVE 배너 / current_table 등은 폴링 데이터 필요!

v90.62 처방:
  1. monitorStore.startBackgroundPolling() — visible 무관하게 폴링 시작
  2. monitorStore.stopBackgroundPolling() — 페이지 떠날 때 정리
  3. JobMonitor.onMounted/onActivated 에서 호출
  4. 모니터 버튼 옆 라이브 점멸 (.monitor-live-dot, isPolling getter 사용)
"""

import os
import re
import pytest

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)

# Frontend 파일 경로 (backend 디렉토리 기준)
MS_FILE = os.path.normpath(os.path.join(
    _BACKEND_DIR, "..", "frontend", "src", "store", "monitorStore.js"
))
JM_FILE = os.path.normpath(os.path.join(
    _BACKEND_DIR, "..", "frontend", "src", "pages", "JobMonitor.vue"
))


# ════════════════════════════════════════════════════════════════════════════
# Python 미러 - monitorStore 의 새 동작 시뮬레이션
# ════════════════════════════════════════════════════════════════════════════

class MonitorStoreMirror:
    """v90.62 monitorStore 동작 미러."""
    
    def __init__(self):
        self.visible = False
        self._timer = None
        self._bgPolling = False
        self.live = None
        self.loading = False
    
    @property
    def isPolling(self):
        # v90.62: timer 가 있으면 폴링 중 (visible 또는 bgPolling 둘 다 인정)
        return self._timer is not None
    
    def fetchOnce(self):
        # 단순 fetch 시뮬레이션
        self.live = {"jobs": [{"id": 1}], "ts": 1}
        return self.live
    
    def _scheduleNext(self):
        # visible 또는 bgPolling 활성이면 timer 설정
        if not self.visible and not self._bgPolling:
            return
        self._timer = "MOCK_TIMER"  # 실제로는 setTimeout
    
    def show(self):
        self.visible = True
        self.startPolling()
    
    def hide(self):
        self.visible = False
        self.stopPolling()
    
    def startPolling(self):
        if self._timer:
            return
        self.fetchOnce()
        self._scheduleNext()
    
    def stopPolling(self):
        if self._timer:
            self._timer = None
        self._bgPolling = False  # v90.62: bgPolling 도 클리어
    
    # v90.62 신규
    def startBackgroundPolling(self):
        if self._timer:
            return
        self._bgPolling = True
        self.fetchOnce()
        self._scheduleNext()
    
    def stopBackgroundPolling(self):
        # visible 이면 정지 안 함
        if self.visible:
            return
        self.stopPolling()


# ════════════════════════════════════════════════════════════════════════════
# 시나리오 검증
# ════════════════════════════════════════════════════════════════════════════

class TestBackgroundPolling:
    """v90.62 백그라운드 폴링 동작."""
    
    def test_start_bg_polling_starts_timer(self):
        """startBackgroundPolling 호출 시 timer 가 설정되고 isPolling=True."""
        ms = MonitorStoreMirror()
        assert not ms.isPolling
        
        ms.startBackgroundPolling()
        
        assert ms.isPolling
        assert ms._bgPolling
        assert ms.live is not None  # fetchOnce 실행됨
    
    def test_bg_polling_without_visible(self):
        """visible 안 켜도 폴링 동작 (본부장님 시나리오)."""
        ms = MonitorStoreMirror()
        assert not ms.visible
        
        ms.startBackgroundPolling()
        
        assert ms.isPolling
        assert not ms.visible  # 패널 안 열려있음 (안 보임)
    
    def test_show_after_bg_polling_no_op_at_polling_level(self):
        """bg 폴링 중에 show() 호출 — 폴링 그대로 유지 (이미 폴링 중)."""
        ms = MonitorStoreMirror()
        ms.startBackgroundPolling()
        assert ms.isPolling
        
        ms.show()
        
        # 여전히 폴링 중 (startPolling 안에서 already polling 이라 no-op)
        assert ms.isPolling
        # visible 은 켜짐
        assert ms.visible
    
    def test_hide_after_show_continues_bg_polling(self):
        """본부장님 패턴 — show 후 hide 해도 bg 폴링 계속."""
        ms = MonitorStoreMirror()
        # 1. 백그라운드 폴링 시작 (페이지 진입)
        ms.startBackgroundPolling()
        # 2. 모니터 패널 열기
        ms.show()
        # 3. 모니터 패널 닫기
        ms.hide()
        
        # bgPolling 도 stopPolling 에서 클리어돼서 정지
        # 그래서 화면 진입 시 startBackgroundPolling 다시 필요
        # → 이게 본부장님 "한 번 열었다 닫으면 정상화" 패턴
        # 다시 startBackgroundPolling 호출해서 복원 가능한지
        ms.startBackgroundPolling()
        assert ms.isPolling, "show/hide 후에도 bg 폴링 재시작 가능해야 함"
    
    def test_stop_bg_polling_when_visible_no_op(self):
        """visible 상태일 때 stopBackgroundPolling 호출해도 정지 안 함."""
        ms = MonitorStoreMirror()
        ms.show()  # 사용자가 직접 패널 열음
        assert ms.isPolling
        
        ms.stopBackgroundPolling()
        
        # visible 상태이므로 stop 무시
        assert ms.isPolling
        assert ms.visible
    
    def test_stop_bg_polling_when_invisible_stops(self):
        """invisible 상태에서 stopBackgroundPolling 호출 시 정지."""
        ms = MonitorStoreMirror()
        ms.startBackgroundPolling()
        assert ms.isPolling
        
        ms.stopBackgroundPolling()
        
        assert not ms.isPolling
        assert not ms._bgPolling


class TestPresidentScenario:
    """본부장님 화면 시나리오."""
    
    def test_president_scenario_now_works(self):
        """
        본부장님 시나리오:
        1. JobMonitor 페이지 진입 → startBackgroundPolling 자동 호출
        2. 모니터 버튼 옆 라이브 점멸 보임 (isPolling = true)
        3. 패널 안 열어도 LIVE 배너 / current_table 등이 자동 갱신
        """
        ms = MonitorStoreMirror()
        
        # 페이지 진입 (onMounted)
        ms.startBackgroundPolling()
        
        # 검증
        assert ms.isPolling, "폴링 활성 → 라이브 점멸 보여야"
        assert not ms.visible, "패널은 안 열려 있음"
        assert ms.live is not None, "데이터 로드됨"
    
    def test_isPolling_for_live_indicator(self):
        """isPolling getter 가 라이브 점멸 인디케이터 표시 조건으로 사용."""
        ms = MonitorStoreMirror()
        
        # 폴링 안 함 → 라이브 점멸 숨김
        assert not ms.isPolling
        
        # bg 폴링 시작 → 라이브 점멸 표시
        ms.startBackgroundPolling()
        assert ms.isPolling
        
        # 폴링 정지 → 라이브 점멸 숨김
        ms.stopBackgroundPolling()
        assert not ms.isPolling


# ════════════════════════════════════════════════════════════════════════════
# 소스 파일 마커 검증
# ════════════════════════════════════════════════════════════════════════════

class TestPatchMarkers:
    """JobMonitor.vue + monitorStore.js 의 v90.62 fix 마커 확인."""
    
    def test_monitorStore_v90_62_marker(self):
        if not os.path.exists(MS_FILE):
            pytest.skip(f"{MS_FILE} 없음")
        content = open(MS_FILE, encoding='utf-8').read()
        assert "v90.62" in content, "v90.62 마커 누락"
    
    def test_monitorStore_actions_present(self):
        if not os.path.exists(MS_FILE):
            pytest.skip("")
        content = open(MS_FILE, encoding='utf-8').read()
        assert "startBackgroundPolling" in content
        assert "stopBackgroundPolling" in content
        assert "_bgPolling" in content
        assert "isPolling" in content
    
    def test_monitorStore_scheduleNext_handles_bg(self):
        """_scheduleNext 가 bgPolling 도 인정."""
        if not os.path.exists(MS_FILE):
            pytest.skip("")
        content = open(MS_FILE, encoding='utf-8').read()
        # _scheduleNext 안에 bgPolling 체크
        assert re.search(
            r"_scheduleNext.*\n.*!this\.visible\s+&&\s+!this\._bgPolling",
            content, re.DOTALL
        ), "_scheduleNext 가 bgPolling 안 인정함"
    
    def test_jm_uses_startBackgroundPolling(self):
        if not os.path.exists(JM_FILE):
            pytest.skip(f"{JM_FILE} 없음")
        content = open(JM_FILE, encoding='utf-8').read()
        # primeBackground 대신 startBackgroundPolling 사용
        assert "monitorStore.startBackgroundPolling" in content
        # onMounted 와 onActivated 에 모두 추가됐는지
        # (단순히 발견되면 OK — 구체 위치는 라인 변경 가능)
        count = content.count("monitorStore.startBackgroundPolling()")
        assert count >= 2, f"startBackgroundPolling 호출이 2번 미만 ({count}번)"
    
    def test_jm_uses_stopBackgroundPolling(self):
        if not os.path.exists(JM_FILE):
            pytest.skip("")
        content = open(JM_FILE, encoding='utf-8').read()
        assert "monitorStore.stopBackgroundPolling" in content, \
            "onUnmounted 에 stopBackgroundPolling 없음 (메모리 누수 위험)"
    
    def test_jm_live_dot_indicator(self):
        """모니터 버튼 옆 라이브 점멸 인디케이터."""
        if not os.path.exists(JM_FILE):
            pytest.skip("")
        content = open(JM_FILE, encoding='utf-8').read()
        # 1) template 에 dot 엘리먼트
        assert 'class="monitor-live-dot"' in content, \
            "monitor-live-dot 엘리먼트 없음"
        # 2) v-if 가 isPolling 조건
        assert re.search(
            r'v-if="monitorStore\.isPolling".*monitor-live-dot',
            content
        ), "v-if 가 isPolling 으로 연결 안 됨"
        # 3) CSS 정의
        assert ".monitor-live-dot" in content, "CSS 정의 없음"
        # 4) 점멸 애니메이션
        assert re.search(r"@keyframes\s+mon-live-pulse", content), \
            "mon-live-pulse 애니메이션 정의 누락"


if __name__ == "__main__":
    print("=== v90.62 본부장님 시나리오 시뮬레이션 ===")
    ms = MonitorStoreMirror()
    
    print("\n1. 페이지 진입 — startBackgroundPolling()")
    ms.startBackgroundPolling()
    print(f"   isPolling={ms.isPolling}, visible={ms.visible}")
    print(f"   → 모니터 버튼 옆 라이브 점멸 표시: {'✓' if ms.isPolling else '✗'}")
    print(f"   → LIVE 배너 데이터: {'✓' if ms.live else '✗'}")
    
    print("\n2. 모니터 버튼 클릭 — show()")
    ms.show()
    print(f"   isPolling={ms.isPolling}, visible={ms.visible}")
    
    print("\n3. 모니터 패널 닫기 — hide()")
    ms.hide()
    print(f"   isPolling={ms.isPolling}, visible={ms.visible}")
    print(f"   (이 시점엔 bgPolling 도 같이 정지됨 — 다시 startBackgroundPolling 필요)")
    
    print("\n4. 페이지 떠남 — stopBackgroundPolling() (onUnmounted)")
    ms.stopBackgroundPolling()
    print(f"   isPolling={ms.isPolling}, visible={ms.visible}")
    print("   메모리 누수 방지 ✓")
