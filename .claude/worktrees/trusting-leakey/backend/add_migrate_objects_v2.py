"""
add_migrate_objects_v2.py
backend 폴더에서 실행: python add_migrate_objects_v2.py

migrate_objects_method.txt 파일을 읽어서
MigrationEngine에 _migrate_objects 메서드를 추가합니다.
"""
import shutil, ast, warnings
warnings.filterwarnings("ignore", category=SyntaxWarning)
from datetime import datetime

path = 'app/api/routes/jobs.py'
bak  = path + '.' + datetime.now().strftime('%H%M%S') + '.bak'
shutil.copy2(path, bak)
print(f'백업: {bak}')

content = open(path, encoding='utf-8').read()

if 'def _migrate_objects' in content:
    print('_migrate_objects 이미 존재 — 재삽입 (덮어쓰기)')
    # 기존 것 제거
    s_idx = content.find('\n    def _migrate_objects(')
    e_idx = content.find('\n    def _migrate_table(')
    if s_idx != -1 and e_idx != -1:
        content = content[:s_idx] + content[e_idx:]
        print('기존 _migrate_objects 제거')

# migrate_objects_method.txt 읽기
try:
    new_method = open('migrate_objects_method.txt', encoding='utf-8').read()
    print(f'migrate_objects_method.txt 로드 ({len(new_method)} bytes)')
except FileNotFoundError:
    print('오류: migrate_objects_method.txt 파일 없음')
    print('add_migrate_objects_v2.py 와 같은 폴더에 migrate_objects_method.txt 가 있어야 합니다')
    exit(1)

# _migrate_table 바로 앞에 삽입
INSERT_BEFORE = '\n    def _migrate_table('
idx = content.find(INSERT_BEFORE)
if idx == -1:
    print('오류: _migrate_table 을 찾을 수 없음')
    exit(1)

new_content = content[:idx] + new_method + content[idx:]

try:
    ast.parse(new_content)
    print('✓ 문법 OK')
except SyntaxError as e:
    lines = new_content.split('\n')
    print(f'✗ 문법 오류 {e.lineno}: {e.msg}')
    for i, ln in enumerate(lines[max(0,e.lineno-3):e.lineno+3], max(1,e.lineno-2)):
        print(f'{i}: {ln}')
    print(f'복구: copy {bak} {path}')
    exit(1)

open(path, 'w', encoding='utf-8').write(new_content)
print('_migrate_objects 추가 완료')
print('\n재시작:')
print('python -m uvicorn main:app --port 8000')
