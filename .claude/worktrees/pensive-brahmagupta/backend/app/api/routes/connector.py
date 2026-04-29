"""
app/api/routes/connector.py
커넥터 관리 REST API — JSON 파일 영속성 적용
"""
from fastapi import APIRouter, HTTPException
import uuid, time, random
from datetime import datetime
from app.core.store import Store

router = APIRouter()

# ── JSON 파일 영속 스토어 ─────────────────────────────────
_profiles = Store("profiles")

# 초기 샘플 프로파일 (profiles.json이 없을 때만 생성)
if len(_profiles) == 0:
    _default = {
        "id": "p1",
        "name": "MySQL Local → MSSQL Local",
        "source": {
            "db_type": "mysql", "host": "localhost", "port": 3306,
            "username": "root", "password": "", "database": "sakila",
            "version": "MySQL 8.0",
        },
        "target": {
            "db_type": "mssql", "host": "localhost", "port": 1433,
            "username": "sa", "password": "", "database": "target_db",
            "version": "SQL Server 2019",
        },
        "created_at": datetime.now().isoformat(),
        "status": "ok",
    }
    _profiles.set("p1", _default)

# ── DB 버전 Mock 매핑 ─────────────────────────────────────
_DB_VER = {
    "mssql":      "Microsoft SQL Server 2019 (RTM) - 15.0.2000.5",
    "mysql":      "8.0.45 MySQL Community Server",
    "postgresql": "PostgreSQL 15.6 on x86_64-pc-linux-gnu",
    "oracle":     "Oracle Database 19c Enterprise Edition",
    "aurora":     "8.0.36 MySQL Community Server (Aurora)",
    "azure":      "Microsoft SQL Server 2022 (Azure SQL)",
    "snowflake":  "Snowflake 7.42.0",
    "db2":        "DB2/LINUXX8664 SQL11054",
    "hana":       "SAP HANA 2.00.070",
    "clickhouse": "23.8.9.54",
    "tidb":       "TiDB v7.5.0",
    "bigquery":   "BigQuery (Google Cloud)",
    "duckdb":     "DuckDB v0.9.2",
    "redshift":   "Redshift (PostgreSQL 8.0.2)",
    "sqlite":     "SQLite 3.45.1",
    "mongodb":    "MongoDB 7.0.4",
    "cloudsql":   "Cloud SQL MySQL 8.0.31",
    "sybase":     "Adaptive Server Enterprise 16.0",
    "teradata":   "Teradata Database 17.20",
}


# ── 연결 테스트 ───────────────────────────────────────────

@router.post("/test")
def test_connection(body: dict):
    """
    DB 연결 테스트
    body: { db_type, host, port, username, password, database, version }
    """
    db_type  = body.get("db_type", "")
    host     = body.get("host", "").strip()
    port     = body.get("port", 3306)
    username = body.get("username", "").strip()
    password = body.get("password", "")
    database = body.get("database", "").strip()

    # 기본 유효성 검사
    if not host:
        return {"success": False, "latency": None, "version": None, "message": "호스트를 입력하세요"}
    if not username and db_type not in ("sqlite", "bigquery", "duckdb"):
        return {"success": False, "latency": None, "version": None, "message": "사용자명을 입력하세요"}
    if not database:
        return {"success": False, "latency": None, "version": None, "message": "데이터베이스명을 입력하세요"}

    # 실제 드라이버 연결 시도
    try:
        result = _real_connect(db_type, host, int(port), username, password, database)
        return result
    except NotImplementedError:
        pass  # 미지원 드라이버 → Mock으로 대체
    except Exception as e:
        # 드라이버는 있는데 연결 실패 → 실제 에러 반환
        return {
            "success": False,
            "latency": None,
            "version": None,
            "message": f"연결 실패: {str(e)[:200]}",
        }

    # Mock 응답 (드라이버 미설치 DB)
    time.sleep(random.uniform(0.3, 0.8))
    lat = round(random.uniform(2.0, 18.0), 1)
    ver = _DB_VER.get(db_type, "Unknown")
    return {
        "success": True,
        "latency": lat,
        "version": ver,
        "message": f"연결 성공 (Mock) — {ver[:60]}",
    }


