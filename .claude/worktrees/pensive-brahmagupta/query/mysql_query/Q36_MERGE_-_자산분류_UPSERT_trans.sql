SELECT
    g.class_cd,
    COUNT(*) AS loan_cnt,
    SUM(l.principal_amt) AS total_amt,
    CASE g.class_cd
        WHEN 'L'  THEN '요주의' WHEN 'D3' THEN '고정'
        WHEN 'D4' THEN '회수의문' WHEN 'D5' THEN '추정손실'
        ELSE '정상'
    END AS class_nm
FROM G01_AssetClassification g
INNER JOIN E01_LoanContract l ON g.loan_id = l.loan_id
WHERE g.class_ym = DATE_FORMAT(NOW(),'%Y%m')
GROUP BY g.class_cd
ORDER BY g.class_cd;