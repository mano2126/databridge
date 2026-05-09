"""
app/api/routes/validate.py
DataBridge 검증 엔진 v2 — 행수·체크섬·샘플·컬럼통계 비교

──────────────────────────────────────────────────────────────────────────
v35 (2026-04-22) 임시 가드 패치
──────────────────────────────────────────────────────────────────────────
v34-C 에서 "bare name 매칭" (schema.table 에서 table 부분만 추출해 매칭)
방식이 채택되었으나, 여러 스키마에 같은 테이블명이 있으면 ("credit.contract"
vs "settlement.contract") 잘못된 테이블과 매칭되는 치명적 결함이 있어
v34-C 는 폐기되었다.

그러나 기존 capital_midsize → capital_target 처럼 **이름 충돌이 없는 환경**
에서는 bare name 매칭이 우연히 동작하므로, STEP 2 의 name_map 기반 본공사
전에 아래 임시 가드를 도입한다.

이 패치의 목적:
  (1) 검증 시작 전에 소스/타겟 양쪽의 스키마 구조를 스캔하여
      **bare name 충돌 여부를 선제적으로 탐지**한다.
  (2) 충돌이 없으면 기존 동작을 그대로 유지 (이름 추측이 안전함을 증명함).
  (3) 충돌이 발견되면 검증을 거부하고 명시적 에러 반환 — 잘못된 매칭으로
      인한 오판정(false positive "일치")을 원천 차단.
  (4) 결과 페이로드에 _validation_mode 를 명시하여 "이름 추측 기반
      임시 모드"임을 프론트/리포트가 인식할 수 있도록 한다.

STEP 2 (name_map 기반 본공사) 에서 이 가드는 전량 제거되며,
검증은 job.name_map 만 참조하게 된다. 본 파일의 모든 임시 코드에는
`# TEMP-GUARD-V34C:` 주석이 붙어 있어 제거 대상을 식별할 수 있다.
"""
from fastapi import APIRouter, HTTPException, Depends
from app.core.auth_deps import require_viewer, require_operator, Request
import time, hashlib, json, logging

router = APIRouter()
_history: list = []

logger = logging.getLogger("databridge.validate")


# ── DB 연결 ──────────────────────────────────────────────────
def _connect(info: dict):
    db_type = info.get("db_type", "mysql").lower()
    h  = info.get("host", "")
    p  = int(info.get("port") or (1434 if db_type in ("mssql","azure") else 3306))
    u  = info.get("username", "")
    pw = info.get("password", "")
    db = info.get("database", "")
    from app.core.password_resolver import resolve_password
    pw = resolve_password(
        pw, profile_id=info.get("profile_id"),
        side=info.get("side","source"),
        host=h, username=u, database=db,
    )
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
        # TEMP-GUARD-V34C: tbl 이 "schema.table" 이면 그 스키마를, 아니면 dbo.
        if "." in tbl:
            sch, name = tbl.split(".", 1)
            return f"[{db}].[{sch}].[{name}]"
        return f"[{db}].[dbo].[{tbl}]"
    # ════════════════════════════════════════════════════════════════════
    # v94_p7 (2026-05-01) 본부장님 호소 처방 — T1:
    #   "테이블 검증에서 -600,000 같은 가짜 차이"
    #
    # 본질: 본부장님 환경은 underscore 정책 (collection.profile → collection_profile)
    #       기존 코드는 schema.table → bare name 으로 떨어뜨려 `db`.`activity` 호출
    #       → 타겟에 그 이름 테이블 없거나 잘못된 테이블 매칭 → 가짜 차이
    #
    # 처방: schema.table 받으면 underscore 결합 (collection.activity → collection_activity)
    #       단, bare name (점 없음) 은 그대로
    # ════════════════════════════════════════════════════════════════════
    if "." in tbl:
        sch, name = tbl.split(".", 1)
        # underscore 정책: schema_name 패턴 우선 시도
        return f"`{db}`.`{sch}_{name}`"
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
            if "." in tbl:
                sch, name = tbl.split(".", 1)
            else:
                sch, name = "dbo", tbl
            row = _fetchone(conn,
                "SELECT COUNT(*) AS c FROM information_schema.TABLES "
                "WHERE TABLE_CATALOG=? AND TABLE_SCHEMA=? AND TABLE_NAME=?",
                [db, sch, name])
            return int((row or {}).get("c", 0)) > 0
        else:
            # ════════════════════════════════════════════════════════════════
            # v94_p7 T1: underscore 정책 우선 시도 → bare name fallback
            #   본부장님 환경: schemaStrategy='underscore'
            #   collection.activity → collection_activity (underscore 정책)
            # ════════════════════════════════════════════════════════════════
            if "." in tbl:
                sch, bare = tbl.split(".", 1)
                # 1차 시도: underscore 정책 (collection_activity)
                _underscore_name = f"{sch}_{bare}"
                row = _fetchone(conn,
                    "SELECT TABLE_NAME AS c FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA=%s AND LOWER(TABLE_NAME)=LOWER(%s) LIMIT 1",
                    [db, _underscore_name])
                if row is not None:
                    return True
                # 2차 시도: bare name (drop 정책 fallback)
                row = _fetchone(conn,
                    "SELECT TABLE_NAME AS c FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA=%s AND LOWER(TABLE_NAME)=LOWER(%s) LIMIT 1",
                    [db, bare])
                return row is not None
            else:
                # bare name 으로 들어온 경우 그대로
                row = _fetchone(conn,
                    "SELECT TABLE_NAME AS c FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA=%s AND LOWER(TABLE_NAME)=LOWER(%s) LIMIT 1",
                    [db, tbl])
                return row is not None
    except Exception:
        return False

