$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = Join-Path $PatchRoot "..\.."
$PatchSrc = (Resolve-Path $PatchSrc).Path

Write-Host "════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v92p6 — FK stuck + 로그 drag" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v92p6_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "frontend\src\pages\JobMonitor.vue",
    "frontend\src\pages\Settings.vue",
    "backend\app\engine\migration_engine.py"
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

# Python syntax 검증
$py = Join-Path $ProjectRoot "backend\app\engine\migration_engine.py"
$r = & python -c "import ast; ast.parse(open(r'$py',encoding='utf-8').read()); print('OK')" 2>&1
if ($r -match "OK") {
    Write-Host "`n✓ v92p6 완료" -ForegroundColor Green
    Write-Host "  백엔드 reload 후 Ctrl+Shift+R" -ForegroundColor Cyan
    Write-Host "  롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
} else {
    Write-Host "`n✗ syntax 실패: $r" -ForegroundColor Red
    exit 1
}
