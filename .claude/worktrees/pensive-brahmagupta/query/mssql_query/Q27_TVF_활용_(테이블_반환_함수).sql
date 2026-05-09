-- Q27. 활성 대출 잔액 조회 (TVF 대체) - MSSQL
-- 검증 고정 조건: loan_id 범위 고정 (타임아웃 방지)
SELECT
    l.loan_id, l.loan_no, c.cust_id, c.cust_nm,
    l.principal_amt, l.final_rate, l.execute_dt, l.maturity_dt, l.status_cd,
    ISNULL((SELECT SUM(s.balance_amt) FROM E02_RepaySchedule s
             WHERE s.loan_id = l.loan_id AND s.status_cd = 'SC'), 0) AS current_balance
FROM E01_LoanContract l
INNER JOIN B01_Customer c ON l.cust_id = c.cust_id
WHERE l.status_cd = 'ACT'
  AND l.loan_id BETWEEN 20000001 AND 20001000
ORDER BY l.loan_id;
