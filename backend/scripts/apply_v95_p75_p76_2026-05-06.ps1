# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p75 + v95_p76 적용 (2026-05-06)
#   본부장님 UX 호소 — 결정 표시 + 컴팩트 라디오 리스트
# ════════════════════════════════════════════════════════════════════
# 본부장님 호소:
#   1) "어떤걸 선택했는지 보여 주자, 화면이 지나가서 모르겠어"
#   2) "아이콘이든 뱃지 형태든 어떤 형태로든"
#   3) "3개를 보여주고 check box 로 선택할 수 있게 해주는것도 좋겠어"
#   4) "폭을 조금더 넓히고, 오른쪽화면 폭은 조금 줄여야 될 것 같아"
#   5) "3가지 선택할 수 있는 블록은 조금 줄여도 될 것 같아"
#
# 처방:
#
#   v95_p75 — 결정 뱃지 + 강한 강조
#     ✓ 좌측 리스트에 결정 뱃지 표시 (🤖/✍️/⊘ 색상별)
#     ✓ 우측 상세에 "선택됨: 자동 변환 시도" 큰 뱃지 + 색상
#     ✓ "결정 취소" → "↻ 변경" (의미 명확)
#     ✓ 좌측 폭 확대 (320 → 420)
#     ✓ 결정 버튼 컴팩트화 (10/12 → 7/8)
#
#   v95_p76 — 컴팩트 라디오 리스트 (추가 호소)
#     ✓ 가로 카드 3개 → 세로 라디오 3줄 (높이 절반)
#     ✓ 라디오 형태 (체크박스 같은 시각)
#     ✓ 결정별 색상 (자동=초록, 수동=보라, 제외=빨강)
#     ✓ active 상태 명확 (border 진하게 + 배경 색상)
#     ✓ explain 컴팩트 (조건별 짧은 안내)
#     ✓ 좌측 폭 추가 확대 (420 → 460)
#
# 변경 파일 1개:
#   frontend/src/pages/JobWizard.vue
#
# 부작용 0:
#   - 기존 모든 처방 100% 보존 (v95_p65~p74 모두)
#   - 결정 로직 (form.objectDecisions) 변경 없음
#   - 다른 단계 영향 0
#
# UI 비교:
#
#   Before (v95_p64):
#     [🤖 자동 변환] [✍️ 수동 SQL] [⊘ 이관 제외]   <- 가로 3카드
#     - 어떤 걸 선택했는지 화면 스크롤되면 까먹음
#     - 좌측 리스트엔 결정 표시 0
#
#   After (v95_p75 + v95_p76):
#     좌측 리스트:
#       [긴급] ⚠️ vJobCandidate (🤖)  ← 결정 뱃지 컬러풀
#       [긴급] ⚠️ vEmployee (✍️)
#       [긴급] ⚠️ vAdditional (⊘)
#     
#     우측 상세:
#       📋 변환 방법 선택
#       💡 잘 모르시면 [자동 변환 시도] 추천
#       
#       ◉ 🤖 자동 변환 시도        AI 변환 + 환각 자동 검증 (추천) [선택됨]
#       ○ ✍️ 전문가 직접 작성       DBA 만 권장
#       ○ ⊘  이관 제외             이 객체 없이 진행
#       
#       ✓ 선택됨: 🤖 자동 변환 시도            [↻ 변경]
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p75 + v95_p76 적용"
Write-Host "  결정 뱃지 + 컴팩트 라디오 리스트"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$Path = Join-Path $Root "frontend\src\pages\JobWizard.vue"

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p75_p76_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $Path (Join-Path $BackupDir "JobWizard.vue.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$src = [System.IO.File]::ReadAllText($Path, [System.Text.UTF8Encoding]::new($false))

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p75 처방 (결정 뱃지 + 강조):"
$ok_p75       = ([regex]::Matches($src, 'v95_p75')).Count -ge 5
$ok_badge     = $src.Contains('pf-list-decision-badge')
$ok_strong    = $src.Contains('pf-rm-d-status-strong')
$ok_change    = $src.Contains('↻ 변경')
$ok_460       = $src.Contains('grid-template-columns: 460px')
Write-Host ("    [{0}] v95_p75 마커 (5건 이상)" -f (_Mark $ok_p75))
Write-Host ("    [{0}] 좌측 결정 뱃지 (pf-list-decision-badge)" -f (_Mark $ok_badge))
Write-Host ("    [{0}] 강한 강조 (pf-rm-d-status-strong)" -f (_Mark $ok_strong))
Write-Host ("    [{0}] '↻ 변경' 버튼" -f (_Mark $ok_change))

Write-Host ""
Write-Host "  v95_p76 처방 (컴팩트 라디오):"
$ok_p76       = ([regex]::Matches($src, 'v95_p76')).Count -ge 3
$ok_compact   = $src.Contains('pf-rm-decision-compact')
$ok_radiolist = $src.Contains('pf-rm-radio-list')
$ok_radiorow  = $src.Contains('pf-rm-radio-row')
$ok_radioinput= $src.Contains('pf-rm-radio-input')
Write-Host ("    [{0}] v95_p76 마커 (3건 이상)" -f (_Mark $ok_p76))
Write-Host ("    [{0}] 컴팩트 결정 영역" -f (_Mark $ok_compact))
Write-Host ("    [{0}] 라디오 리스트" -f (_Mark $ok_radiolist))
Write-Host ("    [{0}] 라디오 행" -f (_Mark $ok_radiorow))
Write-Host ("    [{0}] 라디오 input" -f (_Mark $ok_radioinput))
Write-Host ("    [{0}] 좌측 폭 460px" -f (_Mark $ok_460))

Write-Host ""
Write-Host "  이전 처방 보존:"
foreach ($m in @('v95_p65','v95_p66','v95_p72','v95_p73','manualSqlModal','objectDecisions')) {
    Write-Host ("    [{0}] {1}" -f (_Mark ($src.Contains($m))), $m)
}

$allOk = $ok_p75 -and $ok_badge -and $ok_strong -and $ok_change -and `
         $ok_p76 -and $ok_compact -and $ok_radiolist -and $ok_radiorow -and `
         $ok_radioinput -and $ok_460

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p75 + v95_p76 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:"
    Write-Host ""
    Write-Host "  1) Frontend hot-reload 자동 (또는 Ctrl+Shift+R 강제 새로고침)"
    Write-Host ""
    Write-Host "  2) 위저드 ③ 변환 규칙 → ⚠️ vJobCandidate 등 위험 객체 클릭"
    Write-Host ""
    Write-Host "  3) 검증:"
    Write-Host "     - 좌측 리스트: 결정 뱃지 색상별 (🤖 초록 / ✍️ 보라 / ⊘ 빨강)"
    Write-Host "     - 우측 상세: 라디오 리스트 3줄 (가로 카드 X)"
    Write-Host "     - 라디오 선택 시: 색상 강조 + 큰 뱃지 '선택됨: ...'"
    Write-Host "     - 좌측 폭 더 넓고 우측 폭 적정"
    Write-Host "     - [↻ 변경] 버튼으로 결정 취소 가능"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$Path' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    exit 2
}
