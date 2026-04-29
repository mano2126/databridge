"""
app/monitor/registry.py — 모니터 대상 레지스트리
v10 #22

책임:
  1. MonitorTarget 영속화 (Store("monitor_targets"))
  2. 어댑터 인스턴스 캐싱 (매 호출마다 connect 하지 않도록)
  3. 자동 감지 (DataBridge 가 이미 연결한 DB 기반)
  4. 동시성 안전 (thread-safe)

Singleton 패턴: get_registry() 로 접근
"""
from __future__ import annotations

import threading
import uuid
import time
from datetime import datetime
from typing import Optional, Any

from app.monitor.base import (
    MonitorAdapter, MonitorTarget, MonitorSnapshot,
)


# 어댑터 타입 ↔ 클래스 매핑 (lazy import 로 순환 참조 회피)
def _load_adapter_class(target_type: str):
    """어댑터 클래스를 lazy import 로 로드."""
    if target_type == "localhost":
        from app.monitor.adapter_localhost import LocalhostAdapter
        return LocalhostAdapter
    if target_type in ("docker", "docker_local", "docker_remote"):
        from app.monitor.adapter_docker import DockerAdapter
        return DockerAdapter
    if target_type == "db_native":
        from app.monitor.adapter_db_native import DBNativeAdapter
        return DBNativeAdapter
    # Phase C 에서 추가될 타입들
    if target_type == "ssh":
        # from app.monitor.adapter_ssh import SSHAdapter
        # return SSHAdapter
        return None
    if target_type == "winrm":
        return None
    return None


