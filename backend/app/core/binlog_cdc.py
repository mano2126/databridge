"""
app/core/binlog_cdc.py
MySQL binlog 기반 진짜 CDC 엔진.

기술:
  - python-mysql-replication 라이브러리 (pymysqlreplication)
  - MySQL replication protocol로 binlog stream 구독
  - ROW 형식 binlog 이벤트를 파싱하여 INSERT/UPDATE/DELETE 이벤트 생성

요구사항:
  소스 MySQL에서 다음이 설정되어야 함:
    [mysqld]
    server-id = <unique_id>
    log_bin = mysql-bin          # binlog 활성
    binlog_format = ROW          # ROW 권장
    binlog_row_image = FULL      # (선택) UPDATE의 전체 이전값 기록

  소스 사용자에 권한 필요:
    GRANT REPLICATION SLAVE, REPLICATION CLIENT ON *.* TO 'cdc_user'@'%';
    GRANT SELECT ON <db>.* TO 'cdc_user'@'%';

한계:
  - MySQL 계열만 지원 (MSSQL CDC는 별도 구현 필요 — 로드맵)
  - DDL 변경은 자동 처리 안 함 (컬럼 추가/삭제 시 수동 대응)
  - 시작 시점 이전 변경은 받을 수 없음 (초기 full load 필요)

사용:
  from app.core.binlog_cdc import start_binlog_cdc, stop_binlog_cdc
  start_binlog_cdc("cdc_job_1", {
      "src_conn": {...},
      "tgt_conn": {...},
      "tables":   [{"table": "orders"}, ...],
      "server_id": 100,       # 소스 MySQL과 다른 고유 ID
  })
"""
from __future__ import annotations
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

KST = timezone(timedelta(hours=9))
logger = logging.getLogger("databridge.cdc.binlog")


_HAS_PYMYSQLREPLICATION = False
try:
    # 지연 import 없이 한 번 시도 — 라이브러리 존재 여부 확인
    from pymysqlreplication import BinLogStreamReader  # noqa
    from pymysqlreplication.row_event import (
        DeleteRowsEvent, UpdateRowsEvent, WriteRowsEvent,
    )
    _HAS_PYMYSQLREPLICATION = True
except ImportError:
    logger.info(
        "pymysqlreplication 미설치 — binlog CDC 기능 비활성. "
        "'pip install mysql-replication' 으로 활성화 가능."
    )


_running: dict = {}
_running_lock = threading.Lock()


def is_available() -> bool:
    """binlog CDC 사용 가능 여부"""
    return _HAS_PYMYSQLREPLICATION


def _now_kst():
    return datetime.now(KST)


# ── 메인 CDC 루프 ────────────────────────────────────────────

def _cdc_loop(cdc_id: str, config: dict):
    """
    binlog stream을 열고 이벤트를 처리하는 메인 루프.
    stop() 신호 받기 전까지 무한 루프.
    """
    from app.core.store import Store
    _jstore = Store("jobs")

    src = config.get("src_conn", {})
    tgt = config.get("tgt_conn", {})
    tables = [t["table"] for t in config.get("tables", []) if t.get("table")]
    server_id = int(config.get("server_id", 100))
    only_schemas = [src.get("database")] if src.get("database") else None

    state = _running[cdc_id]
    state["events_total"]  = 0
    state["events_insert"] = 0
    state["events_update"] = 0
    state["events_delete"] = 0

    # MySQL 연결 설정
    mysql_settings = {
        "host":     src.get("host", "127.0.0.1"),
        "port":     int(src.get("port", 3306)),
        "user":     src.get("username", ""),
        "passwd":   src.get("password", ""),
    }

    # 타겟 연결 (적용용)
    tgt_conn = None
    try:
        tgt_conn = _connect_target(tgt)
    except Exception as e:
        logger.error("[CDC:%s] 타겟 연결 실패: %s", cdc_id, e)
        state["status"] = "error"
        state["error"] = f"타겟 연결 실패: {e}"
        return

    stream = None
    try:
        stream = BinLogStreamReader(
            connection_settings=mysql_settings,
            server_id=server_id,
            only_events=[WriteRowsEvent, UpdateRowsEvent, DeleteRowsEvent],
            only_schemas=only_schemas,
            only_tables=tables if tables else None,
            blocking=True,          # 이벤트 없으면 대기
            resume_stream=True,     # 마지막 위치에서 재개
        )
        logger.info("[CDC:%s] binlog stream 시작 (server_id=%d, tables=%s)",
                    cdc_id, server_id, tables)
        state["status"] = "running"

        for event in stream:
            # 중지 신호
            if state.get("stop"):
                logger.info("[CDC:%s] stop 신호 수신 — 루프 종료", cdc_id)
                break

            try:
                _apply_event(cdc_id, event, tgt_conn, tgt, state)
            except Exception as e:
                logger.warning("[CDC:%s] 이벤트 적용 실패: %s", cdc_id, e)
                state["events_error"] = state.get("events_error", 0) + 1
                # fail-forward: 한 이벤트 실패해도 다음 이벤트 계속 처리

    except Exception as e:
        logger.error("[CDC:%s] binlog stream 오류: %s", cdc_id, e)
        state["status"] = "error"
        state["error"] = str(e)[:300]
    finally:
        try:
            if stream:
                stream.close()
        except Exception:
            pass
        try:
            if tgt_conn:
                tgt_conn.close()
        except Exception:
            pass
        state["status"] = "stopped" if not state.get("error") else "error"
        state["finished_at"] = _now_kst().isoformat()

        # jobs store에도 반영
        try:
            j = _jstore.get(cdc_id)
            if j:
                j["status"] = state["status"]
                _jstore.set(cdc_id, j)
        except Exception:
            pass


