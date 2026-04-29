"""
app/core/advisor/ — AI DBA Consultant 권고 엔진
v88 P5 (2026-04-23)

4가지 권고 카테고리 전체 활성화:
  - ServerAdvisor  (P2 ✅)
  - TableAdvisor   (P3 ✅)
  - ObjectAdvisor  (P4 ✅)
  - IndexAdvisor   (P5 ✅)

P6 예정: advisor_learner — 권고 수용 결과를 KB 로 축적.
"""

from app.core.advisor.base_advisor import (
    BaseAdvisor,
    JobSelection,
    AnalysisContext,
    AnalysisMode,
    Category,
    Severity,
    Recommendation,
    estimate_analysis_cost,
)
from app.core.advisor.server_advisor import ServerAdvisor
from app.core.advisor.table_advisor  import TableAdvisor
from app.core.advisor.object_advisor import ObjectAdvisor
from app.core.advisor.index_advisor  import IndexAdvisor

__all__ = [
    "BaseAdvisor",
    "JobSelection",
    "AnalysisContext",
    "AnalysisMode",
    "Category",
    "Severity",
    "Recommendation",
    "estimate_analysis_cost",
    "ServerAdvisor",
    "TableAdvisor",
    "ObjectAdvisor",
    "IndexAdvisor",
    "get_all_advisors",
]


def get_all_advisors() -> list[BaseAdvisor]:
    """
    모든 활성 Advisor 인스턴스 리스트.
    순서: Server → Table → Index → Object (중요도/응답속도 순)
    """
    return [
        ServerAdvisor(),
        TableAdvisor(),
        IndexAdvisor(),
        ObjectAdvisor(),
    ]
