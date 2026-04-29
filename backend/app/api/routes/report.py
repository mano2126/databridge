"""
app/api/routes/report.py
실행 리포트 API — 실제 Job 데이터 기반

v90 P2 (2026-04-23) — 충실한 검증 리포트:
  - 위저드에서 선택한 모든 항목 (테이블/SP/Function/Trigger/View/옵션들) 이
    실제 이관에 어떻게 반영됐는지 대조하는 상세 리포트 추가.
  - GET /verify/{job_id}        — JSON (프론트 렌더링용)
  - GET /export/{job_id}        — CSV/JSON/HTML 다운로드 (구조화 섹션)
  - 기존 /history, /stats, /export-all 은 하위 호환 유지
"""
from fastapi import APIRouter, Depends, HTTPException
from app.core.auth_deps import require_viewer
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


def _find_job(job_id: str):
    jobs = _get_jobs()
    return next((j for j in jobs if j.get("id") == job_id), None)


# ═══════════════════════════════════════════════════════════════════
# v90 P2: 검증 리포트 빌더
# ═══════════════════════════════════════════════════════════════════

def _build_verify_report(job: dict) -> dict:
    """위저드 선택 vs 실제 결과 검증 리포트."""
    item_statuses = job.get("item_statuses") or {}

    # ── 1. 기본 정보 ──────────────────────────────────────
    started  = job.get("started_at") or ""
    finished = job.get("finished_at") or ""
    duration_sec = None
    if started and finished:
        try:
            s = datetime.fromisoformat(started.replace("Z","").replace("+00:00",""))
            f = datetime.fromisoformat(finished.replace("Z","").replace("+00:00",""))
            duration_sec = round((f - s).total_seconds(), 1)
        except Exception:
            pass

    summary = {
        "job_id":       job.get("id", ""),
        "job_name":     job.get("name", ""),
        "status":       job.get("status", ""),
        "progress":     job.get("progress", 0),
        "src_db":       job.get("src_db", ""),
        "src_host":     job.get("src_host", ""),
        "src_database": job.get("src_database", ""),
        "tgt_db":       job.get("tgt_db", ""),
        "tgt_host":     job.get("tgt_host", ""),
        "tgt_database": job.get("tgt_database", ""),
        "started_at":   started,
        "finished_at":  finished,
        "duration_sec": duration_sec,
    }

    # ── 2. 위저드 선택 옵션 스냅샷 ──────────────────────────
    wizard_selected = {
        "scope": {
            "tables_count": len(job.get("tables") or []),
            "tables":       job.get("tables") or [],
            "objects": {
                "procedures": (job.get("objects") or {}).get("procedures") or [],
                "functions":  (job.get("objects") or {}).get("functions") or [],
                "triggers":   (job.get("objects") or {}).get("triggers") or [],
                "views":      (job.get("objects") or {}).get("views") or [],
            },
            "objects_count": {
                "procedures": len((job.get("objects") or {}).get("procedures") or []),
                "functions":  len((job.get("objects") or {}).get("functions") or []),
                "triggers":   len((job.get("objects") or {}).get("triggers") or []),
                "views":      len((job.get("objects") or {}).get("views") or []),
            },
        },
        "mode": {
            "table_mode":       job.get("table_mode", "schema_data"),
            "obj_mode":         job.get("obj_mode", "drop_recreate"),
            "view_mode":        job.get("view_mode", "drop_recreate"),
            "truncate_target":  bool(job.get("truncate_target", False)),
            "create_table":     bool(job.get("create_table", True)),
            "drop_table":       bool(job.get("drop_table", False)),
            "convert_objects":  bool(job.get("convert_objects", True)),
            "on_error":         job.get("on_error", "skip"),
        },
        "engine": {
            "ddl_engine": job.get("ddl_engine", "auto"),
            "obj_engine": job.get("obj_engine", "auto"),
        },
        "performance": {
            "batch_size":          int(job.get("batch_size", 5000)),
            "parallel_workers":    int(job.get("parallel_workers", 4)),
            "parallel_tables":     int(job.get("parallel_tables", 3)),
            "bulk_mode":           job.get("bulk_mode", "auto"),
            "bulk_threshold_rows": int(job.get("bulk_threshold_rows", 100000)),
        },
        "mssql_tuning": {
            "enabled":         bool(job.get("mssql_tuning", False)),
            "disable_indexes": bool(job.get("mssql_disable_indexes", False)),
        },
    }

    # ── 3. 실제 수행 결과 — 테이블 ─────────────────────────
    tables_selected = job.get("tables") or []
    tables_result = []
    t_done = t_err = t_pending = t_skipped = 0
    t_rows_total_src = 0
    t_rows_total_tgt = 0

    for t in tables_selected:
        s = item_statuses.get(t, {}) or {}
        status = s.get("status", "pending")
        rows_src = int(s.get("rows_src") or s.get("rows_total") or 0)
        rows_tgt = int(s.get("rows") or s.get("rows_tgt") or 0)
        err = s.get("error")

        if status == "done":
            t_done += 1
            if rows_src > 0 and rows_tgt != rows_src:
                verdict = "mismatch"
            elif rows_src == 0 and rows_tgt == 0:
                verdict = "empty"
            else:
                verdict = "ok"
        elif status == "error":
            t_err += 1
            verdict = "error"
        elif status == "skipped":
            t_skipped += 1
            verdict = "skipped"
        else:
            t_pending += 1
            verdict = "pending"

        t_rows_total_src += rows_src
        t_rows_total_tgt += rows_tgt

        tables_result.append({
            "name":       t,
            "status":     status,
            "verdict":    verdict,
            "rows_src":   rows_src,
            "rows_tgt":   rows_tgt,
            "rows_diff":  rows_tgt - rows_src,
            "error":      err,
            "started_at":  s.get("started_at"),
            "finished_at": s.get("finished_at"),
        })

    # ── 4. 실제 수행 결과 — 오브젝트 ────────────────────────
    objects_selected = job.get("objects") or {}
    objects_result = {"procedures": [], "functions": [], "triggers": [], "views": []}
    obj_stats = {
        "procedures": {"selected": 0, "done": 0, "error": 0, "pending": 0},
        "functions":  {"selected": 0, "done": 0, "error": 0, "pending": 0},
        "triggers":   {"selected": 0, "done": 0, "error": 0, "pending": 0},
        "views":      {"selected": 0, "done": 0, "error": 0, "pending": 0},
    }

    for otype in ("procedures", "functions", "triggers", "views"):
        selected_list = objects_selected.get(otype) or []
        obj_stats[otype]["selected"] = len(selected_list)
        for name in selected_list:
            s = item_statuses.get(name, {}) or {}
            status = s.get("status", "pending")
            err = s.get("error")
            if status == "done":
                obj_stats[otype]["done"] += 1
            elif status == "error":
                obj_stats[otype]["error"] += 1
            else:
                obj_stats[otype]["pending"] += 1

            objects_result[otype].append({
                "name":        name,
                "status":      status,
                "error":       err,
                "started_at":  s.get("started_at"),
                "finished_at": s.get("finished_at"),
            })

    # ── 5. 선택 외 항목 (엔진이 자동 처리한 것 등) ──────────
    all_selected_names = set(tables_selected)
    for otype in ("procedures", "functions", "triggers", "views"):
        all_selected_names.update(objects_selected.get(otype) or [])

    unexpected = []
    for name, s in item_statuses.items():
        if name not in all_selected_names:
            s = s or {}
            unexpected.append({
                "name":   name,
                "type":   s.get("type", "unknown"),
                "status": s.get("status", "unknown"),
                "note":   "위저드 선택에 없었음 — 엔진이 자동 처리"
                          if s.get("type") == "trigger"
                          else "위저드 선택에 없었음 — 확인 필요",
            })

    # ── 6. 종합 판정 ─────────────────────────────────────
    total_selected = (
        len(tables_selected)
        + sum(obj_stats[t]["selected"] for t in obj_stats)
    )
    total_done = t_done + sum(obj_stats[t]["done"] for t in obj_stats)
    total_error = t_err + sum(obj_stats[t]["error"] for t in obj_stats)
    mismatch_tables = [t for t in tables_result if t["verdict"] == "mismatch"]
    data_ok = (t_err == 0) and (len(mismatch_tables) == 0)

    if total_selected == 0:
        overall = "no_selection"
    elif total_error == 0 and data_ok and t_pending == 0:
        overall = "success"
    elif total_error == 0 and data_ok:
        overall = "in_progress"
    elif t_err == 0 and total_error > 0:
        overall = "partial"
    else:
        overall = "failed"

    verdict_summary = {
        "overall":         overall,
        "total_selected":  total_selected,
        "total_done":      total_done,
        "total_error":     total_error,
        "success_rate":    round(total_done / total_selected * 100, 1) if total_selected else 0.0,
        "tables": {
            "selected": len(tables_selected),
            "done":     t_done,
            "error":    t_err,
            "pending":  t_pending,
            "skipped":  t_skipped,
            "mismatch": len(mismatch_tables),
        },
        "objects_by_type": obj_stats,
        "data_integrity": {
            "rows_src_total":  t_rows_total_src,
            "rows_tgt_total":  t_rows_total_tgt,
            "rows_diff":       t_rows_total_tgt - t_rows_total_src,
            "data_ok":         data_ok,
            "mismatch_tables": [t["name"] for t in mismatch_tables],
        },
    }

    # ── 7. 실패 상세 (조치 가이드) ────────────────────────
    failures = []
    for t in tables_result:
        if t["verdict"] == "error":
            failures.append({
                "category": "table",
                "name":     t["name"],
                "error":    t["error"] or "(상세 에러 없음)",
            })
        elif t["verdict"] == "mismatch":
            failures.append({
                "category": "table_mismatch",
                "name":     t["name"],
                "error":    f"행수 불일치: 소스 {t['rows_src']:,} vs 타겟 {t['rows_tgt']:,} (차이 {t['rows_diff']:+,})",
            })
    for otype, items in objects_result.items():
        for o in items:
            if o["status"] == "error":
                failures.append({
                    "category": otype.rstrip("s"),
                    "name":     o["name"],
                    "error":    o["error"] or "(상세 에러 없음)",
                })

    return {
        "report_version":   "v90P2+v10#23",
        "generated_at":     datetime.now().isoformat(timespec="seconds"),
        "summary":          summary,
        "wizard_selected":  wizard_selected,
        "tables_result":    tables_result,
        "objects_result":   objects_result,
        "unexpected_items": unexpected,
        "verdict":          verdict_summary,
        "failures":         failures,
        # v10 #23: AI DBA Consultant 권고 Before/After 비교
        "advisor_impact":   _build_advisor_impact(job, tables_result, duration_sec),
    }


