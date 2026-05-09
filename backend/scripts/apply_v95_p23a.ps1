# v95_p23a 적용 스크립트 (UTF-8 BOM, 2026-05-03)
# 본부장님 4가지 본질 한방에 처방:
#   ① 임시 진단 로깅 (AI 진짜 결과 → v95_p23b 정규식 데이터)
#   ② Deadlock 방지 (CREATE TABLE 모듈 직렬화)
#   ③ 통계 1102 (db_name 다중 fallback)
#   ④ 위저드 사전 분석 (Pre-Flight)

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  v95_p23a 적용 — 본부장님 4가지 본질 한방에" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/4] 백엔드 정지..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3

Write-Host "[2/4] __pycache__ + Vite 캐시 정리..." -ForegroundColor Yellow
Get-ChildItem -Path "$ProjectRoot\backend" -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue
}
$viteCache = "$ProjectRoot\frontend\node_modules\.vite"
if (Test-Path $viteCache) {
    Remove-Item -Recurse -Force $viteCache -ErrorAction SilentlyContinue
    Write-Host "  ✓ Vite 캐시 정리" -ForegroundColor Green
}
Write-Host "  ✓ pycache 정리" -ForegroundColor Green

Write-Host "[3/4] 패치 마커 검증 (4가지 본질)..." -ForegroundColor Yellow

$markers = @{
    "$ProjectRoot\backend\app\api\routes\schema.py"           = "v95_p23a-DIAG"
    "$ProjectRoot\backend\app\engine\migration_engine.py"     = "_create_table_lock"
    "$ProjectRoot\backend\app\api\routes\preflight.py"        = "preflight_analyze"
    "$ProjectRoot\backend\main.py"                            = "preflight,"
    "$ProjectRoot\frontend\src\pages\JobWizard.vue"           = "runPreflightAnalysis"
}

$missing = @()
foreach ($file in $markers.Keys) {
    $content = Get-Content $file -Raw -ErrorAction SilentlyContinue
    if (-not $content) {
        Write-Host "  ✗ 파일 없음: $($file | Split-Path -Leaf)" -ForegroundColor Red
        $missing += $file
        continue
    }
    if ($content -match [regex]::Escape($markers[$file])) {
        Write-Host "  ✓ $($file | Split-Path -Leaf): 마커 OK" -ForegroundColor Green
    } else {
        Write-Host "  ✗ 마커 없음: $($file | Split-Path -Leaf)" -ForegroundColor Red
        $missing += $file
    }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "✗ 패치 미적용. ZIP 다시 풀고 재실행" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[4/4] 백엔드 시작..." -ForegroundColor Yellow
Push-Location "$ProjectRoot\backend"
Start-Process -FilePath ".\run_backend.bat" -WindowStyle Normal
Pop-Location
Start-Sleep -Seconds 8

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✅ v95_p23a 적용 완료" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "검증 절차:" -ForegroundColor Yellow
Write-Host "  ① UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  ② Job 위저드 → 객체 선택 후 [다음] 클릭" -ForegroundColor White
Write-Host "  ③ Step 2 (변환 규칙) 화면 상단에 사전 분석 결과 패널 확인" -ForegroundColor White
Write-Host "  ④ 1회 이관 실행 → 끝나면 v95_p23a-DIAG 로그 확보:" -ForegroundColor White
Write-Host '     Get-Content D:\project\databridge_full\backend\logs\databridge_backend.log -Tail 5000 | Select-String "v95_p23a-DIAG" | Select-Object -First 30' -ForegroundColor Gray
Write-Host ""
Write-Host "기대 결과:" -ForegroundColor Cyan
Write-Host "  - Deadlock: 0건 (CREATE 직렬화)" -ForegroundColor White
Write-Host "  - 통계 1102: 0건 (db_name fallback)" -ForegroundColor White
Write-Host "  - Pre-Flight 패널: Step 2 진입 시 표시" -ForegroundColor White
Write-Host "  - DIAG 로그: AI 진짜 결과 → v95_p23b 정규식 데이터" -ForegroundColor White
Write-Host ""
