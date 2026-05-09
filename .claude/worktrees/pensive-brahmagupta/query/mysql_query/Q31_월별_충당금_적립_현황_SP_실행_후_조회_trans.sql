SELECT
    g.class_cd,
    COUNT(*) AS loan_cnt,
    SUM(g.balance_amt) AS total_balance,
    AVG(g.provision_rate) AS avg_rate,
    SUM(g.provision_amt) AS total_provision
FROM G02_LoanLossProvision g
WHERE g.base_ym = DATE_FORMAT(NOW(),'%Y%m')
GROUP BY g.class_cd
ORDER BY g.class_cd;