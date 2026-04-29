"""
pii_masker.py — Phase F-1b (2026-04-25)

PII 마스킹 정책 엔진.

목적:
  pii_detector.py 가 탐지한 PII 컬럼을
  정책에 따라 자동 마스킹 / 가명화 / 익명화.

전략:
  - 마스킹 (Masking): 일부 가림. 'YYMMDD-1******' 같은 형식
  - 가명화 (Pseudonymization): 일관된 가짜 값으로 치환 (조인 가능 유지)
  - 익명화 (Anonymization): 완전 무작위 또는 제거 (복구 불가)
  - 해시 (Hashing): SHA256 등 단방향
  
출력:
  - 마스킹 SQL UPDATE 문 자동 생성
  - 또는 INSERT INTO target SELECT 의 SELECT 절 변환
  - 미리보기 (Before/After 샘플)
"""

from __future__ import annotations
import re
import hashlib
import logging
import secrets
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from enum import Enum

# pii_detector 와 호환
try:
    from app.core.pii_detector import PIICategory, PIISensitivity, PIIDetection
except ImportError:
    # 단독 테스트 시 fallback
    from .pii_detector import PIICategory, PIISensitivity, PIIDetection

_log = logging.getLogger("databridge.pii_masker")


# ════════════════════════════════════════════════════════════════════════════
# 마스킹 전략
# ════════════════════════════════════════════════════════════════════════════

class MaskingStrategy(str, Enum):
    """마스킹 전략 — 사용 시나리오에 따라 선택"""
    
    # 1. 부분 마스킹 (가장 일반적, 형식 유지)
    PARTIAL = "partial"           # '850123-1******'
    
    # 2. 완전 마스킹 (모든 자리 별표)
    FULL = "full"                 # '*************'
    
    # 3. 해시 (단방향, 검색 가능)
    HASH = "hash"                 # 'a3f2c1b8...'
    
    # 4. 가명화 (일관성 있는 가짜 값, 조인 유지)
    PSEUDONYM = "pseudonym"       # '홍길동' → '김 갑돌'
    
    # 5. 무작위 (가짜이지만 형식 유효)
    FAKE = "fake"                 # '850123-1234567' → '901225-1456789'
    
    # 6. 일반화 (광범위 카테고리)
    GENERALIZE = "generalize"     # '서울 강남구 테헤란로 123' → '서울'
    
    # 7. NULL 처리
    NULLIFY = "nullify"           # NULL
    
    # 8. 그대로 (운영→운영 시)
    KEEP = "keep"


class MaskingPreset(str, Enum):
    """미리 정의된 정책 (사용자 선택용)"""
    
    DEV_ENVIRONMENT = "dev_environment"      # 개발 환경: 모든 PII 마스킹
    QA_ENVIRONMENT = "qa_environment"        # QA: Critical 만 마스킹
    ANALYTICS = "analytics"                  # 분석용: 익명화 + 일반화
    PRODUCTION_CLONE = "production_clone"    # 운영 복제: 그대로
    GDPR_COMPLIANT = "gdpr_compliant"        # GDPR: 가명화 + 일부 마스킹
    PCI_DSS = "pci_dss"                     # PCI-DSS: 카드정보 완전 제거
    CUSTOM = "custom"                        # 사용자 정의


# ════════════════════════════════════════════════════════════════════════════
# 카테고리별 기본 마스킹 함수
# ════════════════════════════════════════════════════════════════════════════

