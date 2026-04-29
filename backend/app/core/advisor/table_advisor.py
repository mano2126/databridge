"""
app/core/advisor/table_advisor.py — 테이블 구조 최적화 Advisor
v88 P3 (2026-04-23)

역할:
    선택된 테이블의 구조를 분석하여 이관 시점에 함께 개선할 기회를 찾는다.
    "원본 DB 의 비효율을 그대로 이관하지 않는다" — DataBridge 차별화 핵심.

P3 범위:
    1. 파티셔닝 권고 — 대용량 테이블 (row 수 / 크기 기준)
    2. 타입 오버스펙 탐지 — NVARCHAR(MAX), TEXT, BIGINT 과다 사용
    3. PK 전략 — UNIQUEIDENTIFIER → BINARY(16) 변환 권고
    4. 통계 자동 갱신 — MySQL 은 innodb_stats_auto_recalc=ON, MSSQL 은 AUTO_UPDATE_STATISTICS

설계 원칙:
    - 규칙 기반 (AI 호출 0회) — 안정성과 비용 0 보장
    - 소스 DB 연결 없이도 동작 (selection 메타만으로 추정)
    - context.src_conn 이 있으면 실제 컬럼/row 정보 조회해서 정밀도 ↑ (옵션)
"""
from __future__ import annotations

import logging
from typing import Optional

from app.core.advisor.base_advisor import (
    BaseAdvisor,
    JobSelection,
    AnalysisContext,
    AnalysisMode,
    Recommendation,
)

logger = logging.getLogger("databridge.advisor.table")


# ══════════════════════════════════════════════════════════════
# 임계값 (규칙 엔진 경험값 — P6 learner 가 조정 가능)
# ══════════════════════════════════════════════════════════════
PARTITION_ROW_THRESHOLD   = 10_000_000      # 1천만 rows 이상 → 파티셔닝 권고
PARTITION_SIZE_THRESHOLD  = 10 * 1024**3    # 10GB 이상 → 파티셔닝 권고
LARGE_TABLE_ROW_THRESHOLD = 1_000_000       # 100만 rows — 중간 규모 기준


