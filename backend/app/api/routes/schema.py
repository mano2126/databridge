"""
app/api/routes/schema.py  — 실제 DB 테이블/컬럼 조회 + 타입 경고 분석
"""
import logging
from fastapi import APIRouter, HTTPException
from app.core.db_conn import make_mssql_conn, get_port, default_port

router = APIRouter()
logger = logging.getLogger("databridge.schema")
_conns: dict = {}


# ── DB 별 테이블 목록 ─────────────────────────────────────
def _mysql_tables(h, p, u, pw, db):
    import pymysql
    conn = pymysql.connect(host=h, port=int(p), user=u, password=pw,
                           database=db, charset="utf8mb4", connect_timeout=10,
                           autocommit=True)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT TABLE_NAME, COALESCE(TABLE_ROWS,0),
                   ROUND(COALESCE(DATA_LENGTH,0)/1024/1024,1), COALESCE(TABLE_COMMENT,'')
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE'
            ORDER BY TABLE_NAME
        """, (db,))
        return [{"schema_name": db, "table_name": r[0],
                 "row_count": r[1], "size_mb": float(r[2]), "comment": r[3]}
                for r in cur.fetchall()]
    finally:
        conn.close()


def _mysql_columns(h, p, u, pw, db, tbl):
    import pymysql
    conn = pymysql.connect(host=h, port=int(p), user=u, password=pw,
                           database=db, charset="utf8mb4", connect_timeout=10,
                           autocommit=True)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT COLUMN_NAME, COLUMN_TYPE, CHARACTER_MAXIMUM_LENGTH,
                   NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE,
                   COLUMN_DEFAULT, COLUMN_KEY, EXTRA, COLUMN_COMMENT
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
            ORDER BY ORDINAL_POSITION
        """, (db, tbl))
        return [{"name": r[0], "data_type": r[1], "length": r[2],
                 "precision": r[3], "scale": r[4], "nullable": r[5]=="YES",
                 "default": r[6], "is_pk": r[7]=="PRI",
                 "is_identity": "auto_increment" in (r[8] or ""),
                 "comment": r[9] or ""}
                for r in cur.fetchall()]
    finally:
        conn.close()


