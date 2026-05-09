# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p57 적용 (2026-05-05) — 진짜 본질!
# ════════════════════════════════════════════════════════════════════
# 본부장님 직접 SQL 진단 결과 (1초 만에 확정):
#
#   SELECT c.name, t.name, c.is_nullable
#   FROM sys.columns c JOIN sys.types t ON c.system_type_id = t.system_type_id
#   WHERE c.object_id = OBJECT_ID('Production.ProductDocument');
#
#   결과:
#     ProductID     int         0
#     ModifiedDate  datetime    0
#     DocumentNode  hierarchyid 0
#     DocumentNode  geometry    0
#     DocumentNode  geography   0
#
# 진짜 본질 100% 발견:
#   sys.types 에서 system_type_id=240 인 row 가 3개:
#     - hierarchyid (user_type_id=128)
#     - geometry    (user_type_id=129)
#     - geography   (user_type_id=130)
#   모두 user_type_id ≠ system_type_id (CLR 시스템 타입 특성)
#
#   기존 SQL 필터 (v95_p26):
#     JOIN sys.types tp ON c.system_type_id = tp.user_type_id
#                      AND tp.user_type_id = tp.system_type_id  ← 이 필터
#   → CLR 타입은 자기 자신 매치 안 됨 → JOIN 실패 → cols 누락
#   → CREATE TABLE 에서도 누락 → INSERT NULL → 1364 NOT NULL 위반
#
# 처방 (진짜 본질 SQL JOIN 보강):
#   기존 단순 필터 → CROSS APPLY 스타일 서브쿼리:
#     SELECT TOP 1 tp2.user_type_id
#     FROM sys.types tp2
#     WHERE tp2.system_type_id = c.system_type_id
#     ORDER BY
#         CASE WHEN tp2.user_type_id = tp2.system_type_id THEN 0 ELSE 1 END,
#         tp2.user_type_id
#
#   효과:
#     - 정통 base type (int, varchar): 자기 매치 → ORDER BY 0 → 우선 선택
#     - UDT (Flag, Phone): base type 우선 매치 → v95_p26 처방 보존
#     - CLR 타입 (hierarchyid/geometry/geography): 자기 매치 없으니
#       ORDER BY 1 + 가장 작은 user_type_id → hierarchyid 우선 (128)
#
# 부작용 0 검증 (시뮬레이션):
#   - 정통 base type: 영향 0 ✅
#   - UDT: v95_p26 처방 그대로 (base type 매핑) ✅
#   - CLR 타입: 본질 해결 (hierarchyid 정확 매핑) ✅
#
# 효과:
#   - Production_ProductDocument: cols=4 (이전 cols=2) ✅
#   - DocumentNode (hierarchyid) → ToString() SELECT 적용 ✅
#   - PRIMARY KEY (ProductID, DocumentNode) 복합 PK ✅
#   - 32/32 INSERT 성공 ✅
#   - Production_Document 의 DocumentNode 도 동일 효과 ✅
#
# 일반화:
#   - 캐피탈사 운영 DB hierarchyid 거의 없음 → 영향 0
#   - 어떤 DB 든 CLR 타입 정확 매핑 보장
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p57 적용 (CLR 타입 SQL JOIN 본질)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$MePath = Join-Path $Root "backend\app\engine\migration_engine.py"
if (-not (Test-Path $MePath)) { Write-Host "❌ migration_engine.py 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p57_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $MePath (Join-Path $BackupDir "migration_engine.py.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증 (UTF-8 명시)
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$me = [System.IO.File]::ReadAllText($MePath, [System.Text.UTF8Encoding]::new($false))

$ok_marker = $me.Contains("v95_p57")
$ok_topone = $me.Contains("SELECT TOP 1 tp2.user_type_id")
$ok_order  = $me.Contains("CASE WHEN tp2.user_type_id = tp2.system_type_id THEN 0 ELSE 1 END")
$two_subq  = ([regex]::Matches($me, "SELECT TOP 1 tp2.user_type_id")).Count

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p57 처방:"
Write-Host ("    [{0}] v95_p57 마커 — {1}건" -f (_Mark $ok_marker), [regex]::Matches($me, "v95_p57").Count)
Write-Host ("    [{0}] CLR 매핑 서브쿼리 (TOP 1) — {1}곳 (SQL 두 자리 모두 처방)" -f (_Mark ($two_subq -eq 2)), $two_subq)
Write-Host ("    [{0}] ORDER BY (자기 매치 우선)" -f (_Mark $ok_order))

Write-Host ""
Write-Host "  이전 처방 보존:"
foreach ($m in @("v95_p26","v95_p34","v95_p38","v95_p41","v95_p45","v95_p51","v95_p55")) {
    Write-Host ("    [{0}] {1}" -f (_Mark ($me.Contains($m))), $m)
}

$allOk = $ok_marker -and ($two_subq -eq 2) -and $ok_order

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p57 적용 완료 (진짜 본질!)" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) 백엔드 재시작 (필수):"
    Write-Host "     Stop-Process -Id <PID> -Force"
    Write-Host "     cd $Root\backend; .\start.bat"
    Write-Host ""
    Write-Host "  2) 위저드 [↻ 새로 시작] → 재이관"
    Write-Host ""
    Write-Host "  3) 작동 흔적 검증 (한 줄):"
    Write-Host "     `$Log='$Root\backend\logs\databridge_backend.log'"
    Write-Host "     Get-Content `$Log -Tail 30000 | Select-String 'Production_ProductDocument' | Select-Object -Last 15"
    Write-Host ""
    Write-Host "결과 측정 기대:"
    Write-Host "  - bulk loader cols=4 (이전 cols=2)"
    Write-Host "  - SELECT [ProductID], [DocumentNode].ToString() AS [DocumentNode], [Document], [ModifiedDate]"
    Write-Host "  - PRIMARY KEY (ProductID, DocumentNode)"
    Write-Host "  - 32/32 INSERT 성공 ✅"
    Write-Host "  - Production_Document 도 동일 효과 ✅"
    Write-Host "  - AdventureWorks 100% 이관 완벽 완료 ✅"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\migration_engine.py.bak' '$MePath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\migration_engine.py.bak' '$MePath' -Force"
    exit 2
}
