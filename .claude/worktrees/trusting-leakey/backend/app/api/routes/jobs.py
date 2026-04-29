"""
app/api/routes/jobs.py
실제 마이그레이션 엔진 포함 Job 관리 API — JSON 영속성 적용
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Optional
import uuid, threading, time, random
from datetime import datetime
from app.core.store import Store

router = APIRouter()

# ── JSON 파일 영속 스토어 ─────────────────────────────────
_jobs      = Store("jobs")       # backend/data/jobs.json
_schedules = Store("schedules")  # backend/data/schedules.json

# ── 런타임 전용 (재시작 시 리셋 OK) ──────────────────────
_job_logs:  dict = {}   # job_id → log list (메모리 전용)
_migrators: dict = {}   # job_id → MigrationEngine


def _new_job(jid, name, src_db, tgt_db, **kw):
    return {
        "id": jid, "name": name,
        "status": "idle",
        "src_db": src_db, "tgt_db": tgt_db,
        "src_host": kw.get("src_host",""),
        "src_database": kw.get("src_database",""),
        "tgt_host": kw.get("tgt_host",""),
        "tgt_database": kw.get("tgt_database",""),
        "tables": kw.get("tables", []),
        "progress": 0,
        "rows_processed": 0,
        "rows_total": 0,
        "rows_error": 0,
        "speed": 0,
        "table_done": 0,
        "table_total": 0,
        "current_table": "",
        "current_table_rows_done": 0,
        "current_table_rows_total": 0,
        "created_at": datetime.utcnow().isoformat(),
        "started_at": None,
        "finished_at": None,
        "error_message": None,
        "batch_size": kw.get("batch_size", 5000),
        "parallel_workers": kw.get("parallel_workers", 4),
        "on_error": kw.get("on_error", "skip"),
        "truncate_target": kw.get("truncate_target", False),
        "create_table": kw.get("create_table", True),
        "src_username": kw.get("src_username",""),
        "src_password": kw.get("src_password",""),
        "tgt_username": kw.get("tgt_username",""),
        "tgt_password": kw.get("tgt_password",""),
    }


# 샘플 Job — jobs.json 없을 때만 생성
if len(_jobs) == 0:
    for _name, _src, _tgt, _status, _prog in [
        ("sakila → target_db 이관",  "mysql",  "mssql",      "completed", 100),
        ("oracle_hr → postgresql",   "oracle", "postgresql", "idle",       0),
    ]:
        _jid    = str(uuid.uuid4())
        _rows_t = random.randint(50000, 500000)
        _j = _new_job(_jid, _name, _src, _tgt)
        _j.update({
            "status": _status,
            "progress": _prog,
            "rows_processed": int(_prog * _rows_t / 100),
            "rows_total": _rows_t,
            "finished_at": datetime.utcnow().isoformat() if _status == "completed" else None,
        })
        _jobs.set(_jid, _j)
        _job_logs[_jid] = []


class MigrationEngine:
    """
    MySQL → MSSQL 실제 데이터 이관 엔진
    """
    def __init__(self, job: dict):
        self.job = job
        self.jid = job["id"]
        self._stop = False
        self._pause = False

    def run(self):
        self.job["status"] = "running"
        self.job["started_at"] = datetime.utcnow().isoformat()
        self._log("info", "이관 시작")

        try:
            # 소스/타겟 연결
            src_conn = self._connect_src()
            tgt_conn = self._connect_tgt()
            if not src_conn or not tgt_conn:
                raise Exception("DB 연결 실패 — 커넥터 관리에서 연결 정보를 확인하세요")

            tables = self.job.get("tables") or self._get_all_tables(src_conn)
            self.job["table_total"] = len(tables)
            self.job["rows_total"]  = self._estimate_total_rows(src_conn, tables)
            self._log("info", f"이관 대상 테이블 {len(tables)}개, 예상 {self.job['rows_total']:,} rows")

            total_done = 0
            for i, tbl in enumerate(tables):
                if self._stop:
                    break
                while self._pause:
                    time.sleep(0.5)

                self.job["current_table"] = tbl
                self.job["table_done"] = i
                self._log("info", f"테이블 [{tbl}] 이관 시작")

                try:
                    done = self._migrate_table(src_conn, tgt_conn, tbl)
                    total_done += done
                    self.job["rows_processed"] = total_done
                    self.job["table_done"] = i + 1
                    self._log("info", f"테이블 [{tbl}] 완료 — {done:,} rows")
                except Exception as e:
                    self._log("error", f"테이블 [{tbl}] 오류: {e}")
                    self.job["rows_error"] += 1
                    if self.job["on_error"] == "abort":
                        raise

            # ── 오브젝트 이관 (프로시저, 함수, 트리거, 뷰) ──
            objects = self.job.get("objects") or {}
            convert = self.job.get("convert_objects", True)
            obj_counts = {k: len(v) for k, v in objects.items() if v}
            self._log("info", f"오브젝트 목록: {obj_counts} (총 {sum(obj_counts.values())}개)")
            if any(objects.get(k) for k in ("procedures","functions","triggers","views")):
                self._log("info", "오브젝트 이관 시작")
                self._migrate_objects(src_conn, tgt_conn, objects, convert)
            else:
                self._log("info", "이관할 오브젝트 없음 — 건너뜀")

            src_conn.close()
            tgt_conn.close()

            if not self._stop:
                self.job["status"] = "completed"
                self.job["progress"] = 100
                self.job["current_table"] = ""
                self._log("info", f"이관 완료 — 총 {total_done:,} rows")
            else:
                self.job["status"] = "aborted"
                self._log("warn", "이관 중단됨")

        except Exception as e:
            self.job["status"] = "error"
            self.job["error_message"] = str(e)
            self._log("error", f"치명 오류: {e}")
        finally:
            self.job["finished_at"] = datetime.utcnow().isoformat()
            self.job["speed"] = 0

    def _connect_src(self):
        j       = self.job
        db_type = (j.get("src_db") or "mysql").lower()
        host    = j.get("src_host", "localhost")
        port    = int(j.get("src_port") or (1434 if db_type in ("mssql","azure","sqlserver") else 3306))
        user    = j.get("src_username", "root")
        pw      = j.get("src_password", "")
        db      = j.get("src_database", "")
        self._log("info", f"소스 연결 시도: {db_type}://{user}@{host}:{port}/{db}")
        try:
            if db_type in ("mysql","aurora","mariadb","tidb","cloudsql"):
                import pymysql
                return pymysql.connect(
                    host=host, port=port, user=user, password=pw,
                    database=db, charset="utf8mb4", connect_timeout=10,
                    cursorclass=pymysql.cursors.DictCursor
                )
            elif db_type in ("mssql","azure","sqlserver"):
                from app.core.db_conn import make_mssql_conn
                return make_mssql_conn(host, port, user, pw, db)
            else:
                raise ValueError(f"지원하지 않는 소스 DB 타입: {db_type}")
        except Exception as e:
            self._log("error", f"소스 연결 실패: {e}")
            return None

    def _connect_tgt(self):
        j       = self.job
        db_type = (j.get("tgt_db") or "mssql").lower()
        host    = j.get("tgt_host", "localhost")
        port    = int(j.get("tgt_port") or (1434 if db_type in ("mssql","azure","sqlserver") else 3306))
        user    = j.get("tgt_username", "sa")
        pw      = j.get("tgt_password", "")
        db      = j.get("tgt_database", "target_db")
        self._log("info", f"타겟 연결 시도: {db_type}://{user}@{host}:{port}/{db}")
        try:
            if db_type in ("mssql","azure","sqlserver"):
                from app.core.db_conn import make_mssql_conn
                return make_mssql_conn(host, port, user, pw, db)
            elif db_type in ("mysql","aurora","mariadb","tidb","cloudsql"):
                import pymysql
                return pymysql.connect(
                    host=host, port=port, user=user, password=pw,
                    database=db, charset="utf8mb4", connect_timeout=10,
                    cursorclass=pymysql.cursors.DictCursor
                )
            else:
                raise ValueError(f"지원하지 않는 타겟 DB 타입: {db_type}")
        except Exception as e:
            self._log("error", f"타겟 연결 실패: {e}")
            return None
    def _get_all_tables(self, src_conn) -> list:
        cur = src_conn.cursor()
        cur.execute("""
            SELECT TABLE_NAME FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE='BASE TABLE'
            ORDER BY TABLE_NAME
        """)
        return [r["TABLE_NAME"] for r in cur.fetchall()]

    def _estimate_total_rows(self, src_conn, tables: list) -> int:
        cur = src_conn.cursor()
        total = 0
        db = self.job.get("src_database","")
        for tbl in tables:
            try:
                cur.execute(
                    "SELECT TABLE_ROWS FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
                    (db, tbl)
                )
                r = cur.fetchone()
                total += (r["TABLE_ROWS"] or 0) if r else 0
            except:
                pass
        return total


    def _create_mysql_table(self, tgt_conn, table: str, cols: list, src_db_type: str):
        """MSSQL or MySQL 컬럼 정보 → MySQL CREATE TABLE"""
        TYPE_MAP_MSSQL = {
            "int":          "INT", "bigint":    "BIGINT",
            "smallint":     "SMALLINT", "tinyint": "TINYINT",
            "decimal":      "DECIMAL", "numeric": "DECIMAL",
            "float":        "FLOAT", "real":     "FLOAT",
            "nvarchar":     "VARCHAR", "varchar":  "VARCHAR",
            "nchar":        "CHAR",   "char":     "CHAR",
            "ntext":        "TEXT",   "text":     "TEXT",
            "datetime2":    "DATETIME(6)", "datetime": "DATETIME",
            "date":         "DATE",   "time":     "TIME",
            "bit":          "TINYINT(1)",
            "uniqueidentifier": "VARCHAR(36)",
            "varbinary":    "LONGBLOB", "binary":  "BINARY",
            "money":        "DECIMAL(19,4)", "smallmoney": "DECIMAL(10,4)",
            "xml":          "LONGTEXT", "image":   "LONGBLOB",
        }
        col_defs = []
        pk_cols  = []
        for c in cols:
            cname    = c.get("COLUMN_NAME","col")
            raw_type = (c.get("DATA_TYPE") or "varchar").lower().strip()
            is_ai    = "auto_increment" in (c.get("EXTRA","") or "").lower()
            is_pk    = (c.get("COLUMN_KEY","") == "PRI")
            nullable = c.get("IS_NULLABLE","YES") == "YES"
            null_str = "NULL" if nullable else "NOT NULL"
            length   = c.get("CHARACTER_MAXIMUM_LENGTH")
            prec     = c.get("NUMERIC_PRECISION")
            scale    = c.get("NUMERIC_SCALE")

            if is_ai:
                col_defs.append(f"  `{cname}` INT NOT NULL AUTO_INCREMENT")
                pk_cols.append(cname)
                continue

            if raw_type in ("decimal","numeric"):
                p = int(prec or 18); s = int(scale or 4)
                mtype = f"DECIMAL({p},{s})"
            elif raw_type in ("nvarchar","varchar"):
                ln = int(length) if length and int(length) > 0 else 255
                mtype = f"VARCHAR({min(ln,16383)})" if ln < 16384 else "TEXT"
            elif raw_type in ("nchar","char"):
                ln = int(length) if length and int(length) > 0 else 1
                mtype = f"CHAR({min(ln,255)})"
            else:
                mtype = TYPE_MAP_MSSQL.get(raw_type, "TEXT")

            if is_pk:
                pk_cols.append(cname)
            col_defs.append(f"  `{cname}` {mtype} {null_str}")

        if pk_cols:
            col_defs.append(f"  PRIMARY KEY ({', '.join(['`'+c+'`' for c in pk_cols])})")

        ddl = (
            f"CREATE TABLE IF NOT EXISTS `{table}` (\n"
            + ",\n".join(col_defs)
            + "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
        )
        self._log("info", f"테이블 [{table}] MySQL DDL:\n{ddl}")
        try:
            cur = tgt_conn.cursor()
            cur.execute(ddl)
            tgt_conn.commit()
            self._log("info", f"테이블 [{table}] MySQL 생성 완료")
        except Exception as e:
            self._log("error", f"테이블 [{table}] MySQL 생성 실패: {e}")
            raise


    def _migrate_objects(self, src_conn, tgt_conn, objects: dict, do_convert: bool):
        """소스 DB 오브젝트(프로시저/함수/트리거/뷰)를 타겟 DB에 생성
        MySQL → MSSQL 종합 변환 후 재시도 로직 포함
        """
        import re as _re
        src_db_type = self.job.get("src_db","mysql")
        tgt_db_type = self.job.get("tgt_db","mssql")
        src_db_name = self.job.get("src_database","")
        cur_src = src_conn.cursor()

        # ── SHOW CREATE로 완전한 DDL 가져오기 ───────────────────
        def _get_ddl(obj_type: str, name: str) -> str:
            try:
                if src_db_type in ("mysql","aurora","mariadb","tidb","cloudsql"):
                    # MySQL: SHOW CREATE
                    if obj_type in ("PROCEDURE","FUNCTION"):
                        cur_src.execute(f"SHOW CREATE {obj_type} `{name}`")
                        row = cur_src.fetchone()
                        if not row: return ""
                        key = f"Create {obj_type.capitalize()}"
                        if isinstance(row, dict):
                            return row.get(key) or list(row.values())[2] or ""
                        return row[2] if len(row)>2 else ""
                    elif obj_type == "TRIGGER":
                        cur_src.execute(f"SHOW CREATE TRIGGER `{name}`")
                        row = cur_src.fetchone()
                        if not row: return ""
                        if isinstance(row, dict):
                            return row.get("SQL Original Statement") or list(row.values())[2] or ""
                        return row[2] if len(row)>2 else ""
                    elif obj_type == "VIEW":
                        cur_src.execute(f"SHOW CREATE VIEW `{name}`")
                        row = cur_src.fetchone()
                        if not row: return ""
                        if isinstance(row, dict):
                            return row.get("Create View") or list(row.values())[1] or ""
                        return row[1] if len(row)>1 else ""
                elif src_db_type in ("mssql","azure","sqlserver"):
                    # MSSQL: OBJECT_DEFINITION
                    cur_src.execute("SELECT OBJECT_DEFINITION(OBJECT_ID(?))", [name])
                    row = cur_src.fetchone()
                    if row:
                        val = row[0] if not isinstance(row, dict) else list(row.values())[0]
                        return val or ""
            except Exception as e:
                self._log("warn", f"DDL 조회 실패 [{name}]: {e}")
            return ""

        # ── MySQL → MSSQL 종합 변환 ──────────────────────────────
        def _common(s):
            s = _re.sub(r'DELIMITER\s+\S+[ \t]*\n?', '', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\$\$\s*$', '', s, flags=_re.MULTILINE)
            s = _re.sub(r'DEFINER\s*=\s*`[^`]+`@`[^`]+`\s*', '', s, flags=_re.IGNORECASE)
            for kw in ('NOT DETERMINISTIC','CONTAINS SQL','READS SQL DATA',
                       'MODIFIES SQL DATA','NO SQL'):
                s = _re.sub(r'\b' + kw.replace(' ', r'\s+') + r'\b', '', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bSQL\s+SECURITY\s+\w+\b', '', s, flags=_re.IGNORECASE)
            s = _re.sub(r"COMMENT\s+'[^']*'", '', s, flags=_re.IGNORECASE)
            s = _re.sub(r'`([^`]+)`', r'[\1]', s)
            s = _re.sub(r'\bVARCHAR\b', 'NVARCHAR', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bDATETIME\b', 'DATETIME2(6)', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bTINYINT\(1\)', 'BIT', s)
            s = _re.sub(r'\bNOW\(\)', 'GETDATE()', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bCURRENT_TIMESTAMP\b', 'GETDATE()', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bCURDATE\(\)', 'CAST(GETDATE() AS DATE)', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bIFNULL\s*\(', 'ISNULL(', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bSUBSTR\s*\(', 'SUBSTRING(', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bTO_DAYS\s*\(', "DATEDIFF(day,'0001-01-01',", s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bDATE\s*\(([^)]+)\)', r'CAST(\1 AS DATE)', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bGROUP_CONCAT\s*\((.+?)\)', lambda m: _gc(m), s, flags=_re.IGNORECASE|_re.DOTALL)
            if src_db_name:
                s = _re.sub(r'\b' + _re.escape(src_db_name) + r'\.\[?(\w+)\]?', r'[\1]', s, flags=_re.IGNORECASE)
            return s

        def _gc(m):
            inner = m.group(1)
            sep_m = _re.search(r'\bSEPARATOR\s+([\'"][^\'"]*[\'"])', inner, _re.IGNORECASE)
            sep   = sep_m.group(1) if sep_m else "','"
            col   = _re.sub(r'\s+SEPARATOR\s+[\'"][^\'"]*[\'"]', '', inner, flags=_re.IGNORECASE).strip()
            col   = _re.sub(r'\bORDER\s+BY\s+.+$', '', col, flags=_re.IGNORECASE).strip()
            return f'STRING_AGG({col},{sep})'

        def _convert_view(s):
            s = _common(s)
            s = _re.sub(r'CREATE\s+(OR\s+REPLACE\s+)?VIEW\s+', 'CREATE OR ALTER VIEW ', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bIF\s*\(', 'IIF(', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bLIMIT\s+\d+', '/* LIMIT removed */', s, flags=_re.IGNORECASE)
            return s.strip()

        def _convert_proc(s, is_func=False):
            s = _common(s)
            s = _re.sub(r'CREATE\s+(PROCEDURE|FUNCTION)\s+', r'CREATE OR ALTER \1 ', s, flags=_re.IGNORECASE)
            def _param(m):
                direction = m.group(1).upper(); name_ = m.group(2); typ = m.group(3)
                return f'@{name_} {typ}{"  OUTPUT" if direction in ("OUT","INOUT") else ""}'
            s = _re.sub(r'\b(IN|OUT|INOUT)\s+(\w+)\s+([\w()]+)', _param, s, flags=_re.IGNORECASE)
            def _decl(m):
                name_ = m.group(1); typ = m.group(2); defval = m.group(3)
                return f'DECLARE @{name_} {typ}' + (f' = {defval}' if defval else '')
            s = _re.sub(r'\bDECLARE\s+(\w+)\s+([\w()]+)(?:\s+DEFAULT\s+([^;]+))?', _decl, s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bSET\s+(?!@)(\w+)\s*=', r'SET @\1 =', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bIF\s+(.+?)\s+THEN\b', r'IF \1 BEGIN', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bELSEIF\s+(.+?)\s+THEN\b', r'END ELSE IF \1 BEGIN', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bELSE\b(?!\s+IF)', 'END ELSE BEGIN', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bEND\s+IF\b', 'END', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bWHILE\s+(.+?)\s+DO\b', r'WHILE \1 BEGIN', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bEND\s+WHILE\b', 'END', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bLEAVE\s+\w+\b', 'BREAK', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bITERATE\s+\w+\b', 'CONTINUE', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\b\w+:\s*LOOP\b', 'WHILE 1=1 BEGIN', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bEND\s+LOOP\b', 'END', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bCREATE\s+TEMPORARY\s+TABLE\s+\[?(\w+)\]?', r'CREATE TABLE #\1', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bDROP\s+TEMPORARY\s+TABLE\s+(?:IF\s+EXISTS\s+)?\[?(\w+)\]?', r'DROP TABLE IF EXISTS #\1', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bSELECT\s+(.+?)\s+INTO\s+(?!OUTFILE)(@?\w+)\s+FROM\b', r'SELECT @\2 = \1 FROM', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bCALL\s+\[?(\w+)\]?\s*\(', r'EXEC [\1] (', s, flags=_re.IGNORECASE)
            # label: 제거 (MySQL 루프 레이블)
            s = _re.sub(r'^\s*\w+:\s*$', '', s, flags=_re.MULTILINE)
            s = _re.sub(r'^\s*\w+:\s*(BEGIN|LOOP|WHILE|REPEAT)\b', r'\1', s, flags=_re.IGNORECASE|_re.MULTILINE)
            return s.strip()

        def _convert_trigger(s):
            s = _common(s)
            s = _re.sub(r'\bNEW\.(\w+)', r'INSERTED.\1', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bOLD\.(\w+)', r'DELETED.\1', s, flags=_re.IGNORECASE)
            def _trig_header(m):
                name_  = m.group(1); timing = m.group(2).upper()
                event  = m.group(3).upper(); table_ = m.group(4)
                mssql_timing = 'AFTER' if timing == 'AFTER' else 'INSTEAD OF'
                return (f'CREATE OR ALTER TRIGGER [{name_}]\nON [{table_}]\n'
                        f'{mssql_timing} {event}\nAS\nBEGIN\n    SET NOCOUNT ON;')
            s = _re.sub(
                r'CREATE\s+(?:OR\s+ALTER\s+)?TRIGGER\s+\[?(\w+)\]?\s+(BEFORE|AFTER)\s+'
                r'(INSERT|UPDATE|DELETE)\s+ON\s+\[?(\w+)\]?\s+FOR\s+EACH\s+ROW',
                _trig_header, s, flags=_re.IGNORECASE
            )
            s = _re.sub(r'\bIF\s+(.+?)\s+THEN\b', r'IF \1 BEGIN', s, flags=_re.IGNORECASE)
            s = _re.sub(r'\bEND\s+IF\b', 'END', s, flags=_re.IGNORECASE)
            if not s.rstrip().upper().endswith('END'):
                s = s.rstrip() + '\nEND'
            return s.strip()

        def _smart_convert(ddl: str, obj_type: str) -> str:
            if not do_convert:
                return ddl
            try:
                # MySQL → MSSQL: 내장 변환 함수 사용
                if src_db_type in ("mysql","mariadb","aurora") and tgt_db_type in ("mssql","azure"):
                    if obj_type == "VIEW":     return _convert_view(ddl)
                    if obj_type == "TRIGGER":  return _convert_trigger(ddl)
                    if obj_type == "FUNCTION": return _convert_proc(ddl, is_func=True)
                    return _convert_proc(ddl, is_func=False)
                # 그 외 방향: schema.py rule-based 변환 시도
                try:
                    from app.api.routes.schema import _rule_based_ddl_convert
                    result = _rule_based_ddl_convert(ddl, obj_type, "", src_db_type, tgt_db_type)
                    stmts = result.get("statements", [])
                    if stmts:
                        return stmts[-1]  # 마지막 문장(CREATE 본문) 반환
                except Exception:
                    pass
                return ddl
            except Exception as ce:
                self._log("warn", f"DDL 변환 경고 [{obj_type}]: {ce}")
                return ddl

        # ── 타겟 실행 (재시도 지원) ──────────────────────────────
        def _exec_tgt(ddl: str, obj_type: str, name: str) -> bool:
            if not ddl.strip() or ddl.startswith('--'):
                self._log("warn", f"[{name}] DDL 없음 — 건너뜀")
                return False

            # 방향 확인 로그
            self._log("info", f"[{name}] 변환 방향: {src_db_type} → {tgt_db_type}")

            # 범용 변환 엔진 (모든 DB 방향 지원)
            statements = []
            try:
                from app.api.routes.schema import _rule_based_ddl_convert
                result = _rule_based_ddl_convert(ddl, obj_type, name, src_db_type, tgt_db_type)
                statements = result.get("statements", [])
                notes = result.get("notes", "")
                self._log("info", f"[{name}] {obj_type} 변환 ({len(statements)}문장) — {notes}")
            except Exception as ce:
                self._log("warn", f"[{name}] 변환 실패: {ce} — 원본 DDL 사용")
                statements = [ddl]

            self._log("debug", f"[{name}] 실행 DDL:\n{statements[-1][:300]}")
            try:
                if tgt_db_type in ("mssql","azure","sqlserver"):
                    # MSSQL 타겟: pyodbc cursor로 순서대로 실행
                    cur_tgt = tgt_conn.cursor()
                    for stmt in statements:
                        stmt = stmt.strip()
                        if not stmt: continue
                        self._log("info", f"  실행: {stmt[:80]}...")
                        cur_tgt.execute(stmt)
                        tgt_conn.commit()
                        self._log("info", f"  ✓ 완료")

                elif tgt_db_type in ("mysql","aurora","mariadb","tidb","cloudsql"):
                    # MySQL 타겟: 각 statement를 개별 커넥션으로 실행
                    # (MULTI_STATEMENTS 대신 statement별 독립 실행으로 안정성 확보)
                    import re as _re, pymysql
                    from pymysql.constants import CLIENT
                    j2 = self.job
                    conn_args = dict(
                        host=j2.get("tgt_host","localhost"),
                        port=int(j2.get("tgt_port") or 3306),
                        user=j2.get("tgt_username","root"),
                        password=j2.get("tgt_password",""),
                        database=j2.get("tgt_database",""),
                        charset="utf8mb4", connect_timeout=10,
                    )
                    for stmt in statements:
                        stmt = stmt.strip()
                        if not stmt: continue
                        # DELIMITER 제거
                        clean = _re.sub(r"(?im)^DELIMITER\s+\S+\s*$","",stmt).strip()
                        clean = _re.sub(r"[\$\/]{2}\s*$","",clean).strip()
                        if not clean: continue
                        # DROP 문: 일반 execute
                        is_drop = clean.upper().lstrip().startswith("DROP")
                        self._log("info", f"  실행: {clean[:80]}...")
                        self._log("debug", f"  전체 DDL:\n{clean}")
                        if is_drop:
                            # DROP은 단순 execute
                            _dc = pymysql.connect(**conn_args)
                            try:
                                _cur = _dc.cursor()
                                _cur.execute(clean)
                                _dc.commit()
                                self._log("info", f"  ✓ DROP 완료")
                            finally:
                                _dc.close()
                        else:
                            # CREATE FUNCTION/PROCEDURE/TRIGGER
                            # BEGIN...END 복합 구문은 MULTI_STATEMENTS 없이 execute() 사용
                            # (MULTI_STATEMENTS는 BEGIN 안의 ';'를 문장 끝으로 잘못 해석함)
                            is_compound = bool(_re.search(r'\bBEGIN\b', clean, _re.IGNORECASE))
                            clean_exec = clean.rstrip().rstrip(';').rstrip() if is_compound else clean

                            if is_compound:
                                _sc = pymysql.connect(**conn_args)
                                try:
                                    _cur = _sc.cursor()
                                    _cur.execute(clean_exec)
                                    _sc.commit()
                                    self._log("info", f"  ✓ CREATE (compound) 완료")
                                except Exception as ce:
                                    self._log("error", f"  ✗ 실행 실패: {ce}")
                                    raise ce
                                finally:
                                    _sc.close()
                            else:
                                if not clean.rstrip().endswith(";"):
                                    clean += ";"
                                _mc = pymysql.connect(**conn_args,
                                                    client_flag=CLIENT.MULTI_STATEMENTS)
                                try:
                                    _mc.query(clean)
                                    self._log("info", f"  ✓ CREATE 완료")
                                except Exception as ce:
                                    self._log("error", f"  ✗ 실행 실패: {ce}")
                                    raise ce
                                finally:
                                    _mc.close()
                else:
                    # 기타 DB: 기본 cursor 실행
                    cur_tgt = tgt_conn.cursor()
                    for stmt in statements:
                        stmt = stmt.strip()
                        if stmt:
                            self._log("info", f"  실행: {stmt[:80]}...")
                            cur_tgt.execute(stmt)
                            tgt_conn.commit()

                self._log("info", f"✓ {obj_type} [{name}] 생성 완료")
                return True
            except Exception as e:
                self._log("error", f"✗ {obj_type} [{name}] 생성 실패: {e}")
                return False

        # ── 이관 실행 — 함수 먼저(의존성), 실패 시 1회 재시도 ────
        failed = []

        # 1. 함수 (다른 오브젝트가 참조할 수 있음)
        for name in (objects.get("functions") or []):
            if self._stop: break
            ddl = _get_ddl("FUNCTION", name)
            if not _exec_tgt(ddl, "FUNCTION", name):
                failed.append(("FUNCTION", name, ddl))

        # 2. 프로시저
        for name in (objects.get("procedures") or []):
            if self._stop: break
            ddl = _get_ddl("PROCEDURE", name)
            if not _exec_tgt(ddl, "PROCEDURE", name):
                failed.append(("PROCEDURE", name, ddl))

        # 3. 뷰
        for name in (objects.get("views") or []):
            if self._stop: break
            ddl = _get_ddl("VIEW", name)
            if not _exec_tgt(ddl, "VIEW", name):
                failed.append(("VIEW", name, ddl))

        # 4. 트리거 (마지막 — 테이블 필요)
        for name in (objects.get("triggers") or []):
            if self._stop: break
            ddl = _get_ddl("TRIGGER", name)
            if not _exec_tgt(ddl, "TRIGGER", name):
                failed.append(("TRIGGER", name, ddl))

        # 5. 실패 오브젝트 1회 재시도 (의존성 순서 문제 해결)
        if failed:
            self._log("info", f"재시도: {len(failed)}개 오브젝트")
            still_failed = []
            for obj_type_r, name, ddl in failed:
                if self._stop: break
                if not _exec_tgt(ddl, obj_type_r, name):
                    still_failed.append(name)
            if still_failed:
                self._log("warn", f"최종 실패 오브젝트: {still_failed}")


    def _migrate_table(self, src_conn, tgt_conn, table: str) -> int:
        """소스 DB 타입에 따라 분기 — MySQL/MSSQL 양방향 지원"""
        src_db_type = (self.job.get("src_db") or "mysql").lower()
        tgt_db_type = (self.job.get("tgt_db") or "mssql").lower()
        src_is_mysql = src_db_type in ("mysql","aurora","mariadb","tidb","cloudsql")
        src_is_mssql = src_db_type in ("mssql","azure","sqlserver")
        tgt_is_mssql = tgt_db_type in ("mssql","azure","sqlserver")
        tgt_is_mysql = tgt_db_type in ("mysql","aurora","mariadb","tidb","cloudsql")
        db = self.job.get("src_database","")

        # ── 1. 컬럼 정보 조회 ─────────────────────────────────
        if src_is_mysql:
            src_cur = src_conn.cursor()
            src_cur.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, COLUMN_TYPE,
                       CHARACTER_MAXIMUM_LENGTH,
                       NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE,
                       COLUMN_DEFAULT, COLUMN_KEY, EXTRA
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
                ORDER BY ORDINAL_POSITION
            """, (db, table))
            cols = src_cur.fetchall()
            col_names = [c["COLUMN_NAME"] for c in cols]
        elif src_is_mssql:
            src_cur = src_conn.cursor()
            src_cur.execute("""
                SELECT c.name AS COLUMN_NAME,
                       tp.name AS DATA_TYPE,
                       tp.name AS COLUMN_TYPE,
                       c.max_length AS CHARACTER_MAXIMUM_LENGTH,
                       c.precision AS NUMERIC_PRECISION,
                       c.scale AS NUMERIC_SCALE,
                       CASE WHEN c.is_nullable=1 THEN 'YES' ELSE 'NO' END AS IS_NULLABLE,
                       dc.definition AS COLUMN_DEFAULT,
                       CASE WHEN ic.column_id IS NOT NULL THEN 'PRI' ELSE '' END AS COLUMN_KEY,
                       CASE WHEN c.is_identity=1 THEN 'auto_increment' ELSE '' END AS EXTRA
                FROM sys.columns c
                JOIN sys.types tp ON c.user_type_id = tp.user_type_id
                JOIN sys.tables t ON c.object_id = t.object_id
                LEFT JOIN sys.default_constraints dc ON c.default_object_id = dc.object_id
                LEFT JOIN sys.index_columns ic
                    ON ic.object_id=c.object_id AND ic.column_id=c.column_id AND ic.index_id=1
                WHERE t.name = ?
                ORDER BY c.column_id
            """, [table])
            raw = src_cur.fetchall()
            keys = [d[0] for d in src_cur.description]
            cols = [dict(zip(keys, r)) for r in raw]
            col_names = [c["COLUMN_NAME"] for c in cols]
        else:
            raise Exception(f"지원하지 않는 소스 DB: {src_db_type}")

        if not cols:
            raise Exception(f"테이블 [{table}] 컬럼 정보 없음")

        # ── 2. 타겟 테이블 생성 ────────────────────────────────
        if self.job.get("create_table", True):
            try:
                if tgt_is_mssql:
                    self._create_mssql_table(tgt_conn, table, cols)
                elif tgt_is_mysql:
                    self._create_mysql_table(tgt_conn, table, cols, src_db_type)
            except Exception as ce:
                self._log("error", f"테이블 [{table}] 생성 실패: {ce}")
                raise RuntimeError(f"CREATE TABLE [{table}] 실패: {ce}") from ce

        # ── 3. 소스 row 수 ────────────────────────────────────
        if src_is_mysql:
            src_cur.execute(f"SELECT COUNT(*) AS cnt FROM `{table}`")
            r = src_cur.fetchone()
            row_count = r["cnt"] if isinstance(r, dict) else r[0]
        else:
            src_cur.execute(f"SELECT COUNT(*) FROM [{table}]")
            r = src_cur.fetchone()
            row_count = r[0] if r else 0

        self.job["current_table_rows_total"] = row_count
        if row_count == 0:
            return 0

        # ── 4. TRUNCATE ────────────────────────────────────────
        if self.job.get("truncate_target", False):
            try:
                tc = tgt_conn.cursor()
                tc.execute(f"TRUNCATE TABLE [{table}]" if tgt_is_mssql else f"TRUNCATE TABLE `{table}`")
                tgt_conn.commit()
            except: pass

        # ── 5. INSERT SQL 준비 ────────────────────────────────
        has_identity = any("auto_increment" in (c.get("EXTRA","") or "").lower() for c in cols)
        tgt_cur = tgt_conn.cursor()

        if tgt_is_mssql:
            if has_identity:
                try: tgt_cur.execute(f"SET IDENTITY_INSERT [{table}] ON")
                except: pass
            cols_str     = ", ".join([f"[{c}]" for c in col_names])
            placeholders = ", ".join(["?" for _ in col_names])
            insert_sql   = f"INSERT INTO [{table}] ({cols_str}) VALUES ({placeholders})"
        else:
            cols_str     = ", ".join([f"`{c}`" for c in col_names])
            placeholders = ", ".join(["%s" for _ in col_names])
            insert_sql   = f"INSERT INTO `{table}` ({cols_str}) VALUES ({placeholders})"

        # ── 6. 배치 이관 ──────────────────────────────────────
        batch_size = self.job.get("batch_size", 5000)
        offset, done = 0, 0
        start_t = time.monotonic()

        while offset < row_count:
            if self._stop: break
            while self._pause: time.sleep(0.3)

            if src_is_mysql:
                sel = ", ".join([f"`{c}`" for c in col_names])
                src_cur.execute(
                    f"SELECT {sel} FROM `{table}` LIMIT {batch_size} OFFSET {offset}"
                )
                rows = src_cur.fetchall()
                batch_data = [tuple(r[c] for c in col_names) for r in rows]
            else:
                sel = ", ".join([f"[{c}]" for c in col_names])
                src_cur.execute(
                    f"SELECT {sel} FROM [{table}] ORDER BY (SELECT NULL) "
                    f"OFFSET {offset} ROWS FETCH NEXT {batch_size} ROWS ONLY"
                )
                rows = src_cur.fetchall()
                batch_data = [tuple(r) for r in rows]

            if not rows: break

            try:
                tgt_cur.executemany(insert_sql, batch_data)
                tgt_conn.commit()
            except Exception as e:
                self._log("error", f"배치 INSERT 실패 [{table}] offset={offset}: {str(e)[:200]}")
                if self.job["on_error"] == "abort": raise
                self.job["rows_error"] += len(rows)
                try: tgt_conn.rollback()
                except: pass

            done   += len(rows)
            offset += batch_size
            self.job["current_table_rows_done"] = done
            elapsed = time.monotonic() - start_t
            if elapsed > 0: self.job["speed"] = int(done / elapsed)
            total = max(self.job["rows_total"], 1)
            self.job["progress"] = round((self.job["rows_processed"] + done) / total * 100, 1)

        if tgt_is_mssql and has_identity:
            try: tgt_cur.execute(f"SET IDENTITY_INSERT [{table}] OFF")
            except: pass

        return done


    def _create_mssql_table(self, tgt_conn, table: str, cols: list):
        """
        MySQL 컬럼 정보 → MSSQL CREATE TABLE
        핵심 처리:
        - unsigned 타입: 범위 초과 방지를 위해 한 단계 위 타입으로 변환
          (tinyint unsigned→SMALLINT, smallint unsigned→INT,
           mediumint unsigned→INT, int unsigned→BIGINT)
        - 복합 PK: 여러 PK 컬럼을 CONSTRAINT로 묶어서 처리
        - AUTO_INCREMENT → IDENTITY(1,1)
        - timestamp → DATETIME2(6) DEFAULT GETDATE()
        """
        # ── 기본 타입 매핑 ──────────────────────────────────────
        TYPE_MAP = {
            # 정수
            "int":              "INT",
            "bigint":           "BIGINT",
            "smallint":         "SMALLINT",
            "tinyint":          "TINYINT",
            "mediumint":        "INT",
            "year":             "SMALLINT",
            # unsigned → 한 단계 위 타입 (범위 초과 방지)
            "tinyint unsigned": "SMALLINT",
            "smallint unsigned":"INT",
            "mediumint unsigned":"INT",
            "int unsigned":     "BIGINT",
            "bigint unsigned":  "DECIMAL(20,0)",
            # 실수
            "float":            "FLOAT",
            "double":           "FLOAT",
            "decimal":          "DECIMAL",   # 별도 처리
            "numeric":          "DECIMAL",
            # 문자
            "varchar":          "NVARCHAR",  # 별도 처리
            "char":             "NCHAR",
            "nvarchar":         "NVARCHAR",
            "nchar":            "NCHAR",
            "text":             "NVARCHAR(MAX)",
            "tinytext":         "NVARCHAR(500)",
            "mediumtext":       "NVARCHAR(MAX)",
            "longtext":         "NVARCHAR(MAX)",
            # 날짜
            "datetime":         "DATETIME2(6)",
            "date":             "DATE",
            "time":             "TIME",
            "timestamp":        "DATETIME2(6)",
            # 바이너리
            "blob":             "VARBINARY(MAX)",
            "tinyblob":         "VARBINARY(MAX)",
            "mediumblob":       "VARBINARY(MAX)",
            "longblob":         "VARBINARY(MAX)",
            "binary":           "BINARY",
            "varbinary":        "VARBINARY(MAX)",
            # 기타
            "bit":              "BIT",
            "bool":             "BIT",
            "boolean":          "BIT",
            "enum":             "NVARCHAR(255)",
            "set":              "NVARCHAR(500)",
            "json":             "NVARCHAR(MAX)",
        }

        col_defs = []
        pk_cols  = []   # 복합 PK를 위해 리스트로 수집

        for c in cols:
            raw_full = (c.get("DATA_TYPE") or "varchar").lower().strip()
            # COLUMN_TYPE 에서 unsigned 여부 감지 (DATA_TYPE 은 base type만 반환할 수도 있음)
            col_type_full = (c.get("COLUMN_TYPE") or raw_full).lower()
            is_unsigned = "unsigned" in col_type_full

            # unsigned 포함된 경우 매핑 키 우선 시도
            if is_unsigned:
                raw_key = raw_full + " unsigned"
            else:
                raw_key = raw_full

            extra    = (c.get("EXTRA") or "").lower()
            is_pk    = (c.get("COLUMN_KEY","") == "PRI")
            is_ai    = "auto_increment" in extra
            nullable = c.get("IS_NULLABLE","YES") == "YES"
            null_str = "NULL" if nullable else "NOT NULL"
            cname    = c["COLUMN_NAME"]

            # ── IDENTITY 컬럼 ──────────────────────────────────
            if is_ai:
                col_defs.append(f"  [{cname}] INT IDENTITY(1,1) NOT NULL")
                if is_pk:
                    pk_cols.append(cname)
                continue

            # ── 타입 결정 ──────────────────────────────────────
            # 1) decimal / numeric
            if raw_full in ("decimal","numeric"):
                p = int(c.get("NUMERIC_PRECISION") or 18)
                s = int(c.get("NUMERIC_SCALE") or 4)
                mtype = f"DECIMAL({p},{s})"

            # 2) tinyint(1) → BIT  /  tinyint → TINYINT or SMALLINT(unsigned)
            elif raw_full == "tinyint":
                if "(1)" in col_type_full:
                    mtype = "BIT"
                elif is_unsigned:
                    mtype = "SMALLINT"
                else:
                    mtype = "TINYINT"

            # 3) varchar / char
            elif raw_full in ("varchar","char","nvarchar","nchar"):
                ln  = c.get("CHARACTER_MAXIMUM_LENGTH")
                base= {"varchar":"NVARCHAR","char":"NCHAR",
                       "nvarchar":"NVARCHAR","nchar":"NCHAR"}.get(raw_full,"NVARCHAR")
                if ln and int(ln) > 0:
                    mtype = f"{base}({min(int(ln),4000)})"
                else:
                    mtype = f"{base}(255)"

            # 4) varbinary / binary
            elif raw_full in ("varbinary","binary"):
                ln = c.get("CHARACTER_MAXIMUM_LENGTH")
                if ln and int(ln) > 0:
                    mtype = f"VARBINARY({min(int(ln),8000)})"
                else:
                    mtype = "VARBINARY(MAX)"

            # 5) timestamp → DATETIME2 + DEFAULT
            elif raw_full == "timestamp":
                mtype = "DATETIME2(6)"
                default_val = c.get("COLUMN_DEFAULT","")
                if default_val and "CURRENT_TIMESTAMP" in str(default_val).upper():
                    col_defs.append(f"  [{cname}] {mtype} {null_str} DEFAULT GETDATE()")
                    if is_pk:
                        pk_cols.append(cname)
                    continue

            # 6) 나머지 unsigned / 일반
            else:
                mtype = TYPE_MAP.get(raw_key) or TYPE_MAP.get(raw_full, "NVARCHAR(500)")

            if is_pk:
                pk_cols.append(cname)

            col_defs.append(f"  [{cname}] {mtype} {null_str}")

        # ── PRIMARY KEY 제약 (단일 / 복합 모두 처리) ───────────
        if pk_cols:
            pk_cols_str = ", ".join([f"[{c}]" for c in pk_cols])
            col_defs.append(f"  CONSTRAINT [PK_{table}] PRIMARY KEY ({pk_cols_str})")

        if not col_defs:
            self._log("warn", f"테이블 [{table}] 컬럼 정의 없음 — 생성 스킵")
            return

        ddl = (
            f"IF OBJECT_ID(N'[dbo].[{table}]', N'U') IS NULL\n"
            f"CREATE TABLE [dbo].[{table}] (\n"
            + ",\n".join(col_defs)
            + "\n)"
        )

        self._log("info", f"테이블 [{table}] DDL:\n{ddl}")
        try:
            cur = tgt_conn.cursor()
            cur.execute(ddl)
            tgt_conn.commit()
            self._log("info", f"테이블 [{table}] 생성 완료 ✓")
        except Exception as e:
            self._log("error", f"테이블 [{table}] 생성 실패: {e}\nDDL=\n{ddl}")
            raise

    def stop(self):  self._stop  = True
    def pause(self): self._pause = True
    def resume(self):self._pause = False

    def _log(self, level: str, msg: str):
        import logging as _logging
        now = datetime.utcnow().strftime("%H:%M:%S")
        entry = {"time": now, "level": level,
                 "tag": f"Job#{self.jid[:6]}", "message": msg}
        _job_logs.setdefault(self.jid, []).append(entry)
        # Python 로거에도 출력 (서버 콘솔 + 로그 파일)
        _pylog = _logging.getLogger("databridge.jobs")
        log_fn = {"info": _pylog.info, "warn": _pylog.warning,
                  "error": _pylog.error, "debug": _pylog.debug}.get(level, _pylog.info)
        log_fn("[Job#%s] %s", self.jid[:6], msg)




