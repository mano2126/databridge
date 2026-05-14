"""
app/api/routes/jobs.py
Job 관리 REST API.

이관 엔진 자체는 app/engine 패키지로 분리됨:
  - app.engine.MigrationEngine   : 실제 데이터 이관 수행
  - app.engine.run_migration     : 백그라운드 실행 래퍼
  - app.engine.new_job           : Job dict 팩토리
  - app.engine.encrypt_job_passwords / decrypt_job_for_engine / mask_job_response
                                 : 비밀번호 암호화/복호화/마스킹
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, Request
from typing import Optional
import uuid, threading, time, random, logging
from datetime import datetime, timezone, timedelta

_KST = timezone(timedelta(hours=9))

from app.core.store import Store
from app.core.auth_deps import require_viewer, require_operator, require_admin
from app.core import audit as _audit
from app.core.audit import Actions as _AuditActions
from app.scheduler.engine import get_engine as _get_scheduler

# 엔진 패키지 — 이관 핵심 로직
from app.engine import (
    MigrationEngine,
    run_migration as _run_migration_impl,
    new_job as _new_job,
    encrypt_job_passwords as _encrypt_job_passwords,
    decrypt_job_for_engine as _decrypt_job_for_engine,
    mask_job_response as _mask_job_response,
    MASK_TOKEN as _MASK_TOKEN,
)

logger = logging.getLogger("databridge.jobs")

router = APIRouter()

# ── 영속 스토어 ─────────────────────────────────────────
_jobs      = Store("jobs")
_schedules = Store("schedules")

# ── 런타임 전용 (재시작 시 리셋 OK) ──────────────────────
_job_logs:  dict = {}   # job_id → log list (메모리 전용, GET /logs 응답용)
_migrators: dict = {}   # job_id → MigrationEngine (pause/stop 용)


# ── 백그라운드 이관 실행 래퍼 ─────────────────────────────
# engine.runner.run_migration에 실행 컨텍스트(store/레지스트리)를 주입.
# FastAPI BackgroundTasks는 단일 시그니처 함수를 기대하므로 wrapper가 필요.
def _run_migration(jid: str) -> None:
    _run_migration_impl(
        jid,
        jobs_store=_jobs,
        migrators_registry=_migrators,
        logs_registry=_job_logs,
    )


def _attach_log_sink(engine, jid: str) -> None:
    """
    v9 패치 #47: 재이관 엔드포인트용 로그 싱크 주입 헬퍼.
    엔진의 self._log(...) 호출이 프론트 로그 뷰어에 나타나도록 _job_logs 에 연결.
    메인 이관 경로 (engine/runner.py) 와 동일한 동작.
    """
    def _sink(level, msg, entry):
        try:
            _job_logs.setdefault(jid, []).append(entry)
        except Exception:
            pass
    engine.set_log_sink(_sink)


# ── 샘플 Job — jobs.json 없을 때만 생성 ─────────────────
if len(_jobs) == 0:
    for _name, _src, _tgt, _status, _prog in [
        ("sakila → target_db 이관",  "mysql",  "mssql",      "completed", 100),
        ("oracle_hr → postgresql",   "oracle", "postgresql", "idle",       0),
    ]:
        _jid    = str(uuid.uuid4())
        _rows_t = random.randint(50000, 500000)
        _j = _new_job(_jid, _name, _src, _tgt)
        _j.update({
            "status": _status,
            "progress": _prog,
            "rows_processed": int(_prog * _rows_t / 100),
            "rows_total": _rows_t,
            "finished_at": datetime.now(_KST).isoformat() if _status == "completed" else None,
        })
        _jobs.set(_jid, _j)
        _job_logs[_jid] = []



# ── REST API ──────────────────────────────────────────────

# ── 스케줄 ───────────────────────────────────────────────
@router.get("/schedules")
def list_schedules(_=Depends(require_viewer)):
    now = datetime.now(_KST)
    scheds = _schedules.values()
    updated = []
    for s in scheds:
        # once 타입이고 run_at이 지났으면 자동 만료
        if s.get("type") == "once" and s.get("status") == "active" and s.get("run_at"):
            try:
                run_at = datetime.fromisoformat(s["run_at"].replace("Z",""))
                if run_at < now and s.get("run_count", 0) == 0:
                    s["status"] = "expired"
                    _schedules.set(s["id"], s)
            except Exception:
                pass
        updated.append(s)
    return updated


@router.get("/schedules/history")
def schedules_history(limit: int = 100, _=Depends(require_viewer)):
    """
    v9 #63d / #64: 스케줄 최근 실행 이력.
    CDC 실행은 audit_logs 에 영구 기록되므로 거기서 우선 조회.
    일반 스케줄 Job 은 jobs 에서 매칭.
    """
    from app.core import audit as _audit
    from app.core.store import Store as _S
    cfg_store = _S("cdc_configs")
    cdc_cfgs = {k: v for k, v in cfg_store.all().items() if isinstance(v, dict)}
    # cfg_id → cfg (이름 매핑용)
    # 스케줄에서 cfg_id → schedule name 도 찾아 붙여줌
    sched_list = _schedules.values()
    sched_name_by_cfgid = {}
    for s in sched_list:
        cfg = (s.get("job_config") or {})
        cid = cfg.get("cdc_cfg_id")
        if cid:
            sched_name_by_cfgid[cid] = s.get("name", "")

    history = []

    # 1) CDC 실행 이력 (audit_logs 에서)
    try:
        audit_q = _audit.query(
            action_prefix="cdc.run",
            limit=limit * 3,
        )
        for e in audit_q.get("items", []):
            details = e.get("details") or {}
            cdc_id = e.get("resource_id") or ""
            name_candidate = sched_name_by_cfgid.get(cdc_id) or details.get("name") or cdc_id
            dur_sec = int(details.get("duration_sec") or 0)
            if dur_sec < 60:
                duration = f"{dur_sec}초"
            elif dur_sec < 3600:
                duration = f"{dur_sec // 60}분 {dur_sec % 60}초"
            else:
                duration = f"{dur_sec // 3600}시간 {(dur_sec % 3600) // 60}분"
            history.append({
                "id":          e.get("id") or f"{cdc_id}_{details.get('run_no','')}",
                "name":        name_candidate,
                "run_at":      details.get("started_at") or e.get("ts"),
                "duration":    duration,
                "result":      "ok" if e.get("status") == "ok" else "error",
                "rows":        int(details.get("rows") or 0),
                "errors":      int(details.get("errors") or 0),
                "job_id":      cdc_id,
                "schedule_id": "",
                "source":      "cdc",
                "run_no":      details.get("run_no"),
                "error_msg":   details.get("error", ""),
            })
    except Exception as _he:
        logger.warning("CDC audit 이력 조회 실패: %s", _he)

    # 2) 일반 스케줄 Job 이력 (Jobs 에서 이름 매칭)
    try:
        sched_by_name = {s.get("name"): s for s in sched_list if s.get("name")}
        for j in _jobs.values():
            if not isinstance(j, dict): continue
            if j.get("job_type") == "cdc": continue  # CDC 는 위에서 처리됨
            jname = j.get("name", "")
            if jname not in sched_by_name: continue
            sch = sched_by_name[jname]
            duration = "-"
            if j.get("started_at") and j.get("finished_at"):
                try:
                    _s2 = datetime.fromisoformat(j["started_at"].replace("Z",""))
                    _f2 = datetime.fromisoformat(j["finished_at"].replace("Z",""))
                    sec  = max(0, (_f2 - _s2).total_seconds())
                    if sec < 60: duration = f"{int(sec)}초"
                    elif sec < 3600: duration = f"{int(sec//60)}분 {int(sec%60)}초"
                    else: duration = f"{int(sec//3600)}시간 {int((sec%3600)//60)}분"
                except Exception: pass
            history.append({
                "id":           j.get("id"),
                "name":         sch.get("name") or jname,
                "run_at":       j.get("started_at") or j.get("created_at"),
                "duration":     duration,
                "result":       "ok" if j.get("status") == "completed"
                                else ("error" if j.get("status") in ("error","aborted") else "running"),
                "rows":         j.get("rows_processed", 0),
                "errors":       j.get("rows_error", 0),
                "job_id":       j.get("id"),
                "schedule_id":  sch.get("id"),
                "source":       "job",
            })
    except Exception as _je:
        logger.warning("일반 Job 이력 조회 실패: %s", _je)

    # 최신 순 정렬
    history.sort(key=lambda h: h.get("run_at") or "", reverse=True)
    return history[:limit]


@router.post("/schedules/history")
def purge_schedule_history(_=Depends(require_operator)):
    """v9 #64: 선택적 — 이력 수동 정리용 (현재는 audit 에만 기록되므로 거의 불필요)"""
    return {"ok": True}


