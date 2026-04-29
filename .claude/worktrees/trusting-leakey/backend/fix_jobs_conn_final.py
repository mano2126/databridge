"""
fix_jobs_conn_final.py
backend 폴더에서 실행: python fix_jobs_conn_final.py

_connect_src — 항상 pymysql(MySQL) → src_db 타입 기반 자동 선택
_connect_tgt — 항상 pyodbc(MSSQL) → tgt_db 타입 기반 자동 선택
_get_all_tables, _estimate_total_rows — MSSQL 소스 지원
"""
import shutil, ast
from datetime import datetime

path = 'app/api/routes/jobs.py'
bak  = path + '.' + datetime.now().strftime('%H%M%S') + '.bak'
shutil.copy2(path, bak)
print(f'백업: {bak}')

content = open(path, encoding='utf-8').read()

# ── _connect_src 교체 ─────────────────────────────────────
OLD_SRC = '''    def _connect_src(self):
        try:
            import pymysql
            j = self.job
            return pymysql.connect(
                host=j.get("src_host","localhost"),
                port=3306,
                user=j.get("src_username","root"),
                password=j.get("src_password",""),
                database=j.get("src_database",""),
                charset="utf8mb4",
                connect_timeout=10,
                cursorclass=pymysql.cursors.DictCursor
            )
        except Exception as e:
            self._log("error", f"소스 연결 실패: {e}")
            return None'''

NEW_SRC = '''    def _connect_src(self):
        try:
            j       = self.job
            db_type = j.get("src_db", "mysql")
            host    = j.get("src_host", "localhost")
            port    = int(j.get("src_port") or (1434 if db_type in ("mssql","azure") else 3306))
            user    = j.get("src_username", "")
            pw      = j.get("src_password", "")
            db      = j.get("src_database", "")
            self._log("info", f"소스 연결: {db_type}://{host}:{port}/{db}")
            if db_type in ("mssql", "azure"):
                from app.core.db_conn import make_mssql_conn
                return make_mssql_conn(host, port, user, pw, db)
            elif db_type in ("postgresql", "redshift"):
                import psycopg2
                return psycopg2.connect(host=host, port=port, user=user,
                                        password=pw, dbname=db, connect_timeout=10)
            else:
                import pymysql
                return pymysql.connect(
                    host=host, port=port, user=user, password=pw,
                    database=db, charset="utf8mb4", connect_timeout=10,
                    cursorclass=pymysql.cursors.DictCursor
                )
        except Exception as e:
            self._log("error", f"소스 연결 실패: {e}")
            return None'''

if OLD_SRC in content:
    content = content.replace(OLD_SRC, NEW_SRC)
    print('_connect_src 교체 완료')
else:
    print('주의: _connect_src 패턴 없음 — 현재 내용 확인')
    idx = content.find('def _connect_src')
    if idx >= 0:
        print(repr(content[idx:idx+300]))

# ── _connect_tgt 교체 ─────────────────────────────────────
OLD_TGT = '''    def _connect_tgt(self):
        try:
            import pyodbc
            j = self.job
            dsn = (
                f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                f"SERVER={j.get('tgt_host','localhost')};"
                f"DATABASE={j.get('tgt_database','target_db')};"
                f"UID={j.get('tgt_username','sa')};"
                f"PWD={j.get('tgt_password','')};"
                "TrustServerCertificate=yes;"
            )
            return pyodbc.connect(dsn)
        except Exception as e:
            self._log("error", f"타겟 연결 실패: {e}")
            return None'''

NEW_TGT = '''    def _connect_tgt(self):
        try:
            j       = self.job
            db_type = j.get("tgt_db", "mssql")
            host    = j.get("tgt_host", "localhost")
            port    = int(j.get("tgt_port") or (1434 if db_type in ("mssql","azure") else 3306))
            user    = j.get("tgt_username", "")
            pw      = j.get("tgt_password", "")
            db      = j.get("tgt_database", "")
            self._log("info", f"타겟 연결: {db_type}://{host}:{port}/{db}")
            if db_type in ("mssql", "azure"):
                from app.core.db_conn import make_mssql_conn
                return make_mssql_conn(host, port, user, pw, db)
            elif db_type in ("postgresql", "redshift"):
                import psycopg2
                return psycopg2.connect(host=host, port=port, user=user,
                                        password=pw, dbname=db, connect_timeout=10)
            else:
                import pymysql
                return pymysql.connect(
                    host=host, port=port, user=user, password=pw,
                    database=db, charset="utf8mb4", connect_timeout=10
                )
        except Exception as e:
            self._log("error", f"타겟 연결 실패: {e}")
            return None'''

if OLD_TGT in content:
    content = content.replace(OLD_TGT, NEW_TGT)
    print('_connect_tgt 교체 완료')
else:
    print('주의: _connect_tgt 패턴 없음')
    idx = content.find('def _connect_tgt')
    if idx >= 0:
        print(repr(content[idx:idx+300]))

# ── _get_all_tables — MSSQL 소스 지원 ────────────────────
OLD_TABLES = '''    def _get_all_tables(self, src_conn) -> list:
        cur = src_conn.cursor()
        cur.execute("""
            SELECT TABLE_NAME FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE='BASE TABLE'
            ORDER BY TABLE_NAME
        """)
        return [r["TABLE_NAME"] for r in cur.fetchall()]'''

