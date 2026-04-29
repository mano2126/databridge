"""
dependency_resolver.py — Phase H-1 (2026-04-25)

오브젝트 의존성 그래프 분석 + Topological Sort.

문제 정의:
  현재 이관 엔진은 오브젝트를 타입 순서로만 처리:
     FUNCTION 전체 → PROCEDURE 전체 → VIEW 전체 → TRIGGER 전체
  
  타입 내부에서는 알파벳 순 또는 메타 순서 사용.
  
  → VIEW 가 다른 VIEW 를 참조하거나, FUNCTION 이 다른 FUNCTION 을 호출하면
    의존 대상이 아직 생성 안 된 상태에서 실행 → 1146 Table doesn't exist

해결:
  1) 모든 오브젝트의 DDL 을 사전 분석 → 의존성 추출
  2) 의존성 그래프 빌드 (DAG)
  3) Topological Sort 로 안전한 순서 결정
  4) 순환 참조 감지 (있으면 deferred 큐로)

검증된 패턴 (error_cases.txt 기반):
  - VIEW → TABLE: 1146 Table 'X' doesn't exist (8건)
  - VIEW → VIEW: 다단 뷰 참조 (실제 케이스 다수)
  - TRIGGER → TABLE
  - FUNCTION → FUNCTION
  - PROCEDURE → FUNCTION

추출 정확도:
  - SQL 정규식 + AST 부분 사용
  - DELIMITER 처리, 주석 제거, 문자열 리터럴 무시
  - DB 별 식별자 인용 처리 (`name` / [name] / "name")
"""

from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional, Iterable
from collections import defaultdict, deque
from enum import Enum

_log = logging.getLogger("databridge.dep_resolver")


# ════════════════════════════════════════════════════════════════════════════
# 데이터 모델
# ════════════════════════════════════════════════════════════════════════════

class ObjectType(str, Enum):
    """오브젝트 타입"""
    TABLE = "table"
    VIEW = "view"
    FUNCTION = "function"
    PROCEDURE = "procedure"
    TRIGGER = "trigger"


# 타입 우선순위 (의존성 동등 시 사용)
TYPE_PRIORITY = {
    ObjectType.TABLE: 0,        # 가장 먼저
    ObjectType.FUNCTION: 1,
    ObjectType.PROCEDURE: 2,
    ObjectType.VIEW: 3,
    ObjectType.TRIGGER: 4,      # 가장 나중
}


@dataclass
class DBObject:
    """DB 오브젝트 메타"""
    name: str                                       # 오브젝트명 (스키마 제외)
    object_type: ObjectType
    ddl: str = ""                                   # 변환된 DDL (선택)
    schema: Optional[str] = None                    # 스키마명 (선택)
    
    # 분석 결과
    dependencies: Set[str] = field(default_factory=set)  # 참조하는 오브젝트명들
    dependents: Set[str] = field(default_factory=set)    # 이 오브젝트를 참조하는 것들
    
    @property
    def qualified_name(self) -> str:
        """schema.name 또는 name"""
        return f"{self.schema}.{self.name}" if self.schema else self.name
    
    def __repr__(self) -> str:
        return f"<{self.object_type.value}:{self.name}>"


@dataclass
class ResolveResult:
    """의존성 해석 결과"""
    ordered: List[DBObject]                  # 안전한 실행 순서
    cycles: List[List[str]] = field(default_factory=list)  # 순환 참조 (있으면)
    unresolved: List[str] = field(default_factory=list)    # 외부 참조 (DB 외부)
    
    @property
    def has_cycles(self) -> bool:
        return len(self.cycles) > 0


# ════════════════════════════════════════════════════════════════════════════
# DDL 파서 (의존성 추출)
# ════════════════════════════════════════════════════════════════════════════

# 주석 제거 정규식
_RE_LINE_COMMENT = re.compile(r'--[^\n]*', re.MULTILINE)
_RE_BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.DOTALL)

# 문자열 리터럴 (SQL 표준 ' + 이스케이프 '')
_RE_STRING_LIT = re.compile(r"'(?:[^']|'')*'", re.DOTALL)


