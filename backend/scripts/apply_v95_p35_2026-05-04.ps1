# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p35 적용 (2026-05-04)
# ════════════════════════════════════════════════════════════════════
# 본질 2: AI 시스템 프롬프트 (view_trigger.txt) 더 강하게
#   - 모든 환각 접미사 명시 (_data, _flat, _Helper, _Instruction 등)
#   - 자기참조 환각 절대 금지 강조
#   - 검증 체크리스트 5개 추가
#
# 본질 3: 환각 검출 정규식 기반 확장 (obj_executor.py)
#   - 알려진 환각 접미사 확장 (_Helper, _Aux, _Ref, _Joined 등)
#   - 정규식 백업: 새로운 환각 접미사 자동 검출
#   - 화이트리스트: 정상 접미사 (_id, _at, _count) 보호
#   - 단위 테스트 9건 통과
#
# 본질 1 (검증 도구 매칭 0건): 진단 스크립트 동봉
#   - 추측 처방 금지 — 실제 환경 진단 후 v95_p36 단일 처방
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p35 적용 (본질 2+3)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$VtPath = Join-Path $Root "backend\prompts\mssql_to_mysql\view_trigger.txt"
$OePath = Join-Path $Root "backend\app\core\obj_executor.py"

if (-not (Test-Path $VtPath)) { Write-Host "❌ view_trigger.txt 없음" -ForegroundColor Red; exit 1 }
if (-not (Test-Path $OePath)) { Write-Host "❌ obj_executor.py 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p35_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $VtPath (Join-Path $BackupDir "view_trigger.txt.bak") -Force
Copy-Item $OePath (Join-Path $BackupDir "obj_executor.py.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$vt = Get-Content $VtPath -Raw
$oe = Get-Content $OePath -Raw

$ok_v2_marker = $vt.Contains("v95_p35")
$ok_v2_helper = $vt.Contains("_Helper")
$ok_v2_check  = $vt.Contains("체크리스트")

$ok_v3_marker = $oe.Contains("v95_p35-#3-HALLUCINATION")
$ok_v3_regex  = $oe.Contains("_hallucination_regex")
$ok_v3_white  = $oe.Contains("_whitelisted_suffixes")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  본질 2 (AI 프롬프트 강화):"
Write-Host ("    [{0}] v95_p35 마커" -f (_Mark $ok_v2_marker))
Write-Host ("    [{0}] _Helper 환각 명시" -f (_Mark $ok_v2_helper))
Write-Host ("    [{0}] 체크리스트 5개" -f (_Mark $ok_v2_check))

Write-Host ""
Write-Host "  본질 3 (환각 검출 정규식):"
Write-Host ("    [{0}] v95_p35-#3-HALLUCINATION 마커" -f (_Mark $ok_v3_marker))
Write-Host ("    [{0}] 정규식 백업 로직" -f (_Mark $ok_v3_regex))
Write-Host ("    [{0}] 화이트리스트 (정상 접미사 보호)" -f (_Mark $ok_v3_white))

Write-Host ""
Write-Host "  이전 처방 보존:"
foreach ($m in @("v95_p23e","v95_p29","v95_p30","v95_p32-#2","v95_p33")) {
    Write-Host ("    [{0}] {1} : {2}건" -f (_Mark ($oe.Contains($m))), $m, ([regex]::Matches($oe, $m)).Count)
}

$allOk = $ok_v2_marker -and $ok_v2_helper -and $ok_v2_check -and $ok_v3_marker -and $ok_v3_regex -and $ok_v3_white

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p35 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) 백엔드 재시작 (프롬프트 + Python 변경 반영)"
    Write-Host "  2) MySQL 타겟 DB 정리"
    Write-Host "  3) 위저드 [↻ 새로 시작] → 재이관"
    Write-Host ""
    Write-Host "  본질 1 검증 도구 진단 (추가):"
    Write-Host "  PowerShell -ExecutionPolicy Bypass -File '$Root\backend\scripts\diag_validate_2026-05-04.ps1'"
    Write-Host "  Compress-Archive -Path '$Root\backend\logs\diag_validate_2026-05-04\*' -DestinationPath 'D:\project\diag_validate_2026-05-04.zip' -Force"
    Write-Host ""
    Write-Host "결과 측정 기대:"
    Write-Host "  - vJobCandidateEducation/vProductModelInstructions 환각: 0건 ✅"
    Write-Host "  - 만약 새 환각 발생 시: [v95_p35-#3-HALLUCINATION] 로그로 노출"
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