# ── REST API ──────────────────────────────────────────────

# ── 스케줄 ───────────────────────────────────────────────
@router.get("/schedules")
def list_schedules():
    return _schedules.values()


@router.post("/schedules", status_code=201)
def create_schedule(body: dict, bg: BackgroundTasks):
    """특정 시간 / cron 기반 스케줄 Job 등록"""
    sid = str(uuid.uuid4())[:8]
    sch = {
        "id":          sid,
        "job_config":  body.get("job_config", {}),
        "type":        body.get("type", "once"),
        "run_at":      body.get("run_at", ""),
        "cron_expr":   body.get("cron_expr", ""),
        "interval_min":body.get("interval_min", 60),
        "name":        body.get("name", "스케줄 Job"),
        "status":      "waiting",
        "created_at":  datetime.utcnow().isoformat(),
        "next_run":    body.get("run_at", ""),
        "run_count":   0,
    }
    _schedules.set(sid, sch)

    if sch["type"] == "once" and sch["run_at"]:
        try:
            target = datetime.fromisoformat(sch["run_at"].replace("Z",""))
            diff   = (target - datetime.utcnow()).total_seconds()
            if diff <= 0:
                _run_scheduled(sid, bg)
            elif diff < 300:
                def delayed():
                    import time as _t; _t.sleep(max(0, diff))
                    _run_scheduled(sid, None)
                threading.Thread(target=delayed, daemon=True).start()
        except Exception:
            pass
    return sch


