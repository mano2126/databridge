# DataBridge 종합 복구 상태 진단 (v90.37)
# 본부장님 환경 - 50/62 테이블 이관됨, 12개 누락 + 객체 실패 분석
#
# 사용법: 
#   PS> cd D:\project\databridge_full\backend\scripts
#   PS> .\full_recovery_status.ps1
#
# 핵심 수정사항 (이전 스크립트 버그):
#   - PowerShell 문자열에서 \b 가 backspace 로 해석되는 문제
#   - 모든 경로는 single quote 또는 escape 사용

Write-Host ""
Write-Host "🔍 DataBridge 종합 복구 상태 진단 v90.37" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan

# ── [1] Docker 컨테이너 ──────────────────────────────────────
Write-Host ""
Write-Host "[1/6] 컨테이너 상태" -ForegroundColor Yellow
docker ps --format "table {{.Names}}`t{{.Status}}" 2>$null | Select-String -Pattern "db_mysql|db_mssql|NAMES"

# ── [2] 백엔드 API ──────────────────────────────────────────
Write-Host ""
Write-Host "[2/6] 백엔드 API 상태" -ForegroundColor Yellow
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/jobs/" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    Write-Host "  ✅ 백엔드 정상 (HTTP $($resp.StatusCode))" -ForegroundColor Green
    $backendOk = $true
} catch {
    Write-Host "  ❌ 백엔드 응답 안 함: $($_.Exception.Message)" -ForegroundColor Red
    $backendOk = $false
}

# ── [3] v90.33/34 적용 검증 ────────────────────────────────
Write-Host ""
Write-Host "[3/6] v90.33/34 코드 적용 검증" -ForegroundColor Yellow

# single quote 사용 - \b 회피
$parser_path = 'D:\project\databridge_full\backend\app\core\ai_response_parser.py'
$postproc_path = 'D:\project\databridge_full\backend\app\core\sql_post_processor.py'

if (Test-Path $parser_path) {
    $c = Get-Content $parser_path -Raw
    if ($c -match "catastrophic backtracking") {
        Write-Host "  ✅ ai_response_parser.py - v90.33 적용됨" -ForegroundColor Green
    } else {
        Write-Host "  ❌ ai_response_parser.py - v90.33 미적용 (ReDoS 위험!)" -ForegroundColor Red
    }
} else {
    Write-Host "  ❌ ai_response_parser.py 없음" -ForegroundColor Red
}

if (Test-Path $postproc_path) {
    Write-Host "  ✅ sql_post_processor.py - v90.34 파일 존재" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  sql_post_processor.py 없음 (자기학습 비활성)" -ForegroundColor Yellow
}

# Python 캐시 점검
$pycache = Get-ChildItem -Path 'D:\project\databridge_full\backend' -Filter '__pycache__' -Recurse -Directory -ErrorAction SilentlyContinue
$pycCount = ($pycache | Measure-Object).Count
if ($pycCount -gt 0) {
    Write-Host "  ⚠️  __pycache__ $pycCount 개 - 옛 코드 가능성! 삭제 권장" -ForegroundColor Yellow
} else {
    Write-Host "  ✅ Python 캐시 깨끗함" -ForegroundColor Green
}

# ── [4] 타겟 MySQL 상태 ────────────────────────────────────
Write-Host ""
Write-Host "[4/6] MySQL 타겟 스키마 + 객체 현황" -ForegroundColor Yellow
$pwd_mysql = Read-Host "  MySQL root 비밀번호 입력" -AsSecureString
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($pwd_mysql)
$plain_pwd = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

# 스키마 자동 탐색
$schemaQuery = "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME NOT IN ('mysql','information_schema','performance_schema','sys') ORDER BY SCHEMA_NAME;"
$schemas = docker exec db_mysql mysql -uroot -p"$plain_pwd" -N -e $schemaQuery 2>$null

Write-Host "  사용자 스키마 목록:" -ForegroundColor Cyan
$schemas | ForEach-Object { Write-Host "    - $_" }

# 가장 가능성 있는 타겟 스키마 (capital_* 또는 첫 번째)
$tgtSchema = ($schemas | Where-Object { $_ -match 'capital' } | Select-Object -First 1)
if (-not $tgtSchema) {
    $tgtSchema = ($schemas | Select-Object -First 1)
}

if ($tgtSchema) {
    Write-Host ""
    Write-Host "  타겟 스키마로 가정: $tgtSchema" -ForegroundColor Cyan
    
    # 테이블 목록
    $tblQ = "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='$tgtSchema' AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME;"
    $tables = docker exec db_mysql mysql -uroot -p"$plain_pwd" -N -e $tblQ 2>$null
    $tblCount = ($tables | Measure-Object).Count
    Write-Host "  📋 테이블: $tblCount 개" -ForegroundColor White
    
    # 객체별 카운트
    $procQ = "SELECT COUNT(*) FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_SCHEMA='$tgtSchema' AND ROUTINE_TYPE='PROCEDURE';"
    $funcQ = "SELECT COUNT(*) FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_SCHEMA='$tgtSchema' AND ROUTINE_TYPE='FUNCTION';"
    $viewQ = "SELECT COUNT(*) FROM INFORMATION_SCHEMA.VIEWS WHERE TABLE_SCHEMA='$tgtSchema';"
    $trigQ = "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TRIGGERS WHERE TRIGGER_SCHEMA='$tgtSchema';"
    
    $procCnt = docker exec db_mysql mysql -uroot -p"$plain_pwd" -N -e $procQ 2>$null
    $funcCnt = docker exec db_mysql mysql -uroot -p"$plain_pwd" -N -e $funcQ 2>$null
    $viewCnt = docker exec db_mysql mysql -uroot -p"$plain_pwd" -N -e $viewQ 2>$null
    $trigCnt = docker exec db_mysql mysql -uroot -p"$plain_pwd" -N -e $trigQ 2>$null
    
    Write-Host "  ⚙ Procedure: $procCnt 개" -ForegroundColor White
    Write-Host "  ƒ Function:  $funcCnt 개" -ForegroundColor White
    Write-Host "  👁 View:     $viewCnt 개" -ForegroundColor White
    Write-Host "  ⚡ Trigger:  $trigCnt 개" -ForegroundColor White
    
    $script:tgtSchema_g = $tgtSchema
    $script:plain_pwd_g = $plain_pwd
}