def _resolve_tbl_name(conn, db_type, db, tbl) -> str:
    """MySQL에서 실제 테이블명(대소문자 맞춤) 반환

    v94_p7 T1: underscore 정책 우선 → bare name fallback
    """
    if db_type in ("mssql","azure"):
        return tbl
    try:
        if "." in tbl:
            sch, bare = tbl.split(".", 1)
            # 1차: underscore 정책
            _underscore_name = f"{sch}_{bare}"
            row = _fetchone(conn,
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=%s AND LOWER(TABLE_NAME)=LOWER(%s) LIMIT 1",
                [db, _underscore_name])
            if row:
                return row.get("TABLE_NAME") or _underscore_name
            # 2차: bare name
            row = _fetchone(conn,
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=%s AND LOWER(TABLE_NAME)=LOWER(%s) LIMIT 1",
                [db, bare])
            return (row or {}).get("TABLE_NAME", _underscore_name)
        else:
            row = _fetchone(conn,
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=%s AND LOWER(TABLE_NAME)=LOWER(%s) LIMIT 1",
                [db, tbl])
            return (row or {}).get("TABLE_NAME", tbl)
    except Exception:
        return tbl


# ── 테이블 목록 ──────────────────────────────────────────────
def _get_tables(conn, db_type, db) -> list:
    """
    소스(MSSQL) 는 schema.table 형식으로, MySQL 은 table 형식으로 반환.
    dbo 스키마는 prefix 생략 (기존 호환).
    """
    if db_type in ("mssql","azure"):
        rows = _fetchall(conn,
            "SELECT s.name AS sname, t.name AS tname "
            "FROM sys.tables t "
            "JOIN sys.schemas s ON t.schema_id=s.schema_id "
            "WHERE s.name NOT IN ('sys','INFORMATION_SCHEMA','guest','db_owner',"
            "'db_accessadmin','db_securityadmin','db_ddladmin','db_backupoperator',"
            "'db_datareader','db_datawriter','db_denydatareader','db_denydatawriter') "
            "ORDER BY s.name, t.name")
        return [
            (r["tname"] if r["sname"] == "dbo" else f'{r["sname"]}.{r["tname"]}')
            for r in rows
        ]
    else:
        rows = _fetchall(conn,
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME",
            [db])
        return [r["TABLE_NAME"] for r in rows]