# ══════════════════════════════════════════════════════════════
# 테이블 메타 조회
# ══════════════════════════════════════════════════════════════
def _fetch_table_meta(
    tables: list[str],
    context: AnalysisContext,
) -> dict[str, dict]:
    """
    선택된 테이블들의 메타 정보를 소스 DB 에서 조회.

    Returns:
        { table_name: {row_count, size_bytes, columns: [{name, type, nullable}], pk: [...], ...} }

    src_conn 없으면 빈 dict (규칙은 동작하지만 정밀도 ↓).
    """
    result: dict[str, dict] = {}
    if context.src_conn is None or not tables:
        return result

    src_db = (context.src_db or "").lower()
    conn = context.src_conn
    cur = conn.cursor()

    try:
        if src_db in ("mysql", "mariadb", "aurora", "tidb", "cloudsql"):
            placeholders = ",".join(["%s"] * len(tables))
            cur.execute(
                f"""
                SELECT table_name, table_rows, data_length + index_length AS bytes
                FROM information_schema.tables
                WHERE table_schema = DATABASE() AND table_name IN ({placeholders})
                """,
                tuple(tables),
            )
            for row in cur.fetchall():
                result[row[0]] = {
                    "row_count": int(row[1] or 0),
                    "size_bytes": int(row[2] or 0),
                    "columns": [],
                    "pk": [],
                }

            cur.execute(
                f"""
                SELECT table_name, column_name, data_type, column_type,
                       is_nullable, character_maximum_length
                FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name IN ({placeholders})
                ORDER BY table_name, ordinal_position
                """,
                tuple(tables),
            )
            for row in cur.fetchall():
                tbl = row[0]
                if tbl not in result:
                    result[tbl] = {"row_count": 0, "size_bytes": 0, "columns": [], "pk": []}
                result[tbl]["columns"].append({
                    "name": row[1],
                    "data_type": (row[2] or "").lower(),
                    "column_type": row[3] or "",
                    "nullable": (row[4] == "YES"),
                    "max_length": int(row[5]) if row[5] is not None else None,
                })

            cur.execute(
                f"""
                SELECT k.table_name, k.column_name
                FROM information_schema.key_column_usage k
                JOIN information_schema.table_constraints t
                  ON k.constraint_name = t.constraint_name
                 AND k.table_schema = t.table_schema
                 AND k.table_name = t.table_name
                WHERE t.constraint_type = 'PRIMARY KEY'
                  AND k.table_schema = DATABASE()
                  AND k.table_name IN ({placeholders})
                ORDER BY k.table_name, k.ordinal_position
                """,
                tuple(tables),
            )
            for row in cur.fetchall():
                tbl = row[0]
                if tbl in result:
                    result[tbl]["pk"].append(row[1])

        elif src_db in ("mssql", "azure", "sqlserver"):
            # v88 hotfix3 (2026-04-23): 스키마 인식
            # 입력 테이블 이름이 "schema.table" 또는 "table" 형태 모두 처리.
            # 동명이인(다른 스키마에 같은 이름) 존재 시 첫 발견된 것 사용 +
            # logger.info 로 경고.
            bare_names: list[str] = []
            schema_hints: dict[str, Optional[str]] = {}   # bare_name → hint
            original_by_bare: dict[str, str] = {}         # bare_name → original input
            for t in tables:
                cleaned = (t or "").replace("[", "").replace("]", "")
                if "." in cleaned:
                    s, b = cleaned.split(".", 1)
                    schema_hints[b] = s
                else:
                    b = cleaned
                    schema_hints.setdefault(b, None)
                bare_names.append(b)
                original_by_bare[b] = t   # 원본 이름 유지 (권고 표시용)

            if not bare_names:
                return result

            placeholders = ",".join(["?"] * len(bare_names))

            # 기본 통계 — 스키마 포함해서 조회
            cur.execute(
                f"""
                SELECT
                    s.name AS schema_name,
                    t.name AS table_name,
                    SUM(CASE WHEN ps.index_id < 2 THEN ps.row_count ELSE 0 END) AS rows,
                    SUM(ps.reserved_page_count) * 8 * 1024 AS bytes
                FROM sys.tables t
                JOIN sys.schemas s ON t.schema_id = s.schema_id
                LEFT JOIN sys.dm_db_partition_stats ps ON ps.object_id = t.object_id
                WHERE t.name IN ({placeholders})
                GROUP BY s.name, t.name
                """,
                tuple(set(bare_names)),
            )

            # 스키마 힌트 기반 매칭
            raw_rows = cur.fetchall()
            picked: dict[str, dict] = {}  # bare_name → row
            for row in raw_rows:
                sch, nm, rows, bytes_ = row[0], row[1], row[2], row[3]
                hint = schema_hints.get(nm)
                if hint is None or hint.lower() == sch.lower():
                    if nm in picked:
                        logger.info(
                            "TableAdvisor: 테이블 %s 동명이인 (이미 %s, 추가 %s) — 먼저 것 유지",
                            nm, picked[nm]["schema"], sch
                        )
                        continue
                    picked[nm] = {
                        "schema": sch, "rows": int(rows or 0), "bytes": int(bytes_ or 0)
                    }

            for bare, info in picked.items():
                original = original_by_bare.get(bare, bare)
                result[original] = {
                    "row_count": info["rows"],
                    "size_bytes": info["bytes"],
                    "columns": [],
                    "pk": [],
                    "_schema": info["schema"],
                }

            # 컬럼 정보 — object_id 기반으로 정확히
            if picked:
                pick_schemas = set(v["schema"] for v in picked.values())
                cur.execute(
                    f"""
                    SELECT s.name, t.name, c.name, ty.name, c.max_length, c.is_nullable
                    FROM sys.columns c
                    JOIN sys.tables  t ON c.object_id = t.object_id
                    JOIN sys.schemas s ON t.schema_id = s.schema_id
                    JOIN sys.types   ty ON c.user_type_id = ty.user_type_id
                    WHERE t.name IN ({placeholders})
                    ORDER BY s.name, t.name, c.column_id
                    """,
                    tuple(set(bare_names)),
                )
                for sch, tbl, col_nm, ty_nm, ml, nullable in cur.fetchall():
                    if tbl not in picked or picked[tbl]["schema"] != sch:
                        continue
                    original = original_by_bare.get(tbl, tbl)
                    if original not in result:
                        continue
                    result[original]["columns"].append({
                        "name": col_nm,
                        "data_type": (ty_nm or "").lower(),
                        "column_type": ty_nm or "",
                        "nullable": bool(nullable),
                        "max_length": int(ml) if ml is not None else None,
                    })

                # PK
                cur.execute(
                    f"""
                    SELECT s.name, t.name, c.name
                    FROM sys.indexes i
                    JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                    JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                    JOIN sys.tables  t ON i.object_id = t.object_id
                    JOIN sys.schemas s ON t.schema_id = s.schema_id
                    WHERE i.is_primary_key = 1 AND t.name IN ({placeholders})
                    ORDER BY s.name, t.name, ic.key_ordinal
                    """,
                    tuple(set(bare_names)),
                )
                for sch, tbl, col_nm in cur.fetchall():
                    if tbl not in picked or picked[tbl]["schema"] != sch:
                        continue
                    original = original_by_bare.get(tbl, tbl)
                    if original in result:
                        result[original]["pk"].append(col_nm)
        else:
            logger.info("TableAdvisor: src_db=%s 메타 조회 미구현", src_db)

    except Exception as e:
        logger.warning("_fetch_table_meta failed: %s", e)
    finally:
        try: cur.close()
        except Exception: pass

    return result


