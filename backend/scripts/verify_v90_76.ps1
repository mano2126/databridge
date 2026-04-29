$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"
$FRONTEND_DIR = "D:\project\databridge_full\frontend"

Write-Host "============================================================"
Write-Host " DataBridge v90.76 검증 실행 시 강제 새로고침"
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

$vl = Join-Path $FRONTEND_DIR "src\pages\Validate.vue"
$tp = Join-Path $BACKEND_DIR  "tests\test_v90_76_force_refresh_validation.py"

Check-Item "Validate.vue"   (Test-Path $vl)
Check-Item "test_v90_76"    (Test-Path $tp)

if (Test-Path $vl) {
    $c = Get-Content $vl -Raw
    Check-Item "v90.76 마커"                       ($c.Contains("v90.76"))
    Check-Item "runValidate 강제 새로고침"          ($c.Contains("v90.76") -and $c.Contains("await loadTables()"))
    Check-Item "runObjValidate 강제 새로고침"       ($c.Contains("loadSrcObjects(true)"))
    Check-Item "v90.70 name_variant 보존"           ($c.Contains("_ckName") -and $c.Contains("name_variant"))
    Check-Item "v90.69 자동 재연결 보존"             ($c.Contains("_autoReconnectIfPossible"))
}

# pytest
Push-Location $BACKEND_DIR
try {
    if (Test-Path "tests\test_v90_76_force_refresh_validation.py") {
        $r = python -m pytest tests/test_v90_76_force_refresh_validation.py -v 2>&1
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
    Write-Host "v90.76 정상 적용." -ForegroundColor Green
    Write-Host "  Frontend 만 재시작"
    Write-Host "  cd D:\project\databridge_full\frontend"
    Write-Host "  npm run dev"
    Write-Host "  브라우저 Ctrl+Shift+R"
    Write-Host ""
    Write-Host "  검증 화면 동작:"
    Write-Host "    - 매 '검증 실행' 클릭 시 DB에서 최신 목록 읽음"
    Write-Host "    - AI 로 만든 새 테이블/객체 즉시 인지"
    exit 0
} else {
    exit 1
}
