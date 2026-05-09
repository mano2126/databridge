$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v95_p2 — 객체 검증 동시 실행 옵션" -ForegroundColor Cyan
Write-Host "  본부장님 명령: 실행 버튼 왼쪽 / 두 줄 방지 / 멀티 수행" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v95_p2_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$rel = "frontend\src\pages\Validate.vue"
$src = Join-Path $ProjectRoot $rel
if (Test-Path $src) {
    $dst = Join-Path $BackupRoot $rel
    New-Item -Path (Split-Path -Parent $dst) -ItemType Directory -Force | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst -Force
}
$sf = Join-Path $PatchSrc $rel
Copy-Item -LiteralPath $sf -Destination $src -Force
Write-Host "  + $rel" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  본부장님 명령 4가지 — 모두 처방됨" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  ✓ 1. 위치: 실행 버튼 *왼쪽*에 동시 실행 옵션" -ForegroundColor Green
Write-Host "  ✓ 2. UI: white-space:nowrap + min-width:110px → 두 줄 방지" -ForegroundColor Green
Write-Host "  ✓ 3. 기능: Promise.all 배치 병렬 실행 (진짜 동시)" -ForegroundColor Green
Write-Host "  ⚠ 4. 테이블 검증 경합: v95_p3 별도 작업 (백엔드 변경 필요)" -ForegroundColor Yellow

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  옵션 — 동시 실행 갯수" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  1개 (순차)  — 안전, 느림 — DB 부하 가장 적음" -ForegroundColor White
Write-Host "  3개 (권장)  — 기본값, 대부분 환경" -ForegroundColor Green
Write-Host "  5개         — 빠름 (DB 여유 있을 때)" -ForegroundColor White
Write-Host "  10개        — 더 빠름 (소규모 객체 대량 검증)" -ForegroundColor White
Write-Host "  20개 (최대) — 가장 빠름 (테스트 환경)" -ForegroundColor White

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  속도 비교 (시뮬레이션, 41개 객체)" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  순차 (1개):  약 10초+" -ForegroundColor White
Write-Host "  동시 3개:    약 5초     ← 권장 기본값" -ForegroundColor Green
Write-Host "  동시 5개:    약 3초" -ForegroundColor White
Write-Host "  동시 10개:   약 2초" -ForegroundColor White

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  v95_p3 예고 — 테이블 검증 경합 분석" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "본부장님 명령 4번 (테이블 경합 분석) 은 백엔드 변경 필요:" -ForegroundColor Cyan
Write-Host "  - validate.py SSE 스트림 수정" -ForegroundColor White
Write-Host "  - 대용량 단독 (1M+ rows)" -ForegroundColor White
Write-Host "  - 소용량 다수 동시" -ForegroundColor White
Write-Host "  - 같은 FK 그룹 직렬화" -ForegroundColor White
Write-Host "  - 충분한 시뮬레이션 + 테스트 후 별도 ZIP" -ForegroundColor White

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  적용 절차" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  1. ZIP 풀기 (D:\project\ 위)" -ForegroundColor White
Write-Host "     Vue 파일만 변경 — 백엔드 재시작 불필요" -ForegroundColor DarkGray
Write-Host "  2. UI Ctrl+Shift+R (Vite HMR 자동 적용)" -ForegroundColor White
Write-Host "  3. 객체 검증 화면 열기" -ForegroundColor White
Write-Host "  4. 화면에 [동시: 3개 (권장) ▼] [▶ 선택 실행 (N개)] 가로 배치 확인" -ForegroundColor White
Write-Host "  5. 동시 갯수 선택 + 실행 → 빠른 일괄 검증" -ForegroundColor Green

Write-Host "`n롤백: Copy-Item '$BackupRoot\frontend\src\pages\Validate.vue' '$ProjectRoot\frontend\src\pages\' -Force" -ForegroundColor DarkYellow
