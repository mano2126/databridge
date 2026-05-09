"""
fix_schema_v2.py
backend 폴더에서 실행: python fix_schema_v2.py

정규식 없이 정확한 문자열 치환만 사용합니다.
"""
import shutil, ast
from datetime import datetime

SRC = 'app/api/routes/schema.py'

# ── 백업 ──────────────────────────────────────────────────
bak = SRC + '.' + datetime.now().strftime('%H%M%S') + '.bak'
shutil.copy2(SRC, bak)
print(f'백업: {bak}')

content = open(SRC, encoding='utf-8').read()

# ── 1. import 추가 ────────────────────────────────────────
if 'from app.core.db_conn import' not in content:
    content = content.replace(
        'from fastapi import APIRouter, HTTPException',
        'from fastapi import APIRouter, HTTPException\n'
        'from app.core.db_conn import make_mssql_conn, get_port, default_port'
    )
    print('import 추가')

# ── 2. _mssql_tables 함수 내 DSN 블록만 교체 ─────────────
OLD_MSSQL_TABLES_DSN = '''    import pyodbc
    dsn = (f"DRIVER={{ODBC Driver 18 for SQL Server}};"
           f"SERVER={h},{p};DATABASE={db};"
           f"UID={u};PWD={pw};TrustServerCertificate=yes;")
    conn = pyodbc.connect(dsn, timeout=10)'''

NEW_MSSQL_TABLES_DSN = '''    conn = make_mssql_conn(h, p, u, pw, db)'''

if OLD_MSSQL_TABLES_DSN in content:
    content = content.replace(OLD_MSSQL_TABLES_DSN, NEW_MSSQL_TABLES_DSN)
    print('_mssql_tables DSN 교체 완료')
else:
    print('주의: _mssql_tables DSN 패턴을 찾지 못함 — 수동 확인 필요')

# ── 3. _get_objects_mssql 함수 내 DSN 블록만 교체 ─────────
OLD_GET_OBJECTS_DSN = '''    import pyodbc
    dsn = (f"DRIVER={{ODBC Driver 18 for SQL Server}};"
           f"SERVER={h},{p};DATABASE={db};UID={u};PWD={pw};TrustServerCertificate=yes;")
    conn = pyodbc.connect(dsn, timeout=10)
    result = {}'''

NEW_GET_OBJECTS_DSN = '''    conn = make_mssql_conn(h, p, u, pw, db)
    result = {}'''

if OLD_GET_OBJECTS_DSN in content:
    content = content.replace(OLD_GET_OBJECTS_DSN, NEW_GET_OBJECTS_DSN)
    print('_get_objects_mssql DSN 교체 완료')
else:
    print('주의: _get_objects_mssql DSN 패턴을 찾지 못함 — 수동 확인 필요')

# ── 4. execute_object 내 CHECK 블록 DSN 교체 ──────────────
OLD_CHECK_DSN = '''                import pyodbc
                dsn=(f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                     f"SERVER={c['host']},{c['port']};DATABASE={c['database']};"
                     f"UID={c['username']};PWD={c.get('password','')};TrustServerCertificate=yes;")
                conn=pyodbc.connect(dsn,timeout=8)'''

NEW_CHECK_DSN = '''                conn = make_mssql_conn(
                    c['host'], c['port'], c['username'],
                    c.get('password',''), c['database'], timeout=8
                )'''

if OLD_CHECK_DSN in content:
    content = content.replace(OLD_CHECK_DSN, NEW_CHECK_DSN)
    print('CHECK 블록 DSN 교체 완료')
else:
    print('주의: CHECK 블록 DSN 패턴을 찾지 못함')

# ── 5. DDL_CREATE 블록 DSN 교체 ───────────────────────────
OLD_DDL_DSN = '''                import pyodbc
                dsn = (
                    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                    f"SERVER={c['host']},{c['port']};DATABASE={c['database']};"
                    f"UID={c['username']};PWD={c.get('password','')};TrustServerCertificate=yes;"
                )
                conn = pyodbc.connect(dsn, timeout=20)'''

NEW_DDL_DSN = '''                conn = make_mssql_conn(
                    c['host'], c['port'], c['username'],
                    c.get('password',''), c['database'], timeout=20
                )'''

if OLD_DDL_DSN in content:
    content = content.replace(OLD_DDL_DSN, NEW_DDL_DSN)
    print('DDL_CREATE 블록 DSN 교체 완료')
else:
    print('주의: DDL_CREATE 블록 DSN 패턴을 찾지 못함')

# ── 6. get_object_ddl 블록 DSN 교체 ──────────────────────
OLD_DDL2 = '''            import pyodbc
            dsn = (f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                   f"SERVER={host},{port};DATABASE={database};"
                   f"UID={username};PWD={password};TrustServerCertificate=yes;")
            conn = pyodbc.connect(dsn, timeout=8)'''

