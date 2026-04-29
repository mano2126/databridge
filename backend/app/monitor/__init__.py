"""
DataBridge Monitor 모듈 — 다중 타겟 실시간 모니터링
v10 #22 — 2026-04-24

설계 철학:
  1. 어댑터 패턴: 모니터 대상이 무엇이든 동일한 인터페이스
     (로컬 PC / Docker / DB 자체 / SSH / WinRM / 원격 Docker ...)
  2. Migration-Aware: 시스템 지표뿐 아니라 이관 성능에 직결되는
     DB 내부 지표까지 제공 (Buffer Cache, Page Life, 블로킹 등)
  3. Graceful degradation: 어떤 어댑터 실패해도 다른 건 계속 동작
  4. 자산 재사용: DataBridge 기존 Connection Profile을 그대로 활용

모듈 구성:
  base.py             — 어댑터 인터페이스 + 공통 데이터 클래스
  registry.py         — 모니터 대상 등록/조회/관리
  adapter_localhost   — 로컬 OS (psutil)
  adapter_docker      — Docker (로컬 + 원격 확장)
  adapter_db_native   — DB 자체 성능 뷰 (MSSQL/MySQL/PG/Oracle)
  adapter_ssh         — SSH 원격 (Phase C)
  adapter_winrm       — Windows Remote Management (Phase C)
  alert_engine        — 임계값 기반 경고 (Phase B)
  history_store       — 시계열 기록 (Phase C)
"""
from app.monitor.base import (
    MonitorAdapter, MonitorSnapshot, MonitorTarget,
    SystemMetrics, DockerMetrics, DBMetrics, ProcessMetrics,
    Alert, AlertLevel, MetricDef,
)
from app.monitor.registry import MonitorRegistry, get_registry

__all__ = [
    "MonitorAdapter", "MonitorSnapshot", "MonitorTarget",
    "SystemMetrics", "DockerMetrics", "DBMetrics", "ProcessMetrics",
    "Alert", "AlertLevel", "MetricDef",
    "MonitorRegistry", "get_registry",
]
