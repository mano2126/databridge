"""
app/api/routes/schema.py  — 실제 DB 테이블/컬럼 조회 + 타입 경고 분석
"""
from fastapi import APIRouter, HTTPException
from app.core.db_conn import make_mssql_conn, get_port, default_port

router = APIRouter()
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
    if not c["host"] or not c["database"]:
        return _mock_detail(table)
    try:
        dt = c["db_type"]
        h,p,u,pw,db = c["host"],int(c["port"]),c["username"],c["password"],c["database"]
        if dt in ("mysql","aurora","cloudsql","tidb","mariadb"):
            cols = _mysql_columns(h,p,u,pw,db,table)
            return {"schema":db,"name":table,"columns":cols,
                    "primary_keys":[col["name"] for col in cols if col["is_pk"]]}
        return _mock_detail(table)
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
    if not c["host"] or not c["database"]:
        return _mock_detail(table)
    try:
        if c["db_type"] in ("mysql","aurora","cloudsql","tidb"):
            cols = _mysql_columns(c["host"], c["port"], c["username"], c["password"], c["database"], table)
            return {"schema": c["database"], "name": table, "columns": cols,
                    "primary_keys": [col["name"] for col in cols if col["is_pk"]]}
        return _mock_detail(table)
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
    """MSSQL 오브젝트 목록 — db_conn 사용 (Encrypt=no 제거)"""
    from app.core.db_conn import make_mssql_conn
    conn = make_mssql_conn(h, p, u, pw, db)
    result = {}
    try:
        cur = conn.cursor()
        # 프로시저
        cur.execute("""SELECT o.name, o.create_date, o.modify_date, m.definition
                       FROM sys.objects o LEFT JOIN sys.sql_modules m ON o.object_id=m.object_id
                       WHERE o.type='P' ORDER BY o.name""")
        result["procedures"] = [{"name":r[0],"type":"PROCEDURE","created":str(r[1]),"body":r[3] or ""} for r in cur.fetchall()]
        # 함수
        cur.execute("""SELECT o.name, o.create_date, m.definition
                       FROM sys.objects o LEFT JOIN sys.sql_modules m ON o.object_id=m.object_id
                       WHERE o.type IN ('FN','IF','TF') ORDER BY o.name""")
        result["functions"] = [{"name":r[0],"type":"FUNCTION","created":str(r[1]),"body":r[2] or ""} for r in cur.fetchall()]
        # 트리거
        cur.execute("""SELECT t.name, o.name AS tbl, m.definition
                       FROM sys.triggers t JOIN sys.objects o ON t.parent_id=o.object_id
                       LEFT JOIN sys.sql_modules m ON t.object_id=m.object_id""")
        result["triggers"] = [{"name":r[0],"type":"TRIGGER","table":r[1],"body":r[2] or ""} for r in cur.fetchall()]
        # 뷰
        cur.execute("""SELECT o.name, m.definition FROM sys.views o
                       LEFT JOIN sys.sql_modules m ON o.object_id=m.object_id ORDER BY o.name""")
        result["views"] = [{"name":r[0],"type":"VIEW","body":r[1] or ""} for r in cur.fetchall()]
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


