$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v92p19 — KB 호출 경로 통합" -ForegroundColor Cyan
Write-Host "  본부장님 결정: KB 우회 경로 차단, 운영 환경 안전화" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v92p19_$ts"
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
    Write-Host "`n✓ v92p19 적용 완료" -ForegroundColor Green
    Write-Host "`n진단:" -ForegroundColor Cyan
    Write-Host "  v92p18 검증 결과 — [KB] 로그 0건" -ForegroundColor White
    Write-Host "  → migration_engine.py 의 객체 이관 + 자동 재시도 경로가" -ForegroundColor White
    Write-Host "    KB 호출을 통째로 우회하고 있었음 (raw error_hint 만 전달)" -ForegroundColor White
    Write-Host "`n처방:" -ForegroundColor Cyan
    Write-Host "  1. _exec_tgt 의 1차 AI 호출 직전 → assemble_prompt_hint() 주입" -ForegroundColor White
    Write-Host "  2. _can_retry 의 자동 재시도 경로 → 동일하게 KB 처방 주입" -ForegroundColor White
    Write-Host "  → 모든 AI 변환 경로가 KB 를 거쳐서 호출됨" -ForegroundColor White
    Write-Host "`n검증 절차 (운영 출시 결정용):" -ForegroundColor Yellow
    Write-Host "  1. 백엔드 reload (Ctrl+C → 재실행)" -ForegroundColor White
    Write-Host "  2. MySQL 콘솔에서 객체 깨뜨리기:" -ForegroundColor White
    Write-Host "     DROP FUNCTION ref_fn_next_business_day;" -ForegroundColor DarkGray
    Write-Host "     DROP PROCEDURE settlement_tvf_daily_trx;" -ForegroundColor DarkGray
    Write-Host "     DROP PROCEDURE credit_sp_calculate_schedule;" -ForegroundColor DarkGray
    Write-Host "  3. 화면에서 🤖 AI 재이관 클릭 (또는 새 Job 시작)" -ForegroundColor White
    Write-Host "  4. 로그 확인:" -ForegroundColor White
    Write-Host "     Select-String -Path '...\databridge_backend.log' -Pattern '\[KB\]|🤖 KB' | Select -Last 20" -ForegroundColor DarkGray
    Write-Host "`n기대 출력 (KB 작동 확정):" -ForegroundColor Cyan
    Write-Host "  [KB] ✓ 매칭 성공: pattern_id=1064_WHILE_END_TO_END_WHILE..." -ForegroundColor Green
    Write-Host "  [...] [fn_next_business_day] 🤖 KB 처방 주입됨 (1850 chars) → AI 호출" -ForegroundColor Green
    Write-Host "  [KB] 📝 프롬프트 주입: 1850 chars, 패턴=[1064_WHILE_END...]" -ForegroundColor Green
    Write-Host "  [KB] 💾 통계 저장: pattern=1064_WHILE_END_TO_END_WHILE, success=✓" -ForegroundColor Green
    Write-Host "`n롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
} else {
    Write-Host "`n✗ syntax FAIL: $r" -ForegroundColor Red
    exit 1
}