@router.post("/cdc/migrate-legacy-jobs")
def migrate_legacy_cdc_jobs(_=Depends(require_operator)):
    """
    v9 #64: 옛 스타일 CDC Job (id = cfg_id_suffix) 들을 정리.

    #64 이후 CDC Job 은 cfg_id 자체를 ID 로 쓰므로,
    과거에 생성된 cfg_id_xxxxxx 형태의 Job 들은 '이전 실행 이력' 개념으로
    정리가 필요. 이 엔드포인트는:
      - suffix 있는 옛 Job 을 모두 삭제 (audit 에 기록 옮김)
      - 새 고정 ID Job 은 유지
    """
    import re as _re
    removed = []
    archived = 0
    from app.core import audit as _audit
    for j in list(_jobs.values()):
        if not isinstance(j, dict): continue
        if j.get("job_type") != "cdc": continue
        jid = j.get("id", "")
        m = _re.match(r"^(.+)_[0-9a-f]{6}$", str(jid), _re.IGNORECASE)
        if not m: continue   # 신스타일은 유지
        # 옛 Job — audit 에 저장 후 삭제
        try:
            duration_sec = 0
            if j.get("started_at") and j.get("finished_at"):
                try:
                    _s = datetime.fromisoformat(j["started_at"].replace("Z",""))
                    _f = datetime.fromisoformat(j["finished_at"].replace("Z",""))
                    duration_sec = max(0, (_f - _s).total_seconds())
                except Exception: pass
            _audit.record(
                action="cdc.run.complete" if j.get("status") == "completed" else "cdc.run.error",
                resource="cdc",
                resource_id=m.group(1),
                status="ok" if j.get("status") == "completed" else "fail",
                details={
                    "name":         j.get("name", "CDC"),
                    "started_at":   j.get("started_at"),
                    "finished_at": j.get("finished_at"),
                    "duration_sec": duration_sec,
                    "rows":         j.get("rows_processed", 0),
                    "errors":       j.get("rows_error", 0),
                    "migrated":     True,
                },
            )
            archived += 1
        except Exception: pass
        try:
            _jobs.delete(jid)
            removed.append(jid)
        except Exception: pass
    return {"ok": True, "removed_count": len(removed), "archived_to_audit": archived}


@router.post("/schedules", status_code=201)
def create_schedule(body: dict, bg: BackgroundTasks, _=Depends(require_operator)):
    """특정 시간 / cron 기반 스케줄 Job 등록"""
    sid = str(uuid.uuid4())[:8]
    sch = {
        "id":          sid,
        "job_config":  body.get("job_config", {}),
        "type":        body.get("type", "once"),
        "run_at":      body.get("run_at", ""),
        "cron_expr":   body.get("cron_expr", ""),
        "interval_min":body.get("interval_min", 60),
        "name":        body.get("name", "스케줄 Job"),
        "status":      "waiting",
        "created_at":  datetime.now(_KST).isoformat(),
        "next_run":    body.get("run_at", ""),
        "run_count":   0,
    }
    _schedules.set(sid, sch)

    # APScheduler 엔진에 등록 (once/interval/cron 모두 처리)
    try:
        _get_scheduler().add(sid, sch)
        # 다음 실행 시각 갱신
        nxt = _get_scheduler().next_run(sid)
        if nxt:
            sch["next_run"] = nxt
            _schedules.set(sid, sch)
    except Exception as _se:
        logger.warning("스케줄러 등록 실패: %s", _se)
        # 폴백: once 타입만 threading 처리
        if sch["type"] == "once" and sch["run_at"]:
            try:
                target = datetime.fromisoformat(sch["run_at"].replace("Z",""))
                diff   = (target - datetime.now(_KST)).total_seconds()
                if diff <= 0:
                    _run_scheduled(sid, bg)
                elif diff < 300:
                    def delayed():
                        import time as _t; _t.sleep(max(0, diff))
                        _run_scheduled(sid, None)
                    threading.Thread(target=delayed, daemon=True).start()
            except Exception:
                pass
    return sch


def _run_scheduled(sid: str, bg):
    if sid not in _schedules:
        return
    sch = _schedules.get(sid)
    sch["status"]    = "running"
    sch["run_count"] = sch.get("run_count", 0) + 1
    sch["last_run"]  = datetime.now(_KST).isoformat()
    try:
        nxt = _get_scheduler().next_run(sid)
        if nxt: sch["next_run"] = nxt
    except Exception:
        pass
    _schedules.set(sid, sch)

    cfg      = sch["job_config"]
    job_type = cfg.get("job_type", "migration")  # 'migration' | 'cdc'
    jid      = str(uuid.uuid4())

    # ── CDC 스케줄 ──────────────────────────────────────────────
    if job_type == "cdc":
        from app.core.cdc_engine import run_cdc, get_cdc_status, get_all_cdc_status
        cdc_cfg_id = cfg.get("cdc_cfg_id", "")
        cdc_cfg    = cfg.get("cdc_config", {})
        if not cdc_cfg_id or not cdc_cfg:
            logger.error("[%s] CDC 스케줄: cdc_cfg_id 또는 cdc_config 없음", sid)
            sch["status"] = "error"
            _schedules.set(sid, sch)
            return

        # v9 패치 #62: 중복 실행 방지
        # uvicorn --reload 로 APScheduler 가 2중 등록되어 1분마다 2번 발동하는 경우,
        # 같은 cfg_id 의 CDC 가 이미 최근 5초 내 실행됐다면 스킵 (중복 방지).
        try:
            _now_ts = datetime.now(_KST).timestamp()
            for _running_id, _running_state in list(get_all_cdc_status().items()):
                # 같은 config 기반인지 + 최근 시작됐는지 체크
                if not _running_id.startswith(f"{cdc_cfg_id}_"):
                    continue
                _started = _running_state.get("started_at", "")
                if _started:
                    try:
                        _st_dt = datetime.fromisoformat(_started.replace("Z",""))
                        if _st_dt.tzinfo is None:
                            _st_dt = _st_dt.replace(tzinfo=_KST)
                        _age = _now_ts - _st_dt.timestamp()
                        if _age < 5:  # 5초 이내 실행된 동일 cfg
                            logger.warning(
                                "[%s] CDC 중복 실행 스킵 — %s 가 %.1f초 전 실행됨",
                                sid, _running_id, _age)
                            return
                    except Exception: pass
        except Exception: pass

        # CDC 매 실행마다 새 Job (cdc_id = cfg_id_suffix)
        # (Job 관리 페이지에서 cdc_cfg_id 기준 그룹화해서 표시)
        cdc_id = f"{cdc_cfg_id}_{jid[:6]}"

        def run_cdc_job():
            try:
                tables = cdc_cfg.get("tables") or []
                logger.info("[%s] CDC 스케줄 실행 — 테이블 %d개 cfg_id=%s", sid, len(tables), cdc_cfg_id)
                if not tables:
                    logger.error("[%s] CDC 스케줄: tables 비어있음", sid)
                # base_date 제거 — 스케줄 실행 시 last_sync 우선 사용
                for t in tables:
                    t.pop("base_date", None)

                # v9 패치 #61: 비밀번호 해결 (마스크/암호문 → 평문)
                # 스케줄에 저장된 conn_info 의 password 가 마스크일 수 있음.
                # (저장 프로파일 기반 연결이면 프론트가 '●●●●●●●●' 전송 → 그대로 저장됨)
                # 해결 없이 run_cdc 호출하면 pymysql 의 latin-1 인코딩에서 터짐.
                try:
                    from app.core.password_resolver import resolve_password
                    for _side, _ci_key in [("source","src_conn"), ("target","tgt_conn")]:
                        _ci = cdc_cfg.get(_ci_key) or {}
                        if _ci.get("password"):
                            _ci["password"] = resolve_password(
                                _ci["password"],
                                profile_id=_ci.get("profile_id"),
                                side=_side,
                                host=_ci.get("host"),
                                username=_ci.get("username"),
                                database=_ci.get("database"),
                            )
                except Exception as _rpe:
                    logger.warning("[%s] CDC 비밀번호 해결 실패 (원본 사용): %s", sid, _rpe)

                run_cdc(cdc_id, cdc_cfg)   # run_cdc가 jobs.json에 직접 등록
            except Exception as e:
                logger.error("[%s] CDC 실행 오류: %s", sid, e)
            finally:
                # 스케줄 상태 갱신
                if sch.get("type") == "once":
                    sch["status"] = "done"
                else:
                    sch["status"] = "active"
                    try:
                        nxt = _get_scheduler().next_run(sid)
                        if nxt: sch["next_run"] = nxt
                    except Exception:
                        pass
                sch["last_run"] = datetime.now(_KST).isoformat()
                _schedules.set(sid, sch)

        threading.Thread(target=run_cdc_job, daemon=True).start()
        return cdc_id  # run_cdc가 만든 Job ID 반환

    # ── 일반 이관 스케줄 ────────────────────────────────────────
    j = _new_job(jid, cfg.get("name","스케줄 Job"),
                 cfg.get("src_db","mysql"), cfg.get("tgt_db","mssql"))
    for k in ("src_host","src_database","src_username","src_password",
              "tgt_host","tgt_database","tgt_username","tgt_password",
              "tables","batch_size","truncate_target","create_table","on_error"):
        j[k] = cfg.get(k, j.get(k))
    j["table_total"] = len(j.get("tables") or [])
    j["status"]      = "running"
    j["started_at"]  = datetime.now(_KST).isoformat()
    _jobs.set(jid, j)
    _job_logs[jid]   = []

    def run():
        # engine.runner를 통해 실행 — 비밀번호 복호화/로그 싱크/resume 플래그 정리 일원화
        _run_migration(jid)
        job_obj = _jobs.get(jid)
        if sch.get("type") == "once":
            sch["status"] = "done" if job_obj.get("status") == "completed" else "error"
        else:
            sch["status"] = "active" if job_obj.get("status") == "completed" else "error"
            try:
                nxt = _get_scheduler().next_run(sid)
                if nxt: sch["next_run"] = nxt
            except Exception:
                pass
        sch["last_run"] = datetime.now(_KST).isoformat()
        _schedules.set(sid, sch)
    threading.Thread(target=run, daemon=True).start()
    return jid


