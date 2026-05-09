$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v93_LIB3 hotfix1 — JS Syntax Error 처방" -ForegroundColor Cyan
Write-Host "  본부장님 호소: 'vue-router SyntaxError: Invalid or unexpected token'" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v93_LIB3_hotfix1_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$rel = "frontend\src\pages\operatorLibraryData.js"
$src = Join-Path $ProjectRoot $rel
if (Test-Path $src) {
    $dst = Join-Path $BackupRoot $rel
    New-Item -Path (Split-Path -Parent $dst) -ItemType Directory -Force | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst -Force
}
$sf = Join-Path $PatchSrc $rel
Copy-Item -LiteralPath $sf -Destination $src -Force
Write-Host "  + $rel (수정됨)" -ForegroundColor Green

Write-Host "`n✓ hotfix1 적용 완료" -ForegroundColor Green

Write-Host "`n원인:" -ForegroundColor Cyan
Write-Host "  PowerShell 의 backtick newline 표현 ``n 을 JavaScript template literal" -ForegroundColor White
Write-Host "  (``...``) 안에 그대로 넣었더니, JS 파서가 backtick 을 template 종료로 해석" -ForegroundColor White
Write-Host "  → ESM 동적 import 실패 → vue-router SyntaxError" -ForegroundColor White

Write-Host "`n수정 위치:" -ForegroundColor Cyan
Write-Host "  L1805: ops_email_alert" -ForegroundColor White
Write-Host '         "실패 Job 발생:`\`n"  →  "실패 Job 발생:\`r\`n"' -ForegroundColor DarkGray
Write-Host "         (JS escape 처리 추가 → PowerShell 에서 정상 ``r``n 으로 해석됨)" -ForegroundColor DarkGray

Write-Host "`n검증:" -ForegroundColor Cyan
Write-Host "  Ctrl+Shift+R → 콘솔에 SyntaxError 사라짐 → 운영자 라이브러리 페이지 정상 표시" -ForegroundColor White

Write-Host "`n⚠ frontend 파일 1개만 교체 — 백엔드 영향 없음 (Vite HMR 자동)" -ForegroundColor Yellow
Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
