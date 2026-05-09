"""
fix_concurrent.py
backend 폴더에서 실행: python fix_concurrent.py

1. main.py - pyodbc.pooling=False 를 파일 최상단으로 이동
2. schema.py - get_objects 실패 시 500 대신 빈 결과 반환
              (프로시저/함수/뷰가 없는 DB에서 정상 동작)
"""
import shutil, ast, re
from datetime import datetime

# ── 1. schema.py 수정 ─────────────────────────────────────
print("=== schema.py 수정 ===")
path = 'app/api/routes/schema.py'
bak  = path + '.' + datetime.now().strftime('%H%M%S') + '.bak'
shutil.copy2(path, bak)

content = open(path, encoding='utf-8').read()

# get_objects 엔드포인트에서 예외 발생 시 500 대신 빈 결과 반환
OLD = '''    except Exception as e:
        raise HTTPException(500, f"오브젝트 조회 실패: {e}")'''

NEW = '''    except Exception as e:
        import traceback as _tb
        print(f"[objects 오류 — 빈 결과 반환] {e}", flush=True)
        print(_tb.format_exc(), flush=True)
        return {"procedures": [], "functions": [], "triggers": [], "views": []}'''

if OLD in content:
    content = content.replace(OLD, NEW)
    print('get_objects 예외처리 수정 완료')
else:
    print('주의: 패턴 없음 — 수동 확인 필요')

ast.parse(content)
open(path, 'w', encoding='utf-8').write(content)
print('✓ schema.py 문법 OK')

# ── 2. main.py 수정 ───────────────────────────────────────
print("\n=== main.py 수정 ===")
main_path = 'main.py'
main_bak  = main_path + '.' + datetime.now().strftime('%H%M%S') + '.bak'
shutil.copy2(main_path, main_bak)

main_content = open(main_path, encoding='utf-8').read()

# pyodbc.pooling = False 를 파일 최상단 (import 이전)으로 이동
# 기존 pooling 코드 제거
main_content = re.sub(
    r'# ── pyodbc 스레드 안전성 설정 .*?pass\s*\n',
    '', main_content, flags=re.DOTALL
)

# 파일 맨 위에 추가
pooling_header = '''# pyodbc 연결 풀링 비활성화 (uvicorn 멀티스레드 안전성)
# 반드시 다른 import 보다 먼저 실행되어야 함
try:
    import pyodbc as _p; _p.pooling = False
    print('[DataBridge] pyodbc.pooling=False', flush=True)
except ImportError:
    pass

'''

if 'pyodbc.pooling' not in main_content:
    main_content = pooling_header + main_content
    print('pyodbc.pooling=False 최상단 추가 완료')
else:
    print('pyodbc.pooling 이미 있음')

ast.parse(main_content)
open(main_path, 'w', encoding='utf-8').write(main_content)
print('✓ main.py 문법 OK')

print('\n완료! 백엔드 재시작:')
print('python -m uvicorn main:app --port 8000')
