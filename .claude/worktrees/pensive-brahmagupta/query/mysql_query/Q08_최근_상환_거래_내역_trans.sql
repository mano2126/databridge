SELECT 
    c.cust_nm,
    l.loan_no,
    t.tx_no,
    t.tx_dt,
    t.tx_tp,
    t.tx_amt,
    t.principal_amt,
    t.interest_amt,
    t.fee_amt,
    t.result_cd,
    t.pay_method
FROM F01_Transaction t
INNER JOIN E01_LoanContract l ON t.loan_id = l.loan_id
INNER JOIN B01_Customer c ON l.cust_id = c.cust_id
WHERE t.result_cd = 'OK'
  AND t.tx_tp = 'RP'
ORDER BY t.tx_dt DESC
LIMIT 200;