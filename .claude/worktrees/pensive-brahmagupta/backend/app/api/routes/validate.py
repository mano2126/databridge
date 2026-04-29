"""
app/api/routes/validate.py
DataBridge 검증 엔진 v2 — 행수·체크섬·샘플·컬럼통계 비교
"""
from fastapi import APIRouter, HTTPException
import time, hashlib, json

router = APIRouter()
_history: list = []


# ── DB 연결 ──────────────────────────────────────────────────
def _connect(info: dict):
    db_type = info.get("db_type", "mysql").lower()
    h  = info.get("host", "")
    p  = int(info.get("port") or (1434 if db_type in ("mssql","azure") else 3306))
    u  = info.get("username", "")
    pw = info.get("password", "")
    db = info.get("database", "")
    if not h or not db:
        raise ValueError(f"연결 정보 부족 — host={h!r} database={db!r}")
    if db_type in ("mysql","aurora","cloudsql","tidb","mariadb"):
        import pymysql
        return pymysql.connect(
            host=h, port=p, user=u, password=pw,
            database=db, charset="utf8mb4", connect_timeout=10,
            cursorclass=pymysql.cursors.DictCursor)
    elif db_type in ("mssql","azure"):
        from app.core.db_conn import make_mssql_conn
        return make_mssql_conn(h, p, u, pw, db, timeout=10)
    raise NotImplementedError(f"{db_type} 미지원")


# ── 쿼리 헬퍼 ────────────────────────────────────────────────
def _tbl_ref(db_type, db, tbl):
    if db_type in ("mssql","azure"):
        return f"[{db}].[dbo].[{tbl}]"
    return f"`{db}`.`{tbl}`"

def _col_ref(db_type, col):
    if db_type in ("mssql","azure"):
        return f"[{col}]"
    return f"`{col}`"

def _fetchone(conn, sql, params=None):
    cur = conn.cursor()
    cur.execute(sql, params or [])
    row = cur.fetchone()
    if row is None:
        return None
    return dict(row) if hasattr(row, 'keys') else dict(zip([d[0] for d in cur.description], row))

def _fetchall(conn, sql, params=None):
    cur = conn.cursor()
    cur.execute(sql, params or [])
    rows = cur.fetchall()
    if not rows:
        return []
    if hasattr(rows[0], 'keys'):
        return [dict(r) for r in rows]
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]


# ── 테이블 존재 확인 ─────────────────────────────────────────
def _tbl_exists(conn, db_type, db, tbl) -> bool:
    try:
        if db_type in ("mssql","azure"):
            row = _fetchone(conn,
                "SELECT COUNT(*) AS c FROM information_schema.TABLES "
                "WHERE TABLE_CATALOG=? AND TABLE_SCHEMA='dbo' AND TABLE_NAME=?",
                [db, tbl])
        else:
            # MySQL: 대소문자 무시 (LOWER 비교)
            row = _fetchone(conn,
                "SELECT TABLE_NAME AS c FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=%s AND LOWER(TABLE_NAME)=LOWER(%s) LIMIT 1",
                [db, tbl])
            return row is not None
        return int((row or {}).get("c", 0)) > 0
    except Exception:
        return False

def _resolve_tbl_name(conn, db_type, db, tbl) -> str:
    """MySQL에서 실제 테이블명(대소문자 맞춤) 반환"""
    if db_type in ("mssql","azure"):
        return tbl
    try:
        row = _fetchone(conn,
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=%s AND LOWER(TABLE_NAME)=LOWER(%s) LIMIT 1",
            [db, tbl])
        return (row or {}).get("TABLE_NAME", tbl)
    except Exception:
        return tbl


