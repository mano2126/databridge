# v95_p13 적용 스크립트 — Phase 1+2 (UTF-8 BOM)
# 본부장님 본질 처방: AdventureWorks 48% → 80%+ 목표

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  v95_p13 적용 — Phase 1+2 본질 처방" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 1. 백엔드 정지
Write-Host "[1/4] 백엔드 정지..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3

# 2. __pycache__ 강제 정리
Write-Host "[2/4] __pycache__ 정리..." -ForegroundColor Yellow
Get-ChildItem -Path "$ProjectRoot\backend" -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue
}
Write-Host "  ✓ pycache 정리 완료" -ForegroundColor Green

# 3. 마커 검증
Write-Host "[3/4] 패치 마커 검증..." -ForegroundColor Yellow
$content = Get-Content "$ProjectRoot\backend\app\engine\migration_engine.py" -Raw
$markers = @{
    "v95_p13"                                = "v95_p13 패치 자체"
    "Phase 1-B: UDT"                         = "Phase 1-B UDT 진단"
    "Phase 1-C: PK"                          = "Phase 1-C PK NOT NULL"
    "Phase 1-D"                              = "Phase 1-D nvarchar(max) PK"
    "Phase 1-E"                              = "Phase 1-E 알 수 없는 타입 fallback"
    "Phase 2-A"                              = "Phase 2-A 실패 테이블 추적"
    "Phase 2-B"                              = "Phase 2-B 의존성 가드"
    "COALESCE(bt.name, tp.name)"             = "UDT base type SQL"
    "tp.is_user_defined"                     = "UDT 플래그"
}
$missing = @()
foreach ($m in $markers.GetEnumerator()) {
    if ($content -match [regex]::Escape($m.Key)) {
        Write-Host "  ✓ $($m.Value)" -ForegroundColor Green
    } else {
        Write-Host "  ✗ 누락: $($m.Value) ('$($m.Key)')" -ForegroundColor Red
        $missing += $m.Key
    }
}

if ($missing.Count -gt 0) {
    Write-Host "" -ForegroundColor Red
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
Write-Host "  ✅ v95_p13 적용 완료" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "다음 단계:" -ForegroundColor Yellow
Write-Host "  ① UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  ② AdventureWorks2022 → aw_target Job 재실행" -ForegroundColor White
Write-Host "     (또는 aw_target DROP 후 재이관)" -ForegroundColor White
Write-Host "  ③ 결과 확인 — 기대 성공률 80%+" -ForegroundColor White
Write-Host ""
Write-Host "검증 명령:" -ForegroundColor Cyan
Write-Host '  Get-Content D:\project\databridge_full\backend\logs\databridge_backend.log -Tail 500 | Select-String "v95_p13" | Select-Object -Last 30' -ForegroundColor White
Write-Host ""
Write-Host "기대 로그:" -ForegroundColor Cyan
Write-Host "  [Person_Person] v95_p13 UDT 자동 해석 (4건): NameStyle: 'NameStyle' → 'bit', ..." -ForegroundColor White
Write-Host "  [BillOfMaterials] v95_p13 Phase 1-C: PK 컬럼 'ComponentID' NULL → NOT NULL 강제" -ForegroundColor White
Write-Host "  [Person_PersonPhone] v95_p13 Phase 1-D: PK 'PhoneNumber' nvarchar(max) → VARCHAR(255)" -ForegroundColor White
Write-Host ""
