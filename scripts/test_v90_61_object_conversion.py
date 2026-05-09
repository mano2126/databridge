# ============================================================
# verify_v90_61.ps1 - DataBridge v90.61 SP/FN/VW/TR 변환 강화
# ============================================================
# 본부장님 환경 41개 SP/FN/VW/TR 1064/1049 오류 처방.
# v90.61 fix:
#   1. schema_conversion_policy.py - 정규식 5개 변종 추가
#   2. obj_executor.py - _extract_obj_name + 후처리 6종
#   3. system.txt - 본부장님 41개 케이스 prompt 강화
# ============================================================

$ErrorActionPreference = "Continue"
$BACKEND_DIR = "D:\project\databridge_full\backend"

Write-Host "============================================================"
Write-Host " DataBridge v90.61 SP/FN/VW/TR 변환 강화"
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
Write-Host "[1/5] 핵심 파일 존재 확인"
# ------------------------------------------------------------
$scp = Join-Path $BACKEND_DIR "app\core\schema_conversion_policy.py"
$oe  = Join-Path $BACKEND_DIR "app\core\obj_executor.py"
$st  = Join-Path $BACKEND_DIR "prompts\mssql_to_mysql\system.txt"
$tp  = Join-Path $BACKEND_DIR "tests\test_v90_61_object_conversion.py"

Check-Item "schema_conversion_policy.py" (Test-Path $scp)
Check-Item "obj_executor.py"              (Test-Path $oe)
Check-Item "system.txt"                   (Test-Path $st)
Check-Item "test_v90_61_object_conversion.py" (Test-Path $tp)

# ------------------------------------------------------------
Write-Host ""
Write-Host "[2/5] schema_conversion_policy.py - 정규식 변종"
# ------------------------------------------------------------
if (Test-Path $scp) {
    $content = Get-Content $scp -Raw
    
    $hasMarker      = $content.Contains("v90.61")
    $hasSchemaOnly  = $content.Contains('rf') -and $content.Contains("`{schema}`") -and $content.Contains("\.(\w+)")
    $hasBrackets    = $content.Contains('rf') -and $content.Contains("\[{schema}\]")
    
    Check-Item "v90.61 마커"                     $hasMarker
    Check-Item "schema-only-backtick 패턴"       $hasSchemaOnly
    Check-Item "MSSQL 대괄호 패턴"               $hasBrackets
}

# ------------------------------------------------------------
Write-Host ""
Write-Host "[3/5] obj_executor.py - 헬퍼 + 후처리"
# ------------------------------------------------------------
if (Test-Path $oe) {
    $content = Get-Content $oe -Raw
    
    $hasHelper      = $content.Contains("def _extract_obj_name")
    $hasV61Comment  = $content.Contains("v90.61: 객체 이름 추출")
    $hasDateTime2   = $content.Contains("DATETIME2") -and $content.Contains("DATETIME(6)")
    $hasIfReturn    = $content.Contains("IF \\1 THEN RETURN") -or $content.Contains("THEN RETURN")
    $hasDeclare     = $content.Contains("DECLARE 인라인")
    $hasConcat      = $content.Contains("_replace_string_concat")
    $hasDateAdd     = $content.Contains("DATE_ADD")
    $hasTVF         = $content.Contains("TVF") -and $content.Contains("MySQL 미지원")
    
    Check-Item "_extract_obj_name 헬퍼"          $hasHelper
    Check-Item "v90.61 객체명 추출 강화 주석"    $hasV61Comment
    Check-Item "DATETIME2 변환"                  $hasDateTime2
    Check-Item "IF...THEN RETURN 변환"           $hasIfReturn
    Check-Item "DECLARE 인라인 분리"             $hasDeclare
    Check-Item "문자열 + 결합 CONCAT"            $hasConcat
    Check-Item "DATEADD/DATE_ADD"                $hasDateAdd
    Check-Item "TVF 경고"                        $hasTVF
}

