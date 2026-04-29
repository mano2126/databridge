"""
app/api/routes/cdc.py
데이터 동기화 API 엔드포인트.

⚠ 정직화 (v8+):
  기존 'CDC'라는 이름의 기능은 실제로는 **timestamp 기반 증분 동기화**였음.
  이번 버전부터 다음과 같이 구분:
    - mode="incremental" : 기존 CDC 기능 (timestamp 폴링, 기본값)
    - mode="binlog_cdc"  : 진짜 CDC — MySQL binlog 기반 (신규)

  API 경로는 하위 호환을 위해 /cdc/* 유지.
  UI는 "증분 동기화" / "CDC (binlog)"로 명확히 표기.
"""
import uuid
from fastapi import APIRouter, HTTPException, Depends
from app.core.cdc_engine import (
    start_cdc, stop_cdc, get_cdc_status, get_all_cdc_status,
    get_cdc_state, reset_table_sync,
    list_cdc_configs, save_cdc_config, delete_cdc_config,
)
from app.core import binlog_cdc, pg_cdc, mssql_cdc
from app.core.sync_modes import (
    list_modes, get_mode_info, is_cdc_supported_for, get_cdc_engine_for,
)

router = APIRouter()


# v9 패치 #54: 공용 비밀번호 해결 헬퍼
def _resolve_conn_password(conn_info: dict, side: str = "source") -> dict:
    """
    conn_info["password"] 가 마스크/암호문일 수 있으므로 평문으로 변환.
    프론트가 프로파일에서 로드한 conn_info 는 password 가 '●●●●●●●●' 마스크임.
    이걸 pymysql 에 넘기면 latin-1 인코딩 실패.

    원본 dict 을 수정 + 반환 (inplace).
    """
    try:
        from app.core.password_resolver import resolve_password
        if conn_info.get("password"):
            conn_info["password"] = resolve_password(
                conn_info["password"],
                profile_id=conn_info.get("profile_id"),
                side=side,
                host=conn_info.get("host"),
                username=conn_info.get("username"),
                database=conn_info.get("database"),
            )
    except Exception as _rpe:
        import logging
        logging.getLogger("databridge.cdc").warning(
            "비밀번호 해결 실패 (원본 사용): %s", _rpe)
    return conn_info


# ── CDC 엔진 디스패치 헬퍼 ────────────────────────────────

_CDC_ENGINES = {
    "binlog_cdc": {
        "start":   lambda cid, cfg: binlog_cdc.start_binlog_cdc(cid, cfg),
        "stop":    lambda cid: binlog_cdc.stop_binlog_cdc(cid),
        "status":  lambda cid: binlog_cdc.get_binlog_cdc_status(cid),
        "all":     lambda: binlog_cdc.get_all_binlog_cdc_status(),
        "available": lambda: binlog_cdc.is_available(),
    },
    "pg_cdc": {
        "start":   lambda cid, cfg: pg_cdc.start_pg_cdc(cid, cfg),
        "stop":    lambda cid: pg_cdc.stop_pg_cdc(cid),
        "status":  lambda cid: pg_cdc.get_pg_cdc_status(cid),
        "all":     lambda: pg_cdc.get_all_pg_cdc_status(),
        "available": lambda: pg_cdc.is_available(),
    },
    "mssql_cdc": {
        "start":   lambda cid, cfg: mssql_cdc.start_mssql_cdc(cid, cfg),
        "stop":    lambda cid: mssql_cdc.stop_mssql_cdc(cid),
        "status":  lambda cid: mssql_cdc.get_mssql_cdc_status(cid),
        "all":     lambda: mssql_cdc.get_all_mssql_cdc_status(),
        "available": lambda: mssql_cdc.is_available(),
    },
}


def _resolve_cdc_mode(config: dict) -> str:
    """
    config에서 mode를 결정.
    - mode 명시되어 있으면 그대로
    - "cdc" 같이 모호하면 소스 DB에서 자동 선택
    - 아무것도 없으면 incremental
    """
    mode = (config.get("mode") or "").lower().strip()
    if mode in ("incremental", "binlog_cdc", "pg_cdc", "mssql_cdc"):
        return mode
    if mode in ("cdc", "auto"):
        # 소스 DB 기반 자동 선택
        src_db = (config.get("src_conn", {}).get("db_type") or "").lower()
        auto = get_cdc_engine_for(src_db)
        if auto:
            return auto
        raise HTTPException(
            400,
            f"소스 DB '{src_db}' 에 대한 CDC 엔진이 없습니다. "
            f"지원: MySQL(binlog_cdc), PostgreSQL(pg_cdc), SQL Server(mssql_cdc). "
            f"incremental 모드를 사용하거나 mode를 명시하세요."
        )
    return "incremental"


# ── 모드 정보 ──────────────────────────────────────────────

@router.get("/modes")
def get_sync_modes():
    """
    지원하는 동기화 모드 전체 목록 + 엔진 가용성.
    프론트에서 Job Wizard 드롭다운 구성에 사용.
    """
    return {
        "modes": list_modes(),
        "engines_available": {
            "binlog_cdc": binlog_cdc.is_available(),
            "pg_cdc":     pg_cdc.is_available(),
            "mssql_cdc":  mssql_cdc.is_available(),
        },
    }


@router.get("/modes/{mode_key}")
def get_sync_mode(mode_key: str):
    """특정 모드 상세 정보"""
    info = get_mode_info(mode_key)
    if not info:
        raise HTTPException(404, f"알 수 없는 모드: {mode_key}")
    return {
        "key":           info.key,
        "display_name":  info.display_name,
        "english_name":  info.english_name,
        "description":   info.description,
        "mechanism":     info.mechanism,
        "best_for":      info.best_for,
        "limitations":   info.limitations,
        "supported_dbs": info.supported_dbs,
        "latency":       info.latency,
    }


