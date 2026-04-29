"""
app/core/store.py
SQLite 기반 영속성 레이어 — 서버 재시작 후에도 데이터 유지

왜 SQLite로 바꾸었나:
  - 이전 버전은 JSON 파일 전체를 매 업데이트마다 재작성 → I/O 병목
  - 잡 수천 건 누적 시 파일 크기 수십~수백MB → rewrite 비용 폭주
  - 감사 이력 요구사항(금융권 POC) 불가
  - 동시 쓰기(스케줄러 + 이관 엔진 + API)에서 락 경합

이 모듈은 기존 JSON Store의 공개 API를 100% 유지하므로 호출부 수정이 필요 없다.
한 Store = 한 테이블. 테이블에는 (key TEXT PRIMARY KEY, value TEXT, updated_at DATETIME)
스키마로 저장. value는 JSON 문자열.

= 동시성 =
  - WAL 모드로 읽기 비블로킹
  - busy_timeout 5초로 쓰기 충돌 시 자동 대기
  - 커넥션은 스레드 로컬로 유지 (멀티스레드 환경 대응)

= 호환 =
  - backend/data/{name}.json 파일이 있으면 첫 기동에 SQLite로 자동 import
  - import 완료된 JSON은 backend/data/_migrated/{name}.json으로 이동 (롤백 안전망)
"""
from __future__ import annotations
import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("databridge.store")

# 데이터 저장 디렉토리 (backend/data/)
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_DATA_DIR.mkdir(exist_ok=True)

# 모든 Store가 공유하는 단일 SQLite 파일
_DB_PATH = _DATA_DIR / "databridge.db"
_MIGRATED_DIR = _DATA_DIR / "_migrated"

# ── 싱글턴 레지스트리 ─────────────────────────────────────
_registry: dict = {}
_registry_lock = threading.Lock()

# ── SQLite 커넥션 풀 (스레드 로컬) ────────────────────────
_tls = threading.local()


