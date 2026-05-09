$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v93_LIB — 운영자 라이브러리 페이지" -ForegroundColor Cyan
Write-Host "  본부장님 통찰: '망분리 환경에서 AI 도움 없이도 셀프 운영'" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v93_LIB_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
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

Write-Host "`n✓ v93_LIB 적용 완료" -ForegroundColor Green
Write-Host "`n변경 내용:" -ForegroundColor Cyan
Write-Host "  1. OperatorLibrary.vue 신규 — 운영자 셀프 매뉴얼" -ForegroundColor White
Write-Host "     - 8개 카테고리: 시작/종료, 진단, 패치, KB/통계, DB, 트러블슈팅, 배포, 일상 운영" -ForegroundColor DarkGray
Write-Host "     - 35개 명령 (본부장님과 작업하면서 사용한 모든 명령)" -ForegroundColor DarkGray
Write-Host "     - 프로젝트 ROOT 입력 시 모든 명령에 자동 치환" -ForegroundColor DarkGray
Write-Host "     - PowerShell / cmd / bash / sql 구분 배지" -ForegroundColor DarkGray
Write-Host "     - 검색 + 카테고리 필터 + 관련 명령 cross-link" -ForegroundColor DarkGray
Write-Host "     - 위험도 표시 (warn / danger)" -ForegroundColor DarkGray
Write-Host "     - 1클릭 복사 / 인쇄 최적화 (PDF 출력 가능)" -ForegroundColor DarkGray
Write-Host "  2. router/index.js — /admin/operator-library 라우터 등록" -ForegroundColor White
Write-Host "`n접근 경로:" -ForegroundColor Cyan
Write-Host "  메뉴: 관리자 → 운영자 라이브러리" -ForegroundColor White
Write-Host "  URL : http://localhost:3000/admin/operator-library" -ForegroundColor White
Write-Host "  특정 명령 직접 링크: /admin/operator-library#cmd=verify_patches" -ForegroundColor DarkGray
Write-Host "`n망분리 환경 활용:" -ForegroundColor Cyan
Write-Host "  1. 페이지 열기 → ROOT 경로 입력" -ForegroundColor White
Write-Host "  2. Ctrl+P → PDF 로 저장 → 폐쇄망 PC 에 복사" -ForegroundColor White
Write-Host "  3. AI 없이도 운영자가 명령 찾아서 즉시 실행 가능" -ForegroundColor White
Write-Host "`n8개 카테고리 명령 분포:" -ForegroundColor Cyan
Write-Host "  🚀 시작/종료      6개" -ForegroundColor White
Write-Host "  🔍 진단 명령      8개" -ForegroundColor White
Write-Host "  🛠 패치 관리      4개" -ForegroundColor White
Write-Host "  📊 KB/통계        5개" -ForegroundColor White
Write-Host "  🗄 DB 명령        7개" -ForegroundColor White
Write-Host "  🐛 트러블슈팅     5개" -ForegroundColor White
Write-Host "  📦 배포           3개" -ForegroundColor White
Write-Host "  📋 일상 운영      5개" -ForegroundColor White
Write-Host "`n⚠ 백엔드 변경 없음 — 프론트만 수정 (Ctrl+Shift+R 만으로 반영)" -ForegroundColor Yellow
Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
