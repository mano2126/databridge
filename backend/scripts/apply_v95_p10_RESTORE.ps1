# v95_p10_RESTORE 적용 스크립트 (UTF-8 BOM 필수)
# 사고 복구 — v95_p11이 v95_p10 schema.py를 덮어쓴 회귀 fix
# v95_p10 (View TEMPTABLE 우회) + v95_p11 (_mysql_tables schema_name="") 통합본

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host "=== v95_p10_RESTORE 적용 시작 ===" -ForegroundColor Cyan
Write-Host ""

# 1. 백엔드 정지
Write-Host "[1/6] 백엔드 정지..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3

# 2. __pycache__ 강제 정리 (전체 트리)
Write-Host "[2/6] __pycache__ 강제 정리 (전체 트리)..." -ForegroundColor Yellow
Get-ChildItem -Path "$ProjectRoot\backend" -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue
    Write-Host "  ✗ $($_.FullName)" -ForegroundColor DarkGray
}

# 3. schema.py 적용 검증 (강력하게)
Write-Host "[3/6] schema.py 패치 적용 검증..." -ForegroundColor Yellow
$markers = @{
    "v95_p10"                       = "View TEMPTABLE 우회 처방"
    "WHERE 1=0"                     = "1차 zero-row 트릭"
    "information_schema.COLUMNS"    = "2차 fallback"
    "MAX_EXECUTION_TIME"            = "안전장치"
    "v95_p11"                       = "MySQL schema_name 회귀 fix"
}
$content = Get-Content "$ProjectRoot\backend\app\api\routes\schema.py" -Raw
$missing = @()
foreach ($m in $markers.GetEnumerator()) {
    if ($content -match [regex]::Escape($m.Key)) {
        Write-Host "  ✓ $($m.Value)" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $($m.Value) 누락: '$($m.Key)'" -ForegroundColor Red
        $missing += $m.Key
    }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "❌ 패치 적용 실패. 누락 마커: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "Expand-Archive 가 정상적으로 풀리지 않았거나 다른 ZIP이 덮어썼습니다." -ForegroundColor Red
    Write-Host "→ ZIP 다시 풀고 이 스크립트 재실행하세요." -ForegroundColor Yellow
    exit 1
}

# 4. Docker 컨테이너 재시작 (좀비 정리)
Write-Host "[4/6] DB 컨테이너 재시작 (좀비 정리)..." -ForegroundColor Yellow
docker restart db_mssql 2>&1 | Out-Null
docker restart db_mysql 2>&1 | Out-Null
Start-Sleep -Seconds 15
Write-Host "  ✓ db_mssql, db_mysql 재시작 완료" -ForegroundColor Green

# 5. 백엔드 시작
Write-Host "[5/6] 백엔드 시작..." -ForegroundColor Yellow
Push-Location "$ProjectRoot\backend"
Start-Process -FilePath ".\run_backend.bat" -WindowStyle Normal
Pop-Location
Start-Sleep -Seconds 8

# 6. 적용 후 자동 검증 (본부장님 요청 — 패치 후 검증 의무화)
Write-Host "[6/6] 적용 후 자동 검증..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  검증 명령 1: 백엔드 health check" -ForegroundColor Cyan
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
    Write-Host "  ✓ 백엔드 응답: $($health | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Host "  ⚠ 백엔드 응답 없음 — 시작 중일 수 있습니다 ($_)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  검증 명령 2: View 테스트 (v95_p10 처방 작동 확인)" -ForegroundColor Cyan
Write-Host "  → UI Ctrl+Shift+R 후 /validate 화면에서 41개 일괄 검증 실행" -ForegroundColor White
Write-Host "  → 백엔드 로그에 [v95_p10] 키워드 나타나야 정상" -ForegroundColor White
Write-Host ""
Write-Host "  검증 후 다음 명령으로 결과 확인:" -ForegroundColor Cyan
Write-Host '  Get-Content D:\project\databridge_full\backend\logs\databridge_backend.log -Tail 200 | Select-String "v95_p10" | Select-Object -Last 10' -ForegroundColor White
Write-Host ""
Write-Host "  기대 결과:" -ForegroundColor Cyan
Write-Host "  [v95_p10] customer_v_customer_360: WHERE 1=0 성공 — TEMPTABLE 우회" -ForegroundColor White
Write-Host "  [v95_p10] ref_v_branch_performance: WHERE 1=0 성공 — TEMPTABLE 우회" -ForegroundColor White
Write-Host "  ... (4개 위험 View 모두)" -ForegroundColor White
Write-Host ""
Write-Host "=== v95_p10_RESTORE 적용 완료 ===" -ForegroundColor Cyan
