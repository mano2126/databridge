"""
app/monitor/adapter_db_native.py — DB 자체 성능 뷰 기반 Migration-Aware 모니터
v10 #22

이 어댑터의 철학:
  Docker 가 있든 없든, 로컬이든 원격이든, 클라우드 RDS든 —
  DB 자신은 항상 자기 상태를 알려줄 수 있다.
  이미 DataBridge 가 가진 DB 연결(profile)을 그대로 재사용한다.

지원 DB:
  - MSSQL  : DMV (sys.dm_os_*, sys.dm_exec_*, sys.dm_io_*)
  - MySQL  : SHOW GLOBAL STATUS, performance_schema

설정 예시 (target.config):
  {
    "profile_id": "p1",          # 기존 Connection Profile 재사용 (권장)
    "which":      "source"       # source | target
  }
또는 직접 연결 정보:
  {
    "db_type": "mssql",
    "host":    "localhost",
    "port":    1433,
    "username": "sa",
    "password": "...",
    "database": "master"
  }
"""
from __future__ import annotations

from typing import Optional, Any

from app.monitor.base import (
    MonitorAdapter, MonitorSnapshot,
    DBMetrics, Alert, AlertLevel, MetricDef,
)


class DBNativeAdapter(MonitorAdapter):
    """DB 자체 성능 뷰를 쿼리해서 Migration-Aware 지표를 제공."""

    ADAPTER_TYPE = "db_native"

    # MSSQL DMV 쿼리 — 단일 왕복으로 핵심 지표 일괄 조회
    _MSSQL_KPI_SQL = """
    SELECT
      -- 버퍼 캐시 히트율
      (SELECT CAST(cntr_value AS FLOAT) FROM sys.dm_os_performance_counters
       WHERE counter_name = 'Buffer cache hit ratio'
         AND object_name LIKE '%Buffer Manager%')
      /
      NULLIF((SELECT CAST(cntr_value AS FLOAT) FROM sys.dm_os_performance_counters
              WHERE counter_name = 'Buffer cache hit ratio base'
                AND object_name LIKE '%Buffer Manager%'), 0) * 100 AS bcr_pct,

      -- Page Life Expectancy (sec)
      (SELECT cntr_value FROM sys.dm_os_performance_counters
       WHERE counter_name = 'Page life expectancy'
         AND object_name LIKE '%Buffer Manager%') AS ple_sec,

      -- 메모리
      (SELECT total_physical_memory_kb / 1024 FROM sys.dm_os_sys_memory)     AS total_mem_mb,
      (SELECT available_physical_memory_kb / 1024 FROM sys.dm_os_sys_memory) AS avail_mem_mb,

      -- 활성 세션
      (SELECT COUNT(*) FROM sys.dm_exec_requests WHERE session_id > 50)     AS active_sessions,
      (SELECT COUNT(*) FROM sys.dm_exec_requests
       WHERE session_id > 50 AND blocking_session_id > 0)                    AS blocked_sessions,

      -- 30초 이상 장기 쿼리
      (SELECT COUNT(*) FROM sys.dm_exec_requests
       WHERE session_id > 50 AND total_elapsed_time > 30000)                 AS long_queries,

      -- tempdb (본부장님 트라우마!)
      (SELECT SUM(unallocated_extent_page_count) * 8.0 / 1024
       FROM tempdb.sys.dm_db_file_space_usage)                               AS tempdb_free_mb,

      -- DB 버전
      CAST(SERVERPROPERTY('ProductVersion') AS NVARCHAR(128))                AS db_version
    """

    # MSSQL I/O 지연 (별도 쿼리 — TOP 사용 때문에 분리)
    _MSSQL_IO_SQL = """
    SELECT TOP 1
      AVG(CASE WHEN num_of_reads > 0
               THEN CAST(io_stall_read_ms AS FLOAT) / num_of_reads
               ELSE 0 END)  AS avg_read_ms,
      AVG(CASE WHEN num_of_writes > 0
               THEN CAST(io_stall_write_ms AS FLOAT) / num_of_writes
               ELSE 0 END)  AS avg_write_ms
    FROM sys.dm_io_virtual_file_stats(NULL, NULL)
    """

    def __init__(self, target):
        super().__init__(target)
        self._conn = None
        self._db_type: Optional[str] = None
        self._db_info: Optional[dict] = None
        self._conn_error: Optional[str] = None

    def _resolve_db_info(self) -> Optional[dict]:
        """target.config 에서 DB 접속 정보 해석.
        profile_id 우선 → 직접 정보."""
        cfg = self.target.config or {}
        if cfg.get("profile_id"):
            # 기존 DataBridge Connection Profile 재사용
            try:
                from app.api.routes.connector import get_profile_decrypted
                p = get_profile_decrypted(cfg["profile_id"])
                if not p:
                    return None
                which = cfg.get("which", "source")
                return p.get(which) or p.get("source")
            except Exception:
                return None
        # 직접 정보
        if cfg.get("db_type") and cfg.get("host"):
            return {
                "db_type":  cfg["db_type"],
                "host":     cfg["host"],
                "port":     cfg.get("port"),
                "username": cfg.get("username"),
                "password": cfg.get("password"),
                "database": cfg.get("database"),
            }
        return None

    def connect(self) -> bool:
        if self._connected and self._conn is not None:
            return True

        info = self._resolve_db_info()
        if not info:
            self._conn_error = "DB 접속 정보 없음 (profile_id 또는 직접 정보 필요)"
            return False

        db_type = (info.get("db_type") or "").lower()
        self._db_type = db_type
        self._db_info = info

        try:
            if db_type == "mssql":
                import pyodbc
                driver = "{ODBC Driver 18 for SQL Server}"
                # Encrypt=no, TrustServerCertificate=yes — Dev 편의
                conn_str = (
                    f"DRIVER={driver};"
                    f"SERVER={info['host']},{info.get('port', 1433)};"
                    f"DATABASE={info.get('database','master')};"
                    f"UID={info['username']};PWD={info.get('password','')};"
                    f"Encrypt=no;TrustServerCertificate=yes;"
                    f"Connection Timeout=5"
                )
                self._conn = pyodbc.connect(conn_str, timeout=5)
                self._conn.autocommit = True
            elif db_type in ("mysql", "mariadb"):
                import pymysql
                self._conn = pymysql.connect(
                    host=info["host"],
                    port=int(info.get("port") or 3306),
                    user=info["username"],
                    password=info.get("password", ""),
                    database=info.get("database"),
                    connect_timeout=5,
                    read_timeout=5,
                    autocommit=True,
                )
            elif db_type in ("postgresql", "postgres", "pg"):
                import psycopg2
                self._conn = psycopg2.connect(
                    host=info["host"],
                    port=int(info.get("port") or 5432),
                    user=info["username"],
                    password=info.get("password", ""),
                    dbname=info.get("database", "postgres"),
                    connect_timeout=5,
                )
                self._conn.autocommit = True
            else:
                self._conn_error = f"지원하지 않는 DB 타입: {db_type}"
                return False

            self._connected = True
            self._conn_error = None
            return True

        except Exception as e:
            self._conn_error = f"{type(e).__name__}: {str(e)[:120]}"
            return False

    def fetch_snapshot(self) -> MonitorSnapshot:
        snap = MonitorSnapshot(
            ts=self._ts_ms(),
            target_id=self.target_id,
            target_type=self.ADAPTER_TYPE,
            target_display=self.target.display_name,
        )

        if not self.connect():
            snap.errors["connect"] = self._conn_error or "unknown"
            return snap

        try:
            if self._db_type == "mssql":
                snap.db = self._fetch_mssql()
            elif self._db_type in ("mysql", "mariadb"):
                snap.db = self._fetch_mysql()
            elif self._db_type in ("postgresql", "postgres", "pg"):
                snap.db = self._fetch_postgres()

            if snap.db:
                snap.alerts.extend(self._check_alerts(snap.db))
        except Exception as e:
            # 연결 자체가 끊어진 경우엔 재시도하도록 초기화
            self._connected = False
            try:
                if self._conn:
                    self._conn.close()
            except Exception:
                pass
            self._conn = None
            snap.errors["fetch"] = f"{type(e).__name__}: {str(e)[:100]}"

        return snap

    # ──────────────────────────────────────────────────────
    # MSSQL
    # ──────────────────────────────────────────────────────
    def _fetch_mssql(self) -> DBMetrics:
        db = DBMetrics(db_type="mssql")
        cur = self._conn.cursor()

        # KPI 단일 왕복
        try:
            cur.execute(self._MSSQL_KPI_SQL)
            row = cur.fetchone()
            if row:
                db.buffer_cache_hit_ratio = self._f(row[0])
                db.page_life_expectancy   = self._f(row[1])
                db.total_memory_mb        = self._i(row[2])
                # 가용 = total - avail (즉, 현재 사용)
                if row[2] is not None and row[3] is not None:
                    db.used_memory_mb = max(0, int(row[2]) - int(row[3]))
                db.active_sessions      = self._i(row[4])
                db.blocked_sessions     = self._i(row[5])
                db.long_running_queries = self._i(row[6])
                db.tempdb_free_mb       = self._f(row[7])
                db.db_version           = str(row[8]) if row[8] else None
        except Exception:
            pass

        # I/O 지연
        try:
            cur.execute(self._MSSQL_IO_SQL)
            row = cur.fetchone()
            if row:
                db.avg_read_latency_ms  = self._f(row[0])
                db.avg_write_latency_ms = self._f(row[1])
        except Exception:
            pass

        cur.close()
        return db

    # ──────────────────────────────────────────────────────
    # MySQL
    # ──────────────────────────────────────────────────────
    def _fetch_mysql(self) -> DBMetrics:
        db = DBMetrics(db_type="mysql")
        cur = self._conn.cursor()

        # SHOW GLOBAL STATUS (핵심 변수만)
        try:
            cur.execute("SHOW GLOBAL STATUS WHERE Variable_name IN ("
                        "'Threads_running', 'Threads_connected', "
                        "'Innodb_buffer_pool_pages_total', "
                        "'Innodb_buffer_pool_pages_free', "
                        "'Innodb_row_lock_waits', 'Innodb_row_lock_time_avg', "
                        "'Max_used_connections', 'Slow_queries')")
            stat = {r[0]: r[1] for r in cur.fetchall()}

            total_pages = self._i(stat.get("Innodb_buffer_pool_pages_total"))
            free_pages  = self._i(stat.get("Innodb_buffer_pool_pages_free"))
            if total_pages and total_pages > 0:
                used = total_pages - (free_pages or 0)
                db.buffer_pool_used_pct = round(used / total_pages * 100, 1)

            db.threads_running  = self._i(stat.get("Threads_running"))
            db.active_sessions  = self._i(stat.get("Threads_connected"))
            db.lock_waits       = self._i(stat.get("Innodb_row_lock_waits"))
        except Exception:
            pass

        # max_connections
        try:
            cur.execute("SHOW VARIABLES LIKE 'max_connections'")
            r = cur.fetchone()
            if r:
                db.max_connections = self._i(r[1])
        except Exception:
            pass

        # 버전
        try:
            cur.execute("SELECT VERSION()")
            r = cur.fetchone()
            if r:
                db.db_version = str(r[0])
        except Exception:
            pass

        # 장기 실행 쿼리 (30초 이상)
        try:
            cur.execute("SELECT COUNT(*) FROM information_schema.processlist "
                        "WHERE TIME > 30 AND COMMAND NOT IN ('Sleep','Daemon')")
            r = cur.fetchone()
            if r:
                db.long_running_queries = self._i(r[0])
        except Exception:
            pass

        # buffer pool 크기 (MB 환산)
        try:
            cur.execute("SHOW VARIABLES LIKE 'innodb_buffer_pool_size'")
            r = cur.fetchone()
            if r:
                db.total_memory_mb = int(int(r[1]) / 1024 / 1024)
        except Exception:
            pass

        cur.close()
        return db

    # ──────────────────────────────────────────────────────
    # PostgreSQL (기본 지원 — Phase B 에서 강화)
    # ──────────────────────────────────────────────────────
    def _fetch_postgres(self) -> DBMetrics:
        db = DBMetrics(db_type="postgresql")
        cur = self._conn.cursor()
        try:
            cur.execute("SELECT COUNT(*), "
                        "COUNT(*) FILTER (WHERE wait_event IS NOT NULL), "
                        "COUNT(*) FILTER (WHERE state='active' "
                        "AND now() - query_start > interval '30 seconds') "
                        "FROM pg_stat_activity WHERE pid <> pg_backend_pid()")
            r = cur.fetchone()
            if r:
                db.active_sessions       = self._i(r[0])
                db.blocked_sessions      = self._i(r[1])
                db.long_running_queries  = self._i(r[2])
        except Exception:
            pass

        try:
            cur.execute("SHOW server_version")
            r = cur.fetchone()
            if r:
                db.db_version = str(r[0])
        except Exception:
            pass
        cur.close()
        return db

    # ──────────────────────────────────────────────────────
    # 알림 규칙 — Migration-Aware
    # ──────────────────────────────────────────────────────
    def _check_alerts(self, db: DBMetrics) -> list[Alert]:
        alerts: list[Alert] = []

        # MSSQL 버퍼 캐시 — 95% 아래면 메모리 부족 신호
        if db.buffer_cache_hit_ratio is not None:
            if db.buffer_cache_hit_ratio < 90:
                alerts.append(Alert(
                    level=AlertLevel.CRITICAL,
                    code="MSSQL_BCR_CRITICAL",
                    message=f"버퍼 캐시 히트율 {db.buffer_cache_hit_ratio:.1f}% — 메모리 심각 부족",
                    metric="buffer_cache_hit_ratio",
                    value=db.buffer_cache_hit_ratio, threshold=90,
                ))
            elif db.buffer_cache_hit_ratio < 95:
                alerts.append(Alert(
                    level=AlertLevel.WARNING,
                    code="MSSQL_BCR_LOW",
                    message=f"버퍼 캐시 히트율 {db.buffer_cache_hit_ratio:.1f}% — 메모리 부족 징후",
                    metric="buffer_cache_hit_ratio",
                    value=db.buffer_cache_hit_ratio, threshold=95,
                ))

        # MSSQL Page Life Expectancy — 300초 아래면 위험
        if db.page_life_expectancy is not None:
            if db.page_life_expectancy < 180:
                alerts.append(Alert(
                    level=AlertLevel.CRITICAL,
                    code="MSSQL_PLE_CRITICAL",
                    message=f"Page Life Expectancy {db.page_life_expectancy:.0f}초 — 이관 OOM 임박",
                    metric="page_life_expectancy",
                    value=db.page_life_expectancy, threshold=180,
                ))
            elif db.page_life_expectancy < 300:
                alerts.append(Alert(
                    level=AlertLevel.WARNING,
                    code="MSSQL_PLE_LOW",
                    message=f"Page Life Expectancy {db.page_life_expectancy:.0f}초 — 메모리 순환 빠름",
                    metric="page_life_expectancy",
                    value=db.page_life_expectancy, threshold=300,
                ))

        # MySQL InnoDB 버퍼 풀
        if db.buffer_pool_used_pct is not None and db.buffer_pool_used_pct >= 95:
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                code="MYSQL_BUFFER_POOL_HIGH",
                message=f"InnoDB Buffer Pool {db.buffer_pool_used_pct:.0f}% — 확장 권장",
                metric="buffer_pool_used_pct",
                value=db.buffer_pool_used_pct, threshold=95,
            ))

        # 블로킹 세션 (어느 DB나)
        if db.blocked_sessions is not None and db.blocked_sessions > 0:
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                code="DB_BLOCKED_SESSIONS",
                message=f"블로킹 세션 {db.blocked_sessions}개 감지 — 이관 지연 가능",
                metric="blocked_sessions",
                value=float(db.blocked_sessions),
            ))

        # 장기 쿼리
        if db.long_running_queries is not None and db.long_running_queries >= 3:
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                code="DB_LONG_QUERIES",
                message=f"30초 초과 쿼리 {db.long_running_queries}개 — 경합 가능성",
                metric="long_running_queries",
                value=float(db.long_running_queries),
            ))

        # I/O 지연 (MSSQL)
        if db.avg_read_latency_ms is not None and db.avg_read_latency_ms > 50:
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                code="DB_IO_READ_SLOW",
                message=f"평균 Read 지연 {db.avg_read_latency_ms:.0f}ms — 디스크 병목 가능",
                metric="avg_read_latency_ms",
                value=db.avg_read_latency_ms, threshold=50,
            ))

        # tempdb (MSSQL — 본부장님 트라우마!)
        if db.tempdb_free_mb is not None and db.tempdb_free_mb < 500:
            alerts.append(Alert(
                level=AlertLevel.CRITICAL,
                code="MSSQL_TEMPDB_LOW",
                message=f"tempdb 여유 {db.tempdb_free_mb:.0f}MB — 대용량 이관 실패 위험",
                metric="tempdb_free_mb",
                value=db.tempdb_free_mb, threshold=500,
            ))

        return alerts

    def available_metrics(self) -> list[MetricDef]:
        return [
            MetricDef("buffer_cache_hit_ratio", "버퍼 캐시 히트율", "%",
                      warn_at=95, critical_at=90,
                      description="95 이하면 메모리 부족 징후 (MSSQL)"),
            MetricDef("page_life_expectancy", "Page Life Expectancy", "sec",
                      warn_at=300, critical_at=180,
                      description="페이지가 버퍼에 머무는 시간 (MSSQL)"),
            MetricDef("buffer_pool_used_pct", "InnoDB 버퍼 풀 사용률", "%",
                      warn_at=90, critical_at=95,
                      description="MySQL InnoDB 버퍼 풀"),
            MetricDef("active_sessions",   "활성 세션",   "count"),
            MetricDef("blocked_sessions",  "블로킹 세션", "count",
                      warn_at=1,
                      description="이관 지연/데드락 징후"),
            MetricDef("long_running_queries", "장기 쿼리(30초+)", "count", warn_at=3),
            MetricDef("avg_read_latency_ms",  "평균 Read 지연", "ms",  warn_at=50),
            MetricDef("avg_write_latency_ms", "평균 Write 지연", "ms", warn_at=50),
            MetricDef("tempdb_free_mb", "tempdb 여유", "MB", critical_at=500,
                      description="MSSQL 전용. 대용량 이관 시 급증"),
        ]

    def disconnect(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None
        self._connected = False

    # ── 안전 변환 유틸 ──────────────────────────────
    @staticmethod
    def _f(v) -> Optional[float]:
        if v is None: return None
        try:    return round(float(v), 2)
        except: return None

    @staticmethod
    def _i(v) -> Optional[int]:
        if v is None: return None
        try:    return int(v)
        except: return None
