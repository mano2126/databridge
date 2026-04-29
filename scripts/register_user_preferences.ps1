# v90.5: user_preferences 라우터 등록 스크립트
# main.py 에 한 줄만 추가합니다 (안전한 패턴 매칭)

Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host " user_preferences 라우터 등록 (v90.5)"
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host ""

$mainPath = "D:\project\databridge_full\backend\main.py"

if (-not (Test-Path $mainPath)) {
    Write-Host "❌ main.py 없음" -ForegroundColor Red
    exit 1
}

# 백업
Copy-Item $mainPath "$mainPath.before-v90.5.bak" -Force
Write-Host "[1] 백업: $mainPath.before-v90.5.bak" -ForegroundColor Cyan

# 이미 등록되어 있는지
$content = Get-Content $mainPath -Raw -Encoding UTF8

if ($content -match "user_preferences") {
    Write-Host "✅ 이미 등록됨 — 스킵" -ForegroundColor Green
    exit 0
}

# advisor.router 라인 다음에 추가
$advisorPattern = 'app\.include_router\(advisor\.router'
if ($content -notmatch $advisorPattern) {
    Write-Host "❌ advisor.router 라인 못 찾음 — 수동 추가 필요" -ForegroundColor Red
    Write-Host ""
    Write-Host "다음 코드를 main.py 의 include_router 영역에 추가하세요:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host '# ── v90.5: 사용자 환경설정 (시나리오/DB 사용 이력) ──' -ForegroundColor Gray
    Write-Host 'from app.api.routes import user_preferences' -ForegroundColor Gray
    Write-Host 'app.include_router(user_preferences.router, prefix="/api/v1/user/preferences", tags=["User Preferences"])' -ForegroundColor Gray
    exit 1
}

# 라인별 처리 (안전)
$lines = Get-Content $mainPath
$newLines = New-Object System.Collections.ArrayList
$inserted = $false

for ($i = 0; $i -lt $lines.Count; $i++) {
    [void]$newLines.Add($lines[$i])
    if (-not $inserted -and $lines[$i] -match $advisorPattern) {
        # advisor.router 라인 다음에 삽입
        [void]$newLines.Add('')
        [void]$newLines.Add('# ── v90.5: 사용자 환경설정 (시나리오/DB 사용 이력) ──')
        [void]$newLines.Add('from app.api.routes import user_preferences')
        [void]$newLines.Add('app.include_router(user_preferences.router, prefix="/api/v1/user/preferences", tags=["User Preferences"])')
        $inserted = $true
        Write-Host "[2] Line $($i + 1) 다음에 user_preferences 등록 추가됨" -ForegroundColor Green
    }
}

if (-not $inserted) {
    Write-Host "❌ 삽입 위치 못 찾음" -ForegroundColor Red
    exit 1
}

# UTF-8 (BOM 없이) 저장
[System.IO.File]::WriteAllLines($mainPath, $newLines, (New-Object System.Text.UTF8Encoding $false))
Write-Host "[3] ✅ main.py 저장 완료" -ForegroundColor Green
Write-Host ""
Write-Host "다음 단계:" -ForegroundColor Yellow
Write-Host "  1. 백엔드 재시작:"
Write-Host "     cd D:\project\databridge_full\backend"
Write-Host "     Get-ChildItem -Include '__pycache__' -Recurse -Directory | Remove-Item -Recurse -Force"
Write-Host "     .\venv\Scripts\Activate.ps1"
Write-Host "     uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
Write-Host ""
Write-Host "  2. 검증:"
Write-Host "     Invoke-WebRequest http://localhost:8000/api/v1/user/preferences/scenarios -UseBasicParsing"
