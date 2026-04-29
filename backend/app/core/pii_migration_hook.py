"""
pii_migration_hook.py — Phase F-1e (2026-04-25)

PII 마스킹을 이관 엔진(migration_engine.py)에 통합하는 비침습적 모듈.

설계 원칙 (중요):
  1. 비침습적: migration_engine 의 _build_mysql_converters 같은 큰 함수를
     직접 수정하지 않고, "converter 체이닝" 으로 외부에서 추가.
  2. Opt-in: Job 에 privacy_decisions 가 있을 때만 작동.
  3. Fail-safe: 마스킹 함수 에러 시 원본 값 보존 (이관 자체는 계속).
  4. 성능 우선: 컬럼별 사전 컴파일 — per-cell 에서는 함수 호출만.

흐름:
    1) Job 시작 시 build_pii_converter_map(privacy_decisions) 호출
       → {column_name: masking_function} 사전 컴파일된 dict 반환
    
    2) 기존 _build_mysql_converters() 결과를
       wrap_converters_with_pii() 로 감쌈
       → 기존 변환 → 그 결과에 PII 마스킹 적용
    
    3) per-row 처리 시 자연스럽게 마스킹된 값으로 INSERT

migration_engine.py 수정 최소화 (3줄):
    # 기존:
    converters = self._build_mysql_converters(cols, col_names)
    
    # 변경:
    converters = self._build_mysql_converters(cols, col_names)
    converters = wrap_converters_with_pii(
        converters, col_names, self.job.get("privacy_decisions", []),
        logger=self._log,
    )
"""

from __future__ import annotations
import logging
from typing import List, Dict, Callable, Optional, Any

try:
    from app.core.pii_masker import (
        PIIMasker, MaskingStrategy, CATEGORY_MASKERS,
    )
    from app.core.pii_detector import PIICategory
except ImportError:
    # 단독 테스트용
    from .pii_masker import PIIMasker, MaskingStrategy, CATEGORY_MASKERS
    from .pii_detector import PIICategory

_log = logging.getLogger("databridge.pii_hook")


# ════════════════════════════════════════════════════════════════════════════
# 메인 API
# ════════════════════════════════════════════════════════════════════════════

def build_pii_converter_map(
    privacy_decisions: List[Dict[str, Any]],
    table_filter: Optional[str] = None,
) -> Dict[str, Callable]:
    """
    privacy_decisions 를 받아 컬럼별 마스킹 함수 dict 빌드.
    
    Args:
        privacy_decisions: [{"table_name": "...", "column_name": "...", 
                             "category": "rrn", "strategy": "partial"}, ...]
        table_filter: 특정 테이블만 필터 (None 이면 전체)
    
    Returns:
        {column_name: masking_function} — 빠른 lookup 용
        masking_function 시그니처: (value) -> masked_value
    
    예시:
        decisions = [
            {"table_name": "customer.profile", "column_name": "rrn",
             "category": "rrn", "strategy": "partial"}
        ]
        masker_map = build_pii_converter_map(decisions, "customer.profile")
        # → {"rrn": <function>}
        
        masked = masker_map["rrn"]("850123-1234567")
        # → "850123-1******"
    """
    masker_map: Dict[str, Callable] = {}
    
    if not privacy_decisions:
        return masker_map
    
    for d in privacy_decisions:
        try:
            table_name = d.get("table_name", "")
            column_name = d.get("column_name", "")
            category_str = d.get("category", "")
            strategy_str = d.get("strategy", "partial")
            
            if not column_name:
                continue
            
            # 테이블 필터
            if table_filter and table_name != table_filter:
                # bare name 으로도 매칭 (스키마 빠진 경우)
                if "." in table_name:
                    bare = table_name.split(".", 1)[1]
                    if bare != table_filter:
                        continue
                else:
                    continue
            
            # KEEP 은 마스킹 안 함 — 함수 등록 자체를 skip
            if strategy_str == "keep":
                continue
            
            # Enum 변환
            try:
                category = PIICategory(category_str)
            except ValueError:
                _log.warning(f"[PII Hook] 알 수 없는 카테고리: {category_str}")
                continue
            
            try:
                strategy = MaskingStrategy(strategy_str)
            except ValueError:
                _log.warning(f"[PII Hook] 알 수 없는 전략: {strategy_str}, partial 사용")
                strategy = MaskingStrategy.PARTIAL
            
            # 마스킹 함수 빌드 (closure)
            masker_func = _build_safe_masker(category, strategy, column_name)
            masker_map[column_name] = masker_func
        
        except Exception as e:
            _log.warning(f"[PII Hook] 정책 빌드 실패: {d} - {e}")
            continue
    
    return masker_map


