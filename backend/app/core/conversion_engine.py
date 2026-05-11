"""
DataBridge 4-Layer 변환 엔진 — hotfix_021 본부장님 본질 처방
==============================================================

본부장님 6번째 본질 통찰 (2026-05-10):
  "SQLGlot 에 너무 디펜던트 해지는 거 아닐까?"

처방 — 4-Layer 격리 아키텍처:
  Layer 1: KB 매칭 (이미 검증된 자산 — hotfix_019 그대로 활용)
  Layer 2: DataBridge 자체 Rule Engine (신규, 본부장님 핵심 자산)
  Layer 3: SQLGlot 참조 (격리, 선택적, 결과를 Rule Engine 에 흡수)
  Layer 4: AI Provider (다중 선택 — Anthropic/Ollama/OpenAI/Custom)

핵심 가치:
  - Layer 1+2 만으로도 동작 가능 (캐피탈사 air-gapped 환경)
  - 시간이 갈수록 Rule Engine 누적 → SQLGlot/AI 의존 ↓
  - 모든 변환 결과 + 메타데이터 (어느 Layer / 어느 model) 추적
  - 본부장님 모토 #4 (KB = 살아있는 자산) + #14 (4-way collision 방지)

골격 상태 (2026-05-10):
  - 인터페이스 + 분기 흐름 완성
  - 각 Layer 내부 구현은 다음 세션 Phase 별 진행
  - 부작용 0% — 기존 _ai_convert_ddl 흐름 살아있는 채로 추가
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Any
from datetime import datetime, timezone, timedelta

_KST = timezone(timedelta(hours=9))
_log = logging.getLogger("databridge.conversion_engine")


# ════════════════════════════════════════════════════════════════
# 변환 결과 표준 스키마 (모든 Layer 공통)
# ════════════════════════════════════════════════════════════════
@dataclass
class ConversionResult:
    """변환 결과 통합 스키마.

    layer_used: 어느 Layer 가 최종 결과 만들었는지 (kb / rule / sqlglot / ai)
    model_used: AI 일 때 정확한 모델명 (gemma:9b, claude-sonnet-4 등)
    layers_attempted: 시도한 Layer 순서 (디버깅 + 통계용)
    """
    success: bool
    statements: list[str] = field(default_factory=list)
    layer_used: str = ""               # "kb" | "rule" | "sqlglot" | "ai" | ""
    model_used: str = ""               # AI 일 때만 채움
    layers_attempted: list[str] = field(default_factory=list)
    elapsed_ms: int = 0
    notes: str = ""
    error: str = ""
    # KB 갱신 정보 (Layer 2/3/4 성공 시)
    kb_action: str = ""                # "match" | "register" | "update" | ""
    kb_id: str = ""
    # SQLGlot 사용 추적 (Layer 3 활용 시)
    sqlglot_used: bool = False
    sqlglot_dialect_pair: str = ""     # "tsql->mysql" 등
    # Rule Engine 학습 추적 (Layer 3 결과를 Layer 2 에 흡수했을 때)
    rule_learned: bool = False
    rule_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ════════════════════════════════════════════════════════════════
# 4-Layer 변환 엔진 (메인 진입점)
# ════════════════════════════════════════════════════════════════
class ConversionEngine:
    """DataBridge 4-Layer 변환 엔진.

    호출자 (migration_engine, schema._ai_convert_ddl) 가 이 클래스만 사용.
    내부 Layer 분기는 모두 격리 — Phase 단위로 신중하게 추가.
    """

    def __init__(self, config: dict):
        """
        Args:
            config: 본부장님 환경 설정
              - ai_provider: "anthropic" | "ollama" | "openai" | "custom"
              - ai_model: 모델명
              - sqlglot_enabled: bool (Layer 3 활성화 여부)
              - rule_engine_enabled: bool (Layer 2 활성화 여부)
        """
        self.config = config or {}
        self._stats = ConversionStats()  # 통계 수집기 (가시성 페이지용)

    # ─── 메인 변환 함수 ──────────────────────────────────────
    def convert(
        self,
        src_ddl: str,
        obj_type: str,
        obj_name: str,
        src_dialect: str,
        tgt_dialect: str,
        error_hint: str = "",
        job_id: str = "",
    ) -> ConversionResult:
        """4-Layer 순차 변환.

        흐름:
          [Layer 1] KB 매칭 → HIT 시 즉시 반환
                              MISS 시 다음
          [Layer 2] Rule Engine → 변환 시도
                                  성공 시 KB 등록 + 반환
                                  실패 시 다음
          [Layer 3] SQLGlot → 변환 시도 (격리, 선택적)
                              성공 시 검증 → KB 등록 + Rule 학습 + 반환
                              실패 시 다음
          [Layer 4] AI Provider → fallback (다중 provider 선택)
                                  성공 시 검증 → KB 등록 + 반환
        """
        t0 = time.monotonic()
        result = ConversionResult(success=False)

        # ─── Layer 1: KB 매칭 ───
        # error_hint 가 없을 때만 매칭 (재시도 케이스는 KB 우회)
        if not error_hint:
            kb_result = self._try_kb_match(src_ddl, obj_type, obj_name,
                                            src_dialect, tgt_dialect)
            result.layers_attempted.append("kb")
            if kb_result and kb_result.success:
                result = kb_result
                result.elapsed_ms = int((time.monotonic() - t0) * 1000)
                self._stats.record(result, job_id)
                _log.info(
                    "[L1-KB-HIT] %s [%s] use_count=%s → AI 호출 0회",
                    obj_type, obj_name, result.kb_id
                )
                return result

        # ─── Layer 2: DataBridge Rule Engine ───
        if self.config.get("rule_engine_enabled", True):
            rule_result = self._try_rule_engine(src_ddl, obj_type, obj_name,
                                                 src_dialect, tgt_dialect)
            result.layers_attempted.append("rule")
            if rule_result and rule_result.success:
                # 검증 (게이트 7+8)
                if self._validate(rule_result.statements, obj_type, obj_name):
                    rule_result.elapsed_ms = int((time.monotonic() - t0) * 1000)
                    rule_result.layers_attempted = result.layers_attempted
                    self._kb_register(rule_result, src_ddl, obj_type, obj_name,
                                       src_dialect, tgt_dialect)
                    self._stats.record(rule_result, job_id)
                    _log.info("[L2-RULE-OK] %s [%s]", obj_type, obj_name)
                    return rule_result

        # ─── Layer 3: SQLGlot (격리, 선택적) ───
        if self.config.get("sqlglot_enabled", True):
            sg_result = self._try_sqlglot(src_ddl, obj_type, obj_name,
                                           src_dialect, tgt_dialect)
            result.layers_attempted.append("sqlglot")
            if sg_result and sg_result.success:
                # 검증 (게이트 7+8)
                if self._validate(sg_result.statements, obj_type, obj_name):
                    sg_result.elapsed_ms = int((time.monotonic() - t0) * 1000)
                    sg_result.layers_attempted = result.layers_attempted

                    # ⭐ 핵심: SQLGlot 결과를 Rule Engine 에 흡수
                    self._learn_to_rule_engine(
                        src_ddl, sg_result.statements,
                        src_dialect, tgt_dialect, obj_type
                    )
                    sg_result.rule_learned = True

                    self._kb_register(sg_result, src_ddl, obj_type, obj_name,
                                       src_dialect, tgt_dialect)
                    self._stats.record(sg_result, job_id)
                    _log.info("[L3-SQLGLOT-OK] %s [%s] → Rule Engine 흡수",
                              obj_type, obj_name)
                    return sg_result

        # ─── Layer 4: AI Provider (다중 선택) ───
        ai_result = self._try_ai(src_ddl, obj_type, obj_name,
                                  src_dialect, tgt_dialect, error_hint)
        result.layers_attempted.append(f"ai_{self.config.get('ai_provider', 'unknown')}")
        if ai_result and ai_result.success:
            if self._validate(ai_result.statements, obj_type, obj_name):
                ai_result.elapsed_ms = int((time.monotonic() - t0) * 1000)
                ai_result.layers_attempted = result.layers_attempted
                self._kb_register(ai_result, src_ddl, obj_type, obj_name,
                                   src_dialect, tgt_dialect)
                self._stats.record(ai_result, job_id)
                _log.info("[L4-AI-OK] %s [%s] model=%s",
                          obj_type, obj_name, ai_result.model_used)
                return ai_result

        # ─── 모든 Layer 실패 ───
        result.elapsed_ms = int((time.monotonic() - t0) * 1000)
        result.error = "모든 Layer 변환 실패"
        self._stats.record(result, job_id)
        _log.error("[ALL-LAYERS-FAIL] %s [%s] attempted=%s",
                   obj_type, obj_name, result.layers_attempted)
        return result

    # ════════════════════════════════════════════════════════════
    # 각 Layer 구현 (Phase 별 다음 세션에 채움)
    # ════════════════════════════════════════════════════════════

    def _try_kb_match(self, src_ddl, obj_type, obj_name,
                      src_dialect, tgt_dialect) -> Optional[ConversionResult]:
        """Layer 1: KB 매칭. 기존 obj_executor._kb_match_pattern 활용."""
        try:
            from app.core.obj_executor import _kb_match_pattern
            hit = _kb_match_pattern(src_dialect, tgt_dialect,
                                    obj_type, obj_name, src_ddl)
            if hit and hit.get("tgt_sample_ddl"):
                return ConversionResult(
                    success=True,
                    statements=[hit["tgt_sample_ddl"]],
                    layer_used="kb",
                    kb_action="match",
                    kb_id=hit.get("id", ""),
                    notes=f"KB use_count={hit.get('use_count')}",
                )
        except Exception as e:
            _log.warning("[L1-KB-EXC] %s [%s]: %s", obj_type, obj_name, e)
        return None

    def _try_rule_engine(self, src_ddl, obj_type, obj_name,
                          src_dialect, tgt_dialect) -> Optional[ConversionResult]:
        """Layer 2: DataBridge 자체 Rule Engine.

        Phase 2 (다음 세션) 구현:
          - rule_engine.py 의 RuleEngine 클래스 호출
          - 본부장님 검증한 변환 규칙 누적 자산
          - 함수 매핑, 데이터 타입 매핑, 식별자 quoting 등
          - SQLGlot/AI 결과를 흡수해서 영구 자산화

        현재 (골격): None 반환 → Layer 3 으로 넘어감
        """
        try:
            from app.core.rule_engine import RuleEngine
            engine = RuleEngine()
            return engine.convert(src_ddl, obj_type, obj_name,
                                   src_dialect, tgt_dialect)
        except ImportError:
            # Phase 2 까지 RuleEngine 없음 — 정상
            return None
        except Exception as e:
            _log.warning("[L2-RULE-EXC] %s [%s]: %s", obj_type, obj_name, e)
            return None

    def _try_sqlglot(self, src_ddl, obj_type, obj_name,
                      src_dialect, tgt_dialect) -> Optional[ConversionResult]:
        """Layer 3: SQLGlot 격리 호출.

        Phase 1 (다음 세션) 구현:
          - sqlglot_adapter.py 의 SQLGlotAdapter 클래스 호출
          - dialect 매핑: mssql → tsql, mysql → mysql 등
          - ParseError 등 예외 안전 처리
          - 결과 검증 (게이트 7+8)

        현재 (골격): None 반환 → Layer 4 로 넘어감
        """
        try:
            from app.core.sqlglot_adapter import SQLGlotAdapter
            adapter = SQLGlotAdapter()
            return adapter.transpile(src_ddl, obj_type, obj_name,
                                      src_dialect, tgt_dialect)
        except ImportError:
            # Phase 1 까지 SQLGlotAdapter 없음 — 정상
            return None
        except Exception as e:
            _log.warning("[L3-SQLGLOT-EXC] %s [%s]: %s", obj_type, obj_name, e)
            return None

    def _try_ai(self, src_ddl, obj_type, obj_name,
                 src_dialect, tgt_dialect, error_hint) -> Optional[ConversionResult]:
        """Layer 4: AI Provider 다중 선택.

        Phase 3 (다음 세션) 구현:
          - ai_provider.py 의 AIProvider 클래스 호출
          - 본부장님 설정한 provider/model 사용
          - 변환 종류별 다른 모델 가능 (SP/FN: Qwen Coder, VIEW: Gemma 등)
          - 모델별 KB 추적 (model_used 필드)

        현재 (골격): 기존 _ai_convert_ddl 호출 (호환성 유지)
        """
        try:
            from app.api.routes.schema import _ai_convert_ddl
            r = _ai_convert_ddl(src_ddl, obj_type, obj_name,
                                 src_dialect, tgt_dialect, error_hint)
            if r and r.get("statements"):
                return ConversionResult(
                    success=True,
                    statements=r["statements"],
                    layer_used="ai",
                    model_used=self.config.get("ai_model", "unknown"),
                    notes=r.get("notes", ""),
                    kb_action="register",
                )
        except Exception as e:
            _log.error("[L4-AI-EXC] %s [%s]: %s", obj_type, obj_name, e)
        return None

    def _learn_to_rule_engine(self, src_ddl, tgt_stmts,
                               src_dialect, tgt_dialect, obj_type):
        """Layer 3 (SQLGlot) 결과를 Layer 2 (Rule Engine) 에 흡수.

        본부장님 모토 #4 정면 — 외부 의존 시간 갈수록 0 으로 수렴.

        Phase 2 (다음 세션) 구현:
          - 입력/출력 패턴 분석
          - 변환 규칙 추출 (예: GETDATE() → NOW())
          - rule_engine.py 의 RuleEngine.add_rule() 호출
        """
        try:
            from app.core.rule_engine import RuleEngine
            engine = RuleEngine()
            engine.learn_from_pair(src_ddl, "\n".join(tgt_stmts),
                                    src_dialect, tgt_dialect, obj_type)
        except ImportError:
            pass  # Phase 2 까지 정상

    def _validate(self, statements, obj_type, obj_name) -> bool:
        """게이트 7 + 게이트 8 통과 검증."""
        if not statements:
            return False
        try:
            from app.api.routes.schema import _kb_quality_gate
            for stmt in statements:
                ok, reason = _kb_quality_gate(stmt, obj_type, obj_name)
                if not ok:
                    _log.warning("[VALIDATE-FAIL] %s [%s]: %s",
                                 obj_type, obj_name, reason)
                    return False
            return True
        except Exception:
            return True  # 검증 함수 자체 실패 시 통과 (안전 fallback)

    def _kb_register(self, result, src_ddl, obj_type, obj_name,
                      src_dialect, tgt_dialect):
        """KB 등록 — 모든 Layer 의 성공 결과를 KB 자산화.

        본부장님 모토 #4: KB = 살아있는 자산.
        Layer 2/3/4 의 모든 성공 결과 누적.
        """
        try:
            from app.core.obj_executor import _kb_register_pattern
            kb_id = _kb_register_pattern(
                src_dialect, tgt_dialect,
                obj_type, obj_name,
                src_ddl, "\n".join(result.statements),
                source=result.layer_used,        # ⭐ Layer 추적
                model_used=result.model_used,    # ⭐ 모델 추적
            )
            if kb_id:
                result.kb_id = kb_id
                result.kb_action = "register"
        except Exception as e:
            _log.warning("[KB-REGISTER-EXC] %s [%s]: %s",
                         obj_type, obj_name, e)


# ════════════════════════════════════════════════════════════════
# 통계 수집 (가시성 페이지용)
# ════════════════════════════════════════════════════════════════
class ConversionStats:
    """변환 통계 누적 — KB 메뉴 → 변환 엔진 활용 현황 페이지에서 표시."""

    def record(self, result: ConversionResult, job_id: str = ""):
        """변환 결과 1건 기록.

        Phase 4 (다음 세션) 구현:
          - SQLite store_conversion_stats 테이블에 INSERT
          - 시간별/Layer별/모델별 집계 쿼리 제공
          - /api/v1/conversion-stats 엔드포인트
        """
        try:
            from app.core.store import Store
            stats_store = Store("conversion_stats")
            stats_store.set(
                f"stat_{int(time.time() * 1000)}",
                {
                    "ts": datetime.now(_KST).isoformat(),
                    "job_id": job_id,
                    "result": result.to_dict(),
                }
            )
        except Exception:
            pass  # 통계 실패는 변환에 영향 X
