"""
prompt_enhancer.py — Phase H-4 (2026-04-25)

AI 변환 prompt 강화 — error_cases.txt 의 누적 학습을 prompt 에 지능적으로 주입.

문제 정의:
  현재 obj_executor.py 는 error_cases.txt 의 최근 20줄을 그대로 prompt 에 추가.
  → AI 입장: "주의해야 할 게 너무 많아서 어느 게 중요한지 모름"
  → 결과: 같은 실수 반복

해결:
  1) 에러 패턴 자동 분류 (카테고리별)
  2) 현재 변환 대상에 관련 있는 패턴만 선별
  3) "이런 입력 → 이렇게 변환" 형식으로 명확한 예시 제공
  4) 중요도 순으로 정렬 (CRITICAL → 일반)

설계 원칙:
  - 비침습적: error_cases.txt 형식 유지 (기존 누적 시스템 호환)
  - 지능적: 변환 대상에 따라 prompt 동적 변경
  - 명확함: AI 가 이해하기 쉬운 형식
  - 학습 강화: H-3 의 실패가 자동으로 prompt 개선

핵심 컴포넌트:
  - PatternExtractor: error_cases 에서 패턴 자동 추출
  - PatternMatcher: 현재 DDL 과 매칭되는 패턴 선택
  - PromptBuilder: 강화된 prompt 생성
"""

from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
from enum import Enum

_log = logging.getLogger("databridge.prompt_enhancer")


# ════════════════════════════════════════════════════════════════════════════
# 데이터 모델
# ════════════════════════════════════════════════════════════════════════════

class PatternCategory(str, Enum):
    """error_cases 패턴 카테고리"""
    SYNTAX = "syntax"                # 1064 류
    DEPENDENCY = "dependency"        # 1146 류
    SCHEMA_PREFIX = "schema_prefix"  # MSSQL 접두사
    COLLATION = "collation"          # 1270 류
    DATA_TYPE = "data_type"          # 1406, 1292 류
    PERMISSION = "permission"        # 1419 류
    LABEL = "label"                  # 1308 LEAVE 류
    SUBQUERY = "subquery"            # 서브쿼리 alias 류
    DELIMITER = "delimiter"          # ; 위치 문제
    BEGIN_END = "begin_end"          # 블록 균형
    UNKNOWN = "unknown"


@dataclass
class ErrorPattern:
    """추출된 에러 패턴"""
    raw_text: str                   # 원본 error_cases 항목
    category: PatternCategory
    severity: str = "medium"         # critical/high/medium/low
    
    # AI 학습용
    bad_example: Optional[str] = None      # 잘못된 코드 예
    good_example: Optional[str] = None     # 올바른 코드 예
    rule_summary: str = ""                  # 한 줄 규칙
    
    # 매칭용
    trigger_keywords: Set[str] = field(default_factory=set)  # 이 키워드 있으면 관련
    object_types: Set[str] = field(default_factory=set)      # 적용되는 오브젝트 타입
    
    # 메타
    occurrence_count: int = 1                # 누적 발생 횟수
    last_seen_date: str = ""


# ════════════════════════════════════════════════════════════════════════════
# error_cases 파싱
# ════════════════════════════════════════════════════════════════════════════

# error_cases.txt 의 항목 패턴
# [날짜] 오브젝트명 (TYPE) | 에러 | 원인 ... 해결 ...
_RE_CASE_HEADER = re.compile(
    r'\[(\d{4}-\d{2}-\d{2})\]\s+([^\|]+?)\s*(?:\(([A-Z_/]+)\))?\s*\|\s*(.+)',
    re.MULTILINE,
)

# 카테고리별 키워드 매칭
CATEGORY_KEYWORDS = {
    PatternCategory.SYNTAX: [
        '1064', 'syntax', '서브쿼리', '세미콜론', 'syntax error',
    ],
    PatternCategory.DEPENDENCY: [
        '1146', "doesn't exist", '1049', 'unknown table', 'unknown database',
    ],
    PatternCategory.SCHEMA_PREFIX: [
        '스키마', 'schema', 'dbo.', '[dbo]', '접두사',
    ],
    PatternCategory.COLLATION: [
        '1270', 'collation', 'illegal mix', 'utf8mb4',
    ],
    PatternCategory.DATA_TYPE: [
        '1406', '1292', '1366', 'data too long', 'incorrect datetime',
        'varchar', 'datetime', '날짜', '데이터형',
    ],
    PatternCategory.PERMISSION: [
        '1419', 'super privilege', 'access denied',
    ],
    PatternCategory.LABEL: [
        '1308', 'leave', 'matching label', '레이블',
    ],
    PatternCategory.SUBQUERY: [
        '서브쿼리', 'subquery', 'alias', 'json_arrayagg',
    ],
    PatternCategory.DELIMITER: [
        'delimiter', '세미콜론 위치', 'multi_statements',
    ],
    PatternCategory.BEGIN_END: [
        'begin', 'end', '블록', 'leave with no matching',
    ],
}


