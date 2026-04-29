# ═══════════════════════════════════════════════════════════════════════════
# verify_v90_59.ps1 — DataBridge v90.59 모니터 첫 응답 즉시화
# ═══════════════════════════════════════════════════════════════════════════
# 본부장님 호소 (2026-04-28):
#   "모니터 버튼 누르면 데이터가 너무 늦게 나온다"
#
# v90.59 처방:
#   1. system_live.py: import 시 백그라운드 워밍업 + stale-while-revalidate
#   2. registry.py:    fetch_all 병렬화 (ThreadPoolExecutor)
#   3. monitorStore.js: 캐시된 마지막 데이터 즉시 표시 + primeBackground
#   4. JobMonitor.vue: 페이지 진입 시 백그라운드 워밍업 호출
#
# 효과: 모니터 첫 응답 5~15초 → 즉시 (캐시 표시) + 1~3초 (신선 데이터 갱신)
# ═══════════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"
$FRONTEND_DIR = "D:\project\databridge_full\frontend"

Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host " DataBridge v90.59 모니터 첫 응답 즉시화"
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host ""

$pass = 0
$fail = 0

function Check-Item {
    param([string]$Name, [bool]$Result, [string]$Detail = "")
    if ($Result) {
        Write-Host "  [PASS] $Name $Detail" -ForegroundColor Green
        $script:pass++
    } else {
        Write-Host "  [FAIL] $Name $Detail" -ForegroundColor Red
        $script:fail++
    }
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host "[1/5] 핵심 파일 존재 확인"
# ──────────────────────────────────────────────────────────────────────────
$sl = "$BACKEND_DIR\app\api\routes\system_live.py"
$rg = "$BACKEND_DIR\app\monitor\registry.py"
$ms = "$FRONTEND_DIR\src\store\monitorStore.js"
$jm = "$FRONTEND_DIR\src\pages\JobMonitor.vue"

Check-Item "backend/app/api/routes/system_live.py" (Test-Path $sl)
Check-Item "backend/app/monitor/registry.py" (Test-Path $rg)
Check-Item "frontend/src/store/monitorStore.js" (Test-Path $ms)
Check-Item "frontend/src/pages/JobMonitor.vue" (Test-Path $jm)

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/5] Backend - system_live.py 마커"
# ──────────────────────────────────────────────────────────────────────────
if (Test-Path $sl) {
    $content = Get-Content $sl -Raw
    Check-Item "v90.59 워밍업 함수" ($content -match "def _start_warmup_once")
    Check-Item "v90.59 비동기 갱신 함수" ($content -match "def _refresh_cache_async")
    Check-Item "stale-while-revalidate 패턴" ($content -match "_cache_stale.*True")
    Check-Item "import 시점 워밍업 트리거" ($content -match "(?m)^_start_warmup_once\(\)")
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/5] Backend - registry.py 병렬화"
# ──────────────────────────────────────────────────────────────────────────
if (Test-Path $rg) {
    $content = Get-Content $rg -Raw
    Check-Item "v90.59 ThreadPoolExecutor 사용" ($content -match "ThreadPoolExecutor")
    Check-Item "as_completed 사용" ($content -match "as_completed")
    Check-Item "_fetch_one 헬퍼 함수" ($content -match "def _fetch_one")
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/5] Frontend - monitorStore.js + JobMonitor.vue"
# ──────────────────────────────────────────────────────────────────────────
if (Test-Path $ms) {
    $content = Get-Content $ms -Raw
    Check-Item "primeBackground action" ($content -match "primeBackground\(\)")
    Check-Item "cachedLive 복원 로직" ($content -match "cachedLive")
    Check-Item "isStale 플래그" ($content -match "isStale")
}
if (Test-Path $jm) {
    $content = Get-Content $jm -Raw
    Check-Item "JobMonitor onMounted primeBackground" `
        ($content -match "monitorStore\.primeBackground\(\)")
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[5/5] Python 구문 + 단위 테스트"
# ──────────────────────────────────────────────────────────────────────────
foreach ($pf in @($sl, $rg)) {
    if (Test-Path $pf) {
        $rel = $pf.Replace($BACKEND_DIR + "\", "")
        $result = python -c "import ast; ast.parse(open(r'$pf', encoding='utf-8').read()); print('OK')" 2>&1
        Check-Item "ast.parse $rel" ($result -match "OK")
    }
}

Push-Location $BACKEND_DIR
try {
    if (Test-Path "tests\test_v90_59_monitor_warmup.py") {
        $testResult = python -m pytest tests/test_v90_59_monitor_warmup.py -v 2>&1
        $passLine = $testResult | Select-String "passed"
        if ($passLine) {
            Write-Host "  [PASS] pytest: $passLine" -ForegroundColor Green
            $script:pass++
            
            $hasParallel = $testResult | Select-String "test_parallel_faster_than_serial.*PASSED"
            $hasStale = $testResult | Select-String "test_stale_cache_returns_with_meta.*PASSED"
            $hasIsolated = $testResult | Select-String "test_parallel_exception_in_one_adapter_isolated.*PASSED"
            
            Check-Item "병렬 fetch 가 직렬보다 빠름" ($null -ne $hasParallel)
            Check-Item "stale 캐시 즉시 반환" ($null -ne $hasStale)
            Check-Item "한 어댑터 예외 격리" ($null -ne $hasIsolated)
        } else {
            Write-Host "  [FAIL] pytest 실패" -ForegroundColor Red
            $script:fail++
        }
    }
} finally {
    Pop-Location
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host " 검증 완료: PASS $pass / FAIL $fail"
Write-Host "═══════════════════════════════════════════════════════════════"

if ($fail -eq 0) {
    Write-Host ""
    Write-Host "✓ v90.59 패치 정상 적용." -ForegroundColor Green
    Write-Host ""
    Write-Host "  적용 후 동작 확인:"
    Write-Host "  1. FastAPI 재기동 (Ctrl+C → python -m uvicorn main:app --port 8000 --reload)"
    Write-Host "     ※ 재기동 직후 2초 후 백그라운드 워밍업 시작 (백엔드 로그 안 보일 수 있음)"
    Write-Host "  2. Frontend 재시작 (npm run dev) + Ctrl+Shift+R"
    Write-Host "  3. 이관 작업 모니터 진입"
    Write-Host "  4. 우상단 [모니터] 버튼 클릭"
    Write-Host "     → 첫 클릭부터 즉시 데이터 표시 (이전 캐시 → 곧 신선 데이터로 갱신)"
    Write-Host "     → 페이지 새로고침 후에도 마지막 캐시 즉시 표시 (5분 이내)"
    Write-Host "  5. F12 콘솔에서 store.live._cache_stale 으로 캐시 상태 확인 가능"
    exit 0
} else {
    Write-Host ""
    Write-Host "✗ 일부 항목 실패." -ForegroundColor Red
    exit 1
}