def _mssql_tables(h, p, u, pw, db):
    from app.core.db_conn import make_mssql_conn as _ms_conn
    conn = _ms_conn(h, p, u, pw, db)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT s.name, t.name, p.rows
            FROM sys.tables t
            JOIN sys.schemas s ON t.schema_id=s.schema_id
            JOIN sys.partitions p ON t.object_id=p.object_id AND p.index_id IN(0,1)
            ORDER BY s.name, t.name
        """)
        return [{"schema_name": r[0], "table_name": r[1],
                 "row_count": r[2] or 0, "size_mb": 0, "comment": ""}
                for r in cur.fetchall()]
    finally:
        conn.close()


def _query_tables(c: dict):
    db_type = c.get("db_type","mysql")
    h       = c.get("host","")
    p       = get_port(c)
    u, pw   = c.get("username",""), c.get("password","")
    db      = c.get("database","")
    if db_type in ("mysql","aurora","cloudsql","tidb","mariadb"):
        return _mysql_tables(h, p, u, pw, db)
    elif db_type in ("mssql","azure"):
        return _mssql_tables(h, p, u, pw, db)
    return []


# ── 타입 경고 규칙 (src_db → tgt_db 조합별) ──────────────
_WARN_RULES = {
    "mysql→mssql": [
        {
            "pattern": "auto_increment",    # COLUMN_TYPE 또는 EXTRA 에 포함 여부
            "src_type": "INT AUTO_INCREMENT",
            "tgt_type": "INT IDENTITY(1,1)",
            "level": "warn",
            "title": "AUTO_INCREMENT → IDENTITY 변환",
            "reason": "MySQL의 AUTO_INCREMENT는 MSSQL의 IDENTITY(1,1)로 변환됩니다. 시드값(시작값)과 증가값은 기본값(1,1)으로 설정됩니다.",
            "fix": "IDENTITY(seed, increment) 로 자동 변환하며, 기존 데이터의 ID 값은 그대로 유지됩니다. SET IDENTITY_INSERT ON 을 사용해 삽입합니다.",
            "auto_fix": True,
            "fix_action": "IDENTITY_INSERT"
        },
        {
            "pattern": "varchar",
            "src_type": "VARCHAR(n)",
            "tgt_type": "NVARCHAR(n)",
            "level": "info",
            "title": "VARCHAR → NVARCHAR 유니코드 변환",
            "reason": "MySQL VARCHAR를 MSSQL NVARCHAR로 변환하면 저장 공간이 약 2배 증가하지만, 한글·일어 등 멀티바이트 문자를 안전하게 저장할 수 있습니다.",
            "fix": "VARCHAR(255) → NVARCHAR(255) 자동 변환합니다. 데이터 손실은 없습니다.",
            "auto_fix": True,
            "fix_action": "NVARCHAR_CONVERT"
        },
        {
            "pattern": "tinyint(1)",
            "src_type": "TINYINT(1)",
            "tgt_type": "BIT",
            "level": "info",
            "title": "TINYINT(1) → BIT 변환",
            "reason": "MySQL에서 TINYINT(1)은 boolean(True/False)을 표현하는 관례적 타입입니다. MSSQL의 BIT 타입으로 안전하게 변환됩니다.",
            "fix": "0 → False, 1 → True 로 자동 변환합니다.",
            "auto_fix": True,
            "fix_action": "BOOL_CONVERT"
        },
        {
            "pattern": "enum",
            "src_type": "ENUM(...)",
            "tgt_type": "NVARCHAR(255)",
            "level": "warn",
            "title": "ENUM → NVARCHAR(255) 변환",
            "reason": "MSSQL에는 ENUM 타입이 없습니다. NVARCHAR(255)로 변환 후 CHECK 제약조건을 수동으로 추가해야 합니다.",
            "fix": "ENUM 값 목록을 CHECK 제약조건으로 자동 생성합니다. 예: CHECK (status IN ('active','inactive'))",
            "auto_fix": True,
            "fix_action": "ENUM_TO_CHECK"
        },
        {
            "pattern": "datetime",
            "src_type": "DATETIME",
            "tgt_type": "DATETIME2",
            "level": "info",
            "title": "DATETIME → DATETIME2 정밀도 향상",
            "reason": "MSSQL DATETIME2는 더 높은 정밀도(100나노초)를 제공합니다. MySQL DATETIME보다 범위도 넓어 데이터 손실이 없습니다.",
            "fix": "DATETIME → DATETIME2(6) 으로 변환합니다. 기존 데이터는 그대로 유지됩니다.",
            "auto_fix": True,
            "fix_action": "DATETIME2_CONVERT"
        },
        {
            "pattern": "longtext",
            "src_type": "LONGTEXT",
            "tgt_type": "NVARCHAR(MAX)",
            "level": "info",
            "title": "LONGTEXT → NVARCHAR(MAX) 변환",
            "reason": "MySQL LONGTEXT (최대 4GB)를 MSSQL NVARCHAR(MAX) (최대 2GB)로 변환합니다. 2GB 이상 데이터가 있으면 손실이 발생할 수 있습니다.",
            "fix": "자동으로 NVARCHAR(MAX)로 변환합니다. 2GB 초과 데이터 여부를 사전 확인하세요.",
            "auto_fix": True,
            "fix_action": "TEXT_CONVERT"
        },
    ],
    "mssql→mysql": [
        {
            "pattern": "datetimeoffset",
            "src_type": "DATETIMEOFFSET",
            "tgt_type": "VARCHAR(35)",
            "level": "warn",
            "title": "DATETIMEOFFSET → VARCHAR(35)",
            "reason": "MySQL에 DATETIMEOFFSET 타입이 없습니다. 시간대 정보(+09:00)를 포함한 문자열로 저장합니다.",
            "fix": "CONVERT(NVARCHAR, col)로 읽어 VARCHAR(35)에 저장합니다. 예: '2026-04-08 15:30:00 +09:00'",
            "auto_fix": True,
            "fix_action": "DATETIMEOFFSET_TO_VARCHAR"
        },
        {
            "pattern": "timestamp",
            "src_type": "TIMESTAMP/ROWVERSION",
            "tgt_type": "NULL (건너뜀)",
            "level": "warn",
            "title": "TIMESTAMP/ROWVERSION → NULL 처리",
            "reason": "MSSQL TIMESTAMP(rowversion)은 내부 버전 관리용 바이너리 값으로 MySQL에서 의미가 없습니다.",
            "fix": "이관 시 NULL로 대체합니다. 필요 시 타겟에서 BIGINT 컬럼으로 수동 처리하세요.",
            "auto_fix": True,
            "fix_action": "TIMESTAMP_TO_NULL"
        },
        {
            "pattern": "geography",
            "src_type": "GEOGRAPHY/GEOMETRY",
            "tgt_type": "NULL (건너뜀)",
            "level": "warn",
            "title": "GEOGRAPHY/GEOMETRY → NULL 처리",
            "reason": "MSSQL 공간 데이터 타입을 pyodbc로 직접 읽을 수 없습니다.",
            "fix": "이관 시 NULL로 대체합니다. 공간 데이터가 필요한 경우 별도 이관을 검토하세요.",
            "auto_fix": True,
            "fix_action": "GEO_TO_NULL"
        },
        {
            "pattern": "uniqueidentifier",
            "src_type": "UNIQUEIDENTIFIER",
            "tgt_type": "VARCHAR(36)",
            "level": "info",
            "title": "UNIQUEIDENTIFIER → VARCHAR(36)",
            "reason": "MySQL에 UUID 전용 타입이 없습니다. VARCHAR(36)에 문자열 형태로 저장합니다.",
            "fix": "자동으로 VARCHAR(36)으로 변환합니다. UUID 형식(xxxxxxxx-xxxx-...) 그대로 유지됩니다.",
            "auto_fix": True,
            "fix_action": "UUID_TO_VARCHAR"
        },
        {
            "pattern": "nvarchar",
            "src_type": "NVARCHAR",
            "tgt_type": "VARCHAR",
            "level": "info",
            "title": "NVARCHAR → VARCHAR(utf8mb4)",
            "reason": "MySQL utf8mb4 charset에서 VARCHAR는 NVARCHAR와 동일하게 유니코드를 지원합니다.",
            "fix": "NVARCHAR(n) → VARCHAR(n) 자동 변환합니다. utf8mb4 charset 사용 권장.",
            "auto_fix": True,
            "fix_action": "NVARCHAR_TO_VARCHAR"
        },
        {
            "pattern": "money",
            "src_type": "MONEY/SMALLMONEY",
            "tgt_type": "DECIMAL",
            "level": "info",
            "title": "MONEY → DECIMAL(19,4)",
            "reason": "MySQL에 MONEY 타입이 없습니다. 동일한 정밀도의 DECIMAL로 변환합니다.",
            "fix": "MONEY → DECIMAL(19,4), SMALLMONEY → DECIMAL(10,4) 자동 변환합니다.",
            "auto_fix": True,
            "fix_action": "MONEY_TO_DECIMAL"
        },
        {
            "pattern": "__null_violation__",
            "src_type": "NOT NULL",
            "tgt_type": "NULL 허용",
            "level": "warn",
            "title": "NOT NULL 컬럼에 NULL 데이터 존재",
            "reason": "소스 DB의 NOT NULL 컬럼에 실제 NULL 데이터가 있습니다. 이관 시 INSERT 오류가 발생합니다.",
            "fix": "해당 컬럼을 MySQL에서 NULL 허용으로 변경합니다. (ALTER TABLE ... MODIFY COLUMN ... NULL)",
            "auto_fix": True,
            "fix_action": "NULL_VIOLATION"
        },
    ],
    "mysql→postgresql": [
        {
            "pattern": "auto_increment",
            "src_type": "INT AUTO_INCREMENT",
            "tgt_type": "SERIAL",
            "level": "info",
            "title": "AUTO_INCREMENT → SERIAL 변환",
            "reason": "PostgreSQL의 SERIAL 타입은 MySQL AUTO_INCREMENT와 동일하게 자동 증가 정수를 생성합니다.",
            "fix": "INT AUTO_INCREMENT → SERIAL 로 자동 변환합니다.",
            "auto_fix": True,
            "fix_action": "SERIAL_CONVERT"
        },
        {
            "pattern": "tinyint(1)",
            "src_type": "TINYINT(1)",
            "tgt_type": "BOOLEAN",
            "level": "info",
            "title": "TINYINT(1) → BOOLEAN 변환",
            "reason": "PostgreSQL은 BOOLEAN 타입을 지원합니다. 0/1 값이 FALSE/TRUE로 변환됩니다.",
            "fix": "0 → FALSE, 1 → TRUE 자동 변환합니다.",
            "auto_fix": True,
            "fix_action": "BOOL_CONVERT"
        },
        {
            "pattern": "enum",
            "src_type": "ENUM(...)",
            "tgt_type": "TEXT + CHECK",
            "level": "warn",
            "title": "ENUM → TEXT + CHECK 제약조건",
            "reason": "PostgreSQL에서는 별도의 ENUM 타입을 생성하거나 TEXT + CHECK 제약조건을 사용합니다.",
            "fix": "CREATE TYPE 문으로 PostgreSQL ENUM 타입을 자동 생성합니다.",
            "auto_fix": True,
            "fix_action": "PG_ENUM_TYPE"
        },
    ],
}


# ── 선택된 테이블의 컬럼을 분석해 경고 항목과 영향 테이블 반환 ──
def _analyze_warnings(src_db_type: str, tgt_db_type: str,
                      conn_info: dict, table_names: list) -> list:
    key = f"{src_db_type}→{tgt_db_type}"
    rules = _WARN_RULES.get(key, [])
    if not rules:
        return []

    h  = conn_info.get("host","")
    p  = int(conn_info.get("port", 3306))
    u  = conn_info.get("username","")
    pw = conn_info.get("password","")
    db = conn_info.get("database","")

    # 분석 결과: rule별로 영향받는 테이블+컬럼 목록 수집
    results = []
    for rule in rules:
        affected = []  # {"table": str, "column": str, "col_type": str}
        for tbl in table_names:
            try:
                # ── NULL_VIOLATION: NOT NULL 컬럼에 실제 NULL 데이터 체크 ──
                if rule.get("fix_action") == "NULL_VIOLATION":
                    if src_db_type in ("mssql","azure","sqlserver"):
                        try:
                            from app.core.db_conn import make_mssql_conn
                            _nc = make_mssql_conn(h, p, u, pw, db)
                            _ncur = _nc.cursor()
                            # 전체 테이블 한 번에 NOT NULL + NULL 데이터 조회 (속도 최적화)
                            _tbl_list = "','".join(table_names)
                            _ncur.execute(f"""
                                SELECT t.name AS tbl, c.name AS col, tp.name AS dtype
                                FROM sys.columns c
                                JOIN sys.types tp ON c.user_type_id = tp.user_type_id
                                JOIN sys.tables t ON c.object_id = t.object_id
                                WHERE t.name IN ('{_tbl_list}')
                                AND c.is_nullable = 0
                                AND c.is_identity = 0
                                AND tp.name NOT IN ('timestamp','rowversion')
                            """)
                            _not_null_cols = _ncur.fetchall()
                            for _row in _not_null_cols:
                                _rtbl  = _row[0] if not isinstance(_row, dict) else _row["tbl"]
                                _cname = _row[1] if not isinstance(_row, dict) else _row["col"]
                                _dtype = _row[2] if not isinstance(_row, dict) else _row["dtype"]
                                if _rtbl != tbl: continue
                                try:
                                    _ncur.execute(f"SELECT TOP 1 1 FROM [{_rtbl}] WITH (NOLOCK) WHERE [{_cname}] IS NULL")
                                    if _ncur.fetchone():
                                        affected.append({
                                            "table":    _rtbl,
                                            "column":   _cname,
                                            "col_type": f"{_dtype} NOT NULL → NULL",
                                        })
                                except Exception:
                                    pass
                            _nc.close()
                        except Exception as _ne:
                            pass
                    continue  # NULL_VIOLATION은 아래 일반 패턴 체크 건너뜀

                if src_db_type in ("mysql","aurora","cloudsql","tidb","mariadb"):
                    cols = _mysql_columns(h, p, u, pw, db, tbl)
                    for col in cols:
                        col_type_lower = (col.get("data_type") or "").lower()
                        extra_lower    = str(col.get("is_identity","")).lower()
                        full_type      = col_type_lower + (" auto_increment" if col.get("is_identity") else "")
                        if rule["pattern"] in full_type or rule["pattern"] in col_type_lower:
                            affected.append({
                                "table":    tbl,
                                "column":   col["name"],
                                "col_type": col["data_type"],
                            })
            except Exception:
                pass  # 컬럼 조회 실패 시 해당 테이블 스킵

        results.append({
            **rule,
            "affected_tables": affected,
            "affected_count":  len(affected),
        })

    # 영향받는 테이블이 없는 규칙은 level을 'none'으로 표시
    for r in results:
        if r["affected_count"] == 0:
            r["level"] = "none"

    return results


# ── 엔드포인트 ────────────────────────────────────────────

@router.post("/connection")
def save_conn(body: dict):
    # v9 패치 #7: 저장 시점에 마스크/암호문을 평문으로 해결
    # (이후 /tables 등이 _conns 에서 꺼낼 때 이미 평문이 되도록)
    from app.core.password_resolver import resolve_password as _rpw
    body = dict(body)
    body["password"] = _rpw(
        body.get("password",""),
        profile_id=body.get("profile_id"),
        side=body.get("side","source"),
        host=body.get("host"), username=body.get("username"),
        database=body.get("database"),
    )
    _conns[body.get("side","source")] = body
    return {"ok": True}


@router.get("/tables")
def tables_by_params(
    side: str = "source", db_type: str = "", host: str = "",
    port: int = 3306, username: str = "", password: str = "", database: str = ""
):
    c = {
        "db_type":  db_type  or _conns.get(side,{}).get("db_type","mysql"),
        "host":     host     or _conns.get(side,{}).get("host",""),
        "port":     port     or _conns.get(side,{}).get("port") or default_port(db_type or _conns.get(side,{}).get("db_type","mysql")),
        "username": username or _conns.get(side,{}).get("username",""),
        "password": password or _conns.get(side,{}).get("password",""),
        "database": database or _conns.get(side,{}).get("database",""),
    }
    # v9 패치 #7: 마스크/암호문 password 해결
    from app.core.password_resolver import resolve_password
    c["password"] = resolve_password(
        c["password"], side=side,
        host=c["host"], username=c["username"], database=c["database"],
    )
    if not c["host"] or not c["database"]:
        return []
    try:
        print(f"[DEBUG tables] c={c}", flush=True)
        result = _query_tables(c)
        print(f"[DEBUG tables] 성공: {len(result)}개", flush=True)
        return result
    except Exception as e:
        import traceback
        print(f"[DEBUG tables] 오류: {e}", flush=True)
        print(traceback.format_exc(), flush=True)
        raise HTTPException(500, f"테이블 조회 실패: {e}")


@router.get("/{cid}/tables")
def tables_by_id(cid: str):
    c = _conns.get(cid) or _conns.get("source")
    if not c:
        return _mock_tables()
    try:
        return _query_tables(c)
    except Exception as e:
        raise HTTPException(500, str(e))





@router.post("/analyze-warnings")
def analyze_warnings(body: dict):
    """
    선택된 테이블들의 컬럼을 실제로 분석하여
    타입 변환 경고 + 영향받는 테이블/컬럼 목록 반환
    """
    src_db_type = body.get("src_db_type","mysql")
    tgt_db_type = body.get("tgt_db_type","mssql")
    tables      = body.get("tables", [])
    conn_info   = body.get("conn_info") or _conns.get("source", {})

    if not conn_info.get("host") or not conn_info.get("database"):
        # 연결 정보 없으면 Mock
        return _mock_warnings(src_db_type, tgt_db_type)

    try:
        return _analyze_warnings(src_db_type, tgt_db_type, conn_info, tables)
    except Exception as e:
        raise HTTPException(500, f"경고 분석 실패: {e}")


@router.get("/diff")
def diff(src: str="", tgt: str="", table: str=""):
    """
    소스 테이블 DDL을 조회하고 타겟 DB 방언으로 변환하여 반환
    """
    if not table:
        return {"table": table, "src_ddl": "", "tgt_ddl": "", "warnings": []}

    src_conn = _conns.get("source", {})
    tgt_conn = _conns.get("target", {})

    if not src_conn.get("host"):
        raise HTTPException(400, "소스 DB 연결 정보가 없습니다. 먼저 연결 테스트를 해주세요.")

    src_db_type = src_conn.get("db_type", "mysql")
    tgt_db_type = tgt_conn.get("db_type", "mssql") if tgt_conn.get("host") else "mssql"

    # ── 소스 DDL 조회 ──────────────────────────────────────
    src_ddl = ""
    try:
        if src_db_type in ("mysql", "aurora", "mariadb", "tidb"):
            import pymysql
            conn = pymysql.connect(
                host=src_conn["host"], port=int(src_conn.get("port", 3306)),
                user=src_conn.get("username", ""), password=src_conn.get("password", ""),
                database=src_conn.get("database", ""), charset="utf8mb4",
                connect_timeout=10, cursorclass=pymysql.cursors.DictCursor
            )
            try:
                cur = conn.cursor()
                cur.execute(f"SHOW CREATE TABLE `{table}`")
                row = cur.fetchone()
                if row:
                    src_ddl = row.get("Create Table") or list(row.values())[1]
            finally:
                conn.close()

        elif src_db_type in ("mssql", "azure"):
            from app.core.db_conn import make_mssql_conn
            conn = make_mssql_conn(
                src_conn["host"], src_conn.get("port", 1434),
                src_conn.get("username", ""), src_conn.get("password", ""),
                src_conn.get("database", "")
            )
            try:
                cur = conn.cursor()
                # 컬럼 정보로 DDL 재구성
                cur.execute("""
                    SELECT
                        c.name                                          AS col_name,
                        tp.name                                         AS type_name,
                        c.max_length, c.precision, c.scale,
                        c.is_nullable, c.is_identity,
                        OBJECT_DEFINITION(c.default_object_id)          AS col_default,
                        cc.definition                                   AS check_def,
                        ic.seed_value, ic.increment_value
                    FROM sys.columns c
                    JOIN sys.types tp ON c.user_type_id = tp.user_type_id
                    LEFT JOIN sys.check_constraints cc
                        ON cc.parent_object_id = c.object_id AND cc.parent_column_id = c.column_id
                    LEFT JOIN sys.identity_columns ic
                        ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                    WHERE c.object_id = OBJECT_ID(?)
                    ORDER BY c.column_id
                """, (table,))
                cols = cur.fetchall()

                # PK 조회
                cur.execute("""
                    SELECT c.name FROM sys.key_constraints kc
                    JOIN sys.index_columns ic ON ic.object_id = kc.parent_object_id AND ic.index_id = kc.unique_index_id
                    JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
                    WHERE kc.parent_object_id = OBJECT_ID(?) AND kc.type = 'PK'
                    ORDER BY ic.key_ordinal
                """, (table,))
                pk_cols = [r[0] for r in cur.fetchall()]

                if cols:
                    lines = [f"CREATE TABLE [{table}] ("]
                    col_defs = []
                    for c in cols:
                        cn, tn = c[0], c[1]
                        ml, prec, scale = c[2], c[3], c[4]
                        nullable, is_id = c[5], c[6]
                        col_default = c[7]
                        seed, incr = c[9], c[10]
                        # 타입 문자열
                        if tn in ("nvarchar", "varchar", "nchar", "char", "varbinary", "binary"):
                            size = "MAX" if ml == -1 else str(ml if tn.startswith("n") else ml)
                            type_str = f"{tn.upper()}({size})"
                        elif tn in ("decimal", "numeric"):
                            type_str = f"{tn.upper()}({prec},{scale})"
                        elif tn == "float":
                            type_str = f"FLOAT({prec})"
                        else:
                            type_str = tn.upper()
                        id_str = f" IDENTITY({seed or 1},{incr or 1})" if is_id else ""
                        null_str = " NOT NULL" if not nullable else " NULL"
                        def_str = f" DEFAULT {col_default}" if col_default else ""
                        col_defs.append(f"    [{cn}] {type_str}{id_str}{null_str}{def_str}")
                    if pk_cols:
                        pk_str = ", ".join(f"[{c}]" for c in pk_cols)
                        col_defs.append(f"    CONSTRAINT [PK_{table}] PRIMARY KEY ({pk_str})")
                    lines.append(",\n".join(col_defs))
                    lines.append(");")
                    src_ddl = "\n".join(lines)
            finally:
                conn.close()
    except Exception as e:
        src_ddl = f"-- DDL 조회 오류: {e}"

    # ── 변환기로 타겟 DDL 생성 ─────────────────────────────
    tgt_ddl = ""
    warnings = []
    try:
        from app.api.routes.sql_converter import convert_sql
        result = convert_sql(src_ddl, src_db_type, tgt_db_type)
        tgt_ddl   = result.get("converted", src_ddl)
        warnings  = result.get("warnings", [])
    except Exception as e:
        tgt_ddl  = f"-- 변환 오류: {e}"
        warnings = [str(e)]

    return {
        "table":    table,
        "src_ddl":  src_ddl,
        "tgt_ddl":  tgt_ddl,
        "warnings": warnings,
        "src_db":   src_db_type,
        "tgt_db":   tgt_db_type,
    }


def _mock_tables():
    return [
        {"schema_name":"dbo","table_name":"customers",  "row_count":92410, "size_mb":42,"comment":""},
        {"schema_name":"dbo","table_name":"orders",     "row_count":480320,"size_mb":210,"comment":""},
        {"schema_name":"dbo","table_name":"order_items","row_count":1204800,"size_mb":580,"comment":""},
    ]

def _mock_detail(table):
    return {"schema":"dbo","name":table,"columns":[
        {"name":"id","data_type":"INT","nullable":False,"is_pk":True,"is_identity":True},
        {"name":"name","data_type":"NVARCHAR(255)","nullable":False,"is_pk":False,"is_identity":False},
    ],"primary_keys":["id"]}

def _mock_warnings(src, tgt):
    key = f"{src}→{tgt}"
    rules = _WARN_RULES.get(key, [])
    return [{ **r, "affected_tables": [], "affected_count": 0 } for r in rules]


# ── 컬럼 상세 (쿼리 파라미터 방식) ──────────────────────────
@router.get("/{cid}/tables/{table}")
def get_col_detail(
    cid: str, table: str,
    db_type: str="", host: str="", port: int=3306,
    username: str="", password: str="", database: str=""
):
    c = {
        "db_type":  db_type  or (_conns.get(cid) or _conns.get("source", {})).get("db_type","mysql"),
        "host":     host     or (_conns.get(cid) or _conns.get("source", {})).get("host",""),
        "port":     port     or (_conns.get(cid) or _conns.get("source", {})).get("port",3306),
        "username": username or (_conns.get(cid) or _conns.get("source", {})).get("username",""),
        "password": password or (_conns.get(cid) or _conns.get("source", {})).get("password",""),
        "database": database or (_conns.get(cid) or _conns.get("source", {})).get("database",""),
    }
    # v9 패치 #8: password resolve
    from app.core.password_resolver import resolve_password
    c["password"] = resolve_password(c["password"], side="source",
        host=c["host"], username=c["username"], database=c["database"])
    if not c["host"] or not c["database"]:
        return _mock_detail(table)
    try:
        dt = c["db_type"]
        h,p,u,pw,db = c["host"],int(c["port"]),c["username"],c["password"],c["database"]
        if dt in ("mysql","aurora","cloudsql","tidb","mariadb"):
            cols = _mysql_columns(h,p,u,pw,db,table)
        elif dt in ("mssql","azure","sqlserver"):
            cols = _mssql_columns(h,p,u,pw,db,table)
        else:
            return _mock_detail(table)
        return {"schema":db,"name":table,"columns":cols,
                "primary_keys":[col["name"] for col in cols if col.get("is_pk")]}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{cid}/tables/{table}")
def table_detail_with_params(
    cid: str, table: str,
    db_type: str="", host: str="", port: int=3306,
    username: str="", password: str="", database: str=""
):
    """컬럼 상세 - 쿼리 파라미터로 연결 정보를 직접 받을 수 있음"""
    # 파라미터 우선, 없으면 저장된 연결 정보 사용
    c = {
        "db_type":  db_type  or _conns.get(cid,{}).get("db_type") or _conns.get("source",{}).get("db_type","mysql"),
        "host":     host     or _conns.get(cid,{}).get("host") or _conns.get("source",{}).get("host",""),
        "port":     port     or _conns.get(cid,{}).get("port") or _conns.get("source",{}).get("port",3306),
        "username": username or _conns.get(cid,{}).get("username") or _conns.get("source",{}).get("username",""),
        "password": password or _conns.get(cid,{}).get("password") or _conns.get("source",{}).get("password",""),
        "database": database or _conns.get(cid,{}).get("database") or _conns.get("source",{}).get("database",""),
    }
    # v9 패치 #8: password resolve
    from app.core.password_resolver import resolve_password
    c["password"] = resolve_password(c["password"], side="source",
        host=c["host"], username=c["username"], database=c["database"])
    if not c["host"] or not c["database"]:
        return _mock_detail(table)
    try:
        dt = c["db_type"]
        h,p,u,pw,db = c["host"],c["port"],c["username"],c["password"],c["database"]
        if dt in ("mysql","aurora","cloudsql","tidb","mariadb"):
            cols = _mysql_columns(h, p, u, pw, db, table)
        elif dt in ("mssql","azure","sqlserver"):
            cols = _mssql_columns(h, p, u, pw, db, table)
        else:
            return _mock_detail(table)
        return {"schema": db, "name": table, "columns": cols,
                "primary_keys": [col["name"] for col in cols if col.get("is_pk")]}
    except Exception as e:
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════════════
# 오브젝트 조회 (Function, Procedure, Trigger, View, Event)
# ═══════════════════════════════════════════════════════════════

def _get_objects_mysql(h, p, u, pw, db) -> dict:
    """MySQL 전체 오브젝트 조회"""
    import pymysql
    conn = pymysql.connect(host=h, port=int(p), user=u, password=pw,
                           database=db, charset="utf8mb4", connect_timeout=10,
                           cursorclass=pymysql.cursors.DictCursor)
    result = {"functions":[], "procedures":[], "triggers":[], "views":[], "events":[]}
    try:
        cur = conn.cursor()
        # Functions
        cur.execute("""
            SELECT ROUTINE_NAME as name, ROUTINE_TYPE as type,
                   DATA_TYPE as return_type, ROUTINE_DEFINITION as definition,
                   CREATED, LAST_ALTERED as modified,
                   ROUTINE_COMMENT as comment
            FROM information_schema.ROUTINES
            WHERE ROUTINE_SCHEMA=%s AND ROUTINE_TYPE='FUNCTION'
            ORDER BY ROUTINE_NAME
        """, (db,))
        result["functions"] = cur.fetchall()

        # Procedures
        cur.execute("""
            SELECT ROUTINE_NAME as name, ROUTINE_TYPE as type,
                   ROUTINE_DEFINITION as definition,
                   CREATED, LAST_ALTERED as modified,
                   ROUTINE_COMMENT as comment
            FROM information_schema.ROUTINES
            WHERE ROUTINE_SCHEMA=%s AND ROUTINE_TYPE='PROCEDURE'
            ORDER BY ROUTINE_NAME
        """, (db,))
        result["procedures"] = cur.fetchall()

        # Triggers
        cur.execute("""
            SELECT TRIGGER_NAME as name, EVENT_MANIPULATION as event,
                   EVENT_OBJECT_TABLE as table_name,
                   ACTION_TIMING as timing,
                   ACTION_STATEMENT as definition,
                   CREATED as created
            FROM information_schema.TRIGGERS
            WHERE TRIGGER_SCHEMA=%s
            ORDER BY TRIGGER_NAME
        """, (db,))
        result["triggers"] = cur.fetchall()

        # Views
        cur.execute("""
            SELECT TABLE_NAME as name,
                   VIEW_DEFINITION as definition,
                   CHECK_OPTION, IS_UPDATABLE
            FROM information_schema.VIEWS
            WHERE TABLE_SCHEMA=%s
            ORDER BY TABLE_NAME
        """, (db,))
        result["views"] = cur.fetchall()

        # Events
        try:
            cur.execute("""
                SELECT EVENT_NAME as name, EVENT_TYPE as type,
                       EXECUTE_AT, INTERVAL_VALUE, INTERVAL_FIELD,
                       STATUS, EVENT_DEFINITION as definition
                FROM information_schema.EVENTS
                WHERE EVENT_SCHEMA=%s
            """, (db,))
            result["events"] = cur.fetchall()
        except Exception:
            pass
    finally:
        conn.close()

    # datetime → string 변환
    import datetime
    def serial(obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return str(obj)
        return obj
    for cat in result:
        result[cat] = [{k: serial(v) for k,v in row.items()} for row in result[cat]]
    return result


def _get_object_ddl_mysql(h, p, u, pw, db, obj_type: str, obj_name: str) -> str:
    """MySQL 오브젝트 DDL(소스 코드) 조회"""
    import pymysql
    conn = pymysql.connect(host=h, port=int(p), user=u, password=pw,
                           database=db, charset="utf8mb4", connect_timeout=10,
                           cursorclass=pymysql.cursors.DictCursor)
    try:
        cur = conn.cursor()
        if obj_type == "function":
            cur.execute(f"SHOW CREATE FUNCTION `{db}`.`{obj_name}`")
            row = cur.fetchone()
            return row.get("Create Function","") if row else ""
        elif obj_type == "procedure":
            cur.execute(f"SHOW CREATE PROCEDURE `{db}`.`{obj_name}`")
            row = cur.fetchone()
            return row.get("Create Procedure","") if row else ""
        elif obj_type == "trigger":
            cur.execute(f"SHOW CREATE TRIGGER `{db}`.`{obj_name}`")
            row = cur.fetchone()
            return row.get("SQL Original Statement","") if row else ""
        elif obj_type == "view":
            cur.execute(f"SHOW CREATE VIEW `{db}`.`{obj_name}`")
            row = cur.fetchone()
            return row.get("Create View","") if row else ""
    finally:
        conn.close()
    return ""


def _convert_object_to_mssql(obj_type: str, obj_name: str, source_ddl: str, src_db: str) -> dict:
    """MySQL DDL → MSSQL DDL 변환"""
    import re
    ddl = source_ddl
    warnings = []
    changes = []

    # 공통: 백틱 → 대괄호
    ddl = re.sub(r'`([^`]+)`', r'[\1]', ddl)
    changes.append("백틱 → 대괄호")

    # DEFINER 제거
    ddl = re.sub(r'\s*DEFINER\s*=\s*`[^`]+`@`[^`]+`\s*', ' ', ddl)

    # 타입 변환 (공통)
    type_replacements = [
        (r'\bVARCHAR\b',       'NVARCHAR'),
        (r'\bDATETIME\b',      'DATETIME2(6)'),
        (r'\bTINYINT\(1\)',    'BIT'),
        (r'\bLONGTEXT\b',      'NVARCHAR(MAX)'),
        (r'\bINT\s+UNSIGNED\b','BIGINT'),
        (r'\bNOW\(\)',          'GETDATE()'),
        (r'\bIFNULL\s*\(',     'ISNULL('),
        (r'\bCURRENT_TIMESTAMP\b', 'GETDATE()'),
    ]
    for pattern, repl in type_replacements:
        new_ddl = re.sub(pattern, repl, ddl, flags=re.IGNORECASE)
        if new_ddl != ddl:
            p_clean = pattern.replace('\\b', '').replace('\b', '')
            changes.append(f"{p_clean} → {repl}")
            ddl = new_ddl

    if obj_type == "function":
        # FUNCTION → CREATE OR ALTER FUNCTION
        ddl = re.sub(r'\bCREATE\s+FUNCTION\b', 'CREATE OR ALTER FUNCTION', ddl, flags=re.IGNORECASE)
        # RETURNS 타입 처리
        ddl = re.sub(r'\bRETURNS\s+INT\b', 'RETURNS INT', ddl, flags=re.IGNORECASE)
        # MySQL 함수 본문: BEGIN...END 유지
        if 'DETERMINISTIC' in ddl.upper():
            ddl = re.sub(r'\bDETERMINISTIC\b', '', ddl, flags=re.IGNORECASE)
            warnings.append("DETERMINISTIC 키워드 제거됨")
        if 'READS SQL DATA' in ddl.upper():
            ddl = re.sub(r'\bREADS\s+SQL\s+DATA\b', '', ddl, flags=re.IGNORECASE)
        if 'NO SQL' in ddl.upper():
            ddl = re.sub(r'\bNO\s+SQL\b', '', ddl, flags=re.IGNORECASE)
        # MSSQL 함수 헤더 래핑
        warnings.append("MSSQL 함수는 WITH SCHEMABINDING 또는 RETURNS TABLE 검토 필요")

    elif obj_type == "procedure":
        ddl = re.sub(r'\bCREATE\s+PROCEDURE\b', 'CREATE OR ALTER PROCEDURE', ddl, flags=re.IGNORECASE)
        # MySQL 파라미터 IN/OUT → MSSQL @param
        def convert_params(m):
            direction = m.group(1).upper()  # IN / OUT / INOUT
            name      = m.group(2)
            type_     = m.group(3)
            if direction == 'OUT':
                return f'@{name} {type_} OUTPUT'
            elif direction == 'INOUT':
                return f'@{name} {type_} OUTPUT'
            else:
                return f'@{name} {type_}'
        ddl = re.sub(r'\b(IN|OUT|INOUT)\s+(\w+)\s+(\w+)', convert_params, ddl, flags=re.IGNORECASE)
        changes.append("IN/OUT 파라미터 → @param 형식")
        # DELIMITER 제거
        ddl = re.sub(r'\bDELIMITER\b[^\n]*\n?', '', ddl, flags=re.IGNORECASE)

    elif obj_type == "trigger":
        ddl = re.sub(r'\bCREATE\s+TRIGGER\b', 'CREATE OR ALTER TRIGGER', ddl, flags=re.IGNORECASE)
        # AFTER/BEFORE INSERT → ON table AFTER INSERT
        ddl = re.sub(r'\bFOR EACH ROW\b', '', ddl, flags=re.IGNORECASE)
        # NEW. → INSERTED. , OLD. → DELETED.
        ddl = re.sub(r'\bNEW\.', 'INSERTED.', ddl)
        ddl = re.sub(r'\bOLD\.', 'DELETED.', ddl)
        changes.append("NEW. → INSERTED., OLD. → DELETED.")
        warnings.append("트리거 이벤트 문법(AFTER INSERT ON ...) 수동 검토 필요")

    elif obj_type == "view":
        ddl = re.sub(r'\bCREATE\s+(?:OR REPLACE\s+)?(?:ALGORITHM\s*=\s*\w+\s+)?(?:DEFINER\s*=[^V]+)?VIEW\b',
                     'CREATE OR ALTER VIEW', ddl, flags=re.IGNORECASE)
        ddl = re.sub(r'\bWITH\s+\w+\s+CHECK\s+OPTION\b', '', ddl, flags=re.IGNORECASE)
        changes.append("CREATE VIEW 형식 변환")

    return {"converted_ddl": ddl, "changes": changes, "warnings": warnings, "obj_type": obj_type, "obj_name": obj_name}




# ══ DB 오브젝트 조회 (함수, 프로시저, 트리거, 뷰) ═══════════

def _get_objects_mysql(h, p, u, pw, db):
    """MySQL 오브젝트 목록 — SHOW CREATE로 완전한 DDL 포함"""
    import pymysql
    conn = pymysql.connect(host=h, port=int(p), user=u, password=pw,
                           database=db, charset="utf8mb4", connect_timeout=10,
                           cursorclass=pymysql.cursors.DictCursor)
    result = {}

    def _show_create_proc(cur, obj_type, name):
        """SHOW CREATE PROCEDURE/FUNCTION — 완전한 DDL 반환"""
        try:
            cur.execute(f"SHOW CREATE {obj_type} `{name}`")
            row = cur.fetchone()
            if not row: return ""
            # DictCursor: key는 'Create Procedure' 또는 'Create Function'
            key = f"Create {obj_type.capitalize()}"
            if key in row: return row[key] or ""
            # fallback: 3번째 컬럼
            vals = list(row.values())
            return vals[2] if len(vals) > 2 else ""
        except Exception as e:
            return f"-- SHOW CREATE {obj_type} {name} 실패: {e}"

    def _show_create_view(cur, name):
        try:
            cur.execute(f"SHOW CREATE VIEW `{name}`")
            row = cur.fetchone()
            if not row: return ""
            return row.get("Create View") or (list(row.values())[1] if len(row) > 1 else "")
        except Exception as e:
            return f"-- SHOW CREATE VIEW {name} 실패: {e}"

    def _show_create_trigger(cur, name):
        try:
            cur.execute(f"SHOW CREATE TRIGGER `{name}`")
            row = cur.fetchone()
            if not row: return ""
            return row.get("SQL Original Statement") or (list(row.values())[2] if len(row) > 2 else "")
        except Exception as e:
            return f"-- SHOW CREATE TRIGGER {name} 실패: {e}"

    try:
        cur = conn.cursor()
        # 프로시저 목록
        cur.execute("SELECT ROUTINE_NAME, CREATED FROM information_schema.ROUTINES "
                    "WHERE ROUTINE_SCHEMA=%s AND ROUTINE_TYPE='PROCEDURE' ORDER BY ROUTINE_NAME", (db,))
        proc_list = cur.fetchall()
        result["procedures"] = []
        for r in proc_list:
            name = r["ROUTINE_NAME"]
            full_ddl = _show_create_proc(cur, "PROCEDURE", name)
            result["procedures"].append({
                "name": name, "type": "PROCEDURE",
                "created": str(r["CREATED"]), "body": full_ddl
            })

        # 함수 목록
        cur.execute("SELECT ROUTINE_NAME, DATA_TYPE, CREATED FROM information_schema.ROUTINES "
                    "WHERE ROUTINE_SCHEMA=%s AND ROUTINE_TYPE='FUNCTION' ORDER BY ROUTINE_NAME", (db,))
        func_list = cur.fetchall()
        result["functions"] = []
        for r in func_list:
            name = r["ROUTINE_NAME"]
            full_ddl = _show_create_proc(cur, "FUNCTION", name)
            result["functions"].append({
                "name": name, "type": "FUNCTION",
                "return_type": r["DATA_TYPE"], "created": str(r["CREATED"]),
                "body": full_ddl
            })

        # 트리거 목록
        cur.execute("SELECT TRIGGER_NAME, EVENT_MANIPULATION, EVENT_OBJECT_TABLE, ACTION_TIMING, CREATED "
                    "FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=%s ORDER BY TRIGGER_NAME", (db,))
        trig_list = cur.fetchall()
        result["triggers"] = []
        for r in trig_list:
            name = r["TRIGGER_NAME"]
            full_ddl = _show_create_trigger(cur, name)
            result["triggers"].append({
                "name": name, "type": "TRIGGER",
                "event": f"{r['ACTION_TIMING']} {r['EVENT_MANIPULATION']}",
                "table": r["EVENT_OBJECT_TABLE"],
                "created": str(r["CREATED"]), "body": full_ddl
            })

        # 뷰 목록
        cur.execute("SELECT TABLE_NAME FROM information_schema.VIEWS "
                    "WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME", (db,))
        view_list = cur.fetchall()
        result["views"] = []
        for r in view_list:
            name = r["TABLE_NAME"]
            full_ddl = _show_create_view(cur, name)
            result["views"].append({
                "name": name, "type": "VIEW", "body": full_ddl
            })
    finally:
        conn.close()
    return result


def _get_objects_mssql(h, p, u, pw, db):
    """MSSQL 오브젝트 목록 — db_conn 사용 (Encrypt=no 제거)
    v52: sys.schemas JOIN → schema_name 필드 추가.
    `dbo` 하드코딩 제거를 위해 실제 스키마를 프론트/테스트 호출에 전달.
    """
    from app.core.db_conn import make_mssql_conn
    conn = make_mssql_conn(h, p, u, pw, db)
    result = {}
    try:
        cur = conn.cursor()
        # 프로시저 — v52: sys.schemas JOIN
        cur.execute("""SELECT s.name AS schema_name, o.name, o.create_date, o.modify_date, m.definition
                       FROM sys.objects o
                       JOIN sys.schemas s ON o.schema_id=s.schema_id
                       LEFT JOIN sys.sql_modules m ON o.object_id=m.object_id
                       WHERE o.type='P' ORDER BY s.name, o.name""")
        result["procedures"] = [
            {"name": r[1], "schema_name": r[0], "type": "PROCEDURE",
             "created": str(r[2]), "body": r[4] or ""}
            for r in cur.fetchall()
        ]
        # 함수 — v52
        cur.execute("""SELECT s.name AS schema_name, o.name, o.create_date, o.type, m.definition
                       FROM sys.objects o
                       JOIN sys.schemas s ON o.schema_id=s.schema_id
                       LEFT JOIN sys.sql_modules m ON o.object_id=m.object_id
                       WHERE o.type IN ('FN','IF','TF') ORDER BY s.name, o.name""")
        result["functions"] = [
            {"name": r[1], "schema_name": r[0], "type": "FUNCTION",
             "fn_type": (r[3].strip() if hasattr(r[3], 'strip') else r[3]),
             "created": str(r[2]), "body": r[4] or ""}
            for r in cur.fetchall()
        ]
        # 트리거 — 트리거도 스키마 개념 존재
        cur.execute("""SELECT s.name AS schema_name, t.name, o.name AS tbl, m.definition
                       FROM sys.triggers t
                       JOIN sys.objects o ON t.parent_id=o.object_id
                       JOIN sys.schemas s ON o.schema_id=s.schema_id
                       LEFT JOIN sys.sql_modules m ON t.object_id=m.object_id""")
        result["triggers"] = [
            {"name": r[1], "schema_name": r[0], "type": "TRIGGER",
             "table": r[2], "body": r[3] or ""}
            for r in cur.fetchall()
        ]
        # 뷰 — v52
        cur.execute("""SELECT s.name AS schema_name, o.name, m.definition
                       FROM sys.views o
                       JOIN sys.schemas s ON o.schema_id=s.schema_id
                       LEFT JOIN sys.sql_modules m ON o.object_id=m.object_id
                       ORDER BY s.name, o.name""")
        result["views"] = [
            {"name": r[1], "schema_name": r[0], "type": "VIEW", "body": r[2] or ""}
            for r in cur.fetchall()
        ]
    finally:
        conn.close()
    return result


@router.get("/dependencies")
def get_dependencies(
    side: str = "source",
    db_type: str = "mysql",
    host: str = "",
    port: int = 3306,
    username: str = "",
    password: str = "",
    database: str = "",
):
    """테이블 간 FK 의존성 + 이관 순서 계산"""
    import collections

    def _conn_mysql():
        import pymysql
        return pymysql.connect(
            host=host, port=port, user=username, password=password,
            database=database, charset="utf8mb4", connect_timeout=8,
            cursorclass=pymysql.cursors.DictCursor
        )

    def _conn_mssql():
        from app.core.db_conn import make_mssql_conn
        return make_mssql_conn(host, port, username, password, database)

    try:
        if db_type in ("mysql","aurora","mariadb","tidb"):
            conn = _conn_mysql()
            cur  = conn.cursor()
            # FK 관계
            cur.execute("""
                SELECT
                    kcu.TABLE_NAME       AS tbl,
                    kcu.COLUMN_NAME      AS col,
                    kcu.REFERENCED_TABLE_NAME  AS ref_tbl,
                    kcu.REFERENCED_COLUMN_NAME AS ref_col,
                    rc.DELETE_RULE       AS on_delete,
                    rc.UPDATE_RULE       AS on_update,
                    kcu.CONSTRAINT_NAME  AS fk_name
                FROM information_schema.KEY_COLUMN_USAGE kcu
                JOIN information_schema.REFERENTIAL_CONSTRAINTS rc
                    ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
                    AND kcu.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA
                WHERE kcu.TABLE_SCHEMA = %s
                  AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
                ORDER BY kcu.TABLE_NAME, kcu.COLUMN_NAME
            """, (database,))
            fk_rows = cur.fetchall()
            # 테이블 row count
            cur.execute("""
                SELECT TABLE_NAME, COALESCE(TABLE_ROWS,0) AS row_count
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE'
                ORDER BY TABLE_NAME
            """, (database,))
            tbl_rows = {r["TABLE_NAME"]: r["row_count"] for r in cur.fetchall()}
            conn.close()

        elif db_type in ("mssql","azure"):
            conn = _conn_mssql()
            cur  = conn.cursor()
            cur.execute("""
                SELECT
                    tp.name  AS tbl,
                    cp.name  AS col,
                    tr.name  AS ref_tbl,
                    cr.name  AS ref_col,
                    fk.name  AS fk_name,
                    CASE fk.delete_referential_action WHEN 0 THEN 'NO ACTION'
                        WHEN 1 THEN 'CASCADE' WHEN 2 THEN 'SET NULL'
                        WHEN 3 THEN 'SET DEFAULT' ELSE 'NO ACTION' END AS on_delete,
                    CASE fk.update_referential_action WHEN 0 THEN 'NO ACTION'
                        WHEN 1 THEN 'CASCADE' WHEN 2 THEN 'SET NULL'
                        WHEN 3 THEN 'SET DEFAULT' ELSE 'NO ACTION' END AS on_update
                FROM sys.foreign_keys fk
                JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
                JOIN sys.tables tp ON fkc.parent_object_id = tp.object_id
                JOIN sys.columns cp ON fkc.parent_object_id = cp.object_id AND fkc.parent_column_id = cp.column_id
                JOIN sys.tables tr ON fkc.referenced_object_id = tr.object_id
                JOIN sys.columns cr ON fkc.referenced_object_id = cr.object_id AND fkc.referenced_column_id = cr.column_id
                ORDER BY tp.name, cp.name
            """)
            raw = cur.fetchall()
            cols = [d[0] for d in cur.description]
            fk_rows = [dict(zip(cols, r)) for r in raw]
            cur.execute("""
                SELECT t.name AS TABLE_NAME,
                    SUM(p.rows) AS row_count
                FROM sys.tables t
                JOIN sys.partitions p ON t.object_id=p.object_id AND p.index_id IN (0,1)
                GROUP BY t.name ORDER BY t.name
            """)
            raw2 = cur.fetchall()
            tbl_rows = {r[0]: int(r[1] or 0) for r in raw2}
            conn.close()
        else:
            return {"tables":[], "fks":[], "order":[]}

        # 구조화
        # FK 맵
        fk_map = collections.defaultdict(list)
        for r in fk_rows:
            fk_map[r["tbl"]].append({
                "col":      r["col"],
                "refTable": r["ref_tbl"],
                "refCol":   r["ref_col"],
                "onDelete": r.get("on_delete","NO ACTION"),
                "onUpdate": r.get("on_update","NO ACTION"),
                "fkName":   r.get("fk_name",""),
            })

        all_tables = sorted(tbl_rows.keys())

        # 위상 정렬 (이관 순서)
        graph   = {t: set() for t in all_tables}
        in_deg  = {t: 0     for t in all_tables}
        for r in fk_rows:
            child, parent = r["tbl"], r["ref_tbl"]
            if child in graph and parent in graph and parent not in graph[child]:
                graph[child].add(parent)
                in_deg[child] = in_deg.get(child,0) + 1

        queue   = collections.deque(t for t in all_tables if in_deg.get(t,0)==0)
        ordered = []
        visited = set()
        while queue:
            t = queue.popleft()
            if t in visited: continue
            visited.add(t)
            ordered.append(t)
            # 이 테이블을 참조하는 자식들 in_deg 감소
            for child, parents in graph.items():
                if t in parents and child not in visited:
                    in_deg[child] = max(0, in_deg.get(child,0)-1)
                    if in_deg[child]==0:
                        queue.append(child)
        # 순환 참조된 것 추가
        for t in all_tables:
            if t not in visited:
                ordered.append(t)

        order_result = []
        for t in ordered:
            fks_here = fk_map.get(t,[])
            refs = [f["refTable"] for f in fks_here]
            if not refs:
                reason = "참조 없음 — 독립 테이블"
            else:
                reason = ", ".join(sorted(set(refs))) + " 참조"
            order_result.append({
                "name":   t,
                "rows":   tbl_rows.get(t,0),
                "reason": reason,
                "deps":   refs,
            })

        tables_result = []
        for t in all_tables:
            tables_result.append({
                "name": t,
                "rows": tbl_rows.get(t,0),
                "fks":  fk_map.get(t,[]),
            })

        return {
            "tables": tables_result,
            "fks":    fk_rows,
            "order":  order_result,
        }

    except Exception as e:
        raise HTTPException(500, f"의존성 분석 실패: {e}")


@router.get("/objects")
def get_objects(
    side: str = "source", db_type: str = "", host: str = "",
    port: int = 3306, username: str = "", password: str = "", database: str = ""
):
    """DB 오브젝트 전체 목록 (프로시저, 함수, 트리거, 뷰)"""
    c = {
        "db_type":  db_type  or _conns.get(side,{}).get("db_type","mysql"),
        "host":     host     or _conns.get(side,{}).get("host",""),
        "port":     port     or _conns.get(side,{}).get("port") or default_port(db_type or _conns.get(side,{}).get("db_type","mysql")),
        "username": username or _conns.get(side,{}).get("username",""),
        "password": password or _conns.get(side,{}).get("password",""),
        "database": database or _conns.get(side,{}).get("database",""),
    }
    # v9 패치 #8: password resolve
    from app.core.password_resolver import resolve_password
    c["password"] = resolve_password(
        c["password"], side=side,
        host=c["host"], username=c["username"], database=c["database"],
    )
    if not c["host"] or not c["database"]:
        return {"procedures":[],"functions":[],"triggers":[],"views":[]}
    try:
        if c["db_type"] in ("mysql","aurora","cloudsql","tidb","mariadb"):
            return _get_objects_mysql(c["host"],c["port"],c["username"],c["password"],c["database"])
        elif c["db_type"] in ("mssql","azure"):
            return _get_objects_mssql(c["host"],c["port"],c["username"],c["password"],c["database"])
        return {"procedures":[],"functions":[],"triggers":[],"views":[]}
    except Exception as e:
        import traceback
        print(f"[DEBUG objects] 오류: {e}", flush=True)
        print(traceback.format_exc(), flush=True)
        import traceback as _tb
        print(f"[objects 오류 무시] {e}", flush=True)
        print(_tb.format_exc(), flush=True)
        return {"procedures": [], "functions": [], "triggers": [], "views": []}


@router.post("/remigrate-job")
def create_remigrate_job(body: dict):
    """
    AI 재이관 전용 Job 생성
    - jobs store에 Job 등록 → JobMonitor에서 실시간 확인 가능
    - item_statuses에 오브젝트별 진행 상태 저장
    """
    import uuid as _uuid
    from datetime import datetime as _dt2
    from app.core.store import Store as _Str

    objects   = body.get("objects", [])   # [{name, type, error}]
    src_conn  = body.get("src_conn", {})
    tgt_conn  = body.get("tgt_conn", {})
    job_name  = body.get("name", f"AI 재이관 {_dt2.now().strftime('%m-%d %H:%M')}")

    if not objects:
        return {"ok": False, "error": "재이관 대상 없음"}

    jid = str(_uuid.uuid4())
    now = _dt2.utcnow().isoformat()

    # item_statuses 초기화
    item_statuses = {
        o["name"]: {
            "type":        "object",
            "obj_type":    o.get("type", "PROCEDURE"),
            "status":      "pending",
            "rows":        0,
            "error":       None,
            "started_at":  None,
            "finished_at": None,
            "error_hint":  o.get("error", ""),
        }
        for o in objects
    }

    job = {
        "id":           jid,
        "name":         job_name,
        "status":       "idle",
        "src_db":       src_conn.get("db_type", "mssql"),
        "tgt_db":       tgt_conn.get("db_type", "mysql"),
        "src_host":     src_conn.get("host", ""),
        "src_database": src_conn.get("database", ""),
        "src_username": src_conn.get("username", ""),
        "src_password": src_conn.get("password", ""),
        "src_port":     src_conn.get("port", 1433),
        "tgt_host":     tgt_conn.get("host", ""),
        "tgt_database": tgt_conn.get("database", ""),
        "tgt_username": tgt_conn.get("username", ""),
        "tgt_password": tgt_conn.get("password", ""),
        "tgt_port":     tgt_conn.get("port", 3306),
        "tables":       [],
        "objects":      {o["type"]: [o["name"]] for o in objects},
        "table_total":  0,
        "batch_size":   1,
        "truncate_target": False,
        "create_table": False,
        "on_error":     "skip",
        "convert_objects": True,
        "item_statuses": item_statuses,
        "rows_done":    0,
        "rows_total":   len(objects),
        "started_at":   now,
        "finished_at":  None,
        "created_at":   now,
        "job_type":     "remigrate",   # 일반 migration과 구분
        "progress":     0,
        "current_table": "",
        "elapsed_sec":  0,
        "error":        None,
    }

    try:
        from app.api.routes.jobs import _jobs
        _jobs.set(jid, job)
        logger.info("AI 재이관 Job 생성: %s (%d개 오브젝트)", jid, len(objects))
        return {"ok": True, "job_id": jid, "job": job}
    except Exception as e:
        logger.error("remigrate-job 생성 실패: %s", e)
        return {"ok": False, "error": str(e)}


@router.patch("/remigrate-job/{jid}/item")
def update_remigrate_item(jid: str, body: dict):
    """오브젝트별 진행 상태 업데이트 (프론트에서 단계마다 호출)"""
    from datetime import datetime as _dt3
    try:
        from app.api.routes.jobs import _jobs
        job = _jobs.get(jid)
        if not job:
            return {"ok": False, "error": "Job not found"}

        obj_name = body.get("name", "")
        status   = body.get("status", "running")  # pending/running/done/error
        error    = body.get("error")
        msg      = body.get("msg", "")

        if obj_name and obj_name in job.get("item_statuses", {}):
            item = job["item_statuses"][obj_name]
            item["status"] = status
            if status == "running":
                item["started_at"]  = _dt3.utcnow().isoformat()
                item["msg"]         = msg
            elif status in ("done", "error"):
                item["finished_at"] = _dt3.utcnow().isoformat()
                item["error"]       = error
                item["msg"]         = msg

        # Job 전체 상태 업데이트
        items     = job.get("item_statuses", {})
        done      = sum(1 for v in items.values() if v["status"] == "done")
        errors    = sum(1 for v in items.values() if v["status"] == "error")
        running   = sum(1 for v in items.values() if v["status"] == "running")
        total     = len(items)

        job["rows_done"] = done + errors
        job["progress"]  = round((done + errors) / max(total, 1) * 100)
        job["current_table"] = obj_name if status == "running" else ""

        if done + errors == total:
            job["status"]      = "completed" if errors == 0 else "error"
            job["finished_at"] = _dt3.utcnow().isoformat()
        elif running > 0:
            job["status"] = "running"

        _jobs.set(jid, job)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/convert-object-ai")
def convert_object_ai(body: dict):
    """Claude AI를 사용한 오브젝트 DDL 변환 — 공통 모듈(obj_executor) 사용"""
    from app.core.obj_executor import ai_convert_ddl
    result = ai_convert_ddl(
        ddl        = body.get("ddl", "").strip(),
        obj_type   = body.get("obj_type", "PROCEDURE").upper(),
        obj_name   = body.get("obj_name", ""),
        src_db     = body.get("src_db", "mssql"),
        tgt_db     = body.get("tgt_db", "mysql"),
        error_hint = body.get("error_hint", ""),
    )
    result["api_available"] = result["method"] == "claude-ai"
    return result


@router.post("/convert-object")
def convert_object(body: dict):
    """규칙 기반 오브젝트 DDL 변환 — 공통 모듈(obj_executor) 사용"""
    from app.core.obj_executor import mssql_to_mysql_ddl
    import re

    obj_type = body.get("type", body.get("obj_type", "PROCEDURE")).upper()
    obj_name = body.get("name", body.get("obj_name", ""))
    body_sql = body.get("body", body.get("ddl", ""))
    src_db   = body.get("src_db", "mysql")
    tgt_db   = body.get("tgt_db", "mssql")

    if src_db in ("mssql","azure","sqlserver") and tgt_db in ("mysql","aurora","mariadb","tidb"):
        converted, warnings = mssql_to_mysql_ddl(body_sql, obj_type)
        return {"converted": converted, "converted_ddl": converted,
                "changes": [f"MSSQL → MySQL 규칙 변환 완료 ({obj_type})"],
                "warnings": warnings, "obj_type": obj_type, "obj_name": obj_name}

    # MySQL → MSSQL (기존 로직 유지)
    converted = body_sql
    changes = []; warnings = []
    rules = [
        (r'`([^`]+)`',           r'[\1]',          '백틱→대괄호'),
        (r'\bVARCHAR\b',         'NVARCHAR',        'VARCHAR→NVARCHAR'),
        (r'\bDATETIME\b',        'DATETIME2(6)',     'DATETIME→DATETIME2'),
        (r'\bNOW\(\)',           'GETDATE()',        'NOW()→GETDATE()'),
        (r'\bIFNULL\s*\(',      'ISNULL(',         'IFNULL→ISNULL'),
        (r'\bLIMIT\s+(\d+)',    r'/* LIMIT \1 → TOP \1 */', 'LIMIT→TOP'),
        (r'\bCURRENT_TIMESTAMP\b','GETDATE()',      'CURRENT_TIMESTAMP→GETDATE()'),
    ]
    for pattern, replacement, desc in rules:
        new_s, cnt = re.subn(pattern, replacement, converted, flags=re.IGNORECASE)
        if cnt > 0:
            converted = new_s
            changes.append(f"{desc} ({cnt}건)")
    return {"converted": converted, "converted_ddl": converted,
            "changes": changes, "warnings": warnings,
            "obj_type": obj_type, "obj_name": obj_name}


@router.post("/execute-object")
def execute_object(body: dict):
    """
    오브젝트(프로시저/함수/뷰) 실제 실행 테스트
    """
    import time as _time
    db_type  = body.get("db_type","mysql")
    obj_type = body.get("obj_type","PROCEDURE")
    obj_name = body.get("obj_name","")
    params   = body.get("params",[])
    # v52: 프론트가 선택한 행의 schema_name 을 같이 받으면 우선 사용 (MSSQL 호출용)
    obj_schema = (body.get("obj_schema") or body.get("schema_name") or "").strip()
    c = body
    # v51: password resolve — 이 엔드포인트가 유일하게 resolve 누락되어 있었음.
    # 증상: 프론트 connector 스토어의 password 가 마스크("●●●●")/암호문 형태일 때
    # 그대로 pymysql 에 전달 → 인증 실패 → DB 조회 0건 → "타겟 없음" 오진단.
    # /schema/objects, /convert-object-ai 등 다른 엔드포인트는 이미 resolve 하고 있음.
    try:
        from app.core.password_resolver import resolve_password as _rpw
        # side 힌트: body 에 명시 없으면 target 으로 가정 (CHECK_EXISTS 는 항상 타겟 조회)
        _side_hint = body.get("side", "target")
        _orig_pw = c.get("password", "")
        c["password"] = _rpw(
            _orig_pw,
            profile_id=body.get("profile_id"),
            side=_side_hint,
            host=c.get("host"),
            username=c.get("username"),
            database=c.get("database"),
        )
        # 진단 로그 (평문 저장 금지 — 해결됐는지 boolean 만)
        import logging as _lg
        _lgr = _lg.getLogger("databridge.schema")
        _lgr.info(
            "[execute-object] obj_type=%s obj=%s db=%s side=%s pw_resolved=%s pw_was_mask=%s",
            obj_type, obj_name, c.get("database"), _side_hint,
            bool(c.get("password")),
            (_orig_pw or "").startswith("●") or "enc::" in (_orig_pw or ""),
        )
    except Exception as _pw_err:
        # resolve 실패해도 원본 password 로 진행 (기존 동작 유지)
        import logging as _lg
        _lg.getLogger("databridge.schema").warning("[execute-object] password resolve 실패: %s", _pw_err)

    start = _time.monotonic()

    # CHECK_EXISTS: 오브젝트 존재 여부 확인
    # v10 #34-B: MSSQL → MySQL 이관 시 AI 가 네이밍을 제각각 변환하는 문제 대응
    #   - [credit].[fn_age]  → fn_age              (스키마 제거, 가장 흔함)
    #   - [credit].[sp_x]    → credit_sp_x         (단일 언더스코어)
    #   - [credit].[sp_y]    → credit__sp_y        (더블 언더스코어)
    # 그래서 단일 이름으로 조회하면 못 찾는 케이스가 대부분.
    # → 여러 후보 이름을 순차 조회하여 하나라도 매칭되면 존재하는 것으로 판단.
    if obj_type == "CHECK_EXISTS":
        obj_name_check = body.get("obj_name","")

        # 소스 이름에서 스키마/오브젝트명 분리
        _raw = (obj_name_check or "").strip()
        # MSSQL/ANSI 식별자 인용부호 제거
        _raw = _raw.replace("[","").replace("]","").replace("`","").replace('"',"")
        if "." in _raw:
            _src_schema, _bare = _raw.split(".", 1)
            _src_schema = _src_schema.strip()
            _bare = _bare.strip()
        else:
            _src_schema = ""
            _bare = _raw

        # v57: obj_name 에 점이 없을 때 body 의 obj_schema 를 소스 스키마로 사용.
        # 이전엔 프론트가 bare name 만 보내고 obj_schema 는 무시되어,
        # `{schema}_{name}` (settlement_sp_reverse_trx) 같은 변형 후보가 만들어지지 않았음.
        if not _src_schema and obj_schema:
            _src_schema = obj_schema

        # 후보 이름 목록 (중복 제거, 순서 유지)
        _candidates = []
        def _add(n):
            if n and n not in _candidates:
                _candidates.append(n)
        _add(_bare)                                               # fn_age
        _add(_raw)                                                # 원본 (schema.name 통째로)
        if _src_schema:
            _add(f"{_src_schema}_{_bare}")                        # credit_fn_age
            _add(f"{_src_schema}__{_bare}")                       # credit__fn_age

        try:
            if db_type in ("mysql","aurora","cloudsql","tidb","mariadb"):
                import pymysql
                conn = pymysql.connect(host=c["host"],port=int(c["port"]),
                    user=c["username"],password=c.get("password",""),
                    database=c["database"],charset="utf8mb4",connect_timeout=8,
                    cursorclass=pymysql.cursors.DictCursor)
                try:
                    cur = conn.cursor()
                    # v50: 진단용 — 현재 DB에 존재하는 모든 routine/view/trigger 이름 수집.
                    # "타겟 없음" 오진단 시 실제 MySQL 어떤 이름이 있는지 바로 파악 가능.
                    import logging as _lg
                    _lgr = _lg.getLogger("databridge.schema")
                    cur.execute("""
                        SELECT ROUTINE_NAME AS name, ROUTINE_TYPE AS kind FROM information_schema.ROUTINES
                          WHERE ROUTINE_SCHEMA=%s
                        UNION ALL
                        SELECT TABLE_NAME AS name, 'VIEW' AS kind FROM information_schema.VIEWS
                          WHERE TABLE_SCHEMA=%s
                        UNION ALL
                        SELECT TRIGGER_NAME AS name, 'TRIGGER' AS kind FROM information_schema.TRIGGERS
                          WHERE TRIGGER_SCHEMA=%s
                    """, (c["database"],) * 3)
                    _all_tgt = cur.fetchall() or []
                    _all_names = [r["name"] for r in _all_tgt]
                    _lgr.info(
                        "[CHECK_EXISTS] db=%s obj=%s bare=%s candidates=%s total_in_db=%d",
                        c["database"], _raw, _bare, _candidates, len(_all_names)
                    )

                    # 각 후보를 순차 조회 — 첫 매칭에서 종료 (기존 로직)
                    for _cand in _candidates:
                        cur.execute("""SELECT ROUTINE_NAME AS name, ROUTINE_TYPE AS kind FROM information_schema.ROUTINES
                            WHERE ROUTINE_SCHEMA=%s AND ROUTINE_NAME=%s
                            UNION SELECT TABLE_NAME AS name, 'VIEW' AS kind FROM information_schema.VIEWS
                            WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
                            UNION SELECT TRIGGER_NAME AS name, 'TRIGGER' AS kind FROM information_schema.TRIGGERS
                            WHERE TRIGGER_SCHEMA=%s AND TRIGGER_NAME=%s""",
                            (c["database"], _cand)*3)
                        rows = cur.fetchall()
                        if rows:
                            _lgr.info("[CHECK_EXISTS] ✓ matched on candidate '%s' (exact)", _cand)
                            return {
                                "success": True,
                                "rows": rows,
                                "exists": True,
                                "matched_name": _cand,
                                "name_variant": (None if _cand == _bare else _cand),
                                "candidates_tried": _candidates,
                                "diagnostics": {
                                    "db": c["database"], "total_in_db": len(_all_names),
                                    "match_type": "exact",
                                }
                            }

                    # v50: 후보 exact 매칭 실패 → case-insensitive 폴백.
                    # MySQL 은 DB/객체명이 소문자로 저장될 수 있음 (lower_case_table_names 설정).
                    # 소스(MSSQL)는 대소문자 그대로 오는데 타겟 MySQL 에 소문자로 내려갔으면 매칭 실패한다.
                    for _cand in _candidates:
                        cur.execute("""SELECT ROUTINE_NAME AS name, ROUTINE_TYPE AS kind FROM information_schema.ROUTINES
                            WHERE ROUTINE_SCHEMA=%s AND LOWER(ROUTINE_NAME)=LOWER(%s)
                            UNION SELECT TABLE_NAME AS name, 'VIEW' AS kind FROM information_schema.VIEWS
                            WHERE TABLE_SCHEMA=%s AND LOWER(TABLE_NAME)=LOWER(%s)
                            UNION SELECT TRIGGER_NAME AS name, 'TRIGGER' AS kind FROM information_schema.TRIGGERS
                            WHERE TRIGGER_SCHEMA=%s AND LOWER(TRIGGER_NAME)=LOWER(%s)""",
                            (c["database"], _cand)*3)
                        rows = cur.fetchall()
                        if rows:
                            actual_name = rows[0]["name"]
                            _lgr.info(
                                "[CHECK_EXISTS] ✓ matched on candidate '%s' (case-insensitive → actual='%s')",
                                _cand, actual_name
                            )
                            return {
                                "success": True,
                                "rows": rows,
                                "exists": True,
                                "matched_name": actual_name,
                                "name_variant": actual_name,  # 케이스 다르면 variant 로 표시
                                "candidates_tried": _candidates,
                                "diagnostics": {
                                    "db": c["database"], "total_in_db": len(_all_names),
                                    "match_type": "case_insensitive",
                                    "requested": _cand, "actual": actual_name,
                                }
                            }

                    # v50: 둘 다 실패 → "유사한 이름" 힌트 수집 (진단 강화).
                    # 소스 bare name 이 일부 포함된 타겟 이름 최대 5개 제시.
                    _bare_lower = (_bare or "").lower()
                    _similar = []
                    if _bare_lower:
                        for _n in _all_names:
                            if _bare_lower in (_n or "").lower():
                                _similar.append(_n)
                                if len(_similar) >= 5: break
                    _lgr.warning(
                        "[CHECK_EXISTS] ✗ NOT FOUND — db=%s bare=%s similar=%s (total_in_db=%d)",
                        c["database"], _bare, _similar, len(_all_names)
                    )
                    # 어느 후보도 매칭 안됨
                    return {
                        "success": True,
                        "rows": [],
                        "exists": False,
                        "candidates_tried": _candidates,
                        "diagnostics": {
                            "db": c["database"], "total_in_db": len(_all_names),
                            "match_type": "none",
                            "similar_names": _similar,
                            # 진단용 — 총 이름의 상위 일부만 (응답 크기 제한)
                            "sample_names": _all_names[:20],
                        }
                    }
                finally: conn.close()
            elif db_type in ("mssql","azure"):
                from app.core.db_conn import make_mssql_conn as _ms_c
                conn = _ms_c(c['host'], c['port'], c['username'], c.get('password',''), c['database'])
                try:
                    cur=conn.cursor()
                    # MSSQL 타겟: 동일하게 여러 후보 시도
                    for _cand in _candidates:
                        cur.execute(
                            "SELECT name FROM sys.objects WHERE name=? "
                            "AND type IN ('P','FN','IF','TF','TR','V')",
                            (_cand,)
                        )
                        rows = [{"name": r[0]} for r in cur.fetchall()]
                        if rows:
                            return {
                                "success": True, "rows": rows, "exists": True,
                                "matched_name": _cand,
                                "name_variant": (None if _cand == _bare else _cand),
                                "candidates_tried": _candidates,
                            }
                    return {
                        "success": True, "rows": [], "exists": False,
                        "candidates_tried": _candidates,
                    }
                finally: conn.close()
        except Exception as e:
            return {"success":False,"rows":[],"exists":False,"error":str(e),
                    "candidates_tried": _candidates}

    # DDL_CREATE: 프론트엔드 AI가 변환한 MSSQL SQL을 실행
    # (AI 변환은 브라우저에서 Anthropic API 호출로 수행 — API 키 자동 주입)
    if obj_type == "DDL_CREATE":
        obj_name_c  = body.get("obj_name", "")
        obj_type_c  = body.get("obj_sub_type", "PROCEDURE").upper()

        # 프론트엔드가 AI 변환한 statements 배열을 전달
        # statements: 실행할 MSSQL SQL 문장 배열
        # ddl: 원본 MySQL DDL (fallback용)
        statements  = body.get("statements", [])
        original_ddl = body.get("ddl", "")
        notes       = body.get("notes", "")

        if not statements:
            logger.error("DDL_CREATE [%s]: statements 없음", obj_name_c)
            return {"success": False, "error": "변환된 SQL statements가 없습니다. 프론트엔드 AI 변환을 확인하세요.", "rows": []}

        logger.info("DDL_CREATE [%s] %s: %d개 문장 실행", obj_name_c, obj_type_c, len(statements))
        for i, st in enumerate(statements):
            logger.debug("  [%d] %s", i+1, st[:150])

        try:
            if db_type in ("mssql", "azure"):
                from app.core.db_conn import make_mssql_conn as _ms_c
                conn = _ms_c(c['host'], c['port'], c['username'], c.get('password',''), c['database'])
                executed = []; errors = []
                try:
                    cur = conn.cursor()
                    for i, stmt in enumerate(statements):
                        stmt = stmt.strip()
                        if not stmt or stmt.upper() in ("GO",""):
                            continue
                        try:
                            cur.execute(stmt)
                            conn.commit()
                            executed.append(stmt[:80])
                            logger.info("  ✓ [%d] %s...", i+1, stmt[:60])
                        except Exception as e:
                            logger.error("  ✗ [%d] %s | 오류: %s", i+1, stmt[:80], e)
                            errors.append({"stmt": stmt[:120], "error": str(e)})
                            try: conn.rollback()
                            except: pass

                    if executed and not errors:
                        logger.info("DDL_CREATE [%s] 완전 성공 (%d문장)", obj_name_c, len(executed))
                        return {"success": True, "rows": [],
                                "output": f"{obj_name_c} 생성 완료 ({len(executed)}문장)",
                                "notes": notes, "executed": executed}
                    elif executed:
                        logger.warning("DDL_CREATE [%s] 부분 성공 (%d/%d)", obj_name_c, len(executed), len(executed)+len(errors))
                        return {"success": True, "rows": [],
                                "output": f"{obj_name_c} 부분 성공 ({len(executed)}/{len(executed)+len(errors)})",
                                "notes": notes, "warnings": [e["error"] for e in errors]}
                    else:
                        err = "; ".join(e["error"] for e in errors[:3])
                        logger.error("DDL_CREATE [%s] 전체 실패: %s", obj_name_c, err)
                        return {"success": False, "error": err, "rows": [], "notes": notes, "errors": errors}
                finally:
                    conn.close()

            elif db_type in ("mysql","aurora","cloudsql","tidb","mariadb"):
                from app.core.obj_executor import deploy_mysql_object
                obj_sub = body.get("obj_sub_type","").upper()
                stmts   = statements if statements else [original_ddl]
                full_ddl = "\n".join(stmts)
                result   = deploy_mysql_object(full_ddl, c, obj_sub, obj_name_c)
                if result["success"]:
                    logger.info("DDL_CREATE MySQL [%s] 완료", obj_name_c)
                    return {"success": True, "rows": [], "output": result["output"]}
                else:
                    logger.error("DDL_CREATE MySQL [%s] 실패: %s", obj_name_c, result["error"])
                    return {"success": False, "error": result["error"], "rows": []}

            return {"success": False, "error": f"{db_type} DDL_CREATE 미지원", "rows": []}
        except Exception as e:
            logger.error("DDL_CREATE 연결 오류 [%s]: %s", obj_name_c, e)
            return {"success": False, "error": str(e), "rows": []}






    try:
        if db_type in ("mysql","aurora","cloudsql","tidb","mariadb"):
            import pymysql
            conn = pymysql.connect(
                host=c["host"], port=int(c["port"]),
                user=c["username"], password=c.get("password",""),
                database=c["database"], charset="utf8mb4",
                connect_timeout=10, cursorclass=pymysql.cursors.DictCursor
            )
            try:
                cur = conn.cursor()
                if obj_type == "PROCEDURE":
                    # MySQL callproc: IN+OUT 전체 파라미터 수 맞춰야 함
                    # information_schema에서 전체 파라미터 조회
                    try:
                        cur.execute("""
                            SELECT PARAMETER_MODE, ORDINAL_POSITION
                            FROM information_schema.PARAMETERS
                            WHERE SPECIFIC_SCHEMA = %s AND SPECIFIC_NAME = %s
                              AND ORDINAL_POSITION > 0
                            ORDER BY ORDINAL_POSITION
                        """, (c["database"], obj_name))
                        all_params = cur.fetchall()
                        # IN 파라미터 자리에 값, OUT 자리에 None
                        full_params = []
                        in_idx = 0
                        for row in all_params:
                            mode = (row.get("PARAMETER_MODE") or "IN").upper()
                            if mode in ("IN", "INOUT"):
                                full_params.append(params[in_idx] if in_idx < len(params) else None)
                                in_idx += 1
                            else:  # OUT
                                full_params.append(None)
                    except Exception:
                        full_params = list(params) if params else []

                    # ════════════════════════════════════════════════════════════
                    # v90.77 (2026-04-28): pymysql callproc 우회 — 직접 CALL 실행
                    #   본부장님 진단 결과:
                    #     - MySQL CLI 직접 호출: 통과
                    #     - SP/DB/charset 모두 정상 (utf8mb4_unicode_ci)
                    #     - DataBridge (pymysql callproc) 만 1406 발생
                    #   원인: pymysql.callproc 의 user variable 패턴 (SET @_xxx_0 = ...) 이
                    #         charset/collation/length 어딘가에서 호환 안 됨.
                    #   처방: callproc 대신 표준 placeholder 로 직접 CALL — MySQL CLI 와 동일
                    #         OUT 파라미터는 별도 SELECT 으로 회수 (필요 시)
                    # ════════════════════════════════════════════════════════════
                    has_out = False
                    try:
                        for row in all_params:
                            if (row.get("PARAMETER_MODE") or "IN").upper() in ("OUT", "INOUT"):
                                has_out = True
                                break
                    except Exception:
                        has_out = False
                    
                    if has_out:
                        # OUT/INOUT 있으면 callproc 사용 (회수 위해)
                        cur.callproc(obj_name, full_params)
                    else:
                        # IN 만 → 직접 CALL (MySQL CLI 와 동일, 1406 회피)
                        placeholders = ", ".join(["%s"] * len(full_params))
                        sql = f"CALL `{obj_name}`({placeholders})" if placeholders else f"CALL `{obj_name}`()"
                        cur.execute(sql, full_params)
                    rows = []
                    try:
                        for result in cur.stored_results():
                            fetched = result.fetchall()
                            if fetched:
                                rows = fetched
                    except Exception:
                        try: rows = cur.fetchall() or []
                        except Exception: rows = []

                elif obj_type == "FUNCTION":
                    # TVF (이름이 TVF로 시작) → callproc으로 처리
                    if obj_name.upper().startswith("TVF"):
                        # TVF → 프로시저 변환됨, IN 파라미터만 전달 (OUT 없음)
                        # params 는 이미 is_output 필터링된 IN 값들
                        full_tvf = list(params) if params else []
                        # v90.77: callproc 대신 직접 CALL (1406 회피)
                        ph = ", ".join(["%s"] * len(full_tvf)) if full_tvf else ""
                        sql = f"CALL `{obj_name}`({ph})" if ph else f"CALL `{obj_name}`()"
                        cur.execute(sql, full_tvf)
                        rows = []
                        try:
                            for result in cur.stored_results():
                                fetched = result.fetchall()
                                if fetched:
                                    rows = fetched
                        except Exception:
                            # stored_results 미지원 환경 fallback
                            try: rows = cur.fetchall() or []
                            except Exception: rows = []
                    else:
                        ph = ",".join(["%s"]*len(params)) if params else ""
                        cur.execute(f"SELECT {obj_name}({ph}) AS result", params or [])
                        rows = cur.fetchall()
                elif obj_type == "VIEW":
                    cur.execute(f"SELECT * FROM `{obj_name}` LIMIT 50")
                    rows = cur.fetchall()
                else:
                    rows = []
                elapsed = round((_time.monotonic()-start)*1000, 1)
                return {"success":True,"rows":rows,"elapsed":elapsed,"output":"실행 완료"}
            finally:
                conn.close()

        elif db_type in ("mssql","azure"):
            from app.core.db_conn import make_mssql_conn as _ms_c
            import threading as _th, queue as _q

            def _run_mssql(result_q):
                """별도 스레드에서 MSSQL 실행 — 강제 종료 가능하도록 분리"""
                _conn = None
                try:
                    _conn = _ms_c(c['host'], c['port'], c['username'],
                                  c.get('password',''), c['database'], timeout=8)
                    _cur = _conn.cursor()
                    # 잠금 대기 3초, 쿼리 비용 제한 (긴 배치 SP 자동 중단)
                    for _sql in ("SET LOCK_TIMEOUT 3000",
                                 "SET QUERY_GOVERNOR_COST_LIMIT 10000"):
                        try: _cur.execute(_sql)
                        except: pass

                    # v52: 스키마 동적 해결 — 프론트가 obj_schema 를 보냈으면 우선 사용,
                    # 없으면 sys.objects + sys.schemas 로 찾음. 실패 시 dbo 로 fallback.
                    def _resolve_schema(name):
                        # 프론트가 명시적으로 보낸 값 우선
                        if obj_schema:
                            return obj_schema
                        try:
                            _cur.execute("""
                                SELECT TOP 1 s.name
                                FROM sys.objects o
                                JOIN sys.schemas s ON o.schema_id = s.schema_id
                                WHERE o.name = ?
                                  AND o.type IN ('P','FN','IF','TF','V','TR')
                                ORDER BY CASE WHEN s.name='dbo' THEN 0 ELSE 1 END, s.name
                            """, (name,))
                            _r = _cur.fetchone()
                            return _r[0] if _r else "dbo"
                        except Exception:
                            return "dbo"

                    _sch = _resolve_schema(obj_name)
                    _schema_ref = f"[{_sch}]"   # [credit] 같은 형태로 안전하게

                    if obj_type == "PROCEDURE":
                        ph = ",".join(["?"]*len(params)) if params else ""
                        # v52: EXEC 도 스키마 붙여서 호출 (default_schema_name 의존 제거)
                        _cur.execute(f"EXEC {_schema_ref}.[{obj_name}] {ph}", params or [])
                        try:
                            cols = [d[0] for d in _cur.description]
                            rows = [dict(zip(cols, r)) for r in _cur.fetchmany(50)]
                        except Exception:
                            rows = []

                    elif obj_type == "FUNCTION":
                        # MSSQL 함수: ? 바인딩 불가 → 값을 직접 SQL에 포맷
                        def _fmt_val(v):
                            if v is None: return "NULL"
                            try:
                                float(v); return str(v)
                            except (TypeError, ValueError):
                                return "N'" + str(v).replace("'", "''") + "'"

                        # TVF 여부 확인 (TF/IF 타입은 SELECT * FROM schema.fn() 방식)
                        _cur.execute("""
                            SELECT o.type FROM sys.objects o
                            WHERE o.name = ? AND o.type IN ('FN','IF','TF')
                        """, (obj_name,))
                        _fn_type_row = _cur.fetchone()
                        _fn_type = (_fn_type_row[0] if _fn_type_row else b'FN')
                        if hasattr(_fn_type, 'strip'): _fn_type = _fn_type.strip()
                        _is_tvf = _fn_type in (b'TF', b'IF', 'TF', 'IF')

                        if params:
                            ph = ",".join(_fmt_val(p) for p in params)
                            if _is_tvf:
                                # v52: TVF — 동적 스키마
                                _cur.execute(f"SELECT TOP 50 * FROM {_schema_ref}.[{obj_name}]({ph})")
                            else:
                                # v52: 스칼라 — 동적 스키마
                                _cur.execute(f"SELECT {_schema_ref}.[{obj_name}]({ph}) AS result")
                            try:
                                cols = [d[0] for d in _cur.description]
                                rows = [dict(zip(cols, r)) for r in _cur.fetchall()]
                            except Exception:
                                rows = []
                        else:
                            # params 없음 → sys.parameters 확인
                            _cur.execute("""
                                SELECT COUNT(p.parameter_id) AS param_count
                                FROM sys.objects o
                                LEFT JOIN sys.parameters p
                                    ON o.object_id = p.object_id
                                    AND p.parameter_id > 0
                                WHERE o.name = ?
                                  AND o.type IN ('FN','IF','TF')
                                GROUP BY o.name
                            """, (obj_name,))
                            fn_row = _cur.fetchone()
                            if fn_row and fn_row[0] > 0:
                                result_q.put({
                                    "success": False,
                                    "error": f"함수에 {fn_row[0]}개 파라미터가 필요합니다 (존재 확인됨)",
                                    "rows": []
                                })
                                return
                            elif fn_row:
                                if _is_tvf:
                                    # v52: 동적 스키마
                                    _cur.execute(f"SELECT TOP 50 * FROM {_schema_ref}.[{obj_name}]()")
                                else:
                                    # v52: 동적 스키마
                                    _cur.execute(f"SELECT {_schema_ref}.[{obj_name}]() AS result")
                                cols = [d[0] for d in _cur.description]
                                rows = [dict(zip(cols, r)) for r in _cur.fetchall()]
                            else:
                                result_q.put({"success": False, "error": "함수를 찾을 수 없습니다", "rows": []})
                                return

                    elif obj_type == "VIEW":
                        # NOLOCK 힌트로 잠금 방지, TOP 10으로 최소화
                        # v52: 뷰도 동적 스키마 (스키마 없이 호출하면 default_schema_name 의존)
                        try:
                            _cur.execute(f"SELECT TOP 10 * FROM {_schema_ref}.[{obj_name}] WITH (NOLOCK)")
                        except Exception:
                            _cur.execute(f"SELECT TOP 10 * FROM {_schema_ref}.[{obj_name}]")
                        cols = [d[0] for d in _cur.description]
                        rows = [dict(zip(cols, r)) for r in _cur.fetchall()]
                    else:
                        rows = []

                    result_q.put({"success": True, "rows": rows})
                except Exception as e:
                    result_q.put({"success": False, "error": str(e), "rows": []})
                finally:
                    # 연결 반드시 닫기 — 풀 고갈 방지
                    if _conn:
                        try: _conn.close()
                        except: pass

            rq = _q.Queue()
            t  = _th.Thread(target=_run_mssql, args=(rq,), daemon=True)
            t.start()
            # v62: 6초 하드코딩 → 30초 상향 + body 의 _exec_timeout_sec 로 조정 가능.
            #   배경: MSSQL 쪽 대용량 VIEW/PROC 가 6초 넘게 걸리는 정상 케이스에서
            #   프론트에 "timeout of 6000ms exceeded" 로 반환되어 사용자가 실패로 오인.
            #   특히 Docker MSSQL 재시작 직후 recovery/warm-up 중엔 매번 6초 타임아웃.
            _exec_to = int(body.get("_exec_timeout_sec") or 30)
            t.join(timeout=_exec_to)

            if t.is_alive():
                # 스레드가 살아있으면 타임아웃 — 연결은 스레드가 종료될 때 닫힘
                elapsed = round((_time.monotonic()-start)*1000, 1)
                return {"success": False,
                        "error": f"timeout of {_exec_to*1000}ms exceeded",
                        "rows": [], "elapsed": elapsed}

            result = rq.get_nowait() if not rq.empty() else {"success": False, "error": "no result", "rows": []}
            elapsed = round((_time.monotonic()-start)*1000, 1)
            result["elapsed"] = elapsed
            return result

        return {"success":False,"error":f"{db_type} 실행 미지원","rows":[]}
    except Exception as e:
        return {"success":False,"error":str(e),"rows":[],
                "elapsed":round((_time.monotonic()-start)*1000,1)}


# ── 파라미터 조회 ──────────────────────────────────────────────────────────
@router.post("/object-params")
def get_object_params(body: dict):
    """
    오브젝트 파라미터 목록 조회
    반환: {params: [{name, data_type, max_length, is_output, ordinal}], hint_key}
    """
    db_type  = body.get("db_type", "mysql")
    host     = body.get("host", "")
    port     = body.get("port", 3306)
    username = body.get("username", "")
    password = body.get("password", "")
    database = body.get("database", "")
    obj_name = body.get("obj_name", "")
    obj_type = body.get("obj_type", "PROCEDURE").upper()

    # v9 패치 #7: 마스크/암호문 해결
    from app.core.password_resolver import resolve_password as _rpw
    password = _rpw(password, profile_id=body.get("profile_id"),
                    side=body.get("side","source"),
                    host=host, username=username, database=database)

    # hint_key: 저장된 더미값 참조용
    hint_key = f"{host}:{database}:{obj_name}"

    try:
        if db_type in ("mssql", "azure"):
            from app.core.db_conn import make_mssql_conn as _ms
            conn = _ms(host, port, username, password, database, timeout=8)
            try:
                cur = conn.cursor()
                # sys.parameters + sys.types 조인으로 파라미터 타입까지 조회
                cur.execute("""
                    SELECT
                        p.name            AS param_name,
                        t.name            AS data_type,
                        p.max_length      AS max_length,
                        p.is_output       AS is_output,
                        p.parameter_id    AS ordinal
                    FROM sys.objects o
                    JOIN sys.parameters p ON o.object_id = p.object_id
                    JOIN sys.types t      ON p.user_type_id = t.user_type_id
                    WHERE o.name = ?
                      AND p.parameter_id > 0
                    ORDER BY p.parameter_id
                """, (obj_name,))
                rows = [{"name": r[0], "data_type": r[1],
                         "max_length": r[2], "is_output": bool(r[3]),
                         "ordinal": r[4]} for r in cur.fetchall()]
            finally:
                try: conn.close()
                except: pass

        elif db_type in ("mysql", "aurora", "mariadb", "cloudsql", "tidb"):
            import pymysql
            conn = pymysql.connect(
                host=host, port=int(port), user=username,
                password=password, database=database,
                charset="utf8mb4", connect_timeout=8,
                cursorclass=pymysql.cursors.DictCursor
            )
            try:
                cur = conn.cursor()
                cur.execute("""
                    SELECT
                        PARAMETER_NAME   AS param_name,
                        DATA_TYPE        AS data_type,
                        CHARACTER_MAXIMUM_LENGTH AS max_length,
                        PARAMETER_MODE   AS param_mode,
                        ORDINAL_POSITION AS ordinal
                    FROM information_schema.PARAMETERS
                    WHERE SPECIFIC_SCHEMA = %s
                      AND SPECIFIC_NAME   = %s
                      AND ORDINAL_POSITION > 0
                    ORDER BY ORDINAL_POSITION
                """, (database, obj_name))
                rows = [{"name": r["param_name"], "data_type": r["data_type"],
                         "max_length": r["max_length"],
                         "is_output": (r["param_mode"] or "").upper() in ("OUT","INOUT"),
                         "ordinal": r["ordinal"]} for r in cur.fetchall()]
            finally:
                try: conn.close()
                except: pass
        else:
            rows = []

        return {"params": rows, "hint_key": hint_key, "count": len(rows)}

    except Exception as e:
        return {"params": [], "hint_key": hint_key, "count": 0, "error": str(e)}


# ── 테스트 힌트(더미값) 저장/조회 ──────────────────────────────────────────
@router.get("/obj-test-hints")
def get_obj_hints():
    """저장된 모든 테스트 힌트 반환"""
    from app.core.store import Store
    s = Store("obj_test_hints")
    return {"hints": s.all()}


@router.post("/obj-test-hints")
def save_obj_hint(body: dict):
    """
    오브젝트 테스트 힌트 저장
    key: "{host}:{database}:{obj_name}"
    value: {params: [{name, data_type, dummy_value}], note, saved_at}
    """
    from app.core.store import Store
    from datetime import datetime
    key    = body.get("key", "")
    params = body.get("params", [])
    note   = body.get("note", "")
    if not key:
        return {"ok": False, "error": "key 필요"}
    s = Store("obj_test_hints")
    s.set(key, {
        "params":   params,
        "note":     note,
        "saved_at": datetime.now().isoformat(timespec="seconds")
    })
    return {"ok": True, "key": key}


@router.delete("/obj-test-hints/{hint_key:path}")
def delete_obj_hint(hint_key: str):
    """힌트 삭제"""
    from app.core.store import Store
    s = Store("obj_test_hints")
    s.delete(hint_key)
    return {"ok": True, "key": hint_key}


# ── DB 실제 데이터에서 파라미터 추천값 조회 ────────────────────────────────
@router.post("/object-param-suggestions")
def get_param_suggestions(body: dict):
    """
    SP/FN 파라미터 이름과 관련된 실제 DB 데이터를 찾아 추천값 반환
    전략:
    1. 파라미터명에서 테이블/컬럼 힌트 추출 (@cust_no → customers.cust_no)
    2. information_schema에서 컬럼 매칭
    3. 매칭된 컬럼에서 샘플 데이터 1건 조회
    4. 없으면 타입별 의미있는 기본값 반환
    """
    import re as _re, time as _t

    db_type  = body.get("db_type", "mysql")
    host     = body.get("host", "")
    port     = body.get("port", 3306)
    username = body.get("username", "")
    password = body.get("password", "")
    database = body.get("database", "")
    params   = body.get("params", [])   # [{name, data_type, is_output}, ...]

    # v9 패치 #7
    from app.core.password_resolver import resolve_password as _rpw
    password = _rpw(password, profile_id=body.get("profile_id"),
                    side=body.get("side","source"),
                    host=host, username=username, database=database)

    def _smart_dummy(name: str, dtype: str, max_length: int = 0) -> str:
        """파라미터명 패턴으로 의미있는 기본값 생성 (v90.80: max_length 반영)"""
        n = name.lstrip("@_").lower()
        t = (dtype or "").lower()
        ml = int(max_length) if max_length and max_length > 0 else 0
        # 날짜/시간 — v90.80: VARCHAR(8)=YYYYMMDD, VARCHAR(10)=YYYY-MM-DD
        if any(x in n for x in ["dt","date","day","ymd","yyyymmdd"]):
            if ml > 0 and ml < 10:
                if ml >= 8: return "20240101"
                if ml >= 6: return "202401"
                if ml >= 4: return "2024"
                return "20240101"[:ml]
            return "2024-01-01"
        if any(x in n for x in ["time","tm","hms"]):                    return "09:00:00"
        # 코드/구분
        if any(x in n for x in ["tp","type","cd","code","gb","flag","yn","status","stat"]):
            return "1" if t in ("int","tinyint","smallint","bit") else "A"
        # 이름/문자
        if any(x in n for x in ["nm","name","title","desc","memo","remark","note"]):
            return "테스트"
        # 이메일
        if "email" in n or "mail" in n:                                 return "test@test.com"
        # 전화번호
        if any(x in n for x in ["phone","tel","mobile","hp"]):          return "010-0000-0000"
        # ID/번호 (숫자)
        if any(x in n for x in ["id","no","seq","num","cnt","idx","key"]):
            return "0"
        # 금액/비율
        if any(x in n for x in ["amt","amount","price","rate","ratio","pct","per"]):
            return "0.0" if "float" in t or "decimal" in t or "numeric" in t else "0"
        # 주소
        if any(x in n for x in ["addr","address","zip","post"]):        return "서울시"
        # 출력 파라미터 처리
        if body.get("is_output"):                                        return ""
        # 타입 기본값
        if _re.search(r"int|bigint|smallint|tinyint", t):               return "1"
        if _re.search(r"float|double|decimal|numeric|real|money", t):   return "0.0"
        if _re.search(r"bit|bool", t):                                   return "1"
        if _re.search(r"date", t):
            if ml > 0 and ml < 10: return "20240101"[:max(ml,4)] if ml >= 4 else "20240101"[:ml]
            return "2024-01-01"
        if _re.search(r"time", t):                                       return "09:00:00"
        if _re.search(r"char|text|varchar|nvar|nchar", t):
            if ml > 0 and ml < 5: return "A" * ml
            return "A"
        if "uniqueidentifier" in t or "uuid" in t:                      return "00000000-0000-0000-0000-000000000000"
        return "0"

    def _find_column_sample(cur, db_schema, param_name, dtype, is_mssql=False):
        """파라미터명으로 테이블 컬럼 찾아 실제 샘플값 반환"""
        col_hint = param_name.lstrip("@_").lower()
        try:
            if is_mssql:
                cur.execute("""
                    SELECT TOP 1 c.TABLE_NAME, c.COLUMN_NAME
                    FROM information_schema.COLUMNS c
                    WHERE c.TABLE_CATALOG = ?
                      AND LOWER(c.COLUMN_NAME) = ?
                      AND c.TABLE_NAME NOT LIKE '%#%'
                    ORDER BY c.TABLE_NAME
                """, (db_schema, col_hint))
            else:
                cur.execute("""
                    SELECT TABLE_NAME, COLUMN_NAME
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = %s
                      AND LOWER(COLUMN_NAME) = %s
                    LIMIT 1
                """, (db_schema, col_hint))
            row = cur.fetchone()
            if not row:
                return None
            table_name, col_name = row[0], row[1]
            # 실제 데이터 1건 샘플
            if is_mssql:
                cur.execute(f"SELECT TOP 1 [{col_name}] FROM [{table_name}] WHERE [{col_name}] IS NOT NULL")
            else:
                cur.execute(f"SELECT `{col_name}` FROM `{table_name}` WHERE `{col_name}` IS NOT NULL LIMIT 1")
            sample = cur.fetchone()
            if sample and sample[0] is not None:
                return {"value": str(sample[0]), "source": f"{table_name}.{col_name}"}
        except Exception:
            pass
        return None

    results = []
    try:
        if db_type in ("mssql", "azure"):
            from app.core.db_conn import make_mssql_conn as _ms
            conn = _ms(host, port, username, password, database, timeout=10)
            try:
                cur = conn.cursor()
                cur.execute("SET LOCK_TIMEOUT 3000")
                for p in params:
                    if p.get("is_output"):
                        results.append({**p, "dummy_value": "", "suggestion_source": "출력 파라미터"})
                        continue
                    sample = _find_column_sample(cur, database, p["name"], p["data_type"], is_mssql=True)
                    if sample:
                        results.append({**p, "dummy_value": sample["value"],
                                        "suggestion_source": sample["source"]})
                    else:
                        results.append({**p, "dummy_value": _smart_dummy(p["name"], p["data_type"], p.get("max_length", 0)),
                                        "suggestion_source": "패턴 추천"})
            finally:
                try: conn.close()
                except: pass

        elif db_type in ("mysql", "aurora", "mariadb", "cloudsql", "tidb"):
            import pymysql
            conn = pymysql.connect(
                host=host, port=int(port), user=username,
                password=password, database=database,
                charset="utf8mb4", connect_timeout=8,
                cursorclass=pymysql.cursors.DictCursor
            )
            try:
                cur = conn.cursor()
                for p in params:
                    if p.get("is_output"):
                        results.append({**p, "dummy_value": "", "suggestion_source": "출력 파라미터"})
                        continue
                    # MySQL은 dict cursor라 일반 cursor로
                    cur2 = conn.cursor()
                    sample = _find_column_sample(cur2, database, p["name"], p["data_type"], is_mssql=False)
                    if sample:
                        results.append({**p, "dummy_value": sample["value"],
                                        "suggestion_source": sample["source"]})
                    else:
                        results.append({**p, "dummy_value": _smart_dummy(p["name"], p["data_type"], p.get("max_length", 0)),
                                        "suggestion_source": "패턴 추천"})
            finally:
                try: conn.close()
                except: pass
        else:
            # 지원 안 되는 DB는 스마트 더미값만
            for p in params:
                results.append({**p, "dummy_value": _smart_dummy(p["name"], p["data_type"], p.get("max_length", 0)),
                                "suggestion_source": "패턴 추천"})

        return {"params": results, "ok": True}

    except Exception as e:
        logger.error("param suggestions 오류: %s", e)
        # 연결 실패해도 스마트 더미값은 반환
        for p in params:
            results.append({**p, "dummy_value": _smart_dummy(p["name"], p["data_type"], p.get("max_length", 0)),
                            "suggestion_source": "패턴 추천 (DB 연결 실패)"})
        return {"params": results, "ok": False, "error": str(e)}


@router.get("/objects/ddl")
def get_object_ddl(
    db_type: str = "", host: str = "", port: int = 3306,
    username: str = "", password: str = "", database: str = "",
    obj_type: str = "PROCEDURE", obj_name: str = "",
    obj_schema: str = "",   # v53: MSSQL 스키마 힌트 (프론트 행의 schema_name)
):
    """오브젝트 DDL 단건 조회
    v53: password resolve 누락 수정 (500 에러 원인) + MSSQL OBJECT_ID 호출 시 스키마 사용.
    """
    # v53: password resolve — execute-object, objects 등과 동일 패턴
    try:
        from app.core.password_resolver import resolve_password as _rpw
        password = _rpw(
            password, side="source",
            host=host, username=username, database=database,
        )
    except Exception as _pw_err:
        import logging as _lg
        _lg.getLogger("databridge.schema").warning("[objects/ddl] password resolve 실패: %s", _pw_err)

    try:
        if db_type in ("mysql","aurora","cloudsql","tidb","mariadb"):
            import pymysql
            conn = pymysql.connect(host=host, port=int(port), user=username,
                password=password, database=database, charset="utf8mb4",
                connect_timeout=8, cursorclass=pymysql.cursors.DictCursor)
            try:
                cur = conn.cursor()
                ot = obj_type.upper()
                if ot == "PROCEDURE":
                    cur.execute(f"SHOW CREATE PROCEDURE `{obj_name}`")
                    row = cur.fetchone()
                    ddl = list(row.values())[2] if row else ""
                elif ot == "FUNCTION":
                    cur.execute(f"SHOW CREATE FUNCTION `{obj_name}`")
                    row = cur.fetchone()
                    ddl = list(row.values())[2] if row else ""
                elif ot == "TRIGGER":
                    cur.execute(f"SHOW CREATE TRIGGER `{obj_name}`")
                    row = cur.fetchone()
                    ddl = list(row.values())[2] if row else ""
                elif ot == "VIEW":
                    cur.execute(f"SHOW CREATE VIEW `{obj_name}`")
                    row = cur.fetchone()
                    ddl = list(row.values())[1] if row else ""
                else:
                    ddl = ""
            finally:
                conn.close()
        elif db_type in ("mssql","azure"):
            from app.core.db_conn import make_mssql_conn as _ms_conn
            conn = _ms_conn(host, port, username, password, database)
            try:
                cur = conn.cursor()
                ot = obj_type.upper()
                # v53: OBJECT_ID 호출 시 스키마 포함 — obj_schema 우선, 없으면 동적 탐색
                def _build_qualified_name():
                    if obj_schema:
                        return f"[{obj_schema}].[{obj_name}]"
                    # sys.objects + sys.schemas 로 동적 조회
                    try:
                        cur.execute("""
                            SELECT TOP 1 s.name
                            FROM sys.objects o
                            JOIN sys.schemas s ON o.schema_id = s.schema_id
                            WHERE o.name = ?
                              AND o.type IN ('P','FN','IF','TF','V','TR')
                            ORDER BY CASE WHEN s.name='dbo' THEN 0 ELSE 1 END, s.name
                        """, (obj_name,))
                        _r = cur.fetchone()
                        return f"[{_r[0]}].[{obj_name}]" if _r else f"[{obj_name}]"
                    except Exception:
                        return f"[{obj_name}]"

                if ot in ("PROCEDURE","FUNCTION","TRIGGER","VIEW"):
                    qn = _build_qualified_name()
                    cur.execute("SELECT OBJECT_DEFINITION(OBJECT_ID(?))", (qn,))
                    row = cur.fetchone()
                    ddl = row[0] if row and row[0] else ""
                    # v53: 빈 DDL 이면 sys.sql_modules 로 fallback
                    if not ddl:
                        cur.execute("""
                            SELECT m.definition
                            FROM sys.sql_modules m
                            JOIN sys.objects o ON m.object_id = o.object_id
                            JOIN sys.schemas s ON o.schema_id = s.schema_id
                            WHERE o.name = ?
                              AND (? = '' OR s.name = ?)
                        """, (obj_name, obj_schema or '', obj_schema or ''))
                        _r = cur.fetchone()
                        ddl = _r[0] if _r and _r[0] else ""
                else:
                    ddl = ""
            finally:
                conn.close()
        else:
            ddl = f"-- {db_type} DDL 조회 미지원"
        return {"ddl": ddl or f"-- {obj_name} DDL을 가져올 수 없습니다", "obj_type": obj_type, "obj_name": obj_name}
    except Exception as e:
        import logging as _lg
        _lg.getLogger("databridge.schema").error("[objects/ddl] 실패: obj=%s(%s) err=%s", obj_name, obj_type, e)
        raise HTTPException(500, f"DDL 조회 실패: {e}")



def _exec_mysql_compound_ddl(conn_info: dict, stmt: str, obj_sub: str = "TRIGGER") -> None:
    """
    MySQL에서 TRIGGER/PROCEDURE/FUNCTION 같은 복합 DDL 실행
    pymysql.CLIENT.MULTI_STATEMENTS + connection.query() 사용
    jobs.py에서도 import하여 사용 가능
    """
    import re as _r
    import pymysql
    from pymysql.constants import CLIENT
    
    # DELIMITER 제거
    clean = _r.sub(r"(?im)^DELIMITER\s+\S+\s*$", "", stmt).strip()
    clean = _r.sub(r"[\$\/]{2}\s*$", "", clean).strip()
    if clean and not clean.rstrip().endswith(";"):
        clean += ";"
    if not clean:
        return
    
    conn = pymysql.connect(
        host=conn_info["host"],
        port=int(conn_info.get("port", 3306)),
        user=conn_info.get("username", ""),
        password=conn_info.get("password", ""),
        database=conn_info.get("database", ""),
        charset="utf8mb4",
        connect_timeout=10,
        client_flag=CLIENT.MULTI_STATEMENTS
    )
    try:
        conn.query(clean)
        try:
            while conn.next_result():
                pass
        except Exception:
            pass
    finally:
        conn.close()


@router.post("/objects/convert")
def convert_object_ddl(body: dict):
    """오브젝트 DDL을 타겟 방언으로 변환 (ObjectExplorer 전용)"""
    import re
    src_db   = body.get("src_db", "mysql")
    tgt_db   = body.get("tgt_db", "mssql")
    obj_type = body.get("obj_type", "PROCEDURE").upper()
    obj_name = body.get("obj_name", "")
    ddl      = body.get("ddl", "")

    result = _convert_object_to_mssql(obj_type, obj_name, ddl, src_db)
    return {
        "converted_ddl": result.get("converted", ddl),
        "changes":       result.get("changes", []),
        "warnings":      result.get("warnings", []),
    }


@router.post("/objects/test")
def test_object_execution(body: dict):
    """오브젝트 실행 테스트 (ObjectExplorer 전용)"""
    import time as _t
    # v9 패치 #7: body의 password 필드 해결 (마스크/암호문 → 평문)
    from app.core.password_resolver import resolve_password as _rpw
    body = dict(body)
    body["password"] = _rpw(
        body.get("password",""),
        profile_id=body.get("profile_id"),
        side=body.get("side","source"),
        host=body.get("host"), username=body.get("username"),
        database=body.get("database"),
    )

    db_type  = body.get("db_type", "mysql")
    obj_type = body.get("obj_type", "PROCEDURE").upper()
    obj_name = body.get("obj_name", "")
    params   = [p.get("value","") for p in body.get("params", [])]
    start    = _t.monotonic()

    # 실행할 SQL 미리보기
    if obj_type == "PROCEDURE":
        ph = ",".join([repr(p) for p in params]) if params else ""
        sql_preview = f"CALL {obj_name}({ph})" if db_type.startswith("mysql") else f"EXEC [{obj_name}] {ph}"
    elif obj_type == "FUNCTION":
        ph = ",".join([repr(p) for p in params]) if params else ""
        sql_preview = f"SELECT {obj_name}({ph})"
    elif obj_type == "VIEW":
        sql_preview = f"SELECT * FROM {obj_name} LIMIT 50"
    elif obj_type == "TRIGGER":
        return {"success": False, "error": "트리거는 직접 실행이 불가합니다. 관련 테이블에 DML을 실행하세요.", 
                "sql": "", "elapsed_ms": 0, "row_count": 0, "result": []}
    else:
        return {"success": False, "error": f"{obj_type} 실행 미지원", "sql": "", "elapsed_ms": 0, "result": []}

    try:
        if db_type in ("mysql","aurora","cloudsql","tidb","mariadb"):
            import pymysql
            conn = pymysql.connect(
                host=body["host"], port=int(body["port"]), user=body["username"],
                password=body.get("password",""), database=body["database"],
                charset="utf8mb4", connect_timeout=10,
                cursorclass=pymysql.cursors.DictCursor
            )
            try:
                cur = conn.cursor()
                if obj_type == "PROCEDURE":
                    # v90.77: callproc 대신 직접 CALL (1406 회피)
                    ph = ", ".join(["%s"] * len(params)) if params else ""
                    sql = f"CALL `{obj_name}`({ph})" if ph else f"CALL `{obj_name}`()"
                    cur.execute(sql, params or [])
                    rows = []
                    try:
                        for rs in cur.stored_results():
                            fetched = rs.fetchall()
                            if fetched: rows = fetched
                    except Exception:
                        try: rows = cur.fetchall() or []
                        except Exception: rows = []
                elif obj_type == "FUNCTION":
                    ph = ",".join(["%s"]*len(params))
                    cur.execute(f"SELECT `{obj_name}`({ph}) AS result", params or [])
                    rows = cur.fetchall()
                elif obj_type == "VIEW":
                    cur.execute(f"SELECT * FROM `{obj_name}` LIMIT 50")
                    rows = cur.fetchall()
                elapsed = round((_t.monotonic()-start)*1000, 1)
                return {"success":True, "result":rows, "row_count":len(rows),
                        "elapsed_ms":elapsed, "sql":sql_preview, "error":""}
            finally:
                conn.close()
        elif db_type in ("mssql","azure"):
            from app.core.db_conn import make_mssql_conn as _ms_c
            conn = _ms_c(body['host'], body['port'], body['username'], body.get('password',''), body['database'])
            try:
                cur = conn.cursor()
                if obj_type == "PROCEDURE":
                    ph = ",".join(["?"]*len(params))
                    cur.execute(f"EXEC [{obj_name}] {ph}", params or [])
                    try:
                        cols = [d[0] for d in cur.description]
                        rows = [dict(zip(cols,r)) for r in cur.fetchmany(50)]
                    except:
                        rows = []
                elif obj_type == "FUNCTION":
                    ph = ",".join(["?"]*len(params))
                    cur.execute(f"SELECT [{obj_name}]({ph}) AS result", params or [])
                    cols = [d[0] for d in cur.description]
                    rows = [dict(zip(cols,r)) for r in cur.fetchall()]
                elif obj_type == "VIEW":
                    cur.execute(f"SELECT TOP 50 * FROM [{obj_name}]")
                    cols = [d[0] for d in cur.description]
                    rows = [dict(zip(cols,r)) for r in cur.fetchall()]
                elapsed = round((_t.monotonic()-start)*1000, 1)
                return {"success":True,"result":rows,"row_count":len(rows),"elapsed_ms":elapsed,"sql":sql_preview,"error":""}
            finally:
                conn.close()
    except Exception as e:
        return {"success":False,"error":str(e),"result":[],"row_count":0,
                "elapsed_ms":round((_t.monotonic()-start)*1000,1),"sql":sql_preview}


@router.post("/ai-convert-ddl")
def ai_convert_ddl(body: dict):
    """DDL 변환 — API 키 있으면 Claude AI, 없으면 규칙 기반 자동 변환"""
    import json as _j, urllib.request as _ur, urllib.error as _ue, logging as _lg, os as _os
    _log = _lg.getLogger("databridge.schema")

    ddl         = body.get("ddl", "")
    obj_type    = body.get("obj_type", "PROCEDURE").upper()
    obj_name    = body.get("obj_name", "")
    src_db      = (body.get("src_db") or "mysql").lower()
    tgt_db_type = (body.get("tgt_db_type") or "mssql").lower()

    if not ddl:
        return {"statements": [], "error": "DDL이 비어있습니다", "notes": ""}

    # API 키 확인 (설정 또는 환경변수)
    from app.api.routes.settings import _cfg as _get_cfg
    api_key = _get_cfg().get("anthropic_api_key", "").strip() or \
              _os.environ.get("ANTHROPIC_API_KEY", "").strip()

    # force_rule=True 이면 AI 스킵하고 바로 규칙 기반
    force_rule = body.get("force_rule", False)

    # API 키 없거나 force_rule이면 규칙 기반 변환
    if not api_key or force_rule:
        logger.info("[%s] %s — 규칙 기반 변환", obj_name, "force_rule" if force_rule else "API 키 없음")
        return _rule_based_ddl_convert(ddl, obj_type, obj_name, src_db, tgt_db_type)

    # Claude AI 변환
    is_mssql_src = src_db in ("mssql","azure","sqlserver")
    is_mysql_tgt = tgt_db_type in ("mysql","mariadb","aurora","tidb")
    direction = "SQL Server -> MySQL" if (is_mssql_src and is_mysql_tgt) else "MySQL -> SQL Server"

    tgt_is_mysql = tgt_db_type in ("mysql","aurora","mariadb","tidb","cloudsql")

    mysql_note = (
        "중요: MySQL/MariaDB용 DDL 생성 규칙:\n"
        "1. DELIMITER 명령어를 절대 포함하지 마세요 (pymysql에서 지원 안 됨)\n"
        "2. CREATE TRIGGER/PROCEDURE/FUNCTION 문 하나만 완전하게 작성하세요\n"
        "3. 본문 끝에 END; 로 마무리하세요\n"
        "4. DROP IF EXISTS 문이 필요하면 별도 statements 항목으로 분리하세요\n"
        "예시 올바른 형식:\n"
        "DROP TRIGGER IF EXISTS `trg_name`;\n"
        "CREATE TRIGGER `trg_name` BEFORE INSERT ON `tbl` FOR EACH ROW BEGIN ... END;\n"
    ) if tgt_is_mysql else ""

    msg = (
        "당신은 " + direction + " 마이그레이션 전문가입니다. "
        "아래 " + obj_type + " DDL을 변환하세요.\n"
        + mysql_note +
        "DDL:\n" + ddl[:3000] + "\n\n"
        'JSON만 응답 (마크다운 없이): {"statements":["SQL1","SQL2"],"notes":"설명"}'
    )

    try:
        payload = _j.dumps({
            "model": "claude-opus-4-6",
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": msg}]
        }).encode()
        req = _ur.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01"
            },
            method="POST"
        )
        with _ur.urlopen(req, timeout=60) as resp:
            data = _j.loads(resp.read().decode())
        import re as _re
        text = "".join(b.get("text","") for b in data.get("content",[]) if b.get("type")=="text").strip()
        text = _re.sub(r"^```\w*\n?","",text)
        text = _re.sub(r"\n?```$","",text).strip()
        result = _j.loads(text)
        logger.info("AI 변환 성공 [%s]", obj_name)
        # ── [v10 #18] 변환 지식 자동 축적 ──────────────────
        try:
            from app.engine.conversion_learner import learn_from_ai_conversion
            learn_from_ai_conversion(
                src_ddl=ddl, ai_result=result,
                obj_type=obj_type, obj_name=obj_name,
                src_db=src_db, tgt_db=tgt_db_type,
                job_id=body.get("job_id", ""),
            )
        except Exception as _le:
            logger.warning("[KB 학습] 훅 실패 (무시): %s", _le)
        # ───────────────────────────────────────────────────
        return result
    except Exception as e:
        logger.warning("AI 변환 실패 [%s]: %s — 규칙 기반 폴백", obj_name, e)
        return _rule_based_ddl_convert(ddl, obj_type, obj_name, src_db, tgt_db_type)


def _ai_convert_ddl(src_ddl: str, obj_type: str, obj_name: str,
                    src_db: str, tgt_db: str, error_hint: str = "",
                    job_id: str = "",
                    max_tokens: int = 8192) -> dict:
    """TABLE DDL을 AI로 변환 — jobs.py에서 호출
    v10 #18: 성공 반환 직전 conversion_learner 훅 호출 (타입/오브젝트 매핑 자동 축적)
    v90.40: max_tokens 파라미터 추가 (기본 8192). 잘림 검출 시 호출자가 16384/32768로 재호출 가능.
    v90.40: [AI-TRACE] 단계별 진단 로그 추가 (freeze 시 마지막 마커가 발생 지점)
    """
    import json as _j, urllib.request as _ur, urllib.error as _ue2
    import sys as _sys, time as _time
    from app.core.store import Store as _Store
    import logging as _lg
    _log = _lg.getLogger("databridge.jobs")

    # v90.40: TRACE 로그 헬퍼 (즉시 flush — freeze 직전 로그도 디스크에 남게)
    _trace_t0 = _time.monotonic()
    def _trace(stage: str, **kv):
        _elapsed = _time.monotonic() - _trace_t0
        _kv = " ".join(f"{k}={v}" for k, v in kv.items())
        _log.info("[AI-TRACE %s] [%s] (+%.2fs) %s", stage, obj_name, _elapsed, _kv)
        # logging handlers 강제 flush
        for _h in _log.handlers:
            try: _h.flush()
            except Exception: pass
        try: _sys.stderr.flush()
        except Exception: pass

    _trace("01-enter", obj_type=obj_type, src=src_db, tgt=tgt_db,
           ddl_len=len(src_ddl or ""), max_tokens=max_tokens,
           has_error_hint=bool(error_hint))

    # anthropic_api_key (시스템 설정) 또는 claude_api_key 둘 다 시도
    from app.api.routes.settings import _cfg as _gcfg
    api_key = _gcfg().get("anthropic_api_key", "").strip()
    if not api_key:
        api_key = (_Store("settings").get("claude_api_key") or {}).get("value", "")
    if not api_key:
        return {"statements": [], "notes": "API 키 없음 — 시스템 설정에서 Anthropic API 키를 입력하세요"}

    src_name = {"mssql":"MSSQL","mysql":"MySQL","postgresql":"PostgreSQL"}.get(src_db, src_db.upper())
    tgt_name = {"mssql":"MSSQL","mysql":"MySQL","postgresql":"PostgreSQL"}.get(tgt_db, tgt_db.upper())

    error_section = ""
    if error_hint:
        error_section = f"\n\n이전 변환 시 발생한 오류 (반드시 해결하세요):\n{error_hint}"

    # Phase E-2 (2026-04-24): 스키마 변환 규칙을 AI 프롬프트에 주입 (MySQL 타겟만)
    # AI 가 처음부터 일관된 스키마 표기를 쓰도록 강제.
    schema_rule_section = ""
    if tgt_db.lower() == "mysql":
        try:
            from app.core.schema_conversion_policy import build_schema_rule_prompt
            schema_rule_section = build_schema_rule_prompt("underscore", src_db, tgt_db)
        except Exception:
            schema_rule_section = ""
    error_section = error_section + schema_rule_section

    # 트리거 전용 프롬프트
    if obj_type.upper() == "TRIGGER":
        # v9 패치 #44: 방향별 프롬프트 분리 (기존엔 MSSQL→MySQL 만 있었음)
        if src_db == "mysql" and tgt_db in ("mssql","azure","sqlserver"):
            # MySQL → MSSQL
            prompt = (
                f"You are an expert in MySQL to MSSQL trigger conversion.\n"
                f"Convert the following MySQL trigger to MSSQL (SQL Server) syntax.{error_section}\n\n"
                "Rules:\n"
                "1. Header: CREATE OR ALTER TRIGGER [name] ON [table] AFTER/INSTEAD OF INSERT/UPDATE/DELETE AS BEGIN SET NOCOUNT ON;\n"
                "2. NEW.col -> INSERTED.col, OLD.col -> DELETED.col (but you often need to SELECT FROM INSERTED/DELETED)\n"
                "3. BEFORE triggers: convert to INSTEAD OF (for validation) or AFTER (for logging)\n"
                "4. FOR EACH ROW does not exist in MSSQL - use JOIN with INSERTED/DELETED tables for row-by-row logic\n"
                "5. IFNULL -> ISNULL, NOW() -> GETDATE(), CURRENT_TIMESTAMP -> GETDATE()\n"
                "6. SUBSTR -> SUBSTRING, CONCAT stays (MSSQL 2012+), LIMIT n -> TOP n\n"
                "7. SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='msg' -> RAISERROR(N'msg', 16, 1)\n"
                "8. DECLARE vars: MSSQL uses DECLARE @var TYPE; (must have @ prefix, comma-separated OK)\n"
                "9. SET @var = value (with @ prefix in MSSQL)\n"
                "10. IF ... THEN ... END IF -> IF ... BEGIN ... END (no THEN)\n"
                "11. TIME_FORMAT / DATE_FORMAT -> CONVERT or FORMAT functions\n"
                "12. REPLACE / LEFT / RIGHT stay the same\n"
                "13. [CRITICAL] Remove ALL backticks (`) - MSSQL uses [brackets] for identifiers\n"
                "14. [CRITICAL] Do NOT include COLLATE utf8mb4_unicode_ci - that is MySQL-only\n"
                "15. Multi-event triggers (INSERT, UPDATE, DELETE on same event) can stay as one in MSSQL\n"
                "16. UPDATE table alias: MSSQL supports 'UPDATE t SET ... FROM table t WHERE ...'\n"
                "17. For multi-row triggers, use SELECT ... FROM INSERTED instead of single-row access\n"
                "18. [CRITICAL] Variable names in MSSQL are case-insensitive. "
                "If original MySQL uses both 'rec_system_code' and 'REC_SYSTEM_CODE' as column references, "
                "declare ONLY ONE @variable (e.g. @rec_system_code) and use it consistently. "
                "Do NOT declare both @rec_system_code and @REC_SYSTEM_CODE — MSSQL will raise "
                "'variable already declared' error (134).\n\n"
                f"Original MySQL trigger:\n{src_ddl[:3000]}\n\n"
                "Respond ONLY with JSON, no other text:\n"
                + '{"statements":["IF OBJECT_ID(N\'[dbo].[name]\', N\'TR\') IS NOT NULL DROP TRIGGER [name];","CREATE OR ALTER TRIGGER [name] ON [table] AFTER INSERT AS BEGIN SET NOCOUNT ON; ... END"],"notes":"summary"}'
            )
        else:
            # MSSQL → MySQL (기존)
            prompt = (
                f"You are an expert in MSSQL to MySQL trigger conversion.\n"
                f"Convert the following MSSQL trigger to MySQL 8.0 syntax.{error_section}\n\n"
                "Rules:\n"
                "1. Header: CREATE TRIGGER `name` AFTER/BEFORE INSERT/UPDATE/DELETE ON `table` FOR EACH ROW\n"
                "2. INSERTED -> NEW, DELETED -> OLD\n"
                "3. Remove FROM INSERTED/DELETED JOIN syntax, use NEW/OLD directly\n"
                "4. UPDATE t SET ... FROM table t WHERE ... -> UPDATE table SET col=val WHERE ... (no FROM in MySQL UPDATE)\n"
                "5. IF UPDATE(col) -> IF NEW.col <> OLD.col\n"
                "6. RAISERROR -> SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='...'\n"
                "7. GETDATE()->NOW(), NEWID()->UUID(), ISNULL->IFNULL, SYSTEM_USER->CURRENT_USER()\n"
                "8. N'string' -> 'string', string concat + -> CONCAT()\n"
                "9. Remove SET NOCOUNT ON, RETURN statements\n"
                "10. Multiple events (INSERT,UPDATE,DELETE) -> split into separate triggers\n"
                "11. SELECT ... FROM INSERTED i JOIN DELETED d -> use NEW/OLD directly\n"
                "12. [CRITICAL] Collation: MySQL server uses utf8mb4_unicode_ci. "
                "If comparing VARCHAR params with table columns that may use utf8mb4_0900_ai_ci, "
                "append COLLATE utf8mb4_unicode_ci to string params in WHERE/BETWEEN/JOIN conditions "
                "to avoid Illegal mix of collations error (1270).\n"
                "13. [CRITICAL] VARCHAR date params (YYYYMMDD=8chars, YYYYMM=6chars): "
                "Use VARCHAR(8) or VARCHAR(6), NOT DATE type. Do NOT use DATE format 'YYYY-MM-DD'.\n\n"
                f"Original MSSQL trigger:\n{src_ddl[:3000]}\n\n"
                "Respond ONLY with JSON, no other text:\n"
                + '{"statements":["DROP TRIGGER IF EXISTS `name`;","CREATE TRIGGER ..."],"notes":"summary"}'
            )
    else:
        prompt = (
            f"당신은 {src_name} → {tgt_name} 데이터베이스 마이그레이션 전문가입니다.\n"
            f"아래 {src_name} 오브젝트 [{obj_name}]을 {tgt_name}에서 "
            f"완벽하게 실행 가능하도록 변환하세요.{error_section}\n\n"
            "변환 규칙:\n"
            "- geography, geometry, hierarchyid 등 미지원 타입 → TEXT 또는 VARCHAR(500)로 변환\n"
            f"- {tgt_name} 완전 호환 문법 사용\n"
            "- DROP IF EXISTS + CREATE 형태\n"
            "- PRIMARY KEY, NOT NULL, DEFAULT 유지\n"
            "- [필수] MSSQL VARCHAR 날짜 파라미터 변환 규칙:\n"
            "  * YYYYMMDD 형식(8자리) → VARCHAR(8) 유지, DATE 타입으로 바꾸지 말 것\n"
            "  * YYYYMM 형식(6자리) → VARCHAR(6) 유지\n"
            "  * 파라미터 길이를 임의로 줄이지 말 것 (1406 오류 원인)\n"
            "- [필수] MySQL Collation 충돌 방지:\n"
            "  * MySQL 서버 기본 collation: utf8mb4_unicode_ci\n"
            "  * VARCHAR 파라미터를 테이블 컬럼과 BETWEEN/WHERE/JOIN 비교 시\n"
            "    반드시 COLLATE utf8mb4_unicode_ci 추가\n"
            "    예) WHERE col BETWEEN p_sdate COLLATE utf8mb4_unicode_ci AND p_edate COLLATE utf8mb4_unicode_ci\n"
            "  * 미적용 시 1270 Illegal mix of collations 오류 발생\n"
            "- MSSQL 전용 함수 변환: GETDATE()→NOW(), ISNULL()→IFNULL(), "
            "CONVERT(DATE,x)→DATE(x), DATEADD(day,n,d)→DATE_ADD(d,INTERVAL n DAY)\n"
            "- @파라미터명 → p_파라미터명 (언더스코어 유지)\n\n"
            f"원본 {src_name} DDL:\n{src_ddl[:3000]}\n\n"
            "JSON만 응답 (설명 없이):\n"
            + '{"statements":["DROP ...","CREATE ..."],"notes":"변경사항 요약"}'
        )

    try:
        # v90.40: TRACE 02 - 프롬프트 빌드 완료 (위에서 분기별로 prompt 구성됨)
        _trace("02-prompt-built", prompt_len=len(prompt))

        payload = _j.dumps({
            "model": "claude-opus-4-6",
            "max_tokens": max_tokens,  # v90.40: 호출자가 지정 가능 (기본 8192)
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        req = _ur.Request(
            "https://api.anthropic.com/v1/messages", data=payload,
            headers={"Content-Type":"application/json","x-api-key":api_key,"anthropic-version":"2023-06-01"}
        )

        # v90.40: TRACE 03 - HTTP 요청 송출 직전
        _trace("03-http-send", payload_len=len(payload), max_tokens=max_tokens, timeout=45)

        _http_t0 = _time.monotonic()
        with _ur.urlopen(req, timeout=45) as resp:
            _resp_bytes = resp.read()
        _http_elapsed = _time.monotonic() - _http_t0

        # v90.40: TRACE 04 - HTTP 응답 수신
        _trace("04-http-recv", resp_bytes=len(_resp_bytes), http_elapsed=f"{_http_elapsed:.2f}s")

        data = _j.loads(_resp_bytes)

        # v90.40: TRACE 05 - JSON 파싱 (HTTP 페이로드의 outer JSON)
        _trace("05-outer-json-parsed", content_blocks=len(data.get("content", [])),
               stop_reason=data.get("stop_reason", "?"))

        text = next((b["text"] for b in data.get("content",[]) if b.get("type")=="text"), "")
        _log.info("[AI] 응답 수신: %d chars", len(text))

        # v90.40: TRACE 06 - 텍스트 추출 완료
        _trace("06-text-extracted", text_len=len(text))

        # ── 사용량 기록 ──────────────────────────────────────────
        # v90.40: TRACE 07 - 사용량 기록 진입 (★★ freeze 가장 의심 구간 시작 ★★)
        _trace("07-usage-record-enter")
        try:
            usage = data.get("usage", {})
            in_tok  = usage.get("input_tokens", 0)
            out_tok = usage.get("output_tokens", 0)
            if in_tok or out_tok:
                _us = _Store("claude_usage")
                prev = _us.get("total") or {"calls":0,"input_tokens":0,"output_tokens":0,"objects":[]}
                prev["calls"]         += 1
                prev["input_tokens"]  += in_tok
                prev["output_tokens"] += out_tok
                prev.setdefault("objects", []).append({
                    "ts":   __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "name": obj_name,
                    "type": f"AI_TABLE_{obj_type}",
                    "in":   in_tok, "out": out_tok,
                })
                _us.set("total", prev)
                _log.info("[AI] 사용량 기록 — %s: in=%d out=%d tok", obj_name, in_tok, out_tok)
        except Exception as ue:
            _log.warning("[AI] 사용량 기록 실패: %s", ue)
        # ─────────────────────────────────────────────────────────
        # v90.40: TRACE 08 - 사용량 기록 종료 (★★ 본부장님 보고 기준 freeze 발생 직후 시점 ★★)
        _trace("08-usage-record-done", in_tok=usage.get("input_tokens", 0) if 'usage' in dir() else 0,
               out_tok=usage.get("output_tokens", 0) if 'usage' in dir() else 0)

        text = text.strip()
        # JSON 펜스 제거
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(l for l in lines if not l.strip().startswith("```"))
        text = text.strip()

        # v90.40: TRACE 09 - 텍스트 전처리 완료
        _trace("09-text-prepped", text_len=len(text))

        if not text:
            _log.warning("_ai_convert_ddl: 빈 응답")
            _trace("12-return-empty")
            return {"statements": [], "notes": "빈 응답"}

        # ═══════════════════════════════════════════════════════════
        # Phase E (2026-04-24): JSON 파싱 견고화 + 사후 정규화
        # ═══════════════════════════════════════════════════════════
        # 기존 json.loads() 만 쓰면 "Extra data" 에러 등으로 대량 실패.
        # ai_response_parser 의 5단계 fallback 전략으로 복구율 대폭 향상.
        # v90.40: TRACE 10 - JSON 파싱 시작 (extract_json_robust ReDoS 의심 구간)
        _trace("10-json-parse-enter")
        try:
            from app.core.ai_response_parser import extract_json_robust
            parsed = extract_json_robust(text)
        except Exception as _pe:
            _log.warning("[Phase E] 파서 import 실패, 기존 방식 fallback: %s", _pe)
            try:
                parsed = _j.loads(text)
            except Exception as je:
                _log.warning("_ai_convert_ddl JSON 파싱 실패: %s\n응답: %s", je, text[:300])
                _trace("12-return-json-fail", error=str(je)[:80])
                return {"statements": [], "notes": f"JSON 파싱 실패: {je}"}

        # v90.40: TRACE 11 - JSON 파싱 완료
        _trace("11-json-parse-done",
               stmt_count=len(parsed.get("statements", []) if isinstance(parsed, dict) else []))

        stmts = parsed.get("statements", [])
        if not stmts:
            _log.warning("_ai_convert_ddl: statements 없음, 응답: %s", text[:200])

        # v90.40: TRACE 12 - 스키마 정규화 진입
        _trace("12-schema-norm-enter", stmt_count=len(stmts), tgt=tgt_db)

        # Phase E-2: 스키마 변환 규칙 사후 정규화 (MySQL 타겟만)
        if tgt_db.lower() == "mysql" and stmts:
            try:
                from app.core.schema_conversion_policy import (
                    enforce_schema_strategy,
                    get_strategy_from_job,
                )
                # Job 에서 전략 가져오기 (없으면 기본값 "underscore")
                strategy = "underscore"  # TODO: Job 에서 가져올 수 있게 확장
                normalized_stmts = []
                all_fixes = []
                for s in stmts:
                    ns, fs = enforce_schema_strategy(s, strategy)
                    normalized_stmts.append(ns)
                    all_fixes.extend(fs)
                if all_fixes:
                    _log.info("[Phase E-2] %s 스키마 정규화 적용: %s", obj_name, all_fixes[:3])
                stmts = normalized_stmts
            except Exception as _se:
                _log.warning("[Phase E-2] 스키마 정규화 실패 (무시): %s", _se)

        # v90.40: TRACE 13 - Preflight 검증 진입
        _trace("13-preflight-enter", stmt_count=len(stmts))

        # Phase E-3: Pre-flight syntax validator — 자동 수정 가능한 문제는 수정
        if stmts:
            try:
                from app.core.sql_preflight_validator import preflight_check
                fixed_stmts = []
                for s in stmts:
                    pf = preflight_check(s, obj_type)
                    if pf["auto_fixed_sql"] != s:
                        _log.info(
                            "[Phase E-3] %s preflight 자동 수정: %s",
                            obj_name,
                            [i.get("rule") for i in pf["issues"]],
                        )
                        fixed_stmts.append(pf["auto_fixed_sql"])
                    else:
                        fixed_stmts.append(s)
                    # fail 심각도 경고는 로그로만 (자동 수정 불가)
                    fails = [i for i in pf["issues"] if i.get("severity") == "fail"]
                    if fails:
                        _log.warning(
                            "[Phase E-3] %s 자동 수정 불가 이슈: %s",
                            obj_name,
                            [(i["rule"], i["msg"]) for i in fails],
                        )
                stmts = fixed_stmts
            except Exception as _pve:
                _log.warning("[Phase E-3] preflight 실패 (무시): %s", _pve)

        # v90.40: TRACE 14 - Preflight 완료, KB 학습 진입
        _trace("14-kb-learn-enter", final_stmt_count=len(stmts))

        result = {"statements": stmts, "notes": parsed.get("notes", "")}
        # ═══════════════════════════════════════════════════════════
        try:
            # ── [v10 #18] 변환 지식 자동 축적 ──────────────────
            from app.engine.conversion_learner import learn_from_ai_conversion
            learn_from_ai_conversion(
                src_ddl=src_ddl, ai_result=result,
                obj_type=obj_type, obj_name=obj_name,
                src_db=src_db, tgt_db=tgt_db, job_id=job_id,
            )
        except Exception as _le:
            _log.warning("[KB 학습] 훅 실패 (무시): %s", _le)
        # ───────────────────────────────────────────────────

        # v90.40: TRACE 15 - 정상 반환 직전
        _trace("15-return-ok", final_stmt_count=len(stmts))
        return result
    except Exception as e:
        _log.warning("_ai_convert_ddl 실패: %s", e)
        # v90.40: TRACE 99 - 예외로 인한 반환
        try: _trace("99-return-exception", error=str(e)[:120])
        except Exception: pass
        return {"statements": [], "notes": str(e)}


def _rule_based_ddl_convert(ddl, obj_type, obj_name, src_db, tgt_db):
    """
    범용 DDL 변환 엔진
    - obj_mapping.py 의 규칙을 우선 적용
    - 방향별 전문 변환 함수로 보완
    - 새로운 패턴은 obj_mapping 규칙에 추가하면 자동 적용
    """
    import re as R, logging as _lg
    _log = _lg.getLogger("databridge.schema")

    if not ddl or not ddl.strip():
        return {"statements": [], "notes": "DDL 없음"}

    # src_db 정규화
    MYSQL_TYPES  = ("mysql","aurora","mariadb","tidb","cloudsql")
    MSSQL_TYPES  = ("mssql","azure","sqlserver")
    PG_TYPES     = ("postgresql","postgres","redshift")
    ORA_TYPES    = ("oracle",)

    src = src_db.lower()
    tgt = tgt_db.lower()

    s = ddl.strip()
    changes = []

    # ── STEP 1: obj_mapping 규칙 적용 ──────────────────────────
    try:
        from app.api.routes.obj_mapping import _rules, _init_rules
        _init_rules()
        mapping_rules = [
            r for r in _rules.values()
            if r.get("src_db") == src and r.get("tgt_db") == tgt
            and r.get("obj_type") in (obj_type, "SYNTAX", "FUNCTION_SYNTAX", "ALL")
            and r.get("enabled", True)
        ]
        for rule in mapping_rules:
            sp = rule.get("src_syntax", "")
            tp = rule.get("tgt_syntax", "")
            if sp and tp and sp != tp:
                # regex_mode: src_syntax를 정규식으로 처리
                if rule.get("regex_mode"):
                    try:
                        new_s = R.sub(sp, tp, s, flags=R.IGNORECASE|R.MULTILINE)
                        if new_s != s:
                            changes.append(rule.get("note","regex replace"))
                            s = new_s
                    except Exception:
                        pass
    except Exception as e:
        logger.debug("obj_mapping 규칙 로드 실패: %s", e)

    # ── STEP 2: 공통 정리 함수 ──────────────────────────────────
    def _strip_mysql_meta(t):
        """MySQL 전용 메타정보 제거"""
        t = R.sub(r'DEFINER\s*=\s*`[^`]+`@`[^`]+`\s*', '', t, flags=R.IGNORECASE)
        t = R.sub(r'\bSQL\s+SECURITY\s+\w+\b', '', t, flags=R.IGNORECASE)
        t = R.sub(r'\b(NOT\s+DETERMINISTIC|CONTAINS\s+SQL|READS\s+SQL\s+DATA|MODIFIES\s+SQL\s+DATA|NO\s+SQL)\b', '', t, flags=R.IGNORECASE)
        t = R.sub(r"COMMENT\s+'[^']*'", '', t, flags=R.IGNORECASE)
        t = R.sub(r'DELIMITER\s+\S+\s*', '', t, flags=R.IGNORECASE)
        t = t.replace('$$', '').replace('//', '')
        return t

    def _strip_mssql_meta(t):
        """MSSQL 전용 메타정보 제거"""
        t = R.sub(r'\bSET\s+NOCOUNT\s+ON\s*;?', '', t, flags=R.IGNORECASE)
        t = R.sub(r'\bWITH\s*\(NOLOCK\)', '', t, flags=R.IGNORECASE)
        t = R.sub(r'\[dbo\]\.', '', t, flags=R.IGNORECASE)
        return t

    def _quote(t, src_type, tgt_type):
        """식별자 인용부호 변환"""
        if src_type in MYSQL_TYPES and tgt_type in MSSQL_TYPES:
            return R.sub(r'`([^`]+)`', r'[\1]', t)
        elif src_type in MYSQL_TYPES and tgt_type in PG_TYPES:
            return R.sub(r'`([^`]+)`', r'"\1"', t)
        elif src_type in MSSQL_TYPES and tgt_type in MYSQL_TYPES:
            return R.sub(r'\[([^\]]+)\]', r'`\1`', t)
        elif src_type in MSSQL_TYPES and tgt_type in PG_TYPES:
            return R.sub(r'\[([^\]]+)\]', r'"\1"', t)
        return t

    def _convert_types(t, src_type, tgt_type):
        """공통 데이터 타입 변환"""
        if tgt_type in MSSQL_TYPES:
            t = R.sub(r'\bVARCHAR\b', 'NVARCHAR', t, flags=R.IGNORECASE)
            t = R.sub(r'\bTEXT\b', 'NVARCHAR(MAX)', t, flags=R.IGNORECASE)
            t = R.sub(r'\bDATETIME\b(?!\s*2)', 'DATETIME2(6)', t, flags=R.IGNORECASE)
            t = R.sub(r'\bTINYINT\s*\(1\)', 'BIT', t)
            t = R.sub(r'\bNOW\s*\(\)', 'GETDATE()', t, flags=R.IGNORECASE)
            t = R.sub(r'\bCURRENT_TIMESTAMP\b', 'GETDATE()', t, flags=R.IGNORECASE)
            t = R.sub(r'\bIFNULL\s*\(', 'ISNULL(', t, flags=R.IGNORECASE)
            t = R.sub(r'\bSUBSTR\s*\(', 'SUBSTRING(', t, flags=R.IGNORECASE)
            t = R.sub(r'\bLIMIT\s+(\d+)', r'/* LIMIT \1 removed */', t, flags=R.IGNORECASE)
        elif tgt_type in MYSQL_TYPES:
            t = R.sub(r'\bNVARCHAR\b', 'VARCHAR', t, flags=R.IGNORECASE)
            t = R.sub(r'\bDATETIME2\s*\(\d+\)', 'DATETIME(6)', t, flags=R.IGNORECASE)
            t = R.sub(r'\bGETDATE\s*\(\)', 'NOW()', t, flags=R.IGNORECASE)
            t = R.sub(r'\bISNULL\s*\(', 'IFNULL(', t, flags=R.IGNORECASE)
            t = R.sub(r'\bBIT\b', 'TINYINT(1)', t, flags=R.IGNORECASE)
        elif tgt_type in PG_TYPES:
            t = R.sub(r'\bNVARCHAR\b', 'VARCHAR', t, flags=R.IGNORECASE)
            t = R.sub(r'\bDATETIME\b', 'TIMESTAMP', t, flags=R.IGNORECASE)
            t = R.sub(r'\bGETDATE\s*\(\)', 'NOW()', t, flags=R.IGNORECASE)
            t = R.sub(r'\bISNULL\s*\(', 'COALESCE(', t, flags=R.IGNORECASE)
        return t

    def _convert_flow(t, src_type, tgt_type):
        """제어 흐름 변환 (IF/WHILE/BEGIN-END)"""
        if src_type in MYSQL_TYPES and tgt_type in MSSQL_TYPES:
            t = R.sub(r'\bIF\s+(.+?)\s+THEN\b', r'IF \1 BEGIN', t, flags=R.IGNORECASE)
            t = R.sub(r'\bELSEIF\s+(.+?)\s+THEN\b', r'END ELSE IF \1 BEGIN', t, flags=R.IGNORECASE)
            t = R.sub(r'\bELSE\b(?!\s+IF)', 'END ELSE BEGIN', t, flags=R.IGNORECASE)
            t = R.sub(r'\bEND\s+IF\b', 'END', t, flags=R.IGNORECASE)
            t = R.sub(r'\bWHILE\s+(.+?)\s+DO\b', r'WHILE \1 BEGIN', t, flags=R.IGNORECASE)
            t = R.sub(r'\bEND\s+WHILE\b', 'END', t, flags=R.IGNORECASE)
            t = R.sub(r'\bLEAVE\s+\w+\b', 'BREAK', t, flags=R.IGNORECASE)
            t = R.sub(r'\bITERATE\s+\w+\b', 'CONTINUE', t, flags=R.IGNORECASE)
            t = R.sub(r'^\s*\w+:\s*$', '', t, flags=R.MULTILINE)
        elif src_type in MSSQL_TYPES and tgt_type in MYSQL_TYPES:
            t = R.sub(r'\bIF\s+(.+?)\s+BEGIN\b', r'IF \1 THEN', t, flags=R.IGNORECASE)
            t = R.sub(r'\bEND\s+ELSE\s+IF\b', 'ELSEIF', t, flags=R.IGNORECASE)
            t = R.sub(r'\bEND\s+ELSE\s+BEGIN\b', 'ELSE', t, flags=R.IGNORECASE)
            t = R.sub(r'\bWHILE\s+(.+?)\s+BEGIN\b', r'WHILE \1 DO', t, flags=R.IGNORECASE)
            # 주의: 마지막 END(함수/프로시저 종료)는 END IF로 바꾸면 안됨
            # IF...BEGIN...END 블록의 END만 END IF로 변환
            t = R.sub(r'\bEND\b(?=\s*;?\s*\n\s*(?:ELSEIF|ELSE|END\s+IF))', 'END IF', t, flags=R.IGNORECASE)
        return t

    def _convert_error(t, src_type, tgt_type):
        """오류 처리 변환"""
        if src_type in MYSQL_TYPES and tgt_type in MSSQL_TYPES:
            def _raiserr(m):
                msg = m.group(1) if m.lastindex else '오류'
                return f"RAISERROR(N'{msg}', 16, 1)"
            t = R.sub(r"SIGNAL\s+SQLSTATE\s+'[^']+'\s+SET\s+MESSAGE_TEXT\s*=\s*'([^']*)'", _raiserr, t, flags=R.IGNORECASE)
            t = R.sub(r'\bROLLBACK\s+TRANSACTION\b', 'ROLLBACK TRANSACTION', t, flags=R.IGNORECASE)
        elif src_type in MSSQL_TYPES and tgt_type in MYSQL_TYPES:
            def _signal(m):
                msg = m.group(1) if m.lastindex else '오류'
                return f"SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='{msg}'"
            t = R.sub(r"RAISERROR\s*\(\s*N?'([^']+)'\s*,\s*\d+\s*,\s*\d+\s*\)", _signal, t, flags=R.IGNORECASE)
            t = R.sub(r'\bTHROW\s+\d+\s*,\s*N?\'([^\']+)\'\s*,\s*\d+\s*;?', _signal, t, flags=R.IGNORECASE)
        return t

    # ── STEP 3: 오브젝트 타입별 전문 변환 ───────────────────────
    get_name = lambda t, kw: (R.search(
        r'CREATE\s+(?:OR\s+(?:REPLACE|ALTER)\s+)?' + kw +
        r'\s+(?:\[?dbo\]?\.)?\[?`?"?(\w+)`?"?\]?', t, R.IGNORECASE
    ) or type('', (), {'group': lambda s, n: obj_name})()).group(1)

    if obj_type == "VIEW":
        s = _strip_mysql_meta(s) if src in MYSQL_TYPES else _strip_mssql_meta(s)
        s = _quote(s, src, tgt)
        s = _convert_types(s, src, tgt)
        if src in MYSQL_TYPES and tgt in MSSQL_TYPES:
            s = R.sub(r'CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+', 'CREATE OR ALTER VIEW ', s, flags=R.IGNORECASE)
            s = R.sub(r'\bIF\s*\(', 'IIF(', s, flags=R.IGNORECASE)
        elif src in MSSQL_TYPES and tgt in MYSQL_TYPES:
            s = R.sub(r'CREATE\s+(?:OR\s+ALTER\s+)?VIEW\s+', 'CREATE OR REPLACE VIEW ', s, flags=R.IGNORECASE)
        elif src in MYSQL_TYPES and tgt in PG_TYPES:
            s = R.sub(r'CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+', 'CREATE OR REPLACE VIEW ', s, flags=R.IGNORECASE)
        logger.info("[%s] VIEW 변환 완료", obj_name)
        return {"statements": [s.strip()], "notes": f"규칙 기반 변환 — VIEW ({src}→{tgt})"}

    elif obj_type in ("PROCEDURE", "FUNCTION"):
        s = _strip_mysql_meta(s) if src in MYSQL_TYPES else _strip_mssql_meta(s)
        s = _quote(s, src, tgt)
        s = _convert_types(s, src, tgt)
        s = _convert_flow(s, src, tgt)
        s = _convert_error(s, src, tgt)
        nm = get_name(s, obj_type)

        if src in MYSQL_TYPES and tgt in MSSQL_TYPES:
            # 파라미터 방향 제거 (IN/OUT → @param)
            s = R.sub(r'\b(IN|OUT|INOUT)\s+(\w+)\s+([\w()]+)', r'@\2 \3', s, flags=R.IGNORECASE)
            # DECLARE 변환
            s = R.sub(r'\bDECLARE\s+(\w+)\s+([\w()]+)(?:\s+DEFAULT\s+([^;]+))?',
                      lambda m: f'DECLARE @{m.group(1)} {m.group(2)}' + (f' = {m.group(3)}' if m.group(3) else ''), s, flags=R.IGNORECASE)
            s = R.sub(r'\bSET\s+(?!@)(\w+)\s*=', r'SET @\1 =', s, flags=R.IGNORECASE)
            s = R.sub(r'\bCALL\s+`?(\w+)`?\s*\(', r'EXEC [\1] (', s, flags=R.IGNORECASE)
            # BEGIN...END 래핑
            s = R.sub(r'\bAS\s*\n\s*BEGIN\b', 'AS\nBEGIN', s, flags=R.IGNORECASE)
            # DETERMINISTIC 등 MySQL 전용 제거
            s = R.sub(r'\bDETERMINISTIC\b', '', s, flags=R.IGNORECASE)
            s = R.sub(r'\bRETURNS\s+', 'RETURNS ', s, flags=R.IGNORECASE)
            # CREATE PROCEDURE/FUNCTION → CREATE OR ALTER
            s = R.sub(r'CREATE\s+(?:OR\s+REPLACE\s+)?(PROCEDURE|FUNCTION)\s+\[?`?(\w+)`?\]?\s*',
                      r'CREATE OR ALTER \1 [\2] ', s, flags=R.IGNORECASE)
            # SELECT INTO → SET @var =
            s = R.sub(r'\bSELECT\s+(.+?)\s+INTO\s+(?!OUTFILE)(@?\w+)\s+FROM\b',
                      r'SELECT @\2 = \1 FROM', s, flags=R.IGNORECASE)
            drop = (f"IF OBJECT_ID(N'[dbo].[{nm}]', N'{'P' if obj_type=='PROCEDURE' else 'FN'}') IS NOT NULL "
                    f"DROP {obj_type} [{nm}]")
            logger.info("[%s] %s → MSSQL DROP+CREATE 분리", obj_name, obj_type)
            return {"statements": [drop, s.strip()],
                    "notes": f"규칙 기반 변환 — {obj_type} MySQL→MSSQL"}

        elif src in MSSQL_TYPES and tgt in MYSQL_TYPES:
            # @param → param
            s = R.sub(r'@(\w+)', r'\1', s)
            # EXEC → CALL
            s = R.sub(r'\bEXEC\s+\[?(\w+)\]?\s*\(', r'CALL `\1`(', s, flags=R.IGNORECASE)
            # CREATE OR ALTER → CREATE + 이름 뒤에 줄바꿈 보장
            s = R.sub(r'CREATE\s+(?:OR\s+ALTER\s+)?(PROCEDURE|FUNCTION)\s+\[?(\w+)\]?\s*',
                      r'CREATE \1 `\2`\n', s, flags=R.IGNORECASE)
            # [dbo]. 제거
            s = R.sub(r'\[dbo\]\.', '', s, flags=R.IGNORECASE)
            # FUNCTION: AS BEGIN → DETERMINISTIC\nBEGIN
            if obj_type == "FUNCTION":
                s = R.sub(r'\bAS\s*\n\s*BEGIN\b', 'DETERMINISTIC\nBEGIN', s, flags=R.IGNORECASE)
                s = R.sub(r'\bAS\s+BEGIN\b', 'DETERMINISTIC\nBEGIN', s, flags=R.IGNORECASE)
                s = R.sub(r'(RETURNS\s+[\w()]+\s*\n)(\s*BEGIN\b)',
                          r'\1DETERMINISTIC\n\2', s, flags=R.IGNORECASE)
            else:
                # PROCEDURE: AS BEGIN → BEGIN, 이름 뒤 괄호 없으면 () 추가
                s = R.sub(r'(CREATE\s+PROCEDURE\s+`\w+`)\s*\n\s*(?:AS\s*\n\s*)?BEGIN',
                          r'\1()\nBEGIN', s, flags=R.IGNORECASE)
                s = R.sub(r'\bAS\s*\n\s*BEGIN\b', 'BEGIN', s, flags=R.IGNORECASE)
                s = R.sub(r'\bAS\s+BEGIN\b', 'BEGIN', s, flags=R.IGNORECASE)
            # RAISERROR → SIGNAL
            s = R.sub(r"RAISERROR\s*\(\s*N?'([^']+)'\s*,\s*\d+\s*,\s*\d+\s*\)",
                      r"SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='\1'", s, flags=R.IGNORECASE)
            # ROLLBACK TRANSACTION → MySQL 트리거에서는 SIGNAL로 대체 (ROLLBACK 불가)
            s = R.sub(r'\bROLLBACK\s+TRANSACTION\b\s*;?', '', s, flags=R.IGNORECASE)
            s = R.sub(r'\bROLLBACK\b\s*;?', '', s, flags=R.IGNORECASE)
            # 제어 흐름 변환
            s = _convert_flow(s, src, tgt)
            drop = f"DROP {obj_type} IF EXISTS `{nm}`"
            logger.info("[%s] %s → MySQL DROP+CREATE 분리", obj_name, obj_type)
            return {"statements": [drop, s.strip()],
                    "notes": f"규칙 기반 변환 — {obj_type} MSSQL→MySQL"}

        elif src in MYSQL_TYPES and tgt in PG_TYPES:
            s = R.sub(r'CREATE\s+(?:OR\s+REPLACE\s+)?(PROCEDURE|FUNCTION)\s+`?(\w+)`?\s*',
                      r'CREATE OR REPLACE \1 "\2" ', s, flags=R.IGNORECASE)
            s = R.sub(r'\bDETERMINISTIC\b', '', s, flags=R.IGNORECASE)
            drop = f"DROP {obj_type} IF EXISTS \"{nm}\""
            return {"statements": [drop, s.strip()],
                    "notes": f"규칙 기반 변환 — {obj_type} MySQL→PostgreSQL"}

        else:
            # 기타 방향: 기본 정리만
            logger.warning("[%s] %s→%s 변환 미지원, 기본 정리만 적용", obj_name, src, tgt)
            return {"statements": [s.strip()],
                    "notes": f"부분 변환 — {src}→{tgt} 방향은 AI 변환 권장"}

    elif obj_type == "TRIGGER":
        s = _strip_mysql_meta(s) if src in MYSQL_TYPES else _strip_mssql_meta(s)
        nm = get_name(s, "TRIGGER")

        if src in MYSQL_TYPES and tgt in MSSQL_TYPES:
            s = R.sub(r'\bNEW\.(\w+)', r'INSERTED.\1', s, flags=R.IGNORECASE)
            s = R.sub(r'\bOLD\.(\w+)', r'DELETED.\1', s, flags=R.IGNORECASE)
            # 검증 트리거 (SIGNAL 있으면 BEFORE → INSTEAD OF 또는 AFTER)
            has_signal = bool(R.search(r'\bSIGNAL\b', s, R.IGNORECASE))
            def _trig_hdr(m):
                nm2, timing, ev, tbl = m.group(1), m.group(2).upper(), m.group(3).upper(), m.group(4)
                mssql_timing = 'INSTEAD OF' if timing == 'BEFORE' else 'AFTER'
                return (f'CREATE OR ALTER TRIGGER [{nm2}]\nON [{tbl}]\n'
                        f'{mssql_timing} {ev}\nAS\nBEGIN\n    SET NOCOUNT ON;')
            s = R.sub(
                r'CREATE\s+(?:OR\s+ALTER\s+)?TRIGGER\s+\[?`?(\w+)`?\]?\s+'
                r'(BEFORE|AFTER)\s+(INSERT|UPDATE|DELETE)\s+ON\s+\[?`?(\w+)`?\]?\s+FOR\s+EACH\s+ROW',
                _trig_hdr, s, flags=R.IGNORECASE)
            s = _convert_flow(s, src, tgt)
            # v9 패치 #40: 트리거 본문 백틱 → [대괄호] 변환 (중요: 헤더 치환 후에)
            # 이 호출이 빠져있어서 NEW.`col`, OLD.`col`, 테이블 참조 등에 백틱 남아있었음
            s = _quote(s, src, tgt)
            # 혹시 짝 안 맞는 백틱 남았으면 제거
            if '`' in s:
                s = s.replace('`', '')
            if not s.rstrip().upper().endswith('END'):
                s = s.rstrip() + '\nEND'
            drop = (f"IF OBJECT_ID(N'[dbo].[{nm}]', N'TR') IS NOT NULL DROP TRIGGER [{nm}]")
            return {"statements": [drop, s.strip()],
                    "notes": "규칙 기반 변환 — TRIGGER MySQL→MSSQL"}

        elif src in MSSQL_TYPES and tgt in MYSQL_TYPES:
            # 0. AFTER INSERT, UPDATE, DELETE → AFTER INSERT (첫 이벤트만, MySQL 단일 이벤트)
            s = R.sub(r'(AFTER|INSTEAD\s+OF)\s+(INSERT|UPDATE|DELETE)(?:\s*,\s*(?:INSERT|UPDATE|DELETE))+',
                      lambda m: m.group(1) + ' ' + m.group(2), s, flags=R.IGNORECASE)

            # 0b. FOR EACH ROW 이전 AFTER/BEFORE + 복수 이벤트 정리
            s = R.sub(r'\b(AFTER|BEFORE)\s+((?:INSERT|UPDATE|DELETE)(?:\s*,\s*(?:INSERT|UPDATE|DELETE))*)',
                      lambda m: m.group(1) + ' ' + m.group(2).split(',')[0].strip(),
                      s, flags=R.IGNORECASE)

            # 1. 헤더 치환 (반드시 _quote 전에 - [bracket] 형태 유지)
            def _trig_hdr_my(m):
                nm2 = m.group(1); tbl = m.group(2)
                timing_raw = m.group(3).upper(); ev = m.group(4).upper()
                mysql_timing = 'AFTER' if 'AFTER' in timing_raw else 'BEFORE'
                return f'CREATE TRIGGER `{nm2}`\n{mysql_timing} {ev}\nON `{tbl}`\nFOR EACH ROW\nBEGIN'
            s = R.sub(
                r'CREATE\s+(?:OR\s+ALTER\s+)?TRIGGER\s+\[?(\w+)\]?\s+ON\s+\[?(\w+)\]?\s+'
                r'(AFTER|INSTEAD\s+OF)\s+(INSERT|UPDATE|DELETE)\s*\nAS\s*\nBEGIN',
                _trig_hdr_my, s, flags=R.IGNORECASE)
            # 1b. 헤더 미변환 시 대괄호 제거
            s = R.sub(r'CREATE\s+(?:OR\s+ALTER\s+)?TRIGGER\s+\[?(\w+)\]?',
                      lambda m: f'CREATE TRIGGER `{m.group(1)}`', s, flags=R.IGNORECASE)
            s = R.sub(r'\bON\s+\[(\w+)\]', r'ON `\1`', s, flags=R.IGNORECASE)
            s = R.sub(r'\bAS\s*\n\s*BEGIN\b', 'FOR EACH ROW\nBEGIN', s, flags=R.IGNORECASE)
            # 1c. CAST(x AS VARCHAR/NVARCHAR) → CHAR (early, quote 이전에도 필요)
            s = R.sub(r'\bCAST\s*\((.+?)\s+AS\s+NVARCHAR(?:\s*\(\s*\d+\s*\))?\s*\)',
                      r'CAST(\1 AS CHAR)', s, flags=R.IGNORECASE)
            s = R.sub(r'\bCAST\s*\((.+?)\s+AS\s+VARCHAR\s*\(\s*(\d+)\s*\)\s*\)',
                      r'CAST(\1 AS CHAR(\2))', s, flags=R.IGNORECASE)
            s = R.sub(r'\bCAST\s*\((.+?)\s+AS\s+VARCHAR\s*\)',
                      r'CAST(\1 AS CHAR)', s, flags=R.IGNORECASE)
            # SYSTEM_USER (early)
            s = R.sub(r'\bSYSTEM_USER\b', 'CURRENT_USER()', s, flags=R.IGNORECASE)
            # N'str' prefix (early)
            s = R.sub(r"\bN'", "'", s)

            # 2. INSERTED.col/DELETED.col → NEW.col/OLD.col
            s = R.sub(r'\bINSERTED\.(\w+)', r'NEW.\1', s, flags=R.IGNORECASE)
            s = R.sub(r'\bDELETED\.(\w+)', r'OLD.\1', s, flags=R.IGNORECASE)
            # 3. UPDATE alias SET...FROM RealTable alias INNER JOIN inserted ON pk
            #    → UPDATE `RealTable` SET...WHERE pk=NEW.pk
            def _upd_join(m):
                real_tbl = m.group(3)   # FROM 뒤의 실제 테이블명
                set_part = m.group(2).strip()
                pk_col   = m.group(4)
                return f'UPDATE `{real_tbl}`\n    SET {set_part}\n    WHERE {pk_col} = NEW.{pk_col}'
            s = R.sub(
                r'UPDATE\s+\w+\s+'
                r'SET\s+(.+?)\s+'
                r'FROM\s+(\w+)\s+\w+\s+'
                r'INNER\s+JOIN\s+inserted\s+\w+\s+'
                r'ON\s+\w+\.(\w+)\s*=\s*\w+\.\3',
                lambda m: f'UPDATE `{m.group(2)}`\n    SET {m.group(1).strip()}\n    WHERE {m.group(3)} = NEW.{m.group(3)}',
                s, flags=R.IGNORECASE|R.DOTALL)
            # 4. 불필요한 MSSQL 구문 제거
            s = R.sub(r'\bSET\s+NOCOUNT\s+ON\s*;?', '', s, flags=R.IGNORECASE)
            s = R.sub(r'\bROLLBACK\s+TRANSACTION\b\s*;?', '', s, flags=R.IGNORECASE)
            s = R.sub(r'\bROLLBACK\b\s*;?', '', s, flags=R.IGNORECASE)
            # 5. IF EXISTS (SELECT * FROM inserted WHERE ...) → IF NEW.col THEN
            #    반드시 FROM inserted 제거 전에 실행
            def _if_exists(m):
                cond = m.group(1).strip()
                # 예약어가 아닌 단어 앞에 NEW. 추가
                SKIP = {'AND','OR','NOT','NULL','IS','LIKE','IN','BETWEEN','TRUE','FALSE'}
                def _add_prefix(mm):
                    word = mm.group(1)
                    return word if word.upper() in SKIP else f'NEW.{word}'
                cond = R.sub(r'\b([A-Za-z_]\w*)\b(?!\s*\.)', _add_prefix, cond)
                # NEW.NEW.xxx 중복 방지
                cond = R.sub(r'\bNEW\.NEW\.', 'NEW.', cond)
                return f'IF {cond} THEN'
            s = R.sub(
                r'IF\s+EXISTS\s*\(\s*SELECT\s+\*\s+FROM\s+(?:inserted|NEW_TABLE)\s+WHERE\s+([^)]+)\)\s*(?:\n?\s*BEGIN)?',
                _if_exists, s, flags=R.IGNORECASE)
            # 6. SELECT...FROM deleted → OLD.col 또는 그대로 (DELETE 트리거)
            # SELECT col1, col2 FROM deleted → SELECT OLD.col1, OLD.col2
            def _sel_from_del(m):
                sel = m.group(1).strip()
                # 문자열 연결이 포함된 경우 (SELECT '...' + col FROM deleted)
                # → INSERT ... VALUES (CONCAT('...', OLD.col)) 형태로 변환
                parts = [p.strip() for p in sel.split('+')]
                new_parts = []
                for p in parts:
                    if p.startswith("'") or p.startswith('"'):
                        new_parts.append(p)
                    elif R.match(r'^[A-Za-z_]\w*$', p):
                        new_parts.append(f'OLD.{p}')
                    else:
                        new_parts.append(p)
                if len(new_parts) > 1:
                    return 'CONCAT(' + ', '.join(new_parts) + ')'
                return new_parts[0] if new_parts else sel
            # INSERT INTO tbl (cols) SELECT expr FROM deleted
            # → INSERT INTO tbl (cols) VALUES (CONCAT(...)) or SELECT OLD.col
            def _fix_insert_select_deleted(m):
                insert_prefix = m.group(1)   # INSERT INTO tbl (cols)
                select_expr   = m.group(2).strip()
                result_expr   = _sel_from_del(type('M', (), {'group': lambda self, n: select_expr})())
                if result_expr.startswith('CONCAT(') or 'OLD.' in result_expr:
                    return f"{insert_prefix}\n    VALUES ({result_expr})"
                return f"{insert_prefix}\n    SELECT {result_expr}"
            s = R.sub(
                r'(INSERT\s+INTO\s+\S+\s*(?:\([^)]*\))?)'  # INSERT INTO tbl (cols)
                r'\s*\n?\s*SELECT\s+(.+?)\s+FROM\s+deleted\b',
                _fix_insert_select_deleted, s, flags=R.IGNORECASE|R.DOTALL)
            s = R.sub(r'SELECT\s+(.+?)\s+FROM\s+deleted\b',
                      lambda m: _sel_from_del(m), s, flags=R.IGNORECASE|R.DOTALL)
            s = R.sub(r'\bFROM\s+deleted\b', '', s, flags=R.IGNORECASE)
            s = R.sub(r'\bFROM\s+inserted\b', '', s, flags=R.IGNORECASE)

            # ── 추가 변환 규칙 (누적) ──────────────────────────────

            # R01. UPDATE alias SET...FROM tbl [JOIN INSERTED/DELETED ON pk]
            # → MySQL: UPDATE tbl SET...WHERE pk=NEW.pk
            def _fix_upd_from(m):
                full = m.group(0)
                # SET 절 추출
                set_m = R.search(r'SET\s+([\s\S]+?)\s+FROM\s+', full, R.IGNORECASE)
                if not set_m:
                    return full
                set_blk = set_m.group(1).strip()
                # FROM 뒤 실제 테이블
                from_m = R.search(r'FROM\s+`?(\w+)`?', full, R.IGNORECASE)
                tbl = from_m.group(1) if from_m else 'unknown_tbl'
                # WHERE 절 (JOIN 이후)
                where_m = R.search(r'WHERE\s+([\s\S]+?)$', full, R.IGNORECASE | R.DOTALL)
                where_str = where_m.group(1).strip() if where_m else ''
                # SET 내 alias.col → col 정리
                set_clean = R.sub(r'\b[a-z]\.([\w`]+)', r'`\1`', set_blk, flags=R.IGNORECASE)
                # i.col→NEW.col, d.col→OLD.col 이미 변환됨
                if where_str:
                    return 'UPDATE `{}`\n    SET {}\n    WHERE {}'.format(tbl, set_clean, where_str)
                else:
                    return 'UPDATE `{}`\n    SET {}\n    WHERE `loan_id` = NEW.`loan_id`'.format(tbl, set_clean)
            # FROM tbl JOIN 패턴
            s = R.sub(
                r'UPDATE\s+\w+\s+SET\s+[\s\S]+?FROM\s+`?\w+`?\s+\w+\s+(?:(?:INNER|LEFT|RIGHT)\s+)?'
                r'JOIN\s+(?:INSERTED|DELETED|NEW|OLD)\s+\w+\s+ON\s+[\s\S]+?(?=\n\s*(?:END|IF|INSERT|UPDATE|SELECT|;)|\Z)',
                _fix_upd_from, s, flags=R.IGNORECASE | R.DOTALL)
            # FROM tbl 단독 패턴 (JOIN 없음)
            s = R.sub(
                r'UPDATE\s+\w+\s+SET\s+([\s\S]+?)FROM\s+`?(\w+)`?\s+\w+\s*\n\s*(WHERE[\s\S]+?)(?=\n\s*(?:END|IF|INSERT|UPDATE|;)|\Z)',
                lambda m: 'UPDATE `{}`\n    SET {}\n    {}'.format(
                    m.group(2),
                    R.sub(r'\b[a-z]\.(`?\w+`?)', r'\1', m.group(1).strip(), flags=R.IGNORECASE),
                    m.group(3).strip()),
                s, flags=R.IGNORECASE | R.DOTALL)

            # R02. UPDATE alias SET...FROM tbl WHERE (별칭만 남은 경우)
            # "UPDATE `tbl` SET col=val\n    FROM `tbl` alias\n WHERE..."
            s = R.sub(
                r'\n\s+FROM\s+`\w+`\s+\w*\s*\n',
                '\n',
                s, flags=R.IGNORECASE)

            # R03. WHERE col IN (SELECT col FROM INSERTED) → WHERE col = NEW.col
            s = R.sub(
                r'WHERE\s+`?(\w+)`?\s+IN\s*\(\s*`?\1`?\s*\)',
                r'WHERE `\1` = NEW.`\1`', s, flags=R.IGNORECASE)
            s = R.sub(
                r'WHERE\s+`?(\w+)`?\s+IN\s*\(\s*SELECT\s+`?\1`?\s+FROM\s+(?:INSERTED|NEW)\s*\)',
                r'WHERE `\1` = NEW.`\1`', s, flags=R.IGNORECASE)
            s = R.sub(
                r'WHERE\s+`?(\w+)`?\s+IN\s*\(\s*SELECT\s+`?\1`?\s+FROM\s+(?:DELETED|OLD)\s*\)',
                r'WHERE `\1` = OLD.`\1`', s, flags=R.IGNORECASE)

            # R04. IF UPDATE(col) → IF NEW.col <> OLD.col
            s = R.sub(r'\bIF\s+UPDATE\s*\(\s*`?(\w+)`?\s*\)',
                      r'IF NEW.`\1` <> OLD.`\1`', s, flags=R.IGNORECASE)

            # R05. N'...' + CAST(col AS VARCHAR) 연결 → CONCAT(...)
            # NCONCAT 오류 수정 + 기존 잘못된 변환 복구
            s = R.sub(r'\bNCONCAT\s*\(', 'CONCAT(', s, flags=R.IGNORECASE)
            # CONCAT('str', val).col 잘못된 패턴 수정
            s = R.sub(r'CONCAT\(([^)]+)\)\.`?(\w+)`?', r"CONCAT(\1, NEW.`\2`)", s, flags=R.IGNORECASE)

            # R06. 문자열 + 연결 → CONCAT (SELECT 결과 리스트 내)
            s = R.sub(r"\\bN'", "'", s)  # N'' prefix 선제거
            # 'str' + col + 'str' 패턴만 (CONCAT으로 안된 잔재)
            def _plus_to_concat(m):
                raw = m.group(0)
                if raw.upper().startswith('CONCAT('):
                    return raw
                raw = R.sub(r"\\bN'", "'", raw)
                parts = [p.strip() for p in R.split(r'\s*\+\s*', raw)]
                if len(parts) < 2:
                    return raw
                return 'CONCAT(' + ', '.join(parts) + ')'
            s = R.sub(
                r"(?:N?'[^']*'|`?\w+`?(?:\.\w+)?|CAST\([^)]+\))\s*"
                r"(?:\+\s*(?:N?'[^']*'|`?\w+`?(?:\.\w+)?|CAST\([^)]+\))){1,}",
                _plus_to_concat, s)

            # R07. CAST(x AS VARCHAR(N)) / CAST(x AS VARCHAR) → CHAR
            s = R.sub(r'\bCAST\s*\((.+?)\s+AS\s+NVARCHAR(?:\s*\(\s*\d+\s*\))?\s*\)',
                      r'CAST(\1 AS CHAR)', s, flags=R.IGNORECASE)
            s = R.sub(r'\bCAST\s*\((.+?)\s+AS\s+VARCHAR\s*\(\s*(\d+)\s*\)\s*\)',
                      r'CAST(\1 AS CHAR(\2))', s, flags=R.IGNORECASE)
            s = R.sub(r'\bCAST\s*\((.+?)\s+AS\s+VARCHAR\s*\)',
                      r'CAST(\1 AS CHAR)', s, flags=R.IGNORECASE)

            # R08. SYSTEM_USER → CURRENT_USER()
            s = R.sub(r'\bSYSTEM_USER\b', 'CURRENT_USER()', s, flags=R.IGNORECASE)

            # R09. RETURN; 단독 → 제거
            s = R.sub(r'^\s*RETURN\s*;?\s*$', '', s, flags=R.IGNORECASE | R.MULTILINE)

            # R10. 잔재 FROM INSERTED/DELETED/JOIN 제거
            s = R.sub(r'\bJOIN\s+(?:INSERTED|DELETED)\s+\w+\s+ON\s+[^\n]+', '', s, flags=R.IGNORECASE)
            s = R.sub(r'\bFULL\s+OUTER\s+JOIN\s+\w+\s+\w+\s+ON\s+[^\n]+', '', s, flags=R.IGNORECASE)
            s = R.sub(r'\bFROM\s+(?:INSERTED|DELETED)\s+\w+', '', s, flags=R.IGNORECASE)
            s = R.sub(r'\bJOIN\s+(?:INSERTED|DELETED)\b[^\n]*', '', s, flags=R.IGNORECASE)

            # R11. NEWID() → UUID()
            s = R.sub(r'\bNEWID\s*\(\s*\)', 'UUID()', s, flags=R.IGNORECASE)

            # R12. N'...' prefix 잔재 제거
            s = R.sub(r"\bN'", "'", s)

            # R13. IF EXISTS (1 d WHERE...) 또는 IF EXISTS (1 WHERE...) → IF OLD.col 조건
            # EXISTS 내부에 SELECT 없는 잔재 → 제거
            s = R.sub(r'IF\s+EXISTS\s*\(\s*1\s+\w*\s*(?:WHERE\s+[^)]+)?\)', 'IF TRUE', s, flags=R.IGNORECASE)

            # R14. 고아 SELECT 잔재 줄 제거 (별칭 단독 줄)
            s = R.sub(r'^\s{4,}\b[a-z]\s*$', '', s, flags=R.MULTILINE)

            # R15. DECLARE @var → DECLARE var
            s = R.sub(r'\bDECLARE\s+@(\w+)\b', r'DECLARE \1', s, flags=R.IGNORECASE)

            # R16. UPDATE tbl SET col=val\n    WHERE pk IN (pk) → WHERE pk = NEW.pk
            # TRG09 패턴: WHERE `appl_id` IN (`appl_id`) → WHERE `appl_id` = OLD.`appl_id`
            s = R.sub(r'WHERE\s+(`?\w+`?)\s+IN\s*\(\s*\1\s*\)',
                      r'WHERE \1 = OLD.\1', s, flags=R.IGNORECASE)

            # R17. MySQL 트리거: UPDATE 같은 테이블 자기 참조 불가
            # BEFORE DELETE 트리거에서 같은 테이블 UPDATE → SET NEW.col = val 방식으로
            # (이건 케이스별로 처리가 복잡하므로 일단 주석 처리)

            # R18. i.`col`, d.`col` 잔재 → NEW.`col`, OLD.`col`
            s = R.sub(r'\bi\.`(\w+)`', r'NEW.`\1`', s, flags=R.IGNORECASE)
            s = R.sub(r'\bd\.`(\w+)`', r'OLD.`\1`', s, flags=R.IGNORECASE)
            s = R.sub(r'\bi\.(\w+)\b', r'NEW.\1', s, flags=R.IGNORECASE)
            s = R.sub(r'\bd\.(\w+)\b', r'OLD.\1', s, flags=R.IGNORECASE)

            # ── 추가 변환 규칙 끝 ──────────────────────────────────
            # 7. quote/type 변환 (헤더 치환 후)
            s = _quote(s, src, tgt)
            s = _convert_types(s, src, tgt)
            # 8. RAISERROR → SIGNAL (중복 세미콜론 방지)
            def _raiserr(m):
                msg = m.group(1)
                return f"SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='{msg}'"
            s = R.sub(r"RAISERROR\s*\(\s*N?'([^']+)'\s*,\s*\d+\s*,\s*\d+\s*\)",
                      _raiserr, s, flags=R.IGNORECASE)
            # 9. IF...BEGIN → IF...THEN
            s = R.sub(r'\bIF\s+(.+?)\s+BEGIN\b', r'IF \1 THEN', s, flags=R.IGNORECASE)
            s = R.sub(r'\bELSE\s+BEGIN\b', 'ELSE', s, flags=R.IGNORECASE)
            # 10. END 처리: 마지막 END 보존, 나머지 END → END IF;
            lines = s.split('\n')
            result = []
            for i, line in enumerate(lines):
                if line.strip().rstrip(';').upper() == 'END':
                    remaining = [l.strip() for l in lines[i+1:] if l.strip()]
                    result.append(line if not remaining else '    END IF;')
                else:
                    result.append(line)
            s = '\n'.join(result)
            # 11. 이중 세미콜론 정리
            s = R.sub(r';{2,}', ';', s)
            # 12. 빈 줄 정리
            s = R.sub(r'\n{3,}', '\n\n', s)
            drop = f"DROP TRIGGER IF EXISTS `{nm}`"
            logger.info("[%s] TRIGGER → MySQL DROP+CREATE 분리", obj_name)
            return {"statements": [drop, s.strip()],
                    "notes": "규칙 기반 변환 — TRIGGER MSSQL→MySQL"}
        else:
            return {"statements": [s.strip()], "notes": f"부분 변환 — {src}→{tgt}"}

    # 기타 오브젝트 타입
    logger.info("[%s] %s 기본 변환 (%s→%s)", obj_name, obj_type, src, tgt)
    return {"statements": [s.strip()], "notes": f"기본 변환 — {src}→{tgt}"}





# ══════════════════════════════════════════════════════════════════════
# 데이터 미리보기 API  GET /{cid}/tables/{table}/preview
# ══════════════════════════════════════════════════════════════════════

def _mysql_preview(h, p, u, pw, db, tbl, limit=20):
    """MySQL 테이블 상위 N행 반환"""
    import pymysql
    conn = pymysql.connect(
        host=h, port=int(p), user=u, password=pw,
        database=db, charset="utf8mb4", connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor, autocommit=True
    )
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM `{tbl}` LIMIT %s", (int(limit),))
        rows = cur.fetchall()
        # datetime 등 직렬화 불가 타입 → str 변환
        safe_rows = []
        for row in rows:
            safe_rows.append({
                k: (str(v) if not isinstance(v, (int, float, str, bool, type(None))) else v)
                for k, v in row.items()
            })
        cols = [d[0] for d in cur.description] if cur.description else []
        return {"columns": cols, "rows": safe_rows}
    finally:
        conn.close()


def _mssql_columns(h, p, u, pw, db, tbl):
    """MSSQL 테이블 컬럼 상세 조회"""
    from app.core.db_conn import make_mssql_conn
    conn = make_mssql_conn(h, p, u, pw, db)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                c.name            AS COLUMN_NAME,
                tp.name           AS DATA_TYPE,
                c.max_length      AS CHARACTER_MAXIMUM_LENGTH,
                c.precision       AS NUMERIC_PRECISION,
                c.scale           AS NUMERIC_SCALE,
                CASE WHEN c.is_nullable=1 THEN 'YES' ELSE 'NO' END AS IS_NULLABLE,
                dc.definition     AS COLUMN_DEFAULT,
                CASE WHEN ic.column_id IS NOT NULL THEN 'PRI' ELSE '' END AS COLUMN_KEY,
                CASE WHEN c.is_identity=1 THEN 'auto_increment' ELSE '' END AS EXTRA,
                ''                AS COLUMN_COMMENT
            FROM sys.columns c
            JOIN sys.types   tp ON c.user_type_id = tp.user_type_id
            JOIN sys.tables  t  ON c.object_id    = t.object_id
            LEFT JOIN sys.default_constraints dc ON c.default_object_id = dc.object_id
            LEFT JOIN sys.index_columns ic
                ON ic.object_id = c.object_id
               AND ic.column_id = c.column_id
               AND ic.index_id  = 1
            WHERE t.name = ?
            ORDER BY c.column_id
        """, [tbl])
        rows = cur.fetchall()
        keys = [d[0] for d in cur.description]
        result = []
        for r in rows:
            row = dict(zip(keys, r))
            result.append({
                "name":        row["COLUMN_NAME"],
                "data_type":   row["DATA_TYPE"],
                "length":      row["CHARACTER_MAXIMUM_LENGTH"],
                "precision":   row["NUMERIC_PRECISION"],
                "scale":       row["NUMERIC_SCALE"],
                "nullable":    row["IS_NULLABLE"] == "YES",
                "default":     row["COLUMN_DEFAULT"],
                "is_pk":       row["COLUMN_KEY"] == "PRI",
                "is_identity": "auto_increment" in (row["EXTRA"] or ""),
                "comment":     row["COLUMN_COMMENT"] or "",
                "COLUMN_KEY":  row["COLUMN_KEY"],
                "IS_NULLABLE": row["IS_NULLABLE"],
                "CHARACTER_MAXIMUM_LENGTH": row["CHARACTER_MAXIMUM_LENGTH"],
            })
        return result
    finally:
        conn.close()


