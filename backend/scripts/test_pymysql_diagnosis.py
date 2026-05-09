"""
test_pymysql_diagnosis.py — DataBridge 와 정확히 동일한 흐름으로 진단

본부장님 환경에서 실행:
  cd D:\project\databridge_full\backend
  python test_pymysql_diagnosis.py
"""
import sys, traceback
import pymysql

HOST = "127.0.0.1"
PORT = 3306
USER = "root"
PASS = "bridge1234"
DB   = "testdb"

print("=" * 70)
print(" pymysql 호출 방식별 진단 (5가지 테스트)")
print("=" * 70)

def make_conn():
    return pymysql.connect(
        host=HOST, port=PORT, user=USER, password=PASS,
        database=DB, charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

# ── Test 1: cur.callproc (이전 방식) ──
print("\n[Test 1] cur.callproc — DataBridge 의 이전 방식")
try:
    conn = make_conn()
    cur = conn.cursor()
    cur.callproc('SP_TEST_DAILY_AGG', ['20240101', '20240101'])
    print("  ✅ 성공!")
    conn.close()
except Exception as e:
    print(f"  ❌ {type(e).__name__}: {e}")

# ── Test 2: cur.execute("CALL ... %s", params) — v90.77 방식 ──
print("\n[Test 2] cur.execute('CALL `xxx`(%s,%s)', params) — v90.77 방식")
try:
    conn = make_conn()
    cur = conn.cursor()
    cur.execute("CALL `SP_TEST_DAILY_AGG`(%s, %s)", ['20240101', '20240101'])
    print("  ✅ 성공!")
    conn.close()
except Exception as e:
    print(f"  ❌ {type(e).__name__}: {e}")

# ── Test 3: mogrify 로 SQL 미리 만들어서 단순 execute ──
print("\n[Test 3] mogrify → execute(SQL) — 가장 단순한 방식")
try:
    conn = make_conn()
    cur = conn.cursor()
    sql = cur.mogrify("CALL `SP_TEST_DAILY_AGG`(%s, %s)", ['20240101', '20240101'])
    print(f"  생성된 SQL: {sql}")
    cur.execute(sql)
    print("  ✅ 성공!")
    conn.close()
except Exception as e:
    print(f"  ❌ {type(e).__name__}: {e}")

# ── Test 4: 따옴표 직접 박은 SQL execute ──
print("\n[Test 4] cur.execute(\"CALL `xxx`('20240101', '20240101')\") — 하드코딩")
try:
    conn = make_conn()
    cur = conn.cursor()
    cur.execute("CALL `SP_TEST_DAILY_AGG`('20240101', '20240101')")
    print("  ✅ 성공!")
    conn.close()
except Exception as e:
    print(f"  ❌ {type(e).__name__}: {e}")

# ── Test 5: utf8mb4_unicode_ci 명시 collation ──
print("\n[Test 5] CHARSET 강제 + COLLATION 강제")
try:
    conn = make_conn()
    cur = conn.cursor()
    cur.execute("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci")
    cur.callproc('SP_TEST_DAILY_AGG', ['20240101', '20240101'])
    print("  ✅ 성공!")
    conn.close()
except Exception as e:
    print(f"  ❌ {type(e).__name__}: {e}")

# ── Test 6: connection 시 init_command ──
print("\n[Test 6] connect(init_command='SET NAMES utf8mb4...')")
try:
    conn = pymysql.connect(
        host=HOST, port=PORT, user=USER, password=PASS,
        database=DB, charset='utf8mb4',
        init_command="SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci",
        cursorclass=pymysql.cursors.DictCursor
    )
    cur = conn.cursor()
    cur.callproc('SP_TEST_DAILY_AGG', ['20240101', '20240101'])
    print("  ✅ 성공!")
    conn.close()
except Exception as e:
    print(f"  ❌ {type(e).__name__}: {e}")

# ── Test 7: FN — SELECT 호출 ──
print("\n[Test 7] FN_TEST_TOTAL_AMT — SELECT FN(...) AS r")
try:
    conn = make_conn()
    cur = conn.cursor()
    cur.execute("SELECT `FN_TEST_TOTAL_AMT`(%s, %s) AS r", ['20240101', 'A'])
    result = cur.fetchall()
    print(f"  ✅ 성공: {result}")
    conn.close()
except Exception as e:
    print(f"  ❌ {type(e).__name__}: {e}")

print("\n" + "=" * 70)
print(" 결론 가이드:")
print(" - Test 1 ❌ Test 2 ✅ → v90.77 정확. FastAPI 강제 재시작 필요")
print(" - Test 1 ❌ Test 2 ❌ Test 3 ✅ → mogrify 패턴이 답 (v90.79 만들어야)")
print(" - Test 1 ❌ Test 2 ❌ Test 3 ❌ Test 4 ✅ → placeholder 자체가 문제")
print(" - Test 5/6 ✅ → SET NAMES init_command 가 fix (가장 깔끔)")
print(" - 모두 ❌ → MySQL 서버 자체 또는 SP 변환 자체 문제")
print("=" * 70)