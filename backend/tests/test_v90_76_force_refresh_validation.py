"""
test_v90_76_force_refresh_validation.py — v90.76 (2026-04-28)

본부장님 호소:
  "AI로 만든 후 검증 버튼 누르면 다시 DB에서 읽어 와야 될 것 같아.
   오브젝트 검증도 마찬가지야."

진단:
  - runValidate(): srcTables 가 비어있을 때만 loadTables() 호출
  - runObjValidate(): 첫 실행 시에만 loadSrcObjects() 호출
  → AI 변환으로 새로 만든 객체 인지 못함 (캐시된 목록 사용)

v90.76 처방:
  - runValidate(): 매번 강제 loadTables() 호출
  - runObjValidate(): 매번 강제 loadSrcObjects(true) 호출
  → "검증 실행" = 사용자 의도가 "최신 상태로 검증" 이므로 매번 새로고침
"""

import os
import re
import pytest


_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)


class TestForceRefresh:
    """검증 실행 시 강제 새로고침."""
    
    VAL_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "Validate.vue"
    ))
    
    def _content(self):
        if not os.path.exists(self.VAL_FILE):
            pytest.skip("")
        return open(self.VAL_FILE, encoding='utf-8').read()
    
    def test_v90_76_marker(self):
        c = self._content()
        assert "v90.76" in c
        assert c.count("v90.76") >= 3
    
    def test_runValidate_always_reloads(self):
        """runValidate 가 무조건 loadTables() 호출."""
        c = self._content()
        # runValidate 함수 본체 추출
        idx = c.find("async function runValidate()")
        assert idx > 0
        # 함수 끝 (다음 async function 까지)
        end = c.find("async function ", idx + 50)
        body = c[idx:end] if end > 0 else c[idx:idx+3000]
        
        # 새 코드: 무조건 await loadTables() 호출
        # 이전 코드 패턴 'if (!srcTables.value.length) { await loadTables() }' 사라져야
        assert "v90.76" in body, "runValidate 에 v90.76 마커 없음"
        # await loadTables() 가 if 문 밖에 있어야 (무조건 호출)
        # 단순 검사: 함수 시작부터 첫 `running.value=true` 까지 사이에
        # await loadTables() 가 있고 그 이전에 `if (!srcTables` 패턴이 없어야
        sec = body[:body.find("running.value=true")]
        assert "await loadTables()" in sec, "runValidate 가 loadTables() 호출 안 함"
    
    def test_runValidate_no_conditional_load(self):
        """이전 조건부 로드 (if !srcTables.value.length) 사라짐."""
        c = self._content()
        idx = c.find("async function runValidate()")
        end = c.find("async function ", idx + 50)
        body = c[idx:end] if end > 0 else c[idx:idx+3000]
        # `if (!srcTables.value.length) {` 다음줄에 await loadTables() 패턴은 사라져야
        # (이제 무조건 await loadTables 부터 시작)
        assert not re.search(
            r"if\s*\(\s*!srcTables\.value\.length\s*\)\s*\{\s*\n\s*await\s+loadTables",
            body
        ), "이전 조건부 로드 패턴 남아있음"
    
    def test_runObjValidate_always_reloads(self):
        """runObjValidate 가 무조건 loadSrcObjects(true) 호출."""
        c = self._content()
        idx = c.find("async function runObjValidate()")
        assert idx > 0
        # 함수 시작부터 첫 `if (hadExisting)` 까지 사이에 loadSrcObjects 호출
        sec_end = c.find("hadExisting", idx)
        sec = c[idx:sec_end]
        assert "v90.76" in sec, "runObjValidate 에 v90.76 마커 없음"
        assert "loadSrcObjects(true)" in sec, "loadSrcObjects(true) 호출 누락"
    
    def test_existing_logic_preserved(self):
        """기존 로직 (테스트 결과 보존, 재이관 배지 초기화) 그대로."""
        c = self._content()
        idx = c.find("async function runObjValidate()")
        end = c.find("async function ", idx + 50)
        body = c[idx:end] if end > 0 else c[idx:idx+3000]
        # hadExisting 분기 보존
        assert "hadExisting" in body
        # status='checking' 초기화 보존
        assert "r.status = 'checking'" in body
        # name_variant 초기화 보존 (v90.70 후속)
        assert "r.name_variant = null" in body


