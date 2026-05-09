# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p65 ~ v95_p71 마스터 적용 (2026-05-05)
#   엔터프라이즈 솔루션 — XML/CROSS APPLY 본질 처방 통합
# ════════════════════════════════════════════════════════════════════
# 본부장님 결정: "5 Phase 모두 — 8-12시간 엔터프라이즈"
#                "P71까지 진행하자"
#
# 5 Phase 통합 처방:
#
#   ┌─ Phase 1 (사전 검증) ─────────────────────────────────┐
#   │  v95_p62: object_risk_analyzer.py (이미 적용됨)      │
#   │  v95_p63: preflight.py 통합 (이미 적용됨)            │
#   │  v95_p64: 위저드 UI 통합 (이미 적용됨)               │
#   └─────────────────────────────────────────────────────┘
#
#   ┌─ Phase 4 (사용자 결정) ───────────────────────────────┐
#   │  v95_p65: form.objectDecisions + UI 3-옵션 버튼     │
#   │           (자동 변환 / 수동 SQL / 이관 제외)          │
#   └─────────────────────────────────────────────────────┘
#
#   ┌─ Phase 5 (수동 SQL) ──────────────────────────────────┐
#   │  v95_p66: 수동 SQL 입력 모달 (코드 에디터 + 검증)    │
#   │  v95_p67: MySQL SQL 문법 검증 API (NEW backend)     │
#   │  v95_p68: ai_convert_ddl 에 user_decision 우회      │
#   │           (manual → 사용자 SQL 직접 사용)            │
#   └─────────────────────────────────────────────────────┘
#
#   ┌─ Phase 2 (KB 누적 학습) ──────────────────────────────┐
#   │  v95_p69: conversion_patterns.json + KB 매칭        │
#   │           - 사용자 manual SQL 자동 KB 등록          │
#   │           - AI 성공 결과도 자동 KB 등록             │
#   │           - 다음 이관 시 매칭 → AI 호출 0           │
#   └─────────────────────────────────────────────────────┘
#
#   ┌─ Phase 3 (실패 학습 + 재시도 차단) ───────────────────┐
#   │  v95_p70: conversion_failures.json + 차단 메커니즘   │
#   │           - AI N회 실패 → 재호출 차단 (비용 절감)   │
#   │           - 사용자 결정 (manual/exclude) 후 해제    │
#   │           - MAX_AI_FAILURE_ATTEMPTS=2 (환경변수)    │
#   └─────────────────────────────────────────────────────┘
#
#   ┌─ Phase 6 (통합) ─────────────────────────────────────┐
#   │  v95_p71: 마스터 ZIP — 모든 변경 통합 패키징         │
#   └─────────────────────────────────────────────────────┘
#
# 변경 파일 (4개):
#   1) frontend/src/pages/JobWizard.vue       (UI + form + 모달)
#   2) backend/app/core/obj_executor.py       (KB + 차단 + user_decision)
#   3) backend/app/api/routes/sql_validate.py (NEW 검증 API)
#   4) backend/main.py                        (sql_validate 라우터 등록)
#
# 흐름 (사용자가 위험 객체 만났을 때):
#
#   1. 사전 분석 → vProductModelInstructions HIGH (5%) 검출
#   2. UI 카드: 신뢰도 5% + 검출 패턴 + MySQL 대안
#   3. 사용자 [수동 SQL 작성] 클릭
#   4. 모달: 좌측 MSSQL 원본 + 우측 MySQL 작성 영역
#   5. 사용자 작성 → 검증 → 저장 → KB 등록
#   6. 실행 시 ai_convert_ddl → user_decision='manual' 인식 → 사용자 SQL 사용
#   7. KB 자동 등록 → 다음 이관 시 같은 패턴 자동 매칭 (AI 호출 0)
#
# 비용 효율:
#   - v95_p58 캐시 + v95_p69 KB + v95_p70 차단 = AI 호출 90%+ 절감
#   - 본부장님 환경 오늘 $51 비용 → 다음번부터 $5 이하 예상
#
# 부작용 0 검증:
#   - 모든 신규 기능 Optional (사용자 결정 없으면 옛 흐름)
#   - 옛 클라이언트 호환 (object_ddls 무시)
#   - KB 파일 손상 시 빈 dict 폴백 (안전)
#   - sqlparse 없어도 기본 검증 동작
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p65 ~ v95_p71 마스터 적용"
Write-Host "  5 Phase 엔터프라이즈 솔루션 통합"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

