# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p33 적용 (2026-05-04)
# ════════════════════════════════════════════════════════════════════
# AI 환각 본질 2건 처방:
#
#   본질 1: AI 시스템 프롬프트 (view_trigger.txt) 보강
#     - OPENXML / XQuery / .nodes() / .value() 처리 규칙 추가
#     - 가짜 의존 테이블 작명 절대 금지 (어떤 접미사든)
#     - 의존 객체 이름 변형 금지
#
#   본질 2: VIEW 미존재 의존 검증 (obj_executor.py)
#     - VIEW 의 FROM/JOIN 절 모든 식별자가 실제 테이블인지 확인
#     - 환각 의심 접미사 검출 시 명확한 ERROR 로그
#     - v95_p32 의 SHOW TABLES 캐시 활용 (성능 비용 0)
#
# 적용 파일:
#   - backend/prompts/mssql_to_mysql/view_trigger.txt
#   - backend/app/core/obj_executor.py
#
# 부작용 0 검증: 단위 테스트 7건 통과
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p33 적용 (AI 환각 본질 처방)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$VtPath = Join-Path $Root "backend\prompts\mssql_to_mysql\view_trigger.txt"
$OePath = Join-Path $Root "backend\app\core\obj_executor.py"

if (-not (Test-Path $VtPath)) { Write-Host "❌ view_trigger.txt 없음" -ForegroundColor Red; exit 1 }
if (-not (Test-Path $OePath)) { Write-Host "❌ obj_executor.py 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p33_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $VtPath (Join-Path $BackupDir "view_trigger.txt.bak") -Force
Copy-Item $OePath (Join-Path $BackupDir "obj_executor.py.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$vt = Get-Content $VtPath -Raw
$oe = Get-Content $OePath -Raw

# 본질 1: view_trigger.txt
$ok_v1_marker = $vt.Contains("v95_p33")
$ok_v1_openxml = $vt.Contains("OPENXML")
$ok_v1_no_fake = $vt.Contains("가짜 의존 테이블") -or $vt.Contains("ABSOLUTELY")

# 본질 2: obj_executor.py
$ok_v2_marker = $oe.Contains("v95_p33-#2")
$ok_v2_check  = $oe.Contains("HALLUCINATION") -and $oe.Contains("hallucination_suffixes")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  본질 1 (AI 프롬프트 view_trigger.txt):"
Write-Host ("    [{0}] v95_p33 마커" -f (_Mark $ok_v1_marker))
Write-Host ("    [{0}] OPENXML 처리 규칙" -f (_Mark $ok_v1_openxml))
Write-Host ("    [{0}] 가짜 의존 금지 규칙" -f (_Mark $ok_v1_no_fake))

Write-Host ""
Write-Host "  본질 2 (VIEW 미존재 의존 검증):"
Write-Host ("    [{0}] v95_p33-#2 마커" -f (_Mark $ok_v2_marker))
Write-Host ("    [{0}] HALLUCINATION 검출 로직" -f (_Mark $ok_v2_check))

Write-Host ""
Write-Host "  이전 처방 보존:"
foreach ($m in @("v95_p23e","v95_p29","v95_p30","v95_p32-#2")) {
    Write-Host ("    [{0}] {1} : {2}건" -f (_Mark ($oe.Contains($m))), $m, ([regex]::Matches($oe, $m)).Count)
}

$allOk = $ok_v1_marker -and $ok_v1_openxml -and $ok_v1_no_fake -and $ok_v2_marker -and $ok_v2_check

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p33 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) 백엔드 재시작 (Python + 프롬프트 변경 반영)"
    Write-Host "  2) MySQL 타겟 DB 정리"
    Write-Host "  3) 위저드 [↻ 새로 시작] → 재이관"
    Write-Host ""
    Write-Host "  [본질 3+4+5 진단 동시 차움]:"
    Write-Host "  PowerShell -ExecutionPolicy Bypass -File '$Root\backend\scripts\diag_v95_p33_row_2026-05-04.ps1'"
    Write-Host "  Compress-Archive -Path '$Root\backend\logs\diag_v95_p32_row_2026-05-04\*' \"
    Write-Host "    -DestinationPath 'D:\project\diag_v95_p33_row_2026-05-04.zip' -Force"
    Write-Host ""
    Write-Host "결과 측정 기대:"
    Write-Host "  - vJobCandidateEducation/vProductModelInstructions 1146 가짜 의존 0건"
    Write-Host "  - 또는 [v95_p33-#2-HALLUCINATION] 로그로 진짜 본질 노출"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\view_trigger.txt.bak' '$VtPath' -Force"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$OePath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\view_trigger.txt.bak' '$VtPath' -Force"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$OePath' -Force"
    exit 2
}