# ── TEMP-GUARD-V34C: bare name 충돌 감지기 ──────────────────
def _detect_bare_name_conflicts(conn, db_type, db, tables: list) -> dict:
    """
    MSSQL 소스의 테이블 목록에서 bare name 충돌을 탐지한다.
    같은 테이블명(bare)이 여러 스키마에 존재하면 bare name 매칭은 안전하지 않다.

    반환: {
      "has_conflict": bool,
      "conflicts":    [{"bare": "contract", "schemas": ["credit", "settlement"]}, ...],
      "total_tables": int,
      "mode":         "safe_bare_name" | "conflict_detected" | "not_applicable"
    }

    MySQL 은 스키마=DB 이므로 충돌 불가 → not_applicable 반환.
    """
    if db_type not in ("mssql", "azure"):
        return {"has_conflict": False, "conflicts": [], "total_tables": len(tables), "mode": "not_applicable"}

    try:
        rows = _fetchall(conn,
            "SELECT s.name AS sname, t.name AS tname "
            "FROM sys.tables t "
            "JOIN sys.schemas s ON t.schema_id=s.schema_id "
            "WHERE s.name NOT IN ('sys','INFORMATION_SCHEMA','guest','db_owner',"
            "'db_accessadmin','db_securityadmin','db_ddladmin','db_backupoperator',"
            "'db_datareader','db_datawriter','db_denydatareader','db_denydatawriter')")
    except Exception as e:
        logger.warning(f"충돌 감지 실패 — bare name 매칭 모드 유지: {e}")
        return {"has_conflict": False, "conflicts": [], "total_tables": len(tables),
                "mode": "safe_bare_name", "scan_error": str(e)[:120]}

    bare_to_schemas: dict = {}
    for r in rows:
        nm = r["tname"]
        sch = r["sname"]
        bare_to_schemas.setdefault(nm, set()).add(sch)

    if tables:
        target_bares = set()
        for t in tables:
            bare = t.split(".", 1)[1] if "." in t else t
            target_bares.add(bare)
    else:
        target_bares = set(bare_to_schemas.keys())

    conflicts = []
    for bare, schemas in bare_to_schemas.items():
        if bare in target_bares and len(schemas) >= 2:
            conflicts.append({
                "bare": bare,
                "schemas": sorted(schemas),
            })

    has_conflict = len(conflicts) > 0
    return {
        "has_conflict": has_conflict,
        "conflicts":    conflicts,
        "total_tables": len(tables) if tables else len(bare_to_schemas),
        "mode":         "conflict_detected" if has_conflict else "safe_bare_name",
    }


