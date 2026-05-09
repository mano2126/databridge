"""
apply_fix.py
backend 폴더에서 실행하세요: python apply_fix.py

1. app/core/db_conn.py 생성 (공통 연결 유틸리티)
2. schema.py  — _mssql_tables, _query_tables 등 수정
3. validate.py — _connect 함수 수정
4. jobs.py     — _connect_tgt 수정
5. connector.py — _real_connect 수정
"""
import os, re, shutil
from datetime import datetime

# ── 백업 ──────────────────────────────────────────────────
def backup(path):
    ts  = datetime.now().strftime('%H%M%S')
    bak = path + f'.bak{ts}'
    shutil.copy2(path, bak)
    print(f'  백업: {bak}')

# ── db_conn.py 생성 ───────────────────────────────────────
DB_CONN_CONTENT = open('db_conn.py', encoding='utf-8').read()  # 같은 폴더에 있어야 함

def create_db_conn():
    os.makedirs('app/core', exist_ok=True)
    # __init__.py 없으면 생성
    init = 'app/core/__init__.py'
    if not os.path.exists(init):
        open(init, 'w').close()
    
    with open('app/core/db_conn.py', 'w', encoding='utf-8') as f:
        f.write(DB_CONN_CONTENT)
    print('app/core/db_conn.py 생성 완료')

# ── schema.py 수정 ────────────────────────────────────────
def fix_schema():
    path = 'app/api/routes/schema.py'
    backup(path)
    content = open(path, encoding='utf-8').read()

    # 1. import 추가
    if 'from app.core.db_conn import' not in content:
        content = content.replace(
            'from fastapi import APIRouter, HTTPException',
            'from fastapi import APIRouter, HTTPException\n'
            'from app.core.db_conn import make_conn, make_mssql_conn, get_port, default_port'
        )

    # 2. _mssql_tables 함수 교체
    content = re.sub(
        r'def _mssql_tables\(h, p, u, pw, db\):.*?finally:\s*conn\.close\(\)',
        '''def _mssql_tables(h, p, u, pw, db):
    conn = make_mssql_conn(h, p, u, pw, db)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT s.name, t.name, p2.rows
            FROM sys.tables t
            JOIN sys.schemas s ON t.schema_id=s.schema_id
            JOIN sys.partitions p2 ON t.object_id=p2.object_id
              AND p2.index_id IN(0,1)
            ORDER BY s.name, t.name
        """)
        return [{"schema_name": r[0], "table_name": r[1],
                 "row_count": r[2] or 0, "size_mb": 0, "comment": ""}
                for r in cur.fetchall()]
    finally:
        conn.close()''',
        content, flags=re.DOTALL
    )

    # 3. _query_tables 포트 처리 수정
    content = content.replace(
        'h, p    = c.get("host",""), int(c.get("port", 3306))',
        'h       = c.get("host","")\n'
        '    p       = get_port(c)'
    )

    # 4. tables_by_params 기본 포트 수정
    content = content.replace(
        '"port":     port     or _conns.get(side,{}).get("port",3306)',
        '"port":     port     or _conns.get(side,{}).get("port")'
        ' or default_port(db_type or _conns.get(side,{}).get("db_type","mysql"))'
    )

    # 5. 나머지 pyodbc DSN 하드코딩 → make_mssql_conn 으로 교체
    # _get_objects_mssql 함수
    content = re.sub(
        r'def _get_objects_mssql\(h, p, u, pw, db\):.*?'
        r'import pyodbc\s*\n\s*dsn\s*=.*?conn\s*=\s*pyodbc\.connect\([^)]+\)',
        '''def _get_objects_mssql(h, p, u, pw, db):
    conn = make_mssql_conn(h, p, u, pw, db)''',
        content, flags=re.DOTALL
    )

    # 6. 나머지 모든 pyodbc 하드코딩 DSN에 Encrypt=no 추가
    content = re.sub(
        r'TrustServerCertificate=yes;"',
        'TrustServerCertificate=yes;Encrypt=no;"',
        content
    )
    content = re.sub(
        r"TrustServerCertificate=yes;'",
        "TrustServerCertificate=yes;Encrypt=no;'",
        content
    )
    # 중복 방지
    content = content.replace(
        'TrustServerCertificate=yes;Encrypt=no;Encrypt=no;',
        'TrustServerCertificate=yes;Encrypt=no;'
    )

    # 7. ODBC Driver 18 → 자동감지 (make_mssql_conn이 처리하므로 일단 그대로 둠)

    open(path, 'w', encoding='utf-8').write(content)
    print(f'{path} 수정 완료')


# ── validate.py 수정 ──────────────────────────────────────
def fix_validate():
    path = 'app/api/routes/validate.py'
    backup(path)
    content = open(path, encoding='utf-8').read()

    # import 추가
    if 'from app.core.db_conn import' not in content:
        content = content.replace(
            'from fastapi import APIRouter, HTTPException',
            'from fastapi import APIRouter, HTTPException\n'
            'from app.core.db_conn import make_conn, get_port, default_port'
        )

    # _connect 함수 전체 교체
    content = re.sub(
        r'def _connect\(info: dict\):.*?raise NotImplementedError[^\n]*\n',
        '''def _connect(info: dict):
    """연결 정보 dict → DB 연결 반환. 포트는 info['port'] 값 그대로 사용."""
    return make_conn(info, timeout=10, dict_cursor=True)
''',
        content, flags=re.DOTALL
    )

    # Encrypt=no 추가
    content = re.sub(
        r'TrustServerCertificate=yes;"',
        'TrustServerCertificate=yes;Encrypt=no;"',
        content
    )
    content = content.replace(
        'TrustServerCertificate=yes;Encrypt=no;Encrypt=no;',
        'TrustServerCertificate=yes;Encrypt=no;'
    )

    open(path, 'w', encoding='utf-8').write(content)
    print(f'{path} 수정 완료')