@router.post("/cdc-schedules", status_code=201)
def create_cdc_schedule(body: dict, bg: BackgroundTasks, _=Depends(require_operator)):
    """CDC 설정을 스케줄에 등록"""
    sid = str(uuid.uuid4())[:8]
    sch = {
        "id":           sid,
        "job_config": {
            "job_type":    "cdc",
            "cdc_cfg_id":  body.get("cdc_cfg_id", ""),
            "cdc_config":  body.get("cdc_config", {}),
            "name":        body.get("name", "CDC 스케줄"),
        },
        "type":         body.get("type", "interval"),
        "run_at":       body.get("run_at", ""),
        "cron_expr":    body.get("cron_expr", ""),
        "interval_min": body.get("interval_min", 60),
        "name":         body.get("name", "CDC 스케줄"),
        "status":       "active",
        "created_at":   datetime.now(_KST).isoformat(),
        "next_run":     body.get("run_at", ""),
        "run_count":    0,
        "job_type":     "cdc",           # 목록에서 CDC 구분용
    }
    _schedules.set(sid, sch)
    _get_scheduler().add(sid, sch)
    try:
        nxt = _get_scheduler().next_run(sid)
        if nxt:
            sch["next_run"] = nxt
            _schedules.set(sid, sch)
    except Exception:
        pass
    return sch


@router.patch("/schedules/{sid}/pause")
def pause_schedule(sid: str, _=Depends(require_operator)):
    if sid not in _schedules:
        raise HTTPException(404, "스케줄 없음")
    sch = _schedules.get(sid)
    sch["status"] = "paused"
    _schedules.set(sid, sch)
    _get_scheduler().pause(sid)
    return sch

@router.patch("/schedules/{sid}/resume")
def resume_schedule(sid: str, _=Depends(require_operator)):
    if sid not in _schedules:
        raise HTTPException(404, "스케줄 없음")
    sch = _schedules.get(sid)
    sch["status"] = "active"
    nxt = _get_scheduler().next_run(sid)
    if nxt: sch["next_run"] = nxt
    _schedules.set(sid, sch)
    _get_scheduler().resume(sid)
    return sch

@router.delete("/schedules/{sid}", status_code=204)
def delete_schedule(sid: str, _=Depends(require_operator)):
    if sid not in _schedules:
        raise HTTPException(404, "스케줄 없음")
    _get_scheduler().remove(sid)
    _schedules.delete(sid)


@router.post("/schedules/{sid}/run-now")
def run_schedule_now(sid: str, bg: BackgroundTasks, _=Depends(require_operator)):
    if sid not in _schedules:
        raise HTTPException(404, "스케줄 없음")
    jid = _run_scheduled(sid, bg)
    # 다음 실행 시각 갱신
    sch = _schedules.get(sid)
    nxt = _get_scheduler().next_run(sid)
    if nxt:
        sch["next_run"] = nxt
        _schedules.set(sid, sch)
    return {"ok": True, "job_id": jid}


# ── Job CRUD ─────────────────────────────────────────────

@router.get("/")
def list_jobs(_=Depends(require_viewer)):
    return [_mask_job_response(j) for j in _jobs.values()]


@router.get("/stats")
def get_stats(_=Depends(require_viewer)):
    jl = [j for j in _jobs.values() if j]
    # 오류 카운트: status=error 이거나 rows_error>0 인 completed Job
    errors = sum(1 for j in jl if
        j.get("status") == "error" or
        (j.get("status") == "completed" and (j.get("rows_error") or 0) > 0)
    )
    # 오류 Job ID 목록 (대시보드 → 이관모니터 자동 이동용)
    error_job_ids = [
        j.get("id","") for j in sorted(
            [j for j in jl if
                j.get("status") == "error" or
                (j.get("status") == "completed" and (j.get("rows_error") or 0) > 0)
            ],
            key=lambda j: j.get("created_at",""), reverse=True
        )
    ]
    return {
        "totalJobs":      len(jl),
        "running":        sum(1 for j in jl if j.get("status") == "running"),
        "errors":         errors,
        "error_job_ids":  error_job_ids,
        "completedToday": sum(1 for j in jl if j.get("status") == "completed"),
        "totalRows":      sum(j.get("rows_processed", 0) for j in jl),
        "validateRate":   99.1,
    }


@router.get("/{jid}")
def get_job(jid: str, _=Depends(require_viewer)):
    j = _jobs.get(jid)
    if j is None:
        raise HTTPException(404, "Not found")
    return _mask_job_response(j)


@router.post("/", status_code=201)
def create_job(body: dict, bg: BackgroundTasks, request: Request, user=Depends(require_operator)):
    # ── 라이선스 제한: 동시 실행 Job 수 ─────────────────
    from app.core.license import check_limit, get_license
    running_count = sum(1 for j in _jobs.values()
                        if isinstance(j, dict) and j.get("status") in ("running", "paused"))
    ok, limit = check_limit("max_concurrent_jobs", running_count)
    if not ok:
        lic = get_license()
        raise HTTPException(
            403,
            f"라이선스 제한 — 동시 실행 Job 수가 한도({limit})에 도달했습니다. "
            f"(현재 edition: {lic.edition}). "
            f"상위 edition 라이선스로 업그레이드하거나 진행 중인 Job을 완료하세요."
        )

    jid = str(uuid.uuid4())
    j = _new_job(jid,
                 body.get("name","New Job"),
                 body.get("src_db","mysql"),
                 body.get("tgt_db","mssql"),
                 **{k: body[k] for k in body if k not in ("name","src_db","tgt_db")})
    # v9 패치 #4: 비밀번호 필드를 실제 평문으로 해결
    # (프론트가 마스크/암호문/profile_id를 보내도 여기서 일괄 처리)
    from app.core.password_resolver import resolve_job_passwords as _resolve_pw
    body = _resolve_pw(body)

    j["src_host"]        = body.get("src_host","localhost")
    # ─── v95_p107 hotfix_018: 포트 하드코딩 제거 (위저드 값 그대로) ───
    j["src_port"]        = body.get("src_port")
    j["src_database"]    = body.get("src_database","")
    j["src_username"]    = body.get("src_username","root")
    j["src_password"]    = body.get("src_password","")
    j["tgt_host"]        = body.get("tgt_host","localhost")
    j["tgt_port"]        = body.get("tgt_port")  # hotfix_018: 위저드 값 그대로
    j["tgt_database"]    = body.get("tgt_database","target_db")
    j["tgt_username"]    = body.get("tgt_username","sa")
    j["tgt_password"]    = body.get("tgt_password","")
    j["tables"]          = body.get("tables",[])
    j["objects"]         = body.get("objects", {})        # ← 오브젝트 목록
    j["convert_objects"] = body.get("convert_objects", True)  # ← 변환 여부
    # v90.48: schema 정책 (테이블/객체 이관 시 동일하게 적용)
    #   - "underscore" (기본): customer.profile → customer_profile
    #   - "drop": 접두어 제거 (충돌 위험)
    #   - "database": 별도 DB
    j["schema_strategy"]  = body.get("schema_strategy", "underscore")
    j["table_total"]     = len(j["tables"])
    j["batch_size"]      = body.get("batch_size",5000)
    j["truncate_target"] = body.get("truncate_target",False)
    j["create_table"]    = body.get("create_table",True)
    j["on_error"]        = body.get("on_error","skip")
    j["obj_mode"]        = body.get("obj_mode","drop_recreate")   # drop_recreate | skip_existing
    j["view_mode"]       = body.get("view_mode","drop_recreate")
    j["table_mode"]      = body.get("table_mode","schema_data")
    j["ddl_engine"]      = body.get("ddl_engine","auto")
    j["obj_engine"]      = body.get("obj_engine","auto")
    j["drop_table"]      = body.get("drop_table", False)
    j["parallel_workers"]= body.get("parallel_workers", 4)
    # v90.32: 트리거 hang 방지 옵션
    j["skip_triggers"]      = bool(body.get("skip_triggers", False))
    j["trigger_timeout"]    = int(body.get("trigger_timeout", 120))
    # v9 패치 #20: bulk loader 설정
    j["bulk_mode"]           = body.get("bulk_mode", "auto")
    j["bulk_threshold_rows"] = int(body.get("bulk_threshold_rows", 100000))
    # v9 패치 #23: 테이블 병렬 + MSSQL 튜닝
    j["parallel_tables"]        = int(body.get("parallel_tables", 3))
    j["mssql_tuning"]           = bool(body.get("mssql_tuning", False))
    j["mssql_disable_indexes"]  = bool(body.get("mssql_disable_indexes", False))

    # 수신 데이터 로그
    import logging as _lg
    _lg.getLogger("databridge.jobs").info(
        "Job 생성: src_db=%s tgt_db=%s 테이블 %d개 오브젝트 %s",
        j.get("src_db"), j.get("tgt_db"),
        len(j["tables"]),
        {k: len(v) for k,v in j["objects"].items() if v}
    )

    # ── schedule_cron 있으면 스케줄로 등록, 없으면 즉시 실행 ──────
    cron_str = (body.get("schedule_cron") or "").strip()
    if cron_str:
        sid = str(uuid.uuid4())[:8]
        # cron 타입 파싱
        if cron_str.startswith("ONCE:"):
            stype  = "once"
            run_at = cron_str[5:]  # 사용자 입력 KST 값 그대로 저장 (Z 없음)
            cron_expr = ""
        else:
            stype     = "cron"
            run_at    = ""
            cron_expr = cron_str

        sch = {
            "id":           sid,
            "name":         j.get("name", "스케줄 Job"),
            "type":         stype,
            "run_at":       run_at,
            "cron_expr":    cron_expr,
            "interval_min": body.get("interval_min", 60),
            "status":       "active",
            "created_at":   datetime.now(_KST).isoformat() + "Z",
            "next_run":     run_at or "",
            "run_count":    0,
            "job_config":   {k: body[k] for k in body if k != "schedule_cron"},
        }
        _schedules.set(sid, sch)

        # 스케줄러 엔진에 등록
        try:
            _get_scheduler().add(sid, sch)
            # once 타입은 run_at 그대로 유지 (이미 KST 값)
            if stype != "once":
                nxt = _get_scheduler().next_run(sid)
                if nxt:
                    sch["next_run"] = nxt
                    _schedules.set(sid, sch)
        except Exception as _se:
            logger.warning("스케줄 등록 실패: %s", _se)

        logger.info("스케줄 등록: [%s] type=%s expr=%s", sid, stype, cron_str)
        # 스케줄 등록 시 Job 저장/실행 안 함 — 실행 시점에 Job 생성
        return {"id": sid, "type": "schedule", "name": sch["name"], "status": "scheduled", "next_run": sch.get("next_run","")}
    else:
        # 저장 직전 비밀번호 암호화
        j = _encrypt_job_passwords(j)
        _jobs.set(jid, j)
        _job_logs[jid] = []
        bg.add_task(_run_migration, jid)
        _audit.record(
            action=_AuditActions.JOB_CREATE, status="ok",
            user=user, resource="job", resource_id=jid,
            ip=(request.client.host if request.client else None),
            details={"name": j.get("name"), "src_db": j.get("src_db"), "tgt_db": j.get("tgt_db"),
                     "tables": len(j.get("tables") or [])},
        )
        return _mask_job_response(j)