def _mssql_preview(h, p, u, pw, db, tbl, limit=20):
    """MSSQL 테이블 상위 N행 반환"""
    from app.core.db_conn import make_mssql_conn
    conn = make_mssql_conn(h, p, u, pw, db)
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT TOP {int(limit)} * FROM [{tbl}]")
        keys = [d[0] for d in cur.description]
        rows = []
        for r in cur.fetchall():
            rows.append({
                k: (str(v) if not isinstance(v, (int, float, str, bool, type(None))) else v)
                for k, v in zip(keys, r)
            })
        return {"columns": keys, "rows": rows}
    finally:
        conn.close()


@router.get("/{cid}/tables/{table}/preview")
def table_preview(
    cid: str, table: str,
    db_type: str = "", host: str = "", port: int = 3306,
    username: str = "", password: str = "", database: str = "",
    limit: int = 20,
):
    """
    테이블 데이터 미리보기 — 상위 N행 반환
    Schema.vue 의 '데이터 미리보기' 탭에서 호출
    """
    # 연결 정보 우선순위: 쿼리 파라미터 > 저장된 cid 세션
    saved = _conns.get(cid) or _conns.get("source") or {}
    c = {
        "db_type":  db_type  or saved.get("db_type",  "mysql"),
        "host":     host     or saved.get("host",     ""),
        "port":     port     or saved.get("port",     3306),
        "username": username or saved.get("username", ""),
        "password": password or saved.get("password", ""),
        "database": database or saved.get("database", ""),
    }
    if not c["host"] or not c["database"]:
        return {"columns": [], "rows": [], "error": "연결 정보 부족"}

    limit = max(1, min(int(limit), 200))   # 최대 200행으로 제한

    try:
        dt = c["db_type"]
        h, p, u, pw, db = c["host"], int(c["port"]), c["username"], c["password"], c["database"]
        if dt in ("mysql", "aurora", "cloudsql", "tidb", "mariadb"):
            return _mysql_preview(h, p, u, pw, db, table, limit)
        elif dt in ("mssql", "azure", "sqlserver"):
            return _mssql_preview(h, p, u, pw, db, table, limit)
        else:
            return {"columns": [], "rows": [], "error": f"{dt} 미리보기 미지원"}
    except Exception as e:
        raise HTTPException(500, f"미리보기 조회 실패: {e}")


