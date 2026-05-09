# ════════════════════════════════════════════════════════════════════
# DataBridge — 잔여 본질 D/E/F 진단 (2026-05-04)
# ════════════════════════════════════════════════════════════════════
# 본질 D: VIEW 의존성 (1146) — vJobCandidateEducation, vProductModelInstructions
# 본질 E: TRIG NEW row in AFTER (1362) — uSalesOrderHeader, uPurchaseOrderDetail
# 본질 F: iuPerson (1146) — person_person 소문자
#
# 본부장님 모토: 추측 처방 금지, view tool 로 진짜 코드 확인 후 처방
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$LogPath = "D:\project\databridge_full\backend\logs\databridge_backend.log"
$OutDir  = "D:\project\databridge_full\backend\logs\diag_DEF_2026-05-04"

if (-not (Test-Path $LogPath)) {
    Write-Host "❌ 로그 파일 없음: $LogPath" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge D/E/F 본질 진단 시작"
Write-Host "로그: $LogPath"
Write-Host "출력: $OutDir"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

# ────────────────────────────────────────────────────────────────────
# [1/6] 로그 크기 확인
# ────────────────────────────────────────────────────────────────────
$logFile = Get-Item $LogPath
$logSizeMB = [math]::Round($logFile.Length / 1MB, 2)
Write-Host "[1/6] 로그 크기: $logSizeMB MB" -ForegroundColor Cyan

# 진단 대상 라인 (최근 50000 라인 — 충분히 넓게)
$tailCount = 50000
Write-Host "      최근 $tailCount 라인 분석"
Write-Host ""

# 메모리 효율 위해 한 번 읽고 재사용
$logTail = Get-Content $LogPath -Tail $tailCount

# ────────────────────────────────────────────────────────────────────
# [2/6] 본질 D: VIEW 의존성 진단
# ────────────────────────────────────────────────────────────────────
Write-Host "[2/6] 본질 D: VIEW 의존성 진단" -ForegroundColor Cyan

$viewTargets = @("vJobCandidateEducation", "vProductModelInstructions")
foreach ($vw in $viewTargets) {
    $outFile = Join-Path $OutDir "D_VIEW_$vw.txt"
    "═══ 본질 D: $vw ═══" | Out-File $outFile -Encoding UTF8
    "" | Out-File $outFile -Append -Encoding UTF8

    # 해당 VIEW 와 관련된 모든 라인 (DEPLOY-TRACE 포함)
    $hits = $logTail | Select-String -Pattern $vw -SimpleMatch -CaseSensitive:$false
    "[전체 매치 라인 수] $($hits.Count)" | Out-File $outFile -Append -Encoding UTF8
    "" | Out-File $outFile -Append -Encoding UTF8

    if ($hits.Count -gt 0) {
        # 마지막 시도 (가장 최근) 의 컨텍스트 ±50 라인 추출
        $lastHit = $hits[-1]
        $lineNum = $lastHit.LineNumber
        $startIdx = [Math]::Max(0, $lineNum - 50)
        $endIdx = [Math]::Min($logTail.Count - 1, $lineNum + 50)

        "[최근 시도 컨텍스트 (라인 $startIdx ~ $endIdx)]" | Out-File $outFile -Append -Encoding UTF8
        "─────────────────────────────────────────────────────────" | Out-File $outFile -Append -Encoding UTF8
        $logTail[$startIdx..$endIdx] | Out-File $outFile -Append -Encoding UTF8
    }

    Write-Host "      ✓ $vw → $outFile (매치 $($hits.Count)건)"
}
Write-Host ""

# ────────────────────────────────────────────────────────────────────
# [3/6] 본질 E: TRIG NEW row in AFTER 진단
# ────────────────────────────────────────────────────────────────────
Write-Host "[3/6] 본질 E: TRIG NEW row in AFTER 진단" -ForegroundColor Cyan

$trigTargets = @("uSalesOrderHeader", "uPurchaseOrderDetail")
foreach ($tg in $trigTargets) {
    $outFile = Join-Path $OutDir "E_TRIG_$tg.txt"
    "═══ 본질 E: $tg ═══" | Out-File $outFile -Encoding UTF8
    "" | Out-File $outFile -Append -Encoding UTF8

    $hits = $logTail | Select-String -Pattern $tg -SimpleMatch -CaseSensitive:$false
    "[전체 매치 라인 수] $($hits.Count)" | Out-File $outFile -Append -Encoding UTF8
    "" | Out-File $outFile -Append -Encoding UTF8

    if ($hits.Count -gt 0) {
        $lastHit = $hits[-1]
        $lineNum = $lastHit.LineNumber
        $startIdx = [Math]::Max(0, $lineNum - 50)
        $endIdx = [Math]::Min($logTail.Count - 1, $lineNum + 50)

        "[최근 시도 컨텍스트 (라인 $startIdx ~ $endIdx)]" | Out-File $outFile -Append -Encoding UTF8
        "─────────────────────────────────────────────────────────" | Out-File $outFile -Append -Encoding UTF8
        $logTail[$startIdx..$endIdx] | Out-File $outFile -Append -Encoding UTF8
    }

    Write-Host "      ✓ $tg → $outFile (매치 $($hits.Count)건)"
}

# 1362 에러 전체 패턴 추출 (본부장님 환경에서 실제 발생한 모든 1362)
$err1362 = $logTail | Select-String -Pattern "1362" -SimpleMatch
$out1362 = Join-Path $OutDir "E_ALL_1362_errors.txt"
"═══ 1362 에러 발생 전체 라인 ($($err1362.Count)건) ═══" | Out-File $out1362 -Encoding UTF8
"" | Out-File $out1362 -Append -Encoding UTF8
$err1362 | ForEach-Object {
    "[라인 $($_.LineNumber)] $($_.Line)" | Out-File $out1362 -Append -Encoding UTF8
} 
Write-Host "      ✓ 전체 1362 에러 → $out1362 ($($err1362.Count)건)"
Write-Host ""

# ────────────────────────────────────────────────────────────────────
# [4/6] 본질 F: iuPerson / person_person 진단
# ────────────────────────────────────────────────────────────────────
Write-Host "[4/6] 본질 F: iuPerson / person_person 진단" -ForegroundColor Cyan

$fTargets = @("iuPerson", "person_person", "Person_Person")
foreach ($ft in $fTargets) {
    $outFile = Join-Path $OutDir ("F_" + ($ft -replace "[^a-zA-Z0-9_]", "_") + ".txt")
    "═══ 본질 F: $ft ═══" | Out-File $outFile -Encoding UTF8
    "" | Out-File $outFile -Append -Encoding UTF8

    # 대소문자 구분 — Person_Person 과 person_person 구분 위해
    $hits = $logTail | Select-String -Pattern $ft -SimpleMatch -CaseSensitive
    "[전체 매치 라인 수 (대소문자 구분)] $($hits.Count)" | Out-File $outFile -Append -Encoding UTF8
    "" | Out-File $outFile -Append -Encoding UTF8

    if ($hits.Count -gt 0) {
        $lastHit = $hits[-1]
        $lineNum = $lastHit.LineNumber
        $startIdx = [Math]::Max(0, $lineNum - 30)
        $endIdx = [Math]::Min($logTail.Count - 1, $lineNum + 30)

        "[최근 시도 컨텍스트 (라인 $startIdx ~ $endIdx)]" | Out-File $outFile -Append -Encoding UTF8
        "─────────────────────────────────────────────────────────" | Out-File $outFile -Append -Encoding UTF8
        $logTail[$startIdx..$endIdx] | Out-File $outFile -Append -Encoding UTF8
    }

    Write-Host "      ✓ $ft → $outFile (매치 $($hits.Count)건)"
}
Write-Host ""

# ────────────────────────────────────────────────────────────────────
# [5/6] 1146 에러 전체 패턴 (D/F 공통)
# ────────────────────────────────────────────────────────────────────
Write-Host "[5/6] 1146 에러 전체 패턴 추출" -ForegroundColor Cyan

$err1146 = $logTail | Select-String -Pattern "1146" -SimpleMatch
$out1146 = Join-Path $OutDir "DF_ALL_1146_errors.txt"
"═══ 1146 에러 발생 전체 라인 ($($err1146.Count)건) ═══" | Out-File $out1146 -Encoding UTF8
"" | Out-File $out1146 -Append -Encoding UTF8
$err1146 | ForEach-Object {
    "[라인 $($_.LineNumber)] $($_.Line)" | Out-File $out1146 -Append -Encoding UTF8
}
Write-Host "      ✓ 전체 1146 에러 → $out1146 ($($err1146.Count)건)"
Write-Host ""

# ────────────────────────────────────────────────────────────────────
# [6/6] 요약 리포트
# ────────────────────────────────────────────────────────────────────
Write-Host "[6/6] 요약 리포트 생성" -ForegroundColor Cyan

$summaryFile = Join-Path $OutDir "_SUMMARY.txt"
"═══════════════════════════════════════════════════════════════" | Out-File $summaryFile -Encoding UTF8
"DataBridge D/E/F 본질 진단 요약 — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File $summaryFile -Append -Encoding UTF8
"═══════════════════════════════════════════════════════════════" | Out-File $summaryFile -Append -Encoding UTF8
"" | Out-File $summaryFile -Append -Encoding UTF8
"로그 파일: $LogPath ($logSizeMB MB)" | Out-File $summaryFile -Append -Encoding UTF8
"분석 범위: 최근 $tailCount 라인" | Out-File $summaryFile -Append -Encoding UTF8
"" | Out-File $summaryFile -Append -Encoding UTF8
"[본질 D — VIEW 의존성]" | Out-File $summaryFile -Append -Encoding UTF8
foreach ($vw in $viewTargets) {
    $cnt = ($logTail | Select-String -Pattern $vw -SimpleMatch -CaseSensitive:$false).Count
    "  - $vw : $cnt 매치" | Out-File $summaryFile -Append -Encoding UTF8
}
"" | Out-File $summaryFile -Append -Encoding UTF8
"[본질 E — TRIG NEW row in AFTER]" | Out-File $summaryFile -Append -Encoding UTF8
foreach ($tg in $trigTargets) {
    $cnt = ($logTail | Select-String -Pattern $tg -SimpleMatch -CaseSensitive:$false).Count
    "  - $tg : $cnt 매치" | Out-File $summaryFile -Append -Encoding UTF8
}
"  - 전체 1362 에러: $($err1362.Count)건" | Out-File $summaryFile -Append -Encoding UTF8
"" | Out-File $summaryFile -Append -Encoding UTF8
"[본질 F — iuPerson / person_person]" | Out-File $summaryFile -Append -Encoding UTF8
foreach ($ft in $fTargets) {
    $cnt = ($logTail | Select-String -Pattern $ft -SimpleMatch -CaseSensitive).Count
    "  - $ft (대소문자 구분): $cnt 매치" | Out-File $summaryFile -Append -Encoding UTF8
}
"" | Out-File $summaryFile -Append -Encoding UTF8
"[1146 에러 (D/F 공통)]" | Out-File $summaryFile -Append -Encoding UTF8
"  - 전체 1146 에러: $($err1146.Count)건" | Out-File $summaryFile -Append -Encoding UTF8
"" | Out-File $summaryFile -Append -Encoding UTF8
"═══════════════════════════════════════════════════════════════" | Out-File $summaryFile -Append -Encoding UTF8
"본부장님 — 다음 단계:" | Out-File $summaryFile -Append -Encoding UTF8
"  1) $OutDir 폴더 압축해서 새 세션에 첨부" | Out-File $summaryFile -Append -Encoding UTF8
"  2) Claude 가 진짜 본질 분석 후 단일 본질 단일 처방 시작" | Out-File $summaryFile -Append -Encoding UTF8
"═══════════════════════════════════════════════════════════════" | Out-File $summaryFile -Append -Encoding UTF8

Write-Host "      ✓ 요약 → $summaryFile"
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "✅ 진단 완료" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""
Write-Host "📁 출력 폴더: $OutDir" -ForegroundColor Yellow
Write-Host ""
Write-Host "📦 다음 단계 — 폴더를 ZIP 으로 압축해서 새 세션에 전달:" -ForegroundColor Yellow
Write-Host "   Compress-Archive -Path '$OutDir\*' -DestinationPath 'D:\project\diag_DEF_2026-05-04.zip' -Force"
Write-Host ""

# 요약 화면 출력
Write-Host "─── 요약 ───────────────────────────────────────────────"
Get-Content $summaryFile | Write-Host