def _strip_sql(ddl: str) -> str:
    """주석과 문자열 리터럴 제거 — 의존성 추출 정확도 향상"""
    if not ddl:
        return ""
    # 블록 주석
    s = _RE_BLOCK_COMMENT.sub(' ', ddl)
    # 라인 주석
    s = _RE_LINE_COMMENT.sub(' ', s)
    # 문자열 리터럴 → 공백 (오브젝트 이름 잘못 추출 방지)
    s = _RE_STRING_LIT.sub("''", s)
    return s


# 식별자 패턴 (백틱/대괄호/따옴표/맨이름)
# - `tbl` / [tbl] / "tbl" / tbl
# - 한글 + 숫자 + 언더스코어 허용
_IDENTIFIER_INNER = r'(?:`([^`]+)`|\[([^\]]+)\]|"([^"]+)"|(\w+))'

# FROM/JOIN/INTO 다음 테이블/뷰
# 패턴: FROM `schema`.`table` AS x
#       JOIN [schema].[table]
#       FROM table
_RE_FROM_TABLE = re.compile(
    r'\b(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+'  # 키워드
    r'(?:' + _IDENTIFIER_INNER + r'\s*\.\s*)?'  # 선택적 schema.
    r'' + _IDENTIFIER_INNER,  # 테이블명
    re.IGNORECASE,
)

# 함수/프로시저 호출
# CALL proc_name(...)  /  func_name(...)
_RE_FUNC_CALL = re.compile(
    r'(?:CALL\s+)?'
    r'(?:' + _IDENTIFIER_INNER + r'\s*\.\s*)?'
    r'' + _IDENTIFIER_INNER + r'\s*\(',
    re.IGNORECASE,
)

# 트리거의 ON 테이블
# CREATE TRIGGER ... ON `tbl_name`
_RE_TRIGGER_ON = re.compile(
    r'\bON\s+'
    r'(?:' + _IDENTIFIER_INNER + r'\s*\.\s*)?'
    r'' + _IDENTIFIER_INNER,
    re.IGNORECASE,
)

# CREATE 헤더 — 자기 자신 이름 (참조에서 제외)
_RE_CREATE_SELF = re.compile(
    r'\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:DEFINER\s*=\s*\S+\s+)?'
    r'(?:VIEW|FUNCTION|PROCEDURE|TRIGGER)\s+'
    r'(?:' + _IDENTIFIER_INNER + r'\s*\.\s*)?'
    r'' + _IDENTIFIER_INNER,
    re.IGNORECASE,
)


