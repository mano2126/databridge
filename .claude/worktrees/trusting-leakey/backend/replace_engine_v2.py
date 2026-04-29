"""
replace_engine_v2.py
backend 폴더에서 실행: python replace_engine_v2.py

MigrationEngine 핵심 메서드 완전 교체
- MSSQL/MySQL/PostgreSQL 소스/타겟 모두 지원
- f-string 이스케이프 문제 수정 버전
"""
import shutil, ast
from datetime import datetime

path = 'app/api/routes/jobs.py'
bak  = path + '.' + datetime.now().strftime('%H%M%S') + '.bak'
shutil.copy2(path, bak)

content = open(path, encoding='utf-8').read()

START = '\n    def _connect_src(self):'
END   = '\n    def stop(self):'

idx_start = content.find(START)
idx_end   = content.find(END)

if idx_start == -1 or idx_end == -1:
    print(f'범위 탐색 실패 start={idx_start} end={idx_end}')
    exit(1)

print(f'교체 범위: {idx_start} ~ {idx_end} ({idx_end-idx_start} bytes)')

# ── 새 메서드 블록 (f-string 이스케이프 없이 직접 작성) ──────
BLOCK = r'''
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
                if tgt_db_type in ("mssql", "azure"):
                    tc.execute(f"TRUNCATE TABLE [{table}]")
                elif tgt_db_type in ("postgresql", "redshift"):
                    tc.execute(f'TRUNCATE TABLE "{table}"')
                else:
                    tc.execute(f"TRUNCATE TABLE `{table}`")
                tgt_conn.commit()
            except Exception:
                pass

        tgt_cur = tgt_conn.cursor()
        has_identity = any(
            "auto_increment" in (c.get("EXTRA", "") or "").lower() or
            c.get("is_identity") == 1
            for c in cols
        )
        if tgt_db_type in ("mssql", "azure"):
            if has_identity:
                try:
                    tgt_cur.execute(f"SET IDENTITY_INSERT [{table}] ON")
                except Exception:
                    pass
            cols_str     = ", ".join(f"[{c}]" for c in col_names)
            placeholders = ", ".join("?" for _ in col_names)
            insert_sql   = f"INSERT INTO [{table}] ({cols_str}) VALUES ({placeholders})"
        elif tgt_db_type in ("postgresql", "redshift"):
            cols_str     = ", ".join(f'"{c}"' for c in col_names)
            placeholders = ", ".join("%s" for _ in col_names)
            insert_sql   = f'INSERT INTO "{table}" ({cols_str}) VALUES ({placeholders})'
        else:
            cols_str     = ", ".join(f"`{c}`" for c in col_names)
            placeholders = ", ".join("%s" for _ in col_names)
            insert_sql   = f"INSERT INTO `{table}` ({cols_str}) VALUES ({placeholders})"

        batch_size = self.job.get("batch_size", 5000)
        offset = 0
        done = 0
        start_t = time.monotonic()

        while offset < row_count:
            if self._stop:
                break
            while self._pause:
                time.sleep(0.3)

            rows = self._fetch_batch(src_cur, src_db_type, table, col_names, batch_size, offset)
            if not rows:
                break

            batch_data = [
                tuple(
                    r[c] if isinstance(r, dict) else r[i]
                    for i, c in enumerate(col_names)
                )
                for r in rows
            ]

            try:
                tgt_cur.executemany(insert_sql, batch_data)
                tgt_conn.commit()
            except Exception as e:
                self._log("error", f"배치 INSERT 실패 [{table}] offset={offset}: {str(e)[:200]}")
                try:
                    tgt_conn.rollback()
                except Exception:
                    pass
                if self.job.get("on_error") == "abort":
                    raise
                self.job["rows_error"] += len(rows)

            done   += len(rows)
            offset += batch_size
            self.job["current_table_rows_done"] = done
            elapsed = time.monotonic() - start_t
            if elapsed > 0:
                self.job["speed"] = int(done / elapsed)
            total = max(self.job.get("rows_total", 1), 1)
            self.job["progress"] = round(
                (self.job.get("rows_processed", 0) + done) / total * 100, 1
            )

        if tgt_db_type in ("mssql", "azure") and has_identity:
            try:
                tgt_cur.execute(f"SET IDENTITY_INSERT [{table}] OFF")
            except Exception:
                pass

        return done

    def _get_columns(self, cur, db_type, db, table) -> list:
        try:
            if db_type in ("mssql", "azure"):
                cur.execute("""
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
                    JOIN sys.types tp ON c.user_type_id=tp.user_type_id
                    JOIN sys.objects o ON c.object_id=o.object_id
                    LEFT JOIN sys.indexes i ON o.object_id=i.object_id AND i.is_primary_key=1
                    LEFT JOIN sys.index_columns ic
                        ON i.object_id=ic.object_id AND i.index_id=ic.index_id
                        AND c.column_id=ic.column_id
                    WHERE o.name=? AND o.type='U'
                    ORDER BY c.column_id
                """, (table,))
                raw  = cur.fetchall()
                keys = ["COLUMN_NAME","DATA_TYPE","COLUMN_TYPE",
                        "CHARACTER_MAXIMUM_LENGTH","NUMERIC_PRECISION","NUMERIC_SCALE",
                        "IS_NULLABLE","COLUMN_DEFAULT","COLUMN_KEY","EXTRA"]
                return [dict(zip(keys, r)) for r in raw]
            elif db_type in ("postgresql", "redshift"):
                cur.execute("""
                    SELECT column_name, data_type, data_type,
                           character_maximum_length, numeric_precision, numeric_scale,
                           is_nullable, column_default, '', ''
                    FROM information_schema.columns
                    WHERE table_schema='public' AND table_name=%s
                    ORDER BY ordinal_position
                """, (table,))
                raw  = cur.fetchall()
                keys = ["COLUMN_NAME","DATA_TYPE","COLUMN_TYPE",
                        "CHARACTER_MAXIMUM_LENGTH","NUMERIC_PRECISION","NUMERIC_SCALE",
                        "IS_NULLABLE","COLUMN_DEFAULT","COLUMN_KEY","EXTRA"]
                return [dict(zip(keys, r)) for r in raw]
            else:
                cur.execute("""
                    SELECT COLUMN_NAME, DATA_TYPE, COLUMN_TYPE,
                           CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE,
                           IS_NULLABLE, COLUMN_DEFAULT, COLUMN_KEY, EXTRA
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
                    ORDER BY ORDINAL_POSITION
                """, (db, table))
                return cur.fetchall()
        except Exception as e:
            self._log("error", f"[{table}] 컬럼 조회 실패: {e}")
            return []

    def _count_rows(self, cur, db_type, table) -> int:
        try:
            if db_type in ("mssql", "azure"):
                cur.execute(f"SELECT COUNT(*) FROM [{table}]")
            elif db_type in ("postgresql", "redshift"):
                cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            else:
                cur.execute(f"SELECT COUNT(*) AS cnt FROM `{table}`")
            r = cur.fetchone()
            if not r:
                return 0
            return int(r[0] if not isinstance(r, dict) else r.get("cnt", list(r.values())[0]))
        except Exception as e:
            self._log("warn", f"[{table}] row count 실패: {e}")
            return 0

    def _fetch_batch(self, cur, db_type, table, col_names, batch_size, offset) -> list:
        try:
            if db_type in ("mssql", "azure"):
                cols_str = ", ".join(f"[{c}]" for c in col_names)
                cur.execute(
                    f"SELECT {cols_str} FROM [{table}] "
                    f"ORDER BY (SELECT NULL) "
                    f"OFFSET {offset} ROWS FETCH NEXT {batch_size} ROWS ONLY"
                )
                raw = cur.fetchall()
                return [dict(zip(col_names, r)) if not isinstance(r, dict) else r for r in raw]
            elif db_type in ("postgresql", "redshift"):
                cols_str = ", ".join(f'"{c}"' for c in col_names)
                cur.execute(
                    f'SELECT {cols_str} FROM "{table}" '
                    f'LIMIT {batch_size} OFFSET {offset}'
                )
                raw = cur.fetchall()
                return [dict(zip(col_names, r)) if not isinstance(r, dict) else r for r in raw]
            else:
                cols_str = ", ".join(f"`{c}`" for c in col_names)
                cur.execute(
                    f"SELECT {cols_str} FROM `{table}` "
                    f"LIMIT {batch_size} OFFSET {offset}"
                )
                return cur.fetchall()
        except Exception as e:
            self._log("error", f"[{table}] SELECT 실패 offset={offset}: {e}")
            return []

    def _create_target_table(self, tgt_conn, table, cols, src_db, tgt_db):
        if tgt_db in ("mssql", "azure"):
            self._ddl_mssql(tgt_conn, table, cols, src_db)
        elif tgt_db in ("postgresql", "redshift"):
            self._ddl_postgresql(tgt_conn, table, cols, src_db)
        else:
            self._ddl_mysql(tgt_conn, table, cols, src_db)

    def _create_mssql_table(self, tgt_conn, table, cols):
        self._ddl_mssql(tgt_conn, table, cols, self.job.get("src_db", "mysql"))

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
        "text":"NVARCHAR(MAX)","tinytext":"NVARCHAR(500)",
        "mediumtext":"NVARCHAR(MAX)","longtext":"NVARCHAR(MAX)",
        "datetime":"DATETIME2(6)","date":"DATE","time":"TIME","timestamp":"DATETIME2(6)",
        "blob":"VARBINARY(MAX)","tinyblob":"VARBINARY(MAX)",
        "mediumblob":"VARBINARY(MAX)","longblob":"VARBINARY(MAX)",
        "binary":"BINARY","varbinary":"VARBINARY(MAX)",
        "bit":"BIT","bool":"BIT","boolean":"BIT",
        "enum":"NVARCHAR(255)","set":"NVARCHAR(500)","json":"NVARCHAR(MAX)",
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
        "bool":"TINYINT(1)","boolean":"TINYINT(1)",
        "enum":"VARCHAR(255)","set":"VARCHAR(500)","json":"JSON",
    }

    def _resolve_mysql_type(self, c, src_db):
        raw  = (c.get("DATA_TYPE") or "varchar").lower().strip()
        full = (c.get("COLUMN_TYPE") or raw).lower()
        ln   = c.get("CHARACTER_MAXIMUM_LENGTH")
        p    = c.get("NUMERIC_PRECISION")
        s    = c.get("NUMERIC_SCALE")
        m    = self._MSSQL_TO_MYSQL if src_db in ("mssql","azure") else self._MYSQL_TO_MYSQL
        if raw in ("nvarchar","varchar","char","nchar"):
            base = {"nvarchar":"VARCHAR","varchar":"VARCHAR","nchar":"CHAR","char":"CHAR"}.get(raw,"VARCHAR")
            if ln and int(ln) > 0 and int(ln) <= 16383:
                return f"{base}({int(ln)})"
            return "TEXT" if not ln or int(ln) < 0 else f"{base}(255)"
        if raw in ("decimal","numeric"):
            return f"DECIMAL({int(p) if p else 18},{int(s) if s else 4})"
        if raw == "datetime2":
            return "DATETIME(6)"
        if raw in ("varbinary","binary"):
            if not ln or int(ln) < 0:
                return "LONGBLOB"
            return f"VARBINARY({min(int(ln),65535)})"
        if "unsigned" in full:
            k = raw + " unsigned"
            if k in m:
                return m[k]
        if raw == "tinyint" and "(1)" in full:
            return "TINYINT(1)"
        return m.get(raw, "TEXT")

    def _resolve_mssql_type(self, c, src_db):
        raw  = (c.get("DATA_TYPE") or "varchar").lower().strip()
        full = (c.get("COLUMN_TYPE") or raw).lower()
        ln   = c.get("CHARACTER_MAXIMUM_LENGTH")
        p    = c.get("NUMERIC_PRECISION")
        s    = c.get("NUMERIC_SCALE")
        m    = self._MYSQL_TO_MSSQL
        if raw in ("nvarchar","varchar","char","nchar"):
            base = {"nvarchar":"NVARCHAR","varchar":"NVARCHAR","nchar":"NCHAR","char":"NCHAR"}.get(raw,"NVARCHAR")
            if not ln or int(ln) < 0:
                return f"{base}(MAX)"
            return f"{base}({min(int(ln),4000)})"
        if raw in ("decimal","numeric"):
            return f"DECIMAL({int(p) if p else 18},{int(s) if s else 4})"
        if raw in ("varbinary","binary"):
            if not ln or int(ln) < 0:
                return "VARBINARY(MAX)"
            return f"VARBINARY({min(int(ln),8000)})"
        if raw == "datetime2":
            return "DATETIME2(6)"
        if raw == "tinyint" and "(1)" in full:
            return "BIT"
        if "unsigned" in full:
            k = raw + " unsigned"
            if k in m:
                return m[k]
        return m.get(raw, "NVARCHAR(500)")

    def _ddl_mysql(self, conn, table, cols, src_db):
        col_defs = []
        pk_cols  = []
        for c in cols:
            nm    = c["COLUMN_NAME"]
            extra = (c.get("EXTRA") or "").lower()
            is_pk = c.get("COLUMN_KEY","") == "PRI"
            is_ai = "auto_increment" in extra or c.get("is_identity") == 1
            null  = c.get("IS_NULLABLE","YES") == "YES" and not is_pk
            ns    = "NULL" if null else "NOT NULL"
            if is_pk:
                pk_cols.append(nm)
            if is_ai:
                col_defs.append(f"  `{nm}` INT NOT NULL AUTO_INCREMENT")
                continue
            t = self._resolve_mysql_type(c, src_db)
            col_defs.append(f"  `{nm}` {t} {ns}")
        if pk_cols:
            pk_str = "`, `".join(pk_cols)
            col_defs.append(f"  PRIMARY KEY (`{pk_str}`)")
        if not col_defs:
            return
        lines = [f"CREATE TABLE IF NOT EXISTS `{table}` ("]
        lines.extend(col_defs[i] + ("," if i < len(col_defs)-1 else "") for i in range(len(col_defs)))
        lines.append(") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci")
        ddl = "\n".join(lines)
        self._log("info", f"[{table}] MySQL DDL ({len(cols)}컬럼)")
        cur = conn.cursor()
        cur.execute(ddl)
        conn.commit()
        self._log("info", f"[{table}] 생성 완료 ✓")

    def _ddl_mssql(self, conn, table, cols, src_db):
        col_defs = []
        pk_cols  = []
        for c in cols:
            nm    = c["COLUMN_NAME"]
            extra = (c.get("EXTRA") or "").lower()
            is_pk = c.get("COLUMN_KEY","") == "PRI"
            is_ai = "auto_increment" in extra or c.get("is_identity") == 1
            null  = c.get("IS_NULLABLE","YES") == "YES" and not is_pk
            ns    = "NULL" if null else "NOT NULL"
            if is_pk:
                pk_cols.append(nm)
            if is_ai:
                col_defs.append(f"  [{nm}] INT IDENTITY(1,1) NOT NULL")
                continue
            t = self._resolve_mssql_type(c, src_db)
            col_defs.append(f"  [{nm}] {t} {ns}")
        if pk_cols:
            pk_str = "], [".join(pk_cols)
            col_defs.append(f"  CONSTRAINT [PK_{table}] PRIMARY KEY ([{pk_str}])")
        if not col_defs:
            return
        lines = [f"IF OBJECT_ID(N'[dbo].[{table}]', N'U') IS NULL"]
        lines.append(f"CREATE TABLE [dbo].[{table}] (")
        lines.extend(col_defs[i] + ("," if i < len(col_defs)-1 else "") for i in range(len(col_defs)))
        lines.append(")")
        ddl = "\n".join(lines)
        self._log("info", f"[{table}] MSSQL DDL ({len(cols)}컬럼)")
        cur = conn.cursor()
        cur.execute(ddl)
        conn.commit()
        self._log("info", f"[{table}] 생성 완료 ✓")

    def _ddl_postgresql(self, conn, table, cols, src_db):
        PG_MAP = {
            "int":"INTEGER","bigint":"BIGINT","smallint":"SMALLINT","tinyint":"SMALLINT",
            "float":"REAL","double":"DOUBLE PRECISION","decimal":"NUMERIC","numeric":"NUMERIC",
            "nvarchar":"VARCHAR","varchar":"VARCHAR","char":"CHAR","nchar":"CHAR",
            "text":"TEXT","longtext":"TEXT","mediumtext":"TEXT","tinytext":"TEXT",
            "datetime":"TIMESTAMP","datetime2":"TIMESTAMP","date":"DATE","time":"TIME",
            "timestamp":"TIMESTAMPTZ","blob":"BYTEA","longblob":"BYTEA","varbinary":"BYTEA",
            "bit":"BOOLEAN","bool":"BOOLEAN","boolean":"BOOLEAN",
            "json":"JSONB","jsonb":"JSONB",
        }
        col_defs = []
        pk_cols  = []
        for c in cols:
            nm    = c["COLUMN_NAME"]
            extra = (c.get("EXTRA") or "").lower()
            is_pk = c.get("COLUMN_KEY","") == "PRI"
            is_ai = "auto_increment" in extra or c.get("is_identity") == 1
            null  = c.get("IS_NULLABLE","YES") == "YES" and not is_pk
            ns    = "" if null else " NOT NULL"
            if is_pk:
                pk_cols.append(nm)
            if is_ai:
                col_defs.append(f'  "{nm}" SERIAL')
                continue
            raw = (c.get("DATA_TYPE") or "varchar").lower()
            ln  = c.get("CHARACTER_MAXIMUM_LENGTH")
            p   = c.get("NUMERIC_PRECISION")
            s   = c.get("NUMERIC_SCALE")
            if raw in ("varchar","nvarchar","char","nchar"):
                base = "VARCHAR" if "var" in raw else "CHAR"
                t = f"{base}({int(ln)})" if ln and int(ln) > 0 else "TEXT"
            elif raw in ("decimal","numeric"):
                t = f"NUMERIC({int(p) if p else 18},{int(s) if s else 4})"
            else:
                t = PG_MAP.get(raw, "TEXT")
            col_defs.append(f'  "{nm}" {t}{ns}')
        if pk_cols:
            pk_str = '", "'.join(pk_cols)
            col_defs.append(f'  PRIMARY KEY ("{pk_str}")')
        if not col_defs:
            return
        lines = [f'CREATE TABLE IF NOT EXISTS "{table}" (']
        lines.extend(col_defs[i] + ("," if i < len(col_defs)-1 else "") for i in range(len(col_defs)))
        lines.append(")")
        ddl = "\n".join(lines)
        self._log("info", f"[{table}] PostgreSQL DDL ({len(cols)}컬럼)")
        cur = conn.cursor()
        cur.execute(ddl)
        conn.commit()
        self._log("info", f"[{table}] 생성 완료 ✓")

'''

new_content = content[:idx_start] + BLOCK + content[idx_end:]

try:
    ast.parse(new_content)
    print('✓ 문법 OK')
except SyntaxError as e:
    lines = new_content.split('\n')
    print(f'✗ 문법 오류 {e.lineno}: {e.msg}')
    for i, ln in enumerate(lines[max(0, e.lineno-3):e.lineno+3], max(1, e.lineno-2)):
        print(f'{i}: {ln}')
    print(f'복구: copy {bak} {path}')
    exit(1)

open(path, 'w', encoding='utf-8').write(new_content)

# 검증
chk = new_content
print(f'_connect_src make_mssql_conn: {"make_mssql_conn" in chk}')
print(f'_connect_tgt db_type 분기: {"tgt_db" in chk}')
print(f'_fetch_batch OFFSET FETCH: {"OFFSET" in chk and "FETCH NEXT" in chk}')
print(f'_ddl_mysql: {"def _ddl_mysql" in chk}')
print(f'_ddl_mssql: {"def _ddl_mssql" in chk}')
print(f'남은 port=3306 하드코딩: {chk.count("port=3306")}개')
print('\n완료! 재시작:')
print('python -m uvicorn main:app --port 8000')
