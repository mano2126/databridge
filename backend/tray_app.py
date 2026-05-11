"""
tray_app.py — DataBridge OS 시스템 트레이 앱 (v95_p107)

본부장님 비전: Docker Desktop 메뉴바 동급. macOS 메뉴바 / Windows 작업표시줄 트레이.

스택:
  - pystray (cross-platform tray icon)
  - Pillow  (아이콘 이미지)
  - httpx   (Supervisor API 호출)

동작:
  - 5초마다 http://127.0.0.1:8765/supervisor/status 폴링
  - 상태에 맞춰 아이콘 색상 갱신:
      green  → Backend + Frontend 둘 다 ON
      yellow → 한쪽만 ON (부분)
      red    → 둘 다 OFF or Supervisor 응답 없음
  - 메뉴 클릭 시 Supervisor API 호출 또는 브라우저 열기

실행:
  python3 tray_app.py
  
  또는:
  bash run_tray.sh start
"""
from __future__ import annotations
import os
import sys
import time
import json
import threading
import platform
import webbrowser
import logging
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

try:
    import pystray
    from pystray import MenuItem as Item, Menu
    from PIL import Image
except ImportError as e:
    print(f"[ERROR] 필수 패키지 누락: {e}")
    print("  pip install pystray Pillow")
    sys.exit(1)

# ─── 경로 ────────────────────────────────────────────────
TRAY_DIR = Path(__file__).resolve().parent
ASSETS_DIR = TRAY_DIR / "assets" / "tray"
LOGS_DIR = TRAY_DIR / "logs"
DATA_DIR = TRAY_DIR / "data"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

TRAY_LOG = LOGS_DIR / "tray_app.log"
TRAY_PID = DATA_DIR / "tray_app.pid"

# ─── 설정 ────────────────────────────────────────────────
SUPERVISOR_BASE = os.environ.get("DATABRIDGE_SUPERVISOR_URL", "http://127.0.0.1:8765")
FRONTEND_BASE   = os.environ.get("DATABRIDGE_FRONTEND_URL",   "http://127.0.0.1:3000")
POLL_INTERVAL   = 5.0  # 초

OS_NAME = platform.system()
IS_DARWIN = (OS_NAME == "Darwin")
IS_WINDOWS = (OS_NAME == "Windows")

# ─── 로깅 ────────────────────────────────────────────────
logging.basicConfig(
    format="[%(asctime)s] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(TRAY_LOG, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("tray")

# ─── 상태 ────────────────────────────────────────────────
class TrayState:
    def __init__(self):
        self.supervisor_running = False
        self.backend_running = False
        self.backend_pid: Optional[int] = None
        self.backend_mode: str = ""
        self.backend_uptime: Optional[float] = None
        # ── hotfix_015: Circuit Breaker 상태 ──
        self.backend_crash_reason: str = ""
        self.backend_consecutive_crashes: int = 0
        self.frontend_running = False
        self.frontend_pid: Optional[int] = None
        self.frontend_mode: str = ""
        self.frontend_uptime: Optional[float] = None
        self.frontend_port: int = 3000
        # ── hotfix_015: Frontend Circuit Breaker 상태 ──
        self.frontend_crash_reason: str = ""
        self.frontend_consecutive_crashes: int = 0
        self.last_error: str = ""
        self.last_poll_ts: float = 0.0
        self.lock = threading.RLock()

    def overall_color(self) -> str:
        with self.lock:
            if not self.supervisor_running:
                return "red"
            # ── hotfix_015: 회로 차단 상태도 빨간색 ──
            if self.backend_crash_reason or self.frontend_crash_reason:
                return "red"
            be, fe = self.backend_running, self.frontend_running
            if be and fe:
                return "green"
            if be or fe:
                return "yellow"
            return "red"

    def header_text(self) -> str:
        with self.lock:
            if not self.supervisor_running:
                return "DataBridge — Supervisor 응답 없음"
            # ── hotfix_015: 회로 차단 시 명시 ──
            if self.backend_crash_reason and self.frontend_crash_reason:
                return "DataBridge — 회로 차단 (수동 시작 필요)"
            if self.backend_crash_reason:
                return "DataBridge — Backend 회로 차단"
            if self.frontend_crash_reason:
                return "DataBridge — Frontend 회로 차단"
            be, fe = self.backend_running, self.frontend_running
            if be and fe:
                return "DataBridge is running"
            # ── hotfix_015: 본부장님 표준 — Frontend 우선 표기 ──
            if fe:
                return "DataBridge — Frontend only"
            if be:
                return "DataBridge — Backend only"
            return "DataBridge is stopped"

state = TrayState()

# ─── HTTP 헬퍼 (httpx 미설치 환경 대비 — urllib 사용) ────
def http_get(path: str, timeout: float = 2.0) -> Optional[dict]:
    try:
        url = f"{SUPERVISOR_BASE}{path}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError) as e:
        return None

def http_post(path: str, body: dict | None = None, timeout: float = 15.0) -> Optional[dict]:
    try:
        url = f"{SUPERVISOR_BASE}{path}"
        data = json.dumps(body or {}).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError) as e:
        log.warning("POST %s 실패: %s", path, e)
        return None

