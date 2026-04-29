"""
app/websocket/ws_router.py
DataBridge Studio — WebSocket 실시간 스트림

엔드포인트:
  GET /ws/monitor          → 전체 Job 현황 브로드캐스트 (2초 간격)
  GET /ws/jobs/{job_id}    → 특정 Job 상태 + 새 로그 실시간 스트림

메시지 포맷 (JSON):
  /ws/monitor  : { "jobs": [...], "stats": {...}, "ts": "HH:MM:SS" }
  /ws/jobs/:id : { ...job_fields, "new_logs": [...], "ts": "HH:MM:SS" }
  에러         : { "error": "메시지" }

설계 원칙:
  - FastAPI WebSocket, asyncio, 별도 스레드 없이 동작
  - jobs Store (JSON 파일 기반) 를 직접 읽어 브로드캐스트
  - 클라이언트 연결 해제 시 즉시 루프 종료, 리소스 누수 없음
  - monitor : 연결된 모든 클라이언트에게 동일 페이로드 전송
  - job ws  : 해당 job 이 완료/오류/중단이면 마지막 메시지 후 연결 종료
"""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
KST = timezone(timedelta(hours=9))
from typing import Set, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
log    = logging.getLogger("databridge.ws")


# ── WebSocket 인증 ───────────────────────────────────────────────────

async def _authenticate_ws(ws: WebSocket, required_role: str = "viewer") -> Optional[dict]:
    """
    WebSocket 연결 인증 — accept() 전에 호출해야 함.

    토큰 추출 순서 (HTTP와 동일):
      1. X-Auth-Token 헤더
      2. Authorization: Bearer <token>
      3. 쿼리 파라미터 ?token=...

    브라우저 WebSocket API는 커스텀 헤더를 직접 못 실음 → 쿼리 파라미터 실사용.

    실패 시:
      - RBAC 비활성이면 임시 admin 세션 반환 (기존 동작 유지)
      - 토큰 없음/무효/만료 → ws.close(code=1008) 후 None 반환
      - 권한 부족 → ws.close(code=1008) 후 None 반환 + 감사 기록

    성공 시:
      - 세션 dict 반환: {username, role, expires_at, ...}
    """
    import os
    rbac_on = os.environ.get("DATABRIDGE_RBAC_ENABLED", "true").lower() not in ("false", "0", "no")
    if not rbac_on:
        return {"username": "admin", "role": "admin", "rbac_disabled": True}

    # 토큰 추출
    token = (
        ws.headers.get("X-Auth-Token")
        or ws.headers.get("x-auth-token")
        or ""
    )
    if not token:
        auth_h = ws.headers.get("Authorization", "") or ws.headers.get("authorization", "")
        if auth_h.lower().startswith("bearer "):
            token = auth_h[7:].strip()
    if not token:
        token = ws.query_params.get("token", "")

    if not token:
        _ws_audit_deny(ws, required_role, None, reason="no_token")
        await ws.close(code=1008, reason="Missing authentication token")
        return None

    from app.core.auth import resolve_session, has_role
    sess = resolve_session(token)
    if not sess:
        _ws_audit_deny(ws, required_role, None, reason="invalid_or_expired")
        await ws.close(code=1008, reason="Invalid or expired token")
        return None

    if not has_role(sess.get("role", "guest"), required_role):
        _ws_audit_deny(ws, required_role, sess, reason="insufficient_role")
        await ws.close(code=1008, reason="Insufficient role")
        return None

    return sess


def _ws_audit_deny(ws: WebSocket, required: str, sess: Optional[dict], *, reason: str) -> None:
    """WebSocket 거부 이벤트를 감사 로그에 기록"""
    try:
        from app.core import audit
        path = str(ws.url.path) if hasattr(ws, "url") else ""
        parts = [p for p in path.split("/") if p and p not in ("ws",)]
        resource = "ws." + (parts[0] if parts else "unknown")
        client_host = ws.client.host if ws.client else None
        audit.record(
            action="auth.denied",
            status="denied",
            user=sess,
            resource=resource,
            resource_id=None,
            ip=client_host,
            details={
                "required_role": required,
                "method":        "WS",
                "path":          path,
                "reason":        reason,
            },
        )
    except Exception:
        pass


# ── 내부 헬퍼 ────────────────────────────────────────────────────────


def _now_str() -> str:
    return datetime.now(KST).strftime("%H:%M:%S")


def _get_jobs() -> list:
    """jobs Store 에서 전체 Job 목록 반환 (지연 import — 순환 방지)"""
    try:
        from app.api.routes.jobs import _jobs
        return list(_jobs.values())
    except Exception as e:
        log.warning("_get_jobs 실패: %s", e)
        return []


def _get_job(job_id: str) -> dict | None:
    """특정 Job 반환"""
    try:
        from app.api.routes.jobs import _jobs
        return _jobs.get(job_id)
    except Exception:
        return None


def _get_logs(job_id: str) -> list:
    """특정 Job 의 메모리 로그 반환"""
    try:
        from app.api.routes.jobs import _job_logs
        return list(_job_logs.get(job_id, []))
    except Exception:
        return []


def _calc_stats(jobs: list) -> dict:
    return {
        "totalJobs":      len(jobs),
        "running":        sum(1 for j in jobs if j.get("status") == "running"),
        "errors":         sum(1 for j in jobs if j.get("status") == "error"),
        "completedToday": sum(1 for j in jobs if j.get("status") == "completed"),
        "totalRows":      sum(j.get("rows_processed", 0) for j in jobs),
    }