# ── 컬럼 목록 ────────────────────────────────────────────────
def _get_columns(conn, db_type, db, tbl) -> list:
    """[(name, data_type)] 반환"""
    try:
        if db_type in ("mssql","azure"):
            if "." in tbl:
                sch, name = tbl.split(".", 1)
            else:
                sch, name = "dbo", tbl
            rows = _fetchall(conn,
                "SELECT COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS "
                "WHERE TABLE_CATALOG=? AND TABLE_SCHEMA=? AND TABLE_NAME=? "
                "ORDER BY ORDINAL_POSITION",
                [db, sch, name])
        else:
            # TEMP-GUARD-V34C: MySQL 측도 schema prefix 제거 (preflight 통과 후)
            _lookup_name = tbl.split(".", 1)[1] if "." in tbl else tbl
            rows = _fetchall(conn,
                "SELECT COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s "
                "ORDER BY ORDINAL_POSITION",
                [db, _lookup_name])
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
    ref = _tbl_ref(db_type, db, tbl)
    use_cols = cols[:30]
    col_refs = [_col_ref(db_type, c) for c, _ in use_cols]
    col_names = [c for c, _ in use_cols]

    try:
        if db_type in ("mssql", "azure"):
            # v35: PK 조회 시 스키마까지 고려
            if "." in tbl:
                _sch, _name = tbl.split(".", 1)
            else:
                _sch, _name = "dbo", tbl
            pk_sql = """
                SELECT c.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE c
                  ON tc.CONSTRAINT_NAME = c.CONSTRAINT_NAME
                 AND tc.TABLE_SCHEMA   = c.TABLE_SCHEMA
                WHERE tc.TABLE_SCHEMA = ? AND tc.TABLE_NAME = ?
                  AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                ORDER BY c.ORDINAL_POSITION
            """
            pk_rows = _fetchall(conn, pk_sql, [_sch, _name])
            pk_cols = [r.get("COLUMN_NAME") or r.get("column_name","") for r in pk_rows]
        else:
            # TEMP-GUARD-V34C: MySQL 은 bare name 기준
            _lookup_name = tbl.split(".", 1)[1] if "." in tbl else tbl
            pk_sql = """
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                  AND CONSTRAINT_NAME = 'PRIMARY'
                ORDER BY ORDINAL_POSITION
            """
            pk_rows = _fetchall(conn, pk_sql, [_lookup_name])
            pk_cols = [r.get("COLUMN_NAME") or r.get("column_name","") for r in pk_rows]

        order_cols = pk_cols if pk_cols else [col_names[0]]

        if db_type in ("mssql", "azure"):
            order_expr = ", ".join(f"[{c}]" for c in order_cols)
            sel = ", ".join(col_refs)
            sql = f"SELECT {sel} FROM {ref} ORDER BY {order_expr}"
        else:
            order_expr = ", ".join(f"`{c}`" for c in order_cols)
            sel = ", ".join(col_refs)
            sql = f"SELECT {sel} FROM {ref} ORDER BY {order_expr}"

        cur = conn.cursor()
        cur.execute(sql)

        acc = 0
        batch = 1000
        while True:
            rows = cur.fetchmany(batch)
            if not rows:
                break
            for row in rows:
                if isinstance(row, dict):
                    vals = [str(row.get(c, "") if row.get(c) is not None else "") for c in col_names]
                else:
                    vals = [str(v if v is not None else "") for v in row]
                row_str = "|".join(vals)
                h = int(hashlib.md5(row_str.encode("utf-8")).hexdigest(), 16)
                acc ^= h
        cur.close()
        return format(acc, "032x")
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
    for col_name, col_type in cols[:30]:
        cr = _col_ref(db_type, col_name)
        s = {"col": col_name, "type": col_type}
        try:
            row = _fetchone(conn,
                f"SELECT COUNT(*) AS c FROM {ref} WHERE {cr} IS NULL")
            s["null_cnt"] = int((row or {}).get("c", 0))

            base_type = col_type.lower().split("(")[0]
            if base_type in _NUMERIC:
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


# ── v35: Preflight 엔드포인트 ────────────────────────────────
@router.post("/preflight")
def run_preflight(body: dict):
    """
    검증 실행 전 bare name 충돌을 선제적으로 탐지.
    프론트는 이 결과를 보고 검증 버튼 클릭 여부를 결정할 수 있다.
    """
    src_info = body.get("src_info", {})
    tables   = body.get("tables", [])

    if not src_info.get("host") or not src_info.get("database"):
        raise HTTPException(400, "소스 DB 연결 정보가 없습니다")

    try:
        src_conn = _connect(src_info)
    except Exception as e:
        raise HTTPException(500, f"소스 연결 실패: {e}")

    src_db   = src_info["database"]
    src_type = src_info.get("db_type", "mssql").lower()

    try:
        src_conflict = _detect_bare_name_conflicts(src_conn, src_type, src_db, tables)
    finally:
        try: src_conn.close()
        except: pass

    can_proceed = not src_conflict["has_conflict"]
    if src_conflict["has_conflict"]:
        conflict_names = [c["bare"] for c in src_conflict["conflicts"][:5]]
        warning = (
            f"소스 DB 에 bare name 충돌 {len(src_conflict['conflicts'])}건 발견: "
            f"{', '.join(conflict_names)}"
            f"{' 외' if len(src_conflict['conflicts']) > 5 else ''}. "
            "현재 검증은 이름 추측 기반(임시 모드)이라 충돌 시 오판정 가능. "
            "v2.0 name_map 기반 검증으로 해결 예정."
        )
    elif src_conflict.get("mode") == "not_applicable":
        warning = ""
    elif src_conflict.get("scan_error"):
        warning = f"스키마 스캔 부분 실패(진행은 가능): {src_conflict['scan_error']}"
    else:
        warning = ""

    return {
        "src_conflict":    src_conflict,
        "can_proceed":     can_proceed,
        "warning":         warning,
        "validation_mode": "bare_name_match_v34c_tempguard",
    }


