"""
app/api/routes/sql_converter.py
SQL 쿼리 / DDL 파일 일괄 변환 API
소스 DB 방언(Dialect) → 타겟 DB 방언으로 변환
"""
import logging
logger = logging.getLogger("databridge.sql_converter")
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import re, io, zipfile, time

router = APIRouter()


# ── 변환 규칙 테이블 ──────────────────────────────────────
# (패턴, 치환, 설명)
# 순서 중요: 구체적인 규칙을 먼저 처리

RULES: dict[str, list[tuple]] = {

    # ══ MySQL → MSSQL ════════════════════════════════════
    "mysql→mssql": [
        # 타입 변환
        (r'\bTINYINT\(1\)',                  'BIT',                   'TINYINT(1)→BIT'),
        (r'\bTINYINT\s+UNSIGNED\b',          'SMALLINT',              'tinyint unsigned→SMALLINT'),
        (r'\bSMALLINT\s+UNSIGNED\b',         'INT',                   'smallint unsigned→INT'),
        (r'\bMEDIUMINT\s+UNSIGNED\b',        'INT',                   'mediumint unsigned→INT'),
        (r'\bINT\s+UNSIGNED\b',              'BIGINT',                'int unsigned→BIGINT'),
        (r'\bMEDIUMINT\b',                   'INT',                   'MEDIUMINT→INT'),
        (r'\bTINYINT\b',                     'TINYINT',               'TINYINT OK'),
        (r'\bDOUBLE\b',                      'FLOAT',                 'DOUBLE→FLOAT'),
        (r'\bLONGTEXT\b',                    'NVARCHAR(MAX)',          'LONGTEXT→NVARCHAR(MAX)'),
        (r'\bMEDIUMTEXT\b',                  'NVARCHAR(MAX)',          'MEDIUMTEXT→NVARCHAR(MAX)'),
        (r'\bTEXT\b',                        'NVARCHAR(MAX)',          'TEXT→NVARCHAR(MAX)'),
        (r'\bLONGBLOB\b',                    'VARBINARY(MAX)',         'LONGBLOB→VARBINARY(MAX)'),
        (r'\bMEDIUMBLOB\b',                  'VARBINARY(MAX)',         'MEDIUMBLOB→VARBINARY(MAX)'),
        (r'\bBLOB\b',                        'VARBINARY(MAX)',         'BLOB→VARBINARY(MAX)'),
        (r'\bVARCHAR\b',                     'NVARCHAR',              'VARCHAR→NVARCHAR'),
        (r'\bCHAR\b',                        'NCHAR',                 'CHAR→NCHAR'),
        (r'\bDATETIME\b',                    'DATETIME2(6)',           'DATETIME→DATETIME2'),
        (r'\bTIMESTAMP\b',                   'DATETIME2(6)',           'TIMESTAMP→DATETIME2'),
        (r'ENUM\([^)]+\)',                   'NVARCHAR(255)',          'ENUM→NVARCHAR(255)'),
        (r'\bJSON\b',                        'NVARCHAR(MAX)',          'JSON→NVARCHAR(MAX)'),
        # AUTO_INCREMENT
        (r'\bAUTO_INCREMENT\b',              'IDENTITY(1,1)',          'AUTO_INCREMENT→IDENTITY'),
        # 백틱 → 대괄호
        (r'`([^`]+)`',                       r'[\1]',                 '백틱→대괄호'),
        # UNSIGNED 제거 (이미 타입 변환됨)
        (r'\s+UNSIGNED\b',                   '',                      'UNSIGNED 제거'),
        # 함수 변환
        (r'\bNOW\(\)',                        'GETDATE()',              'NOW()→GETDATE()'),
        (r'\bCURDATE\(\)',                    'CAST(GETDATE() AS DATE)','CURDATE()→CAST'),
        (r'\bCURTIME\(\)',                    'CAST(GETDATE() AS TIME)','CURTIME()→CAST'),
        (r'\bIFNULL\s*\(',                   'ISNULL(',               'IFNULL→ISNULL'),
        (r'\bIF\s*\(',                        'IIF(',                  'IF(→IIF('),
        # GROUP_CONCAT→STRING_AGG: 사전처리에서 정확히 처리됨
        (r'\bSTR_TO_DATE\s*\(([^,]+),\s*[^)]+\)', r'CONVERT(DATE,\1)',  'STR_TO_DATE→CONVERT'),
        (r"\bDATE_FORMAT\s*\(([^,]+),\s*'([^']*)'\s*\)", lambda m: f"FORMAT({m.group(1)}, '{_date_format_mysql_to_mssql(m.group(2))}')", 'DATE_FORMAT→FORMAT'),
        # LIMIT→TOP: 사전처리에서 실제 변환됨
        # LIMIT→주석: 사전처리에서 실제 변환됨
        # ENGINE / CHARSET 제거
        (r'\s*ENGINE\s*=\s*\w+',             '',                      'ENGINE 제거'),
        (r'\s*DEFAULT\s+CHARSET\s*=\s*\w+', '',                      'CHARSET 제거'),
        (r'\s*CHARACTER\s+SET\s+\w+',        '',                      'CHARACTER SET 제거'),
        (r'\s*COLLATE\s+\w+',               '',                      'COLLATE 제거'),
        # CURRENT_TIMESTAMP
        (r'\bCURRENT_TIMESTAMP\b',           'GETDATE()',              'CURRENT_TIMESTAMP→GETDATE()'),
    ],

    # ══ MySQL → PostgreSQL ════════════════════════════════
    "mysql→postgresql": [
        (r'\bTINYINT\(1\)',                  'BOOLEAN',               'TINYINT(1)→BOOLEAN'),
        (r'\bTINYINT\s+UNSIGNED\b',          'SMALLINT',              'tinyint unsigned→SMALLINT'),
        (r'\bSMALLINT\s+UNSIGNED\b',         'INTEGER',               'smallint unsigned→INTEGER'),
        (r'\bINT\s+UNSIGNED\b',              'BIGINT',                'int unsigned→BIGINT'),
        (r'\bINT\s+AUTO_INCREMENT\b',        'SERIAL',                'INT AUTO_INCREMENT→SERIAL'),
        (r'\bBIGINT\s+AUTO_INCREMENT\b',     'BIGSERIAL',             'BIGINT AUTO_INCREMENT→BIGSERIAL'),
        (r'\bSMALLINT\s+AUTO_INCREMENT\b',   'SMALLSERIAL',           'SMALLINT AUTO_INCREMENT→SMALLSERIAL'),
        (r'\bAUTO_INCREMENT\b',              '',                      'AUTO_INCREMENT 제거'),
        (r'\bMEDIUMINT\b',                   'INTEGER',               'MEDIUMINT→INTEGER'),
        (r'\bTINYINT\b',                     'SMALLINT',              'TINYINT→SMALLINT'),
        (r'\bDOUBLE\b',                      'DOUBLE PRECISION',      'DOUBLE→DOUBLE PRECISION'),
        (r'\bLONGTEXT\b',                    'TEXT',                  'LONGTEXT→TEXT'),
        (r'\bMEDIUMTEXT\b',                  'TEXT',                  'MEDIUMTEXT→TEXT'),
        (r'\bLONGBLOB\b',                    'BYTEA',                 'LONGBLOB→BYTEA'),
        (r'\bBLOB\b',                        'BYTEA',                 'BLOB→BYTEA'),
        (r'\bDATETIME\b',                    'TIMESTAMP',             'DATETIME→TIMESTAMP'),
        (r'\bTIMESTAMP\b',                   'TIMESTAMP',             'TIMESTAMP OK'),
        (r'ENUM\([^)]+\)',                   'TEXT',                  'ENUM→TEXT'),
        (r'`([^`]+)`',                       r'"\1"',                 '백틱→큰따옴표'),
        (r'\s+UNSIGNED\b',                   '',                      'UNSIGNED 제거'),
        (r'\bNOW\(\)',                        'NOW()',                 'NOW() OK'),
        (r'\bIFNULL\s*\(',                   'COALESCE(',             'IFNULL→COALESCE'),
        (r'\bIF\s*\(',                        'CASE WHEN /* IF( 변환 필요 */ (',  'IF→CASE'),
        (r'\bLIMIT\s+(\d+)\s+OFFSET\s+(\d+)', r'LIMIT \1 OFFSET \2', 'LIMIT OFFSET OK'),
        (r'\s*ENGINE\s*=\s*\w+',             '',                      'ENGINE 제거'),
        (r'\s*DEFAULT\s+CHARSET\s*=\s*\w+', '',                      'CHARSET 제거'),
        (r'\s*CHARACTER\s+SET\s+\w+',        '',                      'CHARACTER SET 제거'),
        (r'\s*COLLATE\s+\w+',               '',                      'COLLATE 제거'),
        (r'\bCURRENT_TIMESTAMP\b',           'NOW()',                 'CURRENT_TIMESTAMP→NOW()'),
    ],

    # ══ MSSQL → MySQL ════════════════════════════════════
    "mssql→mysql": [
        # ── 데이터 타입 ──────────────────────────────────────────
        (r'IDENTITY\(\d+,\s*\d+\)',              'AUTO_INCREMENT',           'IDENTITY→AUTO_INCREMENT'),
        (r'\bNVARCHAR\s*\(MAX\)',                'LONGTEXT',                 'NVARCHAR(MAX)→LONGTEXT'),
        (r'\bNVARCHAR\b',                          'VARCHAR',                  'NVARCHAR→VARCHAR'),
        (r'\bNCHAR\b',                             'CHAR',                     'NCHAR→CHAR'),
        (r'\bVARBINARY\s*\(MAX\)',               'LONGBLOB',                 'VARBINARY(MAX)→LONGBLOB'),
        (r'\bVARBINARY\b',                         'VARBINARY',                'VARBINARY OK'),
        (r'\bDATETIME2\s*\(\d+\)',              'DATETIME(6)',               'DATETIME2→DATETIME(6)'),
        (r'\bDATETIME2\b',                         'DATETIME(6)',               'DATETIME2→DATETIME(6)'),
        (r'\bSMALLDATETIME\b',                     'DATETIME',                 'SMALLDATETIME→DATETIME'),
        (r'\bBIT\b',                               'TINYINT(1)',               'BIT→TINYINT(1)'),
        (r'\bMONEY\b',                             'DECIMAL(19,4)',            'MONEY→DECIMAL'),
        (r'\bSMALLMONEY\b',                        'DECIMAL(10,4)',            'SMALLMONEY→DECIMAL'),
        (r'\bUNIQUEIDENTIFIER\b',                  'VARCHAR(36)',              'UNIQUEIDENTIFIER→VARCHAR(36)'),
        (r'\bXML\b',                               'LONGTEXT',                 'XML→LONGTEXT'),
        (r'\bIMAGE\b',                             'LONGBLOB',                 'IMAGE→LONGBLOB'),
        # ── 식별자 ──────────────────────────────────────────────
        (r'\[([^\]]+)\]',                          r'`\1`',                   '대괄호→백틱'),
        (r'\bdbo\.',                                '',                         'dbo. 제거'),
        (r"\bN'", r"'",                            "N 리터럴 제거"),
        # ── 기본 함수 ────────────────────────────────────────────
        (r'\bGETDATE\(\)',                         'NOW()',                    'GETDATE()→NOW()'),
        (r'\bGETUTCDATE\(\)',                      'UTC_TIMESTAMP()',          'GETUTCDATE()→UTC_TIMESTAMP()'),
        (r'\bSYSDATETIME\(\)',                     'NOW(6)',                   'SYSDATETIME()→NOW(6)'),
        (r'\bISNULL\s*\(',                         'IFNULL(',                  'ISNULL→IFNULL'),
        (r'\bIIF\s*\(',                            'IF(',                      'IIF→IF('),
        (r'\bCHOOSE\s*\(',                         'ELT(',                    'CHOOSE→ELT'),
        (r'\bSTRING_AGG\s*\(',                     'GROUP_CONCAT(',            'STRING_AGG→GROUP_CONCAT'),
        (r'\bLEN\s*\(',                            'LENGTH(',                  'LEN→LENGTH'),
        (r'\bCHARINDEX\s*\(([^,]+),([^,)]+)\)',  r'LOCATE(\1,\2)',         'CHARINDEX→LOCATE'),
        (r'\bCHARINDEX\s*\(([^,]+),([^,]+),([^)]+)\)', r'LOCATE(\1,\2,\3)', 'CHARINDEX(3args)→LOCATE'),
        (r'\bPATINDEX\s*\(',                       'LOCATE(',                 'PATINDEX→LOCATE'),
        (r'\bREPLICATE\s*\(',                      'REPEAT(',                 'REPLICATE→REPEAT'),
        (r'\bSTUFF\s*\(([^,]+),([^,]+),([^,]+),([^)]+)\)',
            r'INSERT(\1,\2,\3,\4)',               'STUFF→INSERT'),
        (r'\bCONCAT_WS\s*\(',                      'CONCAT_WS(',              'CONCAT_WS OK'),
        (r'\bCAST\s*\((.+?)\s+AS\s+NVARCHAR(?:\(\d+\))?\)',
            r'CAST(\1 AS CHAR)',                     'CAST AS NVARCHAR→CHAR'),
        (r'\bCAST\s*\((.+?)\s+AS\s+VARCHAR(?:\(\d+\))?\)',
            r'CAST(\1 AS CHAR)',                     'CAST AS VARCHAR→CHAR'),
        # ── 날짜 함수 ────────────────────────────────────────────
        (r'\bEOMONTH\s*\(([^)]+)\)',
            r'LAST_DAY(\1)',                         'EOMONTH→LAST_DAY'),
        (r"\bDATENAME\s*\(\s*(?:WEEKDAY|DW)\s*,\s*([^)]+)\)",
            r"DAYNAME(\1)",                          'DATENAME(WEEKDAY)→DAYNAME'),
        (r"\bDATENAME\s*\(\s*(?:MONTH|MM)\s*,\s*([^)]+)\)",
            r"MONTHNAME(\1)",                        'DATENAME(MONTH)→MONTHNAME'),
        (r"\bDATENAME\s*\(\s*(?:YEAR|YY|YYYY)\s*,\s*([^)]+)\)",
            r"YEAR(\1)",                             'DATENAME(YEAR)→YEAR'),
        (r"\bDATEPART\s*\(\s*(?:YEAR|YY|YYYY)\s*,\s*([^)]+)\)",
            r"YEAR(\1)",                             'DATEPART(YEAR)→YEAR'),
        (r"\bDATEPART\s*\(\s*(?:MONTH|MM|M)\s*,\s*([^)]+)\)",
            r"MONTH(\1)",                            'DATEPART(MONTH)→MONTH'),
        (r"\bDATEPART\s*\(\s*(?:DAY|DD|D)\s*,\s*([^)]+)\)",
            r"DAY(\1)",                              'DATEPART(DAY)→DAY'),
        (r"\bDATEPART\s*\(\s*(?:HOUR|HH)\s*,\s*([^)]+)\)",
            r"HOUR(\1)",                             'DATEPART(HOUR)→HOUR'),
        (r"\bDATEPART\s*\(\s*(?:MINUTE|MI|N)\s*,\s*([^)]+)\)",
            r"MINUTE(\1)",                           'DATEPART(MINUTE)→MINUTE'),
        (r"\bDATEPART\s*\(\s*(?:WEEKDAY|DW)\s*,\s*([^)]+)\)",
            r"WEEKDAY(\1)+1",                        'DATEPART(WEEKDAY)→WEEKDAY'),
        (r"\bDATEPART\s*\(\s*QUARTER\s*,\s*([^)]+)\)",
            r"QUARTER(\1)",                          'DATEPART(QUARTER)→QUARTER'),
        (r"\bYEAR\s*\(",                           "YEAR(",                   'YEAR OK'),
        (r"\bMONTH\s*\(",                          "MONTH(",                  'MONTH OK'),
        (r"\bDAY\s*\(",                            "DAY(",                    'DAY OK'),
        # DATEDIFF: YEAR 단위는 TIMESTAMPDIFF로 (정확도), 아래 사전처리에서 처리됨
        # ── NULL 정렬 보정 ────────────────────────────────────────
        # MSSQL: NULL LAST by default DESC, MySQL: NULL FIRST by default DESC
        # ORDER BY x DESC → ORDER BY x IS NULL ASC, x DESC
        (r'\bORDER\s+BY\s+(.+?)\s+DESC\s*(?:;|$)',
            r'ORDER BY \1 IS NULL, \1 DESC',       'ORDER BY DESC NULL 정렬 보정'),
        # ── 집합 연산 ────────────────────────────────────────────
        (r'\bEXCEPT\b',                             'EXCEPT',                  'EXCEPT OK (MySQL 8.0.31+)'),
        (r'\bINTERSECT\b',                          'INTERSECT',               'INTERSECT OK (MySQL 8.0.31+)'),
        # ── PIVOT/UNPIVOT 경고 ────────────────────────────────────
        (r'\bPIVOT\s*\(',                          '/* PIVOT→CASE WHEN 변환 필요 */ PIVOT(',  'PIVOT 주석 추가'),
        (r'\bUNPIVOT\s*\(',                        '/* UNPIVOT→UNION ALL 변환 필요 */ UNPIVOT(', 'UNPIVOT 주석 추가'),
        # ── MERGE 경고 ────────────────────────────────────────────
        (r'\bMERGE\b',                              '/* MSSQL MERGE→MySQL INSERT ... ON DUPLICATE KEY UPDATE */ MERGE', 'MERGE 주석'),
        # ── FOR JSON / FOR XML 경고 ───────────────────────────────
        (r'FOR\s+JSON\s+(?:PATH|AUTO)',              '/* FOR JSON PATH→JSON_ARRAYAGG/JSON_OBJECT 변환 필요 */', 'FOR JSON 주석'),
        (r'FOR\s+XML\s+\w+',                       '/* FOR XML→GROUP_CONCAT 변환 필요 */', 'FOR XML 주석'),
        # ── TRY/CATCH → 주석 ─────────────────────────────────────
        (r'\bBEGIN\s+TRY\b',                       '-- BEGIN TRY (MySQL: DECLARE HANDLER 사용)',  'BEGIN TRY 주석'),
        (r'\bEND\s+TRY\b',                         '-- END TRY',              'END TRY 주석'),
        (r'\bBEGIN\s+CATCH\b',                     '-- BEGIN CATCH',          'BEGIN CATCH 주석'),
        (r'\bEND\s+CATCH\b',                       '-- END CATCH',            'END CATCH 주석'),
        # ── 기타 ─────────────────────────────────────────────────
        (r'\bTOP\s+(\d+)\b',                      r'-- TOP \1 → LIMIT \1 을 쿼리 끝으로 이동', 'TOP→LIMIT 안내'),
        (r'\bNOLOCK\b',                             '',                        'NOLOCK 제거'),
        (r'WITH\s*\(\s*NOLOCK\s*\)',              '',                        'WITH(NOLOCK) 제거'),
        (r'\bSET\s+NOCOUNT\s+ON\s*;?',            '',                        'SET NOCOUNT ON 제거'),
        (r'\bSET\s+XACT_ABORT\s+ON\s*;?',         '',                        'SET XACT_ABORT ON 제거'),
        (r'\bPRINT\s+',                             '-- PRINT ',               'PRINT→주석'),
        (r"\bTHROW\b",   "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT", "THROW→SIGNAL"),
        (r"\bRAISERROR\s*\(", "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = (", "RAISERROR→SIGNAL"),
        # ── 문자열 연결: + → CONCAT ──────────────────────────────
        # (숫자+숫자는 건드리지 않고, 문자열 컬럼+문자열 리터럴만)
        # 주의: 복잡한 경우는 Claude AI로 처리
        # ── DATEADD → DATE_ADD/DATE_SUB ─────────────────────────
        (r"\bDATEADD\s*\(\s*(?:YEAR|YY|YYYY)\s*,\s*(-?\d+)\s*,\s*([^)]+)\)",
            r"DATE_ADD(\2, INTERVAL \1 YEAR)",         "DATEADD(YEAR)→DATE_ADD INTERVAL"),
        (r"\bDATEADD\s*\(\s*(?:MONTH|MM|M)\s*,\s*(-?\d+)\s*,\s*([^)]+)\)",
            r"DATE_ADD(\2, INTERVAL \1 MONTH)",        "DATEADD(MONTH)→DATE_ADD INTERVAL"),
        (r"\bDATEADD\s*\(\s*(?:DAY|DD|D)\s*,\s*(-?\d+)\s*,\s*([^)]+)\)",
            r"DATE_ADD(\2, INTERVAL \1 DAY)",          "DATEADD(DAY)→DATE_ADD INTERVAL"),
        (r"\bDATEADD\s*\(\s*(?:HOUR|HH)\s*,\s*(-?\d+)\s*,\s*([^)]+)\)",
            r"DATE_ADD(\2, INTERVAL \1 HOUR)",         "DATEADD(HOUR)→DATE_ADD INTERVAL"),
        (r"\bDATEADD\s*\(\s*(?:MINUTE|MI|N)\s*,\s*(-?\d+)\s*,\s*([^)]+)\)",
            r"DATE_ADD(\2, INTERVAL \1 MINUTE)",       "DATEADD(MINUTE)→DATE_ADD INTERVAL"),
        (r"\bDATEADD\s*\(\s*(?:SECOND|SS|S)\s*,\s*(-?\d+)\s*,\s*([^)]+)\)",
            r"DATE_ADD(\2, INTERVAL \1 SECOND)",       "DATEADD(SECOND)→DATE_ADD INTERVAL"),
        (r"\bDATEADD\s*\(\s*(?:WEEK|WK|WW)\s*,\s*(-?\d+)\s*,\s*([^)]+)\)",
            r"DATE_ADD(\2, INTERVAL \1 WEEK)",         "DATEADD(WEEK)→DATE_ADD INTERVAL"),
        # ── FULL OUTER JOIN → LEFT JOIN UNION ALL RIGHT JOIN ──────
        (r"\bFULL\s+OUTER\s+JOIN\b",
            r"LEFT JOIN /* FULL OUTER JOIN→LEFT+RIGHT UNION 필요 */", "FULL OUTER JOIN 주석"),
        # ── 문자열 연결 + → CONCAT ─────────────────────────────────
        # 문자열 리터럴 간 + 연결 (패턴: '...' + '...' 또는 컬럼+'...')
        (r"(\w+)\s*\+\s*('[^']*')",
            r"CONCAT(\1, \2)",                         "문자열+ → CONCAT (단순)"),
        (r"('[^']*')\s*\+\s*(\w+)",
            r"CONCAT(\1, \2)",                         "문자열+ → CONCAT (단순2)"),
        # ── CONVERT → CAST ────────────────────────────────────────
        (r"\bCONVERT\s*\(\s*VARCHAR(?:\(\d+\))?\s*,\s*([^)]+)\)",
            r"CAST(\1 AS CHAR)",                        "CONVERT VARCHAR→CAST CHAR"),
        (r"\bCONVERT\s*\(\s*NVARCHAR(?:\(\d+\))?\s*,\s*([^)]+)\)",
            r"CAST(\1 AS CHAR)",                        "CONVERT NVARCHAR→CAST CHAR"),
        (r"\bCONVERT\s*\(\s*INT\s*,\s*([^)]+)\)",
            r"CAST(\1 AS SIGNED)",                      "CONVERT INT→CAST SIGNED"),
        (r"\bCONVERT\s*\(\s*BIGINT\s*,\s*([^)]+)\)",
            r"CAST(\1 AS SIGNED)",                      "CONVERT BIGINT→CAST SIGNED"),
        (r"\bCONVERT\s*\(\s*DATE\s*,\s*([^)]+)\)",
            r"DATE(\1)",                                "CONVERT DATE→DATE()"),
        (r"\bCONVERT\s*\(\s*DATETIME\s*,\s*([^)]+)\)",
            r"CAST(\1 AS DATETIME)",                    "CONVERT DATETIME→CAST DATETIME"),
        # ── SCOPE_IDENTITY / @@IDENTITY ───────────────────────────
        (r"\bSCOPE_IDENTITY\(\)",                     "LAST_INSERT_ID()",   "SCOPE_IDENTITY→LAST_INSERT_ID"),
        (r"\b@@IDENTITY\b",                            "LAST_INSERT_ID()",   "@@IDENTITY→LAST_INSERT_ID"),
        (r"\b@@ROWCOUNT\b",                            "ROW_COUNT()",         "@@ROWCOUNT→ROW_COUNT()"),
        (r"\b@@ERROR\b",                               "/* @@ERROR→핸들러 사용 */", "@@ERROR 주석"),
        # ── TRIM 함수 ─────────────────────────────────────────────
        (r"\bLTRIM\s*\(",                             "LTRIM(",              "LTRIM OK"),
        (r"\bRTRIM\s*\(",                             "RTRIM(",              "RTRIM OK"),
        # ── IIF 추가 변환 ──────────────────────────────────────────
        (r"\bNULLIF\s*\(",                            "NULLIF(",             "NULLIF OK"),
        (r"\bCOALESCE\s*\(",                          "COALESCE(",          "COALESCE OK"),
        # FORMAT→DATE_FORMAT: 아래 사전처리에서 처리
    ],

    # ══ Oracle → MySQL ════════════════════════════════════
    "oracle→mysql": [
        (r'\bNUMBER\s*\((\d+),\s*(\d+)\)',  r'DECIMAL(\1,\2)',       'NUMBER→DECIMAL'),
        (r'\bNUMBER\s*\((\d+)\)',            r'INT',                  'NUMBER(n)→INT'),
        (r'\bNUMBER\b',                      'DECIMAL(18,4)',         'NUMBER→DECIMAL'),
        (r'\bVARCHAR2\b',                    'VARCHAR',               'VARCHAR2→VARCHAR'),
        (r'\bNVARCHAR2\b',                   'VARCHAR',               'NVARCHAR2→VARCHAR'),
        (r'\bCLOB\b',                        'LONGTEXT',              'CLOB→LONGTEXT'),
        (r'\bNCLOB\b',                       'LONGTEXT',              'NCLOB→LONGTEXT'),
        (r'\bBLOB\b',                        'LONGBLOB',              'BLOB→LONGBLOB'),
        (r'\bRAW\b',                         'VARBINARY',             'RAW→VARBINARY'),
        (r'\bINTEGER\b',                     'INT',                   'INTEGER→INT'),
        (r'\bSYSDATE\b',                     'NOW()',                 'SYSDATE→NOW()'),
        (r'\bNVL\s*\(',                      'IFNULL(',               'NVL→IFNULL'),
        (r'\bNVL2\s*\(',                     'IF(',                   'NVL2→IF('),
        (r'\bDECODE\s*\(',                   'CASE /* DECODE → */ (',  'DECODE→CASE 안내'),
        (r'\bROWNUM\b',                      '-- ROWNUM (MySQL: LIMIT 사용)',  'ROWNUM→LIMIT 안내'),
        (r'"([^"]+)"',                       r'`\1`',                 '큰따옴표→백틱'),
        (r'\|\|',                            'CONCAT',                '||→CONCAT 안내'),
        (r'\bTO_DATE\s*\([^)]+\)',           'STR_TO_DATE(/* 형식 확인 */)',  'TO_DATE→STR_TO_DATE'),
        (r'\bTO_CHAR\s*\([^)]+\)',           'DATE_FORMAT(/* 형식 확인 */)',   'TO_CHAR→DATE_FORMAT'),
        (r'\bTRUNC\s*\(',                    'TRUNCATE(',             'TRUNC→TRUNCATE'),
        (r'\bINSTR\s*\(',                    'LOCATE(',               'INSTR→LOCATE'),
        (r'\bLENGTH\s*\(',                   'LENGTH(',               'LENGTH OK'),
        (r'\bSUBSTR\s*\(',                   'SUBSTRING(',            'SUBSTR→SUBSTRING'),
    ],

    # ══ Oracle → PostgreSQL ═══════════════════════════════
    "oracle→postgresql": [
        (r'\bNUMBER\s*\((\d+),\s*(\d+)\)',  r'NUMERIC(\1,\2)',       'NUMBER→NUMERIC'),
        (r'\bNUMBER\s*\((\d+)\)',            r'INTEGER',              'NUMBER(n)→INTEGER'),
        (r'\bNUMBER\b',                      'NUMERIC',               'NUMBER→NUMERIC'),
        (r'\bVARCHAR2\b',                    'VARCHAR',               'VARCHAR2→VARCHAR'),
        (r'\bNVARCHAR2\b',                   'VARCHAR',               'NVARCHAR2→VARCHAR'),
        (r'\bCLOB\b',                        'TEXT',                  'CLOB→TEXT'),
        (r'\bBLOB\b',                        'BYTEA',                 'BLOB→BYTEA'),
        (r'\bRAW\b',                         'BYTEA',                 'RAW→BYTEA'),
        (r'\bSYSDATE\b',                     'NOW()',                 'SYSDATE→NOW()'),
        (r'\bNVL\s*\(',                      'COALESCE(',             'NVL→COALESCE'),
        (r'\bDECODE\s*\(',                   'CASE /* DECODE → */ (',  'DECODE→CASE'),
        (r'\bROWNUM\b',                      '/* ROWNUM (PostgreSQL: LIMIT 사용) */',  'ROWNUM→LIMIT'),
        (r'"([^"]+)"',                       r'"\1"',                 '큰따옴표 유지'),
        (r'\|\|',                            '||',                    '|| 연결 OK'),
        (r'\bTO_DATE\s*\(',                  'TO_DATE(',              'TO_DATE OK'),
        (r'\bTO_CHAR\s*\(',                  'TO_CHAR(',              'TO_CHAR OK'),
        (r'\bTRUNC\s*\(',                    'TRUNC(',                'TRUNC OK'),
        (r'\bINSTR\s*\(',                    'POSITION(',             'INSTR→POSITION'),
        (r'\bSUBSTR\s*\(',                   'SUBSTRING(',            'SUBSTR→SUBSTRING'),
        (r'\bCONNECT BY\b',                 '-- CONNECT BY (재귀 CTE로 변환 필요)',  'CONNECT BY 안내'),
        (r'\bSTART WITH\b',                  '-- START WITH (재귀 CTE로 변환 필요)',  'START WITH 안내'),
    ],
}



