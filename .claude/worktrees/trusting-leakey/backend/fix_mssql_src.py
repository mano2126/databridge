"""
fix_mssql_src.py
backend 폴더에서 실행: python fix_mssql_src.py

1. jobs.py _log() → logging 모듈도 함께 기록 (백엔드 로그 파일에 남도록)
2. jobs.py _get_all_tables() → MSSQL 소스 지원
3. jobs.py _estimate_total_rows() → MSSQL 소스 지원
4. jobs.py _migrate_table() 상단 → MSSQL 소스에서 컬럼 정보 조회 지원
"""
import shutil, ast
from datetime import datetime

path = 'app/api/routes/jobs.py'
bak  = path + '.' + datetime.now().strftime('%H%M%S') + '.bak'
shutil.copy2(path, bak)
print(f'백업: {bak}')

content = open(path, encoding='utf-8').read()

# ── 1. _log 메서드에 logging 추가 ─────────────────────────
OLD_LOG = '''    def _log(self, level: str, msg: str):
        now = datetime.utcnow().strftime("%H:%M:%S")
        _job_logs.setdefault(self.jid, []).append({
            "time": now, "level": level,
            "tag": f"Job#{self.jid[:6]}", "message": msg
        })'''

NEW_LOG = '''    def _log(self, level: str, msg: str):
        import logging as _logging
        now = datetime.utcnow().strftime("%H:%M:%S")
        _job_logs.setdefault(self.jid, []).append({
            "time": now, "level": level,
            "tag": f"Job#{self.jid[:6]}", "message": msg
        })
        # 백엔드 로그 파일에도 기록
        _logger = _logging.getLogger("databridge.jobs")
        _lvl = {"info": _logging.INFO, "warn": _logging.WARNING,
                "error": _logging.ERROR, "debug": _logging.DEBUG}.get(level, _logging.INFO)
        _logger.log(_lvl, "[Job#%s] %s", self.jid[:6], msg)'''

if OLD_LOG in content:
    content = content.replace(OLD_LOG, NEW_LOG)
    print('_log 수정 완료')
else:
    print('주의: _log 패턴 없음')

# ── 2. _get_all_tables — MSSQL 지원 ─────────────────────
OLD_TABLES = '''    def _get_all_tables(self, src_conn) -> list:
        cur = src_conn.cursor()
        cur.execute("""
            SELECT TABLE_NAME FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE='BASE TABLE'
            ORDER BY TABLE_NAME
        """)
        return [r["TABLE_NAME"] for r in cur.fetchall()]'''

NEW_TABLES = '''    def _get_all_tables(self, src_conn) -> list:
        db_type = self.job.get("src_db", "mysql")
        cur = src_conn.cursor()
        if db_type in ("mssql", "azure"):
            cur.execute("""
                SELECT t.name AS TABLE_NAME
                FROM sys.tables t
                JOIN sys.schemas s ON t.schema_id = s.schema_id
                WHERE s.name = 'dbo'
                ORDER BY t.name
            """)
            rows = cur.fetchall()
            # pyodbc 커서는 dict가 아닌 tuple 반환
            return [r[0] if not isinstance(r, dict) else r["TABLE_NAME"] for r in rows]
        else:
            cur.execute("""
                SELECT TABLE_NAME FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE='BASE TABLE'
                ORDER BY TABLE_NAME
            """)
            return [r["TABLE_NAME"] for r in cur.fetchall()]'''

if OLD_TABLES in content:
    content = content.replace(OLD_TABLES, NEW_TABLES)
    print('_get_all_tables 수정 완료')
else:
    print('주의: _get_all_tables 패턴 없음')

# ── 3. _estimate_total_rows — MSSQL 지원 ────────────────
OLD_EST = '''    def _estimate_total_rows(self, src_conn, tables: list) -> int:
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
        return total'''

