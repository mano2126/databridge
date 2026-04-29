"""
fix_final.py
backend 폴더에서 실행: python fix_final.py

두 가지 수정:
1. schema.py 의 모든 DSN에서 Encrypt=no → Connection Timeout=8 로 교체
   (커넥터 테스트 성공 DSN과 동일하게 맞춤)
2. main.py 에 pyodbc.pooling = False 추가
   (uvicorn 멀티스레드 환경에서 pyodbc 안정성 확보)
"""
import shutil, ast
from datetime import datetime

# ── 1. schema.py 수정 ─────────────────────────────────────
print("=== schema.py 수정 ===")

path = 'app/api/routes/schema.py'
bak  = path + '.' + datetime.now().strftime('%H%M%S') + '.bak'
shutil.copy2(path, bak)
print(f'백업: {bak}')

content = open(path, encoding='utf-8').read()

# Encrypt=no; → Connection Timeout=8;
old_str = 'TrustServerCertificate=yes;Encrypt=no;'
new_str = 'TrustServerCertificate=yes;Connection Timeout=8;'

count = content.count(old_str)
content = content.replace(old_str, new_str)
print(f'Encrypt=no → Connection Timeout=8 교체: {count}곳')

# 문법 확인
try:
    ast.parse(content)
    print('✓ schema.py 문법 OK')
except SyntaxError as e:
    print(f'✗ 문법 오류: {e}')
    print(f'복구: copy {bak} {path}')
    exit(1)

open(path, 'w', encoding='utf-8').write(content)

# ── 2. main.py 수정 ───────────────────────────────────────
print("\n=== main.py 수정 ===")

main_path = 'main.py'
main_bak  = main_path + '.' + datetime.now().strftime('%H%M%S') + '.bak'
shutil.copy2(main_path, main_bak)
print(f'백업: {main_bak}')

main_content = open(main_path, encoding='utf-8').read()

# pyodbc.pooling = False 추가 (uvicorn 스레드 풀 환경에서 필수)
pooling_code = '''
# ── pyodbc 스레드 안전성 설정 ─────────────────────────────
# uvicorn 멀티스레드 환경에서 pyodbc 연결 풀링 비활성화
try:
    import pyodbc as _pyodbc_init
    _pyodbc_init.pooling = False
    print('[DataBridge] pyodbc.pooling = False 설정 완료', flush=True)
except ImportError:
    pass
'''

# _patch_pyodbc() 함수 앞에 삽입
if 'pyodbc.pooling = False' not in main_content:
    main_content = main_content.replace(
        '# ── pyodbc 전역 패치 ──────────────────────────────────────',
        pooling_code + '\n# ── pyodbc 전역 패치 ──────────────────────────────────────'
    )
    print('pyodbc.pooling = False 추가 완료')
else:
    print('pyodbc.pooling = False 이미 있음')

# 패치 함수에서 Encrypt 제거 로직도 단순화
# (schema.py가 이미 Connection Timeout=8 을 쓰므로 패치 단순화)
try:
    ast.parse(main_content)
    print('✓ main.py 문법 OK')
except SyntaxError as e:
    print(f'✗ 문법 오류: {e}')
    exit(1)

open(main_path, 'w', encoding='utf-8').write(main_content)

# ── 결과 확인 ─────────────────────────────────────────────
print("\n=== 수정 결과 확인 ===")
final = open(path, encoding='utf-8').read()
remaining_encrypt = final.count('Encrypt=no')
remaining_timeout = final.count('Connection Timeout=8')
print(f'schema.py 남은 Encrypt=no: {remaining_encrypt}개')
print(f'schema.py Connection Timeout=8: {remaining_timeout}개')
print(f'main.py pyodbc.pooling=False: {"있음" if "pooling = False" in open(main_path).read() else "없음"}')

print('\n완료! 백엔드 재시작:')
print('python -m uvicorn main:app --port 8000')
