"""
compliance_rules_kr_finance.py — Phase F-2b (2026-04-25)

한국 금융권 컴플라이언스 룰셋:
  1. 전자금융감독규정 (EFA) — 금융위원회 고시
  2. 전자금융감독규정 시행세칙 (EFA 시행세칙)
  3. 신용정보의 이용 및 보호에 관한 법률 (CIA)
  4. 신용정보업감독규정

법조문 출처 (2024~2025년 기준):
  - 국가법령정보센터 (www.law.go.kr)
  - 금융감독원 전자금융감독규정 해설서
  - 신용정보업감독규정 일부개정 (금융위원회 고시 제2024-19호)

대상:
  - 캐피탈사, 카드사, 은행, 보험, 증권 등 금융회사
  - 마이데이터 사업자
  - 결합전문기관/데이터전문기관

본 룰셋의 한계:
  - 해석 일부는 일반 가이드 수준. 개별 사안 유권해석은 행정관청 문의 필요.
  - 법령 개정으로 조문 번호 바뀔 수 있으므로 주기적 갱신 필요.
"""

from __future__ import annotations
import logging
from typing import List

from app.core.compliance_rules import (
    ComplianceFramework, CheckSeverity, CheckStatus,
    ChecklistItem, ComplianceContext, ComplianceRule,
    make_simple_check,
)

_log = logging.getLogger("databridge.compliance.kr_finance")


# ════════════════════════════════════════════════════════════════════════════
# 전자금융감독규정 (EFA) 룰
# ════════════════════════════════════════════════════════════════════════════

def _check_efa_data_encryption(ctx: ComplianceContext) -> ChecklistItem:
    """
    전자금융감독규정 §15 (해킹 등 방지대책) — 중요정보 암호화
    
    전송 구간 (in-transit) + 저장 구간 (at-rest) 모두 검사.
    이관 도중 평문 전송 = 금감원 감사 시 즉시 지적 사항.
    """
    issues = []
    
    if ctx.use_tls is False:
        issues.append("이관 시 TLS 미적용 — 평문 전송 위험")
    elif ctx.use_tls is None:
        issues.append("TLS 사용 여부 미확인 (DB 연결 옵션 점검 필요)")
    
    if ctx.src_tls_version and ctx.src_tls_version < "1.2":
        issues.append(f"소스 DB TLS 버전 취약: {ctx.src_tls_version} (1.2 이상 권고)")
    if ctx.tgt_tls_version and ctx.tgt_tls_version < "1.2":
        issues.append(f"타겟 DB TLS 버전 취약: {ctx.tgt_tls_version} (1.2 이상 권고)")
    
    if issues:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.EFA,
            severity=CheckSeverity.CRITICAL, title="", description="", legal_basis="",
            status=CheckStatus.FAIL,
            detail="; ".join(issues),
            evidence={"use_tls": ctx.use_tls,
                     "src_tls": ctx.src_tls_version,
                     "tgt_tls": ctx.tgt_tls_version},
        )
    
    return ChecklistItem(
        rule_id="", framework=ComplianceFramework.EFA,
        severity=CheckSeverity.CRITICAL, title="", description="", legal_basis="",
        status=CheckStatus.PASS,
        detail="이관 시 TLS 암호화 적용 확인",
    )


def _check_efa_remote_dev_isolation(ctx: ComplianceContext) -> ChecklistItem:
    """
    전자금융감독규정 §15-1 (시스템 분리) 및 시행세칙
    개발/테스트 시스템은 운영시스템과 분리. 
    원격관리 시 전용회선/VPN 사용.
    
    DataBridge 관점:
      운영 → 개발 이관 시 연결이 VPN/SSH 터널로 이루어지는지 확인.
    """
    if not ctx.is_prod_to_lower:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.EFA,
            severity=CheckSeverity.HIGH, title="", description="", legal_basis="",
            status=CheckStatus.SKIP,
            detail="운영→비운영 이관이 아니므로 비적용",
        )
    
    if ctx.use_vpn_or_ssh_tunnel is False:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.EFA,
            severity=CheckSeverity.HIGH, title="", description="", legal_basis="",
            status=CheckStatus.FAIL,
            detail="운영 → 개발 이관 시 VPN/SSH 터널 미사용",
            evidence={"vpn_used": False},
        )
    elif ctx.use_vpn_or_ssh_tunnel is True:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.EFA,
            severity=CheckSeverity.HIGH, title="", description="", legal_basis="",
            status=CheckStatus.PASS,
            detail="VPN/SSH 터널 사용 확인",
        )
    
    return ChecklistItem(
        rule_id="", framework=ComplianceFramework.EFA,
        severity=CheckSeverity.HIGH, title="", description="", legal_basis="",
        status=CheckStatus.WARN,
        detail="VPN/SSH 사용 여부 미확인 — 네트워크 경로 점검 권고",
    )


