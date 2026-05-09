"""
app/api/routes/report.py
실행 리포트 API — 실제 Job 데이터 기반
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import io, csv, json
from datetime import datetime

router = APIRouter()


def _get_jobs() -> list:
    """jobs 모듈의 Store에서 직접 읽기 (순환 import 방지용 지연 import)"""
    try:
        from app.api.routes.jobs import _jobs
        return _jobs.values()
    except Exception:
        return []


@router.get("/history")
def get_history(
    status: str = "",
    src_db: str = "",
    tgt_db: str = "",
    limit:  int = 100,
):
    """Job 실행 히스토리 반환"""
    jobs = _get_jobs()

    # 완료·오류·중단된 것만 (진행 중 제외)
    terminal = ("completed", "error", "aborted")
    result = [j for j in jobs if j.get("status") in terminal]

    # 필터
    if status: result = [j for j in result if j.get("status") == status]
    if src_db: result = [j for j in result if j.get("src_db") == src_db]
    if tgt_db: result = [j for j in result if j.get("tgt_db") == tgt_db]

    # 최신순 정렬
    result.sort(key=lambda j: j.get("finished_at") or j.get("created_at") or "", reverse=True)

    # 필요한 필드만 추출
    out = []
    for j in result[:limit]:
        started  = j.get("started_at")
        finished = j.get("finished_at")
        duration_min = None
        if started and finished:
            try:
                s = datetime.fromisoformat(started.replace("Z",""))
                f = datetime.fromisoformat(finished.replace("Z",""))
                duration_min = round((f - s).total_seconds() / 60, 1)
            except Exception:
                pass
        out.append({
            "id":           j["id"],
            "job_name":     j.get("name", ""),
            "src":          j.get("src_db", ""),
            "tgt":          j.get("tgt_db", ""),
            "src_host":     j.get("src_host", ""),
            "tgt_host":     j.get("tgt_host", ""),
            "src_database": j.get("src_database", ""),
            "tgt_database": j.get("tgt_database", ""),
            "created_at":   j.get("created_at"),
            "started_at":   started,
            "finished_at":  finished,
            "duration_min": duration_min,
            "rows":         j.get("rows_processed", 0),
            "rows_total":   j.get("rows_total", 0),
            "rows_error":   j.get("rows_error", 0),
            "errors":       j.get("rows_error", 0),
            "status":       j.get("status"),
            "progress":     j.get("progress", 0),
            "tables":       len(j.get("tables") or []),
            "batch_size":   j.get("batch_size", 5000),
            "error_message": j.get("error_message"),
        })
    return out


@router.get("/stats")
def get_stats():
    """전체 통계 집계"""
    jobs = _get_jobs()
    terminal = [j for j in jobs if j.get("status") in ("completed","error","aborted")]
    completed = [j for j in terminal if j.get("status") == "completed"]

    total_rows  = sum(j.get("rows_processed", 0) for j in jobs)
    total_dur   = 0
    speed_list  = []

    for j in completed:
        started  = j.get("started_at")
        finished = j.get("finished_at")
        rows     = j.get("rows_processed", 0)
        if started and finished and rows:
            try:
                s = datetime.fromisoformat(started.replace("Z",""))
                f = datetime.fromisoformat(finished.replace("Z",""))
                secs = (f - s).total_seconds()
                if secs > 0:
                    total_dur += secs
                    speed_list.append(rows / secs)
            except Exception:
                pass

    avg_speed = round(sum(speed_list) / len(speed_list)) if speed_list else 0
    success_rate = round(len(completed) / len(terminal) * 100, 1) if terminal else 100.0

    return {
        "total_migrations":    len(terminal),
        "total_rows":          total_rows,
        "avg_speed_rows_sec":  avg_speed,
        "success_rate":        success_rate,
        "completed":           len(completed),
        "errors":              sum(1 for j in terminal if j.get("status") == "error"),
        "aborted":             sum(1 for j in terminal if j.get("status") == "aborted"),
        "total_duration_min":  round(total_dur / 60, 1),
    }


@router.get("/export/{job_id}")
def export_report(job_id: str, format: str = "csv"):
    """단일 Job 리포트 내보내기 (CSV / JSON)"""
    jobs = _get_jobs()
    job  = next((j for j in jobs if j.get("id") == job_id), None)
    if not job:
        from fastapi import HTTPException
        raise HTTPException(404, "Job을 찾을 수 없습니다")

    if format == "json":
        content = json.dumps(job, ensure_ascii=False, indent=2, default=str)
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="job_{job_id[:8]}.json"'}
        )

    # CSV (기본)
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["필드", "값"])
    for k, v in job.items():
        w.writerow([k, v])
    content = "\uFEFF" + output.getvalue()  # BOM for Excel
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="job_{job_id[:8]}.csv"'}
    )


@router.get("/export-all")
def export_all(format: str = "csv"):
    """전체 Job 히스토리 내보내기"""
    history = get_history(limit=10000)

    if format == "json":
        content = json.dumps(history, ensure_ascii=False, indent=2, default=str)
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="databridge_report.json"'}
        )

    output = io.StringIO()
    w = csv.writer(output)
    if history:
        w.writerow(history[0].keys())
        for row in history:
            w.writerow(row.values())
    content = "\uFEFF" + output.getvalue()
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="databridge_report.csv"'}
    )
