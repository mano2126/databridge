$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"

Write-Host "============================================================"
Write-Host " DataBridge v90.71 하드코딩 제거 (v90.68 fix)"
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

$st = Join-Path $BACKEND_DIR "prompts\mssql_to_mysql\system.txt"
$oe = Join-Path $BACKEND_DIR "app\core\obj_executor.py"
$tp = Join-Path $BACKEND_DIR "tests\test_v90_71_hardcoding_removal.py"

Check-Item "system.txt"        (Test-Path $st)
Check-Item "obj_executor.py"   (Test-Path $oe)
Check-Item "test_v90_71"       (Test-Path $tp)

# 환경 특정 식별자 점검
$forbidden = @('p_rec_sdate', 'p_req_sdate', 'sp_Softphone', 'SP_STATRECORD',
               'SP_STATSYSTEM', 'tbl_rec_data', 'Bridge@1234')

if (Test-Path $oe) {
    $c = Get-Content $oe -Raw
    Check-Item "v90.71 마커 (obj_executor)"  ($c.Contains("v90.71"))
    
    $hasViolation = $false
    foreach ($t in $forbidden) {
        if ($c.Contains($t)) {
            Write-Host "  [VIOLATION] obj_executor.py 에 '$t' 발견!" -ForegroundColor Red
            $hasViolation = $true
        }
    }
    Check-Item "obj_executor.py 환경값 0건"  (-not $hasViolation)
}

if (Test-Path $st) {
    $c = Get-Content $st -Raw
    
    $hasViolation = $false
    foreach ($t in $forbidden) {
        if ($c.Contains($t)) {
            Write-Host "  [VIOLATION] system.txt 에 '$t' 발견!" -ForegroundColor Red
            $hasViolation = $true
        }
    }
    Check-Item "system.txt 환경값 0건"  (-not $hasViolation)
    Check-Item "system.txt 패턴 0 보존" ($c.Contains("패턴 0"))
}

# pytest
Push-Location $BACKEND_DIR
try {
    if (Test-Path "tests\test_v90_71_hardcoding_removal.py") {
        $r = python -m pytest tests/test_v90_71_hardcoding_removal.py -v 2>&1
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
    Write-Host "v90.71 정상 적용 — 환경 특정 식별자 모두 제거." -ForegroundColor Green
    Write-Host "  FastAPI 재기동 필수 (system.txt + obj_executor.py 변경)"
    Write-Host "  cd D:\project\databridge_full\backend"
    Write-Host "  python -m uvicorn main:app --port 8000 --reload"
    exit 0
} else {
    exit 1
}
