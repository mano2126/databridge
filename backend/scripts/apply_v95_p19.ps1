# v95_p19 적용 스크립트 (UTF-8 BOM, 2026-05-03)
# 본부장님 본질 처방 — schema.py:3697 정확한 자리에 AI statements 후처리
# v95_p18_cache 동시 적용 (AI Advisor 결과 캐시화)

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  v95_p19 + v95_p18_cache 적용 — 한방에" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/5] 백엔드 정지..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3

Write-Host "[2/5] __pycache__ 정리..." -ForegroundColor Yellow
Get-ChildItem -Path "$ProjectRoot\backend" -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue
}
Write-Host "  ✓ pycache 정리" -ForegroundColor Green

Write-Host "[3/5] Vite 캐시 정리..." -ForegroundColor Yellow
$viteCache = "$ProjectRoot\frontend\node_modules\.vite"
if (Test-Path $viteCache) {
    Remove-Item -Recurse -Force $viteCache -ErrorAction SilentlyContinue
    Write-Host "  ✓ Vite 캐시 정리" -ForegroundColor Green
} else {
    Write-Host "  → Vite 캐시 없음" -ForegroundColor Gray
}

Write-Host "[4/5] 패치 마커 검증..." -ForegroundColor Yellow

# 짧고 정확한 마커만 (false negative 회피)
$markers = @{
    "$ProjectRoot\backend\app\api\routes\schema.py"              = "_post_fix_ai_stmt"
    "$ProjectRoot\backend\app\core\advisor_cache.py"             = "compute_cache_key"
    "$ProjectRoot\backend\app\api\routes\advisor.py"             = "v95_p18_cache"
    "$ProjectRoot\frontend\src\components\advisor\AdvisorPanel.vue" = "fromCache"
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
Write-Host "[5/5] 백엔드 시작..." -ForegroundColor Yellow
Push-Location "$ProjectRoot\backend"
Start-Process -FilePath ".\run_backend.bat" -WindowStyle Normal
Pop-Location
Start-Sleep -Seconds 8

# 캐시 디렉토리 확인
$cacheDir = "$ProjectRoot\backend\cache\advisor_analysis"
if (-not (Test-Path $cacheDir)) {
    New-Item -Path $cacheDir -ItemType Directory -Force | Out-Null
    Write-Host "  ✓ 캐시 디렉토리 생성: $cacheDir" -ForegroundColor Green
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✅ v95_p19 + v95_p18_cache 적용 완료" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "다음 단계:" -ForegroundColor Yellow
Write-Host "  ① UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  ② aw_target DROP + 재이관:" -ForegroundColor White
Write-Host '     docker exec db_mysql mysql -u root -pbridge1234 -e "DROP DATABASE aw_target; CREATE DATABASE aw_target CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"' -ForegroundColor White
Write-Host "  ③ Job 위저드 → Step 4 (AI DBA 권고) → 첫 분석 (캐시 저장)" -ForegroundColor White
Write-Host "  ④ 새 이관 실행 → 결과 측정" -ForegroundColor White
Write-Host ""
Write-Host "검증 포인트:" -ForegroundColor Cyan
Write-Host "  - v95_p19 작동 흔적 (백엔드 로그):" -ForegroundColor White
Write-Host '     Get-Content D:\project\databridge_full\backend\logs\databridge_backend.log -Tail 5000 | Select-String "v95_p19"' -ForegroundColor Gray
Write-Host "  - 두 번째 분석부터 ⚡ '캐시 사용 중' 배지 표시" -ForegroundColor White
Write-Host ""
Write-Host "기대 결과:" -ForegroundColor Cyan
Write-Host "  - FUNC: 8/11 → 11/11 (CASE WHEN ; 자동 정정)" -ForegroundColor White
Write-Host "  - SP:   8/10 → 10/10 (END IF; 자동 보강)" -ForegroundColor White
Write-Host "  - 전체: 95% → 98%+ ★" -ForegroundColor White
Write-Host "  - AI 비용: 같은 DB 반복 시 99% 절감" -ForegroundColor White
Write-Host ""
