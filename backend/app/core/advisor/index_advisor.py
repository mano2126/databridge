"""
app/core/advisor/index_advisor.py — 인덱스 전략 Advisor
v88 P5 (2026-04-23)

역할:
    선택된 테이블의 인덱스 전략을 종합 분석한다.
    쿼리 로그가 없어도 SP/Function/View 의 WHERE/JOIN 절 정적 분석으로
    "아예 권고 못 함" 상황이 없게 한다.

P5 범위:
    1. 필수 인덱스 도출 — SP/View 의 WHERE/JOIN/ORDER BY 컬럼 기반
    2. 중복 인덱스 탐지 — (a,b) 와 (a) 공존 → 후자 제거
    3. 과다 인덱스 경고 — 테이블당 인덱스 > 8개 시 INSERT 성능 저하
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Optional

from app.core.advisor.base_advisor import (
    BaseAdvisor,
    JobSelection,
    AnalysisContext,
    AnalysisMode,
    Recommendation,
)

logger = logging.getLogger("databridge.advisor.index")


# ══════════════════════════════════════════════════════════════
# 컬럼 참조 추출 (SP/View DDL 에서)
# ══════════════════════════════════════════════════════════════
_RE_WHERE_COL = re.compile(
    r"""
    \bWHERE\b\s+(?:[\w.]+\.)?(\w+)
    \s*(?:=|<|>|<=|>=|<>|!=|LIKE|IN|BETWEEN)
    """,
    re.IGNORECASE | re.VERBOSE,
)
_RE_AND_COL = re.compile(
    r"""
    \bAND\b\s+(?:[\w.]+\.)?(\w+)
    \s*(?:=|<|>|<=|>=|<>|!=|LIKE|IN|BETWEEN)
    """,
    re.IGNORECASE | re.VERBOSE,
)
_RE_JOIN_ON = re.compile(
    r"""
    \bJOIN\s+\w+(?:\s+\w+)?\s+ON\s+
    (?:[\w.]+\.)?(\w+)
    \s*=
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)
_RE_ORDER_BY = re.compile(
    r"\bORDER\s+BY\s+([\w., ]+?)(?:\bASC|\bDESC|\bLIMIT|\bOFFSET|\b;|\)|$)",
    re.IGNORECASE,
)
_RE_GROUP_BY = re.compile(
    r"\bGROUP\s+BY\s+([\w., ]+?)(?:\bHAVING|\bORDER|\bLIMIT|\b;|\)|$)",
    re.IGNORECASE,
)

_RESERVED = {
    "select", "from", "where", "and", "or", "not", "in", "exists",
    "between", "like", "is", "null", "case", "when", "then", "else", "end",
    "by", "group", "order", "having", "limit", "offset", "union", "all",
    "distinct", "top", "as", "on", "join", "inner", "left", "right", "outer", "full",
    "into", "values", "set", "update", "insert", "delete", "table", "create",
    "begin", "rollback", "commit", "declare", "return",
}


def _normalize_col(name: str) -> str:
    n = (name or "").strip().strip(",").strip()
    if "." in n:
        n = n.split(".")[-1]
    return n.lower()


def _extract_cols_from_list(s: str) -> list[str]:
    out = []
    for part in s.split(","):
        p = part.strip().split()
        if not p:
            continue
        c = _normalize_col(p[0])
        if c and c not in _RESERVED and not c.isdigit():
            out.append(c)
    return out


