$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v95_p8 — View 안전 모드 본질 처방" -ForegroundColor Cyan
Write-Host "  본부장님 명령: '근본적 문제 해결'" -ForegroundColor Yellow
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v95_p8_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$rel = "backend\app\core\view_analyzer.py"
$src = Join-Path $ProjectRoot $rel
if (Test-Path $src) {
    $dst = Join-Path $BackupRoot $rel
    New-Item -Path (Split-Path -Parent $dst) -ItemType Directory -Force | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst -Force
}
$sf = Join-Path $PatchSrc $rel
Copy-Item -LiteralPath $sf -Destination $src -Force
Write-Host "  + $rel" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  본부장님 환경 본질 진단 (백엔드 로그)" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "v95_p6 작동 ✓ — 안티패턴 감지 정상:" -ForegroundColor Green
Write-Host "  ✓ settlement_v_recent_trx: window_function" -ForegroundColor White
Write-Host "  ✓ ref_v_employee_workload: correlated_subquery" -ForegroundColor White
Write-Host "  ✓ ref_v_branch_performance: count_distinct_groupby" -ForegroundColor White
Write-Host ""
Write-Host "그러나 max_rows=0 → large=False → safe_mode=False" -ForegroundColor Red
Write-Host "  ↑ InnoDB TABLE_ROWS 통계 부정확 (ANALYZE 미실행)" -ForegroundColor Red
Write-Host "  → 일반 LIMIT 50 → 30초 timeout" -ForegroundColor Red

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  v95_p8 본질 처방" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[변경] should_use_safe_mode 분기:" -ForegroundColor Cyan
Write-Host "  v95_p6: is_risky AND is_large  (대용량 조건 필요)" -ForegroundColor Red
Write-Host "  v95_p8: is_risky               (안티패턴 자체가 위험)" -ForegroundColor Green
Write-Host ""
Write-Host "근거:" -ForegroundColor Cyan
Write-Host "  ROW_NUMBER() OVER, 상관 서브쿼리, COUNT(DISTINCT)+GROUP BY," -ForegroundColor White
Write-Host "  COLLATE JOIN 은 *대용량 아니어도* MySQL 옵티마이저가" -ForegroundColor White
Write-Host "  LIMIT push-down 못 함 → 안전 모드가 *올바른 기본값*" -ForegroundColor White

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  적용 (백엔드 재시작 + 캐시 제거)" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  1. ZIP 풀기 (D:\project\ 위)" -ForegroundColor White
Write-Host "  2. Get-Process python | Stop-Process -Force" -ForegroundColor White
Write-Host "  3. Start-Sleep 3" -ForegroundColor White
Write-Host "  4. Remove-Item -Recurse -Force D:\project\databridge_full\backend\app\core\__pycache__ -ErrorAction SilentlyContinue" -ForegroundColor White
Write-Host "  5. cd D:\project\databridge_full\backend; .\run_backend.bat" -ForegroundColor White
Write-Host "  6. UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  7. 객체 검증 → Clear → 41개 일괄 검증" -ForegroundColor White
Write-Host ""
Write-Host "기대 결과:" -ForegroundColor Cyan
Write-Host "  6개 위험 View → 즉시 응답 (수 ms) + '안전 검증 (LIMIT push-down 불가)'" -ForegroundColor Green
Write-Host "  5개 정상 View → 정상 LIMIT 50" -ForegroundColor Green
Write-Host "  sp_daily_batch → △ 검토 (진짜 배치 SP — 별개 본질)" -ForegroundColor White
Write-Host "  trg_bank_primary → 타겟 없음 (이관 누락 — 별개 본질)" -ForegroundColor White
Write-Host "  → 41/41 ✓ (2개 별개 본질 제외 = 39/39 완벽)" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  검증 로그 확인" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Get-Content D:\project\databridge_full\backend\logs\databridge_backend.log -Tail 200 |" -ForegroundColor White
Write-Host "  Select-String 'v95_p6.*safe_mode=True' | Select-Object -Last 10" -ForegroundColor White
Write-Host ""
Write-Host "기대 (이전: safe_mode=False, 지금: safe_mode=True):" -ForegroundColor Cyan
Write-Host "  [v95_p6] settlement_v_recent_trx: risky=True ... safe_mode=True patterns=['window_function']" -ForegroundColor Green

Write-Host "`n롤백: Copy-Item '$BackupRoot\backend\app\core\view_analyzer.py' '$ProjectRoot\backend\app\core\' -Force" -ForegroundColor DarkYellow
