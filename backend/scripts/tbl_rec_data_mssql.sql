-- ════════════════════════════════════════════════════════════════════════
-- tbl_rec_data — SP_STATRECORD/SP_STATSYSTEM 의 의존 테이블
-- 작성: 2026-04-28 / 본부장님 검증 dead SP 살리기
-- 
-- SP_STATRECORD 의 SELECT 절 분석으로부터 도출한 컬럼:
--   rec_date, rec_hour, user_id, business_code, bpart_code,
--   mpart_code, spart_code, system_code, rec_mode, rec_inout, call_time
-- 
-- 데이터 분포:
--   3일치 (20240101~20240103) × 시간 24개 × 유저 5명 × rec_mode 3종
--   → 총 360행 (집계 검증에 충분)
-- ════════════════════════════════════════════════════════════════════════

USE testdb;
GO

-- ── 기존 객체 정리 (재실행 안전) ──────────────────────────────────
IF OBJECT_ID('tbl_rec_data', 'U') IS NOT NULL DROP TABLE tbl_rec_data;
GO

-- ── 테이블 정의 ────────────────────────────────────────────────────
CREATE TABLE tbl_rec_data (
    rec_date       VARCHAR(8)    NOT NULL,    -- YYYYMMDD
    rec_hour       VARCHAR(2)    NOT NULL,    -- HH (00-23)
    rec_seq        INT           NOT NULL IDENTITY(1,1),
    user_id        VARCHAR(20)   NOT NULL,
    business_code  VARCHAR(10)   NOT NULL,
    bpart_code     VARCHAR(10)   NOT NULL,
    mpart_code     VARCHAR(10)   NOT NULL,
    spart_code     VARCHAR(10)   NOT NULL,
    system_code    VARCHAR(10)   NOT NULL,
    rec_mode       VARCHAR(10)   NOT NULL,    -- 'NORMAL' | 'EVAL' | 'COACH'
    rec_inout      CHAR(1)       NOT NULL,    -- 'I' (인바운드) | 'O' (아웃바운드) | 'L' (로컬)
    call_time      INT           NOT NULL DEFAULT 0,  -- 통화시간 (초)
    created_at     DATETIME      NOT NULL DEFAULT GETDATE(),
    PRIMARY KEY (rec_date, rec_hour, rec_seq)
);
GO

CREATE INDEX IX_tbl_rec_data_user      ON tbl_rec_data(user_id);
CREATE INDEX IX_tbl_rec_data_rec_date  ON tbl_rec_data(rec_date);
GO

-- ── 샘플 데이터 ────────────────────────────────────────────────────
DELETE FROM tbl_rec_data;
GO

DECLARE @i INT = 0;
DECLARE @max INT = 360;       -- 3일 × 24시간 × 5명 = 360 (대략)
WHILE @i < @max
BEGIN
    INSERT INTO tbl_rec_data (
        rec_date, rec_hour, user_id,
        business_code, bpart_code, mpart_code, spart_code, system_code,
        rec_mode, rec_inout, call_time
    )
    VALUES (
        -- 날짜: 3일치 순환
        CASE (@i % 3)
            WHEN 0 THEN '20240101'
            WHEN 1 THEN '20240102'
            ELSE        '20240103'
        END,
        -- 시간: 09~17 영업시간 위주 (09 + (i % 9) 시간)
        RIGHT('00' + CAST((9 + (@i % 9)) AS VARCHAR), 2),
        -- 유저: 5명 순환
        CASE (@i % 5)
            WHEN 0 THEN 'USER001'
            WHEN 1 THEN 'USER002'
            WHEN 2 THEN 'USER003'
            WHEN 3 THEN 'USER004'
            ELSE        'USER005'
        END,
        -- business_code: 3종
        CASE (@i % 3) WHEN 0 THEN 'BIZ_LOAN' WHEN 1 THEN 'BIZ_CARD' ELSE 'BIZ_INS' END,
        -- bpart_code (대분류): 2종
        CASE (@i % 2) WHEN 0 THEN 'BP01' ELSE 'BP02' END,
        -- mpart_code (중분류): 3종
        CASE (@i % 3) WHEN 0 THEN 'MP01' WHEN 1 THEN 'MP02' ELSE 'MP03' END,
        -- spart_code (소분류): 4종
        CASE (@i % 4) WHEN 0 THEN 'SP01' WHEN 1 THEN 'SP02' WHEN 2 THEN 'SP03' ELSE 'SP04' END,
        -- system_code: 2종
        CASE (@i % 2) WHEN 0 THEN 'SYS_A' ELSE 'SYS_B' END,
        -- rec_mode: 3종 (NORMAL 위주)
        CASE (@i % 5) 
            WHEN 0 THEN 'EVAL' 
            WHEN 1 THEN 'COACH' 
            ELSE        'NORMAL' 
        END,
        -- rec_inout: I 가장 많이, O 다음, L 가끔
        CASE (@i % 5)
            WHEN 0 THEN 'O'
            WHEN 1 THEN 'L'
            ELSE        'I'
        END,
        -- call_time: 30초 ~ 900초 (15분) 분포
        CASE (@i % 7)
            WHEN 0 THEN 30      -- 30초 (one_under_cnt 카운트)
            WHEN 1 THEN 45
            WHEN 2 THEN 90      -- 1.5분 (one_five_cnt)
            WHEN 3 THEN 180     -- 3분 (one_five_cnt)
            WHEN 4 THEN 360     -- 6분 (five_ten_cnt)
            WHEN 5 THEN 480     -- 8분 (five_ten_cnt)
            ELSE        720     -- 12분 (ten_over_cnt)
        END
    );
    SET @i = @i + 1;
