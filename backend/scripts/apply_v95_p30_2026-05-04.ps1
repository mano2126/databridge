# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p30 적용 (2026-05-04)
# ════════════════════════════════════════════════════════════════════
# 잔여 본질 2건 처방 (4건 중 2건):
#
#   잔여 1: Document/ProductPhoto 'KeyError: Production_Document'
#     자리: migration_engine.py:3455 self._hier_cols[table].add(_col_name)
#     처방: setdefault 로 안전 초기화 (line 3370 과 동일 패턴)
#
#   잔여 3: uSalesOrderHeader/uPurchaseOrderHeader 1362
#     자리: obj_executor.py:1633 v95_p29 _pattern_set_new
#     처방: NEW row 수정 패턴 정규식 확장
#           - SET NEW.col (기존)
#           - UPDATE table SET ... NEW.col (본부장님 환경 진짜 패턴)
#           - NEW.col := expr (드문 변형)
#
# 잔여 본질 2 (vProductModelInstructions _Flat 환각) — v95_p30 제외
#   AI 환각 본질, 추가 진단 필요 (별도 처방)
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p30 적용 (잔여 본질 2건)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$MePath = Join-Path $Root "backend\app\engine\migration_engine.py"
$OePath = Join-Path $Root "backend\app\core\obj_executor.py"

if (-not (Test-Path $MePath)) {
    Write-Host "❌ migration_engine.py 없음" -ForegroundColor Red; exit 1
}
if (-not (Test-Path $OePath)) {
    Write-Host "❌ obj_executor.py 없음" -ForegroundColor Red; exit 1
}

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p30_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $MePath (Join-Path $BackupDir "migration_engine.py.bak") -Force
Copy-Item $OePath (Join-Path $BackupDir "obj_executor.py.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 적용 검증 (ZIP 압축 해제 시 이미 덮어써짐)
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$me = Get-Content $MePath -Raw
$oe = Get-Content $OePath -Raw

# v95_p30 본질 1
$ok_30_me     = $me.Contains("v95_p30")
$ok_30_setdef = $me.Contains("setdefault(table, set()).add(_col_name)") `
              -and $me.Contains("KeyError 방지")

# v95_p30 본질 3
$ok_30_oe     = $oe.Contains("v95_p30")
$ok_30_pattern = $oe.Contains("_pattern_new_row_modify")
$ok_30_v5_log = $oe.Contains("[v95_p30-#5] AFTER\u2192BEFORE \ubcc0\ud658") -or `
                $oe.Contains("v95_p30-#5") # 한글 인코딩 회피
function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p30 본질 1 (KeyError 방지):"
Write-Host ("    [{0}] migration_engine.py 마커" -f (_Mark $ok_30_me))
Write-Host ("    [{0}] setdefault 처방 적용" -f (_Mark $ok_30_setdef))

Write-Host ""
Write-Host "  v95_p30 본질 3 (NEW row 패턴 확장):"
Write-Host ("    [{0}] obj_executor.py 마커" -f (_Mark $ok_30_oe))
Write-Host ("    [{0}] _pattern_new_row_modify 정의" -f (_Mark $ok_30_pattern))
Write-Host ("    [{0}] v95_p30-#5 로그 마커" -f (_Mark $ok_30_v5_log))

# 이전 처방 보존 검증 (v95_p23~p29)
Write-Host ""
Write-Host "  이전 처방 보존 (v95_p23~p29):"
foreach ($m in @("v95_p23a","v95_p23b","v95_p23e","v95_p23f","v95_p26","v95_p27","v95_p28","v95_p29")) {
    $exists = $me.Contains($m) -or $oe.Contains($m)
    Write-Host ("    [{0}] {1}" -f (_Mark $exists), $m)
}

$allOk = $ok_30_me -and $ok_30_setdef -and $ok_30_oe -and $ok_30_pattern

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p30 적용 검증 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) 백엔드 재시작"
    Write-Host "  2) MySQL 타겟 DB 정리 (DROP DATABASE / CREATE DATABASE)"
    Write-Host "  3) 위저드에서 [↻ 새로 시작] 후 재이관"
    Write-Host "  4) 결과 측정:"
    Write-Host "     - Document, ProductPhoto: 'KeyError' 에러 0건 기대"
    Write-Host "     - uSalesOrderHeader, uPurchaseOrderHeader 1362: 0건 기대"
    Write-Host ""
    Write-Host "잔여 본질 (별도 처방 예정):"
    Write-Host "  - vProductModelInstructions (_Flat 환각) — Phase 1 에 포함 가능"
    Write-Host ""
    Write-Host "작동 흔적 검증 (재이관 1회 후):"
    Write-Host "  Get-Content '$Root\backend\logs\databridge_backend.log' -Tail 5000 | Select-String 'v95_p30' | Select -Last 30"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\migration_engine.py.bak' '$MePath' -Force"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$OePath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패 — 일부 마커 누락" -ForegroundColor Red
    Write-Host ""
    Write-Host "롤백 권장:"
    Write-Host "  Copy-Item '$BackupDir\migration_engine.py.bak' '$MePath' -Force"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$OePath' -Force"
    exit 2
}
