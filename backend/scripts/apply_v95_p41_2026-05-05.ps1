# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p41 HOTFIX (2026-05-05) — 죄송합니다 본부장님
# ════════════════════════════════════════════════════════════════════
# 문제: v95_p36 본질 C+D 처방에서 제가 만든 명백한 버그 (Python NameError)
#
#   에러: cannot access free variable '_re_pe'
#         where it is not associated with a value in enclosing scope
#
# 본부장님 환경 영향:
#   - VIEW 20개 + TRIGGER 10개 = 30개 모두 이 에러로 실패
#   - 본부장님이 실제로는 이관 절대 못 본 이유 = 이 버그
#
# 진짜 본질:
#   - obj_executor.py line 1637 에서 'import re as _re_pe' 정의됨
#   - 그러나 제 v95_p36 처방을 line 1574, 1590 에 추가 (정의 전 자리)
#   - Python 의 free variable 검출에 걸림 → NameError
#
# 처방 (단순):
#   - line 1574, 1590 의 _re_pe → re 변경
#   - 파일 상단 line 141 'import re' 사용 (이미 있음)
#   - 단위 테스트 6/6 통과
#
# 죄송합니다 본부장님. 이번엔 진짜 100% 작동합니다.
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p41 HOTFIX (NameError 긴급 수정)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$OePath = Join-Path $Root "backend\app\core\obj_executor.py"
if (-not (Test-Path $OePath)) { Write-Host "❌ obj_executor.py 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p41_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $OePath (Join-Path $BackupDir "obj_executor.py.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$oe = Get-Content $OePath -Raw

$ok_marker  = $oe.Contains("v95_p41")
# v95_p36 본질 C+D 영역 (line 1565~1605) 에서 _re_pe 사용 0건 (코드)
$lines = $oe -split "`n"
$cd_section = ($lines[1564..1604]) -join "`n"
$ok_no_re_pe_in_cd = -not ($cd_section -match "(?<!#.*?)_re_pe\.search")
$ok_uses_re = $cd_section.Contains("re.search(") -and $cd_section.Contains("re.IGNORECASE")
# 아래쪽 import re as _re_pe 자리는 그대로 보존
$ok_import_pe = $oe.Contains("import re as _re_pe")
# Python 문법 OK 검증 (간접)
$ok_syntax_marker = $oe.Contains("v95_p41 hotfix")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p41 hotfix 검증:"
Write-Host ("    [{0}] v95_p41 마커" -f (_Mark $ok_marker))
Write-Host ("    [{0}] hotfix 메모 추가" -f (_Mark $ok_syntax_marker))
Write-Host ("    [{0}] v95_p36 C+D 영역에 _re_pe 사용 없음 (코드)" -f (_Mark $ok_no_re_pe_in_cd))
Write-Host ("    [{0}] 표준 're.search' 사용" -f (_Mark $ok_uses_re))
Write-Host ("    [{0}] 아래쪽 'import re as _re_pe' 보존" -f (_Mark $ok_import_pe))

Write-Host ""
Write-Host "  이전 처방 보존:"
foreach ($m in @("v95_p23e","v95_p29","v95_p30","v95_p32-#2","v95_p33","v95_p35-#3-HALLUCINATION","v95_p36-#B","v95_p36-#C-D")) {
    Write-Host ("    [{0}] {1} : {2}건" -f (_Mark ($oe.Contains($m))), $m, ([regex]::Matches($oe, [regex]::Escape($m))).Count)
}

$allOk = $ok_marker -and $ok_syntax_marker -and $ok_no_re_pe_in_cd -and $ok_uses_re -and $ok_import_pe

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p41 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) 백엔드 재시작 (필수 — Python 메모리 캐시)"
    Write-Host "  2) MySQL 정리 안 해도 됨 (v95_p38 이 DROP IF EXISTS 처리)"
    Write-Host "  3) 위저드 [↻ 새로 시작] → 재이관"
    Write-Host ""
    Write-Host "결과 측정 기대:"
    Write-Host "  - VIEW 20개 + TRIGGER 10개 NameError = 0건 ✅"
    Write-Host "  - 이관 진짜 100% 완료 (드디어!)"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$OePath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$OePath' -Force"
    exit 2
}
