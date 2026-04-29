-- ============================================================
-- Q14. 상환 유형별 월간 실행 건수 PIVOT
-- DataBridge Studio - MySQL 테스트 쿼리
-- ============================================================

-- Q14. 상환 유형별 월간 실행 건수 PIVOT
SELECT 
    ym,
    SUM(CASE WHEN repay_tp = 'EM' THEN principal_amt ELSE 0 END) AS EM,
    SUM(CASE WHEN repay_tp = 'PM' THEN principal_amt ELSE 0 END) AS PM,
    SUM(CASE WHEN repay_tp = 'BL' THEN principal_amt ELSE 0 END) AS BL
FROM (
    SELECT
        DATE_FORMAT(execute_dt, '%Y-%m') AS ym,
        repay_tp,
        principal_amt
    FROM E01_LoanContract
    WHERE status_cd IN ('ACT','CL')
) src
GROUP BY ym
ORDER BY ym;