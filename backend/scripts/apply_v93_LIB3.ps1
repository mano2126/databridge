$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v93_LIB3 — 운영자 라이브러리 운영급 확장 (35 → 187)" -ForegroundColor Cyan
Write-Host "  본부장님 요청: '구매자가 신경 많이 썼다고 인정할 수준'" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v93_LIB3_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "frontend\src\pages\OperatorLibrary.vue",
    "frontend\src\pages\operatorLibraryData.js",
    "frontend\src\components\layout\Sidebar.vue",
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

Write-Host "`n✓ v93_LIB3 적용 완료" -ForegroundColor Green
Write-Host "`n변경 내용:" -ForegroundColor Cyan
Write-Host "  1. operatorLibraryData.js 신규 — 187개 명령 데이터 분리" -ForegroundColor White
Write-Host "  2. OperatorLibrary.vue — 데이터 import 방식으로 단순화 (976→466라인)" -ForegroundColor White
Write-Host "  3. Sidebar/router — v93_LIB2 의 메뉴 등록 유지" -ForegroundColor White

Write-Host "`n12개 카테고리 명령 분포 (총 187개):" -ForegroundColor Cyan
Write-Host "  🚀 시작/종료      12개  (SAFE/MULTIPROCESS, venv 재생성, 포트 종료...)" -ForegroundColor White
Write-Host "  🔍 진단 명령      23개  (헬스체크, 로그 실시간, DB 응답성, 네트워크...)" -ForegroundColor White
Write-Host "  🛠 패치 관리      10개  (적용/롤백/검증/diff/일괄 적용/이력 추적)" -ForegroundColor White
Write-Host "  📊 KB/통계        14개  (CSV export, 핫 리로드, 미매칭 후보, 자산 백업)" -ForegroundColor White
Write-Host "  🗄 DB 명령        28개  (인덱스/FK/락/슬로우/ANALYZE/REPAIR/charset)" -ForegroundColor White
Write-Host "  🐛 트러블슈팅     22개  (DB 연결/한글/AI 루프/디스크/vmmem/SSL/CORS...)" -ForegroundColor White
Write-Host "  🔐 보안/감사      16개  (KISA 6항목, 민감정보, API key, SSL 인증서)" -ForegroundColor White
Write-Host "  📈 성능 튜닝      16개  (버퍼풀, 누락/중복 인덱스, EXPLAIN ANALYZE...)" -ForegroundColor White
Write-Host "  💾 백업/복구      12개  (FULL/DIFF/PIT/원격NAS/회전/검증)" -ForegroundColor White
Write-Host "  📦 배포           10개  (오프라인pip/Docker export/systemd/IIS/롤링)" -ForegroundColor White
Write-Host "  📋 일상 운영      12개  (헬스체크/스케줄러/메일알림/인계패키지)" -ForegroundColor White
Write-Host "  🎓 학습/레퍼런스  12개  (타입매핑/객체변환/함수차이/Phase의미/용어집)" -ForegroundColor White

Write-Host "`n주요 가치:" -ForegroundColor Cyan
Write-Host "  ✓ 12 카테고리 — 일반 도구가 안 다루는 KISA 보안/성능 튜닝/학습 포함" -ForegroundColor White
Write-Host "  ✓ 위험도 표시 — danger(빨강) / warn(주황) / 안전 자동 구분" -ForegroundColor White
Write-Host "  ✓ ROOT 자동 치환 — 어떤 환경에도 그대로 복붙 가능" -ForegroundColor White
Write-Host "  ✓ 검색 + 관련 명령 cross-link — 한 번 진단부터 처방까지 추적" -ForegroundColor White
Write-Host "  ✓ PDF 출력 최적화 — 폐쇄망 인계 매뉴얼로 즉시 활용" -ForegroundColor White
Write-Host "  ✓ 살아있는 자산 — 데이터 분리로 향후 명령 추가 쉬움" -ForegroundColor White

Write-Host "`n적용 절차:" -ForegroundColor Cyan
Write-Host "  1. Ctrl+Shift+R (Vite HMR 자동 — 백엔드 변경 없음)" -ForegroundColor White
Write-Host "  2. 좌측 사이드바 → '관리자' → '📚 운영자 라이브러리'" -ForegroundColor White

Write-Host "`n구매자 데모 시나리오 (추천):" -ForegroundColor Yellow
Write-Host "  1. 페이지 열기 → 187개 명령 카운트 보여주기" -ForegroundColor White
Write-Host "  2. '🔐 보안/감사' → KISA 6항목 (SMB/Telnet/UAC/RDP/패스워드/SSL)" -ForegroundColor White
Write-Host "  3. '📈 성능 튜닝' → buffer pool / 누락 인덱스 권고" -ForegroundColor White
Write-Host "  4. 검색창에 'KISA' 입력 → 즉시 필터링" -ForegroundColor White
Write-Host "  5. Ctrl+P → PDF 미리보기 (폐쇄망 매뉴얼 즉시 가능)" -ForegroundColor White

Write-Host "`n롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