NEW_DDL2 = '''            conn = make_mssql_conn(host, port, username, password, database, timeout=8)'''

if OLD_DDL2 in content:
    content = content.replace(OLD_DDL2, NEW_DDL2)
    print('get_object_ddl DSN 교체 완료')
else:
    print('주의: get_object_ddl DSN 패턴을 찾지 못함')

# ── 7. test_object_execution 블록 DSN 교체 ────────────────
OLD_TEST = '''            import pyodbc
            dsn = (f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                   f"SERVER={body['host']},{body['port']};DATABASE={body['database']};"
                   f"UID={body['username']};PWD={body.get('password','')};TrustServerCertificate=yes;")
            conn = pyodbc.connect(dsn, timeout=10)'''

NEW_TEST = '''            conn = make_mssql_conn(
                body['host'], body['port'], body['username'],
                body.get('password',''), body['database'], timeout=10
            )'''

if OLD_TEST in content:
    content = content.replace(OLD_TEST, NEW_TEST)
    print('test_object_execution DSN 교체 완료')
else:
    print('주의: test_object_execution DSN 패턴을 찾지 못함')

# ── 8. test_object_mssql 실행 블록 DSN 교체 ─────────────
OLD_EXEC = '''        elif db_type in ("mssql","azure"):
            import pyodbc
            dsn = (f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                   f"SERVER={c['host']},{c['port']};DATABASE={c['database']};"
                   f"UID={c['username']};PWD={c.get('password','')};TrustServerCertificate=yes;")
            conn = pyodbc.connect(dsn, timeout=10)'''

NEW_EXEC = '''        elif db_type in ("mssql","azure"):
            conn = make_mssql_conn(
                c['host'], c['port'], c['username'],
                c.get('password',''), c['database'], timeout=10
            )'''

if OLD_EXEC in content:
    content = content.replace(OLD_EXEC, NEW_EXEC)
    print('실행 블록 DSN 교체 완료')
else:
    print('주의: 실행 블록 DSN 패턴을 찾지 못함')

# ── 포트 기본값 수정 ───────────────────────────────────
content = content.replace(
    '"port":     port     or _conns.get(side,{}).get("port",3306)',
    '"port":     port     or _conns.get(side,{}).get("port")'
    ' or default_port(db_type or _conns.get(side,{}).get("db_type","mysql"))'
)
content = content.replace(
    'h, p    = c.get("host",""), int(c.get("port", 3306))',
    'h       = c.get("host","")\n    p       = get_port(c)'
)
print('포트 기본값 수정 완료')

# ── 9. 남은 ODBC 18 → 17 통일 ────────────────────────────
remaining_18 = content.count('ODBC Driver 18 for SQL Server')
content = content.replace('ODBC Driver 18 for SQL Server', 'ODBC Driver 17 for SQL Server')
if remaining_18:
    print(f'ODBC Driver 18 → 17 변경: {remaining_18}곳')

# ── 10. 남은 DSN에 Encrypt=no 추가 ───────────────────────
content = content.replace(
    'TrustServerCertificate=yes;")',
    'TrustServerCertificate=yes;Encrypt=no;")'
)
content = content.replace(
    "TrustServerCertificate=yes;')",
    "TrustServerCertificate=yes;Encrypt=no;')"
)
# 중복 방지
content = content.replace(
    'TrustServerCertificate=yes;Encrypt=no;Encrypt=no;',
    'TrustServerCertificate=yes;Encrypt=no;'
)

# ── 저장 ──────────────────────────────────────────────────
open(SRC, 'w', encoding='utf-8').write(content)

# ── 검증 ──────────────────────────────────────────────────
print()
try:
    ast.parse(content)
    print('✓ 문법 OK')
except SyntaxError as e:
    print(f'✗ 문법 오류: {e}')
    print(f'  백업에서 복구: copy {bak} {SRC}')
    exit(1)

# 남은 문제 확인
lines = content.split('\n')
drv18  = [(i+1, l.strip()) for i,l in enumerate(lines) if 'ODBC Driver 18' in l]
direct = [(i+1, l.strip()) for i,l in enumerate(lines) if 'pyodbc.connect(' in l]

if drv18:
    print(f'\n남은 ODBC Driver 18 ({len(drv18)}곳):')
    for ln, l in drv18: print(f'  {ln}: {l}')
else:
    print('✓ ODBC Driver 18 없음')

if direct:
    print(f'\n직접 pyodbc.connect 호출 ({len(direct)}곳):')
    for ln, l in direct: print(f'  {ln}: {l}')
else:
    print('✓ 직접 pyodbc.connect 없음')

print('\n완료! 백엔드 재시작:')
print('python -m uvicorn main:app --port 8000')
