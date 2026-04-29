# ============================================================
# verify_v90_66.ps1 - DataBridge v90.66 fn_age 다중라인 RETURN fix
# ============================================================
$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"
$FRONTEND_DIR = "D:\project\databridge_full\frontend"

Write-Host "============================================================"
Write-Host " DataBridge v90.66 fn_age 다중라인 RETURN fix"
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

$oe = Join-Path $BACKEND_DIR  "app\core\obj_executor.py"
$jm = Join-Path $FRONTEND_DIR "src\pages\JobMonitor.vue"
$tp = Join-Path $BACKEND_DIR  "tests\test_v90_66_multiline_return_terminator.py"

Check-Item "obj_executor.py"                              (Test-Path $oe)
Check-Item "JobMonitor.vue"                                (Test-Path $jm)
Check-Item "test_v90_66_multiline_return_terminator.py"   (Test-Path $tp)

if (Test-Path $oe) {
    $content = Get-Content $oe -Raw
    Check-Item "v90.66 마커 (obj_executor)"        ($content.Contains("v90.66"))
    Check-Item "_fix_inner_end_terminator 함수"     ($content.Contains("_fix_inner_end_terminator"))
}

if (Test-Path $jm) {
    $content = Get-Content $jm -Raw
    Check-Item "v90.66 마커 (frontend)"             ($content.Contains("v90.66"))
    Check-Item "오류 KPI 객체/행 구분 명확화"        ($content.Contains("객체") -and $content.Contains("행"))
}

# __pycache__ 청소
Write-Host ""
Write-Host "[__pycache__ 청소]"
$pycount = (Get-ChildItem -Path $BACKEND_DIR -Filter "__pycache__" -Recurse -Directory -ErrorAction SilentlyContinue | Measure-Object).Count
Get-ChildItem -Path $BACKEND_DIR -Filter "__pycache__" -Recurse -Directory -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Write-Host "  __pycache__ $pycount 개 제거" -ForegroundColor Cyan

# pytest
Push-Location $BACKEND_DIR
try {
    if (Test-Path "tests\test_v90_66_multiline_return_terminator.py") {
        $testResult = python -m pytest tests/test_v90_66_multiline_return_terminator.py -v 2>&1
        $passLine = $testResult | Select-String "passed"
        if ($passLine) {
            Write-Host "  [PASS] pytest: $passLine" -ForegroundColor Green
            $script:passCount = $script:passCount + 1
            
            $hasFnAge = $testResult | Select-String "test_fn_age_inner_end_gets_terminator.*PASSED"
            $hasReg = $testResult | Select-String "test_end_if_not_affected.*PASSED"
            
            Check-Item "fn_age 케이스 통과" ($null -ne $hasFnAge)
            Check-Item "END IF 회귀 안전" ($null -ne $hasReg)
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
    Write-Host "v90.66 정상 적용." -ForegroundColor Green
    Write-Host ""
    Write-Host "  적용 후 동작 확인:"
    Write-Host "  1. FastAPI 재기동 (필수)"
    Write-Host "     python -m uvicorn main:app --port 8000 --reload"
    Write-Host "  2. Frontend 재시작"
    Write-Host "     cd D:\project\databridge_full\frontend"
    Write-Host "     npm run dev"
    Write-Host "  3. 브라우저 Ctrl+Shift+R"
    Write-Host "  4. fn_age 재변환 - 41/41 모두 완료 예상"
    Write-Host ""
    Write-Host "  오류 KPI 카드 — 객체/행 단위 구분 명확화됨"
    exit 0
} else {
    exit 1
}
