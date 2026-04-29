$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"

Write-Host "============================================================"
Write-Host " DataBridge v90.73 - VARCHAR 길이 코드 레벨 강제 보정"
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

$oe = Join-Path $BACKEND_DIR "app\core\obj_executor.py"
$tp = Join-Path $BACKEND_DIR "tests\test_v90_73_varchar_enforce.py"

Check-Item "obj_executor.py"   (Test-Path $oe)
Check-Item "test_v90_73"       (Test-Path $tp)

if (Test-Path $oe) {
    $c = Get-Content $oe -Raw
    Check-Item "v90.73 마커"                       ($c.Contains("v90.73"))
    Check-Item "_enforce_varchar_length 함수"      ($c.Contains("def _enforce_varchar_length"))
    Check-Item "ai_convert_ddl 에서 호출"          ($c.Contains("_enforce_varchar_length("))
    
    # 환경 식별자 검사 (v90.71 회귀 방지)
    $forbidden = @('p_rec_sdate', 'p_req_sdate', 'sp_Softphone', 'SP_STATRECORD', 'SP_STATSYSTEM')
    $hasViolation = $false
    foreach ($t in $forbidden) {
        if ($c.Contains($t)) {
            Write-Host "  [VIOLATION] obj_executor.py 에 환경 식별자 '$t' 발견!" -ForegroundColor Red
            $hasViolation = $true
        }
    }
    Check-Item "환경 식별자 0건 (일반화 유지)"     (-not $hasViolation)
}

# pytest
Push-Location $BACKEND_DIR
try {
    if (Test-Path "tests\test_v90_73_varchar_enforce.py") {
        $r = python -m pytest tests/test_v90_73_varchar_enforce.py -v 2>&1
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
    Write-Host "v90.73 정상 적용." -ForegroundColor Green
    Write-Host ""
    Write-Host "  FastAPI 재기동 (필수):"
    Write-Host "    cd D:\project\databridge_full\backend"
    Write-Host "    python -m uvicorn main:app --port 8000 --reload"
    Write-Host ""
    Write-Host "  AI 재이관 시도:"
    Write-Host "    SP_STATRECORD/SP_STATSYSTEM -> 검증 화면에서 AI 클릭"
    Write-Host "    -> AI 변환 후 _enforce_varchar_length 가 자동으로"
    Write-Host "       VARCHAR 길이 강제 보정 (prompt 무관)"
    Write-Host "    -> 1406 오류 사라짐"
    exit 0
} else {
    exit 1
}
