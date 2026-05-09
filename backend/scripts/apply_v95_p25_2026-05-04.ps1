# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p25 적용 스크립트 (2026-05-04)
# ════════════════════════════════════════════════════════════════════
# v95_p25: frontend/src/pages/JobWizard.vue
#   본부장님 호소 3건:
#     ① "전체선택 버튼 만들어 줘"            → 정규화 규칙 [전체 선택]/[전체 해제]
#     ② "3개 적용 글자 fix" 확인              → "N / M개 적용" 분모 표시
#     ③ "단계별로 새로시작 버튼 좀 달아줘"   → 단계 네비에 [새로 시작]
#
# 본부장님 모토: 추측 처방 금지, 단일 본질 단일 처방, 부작용 0
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p25 적용 (UI 강화 3건)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$JobWizardPath = Join-Path $Root "frontend\src\pages\JobWizard.vue"
if (-not (Test-Path $JobWizardPath)) {
    Write-Host "❌ JobWizard.vue 없음: $JobWizardPath" -ForegroundColor Red
    exit 1
}

Write-Host "[1/4] 본부장님 환경 사전 검증" -ForegroundColor Cyan
$jobwizardContent = Get-Content $JobWizardPath -Raw

# 이전 패치 적용 확인 (v95_p24b 가 있어야 정상 — KB 호출 흐름의 후속)
if (-not $jobwizardContent.Contains("v95_p24b")) {
    Write-Host "  ⚠ v95_p24b 마커 없음 — v95_p24b 먼저 적용 권장" -ForegroundColor Yellow
} else {
    Write-Host "  ✓ v95_p24b 마커 존재 (KB 호출 흐름 OK)"
}

if ($jobwizardContent.Contains("v95_p25")) {
    Write-Host "  ⚠ v95_p25 마커 이미 존재 — 재적용 시 ZIP 의 새 버전으로 덮어쓰기됩니다" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[2/4] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p25_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $JobWizardPath (Join-Path $BackupDir "JobWizard.vue.bak") -Force
Write-Host "  ✓ 백업 위치: $BackupDir"

Write-Host ""
Write-Host "[3/4] 패치 적용 (ZIP 풀 때 이미 덮어써진 상태 — 검증 단계)" -ForegroundColor Cyan
Write-Host "  ✓ ZIP 을 D:\project\ 에서 푸시면 자동 적용됩니다"

Write-Host ""
Write-Host "[4/4] 적용 검증" -ForegroundColor Cyan

$jobwizardAfter = Get-Content $JobWizardPath -Raw

$check_marker      = $jobwizardAfter.Contains("v95_p25")
$check_select_all  = $jobwizardAfter.Contains("function selectAllNorms")
$check_clear_all   = $jobwizardAfter.Contains("function clearAllNorms")
$check_restart     = $jobwizardAfter.Contains("function restartWizard")
$check_is_all      = $jobwizardAfter.Contains("isAllNormsSelected")
$check_btn_class   = $jobwizardAfter.Contains("wiz-btn-restart")
$check_norm_bulk   = $jobwizardAfter.Contains("norm-bulk-actions")
$check_denom       = $jobwizardAfter.Contains("/ {{ normRules.length }}개 적용")

function _OkMark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  ① 정규화 규칙 [전체 선택]/[전체 해제] 버튼:"
Write-Host ("    [{0}] selectAllNorms 함수" -f (_OkMark $check_select_all))
Write-Host ("    [{0}] clearAllNorms 함수" -f (_OkMark $check_clear_all))
Write-Host ("    [{0}] isAllNormsSelected computed" -f (_OkMark $check_is_all))
Write-Host ("    [{0}] norm-bulk-actions 스타일" -f (_OkMark $check_norm_bulk))

Write-Host ""
Write-Host "  ② 'N / M개 적용' 분모 표시:"
Write-Host ("    [{0}] 분모 템플릿 (`/ normRules.length 개 적용`)" -f (_OkMark $check_denom))

Write-Host ""
Write-Host "  ③ 단계별 [새로 시작] 버튼:"
Write-Host ("    [{0}] restartWizard 함수" -f (_OkMark $check_restart))
Write-Host ("    [{0}] wiz-btn-restart 스타일" -f (_OkMark $check_btn_class))

Write-Host ""
Write-Host ("  v95_p25 마커: [{0}]" -f (_OkMark $check_marker))

$allOk = $check_marker -and $check_select_all -and $check_clear_all `
        -and $check_restart -and $check_is_all -and $check_btn_class `
        -and $check_norm_bulk -and $check_denom

Write-Host ""
if ($allOk) {
    Write-Host "═══════════════════════════════════════════════════════════"
    Write-Host "✅ v95_p25 적용 검증 완료" -ForegroundColor Green
    Write-Host "═══════════════════════════════════════════════════════════"
    Write-Host ""
    Write-Host "다음 단계 — 본부장님:" -ForegroundColor Yellow
    Write-Host "  1) frontend Ctrl+Shift+R (Vite HMR 또는 빌드)"
    Write-Host "  2) 위저드 진입 후 확인:"
    Write-Host "     - Step 3 변환 규칙: 정규화 헤더 우측에 [✓ 전체 선택] [✗ 전체 해제]"
    Write-Host "     - 적용 카운트가 'N / M개 적용' (분모 표시)"
    Write-Host "     - 모든 단계 하단: [← 이전] [다음 단계 ▶] ........... [↻ 새로 시작]"
    Write-Host "     - [새로 시작] 클릭 시 확인 다이얼로그 → 모든 입력 초기화"
    Write-Host ""
    Write-Host "롤백 필요 시:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$JobWizardPath' -Force"
} else {
    Write-Host "═══════════════════════════════════════════════════════════"
    Write-Host "❌ 적용 검증 실패 — 일부 마커 누락" -ForegroundColor Red
    Write-Host "═══════════════════════════════════════════════════════════"
    Write-Host ""
    Write-Host "롤백 권장:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$JobWizardPath' -Force"
    exit 2
}
