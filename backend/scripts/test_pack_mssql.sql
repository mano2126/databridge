-- ════════════════════════════════════════════════════════════════════════
-- DataBridge Studio 테스트 패키지 — MSSQL 원본
-- 작성: 2026-04-28 / 본부장님 이관·검증 시나리오 검증용
-- 
-- 목적:
--   1. SP_STATRECORD 와 비슷한 구조 (날짜 파라미터 + 집계 INSERT)
--   2. 의존 테이블 같이 포함 → tbl_rec_data 누락 같은 문제 회피
--   3. 다양한 데이터 타입 커버 (VARCHAR, INT, DECIMAL, DATETIME)
--   4. 충분한 데이터 (집계 결과 검증 가능)
-- ════════════════════════════════════════════════════════════════════════

USE testdb;
GO

-- ── 1. 의존 테이블 (원본 데이터) ──────────────────────────────────────
IF OBJECT_ID('tbl_test_sales', 'U') IS NOT NULL DROP TABLE tbl_test_sales;
GO

CREATE TABLE tbl_test_sales (
    sale_date     VARCHAR(8)    NOT NULL,    -- YYYYMMDD
    sale_hour     VARCHAR(2)    NOT NULL,    -- HH
    user_id       VARCHAR(20)   NOT NULL,
    product_code  VARCHAR(10)   NOT NULL,
    region_code   VARCHAR(5)    NOT NULL,
    sale_type     CHAR(1)       NOT NULL,    -- 'I'/'O'/'C'
    quantity      INT           NOT NULL DEFAULT 0,
    amount        DECIMAL(15,2) NOT NULL DEFAULT 0,
    discount_rate DECIMAL(5,2)  NOT NULL DEFAULT 0,
    created_at    DATETIME      NOT NULL DEFAULT GETDATE(),
    PRIMARY KEY (sale_date, sale_hour, user_id, product_code)
);
GO

-- ── 2. 집계 결과 테이블 (SP 가 INSERT 할 곳) ──────────────────────────
IF OBJECT_ID('tbl_test_stat', 'U') IS NOT NULL DROP TABLE tbl_test_stat;
GO

CREATE TABLE tbl_test_stat (
    stat_date       VARCHAR(8)    NOT NULL,
    user_id         VARCHAR(20)   NOT NULL,
    product_code    VARCHAR(10)   NOT NULL,
    region_code     VARCHAR(5)    NOT NULL,
    total_qty       INT           NOT NULL DEFAULT 0,
    total_amount    DECIMAL(18,2) NOT NULL DEFAULT 0,
    in_cnt          INT           NOT NULL DEFAULT 0,
    out_cnt         INT           NOT NULL DEFAULT 0,
    cancel_cnt      INT           NOT NULL DEFAULT 0,
    avg_discount    DECIMAL(5,2)  NOT NULL DEFAULT 0,
    PRIMARY KEY (stat_date, user_id, product_code)
);
GO

-- ── 3. 샘플 데이터 (날짜 3일치 × 유저 3명 × 상품 3종 × 지역 2개) ─────
DELETE FROM tbl_test_sales;
GO

DECLARE @i INT = 0;
WHILE @i < 50
BEGIN
    INSERT INTO tbl_test_sales (sale_date, sale_hour, user_id, product_code, region_code, sale_type, quantity, amount, discount_rate)
    VALUES (
        CASE (@i % 3) WHEN 0 THEN '20240101' WHEN 1 THEN '20240102' ELSE '20240103' END,
        RIGHT('00' + CAST((@i % 24) AS VARCHAR), 2),
        CASE (@i % 3) WHEN 0 THEN 'USER001' WHEN 1 THEN 'USER002' ELSE 'USER003' END,
        CASE (@i % 3) WHEN 0 THEN 'PRD001' WHEN 1 THEN 'PRD002' ELSE 'PRD003' END,
        CASE (@i % 2) WHEN 0 THEN 'SEOUL' ELSE 'BUSAN' END,
        CASE (@i % 3) WHEN 0 THEN 'I' WHEN 1 THEN 'O' ELSE 'C' END,
        (@i % 10) + 1,
        ((@i % 10) + 1) * 10000.00,
        (@i % 5) * 1.50
    );
    SET @i = @i + 1;
