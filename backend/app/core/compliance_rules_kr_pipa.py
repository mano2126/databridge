"""
compliance_rules_kr_pipa.py — Phase F-2c (2026-04-25)

한국 일반 컴플라이언스 룰셋:
  1. 개인정보보호법 (PIPA)
  2. 개인정보의 안전성 확보조치 기준 (보호위원회 고시)
  3. 가명정보 처리 가이드라인 (보호위원회, 2024.2)
  4. ISMS-P 인증기준 (KISA)

법조문 출처 (2024~2025년 기준):
  - 국가법령정보센터 (www.law.go.kr)
  - 개인정보보호위원회 안내서 (2024.10)
  - 가명정보 처리 가이드라인 (2024.2)
  - 고유식별정보 안전조치 관리실태 조사 매뉴얼 (2024.9)

핵심 조문:
  - 개인정보보호법 §15      개인정보 처리 원칙
  - 개인정보보호법 §23      민감정보 처리 제한
  - 개인정보보호법 §24      고유식별정보 처리 제한
  - 개인정보보호법 §24의2   주민등록번호 처리 제한 (암호화 의무)
  - 개인정보보호법 §28의2   가명정보의 처리 등
  - 개인정보보호법 §28의4   가명정보 안전조치 의무
  - 개인정보보호법 §29      안전조치 의무
  - 시행령 §21            고유식별정보 안전성 확보조치
  - 시행령 §29의5         가명정보에 대한 안전성 확보조치
  - 시행령 §30            안전성 확보조치 기준

위반 시 제재:
  - §24의2 위반: 매출액의 3% 이내 과징금 + 3천만원 이하 과태료
"""

from __future__ import annotations
import logging
from typing import List

from app.core.compliance_rules import (
    ComplianceFramework, CheckSeverity, CheckStatus,
    ChecklistItem, ComplianceContext, ComplianceRule,
)

_log = logging.getLogger("databridge.compliance.kr_pipa")


# ════════════════════════════════════════════════════════════════════════════
# 개인정보보호법 (PIPA) 룰
# ════════════════════════════════════════════════════════════════════════════

def _check_pipa_rrn_encryption(ctx: ComplianceContext) -> ChecklistItem:
    """
    개인정보보호법 §24의2 (주민등록번호 처리의 제한)
    
    "주민등록번호가 분실·도난·유출·위조·변조 또는 훼손되지 아니하도록 
     암호화 조치를 통하여 안전하게 보관하여야 한다."
    
    위반 시: 매출액 3% 이내 과징금 + 3천만원 이하 과태료
    
    DataBridge 관점:
      이관 시 RRN 컬럼이 평문으로 전송/저장되면 안 됨.
      마스킹 또는 해시 적용 필요.
    """
    rrn_cols = [d for d in ctx.pii_detections
                if d.get('category') == 'rrn']
    
    if not rrn_cols:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.PIPA,
            severity=CheckSeverity.CRITICAL, title="", description="", legal_basis="",
            status=CheckStatus.SKIP,
            detail="주민등록번호 컬럼 미탐지",
        )
    
    # 운영→비운영 이관: 마스킹 필수
    # 운영→운영 (DR): 양쪽 모두 보호된 환경, 마스킹 안 해도 OK
    if ctx.is_prod_to_lower:
        unmasked = [c['column_name'] for c in rrn_cols
                    if c['column_name'] not in ctx.masked_pii_columns]
        if unmasked:
            return ChecklistItem(
                rule_id="", framework=ComplianceFramework.PIPA,
                severity=CheckSeverity.CRITICAL, title="", description="", legal_basis="",
                status=CheckStatus.FAIL,
                detail=f"비운영 환경으로 RRN 평문 이관: {unmasked} (§24의2 위반 — 과징금/과태료 대상)",
                evidence={
                    "unmasked_rrn_columns": unmasked,
                    "max_penalty": "매출액 3% 이내 과징금 + 3천만원 이하 과태료",
                },
            )
    
    # TLS 미사용도 위반 (in-transit 암호화)
    if ctx.use_tls is False:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.PIPA,
            severity=CheckSeverity.CRITICAL, title="", description="", legal_basis="",
            status=CheckStatus.FAIL,
            detail="RRN 포함 데이터 평문 전송 (TLS 미적용)",
            evidence={"rrn_columns": [c['column_name'] for c in rrn_cols]},
        )
    
    return ChecklistItem(
        rule_id="", framework=ComplianceFramework.PIPA,
        severity=CheckSeverity.CRITICAL, title="", description="", legal_basis="",
        status=CheckStatus.PASS,
        detail=f"RRN {len(rrn_cols)}개 컬럼 암호화/마스킹 조치 완료",
    )