def _date_format_mysql_to_mssql(fmt: str) -> str:
    """MySQL DATE_FORMAT 포맷 문자열 → MSSQL FORMAT 포맷 문자열 변환"""
    mapping = {
        '%Y': 'yyyy', '%y': 'yy',
        '%m': 'MM',   '%c': 'M',
        '%d': 'dd',   '%e': 'd',
        '%H': 'HH',   '%h': 'hh',
        '%i': 'mm',   '%s': 'ss',
        '%p': 'tt',   '%M': 'MMMM',
        '%b': 'MMM',  '%W': 'dddd',
        '%a': 'ddd',  '%f': 'ffffff',
    }
    result = fmt
    for mysql_fmt, mssql_fmt in mapping.items():
        result = result.replace(mysql_fmt, mssql_fmt)
    return result



def _wrap_cte(sql_text, re_mod):
    """
    SELECT col, AGG(x), WIN_FUNC(AGG(x)) OVER (ORDER BY ...) ... GROUP BY ...
    -> WITH __agg AS (SELECT col, AGG(x) ... GROUP BY ...) SELECT *, WIN_FUNC(alias) OVER (ORDER BY alias)
    MSSQL에서 GROUP BY + 윈도우함수(집계식) 조합 불가 -> CTE 분리 필요
    """
    import re as _r2

    clean = _r2.sub(r"--[^\n]*", "", sql_text)

    sel_m  = _r2.search(r"(?i)\bSELECT\b(.*?)\bFROM\b", clean, _r2.DOTALL)
    from_m = _r2.search(r"(?i)\bFROM\b(.*?)(?=\bWHERE\b|\bGROUP\b|\bHAVING\b|\bORDER\b|;|$)", clean, _r2.DOTALL)
    grp_m  = _r2.search(r"(?i)\bGROUP\s+BY\b(.*?)(?=\bHAVING\b|\bORDER\b|;|$)", clean, _r2.DOTALL)
    hav_m  = _r2.search(r"(?i)\bHAVING\b(.*?)(?=\bORDER\b|;|$)", clean, _r2.DOTALL)

    def _outer_order_by(text):
        d = 0; i = 0
        while i < len(text):
            if text[i] == "(": d += 1
            elif text[i] == ")": d -= 1
            elif d == 0:
                m = _r2.match(r"(?i)ORDER\s+BY", text[i:])
                if m:
                    return text[i + m.end():].strip().rstrip(";").strip()
            i += 1
        return ""

    ord_str_raw = _outer_order_by(clean)

    if not (sel_m and from_m and grp_m):
        return sql_text, False

    def _split_cols(s):
        cols = []; d = 0; cur = ""; in_q = False; qc = ""
        for ch in s:
            if in_q:
                cur += ch
                if ch == qc: in_q = False
            elif ch in ("'", '"'):
                in_q = True; qc = ch; cur += ch
            elif ch == "(": d += 1; cur += ch
            elif ch == ")": d -= 1; cur += ch
            elif ch == "," and d == 0:
                if cur.strip(): cols.append(cur.strip())
                cur = ""
            else: cur += ch
        if cur.strip(): cols.append(cur.strip())
        return cols

    WIN_PAT = r"(?i)\b(LAG|LEAD|FIRST_VALUE|LAST_VALUE)\s*\("
    all_cols = _split_cols(sel_m.group(1))
    agg_cols = [c for c in all_cols if not _r2.search(WIN_PAT, c)]
    win_cols = [c for c in all_cols if     _r2.search(WIN_PAT, c)]

    if not win_cols or not agg_cols:
        return sql_text, False

    alias_map = {}
    for col in agg_cols:
        m = _r2.search(r"(?i)\bAS\s+([\w가-힣]+)\s*$", col.strip())
        if m:
            expr  = col[:col.lower().rfind(" as ")].strip()
            alias = m.group(1).strip()
            alias_map[expr] = alias

    def _repl(text):
        for expr, alias in sorted(alias_map.items(), key=lambda x: len(x[0]), reverse=True):
            text = text.replace(expr, alias)
        return text

    new_win   = [_repl(wc) for wc in win_cols]
    ord_clean = _repl(ord_str_raw)
    ord_part  = ("\nORDER BY " + ord_clean) if ord_clean else ""

    inner_cols = ",\n        ".join(agg_cols)
    from_str   = from_m.group(1).strip()
    grp_raw    = grp_m.group(1).strip()
    hav_str    = ("\n    HAVING " + _repl(hav_m.group(1).strip())) if hav_m else ""

    outer_base = []
    for col in agg_cols:
        m = _r2.search(r"(?i)\bAS\s+([\w가-힣]+)\s*$", col.strip())
        if m: outer_base.append(m.group(1).strip())
    outer_sel = ", ".join(outer_base) if outer_base else "*"
    outer_win = ",\n    ".join(new_win)

    comments = _r2.findall(r"--[^\n]*", sql_text)
    prefix   = "\n".join(comments) + "\n" if comments else ""

    new_sql = (
        prefix +
        "WITH __agg AS (\n"
        "    SELECT\n        " + inner_cols + "\n"
        "    FROM " + from_str + "\n"
        "    GROUP BY " + grp_raw + hav_str + "\n"
        ")\n"
        "SELECT " + outer_sel + ",\n    " + outer_win + "\n"
        "FROM __agg" + ord_part + ";"
    )
    return new_sql, True

