# ===============================================================
# DataBridge 이관 후 Level 1 정리 스크립트 (가벼운 정리)
# 파일명: cleanup_level1.ps1
# 용도: 다음 이관 전 메모리/임시 공간만 깔끔히 비우기
# 실행: PowerShell 관리자 권한
#       cd D:\project\scripts
#       Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#       .\cleanup_level1.ps1
# ===============================================================

Write-Host "`n🧹 Level 1 — 컨테이너 재시작 + 캐시 정리 (시간 3~5분)" -ForegroundColor Cyan

# ── 1) 이관 Job 상태 확인 (안전장치) ─────────────────────────
Write-Host "`n[1/5] 이관 Job 상태 확인..." -ForegroundColor Yellow
docker ps --format "table {{.Names}}`t{{.Status}}"
$confirm = Read-Host "`n위 상태를 확인했고 이관이 모두 완료됐습니다. 계속하려면 y"
if ($confirm -ne "y") {
    Write-Host "취소됨." -ForegroundColor Red
    exit
}

# ── 2) MSSQL tempdb 축소 + 캐시 클리어 ───────────────────────
Write-Host "`n[2/5] MSSQL tempdb 축소 및 캐시 클리어..." -ForegroundColor Yellow
$SA_PWD_SEC = Read-Host "MSSQL sa 비밀번호 입력" -AsSecureString
$SA_PWD = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($SA_PWD_SEC))

docker exec db_mssql /opt/mssql-tools18/bin/sqlcmd `
  -S localhost -U sa -P "$SA_PWD" -C -Q `
  "USE tempdb; DBCC SHRINKFILE (tempdev, 500); DBCC SHRINKFILE (templog, 100); DBCC FREEPROCCACHE; DBCC DROPCLEANBUFFERS;" 2>&1

# 보안: 비밀번호 변수 즉시 소거
$SA_PWD = $null
Remove-Variable SA_PWD -ErrorAction SilentlyContinue

# ── 3) MySQL 상태 확인 ──────────────────────────────────────
Write-Host "`n[3/5] MySQL InnoDB 상태 확인..." -ForegroundColor Yellow
docker exec db_mysql mysql --version 2>&1

# ── 4) 컨테이너 재시작 (메모리 완전 리셋) ────────────────────
Write-Host "`n[4/5] 컨테이너 재시작 (깨끗한 상태로)..." -ForegroundColor Yellow
docker restart db_mssql db_mysql
Write-Host "  3분 대기 중 (healthy 대기)..."
Start-Sleep -Seconds 180

# ── 5) 최종 상태 확인 ───────────────────────────────────────
Write-Host "`n[5/5] 최종 상태 확인" -ForegroundColor Yellow

Write-Host "`n[컨테이너 상태]" -ForegroundColor Cyan
docker ps --format "table {{.Names}}`t{{.Status}}`t{{.Image}}"

Write-Host "`n[컨테이너 메모리/CPU]" -ForegroundColor Cyan
docker stats --no-stream

Write-Host "`n✅ Level 1 완료!" -ForegroundColor Green
Write-Host "다음 이관을 시작하셔도 됩니다." -ForegroundColor Green
