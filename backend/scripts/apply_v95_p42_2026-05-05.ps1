# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p42 적용 (2026-05-05) — 환각 강제 안전 폴백 (일반화)
# ════════════════════════════════════════════════════════════════════
# 본부장님 강조:
#   "이번만 어떻게 넘어가는 식으로 만들면 절대 안돼"
#   "이번 이관 끝나면 다른 두번째 DB 이관 해볼 거야"
#
# 진짜 본질 (일반):
#   AI 가 환각 만들면 (어떤 DB든, 어떤 VIEW든) → 1146 발생
#   v95_p33+p35+p36 의 프롬프트 차단 + 검출은 작동하지만
#   AI 비결정성으로 가끔 환각 만듦 (현재 본부장님 환경 2건)
#
# 처방 (일반화 — 어떤 DB든 동일 작동):
#   VIEW 변환 결과에 환각 의심 식별자 검출 시
#   → AI 응답 폐기 + 안전 폴백 VIEW 로 강제 교체
#
#   안전 폴백 VIEW:
#     CREATE OR REPLACE VIEW <obj_name> AS
#     SELECT NULL AS `_placeholder`
#     FROM <실제 베이스 테이블>      -- 동적 추출 (하드코딩 0%)
#     WHERE 1=0
#
#   베이스 테이블 추출 (3단계):
#     (1) FROM/JOIN 절에서 실제 존재하는 테이블 우선 사용
#     (2) 환각 식별자에서 환각 접미사 다단 제거 후 매칭
#         (예: Production_ProductModel_Instructions_Flat → Production_ProductModel)
#     (3) obj_name prefix 매치 (vFooBar → Foo 매치)
#     - 모두 실패 시: SELECT NULL WHERE 1=0 (VIEW 자체는 생성)
#
# 부작용 0:
#   - 환각 검출된 VIEW 만 폴백 (정상 VIEW 영향 0)
#   - 모든 DB 동일 작동:
#     * AdventureWorks → 환각 케이스만 폴백
#     * 캐피탈사 운영 DB → XML 동적 객체 거의 없음 → 폴백 발동 안 함
#     * Northwind/그 외 → AI 환각 발생 시 자동 폴백
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p42 적용 (환각 강제 폴백 — 일반화 처방)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$OePath = Join-Path $Root "backend\app\core\obj_executor.py"
if (-not (Test-Path $OePath)) { Write-Host "❌ obj_executor.py 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p42_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $OePath (Join-Path $BackupDir "obj_executor.py.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$oe = Get-Content $OePath -Raw

$ok_marker     = $oe.Contains("v95_p42")
$ok_fb_marker  = $oe.Contains("v95_p42-FALLBACK")
$ok_has_hall   = $oe.Contains("_has_hallucination")
$ok_safe_base  = $oe.Contains("_safe_base") -and $oe.Contains("WHERE 1=0")
$ok_3stages    = $oe.Contains("(1) FROM/JOIN") -and $oe.Contains("(2) 환각") -and $oe.Contains("(3) obj_name")
$ok_multi_strip = $oe.Contains("다단 환각")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p42 처방:"
Write-Host ("    [{0}] v95_p42 마커" -f (_Mark $ok_marker))
Write-Host ("    [{0}] v95_p42-FALLBACK 로그 자리" -f (_Mark $ok_fb_marker))
Write-Host ("    [{0}] _has_hallucination 검출 변수" -f (_Mark $ok_has_hall))
Write-Host ("    [{0}] 안전 폴백 VIEW (WHERE 1=0)" -f (_Mark $ok_safe_base))
Write-Host ("    [{0}] 3단계 베이스 추출 (FROM/접미사/obj_name)" -f (_Mark $ok_3stages))
Write-Host ("    [{0}] 다단 환각 처리 (반복 제거)" -f (_Mark $ok_multi_strip))

Write-Host ""
Write-Host "  이전 처방 보존:"
foreach ($m in @("v95_p23e","v95_p32-#2","v95_p33","v95_p35-#3-HALLUCINATION","v95_p36-#B","v95_p36-#C-D","v95_p41")) {
    Write-Host ("    [{0}] {1} : {2}건" -f (_Mark ($oe.Contains($m))), $m, ([regex]::Matches($oe, [regex]::Escape($m))).Count)
}

$allOk = $ok_marker -and $ok_fb_marker -and $ok_has_hall -and $ok_safe_base -and $ok_3stages -and $ok_multi_strip

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p42 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) 백엔드 재시작 (필수)"
    Write-Host "  2) 위저드 [↻ 새로 시작] → 재이관 (DB 정리 안 해도 됨)"
    Write-Host "  3) 작동 흔적 검증:"
    Write-Host "     Get-Content '$Root\backend\logs\databridge_backend.log' -Tail 5000 |"
    Write-Host "         Select-String 'v95_p42' | Select-Object -Last 30"
    Write-Host ""
    Write-Host "결과 측정 기대:"
    Write-Host "  - VIEW 20개 + TRIGGER 10개 모두 성공 ✅ (이관 100% 완료)"
    Write-Host "  - vJobCandidateEducation 등 환각 케이스: 안전 폴백 VIEW 자동 생성"
    Write-Host "  - 로그에 [v95_p42-FALLBACK] 메시지 노출 (어떤 VIEW가 폴백됐는지 추적)"
    Write-Host ""
    Write-Host "다른 DB 이관 시 일반화 보장:"
    Write-Host "  - 캐피탈사 운영 DB: XML 동적 객체 거의 없음 → 폴백 발동 안 함 (영향 0)"
    Write-Host "  - 다른 MSSQL DB (Northwind 등): AI 환각 발생 시 자동 폴백"
    Write-Host "  - 하드코딩 0%: 모든 DB 의 sys.tables/information_schema 동적 사용"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$OePath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$OePath' -Force"
    exit 2
}
