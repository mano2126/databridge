#!/bin/bash
# ============================================================
# DataBridge Tray App Launcher (macOS / Linux)
# v95_p107
# ============================================================
# Usage:
#   bash run_tray.sh start       # 트레이 앱 시작 (백그라운드)
#   bash run_tray.sh stop        # 트레이 앱 종료
#   bash run_tray.sh status      # 상태
#   bash run_tray.sh logs        # 로그
#   bash run_tray.sh foreground  # 포그라운드 실행 (디버깅)
# ============================================================
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DATA_DIR="$SCRIPT_DIR/data"
LOGS_DIR="$SCRIPT_DIR/logs"
mkdir -p "$DATA_DIR" "$LOGS_DIR"

TRAY_PID="$DATA_DIR/tray_app.pid"
TRAY_LOG="$LOGS_DIR/tray_app.log"

if [ -t 1 ]; then
    G='\033[0;32m'; R='\033[0;31m'; Y='\033[0;33m'; B='\033[0;34m'; N='\033[0m'
else
    G=''; R=''; Y=''; B=''; N=''
fi

CMD="${1:-status}"
OS_NAME="$(uname -s)"

check_venv() {
    if [ ! -f "venv/bin/activate" ]; then
        echo -e "${R}[ERROR] venv not found at: $SCRIPT_DIR/venv/bin/activate${N}" >&2
        exit 1
    fi
}

check_deps() {
    source venv/bin/activate
    if ! python -c "import pystray, PIL" 2>/dev/null; then
        echo -e "${Y}[INFO] pystray/Pillow 미설치 — 설치 시도${N}"
        pip install --quiet pystray==0.19.5 Pillow==10.4.0 \
            || { echo -e "${R}[ERROR] 설치 실패${N}"; exit 1; }
    fi
}

is_alive() {
    if [ ! -f "$TRAY_PID" ]; then return 1; fi
    local pid=$(cat "$TRAY_PID")
    if [ -z "$pid" ]; then return 1; fi
    if kill -0 "$pid" 2>/dev/null; then return 0; fi
    return 1
}

case "$CMD" in
    start)
        check_venv
        check_deps
        # stale PID 정리
        if [ -f "$TRAY_PID" ]; then
            old_pid=$(cat "$TRAY_PID")
            if [ -n "$old_pid" ] && ! kill -0 "$old_pid" 2>/dev/null; then
                rm -f "$TRAY_PID"
            fi
        fi
        if is_alive; then
            echo -e "${Y}[INFO] Tray app already running (PID=$(cat $TRAY_PID))${N}"
            exit 0
        fi
        echo -e "${G}[START]${N} Tray app 시작..."
        # macOS: GUI 앱이므로 nohup + & + disown
        # 단, pystray 의 NSApplication 은 메인 스레드 GUI 가 필요해서
        # 일반 detach 가능 (Python 안에서 자체 메인루프)
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Tray starting (OS=$OS_NAME)" >> "$TRAY_LOG"
        nohup python tray_app.py >> "$TRAY_LOG" 2>&1 &
        CHILD_PID=$!
        disown $CHILD_PID 2>/dev/null || true
        echo $CHILD_PID > "$TRAY_PID"
        sleep 2
        if is_alive; then
            echo -e "  ${G}✓ Tray app 시작됨 (PID=$CHILD_PID)${N}"
            echo "    상단 메뉴바를 확인하세요 (DataBridge 아이콘)"
            echo "    Log: $TRAY_LOG"
        else
            echo -e "  ${R}✗ Tray app 시작 실패${N}"
            echo "── 마지막 30 라인 ──"
            tail -30 "$TRAY_LOG"
            exit 1
        fi
        ;;
    stop)
        if ! is_alive; then
            echo -e "${Y}[INFO] Tray app not running${N}"
            rm -f "$TRAY_PID"
            exit 0
        fi
        local_pid=$(cat "$TRAY_PID")
        echo -e "${R}[STOP]${N} Tray app 종료 (PID=$local_pid)..."
        kill "$local_pid" 2>/dev/null || true
        for i in 1 2 3 4 5; do
            if ! kill -0 "$local_pid" 2>/dev/null; then break; fi
            sleep 1
        done
        if kill -0 "$local_pid" 2>/dev/null; then
            kill -9 "$local_pid" 2>/dev/null || true
        fi
        rm -f "$TRAY_PID"
        echo -e "  ${G}✓ Tray app 종료됨${N}"
        ;;
    status)
        if is_alive; then
            echo -e "${G}● Tray app 실행 중${N} (PID=$(cat $TRAY_PID))"
        else
            echo -e "${R}○ Tray app 중지됨${N}"
            rm -f "$TRAY_PID"
            exit 1
        fi
        ;;
    logs)
        echo -e "${B}[LOGS]${N} tail -f $TRAY_LOG"
        tail -f "$TRAY_LOG"
        ;;
    foreground|fg)
        check_venv
        check_deps
        if is_alive; then
            echo -e "${Y}[WARN] 이미 실행 중 — 먼저 stop${N}"
            exit 1
        fi
        source venv/bin/activate
        exec python tray_app.py
        ;;
    *)
        echo "Usage: $0 {start|stop|status|logs|foreground}"
        exit 1
        ;;
esac
