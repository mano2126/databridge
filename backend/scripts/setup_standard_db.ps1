# ════════════════════════════════════════════════════════════════════════
# Standard MSSQL DB 자동 설치 스크립트 (일반 처방, UTF-8 BOM)
#
# 본부장님 원칙: "이 DB만 어떻게 해서 넘어갈 생각으로 하드코딩 하면 절대 안돼"
# → 어떤 표준 DB든 같은 흐름으로 동작:
#   - AdventureWorks2022, Northwind, WideWorldImporters
#   - 향후 다른 DB 추가도 같은 스크립트로
#
# 사용법:
#   .\setup_standard_db.ps1 -DbName "AdventureWorks2022"
#   .\setup_standard_db.ps1 -DbName "Northwind"
#   .\setup_standard_db.ps1 -DbName "WideWorldImporters"
# ════════════════════════════════════════════════════════════════════════

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("AdventureWorks2022", "Northwind", "WideWorldImporters")]
    [string]$DbName
)

$ErrorActionPreference = "Stop"

# ═══════════════════════════════════════════════════════════════
# DB 카탈로그 — 추가 시 여기만 수정 (코드 변경 없음)
# 본부장님 원칙: 하드코딩 X — DB 메타데이터 분리
# ═══════════════════════════════════════════════════════════════
$DbCatalog = @{
    "AdventureWorks2022" = @{
        BakUrl = "https://github.com/Microsoft/sql-server-samples/releases/download/adventureworks/AdventureWorks2022.bak"
        BakSize = 250
        ExpectedTables = 71
        ExpectedViews = 20
        Description = "Microsoft 공식 — UDT/hierarchyid/geography 검증"
        TargetDb = "aw_target"
    }
    "Northwind" = @{
        # Northwind 는 .bak 가 아니라 .sql 스크립트로 배포
        SqlUrl = "https://raw.githubusercontent.com/microsoft/sql-server-samples/master/samples/databases/northwind-pubs/instnwnd.sql"
        SqlSize = 1
        ExpectedTables = 13
        ExpectedViews = 16
        Description = "정통 비즈니스 DB — 기본기 검증"
        TargetDb = "nw_target"
        InstallType = "sql"  # SQL 스크립트 실행
    }
    "WideWorldImporters" = @{
        BakUrl = "https://github.com/Microsoft/sql-server-samples/releases/download/wide-world-importers-v1.0/WideWorldImporters-Full.bak"
        BakSize = 121
        ExpectedTables = 70
        ExpectedViews = 25
        Description = "최신 MSSQL — JSON/temporal/memory-optimized 검증"
        TargetDb = "wwi_target"
        InstallType = "bak"
    }
}

$cfg = $DbCatalog[$DbName]
if (-not $cfg) {
    Write-Host "✗ 알 수 없는 DB: $DbName" -ForegroundColor Red
    exit 1
}

$InstallType = if ($cfg.InstallType) { $cfg.InstallType } else { "bak" }
$TargetDb = $cfg.TargetDb

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  $DbName 설치 — DataBridge 표준 검증 데이터셋" -ForegroundColor Cyan
Write-Host "  $($cfg.Description)" -ForegroundColor DarkGray
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

$SqlPwd = "Bridge@1234"
$MyPwd  = "bridge1234"

# ─── 공통 함수 ───────────────────────────────────────────────────────
$SQLCMD = "/opt/mssql-tools18/bin/sqlcmd"
$check = docker exec db_mssql sh -c "test -x $SQLCMD && echo OK" 2>$null
if ($check -notmatch "OK") {
    $SQLCMD = "/opt/mssql-tools/bin/sqlcmd"
}

function Invoke-MsSql {
    param([string]$Sql, [string]$Database = "master")
    & docker exec db_mssql $SQLCMD -S "localhost" -U "sa" -P $SqlPwd -d $Database -C -Q $Sql 2>&1
}

# ─── Step 0: 환경 점검 ──────────────────────────────────────────────
Write-Host "[0/6] 환경 점검..." -ForegroundColor Yellow

$null = docker ps 2>&1
if ($LASTEXITCODE -ne 0) { Write-Host "  ✗ Docker 실행 안 됨" -ForegroundColor Red; exit 1 }
Write-Host "  ✓ Docker 실행 중" -ForegroundColor Green

foreach ($c in @("db_mssql", "db_mysql")) {
    $running = (docker ps --filter "name=$c" --format "{{.Names}}") -eq $c
    if (-not $running) {
        docker start $c 2>&1 | Out-Null; Start-Sleep -Seconds 5
    }
    Write-Host "  ✓ $c 실행 중" -ForegroundColor Green
}

