# -*- coding: utf-8 -*-
"""
DataBridge v95_p1 (2026-05-01) — 통계 갱신 어댑터 (DB-specific)

본부장님 명령 (2026-05-01 23:30):
  "전체 데이터 이관 후 통계 정보 갱신 자동화"
  "오라클 같은 경우 통계 정보 취약 — 파티션 잘 처리"
  "다양한 DB 처리해야 되는데 이런 문제로 고생하면 안 돼"

설계 원칙 (본부장님 모토):
  1. DB-specific 어댑터 (이름 추측 X — DB 종류로 분기)
  2. 새 DB 추가 시 이 파일만 수정 (통합 진입점 보존)
  3. Oracle 파티션 자동 감지 + granularity='ALL'
  4. 실패 허용 (한 테이블 실패해도 이관 성공 유지)
  5. 진행 로그 (각 테이블별 + 합계)

지원 DB:
  - MySQL / MariaDB / Aurora / TiDB
  - PostgreSQL
  - Oracle (파티션 자동 감지)
  - MSSQL
  - DB2

통합 진입점: gather_statistics(conn, db_type, db_name, tables, log_func)
"""

import time as _time
from typing import List, Callable, Dict, Any, Optional


# ════════════════════════════════════════════════════════════════════
# DB-specific 통계 갱신 어댑터
# ════════════════════════════════════════════════════════════════════

def _gather_mysql_table(cur, db_name: str, table: str) -> Dict[str, Any]:
    """MySQL/MariaDB/Aurora — ANALYZE TABLE
       - 파티션 자동 처리 (모든 파티션 통계 갱신)
       - InnoDB 의 persistent stats 자동 저장
    """
    t0 = _time.monotonic()
    cur.execute(f"ANALYZE TABLE `{db_name}`.`{table}`")
    # ANALYZE TABLE 결과셋 소비 (Msg_type/Msg_text)
    try: cur.fetchall()
    except Exception: pass
    elapsed = round((_time.monotonic() - t0) * 1000, 1)
    return {"ok": True, "elapsed_ms": elapsed, "table": table}


def _gather_postgresql_table(cur, db_name: str, table: str, schema: str = "public") -> Dict[str, Any]:
    """PostgreSQL — ANALYZE
       - 파티션 자동 처리 (PostgreSQL 11+ 의 declarative partition 도 자동)
       - VACUUM ANALYZE 가 더 강력하지만 시간이 길어 ANALYZE 만 (이관 직후라 충분)
    """
    t0 = _time.monotonic()
    # 스키마 + 테이블 형식
    if "." in table:
        cur.execute(f'ANALYZE "{table.split(".")[0]}"."{table.split(".", 1)[1]}"')
    else:
        cur.execute(f'ANALYZE "{schema}"."{table}"')
    elapsed = round((_time.monotonic() - t0) * 1000, 1)
    return {"ok": True, "elapsed_ms": elapsed, "table": table}


def _is_oracle_partitioned(cur, schema: str, table: str) -> bool:
    """Oracle 파티션 테이블 여부 감지
       DBA_TAB_PARTITIONS 또는 USER_TAB_PARTITIONS 확인
    """
    try:
        cur.execute("""
            SELECT COUNT(*) FROM ALL_TAB_PARTITIONS
            WHERE TABLE_OWNER = :owner AND TABLE_NAME = :tbl AND ROWNUM = 1
        """, owner=schema.upper(), tbl=table.upper())
        row = cur.fetchone()
        return bool(row and row[0] > 0)
    except Exception:
        # ALL_TAB_PARTITIONS 권한 없으면 USER_TAB_PARTITIONS 시도
        try:
            cur.execute("""
                SELECT COUNT(*) FROM USER_TAB_PARTITIONS
                WHERE TABLE_NAME = :tbl AND ROWNUM = 1
            """, tbl=table.upper())
            row = cur.fetchone()
            return bool(row and row[0] > 0)
        except Exception:
            return False


