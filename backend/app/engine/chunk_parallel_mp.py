"""
청크 분할 병렬 이관 — ProcessPool 버전 (v11 #1, Phase 3a Step 1)

Phase 2 ThreadPool 구현의 한계 (실측 병렬 효율 20%) 를 극복하기 위해
멀티프로세스로 GIL 을 우회한다.

설계 목표:
  - 병렬 효율 70~85% 달성 (ThreadPool 대비 3~4배)
  - 목표 속도: 15,000~25,000 rows/s (단일 4,800 대비 3~5배)
  - 기존 chunk_parallel.py (ThreadPool) 와 **공존** — A/B 비교 가능

핵심 구조:
  - 워커 함수 = 자기 완결적 모듈 레벨 함수 (pickle-safe)
  - self/engine 객체는 워커에 전달 불가 → config dict 만 전달
  - 로그/진행률 집계 = multiprocessing.Queue 기반
  - 각 워커는 자기 DB 연결을 독립 개설 (Phase 2 와 동일 패턴)

Windows spawn 모드 주의사항:
  - 모든 pickle 대상 객체는 모듈 레벨에 정의
  - lambda, closure, 인스턴스 메서드는 사용 금지
  - 워커에서 import 필요한 모듈은 워커 함수 안에서 import
"""
from __future__ import annotations
import os
import time
import threading
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Tuple

from .dialects.base import ChunkRange
from .chunk_parallel import ChunkDecision


# ──────────────────────────────────────────────────────────────
# 직렬화 가능한 워커 설정 (pickle-safe dataclass)
# ──────────────────────────────────────────────────────────────

@dataclass
class WorkerConfig:
    """
    워커 프로세스에 전달하는 **유일한** 인자.

    pickle-safe 한 순수 데이터만 포함 — 연결 객체, 로거, MigrationEngine
    등은 포함 안 됨. 워커가 필요한 건 다 여기 들어있어야 함.
    """
    # 식별
    worker_id: int
    table: str
    chunk_range_dict: Dict[str, Any]   # ChunkRange 를 dict 로 직렬화

    # DB 연결 정보
    src_db_type: str                   # 'mssql', 'mysql', ...
    src_host: str
    src_port: int
    src_username: str
    src_password: str
    src_database: str

    tgt_db_type: str
    tgt_host: str
    tgt_port: int
    tgt_username: str
    tgt_password: str
    tgt_database: str

    connect_timeout: int

    # 이관 설정
    col_names: List[str]
    cols_meta: List[Dict[str, Any]]    # 컬럼 메타 (DATA_TYPE 등 — _build_mysql_converters 용)
    select_expr: str
    insert_sql: str
    batch_size: int
    row_count: int
    loader_mode: str                   # 'auto', 'mysql_load', ...
    job_meta: Dict[str, Any]           # bulk_threshold_rows 등 loader 가 참조하는 Job 설정 일부

    # 변환 로직
    tgt_is_mysql: bool
    tgt_is_mssql: bool
    src_is_mssql: bool


# ──────────────────────────────────────────────────────────────
# 진행률/로그 이벤트 (Queue 로 전송되는 메시지)
# ──────────────────────────────────────────────────────────────

@dataclass
class ProgressEvent:
    """워커 → 메인 진행률 보고"""
    worker_id: int
    inserted: int          # 이번 배치 삽입 건수
    kind: str = "batch"    # 'batch' | 'done' | 'error'
    total_inserted: int = 0
    error_msg: Optional[str] = None


@dataclass
class LogEvent:
    """워커 → 메인 로그 전달"""
    worker_id: int
    level: str     # 'debug', 'info', 'warn', 'error'
    message: str


@dataclass
class BottleneckEvent:
    """워커 완료 시 병목 측정값"""
    worker_id: int
    t_execute: float
    t_select: float
    t_convert: float
    t_load: float
    inserted: int
    elapsed: float


