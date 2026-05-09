# ════════════════════════════════════════════════════════════════════
# DataBridge — 검증 도구 매칭 0건 진단 (2026-05-04)
# ════════════════════════════════════════════════════════════════════
# 본부장님 호소:
#   소스 'Person.Address' (점) ↔ 타겟 'Person_Address' (언더스코어) 가
#   '소스전용', '타겟전용' 으로 분리 표시 = 매칭 0건
#
# 본질 가설:
#   1) Validate.vue 의 _policyKey 함수는 정상이지만
#      schemaStrategy.value 가 'underscore' 가 아닐 가능성
#   2) 또는 소스 데이터가 객체 형태가 아닌 문자열로 와서 schema_name 누락
#   3) 또는 quickSrc/quickTgt 의 schemaStrategy 가 페이지 진입 시 안 채워짐
#
# 진단 본질 (추측 금지 — 진짜 데이터 확인):
#   [1] Validate 페이지 호출 시점의 schemaStrategy 값
#   [2] 소스/타겟 테이블 목록 API 응답 형태
#   [3] _policyKey 함수의 sch / bare 추출 결과
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$OutDir = "D:\project\databridge_full\backend\logs\diag_validate_2026-05-04"
$LogPath = "D:\project\databridge_full\backend\logs\databridge_backend.log"
$VuePath = "D:\project\databridge_full\frontend\src\pages\Validate.vue"

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "검증 도구 매칭 0건 진단"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

# ────────────────────────────────────────────────────────────────────
# [1/4] 백엔드 로그에서 검증 페이지 API 호출 추출
# ────────────────────────────────────────────────────────────────────
Write-Host "[1/4] 검증 API 호출 로그" -ForegroundColor Cyan
$out1 = Join-Path $OutDir "01_validate_api_calls.txt"
"=== 검증 페이지 API 호출 로그 ===" | Out-File $out1 -Encoding UTF8
"" | Out-File $out1 -Append -Encoding UTF8

if (Test-Path $LogPath) {
    $logTail = Get-Content $LogPath -Tail 30000

    # /api/validate 또는 /api/v1/validate 또는 /api/v1/connectors 호출
    $api_hits = $logTail | Select-String -Pattern '/api.*validate|/api.*tables|/api.*connectors.*tables'
    "[validate/tables API 매치] $($api_hits.Count) 라인" | Out-File $out1 -Append -Encoding UTF8
    $api_hits | Select-Object -Last 30 | ForEach-Object { "  $($_.Line)" } | Out-File $out1 -Append -Encoding UTF8

    Write-Host "  ✓ API 호출: $($api_hits.Count) 라인 → $out1"
} else {
    Write-Host "  ⚠ 로그 파일 없음"
}

# ────────────────────────────────────────────────────────────────────
# [2/4] Validate.vue 핵심 자리 스냅샷
# ────────────────────────────────────────────────────────────────────
Write-Host "[2/4] Validate.vue 핵심 자리" -ForegroundColor Cyan
$out2 = Join-Path $OutDir "02_validate_vue_snapshot.txt"
"=== Validate.vue _policyKey + schemaStrategy 자리 ===" | Out-File $out2 -Encoding UTF8
"" | Out-File $out2 -Append -Encoding UTF8

