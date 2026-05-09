# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p43 적용 (2026-05-05) — 검토 화면 시각 계층 강화
# ════════════════════════════════════════════════════════════════════
# 본부장님 호소: "내용들이 구분이 잘 안돼"
#
# 진단 (이미지 100% 분석):
#   - 섹션 헤더가 본문과 비슷한 흰 배경 → 시각 분리 약함
#   - 라벨/값 같은 색감 → 위계 약함
#   - 행 사이 구분 없음 → 평평하게 보임
#
# 처방 (CSS 만 보강 — HTML 구조 변경 0):
#   - 섹션 헤더: 회색톤 그라디언트 + 강한 좌측 띠 (4px)
#   - 본문 행: 흰 배경 카드 + 미세 테두리 + 호버 효과
#   - 라벨: 작게 + uppercase + 약한 회색 (덜 부각)
#   - 값: 진한 검정 (#0f172a) + 굵은 폰트 (부각)
#   - 다크 모드 호환 (CSS 변수 자동 적용)
#
# 부작용 0:
#   - HTML 구조 변경 0 (이전 v95_p37 + v95_p40 처방 100% 보존)
#   - CSS 우선순위로 기존 스타일 강화만
#   - 반응형 (좁은 화면 자동 스택) 보존
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p43 적용 (시각 계층 강화)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$VuePath = Join-Path $Root "frontend\src\pages\JobWizard.vue"
if (-not (Test-Path $VuePath)) { Write-Host "❌ JobWizard.vue 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p43_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $VuePath (Join-Path $BackupDir "JobWizard.vue.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$vue = Get-Content $VuePath -Raw

$ok_marker      = $vue.Contains("v95_p43")
$ok_section_bg  = $vue.Contains("background: #ffffff") -and $vue.Contains("box-shadow: 0 1px 2px")
$ok_head_grad   = $vue.Contains("linear-gradient(to bottom, #f8fafc, #f1f5f9)")
$ok_primary     = $vue.Contains("linear-gradient(to bottom, #eff6ff, #dbeafe 130%)")
$ok_value_dark  = $vue.Contains("#0f172a")
$ok_card_hover  = $vue.Contains("rgba(37,99,235,0.25)") -or $vue.Contains("rgba(37,99,235,0.2)")
$ok_dark_mode   = $vue.Contains(".dark .review-section")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p43 처방:"
Write-Host ("    [{0}] v95_p43 마커" -f (_Mark $ok_marker))
Write-Host ("    [{0}] 섹션 카드 (흰 배경 + 미세 그림자)" -f (_Mark $ok_section_bg))
Write-Host ("    [{0}] 헤더 그라디언트 (회색톤)" -f (_Mark $ok_head_grad))
Write-Host ("    [{0}] 기본 정보 헤더 강조 (파랑 그라디언트)" -f (_Mark $ok_primary))
Write-Host ("    [{0}] 값 진한 검정 (#0f172a)" -f (_Mark $ok_value_dark))
Write-Host ("    [{0}] 행 호버 효과" -f (_Mark $ok_card_hover))
Write-Host ("    [{0}] 다크 모드 호환" -f (_Mark $ok_dark_mode))

Write-Host ""
Write-Host "  이전 처방 보존 (HTML 변경 0):"
foreach ($m in @("v95_p37","v95_p40","review-dbflow-row","review-section-jobname")) {
    Write-Host ("    [{0}] {1} : {2}건" -f (_Mark ($vue.Contains($m))), $m, ([regex]::Matches($vue, [regex]::Escape($m))).Count)
}

$allOk = $ok_marker -and $ok_section_bg -and $ok_head_grad -and $ok_primary -and $ok_value_dark -and $ok_card_hover

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p43 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) Frontend hot-reload (자동) 또는 Ctrl+Shift+R"
    Write-Host "  2) 위저드 → Step 6 (검토 & 실행) 페이지 확인"
    Write-Host ""
    Write-Host "검증 시나리오:"
    Write-Host "  ✅ '기본 정보' 섹션 — 파란 그라디언트 헤더 + 4px 파란 띠"
    Write-Host "  ✅ '이관 객체' / '변환·실행 설정' 섹션 — 회색톤 그라디언트 헤더"
    Write-Host "  ✅ 본문 행 — 미세 테두리 카드 + 호버 시 파랑 강조"
    Write-Host "  ✅ 라벨 (이관 모드 등) — 작은 회색 + UPPERCASE"
    Write-Host "  ✅ 값 (스키마+데이터 등) — 진한 검정 + 굵음"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$VuePath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$VuePath' -Force"
    exit 2
}
