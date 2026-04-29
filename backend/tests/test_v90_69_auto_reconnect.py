"""
test_v90_69_auto_reconnect.py — v90.69 (2026-04-28)

본부장님 호소: "DB 접속이 이미 접속되 있으면 상단 처리"

진단:
  connectorStore.state 가 메모리만 — 페이지 이동/새로고침 시 status='idle' 리셋
  화면 진입할 때마다 ConnectPanel 다시 떠서 또 접속 화면

v90.69 처방:
  Validate.vue:
    - _isAutoConnecting ref — 자동 재연결 시도 중 플래그
    - _autoReconnectIfPossible() — host/username/db 정보 있으면 자동 testConn
    - _disconnectAll() — 사용자가 수동 해제 (다른 DB 선택용)
    - 상단 슬림 인디케이터 (.vp-conn-status) — 연결 완료 시 호스트/DB 표시
    - 자동 재연결 중 (.vp-auto-connect) — 스피너 + 진행 메시지
"""

import os
import re
import pytest

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)


class TestValidateAutoReconnect:
    """Validate.vue 의 v90.69 자동 재연결 로직."""
    
    VAL_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "Validate.vue"
    ))
    
    def _content(self):
        if not os.path.exists(self.VAL_FILE):
            pytest.skip("")
        return open(self.VAL_FILE, encoding='utf-8').read()
    
    def test_v90_69_marker(self):
        c = self._content()
        assert "v90.69" in c
    
    def test_isAutoConnecting_ref(self):
        c = self._content()
        assert "_isAutoConnecting" in c
        # const _isAutoConnecting = ref(...) 정의 검사
        assert re.search(r"const\s+_isAutoConnecting\s*=\s*ref\(", c), \
            "const _isAutoConnecting = ref(...) 정의 누락"
    
    def test_autoReconnectIfPossible_function(self):
        c = self._content()
        assert "_autoReconnectIfPossible" in c
        # 함수 정의
        fn_idx = c.find("async function _autoReconnectIfPossible")
        assert fn_idx > 0, "_autoReconnectIfPossible 함수 정의 누락"
        fn_body = c[fn_idx:fn_idx+1500]
        # 핵심 로직
        assert "bothConnected" in fn_body, "bothConnected 체크 누락"
        assert "_hasInfo" in fn_body or "host" in fn_body, "host 체크 누락"
        assert "testConn" in fn_body, "testConn 호출 누락"
    
    def test_disconnectAll_function(self):
        c = self._content()
        assert "function _disconnectAll" in c
        fn_idx = c.find("function _disconnectAll")
        fn_body = c[fn_idx:fn_idx+300]
        assert "status = 'idle'" in fn_body, "status idle 변경 누락"
    
    def test_onMounted_calls_autoReconnect(self):
        """onMounted 가 자동 재연결 시도."""
        c = self._content()
        om_idx = c.find("onMounted(()")
        om_body = c[om_idx:om_idx+2500]
        assert "_autoReconnectIfPossible()" in om_body
    
    def test_onActivated_calls_autoReconnect(self):
        """onActivated 도 자동 재연결 시도."""
        c = self._content()
        oa_idx = c.find("onActivated(()")
        if oa_idx > 0:
            # onActivated body
            oa_body = c[oa_idx:oa_idx+800]
            assert "_autoReconnectIfPossible" in oa_body
    
    def test_connect_panel_hidden_during_auto(self):
        """자동 재연결 중에는 ConnectPanel 안 보임."""
        c = self._content()
        # ConnectPanel 의 v-if 조건에 _isAutoConnecting 포함
        assert "!_isAutoConnecting" in c, \
            "ConnectPanel v-if 에 _isAutoConnecting 회피 없음"
    
    def test_auto_connect_template(self):
        """자동 재연결 중 표시 (vp-auto-connect)."""
        c = self._content()
        assert 'class="vp-auto-connect"' in c
        assert 'class="vp-auto-spinner"' in c
        assert 'v-if="_isAutoConnecting"' in c
    
    def test_conn_status_template(self):
        """연결 완료 시 슬림 인디케이터."""
        c = self._content()
        assert 'class="vp-conn-status"' in c
        assert 'v-if="connector.bothConnected' in c
        # 호스트/DB 표시
        assert "connector.source.host" in c
        assert "connector.target.host" in c
    
    def test_disconnect_button(self):
        """해제 버튼."""
        c = self._content()
        assert 'class="vp-conn-disc"' in c
        assert '@click="_disconnectAll"' in c
    
    def test_auto_connect_css(self):
        """vp-auto-connect / vp-conn-status CSS 정의."""
        c = self._content()
        assert ".vp-auto-connect" in c
        assert ".vp-auto-spinner" in c
        assert ".vp-conn-status" in c
        assert ".vp-conn-dot" in c
        assert "@keyframes vp-conn-pulse" in c


class TestSimulation:
    """자동 재연결 흐름 시뮬레이션."""
    
    def reconnect_flow(self, src_status, tgt_status, src_has_info, tgt_has_info):
        """v90.69 의 _autoReconnectIfPossible 미러."""
        if src_status == 'ok' and tgt_status == 'ok':
            return 'already_connected'
        if not src_has_info or not tgt_has_info:
            return 'skip_no_info'
        if src_status == 'testing' or tgt_status == 'testing':
            return 'skip_in_progress'
        return 'try_reconnect'
    
    def test_already_connected_skip(self):
        result = self.reconnect_flow('ok', 'ok', True, True)
        assert result == 'already_connected'
    
    def test_no_info_skip(self):
        result = self.reconnect_flow('idle', 'idle', False, True)
        assert result == 'skip_no_info'
    
    def test_in_progress_skip(self):
        result = self.reconnect_flow('testing', 'idle', True, True)
        assert result == 'skip_in_progress'
    
    def test_idle_with_info_try(self):
        """페이지 재진입 후 — host 정보 있으면 자동 시도."""
        result = self.reconnect_flow('idle', 'idle', True, True)
        assert result == 'try_reconnect'
    
    def test_error_state_retry(self):
        """이전 시도 실패 (error 상태) — 재시도."""
        result = self.reconnect_flow('error', 'error', True, True)
        assert result == 'try_reconnect'


if __name__ == "__main__":
    print("=== v90.69 페이지 진입 시나리오 ===\n")
    
    test = TestSimulation()
    
    cases = [
        ("처음 진입, host 정보 없음",      'idle',    'idle',    False, False),
        ("페이지 재진입, host 정보 있음",  'idle',    'idle',    True,  True),
        ("이미 연결된 상태",                'ok',      'ok',      True,  True),
        ("이전 시도 실패, 재시도",          'error',   'error',   True,  True),
        ("연결 시도 중 재호출",             'testing', 'idle',    True,  True),
    ]
    
    for name, src_s, tgt_s, src_i, tgt_i in cases:
        result = test.reconnect_flow(src_s, tgt_s, src_i, tgt_i)
        emoji = {'already_connected':'✓', 'skip_no_info':'⏸', 'skip_in_progress':'⏸', 'try_reconnect':'🔄'}[result]
        print(f"  {emoji} {name:28s} → {result}")
