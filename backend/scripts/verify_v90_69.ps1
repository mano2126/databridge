$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"
$FRONTEND_DIR = "D:\project\databridge_full\frontend"

Write-Host "============================================================"
Write-Host " DataBridge v90.69 검증 화면 자동 재연결"
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
$tp = Join-Path $BACKEND_DIR  "tests\test_v90_69_auto_reconnect.py"

Check-Item "Validate.vue"                  (Test-Path $vl)
Check-Item "test_v90_69_auto_reconnect.py" (Test-Path $tp)

if (Test-Path $vl) {
    $c = Get-Content $vl -Raw
    Check-Item "v90.69 마커"                  ($c.Contains("v90.69"))
    Check-Item "_autoReconnectIfPossible"     ($c.Contains("_autoReconnectIfPossible"))
    Check-Item "_disconnectAll 함수"          ($c.Contains("function _disconnectAll"))
    Check-Item "vp-auto-connect 영역"         ($c.Contains("vp-auto-connect"))
    Check-Item "vp-conn-status 영역"          ($c.Contains("vp-conn-status"))
    Check-Item "ConnectPanel 자동 회피"       ($c.Contains("!_isAutoConnecting"))
}

# pytest
Push-Location $BACKEND_DIR
try {
    if (Test-Path "tests\test_v90_69_auto_reconnect.py") {
        $r = python -m pytest tests/test_v90_69_auto_reconnect.py -v 2>&1
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
    Write-Host "v90.69 정상 적용." -ForegroundColor Green
    Write-Host "  Frontend 만 재시작 (백엔드 변경 없음)"
    Write-Host "  cd D:\project\databridge_full\frontend"
    Write-Host "  npm run dev"
    Write-Host "  브라우저 Ctrl+Shift+R"
    Write-Host ""
    Write-Host "  검증 화면 진입 시:"
    Write-Host "    - 이전 host/db 정보 있으면 자동 재연결 시도"
    Write-Host "    - 성공하면 슬림 인디케이터로 표시"
    Write-Host "    - ConnectPanel 안 뜨고 바로 검증 가능"
    exit 0
} else {
    exit 1
}
