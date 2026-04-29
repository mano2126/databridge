# v89.8 main.py 라우터 등록 강제 패치
# 본부장님 환경에서 pii/adaptive/system_live 라우터가 모두 등록 안 됐을 때 해결

Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host " v89.8 main.py 라우터 등록 강제 패치"
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host ""

$mainPath = "D:\project\databridge_full\backend\main.py"

# 1. 백업
$backupPath = "$mainPath.before-v89.8.bak"
Copy-Item $mainPath $backupPath -Force
Write-Host "[1] 백업 생성: $backupPath" -ForegroundColor Cyan
Write-Host ""

# 2. 현재 등록 상태 확인
$content = Get-Content $mainPath -Raw
Write-Host "[2] 현재 등록 상태:" -ForegroundColor Cyan
$hasPii = $content -match "pii\.router"
$hasAdaptive = $content -match "adaptive_resource\.router"
$hasSysLive = $content -match "system_live"

Write-Host "  pii.router       : $(if ($hasPii) {'✅ 있음'} else {'❌ 없음'})"
Write-Host "  adaptive_resource: $(if ($hasAdaptive) {'✅ 있음'} else {'❌ 없음'})"
Write-Host "  system_live      : $(if ($hasSysLive) {'✅ 있음'} else {'❌ 없음'})"
Write-Host ""

# 3. 정확한 advisor 라인 찾기 (어떤 형식이든 매칭)
Write-Host "[3] advisor 라인 찾기..." -ForegroundColor Cyan
$lines = Get-Content $mainPath
$advisorLineIdx = -1
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match "include_router\(advisor\.router") {
        $advisorLineIdx = $i
        Write-Host "  ✅ Line $($i + 1): $($lines[$i])" -ForegroundColor Green
        break
    }
}

if ($advisorLineIdx -lt 0) {
    Write-Host "  ❌ advisor.router 라인 없음 — 다른 라우터 다음에 추가" -ForegroundColor Yellow
    # ai_assistant 다음에 추가
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "include_router\(ai_assistant\.router") {
            $advisorLineIdx = $i
            Write-Host "  ✅ ai_assistant 라인 사용: Line $($i + 1)" -ForegroundColor Yellow
            break
        }
    }
}

if ($advisorLineIdx -lt 0) {
    Write-Host "  ❌ 적절한 삽입 위치 못 찾음" -ForegroundColor Red
    exit 1
}
Write-Host ""

# 4. 추가할 패치 코드 (이미 있는 건 skip)
$patchLines = @()

if (-not $hasPii) {
    $patchLines += ""
    $patchLines += "# ── v89 (Phase F-1f): PII Privacy ──────────────────────────────"
    $patchLines += "from app.api.routes import pii"
    $patchLines += 'app.include_router(pii.router, prefix=P + "/pii", tags=["PII Privacy"])'
}

if (-not $hasAdaptive) {
    $patchLines += ""
    $patchLines += "# ── v89 (Phase I): Adaptive Resource Control ───────────────────"
    $patchLines += "from app.api.routes import adaptive_resource"
    $patchLines += 'app.include_router(adaptive_resource.router, prefix=P, tags=["Adaptive Resource"])'
}

if (-not $hasSysLive) {
    $patchLines += ""
    $patchLines += "# ── v89.8 (Phase A-1): 실시간 멀티 타겟 모니터 ─────────────────"
    $patchLines += "from app.api.routes import system_live as system_live_routes"
    $patchLines += 'app.include_router(system_live_routes.router, prefix=P, tags=["System Monitor"])'
}

if ($patchLines.Count -eq 0) {
    Write-Host "[4] 추가할 라우터 없음 — 모두 이미 등록됨" -ForegroundColor Green
    Write-Host "    그런데도 작동 안 하면 다른 문제 (백엔드 로그 확인)" -ForegroundColor Yellow
    exit 0
}

Write-Host "[4] 추가할 코드 ($($patchLines.Count) 라인):" -ForegroundColor Cyan
$patchLines | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
Write-Host ""

# 5. 라인 배열 조작 - advisor 라인 다음에 패치 삽입
$newLines = New-Object System.Collections.ArrayList
for ($i = 0; $i -lt $lines.Count; $i++) {
    [void]$newLines.Add($lines[$i])
    if ($i -eq $advisorLineIdx) {
        # advisor 라인 바로 다음에 패치 삽입
        foreach ($p in $patchLines) {
            [void]$newLines.Add($p)
        }
    }
}

# 6. 파일 쓰기
$newLines | Set-Content -Path $mainPath -Encoding UTF8
Write-Host "[5] main.py 업데이트 완료" -ForegroundColor Green
Write-Host ""

# 7. 검증
$newContent = Get-Content $mainPath -Raw
$ok = $true
if (-not ($newContent -match "pii\.router")) { $ok = $false; Write-Host "  ❌ pii.router 추가 실패" -ForegroundColor Red }
if (-not ($newContent -match "adaptive_resource\.router")) { $ok = $false; Write-Host "  ❌ adaptive 추가 실패" -ForegroundColor Red }
if (-not ($newContent -match "system_live")) { $ok = $false; Write-Host "  ❌ system_live 추가 실패" -ForegroundColor Red }

if ($ok) {
    Write-Host "[6] ✅ 모든 라우터 등록 확인됨" -ForegroundColor Green
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════════"
    Write-Host " 다음 단계"
    Write-Host "═══════════════════════════════════════════════════════════════"
    Write-Host ""
    Write-Host "1. 백엔드 캐시 삭제 + 재시작:" -ForegroundColor Yellow
    Write-Host "   cd D:\project\databridge_full\backend"
    Write-Host "   Get-ChildItem -Include '__pycache__' -Recurse -Directory | Remove-Item -Recurse -Force"
    Write-Host "   .\venv\Scripts\Activate.ps1"
    Write-Host "   uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
    Write-Host ""
    Write-Host "2. 백엔드 시작 후 테스트:"
    Write-Host "   Invoke-WebRequest http://localhost:8000/api/v1/system/health -UseBasicParsing"
    Write-Host ""
    Write-Host "3. 브라우저 Ctrl+Shift+R"
}
