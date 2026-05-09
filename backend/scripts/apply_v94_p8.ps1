$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v94_p8 — 오브젝트 검증 본질 처방 (정직한 부분 롤백)" -ForegroundColor Cyan
Write-Host "  본부장님 통찰: '소스 테스트는 그냥 원본 DB 조회 아냐?'" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v94_p8_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$rel = "backend\app\api\routes\schema.py"
$src = Join-Path $ProjectRoot $rel
if (Test-Path $src) {
    $dst = Join-Path $BackupRoot $rel
    New-Item -Path (Split-Path -Parent $dst) -ItemType Directory -Force | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst -Force
}
$sf = Join-Path $PatchSrc $rel
Copy-Item -LiteralPath $sf -Destination $src -Force
Write-Host "  + $rel" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  정직한 진단 — v94_p7 의 잘못된 접근 인정" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "v94_p7 의 PROC 처방 'EXEC sp ?, CAST(? AS date)' 는" -ForegroundColor White
Write-Host "MSSQL EXEC 문법이 인자에 표현식 허용 안 함 → 새 에러 야기:" -ForegroundColor White
Write-Host "  '42000 — Incorrect syntax near @P1'" -ForegroundColor Red
Write-Host ""
Write-Host "v94_p7 의 FUNCTION 처방 'CAST(N'2024-01-01' AS date)' 는" -ForegroundColor White
Write-Host "일부 환경에서 N 접두사 변환 실패 → 새 에러:" -ForegroundColor White
Write-Host "  '22007 — Conversion failed when converting date'" -ForegroundColor Red
Write-Host ""
Write-Host "본부장님 우려: '향후 다양한 DB 이관때 검증 될지'" -ForegroundColor Yellow
Write-Host "→ 정당한 우려. 표준 방식으로 처방 재설계." -ForegroundColor White

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  v94_p8 본질 처방" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[처방 1] PROCEDURE — 표준 ? 바인딩 + Python 객체 변환" -ForegroundColor Cyan
Write-Host "  변경 전: EXEC sp ?, CAST(? AS date)         (잘못된 문법)" -ForegroundColor Red
Write-Host "  변경 후: EXEC sp ?, ?  + Python datetime 객체 전달" -ForegroundColor Green
Write-Host "  본질: pyodbc 가 datetime.date 객체를 sql_date 로 자동 보냄" -ForegroundColor White
Write-Host "        → MSSQL 이 변환 없이 즉시 사용 → strict 변환 회피" -ForegroundColor White
Write-Host ""
Write-Host "[처방 2] FUNCTION — CONVERT 스타일 명시" -ForegroundColor Cyan
Write-Host "  변경 전: CAST(N'2024-01-01' AS date)        (22007 발생)" -ForegroundColor Red
Write-Host "  변경 후: CONVERT(date, '2024-01-01', 23)    (ISO 명시)" -ForegroundColor Green
Write-Host "  본질: N 접두사 제거 (Unicode 변환 회피)" -ForegroundColor White
Write-Host "        스타일 23 = ISO 8601 (yyyy-mm-dd) — dateformat 무관" -ForegroundColor White
Write-Host "        스타일 121 = ISO 8601 datetime (yyyy-mm-dd hh:mi:ss.mmm)" -ForegroundColor White
Write-Host ""
Write-Host "[견고성] 다양한 입력 형식 자동 정규화" -ForegroundColor Cyan
Write-Host "  '2024-01-01'   → 정상" -ForegroundColor Green
Write-Host "  '20240101'     → '2024-01-01' (YYYYMMDD 자동 변환)" -ForegroundColor Green
Write-Host "  '2024/01/01'   → '2024-01-01' (slash → dash)" -ForegroundColor Green
Write-Host "  varchar 'A'    → 그대로 (date 만 변환)" -ForegroundColor Green
Write-Host "  bigint 1       → 그대로 (변환 없음)" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  검증 — 같은 7개 객체 다시 테스트" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "기대 결과:" -ForegroundColor Cyan
Write-Host "  fn_age, fn_korean_date, fn_next_business_day → ✓ ✓ (소스+타겟)" -ForegroundColor Green
Write-Host "  sp_close_branch, sp_daily_batch, sp_refresh_fx → ✓ ✓" -ForegroundColor Green
Write-Host "  tvf_daily_trx 소스 → ✓ (타겟은 1318 — 별도 KB 처방 적용 시)" -ForegroundColor Green
Write-Host ""
Write-Host "남는 것 (별개 본질):" -ForegroundColor Yellow
Write-Host "  sp_mark_delinquent 타겟  : 데이터 의존 (contract_id NULL)" -ForegroundColor White
Write-Host "  tvf_delinq_ranking 타겟 : 1305 이름 매핑 (재이관 시 KB 효과)" -ForegroundColor White
Write-Host "  tvf_daily_trx 타겟       : 1318 변환 손실 (재이관 시 KB 효과)" -ForegroundColor White
Write-Host "  trg_bank_primary         : 이관 자체 누락 (별도 이슈)" -ForegroundColor White

Write-Host "`n적용 절차:" -ForegroundColor Yellow
Write-Host "  1. ZIP 풀기 (D:\project\ 위)" -ForegroundColor White
Write-Host "  2. Get-Process python | Stop-Process -Force" -ForegroundColor White
Write-Host "  3. cd D:\project\databridge_full\backend; run_backend.bat" -ForegroundColor White
Write-Host "  4. 테스트 7개 객체 다시 실행 → 깨끗하게" -ForegroundColor White
Write-Host ""
Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  본부장님 우려 답변 — 향후 다양한 DB 이관 검증" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "이번 v94_p8 의 처방 원칙:" -ForegroundColor Cyan
Write-Host "  1. 각 DB 의 표준 권장 방식 따르기 (pyodbc ? 바인딩, ISO 형식)" -ForegroundColor White
Write-Host "  2. 추측이 아닌 *드라이버 공식 문서* 기반" -ForegroundColor White
Write-Host "  3. Python datetime 객체 활용 — 어느 DB 든 안전 (Oracle, DB2 동일)" -ForegroundColor White
Write-Host ""
Write-Host "v95 큰 그림 (별도 논의):" -ForegroundColor Cyan
Write-Host "  - DB-specific 호출 어댑터 패턴 (MSSQL/MySQL/Oracle/DB2)" -ForegroundColor White
Write-Host "  - 자동 회귀 테스트 (매 처방 시 기존 정상 케이스도 함께 확인)" -ForegroundColor White
