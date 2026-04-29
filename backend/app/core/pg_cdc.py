"""
app/core/pg_cdc.py
PostgreSQL Logical Replication 기반 CDC 엔진.

기술:
  - PostgreSQL logical replication slot + pgoutput/wal2json plugin
  - psycopg2의 LogicalReplicationConnection 사용 (동기)
  - WAL 스트림에서 INSERT/UPDATE/DELETE 이벤트 파싱

요구사항 (소스 PostgreSQL):
  postgresql.conf:
    wal_level = logical
    max_replication_slots = 10   # 충분히 크게
    max_wal_senders = 10

  pg_hba.conf:
    host replication  <user>  <client_ip>/32  md5

  SQL 초기화:
    CREATE PUBLICATION databridge_pub FOR ALL TABLES;  -- 또는 FOR TABLE t1,t2
    GRANT rds_replication TO <user>;   -- RDS의 경우
    -- 슬롯은 엔진 시작 시 자동 생성

한계:
  - 슬롯이 남아있으면 서버 WAL 누적 → 반드시 종료 시 drop_slot 호출
  - 시작 이전 변경은 받을 수 없음 (초기 full load 필요)
  - DDL 변경은 복제되지 않음 (PostgreSQL 17+ 부터 일부 지원)
  - plugin은 wal2json 또는 pgoutput 필요
"""
from __future__ import annotations
import json
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

KST = timezone(timedelta(hours=9))
logger = logging.getLogger("databridge.cdc.pg")


_HAS_PSYCOPG2 = False
try:
    import psycopg2
    import psycopg2.extras
    from psycopg2.extras import LogicalReplicationConnection
    _HAS_PSYCOPG2 = True
except ImportError:
    logger.info(
        "psycopg2 미설치 — PostgreSQL CDC 비활성. "
        "'pip install psycopg2-binary' 권장."
    )


_running: dict = {}
_running_lock = threading.Lock()


def is_available() -> bool:
    return _HAS_PSYCOPG2


def _now_kst():
    return datetime.now(KST)


# ── 메인 CDC 루프 ────────────────────────────────────────

def _pg_cdc_loop(cdc_id: str, config: dict):
    """
    PostgreSQL logical replication stream을 소비하여 타겟에 적용.
    stop 신호까지 무한 루프.
    """
    src = config.get("src_conn", {})
    tgt = config.get("tgt_conn", {})
    slot_name = config.get("slot_name", f"databridge_{cdc_id[:8]}")
    publication = config.get("publication", "databridge_pub")
    plugin = config.get("plugin", "wal2json")
    tables = [t["table"] for t in config.get("tables", []) if t.get("table")]

    state = _running[cdc_id]
    state["events_total"]  = 0
    state["events_insert"] = 0
    state["events_update"] = 0
    state["events_delete"] = 0

    # replication 연결
    try:
        repl_conn = psycopg2.connect(
            host=src.get("host", "127.0.0.1"),
            port=int(src.get("port", 5432)),
            user=src.get("username", ""),
            password=src.get("password", ""),
            database=src.get("database", ""),
            connection_factory=LogicalReplicationConnection,
        )
        repl_cur = repl_conn.cursor()
    except Exception as e:
        logger.error("[CDC:%s] PostgreSQL replication 연결 실패: %s", cdc_id, e)
        state["status"] = "error"
        state["error"] = f"replication 연결 실패: {e}"
        return

    # 타겟 연결
    try:
        tgt_conn = _connect_target(tgt)
    except Exception as e:
        logger.error("[CDC:%s] 타겟 연결 실패: %s", cdc_id, e)
        state["status"] = "error"
        state["error"] = f"타겟 연결 실패: {e}"
        repl_conn.close()
        return

    # replication slot 생성 (이미 있으면 재사용)
    try:
        repl_cur.create_replication_slot(slot_name, output_plugin=plugin)
        logger.info("[CDC:%s] replication slot 생성: %s (plugin=%s)",
                    cdc_id, slot_name, plugin)
    except psycopg2.errors.DuplicateObject:
        logger.info("[CDC:%s] replication slot 기존 것 재사용: %s", cdc_id, slot_name)
    except Exception as e:
        logger.error("[CDC:%s] slot 생성 실패: %s", cdc_id, e)
        state["status"] = "error"
        state["error"] = f"slot 생성 실패: {e}"
        tgt_conn.close()
        repl_conn.close()
        return

    # replication stream 시작
    try:
        options = {}
        if plugin == "pgoutput":
            options = {
                "proto_version": "1",
                "publication_names": publication,
            }
        repl_cur.start_replication(slot_name=slot_name, options=options, decode=True)
        logger.info("[CDC:%s] replication stream 시작", cdc_id)
        state["status"] = "running"

        # consume_stream 대신 수동 루프 (stop 신호 체크 가능)
        while True:
            if state.get("stop"):
                logger.info("[CDC:%s] stop 신호 — 루프 종료", cdc_id)
                break

            msg = repl_cur.read_message()
            if msg:
                try:
                    _apply_pg_event(cdc_id, msg, tgt_conn, tgt, state, tables)
                    msg.cursor.send_feedback(flush_lsn=msg.data_start)
                except Exception as e:
                    logger.warning("[CDC:%s] 이벤트 적용 실패: %s", cdc_id, e)
                    state["events_error"] = state.get("events_error", 0) + 1
            else:
                # 메시지 없으면 짧게 대기
                time.sleep(0.1)

    except Exception as e:
        logger.error("[CDC:%s] replication 오류: %s", cdc_id, e)
        state["status"] = "error"
        state["error"] = str(e)[:300]
    finally:
        try:
            # slot 유지 여부: keep_slot=True 면 서버 재기동 후 이어 받기 가능
            if not config.get("keep_slot", False):
                try:
                    repl_cur.drop_replication_slot(slot_name)
                    logger.info("[CDC:%s] slot 삭제: %s", cdc_id, slot_name)
                except Exception as e:
                    logger.warning("[CDC:%s] slot 삭제 실패 (수동 정리 필요): %s",
                                   cdc_id, e)
        except Exception:
            pass
        try:
            tgt_conn.close()
        except Exception:
            pass
        try:
            repl_conn.close()
        except Exception:
            pass
        state["status"] = "stopped" if not state.get("error") else "error"
        state["finished_at"] = _now_kst().isoformat()


