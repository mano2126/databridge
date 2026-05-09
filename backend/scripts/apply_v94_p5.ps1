$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v94_p5 — 두 패턴 본질 처방 (LEAVE 세미콜론 + DELIMITER)" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v94_p5_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "backend\app\core\sql_post_processor.py",
    "backend\app\engine\error_kb.py",
    "backend\app\engine\error_kb.yml",
    "backend\app\api\routes\schema.py"
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

Write-Host "`n✓ v94_p5 적용 완료" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  본부장님 호소 — 정직한 진단" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "이전 결과: 4 객체 → 2 성공, 2 실패 (반복적으로 같은 두 패턴)" -ForegroundColor White
Write-Host ""
Write-Host "  ✓ sp_mark_delinquent  : 2차 성공 (DECLARE_SUBQUERY KB 자산 효과)" -ForegroundColor Green
Write-Host "  ✓ trg_profile_updated : 2차 성공 (AFTER_UPDATE_NEW KB 자산 효과)" -ForegroundColor Green
Write-Host "  ✗ fn_next_business_day : 1차/2차 동일 — LEAVE 다음 ; 누락" -ForegroundColor Red
Write-Host "  ✗ tvf_contract_events  : 1차/2차 동일 — DELIMITER //" -ForegroundColor Red
Write-Host ""
Write-Host "본질 원인:" -ForegroundColor Cyan
Write-Host "  v94_p4 의 KB Pre-Apply 가 일부 객체 (tvf) 에는 작동했지만," -ForegroundColor White
Write-Host "  fix_prompt 가 충분히 명확하지 않아서 AI 가 또 똑같이 변환." -ForegroundColor White
Write-Host "  → 누적 자산이 '학습 가능한 형태' 가 아니라 raw 케이스였음." -ForegroundColor White

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  처방 — 3 단계" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[Layer 1] error_kb.yml 정식 패턴 등록 (사전 가이드 강화)" -ForegroundColor Cyan
Write-Host "  + 1064_LEAVE_MISSING_SEMI" -ForegroundColor White
Write-Host "    → AI 에 'LEAVE/ITERATE 다음 ; 필수' 명시 가이드 주입" -ForegroundColor DarkGray
Write-Host "  + 1064_DELIMITER_NOT_SUPPORTED" -ForegroundColor White
Write-Host "    → AI 에 'DELIMITER 절대 출력 금지' 명시 가이드 주입" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[Layer 2] 시그니처 추출 보강 (LEAVE_LOOP, DELIMITER_RISK)" -ForegroundColor Cyan
Write-Host "  - LOOP/WHILE 코드 → LEAVE_LOOP 시그니처 자동 부착" -ForegroundColor White
Write-Host "  - BEGIN/END 코드 → DELIMITER_RISK 시그니처 자동 부착" -ForegroundColor White
Write-Host "  → preflight 검색이 위 패턴 사전 적용" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[Layer 3] sql_post_processor 자동 보정 (3중 안전망)" -ForegroundColor Cyan
Write-Host "  + R-011: DELIMITER 라인 통째 제거 (pymysql 환경)" -ForegroundColor White
Write-Host "  + R-011b: END// → END; 변환" -ForegroundColor White
Write-Host "  + R-012: LEAVE/ITERATE label 다음 ; 자동 보충" -ForegroundColor White
Write-Host "  + R-013: RETURN/SET 다음 ; 보충 (보수적)" -ForegroundColor White
Write-Host "  → AI 가 또 같은 실수해도 후처리에서 자동 수정" -ForegroundColor DarkGray
Write-Host ""
Write-Host "본부장님 모토 적용:" -ForegroundColor Yellow
Write-Host "  '지금은 발생해도 앞으로 똑같은건 발생 시키지 않는다'" -ForegroundColor White

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  검증 — 같은 4개 객체 다시 이관" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "기대 결과 (3중 안전망 작동 시):" -ForegroundColor Cyan
Write-Host "  Layer 1+2: 1차 prompt 에 LEAVE/DELIMITER 가이드 주입" -ForegroundColor White
Write-Host "             → AI 가 처음부터 올바른 SQL 생성" -ForegroundColor White
Write-Host "  Layer 3:   AI 가 또 실수해도 R-011/R-012 가 자동 수정" -ForegroundColor White
Write-Host "             → 1차 시도에서 통과" -ForegroundColor White
Write-Host ""
Write-Host "로그 확인 마커:" -ForegroundColor White
Write-Host "  '[SQL-PostProc] R-011 적용: 1회'  ← DELIMITER 자동 제거" -ForegroundColor Green
Write-Host "  '[SQL-PostProc] R-012 적용: 1회'  ← LEAVE 세미콜론 자동 보충" -ForegroundColor Green
Write-Host "  '[AI-TRACE 01b-preflight-applied]'  ← KB 자산 사전 주입" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  '🤖자동이관 OFF' 토글 의미" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "JobMonitor 의 '🤖자동이관' 토글은 별개 기능:" -ForegroundColor Cyan
Write-Host "  ON  : 모니터에서 실패 항목 발견 시 자동으로 다시 재이관 시도" -ForegroundColor White
Write-Host "  OFF : 사용자가 수동으로 [재이관] 버튼 클릭해야 재시도" -ForegroundColor White
Write-Host ""
Write-Host "이번에 본 자동 처리는 토글과 무관 — 백엔드 엔진의 1회 자동 retry." -ForegroundColor White
Write-Host "(객체 이관 1차 실패 → KB 매칭 → 2차 자동 시도, max 1회)" -ForegroundColor DarkGray

Write-Host "`n적용 절차:" -ForegroundColor Yellow
Write-Host "  1. ZIP 풀기 (D:\project\ 위)" -ForegroundColor White
Write-Host "  2. Get-Process python | Stop-Process -Force" -ForegroundColor White
Write-Host "  3. cd D:\project\databridge_full\backend; run_backend.bat" -ForegroundColor White
Write-Host "  4. Ctrl+Shift+R" -ForegroundColor White
Write-Host "  5. 같은 4 객체 다시 이관 → 4 / 4 성공 기대" -ForegroundColor Green
Write-Host ""
Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