NEW_EST = '''    def _estimate_total_rows(self, src_conn, tables: list) -> int:
        db_type = self.job.get("src_db", "mysql")
        cur = src_conn.cursor()
        total = 0
        db = self.job.get("src_database", "")
        for tbl in tables:
            try:
                if db_type in ("mssql", "azure"):
                    cur.execute(
                        "SELECT SUM(p.rows) FROM sys.tables t "
                        "JOIN sys.partitions p ON t.object_id=p.object_id "
                        "AND p.index_id IN(0,1) WHERE t.name=?", (tbl,)
                    )
                    r = cur.fetchone()
                    total += (r[0] or 0) if r else 0
                else:
                    cur.execute(
                        "SELECT TABLE_ROWS FROM information_schema.TABLES "
                        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
                        (db, tbl)
                    )
                    r = cur.fetchone()
                    total += (r["TABLE_ROWS"] or 0) if r else 0
            except:
                pass
        return total'''

if OLD_EST in content:
    content = content.replace(OLD_EST, NEW_EST)
    print('_estimate_total_rows 수정 완료')
else:
    print('주의: _estimate_total_rows 패턴 없음')

# ── 4. _migrate_table 컬럼 조회 — MSSQL 소스 지원 ────────
OLD_COL = '''        src_cur = src_conn.cursor()

        # 컬럼 정보
        db = self.job.get("src_database","")
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

        if not cols:
            raise Exception(f"테이블 [{table}] 컬럼 정보 없음")

        col_names = [c["COLUMN_NAME"] for c in cols]'''

NEW_COL = '''        src_db_type = self.job.get("src_db", "mysql")
        tgt_db_type = self.job.get("tgt_db", "mssql")
        src_cur = src_conn.cursor()

        # 컬럼 정보
        db = self.job.get("src_database", "")
        if src_db_type in ("mssql", "azure"):
            src_cur.execute("""
                SELECT
                    c.name AS COLUMN_NAME,
                    tp.name AS DATA_TYPE,
                    tp.name AS COLUMN_TYPE,
                    c.max_length AS CHARACTER_MAXIMUM_LENGTH,
                    c.precision AS NUMERIC_PRECISION,
                    c.scale AS NUMERIC_SCALE,
                    CASE WHEN c.is_nullable=1 THEN 'YES' ELSE 'NO' END AS IS_NULLABLE,
                    NULL AS COLUMN_DEFAULT,
                    CASE WHEN ic.object_id IS NOT NULL THEN 'PRI' ELSE '' END AS COLUMN_KEY,
                    CASE WHEN c.is_identity=1 THEN 'auto_increment' ELSE '' END AS EXTRA
                FROM sys.columns c
                JOIN sys.types tp ON c.user_type_id = tp.user_type_id
                JOIN sys.objects o ON c.object_id = o.object_id
                LEFT JOIN sys.indexes i ON o.object_id=i.object_id AND i.is_primary_key=1
                LEFT JOIN sys.index_columns ic
                    ON i.object_id=ic.object_id AND i.index_id=ic.index_id
                    AND c.column_id=ic.column_id
                WHERE o.name=? AND o.type='U'
                ORDER BY c.column_id
            """, (table,))
            raw = src_cur.fetchall()
            # pyodbc는 tuple 반환 — dict로 변환
            col_keys = ["COLUMN_NAME","DATA_TYPE","COLUMN_TYPE",
                        "CHARACTER_MAXIMUM_LENGTH","NUMERIC_PRECISION","NUMERIC_SCALE",
                        "IS_NULLABLE","COLUMN_DEFAULT","COLUMN_KEY","EXTRA"]
            cols = [dict(zip(col_keys, r)) for r in raw]
        else:
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

        if not cols:
            raise Exception(f"테이블 [{table}] 컬럼 정보 없음")

        col_names = [c["COLUMN_NAME"] for c in cols]'''

if OLD_COL in content:
    content = content.replace(OLD_COL, NEW_COL)
    print('_migrate_table 컬럼 조회 수정 완료')
else:
    print('주의: _migrate_table 컬럼 조회 패턴 없음')

