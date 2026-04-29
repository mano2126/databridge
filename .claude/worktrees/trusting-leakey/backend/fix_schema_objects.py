"""
fix_schema_objects.py
backend 폴더에서 실행: python fix_schema_objects.py

schema.py 3곳 수정:
1. _get_objects_mssql   — Encrypt=no 제거 (DDL body가 빈 문자열로 오는 원인)
2. execute-object       — Encrypt=no 제거, db_conn 사용, MSSQL→MySQL DDL_CREATE 추가
3. ai-convert-ddl       — MSSQL→MySQL 방향 프롬프트 추가 (양방향 지원)
"""
import shutil, ast
from datetime import datetime

path = 'app/api/routes/schema.py'
bak  = path + '.' + datetime.now().strftime('%H%M%S') + '.bak'
shutil.copy2(path, bak)
print(f'백업: {bak}')

content = open(path, encoding='utf-8').read()

# ── 1. _get_objects_mssql — Encrypt=no 제거 ────────────────
OLD1 = '''def _get_objects_mssql(h, p, u, pw, db):
    """MSSQL 오브젝트 목록"""
    import pyodbc
    dsn = (f"DRIVER={{ODBC Driver 18 for SQL Server}};"
           f"SERVER={h},{p};DATABASE={db};UID={u};PWD={pw};TrustServerCertificate=yes;Encrypt=no;")
    conn = pyodbc.connect(dsn)'''

NEW1 = '''def _get_objects_mssql(h, p, u, pw, db):
    """MSSQL 오브젝트 목록"""
    from app.core.db_conn import make_mssql_conn
    conn = make_mssql_conn(h, p, u, pw, db)'''

if OLD1 in content:
    content = content.replace(OLD1, NEW1)
    print('1. _get_objects_mssql Encrypt=no 제거 완료')
else:
    print('1. 패턴 없음 — 수동 확인 필요')
    # 현재 dsn 확인
    import re
    m = re.search(r'def _get_objects_mssql.{0,200}', content, re.DOTALL)
    if m: print('현재:', repr(m.group()[:200]))

# ── 2. execute-object CHECK_EXISTS — Encrypt=no 제거 ─────────
OLD2 = '''            elif db_type in ("mssql","azure"):
                import pyodbc
                dsn=(f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                     f"SERVER={c['host']},{c['port']};DATABASE={c['database']};"
                     f"UID={c['username']};PWD={c.get('password','')};TrustServerCertificate=yes;Encrypt=no;")
                conn=pyodbc.connect(dsn)
                try:
                    cur=conn.cursor()
                    cur.execute("SELECT name FROM sys.objects WHERE name=? AND type IN ('P','FN','IF','TF','TR','V')", (obj_name_check,))
                    rows=[{"name":r[0]} for r in cur.fetchall()]
                    return {"success":True,"rows":rows,"exists":len(rows)>0}
                finally: conn.close()'''

NEW2 = '''            elif db_type in ("mssql","azure"):
                from app.core.db_conn import make_mssql_conn as _mkms
                conn = _mkms(c['host'], c['port'], c['username'], c.get('password',''), c['database'])
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT name FROM sys.objects WHERE name=? AND type IN ('P','FN','IF','TF','TR','V')", (obj_name_check,))
                    rows = [{"name": r[0]} for r in cur.fetchall()]
                    return {"success": True, "rows": rows, "exists": len(rows) > 0}
                finally:
                    conn.close()'''

if OLD2 in content:
    content = content.replace(OLD2, NEW2)
    print('2. CHECK_EXISTS Encrypt=no 제거 완료')
else:
    print('2. CHECK_EXISTS 패턴 없음')

# ── 3. DDL_CREATE MSSQL 연결 — Encrypt=no 제거 ───────────────
OLD3 = '''            if db_type in ("mssql", "azure"):
                import pyodbc
                dsn = (
                    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                    f"SERVER={c['host']},{c['port']};DATABASE={c['database']};"
                    f"UID={c['username']};PWD={c.get('password','')};TrustServerCertificate=yes;Encrypt=no;"
                )
                conn = pyodbc.connect(dsn)'''