# ── jobs.py 수정 ──────────────────────────────────────────
def fix_jobs():
    path = 'app/api/routes/jobs.py'
    backup(path)
    content = open(path, encoding='utf-8').read()

    # import 추가
    if 'from app.core.db_conn import' not in content:
        content = content.replace(
            'from fastapi import APIRouter, BackgroundTasks, HTTPException',
            'from fastapi import APIRouter, BackgroundTasks, HTTPException\n'
            'from app.core.db_conn import make_conn, make_mssql_conn, get_port'
        )

    # _connect_tgt 함수 교체 (MSSQL 연결)
    content = re.sub(
        r'def _connect_tgt\(self\):.*?return None',
        '''def _connect_tgt(self):
        try:
            j = self.job
            conn_info = {
                "db_type":  j.get("tgt_db", "mssql"),
                "host":     j.get("tgt_host", "localhost"),
                "port":     j.get("tgt_port") or j.get("port", 1433),
                "username": j.get("tgt_username", "sa"),
                "password": j.get("tgt_password", ""),
                "database": j.get("tgt_database", ""),
            }
            from app.core.db_conn import make_conn
            return make_conn(conn_info, timeout=10)
        except Exception as e:
            self._log("error", f"타겟 연결 실패: {e}")
            return None''',
        content, flags=re.DOTALL
    )

    # _connect_src 함수 교체 (MySQL 연결)
    content = re.sub(
        r'def _connect_src\(self\):.*?return None',
        '''def _connect_src(self):
        try:
            j = self.job
            import pymysql
            conn_info = {
                "db_type":  j.get("src_db", "mysql"),
                "host":     j.get("src_host", "localhost"),
                "port":     j.get("src_port") or j.get("port", 3306),
                "username": j.get("src_username", "root"),
                "password": j.get("src_password", ""),
                "database": j.get("src_database", ""),
            }
            from app.core.db_conn import make_conn
            return make_conn(conn_info, timeout=10, dict_cursor=True)
        except Exception as e:
            self._log("error", f"소스 연결 실패: {e}")
            return None''',
        content, flags=re.DOTALL
    )

    # Encrypt=no 추가
    content = re.sub(
        r'TrustServerCertificate=yes;"',
        'TrustServerCertificate=yes;Encrypt=no;"',
        content
    )
    content = content.replace(
        'TrustServerCertificate=yes;Encrypt=no;Encrypt=no;',
        'TrustServerCertificate=yes;Encrypt=no;'
    )

    open(path, 'w', encoding='utf-8').write(content)
    print(f'{path} 수정 완료')


# ── connector.py 수정 ─────────────────────────────────────
def fix_connector():
    path = 'app/api/routes/connector.py'
    backup(path)
    content = open(path, encoding='utf-8').read()

    if 'from app.core.db_conn import' not in content:
        content = content.replace(
            'from fastapi import APIRouter, HTTPException',
            'from fastapi import APIRouter, HTTPException\n'
            'from app.core.db_conn import make_conn, get_port, default_port'
        )

    # _real_connect 함수 교체
    content = re.sub(
        r'def _real_connect\(.*?\) -> dict:.*?raise NotImplementedError[^\n]*\n',
        '''def _real_connect(db_type: str, host: str, port: int,
                  username: str, password: str, database: str) -> dict:
    """실제 드라이버로 연결 시도. 포트는 인자로 받은 값 그대로 사용."""
    import time as _t
    start = _t.monotonic()
    conn_info = {
        "db_type": db_type, "host": host, "port": port,
        "username": username, "password": password, "database": database,
    }
    conn = make_conn(conn_info, timeout=8)
    lat  = round((_t.monotonic() - start) * 1000, 1)

    # 버전 조회
    try:
        cur = conn.cursor()
        if db_type in ("mysql", "aurora", "cloudsql", "tidb", "mariadb"):
            cur.execute("SELECT VERSION()")
        elif db_type in ("mssql", "azure"):
            cur.execute("SELECT @@VERSION")
        elif db_type == "postgresql":
            cur.execute("SELECT version()")
        elif db_type == "sqlite":
            import sqlite3
            conn.close()
            return {"success": True, "latency": lat,
                    "version": f"SQLite {sqlite3.sqlite_version}",
                    "message": "연결 성공"}
        else:
            conn.close()
            return {"success": True, "latency": lat, "version": "", "message": "연결 성공"}
        ver = str(cur.fetchone()[0])[:80]
        conn.close()
        return {"success": True, "latency": lat, "version": ver, "message": f"연결 성공 — {ver[:50]}"}
    except Exception as e:
        try: conn.close()
        except: pass
        raise e
''',
        content, flags=re.DOTALL
    )

    open(path, 'w', encoding='utf-8').write(content)
    print(f'{path} 수정 완료')


# ── 메인 ──────────────────────────────────────────────────
if __name__ == '__main__':
    print('=== MSSQL 연결 포트 하드코딩 수정 시작 ===\n')

    # db_conn.py가 같은 폴더에 있는지 확인
    if not os.path.exists('db_conn.py'):
        print('오류: db_conn.py 파일이 backend 폴더에 없습니다.')
        print('db_conn.py 를 backend 폴더에 복사한 후 다시 실행하세요.')
        exit(1)

    create_db_conn()
    print()
    fix_schema()
    fix_validate()
    fix_jobs()
    fix_connector()

    print('\n=== 완료! 백엔드를 재시작하세요 ===')
    print('python -m uvicorn main:app --port 8000')
