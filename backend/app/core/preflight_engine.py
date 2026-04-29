"""
preflight_engine.py — Phase G-1 (2026-04-25)

Pre-Flight Assessment — DB 환경 자동 진단 엔진.

제품 컨셉:
  "5분 무료 진단" — 운영 DB 연결 정보만 입력하면
  자동으로 PII 위험도 / 컴플라이언스 / 이관 비용을 분석해서
  임원 보고서 한 장으로 출력.

영업 시나리오:
  - 잠재 고객사 임원 미팅 시 데모
  - 자가 진단 (체험판) → 유료 전환 유도
  - 분기별 보안 점검 자동화 (기존 고객 유지)

진단 항목 (5대 카테고리):
  1. PII 노출 (Privacy Risk)
  2. 컴플라이언스 (Compliance Coverage)
  3. 보안 설정 (Security Posture)
  4. 이관 복잡도 (Migration Complexity)
  5. 데이터 품질 (Data Quality)

종합 점수: 0~100점 + 등급 A/B/C/D/F

이 모듈(G-1)은 진단 엔진. 실제 DB 연결/분석은 기존 모듈 재사용:
  - PII 탐지: F-1a pii_detector
  - PII 샘플링: F-1f-1 pii_sampler
  - 컴플라이언스: F-2a~c compliance_rules
"""

from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from enum import Enum

_log = logging.getLogger("databridge.preflight")


# ════════════════════════════════════════════════════════════════════════════
# 데이터 모델
# ════════════════════════════════════════════════════════════════════════════

class AssessmentGrade(str, Enum):
    """진단 종합 등급"""
    A = "A"   # 90~100: 우수
    B = "B"   # 75~89:  양호
    C = "C"   # 60~74:  보통 (주의)
    D = "D"   # 40~59:  미흡 (개선 필요)
    F = "F"   # 0~39:   심각 (즉시 조치)


class AssessmentCategory(str, Enum):
    """진단 카테고리"""
    PRIVACY_RISK = "privacy_risk"            # PII 노출 위험
    COMPLIANCE = "compliance"                 # 컴플라이언스
    SECURITY = "security"                     # 보안 설정
    MIGRATION_COMPLEXITY = "migration"        # 이관 복잡도
    DATA_QUALITY = "data_quality"             # 데이터 품질


@dataclass
class CategoryScore:
    """카테고리별 점수"""
    category: AssessmentCategory
    score: float                              # 0~100
    grade: AssessmentGrade
    
    # 진단 결과
    findings: List[str] = field(default_factory=list)        # 발견사항
    recommendations: List[str] = field(default_factory=list)  # 권고
    
    # 메트릭 (카테고리별 다름)
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d['category'] = self.category.value
        d['grade'] = self.grade.value
        return d


@dataclass
class TopRisk:
    """Top 위험 항목"""
    severity: str                              # critical/high/medium/low
    title: str
    description: str
    affected_items: List[str] = field(default_factory=list)
    legal_reference: Optional[str] = None
    estimated_penalty: Optional[str] = None    # 예상 제재
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TopRecommendation:
    """Top 권고사항"""
    priority: int                              # 1=가장 중요
    title: str
    description: str
    estimated_effort: str                      # "1시간" / "1일" / "1주"
    business_value: str                        # 비즈니스 가치
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MigrationEstimate:
    """이관 예상 비용/시간"""
    estimated_duration_hours: float            # 예상 이관 시간
    estimated_data_size_gb: float
    table_count: int
    row_count_estimate: int
    
    # 위험도
    complexity_level: str                      # low/medium/high/very_high
    risk_factors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AssessmentReport:
    """Pre-Flight Assessment 종합 리포트"""
    
    # 기본 정보
    assessment_id: str
    timestamp: str                              # ISO 8601
    duration_seconds: float
    
    # 대상 정보
    source_db_type: str
    source_host: str                           # 마스킹 처리
    source_database: str
    table_count: int
    column_count: int
    
    # 종합 점수
    overall_score: float                        # 0~100
    overall_grade: AssessmentGrade
    
    # 카테고리별 점수
    category_scores: List[CategoryScore] = field(default_factory=list)
    
    # Top 항목
    top_risks: List[TopRisk] = field(default_factory=list)
    top_recommendations: List[TopRecommendation] = field(default_factory=list)
    
    # 이관 추정
    migration_estimate: Optional[MigrationEstimate] = None
    
    # 한 줄 요약 (임원 보고용)
    executive_summary: str = ""
    
    def to_dict(self) -> dict:
        d = {
            'assessment_id': self.assessment_id,
            'timestamp': self.timestamp,
            'duration_seconds': self.duration_seconds,
            'source_db_type': self.source_db_type,
            'source_host': self.source_host,
            'source_database': self.source_database,
            'table_count': self.table_count,
            'column_count': self.column_count,
            'overall_score': self.overall_score,
            'overall_grade': self.overall_grade.value,
            'category_scores': [c.to_dict() for c in self.category_scores],
            'top_risks': [r.to_dict() for r in self.top_risks],
            'top_recommendations': [r.to_dict() for r in self.top_recommendations],
            'migration_estimate': self.migration_estimate.to_dict() if self.migration_estimate else None,
            'executive_summary': self.executive_summary,
        }
        return d