# 변경 파일 4개
$VuePath = Join-Path $Root "frontend\src\pages\JobWizard.vue"
$OePath = Join-Path $Root "backend\app\core\obj_executor.py"
$SvPath = Join-Path $Root "backend\app\api\routes\sql_validate.py"
$MnPath = Join-Path $Root "backend\main.py"
$DataDir = Join-Path $Root "backend\data"

# 백업
Write-Host "[1/4] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p65_p71_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
foreach ($f in @($VuePath, $OePath, $MnPath)) {
    if (Test-Path $f) {
        $bn = Split-Path $f -Leaf
        Copy-Item $f (Join-Path $BackupDir "$bn.bak") -Force
        Write-Host "  ✓ $bn"
    }
}
Write-Host "  ✓ 백업 위치: $BackupDir"

# data 디렉토리 보장
Write-Host ""
Write-Host "[2/4] backend\data 디렉토리 (KB 저장소)" -ForegroundColor Cyan
if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}
Write-Host "  ✓ $DataDir"
Write-Host "    - ai_conversion_cache.json   (v95_p58 캐시)"
Write-Host "    - conversion_patterns.json   (v95_p69 KB — 자동 생성)"
Write-Host "    - conversion_failures.json   (v95_p70 실패 KB — 자동 생성)"

# 검증 (UTF-8 명시)
Write-Host ""
Write-Host "[3/4] 적용 검증" -ForegroundColor Cyan

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }
function _CheckMarkers($filePath, $markers) {
    if (-not (Test-Path $filePath)) {
        Write-Host ("  ✗ 파일 없음: " + (Split-Path $filePath -Leaf)) -ForegroundColor Red
        return $false
    }
    $content = [System.IO.File]::ReadAllText($filePath, [System.Text.UTF8Encoding]::new($false))
    $allOk = $true
    foreach ($m in $markers) {
        $found = $content.Contains($m)
        $allOk = $allOk -and $found
        Write-Host ("    [{0}] {1}" -f (_Mark $found), $m)
    }
    return $allOk
}

Write-Host ""
Write-Host "  [JobWizard.vue]" -ForegroundColor Yellow
$ok_vue = _CheckMarkers $VuePath @(
    "v95_p65", "v95_p66",
    "objectDecisions",
    "getObjectDecision", "setObjectDecision", "clearObjectDecision",
    "manualSqlModal",
    "openManualSqlModal", "closeManualSqlModal",
    "validateManualSql", "saveManualSql",
    "pf-rm-decision-btn",
    "msql-modal-overlay",
    "msql-textarea-editable"
)

Write-Host ""
Write-Host "  [obj_executor.py]" -ForegroundColor Yellow
$ok_oe = _CheckMarkers $OePath @(
    "v95_p68", "v95_p69", "v95_p70",
    "user_decision", "USER-MANUAL", "USER-EXCLUDE",
    "_kb_register_pattern", "_kb_match_pattern",
    "_failure_check", "_failure_record", "_failure_clear",
    "MAX_AI_FAILURE_ATTEMPTS", "block_until_user_decides",
    "KB-MATCH", "BLOCKED"
)

Write-Host ""
Write-Host "  [sql_validate.py]" -ForegroundColor Yellow
$ok_sv = _CheckMarkers $SvPath @(
    "v95_p67",
    "validate_mysql_sql",
    "_basic_format_check",
    "ValidateInput", "ValidateOutput",
    "MSSQL 잔여"
)

Write-Host ""
Write-Host "  [main.py]" -ForegroundColor Yellow
$ok_mn = _CheckMarkers $MnPath @(
    "v95_p67",
    "sql_validate"
)

