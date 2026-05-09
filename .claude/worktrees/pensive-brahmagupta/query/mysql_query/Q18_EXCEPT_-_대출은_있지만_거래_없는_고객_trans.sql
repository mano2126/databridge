-- ============================================================
-- Q18. EXCEPT - 대출은 있지만 거래 없는 고객
-- DataBridge Studio - MySQL 테스트 쿼리
-- ============================================================

-- Q18. EXCEPT - 대출은 있지만 거래 없는 고객
SELECT DISTINCT cust_id FROM E01_LoanContract
WHERE cust_id NOT IN (
    SELECT DISTINCT l.cust_id
    FROM F01_Transaction t
    INNER JOIN E01_LoanContract l ON t.loan_id = l.loan_id
    WHERE l.cust_id IS NOT NULL
);