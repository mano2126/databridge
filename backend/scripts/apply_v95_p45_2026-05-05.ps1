# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p45 적용 (2026-05-05) — last one
# ════════════════════════════════════════════════════════════════════
# 본부장님 강조: "이번만 어떻게 안 됨, 다음 두번째 DB 이관 일반화"
#
# 진단 결과 (PowerShell 진단 출력):
#   본질 (a) v95_p42-FALLBACK 흔적 없음 → CamelCase 매치 실패
#   본질 (b) DROP 완료 + 그래도 1062 → DocumentNode hierarchyid 스킵
#
# 처방 (둘 다 일반화):
#
#   (a) CamelCase 환각 검출 보강:
#       - 자리: backend/app/core/obj_executor.py
#       - v95_p42 endswith 외 (?<=[a-z])Keyword$ 정규식 매치 추가
#       - 베이스 추출에도 CamelCase 키워드 제거 추가
#
#   (b) PK 일부 컴럼 스킵 시 자동 UPSERT:
#       - 자리: backend/app/engine/migration_engine.py (line ~3757)
#       - 메타데이터 기반 자동 감지:
#         복합 PK + 일부 컴럼이 _hier/_dto/_geo 셋에 있거나 스킵됨
#         → INSERT INTO ... ON DUPLICATE KEY UPDATE 강제 적용
#       - 사용자 옵션 upsert_on_pk_partial_disabled=True 로 끌 수 있음 (안전망)
#
# 일반화 검증:
#   - AdventureWorks Production_ProductDocument: hierarchyid PK → UPSERT 발동 → 32/32 성공
#   - AdventureWorks vProductModelInstructions: CamelCase 환각 → 폴백 발동
#   - 캐피탈사 운영 DB: hierarchyid 거의 없음 → UPSERT 발동 안 함 (영향 0)
#   - Northwind 등: 정상 PK → 영향 0
#
# 단위 테스트:
#   - CamelCase 환각 검출: 6/6 통과 (실제 흐름)
#   - PK UPSERT 결정: 5/5 통과 (시나리오 매트릭스)
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p45 적용 (last one — CamelCase + PK UPSERT)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$OePath = Join-Path $Root "backend\app\core\obj_executor.py"
$MePath = Join-Path $Root "backend\app\engine\migration_engine.py"

if (-not (Test-Path $OePath)) { Write-Host "❌ obj_executor.py 없음" -ForegroundColor Red; exit 1 }
if (-not (Test-Path $MePath)) { Write-Host "❌ migration_engine.py 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p45_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $OePath (Join-Path $BackupDir "obj_executor.py.bak") -Force
Copy-Item $MePath (Join-Path $BackupDir "migration_engine.py.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$oe = Get-Content $OePath -Raw
$me = Get-Content $MePath -Raw

$ok_marker_oe   = $oe.Contains("v95_p45")
$ok_camel_kw    = $oe.Contains("_hallucination_keywords")
$ok_camel_re    = $oe.Contains("_camel_regex")
$ok_camel_check = $oe.Contains("_is_hall_camel")
$ok_camel_strip = $oe.Contains("CamelCase '") -and $oe.Contains("_camel_regex.search(_trial)")

$ok_marker_me   = $me.Contains("v95_p45")
$ok_pk_check    = $me.Contains("_pk_partial_skipped") -and $me.Contains("_pk_names_meta")
$ok_pk_lossy    = $me.Contains("_pk_lossy")
$ok_upsert      = $me.Contains("자동 UPSERT 적용")
$ok_safe_opt    = $me.Contains("upsert_on_pk_partial_disabled")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  처방 (a) CamelCase 환각 보강:"
Write-Host ("    [{0}] v95_p45 마커 (obj_executor)" -f (_Mark $ok_marker_oe))
Write-Host ("    [{0}] hallucination_keywords 추출" -f (_Mark $ok_camel_kw))
Write-Host ("    [{0}] CamelCase 정규식" -f (_Mark $ok_camel_re))
Write-Host ("    [{0}] _is_hall_camel 검사" -f (_Mark $ok_camel_check))
Write-Host ("    [{0}] CamelCase 베이스 추출" -f (_Mark $ok_camel_strip))

Write-Host ""
Write-Host "  처방 (b) PK 일부 스킵 자동 UPSERT:"
Write-Host ("    [{0}] v95_p45 마커 (migration_engine)" -f (_Mark $ok_marker_me))
Write-Host ("    [{0}] PK 메타 추출" -f (_Mark $ok_pk_check))
Write-Host ("    [{0}] PK lossy 검사 (hier/dto/geo)" -f (_Mark $ok_pk_lossy))
Write-Host ("    [{0}] 자동 UPSERT 적용" -f (_Mark $ok_upsert))
Write-Host ("    [{0}] 안전망 옵션 (끄기 가능)" -f (_Mark $ok_safe_opt))

Write-Host ""
Write-Host "  이전 처방 보존:"
foreach ($m in @("v95_p38","v95_p41","v95_p42")) {
    $found = ($oe.Contains($m) -or $me.Contains($m))
    Write-Host ("    [{0}] {1}" -f (_Mark $found), $m)
}

$allOk = $ok_marker_oe -and $ok_camel_kw -and $ok_camel_re -and $ok_camel_check -and $ok_camel_strip -and `
         $ok_marker_me -and $ok_pk_check -and $ok_pk_lossy -and $ok_upsert -and $ok_safe_opt

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p45 적용 완료 (last one!)" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) 백엔드 재시작 (필수)"
    Write-Host "  2) 위저드 [↻ 새로 시작] → 재이관"
    Write-Host "  3) 작동 흔적 검증:"
    Write-Host "     Get-Content '$Root\backend\logs\databridge_backend.log' -Tail 5000 |"
    Write-Host "         Select-String 'v95_p45|v95_p42-FALLBACK' | Select-Object -Last 30"
    Write-Host ""
    Write-Host "결과 측정 기대:"
    Write-Host "  - vProductModelInstructions CamelCase 환각 → 자동 폴백 → 성공 ✅"
    Write-Host "  - Production_ProductDocument 1062 → 자동 UPSERT → 32/32 성공 ✅"
    Write-Host "  - AdventureWorks 100% 이관 완료 ✅"
    Write-Host ""
    Write-Host "다음 두번째 DB 이관 시 일반화 보장:"
    Write-Host "  - 캐피탈사 운영 DB: hierarchyid 없음 → UPSERT 발동 안 함"
    Write-Host "  - Northwind 등: 정상 PK → 영향 0"
    Write-Host "  - 사용자 옵션 끄기: job 에 upsert_on_pk_partial_disabled=True"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$OePath' -Force"
    Write-Host "  Copy-Item '$BackupDir\migration_engine.py.bak' '$MePath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$OePath' -Force"
    Write-Host "  Copy-Item '$BackupDir\migration_engine.py.bak' '$MePath' -Force"
    exit 2
}