NEW_TABLES = '''    def _get_all_tables(self, src_conn) -> list:
        db_type = self.job.get("src_db", "mysql")
        cur = src_conn.cursor()
        if db_type in ("mssql", "azure"):
            cur.execute("""
                SELECT t.name AS TABLE_NAME
                FROM sys.tables t
                JOIN sys.schemas s ON t.schema_id=s.schema_id
                WHERE s.name='dbo' ORDER BY t.name
            """)
            rows = cur.fetchall()
            return [r[0] if not isinstance(r, dict) else r["TABLE_NAME"] for r in rows]
        elif db_type in ("postgresql", "redshift"):
            cur.execute("""
                SELECT tablename AS TABLE_NAME FROM pg_tables
                WHERE schemaname='public' ORDER BY tablename
            """)
            rows = cur.fetchall()
            return [r[0] if not isinstance(r, dict) else r["TABLE_NAME"] for r in rows]
        else:
            cur.execute("""
                SELECT TABLE_NAME FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE='BASE TABLE'
                ORDER BY TABLE_NAME
            """)
            return [r["TABLE_NAME"] if isinstance(r, dict) else r[0] for r in cur.fetchall()]'''

if OLD_TABLES in content:
    content = content.replace(OLD_TABLES, NEW_TABLES)
    print('_get_all_tables 교체 완료')
else:
    print('주의: _get_all_tables 패턴 없음')

# ── _estimate_total_rows — MSSQL 소스 지원 ───────────────
OLD_EST_START = '    def _estimate_total_rows(self, src_conn, tables: list) -> int:\n        cur = src_conn.cursor()\n        total = 0\n        db = self.job.get("src_database","")'
NEW_EST_START = '    def _estimate_total_rows(self, src_conn, tables: list) -> int:\n        db_type = self.job.get("src_db", "mysql")\n        cur = src_conn.cursor()\n        total = 0\n        db = self.job.get("src_database","")'

if OLD_EST_START in content:
    content = content.replace(OLD_EST_START, NEW_EST_START)
    # MSSQL 분기 추가
    OLD_EST_QUERY = ('            try:\n'
                     '                cur.execute(\n'
                     '                    "SELECT TABLE_ROWS FROM information_schema.TABLES "\n'
                     '                    "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",\n'
                     '                    (db, tbl)\n'
                     '                )\n'
                     '                r = cur.fetchone()\n'
                     '                total += (r["TABLE_ROWS"] or 0) if r else 0\n'
                     '            except:\n'
                     '                pass')
    NEW_EST_QUERY = ('            try:\n'
                     '                if db_type in ("mssql", "azure"):\n'
                     '                    cur.execute(\n'
                     '                        "SELECT SUM(p.rows) FROM sys.tables t "\n'
                     '                        "JOIN sys.partitions p ON t.object_id=p.object_id "\n'
                     '                        "AND p.index_id IN(0,1) WHERE t.name=?", (tbl,)\n'
                     '                    )\n'
                     '                    r = cur.fetchone()\n'
                     '                    total += (r[0] or 0) if r else 0\n'
                     '                elif db_type in ("postgresql", "redshift"):\n'
                     '                    cur.execute(\n'
                     '                        "SELECT reltuples::BIGINT FROM pg_class "\n'
                     '                        "WHERE relname=%s", (tbl,)\n'
                     '                    )\n'
                     '                    r = cur.fetchone()\n'
                     '                    total += int(r[0] or 0) if r else 0\n'
                     '                else:\n'
                     '                    cur.execute(\n'
                     '                        "SELECT TABLE_ROWS FROM information_schema.TABLES "\n'
                     '                        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",\n'
                     '                        (db, tbl)\n'
                     '                    )\n'
                     '                    r = cur.fetchone()\n'
                     '                    total += (r["TABLE_ROWS"] or 0) if r else 0\n'
                     '            except:\n'
                     '                pass')
    if OLD_EST_QUERY in content:
        content = content.replace(OLD_EST_QUERY, NEW_EST_QUERY)
        print('_estimate_total_rows 교체 완료')
    else:
        print('_estimate_total_rows 쿼리 패턴 없음 (부분 교체됨)')
else:
    print('주의: _estimate_total_rows 패턴 없음')

# ── 문법 확인 ─────────────────────────────────────────────
try:
    ast.parse(content)
    print('✓ 문법 OK')
except SyntaxError as e:
    print(f'✗ 문법 오류 {e.lineno}: {e.msg}')
    lines = content.split('\n')
    for i, l in enumerate(lines[max(0,e.lineno-3):e.lineno+3], max(1,e.lineno-2)):
        print(f'{i}: {l}')
    print(f'복구: copy {bak} {path}')
    exit(1)

open(path, 'w', encoding='utf-8').write(content)

# 검증 출력
print('\n=== 검증 ===')
new = open(path, encoding='utf-8').read()
print('src_db 기반 분기:', 'src_db", "mysql")' in new or 'src_db","mysql")' in new)
print('make_mssql_conn in src:', 'make_mssql_conn' in new)
print('남은 pymysql 하드코딩:', new.count('port=3306'))
print('\n완료! 백엔드 재시작:')
print('python -m uvicorn main:app --port 8000')