# ── 메인 검증 엔드포인트 (스트리밍) ──────────────────────────
@router.post("/run/stream")
async def run_validate_stream(body: dict, request: Request):
    """SSE 스트리밍으로 테이블별 실시간 진행 상황 전달"""
    from fastapi.responses import StreamingResponse
    import json as _json, asyncio as _asyncio

    src_info = body.get("src_info", {})
    tgt_info = body.get("tgt_info", {})
    tables   = body.get("tables", [])
    method   = body.get("method", "row_count")
    # v35: 충돌 감지 후에도 강행할지 여부 (기본 false — 안전)
    force_bare_name = bool(body.get("force_bare_name", False))
    
    # v90.55: job_id 로 password 자동 복원 (검증 화면이 활성 Job 으로 동작 시)
    job_id = body.get("job_id") or src_info.get("job_id") or tgt_info.get("job_id")
    if job_id or src_info.get("password") or tgt_info.get("password"):
        from app.core.password_resolver import resolve_password as _resolve_pw
        if src_info:
            src_info = dict(src_info)
            src_info["password"] = _resolve_pw(
                src_info.get("password", ""),
                job_id=job_id, side="source",
                host=src_info.get("host"),
                username=src_info.get("username"),
                database=src_info.get("database"),
            )
        if tgt_info:
            tgt_info = dict(tgt_info)
            tgt_info["password"] = _resolve_pw(
                tgt_info.get("password", ""),
                job_id=job_id, side="target",
                host=tgt_info.get("host"),
                username=tgt_info.get("username"),
                database=tgt_info.get("database"),
            )

    def sse(obj):
        return "data: " + _json.dumps(obj) + "\n\n"

    async def generate():
        try:
            src_conn = _connect(src_info)
            tgt_conn = _connect(tgt_info)
        except Exception as e:
            yield sse({"type": "error", "msg": str(e)})
            return

        src_db   = src_info["database"]
        tgt_db   = tgt_info["database"]
        src_type = src_info.get("db_type", "mssql").lower()
        tgt_type = tgt_info.get("db_type", "mysql").lower()

        if not tables:
            try:
                tbl_list = _get_tables(src_conn, src_type, src_db)
            except Exception as e:
                yield sse({"type": "error", "msg": str(e)})
                src_conn.close(); tgt_conn.close(); return
        else:
            tbl_list = list(tables)

        # TEMP-GUARD-V34C: 검증 시작 전 충돌 감지
        conflict = _detect_bare_name_conflicts(src_conn, src_type, src_db, tbl_list)
        yield sse({
            "type":            "preflight",
            "validation_mode": "bare_name_match_v34c_tempguard",
            "conflict":        conflict,
        })
        if conflict["has_conflict"] and not force_bare_name:
            names = [c["bare"] for c in conflict["conflicts"][:10]]
            yield sse({
                "type": "error",
                "msg":  (
                    f"bare name 충돌 {len(conflict['conflicts'])}건 탐지: {', '.join(names)}. "
                    f"현재 검증 엔진(임시 모드)은 이름 추측 기반이라 충돌 시 잘못된 "
                    f"테이블과 매칭될 수 있어 검증을 거부합니다. v2.0 name_map 기반으로 "
                    f"해결됩니다. 그래도 진행하려면 force_bare_name=true 전송."
                ),
                "conflicts": conflict["conflicts"],
            })
            src_conn.close(); tgt_conn.close(); return

        total = len(tbl_list)
        yield sse({"type": "start", "total": total, "method": method})

        start_t = time.monotonic()
        results = []

        for i, tbl in enumerate(tbl_list):
            yield sse({"type": "progress", "current": i, "total": total, "table": tbl})
            await _asyncio.sleep(0)

            item = {
                "table": tbl, "src_count": 0, "tgt_count": 0,
                "diff": 0, "match": False, "tgt_exist": False,
                "src_error": None, "tgt_error": None,
            }

            item["tgt_exist"] = _tbl_exists(tgt_conn, tgt_type, tgt_db, tbl)
            tgt_tbl = _resolve_tbl_name(tgt_conn, tgt_type, tgt_db, tbl) if item["tgt_exist"] else tbl

            try:
                item["src_count"] = _row_count(src_conn, src_type, src_db, tbl)
            except Exception as e:
                item["src_error"] = str(e)[:120]

            if item["tgt_exist"]:
                try:
                    item["tgt_count"] = _row_count(tgt_conn, tgt_type, tgt_db, tgt_tbl)
                except Exception as e:
                    item["tgt_error"] = str(e)[:120]

            item["diff"] = item["tgt_count"] - item["src_count"]
            item["count_match"] = (
                item["src_count"] == item["tgt_count"]
                and item["tgt_exist"]
                and not item["src_error"]
                and not item["tgt_error"]
            )

            src_cols = _get_columns(src_conn, src_type, src_db, tbl)

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

            if method in ("sample", "full") and item["tgt_exist"]:
                try:
                    item["src_sample"] = _sample(src_conn, src_type, src_db, tbl, 5)
                    item["tgt_sample"] = _sample(tgt_conn, tgt_type, tgt_db, tgt_tbl, 5)
                except Exception as e:
                    item["sample_error"] = str(e)[:120]

            if method in ("column_stats", "full") and item["tgt_exist"] and src_cols:
                try:
                    src_stats = _col_stats(src_conn, src_type, src_db, tbl, src_cols)
                    tgt_stats = _col_stats(tgt_conn, tgt_type, tgt_db, tgt_tbl, src_cols)
                    item["col_stats"]   = _compare_stats(src_stats, tgt_stats)
                    item["stats_match"] = all(c["match"] for c in item["col_stats"])
                except Exception as e:
                    item["stats_error"] = str(e)[:120]

            checks = [item["count_match"]]
            if "checksum_match" in item: checks.append(item["checksum_match"])
            if "stats_match"    in item: checks.append(item["stats_match"])
            item["match"] = all(checks) and item["tgt_exist"]

            results.append(item)
            elapsed = round(time.monotonic() - start_t, 2)
            yield sse({"type": "result", "item": item, "current": i + 1, "total": total, "elapsed": elapsed})
            await _asyncio.sleep(0)

        src_conn.close()
        tgt_conn.close()

        elapsed = round(time.monotonic() - start_t, 2)
        passed  = sum(1 for r in results if r["match"])
        summary = {
            "total": len(results), "passed": passed,
            "failed": len(results) - passed,
            "pass_rate": round(passed / len(results) * 100, 1) if results else 0,
            "elapsed_sec": elapsed,
            "validation_mode": "bare_name_match_v34c_tempguard",  # v35
        }
        yield sse({"type": "done", "results": results, "summary": summary})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/run")