END
GO

-- ── 4. 테스트용 PROCEDURE (SP_STATRECORD 와 같은 패턴) ─────────────────
IF OBJECT_ID('SP_TEST_DAILY_AGG', 'P') IS NOT NULL DROP PROCEDURE SP_TEST_DAILY_AGG;
GO

CREATE PROCEDURE SP_TEST_DAILY_AGG
    @p_sdate VARCHAR(8),    -- YYYYMMDD 형식
    @p_edate VARCHAR(8)
AS
BEGIN
    SET NOCOUNT ON;
    
    -- 1. 기존 집계 삭제
    DELETE FROM tbl_test_stat
    WHERE stat_date BETWEEN @p_sdate AND @p_edate;
    
    -- 2. 새 집계 INSERT
    INSERT INTO tbl_test_stat (
        stat_date, user_id, product_code, region_code,
        total_qty, total_amount,
        in_cnt, out_cnt, cancel_cnt,
        avg_discount
    )
    SELECT
        sale_date,
        user_id,
        product_code,
        MAX(region_code),
        SUM(quantity),
        SUM(amount),
        SUM(CASE sale_type WHEN 'I' THEN 1 ELSE 0 END),
        SUM(CASE sale_type WHEN 'O' THEN 1 ELSE 0 END),
        SUM(CASE sale_type WHEN 'C' THEN 1 ELSE 0 END),
        AVG(discount_rate)
    FROM tbl_test_sales
    WHERE sale_date BETWEEN @p_sdate AND @p_edate
    GROUP BY sale_date, user_id, product_code;
END
GO

-- ── 5. 테스트용 FUNCTION ──────────────────────────────────────────────
IF OBJECT_ID('FN_TEST_TOTAL_AMT', 'FN') IS NOT NULL DROP FUNCTION FN_TEST_TOTAL_AMT;
GO

CREATE FUNCTION FN_TEST_TOTAL_AMT
(
    @p_date VARCHAR(8),
    @p_user_id VARCHAR(20)
)
RETURNS DECIMAL(18,2)
AS
BEGIN
    DECLARE @v_total DECIMAL(18,2);
    SELECT @v_total = ISNULL(SUM(amount), 0)
    FROM tbl_test_sales
    WHERE sale_date = @p_date AND user_id = @p_user_id;
    RETURN @v_total;
END
GO

-- ── 6. 테스트용 VIEW ──────────────────────────────────────────────────
IF OBJECT_ID('view_test_daily', 'V') IS NOT NULL DROP VIEW view_test_daily;
GO

CREATE VIEW view_test_daily
AS
SELECT
    sale_date,
    user_id,
    COUNT(*) AS tx_count,
    SUM(quantity) AS total_qty,
    SUM(amount) AS total_amt
FROM tbl_test_sales
GROUP BY sale_date, user_id;
GO

-- ── 7. 검증 시나리오 ──────────────────────────────────────────────────
PRINT '=== 테스트 패키지 설치 완료 ===';
PRINT '';
PRINT '데이터 확인:';
SELECT COUNT(*) AS sales_rows FROM tbl_test_sales;
SELECT COUNT(*) AS stat_rows  FROM tbl_test_stat;
PRINT '';
PRINT 'SP 테스트:';
EXEC SP_TEST_DAILY_AGG @p_sdate = '20240101', @p_edate = '20240103';
SELECT COUNT(*) AS stat_after_sp FROM tbl_test_stat;
PRINT '';
PRINT 'FN 테스트:';
SELECT dbo.FN_TEST_TOTAL_AMT('20240101', 'USER001') AS user001_20240101_total;
PRINT '';
PRINT 'VIEW 테스트:';
SELECT TOP 3 * FROM view_test_daily;
GO