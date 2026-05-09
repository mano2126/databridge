"""
fix_db_type.py
backend 폴더에서 실행: python fix_db_type.py

_connect_src 에서 pyodbc 연결 객체에
커스텀 속성(_db_type)을 할당하는 잘못된 코드를 제거합니다.
"""
import shutil, ast
from datetime import datetime

path = 'app/api/routes/jobs.py'
bak  = path + '.' + datetime.now().strftime('%H%M%S') + '.bak'
shutil.copy2(path, bak)

content = open(path, encoding='utf-8').read()

# 잘못된 줄 제거
OLD = '''                conn = pyodbc.connect(dsn)
                # MSSQL 커서를 DictCursor처럼 동작하도록 래핑
                conn._db_type = "mssql"
                return conn'''

NEW = '''                conn = pyodbc.connect(dsn)
                return conn'''

if OLD in content:
    content = content.replace(OLD, NEW)
    print('_db_type 속성 할당 제거 완료')
else:
    print('패턴 없음 — 이미 수정됐거나 다른 버전')

ast.parse(content)
open(path, 'w', encoding='utf-8').write(content)
print('✓ 완료! 백엔드 재시작:')
print('python -m uvicorn main:app --port 8000')