def _check_pipa_unique_id_protection(ctx: ComplianceContext) -> ChecklistItem:
    """
    개인정보보호법 §24 (고유식별정보의 처리 제한) + 시행령 §21
    
    고유식별정보 = 주민등록번호 / 여권번호 / 운전면허번호 / 외국인등록번호
    "분실·도난·유출·위조·변조 또는 훼손되지 아니하도록 암호화 등 안전성 확보조치"
    
    5만명 이상 처리 시 보호위원회의 정기 조사 대상.
    위반 시 매출액 3% 이내 과징금.
    """
    unique_id_cats = {'rrn', 'frn', 'passport', 'driver_license'}
    unique_cols = [d for d in ctx.pii_detections
                   if d.get('category') in unique_id_cats]
    
    if not unique_cols:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.PIPA,
            severity=CheckSeverity.CRITICAL, title="", description="", legal_basis="",
            status=CheckStatus.SKIP,
            detail="고유식별정보 컬럼 미탐지",
        )
    
    if not ctx.is_prod_to_lower:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.PIPA,
            severity=CheckSeverity.CRITICAL, title="", description="", legal_basis="",
            status=CheckStatus.SKIP,
            detail="비운영 환경으로의 이관 아님",
        )
    
    unmasked = [c['column_name'] for c in unique_cols
                if c['column_name'] not in ctx.masked_pii_columns]
    
    if unmasked:
        # 어떤 카테고리의 ID인지 detail 에 명시 (감사관용)
        unmasked_with_cat = [
            f"{c['column_name']}({c.get('category', '?')})"
            for c in unique_cols
            if c['column_name'] not in ctx.masked_pii_columns
        ]
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.PIPA,
            severity=CheckSeverity.CRITICAL, title="", description="", legal_basis="",
            status=CheckStatus.FAIL,
            detail=f"고유식별정보 평문 이관: {unmasked_with_cat}",
            evidence={
                "unmasked_columns": unmasked_with_cat,
                "estimated_subjects": ctx.total_rows_estimate,
                "subject_to_periodic_audit": ctx.total_rows_estimate >= 50000,
            },
        )
    
    return ChecklistItem(
        rule_id="", framework=ComplianceFramework.PIPA,
        severity=CheckSeverity.CRITICAL, title="", description="", legal_basis="",
        status=CheckStatus.PASS,
        detail=f"고유식별정보 {len(unique_cols)}개 컬럼 보호조치 완료",
    )


