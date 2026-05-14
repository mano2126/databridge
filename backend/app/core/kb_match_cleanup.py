"""
DataBridge KB 매칭 결과 자동 정화 — hotfix_026
=================================================

본부장님 환경 본질 (2026-05-11 오후):
  KB 에 깨진 SQL 5개 등록됨:
    - uspGetBillOfMaterials (CTE FROM 누락)
    - uspGetManagerEmployees (CTE FROM 누락)
    - uspGetWhereUsedProductID (CTE FROM 누락)
    - vSalesPersonSalesByFiscalYears (PIVOT 미변환)
    - vAdditionalContactInfo (ExtractValue 인자 문제)

  use_count = 2~3 (매번 매칭됨)
  → 본부장님 11번째 통찰: "학습한게 영향 받아야"

처방: KB-MATCH 결과를 받은 직후 자동 정화:
  1. CTE FROM 누락 자동 보강 (cte_from_fixer)
  2. PIVOT → CASE WHEN 자동 변환 (pivot_to_case_when)
  3. T-SQL 잔재 정화 (tsql_residue_cleaner — hotfix_025)

본부장님 모토:
  #4 (본질에 충실, KB = 살아있는 자산)
  #14 (4-way collision 방지 — KB 등록은 그대로, 매칭 결과만 정화)
"""
from __future__ import annotations
import logging
from typing import Tuple, List

_log = logging.getLogger("databridge.kb_match_cleanup")


def cleanup_kb_match_result(tgt_sql: str, obj_type: str = "",
                             obj_name: str = "") -> Tuple[str, List[str]]:
    """KB 매칭 결과 SQL 을 자동 정화.
    
    본부장님 환경 5개 깨진 KB 본질 처방.
    
    Returns:
        (cleaned_sql, applied_fixes)
    """
    fixes = []
    result = tgt_sql
    
    if not result:
        return result, fixes
    
    # 1. CTE FROM 누락 자동 보강
    try:
        from app.core.cte_from_fixer import fix_cte_missing_from
        result, cte_fixes = fix_cte_missing_from(result)
        fixes.extend(cte_fixes)
    except Exception as e:
        _log.warning("[kb_match_cleanup] CTE fixer 실패 (무시): %s", e)
    
    # 2. PIVOT → CASE WHEN 결정적 변환
    try:
        from app.core.pivot_to_case_when import convert_pivot_to_case_when
        result, pivot_fixes = convert_pivot_to_case_when(result)
        fixes.extend(pivot_fixes)
    except Exception as e:
        _log.warning("[kb_match_cleanup] PIVOT converter 실패 (무시): %s", e)
    
    # 3. T-SQL 잔재 정화 (hotfix_025)
    try:
        from app.core.tsql_residue_cleaner import clean_tsql_residues
        result, residue_fixes = clean_tsql_residues(result, obj_type, obj_name)
        fixes.extend(residue_fixes)
    except Exception as e:
        _log.warning("[kb_match_cleanup] residue cleaner 실패 (무시): %s", e)
    
    # ════════════════════════════════════════════════════════
    # v95_p107 hotfix_103 (2026-05-13 본부장님 환경 21:17 실데이터):
    #   본부장님 통찰: KB 매칭 경로에 post_process_sql 미호출 발견.
    #   AI 폴백 경로는 R-100/R-103 정화 작동 (uPurchaseOrderDetail R-020 작동 검증).
    #   KB 매칭 경로는 cleanup_kb_match_result 만 호출, R-100~R-110 미적용.
    #
    # 실데이터 (21:17:17):
    #   ufnGetStock: 'intBEGIN' 그대로 → 1064
    #   ufnGetProductListPrice: 'MONEY DETERMINISTIC' 그대로 → 1064
    #
    # 본부장님 모토 #14 (4-way collision):
    #   KB 등록은 그대로, 매칭 결과만 정화 — post_process_sql 호출 추가.
    # ════════════════════════════════════════════════════════
    try:
        from app.core.sql_post_processor import post_process_sql
        result, pp_fixes = post_process_sql(result, obj_name, verbose=False)
        if pp_fixes:
            fixes.extend([f"PP:{f}" for f in pp_fixes])
    except Exception as e:
        _log.warning("[kb_match_cleanup-h103] post_process_sql 실패 (무시): %s", e)
    
    if fixes:
        _log.info(
            "[v95_p107-KB-CLEANUP] %s [%s] KB 매칭 결과 자동 정화: %s",
            obj_type, obj_name, fixes,
        )
    
    return result, fixes
