# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p34 적용 + ProductDocument 진단 (2026-05-04)
# ════════════════════════════════════════════════════════════════════
# 본질 3+5 즉시 처방:
#
#   본질 3: BillOfMaterials 2,679행 1048 'ProductAssemblyID cannot be null'
#     자리: migration_engine.py:3355, 3379 sys.index_columns JOIN
#     본질: index_id=1 은 'clustered index' 일 뿐 PK 가 아닐 수 있음
#           BillOfMaterials clustered = (ProductAssemblyID, ComponentID, StartDate)
#           실제 PK = BillOfMaterialsID
#           → ProductAssemblyID 가 PK 로 잘못 식별되어 v95_p28 NOT NULL 강제 적용
#     처방: sys.indexes idx ON ... AND idx.is_primary_key=1 조건 추가
#
#   본질 5: DatabaseLog 1,596행 1048 'XmlEvent cannot be null'
#     자리: migration_engine.py:1162 _create_mysql_table nullable 결정
#     본질: XML 컬럼은 _skip_cols 처리되어 SELECT 시 NULL 로 대체되지만
#           CREATE TABLE 의 nullable 은 MSSQL 메타 그대로 (NOT NULL)
#     처방: _skip_cols 에 등록된 컬럼은 nullable=True 강제
#
# 본질 4 (ProductDocument 32행 1062 Duplicate) — 별도 진단:
#   hierarchyid DocumentNode ToString() 변환 결과 중복 의심
#   진단 스크립트가 진짜 변환 결과 추출 → 다음 처방 결정
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p34 적용 (본질 3+5)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$MePath = Join-Path $Root "backend\app\engine\migration_engine.py"
if (-not (Test-Path $MePath)) { Write-Host "❌ migration_engine.py 없음" -ForegroundColor Red; exit 1 }

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p34_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
Copy-Item $MePath (Join-Path $BackupDir "migration_engine.py.bak") -Force
Write-Host "  ✓ 백업: $BackupDir"

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
$me = Get-Content $MePath -Raw

# 본질 3: PK 진짜 식별
$ok_v3_marker = $me.Contains("v95_p34")
$ok_v3_pkfix  = ($me -match "is_primary_key=1") -and ($me.Contains("sys.indexes idx"))
$ok_v3_no_old = -not ($me -match "ic\.index_id=1\b")  # 옛 패턴 제거 확인

# 본질 5: _skip_cols nullable 강제
$ok_v5_skip   = $me.Contains("_skip_cols_set") -and $me.Contains("미지원 타입 컬럼")

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

Write-Host ""
Write-Host "  본질 3 (PK 진짜 식별):"
Write-Host ("    [{0}] v95_p34 마커" -f (_Mark $ok_v3_marker))
Write-Host ("    [{0}] is_primary_key=1 + sys.indexes JOIN 추가" -f (_Mark $ok_v3_pkfix))
Write-Host ("    [{0}] 옛 패턴 (index_id=1 단독) 제거" -f (_Mark $ok_v3_no_old))

Write-Host ""
Write-Host "  본질 5 (XML 컬럼 nullable 강제):"
Write-Host ("    [{0}] _skip_cols nullable=True 강제 로직" -f (_Mark $ok_v5_skip))

Write-Host ""
Write-Host "  이전 처방 보존:"
foreach ($m in @("v95_p23a","v95_p26","v95_p27","v95_p28","v95_p30","v95_p31")) {
    Write-Host ("    [{0}] {1} : {2}건" -f (_Mark ($me.Contains($m))), $m, ([regex]::Matches($me, $m)).Count)
}

$allOk = $ok_v3_marker -and $ok_v3_pkfix -and $ok_v3_no_old -and $ok_v5_skip

# 본질 4 진단 - ProductDocument hierarchyid 변환 결과 추출
Write-Host ""
Write-Host "[3/3] ProductDocument 진단 (본질 4)" -ForegroundColor Cyan