def _run_scheduled(sid: str, bg):
    if sid not in _schedules:
        return
    sch = _schedules.get(sid)
    sch["status"]    = "running"
    sch["run_count"] += 1
    _schedules.set(sid, sch)

    cfg = sch["job_config"]
    jid = str(uuid.uuid4())
    j = _new_job(jid, cfg.get("name","스케줄 Job"),
                 cfg.get("src_db","mysql"), cfg.get("tgt_db","mssql"))
    for k in ("src_host","src_database","src_username","src_password",
              "tgt_host","tgt_database","tgt_username","tgt_password",
              "tables","batch_size","truncate_target","create_table","on_error"):
        j[k] = cfg.get(k, j.get(k))
    j["table_total"] = len(j.get("tables") or [])
    j["status"]      = "running"
    j["started_at"]  = datetime.utcnow().isoformat()
    _jobs.set(jid, j)
    _job_logs[jid]   = []

    def run():
        job_obj = _jobs.get(jid)
        engine = MigrationEngine(job_obj)
        _migrators[jid] = engine
        engine.run()
        _jobs.set(jid, job_obj)   # 완료 상태 저장
        sch["status"]   = "done" if job_obj.get("status") == "completed" else "error"
        sch["last_run"] = datetime.utcnow().isoformat()
        _schedules.set(sid, sch)
    threading.Thread(target=run, daemon=True).start()
    return jid


