# ===============================================================
# Phase A-3 쿨다운 해제 및 즉시 재시도
# 파일명: reset_import_retry.ps1
# 용도: failed_modules 쿨다운을 강제로 해제하고 바로 재시도
# 실행: cd D:\project\databridge_full\backend\scripts
#       .\reset_import_retry.ps1
# 안전: API 호출만 — 이관에 영향 0
# ===============================================================

Write-Host "`n🔄 Phase A-3 쿨다운 해제 및 재시도`n" -ForegroundColor Cyan

# ── 1) 현재 상태 확인 ──────────────────────────
Write-Host "[1/3] 현재 import_retry 상태" -ForegroundColor Yellow
try {
    $r1 = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/system/health" -TimeoutSec 5
    if ($r1.import_retry.failed_modules) {
        foreach ($mod in $r1.import_retry.failed_modules.PSObject.Properties) {
            $info = $mod.Value
            Write-Host "  ❌ $($mod.Name): cooldown $([math]::Round($info.cooldown_remaining, 1))초 남음" -ForegroundColor Red
        }
    } else {
        Write-Host "  쿨다운 상태 없음" -ForegroundColor Green
    }
} catch {
    Write-Host "  ❌ API 호출 실패: $_" -ForegroundColor Red
    exit 1
}
Write-Host ""

# ── 2) 60초 대기 (쿨다운 자연 해제) ─────────────
Write-Host "[2/3] 쿨다운 자연 해제 대기 (최대 65초)" -ForegroundColor Yellow
Write-Host "  (Rate limit 이 60초이므로 65초 대기하면 안전)" -ForegroundColor Gray

$maxWait = 65
for ($i = $maxWait; $i -gt 0; $i--) {
    Write-Host -NoNewline "`r  남은 시간: $i 초  "
    Start-Sleep -Seconds 1
}
Write-Host ""
Write-Host ""

# ── 3) 재시도 후 상태 확인 ────────────────────
Write-Host "[3/3] /system/live 호출 → try_import 재시도 트리거" -ForegroundColor Yellow
try {
    $live = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/system/live" -TimeoutSec 5
    Write-Host "  /live API 호출 완료 (재시도 트리거됨)" -ForegroundColor Green
    
    # 2초 대기 (캐시 갱신)
    Start-Sleep -Seconds 3
    
    # 최종 상태 확인
    $r2 = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/system/health" -TimeoutSec 5
    
    Write-Host ""
    Write-Host "  === 재시도 후 상태 ===" -ForegroundColor Cyan
    Write-Host "  psutil: available=$($r2.psutil.available)" -ForegroundColor $(if ($r2.psutil.available) { "Green" } else { "Red" })
    if ($r2.psutil.error) {
        Write-Host "    error: $($r2.psutil.error)" -ForegroundColor Red
    }
    
    Write-Host "  docker: available=$($r2.docker.available)" -ForegroundColor $(if ($r2.docker.available) { "Green" } else { "Red" })
    if ($r2.docker.error) {
        Write-Host "    error: $($r2.docker.error)" -ForegroundColor Red
    }
    
    Write-Host ""
    if ($r2.psutil.available -and $r2.docker.available) {
        Write-Host "  ✅✅✅ 대성공! Phase A-3 완전 동작 — 재시작 없이 해결!" -ForegroundColor Green
        Write-Host "  → 브라우저 새로고침 후 모니터 팝업 확인!" -ForegroundColor Cyan
    } elseif ($r2.psutil.available) {
        Write-Host "  ✅ psutil 해결됨 (docker 는 Docker Desktop 확인 필요)" -ForegroundColor Yellow
    } else {
        Write-Host "  ⚠️ 여전히 실패 — 다른 원인. Claude 에게 공유 필요" -ForegroundColor Yellow
        if ($r2.import_retry.failed_modules) {
            Write-Host "  failed_modules:" -ForegroundColor Yellow
            ($r2.import_retry.failed_modules | ConvertTo-Json) -split "`n" | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
        }
    }
} catch {
    Write-Host "  ❌ 실패: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "완료. 결과를 Claude 에게 공유하세요." -ForegroundColor Cyan
Write-Host ""
