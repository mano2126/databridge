"""
fix_schema_final.py
backend 폴더에서 실행: python fix_schema_final.py

schema.py 안의 모든 MSSQL 하드코딩 DSN을
make_mssql_conn() 호출로 교체합니다.
"""
import re, shutil
from datetime import datetime

SRC = 'app/api/routes/schema.py'

# 백업
bak = SRC + '.' + datetime.now().strftime('%H%M%S') + '.bak'
shutil.copy2(SRC, bak)
print(f'백업: {bak}')

content = open(SRC, encoding='utf-8').read()

# ── 1. import 추가 ────────────────────────────────────────
if 'from app.core.db_conn import' not in content:
    content = content.replace(
        'from fastapi import APIRouter, HTTPException',
        'from fastapi import APIRouter, HTTPException\n'
        'from app.core.db_conn import make_mssql_conn, make_conn, get_port, default_port'
    )
    print('import 추가 완료')
else:
    print('import 이미 있음')

# ── 2. 모든 pyodbc 하드코딩 DSN 블록 교체 ────────────────
# 패턴: import pyodbc + dsn = (...) + conn = pyodbc.connect(dsn, timeout=N)
# 호스트/포트/유저/패스워드/DB 변수명이 제각각이라 범용 패턴으로 처리

def replace_dsn_block(text):
    """
    pyodbc 직접 연결 블록을 make_mssql_conn() 으로 교체.
    변수명을 추출해서 그대로 사용.
    """
    # 패턴: import pyodbc\n    dsn=(..)\n    conn=pyodbc.connect(dsn, timeout=N)
    pattern = re.compile(
        r'import pyodbc\s*\n'
        r'(\s*)dsn\s*=\s*\('
        r'.*?'
        r'SERVER=([^;,]+),([^;]+);DATABASE=([^;]+);'
        r'.*?'
        r'UID=([^;]+);PWD=([^;]+);'
        r'.*?\)'
        r'\s*\n'
        r'\1conn\s*=\s*pyodbc\.connect\(dsn,\s*timeout=(\d+)\)',
        re.DOTALL
    )
    
    def replacer(m):
        indent  = m.group(1)
        host    = m.group(2).strip()
        port    = m.group(3).strip().rstrip("'\"")
        db      = m.group(4).strip()
        user    = m.group(5).strip()
        pwd     = m.group(6).strip()
        timeout = m.group(7)
        return (
            f"{indent}conn = make_mssql_conn(\n"
            f"{indent}    {host}, {port}, {user}, {pwd}, {db}, timeout={timeout}\n"
            f"{indent})"
        )
    
    return pattern.sub(replacer, text)

content = replace_dsn_block(content)

# ── 3. 더 단순한 방식: 특정 함수들을 통째로 교체 ─────────

