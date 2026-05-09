$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v93_D2 — KB 자산 가시화 + 1클릭 후보 등록" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v93_D2_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "backend\app\api\routes\kb.py",
    "frontend\src\pages\AdminKb.vue",
    "frontend\src\pages\AdminKbDashboard.vue",
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

$pyFile = Join-Path $ProjectRoot "backend\app\api\routes\kb.py"
$r = & python -c "import ast; ast.parse(open(r'$pyFile',encoding='utf-8').read()); print('OK')" 2>&1

if ($r -match "OK") {
    Write-Host "`n✓ v93_D2 적용 완료" -ForegroundColor Green
    Write-Host "`n변경 내용:" -ForegroundColor Cyan
    Write-Host "  [백엔드 kb.py — 새 API 3개]" -ForegroundColor Yellow
    Write-Host "    POST /api/v1/kb/register-candidate — 1클릭 KB 후보 등록" -ForegroundColor White
    Write-Host "    GET  /api/v1/kb/cases-recent       — error_cases.txt 최근 케이스" -ForegroundColor White
    Write-Host "    GET  /api/v1/kb/dashboard          — 종합 대시보드 데이터" -ForegroundColor White
    Write-Host "  [프론트 AdminKbDashboard.vue 신규]" -ForegroundColor Yellow
    Write-Host "    상단 4개 요약 카드: 패턴/시도/적중률/AI 절약" -ForegroundColor White
    Write-Host "    카테고리별 패턴 분포 (막대 차트)" -ForegroundColor White
    Write-Host "    Top 10 패턴 표 (적중률 색상 표시)" -ForegroundColor White
    Write-Host "    미매칭 에러 (KB 보강 후보) 목록" -ForegroundColor White
    Write-Host "    최근 KB 후보 케이스 타임라인" -ForegroundColor White
    Write-Host "  [AdminKb.vue 탭 추가]" -ForegroundColor Yellow
    Write-Host "    📊 KB Dashboard (기본 탭)" -ForegroundColor White
    Write-Host "    🚨 에러 KB (기존)" -ForegroundColor White
    Write-Host "    🔄 변환 KB (기존)" -ForegroundColor White
    Write-Host "  [Validate.vue 🔬 KB 버튼]" -ForegroundColor Yellow
    Write-Host "    실패한 객체 옆에 🔬 KB 버튼 → 1클릭 후보 등록" -ForegroundColor White
    Write-Host "    error_cases.txt 에 자동 누적 (다음 세션 검토 + 정식 패턴화)" -ForegroundColor White
    Write-Host "`n전체 본부장님 KB 자산 가시화 완료." -ForegroundColor Green
    Write-Host "⚠ 백엔드 재시작 + Ctrl+Shift+R" -ForegroundColor Yellow
    Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
} else {
    Write-Host "`n✗ syntax FAIL: $r" -ForegroundColor Red
    exit 1
}