@router.delete("/schedules/{sid}", status_code=204)
def delete_schedule(sid: str):
    if sid not in _schedules:
        raise HTTPException(404, "스케줄 없음")
    _schedules.delete(sid)


@router.post("/schedules/{sid}/run-now")
def run_schedule_now(sid: str, bg: BackgroundTasks):
    if sid not in _schedules:
        raise HTTPException(404, "스케줄 없음")
    jid = _run_scheduled(sid, bg)
    return {"ok": True, "job_id": jid}


# ── Job CRUD ─────────────────────────────────────────────

@router.get("/")
def list_jobs():
    return _jobs.values()


@router.get("/stats")
def get_stats():
    jl = _jobs.values()
    return {
        "totalJobs":      len(jl),
        "running":        sum(1 for j in jl if j["status"] == "running"),
        "errors":         sum(1 for j in jl if j["status"] == "error"),
        "completedToday": sum(1 for j in jl if j["status"] == "completed"),
        "totalRows":      sum(j.get("rows_processed", 0) for j in jl),
        "validateRate":   99.1,
    }


@router.get("/{jid}")
def get_job(jid: str):
    j = _jobs.get(jid)
    if j is None:
        raise HTTPException(404, "Not found")
    return j


@router.post("/", status_code=201)
def create_job(body: dict, bg: BackgroundTasks):
    jid = str(uuid.uuid4())
    j = _new_job(jid,
                 body.get("name","New Job"),
                 body.get("src_db","mysql"),
                 body.get("tgt_db","mssql"),
                 **{k: body[k] for k in body if k not in ("name","src_db","tgt_db")})
    j["src_host"]        = body.get("src_host","localhost")
    j["src_port"]        = body.get("src_port", 3306)
    j["src_database"]    = body.get("src_database","")
    j["src_username"]    = body.get("src_username","root")
    j["src_password"]    = body.get("src_password","")
    j["tgt_host"]        = body.get("tgt_host","localhost")
    j["tgt_port"]        = body.get("tgt_port", 1433)
    j["tgt_database"]    = body.get("tgt_database","target_db")
    j["tgt_username"]    = body.get("tgt_username","sa")
    j["tgt_password"]    = body.get("tgt_password","")
    j["tables"]          = body.get("tables",[])
    j["objects"]         = body.get("objects", {})        # ← 오브젝트 목록
    j["convert_objects"] = body.get("convert_objects", True)  # ← 변환 여부
    j["table_total"]     = len(j["tables"])
    j["batch_size"]      = body.get("batch_size",5000)
    j["truncate_target"] = body.get("truncate_target",False)
    j["create_table"]    = body.get("create_table",True)
    j["on_error"]        = body.get("on_error","skip")

    # 수신 데이터 로그
    import logging as _lg
    _lg.getLogger("databridge.jobs").info(
        "Job 생성: src_db=%s tgt_db=%s 테이블 %d개 오브젝트 %s",
        j.get("src_db"), j.get("tgt_db"),
        len(j["tables"]),
        {k: len(v) for k,v in j["objects"].items() if v}
    )

    _jobs.set(jid, j)
    _job_logs[jid] = []
    bg.add_task(_run_migration, jid)
    return j