# ══════════════════════════════════════════════════════════════
# 규칙 엔진
# ══════════════════════════════════════════════════════════════
def _fmt_bytes(n: int) -> str:
    if n >= 1024**3: return f"{n/(1024**3):.1f}GB"
    if n >= 1024**2: return f"{n/(1024**2):.0f}MB"
    return f"{n}B"


def _rule_partitioning(tables: list[str], meta: dict) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for tbl in tables:
        m = meta.get(tbl, {})
        rows = m.get("row_count", 0)
        size = m.get("size_bytes", 0)
        if rows == 0 and size == 0:
            continue
        if rows < PARTITION_ROW_THRESHOLD and size < PARTITION_SIZE_THRESHOLD:
            continue

        cols = m.get("columns", [])
        date_cols = [c for c in cols if c.get("data_type") in
                     ("date", "datetime", "datetime2", "timestamp", "datetime(6)")]
        pk = m.get("pk", [])

        if date_cols:
            part_col = date_cols[0]["name"]
            part_type = "RANGE by YEAR"
            after_sql = (
                f"-- {tbl} 테이블: 날짜 기반 파티셔닝 권장\n"
                f"ALTER TABLE {tbl}\n"
                f"PARTITION BY RANGE (YEAR({part_col})) (\n"
                f"  PARTITION p2023 VALUES LESS THAN (2024),\n"
                f"  PARTITION p2024 VALUES LESS THAN (2025),\n"
                f"  PARTITION p2025 VALUES LESS THAN (2026),\n"
                f"  PARTITION p_future VALUES LESS THAN MAXVALUE\n"
                f");"
            )
            reason_extra = f"\n• 파티션 키 후보: {part_col} (날짜형)\n• 파티션 방식: {part_type}"
        elif pk:
            part_col = pk[0]
            part_type = "HASH"
            after_sql = (
                f"-- {tbl} 테이블: PK 기반 HASH 파티셔닝\n"
                f"ALTER TABLE {tbl}\n"
                f"PARTITION BY HASH({part_col}) PARTITIONS 8;"
            )
            reason_extra = f"\n• 파티션 키: {part_col} (PK)\n• 파티션 방식: HASH 8개 (쓰기 분산)"
        else:
            continue

        recs.append(Recommendation(
            id=f"tbl.partition.{tbl}",
            category="table",
            severity="high" if rows >= PARTITION_ROW_THRESHOLD * 3 else "med",
            title=f"{tbl} 테이블 파티셔닝 권고",
            target=f"{tbl} 테이블",
            reason=(
                f"선택된 {tbl} 테이블은 파티셔닝 적용 임계값을 넘습니다.\n\n"
                f"• 현재 규모: {rows:,}행, {_fmt_bytes(size)}\n"
                f"• 파티셔닝 효과:\n"
                f"  - 쿼리 시 해당 파티션만 스캔 → 조회 10~20배 가속\n"
                f"  - 오래된 파티션 단위 드롭 가능 → 이력 관리 편의\n"
                f"  - 백업/인덱스 재구성 파티션 단위로 가능"
                f"{reason_extra}\n\n"
                f"⚠ 이관 전에만 설정 가능 (기존 대용량 테이블 파티셔닝은 다운타임 큼)"
            ),
            before=f"-- 현재: 단일 테이블 {tbl} ({rows:,}행, {_fmt_bytes(size)})",
            after=after_sql,
            estimated_impact=f"범위 조회 10~20배 가속, 이관 시간 20~30% 단축 가능",
            auto_applicable=False,
            default_action="review",
            source="rule",
            confidence=0.85,
            rule_id="tbl.partition.v1",
        ))
    return recs


