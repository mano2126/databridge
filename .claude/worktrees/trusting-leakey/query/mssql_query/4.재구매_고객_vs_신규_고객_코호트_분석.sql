SELECT '재구매고객' AS 구분,
    COUNT(DISTINCT c.CustomerID)         AS 고객수,
    ROUND(AVG(ord.총주문수), 1)          AS 평균주문수,
    ROUND(AVG(ord.총구매금액), 0)        AS 평균구매금액
FROM Customers c
JOIN (
    SELECT CustomerID,
           COUNT(OrderID)   AS 총주문수,
           SUM(TotalAmount) AS 총구매금액
    FROM Orders
    GROUP BY CustomerID
    HAVING COUNT(OrderID) >= 2
) ord ON c.CustomerID = ord.CustomerID

UNION ALL

SELECT '신규고객' AS 구분,
    COUNT(DISTINCT c.CustomerID),
    ROUND(AVG(ord.총주문수), 1),
    ROUND(AVG(ord.총구매금액), 0)
FROM Customers c
JOIN (
    SELECT CustomerID,
           COUNT(OrderID)   AS 총주문수,
           SUM(TotalAmount) AS 총구매금액
    FROM Orders
    GROUP BY CustomerID
    HAVING COUNT(OrderID) = 1
) ord ON c.CustomerID = ord.CustomerID

UNION ALL

SELECT '미구매고객', COUNT(*), 0, 0
FROM Customers c
WHERE NOT EXISTS (SELECT 1 FROM Orders o WHERE o.CustomerID = c.CustomerID);