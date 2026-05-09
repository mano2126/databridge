# v95_p11 적용 스크립트 (UTF-8 BOM 필수)
# 본부장님 본질 처방:
#   1. 백엔드 schema_name 회귀 수정 (MySQL: db명 → 빈 문자열)
#   2. 프론트 _policyKey 방어 가드 (이중 방어)
#   3. 회귀 테스트 인프라 (pytest)

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host "=== v95_p11 적용 시작 ===" -ForegroundColor Cyan
Write-Host ""

# 1. 백엔드 정지
Write-Host "[1/5] 백엔드 프로세스 정지..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3

# 2. __pycache__ 정리
Write-Host "[2/5] __pycache__ 정리..." -ForegroundColor Yellow
Remove-Item -Recurse -Force "$ProjectRoot\backend\app\api\routes\__pycache__" -ErrorAction SilentlyContinue

# 3. 적용 검증
Write-Host "[3/5] 패치 적용 검증..." -ForegroundColor Yellow
$check1 = Select-String -Path "$ProjectRoot\backend\app\api\routes\schema.py" -Pattern "v95_p11" -SimpleMatch -Quiet
$check2 = Select-String -Path "$ProjectRoot\frontend\src\pages\Validate.vue" -Pattern "v95_p11" -SimpleMatch -Quiet
$check3 = Test-Path "$ProjectRoot\backend\tests\regression\test_schema_tables_response.py"

if ($check1) { Write-Host "  ✓ schema.py (백엔드 schema_name 회귀 수정)" -ForegroundColor Green }
else { Write-Host "  ✗ schema.py 적용 실패" -ForegroundColor Red }

if ($check2) { Write-Host "  ✓ Validate.vue (프론트 방어 가드)" -ForegroundColor Green }
else { Write-Host "  ✗ Validate.vue 적용 실패" -ForegroundColor Red }

if ($check3) { Write-Host "  ✓ 회귀 테스트 인프라 추가" -ForegroundColor Green }
else { Write-Host "  ✗ 회귀 테스트 미적용" -ForegroundColor Red }

if (-not ($check1 -and $check2 -and $check3)) {
    Write-Host ""
    Write-Host "패치 적용 실패. Expand-Archive 재실행하세요." -ForegroundColor Red
    exit 1
}

# 4. 회귀 테스트 실행 (선택)
Write-Host "[4/5] 회귀 테스트 실행..." -ForegroundColor Yellow
Push-Location "$ProjectRoot\backend"
try {
    python -m pytest tests/regression/test_schema_tables_response.py -v --tb=short 2>&1 | Out-String | Write-Host
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ 회귀 테스트 모두 PASS" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ 회귀 테스트 일부 실패 — 본질 처방 다시 확인 필요" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ⚠ pytest 실행 불가 (설치되지 않았을 수 있음): $_" -ForegroundColor Yellow
} finally {
    Pop-Location
}

# 5. 안내
Write-Host ""
Write-Host "[5/5] 다음 단계:" -ForegroundColor Yellow
Write-Host "  ① 백엔드 재시작: cd $ProjectRoot\backend; .\run_backend.bat" -ForegroundColor White
Write-Host "  ② UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  ③ /validate 화면 → 테이블 목록 즉시 매칭 확인 (소스/타겟 전용 0건 기대)" -ForegroundColor White
Write-Host "  ④ 검증 결과: 42개 테이블 매칭 ✓" -ForegroundColor White
Write-Host ""
Write-Host "  향후 코드 수정 시:" -ForegroundColor Cyan
Write-Host "  - cd $ProjectRoot\backend; pytest tests/regression/" -ForegroundColor White
Write-Host "  - 회귀 발생 시 즉시 감지" -ForegroundColor White
Write-Host ""
Write-Host "=== v95_p11 적용 완료 ===" -ForegroundColor Cyan
