$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v92p10_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$rel = "frontend\src\pages\Validate.vue"
$src = Join-Path $ProjectRoot $rel
if (Test-Path $src) {
    $dst = Join-Path $BackupRoot $rel
    New-Item -Path (Split-Path -Parent $dst) -ItemType Directory -Force | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst -Force
}
Copy-Item -LiteralPath (Join-Path $PatchSrc $rel) -Destination $src -Force
Write-Host "✓ v92p10 — 테이블 매칭 multi-key fallback 적용" -ForegroundColor Green
Write-Host "  소스 customer.profile ↔ 타겟 customer_profile 자동 매칭" -ForegroundColor Cyan
Write-Host "  schemaStrategy 드롭다운 값 무관하게 동작" -ForegroundColor Cyan
Write-Host "  브라우저 Ctrl+Shift+R 후 검증 화면 다시 로드" -ForegroundColor Yellow
Write-Host "  롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
