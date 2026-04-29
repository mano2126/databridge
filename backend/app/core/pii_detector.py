"""
pii_detector.py — Phase F-1a (2026-04-25)

한국형 PII (개인식별정보) 자동 탐지 엔진.

목적:
  운영 DB → 개발/스테이징 DB 이관 시
  개인정보보호법 위반 위험 자동 차단.
  
대상:
  - 한국 PII 우선 (주민번호/전화/계좌/카드 등)
  - 글로벌 PII 보조 (이메일/IP/신용카드)
  - 컬럼명 + 데이터 내용 이중 검증

전략:
  1. Layer 1: 컬럼명 패턴 매칭 (rrn, phone, email 등)
  2. Layer 2: 데이터 샘플링 (상위 100건 검사)
  3. Layer 3: 정규식 + 체크섬 검증 (오탐 최소화)
  4. Layer 4: 종합 신뢰도 점수 산출

출력:
  - 컬럼별 PII 분류
  - 탐지 신뢰도 (0~100%)
  - 마스킹 권장 정책
  - 컴플라이언스 위반 위험도
"""

from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from enum import Enum

_log = logging.getLogger("databridge.pii")


# ════════════════════════════════════════════════════════════════════════════
# PII 타입 정의
# ════════════════════════════════════════════════════════════════════════════

class PIICategory(str, Enum):
    """PII 카테고리 (개인정보보호법 분류 기준)"""
    
    # 고유식별정보 (개인정보보호법 24조 — 가장 엄격)
    RRN = "rrn"                          # 주민등록번호
    FRN = "frn"                          # 외국인등록번호
    DRIVER_LICENSE = "driver_license"     # 운전면허번호
    PASSPORT = "passport"                 # 여권번호
    
    # 민감정보 (개인정보보호법 23조)
    HEALTH = "health"                     # 건강 관련
    GENETIC = "genetic"                   # 유전정보
    CRIMINAL = "criminal"                 # 범죄경력
    
    # 일반 개인정보
    NAME_KOR = "name_kor"                # 한글 이름
    PHONE = "phone"                       # 휴대폰
    PHONE_LAND = "phone_land"            # 일반전화
    EMAIL = "email"                       # 이메일
    ADDRESS = "address"                   # 주소
    DOB = "dob"                          # 생년월일
    
    # 금융정보
    BANK_ACCOUNT = "bank_account"         # 계좌번호
    CARD_NUMBER = "card_number"           # 신용/체크카드
    CARD_CVV = "card_cvv"                # CVV
    
    # 기업정보 (사업자번호 등)
    BIZ_NUMBER = "biz_number"            # 사업자등록번호
    CORP_NUMBER = "corp_number"          # 법인등록번호
    
    # 기술 식별자
    IP_ADDRESS = "ip_address"            # IP 주소
    MAC_ADDRESS = "mac_address"          # MAC 주소
    
    # 알 수 없는 PII (사람이 검토 필요)
    UNKNOWN = "unknown"


class PIISensitivity(str, Enum):
    """PII 민감도 (마스킹 강도 결정용)"""
    CRITICAL = "critical"  # 고유식별정보, 민감정보 (반드시 마스킹)
    HIGH = "high"          # 금융정보, 건강정보
    MEDIUM = "medium"      # 일반 개인정보 (이메일, 주소 등)
    LOW = "low"            # 기술 식별자


# 카테고리 → 민감도 매핑
SENSITIVITY_MAP: Dict[PIICategory, PIISensitivity] = {
    PIICategory.RRN: PIISensitivity.CRITICAL,
    PIICategory.FRN: PIISensitivity.CRITICAL,
    PIICategory.DRIVER_LICENSE: PIISensitivity.CRITICAL,
    PIICategory.PASSPORT: PIISensitivity.CRITICAL,
    PIICategory.HEALTH: PIISensitivity.CRITICAL,
    PIICategory.GENETIC: PIISensitivity.CRITICAL,
    PIICategory.CRIMINAL: PIISensitivity.CRITICAL,
    
    PIICategory.CARD_NUMBER: PIISensitivity.HIGH,
    PIICategory.CARD_CVV: PIISensitivity.HIGH,
    PIICategory.BANK_ACCOUNT: PIISensitivity.HIGH,
    
    PIICategory.NAME_KOR: PIISensitivity.MEDIUM,
    PIICategory.PHONE: PIISensitivity.MEDIUM,
    PIICategory.PHONE_LAND: PIISensitivity.MEDIUM,
    PIICategory.EMAIL: PIISensitivity.MEDIUM,
    PIICategory.ADDRESS: PIISensitivity.MEDIUM,
    PIICategory.DOB: PIISensitivity.MEDIUM,
    PIICategory.BIZ_NUMBER: PIISensitivity.MEDIUM,
    PIICategory.CORP_NUMBER: PIISensitivity.MEDIUM,
    
    PIICategory.IP_ADDRESS: PIISensitivity.LOW,
    PIICategory.MAC_ADDRESS: PIISensitivity.LOW,
    PIICategory.UNKNOWN: PIISensitivity.MEDIUM,
}


