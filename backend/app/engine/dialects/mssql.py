"""MSSQL 방언 구현 (v10 #9)"""
from __future__ import annotations
from typing import List, Optional, Tuple, Any

from .base import DatabaseDialect, IndexInfo, PKInfo


class MSSQLDialect(DatabaseDialect):
    """MSSQL / Azure SQL 구현"""

    @property
    def name(self) -> str:
        return "mssql"

    # ── 메타데이터 조회 ────────────────────────────────────

    def get_pk_info(self, conn, table: str) -> Optional[PKInfo]:
        """
        PK 컬럼 및 타입 조회.

        sys.indexes.is_primary_key=1 로 PK 인덱스 찾고,
        sys.index_columns 조인으로 컬럼 순서 확보.
        """
        cur = conn.cursor()
        cur.execute("""
            SELECT c.name AS col_name, tp.name AS col_type, ic.key_ordinal
            FROM sys.indexes i
            JOIN sys.index_columns ic
                ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            JOIN sys.columns c
                ON ic.object_id = c.object_id AND ic.column_id = c.column_id
            JOIN sys.types tp
                ON c.user_type_id = tp.user_type_id
            JOIN sys.tables t
                ON i.object_id = t.object_id
            WHERE i.is_primary_key = 1
              AND t.name = ?
            ORDER BY ic.key_ordinal
        """, [table])
        rows = cur.fetchall()
        try:
            cur.close()
        except Exception:
            pass

        if not rows:
            return None

        cols = [r[0] for r in rows]
        types = [r[1] for r in rows]
        return PKInfo(
            columns=cols,
            column_types=types,
            is_composite=(len(cols) > 1),
        )

    def get_secondary_indexes(self, conn, table: str) -> List[IndexInfo]:
        """
        PK 제외한 세컨더리 인덱스 목록.

        제외 대상:
          - is_primary_key=1  (PK)
          - is_hypothetical=1 (옵티마이저 가상 인덱스)
          - type=0            (힙. 실제 인덱스 아님)
          - is_unique_constraint=1 (UNIQUE CONSTRAINT) — 복원 어려움, Phase 2 범위 외
        """
        cur = conn.cursor()
        cur.execute("""
            SELECT
                i.name           AS idx_name,
                i.is_unique      AS is_unique,
                i.type_desc      AS idx_type,
                c.name           AS col_name,
                ic.key_ordinal   AS key_ord
            FROM sys.indexes i
            JOIN sys.index_columns ic
                ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            JOIN sys.columns c
                ON ic.object_id = c.object_id AND ic.column_id = c.column_id
            JOIN sys.tables t
                ON i.object_id = t.object_id
            WHERE t.name = ?
              AND i.is_primary_key = 0
              AND i.is_unique_constraint = 0
              AND i.is_hypothetical = 0
              AND i.type > 0
              AND i.name IS NOT NULL
            ORDER BY i.name, ic.key_ordinal
        """, [table])
        raw = cur.fetchall()
        try:
            cur.close()
        except Exception:
            pass

        # 인덱스명별로 그룹핑
        grouped: dict = {}
        for idx_name, is_uq, idx_type, col_name, _ord in raw:
            if idx_name not in grouped:
                grouped[idx_name] = IndexInfo(
                    name=idx_name,
                    table=table,
                    columns=[],
                    is_unique=bool(is_uq),
                    index_type=idx_type,
                )
            grouped[idx_name].columns.append(col_name)

        return list(grouped.values())

    def get_pk_range(self, conn, table: str, pk_column: str) -> Tuple[Any, Any]:
        """PK 의 MIN/MAX"""
        cur = conn.cursor()
        cur.execute(f"SELECT MIN([{pk_column}]), MAX([{pk_column}]) FROM [{table}]")
        row = cur.fetchone()
        try:
            cur.close()
        except Exception:
            pass
        if not row:
            return (None, None)
        return (row[0], row[1])

    # ── 인덱스 DDL ─────────────────────────────────────────

    def drop_index_sql(self, index: IndexInfo) -> str:
        # MSSQL: DROP INDEX idx_name ON table_name
        return f"DROP INDEX [{index.name}] ON [{index.table}]"

    def create_index_sql(self, index: IndexInfo) -> str:
        """
        CREATE [UNIQUE] [NONCLUSTERED] INDEX ... 생성.

        type_desc 가 'CLUSTERED' 면 CLUSTERED, 아니면 NONCLUSTERED.
        """
        uq = "UNIQUE " if index.is_unique else ""
        clust = "CLUSTERED" if (index.index_type or "").upper() == "CLUSTERED" else "NONCLUSTERED"
        cols = ", ".join([f"[{c}]" for c in index.columns])
        return (
            f"CREATE {uq}{clust} INDEX [{index.name}] "
            f"ON [{index.table}] ({cols})"
        )

    # ── 청크 WHERE ─────────────────────────────────────────

    def chunk_where_clause(self, pk_column: str, start_val: Any, end_val: Any) -> str:
        """
        파라미터 바인딩 없이 직접 치환된 WHERE 조건 반환.

        MSSQL 에서는 [대괄호] 식별자 + 값은 그대로 (정수만 대상이므로 안전).
        """
        return f"[{pk_column}] >= {start_val} AND [{pk_column}] <= {end_val}"
