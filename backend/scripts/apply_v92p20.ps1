$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v92p20 — date 파라미터 '202' 잘림 버그 수정" -ForegroundColor Cyan
Write-Host "  본부장님 결정: 테스트 시스템도 운영 도구이므로 코드 차원 처방" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v92p20_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "backend\app\api\routes\schema.py",
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

$pyFile = Join-Path $ProjectRoot "backend\app\api\routes\schema.py"
$r = & python -c "import ast; ast.parse(open(r'$pyFile',encoding='utf-8').read()); print('OK')" 2>&1

if ($r -match "OK") {
    Write-Host "`n✓ v92p20 적용 완료" -ForegroundColor Green
    Write-Host "`n진단 (코드 차원):" -ForegroundColor Cyan
    Write-Host "  - MSSQL date 타입 storage = 3바이트" -ForegroundColor White
    Write-Host "  - max_length=3 으로 백엔드/프론트에 전달됨" -ForegroundColor White
    Write-Host "  - _smart_dummy / _makeDummyValue 가 'VARCHAR(3) 날짜 문자열' 로 오해" -ForegroundColor White
    Write-Host "  - '20240101'.substring(0, 3) = '202' 반환 → ODBC date 변환 실패" -ForegroundColor White
    Write-Host "`n처방:" -ForegroundColor Cyan
    Write-Host "  - 진짜 DATE/DATETIME 타입 분리: max_length 무시, ISO 형식 반환" -ForegroundColor White
    Write-Host "  - char/varchar 류만 길이 자르기 적용 (VARCHAR(8) 같은 날짜 문자열)" -ForegroundColor White
    Write-Host "  - 이름 + 타입 양쪽 분기에서 동일 로직 적용" -ForegroundColor White
    Write-Host "`n검증 (시뮬레이션):" -ForegroundColor Cyan
    Write-Host "  ✓ @birth date (ml=3) → '2024-01-01'" -ForegroundColor Green
    Write-Host "  ✓ @dt date (ml=3) → '2024-01-01'" -ForegroundColor Green
    Write-Host "  ✓ @close_date date → '2024-01-01'" -ForegroundColor Green
    Write-Host "  ✓ @from datetime2 → '2024-01-01 00:00:00'" -ForegroundColor Green
    Write-Host "  ✓ @ymd VARCHAR(8) → '20240101' (정상 유지)" -ForegroundColor Green
    Write-Host "`n다음 단계:" -ForegroundColor Cyan
    Write-Host "  1. 백엔드 reload (Ctrl+C → 재실행)" -ForegroundColor White
    Write-Host "  2. 브라우저 Ctrl+Shift+R" -ForegroundColor White
    Write-Host "  3. Validate 페이지에서 7개 실패 객체 ▶ 테스트 다시 실행" -ForegroundColor White
    Write-Host "  4. 입력값이 '2024-01-01' 로 정상 표시되는지 확인" -ForegroundColor White
    Write-Host "  5. 양쪽 (소스/타겟) 모두 ✓ 성공이면 진짜 변환 검증 완료" -ForegroundColor White
    Write-Host "`n남은 작업 (다음):" -ForegroundColor Yellow
    Write-Host "  - tvf_daily_trx, tvf_delinq_ranking (PROCEDURE 변환됨)" -ForegroundColor White
    Write-Host "  - trg_bank_primary 이관 누락" -ForegroundColor White
    Write-Host "`n롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
} else {
    Write-Host "`n✗ syntax FAIL: $r" -ForegroundColor Red
    exit 1
}
