"""
app/api/routes/settings.py
시스템 설정 + 로깅 설정 API — JSON 파일 영속성 적용
"""
from fastapi import APIRouter
import logging, os
from app.core.store import Store

router = APIRouter()

# ── 설정 기본값 ───────────────────────────────────────────
_DEFAULTS: dict = {
    "batch_size":         5000,
    "parallel_workers":   4,
    "log_level":          "INFO",
    "log_retention_days": 30,
    "notify_email":       False,
    "notify_slack":       False,
    "on_error":           "skip",
    "retry_count":        3,
    "backend_log_file":   "./logs/databridge_backend.log",
    "frontend_log_file":  "./logs/databridge_frontend.log",
    "log_format":         "TEXT",
    "log_max_mb":         50,
    "log_backup_count":   5,
    "anthropic_api_key":  os.environ.get("ANTHROPIC_API_KEY", ""),
}

# ── JSON 파일 영속 스토어 ─────────────────────────────────
_store = Store("settings")

# 저장된 설정이 없으면 기본값으로 초기화
if _store.get("config") is None:
    _store.set("config", _DEFAULTS.copy())

def _cfg() -> dict:
    """현재 설정 딕셔너리 반환 (기본값 병합)"""
    saved = _store.get("config", {})
    merged = {**_DEFAULTS, **saved}
    # 환경변수 API 키 우선 (설정 저장값보다 env가 있으면 env 사용)
    env_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if env_key:
        merged["anthropic_api_key"] = env_key
    return merged


# ── 로거 초기화 ────────────────────────────────────────────
def _setup_logging(cfg: dict):
    """설정에 따라 루트 로거를 재구성 (rotate 후에도 정상 동작)"""
    from logging.handlers import RotatingFileHandler
    level_str  = cfg.get("log_level", "INFO").upper()
    log_file   = cfg.get("backend_log_file", "./logs/databridge_backend.log")
    log_format = cfg.get("log_format", "TEXT")
    max_mb     = int(cfg.get("log_max_mb", 50))
    backup_cnt = int(cfg.get("log_backup_count", 5))
    level = getattr(logging, level_str, logging.INFO)

    log_dir = os.path.dirname(os.path.abspath(log_file))
    os.makedirs(log_dir, exist_ok=True)

    if log_format == "JSON":
        fmt = '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","msg":"%(message)s"}'
    else:
        fmt = "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s"
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    root = logging.getLogger()
    root.setLevel(level)

    # 기존 핸들러 완전 제거 (닫기 포함)
    for h in root.handlers[:]:
        try:
            h.flush()
            h.close()
        except Exception:
            pass
        root.removeHandler(h)

    # 콘솔 핸들러
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(formatter)
    root.addHandler(ch)

    # 파일 핸들러 (RotatingFileHandler)
    try:
        fh = RotatingFileHandler(
            log_file,
            maxBytes=max_mb * 1024 * 1024,
            backupCount=backup_cnt,
            encoding="utf-8"
        )
        fh.setLevel(level)
        fh.setFormatter(formatter)
        root.addHandler(fh)
        logging.info("로깅 초기화 완료: %s (레벨: %s)", os.path.abspath(log_file), level_str)
    except Exception as e:
        logging.warning("로그 파일 핸들러 생성 실패: %s", e)

    # uvicorn 등 서드파티 로거의 레벨도 강제 설정 (DEBUG 차단 방지)
    for name in ("databridge", "databridge.jobs", "databridge.schema",
                 "databridge.frontend", "databridge.backend"):
        lg = logging.getLogger(name)
        lg.setLevel(level)
        lg.propagate = True  # 루트로 전파


# 기동 시 저장된 설정으로 로깅 초기화
_setup_logging(_cfg())


# ── REST API ──────────────────────────────────────────────

@router.get("/")
def get_settings():
    return _cfg()


@router.put("/")
def update_settings(body: dict):
    current = _cfg()
    current.update(body)
    # API 키는 env 우선이므로 저장에서 제외하지 않음 (사용자가 명시적으로 넣은 것은 저장)
    _store.set("config", current)

    log_keys = {"log_level", "backend_log_file", "log_format", "log_max_mb", "log_backup_count"}
    if log_keys.intersection(body.keys()):
        _setup_logging(current)
        logging.info(f"로깅 설정 변경됨: { {k: body[k] for k in log_keys if k in body} }")
    return current


