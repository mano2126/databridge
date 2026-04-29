"""MysqlLoadDataLoader 신규 추가 smoke test.

DB 없이 돌릴 수 있는 것만:
1. import 체크
2. _mysql_load_stringify 경계 케이스
3. create_loader(mode=...) 분기 로직
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

print("── 1. import 테스트 ──")
from app.engine.bulk_loader import (
    MysqlLoadDataLoader,
    ExecutemanyLoader,
    MssqlBcpLoader,
    MssqlPymssqlLoader,
    BulkLoadError,
    create_loader,
    _mysql_load_stringify,
)
print("  OK — 모든 심볼 import 성공")

print("\n── 2. _mysql_load_stringify 경계 케이스 ──")
cases = [
    (None, "\\N"),
    (True, "1"),
    (False, "0"),
    (42, "42"),
    (3.14, "3.14"),
    ("hello", "hello"),
    ("tab\there", "tab\there"),
    ("sep\x1fchar", "sep char"),     # FIELD_SEP 포함 시 공백 치환
    ("rec\x1esep", "rec sep"),       # ROW_SEP 포함 시 공백 치환
    (b"\x00\xff", "0x00FF"),         # bytes → hex
    ("\\N", "\\\\N"),                 # NULL 표기 충돌 → 이스케이프
    ("", ""),
]
fail = 0
for inp, expected in cases:
    got = _mysql_load_stringify(inp)
    ok = (got == expected)
    mark = "✓" if ok else "✗"
    print(f"  {mark} {inp!r:25s} → {got!r} (expected {expected!r})")
    if not ok:
        fail += 1
assert fail == 0, f"{fail} cases failed"

print("\n── 3. create_loader 분기 로직 (DB 연결 없이) ──")

# Mock LogSink
logs = []
def mklog():
    return lambda lv, m: logs.append((lv, m))

# (a) mode=executemany → ExecutemanyLoader (타겟 무관)
ldr = create_loader(
    mode="executemany", table="t", col_names=["a"], tgt_conn=None,
    tgt_is_mssql=False, tgt_is_mysql=True,
    insert_sql="INSERT INTO t(a) VALUES(%s)",
)
assert isinstance(ldr, ExecutemanyLoader), f"got {type(ldr).__name__}"
print("  ✓ mode=executemany → ExecutemanyLoader")

# (b) mode=mysql_load + tgt_is_mysql=False → BulkLoadError
try:
    create_loader(
        mode="mysql_load", table="t", col_names=["a"], tgt_conn=None,
        tgt_is_mssql=True, tgt_is_mysql=False,
        insert_sql="",
    )
    assert False, "예외가 올라와야 함"
except BulkLoadError as e:
    assert "MySQL 타겟" in str(e)
    print(f"  ✓ mode=mysql_load + MSSQL 타겟 → BulkLoadError: {e}")

# (c) mode=bcp + tgt_is_mssql=False → BulkLoadError
try:
    create_loader(
        mode="bcp", table="t", col_names=["a"], tgt_conn=None,
        tgt_is_mssql=False, tgt_is_mysql=True,
        insert_sql="",
    )
    assert False
except BulkLoadError as e:
    print(f"  ✓ mode=bcp + MySQL 타겟 → BulkLoadError: {e}")

# (d) mode=auto + 소량 → ExecutemanyLoader
ldr = create_loader(
    mode="auto", table="t", col_names=["a"], tgt_conn=None,
    tgt_is_mssql=False, tgt_is_mysql=True,
    insert_sql="INSERT INTO t(a) VALUES(%s)",
    row_count=100,  # 임계 미만
)
assert isinstance(ldr, ExecutemanyLoader), f"got {type(ldr).__name__}"
print("  ✓ mode=auto + row_count=100 + MySQL → ExecutemanyLoader (임계 미만)")

# (e) mode=auto + 대량 + MySQL + DB 없음 → LOAD 시도하다 BulkLoadError 잡고 executemany 폴백
#     (open() 에서 pymysql.connect 실패)
ldr = create_loader(
    mode="auto", table="t", col_names=["a"], tgt_conn=None,
    tgt_is_mssql=False, tgt_is_mysql=True,
    insert_sql="INSERT INTO t(a) VALUES(%s)",
    row_count=1_000_000,
    job={
        "tgt_host": "127.0.0.1", "tgt_port": 13306,   # 존재하지 않는 포트
        "tgt_username": "x", "tgt_password": "x", "tgt_database": "x",
    },
    log=mklog(),
)
assert isinstance(ldr, ExecutemanyLoader), f"got {type(ldr).__name__}"
# warn 로그에 "MySQL LOAD DATA 불가" 있어야 함
assert any("MySQL LOAD DATA 불가" in m for lv, m in logs), f"logs={logs}"
print("  ✓ mode=auto + 대량 + MySQL + 연결실패 → ExecutemanyLoader 로 폴백, warn 로그 기록")

# (f) 시그니처 하위호환 — tgt_is_mysql 미지정 (기존 호출부)
ldr = create_loader(
    mode="auto", table="t", col_names=["a"], tgt_conn=None,
    tgt_is_mssql=False,
    insert_sql="INSERT INTO t(a) VALUES(%s)",
    row_count=100,
)
assert isinstance(ldr, ExecutemanyLoader)
print("  ✓ tgt_is_mysql 미지정 (기존 호출부) → 동작 유지")

print("\n✅ 모든 테스트 통과")
