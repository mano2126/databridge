"""
test_v90_72_remove_duplicate_indicator.py — v90.72 (2026-04-28)

본부장님 호소: "MSSQL127.0.0.1/testdbMYSQL127.0.0.1/testdb해제 이 정보는 중복이라 없애는게 좋겠어."

진단:
  v90.69 에서 추가한 vp-conn-status 슬림 인디케이터 (.vp-conn-host 표시) 가
  PageHeader 의 src-db/tgt-db 표시와 정확히 동일한 정보 표시 → 중복.

v90.72 처방:
  - vp-conn-status 영역 (template) 제거
  - vp-conn-* CSS 클래스 모두 제거
  - _disconnectAll 함수 제거 (dead code, 호출처 없음)
  - _autoReconnectIfPossible 보존 (자동 재연결 동작 유지)
  - PageHeader 의 src-db/tgt-db 표시는 그대로 (이미 표시 중)
"""

import os
import re
import pytest


_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)


class TestDuplicateIndicatorRemoved:
    """vp-conn-status 중복 인디케이터 제거 검증."""
    
    VAL_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "Validate.vue"
    ))
    
    def _content(self):
        if not os.path.exists(self.VAL_FILE):
            pytest.skip("")
        return open(self.VAL_FILE, encoding='utf-8').read()
    
    def test_v90_72_marker(self):
        c = self._content()
        assert "v90.72" in c
    
    def test_template_indicator_removed(self):
        """vp-conn-status div 영역 제거 (주석만 남음)."""
        c = self._content()
        # template 안에 <div class="vp-conn-status"> 없어야
        assert '<div v-if="connector.bothConnected && !migratingNow" class="vp-conn-status">' not in c
        assert '<span class="vp-conn-dot"></span>' not in c
        assert '<button class="vp-conn-disc"' not in c
    
    def test_css_classes_removed(self):
        """vp-conn-* CSS 클래스 정의 제거."""
        c = self._content()
        forbidden_css = [
            '.vp-conn-status {',
            '.vp-conn-dot {',
            '.vp-conn-text ',
            '.vp-conn-host ',
            '.vp-conn-disc',
            '@keyframes vp-conn-pulse',
        ]
        violations = [css for css in forbidden_css if css in c]
        assert not violations, f"v90.69 vp-conn-* CSS 클래스 잔존: {violations}"
    
    def test_disconnectAll_removed(self):
        """_disconnectAll dead code 제거."""
        c = self._content()
        # 함수 정의 없음 (주석은 OK)
        assert "function _disconnectAll" not in c
    
    def test_autoReconnect_preserved(self):
        """v90.69 의 자동 재연결 기능은 보존."""
        c = self._content()
        assert "_autoReconnectIfPossible" in c
        assert "_isAutoConnecting" in c
        # 함수 정의 보존
        assert "async function _autoReconnectIfPossible" in c
        # onMounted 에서 호출 보존
        assert "_autoReconnectIfPossible()" in c
    
    def test_page_header_db_display_intact(self):
        """PageHeader 의 src-db/tgt-db 표시 그대로 (사용자가 보는 정보)."""
        c = self._content()
        # PageHeader 호출이 있어야
        assert ":show-db=\"true\"" in c
        assert ":src-db=\"connector.source\"" in c
        assert ":tgt-db=\"connector.target\"" in c
    
    def test_auto_connect_status_preserved(self):
        """자동 재연결 중 표시 (vp-auto-connect) 는 보존 — 다른 기능."""
        c = self._content()
        # vp-auto-connect (자동 재연결 진행 중) 그대로
        assert 'class="vp-auto-connect"' in c
        assert '.vp-auto-connect ' in c or '.vp-auto-connect{' in c
    
    def test_connect_panel_logic_intact(self):
        """ConnectPanel v-if 조건 그대로 (자동 재연결 회피)."""
        c = self._content()
        assert "!connector.bothConnected && !_isAutoConnecting" in c


class TestIntegrationFlow:
    """v90.69 자동 재연결 + v90.72 중복 제거의 통합 동작."""
    
    def determine_ui_state(self, both_connected, is_auto_connecting, migrating):
        """
        v90.72 후의 UI 표시 결정 로직 미러:
          - 자동 재연결 중 → vp-auto-connect (스피너 + 메시지)
          - 미연결 + 자동 재연결 아님 → ConnectPanel
          - 연결 완료 → PageHeader 만 (vp-conn-status 제거됨)
        """
        if is_auto_connecting:
            return "vp-auto-connect"
        if not both_connected:
            return "ConnectPanel"
        if migrating:
            return "vp-migrating-warn + PageHeader"
        return "PageHeader_only"
    
    def test_first_visit_shows_connect_panel(self):
        """처음 진입, 정보 없음 → ConnectPanel."""
        result = self.determine_ui_state(False, False, False)
        assert result == "ConnectPanel"
    
    def test_auto_reconnecting_shows_spinner(self):
        """자동 재연결 중 → 스피너만 (ConnectPanel 안 보임)."""
        result = self.determine_ui_state(False, True, False)
        assert result == "vp-auto-connect"
    
    def test_connected_shows_only_page_header(self):
        """연결 완료 → PageHeader 만 (중복 인디케이터 없음)."""
        result = self.determine_ui_state(True, False, False)
        assert result == "PageHeader_only", \
            f"연결 완료 시 PageHeader 만 보여야 하는데 다른 게 표시됨: {result}"
    
    def test_migrating_shows_warning(self):
        """이관 중 → 경고 + PageHeader (중복 인디케이터 없음)."""
        result = self.determine_ui_state(True, False, True)
        assert "PageHeader" in result
        assert "vp-migrating-warn" in result


if __name__ == "__main__":
    print("=== v90.72 중복 인디케이터 제거 검증 ===\n")
    
    test = TestIntegrationFlow()
    
    cases = [
        ("처음 진입, 미연결",                False, False, False),
        ("자동 재연결 중",                   False, True,  False),
        ("연결 완료, 일반 상태",             True,  False, False),
        ("연결 완료, 이관 중",               True,  False, True),
    ]
    
    for name, conn, auto, mig in cases:
        result = test.determine_ui_state(conn, auto, mig)
        print(f"  ✓ {name:30s} → {result}")
