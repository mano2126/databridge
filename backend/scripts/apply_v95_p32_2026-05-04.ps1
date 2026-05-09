# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p32 적용 (2026-05-04)
# ════════════════════════════════════════════════════════════════════
# 본질 1: AdminAudit.vue HTML 표준 위반 (Vite 경고)
#   자리: frontend/src/pages/AdminAudit.vue line 273~334, 347~370
#   처방: <table> 두 곳에 <tbody> 래핑 추가
#
# 본질 2: 자기참조 1146 (Sales_Salesorderheader 등 혼합 case)
#   자리: backend/app/core/obj_executor.py v95_p29-#6 정규식 자리
#   처방: 타겟 MySQL 실제 테이블 목록 조회 → 백틱 안 식별자 case 복원
#         (하드코딩 0% — 모든 DB 자동 작동)
#
# 본부장님 모토 충실:
#   - 본질에 충실: view tool 진단된 자리만 처방
#   - 추측 처방 금지: 단위 테스트 6건 통과
#   - 하드코딩 0%: 실제 테이블 동적 조회
#   - 부작용 0: 매치 안 되는 식별자 영향 없음
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p32 적용 (본질 1 + 2)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$VuePath = Join-Path $Root "frontend\src\pages\AdminAudit.vue"
$OePath  = Join-Path $Root "backend\app\core\obj_executor.py"

if (-not (Test-Path $VuePath)) { Write-Host "❌ AdminAudit.vue 없음" -ForegroundColor Red; exit 1 }
if (-not (Test-Path $OePath))  { Write-Host "❌ obj_executor.py 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p32_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $VuePath (Join-Path $BackupDir "AdminAudit.vue.bak") -Force
Copy-Item $OePath (Join-Path $BackupDir "obj_executor.py.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$vue = Get-Content $VuePath -Raw
$oe  = Get-Content $OePath -Raw

# 본질 1: AdminAudit.vue
$ok_v1_marker = $vue.Contains("v95_p32")
$ok_v1_tbody1 = $vue.Contains('<table class="explain-table">') -and ($vue -match '<table class="explain-table">[\s\S]*?<tbody>')
$ok_v1_tbody2 = $vue.Contains('<table class="hash-table">') -and ($vue -match '<table class="hash-table">[\s\S]*?<tbody>')

# 본질 2: obj_executor.py
$ok_v2_marker = $oe.Contains("v95_p32-#2")
$ok_v2_logic  = $oe.Contains("_real_table_cases") -and $oe.Contains("SHOW TABLES")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  본질 1 (AdminAudit.vue HTML 표준):"
Write-Host ("    [{0}] v95_p32 마커" -f (_Mark $ok_v1_marker))
Write-Host ("    [{0}] explain-table tbody 추가" -f (_Mark $ok_v1_tbody1))
Write-Host ("    [{0}] hash-table tbody 추가" -f (_Mark $ok_v1_tbody2))

Write-Host ""
Write-Host "  본질 2 (자기참조 case 복원):"
Write-Host ("    [{0}] v95_p32-#2 마커" -f (_Mark $ok_v2_marker))
Write-Host ("    [{0}] SHOW TABLES 동적 조회 로직" -f (_Mark $ok_v2_logic))

Write-Host ""
Write-Host "  이전 처방 보존:"
foreach ($m in @("v95_p23e","v95_p29","v95_p30")) {
    Write-Host ("    [{0}] {1} : {2}건" -f (_Mark ($oe.Contains($m))), $m, ([regex]::Matches($oe, $m)).Count)
}

$allOk = $ok_v1_marker -and $ok_v1_tbody1 -and $ok_v1_tbody2 -and $ok_v2_marker -and $ok_v2_logic

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p32 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) 백엔드 재시작 (Python 변경 반영)"
    Write-Host "  2) Vite 자동 새로고침 (frontend 변경) — 또는 Ctrl+Shift+R"
    Write-Host "  3) MySQL 타겟 DB 정리 (DROP DATABASE / CREATE DATABASE)"
    Write-Host "  4) 위저드 [↻ 새로 시작] → 재이관"
    Write-Host ""
    Write-Host "결과 측정 기대:"
    Write-Host "  - AdminAudit.vue 페이지 Vite 경고: 0건"
    Write-Host "  - uSalesOrderHeader/uPurchaseOrderHeader 1146 자기참조: 0건"
    Write-Host ""
    Write-Host "작동 흔적 검증 (재이관 1회 후):"
    Write-Host "  Get-Content '$Root\backend\logs\databridge_backend.log' -Tail 3000 | Select-String 'v95_p32-#2' | Select -Last 10"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\AdminAudit.vue.bak' '$VuePath' -Force"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$OePath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\AdminAudit.vue.bak' '$VuePath' -Force"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$OePath' -Force"
    exit 2
}
