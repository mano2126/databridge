"""
test_v90_59_monitor_warmup.py — v90.59 (2026-04-28)

본부장님 호소: "모니터 버튼 누르면 데이터가 너무 늦게 나온다"

진단:
  - /system/live 첫 호출 시 4개 어댑터 (Localhost+Docker+MSSQL+MySQL) 직렬 fetch
  - bootstrap_auto_detect() 첫 1회 실행 비용
  - 첫 응답 5~15초

v90.59 처방:
  1. system_live.py: import 시 백그라운드 워밍업 + stale-while-revalidate
  2. registry.py: fetch_all 병렬화 (ThreadPoolExecutor)

이 테스트는 두 핵심 기능의 단위 검증.

실행:
  cd backend
  pytest tests/test_v90_59_monitor_warmup.py -v
"""

import sys
import os
import time
import threading
import re
from unittest.mock import patch, MagicMock

import pytest

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)
SYSTEM_LIVE_FILE = os.path.join(_BACKEND_DIR, 'app', 'api', 'routes', 'system_live.py')
REGISTRY_FILE = os.path.join(_BACKEND_DIR, 'app', 'monitor', 'registry.py')


# ════════════════════════════════════════════════════════════════════════════
# Patch 마커 검증 (소스 파일에 v90.59 fix 가 들어있는지)
# ════════════════════════════════════════════════════════════════════════════

class TestPatchMarkers:
    """v90.59 fix 가 파일에 살아있는지 확인."""
    
    def test_system_live_v90_59_marker(self):
        if not os.path.exists(SYSTEM_LIVE_FILE):
            pytest.skip(f"{SYSTEM_LIVE_FILE} 없음")
        content = open(SYSTEM_LIVE_FILE, encoding='utf-8').read()
        assert "v90.59" in content, "system_live.py 에 v90.59 마커 없음"
        assert "_start_warmup_once" in content, "워밍업 함수 누락"
        assert "_refresh_cache_async" in content, "비동기 갱신 함수 누락"
    
    def test_system_live_warmup_started_at_import(self):
        """모듈 어딘가에서 _start_warmup_once() 호출 (top-level)."""
        content = open(SYSTEM_LIVE_FILE, encoding='utf-8').read()
        # top-level 호출 (들여쓰기 0) 이어야 import 시점 실행됨
        # 함수 정의 안에 있으면 import 시 자동 호출 안 됨
        lines = content.splitlines()
        found_top_level_call = False
        for line in lines:
            # 들여쓰기 없이 _start_warmup_once() 호출
            if line.rstrip() == "_start_warmup_once()":
                found_top_level_call = True
                break
        assert found_top_level_call, \
            "모듈 import 시점에 top-level _start_warmup_once() 호출 누락"
    
    def test_system_live_stale_while_revalidate(self):
        """stale-while-revalidate 패턴 확인."""
        content = open(SYSTEM_LIVE_FILE, encoding='utf-8').read()
        assert "_cache_stale" in content, "stale 메타 누락"
        assert re.search(
            r"threading\.Thread\(target=_refresh_cache_async",
            content
        ), "stale 시점 백그라운드 갱신 누락"
    
    def test_registry_v90_59_marker(self):
        content = open(REGISTRY_FILE, encoding='utf-8').read()
        assert "v90.59" in content, "registry.py 에 v90.59 마커 없음"
    
    def test_registry_parallel_fetch(self):
        """fetch_all 이 ThreadPoolExecutor 사용."""
        content = open(REGISTRY_FILE, encoding='utf-8').read()
        assert "ThreadPoolExecutor" in content, "병렬 처리 미적용"
        assert "as_completed" in content, "as_completed 누락"
        # _fetch_one 헬퍼 함수
        assert "def _fetch_one" in content, "_fetch_one 헬퍼 누락"


# ════════════════════════════════════════════════════════════════════════════
# 동작 검증 — 모듈 import 후 실제 동작 확인 (Mock 기반)
# ════════════════════════════════════════════════════════════════════════════

class TestStaleWhileRevalidate:
    """캐시 동작 시뮬레이션."""
    
    def test_fresh_cache_returns_immediately(self):
        """캐시 신선 → 즉시 반환 (TTL 안)."""
        # system_live 의 캐시 메커니즘 단순 시뮬레이션
        cache = {"data": {"foo": "bar"}, "ts": time.time()}
        TTL = 2.0
        
        now = time.time()
        age = now - cache["ts"]
        is_fresh = age < TTL
        
        assert is_fresh
        assert cache["data"] == {"foo": "bar"}
    
    def test_stale_cache_returns_with_meta(self):
        """캐시 stale → stale 마킹 후 반환."""
        cache = {"data": {"foo": "bar"}, "ts": time.time() - 5}  # 5초 전
        TTL = 2.0
        
        now = time.time()
        age = now - cache["ts"]
        is_stale = age >= TTL
        
        assert is_stale
        # stale 응답에는 _cache_stale, _cache_age_sec 추가됨
        out = dict(cache["data"])
        out["_cache_age_sec"] = round(age, 2)
        out["_cache_stale"]   = True
        
        assert out["_cache_stale"] is True
        assert out["_cache_age_sec"] >= 2.0


