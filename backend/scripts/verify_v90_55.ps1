# ═══════════════════════════════════════════════════════════════════════════
# verify_v90_55.ps1 — DataBridge v90.55 검증 화면 활성 Job 자동 연결
# ═══════════════════════════════════════════════════════════════════════════
# v90.15 의 effective 패턴(이관 작업 모니터)을 검증 화면에도 적용.
# 활성 Job 발견 시 connector store 자동 채움 + backend 가 password 자동 복원.
#
# 변경 파일:
#   Backend:
#     - app/core/password_resolver.py     (job_id 파라미터 + _load_from_job_by_id)
#     - app/api/routes/connector.py        (/test 가 job_id 받음 + /from-job/{id})
#     - app/api/routes/schema.py           (/tables 가 job_id 받음)
#     - app/api/routes/validate.py         (/run, /run/stream 가 job_id 받음)
#   Frontend:
#     - frontend/src/store/connectorStore.js  (loadedJobId + applyJobAsConnection)
#     - frontend/src/pages/Validate.vue       (effective 패턴 + 자동 적용)
# ═══════════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$BACKEND_DIR  = "D:\project\databridge_full\backend"
$FRONTEND_DIR = "D:\project\databridge_full\frontend"

Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host " DataBridge v90.55 검증 화면 활성 Job 자동 연결 검증"
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
Write-Host "[1/6] 핵심 파일 존재 확인"
# ──────────────────────────────────────────────────────────────────────────
$files = @(
    "$BACKEND_DIR\app\core\password_resolver.py",
    "$BACKEND_DIR\app\api\routes\connector.py",
    "$BACKEND_DIR\app\api\routes\schema.py",
    "$BACKEND_DIR\app\api\routes\validate.py",
    "$FRONTEND_DIR\src\store\connectorStore.js",
    "$FRONTEND_DIR\src\pages\Validate.vue"
)
foreach ($f in $files) {
    $rel = $f.Replace("D:\project\databridge_full\", "")
    Check-Item $rel (Test-Path $f)
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/6] Backend - password_resolver.py 마커"
# ──────────────────────────────────────────────────────────────────────────
$pr = "$BACKEND_DIR\app\core\password_resolver.py"
if (Test-Path $pr) {
    $content = Get-Content $pr -Raw
    Check-Item "v90.55 신규 마커" ($content -match "v90\.55 신규.*Job ID")
    Check-Item "_load_from_job_by_id 함수" ($content -match "def _load_from_job_by_id")
    Check-Item "resolve_password 의 job_id 파라미터" ($content -match "job_id: Optional\[str\]")
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/6] Backend - connector.py /from-job 마커"
# ──────────────────────────────────────────────────────────────────────────
$conn = "$BACKEND_DIR\app\api\routes\connector.py"
if (Test-Path $conn) {
    $content = Get-Content $conn -Raw
    Check-Item "/from-job/{job_id} endpoint" ($content -match "from-job/\{job_id\}")
    Check-Item "v90.55 주석" ($content -match "v90\.55 신규")
    Check-Item "/test 가 job_id 받음" ($content -match "job_id=body\.get\(`"job_id`"\)")
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/6] Backend - schema.py 와 validate.py job_id 지원"
# ──────────────────────────────────────────────────────────────────────────
$schema = "$BACKEND_DIR\app\api\routes\schema.py"
if (Test-Path $schema) {
    $content = Get-Content $schema -Raw
    Check-Item "schema /tables job_id query param" ($content -match 'job_id: str = ""')
}

$valid = "$BACKEND_DIR\app\api\routes\validate.py"
if (Test-Path $valid) {
    $content = Get-Content $valid -Raw
    Check-Item "validate /run 의 job_id 처리" ($content -match "v90\.55: job_id 가 들어오면")
    Check-Item "validate /run/stream 의 job_id 처리" ($content -match "v90\.55: job_id 로 password 자동 복원")
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[5/6] Frontend - connectorStore.js + Validate.vue 마커"
# ──────────────────────────────────────────────────────────────────────────
$cstore = "$FRONTEND_DIR\src\store\connectorStore.js"
if (Test-Path $cstore) {
    $content = Get-Content $cstore -Raw
    Check-Item "loadedJobId state" ($content -match "loadedJobId:\s+null")
    Check-Item "applyJobAsConnection action" ($content -match "applyJobAsConnection\(job\)")
    Check-Item "testConn 의 job_id payload" ($content -match "payload\.job_id = this\.loadedJobId")
}

$vp = "$FRONTEND_DIR\src\pages\Validate.vue"
if (Test-Path $vp) {
    $content = Get-Content $vp -Raw
    Check-Item "isEffectivelyConnected computed" ($content -match "isEffectivelyConnected = computed")
    Check-Item "effectiveSrcDb computed" ($content -match "effectiveSrcDb = computed")
    Check-Item "effectiveTgtDb computed" ($content -match "effectiveTgtDb = computed")
    Check-Item "v90.55 자동 적용 로직" ($content -match "v90\.55: 활성 Job 발견 시")
    Check-Item "loadTables job_id 전달" ($content -match "connector\.loadedJobId \? \{ job_id")
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[6/6] Python 구문 검증"
# ──────────────────────────────────────────────────────────────────────────
foreach ($pf in @($pr, $conn, $schema, $valid)) {
    if (Test-Path $pf) {
        $rel = $pf.Replace($BACKEND_DIR + "\", "")
        $result = python -c "import ast; ast.parse(open(r'$pf', encoding='utf-8').read()); print('OK')" 2>&1
        Check-Item "ast.parse $rel" ($result -match "OK")
    }
}

# ──────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host " 검증 완료: PASS $pass / FAIL $fail"
Write-Host "═══════════════════════════════════════════════════════════════"

if ($fail -eq 0) {
    Write-Host ""
    Write-Host "✓ v90.55 패치 정상 적용." -ForegroundColor Green
    Write-Host ""
    Write-Host "  적용 후 동작 확인:"
    Write-Host "  1. FastAPI 재기동 (Ctrl+C → python -m uvicorn main:app --port 8000 --reload)"
    Write-Host "  2. Frontend 재시작 (npm run dev) — Vite 캐시 무시 새로고침 (Ctrl+Shift+R)"
    Write-Host "  3. 이관 진행 중인 상태에서 /validate/tables 진입"
    Write-Host "  4. ⚠ 'DB 연결이 필요합니다' 경고 사라지고 이관 모니터처럼 헤더 카드 표시"
    Write-Host "  5. 테이블 목록 자동 로드 (활성 Job 의 src/tgt 사용)"
    Write-Host "  6. backend.log 마커 확인:"
    Write-Host "     - DEBUG tables c={...} ← password 가 *** 로 마스킹된 형태 (resolve 정상)"
    Write-Host "     - 'password 해결: job_id=... side=... → 성공' (DEBUG 레벨)"
    exit 0
} else {
    Write-Host ""
    Write-Host "✗ 일부 항목 실패." -ForegroundColor Red
    exit 1
}