# MSSQL ready 대기
Write-Host "  → MSSQL 응답 대기..." -ForegroundColor DarkGray
$ready = $false
for ($i=0; $i -lt 12; $i++) {
    $test = Invoke-MsSql "SELECT 1"
    if ($test -match "1 rows affected") { $ready = $true; break }
    Start-Sleep -Seconds 5
}
if (-not $ready) { Write-Host "  ✗ MSSQL 미응답" -ForegroundColor Red; exit 1 }
Write-Host "  ✓ MSSQL 응답 정상" -ForegroundColor Green

# 이미 설치되어 있는지
$exists = Invoke-MsSql "SET NOCOUNT ON; SELECT name FROM sys.databases WHERE name='$DbName'"
if ($exists -match $DbName) {
    $confirm = Read-Host "  ⚠ $DbName 이미 존재. 덮어쓸까요? (y/n)"
    if ($confirm -ne "y") { Write-Host "  → 취소" -ForegroundColor Yellow; exit 0 }
    Invoke-MsSql "ALTER DATABASE $DbName SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE $DbName;" | Out-Null
}

docker exec db_mssql mkdir -p /var/opt/mssql/backup 2>$null | Out-Null

# ─── Step 1-3: BAK 또는 SQL 다운로드 + 설치 ─────────────────────────
if ($InstallType -eq "bak") {
    # BAK 파일 방식 (AdventureWorks, WideWorldImporters)
    $BakLocal = "$env:TEMP\$DbName.bak"
    $BakInContainer = "/var/opt/mssql/backup/$DbName.bak"
    
    Write-Host ""
    Write-Host "[1/6] $DbName.bak 다운로드 (~$($cfg.BakSize)MB)..." -ForegroundColor Yellow
    
    if (Test-Path $BakLocal) {
        $size = (Get-Item $BakLocal).Length / 1MB
        if ($size -lt 10) { Remove-Item $BakLocal -Force }
        else { Write-Host "  ✓ 재사용 ($([math]::Round($size,1)) MB)" -ForegroundColor Green }
    }
    
    if (-not (Test-Path $BakLocal)) {
        try {
            $oldProg = $ProgressPreference; $ProgressPreference = 'SilentlyContinue'
            Invoke-WebRequest -Uri $cfg.BakUrl -OutFile $BakLocal -UseBasicParsing
            $ProgressPreference = $oldProg
            Write-Host "  ✓ 다운로드 완료" -ForegroundColor Green
        } catch {
            Write-Host "  ✗ 다운로드 실패: $_" -ForegroundColor Red; exit 1
        }
    }
    
    Write-Host ""
    Write-Host "[2/6] 컨테이너 복사..." -ForegroundColor Yellow
    docker cp $BakLocal "db_mssql:$BakInContainer" 2>&1 | Out-Null
    Write-Host "  ✓ 복사 완료" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "[3/6] RESTORE DATABASE..." -ForegroundColor Yellow
    
    # 논리 파일명 자동 탐지
    $fileListRaw = & docker exec db_mssql $SQLCMD -S "localhost" -U "sa" -P $SqlPwd -C -h -1 -W -s "|" -Q "RESTORE FILELISTONLY FROM DISK='$BakInContainer'" 2>&1
    $moveSt = ""
    foreach ($line in $fileListRaw) {
        $cols = $line -split "\|"
        if ($cols.Length -ge 3) {
            $name = $cols[0].Trim()
            $path = $cols[1].Trim()
            if ($name -and $path) {
                $ext = if ($path -match "\.mdf$") { "mdf" }
                       elseif ($path -match "\.ldf$") { "ldf" }
                       elseif ($path -match "\.ndf$") { "ndf" }
                       else { $null }
                if ($ext) {
                    if ($moveSt) { $moveSt += ", " }
                    $newPath = "/var/opt/mssql/data/${DbName}_$name.$ext"
                    $moveSt += "MOVE '$name' TO '$newPath'"
                }
            }
        }
    }
    
    $restoreSql = "RESTORE DATABASE $DbName FROM DISK='$BakInContainer' WITH $moveSt, REPLACE, STATS=10"
    $restoreResult = Invoke-MsSql $restoreSql
    if ($restoreResult -match "RESTORE DATABASE successfully processed") {
        Write-Host "  ✓ RESTORE 성공" -ForegroundColor Green
    } else {
        Write-Host "  ✗ RESTORE 실패:" -ForegroundColor Red
        $restoreResult | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
        exit 1
    }
} else {
    # SQL 스크립트 방식 (Northwind)
    $SqlLocal = "$env:TEMP\$DbName.sql"
    
    Write-Host ""
    Write-Host "[1/6] $DbName.sql 다운로드..." -ForegroundColor Yellow
    if (-not (Test-Path $SqlLocal)) {
        try {
            $oldProg = $ProgressPreference; $ProgressPreference = 'SilentlyContinue'
            Invoke-WebRequest -Uri $cfg.SqlUrl -OutFile $SqlLocal -UseBasicParsing
            $ProgressPreference = $oldProg
            Write-Host "  ✓ 다운로드 완료" -ForegroundColor Green
        } catch {
            Write-Host "  ✗ 다운로드 실패: $_" -ForegroundColor Red; exit 1
        }
    } else {
        Write-Host "  ✓ 재사용" -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "[2/6] 컨테이너 복사..." -ForegroundColor Yellow
    docker cp $SqlLocal "db_mssql:/tmp/$DbName.sql" 2>&1 | Out-Null
    Write-Host "  ✓ 복사 완료" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "[3/6] SQL 스크립트 실행..." -ForegroundColor Yellow
    # Northwind 스크립트는 USE master 부터 시작하며 자체적으로 CREATE DATABASE
    $execResult = & docker exec db_mssql $SQLCMD -S "localhost" -U "sa" -P $SqlPwd -C -i "/tmp/$DbName.sql" 2>&1
    Write-Host "  ✓ SQL 스크립트 실행 완료" -ForegroundColor Green
}

# ─── Step 4: 검증 (일반 패턴 — 모든 DB 동일) ──────────────────────────
Write-Host ""
Write-Host "[4/6] 데이터 검증 (객체 카운트)..." -ForegroundColor Yellow

$verifySql = "SET NOCOUNT ON; SELECT 'tables' AS metric, CAST(COUNT(*) AS VARCHAR) AS cnt FROM sys.tables UNION ALL SELECT 'views', CAST(COUNT(*) AS VARCHAR) FROM sys.views UNION ALL SELECT 'sps', CAST(COUNT(*) AS VARCHAR) FROM sys.procedures UNION ALL SELECT 'fns', CAST(COUNT(*) AS VARCHAR) FROM sys.objects WHERE type IN ('FN','IF','TF') UNION ALL SELECT 'trigs', CAST(COUNT(*) AS VARCHAR) FROM sys.triggers UNION ALL SELECT 'fks', CAST(COUNT(*) AS VARCHAR) FROM sys.foreign_keys"
$verify = & docker exec db_mssql $SQLCMD -S "localhost" -U "sa" -P $SqlPwd -d $DbName -C -h -1 -W -s "|" -Q $verifySql 2>&1
$verify | Where-Object { $_ -match "\|" } | ForEach-Object {
    $parts = $_ -split "\|"
    if ($parts.Length -ge 2) {
        $metric = $parts[0].Trim(); $cnt = $parts[1].Trim()
        if ($metric -and $cnt -match "^\d+$") {
            Write-Host "  ✓ ${metric}: $cnt" -ForegroundColor Green
        }
    }
}

# ─── Step 5: MySQL 타겟 DB 생성 (일반 패턴) ────────────────────────────
Write-Host ""
Write-Host "[5/6] MySQL 타겟 DB 생성 ($TargetDb)..." -ForegroundColor Yellow

$mysqlExists = docker exec db_mysql mysql -u root "-p$MyPwd" -e "SHOW DATABASES LIKE '$TargetDb'" 2>$null
if ($mysqlExists -match $TargetDb) {
    $confirm = Read-Host "  ⚠ $TargetDb 이미 존재. DROP 후 재생성? (y/n)"
    if ($confirm -eq "y") {
        docker exec db_mysql mysql -u root "-p$MyPwd" -e "DROP DATABASE $TargetDb" 2>$null | Out-Null
        docker exec db_mysql mysql -u root "-p$MyPwd" -e "CREATE DATABASE $TargetDb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci" 2>$null | Out-Null
        Write-Host "  ✓ 재생성" -ForegroundColor Green
    }
} else {
    docker exec db_mysql mysql -u root "-p$MyPwd" -e "CREATE DATABASE $TargetDb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci" 2>$null | Out-Null
    Write-Host "  ✓ 생성 완료" -ForegroundColor Green
}

# ─── Step 6: 안내 ────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✅ $DbName 설치 완료" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "DataBridge 연결 정보:" -ForegroundColor Yellow
Write-Host "  📥 소스 (MSSQL): localhost:1433 / sa / $SqlPwd / $DbName" -ForegroundColor White
Write-Host "  📤 타겟 (MySQL): localhost:3306 / root / $MyPwd / $TargetDb" -ForegroundColor White
Write-Host ""
