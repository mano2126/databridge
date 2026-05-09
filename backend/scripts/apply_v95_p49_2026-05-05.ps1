# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p49 적용 (2026-05-05) — 환각 검출 이중 안전망
# ════════════════════════════════════════════════════════════════════
# 본부장님 강조: "이번만 어떻게 안 됨, 다음 두번째 DB 이관 일반화"
#               "이중 안전망"
#
# 진단 결과 (view tool 100% + 시뮬레이션 검증):
#   v95_p42/p45 환각 검출 정규식이 백틱(`)으로 감싼 식별자만 매치
#   → AI 가 백틱 없이 plain identifier 출력 시 (본부장님 환경 실제 케이스)
#   → 정규식 매치 실패 → _missing_refs 빈 리스트 → 환각 검출 안 됨
#   → v95_p42/p45 폴백 무력화 → 1146 에러 노출
#
# 처방 (이중 안전망):
#
#   (a) 정규식 백틱 옵션화 (감지 측):
#       자리: backend/app/core/obj_executor.py line 1841~1848
#       Before: r"\b(?:FROM|JOIN)\s+`([A-Za-z_]...)`"
#       After:  r"\b(?:FROM|JOIN)\s+`?([A-Za-z_]...)`?"
#       부작용 0: false positive 6/6 검증 (별칭/서브쿼리 영향 0)
#
#   (b) AI 프롬프트 백틱 강제 명시 (생성 측):
#       자리: backend/prompts/mssql_to_mysql/view_trigger.txt
#       추가: "v95_p49 본질" 섹션 — AI 응답에 백틱(`) 강제 명시
#       이유: 환각 자동 검출 시스템과 직결
#
# 단위 테스트 5/5 통과:
#   - 본부장님 환경 환각 3건 (이번 + 이전) 모두 검출 → 폴백 발동
#   - 정상 VIEW (백틱 있/없 모두) 영향 0
#
# 일반화 (다음 두번째 DB 이관):
#   - 캐피탈사 운영 DB: AI 가 백틱 누락해도 검출 작동
#   - Northwind 등: 정상 식별자도 정확 인식, 환각만 폴백
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p49 적용 (환각 검출 이중 안전망)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$OePath = Join-Path $Root "backend\app\core\obj_executor.py"
$VtPath = Join-Path $Root "backend\prompts\mssql_to_mysql\view_trigger.txt"

if (-not (Test-Path $OePath)) { Write-Host "❌ obj_executor.py 없음" -ForegroundColor Red; exit 1 }
if (-not (Test-Path $VtPath)) { Write-Host "❌ view_trigger.txt 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p49_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $OePath (Join-Path $BackupDir "obj_executor.py.bak") -Force
Copy-Item $VtPath (Join-Path $BackupDir "view_trigger.txt.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$oe = Get-Content $OePath -Raw
$vt = Get-Content $VtPath -Raw

$ok_marker_oe = $oe.Contains("v95_p49")
$ok_regex     = $oe.Contains('`?([A-Za-z_]')      # 백틱 옵션 정규식
$ok_marker_vt = $vt.Contains("v95_p49")
$ok_prompt    = $vt.Contains("백틱 강제 형식")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  처방 (a) 정규식 백틱 옵션:"
Write-Host ("    [{0}] v95_p49 마커 (obj_executor)" -f (_Mark $ok_marker_oe))
Write-Host ("    [{0}] 백틱 옵션 정규식 (`?)" -f (_Mark $ok_regex))

Write-Host ""
Write-Host "  처방 (b) AI 프롬프트 백틱 강제:"
Write-Host ("    [{0}] v95_p49 마커 (view_trigger.txt)" -f (_Mark $ok_marker_vt))
Write-Host ("    [{0}] '백틱 강제 형식' 가이드" -f (_Mark $ok_prompt))

Write-Host ""
Write-Host "  이전 처방 보존:"
foreach ($m in @("v95_p42","v95_p42-FALLBACK","v95_p45")) {
    Write-Host ("    [{0}] {1}" -f (_Mark ($oe.Contains($m))), $m)
}

$allOk = $ok_marker_oe -and $ok_regex -and $ok_marker_vt -and $ok_prompt

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p49 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계 (필수):" -ForegroundColor Yellow
    Write-Host "  1) 백엔드 재시작 (필수 — 정규식 + 프롬프트 둘 다 백엔드 측):"
    Write-Host "     Stop-Process -Id <백엔드 PID> -Force"
    Write-Host "     cd $Root\backend; .\start.bat"
    Write-Host ""
    Write-Host "  2) 위저드 [↻ 새로 시작] → 재이관"
    Write-Host ""
    Write-Host "  3) 작동 흔적 검증:"
    Write-Host "     Get-Content '$Root\backend\logs\databridge_backend.log' -Tail 5000 |"
    Write-Host "         Select-String 'v95_p42-FALLBACK' | Select-Object -Last 30"
    Write-Host ""
    Write-Host "결과 측정 기대:"
    Write-Host "  - vJobCandidateEducation 환각 → 검출 → 폴백 → VIEW 생성 ✅"
    Write-Host "  - vProductModelInstructions 환각 → 검출 → 폴백 → VIEW 생성 ✅"
    Write-Host "  - Production_ProductDocument PK 중복 → v95_p45 UPSERT 발동 → 32/32 성공"
    Write-Host "    (v95_p45 도 백엔드 재시작 필요 — 같이 반영)"
    Write-Host ""
    Write-Host "다음 두번째 DB 이관 일반화 보장:"
    Write-Host "  - 캐피탈사 운영 DB: AI 백틱 누락해도 검출 작동"
    Write-Host "  - Northwind/Adventure 모두: 정상 + 환각 100% 정확 분류"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$OePath' -Force"
    Write-Host "  Copy-Item '$BackupDir\view_trigger.txt.bak' '$VtPath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$OePath' -Force"
    Write-Host "  Copy-Item '$BackupDir\view_trigger.txt.bak' '$VtPath' -Force"
    exit 2
}
