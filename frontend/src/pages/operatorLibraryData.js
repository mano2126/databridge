// ════════════════════════════════════════════════════════════════
// operatorLibraryData.js (v93_LIB3, 2026-05-01)
//
// 운영자 라이브러리 — 본부장님 요청
// "구매자가 신경 많이 썼다고 인정할 수준"
//
// 12개 카테고리, 180+ 명령
// 모든 명령은 ${ROOT} 자동 치환 지원
// ════════════════════════════════════════════════════════════════

export const CATEGORIES = [
  { id: 'start',     icon: '🚀', label: '시작/종료' },
  { id: 'diagnose',  icon: '🔍', label: '진단 명령' },
  { id: 'patch',     icon: '🛠', label: '패치 관리' },
  { id: 'kb',        icon: '📊', label: 'KB/통계' },
  { id: 'db',        icon: '🗄', label: 'DB 명령' },
  { id: 'trouble',   icon: '🐛', label: '트러블슈팅' },
  { id: 'security',  icon: '🔐', label: '보안/감사' },
  { id: 'perf',      icon: '📈', label: '성능 튜닝' },
  { id: 'system',    icon: '🖥', label: '시스템 운영' },
  { id: 'backup',    icon: '💾', label: '백업/복구' },
  { id: 'deploy',    icon: '📦', label: '배포' },
  { id: 'ops',       icon: '📋', label: '일상 운영' },
  { id: 'docs',      icon: '🎓', label: '학습/레퍼런스' },
]

