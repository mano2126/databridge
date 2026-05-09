# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p40 적용 (2026-05-05)
# ════════════════════════════════════════════════════════════════════
# 본부장님 호소 (이관 Job 생성 화면 가독성 개선):
#   1) 기본 정보 옆에 Job 이름 표시 (지금은 본문 첫 항목)
#   2) 소스 DB 좌측 / 타겟 DB 우측 → 2줄로 압축
#   3) 제목/내용 시각 구분 강화 (선/색상 대비)
#
# 처방 (Frontend 만, 백엔드 변경 0):
#   - 기본 정보 섹션 헤더 우측에 Job 이름 칩 표시
#   - 소스 → 타겟 좌우 카드 + 가운데 화살표 (DB 흐름 시각화)
#   - 2줄 압축: 1줄 = 소스↔타겟, 2줄 = 이관모드/AI DBA/자동수정
#   - 시각 구분: 좌측 색상 띠 + 그라디언트 배경 + 호버 효과
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p40 적용 (검토 화면 가독성 개선)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$VuePath = Join-Path $Root "frontend\src\pages\JobWizard.vue"
if (-not (Test-Path $VuePath)) { Write-Host "❌ JobWizard.vue 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p40_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $VuePath (Join-Path $BackupDir "JobWizard.vue.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$vue = Get-Content $VuePath -Raw

$ok_marker      = $vue.Contains("v95_p40")
$ok_jobname     = $vue.Contains("review-section-jobname")
$ok_dbflow      = $vue.Contains("review-dbflow-row") -and $vue.Contains("review-dbflow-arrow")
$ok_db_cards    = $vue.Contains("review-db-source") -and $vue.Contains("review-db-target")
$ok_attr_row    = $vue.Contains("review-attr-row") -and $vue.Contains("rv-item-compact")
$ok_visual      = $vue.Contains("review-section-head-primary") -and $vue.Contains("border-left: 3px solid")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p40 처방:"
Write-Host ("    [{0}] v95_p40 마커" -f (_Mark $ok_marker))
Write-Host ("    [{0}] Job 이름 헤더 우측 배치" -f (_Mark $ok_jobname))
Write-Host ("    [{0}] 소스 → 타겟 좌우 카드 + 화살표" -f (_Mark $ok_dbflow))
Write-Host ("    [{0}] 소스/타겟 색상 구분 (회색/파랑)" -f (_Mark $ok_db_cards))
Write-Host ("    [{0}] 2줄 압축 (이관모드/AI/자동수정)" -f (_Mark $ok_attr_row))
Write-Host ("    [{0}] 시각 구분 (좌측 색상 띠 + 그라디언트)" -f (_Mark $ok_visual))

Write-Host ""
Write-Host "  이전 처방 보존:"
foreach ($m in @("v95_p37","v95_p25","v90.49")) {
    Write-Host ("    [{0}] {1} : {2}건" -f (_Mark ($vue.Contains($m))), $m, ([regex]::Matches($vue, [regex]::Escape($m))).Count)
}

$allOk = $ok_marker -and $ok_jobname -and $ok_dbflow -and $ok_db_cards -and $ok_attr_row -and $ok_visual

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p40 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) Frontend hot-reload (자동) 또는 Ctrl+Shift+R"
    Write-Host "  2) 위저드 Step 6 (검토 & 실행) 페이지 확인"
    Write-Host ""
    Write-Host "검증 시나리오:"
    Write-Host "  [기본 정보] 헤더 우측에 Job 이름 표시 (파랑 칩)"
    Write-Host "  ─────────────────────────────────────────────"
    Write-Host "  [소스 DB]                  →     [타겟 DB]"
    Write-Host "  mssql / AdventureWorks2022       mysql / aw_target"
    Write-Host "  ─────────────────────────────────────────────"
    Write-Host "  [이관 모드]   [AI DBA 분석]   [자동 수정]"
    Write-Host "  스키마+데이터  🟢 경제형      0건"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$VuePath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$VuePath' -Force"
    exit 2
}