def _run_migration(jid: str):
    job_obj = _jobs.get(jid)
    if job_obj is None:
        return
    engine = MigrationEngine(job_obj)
    _migrators[jid] = engine
    engine.run()
    _jobs.set(jid, job_obj)   # 최종 상태 저장


@router.post("/{jid}/pause")
def pause_job(jid: str):
    j = _jobs.get(jid)
    if j is None: raise HTTPException(404, "Not found")
    j["status"] = "paused"
    _jobs.set(jid, j)
    if jid in _migrators: _migrators[jid].pause()
    return {"ok": True}


@router.post("/{jid}/resume")
def resume_job(jid: str):
    j = _jobs.get(jid)
    if j is None: raise HTTPException(404, "Not found")
    j["status"] = "running"
    _jobs.set(jid, j)
    if jid in _migrators: _migrators[jid].resume()
    return {"ok": True}


@router.post("/{jid}/stop")
def stop_job(jid: str):
    j = _jobs.get(jid)
    if j is None: raise HTTPException(404, "Not found")
    j["status"] = "aborted"
    _jobs.set(jid, j)
    if jid in _migrators: _migrators[jid].stop()
    return {"ok": True}


@router.delete("/{jid}", status_code=204)
def delete_job(jid: str):
    if jid not in _jobs: raise HTTPException(404, "Not found")
    if jid in _migrators: _migrators[jid].stop()
    _jobs.delete(jid)
    _job_logs.pop(jid, None)


