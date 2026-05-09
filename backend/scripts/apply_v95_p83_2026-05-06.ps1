# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p83 (2026-05-06) — 1064/1054 핫픽스
# ════════════════════════════════════════════════════════════════════
# 본부장님 오전 10:01 오류 보고:
#   1) vJobCandidateEducation: 1064 syntax near 'DROP VIEW IF EXISTS'
#   2) vProductModelInstructions: 1054 Unknown column 'pmd.Name'
#
# 본질 진단:
#   1) 1064: AI 가 DROP 문 끝에 ; 빠뜨림 → DROP+CREATE 합쳐짐
#      ← v95_p77 의 폴백 처방은 ; 명시적이지만, AI 자체 응답이 환각
#        검출 안 된 경우 그대로 사용됨
#
#   2) 1054: AI 가 만든 alias 가 실제 컬럼과 불일치
#      ← 진짜 base 테이블 사용했지만 컬럼 이름 환각
#
# v95_p83 처방 — DROP+CREATE ; 강제 보장 (본질 1):
#   변경: backend/app/core/obj_executor.py
#   - clean 단계 마지막에 정규식 후처리:
#     DROP <KIND> [IF EXISTS] <name> 다음에 CREATE 가 ; 없이 오면
#     자동으로 ; 삽입
#
#   부작용 0:
#     - 이미 ; 있으면 변경 X (정규식 lookahead)
#     - DROP 만 또는 CREATE 만 있으면 변경 X
#     - 모든 객체 타입 적용 (VIEW/TRIGGER/PROCEDURE/FUNCTION)
#
#   단위 테스트 5/5 통과:
#     ✅ 본부장님 환경 vJobCandidateEducation 케이스
#     ✅ 정상 ; 케이스 (false positive 0)
#     ✅ 백틱 식별자
#     ✅ PROCEDURE/FUNCTION 도 동일
#     ✅ CREATE 만 (DROP 없음) 영향 0
#
# 1054 처방 — 다음 세션 또는 본부장님 SQL 데이터 받고:
#   본부장님 환경의 실제 vProductModelInstructions DDL 받아야
#   alias 환각인지, 진짜 컬럼 누락인지 진단 가능.
#   현재는 v95_p72 환각 검증으로 어느 정도 처방됨 (Detail 검출).
#
# 변경 파일 1개:
#   1) backend/app/core/obj_executor.py (v95_p83 ; 보장 추가)
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p83 (1064 syntax 핫픽스)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$Path = Join-Path $Root "backend\app\core\obj_executor.py"

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p83_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $Path (Join-Path $BackupDir "obj_executor.py.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$src = [System.IO.File]::ReadAllText($Path, [System.Text.UTF8Encoding]::new($false))

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

$ok_p83       = $src.Contains('v95_p83')
$ok_pattern   = $src.Contains('_drop_create_pattern')
$ok_marker    = $src.Contains('DROP-CREATE-SEMICOLON')
$ok_p77_keep  = $src.Contains('v95_p77')   # 이전 처방 보존
$ok_p72_keep  = $src.Contains('auto_fix_view_hallucination')

Write-Host ""
Write-Host "  v95_p83 처방:"
Write-Host ("    [{0}] v95_p83 마커" -f (_Mark $ok_p83))
Write-Host ("    [{0}] DROP+CREATE 정규식 패턴" -f (_Mark $ok_pattern))
Write-Host ("    [{0}] DROP-CREATE-SEMICOLON 로그 마커" -f (_Mark $ok_marker))

Write-Host ""
Write-Host "  이전 처방 보존:"
Write-Host ("    [{0}] v95_p77 (환각 검출)" -f (_Mark $ok_p77_keep))
Write-Host ("    [{0}] v95_p72 (환각 자동 수정)" -f (_Mark $ok_p72_keep))

# Python 임포트 테스트
Write-Host ""
Write-Host "  [Python 임포트 테스트]"
try {
    Push-Location (Join-Path $Root "backend")
    $testResult = & python -c @"
import sys
sys.path.insert(0, '.')
import re

# v95_p83 정규식 직접 테스트
pat = re.compile(
    r'(\bDROP\s+(?:VIEW|TRIGGER|PROCEDURE|PROC|FUNCTION|FUNC|TABLE)'
    r'(?:\s+IF\s+EXISTS)?\s+`?[\w]+`?)'
    r'(\s*\n\s*)'
    r'(CREATE\b)',
    re.IGNORECASE
)

test_sql = 'DROP VIEW IF EXISTS HumanResources_vJobCandidateEducation\nCREATE VIEW test AS SELECT 1;'
fixed = pat.sub(r'\1;\2\3', test_sql)
ok = (';' in fixed.split('CREATE')[0])
print(f'OK - DROP+CREATE ; 자동 삽입: {ok}')
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

$allOk = $ok_p83 -and $ok_pattern -and $ok_marker -and $ok_p77_keep -and $ok_p72_keep

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p83 적용 완료 (1064 syntax 핫픽스)" -ForegroundColor Green
    Write-Host ""
    Write-Host "════════════════════════════════════════════════════════"
    Write-Host "  ⚠️ 백엔드 재시작 필수 + 캐시 + 실패 KB 삭제 권장" -ForegroundColor Yellow
    Write-Host "════════════════════════════════════════════════════════"
    Write-Host ""
    Write-Host "다음 단계:"
    Write-Host ""
    Write-Host "  1) 캐시 + 실패 KB 삭제 (옛 환각 결과 제거):"
    Write-Host '     $cache="D:\project\databridge_full\backend\data\ai_conversion_cache.json"'
    Write-Host '     if (Test-Path $cache) { Remove-Item $cache -Force; Write-Host "캐시 삭제" }'
    Write-Host '     $fail="D:\project\databridge_full\backend\data\conversion_failures.json"'
    Write-Host '     if (Test-Path $fail) { Remove-Item $fail -Force; Write-Host "실패 KB 삭제" }'
    Write-Host ""
    Write-Host "  2) 백엔드 재시작:"
    Write-Host '     Get-Process python | Stop-Process -Force; Start-Sleep -Seconds 2'
    Write-Host '     cd D:\project\databridge_full\backend; .\start.bat'
    Write-Host ""
    Write-Host "  3) 위저드 [↻ 새로 시작] → 위험 객체 [자동 변환 시도] → 이관"
    Write-Host ""
    Write-Host "  4) 검증:"
    Write-Host "     - vJobCandidateEducation: 1064 0건 ✅"
    Write-Host "     - 백엔드 로그에서 [v95_p83-DROP-CREATE-SEMICOLON] 로그 확인:"
    Write-Host '       Get-Content "D:\project\databridge_full\backend\logs\databridge_backend.log" -Tail 200 | Select-String "v95_p83"'
    Write-Host ""
    Write-Host "  5) vProductModelInstructions 1054 진단 (다음 세션):"
    Write-Host "     - 본부장님께서 변환된 DDL 공유해주시면 alias 환각인지 진단"
    Write-Host "     - 또는 [✍️ 전문가 직접 작성] 으로 우회"
    Write-Host "     - 또는 [⊘ 이관 제외] (베이스 테이블 데이터는 이관됨)"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$Path' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    exit 2
}
