# 프론트 렌더링 문제 진단
# 파일명: diagnose_frontend_render.ps1

Write-Host "`n🔬 프론트 렌더링 문제 진단`n" -ForegroundColor Cyan

$jobId = "fe80eb29-b9c6-4084-a446-54eccca3a38f"

# ── 1) verify API 가 실제로 has_data:true 반환하는지 ───
Write-Host "[1/4] verify API 반환 검증 (백엔드 OK 확인)" -ForegroundColor Yellow
try {
    $v = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/report/verify/$jobId" -TimeoutSec 10
    $impact = $v.advisor_impact
    if ($impact.has_data) {
        Write-Host "  ✓ advisor_impact.has_data = TRUE" -ForegroundColor Green
        Write-Host "    applied:  $($impact.summary.applied)" -ForegroundColor Gray
        Write-Host "    measured: $($impact.summary.measured_count)" -ForegroundColor Gray
        Write-Host "    savings:  $($impact.summary.estimated_savings)" -ForegroundColor Gray
        Write-Host "  🎯 백엔드는 완벽! 문제는 프론트에 있음" -ForegroundColor Green
    } else {
        Write-Host "  ✗ has_data: FALSE — reason: $($impact.reason)" -ForegroundColor Red
    }
} catch {
    Write-Host "  ✗ API 실패: $_" -ForegroundColor Red
}

# ── 2) 리포트 페이지가 쓰는 파일 확인 ─────────────
Write-Host ""
Write-Host "[2/4] 리포트 페이지 라우팅 확인 - 어느 Vue 파일 쓰나?" -ForegroundColor Yellow
$routerFiles = Get-ChildItem -Path "D:\project\databridge_full\frontend\src" -Recurse -Filter "*.js" | Where-Object { $_.Name -like "*router*" -or $_.Name -eq "index.js" }
foreach ($f in $routerFiles) {
    $content = Get-Content $f.FullName -Raw
    if ($content -and ($content -like "*MigrationReport*" -or $content -like "*Report*")) {
        Write-Host "  파일: $($f.Name)" -ForegroundColor Gray
        $lines = Get-Content $f.FullName
        for ($i=0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match "Report|report") {
                Write-Host "    line $($i+1): $($lines[$i])" -ForegroundColor Gray
            }
        }
        break
    }
}

# ── 3) MigrationReport.vue 에 v10 #23 코드 반영됐는지 재확인 ─
Write-Host ""
Write-Host "[3/4] MigrationReport.vue 의 v10 #23 코드 반영 상태" -ForegroundColor Yellow
$mrPath = "D:\project\databridge_full\frontend\src\pages\MigrationReport.vue"
if (Test-Path $mrPath) {
    $checks = @{
        "verifyReport ref" = "verifyReport\s*=\s*ref"
        "verify API 호출" = "/api/v1/report/verify|axios.get.*verify"
        "hasAdvisorData computed" = "hasAdvisorData"
        "advisor_impact 템플릿" = "advisorImpact|advisor_impact"
        "AI DBA Consultant 섹션 제목" = "AI DBA Consultant"
    }
    foreach ($name in $checks.Keys) {
        $hit = Select-String -Path $mrPath -Pattern $checks[$name] -Quiet
        if ($hit) {
            Write-Host "  ✓ $name" -ForegroundColor Green
        } else {
            Write-Host "  ✗ $name — 코드 없음!" -ForegroundColor Red
        }
    }
} else {
    Write-Host "  ✗ MigrationReport.vue 없음!" -ForegroundColor Red
}

# ── 4) 캐시/빌드 확인 ─────────────────────────
Write-Host ""
Write-Host "[4/4] 프론트 빌드 / 캐시 상태" -ForegroundColor Yellow
$distPath = "D:\project\databridge_full\frontend\dist"
if (Test-Path $distPath) {
    $latestDist = Get-ChildItem -Path $distPath -Recurse | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    Write-Host "  dist 최신 파일: $($latestDist.LastWriteTime)" -ForegroundColor Gray
} else {
    Write-Host "  dist 폴더 없음 (개발 모드 실행 중일 수 있음 — 정상)" -ForegroundColor Gray
}

$vuefile = Get-Item $mrPath
Write-Host "  MigrationReport.vue 수정 시각: $($vuefile.LastWriteTime)" -ForegroundColor Gray

# Vite 개발 서버 확인
try {
    $vite = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 3 -UseBasicParsing -ErrorAction SilentlyContinue
    if ($vite.StatusCode -eq 200) {
        Write-Host "  ✓ Vite 개발 서버 실행 중 (HMR 자동 반영)" -ForegroundColor Green
    }
} catch {}

Write-Host ""
Write-Host "진단 완료. 결과를 Claude 에게 공유하세요." -ForegroundColor Cyan
