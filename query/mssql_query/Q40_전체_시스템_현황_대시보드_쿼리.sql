-- Q40. 전체 시스템 현황 대시보드 - MSSQL
-- 검증 고정 조건: 고정 날짜 '2026-04-02', FN01 서브쿼리 대체
SELECT '고객 수'         AS metric, CAST(COUNT(*) AS VARCHAR) AS val
FROM B01_Customer
UNION ALL
SELECT '활성 대출', CAST(COUNT(*) AS VARCHAR)
FROM E01_LoanContract WHERE status_cd='ACT'
UNION ALL
SELECT '총 대출잔액', CAST(FORMAT(
    (SELECT ISNULL(SUM(s.balance_amt),0) FROM E02_RepaySchedule s
     INNER JOIN E01_LoanContract l ON s.loan_id=l.loan_id
     WHERE l.status_cd='ACT' AND s.status_cd='SC'),'N0') AS VARCHAR)
UNION ALL
SELECT '연체 건수', CAST(COUNT(DISTINCT loan_id) AS VARCHAR)
FROM E02_RepaySchedule WHERE status_cd='OV'
UNION ALL
SELECT '오늘 거래', CAST(COUNT(*) AS VARCHAR)
FROM F01_Transaction WHERE CAST(tx_dt AS DATE)='2026-04-02'
UNION ALL
SELECT '미발송 알림', CAST(COUNT(*) AS VARCHAR)
FROM O01_NotificationLog WHERE result_cd='PE';
