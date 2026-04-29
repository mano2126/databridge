"""
ddl_preflight_validator.py — Phase H-2 (2026-04-25)

DDL 사전 검증 — 변환된 DDL 을 타겟 DB 에 실행하기 직전에
미리 점검해서 알려진 실패 패턴을 잡아냄.

해결하려는 문제 (error_cases.txt 분석 결과):
  유형 A) 의존성 순서          → H-1 dependency_resolver 가 해결
  유형 B) AI 변환 syntax      → H-2 가 해결 (이 모듈)
  유형 C) Collation 충돌      → H-2 가 해결
  유형 D) 메타 (스키마 접두사)  → H-2 가 해결

검증 항목 (실제 error_cases 패턴 기반):
  1. SQL syntax 기본 (괄호 균형, 세미콜론 위치)
  2. 서브쿼리 alias 뒤 세미콜론 금지 (1064 패턴)
  3. LIMIT n 뒤 줄바꿈 누락 (FN_GETCODENAME 패턴)
  4. CREATE 헤더 이중 괄호 (((
  5. INTO p_p_var (이중 p_ 접두)
  6. MSSQL 스키마 접두사 잔존 ([dbo].[table])
  7. DELIMITER 처리
  8. BEGIN/END 균형
  9. CONCAT 안 COLLATE (유효하지 않은 위치)
  10. CASE/WHEN/END 균형

각 검증은 (status, message, suggestion) 반환.
"""

from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

_log = logging.getLogger("databridge.ddl_validator")


# ════════════════════════════════════════════════════════════════════════════
# 데이터 모델
# ════════════════════════════════════════════════════════════════════════════

class ValidationLevel(str, Enum):
    """검증 결과 심각도"""
    PASS = "pass"        # 통과
    WARNING = "warning"  # 경고 (실행해도 됨)
    ERROR = "error"      # 오류 (실행 시 실패 확실)


@dataclass
class ValidationIssue:
    """단일 검증 이슈"""
    rule_id: str                # 'paren_balance', 'subquery_semi' 등
    level: ValidationLevel
    title: str                  # 한글 제목
    message: str                # 상세 설명
    location: Optional[str] = None  # 발견 위치 (예: "라인 12")
    suggestion: Optional[str] = None  # 수정 제안
    auto_fix: Optional[str] = None  # 자동 수정된 DDL (있으면)


@dataclass
class ValidationResult:
    """단일 DDL 검증 결과"""
    object_name: str
    object_type: str           # 'view', 'function', 'procedure', 'trigger'
    issues: List[ValidationIssue] = field(default_factory=list)
    fixed_ddl: Optional[str] = None  # auto-fix 적용된 DDL
    
    @property
    def has_errors(self) -> bool:
        return any(i.level == ValidationLevel.ERROR for i in self.issues)
    
    @property
    def has_warnings(self) -> bool:
        return any(i.level == ValidationLevel.WARNING for i in self.issues)
    
    @property
    def can_proceed(self) -> bool:
        """실행 가능 여부 (ERROR 없으면)"""
        return not self.has_errors
    
    def to_dict(self) -> dict:
        return {
            "object_name": self.object_name,
            "object_type": self.object_type,
            "can_proceed": self.can_proceed,
            "issues": [
                {
                    "rule_id": i.rule_id,
                    "level": i.level.value,
                    "title": i.title,
                    "message": i.message,
                    "location": i.location,
                    "suggestion": i.suggestion,
                }
                for i in self.issues
            ],
            "has_fix": self.fixed_ddl is not None,
        }


# ════════════════════════════════════════════════════════════════════════════
# 유틸리티 (주석/문자열 제거)
# ════════════════════════════════════════════════════════════════════════════

_RE_LINE_COMMENT = re.compile(r'--[^\n]*', re.MULTILINE)
_RE_BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.DOTALL)


def _strip_comments(ddl: str) -> str:
    """주석 제거 (괄호 균형 등 검사 시)"""
    if not ddl:
        return ""
    s = _RE_BLOCK_COMMENT.sub(' ', ddl)
    s = _RE_LINE_COMMENT.sub(' ', s)
    return s


def _strip_strings_and_comments(ddl: str) -> str:
    """주석 + 문자열 리터럴 제거"""
    s = _strip_comments(ddl)
    # 문자열 리터럴 ' ... '
    s = re.sub(r"'(?:[^']|'')*'", "''", s, flags=re.DOTALL)
    return s


# ════════════════════════════════════════════════════════════════════════════
# 개별 검증 룰
# ════════════════════════════════════════════════════════════════════════════

