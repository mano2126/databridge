# ═══════════════════════════════════════════════════════════════════════════
# verify_v90_53.ps1 — DataBridge v90.53 KeyError 근본 해결 검증
# ═══════════════════════════════════════════════════════════════════════════
# v90.48 hotfix 부작용 — _skip_cols_map[table] 등 dict 키 등록 위치 오류로
# 정규화된 이름 (customer_profile / settlement_eft_batch 등) 으로 접근 시 KeyError.
# v90.53 에서 키 등록 위치를 swap 후로 이동하여 근본 해결.
# 
# 본부장님 환경 5건 (eft_batch / org_unit / credit_score / kyc_document / profile)
# 모두 동일 패턴. 검증 후 반드시 모든 케이스 PASS 되어야 함.
# ═══════════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$BACKEND_DIR = "D:\project\databridge_full\backend"

Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host " DataBridge v90.53 Migration Engine KeyError 근본 해결 검증"
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
Write-Host "[1/4] 핵심 파일 존재 확인"
# ──────────────────────────────────────────────────────────────────────────
$files = @(
    "$BACKEND_DIR\app\engine\migration_engine.py",
    "$BACKEND_DIR\tests\test_migrate_table_dict_keys_v90_53.py"
)
foreach ($f in $files) {
    Check-Item $f.Substring($BACKEND_DIR.Length + 1) (Test-Path $f)
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/4] migration_engine.py v90.53 패치 마커 확인"
# ──────────────────────────────────────────────────────────────────────────
$me = "$BACKEND_DIR\app\engine\migration_engine.py"
if (Test-Path $me) {
    $content = Get-Content $me -Raw
    
    # v90.53 마커 존재 확인
    Check-Item "v90.53 주석 마커" ($content -match "v90\.53.*KeyError 근본 해결")
    
    # 키 등록이 swap 후에 있는지 (dict 자체 보장 → swap → 키 등록 순서)
    # 'src_bare = table' 다음에 '_skip_cols_map[table] = set()' 가 와야 함
    $hasCorrectOrder = $content -match "src_bare = table[\s\S]{0,2000}table = tgt_table[\s\S]{0,500}_skip_cols_map\[table\] = set\(\)"
    Check-Item "swap 후 키 등록 순서 (src_bare = table → swap → _skip_cols_map[table] = set())" $hasCorrectOrder
    
    # src_bare 이중 등록 (안전망)
    Check-Item "src_bare alias 이중 등록 (안전망)" ($content -match "_skip_cols_map\[src_bare\] = self\._skip_cols_map\[table\]")
} else {
    Check-Item "migration_engine.py" $false "(파일 없음)"
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/4] Python 구문 검증"
# ──────────────────────────────────────────────────────────────────────────
if (Test-Path $me) {
    $result = python -c "import ast; ast.parse(open(r'$me', encoding='utf-8').read()); print('OK')" 2>&1
    Check-Item "ast.parse migration_engine.py" ($result -match "OK")
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/4] 단위 테스트 (pytest) — 본부장님 환경 5건 검증"
# ──────────────────────────────────────────────────────────────────────────
Push-Location $BACKEND_DIR
try {
    $testResult = python -m pytest tests/test_migrate_table_dict_keys_v90_53.py -v 2>&1
    $passLine = $testResult | Select-String "passed"
    if ($passLine) {
        Write-Host "  [PASS] pytest: $passLine" -ForegroundColor Green
        $script:pass++
        # 본부장님 환경 5건 케이스 정확히 검증됐는지
        $presidentCases = $testResult | Select-String "test_v53_no_keyerror_on_target_name.*(eft_batch|org_unit|credit_score|kyc_document|profile).*PASSED"
        if ($presidentCases.Count -ge 5) {
            Write-Host "  [PASS] 본부장님 환경 5건 모두 PASS" -ForegroundColor Green
            $script:pass++
        } else {
            Write-Host "  [FAIL] 본부장님 환경 5건 중 일부 미통과 ($($presidentCases.Count)/5)" -ForegroundColor Red
            $script:fail++
        }
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
    Write-Host "✓ v90.53 패치 정상 적용. FastAPI 재기동 후 재이관 테스트 진행하세요." -ForegroundColor Green
    Write-Host ""
    Write-Host "  다음 검증 단계:"
    Write-Host "  1. FastAPI 재기동"
    Write-Host "  2. 본부장님 환경 5건 테이블 (eft_batch / org_unit / credit_score /"
    Write-Host "     kyc_document / profile) 중 1~2건 재이관 시도"
    Write-Host "  3. 'KeyError: customer_xxx' 가 더 이상 안 나오는지 확인"
    exit 0
} else {
    Write-Host ""
    Write-Host "✗ 일부 항목 실패. 위 로그 확인 후 수동 점검 필요." -ForegroundColor Red
    exit 1
}
