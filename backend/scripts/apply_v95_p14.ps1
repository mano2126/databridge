# v95_p14 적용 스크립트 (UTF-8 BOM)
# v95_p13 위에 누적 — Phase 2-D/E/F 추가
# 본부장님 진단 (Job#4255fd) 기반 본질 처방

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  v95_p14 적용 — Phase 2-D/E/F 본질 처방" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 1. 백엔드 정지
Write-Host "[1/4] 백엔드 정지..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3

# 2. __pycache__ 정리
Write-Host "[2/4] __pycache__ 정리..." -ForegroundColor Yellow
Get-ChildItem -Path "$ProjectRoot\backend" -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue
}
Write-Host "  ✓ pycache 정리" -ForegroundColor Green

# 3. 마커 검증 (v95_p13 + v95_p14)
Write-Host "[3/4] 패치 마커 검증..." -ForegroundColor Yellow
$content = Get-Content "$ProjectRoot\backend\app\engine\migration_engine.py" -Raw
$markers = @{
    # v95_p13 (필수 — 누적)
    "Phase 1-B: UDT"                = "v95_p13 Phase 1-B (UDT 진단)"
    "Phase 1-C: PK"                 = "v95_p13 Phase 1-C (PK NOT NULL)"
    "Phase 1-D"                     = "v95_p13 Phase 1-D (nvarchar(max) PK)"
    "Phase 1-E"                     = "v95_p13 Phase 1-E (타입 fallback)"
    "Phase 2-A"                     = "v95_p13 Phase 2-A (실패 추적)"
    "Phase 2-B"                     = "v95_p13 Phase 2-B (도미노 차단)"
    "COALESCE(bt.name, tp.name)"    = "v95_p13 UDT base type SQL"
    # v95_p14 신규
    "v95_p14 Phase 2-D"             = "v95_p14 Phase 2-D (양방향 등록)"
    "v95_p14 Phase 2-E"             = "v95_p14 Phase 2-E (INSERT 실패 추적)"
    "v95_p14 Phase 2-F"             = "v95_p14 Phase 2-F (traceback 로깅)"
}
$missing = @()
foreach ($m in $markers.GetEnumerator()) {
    if ($content -match [regex]::Escape($m.Key)) {
        Write-Host "  ✓ $($m.Value)" -ForegroundColor Green
    } else {
        Write-Host "  ✗ 누락: $($m.Value)" -ForegroundColor Red
        $missing += $m.Key
    }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "✗ 패치 미적용. ZIP 다시 풀고 재실행" -ForegroundColor Red
    exit 1
}

# 4. 백엔드 시작
Write-Host ""
Write-Host "[4/4] 백엔드 시작..." -ForegroundColor Yellow
Push-Location "$ProjectRoot\backend"
Start-Process -FilePath ".\run_backend.bat" -WindowStyle Normal
Pop-Location
Start-Sleep -Seconds 8

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✅ v95_p14 적용 완료" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "다음 단계:" -ForegroundColor Yellow
Write-Host "  ① UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  ② aw_target DROP 후 재이관:" -ForegroundColor White
Write-Host "     docker exec db_mysql mysql -u root -pbridge1234 -e `"DROP DATABASE aw_target; CREATE DATABASE aw_target CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci`"" -ForegroundColor White
Write-Host "  ③ 새 Job 실행 → 결과 측정" -ForegroundColor White
Write-Host ""
Write-Host "검증 명령:" -ForegroundColor Cyan
Write-Host '  Get-Content D:\project\databridge_full\backend\logs\databridge_backend.log -Tail 1000 | Select-String "Phase 2-D|Phase 2-E|Phase 2-F|tb:"' -ForegroundColor White
Write-Host ""
Write-Host "기대 효과:" -ForegroundColor Cyan
Write-Host "  - VIEW 도미노 16건 SKIP 처리 (skipped_dep 상태)" -ForegroundColor White
Write-Host "  - 5개 테이블 실패 시 진짜 에러 메시지 + traceback 보임" -ForegroundColor White
Write-Host "  - 다음 v95_p15 처방 위한 진짜 본질 확정 가능" -ForegroundColor White
Write-Host ""
