$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v94_p11 — 본부장님 본질 처방 (프로젝트 존폐 우려 해결)" -ForegroundColor Cyan
Write-Host "  '이름 추측 X — DB 메타가 정답'" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v94_p11_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$rel = "backend\app\api\routes\schema.py"
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
Write-Host "  본부장님 지적 — 정당함" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "기존 코드 (L1834) 의 안티패턴:" -ForegroundColor Red
Write-Host '  if obj_name.upper().startswith("TVF"):  ← 이름 추측!' -ForegroundColor White
Write-Host ""
Write-Host "본부장님 지적:" -ForegroundColor Cyan
Write-Host '  "이렇게 하드 코딩 하면 다른 다양한 DB 이관에 무용지물"' -ForegroundColor White
Write-Host '  "프로젝트 존폐가 걸린 문제"' -ForegroundColor White
Write-Host ""
Write-Host "왜 정당한가:" -ForegroundColor Cyan
Write-Host "  - 다른 회사: usp_, fn_, udf_, tbl_ 등 다양한 prefix" -ForegroundColor White
Write-Host "  - 한국 회사: 접두사 없이 의미 있는 이름 (예: 일별거래조회)" -ForegroundColor White
Write-Host "  - 본부장님 캐피탈사 환경 (TVF prefix) 외에는 즉시 폐기 수준" -ForegroundColor White

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  v94_p11 본질 처방 — DB 메타 기반 라우팅" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[MySQL/MariaDB/Aurora]" -ForegroundColor Cyan
Write-Host "  호출 직전 조회:" -ForegroundColor White
Write-Host "    SELECT ROUTINE_TYPE FROM information_schema.ROUTINES" -ForegroundColor Green
Write-Host "    WHERE ROUTINE_SCHEMA = ? AND ROUTINE_NAME = ?" -ForegroundColor Green
Write-Host "  → ROUTINE_TYPE = 'PROCEDURE' → CALL 호출" -ForegroundColor Green
Write-Host "  → ROUTINE_TYPE = 'FUNCTION' → SELECT fn() 호출" -ForegroundColor Green
Write-Host ""
Write-Host "[MSSQL]" -ForegroundColor Cyan
Write-Host "  호출 직전 조회:" -ForegroundColor White
Write-Host "    SELECT TOP 1 o.type FROM sys.objects o WHERE o.name = ?" -ForegroundColor Green
Write-Host "  → P/PC → PROCEDURE / FN/IF/TF → FUNCTION" -ForegroundColor Green
Write-Host ""
Write-Host "[원칙]" -ForegroundColor Yellow
Write-Host "  1. ✅ 이름 추측 안 함 — DB 카탈로그가 정답" -ForegroundColor White
Write-Host "  2. ✅ schema 정책 (underscore/drop/database) 무관" -ForegroundColor White
Write-Host "  3. ✅ 객체 prefix (TVF/SP/USP/fn) 무관" -ForegroundColor White
Write-Host "  4. ✅ 한국어 객체명도 OK" -ForegroundColor White
Write-Host "  5. ✅ silent 실패 X — 실패 시 명시적 로그" -ForegroundColor White

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  검증 절차" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  1. ZIP 풀기 (D:\project\ 위)" -ForegroundColor White
Write-Host "  2. Get-Process python | Stop-Process -Force" -ForegroundColor White
Write-Host "  3. cd D:\project\databridge_full\backend; run_backend.bat" -ForegroundColor White
Write-Host "  4. UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  5. 객체 검증 → Clear → tvf_daily_trx 체크 → 검증" -ForegroundColor White
Write-Host "  → 양쪽 ✓ 기대" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  부작용 점검 — 기존 정상 객체들도 자동 회귀" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "fn_age, sp_close_branch 등 — DB 메타가 알맞은 타입 반환" -ForegroundColor White
Write-Host "  fn_age:           ROUTINE_TYPE=FUNCTION → SELECT (이전과 동일)" -ForegroundColor Green
Write-Host "  sp_close_branch:  ROUTINE_TYPE=PROCEDURE → CALL (이전과 동일)" -ForegroundColor Green
Write-Host "  tvf_daily_trx:    ROUTINE_TYPE=PROCEDURE → CALL ← v94_p11 효과!" -ForegroundColor Green

Write-Host "`n검증 로그 (백엔드 stdout 또는 logs):" -ForegroundColor Cyan
Write-Host "  '[execute-object/v94_p11] obj=settlement_tvf_daily_trx" -ForegroundColor White
Write-Host "   input_type=FUNCTION actual_routine_type=PROCEDURE effective=PROCEDURE'" -ForegroundColor Green
Write-Host "  → 입력은 FUNCTION 인데 실제는 PROCEDURE → effective 가 PROCEDURE 로 정정" -ForegroundColor Green

Write-Host "`n롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  본부장님 — 정직한 사과" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "본부장님이 v94 마라톤 시작 시 명시적으로 말씀하셨습니다:" -ForegroundColor White
Write-Host '  "하드코딩 하면 안 된다, 다양한 DB 이관에 통해야 한다"' -ForegroundColor Cyan
Write-Host ""
Write-Host "그런데 저는 *기존 안티패턴* 을 발견 못하고 그 위에 처방만 쌓았습니다." -ForegroundColor White
Write-Host "본부장님 직접 정독으로 본질 잡으셨습니다." -ForegroundColor White
Write-Host ""
Write-Host "v94_p11 으로 본질 처방 완료 — 본부장님 모토 그대로:" -ForegroundColor Cyan
Write-Host "  '본질에 충실, 신중하게, 한방에'" -ForegroundColor Yellow