$LogPath = Join-Path $Root "backend\logs\databridge_backend.log"
$DiagDir = Join-Path $Root "backend\logs\diag_v95_p34_pd_2026-05-04"
if (-not (Test-Path $DiagDir)) { New-Item -ItemType Directory -Path $DiagDir -Force | Out-Null }

if (Test-Path $LogPath) {
    $logTail = Get-Content $LogPath -Tail 40000
    $pd_file = Join-Path $DiagDir "ProductDocument_diag.txt"

    "=== ProductDocument 진단 (1062 Duplicate) ===" | Out-File $pd_file -Encoding UTF8
    "" | Out-File $pd_file -Append -Encoding UTF8

    # ProductDocument 처리 흔적
    $pd_hits = $logTail | Select-String -Pattern 'ProductDocument' -CaseSensitive:$false
    "[ProductDocument 매치] $($pd_hits.Count) 라인" | Out-File $pd_file -Append -Encoding UTF8

    # hierarchyid 변환 + DocumentNode 흔적
    $hier_hits = $logTail | Select-String -Pattern 'hierarchyid|DocumentNode|ToString'
    "[hierarchyid/DocumentNode 매치] $($hier_hits.Count) 라인" | Out-File $pd_file -Append -Encoding UTF8

    # 1062 Duplicate 발생 컨텍스트
    "" | Out-File $pd_file -Append -Encoding UTF8
    $dup_hits = $logTail | Select-String -Pattern '1062.*ProductDocument|ProductDocument.*Duplicate'
    "[1062 Duplicate ProductDocument] $($dup_hits.Count) 라인" | Out-File $pd_file -Append -Encoding UTF8
    foreach ($h in ($dup_hits | Select-Object -First 5)) {
        $startIdx = [Math]::Max(0, $h.LineNumber - 30)
        $endIdx   = [Math]::Min($logTail.Count - 1, $h.LineNumber + 5)
        "" | Out-File $pd_file -Append -Encoding UTF8
        "─── L$($h.LineNumber) 컨텍스트 ───" | Out-File $pd_file -Append -Encoding UTF8
        $logTail[$startIdx..$endIdx] | Out-File $pd_file -Append -Encoding UTF8
    }

    Write-Host "  ✓ ProductDocument 진단 → $pd_file"
    Write-Host "    매치: $($pd_hits.Count) | hierarchyid: $($hier_hits.Count) | 1062: $($dup_hits.Count)"
} else {
    Write-Host "  ⚠ 로그 파일 없음 (진단 스킵)"
}

Write-Host ""
if ($allOk) {
    Write-Host "═══════════════════════════════════════════════════════════"
    Write-Host "✅ v95_p34 적용 완료 + 진단 동시 차움" -ForegroundColor Green
    Write-Host "═══════════════════════════════════════════════════════════"
    Write-Host ""
    Write-Host "다음 단계:" -ForegroundColor Yellow
    Write-Host "  1) 백엔드 재시작"
    Write-Host "  2) MySQL 타겟 DB 정리"
    Write-Host "  3) 위저드 [↻ 새로 시작] → 재이관"
    Write-Host ""
    Write-Host "  진단 결과 ZIP (본질 4 다음 처방용):"
    Write-Host "  Compress-Archive -Path '$DiagDir\*' -DestinationPath 'D:\project\diag_v95_p34_pd_2026-05-04.zip' -Force"
    Write-Host ""
    Write-Host "결과 측정 기대:"
    Write-Host "  - BillOfMaterials 2,679행 1048: 0건 ✅ (본질 3)"
    Write-Host "  - DatabaseLog 1,596행 1048: 0건 ✅ (본질 5)"
    Write-Host "  - ProductDocument 32행 1062: 잔존 (본질 4 — 진단 후)"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\migration_engine.py.bak' '$MePath' -Force"
} else {
    Write-Host "❌ 적용 검증 실패" -ForegroundColor Red
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\migration_engine.py.bak' '$MePath' -Force"
    exit 2
}
