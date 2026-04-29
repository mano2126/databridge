# ===============================================================
# DataBridge 이관 후 Level 2 정리 스크립트 (철저한 정리)
# 파일명: cleanup_level2.ps1
# 용도: 이관 중 에러가 많았거나 완전히 새로 시작하고 싶을 때
# 실행: PowerShell 관리자 권한
#       cd D:\project\scripts
#       Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#       .\cleanup_level2.ps1
# 소요: 5~10분
# ===============================================================

Write-Host "`n🔥 Level 2 — 철저한 정리 (시간 5~10분 소요)" -ForegroundColor Magenta
$confirm = Read-Host "`n이관 끝났고 Level 2 정리를 시작합니다. 계속하려면 y"
if ($confirm -ne "y") {
    Write-Host "취소됨." -ForegroundColor Red
    exit
}

# ── 1) DataBridge 백엔드 재시작 ─────────────────────────────────
Write-Host "`n[1/8] DataBridge 백엔드 재시작 (진행 중 워커 정리)..." -ForegroundColor Yellow
docker compose restart backend 2>&1
Write-Host "  ✓ 백엔드 재시작 요청됨"

# ── 2) Docker 시스템 prune (선택) ──────────────────────────────
Write-Host "`n[2/8] Docker 시스템 사용량 확인..." -ForegroundColor Yellow
docker system df

Write-Host "`n  ↑ 중지된 컨테이너/미사용 이미지를 정리하시겠습니까?"
$ans = Read-Host "  (y/N)"
if ($ans -eq "y") {
    Write-Host "  컨테이너 prune..." -ForegroundColor Gray
    docker container prune -f
    Write-Host "  이미지 prune..." -ForegroundColor Gray
    docker image prune -f
    Write-Host "  네트워크 prune..." -ForegroundColor Gray
    docker network prune -f
    Write-Host "  ⚠️ docker volume prune 은 수동 실행 권장 (DB 데이터 보호)" -ForegroundColor Yellow
} else {
    Write-Host "  prune 건너뜀" -ForegroundColor Gray
}

# ── 3) DB 컨테이너 완전 종료 ────────────────────────────────────
Write-Host "`n[3/8] DB 컨테이너 완전 종료..." -ForegroundColor Yellow
docker stop db_mssql db_mysql 2>$null
Write-Host "  ✓ 컨테이너 정지 완료"

# ── 4) Windows 메모리 GC ────────────────────────────────────────
Write-Host "`n[4/8] Windows 메모리 정리 (소프트 GC)..." -ForegroundColor Yellow
[System.GC]::Collect()
[System.GC]::WaitForPendingFinalizers()
[System.GC]::Collect()
Write-Host "  ✓ PowerShell 프로세스 GC 실행"
Write-Host "  참고: 대기 메모리(Standby List) 완전 정리는 재부팅이 가장 확실"

# ── 5) WSL2 메모리 반환 (★ 핵심 ★) ─────────────────────────────
Write-Host "`n[5/8] WSL2 메모리 반환 (Docker Desktop 메모리 회수)..." -ForegroundColor Yellow
Write-Host "  WSL2 는 한 번 잡은 메모리를 호스트에 잘 반환 안 함 → shutdown 으로 강제 회수" -ForegroundColor Gray
wsl --shutdown
Write-Host "  10초 대기 (Docker Desktop 자동 재기동)..."
Start-Sleep -Seconds 10

# ── 6) Docker Desktop 재기동 확인 ──────────────────────────────
Write-Host "`n[6/8] Docker Desktop 재기동 확인..." -ForegroundColor Yellow
$maxWait = 60
$waited = 0
$dockerOK = $false
while ($waited -lt $maxWait) {
    try {
        docker ps 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $dockerOK = $true
            Write-Host "  ✅ Docker 정상 기동 ($waited 초)" -ForegroundColor Green
            break
        }
    } catch {}
    Start-Sleep -Seconds 3
    $waited += 3
    Write-Host "  Docker 대기 중... ($waited/$maxWait 초)"
}

if (-not $dockerOK) {
    Write-Host "`n  ⚠️ Docker Desktop 이 자동으로 뜨지 않음" -ForegroundColor Red
    Write-Host "  시작 메뉴에서 'Docker Desktop' 을 수동으로 실행해주세요." -ForegroundColor Yellow
    Read-Host "  Docker 수동 기동 후 Enter"
}

# ── 7) DB 컨테이너 재시작 ──────────────────────────────────────
Write-Host "`n[7/8] DB 컨테이너 재시작..." -ForegroundColor Yellow
docker start db_mssql db_mysql
Write-Host "  3분 대기 (healthy 상태 기다림)..."
Start-Sleep -Seconds 180

# ── 8) 최종 상태 ───────────────────────────────────────────────
Write-Host "`n[8/8] 최종 상태 확인" -ForegroundColor Yellow

Write-Host "`n[컨테이너 상태]" -ForegroundColor Cyan
docker ps --format "table {{.Names}}`t{{.Status}}"

Write-Host "`n[컨테이너 메모리/CPU]" -ForegroundColor Cyan
docker stats --no-stream

Write-Host "`n[호스트 메모리]" -ForegroundColor Cyan
Get-CimInstance Win32_OperatingSystem | Select-Object `
    @{N='Total(GB)';E={[math]::Round($_.TotalVisibleMemorySize/1MB,1)}}, `
    @{N='Free(GB)';E={[math]::Round($_.FreePhysicalMemory/1MB,1)}}, `
    @{N='Used(%)';E={[math]::Round(($_.TotalVisibleMemorySize-$_.FreePhysicalMemory)/$_.TotalVisibleMemorySize*100,1)}} `
  | Format-Table -AutoSize

Write-Host "`n✅ Level 2 완료!" -ForegroundColor Green
Write-Host "깨끗한 상태로 초기화되었습니다. 다음 작업을 시작하셔도 됩니다." -ForegroundColor Green