# ── GET /{cid}/tables/{table} MSSQL 지원 강화 ──────────────────────

@router.get("/{cid}/tables/{table}/columns")
def get_columns_full(
    cid: str, table: str,
    db_type: str = "", host: str = "", port: int = 3306,
    username: str = "", password: str = "", database: str = "",
):
    """
    컬럼 상세 조회 — MySQL / MSSQL 모두 지원
    Schema.vue 가 /columns 경로로 호출 (미래 확장용)
    """
    saved = _conns.get(cid) or _conns.get("source") or {}
    c = {
        "db_type":  db_type  or saved.get("db_type",  "mysql"),
        "host":     host     or saved.get("host",     ""),
        "port":     port     or saved.get("port",     3306),
        "username": username or saved.get("username", ""),
        "password": password or saved.get("password", ""),
        "database": database or saved.get("database", ""),
    }
    if not c["host"] or not c["database"]:
        return _mock_detail(table)

    try:
        dt = c["db_type"]
        h, p, u, pw, db = c["host"], int(c["port"]), c["username"], c["password"], c["database"]
        if dt in ("mysql", "aurora", "cloudsql", "tidb", "mariadb"):
            cols = _mysql_columns(h, p, u, pw, db, table)
        elif dt in ("mssql", "azure", "sqlserver"):
            cols = _mssql_columns(h, p, u, pw, db, table)
        else:
            return _mock_detail(table)
        return {
            "schema":       db,
            "name":         table,
            "columns":      cols,
            "primary_keys": [col["name"] for col in cols if col.get("is_pk")],
        }
    except Exception as e:
        raise HTTPException(500, str(e))
