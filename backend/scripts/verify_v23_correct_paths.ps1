# v10 #23 정확한 경로로 최종 검증
# 파일명: verify_v23_correct_paths.ps1

Write-Host "`n🎯 v10 #23 최종 검증 (올바른 경로)`n" -ForegroundColor Cyan

$jobId = "655d5ec1-c8a1-44e9-804d-945b89eae886"

# ── 1) 정확한 verify 엔드포인트 호출 ──────────────
Write-Host "[1/3] /api/v1/report/verify/$jobId 호출" -ForegroundColor Yellow
try {
    $verify = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/report/verify/$jobId" -TimeoutSec 15
    Write-Host "  ✓ API 응답 수신" -ForegroundColor Green
    Write-Host "  report_version: $($verify.report_version)" -ForegroundColor Gray
    
    if ($verify.PSObject.Properties["advisor_impact"]) {
        Write-Host "  ✓ advisor_impact 필드 존재!" -ForegroundColor Green
        $impact = $verify.advisor_impact
        Write-Host "    has_data: $($impact.has_data)" -ForegroundColor $(if ($impact.has_data) { "Green" } else { "Yellow" })
        
        if ($impact.has_data) {
            Write-Host ""
            Write-Host "  🎯🎯🎯 데이터 있음! 섹션 나와야 함!" -ForegroundColor Green
            Write-Host "    applied: $($impact.summary.applied)" -ForegroundColor Green
            Write-Host "    skipped: $($impact.summary.skipped)" -ForegroundColor Green
            Write-Host "    measured: $($impact.summary.measured_count)" -ForegroundColor Green
            Write-Host "    estimated_savings: $($impact.summary.estimated_savings)" -ForegroundColor Green
        } else {
            Write-Host "    reason: $($impact.reason)" -ForegroundColor Red
            if ($impact.hint) {
                Write-Host "    hint:   $($impact.hint)" -ForegroundColor Yellow
            }
            Write-Host ""
            Write-Host "  ⚠️ 이유: $($impact.reason)" -ForegroundColor Yellow
            if ($impact.reason -eq "no_advisor_decisions") {
                Write-Host "  → apply_decision 이 저장 안됨 (job_id 없었거나 호출 실패)" -ForegroundColor Yellow
            }
        }
    } else {
        Write-Host "  ✗ advisor_impact 필드 없음 — report.py 미반영 상태!" -ForegroundColor Red
    }
} catch {
    Write-Host "  ✗ API 호출 실패: $_" -ForegroundColor Red
}

# ── 2) Store DB 에서 advisor_tracking 조회 (올바른 경로) ─────
Write-Host ""
Write-Host "[2/3] Store DB 에서 advisor_tracking 조회" -ForegroundColor Yellow
$pyScript = @"
import sqlite3, json
try:
    conn = sqlite3.connect(r'D:\project\databridge_fullackend\data\databridge.db')
    cur = conn.cursor()
    
    # 테이블 목록 먼저 확인
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f'  테이블 목록: {tables}')
    
    # advisor_tracking 조회 (실제 테이블명 맞춰서)
    # 일반적 구조: kv_store 또는 store 테이블
    for tbl in tables:
        try:
            cur.execute(f'PRAGMA table_info({tbl})')
            cols = [r[1] for r in cur.fetchall()]
            if 'namespace' in cols or 'ns' in cols:
                ns_col = 'namespace' if 'namespace' in cols else 'ns'
                cur.execute(f'SELECT {ns_col}, key, value FROM {tbl} WHERE {ns_col}=?', ('advisor_tracking',))
                rows = cur.fetchall()
                if rows:
                    print(f'  ✓ {tbl} 에 advisor_tracking {len(rows)}건 발견!')
                    for ns, k, v in rows:
                        print(f'    key: {k}')
                        try:
                            d = json.loads(v)
                            decs = d.get('decisions', [])
                            jm = d.get('job_metrics', {})
                            print(f'      decisions: {len(decs)} 건')
                            for dec in decs[:3]:
                                print(f'        - {dec.get("rec_id")}: {dec.get("decision")} ({dec.get("title", "no title")})')
                            print(f'      job_metrics: {list(jm.keys())}')
                        except Exception as e:
                            print(f'      (파싱 실패: {e})')
                else:
                    print(f'  {tbl}: advisor_tracking 데이터 없음')
        except Exception as e:
            pass
    
    # 모든 namespace 조회 (어떤 Store 데이터가 있는지)
    for tbl in tables:
        try:
            cur.execute(f'PRAGMA table_info({tbl})')
            cols = [r[1] for r in cur.fetchall()]
            if 'namespace' in cols or 'ns' in cols:
                ns_col = 'namespace' if 'namespace' in cols else 'ns'
                cur.execute(f'SELECT DISTINCT {ns_col}, COUNT(*) FROM {tbl} GROUP BY {ns_col}')
                print(f'  {tbl} namespaces:')
                for ns, cnt in cur.fetchall():
                    print(f'    {ns}: {cnt}건')
                break
        except:
            pass
    
    conn.close()
except Exception as e:
    print(f'  ✗ 조회 실패: {e}')
"@
$tmpPy = [System.IO.Path]::GetTempFileName() + ".py"
Set-Content -Path $tmpPy -Value $pyScript -Encoding UTF8
& "D:\project\databridge_full\backend\venv\Scripts\python.exe" $tmpPy
Remove-Item $tmpPy -ErrorAction SilentlyContinue

# ── 3) apply-decision 엔드포인트 호출 방식 확인 ───────
Write-Host ""
Write-Host "[3/3] 위저드가 apply-decision 호출 시 job_id 넘기는지 확인" -ForegroundColor Yellow
# 프론트에서 apply-decision 호출하는 코드 찾기
$apiFiles = Get-ChildItem -Path "D:\project\databridge_full\frontend\src" -Recurse -Filter "*.js" -ErrorAction SilentlyContinue
$apiFiles += Get-ChildItem -Path "D:\project\databridge_full\frontend\src" -Recurse -Filter "*.vue" -ErrorAction SilentlyContinue

$found = $false
foreach ($f in $apiFiles) {
    $content = Get-Content $f.FullName -Raw -ErrorAction SilentlyContinue
    if ($content -and ($content -like "*apply-decision*" -or $content -like "*apply_decision*")) {
        Write-Host "  발견: $($f.Name)" -ForegroundColor Gray
        $lines = Get-Content $f.FullName
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match "apply-decision|apply_decision") {
                # 주변 10줄 출력
                $start = [Math]::Max(0, $i - 2)
                $end = [Math]::Min($lines.Count - 1, $i + 10)
                Write-Host "    -- line $($i+1) 주변 --" -ForegroundColor DarkGray
                for ($j = $start; $j -le $end; $j++) {
                    Write-Host "    $($lines[$j])" -ForegroundColor Gray
                }
                $found = $true
                break
            }
        }
        if ($found) { break }
    }
}
if (-not $found) {
    Write-Host "  ⚠ apply-decision 호출 코드 못 찾음" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "진단 완료. 결과를 Claude 에게 공유해주세요." -ForegroundColor Cyan
