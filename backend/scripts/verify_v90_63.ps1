# ============================================================
# verify_v90_63.ps1 - DataBridge v90.63 SP 1064 후처리 fix
# ============================================================
$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"
$FRONTEND_DIR = "D:\project\databridge_full\frontend"

Write-Host "============================================================"
Write-Host " DataBridge v90.63 SP 1064 후처리 fix"
Write-Host "============================================================"
Write-Host ""

$script:passCount = 0
$script:failCount = 0

function Check-Item {
    param([string]$Name, [bool]$Result)
    if ($Result) {
        Write-Host "  [PASS] $Name" -ForegroundColor Green
        $script:passCount = $script:passCount + 1
    } else {
        Write-Host "  [FAIL] $Name" -ForegroundColor Red
        $script:failCount = $script:failCount + 1
    }
}

# ------------------------------------------------------------
Write-Host "[1/3] 핵심 파일 존재"
# ------------------------------------------------------------
$oe  = Join-Path $BACKEND_DIR  "app\core\obj_executor.py"
$st  = Join-Path $BACKEND_DIR  "prompts\mssql_to_mysql\system.txt"
$tp  = Join-Path $BACKEND_DIR  "tests\test_v90_63_post_processor_fix.py"
$ms  = Join-Path $FRONTEND_DIR "src\store\monitorStore.js"
$jm  = Join-Path $FRONTEND_DIR "src\pages\JobMonitor.vue"

Check-Item "obj_executor.py"                    (Test-Path $oe)
Check-Item "system.txt"                         (Test-Path $st)
Check-Item "test_v90_63_post_processor_fix.py"  (Test-Path $tp)
Check-Item "monitorStore.js (v90.62 통합)"      (Test-Path $ms)
Check-Item "JobMonitor.vue (v90.62 통합)"       (Test-Path $jm)

# ------------------------------------------------------------
Write-Host ""
Write-Host "[2/3] obj_executor.py + system.txt v90.63 변경"
# ------------------------------------------------------------
if (Test-Path $oe) {
    $content = Get-Content $oe -Raw
    Check-Item "v90.63 마커"                  ($content.Contains("v90.63"))
    Check-Item "P1 RETURN CASE; 후처리"       ($content.Contains("RETURN CASE"))
    Check-Item "P2 SET ... ; WHERE 후처리"    ($content.Contains("SET\s+\w+\s*=\s*[^;\n]+?);(\s*\n\s*WHERE"))
    Check-Item "P3 ,; 콤마+; 후처리"          ($content.Contains(",\s*;\s*\n"))
    Check-Item "P4 RETURN expr ; 보장"        ($content.Contains("RETURN\s+(?!CASE"))
}

if (Test-Path $st) {
    $content = Get-Content $st -Raw
    Check-Item "9대 패턴 헤더"            ($content.Contains("9대 패턴"))
    Check-Item "패턴 6 (RETURN CASE;)"    ($content.Contains("패턴 6"))
    Check-Item "패턴 7 (SET ... ; WHERE)" ($content.Contains("패턴 7"))
    Check-Item "패턴 8 (콤마+;)"           ($content.Contains("패턴 8"))
    Check-Item "패턴 9 (RETURN ;)"         ($content.Contains("패턴 9"))
}

# ------------------------------------------------------------
Write-Host ""
Write-Host "[3/3] Python 검증 + 단위 테스트 (11개 본부장님 케이스)"
# ------------------------------------------------------------
foreach ($pf in @($oe)) {
    if (Test-Path $pf) {
        $rel = $pf.Replace($BACKEND_DIR + "\", "")
        $cmd = "python -c `"import ast; ast.parse(open(r'$pf', encoding='utf-8').read()); print('OK')`""
        $result = Invoke-Expression $cmd 2>&1
        Check-Item "ast.parse $rel" ($result -match "OK")
    }
}

Push-Location $BACKEND_DIR
try {
    if (Test-Path "tests\test_v90_63_post_processor_fix.py") {
        $testResult = python -m pytest tests/test_v90_63_post_processor_fix.py -v 2>&1
        $passLine = $testResult | Select-String "passed"
        if ($passLine) {
            Write-Host "  [PASS] pytest: $passLine" -ForegroundColor Green
            $script:passCount = $script:passCount + 1
            
            $hasP1 = $testResult | Select-String "test_return_case_semicolon_removed.*PASSED"
            $hasP2 = $testResult | Select-String "test_set_then_where_semicolon_removed.*PASSED"
            $hasP3 = $testResult | Select-String "test_comma_semicolon_removed_approve.*PASSED"
            $has11 = $testResult | Select-String "test_all_11_president_cases_after_v90_63.*PASSED"
            
            Check-Item "P1 RETURN CASE; fix"           ($null -ne $hasP1)
            Check-Item "P2 UPDATE SET ; WHERE fix"     ($null -ne $hasP2)
            Check-Item "P3 콤마 ; fix"                  ($null -ne $hasP3)
            Check-Item "본부장님 11개 케이스 통과"      ($null -ne $has11)
        } else {
            Write-Host "  [FAIL] pytest 실행 실패" -ForegroundColor Red
            $script:failCount = $script:failCount + 1
        }
    }
} finally {
    Pop-Location
}

# ------------------------------------------------------------
Write-Host ""
Write-Host "============================================================"
Write-Host " 검증 완료: PASS $script:passCount / FAIL $script:failCount"
Write-Host "============================================================"

if ($script:failCount -eq 0) {
    Write-Host ""
    Write-Host "v90.63 패치 정상 적용." -ForegroundColor Green
    Write-Host ""
    Write-Host "  적용 후 동작 확인:"
    Write-Host "  1. FastAPI 재기동 (Ctrl+C 후 uvicorn)"
    Write-Host "  2. 이관 작업 모니터 - SP/FN/VW/TR 재시도"
    Write-Host "     (테이블은 이미 100% 완료)"
    Write-Host "  3. 11개 잔여 SP/FN 모두 통과 예상"
    Write-Host ""
    Write-Host "  v90.62 frontend (모니터 폴링 + 라이브 점멸) 도 함께 적용됨"
    exit 0
} else {
    Write-Host "일부 항목 실패. 위 FAIL 로그 확인." -ForegroundColor Red
    exit 1
}