# ════════════════════════════════════════════════════════════════════════════
# 점수 계산 헬퍼
# ════════════════════════════════════════════════════════════════════════════

def score_to_grade(score: float) -> AssessmentGrade:
    """점수 → 등급 변환"""
    if score >= 90:
        return AssessmentGrade.A
    elif score >= 75:
        return AssessmentGrade.B
    elif score >= 60:
        return AssessmentGrade.C
    elif score >= 40:
        return AssessmentGrade.D
    else:
        return AssessmentGrade.F


def grade_to_color(grade: AssessmentGrade) -> str:
    """등급 → 색상 (UI 용)"""
    return {
        AssessmentGrade.A: "#16a34a",  # green
        AssessmentGrade.B: "#65a30d",  # lime
        AssessmentGrade.C: "#ca8a04",  # yellow
        AssessmentGrade.D: "#ea580c",  # orange
        AssessmentGrade.F: "#dc2626",  # red
    }[grade]


def grade_to_korean(grade: AssessmentGrade) -> str:
    """등급 → 한글 라벨"""
    return {
        AssessmentGrade.A: "우수",
        AssessmentGrade.B: "양호",
        AssessmentGrade.C: "주의",
        AssessmentGrade.D: "개선 필요",
        AssessmentGrade.F: "즉시 조치",
    }[grade]


# ════════════════════════════════════════════════════════════════════════════
# 카테고리별 진단 함수
# ════════════════════════════════════════════════════════════════════════════

def assess_privacy_risk(
    pii_detections: List[Dict[str, Any]],
    total_columns: int,
) -> CategoryScore:
    """
    카테고리 1: PII 노출 위험
    
    점수 산출:
      - PII 컬럼 수 / 전체 컬럼 비율
      - CRITICAL/HIGH 등급 가중치
      - 마스킹 적용 여부
    """
    if total_columns == 0:
        return CategoryScore(
            category=AssessmentCategory.PRIVACY_RISK,
            score=100.0, grade=AssessmentGrade.A,
            findings=["분석 가능한 컬럼이 없습니다."],
        )
    
    # 등급별 카운트
    critical_count = sum(1 for d in pii_detections if d.get('sensitivity') == 'critical')
    high_count = sum(1 for d in pii_detections if d.get('sensitivity') == 'high')
    medium_count = sum(1 for d in pii_detections if d.get('sensitivity') == 'medium')
    low_count = sum(1 for d in pii_detections if d.get('sensitivity') == 'low')
    pii_total = critical_count + high_count + medium_count + low_count
    
    # 가중 점수 차감 (CRITICAL 컬럼 1개당 -5점, HIGH 1개당 -2점)
    deduction = (
        critical_count * 5.0 +
        high_count * 2.0 +
        medium_count * 0.5 +
        low_count * 0.1
    )
    
    # 컬럼 비율 페널티 (PII 비율이 높으면 추가 차감)
    pii_ratio = pii_total / total_columns
    if pii_ratio > 0.3:
        deduction += 10
    
    score = max(0.0, 100.0 - deduction)
    
    # 발견사항
    findings = []
    if critical_count:
        findings.append(f"고유식별정보({critical_count}개) — 주민/여권/운전면허/외국인등록번호")
    if high_count:
        findings.append(f"금융정보({high_count}개) — 카드/계좌/CVV")
    if medium_count:
        findings.append(f"일반 개인정보({medium_count}개) — 이름/연락처/주소")
    if low_count:
        findings.append(f"기술 식별자({low_count}개) — IP/MAC")
    if not findings:
        findings.append("PII 미탐지 — 양호한 상태")
    
    # 권고
    recommendations = []
    if critical_count > 0:
        recommendations.append(
            f"운영 → 비운영 환경 이관 시 CRITICAL 등급 {critical_count}개 컬럼 필수 마스킹 "
            "(개인정보보호법 §24의2 적용)"
        )
    if high_count > 0:
        recommendations.append(
            f"카드/계좌 정보 {high_count}개 컬럼은 PCI-DSS / 신용정보법 적용 — "
            "마스킹 또는 토큰화 권고"
        )
    if pii_ratio > 0.3:
        recommendations.append(
            f"PII 비율 {pii_ratio:.0%} — 일반 데이터와 분리 저장 검토"
        )
    
    return CategoryScore(
        category=AssessmentCategory.PRIVACY_RISK,
        score=round(score, 1),
        grade=score_to_grade(score),
        findings=findings,
        recommendations=recommendations,
        metrics={
            "total_columns": total_columns,
            "pii_columns": pii_total,
            "pii_ratio": round(pii_ratio, 3),
            "critical_count": critical_count,
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
        },
    )


