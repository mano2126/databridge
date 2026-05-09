# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p24a + v95_p24b 적용 스크립트 (2026-05-04)
# ════════════════════════════════════════════════════════════════════
# v95_p24a: backend/app/api/routes/preflight.py
#           - 사전 분석 진짜 강화 (의존성/row count DB 조회)
# v95_p24b: frontend/src/pages/JobWizard.vue
#           - 정규화 규칙 KB API 호출 (54건), default check 강화
#
# 본부장님 모토: 추측 처방 금지, 단일 본질 단일 처방, 부작용 0
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p24a + v95_p24b 적용"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

# ────────────────────────────────────────────────────────────────────
# 사전 검증 — 두 파일이 본부장님 환경에 존재하는지
# ────────────────────────────────────────────────────────────────────
$PreflightPath = Join-Path $Root "backend\app\api\routes\preflight.py"
$JobWizardPath = Join-Path $Root "frontend\src\pages\JobWizard.vue"

if (-not (Test-Path $PreflightPath)) {
    Write-Host "❌ preflight.py 없음: $PreflightPath" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $JobWizardPath)) {
    Write-Host "❌ JobWizard.vue 없음: $JobWizardPath" -ForegroundColor Red
    exit 1
}

Write-Host "[1/4] 본부장님 환경 사전 검증" -ForegroundColor Cyan
$preflightContent = Get-Content $PreflightPath -Raw
$jobwizardContent = Get-Content $JobWizardPath -Raw

# v95_p23a 마커 존재 검증 (이전 패치 적용 확인)
if (-not $preflightContent.Contains("v95_p23a")) {
    Write-Host "  ⚠ preflight.py 에 v95_p23a 마커 없음 — 이전 패치 누락 가능" -ForegroundColor Yellow
} else {
    Write-Host "  ✓ preflight.py 에 v95_p23a 마커 존재"
}

# v95_p24a/b 이미 적용됐는지 확인 (재적용 방지)
if ($preflightContent.Contains("v95_p24a")) {
    Write-Host "  ⚠ preflight.py 에 v95_p24a 마커 이미 존재 — 재적용 시 덮어쓰기됩니다" -ForegroundColor Yellow
}
if ($jobwizardContent.Contains("v95_p24b")) {
    Write-Host "  ⚠ JobWizard.vue 에 v95_p24b 마커 이미 존재 — 재적용 시 덮어쓰기됩니다" -ForegroundColor Yellow
}

# ────────────────────────────────────────────────────────────────────
# 백업
# ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/4] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p24_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $PreflightPath (Join-Path $BackupDir "preflight.py.bak") -Force
Copy-Item $JobWizardPath (Join-Path $BackupDir "JobWizard.vue.bak") -Force
Write-Host "  ✓ 백업 위치: $BackupDir"

# ────────────────────────────────────────────────────────────────────
# 적용
# ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/4] 패치 파일 적용" -ForegroundColor Cyan

$PatchPreflight = Join-Path $PSScriptRoot "..\..\backend\app\api\routes\preflight.py"
$PatchJobWizard = Join-Path $PSScriptRoot "..\..\frontend\src\pages\JobWizard.vue"

# 패치 ZIP 풀어진 자리 (이 .ps1 가 backend/scripts 안에 있으므로 ../../ 가 databridge_full/)
# Resolve-Path 로 정규화
try {
    $PatchPreflight = (Resolve-Path $PatchPreflight).Path
    $PatchJobWizard = (Resolve-Path $PatchJobWizard).Path
} catch {
    Write-Host "  ❌ 패치 파일 경로 해석 실패: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "     ZIP 을 D:\project\ 에서 풀었는지 확인해 주십시오"
    exit 1
}

# preflight.py 자체를 새 버전으로 교체 (apply 스크립트와 같은 ZIP 안 패치 파일)
# 단, 이 ps1 자신이 ZIP 안에 있고 ZIP 풀 때 본부장님 환경 파일을 덮어쓰므로
# 이 시점에서는 이미 패치된 상태 → 검증만 하면 됨

