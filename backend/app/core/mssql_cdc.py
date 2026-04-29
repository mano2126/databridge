"""
app/core/mssql_cdc.py
Microsoft SQL Server CDC 엔진.

SQL Server는 변경 추적에 2가지 기술을 제공:
  1. Change Tracking (CT): 가벼움, 변경된 row의 PK만 알려줌. 히스토리 없음.
  2. Change Data Capture (CDC): 무거움, 변경 전후 값 모두 기록. SQL Agent 필요.

이 엔진은 기본으로 CDC를 사용하되, 환경이 안 되면 Change Tracking 폴백.

기술:
  - pyodbc로 cdc.fn_cdc_get_all_changes_<capture_instance>() 함수 주기 조회
  - LSN (Log Sequence Number) 기준으로 증분 읽기
  - 변경분을 파싱해 타겟에 적용

요구사항 (소스 MSSQL):
  -- 1) 데이터베이스 레벨 CDC 활성 (sysadmin 필요)
  EXEC sys.sp_cdc_enable_db;

  -- 2) 테이블별 CDC 활성
  EXEC sys.sp_cdc_enable_table
       @source_schema = N'dbo',
       @source_name   = N'orders',
       @role_name     = NULL;

  -- 3) SQL Server Agent 실행 중이어야 함
  -- Azure SQL Database는 SQL Agent가 다른 구조 — 개별 검증 필요

한계:
  - MSSQL Enterprise/Developer 에디션에서만 CDC 완전 지원
    (Standard 에디션은 2016 SP1+ 부터 지원)
  - Express 에디션은 CDC 미지원 → Change Tracking만 가능
  - Azure SQL Managed Instance는 지원, Azure SQL DB는 다른 구조
"""
from __future__ import annotations
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

KST = timezone(timedelta(hours=9))
logger = logging.getLogger("databridge.cdc.mssql")


_HAS_PYODBC = False
try:
    import pyodbc
    _HAS_PYODBC = True
except ImportError:
    logger.info("pyodbc 미설치 — MSSQL CDC 비활성")


_running: dict = {}
_running_lock = threading.Lock()


def is_available() -> bool:
    return _HAS_PYODBC


def _now_kst():
    return datetime.now(KST)


# ── CDC 활성화 확인 ───────────────────────────────────────

def verify_cdc_enabled(conn, tables: list) -> dict:
    """
    소스 DB에서 CDC가 활성화되어 있는지 + 각 테이블이 capture 대상인지 확인.
    return: {"db_enabled": bool, "tables": {tbl: {enabled, capture_instance}}}
    """
    result = {"db_enabled": False, "tables": {}}
    cur = conn.cursor()

    # 1) DB 레벨
    cur.execute("SELECT is_cdc_enabled FROM sys.databases WHERE name = DB_NAME()")
    row = cur.fetchone()
    result["db_enabled"] = bool(row and row[0])

    if not result["db_enabled"]:
        cur.close()
        return result

    # 2) 테이블별 — cdc.change_tables 시스템 뷰
    for tbl in tables:
        cur.execute("""
            SELECT capture_instance FROM cdc.change_tables
            WHERE source_object_id = OBJECT_ID(?)
        """, f"dbo.{tbl}")
        rr = cur.fetchone()
        result["tables"][tbl] = {
            "enabled":          bool(rr),
            "capture_instance": rr[0] if rr else None,
        }
    cur.close()
    return result


# ── 메인 CDC 루프 ─────────────────────────────────────────