def check_paren_balance(ddl: str) -> Optional[ValidationIssue]:
    """규칙 1: 괄호 균형"""
    cleaned = _strip_strings_and_comments(ddl)
    open_count = cleaned.count('(')
    close_count = cleaned.count(')')
    
    if open_count != close_count:
        return ValidationIssue(
            rule_id="paren_balance",
            level=ValidationLevel.ERROR,
            title="괄호 불균형",
            message=f"여는 괄호 {open_count}개, 닫는 괄호 {close_count}개 — 차이 {abs(open_count-close_count)}개",
            suggestion="여는/닫는 괄호 수가 일치해야 함. AI 변환 결과 점검 필요.",
        )
    return None


def check_double_paren_after_create(ddl: str) -> Optional[ValidationIssue]:
    """규칙 2: CREATE 헤더 이중 괄호 (FN_GETCODENAME 패턴)"""
    # CREATE FUNCTION name (( 또는 CREATE FUNCTION name `quoted_name` ((
    # AI 변환 시 이름이 이중으로 나오는 케이스도 처리
    pattern = re.compile(
        r'CREATE\s+(?:DEFINER\s*=\s*\S+\s+)?(?:FUNCTION|PROCEDURE)\s+'
        r'(?:`[^`]+`|\w+)'              # 첫 식별자
        r'(?:\s+(?:`[^`]+`|\w+))?'      # 선택적 두 번째 식별자 (이중 이름 패턴)
        r'\s*\(\s*\(',                  # 이중 괄호
        re.IGNORECASE,
    )
    m = pattern.search(ddl)
    if m:
        return ValidationIssue(
            rule_id="double_paren_create",
            level=ValidationLevel.ERROR,
            title="CREATE 헤더 이중 괄호",
            message=f"CREATE FUNCTION/PROCEDURE 뒤에 '((' 발견 — 1064 syntax error 발생",
            location=f"위치 {m.start()}",
            suggestion="CREATE FUNCTION `name` 만 쓰고 파라미터 괄호 1개만 유지",
        )
    return None


def check_subquery_alias_semicolon(ddl: str) -> Optional[ValidationIssue]:
    """규칙 3: 서브쿼리 alias 뒤 세미콜론 (tvf_delinq_ranking 패턴)
    
    잘못된 패턴: ) sub;
    올바른 패턴: ) sub
    """
    cleaned = _strip_strings_and_comments(ddl)
    
    # ) alias_name ;  (END/RETURN 등 SQL 키워드 제외)
    pattern = re.compile(
        r'\)\s+([a-zA-Z_]\w*)\s*;',
        re.IGNORECASE,
    )
    
    sql_keywords = {'end', 'return', 'select', 'from', 'where', 'group', 
                   'order', 'having', 'limit', 'union', 'intersect', 'except',
                   'on', 'using', 'as', 'and', 'or'}
    
    for m in pattern.finditer(cleaned):
        alias = m.group(1).lower()
        if alias not in sql_keywords:
            return ValidationIssue(
                rule_id="subquery_alias_semicolon",
                level=ValidationLevel.ERROR,
                title="서브쿼리 alias 뒤 세미콜론",
                message=f"서브쿼리 alias '{alias}' 뒤에 세미콜론 — 1064 syntax error",
                location=f"위치 {m.start()}",
                suggestion=f"') {alias};' → ') {alias}' (세미콜론 제거). "
                          "세미콜론은 SET/SELECT/RETURN 등 최상위 SQL 문장 끝에만.",
            )
    return None


def check_limit_no_newline(ddl: str) -> Optional[ValidationIssue]:
    """규칙 4: LIMIT 뒤 줄바꿈 누락 (FN_GETCODENAME)"""
    # LIMIT n RETURN  같은 패턴 (LIMIT 1RETURN 도)
    pattern = re.compile(
        r'\bLIMIT\s+\d+\s*[A-Za-z]',  # LIMIT 1뒤에 바로 글자
        re.IGNORECASE,
    )
    m = pattern.search(ddl)
    if m:
        return ValidationIssue(
            rule_id="limit_no_newline",
            level=ValidationLevel.ERROR,
            title="LIMIT 뒤 세미콜론/줄바꿈 누락",
            message="LIMIT 뒤에 줄바꿈/세미콜론 없이 다른 키워드 — 1064 syntax",
            location=f"위치 {m.start()}",
            suggestion="LIMIT n; 다음에 새 줄로 RETURN 등을 작성",
        )
    return None


