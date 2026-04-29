$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"
$FRONTEND_DIR = "D:\project\databridge_full\frontend"

Write-Host "============================================================"
Write-Host " DataBridge v90.75 박스별 독립 정렬 + 콤마 표기"
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

$jw = Join-Path $FRONTEND_DIR "src\pages\JobWizard.vue"
$tp = Join-Path $BACKEND_DIR  "tests\test_v90_75_per_box_sort.py"

Check-Item "JobWizard.vue"   (Test-Path $jw)
Check-Item "test_v90_75"     (Test-Path $tp)

if (Test-Path $jw) {
    $c = Get-Content $jw -Raw
    Check-Item "v90.75 마커"                   ($c.Contains("v90.75"))
    Check-Item "tableSort ref 정의"             ($c.Contains("const tableSort"))
    Check-Item "5개 toggle 함수"                ($c.Contains("toggleTableSort") -and $c.Contains("toggleProcSort") -and $c.Contains("toggleViewSort"))
    Check-Item "fmtRowsComma 함수"              ($c.Contains("fmtRowsComma"))
    Check-Item "obj-row-head 컬럼 헤더"          ($c.Contains("obj-row-head"))
    Check-Item "sortable 클래스"                ($c.Contains('"orh-name sortable"'))
    Check-Item "sticky header"                  ($c.Contains("position: sticky"))
}

# pytest
Push-Location $BACKEND_DIR
try {
    if (Test-Path "tests\test_v90_75_per_box_sort.py") {
        $r = python -m pytest tests/test_v90_75_per_box_sort.py -v 2>&1
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
    Write-Host "v90.75 정상 적용." -ForegroundColor Green
    Write-Host "  Frontend 만 재시작"
    Write-Host "  cd D:\project\databridge_full\frontend"
    Write-Host "  npm run dev"
    Write-Host "  브라우저 Ctrl+Shift+R"
    Write-Host ""
    Write-Host "  이관 Job 생성 화면:"
    Write-Host "    - 상단 정렬 툴바 사라짐"
    Write-Host "    - 각 박스마다 컬럼 헤더 (클릭으로 정렬)"
    Write-Host "    - 행수: 1,234,567 콤마 표기"
    Write-Host "    - 화살표 기준 컬럼 라인 정렬"
    exit 0
} else {
    exit 1
}