def _build_advisor_impact(job: dict, tables_result: list, duration_sec) -> dict:
    """
    AI DBA Consultant 권고의 실측 효과 분석 (v10 #23).

    Choi (CIO) 의 요청:
      "권고 따랐을 때 실제 얻은 혜택을 Before/After 로 보여줘"

    흐름:
      1. jobs Store 의 실측 데이터를 tracking Store 로 기록
      2. compute_impact 로 권고별 Before/After 계산
      3. 리포트에 포함할 형태로 가공
    """
    job_id = job.get("id") or ""
    if not job_id:
        return {"has_data": False, "reason": "no_job_id"}

    try:
        from app.core.advisor_tracking import (
            record_job_metrics, compute_impact, get_tracking,
        )
    except ImportError:
        return {"has_data": False, "reason": "advisor_tracking module missing"}

    # 이 Job 에 대한 권고 기록이 있는지 먼저 확인
    tracking = get_tracking(job_id)
    if not tracking or not tracking.get("decisions"):
        return {
            "has_data": False,
            "reason":   "no_advisor_decisions",
            "hint":     "위저드에서 AI DBA Consultant 권고를 받고 결정하면 Before/After 비교가 표시됩니다.",
        }

    # ── 1) Job 실측 데이터 수집 & tracking store 에 저장 ──
    item_statuses = job.get("item_statuses") or {}
    table_durations: dict[str, float] = {}
    for t in tables_result:
        name = t.get("name")
        if not name:
            continue
        # item_statuses 에서 started_at/finished_at 추출
        st = item_statuses.get(name) or {}
        started_s = st.get("started_at") or ""
        finished_s = st.get("finished_at") or ""
        if started_s and finished_s:
            try:
                from datetime import datetime as _dt
                s = _dt.fromisoformat(started_s.replace("Z","").replace("+00:00",""))
                f = _dt.fromisoformat(finished_s.replace("Z","").replace("+00:00",""))
                table_durations[name] = round((f - s).total_seconds(), 2)
            except Exception:
                pass

    # 전체 Job 처리량 계산
    rows_total = sum(t.get("rows_tgt") or 0 for t in tables_result)
    rows_per_sec = None
    if duration_sec and duration_sec > 0:
        rows_per_sec = round(rows_total / duration_sec, 1)

    metrics = {
        "total_duration_sec": duration_sec,
        "table_durations":    table_durations,
        "rows_total":         rows_total,
        "rows_per_sec":       rows_per_sec,
        "encoding_issues":    sum(1 for t in tables_result if (t.get("error") or "").lower().find("encoding") >= 0),
        "compat_errors":      sum(1 for t in tables_result if t.get("verdict") == "error"),
        "data_issues":        sum(1 for t in tables_result if t.get("rows_diff")),
    }
    try:
        record_job_metrics(job_id, metrics)
    except Exception:
        pass

    # ── 2) 권고별 Before/After 계산 ────────────────────────
    try:
        impact = compute_impact(job_id)
    except Exception as e:
        return {"has_data": False, "reason": f"compute_impact failed: {e}"}

    return {
        "has_data":     True,
        "job_id":       job_id,
        "summary":      impact.get("summary", {}),
        "applied":      impact.get("applied", []),
        "skipped":      impact.get("skipped", []),
        "edited":       impact.get("edited", []),
        "job_metrics":  impact.get("job_metrics", {}),
    }


