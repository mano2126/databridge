# v95_p16_ui 적용 스크립트 (UTF-8 BOM)
# 두 가지 UI 처방:
#   1) JobWizard Step 5 — opts-grid 폭 안정화 (좌측 두 줄 깨짐 방지)
#   2) JobList — 컴팩트 행 (엔터프라이즈 룩)
#
# 본부장님 원칙: 코드 로직 안 건드림, CSS 만 수정 (안전)

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  v95_p16_ui 적용 — JobWizard + JobList UI 개선" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] 패치 마커 검증..." -ForegroundColor Yellow

$markers = @{
    "$ProjectRoot\frontend\src\pages\JobWizard.vue" = "v95_p16_ui (2026-05-03 본부장님 본질 처방)"
    "$ProjectRoot\frontend\src\pages\JobList.vue"   = "v95_p16_ui (2026-05-03): 본부장님 컴팩트화 처방"
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
Write-Host "[2/3] Vite 캐시 정리 (강제 새로고침)..." -ForegroundColor Yellow
$viteCache = "$ProjectRoot\frontend\node_modules\.vite"
if (Test-Path $viteCache) {
    Remove-Item -Recurse -Force $viteCache -ErrorAction SilentlyContinue
    Write-Host "  ✓ Vite 캐시 정리" -ForegroundColor Green
} else {
    Write-Host "  → Vite 캐시 없음 (정상)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "[3/3] 적용 안내..." -ForegroundColor Yellow
Write-Host "  ℹ Frontend hot reload 가 자동 적용 (npm run dev 가동 중인 경우)" -ForegroundColor Gray
Write-Host "  ℹ 백엔드 재시작 불필요 (CSS 변경만 — 백엔드 무관)" -ForegroundColor Gray

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✅ v95_p16_ui 적용 완료" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "다음 단계:" -ForegroundColor Yellow
Write-Host "  ① 브라우저에서 Ctrl+Shift+R (강제 새로고침)" -ForegroundColor White
Write-Host "  ② Job 생성 위저드 → Step 5 → 좌측 폼이 한 줄로 표시되는지 확인" -ForegroundColor White
Write-Host "  ③ Job 관리 화면 → 행 높이 약 35px 로 컴팩트하게" -ForegroundColor White
Write-Host ""
Write-Host "비교:" -ForegroundColor Cyan
Write-Host "  Step 5 (변경 전): 좌측 '이관 엔진 (대량량)' 두 줄 깨짐" -ForegroundColor Gray
Write-Host "  Step 5 (변경 후): 좌측 '이관 엔진 (대용량)' 한 줄, 우측 메시지 줄바꿈" -ForegroundColor Green
Write-Host "  JobList (변경 전): 행 높이 50px (한 화면 11개)" -ForegroundColor Gray
Write-Host "  JobList (변경 후): 행 높이 35px (한 화면 약 16개)" -ForegroundColor Green
Write-Host ""