def assess_compliance(
    compliance_report: Optional[Dict[str, Any]],
) -> CategoryScore:
    """
    카테고리 2: 컴플라이언스
    
    점수 산출:
      - PASS 비율 (skipped 제외)
      - CRITICAL FAIL = 큰 차감
    """
    if not compliance_report:
        return CategoryScore(
            category=AssessmentCategory.COMPLIANCE,
            score=70.0,  # 정보 부족 시 중간 점수
            grade=AssessmentGrade.C,
            findings=["컴플라이언스 점검을 수행할 정보가 부족합니다."],
            recommendations=["DB 연결 + 보안 설정 정보를 입력하면 정확한 점검 가능"],
        )
    
    checks = compliance_report.get('checks', [])
    if not checks:
        return CategoryScore(
            category=AssessmentCategory.COMPLIANCE,
            score=80.0, grade=AssessmentGrade.B,
            findings=["적용 가능한 룰이 없거나 모두 통과"],
        )
    
    # 카운트
    passed = sum(1 for c in checks if c.get('status') == 'pass')
    failed = sum(1 for c in checks if c.get('status') == 'fail')
    warns = sum(1 for c in checks if c.get('status') == 'warn')
    skipped = sum(1 for c in checks if c.get('status') in ('skip', 'na'))
    
    applicable = passed + failed + warns  # 적용 가능한 것만
    
    if applicable == 0:
        return CategoryScore(
            category=AssessmentCategory.COMPLIANCE,
            score=85.0, grade=AssessmentGrade.B,
            findings=["적용 가능한 컴플라이언스 룰 없음"],
        )
    
    # 기본 점수 = 통과 비율
    base_score = (passed / applicable) * 100
    
    # CRITICAL FAIL 추가 차감
    critical_fails = [c for c in checks 
                     if c.get('status') == 'fail' and c.get('severity') == 'critical']
    high_fails = [c for c in checks 
                  if c.get('status') == 'fail' and c.get('severity') == 'high']
    
    deduction = len(critical_fails) * 15 + len(high_fails) * 8 + warns * 2
    score = max(0.0, base_score - deduction)
    
    # 발견사항 (CRITICAL/HIGH FAIL 중심)
    findings = []
    for c in critical_fails[:3]:
        findings.append(f"🔴 [{c.get('framework')}] {c.get('title')}")
    for c in high_fails[:2]:
        findings.append(f"🟠 [{c.get('framework')}] {c.get('title')}")
    if warns > 0:
        findings.append(f"⚠️ 경고 {warns}건 — 개선 권고")
    if not findings:
        findings.append(f"✅ 적용 룰 {applicable}개 모두 통과")
    
    # 권고 (CRITICAL FAIL 의 권고 위주)
    recommendations = []
    seen_recs = set()
    for c in critical_fails + high_fails:
        rec = c.get('recommendation', '')
        if rec and rec not in seen_recs:
            recommendations.append(rec)
            seen_recs.add(rec)
        if len(recommendations) >= 5:
            break
    
    return CategoryScore(
        category=AssessmentCategory.COMPLIANCE,
        score=round(score, 1),
        grade=score_to_grade(score),
        findings=findings,
        recommendations=recommendations,
        metrics={
            "total_checks": len(checks),
            "passed": passed,
            "failed": failed,
            "warnings": warns,
            "skipped": skipped,
            "critical_fail_count": len(critical_fails),
            "high_fail_count": len(high_fails),
            "by_framework": compliance_report.get('by_framework', {}),
        },
    )


