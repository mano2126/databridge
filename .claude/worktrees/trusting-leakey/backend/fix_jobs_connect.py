"""
fix_jobs_connect.py
backend 폴더에서 실행: python fix_jobs_connect.py

jobs.py 의 _connect_src, _connect_tgt 함수를
src_db / tgt_db 타입을 보고 올바른 드라이버로 연결하도록 수정합니다.

기존: _connect_src = 항상 MySQL, _connect_tgt = 항상 MSSQL
수정: src_db/tgt_db 타입에 따라 MySQL/MSSQL 자동 선택
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
            j        = self.job
            db_type  = j.get("src_db", "mysql")
            host     = j.get("src_host", "localhost")
            port     = int(j.get("src_port") or j.get("port") or (1434 if db_type in ("mssql","azure") else 3306))
            username = j.get("src_username", "root")
            password = j.get("src_password", "")
            database = j.get("src_database", "")

            if db_type in ("mssql", "azure"):
                import pyodbc
                available = pyodbc.drivers()
                drv = "ODBC Driver 18 for SQL Server" if "ODBC Driver 18 for SQL Server" in available \
                      else "ODBC Driver 17 for SQL Server"
                dsn = (
                    f"DRIVER={{{drv}}};"
                    f"SERVER={host},{port};"
                    f"DATABASE={database};"
                    f"UID={username};PWD={password};"
                    "TrustServerCertificate=yes;"
                )
                conn = pyodbc.connect(dsn)
                # MSSQL 커서를 DictCursor처럼 동작하도록 래핑
                conn._db_type = "mssql"
                return conn
            else:
                import pymysql
                return pymysql.connect(
                    host=host, port=port,
                    user=username, password=password,
                    database=database, charset="utf8mb4",
                    connect_timeout=10,
                    cursorclass=pymysql.cursors.DictCursor
                )
        except Exception as e:
            self._log("error", f"소스 연결 실패: {e}")
            return None'''

if OLD_SRC in content:
    content = content.replace(OLD_SRC, NEW_SRC)
    print('_connect_src 수정 완료')
else:
    print('주의: _connect_src 패턴 없음')

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
            j        = self.job
            db_type  = j.get("tgt_db", "mssql")
            host     = j.get("tgt_host", "localhost")
            port     = int(j.get("tgt_port") or (1434 if db_type in ("mssql","azure") else 3306))
            username = j.get("tgt_username", "sa")
            password = j.get("tgt_password", "")
            database = j.get("tgt_database", "target_db")

            if db_type in ("mssql", "azure"):
                import pyodbc
                available = pyodbc.drivers()
                drv = "ODBC Driver 18 for SQL Server" if "ODBC Driver 18 for SQL Server" in available \
                      else "ODBC Driver 17 for SQL Server"
                dsn = (
                    f"DRIVER={{{drv}}};"
                    f"SERVER={host},{port};"
                    f"DATABASE={database};"
                    f"UID={username};PWD={password};"
                    "TrustServerCertificate=yes;"
                )
                return pyodbc.connect(dsn)
            else:
                import pymysql
                return pymysql.connect(
                    host=host, port=port,
                    user=username, password=password,
                    database=database, charset="utf8mb4",
                    connect_timeout=10
                )
        except Exception as e:
            self._log("error", f"타겟 연결 실패: {e}")
            return None'''

if OLD_TGT in content:
    content = content.replace(OLD_TGT, NEW_TGT)
    print('_connect_tgt 수정 완료')
else:
    print('주의: _connect_tgt 패턴 없음')

# ── 문법 확인 및 저장 ─────────────────────────────────────
try:
    ast.parse(content)
    print('✓ 문법 OK')
except SyntaxError as e:
    print(f'✗ 문법 오류: {e}')
    print(f'복구: copy {bak} {path}')
    exit(1)

open(path, 'w', encoding='utf-8').write(content)

print('\n완료! 백엔드 재시작:')
print('python -m uvicorn main:app --port 8000')
