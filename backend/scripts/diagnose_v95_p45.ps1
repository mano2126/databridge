# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p45 진단 (2026-05-05) — last one 두 본질 추적
# ════════════════════════════════════════════════════════════════════
# 본부장님 모토 "본질에 충실, 추측 처방 금지" 충실 위해
# 처방 전 진짜 본질 100% 확인.
#
# 두 본질 동시 진단:
#   (a) CamelCase 환각 (Production_ProductModelInstruction)
#       → v95_p42 환각 검출 로그가 있는지, 어떤 검출 방법으로 잡혔는지
#
#   (b) PK 중복 (Production_ProductDocument 32행)
#       → drop_table 옵션이 backend 까지 전달됐는지
#       → DROP TABLE / TRUNCATE 시도 결과 (성공/실패)
#       → FK 제약으로 fallback 동작했는지
# ════════════════════════════════════════════════════════════════════

$Root = "D:\project\databridge_full"
$LogDir = Join-Path $Root "backend\logs"
$Log = Join-Path $LogDir "databridge_backend.log"

if (-not (Test-Path $Log)) {
    Write-Host "❌ 로그 파일 없음: $Log" -ForegroundColor Red
    Write-Host "   backend 로그 경로 다를 수 있음. 다음 명령으로 확인:" -ForegroundColor Yellow
    Write-Host "   Get-ChildItem '$Root\backend\logs\' -Recurse -Filter '*.log'"
    exit 1
}

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p45 진단 (last one — 두 본질 추적)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "로그: $Log" -ForegroundColor Gray
Write-Host ""

# ──────────────────────────────────────────────────────────────────
# 본질 (a): CamelCase 환각 (vProductModelInstructions)
# ──────────────────────────────────────────────────────────────────
Write-Host "─────────────────────────────────────────────────────────────"
Write-Host "[본질 a] vProductModelInstructions 환각 검출 흔적"
Write-Host "─────────────────────────────────────────────────────────────"

Write-Host ""
Write-Host ">>> 1. v95_p42 안전 폴백이 발동했는가?" -ForegroundColor Cyan
Write-Host ""
$p42_logs = Get-Content $Log -Tail 30000 -ErrorAction SilentlyContinue |
    Select-String "v95_p42-FALLBACK|v95_p35-#3-HALLUCINATION" |
    Select-Object -Last 30
if ($p42_logs) {
    $p42_logs | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "  ⚠ 흔적 없음 — v95_p42 검출 작동 안 함" -ForegroundColor Yellow
    Write-Host "    → CamelCase 환각이 endswith 매치 실패해서 v95_p35 진입조차 못 함" -ForegroundColor Yellow
}

Write-Host ""
Write-Host ">>> 2. vProductModelInstructions 변환 결과 (AI 응답)" -ForegroundColor Cyan
Write-Host ""
$view_logs = Get-Content $Log -Tail 30000 -ErrorAction SilentlyContinue |
    Select-String "vProductModelInstructions" |
    Select-Object -Last 20
if ($view_logs) {
    $view_logs | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "  vProductModelInstructions 관련 로그 없음" -ForegroundColor Yellow
}

Write-Host ""
Write-Host ">>> 3. Production_ProductModelInstruction (가짜 테이블) 참조 흔적" -ForegroundColor Cyan
Write-Host ""
$fake_logs = Get-Content $Log -Tail 30000 -ErrorAction SilentlyContinue |
    Select-String "Production_ProductModelInstruction" |
    Select-Object -Last 10
if ($fake_logs) {
    $fake_logs | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "  로그에 가짜 테이블 참조 흔적 없음 (오류 메시지에만 있음)" -ForegroundColor Gray
}

# ──────────────────────────────────────────────────────────────────
# 본질 (b): PK 중복 (Production_ProductDocument)
# ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "─────────────────────────────────────────────────────────────"
Write-Host "[본질 b] Production_ProductDocument PK 중복 (1062 에러)"
Write-Host "─────────────────────────────────────────────────────────────"

Write-Host ""
Write-Host ">>> 1. drop_table 옵션이 backend 까지 전달됐는가?" -ForegroundColor Cyan
Write-Host ""
$drop_setting = Get-Content $Log -Tail 30000 -ErrorAction SilentlyContinue |
    Select-String "drop_table|이관전 DROP|이관 모드 옵션" |
    Select-Object -Last 10
