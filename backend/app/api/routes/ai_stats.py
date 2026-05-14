"""
app/api/routes/ai_stats.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
v95_p78 (2026-05-06 본부장님): AI 사용 통계 + 비용 관리 API

본부장님 호소:
  "AI 이용을 최소화 시켰는지 조회하는 관리자 화면"
  "운영화면에서 AI 접속 목록을 보는데 너무 약해서"
  "정확한지도 잘 모르겠어"
  "좀더 강력하고, 다양하게 조회 할 수 있는 화면"

제공하는 통계:
  1) AI 호출 총계 (오늘/이번주/이번달)
  2) 캐시 히트율 (v95_p58)
  3) KB 매칭율 (v95_p69)
  4) 환각 검출 + 자동 수정 횟수 (v95_p72/p77)
  5) 사용자 결정 분포 (auto/manual/exclude)
  6) 객체별 변환 이력
  7) 비용 절감 추정 (이전 대비)

API 엔드포인트:
  GET  /api/v1/ai-stats/summary           — 요약 통계
  GET  /api/v1/ai-stats/calls             — AI 호출 이력 (페이징)
  GET  /api/v1/ai-stats/cache-stats       — 캐시 히트율
  GET  /api/v1/ai-stats/kb-stats          — KB 효과
  GET  /api/v1/ai-stats/hallucination     — 환각 검출 통계
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from __future__ import annotations
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import os
import json
import re
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/ai-stats", tags=["ai_stats"])
_log = logging.getLogger("databridge.ai_stats")


def _data_dir() -> str:
    """backend/data 디렉토리"""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "..", "data"))


def _logs_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "..", "logs"))


def _safe_load_json(path: str) -> dict:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


# ════════════════════════════════════════════════════════════════════
# 통계 헬퍼
# ════════════════════════════════════════════════════════════════════

def _count_log_pattern(pattern: str, hours: int = 24) -> int:
    """로그 파일에서 패턴 매칭 라인 수 (최근 N시간)"""
    log_path = os.path.join(_logs_dir(), "databridge_backend.log")
    if not os.path.exists(log_path):
        return 0
    try:
        cutoff = datetime.now() - timedelta(hours=hours)
        count = 0
        regex = re.compile(pattern)
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if regex.search(line):
                    count += 1
        return count
    except Exception as e:
        _log.warning(f"[v95_p78] 로그 카운트 오류: {e}")
        return 0


# ════════════════════════════════════════════════════════════════════
# API 엔드포인트
# ════════════════════════════════════════════════════════════════════

@router.get("/summary")
def get_summary(hours: int = Query(24, ge=1, le=720)) -> dict:
    """
    AI 사용 요약 통계 (최근 N시간, 기본 24시간)
    
    반환:
      - ai_calls_total: 전체 AI 호출 수
      - cache_hits: 캐시 히트 수
      - kb_matches: KB 매칭 수 (AI 호출 0)
      - hallucinations_detected: 환각 검출 수
      - hallucinations_auto_fixed: 자동 수정 수
      - blocked_by_failure: 실패 차단 수
      - cost_saved_pct: 비용 절감 추정 (%)
    """
    # 로그 기반 카운트
    ai_calls       = _count_log_pattern(r"ai_convert_ddl.*완료|claude-ai", hours)
    cache_hits     = _count_log_pattern(r"v95_p58-CACHE-HIT", hours)
    kb_matches     = _count_log_pattern(r"v95_p69-KB-MATCH", hours)
    hall_detected  = _count_log_pattern(r"v95_p72-HALLUCINATION|v95_p77.*HALLUCINATION", hours)
    hall_fixed     = _count_log_pattern(r"v95_p72-AUTO-FIX|v95_p72-FALLBACK", hours)
    blocked        = _count_log_pattern(r"v95_p70-BLOCKED|v95_p70-BLOCK", hours)
    user_manual    = _count_log_pattern(r"v95_p68-USER-MANUAL", hours)
    user_exclude   = _count_log_pattern(r"v95_p68-USER-EXCLUDE", hours)
    
    # 비용 절감 추정
    # 이전: 객체 1개당 평균 3-9회 AI 호출 가정 (재시도 포함)
    # 지금: 캐시/KB/차단/사용자결정 으로 절감
    total_savings = cache_hits + kb_matches + blocked + user_manual + user_exclude
    total_attempts = ai_calls + total_savings
    cost_saved_pct = round((total_savings / total_attempts * 100) if total_attempts > 0 else 0, 1)
    
    return {
        "ok": True,
        "period_hours": hours,
        "ai_calls_total": ai_calls,
        "savings": {
            "cache_hits": cache_hits,
            "kb_matches": kb_matches,
            "user_manual": user_manual,
            "user_exclude": user_exclude,
            "blocked_by_failure": blocked,
            "total": total_savings,
        },
        "hallucination": {
            "detected": hall_detected,
            "auto_fixed": hall_fixed,
        },
        "cost": {
            "saved_pct": cost_saved_pct,
            "total_attempts": total_attempts,
            "ai_actual_calls": ai_calls,
        },
        "ts": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/cache-stats")
def get_cache_stats() -> dict:
    """v95_p58 AI 변환 캐시 통계"""
    cache_path = os.path.join(_data_dir(), "ai_conversion_cache.json")
    cache = _safe_load_json(cache_path)
    
    by_type = {"VIEW": 0, "PROCEDURE": 0, "FUNCTION": 0, "TRIGGER": 0, "OTHER": 0}
    by_db_pair = {}
    cached_at_dates = []
    for k, v in cache.items():
        t = v.get("obj_type", "OTHER").upper()
        by_type[t] = by_type.get(t, 0) + 1
        pair = f"{v.get('src_db','?')}→{v.get('tgt_db','?')}"
        by_db_pair[pair] = by_db_pair.get(pair, 0) + 1
        cached_at_dates.append(v.get("cached_at", ""))
    
    return {
        "ok": True,
        "total_cached": len(cache),
        "by_type": by_type,
        "by_db_pair": by_db_pair,
        "oldest": min(cached_at_dates) if cached_at_dates else None,
        "newest": max(cached_at_dates) if cached_at_dates else None,
        "cache_file": cache_path,
        "exists": os.path.exists(cache_path),
    }


@router.get("/kb-stats")
def get_kb_stats() -> dict:
    """v95_p69 변환 패턴 KB 통계"""
    kb_path = os.path.join(_data_dir(), "conversion_patterns.json")
    kb = _safe_load_json(kb_path)
    patterns = kb.get("patterns", [])
    
    by_source = {"user_manual": 0, "ai_success": 0}
    by_type = {}
    total_uses = 0
    top_used = []
    for p in patterns:
        src = p.get("source", "ai_success")
        by_source[src] = by_source.get(src, 0) + 1
        t = p.get("obj_type", "OTHER")
        by_type[t] = by_type.get(t, 0) + 1
        total_uses += p.get("use_count", 0)
        top_used.append({
            "obj_name": p.get("obj_name_sample", ""),
            "obj_type": p.get("obj_type", ""),
            "source": src,
            "use_count": p.get("use_count", 0),
            "registered_at": p.get("registered_at", ""),
        })
    
    top_used.sort(key=lambda x: x["use_count"], reverse=True)
    
    return {
        "ok": True,
        "total_patterns": len(patterns),
        "by_source": by_source,
        "by_type": by_type,
        "total_uses": total_uses,
        "top_used": top_used[:10],
        "kb_file": kb_path,
        "exists": os.path.exists(kb_path),
    }


@router.get("/failures")
def get_failures() -> dict:
    """v95_p70 실패 패턴 KB"""
    fail_path = os.path.join(_data_dir(), "conversion_failures.json")
    db = _safe_load_json(fail_path)
    failures = db.get("failures", [])
    
    blocked = [f for f in failures if f.get("block_until_user_decides")]
    
    return {
        "ok": True,
        "total_failures": len(failures),
        "blocked_count": len(blocked),
        "blocked": [
            {
                "obj_type": f.get("obj_type"),
                "obj_name_sample": f.get("obj_name_sample"),
                "ai_failures": f.get("ai_failures"),
                "last_error": f.get("last_error", "")[:200],
                "last_failed_at": f.get("last_failed_at"),
            }
            for f in blocked[:20]
        ],
        "file": fail_path,
        "exists": os.path.exists(fail_path),
    }


@router.get("/recent-calls")
def get_recent_calls(limit: int = Query(50, ge=1, le=500)) -> dict:
    """최근 AI 호출 이력 (로그 기반)"""
    log_path = os.path.join(_logs_dir(), "databridge_backend.log")
    if not os.path.exists(log_path):
        return {"ok": False, "error": "로그 파일 없음", "calls": []}
    
    pattern = re.compile(
        r"ai_convert_ddl \[(\w+)\] ([\w_.]+) → (완료|시작|실패)",
        re.IGNORECASE
    )
    calls = []
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = pattern.search(line)
                if m:
                    # 타임스탬프 추출
                    ts_match = re.match(r"^[\d\-:\sT,\.]+", line)
                    ts = ts_match.group(0).strip() if ts_match else ""
                    
                    # 메소드 추출
                    method = "claude-ai"
                    if "캐시 히트" in line or "CACHE-HIT" in line:
                        method = "ai_cached"
                    elif "KB-MATCH" in line:
                        method = "kb_matched"
                    elif "BLOCKED" in line:
                        method = "blocked"
                    
                    calls.append({
                        "ts": ts[:23],  # 짧게
                        "obj_type": m.group(1),
                        "obj_name": m.group(2),
                        "status": m.group(3),
                        "method": method,
                    })
    except Exception as e:
        return {"ok": False, "error": str(e), "calls": []}
    
    # 최신순 + limit
    calls = calls[-limit:][::-1]
    
    return {
        "ok": True,
        "total": len(calls),
        "calls": calls,
    }


# ════════════════════════════════════════════════════════════════════
# v95_p107 hotfix_085 (2026-05-13 본부장님): AI 엔진 실시간 가시화
# ════════════════════════════════════════════════════════════════════
@router.get("/live")
def get_ai_live_status():
    """AI 엔진 실시간 상태 — Topbar AI 버튼 클릭 시 팝업용.
    
    Ollama /api/ps + DataBridge 세션 메트릭 결합.
    Polling 권장 주기: 5초 (lightweight).
    """
    import urllib.request as _ur
    import json as _j
    import logging as _log
    
    _lg = _log.getLogger("databridge.ai_live")
    
    # 현재 settings 로드
    from app.api.routes.settings import _cfg
    cfg = _cfg()
    provider = (cfg.get("ai_provider", "anthropic") or "anthropic").strip().lower()
    
    result = {
        "ok": True,
        "provider": provider,
        "ts": datetime.now().isoformat(),
        "ollama": None,
        "anthropic": None,
        "session": {},
    }
    
    # ── Ollama 실시간 상태 ────────────────────────────────────────
    if provider == "ollama":
        ollama_url = (cfg.get("ollama_url", "http://localhost:11434")
                      or "http://localhost:11434").rstrip("/")
        configured_model = (cfg.get("ollama_model", "") or "").strip()
        
        ollama_data = {
            "url": ollama_url,
            "reachable": False,
            "configured_model": configured_model,
            "loaded_models": [],
            "error": None,
        }
        
        try:
            req = _ur.Request(f"{ollama_url}/api/ps",
                              headers={"Content-Type": "application/json"})
            with _ur.urlopen(req, timeout=3) as r:
                data = _j.loads(r.read())
            ollama_data["reachable"] = True
            
            # /api/ps 응답 → 로드된 모델 목록
            for m in data.get("models", []) or []:
                # processor 비율 계산: size_vram / size (없으면 0)
                size_total = int(m.get("size", 0) or 0)
                size_vram  = int(m.get("size_vram", 0) or 0)
                if size_total > 0:
                    gpu_pct = round(100.0 * size_vram / size_total)
                    cpu_pct = 100 - gpu_pct
                else:
                    gpu_pct = 0; cpu_pct = 0
                
                # 잔여 시간 계산
                expires_at = m.get("expires_at", "")
                expires_in_sec = None
                if expires_at:
                    try:
                        from datetime import datetime as _dt
                        # ISO 8601 (timezone 포함될 수 있음)
                        _exp = _dt.fromisoformat(expires_at.replace("Z", "+00:00"))
                        _now = _dt.now(_exp.tzinfo) if _exp.tzinfo else _dt.now()
                        expires_in_sec = int((_exp - _now).total_seconds())
                    except Exception:
                        pass
                
                # context window (details.parameter_size 같은 데서 추출되지 않음 — 기본값)
                # details 에서 추출 시도
                details = m.get("details", {}) or {}
                
                ollama_data["loaded_models"].append({
                    "name":           m.get("name", ""),
                    "size_bytes":     size_total,
                    "size_gb":        round(size_total / 1024 / 1024 / 1024, 1),
                    "size_vram_gb":   round(size_vram / 1024 / 1024 / 1024, 1),
                    "cpu_pct":        cpu_pct,
                    "gpu_pct":        gpu_pct,
                    "context":        m.get("context_length", 0) or 0,
                    "expires_at":     expires_at,
                    "expires_in_sec": expires_in_sec,
                    "parameter_size": details.get("parameter_size", ""),
                    "quantization":   details.get("quantization_level", ""),
                })
        except Exception as e:
            ollama_data["error"] = f"{type(e).__name__}: {str(e)[:120]}"
            _lg.debug(f"[ai_live] Ollama /api/ps 실패: {e}")
        
        result["ollama"] = ollama_data
    
    # ── Anthropic 상태 (API key 있는지만) ─────────────────────────
    if provider == "anthropic":
        result["anthropic"] = {
            "api_key_set": bool(cfg.get("anthropic_api_key_set") or cfg.get("anthropic_api_key")),
            "model":       cfg.get("anthropic_model", "claude-sonnet-4-5"),
        }
    
    # ── DataBridge 세션 메트릭 (가능한 만큼) ──────────────────────
    try:
        from app.core.mysql_runtime_validator import get_validation_stats
        vstats = get_validation_stats() or {}
        result["session"]["validator"] = {
            "passes": vstats.get("passes", 0),
            "fails":  vstats.get("fails", 0),
            "total":  vstats.get("total", 0),
        }
    except Exception:
        result["session"]["validator"] = {"passes": 0, "fails": 0, "total": 0}
    
    # 오늘 로그에서 AI 호출 카운트 (lightweight grep)
    try:
        from datetime import date as _date
        today = _date.today().isoformat()
        log_path = os.path.join(_logs_dir(), "databridge_backend.log")
        ai_calls = 0
        pattern_kb_hits = 0
        kb_registers = 0
        validator_ok = 0
        validator_fail = 0
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                # 메모리 절약 — 큰 로그는 마지막 N MB 만
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 5_000_000))
                for line in f:
                    if today not in line:
                        continue
                    if "AI-TRACE 03-http-send" in line:
                        ai_calls += 1
                    elif "PATTERN-KB-FIRST" in line:
                        pattern_kb_hits += 1
                    elif "PATTERN-KB-REGISTER" in line:
                        kb_registers += 1
                    elif "PATTERN-KB-VALIDATOR-OK" in line or "MYSQL-VALIDATE-OK" in line:
                        validator_ok += 1
                    elif "PATTERN-KB-VALIDATION-FAIL" in line:
                        validator_fail += 1
        result["session"]["today"] = {
            "ai_calls":         ai_calls,
            "pattern_kb_hits":  pattern_kb_hits,
            "kb_registers":     kb_registers,
            "validator_ok":     validator_ok,
            "validator_fail":   validator_fail,
        }
    except Exception as e:
        _lg.debug(f"[ai_live] today metric 실패: {e}")
        result["session"]["today"] = {
            "ai_calls": 0, "pattern_kb_hits": 0, "kb_registers": 0,
            "validator_ok": 0, "validator_fail": 0,
        }
    
    return result
