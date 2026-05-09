"""
app/api/routes/obj_mapping.py
오브젝트 매핑 규칙 API

테이블, 인덱스, 제약조건, 프로시저, 함수, 트리거, 뷰,
시퀀스, 쿼리문법, 내장함수, 트랜잭션, 예외처리, 커서,
임시테이블, 동적SQL, 권한 등 모든 DB 오브젝트 변환 규칙 관리
"""
from fastapi import APIRouter, HTTPException
import uuid
from app.core.store import Store

router = APIRouter()
_rules = Store("obj_mapping_rules")


def _r(src, tgt, obj, cat, sp, tp, note="", warn=False):
    """규칙 생성 헬퍼"""
    return {
        "src_db": src, "tgt_db": tgt,
        "obj_type": obj, "category": cat,
        "src_syntax": sp, "tgt_syntax": tp,
        "note": note, "warning": warn, "custom": False,
        "is_regex": False,
    }


# ══════════════════════════════════════════════════════════════
# 기본 규칙 데이터 — 현재 세상에 존재하는 모든 주요 DB 조합 커버
# ══════════════════════════════════════════════════════════════
_DEFAULTS = [

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [1] 식별자 인용 부호 (Identifier Quoting)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","SYNTAX","식별자","`column`","[column]","MySQL 백틱 → MSSQL 대괄호"),
    _r("mysql","postgresql","SYNTAX","식별자","`column`",'"column"',"MySQL 백틱 → PostgreSQL 큰따옴표"),
    _r("mysql","oracle","SYNTAX","식별자","`column`",'"column"',"MySQL 백틱 → Oracle 큰따옴표"),
    _r("mssql","mysql","SYNTAX","식별자","[column]","`column`","MSSQL 대괄호 → MySQL 백틱"),
    _r("mssql","postgresql","SYNTAX","식별자","[column]",'"column"',"MSSQL 대괄호 → PostgreSQL 큰따옴표"),
    _r("mssql","oracle","SYNTAX","식별자","[column]",'"column"',"MSSQL 대괄호 → Oracle 큰따옴표"),
    _r("oracle","mysql","SYNTAX","식별자",'"column"',"`column`","Oracle 큰따옴표 → MySQL 백틱"),
    _r("oracle","mssql","SYNTAX","식별자",'"column"',"[column]","Oracle 큰따옴표 → MSSQL 대괄호"),
    _r("postgresql","mysql","SYNTAX","식별자",'"column"',"`column`","PostgreSQL → MySQL 백틱"),
    _r("postgresql","mssql","SYNTAX","식별자",'"column"',"[column]","PostgreSQL → MSSQL 대괄호"),
    _r("db2","mysql","SYNTAX","식별자",'"column"',"`column`","DB2 → MySQL 백틱"),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [2] CREATE TABLE 구조
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","TABLE","CREATE TABLE",
       "CREATE TABLE `tbl` (...) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
       "CREATE TABLE [dbo].[tbl] (...)",
       "ENGINE/CHARSET 제거, 스키마 추가"),
    _r("mysql","postgresql","TABLE","CREATE TABLE",
       "CREATE TABLE `tbl` (...) ENGINE=InnoDB",
       'CREATE TABLE "tbl" (...)',
       "ENGINE 제거, 백틱→큰따옴표"),
    _r("mssql","mysql","TABLE","CREATE TABLE",
       "IF OBJECT_ID(N'[dbo].[tbl]', N'U') IS NULL CREATE TABLE [dbo].[tbl] (...)",
       "CREATE TABLE IF NOT EXISTS `tbl` (...) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
       "IF OBJECT_ID → IF NOT EXISTS, 스키마 제거"),
    _r("mssql","postgresql","TABLE","CREATE TABLE",
       "CREATE TABLE [dbo].[tbl] (...)",
       "CREATE TABLE IF NOT EXISTS tbl (...)",
       "대괄호 제거, 스키마 처리"),
    _r("oracle","mysql","TABLE","CREATE TABLE",
       "CREATE TABLE tbl (...) TABLESPACE users",
       "CREATE TABLE `tbl` (...) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
       "TABLESPACE 제거"),
    _r("oracle","postgresql","TABLE","CREATE TABLE",
       "CREATE TABLE tbl (...) TABLESPACE users",
       "CREATE TABLE tbl (...)",
       "TABLESPACE 제거"),
    _r("postgresql","mysql","TABLE","CREATE TABLE",
       'CREATE TABLE "tbl" (...)',
       "CREATE TABLE `tbl` (...) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4",
       "큰따옴표→백틱, ENGINE 추가"),
    _r("db2","mysql","TABLE","CREATE TABLE",
       "CREATE TABLE schema.tbl (...) IN tablespace",
       "CREATE TABLE `tbl` (...) ENGINE=InnoDB",
       "스키마·테이블스페이스 제거"),
    _r("sybase","mysql","TABLE","CREATE TABLE",
       "CREATE TABLE [tbl] (...) ON segment",
       "CREATE TABLE `tbl` (...) ENGINE=InnoDB",
       "세그먼트 제거"),
    _r("mysql","snowflake","TABLE","CREATE TABLE",
       "CREATE TABLE `tbl` (...) ENGINE=InnoDB",
       "CREATE TABLE tbl (...)",
       "ENGINE/CHARSET 제거"),
    _r("mysql","bigquery","TABLE","CREATE TABLE",
       "CREATE TABLE `tbl` (...)",
       "CREATE TABLE project.dataset.tbl (...)",
       "프로젝트.데이터셋 prefix 필요",True),
    _r("mysql","clickhouse","TABLE","CREATE TABLE",
       "CREATE TABLE `tbl` (...)",
       "CREATE TABLE tbl (...) ENGINE=MergeTree() ORDER BY id",
       "ClickHouse ENGINE 필수",True),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [3] AUTO_INCREMENT / IDENTITY / SEQUENCE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","TABLE","자동증가","INT AUTO_INCREMENT","INT IDENTITY(1,1)",""),
    _r("mysql","postgresql","TABLE","자동증가","INT AUTO_INCREMENT","SERIAL","또는 GENERATED ALWAYS AS IDENTITY"),
    _r("mysql","oracle","TABLE","자동증가","INT AUTO_INCREMENT","NUMBER GENERATED ALWAYS AS IDENTITY","Oracle 12c+",True),
    _r("mysql","snowflake","TABLE","자동증가","INT AUTO_INCREMENT","INT AUTOINCREMENT",""),
    _r("mysql","clickhouse","TABLE","자동증가","INT AUTO_INCREMENT","/* ClickHouse는 자동증가 없음 */","수동 시퀀스 관리 필요",True),
    _r("mysql","bigquery","TABLE","자동증가","INT AUTO_INCREMENT","/* BigQuery는 자동증가 없음 */","UUID 또는 외부 생성 사용",True),
    _r("mssql","mysql","TABLE","자동증가","INT IDENTITY(1,1)","INT AUTO_INCREMENT",""),
    _r("mssql","postgresql","TABLE","자동증가","INT IDENTITY(1,1)","SERIAL","또는 GENERATED ALWAYS AS IDENTITY"),
    _r("mssql","oracle","TABLE","자동증가","INT IDENTITY(1,1)","NUMBER GENERATED ALWAYS AS IDENTITY","Oracle 12c+",True),
    _r("mssql","snowflake","TABLE","자동증가","INT IDENTITY(1,1)","INT AUTOINCREMENT",""),
    _r("oracle","mysql","TABLE","자동증가","SEQUENCE seq; seq.NEXTVAL","INT AUTO_INCREMENT","시퀀스 제거 후 AUTO_INCREMENT",True),
    _r("oracle","mssql","TABLE","자동증가","SEQUENCE seq; seq.NEXTVAL","INT IDENTITY(1,1)","시퀀스 제거",True),
    _r("oracle","postgresql","TABLE","자동증가","SEQUENCE seq; seq.NEXTVAL","SERIAL / nextval('seq')","시퀀스 이름 유지 가능"),
    _r("postgresql","mysql","TABLE","자동증가","SERIAL","INT AUTO_INCREMENT",""),
    _r("postgresql","mssql","TABLE","자동증가","SERIAL","INT IDENTITY(1,1)",""),
    _r("postgresql","oracle","TABLE","자동증가","SERIAL","NUMBER GENERATED ALWAYS AS IDENTITY","Oracle 12c+",True),
    _r("db2","mysql","TABLE","자동증가","GENERATED ALWAYS AS IDENTITY","INT AUTO_INCREMENT",""),
    _r("db2","mssql","TABLE","자동증가","GENERATED ALWAYS AS IDENTITY","INT IDENTITY(1,1)",""),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [4] 인덱스 (INDEX)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","INDEX","일반인덱스",
       "CREATE INDEX idx ON `tbl`(`col`)",
       "CREATE INDEX idx ON [tbl]([col])","백틱→대괄호"),
    _r("mysql","mssql","INDEX","유니크인덱스",
       "CREATE UNIQUE INDEX idx ON `tbl`(`col`)",
       "CREATE UNIQUE INDEX idx ON [tbl]([col])",""),
    _r("mysql","mssql","INDEX","전문인덱스",
       "CREATE FULLTEXT INDEX idx ON `tbl`(`col`)",
       "CREATE FULLTEXT INDEX idx ON [tbl]([col]) KEY INDEX PK_tbl",
       "KEY INDEX 지정 필요",True),
    _r("mysql","postgresql","INDEX","일반인덱스",
       "CREATE INDEX idx ON `tbl`(`col`)",
       'CREATE INDEX idx ON tbl(col)',""),
    _r("mysql","postgresql","INDEX","전문인덱스",
       "CREATE FULLTEXT INDEX idx ON `tbl`(`col`)",
       "CREATE INDEX idx ON tbl USING gin(to_tsvector('korean', col))",
       "GIN 인덱스 + tsvector 사용",True),
    _r("mssql","mysql","INDEX","클러스터드인덱스",
       "CREATE CLUSTERED INDEX idx ON [tbl]([col])",
       "/* MySQL PRIMARY KEY가 클러스터드 인덱스 */",
       "PK로 대체 권장",True),
    _r("mssql","mysql","INDEX","포함열인덱스",
       "CREATE INDEX idx ON [tbl]([col]) INCLUDE ([col2])",
       "CREATE INDEX idx ON `tbl`(`col`, `col2`)",
       "INCLUDE → 복합 인덱스로 변환",True),
    _r("oracle","mysql","INDEX","비트맵인덱스",
       "CREATE BITMAP INDEX idx ON tbl(col)",
       "CREATE INDEX idx ON `tbl`(`col`)",
       "MySQL은 비트맵 인덱스 미지원",True),
    _r("oracle","postgresql","INDEX","함수기반인덱스",
       "CREATE INDEX idx ON tbl(UPPER(col))",
       "CREATE INDEX idx ON tbl(UPPER(col))","동일"),
    _r("mysql","clickhouse","INDEX","인덱스",
       "CREATE INDEX idx ON `tbl`(`col`)",
       "/* ClickHouse는 별도 INDEX 없음, ORDER BY/PARTITION BY 사용 */",
       "ORDER BY 로 대체",True),
    _r("mysql","bigquery","INDEX","인덱스",
       "CREATE INDEX idx ON `tbl`(`col`)",
       "/* BigQuery는 인덱스 없음, 파티셔닝/클러스터링 사용 */",
       "PARTITION BY / CLUSTER BY 로 대체",True),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [5] 제약조건 (CONSTRAINT)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","CONSTRAINT","기본키",
       "PRIMARY KEY (`col`)",
       "CONSTRAINT [PK_tbl] PRIMARY KEY ([col])",""),
    _r("mysql","mssql","CONSTRAINT","외래키",
       "FOREIGN KEY (`col`) REFERENCES `tbl2`(`col2`)",
       "CONSTRAINT [FK_name] FOREIGN KEY ([col]) REFERENCES [tbl2]([col2])",""),
    _r("mysql","mssql","CONSTRAINT","체크제약",
       "CHECK (`col` > 0)",
       "CONSTRAINT [CHK_name] CHECK ([col] > 0)",""),
    _r("mysql","mssql","CONSTRAINT","기본값",
       "DEFAULT CURRENT_TIMESTAMP",
       "DEFAULT GETDATE()","NOW()→GETDATE()"),
    _r("mysql","postgresql","CONSTRAINT","기본값",
       "DEFAULT CURRENT_TIMESTAMP",
       "DEFAULT CURRENT_TIMESTAMP","동일"),
    _r("mssql","mysql","CONSTRAINT","기본키",
       "CONSTRAINT [PK_tbl] PRIMARY KEY ([col])",
       "PRIMARY KEY (`col`)",""),
    _r("mssql","mysql","CONSTRAINT","기본값",
       "DEFAULT GETDATE()",
       "DEFAULT CURRENT_TIMESTAMP",""),
    _r("oracle","mysql","CONSTRAINT","체크제약",
       "CONSTRAINT chk CHECK (col IN ('A','B'))",
       "CONSTRAINT chk CHECK (col IN ('A','B'))","MySQL 8.0.16+ 지원",True),
    _r("mysql","snowflake","CONSTRAINT","외래키",
       "FOREIGN KEY (`col`) REFERENCES `tbl2`(`col2`)",
       "/* Snowflake FK는 선언만 가능, 강제 적용 안 됨 */",
       "참조 무결성 미적용",True),
    _r("mysql","bigquery","CONSTRAINT","외래키",
       "FOREIGN KEY (`col`) REFERENCES `tbl2`(`col2`)",
       "/* BigQuery는 FK 미지원 */",
       "응용단에서 무결성 관리",True),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [6] 뷰 (VIEW)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","VIEW","뷰생성",
       "CREATE OR REPLACE VIEW `vw` AS SELECT ...",
       "CREATE OR ALTER VIEW [dbo].[vw] AS SELECT ...",""),
    _r("mysql","postgresql","VIEW","뷰생성",
       "CREATE OR REPLACE VIEW `vw` AS SELECT ...",
       "CREATE OR REPLACE VIEW vw AS SELECT ...",""),
    _r("mysql","oracle","VIEW","뷰생성",
       "CREATE OR REPLACE VIEW `vw` AS SELECT ...",
       "CREATE OR REPLACE VIEW vw AS SELECT ...",""),
    _r("mssql","mysql","VIEW","뷰생성",
       "CREATE OR ALTER VIEW [dbo].[vw] AS SELECT ...",
       "CREATE OR REPLACE VIEW `vw` AS SELECT ...",""),
    _r("mssql","mysql","VIEW","인덱스드뷰",
       "CREATE VIEW vw WITH SCHEMABINDING AS SELECT ...",
       "/* MySQL은 인덱스드 뷰 미지원 */",
       "일반 뷰 또는 임시테이블로 대체",True),
    _r("oracle","mysql","VIEW","구체화뷰",
       "CREATE MATERIALIZED VIEW mv AS SELECT ...",
       "CREATE TABLE mv AS SELECT ... / EVENT 스케줄러로 갱신",
       "MySQL은 구체화 뷰 미지원",True),
    _r("oracle","postgresql","VIEW","구체화뷰",
       "CREATE MATERIALIZED VIEW mv AS SELECT ...",
       "CREATE MATERIALIZED VIEW mv AS SELECT ...",
       "PostgreSQL 9.3+ 지원"),
    _r("postgresql","mysql","VIEW","구체화뷰",
       "CREATE MATERIALIZED VIEW mv AS SELECT ...",
       "CREATE TABLE mv AS SELECT ... / 수동 갱신",
       "MySQL은 구체화 뷰 미지원",True),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [7] 저장 프로시저 (PROCEDURE)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","PROCEDURE","생성구문",
       "CREATE PROCEDURE `proc`(IN p1 INT, OUT p2 VARCHAR(100))",
       "CREATE OR ALTER PROCEDURE [dbo].[proc] (@p1 INT, @p2 NVARCHAR(100) OUTPUT)",
       "IN/OUT → 없음/@OUTPUT, 백틱→대괄호"),
    _r("mysql","mssql","PROCEDURE","호출",
       "CALL proc(1, @result)",
       "EXEC [proc] 1, @result OUTPUT",""),
    _r("mysql","mssql","PROCEDURE","변수선언",
       "DECLARE v1 INT DEFAULT 0;",
       "DECLARE @v1 INT = 0;","@ 접두사 추가"),
    _r("mysql","mssql","PROCEDURE","IF문",
       "IF condition THEN ... ELSEIF ... ELSE ... END IF;",
       "IF condition BEGIN ... END ELSE IF ... BEGIN ... END ELSE BEGIN ... END",""),
    _r("mysql","mssql","PROCEDURE","WHILE문",
       "WHILE condition DO ... END WHILE;",
       "WHILE condition BEGIN ... END",""),
    _r("mysql","mssql","PROCEDURE","LOOP문",
       "label: LOOP ... LEAVE label; ... END LOOP;",
       "WHILE 1=1 BEGIN ... BREAK; ... END",""),
    _r("mysql","mssql","PROCEDURE","SELECT INTO",
       "SELECT col INTO v1 FROM tbl WHERE ...",
       "SELECT @v1 = col FROM [tbl] WHERE ...","@ 추가"),
    _r("mysql","mssql","PROCEDURE","임시테이블",
       "CREATE TEMPORARY TABLE tmp (...)",
       "CREATE TABLE #tmp (...)","# 접두사"),
    _r("mysql","mssql","PROCEDURE","SIGNAL",
       "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='오류'",
       "RAISERROR('오류', 16, 1) / THROW 50001,'오류',1","",True),
    _r("mssql","mysql","PROCEDURE","생성구문",
       "CREATE OR ALTER PROCEDURE [dbo].[proc] (@p1 INT, @p2 NVARCHAR(100) OUTPUT)",
       "CREATE PROCEDURE `proc`(IN p1 INT, OUT p2 VARCHAR(100))",
       "@ 제거, OUTPUT→OUT, 대괄호→백틱"),
    _r("mssql","mysql","PROCEDURE","호출",
       "EXEC [proc] @p1=1, @p2=@result OUTPUT",
       "CALL `proc`(1, @result)",""),
    _r("mssql","mysql","PROCEDURE","변수선언",
       "DECLARE @v1 INT = 0;",
       "DECLARE v1 INT DEFAULT 0;","@ 제거"),
    _r("mssql","mysql","PROCEDURE","IF문",
       "IF condition BEGIN ... END ELSE BEGIN ... END",
       "IF condition THEN ... ELSE ... END IF;",""),
    _r("mssql","mysql","PROCEDURE","임시테이블",
       "CREATE TABLE #tmp (...)",
       "CREATE TEMPORARY TABLE tmp (...)","# 제거, TEMPORARY 추가"),
    _r("mssql","mysql","PROCEDURE","RAISERROR",
       "RAISERROR('오류메시지', 16, 1)",
       "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='오류메시지'",""),
    _r("oracle","mysql","PROCEDURE","생성구문",
       "CREATE OR REPLACE PROCEDURE proc(p1 IN NUMBER, p2 OUT VARCHAR2)",
       "CREATE PROCEDURE `proc`(IN p1 INT, OUT p2 VARCHAR(100))",
       "IS/AS → 없음, 파라미터 방향 순서 변경",True),
    _r("oracle","mysql","PROCEDURE","예외처리",
       "EXCEPTION WHEN NO_DATA_FOUND THEN ... WHEN OTHERS THEN ...",
       "DECLARE EXIT HANDLER FOR NOT FOUND ...; DECLARE EXIT HANDLER FOR SQLEXCEPTION ...;","",True),
    _r("oracle","mssql","PROCEDURE","예외처리",
       "EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE(SQLERRM)",
       "BEGIN TRY ... END TRY BEGIN CATCH PRINT ERROR_MESSAGE() END CATCH","",True),
    _r("postgresql","mysql","PROCEDURE","생성구문",
       "CREATE OR REPLACE PROCEDURE proc(p1 INT, INOUT p2 TEXT)",
       "CREATE PROCEDURE `proc`(IN p1 INT, INOUT p2 VARCHAR(100))","",True),
    _r("postgresql","mssql","PROCEDURE","생성구문",
       "CREATE OR REPLACE PROCEDURE proc(p1 INT)",
       "CREATE OR ALTER PROCEDURE [dbo].[proc] (@p1 INT)",""),
    _r("db2","mysql","PROCEDURE","생성구문",
       "CREATE OR REPLACE PROCEDURE proc(IN p1 INT, OUT p2 VARCHAR(100))",
       "CREATE PROCEDURE `proc`(IN p1 INT, OUT p2 VARCHAR(100))","거의 동일"),
    _r("sybase","mysql","PROCEDURE","생성구문",
       "CREATE PROCEDURE proc @p1 INT AS BEGIN ... END",
       "CREATE PROCEDURE `proc`(IN p1 INT) BEGIN ... END","@ 제거"),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [8] 함수 (FUNCTION)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","FUNCTION","스칼라함수",
       "CREATE FUNCTION `fn`(p1 INT) RETURNS INT DETERMINISTIC BEGIN RETURN p1+1; END",
       "CREATE OR ALTER FUNCTION [dbo].[fn](@p1 INT) RETURNS INT AS BEGIN RETURN @p1+1 END",""),
    _r("mysql","mssql","FUNCTION","특성제거",
       "DETERMINISTIC / NOT DETERMINISTIC / READS SQL DATA",
       "/* MSSQL에는 이 특성 없음 — 제거 */",""),
    _r("mysql","postgresql","FUNCTION","스칼라함수",
       "CREATE FUNCTION `fn`(p1 INT) RETURNS INT DETERMINISTIC BEGIN RETURN p1+1; END",
       "CREATE OR REPLACE FUNCTION fn(p1 INT) RETURNS INT AS $$ BEGIN RETURN p1+1; END; $$ LANGUAGE plpgsql;",
       "LANGUAGE plpgsql 추가, $$ 블록",True),
    _r("mssql","mysql","FUNCTION","스칼라함수",
       "CREATE FUNCTION [dbo].[fn](@p1 INT) RETURNS INT AS BEGIN RETURN @p1+1 END",
       "CREATE FUNCTION `fn`(p1 INT) RETURNS INT DETERMINISTIC BEGIN RETURN p1+1; END",""),
    _r("mssql","mysql","FUNCTION","테이블반환함수",
       "CREATE FUNCTION fn(@p INT) RETURNS TABLE AS RETURN SELECT ...",
       "CREATE VIEW vw_fn AS SELECT ... / 인라인 처리",
       "MySQL은 테이블반환 함수 미지원",True),
    _r("mssql","postgresql","FUNCTION","테이블반환함수",
       "CREATE FUNCTION fn(@p INT) RETURNS TABLE AS RETURN SELECT ...",
       "CREATE OR REPLACE FUNCTION fn(p INT) RETURNS TABLE (...) AS $$ ... $$ LANGUAGE plpgsql","",True),
    _r("oracle","mysql","FUNCTION","스칼라함수",
       "CREATE OR REPLACE FUNCTION fn(p1 NUMBER) RETURN NUMBER IS v NUMBER; BEGIN RETURN v; END;",
       "CREATE FUNCTION `fn`(p1 INT) RETURNS INT DETERMINISTIC BEGIN RETURN p1; END","IS/RETURN→RETURNS",True),
    _r("oracle","mssql","FUNCTION","스칼라함수",
       "CREATE OR REPLACE FUNCTION fn(p1 NUMBER) RETURN NUMBER IS v NUMBER; BEGIN RETURN v; END;",
       "CREATE OR ALTER FUNCTION [dbo].[fn](@p1 DECIMAL) RETURNS DECIMAL AS BEGIN RETURN @p1 END","",True),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [9] 트리거 (TRIGGER)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","TRIGGER","AFTER INSERT",
       "CREATE TRIGGER trig AFTER INSERT ON `tbl` FOR EACH ROW BEGIN ... END",
       "CREATE OR ALTER TRIGGER [trig] ON [tbl] AFTER INSERT AS BEGIN SET NOCOUNT ON; ... END",
       "FOR EACH ROW 제거, AS BEGIN 추가"),
    _r("mysql","mssql","TRIGGER","BEFORE INSERT",
       "CREATE TRIGGER trig BEFORE INSERT ON `tbl` FOR EACH ROW BEGIN ... END",
       "CREATE OR ALTER TRIGGER [trig] ON [tbl] INSTEAD OF INSERT AS BEGIN SET NOCOUNT ON; ... END",
       "BEFORE → INSTEAD OF",True),
    _r("mysql","mssql","TRIGGER","NEW/OLD 참조",
       "NEW.col / OLD.col",
       "INSERTED.col / DELETED.col",""),
    _r("mysql","postgresql","TRIGGER","트리거생성",
       "CREATE TRIGGER trig AFTER INSERT ON `tbl` FOR EACH ROW BEGIN ... END",
       "CREATE OR REPLACE FUNCTION trig_fn() RETURNS TRIGGER AS $$ BEGIN ... RETURN NEW; END; $$ LANGUAGE plpgsql;\nCREATE TRIGGER trig AFTER INSERT ON tbl FOR EACH ROW EXECUTE FUNCTION trig_fn();",
       "함수와 트리거 분리",True),
    _r("mysql","postgresql","TRIGGER","NEW/OLD 참조",
       "NEW.col / OLD.col",
       "NEW.col / OLD.col","동일"),
    _r("mssql","mysql","TRIGGER","AFTER INSERT",
       "CREATE OR ALTER TRIGGER [trig] ON [tbl] AFTER INSERT AS BEGIN ... END",
       "CREATE TRIGGER trig AFTER INSERT ON `tbl` FOR EACH ROW BEGIN ... END",
       "FOR EACH ROW 추가"),
    _r("mssql","mysql","TRIGGER","INSTEAD OF",
       "INSTEAD OF INSERT",
       "BEFORE INSERT","INSTEAD OF → BEFORE",True),
    _r("mssql","mysql","TRIGGER","INSERTED/DELETED",
       "INSERTED.col / DELETED.col",
       "NEW.col / OLD.col",""),
    _r("oracle","mysql","TRIGGER","트리거생성",
       "CREATE OR REPLACE TRIGGER trig BEFORE INSERT ON tbl FOR EACH ROW BEGIN :NEW.col := ...; END;",
       "CREATE TRIGGER trig BEFORE INSERT ON `tbl` FOR EACH ROW SET NEW.col = ...;",
       ":NEW → NEW, := → =",True),
    _r("oracle","mssql","TRIGGER","트리거생성",
       "CREATE OR REPLACE TRIGGER trig BEFORE INSERT ON tbl FOR EACH ROW BEGIN :NEW.col := ...; END;",
       "CREATE OR ALTER TRIGGER [trig] ON [tbl] INSTEAD OF INSERT AS BEGIN ... END",
       "BEFORE → INSTEAD OF, :NEW → INSERTED",True),
    _r("postgresql","mysql","TRIGGER","트리거+함수",
       "FUNCTION trig_fn() + CREATE TRIGGER trig ... EXECUTE FUNCTION trig_fn()",
       "CREATE TRIGGER trig ... BEGIN ... END",
       "함수 내용을 트리거 본문에 인라인",True),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [10] SELECT 문법
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","QUERY","페이징",
       "SELECT * FROM tbl LIMIT 10 OFFSET 20",
       "SELECT * FROM [tbl] ORDER BY id OFFSET 20 ROWS FETCH NEXT 10 ROWS ONLY",
       "ORDER BY 필수",True),
    _r("mysql","mssql","QUERY","TOP",
       "SELECT * FROM tbl LIMIT 10",
       "SELECT TOP 10 * FROM [tbl]",""),
    _r("mysql","oracle","QUERY","페이징",
       "SELECT * FROM tbl LIMIT 10 OFFSET 20",
       "SELECT * FROM tbl OFFSET 20 ROWS FETCH NEXT 10 ROWS ONLY",
       "Oracle 12c+; 이전 버전은 ROWNUM 사용",True),
    _r("mysql","oracle","QUERY","TOP",
       "SELECT * FROM tbl LIMIT 1",
       "SELECT * FROM tbl WHERE ROWNUM = 1","또는 FETCH FIRST 1 ROWS ONLY"),
    _r("mssql","mysql","QUERY","페이징",
       "SELECT * FROM [tbl] ORDER BY id OFFSET 20 ROWS FETCH NEXT 10 ROWS ONLY",
       "SELECT * FROM `tbl` LIMIT 10 OFFSET 20",""),
    _r("mssql","mysql","QUERY","TOP",
       "SELECT TOP 10 * FROM [tbl]",
       "SELECT * FROM `tbl` LIMIT 10",""),
    _r("oracle","mysql","QUERY","페이징",
       "SELECT * FROM tbl WHERE ROWNUM <= 10",
       "SELECT * FROM `tbl` LIMIT 10",""),
    _r("oracle","mssql","QUERY","ROWNUM",
       "WHERE ROWNUM <= n",
       "TOP n 또는 FETCH NEXT n ROWS ONLY","",True),
    _r("mysql","postgresql","QUERY","페이징",
       "LIMIT n OFFSET m",
       "LIMIT n OFFSET m","동일"),
    _r("mysql","bigquery","QUERY","페이징",
       "SELECT * FROM tbl LIMIT 10 OFFSET 20",
       "SELECT * FROM tbl LIMIT 10 OFFSET 20","동일"),
    _r("mysql","snowflake","QUERY","페이징",
       "SELECT * FROM tbl LIMIT 10 OFFSET 20",
       "SELECT * FROM tbl LIMIT 10 OFFSET 20","동일"),
    _r("mysql","clickhouse","QUERY","페이징",
       "SELECT * FROM tbl LIMIT 10 OFFSET 20",
       "SELECT * FROM tbl LIMIT 20,10","또는 LIMIT 10 OFFSET 20"),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [11] CTE (Common Table Expression)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","QUERY","CTE",
       "WITH cte AS (SELECT ...) SELECT * FROM cte",
       "WITH cte AS (SELECT ...) SELECT * FROM cte","동일 (MySQL 8.0+)"),
    _r("mysql","oracle","QUERY","CTE",
       "WITH cte AS (SELECT ...) SELECT * FROM cte",
       "WITH cte AS (SELECT ...) SELECT * FROM cte","동일"),
    _r("mysql","postgresql","QUERY","재귀CTE",
       "WITH RECURSIVE cte AS (...) SELECT * FROM cte",
       "WITH RECURSIVE cte AS (...) SELECT * FROM cte","동일"),
    _r("mssql","mysql","QUERY","재귀CTE",
       "WITH cte AS (SELECT ... UNION ALL SELECT ...) SELECT * FROM cte",
       "WITH RECURSIVE cte AS (SELECT ... UNION ALL SELECT ...) SELECT * FROM cte",
       "RECURSIVE 키워드 추가 (MySQL 8.0+)"),
    _r("oracle","mysql","QUERY","CTE",
       "WITH cte AS (SELECT ...) SELECT * FROM cte",
       "WITH cte AS (SELECT ...) SELECT * FROM cte","동일 (MySQL 8.0+)"),
    _r("mysql","clickhouse","QUERY","CTE",
       "WITH cte AS (SELECT ...) SELECT * FROM cte",
       "WITH cte AS (SELECT ...) SELECT * FROM cte","ClickHouse 20.6+"),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [12] 날짜/시간 함수
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","FUNCTION","현재시간","NOW()", "GETDATE()",""),
    _r("mysql","mssql","FUNCTION","현재날짜","CURDATE()","CAST(GETDATE() AS DATE)",""),
    _r("mysql","mssql","FUNCTION","날짜더하기","DATE_ADD(d, INTERVAL n DAY)","DATEADD(DAY, n, d)","파라미터 순서 변경",True),
    _r("mysql","mssql","FUNCTION","날짜차이","DATEDIFF(d1, d2)","DATEDIFF(DAY, d2, d1)","파라미터 순서 변경",True),
    _r("mysql","mssql","FUNCTION","날짜포맷","DATE_FORMAT(d, '%Y-%m-%d')","FORMAT(d, 'yyyy-MM-dd')","포맷 문자열 변경",True),
    _r("mysql","mssql","FUNCTION","날짜추출","YEAR(d) / MONTH(d) / DAY(d)","YEAR(d) / MONTH(d) / DAY(d)","동일"),
    _r("mysql","mssql","FUNCTION","날짜변환","STR_TO_DATE('2024-01-01','%Y-%m-%d')","CONVERT(DATE, '2024-01-01')",""),
    _r("mysql","oracle","FUNCTION","현재시간","NOW()","SYSDATE",""),
    _r("mysql","oracle","FUNCTION","날짜더하기","DATE_ADD(d, INTERVAL n DAY)","d + n","Oracle 날짜 산술"),
    _r("mysql","oracle","FUNCTION","날짜차이","DATEDIFF(d1, d2)","d1 - d2","Oracle 날짜 뺄셈"),
    _r("mysql","postgresql","FUNCTION","날짜더하기","DATE_ADD(d, INTERVAL n DAY)","d + INTERVAL 'n day'",""),
    _r("mysql","postgresql","FUNCTION","날짜차이","DATEDIFF(d1, d2)","DATE_PART('day', d1 - d2)","또는 d1::date - d2::date"),
    _r("mysql","postgresql","FUNCTION","날짜포맷","DATE_FORMAT(d,'%Y-%m-%d')","TO_CHAR(d,'YYYY-MM-DD')",""),
    _r("mysql","bigquery","FUNCTION","날짜더하기","DATE_ADD(d, INTERVAL n DAY)","DATE_ADD(d, INTERVAL n DAY)","동일"),
    _r("mysql","bigquery","FUNCTION","날짜포맷","DATE_FORMAT(d,'%Y-%m-%d')","FORMAT_DATE('%Y-%m-%d', d)",""),
    _r("mysql","snowflake","FUNCTION","날짜더하기","DATE_ADD(d, INTERVAL n DAY)","DATEADD(DAY, n, d)",""),
    _r("mysql","clickhouse","FUNCTION","날짜더하기","DATE_ADD(d, INTERVAL n DAY)","addDays(d, n)",""),
    _r("mssql","mysql","FUNCTION","현재시간","GETDATE()","NOW()",""),
    _r("mssql","mysql","FUNCTION","날짜더하기","DATEADD(DAY, n, d)","DATE_ADD(d, INTERVAL n DAY)","파라미터 순서",True),
    _r("mssql","mysql","FUNCTION","날짜차이","DATEDIFF(DAY, d2, d1)","DATEDIFF(d1, d2)","파라미터 순서",True),
    _r("mssql","mysql","FUNCTION","날짜포맷","FORMAT(d, 'yyyy-MM-dd')","DATE_FORMAT(d,'%Y-%m-%d')",""),
    _r("oracle","mysql","FUNCTION","현재시간","SYSDATE","NOW()",""),
    _r("oracle","mysql","FUNCTION","날짜더하기","d + n","DATE_ADD(d, INTERVAL n DAY)",""),
    _r("oracle","mssql","FUNCTION","현재시간","SYSDATE","GETDATE()",""),
    _r("oracle","mssql","FUNCTION","날짜포맷","TO_CHAR(d,'YYYY-MM-DD')","FORMAT(d,'yyyy-MM-dd')",""),
    _r("oracle","postgresql","FUNCTION","날짜포맷","TO_CHAR(d,'YYYY-MM-DD')","TO_CHAR(d,'YYYY-MM-DD')","동일"),
    _r("postgresql","mysql","FUNCTION","날짜더하기","d + INTERVAL 'n day'","DATE_ADD(d, INTERVAL n DAY)",""),
    _r("postgresql","mssql","FUNCTION","날짜더하기","d + INTERVAL 'n day'","DATEADD(DAY, n, d)",""),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [13] 문자열 함수
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","FUNCTION","부분문자열","SUBSTRING(s,p,n) / SUBSTR(s,p,n)","SUBSTRING(s,p,n)","SUBSTR → SUBSTRING"),
    _r("mysql","mssql","FUNCTION","문자열길이","LENGTH(s) / CHAR_LENGTH(s)","LEN(s)",""),
    _r("mysql","mssql","FUNCTION","문자열연결","CONCAT(a,b,c)","CONCAT(a,b,c)","MSSQL 2012+ 동일; 구버전은 a+b+c"),
    _r("mysql","mssql","FUNCTION","NULL연결","CONCAT_WS(',',a,b)","CONCAT_WS(',',a,b)","MSSQL 2017+"),
    _r("mysql","mssql","FUNCTION","집계문자열","GROUP_CONCAT(col SEPARATOR ',')","STRING_AGG(col,',') WITHIN GROUP (ORDER BY col)","",True),
    _r("mysql","mssql","FUNCTION","NULL대체","IFNULL(a,b)","ISNULL(a,b)",""),
    _r("mysql","mssql","FUNCTION","조건함수","IF(cond,a,b)","IIF(cond,a,b)",""),
    _r("mysql","mssql","FUNCTION","위치검색","INSTR(s,sub)","CHARINDEX(sub,s)","파라미터 순서 반대",True),
    _r("mysql","mssql","FUNCTION","공백제거","TRIM(s)","LTRIM(RTRIM(s))","MSSQL 2017 이전",True),
    _r("mysql","mssql","FUNCTION","문자반복","REPEAT(s,n)","REPLICATE(s,n)",""),
    _r("mysql","mssql","FUNCTION","문자대체","REPLACE(s,old,new)","REPLACE(s,old,new)","동일"),
    _r("mysql","oracle","FUNCTION","문자열길이","LENGTH(s)","LENGTH(s)","동일"),
    _r("mysql","oracle","FUNCTION","NULL대체","IFNULL(a,b)","NVL(a,b)",""),
    _r("mysql","oracle","FUNCTION","조건함수","IF(cond,a,b)","DECODE(cond,TRUE,a,b)","또는 CASE WHEN",True),
    _r("mysql","oracle","FUNCTION","집계문자열","GROUP_CONCAT(col)","LISTAGG(col,',') WITHIN GROUP (ORDER BY col)",""),
    _r("mysql","oracle","FUNCTION","위치검색","INSTR(s,sub)","INSTR(s,sub)","동일"),
    _r("mysql","postgresql","FUNCTION","문자열길이","LENGTH(s)","LENGTH(s)","동일"),
    _r("mysql","postgresql","FUNCTION","NULL대체","IFNULL(a,b)","COALESCE(a,b)",""),
    _r("mysql","postgresql","FUNCTION","조건함수","IF(cond,a,b)","CASE WHEN cond THEN a ELSE b END",""),
    _r("mysql","postgresql","FUNCTION","집계문자열","GROUP_CONCAT(col SEPARATOR ',')","STRING_AGG(col, ',')",""),
    _r("mysql","postgresql","FUNCTION","위치검색","INSTR(s,sub)","POSITION(sub IN s)",""),
    _r("mysql","bigquery","FUNCTION","문자열길이","LENGTH(s)","LENGTH(s)","동일"),
    _r("mysql","bigquery","FUNCTION","NULL대체","IFNULL(a,b)","IFNULL(a,b)","동일"),
    _r("mysql","bigquery","FUNCTION","집계문자열","GROUP_CONCAT(col)","STRING_AGG(col,',')",""),
    _r("mysql","snowflake","FUNCTION","NULL대체","IFNULL(a,b)","IFNULL(a,b)","동일"),
    _r("mysql","snowflake","FUNCTION","집계문자열","GROUP_CONCAT(col)","LISTAGG(col,',')",""),
    _r("mysql","clickhouse","FUNCTION","집계문자열","GROUP_CONCAT(col)","groupArray(col)","또는 arrayStringConcat"),
    _r("mssql","mysql","FUNCTION","문자열길이","LEN(s)","CHAR_LENGTH(s)",""),
    _r("mssql","mysql","FUNCTION","NULL대체","ISNULL(a,b)","IFNULL(a,b)",""),
    _r("mssql","mysql","FUNCTION","조건함수","IIF(cond,a,b)","IF(cond,a,b)",""),
    _r("mssql","mysql","FUNCTION","집계문자열","STRING_AGG(col,',')","GROUP_CONCAT(col SEPARATOR ',')",""),
    _r("mssql","mysql","FUNCTION","위치검색","CHARINDEX(sub,s)","INSTR(s,sub)","파라미터 순서 반대",True),
    _r("mssql","mysql","FUNCTION","공백제거","LTRIM(RTRIM(s))","TRIM(s)",""),
    _r("mssql","mysql","FUNCTION","문자반복","REPLICATE(s,n)","REPEAT(s,n)",""),
    _r("oracle","mysql","FUNCTION","NULL대체","NVL(a,b)","IFNULL(a,b)",""),
    _r("oracle","mysql","FUNCTION","NVL2","NVL2(a,b,c)","IF(a IS NOT NULL, b, c)",""),
    _r("oracle","mysql","FUNCTION","집계문자열","LISTAGG(col,',') WITHIN GROUP (ORDER BY col)","GROUP_CONCAT(col ORDER BY col SEPARATOR ',')",""),
    _r("oracle","mssql","FUNCTION","NULL대체","NVL(a,b)","ISNULL(a,b)",""),
    _r("oracle","mssql","FUNCTION","집계문자열","LISTAGG(col,',') WITHIN GROUP (ORDER BY col)","STRING_AGG(col,',') WITHIN GROUP (ORDER BY col)","MSSQL 2017+"),
    _r("oracle","postgresql","FUNCTION","NULL대체","NVL(a,b)","COALESCE(a,b)",""),
    _r("oracle","postgresql","FUNCTION","집계문자열","LISTAGG(col,',') WITHIN GROUP (ORDER BY col)","STRING_AGG(col,',' ORDER BY col)",""),
    _r("postgresql","mysql","FUNCTION","NULL대체","COALESCE(a,b)","COALESCE(a,b)","동일"),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [14] 집계/윈도우 함수
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","FUNCTION","윈도우함수","ROW_NUMBER() OVER (...)","ROW_NUMBER() OVER (...)","동일 (MySQL 8.0+)"),
    _r("mysql","mssql","FUNCTION","윈도우함수","RANK() OVER (...)","RANK() OVER (...)","동일"),
    _r("mysql","mssql","FUNCTION","윈도우함수","LAG(col,1) OVER (...)","LAG(col,1) OVER (...)","동일"),
    _r("mysql","oracle","FUNCTION","윈도우함수","ROW_NUMBER() OVER (...)","ROW_NUMBER() OVER (...)","동일"),
    _r("mysql","clickhouse","FUNCTION","집계함수","COUNT(DISTINCT col)","uniqExact(col)","ClickHouse 방식"),
    _r("mysql","bigquery","FUNCTION","윈도우함수","ROW_NUMBER() OVER (...)","ROW_NUMBER() OVER (...)","동일"),
    _r("oracle","mysql","FUNCTION","분석함수","CONNECT BY (계층쿼리)","WITH RECURSIVE cte AS (...) (CTE 재귀)",
       "MySQL 8.0+ CTE 재귀로 대체",True),
    _r("oracle","mssql","FUNCTION","계층쿼리","START WITH ... CONNECT BY PRIOR","WITH cte AS (... UNION ALL ...) (재귀 CTE)","",True),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [15] 타입 캐스팅
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","FUNCTION","형변환","CAST(col AS CHAR)","CAST(col AS NVARCHAR(100))",""),
    _r("mysql","mssql","FUNCTION","형변환","CAST(col AS DATE)","CAST(col AS DATE)","동일"),
    _r("mysql","mssql","FUNCTION","형변환","CAST(col AS SIGNED)","CAST(col AS INT)",""),
    _r("mysql","oracle","FUNCTION","형변환","CAST(col AS CHAR)","TO_CHAR(col)",""),
    _r("mysql","oracle","FUNCTION","형변환","CAST(col AS DATE)","TO_DATE(col,'YYYY-MM-DD')","포맷 지정 필요",True),
    _r("mysql","postgresql","FUNCTION","형변환","CAST(col AS CHAR)","col::TEXT","또는 CAST(col AS TEXT)"),
    _r("mssql","mysql","FUNCTION","형변환","CONVERT(NVARCHAR, col)","CAST(col AS CHAR)",""),
    _r("mssql","mysql","FUNCTION","형변환","TRY_CAST(col AS INT)","/* MySQL은 TRY_CAST 없음 — CAST 또는 CONVERT 사용 */","오류 처리 주의",True),
    _r("oracle","mysql","FUNCTION","형변환","TO_NUMBER(s)","CAST(s AS DECIMAL)",""),
    _r("oracle","mysql","FUNCTION","형변환","TO_DATE(s,'YYYY-MM-DD')","STR_TO_DATE(s,'%Y-%m-%d')","포맷 문자열 변경",True),
    _r("oracle","mysql","FUNCTION","형변환","TO_CHAR(n,'FM999,999')","FORMAT(n,0)","",True),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [16] 트랜잭션
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","TRANSACTION","트랜잭션시작","START TRANSACTION","BEGIN TRANSACTION / BEGIN TRAN",""),
    _r("mysql","mssql","TRANSACTION","커밋","COMMIT","COMMIT TRANSACTION / COMMIT TRAN",""),
    _r("mysql","mssql","TRANSACTION","롤백","ROLLBACK","ROLLBACK TRANSACTION / ROLLBACK TRAN",""),
    _r("mysql","mssql","TRANSACTION","저장점","SAVEPOINT sp1","SAVE TRANSACTION sp1",""),
    _r("mysql","mssql","TRANSACTION","부분롤백","ROLLBACK TO SAVEPOINT sp1","ROLLBACK TRANSACTION sp1",""),
    _r("mysql","oracle","TRANSACTION","트랜잭션시작","START TRANSACTION","/* Oracle은 자동으로 트랜잭션 시작 */","DDL 자동 커밋 주의",True),
    _r("mysql","oracle","TRANSACTION","저장점","SAVEPOINT sp1","SAVEPOINT sp1","동일"),
    _r("mysql","postgresql","TRANSACTION","트랜잭션시작","START TRANSACTION","BEGIN","또는 START TRANSACTION"),
    _r("mssql","mysql","TRANSACTION","트랜잭션시작","BEGIN TRANSACTION","START TRANSACTION",""),
    _r("mssql","mysql","TRANSACTION","저장점","SAVE TRANSACTION sp1","SAVEPOINT sp1",""),
    _r("oracle","mysql","TRANSACTION","자동커밋","/* DDL 자동 커밋 — Oracle 특성 */","/* MySQL은 DDL 암시적 커밋 */","DDL 후 명시적 커밋 불필요",True),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [17] 예외/오류 처리
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","EXCEPTION","예외처리",
       "DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; END;",
       "BEGIN TRY ... END TRY BEGIN CATCH ROLLBACK; END CATCH",""),
    _r("mysql","mssql","EXCEPTION","오류발생",
       "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='오류'",
       "THROW 50001, '오류', 1",""),
    _r("mysql","oracle","EXCEPTION","예외처리",
       "DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ... END;",
       "EXCEPTION WHEN OTHERS THEN ...","",True),
    _r("mysql","oracle","EXCEPTION","오류발생",
       "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='오류'",
       "RAISE_APPLICATION_ERROR(-20001,'오류')","",True),
    _r("mysql","postgresql","EXCEPTION","예외처리",
       "DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ... END;",
       "EXCEPTION WHEN others THEN ...","plpgsql 내부",True),
    _r("mssql","mysql","EXCEPTION","예외처리",
       "BEGIN TRY ... END TRY BEGIN CATCH ... END CATCH",
       "DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ... END;",""),
    _r("mssql","mysql","EXCEPTION","오류발생",
       "RAISERROR('오류', 16, 1) / THROW 50001,'오류',1",
       "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='오류'",""),
    _r("oracle","mysql","EXCEPTION","예외처리",
       "EXCEPTION WHEN NO_DATA_FOUND THEN ... WHEN OTHERS THEN ...",
       "DECLARE NOT FOUND HANDLER FOR SQLSTATE '02000' ...; DECLARE EXIT HANDLER FOR SQLEXCEPTION ...;","",True),
    _r("oracle","mssql","EXCEPTION","예외처리",
       "EXCEPTION WHEN OTHERS THEN DBMS_OUTPUT.PUT_LINE(SQLERRM);",
       "BEGIN CATCH PRINT ERROR_MESSAGE() END CATCH","",True),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [18] 커서 (CURSOR)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","CURSOR","커서선언",
       "DECLARE cur CURSOR FOR SELECT col FROM tbl;",
       "DECLARE cur CURSOR FOR SELECT [col] FROM [tbl];",""),
    _r("mysql","mssql","CURSOR","커서열기","OPEN cur;","OPEN cur;","동일"),
    _r("mysql","mssql","CURSOR","커서읽기",
       "FETCH cur INTO v1;",
       "FETCH NEXT FROM cur INTO @v1;","NEXT 추가, @ 추가"),
    _r("mysql","mssql","CURSOR","커서닫기","CLOSE cur; DEALLOCATE cur;","CLOSE cur; DEALLOCATE cur;","동일"),
    _r("mysql","mssql","CURSOR","종료감지",
       "DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;",
       "WHILE @@FETCH_STATUS = 0 BEGIN ... FETCH NEXT ... END","구조 변경",True),
    _r("mssql","mysql","CURSOR","커서읽기",
       "FETCH NEXT FROM cur INTO @v1",
       "FETCH cur INTO v1","NEXT/@ 제거"),
    _r("oracle","mysql","CURSOR","커서선언",
       "CURSOR cur IS SELECT col FROM tbl;",
       "DECLARE cur CURSOR FOR SELECT col FROM tbl;","",True),
    _r("oracle","mysql","CURSOR","FOR LOOP",
       "FOR rec IN (SELECT col FROM tbl) LOOP ... END LOOP;",
       "DECLARE cur CURSOR FOR SELECT col FROM tbl; ... FETCH cur INTO v; ...",
       "Oracle FOR LOOP → MySQL 명시적 커서",True),
    _r("oracle","mssql","CURSOR","FOR LOOP",
       "FOR rec IN (SELECT ...) LOOP ... END LOOP;",
       "DECLARE cur CURSOR FOR SELECT ...; OPEN cur; FETCH NEXT FROM cur ...; ... DEALLOCATE cur;","",True),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [19] 동적 SQL (Dynamic SQL)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","DYNAMIC_SQL","동적실행",
       "SET @sql = 'SELECT ...'; PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;",
       "DECLARE @sql NVARCHAR(MAX) = N'SELECT ...'; EXEC sp_executesql @sql;","",True),
    _r("mssql","mysql","DYNAMIC_SQL","동적실행",
       "EXEC sp_executesql @sql, N'@p1 INT', @p1=1;",
       "SET @sql = 'SELECT ...'; PREPARE stmt FROM @sql; EXECUTE stmt USING @p1; DEALLOCATE PREPARE stmt;","",True),
    _r("oracle","mysql","DYNAMIC_SQL","동적실행",
       "EXECUTE IMMEDIATE sql_str USING p1;",
       "SET @sql = sql_str; PREPARE stmt FROM @sql; EXECUTE stmt USING p1; DEALLOCATE PREPARE stmt;","",True),
    _r("oracle","mssql","DYNAMIC_SQL","동적실행",
       "EXECUTE IMMEDIATE sql_str USING p1;",
       "EXEC sp_executesql @sql, N'@p1 TYPE', @p1=p1;","",True),
    _r("postgresql","mysql","DYNAMIC_SQL","동적실행",
       "EXECUTE sql_str USING p1;",
       "PREPARE stmt FROM sql_str; EXECUTE stmt USING @p1; DEALLOCATE PREPARE stmt;","",True),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [20] 임시 테이블
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","TEMP_TABLE","임시테이블생성",
       "CREATE TEMPORARY TABLE tmp (...)",
       "CREATE TABLE #tmp (...)","세션 스코프"),
    _r("mysql","mssql","TEMP_TABLE","임시테이블DROP",
       "DROP TEMPORARY TABLE IF EXISTS tmp",
       "DROP TABLE IF EXISTS #tmp",""),
    _r("mysql","oracle","TEMP_TABLE","임시테이블",
       "CREATE TEMPORARY TABLE tmp (...)",
       "CREATE GLOBAL TEMPORARY TABLE tmp (...) ON COMMIT DELETE ROWS","사전 정의 필요",True),
    _r("mysql","postgresql","TEMP_TABLE","임시테이블",
       "CREATE TEMPORARY TABLE tmp (...)",
       "CREATE TEMP TABLE tmp (...)",""),
    _r("mssql","mysql","TEMP_TABLE","임시테이블생성",
       "CREATE TABLE #tmp (...)",
       "CREATE TEMPORARY TABLE tmp (...)",""),
    _r("mssql","mysql","TEMP_TABLE","테이블변수",
       "DECLARE @tv TABLE (col INT)",
       "CREATE TEMPORARY TABLE tmp (col INT)","테이블 변수 → 임시 테이블",True),
    _r("oracle","mysql","TEMP_TABLE","글로벌임시",
       "CREATE GLOBAL TEMPORARY TABLE tmp (...) ON COMMIT DELETE ROWS",
       "CREATE TEMPORARY TABLE tmp (...)","세션 스코프로 변환",True),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [21] INSERT/UPDATE/DELETE 문법
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","DML","UPSERT",
       "INSERT INTO tbl (...) VALUES (...) ON DUPLICATE KEY UPDATE col=VALUES(col)",
       "MERGE [tbl] USING (VALUES (...)) src ON tbl.id=src.id WHEN MATCHED THEN UPDATE ... WHEN NOT MATCHED THEN INSERT ...","",True),
    _r("mysql","oracle","DML","UPSERT",
       "INSERT INTO tbl (...) VALUES (...) ON DUPLICATE KEY UPDATE col=VALUES(col)",
       "MERGE INTO tbl USING dual ON (id=...) WHEN MATCHED THEN UPDATE ... WHEN NOT MATCHED THEN INSERT ...","",True),
    _r("mysql","postgresql","DML","UPSERT",
       "INSERT INTO tbl (...) VALUES (...) ON DUPLICATE KEY UPDATE col=VALUES(col)",
       "INSERT INTO tbl (...) VALUES (...) ON CONFLICT (id) DO UPDATE SET col=EXCLUDED.col",""),
    _r("mysql","snowflake","DML","UPSERT",
       "INSERT INTO tbl ... ON DUPLICATE KEY UPDATE ...",
       "MERGE INTO tbl USING (SELECT ...) src ON tbl.id=src.id WHEN MATCHED THEN UPDATE ... WHEN NOT MATCHED THEN INSERT ...","",True),
    _r("mssql","mysql","DML","MERGE",
       "MERGE [tbl] USING src ON ... WHEN MATCHED THEN UPDATE ... WHEN NOT MATCHED THEN INSERT ...",
       "INSERT INTO tbl ... ON DUPLICATE KEY UPDATE ...","PK 충돌 기준",True),
    _r("mysql","mssql","DML","멀티행INSERT",
       "INSERT INTO tbl (col) VALUES (1),(2),(3)",
       "INSERT INTO [tbl] ([col]) VALUES (1),(2),(3)","MSSQL 2008+ 동일"),
    _r("oracle","mysql","DML","멀티행INSERT",
       "INSERT ALL INTO tbl (col) VALUES (1) INTO tbl (col) VALUES (2) SELECT 1 FROM DUAL",
       "INSERT INTO tbl (col) VALUES (1),(2)","",True),
    _r("mysql","mssql","DML","DELETE JOIN",
       "DELETE t1 FROM t1 JOIN t2 ON t1.id=t2.id WHERE ...",
       "DELETE t1 FROM [t1] JOIN [t2] ON [t1].id=[t2].id WHERE ...",""),
    _r("mysql","oracle","DML","DELETE JOIN",
       "DELETE t1 FROM t1 JOIN t2 ON t1.id=t2.id WHERE ...",
       "DELETE FROM t1 WHERE id IN (SELECT t1.id FROM t1 JOIN t2 ON t1.id=t2.id WHERE ...)","서브쿼리로 변환",True),
    _r("mysql","mssql","DML","UPDATE JOIN",
       "UPDATE t1 JOIN t2 ON t1.id=t2.id SET t1.col=t2.col",
       "UPDATE t1 SET t1.col=t2.col FROM [t1] JOIN [t2] ON t1.id=t2.id","구조 변경",True),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [22] 스키마/DB 참조
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","SYNTAX","DB참조",
       "SELECT * FROM db_name.tbl",
       "SELECT * FROM [db_name].[dbo].[tbl]","스키마 추가",True),
    _r("mysql","oracle","SYNTAX","DB참조",
       "SELECT * FROM db_name.tbl",
       "SELECT * FROM schema_name.tbl","DB → 스키마",True),
    _r("oracle","mysql","SYNTAX","DUAL","SELECT 1+1 FROM DUAL","SELECT 1+1","DUAL 제거"),
    _r("oracle","postgresql","SYNTAX","DUAL","SELECT 1+1 FROM DUAL","SELECT 1+1","DUAL 제거"),
    _r("oracle","mssql","SYNTAX","DUAL","SELECT SYSDATE FROM DUAL","SELECT GETDATE()","DUAL+SYSDATE 변환"),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [23] 권한/보안 (PERMISSION)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mysql","mssql","PERMISSION","권한부여",
       "GRANT SELECT ON tbl TO 'user'@'host'",
       "GRANT SELECT ON [dbo].[tbl] TO [user]",""),
    _r("mysql","mssql","PERMISSION","권한회수",
       "REVOKE SELECT ON tbl FROM 'user'@'host'",
       "REVOKE SELECT ON [dbo].[tbl] FROM [user]",""),
    _r("mysql","oracle","PERMISSION","권한부여",
       "GRANT SELECT ON tbl TO user",
       "GRANT SELECT ON tbl TO user","거의 동일"),
    _r("mysql","postgresql","PERMISSION","권한부여",
       "GRANT SELECT ON tbl TO user",
       "GRANT SELECT ON tbl TO user","동일"),
    _r("mssql","mysql","PERMISSION","역할",
       "CREATE ROLE [role]; GRANT SELECT ON [tbl] TO [role]",
       "CREATE ROLE 'role'; GRANT SELECT ON tbl TO 'role'@'%'",""),

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [24] 기타 DB별 특수 문법
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _r("mssql","mysql","SYNTAX","힌트제거",
       "SELECT * FROM [tbl] WITH (NOLOCK)",
       "SELECT * FROM `tbl`","NOLOCK 힌트 제거",True),
    _r("mssql","mysql","SYNTAX","힌트제거",
       "SELECT * FROM [tbl] WITH (ROWLOCK, UPDLOCK)",
       "SELECT * FROM `tbl` FOR UPDATE","락 힌트 변환",True),
    _r("oracle","mysql","SYNTAX","힌트제거",
       "SELECT /*+ INDEX(tbl idx) */ * FROM tbl",
       "SELECT * FROM `tbl` USE INDEX (idx)","힌트 방식 변경",True),
    _r("mysql","mssql","SYNTAX","주석","-- 주석 / # 주석","-- 주석","# 주석 제거",True),
    _r("mysql","oracle","SYNTAX","주석","-- 주석 / # 주석","-- 주석","# 주석 제거",True),
    _r("mysql","mssql","SYNTAX","문자열연결","'a' || 'b'","'a' + 'b'","또는 CONCAT()"),
    _r("oracle","mysql","SYNTAX","문자열연결","'a' || 'b'","CONCAT('a','b')",""),
    _r("postgresql","mysql","SYNTAX","문자열연결","'a' || 'b'","CONCAT('a','b')",""),
    _r("mysql","clickhouse","SYNTAX","문자열연결","CONCAT('a','b')","concat('a','b')","소문자"),
    _r("mysql","bigquery","SYNTAX","스키마참조","db.tbl","project.dataset.tbl","3단계 참조",True),
    _r("mysql","snowflake","SYNTAX","스키마참조","db.tbl","database.schema.tbl","3단계 참조",True),
]


