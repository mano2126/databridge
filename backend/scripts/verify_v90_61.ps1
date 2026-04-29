# ═══════════════════════════════════════════════════════════════════════════
# verify_v90_61.ps1 — DataBridge v90.61 SP/FN/VW/TR 변환 전수 강화
# ═══════════════════════════════════════════════════════════════════════════
# 본부장님 환경 (2026-04-28):
#   41개 SP/FN/VW/TR 모두 1064 또는 1049 오류로 실패.
#   진짜 원인 (테더링 무관 - AI API timeout 0건):
#     1. enforce_schema_strategy 가 `schema`.name 변종을 못 잡음
#     2. obj_executor 의 객체명 추출 정규식이 schema.name 을 잘못 처리
#     3. AI prompt 에 underscore 정책이 명확하지 않음
#     4. DATETIME2/IF...RETURN/DECLARE 인라인/문자열+ 등 후처리 누락
#
# v90.61 처방 (4갈래):
#   1. schema_conversion_policy.py — 정규식 5개 변종 추가
#   2. obj_executor.py — _extract_obj_name 헬퍼 + 후처리 변환 6종
#   3. system.txt — 본부장님 41개 케이스 명시 + 5대 패턴 + 체크리스트
# ═══════════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"

Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host " DataBridge v90.61 SP/FN/VW/TR 변환 전수 강화"
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host ""

$pass = 0
$fail = 0

