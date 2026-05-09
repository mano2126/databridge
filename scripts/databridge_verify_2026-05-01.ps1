################################################################################
#  DataBridge 객체 검증 — PowerShell 직접 쿼리 모음
#  본부장님 환경: db_mssql (1433) / db_mysql (3306) Docker
#  목적: v94_p8 적용 전 본부장님이 직접 본질 확인 + 적용 후 검증
################################################################################

# ════════════════════════════════════════════════════════════════════
# A. 환경 정보 확인 (먼저 실행 — dateformat / language 확인)
# ════════════════════════════════════════════════════════════════════

Write-Host "`n━━━ MSSQL 환경 정보 ━━━" -ForegroundColor Cyan
docker exec db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Bridge@1234' -C -d capital_midsize -Q "SELECT @@LANGUAGE AS lang, @@VERSION AS ver"

Write-Host "`n━━━ MSSQL dateformat ━━━" -ForegroundColor Cyan
docker exec db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Bridge@1234' -C -d capital_midsize -Q "DBCC USEROPTIONS"

Write-Host "`n━━━ MySQL 환경 정보 ━━━" -ForegroundColor Cyan
docker exec db_mysql mysql -uroot -p'Bridge@1234' -e "SELECT VERSION() AS version, @@sql_mode AS sql_mode, @@character_set_database AS charset"


# ════════════════════════════════════════════════════════════════════
# B. 함수/프로시저 파라미터 타입 확인
# ════════════════════════════════════════════════════════════════════

Write-Host "`n━━━ MSSQL: fn_age 파라미터 타입 ━━━" -ForegroundColor Cyan
docker exec db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Bridge@1234' -C -d capital_midsize -Q @"
SELECT p.name AS param_name, t.name AS type_name,
       p.max_length, p.precision, p.scale, p.is_output
FROM sys.parameters p
JOIN sys.types t ON p.system_type_id = t.system_type_id AND p.user_type_id = t.user_type_id
JOIN sys.objects o ON p.object_id = o.object_id
WHERE o.name = 'fn_age' AND p.parameter_id > 0
ORDER BY p.parameter_id
"@

Write-Host "`n━━━ MSSQL: sp_close_branch 파라미터 타입 ━━━" -ForegroundColor Cyan
docker exec db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Bridge@1234' -C -d capital_midsize -Q @"
SELECT p.name AS param_name, t.name AS type_name,
       p.max_length, p.precision, p.scale, p.is_output
FROM sys.parameters p
JOIN sys.types t ON p.system_type_id = t.system_type_id AND p.user_type_id = t.user_type_id
JOIN sys.objects o ON p.object_id = o.object_id
WHERE o.name = 'sp_close_branch' AND p.parameter_id > 0
ORDER BY p.parameter_id
"@


# ════════════════════════════════════════════════════════════════════
# C. 본부장님 화면의 7개 객체 — 직접 호출 (v94_p7 의 잘못된 SQL 재현)
# ════════════════════════════════════════════════════════════════════

Write-Host "`n━━━ ❌ v94_p7 의 잘못된 PROC 문법 재현 ━━━" -ForegroundColor Yellow
Write-Host "기대: 42000 — Incorrect syntax near '@P1'" -ForegroundColor DarkGray
docker exec db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Bridge@1234' -C -d capital_midsize -Q @"
DECLARE @p1 nvarchar(10) = 'A';
DECLARE @p2 nvarchar(10) = '2024-01-01';
EXEC ref.sp_close_branch @p1, CAST(@p2 AS date);
"@

Write-Host "`n━━━ ✅ v94_p8 의 올바른 PROC 호출 ━━━" -ForegroundColor Green
Write-Host "기대: 정상 실행 (또는 비즈니스 규칙 에러)" -ForegroundColor DarkGray
docker exec db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Bridge@1234' -C -d capital_midsize -Q @"
DECLARE @p1 nvarchar(10) = 'A';
DECLARE @p2 date = '2024-01-01';
EXEC ref.sp_close_branch @p1, @p2;
"@


