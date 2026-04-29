-- Q05. 고객별 대출 잔액 요약 (CTE)
WITH LoanSummary AS (
    SELECT
        l.cust_id,
        COUNT(l.loan_id)       AS loan_cnt,
        SUM(l.principal_amt)   AS total_principal,
        SUM(s.balance_amt)     AS total_balance,
        MAX(l.final_rate)      AS max_rate,
        MIN(l.execute_dt)      AS first_loan_dt
    FROM E01_LoanContract l
    INNER JOIN E02_RepaySchedule s ON l.loan_id = s.loan_id
    WHERE l.status_cd = 'ACT'
      AND s.status_cd = 'SC'
    GROUP BY l.cust_id
)
SELECT
    c.cust_nm,
    c.credit_grade,
    ls.loan_cnt,
    ls.total_principal,
    ls.total_balance,
    ls.max_rate,
    ls.first_loan_dt
FROM LoanSummary ls
INNER JOIN B01_Customer c ON ls.cust_id = c.cust_id
ORDER BY ls.total_balance DESC
LIMIT 200;