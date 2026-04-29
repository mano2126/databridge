# ===============================================================
# Phase A-3 배포 상태 진단 스크립트
# 파일명: diagnose_phase_a3.ps1
# 용도: Phase A-3 패치가 실제로 반영됐는지 정확히 확인
# 실행: cd D:\project\databridge_full\backend\scripts
#       .\diagnose_phase_a3.ps1
# ===============================================================

Write-Host "`n🔬 Phase A-3 배포 상태 진단`n" -ForegroundColor Cyan

$base = "D:\project\databridge_full\backend"

# ── 1) 파일 존재 여부 ───────────────────────────────
Write-Host "[1/5] 파일 존재 여부 확인" -ForegroundColor Yellow
$files = @(
    "$base\app\monitor\import_retry.py",
    "$base\app\monitor\adapter_localhost.py",
    "$base\app\monitor\adapter_docker.py",
    "$base\app\monitor\registry.py",
    "$base\app\api\routes\system_live.py"
)
foreach ($f in $files) {
    if (Test-Path $f) {
        $size = (Get-Item $f).Length
        $mtime = (Get-Item $f).LastWriteTime.ToString("yyyy-MM-dd HH:mm")
        Write-Host "  ✓ $($f.Substring($base.Length+1))  $size bytes  [$mtime]" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $f  없음!" -ForegroundColor Red
    }
}
Write-Host ""

# ── 2) import_retry 내용 체크 (진짜 Phase A-3 코드인지) ──
Write-Host "[2/5] import_retry.py 내용 검증" -ForegroundColor Yellow
$ir = "$base\app\monitor\import_retry.py"
if (Test-Path $ir) {
    $has_invalidate = Select-String -Path $ir -Pattern "invalidate_caches" -Quiet
    $has_try_import = Select-String -Path $ir -Pattern "def try_import" -Quiet
    if ($has_invalidate -and $has_try_import) {
        Write-Host "  ✓ invalidate_caches + try_import 함수 존재 — 진짜 Phase A-3" -ForegroundColor Green
    } else {
        Write-Host "  ✗ 파일 내용이 Phase A-3 코드가 아님!" -ForegroundColor Red
    }
} else {
    Write-Host "  ✗ 파일 없음 — Phase A-3 미배포" -ForegroundColor Red
}
Write-Host ""

# ── 3) adapter_localhost 가 try_import 쓰는지 ────────
Write-Host "[3/5] adapter_localhost.py 가 try_import 사용하는지" -ForegroundColor Yellow
$al = "$base\app\monitor\adapter_localhost.py"
if (Test-Path $al) {
    $uses_try_import = Select-String -Path $al -Pattern "from app.monitor.import_retry import try_import" -Quiet
    if ($uses_try_import) {
        Write-Host "  ✓ try_import 사용 중 — Phase A-3 적용됨" -ForegroundColor Green
    } else {
        Write-Host "  ✗ try_import 사용 안 함 — 옛 버전!" -ForegroundColor Red
        Write-Host "    Phase A-3 zip 이 제대로 덮어쓰기되지 않음" -ForegroundColor Red
    }
}
Write-Host ""

# ── 4) .pyc 캐시 정리 필요? ───────────────────────────
Write-Host "[4/5] __pycache__ 상태" -ForegroundColor Yellow
$pycache = "$base\app\monitor\__pycache__"
if (Test-Path $pycache) {
    $pyc_count = (Get-ChildItem $pycache -Filter "*.pyc").Count
    Write-Host "  __pycache__ 존재: .pyc 파일 $pyc_count 개" -ForegroundColor Gray
    if ($pyc_count -gt 0) {
        Write-Host "  → .pyc 가 옛 코드라면 uvicorn 이 옛 코드 실행 중일 수 있음" -ForegroundColor Yellow
    }
} else {
    Write-Host "  __pycache__ 없음 (깨끗)" -ForegroundColor Green
}
Write-Host ""

# ── 5) 실제 API 응답 검증 ─────────────────────────────
Write-Host "[5/5] API 실제 응답 — Phase A-3 적용됐는지 확인" -ForegroundColor Yellow
try {
    $r = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/system/health" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "  API 응답 수신 OK" -ForegroundColor Green
    
    # Phase A-3 의 증거: import_retry 필드 존재
    if ($r.import_retry) {
        Write-Host "  ✅ import_retry 필드 존재 — Phase A-3 코드 실행 중!" -ForegroundColor Green
        Write-Host "     cooldown_sec: $($r.import_retry.cooldown_sec)"
        if ($r.import_retry.failed_modules) {
            $failed = $r.import_retry.failed_modules | ConvertTo-Json -Compress
            Write-Host "     failed_modules: $failed" -ForegroundColor Yellow
        } else {
            Write-Host "     failed_modules: (없음)" -ForegroundColor Gray
        }
    } else {
        Write-Host "  ❌ import_retry 필드 없음 — Phase A-3 코드 반영 안 됨!" -ForegroundColor Red
        Write-Host "     → uvicorn 이 옛 코드로 실행 중. 완전 재시작 필요" -ForegroundColor Yellow
    }
    
    # psutil 상태
    Write-Host ""
    Write-Host "  psutil: available=$($r.psutil.available), error=$($r.psutil.error)" -ForegroundColor $(if ($r.psutil.available) { "Green" } else { "Red" })
    Write-Host "  docker: available=$($r.docker.available), error=$($r.docker.error)" -ForegroundColor $(if ($r.docker.available) { "Green" } else { "Red" })
    
} catch {
    Write-Host "  ❌ API 응답 실패: $_" -ForegroundColor Red
}
Write-Host ""

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "진단 완료. 결과를 Claude 에게 공유하세요." -ForegroundColor Cyan
Write-Host ""
