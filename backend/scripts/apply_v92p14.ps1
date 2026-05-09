$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v92p14_$ts"
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
    Write-Host "✓ v92p14 — _migrate_table KeyError 수정 (dict init swap 후로 이동)" -ForegroundColor Green
    Write-Host "  원인: 'customer_credit_score' 등 KeyError" -ForegroundColor Cyan
    Write-Host "  처방: src_bare → tgt_table swap 후 dict 초기화 + _hier_cols 추가" -ForegroundColor Cyan
    Write-Host "  ⚠ 백엔드 reload 필수" -ForegroundColor Yellow
    Write-Host "  롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
} else {
    Write-Host "✗ syntax FAIL: $r" -ForegroundColor Red
    exit 1
}
