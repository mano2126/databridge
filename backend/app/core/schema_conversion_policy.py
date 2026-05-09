"""
schema_conversion_policy.py — Phase E-2 (2026-04-24)

MSSQL → MySQL 변환 시 스키마.테이블 표기를 어떻게 변환할지 결정하는 정책 모듈.

문제:
  MSSQL 은 [schema].[table] 형식 (예: customer.profile)
  MySQL 은 이걸 database.table 로 해석 → Unknown database 에러

  AI 가 매 변환마다 다른 전략을 씀:
    - customer.profile → customer__profile  (이중 언더스코어)
    - customer.profile → customer_profile   (단일 언더스코어)
    - customer.profile → profile            (스키마 제거)
    - customer.profile → `customer`.`profile` (database 로 해석)
  
  한 Job 안에서 4가지가 섞여서 나와 테이블 생성/참조 일치 실패.

해결:
  Profile (Connector) 에 schema_conversion 필드 추가.
  AI 프롬프트에 "반드시 이 규칙만 사용하라" 주입.
  AST 사후 검증으로 위반 탐지.

전략:
  - "drop":       스키마 접두사 완전 제거 (가장 단순, 단일 DB 권장)
  - "underscore": schema.table → schema_table (단일 언더스코어)
  - "database":   schema 를 별도 DB 로 유지 (멀티 DB 환경)

기본값: "underscore" (오늘 이관에서 이게 가장 안정적이었음)
"""

from __future__ import annotations
import re
import logging
from typing import Optional, Literal

_log = logging.getLogger("databridge.schema_policy")

SchemaStrategy = Literal["drop", "underscore", "database"]
DEFAULT_STRATEGY: SchemaStrategy = "underscore"


# ════════════════════════════════════════════════════════════════════════════
# 프롬프트 주입용 규칙 텍스트
# ════════════════════════════════════════════════════════════════════════════

def build_schema_rule_prompt(strategy: SchemaStrategy, src_db: str, tgt_db: str) -> str:
    """
    AI 프롬프트에 주입할 스키마 변환 규칙 텍스트 생성.
    AI 에게 "반드시 이 규칙만 사용하라" 강제.
    """
    # MSSQL 타겟 등 스키마 개념 있는 경우 적용 제외
    if tgt_db in ("mssql", "azure", "sqlserver"):
        return ""  # MSSQL 타겟은 스키마 그대로 사용

    # MySQL 타겟 기준 규칙
    if strategy == "drop":
        return (
            "\n[CRITICAL SCHEMA RULE — MUST FOLLOW EXACTLY]\n"
            "The source uses schema.table notation (e.g., customer.profile).\n"
            "MUST convert ALL schema-qualified names by REMOVING the schema prefix:\n"
            "  customer.profile   → profile\n"
            "  credit.contract    → contract\n"
            "  collection.delinquency → delinquency\n"
            "  ref.product        → product\n"
            "Do NOT use customer_profile, `customer`.`profile`, or customer__profile.\n"
            "Do NOT keep the schema prefix.\n"
            "Do NOT wrap names in backticks unless the name contains reserved words.\n"
        )
    elif strategy == "underscore":
        return (
            "\n[CRITICAL SCHEMA RULE — MUST FOLLOW EXACTLY]\n"
            "The source uses schema.table notation (e.g., customer.profile).\n"
            "MUST convert ALL schema-qualified names using SINGLE UNDERSCORE:\n"
            "  customer.profile       → customer_profile\n"
            "  credit.contract        → credit_contract\n"
            "  collection.delinquency → collection_delinquency\n"
            "  ref.product            → ref_product\n"
            "Do NOT use:\n"
            "  - customer__profile  (double underscore — WRONG)\n"
            "  - profile            (schema removed — WRONG)\n"
            "  - `customer`.`profile` (database qualifier — WRONG)\n"
            "Apply this to BOTH table references AND the object name itself:\n"
            "  CREATE PROCEDURE customer.sp_get → CREATE PROCEDURE customer_sp_get\n"
            "  CREATE VIEW credit.v_active → CREATE VIEW credit_v_active\n"
        )
    elif strategy == "database":
        return (
            "\n[CRITICAL SCHEMA RULE — MUST FOLLOW EXACTLY]\n"
            "The source uses schema.table notation. In MySQL each schema becomes a database.\n"
            "Keep schema-qualified references AS-IS with backticks:\n"
            "  customer.profile → `customer`.`profile`\n"
            "  credit.contract  → `credit`.`contract`\n"
            "Assume databases customer, credit, collection, ref exist on target.\n"
            "Do NOT merge schema into table name.\n"
            "Do NOT remove schema prefix.\n"
        )
    return ""


