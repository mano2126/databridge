"""
app/api/routes/process.py — v95_p104 (2026-05-09 본부장님 비전)

백엔드 프로세스 관리 API:
  GET    /api/v1/process/status    — 현재 백엔드 상태 (PID, 모드, 가동시간)
  POST   /api/v1/process/start     — 백엔드 시작 (감지/거절: 이미 실행 중)
  POST   /api/v1/process/stop      — 백엔드 중지 (자기 자신 종료)
  POST   /api/v1/process/restart   — 재시작 (중지 → 잠시 대기 → 시작)

본부장님 비전:
  엔터프라이즈급 — 시작/중지/재시작 + 빨간불/초록불 상태 + 모드 표시.
  자기 자신 죽이는 본질 처방: subprocess + detach + PID 파일.

구조:
  - PID 파일: backend/data/backend.pid (run_backend.sh 가 기록)
  - 시작 스크립트: backend/run_backend.sh (macOS) 또는 run_backend.bat (Windows)
  - 모드: safe / multiprocess / thread
  - 권한: status=viewer, start/stop/restart=admin
"""
from __future__ import annotations
import os
import sys
import time
import signal
import logging
import platform
import subprocess
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth_deps import require_admin, require_viewer

router = APIRouter()
_log = logging.getLogger("databridge.process")

# ─── PID 파일 경로 (run_backend.sh / .bat 와 동일) ──────────
def _backend_root() -> Path:
    """backend 디렉토리 절대 경로."""
    # 이 파일: backend/app/api/routes/process.py → 4단계 위
    return Path(__file__).resolve().parents[3]

def _pid_file() -> Path:
    return _backend_root() / "data" / "backend.pid"

def _launcher_script() -> Path:
    """OS 별 launcher 스크립트 경로."""
    if platform.system() == "Windows":
        return _backend_root() / "run_backend.bat"
    return _backend_root() / "run_backend.sh"

