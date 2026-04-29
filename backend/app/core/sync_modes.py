"""
app/core/sync_modes.py
데이터 동기화 모드 정의 — 정직화된 용어 SSOT.

배경:
  기존 "CDC"라고 불리던 기능은 실제로는 timestamp 기반 증분 동기화였음.
  진짜 CDC(Change Data Capture)는 DB 트랜잭션 로그(binlog/WAL/redo log)를
  직접 읽는 기술을 의미하며, 이번 버전부터 명확히 구분한다.

모드 분류:
  1. migration       — 1회성 전체 이관 (app/engine/migration_engine.py)
  2. incremental     — timestamp/version 컬럼 기반 주기적 증분 동기화
                      (기존 CDC 엔진이 실제로 하던 것)
  3. binlog_cdc      — 진짜 CDC: MySQL binlog 등 트랜잭션 로그 직접 읽음
                      (이번 버전 신규 지원)

정직화 원칙:
  - UI에서 "CDC"라는 용어는 binlog_cdc 모드에만 사용
  - 기존 기능은 "증분 동기화"로 표기
  - API 경로는 /cdc/* 유지 (하위 호환), 엔드포인트 응답에 mode 명시
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class SyncModeInfo:
    key:           str           # 내부 식별자
    display_name:  str           # UI 표시명
    english_name:  str           # 영문명
    description:   str           # 설명
    mechanism:     str           # 동작 원리
    best_for:      str           # 적합한 사용처
    limitations:   str           # 한계
    supported_dbs: list          # 지원 DB 목록
    latency:       str           # 지연시간 특성


SYNC_MODES = {
    "migration": SyncModeInfo(
        key="migration",
        display_name="1회성 전체 이관",
        english_name="One-shot Migration",
        description="소스 DB 전체를 타겟 DB로 한 번 복제합니다. 이관 후에는 소스의 변경이 반영되지 않습니다.",
        mechanism="Keyset 페이지네이션으로 테이블 전체를 순차 조회 후 타겟에 적재",
        best_for="DB 이사, 클라우드 마이그레이션, 시스템 교체 시 초기 이전",
        limitations="이관 시점 이후 소스 변경은 반영 안 됨. 장기 운영 중이라면 증분 동기화 또는 CDC 병행 필요",
        supported_dbs=["mysql", "mariadb", "aurora", "tidb", "cloudsql",
                       "mssql", "azure", "sqlserver", "postgresql"],
        latency="N/A (1회성)",
    ),

    "incremental": SyncModeInfo(
        key="incremental",
        display_name="증분 동기화",
        english_name="Incremental Sync (Timestamp-based)",
        description="소스 테이블의 updated_at / modified_time 같은 타임스탬프 컬럼을 주기적으로 읽어 변경된 행만 타겟에 반영합니다.",
        mechanism="주기적 폴링: 마지막 동기화 시각 이후 변경된 행을 SELECT WHERE updated_at > last_sync 조회 → 타겟에 UPSERT/APPEND",
        best_for="DELETE가 드물고 updated_at 컬럼이 잘 관리되는 OLTP 테이블, 수 분~수십 분 지연이 허용되는 분석계",
        limitations=(
            "⚠ 물리 삭제(DELETE) 감지 불가 — soft-delete 패턴 필요. "
            "updated_at 컬럼이 없거나 갱신 안 되면 동작 안 함. "
            "폴링 주기 내 빠른 연속 변경은 일부 놓칠 수 있음. "
            "진짜 CDC가 아닌 주기적 쿼리 기반이므로 '준실시간'은 가능해도 '실시간'은 불가."
        ),
        supported_dbs=["mysql", "mariadb", "aurora", "tidb", "cloudsql",
                       "mssql", "azure", "sqlserver", "postgresql"],
        latency="폴링 주기에 비례 (보통 30초 ~ 5분)",
    ),

    "binlog_cdc": SyncModeInfo(
        key="binlog_cdc",
        display_name="CDC (MySQL binlog)",
        english_name="CDC — MySQL Binary Log",
        description="MySQL 계열 DB의 binary log를 replication slave처럼 구독하여 INSERT/UPDATE/DELETE를 이벤트로 수신합니다.",
        mechanism="MySQL replication protocol로 binlog stream 구독 (pymysqlreplication). ROW 포맷 이벤트 파싱 후 타겟에 적용.",
        best_for="물리 삭제 감지 필수, 초당 수백건 이상 변경, 초 단위 지연이 필요한 실시간 복제",
        limitations=(
            "소스는 MySQL 계열만 지원 (MariaDB, Aurora MySQL 포함). "
            "소스에 binlog 활성화 + REPLICATION SLAVE 권한 필요. "
            "binlog_format=ROW 권장 (STATEMENT는 파싱 한계). "
            "DDL 변경은 자동 처리 안 됨."
        ),
        supported_dbs=["mysql", "mariadb", "aurora"],
        latency="초 단위 (1~5초)",
    ),

    "pg_cdc": SyncModeInfo(
        key="pg_cdc",
        display_name="CDC (PostgreSQL Logical Replication)",
        english_name="CDC — PostgreSQL Logical Replication",
        description="PostgreSQL의 logical replication slot + wal2json/pgoutput plugin으로 WAL stream을 구독합니다.",
        mechanism="logical replication connection으로 slot 생성 후 WAL 이벤트 구독. wal2json plugin이 JSON으로 변경분 제공.",
        best_for="PostgreSQL 소스, 실시간 복제, 물리 삭제 포함 전체 변경 추적",
        limitations=(
            "소스는 PostgreSQL만 지원. "
            "wal_level=logical, max_replication_slots 설정 필요. "
            "wal2json plugin 설치 필요 (pgoutput은 기본 제공). "
            "슬롯을 drop 하지 않으면 WAL이 계속 누적 — 종료 시 반드시 정리. "
            "DDL 변경은 PostgreSQL 17+ 에서 일부만 지원."
        ),
        supported_dbs=["postgresql"],
        latency="초 단위 (1~3초)",
    ),

    "mssql_cdc": SyncModeInfo(
        key="mssql_cdc",
        display_name="CDC (SQL Server Change Data Capture)",
        english_name="CDC — SQL Server Change Data Capture",
        description="SQL Server의 내장 CDC 기능으로 변경 이력 테이블을 주기적으로 조회합니다.",
        mechanism="sys.sp_cdc_enable_db 로 DB 활성화 후 테이블별 capture instance 생성. cdc.fn_cdc_get_all_changes_* 함수를 LSN 기반으로 주기 조회.",
        best_for="SQL Server 소스, 변경 이력 감사 요구 있는 환경, 엔터프라이즈/개발자 에디션",
        limitations=(
            "소스는 SQL Server만 지원. "
            "Enterprise/Developer 에디션 권장 (Standard는 2016 SP1+ 가능). "
            "Express 에디션 미지원. "
            "SQL Server Agent 서비스 실행 필요 (capture/cleanup 작업). "
            "폴링 기반이라 지연 수 초 (push 아님). "
            "Azure SQL Database는 다른 구조 — 별도 검증 필요."
        ),
        supported_dbs=["mssql", "sqlserver"],
        latency="폴링 간격 (기본 5초)",
    ),
}


def get_cdc_engine_for(src_db: str) -> Optional[str]:
    """
    주어진 소스 DB에 가장 적합한 CDC 엔진 반환.
    UI의 "CDC 모드 자동 선택"에 사용.
    """
    src = (src_db or "").lower()
    if src in ("mysql", "mariadb", "aurora"):
        return "binlog_cdc"
    if src == "postgresql" or src == "postgres":
        return "pg_cdc"
    if src in ("mssql", "sqlserver"):
        return "mssql_cdc"
    return None


def is_cdc_supported_for(src_db: str) -> bool:
    """어떤 CDC 엔진이든 해당 DB를 지원하면 True"""
    return get_cdc_engine_for(src_db) is not None


def list_modes() -> list:
    """UI 드롭다운용 전체 모드 목록"""
    return [
        {
            "key":           m.key,
            "display_name":  m.display_name,
            "english_name":  m.english_name,
            "description":   m.description,
            "mechanism":     m.mechanism,
            "best_for":      m.best_for,
            "limitations":   m.limitations,
            "supported_dbs": m.supported_dbs,
            "latency":       m.latency,
        }
        for m in SYNC_MODES.values()
    ]


def get_mode_info(key: str) -> Optional[SyncModeInfo]:
    return SYNC_MODES.get(key)
