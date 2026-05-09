$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v93_B — 객체 검증 잔존 3건 본질 처방" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v93_B_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$rel = "backend\app\api\routes\schema.py"
$src = Join-Path $ProjectRoot $rel
if (Test-Path $src) {
    $dst = Join-Path $BackupRoot $rel
    New-Item -Path (Split-Path -Parent $dst) -ItemType Directory -Force | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst -Force
}
Copy-Item -LiteralPath (Join-Path $PatchSrc $rel) -Destination $src -Force

$r = & python -c "import ast; ast.parse(open(r'$src',encoding='utf-8').read()); print('OK')" 2>&1
if ($r -match "OK") {
    Write-Host "`n✓ v93_B 적용 완료" -ForegroundColor Green
    Write-Host "`n변경 내용 (2가지 본질 처방):" -ForegroundColor Cyan
    Write-Host "  [1] FUNCTION 호출 자동 라우팅" -ForegroundColor Yellow
    Write-Host "      대상: tvf_daily_trx, tvf_delinq_ranking" -ForegroundColor White
    Write-Host "      기존: obj_name 이 'tvf_' 로 시작할 때만 CALL 사용" -ForegroundColor DarkGray
    Write-Host "      처방: information_schema.ROUTINES 의 ROUTINE_TYPE 자동 감지 → CALL/SELECT 자동 분기" -ForegroundColor White
    Write-Host "      효과: 'settlement_tvf_daily_trx' (PROCEDURE 변환됨) 도 자동 인식" -ForegroundColor Green
    Write-Host "  [2] _find_column_sample PK 우선 매칭" -ForegroundColor Yellow
    Write-Host "      대상: sp_mark_delinquent (@contract_id)" -ForegroundColor White
    Write-Host "      기존: 'contract_id' 컬럼 가진 첫 테이블의 값 사용 → 비즈니스 정합성 안 맞음" -ForegroundColor DarkGray
    Write-Host "      처방: PK 컬럼 우선 검색 (information_schema.KEY_COLUMN_USAGE + TABLE_CONSTRAINTS)" -ForegroundColor White
    Write-Host "      효과: credit.contract.contract_id (PK) 의 진짜 값 가져옴 → customer_id NOT NULL" -ForegroundColor Green
    Write-Host "`n잔존 3건 처방 결과 (예상):" -ForegroundColor Cyan
    Write-Host "  ✓ tvf_daily_trx → 자동 라우팅 → 양쪽 모두 ✓ 성공" -ForegroundColor Green
    Write-Host "  ✓ tvf_delinq_ranking → 자동 라우팅 → 양쪽 모두 ✓ 성공" -ForegroundColor Green
    Write-Host "  ✓ sp_mark_delinquent → PK 우선 샘플 → 양쪽 모두 ✓ 성공" -ForegroundColor Green
    Write-Host "`n⚠ 백엔드 재시작 + Ctrl+Shift+R + 'AAAA...' 캐시값 초기화 후 재테스트" -ForegroundColor Yellow
    Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
} else {
    Write-Host "`n✗ syntax FAIL: $r" -ForegroundColor Red
    exit 1
}
