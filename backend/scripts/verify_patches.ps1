$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge 패치 적용 검증 도구 (v93_E)" -ForegroundColor Cyan
Write-Host "  본부장님 통찰: 'v92p10 같은 누락 또 발생하면 안돼'" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan

# 검증 대상 — 각 패치가 어느 파일의 어떤 마커를 남겼는지
$patchMap = @(
    @{ id = "v92p10"; file = "frontend\src\pages\Validate.vue";       marker = "_allKeys" },
    @{ id = "v92p11"; file = "frontend\src\pages\JobMonitor.vue";     marker = "ai_auto_retry" },
    @{ id = "v92p12"; file = "backend\app\engine\migration_engine.py"; marker = "_apply_advisor_decisions" },
    @{ id = "v92p15"; file = "backend\app\api\routes\jobs.py";         marker = "ai-auto-retry" },
    @{ id = "v92p16"; file = "backend\app\engine\migration_engine.py"; marker = "_st_key" },
    @{ id = "v92p17"; file = "backend\app\engine\error_kb.yml";        marker = "1064_WHILE_END_TO_END_WHILE" },
    @{ id = "v92p18"; file = "backend\app\engine\error_kb.py";         marker = "logger.info" },
    @{ id = "v92p19"; file = "backend\app\engine\migration_engine.py"; marker = "v92p19" },
    @{ id = "v92p20"; file = "backend\app\api\routes\schema.py";       marker = "v92p20" },
    @{ id = "v92p20"; file = "frontend\src\pages\Validate.vue";        marker = "v92p20" },
    @{ id = "v92p21"; file = "backend\app\api\routes\schema.py";       marker = "is_numeric_type" },
    @{ id = "v92p21"; file = "frontend\src\pages\Validate.vue";        marker = "isNumericType" },
    @{ id = "v92p22"; file = "frontend\src\pages\Validate.vue";        marker = "runWithConcurrency" },
    @{ id = "v92p23"; file = "backend\app\api\routes\validate.py";     marker = "ThreadPoolExecutor" },
    @{ id = "v92p23"; file = "frontend\src\pages\Validate.vue";        marker = "concurrencyLevel" }
)

$totalPatches = 0
$appliedPatches = 0
$missingPatches = @()

foreach ($p in $patchMap) {
    $totalPatches++
    $fullPath = Join-Path $ProjectRoot $p.file
    
    if (-not (Test-Path $fullPath)) {
        Write-Host "  ✗ [$($p.id)] 파일 없음: $($p.file)" -ForegroundColor Red
        $missingPatches += "$($p.id) — 파일 없음 ($($p.file))"
        continue
    }
    
    $content = Get-Content $fullPath -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    if ($content -match [regex]::Escape($p.marker)) {
        Write-Host "  ✓ [$($p.id)] $($p.file) — '$($p.marker)' 발견" -ForegroundColor Green
        $appliedPatches++
    }
    else {
        Write-Host "  ✗ [$($p.id)] $($p.file) — '$($p.marker)' 누락" -ForegroundColor Red
        $missingPatches += "$($p.id) — '$($p.marker)' 마커 없음 ($($p.file))"
    }
}

Write-Host "`n════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  결과: $appliedPatches / $totalPatches 적용됨" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan

if ($missingPatches.Count -gt 0) {
    Write-Host "`n누락된 패치 ($($missingPatches.Count)개):" -ForegroundColor Yellow
    foreach ($m in $missingPatches) {
        Write-Host "  - $m" -ForegroundColor Yellow
    }
    Write-Host "`n해결 방법:" -ForegroundColor Cyan
    Write-Host "  1. 누락 패치의 ZIP 을 outputs 폴더에서 찾기" -ForegroundColor White
    Write-Host "  2. databridge_full\ 위에 덮어쓰기" -ForegroundColor White
    Write-Host "  3. 백엔드 재시작 + Ctrl+Shift+R" -ForegroundColor White
    Write-Host "  4. 이 스크립트 다시 실행" -ForegroundColor White
    exit 1
}
else {
    Write-Host "`n✓ 모든 패치 정상 적용됨" -ForegroundColor Green
    Write-Host "`n다음 점검:" -ForegroundColor Cyan
    
    # 백엔드 가동 여부 + 시작 시각
    $procs = Get-Process python -ErrorAction SilentlyContinue
    if ($procs) {
        Write-Host "  Python 프로세스 ($($procs.Count)개):" -ForegroundColor Green
        foreach ($p in $procs) {
            Write-Host "    PID=$($p.Id), Start=$($p.StartTime), CPU=$([math]::Round($p.CPU, 2))" -ForegroundColor White
        }
        $latest = ($procs | Sort-Object StartTime -Descending | Select-Object -First 1).StartTime
        $age = (Get-Date) - $latest
        if ($age.TotalMinutes -gt 60) {
            Write-Host "  ⚠ 가장 최근 프로세스가 $([math]::Round($age.TotalMinutes, 0))분 전 시작 — 최근 패치 반영 의심" -ForegroundColor Yellow
            Write-Host "    → 백엔드 재시작 권장" -ForegroundColor Yellow
        }
        else {
            Write-Host "  ✓ 백엔드 최신 ($([math]::Round($age.TotalMinutes, 0))분 전 시작)" -ForegroundColor Green
        }
    }
    else {
        Write-Host "  ⚠ Python 프로세스 없음 — 백엔드 시작 필요" -ForegroundColor Yellow
        Write-Host "    cd D:\project\databridge_full\backend; .\run_backend.bat" -ForegroundColor White
    }
    
    # API liveness 체크
    Write-Host "`n  API liveness:" -ForegroundColor Cyan
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/system/live" -Method Get -TimeoutSec 3 -ErrorAction Stop
        Write-Host "    ✓ API 응답 OK" -ForegroundColor Green
    }
    catch {
        Write-Host "    ✗ API 응답 없음 또는 오류: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ""
