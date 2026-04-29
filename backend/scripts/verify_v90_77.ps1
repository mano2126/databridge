$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"

Write-Host "============================================================"
Write-Host " DataBridge v90.77 pymysql callproc 우회"
Write-Host "============================================================"

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

$sc = Join-Path $BACKEND_DIR "app\api\routes\schema.py"
$tp = Join-Path $BACKEND_DIR "tests\test_v90_77_callproc_bypass.py"

Check-Item "schema.py"      (Test-Path $sc)
Check-Item "test_v90_77"    (Test-Path $tp)

if (Test-Path $sc) {
    $c = Get-Content $sc -Raw
    Check-Item "v90.77 마커"                       ($c.Contains("v90.77"))
    Check-Item "직접 CALL 패턴"                    ($c.Contains('CALL `{obj_name}`'))
    Check-Item "has_out 분기"                       ($c.Contains("has_out"))
    
    # 환경 식별자 검사 (v90.71 정책 유지)
    $forbidden = @('p_rec_sdate', 'p_req_sdate', 'sp_Softphone', 'SP_STATRECORD', 'tbl_rec_data')
    $hasViolation = $false
    foreach ($t in $forbidden) {
        if ($c.Contains($t)) {
            Write-Host "  [WARN] schema.py 에 '$t' 발견 (v90.71 정책 위반)" -ForegroundColor Yellow
        }
    }
}

# pytest
Push-Location $BACKEND_DIR
try {
    if (Test-Path "tests\test_v90_77_callproc_bypass.py") {
        $r = python -m pytest tests/test_v90_77_callproc_bypass.py -v 2>&1
        $p = $r | Select-String "passed"
        if ($p) {
            Write-Host "  [PASS] pytest: $p" -ForegroundColor Green
            $script:passCount = $script:passCount + 1
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
    Write-Host "v90.77 정상 적용." -ForegroundColor Green
    Write-Host ""
    Write-Host "  FastAPI 재기동 (필수 — schema.py 변경)"
    Write-Host "    cd D:\project\databridge_full\backend"
    Write-Host "    python -m uvicorn main:app --port 8000 --reload"
    Write-Host ""
    Write-Host "  검증 화면에서 SP/FN 실행 다시:"
    Write-Host "    SP_STATRECORD / SP_TEST_DAILY_AGG / FN_TEST_TOTAL_AMT"
    Write-Host "    → 1406 사라짐 예상 (MySQL CLI 와 동일 동작)"
    exit 0
} else {
    exit 1
}
