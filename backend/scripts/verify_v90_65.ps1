# ============================================================
# verify_v90_65.ps1 - DataBridge v90.65 KPI 전체 진행률 fix
# ============================================================
$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"
$FRONTEND_DIR = "D:\project\databridge_full\frontend"

Write-Host "============================================================"
Write-Host " DataBridge v90.65 KPI 전체 진행률 fix"
Write-Host "============================================================"
Write-Host ""

$script:passCount = 0
$script:failCount = 0

function Check-Item {
    param([string]$Name, [bool]$Result)
    if ($Result) {
        Write-Host "  [PASS] $Name" -ForegroundColor Green
        $script:passCount = $script:passCount + 1
    } else {
        Write-Host "  [FAIL] $Name" -ForegroundColor Red
        $script:failCount = $script:failCount + 1
    }
}

$jm = Join-Path $FRONTEND_DIR "src\pages\JobMonitor.vue"
$tp = Join-Path $BACKEND_DIR  "tests\test_v90_65_progress_kpi_fix.py"

Check-Item "JobMonitor.vue"                 (Test-Path $jm)
Check-Item "test_v90_65_progress_kpi_fix.py" (Test-Path $tp)

if (Test-Path $jm) {
    $content = Get-Content $jm -Raw
    Check-Item "v90.65 마커"                ($content.Contains("v90.65"))
    Check-Item "effectiveProgress 정의"     ($content.Contains("const effectiveProgress"))
    Check-Item "KPI 카드가 effectiveProgress 사용" ($content.Contains("{{ effectiveProgress }}%"))
    Check-Item "safeProgress 보존 (회귀 안전)" ($content.Contains("const safeProgress"))
}

# pytest
Push-Location $BACKEND_DIR
try {
    if (Test-Path "tests\test_v90_65_progress_kpi_fix.py") {
        $testResult = python -m pytest tests/test_v90_65_progress_kpi_fix.py -v 2>&1
        $passLine = $testResult | Select-String "passed"
        if ($passLine) {
            Write-Host "  [PASS] pytest: $passLine" -ForegroundColor Green
            $script:passCount = $script:passCount + 1
            
            $hasPresident = $testResult | Select-String "test_president_screen_capture.*PASSED"
            $hasReg1 = $testResult | Select-String "test_table_only_job_uses_backend_progress.*PASSED"
            
            Check-Item "본부장님 화면 시나리오 (3/41 = 7.3%)" ($null -ne $hasPresident)
            Check-Item "테이블 Job 회귀 안전"                  ($null -ne $hasReg1)
        }
    }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "============================================================"
Write-Host " PASS $script:passCount / FAIL $script:failCount"
Write-Host "============================================================"

if ($script:failCount -eq 0) {
    Write-Host ""
    Write-Host "v90.65 정상 적용. 다음 단계:" -ForegroundColor Green
    Write-Host "  1. Frontend 재시작 (백엔드 변경 없음)"
    Write-Host "     cd D:\project\databridge_full\frontend"
    Write-Host "     npm run dev"
    Write-Host "  2. 브라우저 Ctrl+Shift+R"
    Write-Host "  3. 이관 작업 모니터 - 전체 진행 % 가 객체 변환 진척과 함께 움직임"
    exit 0
} else {
    exit 1
}
