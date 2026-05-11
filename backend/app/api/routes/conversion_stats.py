"""
DataBridge 변환 엔진 통계 API — hotfix_021 가시성 페이지용
============================================================

본부장님 결정 (2026-05-10):
  "관리자 화면의 KB 메뉴 아래에 SQLGlot 관련 호출 횟수와
   어떻게 도움 받았고, 또 어떻게 우리 KB 에서 수용 시켰는지
   상세히 볼 수 있는 페이지 하나 만들어서"

엔드포인트:
  GET /api/v1/conversion-stats/summary       — Layer 별 사용 비율, 시간별 추이
  GET /api/v1/conversion-stats/sqlglot       — SQLGlot 호출 상세 (성공/실패, 흡수율)
  GET /api/v1/conversion-stats/rule-engine   — Rule Engine 누적 통계
  GET /api/v1/conversion-stats/ai-providers  — Provider 별 사용 + 성공률
  GET /api/v1/conversion-stats/recent        — 최근 변환 N건 상세
  
  GET /api/v1/ai-providers/list              — 지원 Provider 목록 (관리자 dropdown)
  GET /api/v1/ai-providers/current           — 현재 활성 Provider 설정
  POST /api/v1/ai-providers/set-default      — 기본 Provider 변경
  POST /api/v1/ai-providers/set-by-obj-type  — 객체 타입별 모델 변경

골격 상태 (2026-05-10):
  - 라우트 정의 완성 (모두 stub 응답)
  - Phase 4 (다음 세션) 에서 실제 데이터 집계 + 응답 채움
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import logging

_log = logging.getLogger("databridge.api.conversion_stats")

router = APIRouter(prefix="/api/v1/conversion-stats", tags=["conversion-stats"])
provider_router = APIRouter(prefix="/api/v1/ai-providers", tags=["ai-providers"])


# ════════════════════════════════════════════════════════════
# 변환 통계 (KB 메뉴 → 변환 엔진 활용 현황 페이지)
# ════════════════════════════════════════════════════════════

@router.get("/summary")
def get_summary(
    period: str = Query("7d", description="기간: 1h, 24h, 7d, 30d, all"),
):
    """Layer 별 사용 비율 + 시간별 추이.

    Phase 4 구현:
      - store_conversion_stats 에서 기간 필터링 집계
      - {kb: 87%, rule: 5%, sqlglot: 3%, ai: 5%} 같은 비율
      - 시간별 시계열 (Chart.js 용)
    """
    return {
        "period": period,
        "layer_distribution": {
            "kb": 0,
            "rule": 0,
            "sqlglot": 0,
            "ai": 0,
        },
        "total_conversions": 0,
        "total_elapsed_ms": 0,
        "ai_call_count": 0,
        "ai_call_saved": 0,  # KB+Rule+SQLGlot 으로 절약된 AI 호출
        "time_series": [],   # [{ts, kb, rule, sqlglot, ai}]
        "_status": "skeleton",  # Phase 4 까지 골격
    }


@router.get("/sqlglot")
def get_sqlglot_stats(period: str = Query("7d")):
    """SQLGlot 호출 상세.

    핵심 지표 (본부장님 의존성 우려 모니터링):
      - 호출 횟수
      - 성공/실패 비율
      - dialect 쌍별 성공률
      - Rule Engine 흡수율 (몇 % 가 영구 자산화)
      - 시간 추이 (감소해야 정상)
    """
    return {
        "period": period,
        "total_calls": 0,
        "success_rate": 0.0,
        "by_dialect_pair": {},      # {"tsql->mysql": {calls: N, success: M}}
        "rule_absorption_rate": 0.0,  # ⭐ 의존성 감소 핵심 지표
        "absorbed_count": 0,
        "recent_calls": [],         # 최근 호출 상세 (입력/출력/검증결과)
        "version": "n/a",
        "_status": "skeleton",
    }


@router.get("/rule-engine")
def get_rule_engine_stats():
    """Rule Engine 누적 통계.

    본부장님 모토 정면 — 자산 누적 가시화:
      - 카테고리별 규칙 수
      - 가장 많이 쓰인 규칙 Top 10
      - 시간별 누적 그래프
      - SQLGlot 으로부터 학습한 규칙 비율
    """
    try:
        from app.core.rule_engine import RuleEngine
        engine = RuleEngine()
        stats = engine.get_stats()
        stats["_status"] = "skeleton"
        return stats
    except Exception as e:
        return {"error": str(e), "_status": "error"}


@router.get("/ai-providers")
def get_ai_provider_stats(period: str = Query("7d")):
    """Provider 별 사용 통계 + 성공률.

    Phase 4 구현:
      - 각 provider/model 사용 횟수
      - 성공률, 평균 응답 시간
      - 객체 타입별 적합도 분석
    """
    return {
        "period": period,
        "by_provider": {},  # {"anthropic": {...}, "ollama": {...}}
        "by_model": {},     # {"gemma2:27b": {calls, success_rate, avg_ms}}
        "_status": "skeleton",
    }


@router.get("/recent")
def get_recent_conversions(limit: int = Query(50, ge=1, le=500)):
    """최근 변환 N건 상세.

    각 행:
      - timestamp, job_id, obj_type, obj_name
      - layers_attempted (KB → Rule → SQLGlot → AI)
      - layer_used (최종)
      - model_used (AI 일 때)
      - elapsed_ms
      - kb_action, rule_learned 등
    """
    return {
        "items": [],
        "total": 0,
        "limit": limit,
        "_status": "skeleton",
    }


# ════════════════════════════════════════════════════════════
# AI Provider 관리 (관리자 화면)
# ════════════════════════════════════════════════════════════

@provider_router.get("/list")
def list_providers():
    """지원 Provider 목록 — 관리자 화면 dropdown 데이터."""
    from app.core.ai_provider import SUPPORTED_PROVIDERS
    return {"providers": SUPPORTED_PROVIDERS}


@provider_router.get("/current")
def get_current_provider():
    """현재 활성 Provider 설정 조회.

    Phase 3 구현:
      - store_settings 에서 'ai_provider_config' 키 로드
      - 마스킹된 응답 (api_key 등 가림)
    """
    return {
        "default": {
            "provider": "anthropic",  # 현재 환경 추정
            "model": "claude-sonnet-4-20250514",
        },
        "by_obj_type": {},
        "_status": "skeleton",
    }


@provider_router.post("/set-default")
def set_default_provider(payload: dict):
    """기본 Provider 변경.

    Body: {provider: "ollama", model: "qwen2.5-coder:32b", config: {...}}

    Phase 3 구현:
      - 유효성 검증 (provider 존재, model 형식)
      - 연결 테스트 (Ollama URL ping, API key 검증)
      - store_settings 저장
      - 즉시 적용 (다음 변환부터 새 provider)
    """
    return {"ok": False, "_status": "skeleton — Phase 3 에서 구현"}


@provider_router.post("/set-by-obj-type")
def set_provider_by_obj_type(payload: dict):
    """객체 타입별 모델 매핑 변경.

    Body: {
      "PROCEDURE": {"provider": "ollama", "model": "qwen2.5-coder:32b"},
      "VIEW": {"provider": "ollama", "model": "gemma2:9b"},
      ...
    }
    """
    return {"ok": False, "_status": "skeleton"}


@provider_router.post("/test-connection")
def test_provider_connection(payload: dict):
    """Provider 연결 테스트 — 관리자 화면의 [테스트] 버튼.

    Body: {provider: "ollama", config: {ollama_url: "http://localhost:11434"}}

    Phase 3 구현:
      - Ollama: GET /api/tags
      - Anthropic: 작은 메시지 1건 호출
      - 응답 시간 측정
    """
    return {"ok": False, "elapsed_ms": 0, "_status": "skeleton"}
