# v90 시나리오 통합 자동 패치 스크립트 v2
# 본부장님 환경의 JobWizard.vue 에 시나리오 선택 + 컴포넌트 props 전달

Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host " v90 시나리오 통합 자동 패치"
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host ""

$jobWizardPath = "D:\project\databridge_full\frontend\src\pages\JobWizard.vue"

if (-not (Test-Path $jobWizardPath)) {
    Write-Host "❌ JobWizard.vue 없음" -ForegroundColor Red
    exit 1
}

# 백업
Copy-Item $jobWizardPath "$jobWizardPath.before-v90.bak" -Force
Write-Host "[1] 백업 완료" -ForegroundColor Cyan

$content = Get-Content $jobWizardPath -Raw -Encoding UTF8

if ($content -match "ScenarioSelector") {
    Write-Host "⚠️ 이미 통합되어 있음 — 종료" -ForegroundColor Yellow
    exit 0
}

$changeCount = 0

# 1. import 추가
Write-Host "[2] import 추가..." -ForegroundColor Cyan
$importPattern = "import AdvisorPanel from '@/components/advisor/AdvisorPanel.vue'"
if ($content -match [regex]::Escape($importPattern)) {
    $newImport = $importPattern + "`r`nimport ScenarioSelector from '@/components/wizard/ScenarioSelector.vue'  // v90: 이관 시나리오"
    $content = $content -replace [regex]::Escape($importPattern), $newImport
    Write-Host "  ✅ import 추가" -ForegroundColor Green
    $changeCount++
}

# 2. form.migrationScenario
Write-Host "[3] form 필드 추가..." -ForegroundColor Cyan
$formPattern = "advisorDecisions: \[\],"
if ($content -match $formPattern) {
    $formInsert = "advisorDecisions: [],`r`n`r`n  // v90: 이관 시나리오 (Step 0 에서 선택)`r`n  migrationScenario: '',"
    $content = $content -replace $formPattern, $formInsert
    Write-Host "  ✅ migrationScenario 필드" -ForegroundColor Green
    $changeCount++
}

# 3. Step 0 에 ScenarioSelector 삽입
Write-Host "[4] Step 0 에 ScenarioSelector 삽입..." -ForegroundColor Cyan
$step0Pattern = '(?s)(<div v-if="connector\.target\.dbType===d\.value" class="db-card-badge tgt">연결됨</div>\s*</div>\s*</div>)\s*</template>'
if ($content -match $step0Pattern) {
    $newStep0 = '$1' + "`r`n`r`n        <!-- v90: 이관 시나리오 선택 -->`r`n        <ScenarioSelector v-model=`"form.migrationScenario`" />`r`n      </template>"
    $content = $content -replace $step0Pattern, $newStep0
    Write-Host "  ✅ ScenarioSelector 삽입" -ForegroundColor Green
    $changeCount++
}

# 4. AdvisorPanel 에 시나리오 prop 전달
Write-Host "[5] AdvisorPanel 시나리오 prop 전달..." -ForegroundColor Cyan
if ($content -match '<AdvisorPanel\s+:src-db') {
    $content = $content -replace '<AdvisorPanel\s+:src-db', '<AdvisorPanel`r`n          :migration-scenario="form.migrationScenario"`r`n          :src-db'
    Write-Host "  ✅ AdvisorPanel" -ForegroundColor Green
    $changeCount++
}

# 5. PrivacyPanel
Write-Host "[6] PrivacyPanel 시나리오 prop 전달..." -ForegroundColor Cyan
if ($content -match '<PrivacyPanel\s') {
    $content = $content -replace '<PrivacyPanel\s', '<PrivacyPanel`r`n          :migration-scenario="form.migrationScenario"`r`n          '
    Write-Host "  ✅ PrivacyPanel" -ForegroundColor Green
    $changeCount++
}

# 6. AnalysisTabs (마스터 ZIP 으로 들어온 경우)
if ($content -match '<AnalysisTabs\s') {
    Write-Host "[7] AnalysisTabs 시나리오 prop 전달..." -ForegroundColor Cyan
    $content = $content -replace '<AnalysisTabs\s', '<AnalysisTabs`r`n          :migration-scenario="form.migrationScenario"`r`n          '
    Write-Host "  ✅ AnalysisTabs" -ForegroundColor Green
    $changeCount++
}

# 7. nextStep 검증
Write-Host "[8] nextStep 검증 추가..." -ForegroundColor Cyan
if ($content -match "function nextStep\(\)\{" -and $content -notmatch "이관 시나리오를 먼저 선택") {
    $nextStepNew = @"
function nextStep(){
  if (cur.value === 0 && !form.value.migrationScenario) {
    if (typeof window !== 'undefined' && window.alert) {
      window.alert('이관 시나리오를 먼저 선택해주세요. 시나리오에 따라 AI DBA + PII 정책이 자동 적용됩니다.')
    }
    return
  }
"@
    $content = $content -replace "function nextStep\(\)\{", $nextStepNew
    Write-Host "  ✅ 검증 추가" -ForegroundColor Green
    $changeCount++
}

# 저장 (UTF-8 BOM 없이)
[System.IO.File]::WriteAllText($jobWizardPath, $content, (New-Object System.Text.UTF8Encoding $false))
Write-Host ""
Write-Host "[9] ✅ 저장 완료 ($changeCount 개 변경)" -ForegroundColor Green

# 검증
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════"
Write-Host " 검증"
Write-Host "═══════════════════════════════════════════════════════════════"
$check = Get-Content $jobWizardPath -Raw -Encoding UTF8
if ($check -match "import ScenarioSelector") { Write-Host "  ✅ ScenarioSelector import" -ForegroundColor Green } else { Write-Host "  ❌ ScenarioSelector import" -ForegroundColor Red }
if ($check -match "migrationScenario:") { Write-Host "  ✅ form.migrationScenario" -ForegroundColor Green } else { Write-Host "  ❌ form.migrationScenario" -ForegroundColor Red }
if ($check -match '<ScenarioSelector') { Write-Host "  ✅ <ScenarioSelector> 태그" -ForegroundColor Green } else { Write-Host "  ❌ <ScenarioSelector> 태그" -ForegroundColor Red }

Write-Host ""
Write-Host "다음 단계:" -ForegroundColor Yellow
Write-Host "  1. cd D:\project\databridge_full\frontend"
Write-Host "  2. Remove-Item 'node_modules\.vite' -Recurse -Force -ErrorAction SilentlyContinue"
Write-Host "  3. npm run dev 재시작"
Write-Host "  4. Ctrl+Shift+R"
Write-Host "  5. 위저드 Step 0 → 시나리오 카드 8개 표시 확인"
