$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"
$FRONTEND_DIR = "D:\project\databridge_full\frontend"

Write-Host "============================================================"
Write-Host " DataBridge v90.70 검증 - 객체명 매칭 fix (name_variant 라우팅)"
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
$tp = Join-Path $BACKEND_DIR  "tests\test_v90_70_name_variant_routing.py"

Check-Item "Validate.vue"      (Test-Path $vl)
Check-Item "test_v90_70"       (Test-Path $tp)

if (Test-Path $vl) {
    $c = Get-Content $vl -Raw
    Check-Item "v90.70 마커"                    ($c.Contains("v90.70"))
    Check-Item "_ckName 변수 도입"              ($c.Contains("_ckName"))
    Check-Item "name_variant 우선 처리"         ($c.Contains("r.name_variant : name"))
    Check-Item "PROCEDURE _ckName 사용"         ($c.Contains("obj_name: _ckName"))
    Check-Item "runObjTestWithParams 타겟 fix"  ($c.Contains("r.name_variant || r.name"))
}

# pytest
Push-Location $BACKEND_DIR
try {
    if (Test-Path "tests\test_v90_70_name_variant_routing.py") {
        $r = python -m pytest tests/test_v90_70_name_variant_routing.py -v 2>&1
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
    Write-Host "v90.70 정상 적용." -ForegroundColor Green
    Write-Host "  Frontend 만 재시작 (백엔드 변경 없음)"
    Write-Host "  cd D:\project\databridge_full\frontend"
    Write-Host "  npm run dev"
    Write-Host "  브라우저 Ctrl+Shift+R"
    Write-Host ""
    Write-Host "  검증 화면에서 다시 테스트:"
    Write-Host "  - sp_Softphone_UpdateRecord(dbo_sp_Softphone_UpdateRecord) → 타겟 통과 예상"
    Write-Host "  - SP_STATRECORD 의 1406 → AI 재이관 (v90.68 hint) 활용"
    Write-Host "  - SP_STATRECORD 의 소스 42S02 → 본부장님 환경 데이터 (tbl_rec_data 누락)"
    exit 0
} else {
    exit 1
}