# ── 진단 엔드포인트 ─────────────────────────────────────

@router.post("/diagnose/mssql")
def diagnose_mssql_cdc(body: dict):
    """
    MSSQL CDC 설정 진단 — admin이 CDC 시작 전에 환경 확인.
    body: { src_conn: {...}, tables: ["t1","t2"] }
    """
    src = body.get("src_conn", {})
    tables = body.get("tables", [])
    if not src or not tables:
        raise HTTPException(400, "src_conn + tables 필수")
    return mssql_cdc.diagnose_cdc_setup(src, tables)


# ── CDC 설정 CRUD ────────────────────────────────────────────────

@router.get("/configs")
def list_configs():
    """저장된 CDC 설정 목록"""
    return list_cdc_configs()


def _resolve_config_passwords(body: dict) -> None:
    """
    v9 패치 #61: CDC 설정 저장/수정 시 비밀번호 마스크/암호문 → 평문으로 미리 해결.
    이 시점에 resolve 해두지 않으면 나중에 스케줄 실행 시 (원본 프로파일이 삭제됐다면)
    복원 불가능해지고 latin-1 오류 발생.
    """
    for _side, _ci_key in [("source","src_conn"), ("target","tgt_conn")]:
        _ci = body.get(_ci_key) or {}
        if _ci.get("password"):
            try:
                from app.core.password_resolver import resolve_password
                _ci["password"] = resolve_password(
                    _ci["password"],
                    profile_id=_ci.get("profile_id"),
                    side=_side,
                    host=_ci.get("host"),
                    username=_ci.get("username"),
                    database=_ci.get("database"),
                )
            except Exception as _rpe:
                import logging
                logging.getLogger("databridge.cdc").warning(
                    "CDC 설정 저장 시 비밀번호 해결 실패: %s", _rpe)


@router.post("/configs")
def create_config(body: dict):
    """CDC 설정 저장"""
    # v9 패치 #56: '__new__' 는 프론트 임시 마커 — 실제 ID 로 사용 금지
    raw_id = body.get("id")
    if raw_id in (None, "", "__new__"):
        config_id = str(uuid.uuid4())[:8]
    else:
        config_id = raw_id
    body["id"] = config_id  # payload 에도 올바른 ID 반영
    # v9 패치 #61: 비밀번호 미리 평문화
    _resolve_config_passwords(body)
    save_cdc_config(config_id, body)
    return {"ok": True, "id": config_id}


@router.put("/configs/{config_id}")
def update_config(config_id: str, body: dict):
    """CDC 설정 수정"""
    # v9 패치 #56: '__new__' ID 로 PUT 이 오면 신규 생성으로 처리
    if config_id == "__new__":
        config_id = str(uuid.uuid4())[:8]
        body["id"] = config_id
    # v9 패치 #61: 비밀번호 미리 평문화
    _resolve_config_passwords(body)
    save_cdc_config(config_id, body)
    return {"ok": True, "id": config_id}


@router.delete("/configs/{config_id}")
def delete_config(config_id: str):
    """CDC 설정 삭제"""
    delete_cdc_config(config_id)
    return {"ok": True}


@router.post("/configs/cleanup-orphan")
def cleanup_orphan_configs():
    """
    v9 패치 #56: 잘못된 ID ('__new__' 등) 로 저장된 설정을 정리.
    CIO 가 "편집 시 카드 2개" 버그로 인해 __new__ ID 로 저장된 설정이 있을 수 있음.
    """
    from app.core.store import Store
    cfg_store = Store("cdc_configs")
    removed = []
    for key in list(cfg_store.all().keys()):
        if key in ("__new__", None, ""):
            cfg_store.delete(key)
            removed.append(key)
    return {"ok": True, "removed": removed}


@router.post("/configs/resolve-passwords")
def resolve_all_config_passwords():
    """
    v9 패치 #61: 저장된 모든 CDC 설정의 비밀번호를 마스크/암호문 → 평문으로 일괄 해결.
    (이전 버전의 설정들은 마스크 그대로 저장돼있어 스케줄 실행 시 latin-1 오류 발생)
    """
    from app.core.store import Store
    cfg_store = Store("cdc_configs")
    resolved = []
    for key, cfg in list(cfg_store.all().items()):
        if not isinstance(cfg, dict):
            continue
        changed = False
        for _side, _ci_key in [("source","src_conn"), ("target","tgt_conn")]:
            _ci = cfg.get(_ci_key) or {}
            _pw = _ci.get("password", "")
            if not _pw:
                continue
            try:
                from app.core.password_resolver import resolve_password
                _new = resolve_password(
                    _pw,
                    profile_id=_ci.get("profile_id"),
                    side=_side,
                    host=_ci.get("host"),
                    username=_ci.get("username"),
                    database=_ci.get("database"),
                )
                if _new != _pw:
                    _ci["password"] = _new
                    changed = True
            except Exception:
                pass
        if changed:
            cfg_store.set(key, cfg)
            resolved.append(key)
    return {"ok": True, "resolved": resolved}


# ── CDC 실행 ─────────────────────────────────────────────────────

@router.post("/run/{config_id}")
def run_cdc_by_config(config_id: str):
    """저장된 설정으로 동기화 실행. config.mode 에 따라 엔진 자동 선택."""
    from app.core.store import Store
    cfg_store = Store("cdc_configs")
    config = cfg_store.get(config_id)
    if not config:
        raise HTTPException(404, f"설정 없음: {config_id}")

    cdc_id = f"{config_id}_{uuid.uuid4().hex[:6]}"
    mode = _resolve_cdc_mode(config)

    # v9 패치 #54: 저장된 설정 속 소스·타겟 비밀번호 해결 (마스크·암호문 → 평문)
    if config.get("src_conn"):
        _resolve_conn_password(config["src_conn"], side="source")
    if config.get("tgt_conn"):
        _resolve_conn_password(config["tgt_conn"], side="target")

    if mode == "incremental":
        start_cdc(cdc_id, config)
        return {"ok": True, "cdc_id": cdc_id, "mode": "incremental"}

    engine = _CDC_ENGINES.get(mode)
    if not engine:
        raise HTTPException(400, f"알 수 없는 모드: {mode}")
    result = engine["start"](cdc_id, config)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", f"{mode} 시작 실패"))
    return result