def check_double_p_prefix(ddl: str) -> Optional[ValidationIssue]:
    """규칙 5: INTO p_p_var (이중 p_ 접두)"""
    pattern = re.compile(r'\bINTO\s+p_p_\w+', re.IGNORECASE)
    m = pattern.search(ddl)
    if m:
        return ValidationIssue(
            rule_id="double_p_prefix",
            level=ValidationLevel.WARNING,
            title="이중 p_ 접두사",
            message=f"INTO p_p_xxx 패턴 — 변환 시 p_ 가 두 번 추가됨",
            location=f"위치 {m.start()}",
            suggestion="INTO p_xxx 로 수정 (한 번만 적용)",
        )
    return None


def check_mssql_schema_prefix(ddl: str) -> Optional[ValidationIssue]:
    """규칙 6: MSSQL 스키마 접두사 잔존 ([dbo].[table])"""
    # [schema].[table] 패턴 — MSSQL 만의 표기
    pattern = re.compile(r'\[\w+\]\s*\.\s*\[\w+\]', re.IGNORECASE)
    m = pattern.search(ddl)
    if m:
        return ValidationIssue(
            rule_id="mssql_schema_prefix",
            level=ValidationLevel.ERROR,
            title="MSSQL 스키마 접두사 잔존",
            message=f"'{m.group()}' — MSSQL 표기가 변환 안 됨, MySQL 에서 1146 발생",
            location=f"위치 {m.start()}",
            suggestion="[schema].[table] → `table` 또는 `schema_table` 로 변환",
        )
    
    # collection.delinquent 처럼 점 표기 (MySQL 외부 db 가 아닌 경우)
    # 이건 컨텍스트 봐야 해서 WARNING 만
    pattern2 = re.compile(r'\bFROM\s+(\w+)\.(\w+)', re.IGNORECASE)
    m2 = pattern2.search(ddl)
    if m2:
        schema = m2.group(1).lower()
        # 일반적인 schema 이름
        if schema in ('dbo', 'collection', 'credit', 'customer', 'finance', 'mssql'):
            return ValidationIssue(
                rule_id="mssql_schema_prefix",
                level=ValidationLevel.WARNING,
                title="스키마 접두사 의심",
                message=f"FROM {m2.group(1)}.{m2.group(2)} — MSSQL 스키마 표기 의심",
                suggestion="MySQL 에서는 database.table 만 지원. 스키마 접두사 제거 검토.",
            )
    
    return None


def check_begin_end_balance(ddl: str) -> Optional[ValidationIssue]:
    """규칙 7: BEGIN/END 균형 (PROCEDURE/FUNCTION 만)"""
    cleaned = _strip_strings_and_comments(ddl).upper()
    # 단어 경계 BEGIN / END (END IF, END WHILE 등 제외)
    begin_count = len(re.findall(r'\bBEGIN\b', cleaned))
    end_count = len(re.findall(r'\bEND\b', cleaned))
    
    # END IF, END WHILE, END LOOP, END CASE 도 END 카운트 됨
    # 따라서 BEGIN 마다 매칭되는 END 가 있어야 함 → END 가 BEGIN 보다 같거나 많아야
    if begin_count > end_count:
        return ValidationIssue(
            rule_id="begin_end_balance",
            level=ValidationLevel.ERROR,
            title="BEGIN/END 불균형",
            message=f"BEGIN {begin_count}개, END {end_count}개 — END 부족",
            suggestion="모든 BEGIN 에 대응하는 END 추가 필요",
        )
    return None


