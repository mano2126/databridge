#!/bin/bash
# ============================================================
# MSSQL 초기화 — 컨테이너 기동 후 수동 실행
# 사용법: docker exec -it db_mssql bash /docker-mssql-init/01_init.sh
# ============================================================

# MSSQL이 준비될 때까지 대기
echo "⏳ MSSQL 준비 대기 중..."
for i in {1..30}; do
    /opt/mssql-tools18/bin/sqlcmd -S localhost -U SA -P "Bridge@1234" \
        -Q "SELECT 1" -No -C > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "✅ MSSQL 준비 완료"
        break
    fi
    echo "  대기 중... ($i/30)"
    sleep 3
done

# DB 및 테이블 생성
/opt/mssql-tools18/bin/sqlcmd -S localhost -U SA -P "Bridge@1234" -No -C << 'SQLEOF'

-- DB 생성
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'testdb')
    CREATE DATABASE testdb;
GO

USE testdb;
GO

-- 로그인 생성
IF NOT EXISTS (SELECT name FROM sys.server_principals WHERE name = 'bridge')
BEGIN
    CREATE LOGIN bridge WITH PASSWORD = 'Bridge@1234';
END
GO

-- 사용자 생성
IF NOT EXISTS (SELECT name FROM sys.database_principals WHERE name = 'bridge')
BEGIN
    CREATE USER bridge FOR LOGIN bridge;
    ALTER ROLE db_owner ADD MEMBER bridge;
END
GO

-- 고객 테이블
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='B01_Customer' AND xtype='U')
CREATE TABLE B01_Customer (
    cust_id       INT           NOT NULL IDENTITY(1,1),
    cust_name     NVARCHAR(100) NOT NULL,
    birth_date    DATE,
    gender        CHAR(1),
    mobile        VARCHAR(20),
    email         VARCHAR(100),
    credit_score  SMALLINT      DEFAULT 700,
    reg_date      DATETIME2     DEFAULT GETDATE(),
    upd_date      DATETIME2     DEFAULT GETDATE(),
    use_yn        CHAR(1)       DEFAULT 'Y',
    CONSTRAINT PK_Customer PRIMARY KEY (cust_id)
);
GO

-- 대출 상품 테이블
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='B02_LoanProduct' AND xtype='U')
CREATE TABLE B02_LoanProduct (
    prod_id       INT           NOT NULL IDENTITY(1,1),
    prod_name     NVARCHAR(200) NOT NULL,
    prod_type     VARCHAR(50),
    min_rate      DECIMAL(5,2),
    max_rate      DECIMAL(5,2),
    min_term      SMALLINT,
    max_term      SMALLINT,
    max_amount    BIGINT,
    use_yn        CHAR(1)       DEFAULT 'Y',
    CONSTRAINT PK_LoanProduct PRIMARY KEY (prod_id)
);
GO

-- 대출 신청 테이블
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='B03_LoanApply' AND xtype='U')
CREATE TABLE B03_LoanApply (
    apply_id      INT           NOT NULL IDENTITY(1,1),
    cust_id       INT           NOT NULL,
    prod_id       INT           NOT NULL,
    apply_amt     BIGINT        NOT NULL,
    apply_term    SMALLINT      NOT NULL,
    apply_rate    DECIMAL(5,2),
    apply_status  VARCHAR(20)   DEFAULT 'APPLIED',
    apply_date    DATETIME2     DEFAULT GETDATE(),
    review_date   DATETIME2,
    reviewer_id   VARCHAR(20),
    reject_reason NVARCHAR(500),
    CONSTRAINT PK_LoanApply PRIMARY KEY (apply_id),
    CONSTRAINT FK_Apply_Cust FOREIGN KEY (cust_id) REFERENCES B01_Customer(cust_id),
    CONSTRAINT FK_Apply_Prod FOREIGN KEY (prod_id) REFERENCES B02_LoanProduct(prod_id)
);
GO

-- 대출 실행 테이블
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='B04_LoanExec' AND xtype='U')
CREATE TABLE B04_LoanExec (
    loan_id       INT           NOT NULL IDENTITY(1,1),
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
    CONSTRAINT PK_LoanExec PRIMARY KEY (loan_id),
    CONSTRAINT FK_Exec_Apply FOREIGN KEY (apply_id) REFERENCES B03_LoanApply(apply_id),
    CONSTRAINT FK_Exec_Cust  FOREIGN KEY (cust_id)  REFERENCES B01_Customer(cust_id),
    CONSTRAINT FK_Exec_Prod  FOREIGN KEY (prod_id)  REFERENCES B02_LoanProduct(prod_id)
);
GO