def convert_sql(sql: str, src_db: str, tgt_db: str) -> dict:
    """
    SQL 문자열을 변환하고 변경 내역 반환
    returns: { "converted": str, "changes": list[str], "warnings": list[str] }
    """
    key = f"{src_db}→{tgt_db}"
    rules = RULES.get(key, [])
    if not rules:
        return {"converted": sql, "changes": [], "warnings": [f"{key} 변환 규칙이 없습니다"]}

    result   = sql
    changes  = []
    warnings = []

    # ── MSSQL→MySQL 사전 처리: TOP/STRING_AGG/N-prefix ──────────────────────
    if src_db in ("mssql","azure") and tgt_db in ("mysql","mariadb","aurora","tidb"):
        import re as _rm

        # 1) SELECT TOP n → SELECT ... LIMIT n (CTE 인식)
        def _top_to_limit(sql_text):
            # WITH CTE가 있으면 CTE 이후 메인 SELECT의 TOP 처리
            _cte = _rm.search(r"(?i)^\s*WITH\s+\w", sql_text, _rm.MULTILINE)
            if _cte:
                # 괄호 깊이로 CTE 블록 끝 탐색
                p = _cte.start(); dd = 0; in_cte = False
                for ii, cc in enumerate(sql_text[p:], p):
                    if cc == '(': dd += 1; in_cte = True
                    elif cc == ')': dd -= 1
                    elif in_cte and dd == 0:
                        # CTE 이후 메인 SELECT에서 TOP 찾기
                        rest = sql_text[ii:]
                        m = _rm.search(r"(?i)\bSELECT\s+TOP\s+(\d+)\b", rest)
                        if m:
                            n = m.group(1)
                            # TOP n 제거
                            no_top = sql_text[:ii] + _rm.sub(
                                r"(?i)\bSELECT\s+TOP\s+\d+\b", "SELECT", rest, count=1)
                            # 세미콜론 앞 또는 끝에 LIMIT 추가
                            no_top = _rm.sub(r"(\s*;?\s*)$", "\nLIMIT " + n + ";", no_top.rstrip().rstrip(";"))
                            return no_top, "TOP " + n + "→LIMIT " + n + " (CTE 이후 메인 SELECT)"
                        break
            # 일반 SELECT TOP n
            m = _rm.search(r"(?i)\bSELECT\s+TOP\s+(\d+)\b", sql_text)
            if m:
                n = m.group(1)
                no_top = _rm.sub(r"(?i)\bSELECT\s+TOP\s+\d+\b", "SELECT", sql_text, count=1)
                no_top = _rm.sub(r"(\s*;?\s*)$", "\nLIMIT " + n + ";", no_top.rstrip().rstrip(";"))
                return no_top, "TOP " + n + "→LIMIT " + n
            return sql_text, None

        new_r, msg = _top_to_limit(result)
        if msg:
            changes.append(msg)
            result = new_r
            # TOP→LIMIT 변환 후 기존 LIMIT 잔재 제거 (중복 방지)
            # 이미 추가된 LIMIT 뒤에 또 LIMIT이 있으면 제거
            import re as _rdup
            result = _rdup.sub(
                r"(LIMIT\s+\d+(?:\s+OFFSET\s+\d+)?)([\s\n]*LIMIT\s+\d+(?:\s+OFFSET\s+\d+)?)+",
                r"\1", result, flags=_rdup.IGNORECASE)

        # 2) STRING_AGG(expr, sep) WITHIN GROUP (ORDER BY ...) → GROUP_CONCAT
        def _str_agg_to_gc(sql_text):
            out = []; i = 0; ok = False
            while i < len(sql_text):
                m = _rm.match(r"(?i)STRING_AGG\s*\(", sql_text[i:])
                if not m: out.append(sql_text[i]); i += 1; continue
                # expr, sep 파싱 — 따옴표 안의 쉼표는 무시
                s = i + m.end(); args = []; d = 1; j = s; cur = ""; in_q = False; q_ch = ""
                while j < len(sql_text) and d > 0:
                    c2 = sql_text[j]
                    if in_q:
                        cur += c2
                        if c2 == q_ch: in_q = False
                    elif c2 in ("'", '"'):
                        in_q = True; q_ch = c2; cur += c2
                    elif c2 == "(": d += 1; cur += c2
                    elif c2 == ")":
                        d -= 1
                        if d == 0: args.append(cur.strip()); break
                        else: cur += c2
                    elif c2 == "," and d == 1: args.append(cur.strip()); cur = ""
                    else: cur += c2
                    j += 1
                end_pos = j + 1
                expr = args[0] if args else ""
                sep  = args[1] if len(args) > 1 else "','"
                # WITHIN GROUP (ORDER BY ...) 확인
                rest = sql_text[end_pos:]
                wg = _rm.match(r"\s*WITHIN\s+GROUP\s*\(\s*ORDER\s+BY\s+([^)]+)\)", rest, _rm.IGNORECASE)
                if wg:
                    order_part = wg.group(1).strip()
                    end_pos += wg.end()
                    cv = "GROUP_CONCAT(" + expr + " ORDER BY " + order_part + " SEPARATOR " + sep + ")"
                else:
                    cv = "GROUP_CONCAT(" + expr + " SEPARATOR " + sep + ")"
                out.append(cv); i = end_pos; ok = True
            return "".join(out), ok

        new_r, gc_ok = _str_agg_to_gc(result)
        if gc_ok:
            changes.append("STRING_AGG WITHIN GROUP→GROUP_CONCAT")
            result = new_r

        # 3) N'문자열' → '문자열' (NVARCHAR 리터럴 N 접두어 제거)
        new_r = _rm.sub(r"\bN(')", r"\1", result)
        if new_r != result:
            changes.append("N'...' 접두어 제거")
            result = new_r

        # 4) OFFSET m ROWS FETCH NEXT n ROWS ONLY → LIMIT n OFFSET m
        _of = _rm.search(
            r"(?i)\bOFFSET\s+(\d+)\s+ROWS\s+FETCH\s+NEXT\s+(\d+)\s+ROWS\s+ONLY\b",
            result)
        if _of:
            off, n2 = _of.group(1), _of.group(2)
            result = result[:_of.start()].rstrip() + "\nLIMIT " + n2 + " OFFSET " + off
            changes.append("OFFSET FETCH→LIMIT OFFSET")

    # ── FORMAT→DATE_FORMAT 사전 처리 (MSSQL→MySQL: 포맷 문자열 역변환) ──
    if src_db in ("mssql","azure") and tgt_db in ("mysql","mariadb","aurora","tidb"):
        def _fmt_mssql_to_mysql(m):
            expr = m.group(1)
            fmt  = m.group(2)
            # 플레이스홀더 방식 — 긴 패턴 먼저 치환해서 충돌 방지
            fmt_pairs = [
                ('yyyy','%Y'), ('yy','%y'),
                ('MMMM','%M'), ('MMM','%b'), ('MM','%m'), ('M','%c'),
                ('dddd','%W'), ('ddd','%a'), ('dd','%d'), ('d','%e'),
                ('HH','%H'),   ('hh','%h'),
                ('mm','%i'),   ('ss','%s'),
                ('tt','%p'),   ('ffffff','%f'),
            ]
            ph_map = {}
            result_fmt = fmt
            for i, (k, v) in enumerate(fmt_pairs):
                ph = f'\x00{i}\x00'
                new = result_fmt.replace(k, ph)
                if new != result_fmt:
                    ph_map[ph] = v
                    result_fmt = new
            for ph, v in ph_map.items():
                result_fmt = result_fmt.replace(ph, v)
            return f"DATE_FORMAT({expr.strip()}, '{result_fmt}')"
        new_r = re.sub(
            r"\bFORMAT\s*\(([^,]+),\s*'([^']*)'\s*\)",
            _fmt_mssql_to_mysql, result, flags=re.IGNORECASE
        )
        if new_r != result:
            changes.append("FORMAT→DATE_FORMAT (포맷 문자열 역변환 포함)")
            result = new_r

    # ── DATEADD 사전처리 (괄호 깊이 추적) ────────────────────────────────────
    if src_db in ("mssql","azure") and tgt_db in ("mysql","mariadb","aurora","tidb"):
        import re as _rda
        _unit_da = {
            "year":"YEAR","yy":"YEAR","yyyy":"YEAR",
            "month":"MONTH","mm":"MONTH","m":"MONTH",
            "day":"DAY","dd":"DAY","d":"DAY",
            "hour":"HOUR","hh":"HOUR",
            "minute":"MINUTE","mi":"MINUTE","n":"MINUTE",
            "second":"SECOND","ss":"SECOND","s":"SECOND",
            "week":"WEEK","wk":"WEEK","ww":"WEEK",
        }
        def _conv_dateadd(s):
            out=[]; i=0; changed=False
            while i < len(s):
                m = _rda.match(r'(?i)DATEADD\s*\(', s[i:])
                if not m:
                    out.append(s[i]); i+=1; continue
                st = i + m.end()
                # 3개 인수 파싱 (괄호 깊이 추적)
                args=[]; d=1; cur=''; j=st
                while j < len(s) and d > 0:
                    c = s[j]
                    if c=='(':   d+=1;   cur+=c
                    elif c==')':
                        d-=1
                        if d==0: args.append(cur.strip()); break
                        else:    cur+=c
                    elif c==',' and d==1:
                        args.append(cur.strip()); cur=''
                    else: cur+=c
                    j+=1
                if len(args)==3:
                    unit = args[0].strip().strip("'\"").lower()
                    n    = args[1].strip()
                    dt   = args[2].strip()
                    mu   = _unit_da.get(unit, unit.upper())
                    out.append(f"DATE_ADD({dt}, INTERVAL {n} {mu})")
                    i = j+1; changed=True
                else:
                    out.append(s[i]); i+=1
            return ''.join(out), changed
        new_r, changed = _conv_dateadd(result)
        if changed:
            result = new_r
            changes.append("DATEADD→DATE_ADD INTERVAL (사전처리)")

    # ── DATEDIFF 양방향 변환 (괄호 깊이 추적 파서) ────────────────────────
    def _parse_df_args(s):
        """DATEDIFF 인자 목록 반환 [(start,end,args), ...]"""
        import re as _r; out = []; i = 0
        while i < len(s):
            mm = _r.match(r'(?i)DATEDIFF\s*\(', s[i:])
            if mm:
                st = i+mm.end(); args=[]; d=1; cur=''; j=st
                while j<len(s) and d>0:
                    c=s[j]
                    if c=='(':   d+=1;   cur+=c
                    elif c==')':
                        d-=1
                        if d==0:    args.append(cur.strip()); break
                        else:       cur+=c
                    elif c==','and d==1: args.append(cur.strip());cur=''
                    else:        cur+=c
                    j+=1
                out.append((i,j+1,args)); i=j+1
            else: i+=1
        return out

    if src_db in ("mssql","azure") and tgt_db in ("mysql","mariadb","aurora","tidb"):
        hits = _parse_df_args(result)
        if hits:
            _umap = {
                "year":"YEAR","yy":"YEAR","yyyy":"YEAR",
                "month":"MONTH","mm":"MONTH","m":"MONTH",
                "day":"DAY","dd":"DAY","d":"DAY",
                "hour":"HOUR","hh":"HOUR",
                "minute":"MINUTE","mi":"MINUTE","n":"MINUTE",
                "second":"SECOND","ss":"SECOND","s":"SECOND",
                "week":"WEEK","wk":"WEEK","ww":"WEEK",
                "quarter":"QUARTER","qq":"QUARTER","q":"QUARTER",
            }
            parts=[]; prev=0
            for (s2,e2,args) in hits:
                parts.append(result[prev:s2])
                if len(args)==3:
                    unit = args[0].strip().strip("'\"").lower()
                    a, b = args[1].strip(), args[2].strip()
                    mu = _umap.get(unit, unit.upper())
                    if mu == "DAY":
                        parts.append(f"DATEDIFF({b}, {a})")
                        changes.append(f"DATEDIFF(DAY)→DATEDIFF(b,a)")
                    else:
                        parts.append(f"TIMESTAMPDIFF({mu}, {a}, {b})")
                        changes.append(f"DATEDIFF({unit})→TIMESTAMPDIFF({mu})")
                        if mu == "YEAR":
                            warnings.append("⚠ TIMESTAMPDIFF(YEAR) 사용 — 생일 기준 정확한 연 차이")
                else:
                    parts.append(f"DATEDIFF({', '.join(args)})")
                prev=e2
            parts.append(result[prev:]); result=''.join(parts)

    elif src_db in ("mysql","mariadb","aurora","tidb") and tgt_db in ("mssql","azure"):
        hits = _parse_df_args(result)
        if hits:
            parts=[]; prev=0
            for (s2,e2,args) in hits:
                parts.append(result[prev:s2])
                if len(args)==2: parts.append(f"DATEDIFF(day, {args[1]}, {args[0]})"); changes.append("DATEDIFF(a,b)→DATEDIFF(day,b,a)"); warnings.append("⚠ DATEDIFF 인자 순서 변환 확인 필요")
                else:            parts.append(f"DATEDIFF({', '.join(args)})")
                prev=e2
            parts.append(result[prev:]); result=''.join(parts)

    # ── GROUP_CONCAT / LIMIT / HAVING alias 사전처리 (MySQL->MSSQL) ─────────
    if src_db in ("mysql","mariadb","aurora","tidb") and tgt_db in ("mssql","azure"):
        import re as _rg
        def _gc(sql):
            out=[]; i=0; ok=False
            while i<len(sql):
                m=_rg.match(r"(?i)GROUP_CONCAT\s*\(",sql[i:])
                if not m: out.append(sql[i]); i+=1; continue
                s=i+m.end(); d=1; j=s; inn=""
                while j<len(sql) and d>0:
                    c=sql[j]
                    if c=="(": d+=1
                    elif c==")":
                        d-=1
                        if d==0: break
                    inn+=c; j+=1
                inn=inn.strip()
                has_d=bool(_rg.match(r"(?i)\s*DISTINCT\s+",inn))
                if has_d:
                    inn=_rg.sub(r"(?i)^\s*DISTINCT\s+","",inn)
                    warnings.append("STRING_AGG: DISTINCT 제거됨 (MSSQL 미지원)")
                sep=","
                sm=_rg.search(r"(?i)\bSEPARATOR\s+(?P<s>'[^']*')\s*$",inn)
                if sm: sep=sm.group("s"); inn=inn[:sm.start()].rstrip()
                om=_rg.search(r"(?i)\bORDER\s+BY\s+(.+)$",inn)
                oc=""
                if om: oc=om.group(1).strip(); inn=inn[:om.start()].rstrip()
                ex=inn.strip()
                if oc:
                    cv="STRING_AGG("+ex+", "+sep+") WITHIN GROUP (ORDER BY "+oc+")"
                else:
                    cv="STRING_AGG("+ex+", "+sep+")"
                out.append(cv); i=j+1; ok=True
            return "".join(out),ok
        nr,gok=_gc(result)
        if gok:
            changes.append("GROUP_CONCAT->STRING_AGG WITHIN GROUP")
            result=nr

        _lo=_rg.search(r"(?i)\bLIMIT\s+(\d+)\s+OFFSET\s+(\d+)\s*;?\s*$",result,_rg.MULTILINE)
        if _lo:
            n2,o2=_lo.group(1),_lo.group(2)
            result=result[:_lo.start()].rstrip().rstrip(";")+("\nOFFSET "+o2+" ROWS FETCH NEXT "+n2+" ROWS ONLY;")
            changes.append("LIMIT OFFSET->OFFSET FETCH")
        else:
            _lm=_rg.search(r"(?i)\bLIMIT\s+(\d+)\s*;?\s*$",result,_rg.MULTILINE)
            if _lm:
                n2=_lm.group(1)
                nl=result[:_lm.start()].rstrip().rstrip(";")
                nl=_rg.sub(r"(?i)--[^\n]*LIMIT[^\n]*","",nl)
                # CTE(WITH절)가 있으면 WITH 블록 이후의 첫 SELECT에 TOP 삽입
                # WITH ... ) 다음에 오는 SELECT를 찾기
                _cte=_rg.search(r"(?i)^\s*WITH\s+\w",nl,_rg.MULTILINE)
                if _cte:
                    # CTE 블록 끝 ( 마지막 ) 이후 SELECT ) 찾기
                    # CTE 괄호 깊이 추적으로 메인 SELECT 위치 탐색
                    _p=_cte.start(); _dd=0; _in_cte=False
                    for _ii,_cc in enumerate(nl[_p:],_p):
                        if _cc=='(': _dd+=1; _in_cte=True
                        elif _cc==')': _dd-=1
                        elif _in_cte and _dd==0:
                            # CTE 블록 종료 후 SELECT 찾기
                            _rest=nl[_ii:]
                            _ms=_rg.search(r"(?i)\bSELECT\b",_rest)
                            if _ms:
                                _pos=_ii+_ms.start()
                                ns=nl[:_pos]+"SELECT TOP "+n2+nl[_pos+6:]
                                changes.append("LIMIT "+n2+"->SELECT TOP "+n2+" (CTE 이후 메인 SELECT)")
                                result=ns+";"; break
                    else:
                        ns=_rg.sub(r"(?i)\bSELECT\b","SELECT TOP "+n2,nl,count=1)
                        if ns!=nl: changes.append("LIMIT "+n2+"->SELECT TOP "+n2); result=ns+";"
                else:
                    ns=_rg.sub(r"(?i)\bSELECT\b","SELECT TOP "+n2,nl,count=1)
                    if ns!=nl: changes.append("LIMIT "+n2+"->SELECT TOP "+n2); result=ns+";"

        # HAVING 별칭→표현식: 문자열 리터럴('구분') 제외, 실제 컬럼 별칭만 처리
        # 메인 쿼리(CTE 제외)의 SELECT 절에서 alias 추출
        _cte2=_rg.search(r"(?i)^\s*WITH\s+\w",result,_rg.MULTILINE)
        _search_start=0
        if _cte2:
            # CTE 이후 메인 SELECT 위치
            _p2=_cte2.start(); _dd2=0; _in2=False
            for _ii2,_cc2 in enumerate(result[_p2:],_p2):
                if _cc2=='(': _dd2+=1; _in2=True
                elif _cc2==')': _dd2-=1
                elif _in2 and _dd2==0:
                    _ms2=_rg.search(r"(?i)\bSELECT\b",result[_ii2:])
                    if _ms2: _search_start=_ii2+_ms2.start(); break
        _sm=_rg.search(r"(?i)\bSELECT\b(.*?)\bFROM\b",result[_search_start:],_rg.DOTALL)
        if _sm:
            _am={}; _d2=0; _cu=""; _cl=[]
            for _c2 in _sm.group(1):
                if _c2=="(": _d2+=1
                elif _c2==")": _d2-=1
                elif _c2=="," and _d2==0: _cl.append(_cu.strip()); _cu=""; continue
                _cu+=_c2
            if _cu.strip(): _cl.append(_cu.strip())
            for _co in _cl:
                _a=_rg.search(r"(?i)\bAS\s+([\w가-힣]+)\s*$",_co.strip())
                if _a:
                    _al=_a.group(1).strip()
                    _ex=_co[:_co.lower().rfind(" as ")].strip()
                    # 표현식이 단순 문자열 리터럴이면 alias 등록 제외
                    if not _rg.match(r"^'[^']*'$",_ex.strip()) and not _rg.match(r'^"[^"]*"$',_ex.strip()):
                        _am[_al]=_ex
            _hm=_rg.search(r"(?i)\bHAVING\b(.+?)(?=\bORDER\b|\bLIMIT\b|\bOFFSET\b|;|$)",result,_rg.DOTALL)
            if _hm and _am:
                _hv=_hm.group(1); _nh=_hv
                for _al,_ex in _am.items():
                    _pt=r"(?<![가-힣a-zA-Z_(])"+_rg.escape(_al)+r"(?![가-힣a-zA-Z_0-9(])"
                    if _rg.search(_pt,_hv):
                        _nh=_rg.sub(_pt,"("+_ex+")",_nh)
                        changes.append("HAVING \""+_al+"\"->표현식 직접 사용")
                if _nh!=_hv:
                    result=result[:_hm.start(1)]+_nh+result[_hm.end(1):]

    for pattern, replacement, desc in rules:
        flags = re.IGNORECASE | re.MULTILINE
        try:
            new_result, count = re.subn(pattern, replacement, result, flags=flags)
            if count > 0:
                result = new_result
                changes.append(f"{desc} ({count}건)")
                if "안내" in desc or "변환 필요" in desc:
                    warnings.append(desc)
        except re.error:
            pass


    # ── GROUP BY + 윈도우함수(집계식) → CTE 자동 래핑 (MSSQL 호환) ──
    if src_db in ("mysql","mariadb","aurora","tidb") and tgt_db in ("mssql","azure"):
        import re as _rc
        _has_grp = bool(_rc.search(r"(?i)GROUP\s+BY", result))
        _has_win = bool(_rc.search(
            r"(?i)(LAG|LEAD|FIRST_VALUE|LAST_VALUE)\s*\(\s*(SUM|COUNT|AVG|MAX|MIN)\s*\(",
            result))
        if _has_grp and _has_win:
            try:
                result, _cte_ok = _wrap_cte(result, _rc)
                if _cte_ok:
                    changes.append("GROUP BY + 윈도우함수 → CTE 자동 래핑")
                    warnings.append("CTE 자동 래핑 적용 - 결과 검토 권장")
            except Exception:
                warnings.append("CTE 자동 래핑 실패 - 수동 변환 필요")

    return {"converted": result, "changes": changes, "warnings": warnings}


