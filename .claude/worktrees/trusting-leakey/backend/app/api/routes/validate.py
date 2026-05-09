"""
app/api/routes/validate.py
실제 소스/타겟 DB Row Count 비교 — COUNT(*) 사용 (정확한 값)
"""
from fastapi import APIRouter, HTTPException
import time

router = APIRouter()
_history: list = []


def _connect(info: dict, retries: int = 2):
    """DB 연결 — MSSQL은 make_mssql_conn(드라이버 자동선택+재시도) 사용"""
    db_type = info.get("db_type", "mysql")
    h  = info.get("host", "")
    p  = int(info.get("port") or (1434 if db_type in ("mssql","azure") else 3306))
    u  = info.get("username", "")
    pw = info.get("password", "")
    db = info.get("database", "")
    if not h or not db:
        raise ValueError(f"연결 정보 부족 — host={h!r} database={db!r}")

    if db_type in ("mysql", "aurora", "cloudsql", "tidb", "mariadb"):
        import pymysql
        return pymysql.connect(
            host=h, port=p, user=u, password=pw,
            database=db, charset="utf8mb4", connect_timeout=10,
            cursorclass=pymysql.cursors.DictCursor
        )
    elif db_type in ("mssql", "azure"):
        # make_mssql_conn: Driver 18→17→SQL Server 순 자동선택, 재시도 포함
        from app.core.db_conn import make_mssql_conn
        return make_mssql_conn(h, p, u, pw, db, timeout=10)
    raise NotImplementedError(f"{db_type} 드라이버 미지원")


def _get_tables_mysql(conn, db: str) -> list:
    cur = conn.cursor()
    cur.execute("""
        SELECT TABLE_NAME FROM information_schema.TABLES
        WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE'
        ORDER BY TABLE_NAME
    """, (db,))
    return [r["TABLE_NAME"] for r in cur.fetchall()]


def _get_tables_mssql(conn) -> list:
    cur = conn.cursor()
    cur.execute("""
        SELECT t.name FROM sys.tables t
        JOIN sys.schemas s ON t.schema_id=s.schema_id
        WHERE s.name='dbo' ORDER BY t.name
    """)
    return [row[0] for row in cur.fetchall()]


def _count_mysql(conn, db: str, table: str) -> int:
    """COUNT(*) — 정확한 건수"""
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) AS cnt FROM `{db}`.`{table}`")
    row = cur.fetchone()
    return int(row["cnt"]) if row else 0


def _count_mssql(conn, db: str, table: str) -> tuple:
    """(count, exists) 반환"""
    cur = conn.cursor()
    # 테이블 존재 여부 먼저 확인
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.TABLES
        WHERE TABLE_CATALOG=? AND TABLE_SCHEMA='dbo' AND TABLE_NAME=?
    """, (db, table))
    exists = cur.fetchone()[0] > 0
    if not exists:
        return 0, False
    cur.execute(f"SELECT COUNT(*) FROM [{db}].[dbo].[{table}]")
    row = cur.fetchone()
    return (int(row[0]) if row else 0), True


def _sample_mysql(conn, db: str, table: str, n=3) -> list:
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT * FROM `{db}`.`{table}` LIMIT {n}")
        return cur.fetchall()
    except Exception:
        return []


def _sample_mssql(conn, db: str, table: str, n=3) -> list:
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT TOP {n} * FROM [{db}].[dbo].[{table}]")
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception:
        return []


@router.post("/run")
def run_validate(body: dict):
    src_info = body.get("src_info", {})
    tgt_info = body.get("tgt_info", {})
    tables   = body.get("tables", [])
    method   = body.get("method", "row_count")

    if not src_info.get("host") or not src_info.get("database"):
        raise HTTPException(400, "소스 DB 연결 정보가 없습니다 (host, database 필수)")
    if not tgt_info.get("host") or not tgt_info.get("database"):
        raise HTTPException(400, "타겟 DB 연결 정보가 없습니다 (host, database 필수)")

    # 연결
    try:
        src_conn = _connect(src_info)
    except Exception as e:
        raise HTTPException(500, f"소스 연결 실패: {e}")
    try:
        tgt_conn = _connect(tgt_info)
    except Exception as e:
        src_conn.close()
        raise HTTPException(500, f"타겟 연결 실패: {e}")

    src_db      = src_info["database"]
    tgt_db      = tgt_info["database"]
    src_type    = src_info.get("db_type", "mysql")
    tgt_type    = tgt_info.get("db_type", "mssql")

    # 테이블 목록 수집
    if not tables:
        try:
            if src_type in ("mysql","aurora","cloudsql","tidb","mariadb"):
                tables = _get_tables_mysql(src_conn, src_db)
            elif src_type in ("mssql","azure"):
                tables = _get_tables_mssql(src_conn)
        except Exception as e:
            src_conn.close(); tgt_conn.close()
            raise HTTPException(500, f"테이블 목록 조회 실패: {e}")

    start_t = time.monotonic()
    results = []

    for tbl in tables:
        item = {
            "table":      tbl,
            "src":        0,
            "tgt":        0,
            "diff":       0,
            "match":      False,
            "tgt_exist":  True,
            "src_error":  None,
            "tgt_error":  None,
        }

        # 소스 COUNT(*)
        try:
            if src_type in ("mysql","aurora","cloudsql","tidb","mariadb"):
                item["src"] = _count_mysql(src_conn, src_db, tbl)
            elif src_type in ("mssql","azure"):
                cnt, ex = _count_mssql(src_conn, src_db, tbl)
                item["src"] = cnt
                if not ex:
                    item["src_error"] = "테이블 없음"
        except Exception as e:
            item["src_error"] = str(e)

        # 타겟 COUNT(*)
        try:
            if tgt_type in ("mysql","aurora","cloudsql","tidb","mariadb"):
                item["tgt"] = _count_mysql(tgt_conn, tgt_db, tbl)
            elif tgt_type in ("mssql","azure"):
                cnt, ex = _count_mssql(tgt_conn, tgt_db, tbl)
                item["tgt"] = cnt
                item["tgt_exist"] = ex
        except Exception as e:
            item["tgt_error"] = str(e)

        item["diff"]  = item["tgt"] - item["src"]
        item["match"] = (
            item["src"] == item["tgt"]
            and item["tgt_exist"]
            and not item["src_error"]
            and not item["tgt_error"]
        )

        # 샘플 데이터 (method=sample 일 때)
        if method == "sample":
            try:
                if src_type in ("mysql","aurora","cloudsql","tidb","mariadb"):
                    item["src_sample"] = _sample_mysql(src_conn, src_db, tbl, 3)
                if item["tgt_exist"]:
                    if tgt_type in ("mssql","azure"):
                        item["tgt_sample"] = _sample_mssql(tgt_conn, tgt_db, tbl, 3)
            except Exception:
                pass

        results.append(item)

    src_conn.close()
    tgt_conn.close()

    elapsed = round(time.monotonic() - start_t, 2)
    passed  = sum(1 for r in results if r["match"])
    failed  = len(results) - passed

    summary = {
        "total":       len(results),
        "passed":      passed,
        "failed":      failed,
        "pass_rate":   round(passed / len(results) * 100, 1) if results else 0,
        "elapsed_sec": elapsed,
        "src_db":      src_db,
        "tgt_db":      tgt_db,
        "method":      method,
    }

    _history.insert(0, {
        **summary,
        "tables":    len(results),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    if len(_history) > 50:
        _history.pop()

    return {"results": results, "summary": summary}


@router.get("/history")
def get_history():
    return _history