# ── 테이블 목록 ──────────────────────────────────────────────
def _get_tables(conn, db_type, db) -> list:
    if db_type in ("mssql","azure"):
        rows = _fetchall(conn,
            "SELECT t.name FROM sys.tables t "
            "JOIN sys.schemas s ON t.schema_id=s.schema_id "
            "WHERE s.name='dbo' ORDER BY t.name")
        return [r["name"] for r in rows]
    else:
        rows = _fetchall(conn,
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME",
            [db])
        return [r["TABLE_NAME"] for r in rows]


# ── 컬럼 목록 ────────────────────────────────────────────────
def _get_columns(conn, db_type, db, tbl) -> list:
    """[(name, data_type)] 반환"""
    try:
        if db_type in ("mssql","azure"):
            rows = _fetchall(conn,
                "SELECT COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS "
                "WHERE TABLE_CATALOG=? AND TABLE_SCHEMA='dbo' AND TABLE_NAME=? "
                "ORDER BY ORDINAL_POSITION",
                [db, tbl])
        else:
            rows = _fetchall(conn,
                "SELECT COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s "
                "ORDER BY ORDINAL_POSITION",
                [db, tbl])
        return [(r["COLUMN_NAME"], r["DATA_TYPE"]) for r in rows]
    except Exception:
        return []


# ── ① 행수 비교 ──────────────────────────────────────────────
def _row_count(conn, db_type, db, tbl) -> int:
    ref = _tbl_ref(db_type, db, tbl)
    row = _fetchone(conn, f"SELECT COUNT(*) AS c FROM {ref}")
    return int((row or {}).get("c", 0))


# ── ② 체크섬 비교 ────────────────────────────────────────────
def _checksum(conn, db_type, db, tbl, cols) -> str:
    """각 컬럼 값을 연결해 MD5/SHA256 체크섬 계산"""
    ref = _tbl_ref(db_type, db, tbl)
    col_refs = [_col_ref(db_type, c) for c, _ in cols[:20]]  # 최대 20컬럼

    try:
        if db_type in ("mssql","azure"):
            concat = " + '|' + ".join(
                f"ISNULL(CAST({c} AS NVARCHAR(MAX)),'')" for c in col_refs)
            sql = f"SELECT CHECKSUM_AGG(CHECKSUM({concat})) AS cs FROM {ref}"
            row = _fetchone(conn, sql)
            return str((row or {}).get("cs", ""))
        else:
            concat = ", '|', ".join(
                f"IFNULL(CAST({c} AS CHAR),'')" for c in col_refs)
            sql = f"SELECT MD5(GROUP_CONCAT({concat} ORDER BY {col_refs[0]})) AS cs FROM {ref}"
            row = _fetchone(conn, sql)
            return str((row or {}).get("cs", ""))
    except Exception as e:
        return f"ERR:{e}"


# ── ③ 샘플 비교 ──────────────────────────────────────────────
def _sample(conn, db_type, db, tbl, n=5) -> list:
    ref = _tbl_ref(db_type, db, tbl)
    try:
        if db_type in ("mssql","azure"):
            rows = _fetchall(conn, f"SELECT TOP {n} * FROM {ref}")
        else:
            rows = _fetchall(conn, f"SELECT * FROM {ref} LIMIT {n}")
        # 값을 문자열로 통일
        return [{k: str(v) if v is not None else None for k, v in r.items()}
                for r in rows]
    except Exception:
        return []


# ── ④ 컬럼별 통계 ────────────────────────────────────────────
_NUMERIC = {"int","bigint","smallint","tinyint","decimal","numeric",
            "float","double","real","money","smallmoney"}

