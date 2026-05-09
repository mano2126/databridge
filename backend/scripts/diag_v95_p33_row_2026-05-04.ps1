# ════════════════════════════════════════════════════════════════════
# DataBridge — 본질 3+4 진단 (행 단위 실패) (2026-05-04)
# ════════════════════════════════════════════════════════════════════
# 본질 3: Production_BillOfMaterials 2,679행 NULL 위반
#   에러: 1048 'Column ProductAssemblyID cannot be null'
#   가설: v95_p28 PK NOT NULL 강제가 ProductAssemblyID 도 NOT NULL 로 만들었을 수 있음
#         또는 MSSQL is_nullable 메타가 잘못 와서 NOT NULL DDL 생성됨
#
# 본질 4: Production_ProductDocument 32행 1062 Duplicate
#   에러: (1062, "Duplicate entry '506' for key 'PRIMARY'")
#   가설: PK = (ProductID, DocumentNode) 복합키, hierarchyid 변환 결과 중복
#
# 본질 5: DatabaseLog 1,596행 모두 실패
#   에러: 메시지 미상 (캡처에 안 보임)
#
# 본부장님 모토: 추측 처방 금지, view tool 로 진짜 자리 확인
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$LogPath = "D:\project\databridge_full\backend\logs\databridge_backend.log"
$OutDir  = "D:\project\databridge_full\backend\logs\diag_v95_p32_row_2026-05-04"

