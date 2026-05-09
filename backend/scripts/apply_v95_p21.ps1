# v95_p21 적용 스크립트 (UTF-8 BOM, 2026-05-03)
# 본부장님 본질 처방 — 캐시 사전 표시 (분석 시작 전 비용 알림)

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  v95_p21 적용 — 캐시 사전 표시 (비용 바로 알림)" -ForegroundColor Cyan
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

$markers = @{
    "$ProjectRoot\backend\app\api\routes\advisor.py"             = "check-cache"
    "$ProjectRoot\frontend\src\components\advisor\AdvisorPanel.vue" = "preCheckCache"
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
Write-Host "  ✅ v95_p21 적용 완료" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "검증 절차:" -ForegroundColor Yellow
Write-Host "  ① UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  ② Job 위저드 → Step 4 (AI DBA 권고)" -ForegroundColor White
Write-Host "  ③ 모드 선택 (Smart/Hybrid/Deep)" -ForegroundColor White
Write-Host "  ④ 비용 영역 위 배너 확인:" -ForegroundColor White
Write-Host "     - 캐시 있음:  ⚡ 캐시 적중 — 무료 분석" -ForegroundColor Green
Write-Host "     - 캐시 없음:  🆕 첫 분석 — 캐시 자동 저장" -ForegroundColor Yellow
Write-Host "  ⑤ 분석 시작 버튼 라벨 변경 확인:" -ForegroundColor White
Write-Host "     - 캐시 있음: '⚡ 캐시 사용 (무료, 1초)' (녹색)" -ForegroundColor Green
Write-Host "     - 캐시 없음: '경제형 분석 시작' (기존 보라색)" -ForegroundColor White
Write-Host ""
Write-Host "기대 효과:" -ForegroundColor Cyan
Write-Host "  - 분석 시작 버튼 누르기 전에 비용 발생 여부 명확" -ForegroundColor White
Write-Host "  - 같은 DB 반복 테스트 시 안심" -ForegroundColor White
Write-Host "  - 새 DB 분석 시 '다음번부터 무료' 인지" -ForegroundColor White
Write-Host ""