def _connect_target(conn_info: dict):
    """타겟 DB 연결 — MySQL/MSSQL/PostgreSQL"""
    db_type = (conn_info.get("db_type") or "").lower()
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
        return psycopg2.connect(host=host, port=port, user=user, password=pwd,
                                database=db)
    else:
        raise ValueError(f"지원하지 않는 타겟 DB: {db_type}")


def _apply_pg_event(cdc_id: str, msg, tgt_conn, tgt_info: dict, state: dict, tables_filter: list):
    """
    wal2json 또는 pgoutput 이벤트를 파싱해서 타겟에 적용.
    wal2json 포맷이 훨씬 다루기 쉬워 기본으로 가정.
    """
    try:
        payload = json.loads(msg.payload)
    except Exception:
        logger.debug("[CDC:%s] 비 JSON 메시지 건너뜀", cdc_id)
        return

    # wal2json 포맷: {"change": [ {kind, schema, table, columnnames, columnvalues, oldkeys}, ...]}
    changes = payload.get("change", [])
    if not changes:
        return

    tgt_db_type = (tgt_info.get("db_type") or "mysql").lower()
    cur = tgt_conn.cursor()

    for ch in changes:
        table = ch.get("table")
        if tables_filter and table not in tables_filter:
            continue
        kind = ch.get("kind")  # insert | update | delete

        if kind == "insert":
            cols = ch.get("columnnames", [])
            vals = ch.get("columnvalues", [])
            _do_insert(cur, table, cols, vals, tgt_db_type)
            state["events_insert"] += 1

        elif kind == "update":
            cols = ch.get("columnnames", [])
            vals = ch.get("columnvalues", [])
            oldkeys = ch.get("oldkeys", {})
            pk_cols = oldkeys.get("keynames", [])
            pk_vals = oldkeys.get("keyvalues", [])
            _do_update(cur, table, cols, vals, pk_cols, pk_vals, tgt_db_type)
            state["events_update"] += 1

        elif kind == "delete":
            oldkeys = ch.get("oldkeys", {})
            pk_cols = oldkeys.get("keynames", [])
            pk_vals = oldkeys.get("keyvalues", [])
            _do_delete(cur, table, pk_cols, pk_vals, tgt_db_type)
            state["events_delete"] += 1

        state["events_total"] += 1

    cur.close()
    state["last_event_at"] = _now_kst().isoformat()


