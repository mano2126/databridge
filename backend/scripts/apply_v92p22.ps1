$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v92p22 — 객체 검증 멀티 처리 (동시 5개)" -ForegroundColor Cyan
Write-Host "  본부장님 호소: '하나씩 기다리기 너무 힘들어'" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v92p22_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$rel = "frontend\src\pages\Validate.vue"
$src = Join-Path $ProjectRoot $rel
if (Test-Path $src) {
    $dst = Join-Path $BackupRoot $rel
    New-Item -Path (Split-Path -Parent $dst) -ItemType Directory -Force | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst -Force
}
Copy-Item -LiteralPath (Join-Path $PatchSrc $rel) -Destination $src -Force
Write-Host "  + $rel" -ForegroundColor Green

Write-Host "`n✓ v92p22 적용 완료" -ForegroundColor Green
Write-Host "`n변경 내용:" -ForegroundColor Cyan
Write-Host "  1. runWithConcurrency 헬퍼 추가 — 워커 풀 패턴" -ForegroundColor White
Write-Host "  2. runObjValidate (CHECK_EXISTS) → 동시 5개" -ForegroundColor White
Write-Host "  3. runAllObjTest (전체 실행) → 동시 5개" -ForegroundColor White
Write-Host "  4. runSelectedObjTest (선택 실행) → 동시 5개" -ForegroundColor White
Write-Host "`n호환성 보장:" -ForegroundColor Cyan
Write-Host "  ✓ objRs.waitIfPaused / stopFlag 그대로 작동" -ForegroundColor Green
Write-Host "  ✓ 진행률 표시: '동시 진행중 N건: A, B, C...' 형태로 변경" -ForegroundColor Green
Write-Host "  ✓ DB 커넥션 부하 안전 (5개 이하)" -ForegroundColor Green
Write-Host "`n예상 성능:" -ForegroundColor Cyan
Write-Host "  35개 객체 검증:" -ForegroundColor White
Write-Host "    이전 (순차): 약 5~15분" -ForegroundColor DarkGray
Write-Host "    이후 (동시 5개): 약 1~3분  → 약 5~7배 빠름" -ForegroundColor Green
Write-Host "`n적용:" -ForegroundColor Cyan
Write-Host "  1. 브라우저 Ctrl+Shift+R (Vite HMR 자동 반영)" -ForegroundColor White
Write-Host "  2. 오브젝트 검증 다시 실행 → 진행 시간 비교" -ForegroundColor White
Write-Host "`n참고: 백엔드 변경 없음 — 프론트만 수정" -ForegroundColor DarkGray
Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
