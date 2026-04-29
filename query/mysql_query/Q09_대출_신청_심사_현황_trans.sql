-- Q09. 대출 신청 심사 현황 (MySQL)
-- 수정: ar.score → ar.total_score, ar.grade → ar.grade_cd, ar.result_cd 제거
SELECT
    d.appl_no,
    c.cust_nm,
    c.credit_score,
    d.appl_amt,
    d.appl_channel,
    d.status_cd,
    ar.total_score  AS auto_score,
    ar.grade_cd     AS auto_grade,
    ar.pd_prob,
    ar.run_dt       AS review_dt
FROM D01_LoanApplication d
INNER JOIN B01_Customer c ON d.cust_id = c.cust_id
LEFT  JOIN D03_AutoReviewResult ar ON d.appl_id = ar.appl_id
WHERE d.appl_dt >= DATE_SUB(NOW(), INTERVAL 3 MONTH)
ORDER BY d.appl_dt DESC, d.appl_no
LIMIT 200;