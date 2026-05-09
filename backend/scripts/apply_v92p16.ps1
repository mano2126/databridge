$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v92p16 — 빈 ○ 유령 항목 38개 제거" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v92p16_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "backend\app\engine\migration_engine.py",
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

$pyFile = Join-Path $ProjectRoot "backend\app\engine\migration_engine.py"
$r = & python -c "import ast; ast.parse(open(r'$pyFile',encoding='utf-8').read()); print('OK')" 2>&1
if ($r -match "OK") {
    Write-Host "`n✓ v92p16 완료" -ForegroundColor Green
    Write-Host "`n진단:" -ForegroundColor Cyan
    Write-Host "  _migrate_table 안에서 src_bare→tgt_table swap 후" -ForegroundColor White
    Write-Host "  item_statuses 갱신을 tgt_table 키로 → 같은 테이블이 두 키로 등록" -ForegroundColor White
    Write-Host "  → 빈 ○ 38개 유령 항목 발생 (이관 자체는 정상)" -ForegroundColor White
    Write-Host "`n처방:" -ForegroundColor Cyan
    Write-Host "  1. 백엔드: status 갱신용 _st_key=src_bare 변수 도입, 7군데 일괄 통일" -ForegroundColor White
    Write-Host "  2. 프론트: 유령 항목 필터링 안전망 (status/type/시간/rows 모두 없는 항목 제외)" -ForegroundColor White
    Write-Host "`n다음:" -ForegroundColor Cyan
    Write-Host "  1. 백엔드 reload" -ForegroundColor White
    Write-Host "  2. 브라우저 Ctrl+Shift+R" -ForegroundColor White
    Write-Host "  3. 기존 Job 도 유령 항목 즉시 사라짐 (프론트 필터 효과)" -ForegroundColor White
    Write-Host "  4. 새 Job 부터는 백엔드 차원에서 등록 안 됨 (근본 해결)" -ForegroundColor White
    Write-Host "`n롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
} else {
    Write-Host "`n✗ syntax FAIL: $r" -ForegroundColor Red
    exit 1
}