def _rule_overspec_types(tables: list[str], meta: dict) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for tbl in tables:
        m = meta.get(tbl, {})
        cols = m.get("columns", [])
        if not cols:
            continue

        suspicious = []
        for c in cols:
            dt = c.get("data_type", "")
            col_type = c.get("column_type", "")
            name = c.get("name", "")
            ml = c.get("max_length")

            if dt in ("text", "mediumtext", "longtext", "ntext"):
                suspicious.append({
                    "col": name, "current": col_type,
                    "issue": "무제한 텍스트 타입 — 실제 사용 길이 확인 필요",
                    "suggest": "실측 후 VARCHAR(N) 또는 VARCHAR(255~4000) 으로 축소",
                })
            elif dt == "nvarchar" and ml == -1:
                suspicious.append({
                    "col": name, "current": "NVARCHAR(MAX)",
                    "issue": "MAX 타입 — 인덱스 생성 제약",
                    "suggest": "실사용 길이 측정 후 NVARCHAR(N) 또는 MySQL VARCHAR(N) 로 축소",
                })
            elif dt == "varchar" and ml and ml > 4000:
                suspicious.append({
                    "col": name, "current": col_type,
                    "issue": f"VARCHAR({ml}) — 과다 길이",
                    "suggest": "실사용 길이 측정 후 축소 (인덱싱 효율)",
                })

            if dt == "bigint" and name.lower() not in ("id",) and not name.lower().endswith("_id"):
                if any(kw in name.lower() for kw in ("status", "code", "type", "flag", "level")):
                    suspicious.append({
                        "col": name, "current": "BIGINT",
                        "issue": "분류 성격 컬럼인데 BIGINT — 저장 공간 낭비",
                        "suggest": "INT 또는 TINYINT 로 축소 (값 범위 확인 후)",
                    })

        if not suspicious:
            continue

        sev = "med" if len(suspicious) >= 3 else "low"
        before_lines = [f"-- {tbl} 현재 정의:"]
        after_lines  = [f"-- {tbl} 권고 (실측 후 확정):"]
        reason_items = []
        for s in suspicious[:6]:
            before_lines.append(f"  {s['col']}  {s['current']}")
            after_lines.append(f"  {s['col']}  -- {s['suggest']}")
            reason_items.append(f"• {s['col']} ({s['current']}): {s['issue']}")
        more = len(suspicious) - 6
        if more > 0:
            reason_items.append(f"... 외 {more}개 더 있음")

        recs.append(Recommendation(
            id=f"tbl.overspec.{tbl}",
            category="table",
            severity=sev,
            title=f"{tbl} 테이블 타입 오버스펙 {len(suspicious)}개 탐지",
            target=f"{tbl} 테이블",
            reason=(
                f"이관 대상 {tbl} 에서 과다 크기 타입 사용이 탐지되었습니다.\n\n"
                + "\n".join(reason_items)
                + "\n\n"
                "• 효과: 저장 공간 20~50% 감소, 인덱스 효율 개선\n"
                "• 주의: 실사용 최대 길이 측정 후 확정 (MAX(LENGTH(col)) 쿼리 권장)"
            ),
            before="\n".join(before_lines),
            after="\n".join(after_lines),
            estimated_impact=f"저장 공간 최대 30% 감소, 인덱스 성능 개선",
            auto_applicable=False,
            default_action="review",
            source="rule",
            confidence=0.75,
            rule_id="tbl.overspec.v1",
        ))
    return recs