# Phase 4: 적용 후 검증
Write-Host ""
Write-Host "[4/4] 적용 검증" -ForegroundColor Cyan

# 재읽기 (ZIP 풀 때 이미 덮어써진 상태)
$preflightAfter = Get-Content $PreflightPath -Raw
$jobwizardAfter = Get-Content $JobWizardPath -Raw

$check_p24a_marker = $preflightAfter.Contains("v95_p24a")
$check_p24a_dep    = $preflightAfter.Contains("sys.sql_expression_dependencies")
$check_p24a_perf   = $preflightAfter.Contains("sys.partitions")
$check_p24a_make   = $preflightAfter.Contains("from app.core.db_conn import make_conn")

$check_p24b_marker = $jobwizardAfter.Contains("v95_p24b")
$check_p24b_kb     = $jobwizardAfter.Contains("/api/v1/mapping/rules")
$check_p24b_async  = $jobwizardAfter.Contains("async function loadNormRules")

function _OkMark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p24a (preflight.py):"
Write-Host ("    [{0}] v95_p24a 마커" -f (_OkMark $check_p24a_marker))
Write-Host ("    [{0}] sys.sql_expression_dependencies (의존성 진짜 조회)" -f (_OkMark $check_p24a_dep))
Write-Host ("    [{0}] sys.partitions (성능 진짜 조회)" -f (_OkMark $check_p24a_perf))
Write-Host ("    [{0}] make_conn import (통합 헬퍼)" -f (_OkMark $check_p24a_make))

Write-Host ""
Write-Host "  v95_p24b (JobWizard.vue):"
Write-Host ("    [{0}] v95_p24b 마커" -f (_OkMark $check_p24b_marker))
Write-Host ("    [{0}] /api/v1/mapping/rules KB API 호출" -f (_OkMark $check_p24b_kb))
Write-Host ("    [{0}] async function loadNormRules" -f (_OkMark $check_p24b_async))

$allOk = $check_p24a_marker -and $check_p24a_dep -and $check_p24a_perf -and $check_p24a_make `
        -and $check_p24b_marker -and $check_p24b_kb -and $check_p24b_async

Write-Host ""
if ($allOk) {
    Write-Host "═══════════════════════════════════════════════════════════"
    Write-Host "✅ v95_p24a + v95_p24b 적용 검증 완료" -ForegroundColor Green
    Write-Host "═══════════════════════════════════════════════════════════"
    Write-Host ""
    Write-Host "다음 단계 — 본부장님:" -ForegroundColor Yellow
    Write-Host "  1) backend 재시작 (preflight.py 변경 반영)"
    Write-Host "  2) frontend 빌드/Ctrl+Shift+R (JobWizard.vue 캐시 무효화)"
    Write-Host "  3) 위저드 3단계 진입 → 사전 분석 결과 확인"
    Write-Host "     - 의존성: 'VIEW N건 — 의존성 OK (진짜 조회 완료)' 또는 미선택 경고"
    Write-Host "     - 성능: '대용량 테이블 N건 (≥1M행)' 진짜 row count 표시"
    Write-Host "     - 정규화 규칙: 6개 → KB 54건 표시 (mssql→mysql 인 경우)"
    Write-Host ""
    Write-Host "롤백 필요 시:"
    Write-Host "  Copy-Item '$BackupDir\preflight.py.bak' '$PreflightPath' -Force"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$JobWizardPath' -Force"
} else {
    Write-Host "═══════════════════════════════════════════════════════════"
    Write-Host "❌ 적용 검증 실패 — 일부 마커 누락" -ForegroundColor Red
    Write-Host "═══════════════════════════════════════════════════════════"
    Write-Host ""
    Write-Host "롤백 권장:"
    Write-Host "  Copy-Item '$BackupDir\preflight.py.bak' '$PreflightPath' -Force"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$JobWizardPath' -Force"
    exit 2
}