# ═══════════════════════════════════════════════════════════════════
# 기존 엔드포인트 (하위 호환)
# ═══════════════════════════════════════════════════════════════════

@router.get("/history")
def get_history(
    status: str = "",
    src_db: str = "",
    tgt_db: str = "",
    limit:  int = 100,
):
    """Job 실행 히스토리 반환"""
    jobs = _get_jobs()
    terminal = ("completed", "error", "aborted")
    result = [j for j in jobs if j.get("status") in terminal]
    if status: result = [j for j in result if j.get("status") == status]
    if src_db: result = [j for j in result if j.get("src_db") == src_db]
    if tgt_db: result = [j for j in result if j.get("tgt_db") == tgt_db]
    result.sort(key=lambda j: j.get("finished_at") or j.get("created_at") or "", reverse=True)

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

    total_rows = sum(j.get("rows_processed", 0) for j in jobs)
    total_dur = 0
    speed_list = []

    for j in completed:
        started  = j.get("started_at")
        finished = j.get("finished_at")
        rows = j.get("rows_processed", 0)
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


# ═══════════════════════════════════════════════════════════════════
# v90 P2: 충실한 검증 리포트 엔드포인트
# ═══════════════════════════════════════════════════════════════════

@router.get("/verify/{job_id}")
def verify_job(job_id: str):
    """v90 P2 — 위저드 선택 vs 실제 결과 검증 리포트 (JSON)."""
    job = _find_job(job_id)
    if not job:
        raise HTTPException(404, "Job을 찾을 수 없습니다")
    return _build_verify_report(job)


