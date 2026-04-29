# ═══════════════════════════════════════════════════════════════════════════
# verify_v90_57.ps1 — DataBridge v90.57 카테고리 탭 클릭 토글
# ═══════════════════════════════════════════════════════════════════════════
# 본부장님 요청 (2026-04-28):
#   "카테고리 버튼 클릭 = 해당 카테고리 항목 전체 선택 ↔ 전체 해제 토글"
#
# 동작:
#   - 다른 카테고리 클릭: 그 카테고리로 이동만 (선택 변경 X)
#   - 활성 카테고리 재클릭:
#       none / partial → 전체 선택
#       all            → 전체 해제 (토글)
#
# 변경 파일: 1개 (frontend/src/components/advisor/AdvisorPanel.vue)
# 백엔드 변경 없음 — FastAPI 재기동 불필요.
# ═══════════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"
$FRONTEND_DIR = "D:\project\databridge_full\frontend"

Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host " DataBridge v90.57 카테고리 탭 클릭 토글"
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
Write-Host "[1/4] 핵심 파일 존재"
# ──────────────────────────────────────────────────────────────────────────
$ap = "$FRONTEND_DIR\src\components\advisor\AdvisorPanel.vue"
$tp = "$BACKEND_DIR\tests\test_v90_57_category_toggle.py"
Check-Item "frontend/src/components/advisor/AdvisorPanel.vue" (Test-Path $ap)
Check-Item "backend/tests/test_v90_57_category_toggle.py" (Test-Path $tp)

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/4] AdvisorPanel.vue v90.57 마커"
# ──────────────────────────────────────────────────────────────────────────
if (Test-Path $ap) {
    $content = Get-Content $ap -Raw
    
    Check-Item "v90.57 주석 존재" ($content -match "v90\.57.*카테고리 탭 재클릭 시 토글")
    Check-Item "@click 핸들러 변경" ($content -match '@click="onCategoryClick\(cat\)"')
    Check-Item "categorySelectionState computed" ($content -match "const categorySelectionState = computed")
    Check-Item "onCategoryClick 함수" ($content -match "function onCategoryClick\(cat\)")
    Check-Item "selectAllInCategory 함수" ($content -match "function selectAllInCategory\(catId\)")
    Check-Item "deselectAllInCategory 함수" ($content -match "function deselectAllInCategory\(catId\)")
    Check-Item "선택 상태 시각화 아이콘 (✓/◐)" ($content -match "adv-cat-sel-state")
    Check-Item "title 툴팁 (재클릭 안내)" ($content -match "재클릭하면 전체")
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/4] 단위 테스트 — 본부장님 시나리오 6단계 검증"
# ──────────────────────────────────────────────────────────────────────────
Push-Location $BACKEND_DIR
try {
    $testResult = python -m pytest tests/test_v90_57_category_toggle.py -v 2>&1
    $passLine = $testResult | Select-String "passed"
    if ($passLine) {
        Write-Host "  [PASS] pytest: $passLine" -ForegroundColor Green
        $script:pass++
        
        $hasPresidentFlow = $testResult | Select-String "test_president_screen_full_flow.*PASSED"
        $hasNoPollution = $testResult | Select-String "test_no_cross_category_pollution.*PASSED"
        $hasOtherMoves = $testResult | Select-String "test_other_category_just_moves.*PASSED"
        $hasEditedPreserved = $testResult | Select-String "test_edited_recs_preserved_on_select_all.*PASSED"
        
        Check-Item "본부장님 시나리오 6단계" ($null -ne $hasPresidentFlow)
        Check-Item "카테고리 간 오염 없음" ($null -ne $hasNoPollution)
        Check-Item "다른 카테고리 클릭은 이동만" ($null -ne $hasOtherMoves)
        Check-Item "edited 항목 보존" ($null -ne $hasEditedPreserved)
    } else {
        Write-Host "  [FAIL] pytest 실행 실패" -ForegroundColor Red
        $script:fail++
    }
} finally {
    Pop-Location
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/4] 회귀 점검 — 기존 selectAll/deselectAll/toggleAll 보존"
# ──────────────────────────────────────────────────────────────────────────
if (Test-Path $ap) {
    $content = Get-Content $ap -Raw
    Check-Item "기존 selectAll 함수 보존" ($content -match "function selectAll\(\)\s*\{")
    Check-Item "기존 deselectAll 함수 보존" ($content -match "function deselectAll\(\)\s*\{")
    Check-Item "기존 toggleAll 함수 보존" ($content -match "function toggleAll\(checked\)")
    Check-Item "기존 selectBySev 함수 보존" ($content -match "function selectBySev\(sev\)")
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host " 검증 완료: PASS $pass / FAIL $fail"
Write-Host "═══════════════════════════════════════════════════════════════"

if ($fail -eq 0) {
    Write-Host ""
    Write-Host "✓ v90.57 패치 정상 적용." -ForegroundColor Green
    Write-Host ""
    Write-Host "  적용 후 동작 확인 (이관 Job 위저드 → AdvisorPanel):"
    Write-Host "  1. Frontend 재시작 (npm run dev) + Ctrl+Shift+R"
    Write-Host "     ※ 백엔드 변경 없음 → FastAPI 재기동 불필요"
    Write-Host "  2. Job Wizard → 사전점검 → AdvisorPanel 진입"
    Write-Host "  3. 카테고리 탭 동작 확인:"
    Write-Host "     [서버 설정 7] 클릭 → 이동"
    Write-Host "     [서버 설정 7] 다시 클릭 → 7개 모두 선택 + 카테고리에 ✓ 표시"
    Write-Host "     [서버 설정 7] 또 클릭 → 7개 모두 해제 (토글)"
    Write-Host "     [테이블 구조 12] 클릭 → 테이블로 이동, 서버 선택 보존"
    Write-Host "  4. 마우스 hover 시 툴팁: '재클릭하면 전체 선택/해제'"
    exit 0
} else {
    Write-Host ""
    Write-Host "✗ 일부 항목 실패." -ForegroundColor Red
    exit 1
}
