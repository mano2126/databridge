# v95_p23f 적용 스크립트 (UTF-8 BOM, 2026-05-03)
# 본부장님 22:06 진단 결과 기반 — line 2840 키 불일치 수정
#
# 진짜 본질: chunk SELECT 자리에서 _src_schema_map lookup 키 잘못
#   기존: get(table)   [table='Production_Document'] → None → 42S02 에러
#   수정: get(src_bare) [src_bare='Document'] → 'Production' 매치!
#
# 단일 자리 단일 본질 (다른 6자리와 패턴 100% 일관)

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  v95_p23f 적용 — chunk SELECT 키 불일치 수정" -ForegroundColor Cyan
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

$file = "$ProjectRoot\backend\app\engine\migration_engine.py"
$content = Get-Content $file -Raw -ErrorAction SilentlyContinue

if (-not $content) {
    Write-Host "  ✗ 파일 없음: migration_engine.py" -ForegroundColor Red
    exit 1
}

# 단순 .Contains() 매치 (정규식 escape 안전)
if ($content.Contains("v95_p23f")) {
    Write-Host "  ✓ v95_p23f 마커 적용됨" -ForegroundColor Green
} else {
    Write-Host "  ✗ v95_p23f 마커 누락" -ForegroundColor Red
    exit 1
}

if ($content.Contains("키 불일치 수정")) {
    Write-Host "  ✓ 본질 코멘트 있음" -ForegroundColor Green
}

Write-Host ""
Write-Host "[4/4] 백엔드 시작..." -ForegroundColor Yellow
Push-Location "$ProjectRoot\backend"
Start-Process -FilePath ".\run_backend.bat" -WindowStyle Normal
Pop-Location
Start-Sleep -Seconds 8

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✅ v95_p23f 적용 완료" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "검증 절차:" -ForegroundColor Yellow
Write-Host "  ① UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  ② DB 초기화 (선택):" -ForegroundColor White
Write-Host "     docker exec db_mysql mysql -u root -pbridge1234 -e ""DROP DATABASE IF EXISTS aw_target; CREATE DATABASE aw_target CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci""" -ForegroundColor Gray
Write-Host "  ③ 새 Job → 전체 이관" -ForegroundColor White
Write-Host ""
Write-Host "기대 결과:" -ForegroundColor Cyan
Write-Host "  - Production_Document 정상 이관 (42S02 에러 0건)" -ForegroundColor White
Write-Host "  - Production_ProductPhoto 정상 이관" -ForegroundColor White
Write-Host ""
Write-Host "검증 명령:" -ForegroundColor Cyan
Write-Host '  Get-Content D:\project\databridge_full\backend\logs\databridge_backend.log -Tail 5000 | Select-String "Document.*42S02|Document.*Invalid object" | Select-Object -Last 5' -ForegroundColor Gray
Write-Host ""
