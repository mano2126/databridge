"""
app/api/routes/sql_converter.py
SQL 쿼리 / DDL 파일 일괄 변환 API
소스 DB 방언(Dialect) → 타겟 DB 방언으로 변환
"""
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
        (r'IDENTITY\(\d+,\s*\d+\)',          'AUTO_INCREMENT',        'IDENTITY→AUTO_INCREMENT'),
        (r'\bNVARCHAR\s*\(MAX\)',            'LONGTEXT',              'NVARCHAR(MAX)→LONGTEXT'),
        (r'\bNVARCHAR\b',                    'VARCHAR',               'NVARCHAR→VARCHAR'),
        (r'\bNCHAR\b',                       'CHAR',                  'NCHAR→CHAR'),
        (r'\bVARBINARY\s*\(MAX\)',           'LONGBLOB',              'VARBINARY(MAX)→LONGBLOB'),
        (r'\bVARBINARY\b',                   'VARBINARY',             'VARBINARY OK'),
        (r'\bDATETIME2\s*\(\d+\)',           'DATETIME',              'DATETIME2→DATETIME'),
        (r'\bDATETIME2\b',                   'DATETIME',              'DATETIME2→DATETIME'),
        (r'\bBIT\b',                         'TINYINT(1)',            'BIT→TINYINT(1)'),
        (r'\[([^\]]+)\]',                    r'`\1`',                 '대괄호→백틱'),
        (r'\bGETDATE\(\)',                   'NOW()',                 'GETDATE()→NOW()'),
        (r'\bISNULL\s*\(',                   'IFNULL(',               'ISNULL→IFNULL'),
        (r'\bIIF\s*\(',                      'IF(',                   'IIF→IF('),
        (r'\bTOP\s+(\d+)\b',                r'-- TOP \1 → LIMIT \1 을 쿼리 끝으로 이동', 'TOP→LIMIT 안내'),
        (r'\bSTRING_AGG\s*\(',              'GROUP_CONCAT(',         'STRING_AGG→GROUP_CONCAT'),
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
            parts=[]; prev=0
            for (s2,e2,args) in hits:
                parts.append(result[prev:s2])
                if len(args)==3: parts.append(f"DATEDIFF({args[2]}, {args[1]})"); changes.append("DATEDIFF(unit,a,b)→DATEDIFF(b,a)"); warnings.append("⚠ DATEDIFF 인자 순서 변환 확인 필요")
                else:            parts.append(f"DATEDIFF({', '.join(args)})")
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
    max_rows = min(int(body.get("max_rows", 200)), 1000)

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
                    raw  = cur.fetchmany(max_rows)
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
                    raw  = cur.fetchmany(max_rows)
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

    src_result = run_query(src_sql, src_conn)
    tgt_result = run_query(tgt_sql, tgt_conn)

    # 결과 비교
    def compare(a, b):
        if not a["ok"] or not b["ok"]:
            return {"match": False, "reason": "실행 오류"}
        if a["row_count"] != b["row_count"]:
            return {"match": False, "reason": f"행 수 불일치 (소스:{a['row_count']} vs 타겟:{b['row_count']})"}
        if len(a["cols"]) != len(b["cols"]):
            return {"match": False, "reason": f"컬럼 수 불일치 (소스:{len(a['cols'])} vs 타겟:{len(b['cols'])})"}
        diff_rows = []
        for i, (ra, rb) in enumerate(zip(a["rows"], b["rows"])):
            row_diffs = []
            for j, (va, vb) in enumerate(zip(ra, rb)):
                # 숫자: 소수점 반올림 허용
                try:
                    if va is not None and vb is not None and abs(float(str(va)) - float(str(vb))) < 0.001:
                        continue
                except: pass
                # datetime: 1초 이내 오차 허용 (DB 간 정밀도 차이)
                try:
                    from datetime import datetime
                    def _parse_dt(v):
                        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'):
                            try: return datetime.strptime(str(v).strip(), fmt)
                            except: pass
                        return None
                    dta, dtb = _parse_dt(va), _parse_dt(vb)
                    if dta and dtb and abs((dta - dtb).total_seconds()) <= 1:
                        continue
                except: pass
                if str(va) != str(vb):
                    col_a = a["cols"][j] if j < len(a["cols"]) else str(j)
                    col_b = b["cols"][j] if j < len(b["cols"]) else str(j)
                    row_diffs.append({"col_src": col_a, "col_tgt": col_b, "src": str(va), "tgt": str(vb)})
            if row_diffs:
                diff_rows.append({"row": i+1, "diffs": row_diffs})
        if diff_rows:
            return {"match": False, "reason": f"{len(diff_rows)}개 행에서 값 불일치", "diff_rows": diff_rows[:20]}
        return {"match": True, "reason": "완전 일치"}

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

    prompt = (
        f"당신은 {src_name} → {tgt_name} SQL 변환 전문가입니다.\n"
        f"아래 {src_name} SQL 쿼리를 {tgt_name}에서 실행 가능하도록 정확히 변환하세요.\n\n"
        "변환 규칙:\n"
        f"- 모든 함수/문법을 {tgt_name} 표준으로 변환\n"
        "- DATE_FORMAT↔FORMAT, DATEDIFF 인자 순서, GETDATE()↔NOW() 등 정확히 변환\n"
        "- CTE, 윈도우 함수, 서브쿼리 구조 유지\n"
        "- 한글 별칭(AS 절) 그대로 유지\n"
        "- 원본 SQL의 로직/의미 완전히 동일하게 유지\n\n"
        f"원본 SQL ({src_name}):\n{sql[:4000]}\n\n"
        "JSON만 응답 (마크다운/코드블록 없이):\n"
        '{"converted":"변환된SQL","changes":["변경사항1","변경사항2"],"warnings":["주의사항"]}'
    )

    try:
        payload = _j.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 4000,
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
        parsed["method"] = "claude-ai"
        parsed["api_available"] = True
        return parsed

    except Exception as e:
        # AI 실패 시 규칙 기반 폴백
        result = convert_sql(sql, src_db, tgt_db)
        result["method"] = "rules_fallback"
        result["api_available"] = True
        result["ai_error"] = str(e)[:100]
        return result