# ──────────────────────────────────────────────────────────────
# 워커 진입점 (pickle-safe 모듈 레벨 함수)
# ──────────────────────────────────────────────────────────────

def _chunk_worker_subprocess(
    config: WorkerConfig,
    event_queue: mp.Queue,
) -> Dict[str, Any]:
    """
    별도 프로세스에서 실행되는 워커.

    Windows spawn 모드 호환을 위해:
      - 모든 import 를 함수 내부에서 수행
      - 예외 발생 시 Queue 로도 알리고, 반환값에도 담음
      - 반환값: {'inserted': N, 'failed': M, 'elapsed': X, 'error': str|None}
    """
    import time as _time
    import traceback as _tb

    worker_id = config.worker_id
    table = config.table
    t_start = _time.monotonic()

    # 워커에서 쓸 로그 헬퍼
    def _emit_log(level: str, msg: str):
        try:
            event_queue.put(LogEvent(worker_id=worker_id, level=level, message=msg))
        except Exception:
            pass  # Queue 문제 시 로그만 잃고 계속 진행

    def _emit_progress(inserted: int, total: int):
        try:
            event_queue.put(ProgressEvent(
                worker_id=worker_id, inserted=inserted,
                total_inserted=total, kind="batch"))
        except Exception:
            pass

    _emit_log("info",
        f"  [{table}] Worker#{worker_id} (PID {os.getpid()}) 시작 — "
        f"range: {config.chunk_range_dict.get('start_value')}..{config.chunk_range_dict.get('end_value')}")

    # 측정 지표
    t_execute = 0.0
    t_select  = 0.0
    t_convert = 0.0
    t_load    = 0.0
    inserted_total = 0

    src_conn = None
    tgt_conn = None
    loader = None

    try:
        # ── 1. DB 연결 개설 (워커 프로세스 내부에서) ──────────
        # 주의: app.core.db_conn 은 이 워커 프로세스에서 처음 import 되므로
        # 초기화 시간이 약간 걸릴 수 있음 (Windows spawn 특성)
        from app.core.db_conn import make_mssql_conn, make_mysql_conn

        t_conn = _time.monotonic()
        if config.src_db_type in ("mysql", "mariadb", "aurora", "tidb", "cloudsql"):
            src_conn = make_mysql_conn(
                host=config.src_host, port=config.src_port,
                username=config.src_username, password=config.src_password,
                database=config.src_database, timeout=config.connect_timeout,
                dict_cursor=True,
            )
        else:
            src_conn = make_mssql_conn(
                host=config.src_host, port=config.src_port,
                username=config.src_username, password=config.src_password,
                database=config.src_database, timeout=config.connect_timeout,
            )

        if config.tgt_db_type in ("mysql", "mariadb", "aurora", "tidb", "cloudsql"):
            tgt_conn = make_mysql_conn(
                host=config.tgt_host, port=config.tgt_port,
                username=config.tgt_username, password=config.tgt_password,
                database=config.tgt_database, timeout=config.connect_timeout,
            )
        else:
            tgt_conn = make_mssql_conn(
                host=config.tgt_host, port=config.tgt_port,
                username=config.tgt_username, password=config.tgt_password,
                database=config.tgt_database, timeout=config.connect_timeout,
            )
        conn_elapsed = _time.monotonic() - t_conn
        _emit_log("debug",
            f"  [{table}] Worker#{worker_id} DB 연결 완료 ({conn_elapsed:.2f}s)")

        # v11 #1 hotfix3: 워커의 MySQL tgt_conn 에 이관 최적화 힌트 세팅
        # 메인 프로세스가 설정한 SET FOREIGN_KEY_CHECKS=0 은 **메인 연결에만** 적용됨.
        # 워커는 별도 프로세스의 독립 연결 → FK=1 기본값 상태 → FK 참조 테이블 INSERT 시 실패.
        # 각 워커도 자기 세션에 명시적으로 FK/UNIQUE 체크 비활성화 필요.
        if config.tgt_is_mysql:
            try:
                _hint_cur = tgt_conn.cursor()
                for _hint in ("SET foreign_key_checks=0",
                              "SET unique_checks=0"):
                    try:
                        _hint_cur.execute(_hint)
                    except Exception:
                        pass  # 권한 없어도 치명적 아님
                _hint_cur.close()
            except Exception:
                pass  # 힌트 실패해도 이관 자체는 계속 시도

        # ── 2. bulk_loader 생성 ──────────────────────────────
        from app.engine.bulk_loader import create_loader
        loader = create_loader(
            mode=config.loader_mode,
            table=table, col_names=config.col_names, tgt_conn=tgt_conn,
            tgt_is_mssql=config.tgt_is_mssql, tgt_is_mysql=config.tgt_is_mysql,
            insert_sql=config.insert_sql,
            log=lambda lv, msg: _emit_log(lv, msg),
            job=config.job_meta,
            row_count=config.row_count,
            stop_check=lambda: False,  # 워커 프로세스는 자체 stop 체크 없음 (Phase 3a 에서 개선)
        )
        loader.open()

        # ── 3. converters 빌드 (워커 내부에서) ────────────────
        converters = None
        if config.tgt_is_mysql and config.src_is_mssql:
            # MigrationEngine._build_mysql_converters 를 호출할 수 없으므로 축약 버전
            converters = _build_converters_inline(
                config.cols_meta, config.col_names)

        # ── 4. SELECT SQL 생성 ───────────────────────────────
        chunk_range = config.chunk_range_dict
        pk_col = chunk_range["pk_column"]
        start_val = chunk_range["start_value"]
        end_val = chunk_range["end_value"]

        if config.src_is_mssql:
            where = f"[{pk_col}] >= {start_val} AND [{pk_col}] <= {end_val}"
            sql = (f"SELECT {config.select_expr} FROM [{table}] "
                   f"WHERE {where} ORDER BY [{pk_col}] ASC")
        else:
            where = f"`{pk_col}` >= {start_val} AND `{pk_col}` <= {end_val}"
            sql = (f"SELECT {config.select_expr} FROM `{table}` "
                   f"WHERE {where} ORDER BY `{pk_col}` ASC")

        src_cur = src_conn.cursor()
        if config.src_is_mssql:
            try: src_cur.arraysize = config.batch_size
            except: pass

        # EXECUTE 측정
        t0 = _time.monotonic()
        src_cur.execute(sql)
        t_execute = _time.monotonic() - t0
        _emit_log("debug",
            f"  [{table}] Worker#{worker_id} execute: {t_execute:.2f}s")

        # ── 5. 배치 루프 ──────────────────────────────────────
        while True:
            t0 = _time.monotonic()
            rows = src_cur.fetchmany(config.batch_size)
            t_select += _time.monotonic() - t0
            if not rows:
                break

            # 변환
            t0 = _time.monotonic()
            if converters is not None:
                batch_data = [
                    tuple(conv(v) for conv, v in zip(converters, r))
                    for r in rows
                ]
            else:
                batch_data = [tuple(r) for r in rows]
            t_convert += _time.monotonic() - t0

            # 로드
            t0 = _time.monotonic()
            inserted = loader.load(batch_data)
            t_load += _time.monotonic() - t0
            inserted_total += inserted

            # 메인에 진행률 통지
            _emit_progress(inserted, inserted_total)

        try: src_cur.close()
        except: pass

        elapsed = _time.monotonic() - t_start
        speed = int(inserted_total / elapsed) if elapsed > 0 else 0

        # 병목 보고
        try:
            event_queue.put(BottleneckEvent(
                worker_id=worker_id,
                t_execute=t_execute, t_select=t_select,
                t_convert=t_convert, t_load=t_load,
                inserted=inserted_total, elapsed=elapsed,
            ))
        except Exception:
            pass

        _emit_log("info",
            f"  [{table}] Worker#{worker_id} 완료: {inserted_total:,} rows "
            f"in {elapsed:.1f}s ({speed:,} rows/s)")

        return {
            "worker_id": worker_id,
            "inserted": inserted_total,
            "failed": 0,
            "elapsed": elapsed,
            "error": None,
        }

    except Exception as e:
        tb = _tb.format_exc()
        _emit_log("error",
            f"  [{table}] Worker#{worker_id} 예외: {str(e)[:200]}")
        _emit_log("debug", f"Traceback:\n{tb[:2000]}")
        return {
            "worker_id": worker_id,
            "inserted": inserted_total,
            "failed": config.row_count // 4,  # 추정치
            "elapsed": _time.monotonic() - t_start,
            "error": str(e)[:500],
        }

    finally:
        for c in (src_conn, tgt_conn):
            try:
                if c is not None: c.close()
            except Exception: pass
        try:
            if loader is not None: loader.close()
        except Exception: pass