def _get_conn() -> sqlite3.Connection:
    """스레드별 SQLite 커넥션 반환 (없으면 생성)"""
    if not hasattr(_tls, "conn") or _tls.conn is None:
        conn = sqlite3.connect(
            str(_DB_PATH),
            timeout=5.0,
            isolation_level=None,     # autocommit
            check_same_thread=False,
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA temp_store=MEMORY")
        _tls.conn = conn
    return _tls.conn


# ── JSON 마이그레이션 (1회만) ─────────────────────────────
_migrated_names: set[str] = set()
_migrate_lock = threading.Lock()


def _import_legacy_json_if_any(name: str, conn: sqlite3.Connection) -> int:
    """
    backend/data/{name}.json 이 있으면 SQLite 테이블로 import.
    성공 시 해당 JSON은 _migrated/ 로 이동.
    이미 테이블이 있고 행이 있으면 스킵.
    """
    with _migrate_lock:
        if name in _migrated_names:
            return 0

        try:
            cur = conn.execute(f"SELECT COUNT(*) FROM `store_{name}`")
            existing = cur.fetchone()[0]
            if existing > 0:
                _migrated_names.add(name)
                return 0
        except sqlite3.OperationalError:
            pass  # 테이블 없음 — 이제 만들 예정

        json_path = _DATA_DIR / f"{name}.json"
        if not json_path.exists():
            _migrated_names.add(name)
            return 0

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error("JSON 마이그레이션 읽기 실패 [%s]: %s", name, e)
            _migrated_names.add(name)
            return 0

        if not isinstance(data, dict):
            logger.warning("JSON 마이그레이션 스킵 [%s]: 딕셔너리 아님", name)
            _migrated_names.add(name)
            return 0

        conn.execute("BEGIN")
        try:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            for k, v in data.items():
                conn.execute(
                    f"INSERT OR REPLACE INTO `store_{name}` (key, value, updated_at) VALUES (?, ?, ?)",
                    (str(k), json.dumps(v, ensure_ascii=False, default=str), ts),
                )
            conn.execute("COMMIT")
        except Exception as e:
            conn.execute("ROLLBACK")
            logger.error("JSON 마이그레이션 INSERT 실패 [%s]: %s", name, e)
            _migrated_names.add(name)
            return 0

        try:
            _MIGRATED_DIR.mkdir(exist_ok=True)
            dest = _MIGRATED_DIR / json_path.name
            if dest.exists():
                suffix = time.strftime("%Y%m%d_%H%M%S")
                dest = _MIGRATED_DIR / f"{json_path.stem}.{suffix}.json"
            json_path.rename(dest)
        except Exception as e:
            logger.warning("마이그레이션 후 원본 이동 실패 (무시) [%s]: %s", name, e)

        logger.warning(
            "Store '%s': JSON → SQLite 마이그레이션 완료 (%d행). 원본은 data/_migrated/로 이동.",
            name, len(data),
        )
        _migrated_names.add(name)
        return len(data)


class Store:
    """
    key-value 스토어 — SQLite 백엔드.
    공개 API는 이전 JSON 기반 Store와 100% 동일.
    """

    def __new__(cls, name: str):
        with _registry_lock:
            if name not in _registry:
                instance = super().__new__(cls)
                _registry[name] = instance
            return _registry[name]

    def __init__(self, name: str):
        if getattr(self, "_initialized", False):
            return
        if not name.replace("_", "").isalnum():
            raise ValueError(f"Store name은 영숫자/언더스코어만 허용: {name!r}")

        self._name = name
        self._table = f"store_{name}"
        self._lock = threading.RLock()

        conn = _get_conn()
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS `{self._table}` (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS `idx_{self._table}_updated` "
            f"ON `{self._table}`(updated_at DESC)"
        )

        _import_legacy_json_if_any(name, conn)

        self._cache: dict = self._load_all_from_db(conn)
        self._initialized = True

    def _load_all_from_db(self, conn: sqlite3.Connection) -> dict:
        result: dict = {}
        cur = conn.execute(f"SELECT key, value FROM `{self._table}`")
        for k, v in cur.fetchall():
            try:
                result[k] = json.loads(v)
            except Exception:
                result[k] = v
        return result

    def _write_one(self, key: str, value: Any) -> None:
        try:
            payload = json.dumps(value, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error("Store[%s] JSON 직렬화 실패 key=%s: %s", self._name, key, e)
            return
        conn = _get_conn()
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            conn.execute(
                f"INSERT OR REPLACE INTO `{self._table}` (key, value, updated_at) VALUES (?, ?, ?)",
                (str(key), payload, ts),
            )
        except Exception as e:
            logger.error("Store[%s] 저장 실패 key=%s: %s", self._name, key, e)

    def _delete_one(self, key: str) -> None:
        conn = _get_conn()
        try:
            conn.execute(f"DELETE FROM `{self._table}` WHERE key = ?", (str(key),))
        except Exception as e:
            logger.error("Store[%s] 삭제 실패 key=%s: %s", self._name, key, e)

    # ── 공개 API (JSON Store와 호환) ───────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        return self._cache.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._cache[key] = value
            self._write_one(key, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)
            self._delete_one(key)

    def all(self) -> dict:
        return dict(self._cache)

    def values(self) -> list:
        return list(self._cache.values())

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def __len__(self) -> int:
        return len(self._cache)

    def update_field(self, key: str, field: str, value: Any) -> None:
        with self._lock:
            if key in self._cache and isinstance(self._cache[key], dict):
                self._cache[key][field] = value
                self._write_one(key, self._cache[key])

    def bulk_update(self, key: str, updates: dict) -> None:
        with self._lock:
            if key in self._cache and isinstance(self._cache[key], dict):
                self._cache[key].update(updates)
                self._write_one(key, self._cache[key])

    def update_in_memory(self, key: str, updates: dict) -> None:
        """
        메모리만 갱신. 이관 엔진이 초당 수십회 진행률 업데이트할 때
        fsync 폭주 방지. 최종 저장은 flush() 또는 set()에서 발생.
        """
        if key in self._cache and isinstance(self._cache[key], dict):
            with self._lock:
                self._cache[key].update(updates)

    def flush(self) -> None:
        """메모리 캐시 전체 → 디스크 일괄 동기화"""
        with self._lock:
            conn = _get_conn()
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("BEGIN")
            try:
                for k, v in self._cache.items():
                    try:
                        payload = json.dumps(v, ensure_ascii=False, default=str)
                    except Exception:
                        continue
                    conn.execute(
                        f"INSERT OR REPLACE INTO `{self._table}` (key, value, updated_at) VALUES (?, ?, ?)",
                        (str(k), payload, ts),
                    )
                conn.execute("COMMIT")
            except Exception as e:
                try: conn.execute("ROLLBACK")
                except Exception: pass
                logger.error("Store[%s] flush 실패: %s", self._name, e)


def close_all() -> None:
    """lifespan shutdown에서 호출. WAL 체크포인트 후 커넥션 종료."""
    if hasattr(_tls, "conn") and _tls.conn is not None:
        try:
            _tls.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            _tls.conn.close()
        except Exception:
            pass
        _tls.conn = None
