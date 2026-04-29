"""
fix_create_table_v2.py
backend 폴더에서 실행: python fix_create_table_v2.py

완전히 동적인 다중 DB 이관 엔진으로 교체합니다.
- 어떤 테이블이든, 몇 개의 테이블이든 자동 처리
- MSSQL → MySQL, MySQL → MSSQL, MySQL → MySQL, MSSQL → MSSQL
- 모든 주요 데이터 타입 양방향 매핑
- NULL/NOT NULL, PK, AUTO_INCREMENT/IDENTITY, 기본값 처리
"""
import shutil, ast
from datetime import datetime

path = 'app/api/routes/jobs.py'
bak  = path + '.' + datetime.now().strftime('%H%M%S') + '.bak'
shutil.copy2(path, bak)
print(f'백업: {bak}')

content = open(path, encoding='utf-8').read()

# ── 1. 호출부: _create_mssql_table → _create_target_table ────────
OLD_CALL = '                self._create_mssql_table(tgt_conn, table, cols)'
NEW_CALL = '                self._create_target_table(tgt_conn, table, cols)'
if OLD_CALL in content:
    content = content.replace(OLD_CALL, NEW_CALL)
    print('호출부 교체 완료')

# ── 2. IDENTITY/INSERT/TRUNCATE 통합 처리 ────────────────────────
OLD_IDENTITY = '''        tgt_cur = tgt_conn.cursor()
        has_identity = any("auto_increment" in (c.get("EXTRA","") or "").lower() for c in cols)
        if has_identity:
            try:
                tgt_cur.execute(f"SET IDENTITY_INSERT [{table}] ON")
            except:
                pass

        cols_str = ", ".join([f"[{c}]" for c in col_names])
        placeholders = ", ".join(["?" for _ in col_names])
        insert_sql = f"INSERT INTO [{table}] ({cols_str}) VALUES ({placeholders})"'''

NEW_IDENTITY = '''        tgt_cur = tgt_conn.cursor()
        has_identity = any(
            "auto_increment" in (c.get("EXTRA","") or "").lower() or
            c.get("is_identity") == 1 or c.get("EXTRA","") == "auto_increment"
            for c in cols
        )
        if tgt_db_type in ("mssql", "azure"):
            if has_identity:
                try:
                    tgt_cur.execute(f"SET IDENTITY_INSERT [{table}] ON")
                except Exception:
                    pass
            cols_str     = ", ".join([f"[{c}]" for c in col_names])
            placeholders = ", ".join(["?" for _ in col_names])
            insert_sql   = f"INSERT INTO [{table}] ({cols_str}) VALUES ({placeholders})"
        else:
            # MySQL / MariaDB / Aurora 등
            cols_str     = ", ".join([f"`{c}`" for c in col_names])
            placeholders = ", ".join(["%s" for _ in col_names])
            insert_sql   = f"INSERT INTO `{table}` ({cols_str}) VALUES ({placeholders})"'''

if OLD_IDENTITY in content:
    content = content.replace(OLD_IDENTITY, NEW_IDENTITY)
    print('INSERT/IDENTITY 구문 교체 완료')

# ── 3. TRUNCATE 분기 ─────────────────────────────────────────────
OLD_TRUNC = '''        if self.job.get("truncate_target", False):
            try:
                tgt_cur = tgt_conn.cursor()
                tgt_cur.execute(f"TRUNCATE TABLE [{table}]")
                tgt_conn.commit()
            except:
                pass'''

NEW_TRUNC = '''        if self.job.get("truncate_target", False):
            try:
                tgt_cur = tgt_conn.cursor()
                if tgt_db_type in ("mssql", "azure"):
                    tgt_cur.execute(f"TRUNCATE TABLE [{table}]")
                else:
                    tgt_cur.execute(f"TRUNCATE TABLE `{table}`")
                tgt_conn.commit()
            except Exception:
                pass'''

if OLD_TRUNC in content:
    content = content.replace(OLD_TRUNC, NEW_TRUNC)
    print('TRUNCATE 구문 교체 완료')

# ── 4. _create_mssql_table 함수 전체를 새 함수들로 교체 ──────────
func_start = content.find('\n    def _create_mssql_table(self, tgt_conn, table: str, cols: list):')
func_end   = content.find('\n    def stop(self):')

