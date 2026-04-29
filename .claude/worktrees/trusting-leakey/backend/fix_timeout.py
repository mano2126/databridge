"""
fix_timeout.py
backend 폴더에서 실행: python fix_timeout.py

schema.py 의 pyodbc.connect(dsn, timeout=N) 에서
timeout 인수를 제거합니다.
직접 실행은 성공하지만 uvicorn 에서 실패하는 원인입니다.
"""
import shutil, ast
from datetime import datetime

files = [
    'app/api/routes/schema.py',
    'app/api/routes/validate.py',
    'app/api/routes/jobs.py',
    'app/api/routes/connector.py',
]

for path in files:
    try:
        content = open(path, encoding='utf-8').read()

        # pyodbc.connect(dsn, timeout=N) → pyodbc.connect(dsn)
        import re
        new = re.sub(
            r'pyodbc\.connect\(([^,)]+),\s*timeout=\d+\)',
            r'pyodbc.connect(\1)',
            content
        )

        if new == content:
            print(f'{path}: 변경 없음')
            continue

        # 백업
        bak = path + '.' + datetime.now().strftime('%H%M%S') + '.bak'
        shutil.copy2(path, bak)

        # 저장
        open(path, 'w', encoding='utf-8').write(new)

        # 문법 확인
        ast.parse(new)

        count = len(re.findall(r'pyodbc\.connect\(', content)) - \
                len(re.findall(r'pyodbc\.connect\(', new)) + \
                len(re.findall(r'pyodbc\.connect\(', new))
        changed = content.count('timeout=') - new.count('timeout=')
        print(f'{path}: timeout 인수 {changed}개 제거 완료')

    except SyntaxError as e:
        print(f'{path}: 문법 오류 — {e}')
    except FileNotFoundError:
        print(f'{path}: 파일 없음 — 스킵')

print('\n완료! 백엔드 재시작:')
print('python -m uvicorn main:app --port 8000')
