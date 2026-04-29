SELECT
    cust_nm, birth_dt,
    TIMESTAMPDIFF(YEAR, birth_dt, '2026-04-05')
        - CASE WHEN MONTH(birth_dt)*100+DAY(birth_dt) > MONTH('2026-04-05')*100+DAY('2026-04-05')
               THEN 1 ELSE 0 END AS age,
    CASE
        WHEN TIMESTAMPDIFF(YEAR, birth_dt, '2026-04-05')
             - CASE WHEN MONTH(birth_dt)*100+DAY(birth_dt) > 405 THEN 1 ELSE 0 END < 30 THEN '20대'
        WHEN TIMESTAMPDIFF(YEAR, birth_dt, '2026-04-05')
             - CASE WHEN MONTH(birth_dt)*100+DAY(birth_dt) > 405 THEN 1 ELSE 0 END < 40 THEN '30대'
        WHEN TIMESTAMPDIFF(YEAR, birth_dt, '2026-04-05')
             - CASE WHEN MONTH(birth_dt)*100+DAY(birth_dt) > 405 THEN 1 ELSE 0 END < 50 THEN '40대'
        ELSE '50대 이상'
    END AS age_group
FROM B01_Customer
WHERE birth_dt IS NOT NULL
ORDER BY cust_nm;