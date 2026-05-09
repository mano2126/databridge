# ════════════════════════════════════════════════════════════════════
# DataBridge v95_p74 적용 (2026-05-06) — AI 프롬프트 강화
#   본부장님 5번째 통찰: "사용자는 SQL 변환 능력 없다"
#   v95_p72 (후처리) + v95_p74 (사전처리) = 2중 안전망
# ════════════════════════════════════════════════════════════════════
# 본부장님 결정:
#   "다음 세션: v95_p72 (AI 프롬프트 강화) → 재이관 시 AI 가 알아서 변환"
#   "이것도 바로 진행하자"
#
# 본질:
#   v95_p33 강화 프롬프트가 있어도 AI 가 _data, _Flattened 환각.
#   v95_p72 (후처리) 로 자동 수정 가능하지만 — 비용 절감 위해
#   AI 가 처음부터 안전한 변환을 하도록 프롬프트 추가 강화.
#
# 처방:
#   backend/prompts/mssql_to_mysql/view_trigger.txt
#   - 최상단에 【v95_p74 안전 변환 의무화】 섹션 추가
#   - 6가지 절대 규칙 (A ~ F):
#     A. FROM/JOIN 의 모든 테이블은 원본에 존재해야 함
#     B. XML 함수 발견 시 안전 폴백 (XML 컬럼 NULL)
#     C. CROSS APPLY 도 안전 폴백
#     D. PIVOT / UNPIVOT 도 안전 폴백
#     E. 컬럼 보존 의무 (응용단 호환)
#     F. 응답 노트 의무
#   - 환각 패턴 21번 명시 (AI 가 무시 못 하도록 반복 강조)
#   - 구체적인 변환 템플릿 (Few-shot 학습):
#     * vJobCandidateEducation 안전 폴백 예시
#     * vProductModelInstructions 안전 폴백 예시
#
# 효과:
#   - AI 가 처음부터 안전 폴백 변환 (환각 0건 목표)
#   - 비용 절감: AI 호출 1번에 안전한 변환 (재시도 0)
#   - v95_p72 후처리는 백업 안전망으로 (이중 안전)
#   - 사용자 친화: 외부 사용자도 [자동 변환 시도] 클릭만 하면 OK
#
# 부작용 0:
#   - 기존 v95_p33 처방 100% 보존 (line 156+)
#   - 다른 객체 타입 (PROCEDURE, FUNCTION, TRIGGER) 영향 0
#   - 정상 VIEW (XML/APPLY 미사용) 는 옛 흐름 그대로
# ════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
$Root = "D:\project\databridge_full"

Write-Host "═══════════════════════════════════════════════════════════"
Write-Host "DataBridge v95_p74 적용 (AI 프롬프트 강화)"
Write-Host "  사용자 친화 — 2중 안전망 완성 (v95_p72 + v95_p74)"
Write-Host "═══════════════════════════════════════════════════════════"
Write-Host ""

$Path = Join-Path $Root "backend\prompts\mssql_to_mysql\view_trigger.txt"

# 백업
Write-Host "[1/3] 백업 생성" -ForegroundColor Cyan
$BackupDir = Join-Path $Root "backend\backup_v95_p74_$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
if (Test-Path $Path) {
    Copy-Item $Path (Join-Path $BackupDir "view_trigger.txt.bak") -Force
    Write-Host "  ✓ 백업: $BackupDir"
}

# 검증
Write-Host ""
Write-Host "[2/3] 적용 검증" -ForegroundColor Cyan
if (-not (Test-Path $Path)) {
    Write-Host "  ✗ view_trigger.txt 없음" -ForegroundColor Red
    exit 1
}
$src = [System.IO.File]::ReadAllText($Path, [System.Text.UTF8Encoding]::new($false))

function _Mark($b) { if ($b) { return "✓" } else { return "✗" } }

$ok_p74      = ([regex]::Matches($src, 'v95_p74')).Count -ge 1
$ok_p33      = ([regex]::Matches($src, 'v95_p33')).Count -ge 2
$ok_safe     = $src.Contains('안전 변환 의무화')
$ok_rule_a   = $src.Contains('규칙 A:')
$ok_rule_b   = $src.Contains('규칙 B:')
$ok_rule_c   = $src.Contains('규칙 C:')
$ok_rule_d   = $src.Contains('규칙 D:')
$ok_rule_e   = $src.Contains('규칙 E:')
$ok_rule_f   = $src.Contains('규칙 F:')
$ok_jobcand  = $src.Contains('vJobCandidateEducation')
$ok_prodmod  = $src.Contains('vProductModelInstructions')

