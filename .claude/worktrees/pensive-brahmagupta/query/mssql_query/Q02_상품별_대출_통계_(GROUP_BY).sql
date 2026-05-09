-- Q02. 상품별 대출 통계 (GROUP BY + HAVING)
SELECT
    p.prod_nm,
    p.prod_tp,
    COUNT(l.loan_id)          AS loan_cnt,
    SUM(l.principal_amt)      AS total_principal,
    AVG(l.final_rate)         AS avg_rate,
    MIN(l.final_rate)         AS min_rate,
    MAX(l.final_rate)         AS max_rate
FROM C01_Product p
INNER JOIN E01_LoanContract l ON p.prod_id = l.prod_id
WHERE l.status_cd IN ('ACT','CLS')
GROUP BY p.prod_id, p.prod_nm, p.prod_tp
HAVING COUNT(l.loan_id) >= 10
ORDER BY total_principal DESC;
