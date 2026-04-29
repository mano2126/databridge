# ═══════════════════════════════════════════════════════════════════════════
# verify_v90_58.ps1 — DataBridge v90.58 hotfix
# ═══════════════════════════════════════════════════════════════════════════
# 본부장님 환경 KeyError 재발 (org_unit → ref_org_unit, eft_batch → settlement_eft_batch)
# 의 진짜 원인: v90.54 ZIP 작성 시 v90.53 fix 가 누락된 채로 ZIP 됐음.
# v90.54 적용 시 v90.53 fix 깨끗이 덮어씌워져 KeyError 재발.
#
# v90.58 hotfix:
#   v90.53 정상본 + v90.54 _ensure_terminator fix 합본
#   = migration_engine.py 한 파일 교체
# ═══════════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"

Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host " DataBridge v90.58 hotfix — v90.53 + v90.54 합본"
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
Write-Host "[1/3] migration_engine.py 패치 적용"
# ──────────────────────────────────────────────────────────────────────────
$me = "$BACKEND_DIR\app\engine\migration_engine.py"
Check-Item "migration_engine.py 존재" (Test-Path $me)

if (Test-Path $me) {
    $content = Get-Content $me -Raw
    
    # v90.53 fix
    Check-Item "v90.53 KeyError fix 주석" ($content -match "v90\.53.*KeyError")
    Check-Item "v90.53 src_bare = table (swap)" ($content -match "src_bare = table")
    Check-Item "v90.53 swap 후 dict 키 등록" `
        ($content -match "v90\.53.*키 등록.*swap 후")
    Check-Item "v90.53 src_bare alias 이중 등록" `
        ($content -match "_skip_cols_map\[src_bare\]\s*=\s*self\._skip_cols_map\[table\]")
    
    # v90.54 fix
    Check-Item "v90.54 _ensure_terminator 함수" ($content -match "def _ensure_terminator")
    Check-Item "v90.54 full_ddl 주석" ($content -match "v90\.54.*full_ddl")
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/3] Python 구문 + 단위 테스트"
# ──────────────────────────────────────────────────────────────────────────
if (Test-Path $me) {
    $result = python -c "import ast; ast.parse(open(r'$me', encoding='utf-8').read()); print('OK')" 2>&1
    Check-Item "ast.parse migration_engine.py" ($result -match "OK")
}

Push-Location $BACKEND_DIR
try {
    if (Test-Path "tests\test_v90_58_hotfix_combined.py") {
        $testResult = python -m pytest tests/test_v90_58_hotfix_combined.py -v 2>&1
        $passLine = $testResult | Select-String "passed"
        if ($passLine) {
            Write-Host "  [PASS] pytest: $passLine" -ForegroundColor Green
            $script:pass++
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
Write-Host "[3/3] Python 모듈 캐시 정리 (옛날 .pyc 가 로드되지 않도록)"
# ──────────────────────────────────────────────────────────────────────────
Push-Location $BACKEND_DIR
try {
    Get-ChildItem -Path . -Filter "__pycache__" -Recurse -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  [OK] __pycache__ 디렉토리 정리 완료" -ForegroundColor Green
    $script:pass++
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
    Write-Host "✓ v90.58 hotfix 정상 적용." -ForegroundColor Green
    Write-Host ""
    Write-Host "  다음 단계:"
    Write-Host "  1. FastAPI 재기동 (Ctrl+C → python -m uvicorn main:app --port 8000 --reload)"
    Write-Host "  2. 재이관 진행"
    Write-Host "  3. backend.log 에서 다음 패턴이 더 이상 안 나오는지 확인:"
    Write-Host "     '오류: ref_org_unit'"
    Write-Host "     '오류: settlement_eft_batch'"
    Write-Host "     '오류: customer_xxx'"
    exit 0
} else {
    Write-Host ""
    Write-Host "✗ 일부 실패." -ForegroundColor Red
    exit 1
}