def _rule_guid_pk(tables: list[str], meta: dict, tgt_db: str) -> list[Recommendation]:
    recs: list[Recommendation] = []
    if tgt_db not in ("mysql", "mariadb", "aurora", "tidb", "cloudsql"):
        return recs

    for tbl in tables:
        m = meta.get(tbl, {})
        pk_names = m.get("pk", [])
        cols = {c["name"]: c for c in m.get("columns", [])}

        for pk in pk_names:
            c = cols.get(pk)
            if not c:
                continue
            dt = c.get("data_type", "")
            col_type = c.get("column_type", "").lower()
            is_guid = (
                dt == "uniqueidentifier" or
                (dt in ("char", "varchar") and c.get("max_length") == 36) or
                "uniqueidentifier" in col_type
            )
            if not is_guid:
                continue

            recs.append(Recommendation(
                id=f"tbl.guid_pk.{tbl}",
                category="table",
                severity="high",
                title=f"{tbl}.{pk} — GUID PK를 BINARY(16)으로 변환 권고",
                target=f"{tbl}.{pk}",
                reason=(
                    f"UNIQUEIDENTIFIER (또는 CHAR(36) 형태 GUID) 를 MySQL 에 그대로 가져가면 "
                    f"인덱스 크기가 크고 (36바이트 → 16바이트 가능) JOIN/조회 성능이 떨어집니다.\n\n"
                    f"• 현재: {c.get('column_type', 'GUID')} — 36바이트 문자열로 저장\n"
                    f"• 권고: BINARY(16) — 2.25배 압축, 인덱스 효율 ↑\n"
                    f"• 주의:\n"
                    f"  - 변환 함수 필요: UUID_TO_BIN(guid_str) / BIN_TO_UUID(bin_val)\n"
                    f"  - 애플리케이션 코드도 함께 수정 필요 (SELECT 시 BIN_TO_UUID)\n"
                    f"  - PK 순서 보존을 원하면 UUID_TO_BIN(x, 1) (MySQL 8.0+)"
                ),
                before=f"CREATE TABLE {tbl} (\n  {pk} CHAR(36) PRIMARY KEY,\n  ...\n);",
                after=(
                    f"CREATE TABLE {tbl} (\n"
                    f"  {pk} BINARY(16) PRIMARY KEY,\n"
                    f"  ...\n"
                    f");\n\n"
                    f"-- 조회 시: SELECT BIN_TO_UUID({pk}) AS {pk}_str FROM {tbl} ...\n"
                    f"-- 입력 시: INSERT INTO {tbl} ({pk}, ...) VALUES (UUID_TO_BIN('...'), ...)"
                ),
                estimated_impact="PK 저장 공간 56% 감소, 인덱스 조회 20~30% 개선",
                auto_applicable=False,
                default_action="review",
                source="rule",
                confidence=0.90,
                rule_id="tbl.guid_pk.v1",
            ))
    return recs