def convert_file_content(content: str, src_db: str, tgt_db: str, filename: str) -> dict:
    """파일 단위 변환"""
    result = convert_sql(content, src_db, tgt_db)
    result["filename"] = filename
    result["original_size"] = len(content)
    result["converted_size"] = len(result["converted"])
    return result


# ── API 엔드포인트 ─────────────────────────────────────────

@router.post("/convert")
def convert_query(body: dict):
    """
    단일 SQL 텍스트 변환
    body: { sql, src_db, tgt_db }
    """
    sql    = body.get("sql", "")
    src_db = body.get("src_db", "mysql")
    tgt_db = body.get("tgt_db", "mssql")

    if not sql.strip():
        raise HTTPException(400, "SQL이 비어있습니다")

    return convert_sql(sql, src_db, tgt_db)


@router.post("/convert-files")
def convert_files(body: dict):
    """
    여러 파일 내용을 일괄 변환
    body: { files: [{name, content}], src_db, tgt_db }
    반환: 변환된 파일 목록
    """
    files  = body.get("files", [])
    src_db = body.get("src_db", "mysql")
    tgt_db = body.get("tgt_db", "mssql")

    if not files:
        raise HTTPException(400, "파일이 없습니다")

    results = []
    for f in files:
        r = convert_file_content(f.get("content",""), src_db, tgt_db, f.get("name","unnamed.sql"))
        results.append(r)

    total_changes = sum(len(r["changes"]) for r in results)
    return {
        "files":         results,
        "total_files":   len(results),
        "total_changes": total_changes,
        "src_db":        src_db,
        "tgt_db":        tgt_db,
    }


