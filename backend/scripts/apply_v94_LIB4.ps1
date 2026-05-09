$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v94_LIB4 — 운영자 라이브러리 시스템 운영 + 강화 필터" -ForegroundColor Cyan
Write-Host "  본부장님 요청:" -ForegroundColor Yellow
Write-Host "    1. ROOT 입력 절반 축소" -ForegroundColor White
Write-Host "    2. 조회 조건 강화" -ForegroundColor White
Write-Host "    3. 메모리/시스템 운영 메뉴 (Windows + Linux)" -ForegroundColor White
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v94_LIB4_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "frontend\src\pages\OperatorLibrary.vue",
    "frontend\src\pages\operatorLibraryData.js"
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

Write-Host "`n✓ v94_LIB4 적용 완료 (187 → 214 명령, 12 → 13 카테고리)" -ForegroundColor Green

Write-Host "`n변경 요약:" -ForegroundColor Cyan
Write-Host "  1. ROOT 입력 절반 축소 (280px → 180px 고정)" -ForegroundColor White
Write-Host "     - 라벨 '📁 프로젝트 ROOT' → 아이콘 '📁' 만" -ForegroundColor DarkGray
Write-Host "     - '초기화' 버튼 → '↺' 아이콘" -ForegroundColor DarkGray
Write-Host "  2. 조회 조건 4종 강화 (세트형 select + 토글)" -ForegroundColor White
Write-Host "     - Shell: 전체 / PowerShell / CMD / Bash / SQL" -ForegroundColor DarkGray
Write-Host "     - 위험도: 전체 / 안전 / 주의 / 위험" -ForegroundColor DarkGray
Write-Host "     - OS: 전체 / Windows / Linux / 공통" -ForegroundColor DarkGray
Write-Host "     - 즐겨찾기: ☆ 전체 / ⭐ 즐겨찾기만" -ForegroundColor DarkGray
Write-Host "     - '✕ 필터 초기화' (활성 필터 있을 때만 표시)" -ForegroundColor DarkGray
Write-Host "  3. 신규 카테고리: 🖥 시스템 운영 (27개 명령)" -ForegroundColor White
Write-Host "     ─── 메모리 관리 (Windows) ───" -ForegroundColor DarkGray
Write-Host "       · 메모리 상태 / 정리 (대기 메모리 회수) / Top 10 / 페이지 파일" -ForegroundColor DarkGray
Write-Host "     ─── 메모리 관리 (Linux) ───" -ForegroundColor DarkGray
Write-Host "       · free -h / drop_caches / swap 정리 / ps Top" -ForegroundColor DarkGray
Write-Host "     ─── 시스템 모니터링 ───" -ForegroundColor DarkGray
Write-Host "       · Performance Counter (Win) / top, htop, iostat (Linux)" -ForegroundColor DarkGray
Write-Host "     ─── WSL/Docker 메모리 ───" -ForegroundColor DarkGray
Write-Host "       · WSL shutdown / docker prune / 컨테이너 재시작" -ForegroundColor DarkGray
Write-Host "     ─── 서비스 관리 ───" -ForegroundColor DarkGray
Write-Host "       · Windows: Get-Service / Linux: systemctl, journalctl" -ForegroundColor DarkGray
Write-Host "     ─── 디스크 정리 ───" -ForegroundColor DarkGray
Write-Host "       · Win: Temp + 휴지통 / Linux: apt clean + journal vacuum" -ForegroundColor DarkGray
Write-Host "     ─── 네트워크 / 시간 ───" -ForegroundColor DarkGray
Write-Host "       · 네트워크 스택 초기화 / NTP 시간 동기화" -ForegroundColor DarkGray
Write-Host "     ─── 시스템 재시작 ───" -ForegroundColor DarkGray
Write-Host "       · Job 진행 확인 후 안전 재시작 (Win/Linux 별)" -ForegroundColor DarkGray
Write-Host "     ─── 환경 정보 ───" -ForegroundColor DarkGray
Write-Host "       · 종합 시스템 정보 한 번에 (Win/Linux 별)" -ForegroundColor DarkGray

Write-Host "`n4. 명령 카드 강화:" -ForegroundColor Cyan
Write-Host "   - OS 배지 (🪟 Win / 🐧 Linux / 🔀 공통) — 색상 구분" -ForegroundColor White
Write-Host "   - 즐겨찾기 별표 (⭐) — localStorage 보존, 클릭으로 토글" -ForegroundColor White

Write-Host "`n전체 카테고리 분포 (총 214개):" -ForegroundColor Cyan
Write-Host "  🚀 시작/종료      12개" -ForegroundColor White
Write-Host "  🔍 진단 명령      23개" -ForegroundColor White
Write-Host "  🛠 패치 관리      10개" -ForegroundColor White
Write-Host "  📊 KB/통계        14개" -ForegroundColor White
Write-Host "  🗄 DB 명령        28개" -ForegroundColor White
Write-Host "  🐛 트러블슈팅     22개" -ForegroundColor White
Write-Host "  🔐 보안/감사      16개" -ForegroundColor White
Write-Host "  📈 성능 튜닝      16개" -ForegroundColor White
Write-Host "  🖥 시스템 운영    27개  ← 신규" -ForegroundColor Green
Write-Host "  💾 백업/복구      12개" -ForegroundColor White
Write-Host "  📦 배포           10개" -ForegroundColor White
Write-Host "  📋 일상 운영      12개" -ForegroundColor White
Write-Host "  🎓 학습/레퍼런스  12개" -ForegroundColor White

Write-Host "`n구매자 데모 시나리오:" -ForegroundColor Yellow
Write-Host "  1. '🖥 시스템 운영' 클릭 → 27개 메모리/디스크/서비스 명령" -ForegroundColor White
Write-Host "  2. OS 필터: Linux 선택 → Linux 환경 운영자에게도 즉시 활용 가능" -ForegroundColor White
Write-Host "  3. 위험도 필터: 위험 → 13개 danger 명령만 → 운영 교육 자료" -ForegroundColor White
Write-Host "  4. 즐겨찾기 추가 → 자주 쓰는 명령 PDF 출력 시 분리" -ForegroundColor White
Write-Host "  5. 검색 'memory' → 메모리 관련 모든 명령 즉시" -ForegroundColor White

Write-Host "`n⚠ 백엔드 변경 없음 — Ctrl+Shift+R 만으로 반영" -ForegroundColor Yellow
Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