def _real_connect(db_type: str, host: str, port: int,
                  username: str, password: str, database: str) -> dict:
    """실제 드라이버로 연결 시도"""
    start = time.monotonic()

    if db_type in ("mysql", "aurora", "cloudsql", "tidb", "mariadb"):
        import pymysql
        conn = pymysql.connect(
            host=host, port=port, user=username, password=password,
            database=database, charset="utf8mb4", connect_timeout=8
        )
        cur = conn.cursor()
        cur.execute("SELECT VERSION()")
        ver = cur.fetchone()[0]
        conn.close()
        lat = round((time.monotonic() - start) * 1000, 1)
        return {"success": True, "latency": lat, "version": ver,
                "message": f"연결 성공 — MySQL {ver}"}

    elif db_type in ("mssql", "azure"):
        # make_mssql_conn: 드라이버 18→17→SQL Server 자동선택, Encrypt=no, 재시도 포함
        from app.core.db_conn import make_mssql_conn
        conn = make_mssql_conn(host, port, username, password, database, timeout=8)
        cur = conn.cursor()
        cur.execute("SELECT @@VERSION")
        ver = str(cur.fetchone()[0])[:80]
        conn.close()
        lat = round((time.monotonic() - start) * 1000, 1)
        return {"success": True, "latency": lat, "version": ver,
                "message": f"연결 성공 — SQL Server"}

    elif db_type == "postgresql":
        import psycopg2
        conn = psycopg2.connect(
            host=host, port=port, user=username, password=password,
            dbname=database, connect_timeout=8
        )
        cur = conn.cursor()
        cur.execute("SELECT version()")
        ver = cur.fetchone()[0][:80]
        conn.close()
        lat = round((time.monotonic() - start) * 1000, 1)
        return {"success": True, "latency": lat, "version": ver, "message": "연결 성공"}

    elif db_type == "sqlite":
        import sqlite3
        conn = sqlite3.connect(database)
        ver = f"SQLite {sqlite3.sqlite_version}"
        conn.close()
        lat = round((time.monotonic() - start) * 1000, 1)
        return {"success": True, "latency": lat, "version": ver, "message": "연결 성공"}

    else:
        raise NotImplementedError(f"드라이버 미구현: {db_type}")


# ── 프로파일 CRUD ─────────────────────────────────────────

@router.get("/profiles")
def list_profiles():
    return _profiles.values()


@router.post("/profiles", status_code=201)
def create_profile(body: dict):
    pid = str(uuid.uuid4())[:8]
    profile = {
        "id":         pid,
        "name":       body.get("name", "새 프로파일"),
        "source":     body.get("source", {}),
        "target":     body.get("target", {}),
        "created_at": datetime.now().isoformat(),
        "status":     "ok",
    }
    _profiles.set(pid, profile)
    return profile


@router.get("/profiles/{pid}")
def get_profile(pid: str):
    p = _profiles.get(pid)
    if p is None:
        raise HTTPException(404, "프로파일을 찾을 수 없습니다")
    return p


@router.put("/profiles/{pid}")
def update_profile(pid: str, body: dict):
    """프로파일 수정"""
    p = _profiles.get(pid)
    if p is None:
        raise HTTPException(404, "프로파일을 찾을 수 없습니다")
    if "name"   in body: p["name"]   = body["name"]
    if "source" in body: p["source"] = body["source"]
    if "target" in body: p["target"] = body["target"]
    p["updated_at"] = datetime.now().isoformat()
    _profiles.set(pid, p)
    return p


@router.delete("/profiles/{pid}", status_code=204)
def delete_profile(pid: str):
    if pid not in _profiles:
        raise HTTPException(404, "프로파일을 찾을 수 없습니다")
    _profiles.delete(pid)