# ── 연결 관리 ─────────────────────────────────────────────────────────

_monitor_clients: Set[WebSocket] = set()


# ══════════════════════════════════════════════════════════════════════
# /ws/monitor  — 전체 Job 현황 브로드캐스트
# ══════════════════════════════════════════════════════════════════════

@router.websocket("/monitor")
async def ws_monitor(ws: WebSocket):
    """
    2초마다 전체 Job 목록 + 통계를 브로드캐스트.
    클라이언트가 연결하는 순간부터 모니터링 시작.

    인증: viewer 이상 필요 (토큰 쿼리 파라미터 ?token=... 또는 헤더로 전달).
    """
    user = await _authenticate_ws(ws, required_role="viewer")
    if user is None:
        return   # 인증 실패 — close는 _authenticate_ws 내부에서 처리
    await ws.accept()
    _monitor_clients.add(ws)
    log.info("[WS/monitor] 클라이언트 연결: user=%s (%d명)",
             user.get("username"), len(_monitor_clients))

    try:
        while True:
            jobs  = _get_jobs()
            stats = _calc_stats(jobs)

            payload = json.dumps({
                "jobs":  jobs,
                "stats": stats,
                "ts":    _now_str(),
            }, ensure_ascii=False, default=str)

            await ws.send_text(payload)

            # 2초 대기 — 0.1초 단위로 분할해 클라이언트 메시지도 처리
            for _ in range(20):
                await asyncio.sleep(0.1)
                # 클라이언트가 보낸 메시지(ping/command) 처리 (옵션)
                try:
                    msg = await asyncio.wait_for(ws.receive_text(), timeout=0.01)
                    if msg == "ping":
                        await ws.send_text(json.dumps({"pong": True}))
                except asyncio.TimeoutError:
                    pass

    except WebSocketDisconnect:
        log.info("[WS/monitor] 클라이언트 연결 해제")
    except Exception as e:
        log.warning("[WS/monitor] 오류: %s", e)
        try:
            await ws.send_text(json.dumps({"error": str(e)}))
        except Exception:
            pass
    finally:
        _monitor_clients.discard(ws)
        log.info("[WS/monitor] 정리 완료 (%d명)", len(_monitor_clients))


# ══════════════════════════════════════════════════════════════════════
# /ws/jobs/{job_id}  — 특정 Job 실시간 스트림
# ══════════════════════════════════════════════════════════════════════

@router.websocket("/jobs/{job_id}")
async def ws_job(ws: WebSocket, job_id: str):
    """
    특정 Job 의 상태와 새 로그를 1초 간격으로 스트리밍.

    인증: viewer 이상 필요.
    Job 이 완료/오류/중단 상태이면 마지막 메시지를 보내고 연결을 닫음.
    """
    user = await _authenticate_ws(ws, required_role="viewer")
    if user is None:
        return
    await ws.accept()
    log.info("[WS/job] 연결: user=%s, job_id=%s", user.get("username"), job_id[:8])

    # 먼저 Job 존재 여부 확인
    job = _get_job(job_id)
    if job is None:
        await ws.send_text(json.dumps({"error": f"Job {job_id} 를 찾을 수 없습니다"}))
        await ws.close()
        return

    # 마지막으로 클라이언트에 전달한 로그 인덱스
    last_log_idx = 0
    TERMINAL = {"completed", "error", "aborted"}

    try:
        while True:
            job = _get_job(job_id)
            if job is None:
                await ws.send_text(json.dumps({"error": "Job 이 삭제됐습니다"}))
                break

            # 새 로그만 추출
            all_logs = _get_logs(job_id)
            new_logs = all_logs[last_log_idx:]
            last_log_idx = len(all_logs)

            # 핵심 필드만 추출 (패스워드 제외)
            EXCLUDE = {"src_password", "tgt_password"}
            payload = {k: v for k, v in job.items() if k not in EXCLUDE}
            payload["new_logs"] = new_logs
            payload["ts"]       = _now_str()

            await ws.send_text(
                json.dumps(payload, ensure_ascii=False, default=str)
            )

            # 종료 상태이면 루프 탈출
            if job.get("status") in TERMINAL:
                log.info("[WS/job] Job 종료 상태 (%s) — 연결 닫음", job.get("status"))
                break

            # 1초 대기 (0.1초 단위 분할)
            for _ in range(10):
                await asyncio.sleep(0.1)
                try:
                    msg = await asyncio.wait_for(ws.receive_text(), timeout=0.01)
                    if msg == "ping":
                        await ws.send_text(json.dumps({"pong": True, "ts": _now_str()}))
                    elif msg == "stop":
                        log.info("[WS/job] 클라이언트가 stop 요청")
                        return
                except asyncio.TimeoutError:
                    pass

    except WebSocketDisconnect:
        log.info("[WS/job] 클라이언트 연결 해제: job_id=%s", job_id[:8])
    except Exception as e:
        log.warning("[WS/job] 오류: %s", e)
        try:
            await ws.send_text(json.dumps({"error": str(e)}))
        except Exception:
            pass
    finally:
        log.info("[WS/job] 정리 완료: job_id=%s", job_id[:8])


# ══════════════════════════════════════════════════════════════════════
# /ws/ping  — 헬스체크용 (선택)
# ══════════════════════════════════════════════════════════════════════

@router.websocket("/ping")
async def ws_ping(ws: WebSocket):
    """간단한 WS 헬스체크 — 연결 후 pong 응답하고 종료"""
    await ws.accept()
    await ws.send_text(json.dumps({"pong": True, "ts": _now_str()}))
    await ws.close()
