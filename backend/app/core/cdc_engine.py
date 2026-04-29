"""
app/core/cdc_engine.py  v2.1
변경분 이관 엔진 (타임스탬프 기반 CDC) — 견고화 버전

개선 사항:
  - 22007: last_sync 마이크로초 자동 정리
  - HY000: PK 조회 시 별도 커넥션 사용
  - 타임아웃: 재연결 로직 (최대 3회)
  - 데이터 타입 오류: 행 단위 폴백 처리
  - 1146: 타겟 테이블 없음 명확한 안내
  - 배치 커밋 실패: 롤백 후 재시도
  - crec_recfile 같은 VIEW 참조 오류: 오류 격리
"""

import logging
import re
import threading
import time
from datetime import datetime, timezone, timedelta
KST = timezone(timedelta(hours=9))
def _now_kst(): return datetime.now(KST)
from typing import Optional

from app.core.store import Store

logger = logging.getLogger("databridge.cdc")

_cdc_state   = Store("cdc_state")
_running: dict = {}
_running_lock  = threading.Lock()

MAX_RETRY      = 3          # 배치 실패 시 최대 재시도
RETRY_WAIT     = 2          # 재시도 대기 초
CONN_TIMEOUT   = 30         # DB 연결 타임아웃 (초)
BATCH_LOG_EVERY = 5         # N 배치마다 진행 로그


# ── DB 연결 ──────────────────────────────────────────────────────

def _connect(conn_info: dict, timeout: int = CONN_TIMEOUT):
    db_type = (conn_info.get("db_type") or "mysql").lower()
    host    = conn_info.get("host", "127.0.0.1")
    port    = int(conn_info.get("port") or 3306)
    user    = conn_info.get("username", "")
    pwd     = conn_info.get("password", "")
    db      = conn_info.get("database", "")

    if db_type in ("mssql", "sqlserver", "azure"):
        # v9 패치 #52: 공용 헬퍼 사용 (드라이버 자동감지 + 인코딩 설정)
        from app.core.db_conn import make_mssql_conn
        return make_mssql_conn(host, port, user, pwd, db, timeout=timeout)

    elif db_type in ("mysql", "aurora", "mariadb", "tidb", "cloudsql"):
        import pymysql
        return pymysql.connect(
            host=host, port=port, user=user, password=pwd,
            database=db, charset="utf8mb4",
            connect_timeout=timeout, read_timeout=3600,
            write_timeout=3600, autocommit=False,
        )

    elif db_type in ("postgresql", "postgres"):
        import psycopg2
        return psycopg2.connect(
            host=host, port=port, user=user, password=pwd,
            dbname=db, connect_timeout=timeout,
        )

    raise ValueError(f"지원하지 않는 DB: {db_type}")


def _reconnect(conn_info: dict, old_conn, log_fn) -> object:
    """연결이 끊겼을 때 재연결"""
    try:
        if old_conn: old_conn.close()
    except Exception: pass
    for attempt in range(1, MAX_RETRY + 1):
        try:
            log_fn("warn", f"재연결 시도 {attempt}/{MAX_RETRY}...")
            conn = _connect(conn_info)
            log_fn("info", "재연결 성공")
            return conn
        except Exception as e:
            if attempt < MAX_RETRY:
                time.sleep(RETRY_WAIT * attempt)
            else:
                raise RuntimeError(f"재연결 실패: {e}")


def _is_alive(conn, db_type: str) -> bool:
    """커넥션 살아있는지 확인"""
    try:
        cur = conn.cursor()
        if db_type in ("mssql", "sqlserver", "azure"):
            cur.execute("SELECT 1")
        else:
            cur.execute("SELECT 1")
        cur.close()
        return True
    except Exception:
        return False


# ── 날짜 정규화 ───────────────────────────────────────────────────

def _clean_dt(val: str, add_ms: int = 0) -> str:
    """
    last_sync 값 정규화
    - 마이크로초 6자리 → 밀리초 3자리로 축소 (22007 방지)
    - add_ms: 밀리초 추가 (last_sync 저장 시 중복 방지용)
    """
    if not val:
        return "1900-01-01 00:00:00"
    s = str(val)
    # 마이크로초 .NNNNNN → .NNN
    s = re.sub(r'(\.\d{3})\d+', r'\1', s)
    # T 구분자 → 공백
    s = s.replace('T', ' ')
    # +09:00 같은 timezone 제거
    s = re.sub(r'[+-]\d{2}:\d{2}$', '', s).strip()
    # 끝의 Z 제거
    s = s.rstrip('Z').strip()
    if s.startswith('1900') or not s:
        return "1900-01-01 00:00:00"
    # 밀리초 추가 (중복 방지)
    if add_ms:
        try:
            from datetime import datetime, timedelta
            fmt = "%Y-%m-%d %H:%M:%S.%f" if "." in s else "%Y-%m-%d %H:%M:%S"
            dt = datetime.strptime(s, fmt) + timedelta(milliseconds=add_ms)
            s = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:23]  # 밀리초 3자리
        except Exception:
            pass
    return s


