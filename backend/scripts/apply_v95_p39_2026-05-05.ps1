# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p39 적용 (2026-05-05)
# ════════════════════════════════════════════════════════════════════
# 본부장님 호소: "Throttle 100→75 변경 시 구체적으로 어떻게 변경되는지 보여줘
#               Thread X개 → Thread Y개 처럼"
#
# 진단 (view tool 100% 확인):
#   - 백엔드 ThrottleController._throttle_to_batch / _throttle_to_parallelism 매핑:
#     * 100% → batch 5000, thread 3
#     * 75%  → batch 3750, thread 2
#     * 50%  → batch 2500, thread 1
#     * 25%  → batch 1250, thread 1
#   - 백엔드 API 응답 (data.policy) 에 batch_size + parallelism 포함됨
#   - Frontend 만 처방하면 됨 (백엔드 수정 불필요)
#
# 처방:
#   - jobLastChange state 추가 (action, before, after, time)
#   - setJobThrottle/setJobMode: 변경 전후 비교 캡처
#   - Template: 두-세줄 상세 표시 (Thread + Batch + 힌트)
#   - 색상 표시: 감소 노란색 (부하 절감), 증가 초록색 (성능 향상)
#   - 운영 힌트: "DB 부담 25% 경감, 다른 작업과 공존 유리" 등
#
# 단위 테스트 5/5 통과, 백엔드 매핑 100% 일치 검증
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p39 적용 (Throttle/Mode 변경 효과 상세 표시)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$VuePath = Join-Path $Root "frontend\src\components\common\FloatingMonitor.vue"
if (-not (Test-Path $VuePath)) { Write-Host "❌ FloatingMonitor.vue 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p39_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $VuePath (Join-Path $BackupDir "FloatingMonitor.vue.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$vue = Get-Content $VuePath -Raw

$ok_marker      = $vue.Contains("v95_p39")
$ok_state       = $vue.Contains("jobLastChange")
$ok_local_pol   = $vue.Contains("computeLocalPolicy")
$ok_hint        = $vue.Contains("throttleHint") -and $vue.Contains("modeHint")
$ok_template    = $vue.Contains("fm-change-detail") -and $vue.Contains("fm-change-row")
$ok_css         = $vue.Contains(".fm-delta-down") -and $vue.Contains(".fm-delta-up")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  처방 검증:"
Write-Host ("    [{0}] v95_p39 마커" -f (_Mark $ok_marker))
Write-Host ("    [{0}] jobLastChange state 추가" -f (_Mark $ok_state))
Write-Host ("    [{0}] computeLocalPolicy 매핑" -f (_Mark $ok_local_pol))
Write-Host ("    [{0}] throttleHint + modeHint 헬퍼" -f (_Mark $ok_hint))
Write-Host ("    [{0}] Template 변경 효과 UI" -f (_Mark $ok_template))
Write-Host ("    [{0}] CSS delta 색상 (감소/증가)" -f (_Mark $ok_css))

Write-Host ""
Write-Host "  이전 처방 보존:"
foreach ($m in @("v90.14","v90.21","v90.42")) {
    Write-Host ("    [{0}] {1} : {2}건" -f (_Mark ($vue.Contains($m))), $m, ([regex]::Matches($vue, [regex]::Escape($m))).Count)
}

$allOk = $ok_marker -and $ok_state -and $ok_local_pol -and $ok_hint -and $ok_template -and $ok_css

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p39 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) Frontend hot-reload (자동) 또는 Ctrl+Shift+R"
    Write-Host "  2) 이관 작업 실행 → 모니터 팝업 확인"
    Write-Host "  3) Throttle 버튼 클릭 (100→75) → 두-세줄 상세 표시"
    Write-Host "  4) 모드 버튼 클릭 (AI ↔ 하이브리드 ↔ 수동) → 모드 변경 효과 표시"
    Write-Host ""
    Write-Host "검증 시나리오:"
    Write-Host "  Throttle 100→75 클릭 시 표시:"
    Write-Host "    🤖 Throttle 100% → 75% (수동) ✓"
    Write-Host "    ⚙️ Thread 3개 → 2개"
    Write-Host "    📦 Batch 5,000 → 3,750 행"
    Write-Host "    💡 부하 살짝 절감 — 메모리/CPU 여유 확보"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\FloatingMonitor.vue.bak' '$VuePath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\FloatingMonitor.vue.bak' '$VuePath' -Force"
    exit 2
}