def _check_efa_audit_log(ctx: ComplianceContext) -> ChecklistItem:
    """
    전자금융감독규정 시행세칙 — 접근기록(접속·접근·로그인) 보관
    이관 작업 자체도 접속/처리 기록으로 보관 대상.
    """
    if ctx.audit_log_enabled is True:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.EFA,
            severity=CheckSeverity.MEDIUM, title="", description="", legal_basis="",
            status=CheckStatus.PASS,
            detail="이관 작업 감사 로그 활성화",
        )
    elif ctx.audit_log_enabled is False:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.EFA,
            severity=CheckSeverity.MEDIUM, title="", description="", legal_basis="",
            status=CheckStatus.FAIL,
            detail="이관 작업 감사 로그 비활성화",
        )
    return ChecklistItem(
        rule_id="", framework=ComplianceFramework.EFA,
        severity=CheckSeverity.MEDIUM, title="", description="", legal_basis="",
        status=CheckStatus.WARN,
        detail="감사 로그 활성화 여부 미확인",
    )


def _check_efa_backup_recovery(ctx: ComplianceContext) -> ChecklistItem:
    """
    전자금융감독규정 §15 (긴급사태 대비 백업 및 복구 절차)
    이관 전 소스 DB 백업, 이관 실패 시 롤백 절차 점검.
    """
    if ctx.backup_enabled is True:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.EFA,
            severity=CheckSeverity.HIGH, title="", description="", legal_basis="",
            status=CheckStatus.PASS,
            detail="이관 전 백업 활성화 확인",
        )
    elif ctx.backup_enabled is False:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.EFA,
            severity=CheckSeverity.HIGH, title="", description="", legal_basis="",
            status=CheckStatus.FAIL,
            detail="이관 전 백업 미설정 — 실패 시 복구 어려움",
        )
    return ChecklistItem(
        rule_id="", framework=ComplianceFramework.EFA,
        severity=CheckSeverity.HIGH, title="", description="", legal_basis="",
        status=CheckStatus.WARN,
        detail="백업 설정 미확인 — 이관 전 백업 권고",
    )


# ════════════════════════════════════════════════════════════════════════════
# 신용정보법 / 신용정보업감독규정 룰
# ════════════════════════════════════════════════════════════════════════════

def _check_cia_account_protection(ctx: ComplianceContext) -> ChecklistItem:
    """
    신용정보법 §32 / 신용정보업감독규정 — 계좌번호 등 신용정보 보호
    개인신용정보 (계좌번호 등) 의 비운영 환경 이관 시 보호 조치 필수.
    """
    account_cols = [d for d in ctx.pii_detections
                    if d.get('category') == 'bank_account']
    
    if not account_cols:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.CIA,
            severity=CheckSeverity.HIGH, title="", description="", legal_basis="",
            status=CheckStatus.SKIP,
            detail="계좌번호 컬럼 미탐지",
        )
    
    if not ctx.is_prod_to_lower:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.CIA,
            severity=CheckSeverity.HIGH, title="", description="", legal_basis="",
            status=CheckStatus.SKIP,
            detail="운영→비운영 이관이 아니므로 비적용",
        )
    
    unmasked = [c['column_name'] for c in account_cols
                if c['column_name'] not in ctx.masked_pii_columns]
    
    if unmasked:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.CIA,
            severity=CheckSeverity.HIGH, title="", description="", legal_basis="",
            status=CheckStatus.FAIL,
            detail=f"개발/테스트 환경에 계좌번호 평문 이관: {unmasked}",
            evidence={"unmasked_account_columns": unmasked},
        )
    
    return ChecklistItem(
        rule_id="", framework=ComplianceFramework.CIA,
        severity=CheckSeverity.HIGH, title="", description="", legal_basis="",
        status=CheckStatus.PASS,
        detail=f"계좌번호 {len(account_cols)}개 컬럼 모두 마스킹 적용",
    )