# ──────────────────────────────────────────────────────────────
# 워커 내부용: converters 축약 빌드
# ──────────────────────────────────────────────────────────────

def _build_converters_inline(cols_meta: List[Dict[str, Any]], col_names: List[str]):
    """
    MigrationEngine._build_mysql_converters 의 축약 버전.

    워커 프로세스에서 self 참조 없이 동작 가능하도록 모듈 레벨 함수로 분리.
    Phase 3a Step 1 에서는 기본 변환만 지원 (rowversion/binary/datetime2 등은 TODO).
    """
    col_types = {c["COLUMN_NAME"]: (c.get("DATA_TYPE") or "").lower() for c in cols_meta}
    converters = []

    for cname in col_names:
        ct = col_types.get(cname, "")

        if ct in ("rowversion", "timestamp"):
            def f(v, _ct=ct):
                if v is None: return None
                if isinstance(v, (bytes, bytearray)): return bytes(v).hex()
                return None
            converters.append(f)
        elif ct in ("binary", "varbinary", "image"):
            def f(v):
                if v is None: return None
                if isinstance(v, (bytes, bytearray)): return bytes(v)
                return v
            converters.append(f)
        elif ct == "bit":
            def f(v):
                if v is None: return None
                return 1 if v else 0
            converters.append(f)
        else:
            # 일반 타입 — 그대로
            def f(v):
                return v
            converters.append(f)

    return converters


