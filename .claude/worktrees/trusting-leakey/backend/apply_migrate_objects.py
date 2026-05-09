"""
apply_migrate_objects.py
backend 폴더에서 실행: python apply_migrate_objects.py

jobs.py 의 _migrate_objects 함수를 양방향 지원 버전으로 교체합니다.
- MySQL/MSSQL/Oracle/PostgreSQL 소스 DDL 조회
- MySQL↔MSSQL 양방향 변환
- 동일 DB 타입 간 정리
"""
import ast, shutil
from datetime import datetime

path = 'app/api/routes/jobs.py'
bak  = path + '.' + datetime.now().strftime('%H%M%S') + '.bak'
shutil.copy2(path, bak)
print(f'백업: {bak}')

content = open(path, encoding='utf-8').read()

start = content.find('\n    def _migrate_objects(self, src_conn, tgt_conn, objects: dict, do_convert: bool):')
end   = content.find('\n    def _migrate_table(self, src_conn, tgt_conn, table: str) -> int:')

if start == -1 or end == -1:
    print(f'오류: 함수 범위 탐색 실패 (start={start}, end={end})')
    exit(1)

NEW_FUNC = '''
    def _migrate_objects(self, src_conn, tgt_conn, objects: dict, do_convert: bool):
        """오브젝트(프로시저/함수/트리거/뷰) 양방향 이관 — MySQL/MSSQL/Oracle/PostgreSQL 지원"""
        import re as R
        src_db = self.job.get("src_db", "mysql")
        tgt_db = self.job.get("tgt_db", "mssql")
        src_dbname = self.job.get("src_database", "")
        is_src_mssql = src_db in ("mssql", "azure")
        is_tgt_mssql = tgt_db in ("mssql", "azure")
        is_src_mysql  = src_db in ("mysql","mariadb","aurora","tidb")
        is_tgt_mysql  = tgt_db in ("mysql","mariadb","aurora","tidb")
        cur = src_conn.cursor()
        ok = 0; fail = 0

        # ── DDL 조회 ──────────────────────────────────────────────
        def get_mysql(t, n):
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

        def get_mssql(t, n):
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

        def get_oracle(t, n):
            try:
                if t == "VIEW":
                    cur.execute("SELECT TEXT FROM ALL_VIEWS WHERE VIEW_NAME=:1", (n.upper(),))
                    row = cur.fetchone()
                    txt = (row[0] if not isinstance(row,dict) else row.get("TEXT","")) if row else ""
                    return f"CREATE OR REPLACE VIEW {n} AS {txt}" if txt else ""
                else:
                    cur.execute("SELECT TEXT FROM ALL_SOURCE WHERE NAME=:1 ORDER BY LINE", (n.upper(),))
                    rows = cur.fetchall()
                    if not rows: return ""
                    return "CREATE OR REPLACE " + "".join(r[0] if not isinstance(r,dict) else r.get("TEXT","") for r in rows)
            except Exception as e:
                self._log("warn", f"[{n}] Oracle DDL 조회 실패: {e}")
            return ""

        def get_pg(t, n):
            try:
                if t == "VIEW":
                    cur.execute("SELECT definition FROM pg_views WHERE viewname=%s", (n,))
                    row = cur.fetchone()
                    txt = (row[0] if not isinstance(row,dict) else row.get("definition","")) if row else ""
                    return f"CREATE OR REPLACE VIEW {n} AS {txt}" if txt else ""
                elif t == "TRIGGER":
                    cur.execute("SELECT pg_get_triggerdef(oid) FROM pg_trigger WHERE tgname=%s", (n,))
                    row = cur.fetchone()
                    return (row[0] if not isinstance(row,dict) else row.get("pg_get_triggerdef","")) if row else ""
                else:
                    cur.execute("SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname=%s", (n,))
                    row = cur.fetchone()
                    return (row[0] if not isinstance(row,dict) else row.get("pg_get_functiondef","")) if row else ""
            except Exception as e:
                self._log("warn", f"[{n}] PG DDL 조회 실패: {e}")
            return ""

        def get_ddl(t, n):
            if is_src_mssql:                       return get_mssql(t, n)
            if src_db == "oracle":                 return get_oracle(t, n)
            if src_db in ("postgresql","redshift"): return get_pg(t, n)
            return get_mysql(t, n)

        # ── MySQL → MSSQL 변환 ────────────────────────────────────
        def m2ms_common(s):
            s = R.sub(r'DELIMITER\s+\S+[ \t]*\n?', '', s, flags=R.IGNORECASE)
            s = R.sub(r'\$\$\s*$', '', s, flags=R.MULTILINE)
            s = R.sub(r'DEFINER\s*=\s*`[^`]+`@`[^`]+`\s*', '', s, flags=R.IGNORECASE)
            for kw in ('NOT DETERMINISTIC','CONTAINS SQL','READS SQL DATA','MODIFIES SQL DATA','NO SQL'):
                s = R.sub(r'\b' + kw.replace(' ',r'\s+') + r'\b', '', s, flags=R.IGNORECASE)
            s = R.sub(r'\bSQL\s+SECURITY\s+\w+\b', '', s, flags=R.IGNORECASE)
            s = R.sub(r"COMMENT\s+'[^']*'", '', s, flags=R.IGNORECASE)
            s = R.sub(r'`([^`]+)`', r'[\1]', s)
            s = R.sub(r'\bVARCHAR\b', 'NVARCHAR', s, flags=R.IGNORECASE)
            s = R.sub(r'\bDATETIME\b', 'DATETIME2(6)', s, flags=R.IGNORECASE)
            s = R.sub(r'\bTINYINT\(1\)', 'BIT', s)
            s = R.sub(r'\bNOW\(\)', 'GETDATE()', s, flags=R.IGNORECASE)
            s = R.sub(r'\bCURRENT_TIMESTAMP\b', 'GETDATE()', s, flags=R.IGNORECASE)
            s = R.sub(r'\bCURDATE\(\)', 'CAST(GETDATE() AS DATE)', s, flags=R.IGNORECASE)
            s = R.sub(r'\bIFNULL\s*\(', 'ISNULL(', s, flags=R.IGNORECASE)
            s = R.sub(r'\bSUBSTR\s*\(', 'SUBSTRING(', s, flags=R.IGNORECASE)
            if src_dbname:
                s = R.sub(r'\b' + R.escape(src_dbname) + r'\.\[?(\w+)\]?', r'[\1]', s, flags=R.IGNORECASE)
            return s

        def m2ms_proc(s, is_func=False):
            s = m2ms_common(s)
            s = R.sub(r'CREATE\s+(OR\s+REPLACE\s+)?(PROCEDURE|FUNCTION)\s+', r'CREATE OR ALTER \2 ', s, flags=R.IGNORECASE)
            def _p(m):
                d=m.group(1).upper(); n_=m.group(2); t=m.group(3)
                return f'@{n_} {t}{"  OUTPUT" if d in ("OUT","INOUT") else ""}'
            s = R.sub(r'\b(IN|OUT|INOUT)\s+(\w+)\s+([\w()]+)', _p, s, flags=R.IGNORECASE)
            def _d(m):
                n_=m.group(1); t=m.group(2); dv=m.group(3)
                return f'DECLARE @{n_} {t}' + (f' = {dv}' if dv else '')
            s = R.sub(r'\bDECLARE\s+(\w+)\s+([\w()]+)(?:\s+DEFAULT\s+([^;]+))?', _d, s, flags=R.IGNORECASE)
            s = R.sub(r'\bSET\s+(?!@)(\w+)\s*=', r'SET @\1 =', s, flags=R.IGNORECASE)
            s = R.sub(r'\bIF\s+(.+?)\s+THEN\b', r'IF \1 BEGIN', s, flags=R.IGNORECASE)
            s = R.sub(r'\bELSEIF\s+(.+?)\s+THEN\b', r'END ELSE IF \1 BEGIN', s, flags=R.IGNORECASE)
            s = R.sub(r'\bELSE\b(?!\s+IF)', 'END ELSE BEGIN', s, flags=R.IGNORECASE)
            s = R.sub(r'\bEND\s+IF\b', 'END', s, flags=R.IGNORECASE)
            s = R.sub(r'\bWHILE\s+(.+?)\s+DO\b', r'WHILE \1 BEGIN', s, flags=R.IGNORECASE)
            s = R.sub(r'\bEND\s+WHILE\b', 'END', s, flags=R.IGNORECASE)
            s = R.sub(r'\bCALL\s+\[?(\w+)\]?\s*\(', r'EXEC [\1] (', s, flags=R.IGNORECASE)
            s = R.sub(r'\bCREATE\s+TEMPORARY\s+TABLE\s+\[?(\w+)\]?', r'CREATE TABLE #\1', s, flags=R.IGNORECASE)
            return s.strip()

        def m2ms_view(s):
            s = m2ms_common(s)
            s = R.sub(r'CREATE\s+(OR\s+REPLACE\s+)?VIEW\s+', 'CREATE OR ALTER VIEW ', s, flags=R.IGNORECASE)
            s = R.sub(r'\bLIMIT\s+\d+', '/* LIMIT removed */', s, flags=R.IGNORECASE)
            return s.strip()

        def m2ms_trigger(s):
            s = m2ms_common(s)
            s = R.sub(r'\bNEW\.(\w+)', r'INSERTED.\1', s, flags=R.IGNORECASE)
            s = R.sub(r'\bOLD\.(\w+)', r'DELETED.\1', s, flags=R.IGNORECASE)
            def _h(m):
                nm=m.group(1); tm=m.group(2).upper(); ev=m.group(3).upper(); tb=m.group(4)
                ms_t = 'AFTER' if tm=='AFTER' else 'INSTEAD OF'
                return f'CREATE OR ALTER TRIGGER [{nm}]\nON [{tb}]\n{ms_t} {ev}\nAS\nBEGIN\n    SET NOCOUNT ON;'
            s = R.sub(
                r'CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+\[?(\w+)\]?\s+(BEFORE|AFTER)\s+(INSERT|UPDATE|DELETE)\s+ON\s+\[?(\w+)\]?\s+FOR\s+EACH\s+ROW',
                _h, s, flags=R.IGNORECASE)
            s = R.sub(r'\bIF\s+(.+?)\s+THEN\b', r'IF \1 BEGIN', s, flags=R.IGNORECASE)
            s = R.sub(r'\bEND\s+IF\b', 'END', s, flags=R.IGNORECASE)
            if not s.rstrip().upper().endswith('END'):
                s = s.rstrip() + '\nEND'
            return s.strip()

        # ── MSSQL → MySQL 변환 ────────────────────────────────────
        def ms2m_common(s):
            s = R.sub(r'\[([^\]]+)\]', r'`\1`', s)
            s = R.sub(r'\bSET\s+NOCOUNT\s+ON\s*;?', '', s, flags=R.IGNORECASE)
            s = R.sub(r'\bSET\s+NOCOUNT\s+OFF\s*;?', '', s, flags=R.IGNORECASE)
            s = R.sub(r'\bWITH\s+\(NOLOCK\)', '', s, flags=R.IGNORECASE)
            s = R.sub(r'\bNVARCHAR\s*\(MAX\)', 'LONGTEXT', s, flags=R.IGNORECASE)
            s = R.sub(r'\bVARCHAR\s*\(MAX\)', 'LONGTEXT', s, flags=R.IGNORECASE)
            s = R.sub(r'\bNVARCHAR\b', 'VARCHAR', s, flags=R.IGNORECASE)
            s = R.sub(r'\bDATETIME2\s*\(\d+\)', 'DATETIME(6)', s, flags=R.IGNORECASE)
            s = R.sub(r'\bDATETIME2\b', 'DATETIME(6)', s, flags=R.IGNORECASE)
            s = R.sub(r'\bGETDATE\(\)', 'NOW()', s, flags=R.IGNORECASE)
            s = R.sub(r'\bSYSDATETIME\(\)', 'NOW()', s, flags=R.IGNORECASE)
            s = R.sub(r'\bISNULL\s*\(', 'IFNULL(', s, flags=R.IGNORECASE)
            s = R.sub(r'\bIIF\s*\(', 'IF(', s, flags=R.IGNORECASE)
            s = R.sub(r'\bSTRING_AGG\s*\((.+?),(.+?)\)', r'GROUP_CONCAT(\1 SEPARATOR \2)', s, flags=R.IGNORECASE|R.DOTALL)
            s = R.sub(r'\bTOP\s+(\d+)\b', r'/* TOP \1 */', s, flags=R.IGNORECASE)
            s = R.sub(r'\bIDENTITY\s*\(\d+,\s*\d+\)', 'AUTO_INCREMENT', s, flags=R.IGNORECASE)
            s = R.sub(r'\bUNIQUEIDENTIFIER\b', 'CHAR(36)', s, flags=R.IGNORECASE)
            s = R.sub(r'\bMONEY\b', 'DECIMAL(19,4)', s, flags=R.IGNORECASE)
            return s

        def ms2m_proc(s, is_func=False):
            s = ms2m_common(s)
            s = R.sub(r'@(\w+)', r'\1', s)
            s = R.sub(r'CREATE\s+OR\s+ALTER\s+(PROCEDURE|FUNCTION)', r'CREATE OR REPLACE \1', s, flags=R.IGNORECASE)
            s = R.sub(r'\bEXEC\s+`?(\w+)`?\s*\(', r'CALL `\1`(', s, flags=R.IGNORECASE)
            return s.strip()

        def ms2m_view(s):
            s = ms2m_common(s)
            s = R.sub(r'CREATE\s+OR\s+ALTER\s+VIEW', 'CREATE OR REPLACE VIEW', s, flags=R.IGNORECASE)
            s = R.sub(r'\bOFFSET\s+\d+\s+ROWS\s+FETCH\s+NEXT\s+(\d+)\s+ROWS\s+ONLY', r'LIMIT \1', s, flags=R.IGNORECASE)
            return s.strip()

        def ms2m_trigger(s):
            s = ms2m_common(s)
            s = R.sub(r'\bINSERTED\.(\w+)', r'NEW.\1', s, flags=R.IGNORECASE)
            s = R.sub(r'\bDELETED\.(\w+)', r'OLD.\1', s, flags=R.IGNORECASE)
            def _h(m):
                nm=m.group(1); tb=m.group(2); tm=m.group(3); ev=m.group(4)
                return f'CREATE OR REPLACE TRIGGER `{nm}`\n{tm.upper()} {ev.upper()}\nON `{tb}`\nFOR EACH ROW\nBEGIN'
            s = R.sub(
                r'CREATE\s+(?:OR\s+ALTER\s+)?TRIGGER\s+`?(\w+)`?\s+ON\s+`?(\w+)`?\s+(AFTER|INSTEAD\s+OF)\s+(INSERT|UPDATE|DELETE)\s+AS\s+BEGIN',
                _h, s, flags=R.IGNORECASE)
            return s.strip()

        # ── 변환 라우터 ───────────────────────────────────────────
        def convert(ddl, obj_type):
            if not do_convert: return ddl
            try:
                if is_src_mysql and is_tgt_mssql:
                    if obj_type == "VIEW":     return m2ms_view(ddl)
                    if obj_type == "TRIGGER":  return m2ms_trigger(ddl)
                    if obj_type == "FUNCTION": return m2ms_proc(ddl, True)
                    return m2ms_proc(ddl)
                elif is_src_mssql and is_tgt_mysql:
                    if obj_type == "VIEW":     return ms2m_view(ddl)
                    if obj_type == "TRIGGER":  return ms2m_trigger(ddl)
                    if obj_type == "FUNCTION": return ms2m_proc(ddl, True)
                    return ms2m_proc(ddl)
                elif is_src_mysql and is_tgt_mysql:
                    ddl = R.sub(r'DEFINER\s*=\s*`[^`]+`@`[^`]+`\s*', '', ddl, flags=R.IGNORECASE)
                    ddl = R.sub(r'DELIMITER\s+\S+[ \t]*\n?', '', ddl, flags=R.IGNORECASE)
                    return ddl
                return ddl
            except Exception as e:
                self._log("warn", f"변환 경고 [{obj_type}]: {e}")
                return ddl

        # ── 타겟 실행 ─────────────────────────────────────────────
        def do_exec(ddl, obj_type, name):
            if not ddl or not ddl.strip():
                self._log("warn", f"[{name}] DDL 없음 — 건너뜀")
                return False
            converted = convert(ddl, obj_type)
            self._log("info", f"[{name}] {obj_type} 변환 완료 ({len(converted)}자)")
            try:
                tc = tgt_conn.cursor()
                if is_tgt_mssql:
                    tc.execute(converted)
                    tgt_conn.commit()
                else:
                    if obj_type in ("PROCEDURE","FUNCTION","TRIGGER"):
                        tc.execute(converted)
                        tgt_conn.commit()
                    else:
                        for stmt in [s.strip() for s in converted.split(';') if s.strip()]:
                            tc.execute(stmt)
                        tgt_conn.commit()
                self._log("info", f"✓ {obj_type} [{name}] 생성 완료")
                return True
            except Exception as e:
                self._log("error", f"✗ {obj_type} [{name}] 실패: {e}")
                return False

        # ── 이관 실행 ─────────────────────────────────────────────
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

new_content = content[:start] + NEW_FUNC + content[end:]

try:
    ast.parse(new_content)
    print('✓ 문법 OK')
except SyntaxError as e:
    print(f'✗ 문법 오류 {e.lineno}: {e.msg}')
    lines = new_content.split('\n')
    for i, l in enumerate(lines[max(0,e.lineno-3):e.lineno+3], max(1,e.lineno-2)):
        print(f'{i}: {l}')
    exit(1)

open(path, 'w', encoding='utf-8').write(new_content)
print('jobs.py 저장 완료')
print('백엔드 재시작: python -m uvicorn main:app --port 8000')