@dataclass
class PIIDetection:
    """단일 PII 탐지 결과"""
    column_name: str                     # 컬럼명
    table_name: str                      # 테이블명
    category: PIICategory                # PII 카테고리
    sensitivity: PIISensitivity          # 민감도
    confidence: float                    # 신뢰도 0.0 ~ 1.0
    
    # 탐지 근거
    column_match: bool = False           # 컬럼명 매칭 여부
    pattern_match_rate: float = 0.0      # 데이터 패턴 매칭률 (0~1)
    checksum_pass_rate: float = 0.0      # 체크섬 검증 통과율 (0~1)
    sample_count: int = 0                # 검사한 샘플 수
    matched_count: int = 0               # 매칭된 샘플 수
    
    # 권고
    recommended_masking: str = ""        # 권장 마스킹 방식
    legal_reference: str = ""            # 관련 법조문
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d['category'] = self.category.value
        d['sensitivity'] = self.sensitivity.value
        return d


# ════════════════════════════════════════════════════════════════════════════
# 컬럼명 패턴 (Layer 1)
# ════════════════════════════════════════════════════════════════════════════

# 컬럼명 → PII 카테고리 매핑 (한국어/영어 모두)
COLUMN_NAME_PATTERNS: Dict[PIICategory, List[str]] = {
    PIICategory.RRN: [
        r'\brrn\b', r'\bjumin\b', r'\bssn\b',
        r'_rrn\b', r'_ssn\b', r'_jumin\b',
        r'주민', r'주민등록', r'주민번호',
        r'identity_no', r'national_id', r'citizen_id',
    ],
    PIICategory.FRN: [
        r'\bfrn\b', r'_frn\b',
        r'외국인', r'foreign.*id', r'alien.*id',
    ],
    PIICategory.DRIVER_LICENSE: [
        r'driver.*license', r'license.*no', r'운전면허',
    ],
    PIICategory.PASSPORT: [
        r'passport', r'여권',
    ],
    PIICategory.NAME_KOR: [
        r'\bname\b', r'_name\b', r'name_kor', r'user_name', r'customer_name',
        r'contractor_name', r'guarantor_name', r'holder_name',
        r'성명', r'이름', r'고객명', r'사용자명',
    ],
    PIICategory.PHONE: [
        r'\bphone\b', r'\bmobile\b', r'\bcell\b', r'\bhp\b',
        r'phone_mobile', r'phone_no', r'tel_mobile', r'_phone\b',
        r'휴대폰', r'핸드폰', r'전화', r'연락처',
    ],
    PIICategory.PHONE_LAND: [
        r'phone_land', r'phone_office', r'tel_office', r'tel_home',
        r'사무실전화', r'집전화',
    ],
    PIICategory.EMAIL: [
        r'\bemail\b', r'\bmail\b', r'e_mail', r'_email\b',
        r'이메일', r'메일',
    ],
    PIICategory.ADDRESS: [
        r'\baddr\b', r'\baddress\b', r'addr1', r'addr2', r'addr_detail',
        r'home_addr', r'_addr\b', r'_address\b',
        r'주소', r'거주지', r'상세주소',
    ],
    PIICategory.DOB: [
        r'\bdob\b', r'birth', r'birthday', r'birth_date', r'birth_dt',
        r'_birth\b', r'생일', r'생년월일',
    ],
    PIICategory.BANK_ACCOUNT: [
        r'\baccount\b', r'\bacct\b', r'account_no', r'acct_no', r'bank_account',
        r'auto_debit_account', r'_account\b',
        r'계좌', r'계좌번호',
    ],
    PIICategory.CARD_NUMBER: [
        r'\bcard\b', r'card_no', r'card_number', r'\bccn\b',
        r'카드번호',
    ],
    PIICategory.CARD_CVV: [
        r'\bcvv\b', r'\bcvc\b', r'card_cvc', r'card_cvv', r'security_code',
    ],
    PIICategory.BIZ_NUMBER: [
        r'biz_no', r'business_no', r'biz_reg_no', r'business_reg',
        r'\bbrn\b', r'tax_id', r'business_id',
        r'사업자', r'사업자등록', r'사업자번호',
    ],
    PIICategory.CORP_NUMBER: [
        r'corp_no', r'corp_reg_no', r'corporation_no', r'corp_id',
        r'법인', r'법인등록', r'법인번호',
    ],
    PIICategory.IP_ADDRESS: [
        r'\bip\b', r'ip_addr', r'ip_address', r'client_ip', r'_ip\b',
    ],
    PIICategory.MAC_ADDRESS: [
        r'\bmac\b', r'mac_addr', r'mac_address', r'client_mac', r'device_mac', r'_mac\b',
    ],
}


