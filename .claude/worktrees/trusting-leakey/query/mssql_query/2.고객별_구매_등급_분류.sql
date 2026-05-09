WITH CustomerStats AS (
    SELECT 
        c.CustomerID,
        c.CustomerName,
        COUNT(o.OrderID)    AS 총주문수,
        SUM(o.TotalAmount)  AS 총구매금액,
        MAX(o.OrderDate)    AS 최근주문일,
        DATEDIFF(day, MAX(o.OrderDate), GETDATE()) AS 최근주문경과일
    FROM Customers c
    LEFT JOIN Orders o ON c.CustomerID = o.CustomerID
    GROUP BY c.CustomerID, c.CustomerName
)
SELECT 
    CustomerID, CustomerName, 총주문수, 총구매금액, 최근주문일,
    CASE 
        WHEN 총구매금액 >= 1000000 AND 최근주문경과일 <= 30  THEN 'VIP'
        WHEN 총구매금액 >= 500000  AND 최근주문경과일 <= 90  THEN '우수'
        WHEN 총주문수  >= 1        AND 최근주문경과일 <= 180 THEN '일반'
        WHEN 총주문수  = 0                                    THEN '미구매'
        ELSE '휴면'
    END AS 고객등급,
    RANK() OVER (ORDER BY 총구매금액 DESC) AS 구매금액순위
FROM CustomerStats
ORDER BY 총구매금액 DESC;