# Note: 이전에 이 위치에 있던 _run_migration 함수는 app/engine/runner.py 로 이관되었습니다.
# 새 헤더의 _run_migration (라인 49 근처) 가 runner.run_migration 을 호출합니다.


@router.post("/{jid}/pause")
def pause_job(jid: str, _=Depends(require_operator)):
    j = _jobs.get(jid)
    if j is None: raise HTTPException(404, "Not found")
    j["status"] = "paused"
    _jobs.set(jid, j)
    # v48: 진단용 로그 — 엔진 레지스트리 등록 여부와 pause 호출 기록
    _has_engine = jid in _migrators
    logger.info("[PAUSE] jid=%s engine_registered=%s", jid[:8], _has_engine)
    if _has_engine:
        _migrators[jid].pause()
        # 프론트 로그 뷰어에도 서버 측 확인 메시지 추가
        _job_logs.setdefault(jid, []).append({
            "time": datetime.now(_KST).isoformat(),
            "level": "info", "tag": "server",
            "message": f"🖥 서버 수신: pause 요청 — 엔진 일시정지 플래그 세팅됨"
        })
    else:
        _job_logs.setdefault(jid, []).append({
            "time": datetime.now(_KST).isoformat(),
            "level": "warn", "tag": "server",
            "message": f"⚠ 서버 수신: pause 요청 — 엔진 미등록 (이미 완료되었거나 재이관 경로)"
        })
    return {"ok": True}


@router.post("/{jid}/resume")
def resume_job(jid: str, _=Depends(require_operator)):
    j = _jobs.get(jid)
    if j is None: raise HTTPException(404, "Not found")
    j["status"] = "running"
    _jobs.set(jid, j)
    # v48: 진단용 로그
    _has_engine = jid in _migrators
    logger.info("[RESUME] jid=%s engine_registered=%s", jid[:8], _has_engine)
    if _has_engine:
        _migrators[jid].resume()
        _job_logs.setdefault(jid, []).append({
            "time": datetime.now(_KST).isoformat(),
            "level": "info", "tag": "server",
            "message": f"🖥 서버 수신: resume 요청 — 엔진 재개 플래그 해제됨"
        })
    else:
        _job_logs.setdefault(jid, []).append({
            "time": datetime.now(_KST).isoformat(),
            "level": "warn", "tag": "server",
            "message": f"⚠ 서버 수신: resume 요청 — 엔진 미등록"
        })
    return {"ok": True}


@router.post("/{jid}/stop")
def stop_job(jid: str, request: Request, user=Depends(require_operator)):
    j = _jobs.get(jid)
    if j is None: raise HTTPException(404, "Not found")
    j["status"] = "aborted"
    _jobs.set(jid, j)
    # v48: 진단용 로그
    _has_engine = jid in _migrators
    logger.info("[STOP] jid=%s engine_registered=%s", jid[:8], _has_engine)
    if _has_engine:
        _migrators[jid].stop()
        _job_logs.setdefault(jid, []).append({
            "time": datetime.now(_KST).isoformat(),
            "level": "info", "tag": "server",
            "message": f"🖥 서버 수신: stop 요청 — 엔진 중단 플래그 세팅됨"
        })
    _audit.record(
        action=_AuditActions.JOB_STOP, status="ok",
        user=user, resource="job", resource_id=jid,
        ip=(request.client.host if request.client else None),
    )
    return {"ok": True}


@router.delete("/{jid}", status_code=204)
def delete_job(jid: str, request: Request, user=Depends(require_operator)):
    if jid not in _jobs: raise HTTPException(404, "Not found")
    if jid in _migrators: _migrators[jid].stop()
    _jobs.delete(jid)
    _job_logs.pop(jid, None)
    _audit.record(
        action=_AuditActions.JOB_DELETE, status="ok",
        user=user, resource="job", resource_id=jid,
        ip=(request.client.host if request.client else None),
    )


@router.post("/bulk-delete")
def bulk_delete_jobs(body: dict, request: Request, user=Depends(require_admin)):
    """여러 Job 일괄 삭제"""
    ids = body.get("ids", [])
    deleted = []; skipped = []
    for jid in ids:
        j = _jobs.get(jid)
        if j is None:
            skipped.append(jid); continue
        if j.get("status") in ("running", "paused"):
            skipped.append(jid); continue
        if jid in _migrators:
            try: _migrators[jid].stop()
            except: pass
        _jobs.delete(jid)
        _job_logs.pop(jid, None)
        deleted.append(jid)
    _audit.record(
        action=_AuditActions.JOB_BULK_DELETE, status="ok",
        user=user, resource="job", resource_id=None,
        ip=(request.client.host if request.client else None),
        details={"requested": len(ids), "deleted": len(deleted), "skipped": len(skipped)},
    )
    return {"deleted": len(deleted), "skipped": len(skipped),
            "deleted_ids": deleted, "skipped_ids": skipped}


