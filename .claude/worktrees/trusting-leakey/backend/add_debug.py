"""
add_debug.py
backend 폴더에서 실행: python add_debug.py

schema.py 의 테이블/오브젝트 조회 함수에 디버그 로그를 추가합니다.
"""
import shutil
from datetime import datetime

SRC = 'app/api/routes/schema.py'
bak = SRC + '.' + datetime.now().strftime('%H%M%S') + '.bak'
shutil.copy2(SRC, bak)

content = open(SRC, encoding='utf-8').read()

# tables 엔드포인트에 디버그 추가
OLD_TABLES = '''    try:
        return _query_tables(c)
    except Exception as e:
        raise HTTPException(500, f"테이블 조회 실패: {e}")'''

NEW_TABLES = '''    try:
        print(f"[DEBUG tables] c={c}", flush=True)
        result = _query_tables(c)
        print(f"[DEBUG tables] 성공: {len(result)}개", flush=True)
        return result
    except Exception as e:
        import traceback
        print(f"[DEBUG tables] 오류: {e}", flush=True)
        print(traceback.format_exc(), flush=True)
        raise HTTPException(500, f"테이블 조회 실패: {e}")'''

if OLD_TABLES in content:
    content = content.replace(OLD_TABLES, NEW_TABLES)
    print('tables 디버그 추가 완료')
else:
    print('주의: tables 패턴 찾지 못함')

# objects 엔드포인트에 디버그 추가
OLD_OBJECTS = '''    except Exception as e:
        raise HTTPException(500, f"오브젝트 조회 실패: {e}")'''

NEW_OBJECTS = '''    except Exception as e:
        import traceback
        print(f"[DEBUG objects] 오류: {e}", flush=True)
        print(traceback.format_exc(), flush=True)
        raise HTTPException(500, f"오브젝트 조회 실패: {e}")'''

if OLD_OBJECTS in content:
    content = content.replace(OLD_OBJECTS, NEW_OBJECTS)
    print('objects 디버그 추가 완료')
else:
    print('주의: objects 패턴 찾지 못함')

open(SRC, 'w', encoding='utf-8').write(content)
print(f'\n완료! 백업: {bak}')
print('백엔드 재시작: python -m uvicorn main:app --port 8000')