# _mssql_tables
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
            JOIN sys.partitions p2
              ON t.object_id=p2.object_id AND p2.index_id IN(0,1)
            ORDER BY s.name, t.name
        """)
        return [{"schema_name": r[0], "table_name": r[1],
                 "row_count": r[2] or 0, "size_mb": 0, "comment": ""}
                for r in cur.fetchall()]
    finally:
        conn.close()''',
    content, flags=re.DOTALL
)
print('_mssql_tables 교체 완료')

# _get_objects_mssql
content = re.sub(
    r'def _get_objects_mssql\(h, p, u, pw, db\):.*?finally:\s*conn\.close\(\)\s*return result',
    '''def _get_objects_mssql(h, p, u, pw, db):
    """MSSQL 오브젝트 목록"""
    conn = make_mssql_conn(h, p, u, pw, db)
    result = {}
    try:
        cur = conn.cursor()
        cur.execute("""SELECT o.name, o.create_date, o.modify_date, m.definition
                       FROM sys.objects o LEFT JOIN sys.sql_modules m ON o.object_id=m.object_id
                       WHERE o.type=\'P\' ORDER BY o.name""")
        result["procedures"] = [{"name":r[0],"type":"PROCEDURE","created":str(r[1]),"body":r[3] or ""} for r in cur.fetchall()]
        cur.execute("""SELECT o.name, o.create_date, m.definition
                       FROM sys.objects o LEFT JOIN sys.sql_modules m ON o.object_id=m.object_id
                       WHERE o.type IN (\'FN\',\'IF\',\'TF\') ORDER BY o.name""")
        result["functions"] = [{"name":r[0],"type":"FUNCTION","created":str(r[1]),"body":r[2] or ""} for r in cur.fetchall()]
        cur.execute("""SELECT t.name, o.name AS tbl, m.definition
                       FROM sys.triggers t JOIN sys.objects o ON t.parent_id=o.object_id
                       LEFT JOIN sys.sql_modules m ON t.object_id=m.object_id""")
        result["triggers"] = [{"name":r[0],"type":"TRIGGER","table":r[1],"body":r[2] or ""} for r in cur.fetchall()]
        cur.execute("""SELECT o.name, m.definition FROM sys.views o
                       LEFT JOIN sys.sql_modules m ON o.object_id=m.object_id ORDER BY o.name""")
        result["views"] = [{"name":r[0],"type":"VIEW","body":r[1] or ""} for r in cur.fetchall()]
    finally:
        conn.close()
    return result''',
    content, flags=re.DOTALL
)
print('_get_objects_mssql 교체 완료')

# ── 4. get_objects 엔드포인트 포트 처리 수정 ─────────────
content = content.replace(
    '"port":     port     or _conns.get(side,{}).get("port",3306)',
    '"port":     port     or _conns.get(side,{}).get("port") or default_port(db_type or _conns.get(side,{}).get("db_type","mysql"))'
)
content = content.replace(
    '"port":     port     or _conns.get(side,{}).get("port",3306),',
    '"port":     port     or _conns.get(side,{}).get("port") or default_port(db_type or _conns.get(side,{}).get("db_type","mysql")),'
)
print('포트 기본값 수정 완료')

# ── 5. 남은 모든 pyodbc 하드코딩에 Encrypt=no 추가 ────────
# TrustServerCertificate=yes 뒤에 Encrypt=no 없으면 추가
content = re.sub(
    r'TrustServerCertificate=yes;(?!Encrypt)',
    'TrustServerCertificate=yes;Encrypt=no;',
    content
)
# ODBC Driver 18 → 17 (Driver 17이 설치된 환경)
# 실제로는 make_mssql_conn이 자동 감지하므로, 남은 하드코딩만 처리
# make_mssql_conn을 못 쓰는 인라인 코드는 18→17로 통일
content = content.replace(
    'ODBC Driver 18 for SQL Server',
    'ODBC Driver 17 for SQL Server'
)
print('Encrypt=no 및 드라이버 버전 수정 완료')

# ── 6. _query_tables 포트 처리 ───────────────────────────
content = content.replace(
    'h, p    = c.get("host",""), int(c.get("port", 3306))',
    'h       = c.get("host","")\n    p       = get_port(c)'
)

# ── 저장 ──────────────────────────────────────────────────
open(SRC, 'w', encoding='utf-8').write(content)

# ── 검증 ──────────────────────────────────────────────────
import ast
try:
    ast.parse(content)
    print(f'\n✓ {SRC} 문법 OK')
except SyntaxError as e:
    print(f'\n✗ 문법 오류: {e}')
    print('백업에서 복구하세요:', bak)

# 남은 ODBC 18 확인
remaining = [(i+1, l) for i, l in enumerate(content.split('\n'))
             if 'ODBC Driver 18' in l]
if remaining:
    print(f'\n남은 ODBC Driver 18 ({len(remaining)}곳):')
    for ln, line in remaining:
        print(f'  {ln}: {line.strip()}')
else:
    print('✓ ODBC Driver 18 하드코딩 없음')

# 남은 pyodbc.connect 직접 호출 확인
direct = [(i+1, l) for i, l in enumerate(content.split('\n'))
          if 'pyodbc.connect(' in l]
if direct:
    print(f'\n직접 pyodbc.connect 호출 ({len(direct)}곳):')
    for ln, line in direct:
        print(f'  {ln}: {line.strip()}')
else:
    print('✓ 직접 pyodbc.connect 호출 없음')

print('\n완료! 백엔드를 재시작하세요:')
print('python -m uvicorn main:app --port 8000')