def classify_pattern(text: str) -> PatternCategory:
    """텍스트에서 카테고리 분류"""
    text_lower = text.lower()
    
    # 가중치 기반 매칭 — 가장 많이 매칭되는 카테고리
    scores: Dict[PatternCategory, int] = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score > 0:
            scores[cat] = score
    
    if not scores:
        return PatternCategory.UNKNOWN
    
    return max(scores.items(), key=lambda x: x[1])[0]


def extract_severity(text: str) -> str:
    """심각도 추론"""
    text_lower = text.lower()
    
    # CRITICAL — 첫 이관 시 빈번한 패턴
    if any(kw in text_lower for kw in ['1146', '1064', '서브쿼리', 'syntax']):
        return "critical"
    
    # HIGH — 변환 결함
    if any(kw in text_lower for kw in ['1270', '1308', 'collation', 'leave']):
        return "high"
    
    # MEDIUM — 데이터/권한
    if any(kw in text_lower for kw in ['1406', '1292', '1419', 'data too']):
        return "medium"
    
    return "low"


def extract_examples(case_block: str) -> Tuple[Optional[str], Optional[str]]:
    """case_block 에서 잘못된/올바른 예시 추출"""
    bad = None
    good = None
    
    # "예: ..." 또는 "예) ..." 패턴
    bad_patterns = [
        r'잘못[된]?\s*[예:]+\s*(.+?)(?=\s*[해결올바른맞은✓]|$)',
        r'(?:기존|원본|wrong)\s*[:)]\s*(.+?)(?=\s*해결|올바른|→|$)',
    ]
    good_patterns = [
        r'(?:해결|올바른|맞은|예\)|예:)\s*(.+?)(?=\[\d{4}|$)',
        r'(?:correct|fix|→)\s*[:)]?\s*(.+?)(?=\[\d{4}|$)',
    ]
    
    for p in bad_patterns:
        m = re.search(p, case_block, re.IGNORECASE | re.DOTALL)
        if m:
            bad = m.group(1).strip()[:200]
            break
    
    for p in good_patterns:
        m = re.search(p, case_block, re.IGNORECASE | re.DOTALL)
        if m:
            good = m.group(1).strip()[:200]
            break
    
    return bad, good


def extract_keywords(text: str) -> Set[str]:
    """관련 키워드 추출 (현재 DDL 과 매칭용)"""
    keywords = set()
    
    # 함수/오브젝트 이름 추출
    for m in re.finditer(r'\b([A-Z_][A-Z0-9_]+|[a-z_][a-z0-9_]+)\b', text):
        word = m.group(1)
        if len(word) >= 4 and word not in ('CREATE', 'TABLE', 'BEGIN', 'WHERE'):
            keywords.add(word.lower())
    
    # 오류 코드
    for m in re.finditer(r'\b(\d{4})\b', text):
        keywords.add(m.group(1))
    
    return keywords


# ════════════════════════════════════════════════════════════════════════════
# 패턴 추출기
# ════════════════════════════════════════════════════════════════════════════

