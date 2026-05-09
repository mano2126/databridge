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


# ════════════════════════════════════════════════════════════════
# v95_p20 (2026-05-03 본부장님 본질 처방): 드라이버 모듈 캐시
# ════════════════════════════════════════════════════════════════
# 본부장님 호소: "이렇게 db 접속을 대량으로 해야 되는거야?"
#
# 본질 진단 — 본부장님 환경 로그:
#   PYODBC connect → DRIVER=ODBC 18 → 실패
#   PYODBC connect → DRIVER=ODBC 17 → 실패
#   PYODBC connect → DRIVER={SQL Server} → 성공
#   ... 매 connect 마다 위 패턴 반복 (3종 fallback) ...
#
# 처방: 첫 성공한 드라이버를 모듈 변수에 캐시 → 다음 connect 부터 그것만 시도
# 효과: 변환 규칙 화면 로드 시 connect 시도 횟수 약 3배 감소
#
# 본부장님 원칙: 환경별로 자동 감지 (하드코딩 없음 — pyodbc.drivers() 결과 기반)
_cached_mssql_driver: str = ""  # 첫 성공 드라이버 캐시 (전역 모듈 변수)


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
                    database: str, timeout: int = 10):
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

    # ── v95_p20 (2026-05-03 본부장님 본질 처방): 캐시된 드라이버 우선 시도 ──
    # 첫 성공 드라이버를 캐시 → 다음 connect 부터 그것만 시도 → fallback 폭발 방지
    global _cached_mssql_driver
    if _cached_mssql_driver and _cached_mssql_driver in drivers:
        # 캐시된 드라이버를 맨 앞으로 (이전 성공한 드라이버를 우선 시도)
        drivers = [_cached_mssql_driver] + [d for d in drivers if d != _cached_mssql_driver]

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
            conn = pyodbc.connect(dsn, timeout=timeout)
            # 한글/유니코드 처리 (v9 패치 #15, v10 #14 개선):
            #   - setdecoding: 서버→클라 (SELECT 결과 읽기) 인코딩
            #       SQL_CHAR  (VARCHAR)  는 한국어 MSSQL 관행에 따라 CP949 우선
            #       SQL_WCHAR (NVARCHAR) 는 UTF-16LE (MSSQL 서버 표준)
            #   - setencoding(SQL_WCHAR): 클라→서버 (INSERT/WHERE 파라미터) 인코딩
            #       Python str → UTF-16LE 로 직접 전송 → MSSQL NVARCHAR 에 정확히 매핑
            #       이걸 빠뜨리면 pyodbc 가 기본 UCS-2 를 쓰거나 latin-1 을 거쳐 손상 가능
            #   - setencoding(str=...) 는 NVARCHAR 컬럼과 잘 맞음.
            #
            # v10 #14 변경:
            #   기존 SQL_CHAR = 'utf-8' → CP949 VARCHAR 데이터에서 한글 디코딩 실패
            #   ('utf-8' codec can't decode byte 0xbf/0xb5 ...)
            #   한국어 MSSQL 관행:
            #     - NVARCHAR: 유니코드 (UTF-16LE) — 표준
            #     - VARCHAR : 코드페이지 의존 (한국어 Windows 기본 CP949/MS949/EUC-KR)
            #   환경변수 DATABRIDGE_MSSQL_VARCHAR_ENCODING 로 override 가능 (기본: cp949).
            try:
                import os as _os
                _varchar_enc = _os.environ.get(
                    "DATABRIDGE_MSSQL_VARCHAR_ENCODING", "cp949"
                ).lower().strip() or "cp949"
                conn.setdecoding(pyodbc.SQL_CHAR,  encoding=_varchar_enc)
                conn.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-16le')
                # Python str → MSSQL NVARCHAR(UTF-16LE) 직결
                conn.setencoding(encoding='utf-16le')
            except Exception:
                pass  # 구버전 pyodbc는 메서드 없음
            # v95_p20: 첫 성공 드라이버를 모듈 캐시에 기록
            #   다음 connect 부터 이 드라이버만 시도 (fallback 폭발 방지)
            if _cached_mssql_driver != drv:
                _cached_mssql_driver = drv
            return conn
        except Exception as e:
            errors.append(f"{drv}: {e}")

    # 네트워크 오류(10054 등) 시 재시도하지 않음
    # → 재시도가 오히려 연결 풀 부하를 키우고 MSSQL 서버 과부하 유발
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
