$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v93_C — Post-Migration Audit Engine" -ForegroundColor Cyan
Write-Host "  본부장님 통찰: '이관 시점에 점검해야 진짜 AI 이관 툴'" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v93_C_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "backend\app\engine\audit_engine.py",
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

# 무결성
$ok = $true
foreach ($rel in $files) {
    $f = Join-Path $ProjectRoot $rel
    if ($f -like "*.py") {
        $r = & python -c "import ast; ast.parse(open(r'$f',encoding='utf-8').read()); print('OK')" 2>&1
        if ($r -notmatch "OK") { Write-Host "✗ $rel : $r" -ForegroundColor Red; $ok = $false }
    }
}

if ($ok) {
    Write-Host "`n✓ v93_C 적용 완료" -ForegroundColor Green
    Write-Host "`n변경 내용:" -ForegroundColor Cyan
    Write-Host "  1. audit_engine.py 신규 — 5개 검증 모듈" -ForegroundColor White
    Write-Host "     - INDEX 누락 (소스 vs 타겟 secondary index)" -ForegroundColor DarkGray
    Write-Host "     - FK 무결성 (참조 깨진 행 카운트)" -ForegroundColor DarkGray
    Write-Host "     - OBJECT 누락 (SP/FUNC/VIEW/TRIGGER)" -ForegroundColor DarkGray
    Write-Host "     - ROW COUNT 차이 (모든 테이블)" -ForegroundColor DarkGray
    Write-Host "     - 타입 손실 (varchar/decimal/datetime2 등)" -ForegroundColor DarkGray
    Write-Host "  2. migration_engine.py — run() 끝에 자동 audit 호출" -ForegroundColor White
    Write-Host "     - phase=AUDIT 단계 추가, audit_report/severity/summary 저장" -ForegroundColor DarkGray
    Write-Host "  3. jobs.py — audit API 추가" -ForegroundColor White
    Write-Host "     GET  /api/v1/jobs/{jid}/audit       — 리포트 조회" -ForegroundColor DarkGray
    Write-Host "     POST /api/v1/jobs/{jid}/audit/rerun — 수동 재실행" -ForegroundColor DarkGray
    Write-Host "`n동작:" -ForegroundColor Cyan
    Write-Host "  이관 완료 → phase=AUDIT → 5개 검증 자동 실행 →" -ForegroundColor White
    Write-Host "  → audit_severity (ok/warn/critical) + summary 표시" -ForegroundColor White
    Write-Host "  → 다음 단계 (Phase D-2 KB 통계 UI 와 연동) 에서 화면 표시 예정" -ForegroundColor White
    Write-Host "`n⚠ 백엔드 재시작 필수 (audit_engine 모듈 신규)" -ForegroundColor Yellow
    Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
} else {
    Write-Host "`n✗ syntax FAIL" -ForegroundColor Red
    exit 1
}
