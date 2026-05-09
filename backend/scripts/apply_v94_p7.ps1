$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v94_p7 — 테이블 + 오브젝트 검증 한방 처방" -ForegroundColor Cyan
Write-Host "  본부장님 모토: 본질에 충실, 신중하게, 한방에" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v94_p7_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "backend\app\api\routes\validate.py",
    "backend\app\api\routes\schema.py",
    "backend\app\engine\error_kb.yml",
    "backend\app\core\sql_post_processor.py",
    "frontend\src\pages\Validate.vue"
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

Write-Host "`n✓ v94_p7 적용 완료" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  처방 — 5가지 본질 동시 처방" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray

Write-Host ""
Write-Host "[T1] 테이블 검증 -600,000 가짜 차이" -ForegroundColor Cyan
Write-Host "  본질: validate.py 의 _tbl_ref / _tbl_exists / _resolve_tbl_name" -ForegroundColor White
Write-Host "        가 schema.table → bare name 으로 떨어뜨려 underscore 정책 무시" -ForegroundColor White
Write-Host "        → 본부장님 환경의 실제 테이블 collection_activity 못 찾음" -ForegroundColor White
Write-Host "  처방: underscore 정책 우선 시도 (collection.activity → collection_activity)" -ForegroundColor White
Write-Host "        실패 시 bare name fallback (drop 정책 호환)" -ForegroundColor White
Write-Host "  영향: 41개 불일치 → 정상 매칭 후 진짜 차이만 표시" -ForegroundColor Green

Write-Host ""
Write-Host "[O1] MSSQL FUNC/PROC date 타입 캐스팅 (6개)" -ForegroundColor Cyan
Write-Host "  본질: schema.py 의 _fmt_val 가 타입 무관하게 N'2024-01-01' 로 포맷" -ForegroundColor White
Write-Host "        → MSSQL strict 환경: 'nvarchar to date 변환 실패'" -ForegroundColor White
Write-Host "  처방: sys.parameters 에서 타입 조회 후" -ForegroundColor White
Write-Host "        date/datetime/datetime2/time 인 자리는 CAST(N'...' AS xxx) 명시" -ForegroundColor White
Write-Host "        PROCEDURE 도 ? 바인딩 시 CAST(? AS date) 적용" -ForegroundColor White
Write-Host "  영향: fn_age, fn_korean_date, fn_next_business_day," -ForegroundColor Green
Write-Host "        sp_close_branch, sp_daily_batch, tvf_daily_trx, tvf_contract_events" -ForegroundColor Green

Write-Host ""
Write-Host "[O2] tvf_delinq_ranking '타겟 없음' (1305)" -ForegroundColor Cyan
Write-Host "  본질: 이름 매핑 정책 차이 — KB 패턴 등록으로 미래 자동 처방" -ForegroundColor White
Write-Host "  처방: error_kb.yml + 1305_OBJECT_NAME_MISMATCH" -ForegroundColor White
Write-Host "  영향: 다음 변환부터 AI 가 underscore 정책 명확히 적용" -ForegroundColor Green

Write-Host ""
Write-Host "[O3] tvf_daily_trx 0 인자 손실 (1318)" -ForegroundColor Cyan
Write-Host "  본질: AI 변환 시 TVF 파라미터 시그니처 잃음" -ForegroundColor White
Write-Host "  처방: error_kb.yml + 1318_TVF_PARAM_LOST" -ForegroundColor White
Write-Host "        → 다음 변환부터 사전 가이드 주입" -ForegroundColor White
Write-Host "  영향: 미래 같은 패턴 변환 시 1차에서 정상 변환" -ForegroundColor Green

Write-Host ""
Write-Host "[보너스] 검증 화면 input 폭 좁아서 '202' 만 보이던 문제" -ForegroundColor Cyan
Write-Host "  본질: .vp-param-inp-wide 의 flex: 1 가 부모 폭에 따라 줄어듦" -ForegroundColor White
Write-Host "  처방: min-width: 140px 추가 → '2024-01-01 00:00:00' 끝까지 보임" -ForegroundColor White

Write-Host ""
Write-Host "[데이터 의존성 — 코드 X]" -ForegroundColor Yellow
Write-Host "  sp_mark_delinquent: customer_id NULL" -ForegroundColor White
Write-Host "    → 추천값 contract_id=1 이 타겟에 실재하는 값 아님" -ForegroundColor DarkGray
Write-Host "    → 본부장님이 input 박스에 실제 contract_id 입력하시면 통과" -ForegroundColor DarkGray
Write-Host "  trg_bank_primary: 타겟 없음" -ForegroundColor White
Write-Host "    → AFTER trigger NEW row 제약 (이전 케이스와 같은 패턴)" -ForegroundColor DarkGray
Write-Host "    → AI 재변환 버튼 시도하면 KB 자산으로 재변환 시도" -ForegroundColor DarkGray

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  검증 — 두 화면 다시 실행" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[테이블 검증 화면]" -ForegroundColor Cyan
Write-Host "  기대: 41 불일치 → 0~3 불일치 (진짜 차이만)" -ForegroundColor Green
Write-Host "  -600,000 같은 가짜 차이 사라짐" -ForegroundColor Green
Write-Host ""
Write-Host "[오브젝트 검증 화면]" -ForegroundColor Cyan
Write-Host "  기대: 9개 ✗ → 1~3개 ✗ (진짜 변환 차이만)" -ForegroundColor Green
Write-Host "    fn_age, fn_korean_date, fn_next_business_day      → ✓ ✓ 으로 전환" -ForegroundColor Green
Write-Host "    sp_close_branch, sp_daily_batch                    → ✓ ✓ 으로 전환" -ForegroundColor Green
Write-Host "    tvf_daily_trx (소스), tvf_contract_events (소스)   → ✓ 으로 전환" -ForegroundColor Green
Write-Host ""
Write-Host "  남는 것: sp_mark_delinquent (데이터 의존)," -ForegroundColor White
Write-Host "          tvf_delinq_ranking (이름 매핑 — 다음 재이관 시 KB 효과)" -ForegroundColor White

Write-Host "`n적용 절차:" -ForegroundColor Yellow
Write-Host "  1. ZIP 풀기 (D:\project\ 위)" -ForegroundColor White
Write-Host "  2. Get-Process python | Stop-Process -Force" -ForegroundColor White
Write-Host "  3. cd D:\project\databridge_full\backend; run_backend.bat" -ForegroundColor White
Write-Host "  4. Ctrl+Shift+R" -ForegroundColor White
Write-Host "  5. 테이블·오브젝트 검증 → 화면 깨끗해짐" -ForegroundColor Green
Write-Host ""
Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
