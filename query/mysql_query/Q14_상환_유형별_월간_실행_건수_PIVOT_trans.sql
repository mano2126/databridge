SELECT 
    ym,
    COALESCE(SUM(CASE WHEN repay_tp = 'EM' THEN principal_amt END), 0) AS EM,
    COALESCE(SUM(CASE WHEN repay_tp = 'PM' THEN principal_amt END), 0) AS PM,
    COALESCE(SUM(CASE WHEN repay_tp = 'BL' THEN principal_amt END), 0) AS BL
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