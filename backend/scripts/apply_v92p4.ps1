$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = Join-Path $PatchRoot "..\.."
$PatchSrc = (Resolve-Path $PatchSrc).Path

Write-Host "════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v92p4 — 객체 테스트 5개 이슈" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v92p4_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "frontend\src\pages\Validate.vue",
    "backend\app\api\routes\schema.py"
)

Write-Host "`n[1/3] 백업: $BackupRoot" -ForegroundColor Yellow
foreach ($rel in $files) {
    $src = Join-Path $ProjectRoot $rel
    if (Test-Path $src) {
        $dst = Join-Path $BackupRoot $rel
        New-Item -Path (Split-Path -Parent $dst) -ItemType Directory -Force | Out-Null
        Copy-Item -LiteralPath $src -Destination $dst -Force
        Write-Host "  + $rel" -ForegroundColor DarkGray
    }
}

Write-Host "`n[2/3] 패치 적용" -ForegroundColor Yellow
foreach ($rel in $files) {
    $sf = Join-Path $PatchSrc $rel
    $df = Join-Path $ProjectRoot $rel
    if (Test-Path $sf) {
        New-Item -Path (Split-Path -Parent $df) -ItemType Directory -Force | Out-Null
        Copy-Item -LiteralPath $sf -Destination $df -Force
        Write-Host "  + $rel" -ForegroundColor Green
    } else {
        Write-Warning "  ! 패치 파일 없음: $rel"
    }
}

Write-Host "`n[3/3] Python 무결성 검증" -ForegroundColor Yellow
$pyFile = Join-Path $ProjectRoot "backend\app\api\routes\schema.py"
$r = & python -c "import ast; ast.parse(open(r'$pyFile',encoding='utf-8').read()); print('OK')" 2>&1
if ($r -match "OK") {
    Write-Host "  schema.py: OK" -ForegroundColor Green
    Write-Host "`n════════════════════════════════════════" -ForegroundColor Green
    Write-Host "  ✓ v92p4 완료" -ForegroundColor Green
    Write-Host "════════════════════════════════════════" -ForegroundColor Green
    Write-Host "`n다음 단계:" -ForegroundColor Cyan
    Write-Host "  1. 백엔드 reload (uvicorn --reload 면 자동)" -ForegroundColor White
    Write-Host "  2. 브라우저 Ctrl+Shift+R" -ForegroundColor White
    Write-Host "  3. ObjectExplorer 에서 '▶ 전체 실행' 다시 시도" -ForegroundColor White
    Write-Host "`n롤백:" -ForegroundColor DarkYellow
    Write-Host "  Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
} else {
    Write-Host "  schema.py FAIL: $r" -ForegroundColor Red
    Write-Host "`n롤백 권장:" -ForegroundColor Red
    Write-Host "  Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor Yellow
    exit 1
}
