# ============================================================
# DataBridge GitHub 신규 업로드 스크립트
# ------------------------------------------------------------
# 시나리오:
#   - GitHub 웹에서 기존 mano2126/databridge 저장소를 수동 삭제하고
#   - 동일 이름으로 빈 저장소를 새로 생성한 직후 실행하는 스크립트
#   - 로컬의 .git 폴더도 삭제하고 완전히 새로 시작
#
# 사전 작업 (수동, 스크립트 실행 전 반드시 수행):
#   [1] https://github.com/mano2126/databridge/settings
#       → 페이지 맨 아래 "Danger Zone" → "Delete this repository"
#       → 저장소 이름 입력 후 삭제
#
#   [2] https://github.com/new
#       → Repository name: databridge
#       → Owner: mano2126
#       → Public / Private 선택 (기존과 동일하게)
#       → "Add a README", "Add .gitignore", "Choose a license"
#         이 세 가지는 반드시 모두 체크 해제 (빈 저장소여야 함)
#       → "Create repository" 클릭
#
# 사전 작업이 끝나면 이 스크립트를 실행하세요.
#
# 사용법:
#   1. 이 파일을 D:\project\databridge_full\ 위치에 저장
#   2. PowerShell 열기
#   3. cd D:\project\databridge_full
#   4. .\github_fresh_upload.ps1
#
# 실행 정책 오류 시:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
# ============================================================

$ErrorActionPreference = "Stop"

# --- 설정 ---------------------------------------------------
$ProjectPath = "D:\project\databridge_full"
$RepoUrl     = "https://github.com/mano2126/databridge.git"
$RepoWebUrl  = "https://github.com/mano2126/databridge"
$Branch      = "main"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " DataBridge GitHub 신규 업로드" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# --- 0. 사전 작업 확인 --------------------------------------
Write-Host "[사전 확인] GitHub 작업을 모두 완료하셨나요?" -ForegroundColor Yellow
Write-Host "  [1] 기존 mano2126/databridge 저장소 삭제" -ForegroundColor Gray
Write-Host "  [2] 동일 이름으로 빈 저장소 새로 생성 (README/gitignore/license 모두 체크 해제)" -ForegroundColor Gray
Write-Host ""
$confirm = Read-Host "두 작업을 모두 완료하셨다면 Y 를 입력하세요 (계속) / N 입력 시 종료"
if ($confirm -ne "Y" -and $confirm -ne "y") {
    Write-Host "종료합니다. GitHub 사전 작업 후 다시 실행하세요." -ForegroundColor Red
    exit 0
}
Write-Host ""

# --- 1. 작업 디렉토리 확인 ----------------------------------
if (-not (Test-Path $ProjectPath)) {
    Write-Host "[ERROR] 프로젝트 경로가 없습니다: $ProjectPath" -ForegroundColor Red
    exit 1
}
Set-Location $ProjectPath
Write-Host "[INFO] 작업 디렉토리: $ProjectPath" -ForegroundColor Green
Write-Host ""

# --- 2. 기존 .git 폴더 완전 삭제 ----------------------------
Write-Host "[STEP 1/6] 기존 .git 폴더 제거 중..." -ForegroundColor Yellow
if (Test-Path ".git") {
    # Windows Git이 만든 readonly 파일 속성 제거 후 삭제
    cmd /c "attrib -r -s -h .git\*.* /s /d" 2>$null | Out-Null
    Remove-Item -Path ".git" -Recurse -Force
    Write-Host "          기존 .git 폴더 삭제 완료" -ForegroundColor Green
} else {
    Write-Host "          .git 폴더 없음 (건너뜀)" -ForegroundColor Gray
}
Write-Host ""

# --- 3. .gitignore 생성/덮어쓰기 ----------------------------
Write-Host "[STEP 2/6] .gitignore 생성 중..." -ForegroundColor Yellow
$GitIgnore = @"
# Python
__pycache__/
*.py[cod]
*.pyo
*.egg-info/
.venv/
venv/
env/

# Node / Vue
node_modules/
dist/
.vite/
*.log
npm-debug.log*

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
desktop.ini

# 환경변수 / 비밀
.env
.env.local
.env.*.local
*.key
*.pem

# 로그 / 임시
logs/
*.tmp
*.bak
*.zip

# DB / 데이터
*.mdf
*.ldf
data/raw/
backend/uploads/
"@

Set-Content -Path ".gitignore" -Value $GitIgnore -Encoding UTF8
Write-Host "          .gitignore 작성 완료" -ForegroundColor Green
Write-Host ""

# --- 4. Git 초기화 ------------------------------------------
Write-Host "[STEP 3/6] Git 저장소 초기화 중..." -ForegroundColor Yellow
git init -b $Branch | Out-Null
Write-Host "          git init 완료 (branch: $Branch)" -ForegroundColor Green
Write-Host ""

# --- 5. user 정보 확인 (없으면 임시 설정) -------------------
Write-Host "[STEP 4/6] Git user 정보 확인 중..." -ForegroundColor Yellow
$userName  = git config user.name  2>$null
$userEmail = git config user.email 2>$null
if (-not $userName) {
    git config user.name "mano2126"
    Write-Host "          user.name = mano2126 (임시 설정)" -ForegroundColor Gray
} else {
    Write-Host "          user.name = $userName" -ForegroundColor Gray
}
if (-not $userEmail) {
    git config user.email "mano2126@users.noreply.github.com"
    Write-Host "          user.email = mano2126@users.noreply.github.com (임시 설정)" -ForegroundColor Gray
} else {
    Write-Host "          user.email = $userEmail" -ForegroundColor Gray
}
Write-Host ""

# --- 6. 원격 저장소 연결 ------------------------------------
Write-Host "[STEP 5/6] 원격 저장소 연결 중..." -ForegroundColor Yellow
git remote add origin $RepoUrl
Write-Host "          remote origin = $RepoUrl" -ForegroundColor Green
Write-Host ""

# --- 7. 전체 파일 add + commit + push -----------------------
Write-Host "[STEP 6/6] 파일 추가, commit, push 중..." -ForegroundColor Yellow
git add -A

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
git commit -m "Initial commit: DataBridge full upload ($timestamp)" | Out-Null
Write-Host "          commit 완료" -ForegroundColor Green

Write-Host "          GitHub로 push 중... (인증 창이 뜰 수 있습니다)" -ForegroundColor DarkYellow
git push -u origin $Branch

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host " 업로드 성공!" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host " URL: $RepoWebUrl" -ForegroundColor Cyan
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "[ERROR] push 실패. 다음을 확인하세요:" -ForegroundColor Red
    Write-Host "  1. GitHub 저장소가 빈 상태인지 (README 등 없이)" -ForegroundColor Yellow
    Write-Host "  2. GitHub 인증 (Personal Access Token 또는 GitHub CLI 로그인)" -ForegroundColor Yellow
    Write-Host "  3. 네트워크 / 회사 방화벽 정책" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  인증 문제라면:" -ForegroundColor Yellow
    Write-Host "    gh auth login" -ForegroundColor Gray
    Write-Host "  또는 GitHub Settings > Developer settings > Personal access tokens 에서" -ForegroundColor Yellow
    Write-Host "  토큰 발급 후 push 재시도 시 비밀번호 자리에 입력" -ForegroundColor Yellow
    exit 1
}