@router.get("/log-tail")
def tail_log(lines: int = 300, source: str = "backend"):
    """로그 파일 마지막 N줄 반환"""
    cfg = _cfg()
    key = "backend_log_file" if source == "backend" else "frontend_log_file"
    log_file = cfg.get(key, f"./logs/databridge_{source}.log")
    abs_path = os.path.abspath(log_file)
    if not os.path.exists(abs_path):
        return {"lines": [], "file": abs_path, "exists": False,
                "message": f"로그 파일이 없습니다: {abs_path}"}
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return {
            "lines":  [l.rstrip() for l in tail],
            "file":   abs_path,
            "exists": True,
            "total":  len(all_lines),
            "source": source,
        }
    except Exception as e:
        return {"lines": [str(e)], "file": abs_path, "exists": True, "error": str(e)}


@router.get("/log-info")
def log_info(source: str = "backend"):
    """로그 파일 정보"""
    cfg = _cfg()
    key = "backend_log_file" if source == "backend" else "frontend_log_file"
    log_file = cfg.get(key, f"./logs/databridge_{source}.log")
    abs_path = os.path.abspath(log_file)
    exists   = os.path.exists(abs_path)
    size_kb  = round(os.path.getsize(abs_path) / 1024, 1) if exists else 0
    return {
        "file":    abs_path,
        "exists":  exists,
        "size_kb": size_kb,
        "level":   cfg.get("log_level", "INFO"),
        "source":  source,
    }


@router.get("/log-info-both")
def log_info_both():
    """백엔드 + 프론트엔드 로그 파일 정보"""
    cfg = _cfg()

    def _info(path_key):
        log_file = cfg.get(path_key, "")
        abs_path = os.path.abspath(log_file) if log_file else ""
        exists   = os.path.exists(abs_path) if abs_path else False
        size_kb  = round(os.path.getsize(abs_path) / 1024, 1) if exists else 0
        return {"file": abs_path, "exists": exists, "size_kb": size_kb, "rel": log_file}

    return {
        "backend":  {**_info("backend_log_file"),  "level": cfg.get("log_level", "INFO")},
        "frontend": {**_info("frontend_log_file")},
    }


@router.post("/api-key-test")
def test_api_key():
    """Anthropic API 키 연결 테스트"""
    import urllib.request as _ur, urllib.error as _ue, json as _j
    key = _cfg().get("anthropic_api_key", "").strip()
    if not key:
        return {"ok": False, "error": "API 키가 설정되지 않았습니다. 시스템 설정에서 입력하세요."}
    try:
        payload = _j.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 20,
            "messages": [{"role": "user", "content": "Say OK"}]
        }).encode()
        req = _ur.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type":      "application/json",
                "x-api-key":         key,
                "anthropic-version": "2023-06-01",
            },
            method="POST"
        )
        with _ur.urlopen(req, timeout=15) as r:
            data = _j.loads(r.read())
        text  = data.get("content", [{}])[0].get("text", "")
        model = data.get("model", "")
        return {"ok": True, "message": f"연결 성공! 모델: {model} | 응답: {text}"}
    except _ue.HTTPError as e:
        body = e.read().decode()
        try:
            err_data = _j.loads(body)
            err_type = err_data.get("error", {}).get("type", "")
            err_msg  = err_data.get("error", {}).get("message", "")
            if err_type == "authentication_error":
                return {"ok": False, "error": "API 키가 올바르지 않습니다. console.anthropic.com에서 키를 확인하세요."}
            return {"ok": False, "error": f"HTTP {e.code} {err_type}: {err_msg}"}
        except Exception:
            return {"ok": False, "error": f"HTTP {e.code}: {body[:200]}"}
    except _ue.URLError as e:
        return {"ok": False, "error": f"네트워크 오류: {e.reason}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/frontend-log")
