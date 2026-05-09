-- Q29. 조건부 검색 - MSSQL
-- 검증 고정 조건: 2021년 loan_no 범위
SELECT c.cust_nm, l.loan_no, l.principal_amt, l.status_cd
FROM E01_LoanContract l
INNER JOIN B01_Customer c ON l.cust_id = c.cust_id
WHERE l.status_cd = 'ACT'
  AND l.principal_amt >= 10000000
  AND l.execute_dt BETWEEN '2021-01-01' AND '2021-12-31'
ORDER BY l.loan_no;
