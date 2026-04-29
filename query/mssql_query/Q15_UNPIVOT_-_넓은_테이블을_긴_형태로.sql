-- Q15. UNPIVOT - 넓은 테이블을 긴 형태로 - MSSQL
-- 검증 고정 조건: loan_id 범위 고정
SELECT cust_id, attr_name, attr_value
FROM (
    SELECT
        cust_id,
        CAST(principal_amt AS NVARCHAR) AS principal_amt,
        CAST(final_rate    AS NVARCHAR) AS final_rate,
        CAST(term_month    AS NVARCHAR) AS term_month
    FROM E01_LoanContract
    WHERE status_cd = 'ACT'
      AND loan_id BETWEEN 20000001 AND 20002000
) src
UNPIVOT (
    attr_value FOR attr_name IN (principal_amt, final_rate, term_month)
) upvt
ORDER BY cust_id, attr_name;
