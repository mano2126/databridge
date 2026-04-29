-- ============================================================
-- DataBridge Studio — MySQL 테스트 데이터
-- 캐피탈사 대출 시스템 샘플 (금융 도메인)
-- ============================================================

USE testdb;

-- 고객 테이블
CREATE TABLE IF NOT EXISTS B01_Customer (
    cust_id       INT           NOT NULL AUTO_INCREMENT,
    cust_name     VARCHAR(100)  NOT NULL,
    birth_date    DATE,
    gender        CHAR(1),
    mobile        VARCHAR(20),
    email         VARCHAR(100),
    credit_score  SMALLINT      DEFAULT 700,
    reg_date      DATETIME      DEFAULT CURRENT_TIMESTAMP,
    upd_date      DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    use_yn        CHAR(1)       DEFAULT 'Y',
    PRIMARY KEY (cust_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 대출 상품 테이블
CREATE TABLE IF NOT EXISTS B02_LoanProduct (
    prod_id       INT           NOT NULL AUTO_INCREMENT,
    prod_name     VARCHAR(200)  NOT NULL,
    prod_type     VARCHAR(50),
    min_rate      DECIMAL(5,2),
    max_rate      DECIMAL(5,2),
    min_term      SMALLINT,
    max_term      SMALLINT,
    max_amount    BIGINT,
    use_yn        CHAR(1)       DEFAULT 'Y',
    PRIMARY KEY (prod_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 대출 신청 테이블
CREATE TABLE IF NOT EXISTS B03_LoanApply (
    apply_id      INT           NOT NULL AUTO_INCREMENT,
    cust_id       INT           NOT NULL,
    prod_id       INT           NOT NULL,
    apply_amt     BIGINT        NOT NULL,
    apply_term    SMALLINT      NOT NULL,
    apply_rate    DECIMAL(5,2),
    apply_status  VARCHAR(20)   DEFAULT 'APPLIED',
    apply_date    DATETIME      DEFAULT CURRENT_TIMESTAMP,
    review_date   DATETIME,
    reviewer_id   VARCHAR(20),
    reject_reason VARCHAR(500),
    PRIMARY KEY (apply_id),
    FOREIGN KEY (cust_id) REFERENCES B01_Customer(cust_id),
    FOREIGN KEY (prod_id) REFERENCES B02_LoanProduct(prod_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 대출 실행 테이블
CREATE TABLE IF NOT EXISTS B04_LoanExec (
    loan_id       INT           NOT NULL AUTO_INCREMENT,
    apply_id      INT           NOT NULL,
    cust_id       INT           NOT NULL,
    prod_id       INT           NOT NULL,
    loan_amt      BIGINT        NOT NULL,
    loan_term     SMALLINT      NOT NULL,
    loan_rate     DECIMAL(5,2)  NOT NULL,
    exec_date     DATE          NOT NULL,
    maturity_date DATE          NOT NULL,
    balance_amt   BIGINT,
    loan_status   VARCHAR(20)   DEFAULT 'ACTIVE',
    PRIMARY KEY (loan_id),
    FOREIGN KEY (apply_id) REFERENCES B03_LoanApply(apply_id),
    FOREIGN KEY (cust_id)  REFERENCES B01_Customer(cust_id),
    FOREIGN KEY (prod_id)  REFERENCES B02_LoanProduct(prod_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 상환 스케줄 테이블
CREATE TABLE IF NOT EXISTS B05_RepaySchedule (
    sched_id      INT           NOT NULL AUTO_INCREMENT,
    loan_id       INT           NOT NULL,
    sched_seq     SMALLINT      NOT NULL,
    due_date      DATE          NOT NULL,
    principal_amt BIGINT        DEFAULT 0,
    interest_amt  BIGINT        DEFAULT 0,
    total_amt     BIGINT        DEFAULT 0,
    paid_amt      BIGINT        DEFAULT 0,
    paid_date     DATE,
    status        VARCHAR(20)   DEFAULT 'UNPAID',
    PRIMARY KEY (sched_id),
    FOREIGN KEY (loan_id) REFERENCES B04_LoanExec(loan_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 거래 내역 테이블
CREATE TABLE IF NOT EXISTS B06_Transaction (
    txn_id        BIGINT        NOT NULL AUTO_INCREMENT,
    loan_id       INT           NOT NULL,
    cust_id       INT           NOT NULL,
    txn_type      VARCHAR(30)   NOT NULL,
    txn_amt       BIGINT        NOT NULL,
    txn_date      DATETIME      DEFAULT CURRENT_TIMESTAMP,
    txn_channel   VARCHAR(20),
    memo          VARCHAR(500),
    PRIMARY KEY (txn_id),
    FOREIGN KEY (loan_id) REFERENCES B04_LoanExec(loan_id),
    FOREIGN KEY (cust_id) REFERENCES B01_Customer(cust_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 감사 로그 테이블
CREATE TABLE IF NOT EXISTS B99_AuditLog (
    log_id        BIGINT        NOT NULL AUTO_INCREMENT,
    table_name    VARCHAR(100),
    pk_value      VARCHAR(100),
    action        CHAR(1),
    changed_by    VARCHAR(50),
    changed_at    DATETIME      DEFAULT CURRENT_TIMESTAMP,
    old_data      TEXT,
    new_data      TEXT,
    PRIMARY KEY (log_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 샘플 데이터 입력
-- ============================================================

-- 고객 데이터 (30명)
INSERT INTO B01_Customer (cust_name, birth_date, gender, mobile, email, credit_score) VALUES
('김민준', '1985-03-15', 'M', '010-1234-5678', 'minjun.kim@email.com', 820),
('이서연', '1990-07-22', 'F', '010-2345-6789', 'seoyeon.lee@email.com', 750),
('박지호', '1978-11-08', 'M', '010-3456-7890', 'jiho.park@email.com', 680),
('최수아', '1995-04-30', 'F', '010-4567-8901', 'sua.choi@email.com', 790),
('정도윤', '1982-09-12', 'M', '010-5678-9012', 'doyun.jung@email.com', 710),
('강하은', '1988-06-25', 'F', '010-6789-0123', 'haeun.kang@email.com', 830),
('윤시우', '1993-02-14', 'M', '010-7890-1234', 'siwoo.yoon@email.com', 660),
('임지은', '1976-12-03', 'F', '010-8901-2345', 'jieun.lim@email.com', 770),
('한지원', '1991-08-19', 'M', '010-9012-3456', 'jiwon.han@email.com', 720),
('오채원', '1987-05-07', 'F', '010-0123-4567', 'chaewon.oh@email.com', 800),
('신현우', '1983-10-28', 'M', '010-1111-2222', 'hyunwoo.shin@email.com', 740),
('류나연', '1997-01-16', 'F', '010-2222-3333', 'nayeon.ryu@email.com', 690),
('문태양', '1979-07-04', 'M', '010-3333-4444', 'taeyang.moon@email.com', 760),
('배소희', '1994-03-21', 'F', '010-4444-5555', 'sohee.bae@email.com', 810),
('노준서', '1986-11-13', 'M', '010-5555-6666', 'junseo.noh@email.com', 670),
('유다인', '1992-06-09', 'F', '010-6666-7777', 'dain.yoo@email.com', 780),
('홍성민', '1980-04-26', 'M', '010-7777-8888', 'sungmin.hong@email.com', 730),
('전지수', '1996-09-18', 'F', '010-8888-9999', 'jisu.jeon@email.com', 850),
('장현석', '1984-02-07', 'M', '010-9999-0000', 'hyunseok.jang@email.com', 700),
('권미래', '1989-12-31', 'F', '010-1212-3434', 'mirae.kwon@email.com', 760),
('허준혁', '1977-08-15', 'M', '010-3434-5656', 'junhyuk.heo@email.com', 640),
('남하영', '1998-05-03', 'F', '010-5656-7878', 'hayoung.nam@email.com', 720),
('송민재', '1985-10-22', 'M', '010-7878-9090', 'minjae.song@email.com', 790),
('안지현', '1991-03-11', 'F', '010-9090-1212', 'jihyun.ahn@email.com', 810),
('구성훈', '1973-07-29', 'M', '010-1122-3344', 'sunghoon.goo@email.com', 650),
('표나리', '1999-01-08', 'F', '010-3344-5566', 'nari.pyo@email.com', 700),
('변재혁', '1981-06-17', 'M', '010-5566-7788', 'jaehyuk.byun@email.com', 770),
('채유진', '1993-11-24', 'F', '010-7788-9900', 'yujin.chae@email.com', 820),
('명승준', '1988-04-05', 'M', '010-9900-1122', 'seungjun.myung@email.com', 680),
('탁소영', '1995-09-13', 'F', '010-1234-9876', 'soyoung.tak@email.com', 750);

-- 대출 상품 데이터
INSERT INTO B02_LoanProduct (prod_name, prod_type, min_rate, max_rate, min_term, max_term, max_amount) VALUES
('직장인 신용대출', 'CREDIT',    3.50,  8.90,  12,  60, 50000000),
('소상공인 운영자금', 'BUSINESS', 4.20, 10.50,  12,  84, 100000000),
('주택담보대출',    'MORTGAGE',  2.80,  5.50,  60, 360, 500000000),
('자동차담보대출',  'AUTO',      3.90,  7.20,  24,  72, 70000000),
('마이너스통장',    'OVERDRAFT', 5.50, 12.00,   1,  12, 30000000),
('중금리 신용대출', 'CREDIT',    8.50, 15.00,   6,  48, 20000000),
('전세자금대출',   'JEONSE',    2.50,  4.50,  12,  24, 300000000),
('사업자대출',     'BUSINESS',  4.80, 11.00,  12,  60, 200000000);

-- 대출 신청 데이터 (50건)
INSERT INTO B03_LoanApply (cust_id, prod_id, apply_amt, apply_term, apply_rate, apply_status, apply_date, review_date, reviewer_id) VALUES
(1,  1, 20000000, 36, 5.50, 'APPROVED', '2024-01-05 09:30:00', '2024-01-06 14:20:00', 'reviewer01'),
(2,  1, 15000000, 24, 6.20, 'APPROVED', '2024-01-08 10:15:00', '2024-01-09 11:30:00', 'reviewer02'),
(3,  2, 50000000, 60, 7.80, 'APPROVED', '2024-01-10 14:00:00', '2024-01-12 09:45:00', 'reviewer01'),
(4,  3,300000000, 240, 3.20, 'APPROVED', '2024-01-15 11:00:00', '2024-01-17 16:30:00', 'reviewer03'),
(5,  1, 10000000, 12, 7.50, 'REJECTED', '2024-01-18 09:00:00', '2024-01-19 10:00:00', 'reviewer02'),
(6,  4, 35000000, 48, 4.90, 'APPROVED', '2024-01-20 15:30:00', '2024-01-22 09:15:00', 'reviewer01'),
(7,  6, 10000000, 24, 12.00, 'APPROVED', '2024-01-25 13:00:00', '2024-01-26 14:00:00', 'reviewer02'),
(8,  1, 30000000, 36, 4.80, 'APPROVED', '2024-02-01 09:30:00', '2024-02-02 11:00:00', 'reviewer03'),
(9,  2, 80000000, 72, 8.50, 'APPROVED', '2024-02-05 14:00:00', '2024-02-07 09:30:00', 'reviewer01'),
(10, 5, 20000000, 12, 7.00, 'APPROVED', '2024-02-10 10:00:00', '2024-02-11 15:00:00', 'reviewer02'),
(11, 1, 25000000, 36, 5.80, 'APPROVED', '2024-02-15 09:00:00', '2024-02-16 10:30:00', 'reviewer01'),
(12, 6, 8000000,  18, 13.50, 'APPROVED', '2024-02-20 11:30:00', '2024-02-21 09:00:00', 'reviewer03'),
(13, 3,200000000, 180, 3.50, 'APPROVED', '2024-03-01 14:00:00', '2024-03-03 16:00:00', 'reviewer02'),
(14, 1, 18000000, 24, 6.50, 'APPROVED', '2024-03-05 09:30:00', '2024-03-06 11:00:00', 'reviewer01'),
(15, 2, 60000000, 60, 9.00, 'REJECTED', '2024-03-10 10:00:00', '2024-03-11 14:00:00', 'reviewer03'),
(16, 7,150000000, 24, 3.20, 'APPROVED', '2024-03-15 13:00:00', '2024-03-17 09:00:00', 'reviewer02'),
(17, 4, 45000000, 60, 5.50, 'APPROVED', '2024-03-20 15:00:00', '2024-03-22 11:00:00', 'reviewer01'),
(18, 1, 22000000, 36, 5.20, 'APPROVED', '2024-04-01 09:00:00', '2024-04-02 10:30:00', 'reviewer02'),
(19, 6, 12000000, 24, 11.50, 'APPROVED', '2024-04-05 14:00:00', '2024-04-06 15:30:00', 'reviewer03'),
(20, 1, 28000000, 48, 4.90, 'APPROVED', '2024-04-10 10:30:00', '2024-04-11 09:00:00', 'reviewer01'),
(1,  2, 40000000, 36, 6.80, 'PENDING',  '2024-11-01 09:00:00', NULL, NULL),
(2,  4, 25000000, 36, 4.50, 'PENDING',  '2024-11-05 10:30:00', NULL, NULL),
(3,  1, 15000000, 24, 6.00, 'PENDING',  '2024-11-10 14:00:00', NULL, NULL),
(4,  6, 10000000, 18, 12.50, 'PENDING', '2024-11-15 09:30:00', NULL, NULL),
(5,  3,250000000, 240, 3.10, 'PENDING', '2024-11-20 11:00:00', NULL, NULL);

-- 대출 실행 데이터 (20건)
INSERT INTO B04_LoanExec (apply_id, cust_id, prod_id, loan_amt, loan_term, loan_rate, exec_date, maturity_date, balance_amt, loan_status) VALUES
(1,  1,  1, 20000000, 36, 5.50, '2024-01-07', '2027-01-07', 15000000, 'ACTIVE'),
(2,  2,  1, 15000000, 24, 6.20, '2024-01-10', '2026-01-10', 10000000, 'ACTIVE'),
(3,  3,  2, 50000000, 60, 7.80, '2024-01-13', '2029-01-13', 45000000, 'ACTIVE'),
(4,  4,  3,300000000,240, 3.20, '2024-01-18', '2044-01-18',285000000, 'ACTIVE'),
(6,  6,  4, 35000000, 48, 4.90, '2024-01-23', '2028-01-23', 28000000, 'ACTIVE'),
(7,  7,  6, 10000000, 24,12.00, '2024-01-27', '2026-01-27',  7500000, 'ACTIVE'),
(8,  8,  1, 30000000, 36, 4.80, '2024-02-03', '2027-02-03', 25000000, 'ACTIVE'),
(9,  9,  2, 80000000, 72, 8.50, '2024-02-08', '2030-02-08', 75000000, 'ACTIVE'),
(10,10,  5, 20000000, 12, 7.00, '2024-02-12', '2025-02-12',  5000000, 'ACTIVE'),
(11,11,  1, 25000000, 36, 5.80, '2024-02-17', '2027-02-17', 20000000, 'ACTIVE'),
(12,12,  6,  8000000, 18,13.50, '2024-02-22', '2025-08-22',  4000000, 'ACTIVE'),
(13,13,  3,200000000,180, 3.50, '2024-03-04', '2039-03-04',196000000, 'ACTIVE'),
(14,14,  1, 18000000, 24, 6.50, '2024-03-07', '2026-03-07', 13000000, 'ACTIVE'),
(16,16,  7,150000000, 24, 3.20, '2024-03-18', '2026-03-18',130000000, 'ACTIVE'),
(17,17,  4, 45000000, 60, 5.50, '2024-03-23', '2029-03-23', 40000000, 'ACTIVE'),
(18,18,  1, 22000000, 36, 5.20, '2024-04-03', '2027-04-03', 19000000, 'ACTIVE'),
(19,19,  6, 12000000, 24,11.50, '2024-04-07', '2026-04-07',  9000000, 'ACTIVE'),
(20,20,  1, 28000000, 48, 4.90, '2024-04-12', '2028-04-12', 25000000, 'ACTIVE'),
(2,  2,  1, 15000000, 24, 6.20, '2024-01-10', '2026-01-10',       0, 'CLOSED'),
(3,  3,  2, 50000000, 60, 7.80, '2022-05-01', '2023-05-01',       0, 'MATURED');

-- 거래 내역 (40건)
INSERT INTO B06_Transaction (loan_id, cust_id, txn_type, txn_amt, txn_date, txn_channel, memo) VALUES
(1, 1,  'REPAY',   600000, '2024-02-07 10:00:00', 'AUTO', '2월 정기상환'),
(1, 1,  'REPAY',   600000, '2024-03-07 10:00:00', 'AUTO', '3월 정기상환'),
(1, 1,  'REPAY',   600000, '2024-04-07 10:00:00', 'AUTO', '4월 정기상환'),
(2, 2,  'REPAY',   700000, '2024-02-10 09:30:00', 'BANK', '2월 정기상환'),
(2, 2,  'REPAY',   700000, '2024-03-10 09:30:00', 'BANK', '3월 정기상환'),
(3, 3,  'REPAY',  1200000, '2024-02-13 11:00:00', 'AUTO', '2월 정기상환'),
(3, 3,  'REPAY',  1200000, '2024-03-13 11:00:00', 'AUTO', '3월 정기상환'),
(4, 4,  'REPAY',  1500000, '2024-02-18 10:30:00', 'AUTO', '2월 정기상환'),
(4, 4,  'REPAY',  1500000, '2024-03-18 10:30:00', 'AUTO', '3월 정기상환'),
(5, 6,  'REPAY',   900000, '2024-02-23 09:00:00', 'AUTO', '2월 정기상환'),
(6, 7,  'REPAY',   550000, '2024-02-27 14:00:00', 'APP',  '2월 정기상환'),
(7, 8,  'REPAY',   850000, '2024-03-03 10:00:00', 'AUTO', '3월 정기상환'),
(8, 9,  'REPAY',  1800000, '2024-03-08 11:30:00', 'AUTO', '3월 정기상환'),
(9, 10, 'REPAY',  1700000, '2024-03-12 09:00:00', 'BANK', '3월 정기상환'),
(10,11, 'REPAY',   720000, '2024-03-17 10:00:00', 'AUTO', '3월 정기상환'),
(1, 1,  'PREPAY', 2000000, '2024-05-07 14:00:00', 'APP',  '중도상환'),
(3, 3,  'PREPAY', 5000000, '2024-06-13 11:00:00', 'BANK', '중도상환'),
(4, 4,  'PREPAY',10000000, '2024-07-18 09:30:00', 'BANK', '중도상환'),
(7, 8,  'PREPAY', 3000000, '2024-08-03 14:00:00', 'APP',  '중도상환'),
(13,13, 'REPAY',  2500000, '2024-04-04 10:00:00', 'AUTO', '4월 정기상환'),
(14,14, 'REPAY',   780000, '2024-04-07 09:30:00', 'AUTO', '4월 정기상환'),
(15,16, 'REPAY',  6500000, '2024-04-18 10:00:00', 'AUTO', '4월 정기상환'),
(16,17, 'REPAY',  1100000, '2024-04-23 11:00:00', 'AUTO', '4월 정기상환'),
(17,18, 'REPAY',   660000, '2024-05-03 09:00:00', 'AUTO', '5월 정기상환'),
(18,19, 'REPAY',   580000, '2024-05-07 10:30:00', 'APP',  '5월 정기상환'),
(1, 1,  'REPAY',   600000, '2024-05-07 10:00:00', 'AUTO', '5월 정기상환'),
(2, 2,  'REPAY',   700000, '2024-04-10 09:30:00', 'BANK', '4월 정기상환'),
(5, 6,  'REPAY',   900000, '2024-03-23 09:00:00', 'AUTO', '3월 정기상환'),
(6, 7,  'LATE_FEE', 25000, '2024-04-05 00:00:00', 'AUTO', '연체료'),
(8, 9,  'REPAY',  1800000, '2024-04-08 11:30:00', 'AUTO', '4월 정기상환'),
(9, 10, 'REPAY',  1700000, '2024-04-12 09:00:00', 'BANK', '4월 정기상환'),
(10,11, 'REPAY',   720000, '2024-04-17 10:00:00', 'AUTO', '4월 정기상환'),
(11,12, 'REPAY',   560000, '2024-03-22 14:00:00', 'APP',  '3월 정기상환'),
(12,13, 'REPAY',  2500000, '2024-05-04 10:00:00', 'AUTO', '5월 정기상환'),
(13,14, 'REPAY',   780000, '2024-05-07 09:30:00', 'AUTO', '5월 정기상환'),
(14,16, 'REPAY',  6500000, '2024-05-18 10:00:00', 'AUTO', '5월 정기상환'),
(15,17, 'REPAY',  1100000, '2024-05-23 11:00:00', 'AUTO', '5월 정기상환'),
(16,18, 'REPAY',   660000, '2024-06-03 09:00:00', 'AUTO', '6월 정기상환'),
(17,19, 'REPAY',   580000, '2024-06-07 10:30:00', 'APP',  '6월 정기상환'),
(18,20, 'REPAY',   750000, '2024-05-12 10:00:00', 'AUTO', '5월 정기상환');

-- 인덱스 생성
CREATE INDEX idx_loan_cust   ON B04_LoanExec(cust_id);
CREATE INDEX idx_loan_status ON B04_LoanExec(loan_status);
CREATE INDEX idx_txn_date    ON B06_Transaction(txn_date);
CREATE INDEX idx_apply_date  ON B03_LoanApply(apply_date);

SELECT CONCAT('MySQL 초기화 완료 - B01:',
  (SELECT COUNT(*) FROM B01_Customer), '건, B03:',
  (SELECT COUNT(*) FROM B03_LoanApply), '건, B04:',
  (SELECT COUNT(*) FROM B04_LoanExec), '건') AS result;