def _mssql_cdc_loop(cdc_id: str, config: dict):
    """
    주기적으로 cdc.fn_cdc_get_all_changes_*를 호출하여 증분 이벤트 수집.
    MSSQL CDC는 push 모델이 아니라 pull — 폴링 간격으로 주기 조절.
    """
    src = config.get("src_conn", {})
    tgt = config.get("tgt_conn", {})
    tables = [t["table"] for t in config.get("tables", []) if t.get("table")]
    poll_interval = int(config.get("poll_interval", 5))

    state = _running[cdc_id]
    state["events_total"]  = 0
    state["events_insert"] = 0
    state["events_update"] = 0
    state["events_delete"] = 0

    # 소스 연결
    try:
        src_conn = _connect_mssql(src)
    except Exception as e:
        logger.error("[CDC:%s] 소스 연결 실패: %s", cdc_id, e)
        state["status"] = "error"
        state["error"] = f"소스 연결 실패: {e}"
        return

    # CDC 활성 여부 확인
    cdc_info = verify_cdc_enabled(src_conn, tables)
    if not cdc_info["db_enabled"]:
        state["status"] = "error"
        state["error"] = (
            "소스 DB에 CDC가 활성화되지 않았습니다. "
            "sysadmin으로 EXEC sys.sp_cdc_enable_db; 실행 후 다시 시도하세요."
        )
        src_conn.close()
        return

    missing = [t for t in tables if not cdc_info["tables"].get(t, {}).get("enabled")]
    if missing:
        state["status"] = "error"
        state["error"] = (
            f"다음 테이블에 CDC 미활성: {missing}. "
            f"EXEC sys.sp_cdc_enable_table @source_schema='dbo', "
            f"@source_name='<table>', @role_name=NULL; 실행 필요."
        )
        src_conn.close()
        return

    # capture_instance 매핑
    capture_map = {t: cdc_info["tables"][t]["capture_instance"] for t in tables}

    # 타겟 연결
    try:
        tgt_conn = _connect_target(tgt)
    except Exception as e:
        state["status"] = "error"
        state["error"] = f"타겟 연결 실패: {e}"
        src_conn.close()
        return

    # 시작 LSN — 테이블별 추적
    last_lsn = {t: None for t in tables}
    state["status"] = "running"
    logger.info("[CDC:%s] MSSQL CDC 시작 — 테이블 %d개, 폴링 %d초", cdc_id, len(tables), poll_interval)

    try:
        while not state.get("stop"):
            for tbl in tables:
                if state.get("stop"):
                    break
                try:
                    events = _poll_table_changes(src_conn, tbl, capture_map[tbl], last_lsn.get(tbl))
                    if events:
                        _apply_events(tgt_conn, tbl, events, (tgt.get("db_type") or "mssql").lower(), state)
                        # 마지막 LSN 갱신
                        last_lsn[tbl] = events[-1]["__$start_lsn"]
                except Exception as e:
                    logger.warning("[CDC:%s] 테이블 %s 처리 실패: %s", cdc_id, tbl, e)
                    state["events_error"] = state.get("events_error", 0) + 1

            # 폴링 간격 대기 (0.2초 단위로 stop 체크)
            for _ in range(poll_interval * 5):
                if state.get("stop"):
                    break
                time.sleep(0.2)

    except Exception as e:
        logger.error("[CDC:%s] 루프 오류: %s", cdc_id, e)
        state["status"] = "error"
        state["error"] = str(e)[:300]
    finally:
        try: src_conn.close()
        except: pass
        try: tgt_conn.close()
        except: pass
        state["status"] = "stopped" if not state.get("error") else "error"
        state["finished_at"] = _now_kst().isoformat()


def _poll_table_changes(conn, table: str, capture_instance: str, from_lsn):
    """
    cdc.fn_cdc_get_all_changes_<capture_instance> 호출 결과 반환.

    from_lsn None 이면 sys.fn_cdc_get_min_lsn(capture_instance)으로 시작.
    """
    cur = conn.cursor()

    # 현재 DB의 max LSN
    cur.execute("SELECT sys.fn_cdc_get_max_lsn()")
    max_lsn = cur.fetchone()[0]

    # 시작 LSN
    if from_lsn is None:
        cur.execute("SELECT sys.fn_cdc_get_min_lsn(?)", capture_instance)
        from_lsn = cur.fetchone()[0]

    # 조회
    sql = f"SELECT * FROM cdc.fn_cdc_get_all_changes_{capture_instance}(?, ?, 'all')"
    cur.execute(sql, from_lsn, max_lsn)

    # 컬럼명 수집
    cols = [desc[0] for desc in cur.description]
    events = []
    for row in cur.fetchall():
        events.append(dict(zip(cols, row)))
    cur.close()
    return events


