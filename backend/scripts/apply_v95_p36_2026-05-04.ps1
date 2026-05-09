# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p36 적용 (2026-05-04)
# ════════════════════════════════════════════════════════════════════
# 5개 신규 본질 일괄 처방:
#
#   본질 A: MSSQL XML 함수 그대로 출력 (1064)
#     자리: view_trigger.txt 규칙 12 추가
#     처방: AI 프롬프트에 XML 함수 절대 금지 + NULL 컬럼 대체 강력 명시
#
#   본질 B: WITH SCHEMABINDING/ENCRYPTION 그대로 (1064)
#     자리: view_trigger.txt 규칙 13 + obj_executor.py post-fix
#     처방: 프롬프트 명시 + post-fix 자리 강제 제거 (이중 안전망)
#
#   본질 C+D: TRIGGER 헤더 누락 / CREATE 자체 없음
#     자리: obj_executor.py _split_sql_statements 직후
#     처방: 헤더 검증 + 명확한 진단 로그 (다음 재이관에서 본질 100% 노출)
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p36 적용 (5개 본질 일괄)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$VtPath = Join-Path $Root "backend\prompts\mssql_to_mysql\view_trigger.txt"
$OePath = Join-Path $Root "backend\app\core\obj_executor.py"

if (-not (Test-Path $VtPath)) { Write-Host "❌ view_trigger.txt 없음" -ForegroundColor Red; exit 1 }
if (-not (Test-Path $OePath)) { Write-Host "❌ obj_executor.py 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p36_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $VtPath (Join-Path $BackupDir "view_trigger.txt.bak") -Force
Copy-Item $OePath (Join-Path $BackupDir "obj_executor.py.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$vt = Get-Content $VtPath -Raw
$oe = Get-Content $OePath -Raw

$ok_v36_marker  = $vt.Contains("v95_p36")
$ok_v36_xml     = $vt.Contains("Resume.value") -and $vt.Contains("절대 출력 금지")
$ok_v36_schbind = $vt.Contains("SCHEMABINDING") -and $vt.Contains("MySQL 미지원")

$ok_oe_marker = $oe.Contains("v95_p36-#B") -and $oe.Contains("v95_p36-#C-D")
$ok_oe_remove = $oe.Contains("MSSQL 전용 키워드 제거")
$ok_oe_check  = $oe.Contains("CREATE TRIGGER 헤더 누락")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  본질 A+B (AI 프롬프트):"
Write-Host ("    [{0}] v95_p36 마커" -f (_Mark $ok_v36_marker))
Write-Host ("    [{0}] XML 함수 절대 금지 명시" -f (_Mark $ok_v36_xml))
Write-Host ("    [{0}] SCHEMABINDING 미지원 명시" -f (_Mark $ok_v36_schbind))

Write-Host ""
Write-Host "  본질 B (post-fix 강제 제거):"
Write-Host ("    [{0}] v95_p36-#B 마커" -f (_Mark $ok_oe_marker))
Write-Host ("    [{0}] MSSQL 키워드 제거 로직" -f (_Mark $ok_oe_remove))

Write-Host ""
Write-Host "  본질 C+D (헤더 검증):"
Write-Host ("    [{0}] 헤더 누락 진단 로그" -f (_Mark $ok_oe_check))

Write-Host ""
Write-Host "  이전 처방 보존:"
foreach ($m in @("v95_p23e","v95_p29","v95_p30","v95_p32-#2","v95_p33","v95_p35-#3-HALLUCINATION")) {
    Write-Host ("    [{0}] {1} : {2}건" -f (_Mark ($oe.Contains($m))), $m, ([regex]::Matches($oe, $m)).Count)
}

$allOk = $ok_v36_marker -and $ok_v36_xml -and $ok_v36_schbind -and $ok_oe_marker -and $ok_oe_remove -and $ok_oe_check

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p36 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) 백엔드 재시작 (프롬프트 + Python 변경 반영)"
    Write-Host "  2) MySQL 타겟 DB 정리"
    Write-Host "  3) 위저드 [↻ 새로 시작] → 재이관"
    Write-Host ""
    Write-Host "결과 측정 기대:"
    Write-Host "  - vProductAndDescription SCHEMABINDING 1064: 0건 ✅ (post-fix 제거)"
    Write-Host "  - vJobCandidateEducation/vProductModelInstructions XML 함수 1064:"
    Write-Host "    프롬프트 강화로 0건 기대 (AI 가 NULL 컬럼 대체 따를 가능성)"
    Write-Host "  - TRIGGER 'near END' / '실행 가능한 CREATE 없음':"
    Write-Host "    [v95_p36-#C-D] 진단 로그로 진짜 원본 응답 노출 → v95_p37 정확한 처방"
    Write-Host ""
    Write-Host "작동 흔적 검증 (재이관 1회 후):"
    Write-Host "  Get-Content '$Root\backend\logs\databridge_backend.log' -Tail 5000 | Select-String 'v95_p36' | Select -Last 30"
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