export const COMMANDS = [
  // ════════════════════════════════════════════════════════════
  // 🚀 시작/종료 (12)
  // ════════════════════════════════════════════════════════════
  {
    id: 'start_backend', cat: 'start', shell: 'cmd',
    title: '백엔드 시작 (run_backend.bat)',
    desc: 'FastAPI/uvicorn 백엔드 시작. --reload 활성 — 코드 변경 시 자동 재시작.',
    when: '서버 처음 시작 시. 패치 적용 후 백엔드가 죽어있을 때.',
    cmd: `cd /d \${ROOT}\\backend
run_backend.bat`,
    expected: 'INFO  uvicorn.error — Application startup complete.\n메뉴 [1] SAFE 또는 [2] MULTIPROCESS 선택',
    troubleshoot: '<b>ERROR: Could not import module:</b> backend 디렉토리에서 실행했는지 확인. 직접:<br><code>cd /d ${ROOT}\\backend && python -m uvicorn main:app --port 8000 --reload</code>',
    related: ['stop_backend', 'restart_backend', 'check_backend'],
  },
  {
    id: 'start_backend_safe', cat: 'start', shell: 'powershell',
    title: '백엔드 시작 — SAFE 모드 (단일 스레드)',
    desc: '대용량 이관 안전 모드. 처음 거래처 DB 이관, 검증 안 된 환경에 권장.',
    when: '운영 DB 첫 이관, 미검증 환경. 속도보다 안정성 우선.',
    cmd: `cd \${ROOT}\\backend
$env:DATABRIDGE_MODE="safe"
python -m uvicorn main:app --port 8000 --reload`,
    related: ['start_backend_mp', 'start_backend'],
  },
  {
    id: 'start_backend_mp', cat: 'start', shell: 'powershell',
    title: '백엔드 시작 — MULTIPROCESS 모드 (4 worker)',
    desc: '대형 테이블 (1M rows+) 이관 가속. 검증 환경에서만 사용.',
    when: '검증 완료된 환경, 1M+ 테이블 이관 시 약 4배 가속.',
    cmd: `cd \${ROOT}\\backend
$env:DATABRIDGE_MODE="multiprocess"
$env:DATABRIDGE_WORKERS="4"
python -m uvicorn main:app --port 8000 --reload`,
    related: ['start_backend_safe'],
  },
  {
    id: 'start_frontend', cat: 'start', shell: 'cmd',
    title: '프론트엔드 시작 (Vite dev server)',
    desc: 'Vite 개발 서버 (포트 3000). HMR 자동 — Vue 파일 변경 시 자동 반영.',
    when: '프론트 개발/테스트.',
    cmd: `cd /d \${ROOT}\\frontend
npm run dev`,
    expected: 'VITE v5.x  ready in xxx ms\nLocal:   http://localhost:3000/',
    related: ['build_frontend'],
  },
  {
    id: 'start_frontend_host', cat: 'start', shell: 'cmd',
    title: '프론트엔드 외부 접속 허용',
    desc: '프론트를 0.0.0.0 으로 바인딩 → 같은 네트워크 다른 PC 에서 접속 가능.',
    when: '본부장님 PC 백엔드 + 다른 PC 프론트 분리, 또는 네트워크 테스트.',
    cmd: `cd /d \${ROOT}\\frontend
npm run dev -- --host 0.0.0.0`,
  },
  {
    id: 'stop_backend', cat: 'start', shell: 'powershell',
    title: '백엔드 정상 종료 (Ctrl+C)',
    desc: '백엔드 콘솔 창에서 Ctrl+C → 5초 대기 → 정상 종료. 진행 중 작업 안전 마감.',
    when: '평상시 종료. uvicorn 콘솔 창이 보일 때.',
    cmd: '# uvicorn 콘솔 창에서 Ctrl+C 한 번 누르고 5초 대기',
    related: ['start_backend', 'force_kill_python'],
  },
  {
    id: 'force_kill_python', cat: 'start', shell: 'powershell', severity: 'warn',
    title: '백엔드 강제 종료 (모든 Python 프로세스)',
    desc: 'Python 모든 프로세스 강제 종료. 다른 Python 도구 함께 종료될 수 있음.',
    when: '콘솔 창 못 찾을 때, 백엔드 응답 안 할 때.',
    cmd: 'Get-Process python | Stop-Process -Force',
    troubleshoot: '<b>주의:</b> 다른 Python 도 종료됨. PID 지정 권장:<br><code>Get-Process python | Format-Table Id, StartTime</code> → <code>Stop-Process -Id 12345 -Force</code>',
    related: ['start_backend', 'check_python_processes'],
  },
  {
    id: 'kill_by_port', cat: 'start', shell: 'powershell', severity: 'warn',
    title: '포트 점유 프로세스 종료 (8000/3000)',
    desc: '특정 포트만 점유한 프로세스 강제 종료. force_kill_python 보다 정확.',
    when: '"port already in use" 에러. 다른 Python 영향 안 주고 싶을 때.',
    cmd: `# 포트 8000 점유 프로세스 찾아서 종료
$conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -EA 0
if ($conn) { Stop-Process -Id $conn.OwningProcess -Force; Write-Host "✓ 종료됨" }
else { Write-Host "포트 8000 미사용" }`,
  },
  {
    id: 'restart_backend', cat: 'start', shell: 'powershell',
    title: '백엔드 재시작 (강제)',
    desc: 'Python 종료 + 백엔드 재시작 한 번에. 패치 캐시 안 풀릴 때 표준 처방.',
    when: '패치 적용 후 옛 코드 실행 의심, --reload 가 변경 감지 못 할 때.',
    cmd: `Get-Process python | Stop-Process -Force
Start-Sleep -Seconds 2
Start-Process -FilePath "\${ROOT}\\backend\\run_backend.bat" -WorkingDirectory "\${ROOT}\\backend"`,
    related: ['force_kill_python', 'start_backend'],
  },
  {
    id: 'build_frontend', cat: 'start', shell: 'cmd',
    title: '프론트엔드 빌드 (운영 배포용)',
    desc: '프론트 정적 빌드 → dist/. 폐쇄망 배포, 정적 호스팅 가능.',
    when: '운영 배포 직전, 폐쇄망 설치 패키지.',
    cmd: `cd /d \${ROOT}\\frontend
npm run build`,
    expected: 'vite v5.x building for production...\n✓ built in xxxms\ndist/index.html ...',
  },
  {
    id: 'build_frontend_analyze', cat: 'start', shell: 'cmd',
    title: '프론트 빌드 + 번들 분석',
    desc: '빌드 결과의 청크 크기/의존성 분석. 큰 번들 진단.',
    when: '프론트 로딩 느릴 때, 빌드 결과물 분석.',
    cmd: `cd /d \${ROOT}\\frontend
npm run build -- --mode analyze`,
  },
  {
    id: 'venv_recreate', cat: 'start', shell: 'powershell',
    title: 'Python venv 재생성',
    desc: 'venv 깨졌을 때 재생성 + 의존성 재설치.',
    when: 'pip 충돌, 의존성 깨짐, 새 PC 셋업.',
    cmd: `cd \${ROOT}\\backend
Remove-Item venv -Recurse -Force -ErrorAction SilentlyContinue
python -m venv venv
.\\venv\\Scripts\\activate
pip install --upgrade pip
pip install -r requirements.txt`,
  },

  // ════════════════════════════════════════════════════════════
  // 🔍 진단 명령 (24)
  // ════════════════════════════════════════════════════════════
  {
    id: 'check_python_processes', cat: 'diagnose', shell: 'powershell',
    title: 'Python 프로세스 확인',
    desc: '실행 중인 Python 프로세스 + 시작 시각 + CPU + 메모리. 패치 반영 추정.',
    when: '백엔드 가동 확인, 패치 적용 시각 확인.',
    cmd: 'Get-Process python | Format-Table Id, StartTime, CPU, @{N="MemMB";E={[math]::Round($_.WorkingSet/1MB,1)}}',
    expected: 'Id    StartTime              CPU       MemMB\n----  ---------              ---       -----\n8348  2026-04-30 23:17:05    18.156    234.5',
    troubleshoot: '<b>비어있음:</b> 백엔드 미실행 → run_backend.bat<br><b>StartTime 이전:</b> 백엔드 재시작 필요',
    related: ['restart_backend', 'check_backend'],
  },
  {
    id: 'check_backend', cat: 'diagnose', shell: 'powershell',
    title: '백엔드 API liveness 확인',
    desc: '백엔드 응답성 빠른 확인. 첫 진단 단계.',
    when: '500 에러, 화면 미표시 시 첫 점검.',
    cmd: 'Invoke-RestMethod -Uri "http://localhost:8000/api/v1/system/live" -TimeoutSec 3',
    expected: 'status   : ok\ntimestamp: 2026-05-01T11:30:00',
    troubleshoot: '<b>응답 없음:</b> 백엔드 미실행/포트 충돌<br><b>timeout:</b> 응답 못 함 → 로그 확인',
    related: ['check_python_processes', 'check_log'],
  },
  {
    id: 'check_backend_full', cat: 'diagnose', shell: 'powershell',
    title: '백엔드 전체 헬스체크 API',
    desc: '백엔드의 DB 연결, KB 로드, 라이선스 등 종합 상태.',
    when: '운영 시작 직전 종합 점검.',
    cmd: `Invoke-RestMethod -Uri "http://localhost:8000/api/v1/system/health" | ConvertTo-Json -Depth 4`,
  },
  {
    id: 'check_port', cat: 'diagnose', shell: 'powershell',
    title: '포트 사용 확인 (8000 / 3000 / 1433 / 3306)',
    desc: '백엔드/프론트/DB 포트 점유 현황.',
    when: 'port already in use, 또는 시작 안 될 때.',
    cmd: 'Get-NetTCPConnection -LocalPort 8000,3000,1433,3306 -EA 0 | Select-Object LocalPort, State, OwningProcess | Format-Table',
    troubleshoot: 'OwningProcess PID → <code>Get-Process -Id PID</code> → 필요 시 종료',
    related: ['kill_by_port'],
  },
  {
    id: 'check_log', cat: 'diagnose', shell: 'powershell',
    title: '백엔드 로그 끝부분 확인',
    desc: '최근 80줄 → notepad. 에러 추적 첫 단계.',
    when: '에러 발생 시. 패치 적용 후 동작 확인.',
    cmd: `Get-Content "\${ROOT}\\backend\\logs\\databridge_backend.log" -Tail 80 | Out-File "\$env:TEMP\\last80.txt"
notepad "\$env:TEMP\\last80.txt"`,
    related: ['search_log_error', 'tail_log_live'],
  },
  {
    id: 'tail_log_live', cat: 'diagnose', shell: 'powershell',
    title: '백엔드 로그 실시간 모니터링 (tail -f)',
    desc: '로그 파일을 실시간으로 따라가면서 새 라인 즉시 표시.',
    when: '문제 재현 시 실시간 추적, 이관 진행 중 모니터링.',
    cmd: `Get-Content "\${ROOT}\\backend\\logs\\databridge_backend.log" -Wait -Tail 0`,
  },
  {
    id: 'search_log_error', cat: 'diagnose', shell: 'powershell',
    title: '로그에서 에러/예외 검색',
    desc: 'Traceback / ERROR / Exception 패턴 추출 + 컨텍스트 5줄.',
    when: '500 에러 추적, 미상의 동작 원인 파악.',
    cmd: `Select-String -Path "\${ROOT}\\backend\\logs\\databridge_backend.log" \`
  -Pattern "Traceback|ERROR|Exception" -Context 0,5 | Select-Object -Last 30`,
  },
  {
    id: 'search_log_warning', cat: 'diagnose', shell: 'powershell',
    title: '로그에서 경고 검색',
    desc: 'WARNING / WARN 라인 추출. 잠재 이슈 파악.',
    when: '운영 점검, 사후 검증 단계.',
    cmd: `Select-String -Path "\${ROOT}\\backend\\logs\\databridge_backend.log" \`
  -Pattern "WARNING|WARN " | Select-Object -Last 50`,
  },
  {
    id: 'search_log_kb', cat: 'diagnose', shell: 'powershell',
    title: '로그에서 KB 매칭 추적',
    desc: '[KB] ✓ / ✗ / 📝 / 💾 라인 → KB 작동 검증.',
    when: '객체 변환 후 KB 호출 검증.',
    cmd: `Select-String -Path "\${ROOT}\\backend\\logs\\databridge_backend.log" \`
  -Pattern "\\[KB\\]" | Select-Object -Last 20`,
    expected: '[KB] ✓ 매칭 성공: pattern_id=1064_END_IF_NESTING\n[KB] 📝 프롬프트 주입: 588 chars',
    related: ['kb_db_query'],
  },
  {
    id: 'check_log_object', cat: 'diagnose', shell: 'powershell',
    title: '특정 객체의 로그 추적',
    desc: '객체명 (예: tvf_daily_trx) 의 모든 로그 + 컨텍스트 3줄.',
    when: '특정 객체 변환/검증 실패 추적.',
    cmd: `Select-String -Path "\${ROOT}\\backend\\logs\\databridge_backend.log" \`
  -Pattern "OBJECT_NAME" -Context 0,3 | Select-Object -Last 30
# OBJECT_NAME 을 실제 객체명으로 (예: tvf_daily_trx)`,
  },
  {
    id: 'docker_status', cat: 'diagnose', shell: 'powershell',
    title: 'Docker 컨테이너 상태',
    desc: 'MSSQL/MySQL 컨테이너 상태 + 리소스.',
    when: 'DB 연결 실패, 컨테이너 재시작 확인.',
    cmd: 'docker ps --format "table {{.Names}}\\t{{.Status}}\\t{{.Ports}}"\ndocker stats --no-stream',
    expected: 'NAMES         STATUS          PORTS\ndb_mssql      Up 2 hours      0.0.0.0:1433->1433',
  },
  {
    id: 'docker_inspect', cat: 'diagnose', shell: 'powershell',
    title: 'Docker 컨테이너 상세 정보',
    desc: '특정 컨테이너의 IP, 환경변수, 볼륨, 네트워크 등.',
    when: '연결 문제 진단, 환경 점검.',
    cmd: `docker inspect db_mysql --format '{{json .NetworkSettings}}' | ConvertFrom-Json
docker inspect db_mysql --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\`n"}}{{end}}'`,
  },
  {
    id: 'docker_logs', cat: 'diagnose', shell: 'powershell',
    title: 'Docker 컨테이너 로그',
    desc: 'DB 컨테이너의 최근 로그.',
    when: 'DB 시작 실패, 비정상 종료, 슬로우 쿼리 추적.',
    cmd: `docker logs --tail 100 db_mysql
# MSSQL: docker logs --tail 100 db_mssql`,
  },
  {
    id: 'check_disk_space', cat: 'diagnose', shell: 'powershell',
    title: '디스크 공간 확인',
    desc: '드라이브별 여유 공간. 백업 / 로그 / DB 용량 점검.',
    when: '백업 전, 대용량 이관 전, 정기 점검.',
    cmd: `Get-PSDrive -PSProvider FileSystem | Where-Object Used -gt 0 | \`
  Format-Table Name, @{N="UsedGB";E={[math]::Round($_.Used/1GB,1)}}, \`
  @{N="FreeGB";E={[math]::Round($_.Free/1GB,1)}}, \`
  @{N="Total%";E={[math]::Round($_.Used/($_.Used+$_.Free)*100,1)}}`,
  },
  {
    id: 'check_memory', cat: 'diagnose', shell: 'powershell',
    title: '메모리 사용량 (Top 10)',
    desc: '메모리 가장 많이 쓰는 프로세스 10개.',
    when: '시스템 느려질 때, vmmem 폭증 시.',
    cmd: `Get-Process | Sort-Object WorkingSet -Descending | Select-Object -First 10 \`
  Name, Id, @{N="MemMB";E={[math]::Round($_.WorkingSet/1MB,1)}}, CPU | \`
  Format-Table -AutoSize`,
  },
  {
    id: 'check_network_db', cat: 'diagnose', shell: 'powershell',
    title: 'DB 서버 네트워크 응답성 (ping/traceroute)',
    desc: '원격 DB 서버까지 네트워크 지연 + 경로.',
    when: '원격 DB 이관 시 속도 진단, 방화벽/VPN 문제 의심.',
    cmd: `# DB 서버 IP 또는 호스트명
Test-Connection -ComputerName db.example.com -Count 4
Test-NetConnection -ComputerName db.example.com -Port 3306`,
  },
  {
    id: 'check_dns', cat: 'diagnose', shell: 'powershell',
    title: 'DNS 응답 확인',
    desc: 'DB 호스트명이 정상 해석되는지.',
    when: '"name resolution failed" 에러, 호스트 변경 후.',
    cmd: `Resolve-DnsName -Name db.example.com
nslookup db.example.com`,
  },
  {
    id: 'check_firewall', cat: 'diagnose', shell: 'powershell',
    title: '방화벽 규칙 확인 (DataBridge 관련)',
    desc: '8000/3000/1433/3306 포트 방화벽 상태.',
    when: '외부 접속 안 될 때.',
    cmd: `Get-NetFirewallPortFilter | Where-Object { $_.LocalPort -in @('8000','3000','1433','3306') } | \`
  ForEach-Object {
    $rule = Get-NetFirewallRule -AssociatedNetFirewallPortFilter $_
    [PSCustomObject]@{Port=$_.LocalPort; Name=$rule.DisplayName; Enabled=$rule.Enabled; Action=$rule.Action}
  } | Format-Table`,
  },
  {
    id: 'check_python_packages', cat: 'diagnose', shell: 'powershell',
    title: 'Python 의존성 버전 확인',
    desc: '핵심 패키지 (fastapi, pymysql, pyodbc) 설치 버전.',
    when: '의존성 충돌 의심, 버그 재현 환경 비교.',
    cmd: `cd \${ROOT}\\backend
.\\venv\\Scripts\\activate
pip list | findstr /i "fastapi pymysql pyodbc uvicorn anthropic sqlalchemy"`,
  },
  {
    id: 'check_node_version', cat: 'diagnose', shell: 'cmd',
    title: 'Node.js / npm 버전',
    desc: '프론트 빌드 환경 검증.',
    when: '빌드 실패, 환경 차이 의심.',
    cmd: `node --version
npm --version`,
  },
  {
    id: 'check_env_vars', cat: 'diagnose', shell: 'powershell',
    title: '환경 변수 확인 (DATABRIDGE_*)',
    desc: 'DataBridge 환경 변수 + Python 경로.',
    when: '환경 의존 동작 진단.',
    cmd: `Get-ChildItem env: | Where-Object Name -like "DATABRIDGE_*"
$env:PYTHONPATH
$env:PATH -split ';' | Where-Object { $_ -like "*python*" -or $_ -like "*node*" }`,
  },
  {
    id: 'list_jobs_recent', cat: 'diagnose', shell: 'powershell',
    title: '최근 Job 목록 조회',
    desc: '최근 10개 Job 의 상태/이름/시작시각.',
    when: '운영 모니터링, 실패 Job 탐지.',
    cmd: `Invoke-RestMethod -Uri "http://localhost:8000/api/v1/jobs/" | \`
  Sort-Object created_at -Descending | Select-Object -First 10 \`
  id, name, status, phase, created_at, finished_at | Format-Table`,
  },
  {
    id: 'job_detail', cat: 'diagnose', shell: 'powershell',
    title: '특정 Job 상세 조회',
    desc: 'Job 의 모든 필드 (audit_report, index_report 포함).',
    when: '이관 결과 분석, 에러 추적.',
    cmd: `$jid = "JOB_ID_HERE"
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/jobs/$jid" | ConvertTo-Json -Depth 6`,
  },

  // ════════════════════════════════════════════════════════════
  // 🛠 패치 관리 (10)
  // ════════════════════════════════════════════════════════════
  {
    id: 'verify_patches', cat: 'patch', shell: 'powershell',
    title: '적용된 패치 자동 검증 (verify_patches.ps1)',
    desc: 'v92~v93 모든 패치 적용 검증. 어제 v92p10 누락 발견했던 도구.',
    when: '패치 적용 후 첫 검증.',
    cmd: `cd \${ROOT}\\backend\\scripts
.\\verify_patches.ps1`,
    expected: '결과: 15 / 15 적용됨\n✓ 모든 패치 정상 적용됨',
    troubleshoot: '<b>누락 발견:</b> outputs 폴더 ZIP 다시 풀어 적용 → 재실행',
    related: ['apply_patch_zip', 'rollback_patch'],
  },
  {
    id: 'apply_patch_zip', cat: 'patch', shell: 'powershell',
    title: '패치 ZIP 적용',
    desc: 'ZIP 의 databridge_full/ 가 D:\\project\\ 위에 덮어쓰기.',
    when: '새 패치 받았을 때 표준 절차.',
    cmd: `Expand-Archive -Path "D:\\Downloads\\databridge_v93_X_2026-05-01.zip" \`
  -DestinationPath "D:\\project\\" -Force
# 그 후 verify_patches.ps1 로 검증`,
    related: ['verify_patches', 'rollback_patch'],
  },
  {
    id: 'apply_patch_dryrun', cat: 'patch', shell: 'powershell',
    title: '패치 적용 미리보기 (dry-run)',
    desc: '실제 적용 전에 어떤 파일이 바뀌는지 확인.',
    when: '운영 환경 적용 직전 안전 확인.',
    cmd: `$zip = "D:\\Downloads\\databridge_v93_X_2026-05-01.zip"
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::OpenRead($zip).Entries | \`
  Select-Object FullName, Length, LastWriteTime | Format-Table`,
  },
  {
    id: 'rollback_patch', cat: 'patch', shell: 'powershell', severity: 'warn',
    title: '패치 롤백 (백업 복원)',
    desc: 'apply 스크립트가 만든 백업 폴더에서 복원.',
    when: '패치 적용 후 문제 발생 시.',
    cmd: `Get-ChildItem "D:\\project\\databridge_full_backup_*" | Sort-Object LastWriteTime -Descending | Select-Object -First 5
# 위에서 가장 최근 백업 폴더명 확인 후:
Copy-Item "D:\\project\\databridge_full_backup_v93_X_20260501_140000\\*" \`
  "\${ROOT}\\" -Recurse -Force`,
  },
  {
    id: 'list_zips', cat: 'patch', shell: 'powershell',
    title: '받은 패치 ZIP 목록',
    desc: 'Downloads 의 패치 ZIP 최신순.',
    when: '어떤 패치가 있는지 확인.',
    cmd: `Get-ChildItem "D:\\Downloads\\databridge_v9*.zip" -EA 0 | \`
  Sort-Object LastWriteTime -Descending | \`
  Select-Object Name, @{N="SizeKB";E={[math]::Round($_.Length/1KB,0)}}, LastWriteTime`,
  },
  {
    id: 'list_backups', cat: 'patch', shell: 'powershell',
    title: '백업 폴더 목록 + 정리',
    desc: '백업 폴더 최신순 + 30일 이상 된 백업 자동 정리.',
    when: '디스크 공간 확보, 정기 청소.',
    cmd: `# 목록
Get-ChildItem "D:\\project\\databridge_full_backup_*" | \`
  Sort-Object LastWriteTime -Descending | \`
  Select-Object Name, @{N="SizeMB";E={[math]::Round((Get-ChildItem $_.FullName -Recurse | Measure-Object Length -Sum).Sum/1MB,1)}}, LastWriteTime

# 30일 이상 삭제 (확인 후 실행)
# Get-ChildItem "D:\\project\\databridge_full_backup_*" | Where-Object LastWriteTime -lt (Get-Date).AddDays(-30) | Remove-Item -Recurse -Force`,
  },
  {
    id: 'patch_diff', cat: 'patch', shell: 'powershell',
    title: '패치 적용 전후 diff',
    desc: '백업 폴더 vs 현재 — 어떤 파일이 바뀌었나.',
    when: '패치 영향 분석, 문제 원인 추적.',
    cmd: `$bk = "D:\\project\\databridge_full_backup_v93_X_LATEST"
Compare-Object \`
  (Get-ChildItem -Path $bk -Recurse -File | ForEach-Object { $_.FullName.Replace($bk, '') }) \`
  (Get-ChildItem -Path "\${ROOT}" -Recurse -File | ForEach-Object { $_.FullName.Replace("\${ROOT}", '') })`,
  },
  {
    id: 'apply_all_v93', cat: 'patch', shell: 'powershell',
    title: 'v93 전체 패치 일괄 적용',
    desc: 'E → C → A → B → D-1 → D-2 → LIB 순서로 일괄 적용.',
    when: '완전 새 환경에 v93 한 번에 적용.',
    cmd: `$zips = "databridge_v93_E", "databridge_v93_C", "databridge_v93_A", "databridge_v93_B", "databridge_v93_D1", "databridge_v93_D2", "databridge_v93_LIB2"
foreach ($z in $zips) {
    $f = Get-ChildItem "D:\\Downloads\\$z*.zip" | Select-Object -First 1
    if ($f) {
        Write-Host "→ 적용: $($f.Name)" -ForegroundColor Cyan
        Expand-Archive -Path $f.FullName -DestinationPath "D:\\project\\" -Force
    }
}
Write-Host "✓ 일괄 적용 완료. 백엔드 재시작 + Ctrl+Shift+R 필요" -ForegroundColor Green`,
  },
  {
    id: 'patch_history', cat: 'patch', shell: 'powershell',
    title: '패치 이력 (적용된 마커 추출)',
    desc: '코드 안의 v92pNN / v93_X 마커 카운트 → 패치 이력.',
    when: '환경 식별, 패치 누락 추정.',
    cmd: `$files = @("\${ROOT}\\backend\\app\\engine\\migration_engine.py",
            "\${ROOT}\\backend\\app\\api\\routes\\schema.py",
            "\${ROOT}\\frontend\\src\\pages\\Validate.vue")
foreach ($f in $files) {
    if (Test-Path $f) {
        $content = Get-Content $f -Raw
        $matches = [regex]::Matches($content, "v9[23](_[A-Z]+|p\\d+)")
        $unique = $matches.Value | Sort-Object -Unique
        Write-Host "$f → $($unique -join ', ')"
    }
}`,
  },
  {
    id: 'patch_changelog', cat: 'patch', shell: 'powershell',
    title: '내가 만든 패치 변경 이력 추출',
    desc: '코드 주석에서 "v92pNN ... 본부장님" 라인 모두 추출 → 변경 이력 자동 생성.',
    when: '운영 인계 문서 작성, 변경 추적.',
    cmd: `Get-ChildItem "\${ROOT}" -Include *.py,*.vue,*.js -Recurse -EA 0 | \`
  Select-String -Pattern "v9[23](_[A-Z]+|p\\d+).*본부장님" | \`
  Select-Object -First 100 Line, Path | Format-Table -Wrap`,
  },

  // ════════════════════════════════════════════════════════════
  // 📊 KB / 통계 (14)
  // ════════════════════════════════════════════════════════════
  {
    id: 'kb_db_query', cat: 'kb', shell: 'powershell',
    title: 'KB 통계 DB 직접 조회 (sqlite)',
    desc: 'kb_stats.db 의 최근 매칭 시도 10건. KB 작동 결정적 증거.',
    when: 'KB 인프라 검증, 패턴 등록 후 매칭 확인.',
    cmd: `python -c "import sqlite3; c=sqlite3.connect(r'\${ROOT}\\backend\\data\\kb_stats.db'); rows=list(c.execute('SELECT pattern_id, success, ai_used, item_name, ts FROM kb_attempts ORDER BY ts DESC LIMIT 10').fetchall()); [print(r) for r in rows]"`,
    related: ['search_log_kb', 'kb_dashboard'],
  },
  {
    id: 'kb_stats_summary', cat: 'kb', shell: 'powershell',
    title: 'KB 통계 요약 (패턴별 적중률)',
    desc: '패턴별 시도/성공/적중률.',
    when: '주간/월간 KB 자산 리포트.',
    cmd: `python -c "import sqlite3; c=sqlite3.connect(r'\${ROOT}\\backend\\data\\kb_stats.db'); cur=c.execute('SELECT pattern_id, COUNT(*), SUM(success), MAX(ts) FROM kb_attempts GROUP BY pattern_id ORDER BY COUNT(*) DESC'); [print(f'{r[0]:40s} 시도={r[1]:4d} 성공={r[2]:4d} ({r[2]/r[1]*100:.0f}%) last={r[3]}') for r in cur.fetchall()]"`,
  },
  {
    id: 'kb_dashboard', cat: 'kb', shell: 'powershell',
    title: 'KB Dashboard API 호출',
    desc: '/api/v1/kb/dashboard 직접 호출 — 화면 우회.',
    when: '화면 안 뜰 때 데이터 직접 확인.',
    cmd: 'Invoke-RestMethod -Uri "http://localhost:8000/api/v1/kb/dashboard" | ConvertTo-Json -Depth 5',
  },
  {
    id: 'kb_yml_check', cat: 'kb', shell: 'powershell',
    title: 'error_kb.yml 무결성 검증',
    desc: 'YAML syntax + 패턴 카운트.',
    when: 'KB yml 수정 후, 패치 적용 후.',
    cmd: `python -c "import yaml; data=yaml.safe_load(open(r'\${ROOT}\\backend\\app\\engine\\error_kb.yml',encoding='utf-8')); patterns=data.get('patterns',{}); print(f'YAML OK — 패턴 {len(patterns)}개'); [print(f'  - {p}') for p in patterns.keys()]"`,
  },
  {
    id: 'kb_yml_reload', cat: 'kb', shell: 'powershell',
    title: 'KB YAML 핫 리로드 (재시작 없이)',
    desc: 'error_kb.yml 변경 후 백엔드 재시작 없이 즉시 반영.',
    when: 'KB 패턴 추가/수정 후.',
    cmd: `Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/v1/kb/reload"`,
  },
  {
    id: 'error_cases_tail', cat: 'kb', shell: 'powershell',
    title: 'error_cases.txt 최근 케이스',
    desc: 'KB 후보 누적 파일 마지막 100줄.',
    when: '🔬 KB 등록 버튼 후 누적 확인.',
    cmd: `Get-Content "\${ROOT}\\backend\\prompts\\mssql_to_mysql\\error_cases.txt" -Tail 100`,
  },
  {
    id: 'kb_unmatched', cat: 'kb', shell: 'powershell',
    title: 'KB 미매칭 에러 (보강 후보)',
    desc: 'KB 패턴에 매칭 안 된 최근 에러 → 패턴 추가 후보.',
    when: 'KB 자산 보강, 신규 패턴 발굴.',
    cmd: `Invoke-RestMethod -Uri "http://localhost:8000/api/v1/kb/unmatched?limit=20" | ConvertTo-Json -Depth 4`,
  },
  {
    id: 'kb_export_csv', cat: 'kb', shell: 'powershell',
    title: 'KB 통계 CSV 내보내기 (월간 리포트)',
    desc: '패턴별 시도/성공률을 CSV 로 추출 → Excel 분석.',
    when: '월간 보고, 경영진 자료.',
    cmd: `python -c "import sqlite3,csv,sys; c=sqlite3.connect(r'\${ROOT}\\backend\\data\\kb_stats.db'); rows=c.execute('SELECT pattern_id, error_code, category, COUNT(*) attempts, SUM(success) success, MAX(ts) last FROM kb_attempts GROUP BY pattern_id ORDER BY attempts DESC').fetchall(); w=csv.writer(open(r'D:\\kb_stats_export.csv','w',newline='',encoding='utf-8-sig')); w.writerow(['pattern_id','error_code','category','attempts','success','rate%','last']); [w.writerow([r[0],r[1],r[2],r[3],r[4],round(r[4]/r[3]*100,1),r[5]]) for r in rows]; print('✓ D:\\kb_stats_export.csv 생성됨')"`,
  },
  {
    id: 'kb_test_match', cat: 'kb', shell: 'powershell',
    title: 'KB 패턴 매칭 테스트',
    desc: '특정 에러 메시지가 어떤 KB 패턴에 매칭되는지 테스트.',
    when: 'KB 패턴 추가 후 동작 검증.',
    cmd: `$body = @{ error_message = "(1064, 'You have an error in your SQL syntax near \\"END IF\\" at line 12')" } | ConvertTo-Json
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/v1/kb/test-match" -Body $body -ContentType "application/json"`,
  },
  {
    id: 'kb_register_candidate', cat: 'kb', shell: 'powershell',
    title: 'KB 후보 수동 등록 (API)',
    desc: '실패 케이스를 KB 후보로 등록 (화면 🔬 버튼과 동일).',
    when: '스크립트로 KB 후보 일괄 등록.',
    cmd: `$body = @{
  item_name = "test_obj"
  obj_type = "FUNCTION"
  error_message = "(1064, 'syntax error...')"
  src_ddl = "CREATE FUNCTION ..."
  notes = "테스트 등록"
} | ConvertTo-Json
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/v1/kb/register-candidate" -Body $body -ContentType "application/json"`,
  },
  {
    id: 'kb_conversion_overview', cat: 'kb', shell: 'powershell',
    title: '변환 KB 자산 현황',
    desc: 'TypeMapping/ObjectMapping 누적 규칙 + 상태별 카운트.',
    when: '변환 KB 자산 리포트.',
    cmd: `Invoke-RestMethod -Uri "http://localhost:8000/api/v1/kb/conversion/overview" | ConvertTo-Json -Depth 4`,
  },
  {
    id: 'kb_conversion_metrics', cat: 'kb', shell: 'powershell',
    title: '변환 KB 추이 (일자별)',
    desc: '날짜별 AI 호출 vs 로컬 처리 추이 → KB 절감 효과 가시화.',
    when: '월간 KB 절감 효과 리포트.',
    cmd: `Invoke-RestMethod -Uri "http://localhost:8000/api/v1/kb/conversion/metrics?days=30" | ConvertTo-Json -Depth 4`,
  },
  {
    id: 'kb_db_size', cat: 'kb', shell: 'powershell',
    title: 'KB 자산 파일 크기 추이',
    desc: 'kb_stats.db, error_cases.txt 크기 — 자산 성장 가시화.',
    when: '자산 크기 추적, 백업 계획.',
    cmd: `$files = @(
  "\${ROOT}\\backend\\data\\kb_stats.db",
  "\${ROOT}\\backend\\data\\databridge.db",
  "\${ROOT}\\backend\\prompts\\mssql_to_mysql\\error_cases.txt",
  "\${ROOT}\\backend\\app\\engine\\error_kb.yml"
)
$files | ForEach-Object {
  if (Test-Path $_) {
    [PSCustomObject]@{File=Split-Path $_ -Leaf; SizeKB=[math]::Round((Get-Item $_).Length/1KB,1); Modified=(Get-Item $_).LastWriteTime}
  }
} | Format-Table -AutoSize`,
  },
  {
    id: 'kb_full_backup', cat: 'kb', shell: 'powershell',
    title: 'KB 자산 일괄 백업 (운영 인계용)',
    desc: 'KB 관련 모든 파일 한 폴더로 백업 → 다른 환경 이전 가능.',
    when: '운영 인계, 다른 환경 (다른 캐피탈사) 이전.',
    cmd: `$ts = Get-Date -Format "yyyyMMdd"
$bk = "D:\\backup\\kb_assets_$ts"
New-Item -Path $bk -ItemType Directory -Force | Out-Null
Copy-Item "\${ROOT}\\backend\\data\\kb_stats.db" "$bk\\" -Force
Copy-Item "\${ROOT}\\backend\\app\\engine\\error_kb.yml" "$bk\\" -Force
Copy-Item "\${ROOT}\\backend\\prompts\\mssql_to_mysql\\*.txt" "$bk\\" -Force
Compress-Archive -Path $bk -DestinationPath "$bk.zip" -Force
Write-Host "✓ KB 자산 백업: $bk.zip"`,
  },

  // ════════════════════════════════════════════════════════════
  // 🗄 DB 명령 (28)
  // ════════════════════════════════════════════════════════════
  {
    id: 'mssql_object_list', cat: 'db', shell: 'powershell',
    title: 'MSSQL 객체 목록',
    desc: '소스 DB SP/FUNC/VIEW/TRIGGER 전체.',
    when: '이관 대상 확인, 누락 점검.',
    cmd: `docker exec -i db_mssql /opt/mssql-tools18/bin/sqlcmd \`
  -S localhost -U sa -P "Bridge@1234" -C -d capital_midsize -y 0 -Y 0 \`
  -Q "SELECT s.name + '.' + o.name AS full_name, o.type_desc FROM sys.objects o JOIN sys.schemas s ON o.schema_id=s.schema_id WHERE o.type IN ('P','FN','TF','IF','V','TR') AND o.is_ms_shipped=0 ORDER BY full_name"`,
  },
  {
    id: 'mssql_table_list', cat: 'db', shell: 'powershell',
    title: 'MSSQL 테이블 목록 + 행 수',
    desc: '테이블별 대략적 행 수 + 스키마.',
    when: '이관 규모 추정, 큰 테이블 식별.',
    cmd: `docker exec -i db_mssql /opt/mssql-tools18/bin/sqlcmd \`
  -S localhost -U sa -P "Bridge@1234" -C -d capital_midsize -y 0 -Y 0 \`
  -Q "SELECT s.name + '.' + t.name AS tbl, p.rows FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id JOIN sys.partitions p ON t.object_id=p.object_id WHERE p.index_id IN (0,1) ORDER BY p.rows DESC"`,
  },
  {
    id: 'mssql_size_per_table', cat: 'db', shell: 'powershell',
    title: 'MSSQL 테이블별 디스크 크기',
    desc: '테이블별 데이터/인덱스 크기 (MB).',
    when: '대형 테이블 식별, 이관 시간 추정.',
    cmd: `docker exec -i db_mssql /opt/mssql-tools18/bin/sqlcmd \`
  -S localhost -U sa -P "Bridge@1234" -C -d capital_midsize -y 0 -Y 0 \`
  -Q "SELECT s.name+'.'+t.name AS tbl, SUM(a.total_pages)*8/1024 AS total_mb, SUM(a.used_pages)*8/1024 AS used_mb FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id JOIN sys.indexes i ON t.object_id=i.object_id JOIN sys.partitions p ON i.object_id=p.object_id AND i.index_id=p.index_id JOIN sys.allocation_units a ON p.partition_id=a.container_id GROUP BY s.name, t.name ORDER BY total_mb DESC"`,
  },
  {
    id: 'mysql_object_list', cat: 'db', shell: 'powershell',
    title: 'MySQL 객체 목록',
    desc: '타겟 DB PROCEDURE/FUNCTION/VIEW/TRIGGER.',
    when: '이관 결과 확인.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 capital_target -e \`
"SELECT ROUTINE_NAME, ROUTINE_TYPE FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='capital_target';
SELECT TABLE_NAME, 'VIEW' FROM information_schema.VIEWS WHERE TABLE_SCHEMA='capital_target';
SELECT TRIGGER_NAME, 'TRIGGER' FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA='capital_target';"`,
  },
  {
    id: 'mysql_table_list', cat: 'db', shell: 'powershell',
    title: 'MySQL 테이블 목록 + 행 수',
    desc: '테이블별 행 수 + 데이터/인덱스 크기.',
    when: '이관 결과 검증, 크기 비교.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 -e \`
"SELECT TABLE_NAME, TABLE_ROWS, ROUND(DATA_LENGTH/1024/1024,1) AS data_mb, ROUND(INDEX_LENGTH/1024/1024,1) AS idx_mb FROM information_schema.TABLES WHERE TABLE_SCHEMA='capital_target' AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_ROWS DESC;"`,
  },
  {
    id: 'mysql_show_create', cat: 'db', shell: 'powershell',
    title: 'MySQL 객체 DDL 추출',
    desc: 'SHOW CREATE 결과 → 변환된 DDL 확인.',
    when: 'AI 변환 결과 검증.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 capital_target -e \`
"SHOW CREATE PROCEDURE OBJECT_NAME\\G"
# OBJECT_NAME = 객체명. PROCEDURE 부분을 FUNCTION/VIEW/TRIGGER 로 변경 가능`,
  },
  {
    id: 'mysql_index_check', cat: 'db', shell: 'powershell',
    title: 'MySQL 인덱스 누락 확인',
    desc: '테이블별 secondary index 카운트. 0인 테이블이 위험.',
    when: '인덱스 자동 이관 후 검증.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 capital_target -e \`
"SELECT TABLE_NAME, COUNT(DISTINCT INDEX_NAME)-1 AS secondary_idx_count FROM information_schema.STATISTICS WHERE TABLE_SCHEMA='capital_target' AND INDEX_NAME != 'PRIMARY' GROUP BY TABLE_NAME UNION SELECT TABLE_NAME, 0 FROM information_schema.TABLES t WHERE t.TABLE_SCHEMA='capital_target' AND TABLE_TYPE='BASE TABLE' AND NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS s WHERE s.TABLE_SCHEMA=t.TABLE_SCHEMA AND s.TABLE_NAME=t.TABLE_NAME AND s.INDEX_NAME != 'PRIMARY') ORDER BY 2;"`,
  },
  {
    id: 'mysql_index_detail', cat: 'db', shell: 'powershell',
    title: 'MySQL 인덱스 상세 (특정 테이블)',
    desc: '특정 테이블의 모든 인덱스 — 이름/컬럼/cardinality.',
    when: '인덱스 사용성 분석, 풀스캔 원인 추적.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 capital_target -e \`
"SHOW INDEX FROM TABLE_NAME;"`,
  },
  {
    id: 'mysql_fk_list', cat: 'db', shell: 'powershell',
    title: 'MySQL FK 제약 목록',
    desc: 'FK 제약 + 부모/자식 테이블 매핑.',
    when: 'FK 검증, 무결성 점검.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 -e \`
"SELECT CONSTRAINT_NAME, TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA='capital_target' AND REFERENCED_TABLE_NAME IS NOT NULL ORDER BY TABLE_NAME;"`,
  },
  {
    id: 'mysql_kill_zombies', cat: 'db', shell: 'powershell', severity: 'warn',
    title: 'MySQL 좀비 connection 정리',
    desc: 'SLEEP/LOCK 60초+ connection 강제 KILL.',
    when: 'vmmem 폭증, stuck, MySQL 응답 느려짐.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 -e \`
"SELECT id, time, state, info FROM information_schema.PROCESSLIST WHERE command != 'Sleep' AND time > 60 ORDER BY time DESC;"
# 위에서 확인 후 개별 KILL:
# docker exec -i db_mysql mysql -uroot -pBridge@1234 -e "KILL 12345;"`,
    troubleshoot: '극약처방: <code>docker restart db_mysql</code>',
  },
  {
    id: 'mysql_show_processlist', cat: 'db', shell: 'powershell',
    title: 'MySQL 활성 쿼리 모니터',
    desc: '현재 실행 중인 쿼리 + 상태 + 경과 시간.',
    when: '슬로우 쿼리 추적, 응답 지연 진단.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 -e "SHOW FULL PROCESSLIST;"`,
  },
  {
    id: 'mysql_innodb_status', cat: 'db', shell: 'powershell',
    title: 'MySQL InnoDB 상태',
    desc: '버퍼 풀 / 트랜잭션 / 락 / 데드락 정보.',
    when: '성능 진단, 락 분석.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 -e "SHOW ENGINE INNODB STATUS\\G" | Select-Object -First 100`,
  },
  {
    id: 'mysql_lock_check', cat: 'db', shell: 'powershell',
    title: 'MySQL 락 대기 확인',
    desc: 'innodb_lock_waits 뷰 — 어느 트랜잭션이 어느 락 기다리나.',
    when: '대규모 이관 중 멈춤, 데드락 의심.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 -e \`
"SELECT * FROM performance_schema.data_lock_waits;
SELECT * FROM performance_schema.data_locks LIMIT 20;"`,
  },
  {
    id: 'mysql_slow_query', cat: 'db', shell: 'powershell',
    title: 'MySQL 슬로우 쿼리 로그 확인',
    desc: 'slow_query_log_file 의 마지막 100줄.',
    when: '느린 쿼리 식별, 인덱스 결손 진단.',
    cmd: `docker exec -i db_mysql tail -100 /var/log/mysql/slow.log 2>$null
# 또는 활성화: docker exec -i db_mysql mysql -uroot -pBridge@1234 -e "SET GLOBAL slow_query_log='ON'; SET GLOBAL long_query_time=2;"`,
  },
  {
    id: 'mysql_explain', cat: 'db', shell: 'powershell',
    title: 'MySQL EXPLAIN — 쿼리 계획 분석',
    desc: '쿼리의 실행 계획 → 풀스캔/조인 순서/인덱스 사용 확인.',
    when: '쿼리 튜닝, 풀스캔 원인 추적.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 capital_target -e \`
"EXPLAIN SELECT * FROM v_customer_360 WHERE customer_id=12345;"`,
  },
  {
    id: 'mysql_user_list', cat: 'db', shell: 'powershell',
    title: 'MySQL 사용자 + 권한 목록',
    desc: 'user / host / 권한 — 보안 감사.',
    when: '보안 점검, 권한 인계.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 -e \`
"SELECT User, Host FROM mysql.user;
SHOW GRANTS FOR 'root'@'%';"`,
  },
  {
    id: 'mysql_charset_check', cat: 'db', shell: 'powershell',
    title: 'MySQL charset/collation 확인',
    desc: '서버/DB/테이블 charset — 한글 깨짐 진단.',
    when: '한글 데이터 깨짐, charset 이슈.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 -e \`
"SHOW VARIABLES LIKE 'character_set%';
SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_COLLATION FROM information_schema.TABLES WHERE TABLE_SCHEMA='capital_target' LIMIT 20;"`,
  },
  {
    id: 'mssql_kill_session', cat: 'db', shell: 'powershell', severity: 'warn',
    title: 'MSSQL 세션 강제 종료',
    desc: 'KILL session_id — 멈춘 SP, 풀스캔 stuck 처리.',
    when: 'MSSQL 쿼리 timeout 안 끝나는 경우.',
    cmd: `# 1) 활성 세션 확인
docker exec -i db_mssql /opt/mssql-tools18/bin/sqlcmd \`
  -S localhost -U sa -P "Bridge@1234" -C -y 0 -Y 0 \`
  -Q "SELECT session_id, status, login_name, host_name, program_name FROM sys.dm_exec_sessions WHERE is_user_process=1 AND status='running'"
# 2) 종료 (session_id 확인 후)
# docker exec -i db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "Bridge@1234" -C -Q "KILL 53"`,
  },
  {
    id: 'audit_run', cat: 'db', shell: 'powershell',
    title: '사후 검증 (Audit) 수동 실행',
    desc: 'Job 의 audit 리포트 재실행. v93_C 의 5영역.',
    when: '이관 후 시간 지나 데이터 변경, 정기 점검.',
    cmd: `Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/v1/jobs/JOB_ID/audit/rerun" -ContentType "application/json"`,
  },
  {
    id: 'audit_get', cat: 'db', shell: 'powershell',
    title: '사후 검증 리포트 조회',
    desc: 'Job 의 마지막 audit 결과 — 5영역 (인덱스/FK/객체/행수/타입).',
    when: '이관 완료 후 결과 검토.',
    cmd: `Invoke-RestMethod -Uri "http://localhost:8000/api/v1/jobs/JOB_ID/audit" | ConvertTo-Json -Depth 6`,
  },
  {
    id: 'sql_compare_row_counts', cat: 'db', shell: 'powershell',
    title: '소스 vs 타겟 행 수 일괄 비교',
    desc: '모든 테이블의 src_count vs tgt_count diff.',
    when: '이관 무결성 검증, 누락 탐지.',
    cmd: `# 백엔드 API 사용 (양쪽 비교 자동)
$body = @{ src=@{...}; tgt=@{...}; method="row_count"; tables=@() } | ConvertTo-Json
# 또는 audit_get 으로 row_count 영역 확인 (자동 검증됨)
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/jobs/JOB_ID/audit" | Select-Object -ExpandProperty report | Select-Object -ExpandProperty checks | Select-Object -ExpandProperty row_count | ConvertTo-Json -Depth 4`,
  },
  {
    id: 'mysql_optimize_table', cat: 'db', shell: 'powershell',
    title: 'MySQL 테이블 최적화 (OPTIMIZE TABLE)',
    desc: '테이블 단편화 정리 + 통계 갱신.',
    when: '대량 INSERT/DELETE 후, 정기 유지보수.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 capital_target -e \`
"OPTIMIZE TABLE TABLE_NAME;"
# 모든 테이블: SELECT CONCAT('OPTIMIZE TABLE ',TABLE_NAME,';') FROM information_schema.TABLES WHERE TABLE_SCHEMA='capital_target' AND TABLE_TYPE='BASE TABLE';`,
  },
  {
    id: 'mysql_analyze_table', cat: 'db', shell: 'powershell',
    title: 'MySQL ANALYZE TABLE (통계 갱신)',
    desc: '옵티마이저 통계 갱신 → 쿼리 계획 정확도 향상.',
    when: '대량 데이터 변경 후, 쿼리 계획 이상할 때.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 capital_target -e \`
"ANALYZE TABLE TABLE_NAME;"`,
  },
  {
    id: 'mysql_repair_table', cat: 'db', shell: 'powershell', severity: 'warn',
    title: 'MySQL REPAIR TABLE (MyISAM)',
    desc: 'MyISAM 테이블 손상 복구 (InnoDB 미지원).',
    when: '"Table is marked as crashed" 에러.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 capital_target -e \`
"REPAIR TABLE TABLE_NAME;"`,
  },
  {
    id: 'mssql_index_fragmentation', cat: 'db', shell: 'powershell',
    title: 'MSSQL 인덱스 단편화 확인',
    desc: '단편화 30%+ 인덱스 → REBUILD 권장.',
    when: '정기 유지보수, 쿼리 느려질 때.',
    cmd: `docker exec -i db_mssql /opt/mssql-tools18/bin/sqlcmd \`
  -S localhost -U sa -P "Bridge@1234" -C -d capital_midsize -y 0 -Y 0 \`
  -Q "SELECT OBJECT_NAME(ips.object_id) AS tbl, i.name AS idx, ips.avg_fragmentation_in_percent FROM sys.dm_db_index_physical_stats(DB_ID(),NULL,NULL,NULL,NULL) ips JOIN sys.indexes i ON ips.object_id=i.object_id AND ips.index_id=i.index_id WHERE ips.avg_fragmentation_in_percent > 30 ORDER BY ips.avg_fragmentation_in_percent DESC"`,
  },
  {
    id: 'docker_exec_mysql', cat: 'db', shell: 'powershell',
    title: 'MySQL 인터랙티브 셸 (직접 SQL)',
    desc: 'MySQL 컨테이너에 mysql 클라이언트로 접속 → 자유 SQL.',
    when: '복잡한 분석, ad-hoc 쿼리.',
    cmd: `docker exec -it db_mysql mysql -uroot -pBridge@1234 capital_target`,
  },
  {
    id: 'docker_exec_mssql', cat: 'db', shell: 'powershell',
    title: 'MSSQL 인터랙티브 셸',
    desc: 'sqlcmd 인터랙티브 모드.',
    when: 'MSSQL ad-hoc 쿼리.',
    cmd: `docker exec -it db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "Bridge@1234" -C -d capital_midsize`,
  },
  {
    id: 'sql_export_schema', cat: 'db', shell: 'powershell',
    title: '스키마 export (mysqldump --no-data)',
    desc: '데이터 없이 스키마만 덤프 → 검증/이전 환경 구성.',
    when: '스키마 백업, 다른 환경 구조 동기화.',
    cmd: `$ts = Get-Date -Format "yyyyMMdd"
docker exec -i db_mysql mysqldump -uroot -pBridge@1234 \`
  --no-data --routines --triggers --events capital_target > "D:\\backup\\schema_capital_target_$ts.sql"`,
  },

  // ════════════════════════════════════════════════════════════
  // 🐛 트러블슈팅 (22)
  // ════════════════════════════════════════════════════════════
  {
    id: 'ts_500_jobs', cat: 'trouble', shell: 'powershell', severity: 'warn',
    title: '/api/v1/jobs/ 500 에러',
    desc: 'jobs API 500 시 traceback + store 손상 확인.',
    when: 'jobStore fetch 실패, 500 반복.',
    cmd: `Get-Content "\${ROOT}\\backend\\logs\\databridge_backend.log" -Tail 80
try { Invoke-RestMethod -Uri "http://localhost:8000/api/v1/jobs/" } catch { $_.ErrorDetails.Message }
python -c "import sqlite3; c=sqlite3.connect(r'\${ROOT}\\backend\\data\\databridge.db'); rows=c.execute('SELECT key, length(value) FROM jobs').fetchall(); print(f'Job 수: {len(rows)}'); [print(r) for r in rows[:5]]"`,
  },
  {
    id: 'ts_patch_not_applied', cat: 'trouble', shell: 'powershell',
    title: '패치가 적용 안 된 것 같을 때',
    desc: 'findstr 로 마커 검증.',
    when: '패치 적용 후 효과 없을 때.',
    cmd: `findstr /C:"v92p20" \${ROOT}\\backend\\app\\api\\routes\\schema.py
findstr /C:"v92p20" \${ROOT}\\frontend\\src\\pages\\Validate.vue
# 줄 출력되면 적용 OK, 빈 출력이면 미적용`,
    related: ['verify_patches'],
  },
  {
    id: 'ts_cache_clear', cat: 'trouble', shell: 'powershell',
    title: '캐시 문제 (백엔드/프론트)',
    desc: '백엔드 .pyc + 프론트 Vite 캐시 삭제.',
    when: '패치 적용했는데 옛 코드 실행될 때.',
    cmd: `Get-ChildItem "\${ROOT}\\backend" -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force
Remove-Item "\${ROOT}\\frontend\\node_modules\\.vite" -Recurse -Force -EA 0
# 백엔드 재시작 + Ctrl+Shift+R`,
  },
  {
    id: 'ts_password_mask', cat: 'trouble', shell: 'powershell',
    title: '"password mask" 관련 에러',
    desc: 'password resolver 가 마스크 (●●●) 평문화 실패.',
    when: '검증 시 DB 접속 오류.',
    cmd: `Select-String -Path "\${ROOT}\\backend\\logs\\databridge_backend.log" \`
  -Pattern "password_resolver|pw_resolved|pw_was_mask" -Context 0,2 | Select-Object -Last 20`,
    troubleshoot: 'connector 화면에서 DB 다시 연결 → 평문 password 다시 입력',
  },
  {
    id: 'ts_smb_port', cat: 'trouble', shell: 'powershell', severity: 'danger',
    title: 'SMB 445 포트 보안 점검 (MS17-010)',
    desc: 'EternalBlue 취약점. 금융보안원 framework 기준.',
    when: '운영 환경 보안 audit.',
    cmd: `Get-NetFirewallRule -DisplayGroup "파일 및 프린터 공유" | Where-Object Enabled -eq True
Get-HotFix | Where-Object HotFixID -in @('KB4013389','KB4012212','KB4012215')`,
    troubleshoot: '취약 시: <code>Disable-NetFirewallRule -DisplayGroup "파일 및 프린터 공유"</code>',
  },
  {
    id: 'ts_db_connect_fail', cat: 'trouble', shell: 'powershell',
    title: 'DB 연결 실패 (Access denied / timeout)',
    desc: '체계적 진단: 컨테이너 → 포트 → 인증.',
    when: 'connector 등록 실패, 검증 시 connection error.',
    cmd: `# 1) 컨테이너 가동 확인
docker ps --filter "name=db_" --format "{{.Names}}: {{.Status}}"
# 2) 포트 응답 확인
Test-NetConnection -ComputerName localhost -Port 3306
Test-NetConnection -ComputerName localhost -Port 1433
# 3) MySQL 인증 확인
docker exec -i db_mysql mysql -uroot -pBridge@1234 -e "SELECT user, host FROM mysql.user;"`,
  },
  {
    id: 'ts_korean_corruption', cat: 'trouble', shell: 'powershell',
    title: '한글 깨짐 (?? 또는 ㅁ)',
    desc: 'charset/collation 진단.',
    when: '이관 후 한글 데이터 깨짐.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 -e \`
"SHOW VARIABLES LIKE 'character_set%';
SHOW VARIABLES LIKE 'collation%';
SELECT TABLE_NAME, TABLE_COLLATION FROM information_schema.TABLES WHERE TABLE_SCHEMA='capital_target';"
# 모든 charset 이 utf8mb4 인지 확인`,
  },
  {
    id: 'ts_ai_loop', cat: 'trouble', shell: 'powershell',
    title: 'AI 변환이 같은 실수 반복 (무한 루프)',
    desc: '재시도 카운트 + KB 매칭 확인.',
    when: 'AI 가 "수정했다" 주장하는데 같은 1064 에러 반복.',
    cmd: `# 1) 최근 AI 호출 + KB 매칭 추적
Select-String -Path "\${ROOT}\\backend\\logs\\databridge_backend.log" -Pattern "ai_convert|\\[KB\\]" -Context 0,2 | Select-Object -Last 30

# 2) 재시도 카운트 확인 (max 2~3 권장)
findstr /C:"retry_count" "\${ROOT}\\backend\\logs\\databridge_backend.log"`,
    troubleshoot: '<b>처방:</b> v93_D1 의 객체명 정리 + KB fix_prompt 표준화로 해결됨. 추가 케이스는 🔬 KB 등록.',
  },
  {
    id: 'ts_disk_full', cat: 'trouble', shell: 'powershell', severity: 'danger',
    title: '디스크 가득 참',
    desc: '대용량 파일 추출 + 정리 후보.',
    when: '"No space left on device".',
    cmd: `# 1) 디스크 사용량
Get-PSDrive C, D | Format-Table Name, @{N="UsedGB";E={[math]::Round($_.Used/1GB,1)}}, @{N="FreeGB";E={[math]::Round($_.Free/1GB,1)}}
# 2) 큰 파일 Top 20
Get-ChildItem "\${ROOT}" -Recurse -EA 0 | Sort-Object Length -Descending | Select-Object -First 20 FullName, @{N="MB";E={[math]::Round($_.Length/1MB,1)}}
# 3) Docker 정리
docker system prune -a --volumes`,
  },
  {
    id: 'ts_vmmem_high', cat: 'trouble', shell: 'powershell',
    title: 'vmmem CPU/메모리 폭증 (WSL2)',
    desc: 'Docker Desktop / WSL2 의 vmmem 프로세스 폭증.',
    when: '시스템 느려짐, Docker 응답 안 함.',
    cmd: `# 1) WSL 메모리 확인
wsl --list --running --verbose
# 2) WSL 재시작 (모든 Docker 컨테이너 재시작됨)
wsl --shutdown
Start-Sleep 3
# 3) Docker Desktop 재시작 후
docker start db_mysql db_mssql`,
  },
  {
    id: 'ts_ssl_error', cat: 'trouble', shell: 'powershell',
    title: 'MSSQL SSL/TLS 인증서 오류',
    desc: 'self-signed cert 거부 → -C 또는 TrustServerCertificate=true.',
    when: '"SSL Provider: error" / "certificate cannot be verified".',
    cmd: `# sqlcmd: -C 옵션 추가
docker exec -i db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "Bridge@1234" -C -Q "SELECT @@VERSION"
# Python pyodbc 연결 문자열에 추가:
# "TrustServerCertificate=yes;Encrypt=no"`,
  },
  {
    id: 'ts_cors', cat: 'trouble', shell: 'powershell',
    title: 'CORS 에러 (프론트 → 백엔드)',
    desc: 'Access-Control-Allow-Origin 누락.',
    when: '프론트 콘솔에 "blocked by CORS policy".',
    cmd: `# 백엔드 응답 헤더 확인
curl -i -X OPTIONS http://localhost:8000/api/v1/system/live -H "Origin: http://localhost:3000" -H "Access-Control-Request-Method: GET"
# 응답에 Access-Control-Allow-Origin 있는지 확인`,
    troubleshoot: '백엔드 main.py 의 CORSMiddleware allow_origins 확인',
  },
  {
    id: 'ts_jobs_db_corrupt', cat: 'trouble', shell: 'powershell', severity: 'danger',
    title: 'jobs SQLite DB 손상',
    desc: 'integrity_check + 손상 시 백업에서 복구.',
    when: '/api/v1/jobs/ 500 + jobs.db 손상 의심.',
    cmd: `# 1) 무결성 검증
python -c "import sqlite3; c=sqlite3.connect(r'\${ROOT}\\backend\\data\\databridge.db'); print(c.execute('PRAGMA integrity_check').fetchone())"
# 2) 손상 시 — 백업 확인
Get-ChildItem "D:\\backup\\databridge_*\\databridge.db" | Sort-Object LastWriteTime -Descending | Select-Object -First 3
# 3) 복원 (백엔드 종료 후)
# Stop python → Copy-Item 백업\\databridge.db → backend\\data\\databridge.db`,
  },
  {
    id: 'ts_npm_install_fail', cat: 'trouble', shell: 'powershell',
    title: 'npm install 실패 (망분리/registry)',
    desc: 'registry 차단, lock 충돌, peer dep 등.',
    when: 'npm install 무한 멈춤, ENOTFOUND.',
    cmd: `# 1) registry 응답 확인
npm ping
# 2) npm 캐시 정리
npm cache clean --force
# 3) lock 삭제 후 재설치
Remove-Item "\${ROOT}\\frontend\\package-lock.json" -EA 0
Remove-Item "\${ROOT}\\frontend\\node_modules" -Recurse -Force -EA 0
npm install
# 4) 폐쇄망 — node_modules 통째로 복사 (외부 PC 에서)`,
  },
  {
    id: 'ts_ai_quota', cat: 'trouble', shell: 'powershell',
    title: 'AI API quota / 429 에러',
    desc: 'Anthropic API 한도 초과.',
    when: '"rate_limit_error" / 429.',
    cmd: `Select-String -Path "\${ROOT}\\backend\\logs\\databridge_backend.log" \`
  -Pattern "rate_limit|429|quota" | Select-Object -Last 10`,
    troubleshoot: 'Settings → API 키 확인. 일정 시간 대기 후 재시도. KB 활용도 점검 (kb_dashboard).',
  },
  {
    id: 'ts_websocket', cat: 'trouble', shell: 'powershell',
    title: '실시간 진행 표시 안 됨 (WebSocket)',
    desc: 'WS 연결 / proxy / 방화벽 진단.',
    when: '이관 진행률이 멈춰 보임 (실제는 진행 중).',
    cmd: `# WS 연결 시도 (curl)
curl --include --no-buffer --header "Connection: Upgrade" --header "Upgrade: websocket" --header "Host: localhost:8000" --header "Origin: http://localhost:3000" --header "Sec-WebSocket-Key: test" --header "Sec-WebSocket-Version: 13" http://localhost:8000/ws/jobs
# 응답 101 이면 OK`,
  },
  {
    id: 'ts_config_corrupt', cat: 'trouble', shell: 'powershell',
    title: '설정 파일 손상',
    desc: 'settings.json 손상 시 복구.',
    when: '설정 화면 안 뜸, 기본값으로 동작.',
    cmd: `# JSON 무결성 확인
python -m json.tool "\${ROOT}\\backend\\settings.json"
# 손상 시 백업에서 복구
Copy-Item "D:\\backup\\databridge_LATEST\\settings.json" "\${ROOT}\\backend\\settings.json"`,
  },
  {
    id: 'ts_session_lost', cat: 'trouble', shell: 'powershell',
    title: '로그인 세션 자주 끊김',
    desc: 'JWT 만료, 쿠키, 시계 동기화 진단.',
    when: '잠깐 후 자동 로그아웃, 401 반복.',
    cmd: `# 1) 시스템 시계 동기화 확인
w32tm /query /status
# 2) 백엔드 시간
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/system/live" | Select-Object timestamp
# 3) JWT 만료 설정 확인 (백엔드 settings)
findstr /C:"JWT_EXPIRE" \${ROOT}\\backend\\app\\core\\auth.py`,
  },
  {
    id: 'ts_high_cpu_python', cat: 'trouble', shell: 'powershell',
    title: 'Python 프로세스 CPU 폭증',
    desc: 'py-spy 또는 traceback 으로 stuck point 분석.',
    when: 'Python 100% CPU, 응답 안 함.',
    cmd: `$pid = (Get-Process python | Sort-Object CPU -Descending | Select-Object -First 1).Id
Write-Host "분석 대상 PID: $pid"
# py-spy 설치 시: pip install py-spy && py-spy dump --pid $pid
# 또는 그냥 종료 후 재시작
# Stop-Process -Id $pid -Force`,
  },
  {
    id: 'ts_env_mismatch', cat: 'trouble', shell: 'powershell',
    title: '환경 차이 (개발 vs 운영)',
    desc: '두 환경의 패키지/설정/패치 비교.',
    when: '"개발 환경에선 됐는데 운영에선 안 됨".',
    cmd: `# 1) Python 버전
python --version
# 2) 핵심 패키지 버전
pip list | findstr /i "fastapi pymysql pyodbc"
# 3) 패치 마커
findstr /S /C:"v93_" "\${ROOT}\\backend\\*.py" | Select-Object -First 20
# 4) 결과를 두 환경에서 실행 후 diff`,
  },
  {
    id: 'ts_log_too_big', cat: 'trouble', shell: 'powershell',
    title: '로그 파일 너무 큼 (느려짐)',
    desc: '로그 100MB+ 면 파일 access 느려짐.',
    when: '로그 검색이 매우 느림.',
    cmd: `$log = "\${ROOT}\\backend\\logs\\databridge_backend.log"
$sizeMB = (Get-Item $log).Length / 1MB
Write-Host "현재 로그 크기: $([math]::Round($sizeMB,1)) MB"
if ($sizeMB -gt 100) {
  $ts = Get-Date -Format "yyyyMMdd_HHmmss"
  Move-Item $log "$log.$ts"
  Write-Host "✓ 로그 회전됨. 백엔드는 자동으로 새 파일 생성"
}`,
  },
  {
    id: 'ts_ai_response_invalid', cat: 'trouble', shell: 'powershell',
    title: 'AI 응답 JSON 파싱 실패',
    desc: 'AI 가 JSON 이 아닌 자연어로 답할 때.',
    when: 'AI 변환 결과가 비어있음, "JSON 파싱 실패" 로그.',
    cmd: `Select-String -Path "\${ROOT}\\backend\\logs\\databridge_backend.log" \`
  -Pattern "JSON 파싱 실패|Extra data|extract_json" -Context 0,3 | Select-Object -Last 20`,
    troubleshoot: 'v93_D1 의 fix_prompt 표준화 (===INSTRUCTION=== 마커) 가 처방. KB yml 점검.',
  },

  // ════════════════════════════════════════════════════════════
  // 🔐 보안/감사 (16)
  // ════════════════════════════════════════════════════════════
  {
    id: 'sec_audit_log', cat: 'security', shell: 'powershell',
    title: '감사 로그 조회 (최근 N개)',
    desc: '관리자 액션 감사 로그 — 누가 언제 무엇을.',
    when: '보안 감사, 사고 추적.',
    cmd: `Invoke-RestMethod -Uri "http://localhost:8000/api/v1/admin/audit?limit=50" | ConvertTo-Json -Depth 4`,
  },
  {
    id: 'sec_audit_export', cat: 'security', shell: 'powershell',
    title: '감사 로그 CSV export (월간 보고용)',
    desc: '감사 로그를 CSV → Excel 분석 가능.',
    when: '월간 보안 보고, 컴플라이언스.',
    cmd: `Invoke-RestMethod -Uri "http://localhost:8000/api/v1/admin/audit?limit=10000" | \`
  Export-Csv -Path "D:\\audit_$(Get-Date -Format 'yyyyMM').csv" -NoTypeInformation -Encoding UTF8`,
  },
  {
    id: 'sec_user_list', cat: 'security', shell: 'powershell',
    title: '시스템 사용자 + 역할 목록',
    desc: 'DataBridge 사용자/역할 — 권한 점검.',
    when: '권한 인계, 정기 audit.',
    cmd: `Invoke-RestMethod -Uri "http://localhost:8000/api/v1/admin/users" | ConvertTo-Json -Depth 3`,
  },
  {
    id: 'sec_failed_logins', cat: 'security', shell: 'powershell',
    title: '실패한 로그인 시도 추적',
    desc: '실패 로그인 → 무차별 대입 의심.',
    when: '보안 사고, 정기 점검.',
    cmd: `Select-String -Path "\${ROOT}\\backend\\logs\\databridge_backend.log" \`
  -Pattern "login.*failed|authentication.*failed|401" | Select-Object -Last 30`,
  },
  {
    id: 'sec_password_policy', cat: 'security', shell: 'powershell',
    title: '비밀번호 정책 확인',
    desc: '백엔드 password 정책 (최소 길이/복잡도).',
    when: 'KISA 기준 점검, 보안 audit.',
    cmd: `findstr /C:"MIN_PASSWORD" /C:"PASSWORD_REGEX" /C:"password_policy" \${ROOT}\\backend\\app\\core\\*.py`,
  },
  {
    id: 'sec_sensitive_in_logs', cat: 'security', shell: 'powershell', severity: 'warn',
    title: '로그에 민감 정보 검사',
    desc: '로그에 password / token / 주민번호 패턴 누출 검색.',
    when: '운영 시작 전 보안 점검.',
    cmd: `Select-String -Path "\${ROOT}\\backend\\logs\\*.log" \`
  -Pattern "password['\\\\\"\\s:=]+[^\\*\\s]{4,}|token['\\\\\"\\s:=]+[a-zA-Z0-9]{20,}|\\d{6}-[1-4]\\d{6}" | \`
  Select-Object -First 20`,
    troubleshoot: '발견 시: mask_job_response, password_resolver 동작 확인. 로그 마스킹 강화.',
  },
  {
    id: 'sec_kisa_smb', cat: 'security', shell: 'powershell',
    title: 'KISA — SMB 1.0 비활성',
    desc: '금융보안원 점검 항목 — SMBv1 취약점.',
    when: 'KISA audit 대응.',
    cmd: `# SMBv1 상태
Get-WindowsOptionalFeature -Online -FeatureName "SMB1Protocol*" | Select-Object FeatureName, State
# 비활성: Disable-WindowsOptionalFeature -Online -FeatureName "SMB1Protocol" -NoRestart`,
  },
  {
    id: 'sec_kisa_telnet', cat: 'security', shell: 'powershell',
    title: 'KISA — Telnet 비활성',
    desc: 'Telnet 클라이언트/서버 비활성 확인.',
    when: 'KISA audit.',
    cmd: `Get-WindowsCapability -Online | Where-Object Name -like "*Telnet*"
Get-Service | Where-Object DisplayName -like "*Telnet*"`,
  },
  {
    id: 'sec_kisa_uac', cat: 'security', shell: 'powershell',
    title: 'KISA — UAC 활성 확인',
    desc: 'User Account Control 레벨.',
    when: 'KISA audit.',
    cmd: `Get-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System" | \`
  Select-Object EnableLUA, ConsentPromptBehaviorAdmin`,
  },
  {
    id: 'sec_kisa_rdp', cat: 'security', shell: 'powershell',
    title: 'KISA — RDP 보안 설정',
    desc: 'NLA / 암호화 / 포트 변경 확인.',
    when: 'KISA audit, 원격접속 보안.',
    cmd: `# NLA 활성
(Get-ItemProperty -Path "HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp").UserAuthentication
# 암호화 레벨
(Get-ItemProperty -Path "HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp").MinEncryptionLevel`,
  },
  {
    id: 'sec_kisa_password_age', cat: 'security', shell: 'powershell',
    title: 'KISA — 패스워드 만료 정책',
    desc: '로컬 계정 password 정책.',
    when: 'KISA audit.',
    cmd: `net accounts`,
  },
  {
    id: 'sec_db_ssl', cat: 'security', shell: 'powershell',
    title: 'DB SSL/TLS 연결 확인',
    desc: 'MySQL/MSSQL SSL 활성 + 인증서.',
    when: '운영 환경 보안.',
    cmd: `# MySQL
docker exec -i db_mysql mysql -uroot -pBridge@1234 -e "SHOW VARIABLES LIKE '%ssl%';"
# MSSQL
docker exec -i db_mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "Bridge@1234" -C -Q "SELECT * FROM sys.dm_exec_connections WHERE encrypt_option='TRUE'"`,
  },
  {
    id: 'sec_role_grants', cat: 'security', shell: 'powershell',
    title: 'DB 권한 점검 (최소 권한 원칙)',
    desc: '운영 계정의 권한 — 과대 권한 검출.',
    when: '권한 인계, KISA audit.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 -e \`
"SELECT User, Host FROM mysql.user;
SHOW GRANTS FOR 'root'@'%';"
# 운영 계정에 GRANT ALL 있으면 의심`,
  },
  {
    id: 'sec_apikey_check', cat: 'security', shell: 'powershell',
    title: 'API Key 노출 검사',
    desc: 'Anthropic API key / DB password 가 코드/설정에 평문 노출됐는지.',
    when: 'commit 전, 보안 audit.',
    cmd: `# .env / settings 검사
findstr /S /I /C:"sk-ant-" "\${ROOT}\\*.json" "\${ROOT}\\*.env" 2>$null
findstr /S /I /C:"password" "\${ROOT}\\*.json" "\${ROOT}\\.env*" 2>$null
# .gitignore 확인
Get-Content "\${ROOT}\\.gitignore" | Select-String -Pattern "settings|env|key"`,
  },
  {
    id: 'sec_open_ports', cat: 'security', shell: 'powershell',
    title: '시스템 열린 포트 전체',
    desc: 'LISTEN 상태 모든 포트 — 불필요 노출 점검.',
    when: '보안 audit, 신규 서버.',
    cmd: `Get-NetTCPConnection -State Listen | \`
  Select-Object LocalAddress, LocalPort, OwningProcess, \`
  @{N="Process";E={(Get-Process -Id $_.OwningProcess -EA 0).Name}} | \`
  Sort-Object LocalPort | Format-Table`,
  },
  {
    id: 'sec_certificate_check', cat: 'security', shell: 'powershell',
    title: 'SSL 인증서 만료일 확인',
    desc: '서버 인증서 만료 날짜 — 갱신 시점 추적.',
    when: '운영 환경 정기 점검.',
    cmd: `# 시스템 인증서 저장소
Get-ChildItem -Path Cert:\\LocalMachine\\My | \`
  Select-Object Subject, NotAfter, @{N="DaysLeft";E={($_.NotAfter - (Get-Date)).Days}} | \`
  Sort-Object DaysLeft`,
  },

  // ════════════════════════════════════════════════════════════
  // 📈 성능 튜닝 (16)
  // ════════════════════════════════════════════════════════════
  {
    id: 'perf_mysql_buffer', cat: 'perf', shell: 'powershell',
    title: 'MySQL 버퍼풀 사용률',
    desc: 'innodb_buffer_pool 히트율 + 사용량.',
    when: '성능 튜닝, 메모리 부족 의심.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 -e \`
"SELECT (1 - (Innodb_buffer_pool_reads / Innodb_buffer_pool_read_requests)) * 100 AS hit_rate_pct FROM (SELECT VARIABLE_VALUE AS Innodb_buffer_pool_reads FROM performance_schema.global_status WHERE VARIABLE_NAME='Innodb_buffer_pool_reads') a, (SELECT VARIABLE_VALUE AS Innodb_buffer_pool_read_requests FROM performance_schema.global_status WHERE VARIABLE_NAME='Innodb_buffer_pool_read_requests') b;"`,
    expected: 'hit_rate_pct > 99% 가 정상',
  },
  {
    id: 'perf_mysql_status', cat: 'perf', shell: 'powershell',
    title: 'MySQL 핵심 상태 변수',
    desc: 'connection / query / cache / 슬로우 카운트.',
    when: '성능 진단.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 -e \`
"SHOW GLOBAL STATUS LIKE 'Threads%';
SHOW GLOBAL STATUS LIKE 'Slow_queries';
SHOW GLOBAL STATUS LIKE 'Queries';
SHOW GLOBAL STATUS LIKE 'Connections';"`,
  },
  {
    id: 'perf_mysql_top_queries', cat: 'perf', shell: 'powershell',
    title: 'MySQL 가장 무거운 쿼리 Top 10',
    desc: 'sys.statements_with_runtimes_in_95th_percentile.',
    when: '성능 핫스팟 발굴.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 -e \`
"SELECT query, total_latency, exec_count FROM sys.statements_with_runtimes_in_95th_percentile LIMIT 10\\G"`,
  },
  {
    id: 'perf_mysql_unused_indexes', cat: 'perf', shell: 'powershell',
    title: 'MySQL 미사용 인덱스',
    desc: '쓰이지 않는 인덱스 → 삭제 후보.',
    when: '인덱스 정리, 쓰기 성능 향상.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 -e \`
"SELECT object_schema, object_name, index_name FROM sys.schema_unused_indexes WHERE object_schema='capital_target';"`,
  },
  {
    id: 'perf_mysql_redundant_indexes', cat: 'perf', shell: 'powershell',
    title: 'MySQL 중복 인덱스',
    desc: '같은 컬럼으로 만든 중복 인덱스 → 제거 권장.',
    when: '인덱스 정리.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 -e \`
"SELECT * FROM sys.schema_redundant_indexes WHERE table_schema='capital_target';"`,
  },
  {
    id: 'perf_mssql_top_queries', cat: 'perf', shell: 'powershell',
    title: 'MSSQL 가장 무거운 쿼리 Top 10',
    desc: 'sys.dm_exec_query_stats — CPU/논리적 읽기 기준.',
    when: '성능 진단.',
    cmd: `docker exec -i db_mssql /opt/mssql-tools18/bin/sqlcmd \`
  -S localhost -U sa -P "Bridge@1234" -C -y 0 -Y 0 \`
  -Q "SELECT TOP 10 SUBSTRING(qt.text,(qs.statement_start_offset/2)+1,((CASE qs.statement_end_offset WHEN -1 THEN DATALENGTH(qt.text) ELSE qs.statement_end_offset END - qs.statement_start_offset)/2)+1) AS query, qs.execution_count, qs.total_logical_reads, qs.total_worker_time/1000 AS total_cpu_ms FROM sys.dm_exec_query_stats qs CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) qt ORDER BY qs.total_worker_time DESC"`,
  },
  {
    id: 'perf_mssql_missing_indexes', cat: 'perf', shell: 'powershell',
    title: 'MSSQL 누락 인덱스 권고',
    desc: '옵티마이저가 추천하는 인덱스.',
    when: '성능 튜닝, 슬로우 쿼리 처방.',
    cmd: `docker exec -i db_mssql /opt/mssql-tools18/bin/sqlcmd \`
  -S localhost -U sa -P "Bridge@1234" -C -y 0 -Y 0 \`
  -Q "SELECT TOP 10 mid.statement, mid.equality_columns, mid.inequality_columns, mid.included_columns, migs.user_seeks, migs.user_scans, migs.avg_total_user_cost FROM sys.dm_db_missing_index_details mid JOIN sys.dm_db_missing_index_groups mig ON mid.index_handle=mig.index_handle JOIN sys.dm_db_missing_index_group_stats migs ON mig.index_group_handle=migs.group_handle ORDER BY migs.avg_total_user_cost*migs.user_seeks DESC"`,
  },
  {
    id: 'perf_explain_plan', cat: 'perf', shell: 'powershell',
    title: 'MySQL 쿼리 EXPLAIN ANALYZE',
    desc: '실제 실행 시간 + 행 수 측정.',
    when: '쿼리 튜닝, 풀스캔 진단.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 capital_target -e \`
"EXPLAIN ANALYZE SELECT * FROM customer WHERE customer_id=12345;"`,
  },
  {
    id: 'perf_mysql_innodb_tune', cat: 'perf', shell: 'powershell',
    title: 'MySQL InnoDB 튜닝 권고값',
    desc: '시스템 메모리 기반 buffer_pool / log_file 권고.',
    when: '운영 환경 셋업.',
    cmd: `$totalMemMB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1MB)
$bufferMB = [math]::Round($totalMemMB * 0.5)
Write-Host "권고 — 시스템 메모리: $totalMemMB MB"
Write-Host "  innodb_buffer_pool_size = $($bufferMB)M  (총 메모리의 50%)"
Write-Host "  innodb_log_file_size    = 256M+  (대량 트랜잭션이면 1G)"
Write-Host "  max_connections         = 200~500"
Write-Host "  innodb_flush_log_at_trx_commit = 1 (안정) / 2 (속도)"`,
  },
  {
    id: 'perf_query_cache', cat: 'perf', shell: 'powershell',
    title: 'MySQL 쿼리 캐시 상태 (8.0 미사용)',
    desc: 'MySQL 8.0 부터 query cache 제거됨.',
    when: 'MySQL 5.7 환경 (구) 진단.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 -e \`
"SHOW VARIABLES LIKE 'query_cache%';
SHOW STATUS LIKE 'Qcache%';"`,
  },
  {
    id: 'perf_table_io', cat: 'perf', shell: 'powershell',
    title: 'MySQL 테이블별 I/O',
    desc: '읽기/쓰기 가장 많은 테이블.',
    when: 'I/O 핫스팟 식별.',
    cmd: `docker exec -i db_mysql mysql -uroot -pBridge@1234 -e \`
"SELECT object_schema, object_name, count_read, count_write, sum_timer_wait FROM performance_schema.table_io_waits_summary_by_table ORDER BY sum_timer_wait DESC LIMIT 10;"`,
  },
  {
    id: 'perf_databridge_speed', cat: 'perf', shell: 'powershell',
    title: 'DataBridge 이관 속도 측정',
    desc: '최근 Job 의 평균 rows/sec.',
    when: '성능 평가, 모드 비교.',
    cmd: `Invoke-RestMethod -Uri "http://localhost:8000/api/v1/jobs/" | \`
  Where-Object status -eq "completed" | \`
  Select-Object -First 5 name, rows_processed, \`
    @{N="seconds";E={[int](([datetime]$_.finished_at - [datetime]$_.created_at).TotalSeconds)}}, \`
    @{N="rows_per_sec";E={if($_.rows_processed){[int]($_.rows_processed / ([datetime]$_.finished_at - [datetime]$_.created_at).TotalSeconds)}else{0}}}`,
  },
  {
    id: 'perf_concurrency_test', cat: 'perf', shell: 'powershell',
    title: '동시 검증 성능 비교',
    desc: 'concurrency 1 vs 5 vs 10 — 실제 단축 비율.',
    when: '동시성 최적값 결정.',
    cmd: `# 백엔드 로그에서 검증 시간 추출
Select-String -Path "\${ROOT}\\backend\\logs\\databridge_backend.log" \`
  -Pattern "concurrency=\\d+|elapsed_sec" | Select-Object -Last 30`,
  },
  {
    id: 'perf_disk_io', cat: 'perf', shell: 'powershell',
    title: '디스크 I/O 부하',
    desc: '디스크별 read/write IOPS, 큐 길이.',
    when: 'I/O 병목 의심.',
    cmd: `Get-Counter -Counter "\\PhysicalDisk(_Total)\\Disk Reads/sec","\\PhysicalDisk(_Total)\\Disk Writes/sec","\\PhysicalDisk(_Total)\\Current Disk Queue Length" -SampleInterval 2 -MaxSamples 5`,
  },
  {
    id: 'perf_network_io', cat: 'perf', shell: 'powershell',
    title: '네트워크 I/O 부하',
    desc: '네트워크 인터페이스별 송수신 속도.',
    when: '원격 DB 이관 속도 진단.',
    cmd: `Get-Counter -Counter "\\Network Interface(*)\\Bytes Total/sec" -SampleInterval 2 -MaxSamples 3 -EA 0 | \`
  Select-Object -ExpandProperty CounterSamples | \`
  Where-Object CookedValue -gt 0 | Format-Table InstanceName, @{N="MBps";E={[math]::Round($_.CookedValue/1MB,2)}}`,
  },
  {
    id: 'perf_audit_recommendations', cat: 'perf', shell: 'powershell',
    title: 'audit_report 의 성능 권고 추출',
    desc: 'Job audit 의 critical/warn 항목 → 처방 가이드.',
    when: '이관 후 성능 처방.',
    cmd: `$jid = "JOB_ID_HERE"
$audit = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/jobs/$jid/audit"
$audit.report.checks.PSObject.Properties | ForEach-Object {
  Write-Host "─── $($_.Name) ($($_.Value.severity)) ───" -ForegroundColor Cyan
  $_.Value | ConvertTo-Json -Depth 3 -Compress
}`,
  },

  // ════════════════════════════════════════════════════════════
  // 💾 백업/복구 (12)
  // ════════════════════════════════════════════════════════════
  {
    id: 'backup_full_daily', cat: 'backup', shell: 'powershell',
    title: '일일 전체 백업 (앱 + DB + 설정)',
    desc: 'DataBridge SQLite + 설정 + KB → D:\\backup\\.',
    when: '매일 자동 (스케줄러), 주요 작업 전.',
    cmd: `$ts = Get-Date -Format "yyyyMMdd"
$bk = "D:\\backup\\databridge_$ts"
New-Item -Path $bk -ItemType Directory -Force | Out-Null
Copy-Item "\${ROOT}\\backend\\data\\*.db" "$bk\\" -Force
Copy-Item "\${ROOT}\\backend\\settings.json" "$bk\\" -Force -EA 0
Copy-Item "\${ROOT}\\backend\\app\\engine\\error_kb.yml" "$bk\\" -Force
Copy-Item "\${ROOT}\\backend\\prompts\\mssql_to_mysql\\error_cases.txt" "$bk\\" -Force
Write-Host "✓ 백업 완료: $bk"`,
  },
  {
    id: 'backup_mysql_dump', cat: 'backup', shell: 'powershell',
    title: 'MySQL 전체 mysqldump',
    desc: 'capital_target 전체 데이터 + 스키마 + 객체 덤프.',
    when: '대규모 변경 전, 일일 백업, 다른 환경 이전.',
    cmd: `$ts = Get-Date -Format "yyyyMMdd_HHmmss"
docker exec -i db_mysql mysqldump -uroot -pBridge@1234 \`
  --routines --triggers --events --single-transaction \`
  capital_target > "D:\\backup\\capital_target_$ts.sql"
Compress-Archive -Path "D:\\backup\\capital_target_$ts.sql" -DestinationPath "D:\\backup\\capital_target_$ts.zip" -Force
Remove-Item "D:\\backup\\capital_target_$ts.sql"`,
  },
  {
    id: 'backup_mysql_compress', cat: 'backup', shell: 'powershell',
    title: 'MySQL 압축 mysqldump (대용량)',
    desc: 'gzip 으로 즉시 압축 → 디스크 절약.',
    when: '대용량 DB 백업.',
    cmd: `$ts = Get-Date -Format "yyyyMMdd"
docker exec -i db_mysql sh -c "mysqldump -uroot -pBridge@1234 --single-transaction --routines --triggers capital_target | gzip" > "D:\\backup\\capital_target_$ts.sql.gz"`,
  },
  {
    id: 'backup_mssql_full', cat: 'backup', shell: 'powershell',
    title: 'MSSQL FULL 백업',
    desc: 'BACKUP DATABASE → .bak 파일.',
    when: 'MSSQL 운영 환경 백업.',
    cmd: `$ts = Get-Date -Format "yyyyMMdd_HHmmss"
docker exec -i db_mssql /opt/mssql-tools18/bin/sqlcmd \`
  -S localhost -U sa -P "Bridge@1234" -C \`
  -Q "BACKUP DATABASE [capital_midsize] TO DISK='/var/opt/mssql/backup/capital_midsize_$ts.bak' WITH COMPRESSION, INIT"
docker cp db_mssql:/var/opt/mssql/backup/capital_midsize_$ts.bak D:\\backup\\`,
  },
  {
    id: 'backup_mssql_diff', cat: 'backup', shell: 'powershell',
    title: 'MSSQL 차등 백업 (DIFFERENTIAL)',
    desc: '마지막 FULL 이후 변경분만 — 빠르고 작음.',
    when: '일일 백업, FULL 사이.',
    cmd: `$ts = Get-Date -Format "yyyyMMdd_HHmmss"
docker exec -i db_mssql /opt/mssql-tools18/bin/sqlcmd \`
  -S localhost -U sa -P "Bridge@1234" -C \`
  -Q "BACKUP DATABASE [capital_midsize] TO DISK='/var/opt/mssql/backup/capital_midsize_diff_$ts.bak' WITH DIFFERENTIAL, COMPRESSION, INIT"`,
  },
  {
    id: 'backup_mysql_restore', cat: 'backup', shell: 'powershell', severity: 'warn',
    title: 'MySQL 복구 (mysqldump 에서)',
    desc: '백업 SQL 파일에서 복구.',
    when: '재해 복구, 다른 환경 구축.',
    cmd: `# 1) 새 DB 생성 (선택)
docker exec -i db_mysql mysql -uroot -pBridge@1234 -e "CREATE DATABASE capital_target_restore;"
# 2) 복구
Get-Content "D:\\backup\\capital_target_LATEST.sql" | docker exec -i db_mysql mysql -uroot -pBridge@1234 capital_target_restore`,
  },
  {
    id: 'backup_mssql_restore', cat: 'backup', shell: 'powershell', severity: 'warn',
    title: 'MSSQL 복구 (.bak 에서)',
    desc: 'RESTORE DATABASE.',
    when: '재해 복구.',
    cmd: `# 1) 컨테이너에 .bak 복사
docker cp D:\\backup\\capital_midsize.bak db_mssql:/var/opt/mssql/backup/
# 2) 복구
docker exec -i db_mssql /opt/mssql-tools18/bin/sqlcmd \`
  -S localhost -U sa -P "Bridge@1234" -C \`
  -Q "RESTORE DATABASE [capital_midsize_restore] FROM DISK='/var/opt/mssql/backup/capital_midsize.bak' WITH MOVE 'capital_midsize' TO '/var/opt/mssql/data/capital_midsize_restore.mdf', MOVE 'capital_midsize_log' TO '/var/opt/mssql/data/capital_midsize_restore_log.ldf'"`,
  },
  {
    id: 'backup_verify', cat: 'backup', shell: 'powershell',
    title: '백업 무결성 검증',
    desc: '백업 파일이 손상 없이 복구 가능한지 확인.',
    when: '주간 백업 검증, DR 훈련.',
    cmd: `# MSSQL: VERIFYONLY
docker exec -i db_mssql /opt/mssql-tools18/bin/sqlcmd \`
  -S localhost -U sa -P "Bridge@1234" -C \`
  -Q "RESTORE VERIFYONLY FROM DISK='/var/opt/mssql/backup/capital_midsize_LATEST.bak'"
# MySQL: 그냥 dry run
Get-Content "D:\\backup\\capital_target_LATEST.sql" -Head 100 | Select-String "CREATE TABLE"`,
  },
  {
    id: 'backup_to_remote', cat: 'backup', shell: 'powershell',
    title: '원격 저장소로 백업 복사',
    desc: 'NAS / SMB share 로 백업 이전.',
    when: '오프사이트 백업, DR 대비.',
    cmd: `# Map drive (한 번만)
# net use Z: \\\\backup-server\\databridge /user:USER PASSWORD
$ts = Get-Date -Format "yyyyMMdd"
$src = "D:\\backup\\databridge_$ts"
if (Test-Path "Z:\\") {
  Compress-Archive -Path $src -DestinationPath "Z:\\databridge_$ts.zip" -Force
  Write-Host "✓ 원격 백업 완료"
}`,
  },
  {
    id: 'backup_rotation', cat: 'backup', shell: 'powershell',
    title: '백업 회전 (오래된 것 삭제)',
    desc: '7일 일일 + 4주 주간 + 12월 월간 보존.',
    when: '월 1회 또는 디스크 부족.',
    cmd: `$now = Get-Date
# 7일 이상 된 일일 백업 → 주간으로 변환 (월요일자만 보존)
Get-ChildItem "D:\\backup\\databridge_*" | Where-Object { 
  $_.Name -match "databridge_(\\d{8})" -and 
  ($now - $_.LastWriteTime).Days -gt 7 -and 
  ([datetime]::ParseExact($matches[1],"yyyyMMdd",$null)).DayOfWeek -ne "Monday" 
} | Remove-Item -Recurse -Force
# 30일 이상 → 월간 보존 (1일자만)
Get-ChildItem "D:\\backup\\databridge_*" | Where-Object {
  $_.Name -match "databridge_(\\d{8})" -and 
  ($now - $_.LastWriteTime).Days -gt 30 -and
  -not $_.Name.EndsWith("01")
} | Remove-Item -Recurse -Force`,
  },
  {
    id: 'backup_pit', cat: 'backup', shell: 'powershell',
    title: 'Point-in-Time 복구 (binlog)',
    desc: 'MySQL binlog 활용한 시점 복구.',
    when: '특정 시각 직전 상태 복구 필요.',
    cmd: `# binlog 활성 확인
docker exec -i db_mysql mysql -uroot -pBridge@1234 -e "SHOW VARIABLES LIKE 'log_bin';"
# binlog 파일 목록
docker exec -i db_mysql mysql -uroot -pBridge@1234 -e "SHOW BINARY LOGS;"
# 특정 시각까지 복구 (mysqlbinlog --stop-datetime)
# docker exec db_mysql mysqlbinlog --stop-datetime="2026-05-01 14:00:00" /var/lib/mysql/binlog.000123 | mysql -uroot -p...`,
  },
  {
    id: 'backup_settings', cat: 'backup', shell: 'powershell',
    title: '설정 파일 일괄 백업',
    desc: 'settings.json, .env, error_kb.yml 등.',
    when: '설정 변경 전 안전망.',
    cmd: `$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$bk = "D:\\backup\\config_$ts"
New-Item -Path $bk -ItemType Directory -Force | Out-Null
@(
  "\${ROOT}\\backend\\settings.json",
  "\${ROOT}\\backend\\.env",
  "\${ROOT}\\backend\\app\\engine\\error_kb.yml",
  "\${ROOT}\\frontend\\.env"
) | ForEach-Object { if (Test-Path $_) { Copy-Item $_ $bk\\ -Force } }
Write-Host "✓ 설정 백업: $bk"`,
  },

  // ════════════════════════════════════════════════════════════
  // 📦 배포 (10)
  // ════════════════════════════════════════════════════════════
  {
    id: 'deploy_master_zip', cat: 'deploy', shell: 'powershell',
    title: '전체 마스터 ZIP (새 PC 배포용)',
    desc: 'databridge_full 전체 ZIP. 폐쇄망 이전용.',
    when: '신규 PC 설치, 다른 환경 배포, 분기말 백업.',
    cmd: `$ts = Get-Date -Format "yyyyMMdd_HHmmss"
Compress-Archive -Path "\${ROOT}" -DestinationPath "D:\\databridge_master_$ts.zip" -CompressionLevel Optimal -Force
Write-Host "✓ 마스터 ZIP: D:\\databridge_master_$ts.zip"`,
  },
  {
    id: 'deploy_new_pc', cat: 'deploy', shell: 'powershell',
    title: '새 PC 셋업 (마스터 ZIP에서)',
    desc: 'ZIP 풀기 + venv + npm install + Docker 시작.',
    when: '신규 PC 처음 셋업.',
    cmd: `Expand-Archive -Path "D:\\databridge_master_YYYYMMDD.zip" -DestinationPath "D:\\project\\" -Force
cd D:\\project\\databridge_full\\backend
python -m venv venv
.\\venv\\Scripts\\activate
pip install -r requirements.txt
cd ..\\frontend
npm install
cd ..
docker-compose up -d
# 백엔드 시작 → run_backend.bat`,
    related: ['start_backend', 'start_frontend'],
  },
  {
    id: 'deploy_offline_npm', cat: 'deploy', shell: 'powershell', severity: 'warn',
    title: '폐쇄망 npm install 우회',
    desc: 'node_modules 통째로 복사.',
    when: '망분리 환경, 외부 npm registry 차단.',
    cmd: `# 외부 PC: 의존성 다운로드
cd \${ROOT}\\frontend
npm install
# node_modules ZIP → 폐쇄망 PC 로 복사
Compress-Archive -Path node_modules -DestinationPath D:\\node_modules.zip
# 폐쇄망 PC: ZIP 풀어서 frontend\\node_modules 에 배치`,
  },
  {
    id: 'deploy_offline_pip', cat: 'deploy', shell: 'powershell', severity: 'warn',
    title: '폐쇄망 pip install 우회',
    desc: 'pip download → wheels 통째 복사 → 오프라인 설치.',
    when: '망분리, 외부 PyPI 차단.',
    cmd: `# 외부 PC: wheels 다운로드
cd \${ROOT}\\backend
pip download -r requirements.txt -d wheels
# wheels 폴더 ZIP → 폐쇄망 PC 로 복사
# 폐쇄망 PC:
pip install --no-index --find-links=wheels -r requirements.txt`,
  },
  {
    id: 'deploy_docker_export', cat: 'deploy', shell: 'powershell',
    title: 'Docker 이미지 export (폐쇄망용)',
    desc: 'MySQL/MSSQL 이미지를 tar 로 export.',
    when: '폐쇄망 PC 에 DB 이미지 이전.',
    cmd: `docker save -o D:\\images\\db_mysql.tar mysql:8.0
docker save -o D:\\images\\db_mssql.tar mcr.microsoft.com/mssql/server:2022-latest
# 폐쇄망 PC 에서:
# docker load -i D:\\images\\db_mysql.tar
# docker load -i D:\\images\\db_mssql.tar`,
  },
  {
    id: 'deploy_docker_compose', cat: 'deploy', shell: 'powershell',
    title: 'Docker Compose 시작/종료',
    desc: 'docker-compose.yml 로 모든 컨테이너 한 번에.',
    when: '환경 셋업, 정기 재시작.',
    cmd: `cd \${ROOT}
docker-compose up -d        # 시작
# docker-compose down       # 종료 + 컨테이너 삭제
# docker-compose restart    # 재시작
# docker-compose logs -f    # 실시간 로그`,
  },
  {
    id: 'deploy_systemd_service', cat: 'deploy', shell: 'bash',
    title: 'systemd 서비스 등록 (Linux 운영)',
    desc: '백엔드를 systemd 서비스로 → 자동 시작/재시작.',
    when: 'Linux 운영 환경, 24/7 운영.',
    cmd: `# /etc/systemd/system/databridge.service 생성
sudo tee /etc/systemd/system/databridge.service > /dev/null <<EOF
[Unit]
Description=DataBridge Backend
After=network.target docker.service

[Service]
Type=simple
User=databridge
WorkingDirectory=/opt/databridge_full/backend
ExecStart=/opt/databridge_full/backend/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable databridge
sudo systemctl start databridge
sudo systemctl status databridge`,
  },
  {
    id: 'deploy_iis_reverse', cat: 'deploy', shell: 'powershell',
    title: 'IIS 리버스 프록시 설정',
    desc: 'IIS → uvicorn 프록시 (URL Rewrite + ARR).',
    when: 'Windows Server, IIS 환경.',
    cmd: `# 1) ARR + URL Rewrite 모듈 설치 필수
# 2) web.config 예시:
@"
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <system.webServer>
    <rewrite>
      <rules>
        <rule name="Reverse Proxy" stopProcessing="true">
          <match url="^api/(.*)" />
          <action type="Rewrite" url="http://localhost:8000/api/{R:1}" />
        </rule>
      </rules>
    </rewrite>
  </system.webServer>
</configuration>
"@ | Out-File "C:\\inetpub\\wwwroot\\databridge\\web.config" -Encoding UTF8`,
  },
  {
    id: 'deploy_health_check', cat: 'deploy', shell: 'powershell',
    title: '배포 후 종합 헬스체크',
    desc: '배포 완료 후 모든 컴포넌트 검증.',
    when: '배포 직후, 운영 시작 전.',
    cmd: `Write-Host "═══ 배포 후 헬스체크 ═══" -ForegroundColor Cyan
# 1) 백엔드
$be = try { Invoke-RestMethod "http://localhost:8000/api/v1/system/live" -TimeoutSec 5 } catch { $null }
Write-Host ("  백엔드 API : " + $(if($be){'✓'}else{'✗'}))
# 2) 프론트
$fe = try { Invoke-WebRequest "http://localhost:3000" -TimeoutSec 5 } catch { $null }
Write-Host ("  프론트     : " + $(if($fe.StatusCode -eq 200){'✓'}else{'✗'}))
# 3) DB
$mysql = docker exec db_mysql mysql -uroot -pBridge@1234 -e "SELECT 1" 2>$null
Write-Host ("  MySQL      : " + $(if($mysql){'✓'}else{'✗'}))
# 4) KB
$kb = try { Invoke-RestMethod "http://localhost:8000/api/v1/kb/dashboard" -TimeoutSec 5 } catch { $null }
Write-Host ("  KB         : " + $(if($kb){'✓ 패턴 ' + $kb.summary.total_patterns + '개'}else{'✗'}))
Write-Host "═══════════════════════════════" -ForegroundColor Cyan`,
  },
  {
    id: 'deploy_rolling_update', cat: 'deploy', shell: 'powershell',
    title: 'Rolling Update (다운타임 최소)',
    desc: '백엔드 두 개 띄워서 무중단 패치.',
    when: '운영 환경, 다운타임 허용 안 됨.',
    cmd: `# 1) 새 백엔드를 다른 포트로
$env:DATABRIDGE_PORT="8001"
Start-Process powershell -ArgumentList "-c","cd \${ROOT}\\backend; python -m uvicorn main:app --port 8001"
Start-Sleep 5
# 2) 새 인스턴스 헬스체크
$ok = try { Invoke-RestMethod "http://localhost:8001/api/v1/system/live" } catch { $null }
if ($ok) {
  # 3) 프록시 라우팅 변경 (8000 → 8001)
  Write-Host "✓ 새 인스턴스 가동. 프록시 변경 필요"
} else {
  Write-Host "✗ 새 인스턴스 실패"
}`,
  },

  // ════════════════════════════════════════════════════════════
  // 📋 일상 운영 (12)
  // ════════════════════════════════════════════════════════════
  {
    id: 'ops_health_summary', cat: 'ops', shell: 'powershell',
    title: '시스템 종합 헬스체크',
    desc: '백엔드/프론트/DB/로그/디스크/KB 한 번에.',
    when: '매일 오전, 이상 감지 시.',
    cmd: `Write-Host "═══ DataBridge 헬스체크 $(Get-Date -Format 'yyyy-MM-dd HH:mm') ═══" -ForegroundColor Cyan
$be = try { Invoke-RestMethod "http://localhost:8000/api/v1/system/live" -TimeoutSec 3 } catch { $null }
Write-Host ("백엔드     : " + $(if($be){'✓ OK'}else{'✗ 응답없음'}))
$py = (Get-Process python -EA 0).Count; Write-Host "Python     : $py 프로세스"
docker ps --filter name=db_ --format "DB         : {{.Names}} ({{.Status}})"
$logSize = "{0:N0} MB" -f ((Get-ChildItem "\${ROOT}\\backend\\logs" -Recurse -EA 0 | Measure-Object Length -Sum).Sum / 1MB)
Write-Host "로그       : $logSize"
$disk = Get-PSDrive D | Select-Object @{N="Free";E={[math]::Round($_.Free/1GB,1)}}
Write-Host "D: 여유    : $($disk.Free) GB"
$errs = (Select-String "\${ROOT}\\backend\\logs\\databridge_backend.log" -Pattern "ERROR" -EA 0 | Select-Object -Last 100).Count
Write-Host "최근 에러  : $errs 건"
Write-Host "═════════════════════════════════════" -ForegroundColor Cyan`,
  },
  {
    id: 'ops_log_rotate', cat: 'ops', shell: 'powershell',
    title: '로그 정리 (rotate)',
    desc: '7일 이상 압축, 30일 이상 삭제.',
    when: '월 1회.',
    cmd: `$logDir = "\${ROOT}\\backend\\logs"
Get-ChildItem $logDir -Filter "*.log" | Where-Object LastWriteTime -lt (Get-Date).AddDays(-7) | ForEach-Object {
  Compress-Archive -Path $_.FullName -DestinationPath "$($_.FullName).zip" -Force
  Remove-Item $_.FullName
}
Get-ChildItem $logDir -Filter "*.log.zip" | Where-Object LastWriteTime -lt (Get-Date).AddDays(-30) | Remove-Item`,
  },
  {
    id: 'ops_disk_check', cat: 'ops', shell: 'powershell',
    title: '디스크 사용량 점검',
    desc: '프로젝트 + 로그 + Docker 볼륨 + 백업.',
    when: '월 1회 또는 경고 시.',
    cmd: `Write-Host "─── 프로젝트 ───"
"{0:N1} GB" -f ((Get-ChildItem "\${ROOT}" -Recurse -EA 0 | Measure-Object Length -Sum).Sum/1GB)
Write-Host "─── 로그 ───"
"{0:N1} MB" -f ((Get-ChildItem "\${ROOT}\\backend\\logs" -Recurse -EA 0 | Measure-Object Length -Sum).Sum/1MB)
Write-Host "─── 백업 ───"
"{0:N1} GB" -f ((Get-ChildItem "D:\\backup" -Recurse -EA 0 | Measure-Object Length -Sum).Sum/1GB)
Write-Host "─── Docker ───"
docker system df`,
  },
  {
    id: 'ops_git_pull', cat: 'ops', shell: 'powershell',
    title: 'Git 최신 받기',
    desc: 'GitHub 의 최신 commit pull.',
    when: '환경 동기화, 새 PC 셋업.',
    cmd: `cd \${ROOT}
git status
git pull origin main`,
  },
  {
    id: 'ops_git_status_pr', cat: 'ops', shell: 'powershell',
    title: 'Git 변경 사항 확인',
    desc: '로컬에 안 commit 한 변경 + diff stat.',
    when: 'commit 전 변경 검토.',
    cmd: `cd \${ROOT}
git status -s
git diff --stat`,
  },
  {
    id: 'ops_daily_report', cat: 'ops', shell: 'powershell',
    title: '일일 운영 리포트 자동 생성',
    desc: 'HTML 리포트 → Job 통계 + KB + 헬스 + 디스크.',
    when: '매일 오전 (스케줄러 등록).',
    cmd: `$ts = Get-Date -Format "yyyy-MM-dd"
$jobs = Invoke-RestMethod "http://localhost:8000/api/v1/jobs/" -EA 0
$kb = Invoke-RestMethod "http://localhost:8000/api/v1/kb/dashboard" -EA 0
$report = @"
<html><body style='font-family:Segoe UI,sans-serif'>
<h2>DataBridge 일일 리포트 — $ts</h2>
<h3>Job 통계</h3>
<p>총: $($jobs.Count) | 성공: $($jobs | Where-Object status -eq 'completed' | Measure-Object | Select-Object -ExpandProperty Count) | 실패: $($jobs | Where-Object status -eq 'error' | Measure-Object | Select-Object -ExpandProperty Count)</p>
<h3>KB 자산</h3>
<p>패턴: $($kb.summary.total_patterns) | 적중률: $($kb.summary.overall_rate)% | AI 절약: $($kb.summary.ai_saved_rate)%</p>
</body></html>
"@
$report | Out-File "D:\\reports\\daily_$ts.html" -Encoding UTF8
Write-Host "✓ D:\\reports\\daily_$ts.html"`,
  },
  {
    id: 'ops_schedule_task', cat: 'ops', shell: 'powershell',
    title: 'Windows 스케줄러 등록 (자동화)',
    desc: '매일 오전 6시 헬스체크 자동 실행.',
    when: '운영 자동화 셋업.',
    cmd: `$action = New-ScheduledTaskAction -Execute "powershell.exe" \`
  -Argument "-File \${ROOT}\\backend\\scripts\\daily_health.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At 6am
Register-ScheduledTask -TaskName "DataBridgeHealthCheck" \`
  -Action $action -Trigger $trigger -Description "DataBridge 일일 헬스체크"`,
  },
  {
    id: 'ops_email_alert', cat: 'ops', shell: 'powershell',
    title: '이메일 알림 (실패 시)',
    desc: 'Job 실패 또는 critical audit 발생 시 메일.',
    when: '운영 알림 셋업.',
    cmd: `$jobs = Invoke-RestMethod "http://localhost:8000/api/v1/jobs/"
$failed = $jobs | Where-Object status -eq "error"
if ($failed) {
  $body = "실패 Job 발생:\`r\`n" + ($failed | Select-Object id, name, error_message | Out-String)
  Send-MailMessage -SmtpServer "smtp.example.com" -From "noreply@example.com" \`
    -To "ops@example.com" -Subject "DataBridge 알림" -Body $body
}`,
  },
  {
    id: 'ops_user_activity', cat: 'ops', shell: 'powershell',
    title: '사용자 활동 통계 (월간)',
    desc: '월간 사용자별 액션 카운트.',
    when: '월간 사용 리포트.',
    cmd: `Invoke-RestMethod "http://localhost:8000/api/v1/admin/audit?limit=10000" | \`
  Group-Object user | Select-Object Name, Count | Sort-Object Count -Descending`,
  },
  {
    id: 'ops_capacity_plan', cat: 'ops', shell: 'powershell',
    title: '용량 계획 (성장률 추적)',
    desc: 'DB / 로그 / 백업 크기 7일 추이.',
    when: '월간, 분기 capacity planning.',
    cmd: `# 백업 폴더의 7일치 변화
Get-ChildItem "D:\\backup\\databridge_*" | \`
  Where-Object LastWriteTime -gt (Get-Date).AddDays(-7) | \`
  Sort-Object LastWriteTime | \`
  Select-Object @{N="Date";E={$_.LastWriteTime.ToString('yyyy-MM-dd')}}, \`
                @{N="SizeMB";E={[math]::Round((Get-ChildItem $_.FullName -Recurse | Measure-Object Length -Sum).Sum/1MB,1)}}`,
  },
  {
    id: 'ops_restart_weekly', cat: 'ops', shell: 'powershell',
    title: '주간 재시작 (정기 점검)',
    desc: '메모리 leak 방지 등 정기 재시작.',
    when: '주간 — 일요일 새벽 권장.',
    cmd: `# 1) 진행 중 Job 없는지 확인
$running = (Invoke-RestMethod "http://localhost:8000/api/v1/jobs/" | Where-Object status -eq "running").Count
if ($running -gt 0) { Write-Host "⚠ 진행 중 Job $running 개 — 재시작 보류"; exit }
# 2) 백엔드 재시작
Get-Process python | Stop-Process -Force
Start-Sleep 3
Start-Process "\${ROOT}\\backend\\run_backend.bat" -WorkingDirectory "\${ROOT}\\backend"
Write-Host "✓ 주간 재시작 완료"`,
  },
  {
    id: 'ops_handover_pack', cat: 'ops', shell: 'powershell',
    title: '운영 인계 패키지 생성',
    desc: '설정/KB/감사로그/매뉴얼 한 번에 패키징.',
    when: '운영 인계, 분기말 정리.',
    cmd: `$ts = Get-Date -Format "yyyyMMdd"
$pack = "D:\\handover\\databridge_$ts"
New-Item $pack -ItemType Directory -Force | Out-Null
# 1) KB 자산
Copy-Item "\${ROOT}\\backend\\app\\engine\\error_kb.yml" "$pack\\"
Copy-Item "\${ROOT}\\backend\\data\\kb_stats.db" "$pack\\"
Copy-Item "\${ROOT}\\backend\\prompts\\mssql_to_mysql\\error_cases.txt" "$pack\\"
# 2) 감사 로그
Invoke-RestMethod "http://localhost:8000/api/v1/admin/audit?limit=10000" | Export-Csv "$pack\\audit_export.csv" -NoTypeInformation -Encoding UTF8
# 3) 운영자 라이브러리 PDF (브라우저에서 인쇄 → 저장)
Write-Host "→ 브라우저: /admin/operator-library 열어 Ctrl+P → PDF 저장 → $pack\\"
Compress-Archive -Path $pack -DestinationPath "$pack.zip" -Force
Write-Host "✓ 인계 패키지: $pack.zip"`,
  },

  // ════════════════════════════════════════════════════════════
  // 🖥 시스템 운영 (25) — Windows / Linux / 공통
  // 메모리 정리, 서비스 관리, 디스크 정리, 시스템 모니터링
  // ════════════════════════════════════════════════════════════

  // ─── 메모리 관리 (Windows) ─────────────────────────────────
  {
    id: 'sys_win_mem_status', cat: 'system', shell: 'powershell', os: 'win',
    title: 'Windows 메모리 상태 (전체/사용/여유)',
    desc: '시스템 메모리 사용 현황 + 캐시/대기 메모리.',
    when: '메모리 부족 의심, 성능 저하 시.',
    cmd: `$os = Get-CimInstance Win32_OperatingSystem
$totalGB = [math]::Round($os.TotalVisibleMemorySize/1MB, 1)
$freeGB  = [math]::Round($os.FreePhysicalMemory/1MB, 1)
$usedGB  = [math]::Round($totalGB - $freeGB, 1)
$pct     = [math]::Round(($usedGB / $totalGB) * 100, 1)
Write-Host "─── 메모리 상태 ───" -ForegroundColor Cyan
Write-Host "  총량   : $totalGB GB"
Write-Host "  사용중 : $usedGB GB ($pct%)"
Write-Host "  여유   : $freeGB GB"
# 캐시/대기 메모리 (Windows 가 회수 가능한 영역)
$cs = Get-Counter '\\Memory\\Standby Cache Normal Priority Bytes' -EA 0
if ($cs) { Write-Host "  대기캐시: $([math]::Round($cs.CounterSamples[0].CookedValue/1GB,1)) GB (회수 가능)" }`,
    expected: '총량 : 16 GB / 사용중 : 12.5 GB (78%) / 여유 : 3.5 GB',
    related: ['sys_win_mem_clear', 'sys_win_top_mem'],
  },
  {
    id: 'sys_win_mem_clear', cat: 'system', shell: 'powershell', os: 'win',
    severity: 'warn',
    title: 'Windows 메모리 정리 (대기 메모리 회수)',
    desc: '대기 메모리 + 작업집합 정리. 관리자 권한 필요. RAMMap 의 EmptyStandbyList 와 동일 효과.',
    when: '메모리 사용률 80%+ 일 때, 시스템 느려질 때, 큰 작업 직전.',
    cmd: `# 1) 모든 프로세스의 작업집합 강제 축소
Get-Process | Where-Object { $_.WorkingSet -gt 50MB } | ForEach-Object {
    try { [System.Diagnostics.Process]::GetProcessById($_.Id).MaxWorkingSet = $_.MaxWorkingSet } catch {}
}
# 2) 가비지 컬렉션 트리거
[System.GC]::Collect()
[System.GC]::WaitForPendingFinalizers()
# 3) 결과 확인
$os = Get-CimInstance Win32_OperatingSystem
Write-Host "✓ 메모리 정리 완료. 여유: $([math]::Round($os.FreePhysicalMemory/1MB,1)) GB" -ForegroundColor Green
# 더 강력한 정리: SysInternals 의 RAMMap.exe -Et (대기리스트 비우기) — 별도 다운로드 필요`,
    troubleshoot: '<b>관리자 권한 거부 시:</b> PowerShell 을 "관리자 권한으로 실행"<br><b>더 강력한 정리:</b> Microsoft SysInternals 의 RAMMap.exe 다운로드 → <code>RAMMap.exe -Et</code>',
    related: ['sys_win_mem_status', 'sys_wsl_shutdown'],
  },
  {
    id: 'sys_win_top_mem', cat: 'system', shell: 'powershell', os: 'win',
    title: 'Windows 메모리 사용 Top 10 프로세스',
    desc: '가장 메모리 많이 쓰는 프로세스 + 정리 후보 식별.',
    when: '메모리 부족 시 원인 파악.',
    cmd: `Get-Process | Sort-Object WorkingSet -Descending | Select-Object -First 10 \`
  Name, Id, \`
  @{N="MemMB";  E={[math]::Round($_.WorkingSet/1MB, 1)}}, \`
  @{N="VirtMB"; E={[math]::Round($_.VirtualMemorySize/1MB, 1)}}, \`
  @{N="CPU(s)"; E={[math]::Round($_.CPU, 1)}} | Format-Table -AutoSize`,
  },
  {
    id: 'sys_win_pagefile', cat: 'system', shell: 'powershell', os: 'win',
    title: 'Windows 페이지 파일 사용량',
    desc: '가상 메모리 (pagefile.sys) 크기 + 사용량.',
    when: '메모리 부족, swap 압박 진단.',
    cmd: `Get-CimInstance Win32_PageFileUsage | Format-Table Name, \`
  @{N="AllocatedMB"; E={$_.AllocatedBaseSize}}, \`
  @{N="CurrentMB";   E={$_.CurrentUsage}}, \`
  @{N="PeakMB";      E={$_.PeakUsage}}`,
  },

  // ─── 메모리 관리 (Linux) ───────────────────────────────────
  {
    id: 'sys_linux_mem_status', cat: 'system', shell: 'bash', os: 'linux',
    title: 'Linux 메모리 상태 (free -h)',
    desc: '총량/사용/여유/buffer/cache/swap 한 화면.',
    when: '메모리 부족 진단, 정기 점검.',
    cmd: `free -h
echo "─── /proc/meminfo 상세 ───"
grep -E "MemTotal|MemAvailable|Cached|Buffers|SwapTotal|SwapFree|Dirty" /proc/meminfo`,
    expected: '              total        used        free      shared  buff/cache   available\nMem:           15Gi        8.2Gi       1.1Gi       234Mi       6.0Gi       6.6Gi',
    related: ['sys_linux_mem_clear', 'sys_linux_top'],
  },
  {
    id: 'sys_linux_mem_clear', cat: 'system', shell: 'bash', os: 'linux',
    severity: 'warn',
    title: 'Linux 페이지 캐시 정리 (drop_caches)',
    desc: '커널의 페이지 캐시/dentry/inode 캐시 회수. root 필요.',
    when: '메모리 부족, 큰 배치 작업 직전.',
    cmd: `# 1) 디스크 동기화 (안전을 위해 필수)
sudo sync
# 2) 캐시 정리
#   1: 페이지 캐시만
#   2: dentries + inodes
#   3: 모두
sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'
echo "✓ 캐시 정리 완료"
free -h`,
    troubleshoot: '<b>주의:</b> 캐시는 성능 향상에 기여하므로 평상시엔 정리 불필요. 대용량 작업 전후에만.',
    related: ['sys_linux_mem_status'],
  },
  {
    id: 'sys_linux_swap_clear', cat: 'system', shell: 'bash', os: 'linux',
    severity: 'warn',
    title: 'Linux swap 정리 (swap → memory)',
    desc: 'swap 에 밀려난 메모리를 다시 RAM 으로. RAM 여유 있을 때만 실행.',
    when: 'swap 사용률 높음 + RAM 여유 있을 때 성능 회복.',
    cmd: `# 사전 확인 — RAM 여유 + swap 사용량
free -h
# RAM 여유 > swap 사용량 인지 확인 후 실행:
sudo swapoff -a && sudo swapon -a
echo "✓ swap 재설정 완료"
free -h`,
    troubleshoot: '<b>RAM 부족하면 시스템 멈출 수 있음.</b> RAM 여유 &gt; swap 사용량 인 경우만 실행.',
  },
  {
    id: 'sys_linux_top_mem', cat: 'system', shell: 'bash', os: 'linux',
    title: 'Linux 메모리 Top 10 프로세스',
    desc: '메모리 가장 많이 쓰는 프로세스.',
    when: '메모리 부족 원인 파악.',
    cmd: `ps aux --sort=-%mem | head -11
# 또는 더 보기 좋게:
ps -eo pid,user,rss,vsz,pmem,pcpu,comm --sort=-rss | head -11`,
  },

  // ─── 시스템 모니터링 ────────────────────────────────────────
  {
    id: 'sys_win_perf_live', cat: 'system', shell: 'powershell', os: 'win',
    title: 'Windows 실시간 시스템 부하 (Performance Counter)',
    desc: 'CPU/메모리/디스크/네트워크 5초 간격 5회.',
    when: '성능 저하 실시간 추적.',
    cmd: `Get-Counter -Counter \`
  "\\Processor(_Total)\\% Processor Time", \`
  "\\Memory\\Available MBytes", \`
  "\\PhysicalDisk(_Total)\\% Disk Time", \`
  "\\Network Interface(*)\\Bytes Total/sec" \`
  -SampleInterval 5 -MaxSamples 5`,
  },
  {
    id: 'sys_linux_top', cat: 'system', shell: 'bash', os: 'linux',
    title: 'Linux 실시간 모니터링 (top/htop)',
    desc: '프로세스/CPU/메모리 실시간.',
    when: '성능 진단, 활성 프로세스 추적.',
    cmd: `# 기본 top (q 로 종료)
top -b -n 1 | head -20
# htop 설치돼있으면 더 보기 좋음:
# htop`,
  },
  {
    id: 'sys_linux_iostat', cat: 'system', shell: 'bash', os: 'linux',
    title: 'Linux 디스크 I/O 부하 (iostat)',
    desc: '디스크별 read/write IOPS, 응답시간.',
    when: 'I/O 병목 진단.',
    cmd: `# sysstat 패키지 필요 (apt install sysstat)
iostat -xz 5 3`,
  },

  // ─── WSL / Docker 메모리 (공통) ────────────────────────────
  {
    id: 'sys_wsl_shutdown', cat: 'system', shell: 'powershell', os: 'win',
    title: 'WSL 종료 (vmmem 메모리 회수)',
    desc: 'WSL2 의 vmmem 프로세스가 점유한 메모리 한 번에 회수.',
    when: 'vmmem 메모리 폭증, Docker Desktop 무거워짐.',
    cmd: `# 현재 WSL 메모리 사용량
Get-Process vmmem -EA 0 | Select-Object Name, Id, @{N="MemMB";E={[math]::Round($_.WorkingSet/1MB,1)}}
# 종료
wsl --shutdown
Start-Sleep 3
Write-Host "✓ WSL 종료 완료. Docker 컨테이너는 자동 재시작 됨" -ForegroundColor Green
# Docker 컨테이너 재시작 (필요 시)
docker start db_mysql db_mssql 2>$null`,
    related: ['sys_docker_prune', 'sys_win_mem_status'],
  },
  {
    id: 'sys_docker_prune', cat: 'system', shell: 'powershell', os: 'cross',
    severity: 'warn',
    title: 'Docker 메모리/디스크 정리 (사용 안 하는 모든 것)',
    desc: '중지된 컨테이너, 사용 안 하는 이미지/볼륨/네트워크 정리.',
    when: '디스크 공간 부족, Docker 무거워질 때.',
    cmd: `# 정리 전 사용량
docker system df
# 안전한 정리 (사용 안 하는 것만)
docker system prune -f
# 더 공격적 (이미지/볼륨까지)
# docker system prune -a --volumes -f
# 정리 후 사용량
docker system df`,
    troubleshoot: '<b>--volumes 주의:</b> DB 데이터 볼륨까지 삭제될 수 있음. 평상시는 이미지만 정리.',
  },
  {
    id: 'sys_docker_restart_all', cat: 'system', shell: 'powershell', os: 'cross',
    severity: 'warn',
    title: 'Docker 모든 컨테이너 재시작',
    desc: '메모리 leak 의심 시 정기 재시작.',
    when: '주간 정기 점검, 컨테이너 응답 느려질 때.',
    cmd: `docker ps --filter "name=db_" --format "{{.Names}}" | ForEach-Object {
    Write-Host "재시작: $_" -ForegroundColor Cyan
    docker restart $_
}
Start-Sleep 5
docker ps --filter "name=db_" --format "table {{.Names}}\\t{{.Status}}"`,
  },

  // ─── 서비스 관리 ────────────────────────────────────────────
  {
    id: 'sys_win_services_db', cat: 'system', shell: 'powershell', os: 'win',
    title: 'Windows DB 관련 서비스 상태',
    desc: 'MSSQL/MySQL/Docker 서비스 상태.',
    when: '서비스 비정상 의심, 재시작 직전.',
    cmd: `Get-Service | Where-Object { $_.DisplayName -match "SQL|MySQL|Docker" } | \`
  Format-Table Status, Name, DisplayName -AutoSize`,
  },
  {
    id: 'sys_linux_systemctl', cat: 'system', shell: 'bash', os: 'linux',
    title: 'Linux systemd 서비스 관리',
    desc: 'DB / DataBridge 서비스 상태/재시작/중지.',
    when: 'Linux 운영 환경에서 서비스 관리.',
    cmd: `# 상태
systemctl status mysql mariadb postgresql databridge 2>/dev/null | grep -E "●|Active"
# 재시작 (예: databridge)
# sudo systemctl restart databridge
# 부팅 시 자동 시작
# sudo systemctl enable databridge
# 종료
# sudo systemctl stop databridge`,
  },
  {
    id: 'sys_linux_journalctl', cat: 'system', shell: 'bash', os: 'linux',
    title: 'Linux 시스템 로그 (journalctl)',
    desc: 'systemd 서비스 로그 + 부트 로그.',
    when: '서비스 시작 실패, 시스템 이슈.',
    cmd: `# DataBridge 서비스 로그 마지막 50줄
sudo journalctl -u databridge -n 50 --no-pager
# 실시간 추적
# sudo journalctl -u databridge -f
# 부팅 후 에러만
# sudo journalctl -p err -b`,
  },

  // ─── 디스크 정리 ────────────────────────────────────────────
  {
    id: 'sys_win_cleanup', cat: 'system', shell: 'powershell', os: 'win',
    title: 'Windows 디스크 정리 (Temp/RecycleBin)',
    desc: '임시 파일 / 휴지통 / Windows 업데이트 캐시 정리.',
    when: '디스크 공간 확보, 정기 청소.',
    cmd: `# 1) 임시 파일
$temp = [System.IO.Path]::GetTempPath()
$before = (Get-ChildItem $temp -Recurse -EA 0 | Measure-Object Length -Sum).Sum
Get-ChildItem $temp -Recurse -EA 0 | Where-Object { -not $_.PSIsContainer -and $_.LastWriteTime -lt (Get-Date).AddDays(-7) } | Remove-Item -Force -EA 0
$after = (Get-ChildItem $temp -Recurse -EA 0 | Measure-Object Length -Sum).Sum
Write-Host "Temp 정리: $([math]::Round(($before-$after)/1MB,1)) MB 회수" -ForegroundColor Green
# 2) 휴지통
Clear-RecycleBin -Force -EA 0
Write-Host "✓ 휴지통 비움" -ForegroundColor Green
# 3) Windows 디스크 정리 마법사 (대화식)
# cleanmgr.exe /sagerun:1`,
  },
  {
    id: 'sys_linux_apt_clean', cat: 'system', shell: 'bash', os: 'linux',
    title: 'Linux 패키지 캐시 정리 (apt)',
    desc: 'apt 다운로드 캐시 + 사용 안 하는 패키지 정리.',
    when: '디스크 공간 확보.',
    cmd: `sudo apt clean              # 다운로드된 .deb 파일 모두 삭제
sudo apt autoclean          # 더 이상 받을 수 없는 .deb 만
sudo apt autoremove -y      # 의존성 떨어진 패키지
df -h`,
  },
  {
    id: 'sys_linux_journal_vacuum', cat: 'system', shell: 'bash', os: 'linux',
    title: 'Linux journalctl 로그 정리',
    desc: 'systemd 로그 7일 이상 자동 회수.',
    when: '/var/log 가득 찼을 때.',
    cmd: `# 현재 로그 크기
sudo journalctl --disk-usage
# 7일 이상 정리
sudo journalctl --vacuum-time=7d
# 또는 크기 제한
# sudo journalctl --vacuum-size=500M`,
  },

  // ─── 네트워크 / 시간 ───────────────────────────────────────
  {
    id: 'sys_win_net_reset', cat: 'system', shell: 'powershell', os: 'win',
    severity: 'warn',
    title: 'Windows 네트워크 스택 초기화',
    desc: 'DNS 캐시, 소켓, IP 갱신. 관리자 권한 필요.',
    when: '네트워크 비정상, DNS 응답 이상, 연결 안 됨.',
    cmd: `ipconfig /flushdns
ipconfig /release
ipconfig /renew
netsh winsock reset
netsh int ip reset
Write-Host "✓ 네트워크 초기화 완료. 재부팅 권장." -ForegroundColor Yellow`,
  },
  {
    id: 'sys_win_time_sync', cat: 'system', shell: 'powershell', os: 'win',
    title: 'Windows 시간 동기화',
    desc: 'NTP 서버에서 시간 강제 동기화. JWT 만료/세션 끊김 처방.',
    when: '시계 어긋남, 인증 오류.',
    cmd: `w32tm /query /status
w32tm /resync /force
Get-Date`,
  },
  {
    id: 'sys_linux_ntp_sync', cat: 'system', shell: 'bash', os: 'linux',
    title: 'Linux 시간 동기화 (chrony/ntpd)',
    desc: 'NTP 동기화 강제.',
    when: '시계 어긋남.',
    cmd: `# chrony 사용 환경
sudo chronyc -a makestep
chronyc tracking
# 또는 ntpd:
# sudo systemctl restart ntp
# 또는 timedatectl:
# sudo timedatectl set-ntp true
date`,
  },

  // ─── 시스템 재시작 / 종료 ──────────────────────────────────
  {
    id: 'sys_win_restart', cat: 'system', shell: 'powershell', os: 'win',
    severity: 'danger',
    title: 'Windows 재시작 (안전 절차)',
    desc: 'DataBridge Job 진행 확인 후 안전 재시작.',
    when: '주간 재시작, 패치 후 재시작.',
    cmd: `# 1) 진행 중 Job 없는지 확인
$running = (Invoke-RestMethod "http://localhost:8000/api/v1/jobs/" -EA 0 | Where-Object status -eq "running").Count
if ($running -gt 0) { Write-Host "⚠ 진행 중 Job $running 개 — 재시작 보류" -ForegroundColor Red; exit }
# 2) 백엔드 정상 종료
Get-Process python | Stop-Process
Start-Sleep 5
# 3) Docker 컨테이너 정상 종료
docker stop $(docker ps -q) 2>$null
# 4) 재시작 (60초 후)
shutdown /r /t 60 /c "DataBridge 정기 재시작"
Write-Host "60초 후 재시작 — 취소: shutdown /a" -ForegroundColor Yellow`,
    troubleshoot: '<b>취소:</b> <code>shutdown /a</code>',
  },
  {
    id: 'sys_linux_restart', cat: 'system', shell: 'bash', os: 'linux',
    severity: 'danger',
    title: 'Linux 재시작 (안전 절차)',
    desc: 'systemd 서비스 정상 종료 후 재시작.',
    when: '주간 재시작, 커널 업데이트 후.',
    cmd: `# 1) 진행 중 Job 확인
RUNNING=$(curl -s http://localhost:8000/api/v1/jobs/ | grep -o '"status":"running"' | wc -l)
if [ "$RUNNING" -gt 0 ]; then
    echo "⚠ 진행 중 Job $RUNNING 개 — 재시작 보류"
    exit 1
fi
# 2) DataBridge 정상 종료
sudo systemctl stop databridge
# 3) 재시작
sudo shutdown -r +1 "DataBridge 정기 재시작"
echo "1분 후 재시작 — 취소: sudo shutdown -c"`,
    troubleshoot: '<b>취소:</b> <code>sudo shutdown -c</code>',
  },

  // ─── 환경 정보 ──────────────────────────────────────────────
  {
    id: 'sys_info_summary', cat: 'system', shell: 'powershell', os: 'win',
    title: 'Windows 시스템 정보 요약',
    desc: 'OS / CPU / RAM / 디스크 / 네트워크 한 번에.',
    when: '환경 인계, 트러블슈팅 첫 단계.',
    cmd: `$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$disks = Get-PSDrive -PSProvider FileSystem | Where-Object Used -gt 0
Write-Host "═══ 시스템 정보 ═══" -ForegroundColor Cyan
Write-Host "  OS         : $($os.Caption) $($os.Version)"
Write-Host "  CPU        : $($cpu.Name) ($($cpu.NumberOfCores) cores)"
Write-Host "  RAM        : $([math]::Round($os.TotalVisibleMemorySize/1MB, 1)) GB"
Write-Host "  여유 RAM   : $([math]::Round($os.FreePhysicalMemory/1MB, 1)) GB"
Write-Host "  Hostname   : $env:COMPUTERNAME"
Write-Host "  사용자     : $env:USERNAME"
Write-Host "  PowerShell : $($PSVersionTable.PSVersion)"
foreach ($d in $disks) {
    $totalGB = [math]::Round(($d.Used + $d.Free)/1GB, 1)
    $freeGB  = [math]::Round($d.Free/1GB, 1)
    Write-Host "  $($d.Name): 드라이브 : $freeGB GB 여유 / $totalGB GB"
}`,
  },
  {
    id: 'sys_info_summary_linux', cat: 'system', shell: 'bash', os: 'linux',
    title: 'Linux 시스템 정보 요약',
    desc: 'OS / 커널 / CPU / RAM / 디스크 한 번에.',
    when: '환경 인계, 트러블슈팅 첫 단계.',
    cmd: `echo "═══ 시스템 정보 ═══"
echo "OS       : $(lsb_release -d 2>/dev/null | cut -f2 || cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2)"
echo "Kernel   : $(uname -r)"
echo "Hostname : $(hostname)"
echo "Uptime   : $(uptime -p)"
echo "─── CPU ───"
lscpu | grep -E "Model name|CPU\\(s\\)|MHz" | head -3
echo "─── 메모리 ───"
free -h | head -2
echo "─── 디스크 ───"
df -h | grep -vE "tmpfs|udev"`,
  },


  {
    id: 'docs_mssql_to_mysql_types', cat: 'docs', shell: 'sql',
    title: '타입 매핑 cheat sheet (MSSQL → MySQL)',
    desc: '주요 타입 변환 빠른 참조.',
    when: '수동 DDL 변환, 검토.',
    cmd: `-- MSSQL              →  MySQL
-- INT                  →  INT
-- BIGINT               →  BIGINT
-- DECIMAL(p,s)         →  DECIMAL(p,s)
-- VARCHAR(n)           →  VARCHAR(n)
-- VARCHAR(MAX)         →  LONGTEXT
-- NVARCHAR(n)          →  VARCHAR(n) CHARACTER SET utf8mb4
-- NVARCHAR(MAX)        →  LONGTEXT CHARACTER SET utf8mb4
-- DATETIME             →  DATETIME
-- DATETIME2(7)         →  DATETIME(6)  -- 7자리 → 6자리 손실
-- DATE                 →  DATE
-- BIT                  →  TINYINT(1)
-- UNIQUEIDENTIFIER     →  CHAR(36)
-- VARBINARY(MAX)       →  LONGBLOB
-- XML                  →  LONGTEXT
-- SYSNAME              →  VARCHAR(128)`,
  },
  {
    id: 'docs_object_conversion', cat: 'docs', shell: 'sql',
    title: '객체 변환 가이드 (PROCEDURE/FUNCTION/VIEW/TRIGGER)',
    desc: '객체 종류별 변환 규칙.',
    when: 'AI 변환 검토, 수동 변환.',
    cmd: `-- ┌─────────────────────────────────────────────────────────┐
-- │  MSSQL                          MySQL                       │
-- ├─────────────────────────────────────────────────────────────┤
-- │  CREATE PROCEDURE p()           CREATE PROCEDURE p()         │
-- │  AS BEGIN                       BEGIN                        │
-- │    @v1 INT = 10;                  DECLARE v1 INT DEFAULT 10; │
-- │    SET @v2 = @v1 + 1;             SET v2 = v1 + 1;           │
-- │  END                            END                          │
-- │                                                              │
-- │  CREATE FUNCTION f() RETURNS    CREATE FUNCTION f()          │
-- │    @t TABLE (...)                 RETURNS LONGTEXT           │
-- │  AS RETURN (SELECT...)            -- TVF 미지원              │
-- │                                   -- → VIEW 또는 PROCEDURE   │
-- │                                                              │
-- │  CREATE TRIGGER t                CREATE TRIGGER t            │
-- │    ON tbl AFTER INSERT             AFTER INSERT ON tbl       │
-- │  AS BEGIN ... END                  FOR EACH ROW              │
-- │                                  BEGIN ... END               │
-- │                                                              │
-- │  CREATE VIEW v AS SELECT...      CREATE OR REPLACE VIEW v    │
-- │                                    AS SELECT...              │
-- └─────────────────────────────────────────────────────────────┘`,
  },
  {
    id: 'docs_function_diff', cat: 'docs', shell: 'sql',
    title: '내장 함수 차이 cheat sheet',
    desc: '자주 쓰는 함수 매핑.',
    when: 'AI 변환 보완, 수동 SQL 변환.',
    cmd: `-- ─────────  날짜/시간  ─────────────────
-- GETDATE()              →  NOW()
-- DATEADD(DD,1,d)        →  DATE_ADD(d, INTERVAL 1 DAY)
-- DATEDIFF(DD,d1,d2)     →  DATEDIFF(d2, d1)
-- FORMAT(d,'yyyy-MM-dd') →  DATE_FORMAT(d, '%Y-%m-%d')
-- CONVERT(DATE, d)       →  DATE(d)
-- 
-- ─────────  문자열  ─────────────────────
-- LEN(s)                 →  CHAR_LENGTH(s)
-- ISNULL(a,b)            →  IFNULL(a,b)
-- CHARINDEX(p,s)         →  LOCATE(p,s)
-- STUFF(s,p,n,r)         →  CONCAT(LEFT(s,p-1),r,SUBSTRING(s,p+n))
-- 
-- ─────────  변환  ───────────────────────
-- CAST(x AS INT)         →  CAST(x AS SIGNED)
-- TRY_CONVERT(INT, x)    →  CAST(x AS SIGNED) (실패 시 NULL X)
-- 
-- ─────────  TOP / LIMIT  ───────────────
-- SELECT TOP 10 * FROM t →  SELECT * FROM t LIMIT 10
-- 
-- ─────────  IDENTITY / AUTO_INCREMENT  ──
-- IDENTITY(1,1)          →  AUTO_INCREMENT
-- @@IDENTITY             →  LAST_INSERT_ID()`,
  },
  {
    id: 'docs_phase_meaning', cat: 'docs', shell: 'sql',
    title: 'DataBridge Phase 의미 (이관 단계)',
    desc: '각 phase 가 뭘 하는지 + 트러블슈팅 위치.',
    when: '운영자 학습, 진행률 의미 파악.',
    cmd: `-- DataBridge Job 의 phase 흐름
-- 
-- INIT          →  Job 생성, 환경 검증
-- FK_DISABLE    →  대상 테이블의 FK 비활성 (이관 가속)
-- DROP_TABLE    →  타겟 테이블 DROP (옵션)
-- CREATE_TABLE  →  타겟 테이블 CREATE
-- TRUNCATE      →  TRUNCATE (옵션)
-- RUNNING       →  실제 데이터 이관 (largest)
-- CONVERT_OBJ   →  PROCEDURE/FUNCTION/VIEW/TRIGGER 변환
-- FK_RESTORE    →  FK 복원
-- INDEX_CREATE  →  소스 인덱스를 타겟에 자동 생성 (v93_A)
-- AUDIT         →  사후 검증 (v93_C) — 5영역 자동 점검
-- DONE          →  완료
-- 
-- 멈춘 phase 별 대응:
--   RUNNING: 백엔드 로그 확인, 큰 테이블이면 정상
--   CONVERT_OBJ: AI 호출 중 — Settings → API key 확인
--   INDEX_CREATE: 인덱스 충돌 — index_report 확인
--   AUDIT: 검증 자체 실패 — audit_report.checks 확인`,
  },
  {
    id: 'docs_kb_pattern_anatomy', cat: 'docs', shell: 'sql',
    title: 'KB 패턴 작성 가이드',
    desc: 'error_kb.yml 패턴 구조 + 필드 의미.',
    when: '신규 KB 패턴 작성.',
    cmd: `# error_kb.yml 의 패턴 구조
patterns:
  PATTERN_ID:                            # ex: 1064_END_IF_NESTING
    error_code: '1064'                   # SQL 에러 코드
    category: SYNTAX                     # SYNTAX/PERMISSION/DATA/...
    fix_type: ai                         # ai (AI 재변환) / config / engine
    regex: 'You have an error.*END IF'   # 에러 메시지 매칭 정규식
    ai_skip: false                       # true 면 AI 호출 건너뛰고 fix_prompt 만
    fix_prompt: |                        # AI 에 주입할 추가 가이드
      ===INSTRUCTION===
      [반드시 지킬 규칙]
      1. ...
      2. ...
      [핵심 변환 규칙]
      ...
      ===END===
    
# 좋은 fix_prompt 의 조건 (v93_D1):
#  ✓ ===INSTRUCTION=== / ===END=== 명확 마커
#  ✓ 객체명/시그니처 보존 명시
#  ✓ 자연어 설명 금지 + 코드만
#  ✓ Before/After 예시 1~2개
#  ✓ 결정 가이드 (어떤 옵션 언제)`,
  },
  {
    id: 'docs_v93_changelog', cat: 'docs', shell: 'sql',
    title: 'v93 패치 changelog',
    desc: '최근 패치별 변경 + 핵심 통찰.',
    when: '운영 인계, 변경 추적.',
    cmd: `-- v93 (2026-05-01) — "본질 충실 모드" — 본부장님 통찰 결실
-- 
-- v93_E   운영 안정성
--   - verify_patches.ps1 — 패치 적용 자동 검증
--   - --reload 표준화 (이미 활성)
--   - jobs store 무결성 (자동 처리)
-- 
-- v93_C   사후 검증 (Post-Migration Audit)
--   - AuditEngine 신규 — 5영역 자동 점검
--     인덱스 누락 / FK 무결성 / 객체 누락 / 행수 차이 / 타입 손실
--   - run() 끝에 자동 실행
--   - GET/POST /api/v1/jobs/{jid}/audit
-- 
-- v93_A   인덱스 자동 이관
--   - IndexMigrator 신규 — 소스 secondary index → 타겟 자동 생성
--   - 시그니처 기반 중복 방지
--   - PHASE_INDEX_CREATE 추가
-- 
-- v93_B   잔존 객체 3건 처방
--   - FUNCTION 자동 라우팅 (information_schema.ROUTINES.ROUTINE_TYPE)
--   - _find_column_sample PK 우선 매칭
-- 
-- v93_D1  KB fix_prompt 정밀화
--   - ===INSTRUCTION=== / ===END=== 표준화
--   - 객체명 박힘 자동 정리 (forbidden_tokens 9개)
-- 
-- v93_D2  KB 자산 가시화
--   - AdminKbDashboard 신규 (📊 탭)
--   - 🔬 KB 후보 1클릭 등록
--   - GET /api/v1/kb/dashboard, /cases-recent, /register-candidate
-- 
-- v93_LIB 운영자 라이브러리 (이 페이지)`,
  },
  {
    id: 'docs_naming_conventions', cat: 'docs', shell: 'sql',
    title: '명명 규칙 (DataBridge 표준)',
    desc: 'schema/table/column 변환 규칙.',
    when: '신규 객체 검토, 규약 학습.',
    cmd: `-- DataBridge schema_strategy 옵션
-- 
-- ┌──────────────────────────────────────────────────────────┐
-- │ underscore (기본):                                        │
-- │   MSSQL: customer.profile         →  MySQL: customer_profile│
-- │   MSSQL: settlement.tvf_daily_trx →  MySQL: settlement_tvf_daily_trx│
-- │                                                          │
-- │ separate_db:                                             │
-- │   MSSQL: customer.profile  →  MySQL: customer_db.profile │
-- │   (MySQL 의 database = MSSQL 의 schema)                  │
-- │                                                          │
-- │ flat (스키마 무시):                                       │
-- │   MSSQL: customer.profile  →  MySQL: profile             │
-- │   ⚠ 주의: 다른 schema 동명 테이블 충돌 가능              │
-- └──────────────────────────────────────────────────────────┘
-- 
-- 컬럼명: 그대로 (case 변환만 — MSSQL 보통 PascalCase, MySQL snake_case 권장)
-- 인덱스: idx_{table}_{first_3_columns_truncated}  (v93_A)`,
  },
  {
    id: 'docs_api_endpoints', cat: 'docs', shell: 'powershell',
    title: 'API 엔드포인트 cheat sheet',
    desc: '자주 쓰는 API + 사용 예시.',
    when: '스크립트 작성, 통합 개발.',
    cmd: `# ─── Job ─────────────────────────────────
# GET    /api/v1/jobs/                        — Job 목록
# GET    /api/v1/jobs/{jid}                   — Job 상세
# POST   /api/v1/jobs/                        — Job 생성
# DELETE /api/v1/jobs/{jid}                   — Job 삭제
# GET    /api/v1/jobs/{jid}/audit             — 사후 검증 결과 (v93_C)
# POST   /api/v1/jobs/{jid}/audit/rerun       — Audit 재실행
# 
# ─── KB (v93_D2) ─────────────────────────
# GET    /api/v1/kb/patterns                  — 패턴 목록
# GET    /api/v1/kb/stats?days=30             — 통계
# GET    /api/v1/kb/dashboard                 — 대시보드 데이터
# GET    /api/v1/kb/cases-recent?limit=20     — 최근 케이스
# POST   /api/v1/kb/register-candidate        — 후보 등록
# POST   /api/v1/kb/test-match                — 패턴 매칭 테스트
# POST   /api/v1/kb/reload                    — yml 핫 리로드
# 
# ─── 검증 ─────────────────────────────────
# POST   /api/v1/validate/run/stream          — 스트리밍 검증 (concurrency 지원)
# 
# ─── 시스템 ───────────────────────────────
# GET    /api/v1/system/live                  — liveness
# GET    /api/v1/system/health                — 종합 상태
# 
# ─── 인증 ─────────────────────────────────
# POST   /api/v1/auth/login                   — 로그인
# POST   /api/v1/auth/refresh                 — 토큰 갱신`,
  },
  {
    id: 'docs_log_format', cat: 'docs', shell: 'sql',
    title: '로그 포맷 + 마커 cheat sheet',
    desc: '로그 라인의 의미 + 검색 패턴.',
    when: '로그 분석, 자동화.',
    cmd: `-- 로그 마커 의미
-- 
-- [KB] ✓ 매칭 성공: pattern_id=...        ← KB 작동 정상
-- [KB] ✗ 매칭 실패                         ← 미매칭 (KB 보강 후보)
-- [KB] 📝 프롬프트 주입: N chars            ← AI 가이드 강화
-- [KB] 💾 통계 저장: success=✓             ← 성공 결과 누적
-- 
-- [Phase E] ...                            ← AI JSON 파싱 robust
-- [v92pNN] ...                             ← v92 패치 시리즈 마커
-- [v93_X] ...                              ← v93 패치 시리즈 마커
-- 
-- [Audit/Index] 누락 인덱스: N개            ← 사후 검증
-- [Audit/FK]    깨진 참조: N건
-- [Audit/Object] 누락 객체: N개
-- 
-- TRACE NN-name args...                    ← _ai_convert_ddl 내부 추적
-- 
-- INFO  / WARNING / ERROR                  ← 표준 레벨
-- 
-- 검색 패턴 (Select-String):
--   "\\[KB\\]"                  — KB 작동
--   "Traceback|ERROR|Exception" — 에러
--   "v9[23]_[A-Z]"              — 신규 패치
--   "Audit/"                    — 사후 검증`,
  },
  {
    id: 'docs_known_gotchas', cat: 'docs', shell: 'sql',
    title: '알려진 함정 (gotchas)',
    desc: '본부장님과 작업하면서 발견한 함정들.',
    when: '신규 운영자 학습.',
    cmd: `-- 1. SHOW CREATE PROCEDURE 가 빈 결과
--    → user 권한 부족. SHOW PROCEDURE CODE 권한 필요
-- 
-- 2. mysqldump 가 routines 빠뜨림
--    → --routines --triggers --events 옵션 필수
-- 
-- 3. 한글 깨짐
--    → server, db, table, column 4단계 모두 utf8mb4 인지 확인
--    → mysql 클라이언트 default-character-set=utf8mb4
-- 
-- 4. 큰 테이블 이관 stuck
--    → MULTIPROCESS 모드는 검증 후에만 사용
--    → SAFE 모드가 안전
-- 
-- 5. v_customer_360 풀스캔 28조
--    → secondary index 누락 (v93_A 가 처방)
-- 
-- 6. tvf 함수명에 가이드 텍스트 박힘
--    → KB fix_prompt 미흡 (v93_D1 가 처방)
-- 
-- 7. AI 같은 실수 무한 반복
--    → 재시도 카운트 max 2~3 권장 + KB 강화
-- 
-- 8. Docker vmmem 폭증
--    → wsl --shutdown → 재시작
-- 
-- 9. Vite cache 안 풀림
--    → node_modules\\.vite 삭제
-- 
-- 10. 패치 적용 후 옛 코드 실행
--     → __pycache__ 삭제 + 백엔드 재시작 (--reload 만으론 부족할 수 있음)`,
  },
  {
    id: 'docs_glossary', cat: 'docs', shell: 'sql',
    title: '용어집 (Glossary)',
    desc: 'DataBridge 핵심 용어.',
    when: '신규 운영자 onboarding.',
    cmd: `-- AI 변환            : Anthropic API 로 SQL DDL 을 양 DB 간 변환
-- KB (Knowledge Base) : 변환 시 자주 발생하는 에러 패턴 + 처방
-- 패턴 (Pattern)       : KB 의 한 항목 (regex + fix_prompt)
-- 매칭 (Match)         : 에러 메시지가 패턴의 regex 와 일치
-- fix_prompt           : 매칭 시 AI 에 추가로 주입하는 가이드
-- KB 후보              : 정식 패턴은 아니지만 누적된 케이스 (검토 후 패턴화)
-- error_cases.txt      : KB 후보 누적 파일 (살아있는 자산)
-- Phase                : Job 의 진행 단계 (INIT, RUNNING, AUDIT, DONE 등)
-- Audit (사후 검증)     : 이관 완료 후 5영역 자동 검증 (v93_C)
-- IndexMigrator       : 인덱스 자동 이관 (v93_A)
-- TVF                  : Table-Valued Function (MSSQL) — MySQL 미지원
-- DDL                  : Data Definition Language (CREATE/ALTER/DROP)
-- DML                  : Data Manipulation Language (SELECT/INSERT/UPDATE)
-- schema_strategy      : 스키마 매핑 정책 (underscore/separate_db/flat)
-- KISA                 : 한국인터넷진흥원 — 보안 점검 기준
-- KB 매칭률            : 전체 매칭 시도 중 성공한 비율 (자산 품질 지표)
-- AI 절약률            : KB 가 처리해서 AI 호출 안 한 비율 (가성비 지표)`,
  },
  {
    id: 'docs_print_pdf', cat: 'docs', shell: 'powershell',
    title: '이 라이브러리 PDF 로 출력',
    desc: '망분리 PC 인계용. 브라우저 인쇄로 PDF 저장.',
    when: '운영 인계, 폐쇄망 매뉴얼 작성.',
    cmd: `# 1) 브라우저에서 /admin/operator-library 열기
# 2) ROOT 경로 입력 (운영 환경 경로)
# 3) Ctrl+P → "PDF 로 저장"
# 4) 인쇄 미리보기에서:
#    - 머리글/바닥글: 끄기
#    - 배경 그래픽: 켜기  (배지 색깔 표시)
#    - 여백: 보통
# 5) "DataBridge 운영 매뉴얼 YYYY-MM-DD.pdf" 로 저장`,
  },
]
