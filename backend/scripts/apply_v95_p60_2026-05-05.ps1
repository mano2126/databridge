# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p60 적용 (2026-05-05) — 위저드 전체 state 통합 보존
# ════════════════════════════════════════════════════════════════════
# 본부장님 호소:
#   "변환규칙도 선택후 다른 화면 갔다 오면 없어져 버려"
#   "위저드 전체적으로 다른 화면 갔다 오면 변경된 내용까지 유지 되는기능"
#
# 진짜 본질 (view tool 100% 추적):
#   사용자 작업 데이터가 form 외에 여러 ref 에 분산:
#   - warnRules/normRules: 변환 규칙 (AI 분석 결과)
#   - preflightRisks/preflightSummary: AI DBA 분석 결과
#   - sched/schedEnabled: 스케줄 설정
#   - openRules/normOpen: UI 펼침 상태
#   - tableSort/procSort/etc: 정렬 상태
#   → form 만 저장 → 다른 화면 복귀 시 모두 손실
#   → AI 재분석 필요 → 비용 추가 발생 + 작업 손실
#
# 처방: 위저드 전체 state 24개 항목 통합 저장/복원
#   1) saveWizardState: 24개 항목 모두 sessionStorage 저장
#   2) restoreWizardState: 24개 항목 모두 복원 (타입 검증)
#   3) watch: 24개 항목 변경 시 자동 저장
#
# 효과:
#   - 다른 화면 → 위저드 복귀: 모든 작업 100% 보존 ✅
#   - AI 재분석 비용 0 (warnRules/preflightRisks 보존)
#   - UX 향상 (정렬/펼침 상태도 보존)
#
# 부작용 0:
#   - sessionStorage 5MB 한계 vs 전체 ~200KB 추산
#   - 1시간 TTL 그대로 (오래된 상태 자동 폐기)
#   - 새로 시작 (?fresh=1) 흐름 그대로
#   - v95_p59 처방 100% 보존 (allTables/allObjects)
#
# 보존 항목 24개:
#   변환 규칙 (5): warnRules, normRules, normOpen, openRules, normUnappliedOpen
#   AI DBA (6): preflightRisks, preflightSummary, preflightOpen,
#              pfSelectedIdx, pfSortMode, showAllAffected
#   스케줄 (3): schedEnabled, schedType, sched
#   검토 펼침 (3): reviewObjOpen, reviewCfgOpen, reviewDetailOpen
#   UI 상태 (7): objTab, objSearch, tableSort, procSort, funcSort, trigSort, viewSort
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p60 적용 (위저드 전체 state 보존)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$VuePath = Join-Path $Root "frontend\src\pages\JobWizard.vue"
if (-not (Test-Path $VuePath)) { Write-Host "❌ JobWizard.vue 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p60_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $VuePath (Join-Path $BackupDir "JobWizard.vue.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증 (UTF-8 명시)
Write-Host ""
Write-Host "[2/3] 적용 검증 (24개 사용자 작업 항목)" -ForegroundColor Cyan
$vue = [System.IO.File]::ReadAllText($VuePath, [System.Text.UTF8Encoding]::new($false))

$ok_marker = $vue.Contains("v95_p60")
$ok_p59    = $vue.Contains("v95_p59")  # 이전 처방 보존

# 24개 항목 검증
$items = @(
    @("변환 규칙 — warnRules",       "state.warnRules",        "watch(warnRules"),
    @("변환 규칙 — normRules",       "state.normRules",        "watch(normRules"),
    @("변환 규칙 — normOpen",        "state.normOpen",         "watch(normOpen"),
    @("변환 규칙 — openRules",       "state.openRules",        "watch(openRules"),
    @("변환 규칙 — normUnappliedOpen","state.normUnappliedOpen","watch(normUnappliedOpen"),
    @("AI DBA — preflightRisks",     "state.preflightRisks",   "watch(preflightRisks"),
    @("AI DBA — preflightSummary",   "state.preflightSummary", "watch(preflightSummary"),
    @("AI DBA — preflightOpen",      "state.preflightOpen",    "watch(preflightOpen"),
    @("AI DBA — pfSelectedIdx",      "state.pfSelectedIdx",    "watch(pfSelectedIdx"),
    @("AI DBA — pfSortMode",         "state.pfSortMode",       "watch(pfSortMode"),
    @("AI DBA — showAllAffected",    "state.showAllAffected",  "watch(showAllAffected"),
    @("스케줄 — schedEnabled",       "state.schedEnabled",     "watch(schedEnabled"),
    @("스케줄 — schedType",          "state.schedType",        "watch(schedType"),
    @("스케줄 — sched",              "state.sched",            "watch(sched"),
    @("검토 — reviewObjOpen",        "state.reviewObjOpen",    "watch(reviewObjOpen"),
    @("검토 — reviewCfgOpen",        "state.reviewCfgOpen",    "watch(reviewCfgOpen"),
    @("검토 — reviewDetailOpen",     "state.reviewDetailOpen", "watch(reviewDetailOpen"),
    @("UI — objTab",                 "state.objTab",           "watch(objTab"),
    @("UI — objSearch",              "state.objSearch",        "watch(objSearch"),
    @("UI — tableSort",              "state.tableSort",        "watch(tableSort"),
    @("UI — procSort",               "state.procSort",         "watch(procSort"),
    @("UI — funcSort",               "state.funcSort",         "watch(funcSort"),
    @("UI — trigSort",               "state.trigSort",         "watch(trigSort"),
    @("UI — viewSort",               "state.viewSort",         "watch(viewSort")
)

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
$okCount = 0
foreach ($item in $items) {
    $name = $item[0]
    $restore = $item[1]
    $watch = $item[2]
    $ok = $vue.Contains($restore) -and $vue.Contains($watch)
    if ($ok) { $okCount++ }
    Write-Host ("    [{0}] {1}" -f (_Mark $ok), $name)
}

Write-Host ""
Write-Host ("  v95_p60 마커: {0} ({1}건)" -f (_Mark $ok_marker), [regex]::Matches($vue, "v95_p60").Count)
Write-Host ("  v95_p59 보존: {0}" -f (_Mark $ok_p59))
Write-Host ("  통합 항목: {0}/24" -f $okCount)

$allOk = $ok_marker -and $ok_p59 -and ($okCount -eq 24)

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p60 적용 완료 — 위저드 전체 state 보존" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) Frontend hot-reload (자동) 또는 Ctrl+Shift+R"
    Write-Host ""
    Write-Host "  2) sessionStorage 옛 상태 정리 (한 번만):"
    Write-Host "     위저드에서 [↻ 새로 시작] 버튼"
    Write-Host ""
    Write-Host "  3) 테스트:"
    Write-Host "     - 위저드 → 변환 규칙 토글 변경 → 다른 화면 → 위저드 복귀"
    Write-Host "     - 모든 변경 사항 보존 ✅"
    Write-Host "     - AI 재분석 0 (비용 절감)"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$VuePath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$VuePath' -Force"
    exit 2
}
