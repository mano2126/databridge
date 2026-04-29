-- Q16. UNION ALL - 고객 이벤트 통합 타임라인 (MSSQL)
-- event_dt를 DATE로 캐스팅 (시간 소수점 차이 제거)
SELECT 'APPL' AS event_tp, cust_id, CAST(appl_dt AS DATE) AS event_dt,
       appl_no AS ref_no, CAST(appl_amt AS NVARCHAR) AS amt_str
FROM D01_LoanApplication
UNION ALL
SELECT 'EXEC', cust_id, CAST(execute_dt AS DATE),
       loan_no, CAST(principal_amt AS NVARCHAR)
FROM E01_LoanContract
UNION ALL
SELECT 'TX', l.cust_id, CAST(t.tx_dt AS DATE),
       t.tx_no, CAST(t.tx_amt AS NVARCHAR)
FROM F01_Transaction t
INNER JOIN E01_LoanContract l ON t.loan_id = l.loan_id
ORDER BY cust_id, event_dt;