def assess_security(
    use_tls: Optional[bool],
    use_vpn: Optional[bool],
    audit_log: Optional[bool],
    backup: Optional[bool],
    privileged_user: Optional[bool],
) -> CategoryScore:
    """
    카테고리 3: 보안 설정
    
    5가지 핵심 보안 설정 점검 (각 20점)
    """
    score = 0
    findings = []
    recommendations = []
    
    # 1. TLS (20점)
    if use_tls is True:
        score += 20
        findings.append("✅ TLS 암호화 적용")
    elif use_tls is False:
        findings.append("❌ TLS 미적용 — 평문 전송 위험")
        recommendations.append("DB 연결에 TLS/SSL 옵션 활성화")
    else:
        score += 10  # 정보 부족 시 절반
        findings.append("⚠️ TLS 적용 여부 미확인")
    
    # 2. VPN/SSH (20점)
    if use_vpn is True:
        score += 20
        findings.append("✅ VPN/SSH 터널 사용")
    elif use_vpn is False:
        findings.append("❌ VPN/SSH 미사용 — 공용망 노출 위험")
        recommendations.append("운영-개발 간 통신은 VPN 필수")
    else:
        score += 10
    
    # 3. 감사 로그 (20점)
    if audit_log is True:
        score += 20
        findings.append("✅ 감사 로그 활성화")
    elif audit_log is False:
        findings.append("❌ 감사 로그 비활성 — 추적 불가")
        recommendations.append("DB 감사 로그 활성화 (1년 이상 보관)")
    else:
        score += 10
    
    # 4. 백업 (20점)
    if backup is True:
        score += 20
        findings.append("✅ 백업 활성화")
    elif backup is False:
        findings.append("❌ 백업 미설정 — 복구 불가능")
        recommendations.append("일일 백업 + 7일 보관 + 월 1회 복구 테스트")
    else:
        score += 10
    
    # 5. 최소 권한 (20점, 반전)
    if privileged_user is False:
        score += 20
        findings.append("✅ 최소 권한 원칙 준수")
    elif privileged_user is True:
        findings.append("❌ 시스템 관리자 권한 사용 — 최소 권한 원칙 위배")
        recommendations.append("이관 전용 계정 생성 (SELECT/INSERT 만)")
    else:
        score += 10
    
    return CategoryScore(
        category=AssessmentCategory.SECURITY,
        score=float(score),
        grade=score_to_grade(score),
        findings=findings,
        recommendations=recommendations,
        metrics={
            "tls": use_tls,
            "vpn": use_vpn,
            "audit_log": audit_log,
            "backup": backup,
            "minimal_privilege": (privileged_user is False),
        },
    )