def _check_cia_pseudonymization(ctx: ComplianceContext) -> ChecklistItem:
    """
    신용정보법 §40의2 / 개인정보보호법 §28의2 — 가명처리
    분석/통계 목적 이관 시 가명처리 준수.
    
    분석 환경 (analytics) 이관인데 PARTIAL 마스킹만 했다면 부족.
    HASH/PSEUDONYM 등 식별 불가능한 처리 권고.
    """
    is_analytics = ctx.tgt_environment.lower() in ('analytics', 'bi', '분석')
    
    if not is_analytics:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.CIA,
            severity=CheckSeverity.MEDIUM, title="", description="", legal_basis="",
            status=CheckStatus.SKIP,
            detail="분석/통계 환경 이관이 아니므로 비적용",
        )
    
    # 가명처리 강도 확인
    weak_strategies = {'partial', 'keep'}
    pii_cols = [d for d in ctx.privacy_decisions
                if d.get('strategy') and d.get('strategy') != 'keep']
    weak_count = sum(1 for d in ctx.privacy_decisions
                    if d.get('strategy') in weak_strategies)
    
    if not pii_cols:
        # 마스킹 자체를 안 함
        if ctx.pii_detections:
            return ChecklistItem(
                rule_id="", framework=ComplianceFramework.CIA,
                severity=CheckSeverity.HIGH, title="", description="", legal_basis="",
                status=CheckStatus.FAIL,
                detail="분석 환경에 PII 가명처리 없이 이관",
            )
    
    if weak_count > 0:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.CIA,
            severity=CheckSeverity.MEDIUM, title="", description="", legal_basis="",
            status=CheckStatus.WARN,
            detail=f"분석 환경에 약한 가명처리({weak_count}개 컬럼) — HASH/PSEUDONYM 권고",
        )
    
    return ChecklistItem(
        rule_id="", framework=ComplianceFramework.CIA,
        severity=CheckSeverity.MEDIUM, title="", description="", legal_basis="",
        status=CheckStatus.PASS,
        detail="분석 환경 가명처리 적합",
    )


def _check_cia_separated_access(ctx: ComplianceContext) -> ChecklistItem:
    """
    개인정보보호법 시행령 §29의5 — 가명정보와 추가정보의 접근권한 분리
    
    이관 작업자는 가명정보만 다루고, 추가정보(매핑테이블)는 별도 인력이 관리.
    DataBridge 의 PSEUDONYM/FAKE 전략 사용 시 매핑테이블이 별도 보관되는지.
    
    (이건 운영 정책 영역. DataBridge 가 자동 검증하기 어려움 — INFO 로 안내)
    """
    has_pseudonym = any(
        d.get('strategy') in ('pseudonym', 'fake', 'hash')
        for d in ctx.privacy_decisions
    )
    
    if not has_pseudonym:
        return ChecklistItem(
            rule_id="", framework=ComplianceFramework.CIA,
            severity=CheckSeverity.LOW, title="", description="", legal_basis="",
            status=CheckStatus.SKIP,
            detail="가명처리 미적용 — 비적용",
        )
    
    return ChecklistItem(
        rule_id="", framework=ComplianceFramework.CIA,
        severity=CheckSeverity.LOW, title="", description="", legal_basis="",
        status=CheckStatus.WARN,  # INFO 대신 WARN 으로 노출
        detail="가명처리 사용 — 매핑테이블 별도 보관 + 접근권한 분리 운영 정책 점검 필요",
        recommendation="가명정보 운영 가이드라인에 따라 추가정보 별도 관리",
    )


# ════════════════════════════════════════════════════════════════════════════
# 룰 정의 (메타데이터 + 함수 결합)
# ════════════════════════════════════════════════════════════════════════════

