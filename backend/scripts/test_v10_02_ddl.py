"""v10 #2 — _create_mysql_table 역방향 DDL 보강 검증.

목표
----
A. IDENTITY 타입 보존         — bigint IDENTITY → BIGINT AUTO_INCREMENT
B. nvarchar(max) 처리         — CHARACTER_MAXIMUM_LENGTH=-1 → LONGTEXT
C. max_length 바이트→문자    — nvarchar(50) 은 MSSQL 에서 max_length=100 으로 옴
D. DEFAULT 절 변환            — GETDATE/숫자/문자열/NEWID 등

DB 연결 없이 돌릴 수 있도록 conn 은 mock.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# MigrationEngine 은 job dict 만 있으면 인스턴스화 가능
from app.engine.migration_engine import MigrationEngine


class MockCursor:
    def __init__(self): self.executed = []
    def execute(self, sql, *a): self.executed.append(sql)
    def close(self): pass


class MockConn:
    def __init__(self): self.cur = MockCursor()
    def cursor(self): return self.cur
    def commit(self): pass


def make_engine():
    eng = MigrationEngine({"id": "test-job", "src_db": "mssql", "tgt_db": "mysql",
                           "auto_fix_actions": []})
    # _log 를 수집 리스트로 리다이렉트
    eng._collected_logs = []
    eng._log = lambda lv, m: eng._collected_logs.append((lv, m))
    return eng


def run_and_get_ddl(cols, src="mssql"):
    eng = make_engine()
    conn = MockConn()
    eng._create_mysql_table(conn, "T", cols, src)
    # execute 된 첫 번째 SQL = CREATE TABLE DDL
    assert conn.cur.executed, "DDL 이 실행되지 않음"
    return conn.cur.executed[0], eng


# ─────────────────────────────────────────────────────────────
# A. IDENTITY 타입 보존
# ─────────────────────────────────────────────────────────────
print("═══ A. IDENTITY 타입 보존 ═══")

ddl, _ = run_and_get_ddl([
    {"COLUMN_NAME": "id", "DATA_TYPE": "bigint", "EXTRA": "auto_increment",
     "COLUMN_KEY": "PRI", "IS_NULLABLE": "NO"}
])
assert "BIGINT NOT NULL AUTO_INCREMENT" in ddl, f"bigint IDENTITY 보존 실패\nDDL:\n{ddl}"
print("  ✓ bigint IDENTITY → BIGINT AUTO_INCREMENT")

ddl, _ = run_and_get_ddl([
    {"COLUMN_NAME": "id", "DATA_TYPE": "int", "EXTRA": "auto_increment",
     "COLUMN_KEY": "PRI", "IS_NULLABLE": "NO"}
])
assert "INT NOT NULL AUTO_INCREMENT" in ddl
print("  ✓ int IDENTITY → INT AUTO_INCREMENT")

ddl, _ = run_and_get_ddl([
    {"COLUMN_NAME": "id", "DATA_TYPE": "smallint", "EXTRA": "auto_increment",
     "COLUMN_KEY": "PRI", "IS_NULLABLE": "NO"}
])
assert "SMALLINT NOT NULL AUTO_INCREMENT" in ddl
print("  ✓ smallint IDENTITY → SMALLINT AUTO_INCREMENT")

ddl, _ = run_and_get_ddl([
    {"COLUMN_NAME": "id", "DATA_TYPE": "tinyint", "EXTRA": "auto_increment",
     "COLUMN_KEY": "PRI", "IS_NULLABLE": "NO"}
])
assert "TINYINT NOT NULL AUTO_INCREMENT" in ddl
print("  ✓ tinyint IDENTITY → TINYINT AUTO_INCREMENT")

# IDENTITY 가 아니면 AUTO_INCREMENT 없음
ddl, _ = run_and_get_ddl([
    {"COLUMN_NAME": "age", "DATA_TYPE": "int", "EXTRA": "",
     "COLUMN_KEY": "", "IS_NULLABLE": "YES"}
])
assert "AUTO_INCREMENT" not in ddl
print("  ✓ 일반 int 컬럼 → AUTO_INCREMENT 없음")

# ─────────────────────────────────────────────────────────────
# B. nvarchar(max) / varchar(max) 처리
# ─────────────────────────────────────────────────────────────
print("\n═══ B. nvarchar(max) → LONGTEXT ═══")

ddl, _ = run_and_get_ddl([
    {"COLUMN_NAME": "body", "DATA_TYPE": "nvarchar", "IS_NULLABLE": "YES",
     "CHARACTER_MAXIMUM_LENGTH": -1}
])
assert "`body` LONGTEXT" in ddl, f"nvarchar(max) → LONGTEXT 실패:\n{ddl}"
print("  ✓ nvarchar(max) → LONGTEXT")

ddl, _ = run_and_get_ddl([
    {"COLUMN_NAME": "body", "DATA_TYPE": "varchar", "IS_NULLABLE": "YES",
     "CHARACTER_MAXIMUM_LENGTH": -1}
])
assert "`body` LONGTEXT" in ddl
print("  ✓ varchar(max) → LONGTEXT")

ddl, _ = run_and_get_ddl([
    {"COLUMN_NAME": "blob_col", "DATA_TYPE": "varbinary", "IS_NULLABLE": "YES",
     "CHARACTER_MAXIMUM_LENGTH": -1}
])
assert "`blob_col` LONGBLOB" in ddl
print("  ✓ varbinary(max) → LONGBLOB")

# ─────────────────────────────────────────────────────────────
# C. MSSQL max_length 바이트 단위 → 문자 수 변환
# ─────────────────────────────────────────────────────────────
print("\n═══ C. 바이트→문자 변환 ═══")

# MSSQL 에서 nvarchar(50) 은 max_length = 100 (UTF-16, 2바이트/문자)
ddl, _ = run_and_get_ddl([
    {"COLUMN_NAME": "name", "DATA_TYPE": "nvarchar", "IS_NULLABLE": "YES",
     "CHARACTER_MAXIMUM_LENGTH": 100}
])
assert "VARCHAR(50)" in ddl, f"nvarchar(50) (100바이트) → VARCHAR(50) 실패:\n{ddl}"
print("  ✓ nvarchar(50) [max_length=100] → VARCHAR(50)")

# nchar(10) 은 max_length = 20
ddl, _ = run_and_get_ddl([
    {"COLUMN_NAME": "code", "DATA_TYPE": "nchar", "IS_NULLABLE": "YES",
     "CHARACTER_MAXIMUM_LENGTH": 20}
])
assert "CHAR(10)" in ddl
print("  ✓ nchar(10) [max_length=20] → CHAR(10)")

# varchar(100) 은 max_length = 100 (1바이트/문자) — 변환 없어야 함
ddl, _ = run_and_get_ddl([
    {"COLUMN_NAME": "descr", "DATA_TYPE": "varchar", "IS_NULLABLE": "YES",
     "CHARACTER_MAXIMUM_LENGTH": 100}
])
assert "VARCHAR(100)" in ddl, f"varchar(100) 길이 유지 실패:\n{ddl}"
print("  ✓ varchar(100) [max_length=100] → VARCHAR(100) (그대로)")

# 소스가 MySQL 이면 변환하지 않아야 함 (하위 호환)
ddl, _ = run_and_get_ddl([
    {"COLUMN_NAME": "name", "DATA_TYPE": "varchar", "IS_NULLABLE": "YES",
     "CHARACTER_MAXIMUM_LENGTH": 100}
], src="mysql")
assert "VARCHAR(100)" in ddl
print("  ✓ 소스=MySQL 일 때 길이 변환 미적용 (하위호환)")

# ─────────────────────────────────────────────────────────────
# D. DEFAULT 절 변환
# ─────────────────────────────────────────────────────────────
print("\n═══ D. DEFAULT 변환 ═══")

# D-1) GETDATE() → CURRENT_TIMESTAMP
ddl, _ = run_and_get_ddl([
    {"COLUMN_NAME": "created_at", "DATA_TYPE": "datetime2", "IS_NULLABLE": "YES",
     "COLUMN_DEFAULT": "(getdate())"}
])
assert "DEFAULT CURRENT_TIMESTAMP(6)" in ddl, f"GETDATE → CURRENT_TIMESTAMP(6) 실패:\n{ddl}"
print("  ✓ (getdate()) + datetime2 → DEFAULT CURRENT_TIMESTAMP(6)")

ddl, _ = run_and_get_ddl([
    {"COLUMN_NAME": "created_at", "DATA_TYPE": "datetime", "IS_NULLABLE": "YES",
     "COLUMN_DEFAULT": "(GETDATE())"}
])
# datetime → DATETIME(3) 이므로 CURRENT_TIMESTAMP(3)
assert "DEFAULT CURRENT_TIMESTAMP(3)" in ddl, f"GETDATE → CURRENT_TIMESTAMP(3) 실패:\n{ddl}"
print("  ✓ (GETDATE()) + datetime → DEFAULT CURRENT_TIMESTAMP(3)")

# D-2) 숫자 리터럴 (((0))) 깊은 괄호 포함
ddl, _ = run_and_get_ddl([
    {"COLUMN_NAME": "status", "DATA_TYPE": "int", "IS_NULLABLE": "NO",
     "COLUMN_DEFAULT": "((0))"}
])
assert "DEFAULT 0" in ddl, f"((0)) → DEFAULT 0 실패:\n{ddl}"
print("  ✓ ((0)) → DEFAULT 0")

ddl, _ = run_and_get_ddl([
    {"COLUMN_NAME": "price", "DATA_TYPE": "decimal", "IS_NULLABLE": "NO",
     "NUMERIC_PRECISION": 10, "NUMERIC_SCALE": 2,
     "COLUMN_DEFAULT": "((-123.45))"}
])
assert "DEFAULT -123.45" in ddl
print("  ✓ ((-123.45)) → DEFAULT -123.45")

# D-3) 문자열 리터럴
ddl, _ = run_and_get_ddl([
    {"COLUMN_NAME": "flag", "DATA_TYPE": "nvarchar", "IS_NULLABLE": "YES",
     "CHARACTER_MAXIMUM_LENGTH": 10,
     "COLUMN_DEFAULT": "(N'Y')"}
])
assert "DEFAULT 'Y'" in ddl, f"(N'Y') → DEFAULT 'Y' 실패:\n{ddl}"
print("  ✓ (N'Y') → DEFAULT 'Y'")

ddl, _ = run_and_get_ddl([
    {"COLUMN_NAME": "flag", "DATA_TYPE": "nvarchar", "IS_NULLABLE": "YES",
     "CHARACTER_MAXIMUM_LENGTH": 10,
     "COLUMN_DEFAULT": "('')"}
])
assert "DEFAULT ''" in ddl
print("  ✓ ('') → DEFAULT ''")

# D-4) NEWID() — MySQL DEFAULT 에 UUID() 못 쓰므로 생략 + info 로그
eng = make_engine()
conn = MockConn()
eng._create_mysql_table(conn, "T", [
    {"COLUMN_NAME": "id_g", "DATA_TYPE": "uniqueidentifier", "IS_NULLABLE": "NO",
     "COLUMN_DEFAULT": "(newid())"}
], "mssql")
ddl = conn.cur.executed[0]
assert "DEFAULT" not in ddl.split("`id_g`")[1].split(",")[0].split("\n")[0], \
    f"NEWID 는 생략되어야 함:\n{ddl}"
print("  ✓ (newid()) → DEFAULT 생략 (MySQL DEFAULT UUID 비지원)")

# D-5) 복잡 표현식 — 자동 변환 생략 + info 로그
eng = make_engine()
conn = MockConn()
eng._create_mysql_table(conn, "T", [
    {"COLUMN_NAME": "x", "DATA_TYPE": "int", "IS_NULLABLE": "YES",
     "COLUMN_DEFAULT": "(CONVERT(int, SUBSTRING(foo, 1, 1)))"}
], "mssql")
ddl = conn.cur.executed[0]
# 해당 컬럼 라인에 DEFAULT 없어야 함
for line in ddl.split("\n"):
    if "`x`" in line:
        assert "DEFAULT" not in line.upper(), f"복잡 표현식은 생략해야 함: {line}"
assert any("자동 변환 생략" in m for lv, m in eng._collected_logs), \
    "info 로그에 자동 변환 생략 기록 필요"
print("  ✓ 복잡 표현식 (CONVERT...) → DEFAULT 생략 + info 로그")

# D-6) 소스가 MySQL 이면 DEFAULT 변환 로직 미적용 (하위 호환)
ddl, _ = run_and_get_ddl([
    {"COLUMN_NAME": "status", "DATA_TYPE": "int", "IS_NULLABLE": "NO",
     "COLUMN_DEFAULT": "0"}
], src="mysql")
# MySQL 소스에서는 COLUMN_DEFAULT 값이 있어도 v10 #2 로직이 안 돎
# (원래도 처리 안 하던 코드, 순방향 동작 유지 확인)
assert "DEFAULT" not in ddl or "DEFAULT 0" not in ddl
print("  ✓ 소스=MySQL → DEFAULT 변환 로직 미적용 (하위호환)")

# ─────────────────────────────────────────────────────────────
# E. 통합 — 복합 컬럼 테이블
# ─────────────────────────────────────────────────────────────
print("\n═══ E. 통합 테스트 (실전 스키마 샘플) ═══")

ddl, eng = run_and_get_ddl([
    # BIGINT IDENTITY PK
    {"COLUMN_NAME": "id",         "DATA_TYPE": "bigint",    "EXTRA": "auto_increment",
     "COLUMN_KEY": "PRI",         "IS_NULLABLE": "NO"},
    # nvarchar(100) — MSSQL 은 max_length=200
    {"COLUMN_NAME": "name",       "DATA_TYPE": "nvarchar",  "IS_NULLABLE": "NO",
     "CHARACTER_MAXIMUM_LENGTH": 200,
     "COLUMN_DEFAULT": "(N'unknown')"},
    # nvarchar(max)
    {"COLUMN_NAME": "description","DATA_TYPE": "nvarchar",  "IS_NULLABLE": "YES",
     "CHARACTER_MAXIMUM_LENGTH": -1},
    # decimal(18,4) with default 0
    {"COLUMN_NAME": "amount",     "DATA_TYPE": "decimal",   "IS_NULLABLE": "NO",
     "NUMERIC_PRECISION": 18, "NUMERIC_SCALE": 4,
     "COLUMN_DEFAULT": "((0.0000))"},
    # datetime2 default getdate
    {"COLUMN_NAME": "created_at", "DATA_TYPE": "datetime2", "IS_NULLABLE": "NO",
     "COLUMN_DEFAULT": "(getdate())"},
    # uniqueidentifier default newid
    {"COLUMN_NAME": "guid",       "DATA_TYPE": "uniqueidentifier", "IS_NULLABLE": "NO",
     "COLUMN_DEFAULT": "(newid())"},
    # bit default 1
    {"COLUMN_NAME": "is_active",  "DATA_TYPE": "bit",       "IS_NULLABLE": "NO",
     "COLUMN_DEFAULT": "((1))"},
])

print("\n생성된 DDL:")
print(ddl)

expected_fragments = [
    "`id` BIGINT NOT NULL AUTO_INCREMENT",
    "`name` VARCHAR(100) NOT NULL DEFAULT 'unknown'",
    "`description` LONGTEXT NULL",
    "`amount` DECIMAL(18,4) NOT NULL DEFAULT 0.0000",
    "`created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)",
    "`guid` VARCHAR(36) NOT NULL",     # newid 는 DEFAULT 없음
    "`is_active` TINYINT(1) NOT NULL DEFAULT 1",
    "PRIMARY KEY (`id`)",
]
miss = [f for f in expected_fragments if f not in ddl]
assert not miss, f"누락 조각:\n  - " + "\n  - ".join(miss) + f"\n\nDDL:\n{ddl}"
print("\n  ✓ 모든 예상 조각 포함")

# guid 라인에 DEFAULT 없음 확인
for line in ddl.split("\n"):
    if "`guid`" in line:
        assert "DEFAULT" not in line.upper(), f"guid 에 DEFAULT 가 있으면 안됨: {line}"
print("  ✓ guid 컬럼에 DEFAULT 절 없음 (NEWID 생략)")

print("\n✅ 모든 테스트 통과 — v10 #2 DDL 보강 완료")
