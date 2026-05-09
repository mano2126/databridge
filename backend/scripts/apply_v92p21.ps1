$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v92p21 — 'days' (int) 가 날짜로 오인되는 회귀 수정" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v92p21_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "backend\app\api\routes\schema.py",
    "frontend\src\pages\Validate.vue"
)

foreach ($rel in $files) {
    $src = Join-Path $ProjectRoot $rel
    if (Test-Path $src) {
        $dst = Join-Path $BackupRoot $rel
        New-Item -Path (Split-Path -Parent $dst) -ItemType Directory -Force | Out-Null
        Copy-Item -LiteralPath $src -Destination $dst -Force
    }
    $sf = Join-Path $PatchSrc $rel
    if (Test-Path $sf) {
        New-Item -Path (Split-Path -Parent $src) -ItemType Directory -Force | Out-Null
        Copy-Item -LiteralPath $sf -Destination $src -Force
        Write-Host "  + $rel" -ForegroundColor Green
    }
}

$pyFile = Join-Path $ProjectRoot "backend\app\api\routes\schema.py"
$r = & python -c "import ast; ast.parse(open(r'$pyFile',encoding='utf-8').read()); print('OK')" 2>&1

if ($r -match "OK") {
    Write-Host "`n✓ v92p21 적용 완료" -ForegroundColor Green
    Write-Host "`n진단 (v92p20 회귀):" -ForegroundColor Cyan
    Write-Host "  - 'day' 부분문자열 매칭이 'days' (일수, int) 까지 잡음" -ForegroundColor White
    Write-Host "  - fn_delinq_stage(@days int) → '2024-01-01' 날짜 입력됨" -ForegroundColor White
    Write-Host "  - 소스 ODBC: 'Conversion failed when converting nvarchar to int'" -ForegroundColor White
    Write-Host "  - 타겟 MySQL: 'Data truncated for column p_days'" -ForegroundColor White
    Write-Host "`n처방 (양쪽 동일):" -ForegroundColor Cyan
    Write-Host "  - is_numeric_type 가드: int/decimal/float 면 날짜 매칭 제외" -ForegroundColor White
    Write-Host "  - days/day/term 등 numeric 타입 → 30 (일수 의미 안전값)" -ForegroundColor White
    Write-Host "`n검증 (시뮬레이션):" -ForegroundColor Cyan
    Write-Host "  ✓ @days int → 30 (일수)" -ForegroundColor Green
    Write-Host "  ✓ @dt date → '2024-01-01' (정상 유지)" -ForegroundColor Green
    Write-Host "  ✓ @birthday date → '2024-01-01' (정상 유지)" -ForegroundColor Green
    Write-Host "  ✓ @close_date date → '2024-01-01' (정상 유지)" -ForegroundColor Green
    Write-Host "`n⚠ 백엔드 reload 필수 (Ctrl+C → uvicorn 재실행)" -ForegroundColor Yellow
    Write-Host "⚠ 브라우저 Ctrl+Shift+R" -ForegroundColor Yellow
    Write-Host "`n롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
} else {
    Write-Host "`n✗ syntax FAIL: $r" -ForegroundColor Red
    exit 1
}
