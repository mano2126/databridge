-- Q07. 월별 대출 신청/실행 추이
SELECT
    FORMAT(d.appl_dt, 'yyyy-MM')  AS ym,
    COUNT(d.appl_id)               AS appl_cnt,
    SUM(d.appl_amt)                AS appl_amt_sum,
    COUNT(l.loan_id)               AS exec_cnt,
    SUM(l.principal_amt)           AS exec_amt_sum,
    ROUND(COUNT(l.loan_id) * 100.0 / NULLIF(COUNT(d.appl_id), 0), 1) AS exec_rate
FROM D01_LoanApplication d
LEFT JOIN E01_LoanContract l ON d.appl_id = l.appl_id
WHERE d.appl_dt >= DATEADD(MONTH, -12, GETDATE())
GROUP BY FORMAT(d.appl_dt, 'yyyy-MM')
ORDER BY ym;
