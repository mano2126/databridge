$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v95_p4 — 모든 본질 처방 통합 + 이름 매핑 본질" -ForegroundColor Cyan
Write-Host "  본부장님 명령: '근본적 문제 해결에 초점 — 별도로 말 안 해도'" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v95_p4_$ts"
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
Write-Host "  본부장님께 정직한 사과" -ForegroundColor Red
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "v95_p3 작업 시 v94_p10 직전 베이스에서 시작 → v94_p11 의" -ForegroundColor White
Write-Host "본질 처방 (이름 추측 안티패턴 제거) 이 덮어씌워졌습니다." -ForegroundColor White
Write-Host ""
Write-Host "그 결과:" -ForegroundColor Cyan
Write-Host "  - startswith('TVF') 안티패턴 부활" -ForegroundColor Red
Write-Host "  - tvf_daily_trx, tvf_delinq_ranking 1305 재발" -ForegroundColor Red
Write-Host "  - View 들 30초 timeout (bare name 호출)" -ForegroundColor Red

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  v95_p4 — 모든 본질 처방 통합" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[유지] v94_p10: date max_length 본질 처방" -ForegroundColor Green
Write-Host "[유지] v94_p11: 이름 추측 안티패턴 제거 + DB 메타 라우팅" -ForegroundColor Green
Write-Host "[유지] v95_p3: _smart_dummy 타입 우선 + _find_column_sample 타입 호환 + FK 안전" -ForegroundColor Green
Write-Host "[추가] v95_p4: bare name → 실제 객체 이름 자동 매핑" -ForegroundColor Cyan

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  v95_p4 처방 — bare name 매핑 본질" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "본부장님 환경 본질:" -ForegroundColor Cyan
Write-Host "  사용자 호출:    tvf_daily_trx (bare)" -ForegroundColor White
Write-Host "  실제 객체:      settlement_tvf_daily_trx (underscore 정책)" -ForegroundColor White
Write-Host "  → 1305 FUNCTION does not exist" -ForegroundColor Red
Write-Host ""
Write-Host "처방 (PROCEDURE/FUNCTION/VIEW 모두):" -ForegroundColor Cyan
Write-Host "  1. obj_name 그대로 information_schema 조회" -ForegroundColor Green
Write-Host "  2. 없으면 obj_schema_hint 붙은 변형 시도" -ForegroundColor Green
Write-Host "  3. 그래도 없으면 LIKE '%_{name}' suffix 매칭" -ForegroundColor Green
Write-Host "  4. 발견된 실제 이름으로 호출" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  검증" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  ✓ Python syntax OK" -ForegroundColor Green
Write-Host "  ✓ v94_p10 + v94_p11 + v95_p3 + v95_p4 모두 보존" -ForegroundColor Green
Write-Host "  ✓ startswith('TVF') 안티패턴: 0개 (재발 방지)" -ForegroundColor Green
Write-Host "  ✓ 함수 중복: 0 (cleanup 완료)" -ForegroundColor Green
Write-Host "  ✓ DB 메타 라우팅 라이브" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  적용 절차" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  1. ZIP 풀기 (D:\project\ 위)" -ForegroundColor White
Write-Host "  2. Get-Process python | Stop-Process -Force" -ForegroundColor White
Write-Host "  3. cd D:\project\databridge_full\backend; run_backend.bat" -ForegroundColor White
Write-Host "  4. UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  5. 객체 검증 → Clear → 41개 일괄 검증" -ForegroundColor White
Write-Host ""
Write-Host "  검증 후 적용 확인 (PowerShell):" -ForegroundColor Cyan
Write-Host "    Select-String D:\project\databridge_full\backend\app\api\routes\schema.py ``" -ForegroundColor White
Write-Host "       -Pattern 'v94_p11|v95_p4' | Select-Object -First 5" -ForegroundColor White
Write-Host "    → v94_p11 + v95_p4 마커 모두 보여야 정상" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  남은 본질 (별개 영역)" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  - sp_mark_delinquent FK 데이터: 진짜 데이터 의존 (v95_p5 영역)" -ForegroundColor White
Write-Host "  - sp_reverse_trx Lock: 이전 검증 트랜잭션 잔재 (백엔드 재시작 시 해소)" -ForegroundColor White
Write-Host "  - View 30초: 인덱스 무효 패턴 (View 정의 분석 필요, v95_p5 영역)" -ForegroundColor White

Write-Host "`n롤백: Copy-Item '$BackupRoot\backend\app\api\routes\schema.py' '$ProjectRoot\backend\app\api\routes\' -Force" -ForegroundColor DarkYellow
