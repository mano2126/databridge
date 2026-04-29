-- Q01. 활성 대출 고객 현황 (MySQL)
-- 수정: ORDER BY에 loan_id 추가 → 동점 시 일관된 정렬
SELECT
    c.cust_no, c.cust_nm, c.credit_grade, c.credit_score,
    p.prod_nm, l.loan_no, l.principal_amt, l.final_rate,
    l.execute_dt, l.maturity_dt, l.status_cd
FROM B01_Customer c
INNER JOIN E01_LoanContract l ON c.cust_id = l.cust_id
INNER JOIN C01_Product p ON l.prod_id = p.prod_id
WHERE l.status_cd = 'ACT'
ORDER BY l.principal_amt DESC, l.loan_id
LIMIT 200;