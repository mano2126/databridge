"""
DataBridge Rule Engine — Layer 2 (자체 변환 규칙 엔진)
========================================================

본부장님 모토 #4 정면 충실:
  "KB = 살아있는 자산" + "외부 의존 0 으로 수렴"

핵심 가치:
  - SQLGlot/AI 결과를 흡수하여 영구 자산화
  - 시간 갈수록 외부 호출 ↓
  - 본부장님 검증한 변환 규칙만 누적
  - Apache 2.0 외부 라이브러리 의존 0

규칙 형식 (rules.json):
  {
    "rules": [
      {
        "id": "rule_001",
        "category": "function_mapping",
        "src_dialect": "mssql",
        "tgt_dialect": "mysql",
        "pattern": "GETDATE\\(\\)",
        "replacement": "NOW()",
        "applies_to": ["FUNCTION", "PROCEDURE", "TRIGGER", "VIEW"],
        "verified_by": "본부장님 또는 SQLGlot",
        "use_count": 0,
        "registered_at": "2026-05-10T..."
      },
      {
        "id": "rule_002",
        "category": "type_mapping",
        ...
      }
    ]
  }

규칙 카테고리:
  - function_mapping: GETDATE→NOW, ISNULL→IFNULL 등
  - type_mapping: nvarchar→varchar, datetime2→datetime 등
  - identifier_quoting: [name] → `name`
  - schema_flattening: customer.profile → customer_profile (본부장님 비즈니스 로직)
  - ddl_structure: CREATE FUNCTION … RETURNS TABLE → MySQL TEMPORARY TABLE 변환
  - control_flow: IF … BEGIN … END → MySQL 등가 변환

골격 상태 (2026-05-10):
  - 인터페이스 + JSON 로딩 완성
  - 실제 규칙 적용 로직은 Phase 2 (다음 세션)
  - learn_from_pair 의 패턴 추출 알고리즘은 Phase 2
"""
from __future__ import annotations
import json
import logging
import re
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Any

_KST = timezone(timedelta(hours=9))
_log = logging.getLogger("databridge.rule_engine")


# 규칙 저장 경로
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_RULES_FILE = _DATA_DIR / "conversion_rules.json"


class RuleEngine:
    """DataBridge 자체 변환 규칙 엔진."""

    def __init__(self):
        self._rules = self._load_rules()

    def _load_rules(self) -> dict:
        """규칙 JSON 로드. 없으면 빈 구조로 시작."""
        if _RULES_FILE.exists():
            try:
                with open(_RULES_FILE, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                _log.warning("rules 파일 로드 실패: %s", e)
        return {"rules": [], "version": "1.0", "created_at": datetime.now(_KST).isoformat()}

    def _save_rules(self):
        """규칙 JSON 저장."""
        _DATA_DIR.mkdir(exist_ok=True)
        try:
            with open(_RULES_FILE, "w", encoding="utf-8") as f:
                json.dump(self._rules, f, indent=2, ensure_ascii=False)
        except Exception as e:
            _log.error("rules 파일 저장 실패: %s", e)

    # ════════════════════════════════════════════════════════════
    # 규칙 적용 (Layer 2 변환 호출)
    # ════════════════════════════════════════════════════════════
    def convert(
        self,
        src_ddl: str,
        obj_type: str,
        obj_name: str,
        src_dialect: str,
        tgt_dialect: str,
    ):
        """누적된 규칙으로 변환 시도.

        Phase 2 (다음 세션) 구현:
          1. 적용 가능한 규칙 필터링 (src/tgt dialect, obj_type 매치)
          2. 카테고리 순서대로 적용 (type → identifier → function → ...)
          3. 적용 횟수 카운트 (use_count++)
          4. 결과 게이트 검증 후 반환

        현재 (골격): None 반환 → 다음 Layer 로 위임
        """
        # Phase 2 까지 None — Layer 3 (SQLGlot) 으로 위임
        return None

    # ════════════════════════════════════════════════════════════
    # 규칙 학습 (Layer 3/4 결과 흡수)
    # ════════════════════════════════════════════════════════════
    def learn_from_pair(
        self,
        src_ddl: str,
        tgt_ddl: str,
        src_dialect: str,
        tgt_dialect: str,
        obj_type: str,
    ):
        """입력/출력 SQL 쌍에서 변환 규칙 추출 + 누적.

        본부장님 모토 #4: SQLGlot/AI 의 검증된 결과를 영구 자산화.

        Phase 2 (다음 세션) 구현:
          - 차이점 분석 (diff)
          - 패턴 추출 (예: 입력에 GETDATE(), 출력에 NOW() → rule)
          - 중복 검사 (이미 있는 규칙은 use_count++)
          - 새 규칙은 _rules["rules"] 에 append + save
        """
        # Phase 2 까지 no-op — 추후 구현
        pass

    # ════════════════════════════════════════════════════════════
    # 통계 (가시성 페이지용)
    # ════════════════════════════════════════════════════════════
    def get_stats(self) -> dict:
        """규칙 누적 통계 — /api/v1/rule-engine/stats 가 반환.

        Phase 4 (다음 세션) 구현:
          - 카테고리별 규칙 수
          - 가장 많이 쓰인 규칙 Top 10
          - 시간별 학습 누적 그래프 데이터
        """
        rules = self._rules.get("rules", [])
        return {
            "total_rules": len(rules),
            "by_category": self._count_by_category(rules),
            "total_use_count": sum(r.get("use_count", 0) for r in rules),
            "version": self._rules.get("version"),
        }

    def _count_by_category(self, rules: list) -> dict:
        cnt = {}
        for r in rules:
            cat = r.get("category", "unknown")
            cnt[cat] = cnt.get(cat, 0) + 1
        return cnt

    # ════════════════════════════════════════════════════════════
    # 본부장님 비즈니스 로직 (스키마 평탄화 등) — Phase 2 핵심
    # ════════════════════════════════════════════════════════════
    def apply_schema_flattening(self, ddl: str, strategy: str = "underscore") -> str:
        """본부장님 메모리 #19: customer.profile → customer_profile.

        Phase 2 (다음 세션) 구현:
          - SQL 토큰화 (정규식 또는 SQLGlot AST 활용)
          - schema.table 패턴 찾아서 schema_table 로 변환
          - 다른 strategy: drop, database
        """
        # Phase 2 까지 원본 그대로
        return ddl