# ══════════════════════════════════════════════════════════════
# 컬럼 사용 통계 수집
# ══════════════════════════════════════════════════════════════
def _collect_column_usage(objects_ddls: dict[str, str]) -> dict[str, dict]:
    stats: dict[str, dict] = defaultdict(
        lambda: {"where": 0, "join": 0, "order": 0, "group": 0, "objects": set()}
    )

    for obj_key, ddl in objects_ddls.items():
        if not ddl:
            continue
        for m in _RE_WHERE_COL.findall(ddl):
            c = _normalize_col(m)
            if c and c not in _RESERVED:
                stats[c]["where"] += 1
                stats[c]["objects"].add(obj_key)
        for m in _RE_AND_COL.findall(ddl):
            c = _normalize_col(m)
            if c and c not in _RESERVED:
                stats[c]["where"] += 1
                stats[c]["objects"].add(obj_key)
        for m in _RE_JOIN_ON.findall(ddl):
            c = _normalize_col(m)
            if c and c not in _RESERVED:
                stats[c]["join"] += 1
                stats[c]["objects"].add(obj_key)
        for m in _RE_ORDER_BY.findall(ddl):
            for c in _extract_cols_from_list(m):
                stats[c]["order"] += 1
                stats[c]["objects"].add(obj_key)
        for m in _RE_GROUP_BY.findall(ddl):
            for c in _extract_cols_from_list(m):
                stats[c]["group"] += 1
                stats[c]["objects"].add(obj_key)

    return stats