def detect_by_column_name(column_name: str) -> Optional[PIICategory]:
    """
    컬럼명만으로 PII 카테고리 추정.
    Layer 1 — 가장 빠른 1차 필터.
    """
    if not column_name:
        return None
    
    col_lower = column_name.lower()
    
    # 우선순위 순회 (CRITICAL 먼저)
    for category, patterns in COLUMN_NAME_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, col_lower, re.IGNORECASE):
                return category
    
    return None


# ════════════════════════════════════════════════════════════════════════════
# 데이터 패턴 검사 (Layer 2 + 3)
# ════════════════════════════════════════════════════════════════════════════

# 정규식 패턴 + 체크섬 검증 함수
class PIIPatternChecker:
    """PII 카테고리별 패턴 검사기"""
    
    @staticmethod
    def is_rrn(value: str) -> bool:
        """주민등록번호: YYMMDD-XXXXXXX (체크섬 포함)"""
        if not value or not isinstance(value, str):
            return False
        v = value.replace('-', '').strip()
        if not re.fullmatch(r'\d{13}', v):
            return False
        # 체크섬 검증 (마지막 자리)
        weights = [2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5]
        try:
            total = sum(int(v[i]) * weights[i] for i in range(12))
            check = (11 - total % 11) % 10
            return check == int(v[12])
        except (ValueError, IndexError):
            return False
    
    @staticmethod
    def is_frn(value: str) -> bool:
        """외국인등록번호: 7번째 자리가 5,6,7,8"""
        if not value or not isinstance(value, str):
            return False
        v = value.replace('-', '').strip()
        if not re.fullmatch(r'\d{13}', v):
            return False
        if v[6] not in '5678':
            return False
        # 체크섬 (FRN 전용)
        weights = [2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5]
        try:
            total = sum(int(v[i]) * weights[i] for i in range(12))
            check = (11 - total % 11) % 10
            check = (check + 2) % 10  # 외국인 보정
            return check == int(v[12])
        except (ValueError, IndexError):
            return False
    
    @staticmethod
    def is_phone_kr(value: str) -> bool:
        """한국 휴대폰: 010/011/016/017/018/019"""
        if not value or not isinstance(value, str):
            return False
        v = re.sub(r'[\s\-\.()]', '', value).strip()
        return bool(re.fullmatch(r'01[016789]\d{7,8}', v))
    
    @staticmethod
    def is_phone_land(value: str) -> bool:
        """일반전화: 02 / 0XX 지역번호"""
        if not value or not isinstance(value, str):
            return False
        v = re.sub(r'[\s\-\.()]', '', value).strip()
        # 02 (서울) 또는 03X~06X (지방)
        return bool(re.fullmatch(r'(02|0[3-6]\d)\d{7,8}', v))
    
    @staticmethod
    def is_email(value: str) -> bool:
        """이메일 (RFC 5322 간소화)"""
        if not value or not isinstance(value, str):
            return False
        return bool(re.fullmatch(
            r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
            value.strip()
        ))
    
    @staticmethod
    def is_card_number(value: str) -> bool:
        """신용카드 (Luhn 알고리즘)"""
        if not value or not isinstance(value, str):
            return False
        v = re.sub(r'[\s\-]', '', value).strip()
        if not re.fullmatch(r'\d{13,19}', v):
            return False
        # Luhn 검증
        try:
            digits = [int(d) for d in v]
            checksum = 0
            for i, d in enumerate(reversed(digits)):
                if i % 2 == 1:
                    d *= 2
                    if d > 9:
                        d -= 9
                checksum += d
            return checksum % 10 == 0
        except ValueError:
            return False
    
    @staticmethod
    def is_bank_account(value: str) -> bool:
        """계좌번호: 한국 은행 계좌 패턴 (단순 휴리스틱)"""
        if not value or not isinstance(value, str):
            return False
        v = re.sub(r'[\s\-]', '', value).strip()
        # 10~16자리 숫자 (국민/신한/우리/하나/농협/기업 등)
        return bool(re.fullmatch(r'\d{10,16}', v))
    
    @staticmethod
    def is_biz_number(value: str) -> bool:
        """사업자등록번호: XXX-XX-XXXXX (체크섬 포함)"""
        if not value or not isinstance(value, str):
            return False
        v = value.replace('-', '').replace(' ', '').strip()
        if not re.fullmatch(r'\d{10}', v):
            return False
        # 표준 체크섬 알고리즘 (국세청)
        weights = [1, 3, 7, 1, 3, 7, 1, 3, 5]
        try:
            total = 0
            for i in range(9):
                total += int(v[i]) * weights[i]
            # 9번째 자리 × 5 의 십의 자리도 더함
            total += (int(v[8]) * 5) // 10
            check = (10 - (total % 10)) % 10
            return check == int(v[9])
        except (ValueError, IndexError):
            return False
    
    @staticmethod
    def is_passport(value: str) -> bool:
        """여권번호: 알파벳 1~2자 + 숫자 7자리"""
        if not value or not isinstance(value, str):
            return False
        return bool(re.fullmatch(r'[A-Z]{1,2}\d{7,8}', value.strip().upper()))
    
    @staticmethod
    def is_ip_address(value: str) -> bool:
        """IPv4 또는 IPv6"""
        if not value or not isinstance(value, str):
            return False
        v = value.strip()
        # IPv4
        ipv4_match = re.fullmatch(r'(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})', v)
        if ipv4_match:
            return all(0 <= int(g) <= 255 for g in ipv4_match.groups())
        # IPv6 (간소화)
        return bool(re.fullmatch(
            r'([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}',
            v
        ))
    
    @staticmethod
    def is_name_kor(value: str) -> bool:
        """한글 이름: 한글 2~5자"""
        if not value or not isinstance(value, str):
            return False
        v = value.strip()
        return bool(re.fullmatch(r'[가-힣]{2,5}', v))
    
    @staticmethod
    def is_dob(value: str) -> bool:
        """생년월일: YYYY-MM-DD / YYYYMMDD / YY-MM-DD"""
        if not value:
            return False
        v = str(value).strip()
        patterns = [
            r'^(19|20)\d{2}-\d{2}-\d{2}$',
            r'^(19|20)\d{6}$',
            r'^\d{2}-\d{2}-\d{2}$',
            r'^\d{4}-\d{2}-\d{2}$',
        ]
        return any(re.fullmatch(p, v) for p in patterns)


