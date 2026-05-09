# v95_p23e 적용 스크립트 (UTF-8 BOM, 2026-05-03)
# 본부장님 21:12 진단 결과 기반 — 모든 흐름 공통 관문 후처리
#
# 진짜 본질: 
#   - AI 새 호출 / KB 캐시 / rule-based 모든 흐름이 거치는 자리
#   - obj_executor.deploy_mysql_object 의 _split_sql_statements 직후
#
# 단일 본질 단일 처방 (단순 매치, 정규식 escape 안전)

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  v95_p23e 적용 — 모든 흐름 공통 관문 후처리" -ForegroundColor Cyan
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

# 단순 .Contains() 매치 (정규식 escape 안전)
if ($content.Contains("v95_p23e")) {
    Write-Host "  ✓ v95_p23e 마커 적용됨" -ForegroundColor Green
} else {
    Write-Host "  ✗ v95_p23e 마커 누락" -ForegroundColor Red
    exit 1
}

if ($content.Contains("[v95_p23e] post-fix applied")) {
    Write-Host "  ✓ 후처리 로깅 적용됨" -ForegroundColor Green
}

if ($content.Contains("모든 흐름 공통 관문 후처리")) {
    Write-Host "  ✓ 본질 처방 자리 (deploy_mysql_object) 확정" -ForegroundColor Green
}

Write-Host ""
Write-Host "[4/4] 백엔드 시작..." -ForegroundColor Yellow
Push-Location "$ProjectRoot\backend"
Start-Process -FilePath ".\run_backend.bat" -WindowStyle Normal
Pop-Location
Start-Sleep -Seconds 8

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✅ v95_p23e 적용 완료" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "검증 절차:" -ForegroundColor Yellow
Write-Host "  ① UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  ② DB 초기화 (선택):" -ForegroundColor White
Write-Host "     docker exec db_mysql mysql -u root -pbridge1234 -e ""DROP DATABASE IF EXISTS aw_target; CREATE DATABASE aw_target CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci""" -ForegroundColor Gray
Write-Host "  ③ 새 Job → 전체 이관" -ForegroundColor White
Write-Host ""
Write-Host "기대 결과:" -ForegroundColor Cyan
Write-Host "  - FUNC 3건 (CASE p_Status;) 0건" -ForegroundColor White
Write-Host "  - SP 2건 (CALL/COMMIT 다음 ;) 0건" -ForegroundColor White
Write-Host "  - [v95_p23e] post-fix applied 로그 5건 출현" -ForegroundColor White
Write-Host ""
Write-Host "검증 명령:" -ForegroundColor Cyan
Write-Host '  Get-Content D:\project\databridge_full\backend\logs\databridge_backend.log -Tail 5000 | Select-String "v95_p23e" | Select-Object -Last 10' -ForegroundColor Gray
Write-Host ""
