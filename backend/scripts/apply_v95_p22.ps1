# v95_p22 적용 스크립트 (UTF-8 BOM, 2026-05-03)
# 본부장님 두 번 약속한 두 의제 정리:
#   ① v95_p19 호출 비활성화 (정규식 미매치로 미작동, 부작용 없음)
#   ② ○ 가드 정밀 강화 (진단 데이터 기반 - type 없으면 제외)

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  v95_p22 적용 — 약속한 두 의제 한방에 정리" -ForegroundColor Cyan
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

Write-Host "[3/4] 패치 마커 검증..." -ForegroundColor Yellow

$markers = @{
    "$ProjectRoot\backend\app\api\routes\schema.py"       = "v95_p22 (2026-05-03): v95_p19 호출 비활성화"
    "$ProjectRoot\frontend\src\pages\JobMonitor.vue"      = "v95_p22"
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
Write-Host "  ✅ v95_p22 적용 완료" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "검증 절차:" -ForegroundColor Yellow
Write-Host "  ① UI Ctrl+Shift+R (강제 새로고침)" -ForegroundColor White
Write-Host "  ② 이관 모니터 화면 들어가기" -ForegroundColor White
Write-Host "  ③ ○ 항목 (Person_AddressType 등 schema_name 형식) 사라졌는지 확인" -ForegroundColor White
Write-Host ""
Write-Host "기대 결과:" -ForegroundColor Cyan
Write-Host "  - 이전: 전체 185 항목 (66개 ○)" -ForegroundColor White
Write-Host "  - v95_p22: 전체 119 항목 (○ 0개)" -ForegroundColor Green
Write-Host ""
Write-Host "검증 명령 (브라우저 콘솔):" -ForegroundColor Cyan
Write-Host "  fetch('/api/v1/jobs/').then(r=>r.json()).then(jobs=>{const i=jobs[0].item_statuses||{};const noType=Object.entries(i).filter(([k,v])=>!v.type).length;console.log('전체:',Object.keys(i).length,'type 없음(제외 대상):',noType)})" -ForegroundColor Gray
Write-Host ""
