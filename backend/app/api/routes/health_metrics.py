"""
app/api/routes/health_metrics.py — 헬스체크 강화 + Prometheus 메트릭
v10 #21 — 2026-04-21

제공 엔드포인트:
  GET /health           — 기본 ok/version (기존 유지, main.py 에 있음)
  GET /api/v1/health/detailed — 상세 헬스 (DB·디스크·활성Job)
  GET /metrics          — Prometheus text format (text/plain)

왜 /metrics 는 /api/v1 밖인가:
  Prometheus exporter 관례상 /metrics 루트 경로. 방화벽 rule 단순화 목적.
"""
from __future__ import annotations

import os
import shutil
import time
from fastapi import APIRouter, Response

# 두 개 라우터 — main.py 에서 각각 다른 prefix 로 등록됨
# - router        : /api/v1 prefix 아래 /health/detailed
# - metrics_router: 루트 경로 /metrics (Prometheus 관례)
router = APIRouter()
metrics_router = APIRouter()

# 프로세스 시작 시각 (uptime 계산용)
_START_EPOCH = time.time()


def _db_check() -> dict:
    """SQLite 파일 존재 여부 + 간단 read 쿼리."""
    try:
        from app.core.store import Store
        s = Store("settings")
        _ = len(s)
        return {"ok": True, "store": "sqlite"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def _disk_check(path: str = ".") -> dict:
    """디스크 잔여 용량 체크."""
    try:
        total, used, free = shutil.disk_usage(path)
        pct = round(used / total * 100, 1) if total else 0
        return {
            "ok": free > 500 * 1024 * 1024,   # 500MB 여유 있어야 ok
            "total_gb": round(total / 1e9, 2),
            "used_pct": pct,
            "free_gb":  round(free / 1e9, 2),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def _active_jobs_count() -> int:
    """running 상태의 Job 수 — Store 직접 조회."""
    try:
        from app.core.store import Store
        running = 0
        for j in Store("jobs").values():
            if isinstance(j, dict) and j.get("status") in ("running", "queued"):
                running += 1
        return running
    except Exception:
        return -1


def _api_key_configured() -> bool:
    """Anthropic API 키 설정 여부 (값은 노출 안 함)."""
    try:
        from app.api.routes.settings import _cfg
        k = (_cfg() or {}).get("anthropic_api_key", "") or ""
        return bool(k and k != "ollama")
    except Exception:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))


# ══════════════════════════════════════════════════════════
# /api/v1/health/detailed — 운영자용 상세 점검
# ══════════════════════════════════════════════════════════
@router.get("/health/detailed")
def health_detailed():
    db   = _db_check()
    disk = _disk_check()
    active = _active_jobs_count()
    api_key = _api_key_configured()

    ok = db["ok"] and disk["ok"]
    return {
        "ok":            ok,
        "version":       "2.0.0",
        "uptime_sec":    int(time.time() - _START_EPOCH),
        "database":      db,
        "disk":          disk,
        "active_jobs":   active,
        "api_key_configured": api_key,
        "timestamp":     int(time.time()),
    }


# ══════════════════════════════════════════════════════════
# /metrics — Prometheus text format (exposition format v0.0.4)
# ══════════════════════════════════════════════════════════
@metrics_router.get("/metrics")
def metrics():
    """
    Prometheus scrape 용 메트릭.
    내부 Grafana 대시보드와 연동 가능.
    인증 불필요 (scrape 대상이므로). 운영 시엔 방화벽/IP 제한 권장.
    """
    lines: list[str] = []

    def add(name: str, value: float | int, help_: str, type_: str = "gauge"):
        lines.append(f"# HELP {name} {help_}")
        lines.append(f"# TYPE {name} {type_}")
        lines.append(f"{name} {value}")

    # uptime
    add("databridge_uptime_seconds", int(time.time() - _START_EPOCH),
        "Process uptime in seconds.")

    # 활성 Job
    add("databridge_jobs_active", _active_jobs_count(),
        "Number of jobs currently running or queued.")

    # 디스크 사용률
    disk = _disk_check()
    add("databridge_disk_used_percent", disk.get("used_pct", 0),
        "Disk used percent on the database volume.")
    add("databridge_disk_free_bytes",
        int(disk.get("free_gb", 0) * 1e9),
        "Disk free bytes.")

    # KB 학습 메트릭 (conversion_learner)
    try:
        from app.engine.conversion_learner import get_metrics
        m = get_metrics(days=1).get("summary", {})
        add("databridge_ai_calls_today",   m.get("ai_calls", 0),
            "Anthropic API calls today.")
        add("databridge_local_hits_today", m.get("local_hits", 0),
            "Local KB conversion hits today.")
        add("databridge_patterns_learned_today", m.get("patterns_learned", 0),
            "New conversion patterns auto-learned today.")
    except Exception:
        pass

    # DB 연결 상태 (1=ok, 0=fail)
    db = _db_check()
    add("databridge_db_healthy", 1 if db["ok"] else 0,
        "Is the internal metadata DB healthy? 1=ok.")

    body = "\n".join(lines) + "\n"
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")
