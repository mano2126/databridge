# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p54 적용 (2026-05-05) — 변환·실행 6칸 통일 + 구분선
# ════════════════════════════════════════════════════════════════════
# 본부장님 호소:
#   1. 변환·실행 설정 한 줄로 — 이관 객체와 통일
#   2. 컬럼간 구분선 선명하게
#
# 처방:
#   - 변환·실행 설정 표 6칸 통일 (이관 객체와 동일):
#     [배치 크기][뷰 모드][객체 모드][객체 변환][이관전 DROP][TRUNCATE]
#     - 항목 없을 때 "—" 표시 (구조 안정)
#     - 두 표 (4칸 + 객체 모드 표) → 한 표 (6칸)로 통합
#   - 컬럼간 구분선 강화:
#     * 라이트: 1px dashed rgba(0,0,0,0.05) → 1px solid rgba(0,0,0,0.12)
#     * 다크: rgba(255,255,255,0.06) → 0.15
#     * 라벨/값 사이: rgba(37,99,235,0.12) → 0.30 (선명)
#
# 부작용 0:
#   - 모든 form 필드 100% 보존
#   - v95_p48/p50/p52 그룹/색상 띠/5칸 그대로
#   - 데이터 영향 0
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p54 적용 (변환·실행 6칸 + 구분선 선명)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$VuePath = Join-Path $Root "frontend\src\pages\JobWizard.vue"
if (-not (Test-Path $VuePath)) { Write-Host "❌ JobWizard.vue 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p54_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $VuePath (Join-Path $BackupDir "JobWizard.vue.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증 (UTF-8 명시)
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$vue = [System.IO.File]::ReadAllText($VuePath, [System.Text.UTF8Encoding]::new($false))

$ok_marker      = $vue.Contains("v95_p54")
$ok_6col_unify  = $vue -match "변환 · 실행 설정 \(v95_p54: 6칸 한 줄"
$ok_solid_div   = $vue.Contains("border-right: 1px solid rgba(0,0,0,0.12)")
$ok_label_div   = $vue.Contains("rgba(37, 99, 235, 0.30)")
$ok_dark_div    = $vue.Contains("rgba(255,255,255,0.15)")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p54 처방:"
Write-Host ("    [{0}] v95_p54 마커" -f (_Mark $ok_marker))
Write-Host ("    [{0}] 변환·실행 6칸 통일" -f (_Mark $ok_6col_unify))
Write-Host ("    [{0}] 컬럼간 구분선 선명 (solid 0.12)" -f (_Mark $ok_solid_div))
Write-Host ("    [{0}] 라벨/값 구분선 선명 (파란 0.30)" -f (_Mark $ok_label_div))
Write-Host ("    [{0}] 다크 모드 구분선 선명 (0.15)" -f (_Mark $ok_dark_div))

Write-Host ""
Write-Host "  데이터 보존 (form 필드):"
foreach ($f in @("form.batchSize", "form.viewMode", "form.objMode",
                  "form.dropTbl", "form.truncate", "form.convertObjs",
                  "form.procedures.length", "form.functions.length",
                  "form.triggers.length", "form.views.length")) {
    Write-Host ("    [{0}] {1}" -f (_Mark ($vue.Contains($f))), $f)
}

$allOk = $ok_marker -and $ok_6col_unify -and $ok_solid_div -and $ok_label_div -and $ok_dark_div

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p54 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) Frontend hot-reload (자동) 또는 Ctrl+Shift+R"
    Write-Host "  2) 위저드 Step 6 (검토 & 실행) 페이지 확인"
    Write-Host ""
    Write-Host "검증 시나리오:"
    Write-Host "  [▼ 상세 정보]"
    Write-Host "    ▍이관 객체 (6칸 한 줄)"
    Write-Host "    ┌─────┬─────┬─────┬─────┬─────┬─────┐"
    Write-Host "    │테이블│프로시저│함수 │트리거│뷰   │적용권고│"
    Write-Host "    ╞═════╪═════╪═════╪═════╪═════╪═════╡   ← 선명한 파란선"
    Write-Host "    │71개 │10개 │11개 │10개 │20개 │14/14│"
    Write-Host "    └─────┴─────┴─────┴─────┴─────┴─────┘   ← 컬럼간 선명"
    Write-Host ""
    Write-Host "    ▌변환 · 실행 설정 (6칸 한 줄 통일 ✅)"
    Write-Host "    ┌─────┬─────┬─────┬─────┬─────┬─────┐"
    Write-Host "    │배치 │뷰   │객체 │객체 │이관전│TRUNC│"
    Write-Host "    │크기 │모드 │모드 │변환 │DROP │     │"
    Write-Host "    ╞═════╪═════╪═════╪═════╪═════╪═════╡"
    Write-Host "    │5,000│DROP │DROP │자동 │✓DROP│—    │"
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
