# ═══════════════════════════════════════════════════════════════════════════
# verify_v90_54.ps1 — DataBridge v90.54 3건 케이스 검증
# ═══════════════════════════════════════════════════════════════════════════
# v90.52 적용 후에도 발생한 3건 케이스 외과수술:
#   1) sql_post_processor R-010 정규식 정밀화 (END; 손상 방지)
#   2) obj_executor TVF placeholder DROP 자동 보강 (1304 방지)
#   3) migration_engine full_ddl join 시 ; 보장 ("CREATE 0개" 방지)
# ═══════════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$BACKEND_DIR = "D:\project\databridge_full\backend"

Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host " DataBridge v90.54 3건 케이스 외과수술 검증"
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host ""

$pass = 0
$fail = 0

function Check-Item {
    param([string]$Name, [bool]$Result, [string]$Detail = "")
    if ($Result) {
        Write-Host "  [PASS] $Name $Detail" -ForegroundColor Green
        $script:pass++
    } else {
        Write-Host "  [FAIL] $Name $Detail" -ForegroundColor Red
        $script:fail++
    }
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host "[1/5] 핵심 파일 존재 확인"
# ──────────────────────────────────────────────────────────────────────────
$files = @(
    "$BACKEND_DIR\app\core\sql_post_processor.py",
    "$BACKEND_DIR\app\core\obj_executor.py",
    "$BACKEND_DIR\app\engine\migration_engine.py",
    "$BACKEND_DIR\tests\test_v90_54_three_cases.py"
)
foreach ($f in $files) {
    Check-Item $f.Substring($BACKEND_DIR.Length + 1) (Test-Path $f)
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/5] 케이스 1 — R-010 정규식 정밀화 마커"
# ──────────────────────────────────────────────────────────────────────────
$pp = "$BACKEND_DIR\app\core\sql_post_processor.py"
if (Test-Path $pp) {
    $content = Get-Content $pp -Raw
    Check-Item "v90.54 정밀화 주석" ($content -match "v90\.54 변경.*\[\^;\]\+ → \[\^;\\\\n\]\+")
    Check-Item "정밀화 정규식 (줄바꿈 차단)" ($content -match '\[\^;\\n\]\+')
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/5] 케이스 2 — TVF placeholder DROP 자동 보강 마커"
# ──────────────────────────────────────────────────────────────────────────
$oe = "$BACKEND_DIR\app\core\obj_executor.py"
if (Test-Path $oe) {
    $content = Get-Content $oe -Raw
    Check-Item "v90.54 DROP 보강 주석" ($content -match "v90\.54.*CREATE 마다 대응 DROP 자동 보강")
    Check-Item "_not_supported 변종 처리" ($content -match "_not_supported")
    Check-Item "04b-drops-augmented 트레이스" ($content -match "04b-drops-augmented")
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/5] 케이스 3 — full_ddl 세미콜론 보장 마커"
# ──────────────────────────────────────────────────────────────────────────
$me = "$BACKEND_DIR\app\engine\migration_engine.py"
if (Test-Path $me) {
    $content = Get-Content $me -Raw
    Check-Item "v90.54 ; 보장 주석" ($content -match "v90\.54.*full_ddl 합치기")
    Check-Item "_ensure_terminator 헬퍼" ($content -match "_ensure_terminator")
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[5/5] Python 구문 + 단위 테스트"
# ──────────────────────────────────────────────────────────────────────────
foreach ($pf in @($pp, $oe, $me)) {
    if (Test-Path $pf) {
        $result = python -c "import ast; ast.parse(open(r'$pf', encoding='utf-8').read()); print('OK')" 2>&1
        Check-Item "ast.parse $($pf.Substring($BACKEND_DIR.Length + 1))" ($result -match "OK")
    }
}

Push-Location $BACKEND_DIR
try {
    $testResult = python -m pytest tests/test_v90_54_three_cases.py -v 2>&1
    $passLine = $testResult | Select-String "passed"
    if ($passLine) {
        Write-Host "  [PASS] pytest: $passLine" -ForegroundColor Green
        $script:pass++
    } else {
        Write-Host "  [FAIL] pytest 실행 실패" -ForegroundColor Red
        Write-Host $testResult
        $script:fail++
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
    Write-Host "✓ v90.54 패치 정상 적용. FastAPI 재기동 후 테스트하세요." -ForegroundColor Green
    Write-Host ""
    Write-Host "  다음 검증 단계:"
    Write-Host "  1. FastAPI 재기동 (Ctrl+C → python -m uvicorn main:app --port 8000 --reload)"
    Write-Host "  2. 본부장님 환경 3건 (fn_delinq_stage / tvf_daily_trx / sp_calculate_schedule) 재이관"
    Write-Host "  3. 로그에서 다음 마커 확인:"
    Write-Host "     - [v90.54: CREATE 대응 DROP 자동 보강 N개]    ← 케이스 2 동작"
    Write-Host "     - DEPLOY-TRACE 03-split-done stmt_count=4    ← 케이스 3 동작 (1 → 4)"
    Write-Host "     - END; 보존 (1064 'END' at line N 사라짐)     ← 케이스 1 동작"
    exit 0
} else {
    Write-Host ""
    Write-Host "✗ 일부 항목 실패." -ForegroundColor Red
    exit 1
}
