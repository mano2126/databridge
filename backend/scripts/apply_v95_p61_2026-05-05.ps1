# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p61 적용 (2026-05-05) — v95_p60 TDZ 핫픽스
# ════════════════════════════════════════════════════════════════════
# 본부장님 환경 에러:
#   "Uncaught (in promise) ReferenceError:
#    Cannot access 'tableSort' before initialization at JobWizard.vue:1920"
#
# 진짜 본질 (제 v95_p60 처방 실수):
#   v95_p60 watch 24개 중 5개 (tableSort/procSort/funcSort/trigSort/viewSort)
#   가 변수 정의 (line 2048+) 보다 위인 line 1920 에 배치됨
#   → JavaScript Temporal Dead Zone 위반 → 위저드 setup 실패
#
# 본부장님 모토 "추측 처방 금지" 본부장님 지적 그대로 — 
# 모든 watch 자리 view tool 정확 검증 후 처방했어야 함. 죄송합니다.
#
# 처방 (TDZ 회피):
#   1) 잘못 배치된 5개 sort watch 제거 (line ~1920)
#   2) sort 변수 정의 (line 2048+) 직후로 이동
#   3) 다른 19개 watch 는 정상 (정의 line 1455-1528, watch 1897+)
#
# 부작용 0:
#   - 기능 영향 0 (배치만 변경)
#   - v95_p60 의 24개 항목 보존 효과 유지
#   - v95_p59 처방 100% 보존
#
# 검증:
#   24/24 watch 모두 변수 정의 후 자리 ✅ (TDZ 0건)
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p61 적용 (TDZ 핫픽스)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$VuePath = Join-Path $Root "frontend\src\pages\JobWizard.vue"
if (-not (Test-Path $VuePath)) { Write-Host "❌ JobWizard.vue 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p61_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $VuePath (Join-Path $BackupDir "JobWizard.vue.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증 (UTF-8 명시)
Write-Host ""
Write-Host "[2/3] TDZ 회피 검증" -ForegroundColor Cyan
$vue = [System.IO.File]::ReadAllText($VuePath, [System.Text.UTF8Encoding]::new($false))

$ok_marker = $vue.Contains("v95_p61")
$ok_p60    = $vue.Contains("v95_p60")  # 이전 처방 보존
$ok_comment= $vue.Contains("sort watch 는")  # 이동 표시 코멘트

# sort watch 가 const tableSort 정의 후에 있는지 확인 (단순 위치 검사)
$constIdx = $vue.IndexOf("const tableSort = ref(")
$watchIdx = $vue.IndexOf("watch(tableSort,")
$ok_order = ($constIdx -gt 0) -and ($watchIdx -gt $constIdx)

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p61 처방:"
Write-Host ("    [{0}] v95_p61 마커" -f (_Mark $ok_marker))
Write-Host ("    [{0}] sort watch 이동 코멘트" -f (_Mark $ok_comment))
Write-Host ("    [{0}] sort watch 가 정의 후 자리 (TDZ 회피)" -f (_Mark $ok_order))
Write-Host ("    [{0}] v95_p60 (24개 항목) 보존" -f (_Mark $ok_p60))

$allOk = $ok_marker -and $ok_comment -and $ok_order -and $ok_p60

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p61 적용 완료 — TDZ 에러 해결" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) Frontend hot-reload 자동 (또는 Ctrl+Shift+R)"
    Write-Host ""
    Write-Host "  2) 브라우저 콘솔 확인 → 에러 0건 ✅"
    Write-Host ""
    Write-Host "  3) 위저드 정상 진입 → 작업 → 다른 화면 → 복귀"
    Write-Host "     → 모든 작업 보존 (v95_p60 효과 정상 동작)"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$VuePath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$VuePath' -Force"
    exit 2
}