def _rule_statistics_auto(tgt_db: str, tables_count: int) -> Optional[Recommendation]:
    if tables_count == 0:
        return None
    if tgt_db in ("mysql", "mariadb", "aurora", "tidb", "cloudsql"):
        return Recommendation(
            id="tbl.stats_auto.mysql",
            category="table",
            severity="low",
            title="innodb_stats_auto_recalc 활성 확인",
            target="타겟 MySQL 전역 설정",
            reason=(
                "이관 직후 옵티마이저가 최적 실행계획을 만들려면 최신 통계가 필요합니다. "
                "MySQL 은 innodb_stats_auto_recalc=ON 이 기본이지만 서버 설정 확인 권장.\n\n"
                "• 수동 갱신: ANALYZE TABLE 테이블명;\n"
                "• 이관 완료 직후 전 테이블 ANALYZE TABLE 실행 권장"
            ),
            before="# innodb_stats_auto_recalc 값 미확인",
            after=(
                "-- my.cnf 확인 또는 설정:\n"
                "[mysqld]\n"
                "innodb_stats_auto_recalc = ON\n"
                "innodb_stats_persistent   = ON\n\n"
                "-- 이관 완료 후 권장 실행:\n"
                "ANALYZE TABLE tbl1, tbl2, ...;"
            ),
            estimated_impact="이관 직후 쿼리 옵티마이저 정확도 향상",
            auto_applicable=True,
            default_action="apply",
            source="rule",
            confidence=0.95,
            rule_id="tbl.stats_auto.mysql.v1",
        )
    if tgt_db in ("mssql", "azure", "sqlserver"):
        return Recommendation(
            id="tbl.stats_auto.mssql",
            category="table",
            severity="low",
            title="AUTO_UPDATE_STATISTICS 활성 확인",
            target="타겟 MSSQL 데이터베이스",
            reason=(
                "MSSQL 은 AUTO_UPDATE_STATISTICS 가 기본 ON 이지만 DB 별로 꺼져있을 수 있어 확인 권장. "
                "이관 완료 후 UPDATE STATISTICS 일괄 실행도 권장."
            ),
            before="-- 현재 상태 확인:\nSELECT name, is_auto_update_stats_on FROM sys.databases;",
            after=(
                "-- 활성화:\n"
                "ALTER DATABASE [{DB}] SET AUTO_UPDATE_STATISTICS ON;\n\n"
                "-- 이관 완료 후 수동 갱신:\n"
                "EXEC sp_updatestats;"
            ),
            estimated_impact="쿼리 옵티마이저 정확도 향상",
            auto_applicable=False,
            default_action="apply",
            source="rule",
            confidence=0.90,
            rule_id="tbl.stats_auto.mssql.v1",
        )
    return None


# ══════════════════════════════════════════════════════════════
# TableAdvisor 본체
# ══════════════════════════════════════════════════════════════
class TableAdvisor(BaseAdvisor):
    """테이블 구조 최적화 권고."""
    category = "table"

    def supports(self, src_db: str, tgt_db: str) -> bool:
        supported = {"mysql", "mariadb", "aurora", "tidb", "cloudsql",
                     "mssql", "azure", "sqlserver"}
        return (src_db or "").lower() in supported or (tgt_db or "").lower() in supported

    def analyze(self, selection: JobSelection, context: AnalysisContext) -> list[Recommendation]:
        tables = selection.tables
        if not tables:
            return []

        logger.info("TableAdvisor: 분석 시작 (tables=%d)", len(tables))
        meta = _fetch_table_meta(tables, context)

        recs: list[Recommendation] = []
        tgt_db = (context.tgt_db or "").lower()

        if meta:
            recs.extend(_rule_partitioning(tables, meta))
            recs.extend(_rule_overspec_types(tables, meta))
            recs.extend(_rule_guid_pk(tables, meta, tgt_db))
        else:
            logger.info("TableAdvisor: 소스 메타 없음 → 일반 권고만")

        stats_rec = _rule_statistics_auto(tgt_db, len(tables))
        if stats_rec:
            recs.append(stats_rec)

        logger.info("TableAdvisor: %d개 권고 생성", len(recs))
        return recs

    def estimate_tokens(self, selection: JobSelection, mode: AnalysisMode) -> dict:
        if mode == "smart":
            return {"tokens_in": 0, "tokens_out": 0}
        elif mode == "hybrid":
            candidates = max(1, len(selection.tables) // 10)
            return {"tokens_in": 2500 * candidates, "tokens_out": 1500 * candidates}
        else:
            return {"tokens_in": 2500 * len(selection.tables),
                    "tokens_out": 1500 * len(selection.tables)}
