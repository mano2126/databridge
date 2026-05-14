"""
v95_p9: 통합 로깅 설정 (본질 처방)

본질:
1. databridge.log + databridge_backend.log → databridge_backend.log 단일화
2. 동일 핸들러 중복 등록 버그 제거 (좀비 부팅 메시지 방지)
3. 사이즈/시간 OR 회전 (HybridRotatingHandler)
4. 사용자 설정값 (size_mb, interval_hours) 저장/적용

v95_p107 hotfix_098 (2026-05-13 본부장님 본질 처방):
   "로그 시작 중지는 tray에서 지정할 수 있도록"
   "아무것도 안하고 엔진만 올렸는데 쌓여서 불편해"

발견된 두 본질:
  ① LOG_DIR Windows 경로 하드코딩 → macOS 환경 깨짐 (본부장님 환경 logs/ 비어있던 이유)
  ② 파일 로깅 always-on → 본부장님이 의도하지 않은 누적

처방:
  ① LOG_DIR 을 __file__ 기준 동적 계산 (Windows/macOS/Linux 모두 작동)
  ② file_logging_enabled 설정 추가 (기본 OFF — 본부장님이 트레이에서 명시적 ON)
  ③ log_level 설정 추가 (Info/Warn/Error/Debug)
  ④ apply_runtime_settings() — 재시작 없이 즉시 반영
"""
import logging
import logging.handlers
import os
import time
import json
from pathlib import Path
from datetime import datetime, timedelta

# v95_p107 hotfix_098: LOG_DIR 동적 계산
# logging_setup.py 는 backend/app/core/ 에 있음 → parents[2] = backend/
_THIS_DIR = Path(__file__).resolve().parent           # backend/app/core
_BACKEND_DIR = _THIS_DIR.parent.parent                  # backend/
LOG_DIR = _BACKEND_DIR / "logs"
ARCHIVE_DIR = LOG_DIR / "archive"
SETTINGS_FILE = LOG_DIR / "logging_settings.json"
PRIMARY_LOG = LOG_DIR / "databridge_backend.log"

# 폐기 대상 (v95_p9 에서 통합)
LEGACY_LOG = LOG_DIR / "databridge.log"

DEFAULT_SETTINGS = {
    "size_mb": 5,        # 1 ~ 5
    "interval_hours": 1,  # 1, 2, 4, 6, 12, 24
    "retention_days": 30,  # 백업 보관 일수
    # v95_p107 hotfix_098: 본부장님 본질 처방 — 기본 OFF
    "file_logging_enabled": False,   # ★ 파일 로깅 토글 (기본 OFF)
    "log_level": "INFO",              # INFO / WARNING / ERROR / DEBUG
}


def _load_settings():
    """사용자 설정 로드 (없으면 기본값)"""
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 검증
            size_mb = max(1, min(5, int(data.get("size_mb", 5))))
            interval_hours = max(1, min(24, int(data.get("interval_hours", 1))))
            retention_days = max(1, min(365, int(data.get("retention_days", 30))))
            # v95_p107 hotfix_098: 새 옵션
            file_enabled = bool(data.get("file_logging_enabled", False))
            level = str(data.get("log_level", "INFO")).upper()
            if level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
                level = "INFO"
            return {
                "size_mb": size_mb,
                "interval_hours": interval_hours,
                "retention_days": retention_days,
                "file_logging_enabled": file_enabled,
                "log_level": level,
            }
    except Exception:
        pass
    return DEFAULT_SETTINGS.copy()


