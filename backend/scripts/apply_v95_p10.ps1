# v95_p10 적용 스크립트 (UTF-8 BOM 필수)
# View timeout 본질 처방 — TEMPTABLE 알고리즘 우회
#   1차: WHERE 1=0 (zero-row 트릭)
#   2차: information_schema.COLUMNS (메타 fallback)

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host "=== v95_p10 적용 시작 ===" -ForegroundColor Cyan
Write-Host ""

# 1. 백엔드 정지
Write-Host "[1/4] 백엔드 프로세스 정지..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3

# 2. __pycache__ 정리
Write-Host "[2/4] __pycache__ 정리..." -ForegroundColor Yellow
Remove-Item -Recurse -Force "$ProjectRoot\backend\app\api\routes\__pycache__" -ErrorAction SilentlyContinue

# 3. 적용 검증
Write-Host "[3/4] 패치 적용 검증..." -ForegroundColor Yellow
$check = Select-String -Path "$ProjectRoot\backend\app\api\routes\schema.py" -Pattern "v95_p10" -SimpleMatch -Quiet
if ($check) {
    Write-Host "  ✓ schema.py (TEMPTABLE 우회)" -ForegroundColor Green
} else {
    Write-Host "  ✗ schema.py 적용 실패 — Expand-Archive 재실행 필요" -ForegroundColor Red
    exit 1
}

# 검증: 핵심 마커 모두 존재
$markers = @("WHERE 1=0", "information_schema.COLUMNS", "MAX_EXECUTION_TIME", "safe_method")
$schemaContent = Get-Content "$ProjectRoot\backend\app\api\routes\schema.py" -Raw
foreach ($m in $markers) {
    if ($schemaContent -match [regex]::Escape($m)) {
        Write-Host "  ✓ 마커: $m" -ForegroundColor Green
    } else {
        Write-Host "  ✗ 마커 누락: $m" -ForegroundColor Red
    }
}

# 4. 안내
Write-Host ""
Write-Host "[4/4] 다음 단계:" -ForegroundColor Yellow
Write-Host "  ① 백엔드 재시작: cd $ProjectRoot\backend; .\run_backend.bat" -ForegroundColor White
Write-Host "  ② UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  ③ 41개 일괄 검증 재실행" -ForegroundColor White
Write-Host "  ④ 4개 위험 View 즉시 응답 확인:" -ForegroundColor White
Write-Host "     - customer_v_customer_360 (0~50ms 기대)" -ForegroundColor White
Write-Host "     - ref_v_branch_performance (0~50ms 기대)" -ForegroundColor White
Write-Host "     - ref_v_employee_workload (0~50ms 기대)" -ForegroundColor White
Write-Host "     - settlement_v_recent_trx (0~50ms 기대)" -ForegroundColor White
Write-Host "  ⑤ 백엔드 로그에서 'v95_p10' 키워드 필터:" -ForegroundColor White
Write-Host "     - 정상: '[v95_p10] xxx: WHERE 1=0 성공 — TEMPTABLE 우회'" -ForegroundColor White
Write-Host "     - fallback: '[v95_p10] xxx: information_schema fallback 성공'" -ForegroundColor White
Write-Host ""
Write-Host "=== v95_p10 적용 완료 ===" -ForegroundColor Cyan
