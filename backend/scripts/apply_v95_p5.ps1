$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v95_p5 — _find_column_sample DictCursor 호환 + 진단 로그" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v95_p5_$ts"
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
Write-Host "  본부장님 환경 본질 진단" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "credit_contract 데이터:" -ForegroundColor Cyan
Write-Host "  - 1,500,000 행 (contract_id 20000001 ~ 21500000)" -ForegroundColor White
Write-Host "  - customer_id NOT NULL: 100% (NULL 0개)" -ForegroundColor White
Write-Host ""
Write-Host "본부장님 화면:" -ForegroundColor Cyan
Write-Host "  소스 (MSSQL): 📊 자동 + 20000002 ✓ (작동)" -ForegroundColor Green
Write-Host "  타겟 (MySQL): 📊 자동 *없음* + 1 ✗ (작동 안 함)" -ForegroundColor Red
Write-Host ""
Write-Host "본질 발견:" -ForegroundColor Cyan
Write-Host "  v95_p3 의 _find_column_sample 가" -ForegroundColor White
Write-Host "  row[3] 같은 정수 인덱스 사용 → DictCursor 비호환" -ForegroundColor Red
Write-Host "  → KeyError → except → None → _smart_dummy fallback → '1'" -ForegroundColor Red
Write-Host ""
Write-Host "v95_p5 처방:" -ForegroundColor Cyan
Write-Host "  _row_get(row, 3, 'DATA_TYPE') 헬퍼 도입" -ForegroundColor Green
Write-Host "  - dict cursor: row['DATA_TYPE'] 로 추출" -ForegroundColor Green
Write-Host "  - tuple cursor: row[3] 로 추출" -ForegroundColor Green
Write-Host "  - 양쪽 모두 호환 (pymysql/pyodbc/cx_Oracle)" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  추가 — 진단 로그 강화" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "이전: 모든 Exception 침묵 → 진단 불가" -ForegroundColor Red
Write-Host "현재: 각 단계 _logger_fcs.info/warning 으로 명시적 로그" -ForegroundColor Green
Write-Host "      → 본부장님이 어디서 실패하는지 즉시 확인 가능" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  적용" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  1. ZIP 풀기 (D:\project\ 위)" -ForegroundColor White
Write-Host "  2. Get-Process python | Stop-Process -Force" -ForegroundColor White
Write-Host "  3. cd D:\project\databridge_full\backend; run_backend.bat" -ForegroundColor White
Write-Host "  4. UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  5. sp_mark_delinquent 만 체크 → 검증" -ForegroundColor White
Write-Host ""
Write-Host "기대:" -ForegroundColor Cyan
Write-Host "  타겟 (MySQL) 화면: 📊 자동 + 20000001 (또는 더 안전한 ID)" -ForegroundColor Green
Write-Host "  → INSERT 정상 → ✓ 양쪽 성공" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  진단 로그 확인" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "검증 후 백엔드 로그:" -ForegroundColor Cyan
Write-Host "  Get-Content D:\project\databridge_full\backend\logs\databridge_backend.log -Tail 100 |" -ForegroundColor White
Write-Host "    Select-String 'param-suggest/v95_p5'" -ForegroundColor White
Write-Host ""
Write-Host "기대 로그:" -ForegroundColor Cyan
Write-Host "  [param-suggest/v95_p5] @contract_id (bigint): 1개 호환 컬럼 — 우선 시도: credit_contract.contract_id" -ForegroundColor Green
Write-Host "  [param-suggest/v95_p5] @contract_id → credit_contract.contract_id = 20000001" -ForegroundColor Green

Write-Host "`n롤백: Copy-Item '$BackupRoot\backend\app\api\routes\schema.py' '$ProjectRoot\backend\app\api\routes\' -Force" -ForegroundColor DarkYellow

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  남은 본질 — View 30초 timeout (별도 영역)" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "v95_p5 적용 후 sp_mark_delinquent ✓ 확인되면" -ForegroundColor White
Write-Host "View 30초 timeout 진단 (다음 단계):" -ForegroundColor Cyan
Write-Host "  docker exec db_mysql mysql -uroot -pbridge1234 capital_target -e ``" -ForegroundColor White
Write-Host "    'SHOW CREATE VIEW settlement_v_recent_trx\G'" -ForegroundColor White
Write-Host ""
Write-Host "View 정의의 인덱스 무효 패턴 (CAST 등) 확인 후 처방 진행" -ForegroundColor Green