@router.post("/convert-files-ai")
def convert_files_ai(body: dict):
    """
    여러 파일을 Claude AI로 일괄 변환
    API 키 없으면 규칙 기반으로 폴백
    body: { files: [{name, content}], src_db, tgt_db, engine }
    """
    import json as _j2, urllib.request as _ur2, os as _os2, time as _tm

    files  = body.get("files", [])
    src_db = body.get("src_db", "mssql")
    tgt_db = body.get("tgt_db", "mysql")
    engine = body.get("engine", "auto")

    if not files:
        raise HTTPException(400, "파일이 없습니다")

    # API 키 확인
    try:
        from app.api.routes.settings import _cfg as _get_cfg2
        api_key2 = _get_cfg2().get("anthropic_api_key", "").strip()
    except Exception:
        api_key2 = ""
    api_key2 = api_key2 or _os2.environ.get("ANTHROPIC_API_KEY", "").strip()

    # API 키 없거나 규칙 모드이면 기존 규칙 변환
    if not api_key2 or engine == "rules":
        results = []
        for f in files:
            r = convert_file_content(f.get("content",""), src_db, tgt_db, f.get("name","unnamed.sql"))
            results.append(r)
        total_changes = sum(len(r["changes"]) for r in results)
        return {"files": results, "total_files": len(results), "total_changes": total_changes, "method": "rules"}

    # Claude AI로 파일별 변환
    src_name = {"mssql":"SQL Server","mysql":"MySQL","mariadb":"MariaDB",
                "postgresql":"PostgreSQL","oracle":"Oracle"}.get(src_db, src_db)
    tgt_name = {"mssql":"SQL Server","mysql":"MySQL","mariadb":"MariaDB",
                "postgresql":"PostgreSQL","oracle":"Oracle"}.get(tgt_db, tgt_db)

    results = []
    total_in = 0; total_out = 0

    for f in files:
        fname   = f.get("name", "unnamed.sql")
        sql_txt = f.get("content", "").strip()

        if not sql_txt:
            results.append({"filename": fname, "converted": "", "changes": [], "warnings": []})
            continue

        NL = "\n"
        prompt = (
            f"당신은 {src_name} → {tgt_name} SQL 변환 전문가입니다.{NL}"
            f"아래 {src_name} SQL을 {tgt_name}에서 실행 가능하도록 정확히 변환하세요.{NL}{NL}"
            f"변환 규칙:{NL}"
            f"- 모든 함수/문법을 {tgt_name} 표준으로 변환{NL}"
            f"- DATEADD → DATE_ADD INTERVAL, EOMONTH → LAST_DAY, DATENAME → DAYNAME/MONTHNAME{NL}"
            f"- DATEDIFF(YEAR,a,b) → TIMESTAMPDIFF(YEAR,a,b), DATEDIFF(DAY,a,b) → DATEDIFF(b,a){NL}"
            f"- FULL OUTER JOIN → LEFT JOIN UNION ALL RIGHT JOIN 구조로 완전 변환{NL}"
            f"- PIVOT/UNPIVOT → CASE WHEN 구조로 완전 변환{NL}"
            f"- [dbo].[테이블] → `테이블`, ISNULL → IFNULL, TOP N → LIMIT N{NL}"
            f"- 문자열 연결 + → CONCAT(), LEN → LENGTH, CHARINDEX → LOCATE{NL}"
            f"- 한글 별칭(AS 절) 그대로 유지{NL}"
            f"- 설명 없이 변환된 SQL만 출력 (JSON 형식){NL}{NL}"
            f"파일명: {fname}{NL}"
            f"원본 SQL ({src_name}):{NL}{sql_txt[:3000]}{NL}{NL}"
            '{"converted":"변환된SQL","changes":["변경1","변경2"],"warnings":["주의"]}'
        )

        try:
            payload = _j2.dumps({
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4000,
                "messages": [{"role": "user", "content": prompt}]
            }).encode()
            req = _ur2.Request(
                "https://api.anthropic.com/v1/messages",
                data=payload,
                headers={"Content-Type":"application/json",
                         "x-api-key":api_key2,
                         "anthropic-version":"2023-06-01"}
            )
            with _ur2.urlopen(req, timeout=60) as resp:
                data_r = _j2.loads(resp.read())

            text_r = "".join(b.get("text","") for b in data_r.get("content",[]) if b.get("type")=="text")
            text_r = text_r.strip()
            if "```" in text_r:
                import re as _re3
                text_r = _re3.sub(r"^```[a-z]*\n?", "", text_r, flags=_re3.IGNORECASE)
                text_r = _re3.sub(r"\n?```$", "", text_r).strip()

            parsed_r = _j2.loads(text_r)
            # AI 변환 결과 후처리 (섹션 구분 주석 제거)
            if "converted" in parsed_r:
                parsed_r["converted"] = _clean_converted_sql(parsed_r["converted"])
            parsed_r["filename"] = fname
            parsed_r["method"]   = "claude-ai"
            results.append(parsed_r)

            # 사용량 누적
            usage_r = data_r.get("usage", {})
            total_in  += usage_r.get("input_tokens", 0)
            total_out += usage_r.get("output_tokens", 0)

        except Exception as e_r:
            # 개별 파일 실패 시 규칙 기반 폴백
            fallback = convert_file_content(sql_txt, src_db, tgt_db, fname)
            fallback["method"] = "rules_fallback"
            fallback["ai_error"] = str(e_r)[:80]
            results.append(fallback)

    # 전체 사용량 기록
    if total_in > 0:
        try:
            from app.core.store import Store as _St3
            _us3 = _St3("claude_usage")
            _prev3 = _us3.get("total") or {"calls":0,"input_tokens":0,"output_tokens":0,"objects":[]}
            _prev3["calls"]         += len(files)
            _prev3["input_tokens"]  += total_in
            _prev3["output_tokens"] += total_out
            _prev3["objects"].append({
                "name": f"파일변환 {len(files)}개 ({src_db}→{tgt_db})",
                "type": "SQL_CONVERT_FILES",
                "in":   total_in,
                "out":  total_out,
                "ts":   __import__("datetime").datetime.now().isoformat()
            })
            _prev3["objects"] = _prev3["objects"][-100:]
            _us3.set("total", _prev3)
        except Exception:
            pass

    total_changes = sum(len(r.get("changes",[])) for r in results)
    return {"files": results, "total_files": len(results),
            "total_changes": total_changes, "method": "claude-ai"}

@router.post("/convert-files/download")
def download_converted(body: dict):
    """
    변환된 파일들을 ZIP으로 다운로드
    """
    files  = body.get("files", [])
    src_db = body.get("src_db", "mysql")
    tgt_db = body.get("tgt_db", "mssql")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            r = convert_file_content(f.get("content",""), src_db, tgt_db, f.get("name",""))
            # 파일명에 _converted 추가
            name = f.get("name","unnamed.sql")
            base = name.rsplit(".",1)
            new_name = f"{base[0]}_converted.{base[1]}" if len(base)==2 else name+"_converted"
            zf.writestr(new_name, r["converted"])

        # 변환 요약 리포트
        report_lines = [
            f"DataBridge Studio — SQL 변환 리포트",
            f"변환일시: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"소스 DB: {src_db}  →  타겟 DB: {tgt_db}",
            f"변환 파일 수: {len(files)}",
            "=" * 50,
        ]
        for f in files:
            r = convert_file_content(f.get("content",""), src_db, tgt_db, f.get("name",""))
            report_lines.append(f"\n[ {f.get('name','')} ]")
            report_lines.extend([f"  ✓ {c}" for c in r["changes"]])
            if r["warnings"]:
                report_lines.extend([f"  ⚠ {w}" for w in r["warnings"]])
        zf.writestr("_변환리포트.txt", "\n".join(report_lines))

    buf.seek(0)
    filename = f"converted_{src_db}_to_{tgt_db}_{time.strftime('%Y%m%d_%H%M%S')}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/rules")
def get_rules(src_db: str = "mysql", tgt_db: str = "mssql"):
    """변환 규칙 목록 조회"""
    key = f"{src_db}→{tgt_db}"
    rules = RULES.get(key, [])
    return {
        "key": key,
        "count": len(rules),
        "rules": [{"pattern": p, "replacement": r, "desc": d} for p, r, d in rules]
    }


@router.get("/supported")
def get_supported():
    """지원하는 변환 조합 목록"""
    return [{"key": k, "src": k.split("→")[0], "tgt": k.split("→")[1], "rules": len(v)}
            for k, v in RULES.items()]



def _clean_converted_sql(sql: str) -> str:
    """
    AI 변환 결과 후처리:
    1. 쿼리 끝에 붙은 섹션 구분 주석 제거
       (-- ===... 또는 -- [N] ... 형태)
    2. 끝 공백/빈줄 정리
    """
    import re as _rc
    lines = sql.split('\n')
    result = []
    sql_started = False

    for ln in lines:
        stripped = ln.strip()
        # SQL 키워드가 나오면 SQL 시작으로 간주
        if _rc.match(
            r'^(SELECT|WITH|INSERT|UPDATE|DELETE|CREATE|DECLARE|SET|CALL|EXEC)',
            stripped, _rc.IGNORECASE
        ):
            sql_started = True

        # SQL 시작 이후 섹션 구분자 → 제거하고 중단
        if sql_started:
            # -- =========== (10개 이상 =)
            if _rc.match(r'^--\s*={10,}', stripped):
                break
            # -- [숫자] 섹션 제목
            if _rc.match(r'^--\s*\[\d+\]', stripped):
                break

        result.append(ln)

    # 끝 빈줄 제거
    while result and not result[-1].strip():
        result.pop()

    return '\n'.join(result)


def _extract_groupby_cols(sql: str) -> str:
    """
    SQL에서 최외각 GROUP BY 절의 컬럼 추출 (괄호 포함).
    예: GROUP BY YEAR(sent_dt), status_cd → 'YEAR(sent_dt), status_cd'
    """
    import re as _rg
    s = sql.strip()
    # depth=0에서 GROUP BY 키워드 위치 찾기
    depth = 0; i = 0; gb_start = -1
    while i < len(s):
        c = s[i]
        if c in ("'", '"'):
            q = c; i += 1
            while i < len(s) and s[i] != q:
                if s[i] == '\\': i += 1
                i += 1
        elif c == '(': depth += 1
        elif c == ')': depth -= 1
        elif depth == 0:
            # GROUP BY 키워드 검사
            chunk = s[i:i+8].upper()
            if chunk.startswith('GROUP') and _rg.match(r'GROUP\s+BY\b', s[i:], _rg.IGNORECASE):
                m = _rg.match(r'GROUP\s+BY\s+', s[i:], _rg.IGNORECASE)
                gb_start = i + m.end()
                break
        i += 1

    if gb_start < 0:
        return ''

    # gb_start부터 HAVING/UNION/LIMIT/EXCEPT/INTERSECT/끝까지 depth=0 추출
    depth = 0; buf = []; i = gb_start
    while i < len(s):
        c = s[i]
        if c in ("'", '"'):
            q = c; buf.append(c); i += 1
            while i < len(s) and s[i] != q:
                if s[i] == '\\': i += 1; buf.append(s[i])
                buf.append(s[i]); i += 1
            if i < len(s): buf.append(s[i])
        elif c == '(':
            depth += 1; buf.append(c)
        elif c == ')':
            if depth == 0: break
            depth -= 1; buf.append(c)
        elif depth == 0:
            # 종료 키워드 검사
            upper = s[i:].upper()
            if any(upper.startswith(k) for k in ('HAVING ', 'HAVING\n', 'UNION ', 'UNION\n',
                                                   'LIMIT ', 'EXCEPT ', 'INTERSECT ', 'ORDER ')):
                break
            buf.append(c)
        else:
            buf.append(c)
        i += 1

    return ''.join(buf).strip().rstrip(';').strip()

