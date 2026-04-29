"""
app/core/store.py
JSON 파일 기반 영속성 레이어 — 서버 재시작 후에도 데이터 유지

사용법:
    from app.core.store import Store
    s = Store("jobs")          # data/jobs.json 에 저장
    s.set("key", value)
    s.get("key")
    s.delete("key")
    s.all() → dict
"""
import json
import os
import threading
import time
from pathlib import Path

# 데이터 저장 디렉토리 (backend/data/)
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_DATA_DIR.mkdir(exist_ok=True)

_lock = threading.Lock()


class Store:
    """단순 key-value JSON 파일 스토어"""

    def __init__(self, name: str):
        self._path = _DATA_DIR / f"{name}.json"
        self._cache: dict = {}
        self._dirty = False
        self._load()

    # ── 내부 I/O ─────────────────────────────────────────

    def _load(self):
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except Exception:
                self._cache = {}
        else:
            self._cache = {}

    def _save(self):
        """즉시 디스크에 플러시"""
        try:
            tmp = self._path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2, default=str)
            tmp.replace(self._path)   # atomic rename
        except Exception as e:
            pass  # 저장 실패는 무시 (메모리 캐시는 살아 있음)

    # ── 공개 API ──────────────────────────────────────────

    def get(self, key: str, default=None):
        return self._cache.get(key, default)

    def set(self, key: str, value):
        with _lock:
            self._cache[key] = value
            self._save()

    def delete(self, key: str):
        with _lock:
            self._cache.pop(key, None)
            self._save()

    def all(self) -> dict:
        return dict(self._cache)

    def values(self) -> list:
        return list(self._cache.values())

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def __len__(self) -> int:
        return len(self._cache)

    def update_field(self, key: str, field: str, value):
        """딕셔너리 항목의 특정 필드만 업데이트 (Job 진행률 갱신 등)"""
        with _lock:
            if key in self._cache and isinstance(self._cache[key], dict):
                self._cache[key][field] = value
                self._save()

    def bulk_update(self, key: str, updates: dict):
        """딕셔너리 항목 여러 필드 한꺼번에 갱신"""
        with _lock:
            if key in self._cache and isinstance(self._cache[key], dict):
                self._cache[key].update(updates)
                self._save()

    def update_in_memory(self, key: str, updates: dict):
        """
        저장은 하지 않고 메모리만 갱신 (진행 중인 Job 상태 업데이트용)
        job finished 시에만 _save() 호출하도록 설계
        """
        if key in self._cache and isinstance(self._cache[key], dict):
            self._cache[key].update(updates)

    def flush(self):
        """메모리 → 디스크 강제 동기화"""
        with _lock:
            self._save()