class PatternExtractor:
    """error_cases.txt 에서 ErrorPattern 리스트 추출"""
    
    def parse(self, error_cases_text: str) -> List[ErrorPattern]:
        """전체 텍스트 → 패턴 리스트"""
        if not error_cases_text:
            return []
        
        # 항목 분리: [YYYY-MM-DD] 로 시작하는 블록 단위
        blocks = self._split_into_blocks(error_cases_text)
        patterns = []
        
        for block in blocks:
            pattern = self._parse_single_block(block)
            if pattern:
                patterns.append(pattern)
        
        # 중복 제거 + 발생 횟수 누적
        return self._deduplicate(patterns)
    
    def _split_into_blocks(self, text: str) -> List[str]:
        """[YYYY-MM-DD] 단위로 분리"""
        blocks = []
        current_block: List[str] = []
        
        for line in text.split('\n'):
            if re.match(r'^\[\d{4}-\d{2}-\d{2}\]', line):
                # 새 블록 시작
                if current_block:
                    blocks.append('\n'.join(current_block).strip())
                current_block = [line]
            elif current_block:
                current_block.append(line)
        
        if current_block:
            blocks.append('\n'.join(current_block).strip())
        
        return [b for b in blocks if b]
    
    def _parse_single_block(self, block: str) -> Optional[ErrorPattern]:
        """단일 블록 → ErrorPattern"""
        m = _RE_CASE_HEADER.search(block)
        if not m:
            return None
        
        date_str = m.group(1)
        obj_name = m.group(2).strip()
        obj_type = (m.group(3) or "").strip()
        error_msg = m.group(4).strip()
        
        category = classify_pattern(block)
        severity = extract_severity(block)
        bad, good = extract_examples(block)
        
        # 한 줄 규칙 추출 (해결책 부분)
        rule_summary = self._extract_rule_summary(block)
        
        # 키워드 추출
        keywords = extract_keywords(block)
        
        # 오브젝트 타입 추출
        obj_types = set()
        if obj_type:
            for t in obj_type.split('/'):
                obj_types.add(t.strip().lower())
        
        return ErrorPattern(
            raw_text=block,
            category=category,
            severity=severity,
            bad_example=bad,
            good_example=good,
            rule_summary=rule_summary,
            trigger_keywords=keywords,
            object_types=obj_types,
            last_seen_date=date_str,
        )
    
    def _extract_rule_summary(self, block: str) -> str:
        """블록에서 한 줄 규칙 요약 추출"""
        # "해결: " 다음의 첫 줄
        m = re.search(r'해결[:\s]+(.+?)(?=\n|$)', block)
        if m:
            return m.group(1).strip()[:150]
        
        # 폴백: "원인: " 다음 첫 줄
        m = re.search(r'원인[:\s]+(.+?)(?=\n|$)', block)
        if m:
            return m.group(1).strip()[:150]
        
        # 더 폴백: 첫 100자
        return block[:100].replace('\n', ' ').strip()
    
    def _deduplicate(self, patterns: List[ErrorPattern]) -> List[ErrorPattern]:
        """동일 패턴 합치기 (rule_summary 기준)"""
        seen: Dict[str, ErrorPattern] = {}
        for p in patterns:
            key = (p.category.value, p.rule_summary[:80])
            if key in seen:
                # 발생 횟수 누적
                seen[key].occurrence_count += 1
                # 최신 날짜 사용
                if p.last_seen_date > seen[key].last_seen_date:
                    seen[key].last_seen_date = p.last_seen_date
                # 키워드 합치기
                seen[key].trigger_keywords |= p.trigger_keywords
            else:
                seen[key] = p
        
        return list(seen.values())


# ════════════════════════════════════════════════════════════════════════════
# 패턴 매처 (현재 DDL 에 관련된 패턴만 선택)
# ════════════════════════════════════════════════════════════════════════════

class PatternMatcher:
    """현재 변환 대상에 관련된 패턴만 선택"""
    
    def __init__(self, patterns: List[ErrorPattern]):
        self.patterns = patterns
    
    def find_relevant(
        self,
        ddl: str,
        object_type: str,
        max_count: int = 8,
    ) -> List[ErrorPattern]:
        """
        DDL 과 오브젝트 타입에 관련된 패턴 선택.
        
        선택 기준 (점수 합산):
          - 오브젝트 타입 매칭: +5점
          - DDL 안의 키워드 매칭: 키워드당 +3점
          - 카테고리가 universal (SCHEMA_PREFIX 등): +2점
          - severity critical: +5점
          - 최근 발생: +3점
          - 발생 빈도 높음: +2점/회
        """
        ddl_lower = ddl.lower() if ddl else ""
        obj_type_lower = object_type.lower()
        scored: List[Tuple[float, ErrorPattern]] = []
        
        for p in self.patterns:
            score = 0
            
            # 1. 오브젝트 타입 매칭
            if not p.object_types or obj_type_lower in p.object_types:
                score += 5
            elif p.object_types:
                # 매칭 안 됨 — skip
                continue
            
            # 2. 키워드 매칭
            if p.trigger_keywords:
                matched_kw = sum(1 for kw in p.trigger_keywords if kw in ddl_lower)
                score += matched_kw * 3
            
            # 3. Universal 카테고리 (DDL 무관하게 항상 적용)
            if p.category in (PatternCategory.SCHEMA_PREFIX, 
                             PatternCategory.SYNTAX,
                             PatternCategory.SUBQUERY):
                score += 2
            
            # 4. Severity
            severity_bonus = {'critical': 5, 'high': 3, 'medium': 1}.get(p.severity, 0)
            score += severity_bonus
            
            # 5. 최근 발생 (최신 일수록 중요)
            # 단순히 최신 날짜인지만 확인 (TODO: 더 정교한 시간 비교)
            
            # 6. 빈도
            score += min(p.occurrence_count * 2, 10)
            
            if score > 0:
                scored.append((score, p))
        
        # 점수 내림차순 정렬, 상위 N개
        scored.sort(key=lambda x: -x[0])
        return [p for _, p in scored[:max_count]]