END
GO

-- ── 의존 결과 테이블 만들기 (없으면) ──────────────────────────────
IF OBJECT_ID('tbl_stat_record', 'U') IS NULL
BEGIN
    CREATE TABLE tbl_stat_record (
        rec_date        VARCHAR(8)    NOT NULL,
        rec_hour        VARCHAR(2)    NOT NULL,
        user_id         VARCHAR(20)   NOT NULL,
        rec_mode        VARCHAR(10)   NOT NULL,
        business_code   VARCHAR(10)   NULL,
        bpart_code      VARCHAR(10)   NULL,
        mpart_code      VARCHAR(10)   NULL,
        spart_code      VARCHAR(10)   NULL,
        system_code     VARCHAR(10)   NULL,
        tot_cnt         INT           NOT NULL DEFAULT 0,
        tot_call_time   INT           NOT NULL DEFAULT 0,
        in_cnt          INT           NOT NULL DEFAULT 0,
        out_cnt         INT           NOT NULL DEFAULT 0,
        local_cnt       INT           NOT NULL DEFAULT 0,
        one_under_cnt   INT           NOT NULL DEFAULT 0,
        one_five_cnt    INT           NOT NULL DEFAULT 0,
        five_ten_cnt    INT           NOT NULL DEFAULT 0,
        ten_over_cnt    INT           NOT NULL DEFAULT 0,
        PRIMARY KEY (rec_date, rec_hour, user_id, rec_mode)
    );
END
GO

-- ── 결과 확인 ──────────────────────────────────────────────────────
PRINT '=== tbl_rec_data 생성 완료 ===';
SELECT COUNT(*) AS total_rows FROM tbl_rec_data;
PRINT '';
PRINT '날짜별 분포:';
SELECT rec_date, COUNT(*) AS cnt FROM tbl_rec_data GROUP BY rec_date ORDER BY rec_date;
PRINT '';
PRINT '유저별 분포:';
SELECT user_id, COUNT(*) AS cnt FROM tbl_rec_data GROUP BY user_id ORDER BY user_id;
PRINT '';
PRINT 'rec_inout 분포:';
SELECT rec_inout, COUNT(*) AS cnt FROM tbl_rec_data GROUP BY rec_inout ORDER BY rec_inout;
PRINT '';
PRINT 'call_time 분포 (구간별):';
SELECT 
    SUM(CASE WHEN call_time < 60 THEN 1 ELSE 0 END) AS under_1min,
    SUM(CASE WHEN call_time >= 60 AND call_time < 300 THEN 1 ELSE 0 END) AS one_to_five_min,
    SUM(CASE WHEN call_time >= 300 AND call_time < 600 THEN 1 ELSE 0 END) AS five_to_ten_min,
    SUM(CASE WHEN call_time >= 600 THEN 1 ELSE 0 END) AS over_ten_min
FROM tbl_rec_data;
PRINT '';
PRINT 'SP_STATRECORD 실행 테스트:';
EXEC SP_STATRECORD @p_rec_sdate = '20240101', @p_rec_edate = '20240103';
SELECT COUNT(*) AS stat_record_rows FROM tbl_stat_record;
PRINT '';
PRINT '=== 모두 통과시 정상 ===';
GO