def _check_pipa_sensitive_info(ctx: ComplianceContext) -> ChecklistItem:
    """
    개인정보보호법 §23 (민감정보의 처리 제한)
    
    민감정보 = 건강정보, 유전정보, 범죄경력, 사상·신념, 노조 가입, 정치적 견해, 
              성생활, 인종·민족 등
    """
    sensitive_cats = {'health', 'genetic', 'criminal'}
    sensitive_cols = [d for d in ctx.pii_detections
                      if d.get('category') in sensitive_cats]
    
    if not sensitive_cols:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.PIPA,
            severity=CheckSeverity.CRITICAL, title="", description="", legal_basis="",
            status=CheckStatus.SKIP,
            detail="민감정보 컬럼 미탐지",
        )
    
    unmasked = [c['column_name'] for c in sensitive_cols
                if c['column_name'] not in ctx.masked_pii_columns]
    
    if ctx.is_prod_to_lower and unmasked:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.PIPA,
            severity=CheckSeverity.CRITICAL, title="", description="", legal_basis="",
            status=CheckStatus.FAIL,
            detail=f"민감정보 평문 이관: {unmasked}",
            evidence={"unmasked_sensitive_columns": unmasked},
        )
    
    return ChecklistItem(
        rule_id="", framework=ComplianceFramework.PIPA,
        severity=CheckSeverity.CRITICAL, title="", description="", legal_basis="",
        status=CheckStatus.PASS,
        detail=f"민감정보 {len(sensitive_cols)}개 컬럼 보호조치 완료",
    )


def _check_pipa_pseudonym_safeguard(ctx: ComplianceContext) -> ChecklistItem:
    """
    개인정보보호법 §28의4 (가명정보 안전조치 의무)
    시행령 §29의5 (가명정보에 대한 안전성 확보조치)
    
    "원래의 상태로 복원하기 위한 추가 정보를 별도로 분리하여 보관·관리"
    
    DataBridge 관점:
      PSEUDONYM/FAKE 사용 시 매핑테이블이 별도 보관되는지.
      이건 운영 정책이라 자동 검증 어려움 → WARN 으로 안내.
    """
    pseudonym_cols = [d for d in ctx.privacy_decisions
                      if d.get('strategy') in ('pseudonym', 'fake')]
    
    if not pseudonym_cols:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.PIPA,
            severity=CheckSeverity.MEDIUM, title="", description="", legal_basis="",
            status=CheckStatus.SKIP,
            detail="가명처리(PSEUDONYM/FAKE) 미사용",
        )
    
    return ChecklistItem(
        rule_id="", framework=ComplianceFramework.PIPA,
        severity=CheckSeverity.MEDIUM, title="", description="", legal_basis="",
        status=CheckStatus.WARN,
        detail=(
            f"가명처리 {len(pseudonym_cols)}개 컬럼 적용 — "
            "매핑테이블 별도 보관 + 접근권한 분리 정책 점검 필요 (§28의4)"
        ),
        evidence={"pseudonymized_columns": [c['column_name'] for c in pseudonym_cols]},
        recommendation=(
            "가명정보 처리 가이드라인에 따라 추가정보를 별도 DB/볼트에 보관, "
            "이관 작업자와 매핑 관리자 권한 분리 운영"
        ),
    )


def _check_pipa_purpose_limit(ctx: ComplianceContext) -> ChecklistItem:
    """
    개인정보보호법 §3 (개인정보 보호 원칙) + §15 (수집·이용)
    
    "수집 목적의 범위에서만 처리"
    
    DataBridge 관점:
      운영 → 분석/통계 환경으로 이관 = 목적 변경 가능성.
      §28의2 가명정보 처리 특례 (통계작성, 과학적 연구, 공익적 기록보존) 적용 여부.
    """
    is_analytics = ctx.tgt_environment.lower() in ('analytics', 'bi', '분석', 'statistics')
    
    if not is_analytics:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.PIPA,
            severity=CheckSeverity.MEDIUM, title="", description="", legal_basis="",
            status=CheckStatus.SKIP,
            detail="분석/통계 환경 아님",
        )
    
    if ctx.has_critical_pii and not ctx.privacy_decisions:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.PIPA,
            severity=CheckSeverity.HIGH, title="", description="", legal_basis="",
            status=CheckStatus.FAIL,
            detail=(
                "분석 환경에 PII 평문 이관 — 목적 외 처리 위험. "
                "통계작성/과학적 연구 목적이면 가명처리 필수 (§28의2)"
            ),
        )
    
    return ChecklistItem(
        rule_id="", framework=ComplianceFramework.PIPA,
        severity=CheckSeverity.MEDIUM, title="", description="", legal_basis="",
        status=CheckStatus.PASS,
        detail="분석 환경 가명처리 적합",
    )


