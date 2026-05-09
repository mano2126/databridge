# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p52 적용 (2026-05-05) — DDL/객체 엔진 기본 정보 합침
# ════════════════════════════════════════════════════════════════════
# 본부장님 호소:
#   "DDL 엔진 / 객체 엔진 두 개를 이관 모드 / AI DBA / 자동 수정 과
#    같은 1줄 라인에 놓고 보여 주자"
#
# 처방:
#   - 기본 정보 카드: 3칸 → 5칸 한 줄
#     [이관 모드] [AI DBA] [자동 수정] [DDL 엔진] [객체 엔진]
#   - 변환·실행 설정 표: 6칸 → 4칸 (DDL/객체 엔진 제거)
#     [배치 크기] [뷰 모드] [이관전 DROP] [TRUNCATE]
#   - 객체 모드 표: 6칸 → 4칸 정리
#
# 반응형:
#   - 1024px 이하: 5칸 → 3칸 wrap
#   - 700px 이하: 5칸 → 2칸 wrap
#
# 부작용 0:
#   - 모든 form 필드 보존 (16+ 건)
#   - 데이터/상태 영향 0
#   - v95_p48/p50 의 그룹/색상 띠 그대로
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p52 적용 (5칸 한 줄 정리)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$VuePath = Join-Path $Root "frontend\src\pages\JobWizard.vue"
if (-not (Test-Path $VuePath)) { Write-Host "❌ JobWizard.vue 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p52_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $VuePath (Join-Path $BackupDir "JobWizard.vue.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증 (UTF-8 명시 + 정확한 패턴)
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$vue = [System.IO.File]::ReadAllText($VuePath, [System.Text.UTF8Encoding]::new($false))

$ok_marker      = $vue.Contains("v95_p52")
$ok_5col_class  = $vue.Contains("review-attr-row-5col")
$ok_5col_grid   = $vue -match "grid-template-columns:\s*1fr 1fr 1fr 1fr 1fr"
$ok_ddl_basic   = $vue -match '<span class="rv-l">DDL 엔진</span>'
$ok_obj_basic   = $vue -match '<span class="rv-l">객체 엔진</span>'

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p52 처방:"
Write-Host ("    [{0}] v95_p52 마커" -f (_Mark $ok_marker))
Write-Host ("    [{0}] 5칸 클래스 (review-attr-row-5col)" -f (_Mark $ok_5col_class))
Write-Host ("    [{0}] 5칸 그리드 CSS" -f (_Mark $ok_5col_grid))
Write-Host ("    [{0}] 기본 정보 카드 — DDL 엔진" -f (_Mark $ok_ddl_basic))
Write-Host ("    [{0}] 기본 정보 카드 — 객체 엔진" -f (_Mark $ok_obj_basic))

Write-Host ""
Write-Host "  데이터 보존 (form 필드):"
foreach ($f in @("form.tableMode", "form.advisorMode", "autoFixEnabledCount",
                  "form.ddlEngine", "form.objEngine", "form.batchSize",
                  "form.viewMode", "form.dropTbl", "form.truncate")) {
    Write-Host ("    [{0}] {1}" -f (_Mark ($vue.Contains($f))), $f)
}

$allOk = $ok_marker -and $ok_5col_class -and $ok_5col_grid -and $ok_ddl_basic -and $ok_obj_basic

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p52 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) Frontend hot-reload (자동) 또는 Ctrl+Shift+R"
    Write-Host "  2) 위저드 Step 6 (검토 & 실행) 페이지 확인"
    Write-Host ""
    Write-Host "검증 시나리오:"
    Write-Host "  [기본 정보]"
    Write-Host "    소스 DB ↔ 타겟 DB"
    Write-Host "    [이관 모드] [AI DBA] [자동 수정] [DDL 엔진] [객체 엔진]   ← 5칸 한 줄 ✅"
    Write-Host ""
    Write-Host "  [▼ 상세 정보]"
    Write-Host "    ▍이관 객체 (6칸)"
    Write-Host "    ▌변환 · 실행 설정 (4칸 — DDL/객체 엔진 제거)"
    Write-Host "      [배치 크기] [뷰 모드] [이관전 DROP] [TRUNCATE]"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$VuePath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$VuePath' -Force"
    exit 2
}
