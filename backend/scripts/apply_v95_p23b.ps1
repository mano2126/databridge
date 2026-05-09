# v95_p23b 적용 스크립트 (UTF-8 BOM, 2026-05-03)
# 본부장님 4가지 본질 한방에 처방:
#   ① UDT base type 해석 (1101 + 1170 동시 해소) — system_type_id JOIN
#   ② KeyError (underscore 입력 분해)
#   ③ PK NOT NULL 강제 (1171)
#   ④ PascalCase schema 추론

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  v95_p23b 적용 — 4가지 본질 한방에" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/4] 백엔드 정지..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3

Write-Host "[2/4] __pycache__ 정리..." -ForegroundColor Yellow
Get-ChildItem -Path "$ProjectRoot\backend" -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue
}
Write-Host "  ✓ pycache 정리" -ForegroundColor Green

Write-Host "[3/4] 패치 마커 검증 (4가지 본질)..." -ForegroundColor Yellow

$markers = @{
    "$ProjectRoot\backend\app\engine\migration_engine.py"             = "system_type_id = tp.user_type_id"
    "$ProjectRoot\backend\app\core\schema_conversion_policy.py"       = "PascalCase"
}

$missing = @()
foreach ($file in $markers.Keys) {
    $content = Get-Content $file -Raw -ErrorAction SilentlyContinue
    if (-not $content) {
        Write-Host "  ✗ 파일 없음: $($file | Split-Path -Leaf)" -ForegroundColor Red
        $missing += $file
        continue
    }
    if ($content -match [regex]::Escape($markers[$file])) {
        Write-Host "  ✓ $($file | Split-Path -Leaf): 마커 OK" -ForegroundColor Green
    } else {
        Write-Host "  ✗ 마커 없음: $($file | Split-Path -Leaf)" -ForegroundColor Red
        $missing += $file
    }
}

# 추가 검증 — 4가지 처방 모두
$content = Get-Content "$ProjectRoot\backend\app\engine\migration_engine.py" -Raw -ErrorAction SilentlyContinue
$checks = @{
    "UDT system_type_id 처방"  = "system_type_id = tp.user_type_id"
    "underscore 분해 처방"     = "underscore 분해"
    "PK NOT NULL 강제 처방"    = "MySQL 1171 방지"
}
foreach ($name in $checks.Keys) {
    if ($content -match [regex]::Escape($checks[$name])) {
        Write-Host "  ✓ $name 적용됨" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $name 누락" -ForegroundColor Red
        $missing += $name
    }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "✗ 패치 미적용. ZIP 다시 풀고 재실행" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[4/4] 백엔드 시작..." -ForegroundColor Yellow
Push-Location "$ProjectRoot\backend"
Start-Process -FilePath ".\run_backend.bat" -WindowStyle Normal
Pop-Location
Start-Sleep -Seconds 8

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✅ v95_p23b 적용 완료" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "검증 절차:" -ForegroundColor Yellow
Write-Host "  ① UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  ② aw_target 초기화 (옵션):" -ForegroundColor White
Write-Host '     docker exec db_mysql mysql -u root -pbridge1234 -e "DROP DATABASE aw_target; CREATE DATABASE aw_target CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"' -ForegroundColor Gray
Write-Host "  ③ 새 Job 생성 → 1개씩 이관 (또는 멀티)" -ForegroundColor White
Write-Host ""
Write-Host "기대 결과:" -ForegroundColor Cyan
Write-Host "  - 1101 (NameStyle/MakeFlag/...): 0건 (UDT → bit → TINYINT(1))" -ForegroundColor White
Write-Host "  - 1170 (PhoneNumber): 0건 (UDT → nvarchar → VARCHAR)" -ForegroundColor White
Write-Host "  - 1171 (BillOfMaterials PK): 0건 (PK NOT NULL 강제)" -ForegroundColor White
Write-Host "  - KeyError (HumanResources_Employee 등): 0건 (underscore 분해)" -ForegroundColor White
Write-Host ""
Write-Host "검증 명령:" -ForegroundColor Cyan
Write-Host '  Get-Content D:\project\databridge_full\backend\logs\databridge_backend.log -Tail 5000 | Select-String "v95_p23b" | Select-Object -Last 20' -ForegroundColor Gray
Write-Host ""