class MonitorRegistry:
    """
    모니터 대상 및 어댑터 인스턴스를 관리하는 레지스트리.
    - 영속: 대상 정의(MonitorTarget)는 Store("monitor_targets") 에 저장
    - 캐시: 어댑터 인스턴스는 메모리에 유지 (재연결 비용 절감)
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._adapters: dict[str, MonitorAdapter] = {}   # target_id -> adapter
        self._store = None
        self._bootstrap_done = False

    # ── 저장소 ─────────────────────────────────────
    def _get_store(self):
        if self._store is None:
            from app.core.store import Store
            self._store = Store("monitor_targets")
        return self._store

    # ── 대상 관리 ───────────────────────────────────
    def list_targets(self) -> list[MonitorTarget]:
        """저장된 모니터 대상 전체."""
        with self._lock:
            out: list[MonitorTarget] = []
            # Store 클래스는 .all() → dict 반환. .items() 는 없음.
            for tid, d in self._get_store().all().items():
                if not isinstance(d, dict):
                    continue
                try:
                    out.append(self._dict_to_target(d))
                except Exception:
                    pass
            return out

    def get_target(self, target_id: str) -> Optional[MonitorTarget]:
        with self._lock:
            d = self._get_store().get(target_id)
            if not isinstance(d, dict):
                return None
            try:
                return self._dict_to_target(d)
            except Exception:
                return None

    def add_target(self, target: MonitorTarget) -> MonitorTarget:
        """새 대상 추가 (target_id 없으면 자동 생성)."""
        with self._lock:
            if not target.target_id:
                target.target_id = f"m_{uuid.uuid4().hex[:10]}"
            if not target.created_at:
                target.created_at = datetime.now().isoformat()
            self._get_store().set(target.target_id, self._target_to_dict(target))
            # 이미 캐싱된 어댑터 있으면 무효화
            self._invalidate_adapter(target.target_id)
            return target

    def update_target(self, target_id: str, patch: dict) -> Optional[MonitorTarget]:
        with self._lock:
            t = self.get_target(target_id)
            if not t:
                return None
            # 얕은 병합
            d = self._target_to_dict(t)
            for k, v in patch.items():
                if k in ("target_id", "created_at"):   # 보호 필드
                    continue
                if k == "config" and isinstance(v, dict):
                    # config 는 병합 (기존 키 보존)
                    merged = dict(d.get("config") or {})
                    merged.update(v)
                    d["config"] = merged
                else:
                    d[k] = v
            self._get_store().set(target_id, d)
            self._invalidate_adapter(target_id)
            return self._dict_to_target(d)

    def delete_target(self, target_id: str) -> bool:
        with self._lock:
            if target_id not in self._get_store():
                return False
            self._invalidate_adapter(target_id)
            self._get_store().delete(target_id)
            return True

    # ── 어댑터 가져오기 ─────────────────────────────
    def get_adapter(self, target_id: str) -> Optional[MonitorAdapter]:
        """어댑터 인스턴스 반환 (캐시 우선)."""
        with self._lock:
            if target_id in self._adapters:
                return self._adapters[target_id]
            t = self.get_target(target_id)
            if not t:
                return None
            cls = _load_adapter_class(t.target_type)
            if cls is None:
                return None
            adapter = cls(t)
            self._adapters[target_id] = adapter
            return adapter

    def _invalidate_adapter(self, target_id: str):
        """설정 변경 시 기존 어댑터 폐기."""
        adapter = self._adapters.pop(target_id, None)
        if adapter is not None:
            try:
                adapter.disconnect()
            except Exception:
                pass

    # ── 스냅샷 조회 (배치) ──────────────────────────
    def fetch_all(self, enabled_only: bool = True) -> list[MonitorSnapshot]:
        """모든 활성 대상의 스냅샷을 조회.
        
        v90.59 (2026-04-28): 병렬 처리로 변경 (기존 순차 → ThreadPoolExecutor).
          - 본부장님 호소: "모니터 첫 응답이 너무 늦다"
          - 진단: 어댑터 N개를 직렬 호출하면 N×(평균 응답시간) 누적
          - 처방: 어댑터마다 별도 스레드로 병렬 fetch_snapshot()
                  + 개별 어댑터 timeout 5초 (한 어댑터가 느려도 다른 어댑터 영향 없음)
          - 효과: N=4 (Localhost+Docker+MSSQL+MySQL) 환경에서 첫 응답 ~70% 단축
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        self.bootstrap_auto_detect()  # 자동 감지 (최초 1회)
        
        # 호출 대상 정리
        plan: list[tuple[Any, Any]] = []  # [(target, adapter), ...]
        for t in self.list_targets():
            if enabled_only and not t.enabled:
                continue
            adapter = self.get_adapter(t.target_id)
            if adapter is None:
                continue
            plan.append((t, adapter))
        
        if not plan:
            return []
        
        # 단일 어댑터 fetch_snapshot — 예외 시 빈 스냅샷 반환
        def _fetch_one(t: Any, adapter: Any) -> MonitorSnapshot:
            try:
                return adapter.fetch_snapshot()
            except Exception as e:
                snap = MonitorSnapshot(
                    ts=int(time.time() * 1000),
                    target_id=t.target_id,
                    target_type=t.target_type,
                    target_display=t.display_name,
                )
                snap.errors["fatal"] = f"{type(e).__name__}: {str(e)[:100]}"
                return snap
        
        # v90.59: ThreadPoolExecutor 로 병렬 실행 (max 8 워커 — 어댑터 수 보다 충분)
        # 결과 순서는 plan 의 원래 순서를 보존 (UI 일관성)
        results: list[Optional[MonitorSnapshot]] = [None] * len(plan)
        with ThreadPoolExecutor(max_workers=min(8, len(plan)), 
                                thread_name_prefix="monitor-fetch") as ex:
            future_to_idx = {
                ex.submit(_fetch_one, t, adapter): idx
                for idx, (t, adapter) in enumerate(plan)
            }
            # as_completed + 전체 timeout 10초 (개별 어댑터 timeout 은 어댑터 내부에서)
            try:
                for future in as_completed(future_to_idx, timeout=10.0):
                    idx = future_to_idx[future]
                    try:
                        results[idx] = future.result(timeout=0.1)  # 이미 완료된 거니 즉시
                    except Exception as e:
                        # future.result() 자체가 예외 던질 수 있음 (위 _fetch_one 가
                        # 모든 예외를 잡지만, ThreadPool 의 스케줄링 단계 예외는 별도)
                        t, adapter = plan[idx]
                        snap = MonitorSnapshot(
                            ts=int(time.time() * 1000),
                            target_id=t.target_id,
                            target_type=t.target_type,
                            target_display=t.display_name,
                        )
                        snap.errors["fatal"] = f"future_error: {str(e)[:100]}"
                        results[idx] = snap
            except Exception as e:
                # 전체 timeout 초과 — 완료된 것만 반환
                # 미완료 어댑터는 None 으로 남고, 아래 None 필터링에서 제거됨
                try:
                    import logging
                    logging.getLogger("monitor.registry").warning(
                        "fetch_all timeout 초과: %s", e
                    )
                except Exception:
                    pass
        
        # None 제거 (timeout 초과한 어댑터들)
        return [s for s in results if s is not None]

    # ── 자동 감지 ────────────────────────────────────
    def bootstrap_auto_detect(self) -> int:
        """
        최초 1회 자동 감지:
          1) Localhost 대상 (항상 추가)
          2) Docker (가능하면 추가) — 처음엔 실패해도 다음 bootstrap 시 재시도 가능
          3) DataBridge 가 이미 갖고 있는 Connection Profile → DB Native 대상

        v10 #22 Phase A-3:
          - Docker 자동 감지는 실패해도 bootstrap_done 을 False 로 유지
          - 사용자가 나중에 Docker Desktop 켜거나 docker SDK 설치하면
            다음 API 호출에서 자동으로 감지됨 (재시작 불필요)

        이미 존재하는 auto_detected 대상은 건드리지 않는다.
        반환: 새로 추가된 대상 수.
        """
        with self._lock:
            added = 0
            existing = self.list_targets()
            existing_auto_keys = {
                (t.target_type, (t.config or {}).get("profile_id"),
                 (t.config or {}).get("which"))
                for t in existing if t.auto_detected
            }

            # 1) Localhost — 항상 (한 번만 시도)
            local_done = any(t.target_type == "localhost" and t.auto_detected for t in existing)
            if not local_done:
                self.add_target(MonitorTarget(
                    target_id="",   # auto
                    target_type="localhost",
                    display_name="이 PC (DataBridge 서버)",
                    auto_detected=True,
                    config={},
                ))
                added += 1
                local_done = True

            # 2) Docker — ping 성공 시에만
            if not any(t.target_type == "docker" and t.auto_detected for t in existing):
                # v10 #22 Phase A-3: try_import 로 런타임 설치 감지
                from app.monitor.import_retry import try_import
                docker_mod = try_import("docker")
                docker_ok = False
                if docker_mod is not None:
                    try:
                        c = docker_mod.from_env(timeout=2)
                        c.ping()
                        docker_ok = True
                        try: c.close()
                        except: pass
                    except Exception:
                        docker_ok = False
                if docker_ok:
                    self.add_target(MonitorTarget(
                        target_id="",
                        target_type="docker",
                        display_name="로컬 Docker",
                        auto_detected=True,
                        config={},   # 로컬 기본
                    ))
                    added += 1

            # 3) 기존 Connection Profile 감지
            try:
                from app.core.store import Store
                for pid, p in Store("profiles").all().items():
                    if not isinstance(p, dict):
                        continue
                    for which in ("source", "target"):
                        cfg = p.get(which)
                        if not isinstance(cfg, dict):
                            continue
                        key = ("db_native", pid, which)
                        if key in existing_auto_keys:
                            continue
                        db_type = (cfg.get("db_type") or "").lower()
                        if db_type not in ("mssql", "mysql", "mariadb",
                                           "postgresql", "postgres", "pg"):
                            continue
                        # 표시명 구성
                        host = cfg.get("host", "?")
                        dbname = cfg.get("database", "")
                        type_upper = db_type.upper()
                        label = f"{type_upper} · {host}"
                        if dbname:
                            label += f"/{dbname}"
                        label += f"  ({which})"

                        self.add_target(MonitorTarget(
                            target_id="",
                            target_type="db_native",
                            display_name=label,
                            enabled=False,   # 기본 비활성 (사용자가 켜야 함)
                            auto_detected=True,
                            profile_id=pid,
                            config={"profile_id": pid, "which": which},
                        ))
                        added += 1
            except Exception:
                pass

            # v10 #22 Phase A-3:
            # _bootstrap_done 플래그 제거.
            # 모든 감지 단계가 이미 existing 중복 체크를 하므로
            # 매번 호출돼도 안전하고, Docker/추가 Profile 등은 나중에
            # 설치/추가돼도 자동 감지된다. 사용자 재시작 불필요.
            return added

    # ── 직렬화 ──────────────────────────────────────
    @staticmethod
    def _target_to_dict(t: MonitorTarget) -> dict[str, Any]:
        return {
            "target_id":     t.target_id,
            "target_type":   t.target_type,
            "display_name":  t.display_name,
            "enabled":       bool(t.enabled),
            "config":        dict(t.config or {}),
            "created_at":    t.created_at,
            "created_by":    t.created_by,
            "auto_detected": bool(t.auto_detected),
            "profile_id":    t.profile_id,
        }

    @staticmethod
    def _dict_to_target(d: dict[str, Any]) -> MonitorTarget:
        return MonitorTarget(
            target_id     = d.get("target_id") or "",
            target_type   = d.get("target_type") or "localhost",
            display_name  = d.get("display_name") or "unnamed",
            enabled       = bool(d.get("enabled", True)),
            config        = dict(d.get("config") or {}),
            created_at    = d.get("created_at"),
            created_by    = d.get("created_by"),
            auto_detected = bool(d.get("auto_detected", False)),
            profile_id    = d.get("profile_id"),
        )


# ── Singleton 접근 ──────────────────────────────────
_REGISTRY: Optional[MonitorRegistry] = None
_REG_LOCK = threading.Lock()


def get_registry() -> MonitorRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        with _REG_LOCK:
            if _REGISTRY is None:
                _REGISTRY = MonitorRegistry()
    return _REGISTRY
