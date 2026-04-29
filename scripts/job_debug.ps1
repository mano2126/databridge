# Job 옵션 진단 스크립트 (v90.16)

Write-Host ""
Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host " 최근 Job 의 옵션 상태 진단" -ForegroundColor Cyan
Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host ""

# 최근 Job 가져오기
try {
    $jobs = Invoke-RestMethod "http://localhost:8000/api/v1/jobs" -ErrorAction Stop
    if ($jobs.Count -eq 0) {
        Write-Host "[X] Job 이 없음" -ForegroundColor Red
        exit 0
    }
} catch {
    Write-Host "[X] Job 목록 조회 실패: $_" -ForegroundColor Red
    exit 1
}

# 최근 5개 Job 진단
$recentJobs = $jobs | Sort-Object created_at -Descending | Select-Object -First 5

Write-Host "최근 5개 Job 의 옵션 상태:" -ForegroundColor Yellow
Write-Host ""

foreach ($j in $recentJobs) {
    $name = if ($j.name) { $j.name } else { "(unnamed)" }
    $status = $j.status
    $color = switch ($status) {
        "running"   { "Yellow" }
        "completed" { "Green" }
        "failed"    { "Red" }
        default     { "Gray" }
    }

    $jobIdShort = $j.id.Substring(0, [Math]::Min(8, $j.id.Length))

    Write-Host "-------------------------------------------------" -ForegroundColor DarkGray
    Write-Host "[$jobIdShort] $name" -ForegroundColor White
    Write-Host "  상태: $status" -ForegroundColor $color
    Write-Host "  소스: $($j.src_db) / $($j.src_database)" -ForegroundColor Gray
    Write-Host "  타겟: $($j.tgt_db) / $($j.tgt_database)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  옵션 분석:" -ForegroundColor Cyan

    $dropTable   = $j.drop_table
    $truncate    = $j.truncate_target
    $createTable = $j.create_table

    $dropColor   = if ($dropTable)   { "Green" } else { "Gray" }
    $truncColor  = if ($truncate)    { "Green" } else { "Gray" }
    $createColor = if ($createTable) { "Green" } else { "Gray" }

    Write-Host "    drop_table:        $dropTable" -ForegroundColor $dropColor
    Write-Host "    truncate_target:   $truncate" -ForegroundColor $truncColor
    Write-Host "    create_table:      $createTable" -ForegroundColor $createColor

    # 위험 진단
    if (-not $dropTable -and -not $truncate) {
        Write-Host ""
        Write-Host "    [!!!] 위험: drop=False AND truncate=False" -ForegroundColor Red
        Write-Host "       기존 데이터에 그대로 INSERT 시도 -> Duplicate Key 발생!" -ForegroundColor Red
        Write-Host "       위저드에서 TRUNCATE 또는 DROP 옵션 켜고 새 Job 만드세요" -ForegroundColor Yellow
    } elseif ($truncate -and -not $dropTable) {
        Write-Host ""
        Write-Host "    [OK] TRUNCATE 옵션 ON - 정상" -ForegroundColor Green
        Write-Host "       이관 시 타겟 데이터 삭제 후 INSERT" -ForegroundColor Gray
    } elseif ($dropTable) {
        Write-Host ""
        Write-Host "    [OK] DROP 옵션 ON - 정상" -ForegroundColor Green
        Write-Host "       이관 시 타겟 테이블 DROP 후 재생성" -ForegroundColor Gray
    }
    Write-Host ""
}

Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host " 가이드" -ForegroundColor Cyan
Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Duplicate Key 오류 발생 시 해결 방법:" -ForegroundColor Yellow
Write-Host ""
Write-Host "방법 1) 위저드에서 새 Job 만들기 - 권장"
Write-Host "  - Step 4 (실행 옵션) 에서 TRUNCATE 또는 DROP 체크"
Write-Host ""
Write-Host "방법 2) MySQL 에서 수동 삭제"
Write-Host "  docker exec -it db_mysql mysql -uroot -pbridge1234 testdb -e \""
Write-Host "    SET FOREIGN_KEY_CHECKS=0;"
Write-Host "    TRUNCATE TABLE B01_Customer;"
Write-Host "    TRUNCATE TABLE B02_LoanProduct;"
Write-Host "    TRUNCATE TABLE B03_LoanApply;"
Write-Host "    SET FOREIGN_KEY_CHECKS=1;\""
Write-Host ""
Write-Host "방법 3) 타겟 테이블 통째로 DROP"
Write-Host "  - DROP TABLE B01_Customer;"
Write-Host "  - 다음 이관 시 자동 재생성"