# ════════════════════════════════════════════════════════════════════
# D. v94_p7 vs v94_p8 의 FUNCTION 호출 비교
# ════════════════════════════════════════════════════════════════════

Write-Host "`n━━━ ❌ v94_p7 의 CAST(N'...' AS date) — 22007 재현? ━━━" -ForegroundColor Yellow
docker exec db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Bridge@1234' -C -d capital_midsize -Q @"
SELECT ref.fn_age(CAST(N'2024-01-01' AS date)) AS result;
"@

Write-Host "`n━━━ ✅ v94_p8 의 CONVERT(date, '...', 23) ━━━" -ForegroundColor Green
docker exec db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Bridge@1234' -C -d capital_midsize -Q @"
SELECT ref.fn_age(CONVERT(date, '2024-01-01', 23)) AS result;
"@

Write-Host "`n━━━ 표준 방식 (참고) — 변수 사용 ━━━" -ForegroundColor Cyan
docker exec db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Bridge@1234' -C -d capital_midsize -Q @"
DECLARE @dt date = '2024-01-01';
SELECT ref.fn_age(@dt) AS result;
"@


# ════════════════════════════════════════════════════════════════════
# E. 본부장님 화면의 7개 객체 — 모두 직접 호출 테스트
# ════════════════════════════════════════════════════════════════════

Write-Host "`n━━━ MSSQL 7개 객체 직접 호출 (v94_p8 방식) ━━━" -ForegroundColor Cyan
docker exec db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Bridge@1234' -C -d capital_midsize -Q @"
PRINT '─── fn_age ───';
SELECT ref.fn_age(CONVERT(date, '2024-01-01', 23)) AS result;

PRINT '─── fn_korean_date ───';
SELECT ref.fn_korean_date(CONVERT(date, '2024-01-01', 23)) AS result;

PRINT '─── fn_next_business_day ───';
SELECT ref.fn_next_business_day(CONVERT(date, '2024-01-01', 23)) AS result;

PRINT '─── sp_close_branch ───';
DECLARE @bc nvarchar(10) = 'A', @cd date = '2024-01-01';
EXEC ref.sp_close_branch @bc, @cd;

PRINT '─── sp_daily_batch ───';
DECLARE @rd date = '2024-01-01';
EXEC settlement.sp_daily_batch @rd;

PRINT '─── sp_refresh_fx ───';
DECLARE @fxdt date = '2024-01-01';
EXEC ref.sp_refresh_fx @fxdt;

PRINT '─── tvf_daily_trx (TVF) ───';
SELECT TOP 5 * FROM settlement.tvf_daily_trx(CONVERT(date, '2024-01-01', 23));
"@


# ════════════════════════════════════════════════════════════════════
# F. MySQL 타겟 측 — 같은 객체들 (이름 매핑된 후)
# ════════════════════════════════════════════════════════════════════

Write-Host "`n━━━ MySQL 7개 객체 직접 호출 ━━━" -ForegroundColor Cyan
docker exec db_mysql mysql -uroot -p'Bridge@1234' capital_target -e @"
SELECT ref_fn_age('2024-01-01') AS fn_age_result;
SELECT ref_fn_korean_date('2024-01-01') AS fn_korean_date_result;
SELECT ref_fn_next_business_day('2024-01-01') AS fn_next_biz_day_result;
CALL ref_sp_close_branch('A', '2024-01-01');
CALL settlement_sp_daily_batch('2024-01-01');
CALL ref_sp_refresh_fx('2024-01-01');
CALL settlement_tvf_daily_trx('2024-01-01');
"@


# ════════════════════════════════════════════════════════════════════
# G. 1305 본질 — tvf_delinq_ranking 타겟 존재 여부
# ════════════════════════════════════════════════════════════════════

