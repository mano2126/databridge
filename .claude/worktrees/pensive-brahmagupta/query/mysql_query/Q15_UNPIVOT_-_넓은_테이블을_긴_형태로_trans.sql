-- Q15. UNPIVOT - 넓은 테이블을 긴 형태로 - MySQL
-- 검증 고정 조건: loan_id 범위 고정
SELECT cust_id, attr_name, attr_value
FROM (
    SELECT cust_id, 'principal_amt' AS attr_name, CAST(principal_amt AS CHAR) AS attr_value
    FROM E01_LoanContract
    WHERE status_cd = 'ACT' AND loan_id BETWEEN 20000001 AND 20002000
    UNION ALL
    SELECT cust_id, 'final_rate', CAST(final_rate AS CHAR)
    FROM E01_LoanContract
    WHERE status_cd = 'ACT' AND loan_id BETWEEN 20000001 AND 20002000
    UNION ALL
    SELECT cust_id, 'term_month', CAST(term_month AS CHAR)
    FROM E01_LoanContract
    WHERE status_cd = 'ACT' AND loan_id BETWEEN 20000001 AND 20002000
) upvt
ORDER BY cust_id, attr_name;
