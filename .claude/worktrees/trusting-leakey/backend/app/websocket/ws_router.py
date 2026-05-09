"""
app/websocket/ws_router.py
WebSocket 라우터 — 실제 Job 상태를 1초마다 브로드캐스트
"""
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

ws_router = APIRouter()


def _get_job(job_id: str) -> dict | None:
    """jobs 모듈 Store에서 Job 상태 조회 (지연 import로 순환 참조 방지)"""
    try:
        from app.api.routes.jobs import _jobs
        return _jobs.get(job_id)
    except Exception:
        return None


def _get_all_jobs() -> list:
    try:
        from app.api.routes.jobs import _jobs
        return _jobs.values()
    except Exception:
        return []


def _get_logs(job_id: str) -> list:
    try:
        from app.api.routes.jobs import _job_logs
        return _job_logs.get(job_id, [])
    except Exception:
        return []


# ── 개별 Job 모니터 WebSocket ─────────────────────────────
@ws_router.websocket("/jobs/{job_id}")
async def job_ws(websocket: WebSocket, job_id: str):
    """특정 Job의 실시간 상태 스트림"""
    await websocket.accept()
    last_log_len = 0

    try:
        while True:
            job = _get_job(job_id)

            if job is None:
                await websocket.send_text(json.dumps({
                    "error": "Job을 찾을 수 없습니다",
                    "job_id": job_id,
                }))
                break

            # 새로운 로그 항목만 전송
            logs     = _get_logs(job_id)
            new_logs = logs[last_log_len:]
            last_log_len = len(logs)

            payload = {
                "job_id":                  job_id,
                "status":                  job.get("status", "idle"),
                "progress":                job.get("progress", 0),
                "rows_processed":          job.get("rows_processed", 0),
                "rows_total":              job.get("rows_total", 0),
                "rows_error":              job.get("rows_error", 0),
                "speed":                   job.get("speed", 0),
                "table_done":              job.get("table_done", 0),
                "table_total":             job.get("table_total", 0),
                "current_table":           job.get("current_table", ""),
                "current_table_rows_done": job.get("current_table_rows_done", 0),
                "current_table_rows_total":job.get("current_table_rows_total", 0),
                "started_at":              job.get("started_at"),
                "finished_at":             job.get("finished_at"),
                "error_message":           job.get("error_message"),
                "new_logs":                new_logs,
            }

            await websocket.send_text(json.dumps(payload, default=str))

            # 완료 / 오류 / 중단 상태면 연결 종료
            if job.get("status") in ("completed", "error", "aborted"):
                break

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"error": str(e)}))
        except Exception:
            pass


# ── 전체 Job 목록 요약 스트림 ─────────────────────────────
@ws_router.websocket("/monitor")
async def monitor_ws(websocket: WebSocket):
    """전체 Job 실행 현황 요약 스트림 (대시보드·모니터 페이지용)"""
    await websocket.accept()
    try:
        while True:
            jobs = _get_all_jobs()
            running = [j for j in jobs if j.get("status") == "running"]
            summary = {
                "timestamp": asyncio.get_event_loop().time(),
                "total":     len(jobs),
                "running":   len(running),
                "completed": sum(1 for j in jobs if j.get("status") == "completed"),
                "errors":    sum(1 for j in jobs if j.get("status") == "error"),
                "jobs": [
                    {
                        "id":              j["id"],
                        "name":            j.get("name", ""),
                        "status":          j.get("status"),
                        "progress":        j.get("progress", 0),
                        "rows_processed":  j.get("rows_processed", 0),
                        "speed":           j.get("speed", 0),
                        "current_table":   j.get("current_table", ""),
                    }
                    for j in running
                ],
            }
            await websocket.send_text(json.dumps(summary, default=str))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
