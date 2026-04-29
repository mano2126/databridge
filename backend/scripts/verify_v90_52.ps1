# ═══════════════════════════════════════════════════════════════════════════
# verify_v90_52.ps1 — DataBridge v90.52 패치 검증 스크립트
# ═══════════════════════════════════════════════════════════════════════════
# 본부장님 환경 18건 1064 패턴 → preflight_validator 강화 + 안전망 이중화 검증.
# ZIP 추출 후 D:\project\databridge_full\backend\scripts\ 위치에서 실행.
# 
# 실행: powershell -ExecutionPolicy Bypass -File verify_v90_52.ps1
# ═══════════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$BACKEND_DIR = "D:\project\databridge_full\backend"

Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host " DataBridge v90.52 Preflight 강화 패치 검증"
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host ""

$pass = 0
$fail = 0

function Check-Item {
    param([string]$Name, [bool]$Result, [string]$Detail = "")
    $script:total++
    if ($Result) {
        Write-Host "  [PASS] $Name $Detail" -ForegroundColor Green
        $script:pass++
    } else {
        Write-Host "  [FAIL] $Name $Detail" -ForegroundColor Red
        $script:fail++
    }
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host "[1/6] 핵심 파일 존재 확인"
# ──────────────────────────────────────────────────────────────────────────
$files = @(
    "$BACKEND_DIR\app\core\sql_preflight_validator.py",
    "$BACKEND_DIR\app\core\preflight_kb_learner.py",
    "$BACKEND_DIR\app\core\obj_executor.py",
    "$BACKEND_DIR\app\api\routes\schema.py",
    "$BACKEND_DIR\prompts\mssql_to_mysql\error_cases.txt",
    "$BACKEND_DIR\prompts\mssql_to_mysql\auto_learned_rules.json",
    "$BACKEND_DIR\tests\test_sql_preflight_validator_v90_52.py"
)
foreach ($f in $files) {
    Check-Item $f.Substring($BACKEND_DIR.Length + 1) (Test-Path $f)
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/6] 룰 R-01 ~ R-10 등록 확인"
# ──────────────────────────────────────────────────────────────────────────
$validator = "$BACKEND_DIR\app\core\sql_preflight_validator.py"
if (Test-Path $validator) {
    $content = Get-Content $validator -Raw
    foreach ($rule in @("R-01", "R-02", "R-03", "R-04", "R-05", "R-06", "R-07", "R-08", "R-09", "R-10")) {
        Check-Item "rule $rule" ($content -match "\b$rule\b")
    }
} else {
    Check-Item "rules" $false "(validator 파일 없음)"
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/6] schema.py 13-1 ~ 13-9 진단 로그 확인"
# ──────────────────────────────────────────────────────────────────────────
$schema = "$BACKEND_DIR\app\api\routes\schema.py"
if (Test-Path $schema) {
    $sc = Get-Content $schema -Raw
    foreach ($trace in @("13-1-import-enter", "13-2-import-done", "13-3-rule-apply-enter",
                          "13-4-rule-apply-done", "13-5-all-done", "13-9-fallback-exception")) {
        Check-Item "trace $trace" ($sc -match [regex]::Escape($trace))
    }
} else {
    Check-Item "schema traces" $false "(schema.py 없음)"
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/6] obj_executor.py 안전망 2차 호출 확인"
# ──────────────────────────────────────────────────────────────────────────
$executor = "$BACKEND_DIR\app\core\obj_executor.py"
if (Test-Path $executor) {
    $ex = Get-Content $executor -Raw
    Check-Item "E4-preflight-2nd-fixed marker" ($ex -match "E4-preflight-2nd-fixed")
    Check-Item "E4-preflight-2nd-clean marker" ($ex -match "E4-preflight-2nd-clean")
    Check-Item "안전망 2차 import" ($ex -match "preflight_check as _pfc2")
} else {
    Check-Item "executor markers" $false "(obj_executor.py 없음)"
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[5/6] Python 구문 검증 (ast.parse)"
# ──────────────────────────────────────────────────────────────────────────
$pyFiles = @(
    "$BACKEND_DIR\app\core\sql_preflight_validator.py",
    "$BACKEND_DIR\app\core\preflight_kb_learner.py",
    "$BACKEND_DIR\app\core\obj_executor.py",
    "$BACKEND_DIR\app\api\routes\schema.py"
)
foreach ($pf in $pyFiles) {
    if (Test-Path $pf) {
        $result = python -c "import ast; ast.parse(open(r'$pf', encoding='utf-8').read()); print('OK')" 2>&1
        Check-Item "ast.parse $($pf.Substring($BACKEND_DIR.Length + 1))" ($result -match "OK")
    }
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[6/6] 단위 테스트 실행 (pytest)"
# ──────────────────────────────────────────────────────────────────────────
Push-Location $BACKEND_DIR
try {
    $testResult = python -m pytest tests/test_sql_preflight_validator_v90_52.py -v 2>&1
    $passLine = $testResult | Select-String "passed"
    if ($passLine) {
        Write-Host "  [PASS] pytest: $passLine" -ForegroundColor Green
        $pass++
    } else {
        Write-Host "  [FAIL] pytest 실행 실패" -ForegroundColor Red
        Write-Host $testResult
        $fail++
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
    Write-Host "✓ v90.52 패치 정상 적용 확인. FastAPI 재기동 후 테스트하세요." -ForegroundColor Green
    Write-Host "  Ctrl+C 로 backend 종료 → python -m uvicorn app.main:app --reload --port 8000"
    exit 0
} else {
    Write-Host ""
    Write-Host "✗ 일부 항목 실패. 위 로그 확인 후 수동 점검 필요." -ForegroundColor Red
    exit 1
}