KR_FINANCE_RULES: List[ComplianceRule] = [
    # ─── 전자금융감독규정 ─────────────────────────────────────────
    ComplianceRule(
        rule_id="efa-15-encrypt-transit",
        framework=ComplianceFramework.EFA,
        severity=CheckSeverity.CRITICAL,
        title="이관 데이터 암호화 (in-transit)",
        description=(
            "DB 간 데이터 이관 시 TLS 1.2 이상으로 암호화. "
            "평문 전송은 해킹 등 침해 위험에 직접 노출."
        ),
        legal_basis="전자금융감독규정 §15 (해킹 등 방지대책)",
        checker=_check_efa_data_encryption,
        recommendation="DB 연결 문자열에 TLS/SSL 옵션 활성화 (예: encrypt=true)",
    ),
    
    ComplianceRule(
        rule_id="efa-15-isolation-vpn",
        framework=ComplianceFramework.EFA,
        severity=CheckSeverity.HIGH,
        title="운영-개발 시스템 격리",
        description=(
            "운영시스템과 개발/테스트 시스템 간 네트워크 격리. "
            "원격 접속 시 VPN 또는 전용회선 사용 의무."
        ),
        legal_basis="전자금융감독규정 §15 (시스템 분리) / 시행세칙",
        checker=_check_efa_remote_dev_isolation,
        applies_when=lambda c: c.is_prod_to_lower,
        recommendation="운영 → 개발 이관은 반드시 VPN/SSH 터널을 통해 수행",
    ),
    
    ComplianceRule(
        rule_id="efa-audit-access-log",
        framework=ComplianceFramework.EFA,
        severity=CheckSeverity.MEDIUM,
        title="이관 작업 감사 로그",
        description=(
            "이관 작업의 시점, 작업자, 처리 내역을 접근기록으로 보존. "
            "전금감 시행세칙에 따라 1년 이상 보관."
        ),
        legal_basis="전자금융감독규정 시행세칙 (접근기록)",
        checker=_check_efa_audit_log,
        recommendation="DataBridge Job 로그 + DB 감사 로그 1년 이상 보관",
    ),
    
    ComplianceRule(
        rule_id="efa-15-backup-recovery",
        framework=ComplianceFramework.EFA,
        severity=CheckSeverity.HIGH,
        title="이관 전 백업 및 복구 절차",
        description=(
            "이관 실패 또는 장애 발생 시 복구를 위한 사전 백업. "
            "전금감 §15 긴급사태 대비 의무."
        ),
        legal_basis="전자금융감독규정 §15 (백업 및 복구)",
        checker=_check_efa_backup_recovery,
        applies_when=lambda c: c.is_prod_to_lower,  # 운영→개발 시 특히 중요
        recommendation="이관 시작 전 소스 DB snapshot 또는 물리 백업 수행",
    ),
    
    # ─── 신용정보법 / 신용정보업감독규정 ─────────────────────────────
    ComplianceRule(
        rule_id="cia-32-account",
        framework=ComplianceFramework.CIA,
        severity=CheckSeverity.HIGH,
        title="개인신용정보 (계좌번호) 보호",
        description=(
            "운영 → 개발/테스트 환경 이관 시 계좌번호 등 "
            "개인신용정보를 마스킹하지 않으면 신용정보법 위반 위험."
        ),
        legal_basis="신용정보의 이용 및 보호에 관한 법률 §32 / 신용정보업감독규정",
        checker=_check_cia_account_protection,
        recommendation="PII Privacy 탭에서 계좌번호에 PARTIAL 또는 HASH 마스킹 적용",
    ),
    
    ComplianceRule(
        rule_id="cia-40-pseudo",
        framework=ComplianceFramework.CIA,
        severity=CheckSeverity.MEDIUM,
        title="가명처리 (분석/통계 목적)",
        description=(
            "통계작성·과학적 연구·공익적 기록보존 목적의 가명처리는 "
            "신용정보법에 따라 가명정보로 분류되며, 식별 불가능한 처리 필요."
        ),
        legal_basis="신용정보법 §40의2 / 개인정보보호법 §28의2",
        checker=_check_cia_pseudonymization,
        applies_when=lambda c: c.tgt_environment.lower() in ('analytics', 'bi', '분석'),
        recommendation="분석 환경에는 ANALYTICS preset (HASH + GENERALIZE) 사용",
    ),
    
    ComplianceRule(
        rule_id="cia-29-5-separation",
        framework=ComplianceFramework.CIA,
        severity=CheckSeverity.LOW,
        title="가명정보 추가정보 분리 보관",
        description=(
            "가명정보와 원래 상태로 복원 가능한 추가정보(매핑테이블)는 "
            "분리 보관, 접근권한 분리 운영."
        ),
        legal_basis="개인정보보호법 시행령 §29의5",
        checker=_check_cia_separated_access,
        recommendation=(
            "PSEUDONYM/FAKE 사용 시 매핑테이블을 별도 DB/볼트에 보관, "
            "접근권한은 이관 작업자 ≠ 매핑 관리자로 분리"
        ),
    ),
]


def register_kr_finance_rules(registry) -> None:
    """기본 레지스트리에 한국 금융권 룰 등록"""
    registry.add_rules(KR_FINANCE_RULES)
    _log.info(f"[Compliance] 한국 금융권 룰 {len(KR_FINANCE_RULES)}개 등록 완료")