if (-not (Test-Path $LogPath)) {
    Write-Host "❌ 로그 없음: $LogPath" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge 본질 3+4+5 진단 (행 단위 실패)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$logFile = Get-Item $LogPath
Write-Host "로그 크기: $([math]::Round($logFile.Length / 1MB, 2)) MB"

# 시간대 추출 (13:40~14:00 — 본부장님 마지막 재이관 시간대 추정)
$logTail = Get-Content $LogPath -Tail 80000

# ────────────────────────────────────────────────────────────────────
# [1/5] 시간대 추출 (가장 최근 재이관)
# ────────────────────────────────────────────────────────────────────
Write-Host "[1/5] 시간대 추출 (13:40~14:00)" -ForegroundColor Cyan
$tw = $logTail | Select-String -Pattern '1[34]:[0-5][0-9]:'
$tw_file = Join-Path $OutDir "01_time_window.txt"
"=== 13:40~14:00 ($($tw.Count) 라인) ===" | Out-File $tw_file -Encoding UTF8
$tw | ForEach-Object { $_.Line } | Out-File $tw_file -Append -Encoding UTF8
Write-Host "  ✓ $($tw.Count) 라인 → $tw_file"

# ────────────────────────────────────────────────────────────────────
# [2/5] 본질 3: BillOfMaterials NULL 위반 (1048)
# ────────────────────────────────────────────────────────────────────
Write-Host "[2/5] BillOfMaterials NULL 위반 (1048)" -ForegroundColor Cyan
$out2 = Join-Path $OutDir "02_bom_null.txt"
"=== Production_BillOfMaterials NULL 위반 진단 ===" | Out-File $out2 -Encoding UTF8
"" | Out-File $out2 -Append -Encoding UTF8

# v95_p28 PK NOT NULL 강제 흔적 (ProductAssemblyID 강제됐는지)
"=== v95_p28 PK NOT NULL 강제 흔적 (BillOfMaterials 컬럼) ===" | Out-File $out2 -Append -Encoding UTF8
$p28_hits = $logTail | Select-String -Pattern 'v95_p28.*BillOfMaterials|BillOfMaterials.*NOT NULL 강제'
"[v95_p28 + BillOfMaterials 매치] $($p28_hits.Count) 라인" | Out-File $out2 -Append -Encoding UTF8
$p28_hits | ForEach-Object { "  $($_.Line)" } | Out-File $out2 -Append -Encoding UTF8

# CREATE TABLE 진짜 DDL 추출 (BillOfMaterials)
"" | Out-File $out2 -Append -Encoding UTF8
"=== CREATE TABLE Production_BillOfMaterials DDL ===" | Out-File $out2 -Append -Encoding UTF8
$ddl_hits = $logTail | Select-String -Pattern 'CREATE TABLE.*Production_BillOfMaterials|Production_BillOfMaterials.*CREATE'
"[매치] $($ddl_hits.Count) 라인" | Out-File $out2 -Append -Encoding UTF8
foreach ($h in ($ddl_hits | Select-Object -First 5)) {
    $startIdx = [Math]::Max(0, $h.LineNumber - 5)
    $endIdx   = [Math]::Min($logTail.Count - 1, $h.LineNumber + 80)  # CREATE TABLE 길이 큼
    "" | Out-File $out2 -Append -Encoding UTF8
    "─── L$($h.LineNumber) ±컨텍스트 ───" | Out-File $out2 -Append -Encoding UTF8
    $logTail[$startIdx..$endIdx] | Out-File $out2 -Append -Encoding UTF8
}

# 1048 에러 발생 컨텍스트
"" | Out-File $out2 -Append -Encoding UTF8
"=== 1048 NULL 에러 발생 컨텍스트 ===" | Out-File $out2 -Append -Encoding UTF8
$err_hits = $logTail | Select-String -Pattern '1048.*ProductAssemblyID|ProductAssemblyID.*null'
"[매치] $($err_hits.Count) 라인" | Out-File $out2 -Append -Encoding UTF8
foreach ($h in ($err_hits | Select-Object -First 5)) {
    $startIdx = [Math]::Max(0, $h.LineNumber - 30)
    $endIdx   = [Math]::Min($logTail.Count - 1, $h.LineNumber + 5)
    "" | Out-File $out2 -Append -Encoding UTF8
    "─── L$($h.LineNumber) ±컨텍스트 ───" | Out-File $out2 -Append -Encoding UTF8
    $logTail[$startIdx..$endIdx] | Out-File $out2 -Append -Encoding UTF8
}

Write-Host "  ✓ BillOfMaterials → $out2"
Write-Host "    v95_p28 + BOM 매치: $($p28_hits.Count) 라인"
Write-Host "    1048 에러: $($err_hits.Count) 라인"

# ────────────────────────────────────────────────────────────────────
# [3/5] 본질 4: ProductDocument 1062 Duplicate
# ────────────────────────────────────────────────────────────────────
Write-Host "[3/5] ProductDocument 1062 Duplicate" -ForegroundColor Cyan
$out3 = Join-Path $OutDir "03_pd_duplicate.txt"
"=== Production_ProductDocument 1062 Duplicate 진단 ===" | Out-File $out3 -Encoding UTF8
"" | Out-File $out3 -Append -Encoding UTF8

# CREATE TABLE Production_ProductDocument DDL
"=== CREATE TABLE Production_ProductDocument DDL ===" | Out-File $out3 -Append -Encoding UTF8
$pd_ddl = $logTail | Select-String -Pattern 'CREATE TABLE.*Production_ProductDocument|Production_ProductDocument.*CREATE TABLE'
"[매치] $($pd_ddl.Count) 라인" | Out-File $out3 -Append -Encoding UTF8
foreach ($h in ($pd_ddl | Select-Object -First 3)) {
    $startIdx = [Math]::Max(0, $h.LineNumber - 5)
    $endIdx   = [Math]::Min($logTail.Count - 1, $h.LineNumber + 50)
    "" | Out-File $out3 -Append -Encoding UTF8
    "─── L$($h.LineNumber) ───" | Out-File $out3 -Append -Encoding UTF8
    $logTail[$startIdx..$endIdx] | Out-File $out3 -Append -Encoding UTF8
}

# Duplicate 에러 + DocumentNode (hierarchyid) 변환 흔적
"" | Out-File $out3 -Append -Encoding UTF8
"=== 1062 Duplicate + DocumentNode 변환 흔적 ===" | Out-File $out3 -Append -Encoding UTF8
$dup_hits = $logTail | Select-String -Pattern "1062.*ProductDocument|Duplicate.*ProductDocument|hierarchyid.*ProductDocument|DocumentNode"
"[매치] $($dup_hits.Count) 라인" | Out-File $out3 -Append -Encoding UTF8
$dup_hits | Select-Object -First 30 | ForEach-Object { "  $($_.Line)" } | Out-File $out3 -Append -Encoding UTF8

Write-Host "  ✓ ProductDocument → $out3"

# ────────────────────────────────────────────────────────────────────
# [4/5] 본질 5: DatabaseLog 전체 실패
# ────────────────────────────────────────────────────────────────────
Write-Host "[4/5] DatabaseLog 1,596행 모두 실패" -ForegroundColor Cyan
$out4 = Join-Path $OutDir "04_databaselog.txt"
"=== DatabaseLog 진단 (1,596행 실패) ===" | Out-File $out4 -Encoding UTF8
"" | Out-File $out4 -Append -Encoding UTF8

$dl_hits = $logTail | Select-String -Pattern 'DatabaseLog'
"[매치] $($dl_hits.Count) 라인" | Out-File $out4 -Append -Encoding UTF8
"" | Out-File $out4 -Append -Encoding UTF8

# DatabaseLog 처리 시작 ~ 실패까지 컨텍스트
$dl_start = $dl_hits | Where-Object { $_.Line -match '?닿? ?쒖옉|처리 시작|처리시작' } | Select-Object -First 1
if ($dl_start) {
    $startIdx = [Math]::Max(0, $dl_start.LineNumber - 2)
    $endIdx   = [Math]::Min($logTail.Count - 1, $dl_start.LineNumber + 50)
    $logTail[$startIdx..$endIdx] | Out-File $out4 -Append -Encoding UTF8
} else {
    # fallback - 처음 매치 컨텍스트
    if ($dl_hits.Count -gt 0) {
        $startIdx = [Math]::Max(0, $dl_hits[0].LineNumber - 5)
        $endIdx   = [Math]::Min($logTail.Count - 1, $dl_hits[-1].LineNumber + 30)
        $logTail[$startIdx..$endIdx] | Out-File $out4 -Append -Encoding UTF8
    }
}

Write-Host "  ✓ DatabaseLog → $out4 (매치 $($dl_hits.Count))"

# ────────────────────────────────────────────────────────────────────
# [5/5] 종합 요약
# ────────────────────────────────────────────────────────────────────
$sum = Join-Path $OutDir "_SUMMARY.txt"
"═══════════════════════════════════════════════════════════════" | Out-File $sum -Encoding UTF8
"본질 3+4+5 진단 — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File $sum -Append -Encoding UTF8
"═══════════════════════════════════════════════════════════════" | Out-File $sum -Append -Encoding UTF8
"" | Out-File $sum -Append -Encoding UTF8

"[흔적 카운트]" | Out-File $sum -Append -Encoding UTF8
"  - v95_p28 + BillOfMaterials: $($p28_hits.Count) 라인" | Out-File $sum -Append -Encoding UTF8
"  - 1048 ProductAssemblyID null: $($err_hits.Count) 라인" | Out-File $sum -Append -Encoding UTF8
"  - 1062 ProductDocument Duplicate: $($dup_hits.Count) 라인" | Out-File $sum -Append -Encoding UTF8
"  - DatabaseLog 매치: $($dl_hits.Count) 라인" | Out-File $sum -Append -Encoding UTF8
"" | Out-File $sum -Append -Encoding UTF8

"[다음 단계]" | Out-File $sum -Append -Encoding UTF8
"  $OutDir 폴더 압축해서 다음 메시지에 첨부" | Out-File $sum -Append -Encoding UTF8

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "✅ 진단 완료" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""
Write-Host "📁 출력: $OutDir" -ForegroundColor Yellow
Write-Host ""
Write-Host "📦 ZIP 압축:" -ForegroundColor Yellow
Write-Host "  Compress-Archive -Path '$OutDir\*' -DestinationPath 'D:\project\diag_v95_p32_row_2026-05-04.zip' -Force"
Write-Host ""
Get-Content $sum | Write-Host
