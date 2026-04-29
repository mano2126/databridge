SELECT
    c.cust_nm,
    c.credit_score,
    c.credit_grade,
    l.loan_no,
    l.principal_amt,
    l.final_rate,
    l.status_cd
FROM B01_Customer c
INNER JOIN E01_LoanContract l ON c.cust_id = l.cust_id
WHERE c.credit_score > (SELECT AVG(credit_score) FROM B01_Customer WHERE credit_score IS NOT NULL)
  AND l.status_cd = 'ACT'
ORDER BY c.credit_score DESC, l.principal_amt DESC
LIMIT 200;