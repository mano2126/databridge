$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v92p11 — AI 자동 재이관 토글" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v92p11_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "frontend\src\pages\JobWizard.vue",
    "frontend\src\pages\JobMonitor.vue",
    "backend\app\engine\migration_engine.py",
    "backend\app\api\routes\jobs.py"
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
$pyFiles = @(
    "backend\app\engine\migration_engine.py",
    "backend\app\api\routes\jobs.py"
)
$allOk = $true
foreach ($pf in $pyFiles) {
    $full = Join-Path $ProjectRoot $pf
    $r = & python -c "import ast; ast.parse(open(r'$full',encoding='utf-8').read()); print('OK')" 2>&1
    if ($r -match "OK") {
        Write-Host "  ✓ $pf" -ForegroundColor DarkGreen
    } else {
        Write-Host "  ✗ $pf : $r" -ForegroundColor Red
        $allOk = $false
    }
}

if ($allOk) {
    Write-Host "`n════════════════════════════════════════" -ForegroundColor Green
    Write-Host "  ✓ v92p11 완료" -ForegroundColor Green
    Write-Host "════════════════════════════════════════" -ForegroundColor Green
    Write-Host "`n적용된 변경사항:" -ForegroundColor Cyan
    Write-Host "  1. JobWizard 에 'AI 자동 재이관' 체크박스 (기본 OFF)" -ForegroundColor White
    Write-Host "  2. JobMonitor 상태 카드에 '🤖 자동이관 ON/OFF' 배지 표시" -ForegroundColor White
    Write-Host "  3. 백엔드: ai_auto_retry=true 일 때만 자동 재시도 발동" -ForegroundColor White
    Write-Host "  4. 모든 객체 타입 + MySQL/MSSQL 타겟 지원 (이전엔 MSSQL TRIGGER 만)" -ForegroundColor White
    Write-Host "`n다음 단계:" -ForegroundColor Cyan
    Write-Host "  1. 백엔드 reload (uvicorn --reload 면 자동)" -ForegroundColor White
    Write-Host "  2. 브라우저 Ctrl+Shift+R" -ForegroundColor White
    Write-Host "  3. 새 Job 생성 시 'AI 자동 재이관' 체크박스 확인" -ForegroundColor White
    Write-Host "`n롤백:" -ForegroundColor DarkYellow
    Write-Host "  Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
} else {
    Write-Host "`n✗ 일부 파일 syntax 실패 — 롤백 권장" -ForegroundColor Red
    exit 1
}