@router.post("/run")
def run_cdc_direct(body: dict):
    """
    설정 저장 없이 바로 동기화 실행.
    body.mode: "incremental" | "binlog_cdc" | "pg_cdc" | "mssql_cdc" | "cdc"(자동선택) | "auto"(자동선택)
    """
    cdc_id = body.get("cdc_id") or str(uuid.uuid4())[:8]
    mode = _resolve_cdc_mode(body)

    # v9 패치 #54: 소스·타겟 비밀번호 해결 (마스크 → 평문)
    if body.get("src_conn"):
        _resolve_conn_password(body["src_conn"], side="source")
    if body.get("tgt_conn"):
        _resolve_conn_password(body["tgt_conn"], side="target")

    if mode == "incremental":
        start_cdc(cdc_id, body)
        return {"ok": True, "cdc_id": cdc_id, "mode": "incremental"}

    engine = _CDC_ENGINES.get(mode)
    if not engine:
        raise HTTPException(400, f"알 수 없는 모드: {mode}")
    if not engine["available"]():
        raise HTTPException(
            400,
            f"{mode} 엔진 비활성 (의존성 라이브러리 미설치). "
            f"binlog_cdc: mysql-replication, pg_cdc: psycopg2-binary, mssql_cdc: pyodbc"
        )
    result = engine["start"](cdc_id, body)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", f"{mode} 시작 실패"))
    return result


@router.post("/stop/{cdc_id}")
def stop(cdc_id: str):
    """동기화 중단 — 3개 CDC 엔진 + incremental 모두 검사"""
    # 각 엔진에서 찾아봄
    for mode_key, engine in _CDC_ENGINES.items():
        if engine["status"](cdc_id) is not None:
            r = engine["stop"](cdc_id)
            return {**r, "mode": mode_key}
    # incremental 폴백
    return {**stop_cdc(cdc_id), "mode": "incremental"}


# ── 상태 조회 ────────────────────────────────────────────────

@router.get("/status")
def all_status():
    """실행 중인 모든 동기화 작업 — 4개 엔진 통합"""
    result = {}
    # incremental
    for k, v in get_all_cdc_status().items():
        result[k] = {**v, "mode": "incremental"}
    # 3개 CDC 엔진
    for mode_key, engine in _CDC_ENGINES.items():
        for k, v in engine["all"]().items():
            result[k] = {**v, "mode": mode_key}
    return result


@router.get("/status/{cdc_id}")
def one_status(cdc_id: str):
    """특정 동기화 작업 상태 — 4개 엔진 자동 탐색"""
    # 3개 CDC 엔진에서 먼저 탐색
    for mode_key, engine in _CDC_ENGINES.items():
        s = engine["status"](cdc_id)
        if s is not None:
            return {**s, "mode": mode_key}
    # incremental 폴백
    s = get_cdc_status(cdc_id)
    if s is None:
        raise HTTPException(404, "동기화 작업 없음")
    return {**s, "mode": "incremental"}


# ── last_sync 상태 관리 ──────────────────────────────────────────

@router.get("/state")
def get_state(src_host: str, src_db: str, tgt_host: str, tgt_db: str):
    """테이블별 last_sync 조회"""
    state_key = f"{src_host}:{src_db}→{tgt_host}:{tgt_db}"
    return get_cdc_state(state_key)


@router.delete("/state/table")
def reset_table(src_host: str, src_db: str, tgt_host: str,
                tgt_db: str, table: str):
    """특정 테이블 last_sync 초기화 (다음 실행 시 전체 재동기화)"""
    state_key = f"{src_host}:{src_db}→{tgt_host}:{tgt_db}"
    reset_table_sync(state_key, table)
    return {"ok": True, "table": table}


# ── 타임스탬프 컬럼 자동 감지 (힌트 제공) ────────────────────────

