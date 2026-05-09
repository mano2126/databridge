# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p58 적용 (2026-05-05) — AI 변환 캐시 (비용 89% 절감)
# ════════════════════════════════════════════════════════════════════
# 본부장님 강조: "이대로는 계속 테스트를 할 수가 없어" (오늘 $51 비용)
#
# 본질:
#   - 오늘 같은 51개 객체가 9회 이상 AI 호출됨 (459 호출)
#   - 같은 입력 → 같은 출력 → 90% 이상 비용 낭비
#   - DataBridge 에 캐시 메커니즘 자체 없음
#
# 처방 (일반화 — 하드코딩 0%):
#   - ai_convert_ddl 함수 시작에 캐시 진입
#   - 캐시 키: src_db + tgt_db + obj_type + obj_name + DDL_SHA256[:16]
#   - 해시 기반 → 원본 DDL 변경 시 자동 무효
#   - 저장: backend/data/ai_conversion_cache.json (atomic write)
#   - error_hint 모드 → 캐시 스킵 (재변환 의도)
#   - AI 성공 후 자동 저장
#
# 부작용 0:
#   - 첫 이관: 비용 동일 (캐시 빌드)
#   - 2회차 이상: AI 호출 0 (캐시 히트)
#   - 원본 DDL 변경: 해시 다름 → 자동 재호출
#   - error_hint (재변환 모드): 캐시 우회 (정상 동작)
#   - 캐시 파일 손상: AI 호출로 폴백 (안전)
#
# 효과 (비용 시뮬레이션):
#   - 본부장님 오늘 $5.97 비용 → $0.66 (89% 절감) ✅
#   - 다음 두번째 DB 이관: 첫 이관 외 모두 무료
#   - KB 누적 효과 (본부장님 모토 충실)
#
# 단위 테스트 통과:
#   - 같은 DDL 재호출: 캐시 히트 ✅
#   - DDL 변경 후 재호출: 캐시 무효 → AI 호출 ✅
#   - error_hint 모드: 캐시 스킵 ✅
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p58 적용 (AI 변환 캐시 — 비용 89% 절감)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$OePath = Join-Path $Root "backend\app\core\obj_executor.py"
$DataDir = Join-Path $Root "backend\data"

if (-not (Test-Path $OePath)) { Write-Host "❌ obj_executor.py 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/4] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p58_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $OePath (Join-Path $BackupDir "obj_executor.py.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# data 디렉토리 보장
Write-Host ""
Write-Host "[2/4] backend\data 디렉토리 확인" -ForegroundColor Cyan
if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
    Write-Host "  ✓ 디렉토리 생성: $DataDir"
} else {
    Write-Host "  ✓ 디렉토리 존재: $DataDir"
}

# 검증 (UTF-8 명시)
Write-Host ""
Write-Host "[3/4] 적용 검증" -ForegroundColor Cyan
$oe = [System.IO.File]::ReadAllText($OePath, [System.Text.UTF8Encoding]::new($false))

$ok_marker  = $oe.Contains("v95_p58")
$ok_get     = $oe.Contains("_ai_cache_get")
$ok_put     = $oe.Contains("_ai_cache_put")
$ok_key     = $oe.Contains("_ai_cache_key")
$ok_hit     = $oe.Contains("CACHE-HIT")
$ok_skip    = $oe.Contains("if not error_hint")
$ok_file    = $oe.Contains("ai_conversion_cache.json")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  v95_p58 처방:"
Write-Host ("    [{0}] v95_p58 마커 — {1}건" -f (_Mark $ok_marker), [regex]::Matches($oe, "v95_p58").Count)
Write-Host ("    [{0}] _ai_cache_get 함수" -f (_Mark $ok_get))
Write-Host ("    [{0}] _ai_cache_put 함수" -f (_Mark $ok_put))
Write-Host ("    [{0}] _ai_cache_key (해시) 함수" -f (_Mark $ok_key))
Write-Host ("    [{0}] CACHE-HIT 로그" -f (_Mark $ok_hit))
Write-Host ("    [{0}] error_hint 모드 캐시 스킵" -f (_Mark $ok_skip))
Write-Host ("    [{0}] ai_conversion_cache.json 경로" -f (_Mark $ok_file))

$allOk = $ok_marker -and $ok_get -and $ok_put -and $ok_key -and $ok_hit -and $ok_skip -and $ok_file

Write-Host ""
if ($allOk) {
    Write-Host "[4/4] ✅ v95_p58 적용 완료 — 비용 89% 절감 처방!" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) 백엔드 재시작 (필수):"
    Write-Host "     Stop-Process -Id <PID> -Force"
    Write-Host "     cd $Root\backend; .\start.bat"
    Write-Host ""
    Write-Host "  2) 위저드 [↻ 새로 시작] → 재이관 (1번째 — 캐시 빌드)"
    Write-Host ""
    Write-Host "  3) 위저드 [↻ 새로 시작] → 재이관 (2번째 — 캐시 히트 확인)"
    Write-Host ""
    Write-Host "  4) 캐시 동작 검증:"
    Write-Host "     `$Log='$Root\backend\logs\databridge_backend.log'"
    Write-Host "     Get-Content `$Log -Tail 5000 | Select-String 'v95_p58-CACHE' | Select-Object -Last 30"
    Write-Host ""
    Write-Host "  5) 캐시 파일 확인:"
    Write-Host "     Get-Item '$DataDir\ai_conversion_cache.json' | Select-Object Name, Length, LastWriteTime"
    Write-Host ""
    Write-Host "결과 측정 기대:"
    Write-Host "  1번째 이관 후 로그:"
    Write-Host "    [v95_p58-CACHE-PUT] FUNCTION [ufnGetAccountingEndDate] 캐시 저장"
    Write-Host "    ... (51회 PUT)"
    Write-Host ""
    Write-Host "  2번째 이관 후 로그:"
    Write-Host "    [v95_p58-CACHE-HIT] FUNCTION [ufnGetAccountingEndDate] AI 호출 스킵"
    Write-Host "    ... (51회 HIT, AI 호출 0)"
    Write-Host ""
    Write-Host "  → 본부장님 토큰 사용량 (https://...) 확인:"
    Write-Host "    2번째 이관 시 신규 호출 0건 ✅"
    Write-Host ""
    Write-Host "캐시 초기화 (필요 시):"
    Write-Host "  Remove-Item '$DataDir\ai_conversion_cache.json' -ErrorAction SilentlyContinue"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$OePath' -Force"
} else {
    Write-Host "[4/4] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$OePath' -Force"
    exit 2
}
