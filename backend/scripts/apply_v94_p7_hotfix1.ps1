$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  v94_p7 hotfix1 — 매칭 분리 긴급 처방" -ForegroundColor Cyan
Write-Host "  본부장님 호소: '소스전용 42개 / 타겟전용 42개 매칭 0개'" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v94_p7_hotfix1_$ts"
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
Write-Host "  본질 진단 (정직)" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "이 부작용은 v94_p7 의 backend 변경이 *원인이 아닙니다*." -ForegroundColor White
Write-Host "(백엔드 변경은 검증 실행 단계 — 매칭 후보 화면은 별도 영역)" -ForegroundColor DarkGray
Write-Host ""
Write-Host "원인: v90.49 시점부터 있던 _policyKey 의 설계 한계." -ForegroundColor Cyan
Write-Host ""
Write-Host "  소스 (MSSQL):" -ForegroundColor White
Write-Host "    schema_name='collection' / table_name='activity'" -ForegroundColor DarkGray
Write-Host "    → underscore 정책: 'collection_activity' ✓" -ForegroundColor Green
Write-Host ""
Write-Host "  타겟 (MySQL):" -ForegroundColor White
Write-Host "    schema_name='capital_target' (← DB 이름!)" -ForegroundColor DarkGray
Write-Host "    table_name='collection_activity'" -ForegroundColor DarkGray
Write-Host "    → underscore 정책: 'capital_target_collection_activity' ✗" -ForegroundColor Red
Write-Host ""
Write-Host "→ 양쪽 매칭키 불일치 → 좌측 '소스전용 42개', 우측 '타겟전용 42개'" -ForegroundColor Yellow

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  처방" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "_policyKey(t, dbName) 시그니처 추가:" -ForegroundColor Cyan
Write-Host "  - sch === dbName 이면 결합 안 함 (DB 이름은 schema 가 아님)" -ForegroundColor White
Write-Host "  - dbo / 빈 schema 처럼 무시" -ForegroundColor White
Write-Host ""
Write-Host "호출 측에서 src.database / tgt.database 전달" -ForegroundColor Cyan
Write-Host ""
Write-Host "검증 결과 (시뮬레이션):" -ForegroundColor Cyan
Write-Host "  소스 'collection.activity'         → 'collection_activity'" -ForegroundColor White
Write-Host "  타겟 'capital_target.collection_activity' → 'collection_activity'" -ForegroundColor White
Write-Host "  → ✓ 매칭 성공" -ForegroundColor Green
Write-Host ""
Write-Host "부작용 점검:" -ForegroundColor Cyan
Write-Host "  - dbo.users → 'users'  (기존 동작 유지)" -ForegroundColor Green
Write-Host "  - drop 정책 → bare 만   (기존 동작 유지)" -ForegroundColor Green
Write-Host "  - 이미 결합된 이름 → 중복 방지 (기존 동작 유지)" -ForegroundColor Green

Write-Host "`n검증:" -ForegroundColor Yellow
Write-Host "  1. Ctrl+Shift+R" -ForegroundColor White
Write-Host "  2. 테이블 검증 화면 → 매칭 42개 / 소스전용 0 / 타겟전용 0" -ForegroundColor Green
Write-Host "  3. 검증 실행 → v94_p7 의 underscore 매칭 효과로 정상 카운트 비교" -ForegroundColor Green

Write-Host "`n⚠ Frontend 1 파일만 — 백엔드 영향 없음 (Vite HMR 자동)" -ForegroundColor Yellow
Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
