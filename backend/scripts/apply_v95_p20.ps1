# v95_p20 적용 스크립트 (UTF-8 BOM, 2026-05-03)
# 본부장님 본질 처방 — DB 연결 폭발 해소 (운영 환경 위험 해결)
# 3가지 본질 동시:
#   1) 드라이버 모듈 캐시 (db_conn.py)
#   2) connect 폭발 해소 (schema.py: _analyze_warnings)
#   3) 메타 쿼리 1회만 (sys.columns / information_schema 일괄)

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  v95_p20 적용 — DB 연결 폭발 해소 (운영 환경 안정화)" -ForegroundColor Cyan
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
    "$ProjectRoot\backend\app\core\db_conn.py"            = "_cached_mssql_driver"
    "$ProjectRoot\backend\app\api\routes\schema.py"       = "v95_p20"
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
Write-Host "  ✅ v95_p20 적용 완료" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "검증:" -ForegroundColor Yellow
Write-Host "  ① UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  ② Job 위저드 → Step 3 (변환 규칙) 진입" -ForegroundColor White
Write-Host "  ③ 백엔드 로그에서 PYODBC connect 횟수 확인:" -ForegroundColor White
Write-Host '     Get-Content D:\project\databridge_full\backend\logs\databridge_backend.log -Tail 200 | Select-String "PYODBC connect" | Measure-Object | Select-Object -ExpandProperty Count' -ForegroundColor Gray
Write-Host ""
Write-Host "기대:" -ForegroundColor Cyan
Write-Host "  - PYODBC connect 횟수: 수백 회 → 1~2 회 (-99%)" -ForegroundColor White
Write-Host "  - 변환 규칙 화면 진입 시간: 6초 → 0.5초 (12배 빠름)" -ForegroundColor White
Write-Host "  - 운영 환경 connection limit 폭발 위험 해소" -ForegroundColor White
Write-Host ""
