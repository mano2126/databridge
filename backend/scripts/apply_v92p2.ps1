#requires -Version 5.1
<#
.SYNOPSIS
  DataBridge v92p2 패치 적용 — UX 개선 (A1+A2) + 일괄 튜닝 권장 패널 (B) + 검증 매칭 인지 (C)

.DESCRIPTION
  본 패치는 D:\project\databridge_full 기준으로 다음 파일을 갱신/추가합니다.
    [수정] frontend/src/pages/SqlConverter.vue
    [수정] frontend/src/pages/Validate.vue
    [수정] frontend/src/store/converterStore.js
    [수정] backend/app/api/routes/sql_converter.py
    [수정] backend/app/api/routes/validate.py
    [수정] backend/app/core/schema_conversion_policy.py
    [신규] frontend/src/components/converter/BatchTuningPanel.vue

.NOTES
  - 적용 전 자동 백업 (D:\project\databridge_full_backup_yyyyMMdd_HHmmss)
  - 백엔드 reload 후 프론트는 Ctrl+Shift+R 로 캐시 갱신
#>

[CmdletBinding()]
param(
    [string]$ProjectRoot = "D:\project\databridge_full",
    [string]$PatchRoot   = (Split-Path -Parent $MyInvocation.MyCommand.Path)
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.UTF8Encoding]::new($true)

Write-Host "════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v92p2 패치 적용" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ── 사전 검증 ──
if (-not (Test-Path $ProjectRoot)) {
    Write-Error "프로젝트 경로를 찾을 수 없습니다: $ProjectRoot"
    exit 1
}

$PatchSrc = Join-Path $PatchRoot "databridge_full"
if (-not (Test-Path $PatchSrc)) {
    Write-Error "패치 소스 경로를 찾을 수 없습니다: $PatchSrc"
    Write-Error "본 .ps1 파일은 databridge_v92p2_*.zip 을 푼 폴더에서 실행하세요."
    exit 1
}

# ── 백업 ──
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_$ts"
Write-Host "[1/3] 백업 생성: $BackupRoot" -ForegroundColor Yellow

$filesToBackup = @(
    "frontend\src\pages\SqlConverter.vue",
    "frontend\src\pages\Validate.vue",
    "frontend\src\store\converterStore.js",
    "backend\app\api\routes\sql_converter.py",
    "backend\app\api\routes\validate.py",
    "backend\app\core\schema_conversion_policy.py"
)

New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null
foreach ($rel in $filesToBackup) {
    $src = Join-Path $ProjectRoot $rel
    if (Test-Path $src) {
        $dst = Join-Path $BackupRoot $rel
        $dstDir = Split-Path -Parent $dst
        New-Item -Path $dstDir -ItemType Directory -Force | Out-Null
        Copy-Item -LiteralPath $src -Destination $dst -Force
        Write-Host "  + $rel" -ForegroundColor DarkGray
    }
}

# ── 적용 ──
Write-Host ""
Write-Host "[2/3] 패치 파일 복사" -ForegroundColor Yellow

$copyMap = @(
    @{ src = "frontend\src\pages\SqlConverter.vue";        dst = "frontend\src\pages\SqlConverter.vue" },
    @{ src = "frontend\src\pages\Validate.vue";            dst = "frontend\src\pages\Validate.vue" },
    @{ src = "frontend\src\store\converterStore.js";       dst = "frontend\src\store\converterStore.js" },
    @{ src = "frontend\src\components\converter\BatchTuningPanel.vue"; dst = "frontend\src\components\converter\BatchTuningPanel.vue" },
    @{ src = "backend\app\api\routes\sql_converter.py";    dst = "backend\app\api\routes\sql_converter.py" },
    @{ src = "backend\app\api\routes\validate.py";         dst = "backend\app\api\routes\validate.py" },
    @{ src = "backend\app\core\schema_conversion_policy.py"; dst = "backend\app\core\schema_conversion_policy.py" }
)

foreach ($item in $copyMap) {
    $srcFull = Join-Path $PatchSrc $item.src
    $dstFull = Join-Path $ProjectRoot $item.dst
    if (-not (Test-Path $srcFull)) {
        Write-Warning "  ! 패치 파일 없음: $($item.src)"
        continue
    }
    $dstDir = Split-Path -Parent $dstFull
    if (-not (Test-Path $dstDir)) {
        New-Item -Path $dstDir -ItemType Directory -Force | Out-Null
    }
    Copy-Item -LiteralPath $srcFull -Destination $dstFull -Force
    Write-Host "  + $($item.dst)" -ForegroundColor Green
}

# ── 무결성 검증 ──
Write-Host ""
Write-Host "[3/3] 무결성 검증" -ForegroundColor Yellow

$pyFiles = @(
    "backend\app\api\routes\sql_converter.py",
    "backend\app\api\routes\validate.py",
    "backend\app\core\schema_conversion_policy.py"
)
$pyOk = $true
foreach ($rel in $pyFiles) {
    $full = Join-Path $ProjectRoot $rel
    $r = & python -c "import ast,sys; ast.parse(open(r'$full',encoding='utf-8').read()); print('OK')" 2>&1
    if ($LASTEXITCODE -eq 0 -and $r -match "OK") {
        Write-Host "  py OK: $rel" -ForegroundColor Green
    } else {
        Write-Host "  py FAIL: $rel — $r" -ForegroundColor Red
        $pyOk = $false
    }
}

Write-Host ""
if ($pyOk) {
    Write-Host "════════════════════════════════════════" -ForegroundColor Green
    Write-Host "  ✓ v92p2 적용 완료" -ForegroundColor Green
    Write-Host "════════════════════════════════════════" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Cyan
    Write-Host "  1. 백엔드 reload — uvicorn 재시작 또는 --reload 모드 자동 감지" -ForegroundColor White
    Write-Host "  2. 프론트 — 브라우저에서 Ctrl+Shift+R (캐시 무시 새로고침)" -ForegroundColor White
    Write-Host ""
    Write-Host "롤백 필요 시:" -ForegroundColor DarkYellow
    Write-Host "  Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
} else {
    Write-Host "════════════════════════════════════════" -ForegroundColor Red
    Write-Host "  ✗ syntax 검증 실패 — 백업으로 롤백 권장" -ForegroundColor Red
    Write-Host "════════════════════════════════════════" -ForegroundColor Red
    Write-Host "  Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor Yellow
    exit 1
}
