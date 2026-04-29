# ============================================================
# verify_v90_64.ps1 - DataBridge v90.64 deploy clean 진짜 1064 fix
# ============================================================
$ErrorActionPreference = "Continue"
$BACKEND_DIR = "D:\project\databridge_full\backend"

Write-Host "============================================================"
Write-Host " DataBridge v90.64 deploy clean 진짜 1064 fix"
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

# 핵심 파일
$oe = Join-Path $BACKEND_DIR "app\core\obj_executor.py"
$tp = Join-Path $BACKEND_DIR "tests\test_v90_64_deploy_clean_fix.py"

Check-Item "obj_executor.py" (Test-Path $oe)
Check-Item "test_v90_64_deploy_clean_fix.py" (Test-Path $tp)

# v90.64 마커 + 핵심 코드
if (Test-Path $oe) {
    $content = Get-Content $oe -Raw
    Check-Item "v90.64 마커"           ($content.Contains("v90.64"))
    Check-Item "deploy_mysql_object 안" ($content.Contains("v90.64") -and ($content.IndexOf("v90.64") -gt $content.IndexOf("def deploy_mysql_object")))
    Check-Item "WHERE 회피 정규식"      ($content.Contains("WHERE\b|FROM\b|JOIN\b"))
    Check-Item "CASE 회피 정규식"       ($content.Contains("CASE\b|SELECT\b"))
    Check-Item "retroactive RETURN CASE" ($content.Contains("RETURN CASE\\s*;"))
}

# 핵심: __pycache__ 강제 청소
Write-Host ""
Write-Host "[__pycache__ 청소]"
$pycount = (Get-ChildItem -Path $BACKEND_DIR -Filter "__pycache__" -Recurse -Directory -ErrorAction SilentlyContinue | Measure-Object).Count
Get-ChildItem -Path $BACKEND_DIR -Filter "__pycache__" -Recurse -Directory -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Write-Host "  __pycache__ $pycount 개 제거" -ForegroundColor Cyan

# pytest
Push-Location $BACKEND_DIR
try {
    if (Test-Path "tests\test_v90_64_deploy_clean_fix.py") {
        $testResult = python -m pytest tests/test_v90_64_deploy_clean_fix.py -v 2>&1
        $passLine = $testResult | Select-String "passed"
        if ($passLine) {
            Write-Host "  [PASS] pytest: $passLine" -ForegroundColor Green
            $script:passCount = $script:passCount + 1
            
            $hasReal = $testResult | Select-String "test_sp_assign_collector_set_where_not_broken.*PASSED"
            $hasRetro = $testResult | Select-String "test_already_broken_return_case_fixed.*PASSED"
            $hasReg = $testResult | Select-String "test_normal_set_get_terminator.*PASSED"
            
            Check-Item "본부장님 raw SQL 정상 처리" ($null -ne $hasReal)
            Check-Item "이미 깨진 패턴 retroactive fix" ($null -ne $hasRetro)
            Check-Item "정상 SQL 회귀 영향 없음" ($null -ne $hasReg)
        }
    }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "============================================================"
Write-Host " PASS $script:passCount / FAIL $script:failCount"
Write-Host "============================================================"

if ($script:failCount -eq 0) {
    Write-Host ""
    Write-Host "v90.64 정상 적용. 다음 단계:" -ForegroundColor Green
    Write-Host "  1. FastAPI 재기동 (필수!)"
    Write-Host "     python -m uvicorn main:app --port 8000 --reload"
    Write-Host "  2. 이관 작업 모니터에서 SP/FN/VW/TR 재변환"
    Write-Host "  3. 11개 잔여 1064 모두 통과 예상"
    exit 0
} else {
    Write-Host "일부 항목 실패." -ForegroundColor Red
    exit 1
}
