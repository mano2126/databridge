# ════════════════════════════════════════════════════════════════════
# DataBridge — v95_p31 적용 후 잔여 6건 진단 (2026-05-04)
# ════════════════════════════════════════════════════════════════════
# 본부장님 환경 시간대: 12:05 ~ 12:18
#
# 이번 진단 핵심:
#   [1] v95_p31-TRACEBACK 로그 추출 — 진짜 자리 100% 노출 (Document/ProductPhoto)
#   [2] vJobCandidateEducation/_flat AI 변환 진짜 DDL
#   [3] vProductModelInstructions/_Instruction AI 변환 진짜 DDL
#   [4] uSalesOrderHeader/uPurchaseOrderDetail 1146 자기참조 변환 결과
#   [5] v95_p31 (a) 안전망 작동 검증
#
# 본부장님 모토: 추측 처방 금지, view tool 로 진짜 자리 확인 후 처방
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$LogPath = "D:\project\databridge_full\backend\logs\databridge_backend.log"
$OutDir  = "D:\project\databridge_full\backend\logs\diag_p31_2026-05-04"

if (-not (Test-Path $LogPath)) {
    Write-Host "❌ 로그 없음: $LogPath" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p31 후 잔여 6건 진단"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$logFile = Get-Item $LogPath
Write-Host "로그 크기: $([math]::Round($logFile.Length / 1MB, 2)) MB"
Write-Host "분석 범위: 12:05 ~ 12:19 (이번 재이관)"
Write-Host ""

$logTail = Get-Content $LogPath -Tail 100000

# ────────────────────────────────────────────────────────────────────
# [1/6] 시간대 추출 (12:05~12:19)
# ────────────────────────────────────────────────────────────────────
Write-Host "[1/6] 12:05~12:19 시간대 라인" -ForegroundColor Cyan
$timeWindow = $logTail | Select-String -Pattern '12:0[5-9]:|12:1[0-9]:'
$tw_file = Join-Path $OutDir "01_time_window.txt"
"=== 12:05~12:19 ($($timeWindow.Count) 라인) ===" | Out-File $tw_file -Encoding UTF8
$timeWindow | ForEach-Object { $_.Line } | Out-File $tw_file -Append -Encoding UTF8
Write-Host "  ✓ $($timeWindow.Count) 라인 → $tw_file"

# ────────────────────────────────────────────────────────────────────
# [2/6] v95_p31-TRACEBACK 추출 — 가장 중요!
# ────────────────────────────────────────────────────────────────────
Write-Host "[2/6] v95_p31-TRACEBACK 추출 (진짜 자리 노출)" -ForegroundColor Cyan
$out2 = Join-Path $OutDir "02_traceback.txt"
"=== v95_p31-TRACEBACK 라인 + 그 다음 30라인 (Python stack trace) ===" | Out-File $out2 -Encoding UTF8
"" | Out-File $out2 -Append -Encoding UTF8

# v95_p31-TRACEBACK 매치
$tb_hits = $logTail | Select-String -Pattern 'v95_p31-TRACEBACK'
"[v95_p31-TRACEBACK 흔적] $($tb_hits.Count) 라인" | Out-File $out2 -Append -Encoding UTF8
"" | Out-File $out2 -Append -Encoding UTF8

if ($tb_hits.Count -eq 0) {
    "  ⚠️ v95_p31-TRACEBACK 흔적 0건 — 백엔드 재시작 안 했거나 패치 미적용 가능성" | Out-File $out2 -Append -Encoding UTF8
} else {
    foreach ($h in $tb_hits) {
        $startIdx = [Math]::Max(0, $h.LineNumber - 2)
        $endIdx   = [Math]::Min($logTail.Count - 1, $h.LineNumber + 30)
        "" | Out-File $out2 -Append -Encoding UTF8
        "─── 라인 $($h.LineNumber) ─────────────────────" | Out-File $out2 -Append -Encoding UTF8
        $logTail[$startIdx..$endIdx] | Out-File $out2 -Append -Encoding UTF8
    }
}

# 일반 Traceback (Python stack trace) 검색
"" | Out-File $out2 -Append -Encoding UTF8
"=== 일반 Python Traceback 패턴 ===" | Out-File $out2 -Append -Encoding UTF8
$py_tb = $logTail | Select-String -Pattern 'Traceback \(most recent call|File ".*\.py", line \d+|KeyError:'
"[Python Traceback/KeyError 매치] $($py_tb.Count) 라인" | Out-File $out2 -Append -Encoding UTF8
$py_tb | Select-Object -First 50 | ForEach-Object { "  $($_.Line)" } | Out-File $out2 -Append -Encoding UTF8

Write-Host "  ✓ Traceback 진단 → $out2"
Write-Host "    v95_p31-TRACEBACK 흔적: $($tb_hits.Count) 라인 (>0 이면 진짜 자리 노출)"
Write-Host "    Python Traceback 매치: $($py_tb.Count) 라인"

# ────────────────────────────────────────────────────────────────────
# [3/6] v95_p31 (a) 안전망 작동 검증
# ────────────────────────────────────────────────────────────────────
Write-Host "[3/6] v95_p31 (a) 안전망 작동 검증" -ForegroundColor Cyan
$out3 = Join-Path $OutDir "03_v95_p31_a_check.txt"
"=== v95_p31 (a) swap 후 dict 6개 재등록 흔적 ===" | Out-File $out3 -Encoding UTF8

$p31a = $logTail | Select-String -Pattern 'v95_p31-a'
"[v95_p31-a 흔적] $($p31a.Count) 라인 (>0 이면 (a) 처방 작동)" | Out-File $out3 -Append -Encoding UTF8
"" | Out-File $out3 -Append -Encoding UTF8
$p31a | Select-Object -First 20 | ForEach-Object { "  $($_.Line)" } | Out-File $out3 -Append -Encoding UTF8

# Document/ProductPhoto 직전 (a) 가 호출됐는지
"" | Out-File $out3 -Append -Encoding UTF8
"=== Document/ProductPhoto 처리 직전 (a) 흔적 ===" | Out-File $out3 -Append -Encoding UTF8
foreach ($t in @("Production_Document", "Production_ProductPhoto")) {
    $hits = $logTail | Select-String -Pattern "v95_p31-a.*$t"
    "  [$t] (a) 호출: $($hits.Count) 건" | Out-File $out3 -Append -Encoding UTF8
}
Write-Host "  ✓ v95_p31 (a) 검증 → $out3"

# ────────────────────────────────────────────────────────────────────
# [4/6] AI 환각 — vJobCandidateEducation _flat
# ────────────────────────────────────────────────────────────────────
Write-Host "[4/6] vJobCandidateEducation _flat 환각" -ForegroundColor Cyan
$out4 = Join-Path $OutDir "04_vJobCandidateEducation.txt"
"=== vJobCandidateEducation AI 변환 + _flat 환각 ===" | Out-File $out4 -Encoding UTF8

$tw_lines = Get-Content $tw_file
$matches4 = @()
for ($i = 0; $i -lt $tw_lines.Count; $i++) {
    if ($tw_lines[$i] -like "*vJobCandidateEducation*") {
        $matches4 += $i
    }
}
"[매치] $($matches4.Count) 라인" | Out-File $out4 -Append -Encoding UTF8
"" | Out-File $out4 -Append -Encoding UTF8

if ($matches4.Count -gt 0) {
    $startIdx = [Math]::Max(0, $matches4[0] - 50)
    $endIdx   = [Math]::Min($tw_lines.Count - 1, $matches4[-1] + 50)
    $tw_lines[$startIdx..$endIdx] | Out-File $out4 -Append -Encoding UTF8
}
Write-Host "  ✓ vJobCandidateEducation → $out4 (매치 $($matches4.Count))"

# ────────────────────────────────────────────────────────────────────
# [5/6] AI 환각 — vProductModelInstructions _Instruction
# ────────────────────────────────────────────────────────────────────
Write-Host "[5/6] vProductModelInstructions _Instruction 환각" -ForegroundColor Cyan
$out5 = Join-Path $OutDir "05_vProductModelInstructions.txt"
"=== vProductModelInstructions AI 변환 + _Instruction 환각 ===" | Out-File $out5 -Encoding UTF8

$matches5 = @()
for ($i = 0; $i -lt $tw_lines.Count; $i++) {
    if ($tw_lines[$i] -like "*vProductModelInstructions*" -or `
        $tw_lines[$i] -like "*Production_ProductModelInstruction*" -or `
        $tw_lines[$i] -like "*ProductModel_Flat*" -or `
        $tw_lines[$i] -like "*ProductModelInstruction_*") {
        $matches5 += $i
    }
}
"[매치] $($matches5.Count) 라인" | Out-File $out5 -Append -Encoding UTF8
"" | Out-File $out5 -Append -Encoding UTF8

if ($matches5.Count -gt 0) {
    $startIdx = [Math]::Max(0, $matches5[0] - 50)
    $endIdx   = [Math]::Min($tw_lines.Count - 1, $matches5[-1] + 50)
    $tw_lines[$startIdx..$endIdx] | Out-File $out5 -Append -Encoding UTF8
}
Write-Host "  ✓ vProductModelInstructions → $out5 (매치 $($matches5.Count))"

# ────────────────────────────────────────────────────────────────────
# [6/6] uSalesOrderHeader / uPurchaseOrderDetail 1146 자기참조
# ────────────────────────────────────────────────────────────────────
Write-Host "[6/6] uSalesOrderHeader / uPurchaseOrderDetail 1146" -ForegroundColor Cyan
$out6 = Join-Path $OutDir "06_trigger_1146.txt"
"=== 트리거 1146 자기참조 + v95_p30-#5 작동 검증 ===" | Out-File $out6 -Encoding UTF8
"" | Out-File $out6 -Append -Encoding UTF8

# v95_p30-#5 흔적
$v30_5 = $logTail | Select-String -Pattern 'v95_p30-#5'
"[v95_p30-#5 (NEW row 패턴 확장) 흔적] $($v30_5.Count) 라인" | Out-File $out6 -Append -Encoding UTF8
$v30_5 | ForEach-Object { "  $($_.Line)" } | Out-File $out6 -Append -Encoding UTF8

# uSalesOrderHeader / uPurchaseOrderDetail 매치
foreach ($t in @("uSalesOrderHeader", "uPurchaseOrderDetail")) {
    "" | Out-File $out6 -Append -Encoding UTF8
    "=== [$t] 매치 ===" | Out-File $out6 -Append -Encoding UTF8
    $matches_t = @()
    for ($i = 0; $i -lt $tw_lines.Count; $i++) {
        if ($tw_lines[$i] -like "*$t*") {
            $matches_t += $i
        }
    }
    "[매치] $($matches_t.Count) 라인" | Out-File $out6 -Append -Encoding UTF8

    if ($matches_t.Count -gt 0) {
        $startIdx = [Math]::Max(0, $matches_t[0] - 30)
        $endIdx   = [Math]::Min($tw_lines.Count - 1, $matches_t[-1] + 30)
        "" | Out-File $out6 -Append -Encoding UTF8
        $tw_lines[$startIdx..$endIdx] | Out-File $out6 -Append -Encoding UTF8
    }
}
Write-Host "  ✓ 트리거 1146 → $out6"

# ────────────────────────────────────────────────────────────────────
# [7/7] 종합 요약
# ────────────────────────────────────────────────────────────────────
$sum = Join-Path $OutDir "_SUMMARY.txt"
"═══════════════════════════════════════════════════════════════" | Out-File $sum -Encoding UTF8
"DataBridge v95_p31 후 잔여 6건 진단 — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File $sum -Append -Encoding UTF8
"═══════════════════════════════════════════════════════════════" | Out-File $sum -Append -Encoding UTF8
"" | Out-File $sum -Append -Encoding UTF8

"[v95_p31 적용 후 결과]" | Out-File $sum -Append -Encoding UTF8
"  잔여 1: Document KeyError (메시지 비어있음 = 변형)" | Out-File $sum -Append -Encoding UTF8
"  잔여 2: ProductPhoto 'Production_ProductPhoto' (잔존)" | Out-File $sum -Append -Encoding UTF8
"  잔여 3: vJobCandidateEducation _flat 환각 (변형)" | Out-File $sum -Append -Encoding UTF8
"  잔여 4: vProductModelInstructions _Instruction 환각 (변형)" | Out-File $sum -Append -Encoding UTF8
"  잔여 5: uSalesOrderHeader 1146 자기참조 (잔존)" | Out-File $sum -Append -Encoding UTF8
"  잔여 6: uPurchaseOrderDetail 1146 자기참조 (회귀!)" | Out-File $sum -Append -Encoding UTF8
"" | Out-File $sum -Append -Encoding UTF8

"[v95_p31 작동 검증]" | Out-File $sum -Append -Encoding UTF8
"  - v95_p31-TRACEBACK 흔적: $($tb_hits.Count) 라인" | Out-File $sum -Append -Encoding UTF8
"  - v95_p31-a 흔적: $($p31a.Count) 라인" | Out-File $sum -Append -Encoding UTF8
"  - Python Traceback 매치: $($py_tb.Count) 라인" | Out-File $sum -Append -Encoding UTF8
"  - v95_p30-#5 흔적: $($v30_5.Count) 라인" | Out-File $sum -Append -Encoding UTF8
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
Write-Host "  Compress-Archive -Path '$OutDir\*' -DestinationPath 'D:\project\diag_p31_2026-05-04.zip' -Force"
Write-Host ""
Write-Host "─── 요약 ───────────────────────────────────────────────"
Get-Content $sum | Write-Host