@router.get("/export/{job_id}")
def export_report(job_id: str, format: str = "csv"):
    """단일 Job 리포트 내보내기.

    v90 P2 — 섹션별 구조화된 충실한 리포트:
      format=csv  → 섹션 헤더 포함 엑셀용 CSV (기본)
      format=json → 검증 리포트 JSON 전체
      format=html → 인쇄용 HTML 리포트
    """
    job = _find_job(job_id)
    if not job:
        raise HTTPException(404, "Job을 찾을 수 없습니다")

    report = _build_verify_report(job)

    if format == "json":
        content = json.dumps(report, ensure_ascii=False, indent=2, default=str)
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="verify_{job_id[:8]}.json"'}
        )

    if format == "html":
        html = _render_html_report(report)
        return StreamingResponse(
            io.BytesIO(html.encode("utf-8")),
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="verify_{job_id[:8]}.html"'}
        )

    # CSV (기본)
    output = io.StringIO()
    w = csv.writer(output)
    s  = report["summary"]
    ws = report["wizard_selected"]
    vd = report["verdict"]

    w.writerow(["=== [1] 이관 기본 정보 ==="])
    w.writerow(["Job ID",        s["job_id"]])
    w.writerow(["Job 이름",      s["job_name"]])
    w.writerow(["상태",          s["status"]])
    w.writerow(["종합 판정",     _verdict_label(vd["overall"])])
    w.writerow(["소스",          f'{s["src_db"]} / {s["src_host"]} / {s["src_database"]}'])
    w.writerow(["타겟",          f'{s["tgt_db"]} / {s["tgt_host"]} / {s["tgt_database"]}'])
    w.writerow(["시작 시각",     s["started_at"]])
    w.writerow(["종료 시각",     s["finished_at"]])
    w.writerow(["소요 시간(초)", s["duration_sec"]])
    w.writerow([])

    w.writerow(["=== [2] 위저드에서 선택한 옵션 ==="])
    w.writerow(["== 이관 범위 =="])
    w.writerow(["테이블 선택 수",    ws["scope"]["tables_count"]])
    w.writerow(["Procedure 선택 수", ws["scope"]["objects_count"]["procedures"]])
    w.writerow(["Function 선택 수",  ws["scope"]["objects_count"]["functions"]])
    w.writerow(["Trigger 선택 수",   ws["scope"]["objects_count"]["triggers"]])
    w.writerow(["View 선택 수",      ws["scope"]["objects_count"]["views"]])
    w.writerow(["== 이관 방식 =="])
    w.writerow(["테이블 모드",        ws["mode"]["table_mode"]])
    w.writerow(["오브젝트 모드",      ws["mode"]["obj_mode"]])
    w.writerow(["뷰 모드",            ws["mode"]["view_mode"]])
    w.writerow(["타겟 TRUNCATE",      ws["mode"]["truncate_target"]])
    w.writerow(["CREATE TABLE",       ws["mode"]["create_table"]])
    w.writerow(["DROP TABLE",         ws["mode"]["drop_table"]])
    w.writerow(["오브젝트 변환",       ws["mode"]["convert_objects"]])
    w.writerow(["에러 처리",          ws["mode"]["on_error"]])
    w.writerow(["== 변환 엔진 =="])
    w.writerow(["DDL 엔진",           ws["engine"]["ddl_engine"]])
    w.writerow(["오브젝트 엔진",      ws["engine"]["obj_engine"]])
    w.writerow(["== 성능 옵션 =="])
    w.writerow(["batch_size",         ws["performance"]["batch_size"]])
    w.writerow(["parallel_workers",   ws["performance"]["parallel_workers"]])
    w.writerow(["parallel_tables",    ws["performance"]["parallel_tables"]])
    w.writerow(["bulk_mode",          ws["performance"]["bulk_mode"]])
    w.writerow(["bulk_threshold_rows",ws["performance"]["bulk_threshold_rows"]])
    w.writerow(["== MSSQL 튜닝 =="])
    w.writerow(["MSSQL 튜닝",         ws["mssql_tuning"]["enabled"]])
    w.writerow(["인덱스 비활성화",    ws["mssql_tuning"]["disable_indexes"]])
    w.writerow([])

    w.writerow(["=== [3] 종합 판정 ==="])
    w.writerow(["판정",               _verdict_label(vd["overall"])])
    w.writerow(["선택 총계",          vd["total_selected"]])
    w.writerow(["성공 총계",          vd["total_done"]])
    w.writerow(["실패 총계",          vd["total_error"]])
    w.writerow(["성공률(%)",          vd["success_rate"]])
    w.writerow(["── 테이블 ──"])
    w.writerow(["선택/성공/실패/대기/건너뜀/행불일치",
                f'{vd["tables"]["selected"]} / {vd["tables"]["done"]} / '
                f'{vd["tables"]["error"]} / {vd["tables"]["pending"]} / '
                f'{vd["tables"]["skipped"]} / {vd["tables"]["mismatch"]}'])
    for otype, k in [("procedures","Procedure"),("functions","Function"),
                     ("triggers","Trigger"),("views","View")]:
        s2 = vd["objects_by_type"][otype]
        w.writerow([f"── {k} ──"])
        w.writerow([f"선택/성공/실패/대기",
                    f'{s2["selected"]} / {s2["done"]} / {s2["error"]} / {s2["pending"]}'])
    w.writerow(["── 데이터 정합성 ──"])
    di = vd["data_integrity"]
    w.writerow(["소스 행수 합계",     di["rows_src_total"]])
    w.writerow(["타겟 행수 합계",     di["rows_tgt_total"]])
    w.writerow(["차이",               di["rows_diff"]])
    w.writerow(["정합성 판정",        "일치" if di["data_ok"] else "불일치"])
    if di["mismatch_tables"]:
        w.writerow(["행수 불일치 테이블", ", ".join(di["mismatch_tables"])])
    w.writerow([])

    w.writerow(["=== [4] 테이블별 결과 ==="])
    w.writerow(["테이블","상태","판정","소스행수","타겟행수","차이","시작","종료","에러"])
    for t in report["tables_result"]:
        w.writerow([
            t["name"], t["status"], _verdict_label(t["verdict"]),
            t["rows_src"], t["rows_tgt"], t["rows_diff"],
            t["started_at"] or "", t["finished_at"] or "",
            (t["error"] or "")[:200],
        ])
    w.writerow([])

    for otype, k in [("procedures","Procedure"),("functions","Function"),
                     ("triggers","Trigger"),("views","View")]:
        items = report["objects_result"][otype]
        if not items:
            continue
        w.writerow([f"=== [5] {k} 결과 ==="])
        w.writerow(["이름","상태","시작","종료","에러"])
        for o in items:
            w.writerow([
                o["name"], o["status"],
                o["started_at"] or "", o["finished_at"] or "",
                (o["error"] or "")[:200],
            ])
        w.writerow([])

    if report["failures"]:
        w.writerow(["=== [6] 실패 상세 (조치 필요) ==="])
        w.writerow(["구분","이름","에러 메시지"])
        for f in report["failures"]:
            w.writerow([f["category"], f["name"], (f["error"] or "")[:500]])
        w.writerow([])

    if report["unexpected_items"]:
        w.writerow(["=== [7] 위저드 선택 외 항목 (참고) ==="])
        w.writerow(["이름","타입","상태","비고"])
        for u in report["unexpected_items"]:
            w.writerow([u["name"], u["type"], u["status"], u["note"]])

    content = "\uFEFF" + output.getvalue()
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="verify_{job_id[:8]}.csv"'}
    )


