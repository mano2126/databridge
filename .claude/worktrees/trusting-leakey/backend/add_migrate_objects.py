"""
add_migrate_objects.py
backend 폴더에서 실행: python add_migrate_objects.py

MigrationEngine에 _migrate_objects 메서드를 추가합니다.
(ENGINE_BLOCK 교체 시 삭제된 메서드 복원)
"""
import shutil, ast
from datetime import datetime

path = 'app/api/routes/jobs.py'
bak  = path + '.' + datetime.now().strftime('%H%M%S') + '.bak'
shutil.copy2(path, bak)

content = open(path, encoding='utf-8').read()

# 이미 있으면 스킵
if 'def _migrate_objects' in content:
    print('_migrate_objects 이미 존재 — 스킵')
else:
    print('_migrate_objects 없음 — 추가')

# _migrate_objects 위치: _migrate_table 바로 앞에 삽입
INSERT_BEFORE = '\n    def _migrate_table('
idx = content.find(INSERT_BEFORE)
if idx == -1:
    print('오류: _migrate_table 을 찾을 수 없음')
    exit(1)

NEW_METHOD = '''
    def _migrate_objects(self, src_conn, tgt_conn, objects: dict, do_convert: bool):
        """오브젝트 양방향 이관 — MSSQL/MySQL 소스 지원"""
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
            s = R.sub(r"DEFINER\s*=\s*`[^`]+`@`[^`]+`\s*","",s,flags=R.IGNORECASE)
            for kw in ("NOT DETERMINISTIC","CONTAINS SQL","READS SQL DATA","MODIFIES SQL DATA","NO SQL"):
                s = R.sub(r"\b"+kw.replace(" ",r"\s+")+r"\b","",s,flags=R.IGNORECASE)
            s = R.sub(r"SQL\s+SECURITY\s+\w+","",s,flags=R.IGNORECASE)
            s = R.sub(r"COMMENT\s+\x27[^\x27]*\x27","",s,flags=R.IGNORECASE)
            s = R.sub(r"DELIMITER\s+\S+\s*","",s,flags=R.IGNORECASE)
            s = s.replace("$$","")
            s = R.sub(r"`([^`]+)`",r"[\1]",s)
            s = R.sub(r"\bVARCHAR\b","NVARCHAR",s,flags=R.IGNORECASE)
            s = R.sub(r"\bDATETIME\b","DATETIME2(6)",s,flags=R.IGNORECASE)
            s = R.sub(r"\bTINYINT\(1\)","BIT",s)
            s = R.sub(r"\bNOW\(\)","GETDATE()",s,flags=R.IGNORECASE)
            s = R.sub(r"\bCURRENT_TIMESTAMP\b","GETDATE()",s,flags=R.IGNORECASE)
            s = R.sub(r"\bIFNULL\s*\(","ISNULL(",s,flags=R.IGNORECASE)
            s = R.sub(r"\bSUBSTR\s*\(","SUBSTRING(",s,flags=R.IGNORECASE)
            if src_dbname:
                s = R.sub(r"\b"+R.escape(src_dbname)+r"\.\[?(\w+)\]?",r"[\1]",s,flags=R.IGNORECASE)
            return s

        def m2ms_proc(s):
            s = m2ms(s)
            s = R.sub(r"CREATE\s+(OR\s+REPLACE\s+)?(PROCEDURE|FUNCTION)\s+",r"CREATE OR ALTER \2 ",s,flags=R.IGNORECASE)
            def _p(m):
                d,n_,t = m.group(1).upper(),m.group(2),m.group(3)
                return "@"+n_+" "+t+(" OUTPUT" if d in ("OUT","INOUT") else "")
            s = R.sub(r"\b(IN|OUT|INOUT)\s+(\w+)\s+([\w()]+)",_p,s,flags=R.IGNORECASE)
            s = R.sub(r"\bDECLARE\s+(\w+)\s+([\w()]+)",r"DECLARE @\1 \2",s,flags=R.IGNORECASE)
            s = R.sub(r"\bSET\s+(?!@)(\w+)\s*=",r"SET @\1 =",s,flags=R.IGNORECASE)
            s = R.sub(r"\bIF\s+(.+?)\s+THEN\b",r"IF \1 BEGIN",s,flags=R.IGNORECASE)
            s = R.sub(r"\bELSEIF\s+(.+?)\s+THEN\b",r"END ELSE IF \1 BEGIN",s,flags=R.IGNORECASE)
            s = R.sub(r"\bELSE\b(?!\s+IF)","END ELSE BEGIN",s,flags=R.IGNORECASE)
            s = R.sub(r"\bEND\s+IF\b","END",s,flags=R.IGNORECASE)
            s = R.sub(r"\bWHILE\s+(.+?)\s+DO\b",r"WHILE \1 BEGIN",s,flags=R.IGNORECASE)
            s = R.sub(r"\bEND\s+WHILE\b","END",s,flags=R.IGNORECASE)
            s = R.sub(r"\bCALL\s+\[?(\w+)\]?\s*\(",r"EXEC [\1] (",s,flags=R.IGNORECASE)
            s = R.sub(r"\bCREATE\s+TEMPORARY\s+TABLE\s+\[?(\w+)\]?",r"CREATE TABLE #\1",s,flags=R.IGNORECASE)
            return s.strip()

        def m2ms_view(s):
            s = m2ms(s)
            s = R.sub(r"CREATE\s+(OR\s+REPLACE\s+)?VIEW\s+","CREATE OR ALTER VIEW ",s,flags=R.IGNORECASE)
            s = R.sub(r"\bLIMIT\s+\d+","/* LIMIT removed */",s,flags=R.IGNORECASE)
            return s.strip()

        def m2ms_trigger(s):
            s = m2ms(s)
            s = R.sub(r"\bNEW\.(\w+)",r"INSERTED.\1",s,flags=R.IGNORECASE)
            s = R.sub(r"\bOLD\.(\w+)",r"DELETED.\1",s,flags=R.IGNORECASE)
            def _h(m):
                nm,tm,ev,tb = m.group(1),m.group(2).upper(),m.group(3).upper(),m.group(4)
                timing = "AFTER" if tm=="AFTER" else "INSTEAD OF"
                return ("CREATE OR ALTER TRIGGER ["+nm+"]\nON ["+tb+"]\n"+timing+" "+ev+"\nAS\nBEGIN\n    SET NOCOUNT ON;")
            s = R.sub(
                r"CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+\[?(\w+)\]?\s+(BEFORE|AFTER)\s+(INSERT|UPDATE|DELETE)\s+ON\s+\[?(\w+)\]?\s+FOR\s+EACH\s+ROW",
                _h,s,flags=R.IGNORECASE)
            s = R.sub(r"\bIF\s+(.+?)\s+THEN\b",r"IF \1 BEGIN",s,flags=R.IGNORECASE)
            s = R.sub(r"\bEND\s+IF\b","END",s,flags=R.IGNORECASE)
            if not s.rstrip().upper().endswith("END"):
                s = s.rstrip()+"\nEND"
            return s.strip()

        def ms2m(s):
            s = R.sub(r"\[([^\]]+)\]",r"`\1`",s)
            s = R.sub(r"\bSET\s+NOCOUNT\s+ON\s*;?","",s,flags=R.IGNORECASE)
            s = R.sub(r"\bSET\s+NOCOUNT\s+OFF\s*;?","",s,flags=R.IGNORECASE)
            s = R.sub(r"\bNVARCHAR\s*\(MAX\)","LONGTEXT",s,flags=R.IGNORECASE)
            s = R.sub(r"\bNVARCHAR\b","VARCHAR",s,flags=R.IGNORECASE)
            s = R.sub(r"\bDATETIME2\s*\(\d+\)","DATETIME(6)",s,flags=R.IGNORECASE)
            s = R.sub(r"\bGETDATE\(\)","NOW()",s,flags=R.IGNORECASE)
            s = R.sub(r"\bISNULL\s*\(","IFNULL(",s,flags=R.IGNORECASE)
            s = R.sub(r"\bIIF\s*\(","IF(",s,flags=R.IGNORECASE)
            s = R.sub(r"\bIDENTITY\s*\(\d+,\s*\d+\)","AUTO_INCREMENT",s,flags=R.IGNORECASE)
            s = R.sub(r"\bMONEY\b","DECIMAL(19,4)",s,flags=R.IGNORECASE)
            return s

        def ms2m_proc(s):
            s = ms2m(s)
            s = R.sub(r"@(\w+)",r"\1",s)
            s = R.sub(r"CREATE\s+OR\s+ALTER\s+(PROCEDURE|FUNCTION)",r"CREATE OR REPLACE \1",s,flags=R.IGNORECASE)
            s = R.sub(r"\bEXEC\s+`?(\w+)`?\s*\(",r"CALL `\1`(",s,flags=R.IGNORECASE)
            return s.strip()

        def ms2m_view(s):
            s = ms2m(s)
            s = R.sub(r"CREATE\s+OR\s+ALTER\s+VIEW","CREATE OR REPLACE VIEW",s,flags=R.IGNORECASE)
            s = R.sub(r"\bOFFSET\s+\d+\s+ROWS\s+FETCH\s+NEXT\s+(\d+)\s+ROWS\s+ONLY",r"LIMIT \1",s,flags=R.IGNORECASE)
            return s.strip()

        def ms2m_trigger(s):
            s = ms2m(s)
            s = R.sub(r"\bINSERTED\.(\w+)",r"NEW.\1",s,flags=R.IGNORECASE)
            s = R.sub(r"\bDELETED\.(\w+)",r"OLD.\1",s,flags=R.IGNORECASE)
            def _h(m):
                nm,tb,tm,ev = m.group(1),m.group(2),m.group(3),m.group(4)
                return ("CREATE OR REPLACE TRIGGER `"+nm+"`\n"+tm.upper()+" "+ev.upper()+"\nON `"+tb+"`\nFOR EACH ROW\nBEGIN")
            s = R.sub(
                r"CREATE\s+(?:OR\s+ALTER\s+)?TRIGGER\s+`?(\w+)`?\s+ON\s+`?(\w+)`?\s+(AFTER|INSTEAD\s+OF)\s+(INSERT|UPDATE|DELETE)\s+AS\s+BEGIN",
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
                    ddl = R.sub(r"DEFINER\s*=\s*`[^`]+`@`[^`]+`\s*","",ddl,flags=R.IGNORECASE)
                    ddl = R.sub(r"DELIMITER\s+\S+\s*","",ddl,flags=R.IGNORECASE)
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
                        for stmt in [s.strip() for s in converted.split(";") if s.strip()]:
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

new_content = content[:idx] + NEW_METHOD + content[idx:]

try:
    ast.parse(new_content)
    print('✓ 문법 OK')
except SyntaxError as e:
    lines = new_content.split('\n')
    print(f'✗ 문법 오류 {e.lineno}: {e.msg}')
    for i, ln in enumerate(lines[max(0,e.lineno-3):e.lineno+3], max(1,e.lineno-2)):
        print(f'{i}: {ln}')
    print(f'복구: copy {bak} {path}')
    exit(1)

open(path, 'w', encoding='utf-8').write(new_content)
print('_migrate_objects 추가 완료')
print('\n재시작:')
print('python -m uvicorn main:app --port 8000')
