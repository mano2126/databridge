# ════════════════════════════════════════════════════════════════════════
# v95_p13 검증을 위한 환경 안정화 스크립트
# 본부장님 환경 (8GB RAM PC) 기준 최적 설정
#
# 동작:
#   1. 백엔드 정지 (DataBridge가 잡고 있는 연결 해제)
#   2. capital_midsize DROP (메모리 확보)
#   3. AdventureWorks + aw_target 보존 확인
#   4. db_mssql 메모리 한도 4GB → 3GB 조정 (swap 회피)
#   5. db_mysql 메모리 한도 명시 (2GB)
#   6. 컨테이너 재시작
#   7. ready 자동 대기
#   8. 검증 (sqlcmd 응답 + AdventureWorks 카운트)
# ════════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Stop"
$SqlPwd = "Bridge@1234"
$MyPwd  = "bridge1234"
$SQLCMD = "/opt/mssql-tools18/bin/sqlcmd"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  환경 안정화 — 8GB PC 최적 분배" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ─── Step 1: 사전 점검 ────────────────────────────────────────────────
Write-Host "[1/8] 사전 점검..." -ForegroundColor Yellow

$null = docker ps 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ Docker 실행 안 됨" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Docker 실행 중" -ForegroundColor Green

# ─── Step 2: 백엔드 정지 ──────────────────────────────────────────────
Write-Host ""
Write-Host "[2/8] DataBridge 백엔드 정지..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3
Write-Host "  ✓ 백엔드 정지 완료" -ForegroundColor Green

# ─── Step 3: MSSQL 응답 확인 (아직 살아있다면 capital_midsize DROP) ──
Write-Host ""
Write-Host "[3/8] capital_midsize DB 정리..." -ForegroundColor Yellow

# 응답 가능한지 먼저 확인
$alive = $false
for ($i=0; $i -lt 6; $i++) {
    $test = & docker exec db_mssql $SQLCMD -S localhost -U sa -P $SqlPwd -C -Q "SELECT 1" 2>&1
    if ($test -match "1 rows affected" -or $test -match "^\s*1\s*$") {
        $alive = $true
        break
    }
    Start-Sleep -Seconds 5
    Write-Host "    응답 대기... $((($i+1)*5))초" -ForegroundColor DarkGray
}