@router.post("/{jid}/remig-object")
def remig_object(jid: str, body: dict, _=Depends(require_operator)):
    """오브젝트(트리거/함수/프로시저/뷰) 재이관"""
    j = _jobs.get(jid)
    if not j: raise HTTPException(404, "Job 없음")
    name      = body.get("name") or body.get("object_name")
    obj_type  = (body.get("type") or body.get("object_type") or "trigger").upper()
    mode      = body.get("mode", "drop_recreate")
    error_hint = body.get("error_hint", "")
    # v10 #17: error_history 수용 (프론트 일괄 재처리가 전달)
    error_history = body.get("error_history", [])
    # v95_p107 hotfix_048: provider override (UI 에서 선택 — Phase 3 라우팅 적용까지 로그 신호만)
    ai_provider_override = body.get("ai_provider") or ""
    ai_model_override    = body.get("ai_model") or ""
    if ai_provider_override:
        import logging as _h048lg
        _h048lg.getLogger("databridge.jobs").info(
            "[h048] remig-object provider override: %s / %s (대상: %s)",
            ai_provider_override, ai_model_override, name
        )
    if not name: raise HTTPException(400, "name 필수")

    # v10 #17: KB 패턴 매칭 — AI 스킵 대상인지 먼저 확인
    matched_kb = None
    try:
        from app.engine.error_kb import match_error, assemble_prompt_hint, record_attempt
        matched_kb = match_error(error_hint or "")
    except Exception:
        pass

    # KB 가 ai_skip=True 이면 AI 호출 우회 안내 (설정/엔진 규칙 권고)
    # 실제 처리는 그대로 진행하지만 응답에 KB 정보 포함

    import threading
    def _run():
        # 이 경로는 "특정 오브젝트만" 재이관하는 특수 기능이라
        # run_migration 러너 전체 경로를 타지 않고 엔진 메서드를 직접 호출한다.
        # 따라서 암호화된 비밀번호를 수동으로 복호화한 사본을 엔진에 전달.
        engine_job = _decrypt_job_for_engine(j)
        engine = MigrationEngine(engine_job)
        _attach_log_sink(engine, jid)   # v9 #47: 실시간 로그 뷰어 연결
        try:
            src_conn = engine._connect_src()
            tgt_conn = engine._connect_tgt()
            if not src_conn or not tgt_conn:
                j["item_statuses"][name] = {"type":obj_type.lower(),"status":"error","rows":0,
                    "error":"DB 연결 실패","started_at":None,"finished_at":datetime.now(_KST).isoformat()}
                return

            j["item_statuses"][name] = {"type":obj_type.lower(),"status":"running","rows":0,
                "error":None,"started_at":datetime.now(_KST).isoformat(),"finished_at":None}
            _jobs.set(jid, j)

            if mode == "ai":
                # AI 변환
                try:
                    from app.api.routes.schema import _ai_convert_ddl
                    cur_src = src_conn.cursor()
                    cur_src.execute("SELECT OBJECT_DEFINITION(OBJECT_ID(?))", [name])
                    row = cur_src.fetchone()
                    src_ddl = (row[0] if row else "") or ""
                    if src_ddl:
                        # v10 #17: KB 지침 + error_history 를 모두 프롬프트에 포함
                        try:
                            full_ctx = assemble_prompt_hint(
                                current_error=error_hint,
                                error_history=error_history or [],
                            )
                            if not full_ctx and error_hint:
                                full_ctx = f"오류: {error_hint}"
                        except Exception:
                            full_ctx = f"오류: {error_hint}" if error_hint else ""

                        # ════════════════════════════════════════════════════════════
                        # v95_p90_schemactx_004 (2026-05-08 본부장님 본질 처방):
                        # 재이관 경로에서 _conns["target"] 자동 채우기
                        # ════════════════════════════════════════════════════════════
                        # 본부장님 검증 결과 (2026-05-08 09:10~09:16):
                        #   "[v95_p90_schemactx_003] tgt_conn host 비어있음 — 스킵"
                        #   20번 반복 → 동적 스키마 발견 미작동 → 컨텍스트 주입 0건
                        #
                        # 본질:
                        #   _conns["target"] 은 Job 위저드 화면에서만 채워짐
                        #   재이관 (remig_object) 은 화면 안 거침 → _conns 비어있음
                        #
                        # 처방:
                        #   재이관 시 engine_job 의 연결 정보로 _conns["target"] 자동 채우기
                        #   → _ai_convert_ddl 안의 _discover_target_schemas 작동 가능
                        #   → 17건 빨간불 본질 (Gemma 환각) 잡힐 가능성
                        # ════════════════════════════════════════════════════════════
                        try:
                            from app.api.routes.schema import _conns as _schema_conns
                            _schema_conns["target"] = {
                                "db_type":  engine_job.get("tgt_db", "mysql"),
                                "host":     engine_job.get("tgt_host", ""),
                                "port":     engine_job.get("tgt_port"),  # hotfix_018: 위저드 값 그대로
                                "username": engine_job.get("tgt_username", ""),
                                "password": engine_job.get("tgt_password", ""),
                                "database": engine_job.get("tgt_database", ""),
                            }
                            engine._log(
                                "info",
                                f"[v95_p90_schemactx_004] 재이관용 _conns[target] 채움: "
                                f"host={engine_job.get('tgt_host')} db={engine_job.get('tgt_database')}"
                            )
                        except Exception as _ce:
                            engine._log("warn",
                                f"[v95_p90_schemactx_004] _conns 채우기 실패 (무시): {_ce}")

                        result = _ai_convert_ddl(src_ddl, obj_type, name,
                            j.get("src_db","mssql"), j.get("tgt_db","mysql"), full_ctx)
                        stmts = result.get("statements", [])
                        if stmts:
                            cur_tgt = tgt_conn.cursor()
                            for stmt in stmts:
                                if stmt.strip():
                                    # v95_p107 hotfix_066: 안전망 통합 적용 (진짜 본질)
                                    # 이 경로는 obj_executor._exec_one 우회 → h054~h061 안전망 적용 안 됨
                                    # 본부장님 오늘 하루 절망의 진짜 본질
                                    try:
                                        import re as _h066re
                                        # 1) post_process_sql (POSTPROCESS_RULES 통합 — R-001~R-041)
                                        try:
                                            from app.core.sql_post_processor import post_process_sql as _h066_pps
                                            stmt, _h066_fixes = _h066_pps(stmt, name, verbose=False)
                                            if _h066_fixes:
                                                engine._log("info", f"[h066] [{name}] post_process 적용: {', '.join(_h066_fixes)}")
                                        except Exception as _h066pe:
                                            engine._log("warn", f"[h066] post_process 실패 (무시): {_h066pe}")
                                        # 2) R-033 proc signature (함수형 룰)
                                        try:
                                            from app.core.sql_post_processor import _r033_fix_proc_signature as _h066_r033
                                            if "CREATE PROCEDURE" in stmt.upper() or "CREATE FUNCTION" in stmt.upper():
                                                stmt, _h066_r033c = _h066_r033(stmt)
                                                if _h066_r033c > 0:
                                                    engine._log("info", f"[h066] [{name}] R-033 정정 x{_h066_r033c}")
                                        except Exception: pass
                                        # 3) 핵심 안전망 (bracket + AS BEGIN + OPTION + CONVERT + N'literal')
                                        _h066_olen = len(stmt)
                                        # R-034: [ident] → `ident`
                                        stmt = _h066re.sub(r'\[([A-Za-z_][\w]*)\]', r'`\1`', stmt)
                                        # R-037: OPTION (MAXRECURSION N)
                                        stmt = _h066re.sub(r'\s*OPTION\s*\(\s*MAXRECURSION\s+\d+\s*\)\s*', ' ', stmt, flags=_h066re.IGNORECASE)
                                        # R-039: FUNC AS BEGIN
                                        stmt = _h066re.sub(
                                            r'(CREATE\s+FUNCTION\s+`?\w+`?\s*\([^)]*\)\s*RETURNS\s+\w+(?:\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\))?)\s+AS\s*(\n?\s*)BEGIN\b',
                                            r'\1\2BEGIN', stmt, flags=_h066re.IGNORECASE)
                                        # R-040: CONVERT style
                                        stmt = _h066re.sub(r"('\d{8}')\s*,\s*\d{2,3}\s*\)", r"CAST(\1 AS DATETIME))", stmt)
                                        # R-041: N'literal'
                                        stmt = _h066re.sub(r"\bN'((?:[^'\\]|\\.|'')*)'", r"'\1'", stmt)
                                        # DELIMITER 잔재 제거
                                        stmt = _h066re.sub(r"(?im)^\s*DELIMITER\s+\S+\s*$", "", stmt)
                                        if len(stmt) != _h066_olen:
                                            engine._log("info", f"[h066-safetynet] [{name}] 정규식 정정 (len {_h066_olen}→{len(stmt)})")
                                    except Exception as _h066e:
                                        engine._log("warn", f"[h066] 안전망 예외 (원본 사용): {_h066e}")
                                    cur_tgt.execute(stmt)
                                    tgt_conn.commit()
                            j["item_statuses"][name].update({"status":"done","finished_at":datetime.now(_KST).isoformat()})
                            # rows_error 차감 (0 미만 방지)
                            if j.get("rows_error", 0) > 0:
                                j["rows_error"] -= 1
                            engine._log("info", f"✓ [{name}] AI 재이관 완료")
                            # v10 #17: KB 통계 기록 (성공)
                            try:
                                record_attempt(
                                    pattern_id=(matched_kb or {}).get("id"),
                                    error_code=(matched_kb or {}).get("error_code", ""),
                                    category=(matched_kb or {}).get("category", ""),
                                    job_id=jid, item_name=name,
                                    attempt_num=len(error_history or []) + 1,
                                    success=True, ai_used=True,
                                    prompt_chars=len(full_ctx) if full_ctx else 0,
                                )
                            except Exception: pass
                            return
                except Exception as ae:
                    engine._log("warn", f"[{name}] AI 변환 실패: {ae} — 일반 재이관으로 폴백")
                    # v10 #17: KB 통계 기록 (AI 실패)
                    try:
                        record_attempt(
                            pattern_id=(matched_kb or {}).get("id"),
                            error_code=(matched_kb or {}).get("error_code", ""),
                            category=(matched_kb or {}).get("category", ""),
                            job_id=jid, item_name=name,
                            attempt_num=len(error_history or []) + 1,
                            success=False, ai_used=True,
                        )
                    except Exception: pass

            # 일반 재이관 — _migrate_objects 활용
            objects = {obj_type.lower() + "s": [name]}
            if obj_type == "FUNCTION": objects = {"functions": [name]}
            elif obj_type == "PROCEDURE": objects = {"procedures": [name]}
            elif obj_type == "TRIGGER": objects = {"triggers": [name]}
            elif obj_type == "VIEW": objects = {"views": [name]}

            # ════════════════════════════════════════════════════════════
            # v95_p90_schemactx_005 (2026-05-08 본부장님 진짜 본질):
            # drop_recreate 경로에도 _conns["target"] 채우기
            # ════════════════════════════════════════════════════════════
            # 본부장님 검증 (2026-05-08 09:32~09:35):
            #   - 빨간불 17 → 15 (2건 감소: ufnGetAccountingEndDate, uspSearchCandidateResumes)
            #   - 그러나 schema_ctx 로그 0건 → mode != 'ai' 확인
            #
            # 본부장님 화면 분석 (JobMonitor.vue:2449):
            #   mode: bulkMode === 'rules' ? 'drop_recreate' : 'ai'
            #   → 단일 '재이관' 버튼은 'drop_recreate' 가 기본
            #   → 우리 처방 (mode == 'ai' 안) 우회됨
            #
            # 처방:
            #   _migrate_objects 호출 전에도 _conns 채우기
            #   → _migrate_objects 내부의 _ai_convert_ddl 호출 시
            #      _discover_target_schemas 작동 가능
            # ════════════════════════════════════════════════════════════
            try:
                from app.api.routes.schema import _conns as _schema_conns
                _schema_conns["target"] = {
                    "db_type":  engine_job.get("tgt_db", "mysql"),
                    "host":     engine_job.get("tgt_host", ""),
                    "port":     engine_job.get("tgt_port"),  # hotfix_018: 위저드 값 그대로
                    "username": engine_job.get("tgt_username", ""),
                    "password": engine_job.get("tgt_password", ""),
                    "database": engine_job.get("tgt_database", ""),
                }
                engine._log(
                    "info",
                    f"[v95_p90_schemactx_005] drop_recreate 경로 _conns[target] 채움: "
                    f"host={engine_job.get('tgt_host')} db={engine_job.get('tgt_database')}"
                )
            except Exception as _ce:
                engine._log("warn",
                    f"[v95_p90_schemactx_005] _conns 채우기 실패 (무시): {_ce}")

            engine._migrate_objects(src_conn, tgt_conn, objects, True)
            # v95_p107 hotfix_043 (본부장님 모토 #14 정면 — 진가 검증):
            # _migrate_objects 가 status 를 명시적 설정 못하는 경로 본질 처방.
            # MySQL 에 진짜 객체 존재 확인 후 status 결정.
            st = j["item_statuses"].get(name, {})
            _h043_status = st.get("status")
            # 진짜 본질: MySQL 객체 실제 존재 여부 검증
            _h043_obj_exists = False
            try:
                _h043_check_cur = tgt_conn.cursor()
                _h043_tgt_db = engine_job.get("tgt_database", "")
                if obj_type == "PROCEDURE":
                    _h043_check_cur.execute(
                        "SELECT COUNT(*) FROM information_schema.ROUTINES "
                        "WHERE ROUTINE_SCHEMA=%s AND ROUTINE_TYPE=\'PROCEDURE\' "
                        "AND (ROUTINE_NAME=%s OR ROUTINE_NAME LIKE %s OR ROUTINE_NAME LIKE %s)",
                        [_h043_tgt_db, name, f"%_{name}", f"{name}_%"]
                    )
                elif obj_type == "FUNCTION":
                    _h043_check_cur.execute(
                        "SELECT COUNT(*) FROM information_schema.ROUTINES "
                        "WHERE ROUTINE_SCHEMA=%s AND ROUTINE_TYPE=\'FUNCTION\' "
                        "AND (ROUTINE_NAME=%s OR ROUTINE_NAME LIKE %s OR ROUTINE_NAME LIKE %s)",
                        [_h043_tgt_db, name, f"%_{name}", f"{name}_%"]
                    )
                elif obj_type == "TRIGGER":
                    _h043_check_cur.execute(
                        "SELECT COUNT(*) FROM information_schema.TRIGGERS "
                        "WHERE TRIGGER_SCHEMA=%s "
                        "AND (TRIGGER_NAME=%s OR TRIGGER_NAME LIKE %s OR TRIGGER_NAME LIKE %s)",
                        [_h043_tgt_db, name, f"%_{name}", f"{name}_%"]
                    )
                elif obj_type == "VIEW":
                    _h043_check_cur.execute(
                        "SELECT COUNT(*) FROM information_schema.VIEWS "
                        "WHERE TABLE_SCHEMA=%s "
                        "AND (TABLE_NAME=%s OR TABLE_NAME LIKE %s OR TABLE_NAME LIKE %s)",
                        [_h043_tgt_db, name, f"%_{name}", f"{name}_%"]
                    )
                _h043_row = _h043_check_cur.fetchone()
                _h043_obj_exists = bool(_h043_row and (_h043_row[0] if not isinstance(_h043_row, dict) else list(_h043_row.values())[0]))
                _h043_check_cur.close()
            except Exception as _h043_e:
                engine._log("warn", f"[{name}] [h043] MySQL 객체 검증 예외: {_h043_e}")
            
            if _h043_obj_exists:
                # 진짜 MySQL 객체 존재 → 성공
                j["item_statuses"][name].update({"status":"done","finished_at":datetime.now(_KST).isoformat()})
                if j.get("rows_error", 0) > 0:
                    j["rows_error"] -= 1
                engine._log("info", f"✓ [{name}] 재이관 완료")
            else:
                # v95_p107 hotfix_064: 실패 시 반드시 timestamp 갱신 (본부장님 모토 #14 정직)
                # 본질: 옛날 흐름이 status=error 면 error 안 덮어쓰던 결함 → 본부장님 화면 캐시
                _h064_now = datetime.now(_KST).strftime("%H:%M:%S")
                _h064_existing = (st.get("error") or "").strip()
                if _h064_existing and not _h064_existing.startswith("["):
                    _h064_msg = f"[{_h064_now} 재시도] {_h064_existing}"
                elif _h064_existing:
                    # 이미 [시각] prefix 있으면 새 시각으로 교체
                    import re as _h064re
                    _h064_msg = _h064re.sub(r"^\[[^\]]+\]\s*", f"[{_h064_now} 재시도] ", _h064_existing, count=1)
                else:
                    _h064_msg = f"[{_h064_now}] MySQL 객체 생성 실패 (h043 검증 — 엔진 변환 후 객체 없음)"
                j["item_statuses"][name].update({
                    "status": "error",
                    "error": _h064_msg[:400],
                    "finished_at": datetime.now(_KST).isoformat(),
                })
                engine._log("warn", f"✗ [{name}] [h064] 재이관 실패 — error 갱신: {_h064_msg[:80]}")
        except Exception as e:
            j["item_statuses"][name] = {"type":obj_type.lower(),"status":"error","rows":0,
                "error":str(e)[:300],"started_at":None,"finished_at":datetime.now(_KST).isoformat()}
            engine._log("error", f"✗ [{name}] 재이관 실패: {e}")
        finally:
            _jobs.set(jid, j)
            try: src_conn.close()
            except: pass
            try: tgt_conn.close()
            except: pass

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "name": name, "type": obj_type, "mode": mode}


