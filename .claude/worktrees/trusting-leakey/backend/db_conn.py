"""
app/core/db_conn.py
DB 연결 공통 유틸리티

- 포트는 항상 연결 정보(conn_info)에서 읽음 (하드코딩 금지)
- MSSQL: 설치된 ODBC 드라이버 자동 감지 (18 → 17 → SQL Server 순서)
- TrustServerCertificate=yes + Encrypt=no 항상 포함
"""
import pyodbc


def default_port(db_type: str) -> int:
    """DB 종류별 기본 포트"""
    return {
        "mssql":      1433,
        "azure":      1433,
        "mysql":      3306,
        "aurora":     3306,
        "mariadb":    3306,
        "cloudsql":   3306,
        "tidb":       3306,
        "postgresql": 5432,
        "redshift":   5439,
        "oracle":     1521,
        "mongodb":    27017,
        "sqlite":     0,
    }.get(db_type, 3306)


def get_port(conn_info: dict) -> int:
    """
    연결 정보 dict에서 포트 추출.
    port 값이 있으면 그대로 사용, 없으면 db_type 기반 기본값.
    """
    p = conn_info.get("port") or conn_info.get("PORT")
    if p:
        return int(p)
    return default_port(conn_info.get("db_type", "mysql"))


def make_mssql_conn(host: str, port, username: str, password: str,
                    database: str, timeout: int = 10):
    """
    설치된 ODBC 드라이버를 자동 감지하여 MSSQL 연결 반환.
    18 → 17 → SQL Server 순서로 시도.
    포트는 반드시 인자로 받은 값 사용.
    """
    port = int(port) if port else 1433
    errors = []

    for drv in [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server",
    ]:
        if drv not in pyodbc.drivers():
            continue
        dsn = (
            f"DRIVER={{{drv}}};"
            f"SERVER={host},{port};"
            f"DATABASE={database};"
            f"UID={username};"
            f"PWD={password};"
            "TrustServerCertificate=yes;"
            "Encrypt=no;"
        )
        try:
            conn = pyodbc.connect(dsn, timeout=timeout)
            return conn
        except Exception as e:
            errors.append(f"{drv}: {e}")

    raise Exception("MSSQL 연결 실패 — " + " | ".join(errors) if errors
                    else "MSSQL ODBC 드라이버가 설치되지 않았습니다.")


def make_mysql_conn(host: str, port, username: str, password: str,
                    database: str, timeout: int = 10, dict_cursor: bool = False):
    """MySQL 계열 연결 반환"""
    import pymysql
    kwargs = dict(
        host=host,
        port=int(port) if port else 3306,
        user=username,
        password=password,
        database=database,
        charset="utf8mb4",
        connect_timeout=timeout,
    )
    if dict_cursor:
        kwargs["cursorclass"] = pymysql.cursors.DictCursor
    return pymysql.connect(**kwargs)


def make_conn(conn_info: dict, timeout: int = 10, dict_cursor: bool = False):
    """
    연결 정보 dict를 받아 적절한 DB 연결 반환.
    포트는 conn_info['port'] 값을 그대로 사용.

    conn_info 필드:
        db_type   : "mysql" | "mssql" | "postgresql" | "sqlite" 등
        host      : 호스트
        port      : 포트 (없으면 db_type 기반 기본값)
        username  : 사용자명
        password  : 비밀번호
        database  : 데이터베이스명
    """
    db_type  = conn_info.get("db_type", "mysql")
    host     = conn_info.get("host", "")
    port     = get_port(conn_info)
    username = conn_info.get("username", "")
    password = conn_info.get("password", "")
    database = conn_info.get("database", "")

    if not host or not database:
        raise ValueError(
            f"연결 정보 부족 — host={host!r} database={database!r}"
        )

    if db_type in ("mysql", "aurora", "cloudsql", "tidb", "mariadb"):
        return make_mysql_conn(host, port, username, password, database,
                               timeout, dict_cursor)

    elif db_type in ("mssql", "azure"):
        return make_mssql_conn(host, port, username, password, database, timeout)

    elif db_type == "postgresql":
        import psycopg2
        return psycopg2.connect(
            host=host, port=port,
            user=username, password=password,
            dbname=database, connect_timeout=timeout,
        )

    elif db_type == "sqlite":
        import sqlite3
        return sqlite3.connect(database)

    raise NotImplementedError(f"지원되지 않는 DB 타입: {db_type}")