# ─── 프로세스 살아있는지 체크 ────────────────────────────
def _is_alive(pid: int) -> bool:
    """PID 가 살아있는지 — kill(pid, 0) 이 raise 안 하면 살아있음."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False

def _read_pid() -> Optional[int]:
    """PID 파일에서 읽기. 없거나 죽은 프로세스면 None."""
    pf = _pid_file()
    if not pf.exists():
        return None
    try:
        pid = int(pf.read_text().strip())
        if _is_alive(pid):
            return pid
        # 죽은 PID 파일 정리
        try: pf.unlink()
        except Exception: pass
        return None
    except (ValueError, OSError):
        return None

def _process_start_time(pid: int) -> Optional[float]:
    """프로세스 시작 시각 (Unix epoch). macOS / Linux 만."""
    try:
        if platform.system() == "Darwin":
            # macOS: ps -o lstart=
            r = subprocess.run(
                ["ps", "-o", "lstart=", "-p", str(pid)],
                capture_output=True, text=True, timeout=2
            )
            if r.returncode == 0 and r.stdout.strip():
                # "Sat May  9 18:00:00 2026" 형식
                import time as _t
                t = _t.strptime(r.stdout.strip(), "%a %b %d %H:%M:%S %Y")
                return _t.mktime(t)
        elif platform.system() == "Linux":
            # /proc/{pid}/stat 의 22번째 필드 (starttime, jiffies)
            with open(f"/proc/{pid}/stat") as f:
                fields = f.read().split()
            starttime_jiffies = int(fields[21])
            # boot time + (starttime / clk_tck)
            with open("/proc/stat") as f:
                for line in f:
                    if line.startswith("btime "):
                        boot_time = int(line.split()[1])
                        break
            clk_tck = os.sysconf("SC_CLK_TCK")
            return boot_time + (starttime_jiffies / clk_tck)
    except Exception:
        pass
    return None

def _detect_mode_from_env() -> str:
    """환경 변수에서 현재 모드 추정."""
    exp = os.environ.get("DATABRIDGE_CHUNK_EXPERIMENT", "")
    cm = os.environ.get("DATABRIDGE_CHUNK_MODE", "")
    if exp == "1":
        if cm == "process":
            return "multiprocess"
        if cm == "thread":
            return "thread"
    return "safe"

# ─── API 모델 ────────────────────────────────────────────
class ProcessStatusResponse(BaseModel):
    running: bool
    pid: Optional[int] = None
    mode: str = ""
    uptime_seconds: Optional[float] = None
    started_at: Optional[float] = None       # Unix epoch
    launcher_script: str = ""
    launcher_exists: bool = False
    platform: str = ""
    self_pid: int                             # 응답하는 백엔드 자신의 PID

class ProcessStartRequest(BaseModel):
    mode: str = "safe"                        # safe | multiprocess | thread

class ProcessActionResponse(BaseModel):
    ok: bool
    message: str
    pid: Optional[int] = None

# ─── REST API ────────────────────────────────────────────

@router.get("/status", response_model=ProcessStatusResponse)
def process_status(_=Depends(require_viewer)):
    """현재 백엔드 프로세스 상태.
    
    self_pid 와 PID 파일의 PID 가 같으면 → 이 API 가 응답하는 백엔드가 살아있음.
    다르면 → 다른 백엔드 인스턴스가 PID 파일에 기록된 상태 (이상 케이스).
    """
    pid = _read_pid()
    self_pid = os.getpid()
    
    # PID 파일이 없으면 → 자기 자신 PID 라도 표시 (현재 응답 중인 프로세스)
    if pid is None:
        # 응답 중인 프로세스가 곧 백엔드
        pid = self_pid
    
    started_at = _process_start_time(pid)
    uptime = (time.time() - started_at) if started_at else None
    
    launcher = _launcher_script()
    
    return ProcessStatusResponse(
        running=True,                         # 응답하면 살아있음
        pid=pid,
        mode=_detect_mode_from_env(),
        uptime_seconds=uptime,
        started_at=started_at,
        launcher_script=str(launcher),
        launcher_exists=launcher.exists(),
        platform=platform.system(),
        self_pid=self_pid,
    )

@router.post("/start", response_model=ProcessActionResponse)
def process_start(body: ProcessStartRequest, admin=Depends(require_admin)):
    """백엔드 프로세스 시작 (이미 실행 중이면 거절).
    
    이 API 호출은 — 실제 시나리오에서는 — '중지' 후 사용 안 됨 
    (중지 시 백엔드 자체가 죽으므로 이 API 호출 불가). 
    그러나 PID 파일 잔재 등 이상 상태 복구 용도로 유지.
    
    실제 시작은 사용자가 터미널/launchd/systemd 에서 run_backend.sh 실행.
    """
    pid = _read_pid()
    if pid:
        return ProcessActionResponse(
            ok=False,
            message=f"백엔드가 이미 실행 중입니다 (PID={pid})",
            pid=pid,
        )
    
    launcher = _launcher_script()
    if not launcher.exists():
        raise HTTPException(404, f"Launcher 스크립트 없음: {launcher}")
    
    mode = body.mode.lower()
    if mode not in ("safe", "multiprocess", "thread"):
        raise HTTPException(400, f"Invalid mode: {mode}. Use safe/multiprocess/thread.")
    
    try:
        if platform.system() == "Windows":
            # Windows: BAT 파일은 자체 모드 메뉴가 있어 자동화 어려움 → 거절
            return ProcessActionResponse(
                ok=False,
                message="Windows 에서는 run_backend.bat 를 직접 실행하세요.",
            )
        else:
            # macOS / Linux: run_backend.sh <mode> --detach
            r = subprocess.run(
                ["bash", str(launcher), mode, "--detach"],
                capture_output=True, text=True, timeout=10,
                cwd=str(_backend_root()),
            )
            if r.returncode == 0:
                # PID 파일에서 새 PID 읽기
                time.sleep(0.5)
                new_pid = _read_pid()
                _log.info("[process] 백엔드 시작 성공 (PID=%s, mode=%s)", new_pid, mode)
                return ProcessActionResponse(
                    ok=True,
                    message=f"백엔드 시작됨 (mode={mode})",
                    pid=new_pid,
                )
            else:
                _log.error("[process] 시작 실패: stdout=%s stderr=%s", r.stdout, r.stderr)
                return ProcessActionResponse(
                    ok=False,
                    message=f"시작 실패: {r.stderr.strip() or r.stdout.strip()}",
                )
    except subprocess.TimeoutExpired:
        return ProcessActionResponse(ok=False, message="시작 명령 타임아웃 (10초)")
    except Exception as e:
        _log.exception("[process] 시작 중 예외")
        raise HTTPException(500, f"시작 실패: {e}")

@router.post("/stop", response_model=ProcessActionResponse)
def process_stop(admin=Depends(require_admin)):
    """백엔드 프로세스 중지 (자기 자신 종료).
    
    응답 후 즉시 자기 자신을 SIGTERM 으로 종료.
    UI 는 이 응답을 받으면 "중지됨" 표시 + 상태 폴링 시작 (시작 버튼만 활성화).
    
    안전 본질: 응답 후 1초 대기 → SIGTERM → uvicorn graceful shutdown.
    """
    self_pid = os.getpid()
    _log.warning("[process] 본부장님 중지 요청 — self_pid=%d", self_pid)
    
    # 응답 후 종료를 예약 (별도 스레드에서 1초 후 SIGTERM)
    import threading
    def _delayed_kill():
        time.sleep(1.0)
        _log.warning("[process] 자기 자신 SIGTERM 송신 (PID=%d)", self_pid)
        try:
            os.kill(self_pid, signal.SIGTERM)
        except Exception as e:
            _log.error("[process] SIGTERM 실패: %s", e)
            # fallback: SIGKILL
            try: os.kill(self_pid, signal.SIGKILL)
            except Exception: pass
    
    threading.Thread(target=_delayed_kill, daemon=True).start()
    
    return ProcessActionResponse(
        ok=True,
        message=f"백엔드 중지 신호 전송됨 (PID={self_pid}, 1초 후 종료)",
        pid=self_pid,
    )

@router.post("/restart", response_model=ProcessActionResponse)
def process_restart(body: ProcessStartRequest, admin=Depends(require_admin)):
    """재시작 — 중지 + 잠시 대기 + 시작.
    
    본질 주의:
      자기 자신을 죽이고 새로 시작은 본질적으로 불가능 (응답 못 함).
      → 실제 동작: 1) 별도 supervisor 스크립트 호출 (있으면), 또는
                   2) 단순 stop 만 하고 사용자가 launchd/systemd 에 의존
    
    macOS: launchd KeepAlive 가 설정되어 있으면 자동 재시작.
           아니면 사용자가 터미널에서 run_backend.sh 재실행 필요.
    """
    self_pid = os.getpid()
    _log.warning("[process] 재시작 요청 — self_pid=%d, mode=%s", self_pid, body.mode)
    
    # 단순 SIGTERM (위 stop 과 같은 패턴)
    # KeepAlive 있는 환경 (launchd/systemd) 에서는 자동 재시작
    import threading
    def _delayed_restart():
        time.sleep(1.0)
        _log.warning("[process] 자기 자신 SIGTERM (재시작 의도)")
        try:
            os.kill(self_pid, signal.SIGTERM)
        except Exception as e:
            _log.error("[process] 재시작용 SIGTERM 실패: %s", e)
    
    threading.Thread(target=_delayed_restart, daemon=True).start()
    
    return ProcessActionResponse(
        ok=True,
        message=(f"재시작 신호 전송됨 (PID={self_pid}, 1초 후 종료). "
                 f"launchd/systemd 가 자동 재시작합니다. "
                 f"수동 환경이면 터미널에서 run_backend.sh 재실행."),
        pid=self_pid,
    )
