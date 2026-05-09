# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p26 ~ v95_p29 일괄 적용 스크립트 (2026-05-04)
# ════════════════════════════════════════════════════════════════════
# 본질 6건 일괄 처방:
#   v95_p26: UDT base type 진짜 해소 (1101 BLOB default → 9건 자동 해소)
#   v95_p27: TEXT 폴백 안전망 (UDT 가 base 안 풀려도 1101/1170 회피)
#   v95_p28: PK NULL 강제 NOT NULL (1171 PK NULL 에러 해소)
#   v95_p29: TRIGGER AFTER→BEFORE (1362) + 소문자 case 복원 (1146)
#
# 적용 파일:
#   - backend/app/engine/migration_engine.py (v95_p26 + v95_p27 + v95_p28)
#   - backend/app/core/obj_executor.py        (v95_p29)
#
# 본부장님 모토: 본질에 충실, 추측 처방 금지, 부작용 0
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p26 ~ v95_p29 일괄 적용 (본질 6건)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$MePath = Join-Path $Root "backend\app\engine\migration_engine.py"
$OePath = Join-Path $Root "backend\app\core\obj_executor.py"

if (-not (Test-Path $MePath)) {
    Write-Host "❌ migration_engine.py 없음: $MePath" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $OePath)) {
    Write-Host "❌ obj_executor.py 없음: $OePath" -ForegroundColor Red
    exit 1
}

# ────────────────────────────────────────────────────────────────────
# 사전 검증
# ────────────────────────────────────────────────────────────────────
Write-Host "[1/4] 본부장님 환경 사전 검증" -ForegroundColor Cyan
$me = Get-Content $MePath -Raw
$oe = Get-Content $OePath -Raw

# 이전 처방 마커 검증 (v95_p23 시리즈가 있어야 정상)
foreach ($m in @("v95_p23a","v95_p23b","v95_p23e","v95_p23f")) {
    if ($me.Contains($m) -or $oe.Contains($m)) {
        Write-Host "  ✓ $m 마커 존재"
    } else {
        Write-Host "  ⚠ $m 마커 없음 — 이전 패치 누락 가능" -ForegroundColor Yellow
    }
}

# v95_p26~29 이미 적용됐는지
foreach ($m in @("v95_p26","v95_p27","v95_p28","v95_p29")) {
    if ($me.Contains($m) -or $oe.Contains($m)) {
        Write-Host "  ⚠ $m 마커 이미 존재 — 재적용 시 ZIP 파일로 덮어쓰기됩니다" -ForegroundColor Yellow
    }
}

# ────────────────────────────────────────────────────────────────────
# 백업
# ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/4] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p26_29_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $MePath (Join-Path $BackupDir "migration_engine.py.bak") -Force
Copy-Item $OePath (Join-Path $BackupDir "obj_executor.py.bak") -Force
Write-Host "  ✓ 백업 위치: $BackupDir"

# ────────────────────────────────────────────────────────────────────
# 적용 (ZIP 풀 때 이미 덮어써짐 - 검증만)
# ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/4] 패치 적용 (ZIP 압축 해제 시 자동 덮어쓰기)" -ForegroundColor Cyan
Write-Host "  ✓ ZIP 을 D:\project\ 에서 푸시면 자동 적용됨"

# ────────────────────────────────────────────────────────────────────
# 적용 검증
# ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/4] 적용 검증" -ForegroundColor Cyan

$me_after = Get-Content $MePath -Raw
$oe_after = Get-Content $OePath -Raw

# v95_p26 검증 (UDT base type)
$ok_26_marker = $me_after.Contains("v95_p26")
$ok_26_join1  = $me_after.Contains("c.system_type_id = tp.user_type_id")
$ok_26_no_old = -not $me_after.Contains("c.user_type_id = tp.user_type_id")

# v95_p27 검증 (TEXT 폴백 안전망)
$ok_27_marker = $me_after.Contains("v95_p27")
$ok_27_safe   = $me_after.Contains('VARCHAR(255) 폴백')

# v95_p28 검증 (PK NULL)
$ok_28_marker = $me_after.Contains("v95_p28")
$ok_28_force  = $me_after.Contains("PK 컬럼 NOT NULL 강제")

