# v95_p23c 적용 스크립트 (UTF-8 BOM, 2026-05-03)
# 본부장님 SQL-FAIL-DUMP 진짜 데이터 100% 기반 처방:
#   본질 A: CASE expr; (FUNC 3건) - ufnGetDocumentStatusText 등
#   본질 B: 명령 끝 ; 누락 (SP 2건) - CALL X() / COMMIT 후 END IF

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  v95_p23c 적용 — FUNC/SP 5건 진짜 패턴 처방" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/4] 백엔드 정지..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3

Write-Host "[2/4] __pycache__ 정리..." -ForegroundColor Yellow
Get-ChildItem -Path "$ProjectRoot\backend" -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue
}
Write-Host "  ✓ pycache 정리" -ForegroundColor Green

Write-Host "[3/4] 패치 마커 검증..." -ForegroundColor Yellow

$file = "$ProjectRoot\backend\app\api\routes\schema.py"
$content = Get-Content $file -Raw -ErrorAction SilentlyContinue
if (-not $content) {
    Write-Host "  ✗ 파일 없음: schema.py" -ForegroundColor Red
    exit 1
}

# 4가지 검증
$checks = @{
    "v95_p23c 마커"               = "v95_p23c"
    "본질 A 정규식 (CASE expr;)"  = "CASE\\s\\+\\\\w\\+\\);"
    "본질 B 정규식 (END IF)"      = "COMMIT\\\\b\\|\\\\bROLLBACK"
    "재활성화 (호출 코드)"         = "stmts = \[_post_fix_ai_stmt"
}
foreach ($name in $checks.Keys) {
    if ($content -match [regex]::Escape($checks[$name]) -or $content -match $checks[$name]) {
        Write-Host "  ✓ $name 적용됨" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $name 누락" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "[4/4] 백엔드 시작..." -ForegroundColor Yellow
Push-Location "$ProjectRoot\backend"
Start-Process -FilePath ".\run_backend.bat" -WindowStyle Normal
Pop-Location
Start-Sleep -Seconds 8

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✅ v95_p23c 적용 완료" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "검증 절차:" -ForegroundColor Yellow
Write-Host "  ① UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  ② 새 Job 생성 → FUNC/SP 만 선택해서 빠른 이관" -ForegroundColor White
Write-Host "  ③ FUNC 3 + SP 2 = 5건 모두 정상 작동 확인" -ForegroundColor White
Write-Host ""
Write-Host "기대 결과:" -ForegroundColor Cyan
Write-Host "  - FUNC CASE WHEN ; (3건): 0건" -ForegroundColor White
Write-Host "  - SP END IF; (2건): 0건" -ForegroundColor White
Write-Host "  - post-fix 작동 흔적 로그 출현" -ForegroundColor White
Write-Host ""
Write-Host "검증 명령:" -ForegroundColor Cyan
Write-Host '  Get-Content D:\project\databridge_full\backend\logs\databridge_backend.log -Tail 5000 | Select-String "v95_p23c.*post-fix applied" | Select-Object -Last 10' -ForegroundColor Gray
Write-Host ""
