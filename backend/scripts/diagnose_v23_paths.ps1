# v10 #23 정확한 경로 탐색 진단
# 파일명: diagnose_v23_paths.ps1

Write-Host "`n🔍 실제 경로 확인 진단`n" -ForegroundColor Cyan

$jobId = "655d5ec1-c8a1-44e9-804d-945b89eae886"

# ── 1) OpenAPI 스펙에서 verify 엔드포인트 실제 경로 찾기 ─────
Write-Host "[1/4] FastAPI OpenAPI 스펙에서 verify 엔드포인트 찾기" -ForegroundColor Yellow
try {
    $openapi = Invoke-RestMethod -Uri "http://localhost:8000/openapi.json" -TimeoutSec 10
    $paths = $openapi.paths.PSObject.Properties.Name
    $verifyPaths = $paths | Where-Object { $_ -like "*verify*" -or $_ -like "*report*" }
    if ($verifyPaths) {
        Write-Host "  verify/report 관련 엔드포인트:" -ForegroundColor Green
        foreach ($p in $verifyPaths) {
            Write-Host "    $p" -ForegroundColor Gray
        }
    } else {
        Write-Host "  ⚠ verify/report 엔드포인트 없음" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ✗ OpenAPI 조회 실패: $_" -ForegroundColor Red
}

# ── 2) Jobs 관련 엔드포인트 (리포트는 보통 여기에) ──────────
Write-Host ""
Write-Host "[2/4] Jobs 관련 전체 엔드포인트" -ForegroundColor Yellow
try {
    $openapi = Invoke-RestMethod -Uri "http://localhost:8000/openapi.json" -TimeoutSec 10
    $jobPaths = $openapi.paths.PSObject.Properties.Name | Where-Object { $_ -like "*jobs*" }
    foreach ($p in $jobPaths) {
        Write-Host "    $p" -ForegroundColor Gray
    }
} catch {}

# ── 3) Store 실제 위치 찾기 ────────────────────────────────
Write-Host ""
Write-Host "[3/4] DataBridge Store 파일 위치 탐색" -ForegroundColor Yellow
$searchPaths = @(
    "D:\project\databridge_full\backend\databridge.db",
    "D:\project\databridge_full\backend\data\databridge.db",
    "D:\project\databridge_full\backend\app\databridge.db",
    "D:\project\databridge_full\backend\app\data\databridge.db",
    "D:\project\databridge_full\backend\store.db",
    "D:\project\databridge_full\data\databridge.db"
)
foreach ($p in $searchPaths) {
    if (Test-Path $p) {
        $size = (Get-Item $p).Length
        Write-Host "  ✓ 발견: $p ($size bytes)" -ForegroundColor Green
    }
}

# .db 파일 전체 재귀 검색
Write-Host ""
Write-Host "  재귀 검색 (모든 .db 파일):" -ForegroundColor Gray
Get-ChildItem -Path "D:\project\databridge_full" -Recurse -Filter "*.db" -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "    $($_.FullName) ($($_.Length) bytes)" -ForegroundColor Gray
}

# ── 4) Store 모듈이 실제 어디에 저장하는지 확인 ──────────────
Write-Host ""
Write-Host "[4/4] Store 모듈의 기본 경로 설정 확인" -ForegroundColor Yellow
$storePath = "D:\project\databridge_full\backend\app\core\store.py"
if (Test-Path $storePath) {
    Write-Host "  Store 파일: $storePath" -ForegroundColor Gray
    $dbRefs = Select-String -Path $storePath -Pattern "\.db|DB_PATH|store\.db|databridge\.db" -AllMatches | Select-Object -First 5
    foreach ($ref in $dbRefs) {
        Write-Host "    line $($ref.LineNumber): $($ref.Line.Trim())" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "진단 완료. Claude 에게 결과 공유하세요." -ForegroundColor Cyan