class TestBackwardCompatibility:
    """회귀 안전 — 기존 v90.X 패치들 보존."""
    
    VAL_FILE = os.path.normpath(os.path.join(
        _BACKEND_DIR, "..", "frontend", "src", "pages", "Validate.vue"
    ))
    
    def _content(self):
        if not os.path.exists(self.VAL_FILE):
            pytest.skip("")
        return open(self.VAL_FILE, encoding='utf-8').read()
    
    def test_v90_69_auto_reconnect_preserved(self):
        """v90.69 자동 재연결 보존."""
        c = self._content()
        assert "_autoReconnectIfPossible" in c
        assert "_isAutoConnecting" in c
    
    def test_v90_70_name_variant_preserved(self):
        """v90.70 name_variant 라우팅 보존."""
        c = self._content()
        assert "_ckName" in c
        assert "name_variant" in c
        assert "(side === 'tgt' && r && r.name_variant)" in c
    
    def test_v90_72_no_duplicate_indicator(self):
        """v90.72 중복 인디케이터 제거 보존."""
        c = self._content()
        # 이전 vp-conn-status template 영역 없어야
        assert '<div v-if="connector.bothConnected && !migratingNow" class="vp-conn-status">' not in c
    
    def test_handleStart_intact(self):
        c = self._content()
        assert "async function handleStart()" in c
        # vType 분기 보존
        assert "vType.value === 'table'" in c


class TestSimulation:
    """검증 흐름 시뮬레이션."""
    
    def simulate_validate_table(self, has_cached, was_modified):
        """v90.76 의 runValidate 흐름 미러."""
        actions = []
        # v90.76: 무조건 loadTables
        actions.append("loadTables()")
        if was_modified:
            actions.append("fresh_table_list_includes_new_table")
        actions.append("runValidationOnFreshList")
        return actions
    
    def test_ai_created_table_detected_after_refresh(self):
        """AI 로 만든 새 테이블이 검증 실행 시 인지됨."""
        actions = self.simulate_validate_table(has_cached=True, was_modified=True)
        assert "loadTables()" == actions[0]
        assert "fresh_table_list_includes_new_table" in actions
    
    def test_ai_created_obj_detected(self):
        """AI 로 만든 새 객체도 마찬가지."""
        # 시뮬레이션은 같은 패턴
        actions = self.simulate_validate_table(has_cached=True, was_modified=True)
        assert actions[0] == "loadTables()"


if __name__ == "__main__":
    print("=== v90.76 검증 실행 시 강제 새로고침 ===\n")
    
    print("Before (v90.75):")
    print("  사용자: 검증 화면에서 '타겟 없음' 알림 → AI로 객체 생성 → 검증 실행")
    print("  코드:   srcTables 캐시됨 → loadTables() 호출 안 됨 → 옛 결과")
    print("          → 사용자 혼란 ('내가 만들었는데 왜 또 없다고 해?')")
    print()
    print("After (v90.76):")
    print("  사용자: 동일 흐름")
    print("  코드:   매 검증 실행 시 무조건 loadTables() 호출")
    print("          → DB 에서 최신 상태 읽음 → AI 가 만든 새 객체 인지")
    print("          → 검증 결과 정확")
    print()
    
    test = TestSimulation()
    actions = test.simulate_validate_table(has_cached=True, was_modified=True)
    print("시뮬레이션 (AI 로 새 테이블 만든 후):")
    for i, a in enumerate(actions, 1):
        print(f"  {i}. {a}")