def _wrap_order_by(sql: str, db_type: str) -> str:
    """
    ORDER BY 없는 SELECT 쿼리에 ORDER BY 추가.
    - GROUP BY 있는 쿼리: GROUP BY 컬럼을 ORDER BY에 직접 추가
    - 일반 SELECT: 서브쿼리로 감싸서 ORDER BY 1 추가
    - WITH CTE: 마지막에 ORDER BY 1 추가
    소스/타겟 행 순서를 동일하게 맞춰 집합 비교 정확도 향상.
    """
    import re as _rw
    s = sql.strip().rstrip(';')
    dt = (db_type or '').lower()

    # 최외각 레벨 추출 함수 (괄호 depth=0 구간만)
    def _outer(text):
        depth = 0; buf = []
        i = 0
        while i < len(text):
            c = text[i]
            if c in ("'", '"'):
                q = c; i += 1
                while i < len(text) and text[i] != q:
                    if text[i] == '\\': i += 1
                    i += 1
            elif c == '(': depth += 1
            elif c == ')': depth -= 1
            if depth == 0: buf.append(c)
            i += 1
        return ''.join(buf)

    outer = _outer(s)

    # 이미 ORDER BY 있으면 그대로
    if _rw.search(r'\bORDER\s+BY\b', outer, _rw.IGNORECASE):
        return sql

    # SELECT/WITH 가 아니면 패스 (CALL, SET, EXEC 등)
    if not _rw.match(r'\s*(WITH\b|SELECT\b)', s, _rw.IGNORECASE):
        return sql

    # CTE(WITH) → 마지막에 ORDER BY 1 추가
    if _rw.match(r'\s*WITH\b', s, _rw.IGNORECASE):
        return s + '\nORDER BY 1'

    # GROUP BY 있는 쿼리 처리
    if _rw.search(r'\bGROUP\s+BY\b', outer, _rw.IGNORECASE):
        gb_cols = _extract_groupby_cols(s)
        if gb_cols:
            return s + f'\nORDER BY {gb_cols}'

    # 일반 SELECT → 서브쿼리로 감싸서 ORDER BY 1,2,...N
    # 원본 sql에서 SELECT~FROM 사이 depth=0 콤마로 컬럼수 추정
    import re as _rc2
    _pos_m = _rc2.match(r'\s*SELECT\s+', s, _rc2.IGNORECASE)
    col_cnt = 1
    if _pos_m:
        _pos = _pos_m.end(); _d2 = 0; _i = _pos
        while _i < len(s):
            _c = s[_i]
            if _c in ("'", '"'):
                _q = _c; _i += 1
                while _i < len(s) and s[_i] != _q:
                    if s[_i] == '\\': _i += 1
                    _i += 1
            elif _c == '(': _d2 += 1
            elif _c == ')': _d2 -= 1
            elif _d2 == 0:
                if _c == ',': col_cnt += 1
                elif _rc2.match(r'\bFROM\b', s[_i:], _rc2.IGNORECASE): break
            _i += 1
    col_cnt = min(col_cnt, 10)
    order_cols = ','.join(str(n) for n in range(1, col_cnt + 1))
    if dt in ('mysql', 'mariadb', 'aurora', 'tidb'):
        return f"SELECT * FROM (\n{s}\n) _ob ORDER BY {order_cols}"
    else:
        return f"SELECT * FROM (\n{s}\n) AS _ordered ORDER BY {order_cols}"


def _extract_row_limit(sql: str):
    import re
    s = sql.strip()
    m = re.search(r'\bSELECT\s+TOP\s+(\d+)\b', s, re.IGNORECASE)
    if m: return int(m.group(1))
    m = re.search(r'\bLIMIT\s+(\d+)(?:\s*,\s*\d+|\s+OFFSET\s+\d+)?\s*;?\s*$', s, re.IGNORECASE)
    if m: return int(m.group(1))
    return None

def _apply_row_limit(sql: str, n: int, db_type: str) -> str:
    import re
    s = sql.strip().rstrip(';')
    dt = (db_type or '').lower()
    if dt in ('mssql', 'azure', 'sqlserver'):
        if re.search(r'\bSELECT\s+TOP\s+\d+\b', s, re.IGNORECASE): return sql
        # INTERSECT/UNION/EXCEPT 집합 연산은 서브쿼리로 감싸서 TOP 적용
        _outer_up = _get_outer_text(s).upper()
        if re.search(r'\bINTERSECT\b|\bEXCEPT\b|\bUNION\b', _outer_up):
            import re as _re2
            s_no_order = _re2.sub(r'\bORDER\s+BY\s+.+$', '', s.rstrip(';'),
                                   flags=_re2.IGNORECASE|_re2.DOTALL).strip()
            return f'SELECT TOP {n} * FROM (\n{s_no_order}\n) AS _top_wrap ORDER BY 1'
        # WITH CTE 쿼리: CTE 이후 메인 SELECT에만 TOP 적용
        if re.match(r'\s*WITH\b', s, re.IGNORECASE):
            # CTE 정의를 건너뛰고 마지막 메인 SELECT 위치 찾기
            # _get_outer_text로 depth=0 텍스트에서 마지막 SELECT 위치 찾기
            outer = _get_outer_text(s)
            # 마지막 SELECT 찾기 (depth=0)
            last_sel = None
            for mo in re.finditer(r'\bSELECT\b', outer, re.IGNORECASE):
                last_sel = mo
            if last_sel:
                # 원본 SQL에서 같은 오프셋의 SELECT를 TOP으로 교체
                # outer와 원본은 길이가 다를 수 있으므로 위치 매핑
                # 간단한 방법: 마지막 SELECT를 역방향으로 찾아 교체
                import re as _re3
                # 역방향: 마지막 SELECT TOP 없는 것 → TOP 추가
                parts = _re3.split(r'(?i)\bSELECT\b', s)
                if len(parts) > 1:
                    rejoined = 'SELECT'.join(parts[:-1]) + f'SELECT TOP {n}' + parts[-1]
                    return rejoined
        return re.sub(r'\bSELECT\b', f'SELECT TOP {n}', s, count=1, flags=re.IGNORECASE)
    else:
        if re.search(r'\bLIMIT\s+\d+', s, re.IGNORECASE): return sql
        # UNION/INTERSECT 계열은 서브쿼리로 감싸기
        _outer_up = _get_outer_text(s).upper()
        if re.search(r'\bUNION\b|\bINTERSECT\b|\bEXCEPT\b', _outer_up):
            return f'SELECT * FROM (\n{s}\n) _lim_wrap LIMIT {n}'
        return s + f'\nLIMIT {n}'

def _get_outer_text(sql):
    """괄호 depth=0 텍스트만 추출"""
    depth = 0; buf = []; i = 0
    while i < len(sql):
        c = sql[i]
        if c in ("'", '"'):
            q = c; i += 1
            while i < len(sql) and sql[i] != q:
                if sql[i] == '\\': i += 1
                i += 1
        elif c == '(': depth += 1
        elif c == ')': depth -= 1
        if depth == 0: buf.append(c)
        i += 1
    return ''.join(buf)

def _pk_match_query(src_result, src_sql, tgt_sql, src_conn, tgt_conn,
                    max_rows, run_query, serialize):
    """
    PK 기반 검증 (개선판):
    1. 소스(MSSQL) 쿼리에 TOP N 자동 삽입 후 실행
    2. 결과에서 PK 컬럼 자동 탐지
    3. MySQL 타겟 테이블에서 WHERE pk IN (...) 재조회
    4. 동일한 행 집합으로 정확한 비교 보장
    """
    import re, logging as _lg

    src_db_type = (src_conn.get("db_type") or "mssql").lower()
    tgt_db_type = (tgt_conn.get("db_type") or "mysql").lower()

    # ── Step 1: 소스 쿼리에 TOP N 자동 삽입 (MSSQL 계열만) ──
    def inject_top_n(sql, n):
        """
        MSSQL SELECT에 TOP N 자동 삽입
        - 이미 TOP이 있으면 → 그대로 유지 (사용자 의도 존중)
        - TOP이 없으면 → 최대행수(n) 삽입
        """
        sql = sql.strip().lstrip(";").strip()

        # CTE(WITH) 쿼리: 루트 레벨 SELECT/TOP 탐지
        if re.match(r"(;?\s*WITH\s)", sql, re.IGNORECASE):
            depth, last_sel, last_top = 0, -1, -1
            for tok in re.finditer(r"\(|\)|\bSELECT\b|\bTOP\s+\d+", sql, re.IGNORECASE):
                g = tok.group()
                if g == "(":   depth += 1
                elif g == ")": depth -= 1
                elif g.upper() == "SELECT" and depth == 0:
                    last_sel = tok.start()
                elif g.upper().startswith("TOP") and depth == 0:
                    last_top = tok.start()

            if last_top >= 0:
                # 이미 TOP 있음 → 그대로
                return sql
            if last_sel >= 0:
                # TOP 없음 → 삽입
                after = sql[last_sel + 6:]
                dm = re.match(r"\s+DISTINCT\s+", after, re.IGNORECASE)
                if dm:
                    return sql[:last_sel + 6] + after[:dm.end()] + f"TOP {n} " + after[dm.end():]
                return sql[:last_sel + 6] + f" TOP {n}" + after
            return sql

        # 일반 쿼리: 이미 TOP 있으면 그대로
        if re.match(r"SELECT\s+(DISTINCT\s+)?TOP\s+\d+", sql, re.IGNORECASE):
            return sql   # ← 기존 TOP 유지

        # TOP 없음 → 최대행수 삽입
        m = re.match(r"(SELECT\s+)(DISTINCT\s+)?", sql, re.IGNORECASE)
        if m:
            return sql[:m.end()] + f"TOP {n} " + sql[m.end():]

        return sql

    # MSSQL 계열이면 TOP N 삽입
    if src_db_type in ("mssql", "azure"):
        src_sql_with_top = inject_top_n(src_sql, max_rows)
        _lg.info(f"[pk_match] TOP {max_rows} 삽입: {src_sql_with_top[:120]}...")
    else:
        src_sql_with_top = src_sql

    # ── Step 2: TOP N 적용한 소스 쿼리 실행 ─────────────────
    src_result_top = run_query(src_sql_with_top, src_conn)
    if not src_result_top["ok"] or not src_result_top["rows"]:
        _lg.warning("[pk_match] 소스 TOP 쿼리 실패 → 원본 결과 사용")
        # 원본 결과(src_result)가 있으면 그 기반으로
        if not src_result["ok"] or not src_result["rows"]:
            return run_query(tgt_sql, tgt_conn)
        src_result_top = src_result

    cols = src_result_top["cols"]
    rows = src_result_top["rows"]

    # ── Step 3: PK 컬럼 자동 탐지 ───────────────────────────
    pk_patterns = [
        r"^\w+_id$",    # loan_id, cust_id, tx_id, audit_id ...
        r"^id$",
        r"^\w+_no$",    # loan_no, appl_no, tx_no ...
        r"^\w+_key$",
        r"^pk_\w+$",
    ]
    pk_col, pk_idx = None, 0
    for pat in pk_patterns:
        for i, c in enumerate(cols):
            if re.match(pat, c.lower()):
                pk_col, pk_idx = c, i
                break
        if pk_col:
            break

    if not pk_col:
        pk_col, pk_idx = (cols[0], 0) if cols else (None, 0)
        _lg.warning(f"[pk_match] PK 탐지 실패 → 첫 컬럼 {pk_col!r} 사용")
    else:
        _lg.info(f"[pk_match] PK 탐지: {pk_col!r} (idx={pk_idx})")

    if not pk_col:
        return run_query(tgt_sql, tgt_conn)

    # ── Step 4: PK 값 목록 추출 ──────────────────────────────
    pk_values = [row[pk_idx] for row in rows if pk_idx < len(row) and row[pk_idx] is not None]
    if not pk_values:
        return run_query(tgt_sql, tgt_conn)

    # ── Step 5: 타겟 테이블명 파싱 ───────────────────────────
    tbl_match = re.search(
        r"\bFROM\s+[`\[\"]?([\w.]+)[`\]\"]?(?:\s+(?:AS\s+)?\w+)?(?:\s|$)",
        tgt_sql, re.IGNORECASE
    )
    if not tbl_match:
        _lg.warning("[pk_match] 타겟 테이블명 파싱 실패 → 원본 쿼리 사용")
        return run_query(tgt_sql, tgt_conn)

    tgt_table = tbl_match.group(1).strip("`[]\"")
    _lg.info(f"[pk_match] 타겟 테이블: {tgt_table!r}, PK={pk_col!r}, {len(pk_values)}개")

    # ── Step 6: MySQL WHERE pk IN (...) 쿼리 생성 ────────────
    def safe_val(v):
        if v is None: return "NULL"
        try:
            f = float(str(v))
            return str(int(f)) if f == int(f) else str(f)
        except:
            return "'" + str(v).replace("'", "''").strip() + "'"

    in_clause = ", ".join(safe_val(v) for v in pk_values[:1000])

    if tgt_db_type in ("mssql", "azure"):
        col_ref = f"[{pk_col}]";  tbl_ref = f"[{tgt_table}]"
    else:
        col_ref = f"`{pk_col}`";  tbl_ref = f"`{tgt_table}`"

    # 원본 SELECT 절 보존
    sel_m = re.match(r"(SELECT\s+.+?)\s+FROM\s+", tgt_sql, re.IGNORECASE | re.DOTALL)
    select_part = sel_m.group(1) if sel_m else "SELECT *"

    pk_sql = f"{select_part}\nFROM {tbl_ref}\nWHERE {col_ref} IN ({in_clause})\nORDER BY {col_ref}"
    _lg.info(f"[pk_match] 생성 쿼리: {pk_sql[:200]}")

    result = run_query(pk_sql, tgt_conn)
    result["pk_col"]       = pk_col
    result["pk_count"]     = len(pk_values)
    result["pk_method"]    = "pk_match"
    result["src_top_rows"] = len(rows)

    # 소스도 TOP 결과로 교체 (비교 대상 통일)
    src_result_top["pk_col"]    = pk_col
    src_result_top["pk_method"] = "pk_match"

    return result, src_result_top  # (tgt, src) 튜플 반환