@router.post("/{jid}/remig-table")
def remig_table(jid: str, body: dict, _=Depends(require_operator)):
    """특정 테이블의 스키마를 재이관"""
    j = _jobs.get(jid)
    if not j: raise HTTPException(404, "Job 없음")
    table      = body.get("table")
    mode       = body.get("mode", "skip_geo")   # drop_recreate | skip_geo | ai
    error_hint    = body.get("error_hint", "")
    error_history = body.get("error_history", [])  # [{attempt, error, ts}, ...]
    # 원본 Job 설정 오버라이드 (프론트에서 전달 시 적용)
    override_table_mode      = body.get("table_mode")       # schema_data | data_only | schema_only
    override_drop_table      = body.get("drop_table")
    override_truncate_target = body.get("truncate_target")
    override_create_table    = body.get("create_table")
    # v95_p107 hotfix_048: provider override (UI 에서 선택 — Phase 3 라우팅 적용까지 로그 신호만)
    ai_provider_override = body.get("ai_provider") or ""
    ai_model_override    = body.get("ai_model") or ""
    if ai_provider_override:
        import logging as _h048lg
        _h048lg.getLogger("databridge.jobs").info(
            "[h048] remig-table provider override: %s / %s (테이블: %s)",
            ai_provider_override, ai_model_override, table
        )
    if not table: raise HTTPException(400, "table 필수")

    # 누적 오류 히스토리 → AI 프롬프트용 텍스트 생성
    def _build_error_context(hint: str, history: list) -> str:
        parts = []
        if history:
            parts.append("=== 재이관 시도 오류 히스토리 ===")
            for h in history:
                parts.append(f"시도 #{h.get('attempt','')} ({h.get('ts','')}): {h.get('error','')}")
            parts.append("================================")
        if hint and (not history or hint not in str(history)):
            parts.append(f"현재 오류: {hint}")

        # v10 #17: KB 패턴 매칭 → 프롬프트에 교정 지침 주입
        try:
            from app.engine.error_kb import assemble_prompt_hint
            kb_hint = assemble_prompt_hint(current_error=hint, error_history=history or [])
            if kb_hint:
                parts.append("")
                parts.append(kb_hint)
        except Exception as _kb_err:
            # KB 실패는 로그만 남기고 기존 동작 유지
            logger.warning("[KB] assemble_prompt_hint 실패 (무시): %s", _kb_err)

        return "\n".join(parts) if parts else hint

    import threading

    def _drop_table(tgt_conn, tgt_db, table_name):
        try:
            cur = tgt_conn.cursor()
            if tgt_db in ("mssql","azure","sqlserver"):
                cur.execute(f"IF OBJECT_ID(N'[dbo].[{table_name}]', N'U') IS NOT NULL DROP TABLE [dbo].[{table_name}]")
            else:
                cur.execute(f"DROP TABLE IF EXISTS `{table_name}`")
            tgt_conn.commit()
        except Exception as de:
            logger.warning("[%s] DROP 실패 (무시): %s", table_name, de)

    def _run():
        # 특정 테이블 재이관 — 엔진의 내부 메서드를 직접 호출하는 경로.
        # run_migration 러너를 타지 않으므로 비밀번호는 수동 복호화한 사본을 넘긴다.
        engine_job = _decrypt_job_for_engine(j)
        engine = MigrationEngine(engine_job)
        _attach_log_sink(engine, jid)   # v9 #47: 실시간 로그 뷰어 연결
        # v46: 재이관 엔진을 _migrators 에 등록 → /pause /resume /stop 엔드포인트가
        # engine._pause / engine._stop 플래그를 제대로 세팅할 수 있게 된다.
        # 기존에는 등록이 누락되어 있어 pause 호출이 사실상 no-op 이었고,
        # 엔진 내부의 `while self._pause: time.sleep(0.3)` 루프가 작동하지 않았다.
        _migrators[jid] = engine

        # v46: status 보존 헬퍼 — Store 의 status 가 'paused'/'aborted' 면 그 값 유지.
        # background thread 의 주기적 _jobs.set 이 사용자의 pause/stop 요청을
        # 1초 내에 덮어써 UI 가 paused 분기로 전환되지 않던 버그의 근본 수정.
        def _persist_job():
            try:
                current = _jobs.get(jid)
                if current and current.get("status") in ("paused", "aborted"):
                    j["status"] = current["status"]
            except Exception:
                pass
            _jobs.set(j["id"], j)

        # error_hint/history를 엔진에 주입 → 미지원 컬럼 자동 스킵
        full_hint = _build_error_context(error_hint, error_history)
        engine._remig_error_hint = full_hint
        try:
            src_conn = engine._connect_src()
            tgt_conn = engine._connect_tgt()
            if not src_conn or not tgt_conn:
                j["item_statuses"][table] = {"type":"table","status":"error","rows":0,
                    "error":"DB 연결 실패","started_at":None,"finished_at":datetime.now(_KST).isoformat()}
                return

            tgt_db = j.get("tgt_db","mysql")
            engine._log("info", f"[{table}] 재이관 시작 — mode={mode}")
            if full_hint:
                engine._log("info", f"[{table}] 오류 컨텍스트 적용:\n{full_hint[:200]}")

            # ── AI 이관 ──────────────────────────────────────────
            if mode == "ai":
                engine._log("info", f"[{table}] AI 스키마 분석 중...")
                _drop_table(tgt_conn, tgt_db, table)
                # schema.py의 AI 변환 활용
                try:
                    from app.api.routes.schema import _ai_convert_ddl
                    src_cur = src_conn.cursor()
                    # 소스 DDL 가져오기
                    src_db_type = j.get("src_db","mssql")
                    if src_db_type in ("mssql","azure","sqlserver"):
                        src_cur.execute("SELECT OBJECT_DEFINITION(OBJECT_ID(?))", [table])
                        row = src_cur.fetchone()
                        src_ddl = (row[0] if row else "") or ""
                        if not src_ddl:
                            # sys.columns로 CREATE TABLE 재구성
                            src_cur.execute("""
                                SELECT c.name, t.name as type_name, c.max_length, c.precision,
                                       c.scale, c.is_nullable, c.is_identity
                                FROM sys.columns c
                                JOIN sys.types t ON c.user_type_id=t.user_type_id
                                WHERE c.object_id=OBJECT_ID(?)
                                ORDER BY c.column_id
                            """, [table])
                            cols = src_cur.fetchall()
                            src_ddl = f"-- {table} 컬럼 정보\n"
                            for col in cols:
                                nm = col[0] if not isinstance(col,dict) else col['name']
                                tp = col[1] if not isinstance(col,dict) else col['type_name']
                                src_ddl += f"  [{nm}] [{tp}]\n"
                    else:
                        src_cur.execute(f"SHOW CREATE TABLE `{table}`")
                        row = src_cur.fetchone()
                        src_ddl = (row[1] if row else "") or ""

                    engine._log("info", f"[{table}] AI 변환 요청 중...")
                    # AI DDL 변환 (schema.py 활용)
                    # 누적 오류 히스토리 포함한 컨텍스트 생성
                    full_error_ctx = _build_error_context(error_hint, error_history)
                    engine._log("info", f"[{table}] AI 오류 컨텍스트:\n{full_error_ctx[:300]}")
                    result = _ai_convert_ddl(
                        src_ddl, "TABLE", table,
                        j.get("src_db","mssql"), j.get("tgt_db","mysql"),
                        full_error_ctx
                    )
                    stmts = result.get("statements", [])
                    if stmts:
                        cur_tgt = tgt_conn.cursor()
                        for stmt in stmts:
                            if stmt.strip():
                                cur_tgt.execute(stmt)
                                tgt_conn.commit()
                        engine._log("info", f"[{table}] AI 스키마 생성 완료")
                    else:
                        engine._log("warn", f"[{table}] AI 변환 결과 없음 — 자체 이관으로 폴백")
                except Exception as ae:
                    engine._log("warn", f"[{table}] AI 변환 실패: {ae} — 자체 이관으로 폴백")

            # ── 원본 설정 그대로 ─────────────────────────────────
            elif mode == "original":
                # Job 원본 설정 적용
                orig_table_mode = j.get("table_mode", "schema_data")
                orig_drop       = j.get("drop_table", False)
                orig_truncate   = j.get("truncate_target", False)
                engine._log("info", f"[{table}] 원본 설정 적용 — table_mode={orig_table_mode} drop={orig_drop} truncate={orig_truncate}")
                if orig_drop:
                    _drop_table(tgt_conn, tgt_db, table)
                    engine._log("info", f"[{table}] DROP 완료")

            # ── DROP 후 재생성 ────────────────────────────────────
            elif mode == "drop_recreate":
                _drop_table(tgt_conn, tgt_db, table)
                engine._log("info", f"[{table}] DROP 완료 — 재이관 시작")

            # ── skip_geo (기본): geography 등 미지원 타입 스킵 ──
            else:
                engine._log("info", f"[{table}] 미지원 컬럼 스킵 모드로 재이관")

            # ── 원본 설정 오버라이드 적용 ─────────────────────────
            if override_table_mode is not None:
                j["table_mode"] = override_table_mode
            if override_drop_table is not None:
                j["drop_table"] = override_drop_table
            if override_truncate_target is not None:
                j["truncate_target"] = override_truncate_target
            if override_create_table is not None:
                j["create_table"] = override_create_table

            # ── 실제 데이터 이관 ──────────────────────────────────
            j["item_statuses"][table] = {"type":"table","status":"running","rows":0,
                "error":None,"started_at":datetime.now(_KST).isoformat(),"finished_at":None}
            j["current_table"] = table
            _persist_job()  # v46: status 보존 + 즉시 저장 → UI 반영

            try:
                # v46: _migrate_table 진입 전 pause/stop 체크.
                # 엔진 내부 청크 루프에도 `while self._pause` 가 있지만,
                # 실행 직전에도 가드를 두어 정책상 명시적으로 대기시킨다.
                import time as _t_pause
                while engine._pause and not engine._stop:
                    _t_pause.sleep(0.3)
                if engine._stop:
                    engine._log("info", f"[{table}] 중단 요청으로 재이관 미시작")
                    j["item_statuses"][table].update({
                        "status":"aborted","error":"사용자 중단",
                        "finished_at":datetime.now(_KST).isoformat()
                    })
                    return

                done = engine._migrate_table(src_conn, tgt_conn, table)
                # 이전 오류 건수 차감
                prev_st = j["item_statuses"].get(table, {})
                prev_err_rows = prev_st.get("batch_error_rows", 0)
                if prev_err_rows > 0:
                    j["rows_error"] = max(0, j.get("rows_error", 0) - prev_err_rows)
                j["item_statuses"][table].update({
                    "status":"done","rows":done,
                    "rows_src": done, "rows_tgt": done,
                    "batch_errors": [], "batch_error_rows": 0,
                    "finished_at":datetime.now(_KST).isoformat(),"error":None
                })
                engine._log("info", f"✓ [{table}] 재이관 완료 — {done:,} rows")
                # job 전체 상태 재계산
                all_st = j["item_statuses"].values()
                if all(s.get("status") in ("done","skip") for s in all_st if s.get("type")=="table"):
                    if not any(s.get("status")=="running" for s in all_st):
                        j["status"] = "completed"
                        j["progress"] = 100
            except Exception as me:
                j["item_statuses"][table].update({"status":"error","error":str(me)[:300],
                    "finished_at":datetime.now(_KST).isoformat()})
                engine._log("error", f"✗ [{table}] 재이관 실패: {me}")
            finally:
                j["current_table"] = ""
                _persist_job()   # v46: 완료/실패 상태 저장 (status 보존)
                try: src_conn.close()
                except: pass
                try: tgt_conn.close()
                except: pass
        except Exception as e:
            engine._log("error", f"재이관 엔진 오류: {e}")
        finally:
            # v46: 스레드 종료 시 _migrators 에서 해제 — 다음 재이관에서 깨끗한 엔진 사용
            _migrators.pop(jid, None)

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "table": table, "mode": mode}


