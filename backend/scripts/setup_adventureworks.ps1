# ════════════════════════════════════════════════════════════════════════
# AdventureWorks2022 자동 설치 스크립트 v3 (UTF-8 BOM)
#
# v3 변경 (2026-05-02 본부장님 환경 진단 반영):
#   - $args 자동 변수 충돌 제거 (PowerShell built-in)
#   - splatting 대신 직접 명령 호출 (가장 안전)
#   - MSSQL ready 자동 polling (최대 60초)
#   - Bridge@1234 특수문자 안전 전달
# ════════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Stop"
$BakUrl  = "https://github.com/Microsoft/sql-server-samples/releases/download/adventureworks/AdventureWorks2022.bak"
$BakLocal = "$env:TEMP\AdventureWorks2022.bak"
$BakInContainer = "/var/opt/mssql/backup/AdventureWorks2022.bak"
$SqlPwd = "Bridge@1234"
$MyPwd  = "bridge1234"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  AdventureWorks2022 설치 v3 — DataBridge 표준 검증 데이터셋" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ─── Step 0: 환경 점검 + sqlcmd 탐지 + MSSQL ready 대기 ────────────────
Write-Host "[0/6] 환경 점검..." -ForegroundColor Yellow

# Docker 실행 확인
$null = docker ps 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ Docker 실행 안 됨" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Docker 실행 중" -ForegroundColor Green

# 컨테이너 시작 보장
foreach ($c in @("db_mssql", "db_mysql")) {
    $running = (docker ps --filter "name=$c" --format "{{.Names}}") -eq $c
    if (-not $running) {
        Write-Host "  → $c 컨테이너 시작..." -ForegroundColor Yellow
        docker start $c 2>&1 | Out-Null
        Start-Sleep -Seconds 5
    }
    Write-Host "  ✓ $c 실행 중" -ForegroundColor Green
}