def _gather_oracle_table(cur, db_name: str, table: str, schema: Optional[str] = None) -> Dict[str, Any]:
    """Oracle — DBMS_STATS.GATHER_TABLE_STATS

    본부장님 강조 (2026-05-01):
      "오라클 통계 정보에 취약 — 파티션 잘 처리해야 됨"

    파티션 처리 (granularity 옵션):
      - 'AUTO'    : 일반 테이블 (Oracle 자동 결정)
      - 'ALL'     : 글로벌 + 파티션 + 서브파티션 모두 (파티션 테이블 권장)
      - 'GLOBAL'  : 글로벌만
      - 'PARTITION': 파티션 레벨만

    옵션:
      - estimate_percent = AUTO_SAMPLE_SIZE  : Oracle 권장 (정확도 + 속도)
      - method_opt = 'FOR ALL COLUMNS SIZE AUTO' : 컬럼별 히스토그램 자동
      - cascade = TRUE : 인덱스 통계도 함께
      - no_invalidate = FALSE : 기존 SQL 캐시 무효화 (새 통계 즉시 반영)
    """
    t0 = _time.monotonic()

    # 스키마 분리
    if "." in table:
        _sch, _tbl = table.split(".", 1)
    else:
        _sch = schema or db_name
        _tbl = table

    # 파티션 자동 감지
    is_partitioned = _is_oracle_partitioned(cur, _sch, _tbl)
    granularity = 'ALL' if is_partitioned else 'AUTO'

    # DBMS_STATS 익명 PL/SQL 블록
    plsql = """
    BEGIN
        DBMS_STATS.GATHER_TABLE_STATS(
            ownname          => :p_owner,
            tabname           => :p_table,
            estimate_percent => DBMS_STATS.AUTO_SAMPLE_SIZE,
            method_opt        => 'FOR ALL COLUMNS SIZE AUTO',
            cascade           => TRUE,
            granularity       => :p_granularity,
            no_invalidate     => FALSE
        );
    END;
    """
    cur.execute(plsql, p_owner=_sch.upper(), p_table=_tbl.upper(), p_granularity=granularity)

    elapsed = round((_time.monotonic() - t0) * 1000, 1)
    return {
        "ok": True,
        "elapsed_ms": elapsed,
        "table": table,
        "partitioned": is_partitioned,
        "granularity": granularity
    }


def _gather_mssql_table(cur, db_name: str, table: str) -> Dict[str, Any]:
    """MSSQL — UPDATE STATISTICS WITH FULLSCAN
       - WITH FULLSCAN : 전체 행 스캔 (정확)
       - 파티션 인덱스 통계는 자동 포함
       - 시간 vs 정확도: WITH SAMPLE 50 PERCENT 도 가능 (대용량 테이블)
    """
    t0 = _time.monotonic()
    if "." in table:
        sch, tbl = table.split(".", 1)
        cur.execute(f"UPDATE STATISTICS [{db_name}].[{sch}].[{tbl}] WITH FULLSCAN")
    else:
        cur.execute(f"UPDATE STATISTICS [{db_name}].[dbo].[{table}] WITH FULLSCAN")
    elapsed = round((_time.monotonic() - t0) * 1000, 1)
    return {"ok": True, "elapsed_ms": elapsed, "table": table}


def _gather_db2_table(cur, db_name: str, table: str, schema: Optional[str] = None) -> Dict[str, Any]:
    """DB2 — RUNSTATS ON TABLE
       - WITH DISTRIBUTION : 데이터 분포 (값 빈도)
       - AND DETAILED INDEXES ALL : 인덱스 상세 통계
       - ON ALL COLUMNS : 전 컬럼 통계
    """
    t0 = _time.monotonic()
    if "." in table:
        full_name = table
    else:
        full_name = f"{schema or db_name}.{table}"
    cur.execute(
        f"RUNSTATS ON TABLE {full_name} "
        f"ON ALL COLUMNS WITH DISTRIBUTION AND DETAILED INDEXES ALL"
    )
    elapsed = round((_time.monotonic() - t0) * 1000, 1)
    return {"ok": True, "elapsed_ms": elapsed, "table": table}


# ════════════════════════════════════════════════════════════════════
# 통합 진입점 — DB 종류로 분기
# ════════════════════════════════════════════════════════════════════

