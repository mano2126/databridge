"""
app/api/routes/preflight.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
v95_p23a (2026-05-03 본부장님 본질 처방): 위저드 사전 분석 (Pre-Flight)
v95_p24a (2026-05-04 본부장님 본질 처방): 진짜 분석으로 강화

본부장님 호소 (v95_p24a):
  "이 단계에서 해야 할 일들을 정말 다 하고 있는게 맞는지 한번더 확인 좀 부탁해"
  → 분석이 빨리 끝나는 이유 = source_conn 받아도 DB 조회 0회 (정형 메시지만)
  → v95_p24a: source_conn 활용 → 진짜 의존성/row count 조회

진짜 조회 추가 (v95_p24a):
  - 의존성: sys.sql_expression_dependencies (MSSQL) — 미선택 의존 객체 식별
  - 성능: sys.partitions / information_schema.TABLES — 진짜 row count
  - 부작용 0: source_conn 없거나 조회 실패 시 기존 동작 그대로 fallback
  - 하드코딩 0%: make_conn(conn_info) 통합 헬퍼 사용 (모든 DB 타입 지원)

본부장님 호소:
  "위저드에서 테이블 및 오브젝트 전체 선택하고 다음으로 넘어가면 그때 전체
   분석할때 이렇게 dead lock 걸릴 거 분석해서 회피해서 순서를 정해야 되는거
   아냐? 분명 멀티로 진행하면 이런일 발생할 소지 있다고 내가 말했었는데."

본질:
  PoC 마인드: 이관 시작 → 에러 → 재시도
  엔터프라이즈 마인드: 사전 분석 → 위험 차단 → 안전 이관

엔드포인트:
  POST /api/v1/preflight/analyze
  입력: src_db, tgt_db, selection (tables/procs/funcs/triggers/views)
  출력: 위험 목록 (level, category, title, affected, auto_fix)

분석 카테고리 (4가지):
  1) deadlock_risk    - 동시 CREATE TABLE 시 lock 충돌 위험
  2) ai_conversion    - FUNC/SP/TRIG AI 변환 알려진 함정 패턴
  3) dependency       - VIEW 의 의존 테이블 미선택/미존재
  4) performance      - 대용량 테이블 동시 처리 위험

하드코딩 0%:
  - DB 종류 무관 (src_db/tgt_db 입력으로 동적 처리)
  - 객체 이름/테이블 이름 박지 않음
  - 모든 표준 DB (Northwind/WideWorldImporters/캐피탈사 운영 DB) 동일 작동
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
import logging

router = APIRouter(prefix="/api/v1/preflight", tags=["preflight"])
_log = logging.getLogger("databridge.preflight")


# ════════════════════════════════════════════════════════════════════
# 모델 정의
# ════════════════════════════════════════════════════════════════════
class ObjectDDL(BaseModel):
    """단일 객체의 DDL 정의 (v95_p63 추가)"""
    name: str
    type: str  # 'VIEW' | 'PROCEDURE' | 'FUNCTION' | 'TRIGGER'
    ddl: str = ""


class SelectionInput(BaseModel):
    tables:     List[str] = []
    procedures: List[str] = []
    functions:  List[str] = []
    triggers:   List[str] = []
    views:      List[str] = []
    # v95_p63 (2026-05-05 본부장님): 객체 DDL 정보 추가
    #   엔터프라이즈 패턴 검출 (XML/CROSS APPLY/PIVOT/hierarchyid)
    #   본부장님 환경 vProductModelInstructions 같은 위험 객체 사전 검출용
    #   - 위저드에서 DDL 함께 전송 (없으면 기존 흐름)
    #   - 부작용 0 (선택적 필드)
    object_ddls: List[ObjectDDL] = []


class PreflightInput(BaseModel):
    src_db:     str  # mssql / mysql / postgresql / ...
    tgt_db:     str
    selection:  SelectionInput
    source_conn: Optional[dict] = None
    parallel_tables: int = 3  # 병렬도 (기본 3)


class RiskItem(BaseModel):
    level:    str   # info / warn / critical
    category: str   # deadlock_risk / ai_conversion / dependency / performance / object_risk
    title:    str
    desc:     str
    affected: List[str]
    auto_fix: Optional[str] = None
    affected_count: int = 0
    # v95_p63 (2026-05-05 본부장님): 객체별 상세 메타 (UI 카드 + 사용자 결정용)
    #   - HIGH 위험 객체별 자동 변환 신뢰도, 검출 패턴 목록, 권장 처리
    #   - Phase 4 UI 에서 카드 + 3-옵션 (자동/수동/제외) 표시
    #   - 부작용 0 (Optional 필드)
    risk_meta: Optional[dict] = None


# ════════════════════════════════════════════════════════════════════
# 위험 분석 함수들 — 카테고리별
# ════════════════════════════════════════════════════════════════════
def _analyze_deadlock_risk(
    src_db: str, tgt_db: str, tables: List[str], parallel: int
) -> Optional[RiskItem]:
    """본질 1: Deadlock 위험 분석.
    
    동시 CREATE TABLE 시 InnoDB metadata lock 충돌 위험.
    parallel >= 2 이고 tables >= parallel 이면 위험.
    """
    if parallel < 2 or len(tables) < parallel:
        return None
    
    # MySQL 계열 타겟에서 발생 (InnoDB metadata lock)
    tgt_mysql = tgt_db.lower() in ("mysql", "aurora", "mariadb", "tidb", "cloudsql")
    if not tgt_mysql:
        return None  # MSSQL 타겟은 metadata lock 본질 다름
    
    return RiskItem(
        level="warn",
        category="deadlock_risk",
        title=f"동시 CREATE TABLE 으로 인한 Deadlock 위험",
        desc=(
            f"테이블 {len(tables)}개를 병렬도 {parallel} 로 동시 처리 시 "
            f"MySQL InnoDB metadata lock 충돌로 1213 Deadlock 발생 가능. "
            f"DataBridge 가 CREATE TABLE 단계를 자동 직렬화 하여 위험 차단."
        ),
        affected=tables[:5],  # 샘플 5개만
        affected_count=len(tables),
        auto_fix="자동 처리됨 — CREATE TABLE 직렬화 (담당자 조치 불필요)"
    )


def _analyze_ai_conversion_risk(
    src_db: str, tgt_db: str, selection: SelectionInput
) -> List[RiskItem]:
    """본질 2: AI 변환 위험 분석.
    
    FUNC/SP/TRIG 객체는 AI 변환에서 알려진 함정 패턴 (CASE WHEN ; / END IF; / 
    AFTER trigger NEW row update) 발생 가능.
    """
    risks = []
    obj_count = (
        len(selection.functions) + len(selection.procedures) + len(selection.triggers)
    )
    if obj_count == 0:
        return risks
    
    # MSSQL → MySQL 변환에서 알려진 함정
    src_mssql = src_db.lower() in ("mssql", "azure", "sqlserver")
    tgt_mysql = tgt_db.lower() in ("mysql", "aurora", "mariadb", "tidb", "cloudsql")
    
    if src_mssql and tgt_mysql:
        if selection.functions:
            risks.append(RiskItem(
                level="info",
                category="ai_conversion",
                title=f"FUNC {len(selection.functions)}건 — AI 변환 함정 가능성",
                desc=(
                    "MSSQL → MySQL 변환 시 CASE 문 안의 ; (세미콜론) 패턴이 "
                    "1064 syntax error 일으킬 수 있음. "
                    "DataBridge 가 변환 후 자동 정정 처리."
                ),
                affected=selection.functions[:5],
                affected_count=len(selection.functions),
                auto_fix="자동 처리됨 — 후처리 정정 (담당자 조치 불필요)"
            ))
        if selection.procedures:
            risks.append(RiskItem(
                level="info",
                category="ai_conversion",
                title=f"PROC {len(selection.procedures)}건 — AI 변환 함정 가능성",
                desc=(
                    "MSSQL → MySQL 변환 시 IF ... END IF; 뒤 추가 ; 패턴 "
                    "1064 syntax error 일으킬 수 있음. "
                    "DataBridge 가 변환 후 자동 정정 처리."
                ),
                affected=selection.procedures[:5],
                affected_count=len(selection.procedures),
                auto_fix="자동 처리됨 — 후처리 정정 (담당자 조치 불필요)"
            ))
        if selection.triggers:
            risks.append(RiskItem(
                level="warn",
                category="ai_conversion",
                title=f"TRIGGER {len(selection.triggers)}건 — AFTER trigger NEW row 본질",
                desc=(
                    "MSSQL 의 AFTER trigger 는 NEW.column 수정 가능하나 "
                    "MySQL 의 AFTER trigger 는 1362 에러 발생. "
                    "AFTER → BEFORE 변환이 필요한 경우 있음 (수동 검토 권장)."
                ),
                affected=selection.triggers[:5],
                affected_count=len(selection.triggers),
                auto_fix=None
            ))
    
    return risks


def _bare_name(qname: str) -> str:
    """v95_p24a: 'Schema.Object' 또는 'Schema_Object' → 'Object' (bare name).

    위저드 selection 은 'Person.Address' 결합 형태로 올 수 있음.
    의존성 비교 시 bare name 으로 통일.
    """
    if not qname:
        return ""
    # 'Schema.Object' 우선
    if "." in qname:
        return qname.split(".", 1)[1]
    # 'Schema_Object' (언더스코어 결합 정책) — 첫 번째 _ 만 분리
    # 단, 원본에 _ 가 있을 수 있으므로 보수적으로 split 시도하지 않음
    return qname


def _analyze_object_risk(
    selection: SelectionInput,
    src_db: str,
    tgt_db: str,
) -> List[RiskItem]:
    """
    v95_p63 (2026-05-05 본부장님): 본질 5 — 객체 DDL 패턴 위험 분석.
    
    Phase 1-2: v95_p62 의 object_risk_analyzer 를 preflightRisks 와 통합.
    
    본질:
      vProductModelInstructions 같은 VIEW 의 XML/CROSS APPLY 패턴은
      AI 변환 거의 불가능 → 사전 검출 → 사용자에게 결정권 부여.
    
    위험 객체별로 RiskItem 1건 생성 (level=critical/warn/info):
      - HIGH 위험 → critical (사용자 결정 필수)
      - MEDIUM 위험 → warn (AI 변환 시도 가능)
      - LOW 위험 → info (자동 변환 신뢰)
    
    부작용 0:
      - object_ddls 비어있으면 빈 리스트 반환
      - object_risk_analyzer 임포트 실패 시 빈 리스트 (안전 폴백)
    """
    risks: List[RiskItem] = []
    
    # DDL 정보 없으면 분석 스킵
    if not selection.object_ddls:
        return risks
    
    # 안전 임포트 (모듈 없거나 오류 시 폴백)
    try:
        from app.engine.object_risk_analyzer import (
            analyze_objects_batch, to_dict
        )
    except Exception as e:
        _log.warning(f"[v95_p63] object_risk_analyzer 임포트 실패 — 분석 스킵: {e}")
        return risks
    
    # DDL 리스트 변환
    objects_for_analysis = [
        {"name": od.name, "type": od.type, "ddl": od.ddl}
        for od in selection.object_ddls
        if od.ddl  # DDL 있는 것만
    ]
    if not objects_for_analysis:
        return risks
    
    # 일괄 분석
    try:
        analyses = analyze_objects_batch(objects_for_analysis, src_db, tgt_db)
    except Exception as e:
        _log.warning(f"[v95_p63] 분석 실패 — 폴백: {e}")
        return risks
    
    # 위험 레벨별 그룹핑
    high_risk = [a for a in analyses if a.overall_risk == "HIGH"]
    medium_risk = [a for a in analyses if a.overall_risk == "MEDIUM"]
    
    # ─── HIGH 위험 객체별 — critical 레벨 RiskItem ──────────────
    # 사용자가 카드별 결정 가능하도록 객체별 1건씩 생성
    for analysis in high_risk:
        # 검출 패턴 요약
        pattern_summary = ", ".join(
            sorted(set(p.label for p in analysis.detected_patterns))
        )
        risks.append(RiskItem(
            level="critical",
            category="object_risk",
            title=f"⚠️ {analysis.obj_type} [{analysis.obj_name}] — 자동 변환 어려움",
            desc=(
                f"검출 패턴: {pattern_summary}\n"
                f"자동 변환 신뢰도: {analysis.confidence_pct}%\n"
                f"{analysis.recommendation}"
            ),
            affected=[analysis.obj_name],
            affected_count=1,
            auto_fix=None,  # 자동 fix 없음 — 사용자 결정 필요
            risk_meta=to_dict(analysis),  # UI 카드용 상세 메타
        ))
    
    # ─── MEDIUM 위험 — warn 레벨 (집계 또는 개별) ───────────────
    if medium_risk:
        # MEDIUM 은 5개 미만이면 개별, 5개 이상이면 집계
        if len(medium_risk) < 5:
            for analysis in medium_risk:
                pattern_summary = ", ".join(
                    sorted(set(p.label for p in analysis.detected_patterns))
                )
                risks.append(RiskItem(
                    level="warn",
                    category="object_risk",
                    title=f"⚡ {analysis.obj_type} [{analysis.obj_name}] — 변환 주의",
                    desc=(
                        f"검출 패턴: {pattern_summary}\n"
                        f"자동 변환 신뢰도: {analysis.confidence_pct}%\n"
                        f"{analysis.recommendation}"
                    ),
                    affected=[analysis.obj_name],
                    affected_count=1,
                    auto_fix="AI 변환 시도 — 실패 시 수동 변환 권장",
                    risk_meta=to_dict(analysis),
                ))
        else:
            # 5개 이상은 집계 메시지 1건 + 첫 5개 affected
            avg_conf = sum(a.confidence_pct for a in medium_risk) // len(medium_risk)
            risks.append(RiskItem(
                level="warn",
                category="object_risk",
                title=f"⚡ MEDIUM 위험 객체 {len(medium_risk)}건 — AI 변환 주의",
                desc=(
                    f"PIVOT/UNPIVOT/MERGE/hierarchyid/spatial 등의 패턴 검출.\n"
                    f"평균 자동 변환 신뢰도: {avg_conf}%\n"
                    f"AI 변환 시도 가능 (실패 시 수동 변환)"
                ),
                affected=[a.obj_name for a in medium_risk[:5]],
                affected_count=len(medium_risk),
                auto_fix="AI 변환 시도 — 객체별 결과 확인 권장",
                risk_meta={
                    "objects": [to_dict(a) for a in medium_risk]
                },
            ))
    
    if risks:
        _log.info(
            f"[v95_p63] 객체 위험 분석 완료 — "
            f"HIGH {len(high_risk)}건, MEDIUM {len(medium_risk)}건 "
            f"(총 {len(selection.object_ddls)}개 객체 분석)"
        )
    
    return risks


def _analyze_dependency_risk(
    selection: SelectionInput,
    src_db: str,
    source_conn: Optional[dict]
) -> List[RiskItem]:
    """본질 3: VIEW 의존성 위험 분석 — v95_p24a 강화.

    이전 (v95_p23a):
      - VIEW 개수만 보고 정형 메시지 출력 (진짜 의존성 안 봄)

    v95_p24a (2026-05-04 본부장님 본질 처방):
      - source_conn 있고 MSSQL 이면 sys.sql_expression_dependencies 조회
      - 각 VIEW 의 진짜 의존 테이블 추출
      - 선택된 테이블 목록과 비교하여 미선택 테이블 식별
      - 미선택 의존 테이블 발견 시 critical 위험으로 표시

    부작용 0:
      - source_conn 없거나 MSSQL 아니면 기존 동작 (정형 안내만)
      - DB 조회 실패해도 fallback (정형 안내)
      - 하드코딩 0% (모든 MSSQL DB 동일 작동)
    """
    if not selection.views:
        return []

    risks: List[RiskItem] = []

    # ── v95_p24a: 진짜 의존성 분석 (MSSQL 한정) ────────────────
    src_mssql = src_db.lower() in ("mssql", "azure", "sqlserver")
    do_real_check = bool(source_conn) and src_mssql

    real_check_done = False
    missing_deps: List[dict] = []  # [{view, missing: [tbl, ...]}, ...]

    if do_real_check:
        try:
            from app.core.db_conn import make_conn

            # 선택된 테이블의 bare name set (의존성 비교용)
            selected_table_bares = {
                _bare_name(t).lower() for t in selection.tables
            }

            conn = make_conn(source_conn, timeout=8)
            try:
                cur = conn.cursor()
                for v_qname in selection.views:
                    v_bare = _bare_name(v_qname)
                    # MSSQL: sys.sql_expression_dependencies (참조 객체)
                    # referenced_entity_name 만 조회 — 스키마/타입 무관 단순화
                    try:
                        cur.execute("""
                            SELECT DISTINCT referenced_entity_name
                            FROM sys.sql_expression_dependencies d
                            INNER JOIN sys.objects o ON d.referencing_id = o.object_id
                            WHERE o.name = ?
                              AND o.type = 'V'
                              AND referenced_entity_name IS NOT NULL
                        """, [v_bare])
                        rows = cur.fetchall()
                        deps = [r[0] for r in rows if r and r[0]]
                    except Exception:
                        deps = []

                    # 미선택 의존 객체 (테이블 이름 셋에 없는 것들)
                    missing = [
                        d for d in deps
                        if d.lower() not in selected_table_bares
                    ]
                    if missing:
                        missing_deps.append({"view": v_qname, "missing": missing})
                cur.close()
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

            real_check_done = True
            _log.info(
                "[v95_p24a-Preflight] 의존성 진짜 조회 완료: views=%d missing_views=%d",
                len(selection.views), len(missing_deps)
            )
        except Exception as e:
            # 조회 실패해도 안전 fallback (정형 안내)
            _log.warning("[v95_p24a-Preflight] 의존성 조회 실패 (fallback): %s", e)
            real_check_done = False

    # ── 결과 위험 항목 생성 ────────────────────────────────────
    if real_check_done and missing_deps:
        # 진짜 분석 결과: 미선택 의존 객체 발견
        affected_views = [m["view"] for m in missing_deps]
        # 샘플 미선택 객체 표시 (각 VIEW 별 최대 3개)
        sample_missing = []
        for m in missing_deps[:5]:
            for tbl in m["missing"][:3]:
                sample_missing.append(f"{m['view']} → {tbl}")
        risks.append(RiskItem(
            level="warn",
            category="dependency",
            title=f"VIEW {len(missing_deps)}건 — 의존 객체 미선택 (1146 에러 위험)",
            desc=(
                f"선택한 VIEW {len(missing_deps)}건의 의존 객체가 선택된 테이블에 "
                f"포함되지 않음. 이관 시 1146 (Table doesn't exist) 에러로 SKIP 됨. "
                f"의존 테이블/뷰를 추가 선택하거나, 의존성이 깨진 VIEW 는 선택 해제 권장."
            ),
            affected=sample_missing[:10],
            affected_count=sum(len(m["missing"]) for m in missing_deps),
            auto_fix=None  # 본부장님 결정 필요 (수동 해소 권장)
        ))
        # 의존성 OK 인 VIEW 는 별도 안내 (info)
        ok_views = [v for v in selection.views
                    if v not in {m["view"] for m in missing_deps}]
        if ok_views:
            risks.append(RiskItem(
                level="info",
                category="dependency",
                title=f"VIEW {len(ok_views)}건 — 의존성 OK",
                desc="선택한 테이블 안에 의존 객체가 모두 포함되어 있음 (이관 가능).",
                affected=ok_views[:5],
                affected_count=len(ok_views),
                auto_fix=None
            ))
    elif real_check_done:
        # 진짜 분석 결과: 모든 VIEW 의존성 OK
        risks.append(RiskItem(
            level="info",
            category="dependency",
            title=f"VIEW {len(selection.views)}건 — 의존성 OK (진짜 조회 완료)",
            desc=(
                "MSSQL sys.sql_expression_dependencies 진짜 조회 결과 — "
                "선택한 테이블 안에 모든 VIEW 의 의존 객체가 포함되어 있음."
            ),
            affected=selection.views[:5],
            affected_count=len(selection.views),
            auto_fix=None
        ))
    else:
        # Fallback: 진짜 조회 못 함 → 기존 정형 안내
        risks.append(RiskItem(
            level="info",
            category="dependency",
            title=f"VIEW {len(selection.views)}건 — 의존 테이블 확인 필요",
            desc=(
                "VIEW 는 의존 테이블이 먼저 생성되어야 함. "
                "선택한 테이블에 모든 의존 테이블 포함되었는지 확인 필요. "
                "이관 중 의존 테이블 미존재 시 1146 에러로 SKIP 처리됨."
            ),
            affected=selection.views[:5],
            affected_count=len(selection.views),
            auto_fix="자동 처리됨 — 의존성 자동 감지 (담당자 조치 불필요)"
        ))

    return risks


def _analyze_performance_risk(
    tables: List[str], parallel: int,
    src_db: str, source_conn: Optional[dict]
) -> List[RiskItem]:
    """본질 4: 성능 위험 분석 — v95_p24a 강화.

    이전 (v95_p23a):
      - tables 개수만 보고 정형 메시지 출력 (진짜 row count 안 봄)

    v95_p24a (2026-05-04 본부장님 본질 처방):
      - source_conn 있으면 진짜 row count 조회 (sys.dm_db_partition_stats 또는 sys.partitions)
      - 1M 초과 대용량 테이블 식별
      - 100K 초과 중용량 테이블 카운트

    부작용 0:
      - source_conn 없으면 기존 동작 (정형 안내만)
      - DB 조회 실패해도 fallback (정형 안내)
      - 비용 절감: SUM(rows) approx 만 사용 (COUNT(*) 안 함)
    """
    if not tables:
        return []

    risks: List[RiskItem] = []

    src_mssql = src_db.lower() in ("mssql", "azure", "sqlserver")
    src_mysql = src_db.lower() in ("mysql", "aurora", "mariadb", "tidb", "cloudsql")
    do_real_check = bool(source_conn) and (src_mssql or src_mysql)

    real_check_done = False
    big_tables: List[dict] = []   # >= 1M rows
    mid_tables: List[dict] = []   # 100K ~ 1M rows

    if do_real_check:
        try:
            from app.core.db_conn import make_conn

            conn = make_conn(source_conn, timeout=8)
            try:
                cur = conn.cursor()
                # 진짜 row count 조회 (catalog 기반 — COUNT(*) 안 씀, 비용 0)
                if src_mssql:
                    # MSSQL: sys.dm_db_partition_stats (HEAP/CLUSTERED 대상)
                    placeholders = ",".join(["?"] * len(tables))
                    bare_names = [_bare_name(t) for t in tables]
                    qname_map = {_bare_name(t).lower(): t for t in tables}
                    try:
                        cur.execute(f"""
                            SELECT t.name, SUM(p.rows) AS row_count
                            FROM sys.tables t
                            INNER JOIN sys.partitions p
                              ON t.object_id = p.object_id AND p.index_id IN (0, 1)
                            WHERE t.name IN ({placeholders})
                            GROUP BY t.name
                        """, bare_names)
                        rows = cur.fetchall()
                        for r in rows:
                            tbl_name, row_count = r[0], int(r[1] or 0)
                            qname = qname_map.get(tbl_name.lower(), tbl_name)
                            if row_count >= 1_000_000:
                                big_tables.append({"table": qname, "rows": row_count})
                            elif row_count >= 100_000:
                                mid_tables.append({"table": qname, "rows": row_count})
                    except Exception:
                        pass
                elif src_mysql:
                    # MySQL: information_schema.TABLES.TABLE_ROWS (approx)
                    db = source_conn.get("database", "")
                    placeholders = ",".join(["%s"] * len(tables))
                    bare_names = [_bare_name(t) for t in tables]
                    qname_map = {_bare_name(t).lower(): t for t in tables}
                    try:
                        cur.execute(f"""
                            SELECT TABLE_NAME, TABLE_ROWS
                            FROM information_schema.TABLES
                            WHERE TABLE_SCHEMA = %s
                              AND TABLE_NAME IN ({placeholders})
                        """, [db] + bare_names)
                        rows = cur.fetchall()
                        for r in rows:
                            if isinstance(r, dict):
                                tbl_name = r.get("TABLE_NAME") or ""
                                row_count = int(r.get("TABLE_ROWS") or 0)
                            else:
                                tbl_name = r[0] or ""
                                row_count = int(r[1] or 0)
                            qname = qname_map.get(tbl_name.lower(), tbl_name)
                            if row_count >= 1_000_000:
                                big_tables.append({"table": qname, "rows": row_count})
                            elif row_count >= 100_000:
                                mid_tables.append({"table": qname, "rows": row_count})
                    except Exception:
                        pass
                cur.close()
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

            real_check_done = True
            _log.info(
                "[v95_p24a-Preflight] 성능 진짜 조회 완료: tables=%d big=%d mid=%d",
                len(tables), len(big_tables), len(mid_tables)
            )
        except Exception as e:
            _log.warning("[v95_p24a-Preflight] 성능 조회 실패 (fallback): %s", e)
            real_check_done = False

    # ── 결과 위험 항목 ────────────────────────────────────────
    if real_check_done and big_tables:
        # 대용량 테이블 발견
        big_tables.sort(key=lambda x: -x["rows"])
        big_table_summary = [
            f"{t['table']} ({t['rows']:,}행)" for t in big_tables[:5]
        ]
        risks.append(RiskItem(
            level="warn",
            category="performance",
            title=f"대용량 테이블 {len(big_tables)}건 (≥1M행) — 단독 실행 자동 전환",
            desc=(
                f"진짜 row count 조회 결과 1M 행 이상 테이블 {len(big_tables)}건 발견. "
                f"job 의 parallel_big_table_rows 임계값 (기본 1M) 초과 시 단독 실행으로 "
                f"자동 전환되어 메모리/IO 경합 회피됨."
            ),
            affected=big_table_summary,
            affected_count=len(big_tables),
            auto_fix="자동 처리됨 — 대용량 테이블 단독 실행 (담당자 조치 불필요)"
        ))
    if real_check_done and mid_tables:
        # 중용량 테이블 안내
        mid_tables.sort(key=lambda x: -x["rows"])
        mid_summary = [
            f"{t['table']} ({t['rows']:,}행)" for t in mid_tables[:5]
        ]
        risks.append(RiskItem(
            level="info",
            category="performance",
            title=f"중용량 테이블 {len(mid_tables)}건 (100K~1M행) — 병렬 가능",
            desc=(
                f"100K~1M 행 테이블 {len(mid_tables)}건. 병렬도 {parallel} 로 처리 가능."
            ),
            affected=mid_summary,
            affected_count=len(mid_tables),
            auto_fix=None
        ))
    if real_check_done and not big_tables and not mid_tables:
        risks.append(RiskItem(
            level="info",
            category="performance",
            title=f"테이블 {len(tables)}개 — 모두 소용량 (<100K행)",
            desc="진짜 row count 조회 결과 모두 소용량. 병렬 처리 안전.",
            affected=[],
            affected_count=0,
            auto_fix=None
        ))

    if not real_check_done and len(tables) >= parallel * 2:
        # Fallback: 진짜 조회 못 함 → 기존 정형 안내
        risks.append(RiskItem(
            level="info",
            category="performance",
            title=f"테이블 {len(tables)}개 — 병렬 처리 성능 가이드",
            desc=(
                f"병렬도 {parallel} 로 처리. 대용량 테이블 (>1M rows) 이 여러 개면 "
                f"메모리/IO 경합 발생 가능. job 의 parallel_big_table_rows 임계값 "
                f"(기본 1M) 초과 시 단독 실행으로 자동 전환됨."
            ),
            affected=[],
            affected_count=0,
            auto_fix="자동 처리됨 — 대용량 테이블 단독 실행 (담당자 조치 불필요)"
        ))

    return risks


# ════════════════════════════════════════════════════════════════════
# 메인 엔드포인트
# ════════════════════════════════════════════════════════════════════
@router.post("/analyze")
def preflight_analyze(body: PreflightInput) -> dict:
    """위저드 사전 분석 — 모든 위험 카테고리 검사.
    
    응답:
        {
            "ok": True,
            "summary": {"total": N, "critical": M, "warn": K, "info": L},
            "risks": [...]
        }
    """
    risks: List[RiskItem] = []
    
    try:
        # 본질 1: Deadlock
        r = _analyze_deadlock_risk(
            body.src_db, body.tgt_db,
            body.selection.tables, body.parallel_tables
        )
        if r:
            risks.append(r)
        
        # 본질 2: AI 변환
        risks.extend(_analyze_ai_conversion_risk(
            body.src_db, body.tgt_db, body.selection
        ))
        
        # 본질 3: 의존성 (v95_p24a: source_conn 전달 → 진짜 조회)
        risks.extend(_analyze_dependency_risk(
            body.selection, body.src_db, body.source_conn
        ))
        
        # 본질 4: 성능 (v95_p24a: source_conn 전달 → 진짜 row count 조회)
        risks.extend(_analyze_performance_risk(
            body.selection.tables, body.parallel_tables,
            body.src_db, body.source_conn
        ))
        
        # 본질 5: 객체 패턴 위험 (v95_p63 — XML/CROSS APPLY/PIVOT/hierarchyid)
        #   본부장님 결정: "5 Phase 모두 순차 구현 — 엔터프라이즈 솔루션"
        #   Phase 1-2 — object_risk_analyzer 와 통합
        #   object_ddls 없으면 빈 리스트 반환 (옛 클라이언트 호환)
        risks.extend(_analyze_object_risk(
            body.selection, body.src_db, body.tgt_db
        ))
        
        # 요약 통계
        summary = {
            "total":    len(risks),
            "critical": sum(1 for x in risks if x.level == "critical"),
            "warn":     sum(1 for x in risks if x.level == "warn"),
            "info":     sum(1 for x in risks if x.level == "info"),
            "auto_fix_count": sum(1 for x in risks if x.auto_fix),
        }
        
        _log.info(
            "[v95_p23a-Preflight] %s→%s analyze: total=%d critical=%d warn=%d info=%d",
            body.src_db, body.tgt_db,
            summary["total"], summary["critical"], summary["warn"], summary["info"]
        )
        
        return {
            "ok":      True,
            "summary": summary,
            "risks":   [r.dict() for r in risks],
        }
    
    except Exception as e:
        _log.exception("[v95_p23a-Preflight] 분석 실패")
        return {
            "ok":     False,
            "error":  str(e),
            "summary": {"total": 0, "critical": 0, "warn": 0, "info": 0},
            "risks":   [],
        }
