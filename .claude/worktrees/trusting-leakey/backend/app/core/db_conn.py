"""
app/core/db_conn.py
DB 연결 공통 유틸리티

- 포트는 항상 연결 정보(conn_info)에서 읽음 (하드코딩 금지)
- MSSQL: 설치된 ODBC 드라이버 자동 감지 (18 → 17 → SQL Server 순서)
- TrustServerCertificate=yes + Encrypt=no 항상 포함
- 핸드셰이크 오류: 1회만 재시도 (과도한 재시도 방지)
"""
try:
    import pyodbc
    # 연결 풀링 비활성화 — SQL Server 과부하 방지
    # (연결 close() 시 즉시 해제, 풀에 남기지 않음)
    pyodbc.pooling = False
    _pyodbc_available = True
except ImportError:
    _pyodbc_available = False


def default_port(db_type: str) -> int:
    """DB 종류별 기본 포트"""
    return {
        "mssql":      1433,
        "azure":      1433,
        "sqlserver":  1433,
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
    p = conn_info.get("port") or conn_info.get("PORT")
    if p:
        return int(p)
    return default_port(conn_info.get("db_type", "mysql"))


def make_mssql_conn(host: str, port, username: str, password: str,
                    database: str, timeout: int = 10, retries: int = 2):
    """
    MSSQL 연결 반환.
    - 드라이버 18 → 17 → SQL Server 순서로 자동 선택
    - 첫 번째 드라이버 성공 시 즉시 반환
    - 핸드셰이크 오류(08001/10054)는 1회만 재시도 (과부하 방지)
    """
    import time
    if not _pyodbc_available:
        raise Exception(
            "pyodbc 모듈이 설치되지 않았습니다. "
            "venv\\Scripts\\activate 후 'pip install pyodbc' 를 실행하세요."
        )
    port = int(port) if port else 1433
    drivers = [drv for drv in [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server",
    ] if drv in pyodbc.drivers()]

    if not drivers:
        raise Exception("MSSQL ODBC 드라이버가 설치되지 않았습니다.")

    # 첫 번째 시도
    errors = []
    for drv in drivers:
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
            return pyodbc.connect(dsn, timeout=timeout)
        except Exception as e:
            errors.append(f"{drv}: {e}")

    # 핸드셰이크/네트워크 오류인 경우에만 1회 재시도
    is_network_err = any(
        code in str(e)
        for e in errors
        for code in ("08001", "10054", "08S01", "11")
    )
    if is_network_err and retries > 1:
        time.sleep(1.5)
        errors2 = []
        for drv in drivers:
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
                return pyodbc.connect(dsn, timeout=timeout)
            except Exception as e:
                errors2.append(f"{drv}: {e}")
        errors = errors2

    raise Exception("MSSQL 연결 실패 — " + " | ".join(errors))


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
    """
    db_type  = conn_info.get("db_type", "mysql")
    host     = conn_info.get("host", "")
    port     = get_port(conn_info)
    username = conn_info.get("username", "")
    password = conn_info.get("password", "")
    database = conn_info.get("database", "")

    if not host or not database:
        raise ValueError(f"연결 정보 부족 — host={host!r} database={database!r}")

    if db_type in ("mysql", "aurora", "cloudsql", "tidb", "mariadb"):
        return make_mysql_conn(host, port, username, password, database, timeout, dict_cursor)
    elif db_type in ("mssql", "azure", "sqlserver"):
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
