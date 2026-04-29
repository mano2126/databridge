"""
app/api/routes/jobs.py
실제 마이그레이션 엔진 포함 Job 관리 API — JSON 영속성 적용
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Optional
import uuid, threading, time, random, logging
from datetime import datetime
from app.core.store import Store

logger = logging.getLogger("databridge.jobs")

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
        "phase": "INIT",
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
        "item_statuses": {},   # {name: {type,status,rows,error,started_at,finished_at}}
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
        self._log("info", f"이관 시작 — {self.job.get('name','')}")
        self._log("info", f"소스: {self.job.get('src_db','').upper()} {self.job.get('src_host','')} / {self.job.get('src_database','')}")
        self._log("info", f"타겟: {self.job.get('tgt_db','').upper()} {self.job.get('tgt_host','')} / {self.job.get('tgt_database','')}")

        try:
            # 소스/타겟 연결
            src_conn = self._connect_src()
            tgt_conn = self._connect_tgt()
            if not src_conn or not tgt_conn:
                raise Exception("DB 연결 실패 — 커넥터 관리에서 연결 정보를 확인하세요")

            # tables가 명시적으로 지정된 경우 그대로 사용 (빈 리스트도 존중)
            _tables_val = self.job.get("tables")
            if _tables_val is None:
                tables = self._get_all_tables(src_conn)   # 미지정 → 전체
            else:
                tables = _tables_val                       # 빈 리스트 포함 그대로
            self.job["table_total"] = len(tables)

            # ── MySQL 타겟: 이관 전 FK + 트리거 비활성화 ──────────
            tgt_db_type = (self.job.get("tgt_db") or "mysql").lower()
            tgt_is_mysql = tgt_db_type in ("mysql","aurora","mariadb","tidb","cloudsql")
            tgt_is_mssql = tgt_db_type in ("mssql","azure","sqlserver")
            _global_triggers_disabled = False
            _dropped_triggers = {}
            if tgt_db_type in ("mysql","aurora","mariadb","tidb","cloudsql"):
                try:
                    self.job["phase"] = "FK_DISABLE"
                    self.job["current_table"] = "⚙ FK / 트리거 비활성화 중..."
                    _gc = tgt_conn.cursor()
                    _gc.execute("SET FOREIGN_KEY_CHECKS=0")
                    _gc.execute("SET UNIQUE_CHECKS=0")
                    tgt_conn.commit()
                    _global_triggers_disabled = True
                    self._log("info", "MySQL: FOREIGN_KEY_CHECKS=0, UNIQUE_CHECKS=0")

                    # ── 트리거 백업 및 DROP ──────────────────────
                    import pymysql.cursors as _pyc2
                    _dict_cur = tgt_conn.cursor(_pyc2.DictCursor)
                    _tgt_db = self.job.get("tgt_database", "")
                    _dict_cur.execute(
                        "SELECT TRIGGER_NAME, EVENT_OBJECT_TABLE, ACTION_TIMING, "
                        "EVENT_MANIPULATION, ACTION_STATEMENT "
                        "FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=%s",
                        [_tgt_db]
                    )
                    _all_trigs = _dict_cur.fetchall()
                    if _all_trigs:
                        self._log("info", f"트리거 {len(_all_trigs)}개 임시 비활성화(DROP)")
                        for _tr in _all_trigs:
                            _tn  = _tr["TRIGGER_NAME"] if isinstance(_tr, dict) else _tr[0]
                            _tbl = _tr["EVENT_OBJECT_TABLE"] if isinstance(_tr, dict) else _tr[1]
                            _tim = _tr["ACTION_TIMING"] if isinstance(_tr, dict) else _tr[2]
                            _evt = _tr["EVENT_MANIPULATION"] if isinstance(_tr, dict) else _tr[3]
                            _act = _tr["ACTION_STATEMENT"] if isinstance(_tr, dict) else _tr[4]
                            _dropped_triggers.setdefault(_tbl, []).append({
                                "name": _tn, "timing": _tim, "event": _evt, "action": _act
                            })
                            _gc.execute(f"DROP TRIGGER IF EXISTS `{_tn}`")
                        tgt_conn.commit()
                        self._log("info", f"트리거 {len(_all_trigs)}개 DROP 완료")

                    self.job["phase"] = "RUNNING"
                    self.job["current_table"] = ""
                except Exception as _ge:
                    self._log("warn", f"FK/트리거 비활성화 실패 (무시): {_ge}")
                    self.job["phase"] = "RUNNING"
                    self.job["current_table"] = ""
            try:
                self.job["rows_total"] = self._estimate_total_rows(src_conn, tables)
            except Exception as _e:
                self._log("warn", f"rows 추정 실패 (무시): {_e}")
                self.job["rows_total"] = 0
            self._log("info", f"이관 대상 테이블 {len(tables)}개, 예상 {self.job['rows_total']:,} rows")
            # 모든 테이블 pending 초기화
            for _t in tables:
                self.job["item_statuses"][_t] = {"type":"table","status":"pending","rows":0,"error":None,"started_at":None,"finished_at":None}

            # ── FK 의존성 분석 → 토폴로지 정렬 ─────────────────────
            def _topo_sort_tables(conn, tbl_list, db_type):
                if len(tbl_list) <= 1: return tbl_list
                deps = {t: set() for t in tbl_list}
                tbl_set = set(t.lower() for t in tbl_list)
                try:
                    _cur = conn.cursor()
                    if db_type in ("mssql","azure","sqlserver"):
                        _cur.execute("""
                            SELECT OBJECT_NAME(fk.parent_object_id) AS c,
                                   OBJECT_NAME(fk.referenced_object_id) AS p
                            FROM sys.foreign_keys fk
                            WHERE OBJECT_NAME(fk.parent_object_id)<>OBJECT_NAME(fk.referenced_object_id)
                        """)
                        for _r in _cur.fetchall():
                            _c = _r[0] if not isinstance(_r,dict) else _r["c"]
                            _p = _r[1] if not isinstance(_r,dict) else _r["p"]
                            if _c and _p and _c.lower() in tbl_set and _p.lower() in tbl_set:
                                _cr = next((t for t in tbl_list if t.lower()==_c.lower()),_c)
                                _pr = next((t for t in tbl_list if t.lower()==_p.lower()),_p)
                                deps[_cr].add(_pr)
                    elif db_type in ("mysql","aurora","mariadb","tidb","cloudsql"):
                        _tdb = self.job.get("src_database","")
                        _cur.execute(
                            "SELECT TABLE_NAME,REFERENCED_TABLE_NAME FROM information_schema.KEY_COLUMN_USAGE "
                            "WHERE TABLE_SCHEMA=%s AND REFERENCED_TABLE_NAME IS NOT NULL "
                            "AND TABLE_NAME<>REFERENCED_TABLE_NAME", [_tdb])
                        for _r in _cur.fetchall():
                            _c = _r[0] if not isinstance(_r,dict) else _r["TABLE_NAME"]
                            _p = _r[1] if not isinstance(_r,dict) else _r["REFERENCED_TABLE_NAME"]
                            if _c and _p and _c.lower() in tbl_set and _p.lower() in tbl_set:
                                _cr = next((t for t in tbl_list if t.lower()==_c.lower()),_c)
                                _pr = next((t for t in tbl_list if t.lower()==_p.lower()),_p)
                                deps[_cr].add(_pr)
                except Exception as _te:
                    self._log("warn", f"FK 의존성 분석 실패 (원래 순서 유지): {_te}")
                    return tbl_list
                # Kahn's 토폴로지 정렬
                in_deg = {t: len(deps[t]) for t in tbl_list}
                q = sorted([t for t in tbl_list if in_deg[t]==0])
                result = []
                while q:
                    node = q.pop(0); result.append(node)
                    for child in tbl_list:
                        if node in deps[child]:
                            deps[child].discard(node)
                            in_deg[child] -= 1
                            if in_deg[child]==0:
                                q.append(child); q.sort()
                remain = [t for t in tbl_list if t not in result]
                if remain:
                    self._log("warn", f"순환 FK 참조: {remain} — 뒤에 추가")
                    result.extend(remain)
                self._log("info", f"FK 의존성 정렬: {len(result)}개 테이블 순서 확정")
                return result

            if tables:
                tables = _topo_sort_tables(src_conn, tables, src_db_type)
                for _t in tables:
                    if _t not in self.job["item_statuses"]:
                        self.job["item_statuses"][_t] = {"type":"table","status":"pending","rows":0,"error":None,"started_at":None,"finished_at":None}

            total_done = 0
            for i, tbl in enumerate(tables):
                if self._stop:
                    break
                while self._pause:
                    time.sleep(0.5)

                self.job["current_table"] = tbl
                self.job["table_done"] = i
                self._log("info", f"테이블 [{tbl}] 이관 시작")
                _ts = datetime.utcnow().isoformat()
                self.job["item_statuses"][tbl] = {"type":"table","status":"running","rows":0,"error":None,"started_at":_ts,"finished_at":None}

                try:
                    done = self._migrate_table(src_conn, tgt_conn, tbl)
                    total_done += done
                    self.job["rows_processed"] = total_done
                    self.job["table_done"] = i + 1
                    self._log("info", f"✓ 테이블 [{tbl}] 완료 — {done:,} rows")
                    st2 = self.job["item_statuses"].get(tbl, {})
                    # 실제 타겟 건수 확인
                    _actual_tgt = st2.get("rows_tgt", done)
                    try:
                        _vc = tgt_conn.cursor()
                        _vc.execute(f"SELECT COUNT(*) FROM `{tbl}`" if tgt_is_mysql else f"SELECT COUNT(*) FROM [{tbl}]")
                        _vr = _vc.fetchone()
                        _actual_tgt = _vr[0] if _vr else _actual_tgt
                    except: pass
                    self.job["item_statuses"][tbl].update({
                        "status":"done","rows":done,
                        "rows_src": done,
                        "rows_tgt": _actual_tgt,
                        "rows_tgt_final": True,
                        "finished_at":datetime.utcnow().isoformat()
                    })
                except Exception as e:
                    self._log("error", f"테이블 [{tbl}] 오류: {e}")
                    self.job["rows_error"] += 1
                    self.job["item_statuses"][tbl].update({"status":"error","error":str(e)[:200],"finished_at":datetime.utcnow().isoformat()})
                    if self.job["on_error"] == "abort":
                        raise

            # ── MySQL 타겟: 이관 완료 후 FK/유니크 체크 복원 ───
            if _global_triggers_disabled:
                try:
                    self.job["phase"] = "FK_RESTORE"
                    self.job["current_table"] = "⚙ FK / 트리거 복원 중..."
                    _rc = tgt_conn.cursor()
                    _rc.execute("SET FOREIGN_KEY_CHECKS=1")
                    _rc.execute("SET UNIQUE_CHECKS=1")
                    tgt_conn.commit()
                    self._log("info", "MySQL: FOREIGN_KEY_CHECKS=1, UNIQUE_CHECKS=1 복원")

                    # ── 트리거 복원 ──────────────────────────────
                    if _dropped_triggers:
                        import pymysql as _pm2
                        _tgt_db2 = self.job.get("tgt_database", "")
                        _conn_kw2 = dict(
                            host=self.job.get("tgt_host","localhost"),
                            port=int(self.job.get("tgt_port") or 3306),
                            user=self.job.get("tgt_username","root"),
                            password=self.job.get("tgt_password",""),
                            database=_tgt_db2, charset="utf8mb4"
                        )
                        _restored = 0
                        _failed_restore = []
                        _total = sum(len(v) for v in _dropped_triggers.values())
                        for _rtbl, _rtrigs in _dropped_triggers.items():
                            for _rtr in _rtrigs:
                                try:
                                    _sql = (
                                        f"CREATE TRIGGER `{_rtr['name']}` "
                                        f"{_rtr['timing']} {_rtr['event']} "
                                        f"ON `{_rtbl}` FOR EACH ROW {_rtr['action']}"
                                    )
                                    _tc = _pm2.connect(**_conn_kw2)
                                    try:
                                        _tc.cursor().execute(_sql)
                                        _tc.commit()
                                        _restored += 1
                                        self._log("info", f"  트리거 [{_rtr['name']}] 복원 완료")
                                    finally:
                                        _tc.close()
                                except Exception as _rte:
                                    _failed_restore.append(_rtr['name'])
                                    self._log("warn", f"  트리거 [{_rtr['name']}] 복원 실패: {_rte}")
                        self._log("info", f"트리거 {_restored}/{_total}개 복원 완료")
                        if _failed_restore:
                            self._log("warn", f"복원 실패: {_failed_restore}")

                    self.job["current_table"] = ""
                    self.job["phase"] = "RUNNING"
                except Exception as _re:
                    self._log("warn", f"FK/트리거 복원 실패: {_re}")
                    self.job["current_table"] = ""

            # ── 오브젝트 이관 (프로시저, 함수, 트리거, 뷰) ──
            objects = self.job.get("objects") or {}
            convert = self.job.get("convert_objects", True)
            obj_counts = {k: len(v) for k, v in objects.items() if v}
            self._log("info", f"오브젝트 목록: {obj_counts} (총 {sum(obj_counts.values())}개)")
            if any(objects.get(k) for k in ("procedures","functions","triggers","views")):
                self.job["phase"] = "OBJECTS"
                self._log("info", "오브젝트 이관 시작")
                self._migrate_objects(src_conn, tgt_conn, objects, convert)
            else:
                self._log("info", "이관할 오브젝트 없음 — 건너뜀")

            src_conn.close()
            tgt_conn.close()

            if not self._stop:
                self.job["status"] = "completed"
                self.job["phase"]  = "DONE"
                self.job["progress"] = 100
                self.job["current_table"] = ""
                self._log("info", f"이관 완료 — 총 {total_done:,} rows")
            else:
                self.job["status"] = "aborted"
                self.job["phase"]  = "DONE"
                self._log("warn", "이관 중단됨")

        except Exception as e:
            import traceback as _tb
            self.job["status"] = "error"
            self.job["phase"]  = "DONE"
            self.job["error_message"] = str(e)
            self._log("error", f"치명 오류: {e}\n{_tb.format_exc()}")
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
        src_db_type = (self.job.get("src_db") or "mysql").lower()
        src_database = self.job.get("src_database", "")
        cur = src_conn.cursor()

        if src_db_type in ("mssql", "azure", "sqlserver"):
            # MSSQL: sys.tables 사용
            cur.execute("""
                SELECT TABLE_NAME FROM information_schema.TABLES
                WHERE TABLE_CATALOG = ? AND TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
            """, (src_database,))
            rows = cur.fetchall()
            return [r[0] if not isinstance(r, dict) else r["TABLE_NAME"] for r in rows]
        else:
            # MySQL / MariaDB / Aurora
            cur.execute("""
                SELECT TABLE_NAME FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE='BASE TABLE'
                ORDER BY TABLE_NAME
            """)
            return [r["TABLE_NAME"] for r in cur.fetchall()]

    def _estimate_total_rows(self, src_conn, tables: list) -> int:
        """rows 추정 — 실패 시 0 반환 (이관에 영향 없음)"""
        src_db_type = (self.job.get("src_db") or "mysql").lower()
        total = 0
        try:
            cur = src_conn.cursor()
            if src_db_type in ("mssql", "azure", "sqlserver"):
                # MSSQL: sys.dm_db_partition_stats 로 한번에 조회
                cur.execute("""
                    SELECT OBJECT_NAME(object_id) AS tbl, SUM(row_count) AS cnt
                    FROM sys.dm_db_partition_stats
                    WHERE index_id IN (0, 1)
                    GROUP BY object_id
                """)
                rows = cur.fetchall()
                name_map = {}
                for r in rows:
                    try:
                        nm = r[0] if isinstance(r, (list,tuple)) else r.get("tbl","")
                        cnt = r[1] if isinstance(r, (list,tuple)) else r.get("cnt",0)
                        name_map[nm] = cnt or 0
                    except: pass
                total = sum(name_map.get(t, 0) for t in tables)
            else:
                # MySQL: information_schema 한번에 조회
                cur.execute(
                    "SELECT TABLE_NAME, TABLE_ROWS FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE='BASE TABLE'"
                )
                rows = cur.fetchall()
                name_map = {}
                for r in rows:
                    try:
                        nm  = r["TABLE_NAME"] if isinstance(r, dict) else r[0]
                        cnt = r["TABLE_ROWS"]  if isinstance(r, dict) else r[1]
                        name_map[nm] = cnt or 0
                    except: pass
                total = sum(name_map.get(t, 0) for t in tables)
        except Exception as _e:
            self._log("warn", f"rows 추정 실패 (0 처리): {_e}")
            total = 0
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
            "datetimeoffset": "DATETIME(6)",   # ODBC -155 → UTC 변환 후 DATETIME으로
            "rowversion":   "BIGINT",          # 8바이트 이진 → 부호없는 정수
            "timestamp":    "BIGINT",          # rowversion과 동일
            "hierarchyid":  "VARCHAR(500)",    # /1/2/3/ 형태 계층 경로
            "geography":    "TEXT",            # WKT 문자열 (ST_AsText)
            "geometry":     "TEXT",            # WKT 문자열
            "sql_variant":  "TEXT",
        }
        col_defs = []
        pk_cols  = []
        for c in cols:
            cname    = c.get("COLUMN_NAME","col")
            raw_type = (c.get("DATA_TYPE") or "varchar").lower().strip()
            is_ai    = "auto_increment" in (c.get("EXTRA","") or "").lower()
            is_pk    = (c.get("COLUMN_KEY","") == "PRI")
            nullable = c.get("IS_NULLABLE","YES") == "YES"
            # NULL_VIOLATION fix_action: NOT NULL 컬럼을 NULL 허용으로 강제 변환
            _fix_actions = self.job.get("auto_fix_actions") or []
            _null_fix_cols = set()
            for _fa in _fix_actions:
                if _fa.get("action") == "NULL_VIOLATION":
                    for _at in (_fa.get("affected") or []):
                        if _at.get("table") == table:
                            _null_fix_cols.add(_at.get("column",""))
            if not nullable and cname in _null_fix_cols:
                nullable = True  # NULL_VIOLATION fix: NOT NULL → NULL
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

        def _mssql_to_mysql_trigger(ddl: str, trig_name: str) -> str:
            """MSSQL 트리거 DDL → MySQL 트리거로 변환"""
            import re as _r

            s = ddl.strip()

            # 1. [dbo].[name] 또는 [name] → name
            s = _r.sub(r'\[dbo\]\.\[(\w+)\]', r'\1', s)
            s = _r.sub(r'\[(\w+)\]',           r'\1', s)

            # 2. CREATE [OR ALTER] TRIGGER — 다중 이벤트 먼저 처리
            # 다중 이벤트 패턴: TRIGGER name ON tbl AFTER INSERT, UPDATE, DELETE
            _multi_raw = _r.search(
                r'CREATE\s+(?:OR\s+ALTER\s+)?TRIGGER\s+(\w+)\s+ON\s+(\w+)\s+'
                r'(AFTER|FOR|INSTEAD\s+OF)\s+'
                r'((?:INSERT|UPDATE|DELETE)(?:\s*,\s*(?:INSERT|UPDATE|DELETE))+)',
                s, _r.IGNORECASE)
            if _multi_raw:
                _mn   = _multi_raw.group(1)
                _mtbl = _multi_raw.group(2)
                _mtim = 'AFTER' if _multi_raw.group(3).upper() in ('AFTER','FOR') else 'BEFORE'
                _mevts = [e.strip().upper() for e in _multi_raw.group(4).split(',')]
                # body 추출 (AS\nBEGIN 또는 BEGIN)
                _mb_start = s.find('BEGIN', _multi_raw.end())
                _mbody = s[_mb_start:].strip() if _mb_start >= 0 else 'BEGIN\nEND'
                # body 정리
                # MSSQL 전용 구문 제거
                _mbody = _r.sub(r'\bSET\s+NOCOUNT\s+ON\s*;?', '', _mbody, flags=_r.IGNORECASE)
                _mbody = _r.sub(r'\bSET\s+NOCOUNT\s+OFF\s*;?', '', _mbody, flags=_r.IGNORECASE)
                _mbody = _r.sub(r'\bRETURN\s*;?\s*\n', '\n', _mbody, flags=_r.IGNORECASE)
                _mbody = _r.sub(r'\bAS\s*\n\s*BEGIN\b', 'BEGIN', _mbody, flags=_r.IGNORECASE)
                _mbody = _r.sub(r'\bISNULL\s*\(', 'IFNULL(', _mbody, flags=_r.IGNORECASE)
                _mbody = _r.sub(r'\bNVARCHAR\b', 'CHAR', _mbody, flags=_r.IGNORECASE)
                _mbody = _r.sub(r'\bNVARCHAR\s*\(', 'CHAR(', _mbody, flags=_r.IGNORECASE)
                _mbody = _r.sub(r'\bSYSTEM_USER\b', 'CURRENT_USER()', _mbody, flags=_r.IGNORECASE)
                _mbody = _r.sub(r'\bGETDATE\(\)', 'NOW()', _mbody, flags=_r.IGNORECASE)
                _mbody = _r.sub(r'\bNEWID\(\)', 'UUID()', _mbody, flags=_r.IGNORECASE)
                # alias.col → NEW.col / OLD.col (i., d., ins., del. 패턴)
                _mbody = _r.sub(r'\b(?:i|ins|inserted)\.(\w+)', r'NEW.\1', _mbody, flags=_r.IGNORECASE)
                _mbody = _r.sub(r'\b(?:d|del|deleted)\.(\w+)', r'OLD.\1', _mbody, flags=_r.IGNORECASE)
                # SELECT ... 절에서 FROM 없는 경우 VALUES 형태로 변환은 복잡하므로 FROM DUAL 추가
                _mbody = _r.sub(r'\bDECLARE\s+@\w+[^;]+;?', '', _mbody, flags=_r.IGNORECASE)
                _mbody = _r.sub(r'WHEN\s+EXISTS\s*\([^)]+\)', 'TRUE', _mbody, flags=_r.IGNORECASE)
                _mbody = _r.sub(r'\bINSERTED\.', 'NEW.', _mbody, flags=_r.IGNORECASE)
                _mbody = _r.sub(r'\bDELETED\.', 'OLD.', _mbody, flags=_r.IGNORECASE)
                _mbody = _r.sub(r'FROM\s+INSERTED\s+\w+.*?(?=SELECT|INSERT|UPDATE|WHERE|END)', '', _mbody, flags=_r.IGNORECASE|_r.DOTALL)
                _mbody = _r.sub(r'FULL\s+OUTER\s+JOIN\s+(?:INSERTED|DELETED)\s+\w+\s+ON[^\n]*', '', _mbody, flags=_r.IGNORECASE)
                _mbody = _r.sub(r'JOIN\s+(?:INSERTED|DELETED)\s+\w+\s+ON[^\n]*', '', _mbody, flags=_r.IGNORECASE)
                _mbody = _r.sub(r'\n{3,}', '\n\n', _mbody)
                _op_map = {'INSERT': "'I'", 'UPDATE': "'U'", 'DELETE': "'D'"}
                _parts = []
                for _evt in _mevts:
                    _tname = f"{_mn}_{_evt}"
                    _parts.append(f"DROP TRIGGER IF EXISTS `{_tname}`;")
                    _evt_body = _r.sub(r"@op", _op_map.get(_evt, "'U'"), _mbody)
                    _parts.append(
                        f"CREATE TRIGGER `{_tname}`\n{_mtim} {_evt}\n"
                        f"ON `{_mtbl}` FOR EACH ROW\n{_evt_body}"
                    )
                return '\n'.join(_parts)

            # 단일 이벤트 헤더 변환
            def _hdr(m):
                tn  = m.group(1); tbl = m.group(2)
                tim = 'AFTER' if m.group(3).upper() in ('AFTER','FOR') else 'BEFORE'
                evt = m.group(4).upper()
                return f'CREATE TRIGGER `{tn}`\n{tim} {evt}\nON `{tbl}`\nFOR EACH ROW'
            s = _r.sub(
                r'CREATE\s+(?:OR\s+ALTER\s+)?TRIGGER\s+(\w+)\s+ON\s+(\w+)\s+(AFTER|INSTEAD\s+OF|FOR)\s+(INSERT|UPDATE|DELETE)',
                _hdr, s, flags=_r.IGNORECASE)

            # 3. MSSQL 전용 구문 제거
            s = _r.sub(r'SET\s+NOCOUNT\s+ON\s*;?', '', s, flags=_r.IGNORECASE)
            s = _r.sub(r'IF\s+UPDATE\s*\(\w+\)',    '', s, flags=_r.IGNORECASE)

            # 4. FROM INSERTED i JOIN DELETED d → 제거 (MySQL은 NEW/OLD 사용)
            #    INSERTED.col / i.col → NEW.col
            #    DELETED.col  / d.col → OLD.col
            # 먼저 alias 매핑 분석
            ins_alias = _r.search(r'FROM\s+INSERTED\s+(\w+)', s, _r.IGNORECASE)
            del_alias = _r.search(r'JOIN\s+DELETED\s+(\w+)',  s, _r.IGNORECASE)
            i_al = ins_alias.group(1) if ins_alias else None
            d_al = del_alias.group(1) if del_alias else None

            # alias.col → NEW.col / OLD.col
            if i_al:
                s = _r.sub(rf'\b{i_al}\.(\w+)', r'NEW.\1', s, flags=_r.IGNORECASE)
            if d_al:
                s = _r.sub(rf'\b{d_al}\.(\w+)', r'OLD.\1', s, flags=_r.IGNORECASE)

            # INSERTED.col → NEW.col
            s = _r.sub(r'\bINSERTED\.(\w+)', r'NEW.\1', s, flags=_r.IGNORECASE)
            s = _r.sub(r'\bDELETED\.(\w+)',  r'OLD.\1', s, flags=_r.IGNORECASE)

            # FROM INSERTED ... JOIN DELETED ... ON ... 절 제거
            s = _r.sub(r'\bFROM\s+(?:INSERTED|DELETED)\s+\w+.*?(?=WHERE|BEGIN|END|INSERT|UPDATE|DELETE|$)',
                        '', s, flags=_r.IGNORECASE|_r.DOTALL)
            s = _r.sub(r'\bJOIN\s+(?:INSERTED|DELETED)\s+\w+\s+ON[^;]*?(?=WHERE|BEGIN|END|INSERT|UPDATE|DELETE|$)',
                        '', s, flags=_r.IGNORECASE|_r.DOTALL)

            # 5. 함수 변환
            s = _r.sub(r'\bGETDATE\(\)',       'NOW()',           s, flags=_r.IGNORECASE)
            s = _r.sub(r'\bGETUTCDATE\(\)',    'UTC_TIMESTAMP()', s, flags=_r.IGNORECASE)
            s = _r.sub(r'\bISNULL\s*\(',       'IFNULL(',         s, flags=_r.IGNORECASE)
            s = _r.sub(r'\bSYSTEM_USER\b',     'CURRENT_USER()',  s, flags=_r.IGNORECASE)
            s = _r.sub(r'\bNVARCHAR\b',        'CHAR',            s, flags=_r.IGNORECASE)

            # 6. AS\nBEGIN 구조 정리 (MySQL은 AS 없음)
            s = _r.sub(r'\bAS\s*\n\s*BEGIN\b', 'BEGIN', s, flags=_r.IGNORECASE)

            # 7. 빈 줄 정리
            s = _r.sub(r'\n{3,}', '\n\n', s)

            # 8. 다중 이벤트 분리 (MySQL은 이벤트당 하나의 트리거)
            # 패턴1: AFTER INSERT ON tbl FOR EACH ROW, UPDATE, DELETE
            # 패턴2: AFTER INSERT / ON tbl / FOR EACH ROW, UPDATE, DELETE
            multi_m = _r.search(
                r'CREATE\s+TRIGGER\s+`(\w+)`'
                r'[\s\S]*?'
                r'(AFTER|BEFORE)\s+'
                r'((?:INSERT|UPDATE|DELETE)(?:\s*,\s*(?:INSERT|UPDATE|DELETE))+)'
                r'\s+ON\s+`(\w+)`\s+FOR\s+EACH\s+ROW',
                s, _r.IGNORECASE)
            if multi_m:
                base_name = multi_m.group(1)
                timing    = multi_m.group(2).upper()
                all_evts  = [e.strip().upper() for e in multi_m.group(3).split(',')]
                table     = multi_m.group(4)
                body_start = s.find('BEGIN', multi_m.end())
                body = s[body_start:].strip() if body_start >= 0 else 'BEGIN\nEND'
                # body 내 MSSQL 잔류 패턴 정리
                body = _r.sub(r'\bDECLARE\s+@\w+.*?;', '', body, flags=_r.IGNORECASE|_r.DOTALL)
                body = _r.sub(r'WHEN\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+INSERTED.*?\)', 'TRUE', body, flags=_r.IGNORECASE|_r.DOTALL)
                body = _r.sub(r'WHEN\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+DELETED.*?\)', 'TRUE', body, flags=_r.IGNORECASE|_r.DOTALL)
                body = _r.sub(r'\bINSERTED\.', 'NEW.', body, flags=_r.IGNORECASE)
                body = _r.sub(r'\bDELETED\.', 'OLD.', body, flags=_r.IGNORECASE)
                body = _r.sub(r'FROM\s+INSERTED\b[^\n]*', '', body, flags=_r.IGNORECASE)
                body = _r.sub(r'FROM\s+DELETED\b[^\n]*', '', body, flags=_r.IGNORECASE)
                body = _r.sub(r'JOIN\s+(?:INSERTED|DELETED)\s+\w+\s+ON[^\n]*', '', body, flags=_r.IGNORECASE)
                body = _r.sub(r'\n{3,}', '\n\n', body)
                parts = []
                for evt in all_evts:
                    tname = f"{base_name}_{evt}"
                    parts.append(f"DROP TRIGGER IF EXISTS `{tname}`;")
                    # AuditLog 타입: 각 이벤트별로 적절한 op_cd 설정
                    if 'AuditLog' in base_name or 'audit' in base_name.lower():
                        op_map = {'INSERT': "'I'", 'UPDATE': "'U'", 'DELETE': "'D'"}
                        evt_body = _r.sub(r"@op\s+CHAR\(1\).*?END;?", '', body, flags=_r.IGNORECASE|_r.DOTALL)
                        evt_body = _r.sub(r"\b@op\b", op_map.get(evt,"'U'"), evt_body)
                    else:
                        evt_body = body
                    parts.append(
                        f"CREATE TRIGGER `{tname}`\n{timing} {evt}\n"
                        f"ON `{table}` FOR EACH ROW\n{evt_body}"
                    )
                return '\n'.join(parts)

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
                # MSSQL → MySQL: 트리거 변환
                if src_db_type in ("mssql","azure","sqlserver") and tgt_db_type in ("mysql","aurora","mariadb"):
                    if obj_type == "TRIGGER":
                        return _mssql_to_mysql_trigger(ddl, "")
                # 그 외 방향: schema.py rule-based 변환 시도
                try:
                    from app.api.routes.schema import _rule_based_ddl_convert
                    result = _rule_based_ddl_convert(ddl, obj_type, "", src_db_type, tgt_db_type)
                    stmts = result.get("statements", [])
                    if stmts:
                        return stmts[-1]
                except Exception:
                    pass
                return ddl
            except Exception as ce:
                self._log("warn", f"DDL 변환 경고 [{obj_type}]: {ce}")
                return ddl

        # ── obj_mode: skip_existing 체크 ─────────────────────────
        def _obj_exists_in_tgt(obj_type: str, name: str) -> bool:
            """타겟 DB에 오브젝트가 이미 존재하는지 확인"""
            try:
                cur_tgt = tgt_conn.cursor()
                if tgt_db_type in ("mssql","azure","sqlserver"):
                    cur_tgt.execute("SELECT 1 FROM sys.objects WHERE name=? AND type IN ('P','FN','TR','V','IF','TF')", [name])
                    return cur_tgt.fetchone() is not None
                else:  # MySQL
                    db = self.job.get("tgt_database","")
                    cur_tgt.execute(
                        "SELECT 1 FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=%s AND ROUTINE_NAME=%s "
                        "UNION SELECT 1 FROM information_schema.VIEWS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s "
                        "UNION SELECT 1 FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=%s AND TRIGGER_NAME=%s",
                        [db, name, db, name, db, name]
                    )
                    return cur_tgt.fetchone() is not None
            except Exception:
                return False

        # ── 타겟 실행 (재시도 지원) ──────────────────────────────
        def _exec_tgt(ddl: str, obj_type: str, name: str, error_hint: str = "") -> bool:
            if not ddl.strip() or ddl.startswith('--'):
                self._log("warn", f"[{name}] DDL 없음 — 건너뜀")
                return True  # 오류 아님

            # skip_existing: 타겟에 이미 있으면 건너뜀
            obj_mode = self.job.get("obj_mode", "drop_recreate")
            # 다중 이벤트 분리 트리거 체크: TRG02 → TRG02_INSERT/UPDATE/DELETE
            def _trigger_exists_any(n):
                if _obj_exists_in_tgt(obj_type, n): return True
                if obj_type == "TRIGGER":
                    for _evt in ("INSERT","UPDATE","DELETE"):
                        if _obj_exists_in_tgt(obj_type, f"{n}_{_evt}"): return True
                return False
            if obj_mode == "skip_existing" and _trigger_exists_any(name):
                self._log("info", f"[{name}] 이미 존재 — skip (obj_mode=skip_existing)")
                self.job["item_statuses"][name] = {
                    "type": obj_type.lower(), "status": "done",
                    "rows": 0, "error": None,
                    "started_at": None, "finished_at": datetime.utcnow().isoformat()
                }
                return True

            # 방향 확인 로그
            self._log("info", f"[{name}] 변환 방향: {src_db_type} → {tgt_db_type}")

            # obj_engine 설정 확인
            _obj_engine = self.job.get("obj_engine", "auto")
            statements = []

            # ── AI 이관 ──────────────────────────────────────────
            if _obj_engine in ("ai", "claude"):
                # API 키 확인 (anthropic_api_key 우선)
                try:
                    from app.api.routes.settings import _cfg as _chk_cfg
                    _api_key = _chk_cfg().get("anthropic_api_key", "").strip()
                    if not _api_key:
                        from app.core.store import Store as _ChkStore
                        _api_key = (_ChkStore("settings").get("claude_api_key") or {}).get("value", "")
                except: _api_key = ""

                if not _api_key:
                    # API 키 없음 — 즉시 오류로 처리
                    err_msg = "Claude API 키가 설정되지 않았습니다. 시스템 설정 → Claude AI 설정에서 API 키를 입력하세요."
                    self._log("error", f"[{name}] {err_msg}")
                    self.job["item_statuses"][name] = {
                        "type": obj_type.lower(), "status": "error",
                        "rows": 0, "error": err_msg,
                        "started_at": None, "finished_at": datetime.utcnow().isoformat()
                    }
                    return False
                try:
                    from app.api.routes.schema import _ai_convert_ddl
                    self._log("info", f"[{name}] AI 변환 요청 중...")
                    result = _ai_convert_ddl(
                        ddl, obj_type, name,
                        src_db_type, tgt_db_type,
                        error_hint  # 이전 오류 포함
                    )
                    stmts = result.get("statements", [])
                    notes = result.get("notes", "")
                    if stmts:
                        statements = stmts
                        self._log("info", f"[{name}] AI 변환 완료 — {notes}")
                    else:
                        self._log("warn", f"[{name}] AI 변환 결과 없음 — rule-based로 폴백")
                except Exception as ae:
                    self._log("warn", f"[{name}] AI 변환 실패: {ae} — rule-based로 폴백")

            # ── rule-based / smart_convert ────────────────────────
            if not statements:
                converted_ddl = _smart_convert(ddl, obj_type)
                if converted_ddl != ddl:
                    self._log("info", f"[{name}] _smart_convert 적용됨")

                # 다중 트리거 분리 결과 감지 (DROP TRIGGER + CREATE TRIGGER 여러 개)
                import re as _stmtre
                _sub_stmts = [s.strip() for s in _stmtre.split(';', converted_ddl) if s.strip() and ('DROP TRIGGER' in s or 'CREATE TRIGGER' in s)]
                if len(_sub_stmts) > 1:
                    statements = _sub_stmts
                    self._log("info", f"[{name}] 다중 이벤트 분리 완료 — {len(_sub_stmts)}개 트리거")
                else:
                    try:
                        from app.api.routes.schema import _rule_based_ddl_convert
                        result = _rule_based_ddl_convert(converted_ddl, obj_type, name, src_db_type, tgt_db_type)
                        stmts = result.get("statements", [])
                        notes = result.get("notes", "")
                        if stmts and not (len(stmts)==1 and stmts[0].strip()==converted_ddl.strip()):
                            statements = stmts
                            self._log("info", f"[{name}] rule-based 변환 완료 ({len(stmts)}문장) — {notes}")
                        else:
                            statements = [converted_ddl]
                    except Exception as ce:
                        self._log("warn", f"[{name}] 변환 실패: {ce} — 원본 사용")
                        statements = [converted_ddl]

            self._log("debug", f"[{name}] 실행 DDL:\n{statements[-1][:300]}")
            # ── MSSQL 잔류 패턴 검증 (트리거) ──────────────────────
            if obj_type == "TRIGGER" and statements:
                _MSSQL_PATTERNS = [
                    # MSSQL 전용 테이블/키워드
                    r'\bFROM\s+INSERTED\b', r'\bFROM\s+DELETED\b',
                    r'\bJOIN\s+INSERTED\b', r'\bJOIN\s+DELETED\b',
                    r'\bINSERTED\.\w+',      r'\bDELETED\.\w+',
                    r'\bNEWID\s*\(\)',       r"\bN'",
                    r'\[dbo\]\.',             r'\[\w+\]',
                    r'\bRAISERROR\b',          r'\bSET\s+NOCOUNT\s+ON\b',
                    # MySQL 아키텍처 제약
                    r'UPDATE\s+\w+\s+SET[^;]+FROM\s+\w+',  # UPDATE...FROM (MSSQL 문법)
                    r'\bIF\s+UPDATE\s*\(',   # IF UPDATE(col)
                    r'\bSELECT\s+.*FROM\s+INSERTED',  # SELECT FROM INSERTED
                    r'\bDECLARE\s+@',          # MSSQL 변수 선언
                    r'\bSET\s+@\w+',           # MSSQL 변수 할당
                ]
                # MySQL 자기 테이블 UPDATE 패턴 — 트리거 대상 테이블명 추출
                import re as _rv2
                _trig_tbl_m = _rv2.search(
                    r'ON\s+`?(\w+)`?\s+FOR\s+EACH\s+ROW', statements[-1], _rv2.IGNORECASE)
                if _trig_tbl_m:
                    _trig_tbl = _trig_tbl_m.group(1).lower()
                    # 트리거 본문에서 자기 테이블 UPDATE 감지
                    _self_update = _rv2.search(
                        rf'UPDATE\s+`?{_trig_tbl}`?\s+SET', statements[-1], _rv2.IGNORECASE)
                    if _self_update:
                        _MSSQL_PATTERNS.append(rf'UPDATE\s+`?{_trig_tbl}`?\s+SET')
                import re as _rv
                _last_stmt = statements[-1]
                _found = [p for p in _MSSQL_PATTERNS if _rv.search(p, _last_stmt, _rv.IGNORECASE)]
                if _found:
                    self._log("warn", f"[{name}] MSSQL 잔류 패턴 감지: {_found[:3]} — AI 재변환 시도")
                    try:
                        from app.api.routes.schema import _ai_convert_ddl
                        from app.api.routes.settings import _cfg as _v_cfg
                        if _v_cfg().get("anthropic_api_key", ""):
                            _vr = _ai_convert_ddl(
                                ddl, obj_type, name, src_db_type, tgt_db_type,
                                f"이전 변환 오류: {_found[:3]}\n"
                                        f"MySQL 트리거 제약사항:\n"
                                        f"1. UPDATE table SET ... FROM table 불가 → JOIN 방식으로 변환\n"
                                        f"2. 트리거 대상 테이블 자체를 트리거 내에서 UPDATE 불가\n"
                                        f"3. INSERTED/DELETED 테이블 없음 → NEW/OLD 사용\n"
                                        f"4. DECLARE @var 없음 → SET @var := val 또는 제거\n"
                                        f"반드시 순수 MySQL 8.0 문법만 사용하세요."
                            )
                            if _vr.get("statements"):
                                statements = _vr["statements"]
                                self._log("info", f"[{name}] AI 재변환 완료")
                    except Exception as _ve:
                        self._log("warn", f"[{name}] AI 재변환 실패: {_ve}")

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
                self.job["item_statuses"][name] = {"type":obj_type.lower(),"status":"done","rows":0,"error":None,"started_at":None,"finished_at":datetime.utcnow().isoformat()}
                return True
            except Exception as e:
                self._log("error", f"✗ {obj_type} [{name}] 생성 실패: {e}")
                self.job["item_statuses"][name] = {"type":obj_type.lower(),"status":"error","rows":0,"error":str(e)[:200],"started_at":None,"finished_at":datetime.utcnow().isoformat()}
                self.job["rows_error"] += 1
                return False

        # ── 이관 실행 — 함수 먼저(의존성), 실패 시 1회 재시도 ────
        failed = []

        # 오브젝트 pending 초기화
        for _ot, _olist in [("FUNCTION", objects.get("functions") or []),
                             ("PROCEDURE", objects.get("procedures") or []),
                             ("VIEW", objects.get("views") or []),
                             ("TRIGGER", objects.get("triggers") or [])]:
            for _on in _olist:
                if _on not in self.job["item_statuses"]:
                    self.job["item_statuses"][_on] = {"type":_ot.lower(),"status":"pending","rows":0,"error":None,"started_at":None,"finished_at":None}

        # 1. 함수 (다른 오브젝트가 참조할 수 있음)
        for name in (objects.get("functions") or []):
            if self._stop: break
            ddl = _get_ddl("FUNCTION", name)
            if not _exec_tgt(ddl, "FUNCTION", name):
                err_info = (self.job.get("item_statuses", {}).get(name) or {}).get("error", "")
                failed.append(("FUNCTION", name, ddl, err_info))

        # 2. 프로시저
        for name in (objects.get("procedures") or []):
            if self._stop: break
            ddl = _get_ddl("PROCEDURE", name)
            if not _exec_tgt(ddl, "PROCEDURE", name):
                err_info = (self.job.get("item_statuses", {}).get(name) or {}).get("error", "")
                failed.append(("PROCEDURE", name, ddl, err_info))

        # 3. 뷰
        for name in (objects.get("views") or []):
            if self._stop: break
            ddl = _get_ddl("VIEW", name)
            if not _exec_tgt(ddl, "VIEW", name):
                err_info = (self.job.get("item_statuses", {}).get(name) or {}).get("error", "")
                failed.append(("VIEW", name, ddl, err_info))

        # 4. 트리거 (마지막 — 테이블 필요)
        # MySQL 타겟: 데이터 이관 시 백업→복원이 이미 됐으므로 존재하면 skip
        _tgt_is_mysql_obj = tgt_db_type in ("mysql","aurora","mariadb","tidb","cloudsql")
        for name in (objects.get("triggers") or []):
            if self._stop: break
            if _tgt_is_mysql_obj and _obj_exists_in_tgt("TRIGGER", name):
                self._log("info", f"[{name}] 트리거 이미 존재 (이관 중 복원됨) — skip")
                self.job["item_statuses"][name] = {
                    "type":"trigger","status":"done","rows":0,"error":None,
                    "started_at":None,"finished_at":datetime.utcnow().isoformat()
                }
                continue
            ddl = _get_ddl("TRIGGER", name)
            if not _exec_tgt(ddl, "TRIGGER", name):
                err_info = (self.job.get("item_statuses", {}).get(name) or {}).get("error", "")
                failed.append(("TRIGGER", name, ddl, err_info))

        # 5. 실패 오브젝트 1회 재시도 (의존성 순서 문제 해결)
        if failed:
            self._log("info", f"재시도: {len(failed)}개 오브젝트")
            still_failed = []
            for item_f in failed:
                obj_type_r, name, ddl = item_f[0], item_f[1], item_f[2]
                prev_err = item_f[3] if len(item_f) > 3 else ""
                if self._stop: break
                if not _exec_tgt(ddl, obj_type_r, name, error_hint=prev_err):
                    still_failed.append(name)
            if still_failed:
                self._log("warn", f"최종 실패 오브젝트: {still_failed}")


    _UNSUPPORTED_ODBC_TYPES = {-151, -155, -152, -153}  # geography, geometry, hierarchyid 등

    def _migrate_table(self, src_conn, tgt_conn, table: str) -> int:
        """소스 DB 타입에 따라 분기 — MySQL/MSSQL 양방향 지원"""
        # ── 테이블별 컬럼 처리맵 무조건 초기화 (잔상 방지) ──
        if not hasattr(self, '_skip_cols_map'): self._skip_cols_map = {}
        if not hasattr(self, '_cast_cols_map'): self._cast_cols_map = {}
        if not hasattr(self, '_rowver_cols'):   self._rowver_cols   = {}
        if not hasattr(self, '_dto_cols'):      self._dto_cols      = {}
        if not hasattr(self, '_geo_cols'):      self._geo_cols      = {}
        if not hasattr(self, '_bin_cols'):      self._bin_cols      = {}
        self._skip_cols_map[table] = set()
        self._cast_cols_map[table] = set()
        self._rowver_cols[table]   = set()
        self._dto_cols[table]      = set()
        self._geo_cols[table]      = set()
        self._bin_cols[table]      = set()

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

            # ── MSSQL 미지원 타입 컬럼 식별 ──────────────────────
            # 1단계: 타입 이름으로 명백한 미지원 타입 스킵
            _UNSUPPORTED_TYPES = {"sql_variant", "image", "xml"}  # hierarchyid는 별도 처리
            _HIER_TYPES        = {"hierarchyid"}
            _GEO_TYPES         = {"geography", "geometry"}
            _BINARY_TYPES = {"binary", "varbinary"}
            _skip_cols    = set()
            # _bin_cols는 _migrate_table 시작에서 이미 초기화됨 — 여기서 재초기화 금지

            for c in cols:
                dt = (c.get("DATA_TYPE") or "").lower()
                cn = c["COLUMN_NAME"]
                if dt in _HIER_TYPES:
                    # hierarchyid → ToString()으로 경로 문자열 변환 (/1/2/3/ 형태)
                    if not hasattr(self, '_hier_cols'): self._hier_cols = {}
                    self._hier_cols.setdefault(table, set()).add(cn)
                    self._cast_cols_map[table].add(cn)
                    self._log("info", f"  [{table}] hierarchyid 컬럼 '{cn}' → ToString() 변환")
                elif dt in _GEO_TYPES:
                    self._geo_cols[table].add(cn)
                    self._cast_cols_map[table].add(cn)
                    self._log("info", f"  [{table}] {dt} 컬럼 '{cn}' → STAsText() WKT 변환")
                elif dt in ("timestamp", "rowversion"):
                    self._rowver_cols[table].add(cn)
                    self._cast_cols_map[table].add(cn)
                    self._log("info", f"  [{table}] rowversion 컬럼 '{cn}' → BIGINT 변환")
                elif dt == "datetimeoffset":
                    self._dto_cols[table].add(cn)
                    self._cast_cols_map[table].add(cn)
                    self._log("info", f"  [{table}] datetimeoffset 컬럼 '{cn}' → DATETIME(6) 변환")
                elif dt in _BINARY_TYPES:
                    # binary/varbinary → Python에서 bytes로 변환 (특별 처리 불필요)
                    self._bin_cols[table].add(cn)
                    self._log("debug", f"  [{table}] {dt} 컬럼 '{cn}' → bytes 변환")
                elif dt in _UNSUPPORTED_TYPES:
                    _skip_cols.add(cn)
                    self._log("warn", f"  [{table}] 미지원 타입 컬럼 '{cn}' ({dt}) → NULL로 대체")

            # 2단계: error_hint에서 ODBC 오류 컬럼 인덱스 모두 추출
            import re as _re2
            _error_hint = getattr(self, '_remig_error_hint', '')
            if _error_hint and 'column-index=' in _error_hint:
                for _m in _re2.finditer(r'column-index=(\d+)', _error_hint):
                    _idx = int(_m.group(1))
                    if 0 <= _idx < len(cols):
                        _col_name = cols[_idx]["COLUMN_NAME"]
                        _skip_cols.add(_col_name)
                        self._log("warn", f"  [{table}] ODBC 오류 컬럼 [{_col_name}] (index={_idx}) → NULL로 대체")

            # 3단계: pyodbc description으로 실제 ODBC 타입 코드 확인
            # SELECT TOP 0으로 컬럼별 타입 코드를 미리 검사
            _UNSUPPORTED_ODBC_CODES = {-151, -155, -152, -153, -154, -150}
            try:
                _probe_cur = src_conn.cursor()
                _probe_cur.execute(f"SELECT TOP 0 * FROM [{table}]")
                self._log("debug", f"  [{table}] ODBC 사전 검사 — 컬럼 {len(_probe_cur.description)}개")
                for _i, _desc in enumerate(_probe_cur.description or []):
                    _col_name  = _desc[0]
                    _odbc_type = _desc[1]
                    # pyodbc type_code는 type 객체 — str/repr로 코드 추출
                    _type_str  = str(_odbc_type)
                    _type_int  = 0
                    if hasattr(_odbc_type, 'code'):
                        _type_int = int(_odbc_type.code)
                    elif isinstance(_odbc_type, int):
                        _type_int = _odbc_type
                    else:
                        # repr에서 숫자 추출 시도
                        import re as _re3
                        _m3 = _re3.search(r'-?\d+', _type_str)
                        if _m3:
                            _type_int = int(_m3.group())
                    self._log("debug", f"    col[{_i}] {_col_name}: odbc_type={_type_str} code={_type_int}")

                    _is_bytearray = (_type_str == "<class 'bytearray'>")
                    _is_unsupported = _type_int in _UNSUPPORTED_ODBC_CODES

                    if _is_bytearray:
                        # bytearray = binary/varbinary/datetimeoffset/rowversion 모두 포함
                        # 반드시 실제 타입 확인 후 처리
                        _real_dt = ""
                        for _c in cols:
                            if _c.get("COLUMN_NAME") == _col_name:
                                _real_dt = (_c.get("DATA_TYPE") or "").lower()
                                break

                        if _real_dt in ("binary", "varbinary", "image"):
                            # binary → 그냥 읽기 (bytes), _bin_cols에 추가
                            self._bin_cols[table].add(_col_name)
                            self._log("debug", f"  [{table}] binary [{_col_name}] → bytes 처리")
                        elif _real_dt in ("timestamp", "rowversion"):
                            # rowversion → BIGINT
                            self._cast_cols_map[table].add(_col_name)
                            self._rowver_cols[table].add(_col_name)
                            self._log("warn", f"  [{table}] rowversion [{_col_name}] → BIGINT 처리")
                        elif _real_dt == "hierarchyid":
                            # hierarchyid → ToString() 경로 문자열
                            self._hier_cols[table].add(_col_name)
                            self._cast_cols_map[table].add(_col_name)
                            self._log("warn", f"  [{table}] hierarchyid [{_col_name}] → ToString() 처리")
                        elif _real_dt == "sql_variant":
                            _skip_cols.add(_col_name)
                            self._log("warn", f"  [{table}] [{_col_name}] (sql_variant) → NULL 처리")
                        elif _real_dt == "datetimeoffset":
                            # datetimeoffset → SWITCHOFFSET UTC
                            self._cast_cols_map[table].add(_col_name)
                            self._dto_cols[table].add(_col_name)
                            self._log("warn", f"  [{table}] datetimeoffset [{_col_name}] → SWITCHOFFSET 처리")
                        else:
                            # 타입 불명 bytearray → 안전하게 bytes로
                            self._bin_cols[table].add(_col_name)
                            self._log("warn", f"  [{table}] 알 수 없는 bytearray [{_col_name}] (dt={_real_dt}) → bytes 처리")
                    elif _is_unsupported:
                        _skip_cols.add(_col_name)
                        self._log("warn", f"  [{table}] ODBC type {_type_int} 컬럼 [{_col_name}] (index={_i}) → NULL로 대체")
                _probe_cur.close()
            except Exception as _pe:
                self._log("warn", f"  [{table}] ODBC 타입 사전 검사 실패: {_pe}")

            # 최종 skip_cols를 맵에 저장 (SELECT 쿼리 생성 시 사용)
            self._skip_cols_map[table] = _skip_cols
            if _skip_cols:
                self._log("info", f"  [{table}] 총 {len(_skip_cols)}개 컬럼 NULL 대체: {sorted(_skip_cols)}")
            if self._cast_cols_map.get(table):
                self._log("info", f"  [{table}] CAST 컬럼: {sorted(self._cast_cols_map[table])}")
        else:
            raise Exception(f"지원하지 않는 소스 DB: {src_db_type}")

        if not cols:
            raise Exception(f"테이블 [{table}] 컬럼 정보 없음")
        # ── 테이블별 컬럼 처리 맵 — 매 호출마다 해당 테이블 초기화 ──
        # (초기화는 _migrate_table 시작에서 처리)

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
        # (FK/트리거 비활성화는 run()에서 전역으로 처리됨)

        if self.job.get("truncate_target", False):
            try:
                tc = tgt_conn.cursor()
                if tgt_is_mssql:
                    tc.execute(f"TRUNCATE TABLE [{table}]")
                else:
                    # MySQL: TRUNCATE 전 FK 체크 비활성화 이미 됨
                    tc.execute(f"TRUNCATE TABLE `{table}`")
                tgt_conn.commit()
                self._log("info", f"  [{table}] TRUNCATE 완료")
            except Exception as te:
                self._log("warn", f"  [{table}] TRUNCATE 실패 (무시): {te}")

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
            insert_sql   = (
            f"INSERT IGNORE INTO `{table}` ({cols_str}) VALUES ({placeholders})"
            if tgt_is_mysql else
            f"INSERT INTO `{table}` ({cols_str}) VALUES ({placeholders})"
        )

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
                # 미지원 타입 컬럼(geography 등)은 NULL로 대체
                _skip   = getattr(self, '_skip_cols_map', {}).get(table, set())
                _cast   = getattr(self, '_cast_cols_map', {}).get(table, set())
                _rowver = getattr(self, '_rowver_cols',   {}).get(table, set())
                _dto    = getattr(self, '_dto_cols',      {}).get(table, set())
                _geo    = getattr(self, '_geo_cols',      {}).get(table, set())
                _bin    = getattr(self, '_bin_cols',      {}).get(table, set())
                _hier   = getattr(self, '_hier_cols',     {}).get(table, set())
                sel_parts = []
                for c in col_names:
                    if c in _hier:
                        # hierarchyid → /1/2/3/ 경로 문자열 (skip보다 우선)
                        sel_parts.append(f"[{c}].ToString() AS [{c}]")
                    elif c in _skip:
                        sel_parts.append(f"NULL AS [{c}]")
                    elif c in _rowver:
                        sel_parts.append(f"CONVERT(BIGINT, CONVERT(VARBINARY(8), [{c}])) AS [{c}]")
                    elif c in _dto:
                        sel_parts.append(f"CONVERT(NVARCHAR(30), SWITCHOFFSET([{c}], '+00:00'), 120) AS [{c}]")
                    elif c in _geo:
                        sel_parts.append(f"[{c}].STAsText() AS [{c}]")
                    elif c in _bin:
                        sel_parts.append(f"[{c}]")
                    elif c in _cast:
                        sel_parts.append(f"CONVERT(NVARCHAR(100), [{c}]) AS [{c}]")
                    else:
                        sel_parts.append(f"[{c}]")
                sel = ", ".join(sel_parts)
                # PK 컬럼 찾기 (있으면 PK 정렬, 없으면 1번 컬럼)
                _pk_cols = [c["COLUMN_NAME"] for c in cols if c.get("COLUMN_KEY") == "PRI"]
                if _pk_cols:
                    _order = ", ".join(f"[{c}]" for c in _pk_cols)
                else:
                    _order = f"[{col_names[0]}]"
                _sql = (f"SELECT {sel} FROM [{table}] ORDER BY {_order} "
                        f"OFFSET {offset} ROWS FETCH NEXT {batch_size} ROWS ONLY")
                if offset == 0:  # 첫 배치만 로깅
                    self._log("debug", f"  [{table}] SELECT:\n{_sql[:500]}")
                src_cur.execute(_sql)
                rows = src_cur.fetchall()
                # MSSQL→MySQL: 컬럼 타입별 값 변환
                if tgt_is_mysql:
                    _col_types = {c["COLUMN_NAME"]: c["DATA_TYPE"].lower() for c in cols}
                    def _conv(col, val):
                        if val is None:
                            return None
                        ct = _col_types.get(col, "")
                        if ct in ("rowversion", "timestamp"):
                            return bytes(val).hex() if isinstance(val, (bytes, bytearray)) else None
                        if ct in ("binary", "varbinary", "image"):
                            return bytes(val) if isinstance(val, (bytes, bytearray)) else val
                        if ct in ("geography", "geometry", "hierarchyid", "sql_variant", "xml"):
                            return str(val)
                        if ct == "uniqueidentifier":
                            return str(val)
                        if ct == "datetimeoffset":
                            return val.isoformat() if hasattr(val, "isoformat") else str(val)
                        if hasattr(val, "__class__") and val.__class__.__name__ == "Decimal":
                            return float(val)
                        return val
                    batch_data = [
                        tuple(_conv(col_names[i], v) for i, v in enumerate(r))
                        for r in rows
                    ]
                else:
                    batch_data = [tuple(r) for r in rows]

            if not rows: break

            rows_inserted = 0
            try:
                tgt_cur.executemany(insert_sql, batch_data)
                tgt_conn.commit()
                rows_inserted = len(rows)
            except Exception as e:
                err_msg = str(e)[:300]
                # 트리거 관련 오류 → 트리거 비활성화 후 재시도
                # 건별 재시도 (트리거는 전역에서 이미 비활성화됨)
                if True:
                    self._log("error", f"배치 INSERT 실패 [{table}] offset={offset}: {err_msg}")
                    if self.job["on_error"] == "abort": raise
                    # 한 건씩 재시도 — 오류 행만 건너뜀
                    _row_ok = 0
                    _row_fail = 0
                    try:
                        tgt_conn.rollback()
                        for _single in batch_data:
                            try:
                                tgt_cur.execute(insert_sql, _single)
                                tgt_conn.commit()
                                _row_ok += 1
                            except Exception as _se:
                                _row_fail += 1
                                try: tgt_conn.rollback()
                                except: pass
                        rows_inserted = _row_ok
                        self._log("warn", f"  [{table}] 건별 재시도: 성공 {_row_ok:,}건 / 실패 {_row_fail:,}건")
                    except Exception as _re:
                        self._log("error", f"  [{table}] 건별 재시도 실패: {_re}")
                    self.job["rows_error"] += _row_fail
                # item_statuses에 오류 누적 기록
                prev = self.job["item_statuses"].get(table, {})
                prev_err = prev.get("batch_errors") or []
                if not any(err_msg[:80] in e for e in prev_err):
                    prev_err.append(f"offset={offset}: {err_msg}")
                self.job["item_statuses"][table] = {
                    **prev,
                    "batch_errors": prev_err[-10:],  # 최대 10개
                    "batch_error_rows": (prev.get("batch_error_rows") or 0) + len(rows),
                    "error": f"배치 오류 {len(prev_err)}건, {(prev.get('batch_error_rows') or 0)+len(rows):,}행 실패"
                }
                try: tgt_conn.rollback()
                except: pass

            done   += len(rows)
            offset += batch_size
            self.job["current_table_rows_done"] = done
            # 소스/타겟 건수 분리 추적 (실제 INSERT된 건수만 누적)
            st = self.job["item_statuses"].get(table, {})
            self.job["item_statuses"][table] = {
                **st,
                "rows_src": done,
                "rows_tgt": st.get("rows_tgt", 0) + rows_inserted,
                "rows_tgt_final": False,  # 아직 진행중
            }
            elapsed = time.monotonic() - start_t
            if elapsed > 0: self.job["speed"] = int(done / elapsed)
            # 10% 단위로 진행 로그
            if row_count and done % max(1, (row_count // 10)) < batch_size:
                pct = min(100, round(done / row_count * 100))
                self._log("debug", f"  [{table}] {pct}% — {done:,}/{row_count:,} rows ({self.job['speed']:,} rows/s)")
            rows_total = self.job.get("rows_total", 0)
            if rows_total > 0:
                self.job["progress"] = min(99.9, round(
                    (self.job["rows_processed"] + done) / rows_total * 100, 1))
            else:
                # rows_total 추정 실패 시 → 테이블 진행 기반
                t_done  = self.job.get("table_done", 0)
                t_total = max(self.job.get("table_total", 1), 1)
                self.job["progress"] = min(99.9, round(t_done / t_total * 100, 1))

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
        now = datetime.utcnow().strftime("%H:%M:%S")
        entry = {"time": now, "level": level,
                 "tag": f"Job#{self.jid[:6]}", "message": msg}
        _job_logs.setdefault(self.jid, []).append(entry)
        # 파일/콘솔 로거 출력
        log_fn = {"info": logger.info, "warn": logger.warning,
                  "error": logger.error, "debug": logger.debug}.get(level, logger.info)
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
    j["obj_mode"]        = body.get("obj_mode","drop_recreate")   # drop_recreate | skip_existing
    j["view_mode"]       = body.get("view_mode","drop_recreate")
    j["table_mode"]      = body.get("table_mode","schema_data")
    j["ddl_engine"]      = body.get("ddl_engine","auto")
    j["obj_engine"]      = body.get("obj_engine","auto")
    j["drop_table"]      = body.get("drop_table", False)
    j["parallel_workers"]= body.get("parallel_workers", 4)

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
    try:
        engine.run()
    except Exception as e:
        import traceback
        logger.error("이관 엔진 치명적 오류 [%s]: %s\n%s", jid[:8], e, traceback.format_exc())
        job_obj["status"] = "error"
        job_obj["error"] = str(e)[:300]
    finally:
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


@router.post("/{jid}/remig-object")
def remig_object(jid: str, body: dict):
    """오브젝트(트리거/함수/프로시저/뷰) 재이관"""
    j = _jobs.get(jid)
    if not j: raise HTTPException(404, "Job 없음")
    name      = body.get("name")
    obj_type  = (body.get("type") or "trigger").upper()
    mode      = body.get("mode", "drop_recreate")
    error_hint = body.get("error_hint", "")
    if not name: raise HTTPException(400, "name 필수")

    import threading
    def _run():
        engine = MigrationEngine(j)
        try:
            src_conn = engine._connect_src()
            tgt_conn = engine._connect_tgt()
            if not src_conn or not tgt_conn:
                j["item_statuses"][name] = {"type":obj_type.lower(),"status":"error","rows":0,
                    "error":"DB 연결 실패","started_at":None,"finished_at":datetime.utcnow().isoformat()}
                return

            j["item_statuses"][name] = {"type":obj_type.lower(),"status":"running","rows":0,
                "error":None,"started_at":datetime.utcnow().isoformat(),"finished_at":None}
            _jobs.set(jid, j)

            if mode == "ai":
                # AI 변환
                try:
                    from app.api.routes.schema import _ai_convert_ddl
                    cur_src = src_conn.cursor()
                    cur_src.execute("SELECT OBJECT_DEFINITION(OBJECT_ID(?))", [name])
                    row = cur_src.fetchone()
                    src_ddl = (row[0] if row else "") or ""
                    if src_ddl:
                        full_ctx = f"오류: {error_hint}" if error_hint else ""
                        result = _ai_convert_ddl(src_ddl, obj_type, name,
                            j.get("src_db","mssql"), j.get("tgt_db","mysql"), full_ctx)
                        stmts = result.get("statements", [])
                        if stmts:
                            cur_tgt = tgt_conn.cursor()
                            for stmt in stmts:
                                if stmt.strip():
                                    cur_tgt.execute(stmt)
                                    tgt_conn.commit()
                            j["item_statuses"][name].update({"status":"done","finished_at":datetime.utcnow().isoformat()})
                            engine._log("info", f"✓ [{name}] AI 재이관 완료")
                            return
                except Exception as ae:
                    engine._log("warn", f"[{name}] AI 변환 실패: {ae} — 일반 재이관으로 폴백")

            # 일반 재이관 — _migrate_objects 활용
            objects = {obj_type.lower() + "s": [name]}
            if obj_type == "FUNCTION": objects = {"functions": [name]}
            elif obj_type == "PROCEDURE": objects = {"procedures": [name]}
            elif obj_type == "TRIGGER": objects = {"triggers": [name]}
            elif obj_type == "VIEW": objects = {"views": [name]}

            engine._migrate_objects(src_conn, tgt_conn, objects, True)
            st = j["item_statuses"].get(name, {})
            if st.get("status") != "error":
                j["item_statuses"][name].update({"status":"done","finished_at":datetime.utcnow().isoformat()})
                engine._log("info", f"✓ [{name}] 재이관 완료")
        except Exception as e:
            j["item_statuses"][name] = {"type":obj_type.lower(),"status":"error","rows":0,
                "error":str(e)[:300],"started_at":None,"finished_at":datetime.utcnow().isoformat()}
            engine._log("error", f"✗ [{name}] 재이관 실패: {e}")
        finally:
            _jobs.set(jid, j)
            try: src_conn.close()
            except: pass
            try: tgt_conn.close()
            except: pass

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "name": name, "type": obj_type, "mode": mode}


@router.post("/{jid}/remig-table")
def remig_table(jid: str, body: dict):
    """특정 테이블의 스키마를 재이관"""
    j = _jobs.get(jid)
    if not j: raise HTTPException(404, "Job 없음")
    table      = body.get("table")
    mode       = body.get("mode", "skip_geo")   # drop_recreate | skip_geo | ai
    error_hint    = body.get("error_hint", "")
    error_history = body.get("error_history", [])  # [{attempt, error, ts}, ...]
    # 원본 Job 설정 오버라이드 (프론트에서 전달 시 적용)
    override_table_mode      = body.get("table_mode")       # schema_data | data_only | schema_only
    override_drop_table      = body.get("drop_table")
    override_truncate_target = body.get("truncate_target")
    override_create_table    = body.get("create_table")
    if not table: raise HTTPException(400, "table 필수")

    # 누적 오류 히스토리 → AI 프롬프트용 텍스트 생성
    def _build_error_context(hint: str, history: list) -> str:
        parts = []
        if history:
            parts.append("=== 재이관 시도 오류 히스토리 ===")
            for h in history:
                parts.append(f"시도 #{h.get('attempt','')} ({h.get('ts','')}): {h.get('error','')}")
            parts.append("================================")
        if hint and (not history or hint not in str(history)):
            parts.append(f"현재 오류: {hint}")
        return "\n".join(parts) if parts else hint

    import threading

    def _drop_table(tgt_conn, tgt_db, table_name):
        try:
            cur = tgt_conn.cursor()
            if tgt_db in ("mssql","azure","sqlserver"):
                cur.execute(f"IF OBJECT_ID(N'[dbo].[{table_name}]', N'U') IS NOT NULL DROP TABLE [dbo].[{table_name}]")
            else:
                cur.execute(f"DROP TABLE IF EXISTS `{table_name}`")
            tgt_conn.commit()
        except Exception as de:
            logger.warning("[%s] DROP 실패 (무시): %s", table_name, de)

    def _run():
        engine = MigrationEngine(j)
        # error_hint/history를 엔진에 주입 → 미지원 컬럼 자동 스킵
        full_hint = _build_error_context(error_hint, error_history)
        engine._remig_error_hint = full_hint
        try:
            src_conn = engine._connect_src()
            tgt_conn = engine._connect_tgt()
            if not src_conn or not tgt_conn:
                j["item_statuses"][table] = {"type":"table","status":"error","rows":0,
                    "error":"DB 연결 실패","started_at":None,"finished_at":datetime.utcnow().isoformat()}
                return

            tgt_db = j.get("tgt_db","mysql")
            engine._log("info", f"[{table}] 재이관 시작 — mode={mode}")
            if full_hint:
                engine._log("info", f"[{table}] 오류 컨텍스트 적용:\n{full_hint[:200]}")

            # ── AI 이관 ──────────────────────────────────────────
            if mode == "ai":
                engine._log("info", f"[{table}] AI 스키마 분석 중...")
                _drop_table(tgt_conn, tgt_db, table)
                # schema.py의 AI 변환 활용
                try:
                    from app.api.routes.schema import _ai_convert_ddl
                    src_cur = src_conn.cursor()
                    # 소스 DDL 가져오기
                    src_db_type = j.get("src_db","mssql")
                    if src_db_type in ("mssql","azure","sqlserver"):
                        src_cur.execute("SELECT OBJECT_DEFINITION(OBJECT_ID(?))", [table])
                        row = src_cur.fetchone()
                        src_ddl = (row[0] if row else "") or ""
                        if not src_ddl:
                            # sys.columns로 CREATE TABLE 재구성
                            src_cur.execute("""
                                SELECT c.name, t.name as type_name, c.max_length, c.precision,
                                       c.scale, c.is_nullable, c.is_identity
                                FROM sys.columns c
                                JOIN sys.types t ON c.user_type_id=t.user_type_id
                                WHERE c.object_id=OBJECT_ID(?)
                                ORDER BY c.column_id
                            """, [table])
                            cols = src_cur.fetchall()
                            src_ddl = f"-- {table} 컬럼 정보\n"
                            for col in cols:
                                nm = col[0] if not isinstance(col,dict) else col['name']
                                tp = col[1] if not isinstance(col,dict) else col['type_name']
                                src_ddl += f"  [{nm}] [{tp}]\n"
                    else:
                        src_cur.execute(f"SHOW CREATE TABLE `{table}`")
                        row = src_cur.fetchone()
                        src_ddl = (row[1] if row else "") or ""

                    engine._log("info", f"[{table}] AI 변환 요청 중...")
                    # AI DDL 변환 (schema.py 활용)
                    # 누적 오류 히스토리 포함한 컨텍스트 생성
                    full_error_ctx = _build_error_context(error_hint, error_history)
                    engine._log("info", f"[{table}] AI 오류 컨텍스트:\n{full_error_ctx[:300]}")
                    result = _ai_convert_ddl(
                        src_ddl, "TABLE", table,
                        j.get("src_db","mssql"), j.get("tgt_db","mysql"),
                        full_error_ctx
                    )
                    stmts = result.get("statements", [])
                    if stmts:
                        cur_tgt = tgt_conn.cursor()
                        for stmt in stmts:
                            if stmt.strip():
                                cur_tgt.execute(stmt)
                                tgt_conn.commit()
                        engine._log("info", f"[{table}] AI 스키마 생성 완료")
                    else:
                        engine._log("warn", f"[{table}] AI 변환 결과 없음 — 자체 이관으로 폴백")
                except Exception as ae:
                    engine._log("warn", f"[{table}] AI 변환 실패: {ae} — 자체 이관으로 폴백")

            # ── 원본 설정 그대로 ─────────────────────────────────
            elif mode == "original":
                # Job 원본 설정 적용
                orig_table_mode = j.get("table_mode", "schema_data")
                orig_drop       = j.get("drop_table", False)
                orig_truncate   = j.get("truncate_target", False)
                engine._log("info", f"[{table}] 원본 설정 적용 — table_mode={orig_table_mode} drop={orig_drop} truncate={orig_truncate}")
                if orig_drop:
                    _drop_table(tgt_conn, tgt_db, table)
                    engine._log("info", f"[{table}] DROP 완료")

            # ── DROP 후 재생성 ────────────────────────────────────
            elif mode == "drop_recreate":
                _drop_table(tgt_conn, tgt_db, table)
                engine._log("info", f"[{table}] DROP 완료 — 재이관 시작")

            # ── skip_geo (기본): geography 등 미지원 타입 스킵 ──
            else:
                engine._log("info", f"[{table}] 미지원 컬럼 스킵 모드로 재이관")

            # ── 원본 설정 오버라이드 적용 ─────────────────────────
            if override_table_mode is not None:
                j["table_mode"] = override_table_mode
            if override_drop_table is not None:
                j["drop_table"] = override_drop_table
            if override_truncate_target is not None:
                j["truncate_target"] = override_truncate_target
            if override_create_table is not None:
                j["create_table"] = override_create_table

            # ── 실제 데이터 이관 ──────────────────────────────────
            j["item_statuses"][table] = {"type":"table","status":"running","rows":0,
                "error":None,"started_at":datetime.utcnow().isoformat(),"finished_at":None}
            j["current_table"] = table
            _jobs.set(j["id"], j)  # 즉시 저장 → UI 반영

            try:
                done = engine._migrate_table(src_conn, tgt_conn, table)
                # 이전 오류 건수 차감
                prev_st = j["item_statuses"].get(table, {})
                prev_err_rows = prev_st.get("batch_error_rows", 0)
                if prev_err_rows > 0:
                    j["rows_error"] = max(0, j.get("rows_error", 0) - prev_err_rows)
                j["item_statuses"][table].update({
                    "status":"done","rows":done,
                    "rows_src": done, "rows_tgt": done,
                    "batch_errors": [], "batch_error_rows": 0,
                    "finished_at":datetime.utcnow().isoformat(),"error":None
                })
                engine._log("info", f"✓ [{table}] 재이관 완료 — {done:,} rows")
                # job 전체 상태 재계산
                all_st = j["item_statuses"].values()
                if all(s.get("status") in ("done","skip") for s in all_st if s.get("type")=="table"):
                    if not any(s.get("status")=="running" for s in all_st):
                        j["status"] = "completed"
                        j["progress"] = 100
            except Exception as me:
                j["item_statuses"][table].update({"status":"error","error":str(me)[:300],
                    "finished_at":datetime.utcnow().isoformat()})
                engine._log("error", f"✗ [{table}] 재이관 실패: {me}")
            finally:
                j["current_table"] = ""
                _jobs.set(j["id"], j)   # ← 완료/실패 상태 즉시 저장
                try: src_conn.close()
                except: pass
                try: tgt_conn.close()
                except: pass
        except Exception as e:
            engine._log("error", f"재이관 엔진 오류: {e}")

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "table": table, "mode": mode}


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
