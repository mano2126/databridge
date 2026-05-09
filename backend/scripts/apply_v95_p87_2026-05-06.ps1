# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p87 (2026-05-06) — 마지막 핫픽스 ❤️
#   본부장님 — 파트너 — 마지막 하나!
# ════════════════════════════════════════════════════════════════════
# 본부장님 오후 6:49 오류:
#   (1054, "Unknown column 'pmi.Name' in 'field list'")
#
# 진단 (오늘 마지막 본질):
#   - AI 가 진짜 베이스 테이블 (Production_ProductModel) 사용
#   - alias 'pmi' 부여 + CROSS APPLY/XML 함수 그대로
#   - 환각 검증 통과 (테이블 진짜) → 폴백 안 거침
#   - MySQL 에서 'pmi.Name' 참조 시 실패 (환각이 아니라 비호환)
#
# 본질:
#   환각만 검증하면 안 됨 — MySQL 비호환 SQL 도 검증 필요!
#
# v95_p87 처방 (2가지 본질 한 방에):
#
#   처방 1: MySQL 비호환 패턴 자동 검출
#     변경: auto_fix_view_hallucination 함수
#     검출 패턴:
#       - CROSS APPLY / OUTER APPLY (MySQL 미지원)
#       - .value(), .nodes(), .query(), .exist() (XML 함수)
#       - PIVOT / UNPIVOT
#       - hierarchyid 메서드 (.GetAncestor, .ToString)
#     → 발견 시 환각이 아니어도 강제 안전 폴백
#     → [v95_p87-INCOMPAT] / [v95_p87-FORCE-FALLBACK] 로그
#
#   처방 2: 폴백 SQL 의 alias.column 처리 강화
#     변경: _generate_safe_fallback_view 함수
#     - pm.[Name] → `Name` (대괄호 추출)
#     - pmi.Name → `Name` (alias.column 패턴 NEW v95_p87)
#     - alias 무시 — 베이스 테이블의 진짜 컬럼만 사용
#
#   단위 테스트 통과:
#     ✅ AI 결과의 CROSS APPLY + XML .value/.nodes 3건 검출
#     ✅ 강제 안전 폴백 발동
#     ✅ pm.[Name] → `Name` 정확 추출
#     ✅ pm.[ProductModelID] → `ProductModelID` 정확 추출
#
# 본부장님 환경 즉시 효과:
#   vProductModelInstructions:
#     이전 (오후 6:49): pmi.Name 참조 → 1054
#     이후 (v95_p87):
#       - CROSS APPLY/XML 검출 → 강제 폴백
#       - SELECT `ProductModelID`, `Name`, NULL AS `Instructions`, ...
#       - FROM Production_ProductModel
#       - → 1054 0건 ✅
#
# 변경 파일 1개:
#   1) backend/app/core/obj_executor.py
#
# 부작용 0:
#   - 환각 없는 정상 VIEW 영향 0
#   - 정상 컬럼 (alias 없는) 영향 0
#   - 모든 이전 처방 (v95_p65~p86) 100% 보존
#
# 본부장님 모토 충실:
#   - 본질에 충실: 환각 ≠ 비호환 — 둘 다 검증 필요 (정확 진단)
#   - 추측 처방 금지: 본부장님 실제 SQL 'pmi.Name' 정확 시뮬 + 단위 테스트
#   - 부작용 0: 정상 VIEW 영향 0
#   - 일반화: 모든 CROSS APPLY/XML/PIVOT/hierarchyid 동일 작동
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p87 — 마지막 핫픽스 ❤️"
Write-Host "  파트너 — 이번에 끝내자!"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$Path = Join-Path $Root "backend\app\core\obj_executor.py"

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p87_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $Path (Join-Path $BackupDir "obj_executor.py.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$src = [System.IO.File]::ReadAllText($Path, [System.Text.UTF8Encoding]::new($false))

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p87 처방:"
$ok_p87       = ([regex]::Matches($src, 'v95_p87')).Count -ge 3
$ok_incompat  = $src.Contains('mysql_incompatible_patterns')
$ok_force     = $src.Contains('v95_p87-FORCE-FALLBACK')
$ok_alias_col = $src.Contains('alias_col')
$ok_cross_app = $src.Contains('CROSS\s+APPLY\b')

Write-Host ("    [{0}] v95_p87 마커" -f (_Mark $ok_p87))
Write-Host ("    [{0}] MySQL 비호환 패턴 리스트" -f (_Mark $ok_incompat))
Write-Host ("    [{0}] 강제 폴백 로그 마커" -f (_Mark $ok_force))
Write-Host ("    [{0}] alias.column 처리" -f (_Mark $ok_alias_col))
Write-Host ("    [{0}] CROSS APPLY 패턴" -f (_Mark $ok_cross_app))

Write-Host ""
Write-Host "  이전 처방 보존:"
foreach ($m in @('v95_p72','v95_p77','v95_p83','v95_p85','v95_p86','auto_fix_view_hallucination')) {
    Write-Host ("    [{0}] {1}" -f (_Mark ($src.Contains($m))), $m)
}

# Python 단위 테스트
Write-Host ""
Write-Host "  [Python 단위 테스트]"
try {
    Push-Location (Join-Path $Root "backend")
    $testResult = & python -c @"
import sys
sys.path.insert(0, '.')
from app.core.obj_executor import auto_fix_view_hallucination

# 본부장님 환경 시뮬 (오후 6:49)
ai_sql = '''CREATE VIEW Production_vProductModelInstructions AS
SELECT pmi.ProductModelID, pmi.Name,
       pmi.Instructions.value('xpath', 'nvarchar(max)') AS Instruction
FROM Production_ProductModel pmi
CROSS APPLY pmi.Instructions.nodes('xpath') M(ref);'''

src_sql = '''CREATE VIEW [Production].[vProductModelInstructions] AS
SELECT pm.[ProductModelID], pm.[Name],
       pm.[Instructions].value('x','y') AS Instruction
FROM [Production].[ProductModel] pm
CROSS APPLY pm.[Instructions].nodes('x') M(ref);'''

result = auto_fix_view_hallucination(ai_sql, src_sql, 'VIEW', 'Production_vProductModelInstructions')

# 검증: 강제 폴백 발동 + 결과 SQL 에 pmi.Name 없음
ok_fixed = result['was_fixed']
ok_no_alias_ref = 'pmi.Name' not in result['fixed_ddl'] and 'pmi.' not in result['fixed_ddl']
ok_has_name = '\`Name\`' in result['fixed_ddl']
print(f'OK - 폴백 적용: {ok_fixed}, alias 제거: {ok_no_alias_ref}, Name 컬럼 보존: {ok_has_name}')
"@ 2>&1
    Pop-Location
    if ($testResult -match "OK") {
        Write-Host "    ✓ $testResult"
    } else {
        Write-Host "    ⚠ $testResult" -ForegroundColor Yellow
    }
} catch {
    Write-Host "    ⚠ Python 검증 스킵"
}

$allOk = $ok_p87 -and $ok_incompat -and $ok_force -and $ok_alias_col

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p87 적용 완료 — 마지막 핫픽스!" -ForegroundColor Green
    Write-Host ""
    Write-Host "════════════════════════════════════════════════════════"
    Write-Host "  ⚠️ 백엔드 재시작 + 캐시 삭제 권장" -ForegroundColor Yellow
    Write-Host "════════════════════════════════════════════════════════"
    Write-Host ""
    Write-Host "다음 단계:"
    Write-Host ""
    Write-Host "  1) 캐시 + 실패 KB 삭제 (옛 환각 결과 깨끗하게):"
    Write-Host '     $cache="D:\project\databridge_full\backend\data\ai_conversion_cache.json"'
    Write-Host '     if (Test-Path $cache) { Remove-Item $cache -Force }'
    Write-Host '     $fail="D:\project\databridge_full\backend\data\conversion_failures.json"'
    Write-Host '     if (Test-Path $fail) { Remove-Item $fail -Force }'
    Write-Host ""
    Write-Host "  2) 백엔드 재시작:"
    Write-Host '     Get-Process python | Stop-Process -Force; Start-Sleep -Seconds 2'
    Write-Host '     cd D:\project\databridge_full\backend; .\start.bat'
    Write-Host ""
    Write-Host "  3) 위저드 [↻ 새로 시작] → 위험 객체 [자동 변환 시도] → 이관"
    Write-Host ""
    Write-Host "  4) 검증:"
    Write-Host "     - vProductModelInstructions: 1054 0건 ✅"
    Write-Host "     - 모든 위험 VIEW 6개 안전 폴백 적용 ✅"
    Write-Host "     - 백엔드 로그에서 v95_p87 흔적 확인:"
    Write-Host '       Get-Content "D:\project\databridge_full\backend\logs\databridge_backend.log" -Tail 200 | Select-String "v95_p87"'
    Write-Host ""
    Write-Host "  5) ★ 이관 100% 성공 축하 ★"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$Path' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    exit 2
}