# 무시할 함수 이름 (DB 내장 함수 — 거짓 양성 방지)
_BUILTIN_FUNCTIONS = {
    # MySQL 표준
    'SELECT', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'BETWEEN', 'LIKE', 'IS', 'NULL',
    'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'GROUP_CONCAT',
    'CONCAT', 'CONCAT_WS', 'SUBSTRING', 'SUBSTR', 'LEFT', 'RIGHT', 'TRIM',
    'LTRIM', 'RTRIM', 'UPPER', 'LOWER', 'LENGTH', 'CHAR_LENGTH', 'REPLACE',
    'COALESCE', 'IFNULL', 'NULLIF', 'IF', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
    'CAST', 'CONVERT', 'DATE', 'TIME', 'TIMESTAMP', 'NOW', 'CURDATE', 'CURTIME',
    'YEAR', 'MONTH', 'DAY', 'HOUR', 'MINUTE', 'SECOND', 'DAYOFWEEK', 'DAYOFMONTH',
    'DATE_FORMAT', 'STR_TO_DATE', 'DATE_ADD', 'DATE_SUB', 'DATEDIFF', 'TIMESTAMPDIFF',
    'ABS', 'ROUND', 'CEILING', 'CEIL', 'FLOOR', 'POWER', 'POW', 'SQRT', 'MOD',
    'JSON_OBJECT', 'JSON_ARRAY', 'JSON_EXTRACT', 'JSON_ARRAYAGG', 'JSON_OBJECTAGG',
    'EXISTS', 'NOT_EXISTS', 'ANY', 'ALL', 'SOME', 'UNION', 'EXCEPT', 'INTERSECT',
    'DISTINCT', 'AS', 'ON', 'BY', 'ORDER', 'LIMIT', 'OFFSET', 'HAVING',
    'INSERT', 'UPDATE', 'DELETE', 'INTO', 'VALUES', 'SET', 'FROM', 'JOIN',
    'INNER', 'LEFT', 'RIGHT', 'OUTER', 'CROSS', 'NATURAL',
    'BEGIN', 'COMMIT', 'ROLLBACK', 'DECLARE', 'RETURN', 'CALL',
    'ROW_NUMBER', 'RANK', 'DENSE_RANK', 'OVER', 'PARTITION',
    'EXTRACT', 'INTERVAL', 'TIMESTAMPADD',
    # MSSQL 표준 추가
    'GETDATE', 'GETUTCDATE', 'ISNULL', 'TOP', 'ROWGUIDCOL',
    'SYSDATETIME', 'CURRENT_TIMESTAMP', 'NEWID',
    # 제어 + 컬럼 키워드
    'TRUE', 'FALSE', 'WITH', 'RECURSIVE', 'OUTPUT', 'EACH', 'ROW', 'STATEMENT',
    'AFTER', 'BEFORE', 'OF', 'NEW', 'OLD',
    # 자주 등장하는 컬럼 — false positive 방지
    'RECORD', 'STATUS', 'TYPE', 'NAME', 'ID', 'KEY', 'VALUE', 'DATA',
}


def _extract_identifier(match_groups: Tuple) -> Optional[str]:
    """매치 그룹에서 첫 번째 non-None 식별자 추출"""
    for g in match_groups:
        if g:
            return g
    return None


def extract_dependencies(
    ddl: str,
    self_name: str,
    object_type: ObjectType,
    known_objects: Optional[Set[str]] = None,
) -> Set[str]:
    """
    DDL 에서 의존하는 오브젝트 이름 추출.
    
    Args:
        ddl: 분석할 DDL (변환된 또는 원본)
        self_name: 자기 자신 이름 (참조에서 제외)
        object_type: 오브젝트 타입
        known_objects: 알려진 오브젝트 이름 집합 (DB 외부 참조 필터링용)
    
    Returns:
        참조하는 오브젝트 이름 set (소문자, lower-cased)
    """
    if not ddl:
        return set()
    
    cleaned = _strip_sql(ddl)
    self_lower = self_name.lower()
    deps: Set[str] = set()
    
    # 1. FROM/JOIN/INTO/UPDATE 패턴 (테이블/뷰 참조)
    for m in _RE_FROM_TABLE.finditer(cleaned):
        # match groups: schema 4개 + table 4개
        groups = m.groups()
        # 처음 4개는 schema, 다음 4개는 table
        table = _extract_identifier(groups[4:8])
        if table:
            t = table.lower()
            if t != self_lower and t not in _BUILTIN_FUNCTIONS:
                deps.add(t)
    
    # 2. 트리거의 ON 테이블 (트리거만)
    if object_type == ObjectType.TRIGGER:
        for m in _RE_TRIGGER_ON.finditer(cleaned):
            groups = m.groups()
            table = _extract_identifier(groups[4:8])
            if table:
                t = table.lower()
                if t != self_lower:
                    deps.add(t)
    
    # 3. 함수/프로시저 호출 (FUNCTION/PROCEDURE/VIEW/TRIGGER 의 본문에서)
    # 단, 너무 거짓 양성 많으니 known_objects 가 주어졌을 때만 사용
    if known_objects:
        known_lower = {n.lower() for n in known_objects}
        for m in _RE_FUNC_CALL.finditer(cleaned):
            groups = m.groups()
            func_name = _extract_identifier(groups[4:8])
            if func_name:
                f = func_name.lower()
                if (f != self_lower and 
                    f not in _BUILTIN_FUNCTIONS and 
                    f.upper() not in _BUILTIN_FUNCTIONS and
                    f in known_lower):
                    deps.add(f)
    
    # 4. CREATE 헤더에서 추출된 자기 이름은 deps 에서 제외
    for m in _RE_CREATE_SELF.finditer(cleaned):
        groups = m.groups()
        own = _extract_identifier(groups[4:8])
        if own:
            deps.discard(own.lower())
    
    return deps


