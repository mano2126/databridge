"""
app/monitor/import_retry.py — 런타임 설치 감지 유틸
v10 #22 Phase A-3 — 2026-04-24

목적:
  사용자가 백엔드 실행 중에 `pip install <pkg>` 한 패키지를
  **서버 재시작 없이** 감지하여 import.

배경:
  Phase A-1 배포 후 발견된 문제.
  사용자가 이관 중에 psutil/docker 를 설치했는데,
  이미 한 번 import 실패했던 모듈은 sys.modules 에 None 으로
  저장되어 (CPython 내부 동작) 그 프로세스에서는 재시도해도
  "import halted; None in sys.modules" 오류 발생.

  POC 검증 결과 (Python 3.11, 2026-04-24):
    - sys.modules['psutil'] = None 시: 1차 import 실패
    - del sys.modules + importlib.invalidate_caches() + import_module 시: 성공

사용자 철학:
  "한 번의 재시작도 사용자에게 마찰이다" (Choi, CIO 2026-04-24)
  → 경쟁 도구는 의존성 변경 시 재시작 요구.
    DataBridge 는 그냥 작동해야 한다.

주요 특징:
  1. Rate limit (60초) — 미설치 상태에서 매 폴링마다 invalidate
     호출하면 CPU 낭비. 60초에 1회로 제한.
  2. 정상 로드된 모듈은 캐시 그대로 쓴다 (빠름)
  3. thread-safe (RLock)
"""
from __future__ import annotations

import importlib
import sys
import threading
import time
from typing import Any, Optional


# ── 상태 ──────────────────────────────────────────────
_lock = threading.RLock()
_last_fail: dict[str, float] = {}
_FAIL_COOLDOWN_SEC = 60.0


def try_import(module_name: str, force_refresh: bool = False) -> Optional[Any]:
    """
    런타임에 설치된 모듈을 감지하여 import 한다.

    Args:
        module_name: "psutil", "docker" 같은 모듈명
        force_refresh: True 면 캐시 무시하고 강제 재import

    Returns:
        모듈 객체 (성공 시) 또는 None (실패/미설치)

    동작 흐름:
        1. 이미 정상 로드됐으면 캐시 반환 (빠름)
        2. Rate limit: 최근 60초 내 실패했으면 바로 None
        3. sys.modules 의 None 오염 제거
        4. importlib.invalidate_caches() 로 finder 리셋
        5. importlib.import_module() 로 깨끗하게 재시도
    """
    with _lock:
        # 1) 이미 정상 로드 상태 — 빠른 경로
        if not force_refresh:
            cached = sys.modules.get(module_name)
            if cached is not None:
                # None 이 아닌 모듈 객체가 캐시돼 있으면 그대로 반환
                return cached

        # 2) Rate limit — 최근 실패 이력 체크
        last = _last_fail.get(module_name, 0.0)
        if time.time() - last < _FAIL_COOLDOWN_SEC:
            return None

        # 3) sys.modules 오염 제거 (None 캐싱된 경우)
        if module_name in sys.modules and sys.modules[module_name] is None:
            del sys.modules[module_name]

        # 4) finder 캐시 무효화 — 새로 설치된 패키지 site-packages 재스캔
        importlib.invalidate_caches()

        # 5) 깨끗한 재import 시도
        try:
            mod = importlib.import_module(module_name)
            # 성공: 실패 기록 제거
            _last_fail.pop(module_name, None)
            return mod
        except ImportError:
            _last_fail[module_name] = time.time()
            return None
        except Exception:
            # 다른 예외 (예: 모듈 초기화 에러) 도 동일 처리
            _last_fail[module_name] = time.time()
            return None


def mark_failed(module_name: str) -> None:
    """명시적으로 실패 표시 (예: ping 은 되는데 권한 에러 등)."""
    with _lock:
        _last_fail[module_name] = time.time()


def reset_retry_state(module_name: Optional[str] = None) -> None:
    """재시도 상태 초기화.

    Args:
        module_name: 특정 모듈만 초기화. None 이면 전체.
    """
    with _lock:
        if module_name is None:
            _last_fail.clear()
        else:
            _last_fail.pop(module_name, None)


def get_status() -> dict[str, Any]:
    """디버깅용 — 현재 재시도 상태 스냅샷."""
    with _lock:
        now = time.time()
        return {
            "cooldown_sec": _FAIL_COOLDOWN_SEC,
            "failed_modules": {
                name: {
                    "failed_at":    ts,
                    "cooldown_remaining": max(0, _FAIL_COOLDOWN_SEC - (now - ts)),
                }
                for name, ts in _last_fail.items()
            },
        }