@router.post("/detect-ts-columns")
def detect_ts_columns(body: dict):
    """
    소스 DB의 테이블별 타임스탬프 후보 컬럼 자동 감지
    사용자가 직접 선택할 수 있도록 후보 목록 반환
    """
    conn_info = body.get("conn_info", {})
    tables    = body.get("tables", [])

    # 타임스탬프 컬럼으로 적합한 패턴 (우선순위 순)
    TS_PATTERNS = [
        "upd_datm", "upd_date", "updated_at", "update_dt",
        "mod_datm", "mod_date", "modified_at",
        "rec_datm", "regi_datm", "reg_datm",
        "created_at", "create_dt", "ins_datm",
        "changed_at", "change_datm",
        "log_datm", "login_datm",
    ]

    try:
        from app.core.cdc_engine import _connect
        _resolve_conn_password(conn_info, side="source")   # v9 #54
        conn    = _connect(conn_info)
        db_type = conn_info.get("db_type", "mysql").lower()
        database= conn_info.get("database", "")
        cur     = conn.cursor()

        result = []
        for table in tables:
            # 테이블의 datetime 계열 컬럼 조회
            if db_type in ("mssql", "sqlserver", "azure"):
                cur.execute("""
                    SELECT COLUMN_NAME, DATA_TYPE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = ? AND DATA_TYPE IN
                      ('datetime','datetime2','date','smalldatetime','datetimeoffset')
                    ORDER BY ORDINAL_POSITION
                """, [table])
            elif db_type in ("mysql", "aurora", "mariadb"):
                cur.execute("""
                    SELECT COLUMN_NAME, DATA_TYPE
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                      AND DATA_TYPE IN ('datetime','date','timestamp')
                    ORDER BY ORDINAL_POSITION
                """, [database, table])
            elif db_type in ("postgresql", "postgres"):
                cur.execute("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                      AND data_type LIKE '%%timestamp%%'
                    ORDER BY ordinal_position
                """, [table])

            dt_cols = [(r[0], r[1]) for r in cur.fetchall()]

            # 우선순위에 따라 추천 컬럼 결정
            candidates = [col for col, _ in dt_cols]
            recommended = None
            for pat in TS_PATTERNS:
                match = next((c for c in candidates if c.lower() == pat.lower()), None)
                if match:
                    recommended = match
                    break

            result.append({
                "table":       table,
                "candidates":  [{"col": c, "type": t} for c, t in dt_cols],
                "recommended": recommended,
            })

        conn.close()
        return {"ok": True, "tables": result}

    except Exception as e:
        raise HTTPException(500, str(e))


# ── 소스 DB 전체 테이블 스캔 (목록 + PK + 타임스탬프 일괄감지) ──

TS_PRIORITY = [
    "upd_datm","upd_date","updated_at","update_dt",
    "mod_datm","mod_date","modified_at","modify_dt",
    "rec_datm","regi_datm","reg_datm","regist_datm",
    "created_at","create_dt","ins_datm","insert_dt",
    "changed_at","change_datm","chg_datm",
    "log_datm","login_datm","proc_datm","req_datm",
]

def _recommend_ts(candidates: list) -> str | None:
    lower_map = {c.lower(): c for c in candidates}
    for pat in TS_PRIORITY:
        if pat in lower_map:
            return lower_map[pat]
    return candidates[0] if candidates else None

def _recommend_strategy(pk_cols: list, ts_col: str | None,
                         table_name: str) -> str:
    if not ts_col:
        return "full"
    name_lower = table_name.lower()
    # 이력/로그성 테이블 키워드 → append
    append_keywords = ["hist","log","record","rec","listen","login",
                       "audit","event","result","excel","pass_change"]
    if any(k in name_lower for k in append_keywords):
        return "append"
    # PK 있고 마스터성 → upsert
    if pk_cols:
        return "upsert"
    return "append"

@router.post("/scan-tables")
def scan_tables(body: dict):
    """
    소스 DB 전체 테이블 스캔
    - 테이블 목록 조회
    - 각 테이블의 PK 컬럼, 타임스탬프 후보 컬럼 감지
    - 전략 추천값 반환
    - 저장된 CDC 설정과 병합하여 반환
    """
    conn_info  = body.get("conn_info", {})
    tgt_conn_info = body.get("tgt_conn_info", {})   # v9 #60: 타겟 PK 폴백용
    saved_cfg  = body.get("saved_tables", {})  # {table: {ts_col, extra_where, strategy}}
    page       = int(body.get("page", 1))
    page_size  = int(body.get("page_size", 10))
    search     = body.get("search", "").strip().lower()
    filter_by  = body.get("filter", "all")  # all | recommended | unset | excluded

    try:
        from app.core.cdc_engine import _connect, _get_pk_columns
        # v9 패치 #54: 비밀번호 해결 (마스크 → 평문)
        _resolve_conn_password(conn_info, side="source")
        conn     = _connect(conn_info)
        db_type  = conn_info.get("db_type", "mssql").lower()
        database = conn_info.get("database", "")
        cur      = conn.cursor()

        # v9 #60: 타겟 연결 준비 (PK 폴백용) — 실패해도 스캔은 계속
        tgt_conn = None
        tgt_db_type = ""
        tgt_database = ""
        if tgt_conn_info and tgt_conn_info.get("host"):
            try:
                _resolve_conn_password(tgt_conn_info, side="target")
                tgt_conn = _connect(tgt_conn_info)
                tgt_db_type = tgt_conn_info.get("db_type", "").lower()
                tgt_database = tgt_conn_info.get("database", "")
            except Exception as _te:
                import logging
                logging.getLogger("databridge.cdc").warning(
                    "타겟 연결 실패 (PK 폴백 비활성): %s", _te)

        # ── 1. 전체 테이블 목록 ───────────────────────────────
        if db_type in ("mssql", "sqlserver", "azure"):
            cur.execute("""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE='BASE TABLE'
                  AND TABLE_CATALOG=?
                ORDER BY TABLE_NAME
            """, [database])
        elif db_type in ("mysql", "aurora", "mariadb"):
            cur.execute("""
                SELECT TABLE_NAME
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE'
                ORDER BY TABLE_NAME
            """, [database])
        elif db_type in ("postgresql", "postgres"):
            cur.execute("""
                SELECT tablename FROM pg_tables
                WHERE schemaname='public' ORDER BY tablename
            """)

        all_tables = [r[0] for r in cur.fetchall()]

        # ── 2. 테이블별 분석 ─────────────────────────────────
        # v9 #60: 타겟 PK 조회 헬퍼 (소스 PK 없는 테이블용)
        def _pk_from_tgt(tbl):
            if not tgt_conn or not tgt_db_type:
                return []
            try:
                tcur = tgt_conn.cursor()
                if tgt_db_type in ("mssql", "sqlserver", "azure"):
                    tcur.execute("""
                        SELECT c.COLUMN_NAME
                        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE c
                          ON tc.CONSTRAINT_NAME=c.CONSTRAINT_NAME
                        WHERE tc.TABLE_NAME=? AND tc.CONSTRAINT_TYPE='PRIMARY KEY'
                        ORDER BY c.ORDINAL_POSITION
                    """, [tbl])
                elif tgt_db_type in ("mysql", "aurora", "mariadb"):
                    tcur.execute("""
                        SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE
                        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
                          AND CONSTRAINT_NAME='PRIMARY'
                        ORDER BY ORDINAL_POSITION
                    """, [tgt_database, tbl])
                else:
                    return []
                return [r[0] for r in tcur.fetchall()]
            except Exception:
                return []

        results = []
        for tbl in all_tables:
            # PK 감지 (소스 → 타겟 폴백)
            try:
                pk_cols = _get_pk_columns(conn, db_type, database, tbl)
            except Exception:
                pk_cols = []
            if not pk_cols:
                tgt_pk = _pk_from_tgt(tbl)
                if tgt_pk:
                    pk_cols = tgt_pk

            # 타임스탬프 컬럼 감지
            try:
                if db_type in ("mssql", "sqlserver", "azure"):
                    cur.execute("""
                        SELECT COLUMN_NAME, DATA_TYPE
                        FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_NAME=? AND TABLE_CATALOG=?
                          AND DATA_TYPE IN
                          ('datetime','datetime2','date','smalldatetime','datetimeoffset')
                        ORDER BY ORDINAL_POSITION
                    """, [tbl, database])
                elif db_type in ("mysql", "aurora", "mariadb"):
                    cur.execute("""
                        SELECT COLUMN_NAME, DATA_TYPE
                        FROM information_schema.COLUMNS
                        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
                          AND DATA_TYPE IN ('datetime','date','timestamp')
                        ORDER BY ORDINAL_POSITION
                    """, [database, tbl])
                elif db_type in ("postgresql", "postgres"):
                    cur.execute("""
                        SELECT column_name, data_type
                        FROM information_schema.columns
                        WHERE table_schema='public' AND table_name=%s
                          AND data_type LIKE '%%timestamp%%'
                        ORDER BY ordinal_position
                    """, [tbl])
                ts_candidates = [r[0] for r in cur.fetchall()]
            except Exception:
                ts_candidates = []

            recommended_ts = _recommend_ts(ts_candidates)

            # 저장된 설정 있으면 우선 사용
            saved = saved_cfg.get(tbl, {})
            ts_col     = saved.get("ts_col")     if saved else recommended_ts
            extra_where= saved.get("extra_where","") if saved else ""
            strategy   = saved.get("strategy")   if saved else _recommend_strategy(pk_cols, ts_col, tbl)
            is_saved   = bool(saved)
            excluded   = saved.get("excluded", False)

            # 상태 분류
            if excluded:
                status = "excluded"
            elif is_saved:
                status = "saved"
            elif recommended_ts:
                status = "recommended"
            else:
                status = "unset"

            results.append({
                "table":         tbl,
                "pk_cols":       pk_cols,
                "ts_candidates": ts_candidates,
                "recommended_ts": recommended_ts,
                "ts_col":        ts_col,
                "extra_where":   extra_where,
                "strategy":      strategy,
                "status":        status,
                "is_saved":      is_saved,
                "excluded":      excluded,
            })

        conn.close()
        if tgt_conn:
            try: tgt_conn.close()
            except Exception: pass

        # ── 3. 필터 + 검색 ───────────────────────────────────
        if search:
            results = [r for r in results if search in r["table"].lower()]
        if filter_by == "recommended":
            results = [r for r in results if r["status"] in ("recommended","saved")]
        elif filter_by == "unset":
            results = [r for r in results if r["status"] == "unset"]
        elif filter_by == "excluded":
            results = [r for r in results if r["excluded"]]

        total = len(results)

        # 상태별 카운트
        counts = {
            "all":         len([r for r in results]),
            "recommended": len([r for r in results if r["status"] in ("recommended","saved")]),
            "unset":       len([r for r in results if r["status"] == "unset"]),
            "excluded":    len([r for r in results if r["excluded"]]),
        }

        # ── 4. 페이징 ────────────────────────────────────────
        start  = (page - 1) * page_size
        paged  = results[start : start + page_size]

        return {
            "ok":        True,
            "total":     total,
            "page":      page,
            "page_size": page_size,
            "counts":    counts,
            "tables":    paged,
        }

    except Exception as e:
        # v9 패치 #53: latin-1 오류 진단용 상세 traceback
        import traceback, logging
        _lg = logging.getLogger("databridge.cdc")
        _tb = traceback.format_exc()
        _lg.error("scan_tables 오류:\n%s", _tb)
        _err_msg = f"{type(e).__name__}: {str(e)}"
        _last_frames = _tb.strip().split('\n')
        _origin = ""
        for _line in reversed(_last_frames):
            if 'File "' in _line and 'site-packages' not in _line:
                _origin = _line.strip()
                break
        if _origin:
            _err_msg += f"\n발생 위치: {_origin}"
        raise HTTPException(500, _err_msg)


# ── 테이블 전체 컬럼 목록 조회 ────────────────────────────────────

@router.post("/table-columns")
def get_table_columns(body: dict):
    """테이블의 전체 컬럼 목록 반환 (컬럼 피커용)"""
    conn_info = body.get("conn_info", {})
    table     = body.get("table", "")
    if not table:
        raise HTTPException(400, "table 필수")
    try:
        from app.core.cdc_engine import _connect
        _resolve_conn_password(conn_info, side="source")   # v9 #54
        conn     = _connect(conn_info)
        db_type  = conn_info.get("db_type", "mssql").lower()
        database = conn_info.get("database", "")
        cur      = conn.cursor()

        if db_type in ("mssql", "sqlserver", "azure"):
            cur.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE,
                       COALESCE(CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, 0) AS col_len
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME=? AND TABLE_CATALOG=?
                ORDER BY ORDINAL_POSITION
            """, [table, database])
        elif db_type in ("mysql", "aurora", "mariadb"):
            cur.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE,
                       COALESCE(CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, 0) AS col_len
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
                ORDER BY ORDINAL_POSITION
            """, [database, table])
        elif db_type in ("postgresql", "postgres"):
            cur.execute("""
                SELECT column_name, data_type, is_nullable, 0
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name=%s
                ORDER BY ordinal_position
            """, [table])

        columns = [
            {"name": r[0], "type": r[1], "nullable": r[2], "len": r[3] or 0}
            for r in cur.fetchall()
        ]
        conn.close()
        return {"ok": True, "table": table, "columns": columns}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── 테이블 건수 조회 ──────────────────────────────────────────────

@router.post("/table-count")
def get_table_count(body: dict):
    """테이블 건수 반환 — 통계 기반 빠른 조회 후 폴백"""
    conn_info = body.get("conn_info", {})
    table     = body.get("table", "")
    if not table:
        raise HTTPException(400, "table 필수")
    try:
        from app.core.cdc_engine import _connect
        _resolve_conn_password(conn_info, side="source")   # v9 #54
        conn     = _connect(conn_info)
        db_type  = conn_info.get("db_type", "mssql").lower()
        database = conn_info.get("database", "")
        cur      = conn.cursor()
        count    = None

        if db_type in ("mssql", "sqlserver", "azure"):
            # 통계 기반 빠른 조회 (대용량 테이블도 즉시)
            try:
                cur.execute("""
                    SELECT SUM(p.rows)
                    FROM sys.tables t
                    JOIN sys.partitions p ON t.object_id = p.object_id
                    WHERE t.name = ? AND p.index_id IN (0,1)
                """, [table])
                row = cur.fetchone()
                if row and row[0] is not None:
                    count = int(row[0])
            except Exception:
                pass
            # 통계 실패 시 COUNT(*) 폴백
            if count is None:
                cur.execute(f"SELECT COUNT(*) FROM [{table}] WITH(NOLOCK)")
                count = cur.fetchone()[0]

        elif db_type in ("mysql", "aurora", "mariadb"):
            # information_schema 통계 (빠름, 근사값)
            try:
                cur.execute("""
                    SELECT TABLE_ROWS FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
                """, [database, table])
                row = cur.fetchone()
                if row and row[0] is not None:
                    count = int(row[0])
            except Exception:
                pass
            if count is None:
                cur.execute(f"SELECT COUNT(*) FROM `{table}`")
                count = cur.fetchone()[0]

        elif db_type in ("postgresql", "postgres"):
            # pg_stat 통계
            try:
                cur.execute("""
                    SELECT n_live_tup FROM pg_stat_user_tables
                    WHERE relname=%s
                """, [table])
                row = cur.fetchone()
                if row and row[0] is not None:
                    count = int(row[0])
            except Exception:
                pass
            if count is None:
                cur.execute(f'SELECT COUNT(*) FROM "{table}"')
                count = cur.fetchone()[0]

        conn.close()
        return {"ok": True, "table": table, "count": count or 0}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── 테스트 SQL 파일 생성 및 다운로드 ──────────────────────────────

@router.post("/generate-test-sql")
def generate_test_sql(body: dict):
    """
    기준 컬럼이 있는 테이블 중 최대 5개를 선택해
    INSERT 100건 + DELETE + 확인 SELECT 쿼리를 SQL 파일로 반환
    """
    conn_info   = body.get("conn_info", {})
    tables_cfg  = body.get("tables", [])      # [{table, ts_col, pk_cols, strategy}]
    max_tables  = body.get("max_tables", 5)
    rows_per_tbl= body.get("rows_per_table", 100)

    db_type = conn_info.get("db_type", "mssql").lower()
    db_name = conn_info.get("database", "DB")

    def q(name):  # 인용부호
        if db_type in ("mssql", "sqlserver", "azure"): return f"[{name}]"
        if db_type in ("postgresql", "postgres"):       return f'"{name}"'
        return f"`{name}`"

    def ph():     # 날짜 포맷
        return "GETDATE()" if db_type in ("mssql","sqlserver","azure") else "NOW()"

    # 기준 컬럼 있는 테이블만 최대 5개 선택
    ts_tables = [t for t in tables_cfg if t.get("ts_col")][:max_tables]

    if not ts_tables:
        raise HTTPException(400, "기준 컬럼이 설정된 테이블이 없습니다")

    # 컬럼 정보 조회
    try:
        from app.core.cdc_engine import _connect
        _resolve_conn_password(conn_info, side="source")   # v9 #54
        conn = _connect(conn_info)
        cur  = conn.cursor()

        def get_cols(table):
            if db_type in ("mssql", "sqlserver", "azure"):
                cur.execute("""
                    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE,
                           COLUMNPROPERTY(OBJECT_ID(TABLE_NAME), COLUMN_NAME, 'IsIdentity') as is_identity,
                           ISNULL(CHARACTER_MAXIMUM_LENGTH, 0) as col_len
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME=? AND TABLE_CATALOG=?
                    ORDER BY ORDINAL_POSITION
                """, [table, conn_info.get("database","")])
            elif db_type in ("mysql","aurora","mariadb"):
                cur.execute("""
                    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, EXTRA,
                           IFNULL(CHARACTER_MAXIMUM_LENGTH, 0) as col_len
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
                    ORDER BY ORDINAL_POSITION
                """, [conn_info.get("database",""), table])
            return cur.fetchall()

        lines = []
        lines.append(f"-- ============================================================")
        lines.append(f"-- DataBridge CDC 테스트 SQL — {db_name}")
        lines.append(f"-- 생성일시: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"-- 대상 테이블: {len(ts_tables)}개 / 테이블당 {rows_per_tbl}건")
        lines.append(f"-- ============================================================")
        lines.append(f"-- ⚠ 주의: 소스 DB({db_type.upper()})에서 실행하세요!")
        lines.append(f"-- ⚠ 실행 전 SELECT로 반드시 확인하세요!")
        lines.append("")

        for tbl_cfg in ts_tables:
            table  = tbl_cfg["table"]
            ts_col = tbl_cfg["ts_col"]
            pk_cols = tbl_cfg.get("pk_cols", [])

            # pk_cols 없으면 DB에서 직접 조회
            if not pk_cols:
                try:
                    if db_type in ("mssql","sqlserver","azure"):
                        cur.execute("""
                            SELECT c.COLUMN_NAME
                            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                            JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE c
                              ON tc.CONSTRAINT_NAME=c.CONSTRAINT_NAME
                            WHERE tc.TABLE_NAME=? AND tc.CONSTRAINT_TYPE='PRIMARY KEY'
                        """, [table])
                        pk_cols = [r[0] for r in cur.fetchall()]
                except Exception:
                    pk_cols = []

            cols_raw = get_cols(table)
            # identity/auto_increment 컬럼 제외
            cols = []
            for r in cols_raw:
                col_name, dtype, nullable = r[0], r[1], r[2]
                is_auto = r[3] if len(r) > 3 else None
                col_len = r[4] if len(r) > 4 else 0  # CHARACTER_MAXIMUM_LENGTH
                if is_auto in (1, '1', 'auto_increment'):
                    continue
                cols.append({
                    "name": col_name, "type": dtype.lower(),
                    "nullable": nullable, "len": int(col_len or 0)
                })

            if not cols:
                continue

            # 타입별 샘플값 생성
            import random
            now_str = __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            def sample_val(c, idx):
                t   = c["type"]
                n   = c["name"]
                clen = c.get("len", 0)

                if n == ts_col:
                    if db_type in ("mssql","sqlserver","azure"):
                        return f"DATEADD(MILLISECOND, {idx} * 100, GETDATE())"
                    return f"DATE_ADD(NOW(), INTERVAL {idx * 100} MICROSECOND)"
                if n in pk_cols:
                    if 'char' in t or 'text' in t:
                        val = f"TST_{idx:04d}"
                        return f"'{val[:clen]}'" if clen > 0 else f"'{val}'"
                    return str(90000000 + idx)
                if any(x in t for x in ('int','numeric','decimal','float','double','money','bigint','smallint')):
                    return str(idx % 100 + 1)
                if any(x in t for x in ('datetime','timestamp','date','time')):
                    return f"'{now_str}'"
                if any(x in t for x in ('char','varchar','text','nchar','nvarchar','ntext')):
                    # 컬럼 길이 맞춤
                    prefix = f"T{n[:3].upper()}"  # 최대 4자
                    val = f"{prefix}{idx:03d}"     # 예: TSTA001 = 7자
                    if clen > 0 and len(val) > clen:
                        val = str(idx)[:clen]
                    return f"'{val}'"
                if any(x in t for x in ('bit','bool','tinyint')):
                    return '1'
                return 'NULL' if c["nullable"] == 'YES' else "'T'"

            col_list = ", ".join(q(c["name"]) for c in cols)

            lines.append(f"-- ============================================================")
            lines.append(f"-- 테이블: {table}  (기준컬럼: {ts_col})")
            lines.append(f"-- ============================================================")
            lines.append("")
            lines.append(f"-- [1] INSERT {rows_per_tbl}건 후 변경분 이관 테스트")
            nolock = " WITH(NOLOCK)" if db_type in ("mssql","sqlserver","azure") else ""
            lines.append(f"SELECT TOP 10 * FROM {q(table)}{nolock} ORDER BY {q(ts_col)} DESC;")
            lines.append("")

            lines.append(f"-- [1-1] INSERT ({rows_per_tbl}건) — {table}")
            if db_type in ("mssql","sqlserver","azure"):
                # PK 컬럼 파악
                pk_set = set(pk_cols)

                def mssql_val(c):
                    n, t, nl = c["name"], c["type"].lower(), c["nullable"]
                    col_len  = c.get("len", 0)

                    # @i=1: 현재, @i=2~(N-1): 현재+1초, @i=N: 현재+10초
                    if n == ts_col:
                        return "CASE WHEN @i = 1 THEN @insert_start WHEN @i = @total THEN DATEADD(SECOND, 10, @insert_start) ELSE DATEADD(SECOND, 1, @insert_start) END"

                    # 문자열 타입
                    if any(x in t for x in ("char","varchar","nchar","nvarchar","text","ntext")):
                        # PK 컬럼 → NEWID() 또는 현재시각+랜덤으로 유니크하게
                        if n in pk_set:
                            if col_len > 0 and col_len < 36:
                                # 짧은 PK: 현재시각 기반 유니크값
                                max_l = col_len
                                return "LEFT(REPLACE(CAST(NEWID() AS VARCHAR(36)),'-',''), %d)" % max_l
                            return "CAST(NEWID() AS VARCHAR(36))"  # GUID 문자열

                        # 일반 문자열 컬럼
                        prefix = n[:4].upper()
                        sample = "T_" + prefix + "_"      # 예: T_STAT_ = 8자
                        full_len = len(sample) + 3          # + 3자리 숫자
                        if col_len > 0 and full_len > col_len:
                            if col_len >= 3:
                                return "RIGHT(REPLACE(CAST(NEWID() AS VARCHAR(36)),'-',''), %d)" % col_len
                            return "LEFT(CAST(@i AS VARCHAR), %d)" % col_len
                        return "CONCAT('%s', RIGHT('000'+CAST(@i AS VARCHAR),3))" % sample

                    # 숫자 타입
                    if any(x in t for x in ("int","numeric","decimal","float","money","double","bigint","smallint")):
                        # PK 숫자 → 큰 범위 랜덤값 (중복 방지)
                        if n in pk_set:
                            return "ABS(CHECKSUM(NEWID())) % 2000000000 + @i * 1000000"
                        return "@i"

                    if any(x in t for x in ("datetime","datetime2","date","smalldatetime","datetimeoffset")):
                        return "CASE WHEN @i = 1 THEN @insert_start WHEN @i = @total THEN DATEADD(SECOND, 10, @insert_start) ELSE DATEADD(SECOND, 1, @insert_start) END"
                    if "time" in t and "datetime" not in t:
                        return "CAST(GETDATE() AS TIME)"
                    if "bit" in t:
                        return "1"
                    if "uniqueidentifier" in t:
                        return "NEWID()"
                    if "binary" in t or "varbinary" in t:
                        return "0x01"
                    return "NULL" if nl == "YES" else (
                        "LEFT(REPLACE(CAST(NEWID() AS VARCHAR(36)),'-',''), %d)" % max(col_len,1)
                        if col_len > 0 else "'T'"
                    )

                val_parts = [mssql_val(c) for c in cols]
                val_line  = ", ".join(val_parts)

                # INSERT + 확인을 같은 배치에서 처리 (@insert_start 변수 공유)
                lines.append("GO")
                lines.append("DECLARE @insert_start DATETIME = CAST(GETDATE() AT TIME ZONE 'UTC' AT TIME ZONE 'Korea Standard Time' AS DATETIME)")
                lines.append("DECLARE @total INT = %d" % rows_per_tbl)
                lines.append("DECLARE @i INT = 1")
                lines.append("WHILE @i <= @total")
                lines.append("BEGIN")
                lines.append("  INSERT INTO %s (%s)" % (q(table), col_list))
                lines.append("  VALUES (%s);" % val_line)
                lines.append("  SET @i = @i + 1")
                lines.append("END")
                lines.append("")
                lines.append(f"-- [2] INSERT 결과 확인")
                lines.append(f"-- 첫번째: @insert_start, 중간: @insert_start+1초, 마지막: @insert_start+10초")
                lines.append(f"SELECT COUNT(*) AS 삽입건수,")
                lines.append(f"       MIN({q(ts_col)}) AS 첫번째시각,")
                lines.append(f"       MAX({q(ts_col)}) AS 마지막시각,")
                lines.append(f"       DATEADD(SECOND, @total * 10, @insert_start) AS 다음테스트_기준시각")
                lines.append(f"FROM {q(table)}{nolock}")
                lines.append(f"WHERE {q(ts_col)} >= @insert_start;")
                lines.append("")
                lines.append(f"-- ※ 다음 테스트: 위 [다음테스트_기준시각] 이후로 CDC가 잡습니다")
                lines.append(f"--   cdc_state.json의 last_sync 또는 CDC 화면 기준일자를 해당 시각으로 설정하세요")
                lines.append("GO")
            else:
                # MySQL: VALUES 반복
                for i in range(1, rows_per_tbl + 1):
                    vals = ", ".join(sample_val(c, i) for c in cols)
                    lines.append(f"INSERT INTO {q(table)} ({col_list}) VALUES ({vals});")
                lines.append("")
                lines.append(f"-- [2] 이관 후 변경분 확인")
                lines.append(f"SELECT COUNT(*) AS 방금_삽입건수 FROM {q(table)} WHERE {q(ts_col)} >= NOW() - INTERVAL {rows_per_tbl + 60} SECOND;")
            lines.append("")
            lines.append("")

        # ── 모든 테이블 INSERT 완료 후 DELETE 구간 ──────────────
        lines.append("")
        lines.append("-- ============================================================")
        lines.append("-- ★ 테스트 데이터 삭제 (반복 테스트 시 — INSERT 완료 후 실행)")
        lines.append("-- ★ @del_start 에 INSERT 직전 시각을 입력하세요 (예: '2026-04-12 17:28:00')")
        lines.append("-- ★ DELETE는 주석 처리 — SELECT 확인 후 주석 해제하여 실행")
        lines.append("-- ★ 삭제 전 반드시 SELECT로 확인하세요!")
        lines.append("-- ============================================================")
        lines.append("")

        for tbl_cfg in ts_tables:
            table  = tbl_cfg["table"]
            ts_col = tbl_cfg["ts_col"]
            nolock = " WITH(NOLOCK)" if db_type in ("mssql","sqlserver","azure") else ""

            if db_type in ("mssql","sqlserver","azure"):
                lines.append("GO")
                lines.append(f"-- [{table}] 삭제 대상 확인")
                lines.append(f"-- ※ @del_start 를 INSERT 결과의 [첫번째시각] 값으로 교체하세요")
                lines.append(f"DECLARE @del_start DATETIME = '2099-01-01'  -- <- 실제 INSERT 시작 시각으로 교체")
                lines.append(f"SELECT COUNT(*) AS 삭제대상, MIN({q(ts_col)}) AS 최소, MAX({q(ts_col)}) AS 최대")
                lines.append(f"FROM {q(table)}{nolock}")
                lines.append(f"WHERE {q(ts_col)} >= @del_start;")
                lines.append("")
                lines.append(f"-- [{table}] 삭제 실행 (위 SELECT 확인 후 주석 해제)")
                lines.append(f"-- DELETE FROM {q(table)}")
                lines.append(f"-- WHERE {q(ts_col)} >= @del_start;")
            else:
                lines.append(f"-- [{table}] 삭제 대상 확인")
                lines.append(f"SET @del_start = '2099-01-01';  -- <- 실제 INSERT 시작 시각으로 교체")
                lines.append(f"SELECT COUNT(*) AS 삭제대상 FROM {q(table)}")
                lines.append(f"WHERE {q(ts_col)} >= @del_start;")
                lines.append("")
                lines.append(f"-- [{table}] 삭제 실행 (SELECT 확인 후 주석 해제)")
                lines.append(f"-- DELETE FROM {q(table)}")
                lines.append(f"-- WHERE {q(ts_col)} >= @del_start;")
            lines.append("")

        conn.close()

        sql_content = "\n".join(lines)

        from fastapi.responses import Response
        filename = f"cdc_test_{db_name}_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        return Response(
            content=sql_content.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