NEW3 = '''            if db_type in ("mssql", "azure"):
                from app.core.db_conn import make_mssql_conn as _mkms2
                conn = _mkms2(c['host'], c['port'], c['username'], c.get('password',''), c['database'])'''

if OLD3 in content:
    content = content.replace(OLD3, NEW3)
    print('3. DDL_CREATE Encrypt=no 제거 완료')
else:
    print('3. DDL_CREATE 패턴 없음')

# ── 4. ai-convert-ddl — 양방향 프롬프트 지원 ─────────────────
OLD_PROMPT = '''    prompt = f"""당신은 MySQL→SQL Server(MSSQL) 마이그레이션 전문가입니다.
아래 MySQL {obj_type} DDL을 SQL Server에서 실행 가능하게 변환해 주세요.'''

NEW_PROMPT = r'''    # 변환 방향에 따라 프롬프트 선택
    src_db_type = src_db.lower() if src_db else "mysql"
    is_mssql_src = src_db_type in ("mssql", "azure", "sqlserver", "sql server")
    is_mysql_tgt = tgt_db_type.lower() in ("mysql", "mariadb", "aurora", "tidb")

    if is_mssql_src and is_mysql_tgt:
        direction_desc = "SQL Server(MSSQL)→MySQL 마이그레이션 전문가"
        rule_block = """## 핵심 변환 규칙 (MSSQL → MySQL)
- [column] → `column` (대괄호→백틱)
- NVARCHAR(MAX) → LONGTEXT, NVARCHAR(n) → VARCHAR(n)
- DATETIME2(n) → DATETIME(6), DATETIMEOFFSET → DATETIME(6)
- BIT → TINYINT(1), MONEY → DECIMAL(19,4), UNIQUEIDENTIFIER → CHAR(36)
- IDENTITY(1,1) → AUTO_INCREMENT
- GETDATE() → NOW(), SYSDATETIME() → NOW(6)
- ISNULL(a,b) → IFNULL(a,b), IIF(c,a,b) → IF(c,a,b)
- LEN(s) → CHAR_LENGTH(s), CHARINDEX(s,str) → LOCATE(s,str)
- STRING_AGG(col,sep) → GROUP_CONCAT(col SEPARATOR sep)
- TOP n → LIMIT n (쿼리 끝으로 이동)
- SET NOCOUNT ON/OFF 제거, WITH(NOLOCK) 제거

### PROCEDURE 규칙 (MSSQL→MySQL)
- @param → param (@ 제거)
- CREATE OR ALTER → CREATE OR REPLACE
- EXEC proc → CALL proc()
- OUTPUT 파라미터 → OUT 파라미터
- DECLARE @v TYPE = val → DECLARE v TYPE DEFAULT val
- IF cond BEGIN → IF cond THEN, END → END IF
- WHILE cond BEGIN → WHILE cond DO, END → END WHILE
- CREATE TABLE #tmp → CREATE TEMPORARY TABLE tmp
- RAISERROR('msg',16,1) → SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='msg'
- BEGIN TRY...END CATCH → DECLARE EXIT HANDLER FOR SQLEXCEPTION

### FUNCTION 규칙 (MSSQL→MySQL)
- CREATE OR ALTER FUNCTION [fn](@p TYPE) RETURNS TYPE AS BEGIN...RETURN v END
  → CREATE FUNCTION `fn`(p TYPE) RETURNS TYPE DETERMINISTIC BEGIN...RETURN v; END

### TRIGGER 규칙 (MSSQL→MySQL)  
- INSERTED.col → NEW.col, DELETED.col → OLD.col
- AFTER INSERT AS BEGIN...END → AFTER INSERT ON `tbl` FOR EACH ROW BEGIN...END
- INSTEAD OF INSERT → BEFORE INSERT ON `tbl` FOR EACH ROW BEGIN...END

### VIEW 규칙 (MSSQL→MySQL)
- CREATE OR ALTER VIEW → CREATE OR REPLACE VIEW
- OFFSET n ROWS FETCH NEXT m ROWS ONLY → LIMIT m OFFSET n"""
    else:
        direction_desc = "MySQL→SQL Server(MSSQL) 마이그레이션 전문가"
        rule_block = """## 핵심 변환 규칙 (MySQL → MSSQL)
- 백틱(`) → 대괄호([])
- DEFINER=... / ALGORITHM=... / SQL SECURITY ... / READS SQL DATA / DETERMINISTIC 제거
- VARCHAR→NVARCHAR, DATETIME→DATETIME2(6), TINYINT(1)→BIT
- NOW()/CURRENT_TIMESTAMP→GETDATE(), IFNULL→ISNULL, LENGTH→LEN, SUBSTR→SUBSTRING
- GROUP_CONCAT(x SEPARATOR ',')→STRING_AGG(x,','), _utf8mb4'...'→'...'
- MySQL # 주석 → -- 주석

### PROCEDURE 규칙 (MySQL→MSSQL)
- IN/OUT/INOUT param → @param (OUT/INOUT은 OUTPUT 추가)
- DECLARE var TYPE → DECLARE @var TYPE
- IF cond THEN → IF cond BEGIN ... END (THEN 제거)
- ELSEIF → END ELSE IF ... BEGIN, END IF → END
- WHILE cond DO → WHILE cond BEGIN ... END
- LEAVE label → BREAK
- CREATE TEMPORARY TABLE t → CREATE TABLE #t
- SELECT expr INTO var FROM → SELECT @var = expr FROM
- CALL proc → EXEC proc
- SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='msg' → THROW 50001,'msg',1

### FUNCTION 규칙 (MySQL→MSSQL)
- CREATE OR ALTER FUNCTION [name](@params) RETURNS type AS BEGIN...RETURN val;END
- RETURNS tinyint(1) → RETURNS BIT
- RETURN TRUE → RETURN 1, RETURN FALSE → RETURN 0

### TRIGGER 규칙 (MySQL→MSSQL)
- BEFORE INSERT/UPDATE → INSTEAD OF INSERT/UPDATE
- AFTER INSERT/UPDATE/DELETE → AFTER (그대로)
- NEW.col → INSERTED.col, OLD.col → DELETED.col
- FOR EACH ROW 제거, BEGIN...END → AS BEGIN SET NOCOUNT ON;...END

### VIEW 규칙 (MySQL→MSSQL)
- CREATE OR REPLACE VIEW → CREATE OR ALTER VIEW
- GROUP_CONCAT → STRING_AGG
- ORDER BY 제거 (뷰에서 TOP 없이 ORDER BY 불가)"""

    prompt = f"""당신은 {direction_desc}입니다.
아래 {obj_type} DDL을 변환해 주세요.'''

