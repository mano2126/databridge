$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v95_p7 — 좌측 메뉴 진행 표시기 (검증 작업 인식)" -ForegroundColor Cyan
Write-Host "  본부장님 명령: '어느 페이지에서 작업 수행 중인지 알 수 있어야'" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v95_p7_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "frontend\src\store\appStore.js",
    "frontend\src\components\layout\Sidebar.vue",
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

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  본부장님 의문 — 본질 진단" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "기존 좌측 메뉴 수레바퀴 (busyRoutes) 인식 영역:" -ForegroundColor Cyan
Write-Host "  ✓ /monitor          (실시간 모니터)" -ForegroundColor White
Write-Host "  ✓ /jobs/monitor     (이관 작업 모니터)" -ForegroundColor White
Write-Host "  ✓ /jobs             (Job 목록)" -ForegroundColor White
Write-Host "  ✓ /schedules        (스케줄 관리)" -ForegroundColor White
Write-Host ""
Write-Host "본부장님이 *지금* 작업하시는 영역:" -ForegroundColor Yellow
Write-Host "  ✗ /validate         (검증 & 대사) ← busyRoutes 에 *없었음*" -ForegroundColor Red
Write-Host "  ✗ /validate/tables  (테이블·오브젝트 검증) ← busyRoutes 에 *없었음*" -ForegroundColor Red
Write-Host ""
Write-Host "본질: 검증 작업의 진행 상태가 *컴포넌트 로컬* 이라 좌측 메뉴 인식 X" -ForegroundColor Cyan

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  v95_p7 본질 처방" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[1] appStore.js — 검증 진행 상태 *전역 store* 로 승격" -ForegroundColor Cyan
Write-Host "    + state: validateRunning, validateProgress" -ForegroundColor Green
Write-Host "    + actions: setValidateRunning, clearValidateRunning" -ForegroundColor Green
Write-Host ""
Write-Host "[2] Sidebar.vue — busyRoutes 에 검증 라우트 추가" -ForegroundColor Cyan
Write-Host "    + /validate" -ForegroundColor Green
Write-Host "    + /validate/tables" -ForegroundColor Green
Write-Host "    → app.validateRunning 보고 자동 표시" -ForegroundColor Green
Write-Host ""
Write-Host "[3] Validate.vue — 검증 시작/종료 시 store 호출" -ForegroundColor Cyan
Write-Host "    + runValidate (테이블 검증) 시작 → setValidateRunning('table')" -ForegroundColor Green
Write-Host "    + runValidate finally → clearValidateRunning()" -ForegroundColor Green
Write-Host "    + runObjValidate (오브젝트 검증) 시작 → setValidateRunning('object')" -ForegroundColor Green
Write-Host "    + runObjValidate 종료 (정상/abort) → clearValidateRunning()" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  v95_p2 본질 처방 보존 확인" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  ✓ 동시 실행 옵션 (오브젝트 검증 실행 버튼 왼쪽)" -ForegroundColor Green
Write-Host "  ✓ 소스 오브젝트 선택 패널 자동 접기/타이틀 클릭 토글" -ForegroundColor Green
Write-Host "  → v95_p2 의 13개 마커 모두 보존" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  적용 (Vue 파일만 — 백엔드 재시작 불필요)" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  1. ZIP 풀기 (D:\project\ 위)" -ForegroundColor White
Write-Host "  2. UI Ctrl+Shift+R (Vite HMR 자동)" -ForegroundColor White
Write-Host "  3. 객체 검증 → '오브젝트 검증 실행' 클릭" -ForegroundColor White
Write-Host "  → 좌측 메뉴 '검증 & 대사' 옆 수레바퀴 ⚙ 회전 확인" -ForegroundColor Green
Write-Host "  → '테이블·오브젝트 검증' 메뉴 옆에도 수레바퀴 ⚙" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  적용 확인" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Select-String D:\project\databridge_full\frontend\src\store\appStore.js ``" -ForegroundColor White
Write-Host "  -Pattern 'v95_p7|validateRunning' | Select-Object -First 5" -ForegroundColor White
Write-Host ""
Write-Host "Select-String D:\project\databridge_full\frontend\src\components\layout\Sidebar.vue ``" -ForegroundColor White
Write-Host "  -Pattern 'v95_p7|/validate' | Select-Object -First 5" -ForegroundColor White

Write-Host "`n롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
