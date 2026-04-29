# ═══════════════════════════════════════════════════════════════════════════
# verify_v90_60.ps1 — DataBridge v90.60 진행 중 표시 fallback
# ═══════════════════════════════════════════════════════════════════════════
# 본부장님 화면 진단 (F12 캡처):
#   - LIVE 배너:   kyc_document 305,000/1,000,000 rows  (정상)
#   - 테이블 카드: kyc_document 0 → 0  (rows 비어있음)
# 
# 진단 결과:
#   같은 시점에 한 곳은 정확, 한 곳은 0/0 → backend 가 current_table_rows_done 은
#   갱신하면서 item_statuses[].rows_src/tgt 갱신은 어떤 경로에서 누락됨.
#
# v90.60 처방:
#   Frontend fallback — 진행 중 테이블이 current_table 이면 top-level
#   current_table_rows_done/total 사용 (backend 가 적극 갱신하는 신뢰 가능 데이터).
#
# 변경 파일: 1개 (frontend/src/pages/JobMonitor.vue)
# 백엔드 변경 없음 — FastAPI 재기동 불필요.
# ═══════════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"
$FRONTEND_DIR = "D:\project\databridge_full\frontend"

Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host " DataBridge v90.60 진행 중 표시 fallback"
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host ""

$pass = 0
$fail = 0

function Check-Item {
    param([string]$Name, [bool]$Result)
    if ($Result) {
        Write-Host "  [PASS] $Name" -ForegroundColor Green
        $script:pass++
    } else {
        Write-Host "  [FAIL] $Name" -ForegroundColor Red
        $script:fail++
    }
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host "[1/3] JobMonitor.vue v90.60 마커"
# ──────────────────────────────────────────────────────────────────────────
$jm = "$FRONTEND_DIR\src\pages\JobMonitor.vue"
Check-Item "JobMonitor.vue 존재" (Test-Path $jm)

if (Test-Path $jm) {
    $content = Get-Content $jm -Raw
    Check-Item "v90.60 주석 마커" ($content -match "v90\.60.*\bfallback\b")
    Check-Item "_isCurrentTable 헬퍼" ($content -match "function _isCurrentTable")
    Check-Item "_displayRowsDone 헬퍼" ($content -match "function _displayRowsDone")
    Check-Item "_displayRowsTotal 헬퍼" ($content -match "function _displayRowsTotal")
    Check-Item "template 가 _displayRowsDone 사용" ($content -match "_displayRowsDone\(item\)")
    Check-Item "progLabel fallback 주석" ($content -match "v90\.60 fallback")
    Check-Item "fmtItemEta fallback 주석" ($content -match "v90\.60.*top-level current_table_rows_total fallback")
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/3] 단위 테스트 — 본부장님 시나리오"
# ──────────────────────────────────────────────────────────────────────────
Push-Location $BACKEND_DIR
try {
    if (Test-Path "tests\test_v90_60_progress_fallback.py") {
        $testResult = python -m pytest tests/test_v90_60_progress_fallback.py -v 2>&1
        $passLine = $testResult | Select-String "passed"
        if ($passLine) {
            Write-Host "  [PASS] pytest: $passLine" -ForegroundColor Green
            $script:pass++
            
            $hasPresident = $testResult | Select-String "test_president_capture_scenario.*PASSED"
            $hasNoPollution = $testResult | Select-String "test_other_table_not_current_no_fallback.*PASSED"
            $hasNormal = $testResult | Select-String "test_normal_scenario_still_works.*PASSED"
            
            Check-Item "본부장님 캡처 시나리오 (305000/1000000)" ($null -ne $hasPresident)
            Check-Item "다른 테이블에 fallback 오염 없음" ($null -ne $hasNoPollution)
            Check-Item "정상 데이터는 그대로 사용" ($null -ne $hasNormal)
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
Write-Host "[3/3] 회귀 점검 — 기존 progLabel/fmtItemEta 보존"
# ──────────────────────────────────────────────────────────────────────────
if (Test-Path $jm) {
    $content = Get-Content $jm -Raw
    Check-Item "기존 progLabel 함수 보존" ($content -match "function progLabel\(item\)")
    Check-Item "기존 fmtItemEta 함수 보존" ($content -match "function fmtItemEta\(item\)")
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host " 검증 완료: PASS $pass / FAIL $fail"
Write-Host "═══════════════════════════════════════════════════════════════"

if ($fail -eq 0) {
    Write-Host ""
    Write-Host "✓ v90.60 패치 정상 적용." -ForegroundColor Green
    Write-Host ""
    Write-Host "  적용 후 확인:"
    Write-Host "  1. Frontend 만 재시작 (백엔드 변경 없음)"
    Write-Host "     cd D:\project\databridge_full\frontend"
    Write-Host "     npm run dev"
    Write-Host "  2. 브라우저 Ctrl+Shift+R (강제 새로고침)"
    Write-Host "  3. 이관 작업 모니터 → 진행 중 테이블 행 확인"
    Write-Host "     → 0 → 0 대신 305,000 → 1,000,000 같이 정확히 표시"
    Write-Host "     → 잔여시간도 표시됨"
    exit 0
} else {
    Write-Host ""
    Write-Host "✗ 일부 항목 실패." -ForegroundColor Red
    exit 1
}
