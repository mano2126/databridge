$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v92p15_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "backend\app\api\routes\jobs.py",
    "frontend\src\pages\JobMonitor.vue"
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

$pyFile = Join-Path $ProjectRoot "backend\app\api\routes\jobs.py"
$r = & python -c "import ast; ast.parse(open(r'$pyFile',encoding='utf-8').read()); print('OK')" 2>&1
if ($r -match "OK") {
    Write-Host "`n✓ v92p15 — AI 자동이관 배지 클릭 토글 적용" -ForegroundColor Green
    Write-Host "  진행 중 Job 도 ON/OFF 실시간 가능" -ForegroundColor Cyan
    Write-Host "  ⚠ 백엔드 reload 필수" -ForegroundColor Yellow
    Write-Host "  롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
} else {
    Write-Host "`n✗ syntax FAIL: $r" -ForegroundColor Red
    exit 1
}