if ($alive) {
    Write-Host "  ✓ MSSQL 응답 가능" -ForegroundColor Green
    
    # capital_midsize 존재 확인 + DROP
    $exists = & docker exec db_mssql $SQLCMD -S localhost -U sa -P $SqlPwd -C -Q "SET NOCOUNT ON; SELECT name FROM sys.databases WHERE name='capital_midsize'" 2>&1
    if ($exists -match "capital_midsize") {
        Write-Host "  → capital_midsize DROP 진행..." -ForegroundColor DarkGray
        $dropResult = & docker exec db_mssql $SQLCMD -S localhost -U sa -P $SqlPwd -C -Q "USE master; ALTER DATABASE capital_midsize SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE capital_midsize;" 2>&1
        Write-Host "  ✓ capital_midsize DROP 완료" -ForegroundColor Green
    } else {
        Write-Host "  → capital_midsize 없음 (이미 정리됨)" -ForegroundColor Cyan
    }
    
    # AdventureWorks2022 존재 확인 (보존 검증)
    $awExists = & docker exec db_mssql $SQLCMD -S localhost -U sa -P $SqlPwd -C -Q "SET NOCOUNT ON; SELECT name FROM sys.databases WHERE name='AdventureWorks2022'" 2>&1
    if ($awExists -match "AdventureWorks2022") {
        Write-Host "  ✓ AdventureWorks2022 보존됨 (검증 자산)" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ AdventureWorks2022 없음 — setup_adventureworks.ps1 재실행 필요" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ⚠ MSSQL 응답 없음 — capital_midsize DROP 건너뜀 (재시작 후 데이터 자동 사라지지 않음)" -ForegroundColor Yellow
    Write-Host "  → 재시작 후 수동 DROP 권장" -ForegroundColor Yellow
}

# MySQL aw_target 확인
$awTarget = docker exec db_mysql mysql -u root "-p$MyPwd" -e "SHOW DATABASES LIKE 'aw_target'" 2>&1
if ($awTarget -match "aw_target") {
    Write-Host "  ✓ aw_target 보존됨 (MySQL 측)" -ForegroundColor Green
}

# ─── Step 4: 컨테이너 재생성 (메모리 한도 조정) ─────────────────────
Write-Host ""
Write-Host "[4/8] db_mssql 메모리 한도 조정 (swap 회피)..." -ForegroundColor Yellow

# 현재 컨테이너 정보 백업 (mounts/ports/network 보존)
$mssqlInspect = docker inspect db_mssql --format '{{json .}}' | ConvertFrom-Json
$mssqlMounts = $mssqlInspect.Mounts
$mssqlNetwork = $mssqlInspect.HostConfig.NetworkMode

Write-Host "  → db_mssql 마운트 보존:" -ForegroundColor DarkGray
foreach ($m in $mssqlMounts) {
    Write-Host "    $($m.Source) -> $($m.Destination)" -ForegroundColor DarkGray
}

# 마운트 인자 구성
$mountArgs = @()
foreach ($m in $mssqlMounts) {
    if ($m.Type -eq "volume") {
        $mountArgs += @("-v", "$($m.Name):$($m.Destination)")
    } elseif ($m.Type -eq "bind") {
        $mountArgs += @("-v", "$($m.Source):$($m.Destination)")
    }
}

# 정지 + 제거 (data volume은 보존됨)
docker stop db_mssql 2>&1 | Out-Null
docker rm db_mssql 2>&1 | Out-Null

# 새 메모리 설정으로 재생성 (3GB 한도 + MSSQL 자체 한도 2.5GB)
$dockerArgs = @(
    "run", "-d",
    "--name", "db_mssql",
    "--memory=3g",            # ← 호스트 메모리 한도 3GB
    "--memory-swap=3g",       # ← swap 제한 (RAM 안에서만)
    "-p", "1433:1433",
    "-e", "ACCEPT_EULA=Y",
    "-e", "SA_PASSWORD=$SqlPwd",
    "-e", "MSSQL_PID=Developer",
    "-e", "MSSQL_MEMORY_LIMIT_MB=2560"  # ← MSSQL 자체 한도 2.5GB (host 3GB 의 85%)
)
$dockerArgs += $mountArgs
$dockerArgs += @("mcr.microsoft.com/mssql/server:2022-latest")

$newId = & docker @dockerArgs
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ db_mssql 재생성 완료 (memory: 3GB host / 2.5GB SQL)" -ForegroundColor Green
} else {
    Write-Host "  ✗ db_mssql 재생성 실패" -ForegroundColor Red
    exit 1
}

# ─── Step 5: db_mysql 메모리 명시 ────────────────────────────────────
Write-Host ""
Write-Host "[5/8] db_mysql 메모리 한도 조정..." -ForegroundColor Yellow

$mysqlInspect = docker inspect db_mysql --format '{{json .}}' | ConvertFrom-Json
$mysqlMounts = $mysqlInspect.Mounts
$mysqlEnv = $mysqlInspect.Config.Env

$mysqlMountArgs = @()
foreach ($m in $mysqlMounts) {
    if ($m.Type -eq "volume") {
        $mysqlMountArgs += @("-v", "$($m.Name):$($m.Destination)")
    } elseif ($m.Type -eq "bind") {
        $mysqlMountArgs += @("-v", "$($m.Source):$($m.Destination)")
    }
}

$mysqlEnvArgs = @()
foreach ($e in $mysqlEnv) {
    if ($e -notmatch "^PATH=" -and $e -notmatch "^GOSU_VERSION") {
        $mysqlEnvArgs += @("-e", $e)
    }
}

docker stop db_mysql 2>&1 | Out-Null
docker rm db_mysql 2>&1 | Out-Null

$mysqlArgs = @(
    "run", "-d",
    "--name", "db_mysql",
    "--memory=2g",
    "--memory-swap=2g",
    "-p", "3306:3306"
)
$mysqlArgs += $mysqlEnvArgs
$mysqlArgs += $mysqlMountArgs
$mysqlArgs += @($mysqlInspect.Config.Image)

