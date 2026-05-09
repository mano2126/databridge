$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v95_p6 — View 안티패턴 안전 검증" -ForegroundColor Cyan
Write-Host "  본부장님 명령: '당연 본질적인 문제 해결'" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v95_p6_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "backend\app\api\routes\schema.py",
    "backend\app\core\view_analyzer.py"
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

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  본부장님 환경 5개 View 본질 진단" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  settlement_v_recent_trx       → ROW_NUMBER() OVER + 25M 행" -ForegroundColor Red
Write-Host "  ref_v_branch_performance      → COLLATE JOIN + COUNT(DISTINCT) + GROUP BY" -ForegroundColor Red
Write-Host "  ref_v_employee_workload       → 상관 서브쿼리 N+1" -ForegroundColor Red
Write-Host "  credit_v_product_delinq_rate  → COLLATE JOIN + COUNT(DISTINCT) + GROUP BY" -ForegroundColor Red
Write-Host "  customer_v_customer_360       → (분석 결과)" -ForegroundColor Red
Write-Host ""
Write-Host "→ 모두 *대용량 테이블 참조* + DataBridge LIMIT 50 호출 시 풀 스캔" -ForegroundColor White

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  본질 처방 — DB 메타 기반 분석" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[신규] backend/app/core/view_analyzer.py" -ForegroundColor Cyan
Write-Host "  - View 정의 자동 분석 (information_schema.VIEWS)" -ForegroundColor White
Write-Host "  - 4가지 안티패턴 감지:" -ForegroundColor Green
Write-Host "    1. 윈도우 함수 (ROW_NUMBER, RANK, LEAD, LAG, FIRST_VALUE, NTILE 등)" -ForegroundColor White
Write-Host "    2. 상관 서브쿼리 (N+1 anti-pattern)" -ForegroundColor White
Write-Host "    3. COUNT(DISTINCT) + GROUP BY (집계 폭주)" -ForegroundColor White
Write-Host "    4. COLLATE JOIN (인덱스 무효)" -ForegroundColor White
Write-Host "  - 참조 테이블 행수 확인 (TABLE_ROWS)" -ForegroundColor Green
Write-Host "  - 안티패턴 + 100만 행 이상 → 안전 모드" -ForegroundColor Green
Write-Host ""
Write-Host "[수정] backend/app/api/routes/schema.py" -ForegroundColor Cyan
Write-Host "  - VIEW 호출 시 view_analyzer 통합" -ForegroundColor White
Write-Host "  - 안전 모드 → LIMIT 1 (구조 확인만)" -ForegroundColor Green
Write-Host "  - 일반 모드 → LIMIT 50 (기존 동작)" -ForegroundColor White

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  다양한 DB 환경 — 본부장님 우려 영역" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  ✓ MySQL/MariaDB/Aurora: information_schema.VIEWS + .TABLES" -ForegroundColor Green
Write-Host "  ✓ PostgreSQL:           information_schema.views + pg_stat_user_tables" -ForegroundColor Green
Write-Host "  ✓ MSSQL:                sys.views + sys.partitions" -ForegroundColor Green
Write-Host "  ✓ Oracle:               ALL_VIEWS + ALL_TABLES" -ForegroundColor Green
Write-Host "  → 모두 표준 카탈로그 사용 — 이름 추측 X" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  적용 + 검증" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  1. ZIP 풀기 (D:\project\ 위)" -ForegroundColor White
Write-Host "  2. Get-Process python | Stop-Process -Force" -ForegroundColor White
Write-Host "  3. cd D:\project\databridge_full\backend; run_backend.bat" -ForegroundColor White
Write-Host "  4. UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  5. 객체 검증 → Clear → 41개 일괄 검증 (동시 5개)" -ForegroundColor White
Write-Host ""
Write-Host "기대 결과:" -ForegroundColor Cyan
Write-Host "  - 5개 위험 View → ✓ 양쪽 성공 (안전 모드 메시지: 'LIMIT 1 구조 확인')" -ForegroundColor Green
Write-Host "  - 5개 정상 View → ✓ 양쪽 성공 (LIMIT 50)" -ForegroundColor Green
Write-Host "  - sp_mark_delinquent → ✓ (v95_p5 효과)" -ForegroundColor Green
Write-Host "  - 41/41 ✓ 기대" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  검증 로그 확인" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Get-Content D:\project\databridge_full\backend\logs\databridge_backend.log -Tail 200 |" -ForegroundColor White
Write-Host "  Select-String 'v95_p6' | Select-Object -Last 15" -ForegroundColor White
Write-Host ""
Write-Host "기대 로그:" -ForegroundColor Cyan
Write-Host "  [v95_p6] settlement_v_recent_trx: risky=True large=True safe_mode=True" -ForegroundColor Green
Write-Host "    patterns=['window_function'] max_rows=25000000" -ForegroundColor Green

Write-Host "`n롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  본부장님 모토 명심" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "'근본적 문제 해결에 초점'" -ForegroundColor Cyan
Write-Host "  - 운영 View 정의 그대로 유지 (비즈니스 영향 X)" -ForegroundColor Green
Write-Host "  - DataBridge 도구의 본질 처방" -ForegroundColor Green
Write-Host "  - 다양한 DB 환경 적용 가능" -ForegroundColor Green
Write-Host "  - KB 자산화 — 미래 환경에 자동 적용" -ForegroundColor Green