# ════════════════════════════════════════════════════════════════════════════
# 안전성 확보조치 기준 (시행령 §30) 룰
# ════════════════════════════════════════════════════════════════════════════

def _check_safeguard_access_log(ctx: ComplianceContext) -> ChecklistItem:
    """
    안전성 확보조치 기준 §8 (접속기록의 보관·점검)
    
    "개인정보처리시스템에 접속한 자의 접속일시, 처리내역 등 접속기록을 1년 이상 보관"
    "월 1회 이상 점검"
    """
    if ctx.audit_log_enabled is True:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.PIPA,
            severity=CheckSeverity.HIGH, title="", description="", legal_basis="",
            status=CheckStatus.PASS,
            detail="이관 작업 접속기록 활성화 (1년 이상 보관 권고)",
        )
    elif ctx.audit_log_enabled is False:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.PIPA,
            severity=CheckSeverity.HIGH, title="", description="", legal_basis="",
            status=CheckStatus.FAIL,
            detail="이관 작업 접속기록 미활성화 — 안전조치 기준 §8 위반",
        )
    return ChecklistItem(
        rule_id="", framework=ComplianceFramework.PIPA,
        severity=CheckSeverity.HIGH, title="", description="", legal_basis="",
        status=CheckStatus.WARN,
        detail="접속기록 활성화 여부 미확인",
    )


def _check_safeguard_min_privilege(ctx: ComplianceContext) -> ChecklistItem:
    """
    안전성 확보조치 기준 §5 (접근 권한의 관리)
    
    "업무수행에 필요한 최소한의 범위로 차등 부여"
    
    DataBridge 관점:
      이관 작업자가 너무 강한 권한 (예: SA / sysadmin) 사용하는지.
      privileged_user=True 면 WARN.
    """
    if ctx.privileged_user is True:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.PIPA,
            severity=CheckSeverity.MEDIUM, title="", description="", legal_basis="",
            status=CheckStatus.WARN,
            detail=(
                "이관 작업자가 시스템 관리자 권한 사용 — 최소 권한 원칙 위배 가능"
            ),
            recommendation="이관 전용 계정 생성, SELECT/INSERT 등 필요한 권한만 부여",
        )
    elif ctx.privileged_user is False:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.PIPA,
            severity=CheckSeverity.MEDIUM, title="", description="", legal_basis="",
            status=CheckStatus.PASS,
            detail="이관 전용 계정 사용 (최소 권한)",
        )
    return ChecklistItem(
        rule_id="", framework=ComplianceFramework.PIPA,
        severity=CheckSeverity.MEDIUM, title="", description="", legal_basis="",
        status=CheckStatus.WARN,
        detail="작업자 권한 수준 미확인 — DB 계정의 최소 권한 점검 권고",
    )


# ════════════════════════════════════════════════════════════════════════════
# ISMS-P 인증기준 (선택 룰)
# ════════════════════════════════════════════════════════════════════════════

def _check_ismsp_data_separation(ctx: ComplianceContext) -> ChecklistItem:
    """
    ISMS-P 2.6.2 (정보시스템 접근통제)
    
    개발/운영 시스템의 접근권한 분리, 운영 데이터 무단 사용 금지.
    """
    if not ctx.is_prod_to_lower:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.ISMS_P,
            severity=CheckSeverity.HIGH, title="", description="", legal_basis="",
            status=CheckStatus.SKIP,
            detail="비운영 환경 이관 아님",
        )
    
    if ctx.privacy_skipped or not ctx.privacy_decisions:
        if ctx.has_critical_pii:
            return ChecklistItem(
                rule_id="", framework=ComplianceFramework.ISMS_P,
                severity=CheckSeverity.HIGH, title="", description="", legal_basis="",
                status=CheckStatus.FAIL,
                detail="운영→개발 PII 평문 이관 — 접근통제 미흡 (ISMS-P 2.6.2)",
            )
    
    return ChecklistItem(
        rule_id="", framework=ComplianceFramework.ISMS_P,
        severity=CheckSeverity.HIGH, title="", description="", legal_basis="",
        status=CheckStatus.PASS,
        detail="운영-개발 데이터 격리 적절",
    )