@router.post("/bulk-delete")
def bulk_delete_jobs(body: dict):
    """여러 Job 일괄 삭제"""
    ids = body.get("ids", [])
    deleted = []; skipped = []
    for jid in ids:
        j = _jobs.get(jid)
        if j is None:
            skipped.append(jid); continue
        if j.get("status") in ("running", "paused"):
            skipped.append(jid); continue
        if jid in _migrators:
            try: _migrators[jid].stop()
            except: pass
        _jobs.delete(jid)
        _job_logs.pop(jid, None)
        deleted.append(jid)
    return {"deleted": len(deleted), "skipped": len(skipped),
            "deleted_ids": deleted, "skipped_ids": skipped}


@router.post("/{jid}/restart")
def restart_job(jid: str, bg: BackgroundTasks, body: dict = None):
    """기존 Job 설정을 복사해 새 Job으로 재실행"""
    if body is None:
        body = {}
    src = _jobs.get(jid)
    if src is None:
        raise HTTPException(404, "Job을 찾을 수 없습니다")

    new_jid   = str(uuid.uuid4())
    orig_name = src["name"].replace("[재실행] ","").replace("【재실행】","").strip()
    new_job   = _new_job(new_jid, f"[재실행] {orig_name}", src["src_db"], src["tgt_db"])

    for key in ("src_host","src_database","src_username","src_password",
                "tgt_host","tgt_database","tgt_username","tgt_password",
                "tables","batch_size","truncate_target","create_table","on_error",
                "objects","convert_objects"):
        new_job[key] = src.get(key, new_job.get(key))

    for key in ("src_host","src_database","src_username","src_password","src_port",
                "tgt_host","tgt_database","tgt_username","tgt_password","tgt_port"):
        if body.get(key):
            new_job[key] = body[key]

    new_job["table_total"]    = len(new_job.get("tables") or [])
    new_job["status"]         = "running"
    new_job["started_at"]     = datetime.utcnow().isoformat()
    new_job["progress"]       = 0
    new_job["rows_processed"] = 0
    new_job["rows_total"]     = 0
    new_job["current_table"]  = "준비 중..."

    _jobs.set(new_jid, new_job)
    _job_logs[new_jid] = [{
        "time":    datetime.utcnow().strftime("%H:%M:%S"),
        "level":   "info",
        "tag":     f"Job#{new_jid[:6]}",
        "message": f"재실행 시작 — 원본: {orig_name}",
    }]
    bg.add_task(_run_migration, new_jid)
    return new_job


@router.get("/{jid}/logs")
def get_logs(jid: str):
    return _job_logs.get(jid, [])
