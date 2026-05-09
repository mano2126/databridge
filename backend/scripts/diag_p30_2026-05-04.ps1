# ════════════════════════════════════════════════════════════════════
# DataBridge — v95_p30 적용 후 잔여 5건 진단 (2026-05-04)
# ════════════════════════════════════════════════════════════════════
# 본부장님 환경 시간대: 10:51 ~ 11:05
#
# 진단 본질 (모두 추측 금지 — 로그에서 진짜 자리 확인):
#   잔여 1: Document       — 'Production_Document' KeyError 진짜 자리
#   잔여 2: ProductPhoto   — 'Production_ProductPhoto' KeyError 진짜 자리
#   잔여 3: vJobCandidateEducation — _data 환각 (AI 변환 DDL)
#   잔여 4: vProductModelInstructions — _Flattened 환각 (AI 변환 DDL)
#   잔여 5: uSalesOrderHeader — 1362 → 1146 변형 (Sales_Salesorderheader 자기참조)
#
# v95_p30 작동 검증:
#   - v95_p30-#5 (NEW row 패턴 확장) 흔적 카운트
#   - v95_p30 setdefault 적용 후에도 KeyError 발생 = 다른 자리 본질
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$LogPath = "D:\project\databridge_full\backend\logs\databridge_backend.log"
$OutDir  = "D:\project\databridge_full\backend\logs\diag_p30_2026-05-04"

