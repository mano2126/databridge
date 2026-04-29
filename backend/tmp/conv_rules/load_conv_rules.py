"""
load_conv_rules.py  — backend 폴더에서 실행
"""
import json, ast, shutil, os
from datetime import datetime

RULES_DIR = 'mssql_to_mysql'
CONVERTER  = 'app/api/routes/sql_converter.py'

# JSON 파일 로드 (통계 출력용)
all_rules = []
files = sorted(f for f in os.listdir(RULES_DIR) if f.endswith('.json'))
print(f'{RULES_DIR}/ 에서 {len(files)}개 파일 로드:')
for fname in files:
    data = json.load(open(os.path.join(RULES_DIR, fname), encoding='utf-8'))
    rules = data.get('rules', [])
    print(f'  ✓ {fname}: {len(rules)}개')
    all_rules.extend(rules)
print(f'총 JSON 규칙: {len(all_rules)}개\n')

# 핵심 변환 규칙 (repr()로 안전하게 인코딩)
CORE_RULES = [
    (r'\bIDENTITY\s*\(\d+,\s*\d+\)',             r'AUTO_INCREMENT',                'IDENTITY→AUTO_INCREMENT'),
    (r'\bNVARCHAR\s*\(MAX\)',                     r'LONGTEXT',                      'NVARCHAR(MAX)→LONGTEXT'),
    (r'\bVARCHAR\s*\(MAX\)',                      r'LONGTEXT',                      'VARCHAR(MAX)→LONGTEXT'),
    (r'\bNVARCHAR\b',                             r'VARCHAR',                       'NVARCHAR→VARCHAR'),
    (r'\bNCHAR\b',                                r'CHAR',                          'NCHAR→CHAR'),
    (r'\bNTEXT\b',                                r'LONGTEXT',                      'NTEXT→LONGTEXT'),
    (r'\bVARBINARY\s*\(MAX\)',                    r'LONGBLOB',                      'VARBINARY(MAX)→LONGBLOB'),
    (r'\bDATETIME2\s*\(\s*\d+\s*\)',             r'DATETIME(6)',                   'DATETIME2(n)→DATETIME(6)'),
    (r'\bDATETIME2\b',                            r'DATETIME(6)',                   'DATETIME2→DATETIME(6)'),
    (r'\bSMALLDATETIME\b',                        r'DATETIME',                      'SMALLDATETIME→DATETIME'),
    (r'\bDATETIMEOFFSET\b',                       r'DATETIME(6)',                   'DATETIMEOFFSET→DATETIME(6) 시간대손실'),
    (r'\bBIT\b',                                  r'TINYINT(1)',                    'BIT→TINYINT(1)'),
    (r'\bMONEY\b',                                r'DECIMAL(19,4)',                 'MONEY→DECIMAL(19,4)'),
    (r'\bSMALLMONEY\b',                          r'DECIMAL(10,4)',                  'SMALLMONEY→DECIMAL(10,4)'),
    (r'\bUNIQUEIDENTIFIER\b',                   r'CHAR(36)',                       'UNIQUEIDENTIFIER→CHAR(36)'),
    (r'\bXML\b',                                  r'LONGTEXT',                      'XML→LONGTEXT'),
    (r'\bSQL_VARIANT\b',                          r'TEXT',                          'SQL_VARIANT→TEXT'),
    (r'\bSYSNAME\b',                              r'VARCHAR(128)',                  'SYSNAME→VARCHAR(128)'),
    (r'\bIMAGE\b',                                r'LONGBLOB',                      'IMAGE→LONGBLOB'),
    (r'\bROWVERSION\b',                           r'BIGINT UNSIGNED',               'ROWVERSION→BIGINT UNSIGNED'),
    (r'\bFLOAT\b',                                r'DOUBLE',                        'FLOAT→DOUBLE'),
    (r'\bREAL\b',                                 r'FLOAT',                         'REAL→FLOAT'),
    (r'\[dbo\]\.',                                r'',                              'dbo 스키마 제거'),
    (r'\bWITH\s*\(NOLOCK\)',                      r'',                              'NOLOCK 힌트 제거'),
    (r'\bWITH\s*\(UPDLOCK\)',                     r'FOR UPDATE',                    'UPDLOCK→FOR UPDATE'),
    (r'\bPRIMARY\s+KEY\s+CLUSTERED\b',           r'PRIMARY KEY',                   'CLUSTERED 제거'),
    (r'\bPRIMARY\s+KEY\s+NONCLUSTERED\b',        r'PRIMARY KEY',                   'NONCLUSTERED 제거'),
    (r'\bNONCLUSTERED\b',                         r'',                              'NONCLUSTERED 제거'),
    (r'ON\s+\[PRIMARY\]',                         r'',                              'ON PRIMARY 제거'),
    (r'\bTEXTIMAGE_ON\s+\[PRIMARY\]',            r'',                              'TEXTIMAGE_ON 제거'),
    (r'\bWITH\s+RECOMPILE\b',                    r'',                              'WITH RECOMPILE 제거'),
    (r'\bWITH\s+ENCRYPTION\b',                   r'',                              'WITH ENCRYPTION 제거'),
    (r'\bWITH\s+SCHEMABINDING\b',                r'',                              'WITH SCHEMABINDING 제거'),
    (r'\bSET\s+NOCOUNT\s+ON\s*;?',               r'',                              'SET NOCOUNT ON 제거'),
    (r'\bSET\s+NOCOUNT\s+OFF\s*;?',              r'',                              'SET NOCOUNT OFF 제거'),
    (r'\bSET\s+XACT_ABORT\s+ON\s*;?',            r'',                              'SET XACT_ABORT ON 제거'),
    (r'\bSET\s+ANSI_NULLS\s+\w+\s*;?',          r'',                              'SET ANSI_NULLS 제거'),
    (r'\bSET\s+QUOTED_IDENTIFIER\s+\w+\s*;?',   r'',                              'SET QUOTED_IDENTIFIER 제거'),
    (r'\bGO\b',                                   r'',                              'GO 제거'),
    (r'CREATE\s+OR\s+ALTER\s+PROCEDURE\s+',      r'CREATE OR REPLACE PROCEDURE ',  'OR ALTER PROC→OR REPLACE'),
    (r'CREATE\s+OR\s+ALTER\s+FUNCTION\s+',       r'CREATE OR REPLACE FUNCTION ',   'OR ALTER FUNC→OR REPLACE'),
    (r'CREATE\s+OR\s+ALTER\s+VIEW\s+',           r'CREATE OR REPLACE VIEW ',       'OR ALTER VIEW→OR REPLACE'),
    (r'CREATE\s+OR\s+ALTER\s+TRIGGER\s+',        r'CREATE OR REPLACE TRIGGER ',    'OR ALTER TRIG→OR REPLACE'),
    (r'\bAS\s*\n\s*BEGIN\b',                     r'BEGIN',                          'AS BEGIN→BEGIN'),
    (r'\bAS\s+BEGIN\b',                          r'BEGIN',                          'AS BEGIN인라인→BEGIN'),
    (r'\bGETDATE\s*\(\)',                         r'NOW()',                          'GETDATE()→NOW()'),
    (r'\bSYSDATETIME\s*\(\)',                     r'NOW(6)',                         'SYSDATETIME→NOW(6)'),
    (r'\bGETUTCDATE\s*\(\)',                      r'UTC_TIMESTAMP()',                'GETUTCDATE→UTC_TIMESTAMP'),
    (r'\bDATEADD\s*\(\s*(\w+)\s*,\s*(-?\d+)\s*,\s*([^)]+)\)', r'DATE_ADD(\3, INTERVAL \2 \1)', 'DATEADD→DATE_ADD'),
    (r'\bDATEDIFF\s*\(\s*day\s*,\s*([^,]+),\s*([^)]+)\)',   r'DATEDIFF(\2,\1)',  'DATEDIFF day 순서반대'),
    (r'\bDATEDIFF\s*\(\s*(\w+)\s*,\s*([^,]+),\s*([^)]+)\)', r'TIMESTAMPDIFF(\1,\2,\3)', 'DATEDIFF→TIMESTAMPDIFF'),
    (r'\bDATEPART\s*\(\s*year\s*,',             r'YEAR(',                          'DATEPART year→YEAR'),
    (r'\bDATEPART\s*\(\s*month\s*,',            r'MONTH(',                         'DATEPART month→MONTH'),
    (r'\bDATEPART\s*\(\s*day\s*,',              r'DAY(',                           'DATEPART day→DAY'),
    (r'\bDATEPART\s*\(\s*hour\s*,',             r'HOUR(',                          'DATEPART hour→HOUR'),
    (r'\bDATEPART\s*\(\s*minute\s*,',           r'MINUTE(',                        'DATEPART minute→MINUTE'),
    (r'\bDATEPART\s*\(\s*second\s*,',           r'SECOND(',                        'DATEPART second→SECOND'),
    (r'\bDATEPART\s*\(\s*quarter\s*,',          r'QUARTER(',                       'DATEPART quarter→QUARTER'),
    (r'\bDATEPART\s*\(\s*week\s*,',             r'WEEK(',                          'DATEPART week→WEEK'),
    (r'\bEOMONTH\s*\(',                          r'LAST_DAY(',                      'EOMONTH→LAST_DAY'),
    (r'\bCONVERT\s*\(\s*DATE\s*,',              r'DATE(',                          'CONVERT DATE→DATE('),
    (r'\bLEN\s*\(',                              r'CHAR_LENGTH(',                   'LEN→CHAR_LENGTH'),
    (r'\bDATALENGTH\s*\(',                       r'LENGTH(',                        'DATALENGTH→LENGTH'),
    (r'\bCHARINDEX\s*\(\s*([^,]+),\s*([^,)]+)\)', r'LOCATE(\1,\2)',              'CHARINDEX→LOCATE'),
    (r'\bREPLICATE\s*\(',                        r'REPEAT(',                        'REPLICATE→REPEAT'),
    (r'\bSTUFF\s*\(\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^)]+)\)', r'INSERT(\1,\2,\3,\4)', 'STUFF→INSERT'),
    (r'\bSTRING_AGG\s*\(\s*([^,]+),\s*([^)]+)\)\s*WITHIN\s+GROUP\s*\(\s*ORDER\s+BY\s+([^)]+)\)', r'GROUP_CONCAT(\1 ORDER BY \3 SEPARATOR \2)', 'STRING_AGG WITHIN GROUP→GROUP_CONCAT'),
    (r'\bSTRING_AGG\s*\(\s*([^,]+),\s*([^)]+)\)', r'GROUP_CONCAT(\1 SEPARATOR \2)', 'STRING_AGG→GROUP_CONCAT'),
    (r'\bISNULL\s*\(',                           r'IFNULL(',                        'ISNULL→IFNULL'),
    (r'\bIIF\s*\(',                              r'IF(',                            'IIF→IF'),
    (r'\bCHOOSE\s*\(',                           r'ELT(',                           'CHOOSE→ELT'),
    (r'\bNEWID\s*\(\)',                          r'UUID()',                          'NEWID→UUID'),
    (r'\bSCOPE_IDENTITY\s*\(\)',                r'LAST_INSERT_ID()',               'SCOPE_IDENTITY→LAST_INSERT_ID'),
    (r'@@IDENTITY\b',                           r'LAST_INSERT_ID()',               '@@IDENTITY→LAST_INSERT_ID'),
    (r'@@ROWCOUNT\b',                           r'ROW_COUNT()',                    '@@ROWCOUNT→ROW_COUNT'),
    (r'@@SPID\b',                               r'CONNECTION_ID()',                '@@SPID→CONNECTION_ID'),
    (r'\bDB_NAME\s*\(\)',                        r'DATABASE()',                      'DB_NAME→DATABASE'),
    (r'\bPOWER\s*\(',                            r'POW(',                           'POWER→POW'),
    (r'\bSQUARE\s*\(\s*([^)]+)\)',              r'POW(\1, 2)',                     'SQUARE→POW(n,2)'),
    (r'\bATN2\s*\(',                             r'ATAN2(',                         'ATN2→ATAN2'),
    (r'\bBEGIN\s+TRANSACTION\b',                 r'START TRANSACTION',              'BEGIN TRANSACTION→START TRANSACTION'),
    (r'\bBEGIN\s+TRAN\b',                        r'START TRANSACTION',              'BEGIN TRAN→START TRANSACTION'),
    (r'\bCOMMIT\s+TRANSACTION\b',                r'COMMIT',                         'COMMIT TRANSACTION→COMMIT'),
    (r'\bCOMMIT\s+TRAN\b',                       r'COMMIT',                         'COMMIT TRAN→COMMIT'),
    (r'\bROLLBACK\s+TRANSACTION\b',              r'ROLLBACK',                       'ROLLBACK TRANSACTION→ROLLBACK'),
    (r'\bROLLBACK\s+TRAN\b',                     r'ROLLBACK',                       'ROLLBACK TRAN→ROLLBACK'),
    (r'\bSAVE\s+TRANSACTION\s+(\w+)',            r'SAVEPOINT \1',                   'SAVE TRANSACTION→SAVEPOINT'),
    (r'\bTHROW\s*;',                             r'RESIGNAL;',                      'THROW 재발생→RESIGNAL'),
    (r'ORDER BY\s+(.+?)\s+OFFSET\s+(\d+)\s+ROWS\s+FETCH\s+NEXT\s+(\d+)\s+ROWS\s+ONLY', r'ORDER BY \1 LIMIT \3 OFFSET \2', 'OFFSET FETCH→LIMIT'),
    (r'OFFSET\s+(\d+)\s+ROWS\s+FETCH\s+(?:NEXT|FIRST)\s+(\d+)\s+ROWS\s+ONLY', r'LIMIT \2 OFFSET \1', 'OFFSET FETCH→LIMIT OFFSET'),
    (r'\bTOP\s+(\d+)\b',                         r'/* TOP \1 → LIMIT */',           'TOP→LIMIT 안내'),
    (r'CREATE\s+TABLE\s+#(\w+)',                  r'CREATE TEMPORARY TABLE `\1`',    '#임시테이블→TEMPORARY'),
    (r'\bFETCH\s+NEXT\s+FROM\s+(\w+)\s+INTO',   r'FETCH \1 INTO',                  'FETCH NEXT FROM→FETCH'),
    (r'\bDEALLOCATE\s+\w+\s*;',                  r'',                               'DEALLOCATE 제거'),
    (r'\bEXEC\s+\[?(\w+)\]?\s*\(',               r'CALL `\1`(',                     'EXEC→CALL'),
    (r'\[([^\]]+)\]',                             r'`\1`',                          '대괄호→백틱'),
]

