-- Q19. 대출 만기 도래 현황 - MSSQL (날짜 인라인, 요일명 제거)
SELECT
    c.cust_nm, l.loan_no, l.execute_dt, l.maturity_dt,
    DATEDIFF(DAY, '2026-04-05', l.maturity_dt)   AS days_to_maturity,
    DATEDIFF(MONTH, l.execute_dt, l.maturity_dt)  AS total_months,
    DATEADD(MONTH, 1, l.maturity_dt)              AS grace_dt,
    EOMONTH(l.maturity_dt)                        AS maturity_eom,
    YEAR(l.maturity_dt)                           AS maturity_yr
FROM E01_LoanContract l
INNER JOIN B01_Customer c ON l.cust_id = c.cust_id
WHERE l.status_cd = 'ACT'
  AND l.maturity_dt BETWEEN '2026-04-05' AND DATEADD(MONTH, 3, '2026-04-05')
ORDER BY l.maturity_dt, l.loan_no;