# ─── 아이콘 로딩 ────────────────────────────────────────
_icon_cache: dict[str, Image.Image] = {}
def load_icon(state_color: str) -> Image.Image:
    if state_color in _icon_cache:
        return _icon_cache[state_color]
    # 큰 사이즈를 로드하면 pystray 가 OS 별로 알아서 리사이즈
    f = ASSETS_DIR / f"db_{state_color}.png"
    if not f.exists():
        # fallback: 64px
        f = ASSETS_DIR / f"db_{state_color}_64.png"
    if not f.exists():
        raise FileNotFoundError(f"아이콘 파일 없음: {f}")
    img = Image.open(f).convert("RGBA")
    _icon_cache[state_color] = img
    return img

# ─── 폴링 + 메뉴 갱신 ────────────────────────────────────
_icon_obj: Optional[pystray.Icon] = None

def poll_status():
    """Supervisor 에서 상태 조회 → state 업데이트."""
    data = http_get("/supervisor/status", timeout=2.0)
    with state.lock:
        if data is None:
            state.supervisor_running = False
            state.backend_running = False
            state.frontend_running = False
            state.backend_crash_reason = ""
            state.frontend_crash_reason = ""
            state.last_error = "Supervisor (port 8765) 응답 없음"
        else:
            state.supervisor_running = True
            state.backend_running = bool(data.get("running"))
            state.backend_pid = data.get("pid")
            state.backend_mode = data.get("mode") or ""
            state.backend_uptime = data.get("uptime_seconds")
            # ── hotfix_015: CB 상태 ──
            state.backend_crash_reason = data.get("crash_reason") or ""
            state.backend_consecutive_crashes = int(data.get("consecutive_crashes") or 0)
            fe = data.get("frontend") or {}
            state.frontend_running = bool(fe.get("running"))
            state.frontend_pid = fe.get("pid")
            state.frontend_mode = fe.get("mode") or ""
            state.frontend_uptime = fe.get("uptime_seconds")
            state.frontend_port = int(fe.get("port") or 3000)
            # ── hotfix_015: Frontend CB 상태 ──
            state.frontend_crash_reason = fe.get("crash_reason") or ""
            state.frontend_consecutive_crashes = int(fe.get("consecutive_crashes") or 0)
            state.last_error = ""
        state.last_poll_ts = time.time()

def update_icon():
    """state 기반으로 아이콘 + 메뉴 갱신."""
    if _icon_obj is None:
        return
    try:
        new_img = load_icon(state.overall_color())
        _icon_obj.icon = new_img
        _icon_obj.title = state.header_text()
        # 메뉴는 dynamic=True 인 경우 자동 재계산
        _icon_obj.update_menu()
    except Exception as e:
        log.error("아이콘 갱신 실패: %s", e)

def poll_loop():
    """5초마다 Supervisor 폴링 + 아이콘 갱신."""
    while True:
        try:
            poll_status()
            update_icon()
        except Exception as e:
            log.error("polling 예외: %s", e)
        time.sleep(POLL_INTERVAL)

# ─── 메뉴 액션 ──────────────────────────────────────────
def action_open_admin(icon, item):
    webbrowser.open(f"{FRONTEND_BASE}/admin/console/process")

def action_open_backend_console(icon, item):
    webbrowser.open(f"{FRONTEND_BASE}/admin/console/process/backend-console")

def action_open_frontend_console(icon, item):
    webbrowser.open(f"{FRONTEND_BASE}/admin/console/process/frontend-console")

def action_open_frontend(icon, item):
    webbrowser.open(FRONTEND_BASE)

# ─── Backend 액션 (mode 파라미터화 — combo_001 옵션 A1) ───
def _backend_start_mode(mode: str):
    """Backend 시작 (mode 파라미터화). 메뉴에서 mode 선택 시 호출."""
    def _action(icon, item):
        log.info("Backend 시작 요청 (mode=%s)", mode)
        r = http_post("/supervisor/start", {"mode": mode})
        log.info("응답: %s", r)
        # 좀비 검출 / Circuit Breaker 거부 시 사용자에게 보이도록 갱신
        threading.Thread(target=lambda: (time.sleep(1.5), poll_status(), update_icon()),
                         daemon=True).start()
    return _action

