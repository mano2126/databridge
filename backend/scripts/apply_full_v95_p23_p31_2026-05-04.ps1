# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p23~p31 통합 적용 + 강제 재검증 (2026-05-04)
# ════════════════════════════════════════════════════════════════════
# 본부장님 환경 진단 결과:
#   - migration_engine.py 가 4175 라인 (v95_p26~p31 모두 누락)
#   - obj_executor.py 는 v95_p30 적용된 듯 (로그 흔적 있음)
#   - 백엔드 시작 시각: 08:18 (4시간 전, 재시작 안 됨)
#
# 이 스크립트는:
#   1) 현재 파일 상태 진단
#   2) 누적 패치 적용 검증
#   3) 백엔드 재시작 필요성 알림
#   4) 진짜 적용 강제 검증
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p23~p31 통합 패치 강제 적용 + 검증"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$MePath = Join-Path $Root "backend\app\engine\migration_engine.py"
$OePath = Join-Path $Root "backend\app\core\obj_executor.py"

if (-not (Test-Path $MePath)) {
    Write-Host "❌ migration_engine.py 없음" -ForegroundColor Red; exit 1
}
if (-not (Test-Path $OePath)) {
    Write-Host "❌ obj_executor.py 없음" -ForegroundColor Red; exit 1
}

# ────────────────────────────────────────────────────────────────────
# [1/5] 현재 상태 진단
# ────────────────────────────────────────────────────────────────────
Write-Host "[1/5] 현재 상태 진단" -ForegroundColor Cyan

$me_lines_before = (Get-Content $MePath | Measure-Object -Line).Lines
$oe_lines_before = (Get-Content $OePath | Measure-Object -Line).Lines

Write-Host "  migration_engine.py 라인: $me_lines_before (기대: 4633)"
Write-Host "  obj_executor.py 라인: $oe_lines_before (기대: 2045)"
Write-Host ""

# 마커 카운트
$me_before = Get-Content $MePath -Raw
$oe_before = Get-Content $OePath -Raw

Write-Host "  마커 카운트 (적용 전):"
foreach ($m in @("v95_p23a","v95_p23f","v95_p26","v95_p27","v95_p28","v95_p30","v95_p31")) {
    $me_cnt = if($me_before){([regex]::Matches($me_before, $m)).Count}else{0}
    $oe_cnt = if($oe_before){([regex]::Matches($oe_before, $m)).Count}else{0}
    Write-Host "    $m : migration_engine=$me_cnt, obj_executor=$oe_cnt"
}

# ────────────────────────────────────────────────────────────────────
# [2/5] 백엔드 프로세스 확인
# ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/5] 백엔드 프로세스 확인" -ForegroundColor Cyan
$pyProcs = Get-Process python -ErrorAction SilentlyContinue
if ($pyProcs) {
    Write-Host "  실행 중인 Python 프로세스:"
    $pyProcs | ForEach-Object {
        $age = (Get-Date) - $_.StartTime
        Write-Host "    PID $($_.Id) - 시작 $($_.StartTime.ToString('HH:mm:ss')) (실행 시간 $([Math]::Round($age.TotalMinutes,0))분)"
    }
} else {
    Write-Host "  ⚠ Python 프로세스 없음 — 백엔드 꺼져 있는 듯"
}

