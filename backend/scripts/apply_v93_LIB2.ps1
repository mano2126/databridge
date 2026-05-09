$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v93_LIB2 — 운영자 라이브러리 메뉴 등록" -ForegroundColor Cyan
Write-Host "  본부장님 요청: '사이트에서 볼 수 있도록 링크 걸자'" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v93_LIB2_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "frontend\src\components\layout\Sidebar.vue",
    "frontend\src\pages\OperatorLibrary.vue",
    "frontend\src\router\index.js"
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

Write-Host "`n✓ v93_LIB2 적용 완료" -ForegroundColor Green
Write-Host "`n변경 내용:" -ForegroundColor Cyan
Write-Host "  1. Sidebar.vue 의 관리자 메뉴 보강" -ForegroundColor White
Write-Host "     - 📚 운영자 라이브러리 (신규 추가)" -ForegroundColor Green
Write-Host "     - 에러 프롬프트 KB (메뉴 누락이었던 항목 추가)" -ForegroundColor Green
Write-Host "  2. router/index.js — /admin/operator-library 라우터 (재포함)" -ForegroundColor White
Write-Host "  3. OperatorLibrary.vue — 35개 명령 카드 (재포함)" -ForegroundColor White
Write-Host "`n사이드바 관리자 메뉴 (변경 후):" -ForegroundColor Cyan
Write-Host "  ▸ 사용자 관리" -ForegroundColor DarkGray
Write-Host "    - 감사 로그" -ForegroundColor DarkGray
Write-Host "    - 라이선스 관리" -ForegroundColor DarkGray
Write-Host "    - 에러 프롬프트 KB         ← 신규 메뉴 노출" -ForegroundColor Yellow
Write-Host "    - 변환 KB 대시보드" -ForegroundColor DarkGray
Write-Host "    - 📚 운영자 라이브러리      ← 신규 메뉴 노출" -ForegroundColor Yellow
Write-Host "`n적용 절차:" -ForegroundColor Cyan
Write-Host "  1. Ctrl+Shift+R (Vite HMR 자동 반영)" -ForegroundColor White
Write-Host "  2. 좌측 사이드바 → '관리자' 섹션 펼치기" -ForegroundColor White
Write-Host "  3. '📚 운영자 라이브러리' 클릭" -ForegroundColor White
Write-Host "`n⚠ admin 역할 가진 계정만 메뉴에 보임" -ForegroundColor Yellow
Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
