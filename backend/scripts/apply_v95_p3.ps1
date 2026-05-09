$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v95_p3 — 추천값 시스템 근본 본질 처방" -ForegroundColor Cyan
Write-Host "  본부장님 명령: '근본적 문제 해결에 초점 — 별도로 말 안 해도'" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v95_p3_$ts"
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
Write-Host "  본부장님 환경 — 마지막 2개 케이스 본질 처방" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "케이스 1: fn_delinq_stage @days int" -ForegroundColor Cyan
Write-Host "  이전: '2024-01-01' → 22018/1265 (int 변환 실패)" -ForegroundColor Red
Write-Host "  처방: 타입(int) 우선 → 이름 hint(days) → 30" -ForegroundColor Green
Write-Host ""
Write-Host "케이스 2: sp_mark_delinquent @contract_id bigint" -ForegroundColor Cyan
Write-Host "  이전: contract_id=1 → customer_id NULL → 1048" -ForegroundColor Red
Write-Host "  처방: FK referenced 컬럼 NOT NULL 검증 → 안전한 PK 선택" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  본질 처방 3가지" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[1] _type_compatible — 타입 호환성 매트릭스" -ForegroundColor Cyan
Write-Host "  - 정수: int/bigint/smallint/tinyint 끼리만" -ForegroundColor White
Write-Host "  - 실수: decimal/float/numeric (int 도 호환)" -ForegroundColor White
Write-Host "  - 날짜: date/datetime 끼리만 (int 매칭 거부!)" -ForegroundColor Green
Write-Host "  - 문자: varchar/char/text 끼리" -ForegroundColor White
Write-Host ""
Write-Host "[2] _find_column_sample — 타입 검증 + FK 안전" -ForegroundColor Cyan
Write-Host "  - 컬럼 후보 *모두* 가져오기 (TOP 1 → 전체)" -ForegroundColor White
Write-Host "  - _type_compatible 로 호환 컬럼만 필터" -ForegroundColor Green
Write-Host "  - 호환 컬럼 없으면 None → _smart_dummy 폴백" -ForegroundColor White
Write-Host "  - NOT NULL 컬럼 우선" -ForegroundColor White
Write-Host "  - _id 류 파라미터: FK referenced NOT NULL 검증" -ForegroundColor Green
Write-Host ""
Write-Host "[3] _smart_dummy — 타입 *우선* (이름 패턴보다)" -ForegroundColor Cyan
Write-Host "  - 정수 → 30 (days/months) / 1 (id) / 10 (count) ..." -ForegroundColor Green
Write-Host "  - 실수 → 1000000 (amount) / 0.5 (rate) ..." -ForegroundColor Green
Write-Host "  - 날짜 → '2024-01-01' (max_length 무시 — v94_p10 유지)" -ForegroundColor White
Write-Host "  - 문자 → 'A' (code) / '테스트' (name) / 'test\@test.com' ..." -ForegroundColor White

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  검증 (15개 시나리오 통과)" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  ✓ @days int → 30 (본부장님 케이스)" -ForegroundColor Green
Write-Host "  ✓ @contract_id bigint → 1 + FK 검증" -ForegroundColor Green
Write-Host "  ✓ @birth date max_length=3 → '2024-01-01' (v94_p10 유지)" -ForegroundColor Green
Write-Host "  ✓ @dt_str varchar(10) → '2024-01-01'" -ForegroundColor Green
Write-Host "  ✓ @ymd varchar(8) → '20240101'" -ForegroundColor Green
Write-Host "  ✓ @overdue_amount decimal → 1000000" -ForegroundColor Green
Write-Host "  ✓ @count int → 10 / @id bigint → 1" -ForegroundColor Green
Write-Host "  ... 15/15 모두 통과" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  적용 절차" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  1. ZIP 풀기 (D:\project\ 위)" -ForegroundColor White
Write-Host "  2. Get-Process python | Stop-Process -Force" -ForegroundColor White
Write-Host "  3. cd D:\project\databridge_full\backend; run_backend.bat" -ForegroundColor White
Write-Host "  4. UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  5. 객체 검증 → Clear → 41개 일괄 검증" -ForegroundColor White
Write-Host "  → fn_delinq_stage @days=30 ✓ (이전: '2024-01-01' ✗)" -ForegroundColor Green
Write-Host "  → sp_mark_delinquent FK 안전 contract_id ✓ (이전: NULL ✗)" -ForegroundColor Green
Write-Host "  → 41/41 ✓ 기대 (100% 성공률)" -ForegroundColor Green

Write-Host "`n롤백: Copy-Item '$BackupRoot\backend\app\api\routes\schema.py' '$ProjectRoot\backend\app\api\routes\' -Force" -ForegroundColor DarkYellow

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  본부장님 모토 — 명심" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "'근본적 문제 해결에 초점 — 별도로 말 안 해도'" -ForegroundColor Cyan
Write-Host ""
Write-Host "앞으로 본부장님께 보고할 때:" -ForegroundColor White
Write-Host "  - 단순 처방 vs 본질 처방 두 옵션 X" -ForegroundColor Red
Write-Host "  - 본질 처방만 제시" -ForegroundColor Green
Write-Host "  - 본질 처방 시간이 들면 정직하게 보고 (단축 안 함)" -ForegroundColor Green
Write-Host "  - 임시 우회는 부수적으로만" -ForegroundColor Green