# ── SQL 빌더 ─────────────────────────────────────────────────────

def _quote(db_type: str, name: str) -> str:
    if db_type in ("mssql", "sqlserver", "azure"):
        return f"[{name}]"
    elif db_type in ("postgresql", "postgres"):
        return f'"{name}"'
    return f"`{name}`"


def _placeholder(db_type: str) -> str:
    return "?" if db_type in ("mssql", "sqlserver", "azure") else "%s"


def _build_select(db_type: str, table: str, ts_col: str,
                  last_sync: str, extra_where: str = "") -> tuple:
    """SELECT SQL + 파라미터 반환"""
    q  = _quote(db_type, table)
    qc = _quote(db_type, ts_col)
    ph = _placeholder(db_type)
    nolock = " WITH(NOLOCK)" if db_type in ("mssql","sqlserver","azure") else ""

    where = f"{qc} > {ph}"
    if extra_where.strip():
        # AND가 앞에 있으면 제거 후 붙이기
        extra = extra_where.strip()
        if extra.upper().startswith("AND "):
            extra = extra[4:].strip()
        where += f" AND {extra}"

    sql = f"SELECT * FROM {q}{nolock} WHERE {where} ORDER BY {qc}"
    return sql, [last_sync]


def _build_upsert(db_type: str, table: str, cols: list, pk_cols: list) -> str:
    q = _quote
    non_pk = [c for c in cols if c not in pk_cols]
    if not pk_cols:
        return _build_insert_ignore(db_type, table, cols)

    if db_type in ("mysql", "aurora", "mariadb", "tidb", "cloudsql"):
        cs  = ", ".join(q(db_type, c) for c in cols)
        vs  = ", ".join(["%s"] * len(cols))
        upd = ", ".join(f"{q(db_type,c)}=VALUES({q(db_type,c)})" for c in non_pk) or f"{q(db_type,pk_cols[0])}=VALUES({q(db_type,pk_cols[0])})"
        return f"INSERT INTO {q(db_type,table)} ({cs}) VALUES ({vs}) ON DUPLICATE KEY UPDATE {upd}"

    elif db_type in ("postgresql", "postgres"):
        cs  = ", ".join(q(db_type, c) for c in cols)
        vs  = ", ".join(["%s"] * len(cols))
        pks = ", ".join(q(db_type, c) for c in pk_cols)
        upd = ", ".join(f"{q(db_type,c)}=EXCLUDED.{q(db_type,c)}" for c in non_pk) or f"{q(db_type,pk_cols[0])}=EXCLUDED.{q(db_type,pk_cols[0])}"
        return f"INSERT INTO {q(db_type,table)} ({cs}) VALUES ({vs}) ON CONFLICT ({pks}) DO UPDATE SET {upd}"

    elif db_type in ("mssql", "sqlserver", "azure"):
        # v9 패치 #49: MSSQL MERGE 파라미터 불일치 버그 수정
        # 기존: USING (SELECT ? AS c1, ? AS c2) + INSERT(...) VALUES (?, ?)
        #       → 파라미터 2*N 개 필요한데 executemany 는 N 개만 전달 → 오류
        # 수정: INSERT 에서 VALUES 대신 s.컬럼 참조 → 파라미터 N 개만 사용
        cs   = ", ".join(q(db_type, c) for c in cols)
        on_c = " AND ".join(f"t.{q(db_type,c)}=s.{q(db_type,c)}" for c in pk_cols)
        upd  = ", ".join(f"t.{q(db_type,c)}=s.{q(db_type,c)}" for c in non_pk) or f"t.{q(db_type,pk_cols[0])}=s.{q(db_type,pk_cols[0])}"
        src_sel = ", ".join(f"? AS {q(db_type,c)}" for c in cols)
        insert_cols = cs
        insert_vals = ", ".join(f"s.{q(db_type,c)}" for c in cols)   # ← 핵심: s.컬럼 참조
        return (
            f"MERGE INTO {q(db_type,table)} AS t "
            f"USING (SELECT {src_sel}) AS s ON ({on_c}) "
            f"WHEN MATCHED THEN UPDATE SET {upd} "
            f"WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals});"
        )
    raise ValueError(f"UPSERT 미지원: {db_type}")


