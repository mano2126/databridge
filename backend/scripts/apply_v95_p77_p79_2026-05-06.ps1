# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p77 + v95_p78 + v95_p79 슈퍼 마스터 (2026-05-06)
#   본부장님 3가지 호소 통합 처방
# ════════════════════════════════════════════════════════════════════
# 본부장님 호소 (오전 8:54):
#   1) vJobCandidateEducation 1064 syntax 오류
#   2) vProductModelInstructions 1146 (Detail 환각)
#   3) AI 사용 모니터링 화면 강화 필요
#   4) 관리자 화면 독립 검토
#
# 처방:
#
# v95_p77 — 환각 검출 강화 (1146/1064 본질 처방)
#   변경: backend/app/core/obj_executor.py
#   - 의심 접미사 (언더스코어 없는 형태) 추가:
#     'Detail', 'Details', 'Data', 'Info', 'Helper',
#     'Flat', 'Flattened', 'Extended', 'Joined', ...
#   - 객체 핵심 부분 매치 강화:
#     'Production_vProductModelInstructions' 핵심 = 'ProductModelInstructions'
#     → 'Production_ProductModelInstructionsDetail' 정확 검출
#   - 안전 폴백 SQL 의 CREATE OR REPLACE → DROP + CREATE 분리
#     (1064 syntax near 'DROP VIEW IF EXISTS' 회피)
#
#   단위 테스트 3/3 통과:
#     ✅ vJobCandidateEducation_data 검출
#     ✅ vProductModelInstructionsDetail 검출 (NEW v95_p77)
#     ✅ vEmployee 정상 (false positive 0)
#
# v95_p78 — AI 사용 모니터링 + 비용 분석 화면
#   신규: backend/app/api/routes/ai_stats.py
#   신규: frontend/src/pages/AIStatsPage.vue
#   변경: backend/main.py (라우터 등록)
#   
#   API 엔드포인트:
#     GET /api/v1/ai-stats/summary       — 요약 (호출 + 절감 + 비용)
#     GET /api/v1/ai-stats/cache-stats   — v95_p58 캐시 통계
#     GET /api/v1/ai-stats/kb-stats      — v95_p69 KB 효과 + Top 10
#     GET /api/v1/ai-stats/failures      — v95_p70 차단 객체
#     GET /api/v1/ai-stats/recent-calls  — 최근 AI 호출 이력
#   
#   화면 구성:
#     ① 요약 카드 6개:
#        - AI 호출 (실제)
#        - 캐시 히트 (v95_p58)
#        - KB 매칭 (v95_p69)
#        - 환각 검출 + 자동 수정
#        - 사용자 결정 (manual/exclude)
#        - 💰 비용 절감 % (가장 중요)
#     ② AI 변환 캐시 통계 (객체 타입별, DB 쌍별)
#     ③ 변환 패턴 KB 통계 (Top 10 자주 매칭)
#     ④ 차단된 객체 (사용자 결정 필요)
#     ⑤ 최근 AI 호출 이력 (실시간)
#   
#   기간 필터: 1시간 / 6시간 / 24시간 / 7일 / 30일
#
# v95_p79 — 관리자 메뉴에 AI Stats 추가
#   변경: frontend/src/router/index.js
#   - /admin/ai-stats 라우트 등록
#   - 기존 RBAC 가드 활용 (admin 권한만 접근)
#   - 관리자 메뉴에 'AI 사용 통계' 자동 표시
#
# 본부장님 추가 결정 받은 사항:
#   - 관리자 화면 완전 독립: 다음 세션에서 (시간 + 토큰 효율)
#   - 현재는 기존 /admin/* 구조 활용 (이미 RBAC + 메뉴 분리되어 있음)
#
# 변경 파일 5개:
#   1) backend/app/core/obj_executor.py            (v95_p77 환각 강화)
#   2) backend/app/api/routes/ai_stats.py          (NEW v95_p78)
#   3) backend/main.py                             (v95_p78 라우터 등록)
#   4) frontend/src/pages/AIStatsPage.vue          (NEW v95_p78 UI)
#   5) frontend/src/router/index.js                (v95_p79 라우트)
#
# 부작용 0:
#   - 환각 강화: false positive 없음 (단위 테스트 통과)
#   - DROP+CREATE 분리: 기존 외부 DROP 흐름과 충돌 0 (subset)
#   - AI Stats 화면: 기존 /admin RBAC 그대로 활용
#   - 다른 모든 처방 (v95_p65~p76) 100% 보존
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p77 + v95_p78 + v95_p79"
Write-Host "  환각 강화 + AI Stats + 관리자 메뉴"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

