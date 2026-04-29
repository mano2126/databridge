# 정확한 누락 파악 스크립트 v90.38
# 본부장님 환경 - 1개 차이가 진짜 누락인지 sqlcmd 메시지인지 확인
# + 객체 (SP/FN/View/Trigger) 별 누락 정확 분석

Write-Host ""
Write-Host "🔍 정확한 누락 객체 진단" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan

# 비밀번호 입력
$pwd_mysql = Read-Host "MySQL root 비밀번호" -AsSecureString
$BSTR1 = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($pwd_mysql)
$mysql_pwd = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR1)

$pwd_mssql = Read-Host "MSSQL sa 비밀번호" -AsSecureString
$BSTR2 = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($pwd_mssql)
$mssql_pwd = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR2)

$srcDb = 'capital_midsize'
$tgtDb = 'capital_target'

# ── [1] 테이블 정확 비교 ──────────────────────────────────────
Write-Host ""
Write-Host "[1] 테이블 정확 비교" -ForegroundColor Yellow

# MSSQL: USE 문 분리 - 메시지 없이 깔끔하게 가져오기
# -d 옵션으로 DB 지정 + -W 로 trim
$srcTblQ = "SET NOCOUNT ON; SELECT name FROM sys.tables ORDER BY name"
$srcTablesRaw = docker exec db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$mssql_pwd" -C -d "$srcDb" -h-1 -W -Q "$srcTblQ" 2>$null
# 빈 줄 + 메시지 제거
$srcTables = $srcTablesRaw | Where-Object { 
    $_ -and 
    $_.Trim() -ne '' -and 
    $_ -notmatch 'rows affected' -and
    $_ -notmatch 'Changed database' -and
    $_ -notmatch '^---'
} | ForEach-Object { $_.Trim() }

# MySQL
$tgtTblQ = "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='$tgtDb' AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME"
$tgtTables = docker exec db_mysql mysql -uroot -p"$mysql_pwd" -N -e "$tgtTblQ" 2>$null | Where-Object { $_ -and $_.Trim() -ne '' } | ForEach-Object { $_.Trim() }

Write-Host "  소스(MSSQL) 테이블: $($srcTables.Count) 개"
Write-Host "  타겟(MySQL) 테이블: $($tgtTables.Count) 개"

# 누락 목록
$tgtSet = [System.Collections.Generic.HashSet[string]]::new()
$tgtTables | ForEach-Object { [void]$tgtSet.Add($_.ToLower()) }

$missingTables = @()
foreach ($t in $srcTables) {
    if (-not $tgtSet.Contains($t.ToLower())) {
        $missingTables += $t
    }
}

if ($missingTables.Count -gt 0) {
    Write-Host ""
    Write-Host "  📋 진짜 누락된 테이블 ($($missingTables.Count) 개):" -ForegroundColor Red
    $missingTables | ForEach-Object { Write-Host "    - $_" -ForegroundColor Yellow }
} else {
    Write-Host "  ✅ 누락 테이블 없음! 모두 이관됨" -ForegroundColor Green
}

# ── [2] Procedure 비교 ──────────────────────────────────────
Write-Host ""
Write-Host "[2] Procedure 비교" -ForegroundColor Yellow

$srcProcQ = "SET NOCOUNT ON; SELECT name FROM sys.procedures ORDER BY name"
$srcProcRaw = docker exec db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$mssql_pwd" -C -d "$srcDb" -h-1 -W -Q "$srcProcQ" 2>$null
$srcProcs = $srcProcRaw | Where-Object { 
    $_ -and 
    $_.Trim() -ne '' -and 
    $_ -notmatch 'rows affected' -and
    $_ -notmatch 'Changed database' -and
    $_ -notmatch '^---'
} | ForEach-Object { $_.Trim() }

$tgtProcQ = "SELECT ROUTINE_NAME FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_SCHEMA='$tgtDb' AND ROUTINE_TYPE='PROCEDURE' ORDER BY ROUTINE_NAME"
$tgtProcs = docker exec db_mysql mysql -uroot -p"$mysql_pwd" -N -e "$tgtProcQ" 2>$null | Where-Object { $_ -and $_.Trim() -ne '' } | ForEach-Object { $_.Trim() }

Write-Host "  소스(MSSQL) Procedure: $($srcProcs.Count) 개"
Write-Host "  타겟(MySQL) Procedure: $($tgtProcs.Count) 개"

# 매칭 - prefix 'dbo_' 또는 정확히 일치
$tgtProcSet = [System.Collections.Generic.HashSet[string]]::new()
$tgtProcs | ForEach-Object { 
    $name = $_.ToLower()
    [void]$tgtProcSet.Add($name)
    # dbo_ prefix 도 있을 수 있음
    if ($name.StartsWith('dbo_')) { 
        [void]$tgtProcSet.Add($name.Substring(4)) 
    }
}

