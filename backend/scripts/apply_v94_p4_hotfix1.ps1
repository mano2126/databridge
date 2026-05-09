$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  v94_p4 hotfix1 — Sidebar 메뉴 복원 (긴급)" -ForegroundColor Cyan
Write-Host "  본부장님 호소: '왼쪽 메뉴 이모지 그대로, 라이브러리 메뉴 사라짐'" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v94_p4_hotfix1_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$rel = "frontend\src\components\layout\Sidebar.vue"
$src = Join-Path $ProjectRoot $rel
if (Test-Path $src) {
    $dst = Join-Path $BackupRoot $rel
    New-Item -Path (Split-Path -Parent $dst) -ItemType Directory -Force | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst -Force
}
$sf = Join-Path $PatchSrc $rel
Copy-Item -LiteralPath $sf -Destination $src -Force
Write-Host "  + $rel (복원됨)" -ForegroundColor Green

Write-Host "`n원인:" -ForegroundColor Cyan
Write-Host "  v94_p4 의 Sidebar.vue 가 마스코트만 처방하면서" -ForegroundColor White
Write-Host "  v93_LIB2/3 에서 추가됐던 두 메뉴 항목이 누락된 채 본부장님 PC 에 적용됨" -ForegroundColor White
Write-Host ""
Write-Host "복원된 메뉴 (관리자 섹션):" -ForegroundColor Cyan
Write-Host "  + 에러 프롬프트 KB    (/admin/kb)" -ForegroundColor Green
Write-Host "  + 변환 KB 대시보드    (/admin/kb/conversion)  ← 이미 있던 것 유지" -ForegroundColor White
Write-Host "  + 📚 운영자 라이브러리 (/admin/operator-library)" -ForegroundColor Green

Write-Host "`n마스코트 (사람 걷는 이모지):" -ForegroundColor Cyan
Write-Host "  v94_p4 의 변경분 살아있음 (하지만 '활성 메뉴' 우측에서만 표시됨)" -ForegroundColor White
Write-Host "  → 메뉴 복원 후 클릭하면 우측에 사람이 좌우로 걷는 애니메이션 보임" -ForegroundColor White

Write-Host "`n검증:" -ForegroundColor Yellow
Write-Host "  1. Ctrl+Shift+R" -ForegroundColor White
Write-Host "  2. 좌측 사이드바 → 관리자 섹션 펼치면 6개 메뉴:" -ForegroundColor White
Write-Host "     - 사용자 관리 / 감사 로그 / 라이선스 관리" -ForegroundColor DarkGray
Write-Host "     - 에러 프롬프트 KB / 변환 KB 대시보드 / 📚 운영자 라이브러리" -ForegroundColor DarkGray
Write-Host "  3. 아무 메뉴 클릭 → 우측에 사람 걷는 SVG 애니메이션" -ForegroundColor White

Write-Host "`n⚠ Frontend 파일 1개만 — 백엔드 영향 없음 (Vite HMR 자동)" -ForegroundColor Yellow
Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
