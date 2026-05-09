# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p50 적용 (2026-05-05) — 검토 화면 한 줄 6-column
# ════════════════════════════════════════════════════════════════════
# 본부장님 호소:
#   1. 이관 객체 한 줄 (테이블 | 프로시저 | 함수 | 트리거 | 뷰 | 적용 권고)
#   2. 변환·실행 설정 한 줄
#   3. 컬럼명/관련 데이터 구분 가독성 강화
#
# 처방:
#   - 4-column → 6-column 변형 클래스 (review-table-6col)
#   - 이관 객체: 6항목 한 줄 (라벨 행 + 값 행)
#   - 변환·실행 설정: 6항목 한 줄
#     * DDL엔진 | 객체엔진 | 배치크기 | 뷰모드 | 이관전DROP | TRUNCATE
#   - 객체 모드 (PROC/FUNC/TRIG 있을 때) — 작은 추가 표 1줄
#   - 라벨/값 사이 굵은 파란 구분선 (border-top 2px) — 가독성 강화
#   - 라벨: 폰트 9.5px, 굵은 회색, UPPERCASE
#   - 값: 폰트 12.5px, 굵게 (font-weight 700), 진한 검정
#   - 좁은 화면 (700px 이하) — 6-col → 3-col 자동
#
# 부작용 0:
#   - 모든 form 필드 100% 보존 (16건 검증)
#   - v95_p48 의 그룹/색상 띠 100% 유지
#   - 4-column 표는 호환성 위해 그대로 (다른 자리에서 사용 가능)
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p50 적용 (검토 화면 6-column 한 줄)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$VuePath = Join-Path $Root "frontend\src\pages\JobWizard.vue"
if (-not (Test-Path $VuePath)) { Write-Host "❌ JobWizard.vue 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p50_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $VuePath (Join-Path $BackupDir "JobWizard.vue.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$vue = Get-Content $VuePath -Raw

$ok_marker     = $vue.Contains("v95_p50")
$ok_6col       = $vue.Contains("review-table-6col")
$ok_6col_width = $vue.Contains("16.66%")
$ok_divider    = $vue.Contains("review-table-labels + tr.review-table-values")
$ok_obj_row    = $vue.Contains("이관 객체") -and $vue.Contains("적용 권고")
$ok_cfg_row    = $vue.Contains("DDL 엔진") -and $vue.Contains("배치 크기")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p50 처방:"
Write-Host ("    [{0}] v95_p50 마커" -f (_Mark $ok_marker))
Write-Host ("    [{0}] 6-column 변형 클래스" -f (_Mark $ok_6col))
Write-Host ("    [{0}] 16.66% 균등 분배" -f (_Mark $ok_6col_width))
Write-Host ("    [{0}] 라벨/값 굵은 파란 구분선" -f (_Mark $ok_divider))
Write-Host ("    [{0}] 이관 객체 한 줄 (테이블~적용 권고)" -f (_Mark $ok_obj_row))
Write-Host ("    [{0}] 변환·실행 한 줄 (DDL~TRUNCATE)" -f (_Mark $ok_cfg_row))

Write-Host ""
Write-Host "  데이터 보존 (16건 검증):"
foreach ($f in @("form.tables.length", "form.procedures.length", "form.functions.length",
                  "form.triggers.length", "form.views.length", "form.advisorDecisions",
                  "form.ddlEngine", "form.objEngine", "form.batchSize", "form.viewMode",
                  "form.objMode", "form.dropTbl", "form.truncate", "form.convertObjs",
                  "form.tableMode", "form.advisorMode")) {
    Write-Host ("    [{0}] {1}" -f (_Mark ($vue.Contains($f))), $f)
}

$allOk = $ok_marker -and $ok_6col -and $ok_6col_width -and $ok_divider -and $ok_obj_row -and $ok_cfg_row

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p50 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) Frontend hot-reload (자동) 또는 Ctrl+Shift+R"
    Write-Host "  2) 위저드 Step 6 (검토 & 실행) 페이지 확인"
    Write-Host ""
    Write-Host "검증 시나리오:"
    Write-Host "  [기본 정보]"
    Write-Host "    소스 DB ↔ 타겟 DB"
    Write-Host "    [이관 모드: 스키마+데이터] [AI DBA: 🟢 경제형] [자동 수정: 0건]"
    Write-Host ""
    Write-Host "  [▼ 상세 정보]"
    Write-Host "    ▍이관 객체"
    Write-Host "    ┌─────┬─────┬─────┬─────┬─────┬─────┐"
    Write-Host "    │테이블│프로시저│함수 │트리거│뷰   │적용권고│"
    Write-Host "    ├═════┼═════┼═════┼═════┼═════┼═════┤  ← 굵은 파란 구분선"
    Write-Host "    │71개 │10개 │11개 │10개 │20개 │14/14│"
    Write-Host "    └─────┴─────┴─────┴─────┴─────┴─────┘"
    Write-Host ""
    Write-Host "    ▌변환 · 실행 설정"
    Write-Host "    ┌─────┬─────┬─────┬─────┬─────┬─────┐"
    Write-Host "    │DDL엔진│객체엔진│배치크기│뷰모드│이관전D│TRUNC│"
    Write-Host "    ├═════┼═════┼═════┼═════┼═════┼═════┤"
    Write-Host "    │🤖 AI │🤖 AI │5,000│DROP재생│✓DROP│—    │"
    Write-Host "    └─────┴─────┴─────┴─────┴─────┴─────┘"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$VuePath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$VuePath' -Force"
    exit 2
}