def wrap_converters_with_pii(
    converters: List[Callable],
    col_names: List[str],
    privacy_decisions: List[Dict[str, Any]],
    table_name: Optional[str] = None,
    logger: Optional[Callable] = None,
) -> List[Callable]:
    """
    기존 converter 리스트에 PII 마스킹을 체이닝.
    
    기존:  raw_value → converter(타입변환) → DB
    변경:  raw_value → converter(타입변환) → masking → DB
    
    Args:
        converters: _build_mysql_converters() 결과
        col_names: 컬럼명 리스트 (converters 와 같은 순서)
        privacy_decisions: Job 의 privacy_decisions
        table_name: 현재 처리 중인 테이블명 (필터용)
        logger: 로그 함수 (self._log)
    
    Returns:
        새로운 converter 리스트 (PII 마스킹 적용된 것)
    """
    if not privacy_decisions:
        return converters  # 마스킹 없음 — 원본 그대로
    
    masker_map = build_pii_converter_map(privacy_decisions, table_name)
    
    if not masker_map:
        return converters  # 이 테이블에는 마스킹 컬럼 없음
    
    # 어느 컬럼이 마스킹되는지 로그
    masked_cols = [c for c in col_names if c in masker_map]
    if masked_cols and logger:
        logger("info", f"[Phase F-1e] {table_name or '(table)'} 마스킹 적용: {masked_cols}")
    
    # 새 converter 리스트 생성
    new_converters = []
    for i, name in enumerate(col_names):
        original_conv = converters[i] if i < len(converters) else (lambda v: v)
        masker = masker_map.get(name)
        
        if masker is None:
            # 마스킹 안 함 — 원본 converter 그대로
            new_converters.append(original_conv)
        else:
            # 체이닝: 원본 converter 후 마스킹
            new_converters.append(_chain(original_conv, masker))
    
    return new_converters


# ════════════════════════════════════════════════════════════════════════════
# 내부 유틸리티
# ════════════════════════════════════════════════════════════════════════════

def _build_safe_masker(
    category: PIICategory,
    strategy: MaskingStrategy,
    column_name: str,
) -> Callable[[Any], Any]:
    """
    안전한 마스킹 함수 생성 (에러 시 원본 보존).
    
    이관 도중 마스킹 에러 = 그 row 만 실패해도 안 됨.
    원본 값 그대로 보존하고 로그만 남김.
    """
    base_masker = CATEGORY_MASKERS.get(category)
    
    if base_masker is None:
        # 매핑 없는 카테고리 → fallback 마스킹
        def masker(value):
            if value is None:
                return None
            try:
                return PIIMasker._fallback_mask(str(value), strategy)
            except Exception:
                return value
        return masker
    
    # 정상 path
    def masker(value):
        if value is None:
            return None
        try:
            return base_masker(str(value), strategy)
        except Exception as e:
            # 에러 시 원본 보존 (이관 자체는 계속)
            _log.debug(f"[PII Hook] {column_name} 마스킹 실패 (값 보존): {e}")
            return value
    
    return masker


def _chain(first_fn: Callable, second_fn: Callable) -> Callable:
    """두 함수 체이닝: 첫 번째 결과를 두 번째에 전달"""
    def chained(value):
        return second_fn(first_fn(value))
    return chained


# ════════════════════════════════════════════════════════════════════════════
# 통계 / 디버깅 헬퍼
# ════════════════════════════════════════════════════════════════════════════

def summarize_pii_hooks(
    privacy_decisions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    이관 시작 전 마스킹 적용 요약 (로그/리포트용).
    
    Returns:
        {
            "total_decisions": 5,
            "by_table": {"customer.profile": 3, "credit.contract": 2},
            "by_strategy": {"partial": 4, "hash": 1},
            "by_category": {"rrn": 1, "email": 2, ...}
        }
    """
    if not privacy_decisions:
        return {
            "total_decisions": 0,
            "by_table": {},
            "by_strategy": {},
            "by_category": {},
        }
    
    by_table: Dict[str, int] = {}
    by_strategy: Dict[str, int] = {}
    by_category: Dict[str, int] = {}
    
    active_decisions = [d for d in privacy_decisions
                       if d.get("strategy") != "keep"]
    
    for d in active_decisions:
        t = d.get("table_name", "(unknown)")
        s = d.get("strategy", "(unknown)")
        c = d.get("category", "(unknown)")
        by_table[t] = by_table.get(t, 0) + 1
        by_strategy[s] = by_strategy.get(s, 0) + 1
        by_category[c] = by_category.get(c, 0) + 1
    
    return {
        "total_decisions": len(active_decisions),
        "by_table": by_table,
        "by_strategy": by_strategy,
        "by_category": by_category,
    }