# ──────────────────────────────────────────────────────────────
# 메인 프로세스: 오케스트레이션
# ──────────────────────────────────────────────────────────────

class MpProgressCollector:
    """
    워커들이 Queue 에 넣은 이벤트를 메인 스레드에서 소비하여
    MigrationEngine.job 상태를 갱신하는 헬퍼.

    별도 스레드로 돌면서 Queue 를 계속 읽음.
    """
    def __init__(self, job: dict, table: str, row_count: int,
                 engine_start_t: float, logger):
        self.job = job
        self.table = table
        self.row_count = row_count
        self.engine_start_t = engine_start_t
        self.logger = logger

        self._lock = threading.Lock()
        self._total_done = 0
        self._worker_dones: Dict[int, int] = {}
        self._bottlenecks: List[BottleneckEvent] = []
        self._stop_flag = False
        self._thread: Optional[threading.Thread] = None

    def start(self, queue: mp.Queue):
        self._stop_flag = False
        self._thread = threading.Thread(
            target=self._consume_loop, args=(queue,),
            name=f"mp-collector-{self.table}", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_flag = True
        if self._thread:
            self._thread.join(timeout=2.0)

    def _consume_loop(self, queue: mp.Queue):
        """Queue 소비 루프 — 이벤트 종류별로 처리."""
        import time as _t
        while not self._stop_flag:
            try:
                event = queue.get(timeout=0.5)
            except Exception:
                continue  # 타임아웃은 정상 — stop 체크 후 재시도

            try:
                if isinstance(event, ProgressEvent):
                    self._handle_progress(event)
                elif isinstance(event, LogEvent):
                    self.logger(event.level, event.message)
                elif isinstance(event, BottleneckEvent):
                    with self._lock:
                        self._bottlenecks.append(event)
            except Exception as e:
                # 이벤트 처리 실패는 조용히 — 이관 자체 방해 안 함
                try: self.logger("debug", f"[mp-collector] event 처리 실패: {e}")
                except: pass

    def _handle_progress(self, ev: ProgressEvent):
        import time as _t
        with self._lock:
            self._total_done += ev.inserted
            self._worker_dones[ev.worker_id] = ev.total_inserted

            # Job 상태 갱신 (hotfix1 로직 재활용)
            _done_now = self._total_done
            try:
                self.job["current_table_rows_done"] = _done_now
                self.job["current_table_rows_total"] = self.row_count

                _st = self.job.setdefault("item_statuses", {}).get(self.table, {})
                _engine_elapsed = _t.monotonic() - self.engine_start_t
                _tbl_speed = (int(_done_now / _engine_elapsed)
                              if _engine_elapsed > 0 else 0)
                self.job["item_statuses"][self.table] = {
                    **_st,
                    "rows_src":       _done_now,
                    "rows_tgt":       _done_now,
                    "rows_total":     self.row_count,
                    "rows_tgt_final": False,
                    "speed":          _tbl_speed,
                    "type":           _st.get("type", "table"),
                    "status":         _st.get("status", "running"),
                }
                if _engine_elapsed > 0:
                    _total_all = (self.job.get("rows_processed", 0) + _done_now)
                    self.job["speed"] = int(_total_all / _engine_elapsed)

                _rows_total = self.job.get("rows_total", 0)
                if _rows_total > 0:
                    self.job["progress"] = min(99.9, round(
                        (self.job.get("rows_processed", 0) + _done_now)
                        / _rows_total * 100, 1))
                elif self.row_count and self.row_count > 0:
                    self.job["progress"] = min(99.9, round(
                        _done_now / self.row_count * 100, 1))
            except Exception:
                pass

    @property
    def total_done(self) -> int:
        with self._lock:
            return self._total_done

    @property
    def bottlenecks(self) -> List[BottleneckEvent]:
        with self._lock:
            return list(self._bottlenecks)


def run_chunked_migration_mp(
    *,
    table: str,
    decision: ChunkDecision,
    worker_configs: List[WorkerConfig],
    job: dict,
    engine_start_t: float,
    logger,
    on_error: str = "abort",
) -> Tuple[int, int]:
    """
    Phase 3a: ProcessPool 기반 청크 병렬 이관 실행.

    Returns:
        (total_inserted, total_failed)
    """
    logger("info",
        f"  [{table}] [MP] ProcessPool 청크 병렬 시작 — "
        f"{decision.workers} 워커 (Phase 3a Step 1)")

    row_count = sum(r.estimated_rows for r in decision.ranges)

    # v11 #1 hotfix1: Manager().Queue() 사용 (pickle 가능한 proxy)
    # 기존 mp.Queue() 는 ProcessPoolExecutor.submit() 의 인자로 전달 시
    # "Queue objects should only be shared between processes through inheritance"
    # 에러 발생 — Manager 가 생성한 Queue proxy 는 pickle 로 워커에 전달 가능.
    #
    # 성능 영향: Manager Queue 는 mp.Queue 보다 약 2~3배 느림 (IPC 오버헤드).
    # 하지만 이관 작업 규모에서는 진행률 이벤트가 초당 100~200개 정도라 무시 가능.
    manager = mp.Manager()
    event_queue = manager.Queue(maxsize=1000)

    # 진행률/로그 collector
    collector = MpProgressCollector(
        job=job, table=table, row_count=row_count,
        engine_start_t=engine_start_t, logger=logger,
    )
    collector.start(event_queue)

    start_t = time.monotonic()
    total_inserted = 0
    total_failed = 0
    workers_count = decision.workers
    abort_on_error = (on_error == "abort")

    try:
        with ProcessPoolExecutor(max_workers=workers_count) as ex:
            futures = {}
            for cfg in worker_configs:
                fut = ex.submit(_chunk_worker_subprocess, cfg, event_queue)
                futures[fut] = cfg.worker_id

            for fut in as_completed(futures):
                wid = futures[fut]
                try:
                    result = fut.result()
                except Exception as e:
                    logger("error",
                        f"  [{table}] Worker#{wid} 프로세스 자체 실패: {e}")
                    total_failed += row_count // workers_count
                    if abort_on_error:
                        break
                    continue

                total_inserted += result.get("inserted", 0)
                total_failed += result.get("failed", 0)

                if result.get("error") and abort_on_error:
                    logger("error",
                        f"  [{table}] Worker#{wid} 에러 — abort 정책으로 중단")
                    break
    finally:
        # Queue 에 남은 이벤트 처리 위해 잠깐 대기
        time.sleep(0.5)
        collector.stop()

    total_elapsed = time.monotonic() - start_t
    speed = int(total_inserted / total_elapsed) if total_elapsed > 0 else 0
    logger("info",
        f"  [{table}] [MP] 청크 병렬 종료 — "
        f"{total_inserted:,} rows / {total_elapsed:.1f}s ({speed:,} rows/s, "
        f"실패 {total_failed:,})")

    # 병목 집계
    bottlenecks = collector.bottlenecks
    if bottlenecks:
        for b in sorted(bottlenecks, key=lambda x: x.worker_id):
            total = b.t_execute + b.t_select + b.t_convert + b.t_load
            if total > 0:
                pct = lambda x: int(x / total * 100)
                logger("info",
                    f"  [{table}] [MP] Worker#{b.worker_id} 병목: "
                    f"EXECUTE {b.t_execute:.1f}s ({pct(b.t_execute)}%) · "
                    f"SELECT {b.t_select:.1f}s ({pct(b.t_select)}%) · "
                    f"CONVERT {b.t_convert:.1f}s ({pct(b.t_convert)}%) · "
                    f"LOAD {b.t_load:.1f}s ({pct(b.t_load)}%) · "
                    f"총 {total:.1f}s")

    return total_inserted, total_failed


def build_worker_configs(
    *,
    table: str, decision: ChunkDecision,
    col_names: List[str], cols_meta: List[Dict[str, Any]],
    select_expr: str, insert_sql: str,
    batch_size: int, row_count: int,
    src_db_type: str, tgt_db_type: str,
    tgt_is_mysql: bool, tgt_is_mssql: bool, src_is_mssql: bool,
    job: dict,
) -> List[WorkerConfig]:
    """
    ChunkRange 리스트와 Job 설정을 받아서 pickle-safe WorkerConfig 리스트 생성.

    MigrationEngine 에서 호출.
    """
    loader_mode = job.get("loader_mode", "auto")

    # job 중 워커가 참조할 필드를 **풍부하게** 전달
    # hotfix2: MySQL LOAD DATA 로더가 내부적으로 tgt_host/tgt_username/tgt_password 등을
    # job dict 에서 직접 참조하므로, job_meta 에 포함 안 하면 Windows 기본 사용자로
    # 재접속 시도 → "Access denied for user '박지안'@..." 발생 → executemany 폴백.
    #
    # 해결: 민감정보 포함한 Job 필드 전체를 pickle-safe 하게 복사.
    # 복사 대상: DB 접속정보 + bulk_loader/engine 동작 플래그.
    # 제외: 런타임 상태 (item_statuses, progress, speed 등) — 워커가 갱신할 필요 없음.
    def _copy_safe(key, default=None):
        v = job.get(key, default)
        # pickle-safe 기본 타입만 (dict/list 는 얕은 복사)
        if isinstance(v, dict): return dict(v)
        if isinstance(v, list): return list(v)
        return v

    job_meta = {
        # DB 접속정보 (★ 이게 핵심 — MySQL LOAD 로더가 재접속 시 필요)
        "src_host":      _copy_safe("src_host", ""),
        "src_port":      _copy_safe("src_port"),
        "src_username":  _copy_safe("src_username", ""),
        "src_password":  _copy_safe("src_password", ""),
        "src_database":  _copy_safe("src_database", ""),
        "src_db":        _copy_safe("src_db") or _copy_safe("src_db_type", ""),
        "tgt_host":      _copy_safe("tgt_host", ""),
        "tgt_port":      _copy_safe("tgt_port"),
        "tgt_username":  _copy_safe("tgt_username", ""),
        "tgt_password":  _copy_safe("tgt_password", ""),
        "tgt_database":  _copy_safe("tgt_database", ""),
        "tgt_db":        _copy_safe("tgt_db") or _copy_safe("tgt_db_type", ""),

        # 엔진/로더 설정
        "bulk_threshold_rows": _copy_safe("bulk_threshold_rows", 100_000),
        "on_error":            _copy_safe("on_error", "abort"),
        "loader_mode":         _copy_safe("loader_mode", "auto"),
        "batch_size":          _copy_safe("batch_size"),
        "bcp_path":            _copy_safe("bcp_path"),
        "connect_timeout":     _copy_safe("connect_timeout", 60),

        # MySQL LOAD DATA 관련 (혹시 구현체가 참조하는 경우 대비)
        "mysql_load_local_infile": _copy_safe("mysql_load_local_infile", True),
        "mysql_load_tmp_dir":      _copy_safe("mysql_load_tmp_dir"),
        "mysql_secure_file_priv":  _copy_safe("mysql_secure_file_priv"),

        # identity / 스키마 옵션
        "identity_insert":     _copy_safe("identity_insert"),
        "on_exists":           _copy_safe("on_exists", "append"),
        "drop_table":          _copy_safe("drop_table", False),

        # 기타 이관 플래그 (로더가 읽을 수 있는 모든 정적 옵션)
        "skip_columns":        _copy_safe("skip_columns"),
        "cast_columns":        _copy_safe("cast_columns"),
    }

    configs: List[WorkerConfig] = []
    for r in decision.ranges:
        configs.append(WorkerConfig(
            worker_id=r.worker_id,
            table=table,
            chunk_range_dict={
                "worker_id":    r.worker_id,
                "pk_column":    r.pk_column,
                "start_value":  r.start_value,
                "end_value":    r.end_value,
                "estimated_rows": r.estimated_rows,
            },
            src_db_type=src_db_type,
            src_host=job.get("src_host", ""),
            src_port=int(job.get("src_port") or (1433 if src_db_type.startswith("ms") else 3306)),
            src_username=job.get("src_username", ""),
            src_password=job.get("src_password", ""),
            src_database=job.get("src_database", ""),

            tgt_db_type=tgt_db_type,
            tgt_host=job.get("tgt_host", ""),
            tgt_port=int(job.get("tgt_port") or (1433 if tgt_db_type.startswith("ms") else 3306)),
            tgt_username=job.get("tgt_username", ""),
            tgt_password=job.get("tgt_password", ""),
            tgt_database=job.get("tgt_database", ""),

            connect_timeout=int(job.get("connect_timeout") or 60),

            col_names=list(col_names),
            cols_meta=list(cols_meta),
            select_expr=select_expr,
            insert_sql=insert_sql,
            batch_size=batch_size,
            row_count=row_count,
            loader_mode=loader_mode,
            job_meta=job_meta,

            tgt_is_mysql=tgt_is_mysql,
            tgt_is_mssql=tgt_is_mssql,
            src_is_mssql=src_is_mssql,
        ))

    return configs