def _backend_restart_mode(mode: str):
    """Backend 재시작 (mode 파라미터화)."""
    def _action(icon, item):
        log.info("Backend 재시작 요청 (mode=%s)", mode)
        r = http_post("/supervisor/restart", {"mode": mode})
        log.info("응답: %s", r)
        threading.Thread(target=lambda: (time.sleep(2.5), poll_status(), update_icon()),
                         daemon=True).start()
    return _action

def action_be_stop(icon, item):
    log.info("Backend 중지 요청")
    r = http_post("/supervisor/stop", {})
    log.info("응답: %s", r)
    threading.Thread(target=lambda: (time.sleep(1.5), poll_status(), update_icon()),
                     daemon=True).start()

# ─── Frontend 액션 (mode 파라미터화) ───
def _frontend_start_mode(mode: str):
    """Frontend 시작 (mode 파라미터화)."""
    def _action(icon, item):
        log.info("Frontend 시작 요청 (mode=%s)", mode)
        r = http_post("/supervisor/frontend/start", {"mode": mode})
        log.info("응답: %s", r)
        threading.Thread(target=lambda: (time.sleep(2.0), poll_status(), update_icon()),
                         daemon=True).start()
    return _action

def _frontend_restart_mode(mode: str):
    """Frontend 재시작 (mode 파라미터화)."""
    def _action(icon, item):
        log.info("Frontend 재시작 요청 (mode=%s)", mode)
        r = http_post("/supervisor/frontend/restart", {"mode": mode})
        log.info("응답: %s", r)
        threading.Thread(target=lambda: (time.sleep(2.5), poll_status(), update_icon()),
                         daemon=True).start()
    return _action

def action_fe_stop(icon, item):
    log.info("Frontend 중지 요청")
    r = http_post("/supervisor/frontend/stop", {})
    log.info("응답: %s", r)
    threading.Thread(target=lambda: (time.sleep(1.5), poll_status(), update_icon()),
                     daemon=True).start()

def action_refresh(icon, item):
    log.info("수동 새로고침")
    poll_status()
    update_icon()

def action_quit(icon, item):
    log.info("트레이 앱 종료")
    icon.stop()

# ─── 메뉴 구성 (Docker Desktop 패턴) ─────────────────────
def fmt_uptime(s: Optional[float]) -> str:
    if not s:
        return ""
    sec = int(s)
    if sec < 60: return f"{sec}s"
    if sec < 3600: return f"{sec//60}m"
    if sec < 86400: return f"{sec//3600}h {(sec%3600)//60}m"
    return f"{sec//86400}d {(sec%86400)//3600}h"

def be_status_label(_=None) -> str:
    with state.lock:
        if not state.supervisor_running:
            return "● Backend  : Supervisor 응답 없음"
        # ── hotfix_015: 회로 차단 우선 표시 ──
        if state.backend_crash_reason:
            return f"⚠ Backend  : 회로 차단 ({state.backend_consecutive_crashes}회 실패)"
        if state.backend_running:
            mode = state.backend_mode.upper() if state.backend_mode else ""
            up = fmt_uptime(state.backend_uptime)
            return f"● Backend  : running (PID {state.backend_pid}, {mode}, up {up})"
        return "○ Backend  : stopped"

def fe_status_label(_=None) -> str:
    with state.lock:
        if not state.supervisor_running:
            return "● Frontend : Supervisor 응답 없음"
        # ── hotfix_015: 회로 차단 우선 표시 ──
        if state.frontend_crash_reason:
            return f"⚠ Frontend : 회로 차단 ({state.frontend_consecutive_crashes}회 실패)"
        if state.frontend_running:
            mode = state.frontend_mode.upper() if state.frontend_mode else ""
            up = fmt_uptime(state.frontend_uptime)
            return f"● Frontend : running (PID {state.frontend_pid}, {mode}, :{state.frontend_port}, up {up})"
        return "○ Frontend : stopped"

def header_label(_=None) -> str:
    return state.header_text()