-- 거래 내역 테이블
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='B06_Transaction' AND xtype='U')
CREATE TABLE B06_Transaction (
    txn_id        BIGINT        NOT NULL IDENTITY(1,1),
    loan_id       INT           NOT NULL,
    cust_id       INT           NOT NULL,
    txn_type      VARCHAR(30)   NOT NULL,
    txn_amt       BIGINT        NOT NULL,
    txn_date      DATETIME2     DEFAULT GETDATE(),
    txn_channel   VARCHAR(20),
    memo          NVARCHAR(500),
    CONSTRAINT PK_Transaction PRIMARY KEY (txn_id)
);
GO

-- 감사 로그
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='B99_AuditLog' AND xtype='U')
CREATE TABLE B99_AuditLog (
    log_id        BIGINT        NOT NULL IDENTITY(1,1),
    table_name    VARCHAR(100),
    pk_value      VARCHAR(100),
    action        CHAR(1),
    changed_by    VARCHAR(50),
    changed_at    DATETIME2     DEFAULT GETDATE(),
    old_data      NVARCHAR(MAX),
    new_data      NVARCHAR(MAX),
    CONSTRAINT PK_AuditLog PRIMARY KEY (log_id)
);
GO

-- 감사 로그 트리거 (Customer 변경 시 자동 기록)
IF EXISTS (SELECT * FROM sys.triggers WHERE name = 'trg_Customer_AuditLog')
    DROP TRIGGER trg_Customer_AuditLog;
GO

CREATE TRIGGER trg_Customer_AuditLog
ON B01_Customer
AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @action CHAR(1);
    IF EXISTS (SELECT 1 FROM inserted) AND EXISTS (SELECT 1 FROM deleted)
        SET @action = 'U';
    ELSE IF EXISTS (SELECT 1 FROM inserted)
        SET @action = 'I';
    ELSE
        SET @action = 'D';

    INSERT INTO B99_AuditLog (table_name, pk_value, action, changed_by)
    SELECT 'B01_Customer',
           CAST(COALESCE(i.cust_id, d.cust_id) AS VARCHAR(100)),
           @action,
           SYSTEM_USER
    FROM inserted i FULL OUTER JOIN deleted d ON i.cust_id = d.cust_id;
END;
GO

-- 샘플 데이터 입력
SET IDENTITY_INSERT B01_Customer ON;
INSERT INTO B01_Customer (cust_id, cust_name, birth_date, gender, mobile, email, credit_score) VALUES
(1,  N'김민준', '1985-03-15', 'M', '010-1234-5678', 'minjun.kim@email.com', 820),
(2,  N'이서연', '1990-07-22', 'F', '010-2345-6789', 'seoyeon.lee@email.com', 750),
(3,  N'박지호', '1978-11-08', 'M', '010-3456-7890', 'jiho.park@email.com', 680),
(4,  N'최수아', '1995-04-30', 'F', '010-4567-8901', 'sua.choi@email.com', 790),
(5,  N'정도윤', '1982-09-12', 'M', '010-5678-9012', 'doyun.jung@email.com', 710),
(6,  N'강하은', '1988-06-25', 'F', '010-6789-0123', 'haeun.kang@email.com', 830),
(7,  N'윤시우', '1993-02-14', 'M', '010-7890-1234', 'siwoo.yoon@email.com', 660),
(8,  N'임지은', '1976-12-03', 'F', '010-8901-2345', 'jieun.lim@email.com', 770),
(9,  N'한지원', '1991-08-19', 'M', '010-9012-3456', 'jiwon.han@email.com', 720),
(10, N'오채원', '1987-05-07', 'F', '010-0123-4567', 'chaewon.oh@email.com', 800);
SET IDENTITY_INSERT B01_Customer OFF;
GO

SET IDENTITY_INSERT B02_LoanProduct ON;
INSERT INTO B02_LoanProduct (prod_id, prod_name, prod_type, min_rate, max_rate, min_term, max_term, max_amount) VALUES
(1, N'직장인 신용대출',   'CREDIT',   3.50,  8.90,  12,  60, 50000000),
(2, N'소상공인 운영자금', 'BUSINESS', 4.20, 10.50,  12,  84, 100000000),
(3, N'주택담보대출',      'MORTGAGE', 2.80,  5.50,  60, 360, 500000000),
(4, N'자동차담보대출',    'AUTO',     3.90,  7.20,  24,  72, 70000000),
(5, N'마이너스통장',      'OVERDRAFT',5.50, 12.00,   1,  12, 30000000),
(6, N'중금리 신용대출',   'CREDIT',   8.50, 15.00,   6,  48, 20000000);
SET IDENTITY_INSERT B02_LoanProduct OFF;
GO

PRINT '✅ MSSQL testdb 초기화 완료';
SELECT 'B01_Customer: ' + CAST(COUNT(*) AS VARCHAR) + '건' FROM B01_Customer
UNION ALL
SELECT 'B02_LoanProduct: ' + CAST(COUNT(*) AS VARCHAR) + '건' FROM B02_LoanProduct;
GO

SQLEOF

echo "✅ MSSQL 초기화 스크립트 완료"
