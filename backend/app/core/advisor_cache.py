"""
app/core/advisor_cache.py — AI DBA Advisor 분석 결과 캐시 (v95_p18_cache 신규, 2026-05-03)
═══════════════════════════════════════════════════════════════════════

본부장님 본질 처방 (2026-05-03):
  "매번 이렇게 비용을 들여야 되는거야? 처음에 한번 전체를 하고 나면 
   기록했다가 전체 이관할때는 그대로 쓰면 안돼?"

본부장님 원칙 (하드코딩 절대 금지):
  - 캐시 키 = SHA256(src_db + tgt_db + mode + sorted(selection) + database)
  - 어떤 DB든 동일 (AdventureWorks/Northwind/WideWorldImporters 모두 작동)
  - DB 이름/테이블 이름 박혀있음 0%

설계:
  - 저장 위치: backend/cache/advisor_analysis/{cache_key}.json
  - 키 입력: src_db_type + tgt_db_type + mode + 선택 객체 (정렬) + 실제 database 이름
  - 결정론: 같은 입력 → 같은 키 → 같은 결과
  - 만료: 기본 7일 (config 가능, 향후 v95_p19 의제)
  - 재시도: 캐시 파일 손상 시 자동으로 새 분석 (안전)

엔드포인트 통합:
  - /advisor/analyze: 캐시 조회 → hit 면 반환, miss 면 새 분석 후 저장
  - body 의 use_cache=False 면 강제 새 분석
  - 응답에 from_cache + cached_at 포함 (UI 입증 표시용)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("databridge.advisor_cache")


# ═══════════════════════════════════════════════════════════════════════
# 캐시 디렉토리 자동 결정
# ═══════════════════════════════════════════════════════════════════════
def _resolve_cache_dir() -> Path:
    """캐시 디렉토리 위치 결정.
    
    환경변수 ADVISOR_CACHE_DIR 우선 → 없으면 backend/cache/advisor_analysis
    """
    env = os.environ.get("ADVISOR_CACHE_DIR", "").strip()
    if env:
        p = Path(env)
    else:
        # backend/app/core/advisor_cache.py 기준 → backend/cache/advisor_analysis
        here = Path(__file__).resolve()
        # here = backend/app/core/advisor_cache.py
        # → backend = here.parent.parent.parent
        backend_root = here.parent.parent.parent
        p = backend_root / "cache" / "advisor_analysis"
    
    p.mkdir(parents=True, exist_ok=True)
    return p


CACHE_DIR = _resolve_cache_dir()
DEFAULT_TTL_DAYS = 7  # 기본 유효기간 (향후 설정 가능)


# ═══════════════════════════════════════════════════════════════════════
# 캐시 키 산출 — 본부장님 원칙 (하드코딩 X)
# ═══════════════════════════════════════════════════════════════════════
def compute_cache_key(
    src_db: str,
    tgt_db: str,
    mode: str,
    selection: dict,
    src_database: str = "",
    src_host: str = "",
) -> str:
    """결정론적 캐시 키 산출.
    
    같은 (DB 종류 + DB 이름 + 호스트 + 모드 + 선택 객체) 조합 = 같은 키.
    어떤 표준 DB든 일반 처방 (AdventureWorks/Northwind/WideWorldImporters 모두 작동).
    
    Args:
        src_db: 소스 DB 종류 (mssql/mysql/...)
        tgt_db: 타겟 DB 종류
        mode: 분석 모드 (smart/hybrid/deep)
        selection: {tables: [...], procedures: [...], functions: [...], 
                    triggers: [...], views: [...]}
        src_database: 실제 소스 DB 이름 (AdventureWorks2022 등) — 같은 DB명도 식별
        src_host: 소스 호스트 (다른 환경 구분용)
    
    Returns:
        SHA256 해시 (64자 hex)
    """
    # 정규화: 공백 제거 + 소문자 통일
    norm = {
        "src_db":      (src_db or "").strip().lower(),
        "tgt_db":      (tgt_db or "").strip().lower(),
        "mode":        (mode or "smart").strip().lower(),
        "src_database": (src_database or "").strip().lower(),
        "src_host":    (src_host or "").strip().lower(),
        "tables":      sorted([str(x).strip() for x in (selection.get("tables") or [])]),
        "procedures":  sorted([str(x).strip() for x in (selection.get("procedures") or [])]),
        "functions":   sorted([str(x).strip() for x in (selection.get("functions") or [])]),
        "triggers":    sorted([str(x).strip() for x in (selection.get("triggers") or [])]),
        "views":       sorted([str(x).strip() for x in (selection.get("views") or [])]),
    }
    
    # JSON 직렬화 후 SHA256
    serialized = json.dumps(norm, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# ═══════════════════════════════════════════════════════════════════════
# 캐시 조회 / 저장
# ═══════════════════════════════════════════════════════════════════════
def get_cached_analysis(cache_key: str, ttl_days: int = DEFAULT_TTL_DAYS) -> Optional[dict]:
    """캐시 조회. 적중 시 결과, 만료 또는 미존재 시 None.
    
    Args:
        cache_key: compute_cache_key 로 산출된 키
        ttl_days: 유효기간 (일). 기본 7일.
    
    Returns:
        캐시 데이터 dict 또는 None
    """
    cache_path = CACHE_DIR / f"{cache_key}.json"
    if not cache_path.exists():
        return None
    
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 만료 검사
        cached_at_str = data.get("cached_at")
        if cached_at_str:
            try:
                cached_at = datetime.fromisoformat(cached_at_str)
                age = datetime.now() - cached_at
                if age > timedelta(days=ttl_days):
                    logger.info(
                        "[advisor_cache] expired key=%s age=%dd", 
                        cache_key[:12], age.days
                    )
                    return None
            except ValueError:
                # 시각 파싱 실패 — 손상된 캐시로 간주
                logger.warning("[advisor_cache] invalid cached_at: %s", cached_at_str)
                return None
        
        logger.info("[advisor_cache] HIT key=%s cached_at=%s", 
                    cache_key[:12], cached_at_str)
        return data
    
    except (json.JSONDecodeError, IOError, OSError) as e:
        logger.warning("[advisor_cache] read failed key=%s: %s", cache_key[:12], e)
        return None


def save_analysis_to_cache(
    cache_key: str,
    analysis_result: dict,
    metadata: Optional[dict] = None,
) -> bool:
    """분석 결과를 캐시에 저장.
    
    Args:
        cache_key: 캐시 키
        analysis_result: /advisor/analyze 응답 본문
        metadata: 선택적 메타데이터 (DB 이름, 선택 객체 수 등 — 디버깅용)
    
    Returns:
        성공 여부
    """
    cache_path = CACHE_DIR / f"{cache_key}.json"
    
    try:
        payload = {
            "cached_at":   datetime.now().isoformat(),
            "cache_key":   cache_key,
            "metadata":    metadata or {},
            "analysis":    analysis_result,
        }
        
        # 임시 파일 후 rename (atomic write)
        tmp_path = cache_path.with_suffix(".json.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        tmp_path.replace(cache_path)
        
        logger.info(
            "[advisor_cache] SAVED key=%s size=%d", 
            cache_key[:12], cache_path.stat().st_size
        )
        return True
    
    except (IOError, OSError) as e:
        logger.error("[advisor_cache] save failed key=%s: %s", cache_key[:12], e)
        return False


def invalidate_cache(cache_key: str) -> bool:
    """특정 캐시 삭제."""
    cache_path = CACHE_DIR / f"{cache_key}.json"
    try:
        if cache_path.exists():
            cache_path.unlink()
            logger.info("[advisor_cache] invalidated key=%s", cache_key[:12])
            return True
    except OSError as e:
        logger.error("[advisor_cache] invalidate failed: %s", e)
    return False


def list_cached_analyses() -> list[dict]:
    """모든 캐시 항목 메타 정보 목록 (관리/디버깅용)."""
    items = []
    for p in CACHE_DIR.glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            items.append({
                "cache_key":   data.get("cache_key", p.stem),
                "cached_at":   data.get("cached_at"),
                "metadata":    data.get("metadata", {}),
                "size_bytes":  p.stat().st_size,
            })
        except Exception:
            continue
    items.sort(key=lambda x: x.get("cached_at") or "", reverse=True)
    return items


def clear_all_cache() -> int:
    """모든 캐시 삭제. 삭제된 파일 수 반환."""
    count = 0
    for p in CACHE_DIR.glob("*.json"):
        try:
            p.unlink()
            count += 1
        except OSError:
            pass
    logger.info("[advisor_cache] cleared all (%d files)", count)
    return count


# ═══════════════════════════════════════════════════════════════════════
# 헬퍼 — analysis result 의 최소 검증
# ═══════════════════════════════════════════════════════════════════════
def is_valid_analysis(result: dict) -> bool:
    """캐시 가능한 분석 결과인지 검증.
    
    빈 결과나 에러만 있는 결과는 캐시하지 않음.
    """
    if not isinstance(result, dict):
        return False
    if not result.get("recommendations"):
        # 권고가 0개면 캐시 안 함 (다음에 재분석 기회 부여)
        return False
    return True
