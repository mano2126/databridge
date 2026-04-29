"""
app/monitor/adapter_localhost.py — 로컬 호스트 어댑터 (psutil)
v10 #22

DataBridge 서버가 실행되는 PC/서버 자신의 CPU/메모리/디스크를 모니터링한다.
인증 불필요. psutil 미설치 시 graceful degrade.
"""
from __future__ import annotations

import os
import time
from typing import Optional

from app.monitor.base import (
    MonitorAdapter, MonitorSnapshot, SystemMetrics,
    Alert, AlertLevel, MetricDef,
)
from app.monitor.import_retry import try_import


class LocalhostAdapter(MonitorAdapter):
    """psutil 기반 로컬 시스템 모니터."""

    ADAPTER_TYPE = "localhost"

    def __init__(self, target):
        super().__init__(target)
        self._psutil = None
        self._last_cpu_ts = 0.0   # cpu_percent interval 관리용
        self._process_start = time.time()

    def connect(self) -> bool:
        # 이미 정상 연결 상태면 빠른 반환
        if self._connected and self._psutil is not None:
            return True

        # v10 #22 Phase A-3: 런타임 설치 감지 (재시작 없이도 동작)
        #   - sys.modules 'None' 오염 제거
        #   - importlib.invalidate_caches()
        #   - 60초 rate limit (CPU 보호)
        ps = try_import("psutil")
        if ps is None:
            return False

        self._psutil = ps
        self._connected = True
        return True

    def fetch_snapshot(self) -> MonitorSnapshot:
        if not self.connect():
            return self._empty_snapshot("psutil not installed")

        snap = MonitorSnapshot(
            ts=self._ts_ms(),
            target_id=self.target_id,
            target_type=self.ADAPTER_TYPE,
            target_display=self.target.display_name,
        )

        try:
            ps = self._psutil
            vm = ps.virtual_memory()

            # cpu_percent(interval=None) 은 직전 호출과의 차이 계산
            # 처음 호출 시 0.0 반환 → 첫 호출 다음부터 의미 있는 값
            cpu = ps.cpu_percent(interval=None)

            sm = SystemMetrics(
                mem_total = int(vm.total),
                mem_used  = int(vm.used),
                mem_pct   = round(vm.percent, 1),
                cpu_pct   = round(cpu, 1),
            )

            # 업타임 (부팅 이후 초)
            try:
                sm.uptime_sec = int(time.time() - ps.boot_time())
            except Exception:
                pass

            # 디스크 (현재 작업 디렉토리 기준 볼륨)
            try:
                du = ps.disk_usage(os.getcwd())
                sm.disk_free_gb  = round(du.free / 1e9, 1)
                sm.disk_used_pct = round(du.percent, 1)
            except Exception:
                pass

            # Load Average (Unix 계열만)
            try:
                if hasattr(ps, "getloadavg"):
                    sm.load_avg = [round(x, 2) for x in ps.getloadavg()]
            except Exception:
                pass

            snap.system = sm

            # 알림 판정 (공통 규칙)
            snap.alerts.extend(self._check_alerts(sm))

        except Exception as e:
            snap.errors["fetch"] = f"{type(e).__name__}: {str(e)[:100]}"

        return snap

    def available_metrics(self) -> list[MetricDef]:
        return [
            MetricDef("mem_pct",       "메모리 사용률", "%",  warn_at=85, critical_at=95),
            MetricDef("cpu_pct",       "CPU 사용률",    "%",  warn_at=80, critical_at=95),
            MetricDef("disk_used_pct", "디스크 사용률", "%",  warn_at=85, critical_at=95),
        ]

    def _check_alerts(self, sm: SystemMetrics) -> list[Alert]:
        alerts: list[Alert] = []
        # 메모리 경고 — 본부장님이 겪은 상황 직접 감지
        if sm.mem_pct >= 95:
            alerts.append(Alert(
                level=AlertLevel.CRITICAL,
                code="HOST_MEM_CRITICAL",
                message=f"호스트 메모리 {sm.mem_pct:.0f}% — 이관 중단 위험",
                metric="mem_pct", value=sm.mem_pct, threshold=95,
            ))
        elif sm.mem_pct >= 85:
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                code="HOST_MEM_HIGH",
                message=f"호스트 메모리 {sm.mem_pct:.0f}% — 주의 필요",
                metric="mem_pct", value=sm.mem_pct, threshold=85,
            ))

        # CPU 경고
        if sm.cpu_pct >= 95:
            alerts.append(Alert(
                level=AlertLevel.CRITICAL,
                code="HOST_CPU_CRITICAL",
                message=f"CPU {sm.cpu_pct:.0f}% — 포화 상태",
                metric="cpu_pct", value=sm.cpu_pct, threshold=95,
            ))

        # 디스크 경고
        if sm.disk_used_pct is not None:
            if sm.disk_used_pct >= 95:
                alerts.append(Alert(
                    level=AlertLevel.CRITICAL,
                    code="HOST_DISK_CRITICAL",
                    message=f"디스크 {sm.disk_used_pct:.0f}% — 이관 실패 위험",
                    metric="disk_used_pct", value=sm.disk_used_pct, threshold=95,
                ))
            elif sm.disk_used_pct >= 85:
                alerts.append(Alert(
                    level=AlertLevel.WARNING,
                    code="HOST_DISK_HIGH",
                    message=f"디스크 {sm.disk_used_pct:.0f}% — 공간 확보 권장",
                    metric="disk_used_pct", value=sm.disk_used_pct, threshold=85,
                ))

        return alerts