def save_settings(size_mb: int = None, interval_hours: int = None,
                  retention_days: int = None,
                  file_logging_enabled: bool = None,
                  log_level: str = None):
    """사용자 설정 저장.
    
    v95_p107 hotfix_098: None 인 인자는 기존값 유지 (부분 갱신 지원).
    UI / tray 가 토글만 바꾸고 싶을 때 호출.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    cur = _load_settings()
    payload = {
        "size_mb": max(1, min(5, int(size_mb if size_mb is not None else cur["size_mb"]))),
        "interval_hours": max(1, min(24, int(interval_hours if interval_hours is not None else cur["interval_hours"]))),
        "retention_days": max(1, min(365, int(retention_days if retention_days is not None else cur["retention_days"]))),
        "file_logging_enabled": bool(file_logging_enabled if file_logging_enabled is not None else cur["file_logging_enabled"]),
        "log_level": (log_level or cur["log_level"]).upper(),
    }
    if payload["log_level"] not in ("DEBUG", "INFO", "WARNING", "ERROR"):
        payload["log_level"] = "INFO"
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def get_settings():
    return _load_settings()


class HybridRotatingHandler(logging.handlers.RotatingFileHandler):
    """
    사이즈 OR 시간 OR 조건 회전 핸들러.
    먼저 도달하는 조건으로 회전, 회전 시 archive/ 로 이동.
    """

    def __init__(self, filename, max_bytes, interval_hours, encoding="utf-8"):
        super().__init__(
            filename,
            maxBytes=max_bytes,
            backupCount=0,  # 자체 archive 관리
            encoding=encoding,
        )
        self.interval_seconds = interval_hours * 3600
        self.next_rollover_time = time.time() + self.interval_seconds
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    def shouldRollover(self, record):
        # 사이즈 조건 (부모)
        if super().shouldRollover(record):
            return 1
        # 시간 조건 (OR)
        if time.time() >= self.next_rollover_time:
            return 1
        return 0

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None

        if os.path.exists(self.baseFilename):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = ARCHIVE_DIR / f"databridge_backend_{ts}.log"
            try:
                os.replace(self.baseFilename, str(archive_name))
            except Exception:
                # 이동 실패 시 truncate (로깅 끊기지 않게)
                try:
                    open(self.baseFilename, "w").close()
                except Exception:
                    pass

        self.next_rollover_time = time.time() + self.interval_seconds

        if not self.delay:
            self.stream = self._open()


def cleanup_old_archives(retention_days: int = 30):
    """보관 기간 초과 백업 자동 삭제"""
    if not ARCHIVE_DIR.exists():
        return 0
    cutoff = datetime.now() - timedelta(days=retention_days)
    deleted = 0
    for f in ARCHIVE_DIR.glob("*.log"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                f.unlink()
                deleted += 1
        except Exception:
            continue
    return deleted


def archive_and_clear():
    """
    화면 초기화 시 호출:
    현재 로그를 archive/cleared_YYYYMMDD_HHMMSS.log 로 이동 후 truncate.
    """
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    if not PRIMARY_LOG.exists() or PRIMARY_LOG.stat().st_size == 0:
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = ARCHIVE_DIR / f"cleared_{ts}.log"

    # 핸들러 close → 이동 → truncate → 핸들러 재오픈
    root = logging.getLogger()
    target_handler = None
    for h in root.handlers:
        if isinstance(h, HybridRotatingHandler):
            target_handler = h
            break

    try:
        if target_handler and target_handler.stream:
            target_handler.stream.close()
            target_handler.stream = None

        # 복사 후 원본 truncate (이동 대신 — 핸들러가 다시 열 수 있게)
        import shutil
        shutil.copy2(str(PRIMARY_LOG), str(archive_path))
        open(str(PRIMARY_LOG), "w", encoding="utf-8").close()

        if target_handler:
            target_handler.stream = target_handler._open()
    except Exception as e:
        # 실패해도 일단 진행
        print(f"[archive_and_clear] error: {e}")
        return None

    # 보관 기간 정리
    settings = _load_settings()
    cleanup_old_archives(settings["retention_days"])

    return str(archive_path)


_SETUP_DONE = False
_LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}


def setup_logging():
    """
    중복 등록 방지하며 단일 로거 구성.
    main.py 에서 한 번만 호출.
    
    v95_p107 hotfix_098: file_logging_enabled / log_level 반영.
    file 핸들러는 토글 ON 일 때만 등록. console 은 항상.
    """
    global _SETUP_DONE
    if _SETUP_DONE:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    settings = _load_settings()
    level = _LOG_LEVEL_MAP.get(settings["log_level"], logging.INFO)

    # 본질: 기존 핸들러 모두 제거 (중복 등록 방지)
    root = logging.getLogger()
    for h in list(root.handlers):
        try:
            h.close()
        except Exception:
            pass
        root.removeHandler(h)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # console 은 항상
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    # 파일 핸들러는 토글 ON 일 때만 (본부장님 본질 처방)
    if settings["file_logging_enabled"]:
        file_handler = HybridRotatingHandler(
            filename=str(PRIMARY_LOG),
            max_bytes=settings["size_mb"] * 1024 * 1024,
            interval_hours=settings["interval_hours"],
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)

    root.setLevel(level)

    # 좀비 로그 폐기: databridge.log 가 남아있으면 archive 로 이관
    if LEGACY_LOG.exists() and LEGACY_LOG.stat().st_size > 0:
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            legacy_archive = ARCHIVE_DIR / f"legacy_databridge_{ts}.log"
            import shutil
            shutil.move(str(LEGACY_LOG), str(legacy_archive))
            logging.info(f"[v95_p9] 레거시 로그 이관: {legacy_archive.name}")
        except Exception as e:
            logging.warning(f"[v95_p9] 레거시 로그 이관 실패: {e}")

    # 시작 시 1회 보관 정리 (파일 로깅 ON 일 때만 의미 있음)
    if settings["file_logging_enabled"]:
        deleted = cleanup_old_archives(settings["retention_days"])
        if deleted > 0:
            logging.info(f"[v95_p9] 만료 백업 {deleted}건 삭제 (보관 {settings['retention_days']}일)")

    logging.info(
        f"[v95_p107-hotfix_098] 로깅 시작 → level={settings['log_level']} "
        f"file={'ON' if settings['file_logging_enabled'] else 'OFF (콘솔만)'} "
        f"path={PRIMARY_LOG if settings['file_logging_enabled'] else 'console-only'}"
    )
    _SETUP_DONE = True


def apply_runtime_settings():
    """
    v95_p107 hotfix_098: 재시작 없이 file_logging / level 즉시 반영.
    트레이/UI 에서 토글 후 호출. 본부장님 모토 "한방에" — 백엔드 재시작 불필요.
    """
    settings = _load_settings()
    root = logging.getLogger()
    level = _LOG_LEVEL_MAP.get(settings["log_level"], logging.INFO)
    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 기존 파일 핸들러 찾기
    existing_file_handlers = [
        h for h in root.handlers
        if isinstance(h, HybridRotatingHandler) or isinstance(h, logging.FileHandler)
    ]

    if settings["file_logging_enabled"]:
        # ON 으로 전환 — 핸들러 없으면 추가
        if not existing_file_handlers:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            handler = HybridRotatingHandler(
                filename=str(PRIMARY_LOG),
                max_bytes=settings["size_mb"] * 1024 * 1024,
                interval_hours=settings["interval_hours"],
                encoding="utf-8",
            )
            handler.setFormatter(fmt)
            root.addHandler(handler)
            logging.info(f"[v95_p107-hotfix_098] 파일 로깅 ON → {PRIMARY_LOG.name}")
    else:
        # OFF 로 전환 — 파일 핸들러 제거
        for h in existing_file_handlers:
            try:
                h.close()
            except Exception:
                pass
            root.removeHandler(h)
        if existing_file_handlers:
            logging.info("[v95_p107-hotfix_098] 파일 로깅 OFF (콘솔만 유지)")

    return settings