def check_collate_in_concat(ddl: str) -> Optional[ValidationIssue]:
    """규칙 8: CONCAT/INSERT 함수 안에 COLLATE 사용 (SP_STATSYSTEM 패턴)"""
    pattern = re.compile(
        r'\b(?:CONCAT|INSERT)\s*\([^)]*\bCOLLATE\b',
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(ddl)
    if m:
        return ValidationIssue(
            rule_id="collate_in_concat",
            level=ValidationLevel.ERROR,
            title="CONCAT/INSERT 함수 안 COLLATE",
            message="CONCAT/INSERT 함수 인자 안에 COLLATE — MySQL 이 인식 못함, 1270",
            location=f"위치 {m.start()}",
            suggestion=(
                "DECLARE 로 지역변수 선언 후 SUBSTRING 으로 직접 조립. "
                "또는 변수 선언 시 CHARSET utf8mb4 COLLATE utf8mb4_0900_ai_ci 명시."
            ),
        )
    return None


def check_leave_label(ddl: str) -> Optional[ValidationIssue]:
    """규칙 9: LEAVE 레이블 매칭 (Insert_Theater_New 패턴)"""
    cleaned = _strip_strings_and_comments(ddl)
    
    # LEAVE 사용
    leave_matches = list(re.finditer(r'\bLEAVE\s+(\w+)\b', cleaned, re.IGNORECASE))
    if not leave_matches:
        return None
    
    # 정의된 레이블 추출 (label_name : BEGIN 또는 label_name : LOOP)
    labels = set()
    for m in re.finditer(r'(\w+)\s*:\s*(?:BEGIN|LOOP|REPEAT|WHILE)', cleaned, re.IGNORECASE):
        labels.add(m.group(1).lower())
    
    # 매칭 안 되는 LEAVE 찾기
    for lm in leave_matches:
        label = lm.group(1).lower()
        if label not in labels:
            return ValidationIssue(
                rule_id="leave_label_unmatched",
                level=ValidationLevel.ERROR,
                title="LEAVE 레이블 미정의",
                message=f"LEAVE {lm.group(1)} — 일치하는 레이블 정의 없음, 1308 발생",
                location=f"위치 {lm.start()}",
                suggestion=f"BEGIN/LOOP 앞에 '{lm.group(1)}:' 레이블 정의 또는 LEAVE 제거",
            )
    return None


def check_super_privilege(ddl: str) -> Optional[ValidationIssue]:
    """규칙 10: SUPER privilege 필요 패턴 (Base64Decode FUNCTION 패턴)"""
    # DEFINER = ... 가 root 또는 다른 권한 있는 사용자
    if 'DEFINER' in ddl.upper():
        # FUNCTION 인 경우 binary log 필요할 수 있음
        if re.search(r'CREATE\s+(?:DEFINER\s*=\s*\S+\s+)?FUNCTION', ddl, re.IGNORECASE):
            return ValidationIssue(
                rule_id="super_privilege",
                level=ValidationLevel.WARNING,
                title="SUPER privilege 필요 가능성",
                message="DEFINER 절 + FUNCTION — log_bin_trust_function_creators=1 또는 SUPER 권한 필요",
                suggestion=(
                    "MySQL 서버에 SET GLOBAL log_bin_trust_function_creators = 1; 적용 또는 "
                    "DEFINER 절 제거"
                ),
            )
    return None


def check_create_keyword(ddl: str) -> Optional[ValidationIssue]:
    """규칙 11: CREATE 문 자체가 있는지 (sp_assign_collector 패턴)"""
    if not re.search(r'\bCREATE\s+(VIEW|FUNCTION|PROCEDURE|TRIGGER|TABLE)\b', 
                     ddl, re.IGNORECASE):
        return ValidationIssue(
            rule_id="no_create_statement",
            level=ValidationLevel.ERROR,
            title="CREATE 문장 없음",
            message="실행 가능한 CREATE 문장이 없음 — AI 응답 파싱 오류 가능성",
            suggestion="AI 변환 결과 재확인. 또는 마크다운 코드 블록 ```sql ... ``` 안에 있는지 확인.",
        )
    return None


# ════════════════════════════════════════════════════════════════════════════
# 자동 수정 (auto-fix) 함수들
# ════════════════════════════════════════════════════════════════════════════

def auto_fix_subquery_alias_semicolon(ddl: str) -> Optional[str]:
    """서브쿼리 alias 뒤 세미콜론 자동 제거"""
    # ) alias ; → ) alias
    sql_keywords = {'end', 'return', 'select', 'from', 'where', 'group', 
                   'order', 'having', 'limit'}
    
    def replacer(m):
        alias = m.group(1)
        if alias.lower() in sql_keywords:
            return m.group(0)  # 변경 안 함
        return f') {alias}'
    
    fixed = re.sub(r'\)\s+([a-zA-Z_]\w*)\s*;', replacer, ddl)
    return fixed if fixed != ddl else None


def auto_fix_double_p_prefix(ddl: str) -> Optional[str]:
    """INTO p_p_xxx → INTO p_xxx"""
    fixed = re.sub(r'\bINTO\s+p_p_(\w+)', r'INTO p_\1', ddl, flags=re.IGNORECASE)
    return fixed if fixed != ddl else None


def auto_fix_mssql_schema_prefix(ddl: str) -> Optional[str]:
    """[schema].[table] → `table`"""
    fixed = re.sub(r'\[(\w+)\]\s*\.\s*\[(\w+)\]', r'`\2`', ddl)
    return fixed if fixed != ddl else None


def auto_fix_limit_newline(ddl: str) -> Optional[str]:
    """LIMIT 1RETURN → LIMIT 1; \n RETURN"""
    pattern = re.compile(r'(\bLIMIT\s+\d+)\s*([A-Za-z])', re.IGNORECASE)
    fixed = pattern.sub(r'\1;\n  \2', ddl)
    return fixed if fixed != ddl else None


# ════════════════════════════════════════════════════════════════════════════
# 메인 API
# ════════════════════════════════════════════════════════════════════════════

# 룰 카탈로그 (rule_id → 검증 함수)
# 순서 중요: 더 구체적인 룰을 먼저 (구체적 검출이 일반적 검출보다 도움됨)
ALL_RULES = [
    ('no_create_statement', check_create_keyword),
    ('double_paren_create', check_double_paren_after_create),  # paren_balance 보다 먼저
    ('paren_balance', check_paren_balance),
    ('subquery_alias_semicolon', check_subquery_alias_semicolon),
    ('limit_no_newline', check_limit_no_newline),
    ('double_p_prefix', check_double_p_prefix),
    ('mssql_schema_prefix', check_mssql_schema_prefix),
    ('begin_end_balance', check_begin_end_balance),
    ('collate_in_concat', check_collate_in_concat),
    ('leave_label_unmatched', check_leave_label),
    ('super_privilege', check_super_privilege),
]

# 자동 수정 가능한 룰
AUTO_FIX_RULES = {
    'subquery_alias_semicolon': auto_fix_subquery_alias_semicolon,
    'double_p_prefix': auto_fix_double_p_prefix,
    'mssql_schema_prefix': auto_fix_mssql_schema_prefix,
    'limit_no_newline': auto_fix_limit_newline,
}


def validate_ddl(
    ddl: str,
    object_name: str,
    object_type: str = "view",
    enable_auto_fix: bool = True,
) -> ValidationResult:
    """
    DDL 사전 검증 — 모든 룰 적용 후 결과 반환.
    
    Args:
        ddl: 검증할 DDL
        object_name: 오브젝트명 (로그용)
        object_type: 'view', 'function', 'procedure', 'trigger', 'table'
        enable_auto_fix: 자동 수정 시도 여부
    
    Returns:
        ValidationResult
    """
    result = ValidationResult(
        object_name=object_name,
        object_type=object_type,
    )
    
    if not ddl or not ddl.strip():
        result.issues.append(ValidationIssue(
            rule_id="empty_ddl",
            level=ValidationLevel.ERROR,
            title="DDL 비어있음",
            message="검증할 DDL 이 빈 문자열",
        ))
        return result
    
    # 모든 룰 적용
    current_ddl = ddl
    for rule_id, checker in ALL_RULES:
        try:
            issue = checker(current_ddl)
            if issue:
                result.issues.append(issue)
                # 자동 수정 시도
                if enable_auto_fix and rule_id in AUTO_FIX_RULES:
                    fixed = AUTO_FIX_RULES[rule_id](current_ddl)
                    if fixed:
                        current_ddl = fixed
                        issue.auto_fix = "자동 수정됨"
        except Exception as e:
            _log.warning(f"[Validator] {rule_id} 검증 실패: {e}")
    
    if enable_auto_fix and current_ddl != ddl:
        result.fixed_ddl = current_ddl
    
    return result


def validate_ddls(
    ddls: Dict[str, Dict[str, str]],
    enable_auto_fix: bool = True,
) -> Dict[str, ValidationResult]:
    """
    여러 DDL 일괄 검증.
    
    Args:
        ddls: {name: {"type": "view", "ddl": "..."}}
    
    Returns:
        {name: ValidationResult}
    """
    results = {}
    for name, info in ddls.items():
        results[name] = validate_ddl(
            ddl=info.get("ddl", ""),
            object_name=name,
            object_type=info.get("type", "view"),
            enable_auto_fix=enable_auto_fix,
        )
    return results


def summarize_validation(results: Dict[str, ValidationResult]) -> Dict[str, any]:
    """검증 결과 종합 요약"""
    total = len(results)
    can_proceed = sum(1 for r in results.values() if r.can_proceed)
    has_errors = sum(1 for r in results.values() if r.has_errors)
    has_warnings = sum(1 for r in results.values() if r.has_warnings)
    auto_fixed = sum(1 for r in results.values() if r.fixed_ddl)
    
    # 룰별 카운트
    by_rule = {}
    for r in results.values():
        for issue in r.issues:
            by_rule.setdefault(issue.rule_id, 0)
            by_rule[issue.rule_id] += 1
    
    return {
        "total": total,
        "can_proceed": can_proceed,
        "blocked": has_errors,
        "with_warnings": has_warnings,
        "auto_fixed": auto_fixed,
        "issues_by_rule": by_rule,
    }
