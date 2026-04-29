"""
app/core/pagination.py
테이블 페이지네이션 전략 — 대용량 이관 핵심 모듈

=== 왜 이 모듈이 필요한가 ===

기존 엔진은 SQL OFFSET/FETCH 기반으로 페이지를 잘랐다.
이 방식은 N번째 배치를 위해 N * batch_size 건을 DB가 읽고 버리므로
10M row 테이블 후반부에서는 배치 하나에 수 분이 걸리는 선형 열화가 발생.
TB급 이관이 POC 8시간 윈도우 안에 끝날 수 없는 근본 원인이었다.

Keyset Pagination은 "마지막 PK보다 큰 것 N건"을 INDEX SEEK으로 가져오므로
배치 1이든 배치 1,000,000이든 비용이 거의 동일하다.

=== 전략 선택 로직 ===

PaginatorFactory.build(...) 가 테이블 메타데이터를 보고 자동 결정:

  [Keyset 가능] — PK가 있고, 타입이 정렬 가능한 원시형일 때
    - 단일 PK:  WHERE pk > :last ORDER BY pk LIMIT N
    - 복합 PK:  WHERE (k1, k2) > (:l1, :l2) ORDER BY k1, k2 LIMIT N

  [OFFSET fallback] — 아래 중 하나
    - PK 없음
    - PK가 BLOB/JSON/GEO 등 비교 불가 타입
    - 복합 PK가 4개 이상

=== 설계 원칙 ===

- DB 방언은 내부에서만 다룸 (mysql: LIMIT/OFFSET, mssql: OFFSET/FETCH).
  호출부는 next_query() / advance(rows) / done() 만 호출.
- WHERE 절에 들어갈 파라미터는 executemany 파라미터로 분리 (SQL Injection 차단).
- 배치 중간에 상태를 저장하고 복구할 수 있도록 checkpoint()/restore() 제공.
  (작업 #7 Resume 기능의 기반이 됨)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Iterable


# ── Keyset 가능한 타입 화이트리스트 ──────────────────────────
# 소스 DB 타입 이름을 소문자로 비교. MSSQL / MySQL / PostgreSQL 타입명 통합.
_KEYSET_COMPATIBLE_TYPES = frozenset({
    # 정수
    "int", "integer", "bigint", "smallint", "tinyint",
    "int identity", "int unsigned", "bigint unsigned",
    # 소수 (정확 비교 가능)
    "decimal", "numeric",
    # 문자열 (UTF-8/UTF-16 비교 가능. BLOB은 제외)
    "varchar", "nvarchar", "char", "nchar", "text", "ntext",
    # 날짜/시간
    "date", "time", "datetime", "datetime2", "smalldatetime", "timestamp",
    # UUID
    "uuid", "uniqueidentifier",
})

# 명시적으로 Keyset 금지
_KEYSET_INCOMPATIBLE_TYPES = frozenset({
    "binary", "varbinary", "image", "blob", "longblob", "mediumblob", "tinyblob",
    "json", "xml",
    "geography", "geometry", "hierarchyid", "sql_variant",
    "rowversion",   # rowversion은 Keyset으로 돌려도 되지만 이관 타겟에서는 사용 안 함
    "datetimeoffset",  # 소스 DB별 표현 차이 큼
})

_MAX_COMPOSITE_PK_KEYS = 3  # 복합 PK가 이보다 많으면 OFFSET fallback


# ── 유틸: DB 방언별 식별자 쿼팅 ───────────────────────────────

def _quote_id(name: str, dialect: str) -> str:
    """컬럼/테이블 이름을 방언에 맞게 쿼팅

    v10 #24c: 이미 완전 식별자(`[schema].[table]`, `"user"."table"` 등) 가 들어오면
    그대로 통과시킴. migration_engine 이 _qualified_table() 로 이미 완성된
    식별자를 넘겨줄 수 있도록.

    검출 규칙: 이름에 브래킷/따옴표가 이미 있거나 점(.)이 있으면 완전 식별자로 간주.
    """
    if not name:
        return name
    # 이미 완전 식별자 (예: "[ref].[branch]", "\"HR\".\"EMPLOYEES\"", "`mydb`.`t`")
    if '.' in name or '[' in name or '"' in name or '`' in name:
        return name
    d = (dialect or "").lower()
    if d in ("mssql", "sqlserver", "azure"):
        return f"[{name}]"
    if d == "oracle":
        return f'"{name}"'
    if d in ("postgres", "postgresql"):
        return f'"{name}"'
    return f"`{name}`"   # mysql family


def _placeholder(dialect: str) -> str:
    """파라미터 플레이스홀더"""
    d = (dialect or "").lower()
    if d in ("mssql", "sqlserver", "azure"):
        return "?"
    if d == "oracle":
        return ":?"   # Oracle: positional 은 numbered 로 별도 처리 필요하지만 자리표시 용도
    return "%s"   # pymysql / psycopg2


# ── 파이프라인 결과 타입 ──────────────────────────────────────

@dataclass
class QueryBatch:
    """한 배치를 가져오기 위해 실행할 SQL + 파라미터"""
    sql: str
    params: tuple = ()


@dataclass
class PaginatorState:
    """재개(Resume)용 체크포인트"""
    strategy: str                 # "keyset" or "offset"
    last_key: tuple | None = None  # Keyset: 마지막으로 본 PK 값(들)
    offset: int = 0                # Offset: 현재 오프셋
    rows_done: int = 0
    table: str = ""


# ── 추상 인터페이스 ──────────────────────────────────────────

class BasePaginator:
    """공통 인터페이스"""
    strategy: str = "base"

    def __init__(self, table: str, select_expr: str, dialect: str,
                 batch_size: int, total_rows: int | None = None):
        self.table = table
        self.select_expr = select_expr   # "col1, col2, CONVERT(...) AS col3 ..."
        self.dialect = dialect.lower()
        self.batch_size = batch_size
        self.total_rows = total_rows    # 모를 때는 None
        self.rows_done = 0
        self._exhausted = False

    def next_query(self) -> QueryBatch | None:
        raise NotImplementedError

    def advance(self, fetched_rows: list, col_index_map: dict[str, int]) -> None:
        """
        방금 가져온 rows를 기반으로 내부 커서를 진행.
        col_index_map: SELECT 결과에서 컬럼명 → 인덱스
        """
        raise NotImplementedError

    def done(self) -> bool:
        return self._exhausted

    def checkpoint(self) -> PaginatorState:
        raise NotImplementedError

    def restore(self, state: PaginatorState) -> None:
        raise NotImplementedError


# ── OFFSET 기반 (Fallback) ───────────────────────────────────

class OffsetPaginator(BasePaginator):
    """
    기존 방식. PK가 없거나 Keyset 부적합할 때만 사용.
    대용량에서는 느려지지만 안전성은 보장.
    """
    strategy = "offset"

    def __init__(self, table: str, select_expr: str, dialect: str,
                 batch_size: int, order_by: str,
                 total_rows: int | None = None):
        super().__init__(table, select_expr, dialect, batch_size, total_rows)
        self.order_by = order_by
        self.offset = 0

    def next_query(self) -> QueryBatch | None:
        if self._exhausted:
            return None
        if self.total_rows is not None and self.offset >= self.total_rows:
            self._exhausted = True
            return None

        tbl = _quote_id(self.table, self.dialect)
        if self.dialect in ("mssql", "sqlserver", "azure"):
            sql = (
                f"SELECT {self.select_expr} FROM {tbl} "
                f"ORDER BY {self.order_by} "
                f"OFFSET {self.offset} ROWS FETCH NEXT {self.batch_size} ROWS ONLY"
            )
        else:
            sql = (
                f"SELECT {self.select_expr} FROM {tbl} "
                f"ORDER BY {self.order_by} "
                f"LIMIT {self.batch_size} OFFSET {self.offset}"
            )
        return QueryBatch(sql=sql)

    def advance(self, fetched_rows: list, col_index_map: dict[str, int]) -> None:
        n = len(fetched_rows)
        self.rows_done += n
        self.offset += self.batch_size
        # 배치 크기보다 적게 왔으면 끝
        if n < self.batch_size:
            self._exhausted = True

    def checkpoint(self) -> PaginatorState:
        return PaginatorState(
            strategy=self.strategy, offset=self.offset,
            rows_done=self.rows_done, table=self.table,
        )

    def restore(self, state: PaginatorState) -> None:
        self.offset = state.offset
        self.rows_done = state.rows_done


# ── Keyset 기반 (정답) ───────────────────────────────────────

class KeysetPaginator(BasePaginator):
    """
    PK 단조 증가 가정 하의 O(log N + batch) 페이지네이션.
    WHERE (pk_cols...) > (last_key...) ORDER BY pk_cols LIMIT N
    """
    strategy = "keyset"

    def __init__(self, table: str, select_expr: str, dialect: str,
                 batch_size: int, pk_cols: list[str],
                 total_rows: int | None = None):
        super().__init__(table, select_expr, dialect, batch_size, total_rows)
        self.pk_cols = pk_cols
        self.last_key: tuple | None = None      # None이면 첫 배치

    def _order_by(self) -> str:
        return ", ".join(_quote_id(c, self.dialect) + " ASC" for c in self.pk_cols)

    def _build_where(self) -> tuple[str, tuple]:
        """
        (WHERE절, 파라미터) 반환.
        last_key None → ("", ())
        단일 PK → "WHERE pk > ?"
        복합 PK → "WHERE (k1, k2) > (?, ?)"   # ANSI SQL row-value 비교
                   * MSSQL은 row-value >를 지원하지 않아 풀어써야 함
        """
        if self.last_key is None:
            return "", ()

        ph = _placeholder(self.dialect)
        if len(self.pk_cols) == 1:
            col = _quote_id(self.pk_cols[0], self.dialect)
            return f"WHERE {col} > {ph}", (self.last_key[0],)

        # 복합 PK — MSSQL/MySQL 공통으로 작동하는 풀어 쓴 형태
        # (a, b, c) > (A, B, C)  ≡
        #   a > A OR (a = A AND b > B) OR (a = A AND b = B AND c > C)
        cols = [_quote_id(c, self.dialect) for c in self.pk_cols]
        clauses = []
        params = []
        for i in range(len(cols)):
            parts = []
            for j in range(i):
                parts.append(f"{cols[j]} = {ph}")
                params.append(self.last_key[j])
            parts.append(f"{cols[i]} > {ph}")
            params.append(self.last_key[i])
            clauses.append("(" + " AND ".join(parts) + ")")
        return "WHERE " + " OR ".join(clauses), tuple(params)

    def next_query(self) -> QueryBatch | None:
        if self._exhausted:
            return None

        where_clause, params = self._build_where()
        tbl = _quote_id(self.table, self.dialect)

        if self.dialect in ("mssql", "sqlserver", "azure"):
            # TOP 사용 — OFFSET 없이도 상한만 지정
            sql = (
                f"SELECT TOP {self.batch_size} {self.select_expr} "
                f"FROM {tbl} {where_clause} "
                f"ORDER BY {self._order_by()}"
            )
        else:
            sql = (
                f"SELECT {self.select_expr} FROM {tbl} {where_clause} "
                f"ORDER BY {self._order_by()} LIMIT {self.batch_size}"
            )
        return QueryBatch(sql=sql.strip(), params=params)

    def advance(self, fetched_rows: list, col_index_map: dict[str, int]) -> None:
        n = len(fetched_rows)
        self.rows_done += n
        if n == 0:
            self._exhausted = True
            return

        # 마지막 행의 PK들을 next last_key로 저장
        last = fetched_rows[-1]
        new_key = []
        for pk in self.pk_cols:
            if pk in col_index_map:
                new_key.append(last[col_index_map[pk]])
            else:
                # SELECT 리스트에 PK가 원본 그대로 포함되지 않은 경우
                # (예: CAST(pk AS NVARCHAR) AS pk — 이 경우 인덱스는 찾지만 값이 변형됨)
                # 호출부가 col_index_map을 PK 원본값 기준으로 넘겨야 함.
                raise RuntimeError(
                    f"Keyset 진행 불가 — PK 컬럼 '{pk}'이 SELECT 결과에 포함되지 않음"
                )
        self.last_key = tuple(new_key)

        # 배치 크기보다 적게 왔으면 끝
        if n < self.batch_size:
            self._exhausted = True

    def checkpoint(self) -> PaginatorState:
        return PaginatorState(
            strategy=self.strategy, last_key=self.last_key,
            rows_done=self.rows_done, table=self.table,
        )

    def restore(self, state: PaginatorState) -> None:
        self.last_key = state.last_key
        self.rows_done = state.rows_done


# ── 전략 자동 선택 팩토리 ────────────────────────────────────

@dataclass
class PaginationPlan:
    """엔진이 사용할 최종 전략 설명 — 로그에 찍기 좋음"""
    strategy: str          # "keyset" or "offset"
    pk_cols: list[str] = field(default_factory=list)
    reason: str = ""       # 왜 이 전략이 선택됐는지
    paginator: BasePaginator | None = None


def plan_pagination(
    *,
    table: str,
    dialect: str,
    batch_size: int,
    select_expr: str,
    pk_candidates: list[dict],      # [{"name": "id", "data_type": "int"}, ...]
    fallback_order_by: str,
    total_rows: int | None = None,
) -> PaginationPlan:
    """
    테이블 메타데이터를 보고 Keyset/OFFSET 중 최적 전략을 선택.

    Args:
      pk_candidates: PK 컬럼들의 메타데이터.
                     반드시 "name"과 "data_type"을 가져야 함.
                     PK가 없으면 빈 리스트.
      fallback_order_by: OFFSET 전략에 사용할 ORDER BY 구절
                         (PK 없을 때 안정성을 위해 첫 컬럼 등).
    """
    # 1. PK 없음 → OFFSET
    if not pk_candidates:
        p = OffsetPaginator(
            table=table, select_expr=select_expr, dialect=dialect,
            batch_size=batch_size, order_by=fallback_order_by,
            total_rows=total_rows,
        )
        return PaginationPlan(
            strategy="offset", pk_cols=[],
            reason="PK 없음 — OFFSET fallback (대용량에서 느려질 수 있음)",
            paginator=p,
        )

    # 2. 복합 PK 너무 많음 → OFFSET
    if len(pk_candidates) > _MAX_COMPOSITE_PK_KEYS:
        pk_cols = [c["name"] for c in pk_candidates]
        p = OffsetPaginator(
            table=table, select_expr=select_expr, dialect=dialect,
            batch_size=batch_size,
            order_by=", ".join(_quote_id(c, dialect) for c in pk_cols),
            total_rows=total_rows,
        )
        return PaginationPlan(
            strategy="offset", pk_cols=pk_cols,
            reason=f"복합 PK {len(pk_candidates)}개 — Keyset 비용 높음, OFFSET 선택",
            paginator=p,
        )

    # 3. 타입 적합성 검사
    for c in pk_candidates:
        dt = (c.get("data_type") or "").lower().strip()
        # "int identity" 같은 경우 첫 단어만 보기
        root_type = dt.split()[0] if dt else ""
        if root_type in _KEYSET_INCOMPATIBLE_TYPES:
            pk_cols = [cc["name"] for cc in pk_candidates]
            p = OffsetPaginator(
                table=table, select_expr=select_expr, dialect=dialect,
                batch_size=batch_size,
                order_by=", ".join(_quote_id(cc, dialect) for cc in pk_cols),
                total_rows=total_rows,
            )
            return PaginationPlan(
                strategy="offset", pk_cols=pk_cols,
                reason=f"PK 컬럼 '{c['name']}'의 타입 '{dt}' Keyset 부적합 — OFFSET 선택",
                paginator=p,
            )
        if root_type not in _KEYSET_COMPATIBLE_TYPES:
            # 알 수 없는 타입 — 보수적으로 OFFSET
            pk_cols = [cc["name"] for cc in pk_candidates]
            p = OffsetPaginator(
                table=table, select_expr=select_expr, dialect=dialect,
                batch_size=batch_size,
                order_by=", ".join(_quote_id(cc, dialect) for cc in pk_cols),
                total_rows=total_rows,
            )
            return PaginationPlan(
                strategy="offset", pk_cols=pk_cols,
                reason=f"PK 컬럼 '{c['name']}' 타입 '{dt}' 화이트리스트 미포함 — OFFSET 선택 (보수적)",
                paginator=p,
            )

    # 4. Keyset 가능
    pk_cols = [c["name"] for c in pk_candidates]
    p = KeysetPaginator(
        table=table, select_expr=select_expr, dialect=dialect,
        batch_size=batch_size, pk_cols=pk_cols,
        total_rows=total_rows,
    )
    return PaginationPlan(
        strategy="keyset", pk_cols=pk_cols,
        reason=f"Keyset 사용 — PK {pk_cols}",
        paginator=p,
    )