# v95_p29 검증 (TRIGGER 본질 5/6)
$ok_29_marker      = $oe_after.Contains("v95_p29")
$ok_29_after_before = $oe_after.Contains("AFTER→BEFORE 변환")
$ok_29_case        = $oe_after.Contains("소문자 테이블 참조 복원")

function _OkMark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p26 (UDT base type):"
Write-Host ("    [{0}] 마커" -f (_OkMark $ok_26_marker))
Write-Host ("    [{0}] 새 JOIN (system_type_id) 적용" -f (_OkMark $ok_26_join1))
Write-Host ("    [{0}] 옛 JOIN (user_type_id=user_type_id) 제거" -f (_OkMark $ok_26_no_old))

Write-Host ""
Write-Host "  v95_p27 (TEXT 폴백 안전망):"
Write-Host ("    [{0}] 마커" -f (_OkMark $ok_27_marker))
Write-Host ("    [{0}] VARCHAR(255) 폴백 코드" -f (_OkMark $ok_27_safe))

Write-Host ""
Write-Host "  v95_p28 (PK NOT NULL 강제):"
Write-Host ("    [{0}] 마커" -f (_OkMark $ok_28_marker))
Write-Host ("    [{0}] PK 강제 코드" -f (_OkMark $ok_28_force))

Write-Host ""
Write-Host "  v95_p29 (TRIGGER 본질 5/6):"
Write-Host ("    [{0}] 마커" -f (_OkMark $ok_29_marker))
Write-Host ("    [{0}] AFTER→BEFORE 변환 코드" -f (_OkMark $ok_29_after_before))
Write-Host ("    [{0}] 소문자 case 복원 코드" -f (_OkMark $ok_29_case))

$allOk = $ok_26_marker -and $ok_26_join1 -and $ok_26_no_old `
        -and $ok_27_marker -and $ok_27_safe `
        -and $ok_28_marker -and $ok_28_force `
        -and $ok_29_marker -and $ok_29_after_before -and $ok_29_case

Write-Host ""
if ($allOk) {
    Write-Host "═══════════════════════════════════════════════════════════"
    Write-Host "✅ v95_p26 ~ v95_p29 적용 검증 완료" -ForegroundColor Green
    Write-Host "═══════════════════════════════════════════════════════════"
    Write-Host ""
    Write-Host "다음 단계 — 본부장님:" -ForegroundColor Yellow
    Write-Host "  1) 백엔드 재시작 (python 변경 반영)"
    Write-Host "  2) MySQL 타겟 DB 정리 (선택사항):"
    Write-Host "     - 이전 실패한 테이블/뷰/트리거가 부분 생성되어 있을 수 있음"
    Write-Host "     - 가능하면 새 DB 또는 DROP DATABASE / CREATE DATABASE 권장"
    Write-Host "  3) 재이관 실행 (모든 객체 재선택)"
    Write-Host "  4) 결과 확인:"
    Write-Host "     - TABLE 13건 1101/1170/1171 에러: 0건 기대"
    Write-Host "     - VIEW cascade 1146 에러: 부모 테이블 성공으로 자동 해소 기대"
    Write-Host "     - TRIG uSalesOrderHeader/uPurchaseOrderHeader 1362: 0건 기대"
    Write-Host "     - TRIG iuPerson 1146 (person_person): 0건 기대"
    Write-Host ""
    Write-Host "작동 흔적 검증 (재이관 1회 후):"
    Write-Host "  Get-Content D:\project\databridge_full\backend\logs\databridge_backend.log -Tail 5000 | Select-String 'v95_p2[6-9]' | Select -Last 20"
    Write-Host ""
    Write-Host "롤백 필요 시:"
    Write-Host "  Copy-Item '$BackupDir\migration_engine.py.bak' '$MePath' -Force"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$OePath' -Force"
} else {
    Write-Host "═══════════════════════════════════════════════════════════"
    Write-Host "❌ 적용 검증 실패 — 일부 마커 누락" -ForegroundColor Red
    Write-Host "═══════════════════════════════════════════════════════════"
    Write-Host ""
    Write-Host "롤백 권장:"
    Write-Host "  Copy-Item '$BackupDir\migration_engine.py.bak' '$MePath' -Force"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$OePath' -Force"
    exit 2
}
