#!/bin/bash
# ============================================================
# DataBridge v95_p106 Big Bang Patch — RUN.sh
# 2026-05-09 본부장님
# ============================================================
# 본부장님 환경: ~/project/databridge_full/
# 이 ZIP 은 ~/project/ 에서 압축 해제되어
#   ~/project/databridge_full/ 위에 덮어씌워집니다.
#
# 사용:
#   cd ~/project
#   unzip databridge_v95_p106_001.zip
#   cd databridge_full
#   bash RUN.sh
# ============================================================
set -e

if [ -t 1 ]; then
    G='\033[0;32m'; R='\033[0;31m'; Y='\033[0;33m'; B='\033[0;34m'; BOLD='\033[1m'; N='\033[0m'
else
    G=''; R=''; Y=''; B=''; BOLD=''; N=''
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo -e "  ${BOLD}DataBridge v95_p106 Big Bang Patch${N}"
echo "  Working dir: $SCRIPT_DIR"
echo "  Date       : $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

# ─── 1. 사전 체크 ─────────────────────────────────────────
echo -e "${B}[1/4]${N} 사전 체크..."

if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo -e "${R}  ✗ 잘못된 위치 — backend/ 또는 frontend/ 없음${N}"
    echo "    이 스크립트는 databridge_full/ 디렉토리 안에서 실행해야 합니다."
    echo "    현재 위치: $SCRIPT_DIR"
    exit 1
fi
echo "  ✓ backend/ frontend/ 확인"

if [ ! -f "backend/main.py" ]; then
    echo -e "${R}  ✗ backend/main.py 없음 — DataBridge 프로젝트가 맞나요?${N}"
    exit 1
fi
echo "  ✓ backend/main.py 확인"

# ─── 2. 백업 ──────────────────────────────────────────────
echo ""
echo -e "${B}[2/4]${N} 변경 대상 파일 백업..."

TS=$(date '+%Y%m%d_%H%M%S')
BACKUP_TAG="before_v95_p106_$TS"

backup_file() {
    local f="$1"
    if [ -f "$f" ]; then
        cp "$f" "$f.$BACKUP_TAG"
        echo "  ✓ 백업: $f.$BACKUP_TAG"
    fi
}

# 변경되는 3개 파일만 백업
backup_file "backend/app/api/routes/process.py"
backup_file "frontend/src/pages/AdminProcess.vue"
backup_file "frontend/src/App.vue"
backup_file "frontend/src/router/index.js"

# 신규 파일은 백업 불필요 (이미 ZIP 안에 있음)
echo "  (신규 파일: supervisor.py, run_supervisor.sh/.bat,"
echo "             BackendConsole.vue, FrontendConsole.vue, SystemTrayWidget.vue)"

# ─── 3. 권한 설정 ─────────────────────────────────────────
echo ""
echo -e "${B}[3/4]${N} 실행 권한 설정..."
chmod +x backend/run_supervisor.sh 2>/dev/null && echo "  ✓ chmod +x backend/run_supervisor.sh" || true
chmod +x backend/run_backend.sh 2>/dev/null && echo "  ✓ chmod +x backend/run_backend.sh" || true

# ─── 4. 의존성 체크 ───────────────────────────────────────
echo ""
echo -e "${B}[4/4]${N} 의존성 체크..."
if [ -f "backend/venv/bin/python" ]; then
    if backend/venv/bin/python -c "import httpx" 2>/dev/null; then
        echo "  ✓ httpx 설치됨"
    else
        echo -e "${Y}  ⚠ httpx 없음 — 설치 시도${N}"
        backend/venv/bin/pip install --quiet httpx==0.28.1 || \
            echo -e "${R}    httpx 설치 실패 — 수동 설치 필요${N}"
    fi
    if backend/venv/bin/python -c "import fastapi" 2>/dev/null; then
        echo "  ✓ fastapi 설치됨"
    fi
    if backend/venv/bin/python -c "import uvicorn" 2>/dev/null; then
        echo "  ✓ uvicorn 설치됨"
    fi
else
    echo -e "${Y}  ⚠ venv 없음 — backend/venv 생성 필요${N}"
fi

# ─── 완료 ────────────────────────────────────────────────
echo ""
echo "============================================================"
echo -e "  ${G}${BOLD}✓ v95_p106 패치 적용 완료${N}"
echo "============================================================"
echo ""
echo -e "${BOLD}다음 단계 — Supervisor 데몬 시작:${N}"
echo ""
echo -e "  ${B}1) Supervisor + Backend + Frontend 모두 자동 시작:${N}"
echo "     cd $SCRIPT_DIR/backend"
echo "     bash run_supervisor.sh start"
echo ""
echo -e "  ${B}2) Supervisor 만 (Backend/Frontend 는 관리자 UI 에서 시작):${N}"
echo "     bash run_supervisor.sh start --supervisor-only"
echo ""
echo -e "  ${B}3) 상태 확인:${N}"
echo "     bash run_supervisor.sh status"
echo ""
echo -e "  ${B}4) Supervisor 로그 실시간:${N}"
echo "     bash run_supervisor.sh logs"
echo ""
echo -e "  ${B}5) 정지:${N}"
echo "     bash run_supervisor.sh stop"
echo ""
echo "------------------------------------------------------------"
echo -e "${BOLD}URL:${N}"
echo "  Supervisor API : http://127.0.0.1:8765/supervisor/status"
echo "  Backend API    : http://127.0.0.1:8000/api/v1/process/status"
echo "  Frontend UI    : http://127.0.0.1:3000"
echo "  관리자 콘솔     : http://127.0.0.1:3000/admin/console/process"
echo "------------------------------------------------------------"
echo ""
echo -e "${BOLD}변경 내역 (v95_p106):${N}"
echo "  ✓ Backend Supervisor (포트 8765, JEUS NodeManager 동급)"
echo "  ✓ Frontend 통합 관리 (auto/dev/release 모드)"
echo "  ✓ KeepAlive 자동 재시작 (Backend + Frontend 모두)"
echo "  ✓ 빨간불/초록불 상태 + 실시간 콘솔 (별창)"
echo "  ✓ 우측 하단 시스템 트레이 위젯 ⭐"
echo ""
echo -e "${G}본부장님 — 화이팅! ❤️🔥🚀${N}"
echo ""