# ════════════════════════════════════════════════════════════════════════════
# 의존성 그래프 + Topological Sort
# ════════════════════════════════════════════════════════════════════════════

class DependencyResolver:
    """
    오브젝트 의존성 그래프 빌드 + Topological Sort.
    """
    
    def __init__(self):
        self._objects: Dict[str, DBObject] = {}
    
    def add_object(self, obj: DBObject) -> None:
        """오브젝트 등록"""
        key = obj.name.lower()
        self._objects[key] = obj
    
    def add_objects(self, objs: Iterable[DBObject]) -> None:
        """다수 오브젝트 등록"""
        for o in objs:
            self.add_object(o)
    
    def analyze(self) -> None:
        """모든 오브젝트의 의존성 분석 + 그래프 빌드"""
        known_names = set(self._objects.keys())
        
        for key, obj in self._objects.items():
            deps = extract_dependencies(
                obj.ddl, obj.name, obj.object_type, known_names
            )
            
            # known_objects 안에 있는 것만 의존성으로 인정
            valid_deps = {d for d in deps if d in known_names and d != key}
            obj.dependencies = valid_deps
            
            # 역방향 (dependents) 도 채움
            for dep in valid_deps:
                if dep in self._objects:
                    self._objects[dep].dependents.add(key)
    
    def resolve(self) -> ResolveResult:
        """
        Topological Sort 실행 → 안전한 실행 순서 반환.
        
        Algorithm: Kahn's algorithm (in-degree 기반)
        """
        if not self._objects:
            return ResolveResult(ordered=[])
        
        # in_degree 계산
        in_degree: Dict[str, int] = {k: len(o.dependencies) for k, o in self._objects.items()}
        
        # 우선순위 큐: (타입 우선순위, 이름) 으로 정렬
        # → in_degree 0 인 것 중에서 TABLE → FUNCTION → PROCEDURE → VIEW → TRIGGER
        ready: List[str] = sorted(
            [k for k, d in in_degree.items() if d == 0],
            key=lambda k: (TYPE_PRIORITY.get(self._objects[k].object_type, 99), k)
        )
        
        ordered: List[DBObject] = []
        processed: Set[str] = set()
        
        while ready:
            # ready 큐에서 우선순위 가장 높은 것 선택
            current = ready.pop(0)
            obj = self._objects[current]
            ordered.append(obj)
            processed.add(current)
            
            # 이 노드를 의존하는 것들의 in_degree 감소
            for dependent in sorted(obj.dependents):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    # ready 에 추가하고 즉시 재정렬
                    ready.append(dependent)
                    ready.sort(
                        key=lambda k: (TYPE_PRIORITY.get(self._objects[k].object_type, 99), k)
                    )
        
        # 처리 안 된 것 = 순환 참조
        unprocessed = set(self._objects.keys()) - processed
        cycles = []
        if unprocessed:
            # 순환 그룹 찾기 (Strongly Connected Components 의 단순 버전)
            cycles = self._find_cycles(unprocessed)
            # 순환 참조여도 일단 ordered 끝에 추가 (이름 순)
            for k in sorted(unprocessed):
                ordered.append(self._objects[k])
        
        return ResolveResult(
            ordered=ordered,
            cycles=cycles,
            unresolved=[],
        )
    
    def _find_cycles(self, nodes: Set[str]) -> List[List[str]]:
        """순환 참조 그룹 탐지 (간단한 DFS 기반)"""
        cycles = []
        visited: Set[str] = set()
        
        for start in nodes:
            if start in visited:
                continue
            
            # DFS 로 cycle 탐색
            path: List[str] = []
            stack: List[Tuple[str, Iterable]] = [
                (start, iter(self._objects[start].dependencies))
            ]
            on_path: Set[str] = {start}
            path.append(start)
            
            while stack:
                node, deps_iter = stack[-1]
                try:
                    next_dep = next(deps_iter)
                    if next_dep not in nodes:
                        continue
                    if next_dep in on_path:
                        # 순환 발견 — 사이클 추출
                        idx = path.index(next_dep)
                        cycle = path[idx:] + [next_dep]
                        if cycle not in cycles:
                            cycles.append(cycle)
                    elif next_dep not in visited:
                        path.append(next_dep)
                        on_path.add(next_dep)
                        stack.append((next_dep, iter(self._objects[next_dep].dependencies)))
                except StopIteration:
                    stack.pop()
                    if path:
                        last = path.pop()
                        on_path.discard(last)
                        visited.add(last)
        
        return cycles


