"""
app/core/supported_dbs.py
지원 DB 레벨 정의 — Single Source of Truth

Tier 정의:
  FULL      : 연결 + 스키마 조회 + 이관 + SQL 변환 (검증 완료)
  CONNECT   : 연결 + 스키마 조회만 (이관 미구현 또는 제한적)
  PLANNED   : 로드맵 (UI에 표시되지만 비활성 상태)

이 정보는 /api/v1/connectors/supported-dbs 엔드포인트로 제공되며
프론트엔드 UI가 DB 선택지를 렌더링할 때 이 값을 따른다.
프로젝트 내 다른 모듈은 이 모듈을 import 하여 사용한다 — 하드코딩 금지.
"""
from enum import Enum
from typing import Dict, List


class SupportTier(str, Enum):
    FULL     = "full"      # 완전 지원 (판매 가능)
    CONNECT  = "connect"   # 연결·조회만
    PLANNED  = "planned"   # 로드맵


# ── 지원 레벨 레지스트리 ────────────────────────────────────
# 각 DB의 기술적 실체와 판매 상품 관점을 모두 반영한다.
# label: UI 표시용 이름
# tier : 지원 레벨
# family: 호환 패밀리 (MySQL 패밀리는 내부적으로 pymysql 드라이버 공유)
# driver_module: import해야 하는 Python 패키지명 (의존성 체크용)
# default_port, icon은 UI 렌더링 보조 정보

_REGISTRY: Dict[str, dict] = {
    # ── Tier 1: Full Support (MVP 판매 대상) ──────────────
    "mysql": {
        "label": "MySQL",
        "tier": SupportTier.FULL,
        "family": "mysql",
        "driver_module": "pymysql",
        "default_port": 3306,
    },
    "mariadb": {
        "label": "MariaDB",
        "tier": SupportTier.FULL,
        "family": "mysql",
        "driver_module": "pymysql",
        "default_port": 3306,
    },
    "mssql": {
        "label": "SQL Server",
        "tier": SupportTier.FULL,
        "family": "mssql",
        "driver_module": "pyodbc",
        "default_port": 1433,
    },
    "postgresql": {
        "label": "PostgreSQL",
        "tier": SupportTier.FULL,
        "family": "postgresql",
        "driver_module": "psycopg2",
        "default_port": 5432,
    },

    # ── Tier 1 호환 패밀리 (MySQL/MSSQL 드라이버로 동작) ──
    # 실제로는 동일 드라이버를 쓰므로 FULL로 분류.
    # 다만 클라우드 특화 기능(Aurora Global, Azure AD 인증 등)은 별도 이슈.
    "aurora": {
        "label": "Amazon Aurora (MySQL)",
        "tier": SupportTier.FULL,
        "family": "mysql",
        "driver_module": "pymysql",
        "default_port": 3306,
        "note": "MySQL 호환. Aurora Global/Replica 기능은 이관 범위 외.",
    },
    "cloudsql": {
        "label": "Google Cloud SQL (MySQL)",
        "tier": SupportTier.FULL,
        "family": "mysql",
        "driver_module": "pymysql",
        "default_port": 3306,
    },
    "tidb": {
        "label": "TiDB",
        "tier": SupportTier.FULL,
        "family": "mysql",
        "driver_module": "pymysql",
        "default_port": 4000,
    },
    "azure": {
        "label": "Azure SQL Database",
        "tier": SupportTier.FULL,
        "family": "mssql",
        "driver_module": "pyodbc",
        "default_port": 1433,
        "note": "SQL Server 호환. Azure AD 인증은 미지원.",
    },

    # ── Tier 2: 연결·조회만 (이관 미구현) ─────────────────
    "oracle": {
        "label": "Oracle Database",
        "tier": SupportTier.CONNECT,
        "family": "oracle",
        "driver_module": "oracledb",
        "default_port": 1521,
        "note": "연결·스키마 조회 가능. 이관 엔진은 v2.1 로드맵.",
    },
    "sqlite": {
        "label": "SQLite",
        "tier": SupportTier.CONNECT,
        "family": "sqlite",
        "driver_module": "sqlite3",
        "default_port": 0,
        "note": "파일 기반. 소형 이관만 권장.",
    },

    # ── Tier 3: 로드맵 (UI 비활성) ────────────────────────
    "redshift":   {"label": "Amazon Redshift",   "tier": SupportTier.PLANNED, "family": "postgresql", "driver_module": "psycopg2",   "default_port": 5439},
    "snowflake":  {"label": "Snowflake",         "tier": SupportTier.PLANNED, "family": "snowflake",  "driver_module": "snowflake-connector-python", "default_port": 443},
    "bigquery":   {"label": "Google BigQuery",   "tier": SupportTier.PLANNED, "family": "bigquery",   "driver_module": "google-cloud-bigquery",      "default_port": 443},
    "mongodb":    {"label": "MongoDB",           "tier": SupportTier.PLANNED, "family": "mongodb",    "driver_module": "pymongo",    "default_port": 27017},
    "db2":        {"label": "IBM Db2",           "tier": SupportTier.PLANNED, "family": "db2",        "driver_module": "ibm_db",     "default_port": 50000},
    "hana":       {"label": "SAP HANA",          "tier": SupportTier.PLANNED, "family": "hana",       "driver_module": "hdbcli",     "default_port": 30015},
    "sybase":     {"label": "SAP Sybase ASE",    "tier": SupportTier.PLANNED, "family": "sybase",     "driver_module": "pyodbc",     "default_port": 5000},
    "teradata":   {"label": "Teradata",          "tier": SupportTier.PLANNED, "family": "teradata",   "driver_module": "teradatasql","default_port": 1025},
    "clickhouse": {"label": "ClickHouse",        "tier": SupportTier.PLANNED, "family": "clickhouse", "driver_module": "clickhouse-driver", "default_port": 9000},
    "duckdb":     {"label": "DuckDB",            "tier": SupportTier.PLANNED, "family": "duckdb",     "driver_module": "duckdb",     "default_port": 0},
}