def assess_migration_complexity(
    table_count: int,
    column_count: int,
    estimated_rows: int,
    estimated_size_gb: float,
    has_blob_columns: bool = False,
    has_special_types: bool = False,
) -> CategoryScore:
    """
    카테고리 4: 이관 복잡도
    
    점수 산출 (역산):
      - 테이블 수 / 컬럼 수 / row 수 / 데이터 크기
      - 특수 타입 (BLOB, GEOMETRY 등) 감점
    """
    score = 100.0
    findings = []
    recommendations = []
    risk_factors = []
    
    # 테이블 수
    if table_count > 100:
        score -= 10
        risk_factors.append(f"테이블 다수 ({table_count}개)")
    if table_count > 500:
        score -= 10
    
    # 컬럼 수
    if column_count > 1000:
        score -= 5
    
    # row 수
    if estimated_rows > 1_000_000:
        risk_factors.append(f"대용량 데이터 ({estimated_rows:,} rows)")
    if estimated_rows > 10_000_000:
        score -= 10
    if estimated_rows > 100_000_000:
        score -= 15
    
    # 데이터 크기
    if estimated_size_gb > 10:
        risk_factors.append(f"데이터 크기 {estimated_size_gb:.1f} GB")
    if estimated_size_gb > 100:
        score -= 10
    if estimated_size_gb > 500:
        score -= 15
    
    # 특수 타입
    if has_blob_columns:
        score -= 5
        risk_factors.append("BLOB/Binary 컬럼 포함")
    if has_special_types:
        score -= 10
        risk_factors.append("특수 타입 (GEOMETRY, JSON 등) 포함")
    
    score = max(0.0, score)
    
    # 복잡도 레벨
    if score >= 80:
        complexity = "low"
        findings.append("✅ 이관 복잡도 낮음 — 표준 절차로 진행 가능")
    elif score >= 60:
        complexity = "medium"
        findings.append("⚠️ 이관 복잡도 중간 — 주의 필요")
    elif score >= 40:
        complexity = "high"
        findings.append("🟠 이관 복잡도 높음 — 단계적 이관 권고")
    else:
        complexity = "very_high"
        findings.append("🔴 이관 복잡도 매우 높음 — 사전 PoC 필수")
    
    findings.extend([f"  - {rf}" for rf in risk_factors])
    
    if estimated_rows > 10_000_000:
        recommendations.append("CDC (Change Data Capture) 모드로 이관 권고")
    if has_blob_columns:
        recommendations.append("BLOB 컬럼은 별도 배치로 이관 (메모리 보호)")
    if estimated_size_gb > 100:
        recommendations.append("이관 시간 단축을 위한 병렬화 (테이블별 동시 이관)")
    
    return CategoryScore(
        category=AssessmentCategory.MIGRATION_COMPLEXITY,
        score=round(score, 1),
        grade=score_to_grade(score),
        findings=findings,
        recommendations=recommendations,
        metrics={
            "table_count": table_count,
            "column_count": column_count,
            "estimated_rows": estimated_rows,
            "estimated_size_gb": estimated_size_gb,
            "has_blob": has_blob_columns,
            "has_special_types": has_special_types,
            "complexity_level": complexity,
        },
    )


def assess_data_quality(
    null_ratio_estimate: float = 0.0,
    has_orphan_records: bool = False,
    duplicate_ratio: float = 0.0,
) -> CategoryScore:
    """
    카테고리 5: 데이터 품질 (간소화 버전 — 실제 분석 어려우므로 자가 평가 위주)
    """
    score = 100.0
    findings = []
    recommendations = []
    
    if null_ratio_estimate > 0.3:
        score -= 20
        findings.append(f"⚠️ NULL 비율 높음 ({null_ratio_estimate:.0%})")
        recommendations.append("이관 전 NULL 값 정합성 검토")
    
    if has_orphan_records:
        score -= 15
        findings.append("⚠️ Orphan record 가능성")
        recommendations.append("FK 무결성 검증 후 이관")
    
    if duplicate_ratio > 0.05:
        score -= 10
        findings.append(f"⚠️ 중복 데이터 ({duplicate_ratio:.0%})")
        recommendations.append("중복 제거 또는 deduplication 전략 수립")
    
    if not findings:
        findings.append("✅ 기본적인 데이터 품질 양호")
    
    return CategoryScore(
        category=AssessmentCategory.DATA_QUALITY,
        score=round(max(0.0, score), 1),
        grade=score_to_grade(score),
        findings=findings,
        recommendations=recommendations,
        metrics={
            "null_ratio": null_ratio_estimate,
            "has_orphan_records": has_orphan_records,
            "duplicate_ratio": duplicate_ratio,
        },
    )


# ════════════════════════════════════════════════════════════════════════════
# Top 항목 추출
# ════════════════════════════════════════════════════════════════════════════

