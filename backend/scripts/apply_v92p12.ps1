$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v92p12 — AI DBA 권고 자동 적용" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v92p12_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "backend\app\api\routes\jobs.py",
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

# Python syntax 검증
$pyFiles = @(
    "backend\app\api\routes\jobs.py",
    "backend\app\engine\migration_engine.py"
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
    Write-Host "`n════════════════════════════════════════════════" -ForegroundColor Green
    Write-Host "  ✓ v92p12 완료" -ForegroundColor Green
    Write-Host "════════════════════════════════════════════════" -ForegroundColor Green
    Write-Host "`n구현 내용:" -ForegroundColor Cyan
    Write-Host "  1. AI DBA 권고 'applied'/'edited' 결정 → 이관 시 자동 실행" -ForegroundColor White
    Write-Host "  2. 카테고리 4종 모두 (index/table/object/server)" -ForegroundColor White
    Write-Host "  3. 새 phase ADVISOR_APPLY (OBJECTS 다음 → DONE 전)" -ForegroundColor White
    Write-Host "  4. 권고 SQL 시간을 ETA 에 가중치 반영 (인덱스는 테이블 row 비례)" -ForegroundColor White
    Write-Host "  5. JobMonitor 5단계 표시 (이전 4단계 → 5단계)" -ForegroundColor White
    Write-Host "  6. 실패한 권고도 보고서로 보존 (job.advisor_apply_result)" -ForegroundColor White
    Write-Host "`n다음 단계:" -ForegroundColor Cyan
    Write-Host "  1. 백엔드 reload (uvicorn --reload 면 자동)" -ForegroundColor White
    Write-Host "  2. 브라우저 Ctrl+Shift+R" -ForegroundColor White
    Write-Host "  3. 새 Job 시작 → AI DBA 분석 → 권고 '전체 적용' → 이관" -ForegroundColor White
    Write-Host "  4. JobMonitor 에서 5단계 진행 확인 (마지막 🤖 AI 권고 적용 단계)" -ForegroundColor White
    Write-Host "`n주의사항:" -ForegroundColor Yellow
    Write-Host "  - 인덱스 빌드는 큰 테이블에서 수 분 걸릴 수 있음" -ForegroundColor White
    Write-Host "  - settlement_trx_history (2455만 행) 같은 인덱스는 3-5분" -ForegroundColor White
    Write-Host "  - 권고 적용 실패 시 Job 자체는 success — 보고서에 실패만 표기" -ForegroundColor White
    Write-Host "`n롤백:" -ForegroundColor DarkYellow
    Write-Host "  Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
} else {
    Write-Host "`n✗ 일부 파일 syntax 실패 — 롤백 권장" -ForegroundColor Red
    exit 1
}
