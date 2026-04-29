"""
compliance_rules.py — Phase F-2a (2026-04-25)

컴플라이언스 자동 점검 규칙 엔진.

설계 철학:
  - 법규는 본질적으로 "체크리스트". 사람이 사람을 검사하는 일을 
    AI/자동화로 옮겨도 그 본질은 같음.
  - 규칙(Rule)은 데이터-주도 (declarative). 새 법규 추가 = JSON-like 규칙 추가.
  - 검증 함수(checker)는 명시적. 무엇을 보고 어떻게 판정했는지 audit trail 남김.
  - 한국 금융권 우선, 글로벌 (GDPR/PCI-DSS) 보조.

작동:
  Job 컨텍스트(테이블/PII/이관 설정) + 룰셋 → ComplianceReport
  
  ComplianceReport = {
    overall_status: PASS | WARN | FAIL,
    checks: [ChecklistItem...],   # 항목별 결과 (audit-friendly)
    by_framework: {ISMS-P: ..., GDPR: ...},   # 프레임워크별 요약
    recommendations: [...],
  }

법규 매핑 (예시 — 룰셋은 별도 모듈):
  RRN 마스킹 안 함 → 개인정보보호법 §24의2 위반
  TLS 미사용     → 전자금융감독규정 §13 (보안조치) 위반
  접근 로그 미보관 → ISMS-P 2.6.2 위반
  CVV 저장      → PCI-DSS Requirement 3.2.2 위반

이 모듈(F-2a)은 골격만. 실제 규칙은 F-2b/c/d 에서 추가.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Callable
from enum import Enum

_log = logging.getLogger("databridge.compliance")


# ════════════════════════════════════════════════════════════════════════════
# 핵심 Enum / 데이터 클래스
# ════════════════════════════════════════════════════════════════════════════

class ComplianceFramework(str, Enum):
    """컴플라이언스 프레임워크"""
    
    # 한국 금융권
    EFA = "efa"                          # 전자금융감독규정
    CIA = "cia"                          # 신용정보업감독규정
    
    # 한국 일반
    PIPA = "pipa"                        # 개인정보보호법
    ISMS_P = "isms_p"                    # 정보보호 및 개인정보보호 관리체계 (KISA)
    
    # 글로벌
    GDPR = "gdpr"                        # EU GDPR
    PCI_DSS = "pci_dss"                  # PCI-DSS (카드)
    SOX = "sox"                          # Sarbanes-Oxley (US, 회계)
    HIPAA = "hipaa"                      # HIPAA (US, 헬스케어)


class CheckSeverity(str, Enum):
    """위반 심각도 — DataBridge 자체 분류"""
    CRITICAL = "critical"    # 법적 처벌 가능 (RRN 마스킹 안 함 등)
    HIGH = "high"            # 감사 지적 가능 (백업 미흡 등)
    MEDIUM = "medium"        # 권고 사항 (로그 보관 부족 등)
    LOW = "low"              # 베스트 프랙티스 (네이밍 규칙 등)
    INFO = "info"            # 참고 사항


class CheckStatus(str, Enum):
    """단일 항목 점검 결과"""
    PASS = "pass"            # 통과
    FAIL = "fail"            # 위반 (심각도에 따라 분류)
    WARN = "warn"            # 주의 (개선 권고)
    SKIP = "skip"            # 점검 대상 아님 (조건 미해당)
    NA = "na"                # 데이터 부족으로 판단 불가


class OverallStatus(str, Enum):
    """전체 점검 결과"""
    PASS = "pass"            # 모든 CRITICAL/HIGH 통과
    WARN = "warn"            # CRITICAL 통과, MEDIUM 이하 일부 WARN
    FAIL = "fail"            # CRITICAL 또는 HIGH 위반 있음


@dataclass
class ChecklistItem:
    """단일 점검 항목 (audit-friendly)"""
    rule_id: str                                  # 'pipa-24-2', 'pci-3-2-2' 등
    framework: ComplianceFramework
    severity: CheckSeverity
    title: str                                    # 한 줄 요약 (한글)
    description: str                              # 상세 설명
    legal_basis: str                              # 법조문 / 표준 ref
    
    # 점검 결과
    status: CheckStatus
    detail: str = ""                              # 무엇을 보고 어떻게 판정했는지
    evidence: Dict[str, Any] = field(default_factory=dict)  # 증거 (감사용)
    recommendation: str = ""                      # 위반/주의 시 권고
    
    # 메타
    auto_fixable: bool = False                    # 자동 수정 가능 여부
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d['framework'] = self.framework.value
        d['severity'] = self.severity.value
        d['status'] = self.status.value
        return d


@dataclass
class ComplianceContext:
    """점검 입력 — Job 의 모든 정보"""
    
    # Job 기본 정보
    job_id: Optional[str] = None
    src_db_type: str = ""                         # mssql/mysql/postgres
    tgt_db_type: str = ""
    src_environment: str = ""                     # production/staging/dev
    tgt_environment: str = ""                     # production/dev/qa/analytics
    
    # 데이터 정보
    tables: List[Dict[str, Any]] = field(default_factory=list)
    total_rows_estimate: int = 0
    
    # PII 정보 (F-1 결과)
    pii_detections: List[Dict[str, Any]] = field(default_factory=list)
    privacy_decisions: List[Dict[str, Any]] = field(default_factory=list)
    privacy_preset: str = ""
    privacy_skipped: bool = False
    
    # 보안 정보
    use_tls: Optional[bool] = None                # in-transit 암호화
    src_tls_version: Optional[str] = None         # TLS 1.2/1.3
    tgt_tls_version: Optional[str] = None
    use_vpn_or_ssh_tunnel: Optional[bool] = None
    
    # 인증/권한
    auth_method: str = ""                         # password/iam/cert
    privileged_user: Optional[bool] = None        # 이관 사용자 권한 수준
    audit_log_enabled: Optional[bool] = None
    
    # 백업/보관
    backup_enabled: Optional[bool] = None
    backup_retention_days: Optional[int] = None
    
    # 운영 시나리오 추정
    @property
    def is_prod_to_lower(self) -> bool:
        """운영 → 비운영 이관 여부"""
        prod_keywords = ('prod', 'production', '운영')
        lower_keywords = ('dev', 'qa', 'staging', 'analytics', 'test', '개발', '분석')
        src = self.src_environment.lower()
        tgt = self.tgt_environment.lower()
        is_src_prod = any(k in src for k in prod_keywords)
        is_tgt_lower = any(k in tgt for k in lower_keywords)
        return is_src_prod and is_tgt_lower
    
    @property
    def has_critical_pii(self) -> bool:
        """CRITICAL 등급 PII (RRN 등) 포함 여부"""
        return any(
            d.get('sensitivity') == 'critical'
            for d in self.pii_detections
        )
    
    @property
    def has_card_data(self) -> bool:
        """카드 데이터 포함 (PCI-DSS 적용)"""
        card_categories = {'card_number', 'card_cvv'}
        return any(
            d.get('category') in card_categories
            for d in self.pii_detections
        )
    
    @property
    def masked_pii_columns(self) -> set:
        """실제 마스킹 적용 컬럼 set"""
        return {
            d.get('column_name')
            for d in self.privacy_decisions
            if d.get('strategy') and d.get('strategy') != 'keep'
        }


@dataclass
class ComplianceReport:
    """전체 점검 결과"""
    overall_status: OverallStatus
    job_id: Optional[str] = None
    
    # 항목별 결과
    checks: List[ChecklistItem] = field(default_factory=list)
    
    # 통계
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    skipped: int = 0
    
    # 프레임워크별 요약
    by_framework: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    # 핵심 권고 (상위 5개)
    key_recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        d = {
            'overall_status': self.overall_status.value,
            'job_id': self.job_id,
            'checks': [c.to_dict() for c in self.checks],
            'total_checks': self.total_checks,
            'passed': self.passed,
            'failed': self.failed,
            'warnings': self.warnings,
            'skipped': self.skipped,
            'by_framework': self.by_framework,
            'key_recommendations': self.key_recommendations,
        }
        return d


# ════════════════════════════════════════════════════════════════════════════
# 규칙 인터페이스
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class ComplianceRule:
    """단일 규칙 정의"""
    rule_id: str
    framework: ComplianceFramework
    severity: CheckSeverity
    title: str
    description: str
    legal_basis: str
    
    # 점검 함수 — context 받아서 ChecklistItem 반환
    checker: Callable[[ComplianceContext], ChecklistItem]
    
    # 적용 조건 (None 이면 항상 적용)
    applies_when: Optional[Callable[[ComplianceContext], bool]] = None
    
    # 권고 (위반 시)
    recommendation: str = ""
    auto_fixable: bool = False
    
    def evaluate(self, ctx: ComplianceContext) -> ChecklistItem:
        """규칙 평가 — 적용 조건 검사 후 checker 호출"""
        # 적용 안 되면 SKIP
        if self.applies_when and not self.applies_when(ctx):
            return ChecklistItem(
                rule_id=self.rule_id,
                framework=self.framework,
                severity=self.severity,
                title=self.title,
                description=self.description,
                legal_basis=self.legal_basis,
                status=CheckStatus.SKIP,
                detail="이 Job 에는 적용되지 않는 규칙",
                recommendation=self.recommendation,
                auto_fixable=self.auto_fixable,
            )
        
        try:
            item = self.checker(ctx)
            # checker 가 일부 필드만 채울 수도 있으므로 룰 정의값으로 무조건 보강
            # (메타데이터는 룰이 권위, checker 는 status/detail/evidence 만 책임)
            item.rule_id = self.rule_id
            item.framework = self.framework
            item.severity = self.severity
            item.title = self.title
            item.description = self.description
            item.legal_basis = self.legal_basis
            if not item.recommendation and item.status in (CheckStatus.FAIL, CheckStatus.WARN):
                item.recommendation = self.recommendation
            item.auto_fixable = self.auto_fixable
            return item
        except Exception as e:
            _log.warning(f"[Compliance] 규칙 {self.rule_id} 평가 실패: {e}")
            return ChecklistItem(
                rule_id=self.rule_id,
                framework=self.framework,
                severity=self.severity,
                title=self.title,
                description=self.description,
                legal_basis=self.legal_basis,
                status=CheckStatus.NA,
                detail=f"평가 중 에러 발생: {e}",
            )


# ════════════════════════════════════════════════════════════════════════════
# 룰셋 레지스트리
# ════════════════════════════════════════════════════════════════════════════

class RuleRegistry:
    """모든 컴플라이언스 규칙 보관소.
    
    F-2b/c/d 에서 add_rule 로 등록.
    실행 시점에 ctx 와 함께 evaluate.
    """
    
    def __init__(self):
        self._rules: List[ComplianceRule] = []
    
    def add_rule(self, rule: ComplianceRule) -> None:
        """규칙 추가"""
        # 중복 ID 방지
        if any(r.rule_id == rule.rule_id for r in self._rules):
            _log.warning(f"[Compliance] 중복 rule_id 스킵: {rule.rule_id}")
            return
        self._rules.append(rule)
    
    def add_rules(self, rules: List[ComplianceRule]) -> None:
        """다수 규칙 추가"""
        for r in rules:
            self.add_rule(r)
    
    def get_rules(
        self,
        frameworks: Optional[List[ComplianceFramework]] = None,
    ) -> List[ComplianceRule]:
        """규칙 조회 (프레임워크 필터링)"""
        if not frameworks:
            return list(self._rules)
        framework_set = set(frameworks)
        return [r for r in self._rules if r.framework in framework_set]
    
    def evaluate_all(
        self,
        ctx: ComplianceContext,
        frameworks: Optional[List[ComplianceFramework]] = None,
    ) -> ComplianceReport:
        """모든 규칙 평가 → ComplianceReport"""
        rules = self.get_rules(frameworks)
        items = [r.evaluate(ctx) for r in rules]
        return self._build_report(items, ctx.job_id)
    
    def _build_report(
        self,
        items: List[ChecklistItem],
        job_id: Optional[str] = None,
    ) -> ComplianceReport:
        """체크리스트 → 종합 리포트"""
        # 카운트
        total = len(items)
        passed = sum(1 for i in items if i.status == CheckStatus.PASS)
        failed = sum(1 for i in items if i.status == CheckStatus.FAIL)
        warnings = sum(1 for i in items if i.status == CheckStatus.WARN)
        skipped = sum(1 for i in items if i.status in (CheckStatus.SKIP, CheckStatus.NA))
        
        # 전체 상태 판정
        critical_failed = any(
            i.severity == CheckSeverity.CRITICAL and i.status == CheckStatus.FAIL
            for i in items
        )
        high_failed = any(
            i.severity == CheckSeverity.HIGH and i.status == CheckStatus.FAIL
            for i in items
        )
        
        if critical_failed or high_failed:
            overall = OverallStatus.FAIL
        elif warnings > 0 or failed > 0:
            overall = OverallStatus.WARN
        else:
            overall = OverallStatus.PASS
        
        # 프레임워크별 요약
        by_framework: Dict[str, Dict[str, int]] = {}
        for item in items:
            fw = item.framework.value
            by_framework.setdefault(fw, {'pass': 0, 'fail': 0, 'warn': 0, 'skip': 0, 'na': 0})
            by_framework[fw][item.status.value] = by_framework[fw].get(item.status.value, 0) + 1
        
        # 핵심 권고 (CRITICAL FAIL 우선, 그다음 HIGH FAIL, WARN)
        key_recs = []
        priority = [
            (CheckSeverity.CRITICAL, CheckStatus.FAIL),
            (CheckSeverity.HIGH, CheckStatus.FAIL),
            (CheckSeverity.CRITICAL, CheckStatus.WARN),
            (CheckSeverity.HIGH, CheckStatus.WARN),
            (CheckSeverity.MEDIUM, CheckStatus.FAIL),
            (CheckSeverity.MEDIUM, CheckStatus.WARN),
        ]
        for sev, st in priority:
            for item in items:
                if item.severity == sev and item.status == st and item.recommendation:
                    if item.recommendation not in key_recs:
                        key_recs.append(item.recommendation)
                if len(key_recs) >= 5:
                    break
            if len(key_recs) >= 5:
                break
        
        return ComplianceReport(
            overall_status=overall,
            job_id=job_id,
            checks=items,
            total_checks=total,
            passed=passed,
            failed=failed,
            warnings=warnings,
            skipped=skipped,
            by_framework=by_framework,
            key_recommendations=key_recs,
        )


# ════════════════════════════════════════════════════════════════════════════
# 빌더 헬퍼 (F-2b/c/d 에서 룰 정의 시 편의용)
# ════════════════════════════════════════════════════════════════════════════

def make_simple_check(
    condition_fn: Callable[[ComplianceContext], bool],
    pass_message: str = "정상",
    fail_message: str = "위반",
) -> Callable[[ComplianceContext], ChecklistItem]:
    """
    단순 boolean 조건 → checker 함수.
    
    사용:
        rule = ComplianceRule(
            rule_id='efa-13-1',
            ...,
            checker=make_simple_check(
                lambda ctx: ctx.use_tls is True,
                pass_message='TLS 적용됨',
                fail_message='TLS 미적용',
            ),
        )
    """
    def checker(ctx: ComplianceContext) -> ChecklistItem:
        passed = bool(condition_fn(ctx))
        return ChecklistItem(
            rule_id="",  # evaluate() 에서 채움
            framework=ComplianceFramework.PIPA,  # evaluate() 에서 채움
            severity=CheckSeverity.MEDIUM,  # evaluate() 에서 채움
            title="",
            description="",
            legal_basis="",
            status=CheckStatus.PASS if passed else CheckStatus.FAIL,
            detail=pass_message if passed else fail_message,
        )
    return checker


# 글로벌 레지스트리 (싱글톤)
_default_registry = RuleRegistry()


def get_default_registry() -> RuleRegistry:
    """전역 룰셋 레지스트리 (F-2b/c/d 가 여기에 등록)"""
    return _default_registry


def evaluate_compliance(
    ctx: ComplianceContext,
    frameworks: Optional[List[ComplianceFramework]] = None,
) -> ComplianceReport:
    """편의 함수 — 기본 레지스트리로 평가"""
    return _default_registry.evaluate_all(ctx, frameworks)
