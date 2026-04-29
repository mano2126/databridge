"""MySQL / MariaDB 방언 구현 (v10 #9)"""
from __future__ import annotations
from typing import List, Optional, Tuple, Any

from .base import DatabaseDialect, IndexInfo, PKInfo


class MySQLDialect(DatabaseDialect):
    """MySQL / MariaDB / Aurora / TiDB 구현"""

    @property
    def name(self) -> str:
        return "mysql"

    # ── 메타데이터 조회 ────────────────────────────────────

    def get_pk_info(self, conn, table: str) -> Optional[PKInfo]:
        """
        PRIMARY KEY 컬럼 및 타입 조회.

        information_schema.KEY_COLUMN_USAGE + COLUMNS 조인.
        """
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT k.COLUMN_NAME, c.DATA_TYPE, k.ORDINAL_POSITION
                FROM information_schema.KEY_COLUMN_USAGE k
                JOIN information_schema.COLUMNS c
                    ON k.TABLE_SCHEMA = c.TABLE_SCHEMA
                   AND k.TABLE_NAME   = c.TABLE_NAME
                   AND k.COLUMN_NAME  = c.COLUMN_NAME
                WHERE k.TABLE_SCHEMA = DATABASE()
                  AND k.TABLE_NAME   = %s
                  AND k.CONSTRAINT_NAME = 'PRIMARY'
                ORDER BY k.ORDINAL_POSITION
            """, (table,))
            rows = cur.fetchall()
        finally:
            try: cur.close()
            except: pass

        if not rows:
            return None

        # pymysql dict_cursor 비-dict 양쪽 대응
        if isinstance(rows[0], dict):
            cols = [r["COLUMN_NAME"] for r in rows]
            types = [r["DATA_TYPE"] for r in rows]
        else:
            cols = [r[0] for r in rows]
            types = [r[1] for r in rows]

        return PKInfo(
            columns=cols,
            column_types=types,
            is_composite=(len(cols) > 1),
        )

    def get_secondary_indexes(self, conn, table: str) -> List[IndexInfo]:
        """
        PRIMARY 제외 세컨더리 인덱스 목록.

        information_schema.STATISTICS 사용.
        """
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT
                    INDEX_NAME,
                    NON_UNIQUE,
                    INDEX_TYPE,
                    COLUMN_NAME,
                    SEQ_IN_INDEX
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                  AND INDEX_NAME <> 'PRIMARY'
                ORDER BY INDEX_NAME, SEQ_IN_INDEX
            """, (table,))
            raw = cur.fetchall()
        finally:
            try: cur.close()
            except: pass

        grouped: dict = {}
        for row in raw:
            if isinstance(row, dict):
                idx_name = row["INDEX_NAME"]
                non_uq   = row["NON_UNIQUE"]
                idx_type = row["INDEX_TYPE"]
                col_name = row["COLUMN_NAME"]
            else:
                idx_name, non_uq, idx_type, col_name, _seq = row

            if idx_name not in grouped:
                grouped[idx_name] = IndexInfo(
                    name=idx_name,
                    table=table,
                    columns=[],
                    is_unique=(int(non_uq) == 0),
                    index_type=idx_type,
                )
            grouped[idx_name].columns.append(col_name)

        return list(grouped.values())

    def get_pk_range(self, conn, table: str, pk_column: str) -> Tuple[Any, Any]:
        """PK 의 MIN/MAX"""
        cur = conn.cursor()
        try:
            cur.execute(f"SELECT MIN(`{pk_column}`), MAX(`{pk_column}`) FROM `{table}`")
            row = cur.fetchone()
        finally:
            try: cur.close()
            except: pass

        if not row:
            return (None, None)
        # dict/tuple 대응
        if isinstance(row, dict):
            vals = list(row.values())
            return (vals[0], vals[1])
        return (row[0], row[1])

    # ── 인덱스 DDL ─────────────────────────────────────────

    def drop_index_sql(self, index: IndexInfo) -> str:
        return f"ALTER TABLE `{index.table}` DROP INDEX `{index.name}`"

    def create_index_sql(self, index: IndexInfo) -> str:
        uq = "UNIQUE " if index.is_unique else ""
        cols = ", ".join([f"`{c}`" for c in index.columns])
        using = ""
        if index.index_type and index.index_type.upper() in ("BTREE", "HASH"):
            using = f" USING {index.index_type.upper()}"
        return (
            f"CREATE {uq}INDEX `{index.name}` ON `{index.table}` ({cols}){using}"
        )

    # ── 청크 WHERE ─────────────────────────────────────────

    def chunk_where_clause(self, pk_column: str, start_val: Any, end_val: Any) -> str:
        return f"`{pk_column}` >= {start_val} AND `{pk_column}` <= {end_val}"

    # ── 세션 튜닝 ─────────────────────────────────────────

    def session_tune_before_load(self, conn) -> None:
        """
        MySQL 벌크 로드 전 세션 튜닝.

        주의: 이미 v10 #1 MysqlLoadDataLoader 에서 세션 힌트 적용 중.
        여기서는 청크 분할 시 '각 워커의 타겟 연결' 이 별도 세션이므로
        워커 연결마다 다시 적용.
        """
        cur = conn.cursor()
        try:
            for hint in (
                "SET foreign_key_checks = 0",
                "SET unique_checks = 0",
                "SET sql_log_bin = 0",
            ):
                try:
                    cur.execute(hint)
                except Exception:
                    pass  # 권한 없으면 무시
        finally:
            try: cur.close()
            except: pass
