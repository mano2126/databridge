$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  v94_p4 hotfix2 — 마스코트 우측 끝 고정 + 글자 잘림 방지" -ForegroundColor Cyan
Write-Host "  본부장님 호소: '메뉴 우측에 붙여달라, 글자가 잘리지 않게'" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v94_p4_hotfix2_$ts"
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
Write-Host "  + $rel" -ForegroundColor Green

Write-Host "`n원인:" -ForegroundColor Cyan
Write-Host "  마스코트 lane 이 'flex: 1 + min-width: 80px' 라" -ForegroundColor White
Write-Host "  글자 영역까지 침범 → '운영자 라...' 처럼 글자 잘림" -ForegroundColor White

Write-Host "`n변경 (CSS 4가지):" -ForegroundColor Cyan
Write-Host "  1. .ni-mascot-lane:" -ForegroundColor White
Write-Host "     position: absolute / right: 6px / width: 18px (사람 SVG 크기만큼)" -ForegroundColor DarkGray
Write-Host "     → 메뉴 박스 우측 끝에 고정, 글자 영역 침범 X" -ForegroundColor DarkGray
Write-Host "  2. z-index: 2 → 글자 위에 떠 있되 영역은 안 차지" -ForegroundColor White
Write-Host "  3. .ni.active .ni-label { padding-right: 22px; }" -ForegroundColor White
Write-Host "     → 활성 메뉴의 글자 우측에 22px 여유 (마스코트 자리)" -ForegroundColor DarkGray
Write-Host "  4. mascot-walk-stationary 키프레임:" -ForegroundColor White
Write-Host "     좌우 이동 X, 제자리에서 살짝 위아래만 (1px) — 자연스러운 걷는 모션" -ForegroundColor DarkGray

Write-Host "`n결과 (개념도):" -ForegroundColor Cyan
Write-Host "  변경 전: |📚 운영자 라...    🚶  |    ← 글자 잘림" -ForegroundColor Red
Write-Host "  변경 후: |📚 운영자 라이브러리       🚶|  ← 글자 온전, 마스코트 우측 끝" -ForegroundColor Green

Write-Host "`n검증:" -ForegroundColor Yellow
Write-Host "  1. Ctrl+Shift+R" -ForegroundColor White
Write-Host "  2. '운영자 라이브러리' 메뉴 클릭" -ForegroundColor White
Write-Host "  3. 글자가 끝까지 보이고, 우측 끝에 사람이 제자리 걷는 애니메이션" -ForegroundColor White

Write-Host "`n⚠ Frontend 1 파일 — 백엔드 영향 없음" -ForegroundColor Yellow
Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