@router.post("/{jid}/restart")
def restart_job(jid: str, bg: BackgroundTasks, request: Request, body: dict = None, user=Depends(require_operator)):
    """기존 Job 설정을 복사해 새 Job으로 재실행"""
    if body is None:
        body = {}
    src = _jobs.get(jid)
    if src is None:
        raise HTTPException(404, "Job을 찾을 수 없습니다")

    new_jid   = str(uuid.uuid4())
    orig_name = src["name"].replace("[재실행] ","").replace("【재실행】","").strip()
    new_job   = _new_job(new_jid, f"[재실행] {orig_name}", src["src_db"], src["tgt_db"])

    for key in ("src_host","src_port","src_database","src_username","src_password",
                "tgt_host","tgt_port","tgt_database","tgt_username","tgt_password",
                "tables","batch_size","truncate_target","create_table","on_error",
                "objects","convert_objects",
                "schema_strategy"):  # v90.48 + hotfix_018: src_port/tgt_port 추가
        new_job[key] = src.get(key, new_job.get(key))

    for key in ("src_host","src_database","src_username","src_password","src_port",
                "tgt_host","tgt_database","tgt_username","tgt_password","tgt_port"):
        if body.get(key):
            new_job[key] = body[key]

    new_job["table_total"]    = len(new_job.get("tables") or [])
    new_job["status"]         = "running"
    new_job["started_at"]     = datetime.now(_KST).isoformat()
    new_job["progress"]       = 0
    new_job["rows_processed"] = 0
    new_job["rows_total"]     = 0
    new_job["current_table"]  = "준비 중..."

    # ═══════════════════════════════════════════════════════════════
    # v90.45: 재실행 시 빈 objects/tables 자동 보강
    # ═══════════════════════════════════════════════════════════════
    # 본부장님 보고: 재실행 후 화면에 "0/0개" 로 표시되어 아무것도 이관 안 됨.
    # 원인: 원본 Job 의 objects 가 비어있거나, 이전 버전 buggy 시점에 저장된 Job.
    # 해결: objects (또는 tables) 가 비어있으면 소스 DB 에서 자동 재조회.
    def _objects_is_empty(objs):
        """objects dict 가 모두 빈 리스트인지 (None 포함)"""
        if not objs or not isinstance(objs, dict):
            return True
        return not any(objs.get(k) for k in ("procedures","functions","triggers","views"))
    
    _replenish_log = []
    _src_db_type = (new_job.get("src_db") or "").lower()
    # ─── v95_p107 hotfix_018 (2026-05-10): 포트 하드코딩 완전 제거 ───
    # 본부장님 모토 #4: 위저드 = single source, 표준 포트도 환경마다 변경 가능.
    # _src_default_port 변수 자체를 제거 — 위저드 값(src_port) 만 사용.
    
    # 공통 conn dict (schema._query_tables / _get_objects_* 가 받는 형식)
    _src_conn = {
        "db_type":  _src_db_type,
        "host":     new_job.get("src_host",""),
        "port":     new_job.get("src_port"),  # hotfix_018: 위저드 값 그대로, None 가능
        "username": new_job.get("src_username",""),
        "password": new_job.get("src_password",""),
        "database": new_job.get("src_database",""),
    }
    # 비밀번호가 암호문이면 복호화
    try:
        from app.core.password_resolver import resolve_password
        _src_conn["password"] = resolve_password(
            _src_conn["password"], side="source",
            host=_src_conn["host"],
            username=_src_conn["username"],
            database=_src_conn["database"],
        )
    except Exception:
        pass  # resolve 실패해도 평문일 수도 있음 — 그대로 시도
    
    # 1) tables 보강 (비어있으면)
    if not new_job.get("tables") and _src_conn["host"] and _src_conn["database"]:
        try:
            from app.api.routes.schema import _query_tables
            _tbl_list = _query_tables(_src_conn) or []
            # _query_tables 는 dict 리스트 반환 → name 만 추출
            if _tbl_list and isinstance(_tbl_list[0], dict):
                _tbl_names = [t.get("name") for t in _tbl_list if t.get("name")]
            else:
                _tbl_names = list(_tbl_list)
            new_job["tables"] = _tbl_names
            new_job["table_total"] = len(_tbl_names)
            _replenish_log.append(f"tables 자동 조회: {len(_tbl_names)}개")
        except Exception as _te:
            _replenish_log.append(f"tables 자동 조회 실패: {str(_te)[:120]}")
    
    # 2) objects 보강 (비어있으면)
    if _objects_is_empty(new_job.get("objects")) and _src_conn["host"] and _src_conn["database"]:
        try:
            from app.api.routes.schema import _get_objects_mssql, _get_objects_mysql
            if _src_db_type in ("mssql","azure"):
                _obj_dict = _get_objects_mssql(
                    _src_conn["host"], _src_conn["port"],
                    _src_conn["username"], _src_conn["password"],
                    _src_conn["database"],
                )
            elif _src_db_type in ("mysql","aurora","mariadb","tidb","cloudsql"):
                _obj_dict = _get_objects_mysql(
                    _src_conn["host"], _src_conn["port"],
                    _src_conn["username"], _src_conn["password"],
                    _src_conn["database"],
                )
            else:
                _obj_dict = {}
            
            # _get_objects_* 는 {"procedures":[{name,schema_name,...}], ...} 반환
            # migration_engine 은 단순 string 리스트 기대 → 이름만 추출
            _normalized = {"procedures":[], "functions":[], "triggers":[], "views":[]}
            for _key in _normalized.keys():
                _items = _obj_dict.get(_key) or []
                for _item in _items:
                    if isinstance(_item, dict):
                        _name = _item.get("name") or ""
                    else:
                        _name = str(_item)
                    if _name:
                        _normalized[_key].append(_name)
            
            new_job["objects"] = _normalized
            _counts = {k: len(v) for k, v in _normalized.items() if v}
            _total = sum(_counts.values())
            _replenish_log.append(f"objects 자동 조회: {_counts} (총 {_total}개)")
        except Exception as _oe:
            _replenish_log.append(f"objects 자동 조회 실패: {str(_oe)[:120]}")
    # ═══════════════════════════════════════════════════════════════

    # 저장 직전 비밀번호 암호화 (원본에서 이미 암호화된 것은 재암호화 방지됨)
    new_job = _encrypt_job_passwords(new_job)
    _jobs.set(new_jid, new_job)
    _job_logs[new_jid] = [{
        "time":    datetime.now(_KST).strftime("%H:%M:%S"),
        "level":   "info",
        "tag":     f"Job#{new_jid[:6]}",
        "message": f"재실행 시작 — 원본: {orig_name}",
    }]
    # v90.45: 자동 보강 결과를 Job 로그에 추가
    for _msg in _replenish_log:
        _job_logs[new_jid].append({
            "time":    datetime.now(_KST).strftime("%H:%M:%S"),
            "level":   "info",
            "tag":     f"Job#{new_jid[:6]}",
            "message": f"[v90.45 자동보강] {_msg}",
        })
    bg.add_task(_run_migration, new_jid)
    _audit.record(
        action=_AuditActions.JOB_RESTART, status="ok",
        user=user, resource="job", resource_id=new_jid,
        ip=(request.client.host if request.client else None),
        details={"original_job_id": jid, "name": new_job.get("name")},
    )
    return _mask_job_response(new_job)


