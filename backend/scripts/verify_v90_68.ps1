$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"
$FRONTEND_DIR = "D:\project\databridge_full\frontend"

Write-Host "============================================================"
Write-Host " DataBridge v90.68 system.txt + 1406/1270/1305 자동 hint"
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

$st = Join-Path $BACKEND_DIR  "prompts\mssql_to_mysql\system.txt"
$oe = Join-Path $BACKEND_DIR  "app\core\obj_executor.py"
$vl = Join-Path $FRONTEND_DIR "src\pages\Validate.vue"
$tp = Join-Path $BACKEND_DIR  "tests\test_v90_68_varchar_length_kb.py"

Check-Item "system.txt"     (Test-Path $st)
Check-Item "obj_executor.py"(Test-Path $oe)
Check-Item "Validate.vue"   (Test-Path $vl)
Check-Item "test_v90_68"    (Test-Path $tp)

if (Test-Path $st) {
    $c = Get-Content $st -Raw
    Check-Item "v90.68 마커 (system.txt)"  ($c.Contains("v90.68"))
    Check-Item "패턴 0 (VARCHAR 길이)"      ($c.Contains("패턴 0"))
    Check-Item "★★★★★ 강조"                ($c.Contains("★★★★★"))
    Check-Item "10대 헤더 변경"             ($c.Contains("10대"))
}

if (Test-Path $oe) {
    $c = Get-Content $oe -Raw
    Check-Item "v90.68 마커 (obj_executor)"     ($c.Contains("v90.68"))
    Check-Item "1406 자동 hint"                  ($c.Contains("1406 오류 강제 fix 룰"))
    Check-Item "1270 자동 hint"                  ($c.Contains("1270 오류 강제 fix 룰"))
    Check-Item "1305 자동 hint"                  ($c.Contains("1305 오류 강제 fix 룰"))
}

if (Test-Path $vl) {
    $c = Get-Content $vl -Raw
    Check-Item "v90.68 마커 (Validate.vue)"     ($c.Contains("v90.68"))
    Check-Item "targetMaxLength 추가"            ($c.Contains("targetMaxLength"))
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
    if (Test-Path "tests\test_v90_68_varchar_length_kb.py") {
        $r = python -m pytest tests/test_v90_68_varchar_length_kb.py -v 2>&1
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
    Write-Host "v90.68 정상 적용." -ForegroundColor Green
    Write-Host "  1. FastAPI 재기동 (필수)"
    Write-Host "  2. Frontend 재시작 + Ctrl+Shift+R"
    Write-Host "  3. 1406 오류난 SP 들 (SP_STATRECORD, SP_STATSYSTEM) AI 재이관 시도"
    Write-Host "     → 자동 hint 가 AI 에게 'VARCHAR 길이 줄이지 말것' 강조"
    exit 0
} else {
    exit 1
}
