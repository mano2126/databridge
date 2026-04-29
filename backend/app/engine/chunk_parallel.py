"""
청크 분할 병렬 이관 (v10 #9)

단일 대용량 테이블을 PK 범위 기준으로 N개 청크로 분할하고,
각 청크를 독립 워커 스레드로 병렬 이관한다.

설계 원칙:
  1. 기존 _migrate_table() 의 단일 스레드 경로를 **대체하지 않음** — 옵션으로 추가
  2. 발동 조건 (모두 충족 시에만):
     - chunk_parallel_enabled=True
     - row_count >= large_table_threshold_rows (기본 100만)
     - PK 존재 + PKInfo.is_chunkable_arithmetic=True (정수 단일 PK)
     - src/tgt Dialect 모두 지원
  3. 조건 미충족 시: 조용히 단일 스레드 fallback
  4. PK 기반 산술분할 (Phase 2). COUNT percentile 은 Phase 3b.

워커 수 결정:
  - Job 설정 chunk_workers (기본 4, 최대 8)
  - row_count / 250,000 상한 (25만 미만 청크는 분할 의미 없음)
  - 최소 2 워커 (1 워커면 단일 스레드 fallback)

진행률 집계:
  - Lock 으로 보호된 누적 카운터
  - migration_engine 의 기존 progress 로직 그대로 활용 (v10 #5)

에러 처리:
  - Job 설정 on_error="abort" 이면 한 워커 실패 시 즉시 전체 중단
  - "skip_table" 이면 실패 청크만 기록하고 다른 워커는 계속
"""
from __future__ import annotations
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, CancelledError
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Any, Tuple

from .dialects.base import DatabaseDialect, PKInfo, ChunkRange


# ──────────────────────────────────────────────────────────
# 결정 로직 — 발동 여부 판단
# ──────────────────────────────────────────────────────────

@dataclass
class ChunkDecision:
    """청크 분할 발동 여부 및 상세"""
    enabled: bool
    reason: str
    workers: int = 0
    ranges: List[ChunkRange] = field(default_factory=list)


