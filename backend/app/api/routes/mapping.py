"""
app/api/routes/mapping.py
타입 매핑 규칙 API — JSON 영속성 적용

v10 #19 (2026-04-21):
  - 기본 규칙 14개 → 283개로 확장 (프론트의 하드코딩 데이터를 백엔드로 이식)
  - category 필드 정식 지원
  - TypeMapping 화면에서 편집/삭제 기능이 이 API 를 통해 동작
"""
from fastapi import APIRouter, HTTPException, Depends
from app.core.auth_deps import require_viewer, require_operator
import uuid
from app.core.store import Store

router = APIRouter()

_rules = Store("mapping_rules")

# 기본 규칙 카탈로그 (v10 #19b: 모듈 레벨로 승격 → seed-defaults 엔드포인트에서 재사용)
_BUILTIN_DEFAULTS = [
    {'src_db':'mysql','tgt_db':'mssql','src_type':'TINYINT(1)','tgt_type':'BIT','category':'부울','note':'0/1 → false/true','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'TINYINT UNSIGNED','tgt_type':'SMALLINT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'TINYINT','tgt_type':'TINYINT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'SMALLINT UNSIGNED','tgt_type':'INT','category':'숫자','note':'범위 확장','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'SMALLINT','tgt_type':'SMALLINT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'MEDIUMINT','tgt_type':'INT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'INT UNSIGNED','tgt_type':'BIGINT','category':'숫자','note':'범위 확장','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'INT','tgt_type':'INT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'BIGINT UNSIGNED','tgt_type':'DECIMAL(20,0)','category':'숫자','note':'오버플로 주의','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'BIGINT','tgt_type':'BIGINT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'FLOAT','tgt_type':'REAL','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'DOUBLE','tgt_type':'FLOAT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'DECIMAL(p,s)','tgt_type':'DECIMAL(p,s)','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'VARCHAR(n)','tgt_type':'NVARCHAR(n)','category':'문자열','note':'Collation 변경','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'CHAR(n)','tgt_type':'NCHAR(n)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'TEXT','tgt_type':'NVARCHAR(MAX)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'MEDIUMTEXT','tgt_type':'NVARCHAR(MAX)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'LONGTEXT','tgt_type':'NVARCHAR(MAX)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'ENUM','tgt_type':'NVARCHAR(255)','category':'문자열','note':'CHECK 제약 추가 권장','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'SET','tgt_type':'NVARCHAR(500)','category':'문자열','note':'정규화 권장','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'DATE','tgt_type':'DATE','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'TIME','tgt_type':'TIME(7)','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'DATETIME','tgt_type':'DATETIME2(6)','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'TIMESTAMP','tgt_type':'DATETIME2(6)','category':'날짜시간','note':'시간대 주의','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'YEAR','tgt_type':'SMALLINT','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'BLOB','tgt_type':'VARBINARY(MAX)','category':'바이너리','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'MEDIUMBLOB','tgt_type':'VARBINARY(MAX)','category':'바이너리','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'LONGBLOB','tgt_type':'VARBINARY(MAX)','category':'바이너리','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'BINARY(n)','tgt_type':'BINARY(n)','category':'바이너리','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'VARBINARY(n)','tgt_type':'VARBINARY(n)','category':'바이너리','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'JSON','tgt_type':'NVARCHAR(MAX)','category':'JSON-XML','note':'JSON 검증 없음','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'GEOMETRY','tgt_type':'GEOMETRY','category':'공간','note':'SRID 확인','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'postgresql','src_type':'TINYINT(1)','tgt_type':'BOOLEAN','category':'부울','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'postgresql','src_type':'TINYINT','tgt_type':'SMALLINT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'postgresql','src_type':'SMALLINT','tgt_type':'SMALLINT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'postgresql','src_type':'MEDIUMINT','tgt_type':'INTEGER','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'postgresql','src_type':'INT','tgt_type':'INTEGER','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'postgresql','src_type':'INT AUTO_INCREMENT','tgt_type':'SERIAL','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'postgresql','src_type':'BIGINT','tgt_type':'BIGINT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'postgresql','src_type':'FLOAT','tgt_type':'REAL','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'postgresql','src_type':'DOUBLE','tgt_type':'DOUBLE PRECISION','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'postgresql','src_type':'DECIMAL(p,s)','tgt_type':'NUMERIC(p,s)','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'postgresql','src_type':'VARCHAR(n)','tgt_type':'VARCHAR(n)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'postgresql','src_type':'TEXT','tgt_type':'TEXT','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'postgresql','src_type':'LONGTEXT','tgt_type':'TEXT','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'postgresql','src_type':'ENUM','tgt_type':'TEXT','category':'문자열','note':'CREATE TYPE 권장','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'postgresql','src_type':'DATETIME','tgt_type':'TIMESTAMP','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'postgresql','src_type':'TIMESTAMP','tgt_type':'TIMESTAMPTZ','category':'날짜시간','note':'시간대 처리','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'postgresql','src_type':'BLOB','tgt_type':'BYTEA','category':'바이너리','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'postgresql','src_type':'JSON','tgt_type':'JSONB','category':'JSON-XML','note':'JSONB 인덱싱 가능','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'postgresql','src_type':'GEOMETRY','tgt_type':'GEOMETRY (PostGIS)','category':'공간','note':'PostGIS 설치 필요','warning':True,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'BIT','tgt_type':'TINYINT(1)','category':'부울','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'TINYINT','tgt_type':'TINYINT UNSIGNED','category':'숫자','note':'MSSQL은 0~255','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'SMALLINT','tgt_type':'SMALLINT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'INT','tgt_type':'INT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'BIGINT','tgt_type':'BIGINT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'REAL','tgt_type':'FLOAT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'FLOAT','tgt_type':'DOUBLE','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'DECIMAL(p,s)','tgt_type':'DECIMAL(p,s)','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'MONEY','tgt_type':'DECIMAL(19,4)','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'SMALLMONEY','tgt_type':'DECIMAL(10,4)','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'NVARCHAR(MAX)','tgt_type':'LONGTEXT','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'NVARCHAR(n)','tgt_type':'VARCHAR(n)','category':'문자열','note':'UTF8MB4 설정','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'VARCHAR(MAX)','tgt_type':'LONGTEXT','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'VARCHAR(n)','tgt_type':'VARCHAR(n)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'CHAR(n)','tgt_type':'CHAR(n)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'NCHAR(n)','tgt_type':'CHAR(n)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'TEXT','tgt_type':'LONGTEXT','category':'문자열','note':'deprecated 타입','warning':True,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'DATE','tgt_type':'DATE','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'TIME(n)','tgt_type':'TIME(6)','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'DATETIME','tgt_type':'DATETIME','category':'날짜시간','note':'밀리초 손실','warning':True,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'DATETIME2(n)','tgt_type':'DATETIME(6)','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'SMALLDATETIME','tgt_type':'DATETIME','category':'날짜시간','note':'분 단위 정밀도','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'DATETIMEOFFSET','tgt_type':'DATETIME(6)','category':'날짜시간','note':'시간대 정보 손실','warning':True,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'VARBINARY(MAX)','tgt_type':'LONGBLOB','category':'바이너리','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'VARBINARY(n)','tgt_type':'VARBINARY(n)','category':'바이너리','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'BINARY(n)','tgt_type':'BINARY(n)','category':'바이너리','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'UNIQUEIDENTIFIER','tgt_type':'CHAR(36)','category':'문자열','note':'UUID 형식','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'XML','tgt_type':'LONGTEXT','category':'JSON-XML','note':'XML 검증 없음','warning':True,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'NUMBER(1)','tgt_type':'TINYINT(1)','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'NUMBER(p,s)','tgt_type':'DECIMAL(p,s)','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'NUMBER(p)','tgt_type':'BIGINT','category':'숫자','note':'p≤18','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'NUMBER','tgt_type':'DOUBLE','category':'숫자','note':'정밀도 주의','warning':True,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'FLOAT','tgt_type':'DOUBLE','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'BINARY_FLOAT','tgt_type':'FLOAT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'BINARY_DOUBLE','tgt_type':'DOUBLE','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'VARCHAR2(n)','tgt_type':'VARCHAR(n)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'NVARCHAR2(n)','tgt_type':'VARCHAR(n)','category':'문자열','note':'UTF8MB4','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'CHAR(n)','tgt_type':'CHAR(n)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'NCHAR(n)','tgt_type':'CHAR(n)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'CLOB','tgt_type':'LONGTEXT','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'NCLOB','tgt_type':'LONGTEXT','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'LONG','tgt_type':'LONGTEXT','category':'문자열','note':'deprecated','warning':True,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'DATE','tgt_type':'DATETIME','category':'날짜시간','note':'Oracle DATE는 시간 포함','warning':True,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'TIMESTAMP(n)','tgt_type':'DATETIME(6)','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'TIMESTAMP WITH TIME ZONE','tgt_type':'DATETIME(6)','category':'날짜시간','note':'시간대 손실','warning':True,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'INTERVAL YEAR TO MONTH','tgt_type':'VARCHAR(30)','category':'날짜시간','note':'수동 변환 필요','warning':True,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'BLOB','tgt_type':'LONGBLOB','category':'바이너리','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'RAW(n)','tgt_type':'VARBINARY(n)','category':'바이너리','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'LONG RAW','tgt_type':'LONGBLOB','category':'바이너리','note':'deprecated','warning':True,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'XMLTYPE','tgt_type':'LONGTEXT','category':'JSON-XML','note':'XML 검증 없음','warning':True,'custom':False},
    {'src_db':'oracle','tgt_db':'mysql','src_type':'ROWID','tgt_type':'VARCHAR(18)','category':'기타','note':'의미 변환 필요','warning':True,'custom':False},
    {'src_db':'oracle','tgt_db':'postgresql','src_type':'NUMBER(p,s)','tgt_type':'NUMERIC(p,s)','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'postgresql','src_type':'NUMBER(p)','tgt_type':'BIGINT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'postgresql','src_type':'NUMBER','tgt_type':'NUMERIC','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'postgresql','src_type':'VARCHAR2(n)','tgt_type':'VARCHAR(n)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'postgresql','src_type':'CLOB','tgt_type':'TEXT','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'postgresql','src_type':'DATE','tgt_type':'TIMESTAMP','category':'날짜시간','note':'Oracle DATE 시간 포함','warning':True,'custom':False},
    {'src_db':'oracle','tgt_db':'postgresql','src_type':'TIMESTAMP(n)','tgt_type':'TIMESTAMP(n)','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'postgresql','src_type':'TIMESTAMP WITH TIME ZONE','tgt_type':'TIMESTAMPTZ','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'postgresql','src_type':'BLOB','tgt_type':'BYTEA','category':'바이너리','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'postgresql','src_type':'RAW(n)','tgt_type':'BYTEA','category':'바이너리','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'postgresql','src_type':'XMLTYPE','tgt_type':'XML','category':'JSON-XML','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'postgresql','src_type':'SDO_GEOMETRY','tgt_type':'GEOMETRY (PostGIS)','category':'공간','note':'PostGIS 필요','warning':True,'custom':False},
    {'src_db':'oracle','tgt_db':'mssql','src_type':'NUMBER(p,s)','tgt_type':'DECIMAL(p,s)','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mssql','src_type':'NUMBER(p)','tgt_type':'BIGINT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mssql','src_type':'NUMBER','tgt_type':'FLOAT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mssql','src_type':'VARCHAR2(n)','tgt_type':'NVARCHAR(n)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mssql','src_type':'NVARCHAR2(n)','tgt_type':'NVARCHAR(n)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mssql','src_type':'CLOB','tgt_type':'NVARCHAR(MAX)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mssql','src_type':'BLOB','tgt_type':'VARBINARY(MAX)','category':'바이너리','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mssql','src_type':'DATE','tgt_type':'DATETIME2(0)','category':'날짜시간','note':'Oracle DATE 시간 포함','warning':True,'custom':False},
    {'src_db':'oracle','tgt_db':'mssql','src_type':'TIMESTAMP(n)','tgt_type':'DATETIME2(n)','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'oracle','tgt_db':'mssql','src_type':'XMLTYPE','tgt_type':'XML','category':'JSON-XML','note':'','warning':False,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'BOOLEAN','tgt_type':'TINYINT(1)','category':'부울','note':'','warning':False,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'SMALLINT','tgt_type':'SMALLINT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'INTEGER','tgt_type':'INT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'BIGINT','tgt_type':'BIGINT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'SERIAL','tgt_type':'INT AUTO_INCREMENT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'BIGSERIAL','tgt_type':'BIGINT AUTO_INCREMENT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'REAL','tgt_type':'FLOAT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'DOUBLE PRECISION','tgt_type':'DOUBLE','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'NUMERIC(p,s)','tgt_type':'DECIMAL(p,s)','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'VARCHAR(n)','tgt_type':'VARCHAR(n)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'TEXT','tgt_type':'LONGTEXT','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'CHAR(n)','tgt_type':'CHAR(n)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'TIMESTAMP','tgt_type':'DATETIME(6)','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'TIMESTAMPTZ','tgt_type':'DATETIME(6)','category':'날짜시간','note':'시간대 손실','warning':True,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'DATE','tgt_type':'DATE','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'TIME','tgt_type':'TIME','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'BYTEA','tgt_type':'LONGBLOB','category':'바이너리','note':'','warning':False,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'JSON','tgt_type':'JSON','category':'JSON-XML','note':'','warning':False,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'JSONB','tgt_type':'JSON','category':'JSON-XML','note':'인덱스 정보 손실','warning':True,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'UUID','tgt_type':'CHAR(36)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'ARRAY','tgt_type':'JSON','category':'기타','note':'정규화 권장','warning':True,'custom':False},
    {'src_db':'postgresql','tgt_db':'mysql','src_type':'HSTORE','tgt_type':'JSON','category':'JSON-XML','note':'','warning':False,'custom':False},
    {'src_db':'db2','tgt_db':'mysql','src_type':'SMALLINT','tgt_type':'SMALLINT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'db2','tgt_db':'mysql','src_type':'INTEGER','tgt_type':'INT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'db2','tgt_db':'mysql','src_type':'BIGINT','tgt_type':'BIGINT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'db2','tgt_db':'mysql','src_type':'DECIMAL(p,s)','tgt_type':'DECIMAL(p,s)','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'db2','tgt_db':'mysql','src_type':'REAL','tgt_type':'FLOAT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'db2','tgt_db':'mysql','src_type':'DOUBLE','tgt_type':'DOUBLE','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'db2','tgt_db':'mysql','src_type':'VARCHAR(n)','tgt_type':'VARCHAR(n)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'db2','tgt_db':'mysql','src_type':'CHAR(n)','tgt_type':'CHAR(n)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'db2','tgt_db':'mysql','src_type':'CLOB(n)','tgt_type':'LONGTEXT','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'db2','tgt_db':'mysql','src_type':'DATE','tgt_type':'DATE','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'db2','tgt_db':'mysql','src_type':'TIME','tgt_type':'TIME','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'db2','tgt_db':'mysql','src_type':'TIMESTAMP(n)','tgt_type':'DATETIME(6)','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'db2','tgt_db':'mysql','src_type':'BLOB(n)','tgt_type':'LONGBLOB','category':'바이너리','note':'','warning':False,'custom':False},
    {'src_db':'db2','tgt_db':'mysql','src_type':'XML','tgt_type':'LONGTEXT','category':'JSON-XML','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'snowflake','src_type':'TINYINT','tgt_type':'NUMBER(3,0)','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'snowflake','src_type':'INT','tgt_type':'NUMBER(10,0)','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'snowflake','src_type':'BIGINT','tgt_type':'NUMBER(19,0)','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'snowflake','src_type':'FLOAT','tgt_type':'FLOAT','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'snowflake','src_type':'DOUBLE','tgt_type':'DOUBLE','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'snowflake','src_type':'DECIMAL(p,s)','tgt_type':'NUMBER(p,s)','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'snowflake','src_type':'VARCHAR(n)','tgt_type':'VARCHAR(n)','category':'문자열','note':'최대 16777216','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'snowflake','src_type':'TEXT','tgt_type':'TEXT','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'snowflake','src_type':'DATETIME','tgt_type':'TIMESTAMP_NTZ','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'snowflake','src_type':'TIMESTAMP','tgt_type':'TIMESTAMP_LTZ','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'snowflake','src_type':'DATE','tgt_type':'DATE','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'snowflake','src_type':'BLOB','tgt_type':'BINARY','category':'바이너리','note':'최대 8MB','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'snowflake','src_type':'JSON','tgt_type':'VARIANT','category':'JSON-XML','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'bigquery','src_type':'TINYINT','tgt_type':'INT64','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'bigquery','src_type':'INT','tgt_type':'INT64','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'bigquery','src_type':'BIGINT','tgt_type':'INT64','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'bigquery','src_type':'FLOAT','tgt_type':'FLOAT64','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'bigquery','src_type':'DOUBLE','tgt_type':'FLOAT64','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'bigquery','src_type':'DECIMAL(p,s)','tgt_type':'NUMERIC(p,s)','category':'숫자','note':'최대 NUMERIC(29,9)','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'bigquery','src_type':'TINYINT(1)','tgt_type':'BOOL','category':'부울','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'bigquery','src_type':'VARCHAR(n)','tgt_type':'STRING','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'bigquery','src_type':'TEXT','tgt_type':'STRING','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'bigquery','src_type':'DATETIME','tgt_type':'DATETIME','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'bigquery','src_type':'TIMESTAMP','tgt_type':'TIMESTAMP','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'bigquery','src_type':'DATE','tgt_type':'DATE','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'bigquery','src_type':'BLOB','tgt_type':'BYTES','category':'바이너리','note':'최대 10MB','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'bigquery','src_type':'JSON','tgt_type':'JSON','category':'JSON-XML','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'clickhouse','src_type':'TINYINT','tgt_type':'Int8','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'clickhouse','src_type':'SMALLINT','tgt_type':'Int16','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'clickhouse','src_type':'INT','tgt_type':'Int32','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'clickhouse','src_type':'BIGINT','tgt_type':'Int64','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'clickhouse','src_type':'INT UNSIGNED','tgt_type':'UInt32','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'clickhouse','src_type':'FLOAT','tgt_type':'Float32','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'clickhouse','src_type':'DOUBLE','tgt_type':'Float64','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'clickhouse','src_type':'DECIMAL(p,s)','tgt_type':'Decimal(p,s)','category':'숫자','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'clickhouse','src_type':'VARCHAR(n)','tgt_type':'String','category':'문자열','note':'ClickHouse String은 가변','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'clickhouse','src_type':'TEXT','tgt_type':'String','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'clickhouse','src_type':'CHAR(n)','tgt_type':'FixedString(n)','category':'문자열','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'clickhouse','src_type':'DATE','tgt_type':'Date','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'clickhouse','src_type':'DATETIME','tgt_type':'DateTime64(6)','category':'날짜시간','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'clickhouse','src_type':'TINYINT(1)','tgt_type':'Bool','category':'부울','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'clickhouse','src_type':'JSON','tgt_type':'String','category':'JSON-XML','note':'JSON 파싱은 함수 사용','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'DATE_FORMAT(col,\'%Y-%m-%d\')','tgt_type':'FORMAT(col,\'yyyy-MM-dd\')','category':'날짜함수','note':'포맷: %Y→yyyy %m→MM %d→dd %H→HH %i→mm %s→ss','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'DATE_FORMAT(col,\'%Y-%m\')','tgt_type':'FORMAT(col,\'yyyy-MM\')','category':'날짜함수','note':'월 단위 집계. GROUP BY 포함 동일 변환','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'DATE_FORMAT(col,\'%H:%i:%s\')','tgt_type':'FORMAT(col,\'HH:mm:ss\')','category':'날짜함수','note':'시간 포맷','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'NOW()','tgt_type':'GETDATE()','category':'날짜함수','note':'현재 날짜/시간','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'CURDATE()','tgt_type':'CAST(GETDATE() AS DATE)','category':'날짜함수','note':'날짜만 반환','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'CURTIME()','tgt_type':'CAST(GETDATE() AS TIME)','category':'날짜함수','note':'시간만 반환','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'DATEDIFF(a,b)','tgt_type':'DATEDIFF(day,b,a)','category':'날짜함수','note':'⚠ 인자 순서 반대! MySQL=a-b, MSSQL=단위+역순','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'DATE_ADD(col,INTERVAL n DAY)','tgt_type':'DATEADD(day,n,col)','category':'날짜함수','note':'INTERVAL DAY/MONTH/YEAR/HOUR/MINUTE/SECOND','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'DATE_SUB(col,INTERVAL n DAY)','tgt_type':'DATEADD(day,-n,col)','category':'날짜함수','note':'DATE_SUB → DATEADD 음수값','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'TIMESTAMPDIFF(MONTH,a,b)','tgt_type':'DATEDIFF(month,a,b)','category':'날짜함수','note':'단위가 첫 번째 인자로 이동','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'HOUR(col)/MINUTE(col)/SECOND(col)','tgt_type':'DATEPART(hour/minute/second,col)','category':'날짜함수','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'DAYOFWEEK(col)','tgt_type':'DATEPART(weekday,col)','category':'날짜함수','note':'⚠ SET DATEFIRST 영향. 확인 필요','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'WEEK(col)','tgt_type':'DATEPART(week,col)','category':'날짜함수','note':'⚠ 주차 계산 기준 다를 수 있음','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'STR_TO_DATE(str,fmt)','tgt_type':'CONVERT(DATETIME,str,120)','category':'날짜함수','note':'형식 120=ISO datetime 112=yyyyMMdd','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'FROM_UNIXTIME(ts)','tgt_type':'DATEADD(second,ts,\'1970-01-01\')','category':'날짜함수','note':'Unix 타임스탬프 변환','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'UNIX_TIMESTAMP(col)','tgt_type':'DATEDIFF(second,\'1970-01-01\',col)','category':'날짜함수','note':'Unix 타임스탬프 역변환','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'LAST_DAY(col)','tgt_type':'EOMONTH(col)','category':'날짜함수','note':'월 마지막 날. MSSQL 2012+','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'IFNULL(a,b)','tgt_type':'ISNULL(a,b)','category':'문자열함수','note':'NULL 대체','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'IF(cond,a,b)','tgt_type':'IIF(cond,a,b)','category':'문자열함수','note':'MSSQL 2012+. 구버전은 CASE WHEN','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'GROUP_CONCAT(col SEPARATOR \',\')','tgt_type':'STRING_AGG(col,\',\')','category':'문자열함수','note':'⚠ MSSQL 2017+. 구버전은 FOR XML PATH','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'GROUP_CONCAT(col ORDER BY col)','tgt_type':'STRING_AGG(col,\',\') WITHIN GROUP (ORDER BY col)','category':'문자열함수','note':'정렬 포함','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'SUBSTR(str,pos,len)','tgt_type':'SUBSTRING(str,pos,len)','category':'문자열함수','note':'함수명만 다름','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'LOCATE(sub,str)','tgt_type':'CHARINDEX(sub,str)','category':'문자열함수','note':'인자 순서 동일','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'INSTR(str,sub)','tgt_type':'CHARINDEX(sub,str)','category':'문자열함수','note':'⚠ 인자 순서 반대! INSTR(str,sub)→CHARINDEX(sub,str)','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'LENGTH(str)','tgt_type':'LEN(str)','category':'문자열함수','note':'⚠ MySQL=바이트수 vs MSSQL=문자수. 멀티바이트 주의','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'CHAR_LENGTH(str)','tgt_type':'LEN(str)','category':'문자열함수','note':'문자 수 기준 동일','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'LPAD(str,len,pad)','tgt_type':'RIGHT(REPLICATE(pad,len)+str,len)','category':'문자열함수','note':'MSSQL LPAD 없음','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'RPAD(str,len,pad)','tgt_type':'LEFT(str+REPLICATE(pad,len),len)','category':'문자열함수','note':'MSSQL RPAD 없음','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'REPEAT(str,n)','tgt_type':'REPLICATE(str,n)','category':'문자열함수','note':'함수명만 다름','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'INSERT(str,pos,len,new)','tgt_type':'STUFF(str,pos,len,new)','category':'문자열함수','note':'함수명만 다름','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'SUBSTRING_INDEX(str,del,n)','tgt_type':'(CHARINDEX 조합 필요)','category':'문자열함수','note':'⚠ MSSQL 직접 미지원','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'ELT(n,v1,v2)','tgt_type':'CHOOSE(n,v1,v2)','category':'문자열함수','note':'MSSQL 2012+','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'FIELD(val,v1,v2)','tgt_type':'CASE WHEN val=v1 THEN 1 WHEN val=v2 THEN 2 END','category':'문자열함수','note':'⚠ MSSQL 미지원','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'TRUNCATE(n,d)','tgt_type':'ROUND(n,d,1)','category':'수학함수','note':'3번째 인자=1이면 TRUNCATE 동작','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'POW(a,b)','tgt_type':'POWER(a,b)','category':'수학함수','note':'함수명만 다름','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'STD(col)','tgt_type':'STDEV(col)','category':'수학함수','note':'표본표준편차','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'GREATEST(a,b,...)','tgt_type':'(SELECT MAX(v) FROM (VALUES(a),(b)) t(v))','category':'수학함수','note':'⚠ MSSQL 미지원','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'LEAST(a,b,...)','tgt_type':'(SELECT MIN(v) FROM (VALUES(a),(b)) t(v))','category':'수학함수','note':'⚠ MSSQL 미지원','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'ISNULL(col) 불리언반환','tgt_type':'CASE WHEN col IS NULL THEN 1 ELSE 0 END','category':'조건함수','note':'⚠ MySQL ISNULL=불리언 vs MSSQL ISNULL=대체값. 완전히 다름','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'COALESCE(a,b,...)','tgt_type':'COALESCE(a,b,...)','category':'조건함수','note':'동일','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'GREATEST/LEAST','tgt_type':'VALUES 서브쿼리','category':'조건함수','note':'⚠ MSSQL 미지원','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'LIMIT n','tgt_type':'SELECT TOP n ...','category':'페이징','note':'⚠ LIMIT 제거 후 SELECT 뒤 TOP n으로 이동','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'LIMIT n OFFSET m','tgt_type':'OFFSET m ROWS FETCH NEXT n ROWS ONLY','category':'페이징','note':'ORDER BY 필수. MSSQL 2012+','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'JSON_EXTRACT(col,\'$.key\')','tgt_type':'JSON_VALUE(col,\'$.key\')','category':'JSON함수','note':'스칼라 값 추출','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'col->\'$.key\' 단축문법','tgt_type':'JSON_VALUE(col,\'$.key\')','category':'JSON함수','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'JSON_EXTRACT(col,\'$.arr\') 배열','tgt_type':'JSON_QUERY(col,\'$.arr\')','category':'JSON함수','note':'객체/배열은 JSON_QUERY','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'JSON_ARRAYAGG(col)','tgt_type':'\'[\'+STRING_AGG(col,\',\')+\']\'','category':'JSON함수','note':'⚠ MSSQL 2017+','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'AUTO_INCREMENT','tgt_type':'IDENTITY(1,1)','category':'DDL문법','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'`백틱 식별자`','tgt_type':'[대괄호 식별자]','category':'DDL문법','note':'','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'ENGINE=InnoDB CHARSET=utf8mb4','tgt_type':'(생략 가능)','category':'DDL문법','note':'MSSQL에 없는 개념','warning':False,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'UNSIGNED INT','tgt_type':'INT (UNSIGNED 미지원)','category':'DDL문법','note':'⚠ 범위 초과 주의','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'ENUM("a","b")','tgt_type':'VARCHAR(n) + CHECK 제약','category':'DDL문법','note':'⚠ ENUM 없음','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'INSERT INTO ... ON DUPLICATE KEY UPDATE','tgt_type':'MERGE INTO ... WHEN MATCHED UPDATE WHEN NOT MATCHED INSERT','category':'DDL문법','note':'⚠ UPSERT 문법 완전히 다름','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'INSERT IGNORE INTO','tgt_type':'TRY/CATCH 또는 MERGE','category':'DDL문법','note':'⚠ IGNORE 없음','warning':True,'custom':False},
    {'src_db':'mysql','tgt_db':'mssql','src_type':'REPLACE INTO','tgt_type':'MERGE INTO','category':'DDL문법','note':'DELETE+INSERT → MERGE','warning':True,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'FORMAT(col,\'yyyy-MM-dd\')','tgt_type':'DATE_FORMAT(col,\'%Y-%m-%d\')','category':'날짜함수','note':'포맷 역변환','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'FORMAT(col,\'yyyy-MM\')','tgt_type':'DATE_FORMAT(col,\'%Y-%m\')','category':'날짜함수','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'GETDATE()','tgt_type':'NOW()','category':'날짜함수','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'GETUTCDATE()','tgt_type':'UTC_TIMESTAMP()','category':'날짜함수','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'DATEADD(day,n,col)','tgt_type':'DATE_ADD(col,INTERVAL n DAY)','category':'날짜함수','note':'인자 순서 다름','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'DATEDIFF(day,a,b)','tgt_type':'DATEDIFF(b,a)','category':'날짜함수','note':'⚠ 인자 순서 반대!','warning':True,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'DATEPART(month,col)','tgt_type':'MONTH(col)','category':'날짜함수','note':'year→YEAR month→MONTH day→DAY','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'CONVERT(VARCHAR,col,120)','tgt_type':'DATE_FORMAT(col,\'%Y-%m-%d %H:%i:%s\')','category':'날짜함수','note':'형식 120=ISO datetime','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'EOMONTH(col)','tgt_type':'LAST_DAY(col)','category':'날짜함수','note':'월 마지막 날','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'ISNULL(a,b)','tgt_type':'IFNULL(a,b)','category':'문자열함수','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'IIF(cond,a,b)','tgt_type':'IF(cond,a,b)','category':'문자열함수','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'STRING_AGG(col,\',\')','tgt_type':'GROUP_CONCAT(col SEPARATOR \',\')','category':'문자열함수','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'CHARINDEX(sub,str)','tgt_type':'LOCATE(sub,str)','category':'문자열함수','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'LEN(str)','tgt_type':'CHAR_LENGTH(str)','category':'문자열함수','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'REPLICATE(str,n)','tgt_type':'REPEAT(str,n)','category':'문자열함수','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'STUFF(str,pos,len,new)','tgt_type':'INSERT(str,pos,len,new)','category':'문자열함수','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'SELECT TOP n ...','tgt_type':'SELECT ... LIMIT n','category':'페이징','note':'⚠ TOP 제거 후 끝에 LIMIT','warning':True,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'OFFSET n ROWS FETCH NEXT m ROWS ONLY','tgt_type':'LIMIT m OFFSET n','category':'페이징','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'IDENTITY(1,1)','tgt_type':'AUTO_INCREMENT','category':'DDL문법','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'[대괄호 식별자]','tgt_type':'`백틱 식별자`','category':'DDL문법','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'NVARCHAR(n)','tgt_type':'VARCHAR(n)','category':'DDL문법','note':'MySQL VARCHAR는 모두 유니코드','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'NVARCHAR(MAX)','tgt_type':'LONGTEXT','category':'DDL문법','note':'','warning':False,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'CREATE OR ALTER PROCEDURE','tgt_type':'DROP PROCEDURE IF EXISTS + CREATE','category':'DDL문법','note':'⚠ MySQL OR REPLACE 없음','warning':True,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'ROLLBACK (트리거 내)','tgt_type':'SIGNAL SQLSTATE 45000 (BEFORE 트리거)','category':'DDL문법','note':'⚠ MySQL 트리거 ROLLBACK 불가','warning':True,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'MERGE INTO ... WHEN MATCHED','tgt_type':'INSERT ON DUPLICATE KEY UPDATE','category':'DDL문법','note':'⚠ UPSERT 문법 완전히 다름','warning':True,'custom':False},
    {'src_db':'mssql','tgt_db':'mysql','src_type':'WITH CTE AS (...)','tgt_type':'WITH CTE AS (...)','category':'DDL문법','note':'MySQL 8.0+. 구버전 서브쿼리 대체','warning':False,'custom':False},
]

# 초기 시드 — 테이블이 완전히 비어있을 때만
if len(_rules) == 0:
    for r in _BUILTIN_DEFAULTS:
        rid = str(uuid.uuid4())[:8]
        _rules.set(rid, {"id": rid, **r})


@router.get("/rules")
def list_rules(src_db: str = "", tgt_db: str = "", category: str = "", q: str = ""):
    """전체 규칙 조회 (필터 지원)"""
    result = _rules.values()
    if src_db:   result = [r for r in result if r.get("src_db")   == src_db]
    if tgt_db:   result = [r for r in result if r.get("tgt_db")   == tgt_db]
    if category: result = [r for r in result if r.get("category") == category]
    if q:
        ql = q.lower()
        result = [r for r in result if
                  ql in (r.get("src_type") or "").lower() or
                  ql in (r.get("tgt_type") or "").lower() or
                  ql in (r.get("note") or "").lower() or
                  ql in (r.get("category") or "").lower()]
    return result


@router.get("/stats")
def get_stats():
    """매핑 규칙 통계 (대시보드/상단 KPI 용)"""
    rules = _rules.values()
    pairs = set(f"{r.get('src_db')}→{r.get('tgt_db')}" for r in rules)
    categories = {}
    for r in rules:
        c = r.get("category", "기타")
        categories[c] = categories.get(c, 0) + 1
    return {
        "total":        len(rules),
        "pairs":        len(pairs),
        "warning":      sum(1 for r in rules if r.get("warning")),
        "custom":       sum(1 for r in rules if r.get("custom")),
        "ai_learned":   sum(1 for r in rules if r.get("source") == "ai_learned"),
        "by_category":  categories,
    }


@router.get("/categories")
def get_categories():
    """중복 제거된 카테고리 목록 (필터 드롭다운 용)"""
    rules = _rules.values()
    return sorted(set(r.get("category", "기타") for r in rules))


@router.post("/rules", status_code=201)
def create_rule(body: dict):
    rid  = str(uuid.uuid4())[:8]
    rule = {"id": rid, "custom": True, **body}
    _rules.set(rid, rule)
    return rule


@router.put("/rules/{rule_id}")
def update_rule(rule_id: str, body: dict):
    existing = _rules.get(rule_id)
    if existing is None:
        raise HTTPException(404, "규칙을 찾을 수 없습니다")
    # id 는 URL 에서 온 값으로 고정 (본문에 변조된 id 무시)
    updated = {**existing, **body, "id": rule_id}
    # 내부 임시 플래그 저장소에 남기지 않음
    updated.pop("_dirty", None)
    updated.pop("_new", None)
    _rules.set(rule_id, updated)
    return updated


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: str):
    if rule_id not in _rules:
        raise HTTPException(404, "규칙을 찾을 수 없습니다")
    _rules.delete(rule_id)

# ══════════════════════════════════════════════════════════
# v10 #19b — 기본 규칙 추가 시드 (관리자용)
# ══════════════════════════════════════════════════════════
@router.post("/seed-defaults")
def seed_defaults(overwrite: bool = False):
    """
    _BUILTIN_DEFAULTS 카탈로그를 현재 스토어에 병합.
    - (src_db, tgt_db, src_type) 조합 기준 중복 체크
    - 기본: 중복은 건너뜀 (안전 — 사용자 수정본 보존)
    - overwrite=True: 중복되어도 덮어씀 (category/note 갱신)
    
    반환: {inserted, skipped, total_after}
    """
    existing = list(_rules.values())
    existing_keys = {
        (r.get("src_db"), r.get("tgt_db"), r.get("src_type")): r.get("id")
        for r in existing
    }

    inserted = 0
    skipped  = 0
    overwritten = 0

    for d in _BUILTIN_DEFAULTS:
        key = (d["src_db"], d["tgt_db"], d["src_type"])
        if key in existing_keys:
            if overwrite:
                rid = existing_keys[key]
                prev = _rules.get(rid) or {}
                # 사용자 커스텀 플래그는 보존
                merged = {**prev, **d, "id": rid,
                          "custom": prev.get("custom", False)}
                _rules.set(rid, merged)
                overwritten += 1
            else:
                skipped += 1
            continue
        rid = str(uuid.uuid4())[:8]
        _rules.set(rid, {"id": rid, **d})
        inserted += 1

    return {
        "inserted":    inserted,
        "skipped":     skipped,
        "overwritten": overwritten,
        "total_after": len(_rules),
        "builtin_total": len(_BUILTIN_DEFAULTS),
    }