class PIIMasker:
    """PII 카테고리별 마스킹 함수 모음"""
    
    @staticmethod
    def mask_rrn(value: str, strategy: MaskingStrategy = MaskingStrategy.PARTIAL) -> str:
        """주민등록번호 마스킹"""
        if not value:
            return value
        v = str(value).replace('-', '').strip()
        if len(v) != 13:
            return PIIMasker._fallback_mask(value, strategy)
        
        if strategy == MaskingStrategy.PARTIAL:
            # 'YYMMDD-1******' (앞 6자리 + 성별만)
            return f"{v[:6]}-{v[6]}******"
        elif strategy == MaskingStrategy.FULL:
            return "*************"
        elif strategy == MaskingStrategy.HASH:
            return PIIMasker._hash(v)
        elif strategy == MaskingStrategy.NULLIFY:
            return None  # type: ignore
        elif strategy == MaskingStrategy.FAKE:
            return PIIMasker._fake_rrn(v)
        return v
    
    @staticmethod
    def mask_phone(value: str, strategy: MaskingStrategy = MaskingStrategy.PARTIAL) -> str:
        """휴대폰 마스킹: 010-****-1234"""
        if not value:
            return value
        v = re.sub(r'[\s\-\.()]', '', str(value)).strip()
        
        if strategy == MaskingStrategy.PARTIAL:
            if len(v) == 11:
                return f"{v[:3]}-****-{v[7:]}"
            elif len(v) == 10:
                return f"{v[:3]}-***-{v[6:]}"
            return PIIMasker._fallback_mask(value, strategy)
        elif strategy == MaskingStrategy.FULL:
            return "***-****-****"
        elif strategy == MaskingStrategy.HASH:
            return PIIMasker._hash(v)
        elif strategy == MaskingStrategy.NULLIFY:
            return None  # type: ignore
        return v
    
    @staticmethod
    def mask_email(value: str, strategy: MaskingStrategy = MaskingStrategy.PARTIAL) -> str:
        """이메일 마스킹: us**@example.com"""
        if not value or '@' not in str(value):
            return value
        v = str(value).strip()
        
        if strategy == MaskingStrategy.PARTIAL:
            local, domain = v.split('@', 1)
            if len(local) <= 2:
                masked_local = '*' * len(local)
            else:
                masked_local = local[:2] + '*' * (len(local) - 2)
            return f"{masked_local}@{domain}"
        elif strategy == MaskingStrategy.FULL:
            return "***@***"
        elif strategy == MaskingStrategy.HASH:
            return PIIMasker._hash(v)
        elif strategy == MaskingStrategy.NULLIFY:
            return None  # type: ignore
        return v
    
    @staticmethod
    def mask_name(value: str, strategy: MaskingStrategy = MaskingStrategy.PARTIAL) -> str:
        """이름 마스킹: 홍길동 → 홍**"""
        if not value:
            return value
        v = str(value).strip()
        
        if strategy == MaskingStrategy.PARTIAL:
            if len(v) <= 1:
                return '*'
            elif len(v) == 2:
                return v[0] + '*'
            else:
                return v[0] + '*' * (len(v) - 1)
        elif strategy == MaskingStrategy.FULL:
            return '*' * len(v)
        elif strategy == MaskingStrategy.HASH:
            return PIIMasker._hash(v)[:8]  # 짧게
        elif strategy == MaskingStrategy.NULLIFY:
            return None  # type: ignore
        elif strategy == MaskingStrategy.PSEUDONYM:
            return PIIMasker._fake_name(v)
        return v
    
    @staticmethod
    def mask_card(value: str, strategy: MaskingStrategy = MaskingStrategy.PARTIAL) -> str:
        """신용카드: 1234-****-****-5678"""
        if not value:
            return value
        v = re.sub(r'[\s\-]', '', str(value)).strip()
        
        if strategy == MaskingStrategy.PARTIAL:
            if len(v) >= 13:
                return f"{v[:4]}-****-****-{v[-4:]}"
            return PIIMasker._fallback_mask(value, strategy)
        elif strategy == MaskingStrategy.FULL:
            return "****-****-****-****"
        elif strategy == MaskingStrategy.HASH:
            return PIIMasker._hash(v)
        elif strategy == MaskingStrategy.NULLIFY:
            return None  # type: ignore
        return v
    
    @staticmethod
    def mask_account(value: str, strategy: MaskingStrategy = MaskingStrategy.PARTIAL) -> str:
        """계좌번호: 마지막 4자리만"""
        if not value:
            return value
        v = re.sub(r'[\s\-]', '', str(value)).strip()
        
        if strategy == MaskingStrategy.PARTIAL:
            if len(v) >= 4:
                return '*' * (len(v) - 4) + v[-4:]
            return PIIMasker._fallback_mask(value, strategy)
        elif strategy == MaskingStrategy.FULL:
            return '*' * len(v)
        elif strategy == MaskingStrategy.HASH:
            return PIIMasker._hash(v)
        elif strategy == MaskingStrategy.NULLIFY:
            return None  # type: ignore
        return v
    
    @staticmethod
    def mask_address(value: str, strategy: MaskingStrategy = MaskingStrategy.PARTIAL) -> str:
        """주소 마스킹"""
        if not value:
            return value
        v = str(value).strip()
        
        if strategy == MaskingStrategy.PARTIAL or strategy == MaskingStrategy.GENERALIZE:
            # 시/도 + 시/구 까지만
            parts = v.split()
            if len(parts) >= 2:
                return f"{parts[0]} {parts[1]}"
            return parts[0] if parts else v
        elif strategy == MaskingStrategy.FULL:
            return "***"
        elif strategy == MaskingStrategy.HASH:
            return PIIMasker._hash(v)[:12]
        elif strategy == MaskingStrategy.NULLIFY:
            return None  # type: ignore
        return v
    
    @staticmethod
    def mask_dob(value, strategy: MaskingStrategy = MaskingStrategy.PARTIAL) -> str:
        """생년월일: 1985-**-**"""
        if not value:
            return value
        v = str(value).strip()
        
        if strategy == MaskingStrategy.PARTIAL:
            # YYYY-MM-DD → YYYY-**-**
            m = re.match(r'^(\d{4})[-/](\d{2})[-/](\d{2})', v)
            if m:
                return f"{m.group(1)}-**-**"
            # YYYYMMDD → YYYY****
            m = re.match(r'^(\d{4})\d{4}', v)
            if m:
                return f"{m.group(1)}****"
            return PIIMasker._fallback_mask(value, strategy)
        elif strategy == MaskingStrategy.GENERALIZE:
            # 연령대로 일반화
            year_m = re.match(r'^(\d{4})', v)
            if year_m:
                year = int(year_m.group(1))
                from datetime import datetime
                age = datetime.now().year - year
                decade = (age // 10) * 10
                return f"{decade}대"
            return v
        elif strategy == MaskingStrategy.HASH:
            return PIIMasker._hash(v)
        elif strategy == MaskingStrategy.NULLIFY:
            return None  # type: ignore
        return v
    
    @staticmethod
    def mask_passport(value: str, strategy: MaskingStrategy = MaskingStrategy.PARTIAL) -> str:
        """여권번호: K**** ****"""
        if not value:
            return value
        v = str(value).strip().upper()
        
        if strategy == MaskingStrategy.PARTIAL:
            if len(v) >= 3:
                return f"{v[0]}{'*' * (len(v) - 3)}{v[-2:]}"
            return PIIMasker._fallback_mask(value, strategy)
        elif strategy == MaskingStrategy.FULL:
            return '*' * len(v)
        elif strategy == MaskingStrategy.HASH:
            return PIIMasker._hash(v)
        elif strategy == MaskingStrategy.NULLIFY:
            return None  # type: ignore
        return v
    
    @staticmethod
    def mask_ip(value: str, strategy: MaskingStrategy = MaskingStrategy.PARTIAL) -> str:
        """IP: 192.168.1.*"""
        if not value:
            return value
        v = str(value).strip()
        
        if strategy == MaskingStrategy.PARTIAL:
            parts = v.split('.')
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.{parts[2]}.*"
            return PIIMasker._fallback_mask(value, strategy)
        elif strategy == MaskingStrategy.GENERALIZE:
            # /16 만 유지
            parts = v.split('.')
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.0.0/16"
            return v
        elif strategy == MaskingStrategy.HASH:
            return PIIMasker._hash(v)
        elif strategy == MaskingStrategy.NULLIFY:
            return None  # type: ignore
        return v
    
    # ── 유틸리티 ──────────────────────────────────────
    
    @staticmethod
    def _hash(value: str, salt: str = "databridge_pii_salt") -> str:
        """SHA256 해시 (salted)"""
        h = hashlib.sha256((salt + value).encode()).hexdigest()
        return h[:16]  # 짧게 16자
    
    @staticmethod
    def _fallback_mask(value: str, strategy: MaskingStrategy) -> str:
        """형식이 안 맞을 때 fallback"""
        v = str(value)
        if strategy == MaskingStrategy.HASH:
            return PIIMasker._hash(v)
        if strategy == MaskingStrategy.NULLIFY:
            return None  # type: ignore
        if len(v) <= 2:
            return '*' * len(v)
        return v[0] + '*' * (len(v) - 2) + v[-1]
    
    @staticmethod
    def _fake_rrn(original: str) -> str:
        """가짜 RRN 생성 (체크섬 맞춤, 형식 유효)"""
        # 일관성 위해 hash 기반 deterministic
        h = hashlib.md5(original.encode()).hexdigest()
        # 1900~2010 사이 랜덤 생년
        year = 1900 + int(h[:2], 16) % 100
        month = 1 + int(h[2:4], 16) % 12
        day = 1 + int(h[4:6], 16) % 28
        gender = '1' if int(h[6], 16) % 2 == 0 else '2'
        middle = h[8:13].translate(str.maketrans('abcdef', '012345'))[:5]
        
        prefix = f"{year % 100:02d}{month:02d}{day:02d}{gender}{middle}"
        # 체크섬
        weights = [2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5]
        total = sum(int(prefix[i]) * weights[i] for i in range(12))
        check = (11 - total % 11) % 10
        return f"{prefix[:6]}-{prefix[6:]}{check}"
    
    @staticmethod
    def _fake_name(original: str) -> str:
        """
        가짜 한글 이름 (deterministic)
        같은 입력 → 항상 같은 출력 (조인/조회 가능)
        """
        if not original:
            return original
        surnames = ['김', '이', '박', '최', '정', '강', '조', '윤', '장', '임',
                    '한', '오', '서', '신', '권', '황', '안', '송', '류', '전']
        first1 = ['길', '영', '철', '미', '준', '현', '서', '지', '민', '수',
                  '재', '동', '예', '주', '하', '윤', '도', '시', '소', '유']
        first2 = ['동', '수', '호', '진', '아', '영', '윤', '연', '석', '환',
                  '우', '훈', '빈', '겸', '은', '율', '담', '결', '범', '강']
        
        h = hashlib.md5(original.encode('utf-8')).digest()
        s = surnames[h[0] % len(surnames)]
        f1 = first1[h[1] % len(first1)]
        f2 = first2[h[2] % len(first2)]
        return s + f1 + f2
    
    # ════════════════════════════════════════════════════════════════════
    # v89.7: Deterministic Fake Generators (개발 환경 정합성 보장)
    #
    # 핵심 원칙: 같은 원본 → 항상 같은 가짜 값
    # 이유: 
    #   1. 조인 보존 (customer.name == payment.holder)
    #   2. 데이터 정합성 테스트 가능
    #   3. 개발자 디버깅 용이
    # 구현: hashlib.md5(원본) → seed → 풀에서 deterministic 선택
    # ════════════════════════════════════════════════════════════════════
    
    @staticmethod
    def _hash_seed(original: str, salt: str = "") -> bytes:
        """원본 문자열에서 deterministic seed 생성"""
        return hashlib.md5(f"{salt}::{original}".encode('utf-8')).digest()
    
    @staticmethod
    def _fake_rrn(original: str) -> str:
        """
        가짜 주민번호 (deterministic) - 형식 유지 + 체크섬 포함
        '850123-1234567' → '781205-1456789' (같은 입력 → 같은 출력)
        """
        if not original:
            return original
        v = str(original).replace('-', '').strip()
        if len(v) != 13:
            return original
        
        h = PIIMasker._hash_seed(original, "rrn")
        # 생년월일 (00-99 / 01-12 / 01-28)
        yy = h[0] % 100
        mm = (h[1] % 12) + 1
        dd = (h[2] % 28) + 1
        # 성별 (1, 2, 3, 4 중)
        gender = (h[3] % 4) + 1
        # 뒤 6자리 (체크섬은 단순화)
        rest = ''.join(str((h[i] + i) % 10) for i in range(4, 10))
        front = f"{yy:02d}{mm:02d}{dd:02d}"
        full = f"{front}{gender}{rest}"
        # 체크섬 계산 (간소화 - 실제 RRN 알고리즘)
        weights = [2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5]
        s = sum(int(full[i]) * weights[i] for i in range(12))
        check = (11 - (s % 11)) % 10
        return f"{front}-{gender}{rest[:5]}{check}"
    
    @staticmethod
    def _fake_phone(original: str) -> str:
        """
        가짜 휴대폰 (deterministic)
        '010-1234-5678' → '010-7890-3456'
        """
        if not original:
            return original
        h = PIIMasker._hash_seed(original, "phone")
        mid = ''.join(str(h[i] % 10) for i in range(0, 4))
        last = ''.join(str(h[i] % 10) for i in range(4, 8))
        return f"010-{mid}-{last}"
    
    @staticmethod
    def _fake_email(original: str) -> str:
        """
        가짜 이메일 (deterministic) - 도메인 유지 (조회/조인 시 통계 의미 유지)
        'hong@gmail.com' → 'user_a3f2@gmail.com'
        """
        if not original:
            return original
        v = str(original).strip()
        if '@' not in v:
            return original
        local, domain = v.rsplit('@', 1)
        h = PIIMasker._hash_seed(original, "email")
        suffix = h.hex()[:6]
        return f"user_{suffix}@{domain}"
    
    @staticmethod
    def _fake_address(original: str) -> str:
        """
        가짜 주소 (deterministic) - 시/도 유지 (지역 분포 통계 보존)
        '서울 강남구 테헤란로 123' → '서울 ○○구 □□로 NNN'
        """
        if not original:
            return original
        v = str(original).strip()
        # 시/도 추출
        cities = ['서울', '부산', '대구', '인천', '광주', '대전', '울산',
                  '세종', '경기', '강원', '충북', '충남', '전북', '전남',
                  '경북', '경남', '제주']
        prefix = next((c for c in cities if v.startswith(c)), '서울')
        
        h = PIIMasker._hash_seed(original, "address")
        gu_list = ['강남구', '서초구', '송파구', '마포구', '용산구',
                   '종로구', '중구', '동작구', '관악구', '광진구']
        gu = gu_list[h[0] % len(gu_list)]
        ro = chr(ord('가') + (h[1] % 50)) + '로'
        num = (h[2] * 256 + h[3]) % 999 + 1
        return f"{prefix} {gu} {ro} {num}"
    
    @staticmethod
    def _fake_card(original: str) -> str:
        """
        가짜 카드번호 (deterministic) - 형식 유지 + 카드사 prefix 보존
        '5350-1234-5678-9012' → '5350-7890-3456-1234' (앞 4자리 보존)
        """
        if not original:
            return original
        v = re.sub(r'[\s\-]', '', str(original)).strip()
        if len(v) < 13:
            return original
        
        prefix = v[:4]  # 카드사 prefix 보존 (5350 = Visa, 4xxx = Master 등)
        h = PIIMasker._hash_seed(original, "card")
        digits = ''.join(str(h[i % 16] % 10) for i in range(12))
        return f"{prefix}-{digits[0:4]}-{digits[4:8]}-{digits[8:12]}"
    
    @staticmethod
    def _fake_account(original: str) -> str:
        """
        가짜 계좌번호 (deterministic)
        '110-1234-567890' → '110-9876-543210' (은행코드 보존)
        """
        if not original:
            return original
        v = str(original).strip()
        h = PIIMasker._hash_seed(original, "account")
        # 첫 3자리 (은행코드 추정) 보존
        prefix = v[:3] if len(v) >= 3 else "110"
        digits = ''.join(str(h[i % 16] % 10) for i in range(11))
        return f"{prefix}-{digits[0:4]}-{digits[4:11]}"
    
    @staticmethod
    def _fake_biz_number(original: str) -> str:
        """가짜 사업자번호 (deterministic) - 'NNN-NN-NNNNN' 형식"""
        if not original:
            return original
        h = PIIMasker._hash_seed(original, "biz")
        n1 = (h[0] * 256 + h[1]) % 900 + 100
        n2 = h[2] % 90 + 10
        n3 = (h[3] * 256 + h[4]) % 90000 + 10000
        return f"{n1:03d}-{n2:02d}-{n3:05d}"
    
    @staticmethod
    def _fake_corp_number(original: str) -> str:
        """가짜 법인번호 (deterministic) - 'NNNNNN-NNNNNNN' 형식"""
        if not original:
            return original
        h = PIIMasker._hash_seed(original, "corp")
        front = ''.join(str(h[i] % 10) for i in range(6))
        back = ''.join(str(h[i + 6] % 10) for i in range(7))
        return f"{front}-{back}"
    
    @staticmethod
    def _fake_passport(original: str) -> str:
        """가짜 여권번호 (deterministic) - 'M' + 8자리"""
        if not original:
            return original
        h = PIIMasker._hash_seed(original, "passport")
        digits = ''.join(str(h[i] % 10) for i in range(8))
        return f"M{digits}"
    
    @staticmethod
    def _fake_ip(original: str) -> str:
        """가짜 IP (deterministic) - 사설망 IP로 변환 (10.x.x.x)"""
        if not original:
            return original
        h = PIIMasker._hash_seed(original, "ip")
        return f"10.{h[0]}.{h[1]}.{h[2]}"
    
    @staticmethod
    def _fake_mac(original: str) -> str:
        """가짜 MAC (deterministic)"""
        if not original:
            return original
        h = PIIMasker._hash_seed(original, "mac")
        return ":".join(f"{h[i]:02X}" for i in range(6))
    
    @staticmethod
    def _fake_dob(original: str) -> str:
        """
        가짜 생년월일 (deterministic) - 날짜 형식 유지
        '1985-01-23' → '1981-07-15'
        """
        if not original:
            return original
        v = str(original).strip()
        h = PIIMasker._hash_seed(original, "dob")
        yy = 1960 + (h[0] % 60)  # 1960~2019
        mm = (h[1] % 12) + 1
        dd = (h[2] % 28) + 1
        return f"{yy}-{mm:02d}-{dd:02d}"
    
    @staticmethod
    def fake_by_category(original: Any, category) -> Any:
        """카테고리별 적합한 deterministic fake 데이터 반환"""
        if original is None or original == "":
            return original
        
        s = str(original)
        
        try:
            if category == PIICategory.NAME_KOR:
                return PIIMasker._fake_name(s)
            elif category == PIICategory.RRN:
                return PIIMasker._fake_rrn(s)
            elif category == PIICategory.FRN:
                return PIIMasker._fake_rrn(s)
            elif category == PIICategory.PHONE:
                return PIIMasker._fake_phone(s)
            elif category == PIICategory.PHONE_LAND:
                return PIIMasker._fake_phone(s)
            elif category == PIICategory.EMAIL:
                return PIIMasker._fake_email(s)
            elif category == PIICategory.ADDRESS:
                return PIIMasker._fake_address(s)
            elif category == PIICategory.CARD_NUMBER:
                return PIIMasker._fake_card(s)
            elif category == PIICategory.BANK_ACCOUNT:
                return PIIMasker._fake_account(s)
            elif category == PIICategory.BIZ_NUMBER:
                return PIIMasker._fake_biz_number(s)
            elif category == PIICategory.CORP_NUMBER:
                return PIIMasker._fake_corp_number(s)
            elif category == PIICategory.PASSPORT:
                return PIIMasker._fake_passport(s)
            elif category == PIICategory.IP_ADDRESS:
                return PIIMasker._fake_ip(s)
            elif category == PIICategory.MAC_ADDRESS:
                return PIIMasker._fake_mac(s)
            elif category == PIICategory.DOB:
                return PIIMasker._fake_dob(s)
            else:
                # 기본값: 카드 CVV 등은 단순 hash 기반
                h = PIIMasker._hash_seed(s, "default")
                return ''.join(str(h[i] % 10) for i in range(min(len(s), 6)))
        except Exception as e:
            _log.warning(f"fake_by_category 실패 ({category}): {e}")
            return PIIMasker._fallback_mask(s, MaskingStrategy.PARTIAL)


# ════════════════════════════════════════════════════════════════════════════
# 카테고리 → 마스킹 함수 매핑
# ════════════════════════════════════════════════════════════════════════════

CATEGORY_MASKERS: Dict[PIICategory, Callable] = {
    PIICategory.RRN: PIIMasker.mask_rrn,
    PIICategory.FRN: PIIMasker.mask_rrn,  # 같은 형식
    PIICategory.PHONE: PIIMasker.mask_phone,
    PIICategory.PHONE_LAND: PIIMasker.mask_phone,
    PIICategory.EMAIL: PIIMasker.mask_email,
    PIICategory.NAME_KOR: PIIMasker.mask_name,
    PIICategory.CARD_NUMBER: PIIMasker.mask_card,
    PIICategory.BANK_ACCOUNT: PIIMasker.mask_account,
    PIICategory.ADDRESS: PIIMasker.mask_address,
    PIICategory.DOB: PIIMasker.mask_dob,
    PIICategory.PASSPORT: PIIMasker.mask_passport,
    PIICategory.IP_ADDRESS: PIIMasker.mask_ip,
}


# ════════════════════════════════════════════════════════════════════════════
# Preset 정책
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class MaskingPolicy:
    """단일 컬럼에 대한 마스킹 정책"""
    column_name: str
    table_name: str
    category: PIICategory
    strategy: MaskingStrategy
    
    def apply(self, value: Any) -> Any:
        """실제 값에 마스킹 적용"""
        if self.strategy == MaskingStrategy.KEEP:
            return value
        
        # v89.7: PSEUDONYM / FAKE 는 deterministic fake generator 사용
        # → 같은 입력 → 항상 같은 출력 (조인/조회 보존)
        if self.strategy in (MaskingStrategy.PSEUDONYM, MaskingStrategy.FAKE):
            return PIIMasker.fake_by_category(value, self.category)
        
        masker = CATEGORY_MASKERS.get(self.category)
        if masker:
            return masker(value, self.strategy)
        # fallback
        return PIIMasker._fallback_mask(str(value) if value else "", self.strategy)


def build_policies_from_preset(
    detections: List[PIIDetection],
    preset: MaskingPreset,
) -> List[MaskingPolicy]:
    """Preset 에 따라 자동으로 정책 생성"""
    policies = []
    
    for d in detections:
        strategy = _decide_strategy(d, preset)
        policies.append(MaskingPolicy(
            column_name=d.column_name,
            table_name=d.table_name,
            category=d.category,
            strategy=strategy,
        ))
    
    return policies


def _decide_strategy(
    detection: PIIDetection,
    preset: MaskingPreset,
) -> MaskingStrategy:
    """Preset + 민감도 기반 전략 결정"""
    
    if preset == MaskingPreset.PRODUCTION_CLONE:
        return MaskingStrategy.KEEP
    
    if preset == MaskingPreset.DEV_ENVIRONMENT:
        # v89.7: 개발 환경 = Deterministic Pseudonymization
        #   - 같은 원본 → 항상 같은 가짜 값
        #   - 조인/조회 보존 (customer.name == payment.holder)
        #   - 데이터 정합성 테스트 가능
        #   - 형식/도메인 유지 (개발자 디버깅 가능)
        # 카테고리별 동작:
        #   NAME_KOR: '홍길동' → '김갑돌' (한글 이름 풀에서)
        #   RRN: '850123-1234567' → '781205-1456789' (체크섬 포함)
        #   PHONE: '010-1234-5678' → '010-7890-3456'
        #   EMAIL: 'hong@gmail.com' → 'user_a3f2@gmail.com' (도메인 보존)
        #   ADDRESS: '서울 강남구...' → '서울 ○○구...' (시/도 보존)
        #   CARD: '5350-1234-5678-9012' → '5350-7890-3456-1234' (카드사 prefix 보존)
        #   CVV/PASSPORT 등도 형식 유지하면서 가짜 값
        if detection.category == PIICategory.CARD_CVV:
            # CVV 는 짧아서 PARTIAL 로 (deterministic 의미 적음)
            return MaskingStrategy.PARTIAL
        return MaskingStrategy.PSEUDONYM
    
    if preset == MaskingPreset.QA_ENVIRONMENT:
        # QA: Critical 만 마스킹
        if detection.sensitivity == PIISensitivity.CRITICAL:
            return MaskingStrategy.PARTIAL
        return MaskingStrategy.KEEP
    
    if preset == MaskingPreset.ANALYTICS:
        # 분석: 익명화 + 일반화
        if detection.category == PIICategory.ADDRESS:
            return MaskingStrategy.GENERALIZE
        if detection.category == PIICategory.DOB:
            return MaskingStrategy.GENERALIZE  # 연령대로
        if detection.category in (PIICategory.NAME_KOR, PIICategory.PHONE,
                                   PIICategory.EMAIL, PIICategory.RRN):
            return MaskingStrategy.HASH  # 분석은 join 가능하게
        return MaskingStrategy.HASH
    
    if preset == MaskingPreset.GDPR_COMPLIANT:
        # GDPR: 가명화 (right to be forgotten 위해 unhash 가능한 매핑테이블 별도 관리)
        if detection.category == PIICategory.NAME_KOR:
            return MaskingStrategy.PSEUDONYM
        if detection.sensitivity == PIISensitivity.CRITICAL:
            return MaskingStrategy.HASH
        return MaskingStrategy.PARTIAL
    
    if preset == MaskingPreset.PCI_DSS:
        # PCI-DSS: 카드 정보 완전 제거, CVV 는 NULL
        if detection.category == PIICategory.CARD_CVV:
            return MaskingStrategy.NULLIFY
        if detection.category == PIICategory.CARD_NUMBER:
            return MaskingStrategy.PARTIAL  # PAN 마스킹 (앞 6 + 뒤 4 만)
        if detection.sensitivity == PIISensitivity.CRITICAL:
            return MaskingStrategy.PARTIAL
        return MaskingStrategy.KEEP
    
    return MaskingStrategy.PARTIAL  # 기본


# ════════════════════════════════════════════════════════════════════════════
# SQL 생성기
# ════════════════════════════════════════════════════════════════════════════

def generate_masking_sql(
    policies: List[MaskingPolicy],
    target_db: str = "mysql",
) -> Dict[str, List[str]]:
    """
    마스킹 정책을 SQL 함수 호출로 변환.
    
    이관 SQL 의 SELECT 절에 적용 가능한 형태:
      SELECT customer_id,
             SUBSTRING(rrn, 1, 7) || '******' AS rrn,  -- masking 적용
             ...
      FROM source_table
    
    Returns:
        {table_name: [SQL fragments...]}
    """
    by_table: Dict[str, List[str]] = {}
    
    for policy in policies:
        sql_expr = _policy_to_sql(policy, target_db)
        if not sql_expr:
            continue
        by_table.setdefault(policy.table_name, []).append(sql_expr)
    
    return by_table


def _policy_to_sql(policy: MaskingPolicy, target_db: str) -> Optional[str]:
    """단일 정책을 SQL 표현식으로"""
    col = policy.column_name
    
    if policy.strategy == MaskingStrategy.KEEP:
        return f"`{col}`"
    
    if policy.strategy == MaskingStrategy.NULLIFY:
        return f"NULL AS `{col}`"
    
    if policy.strategy == MaskingStrategy.HASH:
        if target_db.lower() == "mysql":
            return f"SHA2(CONCAT('databridge_pii_salt', `{col}`), 256) AS `{col}`"
        elif target_db.lower() in ("mssql", "azure", "sqlserver"):
            return f"CONVERT(VARCHAR(64), HASHBYTES('SHA2_256', '{policy.column_name}'), 2) AS [{col}]"
        elif target_db.lower() == "postgres":
            return f"encode(digest('databridge_pii_salt' || \"{col}\", 'sha256'), 'hex') AS \"{col}\""
    
    if policy.strategy == MaskingStrategy.FULL:
        return f"REPEAT('*', LENGTH(`{col}`)) AS `{col}`"
    
    # PARTIAL — 카테고리별 SQL 생성
    if policy.strategy == MaskingStrategy.PARTIAL:
        if policy.category == PIICategory.RRN:
            # 'YYMMDD-1******'
            return (
                f"CONCAT(SUBSTRING(REPLACE(`{col}`, '-', ''), 1, 6), '-', "
                f"SUBSTRING(REPLACE(`{col}`, '-', ''), 7, 1), '******') AS `{col}`"
            )
        if policy.category == PIICategory.PHONE:
            # 010-****-1234
            return (
                f"CASE WHEN LENGTH(REPLACE(REPLACE(`{col}`, '-', ''), ' ', '')) = 11 "
                f"THEN CONCAT(SUBSTRING(REPLACE(REPLACE(`{col}`, '-', ''), ' ', ''), 1, 3), "
                f"'-****-', SUBSTRING(REPLACE(REPLACE(`{col}`, '-', ''), ' ', ''), 8, 4)) "
                f"ELSE `{col}` END AS `{col}`"
            )
        if policy.category == PIICategory.EMAIL:
            return (
                f"CONCAT(LEFT(SUBSTRING_INDEX(`{col}`, '@', 1), 2), "
                f"REPEAT('*', GREATEST(LENGTH(SUBSTRING_INDEX(`{col}`, '@', 1)) - 2, 0)), "
                f"'@', SUBSTRING_INDEX(`{col}`, '@', -1)) AS `{col}`"
            )
        if policy.category == PIICategory.NAME_KOR:
            return (
                f"CONCAT(LEFT(`{col}`, 1), REPEAT('*', GREATEST(CHAR_LENGTH(`{col}`) - 1, 0))) AS `{col}`"
            )
        if policy.category == PIICategory.CARD_NUMBER:
            return (
                f"CONCAT(LEFT(REPLACE(`{col}`, '-', ''), 4), '-****-****-', "
                f"RIGHT(REPLACE(`{col}`, '-', ''), 4)) AS `{col}`"
            )
        if policy.category == PIICategory.BANK_ACCOUNT:
            return (
                f"CONCAT(REPEAT('*', GREATEST(LENGTH(`{col}`) - 4, 0)), "
                f"RIGHT(`{col}`, 4)) AS `{col}`"
            )
        if policy.category == PIICategory.DOB:
            # YYYY-MM-DD → YYYY-**-**
            return f"CONCAT(LEFT(DATE_FORMAT(`{col}`, '%Y'), 4), '-**-**') AS `{col}`"
        if policy.category == PIICategory.IP_ADDRESS:
            return (
                f"CONCAT(SUBSTRING_INDEX(`{col}`, '.', 3), '.*') AS `{col}`"
            )
    
    # GENERALIZE
    if policy.strategy == MaskingStrategy.GENERALIZE:
        if policy.category == PIICategory.ADDRESS:
            return (
                f"SUBSTRING_INDEX(SUBSTRING_INDEX(`{col}`, ' ', 2), ' ', 2) AS `{col}`"
            )
    
    # 기본 fallback — 첫/마지막 글자만 유지
    return f"CONCAT(LEFT(`{col}`, 1), REPEAT('*', GREATEST(LENGTH(`{col}`) - 2, 0)), RIGHT(`{col}`, 1)) AS `{col}`"


# ════════════════════════════════════════════════════════════════════════════
# 미리보기 (Before/After)
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class MaskingPreview:
    """마스킹 미리보기 결과"""
    column_name: str
    category: str
    strategy: str
    samples: List[Dict[str, Any]]  # [{"before": ..., "after": ...}]
    affected_rows_estimate: int = 0


def generate_preview(
    policies: List[MaskingPolicy],
    sample_data: Dict[str, List[Any]],
    sample_count: int = 5,
) -> List[MaskingPreview]:
    """
    마스킹 적용 미리보기.
    실제 데이터에 정책 적용해서 Before/After 보여줌.
    
    v89.5: sample_data 없어도 카테고리별 fake 샘플로 미리보기 생성.
           → 사용자가 정책 변경 시 효과를 즉시 확인 가능.
    """
    # 카테고리별 fake 샘플 (sample_data 없을 때 fallback)
    FAKE_SAMPLES_BY_CATEGORY = {
        "rrn": ["850123-1234567", "920301-2345678"],
        "frn": ["900215-5234567"],
        "passport": ["M12345678"],
        "driver_license": ["11-12-345678-90"],
        "name_kor": ["홍길동", "김철수"],
        "phone": ["010-1234-5678"],
        "phone_land": ["02-555-1234"],
        "email": ["hong@example.com"],
        "address": ["서울특별시 강남구 테헤란로 123"],
        "dob": ["1985-01-23"],
        "bank_account": ["110-1234-567890"],
        "card_number": ["5350-1234-5678-9012"],
        "card_cvv": ["123"],
        "biz_number": ["123-45-67890"],
        "corp_number": ["110111-1234567"],
        "ip_address": ["192.168.1.50"],
        "mac_address": ["AA:BB:CC:11:22:33"],
    }
    
    previews = []
    
    for policy in policies:
        # 1) 실제 샘플 데이터 우선
        samples = sample_data.get(policy.column_name, [])[:sample_count]
        
        # 2) 없으면 카테고리별 fake 샘플 사용 (정책 효과 시각화용)
        if not samples:
            cat_key = policy.category.value if hasattr(policy.category, 'value') else str(policy.category)
            samples = FAKE_SAMPLES_BY_CATEGORY.get(cat_key, ["sample_data"])[:sample_count]
        
        compared = []
        for original in samples:
            try:
                masked = policy.apply(original)
                compared.append({
                    "before": str(original) if original is not None else "(NULL)",
                    "after": str(masked) if masked is not None else "(NULL)",
                })
            except Exception as e:
                compared.append({
                    "before": str(original),
                    "after": f"(ERROR: {e})",
                })
        
        previews.append(MaskingPreview(
            column_name=policy.column_name,
            category=policy.category.value,
            strategy=policy.strategy.value,
            samples=compared,
        ))
    
    return previews