# 카테고리 → 검사 함수 매핑
# 주의: 이 매핑은 하위 호환성 위해 유지하되, 실제 검사는 PRIORITY_ORDER 사용
PATTERN_CHECKERS = {
    PIICategory.RRN: PIIPatternChecker.is_rrn,
    PIICategory.FRN: PIIPatternChecker.is_frn,
    PIICategory.PHONE: PIIPatternChecker.is_phone_kr,
    PIICategory.PHONE_LAND: PIIPatternChecker.is_phone_land,
    PIICategory.EMAIL: PIIPatternChecker.is_email,
    PIICategory.CARD_NUMBER: PIIPatternChecker.is_card_number,
    PIICategory.BANK_ACCOUNT: PIIPatternChecker.is_bank_account,
    PIICategory.BIZ_NUMBER: PIIPatternChecker.is_biz_number,
    PIICategory.PASSPORT: PIIPatternChecker.is_passport,
    PIICategory.IP_ADDRESS: PIIPatternChecker.is_ip_address,
    PIICategory.NAME_KOR: PIIPatternChecker.is_name_kor,
    PIICategory.DOB: PIIPatternChecker.is_dob,
}

# ★ 검사 우선순위 (좁은 패턴 → 넓은 패턴 순서)
# 이유: 850123-1234567 (RRN) 같은 게 bank_account (10-16자리) 에 먼저 매칭되면 안 됨
# CRITICAL 등급 먼저, 그리고 형식이 엄격한 것 먼저, 가장 일반적인 것 마지막
PRIORITY_ORDER = [
    # 1. 가장 엄격한 형식 (체크섬 있음)
    PIICategory.RRN,           # 13자리 + 체크섬
    PIICategory.FRN,           # 13자리 + 7번째 자리 5-8 + 체크섬
    PIICategory.BIZ_NUMBER,    # 10자리 + 체크섬
    
    # 2. 명확한 구분 가능
    PIICategory.EMAIL,         # @ 포함
    PIICategory.IP_ADDRESS,    # x.x.x.x
    PIICategory.PASSPORT,      # 알파벳+숫자
    PIICategory.DOB,           # 날짜 형식
    
    # 3. 한국 특수
    PIICategory.PHONE,         # 010~019
    PIICategory.PHONE_LAND,    # 02 / 0XX
    
    # 4. 길이 + Luhn 체크섬
    PIICategory.CARD_NUMBER,   # 13-19자리 + Luhn
    
    # 5. 한글 (이름은 단순 패턴)
    PIICategory.NAME_KOR,      # 한글 2-5자
    
    # 6. 가장 광범위 (다른 게 안 맞을 때만)
    PIICategory.BANK_ACCOUNT,  # 10-16자리 숫자 (RRN/카드 외 fallback)
]


