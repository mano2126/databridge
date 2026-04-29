-- ============================================================
-- Q37. 이상거래 탐지 (통계 기반)
-- DataBridge Studio - MySQL 테스트 쿼리
-- ============================================================

-- Q37. 이상거래 탐지 (통계 기반)
WITH TxStats AS (
    SELECT
        loan_id,
        AVG(tx_amt)    AS avg_amt,
        STDDEV(tx_amt)  AS std_amt
    FROM F01_Transaction
    WHERE result_cd = 'OK'
    GROUP BY loan_id
)
SELECT
    t.tx_no,
    t.tx_dt,
    t.tx_amt,
    s.avg_amt,
    s.std_amt,
    (t.tx_amt - s.avg_amt) / NULLIF(s.std_amt, 0) AS z_score
FROM F01_Transaction t
INNER JOIN TxStats s ON t.loan_id = s.loan_id
WHERE ABS((t.tx_amt - s.avg_amt) / NULLIF(s.std_amt, 0)) > 3
  AND t.result_cd = 'OK'
ORDER BY ABS((t.tx_amt - s.avg_amt) / NULLIF(s.std_amt, 0)) DESC;