-- Q30. 자산건전성 분류 + 충당금 현황 - MySQL
-- 서브쿼리 → LEFT JOIN으로 교체 (타임아웃 방지)
WITH AssetStatus AS (
    SELECT
        l.loan_id, l.loan_no, c.cust_nm, l.principal_amt,
        COALESCE(bal.balance, 0) AS balance
    FROM E01_LoanContract l
    INNER JOIN B01_Customer c ON l.cust_id = c.cust_id
    LEFT JOIN (
        SELECT loan_id, SUM(balance_amt) AS balance
        FROM E02_RepaySchedule
        WHERE status_cd = 'SC'
        GROUP BY loan_id
    ) bal ON bal.loan_id = l.loan_id
    WHERE l.status_cd = 'ACT'
      AND l.loan_id BETWEEN 20000001 AND 20001000
)
SELECT
    a.loan_id, a.loan_no, a.cust_nm, a.principal_amt, a.balance,
    p.provision_rate, p.provision_amt, p.class_cd,
    CASE p.class_cd
        WHEN 'L'  THEN '요주의' WHEN 'D3' THEN '고정'
        WHEN 'D4' THEN '회수의문' WHEN 'D5' THEN '추정손실'
        ELSE '정상'
    END AS class_nm
FROM AssetStatus a
LEFT JOIN G02_LoanLossProvision p ON a.loan_id = p.loan_id
    AND p.base_ym = '202604'
ORDER BY a.loan_id;
