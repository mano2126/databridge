"""
DataBridge AI Provider — Layer 4 (다중 Provider 추상화)
========================================================

본부장님 결정 (2026-05-10):
  "AI 를 다양하게 선택할 수 있게 관리자 화면에서 구현"
  "올라마보다 더 나은 모델이 있을 수 있으니 그것도 관리자 선택"
  "수행, 재수행 시 쉽게 변경해서 사용 가능하도록"

지원 Provider:
  1. anthropic    — Claude API (claude-sonnet-4 등) — 정확도 우선
  2. ollama       — 로컬 (gemma, llama3, qwen 등) — air-gapped
  3. openai       — GPT-4 등 — 백업 옵션
  4. custom       — 사용자 정의 OpenAI 호환 endpoint

추가 기능 (본부장님 통찰):
  - 변환 종류별 다른 모델 (SP/FN: Qwen Coder, VIEW: Gemma, 복잡: Claude)
  - Job 단위 + 객체 단위 모델 추적 (KB 에 model_used 컬럼)
  - 모델별 성공률 비교 가능 (가시성 페이지)
  - 재실행 시 새 모델 선택 가능

골격 상태 (2026-05-10):
  - 인터페이스 + 분기 흐름 완성
  - 각 Provider 의 실제 호출은 Phase 3 (다음 세션) 에 채움
  - 현재 anthropic provider 만 기존 _ai_convert_ddl 호출로 위임 (호환)
"""
from __future__ import annotations
import logging
import os
import json
from typing import Optional, Any
from datetime import datetime, timezone, timedelta

_KST = timezone(timedelta(hours=9))
_log = logging.getLogger("databridge.ai_provider")


# 지원 Provider 목록 (관리자 화면 dropdown 데이터)
SUPPORTED_PROVIDERS = {
    "anthropic": {
        "name": "Anthropic Claude",
        "models": [
            {"id": "claude-sonnet-4-20250514", "label": "Claude Sonnet 4 (정확도 우선)"},
            {"id": "claude-opus-4-20250514", "label": "Claude Opus 4 (최고 정확도)"},
            {"id": "claude-haiku-4-5-20251001", "label": "Claude Haiku 4.5 (빠름)"},
        ],
        "requires": ["api_key"],
        "air_gapped": False,
    },
    "ollama": {
        "name": "Ollama (로컬)",
        "models": [
            # v95_p107 hotfix_069: 코딩 특화 모델 상위 정렬 — MSSQL→MySQL 변환 권장
            {"id": "qwen2.5-coder:32b", "label": "⭐ Qwen 2.5 Coder 32B (코딩 특화 — 권장)"},
            {"id": "deepseek-coder-v2:16b", "label": "⭐ DeepSeek Coder V2 16B (코딩 특화)"},
            {"id": "qwen2.5-coder:7b", "label": "Qwen 2.5 Coder 7B (코딩 특화, 가벼움)"},
            {"id": "gemma4:26b", "label": "Gemma 4 26B (일반 LLM, 본부장님 현재)"},
            {"id": "gemma2:27b", "label": "Gemma 2 27B (일반 LLM)"},
            {"id": "gemma2:9b", "label": "Gemma 2 9B (일반, 가벼움)"},
            {"id": "llama3.3:70b", "label": "Llama 3.3 70B (일반, 거대)"},
            {"id": "llama3.1:8b", "label": "Llama 3.1 8B (일반, 가벼움)"},
        ],
        "requires": ["ollama_url"],
        "air_gapped": True,  # ⭐ 본부장님 air-gapped 비전
    },
    "openai": {
        "name": "OpenAI",
        "models": [
            {"id": "gpt-4o", "label": "GPT-4o"},
            {"id": "gpt-4-turbo", "label": "GPT-4 Turbo"},
        ],
        "requires": ["api_key"],
        "air_gapped": False,
    },
    "custom": {
        "name": "Custom (사용자 정의 OpenAI 호환)",
        "models": [],  # 사용자가 직접 입력
        "requires": ["base_url", "api_key", "model"],
        "air_gapped": False,  # 사용자 환경에 따라
    },
    # v95_p107 hotfix_050: Moonshot AI (Kimi K2) — 코딩 챌린저 우수 모델
    "moonshot": {
        "name": "Moonshot AI (Kimi K2)",
        "models": [
            {"id": "kimi-k2-0711-preview", "label": "Kimi K2 (코딩 챌린저 우수)"},
            {"id": "moonshot-v1-128k",     "label": "Moonshot v1 128k"},
            {"id": "moonshot-v1-32k",      "label": "Moonshot v1 32k"},
            {"id": "moonshot-v1-8k",       "label": "Moonshot v1 8k"},
        ],
        "requires": ["api_key"],
        "air_gapped": False,  # cloud API (api.moonshot.cn 또는 .ai)
    },
}


# ════════════════════════════════════════════════════════════
# 추상 베이스 클래스
# ════════════════════════════════════════════════════════════
class AIProviderBase:
    """모든 AI Provider 의 공통 인터페이스."""

    provider_id = "base"

    def __init__(self, config: dict):
        self.config = config
        self.model = config.get("model", "")

    def convert_ddl(
        self,
        src_ddl: str,
        obj_type: str,
        obj_name: str,
        src_dialect: str,
        tgt_dialect: str,
        error_hint: str = "",
        max_tokens: int = 8192,
    ):
        """DDL 변환 — 모든 Provider 가 구현.

        반환: ConversionResult or None
        """
        raise NotImplementedError

    def is_available(self) -> bool:
        """Provider 사용 가능 여부 (API 키 / endpoint 등 체크)."""
        return False


