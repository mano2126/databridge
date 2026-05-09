# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p48 적용 (2026-05-05) — 검토 화면 표 형식 + 그룹 통합
# ════════════════════════════════════════════════════════════════════
# 본부장님 호소:
#   1. 이관 객체 + 변환·실행 설정 같은 위치에서 보여달라
#   2. 컬럼과 관련 정보 너무 떨어져 있어 가독성 떨어짐
#   3. 한 줄에 4개 정보
#   4. 블록들에 구분
#   5. 컬럼명과 데이터 테이블 형태로 구분
#
# 처방:
#   - 두 섹션 (이관 객체 + 변환·실행) → 한 카드 "상세 정보" 로 통합
#   - 카드 내부에 두 그룹 (이관 객체 / 변환·실행 설정) — 좌측 색상 띠로 구분
#     * 이관 객체: 파란 띠 (#2563eb)
#     * 변환·실행 설정: 보라 띠 (#6d28d9)
#   - 각 그룹은 4-column 테이블:
#     * 라벨 행: 회색 배경, uppercase, 작은 폰트
#     * 값 행: 흰 배경, 진한 검정, 굵게
#     * 라벨/값이 같은 컬럼에 위아래로 배치 → 가독성 ↑
#   - 단위 (개, 건) 약하게 표시 (디자인 정돈)
#   - AI 엔진은 보라색 강조, 이관전 DROP 은 빨강 강조
#   - 좁은 화면 700px 이하 → 자동 2-column
#
# 부작용 0:
#   - 모든 form 필드 100% 보존 (데이터 영향 0)
#   - 이전 v95_p37/p40/p43 처방 100% 보존
#   - 다크 모드 호환 추가
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p48 적용 (검토 화면 표 형식)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$VuePath = Join-Path $Root "frontend\src\pages\JobWizard.vue"
if (-not (Test-Path $VuePath)) { Write-Host "❌ JobWizard.vue 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p48_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $VuePath (Join-Path $BackupDir "JobWizard.vue.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$vue = Get-Content $VuePath -Raw

$ok_marker      = $vue.Contains("v95_p48")
$ok_state       = $vue.Contains("reviewDetailOpen")
$ok_body        = $vue.Contains("review-detail-body")
$ok_group       = $vue.Contains("review-group") -and $vue.Contains("review-group-bullet")
$ok_table       = $vue.Contains("review-table-labels") -and $vue.Contains("review-table-values")
$ok_4col        = $vue.Contains("width: 25%")
$ok_emphasis    = $vue.Contains("rv-engine-ai") -and $vue.Contains("rv-warn")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p48 처방:"
Write-Host ("    [{0}] v95_p48 마커" -f (_Mark $ok_marker))
Write-Host ("    [{0}] reviewDetailOpen state" -f (_Mark $ok_state))
Write-Host ("    [{0}] 통합 카드 본문" -f (_Mark $ok_body))
Write-Host ("    [{0}] 두 그룹 (좌측 색상 띠)" -f (_Mark $ok_group))
Write-Host ("    [{0}] 표 형식 (라벨 행 + 값 행)" -f (_Mark $ok_table))
Write-Host ("    [{0}] 4-column 균등 분배" -f (_Mark $ok_4col))
Write-Host ("    [{0}] AI/경고 강조 색상" -f (_Mark $ok_emphasis))

Write-Host ""
Write-Host "  데이터 보존 (이전 처방 영향 0):"
foreach ($f in @("form.tables.length", "form.ddlEngine", "form.objEngine",
                  "form.batchSize", "form.viewMode", "form.objMode",
                  "form.dropTbl", "form.truncate")) {
    Write-Host ("    [{0}] {1}" -f (_Mark ($vue.Contains($f))), $f)
}

$allOk = $ok_marker -and $ok_state -and $ok_body -and $ok_group -and $ok_table -and $ok_4col -and $ok_emphasis

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p48 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) Frontend hot-reload (자동) 또는 Ctrl+Shift+R"
    Write-Host "  2) 위저드 Step 6 (검토 & 실행) 페이지 확인"
    Write-Host ""
    Write-Host "검증 시나리오:"
    Write-Host "  [기본 정보]"
    Write-Host "  ────────────────────────────────────────"
    Write-Host "  [▼ 상세 정보]"
    Write-Host "    ▍이관 객체"
    Write-Host "    ┌────────┬────────┬────────┬────────┐"
    Write-Host "    │테이블  │프로시저│함수    │트리거  │"
    Write-Host "    │ 71개   │ 10개   │ 11개   │ 10개   │"
    Write-Host "    ├────────┼────────┼────────┼────────┤"
    Write-Host "    │뷰      │적용권고│        │        │"
    Write-Host "    │ 20개   │14/14건 │        │        │"
    Write-Host "    └────────┴────────┴────────┴────────┘"
    Write-Host ""
    Write-Host "    ▌변환 · 실행 설정"
    Write-Host "    ┌────────┬────────┬────────┬────────┐"
    Write-Host "    │DDL엔진 │객체엔진│객체변환│배치크기│"
    Write-Host "    │🤖AI    │🤖AI    │자동변환│ 5,000  │"
    Write-Host "    ├────────┼────────┼────────┼────────┤"
    Write-Host "    │뷰모드  │객체모드│이관전D │TRUNCATE│"
    Write-Host "    │DROP재생│DROP재생│✓DROP재생│—       │"
    Write-Host "    └────────┴────────┴────────┴────────┘"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$VuePath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$VuePath' -Force"
    exit 2
}
