#!/bin/bash
# ============================================================
# DataBridge Backend Launcher (macOS / Linux)
# ------------------------------------------------------------
# Location: ~/project/databridge_full/backend/run_backend.sh
# Usage   : 
#   1) 직접 실행 (메뉴 모드):
#      bash run_backend.sh
#
#   2) 인자로 모드 지정 (관리자 콘솔에서 자동 호출):
#      bash run_backend.sh safe
#      bash run_backend.sh multiprocess
#      bash run_backend.sh thread
#
#   3) Detached 모드 (관리자 콘솔에서 호출):
#      bash run_backend.sh safe --detach
#
# Replaces: run_backend.bat (Windows)
# Author  : v95_p104 (2026-05-09 본부장님 비전)
# ============================================================

set -e

# 스크립트 위치를 기준으로 작업 디렉토리 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 색상 정의 (터미널 직접 실행 시만)
if [ -t 1 ]; then
    G='\033[0;32m'  # 초록
    R='\033[0;31m'  # 빨강
    Y='\033[0;33m'  # 노랑
    B='\033[0;34m'  # 파랑
    BOLD='\033[1m'
    N='\033[0m'
else
    G=''; R=''; Y=''; B=''; BOLD=''; N=''
fi

# 인자 파싱
MODE="${1:-}"
DETACH="${2:-}"

# Detach 모드 검증
if [ "$DETACH" = "--detach" ] || [ "$1" = "--detach" ]; then
    DETACH_MODE=1
    [ "$1" = "--detach" ] && MODE="${2:-safe}"
else
    DETACH_MODE=0
fi

# 모드별 환경 변수 설정 함수
configure_mode() {
    local mode="$1"
    case "$mode" in
        safe)
            MODE_NAME="SAFE (single thread)"
            export DATABRIDGE_DEV_MODE=1
            unset DATABRIDGE_CHUNK_EXPERIMENT
            unset DATABRIDGE_CHUNK_MODE
            ;;
        multiprocess|mp)
            MODE_NAME="MULTIPROCESS (4 worker processes, Phase 3a)"
            export DATABRIDGE_DEV_MODE=1
            export DATABRIDGE_CHUNK_EXPERIMENT=1
            export DATABRIDGE_CHUNK_MODE=process
            ;;
        thread)
            MODE_NAME="THREAD (4 worker threads, diagnostic)"
            export DATABRIDGE_DEV_MODE=1
            export DATABRIDGE_CHUNK_EXPERIMENT=1
            export DATABRIDGE_CHUNK_MODE=thread
            ;;
        *)
            return 1
            ;;
    esac
    return 0
}

# 메뉴 표시 (인자로 모드 안 들어왔을 때)
show_menu() {
    clear
    echo "============================================================"
    echo "  DataBridge Backend -- Mode Selection (macOS / Linux)"
    echo "============================================================"
    echo ""
    echo "  Select execution mode:"
    echo ""
    echo -e "  ${BOLD}[1] SAFE${N}          -- Single thread, proven stable"
    echo "                       Use for: Production, real customer DB"
    echo "                       Speed  : ~4,800 rows/s baseline"
    echo "                       Risk   : Lowest"
    echo ""
    echo -e "  ${BOLD}[2] MULTIPROCESS${N}  -- 4 worker processes (Phase 3a)"
    echo "                       Use for: Large tables (1M+ rows)"
    echo "                       Speed  : ~9,300 rows/s (2x baseline)"
    echo -e "                       Risk   : ${Y}Medium -- requires ~4x memory${N}"
    echo ""
    echo -e "  ${BOLD}[3] THREAD${N}        -- 4 worker threads (diagnostic only)"
    echo "                       Use for: Comparison/diagnostic only"
    echo "                       Speed  : ~3,700 rows/s (slower than safe!)"
    echo -e "                       Risk   : ${R}Known slow due to GIL${N}"
    echo ""
    echo "  [Q] Quit"
    echo ""
    echo "------------------------------------------------------------"
    echo "  Recommendation:"
    echo -e "    * First run / production  -> ${G}[1] SAFE${N}"
    echo -e "    * Large dataset + tested  -> ${B}[2] MULTIPROCESS${N}"
    echo "    * Just pressing Enter     -> [1] SAFE (default)"
    echo "------------------------------------------------------------"
    echo ""
    
    read -p "Enter choice [1/2/3/Q] (default=1): " CHOICE
    CHOICE="${CHOICE:-1}"
    
    case "$CHOICE" in
        1) MODE="safe" ;;
        2) MODE="multiprocess" ;;
        3)
            echo ""
            echo -e "${Y}WARNING: THREAD mode is known to be SLOWER than SAFE mode${N}"
            echo "         due to Python GIL limitation. Use for diagnostic only."
            echo ""
            read -p "Continue anyway? [y/N]: " CONFIRM
            if [[ ! "$CONFIRM" =~ ^[yY]$ ]]; then
                show_menu
                return
            fi
            MODE="thread"
            ;;
        [qQ]) exit 0 ;;
        *)
            echo ""
            echo "Invalid choice: $CHOICE"
            sleep 1
            show_menu
            return
            ;;
    esac
}

