-- Q20. 나이/기간 계산 - MySQL (DATEDIFF(YEAR) 방식과 동일하게)
SELECT
    cust_nm, birth_dt,
    YEAR('2026-04-05') - YEAR(birth_dt)
        - CASE WHEN DATE_FORMAT(birth_dt,'%m%d') > '0405' THEN 1 ELSE 0 END AS age,
    CASE
        WHEN YEAR('2026-04-05') - YEAR(birth_dt)
             - CASE WHEN DATE_FORMAT(birth_dt,'%m%d') > '0405' THEN 1 ELSE 0 END < 30 THEN '20대'
        WHEN YEAR('2026-04-05') - YEAR(birth_dt)
             - CASE WHEN DATE_FORMAT(birth_dt,'%m%d') > '0405' THEN 1 ELSE 0 END < 40 THEN '30대'
        WHEN YEAR('2026-04-05') - YEAR(birth_dt)
             - CASE WHEN DATE_FORMAT(birth_dt,'%m%d') > '0405' THEN 1 ELSE 0 END < 50 THEN '40대'
        ELSE '50대 이상'
    END AS age_group
FROM B01_Customer
WHERE birth_dt IS NOT NULL
ORDER BY cust_nm;