def detect_by_data_pattern(
    samples: List[Any],
    suspected_category: Optional[PIICategory] = None,
) -> Optional[Dict[PIICategory, float]]:
    """
    데이터 샘플로 PII 카테고리 추정.
    Layer 2 + 3 — 컬럼명 매칭 후 데이터 검증.
    
    Args:
        samples: 컬럼의 데이터 샘플 (보통 100건)
        suspected_category: 컬럼명으로 추정된 카테고리 (있으면 우선 검사)
    
    Returns:
        {카테고리: 매칭률} 딕셔너리 (매칭률 30% 이상만)
    """
    if not samples:
        return None
    
    # NULL 제외
    valid_samples = [s for s in samples if s is not None and str(s).strip()]
    if not valid_samples:
        return None
    
    results: Dict[PIICategory, float] = {}
    
    # suspected_category 가 있으면 우선 검사 (그게 첫 번째)
    # 그 외에는 PRIORITY_ORDER 순서로 (좁은 패턴 → 넓은 패턴)
    if suspected_category and suspected_category in PATTERN_CHECKERS:
        categories_to_check = [suspected_category] + [
            c for c in PRIORITY_ORDER if c != suspected_category
        ]
    else:
        categories_to_check = list(PRIORITY_ORDER)
    
    # 한 카테고리가 강하게 매칭 (>= 80%) 되면 그 이상 광범위한 카테고리는 skip
    # 예: RRN 매칭 강하면 BANK_ACCOUNT 검사 skip (둘 다 매칭되면 좁은 게 맞음)
    strong_match_found = False
    
    for category in categories_to_check:
        checker = PATTERN_CHECKERS.get(category)
        if not checker:
            continue
        
        # 이미 좁은 패턴이 강하게 매칭됐고, 현재 카테고리가 광범위한 fallback (BANK_ACCOUNT) 이면 skip
        if strong_match_found and category == PIICategory.BANK_ACCOUNT:
            continue
        
        matched = 0
        for sample in valid_samples:
            try:
                if checker(str(sample)):
                    matched += 1
            except Exception:
                pass
        
        match_rate = matched / len(valid_samples)
        if match_rate >= 0.3:  # 30% 이상 매칭만 보고
            results[category] = match_rate
            
            # 좁은 패턴이 강하게 매칭됐으면 표시
            if match_rate >= 0.8 and category in (
                PIICategory.RRN, PIICategory.FRN, PIICategory.BIZ_NUMBER,
                PIICategory.CARD_NUMBER, PIICategory.PHONE, PIICategory.EMAIL,
            ):
                strong_match_found = True
    
    return results if results else None


