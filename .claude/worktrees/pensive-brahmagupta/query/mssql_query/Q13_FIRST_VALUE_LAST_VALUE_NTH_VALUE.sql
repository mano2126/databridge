-- Q13. FIRST_VALUE, LAST_VALUE, NTH_VALUE - MSSQL
-- 검증 고정 조건: loan_id 범위 고정
SELECT
    l.loan_id, l.cust_id, l.principal_amt, l.execute_dt,
    FIRST_VALUE(l.execute_dt) OVER (PARTITION BY l.cust_id ORDER BY l.execute_dt, l.loan_id) AS first_loan_dt,
    LAST_VALUE(l.execute_dt)  OVER (PARTITION BY l.cust_id ORDER BY l.execute_dt, l.loan_id
                                    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_loan_dt,
    COUNT(*)                  OVER (PARTITION BY l.cust_id) AS cust_loan_cnt
FROM E01_LoanContract l
WHERE l.loan_id BETWEEN 20000001 AND 20010000
ORDER BY l.loan_id;