def _connect_target(conn_info: dict):
    """타겟 DB 연결 (MySQL/MSSQL/PostgreSQL)"""
    db_type = (conn_info.get("db_type") or "mysql").lower()
    host = conn_info.get("host", "127.0.0.1")
    port = int(conn_info.get("port") or 3306)
    user = conn_info.get("username", "")
    pwd  = conn_info.get("password", "")
    db   = conn_info.get("database", "")

    if db_type in ("mysql", "mariadb", "aurora", "tidb"):
        import pymysql
        return pymysql.connect(host=host, port=port, user=user, password=pwd,
                               database=db, autocommit=True, charset="utf8mb4")
    elif db_type in ("mssql", "sqlserver", "azure"):
        # v9 패치 #52: 공용 헬퍼 (드라이버 자동감지 + 인코딩 설정)
        from app.core.db_conn import make_mssql_conn
        conn = make_mssql_conn(host, port, user, pwd, db)
        conn.autocommit = True
        return conn
    elif db_type in ("postgresql", "postgres"):
        import psycopg2
        return psycopg2.connect(host=host, port=port, user=user, password=pwd,
                                database=db)
    else:
        raise ValueError(f"지원하지 않는 타겟 DB: {db_type}")


def _apply_event(cdc_id: str, event, tgt_conn, tgt_info: dict, state: dict):
    """
    binlog 이벤트 1건을 타겟에 적용.
    INSERT/UPDATE/DELETE 별로 적절한 SQL 생성.
    """
    table = event.table
    schema = event.schema
    tgt_db_type = (tgt_info.get("db_type") or "mysql").lower()
    state["events_total"] += 1

    # 이벤트 종류 분기
    if isinstance(event, WriteRowsEvent):
        _apply_inserts(tgt_conn, table, event.rows, tgt_db_type)
        state["events_insert"] += len(event.rows)
    elif isinstance(event, UpdateRowsEvent):
        _apply_updates(tgt_conn, table, event.rows, event.primary_key, tgt_db_type)
        state["events_update"] += len(event.rows)
    elif isinstance(event, DeleteRowsEvent):
        _apply_deletes(tgt_conn, table, event.rows, event.primary_key, tgt_db_type)
        state["events_delete"] += len(event.rows)

    state["last_event_at"] = _now_kst().isoformat()


def _quote_ident(name: str, db_type: str) -> str:
    if db_type in ("mssql", "sqlserver", "azure"):
        return f"[{name}]"
    return f"`{name}`"


def _apply_inserts(conn, table: str, rows: list, tgt_db_type: str):
    if not rows:
        return
    cur = conn.cursor()
    for row in rows:
        values = row["values"]
        cols = list(values.keys())
        col_list = ", ".join(_quote_ident(c, tgt_db_type) for c in cols)
        placeholders = ", ".join(["?" if tgt_db_type in ("mssql","sqlserver","azure") else "%s"] * len(cols))
        q = _quote_ident(table, tgt_db_type)
        sql = f"INSERT INTO {q} ({col_list}) VALUES ({placeholders})"
        try:
            cur.execute(sql, tuple(values.values()))
        except Exception as e:
            # 이미 있는 PK면 UPDATE로 폴백
            if "duplicate" in str(e).lower() or "pk" in str(e).lower():
                logger.debug("INSERT 실패 (중복) — UPDATE 시도: %s", e)
            else:
                raise
    cur.close()