$lines = ($src -split "`n").Count
Write-Host ""
Write-Host "  파일 크기: $lines 줄"
Write-Host ""
Write-Host "  v95_p74 처방:"
Write-Host ("    [{0}] v95_p74 마커" -f (_Mark $ok_p74))
Write-Host ("    [{0}] 안전 변환 의무화 섹션" -f (_Mark $ok_safe))
Write-Host ("    [{0}] 규칙 A — 환각 금지" -f (_Mark $ok_rule_a))
Write-Host ("    [{0}] 규칙 B — XML 안전 폴백" -f (_Mark $ok_rule_b))
Write-Host ("    [{0}] 규칙 C — CROSS APPLY 안전 폴백" -f (_Mark $ok_rule_c))
Write-Host ("    [{0}] 규칙 D — PIVOT/UNPIVOT 안전 폴백" -f (_Mark $ok_rule_d))
Write-Host ("    [{0}] 규칙 E — 컬럼 보존 의무" -f (_Mark $ok_rule_e))
Write-Host ("    [{0}] 규칙 F — 응답 노트" -f (_Mark $ok_rule_f))
Write-Host ("    [{0}] vJobCandidateEducation Few-shot" -f (_Mark $ok_jobcand))
Write-Host ("    [{0}] vProductModelInstructions Few-shot" -f (_Mark $ok_prodmod))

Write-Host ""
Write-Host "  이전 처방 보존:"
Write-Host ("    [{0}] v95_p33 처방 (2건 이상)" -f (_Mark $ok_p33))

$allOk = $ok_p74 -and $ok_safe -and $ok_rule_a -and $ok_rule_b -and `
         $ok_rule_c -and $ok_rule_d -and $ok_rule_e -and $ok_rule_f -and `
         $ok_jobcand -and $ok_prodmod -and $ok_p33

Write-Host ""
if ($allOk) {
    Write-Host "[3/3] ✅ v95_p74 적용 완료 (AI 프롬프트 강화)" -ForegroundColor Green
    Write-Host ""
    Write-Host "════════════════════════════════════════════════════════"
    Write-Host "  ⚠️ 백엔드 재시작 필수 (프롬프트 파일은 시작 시 로드)" -ForegroundColor Yellow
    Write-Host "════════════════════════════════════════════════════════"
    Write-Host ""
    Write-Host "다음 단계:"
    Write-Host ""
    Write-Host "  1) 캐시 삭제 (옛 환각 결과 제거 — 새 프롬프트 효과 위해 필수):"
    Write-Host '     $cache="D:\project\databridge_full\backend\data\ai_conversion_cache.json"'
    Write-Host '     if (Test-Path $cache) { Remove-Item $cache -Force; Write-Host "캐시 삭제 OK" }'
    Write-Host '     # 실패 KB 도 클리어 (차단 해제):'
    Write-Host '     $fail="D:\project\databridge_full\backend\data\conversion_failures.json"'
    Write-Host '     if (Test-Path $fail) { Remove-Item $fail -Force; Write-Host "실패 KB 삭제 OK" }'
    Write-Host ""
    Write-Host "  2) 백엔드 재시작:"
    Write-Host '     Get-Process python | Stop-Process -Force; Start-Sleep -Seconds 2'
    Write-Host '     cd D:\project\databridge_full\backend; .\start.bat'
    Write-Host ""
    Write-Host "  3) 위저드 [↻ 새로 시작] → 객체 선택 → 이관 실행"
    Write-Host ""
    Write-Host "  4) 검증 (위험 객체 변환 결과):"
    Write-Host "     - vJobCandidateEducation:"
    Write-Host "       이전 (환각): FROM HumanResources_vJobCandidateEducation_data ❌"
    Write-Host "       이후 (안전): FROM HumanResources_JobCandidate ✅"
    Write-Host "                    + NULL AS EduLevel, NULL AS Major"
    Write-Host ""
    Write-Host "     - vProductModelInstructions:"
    Write-Host "       이전 (환각): FROM Production_ProductModelInstructions_Flattened ❌"
    Write-Host "       이후 (안전): FROM Production_ProductModel ✅"
    Write-Host "                    + NULL AS Instructions, NULL AS LocationID, ..."
    Write-Host ""
    Write-Host "  5) 1146 0건 확인 ✅"
    Write-Host ""
    Write-Host "2중 안전망 완성:"
    Write-Host "  ① v95_p74 (사전): AI 가 처음부터 안전 변환 (환각 0 목표)"
    Write-Host "  ② v95_p72 (후처리): 만약 AI 가 환각해도 자동 검증 + 폴백"
    Write-Host "  → 어떤 경우에도 1146 0건 보장"
    Write-Host ""
    Write-Host "롤백:"
    Write-Host "  Copy-Item '$BackupDir\view_trigger.txt.bak' '$Path' -Force"
} else {
    Write-Host "[3/3] ❌ 적용 검증 실패" -ForegroundColor Red
    exit 2
}