# ── 공개 API ────────────────────────────────────────────

def all_dbs() -> List[dict]:
    """UI 렌더링용 전체 DB 목록 (tier 정보 포함)"""
    return [
        {"key": k, **{kk: vv for kk, vv in v.items() if kk != "driver_module"},
         "tier": v["tier"].value if isinstance(v["tier"], SupportTier) else v["tier"]}
        for k, v in _REGISTRY.items()
    ]


def get_info(db_type: str) -> dict | None:
    """특정 DB의 정보 반환 (없으면 None)"""
    return _REGISTRY.get((db_type or "").lower())


def get_tier(db_type: str) -> SupportTier | None:
    """특정 DB의 지원 레벨"""
    info = _REGISTRY.get((db_type or "").lower())
    return info["tier"] if info else None


def is_migration_supported(src_db: str, tgt_db: str) -> bool:
    """
    이관 가능한 조합인가?
    - 소스·타겟 모두 FULL tier여야 이관 엔진이 동작.
    - CONNECT tier(Oracle 등)는 소스로도 타겟으로도 이관 불가.
    """
    src_tier = get_tier(src_db)
    tgt_tier = get_tier(tgt_db)
    return src_tier == SupportTier.FULL and tgt_tier == SupportTier.FULL


def full_support_keys() -> List[str]:
    """이관 대상이 될 수 있는 DB 키 목록 (Full tier)"""
    return [k for k, v in _REGISTRY.items() if v["tier"] == SupportTier.FULL]


def family_of(db_type: str) -> str | None:
    """드라이버 공유 패밀리 반환 (mysql / mssql / postgresql / oracle / ...)"""
    info = _REGISTRY.get((db_type or "").lower())
    return info["family"] if info else None