@router.post("/{jid}/resume-from-checkpoint")
def resume_from_checkpoint(jid: str, bg: BackgroundTasks, request: Request, user=Depends(require_operator)):
    """
    중단된 Job을 마지막 체크포인트에서 재개.

    동작:
      - 대상 Job의 status가 error/aborted/paused 여야 함
      - item_statuses 의 각 테이블에 저장된 checkpoint를 그대로 유지하고
        resume_from_checkpoint=True 플래그를 세워 엔진을 재기동.
      - 이미 'done' 처리된 테이블은 건너뛰며, 'running' 상태에서
        체크포인트가 있는 테이블은 해당 지점부터 이관 이어짐.

    제약:
      - 소스/타겟 DB가 이관 중 변경되지 않았다는 전제 (스키마 동일)
      - drop_table/truncate_target 플래그가 True 였다면 경고 반환
        (재개 시 이미 적재된 데이터를 날리면 안 되므로)
    """
    j = _jobs.get(jid)
    if j is None:
        raise HTTPException(404, "Job을 찾을 수 없습니다")

    status = j.get("status", "")
    if status not in ("error", "aborted", "paused"):
        raise HTTPException(400,
            f"재개 불가 — 현재 상태 '{status}' (error/aborted/paused 만 가능)")

    # 안전 검증: drop_table/truncate가 켜져 있었다면 재개 금지 (데이터 손실 위험)
    if j.get("drop_table") or j.get("truncate_target"):
        raise HTTPException(400,
            "재개 불가 — 이 Job은 DROP/TRUNCATE 옵션이 켜져 있어 재개 시 "
            "완료된 테이블 데이터도 삭제됩니다. 대신 '재실행(restart)'을 사용하세요.")

    # 체크포인트 존재 여부 체크
    items = j.get("item_statuses", {}) or {}
    has_checkpoint = any(
        isinstance(v, dict) and v.get("checkpoint") for v in items.values()
    )
    done_tables = [t for t, v in items.items()
                   if isinstance(v, dict) and v.get("status") == "done"]

    if not has_checkpoint and not done_tables:
        raise HTTPException(400,
            "재개할 체크포인트가 없습니다 — 첫 테이블 시작 전에 중단된 것으로 보입니다. "
            "'재실행(restart)'을 사용하세요.")

    # 상태 초기화 — running 으로 전환하되 체크포인트/완료 테이블은 유지
    j["status"]       = "running"
    j["phase"]        = "RUNNING"
    j["error_message"] = None
    j["started_at"]   = datetime.now(_KST).isoformat()
    j["finished_at"]  = None
    j["resume_from_checkpoint"] = True   # 엔진이 이 플래그를 읽음
    # 'done' 처리된 테이블은 건너뛰도록 item_statuses 그대로 유지
    # 'error'/'running' 이었던 테이블은 pending 으로 되돌림 (재개 대상)
    for t, v in list(items.items()):
        if isinstance(v, dict) and v.get("status") in ("error", "running"):
            v["status"] = "pending"
            v["error"] = None
            # checkpoint는 남겨둠 → 엔진이 복원

    _jobs.set(jid, j)
    _job_logs.setdefault(jid, []).append({
        "time":    datetime.now(_KST).strftime("%H:%M:%S"),
        "level":   "info",
        "tag":     f"Job#{jid[:6]}",
        "message": f"Resume 재개 — 완료 {len(done_tables)}개, 체크포인트 {sum(1 for v in items.values() if isinstance(v,dict) and v.get('checkpoint'))}개",
    })
    bg.add_task(_run_migration, jid)
    _audit.record(
        action=_AuditActions.JOB_RESUME, status="ok",
        user=user, resource="job", resource_id=jid,
        ip=(request.client.host if request.client else None),
        details={"done_tables": len(done_tables),
                 "checkpoints": sum(1 for v in items.values()
                                    if isinstance(v, dict) and v.get("checkpoint"))},
    )
    return {
        "ok": True,
        "job_id": jid,
        "done_tables": len(done_tables),
        "checkpoints": sum(1 for v in items.values()
                           if isinstance(v, dict) and v.get("checkpoint")),
        "message": "체크포인트부터 재개합니다",
    }


@router.get("/{jid}/logs")
def get_logs(jid: str, _=Depends(require_viewer)):
    return _job_logs.get(jid, [])