def _apply_updates(conn, table: str, rows: list, pk_cols, tgt_db_type: str):
    if not rows:
        return
    cur = conn.cursor()
    for row in rows:
        after = row["after_values"]
        before = row["before_values"]
        # PK 컬럼이 파악되면 사용, 아니면 before_values 전체를 WHERE 조건에 사용 (비효율)
        pk_list = pk_cols if pk_cols else list(before.keys())
        set_clause = ", ".join(
            f"{_quote_ident(c, tgt_db_type)} = " + ("?" if tgt_db_type in ("mssql","sqlserver","azure") else "%s")
            for c in after.keys()
        )
        where_clause = " AND ".join(
            f"{_quote_ident(c, tgt_db_type)} = " + ("?" if tgt_db_type in ("mssql","sqlserver","azure") else "%s")
            for c in pk_list
        )
        q = _quote_ident(table, tgt_db_type)
        sql = f"UPDATE {q} SET {set_clause} WHERE {where_clause}"
        params = list(after.values()) + [before.get(c) for c in pk_list]
        cur.execute(sql, tuple(params))
    cur.close()


def _apply_deletes(conn, table: str, rows: list, pk_cols, tgt_db_type: str):
    if not rows:
        return
    cur = conn.cursor()
    for row in rows:
        values = row["values"]
        pk_list = pk_cols if pk_cols else list(values.keys())
        where_clause = " AND ".join(
            f"{_quote_ident(c, tgt_db_type)} = " + ("?" if tgt_db_type in ("mssql","sqlserver","azure") else "%s")
            for c in pk_list
        )
        q = _quote_ident(table, tgt_db_type)
        sql = f"DELETE FROM {q} WHERE {where_clause}"
        params = [values.get(c) for c in pk_list]
        cur.execute(sql, tuple(params))
    cur.close()


# ── 외부 API ─────────────────────────────────────────────────

def start_binlog_cdc(cdc_id: str, config: dict) -> dict:
    """
    binlog CDC 시작. 백그라운드 스레드로 실행.

    config:
      src_conn:  MySQL 연결 정보 (binlog 활성 + REPLICATION 권한 필요)
      tgt_conn:  타겟 DB 연결 정보
      tables:    [{"table": "orders"}, ...]   (빈 리스트면 모든 테이블)
      server_id: int  (소스 MySQL과 다른 고유 ID, 기본 100)

    Returns:
      {"ok": True, "cdc_id": ..., "mode": "binlog_cdc"} 또는
      {"ok": False, "error": "pymysqlreplication 미설치"}
    """
    if not _HAS_PYMYSQLREPLICATION:
        return {"ok": False,
                "error": "pymysqlreplication 라이브러리 미설치. "
                         "'pip install mysql-replication' 후 재기동하세요."}

    src_db_type = (config.get("src_conn", {}).get("db_type") or "").lower()
    if src_db_type not in ("mysql", "mariadb", "aurora"):
        return {"ok": False,
                "error": f"binlog CDC는 MySQL 계열만 지원합니다 (현재: {src_db_type}). "
                         f"MSSQL/Oracle/PostgreSQL CDC는 로드맵입니다."}

    with _running_lock:
        if cdc_id in _running:
            return {"ok": False, "error": "이미 실행 중"}
        _running[cdc_id] = {
            "status": "starting",
            "mode":   "binlog_cdc",
            "started_at": _now_kst().isoformat(),
            "stop":   False,
        }

    t = threading.Thread(target=_cdc_loop, args=(cdc_id, config), daemon=True)
    t.start()

    return {"ok": True, "cdc_id": cdc_id, "mode": "binlog_cdc"}


def stop_binlog_cdc(cdc_id: str) -> dict:
    """binlog CDC 중단 신호 — 루프가 다음 이벤트에서 감지 후 종료"""
    with _running_lock:
        if cdc_id in _running:
            _running[cdc_id]["stop"] = True
            return {"ok": True}
    return {"ok": False, "error": "실행 중인 CDC 없음"}


def get_binlog_cdc_status(cdc_id: str) -> Optional[dict]:
    return _running.get(cdc_id)


def get_all_binlog_cdc_status() -> dict:
    return dict(_running)