@router.post("/compare")
def compare_queries(body: dict):
    """
    소스/타겟 쿼리를 각 DB에 실행하고 결과를 비교
    body: {
        src_sql, tgt_sql,
        src_conn: {db_type, host, port, username, password, database},
        tgt_conn: {db_type, host, port, username, password, database},
        max_rows: int (default 200)
    }
    """
    import time as _t, decimal, datetime

    src_sql  = body.get("src_sql", "").strip()
    tgt_sql  = body.get("tgt_sql", "").strip()
    src_conn = body.get("src_conn", {})
    tgt_conn = body.get("tgt_conn", {})
    _mr = int(body.get("max_rows", 200))
    max_rows = _mr if _mr >= 999999 else min(_mr, 999999)  # Max(전체) 허용

    # ── 행수 자동 조정 ────────────────────────────────────────
    # 소스에서 행수 추출 → 없으면 max_rows 사용
    src_db = (src_conn.get("db_type") or src_conn.get("dbType") or "mssql").lower()
    tgt_db = (tgt_conn.get("db_type") or tgt_conn.get("dbType") or "mysql").lower()
    # ── ORDER BY 자동 추가 (정규화 옵션) ─────────────────────────
    norm_opts = body.get("norm_opts", {})
    if norm_opts.get("autoOrderBy", False):
        src_sql = _wrap_order_by(src_sql, src_db)
        tgt_sql = _wrap_order_by(tgt_sql, tgt_db)

    src_limit = _extract_row_limit(src_sql)
    tgt_limit = _extract_row_limit(tgt_sql)
    # 소스 기준 행수 결정
    effective_n = src_limit if src_limit else max_rows
    # 소스에 없으면 max_rows로 추가
    if not src_limit:
        src_sql = _apply_row_limit(src_sql, effective_n, src_db)
    # 타겟에 소스 기준 행수 적용 (타겟 기존값 무시, 소스와 동일하게)
    if tgt_limit != effective_n:
        # 기존 LIMIT 제거 후 재적용
        import re as _re
        tgt_clean = _re.sub(r'\bLIMIT\s+\d+(?:\s*,\s*\d+|\s+OFFSET\s+\d+)?\s*;?\s*$',
                            '', tgt_sql.strip().rstrip(';'), flags=_re.IGNORECASE).strip()
        tgt_sql = _apply_row_limit(tgt_clean, effective_n, tgt_db)
    import logging as _lg_limit
    _lg_limit.info(f"[compare] 행수조정: src_limit={src_limit} tgt_limit={tgt_limit} effective={effective_n} src_db={src_db} tgt_db={tgt_db}")

    def serialize(v):
        if v is None: return None
        if isinstance(v, (decimal.Decimal,)): return float(v)
        if isinstance(v, (datetime.datetime,)): return v.strftime('%Y-%m-%d %H:%M:%S')
        if isinstance(v, (datetime.date,)): return v.strftime('%Y-%m-%d')
        if isinstance(v, (datetime.time,)): return str(v)
        if isinstance(v, (bytes, bytearray)): return v.hex()
        return v

    QUERY_TIMEOUT = 45  # 쿼리 최대 실행 시간(초)

    def run_query(sql, conn_info):
        if not sql: return {"ok": False, "error": "SQL이 비어있습니다", "rows": [], "cols": [], "elapsed_ms": 0, "row_count": 0}
        # conn_info 타입/내용 확인
        import logging as _lg2
        if not isinstance(conn_info, dict):
            _lg2.warning(f"[compare] conn_info가 dict가 아님: {type(conn_info)} / {conn_info!r}")
            try: conn_info = dict(conn_info)
            except: conn_info = {}
        _lg2.info(f"[compare] conn_info keys={list(conn_info.keys())} host={conn_info.get('host')!r} db={conn_info.get('database')!r}")
        db_type = conn_info.get("db_type") or conn_info.get("dbType") or "mysql"
        host    = conn_info.get("host", "")
        _port_raw = conn_info.get("port") or ""
        port = int(str(_port_raw).strip()) if str(_port_raw).strip().isdigit() else (1434 if db_type in ("mssql","azure") else 3306)
        user    = conn_info.get("username", "")
        pw      = conn_info.get("password", "")
        db      = conn_info.get("database", "")
        if not host or not db:
            import logging as _lg
            _lg.warning(f"[compare] 연결 정보 없음 - db_type={db_type!r} host={host!r} db={db!r} user={user!r} port={port}")
            return {"ok": False, "error": f"연결 정보 없음 (host={host!r}, db={db!r})", "rows": [], "cols": [], "elapsed_ms": 0, "row_count": 0}
        t0 = _t.monotonic()
        try:
            if db_type in ("mysql","mariadb","aurora","tidb"):
                import pymysql
                conn = pymysql.connect(host=host, port=port, user=user, password=pw,
                    database=db, charset="utf8mb4", connect_timeout=10,
                    read_timeout=30, write_timeout=30,
                    cursorclass=pymysql.cursors.DictCursor)
                try:
                    cur = conn.cursor()
                    cur.execute(sql)
                    raw  = cur.fetchall() if max_rows >= 999999 else cur.fetchmany(max_rows)
                    cols = list(raw[0].keys()) if raw else ([d[0] for d in cur.description] if cur.description else [])
                    rows = [[serialize(r[c]) for c in cols] for r in raw]
                    return {"ok": True, "cols": cols, "rows": rows,
                            "elapsed_ms": round((_t.monotonic()-t0)*1000,1),
                            "row_count": len(rows), "error": ""}
                finally: conn.close()

            elif db_type in ("mssql","azure"):
                from app.core.db_conn import make_mssql_conn
                conn = make_mssql_conn(host, port, user, pw, db)
                try:
                    cur = conn.cursor()
                    # pyodbc는 execute timeout을 직접 지원 안 함 - connection timeout으로 처리
                    conn.timeout = QUERY_TIMEOUT
                    cur.execute(sql)
                    raw  = cur.fetchall() if max_rows >= 999999 else cur.fetchmany(max_rows)
                    cols = [d[0] for d in cur.description] if cur.description else []
                    rows = [[serialize(v) for v in row] for row in raw]
                    return {"ok": True, "cols": cols, "rows": rows,
                            "elapsed_ms": round((_t.monotonic()-t0)*1000,1),
                            "row_count": len(rows), "error": ""}
                finally: conn.close()

            else:
                return {"ok": False, "error": f"{db_type} 미지원", "rows": [], "cols": [], "elapsed_ms": 0, "row_count": 0}

        except Exception as e:
            return {"ok": False, "error": str(e), "rows": [], "cols": [],
                    "elapsed_ms": round((_t.monotonic()-t0)*1000,1), "row_count": 0}

    # ── 1단계: 소스 실행 ──────────────────────────────────────
    src_result = run_query(src_sql, src_conn)

    # ── 2단계: PK 기반 타겟 재조회 (pk_match 모드) ────────────
    verify_mode = body.get("verify_mode", "set")

    if verify_mode == "pk_match":
        # TOP N 삽입 후 소스 실행 → PK 추출 → 타겟 재조회
        pk_result = _pk_match_query(
            src_result, src_sql, tgt_sql, src_conn, tgt_conn,
            max_rows, run_query, serialize
        )
        if isinstance(pk_result, tuple):
            tgt_result, src_result = pk_result   # src도 TOP 결과로 교체
        else:
            tgt_result = pk_result
    else:
        tgt_result = run_query(tgt_sql, tgt_conn)

    # 결과 비교
    # ── norm_opts 기반 정규화 설정 ──────────────────────────────
    _no       = body.get("norm_opts", {}) or {}
    _dec      = _no.get("decimal",  {})
    _dtime    = _no.get("datetime", {})
    _str      = _no.get("string",   {})
    _null_eq  = _no.get("nullEmpty", True)
    _bool_int = _no.get("boolInt",   False)

    def _norm_val(v):
        """norm_opts 기반 정규화 - 소수점·날짜·문자열·타입 옵션 적용"""
        import math as _math
        from datetime import datetime as _dt

        if v is None:
            return '' if _null_eq else '__NULL__'
        s = str(v)
        if _str.get("trim", True): s = s.strip()
        if s == '' or s.lower() in ('none','null'): return ''
        if _str.get("caseInsensitive", False): s = s.lower()
        if _bool_int and s.lower() in ('true','false','1','0'):
            return '1' if s.lower() in ('true','1') else '0'

        # 숫자 처리
        try:
            f = float(s.replace(',', ''))
            if f == int(f) and '.' not in s.replace(',', ''):
                return str(int(f))
            if not _dec.get("enabled", True): return s
            mode, digits = _dec.get("mode","round"), int(_dec.get("digits", 4))
            if mode == "ignore":
                return str(int(f))          # 소수점 전체 무시 → 정수만 비교
            if mode == "skip_below":
                # X자리 이하 무시: digits 자리까지만 비교, 그 이하는 잘라냄
                # 예) digits=4 → 503925549.4772 까지만 비교 (4자리 초과 무시)
                m2 = 10 ** digits
                truncated = _math.trunc(f * m2) / m2
                return f'{truncated:.{digits}f}'.rstrip('0').rstrip('.')
            m = 10 ** digits
            if mode == "floor":  r = _math.floor(f * m) / m
            elif mode == "ceil": r = _math.ceil(f * m) / m
            elif mode == "trunc":r = _math.trunc(f * m) / m
            else:                r = round(f, digits)
            return f'{r:.{digits}f}'.rstrip('0').rstrip('.')
        except: pass

        # 날짜 처리
        if _dtime.get("enabled", True):
            dm = _dtime.get("mode","date")
            for fmt in ('%Y-%m-%d %H:%M:%S.%f','%Y-%m-%d %H:%M:%S','%Y-%m-%dT%H:%M:%S','%Y-%m-%d'):
                try:
                    dt = _dt.strptime(s[:len(fmt)], fmt)
                    if dm=="date":     return dt.strftime('%Y-%m-%d')
                    if dm=="datetime": return dt.strftime('%Y-%m-%d %H:%M:%S')
                    if dm=="ym":       return dt.strftime('%Y-%m')
                    if dm=="year":     return dt.strftime('%Y')
                    return dt.strftime('%Y-%m-%d')
                except: pass

        # 월수 허용 (±1): DATEDIFF(MONTH) vs TIMESTAMPDIFF(MONTH) 경계 차이 흡수
        # 숫자인데 monthTolerance 옵션이 켜져 있으면 처리는 비교 단계에서 별도 수행
        return s


    def _row_key(row):
        """행을 비교 가능한 튜플 키로 변환 - 모든 값 정규화"""
        return tuple(_norm_val(v) for v in row)

    def compare(a, b):
        from collections import Counter
        mode = body.get("verify_mode", "set")   # order|set|checksum|hash_row|column_stats

        if not a["ok"] or not b["ok"]:
            return {"match": False, "reason": "실행 오류"}

        # ── 공통 전처리 ──────────────────────────────────────
        if len(a["cols"]) != len(b["cols"]):
            return {"match": False,
                    "reason": f"컬럼 수 불일치 (소스:{len(a['cols'])} vs 타겟:{len(b['cols'])})"}

        rows_a = a["rows"]
        rows_b = b["rows"]

        # ══════════════════════════════════════════════════════
        # ① 순서일치 (order) — 행 순서까지 완전 일치
        # ══════════════════════════════════════════════════════
        if mode == "order":
            if a["row_count"] != b["row_count"]:
                return {"match": False,
                        "reason": f"행 수 불일치 (소스:{a['row_count']} vs 타겟:{b['row_count']})"}
            diffs = []
            for i, (ra, rb) in enumerate(zip(rows_a, rows_b)):
                row_diffs = []
                for j, (va, vb) in enumerate(zip(ra, rb)):
                    if _norm_val(va) != _norm_val(vb):
                        col = a["cols"][j] if j < len(a["cols"]) else str(j)
                        row_diffs.append({"col_src": col, "col_tgt": col,
                                          "src": str(va), "tgt": str(vb)})
                if row_diffs:
                    diffs.append({"row": i+1, "type": "both", "diffs": row_diffs})
            if not diffs:
                return {"match": True, "reason": "완전 일치 (순서 포함)"}
            return {"match": False,
                    "reason": f"{len(diffs)}개 행 불일치",
                    "diff_rows": diffs[:20]}

        # ══════════════════════════════════════════════════════
        # ② 집합비교 (set) — 순서 무관, 데이터 집합 비교 ★ 권장
        # ══════════════════════════════════════════════════════
        if mode in ("set", None, ""):
            if a["row_count"] != b["row_count"]:
                return {"match": False,
                        "reason": f"행 수 불일치 (소스:{a['row_count']} vs 타겟:{b['row_count']})"}
            # 둘 다 0행 → 완전 일치
            if a["row_count"] == 0 and b["row_count"] == 0:
                return {"match": True, "reason": "완전 일치 (0행 — 조건에 해당하는 데이터 없음)"}
            # 1차: 순서 그대로 비교 (빠른 경로)
            _month_tol = _no.get("monthTolerance", False)
            def _norm_eq(va, vb):
                """정규화 후 동일 여부 - monthTolerance 옵션 포함"""
                na, nb = _norm_val(va), _norm_val(vb)
                if na == nb: return True
                if _month_tol:
                    try:
                        fa, fb = float(na), float(nb)
                        if fa == int(fa) and fb == int(fb) and abs(fa - fb) <= 1:
                            return True
                    except: pass
                return False
            order_diffs = []
            for i, (ra, rb) in enumerate(zip(rows_a, rows_b)):
                row_diffs = []
                for j, (va, vb) in enumerate(zip(ra, rb)):
                    if not _norm_eq(va, vb):
                        col = a["cols"][j] if j < len(a["cols"]) else str(j)
                        row_diffs.append({"col_src": col, "col_tgt": col,
                                          "src": str(va), "tgt": str(vb)})
                if row_diffs:
                    order_diffs.append({"row": i+1, "type": "both", "diffs": row_diffs})

            if not order_diffs:
                return {"match": True, "reason": "완전 일치"}

            # 2차: 집합 비교 (정렬 차이 허용)
            set_a = sorted(_row_key(r) for r in rows_a)
            set_b = sorted(_row_key(r) for r in rows_b)
            if set_a == set_b:
                return {"match": True,
                        "reason": "데이터 일치 (정렬 순서 다름)",
                        "warning": "ORDER BY 기준이 DB간 다릅니다 (NULL 정렬, 동점 처리 등)",
                        "order_diff_cnt": len(order_diffs)}

            # 3차: 실제 불일치 행 추출
            cnt_a = Counter(_row_key(r) for r in rows_a)
            cnt_b = Counter(_row_key(r) for r in rows_b)
            only_a = cnt_a - cnt_b
            only_b = cnt_b - cnt_a
            diff_sample, row_num = [], 1
            for key in list(only_a.keys())[:10]:
                for ra in rows_a:
                    if _row_key(ra) == key:
                        diff_sample.append({"row": row_num, "type": "src_only",
                            "diffs": [{"col_src": col, "col_tgt": col,
                                       "src": str(ra[j]) if j < len(ra) else "", "tgt": "—"}
                                      for j, col in enumerate(a["cols"][:8])]})
                        row_num += 1; break
            for key in list(only_b.keys())[:10]:
                for rb in rows_b:
                    if _row_key(rb) == key:
                        diff_sample.append({"row": row_num, "type": "tgt_only",
                            "diffs": [{"col_src": col, "col_tgt": col,
                                       "src": "—", "tgt": str(rb[j]) if j < len(rb) else ""}
                                      for j, col in enumerate(b["cols"][:8])]})
                        row_num += 1; break
            # ── 경계값 허용 옵션 ─────────────────────────────────
            # 소스전용/타겟전용이 모두 "동일한 값 집합"이면 경계값 잘림으로 판단 → 통과
            _no2 = body.get("norm_opts", {}) or {}
            if _no2.get("boundaryTolerance", False) and only_a and only_b:
                # only_a의 값들과 only_b의 값들이 같은 값(정규화 후)인지 확인
                # 같은 컬럼 값 집합이면 → 경계에서 다른 행이 잘린 것
                def _val_set(keys):
                    # key는 tuple of normalized values
                    return set(keys.keys())
                # 각 불일치 행의 "수치 컬럼" 값들이 같은지 확인
                vals_a = sorted(set(k for k in only_a.keys()))
                vals_b = sorted(set(k for k in only_b.keys()))
                # 모든 소스전용 값이 타겟전용 값과 같은 값 범위면 경계값
                a_val_strs = set(str(k) for k in vals_a)
                b_val_strs = set(str(k) for k in vals_b)
                if a_val_strs == b_val_strs:
                    return {"match": True,
                            "reason": f"데이터 일치 (경계값 {len(only_a)}행 허용)",
                            "warning": f"TOP/LIMIT 경계에서 동일한 값을 가진 다른 행이 선택됨 (소스:{len(only_a)}행 ↔ 타겟:{len(only_b)}행)",
                            "boundary_diff": len(only_a)}
            return {"match": False,
                    "reason": f"{len(only_a)+len(only_b)}개 행 불일치 (소스전용:{len(only_a)}, 타겟전용:{len(only_b)})",
                    "diff_rows": diff_sample}

        # ══════════════════════════════════════════════════════
        # ③ 컬럼 정렬 비교 (col_sort) — 각 컬럼별 정렬 후 비교
        # 소량 행수(10/50)에서 ORDER BY 노이즈 없이 정확한 비교
        # ══════════════════════════════════════════════════════
        if mode == "col_sort":
            if a["row_count"] != b["row_count"]:
                return {"match": False,
                        "reason": f"행 수 불일치 (소스:{a['row_count']} vs 타겟:{b['row_count']})"}
            if not rows_a:
                return {"match": True, "reason": "완전 일치 (0행)"}

            # 각 컬럼별로 정규화된 값 리스트를 정렬해서 비교
            cols = a["cols"]
            col_diffs = []
            for j, col in enumerate(cols):
                vals_a = sorted(_norm_val(r[j]) for r in rows_a if j < len(r))
                vals_b = sorted(_norm_val(r[j]) for r in rows_b if j < len(r))
                if vals_a != vals_b:
                    # 불일치 샘플 추출
                    only_a_vals = []
                    only_b_vals = []
                    import collections as _col
                    ca = _col.Counter(str(v) for v in vals_a)
                    cb = _col.Counter(str(v) for v in vals_b)
                    diff_a = ca - cb
                    diff_b = cb - ca
                    col_diffs.append({
                        "col": col,
                        "src_only": list(diff_a.keys())[:5],
                        "tgt_only": list(diff_b.keys())[:5],
                    })

            if not col_diffs:
                return {"match": True, "reason": f"완전 일치 (컬럼 정렬 비교, {a['row_count']}행)"}

            diff_rows = []
            for cd in col_diffs[:20]:
                diff_rows.append({"row": 0, "type": "col_diff",
                    "diffs": [{"col_src": cd["col"], "col_tgt": cd["col"],
                               "src": ", ".join(cd["src_only"]),
                               "tgt": ", ".join(cd["tgt_only"])}]})
            return {"match": False,
                    "reason": f"{len(col_diffs)}개 컬럼 불일치",
                    "diff_rows": diff_rows}

        # ══════════════════════════════════════════════════════
        # ④ 체크섬 (checksum) — 전체를 해시 하나로 압축 비교
        # ══════════════════════════════════════════════════════
        if mode == "checksum":
            import hashlib, json
            def _hash_rows(rows):
                normalized = [tuple(_norm_val(v) for v in r) for r in rows]
                normalized.sort()
                return hashlib.md5(json.dumps(normalized, ensure_ascii=False).encode()).hexdigest()

            hash_a = _hash_rows(rows_a)
            hash_b = _hash_rows(rows_b)

            if a["row_count"] != b["row_count"]:
                return {"match": False,
                        "reason": f"행 수 불일치 (소스:{a['row_count']} vs 타겟:{b['row_count']})"}
            if hash_a == hash_b:
                return {"match": True,
                        "reason": f"체크섬 일치 ({a['row_count']}행 동일)",
                        "checksum": hash_a}
            return {"match": False,
                    "reason": f"체크섬 불일치 — 데이터 내용이 다릅니다",
                    "checksum_src": hash_a, "checksum_tgt": hash_b,
                    "note": "어느 행이 다른지 확인하려면 집합비교(★) 모드를 사용하세요"}

        # ══════════════════════════════════════════════════════
        # ④ 행해시 (hash_row) — 각 행을 해시로 비교
        # ══════════════════════════════════════════════════════
        if mode == "hash_row":
            import hashlib, json
            def _row_hash(row):
                return hashlib.md5(
                    json.dumps(tuple(_norm_val(v) for v in row),
                               ensure_ascii=False).encode()).hexdigest()

            hashes_a = Counter(_row_hash(r) for r in rows_a)
            hashes_b = Counter(_row_hash(r) for r in rows_b)
            only_a_h = hashes_a - hashes_b
            only_b_h = hashes_b - hashes_a

            if not only_a_h and not only_b_h:
                return {"match": True, "reason": f"행해시 완전 일치 ({a['row_count']}행)"}

            # 불일치 행 샘플 추출
            def _row_hash_str(row): return _row_hash(row)
            diff_sample, row_num = [], 1
            for h in list(only_a_h.keys())[:10]:
                for ra in rows_a:
                    if _row_hash_str(ra) == h:
                        diff_sample.append({"row": row_num, "type": "src_only",
                            "diffs": [{"col_src": col, "col_tgt": col,
                                       "src": str(ra[j]) if j < len(ra) else "", "tgt": "—"}
                                      for j, col in enumerate(a["cols"][:8])]})
                        row_num += 1; break
            for h in list(only_b_h.keys())[:10]:
                for rb in rows_b:
                    if _row_hash_str(rb) == h:
                        diff_sample.append({"row": row_num, "type": "tgt_only",
                            "diffs": [{"col_src": col, "col_tgt": col,
                                       "src": "—", "tgt": str(rb[j]) if j < len(rb) else ""}
                                      for j, col in enumerate(b["cols"][:8])]})
                        row_num += 1; break
            total = len(only_a_h) + len(only_b_h)
            return {"match": False,
                    "reason": f"행해시 불일치 {total}행 (소스전용:{len(only_a_h)}, 타겟전용:{len(only_b_h)})",
                    "diff_rows": diff_sample}

        # ══════════════════════════════════════════════════════
        # ⑤ 컬럼통계 (column_stats) — MIN/MAX/AVG/COUNT 비교
        # ══════════════════════════════════════════════════════
        if mode == "column_stats":
            if not rows_a or not rows_b:
                return {"match": True, "reason": "데이터 없음 (둘 다 0행)"}

            cols = a["cols"]
            stats_diffs = []
            for j, col in enumerate(cols):
                vals_a = [_norm_val(r[j]) for r in rows_a if j < len(r)]
                vals_b = [_norm_val(r[j]) for r in rows_b if j < len(r)]

                null_a = sum(1 for v in vals_a if v == '')
                null_b = sum(1 for v in vals_b if v == '')

                # 숫자 컬럼 통계
                nums_a = []
                nums_b = []
                for v in vals_a:
                    try: nums_a.append(float(v))
                    except: pass
                for v in vals_b:
                    try: nums_b.append(float(v))
                    except: pass

                col_diff = {}
                if null_a != null_b:
                    col_diff['null_count'] = {'src': null_a, 'tgt': null_b}
                if nums_a and nums_b:
                    avg_a = round(sum(nums_a)/len(nums_a), 4)
                    avg_b = round(sum(nums_b)/len(nums_b), 4)
                    min_a, max_a = round(min(nums_a),4), round(max(nums_a),4)
                    min_b, max_b = round(min(nums_b),4), round(max(nums_b),4)
                    if abs(avg_a - avg_b) > 0.001:
                        col_diff['avg'] = {'src': avg_a, 'tgt': avg_b}
                    if min_a != min_b:
                        col_diff['min'] = {'src': min_a, 'tgt': min_b}
                    if max_a != max_b:
                        col_diff['max'] = {'src': max_a, 'tgt': max_b}

                if col_diff:
                    stats_diffs.append({
                        "col": col,
                        "row": len(stats_diffs)+1,
                        "type": "both",
                        "diffs": [{"col_src": f"{col}.{k}", "col_tgt": f"{col}.{k}",
                                   "src": str(v['src']), "tgt": str(v['tgt'])}
                                  for k, v in col_diff.items()]
                    })

            if not stats_diffs:
                return {"match": True,
                        "reason": f"컬럼 통계 일치 ({len(cols)}개 컬럼, 소스:{a['row_count']}행/타겟:{b['row_count']}행)"}
            return {"match": False,
                    "reason": f"컬럼 통계 불일치 — {len(stats_diffs)}개 컬럼에서 차이 발견",
                    "diff_rows": stats_diffs}

        # 알 수 없는 모드 → 집합비교로 fallback
        return {"match": False, "reason": f"알 수 없는 검증모드: {mode}"}
    comparison = compare(src_result, tgt_result)
    return {
        "src": src_result,
        "tgt": tgt_result,
        "comparison": comparison,
    }


