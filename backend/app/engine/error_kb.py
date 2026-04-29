"""
DataBridge 에러 프롬프트 지식 베이스 (KB)
============================================
에러 메시지 → 패턴 분류 → AI 프롬프트 지침 주입
성공/실패 피드백을 SQLite 에 누적하여 효과 측정

공개 API:
    from app.engine.error_kb import (
        match_error,          # 에러 메시지 → 매칭된 KB 엔트리 (또는 None)
        assemble_prompt_hint, # Job 의 error_history + KB 엔트리 → 프롬프트용 문자열
        record_attempt,       # 시도 결과 기록 (통계 누적)
        get_stats,            # 전체/패턴별 통계 조회
    )
"""
from __future__ import annotations

import os
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Iterable

try:
    import yaml  # PyYAML
except ImportError:
    yaml = None

# ─────────────────────────────────────────────────────
# 경로
# ─────────────────────────────────────────────────────
_THIS_DIR  = Path(__file__).parent
_KB_PATH   = _THIS_DIR / "error_kb.yml"
_STATS_DB  = Path(os.environ.get(
    "DATABRIDGE_KB_STATS_DB",
    str(_THIS_DIR.parent.parent / "data" / "kb_stats.db")
))

# ─────────────────────────────────────────────────────
# KB 로딩 (프로세스 1회, 필요 시 reload_kb() 로 재로드)
# ─────────────────────────────────────────────────────
_kb_cache: dict = {}       # { pattern_id: entry }
_kb_lock = threading.Lock()
_kb_mtime: float = 0