if (Test-Path $VuePath) {
    $vue = Get-Content $VuePath
    "라인 수: $($vue.Count)" | Out-File $out2 -Append -Encoding UTF8
    "" | Out-File $out2 -Append -Encoding UTF8

    # _policyKey 함수 영역 (line 2270~2315)
    "=== _policyKey 정의 (line 2270~2315) ===" | Out-File $out2 -Append -Encoding UTF8
    $vue[2269..2314] | Out-File $out2 -Append -Encoding UTF8

    # schemaStrategy 정의 (line 1965~1975)
    "" | Out-File $out2 -Append -Encoding UTF8
    "=== schemaStrategy computed (line 1965~1980) ===" | Out-File $out2 -Append -Encoding UTF8
    if ($vue.Count -gt 1980) {
        $vue[1964..1979] | Out-File $out2 -Append -Encoding UTF8
    }

    # tableMatchInfo 자리 (line 2360~2380)
    "" | Out-File $out2 -Append -Encoding UTF8
    "=== tableMatchInfo 결정 자리 (line 2360~2385) ===" | Out-File $out2 -Append -Encoding UTF8
    if ($vue.Count -gt 2385) {
        $vue[2359..2384] | Out-File $out2 -Append -Encoding UTF8
    }

    Write-Host "  ✓ Validate.vue 스냅샷 → $out2"
} else {
    Write-Host "  ⚠ Validate.vue 없음"
}

# ────────────────────────────────────────────────────────────────────
# [3/4] cStore (connectors store) 자리 추적
# ────────────────────────────────────────────────────────────────────
Write-Host "[3/4] connectors store schemaStrategy 자리" -ForegroundColor Cyan
$out3 = Join-Path $OutDir "03_connectors_store.txt"
"=== Connectors store schemaStrategy 자리 ===" | Out-File $out3 -Encoding UTF8
"" | Out-File $out3 -Append -Encoding UTF8

$storeFiles = Get-ChildItem -Path "D:\project\databridge_full\frontend\src\stores" -Filter "*.js" -ErrorAction SilentlyContinue
foreach ($sf in $storeFiles) {
    "─── $($sf.Name) ───" | Out-File $out3 -Append -Encoding UTF8
    $hits = Select-String -Path $sf.FullName -Pattern 'schemaStrategy|underscore|drop|database'
    "[schemaStrategy 관련] $($hits.Count) 라인" | Out-File $out3 -Append -Encoding UTF8
    $hits | ForEach-Object { "  L$($_.LineNumber): $($_.Line)" } | Out-File $out3 -Append -Encoding UTF8
    "" | Out-File $out3 -Append -Encoding UTF8
}

Write-Host "  ✓ stores 분석 → $out3"

# ────────────────────────────────────────────────────────────────────
# [4/4] 종합 요약
# ────────────────────────────────────────────────────────────────────
$sum = Join-Path $OutDir "_SUMMARY.txt"
"═══════════════════════════════════════════════════════════════" | Out-File $sum -Encoding UTF8
"검증 도구 매칭 0건 진단 — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File $sum -Append -Encoding UTF8
"═══════════════════════════════════════════════════════════════" | Out-File $sum -Append -Encoding UTF8
"" | Out-File $sum -Append -Encoding UTF8

"[본부장님 호소]" | Out-File $sum -Append -Encoding UTF8
"  소스 'Person.Address' ↔ 타겟 'Person_Address' 매칭 안 됨" | Out-File $sum -Append -Encoding UTF8
"" | Out-File $sum -Append -Encoding UTF8

"[추정 본질]" | Out-File $sum -Append -Encoding UTF8
"  Validate.vue _policyKey 정상이지만 schemaStrategy 값이 'underscore' 가" | Out-File $sum -Append -Encoding UTF8
"  아닐 가능성. cStore 의 schemaStrategy 기본값 + 페이지 진입 시 채워지는지 확인 필요" | Out-File $sum -Append -Encoding UTF8
"" | Out-File $sum -Append -Encoding UTF8

"[다음 단계]" | Out-File $sum -Append -Encoding UTF8
"  $OutDir 폴더 압축해서 다음 메시지에 첨부" | Out-File $sum -Append -Encoding UTF8
"  진단 결과로 v95_p36 단일 처방" | Out-File $sum -Append -Encoding UTF8

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "✅ 진단 완료" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""
Write-Host "📦 ZIP 압축:" -ForegroundColor Yellow
Write-Host "  Compress-Archive -Path '$OutDir\*' -DestinationPath 'D:\project\diag_validate_2026-05-04.zip' -Force"