# ─── 모드 결정 ────────────────────────────────────────────
if [ -z "$MODE" ]; then
    show_menu
fi

if ! configure_mode "$MODE"; then
    echo -e "${R}[ERROR] Invalid mode: $MODE${N}" >&2
    echo "Valid modes: safe, multiprocess, thread" >&2
    exit 1
fi

# ─── venv 검증 ────────────────────────────────────────────
if [ ! -f "venv/bin/activate" ]; then
    echo -e "${R}[ERROR] venv not found at: $SCRIPT_DIR/venv/bin/activate${N}" >&2
    exit 1
fi

# Detach 모드: PID 파일 + 백그라운드 실행
if [ "$DETACH_MODE" = "1" ]; then
    PID_FILE="$SCRIPT_DIR/data/backend.pid"
    LOG_FILE="$SCRIPT_DIR/logs/backend_supervisor.log"
    mkdir -p "$SCRIPT_DIR/data" "$SCRIPT_DIR/logs"
    
    # 기존 프로세스가 살아있으면 거절
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if kill -0 "$OLD_PID" 2>/dev/null; then
            echo "ERROR: Backend already running (PID=$OLD_PID)" >&2
            exit 2
        fi
    fi
    
    # nohup + setsid (별도 프로세스 그룹) → 부모 죽어도 살아남음
    {
        source venv/bin/activate
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backend starting in DETACHED mode: $MODE_NAME" >> "$LOG_FILE"
        exec python -m uvicorn main:app --port 8000 --host 0.0.0.0 >> "$LOG_FILE" 2>&1
    } &
    
    BACKEND_PID=$!
    
    # 프로세스 그룹 분리 (부모 죽어도 살아남음)
    disown
    
    echo "$BACKEND_PID" > "$PID_FILE"
    echo "Backend started in detached mode (PID=$BACKEND_PID, MODE=$MODE)"
    echo "PID file: $PID_FILE"
    echo "Log file: $LOG_FILE"
    exit 0
fi

# ─── Foreground 모드: 일반 실행 ──────────────────────────
clear
echo "============================================================"
echo "  DataBridge Backend -- Starting"
echo "============================================================"
echo ""
echo "  Mode      : $MODE_NAME"
echo "  Location  : $SCRIPT_DIR"
echo "  Date      : $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "  Environment:"
echo "    DATABRIDGE_DEV_MODE         = ${DATABRIDGE_DEV_MODE:-(unset)}"
echo "    DATABRIDGE_CHUNK_EXPERIMENT = ${DATABRIDGE_CHUNK_EXPERIMENT:-(disabled)}"
echo "    DATABRIDGE_CHUNK_MODE       = ${DATABRIDGE_CHUNK_MODE:-(default)}"
echo ""
echo "------------------------------------------------------------"

source venv/bin/activate
echo -e "  venv      : ${G}activated${N}"
echo "  Python    : $(python --version 2>&1)"
echo ""
echo "------------------------------------------------------------"
echo ""
echo "  Starting uvicorn... (press Ctrl+C to stop)"
echo ""
echo "============================================================"
echo ""

# PID 파일 기록 (Foreground 도 PID 기록 — 관리자 콘솔에서 상태 조회용)
PID_FILE="$SCRIPT_DIR/data/backend.pid"
mkdir -p "$SCRIPT_DIR/data"
echo "$$" > "$PID_FILE"

# 종료 시 PID 파일 정리
trap "rm -f '$PID_FILE'; echo ''; echo '============================================================'; echo '  Backend stopped'; echo '============================================================'" EXIT INT TERM

exec python -m uvicorn main:app --port 8000 --reload
