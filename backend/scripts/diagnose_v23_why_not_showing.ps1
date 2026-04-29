# v10 #23 배포 상태 및 데이터 전체 진단
# 파일명: diagnose_v23_why_not_showing.ps1
# 실행: cd D:\project\databridge_full\backend\scripts
#       .\diagnose_v23_why_not_showing.ps1

Write-Host "`n🔬 v10 #23 Before/After 섹션이 안 나오는 이유 진단`n" -ForegroundColor Cyan

$jobId = "655d5ec1-c8a1-44e9-804d-945b89eae886"
Write-Host "대상 Job: $jobId`n" -ForegroundColor Gray

# ── 1) 파일 레벨 검증 ────────────────────────
Write-Host "[1/6] v10 #23 백엔드 파일 존재 확인" -ForegroundColor Yellow

$files = @{
    "advisor_tracking.py" = "D:\project\databridge_full\backend\app\core\advisor_tracking.py"
    "advisor.py"          = "D:\project\databridge_full\backend\app\api\routes\advisor.py"
    "report.py"           = "D:\project\databridge_full\backend\app\api\routes\report.py"
}
foreach ($name in $files.Keys) {
    if (Test-Path $files[$name]) {
        $size = (Get-Item $files[$name]).Length
        Write-Host "  ✓ $name ($size bytes)" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $name 없음!" -ForegroundColor Red
    }
}

# ── 2) advisor.py 가 tracking 을 호출하는지 ──────
Write-Host ""
Write-Host "[2/6] advisor.py 의 tracking 연동 확인" -ForegroundColor Yellow
$hasImport = Select-String -Path $files["advisor.py"] -Pattern "from app.core.advisor_tracking import record_decisions" -Quiet
if ($hasImport) {
    Write-Host "  ✓ record_decisions import 확인" -ForegroundColor Green
} else {
    Write-Host "  ✗ v10 #23 수정 안 반영됨!" -ForegroundColor Red
    Write-Host "  → databridge_v10_23_beforeafter.zip 을 아직 배포 안 하셨을 가능성" -ForegroundColor Yellow
}

# ── 3) report.py 의 _build_advisor_impact ────────
Write-Host ""
Write-Host "[3/6] report.py 의 _build_advisor_impact 함수 확인" -ForegroundColor Yellow
$hasBuilder = Select-String -Path $files["report.py"] -Pattern "_build_advisor_impact" -Quiet
if ($hasBuilder) {
    Write-Host "  ✓ _build_advisor_impact 확인" -ForegroundColor Green
} else {
    Write-Host "  ✗ v10 #23 수정 안 반영됨!" -ForegroundColor Red
}

# ── 4) verify API 가 advisor_impact 반환하는지 ─────
Write-Host ""
Write-Host "[4/6] verify API 응답에 advisor_impact 필드 있는지" -ForegroundColor Yellow
try {
    $verify = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/verify/$jobId" -TimeoutSec 10
    if ($verify.PSObject.Properties["advisor_impact"]) {
        Write-Host "  ✓ advisor_impact 필드 존재" -ForegroundColor Green
        $impact = $verify.advisor_impact
        Write-Host "    has_data: $($impact.has_data)" -ForegroundColor Gray
        if (-not $impact.has_data) {
            Write-Host "    reason: $($impact.reason)" -ForegroundColor Red
            if ($impact.hint) {
                Write-Host "    hint:   $($impact.hint)" -ForegroundColor Yellow
            }
        } else {
            Write-Host "    summary: $($impact.summary | ConvertTo-Json -Compress)" -ForegroundColor Gray
            Write-Host "  🎯 데이터 있음! 프론트가 안 보여주는 문제" -ForegroundColor Green
        }
    } else {
        Write-Host "  ✗ advisor_impact 필드 없음 — 백엔드 v10 #23 미반영" -ForegroundColor Red
        Write-Host "  → 백엔드 재시작 필요" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "    report_version: $($verify.report_version)" -ForegroundColor Gray
    if ($verify.report_version -like "*v10#23*") {
        Write-Host "    ✓ v10 #23 버전 확인됨" -ForegroundColor Green
    } else {
        Write-Host "    ⚠ v10 #23 버전 아님 — 이전 코드 사용 중" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ✗ verify API 호출 실패: $_" -ForegroundColor Red
}

# ── 5) Tracking Store 에 실제 데이터 있는지 ────────
Write-Host ""
Write-Host "[5/6] advisor_tracking Store 에 이 Job 의 데이터 있는지" -ForegroundColor Yellow
$dbPath = "D:\project\databridge_full\backend\databridge.db"
if (Test-Path $dbPath) {
    Write-Host "  SQLite 파일: $dbPath (존재)" -ForegroundColor Gray
    try {
        # Python 으로 조회 (sqlite3 명령이 없을 수 있으니)
        $pyScript = @"
import sqlite3, json, sys
try:
    conn = sqlite3.connect(r'D:\project\databridge_fullackend\databridge.db')
    cur = conn.cursor()
    # advisor_tracking namespace 조회
    cur.execute("SELECT namespace, key, value FROM store WHERE namespace='advisor_tracking'")
    rows = cur.fetchall()
    if not rows:
        print('  ✗ advisor_tracking 데이터 없음!')
        print('  → AI DBA apply-decision 이 tracking 에 저장 못함')
        print('  → 원인: (a) 위저드가 job_id 안 넘김 (b) v10 #23 미배포 상태로 호출됨')
    else:
        print(f'  ✓ advisor_tracking 데이터 {len(rows)}건')
        for ns, k, v in rows:
            print(f'    key: {k}')
            try:
                d = json.loads(v)
                dec = d.get('decisions', [])
                jm  = d.get('job_metrics', {})
                print(f'      decisions: {len(dec)}건')
                print(f'      job_metrics: {len(jm)}개 필드')
            except:
                print(f'      (파싱 실패)')
    conn.close()
except Exception as e:
    print(f'  ✗ Store 조회 실패: {e}')
"@
        $tmpPy = [System.IO.Path]::GetTempFileName() + ".py"
        Set-Content -Path $tmpPy -Value $pyScript -Encoding UTF8
        & "D:\project\databridge_full\backend\venv\Scripts\python.exe" $tmpPy
        Remove-Item $tmpPy -ErrorAction SilentlyContinue
    } catch {
        Write-Host "  ✗ DB 조회 실패: $_" -ForegroundColor Red
    }
} else {
    Write-Host "  ✗ databridge.db 없음" -ForegroundColor Red
}

# ── 6) MigrationReport.vue 가 verify API 호출하는지 ───
Write-Host ""
Write-Host "[6/6] MigrationReport.vue 가 verify API 호출하도록 수정됐는지" -ForegroundColor Yellow
$vuePath = "D:\project\databridge_full\frontend\src\pages\MigrationReport.vue"
if (Test-Path $vuePath) {
    $hasVerifyCall = Select-String -Path $vuePath -Pattern "verifyReport|advisor_impact|advisorImpact" -Quiet
    if ($hasVerifyCall) {
        Write-Host "  ✓ 프론트 v10 #23 수정 반영됨" -ForegroundColor Green
    } else {
        Write-Host "  ✗ 프론트 v10 #23 미반영!" -ForegroundColor Red
        Write-Host "  → MigrationReport.vue 가 advisor_impact 를 렌더링 안 함" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ? MigrationReport.vue 경로 확인 필요" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "진단 완료. 결과를 Claude 에게 공유해주세요." -ForegroundColor Cyan
Write-Host ""