if func_start != -1 and func_end != -1:
    NEW_FUNCS = r'''
    # ── 타입 매핑 테이블 (클래스 수준에서 공유) ──────────────────
    _MSSQL_TO_MYSQL = {
        "int":"INT","bigint":"BIGINT","smallint":"SMALLINT","tinyint":"TINYINT",
        "float":"FLOAT","real":"FLOAT","double":"DOUBLE",
        "decimal":"DECIMAL","numeric":"DECIMAL",
        "money":"DECIMAL(19,4)","smallmoney":"DECIMAL(10,4)",
        "bit":"TINYINT(1)",
        "nvarchar":"VARCHAR","varchar":"VARCHAR","nchar":"CHAR","char":"CHAR",
        "ntext":"LONGTEXT","text":"LONGTEXT","sysname":"VARCHAR(128)",
        "datetime":"DATETIME","datetime2":"DATETIME(6)","date":"DATE","time":"TIME",
        "smalldatetime":"DATETIME","datetimeoffset":"DATETIME(6)",
        "timestamp":"BIGINT","rowversion":"BIGINT",
        "binary":"BINARY","varbinary":"VARBINARY(255)","image":"LONGBLOB",
        "uniqueidentifier":"CHAR(36)","xml":"LONGTEXT",
        "geography":"TEXT","geometry":"TEXT","hierarchyid":"VARCHAR(255)",
        "sql_variant":"TEXT",
    }
    _MYSQL_TO_MSSQL = {
        "int":"INT","bigint":"BIGINT","smallint":"SMALLINT","tinyint":"TINYINT",
        "mediumint":"INT","year":"SMALLINT",
        "tinyint unsigned":"SMALLINT","smallint unsigned":"INT",
        "mediumint unsigned":"INT","int unsigned":"BIGINT","bigint unsigned":"DECIMAL(20,0)",
        "float":"FLOAT","double":"FLOAT","decimal":"DECIMAL","numeric":"DECIMAL",
        "varchar":"NVARCHAR","char":"NCHAR","nvarchar":"NVARCHAR","nchar":"NCHAR",
        "text":"NVARCHAR(MAX)","tinytext":"NVARCHAR(500)",
        "mediumtext":"NVARCHAR(MAX)","longtext":"NVARCHAR(MAX)",
        "datetime":"DATETIME2(6)","date":"DATE","time":"TIME",
        "timestamp":"DATETIME2(6)","year":"SMALLINT",
        "blob":"VARBINARY(MAX)","tinyblob":"VARBINARY(MAX)",
        "mediumblob":"VARBINARY(MAX)","longblob":"VARBINARY(MAX)",
        "binary":"BINARY","varbinary":"VARBINARY(MAX)",
        "bit":"BIT","bool":"BIT","boolean":"BIT",
        "enum":"NVARCHAR(255)","set":"NVARCHAR(500)","json":"NVARCHAR(MAX)",
    }
    _MYSQL_TO_MYSQL = {
        "int":"INT","bigint":"BIGINT","smallint":"SMALLINT","tinyint":"TINYINT",
        "mediumint":"MEDIUMINT","year":"YEAR",
        "float":"FLOAT","double":"DOUBLE","decimal":"DECIMAL","numeric":"DECIMAL",
        "varchar":"VARCHAR","char":"CHAR","nvarchar":"VARCHAR","nchar":"CHAR",
        "text":"TEXT","tinytext":"TINYTEXT","mediumtext":"MEDIUMTEXT","longtext":"LONGTEXT",
        "datetime":"DATETIME","date":"DATE","time":"TIME","timestamp":"TIMESTAMP",
        "blob":"BLOB","tinyblob":"TINYBLOB","mediumblob":"MEDIUMBLOB","longblob":"LONGBLOB",
        "binary":"BINARY","varbinary":"VARBINARY",
        "bit":"BIT","bool":"TINYINT(1)","boolean":"TINYINT(1)",
        "enum":"VARCHAR(255)","set":"VARCHAR(500)","json":"JSON",
    }

    def _create_target_table(self, tgt_conn, table: str, cols: list):
        """타겟 DB 타입에 맞는 CREATE TABLE 실행 (어떤 테이블이든 동적 처리)"""
        tgt_db = self.job.get("tgt_db", "mssql")
        src_db = self.job.get("src_db", "mysql")
        if tgt_db in ("mssql", "azure"):
            self._ddl_mssql(tgt_conn, table, cols, src_db)
        else:
            self._ddl_mysql(tgt_conn, table, cols, src_db)

    def _resolve_type_mysql(self, c: dict, src_db: str) -> str:
        """컬럼 정보 → MySQL 타입 문자열"""
        raw  = (c.get("DATA_TYPE") or "varchar").lower().strip()
        full = (c.get("COLUMN_TYPE") or raw).lower()
        p    = c.get("NUMERIC_PRECISION")
        s    = c.get("NUMERIC_SCALE")
        ln   = c.get("CHARACTER_MAXIMUM_LENGTH")

        type_map = self._MSSQL_TO_MYSQL if src_db in ("mssql","azure") else self._MYSQL_TO_MYSQL

        # 길이/정밀도 있는 타입 우선 처리
        if raw in ("nvarchar","varchar","char","nchar"):
            base = {"nvarchar":"VARCHAR","varchar":"VARCHAR",
                    "nchar":"CHAR","char":"CHAR"}.get(raw,"VARCHAR")
            if ln and int(ln) > 0 and int(ln) <= 16383:
                return f"{base}({int(ln)})"
            return "TEXT" if (not ln or int(ln)<0) else f"{base}(255)"

        if raw in ("decimal","numeric","money","smallmoney"):
            if raw == "money":    return "DECIMAL(19,4)"
            if raw == "smallmoney": return "DECIMAL(10,4)"
            ep = int(p) if p else 18
            es = int(s) if s else 4
            return f"DECIMAL({ep},{es})"

        if raw == "datetime2":
            return "DATETIME(6)"

        if raw in ("binary","varbinary","image"):
            if raw == "image": return "LONGBLOB"
            if not ln or int(ln) < 0: return "LONGBLOB"
            size = int(ln)
            return f"VARBINARY({min(size,65535)})" if size > 0 else "LONGBLOB"

        # unsigned 처리 (MySQL 소스)
        if "unsigned" in full:
            key = raw + " unsigned"
            if key in type_map: return type_map[key]

        # tinyint(1) → TINYINT(1)
        if raw == "tinyint" and "(1)" in full:
            return "TINYINT(1)"

        return type_map.get(raw, "TEXT")

    def _resolve_type_mssql(self, c: dict, src_db: str) -> str:
        """컬럼 정보 → MSSQL 타입 문자열"""
        raw  = (c.get("DATA_TYPE") or "varchar").lower().strip()
        full = (c.get("COLUMN_TYPE") or raw).lower()
        p    = c.get("NUMERIC_PRECISION")
        s    = c.get("NUMERIC_SCALE")
        ln   = c.get("CHARACTER_MAXIMUM_LENGTH")

        type_map = self._MYSQL_TO_MSSQL

        if raw in ("nvarchar","varchar","char","nchar"):
            base = {"nvarchar":"NVARCHAR","varchar":"NVARCHAR",
                    "nchar":"NCHAR","char":"NCHAR"}.get(raw,"NVARCHAR")
            if not ln or int(ln) < 0:
                return f"{base}(MAX)"
            return f"{base}({min(int(ln),4000)})"

        if raw in ("decimal","numeric"):
            ep = int(p) if p else 18
            es = int(s) if s else 4
            return f"DECIMAL({ep},{es})"

        if raw in ("varbinary","binary"):
            if not ln or int(ln) < 0: return "VARBINARY(MAX)"
            return f"VARBINARY({min(int(ln),8000)})"

        if raw == "timestamp" and src_db in ("mssql","azure"):
            return "BIGINT"

        if "unsigned" in full:
            key = raw + " unsigned"
            if key in type_map: return type_map[key]

        if raw == "tinyint" and "(1)" in full:
            return "BIT"

        return type_map.get(raw, "NVARCHAR(500)")

    def _ddl_mysql(self, tgt_conn, table: str, cols: list, src_db: str):
        """MySQL 타겟 CREATE TABLE 생성 — 모든 컬럼 동적 처리"""
        col_defs = []
        pk_cols  = []

        for c in cols:
            cname    = c["COLUMN_NAME"]
            raw      = (c.get("DATA_TYPE") or "varchar").lower()
            extra    = (c.get("EXTRA") or "").lower()
            is_pk    = c.get("COLUMN_KEY","") == "PRI" or c.get("is_pk") is True
            is_ai    = "auto_increment" in extra or c.get("is_identity") == 1
            nullable = c.get("IS_NULLABLE","YES") == "YES" and not is_pk
            null_str = "NULL" if nullable else "NOT NULL"

            if is_pk:
                pk_cols.append(cname)

            if is_ai:
                col_defs.append(f"  `{cname}` INT NOT NULL AUTO_INCREMENT")
                continue

            mtype = self._resolve_type_mysql(c, src_db)

            # 기본값 처리
            default = c.get("COLUMN_DEFAULT")
            def_str = ""
            if default is not None and str(default).upper() not in ("NULL","NONE",""):
                dv = str(default).strip("'\"")
                if dv.upper() in ("CURRENT_TIMESTAMP","NOW()","GETDATE()"):
                    def_str = " DEFAULT CURRENT_TIMESTAMP"
                elif dv.replace(".","").replace("-","").isdigit():
                    def_str = f" DEFAULT {dv}"
                else:
                    def_str = f" DEFAULT '{dv}'"

            col_defs.append(f"  `{cname}` {mtype} {null_str}{def_str}")

        if pk_cols:
            col_defs.append(f"  PRIMARY KEY (`{'`, `'.join(pk_cols)}`)")

        if not col_defs:
            self._log("warn", f"[{table}] 컬럼 없음 — 스킵")
            return

        ddl = (
            f"CREATE TABLE IF NOT EXISTS `{table}` (\n"
            + ",\n".join(col_defs)
            + "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
        )
        self._log("info", f"[{table}] MySQL DDL 생성 ({len(cols)}컬럼)")
        try:
            cur = tgt_conn.cursor()
            cur.execute(ddl)
            tgt_conn.commit()
            self._log("info", f"[{table}] 테이블 생성 완료 ✓")
        except Exception as e:
            self._log("error", f"[{table}] 생성 실패: {e}\nDDL=\n{ddl}")
            raise

    def _ddl_mssql(self, tgt_conn, table: str, cols: list, src_db: str):
        """MSSQL 타겟 CREATE TABLE 생성 — 모든 컬럼 동적 처리"""
        col_defs = []
        pk_cols  = []

        for c in cols:
            cname    = c["COLUMN_NAME"]
            extra    = (c.get("EXTRA") or "").lower()
            is_pk    = c.get("COLUMN_KEY","") == "PRI" or c.get("is_pk") is True
            is_ai    = "auto_increment" in extra or c.get("is_identity") == 1
            nullable = c.get("IS_NULLABLE","YES") == "YES" and not is_pk
            null_str = "NULL" if nullable else "NOT NULL"

            if is_pk:
                pk_cols.append(cname)

            if is_ai:
                col_defs.append(f"  [{cname}] INT IDENTITY(1,1) NOT NULL")
                continue

            mtype = self._resolve_type_mssql(c, src_db)

            # 기본값 처리
            default = c.get("COLUMN_DEFAULT")
            def_str = ""
            if default is not None and str(default).upper() not in ("NULL","NONE",""):
                dv = str(default).strip("'\"()")
                if dv.upper() in ("CURRENT_TIMESTAMP","NOW()","GETDATE()","SYSDATETIME()"):
                    def_str = " DEFAULT GETDATE()"
                elif dv.replace(".","").replace("-","").isdigit():
                    def_str = f" DEFAULT {dv}"
                else:
                    def_str = f" DEFAULT N'{dv}'"

            col_defs.append(f"  [{cname}] {mtype} {null_str}{def_str}")

        if pk_cols:
            pk_str = ", ".join([f"[{c}]" for c in pk_cols])
            col_defs.append(f"  CONSTRAINT [PK_{table}] PRIMARY KEY ({pk_str})")

        if not col_defs:
            self._log("warn", f"[{table}] 컬럼 없음 — 스킵")
            return

        ddl = (
            f"IF OBJECT_ID(N'[dbo].[{table}]', N'U') IS NULL\n"
            f"CREATE TABLE [dbo].[{table}] (\n"
            + ",\n".join(col_defs)
            + "\n)"
        )
        self._log("info", f"[{table}] MSSQL DDL 생성 ({len(cols)}컬럼)")
        try:
            cur = tgt_conn.cursor()
            cur.execute(ddl)
            tgt_conn.commit()
            self._log("info", f"[{table}] 테이블 생성 완료 ✓")
        except Exception as e:
            self._log("error", f"[{table}] 생성 실패: {e}\nDDL=\n{ddl}")
            raise

    # 하위 호환성 유지
    def _create_mssql_table(self, tgt_conn, table: str, cols: list):
        self._ddl_mssql(tgt_conn, table, cols, self.job.get("src_db","mysql"))

'''
    content = content[:func_start] + NEW_FUNCS + content[func_end:]
    print('DDL 생성 함수 전체 교체 완료')
else:
    print('주의: _create_mssql_table 함수 범위를 찾지 못함')

# ── 5. 문법 확인 ─────────────────────────────────────────────────
try:
    ast.parse(content)
    print('✓ 문법 OK')
except SyntaxError as e:
    print(f'✗ 문법 오류 라인 {e.lineno}: {e.msg}')
    lines = content.split('\n')
    start = max(0, e.lineno-3)
    for i, ln in enumerate(lines[start:e.lineno+2], start+1):
        print(f'{i}: {ln}')
    print(f'복구: copy {bak} {path}')
    exit(1)

open(path, 'w', encoding='utf-8').write(content)
print('\n완료! 백엔드 재시작:')
print('python -m uvicorn main:app --port 8000')
