# v95_p17 적용 스크립트 (UTF-8 BOM)
# v95_p15 위에 누적 — 3가지 의제 한방에:
#   1) AI 결과 정규식 후처리 (잔여 8건 처방)
#   2) ETA smoothing 강화 (10개 + 트리밍 평균)
#   3) ○ 유령 항목 가드 강화 (제거)

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  v95_p17 적용 — 3가지 의제 한방에" -ForegroundColor Cyan
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

# v95_p17 마커만 (가변 텍스트 회피 — false negative 방지)
$markers = @{
    "$ProjectRoot\backend\app\core\obj_executor.py"  = "_post_fix_ai_ddl"
    "$ProjectRoot\frontend\src\pages\JobMonitor.vue" = "v95_p17"
}

$missing = @()
foreach ($file in $markers.Keys) {
    $content = Get-Content $file -Raw -ErrorAction SilentlyContinue
    if (-not $content) {
        Write-Host "  ✗ 파일 없음: $file" -ForegroundColor Red
        $missing += $file
        continue
    }
    if ($content -match [regex]::Escape($markers[$file])) {
        Write-Host "  ✓ $($file | Split-Path -Leaf): v95_p17 마커 OK" -ForegroundColor Green
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
Write-Host "  ✅ v95_p17 적용 완료" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "다음 단계:" -ForegroundColor Yellow
Write-Host "  ① UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  ② aw_target DROP + 재이관:" -ForegroundColor White
Write-Host "     docker exec db_mysql mysql -u root -pbridge1234 -e ""DROP DATABASE aw_target; CREATE DATABASE aw_target CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci""" -ForegroundColor White
Write-Host "  ③ 새 Job 실행 → 결과 측정" -ForegroundColor White
Write-Host ""
Write-Host "기대 결과:" -ForegroundColor Cyan
Write-Host "  - 잔여 오류: 8건 → 1-3건 (95% → 98%+)" -ForegroundColor White
Write-Host "  - ETA: 들쭉날쭉 완화 (트리밍 평균)" -ForegroundColor White
Write-Host "  - 화면: ○ 64개 사라짐" -ForegroundColor White
Write-Host ""
