$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v92p17 — KB 패턴 3개 등록" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v92p17_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "backend\app\engine\error_kb.yml",
    "backend\prompts\mssql_to_mysql\error_cases.txt",
    "backend\prompts\mssql_to_mysql\function.txt",
    "backend\prompts\mssql_to_mysql\procedure.txt"
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

# YAML 검증
$ymlFile = Join-Path $ProjectRoot "backend\app\engine\error_kb.yml"
$r = & python -c "import yaml; yaml.safe_load(open(r'$ymlFile',encoding='utf-8')); print('OK')" 2>&1
if ($r -match "OK") {
    Write-Host "`n════════════════════════════════════════════════" -ForegroundColor Green
    Write-Host "  ✓ v92p17 완료 — KB 18개 패턴 활성화 (3개 신규)" -ForegroundColor Green
    Write-Host "════════════════════════════════════════════════" -ForegroundColor Green
    Write-Host "`n등록된 신규 패턴:" -ForegroundColor Cyan
    Write-Host "  1. 1064_WHILE_END_TO_END_WHILE — WHILE 루프 IF/END IF 잘못 삽입" -ForegroundColor White
    Write-Host "  2. 1064_INLINE_TVF_NOT_SUPPORTED — 인라인 TVF → VIEW/PROCEDURE 재설계" -ForegroundColor White
    Write-Host "  3. AI_RESPONSE_NO_CREATE — AI 응답 형식 강제 (자연어 금지)" -ForegroundColor White
    Write-Host "`n적용 파일:" -ForegroundColor Cyan
    Write-Host "  - error_kb.yml: AI 프롬프트에 자동 주입되는 처방" -ForegroundColor White
    Write-Host "  - error_cases.txt: 케이스별 before/after 누적 (1270 lines)" -ForegroundColor White
    Write-Host "  - function.txt: WHILE / TVF 변환 예시 추가" -ForegroundColor White
    Write-Host "  - procedure.txt: 다중 DECLARE / SELECT INTO 예시 추가" -ForegroundColor White
    Write-Host "`n다음 단계:" -ForegroundColor Cyan
    Write-Host "  1. 백엔드 reload (uvicorn --reload 면 자동)" -ForegroundColor White
    Write-Host "  2. 3개 객체 (fn_next_business_day, tvf_daily_trx, sp_calculate_schedule)" -ForegroundColor White
    Write-Host "     의 🤖 AI 재이관 클릭" -ForegroundColor White
    Write-Host "  3. AI 가 KB 처방 받아 새 변환 시도 → 통과 기대" -ForegroundColor White
    Write-Host "`n동작 원리:" -ForegroundColor DarkCyan
    Write-Host "  AI 재이관 시 → error_kb.match_error() → 패턴 매칭 →" -ForegroundColor DarkGray
    Write-Host "  → assemble_prompt_hint() → AI 프롬프트에 fix_prompt 자동 주입 →" -ForegroundColor DarkGray
    Write-Host "  → AI 가 가이드 받아 정확하게 변환 → 1회 통과" -ForegroundColor DarkGray
    Write-Host "`n롤백:" -ForegroundColor DarkYellow
    Write-Host "  Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
} else {
    Write-Host "`n✗ YAML FAIL: $r" -ForegroundColor Red
    exit 1
}
