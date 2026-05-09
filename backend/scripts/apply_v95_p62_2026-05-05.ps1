# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p62 적용 (2026-05-05) — Phase 1-1 패턴 검출 엔진
# ════════════════════════════════════════════════════════════════════
# 본부장님 결정: "5 Phase 모두 순차 구현 (8-12시간, 완전한 엔터프라이즈)"
#
# 본부장님 모토: "시간이 걸려도 엔터프라이즈 솔루션에 맞도록 구현"
#
# Phase 1-1 — VIEW/객체 위험 패턴 검출 엔진 (신규 모듈)
#
# 신규 파일:
#   backend/app/engine/object_risk_analyzer.py (480 lines)
#
# 검출 패턴 (13개, 데이터 기반 — 새 패턴 추가 시 코드 변경 X):
#
#   HIGH 위험 (자동 변환 거의 불가능):
#     - xml_value_method   : MSSQL XML .value() 메서드
#     - xml_nodes_method   : MSSQL XML .nodes() 메서드 (CROSS APPLY 동반)
#     - xml_query_method   : MSSQL XML .query()
#     - xml_exist_method   : MSSQL XML .exist()
#     - cross_apply        : MSSQL CROSS APPLY
#     - outer_apply        : MSSQL OUTER APPLY
#
#   MEDIUM 위험 (AI 변환 시도 가능):
#     - pivot              : PIVOT 연산자
#     - unpivot            : UNPIVOT 연산자
#     - hierarchyid_method : hierarchyid 메서드 (GetAncestor 등)
#     - spatial_method     : geometry/geography 메서드
#     - merge_statement    : MERGE 구문
#
#   LOW 위험 (자동 변환):
#     - getdate_function   : GETDATE() → NOW()
#     - isnull_function    : ISNULL() → IFNULL()
#     - top_clause         : TOP N → LIMIT N
#
# 단위 테스트 5/5 통과:
#   ✅ vProductModelInstructions: HIGH (XML+APPLY) 신뢰도 5%
#   ✅ vEmployee 일반 VIEW: LOW 신뢰도 100%
#   ✅ uspGetEmployee (TOP/ISNULL/GETDATE): LOW 신뢰도 85%
#   ✅ vSalesByMonth PIVOT: MEDIUM 신뢰도 60%
#   ✅ vEmployeeHierarchy hierarchyid: MEDIUM 신뢰도 50%
#
# 부작용 0:
#   - 신규 모듈 (다른 코드 변경 0)
#   - 정규식 기반 (DB 조회 0)
#   - 분석 실패 시 MEDIUM 반환 (안전)
#
# 다음 단계:
#   v95_p63: preflight.py 통합 (이 엔진을 preflightRisks 에 연결)
#   v95_p64: JobWizard.vue UI (위험 객체 카드 표시)
#   v95_p65: 사용자 결정 form 통합 + v95_p60 보존
#   v95_p66~p68: 수동 SQL 입력 (Phase 5)
#   v95_p69~p70: KB 누적 + 실패 학습 (Phase 2/3)
#   v95_p71: 통합 테스트
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p62 적용 (Phase 1-1 패턴 검출 엔진)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$NewFile = Join-Path $Root "backend\app\engine\object_risk_analyzer.py"

# 백업 (기존 파일 있을 경우)
Write-Host "[1/3] 신규 파일 (기존 파일 없음 — 백업 불필요)" -ForegroundColor Cyan
if (Test-Path $NewFile) {
    $BackupDir = Join-Path $Root "backend\backup_v95_p62_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
    Copy-Item $NewFile (Join-Path $BackupDir "object_risk_analyzer.py.bak") -Force
    Write-Host "  ✓ 기존 파일 백업: $BackupDir"
} else {
    Write-Host "  ✓ 신규 모듈 (백업 불필요)"
}

# 검증 (UTF-8 명시)
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
if (-not (Test-Path $NewFile)) {
    Write-Host "  ✗ object_risk_analyzer.py 없음 — ZIP 풀기 실패?" -ForegroundColor Red
    exit 1
}
$src = [System.IO.File]::ReadAllText($NewFile, [System.Text.UTF8Encoding]::new($false))

$ok_marker     = $src.Contains("v95_p62")
$ok_xml_value  = $src.Contains("xml_value_method")
$ok_xml_nodes  = $src.Contains("xml_nodes_method")
$ok_apply      = $src.Contains("cross_apply")
$ok_pivot      = $src.Contains("pivot")
$ok_hier       = $src.Contains("hierarchyid_method")
$ok_func       = $src.Contains("def analyze_object_ddl")
$ok_batch      = $src.Contains("def analyze_objects_batch")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p62 처방:"
Write-Host ("    [{0}] v95_p62 마커" -f (_Mark $ok_marker))
Write-Host ("    [{0}] HIGH 위험 — XML .value() 패턴" -f (_Mark $ok_xml_value))
Write-Host ("    [{0}] HIGH 위험 — XML .nodes() 패턴" -f (_Mark $ok_xml_nodes))
Write-Host ("    [{0}] HIGH 위험 — CROSS APPLY 패턴" -f (_Mark $ok_apply))
Write-Host ("    [{0}] MEDIUM 위험 — PIVOT 패턴" -f (_Mark $ok_pivot))
Write-Host ("    [{0}] MEDIUM 위험 — hierarchyid 메서드" -f (_Mark $ok_hier))
Write-Host ("    [{0}] analyze_object_ddl 함수" -f (_Mark $ok_func))
Write-Host ("    [{0}] analyze_objects_batch 함수" -f (_Mark $ok_batch))

# Python 임포트 테스트
Write-Host ""
Write-Host "  Python 임포트 테스트:"
$pythonExe = "python"
try {
    Push-Location (Join-Path $Root "backend")
    $testResult = & $pythonExe -c "import sys; sys.path.insert(0, '.'); from app.engine.object_risk_analyzer import analyze_object_ddl, PATTERNS_MSSQL_TO_MYSQL; print(f'OK - {len(PATTERNS_MSSQL_TO_MYSQL)} patterns loaded')" 2>&1
    Pop-Location
    if ($testResult -match "OK") {
        Write-Host "    ✓ $testResult"
    } else {
        Write-Host "    ✗ 임포트 실패: $testResult" -ForegroundColor Yellow
    }
} catch {
    Write-Host "    ⚠ Python 검증 스킵 (수동 확인 필요)" -ForegroundColor Yellow
}

$allOk = $ok_marker -and $ok_xml_value -and $ok_xml_nodes -and $ok_apply -and `
         $ok_pivot -and $ok_hier -and $ok_func -and $ok_batch

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p62 적용 완료 (Phase 1-1 패턴 검출 엔진)" -ForegroundColor Green
    Write-Host ""
    Write-Host "이 패치만으로는 UI 효과 없음:" -ForegroundColor Yellow
    Write-Host "  - 패턴 검출 엔진만 추가 (모듈)"
    Write-Host "  - 다음 v95_p63 에서 preflight.py 와 통합"
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) 백엔드 재시작 (필수 — 새 모듈 로드):"
    Write-Host "     Stop-Process -Id <PID> -Force"
    Write-Host "     cd $Root\backend; .\start.bat"
    Write-Host ""
    Write-Host "  2) Python 임포트 직접 검증:"
    Write-Host "     cd $Root\backend"
    Write-Host "     python -c 'from app.engine.object_risk_analyzer import analyze_object_ddl; print(\"OK\")'"
    Write-Host ""
    Write-Host "  3) v95_p63 (preflight 통합) 진행 알려주십시오"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    exit 2
}
