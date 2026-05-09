# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p63 ~ v95_p71 슈퍼 마스터 적용 (2026-05-06)
#   본부장님 환경 v95_p63 누락 발견 → 모든 변경 한방에
# ════════════════════════════════════════════════════════════════════
# 본부장님 진단 결과:
#   preflight.py v95_p63: 0 건 (정상 8건)
#   → v95_p63 ZIP 적용 안 됨
#   
# 본부장님 모토 "이번에 끝내자, 토큰 효율" — 슈퍼 마스터 1개로:
#   v95_p62: object_risk_analyzer.py (이미 적용됨, 보강용)
#   v95_p63: preflight.py 통합 (NEW — 이번 적용)
#   v95_p64: JobWizard.vue UI (이미 적용됨, 보강용)
#   v95_p65 ~ p71: 사용자 결정 + 수동 SQL + KB + 차단 (모두 이번에)
#
# 변경 파일 6개:
#   1) frontend/src/pages/JobWizard.vue
#   2) backend/app/api/routes/preflight.py        ⭐ v95_p63 누락 보충
#   3) backend/app/api/routes/sql_validate.py     ⭐ NEW
#   4) backend/app/core/obj_executor.py
#   5) backend/app/engine/object_risk_analyzer.py (보강 — 이미 적용됨)
#   6) backend/main.py
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p63 ~ v95_p71 슈퍼 마스터 적용"
Write-Host "  본부장님 환경 v95_p63 누락 보충 + 5 Phase 통합"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

# 변경 파일 목록
$Files = @(
    @{name='JobWizard.vue';            rel='frontend\src\pages\JobWizard.vue'},
    @{name='preflight.py';             rel='backend\app\api\routes\preflight.py'},
    @{name='sql_validate.py';          rel='backend\app\api\routes\sql_validate.py'},
    @{name='obj_executor.py';          rel='backend\app\core\obj_executor.py'},
    @{name='object_risk_analyzer.py';  rel='backend\app\engine\object_risk_analyzer.py'},
    @{name='main.py';                  rel='backend\main.py'}
)

# 백업
Write-Host "[1/4] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p63_p71_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
foreach ($f in $Files) {
    $full = Join-Path $Root $f.rel
    if (Test-Path $full) {
        Copy-Item $full (Join-Path $BackupDir "$($f.name).bak") -Force
        Write-Host "  ✓ $($f.name)"
    }
}
Write-Host "  ✓ 백업 위치: $BackupDir"

# 데이터 디렉토리
Write-Host ""
Write-Host "[2/4] backend\data 디렉토리 (KB 저장소)" -ForegroundColor Cyan
$DataDir = Join-Path $Root "backend\data"
if (-not (Test-Path $DataDir)) { New-Item -ItemType Directory -Path $DataDir -Force | Out-Null }
Write-Host "  ✓ $DataDir"
Write-Host "    - ai_conversion_cache.json   (v95_p58)"
Write-Host "    - conversion_patterns.json   (v95_p69 자동 생성)"
Write-Host "    - conversion_failures.json   (v95_p70 자동 생성)"

# 검증
Write-Host ""
Write-Host "[3/4] 적용 검증" -ForegroundColor Cyan

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

$Checks = @(
    @{name='preflight.py';            rel='backend\app\api\routes\preflight.py';
      markers=@(
        @{m='v95_p63'; min=5},
        @{m='class ObjectDDL'; min=1},
        @{m='_analyze_object_risk'; min=1},
        @{m='object_ddls'; min=1}
      )},
    @{name='sql_validate.py';         rel='backend\app\api\routes\sql_validate.py';
      markers=@(
        @{m='v95_p67'; min=1},
        @{m='validate_mysql_sql'; min=1}
      )},
    @{name='obj_executor.py';         rel='backend\app\core\obj_executor.py';
      markers=@(
        @{m='v95_p68'; min=5},
        @{m='v95_p69'; min=5},
        @{m='v95_p70'; min=5},
        @{m='user_decision'; min=3},
        @{m='_kb_register_pattern'; min=1},
        @{m='_failure_check'; min=1}
      )},
    @{name='object_risk_analyzer.py'; rel='backend\app\engine\object_risk_analyzer.py';
      markers=@(
        @{m='v95_p62'; min=1},
        @{m='analyze_object_ddl'; min=1}
      )},
    @{name='main.py';                 rel='backend\main.py';
      markers=@(
        @{m='sql_validate'; min=1}
      )},
    @{name='JobWizard.vue';           rel='frontend\src\pages\JobWizard.vue';
      markers=@(
        @{m='v95_p64'; min=3},
        @{m='v95_p65'; min=3},
        @{m='v95_p66'; min=3},
        @{m='manualSqlModal'; min=5},
        @{m='msql-modal-overlay'; min=1},
        @{m='objectDecisions'; min=3}
      )}
)

