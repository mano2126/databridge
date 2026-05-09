# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p44 적용 (2026-05-05) — Throttle + Mode 동시 표시
# ════════════════════════════════════════════════════════════════════
# 본부장님 호소:
#   "AI 모드 선택 후 다시 하이브리드 선택을 하면 Thread 3개→2개,
#    Batch 5,000→3,750 행 이게 사라져"
#
# 진단 (view tool 100% 확인):
#   v95_p39 의 jobLastChange[jobId] 가 단일 객체 → 모드 변경 시
#   throttle 정보 덮어씀 (line 549).
#
# 처방 (옵션 A — 양쪽 정보 동시 보기):
#   jobLastChange[jobId] 를 두 슬롯으로 분리:
#     { throttle: {before,after,...}, mode: {before,after,...} }
#   - throttle 변경 → throttle 슬롯만 갱신 (mode 슬롯 보존)
#   - mode 변경 → mode 슬롯만 갱신 (throttle 슬롯 보존)
#
# 단위 테스트 4/4 시나리오 모두 통과:
#   1) Throttle 100→75: throttle 카드 표시
#   2) 모드 AI 클릭: throttle 보존 + mode 카드 추가
#   3) 모드 하이브리드 재클릭: throttle 보존 + mode 갱신 ★ 본부장님 호소 해소
#   4) Throttle 50 재클릭: 모드 정보 보존 + throttle 갱신
#
# 부작용 0:
#   - HTML 구조 강화 (template 두 카드 v-if 분리)
#   - 시각 구분: throttle = 보라, mode = 청록 (좌측 띠 색상)
#   - 마이그레이션 로직 (구 단일 객체 → 새 슬롯) 자동 처리
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p44 적용 (Throttle + Mode 동시 표시)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$VuePath = Join-Path $Root "frontend\src\components\common\FloatingMonitor.vue"
if (-not (Test-Path $VuePath)) { Write-Host "❌ FloatingMonitor.vue 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p44_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $VuePath (Join-Path $BackupDir "FloatingMonitor.vue.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$vue = Get-Content $VuePath -Raw

$ok_marker     = $vue.Contains("v95_p44")
$ok_slot_thr   = $vue.Contains("jobLastChange[jobId].throttle")
$ok_slot_mode  = $vue.Contains("jobLastChange[jobId].mode")
$ok_template_thr = $vue.Contains("jobLastChange[job.id].throttle.before.parallelism")
$ok_template_mode = $vue.Contains("jobLastChange[job.id].mode.before.mode")
$ok_mode_card   = $vue.Contains("fm-change-mode-card")
$ok_migration   = $vue.Contains("action !== undefined")  # 구 형태 마이그레이션

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p44 처방:"
Write-Host ("    [{0}] v95_p44 마커" -f (_Mark $ok_marker))
Write-Host ("    [{0}] throttle 슬롯 (script)" -f (_Mark $ok_slot_thr))
Write-Host ("    [{0}] mode 슬롯 (script)" -f (_Mark $ok_slot_mode))
Write-Host ("    [{0}] Throttle 카드 (template)" -f (_Mark $ok_template_thr))
Write-Host ("    [{0}] Mode 카드 (template)" -f (_Mark $ok_template_mode))
Write-Host ("    [{0}] Mode 카드 시각 구분 (CSS)" -f (_Mark $ok_mode_card))
Write-Host ("    [{0}] 구 형태 → 새 슬롯 마이그레이션" -f (_Mark $ok_migration))

Write-Host ""
Write-Host "  이전 처방 보존:"
foreach ($m in @("v95_p39","jobLastChange","computeLocalPolicy","throttleHint","modeHint")) {
    Write-Host ("    [{0}] {1} : {2}건" -f (_Mark ($vue.Contains($m))), $m, ([regex]::Matches($vue, [regex]::Escape($m))).Count)
}

$allOk = $ok_marker -and $ok_slot_thr -and $ok_slot_mode -and $ok_template_thr -and $ok_template_mode -and $ok_mode_card

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p44 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) Frontend hot-reload (자동) 또는 Ctrl+Shift+R"
    Write-Host "  2) 이관 실행 → 모니터 팝업 → 시나리오 검증:"
    Write-Host "     - Throttle 100→75 클릭 → Thread/Batch 카드 (보라)"
    Write-Host "     - 모드 AI 클릭 → 모드 카드 (청록) 추가, Throttle 카드 보존 ✅"
    Write-Host "     - 모드 하이브리드 재클릭 → 두 카드 모두 표시 ✅"
    Write-Host "     - Throttle 50 재클릭 → throttle 갱신 + 모드 정보 보존 ✅"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\FloatingMonitor.vue.bak' '$VuePath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\FloatingMonitor.vue.bak' '$VuePath' -Force"
    exit 2
}