# ════════════════════════════════════════════════════════════════════════════
# 사후 검증 + 자동 수정
# ════════════════════════════════════════════════════════════════════════════

def enforce_schema_strategy(
    sql: str,
    strategy: SchemaStrategy,
    known_schemas: Optional[list] = None,
) -> tuple[str, list]:
    """
    AI 가 낸 SQL 에서 스키마 규칙 위반을 찾아 자동 수정.
    
    Args:
        sql: AI 가 생성한 SQL 문
        strategy: 적용할 변환 전략
        known_schemas: 알려진 소스 스키마 이름들 (예: ["customer", "credit", "collection", "ref"])
                       None 이면 일반적인 이름 사용
    
    Returns:
        (수정된 SQL, 수정 내역 리스트)
    """
    if not sql:
        return sql, []
    
    if known_schemas is None:
        known_schemas = ["customer", "credit", "collection", "ref", "settlement", "config"]
    
    fixes = []
    result = sql
    
    if strategy == "underscore":
        # 이중 언더스코어 → 단일 언더스코어
        for schema in known_schemas:
            pattern = rf'\b{schema}__(\w+)'
            replacement = rf'{schema}_\1'
            new_result, count = re.subn(pattern, replacement, result)
            if count > 0:
                result = new_result
                fixes.append(f"{schema}__x → {schema}_x ({count}곳)")
        
        # backtick 감싼 `schema`.`table` → schema_table
        for schema in known_schemas:
            pattern = rf'`{schema}`\.`(\w+)`'
            replacement = rf'`{schema}_\1`'  # v90.61: 결과도 backtick 감싸 일관성 유지
            new_result, count = re.subn(pattern, replacement, result)
            if count > 0:
                result = new_result
                fixes.append(f"`{schema}`.`x` → `{schema}_x` ({count}곳)")
        
        # ★ v90.61 신규: schema 만 backtick `schema`.name → schema_name
        # 본부장님 환경 핵심 케이스 — AI 가 자주 이 패턴으로 만듦.
        # 예: `collection`.fn_delinq_stage → collection_fn_delinq_stage
        for schema in known_schemas:
            pattern = rf'`{schema}`\.(\w+)'
            replacement = rf'`{schema}_\1`'  # 결과는 backtick 으로 안전하게 감쌈
            new_result, count = re.subn(pattern, replacement, result)
            if count > 0:
                result = new_result
                fixes.append(f"`{schema}`.x → `{schema}_x` ({count}곳) [v90.61]")
        
        # ★ v90.61 신규: name 만 backtick schema.`name` → schema_name
        for schema in known_schemas:
            pattern = rf'\b{schema}\.`(\w+)`'
            replacement = rf'`{schema}_\1`'
            new_result, count = re.subn(pattern, replacement, result)
            if count > 0:
                result = new_result
                fixes.append(f"{schema}.`x` → `{schema}_x` ({count}곳) [v90.61]")
        
        # ★ v90.61 신규: 대괄호 [schema].[name] (MSSQL 잔재) → schema_name
        for schema in known_schemas:
            pattern = rf'\[{schema}\]\.\[(\w+)\]'
            replacement = rf'`{schema}_\1`'
            new_result, count = re.subn(pattern, replacement, result, flags=re.IGNORECASE)
            if count > 0:
                result = new_result
                fixes.append(f"[{schema}].[x] → `{schema}_x` ({count}곳) [v90.61]")
        
        # 그냥 schema.table (backtick 없음) → schema_table
        for schema in known_schemas:
            pattern = rf'\b{schema}\.(\w+)'
            replacement = rf'{schema}_\1'
            new_result, count = re.subn(pattern, replacement, result)
            if count > 0:
                result = new_result
                fixes.append(f"{schema}.x → {schema}_x ({count}곳)")
    
    elif strategy == "drop":
        # 모든 schema.table / `schema`.`table` / schema__table 에서 스키마 제거
        for schema in known_schemas:
            # `schema`.`table`
            pattern = rf'`{schema}`\.`(\w+)`'
            new_result, count = re.subn(pattern, r'`\1`', result)
            if count > 0:
                result = new_result
                fixes.append(f"`{schema}`.`x` → `x` ({count}곳)")
            
            # ★ v90.61 신규: `schema`.name (schema 만 backtick)
            pattern = rf'`{schema}`\.(\w+)'
            new_result, count = re.subn(pattern, r'\1', result)
            if count > 0:
                result = new_result
                fixes.append(f"`{schema}`.x → x ({count}곳) [v90.61]")
            
            # ★ v90.61 신규: schema.`name` (name 만 backtick)
            pattern = rf'\b{schema}\.`(\w+)`'
            new_result, count = re.subn(pattern, r'`\1`', result)
            if count > 0:
                result = new_result
                fixes.append(f"{schema}.`x` → `x` ({count}곳) [v90.61]")
            
            # ★ v90.61 신규: [schema].[name]
            pattern = rf'\[{schema}\]\.\[(\w+)\]'
            new_result, count = re.subn(pattern, r'`\1`', result, flags=re.IGNORECASE)
            if count > 0:
                result = new_result
                fixes.append(f"[{schema}].[x] → `x` ({count}곳) [v90.61]")
            
            # schema.table (no backtick)
            pattern = rf'\b{schema}\.(\w+)'
            new_result, count = re.subn(pattern, r'\1', result)
            if count > 0:
                result = new_result
                fixes.append(f"{schema}.x → x ({count}곳)")
            
            # schema_table (단일 언더스코어)
            pattern = rf'\b{schema}_(\w+)'
            new_result, count = re.subn(pattern, r'\1', result)
            if count > 0:
                result = new_result
                fixes.append(f"{schema}_x → x ({count}곳)")
    
    return result, fixes


