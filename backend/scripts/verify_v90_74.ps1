$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"
$FRONTEND_DIR = "D:\project\databridge_full\frontend"

Write-Host "============================================================"
Write-Host " DataBridge v90.74 JobWizard 레이아웃 개선"
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
$tp = Join-Path $BACKEND_DIR  "tests\test_v90_74_jobwizard_layout.py"

Check-Item "JobWizard.vue"   (Test-Path $jw)
Check-Item "test_v90_74"     (Test-Path $tp)

if (Test-Path $jw) {
    $c = Get-Content $jw -Raw
    Check-Item "v90.74 마커"                ($c.Contains("v90.74"))
    Check-Item "테이블 폭 확대 2.4fr"        ($c.Contains("2.4fr 1fr 1fr 1fr"))
    Check-Item "grid-template-areas"         ($c.Contains("grid-template-areas:"))
    Check-Item "트리거/뷰 같은 컬럼"          ($c.Contains('"tbl proc func trig"') -and $c.Contains('"tbl proc func view"'))
    Check-Item "빈 테이블 dim 클래스"         ($c.Contains("obj-row-empty"))
    Check-Item "_rowCountClass 함수"          ($c.Contains("_rowCountClass"))
    Check-Item "is-million / is-thousand"    ($c.Contains("is-million") -and $c.Contains("is-thousand"))
}

# pytest
Push-Location $BACKEND_DIR
try {
    if (Test-Path "tests\test_v90_74_jobwizard_layout.py") {
        $r = python -m pytest tests/test_v90_74_jobwizard_layout.py -v 2>&1
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
    Write-Host "v90.74 정상 적용." -ForegroundColor Green
    Write-Host "  Frontend 만 재시작 (백엔드 변경 없음)"
    Write-Host "  cd D:\project\databridge_full\frontend"
    Write-Host "  npm run dev"
    Write-Host "  브라우저 Ctrl+Shift+R"
    Write-Host ""
    Write-Host "  이관 Job 생성 화면 진입:"
    Write-Host "    - 테이블 박스가 매우 넓게 (이름 잘림 해결)"
    Write-Host "    - 트리거 위, 뷰 아래 (같은 컬럼)"
    Write-Host "    - 행 0개 테이블 흐리게"
    Write-Host "    - 큰 테이블 (M/K) 색상 강조"
    exit 0
} else {
    exit 1
}
