-- Q03. 연체 스케줄 현황 (다중 JOIN)
SELECT TOP 200
    c.cust_nm,
    c.mobile_no,
    l.loan_no,
    l.principal_amt,
    s.seq_no,
    s.due_dt,
    s.balance_amt,
    s.overdue_days,
    s.overdue_int,
    DATEDIFF(DAY, s.due_dt, GETDATE()) AS days_past_due
FROM E02_RepaySchedule s
INNER JOIN E01_LoanContract l ON s.loan_id = l.loan_id
INNER JOIN B01_Customer c ON l.cust_id = c.cust_id
WHERE s.status_cd = 'OV'
  AND s.overdue_days > 0
ORDER BY s.overdue_days DESC, l.principal_amt DESC;
