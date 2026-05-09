# v95_p15 적용 스크립트 (UTF-8 BOM)
# v95_p14 위에 누적 — Phase 3-A/B/C/D 추가
# 본부장님 본질 처방 (2026-05-03 새 하루): 5개 테이블 KeyError + T-SQL 변환 버그

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  v95_p15 적용 — Phase 3-A/B/C/D 본질 처방" -ForegroundColor Cyan
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
    "$ProjectRoot\backend\app\engine\migration_engine.py" = @{
        "v95_p13 Phase 1-B: UDT" = "v95_p13 UDT (필수 누적)"
        "v95_p14 Phase 2-D"      = "v95_p14 양방향 등록 (필수 누적)"
        "v95_p15 Phase 3-A"      = "v95_p15 dict 초기화 swap 후 이동 ★"
    }
    "$ProjectRoot\backend\app\core\obj_executor.py" = @{
        "v95_p15 Phase 3-B"      = "v95_p15 CASE WHEN ; 정정"
        "v95_p15 Phase 3-C"      = "v95_p15 IF...END → END IF;"
        "v95_p15 Phase 3-D"      = "v95_p15 TRIGGER case 안전망"
    }
}

$missing = @()
foreach ($file in $markers.Keys) {
    $content = Get-Content $file -Raw -ErrorAction SilentlyContinue
    if (-not $content) { 
        Write-Host "  ✗ 파일 없음: $file" -ForegroundColor Red
        $missing += $file
        continue
    }
    foreach ($m in $markers[$file].GetEnumerator()) {
        if ($content -match [regex]::Escape($m.Key)) {
            Write-Host "  ✓ $($m.Value)" -ForegroundColor Green
        } else {
            Write-Host "  ✗ 누락: $($m.Value)" -ForegroundColor Red
            $missing += $m.Key
        }
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
Write-Host "  ✅ v95_p15 적용 완료" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "다음 단계:" -ForegroundColor Yellow
Write-Host "  ① UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  ② aw_target DROP 후 재이관:" -ForegroundColor White
Write-Host "     docker exec db_mysql mysql -u root -pbridge1234 -e ""DROP DATABASE aw_target; CREATE DATABASE aw_target CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci""" -ForegroundColor White
Write-Host "  ③ 새 Job 실행 → 결과 측정" -ForegroundColor White
Write-Host ""
Write-Host "기대 결과:" -ForegroundColor Cyan
Write-Host "  - 테이블: 71/71 (100%) ★ Phase 3-A KeyError 해결" -ForegroundColor White
Write-Host "  - FUNC:   11/11 (100%) ★ Phase 3-B CASE ; 정정" -ForegroundColor White
Write-Host "  - SP:     8~10/10     ★ Phase 3-C IF END" -ForegroundColor White
Write-Host "  - VIEW:   18~20/20    ★ Employee 살아남 → 도미노 해결" -ForegroundColor White
Write-Host "  - TRIG:   8~9/10      ★ AFTER trigger 별도 처방 필요 (남음)" -ForegroundColor White
Write-Host "  - 전체:   85~92%      (53% → 85%+ 도달 목표)" -ForegroundColor White
Write-Host ""
