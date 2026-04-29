# ═══════════════════════════════════════════════════════════════════════════
# verify_v90_56.ps1 — DataBridge v90.56 검증 매칭 정공법 fix
# ═══════════════════════════════════════════════════════════════════════════
# 본부장님 직관적 모순 지적:
#   "타겟에 underscore 형태가 분명히 있는데 1건도 매칭 안 되는게 이상하다"
#
# 진짜 원인:
#   MySQL 응답이 schema_name = "capital_target" (DB 이름) 으로 옴
#   → _policyKey 가 "capital_target_customer_profile" 같은 잘못된 키 생성
#   → 소스 "customer_profile" 과 매칭 0건
#
# v90.56 fix:
#   schema_name 이 connecting DB 이름과 같으면 schema-less 로 취급
#   + side 파라미터 명시 (source / target 의 DB 이름 다름)
#   + 2차 fuzzy 매칭 (credit_credit_line ↔ credit_line 변종)
#   + 디버그 로그 (F12 콘솔에서 매칭 결과 즉시 확인)
# ═══════════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"
$FRONTEND_DIR = "D:\project\databridge_full\frontend"

Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host " DataBridge v90.56 검증 매칭 정공법 fix"
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
Write-Host "[1/4] 핵심 파일 존재 확인"
# ──────────────────────────────────────────────────────────────────────────
$vp = "$FRONTEND_DIR\src\pages\Validate.vue"
$tp = "$BACKEND_DIR\tests\test_v90_56_matching.py"
Check-Item "frontend/src/pages/Validate.vue" (Test-Path $vp)
Check-Item "backend/tests/test_v90_56_matching.py" (Test-Path $tp)

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/4] Validate.vue v90.56 마커"
# ──────────────────────────────────────────────────────────────────────────
if (Test-Path $vp) {
    $content = Get-Content $vp -Raw
    
    Check-Item "v90.56 핵심 fix 주석" ($content -match "v90\.56.*핵심 fix.*MySQL 응답")
    Check-Item "side 파라미터 추가" ($content -match "_policyKey = \(t, side = 'source'\)")
    Check-Item "DB 이름 fallback 로직" ($content -match "sch\.toLowerCase\(\) === dbName\.toLowerCase\(\)")
    Check-Item "_policyKey(t, 'source') 호출" ($content -match "_policyKey\(t, 'source'\)")
    Check-Item "_policyKey(t, 'target') 호출" ($content -match "_policyKey\(t, 'target'\)")
    Check-Item "v90.56 디버그 로그" ($content -match "\[v90\.56 매칭\] 소스")
    Check-Item "v90.56 fuzzy fallback" ($content -match "_fuzzyPairs")
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/4] 단위 테스트 (pytest) — 본부장님 환경 41건 매칭"
# ──────────────────────────────────────────────────────────────────────────
Push-Location $BACKEND_DIR
try {
    $testResult = python -m pytest tests/test_v90_56_matching.py -v 2>&1
    $passLine = $testResult | Select-String "passed"
    if ($passLine) {
        Write-Host "  [PASS] pytest: $passLine" -ForegroundColor Green
        $script:pass++
        
        # 핵심 테스트 별도 검증
        $hasNormal = $testResult | Select-String "test_v90_56_normal_scenario_100_percent_match.*PASSED"
        $hasSimplified = $testResult | Select-String "test_v90_56_simplified_scenario_also_works.*PASSED"
        $hasBuggyRepro = $testResult | Select-String "test_v90_55_buggy_zero_match.*PASSED"
        
        Check-Item "본부장님 환경 41건 정공법 매칭 100%" ($null -ne $hasNormal)
        Check-Item "AI 단순화 시나리오도 매칭 OK" ($null -ne $hasSimplified)
        Check-Item "v90.55 버그 재현 (음성 테스트)" ($null -ne $hasBuggyRepro)
    } else {
        Write-Host "  [FAIL] pytest 실행 실패" -ForegroundColor Red
        Write-Host $testResult
        $script:fail++
    }
} finally {
    Pop-Location
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/4] v90.55 마커 보존 확인 (회귀 점검)"
# ──────────────────────────────────────────────────────────────────────────
if (Test-Path $vp) {
    $content = Get-Content $vp -Raw
    Check-Item "v90.55 effective 패턴 보존" ($content -match "isEffectivelyConnected = computed")
    Check-Item "v90.55 applyJobAsConnection 호출 보존" ($content -match "applyJobAsConnection\(active\)")
    Check-Item "v90.55 axios job_id 전달 보존" ($content -match "connector\.loadedJobId \? \{ job_id")
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host " 검증 완료: PASS $pass / FAIL $fail"
Write-Host "═══════════════════════════════════════════════════════════════"

if ($fail -eq 0) {
    Write-Host ""
    Write-Host "✓ v90.56 패치 정상 적용." -ForegroundColor Green
    Write-Host ""
    Write-Host "  적용 후 동작 확인:"
    Write-Host "  1. Frontend 재시작 (npm run dev) — Vite 캐시 무시 새로고침 (Ctrl+Shift+R)"
    Write-Host "     ※ 백엔드 변경 없음 → FastAPI 재기동 불필요"
    Write-Host "  2. 재이관 진행"
    Write-Host "  3. 검증 화면 (/validate/tables) 진입"
    Write-Host "  4. F12 콘솔 열고 다음 로그 확인:"
    Write-Host "     [v90.56 매칭] 소스 N개, 타겟 M개, 1차 정확매칭 K건"
    Write-Host "     → K 가 41 또는 42 면 정상"
    Write-Host "     → K 가 0 이면 또 다른 문제 — 콘솔 로그 캡처해서 공유"
    Write-Host "  5. 화면에서 '소스전용' / '타겟전용' 갯수 확인 (0 또는 매우 적어야 정상)"
    exit 0
} else {
    Write-Host ""
    Write-Host "✗ 일부 항목 실패." -ForegroundColor Red
    exit 1
}
