"""
fix_all_objects.py
backend 폴더에서 실행: python fix_all_objects.py

한 번에 모두 수정:
1. create_job — src_port, tgt_port, objects, convert_objects 저장
2. _migrate_objects — MSSQL/MySQL/Oracle/PostgreSQL DDL 조회 및 양방향 변환
3. replace_engine_v2 — _connect_src/tgt, _get_columns, _fetch_batch, _ddl_* 교체
"""
import shutil, ast, re
from datetime import datetime

path = 'app/api/routes/jobs.py'
bak  = path + '.' + datetime.now().strftime('%H%M%S') + '.bak'
shutil.copy2(path, bak)
print(f'백업: {bak}')

content = open(path, encoding='utf-8').read()

# ══════════════════════════════════════════════════════════
# 1. create_job — 누락 필드 추가
# ══════════════════════════════════════════════════════════
OLD_CREATE = '''    j["src_host"]        = body.get("src_host","localhost")
    j["src_database"]    = body.get("src_database","")
    j["src_username"]    = body.get("src_username","root")
    j["src_password"]    = body.get("src_password","")
    j["tgt_host"]        = body.get("tgt_host","localhost")
    j["tgt_database"]    = body.get("tgt_database","target_db")
    j["tgt_username"]    = body.get("tgt_username","sa")
    j["tgt_password"]    = body.get("tgt_password","")
    j["tables"]          = body.get("tables",[])
    j["table_total"]     = len(j["tables"])
    j["batch_size"]      = body.get("batch_size",5000)
    j["truncate_target"] = body.get("truncate_target",False)
    j["create_table"]    = body.get("create_table",True)
    j["on_error"]        = body.get("on_error","skip")'''

NEW_CREATE = '''    j["src_host"]        = body.get("src_host","localhost")
    j["src_port"]        = body.get("src_port") or (1434 if body.get("src_db","mysql") in ("mssql","azure") else 3306)
    j["src_database"]    = body.get("src_database","")
    j["src_username"]    = body.get("src_username","root")
    j["src_password"]    = body.get("src_password","")
    j["tgt_host"]        = body.get("tgt_host","localhost")
    j["tgt_port"]        = body.get("tgt_port") or (1434 if body.get("tgt_db","mssql") in ("mssql","azure") else 3306)
    j["tgt_database"]    = body.get("tgt_database","target_db")
    j["tgt_username"]    = body.get("tgt_username","sa")
    j["tgt_password"]    = body.get("tgt_password","")
    j["tables"]          = body.get("tables",[])
    j["table_total"]     = len(j["tables"])
    raw_obj = body.get("objects") or {}
    j["objects"] = {
        "procedures": raw_obj.get("procedures",[]),
        "functions":  raw_obj.get("functions",[]),
        "triggers":   raw_obj.get("triggers",[]),
        "views":      raw_obj.get("views",[]),
    }
    j["convert_objects"] = body.get("convert_objects", True)
    j["batch_size"]      = body.get("batch_size",5000)
    j["truncate_target"] = body.get("truncate_target",False)
    j["create_table"]    = body.get("create_table",True)
    j["on_error"]        = body.get("on_error","skip")'''

if OLD_CREATE in content:
    content = content.replace(OLD_CREATE, NEW_CREATE)
    print('1. create_job 필드 추가 완료')
else:
    print('1. create_job 패턴 없음')

# ══════════════════════════════════════════════════════════
# 2. _migrate_objects 교체 (MSSQL 소스 지원)
# ══════════════════════════════════════════════════════════
OBJ_START = '\n    def _migrate_objects(self, src_conn, tgt_conn, objects: dict, do_convert: bool):'
OBJ_END   = '\n    def _migrate_table('
idx_obj_s = content.find(OBJ_START)
idx_obj_e = content.find(OBJ_END)

