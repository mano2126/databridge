# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p47 적용 (2026-05-05) — JobMonitor 진행률 + 객체 진행바
# ════════════════════════════════════════════════════════════════════
# 본부장님 호소 4가지:
#   1. 테이블 71/71 완료인데 99.9% — 100% 가 맞다
#   2. 스테이터스바 따로 만들어 객체 진행 보여달라
#   3. 객체는 시간 말고 단순 상태바
#   4. 'ƒ함수 11/11 ⚙SP 10/10 👁View 19/20 ⚡트리거 0/10 ⟳' 한 줄로
#
# 진단 (view tool 100% 확인):
#   - effectiveProgress 가 backend safeProgress 그대로 사용 → 99.9% 잔류
#   - 객체 진행은 카운트만 표시, 진행바 없음
#   - kpi-obj-row 가 flex-wrap: wrap → 두 줄
#
# 처방:
#   1) effectiveProgress 보강:
#      - 테이블 모두 완료 시 100% 강제 (객체 단계 무관)
#      - 전체 진행 = 테이블 단계 명확 분리
#   2) objectsOverallProgress computed 신규:
#      - (done + failed) / total * 100
#      - 별도 진행바 표시
#   3) Template:
#      - 테이블 진행바 + sub 텍스트
#      - 구분선
#      - 객체 변환 라벨 + 진행바 (단순 상태바, 시간 X)
#      - FN/SP/VW/TR 한 줄 (compact, 균등 분배)
#   4) CSS:
#      - kpi-obj-row-compact: flex-wrap: nowrap (한 줄 강제)
#      - kpi-obj-item-compact: flex 1 1 0 (균등 분배)
#      - 폰트 9.5px (한 줄 들어가게)
#      - 객체 진행바: 파랑/초록(완료)/주황(실패) 그라디언트
#
# 부작용 0:
#   - 기존 kpi-obj-row 클래스 보존 (호환)
#   - 객체 카운트 데이터 구조 그대로 (objectsProgress)
#   - 테이블 진행바/sub 텍스트 그대로
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p47 적용 (JobMonitor 진행률 현실화)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$VuePath = Join-Path $Root "frontend\src\pages\JobMonitor.vue"
if (-not (Test-Path $VuePath)) { Write-Host "❌ JobMonitor.vue 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p47_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $VuePath (Join-Path $BackupDir "JobMonitor.vue.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$vue = Get-Content $VuePath -Raw

$ok_marker      = $vue.Contains("v95_p47")
$ok_100_force   = $vue.Contains("return 100")
$ok_obj_overall = $vue.Contains("objectsOverallProgress")
$ok_prog_track  = $vue.Contains("kpi-obj-prog-track")
$ok_compact_row = $vue.Contains("kpi-obj-row-compact")
$ok_nowrap      = $vue.Contains("flex-wrap: nowrap")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p47 처방:"
Write-Host ("    [{0}] v95_p47 마커" -f (_Mark $ok_marker))
Write-Host ("    [{0}] 테이블 100% 강제" -f (_Mark $ok_100_force))
Write-Host ("    [{0}] 객체 진행률 computed" -f (_Mark $ok_obj_overall))
Write-Host ("    [{0}] 객체 진행바 (kpi-obj-prog-track)" -f (_Mark $ok_prog_track))
Write-Host ("    [{0}] 한 줄 compact 행" -f (_Mark $ok_compact_row))
Write-Host ("    [{0}] flex-wrap nowrap (한 줄 강제)" -f (_Mark $ok_nowrap))

$allOk = $ok_marker -and $ok_100_force -and $ok_obj_overall -and $ok_prog_track -and $ok_compact_row -and $ok_nowrap

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p47 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) Frontend hot-reload (자동) 또는 Ctrl+Shift+R"
    Write-Host "  2) 이관 작업 모니터 화면 확인"
    Write-Host ""
    Write-Host "검증 시나리오:"
    Write-Host "  [전체 진행] 100%  ← 테이블 71/71 완료 시 ✅"
    Write-Host "  ──────────────────"
    Write-Host "  테이블 71 / 71 완료"
    Write-Host "  ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ "
    Write-Host "  객체 변환                  27.5%   ← 별도 진행바 ✅"
    Write-Host "  [████████░░░░░░░░░░░░░░░░░░]"
    Write-Host "  [ƒ FN 11/11] [⚙ SP 10/10] [👁 VW 0/20] [⚡ TR 0/10]   ← 한 줄 ✅"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobMonitor.vue.bak' '$VuePath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobMonitor.vue.bak' '$VuePath' -Force"
    exit 2
}
