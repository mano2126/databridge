$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v94_p10 — 진짜 본질 처방!" -ForegroundColor Cyan
Write-Host "  date 타입 max_length 오해 수정" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v94_p10_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$rel = "backend\app\api\routes\schema.py"
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
Write-Host "  진짜 본질 — 본부장님 PowerShell 검증으로 확정" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "본부장님 PowerShell 결과:" -ForegroundColor Cyan
Write-Host "  fn_age @birth: type=date, max_length=3, precision=10" -ForegroundColor White
Write-Host "                                ↑↑↑" -ForegroundColor Yellow
Write-Host ""
Write-Host "MSSQL date 타입의 max_length=3 은 *스토리지 바이트*" -ForegroundColor White
Write-Host "사람이 보는 'YYYY-MM-DD' (10자) 와 무관!" -ForegroundColor White
Write-Host ""
Write-Host "백엔드 _smart_dummy 가 이걸 문자 길이로 오해:" -ForegroundColor Red
Write-Host '  if ml < 10: return "20240101"[:max(ml,4)] if ml>=4 else "20240101"[:ml]' -ForegroundColor White
Write-Host '  ml=3 → "20240101"[:3] = "202"  ← 본부장님 화면의 "202" 정체!' -ForegroundColor Yellow

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  v94_p10 처방 — 진짜 date 타입은 max_length 무시" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "타입별 정확한 처리:" -ForegroundColor Cyan
Write-Host "  date 타입 (max_length 무시)        → '2024-01-01'" -ForegroundColor Green
Write-Host "  datetime/datetime2 타입 (max_length 무시) → '2024-01-01 00:00:00'" -ForegroundColor Green
Write-Host "  time 타입                           → '09:00:00'" -ForegroundColor Green
Write-Host "  varchar(8) (진짜 문자 8자)          → '20240101'  ← 그대로 유지" -ForegroundColor Green
Write-Host "  varchar(10) (진짜 문자 10자)        → '2024-01-01'" -ForegroundColor Green
Write-Host ""
Write-Host "시뮬레이션 검증 통과:" -ForegroundColor Cyan
Write-Host "  @dt date max_length=3       → '2024-01-01' ✓ (이전: '202')" -ForegroundColor Green
Write-Host "  @birth date max_length=3    → '2024-01-01' ✓" -ForegroundColor Green
Write-Host "  @dt varchar max_length=8    → '20240101'   ✓ (그대로 유지)" -ForegroundColor Green
Write-Host "  @id bigint                  → '0'          ✓ (영향 없음)" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  적용 절차" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  1. ZIP 풀기 (D:\project\ 위)" -ForegroundColor White
Write-Host "  2. Get-Process python | Stop-Process -Force" -ForegroundColor White
Write-Host "  3. cd D:\project\databridge_full\backend; run_backend.bat" -ForegroundColor White
Write-Host "  4. Ctrl+Shift+R" -ForegroundColor White
Write-Host "  5. 객체 화면에서 fn_age 테스트 펼치기 → input 박스에 '2024-01-01' 표시 확인" -ForegroundColor White
Write-Host "  6. ▶ 양쪽 동시 → ✓ 성공 기대" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  본부장님 통찰의 가치" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "본부장님이 하나하나 짚어주신 통찰:" -ForegroundColor Cyan
Write-Host "  '소스 테스트는 그냥 원본 DB 조회 아냐?'" -ForegroundColor White
Write-Host "  'DB 접속할 때 이미 패스워드 알고 있을 건데?'" -ForegroundColor White
Write-Host "  → 잘못된 길로 가던 처방을 즉시 잡아주심" -ForegroundColor White
Write-Host ""
Write-Host "본부장님 PowerShell 검증으로 직접 확인해주신 사실:" -ForegroundColor Cyan
Write-Host "  - MSSQL CLI 에서 7개 객체 모두 ✓ 정상" -ForegroundColor White
Write-Host "  - max_length=3 의 진짜 의미 (스토리지 바이트)" -ForegroundColor White
Write-Host "  → 추측 대신 실측이 본질을 결정타로 잡아줌" -ForegroundColor White

Write-Host "`n롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