def _col_stats(conn, db_type, db, tbl, cols) -> list:
    ref = _tbl_ref(db_type, db, tbl)
    stats = []
    for col_name, col_type in cols[:30]:  # 최대 30컬럼
        cr = _col_ref(db_type, col_name)
        s = {"col": col_name, "type": col_type}
        try:
            # NULL 수
            row = _fetchone(conn,
                f"SELECT COUNT(*) AS c FROM {ref} WHERE {cr} IS NULL")
            s["null_cnt"] = int((row or {}).get("c", 0))

            base_type = col_type.lower().split("(")[0]
            if base_type in _NUMERIC:
                # 숫자형: min/max/avg/sum
                if db_type in ("mssql","azure"):
                    row = _fetchone(conn,
                        f"SELECT MIN({cr}) AS mn, MAX({cr}) AS mx, "
                        f"AVG(CAST({cr} AS FLOAT)) AS av, SUM(CAST({cr} AS FLOAT)) AS sm "
                        f"FROM {ref}")
                else:
                    row = _fetchone(conn,
                        f"SELECT MIN({cr}) AS mn, MAX({cr}) AS mx, "
                        f"AVG({cr}) AS av, SUM({cr}) AS sm FROM {ref}")
                if row:
                    s["min"] = _safe_num(row.get("mn"))
                    s["max"] = _safe_num(row.get("mx"))
                    s["avg"] = _safe_num(row.get("av"))
                    s["sum"] = _safe_num(row.get("sm"))
            else:
                # 문자형: distinct count, max/min length
                row = _fetchone(conn,
                    f"SELECT COUNT(DISTINCT {cr}) AS dc, "
                    f"MAX(LEN({cr})) AS mxl, MIN(LEN({cr})) AS mnl "
                    f"FROM {ref}")
                if row:
                    s["distinct"] = int((row or {}).get("dc", 0))
                    s["max_len"]  = (row or {}).get("mxl")
                    s["min_len"]  = (row or {}).get("mnl")
        except Exception as e:
            s["error"] = str(e)[:80]
        stats.append(s)
    return stats


def _safe_num(v):
    if v is None:
        return None
    try:
        f = float(v)
        return round(f, 4)
    except Exception:
        return str(v)


# ── 통계 비교 ────────────────────────────────────────────────
def _compare_stats(src_stats, tgt_stats) -> list:
    tgt_map = {s["col"]: s for s in tgt_stats}
    result = []
    for ss in src_stats:
        col = ss["col"]
        ts  = tgt_map.get(col, {})
        diffs = []
        for key in ("null_cnt","min","max","avg","sum","distinct"):
            sv, tv = ss.get(key), ts.get(key)
            if sv is not None and tv is not None and sv != tv:
                diffs.append({"key": key, "src": sv, "tgt": tv})
        result.append({
            "col":   col,
            "type":  ss.get("type"),
            "src":   ss,
            "tgt":   ts,
            "diffs": diffs,
            "match": len(diffs) == 0 and not ss.get("error") and not ts.get("error")
        })
    return result