# ════════════════════════════════════════════════════════════════════════════
# 전략 추출 (Job / Profile 설정에서)
# ════════════════════════════════════════════════════════════════════════════

def get_strategy_from_job(job: dict) -> SchemaStrategy:
    """Job 설정에서 스키마 변환 전략 추출 (없으면 기본값)"""
    s = (job.get("schema_conversion") or "").strip().lower()
    if s in ("drop", "underscore", "database"):
        return s  # type: ignore
    return DEFAULT_STRATEGY


def get_known_schemas_from_job(job: dict) -> list:
    """Job 에서 소스 스키마 목록 추출"""
    schemas = job.get("known_schemas")
    if isinstance(schemas, list) and schemas:
        return schemas
    # 객체 목록에서 추론
    objects = job.get("objects", {})
    all_names = []
    for _type, items in objects.items():
        if isinstance(items, list):
            all_names.extend(items)
    tables = job.get("tables", [])
    if isinstance(tables, list):
        all_names.extend(tables)
    
    # schema.name 형식에서 schema 부분만 추출
    schemas_found = set()
    for name in all_names:
        if isinstance(name, str) and '.' in name:
            schemas_found.add(name.split('.')[0])
    
    # ════════════════════════════════════════════════════════════
    # v95_p23b (2026-05-03 본부장님 본질 처방): underscore PascalCase 추론
    # ════════════════════════════════════════════════════════════
    # 본부장님 환경: "1개씩 이관" 시 'HumanResources_Employee' 형식 입력
    #               → '.' 분리 못 함 → schemas_found 빈 상태
    # 처방: PascalCase + underscore 패턴 매치하여 schema 추론
    #       AdventureWorks/Northwind/WideWorldImporters 같은 표준 DB 동작
    #
    # 안전성 (캐피탈사 snake_case 영향 0):
    #   - 'customer_profile' (snake_case) → PascalCase 정규식 매치 안 됨
    #   - 'HumanResources_Employee' (PascalCase) → 매치, 'HumanResources' 추출
    if not schemas_found:
        import re as _re
        for _name in all_names:
            if not isinstance(_name, str) or '.' in _name:
                continue
            # PascalCase: [A-Z][a-zA-Z0-9]+ + underscore + [A-Z][a-zA-Z0-9_]+
            _m = _re.match(r'^([A-Z][a-zA-Z0-9]+)_[A-Z][a-zA-Z0-9_]+$', _name)
            if _m:
                schemas_found.add(_m.group(1))
    # ────────────────────────────────────────────────────────────
    
    if schemas_found:
        return sorted(schemas_found)
    
    # fallback: 일반적인 금융권 이름
    return ["customer", "credit", "collection", "ref", "settlement", "config"]


