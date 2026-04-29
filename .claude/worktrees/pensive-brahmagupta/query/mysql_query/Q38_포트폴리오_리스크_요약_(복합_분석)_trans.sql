-- Q38. 포트폴리오 리스크 요약 - MySQL (집계 서브쿼리 단순화)
WITH Portfolio AS (
    SELECT
        p.prod_nm, l.repay_tp,
        COUNT(*)             AS loan_cnt,
        SUM(l.principal_amt) AS total_principal,
        AVG(l.final_rate)    AS avg_rate,
        SUM(CASE WHEN g.class_cd IN ('D3','D4','D5') THEN l.principal_amt ELSE 0 END) AS npl_amt
    FROM E01_LoanContract l
    INNER JOIN C01_Product p ON l.prod_id = p.prod_id
    LEFT JOIN G02_LoanLossProvision g ON l.loan_id = g.loan_id
        AND g.base_ym = '202604'
    WHERE l.status_cd = 'ACT'
      AND l.loan_id BETWEEN 20000001 AND 20002000
    GROUP BY p.prod_nm, l.repay_tp
)
SELECT *,
    CAST(npl_amt / NULLIF(total_principal,0) * 100 AS DECIMAL(5,2)) AS npl_rate
FROM Portfolio
ORDER BY prod_nm, repay_tp;