@router.post("/convert-ai")
def convert_query_ai(body: dict):
    """
    Claude API를 사용한 고품질 SQL 변환
    API 키 없으면 규칙 기반으로 폴백
    body: { sql, src_db, tgt_db }
    """
    import json as _j, urllib.request as _ur, urllib.error as _ue, os as _os

    sql    = body.get("sql", "").strip()
    src_db = body.get("src_db", "mysql")
    tgt_db = body.get("tgt_db", "mssql")

    if not sql:
        raise HTTPException(400, "SQL이 비어있습니다")

    # API 키 확인
    try:
        from app.api.routes.settings import _cfg as _get_cfg
        api_key = _get_cfg().get("anthropic_api_key", "").strip()
    except Exception:
        api_key = ""
    api_key = api_key or _os.environ.get("ANTHROPIC_API_KEY", "").strip()

    # API 키 없으면 규칙 기반 변환으로 폴백
    if not api_key:
        result = convert_sql(sql, src_db, tgt_db)
        result["method"] = "rules"
        result["api_available"] = False
        return result

    # Claude AI 변환
    src_name = {"mssql":"SQL Server","mysql":"MySQL","mariadb":"MariaDB",
                "postgresql":"PostgreSQL","aurora":"Aurora"}.get(src_db, src_db)
    tgt_name = {"mssql":"SQL Server","mysql":"MySQL","mariadb":"MariaDB",
                "postgresql":"PostgreSQL","aurora":"Aurora"}.get(tgt_db, tgt_db)

    # 파일이 매우 큰 경우 규칙 기반으로 폴백 (Claude API 컨텍스트 한계)
    MAX_SQL_CHARS = 80000  # ~20만 토큰 이하
    sql_truncated = False
    sql_for_prompt = sql
    if len(sql) > MAX_SQL_CHARS:
        # 큰 파일은 규칙 기반으로 처리 (AI는 전체 컨텍스트를 다 못 봄)
        result = convert_sql(sql, src_db, tgt_db)
        result["method"] = "rules"
        result["api_available"] = True
        result["warnings"] = result.get("warnings", []) + [
            f"파일이 너무 커서({len(sql)//1024}KB) 규칙 기반으로 변환했습니다. Claude AI는 80KB 이하 파일을 지원합니다."
        ]
        return result

    prompt = (
        f"당신은 {src_name} → {tgt_name} SQL 변환 전문가입니다.\n"
        f"아래 {src_name} SQL 쿼리를 {tgt_name}에서 실행 가능하도록 정확히 변환하세요.\n\n"
        "변환 규칙:\n"
        f"- 모든 함수/문법을 {tgt_name} 표준으로 변환\n"
        "- DATE_FORMAT↔FORMAT, DATEDIFF 인자 순서, GETDATE()↔NOW() 등 정확히 변환\n"
        "- CTE, 윈도우 함수, 서브쿼리 구조 유지\n"
        "- 한글 별칭(AS 절) 그대로 유지\n"
        "- 원본 SQL의 로직/의미 완전히 동일하게 유지\n\n"
        f"원본 SQL ({src_name}):\n{sql_for_prompt}\n\n"
        "JSON만 응답 (마크다운/코드블록 없이):\n"
        '{"converted":"변환된SQL","changes":["변경사항1","변경사항2"],"warnings":["주의사항"]}'
    )

    try:
        payload = _j.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 16000,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        req = _ur.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
        )
        with _ur.urlopen(req, timeout=30) as resp:
            data = _j.loads(resp.read())
        
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
        
        # JSON 파싱
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        
        parsed = _j.loads(text.strip())
        # AI 변환 결과 후처리 (섹션 구분 주석 제거)
        if "converted" in parsed:
            parsed["converted"] = _clean_converted_sql(parsed["converted"])
        parsed["method"] = "claude-ai"
        parsed["api_available"] = True

        # 사용량 기록
        try:
            _usage = data.get("usage", {})
            from app.core.store import Store as _St
            _us = _St("claude_usage")
            _prev = _us.get("total") or {"calls":0,"input_tokens":0,"output_tokens":0,"objects":[]}
            _prev["calls"] += 1
            _prev["input_tokens"]  += _usage.get("input_tokens", 0)
            _prev["output_tokens"] += _usage.get("output_tokens", 0)
            _prev["objects"].append({
                "name": f"{src_db}→{tgt_db}",
                "type": "SQL_CONVERT",
                "in":   _usage.get("input_tokens", 0),
                "out":  _usage.get("output_tokens", 0),
                "ts":   __import__("datetime").datetime.now().isoformat()
            })
            _prev["objects"] = _prev["objects"][-100:]
            _us.set("total", _prev)
        except Exception:
            pass

        return parsed

    except Exception as e:
        # AI 실패 시 규칙 기반 폴백
        result = convert_sql(sql, src_db, tgt_db)
        result["method"] = "rules_fallback"
        result["api_available"] = True
        result["ai_error"] = str(e)[:100]
        return result