def decide_chunk_parallel(
    *,
    row_count: int,
    src_dialect: DatabaseDialect,
    tgt_dialect: DatabaseDialect,
    pk_info: Optional[PKInfo],
    job_config: dict,
    src_conn,
    table: str,
) -> ChunkDecision:
    """
    청크 분할 발동 여부 및 청크 범위 계산.

    반환값이 ChunkDecision(enabled=False, ...) 이면 호출자는 단일 스레드 경로로 폴백.
    """
    # 1) 기능 켜짐?
    # v10 #9 hotfix3: 기본값 False 로 변경 — 실측 결과 현재 구현은 단일 스레드보다 느림.
    # 안전 모드로 전환. 실험 시에만 명시적으로 활성화.
    #
    # 활성화 방법 3가지 (우선순위 순):
    #   1) Job 설정에 chunk_parallel_enabled=True  (영구 — Job 단위)
    #   2) 환경변수 DATABRIDGE_CHUNK_EXPERIMENT=1   (세션 — 모든 Job 강제 ON)
    #   3) 기본값 False                              (비활성)
    import os as _os
    _env_force = _os.environ.get("DATABRIDGE_CHUNK_EXPERIMENT", "").strip() in ("1", "true", "yes", "on")
    _job_enabled = job_config.get("chunk_parallel_enabled", None)

    if _job_enabled is False:
        return ChunkDecision(False, "chunk_parallel_enabled=False (Job 명시 OFF)")
    if _job_enabled is None and not _env_force:
        return ChunkDecision(False, "chunk_parallel_enabled 미설정 + ENV 미설정 (안전 기본값)")
    # 여기까지 오면: job_enabled=True 이거나 env_force=True

    # 2) Dialect 지원?
    from .dialects.base import UnsupportedDialect
    if isinstance(src_dialect, UnsupportedDialect):
        return ChunkDecision(False, f"src dialect '{src_dialect.name}' 미지원")
    if isinstance(tgt_dialect, UnsupportedDialect):
        return ChunkDecision(False, f"tgt dialect '{tgt_dialect.name}' 미지원")

    # 3) 대용량?
    # 기존 job["parallel_big_table_rows"] 필드 재사용 (기본 100만)
    # — 사용자가 한 곳만 조정해도 "대용량 단독 실행" 과 "청크 분할" 양쪽 모두 반영됨
    threshold = int(
        job_config.get("parallel_big_table_rows",
            job_config.get("large_table_threshold_rows", 1_000_000))
    )
    if row_count < threshold:
        return ChunkDecision(
            False,
            f"row_count {row_count:,} < 임계 {threshold:,}")

    # 4) PK 존재?
    if pk_info is None:
        return ChunkDecision(False, "PK 없음 — 산술분할 불가")

    # 5) PK 가 산술분할 가능한 타입?
    if not pk_info.is_chunkable_arithmetic:
        return ChunkDecision(
            False,
            f"PK {pk_info.columns} ({pk_info.column_types}) 산술분할 불가 타입")

    # 6) PK MIN/MAX 조회
    pk_col = pk_info.columns[0]
    try:
        min_val, max_val = src_dialect.get_pk_range(src_conn, table, pk_col)
    except Exception as e:
        return ChunkDecision(False, f"PK 범위 조회 실패: {e}")

    if min_val is None or max_val is None:
        return ChunkDecision(False, "테이블에 행 없음")

    try:
        min_int = int(min_val)
        max_int = int(max_val)
    except (TypeError, ValueError) as e:
        return ChunkDecision(False, f"PK 값이 정수 변환 불가: {e}")

    if max_int <= min_int:
        return ChunkDecision(False, "PK 범위가 단일 값")

    # 7) 워커 수 결정
    requested_workers = int(job_config.get("chunk_workers", 4))
    requested_workers = max(1, min(8, requested_workers))  # clamp 1~8

    # 워커당 최소 25만 행 보장 (너무 잘게 쪼개는 것 방지)
    max_by_size = max(1, row_count // 250_000)
    workers = min(requested_workers, max_by_size)

    if workers < 2:
        return ChunkDecision(
            False,
            f"행수 {row_count:,} / 25만 = {max_by_size} 워커 — 최소 2 미달")

    # 8) 청크 범위 산술분할
    ranges = _split_range_arithmetic(
        pk_col=pk_col,
        min_val=min_int,
        max_val=max_int,
        workers=workers,
        total_rows=row_count,
    )

    return ChunkDecision(
        enabled=True,
        reason=f"{workers} 워커 청크 분할 (PK={pk_col}, "
               f"범위={min_int:,}~{max_int:,})",
        workers=workers,
        ranges=ranges,
    )


def _split_range_arithmetic(
    *, pk_col: str, min_val: int, max_val: int,
    workers: int, total_rows: int,
) -> List[ChunkRange]:
    """
    PK 범위 [min_val, max_val] 를 workers 개 청크로 산술 분할.

    각 청크 범위는 inclusive-inclusive.
    경계값 충돌 없도록 범위가 서로 겹치지 않게 조정.

    예: min=1, max=100, workers=4
      Worker 1: 1..25
      Worker 2: 26..50
      Worker 3: 51..75
      Worker 4: 76..100
    """
    total_span = max_val - min_val + 1
    chunk_span = total_span // workers
    # 마지막 워커는 잔여분 모두 포함 (나눗셈 오차)

    ranges: List[ChunkRange] = []
    for i in range(workers):
        start = min_val + i * chunk_span
        if i == workers - 1:
            end = max_val           # 마지막 워커는 max_val 까지
        else:
            end = min_val + (i + 1) * chunk_span - 1
        # 예상 행수 (균등분포 가정)
        est_rows = total_rows // workers
        if i == workers - 1:
            est_rows = total_rows - est_rows * (workers - 1)

        ranges.append(ChunkRange(
            worker_id=i + 1,
            pk_column=pk_col,
            start_value=start,
            end_value=end,
            estimated_rows=est_rows,
        ))
    return ranges


# ──────────────────────────────────────────────────────────
# 진행률 집계 (공유 상태)
# ──────────────────────────────────────────────────────────

class ChunkProgress:
    """
    여러 워커의 진행을 스레드-안전하게 집계.

    migration_engine 의 기존 progress 필드 업데이트에 맞춰
    "총 done 카운트" 를 제공.
    """
    def __init__(self, total_rows: int):
        self._lock = threading.Lock()
        self._done = 0
        self._failed = 0
        self._total = total_rows
        self._worker_done: dict = {}   # worker_id → done

    def add_batch(self, worker_id: int, inserted: int, failed: int = 0):
        with self._lock:
            self._done += inserted
            self._failed += failed
            self._worker_done[worker_id] = self._worker_done.get(worker_id, 0) + inserted

    @property
    def total_done(self) -> int:
        with self._lock:
            return self._done

    @property
    def total_failed(self) -> int:
        with self._lock:
            return self._failed

    def worker_dones(self) -> dict:
        with self._lock:
            return dict(self._worker_done)


# ──────────────────────────────────────────────────────────
# 워커 실행 — 단일 청크 이관
# ──────────────────────────────────────────────────────────

@dataclass
class ChunkWorkerContext:
    """
    청크 워커가 실행할 작업의 모든 컨텍스트.

    migration_engine 에서 만들어서 워커에 넘긴다.
    """
    # 식별
    worker_id: int
    table: str
    chunk_range: ChunkRange

    # 연결 정보 (각 워커가 자기 src/tgt conn 생성)
    src_conn_factory: Callable        # () → src_conn
    tgt_conn_factory: Callable        # () → tgt_conn

    # 실행 로직 — 기존 _migrate_table 내부의 SELECT/CONVERT/LOAD 를
    # 청크별 WHERE 조건 포함한 클로저로 감싸서 주입
    # 시그니처: (src_conn, tgt_conn, where_clause) -> int (inserted rows)
    run_chunk: Callable[[Any, Any, str], int]

    # 공유 상태
    progress: ChunkProgress
    stop_flag: Callable[[], bool]     # 중단 체크
    logger: Callable[[str, str], None]  # (level, msg)

    # 방언
    src_dialect: DatabaseDialect

    def get_where_clause(self) -> str:
        """이 워커의 WHERE 절"""
        return self.src_dialect.chunk_where_clause(
            self.chunk_range.pk_column,
            self.chunk_range.start_value,
            self.chunk_range.end_value,
        )


def _worker_entry(ctx: ChunkWorkerContext) -> Tuple[int, int, Optional[Exception]]:
    """
    단일 워커 스레드 진입점.

    Returns:
        (inserted_rows, failed_rows, exception_or_None)
    """
    src_conn = None
    tgt_conn = None
    ctx.logger("info",
        f"  [{ctx.table}] {ctx.chunk_range.describe()} 시작")
    t0 = time.monotonic()
    try:
        # 각 워커는 독립 연결 개설
        src_conn = ctx.src_conn_factory()
        tgt_conn = ctx.tgt_conn_factory()

        where = ctx.get_where_clause()
        inserted = ctx.run_chunk(src_conn, tgt_conn, where)

        elapsed = time.monotonic() - t0
        speed = int(inserted / elapsed) if elapsed > 0 else 0
        ctx.logger("info",
            f"  [{ctx.table}] Worker#{ctx.chunk_range.worker_id} 완료: "
            f"{inserted:,} rows in {elapsed:.1f}s ({speed:,} rows/s)")
        return (inserted, 0, None)

    except Exception as e:
        elapsed = time.monotonic() - t0
        ctx.logger("error",
            f"  [{ctx.table}] Worker#{ctx.chunk_range.worker_id} 실패 "
            f"({elapsed:.1f}s 경과): {str(e)[:200]}")
        return (0, ctx.chunk_range.estimated_rows, e)

    finally:
        for c in (src_conn, tgt_conn):
            try:
                if c is not None:
                    c.close()
            except Exception:
                pass


# ──────────────────────────────────────────────────────────
# 메인 엔트리 — 청크 병렬 이관 오케스트레이션
# ──────────────────────────────────────────────────────────

def run_chunked_migration(
    *,
    table: str,
    decision: ChunkDecision,
    src_conn_factory: Callable,
    tgt_conn_factory: Callable,
    run_chunk: Callable[[Any, Any, str], int],
    progress: ChunkProgress,
    stop_flag: Callable[[], bool],
    logger: Callable[[str, str], None],
    src_dialect: DatabaseDialect,
    on_error: str = "abort",
) -> Tuple[int, int]:
    """
    N 개 워커로 청크 병렬 이관 실행.

    Returns:
        (total_inserted, total_failed)
    """
    if not decision.enabled:
        raise ValueError("청크 분할 비활성화 상태에서 run_chunked_migration 호출됨")

    workers = decision.workers
    ranges = decision.ranges

    logger("info",
        f"  [{table}] 청크 병렬 시작 — {decision.reason}")
    for r in ranges:
        logger("debug", f"    {r.describe()}")

    start_t = time.monotonic()
    total_inserted = 0
    total_failed = 0
    abort_on_error = (on_error == "abort")

    # ThreadPoolExecutor — 각 워커는 독립 연결이므로 GIL 영향 최소 (대부분 I/O 대기)
    with ThreadPoolExecutor(max_workers=workers,
                            thread_name_prefix=f"chunk-{table}") as ex:
        futures = {}
        for r in ranges:
            ctx = ChunkWorkerContext(
                worker_id=r.worker_id,
                table=table,
                chunk_range=r,
                src_conn_factory=src_conn_factory,
                tgt_conn_factory=tgt_conn_factory,
                run_chunk=run_chunk,
                progress=progress,
                stop_flag=stop_flag,
                logger=logger,
                src_dialect=src_dialect,
            )
            fut = ex.submit(_worker_entry, ctx)
            futures[fut] = r

        for fut in as_completed(futures):
            r = futures[fut]
            try:
                inserted, failed, exc = fut.result()
            except CancelledError:
                logger("warn", f"  [{table}] Worker#{r.worker_id} 취소됨")
                continue

            total_inserted += inserted
            total_failed += failed

            if exc is not None and abort_on_error:
                logger("error",
                    f"  [{table}] abort 정책 — 다른 워커들 중단 신호 (이미 시작된 건 완료됨)")
                # 남은 future 취소 시도 (이미 실행 중이면 취소 안 됨)
                for pending_fut in futures:
                    if not pending_fut.done():
                        pending_fut.cancel()
                # 중단 상태라도 마저 wait (데이터 일관성 복구는 상위 엔진 책임)
                break

    total_elapsed = time.monotonic() - start_t
    speed = int(total_inserted / total_elapsed) if total_elapsed > 0 else 0
    logger("info",
        f"  [{table}] 청크 병렬 종료 — "
        f"{total_inserted:,} rows / {total_elapsed:.1f}s ({speed:,} rows/s, "
        f"실패 {total_failed:,})")

    # 워커별 기여도 디버그 로그
    worker_dones = progress.worker_dones()
    if worker_dones:
        contrib = " / ".join([f"W#{wid}:{cnt:,}"
                              for wid, cnt in sorted(worker_dones.items())])
        logger("debug", f"  [{table}] 워커별 완료: {contrib}")

    return (total_inserted, total_failed)