@router.get("/export-all")
def export_all(format: str = "csv"):
    """전체 Job 히스토리 내보내기 (요약)"""
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


# ═══════════════════════════════════════════════════════════════════
# 유틸
# ═══════════════════════════════════════════════════════════════════

_VERDICT_LABELS = {
    "success":      "✓ 성공",
    "partial":      "△ 부분 성공",
    "failed":       "✗ 실패",
    "in_progress":  "… 진행 중",
    "no_selection": "– 선택 없음",
    "ok":           "✓ 정합",
    "mismatch":     "△ 행수 불일치",
    "empty":        "○ 빈 테이블",
    "error":        "✗ 실패",
    "skipped":      "– 건너뜀",
    "pending":      "… 대기",
}

def _verdict_label(key: str) -> str:
    return _VERDICT_LABELS.get(key, key)


def _render_html_report(report: dict) -> str:
    """출력/결재용 HTML 리포트."""
    s  = report["summary"]
    ws = report["wizard_selected"]
    vd = report["verdict"]
    di = vd["data_integrity"]

    def esc(v):
        if v is None: return ""
        return (str(v)
                .replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"))

    rows_tbl = []
    for t in report["tables_result"]:
        css = {"ok":"ok","mismatch":"warn","error":"err","empty":"muted",
               "pending":"muted","skipped":"muted"}.get(t["verdict"], "")
        rows_tbl.append(
            f'<tr class="{css}"><td>{esc(t["name"])}</td>'
            f'<td>{esc(_verdict_label(t["verdict"]))}</td>'
            f'<td class="num">{t["rows_src"]:,}</td>'
            f'<td class="num">{t["rows_tgt"]:,}</td>'
            f'<td class="num">{t["rows_diff"]:+,}</td>'
            f'<td>{esc((t.get("error") or "")[:120])}</td></tr>'
        )

    rows_obj = []
    for otype, k in [("procedures","Procedure"),("functions","Function"),
                     ("triggers","Trigger"),("views","View")]:
        for o in report["objects_result"][otype]:
            css = {"done":"ok","error":"err"}.get(o["status"], "muted")
            rows_obj.append(
                f'<tr class="{css}"><td>{esc(k)}</td>'
                f'<td>{esc(o["name"])}</td>'
                f'<td>{esc(o["status"])}</td>'
                f'<td>{esc((o.get("error") or "")[:160])}</td></tr>'
            )

    fail_rows = []
    for f in report["failures"]:
        fail_rows.append(
            f'<tr><td>{esc(f["category"])}</td>'
            f'<td>{esc(f["name"])}</td>'
            f'<td>{esc(f["error"])}</td></tr>'
        )

    overall_label = _verdict_label(vd["overall"])
    overall_css   = {"success":"ok", "partial":"warn",
                     "failed":"err", "in_progress":"muted",
                     "no_selection":"muted"}.get(vd["overall"], "")

    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>DataBridge 이관 검증 리포트 — {esc(s["job_name"])}</title>
<style>
  body {{ font-family: 'Segoe UI', -apple-system, 'Apple SD Gothic Neo', sans-serif;
          max-width: 1100px; margin: 24px auto; padding: 0 20px; color:#222; }}
  h1 {{ margin: 0 0 4px; font-size: 22px; }}
  h2 {{ margin: 24px 0 10px; font-size: 16px; border-bottom: 2px solid #333;
        padding-bottom: 4px; }}
  .sub {{ color:#666; font-size: 13px; margin-bottom: 16px; }}
  .pill {{ display:inline-block; padding:4px 12px; border-radius:14px;
          font-weight:600; font-size:13px; }}
  .pill.ok   {{ background:#d4edda; color:#155724; }}
  .pill.warn {{ background:#fff3cd; color:#856404; }}
  .pill.err  {{ background:#f8d7da; color:#721c24; }}
  .pill.muted {{ background:#e9ecef; color:#495057; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ border: 1px solid #dee2e6; padding: 6px 8px; text-align: left; }}
  th {{ background: #f8f9fa; font-weight: 600; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  tr.ok    td:nth-child(2) {{ color:#155724; font-weight:600; }}
  tr.warn  td:nth-child(2) {{ color:#856404; font-weight:600; }}
  tr.err   td:nth-child(2) {{ color:#721c24; font-weight:600; }}
  tr.muted td {{ color:#6c757d; }}
  .kv {{ display:grid; grid-template-columns: 180px 1fr; gap: 4px 16px; font-size: 13px; }}
  .kv dt {{ color:#555; }}
  .kv dd {{ margin:0; font-weight:500; }}
  .grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap:12px; margin:12px 0; }}
  .card {{ background:#f8f9fa; padding:12px 14px; border-radius:8px;
          border-left: 3px solid #4b78b8; }}
  .card .num {{ font-size:22px; font-weight:700; margin-top:4px; }}
  .card.ok {{ border-left-color:#28a745; }}
  .card.warn {{ border-left-color:#ffc107; }}
  .card.err {{ border-left-color:#dc3545; }}
  @media print {{ body {{ margin: 0; }} .no-print {{ display:none; }} }}
</style></head>
<body>

<h1>DataBridge 이관 검증 리포트</h1>
<div class="sub">생성: {esc(report["generated_at"])} · 리포트 버전 {esc(report["report_version"])}</div>

<h2>[1] 이관 기본 정보</h2>
<dl class="kv">
  <dt>Job 이름</dt><dd>{esc(s["job_name"])}</dd>
  <dt>Job ID</dt><dd style="font-family:monospace">{esc(s["job_id"])}</dd>
  <dt>상태</dt><dd>{esc(s["status"])}</dd>
  <dt>종합 판정</dt><dd><span class="pill {overall_css}">{esc(overall_label)}</span></dd>
  <dt>소스</dt><dd>{esc(s["src_db"])} / {esc(s["src_host"])} / {esc(s["src_database"])}</dd>
  <dt>타겟</dt><dd>{esc(s["tgt_db"])} / {esc(s["tgt_host"])} / {esc(s["tgt_database"])}</dd>
  <dt>시작 → 종료</dt><dd>{esc(s["started_at"])} → {esc(s["finished_at"])} ({esc(s.get("duration_sec"))}초)</dd>
</dl>

<h2>[2] 위저드에서 선택한 옵션</h2>
<div class="grid">
  <div class="card"><div>선택한 테이블</div>
    <div class="num">{ws["scope"]["tables_count"]}</div></div>
  <div class="card"><div>선택한 Procedure</div>
    <div class="num">{ws["scope"]["objects_count"]["procedures"]}</div></div>
  <div class="card"><div>선택한 Function</div>
    <div class="num">{ws["scope"]["objects_count"]["functions"]}</div></div>
  <div class="card"><div>선택한 Trigger</div>
    <div class="num">{ws["scope"]["objects_count"]["triggers"]}</div></div>
  <div class="card"><div>선택한 View</div>
    <div class="num">{ws["scope"]["objects_count"]["views"]}</div></div>
</div>

<h3 style="margin:14px 0 8px; font-size:14px;">이관 방식</h3>
<dl class="kv">
  <dt>테이블 모드</dt><dd>{esc(ws["mode"]["table_mode"])}</dd>
  <dt>오브젝트 모드</dt><dd>{esc(ws["mode"]["obj_mode"])}</dd>
  <dt>뷰 모드</dt><dd>{esc(ws["mode"]["view_mode"])}</dd>
  <dt>타겟 TRUNCATE</dt><dd>{esc(ws["mode"]["truncate_target"])}</dd>
  <dt>CREATE TABLE</dt><dd>{esc(ws["mode"]["create_table"])}</dd>
  <dt>DROP TABLE</dt><dd>{esc(ws["mode"]["drop_table"])}</dd>
  <dt>오브젝트 변환</dt><dd>{esc(ws["mode"]["convert_objects"])}</dd>
  <dt>에러 처리</dt><dd>{esc(ws["mode"]["on_error"])}</dd>
</dl>

<h3 style="margin:14px 0 8px; font-size:14px;">성능·엔진</h3>
<dl class="kv">
  <dt>DDL 엔진</dt><dd>{esc(ws["engine"]["ddl_engine"])}</dd>
  <dt>오브젝트 엔진</dt><dd>{esc(ws["engine"]["obj_engine"])}</dd>
  <dt>batch_size</dt><dd>{ws["performance"]["batch_size"]:,}</dd>
  <dt>parallel_workers</dt><dd>{ws["performance"]["parallel_workers"]}</dd>
  <dt>parallel_tables</dt><dd>{ws["performance"]["parallel_tables"]}</dd>
  <dt>bulk_mode</dt><dd>{esc(ws["performance"]["bulk_mode"])}</dd>
  <dt>bulk_threshold_rows</dt><dd>{ws["performance"]["bulk_threshold_rows"]:,}</dd>
  <dt>MSSQL 튜닝</dt><dd>{esc(ws["mssql_tuning"]["enabled"])} (인덱스 비활성화: {esc(ws["mssql_tuning"]["disable_indexes"])})</dd>
</dl>

<h2>[3] 종합 판정</h2>
<div class="grid">
  <div class="card {overall_css}"><div>종합 판정</div>
    <div class="num">{esc(overall_label)}</div></div>
  <div class="card"><div>선택 총계 → 성공</div>
    <div class="num">{vd["total_selected"]} → {vd["total_done"]}</div></div>
  <div class="card {'ok' if vd['total_error']==0 else 'err'}"><div>실패</div>
    <div class="num">{vd["total_error"]}</div></div>
  <div class="card"><div>성공률</div>
    <div class="num">{vd["success_rate"]}%</div></div>
  <div class="card {'ok' if di['data_ok'] else 'warn'}"><div>데이터 정합성</div>
    <div class="num">{'✓ 일치' if di['data_ok'] else '△ 불일치'}</div></div>
  <div class="card"><div>이관 행수 (소스 / 타겟)</div>
    <div class="num" style="font-size:15px">{di["rows_src_total"]:,} / {di["rows_tgt_total"]:,}</div></div>
</div>

<h2>[4] 테이블별 결과 ({len(report["tables_result"])}개)</h2>
<table>
  <thead><tr><th>테이블</th><th>판정</th><th>소스행수</th><th>타겟행수</th><th>차이</th><th>에러</th></tr></thead>
  <tbody>{"".join(rows_tbl) or '<tr><td colspan="6" class="muted">선택된 테이블 없음</td></tr>'}</tbody>
</table>

<h2>[5] 오브젝트별 결과 ({len(rows_obj)}개)</h2>
<table>
  <thead><tr><th>타입</th><th>이름</th><th>상태</th><th>에러</th></tr></thead>
  <tbody>{"".join(rows_obj) or '<tr><td colspan="4" class="muted">선택된 오브젝트 없음</td></tr>'}</tbody>
</table>
"""

    if fail_rows:
        html += f"""
<h2>[6] 실패 상세 ({len(fail_rows)}건 — 조치 필요)</h2>
<table>
  <thead><tr><th>구분</th><th>이름</th><th>에러 메시지</th></tr></thead>
  <tbody>{"".join(fail_rows)}</tbody>
</table>
"""

    if report["unexpected_items"]:
        unx_rows = "".join(
            f'<tr><td>{esc(u["name"])}</td><td>{esc(u["type"])}</td>'
            f'<td>{esc(u["status"])}</td><td>{esc(u["note"])}</td></tr>'
            for u in report["unexpected_items"]
        )
        html += f"""
<h2>[7] 위저드 선택 외 항목 ({len(report["unexpected_items"])}건 — 참고)</h2>
<table>
  <thead><tr><th>이름</th><th>타입</th><th>상태</th><th>비고</th></tr></thead>
  <tbody>{unx_rows}</tbody>
</table>
"""

    html += """
<div style="margin-top:40px; padding-top:16px; border-top:1px solid #ccc;
            color:#888; font-size:12px; text-align:center;">
  DataBridge — Any DB to Any DB with AI DBA · 이 리포트는 자동 생성되었습니다.
</div>
</body></html>"""
    return html
