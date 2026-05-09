$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v94_p4 — KB Pre-Apply (사전 학습 적용) + 메뉴 마스코트" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v94_p4_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "backend\app\engine\error_kb.py",
    "backend\app\api\routes\schema.py",
    "frontend\src\components\layout\Sidebar.vue"
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

Write-Host "`n✓ v94_p4 적용 완료" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  Part 1 — KB Pre-Apply (본부장님 호소 본질 처방)" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "본부장님 의심 — '매번 똑같은 1차 에러 — KB 학습이 안 되는가?'" -ForegroundColor White
Write-Host "정직한 답: 의심이 정확함." -ForegroundColor Red
Write-Host ""
Write-Host "기존 KB 작동 (v92~v93):" -ForegroundColor Cyan
Write-Host "  1차 변환 (KB 힌트 없음, has_error_hint=False, prompt 2020 chars)" -ForegroundColor White
Write-Host "    ↓ 에러 발생" -ForegroundColor White
Write-Host "  KB 매칭 (그 에러 메시지로 사후 검색)" -ForegroundColor White
Write-Host "    ↓" -ForegroundColor White
Write-Host "  2차 변환 (has_error_hint=True, prompt 2250 chars)" -ForegroundColor White
Write-Host "    ↓ 성공" -ForegroundColor White
Write-Host ""
Write-Host "→ 사후 처방 모드 — 학습 자산이 깨끗한 1차에는 적용 안 됨" -ForegroundColor Yellow
Write-Host ""
Write-Host "v94_p4 처방 — Pre-Apply Mode:" -ForegroundColor Cyan
Write-Host "  1차 변환 직전:" -ForegroundColor White
Write-Host "  ┌─ obj_type + DDL 시그니처 추출 (TVF/AFTER_UPDATE_NEW/...)" -ForegroundColor DarkGray
Write-Host "  ├─ error_cases.txt 검색 (같은 시그니처 과거 케이스)" -ForegroundColor DarkGray
Write-Host "  ├─ yml 정식 KB 패턴 중 obj_type 매칭되는 것" -ForegroundColor DarkGray
Write-Host "  └─ 두 자산의 fix_prompt 들을 1차 prompt 에 사전 주입" -ForegroundColor DarkGray
Write-Host "    ↓" -ForegroundColor White
Write-Host "  → 1차에서 미리 회피 (이론상 1차 통과 가능)" -ForegroundColor Green
Write-Host ""
Write-Host "감지하는 위험 시그니처:" -ForegroundColor Cyan
Write-Host "  FUNCTION  : TVF, WHILE_EXISTS, WHILE_SUBQUERY" -ForegroundColor DarkGray
Write-Host "  TRIGGER   : AFTER_UPDATE_NEW (1362 에러), INSERTED_DELETED" -ForegroundColor DarkGray
Write-Host "  PROCEDURE : DECLARE_SUBQUERY (DECLARE @v=(SELECT...)), SET_NOCOUNT" -ForegroundColor DarkGray
Write-Host "  공통       : DATETIME2, SYSDATETIME, IDENTITY_FN, TOP_CLAUSE" -ForegroundColor DarkGray
Write-Host ""
Write-Host "검증 방법:" -ForegroundColor Yellow
Write-Host "  1. 새 이관 실행" -ForegroundColor White
Write-Host "  2. 백엔드 로그에서 다음 마커 확인:" -ForegroundColor White
Write-Host "     [AI-TRACE 01b-preflight-applied] preflight_len=N" -ForegroundColor Green
Write-Host "  3. 1차 prompt_len 이 기존보다 길어졌는지 (KB 누적 자산만큼)" -ForegroundColor White
Write-Host "  4. 1차 시도가 통과되거나 (이상적), 2차에서 더 빠르게 처방됨" -ForegroundColor White

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  Part 2 — 메뉴 마스코트 (사람 걷는 이모지)" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "발견: 마스코트 시스템이 이미 구축돼 있었음 (v10)" -ForegroundColor Cyan
Write-Host "  → 활성 메뉴 우측에 SVG 사람이 걸어다니는 애니메이션" -ForegroundColor White
Write-Host "  → 본부장님 화면에 안 보이신 이유는 'mascot=none' 설정 가능성" -ForegroundColor White
Write-Host ""
Write-Host "처방: 항상 person 마스코트 표시 (설정 무시 — 본부장님 요청 우선)" -ForegroundColor Cyan
Write-Host "  - 활성 메뉴 클릭 시 → 우측에 사람 SVG 가 좌우로 걸어다님" -ForegroundColor White
Write-Host "  - 6초 주기로 왼쪽 → 오른쪽 → 좌우반전 → 왼쪽 왕복" -ForegroundColor White
Write-Host "  - 팔/다리 별도 애니메이션 (걷는 동작)" -ForegroundColor White

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  적용 절차" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  1. ZIP 풀기 (D:\project\ 위)" -ForegroundColor White
Write-Host "  2. Get-Process python | Stop-Process -Force" -ForegroundColor White
Write-Host "  3. cd D:\project\databridge_full\backend; run_backend.bat" -ForegroundColor White
Write-Host "  4. Ctrl+Shift+R" -ForegroundColor White

Write-Host "`n⚠ 백엔드 변경 있음 — 재시작 필요" -ForegroundColor Yellow
Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