def _quote_ident(name: str, db_type: str) -> str:
    if db_type in ("mssql", "sqlserver", "azure"):
        return f"[{name}]"
    return f'"{name}"' if db_type in ("postgresql", "postgres") else f"`{name}`"


def _placeholder(db_type: str, i: int) -> str:
    if db_type in ("mssql", "sqlserver", "azure"):
        return "?"
    if db_type in ("postgresql", "postgres"):
        return f"%s"
    return "%s"  # pymysql도 %s


def _do_insert(cur, table: str, cols: list, vals: list, tgt_db_type: str):
    col_list = ", ".join(_quote_ident(c, tgt_db_type) for c in cols)
    ph = ", ".join([_placeholder(tgt_db_type, i) for i in range(len(cols))])
    q = _quote_ident(table, tgt_db_type)
    sql = f"INSERT INTO {q} ({col_list}) VALUES ({ph})"
    cur.execute(sql, tuple(vals))


def _do_update(cur, table: str, cols: list, vals: list,
               pk_cols: list, pk_vals: list, tgt_db_type: str):
    set_clause = ", ".join(
        f"{_quote_ident(c, tgt_db_type)} = {_placeholder(tgt_db_type, 0)}"
        for c in cols
    )
    where_clause = " AND ".join(
        f"{_quote_ident(c, tgt_db_type)} = {_placeholder(tgt_db_type, 0)}"
        for c in pk_cols
    )
    q = _quote_ident(table, tgt_db_type)
    sql = f"UPDATE {q} SET {set_clause} WHERE {where_clause}"
    cur.execute(sql, tuple(list(vals) + list(pk_vals)))


def _do_delete(cur, table: str, pk_cols: list, pk_vals: list, tgt_db_type: str):
    where_clause = " AND ".join(
        f"{_quote_ident(c, tgt_db_type)} = {_placeholder(tgt_db_type, 0)}"
        for c in pk_cols
    )
    q = _quote_ident(table, tgt_db_type)
    sql = f"DELETE FROM {q} WHERE {where_clause}"
    cur.execute(sql, tuple(pk_vals))


# ── 외부 API ─────────────────────────────────────────────

def start_pg_cdc(cdc_id: str, config: dict) -> dict:
    """
    PostgreSQL logical replication CDC 시작.

    config:
      src_conn:   PostgreSQL 연결 (wal_level=logical 필요)
      tgt_conn:   타겟 DB 연결
      tables:     [{"table": "orders"}, ...]  (빈 리스트면 publication 전체)
      slot_name:  str (기본: "databridge_{cdc_id[:8]}")
      publication: str (기본: "databridge_pub")
      plugin:     "wal2json" | "pgoutput" (기본: "wal2json")
      keep_slot:  bool (기본: False — 종료 시 slot 삭제)
    """
    if not _HAS_PSYCOPG2:
        return {"ok": False,
                "error": "psycopg2 미설치. 'pip install psycopg2-binary' 후 재기동하세요."}

    src_db_type = (config.get("src_conn", {}).get("db_type") or "").lower()
    if src_db_type not in ("postgresql", "postgres"):
        return {"ok": False,
                "error": f"PostgreSQL CDC는 PostgreSQL 소스만 지원합니다 (현재: {src_db_type})"}

    with _running_lock:
        if cdc_id in _running:
            return {"ok": False, "error": "이미 실행 중"}
        _running[cdc_id] = {
            "status":     "starting",
            "mode":       "pg_cdc",
            "started_at": _now_kst().isoformat(),
            "stop":       False,
        }

    t = threading.Thread(target=_pg_cdc_loop, args=(cdc_id, config), daemon=True)
    t.start()
    return {"ok": True, "cdc_id": cdc_id, "mode": "pg_cdc"}


def stop_pg_cdc(cdc_id: str) -> dict:
    with _running_lock:
        if cdc_id in _running:
            _running[cdc_id]["stop"] = True
            return {"ok": True}
    return {"ok": False, "error": "실행 중인 CDC 없음"}


def get_pg_cdc_status(cdc_id: str) -> Optional[dict]:
    return _running.get(cdc_id)


def get_all_pg_cdc_status() -> dict:
    return dict(_running)
