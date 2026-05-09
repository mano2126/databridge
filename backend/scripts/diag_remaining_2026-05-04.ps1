# ════════════════════════════════════════════════════════════════════
# DataBridge — 잔여 본질 4건 진단 (2026-05-04, v95_p26~p29 적용 후)
# ════════════════════════════════════════════════════════════════════
# 진단 대상:
#   잔여 1: Document      TABLE — 'Production_Document' (코드 없는 에러)
#   잔여 2: ProductPhoto  TABLE — 'Production_ProductPhoto'
#   잔여 3: vProductModelInstructions VIEW — _Flat 테이블 환각
#   잔여 4: uSalesOrderHeader TRIG — 1362 미해소 (v29 정규식 미매치)
#
# 본부장님 모토: 추측 처방 금지, view tool 로 진짜 코드 100% 확인
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$LogPath = "D:\project\databridge_full\backend\logs\databridge_backend.log"
$OutDir  = "D:\project\databridge_full\backend\logs\diag_remaining_2026-05-04"

if (-not (Test-Path $LogPath)) {
    Write-Host "❌ 로그 없음: $LogPath" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge 잔여 본질 4건 진단"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$logFile = Get-Item $LogPath
Write-Host "로그 크기: $([math]::Round($logFile.Length / 1MB, 2)) MB"
Write-Host "분석 범위: 09:45 ~ 09:59 (이번 재이관 시간대)"
Write-Host ""

$logTail = Get-Content $LogPath -Tail 80000

# ────────────────────────────────────────────────────────────────────
# [1/5] 시간대 추출 (09:45~09:59)
# ────────────────────────────────────────────────────────────────────
Write-Host "[1/5] 09:45~09:59 시간대 라인" -ForegroundColor Cyan
$timeWindow = $logTail | Select-String -Pattern '09:4[5-9]:|09:5[0-9]:'
$tw_file = Join-Path $OutDir "01_time_window_09_45-09_59.txt"
"=== 09:45~09:59 ($($timeWindow.Count) 라인) ===" | Out-File $tw_file -Encoding UTF8
$timeWindow | ForEach-Object { $_.Line } | Out-File $tw_file -Append -Encoding UTF8
Write-Host "  ✓ $($timeWindow.Count) 라인 → $tw_file"

# ────────────────────────────────────────────────────────────────────
# [2/5] 잔여 1+2: Document / ProductPhoto 컨텍스트 (±60 라인)
# ────────────────────────────────────────────────────────────────────
Write-Host "[2/5] Document / ProductPhoto 실패 컨텍스트" -ForegroundColor Cyan
$tables = @("Document", "ProductPhoto", "Production_Document", "Production_ProductPhoto")
foreach ($tbl in $tables) {
    $outFile = Join-Path $OutDir "02_${tbl}.txt"
    "=== [$tbl] 컨텍스트 ===" | Out-File $outFile -Encoding UTF8
    $hits = $logTail | Select-String -Pattern "\b$tbl\b" -SimpleMatch
    "[전체 매치] $($hits.Count) 라인" | Out-File $outFile -Append -Encoding UTF8
    "" | Out-File $outFile -Append -Encoding UTF8

    # 최대 5개 매치 컨텍스트
    $sample = $hits | Select-Object -First 5
    foreach ($h in $sample) {
        $startIdx = [Math]::Max(0, $h.LineNumber - 60)
        $endIdx   = [Math]::Min($logTail.Count - 1, $h.LineNumber + 30)
        "" | Out-File $outFile -Append -Encoding UTF8
        "─── [라인 $($h.LineNumber)] 컨텍스트 (±60) ───────────────────" | Out-File $outFile -Append -Encoding UTF8
        $logTail[$startIdx..$endIdx] | Out-File $outFile -Append -Encoding UTF8
    }
    Write-Host "  ✓ $tbl → $outFile (매치 $($hits.Count))"
}

# ────────────────────────────────────────────────────────────────────
# [3/5] 잔여 3: vProductModelInstructions — AI 변환 결과
# ────────────────────────────────────────────────────────────────────
Write-Host "[3/5] vProductModelInstructions VIEW — AI 변환 DDL 추출" -ForegroundColor Cyan
$out3 = Join-Path $OutDir "03_vProductModelInstructions.txt"
"=== vProductModelInstructions VIEW 변환 DDL + 실패 ===" | Out-File $out3 -Encoding UTF8
"" | Out-File $out3 -Append -Encoding UTF8

$hits3 = $logTail | Select-String -Pattern 'vProductModelInstructions|ProductModelInstructions_Flat' -SimpleMatch
"[매치] $($hits3.Count) 라인" | Out-File $out3 -Append -Encoding UTF8
"" | Out-File $out3 -Append -Encoding UTF8

foreach ($h in $hits3) {
    $startIdx = [Math]::Max(0, $h.LineNumber - 80)
    $endIdx   = [Math]::Min($logTail.Count - 1, $h.LineNumber + 40)
    "" | Out-File $out3 -Append -Encoding UTF8
    "─── [라인 $($h.LineNumber)] (±80) ───────────────────" | Out-File $out3 -Append -Encoding UTF8
    $logTail[$startIdx..$endIdx] | Out-File $out3 -Append -Encoding UTF8
}
Write-Host "  ✓ vProductModelInstructions → $out3 (매치 $($hits3.Count))"

# ────────────────────────────────────────────────────────────────────
# [4/5] 잔여 4: uSalesOrderHeader — TRIGGER 변환 DDL
# ────────────────────────────────────────────────────────────────────
Write-Host "[4/5] uSalesOrderHeader TRIG — 변환 DDL + 1362 발생 컨텍스트" -ForegroundColor Cyan
$out4 = Join-Path $OutDir "04_uSalesOrderHeader.txt"
"=== uSalesOrderHeader TRIGGER 변환 + 1362 ===" | Out-File $out4 -Encoding UTF8
"" | Out-File $out4 -Append -Encoding UTF8

$hits4 = $logTail | Select-String -Pattern 'uSalesOrderHeader' -SimpleMatch
"[매치] $($hits4.Count) 라인" | Out-File $out4 -Append -Encoding UTF8
"" | Out-File $out4 -Append -Encoding UTF8

foreach ($h in $hits4) {
    $startIdx = [Math]::Max(0, $h.LineNumber - 100)
    $endIdx   = [Math]::Min($logTail.Count - 1, $h.LineNumber + 30)
    "" | Out-File $out4 -Append -Encoding UTF8
    "─── [라인 $($h.LineNumber)] (±100) ───────────────────" | Out-File $out4 -Append -Encoding UTF8
    $logTail[$startIdx..$endIdx] | Out-File $out4 -Append -Encoding UTF8
}

# v95_p29 작동 흔적 검증
"" | Out-File $out4 -Append -Encoding UTF8
"=== v95_p29 작동 흔적 (TRIGGER 처리 시 호출됐어야) ===" | Out-File $out4 -Append -Encoding UTF8
$p29_hits = $logTail | Select-String -Pattern 'v95_p29'
"[v95_p29 흔적] $($p29_hits.Count) 라인" | Out-File $out4 -Append -Encoding UTF8
$p29_hits | Select-Object -Last 30 | ForEach-Object { "  $($_.Line)" } | Out-File $out4 -Append -Encoding UTF8

Write-Host "  ✓ uSalesOrderHeader → $out4"
Write-Host "    v95_p29 흔적: $($p29_hits.Count) 라인 (0이면 처방 자체가 안 호출됨)"

# ────────────────────────────────────────────────────────────────────
# [5/5] 종합 요약
# ────────────────────────────────────────────────────────────────────
Write-Host "[5/5] 종합 요약" -ForegroundColor Cyan
$sum = Join-Path $OutDir "_SUMMARY.txt"
"═══════════════════════════════════════════════════════════════" | Out-File $sum -Encoding UTF8
"DataBridge 잔여 본질 4건 진단 — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File $sum -Append -Encoding UTF8
"═══════════════════════════════════════════════════════════════" | Out-File $sum -Append -Encoding UTF8
"" | Out-File $sum -Append -Encoding UTF8

"[v95_p26~p29 적용 효과 (이전 대비)]" | Out-File $sum -Append -Encoding UTF8
"  이전 실패: 35건 → 이번 실패: 4건 (88% 해소)" | Out-File $sum -Append -Encoding UTF8
"" | Out-File $sum -Append -Encoding UTF8

"[잔여 본질 매치 카운트]" | Out-File $sum -Append -Encoding UTF8
foreach ($t in @("Document", "ProductPhoto", "vProductModelInstructions",
                 "ProductModelInstructions_Flat", "uSalesOrderHeader")) {
    $cnt = ($logTail | Select-String -Pattern "\b$t\b" -SimpleMatch).Count
    "  - $t : $cnt 매치" | Out-File $sum -Append -Encoding UTF8
}
"" | Out-File $sum -Append -Encoding UTF8

"[v95_p29 작동 검증]" | Out-File $sum -Append -Encoding UTF8
"  - v95_p29 흔적: $($p29_hits.Count) 라인" | Out-File $sum -Append -Encoding UTF8
$p29_5_hits = $logTail | Select-String -Pattern 'v95_p29-#5'
$p29_6_hits = $logTail | Select-String -Pattern 'v95_p29-#6'
"  - v95_p29-#5 (AFTER→BEFORE) 흔적: $($p29_5_hits.Count) 라인" | Out-File $sum -Append -Encoding UTF8
"  - v95_p29-#6 (case 복원) 흔적: $($p29_6_hits.Count) 라인" | Out-File $sum -Append -Encoding UTF8
"" | Out-File $sum -Append -Encoding UTF8

"[다음 단계]" | Out-File $sum -Append -Encoding UTF8
"  $OutDir 폴더 압축해서 새 메시지에 첨부" | Out-File $sum -Append -Encoding UTF8

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "✅ 진단 완료" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""
Write-Host "📁 출력: $OutDir" -ForegroundColor Yellow
Write-Host ""
Write-Host "📦 ZIP 압축:" -ForegroundColor Yellow
Write-Host "  Compress-Archive -Path '$OutDir\*' -DestinationPath 'D:\project\diag_remaining_2026-05-04.zip' -Force"
Write-Host ""
Write-Host "─── 요약 ───────────────────────────────────────────────"
Get-Content $sum | Write-Host