if idx_obj_s != -1 and idx_obj_e != -1:
    NEW_MIGRATE_OBJECTS = '''
    def _migrate_objects(self, src_conn, tgt_conn, objects: dict, do_convert: bool):
        """오브젝트 양방향 이관 — MSSQL/MySQL/Oracle/PostgreSQL"""
        import re as R
        src_db = self.job.get("src_db", "mysql")
        tgt_db = self.job.get("tgt_db", "mssql")
        src_dbname = self.job.get("src_database", "")
        is_src_mssql = src_db in ("mssql","azure")
        is_tgt_mssql = tgt_db in ("mssql","azure")
        is_src_mysql  = src_db in ("mysql","mariadb","aurora","tidb")
        is_tgt_mysql  = tgt_db in ("mysql","mariadb","aurora","tidb")
        cur = src_conn.cursor()
        ok = 0; fail = 0

        def get_ddl_mysql(t, n):
            try:
                if t in ("PROCEDURE","FUNCTION"):
                    cur.execute(f"SHOW CREATE {t} `{n}`")
                    row = cur.fetchone()
                    if not row: return ""
                    key = f"Create {t.capitalize()}"
                    return (row.get(key) or list(row.values())[2] or "") if isinstance(row,dict) else (row[2] if len(row)>2 else "")
                elif t == "TRIGGER":
                    cur.execute(f"SHOW CREATE TRIGGER `{n}`")
                    row = cur.fetchone()
                    if not row: return ""
                    return (row.get("SQL Original Statement") or list(row.values())[2] or "") if isinstance(row,dict) else (row[2] if len(row)>2 else "")
                elif t == "VIEW":
                    cur.execute(f"SHOW CREATE VIEW `{n}`")
                    row = cur.fetchone()
                    if not row: return ""
                    return (row.get("Create View") or list(row.values())[1] or "") if isinstance(row,dict) else (row[1] if len(row)>1 else "")
            except Exception as e:
                self._log("warn", f"[{n}] MySQL DDL 조회 실패: {e}")
            return ""

        def get_ddl_mssql(t, n):
            try:
                if t == "VIEW":
                    cur.execute("SELECT m.definition FROM sys.sql_modules m JOIN sys.views v ON m.object_id=v.object_id WHERE v.name=?", (n,))
                elif t == "TRIGGER":
                    cur.execute("SELECT m.definition FROM sys.sql_modules m JOIN sys.triggers tr ON m.object_id=tr.object_id WHERE tr.name=?", (n,))
                else:
                    cur.execute("SELECT m.definition FROM sys.sql_modules m JOIN sys.objects o ON m.object_id=o.object_id WHERE o.name=? AND o.type IN ('P','FN','IF','TF')", (n,))
                row = cur.fetchone()
                if not row: return ""
                return row[0] if not isinstance(row,dict) else row.get("definition","")
            except Exception as e:
                self._log("warn", f"[{n}] MSSQL DDL 조회 실패: {e}")
            return ""

        def get_ddl(t, n):
            if is_src_mssql: return get_ddl_mssql(t, n)
            return get_ddl_mysql(t, n)

        def m2ms(s):
            s = R.sub(r'DELIMITER\s+\S+[ \t]*\n?','',s,flags=R.IGNORECASE)
            s = R.sub(r'\$\$\s*$','',s,flags=R.MULTILINE)
            s = R.sub(r'DEFINER\s*=\s*`[^`]+`@`[^`]+`\s*','',s,flags=R.IGNORECASE)
            for kw in ('NOT DETERMINISTIC','CONTAINS SQL','READS SQL DATA','MODIFIES SQL DATA','NO SQL'):
                s = R.sub(r'\b'+kw.replace(' ',r'\s+')+r'\b','',s,flags=R.IGNORECASE)
            s = R.sub(r'\bSQL\s+SECURITY\s+\w+\b','',s,flags=R.IGNORECASE)
            s = R.sub(r"COMMENT\s+'[^']*'",'',s,flags=R.IGNORECASE)
            s = R.sub(r'`([^`]+)`',r'[\1]',s)
            s = R.sub(r'\bVARCHAR\b','NVARCHAR',s,flags=R.IGNORECASE)
            s = R.sub(r'\bDATETIME\b','DATETIME2(6)',s,flags=R.IGNORECASE)
            s = R.sub(r'\bTINYINT\(1\)','BIT',s)
            s = R.sub(r'\bNOW\(\)','GETDATE()',s,flags=R.IGNORECASE)
            s = R.sub(r'\bCURRENT_TIMESTAMP\b','GETDATE()',s,flags=R.IGNORECASE)
            s = R.sub(r'\bCURDATE\(\)','CAST(GETDATE() AS DATE)',s,flags=R.IGNORECASE)
            s = R.sub(r'\bIFNULL\s*\(','ISNULL(',s,flags=R.IGNORECASE)
            s = R.sub(r'\bSUBSTR\s*\(','SUBSTRING(',s,flags=R.IGNORECASE)
            if src_dbname:
                s = R.sub(r'\b'+R.escape(src_dbname)+r'\.\[?(\w+)\]?',r'[\1]',s,flags=R.IGNORECASE)
            return s

        def m2ms_proc(s):
            s = m2ms(s)
            s = R.sub(r'CREATE\s+(OR\s+REPLACE\s+)?(PROCEDURE|FUNCTION)\s+',r'CREATE OR ALTER \2 ',s,flags=R.IGNORECASE)
            def _p(m):
                d=m.group(1).upper();n_=m.group(2);t=m.group(3)
                return f'@{n_} {t}{"  OUTPUT" if d in ("OUT","INOUT") else ""}'
            s = R.sub(r'\b(IN|OUT|INOUT)\s+(\w+)\s+([\w()]+)',_p,s,flags=R.IGNORECASE)
            def _d(m):
                n_=m.group(1);t=m.group(2);dv=m.group(3)
                return f'DECLARE @{n_} {t}'+(f' = {dv}' if dv else '')
            s = R.sub(r'\bDECLARE\s+(\w+)\s+([\w()]+)(?:\s+DEFAULT\s+([^;]+))?',_d,s,flags=R.IGNORECASE)
            s = R.sub(r'\bSET\s+(?!@)(\w+)\s*=',r'SET @\1 =',s,flags=R.IGNORECASE)
            s = R.sub(r'\bIF\s+(.+?)\s+THEN\b',r'IF \1 BEGIN',s,flags=R.IGNORECASE)
            s = R.sub(r'\bELSEIF\s+(.+?)\s+THEN\b',r'END ELSE IF \1 BEGIN',s,flags=R.IGNORECASE)
            s = R.sub(r'\bELSE\b(?!\s+IF)','END ELSE BEGIN',s,flags=R.IGNORECASE)
            s = R.sub(r'\bEND\s+IF\b','END',s,flags=R.IGNORECASE)
            s = R.sub(r'\bWHILE\s+(.+?)\s+DO\b',r'WHILE \1 BEGIN',s,flags=R.IGNORECASE)
            s = R.sub(r'\bEND\s+WHILE\b','END',s,flags=R.IGNORECASE)
            s = R.sub(r'\bCALL\s+\[?(\w+)\]?\s*\(',r'EXEC [\1] (',s,flags=R.IGNORECASE)
            s = R.sub(r'\bCREATE\s+TEMPORARY\s+TABLE\s+\[?(\w+)\]?',r'CREATE TABLE #\1',s,flags=R.IGNORECASE)
            return s.strip()

        def m2ms_view(s):
            s = m2ms(s)
            s = R.sub(r'CREATE\s+(OR\s+REPLACE\s+)?VIEW\s+','CREATE OR ALTER VIEW ',s,flags=R.IGNORECASE)
            s = R.sub(r'\bLIMIT\s+\d+','/* LIMIT removed */',s,flags=R.IGNORECASE)
            return s.strip()

        def m2ms_trigger(s):
            s = m2ms(s)
            s = R.sub(r'\bNEW\.(\w+)',r'INSERTED.\1',s,flags=R.IGNORECASE)
            s = R.sub(r'\bOLD\.(\w+)',r'DELETED.\1',s,flags=R.IGNORECASE)
            def _h(m):
                nm=m.group(1);tm=m.group(2).upper();ev=m.group(3).upper();tb=m.group(4)
                ms_t='AFTER' if tm=='AFTER' else 'INSTEAD OF'
                return f'CREATE OR ALTER TRIGGER [{nm}]\nON [{tb}]\n{ms_t} {ev}\nAS\nBEGIN\n    SET NOCOUNT ON;'
            s = R.sub(
                r'CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+\[?(\w+)\]?\s+(BEFORE|AFTER)\s+(INSERT|UPDATE|DELETE)\s+ON\s+\[?(\w+)\]?\s+FOR\s+EACH\s+ROW',
                _h,s,flags=R.IGNORECASE)
            s = R.sub(r'\bIF\s+(.+?)\s+THEN\b',r'IF \1 BEGIN',s,flags=R.IGNORECASE)
            s = R.sub(r'\bEND\s+IF\b','END',s,flags=R.IGNORECASE)
            if not s.rstrip().upper().endswith('END'):
                s = s.rstrip()+'\nEND'
            return s.strip()

        def ms2m(s):
            s = R.sub(r'\[([^\]]+)\]',r'`\1`',s)
            s = R.sub(r'\bSET\s+NOCOUNT\s+ON\s*;?','',s,flags=R.IGNORECASE)
            s = R.sub(r'\bSET\s+NOCOUNT\s+OFF\s*;?','',s,flags=R.IGNORECASE)
            s = R.sub(r'\bWITH\s+\(NOLOCK\)','',s,flags=R.IGNORECASE)
            s = R.sub(r'\bNVARCHAR\s*\(MAX\)','LONGTEXT',s,flags=R.IGNORECASE)
            s = R.sub(r'\bNVARCHAR\b','VARCHAR',s,flags=R.IGNORECASE)
            s = R.sub(r'\bDATETIME2\s*\(\d+\)','DATETIME(6)',s,flags=R.IGNORECASE)
            s = R.sub(r'\bDATETIME2\b','DATETIME(6)',s,flags=R.IGNORECASE)
            s = R.sub(r'\bGETDATE\(\)','NOW()',s,flags=R.IGNORECASE)
            s = R.sub(r'\bISNULL\s*\(','IFNULL(',s,flags=R.IGNORECASE)
            s = R.sub(r'\bIIF\s*\(','IF(',s,flags=R.IGNORECASE)
            s = R.sub(r'\bTOP\s+(\d+)\b',r'/* TOP \1 */',s,flags=R.IGNORECASE)
            s = R.sub(r'\bIDENTITY\s*\(\d+,\s*\d+\)','AUTO_INCREMENT',s,flags=R.IGNORECASE)
            s = R.sub(r'\bMONEY\b','DECIMAL(19,4)',s,flags=R.IGNORECASE)
            return s

        def ms2m_proc(s):
            s = ms2m(s)
            s = R.sub(r'@(\w+)',r'\1',s)
            s = R.sub(r'CREATE\s+OR\s+ALTER\s+(PROCEDURE|FUNCTION)',r'CREATE OR REPLACE \1',s,flags=R.IGNORECASE)
            s = R.sub(r'\bEXEC\s+`?(\w+)`?\s*\(',r'CALL `\1`(',s,flags=R.IGNORECASE)
            return s.strip()

        def ms2m_view(s):
            s = ms2m(s)
            s = R.sub(r'CREATE\s+OR\s+ALTER\s+VIEW','CREATE OR REPLACE VIEW',s,flags=R.IGNORECASE)
            s = R.sub(r'\bOFFSET\s+\d+\s+ROWS\s+FETCH\s+NEXT\s+(\d+)\s+ROWS\s+ONLY',r'LIMIT \1',s,flags=R.IGNORECASE)
            return s.strip()

        def ms2m_trigger(s):
            s = ms2m(s)
            s = R.sub(r'\bINSERTED\.(\w+)',r'NEW.\1',s,flags=R.IGNORECASE)
            s = R.sub(r'\bDELETED\.(\w+)',r'OLD.\1',s,flags=R.IGNORECASE)
            def _h(m):
                nm=m.group(1);tb=m.group(2);tm=m.group(3);ev=m.group(4)
                return f'CREATE OR REPLACE TRIGGER `{nm}`\n{tm.upper()} {ev.upper()}\nON `{tb}`\nFOR EACH ROW\nBEGIN'
            s = R.sub(
                r'CREATE\s+(?:OR\s+ALTER\s+)?TRIGGER\s+`?(\w+)`?\s+ON\s+`?(\w+)`?\s+(AFTER|INSTEAD\s+OF)\s+(INSERT|UPDATE|DELETE)\s+AS\s+BEGIN',
                _h,s,flags=R.IGNORECASE)
            return s.strip()

        def convert(ddl, obj_type):
            if not do_convert: return ddl
            try:
                if is_src_mysql and is_tgt_mssql:
                    if obj_type=="VIEW": return m2ms_view(ddl)
                    if obj_type=="TRIGGER": return m2ms_trigger(ddl)
                    return m2ms_proc(ddl)
                elif is_src_mssql and is_tgt_mysql:
                    if obj_type=="VIEW": return ms2m_view(ddl)
                    if obj_type=="TRIGGER": return ms2m_trigger(ddl)
                    return ms2m_proc(ddl)
                elif is_src_mysql and is_tgt_mysql:
                    ddl = R.sub(r'DEFINER\s*=\s*`[^`]+`@`[^`]+`\s*','',ddl,flags=R.IGNORECASE)
                    ddl = R.sub(r'DELIMITER\s+\S+[ \t]*\n?','',ddl,flags=R.IGNORECASE)
                    return ddl
                return ddl
            except Exception as e:
                self._log("warn", f"변환 경고 [{obj_type}]: {e}")
                return ddl

        def do_exec(ddl, obj_type, name):
            if not ddl or not ddl.strip():
                self._log("warn", f"[{name}] DDL 없음 — 건너뜀")
                return False
            converted = convert(ddl, obj_type)
            self._log("info", f"[{name}] {obj_type} 변환 완료 ({len(converted)}자)")
            try:
                tc = tgt_conn.cursor()
                if is_tgt_mssql:
                    tc.execute(converted); tgt_conn.commit()
                else:
                    if obj_type in ("PROCEDURE","FUNCTION","TRIGGER"):
                        tc.execute(converted); tgt_conn.commit()
                    else:
                        for stmt in [s.strip() for s in converted.split(';') if s.strip()]:
                            tc.execute(stmt)
                        tgt_conn.commit()
                self._log("info", f"✓ {obj_type} [{name}] 생성 완료")
                return True
            except Exception as e:
                self._log("error", f"✗ {obj_type} [{name}] 실패: {e}")
                return False

        order = [
            ("FUNCTION",  objects.get("functions")  or []),
            ("PROCEDURE", objects.get("procedures") or []),
            ("VIEW",      objects.get("views")      or []),
            ("TRIGGER",   objects.get("triggers")   or []),
        ]
        failed = []
        for obj_type, names in order:
            for name in names:
                if self._stop: break
                ddl = get_ddl(obj_type, name)
                if do_exec(ddl, obj_type, name):
                    ok += 1
                else:
                    failed.append((obj_type, name, ddl))
                    fail += 1

        if failed:
            self._log("info", f"재시도: {len(failed)}개")
            still = []
            for ot, nm, ddl in failed:
                if self._stop: break
                if do_exec(ddl, ot, nm):
                    ok += 1; fail -= 1
                else:
                    still.append(f"{ot}:{nm}")
            if still:
                self._log("warn", f"최종 실패: {still}")

        self._log("info", f"오브젝트 이관 완료 — 성공 {ok}, 실패 {fail}")

'''
    content = content[:idx_obj_s] + NEW_MIGRATE_OBJECTS + content[idx_obj_e:]
    print('2. _migrate_objects 교체 완료 (MSSQL 소스 지원)')