if ($drop_setting) {
    $drop_setting | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "  drop_table 설정 로그 없음" -ForegroundColor Yellow
}

Write-Host ""
Write-Host ">>> 2. Production_ProductDocument DROP/TRUNCATE 시도 결과" -ForegroundColor Cyan
Write-Host ""
$pd_drop = Get-Content $Log -Tail 30000 -ErrorAction SilentlyContinue |
    Select-String "Production_ProductDocument" |
    Select-Object -Last 30
if ($pd_drop) {
    $pd_drop | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "  Production_ProductDocument 관련 로그 없음" -ForegroundColor Yellow
}

Write-Host ""
Write-Host ">>> 3. DROP 또는 TRUNCATE 실패 흔적 (어떤 테이블이든)" -ForegroundColor Cyan
Write-Host ""
$drop_fails = Get-Content $Log -Tail 30000 -ErrorAction SilentlyContinue |
    Select-String "DROP 실패|TRUNCATE.*실패|FK.*실패" |
    Select-Object -Last 20
if ($drop_fails) {
    $drop_fails | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "  DROP/TRUNCATE 실패 로그 없음" -ForegroundColor Gray
}

Write-Host ""
Write-Host ">>> 4. PK 중복 (1062) 에러 — 영향받은 테이블 전체" -ForegroundColor Cyan
Write-Host ""
$pk_dups = Get-Content $Log -Tail 30000 -ErrorAction SilentlyContinue |
    Select-String "1062.*Duplicate" |
    Select-Object -Last 10
if ($pk_dups) {
    $pk_dups | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "  1062 PK 중복 에러 없음 (정상)" -ForegroundColor Gray
}

# ──────────────────────────────────────────────────────────────────
# MySQL 직접 진단 (선택적)
# ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "─────────────────────────────────────────────────────────────"
Write-Host "[추가 진단] MySQL 타겟 직접 조회 (선택)"
Write-Host "─────────────────────────────────────────────────────────────"
Write-Host ""
Write-Host "MySQL 컨테이너에서 직접 확인하려면:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  # 테이블 존재 확인 + 행수"
Write-Host "  docker exec db_mysql mysql -uroot -p<pwd> -e ``"
Write-Host "    `"USE aw_target;"
Write-Host "     SELECT 'Production_ProductDocument' AS tbl, COUNT(*) AS rows"
Write-Host "     FROM Production_ProductDocument;"
Write-Host "     SELECT 'Production_ProductModel' AS tbl, COUNT(*) AS rows"
Write-Host "     FROM Production_ProductModel;`""
Write-Host ""
Write-Host "  # 환각 가짜 테이블 진짜로 없는지 확인"
Write-Host "  docker exec db_mysql mysql -uroot -p<pwd> -e ``"
Write-Host "    `"SELECT TABLE_NAME FROM information_schema.TABLES"
Write-Host "     WHERE TABLE_SCHEMA='aw_target'"
Write-Host "     AND TABLE_NAME LIKE 'Production_ProductModelInstruction%';`""

# ──────────────────────────────────────────────────────────────────
# 결론 가이드
# ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "─────────────────────────────────────────────────────────────"
Write-Host "[결론 가이드] 출력 결과 해석"
Write-Host "─────────────────────────────────────────────────────────────"
Write-Host ""
Write-Host "본질 (a) CamelCase 환각 확정 조건:" -ForegroundColor Yellow
Write-Host "  - v95_p42-FALLBACK 흔적 없음 = endswith 매치 실패 → CamelCase 보강 필요"
Write-Host "  - v95_p42-FALLBACK 흔적 있음 = 다른 본질 (베이스 매핑 잘못)"
Write-Host ""
Write-Host "본질 (b) PK 중복 진짜 원인 시나리오:" -ForegroundColor Yellow
Write-Host "  시나리오 A: drop_table 로그 없음 → 위저드→백엔드 전달 끊김"
Write-Host "  시나리오 B: DROP 실패 + TRUNCATE 실패 → FK/락 문제"
Write-Host "  시나리오 C: drop_table 정상 + 그래도 1062 → 소스 자체 PK 중복"
Write-Host ""
Write-Host "이 진단 결과를 본부장님이 공유해주시면 v95_p45 처방 시작합니다."