Write-Host "`n━━━ MySQL 타겟 — tvf_delinq_ranking 존재 확인 ━━━" -ForegroundColor Cyan
docker exec db_mysql mysql -uroot -p'Bridge@1234' capital_target -e @"
SELECT ROUTINE_NAME, ROUTINE_TYPE
FROM information_schema.ROUTINES
WHERE ROUTINE_SCHEMA = 'capital_target'
  AND ROUTINE_NAME LIKE '%delinq_ranking%';
"@

Write-Host "`n━━━ MySQL 타겟 — tvf_daily_trx 파라미터 개수 ━━━" -ForegroundColor Cyan
docker exec db_mysql mysql -uroot -p'Bridge@1234' capital_target -e @"
SELECT SPECIFIC_NAME, ORDINAL_POSITION, PARAMETER_NAME, DATA_TYPE
FROM information_schema.PARAMETERS
WHERE SPECIFIC_SCHEMA = 'capital_target'
  AND SPECIFIC_NAME LIKE 'settlement_tvf_daily_trx%'
ORDER BY ORDINAL_POSITION;
"@


# ════════════════════════════════════════════════════════════════════
# H. 1048 본질 — sp_mark_delinquent customer_id NULL
# ════════════════════════════════════════════════════════════════════

Write-Host "`n━━━ contract_id=1 이 타겟에 실재하나? ━━━" -ForegroundColor Cyan
docker exec db_mysql mysql -uroot -p'Bridge@1234' capital_target -e @"
SELECT contract_id, customer_id FROM credit_contract WHERE contract_id = 1 LIMIT 1;

SELECT MIN(contract_id) AS min_id, MAX(contract_id) AS max_id, COUNT(*) AS total
FROM credit_contract;
"@

Write-Host "`n━━━ 안전한 더미 contract_id (NULL 안 나는 것) ━━━" -ForegroundColor Cyan
docker exec db_mysql mysql -uroot -p'Bridge@1234' capital_target -e @"
SELECT contract_id, customer_id
FROM credit_contract
WHERE customer_id IS NOT NULL
ORDER BY contract_id LIMIT 3;
"@


# ════════════════════════════════════════════════════════════════════
# I. 인덱스 — v94_p6 효과 검증
# ════════════════════════════════════════════════════════════════════

Write-Host "`n━━━ MySQL 타겟 인덱스 시그니처 카운트 ━━━" -ForegroundColor Cyan
docker exec db_mysql mysql -uroot -p'Bridge@1234' capital_target -e @"
SELECT COUNT(DISTINCT TABLE_NAME, INDEX_NAME) AS total_signatures
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = 'capital_target';
"@


# ════════════════════════════════════════════════════════════════════
# J. 테이블 검증 — v94_p7 효과 (행수 비교)
# ════════════════════════════════════════════════════════════════════

Write-Host "`n━━━ 테이블 행수 빠른 비교 (소스 vs 타겟) ━━━" -ForegroundColor Cyan
$tables = @(
    @{src='collection.activity'; tgt='collection_activity'},
    @{src='collection.delinquency'; tgt='collection_delinquency'},
    @{src='credit.application'; tgt='credit_application'},
    @{src='credit.contract'; tgt='credit_contract'},
    @{src='customer.profile'; tgt='customer_profile'}
)

foreach ($pair in $tables) {
    $srcParts = $pair.src -split '\.'
    $srcSch = $srcParts[0]; $srcTbl = $srcParts[1]
    $srcCount = docker exec db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'Bridge@1234' -C -d capital_midsize -h -1 -W -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM [$srcSch].[$srcTbl]" 2>$null | Select-Object -First 1
    $tgtCount = docker exec db_mysql mysql -uroot -p'Bridge@1234' -N -B capital_target -e "SELECT COUNT(*) FROM ``$($pair.tgt)``" 2>$null
    Write-Host ("  {0,-35} 소스:{1,12}  타겟:{2,12}" -f $pair.src, $srcCount, $tgtCount) -ForegroundColor White
}

Write-Host "`n━━━ 검증 완료 ━━━" -ForegroundColor Green
