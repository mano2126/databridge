# v95_p9 적용 스크립트 (UTF-8 BOM 필수)
# 통합 로깅 + LogViewer 개편

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"

Write-Host "=== v95_p9 적용 시작 ===" -ForegroundColor Cyan
Write-Host ""

# 1. 백엔드 정지
Write-Host "[1/5] 백엔드 프로세스 정지..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3

# 2. __pycache__ 정리
Write-Host "[2/5] __pycache__ 정리..." -ForegroundColor Yellow
Remove-Item -Recurse -Force "$ProjectRoot\backend\app\core\__pycache__" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$ProjectRoot\backend\app\api\__pycache__" -ErrorAction SilentlyContinue

# 3. 로그 디렉토리 보장
Write-Host "[3/5] 로그 디렉토리 확인..." -ForegroundColor Yellow
$LogDir = "$ProjectRoot\backend\logs"
$ArchiveDir = "$LogDir\archive"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
if (-not (Test-Path $ArchiveDir)) { New-Item -ItemType Directory -Path $ArchiveDir | Out-Null }

# 4. 적용된 파일 검증 (findstr)
Write-Host "[4/5] 패치 파일 적용 검증..." -ForegroundColor Yellow
$check1 = Select-String -Path "$ProjectRoot\backend\app\core\logging_setup.py" -Pattern "v95_p9" -SimpleMatch -Quiet
$check2 = Select-String -Path "$ProjectRoot\backend\app\api\logs.py" -Pattern "v95_p9" -SimpleMatch -Quiet
$check3 = Select-String -Path "$ProjectRoot\frontend\src\views\LogViewer.vue" -Pattern "v95_p9" -SimpleMatch -Quiet

if ($check1 -and $check2 -and $check3) {
    Write-Host "  ✓ logging_setup.py" -ForegroundColor Green
    Write-Host "  ✓ logs.py" -ForegroundColor Green
    Write-Host "  ✓ LogViewer.vue" -ForegroundColor Green
} else {
    Write-Host "  ✗ 일부 파일 적용 안됨 — Expand-Archive 재실행 필요" -ForegroundColor Red
    exit 1
}

# 5. 안내
Write-Host ""
Write-Host "[5/5] 다음 단계 (수동):" -ForegroundColor Yellow
Write-Host "  ① main.py 패치 (v95_p9_main_py_patch.txt 참조)" -ForegroundColor White
Write-Host "  ② frontend/src/router/index.js 에 /logs 라우트 추가" -ForegroundColor White
Write-Host "  ③ 백엔드 재시작: cd $ProjectRoot\backend; .\run_backend.bat" -ForegroundColor White
Write-Host "  ④ UI Ctrl+Shift+R → /logs 접속" -ForegroundColor White
Write-Host ""
Write-Host "=== v95_p9 파일 배치 완료 ===" -ForegroundColor Cyan
