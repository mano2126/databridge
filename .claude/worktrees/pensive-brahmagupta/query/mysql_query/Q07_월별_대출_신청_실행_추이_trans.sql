SELECT
    DATE_FORMAT(d.appl_dt, '%Y-%m')  AS ym,
    COUNT(d.appl_id)               AS appl_cnt,
    SUM(d.appl_amt)                AS appl_amt_sum,
    COUNT(l.loan_id)               AS exec_cnt,
    SUM(l.principal_amt)           AS exec_amt_sum,
    ROUND(COUNT(l.loan_id) * 100.0 / NULLIF(COUNT(d.appl_id), 0), 1) AS exec_rate
FROM D01_LoanApplication d
LEFT JOIN E01_LoanContract l ON d.appl_id = l.appl_id
WHERE d.appl_dt >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
GROUP BY DATE_FORMAT(d.appl_dt, '%Y-%m')
ORDER BY ym;