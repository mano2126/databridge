# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p37 적용 (2026-05-05)
# ════════════════════════════════════════════════════════════════════
# 본부장님 호소 (이미지 진단):
#   "사전 분석 카드 가독성 떨어짐 — 좌측 리스트 + 우측 상세로"
#   "내부 패치 메시지 (v95_p23a 본질 #2 등) 담당자에게 무관 — 제거"
#   "타입 정규화 56개 모두 펼쳐짐 — 적용 11개 먼저, 미적용 45개 접힘"
#
# 처방 (단일 본질 단일 처방):
#   본질 1: 사전 분석 카드 좌-우 마스터-디테일 + sort 토글
#     자리: frontend/src/pages/JobWizard.vue
#     - 좌측: 간략 리스트 (위험도/카테고리/영향순 정렬 가능)
#     - 우측: 클릭한 항목 상세 (영향 객체 10개 표시 + 더보기 토글)
#     - 모바일: 세로 스택 자동 (반응형)
#
#   본질 2: 타입 정규화 적용/미적용 그룹 분리
#     자리: frontend/src/pages/JobWizard.vue
#     - 적용 11개 먼저 펼쳐짐 (녹색 그룹 라벨)
#     - 미적용 45개 기본 접힘 (클릭 시 펼침)
#
#   본질 3: 사용자 메시지 정리
#     자리: backend/app/api/routes/preflight.py
#     - "v95_p23a 본질 #2" 등 내부 패치 코드 모두 제거
#     - "자동 처리됨 — XXX (담당자 조치 불필요)" 형태 통일
#     - 5개 메시지 정리 (Deadlock/FUNC/PROC/의존성/대용량)
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p37 적용 (UI + 메시지 정리)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$VuePath = Join-Path $Root "frontend\src\pages\JobWizard.vue"
$PyPath  = Join-Path $Root "backend\app\api\routes\preflight.py"

if (-not (Test-Path $VuePath)) { Write-Host "❌ JobWizard.vue 없음" -ForegroundColor Red; exit 1 }
if (-not (Test-Path $PyPath))  { Write-Host "❌ preflight.py 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p37_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $VuePath (Join-Path $BackupDir "JobWizard.vue.bak") -Force
Copy-Item $PyPath (Join-Path $BackupDir "preflight.py.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$vue = Get-Content $VuePath -Raw
$py  = Get-Content $PyPath -Raw

$ok_v37_marker  = $vue.Contains("v95_p37")
$ok_v37_master  = $vue.Contains("pf-master-detail") -and $vue.Contains("sortedPreflightRisks")
$ok_v37_sort    = $vue.Contains("pfSortMode") -and $vue.Contains("severity")
$ok_v37_norm    = $vue.Contains("appliedNormRules") -and $vue.Contains("unappliedNormRules")
$ok_v37_more    = $vue.Contains("showAllAffected") -and $vue.Contains("pf-show-more-btn")

$ok_py_clean    = -not ($py.Contains("v95_p23a 본질 #2"))
$ok_py_friendly = $py.Contains("자동 처리됨") -and $py.Contains("담당자 조치 불필요")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  본질 1 (사전 분석 마스터-디테일):"
Write-Host ("    [{0}] v95_p37 마커" -f (_Mark $ok_v37_marker))
Write-Host ("    [{0}] 좌-우 마스터-디테일 레이아웃" -f (_Mark $ok_v37_master))
Write-Host ("    [{0}] sort 토글 (위험도/카테고리/영향순)" -f (_Mark $ok_v37_sort))
Write-Host ("    [{0}] 영향 객체 더보기 토글" -f (_Mark $ok_v37_more))

Write-Host ""
Write-Host "  본질 2 (타입 정규화 그룹 분리):"
Write-Host ("    [{0}] 적용/미적용 computed" -f (_Mark $ok_v37_norm))

Write-Host ""
Write-Host "  본질 3 (사용자 메시지 정리):"
Write-Host ("    [{0}] 내부 패치 코드 제거" -f (_Mark $ok_py_clean))
Write-Host ("    [{0}] 담당자 친화 메시지 ('자동 처리됨')" -f (_Mark $ok_py_friendly))

$allOk = $ok_v37_marker -and $ok_v37_master -and $ok_v37_sort -and $ok_v37_norm -and $ok_v37_more -and $ok_py_clean -and $ok_py_friendly

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p37 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) 백엔드 재시작 (preflight.py 변경 반영)"
    Write-Host "  2) Frontend 자동 hot-reload — 또는 Ctrl+Shift+R"
    Write-Host "  3) 위저드 → Step 2 (변환 규칙) 페이지에서 확인:"
    Write-Host "     - 사전 분석 완료 카드 → 좌측 리스트 클릭 → 우측 상세"
    Write-Host "     - 정렬 토글: 위험도/카테고리/영향순"
    Write-Host "     - 영향 객체 +N개 더 보기 버튼"
    Write-Host "     - 타입 정규화: 적용 N개 먼저, 미적용 M개 접힘"
    Write-Host "     - '자동 처리됨 (담당자 조치 불필요)' 메시지"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$VuePath' -Force"
    Write-Host "  Copy-Item '$BackupDir\preflight.py.bak' '$PyPath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$VuePath' -Force"
    Write-Host "  Copy-Item '$BackupDir\preflight.py.bak' '$PyPath' -Force"
    exit 2
}