# ════════════════════════════════════════════════════════════════════════
# v90.48 — 테이블 이름 매핑 (테이블 이관 흐름에서 사용)
# ════════════════════════════════════════════════════════════════════════
# 본부장님 보고: 테이블 이관 시엔 'profile'로 평탄화되는데, 객체 변환은 
# 'customer_profile' 로 schema 결합 → 1146 테이블 없음 오류 187회.
# 해결: 동일 정책으로 테이블 이름도 변환.
# ════════════════════════════════════════════════════════════════════════

def map_table_name(
    src_schema: str,
    bare_name: str,
    strategy: SchemaStrategy = "underscore",
) -> str:
    """
    소스 schema + bare 테이블 이름 → 타겟 테이블 이름.
    
    예시 (strategy="underscore"):
        ("customer", "profile") → "customer_profile"
        ("credit", "contract")  → "credit_contract"
        ("dbo", "tag")          → "tag"           # dbo 는 default schema 라 결합 안 함
        ("",      "tag")        → "tag"
    
    예시 (strategy="drop"):
        ("customer", "profile") → "profile"       # 접두어 제거
    
    예시 (strategy="database"):
        ("customer", "profile") → "profile"       # 별도 DB 사용 가정 (이름 변환 없음)
    """
    bare = (bare_name or "").strip()
    sch = (src_schema or "").strip()
    
    # 결합 안 하는 케이스: 빈 schema, dbo (MSSQL default), 또는 이미 schema 가 결합된 이름
    if not sch or sch.lower() == "dbo":
        return bare
    if not bare:
        return bare
    
    # bare 가 이미 schema_ 접두어를 가지고 있으면 중복 방지
    if bare.lower().startswith(sch.lower() + "_"):
        return bare
    
    if strategy == "underscore":
        return f"{sch}_{bare}"
    elif strategy == "drop":
        return bare
    elif strategy == "database":
        # 별도 DB 환경 — 이름은 그대로 (DB 이름이 schema 역할)
        return bare
    return bare


def build_table_name_map(
    src_schema_map: dict,
    strategy: SchemaStrategy = "underscore",
) -> dict:
    """
    {bare_table_name: schema_name} 형식의 src_schema_map 을 받아
    {bare_name: target_name} 매핑 dict 반환.
    
    Example:
        src_schema_map = {"profile": "customer", "contract": "credit", "tag": "dbo"}
        strategy = "underscore"
        → {"profile": "customer_profile", "contract": "credit_contract", "tag": "tag"}
    """
    result = {}
    for bare, schema in (src_schema_map or {}).items():
        result[bare] = map_table_name(schema or "", bare, strategy)
    return result
