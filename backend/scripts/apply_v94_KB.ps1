$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v94_KB — 본질 처방 + KB 자산 가시화 강화" -ForegroundColor Cyan
Write-Host "  본부장님 호소:" -ForegroundColor Yellow
Write-Host "    1. 'closed connection' Audit 5영역 실패 (회피 X 본질 처방)" -ForegroundColor White
Write-Host "    2. 'KB 추가 어디서 확인?' (조회 강화)" -ForegroundColor White
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v94_KB_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "backend\app\engine\migration_engine.py",
    "backend\app\api\routes\kb.py",
    "frontend\src\pages\AdminKbDashboard.vue"
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

Write-Host "`n✓ v94_KB 적용 완료" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  Part 1 — 본질 처방 (migration_engine.py)" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "원인 (확정):" -ForegroundColor Cyan
Write-Host "  객체 이관 끝나자마자 src_conn.close() / tgt_conn.close() 명시적 종료" -ForegroundColor White
Write-Host "  → 그 후 인덱스 자동 이관 + Audit 5영역이 '죽은 connection' 사용" -ForegroundColor White
Write-Host "  → 모두 'Attempt to use a closed connection' 으로 실패" -ForegroundColor White
Write-Host "`n처방 (회피 X):" -ForegroundColor Cyan
Write-Host "  1. close() 호출 시점을 인덱스/Audit 종료 후로 이동" -ForegroundColor White
Write-Host "  2. _ensure_conns_alive() 헬퍼 추가 — 진입 직전 ping 검증" -ForegroundColor White
Write-Host "     - pymysql: 내장 ping(reconnect=True)" -ForegroundColor DarkGray
Write-Host "     - pyodbc:  SELECT 1 가벼운 쿼리" -ForegroundColor DarkGray
Write-Host "     - 죽었으면 _connect_src/_connect_tgt 로 새로 만듦" -ForegroundColor DarkGray
Write-Host "  3. 인덱스 진입 직전 + Audit 진입 직전 두 곳에서 검증" -ForegroundColor White

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  Part 2 — KB 자산 조회 강화 (AdminKbDashboard)" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "본부장님 질문 답:" -ForegroundColor Cyan
Write-Host "  KB 추가 확인 위치 = '관리자 → 에러 프롬프트 KB → 📊 KB Dashboard 탭'" -ForegroundColor White
Write-Host "  (이미 v93_D2 에서 추가됨 — v94_KB 가 그 위에 강화)" -ForegroundColor DarkGray

Write-Host "`n강화 내용:" -ForegroundColor Cyan
Write-Host "  요약 카드 (4개):" -ForegroundColor White
Write-Host "    - 등록 패턴 / KB 후보 케이스 / 적중률 / AI 절약" -ForegroundColor DarkGray
Write-Host "  검색/필터 (6종):" -ForegroundColor White
Write-Host "    - 🔍 키워드 검색 (객체명/에러/DDL 본문 매칭)" -ForegroundColor DarkGray
Write-Host "    - 객체 타입 (FUNCTION/PROCEDURE/TRIGGER/...)" -ForegroundColor DarkGray
Write-Host "    - 에러 코드 (1064/1362/...)" -ForegroundColor DarkGray
Write-Host "    - 날짜 범위 (from ~ to)" -ForegroundColor DarkGray
Write-Host "    - 그룹화 (객체별/날짜별/에러코드별)" -ForegroundColor DarkGray
Write-Host "    - ✕ 필터 초기화" -ForegroundColor DarkGray
Write-Host "  케이스 카드 표시:" -ForegroundColor White
Write-Host "    - 타임스탬프 / 객체 타입 배지 / 객체명 / 에러코드 / 첫 에러 라인" -ForegroundColor DarkGray
Write-Host "  드릴다운:" -ForegroundColor White
Write-Host "    - 그룹 카드 클릭 → 자동 필터링" -ForegroundColor DarkGray
Write-Host "    - 케이스 클릭 → 펼침 → 전체 본문 보기 (검은 배경 코드 블록)" -ForegroundColor DarkGray
Write-Host "  패턴화 워크플로우:" -ForegroundColor White
Write-Host "    - 📋 본문 복사 (클립보드)" -ForegroundColor DarkGray
Write-Host "    - 📝 정식 패턴으로 등록 → (가이드 + 자동 복사)" -ForegroundColor DarkGray

Write-Host "`n신규 백엔드 API (kb.py):" -ForegroundColor Cyan
Write-Host "  GET /api/v1/kb/cases-recent  ← 강화됨 (검색/필터/그룹/메타 추출)" -ForegroundColor White
Write-Host "  GET /api/v1/kb/cases-detail  ← 신규 (단일 케이스 전체 본문)" -ForegroundColor White

Write-Host "`n검증 시나리오:" -ForegroundColor Yellow
Write-Host "  Part 1 (Audit closed connection 처방):" -ForegroundColor White
Write-Host "    - 새 이관 실행 → 'Audit 5영역 모두 정상' 로그 확인" -ForegroundColor DarkGray
Write-Host "    - '[v94_p2] tgt connection 재연결 성공' 로그 (필요 시) 확인" -ForegroundColor DarkGray
Write-Host "  Part 2 (KB 조회):" -ForegroundColor White
Write-Host "    1. 관리자 → 에러 프롬프트 KB → 📊 KB Dashboard 탭" -ForegroundColor DarkGray
Write-Host "    2. 'KB 후보 케이스' 영역 확인 — 4건 (오늘 추가) 보임" -ForegroundColor DarkGray
Write-Host "    3. 그룹화 → '객체별' 선택 → 객체별 카운트 차트" -ForegroundColor DarkGray
Write-Host "    4. 객체 타입 필터: PROCEDURE 만 → 1건 (sp_mark_delinquent)" -ForegroundColor DarkGray
Write-Host "    5. 케이스 클릭 → 펼침 → 전체 본문 + 📝 정식 패턴 등록 버튼" -ForegroundColor DarkGray

Write-Host "`n⚠ 백엔드 변경 있음 — Python 재시작 필요" -ForegroundColor Yellow
Write-Host "   → Get-Process python | Stop-Process -Force; run_backend.bat" -ForegroundColor DarkGray
Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
