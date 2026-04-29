"""
DB 방언 추상 인터페이스 (v10 #9)

확장 가능한 청크 분할 + 인덱스 지연생성을 위한 DB별 동작 추상화.

Phase 2 에서는 MSSQL/MySQL 구현만 제공하고,
Phase 3b (Go) 에서 PostgreSQL, Oracle 등 추가 예정.

다른 DB 요청 시: 명시적 NotImplementedError → 호출자가 fallback 결정.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Any


@dataclass
class IndexInfo:
    """
    드롭/재생성 대상 인덱스 메타데이터.

    Phase 2 범위에서는 '세컨더리 인덱스' 만 대상으로 함 (PK 는 유지).
    PK 를 드롭하면 AUTO_INCREMENT/IDENTITY 컬럼의 INSERT 가 불가능.
    """
    name: str                            # 인덱스명
    table: str                           # 테이블명
    columns: List[str]                   # 구성 컬럼명 (순서 중요)
    is_unique: bool = False              # UNIQUE 여부
    index_type: Optional[str] = None     # BTREE / HASH / CLUSTERED / NONCLUSTERED 등
    original_sql: Optional[str] = None   # 복원용 원본 CREATE INDEX 문 (선택)

    def key(self) -> str:
        """식별자 (로그/비교용)"""
        return f"{self.table}.{self.name}"


@dataclass
class PKInfo:
    """PK 메타데이터 — 청크 분할 가능성 판단용"""
    columns: List[str]                   # PK 컬럼명 (복합 PK 가능)
    column_types: List[str]              # 각 컬럼의 DB 타입명
    is_composite: bool = False           # 복합 PK 여부

    @property
    def is_chunkable_arithmetic(self) -> bool:
        """
        산술 분할 가능 여부 판단.

        조건:
          - 단일 컬럼 PK
          - 정수 계열 타입 (BIGINT/INT/SMALLINT)

        복합 PK, CHAR/VARCHAR/UUID PK 는 False 반환 → 단일 스레드 fallback.
        """
        if self.is_composite or len(self.columns) != 1:
            return False
        ct = self.column_types[0].lower() if self.column_types else ""
        # 정수 계열만 산술 분할 대상
        _int_types = {
            "bigint", "int", "integer", "smallint", "tinyint",
            "mediumint",   # MySQL
            "number",      # Oracle (scale=0 인 경우만 — 여기서는 관대하게 포함)
        }
        return any(ct.startswith(t) for t in _int_types)


@dataclass
class ChunkRange:
    """단일 청크 범위 표현 (PK 기준)"""
    worker_id: int            # 1-based
    pk_column: str
    start_value: Any          # inclusive
    end_value: Any            # inclusive
    estimated_rows: int = 0   # 대략적 행수 (진행률 추정용)

    def describe(self) -> str:
        return (f"Worker#{self.worker_id}: "
                f"{self.pk_column} BETWEEN {self.start_value} AND {self.end_value} "
                f"(~{self.estimated_rows:,} rows)")


class DatabaseDialect(ABC):
    """
    DB별 청크 분할 및 인덱스 관리 동작 추상 인터페이스.

    각 DB 구현체는 이 클래스를 상속하여 필요한 메서드만 오버라이드.
    미구현 메서드 호출 시 NotImplementedError → 호출자가 fallback 결정.
    """

    # ── 메타데이터 조회 ────────────────────────────────────

    @abstractmethod
    def get_pk_info(self, conn, table: str) -> Optional[PKInfo]:
        """테이블의 PK 정보 조회. PK 없으면 None."""
        raise NotImplementedError

    @abstractmethod
    def get_secondary_indexes(self, conn, table: str) -> List[IndexInfo]:
        """
        PK 를 제외한 세컨더리 인덱스 목록.

        인덱스 지연생성 시 DROP 대상.
        """
        raise NotImplementedError

    @abstractmethod
    def get_pk_range(self, conn, table: str, pk_column: str) -> Tuple[Any, Any]:
        """
        PK 의 MIN/MAX 값 조회.

        반환: (min_value, max_value)
        행이 없으면 (None, None).
        """
        raise NotImplementedError

    # ── 인덱스 DDL 생성 ────────────────────────────────────

    @abstractmethod
    def drop_index_sql(self, index: IndexInfo) -> str:
        """DROP INDEX SQL 생성"""
        raise NotImplementedError

    @abstractmethod
    def create_index_sql(self, index: IndexInfo) -> str:
        """CREATE INDEX SQL 생성"""
        raise NotImplementedError

    # ── 청크 WHERE 조건 생성 ──────────────────────────────

    @abstractmethod
    def chunk_where_clause(self, pk_column: str, start_val: Any, end_val: Any) -> str:
        """
        청크별 WHERE 조건 SQL 조각 반환.

        예: "cust_id >= 1000001 AND cust_id <= 2250000"
        (값 인용, 컬럼 이스케이프는 구현체 책임)
        """
        raise NotImplementedError

    # ── 선택적 — 세션 튜닝 ────────────────────────────────

    def session_tune_before_load(self, conn) -> None:
        """
        벌크 로드 전 세션 레벨 튜닝 (선택 구현).
        기본: no-op. MySQL 구현체는 FK/UNIQUE 체크 해제 등.
        """
        pass

    def session_tune_after_load(self, conn) -> None:
        """벌크 로드 후 세션 레벨 복원 (선택 구현)."""
        pass

    # ── 식별자 ────────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """방언 이름 ('mssql', 'mysql' 등)"""
        raise NotImplementedError


class UnsupportedDialect(DatabaseDialect):
    """
    미구현 DB 용 플레이스홀더 — 모든 메서드가 NotImplementedError.

    청크 분할 엔진은 이 객체를 받으면 fallback (단일 스레드) 으로 전환.
    """
    def __init__(self, db_type: str):
        self._db_type = db_type

    @property
    def name(self) -> str:
        return self._db_type

    def _not_impl(self, op: str):
        raise NotImplementedError(
            f"DatabaseDialect for '{self._db_type}' not yet implemented (op: {op}). "
            f"Chunk parallelization requires MSSQL or MySQL in Phase 2. "
            f"Full DB support planned in Phase 3b (Go native pipeline)."
        )

    def get_pk_info(self, conn, table):
        self._not_impl("get_pk_info")

    def get_secondary_indexes(self, conn, table):
        self._not_impl("get_secondary_indexes")

    def get_pk_range(self, conn, table, pk_column):
        self._not_impl("get_pk_range")

    def drop_index_sql(self, index):
        self._not_impl("drop_index_sql")

    def create_index_sql(self, index):
        self._not_impl("create_index_sql")

    def chunk_where_clause(self, pk_column, start_val, end_val):
        self._not_impl("chunk_where_clause")


def get_dialect(db_type: str) -> DatabaseDialect:
    """
    DB 타입 문자열 → Dialect 인스턴스 팩토리.

    Phase 2 지원: mssql, mysql (mariadb 는 mysql 계열로 처리)
    미지원 DB: UnsupportedDialect 반환 → 호출자가 fallback 결정.
    """
    db_type = (db_type or "").lower()

    if db_type in ("mssql", "azure", "sqlserver"):
        from .mssql import MSSQLDialect
        return MSSQLDialect()

    if db_type in ("mysql", "mariadb", "aurora", "tidb", "cloudsql"):
        from .mysql import MySQLDialect
        return MySQLDialect()

    # 확장 지점 — Phase 3b 에서 여기 추가
    # if db_type == "postgres":
    #     from .postgres import PostgreSQLDialect
    #     return PostgreSQLDialect()

    return UnsupportedDialect(db_type)
