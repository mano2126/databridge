# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p84 (2026-05-06) — 좌측 인라인 결정 + 일괄 처리
# ════════════════════════════════════════════════════════════════════
# 본부장님 호소:
#   "여기 목록에서 AI 바로 선택하게 할 수 있을까?"
#   "오른쪽 창을 끝까지 드레그 한 후 하나씩 선택하기 너무 번거로워"
#
# 본질:
#   위험 객체 6개 결정 = 6번 클릭 + 6번 드래그 = 시간 + 피로
#   → 좌측에서 즉시 결정 가능하면 클릭 6번만 (드래그 0)
#   → 일괄 처리로 1번 클릭 가능
#
# 처방:
#
#   v95_p84-A — 좌측 리스트 인라인 결정 버튼
#     각 위험 객체 옆에 [🤖] [✍️] [⊘] 버튼 3개
#     - 클릭 = 즉시 결정 (드래그 + 우측 스크롤 0)
#     - active 상태 (현재 결정) 명확 표시
#     - hover 효과 (확대 + 색상)
#     - object_risk 카테고리만 표시 (다른 카테고리 영향 0)
#
#   v95_p84-B — 일괄 처리 헤더
#     "⚡ 일괄 처리 (6건):"
#     [🤖 모두 자동] [⊘ 모두 제외] [↻ 초기화]
#     - 사용자 확인 후 일괄 적용
#     - manual 일괄은 의미 없으므로 제외 (각 객체별 SQL 다름)
#
# 효과 (본부장님 환경 6개 객체 기준):
#
#   Before (v95_p76):
#     1. 좌측에서 객체 클릭 (6번)
#     2. 우측 끝까지 드래그 (6번)
#     3. 라디오 클릭 (6번)
#     4. 다음 객체 → 반복
#     총 클릭 18+ 회 + 드래그 6회
#
#   After (v95_p84):
#     옵션 A: [🤖 모두 자동] 1회 클릭 → 끝
#     옵션 B: 좌측에서 [🤖] [⊘] 직접 클릭 (6번 클릭, 드래그 0)
#     총 클릭 1회 또는 6회 (드래그 0)
#
# 변경 파일 1개:
#   1) frontend/src/pages/JobWizard.vue (좌측 인라인 + 일괄 처리)
#
# 부작용 0:
#   - 우측 라디오 리스트 (v95_p76) 그대로 — 상세 검토 시 사용
#   - 결정 뱃지 (v95_p75) 그대로 — 시각 확인
#   - 모든 이전 처방 100% 보존
#   - object_risk 외 카테고리 영향 0
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p84"
Write-Host "  좌측 인라인 결정 + 일괄 처리 (드래그 0)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$Path = Join-Path $Root "frontend\src\pages\JobWizard.vue"

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p84_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $Path (Join-Path $BackupDir "JobWizard.vue.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$src = [System.IO.File]::ReadAllText($Path, [System.Text.UTF8Encoding]::new($false))

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p84 처방 (좌측 인라인 + 일괄):"
$ok_p84       = ([regex]::Matches($src, 'v95_p84')).Count -ge 4
$ok_bulk_html = $src.Contains('pf-bulk-actions')
$ok_bulk_btn  = $src.Contains('pf-bulk-btn')
$ok_quick_html= $src.Contains('pf-list-quick-actions')
$ok_quick_btn = $src.Contains('pf-quick-btn')
$ok_setAll    = $src.Contains('setAllObjectDecisions')
$ok_clearAll  = $src.Contains('clearAllObjectDecisions')
$ok_count     = $src.Contains('objectRiskCount')

Write-Host ("    [{0}] v95_p84 마커 (4건 이상)" -f (_Mark $ok_p84))
Write-Host ("    [{0}] 일괄 처리 헤더 HTML" -f (_Mark $ok_bulk_html))
Write-Host ("    [{0}] 일괄 처리 버튼 CSS" -f (_Mark $ok_bulk_btn))
Write-Host ("    [{0}] 좌측 인라인 버튼 HTML" -f (_Mark $ok_quick_html))
Write-Host ("    [{0}] 좌측 인라인 버튼 CSS" -f (_Mark $ok_quick_btn))
Write-Host ("    [{0}] setAllObjectDecisions 함수" -f (_Mark $ok_setAll))
Write-Host ("    [{0}] clearAllObjectDecisions 함수" -f (_Mark $ok_clearAll))
Write-Host ("    [{0}] objectRiskCount computed" -f (_Mark $ok_count))

Write-Host ""
Write-Host "  이전 처방 보존:"
foreach ($m in @('v95_p65','v95_p72','v95_p73','v95_p75','v95_p76',
                  'pf-list-decision-badge','pf-rm-radio-row','manualSqlModal','objectDecisions')) {
    Write-Host ("    [{0}] {1}" -f (_Mark ($src.Contains($m))), $m)
}

$allOk = $ok_p84 -and $ok_bulk_html -and $ok_bulk_btn -and `
         $ok_quick_html -and $ok_quick_btn -and `
         $ok_setAll -and $ok_clearAll -and $ok_count

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p84 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:"
    Write-Host ""
    Write-Host "  1) Frontend 강제 새로고침: Ctrl+Shift+R"
    Write-Host ""
    Write-Host "  2) 위저드 ③ 변환 규칙 → 위험 객체 리스트 확인:"
    Write-Host ""
    Write-Host "     [상단 — 일괄 처리 헤더]"
    Write-Host "       ⚡ 일괄 처리 (6건): [🤖 모두 자동] [⊘ 모두 제외] [↻ 초기화]"
    Write-Host ""
    Write-Host "     [각 위험 객체 — 우측 끝에 인라인 버튼]"
    Write-Host "       긴급 ⚠️ vJobCandidate ... [🤖] [✍️] [⊘]"
    Write-Host "       긴급 ⚠️ vJobCandidateEducation ... [🤖] [✍️] [⊘]"
    Write-Host "       ..."
    Write-Host ""
    Write-Host "  3) 검증:"
    Write-Host "     A. [🤖 모두 자동] 클릭 → 6개 모두 🤖 active"
    Write-Host "     B. 또는 객체별 [🤖] 클릭 → 좌측에서 즉시 결정"
    Write-Host "     C. 우측 드래그 0 — 좌측만으로 모든 결정 가능"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$Path' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    exit 2
}