# ------------------------------------------------------------
Write-Host ""
Write-Host "[4/5] system.txt - prompt 강화"
# ------------------------------------------------------------
if (Test-Path $st) {
    $content = Get-Content $st -Raw
    
    $has5Patterns   = $content.Contains("5대 패턴")
    $hasCollection  = $content.Contains("collection_fn_delinq_stage")
    $hasDt2Pattern  = $content.Contains("DATETIME2") -and $content.Contains("DATETIME(6)")
    $hasIfReturnP   = $content.Contains("THEN") -and $content.Contains("END IF")
    $hasDeclareP    = $content.Contains("DECLARE") -and $content.Contains("인라인")
    $hasConcatP     = $content.Contains("문자열") -and $content.Contains("CONCAT")
    $hasChecklist   = $content.Contains("체크리스트")
    
    Check-Item "5대 패턴 명시"                   $has5Patterns
    Check-Item "본부장님 케이스 명시"            $hasCollection
    Check-Item "DATETIME2 패턴"                  $hasDt2Pattern
    Check-Item "IF...RETURN 패턴"                $hasIfReturnP
    Check-Item "DECLARE 인라인 패턴"             $hasDeclareP
    Check-Item "문자열 + 패턴"                   $hasConcatP
    Check-Item "자체 검증 체크리스트"            $hasChecklist
}

# ------------------------------------------------------------
Write-Host ""
Write-Host "[5/5] Python 구문 + 단위 테스트 (41개 검증)"
# ------------------------------------------------------------

# Python ast.parse 검증
$pythonFiles = @($scp, $oe)
foreach ($pf in $pythonFiles) {
    if (Test-Path $pf) {
        $rel = $pf.Replace($BACKEND_DIR + "\", "")
        $cmd = "python -c `"import ast; ast.parse(open(r'$pf', encoding='utf-8').read()); print('OK')`""
        $result = Invoke-Expression $cmd 2>&1
        Check-Item "ast.parse $rel" ($result -match "OK")
    }
}

# pytest 실행
Push-Location $BACKEND_DIR
try {
    $testFile = "tests\test_v90_61_object_conversion.py"
    if (Test-Path $testFile) {
        $testResult = python -m pytest $testFile -v 2>&1
        $passLine = $testResult | Select-String "passed"
        if ($passLine) {
            Write-Host "  [PASS] pytest: $passLine" -ForegroundColor Green
            $script:passCount = $script:passCount + 1
            
            $hasAll41        = $testResult | Select-String "test_all_41_objects_normalized.*PASSED"
            $hasPresidentFn  = $testResult | Select-String "test_president_full_create_function_normalized.*PASSED"
            $hasDt2Test      = $testResult | Select-String "test_datetime2_converted.*PASSED"
            $hasIfTest       = $testResult | Select-String "test_if_return_converted.*PASSED"
            $hasDeclareTest  = $testResult | Select-String "test_declare_inline_init_converted.*PASSED"
            
            Check-Item "본부장님 41개 객체 종합 검증" ($null -ne $hasAll41)
            Check-Item "fn_delinq_stage 케이스"      ($null -ne $hasPresidentFn)
            Check-Item "DATETIME2 변환 테스트"       ($null -ne $hasDt2Test)
            Check-Item "IF...RETURN 변환 테스트"     ($null -ne $hasIfTest)
            Check-Item "DECLARE 인라인 분리 테스트"  ($null -ne $hasDeclareTest)
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
    Write-Host "v90.61 패치 정상 적용 완료." -ForegroundColor Green
    Write-Host ""
    Write-Host "  적용 후 단계:"
    Write-Host "  1. FastAPI 재기동 (Ctrl+C 후 uvicorn 재실행)"
    Write-Host "  2. 이관 작업 모니터 - SP/FN/VW/TR 재변환"
    Write-Host "     (테이블은 이미 완료, 재이관 불필요)"
    Write-Host "  3. backend.log 에서 1064/1049 오류 미발생 확인"
    Write-Host ""
    Write-Host "  예상 결과: 41개 중 약 36-37개 즉시 통과,"
    Write-Host "             TVF 4개는 MySQL 미지원이라 경고 후 수동 변환 필요"
    exit 0
} else {
    Write-Host ""
    Write-Host "일부 항목 실패. 위 FAIL 로그 확인 부탁드립니다." -ForegroundColor Red
    exit 1
}