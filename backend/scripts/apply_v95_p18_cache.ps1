# v95_p18_cache 적용 스크립트 (UTF-8 BOM, 2026-05-03)
# 본부장님 본질 처방: AI DBA Consultant 분석 결과 캐시화
# → 같은 입력이면 캐시에서 즉시 반환 (비용 0, 1초 응답)

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  v95_p18_cache 적용 — AI DBA Advisor 결과 캐시화" -ForegroundColor Cyan
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

# 짧고 정확한 마커만 (false negative 회피)
$markers = @{
    "$ProjectRoot\backend\app\core\advisor_cache.py"           = "compute_cache_key"
    "$ProjectRoot\backend\app\api\routes\advisor.py"           = "v95_p18_cache"
    "$ProjectRoot\frontend\src\components\advisor\AdvisorPanel.vue" = "fromCache"
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

# 캐시 디렉토리 자동 생성 (백엔드가 만들지만 미리 확인)
$cacheDir = "$ProjectRoot\backend\cache\advisor_analysis"
if (-not (Test-Path $cacheDir)) {
    New-Item -Path $cacheDir -ItemType Directory -Force | Out-Null
    Write-Host "  ✓ 캐시 디렉토리 생성: $cacheDir" -ForegroundColor Green
} else {
    $existingCount = (Get-ChildItem $cacheDir -Filter "*.json" -ErrorAction SilentlyContinue).Count
    Write-Host "  ℹ 기존 캐시: $existingCount 건" -ForegroundColor Gray
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✅ v95_p18_cache 적용 완료" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "사용 방법:" -ForegroundColor Yellow
Write-Host "  ① UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  ② Job 위저드 → Step 4 (AI DBA 권고) → 분석 시작" -ForegroundColor White
Write-Host "  ③ 첫 분석: AI 호출 → 결과 캐시 자동 저장" -ForegroundColor White
Write-Host "  ④ 두번째+: 같은 입력이면 캐시에서 즉시 반환 ★" -ForegroundColor White
Write-Host ""
Write-Host "캐시 입증 표시:" -ForegroundColor Cyan
Write-Host "  - 결과 화면 상단에 ⚡ '캐시 사용 중' 배지 (녹색)" -ForegroundColor White
Write-Host "  - '🔄 새로 분석' 버튼으로 강제 새 AI 호출 가능 (비용 발생)" -ForegroundColor White
Write-Host ""
Write-Host "캐시 관리 API:" -ForegroundColor Cyan
Write-Host "  GET    /api/v1/advisor/cache/list     — 캐시 목록" -ForegroundColor Gray
Write-Host "  DELETE /api/v1/advisor/cache/{key}    — 특정 캐시 삭제" -ForegroundColor Gray
Write-Host "  DELETE /api/v1/advisor/cache          — 전체 캐시 삭제" -ForegroundColor Gray
Write-Host ""
Write-Host "기대 효과:" -ForegroundColor Yellow
Write-Host "  - 같은 DB 반복 이관 테스트 → AI 비용 99%+ 감소" -ForegroundColor White
Write-Host "  - 분석 시간: 60초 → 1초" -ForegroundColor White
Write-Host "  - 결정론적: 같은 입력 = 같은 권고 (재현성)" -ForegroundColor White
Write-Host ""