# ════════════════════════════════════════════════════════════════════════════
# Prompt Builder (강화된 prompt 생성)
# ════════════════════════════════════════════════════════════════════════════

class PromptBuilder:
    """강화된 prompt 생성"""
    
    @staticmethod
    def build_error_lessons_section(patterns: List[ErrorPattern]) -> str:
        """관련 패턴 → AI 가 이해하기 쉬운 prompt 섹션"""
        if not patterns:
            return ""
        
        lines = []
        lines.append("【과거 실수 — 절대 반복 금지】")
        lines.append("")
        
        # 카테고리별 그룹핑
        by_cat: Dict[PatternCategory, List[ErrorPattern]] = {}
        for p in patterns:
            by_cat.setdefault(p.category, []).append(p)
        
        category_titles = {
            PatternCategory.SYNTAX: "🚫 SQL Syntax (1064)",
            PatternCategory.SUBQUERY: "🚫 서브쿼리 alias",
            PatternCategory.SCHEMA_PREFIX: "🚫 MSSQL 스키마 접두사",
            PatternCategory.COLLATION: "🚫 Collation 충돌 (1270)",
            PatternCategory.DATA_TYPE: "🚫 데이터 타입 (1406, 1292)",
            PatternCategory.LABEL: "🚫 LEAVE 레이블 (1308)",
            PatternCategory.PERMISSION: "🚫 권한 (1419)",
            PatternCategory.DEPENDENCY: "🚫 의존성 (1146)",
            PatternCategory.BEGIN_END: "🚫 BEGIN/END 균형",
            PatternCategory.DELIMITER: "🚫 DELIMITER",
        }
        
        for cat, cat_patterns in by_cat.items():
            title = category_titles.get(cat, f"🚫 {cat.value}")
            lines.append(f"### {title}")
            
            for p in cat_patterns[:3]:  # 카테고리별 최대 3건
                # 우선순위 인디케이터
                sev_icon = {'critical': '🔴', 'high': '🟠', 
                          'medium': '🟡', 'low': '⚪'}.get(p.severity, '⚪')
                
                rule = p.rule_summary[:120]
                lines.append(f"  {sev_icon} {rule}")
                
                if p.bad_example:
                    lines.append(f"     ❌ 잘못: {p.bad_example[:100]}")
                if p.good_example:
                    lines.append(f"     ✅ 올바: {p.good_example[:100]}")
                
                if p.occurrence_count > 1:
                    lines.append(f"     ⚠️ 이미 {p.occurrence_count}회 반복된 실수")
            
            lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def build_critical_rules_section() -> str:
        """변환 시 절대 룰 (error_cases 와 무관하게 항상 포함)"""
        return """【MySQL 변환 절대 규칙 — 위반 시 1064/1146 발생】

1. SQL Syntax 절대 룰
   - 서브쿼리 alias 뒤 세미콜론 금지: `) sub` (O)  /  `) sub;` (X)
   - 세미콜론은 SET/SELECT/RETURN/INSERT/UPDATE 등 최상위 SQL 끝에만
   - LIMIT n 뒤 즉시 RETURN 금지: `LIMIT 1; \\n RETURN v` (O)
   - CREATE FUNCTION/PROCEDURE 헤더에 이중 괄호 (( 금지

2. 스키마/식별자 룰
   - MSSQL 의 [schema].[table] → MySQL 의 `table` (스키마 제거)
   - dbo.table_name → table_name 만 사용
   - VIEW 안의 FROM 절도 동일 적용

3. Collation 룰
   - CONCAT/INSERT 함수 안에 COLLATE 사용 금지
   - 대안: DECLARE 로 지역변수 + SUBSTRING 직접 조립
   - 변수 선언 시: CHARSET utf8mb4 COLLATE utf8mb4_0900_ai_ci

4. 데이터 타입 룰
   - VARCHAR(8) 날짜는 그대로 VARCHAR(8) (DATE 변환 금지)
   - YYYYMMDD 문자열을 DATETIME 비교 시 INSERT() 함수 사용
   
5. BEGIN/END/LEAVE 룰
   - BEGIN 마다 매칭되는 END 필수
   - LEAVE 사용 시 BEGIN 앞에 레이블 정의 (예: proc_label: BEGIN)
   - END IF, END WHILE, END LOOP 도 명시
"""
    
    @staticmethod
    def enhance_prompt(
        base_prompt: str,
        ddl: str,
        object_type: str,
        error_cases_text: str,
    ) -> str:
        """
        기존 prompt → 강화된 prompt
        
        Args:
            base_prompt: obj_executor 가 생성한 기본 prompt
            ddl: 변환할 DDL
            object_type: FUNCTION / PROCEDURE / VIEW / TRIGGER
            error_cases_text: error_cases.txt 전체 내용
        
        Returns:
            강화된 prompt
        """
        # 1. error_cases 패턴 추출
        extractor = PatternExtractor()
        all_patterns = extractor.parse(error_cases_text)
        
        # 2. 현재 DDL 에 관련된 패턴만 선택
        matcher = PatternMatcher(all_patterns)
        relevant = matcher.find_relevant(ddl, object_type, max_count=8)
        
        # 3. 강화된 섹션 빌드
        critical_rules = PromptBuilder.build_critical_rules_section()
        error_lessons = PromptBuilder.build_error_lessons_section(relevant)
        
        enhancement_block = f"\n{critical_rules}\n"
        if error_lessons:
            enhancement_block += f"\n{error_lessons}\n"
        
        # 4. 기존 prompt 와 병합
        # - 기존 prompt 안에 이미 있는 'error_cases' 섹션 제거
        # - enhancement 를 적절한 위치에 삽입
        cleaned_base = re.sub(
            r'\n【과거 오류 패턴.*?】.*?(?=\n원본|\n###|\n【|\Z)',
            '\n',
            base_prompt,
            flags=re.DOTALL,
        )
        
        # 삽입 위치 결정 (우선순위 순)
        # a) "원본" 단어 앞에 삽입 (한국어 prompt)
        # b) "Original" 단어 앞 (영문 prompt)  
        # c) "DDL:" 앞
        # d) prompt 끝에 추가 (마지막 폴백)
        markers = ['원본', 'Original', 'DDL:', 'CREATE']
        inserted = False
        result = cleaned_base
        
        for marker in markers:
            if marker in cleaned_base:
                idx = cleaned_base.index(marker)
                result = (
                    cleaned_base[:idx] + 
                    enhancement_block + 
                    "\n" + cleaned_base[idx:]
                )
                inserted = True
                break
        
        # 폴백: prompt 시작에 추가
        if not inserted:
            result = enhancement_block + "\n" + cleaned_base
        
        return result