def extract_top_risks(
    pii_detections: List[Dict[str, Any]],
    compliance_report: Optional[Dict[str, Any]],
    limit: int = 5,
) -> List[TopRisk]:
    """모든 카테고리에서 Top 위험 추출"""
    risks: List[TopRisk] = []
    
    # PII Critical
    critical_pii = [d for d in pii_detections if d.get('sensitivity') == 'critical']
    if critical_pii:
        cols = [d.get('column_name', '?') for d in critical_pii[:5]]
        risks.append(TopRisk(
            severity="critical",
            title="고유식별정보 평문 노출",
            description=(
                f"주민번호/여권 등 고유식별정보 {len(critical_pii)}개 컬럼 탐지. "
                "비운영 환경 이관 시 평문 저장 = 개인정보보호법 §24의2 위반"
            ),
            affected_items=cols,
            legal_reference="개인정보보호법 §24의2",
            estimated_penalty="매출액 3% 이내 과징금 + 3천만원 이하 과태료",
        ))
    
    # 컴플라이언스 CRITICAL FAIL
    if compliance_report:
        for check in compliance_report.get('checks', []):
            if (check.get('status') == 'fail' and 
                check.get('severity') == 'critical'):
                risks.append(TopRisk(
                    severity="critical",
                    title=check.get('title', ''),
                    description=check.get('detail', ''),
                    affected_items=list(check.get('evidence', {}).keys()),
                    legal_reference=check.get('legal_basis'),
                ))
                if len(risks) >= limit:
                    break
    
    return risks[:limit]


def extract_top_recommendations(
    category_scores: List[CategoryScore],
    limit: int = 5,
) -> List[TopRecommendation]:
    """모든 카테고리의 권고에서 Top 추출 (점수 낮은 카테고리 우선)"""
    
    # 카테고리 우선순위 (낮은 점수 = 더 시급)
    sorted_cats = sorted(category_scores, key=lambda c: c.score)
    
    priority_titles = {
        AssessmentCategory.PRIVACY_RISK: "개인정보 마스킹 정책 적용",
        AssessmentCategory.COMPLIANCE: "컴플라이언스 위반 항목 시정",
        AssessmentCategory.SECURITY: "보안 설정 강화",
        AssessmentCategory.MIGRATION_COMPLEXITY: "이관 전략 최적화",
        AssessmentCategory.DATA_QUALITY: "데이터 품질 개선",
    }
    
    effort_estimates = {
        AssessmentCategory.PRIVACY_RISK: "1~2일",
        AssessmentCategory.COMPLIANCE: "1주",
        AssessmentCategory.SECURITY: "1~2시간",
        AssessmentCategory.MIGRATION_COMPLEXITY: "사전 PoC 1주",
        AssessmentCategory.DATA_QUALITY: "1주",
    }
    
    business_values = {
        AssessmentCategory.PRIVACY_RISK: "법적 리스크 제거 + 임원 보고 가능",
        AssessmentCategory.COMPLIANCE: "감사 대응력 향상 + 인증 유지",
        AssessmentCategory.SECURITY: "기본 보안 baseline 확보",
        AssessmentCategory.MIGRATION_COMPLEXITY: "이관 실패 위험 최소화",
        AssessmentCategory.DATA_QUALITY: "정확한 의사결정 가능",
    }
    
    recommendations: List[TopRecommendation] = []
    priority = 1
    
    for cat_score in sorted_cats:
        if cat_score.score >= 90:
            continue  # 이미 좋은 카테고리는 권고 안 만들기
        if not cat_score.recommendations:
            continue
        
        # 첫 번째 권고만 (대표 권고)
        first_rec = cat_score.recommendations[0]
        
        recommendations.append(TopRecommendation(
            priority=priority,
            title=priority_titles.get(cat_score.category, "개선 필요"),
            description=first_rec,
            estimated_effort=effort_estimates.get(cat_score.category, "1주"),
            business_value=business_values.get(cat_score.category, ""),
        ))
        priority += 1
        
        if len(recommendations) >= limit:
            break
    
    return recommendations


# ════════════════════════════════════════════════════════════════════════════
# 종합 점수 계산
# ════════════════════════════════════════════════════════════════════════════