def _init_rules():
    if len(_rules) == 0:
        for r in _DEFAULTS:
            rid = str(uuid.uuid4())[:8]
            _rules.set(rid, {"id": rid, **r})

_init_rules()


# ── REST API ──────────────────────────────────────────────

@router.get("/rules")
def list_rules(
    src_db:   str = "",
    tgt_db:   str = "",
    obj_type: str = "",
    category: str = "",
    q:        str = "",
):
    result = _rules.values()
    if src_db:   result = [r for r in result if r.get("src_db")   == src_db]
    if tgt_db:   result = [r for r in result if r.get("tgt_db")   == tgt_db]
    if obj_type: result = [r for r in result if r.get("obj_type") == obj_type]
    if category: result = [r for r in result if r.get("category") == category]
    if q:
        ql = q.lower()
        result = [r for r in result if
                  ql in r.get("src_syntax","").lower() or
                  ql in r.get("tgt_syntax","").lower() or
                  ql in r.get("note","").lower() or
                  ql in r.get("category","").lower()]
    return result


@router.post("/rules", status_code=201)
def create_rule(body: dict):
    rid  = str(uuid.uuid4())[:8]
    rule = {"id": rid, "custom": True, **body}
    _rules.set(rid, rule)
    return rule


@router.put("/rules/{rid}")
def update_rule(rid: str, body: dict):
    existing = _rules.get(rid)
    if existing is None:
        raise HTTPException(404, "규칙을 찾을 수 없습니다")
    updated = {**existing, **body, "id": rid}
    _rules.set(rid, updated)
    return updated


@router.delete("/rules/{rid}", status_code=204)
def delete_rule(rid: str):
    if rid not in _rules:
        raise HTTPException(404, "규칙을 찾을 수 없습니다")
    _rules.delete(rid)


@router.get("/stats")
def get_stats():
    rules = _rules.values()
    pairs = set(f"{r['src_db']}→{r['tgt_db']}" for r in rules)
    obj_types = {}
    categories = {}
    for r in rules:
        ot = r.get("obj_type","기타")
        ct = r.get("category","기타")
        obj_types[ot]   = obj_types.get(ot, 0) + 1
        categories[ct]  = categories.get(ct, 0) + 1
    return {
        "total":      len(rules),
        "pairs":      len(pairs),
        "warning":    sum(1 for r in rules if r.get("warning")),
        "custom":     sum(1 for r in rules if r.get("custom")),
        "by_obj_type":  obj_types,
        "by_category":  categories,
    }


@router.get("/categories")
def get_categories():
    rules = _rules.values()
    return sorted(set(r.get("category","기타") for r in rules))


@router.get("/obj-types")
def get_obj_types():
    rules = _rules.values()
    return sorted(set(r.get("obj_type","기타") for r in rules))