# ────────────────────────────────────────────────────────────────────
# [3/5] 백업
# ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/5] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_full_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $MePath (Join-Path $BackupDir "migration_engine.py.bak") -Force
Copy-Item $OePath (Join-Path $BackupDir "obj_executor.py.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# ────────────────────────────────────────────────────────────────────
# [4/5] 적용 검증 (ZIP 풀린 직후 호출되므로 이미 덮어써짐)
# ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/5] 적용 후 검증" -ForegroundColor Cyan

$me_lines_after = (Get-Content $MePath | Measure-Object -Line).Lines
$oe_lines_after = (Get-Content $OePath | Measure-Object -Line).Lines

Write-Host "  migration_engine.py 라인: $me_lines_after (기대: 4633)"
Write-Host "  obj_executor.py 라인: $oe_lines_after (기대: 2045)"

$me_after = Get-Content $MePath -Raw
$oe_after = Get-Content $OePath -Raw

Write-Host ""
Write-Host "  마커 카운트 (적용 후):"
$expected = @{
    "v95_p23a" = @{me=5; oe=0}
    "v95_p23e" = @{me=0; oe=3}
    "v95_p23f" = @{me=2; oe=0}
    "v95_p26"  = @{me=3; oe=0}
    "v95_p27"  = @{me=2; oe=0}
    "v95_p28"  = @{me=2; oe=0}
    "v95_p29"  = @{me=0; oe=5}
    "v95_p30"  = @{me=1; oe=4}
    "v95_p31"  = @{me=5; oe=0}
}

$allOk = $true
foreach ($m in @("v95_p23a","v95_p23e","v95_p23f","v95_p26","v95_p27","v95_p28","v95_p29","v95_p30","v95_p31")) {
    $me_cnt = if($me_after){([regex]::Matches($me_after, $m)).Count}else{0}
    $oe_cnt = if($oe_after){([regex]::Matches($oe_after, $m)).Count}else{0}
    $exp_me = $expected[$m].me
    $exp_oe = $expected[$m].oe
    $me_ok = ($me_cnt -ge $exp_me)
    $oe_ok = ($oe_cnt -ge $exp_oe)
    if (-not ($me_ok -and $oe_ok)) { $allOk = $false }
    $mark = if ($me_ok -and $oe_ok) { "✓" } else { "✗" }
    Write-Host "    [$mark] $m : me=$me_cnt(기대$exp_me) oe=$oe_cnt(기대$exp_oe)"
}

# ────────────────────────────────────────────────────────────────────
# [5/5] 결과 + 백엔드 재시작 안내
# ────────────────────────────────────────────────────────────────────
Write-Host ""
if ($allOk) {
    Write-Host "═══════════════════════════════════════════════════════════"
    Write-Host "✅ 패치 적용 완료" -ForegroundColor Green
    Write-Host "═══════════════════════════════════════════════════════════"
    Write-Host ""
    Write-Host "⚠️ 중요: 백엔드 재시작 필수!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Python 은 이미 메모리에 로드된 코드를 사용하므로"
    Write-Host "디스크 파일만 바꿔도 적용 안 됩니다."
    Write-Host ""
    Write-Host "재시작 방법 (택일):" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  방법 A) PID 직접 종료 후 재시작:"
    Write-Host "    Stop-Process -Id <PID> -Force   # 위에서 본 PID"
    Write-Host "    cd $Root\backend"
    Write-Host "    .\start.bat   # 또는 본부장님 환경 시작 명령"
    Write-Host ""
    Write-Host "  방법 B) 모든 Python 종료 후 재시작:"
    Write-Host "    Stop-Process -Name python -Force"
    Write-Host "    cd $Root\backend"
    Write-Host "    .\start.bat"
    Write-Host ""
    Write-Host "재시작 후 검증:"
    Write-Host "  Get-Process python | Select-Object Id, StartTime"
    Write-Host "  → StartTime 이 방금 시각이면 재시작 성공"
    Write-Host ""
    Write-Host "재시작 후 재이관 + 결과 측정:"
    Write-Host "  - Document/ProductPhoto 'Production_Document' KeyError 해소 기대"
    Write-Host "  - 또는 [v95_p31-TRACEBACK] 라인이 로그에 노출되어 진짜 자리 확정"
} else {
    Write-Host "═══════════════════════════════════════════════════════════"
    Write-Host "❌ 일부 마커 누락 — ZIP 압축 해제 위치 확인 필요" -ForegroundColor Red
    Write-Host "═══════════════════════════════════════════════════════════"
    Write-Host ""
    Write-Host "ZIP 이 D:\project\ 에 풀렸는지 확인:"
    Write-Host "  Get-ChildItem 'D:\project\databridge_full\PATCH_*.md' | Select-Object Name, LastWriteTime"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\migration_engine.py.bak' '$MePath' -Force"
    Write-Host "  Copy-Item '$BackupDir\obj_executor.py.bak' '$OePath' -Force"
}