# ════════════════════════════════════════════════════════════════════════════
# 종합 분석 (Layer 4)
# ════════════════════════════════════════════════════════════════════════════

def analyze_column(
    table_name: str,
    column_name: str,
    samples: Optional[List[Any]] = None,
) -> Optional[PIIDetection]:
    """
    컬럼명 + 데이터 샘플로 PII 종합 분석.
    
    Args:
        table_name: 테이블명
        column_name: 컬럼명
        samples: 데이터 샘플 (None 이면 컬럼명만으로 추정)
    
    Returns:
        PIIDetection 또는 None (PII 아님)
    """
    # Layer 1: 컬럼명 검사
    column_category = detect_by_column_name(column_name)
    
    # Layer 2+3: 데이터 패턴 검사
    data_results = None
    if samples:
        data_results = detect_by_data_pattern(samples, column_category)
    
    # 결과 결합
    if not column_category and not data_results:
        return None  # PII 아님
    
    # 최종 카테고리 결정
    final_category: PIICategory
    confidence: float
    column_match = column_category is not None
    pattern_match_rate = 0.0
    matched_count = 0
    sample_count = len(samples) if samples else 0
    
    if column_category and data_results:
        # 컬럼명 매칭 + 데이터 매칭 모두 있는 경우
        if column_category in data_results:
            # 일치 — 신뢰도 매우 높음
            final_category = column_category
            pattern_match_rate = data_results[column_category]
            matched_count = int(pattern_match_rate * sample_count)
            confidence = min(0.5 + pattern_match_rate * 0.5, 0.99)
        else:
            # 불일치 — 데이터 매칭 우선 (실제 데이터가 더 신뢰 가능)
            best_data = max(data_results.items(), key=lambda x: x[1])
            final_category = best_data[0]
            pattern_match_rate = best_data[1]
            matched_count = int(pattern_match_rate * sample_count)
            confidence = pattern_match_rate * 0.7
    elif column_category:
        # 컬럼명만 매칭 (샘플 없음)
        final_category = column_category
        confidence = 0.5  # 데이터 검증 안 됨
    elif data_results:
        # 데이터만 매칭 (컬럼명에 힌트 없음)
        best_data = max(data_results.items(), key=lambda x: x[1])
        final_category = best_data[0]
        pattern_match_rate = best_data[1]
        matched_count = int(pattern_match_rate * sample_count)
        confidence = pattern_match_rate * 0.8
    else:
        return None
    
    sensitivity = SENSITIVITY_MAP.get(final_category, PIISensitivity.MEDIUM)
    
    detection = PIIDetection(
        column_name=column_name,
        table_name=table_name,
        category=final_category,
        sensitivity=sensitivity,
        confidence=confidence,
        column_match=column_match,
        pattern_match_rate=pattern_match_rate,
        sample_count=sample_count,
        matched_count=matched_count,
        recommended_masking=_recommend_masking(final_category, sensitivity),
        legal_reference=_legal_reference(final_category),
    )
    
    return detection


def _recommend_masking(category: PIICategory, sensitivity: PIISensitivity) -> str:
    """PII 카테고리별 권장 마스킹 방식"""
    recommendations = {
        PIICategory.RRN: "앞 6자리 + 뒤 1자리만 (생년월일 + 성별) → 'YYMMDD-1******'",
        PIICategory.FRN: "앞 6자리 + 뒤 1자리만 → 'YYMMDD-5******'",
        PIICategory.PASSPORT: "전체 해시 또는 첫 글자 + 마지막 2자리",
        PIICategory.DRIVER_LICENSE: "지역코드 + 마지막 2자리만",
        PIICategory.NAME_KOR: "성만 유지 + 이름 별표 → '홍**'",
        PIICategory.PHONE: "중간 4자리 마스킹 → '010-****-1234'",
        PIICategory.PHONE_LAND: "중간 마스킹 → '02-****-5678'",
        PIICategory.EMAIL: "@ 앞 일부 + 도메인 → 'us**@example.com'",
        PIICategory.ADDRESS: "시/도/구까지만 → '서울 강남구'",
        PIICategory.DOB: "월/일 제거 → '1985-**-**'",
        PIICategory.BANK_ACCOUNT: "마지막 4자리만 → '*******1234'",
        PIICategory.CARD_NUMBER: "PAN 마스킹 → '1234-**** -**** -5678'",
        PIICategory.CARD_CVV: "완전 제거 (저장 금지)",
        PIICategory.BIZ_NUMBER: "유지 (공개 정보)",
        PIICategory.IP_ADDRESS: "마지막 옥텟 마스킹 → '192.168.1.*'",
    }
    return recommendations.get(category, "Hash (SHA256 또는 가명화)")


