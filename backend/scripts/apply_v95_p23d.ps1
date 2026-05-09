# v95_p23d 적용 스크립트 (UTF-8 BOM, 2026-05-03)
# 본부장님 SQL-FAIL-DUMP 100% 기반 처방 — 진짜 호출 자리 obj_executor.py
#
# v95_p17 의 추측 정규식이 미스매치 → v95_p23d 에서 정확한 정규식
# 단일 파일 단일 자리 (단일 본질 단일 처방)

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  v95_p23d 적용 — 진짜 호출 자리 정규식 정확화" -ForegroundColor Cyan
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

$file = "$ProjectRoot\backend\app\core\obj_executor.py"
$content = Get-Content $file -Raw -ErrorAction SilentlyContinue

if (-not $content) {
    Write-Host "  ✗ 파일 없음: obj_executor.py" -ForegroundColor Red
    exit 1
}

# 단순 키워드 매치 (정규식 escape 안전 - v95_p23c 사고 교훈)
if ($content.Contains("v95_p23d")) {
    Write-Host "  ✓ v95_p23d 마커 적용됨" -ForegroundColor Green
} else {
    Write-Host "  ✗ v95_p23d 마커 누락" -ForegroundColor Red
    exit 1
}

if ($content.Contains("[v95_p23d] AI 후처리 적용")) {
    Write-Host "  ✓ 호출 자리 로깅 갱신됨" -ForegroundColor Green
} else {
    Write-Host "  ✗ 호출 자리 로깅 누락" -ForegroundColor Red
}

Write-Host ""
Write-Host "[4/4] 백엔드 시작..." -ForegroundColor Yellow
Push-Location "$ProjectRoot\backend"
Start-Process -FilePath ".\run_backend.bat" -WindowStyle Normal
Pop-Location
Start-Sleep -Seconds 8

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✅ v95_p23d 적용 완료" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "검증 절차:" -ForegroundColor Yellow
Write-Host "  ① UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  ② DB 초기화 (선택):" -ForegroundColor White
Write-Host "     docker exec db_mysql mysql -u root -pbridge1234 -e ""DROP DATABASE IF EXISTS aw_target; CREATE DATABASE aw_target CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci""" -ForegroundColor Gray
Write-Host "  ③ 새 Job 생성 → FUNC/SP 만 선택해서 빠른 이관" -ForegroundColor White
Write-Host "  ④ FUNC 3 + SP 2 = 5건 모두 정상 작동 확인" -ForegroundColor White
Write-Host ""
Write-Host "기대 결과:" -ForegroundColor Cyan
Write-Host "  - FUNC CASE WHEN ; (3건): 0건" -ForegroundColor White
Write-Host "  - SP END IF; (2건): 0건" -ForegroundColor White
Write-Host "  - [v95_p23d] AI 후처리 적용 로그 5건" -ForegroundColor White
Write-Host ""
Write-Host "검증 명령:" -ForegroundColor Cyan
Write-Host '  Get-Content D:\project\databridge_full\backend\logs\databridge_backend.log -Tail 5000 | Select-String "v95_p23d" | Select-Object -Last 10' -ForegroundColor Gray
Write-Host ""
