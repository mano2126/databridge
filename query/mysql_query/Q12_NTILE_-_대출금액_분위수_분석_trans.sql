SELECT
    cust_id, loan_no, principal_amt,
    NTILE(4)  OVER (ORDER BY principal_amt, loan_no) AS quartile,
    NTILE(10) OVER (ORDER BY principal_amt, loan_no) AS decile,
    PERCENT_RANK() OVER (ORDER BY principal_amt, loan_no) AS pct_rank,
    CUME_DIST()    OVER (ORDER BY principal_amt, loan_no) AS cum_dist
FROM E01_LoanContract
WHERE status_cd = 'ACT'
  AND execute_dt BETWEEN '2021-01-01' AND '2021-12-31'
ORDER BY loan_no;