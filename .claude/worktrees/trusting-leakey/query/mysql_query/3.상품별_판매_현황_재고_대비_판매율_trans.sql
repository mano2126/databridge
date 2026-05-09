-- 3. 상품별 판매 현황 + 재고 대비 판매율 (MySQL)
-- ※ Orders 테이블 스키마: OrderID, CustomerID, ProductID, OrderDate, TotalAmount
--   Quantity 컬럼 없음 → 주문건수(COUNT) / 총매출(SUM TotalAmount) 으로 대체
SELECT 
    p.ProductID,
    p.ProductName,
    p.Price,
    p.Stock                                        AS 현재재고,
    IFNULL(COUNT(o.OrderID), 0)                    AS 총판매건수,
    IFNULL(SUM(o.TotalAmount), 0)                  AS 총판매금액,
    ROUND(
        IFNULL(COUNT(o.OrderID), 0) * 1.0
        / NULLIF(p.Stock + IFNULL(COUNT(o.OrderID), 0), 0) * 100
    , 1)                                           AS 판매율,
    CASE WHEN p.Stock = 0  THEN '품절'
         WHEN p.Stock < 10 THEN '재고부족'
         ELSE '정상' END                           AS 재고상태
FROM Products p
LEFT JOIN Orders o ON p.ProductID = o.ProductID
GROUP BY p.ProductID, p.ProductName, p.Price, p.Stock
HAVING COUNT(o.OrderID) > 0
    OR EXISTS (
        SELECT 1 FROM Products pp
        WHERE pp.ProductID = p.ProductID AND pp.Stock < 5
    )
ORDER BY 총판매금액 DESC
LIMIT 20;