# ── [5] 소스(MSSQL) vs 타겟 비교 ────────────────────────────
Write-Host ""
Write-Host "[5/6] 소스(MSSQL) vs 타겟(MySQL) 차이 분석" -ForegroundColor Yellow

if ($tgtSchema) {
    Write-Host "  MSSQL 비밀번호 (sa) 입력하면 자동 비교" -ForegroundColor Cyan
    $pwd_mssql = Read-Host "  MSSQL sa 비밀번호 (Skip 하려면 Enter)" -AsSecureString
    $BSTR2 = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($pwd_mssql)
    $mssql_pwd = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR2)
    
    if ($mssql_pwd) {
        # MSSQL 테이블 목록 (소스 DB 추정)
        $mssqlSchemaQ = "SELECT name FROM sys.databases WHERE database_id > 4 ORDER BY name"
        $mssqlSchemas = docker exec db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$mssql_pwd" -C -h-1 -W -Q "$mssqlSchemaQ" 2>$null | Where-Object { $_ -and $_ -notmatch 'rows affected' }
        
        Write-Host "  MSSQL 사용자 DB 목록:" -ForegroundColor Cyan
        $mssqlSchemas | ForEach-Object { Write-Host "    - $_" }
        
        # 가장 가능성 있는 소스 DB
        $srcDb = ($mssqlSchemas | Where-Object { $_ -match 'capital' } | Select-Object -First 1)
        if (-not $srcDb) { $srcDb = ($mssqlSchemas | Select-Object -First 1) }
        
        if ($srcDb) {
            Write-Host ""
            Write-Host "  소스 DB: $srcDb" -ForegroundColor Cyan
            
            $srcTblQ = "USE [$srcDb]; SELECT name FROM sys.tables ORDER BY name"
            $srcTables = docker exec db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$mssql_pwd" -C -h-1 -W -Q "$srcTblQ" 2>$null | Where-Object { $_ -and $_ -notmatch 'rows affected' -and $_.Trim() -ne '' }
            
            $srcCount = ($srcTables | Measure-Object).Count
            Write-Host "  소스 테이블: $srcCount 개" -ForegroundColor White
            Write-Host "  타겟 테이블: $tblCount 개" -ForegroundColor White
            Write-Host "  ⚠️ 차이: $($srcCount - $tblCount) 개" -ForegroundColor Yellow
            
            # 누락된 테이블 출력
            if ($srcTables -and $tables) {
                $srcSet = [System.Collections.Generic.HashSet[string]]::new()
                $srcTables | ForEach-Object { [void]$srcSet.Add($_.Trim().ToLower()) }
                $tgtSet = [System.Collections.Generic.HashSet[string]]::new()
                $tables | ForEach-Object { [void]$tgtSet.Add($_.Trim().ToLower()) }
                
                $missing = $srcTables | Where-Object { -not $tgtSet.Contains($_.Trim().ToLower()) }
                if ($missing) {
                    Write-Host ""
                    Write-Host "  📋 누락된 테이블 ($($missing.Count) 개):" -ForegroundColor Red
                    $missing | ForEach-Object { Write-Host "    - $_" -ForegroundColor Yellow }
                }
            }
        }
    } else {
        Write-Host "  (MSSQL 비교 skip)" -ForegroundColor Gray
    }
}

# ── [6] DataBridge Job Store ───────────────────────────────
Write-Host ""
Write-Host "[6/6] DataBridge Job Store" -ForegroundColor Yellow
$db_path = 'D:\project\databridge_full\backend\data\databridge.db'
if (Test-Path $db_path) {
    $size = (Get-Item $db_path).Length / 1KB
    Write-Host "  ✅ Job DB 파일 존재 ($([math]::Round($size, 1)) KB)" -ForegroundColor Green
    Write-Host "  최근 Job 은 백엔드 API 로 조회 가능:" -ForegroundColor Cyan
    Write-Host "    GET http://localhost:8000/api/v1/jobs/" -ForegroundColor Gray
} else {
    Write-Host "  ⚠️ Job DB 파일 없음: $db_path" -ForegroundColor Yellow
}

# ── 결론 ─────────────────────────────────────────────────────
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "📋 진단 요약 + 권장 조치" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host ""

if (-not $backendOk) {
    Write-Host "  ⚠️  백엔드 응답 없음 → 재시작 필요" -ForegroundColor Yellow
}

if ($pycCount -gt 0) {
    Write-Host "  ⚠️  Python 캐시 $pycCount 개 → v90.36 deploy 스크립트 실행 권장" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  결과를 Claude 에게 공유하여 다음 단계 결정"
Write-Host ""