else:
    print(f'2. _migrate_objects 범위 탐색 실패 (start={idx_obj_s}, end={idx_obj_e})')

# ══════════════════════════════════════════════════════════
# 3. _connect_src ~ _create_mssql_table 교체 (replace_engine_v2)
# ══════════════════════════════════════════════════════════
START = '\n    def _connect_src(self):'
END   = '\n    def stop(self):'

idx_start = content.find(START)
idx_end   = content.find(END)

if idx_start != -1 and idx_end != -1:
    print(f'3. 교체 범위: {idx_start} ~ {idx_end} ({idx_end-idx_start} bytes)')

    ENGINE_BLOCK = r'''
    def _connect_src(self):
        j = self.job
        db_type = j.get("src_db", "mysql")
        host    = j.get("src_host", "")
        port    = int(j.get("src_port") or (1434 if db_type in ("mssql","azure") else 3306))
        user    = j.get("src_username", "")
        pw      = j.get("src_password", "")
        db      = j.get("src_database", "")
        self._log("info", f"소스 연결: {db_type}://{host}:{port}/{db}")
        try:
            if db_type in ("mssql", "azure"):
                from app.core.db_conn import make_mssql_conn
                return make_mssql_conn(host, port, user, pw, db)
            elif db_type in ("postgresql", "redshift"):
                import psycopg2
                return psycopg2.connect(host=host, port=port, user=user,
                                        password=pw, dbname=db, connect_timeout=10)
            else:
                import pymysql
                return pymysql.connect(
                    host=host, port=port, user=user, password=pw,
                    database=db, charset="utf8mb4", connect_timeout=10,
                    cursorclass=pymysql.cursors.DictCursor
                )
        except Exception as e:
            self._log("error", f"소스 연결 실패: {e}")
            return None

    def _connect_tgt(self):
        j = self.job
        db_type = j.get("tgt_db", "mssql")
        host    = j.get("tgt_host", "")
        port    = int(j.get("tgt_port") or (1434 if db_type in ("mssql","azure") else 3306))
        user    = j.get("tgt_username", "")
        pw      = j.get("tgt_password", "")
        db      = j.get("tgt_database", "")
        self._log("info", f"타겟 연결: {db_type}://{host}:{port}/{db}")
        try:
            if db_type in ("mssql", "azure"):
                from app.core.db_conn import make_mssql_conn
                return make_mssql_conn(host, port, user, pw, db)
            elif db_type in ("postgresql", "redshift"):
                import psycopg2
                return psycopg2.connect(host=host, port=port, user=user,
                                        password=pw, dbname=db, connect_timeout=10)
            else:
                import pymysql
                return pymysql.connect(
                    host=host, port=port, user=user, password=pw,
                    database=db, charset="utf8mb4", connect_timeout=10
                )
        except Exception as e:
            self._log("error", f"타겟 연결 실패: {e}")
            return None

    def _get_all_tables(self, src_conn) -> list:
        db_type = self.job.get("src_db", "mysql")
        cur = src_conn.cursor()
        try:
            if db_type in ("mssql", "azure"):
                cur.execute("""
                    SELECT t.name FROM sys.tables t
                    JOIN sys.schemas s ON t.schema_id=s.schema_id
                    WHERE s.name='dbo' ORDER BY t.name
                """)
                rows = cur.fetchall()
                return [r[0] if not isinstance(r, dict) else r["name"] for r in rows]
            elif db_type in ("postgresql", "redshift"):
                cur.execute("""
                    SELECT tablename FROM pg_tables
                    WHERE schemaname='public' ORDER BY tablename
                """)
                rows = cur.fetchall()
                return [r[0] if not isinstance(r, dict) else r["tablename"] for r in rows]
            else:
                cur.execute("""
                    SELECT TABLE_NAME FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'
                    ORDER BY TABLE_NAME
                """)
                rows = cur.fetchall()
                return [r["TABLE_NAME"] if isinstance(r, dict) else r[0] for r in rows]
        except Exception as e:
            self._log("error", f"테이블 목록 조회 실패: {e}")
            return []

    def _estimate_total_rows(self, src_conn, tables: list) -> int:
        db_type = self.job.get("src_db", "mysql")
        db      = self.job.get("src_database", "")
        cur = src_conn.cursor()
        total = 0
        for tbl in tables:
            try:
                if db_type in ("mssql", "azure"):
                    cur.execute(
                        "SELECT SUM(p.rows) FROM sys.tables t "
                        "JOIN sys.partitions p ON t.object_id=p.object_id "
                        "AND p.index_id IN(0,1) WHERE t.name=?", (tbl,)
                    )
                    r = cur.fetchone()
                    total += int(r[0] or 0) if r else 0
                elif db_type in ("postgresql", "redshift"):
                    cur.execute(
                        "SELECT reltuples::BIGINT FROM pg_class WHERE relname=%s", (tbl,)
                    )
                    r = cur.fetchone()
                    total += int(r[0] or 0) if r else 0
                else:
                    cur.execute(
                        "SELECT TABLE_ROWS FROM information_schema.TABLES "
                        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s", (db, tbl)
                    )
                    r = cur.fetchone()
                    val = (r["TABLE_ROWS"] if isinstance(r, dict) else r[0]) if r else 0
                    total += int(val or 0)
            except Exception:
                pass
        return total

    def _migrate_table(self, src_conn, tgt_conn, table: str) -> int:
        src_db_type = self.job.get("src_db", "mysql")
        tgt_db_type = self.job.get("tgt_db", "mssql")
        src_db      = self.job.get("src_database", "")
        src_cur = src_conn.cursor()
        cols = self._get_columns(src_cur, src_db_type, src_db, table)
        if not cols:
            raise Exception(f"[{table}] 컬럼 정보 없음")
        col_names = [c["COLUMN_NAME"] for c in cols]
        if self.job.get("create_table", True):
            try:
                self._create_target_table(tgt_conn, table, cols, src_db_type, tgt_db_type)
            except Exception as ce:
                self._log("error", f"[{table}] 생성 실패: {ce}")
                raise RuntimeError(f"CREATE TABLE [{table}] 실패: {ce}") from ce
        row_count = self._count_rows(src_cur, src_db_type, table)
        self.job["current_table_rows_total"] = row_count
        if row_count == 0:
            return 0
        if self.job.get("truncate_target", False):
            try:
                tc = tgt_conn.cursor()
                if tgt_db_type in ("mssql","azure"): tc.execute(f"TRUNCATE TABLE [{table}]")
                elif tgt_db_type in ("postgresql","redshift"): tc.execute(f'TRUNCATE TABLE "{table}"')
                else: tc.execute(f"TRUNCATE TABLE `{table}`")
                tgt_conn.commit()
            except Exception: pass
        tgt_cur = tgt_conn.cursor()
        has_identity = any(
            "auto_increment" in (c.get("EXTRA","") or "").lower() or c.get("is_identity")==1
            for c in cols
        )
        if tgt_db_type in ("mssql","azure"):
            if has_identity:
                try: tgt_cur.execute(f"SET IDENTITY_INSERT [{table}] ON")
                except Exception: pass
            cols_str = ", ".join(f"[{c}]" for c in col_names)
            placeholders = ", ".join("?" for _ in col_names)
            insert_sql = f"INSERT INTO [{table}] ({cols_str}) VALUES ({placeholders})"
        elif tgt_db_type in ("postgresql","redshift"):
            cols_str = ", ".join(f'"{c}"' for c in col_names)
            placeholders = ", ".join("%s" for _ in col_names)
            insert_sql = f'INSERT INTO "{table}" ({cols_str}) VALUES ({placeholders})'
        else:
            cols_str = ", ".join(f"`{c}`" for c in col_names)
            placeholders = ", ".join("%s" for _ in col_names)
            insert_sql = f"INSERT INTO `{table}` ({cols_str}) VALUES ({placeholders})"
        batch_size = self.job.get("batch_size", 5000)
        offset = 0; done = 0
        start_t = time.monotonic()
        while offset < row_count:
            if self._stop: break
            while self._pause: time.sleep(0.3)
            rows = self._fetch_batch(src_cur, src_db_type, table, col_names, batch_size, offset)
            if not rows: break
            batch_data = [
                tuple(r[c] if isinstance(r,dict) else r[i] for i,c in enumerate(col_names))
                for r in rows
            ]
            try:
                tgt_cur.executemany(insert_sql, batch_data)
                tgt_conn.commit()
            except Exception as e:
                self._log("error", f"배치 INSERT 실패 [{table}] offset={offset}: {str(e)[:200]}")
                try: tgt_conn.rollback()
                except Exception: pass
                if self.job.get("on_error") == "abort": raise
                self.job["rows_error"] += len(rows)
            done += len(rows); offset += batch_size
            self.job["current_table_rows_done"] = done
            elapsed = time.monotonic() - start_t
            if elapsed > 0: self.job["speed"] = int(done/elapsed)
            total = max(self.job.get("rows_total",1),1)
            self.job["progress"] = round((self.job.get("rows_processed",0)+done)/total*100,1)
        if tgt_db_type in ("mssql","azure") and has_identity:
            try: tgt_cur.execute(f"SET IDENTITY_INSERT [{table}] OFF")
            except Exception: pass
        return done

    def _get_columns(self, cur, db_type, db, table) -> list:
        try:
            if db_type in ("mssql","azure"):
                cur.execute("""
                    SELECT c.name AS COLUMN_NAME, tp.name AS DATA_TYPE, tp.name AS COLUMN_TYPE,
                           c.max_length AS CHARACTER_MAXIMUM_LENGTH,
                           c.precision AS NUMERIC_PRECISION, c.scale AS NUMERIC_SCALE,
                           CASE WHEN c.is_nullable=1 THEN 'YES' ELSE 'NO' END AS IS_NULLABLE,
                           NULL AS COLUMN_DEFAULT,
                           CASE WHEN ic.object_id IS NOT NULL THEN 'PRI' ELSE '' END AS COLUMN_KEY,
                           CASE WHEN c.is_identity=1 THEN 'auto_increment' ELSE '' END AS EXTRA
                    FROM sys.columns c
                    JOIN sys.types tp ON c.user_type_id=tp.user_type_id
                    JOIN sys.objects o ON c.object_id=o.object_id
                    LEFT JOIN sys.indexes i ON o.object_id=i.object_id AND i.is_primary_key=1
                    LEFT JOIN sys.index_columns ic
                        ON i.object_id=ic.object_id AND i.index_id=ic.index_id AND c.column_id=ic.column_id
                    WHERE o.name=? AND o.type='U' ORDER BY c.column_id
                """, (table,))
                raw = cur.fetchall()
                keys = ["COLUMN_NAME","DATA_TYPE","COLUMN_TYPE","CHARACTER_MAXIMUM_LENGTH",
                        "NUMERIC_PRECISION","NUMERIC_SCALE","IS_NULLABLE","COLUMN_DEFAULT","COLUMN_KEY","EXTRA"]
                return [dict(zip(keys,r)) for r in raw]
            elif db_type in ("postgresql","redshift"):
                cur.execute("""
                    SELECT column_name,data_type,data_type,character_maximum_length,
                           numeric_precision,numeric_scale,is_nullable,column_default,'',''
                    FROM information_schema.columns
                    WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position
                """, (table,))
                raw = cur.fetchall()
                keys = ["COLUMN_NAME","DATA_TYPE","COLUMN_TYPE","CHARACTER_MAXIMUM_LENGTH",
                        "NUMERIC_PRECISION","NUMERIC_SCALE","IS_NULLABLE","COLUMN_DEFAULT","COLUMN_KEY","EXTRA"]
                return [dict(zip(keys,r)) for r in raw]
            else:
                cur.execute("""
                    SELECT COLUMN_NAME,DATA_TYPE,COLUMN_TYPE,CHARACTER_MAXIMUM_LENGTH,
                           NUMERIC_PRECISION,NUMERIC_SCALE,IS_NULLABLE,COLUMN_DEFAULT,COLUMN_KEY,EXTRA
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION
                """, (db, table))
                return cur.fetchall()
        except Exception as e:
            self._log("error", f"[{table}] 컬럼 조회 실패: {e}")
            return []

    def _count_rows(self, cur, db_type, table) -> int:
        try:
            if db_type in ("mssql","azure"): cur.execute(f"SELECT COUNT(*) FROM [{table}]")
            elif db_type in ("postgresql","redshift"): cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            else: cur.execute(f"SELECT COUNT(*) AS cnt FROM `{table}`")
            r = cur.fetchone()
            if not r: return 0
            return int(r[0] if not isinstance(r,dict) else r.get("cnt", list(r.values())[0]))
        except Exception as e:
            self._log("warn", f"[{table}] row count 실패: {e}")
            return 0

    def _fetch_batch(self, cur, db_type, table, col_names, batch_size, offset) -> list:
        try:
            if db_type in ("mssql","azure"):
                cols_str = ", ".join(f"[{c}]" for c in col_names)
                cur.execute(
                    f"SELECT {cols_str} FROM [{table}] ORDER BY (SELECT NULL) "
                    f"OFFSET {offset} ROWS FETCH NEXT {batch_size} ROWS ONLY"
                )
                raw = cur.fetchall()
                return [dict(zip(col_names,r)) if not isinstance(r,dict) else r for r in raw]
            elif db_type in ("postgresql","redshift"):
                cols_str = ", ".join(f'"{c}"' for c in col_names)
                cur.execute(f'SELECT {cols_str} FROM "{table}" LIMIT {batch_size} OFFSET {offset}')
                raw = cur.fetchall()
                return [dict(zip(col_names,r)) if not isinstance(r,dict) else r for r in raw]
            else:
                cols_str = ", ".join(f"`{c}`" for c in col_names)
                cur.execute(f"SELECT {cols_str} FROM `{table}` LIMIT {batch_size} OFFSET {offset}")
                return cur.fetchall()
        except Exception as e:
            self._log("error", f"[{table}] SELECT 실패 offset={offset}: {e}")
            return []

    def _create_target_table(self, tgt_conn, table, cols, src_db, tgt_db):
        if tgt_db in ("mssql","azure"): self._ddl_mssql(tgt_conn,table,cols,src_db)
        elif tgt_db in ("postgresql","redshift"): self._ddl_postgresql(tgt_conn,table,cols,src_db)
        else: self._ddl_mysql(tgt_conn,table,cols,src_db)

    def _create_mssql_table(self, tgt_conn, table, cols):
        self._ddl_mssql(tgt_conn,table,cols,self.job.get("src_db","mysql"))

    _MSSQL_TO_MYSQL = {
        "int":"INT","bigint":"BIGINT","smallint":"SMALLINT","tinyint":"TINYINT",
        "float":"FLOAT","real":"FLOAT","decimal":"DECIMAL","numeric":"DECIMAL",
        "money":"DECIMAL(19,4)","smallmoney":"DECIMAL(10,4)","bit":"TINYINT(1)",
        "nvarchar":"VARCHAR","varchar":"VARCHAR","nchar":"CHAR","char":"CHAR",
        "ntext":"LONGTEXT","text":"LONGTEXT",
        "datetime":"DATETIME","datetime2":"DATETIME(6)","date":"DATE","time":"TIME",
        "smalldatetime":"DATETIME","datetimeoffset":"DATETIME(6)",
        "binary":"BINARY","varbinary":"VARBINARY(255)","image":"LONGBLOB",
        "uniqueidentifier":"CHAR(36)","xml":"LONGTEXT","geography":"TEXT","geometry":"TEXT",
    }
    _MYSQL_TO_MSSQL = {
        "int":"INT","bigint":"BIGINT","smallint":"SMALLINT","tinyint":"TINYINT",
        "mediumint":"INT","year":"SMALLINT","float":"FLOAT","double":"FLOAT",
        "decimal":"DECIMAL","numeric":"DECIMAL",
        "varchar":"NVARCHAR","char":"NCHAR","nvarchar":"NVARCHAR","nchar":"NCHAR",
        "text":"NVARCHAR(MAX)","tinytext":"NVARCHAR(500)","mediumtext":"NVARCHAR(MAX)","longtext":"NVARCHAR(MAX)",
        "datetime":"DATETIME2(6)","date":"DATE","time":"TIME","timestamp":"DATETIME2(6)",
        "blob":"VARBINARY(MAX)","tinyblob":"VARBINARY(MAX)","mediumblob":"VARBINARY(MAX)","longblob":"VARBINARY(MAX)",
        "binary":"BINARY","varbinary":"VARBINARY(MAX)",
        "bit":"BIT","bool":"BIT","boolean":"BIT","enum":"NVARCHAR(255)","set":"NVARCHAR(500)","json":"NVARCHAR(MAX)",
    }
    _MYSQL_TO_MYSQL = {
        "int":"INT","bigint":"BIGINT","smallint":"SMALLINT","tinyint":"TINYINT",
        "mediumint":"MEDIUMINT","year":"YEAR","float":"FLOAT","double":"DOUBLE",
        "decimal":"DECIMAL","numeric":"DECIMAL","varchar":"VARCHAR","char":"CHAR",
        "nvarchar":"VARCHAR","nchar":"CHAR","text":"TEXT","tinytext":"TINYTEXT",
        "mediumtext":"MEDIUMTEXT","longtext":"LONGTEXT","datetime":"DATETIME",
        "date":"DATE","time":"TIME","timestamp":"TIMESTAMP","blob":"BLOB",
        "tinyblob":"TINYBLOB","mediumblob":"MEDIUMBLOB","longblob":"LONGBLOB",
        "binary":"BINARY","varbinary":"VARBINARY","bit":"BIT",
        "bool":"TINYINT(1)","boolean":"TINYINT(1)","enum":"VARCHAR(255)","set":"VARCHAR(500)","json":"JSON",
    }

    def _resolve_mysql_type(self, c, src_db):
        raw=( c.get("DATA_TYPE") or "varchar").lower().strip()
        full=(c.get("COLUMN_TYPE") or raw).lower()
        ln=c.get("CHARACTER_MAXIMUM_LENGTH"); p=c.get("NUMERIC_PRECISION"); s=c.get("NUMERIC_SCALE")
        m=self._MSSQL_TO_MYSQL if src_db in ("mssql","azure") else self._MYSQL_TO_MYSQL
        if raw in ("nvarchar","varchar","char","nchar"):
            base={"nvarchar":"VARCHAR","varchar":"VARCHAR","nchar":"CHAR","char":"CHAR"}.get(raw,"VARCHAR")
            if ln and int(ln)>0 and int(ln)<=16383: return f"{base}({int(ln)})"
            return "TEXT" if not ln or int(ln)<0 else f"{base}(255)"
        if raw in ("decimal","numeric"): return f"DECIMAL({int(p) if p else 18},{int(s) if s else 4})"
        if raw=="datetime2": return "DATETIME(6)"
        if raw in ("varbinary","binary"):
            if not ln or int(ln)<0: return "LONGBLOB"
            return f"VARBINARY({min(int(ln),65535)})"
        if "unsigned" in full:
            k=raw+" unsigned"
            if k in m: return m[k]
        if raw=="tinyint" and "(1)" in full: return "TINYINT(1)"
        return m.get(raw,"TEXT")

    def _resolve_mssql_type(self, c, src_db):
        raw=(c.get("DATA_TYPE") or "varchar").lower().strip()
        full=(c.get("COLUMN_TYPE") or raw).lower()
        ln=c.get("CHARACTER_MAXIMUM_LENGTH"); p=c.get("NUMERIC_PRECISION"); s=c.get("NUMERIC_SCALE")
        m=self._MYSQL_TO_MSSQL
        if raw in ("nvarchar","varchar","char","nchar"):
            base={"nvarchar":"NVARCHAR","varchar":"NVARCHAR","nchar":"NCHAR","char":"NCHAR"}.get(raw,"NVARCHAR")
            if not ln or int(ln)<0: return f"{base}(MAX)"
            return f"{base}({min(int(ln),4000)})"
        if raw in ("decimal","numeric"): return f"DECIMAL({int(p) if p else 18},{int(s) if s else 4})"
        if raw in ("varbinary","binary"):
            if not ln or int(ln)<0: return "VARBINARY(MAX)"
            return f"VARBINARY({min(int(ln),8000)})"
        if raw=="datetime2": return "DATETIME2(6)"
        if raw=="tinyint" and "(1)" in full: return "BIT"
        if "unsigned" in full:
            k=raw+" unsigned"
            if k in m: return m[k]
        return m.get(raw,"NVARCHAR(500)")

    def _ddl_mysql(self, conn, table, cols, src_db):
        col_defs=[]; pk_cols=[]
        for c in cols:
            nm=c["COLUMN_NAME"]; extra=(c.get("EXTRA") or "").lower()
            is_pk=c.get("COLUMN_KEY","")=="PRI"; is_ai="auto_increment" in extra or c.get("is_identity")==1
            null=c.get("IS_NULLABLE","YES")=="YES" and not is_pk; ns="NULL" if null else "NOT NULL"
            if is_pk: pk_cols.append(nm)
            if is_ai: col_defs.append(f"  `{nm}` INT NOT NULL AUTO_INCREMENT"); continue
            t=self._resolve_mysql_type(c,src_db); col_defs.append(f"  `{nm}` {t} {ns}")
        if pk_cols:
            pk_str="`, `".join(pk_cols); col_defs.append(f"  PRIMARY KEY (`{pk_str}`)")
        if not col_defs: return
        lines=[f"CREATE TABLE IF NOT EXISTS `{table}` ("]
        lines.extend(col_defs[i]+("," if i<len(col_defs)-1 else "") for i in range(len(col_defs)))
        lines.append(") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci")
        ddl="\n".join(lines)
        self._log("info",f"[{table}] MySQL DDL ({len(cols)}컬럼)")
        cur=conn.cursor(); cur.execute(ddl); conn.commit()
        self._log("info",f"[{table}] 생성 완료 ✓")

    def _ddl_mssql(self, conn, table, cols, src_db):
        col_defs=[]; pk_cols=[]
        for c in cols:
            nm=c["COLUMN_NAME"]; extra=(c.get("EXTRA") or "").lower()
            is_pk=c.get("COLUMN_KEY","")=="PRI"; is_ai="auto_increment" in extra or c.get("is_identity")==1
            null=c.get("IS_NULLABLE","YES")=="YES" and not is_pk; ns="NULL" if null else "NOT NULL"
            if is_pk: pk_cols.append(nm)
            if is_ai: col_defs.append(f"  [{nm}] INT IDENTITY(1,1) NOT NULL"); continue
            t=self._resolve_mssql_type(c,src_db); col_defs.append(f"  [{nm}] {t} {ns}")
        if pk_cols:
            pk_str="], [".join(pk_cols); col_defs.append(f"  CONSTRAINT [PK_{table}] PRIMARY KEY ([{pk_str}])")
        if not col_defs: return
        lines=[f"IF OBJECT_ID(N'[dbo].[{table}]', N'U') IS NULL",f"CREATE TABLE [dbo].[{table}] ("]
        lines.extend(col_defs[i]+("," if i<len(col_defs)-1 else "") for i in range(len(col_defs)))
        lines.append(")")
        ddl="\n".join(lines)
        self._log("info",f"[{table}] MSSQL DDL ({len(cols)}컬럼)")
        cur=conn.cursor(); cur.execute(ddl); conn.commit()
        self._log("info",f"[{table}] 생성 완료 ✓")

    def _ddl_postgresql(self, conn, table, cols, src_db):
        PG_MAP={"int":"INTEGER","bigint":"BIGINT","smallint":"SMALLINT","tinyint":"SMALLINT",
                "float":"REAL","double":"DOUBLE PRECISION","decimal":"NUMERIC","numeric":"NUMERIC",
                "nvarchar":"VARCHAR","varchar":"VARCHAR","char":"CHAR","nchar":"CHAR",
                "text":"TEXT","longtext":"TEXT","mediumtext":"TEXT","tinytext":"TEXT",
                "datetime":"TIMESTAMP","datetime2":"TIMESTAMP","date":"DATE","time":"TIME",
                "timestamp":"TIMESTAMPTZ","blob":"BYTEA","longblob":"BYTEA","varbinary":"BYTEA",
                "bit":"BOOLEAN","bool":"BOOLEAN","boolean":"BOOLEAN","json":"JSONB","jsonb":"JSONB"}
        col_defs=[]; pk_cols=[]
        for c in cols:
            nm=c["COLUMN_NAME"]; extra=(c.get("EXTRA") or "").lower()
            is_pk=c.get("COLUMN_KEY","")=="PRI"; is_ai="auto_increment" in extra or c.get("is_identity")==1
            null=c.get("IS_NULLABLE","YES")=="YES" and not is_pk; ns="" if null else " NOT NULL"
            if is_pk: pk_cols.append(nm)
            if is_ai: col_defs.append(f'  "{nm}" SERIAL'); continue
            raw=(c.get("DATA_TYPE") or "varchar").lower()
            ln=c.get("CHARACTER_MAXIMUM_LENGTH"); p=c.get("NUMERIC_PRECISION"); s=c.get("NUMERIC_SCALE")
            if raw in ("varchar","nvarchar","char","nchar"):
                base="VARCHAR" if "var" in raw else "CHAR"
                t=f"{base}({int(ln)})" if ln and int(ln)>0 else "TEXT"
            elif raw in ("decimal","numeric"):
                t=f"NUMERIC({int(p) if p else 18},{int(s) if s else 4})"
            else: t=PG_MAP.get(raw,"TEXT")
            col_defs.append(f'  "{nm}" {t}{ns}')
        if pk_cols:
            pk_str='", "'.join(pk_cols); col_defs.append(f'  PRIMARY KEY ("{pk_str}")')
        if not col_defs: return
        lines=[f'CREATE TABLE IF NOT EXISTS "{table}" (']
        lines.extend(col_defs[i]+("," if i<len(col_defs)-1 else "") for i in range(len(col_defs)))
        lines.append(")")
        ddl="\n".join(lines)
        self._log("info",f"[{table}] PostgreSQL DDL ({len(cols)}컬럼)")
        cur=conn.cursor(); cur.execute(ddl); conn.commit()
        self._log("info",f"[{table}] 생성 완료 ✓")

'''
    content = content[:idx_start] + ENGINE_BLOCK + content[idx_end:]
    print('3. MigrationEngine 코어 교체 완료')