def _build_insert_ignore(db_type: str, table: str, cols: list) -> str:
    q  = _quote
    cs = ", ".join(q(db_type, c) for c in cols)
    ph = _placeholder(db_type)
    vs = ", ".join([ph] * len(cols))
    if db_type in ("mysql", "aurora", "mariadb", "tidb", "cloudsql"):
        return f"INSERT IGNORE INTO {q(db_type,table)} ({cs}) VALUES ({vs})"
    elif db_type in ("postgresql", "postgres"):
        return f"INSERT INTO {q(db_type,table)} ({cs}) VALUES ({vs}) ON CONFLICT DO NOTHING"
    # MSSQL — 중복 무시 불가, 일반 INSERT (PK 없으면 중복 허용)
    return f"INSERT INTO {q(db_type,table)} ({cs}) VALUES ({vs})"


# ── PK 조회 ──────────────────────────────────────────────────────

def _get_pk_columns(conn_info: dict, db_type: str, database: str, table: str) -> list:
    """별도 커넥션으로 PK 조회 (HY000 방지)"""
    conn = cur = None
    try:
        conn = _connect(conn_info, timeout=10)
        cur  = conn.cursor()
        db   = db_type.lower()
        if db in ("mssql", "sqlserver", "azure"):
            cur.execute("""
                SELECT c.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE c
                  ON tc.CONSTRAINT_NAME=c.CONSTRAINT_NAME
                WHERE tc.TABLE_NAME=? AND tc.CONSTRAINT_TYPE='PRIMARY KEY'
                ORDER BY c.ORDINAL_POSITION
            """, [table])
        elif db in ("mysql", "aurora", "mariadb"):
            cur.execute("""
                SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
                  AND CONSTRAINT_NAME='PRIMARY'
                ORDER BY ORDINAL_POSITION
            """, [database, table])
        elif db in ("postgresql", "postgres"):
            cur.execute("""
                SELECT a.attname FROM pg_index i
                JOIN pg_attribute a ON a.attrelid=i.indrelid
                  AND a.attnum=ANY(i.indkey)
                WHERE i.indrelid=%s::regclass AND i.indisprimary
            """, [table])
        return [r[0] for r in cur.fetchall()]
    except Exception as e:
        logger.warning("PK 조회 실패 [%s]: %s", table, e)
        return []
    finally:
        try: cur.close() if cur else None
        except Exception: pass
        try: conn.close() if conn else None
        except Exception: pass


# ── 타겟 테이블 존재 확인 ─────────────────────────────────────────

def _target_table_exists(conn, db_type: str, database: str, table: str) -> bool:
    cur = None
    try:
        cur = conn.cursor()
        db  = db_type.lower()
        if db in ("mssql", "sqlserver", "azure"):
            cur.execute(
                "SELECT 1 FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_NAME=? AND TABLE_TYPE='BASE TABLE'", [table]
            )
        elif db in ("mysql", "aurora", "mariadb"):
            cur.execute(
                "SELECT 1 FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s", [database, table]
            )
        elif db in ("postgresql", "postgres"):
            cur.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name=%s", [table]
            )
        return cur.fetchone() is not None
    except Exception:
        return False
    finally:
        try: cur.close() if cur else None
        except Exception: pass


# ── 데이터 타입 안전 변환 ─────────────────────────────────────────

