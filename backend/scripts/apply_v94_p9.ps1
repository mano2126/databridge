$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v94_p9 — 본부장님 PowerShell 검증 패턴 적용" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v94_p9_$ts"
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
Write-Host "  정직한 진단 — v94_p7/p8 모두 잘못된 가설" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "v94_p7: EXEC sp ?, CAST(? AS date)        ← 42000 (CAST 표현식)" -ForegroundColor Red
Write-Host "v94_p8: EXEC sp ?, ? + Python datetime   ← 8114 (ODBC nvarchar 변환)" -ForegroundColor Red
Write-Host ""
Write-Host "본부장님이 PowerShell 로 직접 검증해주신 정답:" -ForegroundColor Cyan
Write-Host "  DECLARE @p1 nvarchar(10) = 'A';" -ForegroundColor Green
Write-Host "  DECLARE @p2 date = '2024-01-01';" -ForegroundColor Green
Write-Host "  EXEC ref.sp_close_branch @p1, @p2;     ← 정상 작동!" -ForegroundColor Green
Write-Host ""
Write-Host "→ v94_p9 는 이 패턴 그대로 코드 생성" -ForegroundColor Yellow

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  처방 — DECLARE + EXEC 한 SQL 블록" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[PROCEDURE] sys.parameters 의 정확한 타입으로 DECLARE 생성" -ForegroundColor Cyan
Write-Host "  변경 전: cur.execute('EXEC sp ?, ?', [...])" -ForegroundColor White
Write-Host "  변경 후: cur.execute('''" -ForegroundColor White
Write-Host "             DECLARE @_p0 varchar(10) = 'A';" -ForegroundColor Green
Write-Host "             DECLARE @_p1 date = '2024-01-01';" -ForegroundColor Green
Write-Host "             EXEC [ref].[sp_close_branch] @_p0, @_p1;" -ForegroundColor Green
Write-Host "           ''')" -ForegroundColor White
Write-Host "  → pyodbc 의 ? 바인딩 우회 → ODBC nvarchar 변환 회피" -ForegroundColor White
Write-Host ""
Write-Host "[FUNCTION] 기존 CONVERT 처방 유지 + 진단 로그 추가" -ForegroundColor Cyan
Write-Host "  로그: [execute-object/FUNCTION] obj=fn_age _fn_ptypes=['date']" -ForegroundColor White
Write-Host "  로그: [execute-object/FUNCTION] 실행 SQL: SELECT [ref].[fn_age](CONVERT(date, '2024-01-01', 23)) AS result" -ForegroundColor White
Write-Host "  → 만약 또 22007 나면 로그로 진짜 본질 즉시 확인 가능" -ForegroundColor White

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  검증 — 본부장님 PowerShell 패턴과 동일" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "본부장님 검증 SQL:" -ForegroundColor Cyan
Write-Host "  DECLARE @p1 nvarchar(10) = 'A';" -ForegroundColor White
Write-Host "  DECLARE @p2 date = '2024-01-01';" -ForegroundColor White
Write-Host "  EXEC ref.sp_close_branch @p1, @p2;       ← ✓ 정상" -ForegroundColor Green
Write-Host ""
Write-Host "v94_p9 가 생성하는 SQL:" -ForegroundColor Cyan
Write-Host "  DECLARE @_p0 varchar(10) = 'A';" -ForegroundColor White
Write-Host "  DECLARE @_p1 date = '2024-01-01';" -ForegroundColor White
Write-Host "  EXEC [ref].[sp_close_branch] @_p0, @_p1; ← 동일 패턴" -ForegroundColor Green

Write-Host "`n적용 절차:" -ForegroundColor Yellow
Write-Host "  1. ZIP 풀기 (D:\project\ 위)" -ForegroundColor White
Write-Host "  2. Get-Process python | Stop-Process -Force" -ForegroundColor White
Write-Host "  3. cd D:\project\databridge_full\backend; run_backend.bat" -ForegroundColor White
Write-Host "  4. 7개 객체 다시 테스트" -ForegroundColor White
Write-Host ""
Write-Host "검증 마커 (성공 시 로그):" -ForegroundColor Cyan
Write-Host "  '[execute-object/PROCEDURE] 실행 SQL 블록:'" -ForegroundColor Green
Write-Host "  '[execute-object/FUNCTION] 실행 SQL: SELECT ... CONVERT(date, ..., 23)'" -ForegroundColor Green
Write-Host ""
Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  ⚠ 만약 또 실패하면 — 로그가 진짜 본질 알려줍니다" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "v94_p9 는 진단 로그 포함 — 만약 또 실패하면:" -ForegroundColor White
Write-Host "  Get-Content D:\project\databridge_full\backend\logs\databridge_backend.log -Tail 50 |" -ForegroundColor White
Write-Host "    Select-String 'execute-object/'" -ForegroundColor White
Write-Host ""
Write-Host "→ 이 로그가 보내진 진짜 SQL 보여줌 → 추측 없이 본질 확정" -ForegroundColor White