if OLD_PROMPT in content:
    content = content.replace(OLD_PROMPT, NEW_PROMPT)
    print('4. ai-convert-ddl 양방향 프롬프트 추가 완료')
else:
    print('4. ai-convert-ddl 프롬프트 패턴 없음')

# ── 5. 프롬프트 본문 교체 ──────────────────────────────────────
OLD_PROMPT_BODY = '''## 핵심 변환 규칙
- DEFINER=... / ALGORITHM=... / SQL SECURITY ... / READS SQL DATA / DETERMINISTIC 제거
- 백틱(`) → 대괄호([])
- VARCHAR→NVARCHAR, DATETIME→DATETIME2(6), TINYINT(1)→BIT
- NOW()/CURRENT_TIMESTAMP→GETDATE(), IFNULL→ISNULL, LENGTH→LEN, SUBSTR→SUBSTRING
- GROUP_CONCAT(x SEPARATOR ',')→STRING_AGG(x,','), _utf8mb4'...'→'...'
- MySQL # 주석 → -- 주석

### PROCEDURE 규칙
- IN/OUT/INOUT param → @param (OUT/INOUT은 OUTPUT 추가)
- DECLARE var TYPE → DECLARE @var TYPE
- IF cond THEN → IF cond BEGIN ... END (THEN 제거)
- ELSEIF → END ELSE IF ... BEGIN
- END IF → END
- WHILE cond DO → WHILE cond BEGIN ... END
- LEAVE label → BREAK
- CREATE TEMPORARY TABLE t → CREATE TABLE #t
- SELECT expr INTO var FROM → SELECT @var = expr FROM
- SELECT COUNT(*) INTO var; → SET @var = (SELECT COUNT(*) ...);
- CALL proc → EXEC proc

### FUNCTION 규칙
- CREATE OR ALTER FUNCTION [name](@params) RETURNS type AS BEGIN...RETURN val;END
- RETURNS tinyint(1) → RETURNS BIT
- RETURN TRUE → RETURN 1, RETURN FALSE → RETURN 0

### TRIGGER 규칙
- BEFORE INSERT/UPDATE에서 단순 SET NEW.col=val → ALTER TABLE ADD CONSTRAINT DEFAULT
- BEFORE INSERT 복잡한 경우 → INSTEAD OF INSERT 트리거
- AFTER INSERT/UPDATE/DELETE → AFTER (그대로)
- NEW.col → INSERTED.col, OLD.col → DELETED.col
- FOR EACH ROW 제거, BEGIN...END → AS BEGIN...END 구조

### VIEW 규칙
- CREATE OR REPLACE VIEW → CREATE OR ALTER VIEW
- DB prefix (예: sakila.) 제거
- GROUP_CONCAT → STRING_AGG
- if(col, a, b) → IIF(col<>0, a, b) (부울 컬럼)
- ORDER BY 제거 (뷰에서 TOP 없이 ORDER BY 불가)
- separator 키워드 제거

## 타겟 환경
- 소스 DB명: {src_db}
- 타겟에 이미 생성된 테이블: {tbl_ctx}

## 변환할 MySQL DDL
```sql
{mysql_ddl[:3000]}
```

## 응답 (JSON만, 마크다운 없이)
{{"statements":["실행가능한 MSSQL SQL문1","SQL문2"],"notes":"변환 설명(한글, 간략히)"}}

주의: statements 배열의 각 항목은 독립적으로 실행 가능한 완전한 SQL이어야 합니다."""'''

