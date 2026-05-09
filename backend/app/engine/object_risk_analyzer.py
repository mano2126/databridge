"""
app/engine/object_risk_analyzer.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
v95_p62 (2026-05-05 본부장님 결정): 엔터프라이즈 수준 객체 위험 분석

본부장님 호소:
  "시간이 걸려도 엔터프라이즈 솔루션에 맞도록 구현해야해"
  
본질:
  vProductModelInstructions 같은 VIEW 가 1146 에러로 실패:
    - MSSQL XML 함수 (.value/.nodes/.query/.exist)
    - CROSS APPLY / OUTER APPLY (테이블 alias 처럼 보이는 임시 결과)
    - hierarchyid / geometry / geography 컬럼 참조
    - PIVOT / UNPIVOT 변환
  → AI 가 무한 재시도해도 변환 실패 → 비용 낭비 + 1146 잔류
  
처방 (5 Phase 엔터프라이즈 솔루션):
  Phase 1 (이 모듈): 사전 검증 — DDL 분석으로 위험 패턴 검출
  Phase 2: 변환 패턴 KB 누적 학습
  Phase 3: 실패 패턴 학습 (Negative KB)
  Phase 4: UI — 사용자 결정 (자동/수동/제외)
  Phase 5: 사용자 SQL 입력 + 검증

이 모듈의 역할:
  - 객체 DDL 정의를 받아 위험 패턴 검출
  - 위험 레벨 (HIGH/MED/LOW) + 자동 변환 신뢰도 (%)
  - 검출된 패턴 목록 + 권장 처리 방법

부작용 0:
  - 정규식 기반 (DB 조회 0)
  - 실패 시 MED (중간 위험) 반환 (안전)
  - 기존 ai_conversion 위험 분석에 추가 (옛 흐름 보존)

하드코딩 0%:
  - 패턴 목록을 데이터로 정의 (PATTERNS 상수)
  - 새 패턴 추가 시 코드 변경 X
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from __future__ import annotations
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


# ════════════════════════════════════════════════════════════════════
# 위험 패턴 정의 (데이터 — 새 패턴 추가 시 이 목록만 수정)
# ════════════════════════════════════════════════════════════════════
@dataclass
class RiskPattern:
    """단일 위험 패턴 정의."""
    code: str                   # 패턴 식별자 (KB 키)
    label: str                  # 사용자 노출 이름
    pattern: str                # 정규식 (re.IGNORECASE 적용)
    risk_level: str             # 'HIGH' | 'MEDIUM' | 'LOW'
    confidence_penalty: int     # 자동 변환 신뢰도 감점 (0-100)
    description: str            # 사용자에게 보여줄 설명
    mysql_alternative: str      # MySQL 대안 (수동 변환 가이드)


# MSSQL → MySQL 변환에서 알려진 위험 패턴들
PATTERNS_MSSQL_TO_MYSQL: List[RiskPattern] = [
    # ─── HIGH RISK: XML 함수 ──────────────────────────────────────────
    RiskPattern(
        code="xml_value_method",
        label="XML .value() 메서드",
        pattern=r"\b\w+\s*\.\s*value\s*\(\s*['N\"]",
        risk_level="HIGH",
        confidence_penalty=70,
        description=(
            "MSSQL XML 데이터 타입의 .value() 메서드는 MySQL 에 "
            "직접 대응이 없습니다. JSON 으로 사전 변환이 필요합니다."
        ),
        mysql_alternative=(
            "MySQL: JSON_EXTRACT(json_col, '$.path') 또는 "
            "JSON_UNQUOTE(JSON_EXTRACT(...))"
        ),
    ),
    RiskPattern(
        code="xml_nodes_method",
        label="XML .nodes() 메서드",
        pattern=r"\b\w+\s*\.\s*nodes\s*\(",
        risk_level="HIGH",
        confidence_penalty=80,
        description=(
            "MSSQL XML .nodes() 는 XML 을 row 로 분해합니다. "
            "MySQL 의 JSON_TABLE() 로 대체 가능하나 자동 변환 어려움."
        ),
        mysql_alternative=(
            "MySQL 8.0+: JSON_TABLE(json_col, '$[*]' COLUMNS (...)) "
            "또는 LATERAL 서브쿼리"
        ),
    ),
    RiskPattern(
        code="xml_query_method",
        label="XML .query() 메서드",
        pattern=r"\b\w+\s*\.\s*query\s*\(",
        risk_level="HIGH",
        confidence_penalty=70,
        description="MSSQL XML .query() — MySQL 직접 대응 없음.",
        mysql_alternative="JSON_EXTRACT 또는 사용자 정의 변환 필요",
    ),
    RiskPattern(
        code="xml_exist_method",
        label="XML .exist() 메서드",
        pattern=r"\b\w+\s*\.\s*exist\s*\(",
        risk_level="HIGH",
        confidence_penalty=60,
        description="MSSQL XML .exist() — MySQL JSON_CONTAINS 로 대체 가능.",
        mysql_alternative="MySQL: JSON_CONTAINS(json_col, value, '$.path')",
    ),
    # ─── HIGH RISK: APPLY ───────────────────────────────────────────
    RiskPattern(
        code="cross_apply",
        label="CROSS APPLY",
        pattern=r"\bCROSS\s+APPLY\b",
        risk_level="HIGH",
        confidence_penalty=60,
        description=(
            "MSSQL CROSS APPLY 는 MySQL 에 직접 대응이 없습니다. "
            "LATERAL JOIN (MySQL 8.0.14+) 또는 서브쿼리로 변환 필요."
        ),
        mysql_alternative=(
            "MySQL 8.0.14+: JOIN LATERAL (...) AS alias ON true"
        ),
    ),
    RiskPattern(
        code="outer_apply",
        label="OUTER APPLY",
        pattern=r"\bOUTER\s+APPLY\b",
        risk_level="HIGH",
        confidence_penalty=60,
        description=(
            "MSSQL OUTER APPLY → MySQL LEFT LATERAL JOIN 변환 필요."
        ),
        mysql_alternative=(
            "MySQL 8.0.14+: LEFT JOIN LATERAL (...) AS alias ON true"
        ),
    ),
    # ─── MEDIUM RISK: PIVOT ─────────────────────────────────────────
    RiskPattern(
        code="pivot",
        label="PIVOT 연산자",
        pattern=r"\bPIVOT\s*\(",
        risk_level="MEDIUM",
        confidence_penalty=40,
        description=(
            "MSSQL PIVOT 은 MySQL 에서 CASE WHEN 집계로 수동 변환 필요."
        ),
        mysql_alternative=(
            "SUM(CASE WHEN col=value THEN ... END) AS pivot_col 패턴"
        ),
    ),
    RiskPattern(
        code="unpivot",
        label="UNPIVOT 연산자",
        pattern=r"\bUNPIVOT\s*\(",
        risk_level="MEDIUM",
        confidence_penalty=40,
        description="MSSQL UNPIVOT → MySQL UNION ALL 패턴으로 변환.",
        mysql_alternative="UNION ALL (SELECT ... ) (SELECT ... ) 패턴",
    ),
    # ─── MEDIUM RISK: hierarchyid / spatial ─────────────────────────
    RiskPattern(
        code="hierarchyid_method",
        label="hierarchyid 메서드",
        pattern=r"\.\s*(GetAncestor|GetDescendant|IsDescendantOf|GetLevel|ToString)\s*\(",
        risk_level="MEDIUM",
        confidence_penalty=50,
        description=(
            "hierarchyid 는 MySQL 에 없습니다. v95_p57 처방으로 "
            "ToString() 만 자동 변환 (path string 으로). 다른 메서드는 수동."
        ),
        mysql_alternative="VARCHAR 컬럼으로 path 저장 + 문자열 검색",
    ),
    RiskPattern(
        code="spatial_method",
        label="공간 데이터 메서드 (geometry/geography)",
        pattern=r"\.\s*(STAsText|STAsBinary|STDistance|STIntersects|STContains)\s*\(",
        risk_level="MEDIUM",
        confidence_penalty=40,
        description=(
            "MSSQL 공간 데이터 메서드 — MySQL ST_AsText/ST_Distance 등 "
            "이름 다름. 자동 변환 가능 (KB 매칭)."
        ),
        mysql_alternative="MySQL: ST_AsText, ST_Distance, ST_Intersects 등",
    ),
    # ─── MEDIUM RISK: MERGE ─────────────────────────────────────────
    RiskPattern(
        code="merge_statement",
        label="MERGE 구문",
        pattern=r"\bMERGE\s+(INTO\s+)?\w+",
        risk_level="MEDIUM",
        confidence_penalty=50,
        description=(
            "MSSQL MERGE 는 MySQL 에 없습니다. "
            "INSERT ... ON DUPLICATE KEY UPDATE 로 변환."
        ),
        mysql_alternative="INSERT INTO ... ON DUPLICATE KEY UPDATE",
    ),
    # ─── LOW RISK: 자주 쓰이는 함수 차이 ─────────────────────────────
    RiskPattern(
        code="getdate_function",
        label="GETDATE() 함수",
        pattern=r"\bGETDATE\s*\(\s*\)",
        risk_level="LOW",
        confidence_penalty=5,
        description="MSSQL GETDATE() → MySQL NOW() (자동 변환).",
        mysql_alternative="MySQL: NOW() 또는 CURRENT_TIMESTAMP",
    ),
    RiskPattern(
        code="isnull_function",
        label="ISNULL() 함수",
        pattern=r"\bISNULL\s*\(",
        risk_level="LOW",
        confidence_penalty=5,
        description="MSSQL ISNULL(a, b) → MySQL IFNULL(a, b) (자동 변환).",
        mysql_alternative="MySQL: IFNULL(a, b) 또는 COALESCE(a, b)",
    ),
    RiskPattern(
        code="top_clause",
        label="TOP 절",
        pattern=r"\bSELECT\s+TOP\s+\d+",
        risk_level="LOW",
        confidence_penalty=5,
        description="MSSQL TOP N → MySQL LIMIT N (자동 변환).",
        mysql_alternative="MySQL: SELECT ... LIMIT N",
    ),
]


# ════════════════════════════════════════════════════════════════════
# 분석 결과 모델
# ════════════════════════════════════════════════════════════════════
@dataclass
class DetectedPattern:
    """검출된 패턴 1건."""
    code: str
    label: str
    risk_level: str
    matches: List[str] = field(default_factory=list)  # 매치된 텍스트 샘플 (최대 3개)
    description: str = ""
    mysql_alternative: str = ""


@dataclass
class ObjectRiskAnalysis:
    """객체 1개의 위험 분석 결과."""
    obj_name: str
    obj_type: str  # 'VIEW' | 'PROCEDURE' | 'FUNCTION' | 'TRIGGER'
    overall_risk: str = "LOW"  # 'HIGH' | 'MEDIUM' | 'LOW'
    confidence_pct: int = 100  # 자동 변환 신뢰도 (0-100)
    detected_patterns: List[DetectedPattern] = field(default_factory=list)
    recommendation: str = ""  # 권장 처리 방법
    has_high_risk: bool = False  # HIGH 위험 1개라도 있으면 True


# ════════════════════════════════════════════════════════════════════
# 핵심 분석 함수
# ════════════════════════════════════════════════════════════════════
def analyze_object_ddl(
    obj_name: str,
    obj_type: str,
    ddl: str,
    src_db: str = "mssql",
    tgt_db: str = "mysql",
) -> ObjectRiskAnalysis:
    """
    객체 DDL 을 분석하여 위험 패턴 검출.
    
    Args:
        obj_name: 객체 이름 (vProductModelInstructions 등)
        obj_type: 객체 타입 (VIEW/PROCEDURE/FUNCTION/TRIGGER)
        ddl: 객체의 SQL 정의
        src_db: 소스 DB 종류 (mssql/postgresql 등)
        tgt_db: 타겟 DB 종류 (mysql/mariadb 등)
    
    Returns:
        ObjectRiskAnalysis: 위험 분석 결과
    """
    result = ObjectRiskAnalysis(obj_name=obj_name, obj_type=obj_type)
    
    # 입력 검증
    if not ddl or not isinstance(ddl, str):
        result.overall_risk = "LOW"
        result.confidence_pct = 100
        result.recommendation = "DDL 정의 없음 — 분석 불가"
        return result
    
    # 현재는 MSSQL → MySQL 만 지원 (다른 변환 시 LOW 반환)
    src_mssql = src_db.lower() in ("mssql", "azure", "sqlserver")
    tgt_mysql = tgt_db.lower() in ("mysql", "aurora", "mariadb", "tidb", "cloudsql")
    if not (src_mssql and tgt_mysql):
        result.recommendation = f"{src_db} → {tgt_db} 변환 분석 미지원 — 기본 LOW 반환"
        return result
    
    patterns = PATTERNS_MSSQL_TO_MYSQL
    
    # 신뢰도 계산용
    total_penalty = 0
    has_high = False
    has_medium = False
    
    # 각 패턴 매칭
    for p in patterns:
        try:
            regex = re.compile(p.pattern, re.IGNORECASE | re.MULTILINE)
            matches = regex.findall(ddl)
            if matches:
                # 매치 샘플 최대 3개 (긴 매치는 100자 제한)
                sample_matches = []
                for m in matches[:3]:
                    if isinstance(m, tuple):
                        m = " ".join(str(x) for x in m if x)
                    sample_matches.append(str(m)[:100])
                
                detected = DetectedPattern(
                    code=p.code,
                    label=p.label,
                    risk_level=p.risk_level,
                    matches=sample_matches,
                    description=p.description,
                    mysql_alternative=p.mysql_alternative,
                )
                result.detected_patterns.append(detected)
                
                # 신뢰도 페널티 누적
                total_penalty += p.confidence_penalty
                if p.risk_level == "HIGH":
                    has_high = True
                elif p.risk_level == "MEDIUM":
                    has_medium = True
        except re.error:
            # 정규식 컴파일 오류 — 무시 (안전)
            continue
    
    # 전체 위험 레벨 결정
    if has_high:
        result.overall_risk = "HIGH"
        result.has_high_risk = True
    elif has_medium:
        result.overall_risk = "MEDIUM"
    else:
        result.overall_risk = "LOW"
    
    # 신뢰도 = max(0, 100 - total_penalty), 최소 5%
    result.confidence_pct = max(5, min(100, 100 - total_penalty))
    
    # 권장 처리 방법
    if result.overall_risk == "HIGH":
        result.recommendation = (
            f"⚠️ 자동 변환 신뢰도 {result.confidence_pct}% — "
            f"수동 변환 또는 이관 제외 권장"
        )
    elif result.overall_risk == "MEDIUM":
        result.recommendation = (
            f"⚡ 자동 변환 신뢰도 {result.confidence_pct}% — "
            f"AI 변환 시도 가능 (실패 시 수동)"
        )
    else:
        result.recommendation = (
            f"✅ 자동 변환 신뢰도 {result.confidence_pct}% — 안전"
        )
    
    return result


def analyze_objects_batch(
    objects: List[Dict[str, str]],
    src_db: str = "mssql",
    tgt_db: str = "mysql",
) -> List[ObjectRiskAnalysis]:
    """
    여러 객체 일괄 분석.
    
    Args:
        objects: [{"name": str, "type": str, "ddl": str}, ...]
        src_db, tgt_db: DB 종류
    
    Returns:
        ObjectRiskAnalysis 리스트
    """
    results = []
    for obj in objects:
        try:
            analysis = analyze_object_ddl(
                obj_name=obj.get("name", "unknown"),
                obj_type=obj.get("type", "UNKNOWN"),
                ddl=obj.get("ddl", ""),
                src_db=src_db,
                tgt_db=tgt_db,
            )
            results.append(analysis)
        except Exception as e:
            # 분석 실패 시 안전하게 MEDIUM 반환
            fallback = ObjectRiskAnalysis(
                obj_name=obj.get("name", "unknown"),
                obj_type=obj.get("type", "UNKNOWN"),
                overall_risk="MEDIUM",
                confidence_pct=50,
                recommendation=f"분석 실패 ({e}) — 수동 검토 권장"
            )
            results.append(fallback)
    return results


def to_dict(analysis: ObjectRiskAnalysis) -> dict:
    """ObjectRiskAnalysis 를 JSON 직렬화 가능한 dict 로."""
    return {
        "obj_name": analysis.obj_name,
        "obj_type": analysis.obj_type,
        "overall_risk": analysis.overall_risk,
        "confidence_pct": analysis.confidence_pct,
        "has_high_risk": analysis.has_high_risk,
        "recommendation": analysis.recommendation,
        "detected_patterns": [
            {
                "code": p.code,
                "label": p.label,
                "risk_level": p.risk_level,
                "matches": p.matches,
                "description": p.description,
                "mysql_alternative": p.mysql_alternative,
            }
            for p in analysis.detected_patterns
        ],
    }


# ════════════════════════════════════════════════════════════════════
# 빠른 검사 헬퍼 (preflight 통합용)
# ════════════════════════════════════════════════════════════════════
def has_high_risk_pattern(ddl: str, src_db: str = "mssql", tgt_db: str = "mysql") -> bool:
    """DDL 에 HIGH 위험 패턴이 있는지 빠르게 확인 (정규식만)."""
    if not ddl:
        return False
    src_mssql = src_db.lower() in ("mssql", "azure", "sqlserver")
    tgt_mysql = tgt_db.lower() in ("mysql", "aurora", "mariadb", "tidb", "cloudsql")
    if not (src_mssql and tgt_mysql):
        return False
    
    for p in PATTERNS_MSSQL_TO_MYSQL:
        if p.risk_level != "HIGH":
            continue
        try:
            if re.search(p.pattern, ddl, re.IGNORECASE | re.MULTILINE):
                return True
        except re.error:
            continue
    return False