def build_menu():
    """동적 메뉴. 상태 변경 시 update_menu() 가 재평가.

    v95_p107 combo_001 (2026-05-10 본부장님 결정):
      - 옵션 A1: Start ▶ Mode (Safe/Multiprocess/Thread)
      - 표준 #21: Frontend → Backend 순서 고정
    """
    return Menu(
        # 헤더 (상태 텍스트, 비활성)
        Item(header_label, None, enabled=False),
        Menu.SEPARATOR,
        # ── 본부장님 표준 #21: Frontend → Backend 순서 ──
        Item(fe_status_label, None, enabled=False),
        Item(be_status_label, None, enabled=False),
        Menu.SEPARATOR,
        # Dashboard
        Item("관리자 콘솔 열기...", action_open_admin),
        Item("Frontend 열기 (브라우저)", action_open_frontend),
        Menu.SEPARATOR,
        # ── Frontend 서브메뉴 (Frontend 가 위) ──
        Item("Frontend", Menu(
            # Start ▶ Mode 선택
            Item("Start", Menu(
                Item("Auto (default)", _frontend_start_mode("auto"),
                     enabled=lambda i: state.supervisor_running and not state.frontend_running),
                Item("Dev", _frontend_start_mode("dev"),
                     enabled=lambda i: state.supervisor_running and not state.frontend_running),
                Item("Release", _frontend_start_mode("release"),
                     enabled=lambda i: state.supervisor_running and not state.frontend_running),
            )),
            Item("Stop", action_fe_stop,
                 enabled=lambda i: state.supervisor_running and state.frontend_running),
            # Restart ▶ Mode 선택
            Item("Restart", Menu(
                Item("Auto (default)", _frontend_restart_mode("auto"),
                     enabled=lambda i: state.supervisor_running and state.frontend_running),
                Item("Dev", _frontend_restart_mode("dev"),
                     enabled=lambda i: state.supervisor_running and state.frontend_running),
                Item("Release", _frontend_restart_mode("release"),
                     enabled=lambda i: state.supervisor_running and state.frontend_running),
            )),
            Menu.SEPARATOR,
            Item("콘솔 열기...", action_open_frontend_console),
        )),
        # ── Backend 서브메뉴 (Backend 가 아래) ──
        Item("Backend", Menu(
            # Start ▶ Mode 선택
            Item("Start", Menu(
                Item("Safe (default)", _backend_start_mode("safe"),
                     enabled=lambda i: state.supervisor_running and not state.backend_running),
                Item("Multiprocess", _backend_start_mode("multiprocess"),
                     enabled=lambda i: state.supervisor_running and not state.backend_running),
                Item("Thread", _backend_start_mode("thread"),
                     enabled=lambda i: state.supervisor_running and not state.backend_running),
            )),
            Item("Stop", action_be_stop,
                 enabled=lambda i: state.supervisor_running and state.backend_running),
            # Restart ▶ Mode 선택
            Item("Restart", Menu(
                Item("Safe (default)", _backend_restart_mode("safe"),
                     enabled=lambda i: state.supervisor_running and state.backend_running),
                Item("Multiprocess", _backend_restart_mode("multiprocess"),
                     enabled=lambda i: state.supervisor_running and state.backend_running),
                Item("Thread", _backend_restart_mode("thread"),
                     enabled=lambda i: state.supervisor_running and state.backend_running),
            )),
            Menu.SEPARATOR,
            Item("콘솔 열기...", action_open_backend_console),
        )),
        Menu.SEPARATOR,
        Item("새로고침", action_refresh),
        Menu.SEPARATOR,
        Item("Quit", action_quit),
    )

# ─── 메인 ────────────────────────────────────────────────
def main():
    global _icon_obj

    # PID 기록
    try:
        TRAY_PID.write_text(str(os.getpid()))
    except Exception as e:
        log.warning("PID 기록 실패: %s", e)

    log.info("=" * 50)
    log.info("DataBridge Tray App — v95_p107")
    log.info("OS=%s, Python=%s", OS_NAME, sys.version.split()[0])
    log.info("Supervisor: %s", SUPERVISOR_BASE)
    log.info("=" * 50)

    # 초기 상태 폴링 (시작 시 즉시)
    poll_status()
    initial_icon = load_icon(state.overall_color())

    # 트레이 아이콘 생성
    _icon_obj = pystray.Icon(
        name="DataBridge",
        icon=initial_icon,
        title=state.header_text(),
        menu=build_menu(),
    )

    # 폴링 스레드
    threading.Thread(target=poll_loop, daemon=True, name="tray-poll").start()

    log.info("트레이 앱 시작 — 메뉴바 확인")
    try:
        _icon_obj.run()  # blocking
    finally:
        try:
            if TRAY_PID.exists():
                TRAY_PID.unlink()
        except Exception:
            pass
        log.info("트레이 앱 종료됨")

if __name__ == "__main__":
    main()