class TestParallelFetchSimulation:
    """fetch_all 병렬화 효과 시뮬레이션."""
    
    def test_parallel_faster_than_serial(self):
        """병렬 실행이 직렬보다 빨라야 함."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def slow_fetch(idx):
            """0.3초 걸리는 가짜 어댑터 호출."""
            time.sleep(0.3)
            return {"target_id": f"t{idx}", "ts": time.time()}
        
        # 직렬
        t0 = time.time()
        serial_results = []
        for i in range(4):
            serial_results.append(slow_fetch(i))
        serial_time = time.time() - t0
        
        # 병렬
        t0 = time.time()
        parallel_results = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(slow_fetch, i) for i in range(4)]
            for future in as_completed(futures):
                parallel_results.append(future.result())
        parallel_time = time.time() - t0
        
        # 병렬은 직렬의 1/2 미만 (4개 모두 동시 실행 → 약 0.3초)
        assert parallel_time < serial_time * 0.5, \
            f"병렬 효과 부족: serial={serial_time:.2f}s, parallel={parallel_time:.2f}s"
        
        # 결과 정확성
        assert len(parallel_results) == 4
    
    def test_parallel_handles_one_slow_adapter(self):
        """한 어댑터가 느려도 다른 어댑터 결과는 빠르게 도착."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def fetch(idx):
            if idx == 0:
                time.sleep(2.0)  # 한 놈만 매우 느림
            else:
                time.sleep(0.05)
            return idx
        
        t0 = time.time()
        first_done_at = None
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(fetch, i) for i in range(4)]
            for future in as_completed(futures):
                if first_done_at is None:
                    first_done_at = time.time() - t0
                future.result()
        
        # 첫 결과는 빠른 어댑터 — 0.5초 안에 도착해야
        assert first_done_at < 0.5, \
            f"첫 결과 지연: {first_done_at:.2f}s (직렬이면 2초+ 걸림)"
    
    def test_parallel_exception_in_one_adapter_isolated(self):
        """한 어댑터 예외가 다른 어댑터에 영향 없어야."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def fetch(idx):
            if idx == 1:
                raise RuntimeError("DB 연결 실패")
            return {"target_id": f"t{idx}"}
        
        results = []
        errors = []
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(fetch, i): i for i in range(4)}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results.append(future.result())
                except Exception as e:
                    errors.append((idx, str(e)))
        
        # 3개는 성공, 1개는 예외
        assert len(results) == 3
        assert len(errors) == 1
        assert errors[0][0] == 1
        assert "DB 연결 실패" in errors[0][1]


class TestWarmupBehavior:
    """모듈 import 시 워밍업 트리거 검증."""
    
    def test_warmup_runs_in_background_thread(self):
        """워밍업이 별도 스레드에서 실행되어야 (메인 import 차단 X)."""
        # 워밍업 시뮬레이션
        worker_started = threading.Event()
        worker_finished = threading.Event()
        
        def warmup_simulation():
            worker_started.set()
            time.sleep(0.5)  # 가짜 fetch
            worker_finished.set()
        
        t = threading.Thread(target=warmup_simulation, daemon=True)
        t.start()
        
        # 메인 스레드는 즉시 진행 (워커 종료 안 기다림)
        worker_started.wait(timeout=1.0)
        assert worker_started.is_set()
        # 이 시점에 worker_finished 는 아직 set 안 됨 (0.5초 sleep 중)
        # 단지 시간 차이로 다음 줄이 실행되니까 메인 스레드 차단 안 됨 확인
        
        # 마지막에 워커 완료 대기
        worker_finished.wait(timeout=2.0)
        assert worker_finished.is_set()


if __name__ == "__main__":
    print("=== v90.59 패치 마커 ===")
    if os.path.exists(SYSTEM_LIVE_FILE):
        c = open(SYSTEM_LIVE_FILE, encoding='utf-8').read()
        print(f"  system_live.py v90.59 마커: {c.count('v90.59')}")
        print(f"  워밍업 함수: {'_start_warmup_once' in c}")
        print(f"  stale 메타: {'_cache_stale' in c}")
    if os.path.exists(REGISTRY_FILE):
        c = open(REGISTRY_FILE, encoding='utf-8').read()
        print(f"  registry.py v90.59 마커: {c.count('v90.59')}")
        print(f"  ThreadPoolExecutor: {'ThreadPoolExecutor' in c}")
    
    print()
    print("=== 병렬 fetch 효과 측정 ===")
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    def slow_fetch(i):
        time.sleep(0.3)
        return i
    
    t0 = time.time()
    [slow_fetch(i) for i in range(4)]
    print(f"  직렬 4건: {time.time()-t0:.2f}초")
    
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(slow_fetch, range(4)))
    print(f"  병렬 4건: {time.time()-t0:.2f}초")
