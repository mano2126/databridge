$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v92p7_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$rel = "backend\app\engine\migration_engine.py"
$src = Join-Path $ProjectRoot $rel
if (Test-Path $src) {
    $dst = Join-Path $BackupRoot $rel
    New-Item -Path (Split-Path -Parent $dst) -ItemType Directory -Force | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst -Force
}
Copy-Item -LiteralPath (Join-Path $PatchSrc $rel) -Destination $src -Force

$r = & python -c "import ast; ast.parse(open(r'$src',encoding='utf-8').read()); print('OK')" 2>&1
if ($r -match "OK") {
    Write-Host "✓ v92p7 — objects-only Job FK 단계 스킵 적용" -ForegroundColor Green
    Write-Host "  ⚠ 백엔드 reload 필수 (uvicorn --reload 면 자동)" -ForegroundColor Yellow
    Write-Host "  현재 stuck Job 은 jobs 페이지에서 ⏹ 중단 후 재시작" -ForegroundColor Cyan
    Write-Host "  롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
} else {
    Write-Host "✗ syntax FAIL: $r" -ForegroundColor Red
    exit 1
}
