# v90.36 강제 재배포 - 캐시 완전 삭제 + 적용
# 본부장님 환경에 v90.33/34 가 적용 안 된 것으로 확인됨
# 이 스크립트는 모든 캐시 삭제 후 강제 재배포

Write-Host ""
Write-Host "===== v90.36 강제 재배포 시작 =====" -ForegroundColor Cyan
Write-Host ""

# 1. 백엔드 강제 종료 (응답 안 해도 강제)
Write-Host "[1/6] 백엔드 프로세스 강제 종료" -ForegroundColor Yellow
$pythonProcs = Get-Process python -ErrorAction SilentlyContinue
if ($pythonProcs) {
    Write-Host "    종료 대상: $(($pythonProcs | Measure-Object).Count) 개 프로세스"
    $pythonProcs | Stop-Process -Force
    Start-Sleep -Seconds 2
    Write-Host "    완료" -ForegroundColor Green
} else {
    Write-Host "    실행 중 Python 없음" -ForegroundColor Gray
}

# 2. ZIP 추출
Write-Host ""
Write-Host "[2/6] ZIP 추출" -ForegroundColor Yellow
$zipPath = "$env:USERPROFILE\Downloads\databridge_v90_36_fix.zip"
if (-not (Test-Path $zipPath)) {
    Write-Host "    ✗ ZIP 파일 없음: $zipPath" -ForegroundColor Red
    Write-Host "    Downloads 폴더에 ZIP 다운로드 후 다시 실행하세요" -ForegroundColor Red
    exit 1
}
Remove-Item -Path "C:\Temp\v90_36" -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive -Path $zipPath -DestinationPath "C:\Temp\v90_36" -Force
Write-Host "    완료" -ForegroundColor Green

# 3. 파일 복사 + 시각 확인
Write-Host ""
Write-Host "[3/6] 파일 복사" -ForegroundColor Yellow
Copy-Item "C:\Temp\v90_36\databridge_full\*" "D:\project\databridge_full\" -Recurse -Force

# 핵심 파일 시각 확인
$parser = "D:\project\databridge_full\backend\app\core\ai_response_parser.py"
$postproc = "D:\project\databridge_full\backend\app\core\sql_post_processor.py"
Write-Host "    ai_response_parser.py: $((Get-Item $parser).LastWriteTime)"
Write-Host "    sql_post_processor.py: $((Get-Item $postproc).LastWriteTime)"

# v90.33 마커 확인
$parserContent = Get-Content $parser -Raw
if ($parserContent -match "catastrophic backtracking") {
    Write-Host "    ✓ v90.33 마커 확인됨" -ForegroundColor Green
} else {
    Write-Host "    ✗ v90.33 마커 없음 - 복사 실패!" -ForegroundColor Red
    exit 1
}

# 4. Python 캐시 완전 삭제 (★ 핵심 ★)
Write-Host ""
Write-Host "[4/6] Python 캐시 완전 삭제 (★ 핵심 ★)" -ForegroundColor Yellow
$pycache = Get-ChildItem -Path "D:\project\databridge_full\backend" -Filter "__pycache__" -Recurse -Directory -ErrorAction SilentlyContinue
$cnt = ($pycache | Measure-Object).Count
Write-Host "    삭제 대상: $cnt 개 폴더"
$pycache | Remove-Item -Recurse -Force
Write-Host "    완료" -ForegroundColor Green

# .pyc 파일도 삭제
$pyc = Get-ChildItem -Path "D:\project\databridge_full\backend" -Filter "*.pyc" -Recurse -ErrorAction SilentlyContinue
$pycCnt = ($pyc | Measure-Object).Count
if ($pycCnt -gt 0) {
    Write-Host "    .pyc 파일 추가 삭제: $pycCnt 개"
    $pyc | Remove-Item -Force
}

# 5. Vite 캐시도 삭제
Write-Host ""
Write-Host "[5/6] Vite 캐시 삭제" -ForegroundColor Yellow
$vite = "D:\project\databridge_full\frontend\node_modules\.vite"
if (Test-Path $vite) {
    Remove-Item -Path $vite -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "    완료" -ForegroundColor Green
} else {
    Write-Host "    Vite 캐시 없음" -ForegroundColor Gray
}

# 6. 백엔드 시작 안내
Write-Host ""
Write-Host "[6/6] 다음 단계 - 수동 시작" -ForegroundColor Yellow
Write-Host ""
Write-Host "  ★ 백엔드 시작 (새 PowerShell 창에서):" -ForegroundColor White
Write-Host "    cd D:\project\databridge_full\backend"
Write-Host "    .\venv\Scripts\Activate.ps1"
Write-Host "    uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
Write-Host ""
Write-Host "  ★ 프론트 시작 (새 PowerShell 창에서):" -ForegroundColor White
Write-Host "    cd D:\project\databridge_full\frontend"
Write-Host "    npm run dev"
Write-Host ""
Write-Host "  ★ 브라우저: Ctrl+Shift+R (캐시 무시 새로고침)" -ForegroundColor White
Write-Host ""
Write-Host "===== 재배포 완료 =====" -ForegroundColor Cyan
