"""
v95_p9: view_analyzer 진단 로그 보강 (timeout 본질 진단용)

기존 view_analyzer.py 의 analyze() 마지막에 아래 로그 한 줄을 추가하면 됨.
LogViewer 에서 'view-analyzer' 키워드로 필터하여 6개 위험 View 의 분기를 확인.

이 파일은 참고용 — 실제로는 기존 view_analyzer.py 의 analyze() 함수 끝에
아래 _log_decision() 호출만 추가하는 형태로 적용.
"""
import logging

logger = logging.getLogger("databridge.view_analyzer")


def log_view_decision(view_name: str, db_type: str, patterns: dict,
                      is_risky: bool, is_large: bool,
                      safe_mode: bool, applied_query: str = ""):
    """
    View 검증 분기 결정을 KB로 남김.
    LogViewer 에서 'view-analyzer' 검색하면 한눈에 보임.
    """
    pat_str = ",".join([k for k, v in patterns.items() if v]) or "none"
    logger.info(
        f"[view-analyzer] {view_name} "
        f"db={db_type} patterns={pat_str} "
        f"risky={is_risky} large={is_large} "
        f"→ safe_mode={safe_mode}"
    )
    if applied_query:
        # 너무 길면 자르기 (500자)
        q = applied_query.replace("\n", " ").strip()
        if len(q) > 500:
            q = q[:500] + "...(truncated)"
        logger.info(f"[view-analyzer] {view_name} applied_query: {q}")


def log_view_test_result(view_name: str, target_db: str,
                          elapsed_ms: int, timeout_ms: int,
                          success: bool, row_count: int = 0,
                          error: str = ""):
    """
    View 검증 테스트 결과 로그 (timeout 본질 분석용).
    소스 vs 타겟 소요 비교를 위해 일관된 포맷.
    """
    status = "OK" if success else "TIMEOUT" if elapsed_ms >= timeout_ms else "FAIL"
    logger.info(
        f"[view-test] {view_name} target={target_db} "
        f"status={status} elapsed={elapsed_ms}ms timeout={timeout_ms}ms "
        f"rows={row_count}"
        + (f" err={error[:200]}" if error else "")
    )
