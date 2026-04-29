"""
인덱스 지연생성 (v10 #9)

벌크 로드 전에 세컨더리 인덱스를 DROP 하고,
로드 완료 후 CREATE INDEX 로 복원한다.

효과:
  - InnoDB / MSSQL 공통: 인덱스 유지 오버헤드 제거 → LOAD 2~5배 빨라짐
  - 복원 시 일괄 정렬 → 인덱스 생성 자체도 효율적

안전성:
  - 컨텍스트매니저로 감싸서 예외 발생 시에도 finally 에서 복원 시도
  - 복원 실패 시 명시적 로그 경고 + 백업 SQL 파일 생성 (사용자가 수동 복원 가능하도록)
  - PK 는 절대 건드리지 않음 (AUTO_INCREMENT 무결성 보장)

사용 예:
    with defer_indexes(conn, dialect, table, logger=log) as ctx:
        # 로드 수행 (이 블록 내부는 인덱스 없음)
        bulk_load(...)
    # 블록 나가면 자동으로 인덱스 복원 시도
"""
from __future__ import annotations
import os
import time
from contextlib import contextmanager
from typing import List, Optional, Callable, Iterator

from .dialects.base import DatabaseDialect, IndexInfo


# 로그 백업 디렉토리 (복원 실패 시 수동 복구용 SQL 저장)
_BACKUP_DIR_NAME = "index_backup"


@contextmanager
def defer_indexes(
    conn,
    dialect: DatabaseDialect,
    table: str,
    logger: Optional[Callable[[str, str], None]] = None,
    backup_dir: Optional[str] = None,
) -> Iterator[List[IndexInfo]]:
    """
    세컨더리 인덱스 지연생성 컨텍스트매니저.

    Args:
        conn        : 타겟 DB 연결 (이 연결로 DROP/CREATE 실행)
        dialect     : 타겟 DB 방언
        table       : 대상 테이블명
        logger      : 로그 콜백 (level: str, msg: str) — 없으면 print fallback
        backup_dir  : 복원 SQL 백업 디렉토리 (기본: None → 현재 작업디렉토리/index_backup)

    Yields:
        DROP 된 인덱스 목록 (호출자가 참조 가능)

    주의사항:
        - PK 는 건드리지 않음
        - MSSQL UNIQUE CONSTRAINT 는 Phase 2 범위 외 (복원 복잡)
        - CHECK/FK 는 이 함수 범위 아님 (상위 엔진에서 처리)
    """
    _log = logger if logger else lambda lv, msg: print(f"[{lv}] {msg}")

    # ── 1. 인덱스 스냅샷 ────────────────────────────────
    try:
        indexes = dialect.get_secondary_indexes(conn, table)
    except Exception as e:
        _log("warn",
            f"  [{table}] 인덱스 조회 실패 — 지연생성 스킵 (인덱스 유지한 채 로드): {e}")
        # 조회 실패 시에도 yield 해서 로드는 계속
        yield []
        return

    if not indexes:
        _log("info", f"  [{table}] 세컨더리 인덱스 없음 — 지연생성 불필요")
        yield []
        return

    _log("info",
        f"  [{table}] 인덱스 지연생성: 세컨더리 인덱스 {len(indexes)}개 DROP 예정")
    for idx in indexes:
        _log("debug",
            f"    - {idx.name} ({'UNIQUE ' if idx.is_unique else ''}"
            f"{idx.index_type or '?'}, cols={idx.columns})")

    # 복원 SQL 을 미리 만들어서 백업 파일로 저장 (복원 실패 시 수동 복구용)
    backup_path = _save_backup_sql(table, indexes, dialect, backup_dir, _log)

    # ── 2. DROP ────────────────────────────────────────
    dropped: List[IndexInfo] = []
    drop_failed: List[tuple] = []  # (index, error)
    cur = conn.cursor()
    try:
        t0 = time.monotonic()
        for idx in indexes:
            try:
                sql = dialect.drop_index_sql(idx)
                _log("debug", f"    DROP: {sql}")
                cur.execute(sql)
                dropped.append(idx)
            except Exception as e:
                drop_failed.append((idx, e))
                _log("warn",
                    f"  [{table}] 인덱스 DROP 실패 — [{idx.name}]: {e}")
        try: conn.commit()
        except Exception: pass

        drop_elapsed = time.monotonic() - t0
        if dropped:
            _log("info",
                f"  [{table}] 인덱스 {len(dropped)}개 DROP 완료 ({drop_elapsed:.1f}s)")
        if drop_failed:
            _log("warn",
                f"  [{table}] DROP 실패 {len(drop_failed)}개 — 해당 인덱스는 유지된 채 로드 진행")
    finally:
        try: cur.close()
        except: pass

    # ── 3. 로드 수행 (호출자가 여기서 INSERT) ────────────
    load_exc = None
    try:
        yield dropped
    except Exception as e:
        load_exc = e
        _log("error",
            f"  [{table}] 로드 중 예외 발생 — 인덱스 복원 시도 (rethrow 예정): {e}")
        # re-raise 는 finally 이후

    # ── 4. CREATE (복원) ──────────────────────────────
    restore_failed: List[tuple] = []
    cur = conn.cursor()
    try:
        t0 = time.monotonic()
        for idx in dropped:
            try:
                sql = dialect.create_index_sql(idx)
                _log("debug", f"    CREATE: {sql}")
                cur.execute(sql)
            except Exception as e:
                restore_failed.append((idx, e))
                _log("error",
                    f"  [{table}] 인덱스 복원 실패 — [{idx.name}]: {e}")
        try: conn.commit()
        except Exception: pass

        restore_elapsed = time.monotonic() - t0
        restored_count = len(dropped) - len(restore_failed)
        if restored_count > 0:
            _log("info",
                f"  [{table}] 인덱스 {restored_count}개 복원 완료 ({restore_elapsed:.1f}s)")
        if restore_failed:
            _log("error",
                f"  [{table}] 복원 실패 {len(restore_failed)}개 — "
                f"백업 SQL 참조: {backup_path or '(저장 실패)'}")
    finally:
        try: cur.close()
        except: pass

    # 로드 중 예외가 있었으면 re-raise
    if load_exc is not None:
        raise load_exc


def _save_backup_sql(
    table: str,
    indexes: List[IndexInfo],
    dialect: DatabaseDialect,
    backup_dir: Optional[str],
    logger: Callable[[str, str], None],
) -> Optional[str]:
    """
    복원용 CREATE INDEX SQL 을 백업 파일로 저장.

    Phase 2: 복원 실패 시 사용자가 수동 복원 가능하도록.
    Phase 3b: Go 바이너리는 자체 복구 로직으로 대체 예정.
    """
    try:
        bd = backup_dir or os.path.join(os.getcwd(), _BACKUP_DIR_NAME)
        os.makedirs(bd, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        fname = f"{table}_restore_{ts}.sql"
        fpath = os.path.join(bd, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(f"-- Index restore script for table: {table}\n")
            f.write(f"-- Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- Dialect: {dialect.name}\n")
            f.write(f"-- Use this if automatic restoration fails.\n\n")
            for idx in indexes:
                f.write(f"-- Index: {idx.name} (unique={idx.is_unique}, type={idx.index_type})\n")
                f.write(dialect.create_index_sql(idx) + ";\n\n")
        logger("debug", f"  [{table}] 인덱스 복원 백업 저장: {fpath}")
        return fpath
    except Exception as e:
        logger("warn", f"  [{table}] 인덱스 백업 SQL 저장 실패 (무시): {e}")
        return None