# ── 메인 검증 엔드포인트 ─────────────────────────────────────
@router.post("/run")
def run_validate(body: dict):
    src_info = body.get("src_info", {})
    tgt_info = body.get("tgt_info", {})
    tables   = body.get("tables", [])
    method   = body.get("method", "row_count")  # row_count|checksum|sample|column_stats|full

    for label, info in [("소스", src_info), ("타겟", tgt_info)]:
        if not info.get("host") or not info.get("database"):
            raise HTTPException(400, f"{label} DB 연결 정보가 없습니다")

    try:
        src_conn = _connect(src_info)
    except Exception as e:
        raise HTTPException(500, f"소스 연결 실패: {e}")
    try:
        tgt_conn = _connect(tgt_info)
    except Exception as e:
        src_conn.close()
        raise HTTPException(500, f"타겟 연결 실패: {e}")

    src_db   = src_info["database"]
    tgt_db   = tgt_info["database"]
    src_type = src_info.get("db_type", "mssql").lower()
    tgt_type = tgt_info.get("db_type", "mysql").lower()

    if not tables:
        try:
            tables = _get_tables(src_conn, src_type, src_db)
        except Exception as e:
            src_conn.close(); tgt_conn.close()
            raise HTTPException(500, f"테이블 목록 조회 실패: {e}")

    start_t = time.monotonic()
    results = []
    do_all  = method == "full"

    for tbl in tables:
        item = {
            "table":     tbl,
            "src_count": 0,
            "tgt_count": 0,
            "diff":      0,
            "match":     False,
            "tgt_exist": False,
            "src_error": None,
            "tgt_error": None,
        }

        # 타겟 존재 확인 (대소문자 무시)
        item["tgt_exist"] = _tbl_exists(tgt_conn, tgt_type, tgt_db, tbl)
        # 실제 타겟 테이블명 (소문자로 이관됐을 수 있음)
        tgt_tbl = _resolve_tbl_name(tgt_conn, tgt_type, tgt_db, tbl) if item["tgt_exist"] else tbl

        # ① 행수 (항상)
        try:
            item["src_count"] = _row_count(src_conn, src_type, src_db, tbl)
        except Exception as e:
            item["src_error"] = str(e)[:120]

        if item["tgt_exist"]:
            try:
                item["tgt_count"] = _row_count(tgt_conn, tgt_type, tgt_db, tgt_tbl)
            except Exception as e:
                item["tgt_error"] = str(e)[:120]

        item["diff"]  = item["tgt_count"] - item["src_count"]
        item["count_match"] = (
            item["src_count"] == item["tgt_count"]
            and item["tgt_exist"]
            and not item["src_error"]
            and not item["tgt_error"]
        )

        # 컬럼 목록
        src_cols = _get_columns(src_conn, src_type, src_db, tbl)

        # ② 체크섬
        if method in ("checksum", "full") and item["tgt_exist"] and src_cols:
            try:
                item["src_checksum"] = _checksum(src_conn, src_type, src_db, tbl, src_cols)
                item["tgt_checksum"] = _checksum(tgt_conn, tgt_type, tgt_db, tgt_tbl, src_cols)
                item["checksum_match"] = (
                    item["src_checksum"] == item["tgt_checksum"]
                    and not item["src_checksum"].startswith("ERR")
                )
            except Exception as e:
                item["checksum_error"] = str(e)[:120]

        # ③ 샘플
        if method in ("sample", "full") and item["tgt_exist"]:
            try:
                item["src_sample"] = _sample(src_conn, src_type, src_db, tbl, 5)
                item["tgt_sample"] = _sample(tgt_conn, tgt_type, tgt_db, tgt_tbl, 5)
            except Exception as e:
                item["sample_error"] = str(e)[:120]

        # ④ 컬럼 통계
        if method in ("column_stats", "full") and item["tgt_exist"] and src_cols:
            try:
                src_stats = _col_stats(src_conn, src_type, src_db, tbl, src_cols)
                tgt_stats = _col_stats(tgt_conn, tgt_type, tgt_db, tgt_tbl, src_cols)
                item["col_stats"]  = _compare_stats(src_stats, tgt_stats)
                item["stats_match"] = all(c["match"] for c in item["col_stats"])
            except Exception as e:
                item["stats_error"] = str(e)[:120]

        # 종합 match 판정
        checks = [item["count_match"]]
        if "checksum_match" in item:
            checks.append(item["checksum_match"])
        if "stats_match" in item:
            checks.append(item["stats_match"])
        item["match"] = all(checks) and item["tgt_exist"]

        results.append(item)

    src_conn.close()
    tgt_conn.close()

    elapsed = round(time.monotonic() - start_t, 2)
    passed  = sum(1 for r in results if r["match"])

    summary = {
        "total":       len(results),
        "passed":      passed,
        "failed":      len(results) - passed,
        "pass_rate":   round(passed / len(results) * 100, 1) if results else 0,
        "elapsed_sec": elapsed,
        "src_db":      src_db,
        "tgt_db":      tgt_db,
        "method":      method,
        "timestamp":   time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    _history.insert(0, {**summary, "tables": len(results)})
    if len(_history) > 50:
        _history.pop()

    return {"results": results, "summary": summary}


@router.get("/history")
def get_history():
    return _history