# sql_converter.py 업데이트
content = open(CONVERTER, encoding='utf-8').read()
bak = CONVERTER + '.' + datetime.now().strftime('%H%M%S') + '.bak'
shutil.copy2(CONVERTER, bak)
print(f'백업: {bak}')

# 규칙을 Python repr로 안전하게 변환
lines = []
for pat, rep, desc in CORE_RULES:
    lines.append(f'        ({repr(pat)}, {repr(rep)}, {repr(desc)}),')
rules_code = '\n'.join(lines)

new_section = f'    "mssql\u2192mysql": [\n{rules_code}\n    ],\n'

s = content.find('    "mssql\u2192mysql": [')
e = content.find('\n    ],\n', s) + 8

if s == -1:
    print('mssql→mysql 섹션 없음')
    exit(1)

new_content = content[:s] + new_section + content[e:]

try:
    ast.parse(new_content)
    print('문법 OK')
except SyntaxError as err:
    lines2 = new_content.split('\n')
    print(f'오류 {err.lineno}: {err.msg}')
    for i, l in enumerate(lines2[max(0,err.lineno-3):err.lineno+3], max(1,err.lineno-2)):
        print(f'{i}: {l}')
    exit(1)

open(CONVERTER, 'w', encoding='utf-8').write(new_content)
print(f'sql_converter.py 업데이트 완료 — mssql→mysql 규칙 {len(CORE_RULES)}개')
print('재시작: python -m uvicorn main:app --port 8000')
