# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p59 적용 (2026-05-05) — 위저드 상태 복원 본질 처방
# ════════════════════════════════════════════════════════════════════
# 본부장님 호소:
#   "다른 화면으로 갔다 왔더니 이렇게 됐어"
#   - 객체 카운트 (√71 등) 표시되지만 카드 안 비어있음
#
# 진짜 본질 (view tool 100% 추적):
#   saveWizardState() 가 form.value 만 저장
#   allTables / allObjects (객체 목록 자체) 는 저장 안 됨
#   → 복원 시 form.tables.length=71 (저장됨) + allObjects.tables=[] (빈 초기값)
#   → 카운트는 보이지만 카드 비어있음
#
# 처방 (자리 두 곳 보강):
#   1) saveWizardState: allTables + allObjects 도 저장
#   2) restoreWizardState: 복원 시 두 변수도 복원
#   3) watch(allTables/allObjects): 변경 시 자동 저장
#
# 부작용 0:
#   - sessionStorage 한계 5MB 대비 ~50KB (122개 객체 메타)
#   - 1시간 TTL 그대로 (오래된 상태 자동 폐기)
#   - 새로 시작 (?fresh=1) 흐름 그대로
#
# 효과:
#   - 다른 화면 → 위저드 복귀 시 카드 정상 표시
#   - API 재호출 0 (sessionStorage 만 사용)
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p59 적용 (위저드 상태 복원)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$VuePath = Join-Path $Root "frontend\src\pages\JobWizard.vue"
if (-not (Test-Path $VuePath)) { Write-Host "❌ JobWizard.vue 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p59_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $VuePath (Join-Path $BackupDir "JobWizard.vue.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증 (UTF-8 명시)
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$vue = [System.IO.File]::ReadAllText($VuePath, [System.Text.UTF8Encoding]::new($false))

$ok_marker     = $vue.Contains("v95_p59")
$ok_save_obj   = $vue.Contains("allObjects: allObjects.value")
$ok_save_tbl   = $vue.Contains("allTables: allTables.value")
$ok_restore    = $vue.Contains("state.allObjects && typeof state.allObjects")
$ok_watch_tbl  = $vue.Contains("watch(allTables")
$ok_watch_obj  = $vue.Contains("watch(allObjects")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p59 처방:"
Write-Host ("    [{0}] v95_p59 마커" -f (_Mark $ok_marker))
Write-Host ("    [{0}] saveWizardState — allObjects 저장" -f (_Mark $ok_save_obj))
Write-Host ("    [{0}] saveWizardState — allTables 저장" -f (_Mark $ok_save_tbl))
Write-Host ("    [{0}] restoreWizardState — allObjects 복원" -f (_Mark $ok_restore))
Write-Host ("    [{0}] watch(allTables) 자동 저장" -f (_Mark $ok_watch_tbl))
Write-Host ("    [{0}] watch(allObjects) 자동 저장" -f (_Mark $ok_watch_obj))

$allOk = $ok_marker -and $ok_save_obj -and $ok_save_tbl -and $ok_restore -and $ok_watch_tbl -and $ok_watch_obj

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p59 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) Frontend hot-reload (자동) 또는 Ctrl+Shift+R"
    Write-Host ""
    Write-Host "  2) sessionStorage 옛 상태 정리 (선택 — 더 깨끗한 시작):"
    Write-Host "     브라우저 개발자 도구 → Application → Session Storage →"
    Write-Host "     databridge.wizard.state.v1 키 삭제"
    Write-Host "     또는 위저드에서 [↻ 새로 시작] 버튼"
    Write-Host ""
    Write-Host "  3) 테스트: 위저드 → 다른 화면 → 위저드 복귀"
    Write-Host "     → 객체 카드 정상 표시 ✅"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$VuePath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$VuePath' -Force"
    exit 2
}