# 카테고리 가중치 (합 = 1.0)
CATEGORY_WEIGHTS = {
    AssessmentCategory.PRIVACY_RISK: 0.30,         # 30%
    AssessmentCategory.COMPLIANCE: 0.25,           # 25%
    AssessmentCategory.SECURITY: 0.20,             # 20%
    AssessmentCategory.MIGRATION_COMPLEXITY: 0.15, # 15%
    AssessmentCategory.DATA_QUALITY: 0.10,         # 10%
}


def calculate_overall_score(category_scores: List[CategoryScore]) -> float:
    """카테고리 점수의 가중 평균 → 종합 점수"""
    if not category_scores:
        return 0.0
    
    total = 0.0
    weight_sum = 0.0
    
    for cs in category_scores:
        weight = CATEGORY_WEIGHTS.get(cs.category, 0.1)
        total += cs.score * weight
        weight_sum += weight
    
    return round(total / weight_sum, 1) if weight_sum > 0 else 0.0


def generate_executive_summary(
    overall_score: float,
    overall_grade: AssessmentGrade,
    category_scores: List[CategoryScore],
    top_risks: List[TopRisk],
) -> str:
    """임원 보고용 한 줄 요약 생성"""
    
    grade_label = grade_to_korean(overall_grade)
    
    # 가장 낮은 카테고리
    weakest = min(category_scores, key=lambda c: c.score) if category_scores else None
    
    cat_names = {
        AssessmentCategory.PRIVACY_RISK: "개인정보 보호",
        AssessmentCategory.COMPLIANCE: "컴플라이언스",
        AssessmentCategory.SECURITY: "보안 설정",
        AssessmentCategory.MIGRATION_COMPLEXITY: "이관 복잡도",
        AssessmentCategory.DATA_QUALITY: "데이터 품질",
    }
    
    summary = f"종합 점수 {overall_score}점 ({grade_label} 등급). "
    
    if overall_grade in (AssessmentGrade.A, AssessmentGrade.B):
        summary += "전반적으로 양호한 상태이며, "
        if weakest and weakest.score < overall_score - 15:
            summary += f"{cat_names[weakest.category]}({weakest.score:.0f}점) 영역의 부분 개선 권고."
        else:
            summary += "현 수준 유지 권장."
    elif overall_grade == AssessmentGrade.C:
        summary += "주의가 필요한 상태로, "
        if weakest:
            summary += f"{cat_names[weakest.category]}({weakest.score:.0f}점) 우선 개선 필요."
    elif overall_grade == AssessmentGrade.D:
        summary += "개선이 필요한 상태로, "
        critical_count = len([r for r in top_risks if r.severity == 'critical'])
        if critical_count:
            summary += f"CRITICAL 위험 {critical_count}건 즉시 조치 권고."
        else:
            summary += "다중 영역 동시 개선 필요."
    else:  # F
        summary += "심각한 위험 상태로, 즉시 조치 필요. "
        critical_count = len([r for r in top_risks if r.severity == 'critical'])
        summary += f"법적 리스크 {critical_count}건 포함 — 우선 대응 시급."
    
    return summary


# ════════════════════════════════════════════════════════════════════════════
# 메인 진단 API
# ════════════════════════════════════════════════════════════════════════════

