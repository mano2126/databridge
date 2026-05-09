-- ============================================================
-- Q32. 거래 내역 누적합 + 분석 윈도우
-- DataBridge Studio - MSSQL 테스트 쿼리
-- ============================================================

-- Q32. 거래 내역 누적합 + 분석 윈도우
SELECT
    t.tx_no,
    t.tx_dt,
    t.tx_tp,
    t.tx_amt,
    t.principal_amt,
    t.interest_amt,
    SUM(t.principal_amt) OVER (PARTITION BY t.loan_id ORDER BY t.tx_dt
        ROWS UNBOUNDED PRECEDING) AS cum_principal,
    SUM(t.interest_amt)  OVER (PARTITION BY t.loan_id ORDER BY t.tx_dt
        ROWS UNBOUNDED PRECEDING) AS cum_interest,
    t.tx_amt - LAG(t.tx_amt) OVER (PARTITION BY t.loan_id ORDER BY t.tx_dt) AS amt_diff,
    ROW_NUMBER() OVER (PARTITION BY t.loan_id ORDER BY t.tx_dt) AS tx_seq
FROM F01_Transaction t
WHERE t.result_cd = 'OK'
ORDER BY t.loan_id, t.tx_dt;
