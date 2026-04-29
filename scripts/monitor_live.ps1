# ===============================================================
# DataBridge 이관 실시간 모니터 (Ctrl+C 로 종료)
# 파일명: monitor_live.ps1
# 용도: 이관 진행 중 다른 창에서 실시간 상태 확인
# 실행: .\monitor_live.ps1
# ===============================================================

Write-Host "`n📊 DataBridge 실시간 모니터 시작 (Ctrl+C 로 종료)" -ForegroundColor Cyan
Start-Sleep -Seconds 2

while ($true) {
    Clear-Host
    Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  DataBridge 이관 모니터 — $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Cyan
    Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan

    # 컨테이너 상태
    Write-Host "`n[컨테이너]" -ForegroundColor Yellow
    docker ps --format "table {{.Names}}`t{{.Status}}" 2>$null

    # 메모리/CPU
    Write-Host "`n[메모리/CPU]" -ForegroundColor Yellow
    docker stats --no-stream --format "table {{.Name}}`t{{.CPUPerc}}`t{{.MemUsage}}`t{{.MemPerc}}" 2>$null

    # 호스트 메모리
    $mem = Get-CimInstance Win32_OperatingSystem
    $freeMem  = [math]::Round($mem.FreePhysicalMemory/1MB, 1)
    $totalMem = [math]::Round($mem.TotalVisibleMemorySize/1MB, 1)
    $usedPct  = [math]::Round(($mem.TotalVisibleMemorySize - $mem.FreePhysicalMemory) / $mem.TotalVisibleMemorySize * 100, 1)

    Write-Host "`n[호스트 메모리]" -ForegroundColor Yellow
    Write-Host "  사용: $usedPct% | 여유: $freeMem GB / 총 $totalMem GB"

    # 경고 레벨
    if ($usedPct -gt 90) {
        Write-Host "  🔴 심각! 메모리 사용률 90% 초과 — 이관 OOM 위험" -ForegroundColor Red
    } elseif ($usedPct -gt 80) {
        Write-Host "  🟡 주의! 메모리 사용률 80% 초과" -ForegroundColor Yellow
    } else {
        Write-Host "  🟢 정상" -ForegroundColor Green
    }

    Write-Host "`n───────────────────────────────────────────────────" -ForegroundColor DarkGray
    Write-Host "(Ctrl+C 로 종료, 2초 간격 갱신)" -ForegroundColor DarkGray
    Start-Sleep -Seconds 2
}