function Check-Item {
    param([string]$Name, [bool]$Result)
    if ($Result) {
        Write-Host "  [PASS] $Name" -ForegroundColor Green
        $script:pass++
    } else {
        Write-Host "  [FAIL] $Name" -ForegroundColor Red
        $script:fail++
    }
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host "[1/5] 핵심 파일 존재 확인"
# ──────────────────────────────────────────────────────────────────────────
$scp = "$BACKEND_DIR\app\core\schema_conversion_policy.py"
$oe  = "$BACKEND_DIR\app\core\obj_executor.py"
$st  = "$BACKEND_DIR\prompts\mssql_to_mysql\system.txt"
$tp  = "$BACKEND_DIR\tests\test_v90_61_object_conversion.py"

Check-Item "schema_conversion_policy.py" (Test-Path $scp)
Check-Item "obj_executor.py" (Test-Path $oe)
Check-Item "system.txt" (Test-Path $st)
Check-Item "test_v90_61_object_conversion.py" (Test-Path $tp)

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/5] schema_conversion_policy.py — 정규식 5개 변종"
# ──────────────────────────────────────────────────────────────────────────
if (Test-Path $scp) {
    $content = Get-Content $scp -Raw
    Check-Item "v90.61 마커" ($content -match "v90\.61")
    Check-Item "schema-only-backtick 패턴 (`schema`.x)" `
        ($content -match 'rf.*`{schema}`\\\.\(\\w\+\)')
    Check-Item "name-only-backtick 패턴 (schema.``x``)" `
        ($content -match "schema\.\\\`\(\\\\w\+\)\\\`")
    Check-Item "MSSQL 대괄호 패턴 [schema].[x]" `
        ($content -match 'rf.*\[\{schema\}\]\\\.\\\[\(\\w\+\)\\\]')
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/5] obj_executor.py — _extract_obj_name 헬퍼 + 후처리 6종"
# ──────────────────────────────────────────────────────────────────────────
if (Test-Path $oe) {
    $content = Get-Content $oe -Raw
    Check-Item "_extract_obj_name 헬퍼" ($content -match "def _extract_obj_name")
    Check-Item "v90.61 객체명 추출 강화" ($content -match "v90\.61: 객체 이름 추출")
    Check-Item "DATETIME2 → DATETIME(6)" ($content -match "DATETIME2.*DATETIME\(6\)")
    Check-Item "IF...RETURN → IF...THEN RETURN; END IF;" `
        ($content -match "IF \\\\1 THEN RETURN")
    Check-Item "DECLARE 인라인 분리" ($content -match "DECLARE.*= value.*분리")
    Check-Item "문자열 + → CONCAT" ($content -match "_replace_string_concat")
    Check-Item "DATEADD → DATE_ADD" ($content -match "DATE_ADD")
    Check-Item "TVF 경고" ($content -match "TVF.*MySQL 미지원")
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/5] system.txt — 본부장님 41개 케이스 명시"
# ──────────────────────────────────────────────────────────────────────────
if (Test-Path $st) {
    $content = Get-Content $st -Raw
    Check-Item "5대 패턴 명시" ($content -match "5대 패턴")
    Check-Item "패턴 1 (schema 표기)" ($content -match "패턴 1.*스키마")
    Check-Item "본부장님 환경 케이스 (collection_fn_delinq_stage)" `
        ($content -match "collection_fn_delinq_stage")
    Check-Item "패턴 2 (DATETIME2)" ($content -match "DATETIME2.*DATETIME\(6\)")
    Check-Item "패턴 3 (IF...RETURN)" ($content -match "IF.*RETURN.*THEN")
    Check-Item "패턴 4 (DECLARE 인라인)" ($content -match "DECLARE.*인라인")
    Check-Item "패턴 5 (문자열 +)" ($content -match "문자열.*CONCAT")
    Check-Item "체크리스트" ($content -match "체크리스트")
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[5/5] 단위 테스트 — 본부장님 41개 종합 검증"
# ──────────────────────────────────────────────────────────────────────────
foreach ($pf in @($scp, $oe)) {
    if (Test-Path $pf) {
        $rel = $pf.Replace($BACKEND_DIR + "\", "")
        $result = python -c "import ast; ast.parse(open(r'$pf', encoding='utf-8').read()); print('OK')" 2>&1
        Check-Item "ast.parse $rel" ($result -match "OK")
    }
}

Push-Location $BACKEND_DIR
try {
    if (Test-Path "tests\test_v90_61_object_conversion.py") {
        $testResult = python -m pytest tests/test_v90_61_object_conversion.py -v 2>&1
        $passLine = $testResult | Select-String "passed"
        if ($passLine) {
            Write-Host "  [PASS] pytest: $passLine" -ForegroundColor Green
            $script:pass++
            
            $has41 = $testResult | Select-String "test_all_41_objects_normalized.*PASSED"
            $hasPresident = $testResult | Select-String "test_president_full_create_function_normalized.*PASSED"
            $hasDateTime2 = $testResult | Select-String "test_datetime2_converted.*PASSED"
            $hasIfReturn = $testResult | Select-String "test_if_return_converted.*PASSED"
            $hasDeclare = $testResult | Select-String "test_declare_inline_init_converted.*PASSED"
            
            Check-Item "41개 객체 종합 검증" ($null -ne $has41)
            Check-Item "본부장님 fn_delinq_stage 케이스" ($null -ne $hasPresident)
            Check-Item "DATETIME2 변환" ($null -ne $hasDateTime2)
            Check-Item "IF...RETURN 변환" ($null -ne $hasIfReturn)
            Check-Item "DECLARE 인라인 분리" ($null -ne $hasDeclare)
        } else {
            Write-Host "  [FAIL] pytest 실패" -ForegroundColor Red
            $script:fail++
        }
    }
} finally {
    Pop-Location
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host " 검증 완료: PASS $pass / FAIL $fail"
Write-Host "═══════════════════════════════════════════════════════════════"

if ($fail -eq 0) {
    Write-Host ""
    Write-Host "✓ v90.61 패치 정상 적용." -ForegroundColor Green
    Write-Host ""
    Write-Host "  적용 후 동작 확인:"
    Write-Host "  1. FastAPI 재기동 (Ctrl+C → uvicorn)"
    Write-Host "  2. 이관 작업 모니터 → SP/FN/VW/TR 만 재시도"
    Write-Host "     (테이블은 이미 100% 완료됐으니 재이관 불필요)"
    Write-Host "  3. backend.log 에서 1064/1049 오류 안 나오는지 확인"
    Write-Host ""
    Write-Host "  예상 결과:"
    Write-Host "    41개 중 ~36~37개 즉시 통과 (FN/SP/VW)"
    Write-Host "    TVF 4개 (tvf_delinq_ranking, tvf_contract_events,"
    Write-Host "             tvf_daily_trx 등) 는 MySQL 미지원 → 경고 후 PROCEDURE 재작성 필요"
    exit 0
} else {
    Write-Host ""
    Write-Host "✗ 일부 항목 실패." -ForegroundColor Red
    exit 1
}