# sqlcmd 경로 자동 탐지
$SQLCMD = "/opt/mssql-tools18/bin/sqlcmd"
$check = docker exec db_mssql sh -c "test -x $SQLCMD && echo OK" 2>$null
if ($check -notmatch "OK") {
    $SQLCMD = "/opt/mssql-tools/bin/sqlcmd"
    $check = docker exec db_mssql sh -c "test -x $SQLCMD && echo OK" 2>$null
    if ($check -notmatch "OK") {
        Write-Host "  ✗ sqlcmd 컨테이너에 없음" -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✓ sqlcmd: $SQLCMD (구버전)" -ForegroundColor Green
} else {
    Write-Host "  ✓ sqlcmd: $SQLCMD (mssql-tools18)" -ForegroundColor Green
}

# ════════════════════════════════════════════════════════════════
# v3 핵심: Invoke-SqlCmd wrapper — $args 자동 변수 회피 + 직접 호출
# 이전 버전 사고: $args 에 splat 했더니 docker 가 빈 인자 받음
# 이번 처방: 변수명 $sqlArgs 로 충돌 회피 + 명시적 인자 전달
# ════════════════════════════════════════════════════════════════
function Invoke-SqlCmd {
    param(
        [Parameter(Mandatory)][string]$Sql,
        [string]$Database = "master"
    )
    # 직접 호출 — splatting 대신 명시적 인자 전달이 가장 안전
    $output = & docker exec db_mssql $SQLCMD `
        -S "localhost" `
        -U "sa" `
        -P $SqlPwd `
        -d $Database `
        -C `
        -Q $Sql 2>&1
    return $output
}

function Invoke-SqlCmdFmt {
    param(
        [Parameter(Mandatory)][string]$Sql,
        [string]$Database = "master"
    )
    $output = & docker exec db_mssql $SQLCMD `
        -S "localhost" `
        -U "sa" `
        -P $SqlPwd `
        -d $Database `
        -C -h -1 -W -s "|" `
        -Q $Sql 2>&1
    return $output
}

# MSSQL ready 자동 polling (최대 60초)
Write-Host "  → MSSQL 응답 대기 (최대 60초)..." -ForegroundColor DarkGray
$ready = $false
for ($i=0; $i -lt 12; $i++) {
    $test = Invoke-SqlCmd "SELECT 1 AS x"
    if ($test -match "^\s*1\s*$" -or $test -match "1 rows affected") {
        $ready = $true
        break
    }
    Start-Sleep -Seconds 5
    Write-Host "    대기중... $((($i+1)*5))초" -ForegroundColor DarkGray
}
if (-not $ready) {
    Write-Host "  ✗ MSSQL 응답 없음 (60초 초과). 컨테이너 로그 확인:" -ForegroundColor Red
    Write-Host "    docker logs db_mssql --tail 30" -ForegroundColor Yellow
    exit 1
}
Write-Host "  ✓ MSSQL 응답 정상" -ForegroundColor Green

# 이미 설치되어 있는지 확인
$existsCheck = Invoke-SqlCmd "SET NOCOUNT ON; SELECT name FROM sys.databases WHERE name = 'AdventureWorks2022'"
if ($existsCheck -match "AdventureWorks2022") {
    Write-Host ""
    Write-Host "  ⚠ AdventureWorks2022 이미 존재" -ForegroundColor Yellow
    $confirm = Read-Host "    덮어쓸까요? (y/n)"
    if ($confirm -ne "y") {
        Write-Host "  → 취소" -ForegroundColor Yellow
        exit 0
    }
    Write-Host "  → DROP 후 재설치" -ForegroundColor Yellow
    Invoke-SqlCmd "ALTER DATABASE AdventureWorks2022 SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE AdventureWorks2022;" | Out-Null
}

docker exec db_mssql mkdir -p /var/opt/mssql/backup 2>$null | Out-Null

# ─── Step 1: BAK 다운로드 ─────────────────────────────────────────────
Write-Host ""
Write-Host "[1/6] AdventureWorks2022.bak 다운로드 (~250MB)..." -ForegroundColor Yellow

if (Test-Path $BakLocal) {
    $size = (Get-Item $BakLocal).Length / 1MB
    Write-Host "  → 기존 파일: $([math]::Round($size,1)) MB" -ForegroundColor Cyan
    if ($size -lt 50) {
        Write-Host "  ✗ 크기 비정상 — 재다운로드" -ForegroundColor Yellow
        Remove-Item $BakLocal -Force
    } else {
        Write-Host "  ✓ 재사용" -ForegroundColor Green
    }
}

if (-not (Test-Path $BakLocal)) {
    Write-Host "  → 다운로드 진행 (1-5분)..." -ForegroundColor DarkGray
    try {
        $oldProgress = $ProgressPreference
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $BakUrl -OutFile $BakLocal -UseBasicParsing
        $ProgressPreference = $oldProgress
        $size = (Get-Item $BakLocal).Length / 1MB
        Write-Host "  ✓ 다운로드 완료: $([math]::Round($size,1)) MB" -ForegroundColor Green
    } catch {
        Write-Host "  ✗ 다운로드 실패: $_" -ForegroundColor Red
        exit 1
    }
}

# ─── Step 2: 컨테이너 복사 ────────────────────────────────────────────
Write-Host ""
Write-Host "[2/6] Docker 컨테이너로 복사..." -ForegroundColor Yellow
docker cp $BakLocal "db_mssql:$BakInContainer" 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ 복사 완료" -ForegroundColor Green
} else {
    Write-Host "  ✗ docker cp 실패" -ForegroundColor Red
    exit 1
}

# ─── Step 3: RESTORE ─────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/6] RESTORE DATABASE..." -ForegroundColor Yellow

# 논리 파일명 자동 탐지
Write-Host "  → 백업 파일 구조 확인..." -ForegroundColor DarkGray
$fileListRaw = Invoke-SqlCmdFmt "RESTORE FILELISTONLY FROM DISK='$BakInContainer'"
$dataLogical = ""
$logLogical = ""
foreach ($line in $fileListRaw) {
    $cols = $line -split "\|"
    if ($cols.Length -ge 3) {
        $name = $cols[0].Trim()
        $path = $cols[1].Trim()
        if ($path -match "\.mdf$" -and -not $dataLogical) { $dataLogical = $name }
        if ($path -match "\.ldf$" -and -not $logLogical) { $logLogical = $name }
    }
}

if (-not $dataLogical -or -not $logLogical) {
    Write-Host "  ⚠ 자동 탐지 실패. 표준 이름 시도" -ForegroundColor Yellow
    $dataLogical = "AdventureWorks2022"
    $logLogical = "AdventureWorks2022_log"
} else {
    Write-Host "  ✓ 논리명: data='$dataLogical', log='$logLogical'" -ForegroundColor Green
}