NEW_PROMPT_BODY = '''{rule_block}

## 타겟 환경
- 소스 DB명: {src_db}
- 소스 DB 타입: {src_db_type}
- 타겟 DB 타입: {tgt_db_type}
- 타겟에 이미 생성된 테이블: {tbl_ctx}

## 변환할 {src_db_type.upper()} DDL
```sql
{mysql_ddl[:3000]}
```

## 응답 (JSON만, 마크다운 없이)
{{"statements":["실행가능한 SQL문1","SQL문2"],"notes":"변환 설명(한글, 간략히)"}}

주의: statements 배열의 각 항목은 독립적으로 실행 가능한 완전한 SQL이어야 합니다."""'''

if OLD_PROMPT_BODY in content:
    content = content.replace(OLD_PROMPT_BODY, NEW_PROMPT_BODY)
    print('5. 프롬프트 본문 교체 완료')
else:
    print('5. 프롬프트 본문 패턴 없음 — 부분 교체됐을 수 있음')

# ── 문법 확인 ──────────────────────────────────────────────────
try:
    ast.parse(content)
    print('✓ 문법 OK')
except SyntaxError as e:
    print(f'✗ 문법 오류 {e.lineno}: {e.msg}')
    lines = content.split('\n')
    for i, l in enumerate(lines[max(0,e.lineno-3):e.lineno+3], max(1,e.lineno-2)):
        print(f'{i}: {l}')
    print(f'복구: copy {bak} {path}')
    exit(1)

open(path, 'w', encoding='utf-8').write(content)
print('\n완료! 백엔드 재시작:')
print('python -m uvicorn main:app --port 8000')
