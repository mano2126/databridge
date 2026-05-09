$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = Join-Path $PatchRoot "..\..\frontend\src\pages\Settings.vue"
$PatchSrc = (Resolve-Path $PatchSrc).Path

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$rel = "frontend\src\pages\Settings.vue"
$src = Join-Path $ProjectRoot $rel
if (Test-Path $src) {
    $dst = Join-Path $BackupRoot $rel
    New-Item -Path (Split-Path -Parent $dst) -ItemType Directory -Force | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst -Force
    Write-Host "백업: $dst" -ForegroundColor DarkGray
}

Copy-Item -LiteralPath $PatchSrc -Destination $src -Force
Write-Host "적용: $rel" -ForegroundColor Green
Write-Host ""
Write-Host "✓ v92p3 완료 — 브라우저에서 Ctrl+Shift+R" -ForegroundColor Cyan
