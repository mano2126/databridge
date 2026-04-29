"""
fix_driver.py
backend 폴더에서 실행: python fix_driver.py

schema.py 의 ODBC Driver 17 → 18 로 복구합니다.
(이전 fix 스크립트가 잘못 변경한 것을 되돌립니다)
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

        count = content.count('ODBC Driver 17 for SQL Server')
        if count == 0:
            print(f'{path}: 변경 없음 (이미 18 사용 중)')
            continue

        # 백업
        bak = path + '.' + datetime.now().strftime('%H%M%S') + '.bak'
        shutil.copy2(path, bak)

        # 17 → 18 교체
        new = content.replace('ODBC Driver 17 for SQL Server',
                              'ODBC Driver 18 for SQL Server')
        open(path, 'w', encoding='utf-8').write(new)

        # 문법 확인
        ast.parse(new)
        print(f'{path}: Driver 17 → 18 교체 완료 ({count}곳)')

    except SyntaxError as e:
        print(f'{path}: 문법 오류 — {e}')
    except FileNotFoundError:
        print(f'{path}: 파일 없음 — 스킵')

print('\n완료! 백엔드 재시작:')
print('python -m uvicorn main:app --port 8000')
