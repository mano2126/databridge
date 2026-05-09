-- Q17. MySQL (EXISTS 변환)
SELECT cust_id FROM E01_LoanContract
WHERE status_cd IN ('ACT','CL')
  AND EXISTS (
    SELECT 1 FROM E02_RepaySchedule s
    INNER JOIN E01_LoanContract l2 ON s.loan_id = l2.loan_id
    WHERE l2.cust_id = E01_LoanContract.cust_id AND s.status_cd = 'OV'
)
ORDER BY cust_id;