def gather_statistics(
    conn,
    db_type: str,
    db_name: str,
    tables: List[str],
    log_func: Optional[Callable[[str, str], None]] = None,
    schema: Optional[str] = None,
) -> Dict[str, Any]:
    """
    이관 완료 후 통계 정보 갱신 (모든 DB 표준 진입점)

    Args:
        conn: 활성 DB 연결 객체 (이관 시 사용한 동일 conn 재사용)
        db_type: 'mysql' / 'mariadb' / 'aurora' / 'tidb' / 'postgresql' /
                 'oracle' / 'mssql' / 'azure' / 'db2'
        db_name: 데이터베이스 이름
        tables: 갱신할 테이블 목록 (스키마 포함 가능: 'schema.table')
        log_func: 로그 콜백 (level, message) — None 이면 print
        schema: 기본 스키마 (table 에 . 없을 때 사용)

    Returns:
        {
            "total": int,
            "succeeded": int,
            "failed": int,
            "elapsed_ms": float,
            "details": [{"table", "ok", "elapsed_ms", "error"?}, ...],
            "skipped": bool  # db_type 미지원 시 True
        }
    """
    def _log(level: str, msg: str):
        if log_func:
            log_func(level, msg)
        else:
            print(f"[{level.upper()}] {msg}")

    db_type_lower = (db_type or "").lower()
    cur = conn.cursor()
    t_start = _time.monotonic()

    # DB-specific 어댑터 매핑
    adapters = {
        "mysql":      _gather_mysql_table,
        "mariadb":    _gather_mysql_table,
        "aurora":     _gather_mysql_table,
        "tidb":       _gather_mysql_table,
        "cloudsql":   _gather_mysql_table,
        "postgresql": _gather_postgresql_table,
        "postgres":   _gather_postgresql_table,
        "oracle":     _gather_oracle_table,
        "mssql":      _gather_mssql_table,
        "azure":      _gather_mssql_table,
        "db2":        _gather_db2_table,
    }

    adapter = adapters.get(db_type_lower)
    if not adapter:
        _log("warn", f"통계 갱신 미지원 DB 타입: {db_type} — 건너뜀")
        return {
            "total": len(tables), "succeeded": 0, "failed": 0,
            "elapsed_ms": 0, "details": [], "skipped": True
        }

    _log("info", f"═══ 통계 정보 자동 갱신 시작 ({db_type_lower}) — {len(tables)}개 테이블 ═══")

    details = []
    succeeded = 0
    failed = 0

    for i, tbl in enumerate(tables, 1):
        try:
            # 어댑터 호출 (시그니처 차이 처리)
            if db_type_lower in ("oracle", "postgresql", "postgres", "db2"):
                result = adapter(cur, db_name, tbl, schema=schema)
            else:
                result = adapter(cur, db_name, tbl)

            details.append(result)
            succeeded += 1

            # 진행 로그 (각 테이블별)
            extra = ""
            if result.get("partitioned"):
                extra = f" [파티션 ALL]"
            _log("info", f"  [{i}/{len(tables)}] ✓ {tbl} ({result['elapsed_ms']:.0f}ms){extra}")

        except Exception as e:
            err = str(e)[:200]
            details.append({
                "ok": False, "table": tbl, "elapsed_ms": 0,
                "error": err
            })
            failed += 1
            # 실패해도 계속 진행 (본부장님 결정)
            _log("warn", f"  [{i}/{len(tables)}] ✗ {tbl} — {err}")

    # 커밋 (Oracle/PostgreSQL/DB2 의 일부 통계는 commit 필요)
    try:
        conn.commit()
    except Exception:
        pass

    total_elapsed = round((_time.monotonic() - t_start) * 1000, 1)
    _log("info",
        f"═══ 통계 갱신 완료 — 성공 {succeeded}/{len(tables)} "
        f"실패 {failed} 소요 {total_elapsed:.0f}ms ({total_elapsed/1000:.1f}s) ═══"
    )

    return {
        "total": len(tables),
        "succeeded": succeeded,
        "failed": failed,
        "elapsed_ms": total_elapsed,
        "details": details,
        "skipped": False
    }
