# ============================================================
# verify_v90_62.ps1 - DataBridge v90.62 모니터 폴링 + 라이브 점멸
# ============================================================
$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"
$FRONTEND_DIR = "D:\project\databridge_full\frontend"

Write-Host "============================================================"
Write-Host " DataBridge v90.62 모니터 폴링 + 라이브 점멸"
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

# ------------------------------------------------------------
Write-Host "[1/3] 핵심 파일"
# ------------------------------------------------------------
$ms = Join-Path $FRONTEND_DIR "src\store\monitorStore.js"
$jm = Join-Path $FRONTEND_DIR "src\pages\JobMonitor.vue"
$tp = Join-Path $BACKEND_DIR  "tests\test_v90_62_monitor_polling.py"

Check-Item "monitorStore.js"               (Test-Path $ms)
Check-Item "JobMonitor.vue"                (Test-Path $jm)
Check-Item "test_v90_62_monitor_polling.py" (Test-Path $tp)

# ------------------------------------------------------------
Write-Host ""
Write-Host "[2/3] monitorStore.js v90.62 변경"
# ------------------------------------------------------------
if (Test-Path $ms) {
    $content = Get-Content $ms -Raw
    Check-Item "v90.62 마커"            ($content.Contains("v90.62"))
    Check-Item "startBackgroundPolling" ($content.Contains("startBackgroundPolling"))
    Check-Item "stopBackgroundPolling"  ($content.Contains("stopBackgroundPolling"))
    Check-Item "_bgPolling 플래그"      ($content.Contains("_bgPolling"))
    Check-Item "isPolling getter"       ($content.Contains("isPolling"))
}

# ------------------------------------------------------------
Write-Host ""
Write-Host "[3/3] JobMonitor.vue v90.62 변경 + 단위 테스트"
# ------------------------------------------------------------
if (Test-Path $jm) {
    $content = Get-Content $jm -Raw
    Check-Item "v90.62 마커"                       ($content.Contains("v90.62"))
    Check-Item "onMounted startBackgroundPolling"  ($content.Contains("monitorStore.startBackgroundPolling"))
    Check-Item "onUnmounted stopBackgroundPolling" ($content.Contains("monitorStore.stopBackgroundPolling"))
    Check-Item "monitor-live-dot 엘리먼트"         ($content.Contains("monitor-live-dot"))
    Check-Item "isPolling 조건부 표시"             ($content.Contains('v-if="monitorStore.isPolling"'))
    Check-Item "mon-live-pulse 애니메이션"         ($content.Contains("mon-live-pulse"))
}

# pytest 실행
Push-Location $BACKEND_DIR
try {
    if (Test-Path "tests\test_v90_62_monitor_polling.py") {
        $testResult = python -m pytest tests/test_v90_62_monitor_polling.py -v 2>&1
        $passLine = $testResult | Select-String "passed"
        if ($passLine) {
            Write-Host "  [PASS] pytest: $passLine" -ForegroundColor Green
            $script:passCount = $script:passCount + 1
            
            $hasPresident = $testResult | Select-String "test_president_scenario_now_works.*PASSED"
            $hasIndicator = $testResult | Select-String "test_isPolling_for_live_indicator.*PASSED"
            $hasJmTests   = $testResult | Select-String "test_jm_live_dot_indicator.*PASSED"
            
            Check-Item "본부장님 시나리오 통과"      ($null -ne $hasPresident)
            Check-Item "라이브 인디케이터 동작"      ($null -ne $hasIndicator)
            Check-Item "JM 의 점멸 dot 통합"         ($null -ne $hasJmTests)
        } else {
            Write-Host "  [FAIL] pytest 실행 실패" -ForegroundColor Red
            $script:failCount = $script:failCount + 1
        }
    }
} finally {
    Pop-Location
}

# ------------------------------------------------------------
Write-Host ""
Write-Host "============================================================"
Write-Host " 검증 완료: PASS $script:passCount / FAIL $script:failCount"
Write-Host "============================================================"

if ($script:failCount -eq 0) {
    Write-Host ""
    Write-Host "v90.62 정상 적용. 다음 단계:" -ForegroundColor Green
    Write-Host "  1. Frontend 만 재시작 (백엔드 변경 없음)"
    Write-Host "     cd D:\project\databridge_full\frontend"
    Write-Host "     npm run dev"
    Write-Host "  2. 브라우저 Ctrl+Shift+R"
    Write-Host "  3. 이관 작업 모니터 진입 즉시:"
    Write-Host "     - 모니터 버튼 옆 초록 점이 깜빡임 (라이브 갱신 중)"
    Write-Host "     - LIVE 배너 / 진행률 자동 갱신"
    Write-Host "     - 모니터 패널 안 열어도 동작"
    exit 0
} else {
    Write-Host "일부 항목 실패. FAIL 로그 확인 부탁드립니다." -ForegroundColor Red
    exit 1
}
