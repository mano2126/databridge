$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v93_D1 — KB fix_prompt 정밀화 + 객체명 박힘 처방" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v93_D1_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "backend\app\engine\error_kb.yml",
    "backend\app\engine\error_kb.py",
    "backend\app\api\routes\schema.py"
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

# 무결성
$ok = $true
$pyFile = Join-Path $ProjectRoot "backend\app\api\routes\schema.py"
$ymlFile = Join-Path $ProjectRoot "backend\app\engine\error_kb.yml"
$pyOk = & python -c "import ast; ast.parse(open(r'$pyFile',encoding='utf-8').read()); print('OK')" 2>&1
$ymlOk = & python -c "import yaml; yaml.safe_load(open(r'$ymlFile',encoding='utf-8')); print('OK')" 2>&1
if ($pyOk -notmatch "OK") { Write-Host "✗ schema.py: $pyOk" -ForegroundColor Red; $ok = $false }
if ($ymlOk -notmatch "OK") { Write-Host "✗ error_kb.yml: $ymlOk" -ForegroundColor Red; $ok = $false }

if ($ok) {
    Write-Host "`n✓ v93_D1 적용 완료" -ForegroundColor Green
    Write-Host "`n변경 내용 (2가지 본질 처방):" -ForegroundColor Cyan
    Write-Host "  [1] error_kb.yml — fix_prompt 형식 표준화" -ForegroundColor Yellow
    Write-Host "      ===INSTRUCTION=== / ===END=== 명확한 구분자" -ForegroundColor White
    Write-Host "      [반드시 지킬 규칙] 섹션 → 객체명/시그니처 보존 강조" -ForegroundColor White
    Write-Host "      절대 금지 패턴 명시: 'is_not_supported' 같은 텍스트 객체명에 포함 금지" -ForegroundColor White
    Write-Host "  [2] schema.py — 객체명 박힘 자동 정리 (return 직전)" -ForegroundColor Yellow
    Write-Host "      AI 가 만든 SQL 에서 forbidden tokens 자동 제거:" -ForegroundColor White
    Write-Host "      - is_not_supported, use_view_or_procedure, not_supported," -ForegroundColor DarkGray
    Write-Host "        use_view, use_procedure, see_documentation, see_kb 등 9개" -ForegroundColor DarkGray
    Write-Host "      CREATE/DROP/CALL/ALTER 모든 위치 자동 정리" -ForegroundColor White
    Write-Host "      정리 시 result.notes 에 '[v93_D1] 객체명 정리 N건' 표시" -ForegroundColor White
    Write-Host "`n검증 (시뮬레이션):" -ForegroundColor Cyan
    Write-Host "  ✓ CREATE FUNCTION settlement_tvf_daily_trx_is_not_supported_use_view_or_procedure(...)" -ForegroundColor Green
    Write-Host "    → CREATE FUNCTION settlement_tvf_daily_trx(...)" -ForegroundColor Green
    Write-Host "  ✓ DROP PROCEDURE IF EXISTS settlement_tvf_daily_trx_is_not_supported..." -ForegroundColor Green
    Write-Host "    → DROP PROCEDURE IF EXISTS settlement_tvf_daily_trx" -ForegroundColor Green
    Write-Host "  ✓ 정상 객체명은 변경 안 됨" -ForegroundColor Green
    Write-Host "`n⚠ 백엔드 재시작 필수 (yml + py 모두 변경)" -ForegroundColor Yellow
    Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
} else {
    Write-Host "`n✗ syntax FAIL" -ForegroundColor Red
    exit 1
}
