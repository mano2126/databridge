"""
app/core/sql_llm_converter.py
LLM 기반 SQL 변환 fallback.

언제 사용:
  - AST 파싱 실패
  - regex 규칙으로 해결 안 되는 복잡 SQL
  - 사용자가 명시적으로 engine="llm" 요청

원칙:
  - Anthropic API 키 없으면 비활성 (graceful degrade)
  - 엔터프라이즈 edition만 사용 가능 (라이선스 feature: custom_sql_rules)
  - 변환 결과는 항상 "LLM 생성 — 검토 권장" 경고 포함
  - 프롬프트에 DB 버전, 스키마 힌트, 기존 AST 시도 결과 등 맥락 주입
"""
from __future__ import annotations
import json
import logging
import os
from typing import Optional

logger = logging.getLogger("databridge.sql_llm")


def is_available() -> bool:
    """LLM fallback 사용 가능 여부"""
    # 1. Anthropic API 키 존재
    try:
        from app.api.routes.settings import _cfg
        api_key = (_cfg().get("anthropic_api_key") or "").strip()
        if not api_key:
            return False
    except Exception:
        # settings 로드 실패 — 환경변수 확인
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return False

    # 2. anthropic 라이브러리 설치
    try:
        import anthropic  # noqa
    except ImportError:
        return False

    # 3. 라이선스: custom_sql_rules 기능 허용
    try:
        from app.core.license import check_feature
        if not check_feature("custom_sql_rules"):
            return False
    except Exception:
        pass

    return True


def _get_api_key() -> Optional[str]:
    try:
        from app.api.routes.settings import _cfg
        key = (_cfg().get("anthropic_api_key") or "").strip()
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("ANTHROPIC_API_KEY")


def convert_via_llm(
    sql: str,
    src_db: str,
    tgt_db: str,
    *,
    prior_attempt: Optional[dict] = None,
    schema_hints: Optional[dict] = None,
) -> Optional[dict]:
    """
    LLM으로 SQL 변환.

    Args:
        sql: 변환할 원본 SQL
        src_db, tgt_db: 방언
        prior_attempt: AST/regex 시도 결과 (참고 맥락)
        schema_hints: {"tables": {...}, "columns": {...}} 선택

    Returns:
        {
          "converted": str,
          "engine": "llm",
          "model": str,
          "warnings": list[str] (항상 "LLM 검토 권장" 포함),
          "notes": list[str],
          "tokens": {"input": N, "output": N},
        }
        또는 None (실패)
    """
    if not is_available():
        return None

    api_key = _get_api_key()
    if not api_key:
        return None

    try:
        import anthropic
    except ImportError:
        return None

    prompt = _build_prompt(sql, src_db, tgt_db, prior_attempt, schema_hints)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        model = "claude-sonnet-4-6-20250514"  # 균형형
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            system=_SYSTEM_PROMPT,
        )
        converted = _extract_sql(response.content[0].text if response.content else "")
        if not converted:
            return None

        return {
            "converted": converted,
            "engine": "llm",
            "model": model,
            "warnings": [
                "⚠ LLM 생성 결과 — 반드시 실행 전 검토 필수. "
                "특히 비즈니스 로직, NULL 처리, 정밀도는 원본과 대조하세요."
            ],
            "notes": [f"LLM({model})로 변환. AST/regex 실패 시 fallback."],
            "tokens": {
                "input":  response.usage.input_tokens,
                "output": response.usage.output_tokens,
            },
        }
    except Exception as e:
        logger.warning("LLM 변환 실패: %s", e)
        return None


_SYSTEM_PROMPT = """You are a senior database engineer expert in multi-dialect SQL conversion.
Your task is to convert SQL queries between database dialects PRESERVING EXACT SEMANTICS.

CRITICAL RULES:
1. Output ONLY the converted SQL wrapped in ```sql ... ``` code block. No explanation outside.
2. Preserve the original query logic exactly. Do not add WHERE clauses, LIMIT, or hints that weren't in the original.
3. For unsupported constructs (e.g., MSSQL PIVOT in MySQL), write a faithful equivalent using supported constructs (CASE WHEN, etc.)
4. Keep original column aliases, table aliases, and identifier casing unchanged when possible.
5. If a construct has NO semantic equivalent (e.g., MSSQL OUTPUT in MySQL), write a comment and leave the original line with -- TODO:
6. Always preserve NULL handling semantics. ISNULL ≠ NULLIF, IFNULL treats empty string differently, etc. Use COALESCE when behavior should match across dialects.
"""


def _build_prompt(sql: str, src: str, tgt: str,
                  prior: Optional[dict], schema: Optional[dict]) -> str:
    parts = [
        f"Convert this SQL from {src.upper()} to {tgt.upper()}.",
        "",
        "=== ORIGINAL SQL ===",
        "```sql",
        sql.strip(),
        "```",
    ]

    if prior:
        parts += [
            "",
            "=== PRIOR AUTOMATED ATTEMPT (may have issues) ===",
            f"engine: {prior.get('engine','?')}",
            "```sql",
            prior.get("converted", "").strip()[:2000],
            "```",
        ]
        if prior.get("warnings"):
            parts += ["Warnings from automated attempt:"]
            parts += [f"- {w}" for w in prior["warnings"][:5]]

    if schema and schema.get("tables"):
        parts += [
            "",
            "=== SCHEMA HINTS ===",
            json.dumps(schema.get("tables"), indent=2)[:1500],
        ]

    parts += [
        "",
        f"Output the converted SQL in {tgt.upper()} dialect. Use a ```sql code block.",
    ]
    return "\n".join(parts)


def _extract_sql(text: str) -> Optional[str]:
    """LLM 응답에서 ```sql ... ``` 블록 추출"""
    import re
    m = re.search(r"```(?:sql)?\s*\n(.+?)\n```", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # 폴백: 전체 텍스트가 SQL이라고 가정
    stripped = text.strip()
    if stripped.upper().startswith(("SELECT", "WITH", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER")):
        return stripped
    return None
