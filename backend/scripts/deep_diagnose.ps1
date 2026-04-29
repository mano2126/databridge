# ===============================================================
# Phase A-3 실패 근본 원인 심층 진단
# 파일명: deep_diagnose.ps1
# 용도: 백엔드가 왜 psutil/docker import 실패하는지 정확히 파악
# 실행: cd D:\project\databridge_full\backend\scripts
#       .\deep_diagnose.ps1
# ===============================================================

Write-Host "`n🔬 Phase A-3 심층 진단 — 진짜 원인 탐색`n" -ForegroundColor Cyan

# ── 1) 백엔드 프로세스가 실제로 쓰는 Python ─────────────
Write-Host "[1/5] 백엔드 프로세스 상세 정보" -ForegroundColor Yellow
$proc = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($proc) {
    $p = Get-Process -Id $proc.OwningProcess
    Write-Host "  PID: $($p.Id)" -ForegroundColor Gray
    Write-Host "  Path: $($p.Path)" -ForegroundColor Gray
    Write-Host "  Name: $($p.Name)" -ForegroundColor Gray
    $backendPy = $p.Path
    
    # CommandLine 확인 (어떻게 실행됐는지)
    try {
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)").CommandLine
        Write-Host "  CommandLine: $cmd" -ForegroundColor Gray
    } catch {}
} else {
    Write-Host "  ❌ 백엔드 프로세스 없음!" -ForegroundColor Red
    exit 1
}
Write-Host ""

# ── 2) 그 Python 의 sys.path 확인 ────────────────────────
Write-Host "[2/5] 백엔드 Python의 sys.path + site-packages" -ForegroundColor Yellow
$testCode = "import sys; print(chr(10).join(sys.path))"
& $backendPy -c $testCode 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
Write-Host ""

# ── 3) 그 Python 에서 직접 import psutil 시도 ────────────
Write-Host "[3/5] 백엔드 Python 에서 psutil/docker 직접 import 테스트" -ForegroundColor Yellow
$testCode = @"
import sys
print('Python:', sys.executable)
print('Version:', sys.version.split()[0])
print()
print('[psutil]')
try:
    import psutil
    print('  OK:', psutil.__version__)
    print('  Location:', psutil.__file__)
except Exception as e:
    print(f'  FAIL: {type(e).__name__}: {e}')
print()
print('[docker]')
try:
    import docker
    print('  OK:', docker.__version__)
    print('  Location:', docker.__file__)
except Exception as e:
    print(f'  FAIL: {type(e).__name__}: {e}')
"@
# 파일로 저장 (-c 로 넘기기엔 복잡)
$tmpPy = [System.IO.Path]::GetTempFileName() + ".py"
Set-Content -Path $tmpPy -Value $testCode -Encoding UTF8
try {
    & $backendPy $tmpPy 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
} finally {
    Remove-Item $tmpPy -ErrorAction SilentlyContinue
}
Write-Host ""

# ── 4) 백엔드가 실제로 임포트를 어떻게 하는지 ────────────
Write-Host "[4/5] 백엔드의 import_retry 실제 호출 로그 확인" -ForegroundColor Yellow
Write-Host "  /api/v1/system/live 호출 후 3초 내 uvicorn 로그에서 에러 확인" -ForegroundColor Gray

# 호출
try {
    Invoke-RestMethod -Uri "http://localhost:8000/api/v1/system/live" -TimeoutSec 5 | Out-Null
    Write-Host "  ✓ API 호출 완료 (uvicorn 창의 로그 확인)" -ForegroundColor Green
} catch {}
Write-Host "  ⚠️ 본부장님, uvicorn 실행 창의 최근 로그를 공유해주세요." -ForegroundColor Yellow
Write-Host ""

# ── 5) 궁극의 테스트 — import_retry 의 try_import 를 같은 Python 에서 직접 호출 ─
Write-Host "[5/5] try_import 함수를 같은 Python 에서 직접 호출 (결정적 테스트)" -ForegroundColor Yellow
$testCode2 = @"
import sys
import os
# 백엔드 app 경로 추가
sys.path.insert(0, r'D:\project\databridge_fullackend')

print('Python:', sys.executable)
print()

# 백엔드가 쓰는 바로 그 try_import 함수 로드
from app.monitor.import_retry import try_import, get_status, reset_retry_state

# 쿨다운 초기화 (상태 깨끗하게)
reset_retry_state()
print('상태 초기화됨')
print()

# psutil 시도
print('[psutil try_import]')
psutil = try_import('psutil')
if psutil is None:
    print('  FAIL — None 반환')
    print('  상태:', get_status())
else:
    print(f'  SUCCESS: {psutil.__version__}')

# docker 시도
print()
print('[docker try_import]')
docker = try_import('docker')
if docker is None:
    print('  FAIL — None 반환')
    print('  상태:', get_status())
else:
    print(f'  SUCCESS: {docker.__version__}')

print()
print('sys.modules 상태 (psutil/docker 만):')
for k in ['psutil', 'docker']:
    v = sys.modules.get(k, '미등록')
    print(f'  {k}: {type(v).__name__ if v is not None else v}')
"@
$tmpPy2 = [System.IO.Path]::GetTempFileName() + ".py"
Set-Content -Path $tmpPy2 -Value $testCode2 -Encoding UTF8
try {
    & $backendPy $tmpPy2 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
} finally {
    Remove-Item $tmpPy2 -ErrorAction SilentlyContinue
}
Write-Host ""

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "진단 완료. 전체 결과 공유해주세요." -ForegroundColor Cyan
Write-Host ""
