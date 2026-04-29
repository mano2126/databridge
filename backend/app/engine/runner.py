"""
app/engine/runner.py
백그라운드 이관 실행 래퍼.

기존에는 jobs.py에 _run_migration 으로 있었지만, FastAPI 라우터와
엔진을 연결하는 "조립선" 역할이라 엔진 패키지로 이동했다.

핵심 흐름:
  1. Store에서 Job 원본(암호문 포함) 로드
  2. decrypt_job_for_engine으로 복호화 사본 생성
  3. 엔진 인스턴스 생성, log_sink 주입
  4. 엔진.run() 실행
  5. 완료 후 엔진이 기록한 진행 상태를 원본에 머지 (비밀번호는 원본 암호문 유지)
  6. resume_from_checkpoint 플래그 정리

의존성 주입:
  - jobs_store:  Store("jobs") 인스턴스 (라우터가 주입)
  - migrators_registry:  {jid: engine} 딕셔너리 (pause/stop API가 엔진 참조할 수 있도록)
  - logs_registry:       {jid: [log_entries]} 딕셔너리 (GET /logs 응답용)
"""
from __future__ import annotations
import logging
import traceback
from typing import Any

from app.engine.migration_engine import MigrationEngine
from app.engine.security import decrypt_job_for_engine

logger = logging.getLogger("databridge.runner")


def run_migration(
    jid: str,
    *,
    jobs_store: Any,
    migrators_registry: dict,
    logs_registry: dict,
) -> None:
    """
    주어진 jid의 Job을 엔진으로 실행.

    예외 처리:
      - Store에 Job이 없으면 no-op
      - 엔진 예외는 잡 상태를 error로 기록하고 저장
      - finally에서 암호화된 원본 비밀번호는 평문으로 덮어쓰지 않음
    """
    job_obj = jobs_store.get(jid)
    if job_obj is None:
        return

    # 엔진에는 복호화된 사본 전달. 저장소의 암호문은 그대로 유지.
    engine_job = decrypt_job_for_engine(job_obj)

    engine = MigrationEngine(engine_job)

    # v9 패치 #9: 엔진이 테이블 완료/진행 시 로그를 내보낼 때마다
    #            현재 진행 상태를 저장소에 반영 (UI 실시간 업데이트용)
    #            비밀번호는 원본 암호문 유지 (복호화된 사본이 저장소에 노출되는 것 방지)
    # v9 패치 #16: 로그에 의존하지 않고 별도 스레드로 1초마다 저장소 갱신
    #              (큰 배치 처리 시 로그 간격이 수십초라 UI가 멈춰 보이는 문제 해결)
    _last_save_at = [0.0]
    _SAVE_MIN_INTERVAL = 0.5

    def _save_progress():
        import time as _t
        now = _t.monotonic()
        if now - _last_save_at[0] < _SAVE_MIN_INTERVAL:
            return
        _last_save_at[0] = now
        fresh = jobs_store.get(jid)
        if fresh is None:
            return
        # v48: Store 의 현재 status 가 'paused'/'aborted' 면 그 값 보존.
        # 주기 저장(1초 tick)이 engine_job["status"]="running" 으로 덮어써
        # 사용자의 pause 요청이 1초 내에 무효화되던 버그 근본 수정.
        _preserve_status = None
        if fresh.get("status") in ("paused", "aborted"):
            _preserve_status = fresh["status"]
        for k, v in engine_job.items():
            if k in ("src_password", "tgt_password"):
                continue
            fresh[k] = v
        if _preserve_status is not None:
            fresh["status"] = _preserve_status
        jobs_store.set(jid, fresh)

    # 엔진 로그 싱크 (로그 들어올 때마다 저장)
    def _sink(level, msg, entry):
        logs_registry.setdefault(jid, []).append(entry)
        try:
            _save_progress()
        except Exception:
            pass
    engine.set_log_sink(_sink)

    # 주기적 저장 스레드 (로그와 별개로 1초마다 진행률 반영)
    import threading
    _stop_ticker = threading.Event()
    def _periodic_save():
        while not _stop_ticker.wait(1.0):
            try:
                _save_progress()
            except Exception:
                pass
    _ticker = threading.Thread(target=_periodic_save, daemon=True, name=f"job-ticker-{jid[:8]}")
    _ticker.start()

    migrators_registry[jid] = engine

    try:
        engine.run()
    except Exception as e:
        logger.error(
            "이관 엔진 치명적 오류 [%s]: %s\n%s",
            jid[:8], e, traceback.format_exc(),
        )
        engine_job["status"] = "error"
        engine_job["error"] = str(e)[:300]
    finally:
        # v9 패치 #16: 주기 저장 스레드 중단
        _stop_ticker.set()
        # 엔진이 기록한 진행상태를 원본에 머지 (비밀번호는 원본 암호문 유지)
        for k, v in engine_job.items():
            if k in ("src_password", "tgt_password"):
                continue  # 평문이 저장소에 재기록되는 것 방지
            job_obj[k] = v
        # 실행 완료 — resume 플래그는 이번 사이클에서 소비됐으므로 제거
        # (다음 재개 요청 시 새로 세팅됨)
        job_obj.pop("resume_from_checkpoint", None)
        jobs_store.set(jid, job_obj)   # 최종 상태 저장
