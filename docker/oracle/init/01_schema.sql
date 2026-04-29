-- ============================================================
-- DataBridge Studio — Oracle XE 21c 테스트 데이터
-- 접속: bridge / bridge1234 @ localhost:1521/XEPDB1
-- ============================================================

-- 고객 테이블
CREATE TABLE B01_Customer (
    cust_id       NUMBER        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cust_name     NVARCHAR2(100) NOT NULL,
    birth_date    DATE,
    gender        CHAR(1),
    mobile        VARCHAR2(20),
    email         VARCHAR2(100),
    credit_score  NUMBER(5)     DEFAULT 700,
    reg_date      TIMESTAMP     DEFAULT SYSTIMESTAMP,
    upd_date      TIMESTAMP     DEFAULT SYSTIMESTAMP,
    use_yn        CHAR(1)       DEFAULT 'Y'
);

-- 대출 상품 테이블
CREATE TABLE B02_LoanProduct (
    prod_id       NUMBER        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    prod_name     NVARCHAR2(200) NOT NULL,
    prod_type     VARCHAR2(50),
    min_rate      NUMBER(5,2),
    max_rate      NUMBER(5,2),
    min_term      NUMBER(5),
    max_term      NUMBER(5),
    max_amount    NUMBER(20),
    use_yn        CHAR(1)       DEFAULT 'Y'
);

-- 샘플 데이터
INSERT INTO B01_Customer (cust_name, birth_date, gender, mobile, email, credit_score) VALUES
(N'김민준', DATE '1985-03-15', 'M', '010-1234-5678', 'minjun.kim@email.com', 820);
INSERT INTO B01_Customer (cust_name, birth_date, gender, mobile, email, credit_score) VALUES
(N'이서연', DATE '1990-07-22', 'F', '010-2345-6789', 'seoyeon.lee@email.com', 750);
INSERT INTO B01_Customer (cust_name, birth_date, gender, mobile, email, credit_score) VALUES
(N'박지호', DATE '1978-11-08', 'M', '010-3456-7890', 'jiho.park@email.com', 680);
INSERT INTO B01_Customer (cust_name, birth_date, gender, mobile, email, credit_score) VALUES
(N'최수아', DATE '1995-04-30', 'F', '010-4567-8901', 'sua.choi@email.com', 790);
INSERT INTO B01_Customer (cust_name, birth_date, gender, mobile, email, credit_score) VALUES
(N'정도윤', DATE '1982-09-12', 'M', '010-5678-9012', 'doyun.jung@email.com', 710);

INSERT INTO B02_LoanProduct (prod_name, prod_type, min_rate, max_rate, min_term, max_term, max_amount) VALUES
(N'직장인 신용대출', 'CREDIT', 3.50, 8.90, 12, 60, 50000000);
INSERT INTO B02_LoanProduct (prod_name, prod_type, min_rate, max_rate, min_term, max_term, max_amount) VALUES
(N'주택담보대출', 'MORTGAGE', 2.80, 5.50, 60, 360, 500000000);

COMMIT;

-- 확인
SELECT '✅ Oracle 초기화 완료 - 고객: ' || COUNT(*) || '건' AS result FROM B01_Customer;