def _legal_reference(category: PIICategory) -> str:
    """PII 카테고리별 관련 법조문"""
    refs = {
        PIICategory.RRN: "개인정보보호법 §24의2 (주민등록번호 처리 제한)",
        PIICategory.FRN: "개인정보보호법 §24 (고유식별정보)",
        PIICategory.DRIVER_LICENSE: "개인정보보호법 §24 (고유식별정보)",
        PIICategory.PASSPORT: "개인정보보호법 §24 (고유식별정보)",
        PIICategory.HEALTH: "개인정보보호법 §23 (민감정보)",
        PIICategory.GENETIC: "개인정보보호법 §23 (민감정보)",
        PIICategory.CRIMINAL: "개인정보보호법 §23 (민감정보)",
        PIICategory.CARD_NUMBER: "여신전문금융업법 §54의5 / PCI-DSS",
        PIICategory.CARD_CVV: "여신전문금융업법 §54의5 / PCI-DSS (저장 금지)",
        PIICategory.BANK_ACCOUNT: "신용정보법 §32 / 전자금융거래법",
        PIICategory.NAME_KOR: "개인정보보호법 §15, §17",
        PIICategory.PHONE: "개인정보보호법 §15, §17 / 정보통신망법",
        PIICategory.EMAIL: "개인정보보호법 §15, §17",
        PIICategory.ADDRESS: "개인정보보호법 §15, §17",
        PIICategory.DOB: "개인정보보호법 §15, §17",
    }
    return refs.get(category, "개인정보보호법 §15 (개인정보 처리 원칙)")


# ════════════════════════════════════════════════════════════════════════════
# 일괄 스캔 API
# ════════════════════════════════════════════════════════════════════════════

def scan_table_schema(
    table_name: str,
    columns: List[Dict[str, Any]],
    sample_data: Optional[Dict[str, List[Any]]] = None,
) -> List[PIIDetection]:
    """
    테이블 전체 스캔.
    
    Args:
        table_name: 테이블명
        columns: [{"name": "...", "type": "..."}, ...] 컬럼 정의
        sample_data: {"column_name": [샘플1, 샘플2, ...], ...}
    
    Returns:
        PII 탐지 결과 리스트 (PII 아닌 컬럼은 제외)
    """
    detections = []
    sample_data = sample_data or {}
    
    for col in columns:
        col_name = col.get("name") or col.get("column_name", "")
        if not col_name:
            continue
        
        samples = sample_data.get(col_name)
        detection = analyze_column(table_name, col_name, samples)
        
        if detection:
            detections.append(detection)
    
    return detections


def summarize_detections(detections: List[PIIDetection]) -> Dict[str, Any]:
    """탐지 결과 요약 통계"""
    if not detections:
        return {
            "total_pii_columns": 0,
            "by_sensitivity": {},
            "by_category": {},
            "compliance_risk": "LOW",
        }
    
    by_sensitivity = {}
    by_category = {}
    
    for d in detections:
        s = d.sensitivity.value
        c = d.category.value
        by_sensitivity[s] = by_sensitivity.get(s, 0) + 1
        by_category[c] = by_category.get(c, 0) + 1
    
    # 위험도 판정
    has_critical = by_sensitivity.get("critical", 0) > 0
    has_high = by_sensitivity.get("high", 0) > 0
    
    if has_critical:
        risk = "CRITICAL"
    elif has_high:
        risk = "HIGH"
    elif detections:
        risk = "MEDIUM"
    else:
        risk = "LOW"
    
    return {
        "total_pii_columns": len(detections),
        "by_sensitivity": by_sensitivity,
        "by_category": by_category,
        "compliance_risk": risk,
        "tables_affected": len(set(d.table_name for d in detections)),
    }