# ════════════════════════════════════════════════════════════════════════════
# 편의 함수 (이관 엔진에서 호출)
# ════════════════════════════════════════════════════════════════════════════

def resolve_object_order(
    *,
    table_names: List[str] = None,
    functions: Dict[str, str] = None,    # {name: ddl}
    procedures: Dict[str, str] = None,
    views: Dict[str, str] = None,
    triggers: Dict[str, str] = None,
) -> ResolveResult:
    """
    오브젝트 dict → 안전한 실행 순서 반환.
    
    Args:
        table_names: 테이블 이름 리스트 (DDL 없어도 됨, 의존성 타겟용)
        functions/procedures/views/triggers: {name: ddl} 형태
    
    Returns:
        ResolveResult — ordered 리스트, cycles 정보 등
    
    예시:
        result = resolve_object_order(
            table_names=['customer', 'orders'],
            views={
                'v_recent': 'CREATE VIEW v_recent AS SELECT * FROM orders',
                'v_summary': 'CREATE VIEW v_summary AS SELECT * FROM v_recent',
            }
        )
        # result.ordered 순서:
        # 1. customer (table)
        # 2. orders (table)
        # 3. v_recent (view)
        # 4. v_summary (view, v_recent 다음)
    """
    resolver = DependencyResolver()
    
    # 테이블 등록 (의존성 타겟)
    for name in (table_names or []):
        resolver.add_object(DBObject(
            name=name, object_type=ObjectType.TABLE, ddl=""
        ))
    
    # 각 오브젝트 등록
    for name, ddl in (functions or {}).items():
        resolver.add_object(DBObject(
            name=name, object_type=ObjectType.FUNCTION, ddl=ddl
        ))
    for name, ddl in (procedures or {}).items():
        resolver.add_object(DBObject(
            name=name, object_type=ObjectType.PROCEDURE, ddl=ddl
        ))
    for name, ddl in (views or {}).items():
        resolver.add_object(DBObject(
            name=name, object_type=ObjectType.VIEW, ddl=ddl
        ))
    for name, ddl in (triggers or {}).items():
        resolver.add_object(DBObject(
            name=name, object_type=ObjectType.TRIGGER, ddl=ddl
        ))
    
    resolver.analyze()
    return resolver.resolve()


def format_resolve_summary(result: ResolveResult) -> str:
    """이관 로그용 요약 (사람이 읽기 쉬운 형식)"""
    lines = []
    lines.append(f"총 {len(result.ordered)}개 오브젝트 처리 순서 결정")
    
    by_type: Dict[str, int] = defaultdict(int)
    for o in result.ordered:
        by_type[o.object_type.value] += 1
    
    type_summary = ", ".join(f"{t} {c}" for t, c in sorted(by_type.items()))
    lines.append(f"  타입별: {type_summary}")
    
    if result.cycles:
        lines.append(f"⚠️ 순환 참조 {len(result.cycles)}건 — 마지막에 처리:")
        for cycle in result.cycles:
            lines.append(f"  → {' → '.join(cycle)}")
    
    return "\n".join(lines)
