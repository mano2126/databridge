# AI DBA 관련 프론트 전체 조사
Write-Host "`n🔍 AI DBA 관련 프론트 전체 흐름 조사`n" -ForegroundColor Cyan

# 1) advisor 관련 전체 endpoint 호출 찾기
Write-Host "[1/3] advisor 관련 API 호출 전체 검색" -ForegroundColor Yellow
$files = Get-ChildItem -Path "D:\project\databridge_full\frontend\src" -Recurse -Include "*.vue","*.js" -ErrorAction SilentlyContinue
$endpoints = @{}
foreach ($f in $files) {
    $content = Get-Content $f.FullName -Raw -ErrorAction SilentlyContinue
    if ($content) {
        $matches = [regex]::Matches($content, "/advisor/[a-z\-_]+|advisor/[a-z\-_]+")
        foreach ($m in $matches) {
            $ep = $m.Value
            if (-not $endpoints.ContainsKey($ep)) {
                $endpoints[$ep] = @()
            }
            $endpoints[$ep] += $f.Name
        }
    }
}
foreach ($ep in $endpoints.Keys) {
    Write-Host "  $ep" -ForegroundColor Green
    foreach ($fname in ($endpoints[$ep] | Select-Object -Unique)) {
        Write-Host "    ← $fname" -ForegroundColor Gray
    }
}

# 2) 백엔드 advisor 라우트 전체 목록
Write-Host ""
Write-Host "[2/3] 백엔드 advisor 엔드포인트 전체" -ForegroundColor Yellow
try {
    $openapi = Invoke-RestMethod -Uri "http://localhost:8000/openapi.json" -TimeoutSec 10
    $advisorPaths = $openapi.paths.PSObject.Properties.Name | Where-Object { $_ -like "*advisor*" }
    foreach ($p in $advisorPaths) {
        $methods = $openapi.paths.$p.PSObject.Properties.Name
        Write-Host "  $p  [$($methods -join ", ")]" -ForegroundColor Gray
    }
} catch {
    Write-Host "  ✗ 실패: $_" -ForegroundColor Red
}

# 3) AI DBA Consultant 관련 Vue 컴포넌트 찾기
Write-Host ""
Write-Host "[3/3] AI DBA / Advisor / Consultant 관련 컴포넌트" -ForegroundColor Yellow
foreach ($f in $files) {
    $content = Get-Content $f.FullName -Raw -ErrorAction SilentlyContinue
    if ($content -and ($content -match "AI DBA|Consultant|analyze.*advisor|advisor.*analyze|dbaAdvisor|DBAAdvisor")) {
        Write-Host "  $($f.FullName)" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "진단 완료." -ForegroundColor Cyan
