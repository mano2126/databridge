-- Q19. 대출 만기 도래 현황 - MySQL (날짜 인라인, 요일명 제거)
SELECT
    c.cust_nm, l.loan_no, l.execute_dt, l.maturity_dt,
    DATEDIFF(l.maturity_dt, '2026-04-05')        AS days_to_maturity,
    TIMESTAMPDIFF(MONTH, l.execute_dt, l.maturity_dt) AS total_months,
    DATE_ADD(l.maturity_dt, INTERVAL 1 MONTH)    AS grace_dt,
    LAST_DAY(l.maturity_dt)                      AS maturity_eom,
    YEAR(l.maturity_dt)                          AS maturity_yr
FROM E01_LoanContract l
INNER JOIN B01_Customer c ON l.cust_id = c.cust_id
WHERE l.status_cd = 'ACT'
  AND l.maturity_dt BETWEEN '2026-04-05' AND DATE_ADD('2026-04-05', INTERVAL 3 MONTH)
ORDER BY l.maturity_dt, l.loan_no;