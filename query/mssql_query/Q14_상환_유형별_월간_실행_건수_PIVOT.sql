-- ============================================================
-- Q14. 상환 유형별 월간 실행 건수 PIVOT
-- DataBridge Studio - MSSQL 테스트 쿼리
-- ============================================================

-- Q14. 상환 유형별 월간 실행 건수 PIVOT
SELECT *
FROM (
    SELECT
        FORMAT(execute_dt, 'yyyy-MM') AS ym,
        repay_tp,
        principal_amt
    FROM E01_LoanContract
    WHERE status_cd IN ('ACT','CL')
) src
PIVOT (
    SUM(principal_amt)
    FOR repay_tp IN ([EM], [PM], [BL])
) pvt
ORDER BY ym;