def run_validate(body: dict):
    src_info = body.get("src_info", {})
    tgt_info = body.get("tgt_info", {})
    tables   = body.get("tables", [])
    method   = body.get("method", "row_count")
    force_bare_name = bool(body.get("force_bare_name", False))  # v35
    
    # ════════════════════════════════════════════════════════════════════
    # v90.55: job_id 가 들어오면 활성 Job 의 password 자동 복원
    # ════════════════════════════════════════════════════════════════════
    # 검증 화면이 활성 Job 의 연결정보로 자동 동작할 때 src_info/tgt_info 의
    # password 필드는 마스크 토큰(●●●●●●●●) 으로 와있음.
    # password_resolver 가 job_id + side 로 평문 복원.
    job_id = body.get("job_id") or src_info.get("job_id") or tgt_info.get("job_id")
    if job_id or src_info.get("password") or tgt_info.get("password"):
        from app.core.password_resolver import resolve_password as _resolve_pw
        if src_info:
            src_info = dict(src_info)
            src_info["password"] = _resolve_pw(
                src_info.get("password", ""),
                job_id=job_id,
                side="source",
                host=src_info.get("host"),
                username=src_info.get("username"),
                database=src_info.get("database"),
            )
        if tgt_info:
            tgt_info = dict(tgt_info)
            tgt_info["password"] = _resolve_pw(
                tgt_info.get("password", ""),
                job_id=job_id,
                side="target",
                host=tgt_info.get("host"),
                username=tgt_info.get("username"),
                database=tgt_info.get("database"),
            )

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

    # TEMP-GUARD-V34C: 충돌 감지 (비스트리밍 경로)
    conflict = _detect_bare_name_conflicts(src_conn, src_type, src_db, tables)
    if conflict["has_conflict"] and not force_bare_name:
        src_conn.close(); tgt_conn.close()
        names = [c["bare"] for c in conflict["conflicts"][:10]]
        raise HTTPException(
            409,
            {
                "error":          "bare_name_conflict",
                "message":        f"bare name 충돌 {len(conflict['conflicts'])}건: {', '.join(names)}. v2.0 name_map 기반으로 해결됩니다.",
                "conflicts":      conflict["conflicts"],
                "validation_mode":"bare_name_match_v34c_tempguard",
            },
        )

    start_t = time.monotonic()
    results = []

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

        item["tgt_exist"] = _tbl_exists(tgt_conn, tgt_type, tgt_db, tbl)
        tgt_tbl = _resolve_tbl_name(tgt_conn, tgt_type, tgt_db, tbl) if item["tgt_exist"] else tbl

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

        src_cols = _get_columns(src_conn, src_type, src_db, tbl)

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

        if method in ("sample", "full") and item["tgt_exist"]:
            try:
                item["src_sample"] = _sample(src_conn, src_type, src_db, tbl, 5)
                item["tgt_sample"] = _sample(tgt_conn, tgt_type, tgt_db, tgt_tbl, 5)
            except Exception as e:
                item["sample_error"] = str(e)[:120]

        if method in ("column_stats", "full") and item["tgt_exist"] and src_cols:
            try:
                src_stats = _col_stats(src_conn, src_type, src_db, tbl, src_cols)
                tgt_stats = _col_stats(tgt_conn, tgt_type, tgt_db, tgt_tbl, src_cols)
                item["col_stats"]  = _compare_stats(src_stats, tgt_stats)
                item["stats_match"] = all(c["match"] for c in item["col_stats"])
            except Exception as e:
                item["stats_error"] = str(e)[:120]

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
        "total":           len(results),
        "passed":          passed,
        "failed":          len(results) - passed,
        "pass_rate":       round(passed / len(results) * 100, 1) if results else 0,
        "elapsed_sec":     elapsed,
        "src_db":          src_db,
        "tgt_db":          tgt_db,
        "method":          method,
        "timestamp":       time.strftime("%Y-%m-%d %H:%M:%S"),
        "validation_mode": "bare_name_match_v34c_tempguard",  # v35
        "conflict":        conflict,                           # v35
    }

    _history.insert(0, {**summary, "tables": len(results)})
    if len(_history) > 50:
        _history.pop()

    return {"results": results, "summary": summary}


@router.get("/history")
def get_history():
    return _history
