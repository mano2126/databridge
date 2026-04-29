"""
app/monitor/base.py — 모니터 어댑터 공통 인터페이스 + 데이터 클래스
v10 #22 — 2026-04-24

모든 모니터 어댑터(Localhost/Docker/DBNative/SSH/WinRM)는 MonitorAdapter 를
상속하여 동일한 fetch_snapshot() 메서드를 제공한다.

이로써 UI 입장에서는 모니터 대상이 무엇이든 같은 방식으로 데이터를 받을 수 있다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


# ══════════════════════════════════════════════════════════
# 공통 데이터 클래스 — 모든 어댑터가 반환하는 표준 스키마
# ══════════════════════════════════════════════════════════

class AlertLevel(str, Enum):
    """경고 수준 (문자열 Enum → JSON 직렬화 자연스러움)"""
    INFO     = "info"        # 정보성 (파란색)
    WARNING  = "warning"     # 주의 (노란색)
    CRITICAL = "critical"    # 심각 (빨간색)


@dataclass
class Alert:
    """임계값 위반 또는 이상 상태 감지."""
    level:    AlertLevel
    code:     str            # "MSSQL_BUFFER_CACHE_LOW" 같은 식별자 (i18n 용이)
    message:  str            # 사람이 읽을 메시지 (한국어)
    metric:   Optional[str] = None   # 어떤 지표에서 발생했는지
    value:    Optional[float] = None # 실제 값
    threshold: Optional[float] = None # 임계값


@dataclass
class MetricDef:
    """어댑터가 제공하는 지표의 메타 정보 (UI 가 사용)."""
    key:         str            # "mem_pct"
    display:     str            # "메모리 사용률"
    unit:        str            # "%" / "MB" / "count" / "ms"
    description: str = ""
    warn_at:     Optional[float] = None
    critical_at: Optional[float] = None


@dataclass
class SystemMetrics:
    """OS 레벨 CPU/메모리 (호스트 관점)."""
    mem_total: int    = 0        # bytes
    mem_used:  int    = 0        # bytes
    mem_pct:   float  = 0.0      # 0~100
    cpu_pct:   float  = 0.0      # 0~100
    load_avg:  Optional[list[float]] = None  # [1m, 5m, 15m] (Unix만)
    uptime_sec: Optional[int]        = None
    disk_free_gb:  Optional[float]   = None  # 주요 볼륨 여유
    disk_used_pct: Optional[float]   = None


@dataclass
class DockerContainerMetric:
    """개별 Docker 컨테이너 지표."""
    name:      str
    status:    str                     # running/exited/...
    health:    Optional[str] = None    # healthy/unhealthy/starting/None
    mem_used:  int  = 0                # bytes (cache 제외)
    mem_limit: int  = 0                # bytes
    mem_pct:   float = 0.0
    cpu_pct:   float = 0.0
    image:     Optional[str] = None
    error:     Optional[str] = None    # 단일 컨테이너 stats 실패 시


@dataclass
class DockerMetrics:
    """Docker 호스트 수준 지표."""
    host_type: str                     # "local" | "remote"
    host_url:  Optional[str] = None    # 원격인 경우
    containers: list[DockerContainerMetric] = field(default_factory=list)


@dataclass
class DBMetrics:
    """
    Migration-Aware DB 메트릭 — 이관 성능에 직결되는 지표.
    어댑터는 가능한 항목만 채우고, 모르는 건 None 으로 둔다.
    """
    db_type:    str                    # mssql/mysql/postgresql/oracle
    db_version: Optional[str] = None

    # 메모리/캐시 계열 (가장 중요!)
    buffer_cache_hit_ratio:  Optional[float] = None  # % (95 아래면 경고)
    page_life_expectancy:    Optional[float] = None  # sec (MSSQL, 300 아래 경고)
    buffer_pool_used_pct:    Optional[float] = None  # % (MySQL InnoDB)
    total_memory_mb:         Optional[int]   = None  # DB 전체 할당
    used_memory_mb:          Optional[int]   = None

    # 세션/커넥션
    active_sessions:    Optional[int] = None
    blocked_sessions:   Optional[int] = None
    max_connections:    Optional[int] = None
    threads_running:    Optional[int] = None        # MySQL

    # I/O 지연 (이관 속도 직결)
    avg_read_latency_ms:   Optional[float] = None
    avg_write_latency_ms:  Optional[float] = None

    # 트랜잭션/락
    lock_waits:            Optional[int] = None
    long_running_queries:  Optional[int] = None     # 30초 이상

    # 임시 공간 (MSSQL tempdb — 본부장님 트라우마!)
    tempdb_free_mb:        Optional[float] = None
    tempdb_used_pct:       Optional[float] = None

    # 복제 지연 (replica 있는 경우)
    replication_lag_sec:   Optional[float] = None


@dataclass
class ProcessMetrics:
    """호스트 위 특정 프로세스 (DataBridge 프로세스 자신 등)."""
    pid:       int
    name:      str
    cpu_pct:   float = 0.0
    mem_mb:    float = 0.0
    threads:   int   = 0


@dataclass
class MigrationJobMetric:
    """현재 실행 중인 이관 Job 요약 — 모니터 팝업에 표시."""
    job_id:   str
    name:     str
    status:   str
    progress: float
    rows_processed: int
    rows_total:     int
    table_done:     int
    table_total:    int
    running_items:  list[dict] = field(default_factory=list)


@dataclass
class MonitorSnapshot:
    """
    어댑터가 반환하는 표준 스냅샷.
    프론트엔드는 어댑터 종류와 무관하게 이 구조를 받는다.
    """
    ts:             int                          # epoch ms
    target_id:      str
    target_type:    str                          # "localhost"/"docker"/"db_native"/...
    target_display: str                          # UI 라벨

    # 어댑터별 특화 필드 (해당 어댑터만 채움, 나머지는 None)
    system:  Optional[SystemMetrics]  = None
    docker:  Optional[DockerMetrics]  = None
    db:      Optional[DBMetrics]      = None
    process: Optional[ProcessMetrics] = None

    # 공통
    alerts:  list[Alert]              = field(default_factory=list)
    errors:  dict[str, str]           = field(default_factory=dict)

    # 이관 Job 정보 (전역 — 어댑터와 무관하게 한 번만 채움)
    jobs:    list[MigrationJobMetric] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """JSON 직렬화용 dict 변환.
        Enum/dataclass 를 재귀 변환하며, None 은 유지 (UI 에서 유무 판단)."""
        d = asdict(self)
        # AlertLevel Enum → str
        for a in d.get("alerts", []):
            if isinstance(a.get("level"), AlertLevel):
                a["level"] = a["level"].value
        return d


# ══════════════════════════════════════════════════════════
# 모니터 대상 정의 (Registry 에 저장됨)
# ══════════════════════════════════════════════════════════

@dataclass
class MonitorTarget:
    """
    사용자가 등록한 모니터 대상.
    비밀번호/키 같은 민감 정보는 암호화되어 저장됨.
    """
    target_id:      str                       # UUID or hash
    target_type:    str                       # "localhost"/"docker_local"/"docker_remote"/
                                              # "db_native"/"ssh"/"winrm"
    display_name:   str                       # UI 표시명
    enabled:        bool = True

    # 어댑터별 설정 (각 어댑터가 해석)
    config:         dict[str, Any] = field(default_factory=dict)

    # 추적/감사
    created_at:     Optional[str] = None
    created_by:     Optional[str] = None
    auto_detected:  bool = False              # 자동 감지로 추가된 것인지

    # 연계된 DataBridge Connection Profile ID (있는 경우)
    profile_id:     Optional[str] = None


# ══════════════════════════════════════════════════════════
# 어댑터 베이스 클래스
# ══════════════════════════════════════════════════════════

class MonitorAdapter(ABC):
    """
    모든 모니터 어댑터가 구현해야 하는 인터페이스.

    생애주기:
        1. __init__(target)   — 설정 파싱
        2. connect()          — 연결 수립 (idempotent)
        3. fetch_snapshot()   — 스냅샷 조회 (반복 호출됨)
        4. disconnect()       — 정리 (optional, 프로세스 종료 시)

    어댑터는 thread-safe 해야 한다 (API 서버가 동시 호출 가능).
    """
    # 서브클래스가 오버라이드
    ADAPTER_TYPE: str = "base"

    def __init__(self, target: MonitorTarget):
        self.target    = target
        self.target_id = target.target_id
        self._connected = False

    @abstractmethod
    def connect(self) -> bool:
        """연결 수립. 이미 연결돼 있으면 True 반환 (idempotent)."""
        raise NotImplementedError

    @abstractmethod
    def fetch_snapshot(self) -> MonitorSnapshot:
        """현재 스냅샷 반환. 빠르고 가볍게 (< 500ms 권장)."""
        raise NotImplementedError

    def disconnect(self) -> None:
        """리소스 정리. 기본은 no-op, 필요 시 오버라이드."""
        self._connected = False

    def available_metrics(self) -> list[MetricDef]:
        """이 어댑터가 제공하는 지표 목록. UI 설정 화면에 사용."""
        return []

    # 공통 유틸리티 ─────────────────────────────────────
    def _ts_ms(self) -> int:
        import time
        return int(time.time() * 1000)

    def _empty_snapshot(self, error: str = "") -> MonitorSnapshot:
        """연결 실패/오류 시 빈 스냅샷 (서버 응답 보장)."""
        snap = MonitorSnapshot(
            ts=self._ts_ms(),
            target_id=self.target_id,
            target_type=self.target.target_type,
            target_display=self.target.display_name,
        )
        if error:
            snap.errors["connect"] = error
        return snap
