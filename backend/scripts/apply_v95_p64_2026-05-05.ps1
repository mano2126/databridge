# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p64 적용 (2026-05-05) — Phase 4-1 위저드 UI 통합
# ════════════════════════════════════════════════════════════════════
# 본부장님 결정: "5 Phase 모두 — 엔터프라이즈 솔루션"
#
# Phase 4-1: 위저드가 객체 DDL 을 preflight 에 전송 + UI 카드 표시
#
# 변경:
#   frontend/src/pages/JobWizard.vue
#
# 추가 사항:
#   1) collectObjectDDLs() — allObjects.body (DDL) 수집 헬퍼
#   2) runPreflightAnalysis 에 object_ddls 동봉
#   3) preflight 좌측 리스트 — object_risk 카테고리 아이콘 (⚠️)
#   4) preflight 우측 상세 — risk_meta 카드 (신뢰도 게이지 + 패턴 + 권장)
#   5) CSS — pf-detail-risk-meta + 패턴 카드 + 신뢰도 바
#
# UI 카드 구성 (object_risk 카테고리 선택 시):
#
#   [신뢰도 게이지 — 색상]
#     0~29%:  🔴 빨간색 (자동 변환 어려움)
#     30~69%: 🟡 노란색 (시도 가능)
#     70~100%: 🟢 초록색 (안전)
#
#   [검출 패턴 카드별]
#     - 위험 레벨 (HIGH/MED/LOW)
#     - 패턴 이름 (XML .value() 메서드 등)
#     - 설명
#     - MySQL 대안 가이드
#     - 매치 샘플 (코드)
#
#   [권장 처리]
#   [v95_p65 안내 — 사용자 결정 (다음 패치)]
#
# 부작용 0:
#   - allObjects 의 body 는 이미 백엔드가 제공
#   - 추가 API 호출 0 (DDL 보유 활용)
#   - 옛 백엔드 호환 (object_ddls 무시)
#   - 기존 4개 카테고리 (deadlock/ai_conversion/dependency/performance) 그대로
#   - v95_p59/p60/p61 처방 100% 보존
#
# 본부장님 환경 효과:
#   - vProductModelInstructions / vJobCandidateEducation 같은 위험 객체
#     사전 분석 단계에서 빨간색 5% 신뢰도로 즉시 표시
#   - XML/CROSS APPLY 검출 패턴 + MySQL 대안 가이드 제공
#   - 사용자가 위험 사전 인지 → v95_p65 (다음) 에서 결정 가능
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p64 적용 (Phase 4-1 위저드 UI)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$Path = Join-Path $Root "frontend\src\pages\JobWizard.vue"
if (-not (Test-Path $Path)) { Write-Host "❌ JobWizard.vue 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p64_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $Path (Join-Path $BackupDir "JobWizard.vue.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증 (UTF-8 명시)
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$src = [System.IO.File]::ReadAllText($Path, [System.Text.UTF8Encoding]::new($false))

$ok_marker = $src.Contains("v95_p64")
$ok_collect = $src.Contains("collectObjectDDLs")
$ok_object_ddls = $src.Contains("object_ddls:")
$ok_obj_risk = $src.Contains("object_risk")
$ok_risk_meta = $src.Contains("risk_meta")
$ok_meta_card = $src.Contains("pf-detail-risk-meta")
$ok_confidence = $src.Contains("pf-rm-confidence")
$ok_patterns = $src.Contains("pf-rm-pattern-card")
$ok_p60 = $src.Contains("v95_p60")  # 보존 확인

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p64 처방:"
Write-Host ("    [{0}] v95_p64 마커" -f (_Mark $ok_marker))
Write-Host ("    [{0}] collectObjectDDLs 헬퍼 함수" -f (_Mark $ok_collect))
Write-Host ("    [{0}] preflight 호출에 object_ddls 동봉" -f (_Mark $ok_object_ddls))
Write-Host ("    [{0}] object_risk 카테고리 처리" -f (_Mark $ok_obj_risk))
Write-Host ("    [{0}] risk_meta 표시" -f (_Mark $ok_risk_meta))
Write-Host ("    [{0}] 상세 메타 카드 CSS (.pf-detail-risk-meta)" -f (_Mark $ok_meta_card))
Write-Host ("    [{0}] 신뢰도 게이지 CSS" -f (_Mark $ok_confidence))
Write-Host ("    [{0}] 패턴 카드 CSS" -f (_Mark $ok_patterns))

Write-Host ""
Write-Host "  이전 처방 보존:"
Write-Host ("    [{0}] v95_p60 (위저드 state 보존)" -f (_Mark $ok_p60))
foreach ($m in @("v95_p59","v95_p61")) {
    Write-Host ("    [{0}] {1}" -f (_Mark ($src.Contains($m))), $m)
}

$allOk = $ok_marker -and $ok_collect -and $ok_object_ddls -and `
         $ok_obj_risk -and $ok_risk_meta -and $ok_meta_card -and `
         $ok_confidence -and $ok_patterns -and $ok_p60

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p64 적용 완료 (Phase 4-1 위저드 UI)" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) Frontend hot-reload 자동 (또는 Ctrl+Shift+R)"
    Write-Host ""
    Write-Host "  2) 위저드 [↻ 새로 시작] → 객체 선택 → AI DBA 분석 단계 진입"
    Write-Host ""
    Write-Host "  3) 검증 시나리오:"
    Write-Host "     - vProductModelInstructions / vJobCandidateEducation 선택 후"
    Write-Host "     - 사전 분석 패널에 ⚠️ 카테고리 critical 항목 표시"
    Write-Host "     - 클릭 시 우측에:"
    Write-Host "       * 빨간 신뢰도 5% 게이지"
    Write-Host "       * XML .value/.nodes/CROSS APPLY 패턴 카드"
    Write-Host "       * MySQL 대안 가이드"
    Write-Host "       * 권장 처리 메시지"
    Write-Host ""
    Write-Host "  4) v95_p65 (사용자 결정 — 자동/수동/제외) 진행"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\JobWizard.vue.bak' '$Path' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    exit 2
}