if (-not (Test-Path $LogPath)) {
    Write-Host "❌ 로그 없음: $LogPath" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p30 후 잔여 5건 진단"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$logFile = Get-Item $LogPath
Write-Host "로그 크기: $([math]::Round($logFile.Length / 1MB, 2)) MB"
Write-Host "분석 범위: 10:51 ~ 11:06 (이번 재이관)"
Write-Host ""

# 시간대 필터링은 라인 단위 — 충분한 tail 확보
$logTail = Get-Content $LogPath -Tail 100000

# ────────────────────────────────────────────────────────────────────
# [1/7] 시간대 추출 (10:51~11:06)
# ────────────────────────────────────────────────────────────────────
Write-Host "[1/7] 10:51~11:06 시간대 라인" -ForegroundColor Cyan
$timeWindow = $logTail | Select-String -Pattern '10:5[1-9]:|11:0[0-6]:'
$tw_file = Join-Path $OutDir "01_time_window.txt"
"=== 10:51~11:06 ($($timeWindow.Count) 라인) ===" | Out-File $tw_file -Encoding UTF8
$timeWindow | ForEach-Object { $_.Line } | Out-File $tw_file -Append -Encoding UTF8
Write-Host "  ✓ $($timeWindow.Count) 라인 → $tw_file"

# ────────────────────────────────────────────────────────────────────
# [2/7] Document/ProductPhoto - 진짜 stack trace 추적
# ────────────────────────────────────────────────────────────────────
Write-Host "[2/7] Document/ProductPhoto KeyError 진짜 자리" -ForegroundColor Cyan
$out2 = Join-Path $OutDir "02_keyerror_real_location.txt"
"=== Document / ProductPhoto KeyError 진짜 자리 ===" | Out-File $out2 -Encoding UTF8
"" | Out-File $out2 -Append -Encoding UTF8

# 시간대 파일에서 KeyError + traceback + Production_Document/Production_ProductPhoto 컨텍스트
foreach ($obj in @("Document", "ProductPhoto")) {
    "" | Out-File $out2 -Append -Encoding UTF8
    "─── [$obj] 처리 시작 → 0초 실패 컨텍스트 ───" | Out-File $out2 -Append -Encoding UTF8

    # 시간대 파일 라인 수
    $tw_lines = Get-Content $tw_file
    $startIdx = -1
    for ($i = 0; $i -lt $tw_lines.Count; $i++) {
        if ($tw_lines[$i] -match "테이블 \[$obj\] 처리 시작") {
            $startIdx = $i
            break
        }
    }

    if ($startIdx -ge 0) {
        $endIdx = [Math]::Min($tw_lines.Count - 1, $startIdx + 100)
        $tw_lines[$startIdx..$endIdx] | Out-File $out2 -Append -Encoding UTF8
    } else {
        "  '$obj 처리 시작' 라인 못 찾음" | Out-File $out2 -Append -Encoding UTF8
    }
}

# Python Traceback 패턴 검색 (KeyError 앞뒤)
"" | Out-File $out2 -Append -Encoding UTF8
"=== Traceback 패턴 검색 (KeyError 앞뒤) ===" | Out-File $out2 -Append -Encoding UTF8
$tb_hits = $logTail | Select-String -Pattern 'Traceback|KeyError|line \d+, in '
"[Traceback/KeyError/line N, in 매치] $($tb_hits.Count) 라인" | Out-File $out2 -Append -Encoding UTF8
$tb_hits | Select-Object -First 30 | ForEach-Object { "  $($_.Line)" } | Out-File $out2 -Append -Encoding UTF8

# 'Production_Document' / 'Production_ProductPhoto' 키 LOOKUP 자리 추적
"" | Out-File $out2 -Append -Encoding UTF8
"=== 'Production_Document' 또는 'Production_ProductPhoto' 키 발생 자리 ===" | Out-File $out2 -Append -Encoding UTF8
$key_hits = $logTail | Select-String -Pattern "'Production_Document'|'Production_ProductPhoto'"
"[매치] $($key_hits.Count) 라인" | Out-File $out2 -Append -Encoding UTF8
foreach ($h in ($key_hits | Select-Object -First 10)) {
    $startIdx = [Math]::Max(0, $h.LineNumber - 5)
    $endIdx   = [Math]::Min($logTail.Count - 1, $h.LineNumber + 5)
    "" | Out-File $out2 -Append -Encoding UTF8
    "─── 라인 $($h.LineNumber) ±5 ───" | Out-File $out2 -Append -Encoding UTF8
    $logTail[$startIdx..$endIdx] | Out-File $out2 -Append -Encoding UTF8
}

# v95_p30 본질 1 작동 흔적
"" | Out-File $out2 -Append -Encoding UTF8
"=== v95_p30 setdefault 처방 작동 흔적 (있어야 정상) ===" | Out-File $out2 -Append -Encoding UTF8
$v30_hier = $logTail | Select-String -Pattern 'hierarchyid.*ToString'
"[hierarchyid → ToString() 처리] $($v30_hier.Count) 라인" | Out-File $out2 -Append -Encoding UTF8
$v30_hier | Select-Object -First 10 | ForEach-Object { "  $($_.Line)" } | Out-File $out2 -Append -Encoding UTF8

Write-Host "  ✓ Document/ProductPhoto 진짜 자리 → $out2"

# ────────────────────────────────────────────────────────────────────
# [3/7] vJobCandidateEducation — _data 환각 진짜 자리
# ────────────────────────────────────────────────────────────────────
Write-Host "[3/7] vJobCandidateEducation _data 환각 — AI 변환 DDL" -ForegroundColor Cyan
$out3 = Join-Path $OutDir "03_vJobCandidateEducation.txt"
"=== vJobCandidateEducation VIEW 진단 ===" | Out-File $out3 -Encoding UTF8
"" | Out-File $out3 -Append -Encoding UTF8

# 시간대 파일에서 vJobCandidateEducation 관련 모든 라인
$obj3 = "vJobCandidateEducation"
$tw_lines = Get-Content $tw_file
$matches3 = @()
for ($i = 0; $i -lt $tw_lines.Count; $i++) {
    if ($tw_lines[$i] -like "*$obj3*" -or $tw_lines[$i] -like "*vJobCandidateEducation_data*") {
        $matches3 += $i
    }
}
"[$obj3 또는 _data 매치] $($matches3.Count) 라인" | Out-File $out3 -Append -Encoding UTF8
"" | Out-File $out3 -Append -Encoding UTF8

# 첫 매치 ±150라인 (AI 변환 DDL 포함하기 위해 큰 윈도우)
if ($matches3.Count -gt 0) {
    $startIdx = [Math]::Max(0, $matches3[0] - 50)
    $endIdx   = [Math]::Min($tw_lines.Count - 1, $matches3[-1] + 50)
    "─── 첫 매치 ~ 마지막 매치 (±50) ───" | Out-File $out3 -Append -Encoding UTF8
    $tw_lines[$startIdx..$endIdx] | Out-File $out3 -Append -Encoding UTF8
}

Write-Host "  ✓ vJobCandidateEducation → $out3 (매치 $($matches3.Count))"

# ────────────────────────────────────────────────────────────────────
# [4/7] vProductModelInstructions — _Flattened 환각
# ────────────────────────────────────────────────────────────────────
Write-Host "[4/7] vProductModelInstructions _Flattened 환각 — AI 변환 DDL" -ForegroundColor Cyan
$out4 = Join-Path $OutDir "04_vProductModelInstructions.txt"
"=== vProductModelInstructions VIEW 진단 ===" | Out-File $out4 -Encoding UTF8
"" | Out-File $out4 -Append -Encoding UTF8

$obj4 = "vProductModelInstructions"
$matches4 = @()
for ($i = 0; $i -lt $tw_lines.Count; $i++) {
    if ($tw_lines[$i] -like "*$obj4*" -or $tw_lines[$i] -like "*ProductModel_Flattened*") {
        $matches4 += $i
    }
}
"[$obj4 또는 _Flattened 매치] $($matches4.Count) 라인" | Out-File $out4 -Append -Encoding UTF8
"" | Out-File $out4 -Append -Encoding UTF8

if ($matches4.Count -gt 0) {
    $startIdx = [Math]::Max(0, $matches4[0] - 50)
    $endIdx   = [Math]::Min($tw_lines.Count - 1, $matches4[-1] + 50)
    "─── 첫 매치 ~ 마지막 매치 (±50) ───" | Out-File $out4 -Append -Encoding UTF8
    $tw_lines[$startIdx..$endIdx] | Out-File $out4 -Append -Encoding UTF8
}

Write-Host "  ✓ vProductModelInstructions → $out4 (매치 $($matches4.Count))"

# ────────────────────────────────────────────────────────────────────
# [5/7] uSalesOrderHeader — 1362 → 1146 변형 (v95_p30-#5 작동 검증)
# ────────────────────────────────────────────────────────────────────
Write-Host "[5/7] uSalesOrderHeader 1146 변형 — v95_p30-#5 작동 + AFTER→BEFORE 후 자기참조" -ForegroundColor Cyan
$out5 = Join-Path $OutDir "05_uSalesOrderHeader.txt"
"=== uSalesOrderHeader 1362 → 1146 변형 ===" | Out-File $out5 -Encoding UTF8
"" | Out-File $out5 -Append -Encoding UTF8

# v95_p30-#5 흔적
$v30_5 = $logTail | Select-String -Pattern 'v95_p30-#5'
"[v95_p30-#5 (NEW row 패턴 확장) 흔적] $($v30_5.Count) 라인" | Out-File $out5 -Append -Encoding UTF8
$v30_5 | ForEach-Object { "  $($_.Line)" } | Out-File $out5 -Append -Encoding UTF8

# v95_p29-#6 흔적
"" | Out-File $out5 -Append -Encoding UTF8
$v29_6 = $logTail | Select-String -Pattern 'v95_p29-#6'
"[v95_p29-#6 (case 복원) 흔적] $($v29_6.Count) 라인" | Out-File $out5 -Append -Encoding UTF8
$v29_6 | Select-Object -Last 20 | ForEach-Object { "  $($_.Line)" } | Out-File $out5 -Append -Encoding UTF8

# uSalesOrderHeader AI 변환 결과 + 1146 직전 컨텍스트
"" | Out-File $out5 -Append -Encoding UTF8
"=== uSalesOrderHeader 매치 컨텍스트 ===" | Out-File $out5 -Append -Encoding UTF8
$obj5 = "uSalesOrderHeader"
$matches5 = @()
for ($i = 0; $i -lt $tw_lines.Count; $i++) {
    if ($tw_lines[$i] -like "*$obj5*" -or $tw_lines[$i] -like "*Sales_Salesorderheader*") {
        $matches5 += $i
    }
}
"[매치] $($matches5.Count) 라인" | Out-File $out5 -Append -Encoding UTF8

if ($matches5.Count -gt 0) {
    $startIdx = [Math]::Max(0, $matches5[0] - 30)
    $endIdx   = [Math]::Min($tw_lines.Count - 1, $matches5[-1] + 30)
    "" | Out-File $out5 -Append -Encoding UTF8
    "─── 첫 ~ 마지막 매치 (±30) ───" | Out-File $out5 -Append -Encoding UTF8
    $tw_lines[$startIdx..$endIdx] | Out-File $out5 -Append -Encoding UTF8
}

Write-Host "  ✓ uSalesOrderHeader → $out5"
Write-Host "    v95_p30-#5 흔적: $($v30_5.Count) 라인 (>0 이면 처방 작동)"
Write-Host "    v95_p29-#6 흔적: $($v29_6.Count) 라인"

# ────────────────────────────────────────────────────────────────────
# [6/7] _hier_cols KeyError 자리 추가 진단
# ────────────────────────────────────────────────────────────────────
Write-Host "[6/7] _hier_cols 처리 자리 추가 진단" -ForegroundColor Cyan
$out6 = Join-Path $OutDir "06_hier_cols_paths.txt"
"=== _hier_cols 관련 로그 + Document/ProductPhoto hierarchyid 처리 흔적 ===" | Out-File $out6 -Encoding UTF8
"" | Out-File $out6 -Append -Encoding UTF8

# hierarchyid / DocumentNode 처리 흔적
$hier_hits = $logTail | Select-String -Pattern 'hierarchyid|DocumentNode|_hier_cols'
"[hierarchyid/DocumentNode/_hier_cols 매치] $($hier_hits.Count) 라인" | Out-File $out6 -Append -Encoding UTF8
$hier_hits | Select-Object -First 30 | ForEach-Object { "  $($_.Line)" } | Out-File $out6 -Append -Encoding UTF8

# Document/ProductPhoto 처리 시작 후 어디까지 진행됐는지 (CREATE TABLE 시도 로그)
"" | Out-File $out6 -Append -Encoding UTF8
"=== Document/ProductPhoto 진행 단계별 로그 ===" | Out-File $out6 -Append -Encoding UTF8
foreach ($t in @("Production_Document", "Production_ProductPhoto")) {
    "" | Out-File $out6 -Append -Encoding UTF8
    "─── [$t] 진행 흔적 ───" | Out-File $out6 -Append -Encoding UTF8
    $hits = $logTail | Select-String -Pattern $t -SimpleMatch | Select-Object -First 20
    foreach ($h in $hits) {
        "  L$($h.LineNumber) | $($h.Line)" | Out-File $out6 -Append -Encoding UTF8
    }
}

Write-Host "  ✓ _hier_cols 진단 → $out6 (hierarchyid 매치 $($hier_hits.Count))"

# ────────────────────────────────────────────────────────────────────
# [7/7] 종합 요약
# ────────────────────────────────────────────────────────────────────
Write-Host "[7/7] 종합 요약" -ForegroundColor Cyan
$sum = Join-Path $OutDir "_SUMMARY.txt"
"═══════════════════════════════════════════════════════════════" | Out-File $sum -Encoding UTF8
"DataBridge v95_p30 후 잔여 5건 진단 — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File $sum -Append -Encoding UTF8
"═══════════════════════════════════════════════════════════════" | Out-File $sum -Append -Encoding UTF8
"" | Out-File $sum -Append -Encoding UTF8

"[v95_p30 적용 후 결과]" | Out-File $sum -Append -Encoding UTF8
"  잔여 1: Document KeyError 잔존" | Out-File $sum -Append -Encoding UTF8
"  잔여 2: ProductPhoto KeyError 잔존" | Out-File $sum -Append -Encoding UTF8
"  잔여 3: vJobCandidateEducation _data 환각 (신규)" | Out-File $sum -Append -Encoding UTF8
"  잔여 4: vProductModelInstructions _Flattened 환각" | Out-File $sum -Append -Encoding UTF8
"  잔여 5: uSalesOrderHeader 1362 → 1146 (자기참조)" | Out-File $sum -Append -Encoding UTF8
"" | Out-File $sum -Append -Encoding UTF8

"[v95_p30 작동 검증]" | Out-File $sum -Append -Encoding UTF8
"  - v95_p30-#5 흔적: $($v30_5.Count) 라인 (>0 이면 본질 3 처방 작동)" | Out-File $sum -Append -Encoding UTF8
"  - v95_p29-#6 흔적: $($v29_6.Count) 라인" | Out-File $sum -Append -Encoding UTF8
"  - hierarchyid 처리 흔적: $($hier_hits.Count) 라인" | Out-File $sum -Append -Encoding UTF8
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
Write-Host "  Compress-Archive -Path '$OutDir\*' -DestinationPath 'D:\project\diag_p30_2026-05-04.zip' -Force"
Write-Host ""
Write-Host "─── 요약 ───────────────────────────────────────────────"
Get-Content $sum | Write-Host