def receive_frontend_log(body: dict):
    """프론트엔드 로그를 파일로 기록"""
    import time as _t
    cfg    = _cfg()
    logger = logging.getLogger("databridge.frontend")
    level  = body.get("level", "info").upper()
    msg    = body.get("message", "")
    detail = body.get("detail", "")
    page   = body.get("page", "")
    full   = f"[PAGE:{page}] {msg}" + (f" | {detail}" if detail else "")
    lvl    = getattr(logging, level, logging.INFO)
    logger.log(lvl, full)

    fe_log = cfg.get("frontend_log_file", "./logs/databridge_frontend.log")
    fe_abs = os.path.abspath(fe_log)
    try:
        os.makedirs(os.path.dirname(fe_abs), exist_ok=True)
        with open(fe_abs, "a", encoding="utf-8") as f:
            ts = _t.strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] {level:<8} {page} — {msg}" + (f" | {detail}" if detail else "") + "\n")
    except Exception as e:
        logger.warning("프론트 로그 파일 기록 실패: %s", e)
    return {"ok": True}


@router.post("/log-rotate")
def rotate_log():
    """현재 로그 파일을 타임스탬프로 백업하고 새 파일로 재시작"""
    import shutil, time as _t
    cfg      = _cfg()
    ts       = _t.strftime("%Y%m%d_%H%M%S")
    backups  = []

    # 백엔드 로그 rotate
    be_log   = cfg.get("backend_log_file", "./logs/databridge_backend.log")
    be_abs   = os.path.abspath(be_log)
    be_bak   = be_abs.replace(".log", f"_{ts}.log")
    try:
        # 핸들러 먼저 닫기
        root = logging.getLogger()
        for h in root.handlers[:]:
            try: h.flush(); h.close()
            except: pass
            root.removeHandler(h)
        if os.path.exists(be_abs):
            shutil.copy2(be_abs, be_bak)
            backups.append(be_bak)
        # 새 파일로 시작
        os.makedirs(os.path.dirname(be_abs), exist_ok=True)
        with open(be_abs, "w", encoding="utf-8") as f:
            f.write(f"[{_t.strftime('%Y-%m-%d %H:%M:%S')}] INFO     root — 로그 재시작 완료. 백업: {be_bak}\n")
    except Exception as e:
        pass

    # 프론트엔드 로그 rotate
    fe_log   = cfg.get("frontend_log_file", "./logs/databridge_frontend.log")
    fe_abs   = os.path.abspath(fe_log)
    fe_bak   = fe_abs.replace(".log", f"_{ts}.log")
    try:
        if os.path.exists(fe_abs):
            shutil.copy2(fe_abs, fe_bak)
            backups.append(fe_bak)
            os.makedirs(os.path.dirname(fe_abs), exist_ok=True)
            with open(fe_abs, "w", encoding="utf-8") as f:
                f.write(f"[{_t.strftime('%Y-%m-%d %H:%M:%S')}] INFO     frontend — 로그 재시작 완료. 백업: {fe_bak}\n")
    except Exception as e:
        pass

    # 로거 재초기화
    try:
        _setup_logging(cfg)
        logging.info("로그 재시작 완료 (ts=%s)", ts)
        return {"ok": True, "backup": be_bak, "backups": backups, "new_file": be_abs, "ts": ts}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/log-test")
def test_log(body: dict):
    """백엔드 로그 테스트 기록"""
    import time as _t
    cfg    = _cfg()
    source = body.get("source", "backend")
    level  = body.get("level", "INFO").upper()
    msg    = body.get("message", "로그 테스트")
    page   = body.get("page", "Settings")

    lvl = getattr(logging, level, logging.INFO)

    if source == "backend":
        logger = logging.getLogger("databridge.backend")
        logger.log(lvl, "[PAGE:%s] %s", page, msg)
        return {"ok": True, "source": "backend", "level": level}
    else:
        # 프론트엔드 로그 파일에 직접 기록
        fe_log  = cfg.get("frontend_log_file", "./logs/databridge_frontend.log")
        fe_abs  = os.path.abspath(fe_log)
        try:
            os.makedirs(os.path.dirname(fe_abs), exist_ok=True)
            with open(fe_abs, "a", encoding="utf-8") as f:
                ts = _t.strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{ts}] {level:<8} {page} — {msg}\n")
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "source": "frontend", "level": level}
