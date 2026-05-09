WITH OrderedProducts AS (
    SELECT 
        o.CustomerID,
        p.ProductName,
        p.ProductID,
        o.OrderDate
    FROM Orders o
    JOIN Products p ON o.ProductID = p.ProductID
)
SELECT 
    a.ProductName                              AS 상품A,
    b.ProductName                              AS 상품B,
    COUNT(DISTINCT a.CustomerID)               AS 함께구매고객수,
    ROUND(COUNT(DISTINCT a.CustomerID) * 100.0 
          / (SELECT COUNT(DISTINCT CustomerID) FROM Orders), 2) AS 전체고객대비율,
    GROUP_CONCAT(SUBSTRING(c.CustomerName, 1, 4) ORDER BY c.CustomerName SEPARATOR ', ')                                          AS 구매고객샘플
FROM OrderedProducts a
JOIN OrderedProducts b 
    ON a.CustomerID = b.CustomerID 
    AND a.ProductID < b.ProductID
JOIN Customers c ON a.CustomerID = c.CustomerID
GROUP BY a.ProductName, b.ProductName
HAVING (COUNT(DISTINCT a.CustomerID)) >= 1
ORDER BY 함께구매고객수 DESC, 전체고객대비율 DESC
LIMIT 10;