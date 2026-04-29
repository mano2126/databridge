# ===============================================================
# POC: Python import 런타임 감지 검증
# 파일명: poc_import_retry.ps1
# 용도: psutil 같은 모듈의 런타임 설치 후 재감지 가능성 테스트
# 안전: 백엔드와 무관한 별도 Python 프로세스 — 이관에 영향 없음
# 실행:
#   cd D:\project\databridge_full\scripts
#   .\poc_import_retry.ps1
# ===============================================================

Write-Host "`n🔬 POC: Python import 캐시 동작 검증" -ForegroundColor Cyan
Write-Host "   (백엔드와 무관한 별도 Python 프로세스로 실행)`n" -ForegroundColor Gray

# 백엔드가 쓰는 Python 경로 자동 감지
$backendPy = $null
try {
    $proc = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
    if ($proc) {
        $backendPy = (Get-Process -Id $proc.OwningProcess).Path
    }
} catch {}

if (-not $backendPy) {
    Write-Host "⚠️ 백엔드 프로세스 자동 감지 실패 — 기본 Python 사용" -ForegroundColor Yellow
    $backendPy = "C:\Users\박지안\AppData\Local\Programs\Python\Python311\python.exe"
}

Write-Host "  Python 경로: $backendPy`n" -ForegroundColor Gray

# POC Python 스크립트 (임시 파일로 저장 후 실행 — 인용 문제 회피)
$pocPy = @"
import sys, importlib

print('=' * 60)
print('POC: import 캐시 동작 검증')
print('=' * 60)
print(f'Python: {sys.version.split()[0]}')
print()

# 실험 1 — 없는 패키지 import 실패 시 sys.modules 상태
print('[실험 1] 없는 패키지 import 실패 후 sys.modules 상태')
try:
    import nonexistent_xyz_test_pkg_abc
except ImportError:
    print('  ImportError 발생: OK')
in_modules = 'nonexistent_xyz_test_pkg_abc' in sys.modules
print(f'  sys.modules 에 남음?: {in_modules}')
if in_modules:
    val = sys.modules['nonexistent_xyz_test_pkg_abc']
    print(f'  타입: {type(val).__name__}, 값: {val!r}')
print()

# 실험 2 — 실패 캐시 후 invalidate_caches + 재import
print('[실험 2] 실패 캐시 후 invalidate_caches + 재import')
if 'psutil' in sys.modules:
    del sys.modules['psutil']
sys.modules['psutil'] = None
print('  sys.modules[psutil] = None (실패 캐싱 시뮬레이션)')

try:
    import psutil as _p1
    print(f'  1차 import: 성공 ({_p1.__version__})')
except Exception as e:
    print(f'  1차 import 실패: {type(e).__name__}: {str(e)[:60]}')

if 'psutil' in sys.modules:
    del sys.modules['psutil']
importlib.invalidate_caches()

try:
    import psutil as _p2
    print(f'  invalidate 후 재import 성공! ver={_p2.__version__}')
except ImportError as e:
    print(f'  invalidate 후에도 실패: {e}')
print()

# 실험 3 — importlib.import_module 방식
print('[실험 3] importlib.import_module 방식')
if 'psutil' in sys.modules:
    del sys.modules['psutil']
try:
    importlib.invalidate_caches()
    m = importlib.import_module('psutil')
    print(f'  importlib.import_module 성공: ver={m.__version__}')
except Exception as e:
    print(f'  실패: {type(e).__name__}: {e}')
print()

# 실험 4 — docker SDK 도 확인
print('[실험 4] docker SDK 동일 테스트')
if 'docker' in sys.modules:
    del sys.modules['docker']
sys.modules['docker'] = None
try:
    import docker as _d1
    print(f'  1차 import 실패 예상 but 성공: {_d1.__version__}')
except Exception as e:
    print(f'  1차 실패 (예상대로): {type(e).__name__}')

if 'docker' in sys.modules:
    del sys.modules['docker']
importlib.invalidate_caches()
try:
    import docker as _d2
    print(f'  invalidate 후 재import 성공! ver={_d2.__version__}')
except Exception as e:
    print(f'  실패: {e}')
print()

print('=' * 60)
print('결론 분석')
print('=' * 60)
print('실험 2/3/4 가 모두 성공 → 해법 A(invalidate_caches) 사용 가능')
print('실험 3 만 성공 → importlib.import_module() 필수')
print('모두 실패 → 해법 B(subprocess) 필요')
"@

$tmpPy = [System.IO.Path]::GetTempFileName() + ".py"
Set-Content -Path $tmpPy -Value $pocPy -Encoding UTF8
try {
    & $backendPy $tmpPy
} finally {
    Remove-Item $tmpPy -ErrorAction SilentlyContinue
}

Write-Host "`n✅ POC 완료" -ForegroundColor Green
Write-Host "위 결과를 Claude 에게 공유해주세요.`n" -ForegroundColor Yellow
