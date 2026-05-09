"""
v95_p9: 로그 관리 API
- GET  /api/logs/tail        : 최신순 로그 조회 (역순)
- GET  /api/logs/settings    : 회전 설정 조회
- POST /api/logs/settings    : 회전 설정 저장
- POST /api/logs/clear       : 화면 초기화 (현재 로그 백업 후 truncate)
- GET  /api/logs/archives    : 백업 파일 목록
- GET  /api/logs/archive/{name}: 백업 파일 다운로드용 내용
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from pathlib import Path
from datetime import datetime
import os
import logging

from app.core.logging_setup import (
    PRIMARY_LOG,
    ARCHIVE_DIR,
    get_settings,
    save_settings,
    archive_and_clear,
    cleanup_old_archives,
)

router = APIRouter(prefix="/api/logs", tags=["logs"])
logger = logging.getLogger("databridge.logs_api")


class SettingsPayload(BaseModel):
    size_mb: int = Field(..., ge=1, le=5)
    interval_hours: int = Field(..., ge=1, le=24)
    retention_days: int = Field(30, ge=1, le=365)


@router.get("/tail")
def tail_log(
    lines: int = Query(500, ge=10, le=5000),
    level: str = Query("ALL", regex="^(ALL|DEBUG|INFO|WARNING|ERROR|CRITICAL)$"),
    keyword: str = Query("", max_length=200),
):
    """
    최신 lines 줄을 역순(최신 위)으로 반환.
    level/keyword 필터 지원.
    """
    if not PRIMARY_LOG.exists():
        return {"lines": [], "total": 0, "file": str(PRIMARY_LOG)}

    # tail N 효율 (큰 파일 대비) — 역방향 읽기
    rows = _tail_file(str(PRIMARY_LOG), lines)

    # 필터
    if level != "ALL":
        rows = [r for r in rows if f"[{level}]" in r]
    if keyword:
        kw = keyword.lower()
        rows = [r for r in rows if kw in r.lower()]

    # 최신 위 (역순)
    rows.reverse()

    return {
        "lines": rows,
        "total": len(rows),
        "file": str(PRIMARY_LOG),
        "size_kb": round(PRIMARY_LOG.stat().st_size / 1024, 1),
    }


def _tail_file(path: str, n: int):
    """효율적 tail (큰 파일 대비)"""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            block = 8192
            data = b""
            while size > 0 and data.count(b"\n") <= n:
                step = min(block, size)
                size -= step
                f.seek(size)
                data = f.read(step) + data
            text = data.decode("utf-8", errors="replace")
            rows = [r.rstrip("\r") for r in text.splitlines() if r.strip()]
            return rows[-n:]
    except Exception as e:
        logger.warning(f"[tail] 읽기 실패: {e}")
        return []


@router.get("/settings")
def get_log_settings():
    return get_settings()


@router.post("/settings")
def update_log_settings(payload: SettingsPayload):
    saved = save_settings(
        size_mb=payload.size_mb,
        interval_hours=payload.interval_hours,
        retention_days=payload.retention_days,
    )
    logger.info(
        f"[v95_p9] 로깅 설정 변경: size={saved['size_mb']}MB, "
        f"interval={saved['interval_hours']}h, retention={saved['retention_days']}d "
        f"(다음 회전 시 적용)"
    )
    return {"status": "ok", "settings": saved, "note": "다음 회전부터 적용됩니다."}


@router.post("/clear")
def clear_log():
    """
    화면 초기화: 현재 로그를 archive/cleared_*.log 로 백업 후 truncate.
    """
    archive_path = archive_and_clear()
    logger.info(f"[v95_p9] 로그 초기화 (백업: {archive_path})")
    return {
        "status": "ok",
        "archived_to": archive_path,
        "message": "로그가 백업 후 초기화되었습니다.",
    }


@router.get("/archives")
def list_archives():
    """백업 파일 목록 (최신순)"""
    if not ARCHIVE_DIR.exists():
        return {"archives": []}
    files = []
    for f in ARCHIVE_DIR.glob("*.log"):
        try:
            stat = f.stat()
            files.append({
                "name": f.name,
                "size_kb": round(stat.st_size / 1024, 1),
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "modified_ts": stat.st_mtime,
            })
        except Exception:
            continue
    files.sort(key=lambda x: x["modified_ts"], reverse=True)
    for f in files:
        f.pop("modified_ts", None)
    return {"archives": files, "total": len(files)}


@router.get("/archive/{name}")
def get_archive(name: str, lines: int = Query(2000, ge=10, le=10000)):
    """특정 백업 파일 내용 조회 (역순)"""
    # 경로 탈출 방어
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(400, "잘못된 파일명")
    path = ARCHIVE_DIR / name
    if not path.exists() or not path.is_file():
        raise HTTPException(404, f"백업 없음: {name}")

    rows = _tail_file(str(path), lines)
    rows.reverse()
    return {
        "name": name,
        "lines": rows,
        "total": len(rows),
        "size_kb": round(path.stat().st_size / 1024, 1),
    }


@router.post("/cleanup")
def cleanup_archives():
    """수동 보관 정리 (현재 retention_days 기준)"""
    settings = get_settings()
    deleted = cleanup_old_archives(settings["retention_days"])
    return {
        "status": "ok",
        "deleted": deleted,
        "retention_days": settings["retention_days"],
    }