$allOk = $true
foreach ($c in $Checks) {
    $full = Join-Path $Root $c.rel
    Write-Host ""
    Write-Host "  [$($c.name)]" -ForegroundColor Yellow
    if (-not (Test-Path $full)) {
        Write-Host "    ✗ 파일 없음" -ForegroundColor Red
        $allOk = $false
        continue
    }
    $src = [System.IO.File]::ReadAllText($full, [System.Text.UTF8Encoding]::new($false))
    foreach ($mk in $c.markers) {
        $cnt = [regex]::Matches($src, [regex]::Escape($mk.m)).Count
        $ok = $cnt -ge $mk.min
        if (-not $ok) { $allOk = $false }
        Write-Host ("    [{0}] {1} : {2}건 (min {3})" -f (_Mark $ok), $mk.m, $cnt, $mk.min)
    }
}

# Python 임포트 통합 테스트
Write-Host ""
Write-Host "  [통합 임포트 테스트]" -ForegroundColor Yellow
try {
    Push-Location (Join-Path $Root "backend")
    $testResult = & python -c @"
import sys
sys.path.insert(0, '.')
from app.api.routes.preflight import _analyze_object_risk, ObjectDDL, SelectionInput
from app.api.routes.sql_validate import validate_mysql_sql, ValidateInput
from app.engine.object_risk_analyzer import analyze_object_ddl, PATTERNS_MSSQL_TO_MYSQL
print(f'OK - {len(PATTERNS_MSSQL_TO_MYSQL)} patterns')
"@ 2>&1
    Pop-Location
    if ($testResult -match "OK") {
        Write-Host "    ✓ $testResult"
    } else {
        Write-Host "    ✗ 임포트 실패: $testResult" -ForegroundColor Red
        $allOk = $false
    }
} catch {
    Write-Host "    ⚠ Python 검증 스킵 (수동 확인)"
}

Write-Host ""
if ($allOk) {
    Write-Host "[4/4] ✅ v95_p63~p71 슈퍼 마스터 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "════════════════════════════════════════════════════════"
    Write-Host "  ⚠️ 백엔드 재시작 필수 (Python 메모리 캐시)" -ForegroundColor Yellow
    Write-Host "════════════════════════════════════════════════════════"
    Write-Host ""
    Write-Host "다음 단계:"
    Write-Host ""
    Write-Host "  1) 백엔드 PID 확인:"
    Write-Host '     Get-Process python | Select-Object Id, StartTime'
    Write-Host ""
    Write-Host "  2) 백엔드 종료 + 재시작:"
    Write-Host '     # PID 가 여러개면 모두 종료'
    Write-Host '     Stop-Process -Id <PID1>,<PID2>,<PID3> -Force'
    Write-Host '     cd D:\project\databridge_full\backend; .\start.bat'
    Write-Host ""
    Write-Host "  3) 30초 후 검증:"
    Write-Host '     Start-Sleep -Seconds 5'
    Write-Host "     # 새 시작 흔적 확인"
    Write-Host '     Get-Content "D:\project\databridge_full\backend\logs\databridge_backend.log" -Tail 20'
    Write-Host ""
    Write-Host "  4) Frontend hot-reload 자동 (또는 Ctrl+Shift+R)"
    Write-Host ""
    Write-Host "  5) 위저드 [↻ 새로 시작] → ③ 변환 규칙 단계:"
    Write-Host "     - vProductModelInstructions / vJobCandidateEducation 선택 후"
    Write-Host "     - 빨간 배너 펼침 → ⚠️ object_risk 카테고리 카드 보임 ✅"
    Write-Host "     - 카드 클릭 → 우측 신뢰도 5% + 검출 패턴 + 3-옵션 버튼"
    Write-Host "     - [✍️ 수동 SQL 작성] 또는 [⊘ 이관 제외] 클릭"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Get-ChildItem '$BackupDir' | ForEach-Object {"
    Write-Host '    $rel = $_.Name -replace "\.bak$", ""'
    Write-Host "    # 적절한 자리로 복사"
    Write-Host "  }"
} else {
    Write-Host "[4/4] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백: $BackupDir"
    exit 2
}
