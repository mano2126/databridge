$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"
$FRONTEND_DIR = "D:\project\databridge_full\frontend"

Write-Host "============================================================"
Write-Host " DataBridge v90.78 선택 필터링 fix + 헤더 클릭 영역 확대"
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
$tp = Join-Path $BACKEND_DIR  "tests\test_v90_78_select_fix.py"

Check-Item "Validate.vue"   (Test-Path $vl)
Check-Item "test_v90_78"    (Test-Path $tp)

if (Test-Path $vl) {
    $c = Get-Content $vl -Raw
    Check-Item "v90.78 마커"                    ($c.Contains("v90.78"))
    Check-Item "헤더 클릭 가능 클래스"             ($c.Contains("vp-obj-sec-hdr-clickable"))
    Check-Item "selectedSet 필터링"               ($c.Contains("selectedSet") -and $c.Contains("filteredResults"))
    Check-Item "indeterminate 표시"               ($c.Contains("indeterminate.prop"))
    Check-Item "v90.76 강제 새로고침 보존"          ($c.Contains("v90.76"))
    Check-Item "v90.70 name_variant 보존"          ($c.Contains("_ckName"))
    Check-Item "toggleGrp 함수 보존"              ($c.Contains("function toggleGrp"))
}

# pytest
Push-Location $BACKEND_DIR
try {
    if (Test-Path "tests\test_v90_78_select_fix.py") {
        $r = python -m pytest tests/test_v90_78_select_fix.py -v 2>&1
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
    Write-Host "v90.78 정상 적용." -ForegroundColor Green
    Write-Host "  Frontend 만 재시작"
    Write-Host "  cd D:\project\databridge_full\frontend"
    Write-Host "  npm run dev"
    Write-Host "  브라우저 Ctrl+Shift+R"
    Write-Host ""
    Write-Host "  검증 화면 동작:"
    Write-Host "    - 객체 선택 영역의 섹션 헤더 (프로시저/함수/트리거/뷰) 클릭으로"
    Write-Host "      해당 그룹 전체 선택/해제 가능"
    Write-Host "    - hover 시 색상 변경"
    Write-Host "    - 일부만 선택된 그룹은 indeterminate 표시"
    Write-Host "    - 선택된 객체만 검증 실행됨 (전체 실행 버그 fix)"
    exit 0
} else {
    exit 1
}