def _load_kb() -> dict:
    """YAML 파일에서 KB 로드. 파일 수정 시간 변경되면 자동 재로드."""
    global _kb_cache, _kb_mtime
    if not _KB_PATH.exists():
        return {}
    if yaml is None:
        # PyYAML 없으면 KB 비활성화 (기존 동작 유지)
        return {}
    try:
        mtime = _KB_PATH.stat().st_mtime
        if mtime == _kb_mtime and _kb_cache:
            return _kb_cache
        with _KB_PATH.open("r", encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        patterns = (doc.get("patterns") or {})
        # 정규식 미리 컴파일
        out = {}
        for pid, entry in patterns.items():
            if not isinstance(entry, dict):
                continue
            regex = entry.get("regex")
            try:
                entry["_re"] = re.compile(regex, re.IGNORECASE | re.DOTALL) if regex else None
            except re.error:
                entry["_re"] = None
            out[pid] = entry
        with _kb_lock:
            _kb_cache = out
            _kb_mtime = mtime
        return out
    except Exception:
        return _kb_cache or {}

def reload_kb() -> int:
    """수동 재로드. 반환: 로드된 패턴 개수"""
    global _kb_mtime
    _kb_mtime = 0
    return len(_load_kb())

def get_all_patterns() -> dict:
    """모든 패턴 반환 (관리자 UI 용)"""
    return _load_kb()

# ─────────────────────────────────────────────────────
# 패턴 매칭
# ─────────────────────────────────────────────────────
def match_error(error_message: str) -> Optional[dict]:
    """
    에러 메시지를 받아 매칭된 KB 엔트리 반환.
    매칭 없으면 None.
    반환 dict 예:
        {
            "id": "1064_UPDATE_SET_COMMA",
            "error_code": "1064",
            "category": "SYNTAX",
            "cause": "...",
            "fix_type": "prompt_injection",
            "ai_skip": False,          # 있으면 True
            "fix_prompt": "...",        # fix_type == prompt_injection 인 경우
            "fix_config": {...},        # fix_type == config_change 인 경우
            "fix_engine_rule": "...",   # fix_type == engine_rule 인 경우
        }
    """
    if not error_message:
        return None
    patterns = _load_kb()
    for pid, entry in patterns.items():
        rx = entry.get("_re")
        if rx and rx.search(error_message):
            out = dict(entry)
            out["id"] = pid
            out.pop("_re", None)
            return out
    return None

def match_all_errors(errors: Iterable[str]) -> list:
    """여러 에러를 받아 각각 매칭. 중복 패턴은 한 번만."""
    seen = set()
    result = []
    for err in errors:
        ent = match_error(err or "")
        if ent and ent["id"] not in seen:
            seen.add(ent["id"])
            result.append(ent)
    return result

# ─────────────────────────────────────────────────────
# 프롬프트 조립
# ─────────────────────────────────────────────────────
def assemble_prompt_hint(
    current_error: str = "",
    error_history: Optional[list] = None,
) -> str:
    """
    AI 프롬프트에 주입할 '지침 섹션' 생성.
    - current_error 에서 패턴 매칭 → 해당 교정 지침
    - error_history 에 있는 각 시도의 에러도 매칭 → 여러 지침 모두 포함 (중복 제거)
    - Job 내 이전 시도 에러를 자연스럽게 요약

    반환: 프롬프트에 바로 붙일 수 있는 문자열. 매칭이 없으면 빈 문자열.
    """
    error_history = error_history or []

    # 1. 모든 관련 에러 수집
    all_errs = []
    if current_error:
        all_errs.append(current_error)
    for h in error_history:
        if isinstance(h, dict):
            err = h.get("error") or ""
        else:
            err = str(h)
        if err:
            all_errs.append(err)

    # 2. 매칭된 KB 엔트리 수집 (중복 제거)
    matched = match_all_errors(all_errs)

    # 3. 프롬프트 섹션 조립
    sections = []

    # KB 기반 지침
    if matched:
        sections.append("")
        sections.append("=" * 60)
        sections.append("[중요] 다음 패턴이 감지되었습니다. 반드시 주의하세요:")
        sections.append("=" * 60)
        for m in matched:
            # prompt_injection 타입만 AI 프롬프트에 반영
            if m.get("fix_type") == "prompt_injection" and m.get("fix_prompt"):
                sections.append("")
                sections.append(f"▶ 패턴: {m['id']} ({m.get('category','')})")
                sections.append(f"  원인: {m.get('cause','')}")
                sections.append(m["fix_prompt"].strip())

    # Job 내 이전 시도 에러 요약
    if error_history:
        sections.append("")
        sections.append("=" * 60)
        sections.append(f"[이전 시도 기록] 이번 항목은 {len(error_history)}회 시도 후 실패했습니다.")
        sections.append("=" * 60)
        sections.append("아래 에러들을 동일하게 발생시키지 마세요:")
        for i, h in enumerate(error_history, 1):
            if isinstance(h, dict):
                attempt = h.get("attempt", i)
                err = h.get("error", "")
            else:
                attempt = i
                err = str(h)
            # 에러 메시지 300자 제한
            err_short = err[:300] + ("..." if len(err) > 300 else "")
            sections.append(f"  [시도 {attempt}] {err_short}")

    return "\n".join(sections).strip()

# ─────────────────────────────────────────────────────
# 통계 기록 (SQLite)
# ─────────────────────────────────────────────────────
def _ensure_stats_db():
    """SQLite DB 준비"""
    _STATS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_STATS_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kb_attempts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_id      TEXT,
            error_code      TEXT,
            category        TEXT,
            job_id          TEXT,
            item_name       TEXT,
            attempt_num     INTEGER,
            success         INTEGER,
            ai_used         INTEGER,
            prompt_chars    INTEGER,
            ts              TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pattern ON kb_attempts(pattern_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON kb_attempts(ts)")
    conn.commit()
    conn.close()

def record_attempt(
    pattern_id: Optional[str],
    error_code: str = "",
    category: str = "",
    job_id: str = "",
    item_name: str = "",
    attempt_num: int = 1,
    success: bool = False,
    ai_used: bool = False,
    prompt_chars: int = 0,
) -> None:
    """
    시도 결과 기록. 예외를 밖으로 내지 않음 (메인 흐름 방해 금지).
    pattern_id 가 None 이면 "_UNMATCHED_" 로 기록.
    """
    try:
        _ensure_stats_db()
        conn = sqlite3.connect(str(_STATS_DB))
        conn.execute(
            """INSERT INTO kb_attempts
               (pattern_id, error_code, category, job_id, item_name,
                attempt_num, success, ai_used, prompt_chars, ts)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pattern_id or "_UNMATCHED_",
                error_code,
                category,
                job_id,
                item_name,
                attempt_num,
                1 if success else 0,
                1 if ai_used else 0,
                prompt_chars,
                datetime.now().isoformat(timespec="seconds"),
            )
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # 통계 기록 실패는 무시

def get_stats(days: int = 30) -> dict:
    """
    통계 요약. 관리자 UI 용.
    반환:
        {
            "total_attempts": 125,
            "total_success": 89,
            "overall_rate": 0.712,
            "ai_attempts": 98,
            "ai_saved": 27,      # AI 호출 안 한 경우 (config_change / engine_rule)
            "by_pattern": [
                {
                    "pattern_id": "1064_UPDATE_SET_COMMA",
                    "error_code": "1064",
                    "category": "SYNTAX",
                    "attempts": 45, "success": 42, "rate": 0.933,
                    "last_seen": "2026-04-20T18:58:02",
                },
                ...
            ],
            "by_category": { "SYNTAX": {...}, "PERMISSION": {...}, ... }
        }
    """
    try:
        _ensure_stats_db()
        conn = sqlite3.connect(str(_STATS_DB))
        conn.row_factory = sqlite3.Row
        # 전체 카운트
        total = conn.execute(
            "SELECT COUNT(*) AS n, SUM(success) AS s, SUM(ai_used) AS a "
            "FROM kb_attempts WHERE ts >= datetime('now', ?)",
            (f"-{days} days",)
        ).fetchone()
        total_n = total["n"] or 0
        total_s = total["s"] or 0
        ai_a    = total["a"] or 0
        ai_saved = total_n - ai_a   # AI 사용 안 함 = 설정/엔진 규칙 기반

        # 패턴별
        rows = conn.execute(
            """SELECT pattern_id, error_code, category,
                      COUNT(*) AS attempts, SUM(success) AS success, MAX(ts) AS last_seen
               FROM kb_attempts
               WHERE ts >= datetime('now', ?)
               GROUP BY pattern_id, error_code, category
               ORDER BY attempts DESC""",
            (f"-{days} days",)
        ).fetchall()

        by_pattern = []
        for r in rows:
            attempts = r["attempts"] or 0
            success  = r["success"] or 0
            by_pattern.append({
                "pattern_id": r["pattern_id"],
                "error_code": r["error_code"] or "",
                "category":   r["category"]   or "",
                "attempts":   attempts,
                "success":    success,
                "rate":       (success / attempts) if attempts else 0.0,
                "last_seen":  r["last_seen"] or "",
            })

        # 카테고리별
        by_cat = {}
        for r in rows:
            c = r["category"] or "UNKNOWN"
            if c not in by_cat:
                by_cat[c] = {"attempts": 0, "success": 0}
            by_cat[c]["attempts"] += r["attempts"] or 0
            by_cat[c]["success"]  += r["success"] or 0
        for c, v in by_cat.items():
            v["rate"] = (v["success"] / v["attempts"]) if v["attempts"] else 0.0

        conn.close()
        return {
            "total_attempts": total_n,
            "total_success":  total_s,
            "overall_rate":   (total_s / total_n) if total_n else 0.0,
            "ai_attempts":    ai_a,
            "ai_saved":       ai_saved,
            "by_pattern":     by_pattern,
            "by_category":    by_cat,
            "days":           days,
        }
    except Exception as e:
        return {
            "total_attempts": 0, "total_success": 0, "overall_rate": 0.0,
            "ai_attempts": 0, "ai_saved": 0,
            "by_pattern": [], "by_category": {},
            "error": str(e),
        }

def get_unmatched_samples(days: int = 30, limit: int = 20) -> list:
    """
    매칭되지 않은 에러 샘플 (신규 패턴 후보).
    관리자 UI 에서 '새 패턴 후보' 탐색용.
    """
    try:
        _ensure_stats_db()
        conn = sqlite3.connect(str(_STATS_DB))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT job_id, item_name, attempt_num, success, ts
               FROM kb_attempts
               WHERE pattern_id = '_UNMATCHED_'
                 AND ts >= datetime('now', ?)
               ORDER BY ts DESC LIMIT ?""",
            (f"-{days} days", limit)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []
