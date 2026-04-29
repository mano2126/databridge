"""
app/engine/job_factory.py
Job dict 생성 팩토리.

기존 _new_job 을 그대로 이관. Job 데이터 스키마의 단일 진실 원천 역할.
API 라우터는 이 팩토리로만 Job을 만들어야 한다 — 필드가 누락되면
엔진이 KeyError로 죽는 문제를 예방.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta

_KST = timezone(timedelta(hours=9))


def new_job(jid: str, name: str, src_db: str, tgt_db: str, **kw) -> dict:
    """
    새 Job dict 생성.

    Args:
        jid:    Job ID (uuid)
        name:   표시명
        src_db: 소스 DB 타입 (supported_dbs.py 키)
        tgt_db: 타겟 DB 타입
        **kw:   선택 필드. host/port/database/username/password,
                tables/batch_size/parallel_workers/on_error 등.

    Returns:
        표준화된 Job dict. 상태 필드는 모두 기본값으로 초기화.
    """
    return {
        "id": jid, "name": name,
        "status": "idle",
        "src_db": src_db, "tgt_db": tgt_db,
        "src_host": kw.get("src_host", ""),
        "src_database": kw.get("src_database", ""),
        "tgt_host": kw.get("tgt_host", ""),
        "tgt_database": kw.get("tgt_database", ""),
        "tables": kw.get("tables", []),
        "progress": 0,
        "rows_processed": 0,
        "rows_total": 0,
        "rows_error": 0,
        "speed": 0,
        "table_done": 0,
        "table_total": 0,
        "current_table": "",
        "phase": "INIT",
        "current_table_rows_done": 0,
        "current_table_rows_total": 0,
        "created_at": datetime.now(_KST).isoformat(),
        "started_at": None,
        "finished_at": None,
        "error_message": None,
        "batch_size": kw.get("batch_size", 5000),
        "parallel_workers": kw.get("parallel_workers", 4),
        "on_error": kw.get("on_error", "skip"),
        "truncate_target": kw.get("truncate_target", False),
        "create_table": kw.get("create_table", True),
        "item_statuses": {},   # {name: {type,status,rows,error,started_at,finished_at, checkpoint}}
        "src_username": kw.get("src_username", ""),
        "src_password": kw.get("src_password", ""),
        "tgt_username": kw.get("tgt_username", ""),
        "tgt_password": kw.get("tgt_password", ""),
    }
