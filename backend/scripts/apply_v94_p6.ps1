$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\project\databridge_full"
$PatchRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PatchSrc = (Resolve-Path (Join-Path $PatchRoot "..\..")).Path

Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DataBridge v94_p6 — 인덱스 이관 본질 처방" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = "D:\project\databridge_full_backup_v94_p6_$ts"
New-Item -Path $BackupRoot -ItemType Directory -Force | Out-Null

$rel = "backend\app\engine\index_migrator.py"
$src = Join-Path $ProjectRoot $rel
if (Test-Path $src) {
    $dst = Join-Path $BackupRoot $rel
    New-Item -Path (Split-Path -Parent $dst) -ItemType Directory -Force | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst -Force
}
$sf = Join-Path $PatchSrc $rel
Copy-Item -LiteralPath $sf -Destination $src -Force
Write-Host "  + $rel" -ForegroundColor Green

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  본부장님 호소 — 정직한 진단" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "이전 결과: 인덱스 33개 시도 → 33개 모두 1061 충돌" -ForegroundColor Red
Write-Host "  '기존 인덱스 시그니처 수집 실패: 0' 경고 후" -ForegroundColor White
Write-Host "  → 모든 인덱스를 신규로 간주하고 만들려고 시도" -ForegroundColor White
Write-Host "  → MySQL 에 이미 존재 → Duplicate key name 1061 충돌" -ForegroundColor White
Write-Host ""
Write-Host "본부장님 추측: '테이블 이관때 함께 이관 됐나?'" -ForegroundColor Cyan
Write-Host "정답: 절반 맞고, 더 깊은 본질이 있었음." -ForegroundColor White
Write-Host ""
Write-Host "진짜 본질 (DictCursor 호환 버그):" -ForegroundColor Yellow
Write-Host ""
Write-Host "  migration_engine.py L878:" -ForegroundColor White
Write-Host "    tgt_conn = pymysql.connect(..., cursorclass=DictCursor)" -ForegroundColor DarkGray
Write-Host "                                    ↑ dict 반환" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  index_migrator.py L219 (구버전):" -ForegroundColor White
Write-Host "    for r in cur.fetchall():" -ForegroundColor DarkGray
Write-Host "        tbl = r[0].lower()  ← KeyError(0)!" -ForegroundColor Red
Write-Host ""
Write-Host "  except Exception as e:" -ForegroundColor White
Write-Host "      log(f'수집 실패: {e}')  ← str(KeyError(0)) == '0'" -ForegroundColor DarkGray
Write-Host ""
Write-Host "→ 본부장님이 본 '수집 실패: 0' 의 정체 = KeyError(0)" -ForegroundColor Yellow
Write-Host "→ 시그니처 빈 set → skip 로직 작동 X → 33개 모두 시도 → 모두 충돌" -ForegroundColor Yellow

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  처방 — 2중 안전망" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[Layer 1] _row_values() 헬퍼 — dict/tuple 양쪽 안전" -ForegroundColor Cyan
Write-Host "  - DictCursor 면 컬럼명으로 lookup (대소문자 무시)" -ForegroundColor White
Write-Host "  - 일반 cursor 면 정수 인덱스 lookup" -ForegroundColor White
Write-Host "  - 4곳 모두 적용:" -ForegroundColor White
Write-Host "    · _collect_mssql_indexes  (소스가 MSSQL 일 때)" -ForegroundColor DarkGray
Write-Host "    · _collect_mysql_indexes  (소스가 MySQL 일 때)" -ForegroundColor DarkGray
Write-Host "    · _collect_target_signatures (MySQL 타겟)" -ForegroundColor DarkGray
Write-Host "    · _collect_target_signatures (MSSQL 타겟)" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[Layer 2] 1061 자동 skip — 안전망" -ForegroundColor Cyan
Write-Host "  CREATE INDEX 시도 시 'Duplicate key name' / 'already exists'" -ForegroundColor White
Write-Host "  → failed 가 아니라 skipped 로 분류 + INFO 로그" -ForegroundColor White
Write-Host "  본부장님 모토: '앞으로 똑같은 건 다시 안 발생'" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[로그 보강]" -ForegroundColor Cyan
Write-Host "  + '기존 인덱스 시그니처 수집: N개' (정상 작동 검증)" -ForegroundColor White
Write-Host "  + 실패 시 'KeyError: 0' 처럼 type(e) 도 함께 (진짜 원인 진단)" -ForegroundColor White

Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  검증 — 같은 이관 다시 실행" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "기대 로그:" -ForegroundColor Cyan
Write-Host "  '기존 인덱스 시그니처 수집: 33개'  ← Layer 1 작동" -ForegroundColor Green
Write-Host "  '인덱스 이관 결과: 생성 0, skip 33, 실패 0'  ← skip 로직 정상" -ForegroundColor Green
Write-Host ""
Write-Host "또는 (만약 시그니처 수집이 또 실패해도):" -ForegroundColor White
Write-Host "  '→ [tbl] idx_xxx 이미 존재 (skip)' x 33  ← Layer 2 fallback" -ForegroundColor Green
Write-Host ""
Write-Host "두 시나리오 모두 — failed 가 0 으로 나와야 정상" -ForegroundColor Yellow

Write-Host "`n적용 절차:" -ForegroundColor Yellow
Write-Host "  1. ZIP 풀기 (D:\project\ 위)" -ForegroundColor White
Write-Host "  2. Get-Process python | Stop-Process -Force" -ForegroundColor White
Write-Host "  3. cd D:\project\databridge_full\backend; run_backend.bat" -ForegroundColor White
Write-Host "  4. 같은 4 객체 다시 이관 → 인덱스도 정상 처리" -ForegroundColor White
Write-Host ""
Write-Host "롤백: Copy-Item '$BackupRoot\*' '$ProjectRoot' -Recurse -Force" -ForegroundColor DarkYellow