def run_assessment(
    *,
    assessment_id: str,
    source_db_type: str,
    source_host: str,
    source_database: str,
    table_count: int,
    column_count: int,
    
    # PII 분석 결과
    pii_detections: Optional[List[Dict[str, Any]]] = None,
    
    # 컴플라이언스 분석 결과
    compliance_report: Optional[Dict[str, Any]] = None,
    
    # 보안 설정 (수동 입력 또는 추정)
    use_tls: Optional[bool] = None,
    use_vpn: Optional[bool] = None,
    audit_log: Optional[bool] = None,
    backup: Optional[bool] = None,
    privileged_user: Optional[bool] = None,
    
    # 이관 추정
    estimated_rows: int = 0,
    estimated_size_gb: float = 0.0,
    has_blob_columns: bool = False,
    has_special_types: bool = False,
    
    # 데이터 품질
    null_ratio: float = 0.0,
    has_orphan_records: bool = False,
    duplicate_ratio: float = 0.0,
) -> AssessmentReport:
    """
    Pre-Flight Assessment 실행 — 모든 카테고리 진단 후 리포트 생성.
    
    이 함수는 "분석 데이터" 를 받아서 점수를 계산만 함.
    실제 DB 연결 + PII 탐지 + 컴플라이언스 점검은 호출자가 미리 수행.
    """
    from datetime import datetime, timezone
    start = time.monotonic()
    
    pii_detections = pii_detections or []
    
    # 1. 카테고리별 진단
    category_scores = [
        assess_privacy_risk(pii_detections, column_count),
        assess_compliance(compliance_report),
        assess_security(use_tls, use_vpn, audit_log, backup, privileged_user),
        assess_migration_complexity(
            table_count, column_count, estimated_rows, estimated_size_gb,
            has_blob_columns, has_special_types,
        ),
        assess_data_quality(null_ratio, has_orphan_records, duplicate_ratio),
    ]
    
    # 2. 종합 점수
    overall_score = calculate_overall_score(category_scores)
    overall_grade = score_to_grade(overall_score)
    
    # 3. Top 항목
    top_risks = extract_top_risks(pii_detections, compliance_report, limit=5)
    top_recommendations = extract_top_recommendations(category_scores, limit=5)
    
    # 4. 이관 추정 모델
    migration_estimate = MigrationEstimate(
        estimated_duration_hours=_estimate_migration_hours(
            estimated_rows, estimated_size_gb, table_count
        ),
        estimated_data_size_gb=estimated_size_gb,
        table_count=table_count,
        row_count_estimate=estimated_rows,
        complexity_level=_get_complexity_level(category_scores),
        risk_factors=_get_risk_factors(category_scores),
    )
    
    # 5. 임원 요약
    summary = generate_executive_summary(
        overall_score, overall_grade, category_scores, top_risks
    )
    
    # 6. 호스트 마스킹 (보안)
    masked_host = _mask_host(source_host)
    
    duration = round(time.monotonic() - start, 3)
    
    return AssessmentReport(
        assessment_id=assessment_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        duration_seconds=duration,
        source_db_type=source_db_type,
        source_host=masked_host,
        source_database=source_database,
        table_count=table_count,
        column_count=column_count,
        overall_score=overall_score,
        overall_grade=overall_grade,
        category_scores=category_scores,
        top_risks=top_risks,
        top_recommendations=top_recommendations,
        migration_estimate=migration_estimate,
        executive_summary=summary,
    )


# ════════════════════════════════════════════════════════════════════════════
# 헬퍼
# ════════════════════════════════════════════════════════════════════════════

def _estimate_migration_hours(rows: int, size_gb: float, tables: int) -> float:
    """이관 시간 추정 (단순 모델)"""
    # 가정: 1만 rows = 1초, 1 GB = 5분, 테이블당 30초 오버헤드
    hours_by_rows = rows / 10000 / 3600
    hours_by_size = size_gb * 5 / 60
    hours_by_tables = tables * 30 / 3600
    return round(max(hours_by_rows, hours_by_size) + hours_by_tables, 2)


def _get_complexity_level(scores: List[CategoryScore]) -> str:
    """이관 복잡도 추출"""
    for s in scores:
        if s.category == AssessmentCategory.MIGRATION_COMPLEXITY:
            return s.metrics.get("complexity_level", "medium")
    return "medium"


def _get_risk_factors(scores: List[CategoryScore]) -> List[str]:
    """위험 요인 모음"""
    factors = []
    for s in scores:
        if s.score < 60:
            factors.append(f"{s.category.value} 점수 {s.score}점")
    return factors


def _mask_host(host: str) -> str:
    """호스트명 마스킹 (IP/도메인 보호)"""
    if not host:
        return ""
    
    # IP 형식
    if all(p.replace('.', '').isdigit() for p in host.split('.')):
        parts = host.split('.')
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.***.***"
    
    # 도메인
    if '.' in host:
        parts = host.split('.')
        if len(parts) >= 2:
            return f"***.{'.'.join(parts[-2:])}"
    
    return host[:3] + '***'