$restoreSql = "RESTORE DATABASE AdventureWorks2022 FROM DISK = '$BakInContainer' WITH MOVE '$dataLogical' TO '/var/opt/mssql/data/AdventureWorks2022.mdf', MOVE '$logLogical' TO '/var/opt/mssql/data/AdventureWorks2022_log.ldf', REPLACE, STATS = 10;"

Write-Host "  → 복원 진행중 (1-3분)..." -ForegroundColor DarkGray
$restoreResult = Invoke-SqlCmd $restoreSql
if ($restoreResult -match "RESTORE DATABASE successfully processed") {
    Write-Host "  ✓ RESTORE 성공" -ForegroundColor Green
} else {
    Write-Host "  ✗ RESTORE 실패:" -ForegroundColor Red
    $restoreResult | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
    exit 1
}

# ─── Step 4: 검증 ────────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/6] 데이터 검증..." -ForegroundColor Yellow

$verifySql = "SELECT 'tables' AS metric, CAST(COUNT(*) AS VARCHAR) AS cnt FROM sys.tables UNION ALL SELECT 'views', CAST(COUNT(*) AS VARCHAR) FROM sys.views UNION ALL SELECT 'sps', CAST(COUNT(*) AS VARCHAR) FROM sys.procedures UNION ALL SELECT 'fns', CAST(COUNT(*) AS VARCHAR) FROM sys.objects WHERE type IN ('FN','IF','TF') UNION ALL SELECT 'trigs', CAST(COUNT(*) AS VARCHAR) FROM sys.triggers UNION ALL SELECT 'fks', CAST(COUNT(*) AS VARCHAR) FROM sys.foreign_keys"
$verify = Invoke-SqlCmdFmt $verifySql "AdventureWorks2022"
$verify | Where-Object { $_ -match "\|" } | ForEach-Object {
    $parts = $_ -split "\|"
    if ($parts.Length -ge 2) {
        $metric = $parts[0].Trim()
        $cnt = $parts[1].Trim()
        if ($metric -and $cnt -match "^\d+$") {
            Write-Host "  ✓ ${metric}: $cnt" -ForegroundColor Green
        }
    }
}

# ─── Step 5: MySQL aw_target ─────────────────────────────────────────
Write-Host ""
Write-Host "[5/6] MySQL aw_target 생성..." -ForegroundColor Yellow

$mysqlExists = docker exec db_mysql mysql -u root "-p$MyPwd" -e "SHOW DATABASES LIKE 'aw_target'" 2>&1
if ($mysqlExists -match "aw_target") {
    $confirm = Read-Host "  ⚠ aw_target 이미 존재. DROP 후 재생성? (y/n)"
    if ($confirm -eq "y") {
        docker exec db_mysql mysql -u root "-p$MyPwd" -e "DROP DATABASE aw_target" 2>&1 | Out-Null
        docker exec db_mysql mysql -u root "-p$MyPwd" -e "CREATE DATABASE aw_target CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci" 2>&1 | Out-Null
        Write-Host "  ✓ 재생성" -ForegroundColor Green
    } else {
        Write-Host "  → 기존 사용" -ForegroundColor Cyan
    }
} else {
    docker exec db_mysql mysql -u root "-p$MyPwd" -e "CREATE DATABASE aw_target CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci" 2>&1 | Out-Null
    Write-Host "  ✓ 생성 완료 (utf8mb4)" -ForegroundColor Green
}

# ─── Step 6: 안내 ────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✅ AdventureWorks2022 설치 완료" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "DataBridge 연결 정보:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  📥 소스 (MSSQL):" -ForegroundColor White
Write-Host "     localhost:1433 / sa / Bridge@1234 / AdventureWorks2022" -ForegroundColor White
Write-Host ""
Write-Host "  📤 타겟 (MySQL):" -ForegroundColor White
Write-Host "     localhost:3306 / root / bridge1234 / aw_target" -ForegroundColor White
Write-Host ""
Write-Host "다음 단계: UI → /jobs/wizard → 새 Job 생성" -ForegroundColor Yellow
Write-Host ""
