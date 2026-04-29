"""
app/core/advisor/base_advisor.py — AI DBA Advisor 기본 인터페이스
v88 P1 (2026-04-23)

철학:
  "프레임워크만 탄탄하면 DB 추가는 껌이다" — 본부장님

설계 원칙:
  1. 모든 Advisor는 BaseAdvisor 를 상속 → 4가지 권고 카테고리를 Plugin 형태로 추가 가능
  2. 권고(Recommendation) 스키마는 공통 → 프론트엔드는 카테고리 상관없이 동일 UI 로 표시
  3. 분석 모드(smart/hybrid/deep) 에 따라 실행 범위/AI 호출 횟수가 달라짐
  4. 권고 수용 결과는 advisor_learner (후속) 로 흘려보내 KB 자동 축적

4개 Advisor (후속 세션 P2~P5에서 구현):
  - TableAdvisor   : 테이블 구조 최적화 (파티셔닝, 오버스펙 등)
  - ObjectAdvisor  : SP/Function/View 최적화 (안티패턴, 재작성 권고)
  - IndexAdvisor   : 인덱스 전략 (실사용 기반 필수/불필요 도출)
  - ServerAdvisor  : 타겟 DB 서버 설정 (버퍼풀, 로그 크기 등)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Literal, Optional, Any

# ══════════════════════════════════════════════════════════════
# 공통 데이터 타입
# ══════════════════════════════════════════════════════════════

# 분석 모드 — 3-tier
AnalysisMode = Literal["smart", "hybrid", "deep"]

# 카테고리 — 4개 Advisor 중 어디서 나왔는지
Category = Literal["table", "object", "index", "server"]

# 권고 심각도
Severity = Literal["high", "med", "low"]

# 권고 기본 행동
DefaultAction = Literal["apply", "review", "skip"]

# 권고 소스 — 규칙 기반인지 AI 기반인지
Source = Literal["rule", "ai", "hybrid"]

# 사용자 결정 — 권고를 어떻게 처리했는가
Decision = Literal["applied", "skipped", "edited", "pending"]


@dataclass
class JobSelection:
    """Stage 2(객체 선택)에서 사용자가 선택한 이관 대상."""
    tables: list[str] = field(default_factory=list)
    procedures: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    views: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (
            len(self.tables)
            + len(self.procedures)
            + len(self.functions)
            + len(self.triggers)
            + len(self.views)
        )

    @property
    def total_objects(self) -> int:
        """테이블 제외 오브젝트 총수 (SP/Func/Trigger/View)."""
        return (
            len(self.procedures)
            + len(self.functions)
            + len(self.triggers)
            + len(self.views)
        )


@dataclass
class AnalysisContext:
    """
    Advisor 에게 전달되는 분석 맥락.

    src_conn / tgt_conn 은 None 가능 — P1 에서는 연결 없이 메타데이터만으로
    비용 산정이 가능해야 함 (analyze() 는 실제 연결 필요).
    """
    src_db: str
    tgt_db: str
    mode: AnalysisMode = "smart"
    user_hints: str = ""                 # 사용자가 추가 맥락 입력 시 (예: "OLTP 위주")
    src_conn: Any = None
    tgt_conn: Any = None
    query_log_available: bool = False    # 쿼리 실행 로그 접근 가능 여부


@dataclass
class Recommendation:
    """
    Advisor 가 반환하는 단일 권고.

    프론트엔드 RecommendationCard.vue 가 이 스키마를 그대로 렌더링한다.
    필드 추가/제거 시 반드시 프론트 컴포넌트 동시 수정.
    """
    id: str                        # 안정적 고유 ID (동일 권고가 재분석되어도 같은 ID)
    category: Category
    severity: Severity
    title: str                     # 한 줄 요약 (한국어)
    target: str                    # 대상 (예: "orders 테이블", "sp_CalcInterest")
    reason: str                    # 왜 권고하는가 — 데이터 근거 포함
    before: str = ""               # 현재 상태 (DDL / 설정값)
    after: str = ""                # 권고 적용 후 (DDL / 설정값)
    estimated_impact: str = ""     # "조회 15배 빨라짐" 등
    auto_applicable: bool = False  # 자동 적용 가능한가
    default_action: DefaultAction = "review"
    source: Source = "rule"
    confidence: float = 1.0        # 0.0 ~ 1.0
    rule_id: Optional[str] = None  # KB 연결용 (learner 축적)

    # 사용자 결정 (분석 시점엔 pending)
    decision: Decision = "pending"
    edited_sql: Optional[str] = None  # decision == "edited" 시 최종 SQL

    def to_dict(self) -> dict:
        return asdict(self)


# ══════════════════════════════════════════════════════════════
# Advisor 추상 클래스
# ══════════════════════════════════════════════════════════════
class BaseAdvisor(ABC):
    """
    모든 Advisor 의 부모 클래스.

    구현 클래스는 최소 다음 2개 메서드를 구현해야 한다:
      - analyze(selection, context) -> list[Recommendation]
      - estimate_tokens(selection, mode) -> int    # 비용 산정용
    """

    # 자식 클래스에서 재정의
    category: Category = "table"

    @abstractmethod
    def analyze(
        self,
        selection: JobSelection,
        context: AnalysisContext,
    ) -> list[Recommendation]:
        """
        실제 분석 수행 — 권고 리스트 반환.

        주의:
          - context.mode == "smart"  : 규칙이 잡은 HIGH 후보만 AI 분석
          - context.mode == "hybrid" : HIGH + MED 모두 AI 분석
          - context.mode == "deep"   : 대상 전체 AI 분석
        """
        raise NotImplementedError

    @abstractmethod
    def estimate_tokens(
        self,
        selection: JobSelection,
        mode: AnalysisMode,
    ) -> dict:
        """
        실제 분석 없이 예상 토큰량 계산 — 모드 선택 UI 의 "예상 비용" 표시용.

        Returns:
            {
                "tokens_in":  int,   # 입력 토큰 예상
                "tokens_out": int,   # 출력 토큰 예상
            }
        """
        raise NotImplementedError

    def supports(self, src_db: str, tgt_db: str) -> bool:
        """
        이 Advisor 가 해당 DB 조합을 지원하는가.

        기본: 모두 지원. 특정 Advisor 에서 제한할 때 재정의
        (예: ServerAdvisor 는 지원하는 타겟 DB 가 정해져 있을 수 있음).
        """
        return True


# ══════════════════════════════════════════════════════════════
# 비용 산정 공식 (Advisor 없이도 독립 사용 가능)
# ══════════════════════════════════════════════════════════════
# Claude Sonnet 4 요금 (2026-04 기준)
_PRICE_INPUT_PER_MTOK = 3.0    # USD per 1M input tokens
_PRICE_OUTPUT_PER_MTOK = 15.0  # USD per 1M output tokens
_TOKENS_PER_SEC = 3000.0       # 대략적 처리 속도 (네트워크 포함)
_USD_TO_KRW = 1380.0           # 환율 추정 (settings 에서 override 가능)

# 모드별 경험값 계수 — advisor_learner 가 실측치로 갱신 예정
_MODE_COEFFICIENTS = {
    "smart":  {"rate_tables": 0.15, "rate_objects": 0.15, "per_candidate_in": 2500, "per_candidate_out": 1500},
    "hybrid": {"rate_tables": 0.40, "rate_objects": 0.40, "per_candidate_in": 2500, "per_candidate_out": 1500},
    "deep":   {"rate_tables": 1.00, "rate_objects": 1.00, "per_candidate_in": 2500, "per_candidate_out": 1500},
}


def estimate_analysis_cost(
    selection: JobSelection,
    mode: AnalysisMode,
) -> dict:
    """
    모드별 예상 분석 비용을 규칙 기반으로 산정 (AI 호출 없음).

    각 Advisor 의 estimate_tokens 합산을 "단순화한 버전" — UI 표시용.
    실제 실행 시에는 각 Advisor 별로 정확한 값으로 재계산된다.

    Returns:
        {
            "mode":        str,
            "tokens_in":   int,
            "tokens_out":  int,
            "tokens_total": int,
            "time_sec":    float,
            "cost_usd":    float,
            "cost_krw":    int,
        }
    """
    coef = _MODE_COEFFICIENTS.get(mode, _MODE_COEFFICIENTS["smart"])

    tables_n = len(selection.tables)
    objects_n = selection.total_objects

    # 후보 수 = 전체 × 모드별 비율 (smart 는 15% 만 AI, deep 는 100%)
    table_candidates = int(tables_n * coef["rate_tables"])
    object_candidates = int(objects_n * coef["rate_objects"])
    total_candidates = table_candidates + object_candidates

    # 입력 토큰 = 후보당 평균 * 수
    tokens_in = total_candidates * coef["per_candidate_in"]
    # 출력 토큰 = 후보당 권고 1건 평균
    tokens_out = total_candidates * coef["per_candidate_out"]

    # smart 모드는 메타데이터 스캔 토큰을 추가 (AI 에는 안 가지만 프롬프트 구성 오버헤드)
    if mode == "smart":
        tokens_in += (tables_n + objects_n) * 500

    # 4개 Advisor 가 각자 분석하므로 전체적으로 소폭 증가 (서버 설정은 작음 — 보정 계수)
    # P1 에서는 단순 합산에 1.15 배 보정. P6 에서 advisor_learner 가 실측으로 갱신.
    tokens_in = int(tokens_in * 1.15)
    tokens_out = int(tokens_out * 1.15)

    # 최소 바닥값 — 대상이 아주 적을 때도 0원이 되지 않도록 (UI 표시 혼란 방지)
    if mode == "deep" and (tables_n + objects_n) > 0:
        tokens_in = max(tokens_in, 3000)
        tokens_out = max(tokens_out, 1000)

    cost_usd = (tokens_in * _PRICE_INPUT_PER_MTOK + tokens_out * _PRICE_OUTPUT_PER_MTOK) / 1_000_000
    cost_krw = int(round(cost_usd * _USD_TO_KRW))
    time_sec = (tokens_in + tokens_out) / _TOKENS_PER_SEC

    return {
        "mode": mode,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "tokens_total": tokens_in + tokens_out,
        "time_sec": round(time_sec, 1),
        "cost_usd": round(cost_usd, 3),
        "cost_krw": cost_krw,
    }
