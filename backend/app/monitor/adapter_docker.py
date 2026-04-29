"""
app/monitor/adapter_docker.py — Docker 어댑터 (로컬 + 원격)
v10 #22

설정 예시 (target.config):
  로컬:
    { "host_url": null }                                  # npipe/unix socket 자동
    { "host_url": "unix:///var/run/docker.sock" }

  원격 (TCP+TLS):
    {
      "host_url": "tcp://192.168.1.10:2376",
      "tls_verify": true,
      "tls_ca":   "/path/to/ca.pem",
      "tls_cert": "/path/to/cert.pem",
      "tls_key":  "/path/to/key.pem"
    }

  원격 (SSH):
    { "host_url": "ssh://user@192.168.1.10" }

docker SDK 미설치 / daemon 미연결 시 graceful degrade.
"""
from __future__ import annotations

from typing import Optional, Any

from app.monitor.base import (
    MonitorAdapter, MonitorSnapshot,
    DockerMetrics, DockerContainerMetric,
    Alert, AlertLevel, MetricDef,
)
from app.monitor.import_retry import try_import, mark_failed


# DB 컨테이너 우선 노출 (이관 관련 테이블이 위에 오도록)
def _container_priority(name: str) -> int:
    n = (name or "").lower()
    if "mssql"    in n: return 0
    if "mysql"    in n: return 1
    if "postgres" in n or "pg_" in n: return 2
    if "oracle"   in n: return 3
    if "maria"    in n: return 4
    if "mongo"    in n: return 5
    if "db_"      in n: return 6
    return 9


def _calc_cpu_pct(stats: dict) -> float:
    """Docker stats API CPU 사용률 공식 (nano-sec 단위)."""
    try:
        cpu_stats  = stats.get("cpu_stats",  {}) or {}
        precpu     = stats.get("precpu_stats", {}) or {}
        cpu_total  = cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
        pre_total  = precpu.get("cpu_usage", {}).get("total_usage", 0)
        sys_total  = cpu_stats.get("system_cpu_usage", 0)
        pre_sys    = precpu.get("system_cpu_usage", 0)
        online_cpus = cpu_stats.get("online_cpus") or \
                      len((cpu_stats.get("cpu_usage", {}) or {}).get("percpu_usage", []) or []) or 1

        cpu_delta = cpu_total - pre_total
        sys_delta = sys_total - pre_sys
        if sys_delta > 0 and cpu_delta > 0:
            return round((cpu_delta / sys_delta) * online_cpus * 100.0, 1)
    except Exception:
        pass
    return 0.0