# ── 5. SELECT/INSERT 쿼리 — MSSQL 소스 지원 ─────────────
OLD_SELECT = '''        while offset < row_count:
            if self._stop:
                break
            while self._pause:
                time.sleep(0.3)

            src_cur.execute(
                f"SELECT {', '.join(['`'+c+'`' for c in col_names])} "
                f"FROM `{table}` LIMIT {batch_size} OFFSET {offset}"
            )
            rows = src_cur.fetchall()
            if not rows:
                break

            batch_data = [tuple(r[c] for c in col_names) for r in rows]'''

NEW_SELECT = '''        while offset < row_count:
            if self._stop:
                break
            while self._pause:
                time.sleep(0.3)

            if src_db_type in ("mssql", "azure"):
                col_str = ", ".join([f"[{c}]" for c in col_names])
                src_cur.execute(
                    f"SELECT {col_str} FROM [{table}] "
                    f"ORDER BY (SELECT NULL) "
                    f"OFFSET {offset} ROWS FETCH NEXT {batch_size} ROWS ONLY"
                )
                raw_rows = src_cur.fetchall()
                rows = [dict(zip(col_names, r)) for r in raw_rows]
            else:
                src_cur.execute(
                    f"SELECT {', '.join(['`'+c+'`' for c in col_names])} "
                    f"FROM `{table}` LIMIT {batch_size} OFFSET {offset}"
                )
                rows = src_cur.fetchall()
            if not rows:
                break

            batch_data = [tuple(r[c] for c in col_names) for r in rows]'''

if OLD_SELECT in content:
    content = content.replace(OLD_SELECT, NEW_SELECT)
    print('SELECT 배치 쿼리 수정 완료')
else:
    print('주의: SELECT 배치 쿼리 패턴 없음')

# ── 6. row_count 조회 — MSSQL 소스 지원 ─────────────────
OLD_CNT = '''        # 소스 row 수
        src_cur.execute(f"SELECT COUNT(*) AS cnt FROM `{table}`")
        row_count = src_cur.fetchone()["cnt"]'''

NEW_CNT = '''        # 소스 row 수
        if src_db_type in ("mssql", "azure"):
            src_cur.execute(f"SELECT COUNT(*) FROM [{table}]")
            r = src_cur.fetchone()
            row_count = r[0] if r else 0
        else:
            src_cur.execute(f"SELECT COUNT(*) AS cnt FROM `{table}`")
            row_count = src_cur.fetchone()["cnt"]'''

if OLD_CNT in content:
    content = content.replace(OLD_CNT, NEW_CNT)
    print('row_count 조회 수정 완료')
else:
    print('주의: row_count 조회 패턴 없음')

# ── 7. INSERT 타겟 — MySQL 타겟 지원 ─────────────────────
OLD_INS = '''        cols_str = ", ".join([f"[{c}]" for c in col_names])
        placeholders = ", ".join(["?" for _ in col_names])
        insert_sql = f"INSERT INTO [{table}] ({cols_str}) VALUES ({placeholders})"'''

NEW_INS = '''        if tgt_db_type in ("mssql", "azure"):
            cols_str = ", ".join([f"[{c}]" for c in col_names])
            placeholders = ", ".join(["?" for _ in col_names])
            insert_sql = f"INSERT INTO [{table}] ({cols_str}) VALUES ({placeholders})"
        else:
            cols_str = ", ".join([f"`{c}`" for c in col_names])
            placeholders = ", ".join(["%s" for _ in col_names])
            insert_sql = f"INSERT INTO `{table}` ({cols_str}) VALUES ({placeholders})"'''

if OLD_INS in content:
    content = content.replace(OLD_INS, NEW_INS)
    print('INSERT SQL 수정 완료')
else:
    print('주의: INSERT SQL 패턴 없음')

# ── 문법 확인 및 저장 ─────────────────────────────────────
try:
    ast.parse(content)
    print('✓ 문법 OK')
except SyntaxError as e:
    print(f'✗ 문법 오류: {e}')
    print(f'복구: copy {bak} {path}')
    exit(1)

open(path, 'w', encoding='utf-8').write(content)
print('\n완료! 백엔드 재시작:')
print('python -m uvicorn main:app --port 8000')