else:
    print(f'3. 코어 범위 탐색 실패 (start={idx_start}, end={idx_end})')

# ══════════════════════════════════════════════════════════
# 문법 확인 및 저장
# ══════════════════════════════════════════════════════════
try:
    ast.parse(content)
    print('✓ 문법 OK')
except SyntaxError as e:
    lines = content.split('\n')
    print(f'✗ 문법 오류 {e.lineno}: {e.msg}')
    for i, ln in enumerate(lines[max(0,e.lineno-3):e.lineno+3], max(1,e.lineno-2)):
        print(f'{i}: {ln}')
    print(f'복구: copy {bak} {path}')
    exit(1)

open(path, 'w', encoding='utf-8').write(content)

chk = content
print('\n=== 검증 ===')
print('src_port 저장:', 'src_port' in content)
print('objects 저장:', '"objects"' in content)
print('MSSQL DDL 조회:', 'sys.sql_modules' in content)
print('FETCH NEXT:', 'FETCH NEXT' in content)
print('_ddl_mysql:', 'def _ddl_mysql' in content)
print('make_mssql_conn:', 'make_mssql_conn' in content)
print('남은 port=3306:', content.count('port=3306'), '개')
print('\n완료! 재시작:')
print('python -m uvicorn main:app --port 8000')