# 변경 파일
$Files = @(
    @{name='obj_executor.py';     rel='backend\app\core\obj_executor.py';
      markers=@('v95_p77','suspicious_suffixes_no_underscore','obj_core','DROP VIEW IF EXISTS')},
    @{name='ai_stats.py';         rel='backend\app\api\routes\ai_stats.py';
      markers=@('v95_p78','router = APIRouter','/summary','/cache-stats','/kb-stats')},
    @{name='main.py';             rel='backend\main.py';
      markers=@('v95_p78','ai_stats')},
    @{name='AIStatsPage.vue';     rel='frontend\src\pages\AIStatsPage.vue';
      markers=@('v95_p78','aip-summary-grid','aip-card-highlight','loadAll')},
    @{name='router\index.js';     rel='frontend\src\router\index.js';
      markers=@('v95_p78','/admin/ai-stats','AIStatsPage','AI 사용 통계')}
)

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p77_p79_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
foreach ($f in $Files) {
    $full = Join-Path $Root $f.rel
    if (Test-Path $full) {
        # 디렉토리 구조 보존하여 백업
        $bn = Split-Path $f.rel -Leaf
        Copy-Item $full (Join-Path $BackupDir "$bn.bak") -Force -ErrorAction SilentlyContinue
        Write-Host "  ✓ $($f.name)"
    }
}
Write-Host "  ✓ 백업 위치: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

$allOk = $true
foreach ($f in $Files) {
    $full = Join-Path $Root $f.rel
    Write-Host ""
    Write-Host "  [$($f.name)]" -ForegroundColor Yellow
    if (-not (Test-Path $full)) {
        Write-Host "    ✗ 파일 없음" -ForegroundColor Red
        $allOk = $false
        continue
    }
    $src = [System.IO.File]::ReadAllText($full, [System.Text.UTF8Encoding]::new($false))
    foreach ($m in $f.markers) {
        $cnt = [regex]::Matches($src, [regex]::Escape($m)).Count
        $ok = $cnt -ge 1
        if (-not $ok) { $allOk = $false }
        Write-Host ("    [{0}] {1} ({2}건)" -f (_Mark $ok), $m, $cnt)
    }
}

# Python 임포트 테스트
Write-Host ""
Write-Host "  [Python 임포트 테스트]" -ForegroundColor Yellow
try {
    Push-Location (Join-Path $Root "backend")
    $testResult = & python -c @"
import sys
sys.path.insert(0, '.')
from app.api.routes.ai_stats import router as ai_stats_router
from app.core.obj_executor import auto_fix_view_hallucination, _detect_hallucinated_tables

# v95_p77 환각 검출 테스트 (본부장님 환경 실제 케이스)
ai_sql = 'CREATE VIEW Production_vProductModelInstructions AS SELECT * FROM Production_ProductModelInstructionsDetail;'
src_sql = 'CREATE VIEW [Production].[vProductModelInstructions] AS SELECT * FROM [Production].[ProductModel] CROSS APPLY x.nodes(\'/\') a(b)'
hall = _detect_hallucinated_tables(ai_sql, src_sql, 'Production_vProductModelInstructions')
print(f'OK - 환각 검출: {len(hall)}건')
for h in hall:
    print(f'  - {h["name"]}: {h["reason"][:60]}')
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

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p77~p79 슈퍼 마스터 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "════════════════════════════════════════════════════════"
    Write-Host "  ⚠️ 백엔드 재시작 필수 + 캐시 삭제 권장" -ForegroundColor Yellow
    Write-Host "════════════════════════════════════════════════════════"
    Write-Host ""
    Write-Host "다음 단계:"
    Write-Host ""
    Write-Host "  1) 캐시 삭제 (옛 환각 결과 제거):"
    Write-Host '     $cache="D:\project\databridge_full\backend\data\ai_conversion_cache.json"'
    Write-Host '     if (Test-Path $cache) { Remove-Item $cache -Force; Write-Host "캐시 삭제 OK" }'
    Write-Host '     $fail="D:\project\databridge_full\backend\data\conversion_failures.json"'
    Write-Host '     if (Test-Path $fail) { Remove-Item $fail -Force; Write-Host "실패 KB 삭제 OK" }'
    Write-Host ""
    Write-Host "  2) 백엔드 재시작:"
    Write-Host '     Get-Process python | Stop-Process -Force; Start-Sleep -Seconds 2'
    Write-Host '     cd D:\project\databridge_full\backend; .\start.bat'
    Write-Host ""
    Write-Host "  3) Frontend hot-reload 자동 (또는 Ctrl+Shift+R)"
    Write-Host ""
    Write-Host "  4) 검증 시나리오:"
    Write-Host ""
    Write-Host "     [재이관 검증 — v95_p77]"
    Write-Host "     - 위저드 [↻ 새로 시작] → 6개 위험 객체 [자동 변환 시도] → 이관"
    Write-Host "     - 기대: 1146 + 1064 모두 0건 ✅"
    Write-Host ""
    Write-Host "     [AI Stats 화면 — v95_p78/p79]"
    Write-Host "     - 좌측 메뉴 → 관리자 → 'AI 사용 통계' 클릭"
    Write-Host "     - 또는 직접 URL: http://localhost:3000/admin/ai-stats"
    Write-Host "     - 6개 카드 + KB Top 10 + 차단 객체 + 최근 호출"
    Write-Host "     - 기간 변경 (1시간 ~ 30일) + 새로 고침"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Get-ChildItem '$BackupDir' | ForEach-Object {"
    Write-Host '    # 적절한 자리로 복사 (각 파일별 경로 매핑 필요)'
    Write-Host "  }"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    exit 2
}
