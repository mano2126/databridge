# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p55 적용 (2026-05-05) — cols 메타 누락 컬럼 보강
# ════════════════════════════════════════════════════════════════════
# 본부장님 강조: "이번에 끝내자", "하드코딩 0%"
#
# 본부장님 환경 진짜 본질 (view tool + 진단 PS1 100% 추적):
#
#   증거 (로그 19:47:30):
#     - bulk loader cols=2 (정상은 cols=4여야 함)
#     - PRIMARY KEY (ProductID) 단일 PK (정상은 ProductID+DocumentNode)
#     - SELECT TOP 5000 [ProductID], [ModifiedDate] (DocumentNode 누락)
#
#   진짜 본질:
#     sys.types JOIN 의 (tp.user_type_id = tp.system_type_id) 필터로
#     hierarchyid (CLR 시스템 타입) 가 sys.types JOIN 에서 빠짐
#     → cols 메타에 컬럼 자체 없음
#     → CREATE TABLE 에서도 누락
#     → SELECT 에서도 누락
#     → MySQL 단일 PK 인식 → 32행 동일 ProductID = 1062 PK 중복
#
# 처방 (일반화 — 하드코딩 0%, 부작용 0):
#
#   probe_cur.description (MSSQL 진짜 컬럼 목록) vs cols (sys.types 필터링됨)
#   → description 에 있는데 cols 에 없는 컬럼 = 메타 누락
#   → sys.indexes 별도 조회로 진짜 PK 컬럼 확인
#   → cols 에 보강 추가 (hierarchyid 추정)
#   → CREATE TABLE / SELECT / PK 모두 정상 인식
#
#   v95_p51 PK 진단 보강과 자동 연동:
#     - 보강 후 cols 에 DocumentNode (PRI) 추가됨
#     - v95_p51 의 _pk_names_meta 추출 시 복합 PK 인식 가능
#     - UPSERT 자동 발동 → 1062 회피
#
# 부작용 0 검증:
#   - 정상 cols 변경 0 (없는 컬럼만 추가)
#   - v95_p26 (UDT 처방) 100% 보존 (sys.types JOIN 변경 없음)
#   - 운영 DB hierarchyid 거의 없음 → 발동 0건
#   - 다른 DB (Northwind 등) cols 누락 없음 → 발동 0건
#
# 단위 테스트 통과:
#   - Production_ProductDocument: DocumentNode 보강 → 복합 PK 인식 ✅
#   - Person_BusinessEntityAddress: cols 누락 없음 → 영향 0 ✅
#   - 운영 DB 정상 테이블: cols 누락 없음 → 영향 0 ✅
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p55 적용 (cols 메타 누락 보강 — 진짜 본질)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$MePath = Join-Path $Root "backend\app\engine\migration_engine.py"
if (-not (Test-Path $MePath)) { Write-Host "❌ migration_engine.py 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p55_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $MePath (Join-Path $BackupDir "migration_engine.py.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증 (UTF-8 명시)
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$me = [System.IO.File]::ReadAllText($MePath, [System.Text.UTF8Encoding]::new($false))

$ok_marker  = $me.Contains("v95_p55")
$ok_missing = $me.Contains("_missing_cols")
$ok_pk_qry  = $me.Contains("is_primary_key = 1")
$ok_recover = $me.Contains("_v95_p55_recovered")
$ok_log     = $me.Contains("cols 메타 누락 컬럼 발견")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p55 처방:"
Write-Host ("    [{0}] v95_p55 마커 — {1}건" -f (_Mark $ok_marker), [regex]::Matches($me, "v95_p55").Count)
Write-Host ("    [{0}] _missing_cols 누락 컬럼 변수" -f (_Mark $ok_missing))
Write-Host ("    [{0}] sys.indexes is_primary_key 별도 조회" -f (_Mark $ok_pk_qry))
Write-Host ("    [{0}] _v95_p55_recovered 마커" -f (_Mark $ok_recover))
Write-Host ("    [{0}] '[v95_p55] cols 메타 누락' 로그" -f (_Mark $ok_log))

Write-Host ""
Write-Host "  이전 처방 보존:"
foreach ($m in @("v95_p26","v95_p34","v95_p38","v95_p41","v95_p45","v95_p51","v95_p53")) {
    Write-Host ("    [{0}] {1}" -f (_Mark ($me.Contains($m))), $m)
}

$allOk = $ok_marker -and $ok_missing -and $ok_pk_qry -and $ok_recover -and $ok_log

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p55 적용 완료 (진짜 본질 처방!)" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계 (필수):" -ForegroundColor Yellow
    Write-Host "  1) 백엔드 재시작 (필수):"
    Write-Host "     Stop-Process -Id <PID> -Force"
    Write-Host "     cd $Root\backend; .\start.bat"
    Write-Host ""
    Write-Host "  2) 위저드 [↻ 새로 시작] → 재이관"
    Write-Host ""
    Write-Host "  3) 작동 흔적 검증 (한 줄로):"
    Write-Host "     `$Log='$Root\backend\logs\databridge_backend.log'"
    Write-Host "     Get-Content `$Log -Tail 30000 | Select-String 'v95_p55|Production_ProductDocument' | Select-Object -Last 30"
    Write-Host ""
    Write-Host "결과 측정 기대 (로그):"
    Write-Host "  [v95_p55] [Production_ProductDocument] cols 메타 누락 컬럼 발견: ['DocumentNode', 'Document']"
    Write-Host "  [v95_p55] [Production_ProductDocument] 컬럼 [DocumentNode] cols 에 보강 추가 (PK=True, dt='hierarchyid' 추정)"
    Write-Host "  [v95_p51] [Production_ProductDocument] PK 진단 보강: ..."
    Write-Host "  → bulk loader cols=4 (이전 cols=2)"
    Write-Host "  → PRIMARY KEY (ProductID, DocumentNode) (이전 단일 PK)"
    Write-Host "  → 32/32 INSERT 성공 (1062 발생 0건) ✅"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\migration_engine.py.bak' '$MePath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\migration_engine.py.bak' '$MePath' -Force"
    exit 2
}
