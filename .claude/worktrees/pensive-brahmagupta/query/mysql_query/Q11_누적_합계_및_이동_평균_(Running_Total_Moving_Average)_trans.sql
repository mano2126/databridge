SELECT
    t.tx_no,
    t.tx_dt,
    t.tx_amt,
    t.principal_amt,
    SUM(t.principal_amt)
        OVER (ORDER BY t.tx_no ROWS UNBOUNDED PRECEDING) AS cum_principal,
    AVG(t.tx_amt)
        OVER (ORDER BY t.tx_no ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS moving_avg_7
FROM F01_Transaction t
ORDER BY t.tx_no;