# ══════════════════════════════════════════════════════════════
# 테이블 메타/인덱스 조회
# ══════════════════════════════════════════════════════════════
def _fetch_table_columns_and_indexes(
    tables: list[str],
    context: AnalysisContext,
) -> dict[str, dict]:
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
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name IN ({placeholders})
                ORDER BY table_name, ordinal_position
                """,
                tuple(tables),
            )
            for tbl, col in cur.fetchall():
                result.setdefault(tbl, {"columns": [], "indexes": [], "pk": []})
                result[tbl]["columns"].append(col.lower())

            cur.execute(
                f"""
                SELECT table_name, index_name, column_name, non_unique, seq_in_index
                FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND table_name IN ({placeholders})
                ORDER BY table_name, index_name, seq_in_index
                """,
                tuple(tables),
            )
            idx_build: dict[tuple, dict] = {}
            for tbl, idx_name, col, non_unique, seq in cur.fetchall():
                key = (tbl, idx_name)
                if key not in idx_build:
                    idx_build[key] = {
                        "name": idx_name,
                        "columns": [],
                        "unique": (non_unique == 0),
                        "is_pk":  (idx_name == "PRIMARY"),
                    }
                idx_build[key]["columns"].append(col.lower())

            for (tbl, _), idx in idx_build.items():
                result.setdefault(tbl, {"columns": [], "indexes": [], "pk": []})
                if idx["is_pk"]:
                    result[tbl]["pk"] = idx["columns"]
                else:
                    result[tbl]["indexes"].append(idx)

        elif src_db in ("mssql", "azure", "sqlserver"):
            # v88 hotfix3 (2026-04-23): 스키마 인식
            bare_names: list[str] = []
            schema_hints: dict[str, Optional[str]] = {}
            original_by_bare: dict[str, str] = {}
            for t in tables:
                cleaned = (t or "").replace("[", "").replace("]", "")
                if "." in cleaned:
                    s, b = cleaned.split(".", 1)
                    schema_hints[b] = s
                else:
                    b = cleaned
                    schema_hints.setdefault(b, None)
                bare_names.append(b)
                original_by_bare[b] = t

            if not bare_names:
                return result

            placeholders = ",".join(["?"] * len(set(bare_names)))

            # 어느 (schema, bare) 조합이 요청과 매치되는지 먼저 확정
            cur.execute(
                f"""
                SELECT s.name, t.name
                FROM sys.tables t
                JOIN sys.schemas s ON t.schema_id = s.schema_id
                WHERE t.name IN ({placeholders})
                """,
                tuple(set(bare_names)),
            )
            picked_tables: dict[str, str] = {}  # bare → schema
            for sch, tbl in cur.fetchall():
                hint = schema_hints.get(tbl)
                if hint is None or hint.lower() == sch.lower():
                    if tbl not in picked_tables:
                        picked_tables[tbl] = sch

            # 각 테이블 초기화
            for tbl, sch in picked_tables.items():
                original = original_by_bare.get(tbl, tbl)
                result[original] = {"columns": [], "indexes": [], "pk": [], "_schema": sch}

            # 컬럼
            cur.execute(
                f"""
                SELECT s.name, t.name, c.name
                FROM sys.columns c
                JOIN sys.tables  t ON c.object_id = t.object_id
                JOIN sys.schemas s ON t.schema_id = s.schema_id
                WHERE t.name IN ({placeholders})
                ORDER BY s.name, t.name, c.column_id
                """,
                tuple(set(bare_names)),
            )
            for sch, tbl, col in cur.fetchall():
                if picked_tables.get(tbl) != sch:
                    continue
                original = original_by_bare.get(tbl, tbl)
                if original in result:
                    result[original]["columns"].append(col.lower())

            # 인덱스
            cur.execute(
                f"""
                SELECT s.name, t.name, i.name, c.name, i.is_unique, i.is_primary_key, ic.key_ordinal
                FROM sys.indexes i
                JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                JOIN sys.tables  t ON i.object_id = t.object_id
                JOIN sys.schemas s ON t.schema_id = s.schema_id
                WHERE t.name IN ({placeholders}) AND i.type > 0
                ORDER BY s.name, t.name, i.name, ic.key_ordinal
                """,
                tuple(set(bare_names)),
            )
            idx_build2: dict[tuple, dict] = {}
            for sch, tbl, idx_name, col, unique, is_pk, _ in cur.fetchall():
                if picked_tables.get(tbl) != sch:
                    continue
                original = original_by_bare.get(tbl, tbl)
                key = (original, idx_name)
                if key not in idx_build2:
                    idx_build2[key] = {
                        "name": idx_name or "(unnamed)",
                        "columns": [],
                        "unique": bool(unique),
                        "is_pk":  bool(is_pk),
                    }
                idx_build2[key]["columns"].append(col.lower())

            for (original, _), idx in idx_build2.items():
                if original not in result:
                    continue
                if idx["is_pk"]:
                    result[original]["pk"] = idx["columns"]
                else:
                    result[original]["indexes"].append(idx)

    except Exception as e:
        logger.warning("_fetch_table_columns_and_indexes failed: %s", e)
    finally:
        try: cur.close()
        except Exception: pass

    return result


# ══════════════════════════════════════════════════════════════
# 규칙 엔진
# ══════════════════════════════════════════════════════════════
def _rule_missing_indexes(
    tables: list[str], table_meta: dict, col_usage: dict,
) -> list[Recommendation]:
    recs: list[Recommendation] = []

    for tbl in tables:
        tm = table_meta.get(tbl)
        if not tm:
            continue

        indexed_first_cols = set()
        for idx in tm.get("indexes", []):
            if idx["columns"]:
                indexed_first_cols.add(idx["columns"][0])
        pk = tm.get("pk", [])
        if pk:
            indexed_first_cols.add(pk[0])

        table_cols = set(tm.get("columns", []))

        suggested = []
        for col, usage in col_usage.items():
            if col not in table_cols:
                continue
            if col in indexed_first_cols:
                continue
            score = usage["where"] * 3 + usage["join"] * 4
            if score >= 3:
                suggested.append({
                    "col": col, "score": score,
                    "where_cnt": usage["where"], "join_cnt": usage["join"],
                    "objs": len(usage["objects"]),
                })

        if not suggested:
            continue

        suggested.sort(key=lambda x: -x["score"])
        suggested = suggested[:5]

        ddl_lines = []
        reason_lines = []
        for s in suggested:
            col = s["col"]
            idx_name = f"idx_{tbl}_{col}"
            ddl_lines.append(f"CREATE INDEX {idx_name} ON {tbl}({col});")
            reason_lines.append(
                f"• {col}: WHERE {s['where_cnt']}회, JOIN {s['join_cnt']}회, "
                f"{s['objs']}개 오브젝트에서 사용 (score={s['score']})"
            )

        recs.append(Recommendation(
            id=f"idx.missing.{tbl}",
            category="index",
            severity="high" if len(suggested) >= 3 else "med",
            title=f"{tbl} — 필수 인덱스 {len(suggested)}개 누락 추정",
            target=f"{tbl} 테이블",
            reason=(
                f"선택된 SP/Function/View 의 WHERE/JOIN 절 분석 결과, "
                f"{tbl} 테이블에서 인덱스가 필요해 보이는 컬럼이 탐지되었습니다.\n\n"
                + "\n".join(reason_lines)
                + "\n\n"
                "⚠ 이관 전에 인덱스를 만들면 이관 시간이 길어집니다. "
                "DataBridge 는 이관 전 드롭 / 이관 후 재생성 옵션을 제공 — "
                "권고 수용 시 이관 완료 후 자동 생성"
            ),
            before=f"-- {tbl} 현재 인덱스 선행 컬럼: {sorted(indexed_first_cols) or '(없음)'}",
            after="\n".join(ddl_lines),
            estimated_impact="해당 쿼리들 10~100배 가속 (풀스캔 → 인덱스 스캔)",
            auto_applicable=True,
            default_action="apply",
            source="rule",
            confidence=0.80,
            rule_id="idx.missing.v1",
        ))

    return recs


def _rule_duplicate_indexes(tables: list[str], table_meta: dict) -> list[Recommendation]:
    recs: list[Recommendation] = []

    for tbl in tables:
        tm = table_meta.get(tbl)
        if not tm:
            continue
        indexes = tm.get("indexes", [])
        if len(indexes) < 2:
            continue

        dup_pairs = []
        for i, idx_a in enumerate(indexes):
            for idx_b in indexes[i + 1:]:
                cols_a = idx_a["columns"]
                cols_b = idx_b["columns"]
                shorter, longer = (cols_a, cols_b) if len(cols_a) <= len(cols_b) else (cols_b, cols_a)
                if longer[:len(shorter)] == shorter:
                    dup_pairs.append({
                        "short": shorter,
                        "short_name": idx_a["name"] if cols_a == shorter else idx_b["name"],
                        "long": longer,
                        "long_name": idx_a["name"] if cols_a == longer else idx_b["name"],
                    })

        if not dup_pairs:
            continue

        ddl_lines = []
        reason_lines = []
        for p in dup_pairs[:5]:
            ddl_lines.append(f"-- 중복: {p['short_name']} ({','.join(p['short'])}) — {p['long_name']} ({','.join(p['long'])}) 의 prefix")
            ddl_lines.append(f"DROP INDEX {p['short_name']} ON {tbl};")
            reason_lines.append(f"• {p['short_name']} ({','.join(p['short'])}) → {p['long_name']} 로 대체 가능")

        recs.append(Recommendation(
            id=f"idx.duplicate.{tbl}",
            category="index",
            severity="low",
            title=f"{tbl} — 중복 인덱스 {len(dup_pairs)}건",
            target=f"{tbl} 테이블",
            reason=(
                f"{tbl} 테이블에 prefix 중복인 인덱스가 있습니다. "
                f"더 긴 인덱스가 더 짧은 인덱스를 완전히 커버하므로, 짧은 쪽은 제거해도 성능 영향 없고 "
                f"저장 공간과 INSERT/UPDATE 오버헤드가 감소합니다.\n\n"
                + "\n".join(reason_lines)
            ),
            before=f"-- {tbl} 현재 인덱스 {len(indexes)}개",
            after="\n".join(ddl_lines),
            estimated_impact="INSERT/UPDATE 3~10% 가속, 저장 공간 감소",
            auto_applicable=True,
            default_action="apply",
            source="rule",
            confidence=0.95,
            rule_id="idx.duplicate.v1",
        ))

    return recs


def _rule_too_many_indexes(tables: list[str], table_meta: dict) -> list[Recommendation]:
    recs: list[Recommendation] = []
    THRESHOLD = 8

    for tbl in tables:
        tm = table_meta.get(tbl)
        if not tm:
            continue
        idx_count = len(tm.get("indexes", []))
        if idx_count < THRESHOLD:
            continue

        idx_names = [i["name"] for i in tm.get("indexes", [])]

        recs.append(Recommendation(
            id=f"idx.too_many.{tbl}",
            category="index",
            severity="med",
            title=f"{tbl} — 인덱스 {idx_count}개 (과다 경고)",
            target=f"{tbl} 테이블",
            reason=(
                f"{tbl} 테이블에 보조 인덱스가 {idx_count}개 있습니다. "
                f"인덱스는 조회에는 도움이 되지만 INSERT/UPDATE/DELETE 에 오버헤드가 누적됩니다.\n\n"
                f"• 테이블당 권장 최대: ~{THRESHOLD}개\n"
                f"• 현재: {', '.join(idx_names[:10])}"
                + (f" 외 {idx_count-10}개" if idx_count > 10 else "") + "\n\n"
                f"권고:\n"
                f"1. 각 인덱스의 실제 사용 여부 측정 (쿼리 로그 또는 sys.dm_db_index_usage_stats)\n"
                f"2. 최근 N개월간 사용 0회인 인덱스 DROP\n"
                f"3. 유사 인덱스는 복합 인덱스로 통합"
            ),
            before=f"-- {tbl} 현재 보조 인덱스: {idx_count}개",
            after=(
                "-- 사용 여부 측정 쿼리:\n"
                "-- MySQL 8.0+:\n"
                "--   SELECT * FROM sys.schema_unused_indexes WHERE object_schema = DATABASE();\n\n"
                "-- MSSQL:\n"
                "--   SELECT i.name FROM sys.indexes i\n"
                "--   LEFT JOIN sys.dm_db_index_usage_stats s ON i.object_id = s.object_id AND i.index_id = s.index_id\n"
                "--   WHERE s.user_seeks IS NULL AND i.type > 1;"
            ),
            estimated_impact="측정 후 미사용 인덱스 제거 시 INSERT 2~5배 가속 가능",
            auto_applicable=False,
            default_action="review",
            source="rule",
            confidence=0.75,
            rule_id="idx.too_many.v1",
        ))

    return recs


# ══════════════════════════════════════════════════════════════
# IndexAdvisor 본체
# ══════════════════════════════════════════════════════════════
class IndexAdvisor(BaseAdvisor):
    """인덱스 전략 권고 (정적 분석 기반)."""
    category = "index"

    def supports(self, src_db: str, tgt_db: str) -> bool:
        return True

    def analyze(self, selection: JobSelection, context: AnalysisContext) -> list[Recommendation]:
        tables = selection.tables
        if not tables:
            return []

        table_meta = _fetch_table_columns_and_indexes(tables, context)
        if not table_meta:
            logger.info("IndexAdvisor: 테이블 메타 없음 → 권고 생략")
            return []

        # ObjectAdvisor 재사용
        from app.core.advisor.object_advisor import _fetch_object_ddl
        objects_ddls = _fetch_object_ddl(
            {
                "procedures": selection.procedures,
                "functions":  selection.functions,
                "views":      selection.views,
                "triggers":   selection.triggers,
            },
            context,
        )

        col_usage = _collect_column_usage(objects_ddls) if objects_ddls else {}
        logger.info(
            "IndexAdvisor: tables=%d, ddls=%d, distinct_cols_used=%d",
            len(tables), len(objects_ddls), len(col_usage)
        )

        recs: list[Recommendation] = []
        if col_usage:
            recs.extend(_rule_missing_indexes(tables, table_meta, col_usage))
        recs.extend(_rule_duplicate_indexes(tables, table_meta))
        recs.extend(_rule_too_many_indexes(tables, table_meta))

        logger.info("IndexAdvisor: %d개 권고 생성", len(recs))
        return recs

    def estimate_tokens(self, selection: JobSelection, mode: AnalysisMode) -> dict:
        if mode == "smart":
            return {"tokens_in": 0, "tokens_out": 0}
        elif mode == "hybrid":
            candidates = max(1, len(selection.tables) // 5)
            return {"tokens_in": 3000 * candidates, "tokens_out": 1500 * candidates}
        else:
            return {"tokens_in": 3000 * len(selection.tables),
                    "tokens_out": 1500 * len(selection.tables)}
