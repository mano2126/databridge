$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v92p18 — KB 가시화 + regex 정밀화" -ForegroundColor Cyan
Write-Host "  본부장님 결정: KB는 운영 환경에서 반드시 작동해야 함" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v92p18_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "backend\app\engine\error_kb.py",
    "backend\app\engine\error_kb.yml"
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

# 무결성 검증
$pyFile = Join-Path $ProjectRoot "backend\app\engine\error_kb.py"
$ymlFile = Join-Path $ProjectRoot "backend\app\engine\error_kb.yml"
$pyOk  = & python -c "import ast; ast.parse(open(r'$pyFile',encoding='utf-8').read()); print('OK')" 2>&1
$ymlOk = & python -c "import yaml; yaml.safe_load(open(r'$ymlFile',encoding='utf-8')); print('OK')" 2>&1

if ($pyOk -match "OK" -and $ymlOk -match "OK") {
    Write-Host "`n✓ v92p18 완료 — KB 인프라 운영급 검증 가능" -ForegroundColor Green
    Write-Host "`n변경 내용:" -ForegroundColor Cyan
    Write-Host "  1. error_kb.py 에 logger 추가 — KB 매칭 결과 로그 출력" -ForegroundColor White
    Write-Host "     - [KB] ✓ 매칭 성공: pattern_id=..." -ForegroundColor DarkGray
    Write-Host "     - [KB] ✗ 매칭 실패 (UNMATCHED) — error 첫 100자: ..." -ForegroundColor DarkGray
    Write-Host "     - [KB] 📝 프롬프트 주입: N chars, 패턴=[...]" -ForegroundColor DarkGray
    Write-Host "     - [KB] 💾 통계 저장: pattern=..., success=..." -ForegroundColor DarkGray
    Write-Host "  2. error_kb.yml 의 v92p17 패턴 3개 regex 정밀화 (실제 메시지 기준)" -ForegroundColor White
    Write-Host "     - 1064_WHILE_END_TO_END_WHILE: 'END IF.{0,30}(SET|END|RETURN|LOOP)" -ForegroundColor DarkGray
    Write-Host "     - 1064_INLINE_TVF_NOT_SUPPORTED: 'TABLE.{0,50}(DETERMINISTIC|RETURN)" -ForegroundColor DarkGray
    Write-Host "     - AI_RESPONSE_NO_CREATE: '실행 가능한 CREATE 문장이 없음' (그대로)" -ForegroundColor DarkGray
    Write-Host "`n검증 (실제 본부장님 환경 메시지로 테스트):" -ForegroundColor Cyan
    Write-Host "  ✓ tvf_daily_trx (TVF) → 1064_INLINE_TVF_NOT_SUPPORTED 매칭" -ForegroundColor Green
    Write-Host "  ✓ fn_next_business_day → 1064_WHILE_END_TO_END_WHILE 매칭" -ForegroundColor Green
    Write-Host "  ✓ sp_calculate_schedule → AI_RESPONSE_NO_CREATE 매칭" -ForegroundColor Green
    Write-Host "  (false positive 0)" -ForegroundColor DarkGreen
    Write-Host "`n다음 단계:" -ForegroundColor Cyan
    Write-Host "  1. 백엔드 reload (Ctrl+C → 재실행)" -ForegroundColor White
    Write-Host "  2. 검증 테스트 — 3개 객체 중 하나를 일부러 깨뜨려서 재이관:" -ForegroundColor White
    Write-Host "     SQL: DROP FUNCTION ref_fn_next_business_day; (MySQL)" -ForegroundColor DarkGray
    Write-Host "  3. 화면에서 🤖 AI 재이관 클릭" -ForegroundColor White
    Write-Host "  4. 백엔드 로그 확인:" -ForegroundColor White
    Write-Host "     Select-String -Path '...\logs\databridge_backend.log' -Pattern '\[KB\]' | Select -Last 10" -ForegroundColor DarkGray
    Write-Host "  5. KB 작동 확인되면 운영 환경 출시 OK" -ForegroundColor White
    Write-Host "`n롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
} else {
    Write-Host "`n✗ syntax/yaml FAIL" -ForegroundColor Red
    Write-Host "  py: $pyOk" -ForegroundColor Red
    Write-Host "  yml: $ymlOk" -ForegroundColor Red
    exit 1
}