@router.post("/convert-object")
def convert_object(body: dict):
    """단일 오브젝트 DDL을 타겟 DB 방언으로 변환"""
    import re
    obj_type = body.get("type","PROCEDURE")
    obj_name = body.get("name","")
    body_sql = body.get("body","")
    src_db   = body.get("src_db","mysql")
    tgt_db   = body.get("tgt_db","mssql")

    converted = body_sql
    changes   = []
    warnings  = []

    if src_db == "mysql" and tgt_db == "mssql":
        # 기본 MySQL → MSSQL 변환
        rules = [
            (r'`([^`]+)`',           r'[\1]',          '백틱→대괄호'),
            (r'\bVARCHAR\b',         'NVARCHAR',        'VARCHAR→NVARCHAR'),
            (r'\bINT\b',             'INT',             'INT OK'),
            (r'\bDATETIME\b',        'DATETIME2(6)',     'DATETIME→DATETIME2'),
            (r'\bNOW\(\)',           'GETDATE()',        'NOW()→GETDATE()'),
            (r'\bIFNULL\s*\(',      'ISNULL(',         'IFNULL→ISNULL'),
            (r'\bLIMIT\s+(\d+)',    r'/* LIMIT \1 → TOP \1 */', 'LIMIT→TOP'),
            (r'\bCURRENT_TIMESTAMP\b','GETDATE()',      'CURRENT_TIMESTAMP→GETDATE()'),
        ]
        if obj_type == "PROCEDURE":
            converted = re.sub(r'CREATE\s+PROCEDURE\s+`?(\w+)`?',
                               r'CREATE OR ALTER PROCEDURE [\1]', converted, flags=re.IGNORECASE)
            changes.append("CREATE PROCEDURE → CREATE OR ALTER PROCEDURE")
            converted = re.sub(r'\bBEGIN\b', 'BEGIN', converted, flags=re.IGNORECASE)
        elif obj_type == "FUNCTION":
            converted = re.sub(r'CREATE\s+FUNCTION\s+`?(\w+)`?',
                               r'CREATE OR ALTER FUNCTION [\1]', converted, flags=re.IGNORECASE)
            changes.append("CREATE FUNCTION → CREATE OR ALTER FUNCTION")
        elif obj_type == "TRIGGER":
            warnings.append("트리거는 문법이 크게 달라 수동 검토 필요")
            converted = re.sub(r'CREATE\s+TRIGGER\s+`?(\w+)`?',
                               r'CREATE OR ALTER TRIGGER [\1]', converted, flags=re.IGNORECASE)
        elif obj_type == "VIEW":
            converted = re.sub(r'CREATE\s+(OR\s+REPLACE\s+)?VIEW\s+`?(\w+)`?',
                               r'CREATE OR ALTER VIEW [\2]', converted, flags=re.IGNORECASE)

        for pattern, replacement, desc in rules:
            new, cnt = re.subn(pattern, replacement, converted, flags=re.IGNORECASE)
            if cnt > 0:
                converted = new
                changes.append(f"{desc} ({cnt}건)")

    return {"converted": converted, "changes": changes, "warnings": warnings,
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
    c = body
    start = _time.monotonic()

    # CHECK_EXISTS: 오브젝트 존재 여부 확인
    if obj_type == "CHECK_EXISTS":
        obj_name_check = body.get("obj_name","")
        try:
            if db_type in ("mysql","aurora","cloudsql","tidb","mariadb"):
                import pymysql
                conn = pymysql.connect(host=c["host"],port=int(c["port"]),
                    user=c["username"],password=c.get("password",""),
                    database=c["database"],charset="utf8mb4",connect_timeout=8,
                    cursorclass=pymysql.cursors.DictCursor)
                try:
                    cur = conn.cursor()
                    cur.execute("""SELECT ROUTINE_NAME FROM information_schema.ROUTINES
                        WHERE ROUTINE_SCHEMA=%s AND ROUTINE_NAME=%s
                        UNION SELECT TABLE_NAME FROM information_schema.VIEWS
                        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
                        UNION SELECT TRIGGER_NAME FROM information_schema.TRIGGERS
                        WHERE TRIGGER_SCHEMA=%s AND TRIGGER_NAME=%s""",
                        (c["database"],obj_name_check)*3)
                    rows = cur.fetchall()
                    return {"success":True,"rows":rows,"exists":len(rows)>0}
                finally: conn.close()
            elif db_type in ("mssql","azure"):
                from app.core.db_conn import make_mssql_conn as _ms_c
                conn = _ms_c(c['host'], c['port'], c['username'], c.get('password',''), c['database'])
                try:
                    cur=conn.cursor()
                    cur.execute("SELECT name FROM sys.objects WHERE name=? AND type IN ('P','FN','IF','TF','TR','V')", (obj_name_check,))
                    rows=[{"name":r[0]} for r in cur.fetchall()]
                    return {"success":True,"rows":rows,"exists":len(rows)>0}
                finally: conn.close()
        except Exception as e:
            return {"success":False,"rows":[],"exists":False,"error":str(e)}

    # DDL_CREATE: 프론트엔드 AI가 변환한 MSSQL SQL을 실행
    # (AI 변환은 브라우저에서 Anthropic API 호출로 수행 — API 키 자동 주입)
    if obj_type == "DDL_CREATE":
        import logging as _lg
        _log = _lg.getLogger("databridge.schema")
        obj_name_c  = body.get("obj_name", "")
        obj_type_c  = body.get("obj_sub_type", "PROCEDURE").upper()

        # 프론트엔드가 AI 변환한 statements 배열을 전달
        # statements: 실행할 MSSQL SQL 문장 배열
        # ddl: 원본 MySQL DDL (fallback용)
        statements  = body.get("statements", [])
        original_ddl = body.get("ddl", "")
        notes       = body.get("notes", "")

        if not statements:
            _log.error("DDL_CREATE [%s]: statements 없음", obj_name_c)
            return {"success": False, "error": "변환된 SQL statements가 없습니다. 프론트엔드 AI 변환을 확인하세요.", "rows": []}

        _log.info("DDL_CREATE [%s] %s: %d개 문장 실행", obj_name_c, obj_type_c, len(statements))
        for i, st in enumerate(statements):
            _log.debug("  [%d] %s", i+1, st[:150])

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
                            _log.info("  ✓ [%d] %s...", i+1, stmt[:60])
                        except Exception as e:
                            _log.error("  ✗ [%d] %s | 오류: %s", i+1, stmt[:80], e)
                            errors.append({"stmt": stmt[:120], "error": str(e)})
                            try: conn.rollback()
                            except: pass

                    if executed and not errors:
                        _log.info("DDL_CREATE [%s] 완전 성공 (%d문장)", obj_name_c, len(executed))
                        return {"success": True, "rows": [],
                                "output": f"{obj_name_c} 생성 완료 ({len(executed)}문장)",
                                "notes": notes, "executed": executed}
                    elif executed:
                        _log.warning("DDL_CREATE [%s] 부분 성공 (%d/%d)", obj_name_c, len(executed), len(executed)+len(errors))
                        return {"success": True, "rows": [],
                                "output": f"{obj_name_c} 부분 성공 ({len(executed)}/{len(executed)+len(errors)})",
                                "notes": notes, "warnings": [e["error"] for e in errors]}
                    else:
                        err = "; ".join(e["error"] for e in errors[:3])
                        _log.error("DDL_CREATE [%s] 전체 실패: %s", obj_name_c, err)
                        return {"success": False, "error": err, "rows": [], "notes": notes, "errors": errors}
                finally:
                    conn.close()

            elif db_type in ("mysql","aurora","cloudsql","tidb","mariadb"):
                import pymysql
                from pymysql.constants import CLIENT
                conn = pymysql.connect(
                    host=c["host"], port=int(c["port"]),
                    user=c["username"], password=c.get("password",""),
                    database=c["database"], charset="utf8mb4",
                    connect_timeout=10,
                    client_flag=CLIENT.MULTI_STATEMENTS
                )
                try:
                    cur = conn.cursor()
                    obj_sub = body.get("obj_sub_type","").upper()
                    stmts_to_run = statements if statements else [original_ddl]
                    executed = []
                    for stmt in stmts_to_run:
                        stmt = stmt.strip()
                        if not stmt:
                            continue
                        if obj_sub in ("PROCEDURE","FUNCTION","TRIGGER","EVENT"):
                            import re as _re
                            # DELIMITER 라인 제거
                            clean = _re.sub(r"(?im)^DELIMITER\s+\S+\s*$", "", stmt).strip()
                            # 끝의 // $$ 구분자 제거
                            clean = _re.sub(r"[\$\/]{2}\s*$", "", clean).strip()
                            # END로 끝나면 ; 추가
                            if clean and not clean.rstrip().endswith(";"):
                                clean += ";"
                            if not clean:
                                continue
                            # connection.query()로 직접 전송 (복합문 지원)
                            conn.query(clean)
                            try:
                                while conn.next_result():
                                    pass
                            except Exception:
                                pass
                        else:
                            for sub in [s.strip() for s in stmt.split(";") if s.strip()]:
                                cur.execute(sub)
                        executed.append(stmt[:40])
                        _log.debug("DDL_CREATE MySQL [%s] 문장 실행: %s...", obj_name_c, stmt[:60])
                    _log.info("DDL_CREATE MySQL [%s] 완료 (%d문장)", obj_name_c, len(executed))
                    return {"success": True, "rows": [], "output": f"{obj_name_c} 생성 완료 ({len(executed)}문장)"}
                except Exception as e:
                    _log.error("DDL_CREATE MySQL [%s] 실패: %s", obj_name_c, e)
                    return {"success": False, "error": str(e), "rows": []}
                finally:
                    conn.close()

            return {"success": False, "error": f"{db_type} DDL_CREATE 미지원", "rows": []}
        except Exception as e:
            _log.error("DDL_CREATE 연결 오류 [%s]: %s", obj_name_c, e)
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
                    placeholders = ",".join(["%s"]*len(params)) if params else ""
                    cur.callproc(obj_name, params)
                    rows = []
                    for result in cur.stored_results():
                        rows = result.fetchall()
                elif obj_type == "FUNCTION":
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
            conn = _ms_c(c['host'], c['port'], c['username'], c.get('password',''), c['database'])
            try:
                cur = conn.cursor()
                if obj_type == "PROCEDURE":
                    ph = ",".join(["?"]*len(params)) if params else ""
                    cur.execute(f"EXEC [{obj_name}] {ph}", params or [])
                    try:
                        cols = [d[0] for d in cur.description]
                        rows = [dict(zip(cols,row)) for row in cur.fetchmany(50)]
                    except Exception:
                        rows = []
                elif obj_type == "FUNCTION":
                    ph = ",".join(["?"]*len(params)) if params else ""
                    cur.execute(f"SELECT [{obj_name}]({ph}) AS result", params or [])
                    cols = [d[0] for d in cur.description]
                    rows = [dict(zip(cols,row)) for row in cur.fetchall()]
                elif obj_type == "VIEW":
                    cur.execute(f"SELECT TOP 50 * FROM [{obj_name}]")
                    cols = [d[0] for d in cur.description]
                    rows = [dict(zip(cols,row)) for row in cur.fetchall()]
                else:
                    rows = []
                elapsed = round((_time.monotonic()-start)*1000, 1)
                return {"success":True,"rows":rows,"elapsed":elapsed}
            finally:
                conn.close()

        return {"success":False,"error":f"{db_type} 실행 미지원","rows":[]}
    except Exception as e:
        return {"success":False,"error":str(e),"rows":[],
                "elapsed":round((_time.monotonic()-start)*1000,1)}


@router.get("/objects/ddl")
def get_object_ddl(
    db_type: str = "", host: str = "", port: int = 3306,
    username: str = "", password: str = "", database: str = "",
    obj_type: str = "PROCEDURE", obj_name: str = ""
):
    """오브젝트 DDL 단건 조회"""
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
                if ot in ("PROCEDURE","FUNCTION"):
                    cur.execute(f"SELECT OBJECT_DEFINITION(OBJECT_ID(?))", [obj_name])
                    row = cur.fetchone()
                    ddl = row[0] if row and row[0] else ""
                elif ot == "TRIGGER":
                    cur.execute(f"SELECT OBJECT_DEFINITION(OBJECT_ID(?))", [obj_name])
                    row = cur.fetchone()
                    ddl = row[0] if row and row[0] else ""
                elif ot == "VIEW":
                    cur.execute(f"SELECT OBJECT_DEFINITION(OBJECT_ID(?))", [obj_name])
                    row = cur.fetchone()
                    ddl = row[0] if row and row[0] else ""
                else:
                    ddl = ""
            finally:
                conn.close()
        else:
            ddl = f"-- {db_type} DDL 조회 미지원"
        return {"ddl": ddl or f"-- {obj_name} DDL을 가져올 수 없습니다", "obj_type": obj_type, "obj_name": obj_name}
    except Exception as e:
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
                    cur.callproc(obj_name, params)
                    rows = []
                    for rs in cur.stored_results():
                        rows = rs.fetchall()
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
        _log.info("[%s] %s — 규칙 기반 변환", obj_name, "force_rule" if force_rule else "API 키 없음")
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
            "model": "claude-sonnet-4-20250514",
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
        _log.info("AI 변환 성공 [%s]", obj_name)
        return result
    except Exception as e:
        _log.warning("AI 변환 실패 [%s]: %s — 규칙 기반 폴백", obj_name, e)
        return _rule_based_ddl_convert(ddl, obj_type, obj_name, src_db, tgt_db_type)


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
        _log.debug("obj_mapping 규칙 로드 실패: %s", e)

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
        _log.info("[%s] VIEW 변환 완료", obj_name)
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
            _log.info("[%s] %s → MSSQL DROP+CREATE 분리", obj_name, obj_type)
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
            _log.info("[%s] %s → MySQL DROP+CREATE 분리", obj_name, obj_type)
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
            _log.warning("[%s] %s→%s 변환 미지원, 기본 정리만 적용", obj_name, src, tgt)
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
            if not s.rstrip().upper().endswith('END'):
                s = s.rstrip() + '\nEND'
            drop = (f"IF OBJECT_ID(N'[dbo].[{nm}]', N'TR') IS NOT NULL DROP TRIGGER [{nm}]")
            return {"statements": [drop, s.strip()],
                    "notes": "규칙 기반 변환 — TRIGGER MySQL→MSSQL"}

        elif src in MSSQL_TYPES and tgt in MYSQL_TYPES:
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
            s = R.sub(r'SELECT\s+(.+?)\s+FROM\s+deleted\b',
                      lambda m: _sel_from_del(m), s, flags=R.IGNORECASE|R.DOTALL)
            s = R.sub(r'\bFROM\s+deleted\b', '', s, flags=R.IGNORECASE)
            s = R.sub(r'\bFROM\s+inserted\b', '', s, flags=R.IGNORECASE)
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
            _log.info("[%s] TRIGGER → MySQL DROP+CREATE 분리", obj_name)
            return {"statements": [drop, s.strip()],
                    "notes": "규칙 기반 변환 — TRIGGER MSSQL→MySQL"}
        else:
            return {"statements": [s.strip()], "notes": f"부분 변환 — {src}→{tgt}"}

    # 기타 오브젝트 타입
    _log.info("[%s] %s 기본 변환 (%s→%s)", obj_name, obj_type, src, tgt)
    return {"statements": [s.strip()], "notes": f"기본 변환 — {src}→{tgt}"}



