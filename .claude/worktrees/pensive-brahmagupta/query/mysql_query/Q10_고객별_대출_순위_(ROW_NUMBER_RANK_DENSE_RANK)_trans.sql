-- Q10. 고객별 대출 순위 (ROW_NUMBER, RANK, DENSE_RANK) - MySQL
-- 검증 고정 조건: 2021년 실행 대출만 (경계값 문제 제거)
SELECT
    c.cust_nm,
    l.loan_no,
    l.principal_amt,
    ROW_NUMBER() OVER (PARTITION BY l.cust_id ORDER BY l.principal_amt DESC, l.loan_no) AS rn,
    RANK()       OVER (PARTITION BY l.cust_id ORDER BY l.principal_amt DESC, l.loan_no) AS rnk,
    DENSE_RANK() OVER (ORDER BY l.principal_amt DESC) AS overall_rank
FROM E01_LoanContract l
INNER JOIN B01_Customer c ON l.cust_id = c.cust_id
WHERE l.status_cd = 'ACT'
  AND l.execute_dt BETWEEN '2021-01-01' AND '2021-12-31'
ORDER BY l.loan_no;
