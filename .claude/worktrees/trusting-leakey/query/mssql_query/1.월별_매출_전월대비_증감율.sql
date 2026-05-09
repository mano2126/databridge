-- 1. 월별 매출 + 전월 대비 증감률 (윈도우 함수)
WITH __agg AS (
    SELECT
        FORMAT(o.OrderDate, 'yyyy-MM') AS 월,
        COUNT(DISTINCT o.CustomerID)      AS 주문고객수,
        COUNT(o.OrderID)                  AS 주문건수,
        SUM(o.TotalAmount)                AS 월매출
    FROM Orders o
    GROUP BY FORMAT(o.OrderDate, 'yyyy-MM')
)
SELECT 월, 주문고객수, 주문건수, 월매출,
    LAG(월매출) OVER (ORDER BY 월) AS 전월매출,
    ROUND(
        (월매출 - LAG(월매출) OVER (ORDER BY 월))
        / NULLIF(LAG(월매출) OVER (ORDER BY 월), 0) * 100, 2
    ) AS 전월대비증감률
FROM __agg
ORDER BY 월;