# ════════════════════════════════════════════════════════════
# Provider 구현체들 (Phase 3 에서 채움)
# ════════════════════════════════════════════════════════════
class AnthropicProvider(AIProviderBase):
    provider_id = "anthropic"

    def convert_ddl(self, src_ddl, obj_type, obj_name,
                     src_dialect, tgt_dialect, error_hint="", max_tokens=8192):
        """Phase 3 다음 세션: Anthropic SDK 직접 호출.
        현재 (골격): 기존 _ai_convert_ddl 호출 (호환성 유지)."""
        try:
            from app.core.conversion_engine import ConversionResult
            from app.api.routes.schema import _ai_convert_ddl
            r = _ai_convert_ddl(src_ddl, obj_type, obj_name,
                                 src_dialect, tgt_dialect, error_hint,
                                 max_tokens=max_tokens)
            if r and r.get("statements"):
                return ConversionResult(
                    success=True,
                    statements=r["statements"],
                    layer_used="ai",
                    model_used=self.model,
                    notes=r.get("notes", ""),
                )
        except Exception as e:
            _log.warning("[AnthropicProvider] %s [%s]: %s", obj_type, obj_name, e)
        return None

    def is_available(self) -> bool:
        return bool(self.config.get("api_key"))


class OllamaProvider(AIProviderBase):
    provider_id = "ollama"

    def convert_ddl(self, src_ddl, obj_type, obj_name,
                     src_dialect, tgt_dialect, error_hint="", max_tokens=8192):
        """Phase 3 다음 세션: Ollama 직접 호출.

        본부장님 핵심 — air-gapped 환경의 핵심 Provider.
        Ollama API: /api/generate 또는 /v1/chat/completions (OpenAI 호환).

        구현 포인트:
          - num_ctx, num_predict 정확히 설정 (토큰 잘림 방지)
          - finish_reason 검증
          - stream 처리 안정화
          - 모델별 프롬프트 최적화 (Qwen Coder 는 다른 형식)
        """
        return None  # Phase 3 까지

    def is_available(self) -> bool:
        return bool(self.config.get("ollama_url"))


class OpenAIProvider(AIProviderBase):
    provider_id = "openai"

    def convert_ddl(self, src_ddl, obj_type, obj_name,
                     src_dialect, tgt_dialect, error_hint="", max_tokens=8192):
        """Phase 3 다음 세션: OpenAI SDK 호출."""
        return None

    def is_available(self) -> bool:
        return bool(self.config.get("api_key"))


class CustomProvider(AIProviderBase):
    provider_id = "custom"

    def convert_ddl(self, src_ddl, obj_type, obj_name,
                     src_dialect, tgt_dialect, error_hint="", max_tokens=8192):
        """Phase 3: 사용자 정의 OpenAI 호환 endpoint."""
        return None

    def is_available(self) -> bool:
        return bool(self.config.get("base_url") and self.config.get("api_key"))


# v95_p107 hotfix_050: Moonshot AI (Kimi K2) — OpenAI 호환 API
class MoonshotProvider(AIProviderBase):
    """Moonshot AI Kimi K2.
    Base URL: https://api.moonshot.cn/v1 (중국) 또는 https://api.moonshot.ai/v1 (글로벌)
    OpenAI 호환 인터페이스 — Phase 3 에서 OpenAI SDK with base_url override 로 구현.
    """
    provider_id = "moonshot"

    def convert_ddl(self, src_ddl, obj_type, obj_name,
                     src_dialect, tgt_dialect, error_hint="", max_tokens=8192):
        """Phase 3: Moonshot Kimi K2 호출 (OpenAI 호환). 현재 골격."""
        return None

    def is_available(self) -> bool:
        return bool(self.config.get("api_key"))


# ════════════════════════════════════════════════════════════
# Factory 함수
# ════════════════════════════════════════════════════════════
def get_ai_provider(provider_id: str, config: dict) -> Optional[AIProviderBase]:
    """Provider id 로 인스턴스 반환."""
    classes = {
        "anthropic": AnthropicProvider,
        "ollama": OllamaProvider,
        "openai": OpenAIProvider,
        "custom": CustomProvider,
        "moonshot": MoonshotProvider,  # v95_p107 hotfix_050
    }
    cls = classes.get(provider_id)
    if not cls:
        _log.warning("미지원 provider: %s", provider_id)
        return None
    return cls(config)


# ════════════════════════════════════════════════════════════
# 변환 종류별 모델 매핑 (본부장님 통찰)
# ════════════════════════════════════════════════════════════
def select_model_for_obj_type(obj_type: str, default_config: dict) -> dict:
    """객체 타입별로 다른 모델 선택 가능.

    본부장님 통찰: SP/FN 은 코드 특화 모델, VIEW 는 간단 모델.

    config 예:
      {
        "default": {"provider": "ollama", "model": "gemma2:9b"},
        "by_obj_type": {
          "PROCEDURE": {"provider": "ollama", "model": "qwen2.5-coder:32b"},
          "FUNCTION":  {"provider": "ollama", "model": "qwen2.5-coder:32b"},
          # v95_p107 hotfix_060: 본부장님 환경 Gemma 강제 (Claude 비용 차단)
          "TRIGGER":   {"provider": "ollama", "model": "gemma2:27b"},
          "VIEW":      {"provider": "ollama", "model": "gemma2:9b"},
        }
      }
    """
    by_type = default_config.get("by_obj_type", {}) or {}
    return by_type.get(obj_type, default_config.get("default", {}))