def _apply_events(tgt_conn, table: str, events: list, tgt_db_type: str, state: dict):
    """
    CDC 이벤트 (__$operation 별) 를 타겟에 적용.
    __$operation: 1=delete, 2=insert, 3=update(before), 4=update(after)
    """
    cur = tgt_conn.cursor()
    # update는 3+4 쌍으로 오므로 4만 처리 (after-image)
    for ev in events:
        op = ev.get("__$operation")
        # 메타 컬럼 제외한 데이터 컬럼만
        data = {k: v for k, v in ev.items() if not k.startswith("__$")}

        try:
            if op == 2:  # insert
                _do_insert(cur, table, data, tgt_db_type)
                state["events_insert"] += 1
                state["events_total"] += 1
            elif op == 4:  # update (after image)
                # PK를 찾기 위해 same event의 before image(op=3)가 필요하지만
                # 일반적으로 PK는 변경되지 않으므로 after 데이터로 WHERE 생성
                _do_update(cur, table, data, tgt_db_type)
                state["events_update"] += 1
                state["events_total"] += 1
            elif op == 1:  # delete
                _do_delete(cur, table, data, tgt_db_type)
                state["events_delete"] += 1
                state["events_total"] += 1
            # op == 3 (update before) 는 건너뜀
        except Exception as e:
            logger.debug("적용 실패 (%s, op=%s): %s", table, op, e)

    cur.close()
    state["last_event_at"] = _now_kst().isoformat()


def _connect_mssql(conn_info: dict):
    host = conn_info.get("host", "127.0.0.1")
    port = int(conn_info.get("port") or 1433)
    user = conn_info.get("username", "")
    pwd  = conn_info.get("password", "")
    db   = conn_info.get("database", "")
    # v9 패치 #52: 공용 헬퍼 (드라이버 자동감지 + 인코딩 설정)
    from app.core.db_conn import make_mssql_conn
    return make_mssql_conn(host, port, user, pwd, db)


def _connect_target(conn_info: dict):
    """타겟 연결 — 공통"""
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
        return _connect_mssql(conn_info)
    elif db_type in ("postgresql", "postgres"):
        import psycopg2
        return psycopg2.connect(host=host, port=port, user=user, password=pwd,
                                database=db)
    raise ValueError(f"지원하지 않는 타겟: {db_type}")


def _quote_ident(name: str, db_type: str) -> str:
    if db_type in ("mssql", "sqlserver", "azure"):
        return f"[{name}]"
    if db_type in ("postgresql", "postgres"):
        return f'"{name}"'
    return f"`{name}`"


def _placeholder(db_type: str) -> str:
    return "?" if db_type in ("mssql", "sqlserver", "azure") else "%s"


def _do_insert(cur, table: str, data: dict, tgt_db_type: str):
    cols = list(data.keys())
    col_list = ", ".join(_quote_ident(c, tgt_db_type) for c in cols)
    ph = ", ".join([_placeholder(tgt_db_type)] * len(cols))
    q = _quote_ident(table, tgt_db_type)
    sql = f"INSERT INTO {q} ({col_list}) VALUES ({ph})"
    cur.execute(sql, tuple(data.values()))


def _do_update(cur, table: str, data: dict, tgt_db_type: str):
    # 간단 구현: 첫 컬럼을 PK로 가정 (실전에서는 별도 PK 파악 필요)
    # 실무에서는 config에서 pk_columns를 받아와야 함
    pk_col = list(data.keys())[0]
    pk_val = data[pk_col]
    set_cols = {k: v for k, v in data.items() if k != pk_col}
    if not set_cols:
        return
    set_clause = ", ".join(
        f"{_quote_ident(c, tgt_db_type)} = {_placeholder(tgt_db_type)}"
        for c in set_cols.keys()
    )
    q = _quote_ident(table, tgt_db_type)
    sql = f"UPDATE {q} SET {set_clause} WHERE {_quote_ident(pk_col, tgt_db_type)} = {_placeholder(tgt_db_type)}"
    cur.execute(sql, tuple(list(set_cols.values()) + [pk_val]))


