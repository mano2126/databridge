"""
app/core/advisor/server_advisor.py — 타겟 DB 서버 설정 Advisor
v88 P2 (2026-04-23)

역할:
    선택된 이관 대상의 총 크기/특성을 기반으로
    타겟 DB 서버 설정(my.cnf 등) 최적화 권고를 생성한다.

P2 범위 (이번 세션):
    - MySQL 타겟 기준 규칙 기반 7개 권고 (smart 모드)
    - 소스 DB 없이도 동작 (fallback 추정값 사용)
    - AI 호출 없음 — 안정성과 비용 0 보장

P3 이후 확장:
    - hybrid/deep 모드에서 AI로 "놓친 파라미터" 질의
    - PostgreSQL 타겟 (postgresql.conf)
    - MSSQL 타겟 (sp_configure + startup parameters)
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

logger = logging.getLogger("databridge.advisor.server")


# ══════════════════════════════════════════════════════════════
# 단위 변환 유틸
# ══════════════════════════════════════════════════════════════
def _fmt_bytes(n: int) -> str:
    """바이트 → 사람이 읽는 단위 (G/M). my.cnf 스타일."""
    if n >= 1024 ** 3:
        gb = n / (1024 ** 3)
        # 정수로 떨어지면 "5G", 아니면 "5.2G"
        return f"{gb:.0f}G" if gb == int(gb) else f"{gb:.1f}G"
    if n >= 1024 ** 2:
        return f"{n // (1024 ** 2)}M"
    return f"{n}K"


def _gb_to_bytes(gb: float) -> int:
    return int(gb * 1024 ** 3)


# ══════════════════════════════════════════════════════════════
# 테이블 크기 추정
# ══════════════════════════════════════════════════════════════
def _estimate_selection_size(
    selection: JobSelection,
    context: AnalysisContext,
) -> dict:
    """
    선택된 이관 대상의 총 크기/특성을 추정한다.

    소스 DB 연결이 있으면 실제 값 조회, 없으면 보수적 추정값 사용.

    Returns:
        {
            "total_bytes": int,       # 전체 데이터 크기 (바이트)
            "total_rows":  int,       # 전체 행 수
            "has_blob":    bool,      # BLOB/TEXT 컬럼 존재 여부 (추정)
            "source":      str,       # "measured" | "estimated"
        }
    """
    result = {
        "total_bytes": 0,
        "total_rows":  0,
        "has_blob":    False,
        "source":      "estimated",
    }

    # 소스 DB 연결이 있으면 실제 값 조회 시도
    if context.src_conn is not None and selection.tables:
        try:
            result = _measure_from_src(selection.tables, context)
            result["source"] = "measured"
            return result
        except Exception as e:
            logger.warning("소스 DB 측정 실패, 추정치로 fallback: %s", e)

    # Fallback: 테이블당 평균 1M rows, row당 평균 500 bytes 로 추정
    tbl_n = len(selection.tables)
    result["total_rows"]  = tbl_n * 1_000_000
    result["total_bytes"] = tbl_n * 1_000_000 * 500   # 약 0.5GB/테이블
    # 오브젝트가 많으면 BLOB 가능성도 있다고 가정 (보수적)
    result["has_blob"]    = (tbl_n >= 10) or (selection.total_objects >= 5)
    return result


def _measure_from_src(tables: list[str], context: AnalysisContext) -> dict:
    """
    소스 DB 에서 선택 테이블의 총 크기/행 수 조회.

    DB별 쿼리가 다르므로 src_db 분기. 실패하면 상위에서 fallback.
    """
    src_db = (context.src_db or "").lower()
    conn = context.src_conn
    total_bytes = 0
    total_rows = 0
    has_blob = False

    cur = conn.cursor()
    try:
        if src_db in ("mysql", "mariadb", "aurora", "tidb", "cloudsql"):
            # information_schema 는 정확도 떨어질 수 있지만 ms 안에 끝남
            placeholders = ",".join(["%s"] * len(tables))
            cur.execute(
                f"""
                SELECT
                    COALESCE(SUM(data_length + index_length), 0) AS bytes,
                    COALESCE(SUM(table_rows), 0) AS rows
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                  AND table_name IN ({placeholders})
                """,
                tuple(tables),
            )
            row = cur.fetchone()
            if row:
                total_bytes = int(row[0] or 0)
                total_rows  = int(row[1] or 0)

            # BLOB/TEXT 컬럼 존재 여부
            cur.execute(
                f"""
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name IN ({placeholders})
                  AND data_type IN ('blob','mediumblob','longblob','text','mediumtext','longtext','json')
                """,
                tuple(tables),
            )
            has_blob = bool(cur.fetchone()[0])

        elif src_db in ("mssql", "azure", "sqlserver"):
            # sp_spaceused 여러 번 호출 대신 sys.dm_db_partition_stats 사용
            placeholders = ",".join(["?"] * len(tables))
            cur.execute(
                f"""
                SELECT
                    SUM(ps.reserved_page_count) * 8.0 * 1024 AS bytes,
                    SUM(CASE WHEN ps.index_id < 2 THEN ps.row_count ELSE 0 END) AS rows
                FROM sys.dm_db_partition_stats ps
                JOIN sys.tables t ON ps.object_id = t.object_id
                WHERE t.name IN ({placeholders})
                """,
                tuple(tables),
            )
            row = cur.fetchone()
            if row:
                total_bytes = int(row[0] or 0)
                total_rows  = int(row[1] or 0)

            cur.execute(
                f"""
                SELECT COUNT(*) FROM sys.columns c
                JOIN sys.tables t ON c.object_id = t.object_id
                JOIN sys.types ty ON c.user_type_id = ty.user_type_id
                WHERE t.name IN ({placeholders})
                  AND ty.name IN ('image','varbinary','varchar(max)','nvarchar(max)','text','ntext','xml')
                """,
                tuple(tables),
            )
            has_blob = bool(cur.fetchone()[0])

        # PostgreSQL, Oracle 등은 P3+ 에서 추가
        else:
            logger.info("src_db=%s 측정 미구현, 추정치 사용", src_db)
            raise NotImplementedError(f"measure not implemented for {src_db}")
    finally:
        try:
            cur.close()
        except Exception:
            pass

    return {
        "total_bytes": total_bytes,
        "total_rows":  total_rows,
        "has_blob":    has_blob,
        "source":      "measured",
    }


# ══════════════════════════════════════════════════════════════
# 규칙 엔진 — MySQL 타겟용
# ══════════════════════════════════════════════════════════════
def _rules_for_mysql_target(stats: dict) -> list[Recommendation]:
    """
    MySQL 타겟 서버 설정 권고 생성 (규칙 기반, AI 없음).

    stats:
        { total_bytes, total_rows, has_blob, source }
    """
    recs: list[Recommendation] = []
    total_gb = stats["total_bytes"] / (1024 ** 3)
    size_desc = f"선택 대상 총 {_fmt_bytes(stats['total_bytes'])}, {stats['total_rows']:,} 행"
    if stats["source"] == "estimated":
        size_desc += " (추정치)"

    # ───────────────────────────────────────────────────
    # 1. innodb_buffer_pool_size — 가장 중요 (HIGH)
    # ───────────────────────────────────────────────────
    # 권장값 = 총 데이터 × 0.7 (서버 RAM 의 최대 70%)
    # 단, 최소 128M, 최대 권장 64G 로 캡핑
    bp_gb = max(min(total_gb * 0.7, 64.0), 0.125)  # 최소 128M
    if total_gb < 1:
        bp_value = "1G"  # 너무 작아도 최소 1G 는 권장
    else:
        bp_value = _fmt_bytes(_gb_to_bytes(bp_gb))

    recs.append(Recommendation(
        id="srv.mysql.buffer_pool",
        category="server",
        severity="high",
        title="innodb_buffer_pool_size 증설 권고",
        target="타겟 MySQL my.cnf",
        reason=(
            f"InnoDB 버퍼 풀은 테이블/인덱스를 메모리에 캐시하는 핵심 영역입니다. "
            f"기본값(128M)은 대부분의 이관 규모에 턱없이 부족합니다.\n\n"
            f"• 측정 근거: {size_desc}\n"
            f"• 공식: 전체 데이터 × 0.7 (서버 RAM 의 70% 이내)\n"
            f"• 효과: 이관 시간 30~50% 단축, 이관 후 캐시 hit rate 대폭 향상"
        ),
        before="# innodb_buffer_pool_size = 128M   (MySQL 기본값)",
        after=f"innodb_buffer_pool_size = {bp_value}",
        estimated_impact="이관 시간 30~50% 단축, 이관 후 조회 20%+ 개선",
        auto_applicable=False,   # my.cnf 수정은 서버 재시작 필요 → 수동
        default_action="apply",
        source="rule",
        confidence=0.95,
        rule_id="srv.mysql.buffer_pool.v1",
    ))

    # ───────────────────────────────────────────────────
    # 2. innodb_log_file_size — 이관용 대용량 INSERT (MED)
    # ───────────────────────────────────────────────────
    # 총 데이터의 10% 권장, 최소 256M, 최대 8G
    log_gb = max(min(total_gb * 0.10, 8.0), 0.25)
    log_value = _fmt_bytes(_gb_to_bytes(log_gb))

    recs.append(Recommendation(
        id="srv.mysql.log_file",
        category="server",
        severity="med",
        title="innodb_log_file_size 증설 권고 (대량 INSERT 대비)",
        target="타겟 MySQL my.cnf",
        reason=(
            f"로그 파일이 작으면 이관 중 체크포인트가 잦아져서 성능이 떨어집니다. "
            f"대량 INSERT 환경에서는 로그 파일을 충분히 크게 해야 합니다.\n\n"
            f"• 공식: 전체 데이터의 10% (최소 256M, 최대 8G)\n"
            f"• 주의: 이 값을 변경 후 첫 시작 시 MySQL 이 로그 파일을 재생성하므로 "
            f"기존 로그가 clean 상태(정상 shutdown)여야 합니다."
        ),
        before="# innodb_log_file_size = 48M   (MySQL 기본값)",
        after=f"innodb_log_file_size = {log_value}",
        estimated_impact="이관 중 체크포인트 대기 감소 → 10~20% 가속",
        auto_applicable=False,
        default_action="apply",
        source="rule",
        confidence=0.90,
        rule_id="srv.mysql.log_file.v1",
    ))

    # ───────────────────────────────────────────────────
    # 3. max_allowed_packet — BLOB/TEXT 있을 때만 (MED)
    # ───────────────────────────────────────────────────
    if stats["has_blob"]:
        recs.append(Recommendation(
            id="srv.mysql.max_packet",
            category="server",
            severity="med",
            title="max_allowed_packet 확대 권고 (BLOB/TEXT 대응)",
            target="타겟 MySQL my.cnf",
            reason=(
                "선택 대상에 BLOB/TEXT/JSON 컬럼이 존재합니다. "
                "기본 max_allowed_packet(16M 또는 64M)은 큰 BLOB 행 하나로도 "
                "`Packet too large` 에러를 일으킬 수 있습니다.\n\n"
                "• 권장: 256M (BLOB 컬럼 최대 길이의 2배 이상)\n"
                "• 주의: 클라이언트 측 설정도 함께 올려야 효과 있음"
            ),
            before="# max_allowed_packet = 16M   (MySQL 기본값)",
            after="max_allowed_packet = 256M",
            estimated_impact="BLOB/TEXT 행 이관 실패 방지 (0 → 안정)",
            auto_applicable=False,
            default_action="apply",
            source="rule",
            confidence=0.92,
            rule_id="srv.mysql.max_packet.v1",
        ))

    # ───────────────────────────────────────────────────
    # 4. innodb_flush_log_at_trx_commit — 이관 동안 임시 튜닝 (HIGH)
    # ───────────────────────────────────────────────────
    recs.append(Recommendation(
        id="srv.mysql.flush_log",
        category="server",
        severity="high",
        title="innodb_flush_log_at_trx_commit=2 (이관 중 한시적)",
        target="타겟 MySQL SET GLOBAL (런타임)",
        reason=(
            "기본값 1 은 매 트랜잭션마다 디스크로 flush → 대량 INSERT 시 가장 큰 병목. "
            "이관 동안만 2 로 낮추면 1초 단위 flush 로 전환되어 성능 2~5배 향상.\n\n"
            "• DataBridge 가 이관 시작 시 자동으로 2 로 변경\n"
            "• 이관 완료 후 자동으로 1 로 복원 (안전 보장)\n"
            "• 이관 중 서버 크래시 발생 시 최대 1초분 트랜잭션 손실 가능성 — "
            "  소스 DB가 정상이므로 재이관으로 복구 가능"
        ),
        before="innodb_flush_log_at_trx_commit = 1   (안전 우선)",
        after="# 이관 중: SET GLOBAL innodb_flush_log_at_trx_commit = 2;\n# 이관 완료 후: SET GLOBAL innodb_flush_log_at_trx_commit = 1;",
        estimated_impact="대량 INSERT 2~5배 가속 (이관 시간에 가장 큰 영향)",
        auto_applicable=True,    # 런타임 변경 + 자동 복원 가능
        default_action="apply",
        source="rule",
        confidence=0.98,
        rule_id="srv.mysql.flush_log.v1",
    ))

    # ───────────────────────────────────────────────────
    # 5. character_set_server / collation_server (HIGH — 안 맞으면 한글 깨짐)
    # ───────────────────────────────────────────────────
    recs.append(Recommendation(
        id="srv.mysql.charset",
        category="server",
        severity="high",
        title="character_set_server=utf8mb4 설정 확인",
        target="타겟 MySQL my.cnf",
        reason=(
            "한국어/이모지 안전을 위해 utf8mb4 + utf8mb4_unicode_ci 권장. "
            "기본값이 latin1 이면 한글이 깨집니다.\n\n"
            "• utf8mb4 는 MySQL 5.5.3+ 부터 지원 (표준)\n"
            "• utf8 (3바이트) 대신 utf8mb4 (4바이트) 를 사용해야 이모지 안전"
        ),
        before="# (미설정 시 latin1 또는 MySQL 5.7 기본 utf8)",
        after=(
            "[mysqld]\n"
            "character_set_server = utf8mb4\n"
            "collation_server     = utf8mb4_unicode_ci\n"
            "\n[client]\n"
            "default-character-set = utf8mb4"
        ),
        estimated_impact="한글/이모지 저장 안정성 확보 (데이터 무결성 직결)",
        auto_applicable=False,
        default_action="apply",
        source="rule",
        confidence=0.99,
        rule_id="srv.mysql.charset.v1",
    ))

    # ───────────────────────────────────────────────────
    # 6. autocommit=0 + 명시 COMMIT 모드 (LOW — 엔진이 batch 단위로 처리)
    # ───────────────────────────────────────────────────
    recs.append(Recommendation(
        id="srv.mysql.autocommit",
        category="server",
        severity="low",
        title="이관 중 autocommit=0 + 배치 COMMIT 권고",
        target="DataBridge 이관 엔진 옵션",
        reason=(
            "DataBridge 가 이미 배치 단위(form.batchSize)로 COMMIT 을 제어하므로 "
            "MySQL autocommit=0 설정이 동반되면 I/O 효율이 더 높아집니다.\n\n"
            "• 이 권고는 DataBridge 엔진이 자동 적용\n"
            "• my.cnf 수정 불필요"
        ),
        before="# autocommit=1 (기본) — 매 INSERT 마다 COMMIT",
        after="# autocommit=0 (이관 중) → 배치 N rows 마다 COMMIT",
        estimated_impact="I/O 횟수 감소 → 5~10% 가속",
        auto_applicable=True,    # 엔진이 자동 제어
        default_action="apply",
        source="rule",
        confidence=0.85,
        rule_id="srv.mysql.autocommit.v1",
    ))

    # ───────────────────────────────────────────────────
    # 7. tmp_table_size / max_heap_table_size (LOW — 데이터 큼 때 필요)
    # ───────────────────────────────────────────────────
    if total_gb >= 10:
        tmp_value = "512M"
    elif total_gb >= 1:
        tmp_value = "256M"
    else:
        tmp_value = None   # 작은 이관은 기본값으로 충분 → 권고 안 함

    if tmp_value:
        recs.append(Recommendation(
            id="srv.mysql.tmp_table",
            category="server",
            severity="low",
            title=f"tmp_table_size / max_heap_table_size={tmp_value} 권고",
            target="타겟 MySQL my.cnf",
            reason=(
                "이관 후 대용량 ORDER BY / GROUP BY / UNION 쿼리 시 임시 테이블이 "
                "디스크로 떨어지는 걸 방지. 소스 SP/View 에 집계 쿼리가 있으면 효과적.\n\n"
                f"• 선택 대상 총 {_fmt_bytes(stats['total_bytes'])} 기준 권장값: {tmp_value}\n"
                f"• tmp_table_size 와 max_heap_table_size 는 동일하게 설정해야 함"
            ),
            before="# tmp_table_size = 16M, max_heap_table_size = 16M (MySQL 기본값)",
            after=f"tmp_table_size     = {tmp_value}\nmax_heap_table_size = {tmp_value}",
            estimated_impact="이관 후 집계 쿼리 10~30% 개선 (Disk tmp → Memory)",
            auto_applicable=False,
            default_action="review",
            source="rule",
            confidence=0.80,
            rule_id="srv.mysql.tmp_table.v1",
        ))

    return recs


# ══════════════════════════════════════════════════════════════
# ServerAdvisor 본체
# ══════════════════════════════════════════════════════════════
class ServerAdvisor(BaseAdvisor):
    """
    타겟 DB 서버 설정 최적화 권고.

    현재 지원:
        - MySQL / MariaDB / Aurora / TiDB / CloudSQL (MySQL 호환)

    미지원 (P3+ 예정):
        - PostgreSQL (postgresql.conf)
        - MSSQL      (sp_configure + startup params)
    """

    category = "server"

    _MYSQL_FAMILY = {"mysql", "mariadb", "aurora", "tidb", "cloudsql"}

    def supports(self, src_db: str, tgt_db: str) -> bool:
        return (tgt_db or "").lower() in self._MYSQL_FAMILY

    def analyze(
        self,
        selection: JobSelection,
        context: AnalysisContext,
    ) -> list[Recommendation]:
        tgt = (context.tgt_db or "").lower()
        if tgt not in self._MYSQL_FAMILY:
            # 미지원 타겟: 빈 리스트 반환 (AdvisorPanel 이 "해당 카테고리 권고 없음" 표시)
            logger.info("ServerAdvisor: 타겟 %s 미지원 (P3+ 예정)", tgt)
            return []

        # 선택 대상 측정/추정
        stats = _estimate_selection_size(selection, context)
        logger.info(
            "ServerAdvisor 분석: target=%s total=%s rows=%s blob=%s source=%s",
            tgt,
            _fmt_bytes(stats["total_bytes"]),
            stats["total_rows"],
            stats["has_blob"],
            stats["source"],
        )

        # MySQL 계열 규칙 적용
        recs = _rules_for_mysql_target(stats)

        # 모드별 조정 (P2 에서는 규칙만 — 모드 영향 적음)
        # hybrid/deep 모드는 P3+ 에서 AI 질의로 추가 권고 생성
        return recs

    def estimate_tokens(
        self,
        selection: JobSelection,
        mode: AnalysisMode,
    ) -> dict:
        """
        ServerAdvisor 는 규칙 기반이라 smart 모드에서 AI 토큰 0.
        hybrid/deep 모드에서는 "추가 파라미터 있나?" 1회 질의 (P3+).
        """
        if mode == "smart":
            return {"tokens_in": 0, "tokens_out": 0}
        elif mode == "hybrid":
            return {"tokens_in": 1500, "tokens_out": 500}
        else:  # deep
            # 각 파라미터당 AI 재산정 (7 파라미터)
            return {"tokens_in": 1500 * 7, "tokens_out": 500 * 7}