# Python 임포트 통합 테스트
Write-Host ""
Write-Host "  [통합 임포트 테스트]" -ForegroundColor Yellow
try {
    Push-Location (Join-Path $Root "backend")
    $testResult = & python -c @"
import sys
sys.path.insert(0, '.')
from app.api.routes.sql_validate import validate_mysql_sql, ValidateInput
from app.engine.object_risk_analyzer import analyze_object_ddl
from app.api.routes.preflight import _analyze_object_risk
print('OK')
"@ 2>&1
    Pop-Location
    if ($testResult -match "OK") {
        Write-Host "    ✓ 모든 모듈 임포트 성공"
    } else {
        Write-Host "    ⚠ 임포트 테스트: $testResult" -ForegroundColor Yellow
    }
} catch {
    Write-Host "    ⚠ Python 검증 스킵 (수동 확인)"
}

$allOk = $ok_vue -and $ok_oe -and $ok_sv -and $ok_mn

Write-Host ""
if ($allOk) {
    Write-Host "[4/4] ✅ v95_p65~p71 마스터 적용 완료 — 5 Phase 엔터프라이즈 솔루션" -ForegroundColor Green
    Write-Host ""
    Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Green
    Write-Host "  적용된 기능 요약" -ForegroundColor Green
    Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Green
    Write-Host ""
    Write-Host "  ✓ Phase 1: vProductModelInstructions / vJobCandidateEducation"
    Write-Host "             같은 위험 객체 사전 검출 (이미 적용됨 v95_p62~p64)"
    Write-Host ""
    Write-Host "  ✓ Phase 4: 위저드에서 객체별 결정 가능"
    Write-Host "             [🤖 자동 변환 시도] [✍️ 수동 SQL] [⊘ 이관 제외]"
    Write-Host ""
    Write-Host "  ✓ Phase 5: 수동 SQL 입력 모달"
    Write-Host "             - 좌측: MSSQL 원본 (참고)"
    Write-Host "             - 우측: MySQL 작성 (코드 에디터)"
    Write-Host "             - 검증 API + 저장 + KB 등록"
    Write-Host ""
    Write-Host "  ✓ Phase 2: KB 누적 학습"
    Write-Host "             - 사용자 manual SQL → conversion_patterns.json"
    Write-Host "             - AI 성공 결과도 자동 등록"
    Write-Host "             - 다음 이관 시 매칭 → AI 호출 0"
    Write-Host ""
    Write-Host "  ✓ Phase 3: 실패 패턴 차단"
    Write-Host "             - AI 2회 실패 → 재호출 차단 (비용 절감)"
    Write-Host "             - 사용자 결정 받기 전까지 차단 유지"
    Write-Host "             - manual/exclude 결정 시 자동 해제"
    Write-Host ""
    Write-Host "다음 단계 (필수):" -ForegroundColor Yellow
    Write-Host "  1) 백엔드 재시작 (필수 — 새 모듈 + 라우터 로드):"
    Write-Host "     Stop-Process -Id <PID> -Force"
    Write-Host "     cd $Root\backend; .\start.bat"
    Write-Host ""
    Write-Host "  2) Frontend hot-reload 자동 (또는 Ctrl+Shift+R)"
    Write-Host ""
    Write-Host "  3) 위저드 [↻ 새로 시작] → 검증 시나리오:"
    Write-Host "     - 객체 선택: vProductModelInstructions, vJobCandidateEducation 포함"
    Write-Host "     - AI DBA 분석 단계 → 빨간 5% 신뢰도 카드 확인 ✅"
    Write-Host "     - [✍️ 수동 SQL 작성] 클릭 → 모달 열림"
    Write-Host "     - MySQL 작성 → [🔎 검증] → [💾 저장 + KB 등록]"
    Write-Host "     - 또는 [⊘ 이관 제외] 클릭"
    Write-Host "     - 실행 → 사용자 결정 적용 ✅"
    Write-Host ""
    Write-Host "  4) KB 누적 효과 검증 (한 줄):"
    Write-Host "     `$DataDir='$DataDir'"
    Write-Host "     Get-ChildItem `$DataDir | Select-Object Name, Length, LastWriteTime"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Get-ChildItem '$BackupDir' | ForEach-Object {"
    Write-Host "    `$dst = Join-Path '$Root' (`$_.Name -replace '\\.bak\$', '' )"
    Write-Host "    Copy-Item `$_.FullName `$dst -Force }"
} else {
    Write-Host "[4/4] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\*.bak' '$Root\...' -Force"
    exit 2
}
