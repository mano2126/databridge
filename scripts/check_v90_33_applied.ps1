# v90.33/34 적용 검증 스크립트
Write-Host ""
Write-Host "===== DataBridge v90.33/34 적용 검증 =====" -ForegroundColor Cyan
Write-Host ""

$base = "D:\project\databridge_full\backend\app"

# 1. v90.33 - ai_response_parser.py 검증
$parser = "$base\core\ai_response_parser.py"
Write-Host "[1] v90.33 ReDoS 수정 (ai_response_parser.py)" -ForegroundColor Yellow
if (Test-Path $parser) {
    $content = Get-Content $parser -Raw
    if ($content -match "catastrophic backtracking") {
        Write-Host "    ✓ v90.33 적용됨 (brace counting)" -ForegroundColor Green
    } else {
        Write-Host "    ✗ v90.33 적용 안 됨! - 이게 hang 원인!" -ForegroundColor Red
        Write-Host "    파일 수정 시각: $((Get-Item $parser).LastWriteTime)"
    }
} else {
    Write-Host "    ✗ 파일 없음: $parser" -ForegroundColor Red
}

# 2. v90.34 - sql_post_processor.py 존재
$postproc = "$base\core\sql_post_processor.py"
Write-Host ""
Write-Host "[2] v90.34 SQL 자기학습 (sql_post_processor.py)" -ForegroundColor Yellow
if (Test-Path $postproc) {
    Write-Host "    ✓ 파일 있음" -ForegroundColor Green
    Write-Host "    파일 수정 시각: $((Get-Item $postproc).LastWriteTime)"
} else {
    Write-Host "    ✗ 파일 없음! v90.34 ZIP 적용 필요" -ForegroundColor Red
}

# 3. v90.34 - migration_engine 통합
$engine = "$base\engine\migration_engine.py"
Write-Host ""
Write-Host "[3] v90.34 migration_engine 통합" -ForegroundColor Yellow
if (Test-Path $engine) {
    $content = Get-Content $engine -Raw
    if ($content -match "post_process_statements\(stmts") {
        Write-Host "    ✓ 통합됨" -ForegroundColor Green
    } else {
        Write-Host "    ✗ 통합 안 됨" -ForegroundColor Red
    }
} else {
    Write-Host "    ✗ 파일 없음" -ForegroundColor Red
}

# 4. Python 캐시 (__pycache__) 가 옛날 것 남아있는지
Write-Host ""
Write-Host "[4] Python 캐시 상태" -ForegroundColor Yellow
$pycache = Get-ChildItem -Path "D:\project\databridge_full\backend" -Filter "__pycache__" -Recurse -Directory -ErrorAction SilentlyContinue
$cnt = ($pycache | Measure-Object).Count
Write-Host "    __pycache__ 폴더 개수: $cnt"
if ($cnt -gt 0) {
    Write-Host "    ⚠ 캐시가 있으면 옛날 코드 실행 가능 - 삭제 권장" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "===== 진단 결과 =====" -ForegroundColor Cyan
Write-Host ""
Write-Host "본부장님 hang 패턴:" -ForegroundColor White
Write-Host "  AI 사용량 기록 직후 1분+ 침묵 -> ReDoS"
Write-Host "  → v90.33 의 ai_response_parser.py 가 적용되어야 함"
Write-Host ""
Write-Host "권장 조치:"
Write-Host "1. 백엔드 강제 종료: Get-Process python | Stop-Process -Force"
Write-Host "2. v90.34 ZIP 재추출 + 복사"
Write-Host "3. Python 캐시 완전 삭제 (필수!)"
Write-Host "4. 백엔드 재시작"