def _safe_row(row: list, cols_meta: list) -> list:
    """
    행 데이터 타입 정규화
    - bytes → 헥스 문자열
    - datetime 마이크로초 → 밀리초
    - None 유지
    """
    result = []
    for val in row:
        if val is None:
            result.append(None)
        elif isinstance(val, (bytes, bytearray)):
            result.append(val.hex() if val else None)
        elif isinstance(val, datetime):
            # 마이크로초 제거
            result.append(val.replace(microsecond=(val.microsecond // 1000) * 1000))
        else:
            result.append(val)
    return result


# ── 배치 실행 (재시도 포함) ──────────────────────────────────────

def _has_identity_column(tgt_conn, tgt_db_type: str, table: str) -> bool:
    """
    v9 패치 #59: MSSQL 타겟 테이블에 IDENTITY 컬럼이 있는지 확인.
    있으면 INSERT 시 SET IDENTITY_INSERT ON 이 필요함.
    """
    if tgt_db_type not in ("mssql", "sqlserver", "azure"):
        return False
    try:
        cur = tgt_conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM sys.columns
            WHERE object_id = OBJECT_ID(?) AND is_identity = 1
        """, [f"dbo.{table}"])
        row = cur.fetchone()
        return bool(row and row[0] > 0)
    except Exception:
        return False


def _exec_batch(cur, sql: str, rows: list, tgt_conn,
                tgt_db_type: str, table: str, log_fn) -> tuple:
    """
    배치 INSERT/UPSERT 실행
    실패 시 행 단위 폴백 → (성공건수, 실패건수) 반환
    """
    # v9 패치 #59: MSSQL IDENTITY 컬럼 있으면 IDENTITY_INSERT ON
    # (소스 PK 값을 타겟에 그대로 유지하려면 필수)
    identity_on = False
    if tgt_db_type in ("mssql", "sqlserver", "azure") and _has_identity_column(tgt_conn, tgt_db_type, table):
        try:
            cur.execute(f"SET IDENTITY_INSERT [{table}] ON")
            identity_on = True
            log_fn("info", f"[{table}] IDENTITY_INSERT ON (자동)")
        except Exception as _ie:
            log_fn("warn", f"[{table}] IDENTITY_INSERT ON 실패: {_ie}")

    try:
        cur.executemany(sql, rows)
        tgt_conn.commit()
        # IDENTITY_INSERT OFF 복원
        if identity_on:
            try: cur.execute(f"SET IDENTITY_INSERT [{table}] OFF")
            except Exception: pass
        return len(rows), 0
    except Exception as batch_err:
        log_fn("warn", f"[{table}] 배치 실패 ({len(rows)}건) — 행 단위 재시도: {str(batch_err)[:100]}")
        try: tgt_conn.rollback()
        except Exception: pass

        # 롤백 후 IDENTITY_INSERT 재설정 (세션 끊기면 초기화됨)
        if tgt_db_type in ("mssql", "sqlserver", "azure") and _has_identity_column(tgt_conn, tgt_db_type, table):
            try:
                cur.execute(f"SET IDENTITY_INSERT [{table}] ON")
                identity_on = True
            except Exception: pass

        ok_cnt = err_cnt = 0
        for row in rows:
            try:
                cur.execute(sql, row)
                tgt_conn.commit()
                ok_cnt += 1
            except Exception as row_err:
                err_cnt += 1
                try: tgt_conn.rollback()
                except Exception: pass
                # 롤백이 세션 상태도 초기화 가능 — IDENTITY_INSERT 재설정
                if identity_on:
                    try: cur.execute(f"SET IDENTITY_INSERT [{table}] ON")
                    except Exception: pass
                if err_cnt <= 3:  # 첫 3건만 로그
                    log_fn("error", f"[{table}] 행 오류: {str(row_err)[:120]}")

        # IDENTITY_INSERT OFF 복원
        if identity_on:
            try: cur.execute(f"SET IDENTITY_INSERT [{table}] OFF")
            except Exception: pass

        return ok_cnt, err_cnt


# ── 메인 CDC 실행 ────────────────────────────────────────────────

def run_cdc(cdc_id: str, config: dict, on_log=None):
    """
    CDC 이관 실행 (견고화 버전)
    """
    _cur_table = [""]

    def log(level, msg):
        logger.info("[CDC:%s] %s", cdc_id, msg)
        if on_log:
            on_log(level, msg)
        try:
            from app.api.routes.jobs import _job_logs
            from datetime import datetime as _dt
            tag = f"CDC/{_cur_table[0]}" if _cur_table[0] else "CDC"
            _job_logs.setdefault(cdc_id, []).append({
                "time":    _dt.now(timezone(timedelta(hours=9))).strftime("%H:%M:%S"),
                "level":   level,
                "tag":     tag,
                "message": msg,
            })
            if len(_job_logs[cdc_id]) > 500:
                _job_logs[cdc_id] = _job_logs[cdc_id][-500:]
        except Exception:
            pass

    with _running_lock:
        if cdc_id in _running:
            return {"ok": False, "error": "이미 실행 중"}
        _running[cdc_id] = {
            "status": "running", "started_at": _now_kst().isoformat(),
            "logs": [], "results": [], "current_table": "",
        }
    state = _running[cdc_id]

    # ── jobs.json 등록 ──────────────────────────────────────────
    from app.core.store import Store as _Store
    _jstore = _Store("jobs")
    src_ci = config.get("src_conn", {})
    tgt_ci = config.get("tgt_conn", {})
    tables = config.get("tables", [])
    src_db  = src_ci.get("db_type","mssql").lower()
    tgt_db  = tgt_ci.get("db_type","mysql").lower()
    tgt_dbname = tgt_ci.get("database","")
    batch_size = config.get("batch_size", 5000)

    # CDC 는 매 실행마다 새 Job 생성 (실시간 모니터에서 그룹화로 묶여 보임)
    try:
        _jstore.set(cdc_id, {
            "id": cdc_id, "name": config.get("name", "CDC 이관") + " [CDC]",
            "job_type": "cdc", "status": "running",
            # v9 #64: cdc_cfg_id 를 별도 필드로 보관 (Job 관리 페이지에서 그룹화 키로 사용)
            "cdc_cfg_id": config.get("id", cdc_id),
            "src_db": src_ci.get("db_type","mssql"), "tgt_db": tgt_ci.get("db_type","mysql"),
            "src_host": src_ci.get("host",""), "src_database": src_ci.get("database",""),
            "tgt_host": tgt_ci.get("host",""), "tgt_database": tgt_ci.get("database",""),
            "progress": 0, "rows_processed": 0, "rows_total": 0,
            "rows_error": 0, "table_done": 0, "table_total": len(tables),
            "current_table": "", "phase": "CDC",
            "item_statuses": {
                t["table"]: {"type":"table","status":"pending","rows":0,
                             "error":None,"started_at":None,"finished_at":None}
                for t in tables
            },
            "created_at": _now_kst().isoformat(),
            "started_at": _now_kst().isoformat(),
            "finished_at": None, "error_message": None,
        })
        log("info", f"CDC Job 등록 — id={cdc_id[:12]}")
    except Exception as _je:
        logger.warning("CDC Job 등록 실패: %s", _je)
    state_key  = f"{src_ci['host']}:{src_ci['database']}→{tgt_ci['host']}:{tgt_ci['database']}"

    src_conn = tgt_conn = None
    total_rows = total_errors = 0

    def _update_jstore(extra: dict = None):
        try:
            upd = {
                "rows_processed": total_rows,
                "rows_error":     total_errors,
                "current_table":  _cur_table[0],
            }
            if extra: upd.update(extra)
            _jstore.bulk_update(cdc_id, upd)
        except Exception: pass

    try:
        log("info", f"CDC 시작 — {state_key}")
        src_conn = _connect(src_ci)
        tgt_conn = _connect(tgt_ci)

        for tbl_cfg in tables:
            if state.get("stop"):
                log("warn", "사용자 중단")
                break

            table       = tbl_cfg["table"]
            ts_col      = tbl_cfg.get("ts_col","").strip()
            extra_where = tbl_cfg.get("extra_where","").strip()
            strategy    = tbl_cfg.get("strategy","append").lower()

            _cur_table[0] = table
            log("info", f"[{table}] 시작 — 전략:{strategy}")

            # 소스 last_sync 로드
            # 우선순위: 저장된 last_sync > base_date > 1900(전체)
            # base_date는 최초 이관 시작점, 이후엔 last_sync 우선 사용
            saved_state  = _cdc_state.get(state_key) or {}
            tbl_state    = saved_state.get(table, {})
            base_date    = tbl_cfg.get("base_date","").strip()
            saved_sync   = tbl_state.get("last_sync","")
            if saved_sync and not saved_sync.startswith("1900"):
                # 이미 이관 이력 있음 → last_sync 우선
                last_sync = _clean_dt(saved_sync)
            else:
                # 최초 이관 → base_date 또는 전체(1900)
                last_sync = _clean_dt(base_date or "1900-01-01 00:00:00")
            log("info", f"[{table}] last_sync = {last_sync} (saved={bool(saved_sync)})")

            tbl_result = {"table":table,"strategy":strategy,"rows":0,"errors":0,"status":"running","error":None}
            state["results"].append(tbl_result)

            # jobs.json 시작 업데이트
            try:
                done_cnt = sum(1 for r in state["results"] if r["status"]=="done")
                cur_st = (_jstore.get(cdc_id) or {}).get("item_statuses",{})
                cur_st[table] = {"type":"table","status":"running","rows":0,"error":None,
                                 "started_at":_now_kst().isoformat(),"finished_at":None}
                _jstore.bulk_update(cdc_id, {
                    "item_statuses": cur_st, "current_table": table,
                    "table_done": done_cnt,
                    "progress": round(done_cnt/max(len(tables),1)*100),
                })
            except Exception: pass

            src_cur = tgt_cur = None
            try:
                # ── 커넥션 살아있는지 확인 후 재연결 ───────────
                if not _is_alive(src_conn, src_db):
                    src_conn = _reconnect(src_ci, src_conn, log)
                if not _is_alive(tgt_conn, tgt_db):
                    tgt_conn = _reconnect(tgt_ci, tgt_conn, log)

                # ── 타겟 테이블 존재 확인 ───────────────────────
                if not _target_table_exists(tgt_conn, tgt_db, tgt_dbname, table):
                    raise RuntimeError(
                        f"타겟 테이블 없음: {tgt_dbname}.{table} "
                        f"— 전체 이관 후 재시도하거나 CDC 설정에서 제외하세요"
                    )

                src_cur = src_conn.cursor()
                tgt_cur = tgt_conn.cursor()

                # ══ Full-refresh ════════════════════════════════
                if strategy == "full":
                    log("info", f"[{table}] Full-refresh")
                    q = _quote(tgt_db, table)
                    tgt_cur.execute(
                        f"TRUNCATE TABLE {q}" if tgt_db not in ("mssql","sqlserver","azure")
                        else f"DELETE FROM {q}"
                    )
                    tgt_conn.commit()

                    q_src = _quote(src_db, table)
                    nolock = " WITH(NOLOCK)" if src_db in ("mssql","sqlserver","azure") else ""
                    sql_sel = f"SELECT * FROM {q_src}{nolock}"
                    log("info", f"[SQL] {sql_sel}")
                    src_cur.execute(sql_sel)
                    cols = [d[0] for d in src_cur.description]

                    ph  = _placeholder(tgt_db)
                    cs  = ", ".join(_quote(tgt_db, c) for c in cols)
                    vs  = ", ".join([ph]*len(cols))
                    ins = f"INSERT INTO {_quote(tgt_db,table)} ({cs}) VALUES ({vs})"

                    cnt = err_cnt = 0
                    batch_no = 0
                    rows_batch = src_cur.fetchmany(batch_size)
                    while rows_batch:
                        safe_rows = [_safe_row(list(r), cols) for r in rows_batch]
                        ok, err = _exec_batch(tgt_cur, ins, safe_rows, tgt_conn, tgt_db, table, log)
                        cnt += ok; err_cnt += err
                        batch_no += 1
                        if batch_no % BATCH_LOG_EVERY == 0:
                            log("info", f"[{table}] Full 진행 {cnt:,}행...")
                            total_rows += ok
                            _update_jstore()
                            total_rows -= ok  # 최종에서 더하기 위해 임시 제거
                        rows_batch = src_cur.fetchmany(batch_size)

                    tbl_result["rows"]   = cnt
                    tbl_result["errors"] = err_cnt
                    total_rows  += cnt
                    total_errors += err_cnt
                    log("info", f"[{table}] Full 완료 — {cnt:,}행 (오류:{err_cnt})")

                # ══ Append / UPSERT ═════════════════════════════
                else:
                    if not ts_col:
                        raise ValueError(
                            "기준 컬럼(ts_col)이 없습니다. "
                            "Full-refresh 전략으로 변경하거나 기준 컬럼을 설정하세요."
                        )

                    sql_sel, params = _build_select(src_db, table, ts_col, last_sync, extra_where)
                    log("info", f"[SQL] {sql_sel}")
                    log("info", f"[PARAM] {params}")
                    src_cur.execute(sql_sel, params)
                    cols = [d[0] for d in src_cur.description]

                    # PK 조회 (별도 커넥션)
                    # v9 패치 #60: 소스에 PK 없으면 타겟에서도 조회 시도
                    # (MySQL 에서 PK 없이 만들었어도 MSSQL 타겟에 PK 있으면 UPSERT 가능)
                    pk_cols = _get_pk_columns(src_ci, src_db, src_ci.get("database",""), table)
                    if not pk_cols:
                        pk_cols_tgt = _get_pk_columns(tgt_ci, tgt_db, tgt_ci.get("database",""), table)
                        if pk_cols_tgt:
                            log("info", f"[{table}] 소스 PK 없음 → 타겟 PK 사용: {pk_cols_tgt}")
                            pk_cols = pk_cols_tgt

                    # v9 패치 #59: MSSQL IDENTITY 있는데 append 면 중복 PK 충돌 필연 → upsert 로 전환
                    if strategy == "append" and pk_cols and tgt_db in ("mssql","sqlserver","azure"):
                        if _has_identity_column(tgt_conn, tgt_db, table):
                            log("info", f"[{table}] IDENTITY 컬럼 감지 — 전략 append → upsert 자동 전환")
                            strategy = "upsert"

                    if strategy == "upsert":
                        if not pk_cols:
                            log("warn", f"[{table}] PK 없음 — Append로 전환")
                            strategy = "append"

                    if strategy == "upsert":
                        ins_sql = _build_upsert(tgt_db, table, cols, pk_cols)
                    else:
                        ins_sql = _build_insert_ignore(tgt_db, table, cols)
                    log("info", f"[SQL] {ins_sql[:120]}...")

                    cnt = err_cnt = 0
                    batch_no = 0
                    new_last_sync = last_sync
                    rows_batch = src_cur.fetchmany(batch_size)

                    while rows_batch:
                        if state.get("stop"): break

                        # 커넥션 유효성 체크 (대용량 처리 중 타임아웃 대비)
                        if batch_no > 0 and batch_no % 20 == 0:
                            if not _is_alive(tgt_conn, tgt_db):
                                tgt_conn = _reconnect(tgt_ci, tgt_conn, log)
                                tgt_cur  = tgt_conn.cursor()

                        safe_rows = [_safe_row(list(r), cols) for r in rows_batch]

                        ok, err = _exec_batch(tgt_cur, ins_sql, safe_rows, tgt_conn, tgt_db, table, log)
                        cnt += ok; err_cnt += err
                        batch_no += 1

                        # last_sync 추적 — 마지막 행 ts_col + 1ms 저장 (중복 재이관 방지)
                        try:
                            ts_idx = cols.index(ts_col)
                            last_val = rows_batch[-1][ts_idx]
                            if last_val: new_last_sync = _clean_dt(str(last_val), add_ms=1)
                        except (ValueError, IndexError): pass

                        if batch_no % BATCH_LOG_EVERY == 0:
                            log("info", f"[{table}] 진행 {cnt:,}행... (오류:{err_cnt})")
                            total_rows += ok
                            _update_jstore()
                            total_rows -= ok

                        rows_batch = src_cur.fetchmany(batch_size)

                    tbl_result["rows"]   = cnt
                    tbl_result["errors"] = err_cnt
                    total_rows  += cnt
                    total_errors += err_cnt
                    log("info", f"[{table}] 완료 — {cnt:,}행 (오류:{err_cnt})")

                    # last_sync 갱신
                    saved_state = _cdc_state.get(state_key) or {}
                    if cnt > 0:
                        # 이관한 행이 있으면 마지막 ts_col 값으로 갱신 (조건 무관 강제 갱신)
                        saved_state[table] = {
                            "ts_col":      ts_col,
                            "last_sync":   new_last_sync,
                            "strategy":    strategy,
                            "last_run":    _now_kst().strftime("%Y-%m-%d %H:%M:%S"),
                            "last_rows":   cnt,
                            "last_errors": err_cnt,
                        }
                        _cdc_state.set(state_key, saved_state)
                        log("info", f"[{table}] last_sync 갱신 → {new_last_sync}")
                    else:
                        # 변경분 없음 — last_run만 갱신, last_sync는 그대로 유지
                        existing = saved_state.get(table, {})
                        existing["last_run"]  = _now_kst().strftime("%Y-%m-%d %H:%M:%S")
                        existing["last_rows"] = 0
                        saved_state[table] = existing
                        _cdc_state.set(state_key, saved_state)
                        log("info", f"[{table}] 변경분 없음 — last_sync 유지 ({last_sync})")

                tbl_result["status"] = "done" if tbl_result["errors"] == 0 else "done_with_errors"

            except RuntimeError as e:
                # 명확한 오류 (타겟 테이블 없음 등) — 재시도 불필요
                tbl_result["status"] = "error"
                tbl_result["error"]  = str(e)
                log("error", f"[{table}] {e}")
                try: tgt_conn.rollback()
                except Exception: pass
                total_errors += 1

            except Exception as e:
                tbl_result["status"] = "error"
                tbl_result["error"]  = str(e)[:300]
                log("error", f"[{table}] 오류: {e}")
                try: tgt_conn.rollback()
                except Exception: pass
                total_errors += 1

            finally:
                try: src_cur.close() if src_cur else None
                except Exception: pass
                try: tgt_cur.close() if tgt_cur else None
                except Exception: pass

            # jobs.json 테이블 완료 업데이트
            try:
                done_cnt = sum(1 for r in state["results"] if r["status"] in ("done","done_with_errors"))
                cur_st = (_jstore.get(cdc_id) or {}).get("item_statuses",{})
                is_err = tbl_result["status"] == "error"
                cur_st[table] = {
                    "type": "table",
                    "status": "error" if is_err else "done",
                    "rows": tbl_result["rows"],
                    "error": tbl_result.get("error"),
                    "started_at": None,
                    "finished_at": _now_kst().isoformat(),
                }
                _jstore.bulk_update(cdc_id, {
                    "item_statuses": cur_st,
                    "table_done":    done_cnt,
                    "rows_processed": total_rows,
                    "rows_error":    total_errors,
                    "progress":      round(done_cnt/max(len(tables),1)*100),
                    "current_table": table,
                })
            except Exception: pass

        # ── 전체 완료 ──────────────────────────────────────────
        state["status"]     = "completed"
        state["finished_at"]= _now_kst().isoformat()
        state["total_rows"] = total_rows
        log("info", f"CDC 완료 — {total_rows:,}행 반영 / 오류:{total_errors}건")
        try:
            _jstore.bulk_update(cdc_id, {
                "status": "completed",
                "finished_at": _now_kst().isoformat(),
                "rows_processed": total_rows, "rows_error": total_errors,
                "progress": 100, "table_done": len(tables), "current_table": "",
            })
            # v9 #64: 실행 이력을 audit_logs 에 영구 기록 (Job 삭제돼도 유지)
            try:
                from app.core import audit as _audit
                _started_at = state.get("started_at") or _now_kst().isoformat()
                _finished_at = _now_kst().isoformat()
                try:
                    _s = datetime.fromisoformat(_started_at.replace("Z",""))
                    _f = datetime.fromisoformat(_finished_at.replace("Z",""))
                    _dur_sec = max(0, (_f - _s).total_seconds())
                except Exception:
                    _dur_sec = 0
                _audit.record(
                    action="cdc.run.complete",
                    resource="cdc",
                    resource_id=config.get("id", cdc_id),   # cfg_id 를 리소스 ID 로
                    status="ok",
                    details={
                        "name":          config.get("name", "CDC 이관"),
                        "job_id":        cdc_id,
                        "started_at":    _started_at,
                        "finished_at":   _finished_at,
                        "duration_sec":  _dur_sec,
                        "rows":          total_rows,
                        "errors":        total_errors,
                        "table_total":   len(tables),
                    },
                )
            except Exception: pass
        except Exception: pass

    except Exception as e:
        state["status"] = "error"
        state["error"]  = str(e)
        # v9 #61: latin-1 재발 진단용 traceback 추가
        import traceback as _tb
        _tb_text = _tb.format_exc()
        log("error", f"CDC 치명 오류: {e}")
        log("error", f"Traceback:\n{_tb_text}")
        try:
            _jstore.bulk_update(cdc_id, {
                "status": "error",
                "finished_at": _now_kst().isoformat(),
                "last_run_at":  _now_kst().isoformat(),
                "last_result":  "error",
                "error_message": str(e)[:200],
            })
            # v9 #64: 오류도 audit 기록
            try:
                from app.core import audit as _audit
                _started_at = state.get("started_at") or _now_kst().isoformat()
                _finished_at = _now_kst().isoformat()
                try:
                    _s = datetime.fromisoformat(_started_at.replace("Z",""))
                    _f = datetime.fromisoformat(_finished_at.replace("Z",""))
                    _dur_sec = max(0, (_f - _s).total_seconds())
                except Exception:
                    _dur_sec = 0
                _audit.record(
                    action="cdc.run.error",
                    resource="cdc",
                    resource_id=cdc_id,
                    status="fail",
                    details={
                        "name":         config.get("name", "CDC 이관"),
                        "started_at":   _started_at,
                        "finished_at":  _finished_at,
                        "duration_sec": _dur_sec,
                        "error":        str(e)[:200],
                        "rows":         total_rows,
                        "errors":       total_errors,
                    },
                )
            except Exception: pass
        except Exception: pass

    finally:
        for c in (src_conn, tgt_conn):
            try:
                if c: c.close()
            except Exception: pass
        state.pop("current_table", None)

    return state


# ── 외부 API ─────────────────────────────────────────────────────

def start_cdc(cdc_id: str, config: dict) -> dict:
    t = threading.Thread(target=run_cdc, args=(cdc_id, config), daemon=True)
    t.start()
    return {"ok": True, "cdc_id": cdc_id}


def stop_cdc(cdc_id: str) -> dict:
    with _running_lock:
        if cdc_id in _running:
            _running[cdc_id]["stop"] = True
            return {"ok": True}
    return {"ok": False, "error": "실행 중인 CDC 없음"}


def get_cdc_status(cdc_id: str) -> Optional[dict]:
    return _running.get(cdc_id)


def get_all_cdc_status() -> dict:
    return dict(_running)


def get_cdc_state(state_key: str) -> dict:
    return _cdc_state.get(state_key) or {}


def reset_table_sync(state_key: str, table: str):
    saved = _cdc_state.get(state_key) or {}
    saved.pop(table, None)
    _cdc_state.set(state_key, saved)


def list_cdc_configs() -> list:
    return list(Store("cdc_configs").all().values())


def save_cdc_config(config_id: str, config: dict):
    s = Store("cdc_configs")
    config["id"] = config_id
    config["updated_at"] = _now_kst().strftime("%Y-%m-%d %H:%M:%S")
    s.set(config_id, config)


def delete_cdc_config(config_id: str):
    Store("cdc_configs").delete(config_id)