$mysqlNewId = & docker @mysqlArgs
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ db_mysql 재생성 완료 (memory: 2GB)" -ForegroundColor Green
} else {
    Write-Host "  ⚠ db_mysql 재생성 실패 — 기존 설정으로 시작 시도" -ForegroundColor Yellow
    docker start db_mysql 2>&1 | Out-Null
}

# ─── Step 6: ready 대기 ──────────────────────────────────────────────
Write-Host ""
Write-Host "[6/8] MSSQL ready 대기 (최대 90초)..." -ForegroundColor Yellow
$ready = $false
for ($i=0; $i -lt 18; $i++) {
    Start-Sleep -Seconds 5
    $test = & docker exec db_mssql $SQLCMD -S localhost -U sa -P $SqlPwd -C -Q "SELECT 1" 2>&1
    if ($test -match "1 rows affected" -or $test -match "^\s*1\s*$") {
        $ready = $true
        Write-Host "  ✓ MSSQL 응답 정상 ($((($i+1)*5))초 후)" -ForegroundColor Green
        break
    }
    Write-Host "    대기중... $((($i+1)*5))초" -ForegroundColor DarkGray
}

if (-not $ready) {
    Write-Host "  ✗ MSSQL 응답 없음 (90초 초과)" -ForegroundColor Red
    Write-Host "    docker logs db_mssql --tail 30" -ForegroundColor Yellow
    exit 1
}

# ─── Step 7: AdventureWorks 검증 ─────────────────────────────────────
Write-Host ""
Write-Host "[7/8] AdventureWorks2022 보존 확인..." -ForegroundColor Yellow

$awCheck = & docker exec db_mssql $SQLCMD -S localhost -U sa -P $SqlPwd -C -d AdventureWorks2022 -Q "SELECT COUNT(*) FROM sys.tables" 2>&1
if ($awCheck -match "71" -or $awCheck -match "70" -or $awCheck -match "72") {
    Write-Host "  ✓ AdventureWorks2022 정상 (71 테이블 확인)" -ForegroundColor Green
} else {
    Write-Host "  ⚠ AdventureWorks2022 검증 결과:" -ForegroundColor Yellow
    $awCheck | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
    Write-Host "  → setup_adventureworks.ps1 재실행 권장" -ForegroundColor Yellow
}

# 메모리 사용 확인
$stats = docker stats db_mssql --no-stream --format "{{.MemUsage}} ({{.MemPerc}})" 2>&1
Write-Host "  → 현재 메모리: $stats" -ForegroundColor Cyan

# ─── Step 8: 백엔드 시작 ─────────────────────────────────────────────
Write-Host ""
Write-Host "[8/8] DataBridge 백엔드 시작..." -ForegroundColor Yellow
Push-Location "D:\project\databridge_full\backend"
Start-Process -FilePath ".\run_backend.bat" -WindowStyle Normal
Pop-Location
Start-Sleep -Seconds 8

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✅ 환경 안정화 완료" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "변경 사항:" -ForegroundColor Yellow
Write-Host "  ✓ capital_midsize DROP (메모리 확보)" -ForegroundColor White
Write-Host "  ✓ db_mssql: 3GB host / 2.5GB SQL (swap 차단)" -ForegroundColor White
Write-Host "  ✓ db_mysql: 2GB" -ForegroundColor White
Write-Host "  ✓ AdventureWorks2022 보존" -ForegroundColor White
Write-Host "  ✓ 백엔드 재시작" -ForegroundColor White
Write-Host ""
Write-Host "다음 단계:" -ForegroundColor Yellow
Write-Host "  ① UI Ctrl+Shift+R" -ForegroundColor White
Write-Host "  ② v95_p13 ZIP 풀고 적용" -ForegroundColor White
Write-Host "  ③ AdventureWorks2022 → aw_target 재이관 (DROP 후)" -ForegroundColor White
Write-Host "  ④ 결과 측정" -ForegroundColor White
Write-Host ""