$missingProcs = @()
foreach ($p in $srcProcs) {
    $pl = $p.ToLower()
    if (-not $tgtProcSet.Contains($pl) -and -not $tgtProcSet.Contains("dbo_$pl")) {
        $missingProcs += $p
    }
}

if ($missingProcs.Count -gt 0) {
    Write-Host ""
    Write-Host "  ⚙ 누락된 Procedure ($($missingProcs.Count) 개):" -ForegroundColor Red
    $missingProcs | ForEach-Object { Write-Host "    - $_" -ForegroundColor Yellow }
} else {
    Write-Host "  ✅ Procedure 누락 없음" -ForegroundColor Green
}

# ── [3] Function 비교 ──────────────────────────────────────
Write-Host ""
Write-Host "[3] Function 비교" -ForegroundColor Yellow

$srcFnQ = "SET NOCOUNT ON; SELECT name FROM sys.objects WHERE type IN ('FN','IF','TF') ORDER BY name"
$srcFnRaw = docker exec db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$mssql_pwd" -C -d "$srcDb" -h-1 -W -Q "$srcFnQ" 2>$null
$srcFns = $srcFnRaw | Where-Object { 
    $_ -and $_.Trim() -ne '' -and 
    $_ -notmatch 'rows affected' -and
    $_ -notmatch 'Changed database' -and
    $_ -notmatch '^---'
} | ForEach-Object { $_.Trim() }

$tgtFnQ = "SELECT ROUTINE_NAME FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_SCHEMA='$tgtDb' AND ROUTINE_TYPE='FUNCTION' ORDER BY ROUTINE_NAME"
$tgtFns = docker exec db_mysql mysql -uroot -p"$mysql_pwd" -N -e "$tgtFnQ" 2>$null | Where-Object { $_ -and $_.Trim() -ne '' } | ForEach-Object { $_.Trim() }

Write-Host "  소스(MSSQL) Function: $($srcFns.Count) 개"
Write-Host "  타겟(MySQL) Function: $($tgtFns.Count) 개"

# ── [4] Trigger 비교 (★ 본부장님 핵심 관심사 ★) ─────────
Write-Host ""
Write-Host "[4] Trigger 비교 ★ 본부장님 핵심 ★" -ForegroundColor Yellow

$srcTrigQ = "SET NOCOUNT ON; SELECT name FROM sys.triggers ORDER BY name"
$srcTrigRaw = docker exec db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$mssql_pwd" -C -d "$srcDb" -h-1 -W -Q "$srcTrigQ" 2>$null
$srcTrigs = $srcTrigRaw | Where-Object { 
    $_ -and $_.Trim() -ne '' -and 
    $_ -notmatch 'rows affected' -and
    $_ -notmatch 'Changed database' -and
    $_ -notmatch '^---'
} | ForEach-Object { $_.Trim() }

$tgtTrigQ = "SELECT TRIGGER_NAME FROM INFORMATION_SCHEMA.TRIGGERS WHERE TRIGGER_SCHEMA='$tgtDb' ORDER BY TRIGGER_NAME"
$tgtTrigs = docker exec db_mysql mysql -uroot -p"$mysql_pwd" -N -e "$tgtTrigQ" 2>$null | Where-Object { $_ -and $_.Trim() -ne '' } | ForEach-Object { $_.Trim() }

Write-Host "  소스(MSSQL) Trigger: $($srcTrigs.Count) 개"
Write-Host "  타겟(MySQL) Trigger: $($tgtTrigs.Count) 개"

if ($srcTrigs.Count -gt 0) {
    Write-Host ""
    Write-Host "  소스 트리거 목록:" -ForegroundColor Cyan
    $srcTrigs | ForEach-Object { Write-Host "    - $_" }
}

if ($tgtTrigs.Count -lt $srcTrigs.Count) {
    Write-Host ""
    Write-Host "  ⚡ 누락된 Trigger ($($srcTrigs.Count - $tgtTrigs.Count) 개)" -ForegroundColor Red
}

# ── 결론 ────────────────────────────────────────────────
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "📊 최종 진단 요약" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host ""
Write-Host "  소스 vs 타겟"
Write-Host "  ─────────────────────────────────────────"
Write-Host "  Tables:     소스 $($srcTables.Count) → 타겟 $($tgtTables.Count) (누락 $($missingTables.Count))"
Write-Host "  Procedures: 소스 $($srcProcs.Count) → 타겟 $($tgtProcs.Count) (누락 $($missingProcs.Count))"
Write-Host "  Functions:  소스 $($srcFns.Count) → 타겟 $($tgtFns.Count)"
Write-Host "  Triggers:   소스 $($srcTrigs.Count) → 타겟 $($tgtTrigs.Count) (누락 $($srcTrigs.Count - $tgtTrigs.Count))"
Write-Host ""
Write-Host "  결과를 Claude 에게 공유하여 재이관 계획 수립"
Write-Host ""
