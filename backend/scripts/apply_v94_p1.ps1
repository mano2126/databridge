$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v94_p1 — AdvisorPanel 자동 저장 (적용/거부 토글 처방)" -ForegroundColor Cyan
Write-Host "  본부장님 호소: '토글 클릭해도 OFF 로만 보여, 동작하는지 모르겠다'" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v94_p1_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$files = @(
    "frontend\src\components\advisor\AdvisorPanel.vue"
)

foreach ($rel in $files) {
    $src = Join-Path $ProjectRoot $rel
    if (Test-Path $src) {
        $dst = Join-Path $BackupRoot $rel
        New-Item -Path (Split-Path -Parent $dst) -ItemType Directory -Force | Out-Null
        Copy-Item -LiteralPath $src -Destination $dst -Force
    }
    $sf = Join-Path $PatchSrc $rel
    if (Test-Path $sf) {
        New-Item -Path (Split-Path -Parent $src) -ItemType Directory -Force | Out-Null
        Copy-Item -LiteralPath $sf -Destination $src -Force
        Write-Host "  + $rel" -ForegroundColor Green
    }
}

Write-Host "`n✓ v94_p1 적용 완료" -ForegroundColor Green

Write-Host "`n원인 진단:" -ForegroundColor Cyan
Write-Host "  AdvisorPanel.vue 의 emitDecisions() 가 부모 form 에 emit 만 했음" -ForegroundColor White
Write-Host "  → 백엔드 /advisor/apply-decision 호출은 submit() 시점에만 일어남" -ForegroundColor White
Write-Host "  → 사용자가 클릭해도 즉시 저장이 안 돼서 '토글이 안 먹는 것처럼' 보였음" -ForegroundColor White

Write-Host "`n처방:" -ForegroundColor Cyan
Write-Host "  1. 토글 클릭 → 800ms debounce → 백엔드 /advisor/apply-decision 자동 호출" -ForegroundColor White
Write-Host "  2. 저장 상태 시각 인디케이터 (선택 카운터 옆):" -ForegroundColor White
Write-Host "     · '저장 중...' (파란색 + 깜빡)" -ForegroundColor DarkGray
Write-Host "     · '✓ 자동 저장됨 (방금/5초 전/1분 전)' (초록색)" -ForegroundColor DarkGray
Write-Host "     · '✗ 저장 실패 (재시도 필요)' (빨강 + 에러 메시지 hover)" -ForegroundColor DarkGray
Write-Host "  3. 매초 '방금/N초 전' 갱신" -ForegroundColor White
Write-Host "  4. 컴포넌트 종료 시 ticker / debounce 타이머 정리 (메모리 leak 방지)" -ForegroundColor White

Write-Host "`n검증 시나리오:" -ForegroundColor Yellow
Write-Host "  1. Ctrl+Shift+R" -ForegroundColor White
Write-Host "  2. JobWizard → 4단계 (AI DBA Consultant) 진입" -ForegroundColor White
Write-Host "  3. 분석 시작 → 권고 받기" -ForegroundColor White
Write-Host "  4. 체크박스 클릭 (적용) → 0.8초 후 '저장 중...' → '✓ 자동 저장됨'" -ForegroundColor Green
Write-Host "  5. 체크 해제 → 다시 0.8초 후 '✓ 자동 저장됨'" -ForegroundColor Green
Write-Host "  6. 백엔드 로그에 '[advisor.apply-decision/P5] stats={...}' 확인" -ForegroundColor White

Write-Host "`n⚠ 백엔드 변경 없음 — Ctrl+Shift+R 만으로 반영" -ForegroundColor Yellow
Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
