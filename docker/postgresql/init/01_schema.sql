-- ============================================================
-- DataBridge Studio — PostgreSQL 테스트 데이터
-- MySQL과 동일한 스키마 (이관 검증용)
-- ============================================================

-- 고객 테이블
CREATE TABLE IF NOT EXISTS b01_customer (
    cust_id       SERIAL        PRIMARY KEY,
    cust_name     VARCHAR(100)  NOT NULL,
    birth_date    DATE,
    gender        CHAR(1),
    mobile        VARCHAR(20),
    email         VARCHAR(100),
    credit_score  SMALLINT      DEFAULT 700,
    reg_date      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    upd_date      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    use_yn        CHAR(1)       DEFAULT 'Y'
);

-- 대출 상품 테이블
CREATE TABLE IF NOT EXISTS b02_loanproduct (
    prod_id       SERIAL        PRIMARY KEY,
    prod_name     VARCHAR(200)  NOT NULL,
    prod_type     VARCHAR(50),
    min_rate      NUMERIC(5,2),
    max_rate      NUMERIC(5,2),
    min_term      SMALLINT,
    max_term      SMALLINT,
    max_amount    BIGINT,
    use_yn        CHAR(1)       DEFAULT 'Y'
);

-- 감사 로그
CREATE TABLE IF NOT EXISTS b99_auditlog (
    log_id        BIGSERIAL     PRIMARY KEY,
    table_name    VARCHAR(100),
    pk_value      VARCHAR(100),
    action        CHAR(1),
    changed_by    VARCHAR(50),
    changed_at    TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    old_data      TEXT,
    new_data      TEXT
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_cust_name ON b01_customer(cust_name);
CREATE INDEX IF NOT EXISTS idx_cust_score ON b01_customer(credit_score);

-- 샘플 데이터
INSERT INTO b01_customer (cust_name, birth_date, gender, mobile, email, credit_score) VALUES
('김민준', '1985-03-15', 'M', '010-1234-5678', 'minjun.kim@email.com', 820),
('이서연', '1990-07-22', 'F', '010-2345-6789', 'seoyeon.lee@email.com', 750),
('박지호', '1978-11-08', 'M', '010-3456-7890', 'jiho.park@email.com', 680),
('최수아', '1995-04-30', 'F', '010-4567-8901', 'sua.choi@email.com', 790),
('정도윤', '1982-09-12', 'M', '010-5678-9012', 'doyun.jung@email.com', 710);

INSERT INTO b02_loanproduct (prod_name, prod_type, min_rate, max_rate, min_term, max_term, max_amount) VALUES
('직장인 신용대출', 'CREDIT',   3.50,  8.90,  12,  60, 50000000),
('소상공인 운영자금', 'BUSINESS',4.20, 10.50,  12,  84, 100000000),
('주택담보대출',    'MORTGAGE', 2.80,  5.50,  60, 360, 500000000);

SELECT '✅ PostgreSQL 초기화 완료' AS result;
