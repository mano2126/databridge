from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import time

class DbType(str, Enum):
    MSSQL="mssql"; ORACLE="oracle"; POSTGRESQL="postgresql"; MYSQL="mysql"
    DB2="db2"; HANA="hana"; SYBASE="sybase"; SQLITE="sqlite"; MONGODB="mongodb"
    AURORA="aurora"; AZURE="azure"; SNOWFLAKE="snowflake"; CLICKHOUSE="clickhouse"
    TIDB="tidb"; BIGQUERY="bigquery"; DUCKDB="duckdb"; REDSHIFT="redshift"
    CLOUDSQL="cloudsql"; TERADATA="teradata"

@dataclass
class ConnectionInfo:
    db_type: DbType; host: str; port: int
    username: str; password: str; database: str; extra: dict = None

@dataclass
class TestResult:
    success: bool; latency: float | None; version: str | None; message: str

class ConnectorFactory:
    @staticmethod
    def test_connection(info: ConnectionInfo) -> TestResult:
        start = time.monotonic()
        try:
            conn = ConnectorFactory._connect(info)
            lat = round((time.monotonic()-start)*1000,1)
            ver = ConnectorFactory._version(conn, info.db_type)
            conn.close()
            return TestResult(True, lat, ver, "연결 성공")
        except Exception as e:
            return TestResult(False, None, None, str(e))

    @staticmethod
    def _connect(info: ConnectionInfo):
        if info.db_type == DbType.MSSQL:
            import pyodbc
            return pyodbc.connect(f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={info.host},{info.port};DATABASE={info.database};UID={info.username};PWD={info.password};TrustServerCertificate=yes;",timeout=5)
        elif info.db_type in (DbType.MYSQL, DbType.AURORA, DbType.CLOUDSQL, DbType.TIDB):
            import pymysql
            return pymysql.connect(host=info.host,port=info.port,user=info.username,password=info.password,database=info.database,charset="utf8mb4",connect_timeout=5)
        elif info.db_type == DbType.POSTGRESQL:
            import psycopg2
            return psycopg2.connect(host=info.host,port=info.port,user=info.username,password=info.password,dbname=info.database,connect_timeout=5)
        elif info.db_type == DbType.ORACLE:
            import cx_Oracle
            dsn=cx_Oracle.makedsn(info.host,info.port,service_name=info.database)
            return cx_Oracle.connect(info.username,info.password,dsn)
        elif info.db_type == DbType.SQLITE:
            import sqlite3; return sqlite3.connect(info.database)
        else:
            raise NotImplementedError(f"{info.db_type} 드라이버 미구현")

    @staticmethod
    def _version(conn, db_type) -> str:
        try:
            cur=conn.cursor()
            sql={DbType.MSSQL:"SELECT @@VERSION",DbType.MYSQL:"SELECT VERSION()",
                 DbType.POSTGRESQL:"SELECT version()",DbType.SQLITE:"SELECT sqlite_version()"}.get(db_type,"SELECT 1")
            cur.execute(sql); r=cur.fetchone()
            return str(r[0])[:60] if r else "Unknown"
        except: return "Unknown"
