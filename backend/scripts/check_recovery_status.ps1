# ===============================================================
# DataBridge 이관 중단 후 복구 상태 진단 스크립트
# 파일명: check_recovery_status.ps1
# 용도: 백엔드 강제 종료 후 타겟 DB / Job Store 상태 확인
# 실행: PowerShell (관리자 권한 불필요)
#   cd D:\project\databridge_full\backend\scripts
#   .\check_recovery_status.ps1
# ===============================================================

Write-Host "`n🔍 DataBridge 복구 상태 진단" -ForegroundColor Cyan
Write-Host "   백엔드 강제 종료 후 이관 상태 점검`n" -ForegroundColor Gray

# ── 1) 컨테이너 상태 ─────────────────────────────────
Write-Host "[1/4] 컨테이너 상태" -ForegroundColor Yellow
docker ps --format "table {{.Names}}`t{{.Status}}"
Write-Host ""

# ── 2) 백엔드 살아있는지 ────────────────────────────
Write-Host "[2/4] 백엔드 API 상태" -ForegroundColor Yellow
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 3 -ErrorAction Stop
    Write-Host "  ✅ 백엔드 정상 ($($r.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "  ❌ 백엔드 응답 없음" -ForegroundColor Red
    Write-Host "  → uvicorn 이 제대로 시작됐는지 확인 필요"
}
Write-Host ""

# ── 3) 타겟 MySQL — 완료된 테이블 몇 개 인지 ─────────
Write-Host "[3/4] 타겟 MySQL 의 capital_target 스키마 현황" -ForegroundColor Yellow
Write-Host "  (MySQL root 비밀번호 필요)" -ForegroundColor Gray
$PWD_SEC = Read-Host "MySQL root 비밀번호" -AsSecureString
$PWD_PLAIN = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($PWD_SEC))

Write-Host ""
Write-Host "  타겟 스키마 이름 확인 중..." -ForegroundColor Gray
# 가능한 스키마 이름들 시도
$schemas = @("capital_target", "capital_midsize_target", "target")
foreach ($sc in $schemas) {
    $q = "SELECT COUNT(*) AS table_count FROM information_schema.TABLES WHERE TABLE_SCHEMA = '$sc';"
    $result = docker exec db_mysql mysql -uroot -p"$PWD_PLAIN" -N -e $q 2>$null
    if ($result -and $result -ne "0") {
        Write-Host "  ✅ 스키마 '$sc' 발견 → 테이블 $result 개" -ForegroundColor Green
        
        # 각 테이블 건수 Top 5
        Write-Host "    테이블별 건수 (TOP 10):" -ForegroundColor Gray
        $q2 = "SELECT TABLE_NAME, TABLE_ROWS FROM information_schema.TABLES WHERE TABLE_SCHEMA = '$sc' ORDER BY TABLE_ROWS DESC LIMIT 10;"
        docker exec db_mysql mysql -uroot -p"$PWD_PLAIN" -e $q2 2>$null
    }
}

# 변수 소거
$PWD_PLAIN = $null
Remove-Variable PWD_PLAIN -ErrorAction SilentlyContinue
Write-Host ""

# ── 4) Job Store SQLite 직접 확인 ────────────────────
Write-Host "[4/4] DataBridge Job Store 상태" -ForegroundColor Yellow
$db_path = "D:\project\databridge_fullackend\data\databridge.db"
if (Test-Path $db_path) {
    Write-Host "  DB 파일 존재: $db_path" -ForegroundColor Gray
    
    # sqlite3 CLI 있나 확인
    $sqlite = Get-Command sqlite3 -ErrorAction SilentlyContinue
    if ($sqlite) {
        Write-Host "  최근 Job 상태 (SQLite 직접 조회):" -ForegroundColor Gray
        sqlite3 $db_path "SELECT key, json_extract(value,'$.status') AS status, json_extract(value,'$.name') AS name, json_extract(value,'$.progress') AS progress FROM store_jobs ORDER BY updated_at DESC LIMIT 5;"
    } else {
        Write-Host "  sqlite3 CLI 없음 — 백엔드 API로 확인 필요" -ForegroundColor Gray
        Write-Host "  다음 명령 사용:" -ForegroundColor Gray
        Write-Host '    Invoke-WebRequest "http://localhost:8000/api/v1/jobs" | Select-Object -ExpandProperty Content' -ForegroundColor DarkGray
    }
} else {
    Write-Host "  ⚠️ DB 파일 없음: $db_path" -ForegroundColor Red
}

Write-Host "`n✅ 진단 완료" -ForegroundColor Green
Write-Host "결과를 Claude 에게 공유하여 복구 방법 상담.`n" -ForegroundColor Yellow