def _check_ismsp_change_management(ctx: ComplianceContext) -> ChecklistItem:
    """
    ISMS-P 2.9.4 (변경관리)
    
    데이터 이관도 시스템 변경. 사전 검토/승인 절차 권고.
    """
    return ChecklistItem(
        rule_id="", framework=ComplianceFramework.ISMS_P,
        severity=CheckSeverity.LOW, title="", description="", legal_basis="",
        status=CheckStatus.WARN,
        detail=(
            "이관은 시스템 변경에 해당 — 변경관리 절차(사전 승인, 영향평가, "
            "롤백 계획) 적용 권고 (ISMS-P 2.9.4)"
        ),
        recommendation=(
            "이관 작업 전 변경관리 티켓 발행 + 결재 + 이관 후 결과 보고"
        ),
    )


# ════════════════════════════════════════════════════════════════════════════
# 룰 정의
# ════════════════════════════════════════════════════════════════════════════

KR_PIPA_RULES: List[ComplianceRule] = [
    # ─── 개인정보보호법 (PIPA) ────────────────────────────────────
    ComplianceRule(
        rule_id="pipa-24-2-rrn-encrypt",
        framework=ComplianceFramework.PIPA,
        severity=CheckSeverity.CRITICAL,
        title="주민등록번호 암호화 의무",
        description=(
            "주민등록번호는 분실·도난·유출 등을 방지하기 위해 암호화 보관 필수. "
            "이관 시 평문 전송/저장 금지. 위반 시 매출액 3% 이내 과징금."
        ),
        legal_basis="개인정보보호법 §24의2",
        checker=_check_pipa_rrn_encryption,
        applies_when=lambda c: any(d.get('category') == 'rrn' for d in c.pii_detections),
        recommendation=(
            "PII Privacy 탭에서 RRN 컬럼에 PARTIAL 또는 HASH 마스킹 적용. "
            "이관 시 TLS 1.2 이상 사용."
        ),
    ),
    
    ComplianceRule(
        rule_id="pipa-24-unique-id",
        framework=ComplianceFramework.PIPA,
        severity=CheckSeverity.CRITICAL,
        title="고유식별정보 안전성 확보조치",
        description=(
            "고유식별정보(주민/여권/운전면허/외국인등록번호) 처리 시 "
            "암호화 등 안전성 확보조치 의무. 5만명 이상 처리 시 정기 조사 대상."
        ),
        legal_basis="개인정보보호법 §24 + 시행령 §21",
        checker=_check_pipa_unique_id_protection,
        recommendation="고유식별정보 컬럼에 마스킹 또는 암호화 적용",
    ),
    
    ComplianceRule(
        rule_id="pipa-23-sensitive",
        framework=ComplianceFramework.PIPA,
        severity=CheckSeverity.CRITICAL,
        title="민감정보 처리 제한",
        description=(
            "건강·유전·범죄경력 등 민감정보는 별도 동의 + 안전성 확보조치 필수."
        ),
        legal_basis="개인정보보호법 §23",
        checker=_check_pipa_sensitive_info,
        recommendation="민감정보 컬럼은 비운영 환경 이관 시 마스킹 또는 제외",
    ),
    
    ComplianceRule(
        rule_id="pipa-28-4-pseudo-safeguard",
        framework=ComplianceFramework.PIPA,
        severity=CheckSeverity.MEDIUM,
        title="가명정보 안전조치 의무",
        description=(
            "가명처리 시 추가정보(매핑테이블)는 별도 분리 보관, 접근권한 분리 운영. "
            "위반 시 3천만원 이하 과태료."
        ),
        legal_basis="개인정보보호법 §28의4 + 시행령 §29의5",
        checker=_check_pipa_pseudonym_safeguard,
    ),
    
    ComplianceRule(
        rule_id="pipa-15-purpose",
        framework=ComplianceFramework.PIPA,
        severity=CheckSeverity.MEDIUM,
        title="목적 범위 내 처리",
        description=(
            "분석/통계 목적 이관 시 §28의2 (가명정보 처리 특례) 적용 여부 확인. "
            "통계작성·과학적 연구·공익적 기록보존이 아니면 가명처리 의무."
        ),
        legal_basis="개인정보보호법 §3, §15, §28의2",
        checker=_check_pipa_purpose_limit,
        applies_when=lambda c: c.tgt_environment.lower() in ('analytics', 'bi', '분석', 'statistics'),
        recommendation="분석 환경 이관은 ANALYTICS preset (HASH + GENERALIZE) 사용",
    ),
    
    # ─── 안전성 확보조치 기준 ───────────────────────────────────
    ComplianceRule(
        rule_id="safeguard-8-access-log",
        framework=ComplianceFramework.PIPA,
        severity=CheckSeverity.HIGH,
        title="접속기록 보관 및 점검",
        description=(
            "개인정보처리시스템 접속기록을 1년 이상 보관하고 월 1회 이상 점검. "
            "위·변조 및 도난·분실 방지 조치 필수."
        ),
        legal_basis="개인정보의 안전성 확보조치 기준 §8",
        checker=_check_safeguard_access_log,
        recommendation="DataBridge Job 로그 1년 이상 보관 + 월간 검토 절차 수립",
    ),
    
    ComplianceRule(
        rule_id="safeguard-5-min-priv",
        framework=ComplianceFramework.PIPA,
        severity=CheckSeverity.MEDIUM,
        title="최소 권한 원칙",
        description=(
            "개인정보처리시스템 접근권한은 업무수행에 필요한 최소한의 범위로 차등 부여."
        ),
        legal_basis="개인정보의 안전성 확보조치 기준 §5",
        checker=_check_safeguard_min_privilege,
    ),
    
    # ─── ISMS-P 인증기준 ────────────────────────────────────────
    ComplianceRule(
        rule_id="ismsp-2-6-2",
        framework=ComplianceFramework.ISMS_P,
        severity=CheckSeverity.HIGH,
        title="개발-운영 시스템 접근통제",
        description=(
            "개발자가 운영 데이터에 접근할 때는 별도 통제 및 가명/마스킹 처리 후 사용."
        ),
        legal_basis="ISMS-P 인증기준 2.6.2 (정보시스템 접근통제)",
        checker=_check_ismsp_data_separation,
        applies_when=lambda c: c.is_prod_to_lower,
        recommendation="운영→개발 이관 시 PII 마스킹 정책 적용",
    ),
    
    ComplianceRule(
        rule_id="ismsp-2-9-4",
        framework=ComplianceFramework.ISMS_P,
        severity=CheckSeverity.LOW,
        title="변경관리 절차",
        description=(
            "데이터 이관은 시스템 변경 사항. 사전 검토·승인·영향평가·롤백계획 수립."
        ),
        legal_basis="ISMS-P 인증기준 2.9.4 (변경관리)",
        checker=_check_ismsp_change_management,
    ),
]


def register_kr_pipa_rules(registry) -> None:
    """기본 레지스트리에 한국 일반 룰 등록"""
    registry.add_rules(KR_PIPA_RULES)
    _log.info(f"[Compliance] 한국 PIPA/ISMS-P 룰 {len(KR_PIPA_RULES)}개 등록 완료")
