-- Q06. 고객별 대출 금액 순위 (MySQL)
-- 수정: PARTITION ORDER BY에 loan_id 추가 → 동점 순위 일관성
SELECT 
    c.cust_nm, c.credit_grade, l.loan_no,
    l.loan_id, l.principal_amt, l.final_rate,
    ROW_NUMBER() OVER (PARTITION BY c.credit_grade ORDER BY l.principal_amt DESC, l.loan_id) AS grade_rank,
    SUM(l.principal_amt)  OVER (PARTITION BY c.credit_grade) AS grade_total,
    ROUND(l.principal_amt * 100.0
          / SUM(l.principal_amt) OVER (PARTITION BY c.credit_grade), 2) AS pct_in_grade
FROM B01_Customer c
INNER JOIN E01_LoanContract l ON c.cust_id = l.cust_id
WHERE l.status_cd = 'ACT'
  AND c.credit_grade IS NOT NULL
ORDER BY c.credit_grade, grade_rank
LIMIT 200;