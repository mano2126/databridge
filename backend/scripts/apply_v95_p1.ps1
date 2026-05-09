$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v95_p1 — 자동 통계 갱신 (본부장님 명령)" -ForegroundColor Cyan
Write-Host "  '다양한 DB 처리해야 되는데 이런 문제로 고생하면 안 돼'" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v95_p1_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "backend\app\engine\migration_engine.py",
    "backend\app\core\statistics_gatherer.py"
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
Write-Host "  본부장님 명령 — 본질 처방" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "본부장님이 직접 발견하신 본질 (오늘 23시):" -ForegroundColor Cyan
Write-Host "  ANALYZE TABLE 전: SELECT MIN(trx_date) → 60초+ 안 끝남" -ForegroundColor White
Write-Host "  ANALYZE TABLE 후: 즉시 응답 + CALL settlement_tvf_daily_trx 정상" -ForegroundColor Green
Write-Host ""
Write-Host "→ 데이터 이관 직후 통계 정보 부재 → 옵티마이저 잘못된 계획" -ForegroundColor White
Write-Host "→ 운영 환경 전환 직후 모든 쿼리 느려짐 → '프로젝트 존폐'" -ForegroundColor Red
Write-Host ""

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  v95_p1 처방 — DB-specific 어댑터 패턴" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[새 모듈] backend/app/core/statistics_gatherer.py" -ForegroundColor Cyan
Write-Host "  - MySQL/MariaDB/Aurora/TiDB: ANALYZE TABLE" -ForegroundColor Green
Write-Host "  - PostgreSQL:                ANALYZE" -ForegroundColor Green
Write-Host "  - Oracle:                    DBMS_STATS.GATHER_TABLE_STATS" -ForegroundColor Green
Write-Host "    + 파티션 자동 감지 (DBA_TAB_PARTITIONS)" -ForegroundColor Yellow
Write-Host "    + granularity='ALL' (글로벌 + 파티션 + 서브파티션)" -ForegroundColor Yellow
Write-Host "  - MSSQL/Azure:               UPDATE STATISTICS WITH FULLSCAN" -ForegroundColor Green
Write-Host "  - DB2:                       RUNSTATS WITH DISTRIBUTION AND DETAILED INDEXES" -ForegroundColor Green
Write-Host ""
Write-Host "[migration_engine 통합]" -ForegroundColor Cyan
Write-Host "  - 이관 완료 직전 (status=completed 직전) 자동 호출" -ForegroundColor White
Write-Host "  - 옵션: job['auto_gather_statistics'] (기본 ON)" -ForegroundColor White
Write-Host "  - 실패 허용 (이관은 성공 유지)" -ForegroundColor White
Write-Host "  - 진행 로그: 각 테이블별 + 합계" -ForegroundColor White

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  Oracle 파티션 처리 (본부장님 강조)" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "본부장님 명령: '오라클 통계 정보에 취약 — 파티션 잘 처리'" -ForegroundColor Cyan
Write-Host ""
Write-Host "처방:" -ForegroundColor White
Write-Host "  1. ALL_TAB_PARTITIONS 으로 파티션 여부 자동 감지" -ForegroundColor Green
Write-Host "  2. 파티션이면 → granularity='ALL'" -ForegroundColor Green
Write-Host "     (글로벌 + 파티션 + 서브파티션 모두)" -ForegroundColor Green
Write-Host "  3. 일반이면 → granularity='AUTO' (Oracle 자동)" -ForegroundColor Green
Write-Host "  4. 옵션:" -ForegroundColor Green
Write-Host "     - estimate_percent = AUTO_SAMPLE_SIZE (Oracle 권장)" -ForegroundColor White
Write-Host "     - method_opt = 'FOR ALL COLUMNS SIZE AUTO' (히스토그램)" -ForegroundColor White
Write-Host "     - cascade = TRUE (인덱스 통계도 함께)" -ForegroundColor White
Write-Host "     - no_invalidate = FALSE (SQL 캐시 무효화 → 새 통계 즉시 반영)" -ForegroundColor White

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  검증 (시뮬레이션 통과)" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  ✓ MySQL 42 테이블 시나리오" -ForegroundColor Green
Write-Host "  ✓ Oracle 일반 테이블 (granularity=AUTO)" -ForegroundColor Green
Write-Host "  ✓ Oracle 파티션 테이블 (granularity=ALL + [파티션 ALL] 표시)" -ForegroundColor Green
Write-Host "  ✓ 미지원 DB 시 안전하게 건너뜀" -ForegroundColor Green
Write-Host "  ✓ 실패 허용 (이관 성공 유지)" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  적용 절차" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  1. ZIP 풀기 (D:\project\ 위)" -ForegroundColor White
Write-Host "  2. Get-Process python | Stop-Process -Force" -ForegroundColor White
Write-Host "  3. cd D:\project\databridge_full\backend; run_backend.bat" -ForegroundColor White
Write-Host "  4. 전체 데이터 이관 시작 (본부장님이 내일 진행 예정)" -ForegroundColor White
Write-Host "  5. 이관 끝날 때 로그 확인:" -ForegroundColor White
Write-Host "     '═══ 통계 정보 자동 갱신 시작 (mysql) — 42개 테이블 ═══'" -ForegroundColor Green
Write-Host "     '  [1/42] ✓ collection_activity (...ms)'" -ForegroundColor Green
Write-Host "     ..." -ForegroundColor Green
Write-Host "     '═══ 통계 갱신 완료 — 성공 42/42 ═══'" -ForegroundColor Green
Write-Host ""
Write-Host "  6. 그 다음 객체 검증 — 60초 타임아웃 사라짐 + 정상 결과" -ForegroundColor Green

Write-Host "`n롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  v95 큰 그림 — 본부장님 우려 해결의 시작" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "v95_p1 (오늘): 자동 통계 갱신 + DB 어댑터 패턴" -ForegroundColor Cyan
Write-Host "v95 향후 처방 (내일 이후):" -ForegroundColor Cyan
Write-Host "  - AI 변환 품질 검증 (stub 자동 감지)" -ForegroundColor White
Write-Host "  - 자동 회귀 테스트 (부작용 방지)" -ForegroundColor White
Write-Host "  - 인덱스 무효 패턴 KB (CAST(date) = ? 같은 패턴 자동 처방)" -ForegroundColor White
Write-Host "  - 멀티 선택 UI 복원" -ForegroundColor White
Write-Host "  - DataBridgeGemma (자체 호스팅 AI, 완전 air-gapped)" -ForegroundColor White
