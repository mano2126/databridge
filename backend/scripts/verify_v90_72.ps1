$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"
$FRONTEND_DIR = "D:\project\databridge_full\frontend"

Write-Host "============================================================"
Write-Host " DataBridge v90.72 중복 DB 인디케이터 제거"
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

$vl = Join-Path $FRONTEND_DIR "src\pages\Validate.vue"
$tp = Join-Path $BACKEND_DIR  "tests\test_v90_72_remove_duplicate_indicator.py"

Check-Item "Validate.vue"  (Test-Path $vl)
Check-Item "test_v90_72"   (Test-Path $tp)

if (Test-Path $vl) {
    $c = Get-Content $vl -Raw
    Check-Item "v90.72 마커"                      ($c.Contains("v90.72"))
    Check-Item "vp-conn-status template 제거"     (-not $c.Contains('class="vp-conn-status"'))
    Check-Item "vp-conn-dot 제거"                 (-not $c.Contains('class="vp-conn-dot"'))
    Check-Item "vp-conn-disc 제거"                (-not $c.Contains('class="vp-conn-disc"'))
    Check-Item "_disconnectAll dead code 제거"    (-not $c.Contains("function _disconnectAll"))
    Check-Item "_autoReconnectIfPossible 보존"    ($c.Contains("_autoReconnectIfPossible"))
    Check-Item "PageHeader src-db 보존"           ($c.Contains(":src-db=`"connector.source`""))
}

# pytest
Push-Location $BACKEND_DIR
try {
    if (Test-Path "tests\test_v90_72_remove_duplicate_indicator.py") {
        $r = python -m pytest tests/test_v90_72_remove_duplicate_indicator.py -v 2>&1
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
    Write-Host "v90.72 정상 적용 — 중복 인디케이터 제거." -ForegroundColor Green
    Write-Host "  Frontend 만 재시작 (백엔드 변경 없음)"
    Write-Host "  cd D:\project\databridge_full\frontend"
    Write-Host "  npm run dev"
    Write-Host "  브라우저 Ctrl+Shift+R"
    exit 0
} else {
    exit 1
}
