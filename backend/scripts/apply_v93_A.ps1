$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v93_A — 인덱스 자동 이관" -ForegroundColor Cyan
Write-Host "  본부장님 발견: 22개 테이블 secondary index 0개 → 운영 시작 불가" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v93_A_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "backend\app\engine\index_migrator.py",
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

$ok = $true
foreach ($rel in $files) {
    $f = Join-Path $ProjectRoot $rel
    if ($f -like "*.py") {
        $r = & python -c "import ast; ast.parse(open(r'$f',encoding='utf-8').read()); print('OK')" 2>&1
        if ($r -notmatch "OK") { Write-Host "✗ $rel : $r" -ForegroundColor Red; $ok = $false }
    }
}

if ($ok) {
    Write-Host "`n✓ v93_A 적용 완료" -ForegroundColor Green
    Write-Host "`n변경 내용:" -ForegroundColor Cyan
    Write-Host "  1. index_migrator.py 신규 — 인덱스 자동 이관 모듈" -ForegroundColor White
    Write-Host "     - MSSQL/MySQL 양방향 secondary index 수집" -ForegroundColor DarkGray
    Write-Host "     - 시그니처 기반 중복 방지 (이미 있는 인덱스 skip)" -ForegroundColor DarkGray
    Write-Host "     - 개별 실패 격리 (한 인덱스 실패해도 나머지 계속)" -ForegroundColor DarkGray
    Write-Host "  2. migration_engine.py — INDEX_CREATE phase 추가" -ForegroundColor White
    Write-Host "     순서: 데이터 이관 완료 → INDEX_CREATE → AUDIT → DONE" -ForegroundColor DarkGray
    Write-Host "     job.with_idx 또는 withIdx 토글 ON 일 때만 실행" -ForegroundColor DarkGray
    Write-Host "`n동작:" -ForegroundColor Cyan
    Write-Host "  Job 옵션 withIdx=true (기본) →" -ForegroundColor White
    Write-Host "    데이터 이관 완료 후 자동으로 인덱스 생성 →" -ForegroundColor White
    Write-Host "    job.index_report 에 결과 저장 (created/skipped/failed)" -ForegroundColor White
    Write-Host "`n결과 조회:" -ForegroundColor Cyan
    Write-Host "  GET /api/v1/jobs/{jid} → response.index_report" -ForegroundColor DarkGray
    Write-Host "`n⚠ 백엔드 재시작 필수 (index_migrator 모듈 신규)" -ForegroundColor Yellow
    Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
} else {
    Write-Host "`n✗ syntax FAIL" -ForegroundColor Red
    exit 1
}
