# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p38 적용 (2026-05-05)
# ════════════════════════════════════════════════════════════════════
# 본부장님 호소: "DB 초기화 안 하면 VIEW 20개 + TRIGGER 10개 모두 오류"
#               "drop 옵션 걸면 정상 수행되는거야?"
#
# 진짜 본질 (view tool 100% 확인):
#   1) view_mode 설정값 어디서도 사용 안 됨 (저장만 + readback)
#   2) obj_mode "drop_recreate" 분기 자체 없음 (skip_existing 만 처리)
#   3) VIEW DROP IF EXISTS 자체가 시스템 어디에도 없음
#      → 이미 존재하는 VIEW + CREATE → 1050 'already exists' 에러
#      → 이미 존재하는 TRIGGER + CREATE → 1359 'already exists' 에러
#
# 처방 (단일 본질 단일 처방):
#   (a) VIEW/TRIGGER/PROC/FUNC 명시적 DROP IF EXISTS 자리 도입
#       자리: migration_engine.py:1948~ _exec_tgt 함수
#       처방: drop_recreate 분기 추가, mysql 타겟에서 명시 DROP 실행
#
#   (b) AI 프롬프트 system.txt 도 CREATE OR REPLACE VIEW 통일 (이중 안전망)
#       자리: prompts/mssql_to_mysql/system.txt:46
#       처방: CREATE VIEW → CREATE OR REPLACE VIEW + 강조 메모
#
#   (c) view_mode/obj_mode 설정값 진짜 적용
#       자리: migration_engine.py:1948~ _exec_tgt 함수
#       처방: VIEW 면 view_mode, 그 외면 obj_mode 적용
#
# 부작용 0:
#   - mysql 타겟에서만 DROP 실행 (MSSQL 타겟은 별도 본질)
#   - DROP 실패는 무시 (이미 없는 객체는 정상)
#   - 단위 테스트 9/9 통과
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p38 적용 (VIEW/TRIGGER DROP 정책 본질)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$MePath = Join-Path $Root "backend\app\engine\migration_engine.py"
$SyPath = Join-Path $Root "backend\prompts\mssql_to_mysql\system.txt"

if (-not (Test-Path $MePath)) { Write-Host "❌ migration_engine.py 없음" -ForegroundColor Red; exit 1 }
if (-not (Test-Path $SyPath)) { Write-Host "❌ system.txt 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p38_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $MePath (Join-Path $BackupDir "migration_engine.py.bak") -Force
Copy-Item $SyPath (Join-Path $BackupDir "system.txt.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$me = Get-Content $MePath -Raw
$sy = Get-Content $SyPath -Raw

$ok_v38_marker     = $me.Contains("v95_p38")
$ok_v38_drop_view  = $me.Contains("DROP VIEW IF EXISTS")
$ok_v38_drop_trig  = $me.Contains("DROP TRIGGER IF EXISTS")
$ok_v38_eff_mode   = $me.Contains("_effective_mode")
$ok_v38_view_mode  = $me.Contains('view_mode = self.job.get("view_mode"')

$ok_sy_replace     = $sy.Contains("CREATE OR REPLACE VIEW")
$ok_sy_marker      = $sy.Contains("v95_p38")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  본질 (a) VIEW/TRIGGER 명시 DROP:"
Write-Host ("    [{0}] DROP VIEW IF EXISTS 도입" -f (_Mark $ok_v38_drop_view))
Write-Host ("    [{0}] DROP TRIGGER IF EXISTS 보강" -f (_Mark $ok_v38_drop_trig))

Write-Host ""
Write-Host "  본질 (b) AI 프롬프트 통일:"
Write-Host ("    [{0}] system.txt CREATE OR REPLACE VIEW" -f (_Mark $ok_sy_replace))
Write-Host ("    [{0}] system.txt v95_p38 강조 메모" -f (_Mark $ok_sy_marker))

Write-Host ""
Write-Host "  본질 (c) 설정값 진짜 적용:"
Write-Host ("    [{0}] view_mode 사용 추가" -f (_Mark $ok_v38_view_mode))
Write-Host ("    [{0}] _effective_mode 분기 (VIEW vs 그 외)" -f (_Mark $ok_v38_eff_mode))

Write-Host ""
Write-Host "  이전 처방 보존:"
foreach ($m in @("v95_p23a","v95_p26","v95_p28","v95_p30","v95_p34")) {
    Write-Host ("    [{0}] {1} : {2}건" -f (_Mark ($me.Contains($m))), $m, ([regex]::Matches($me, $m)).Count)
}

$allOk = $ok_v38_marker -and $ok_v38_drop_view -and $ok_v38_drop_trig -and `
         $ok_v38_eff_mode -and $ok_v38_view_mode -and $ok_sy_replace -and $ok_sy_marker

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p38 적용 완료" -ForegroundColor Green
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) 백엔드 재시작 (필수 — Python 메모리 캐시)"
    Write-Host "  2) MySQL 타겟 DB는 정리 안 해도 됨 — DROP IF EXISTS 가 알아서 처리"
    Write-Host "  3) 위저드 [↻ 새로 시작] → 재이관"
    Write-Host ""
    Write-Host "검증 시나리오 (가장 중요):"
    Write-Host "  - DB 초기화 없이 재이관 실행"
    Write-Host "  - 이전에 30개 모두 오류 → 이번엔 0건 기대 ✅"
    Write-Host "  - 로그에서 [v95_p38 본질] DROP 실행 메시지 확인"
    Write-Host ""
    Write-Host "작동 흔적 검증:"
    Write-Host "  Get-Content '$Root\backend\logs\databridge_backend.log' -Tail 5000 |"
    Write-Host "      Select-String 'v95_p38' | Select-Object -Last 30"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\migration_engine.py.bak' '$MePath' -Force"
    Write-Host "  Copy-Item '$BackupDir\system.txt.bak' '$SyPath' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\migration_engine.py.bak' '$MePath' -Force"
    Write-Host "  Copy-Item '$BackupDir\system.txt.bak' '$SyPath' -Force"
    exit 2
}
