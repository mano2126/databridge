-- Q18. EXCEPT - 대출은 있지만 거래 없는 고객 (MSSQL)
-- EXCEPT는 자동으로 DISTINCT 처리 → SELECT DISTINCT 제거
SELECT cust_id FROM E01_LoanContract
EXCEPT
SELECT l.cust_id
FROM F01_Transaction t
INNER JOIN E01_LoanContract l ON t.loan_id = l.loan_id;