# ════════════════════════════════════════════════════════════════════════════
# 편의 API
# ════════════════════════════════════════════════════════════════════════════

def enhance_conversion_prompt(
    base_prompt: str,
    ddl: str,
    object_type: str,
    error_cases_text: str = "",
) -> str:
    """
    기존 prompt 강화 — 한 번 호출로 전체 처리.
    
    예시:
        from app.core.obj_executor import _make_prompt
        from app.core.prompt_enhancer import enhance_conversion_prompt
        
        base = _make_prompt(...)
        with open("error_cases.txt") as f:
            errors = f.read()
        
        prompt = enhance_conversion_prompt(base, ddl, "VIEW", errors)
        # → AI 호출
    """
    return PromptBuilder.enhance_prompt(
        base_prompt, ddl, object_type, error_cases_text
    )


def analyze_error_cases(error_cases_text: str) -> Dict[str, any]:
    """
    error_cases.txt 분석 리포트 (UI/로그용)
    
    Returns:
        {
            "total_patterns": 25,
            "by_category": {...},
            "by_severity": {...},
            "most_frequent": [(pattern, count), ...],
            "recent_dates": [...],
        }
    """
    extractor = PatternExtractor()
    patterns = extractor.parse(error_cases_text)
    
    by_cat: Dict[str, int] = {}
    by_sev: Dict[str, int] = {}
    
    for p in patterns:
        by_cat[p.category.value] = by_cat.get(p.category.value, 0) + 1
        by_sev[p.severity] = by_sev.get(p.severity, 0) + 1
    
    # 빈도 높은 패턴
    sorted_patterns = sorted(patterns, key=lambda p: -p.occurrence_count)
    most_frequent = [
        (p.rule_summary[:80], p.occurrence_count)
        for p in sorted_patterns[:5]
    ]
    
    # 최근 날짜
    recent_dates = sorted({p.last_seen_date for p in patterns}, reverse=True)[:5]
    
    return {
        "total_patterns": len(patterns),
        "by_category": by_cat,
        "by_severity": by_sev,
        "most_frequent": most_frequent,
        "recent_dates": recent_dates,
    }