class DockerAdapter(MonitorAdapter):
    """Docker 컨테이너 모니터 — 로컬/원격 모두 지원."""

    ADAPTER_TYPE = "docker"

    def __init__(self, target):
        super().__init__(target)
        self._client = None
        self._docker_mod = None
        self._conn_error: Optional[str] = None

    def connect(self) -> bool:
        if self._connected and self._client is not None:
            return True

        # v10 #22 Phase A-3: 런타임 설치 감지 (재시작 없이도 동작)
        docker = try_import("docker")
        if docker is None:
            self._conn_error = "docker SDK not installed (or retry cooldown active)"
            return False

        try:
            self._docker_mod = docker
            cfg = self.target.config or {}
            host_url = cfg.get("host_url")

            if host_url:
                # 원격 또는 명시적 소켓
                client_kwargs: dict[str, Any] = {
                    "base_url": host_url,
                    "timeout":  3,
                }
                if cfg.get("tls_verify"):
                    from docker.tls import TLSConfig
                    client_kwargs["tls"] = TLSConfig(
                        ca_cert=cfg.get("tls_ca"),
                        client_cert=(cfg.get("tls_cert"), cfg.get("tls_key"))
                                       if cfg.get("tls_cert") and cfg.get("tls_key") else None,
                        verify=True,
                    )
                self._client = docker.DockerClient(**client_kwargs)
            else:
                # from_env() — DOCKER_HOST 환경변수 or 기본 소켓 자동 감지
                # Windows: npipe:////./pipe/docker_engine
                # Linux:   unix:///var/run/docker.sock
                self._client = docker.from_env(timeout=3)

            # 연결 확인
            self._client.ping()
            self._connected = True
            self._conn_error = None
            return True
        except Exception as e:
            # daemon 이 꺼져있거나 권한 문제 등 — 모듈은 있지만 연결 실패
            # try_import 는 성공했으니 rate limit 별도 처리
            mark_failed("docker")
            self._conn_error = f"{type(e).__name__}: {str(e)[:120]}"
            return False

    def fetch_snapshot(self) -> MonitorSnapshot:
        snap = MonitorSnapshot(
            ts=self._ts_ms(),
            target_id=self.target_id,
            target_type=self.ADAPTER_TYPE,
            target_display=self.target.display_name,
        )

        if not self.connect():
            snap.errors["connect"] = self._conn_error or "unknown"
            return snap

        cfg = self.target.config or {}
        dm = DockerMetrics(
            host_type = "remote" if cfg.get("host_url") else "local",
            host_url  = cfg.get("host_url"),
        )

        try:
            containers = self._client.containers.list(filters={"status": "running"})
            for c in containers:
                metric = self._container_metric(c)
                dm.containers.append(metric)

            # DB 관련 컨테이너 우선 정렬
            dm.containers.sort(key=lambda x: (_container_priority(x.name), x.name))
            snap.docker = dm

            # 알림 생성 (unhealthy / 메모리 95% 초과)
            snap.alerts.extend(self._check_alerts(dm))

        except Exception as e:
            # daemon 자체 에러 — 연결 초기화 (다음 호출에서 재시도)
            self._connected = False
            self._client = None
            snap.errors["fetch"] = f"{type(e).__name__}: {str(e)[:100]}"

        return snap

    def _container_metric(self, c) -> DockerContainerMetric:
        """단일 컨테이너 stats 조회."""
        try:
            s = c.stats(stream=False)
            mem_stats = s.get("memory_stats", {}) or {}
            mem_used  = int(mem_stats.get("usage", 0) or 0)
            mem_limit = int(mem_stats.get("limit", 0) or 0)
            # Docker 는 cache 가 mem_used 에 포함 → 실제 사용량 = usage - cache
            cache = (mem_stats.get("stats", {}) or {}).get("cache", 0) or 0
            mem_real = max(0, mem_used - cache) if cache else mem_used

            # 헬스 상태
            health = None
            try:
                health = c.attrs.get("State", {}).get("Health", {}).get("Status")
            except Exception:
                pass

            # 이미지 태그
            image = None
            try:
                tags = c.image.tags
                image = tags[0] if tags else (c.image.short_id or None)
            except Exception:
                pass

            return DockerContainerMetric(
                name      = c.name,
                status    = c.status,
                health    = health,
                mem_used  = mem_real,
                mem_limit = mem_limit,
                mem_pct   = round(mem_real / mem_limit * 100, 1) if mem_limit else 0.0,
                cpu_pct   = _calc_cpu_pct(s),
                image     = image,
            )
        except Exception as e:
            return DockerContainerMetric(
                name=getattr(c, "name", "?"),
                status="stats_error",
                error=str(e)[:80],
            )

    def available_metrics(self) -> list[MetricDef]:
        return [
            MetricDef("container.mem_pct", "컨테이너 메모리", "%", warn_at=80, critical_at=95),
            MetricDef("container.cpu_pct", "컨테이너 CPU",    "%", warn_at=80, critical_at=95),
            MetricDef("container.health",  "헬스 상태",       "status"),
        ]

    def _check_alerts(self, dm: DockerMetrics) -> list[Alert]:
        alerts: list[Alert] = []
        for c in dm.containers:
            # 🔴 unhealthy — 본부장님이 10시간 방치했던 바로 그 상황
            if c.health == "unhealthy":
                alerts.append(Alert(
                    level=AlertLevel.CRITICAL,
                    code="CONTAINER_UNHEALTHY",
                    message=f"컨테이너 {c.name} 이 unhealthy 상태 — 재시작 권장",
                    metric=f"{c.name}.health",
                ))
            # 메모리 압박
            if c.mem_pct >= 95:
                alerts.append(Alert(
                    level=AlertLevel.CRITICAL,
                    code="CONTAINER_MEM_CRITICAL",
                    message=f"{c.name} 메모리 {c.mem_pct:.0f}% — OOM 위험",
                    metric=f"{c.name}.mem_pct", value=c.mem_pct, threshold=95,
                ))
            elif c.mem_pct >= 80:
                alerts.append(Alert(
                    level=AlertLevel.WARNING,
                    code="CONTAINER_MEM_HIGH",
                    message=f"{c.name} 메모리 {c.mem_pct:.0f}% — 주의",
                    metric=f"{c.name}.mem_pct", value=c.mem_pct, threshold=80,
                ))
        return alerts

    def disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
        self._client = None
        self._connected = False