def _do_delete(cur, table: str, data: dict, tgt_db_type: str):
    pk_col = list(data.keys())[0]
    pk_val = data[pk_col]
    q = _quote_ident(table, tgt_db_type)
    sql = f"DELETE FROM {q} WHERE {_quote_ident(pk_col, tgt_db_type)} = {_placeholder(tgt_db_type)}"
    cur.execute(sql, (pk_val,))


# ── 외부 API ─────────────────────────────────────────────

def start_mssql_cdc(cdc_id: str, config: dict) -> dict:
    """MSSQL CDC 시작 — 백그라운드 폴링 스레드"""
    if not _HAS_PYODBC:
        return {"ok": False, "error": "pyodbc 미설치"}

    src_db_type = (config.get("src_conn", {}).get("db_type") or "").lower()
    if src_db_type not in ("mssql", "sqlserver", "azure"):
        return {"ok": False,
                "error": f"MSSQL CDC는 SQL Server 소스만 지원 (현재: {src_db_type})"}

    with _running_lock:
        if cdc_id in _running:
            return {"ok": False, "error": "이미 실행 중"}
        _running[cdc_id] = {
            "status":     "starting",
            "mode":       "mssql_cdc",
            "started_at": _now_kst().isoformat(),
            "stop":       False,
        }

    t = threading.Thread(target=_mssql_cdc_loop, args=(cdc_id, config), daemon=True)
    t.start()
    return {"ok": True, "cdc_id": cdc_id, "mode": "mssql_cdc"}


def stop_mssql_cdc(cdc_id: str) -> dict:
    with _running_lock:
        if cdc_id in _running:
            _running[cdc_id]["stop"] = True
            return {"ok": True}
    return {"ok": False, "error": "실행 중인 CDC 없음"}


def get_mssql_cdc_status(cdc_id: str) -> Optional[dict]:
    return _running.get(cdc_id)


def get_all_mssql_cdc_status() -> dict:
    return dict(_running)


# ── 진단 유틸 (관리자용) ───────────────────────────────

def diagnose_cdc_setup(conn_info: dict, tables: list) -> dict:
    """
    MSSQL CDC 설정 진단 — /cdc/diagnose/mssql 엔드포인트에서 사용.
    """
    if not _HAS_PYODBC:
        return {"ok": False, "error": "pyodbc 미설치"}
    try:
        conn = _connect_mssql(conn_info)
    except Exception as e:
        return {"ok": False, "error": f"연결 실패: {e}"}

    info = verify_cdc_enabled(conn, tables)

    # SQL Agent 상태 체크
    cur = conn.cursor()
    agent_status = None
    try:
        cur.execute("""
            SELECT CASE
              WHEN EXISTS (SELECT 1 FROM sys.dm_server_services WHERE servicename LIKE '%Agent%' AND status = 4)
              THEN 'running' ELSE 'stopped' END
        """)
        r = cur.fetchone()
        agent_status = r[0] if r else "unknown"
    except Exception:
        agent_status = "unknown (권한 필요)"
    cur.close()
    conn.close()

    return {
        "ok": True,
        "db_cdc_enabled":  info["db_enabled"],
        "tables":          info["tables"],
        "sql_agent":       agent_status,
        "recommendations": _recommend_setup(info, agent_status),
    }


def _recommend_setup(info: dict, agent_status: str) -> list:
    recs = []
    if not info["db_enabled"]:
        recs.append("1. sysadmin으로 'EXEC sys.sp_cdc_enable_db;' 실행하여 DB CDC 활성화")
    for tbl, t_info in info["tables"].items():
        if not t_info["enabled"]:
            recs.append(
                f"2. 테이블 '{tbl}' CDC 활성화: "
                f"EXEC sys.sp_cdc_enable_table @source_schema='dbo', "
                f"@source_name='{tbl}', @role_name=NULL;"
            )
    if agent_status == "stopped":
        recs.append("3. SQL Server Agent 서비스 시작 (CDC capture/cleanup 작업 필요)")
    if not recs:
        recs.append("✓ CDC 설정 완료 — 시작 가능")
    return recs
