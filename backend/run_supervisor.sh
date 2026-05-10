#!/bin/bash
# DataBridge Supervisor Launcher (macOS / Linux)
# v95_p106_hotfix_001 — macOS setsid 부재 대응
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DATA_DIR="$SCRIPT_DIR/data"
LOGS_DIR="$SCRIPT_DIR/logs"
mkdir -p "$DATA_DIR" "$LOGS_DIR"

SUPERVISOR_PID="$DATA_DIR/supervisor.pid"
SUPERVISOR_LOG="$LOGS_DIR/supervisor.log"
SUPERVISOR_PORT=8765

if [ -t 1 ]; then
    G='\033[0;32m'; R='\033[0;31m'; Y='\033[0;33m'; B='\033[0;34m'; BOLD='\033[1m'; N='\033[0m'
else
    G=''; R=''; Y=''; B=''; BOLD=''; N=''
fi

CMD="${1:-status}"
START_OPT="${2:-}"

OS_NAME="$(uname -s)"
HAS_SETSID=0
if command -v setsid >/dev/null 2>&1; then
    HAS_SETSID=1
fi

check_venv() {
    if [ ! -f "venv/bin/activate" ]; then
        echo -e "${R}[ERROR] venv not found at: $SCRIPT_DIR/venv/bin/activate${N}" >&2
        echo "  실행: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt" >&2
        exit 1
    fi
}

is_supervisor_alive() {
    if [ ! -f "$SUPERVISOR_PID" ]; then return 1; fi
    local pid=$(cat "$SUPERVISOR_PID")
    if [ -z "$pid" ]; then return 1; fi
    if kill -0 "$pid" 2>/dev/null; then return 0; fi
    return 1
}

auto_start_engines() {
    local opt="$1"
    local backend_yes=1
    local frontend_yes=1
    case "$opt" in
        --backend-only)    frontend_yes=0 ;;
        --frontend-only)   backend_yes=0 ;;
        --supervisor-only) backend_yes=0; frontend_yes=0 ;;
    esac
    
    for i in 1 2 3 4 5 6 7 8 9 10; do
        if curl -s -m 1 "http://127.0.0.1:$SUPERVISOR_PORT/supervisor/health" > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    
    if [ "$backend_yes" = "1" ]; then
        echo -e "  ${B}→ Backend 자동 시작 (mode=safe)${N}"
        curl -s -X POST "http://127.0.0.1:$SUPERVISOR_PORT/supervisor/start" \
            -H "Content-Type: application/json" \
            -d '{"mode":"safe"}' | head -c 200
        echo ""
    fi
    if [ "$frontend_yes" = "1" ]; then
        echo -e "  ${B}→ Frontend 자동 시작 (mode=auto)${N}"
        curl -s -X POST "http://127.0.0.1:$SUPERVISOR_PORT/supervisor/frontend/start" \
            -H "Content-Type: application/json" \
            -d '{"mode":"auto"}' | head -c 200
        echo ""
    fi
}

case "$CMD" in
    start)
        check_venv
        # 기존 stale PID 정리
        if [ -f "$SUPERVISOR_PID" ]; then
            old_pid=$(cat "$SUPERVISOR_PID")
            if [ -n "$old_pid" ] && ! kill -0 "$old_pid" 2>/dev/null; then
                rm -f "$SUPERVISOR_PID"
            fi
        fi
        if is_supervisor_alive; then
            echo -e "${Y}[INFO] Supervisor already running (PID=$(cat $SUPERVISOR_PID))${N}"
            echo -e "  Status: ${B}http://127.0.0.1:$SUPERVISOR_PORT/supervisor/status${N}"
            exit 0
        fi
        echo -e "${G}[START]${N} DataBridge Supervisor 데몬 시작... (OS=$OS_NAME, setsid=$HAS_SETSID)"
        source venv/bin/activate
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Supervisor starting (OS=$OS_NAME)" >> "$SUPERVISOR_LOG"
        
        if [ "$HAS_SETSID" = "1" ]; then
            nohup setsid python supervisor.py >> "$SUPERVISOR_LOG" 2>&1 &
            CHILD_PID=$!
        else
            # macOS: setsid 없음 — nohup + & + disown
            nohup python supervisor.py >> "$SUPERVISOR_LOG" 2>&1 &
            CHILD_PID=$!
            disown $CHILD_PID 2>/dev/null || true
        fi
        echo $CHILD_PID > "$SUPERVISOR_PID"
        sleep 2
        
        if is_supervisor_alive; then
            echo -e "  ${G}✓ Supervisor 시작됨 (PID=$(cat $SUPERVISOR_PID))${N}"
            echo "    API : http://127.0.0.1:$SUPERVISOR_PORT/supervisor/status"
            echo "    Log : $SUPERVISOR_LOG"
            auto_start_engines "$START_OPT"
        else
            echo -e "  ${R}✗ Supervisor 시작 실패${N}"
            echo "    Log: $SUPERVISOR_LOG"
            echo "── 마지막 30 라인 ──"
            tail -30 "$SUPERVISOR_LOG"
            exit 1
        fi
        ;;
    
    stop)
        if ! is_supervisor_alive; then
            echo -e "${Y}[INFO] Supervisor not running${N}"
            rm -f "$SUPERVISOR_PID"
            exit 0
        fi
        local_pid=$(cat "$SUPERVISOR_PID")
        echo -e "${R}[STOP]${N} Supervisor 종료 중 (PID=$local_pid)..."
        kill "$local_pid" 2>/dev/null || true
        for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
            if ! kill -0 "$local_pid" 2>/dev/null; then break; fi
            sleep 1
        done
        if kill -0 "$local_pid" 2>/dev/null; then
            echo -e "  ${Y}grace 타임아웃 → SIGKILL${N}"
            kill -9 "$local_pid" 2>/dev/null || true
        fi
        rm -f "$SUPERVISOR_PID"
        echo -e "  ${G}✓ Supervisor 종료됨${N}"
        ;;
    
    status)
        if is_supervisor_alive; then
            sup_pid=$(cat "$SUPERVISOR_PID")
            echo -e "${G}● Supervisor 실행 중${N} (PID=$sup_pid, port=$SUPERVISOR_PORT)"
            if command -v curl > /dev/null 2>&1; then
                echo ""
                echo "  Backend+Frontend 상태:"
                curl -s -m 2 "http://127.0.0.1:$SUPERVISOR_PORT/supervisor/status" 2>/dev/null \
                    | python3 -m json.tool 2>/dev/null \
                    | head -40 || echo "  (status API 응답 없음)"
            fi
        else
            echo -e "${R}○ Supervisor 중지됨${N}"
            rm -f "$SUPERVISOR_PID"
            exit 1
        fi
        ;;
    
    logs)
        echo -e "${B}[LOGS]${N} tail -f $SUPERVISOR_LOG (Ctrl+C 종료)"
        tail -f "$SUPERVISOR_LOG"
        ;;
    
    foreground|fg)
        check_venv
        if is_supervisor_alive; then
            echo -e "${Y}[WARN] Supervisor 이미 실행 중 — 먼저 stop 하세요${N}"
            exit 1
        fi
        echo -e "${G}[FOREGROUND]${N} Supervisor 포그라운드 실행 (Ctrl+C 종료)"
        source venv/bin/activate
        exec python supervisor.py
        ;;
    
    *)
        echo "Usage: $0 {start|stop|status|logs|foreground} [--backend-only|--frontend-only|--supervisor-only]"
        exit 1
        ;;
esac
