$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v92p23 — 동시 검증 셀렉트 박스 + 테이블 검증 멀티" -ForegroundColor Cyan
Write-Host "  본부장님 요청: 검증 실행 왼쪽 셀렉트 박스 + 테이블 검증도 적용" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v92p23_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "backend\app\api\routes\validate.py",
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

$pyFile = Join-Path $ProjectRoot "backend\app\api\routes\validate.py"
$r = & python -c "import ast; ast.parse(open(r'$pyFile',encoding='utf-8').read()); print('OK')" 2>&1

if ($r -match "OK") {
    Write-Host "`n✓ v92p23 적용 완료" -ForegroundColor Green
    Write-Host "`n변경 내용:" -ForegroundColor Cyan
    Write-Host "  [프론트]" -ForegroundColor Yellow
    Write-Host "    1. 검증 실행 버튼 왼쪽에 셀렉트 박스 추가" -ForegroundColor White
    Write-Host "       옵션: 1 (순차) / 3 / 5 (기본) / 10 / 20" -ForegroundColor DarkGray
    Write-Host "    2. localStorage 저장 — 다음 세션도 동일 값 유지" -ForegroundColor White
    Write-Host "    3. 객체 검증 3곳 모두 셀렉트 값 적용 (v92p22 의 5 → 가변)" -ForegroundColor White
    Write-Host "    4. 테이블 검증 body 에 concurrency 추가하여 백엔드로 전송" -ForegroundColor White
    Write-Host "  [백엔드]" -ForegroundColor Yellow
    Write-Host "    5. /run/stream 에 concurrency 파라미터 받기" -ForegroundColor White
    Write-Host "    6. ThreadPoolExecutor + asyncio.Semaphore 워커 풀" -ForegroundColor White
    Write-Host "    7. 각 워커 = 자체 connection 쌍 (DB 부하 = concurrency × 2)" -ForegroundColor White
    Write-Host "    8. concurrency=1 시 순차 모드 (기존 동작 보존)" -ForegroundColor White
    Write-Host "`n예상 성능 (테이블 100개 × 평균 1초 작업):" -ForegroundColor Cyan
    Write-Host "  순차 (1):   100초" -ForegroundColor DarkGray
    Write-Host "  동시 5:      20초 → 5배" -ForegroundColor Green
    Write-Host "  동시 10:     10초 → 10배" -ForegroundColor Green
    Write-Host "  동시 20:      5초 → 20배 (대형 환경)" -ForegroundColor Green
    Write-Host "`n주의 사항:" -ForegroundColor Yellow
    Write-Host "  - DB connection pool 부하 = concurrency × 2 (소스 + 타겟)" -ForegroundColor White
    Write-Host "  - 본부장님 환경 DB max_connections 확인 권장" -ForegroundColor White
    Write-Host "  - 처음엔 5로 시작 → 안정 시 점진적 증가" -ForegroundColor White
    Write-Host "`n적용 절차:" -ForegroundColor Cyan
    Write-Host "  1. 백엔드 재시작 (validate.py 변경)" -ForegroundColor White
    Write-Host "  2. 브라우저 Ctrl+Shift+R" -ForegroundColor White
    Write-Host "  3. 검증 실행 버튼 왼쪽에 [동시 ▼] 셀렉트 박스 확인" -ForegroundColor White
    Write-Host "  4. 5/10/20 등 변경 후 검증 실행 → 시간 비교" -ForegroundColor White
    Write-Host "`n롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
} else {
    Write-Host "`n✗ syntax FAIL: $r" -ForegroundColor Red
    exit 1
}
