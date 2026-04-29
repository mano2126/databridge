# verify_v90_67.ps1 — DataBridge v90.67 AI 재이관 라벨 + 상태 카드 분리
$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"
$FRONTEND_DIR = "D:\project\databridge_full\frontend"

Write-Host "============================================================"
Write-Host " DataBridge v90.67 AI 재이관 라벨 + 상태 카드 분리"
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

$me = Join-Path $BACKEND_DIR  "app\engine\migration_engine.py"
$sc = Join-Path $BACKEND_DIR  "app\api\routes\schema.py"
$jm = Join-Path $FRONTEND_DIR "src\pages\JobMonitor.vue"
$tp = Join-Path $BACKEND_DIR  "tests\test_v90_67_ai_remig_label.py"

Check-Item "migration_engine.py"        (Test-Path $me)
Check-Item "schema.py"                   (Test-Path $sc)
Check-Item "JobMonitor.vue"              (Test-Path $jm)
Check-Item "test_v90_67_ai_remig_label.py" (Test-Path $tp)

if (Test-Path $me) {
    $c = Get-Content $me -Raw
    Check-Item "engine v90.67 마커"          ($c.Contains("v90.67"))
    Check-Item "had_error 필드"               ($c.Contains('"had_error"'))
    Check-Item "attempts 필드"                ($c.Contains('"attempts"'))
}
if (Test-Path $sc) {
    $c = Get-Content $sc -Raw
    Check-Item "schema v90.67 마커"           ($c.Contains("v90.67"))
    Check-Item "via_ai_remig=True"            ($c.Contains('"via_ai_remig": True'))
}
if (Test-Path $jm) {
    $c = Get-Content $jm -Raw
    Check-Item "JM v90.67 마커"               ($c.Contains("v90.67"))
    Check-Item "AI 재이관 성공 라벨"          ($c.Contains("AI 재이관 성공"))
    Check-Item "재시도 성공 라벨"             ($c.Contains("재시도 성공"))
    Check-Item "stat-pill.via-ai 스타일"      ($c.Contains(".stat-pill.done.via-ai"))
    Check-Item "phase-counts 영역"            ($c.Contains("phase-counts"))
    Check-Item "kpi-grid 비율 조정"           ($c.Contains("1.4fr 1.6fr 0.85fr"))
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
    if (Test-Path "tests\test_v90_67_ai_remig_label.py") {
        $r = python -m pytest tests/test_v90_67_ai_remig_label.py -v 2>&1
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
    Write-Host "v90.67 정상 적용." -ForegroundColor Green
    Write-Host "  1. FastAPI 재기동 (필수)"
    Write-Host "  2. Frontend 재시작 + Ctrl+Shift+R"
    Write-Host "  3. 다음 이관에서 라벨 + 상태 카드 변경 확인"
    exit 0
} else {
    exit 1
}
