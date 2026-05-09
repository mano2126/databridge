# v95_p9_REAL 적용 스크립트 (UTF-8 BOM 필수)
# 본부장님 5가지 본질 요청 한방에:
#   1. 사이즈 OR 시간 백업 트리거
#   2. 옵션 확장 (5min, 30min, 2h, 12h 추가)
#   3. 최신 위 정렬 토글 (기본 ON)
#   4. 백업+초기화 한방에
#   5. JobWizard 통계 자동 갱신 체크박스 (기본 ON)

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host "=== v95_p9_REAL 적용 시작 ===" -ForegroundColor Cyan
Write-Host ""

# 1. 백엔드 정지
Write-Host "[1/5] 백엔드 프로세스 정지..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3

# 2. __pycache__ 정리
Write-Host "[2/5] __pycache__ 정리..." -ForegroundColor Yellow
Remove-Item -Recurse -Force "$ProjectRoot\backend\app\api\routes\__pycache__" -ErrorAction SilentlyContinue

# 3. 어제 v95_p9 죽은 파일 명시적 삭제
Write-Host "[3/5] 어제 v95_p9 잘못된 파일 정리 (죽은 코드 제거)..." -ForegroundColor Yellow
$deadFiles = @(
    "$ProjectRoot\backend\app\api\logs.py",
    "$ProjectRoot\backend\app\core\logging_setup.py",
    "$ProjectRoot\frontend\src\views\LogViewer.vue",
    "$ProjectRoot\backend\scripts\v95_p9_main_py_patch.txt",
    "$ProjectRoot\backend\scripts\apply_v95_p9.ps1"
)
foreach ($f in $deadFiles) {
    if (Test-Path $f) {
        Remove-Item -Force $f
        Write-Host "  ✗ 삭제: $f" -ForegroundColor DarkGray
    }
}
$viewsDir = "$ProjectRoot\frontend\src\views"
if ((Test-Path $viewsDir) -and (-not (Get-ChildItem $viewsDir -Recurse -File -ErrorAction SilentlyContinue))) {
    Remove-Item -Recurse -Force $viewsDir
    Write-Host "  ✗ 삭제: $viewsDir (빈 디렉토리)" -ForegroundColor DarkGray
}
if (Test-Path "$ProjectRoot\backend\app\core\view_analyzer_logging.py") {
    Write-Host "  ✓ 보존: view_analyzer_logging.py (다음 턴 view-timeout 진단용)" -ForegroundColor Green
}

# 4. 적용 검증
Write-Host "[4/5] 패치 적용 검증..." -ForegroundColor Yellow
$check1 = Select-String -Path "$ProjectRoot\backend\app\api\routes\settings.py" -Pattern "v95_p9_REAL" -SimpleMatch -Quiet
$check2 = Select-String -Path "$ProjectRoot\frontend\src\pages\Settings.vue" -Pattern "v95_p9_REAL" -SimpleMatch -Quiet
$check3 = Select-String -Path "$ProjectRoot\frontend\src\pages\JobWizard.vue" -Pattern "v95_p9_REAL" -SimpleMatch -Quiet

if ($check1) { Write-Host "  ✓ settings.py (백엔드 사이즈 OR 조건)" -ForegroundColor Green }
else         { Write-Host "  ✗ settings.py 적용 실패" -ForegroundColor Red }

if ($check2) { Write-Host "  ✓ Settings.vue (정렬 토글 + 백업+초기화)" -ForegroundColor Green }
else         { Write-Host "  ✗ Settings.vue 적용 실패" -ForegroundColor Red }

if ($check3) { Write-Host "  ✓ JobWizard.vue (통계 자동 갱신 체크박스)" -ForegroundColor Green }
else         { Write-Host "  ✗ JobWizard.vue 적용 실패" -ForegroundColor Red }

if (-not ($check1 -and $check2 -and $check3)) {
    Write-Host ""
    Write-Host "패치 적용 실패. Expand-Archive 재실행하세요." -ForegroundColor Red
    exit 1
}

# 5. 안내
Write-Host ""
Write-Host "[5/5] 다음 단계:" -ForegroundColor Yellow
Write-Host "  ① 백엔드 재시작: cd $ProjectRoot\backend; .\run_backend.bat" -ForegroundColor White
Write-Host "  ② UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  ③ Settings → 자동백업 select에 새 옵션 8개 확인" -ForegroundColor White
Write-Host "  ④ 로그 뷰어 → '⬆ 최신위' 토글 + '🗑 백업+초기화' 버튼 확인" -ForegroundColor White
Write-Host "  ⑤ JobWizard → 실행 옵션에 '📊 STATS 통계 자동 갱신' 체크박스 (기본 ON)" -ForegroundColor White
Write-Host ""
Write-Host "=== v95_p9_REAL 적용 완료 ===" -ForegroundColor Cyan
