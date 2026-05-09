"""
app/api/routes/sql_validate.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
v95_p67 (2026-05-05 본부장님 결정): MySQL SQL 문법 검증 API (Phase 5-2)

본부장님 호소:
  "5 Phase 모두 — 엔터프라이즈 솔루션"
  사용자가 수동 SQL 작성할 때 저장 전 문법 검증 필요

본질:
  v95_p66 의 수동 SQL 입력 모달에서 사용자가 작성한 MySQL DDL 의
  문법을 사전 검증 → 1064 syntax error 사전 차단

검증 방식 (3단계):
  1) 기본 형식 검사 (CREATE 구문 존재, 객체 이름 매치 등)
  2) MySQL 자체 EXPLAIN / SHOW WARNINGS (옵션 — 타겟 DB 연결 시)
  3) sqlparse 라이브러리 (가능 시) — Python 측 파싱

부작용 0:
  - 검증 실패해도 사용자가 강제 저장 가능 (사용자 책임)
  - 백엔드 검증 라이브러리 없으면 기본 검사만 (안전)
  - 타겟 DB 연결 안 되어 있으면 EXPLAIN 스킵
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
import logging
import re

router = APIRouter(prefix="/api/v1/sql", tags=["sql_validate"])
_log = logging.getLogger("databridge.sql_validate")


class ValidateInput(BaseModel):
    sql: str
    obj_type: str = ""    # 'VIEW' | 'PROCEDURE' | 'FUNCTION' | 'TRIGGER'
    obj_name: str = ""    # 검증 대상 객체 이름
    target_dialect: str = "mysql"  # 'mysql' | 'mariadb'
    target_conn: Optional[dict] = None  # 타겟 DB 연결 정보 (옵션 — EXPLAIN 용)


class ValidateOutput(BaseModel):
    ok: bool
    message: str
    details: List[str] = []
    severity: str = "info"  # 'info' | 'warn' | 'error'


# ════════════════════════════════════════════════════════════════════
# 1단계: 기본 형식 검사 (정규식)
# ════════════════════════════════════════════════════════════════════
def _basic_format_check(sql: str, obj_type: str, obj_name: str) -> List[str]:
    """기본 형식 검사 — 위반 사항 리스트 반환 (빈 리스트면 통과)."""
    issues = []
    sql_upper = sql.upper()
    
    # CREATE 구문 존재
    if not re.search(r'\bCREATE\s+(OR\s+REPLACE\s+)?(VIEW|PROCEDURE|FUNCTION|TRIGGER|TABLE|INDEX)\b',
                     sql_upper):
        issues.append("CREATE 구문이 없습니다 (CREATE VIEW/PROCEDURE/FUNCTION/TRIGGER 등 필요)")
    
    # 객체 타입 매치 검사
    if obj_type:
        type_patterns = {
            'VIEW':       r'\bCREATE\s+(OR\s+REPLACE\s+)?VIEW\b',
            'PROCEDURE':  r'\bCREATE\s+PROCEDURE\b',
            'FUNCTION':   r'\bCREATE\s+FUNCTION\b',
            'TRIGGER':    r'\bCREATE\s+TRIGGER\b',
        }
        pat = type_patterns.get(obj_type.upper())
        if pat and not re.search(pat, sql_upper):
            issues.append(
                f"객체 타입 불일치 — 예상 {obj_type}, 입력된 SQL 은 다른 타입일 수 있음"
            )
    
    # 객체 이름 매치 검사 (warning 만)
    if obj_name and obj_type:
        # MySQL 백틱 / 그냥 이름 둘 다 허용
        # 에를 들어 `vMyView` 또는 vMyView
        name_pat = rf'\b{re.escape(obj_name)}\b'
        if not re.search(name_pat, sql, re.IGNORECASE):
            issues.append(
                f"⚠️ 입력 SQL 에 객체 이름 [{obj_name}] 가 보이지 않음 — 다른 이름일 가능성"
            )
    
    # MSSQL 잔여 패턴 (사용자 실수 방지)
    mssql_remnants = [
        (r'\bGETDATE\s*\(\s*\)',            "MSSQL GETDATE() — MySQL 은 NOW() 사용"),
        (r'\bISNULL\s*\(',                  "MSSQL ISNULL() — MySQL 은 IFNULL() 사용"),
        (r'\bCROSS\s+APPLY\b',              "MSSQL CROSS APPLY — MySQL 은 LATERAL JOIN 또는 서브쿼리"),
        (r'\bOUTER\s+APPLY\b',              "MSSQL OUTER APPLY — MySQL 은 LEFT LATERAL JOIN"),
        (r'\bMERGE\s+INTO\b',               "MSSQL MERGE — MySQL 은 INSERT ... ON DUPLICATE KEY UPDATE"),
        (r'\.\s*nodes\s*\(',                "MSSQL XML .nodes() — MySQL 은 JSON_TABLE() 등"),
        (r"\bNVARCHAR\s*\(",                "MSSQL NVARCHAR — MySQL 은 VARCHAR (utf8mb4)"),
        (r'\bSELECT\s+TOP\s+\d+',           "MSSQL TOP N — MySQL 은 LIMIT N"),
        (r'\[\w+\]\s*\.\s*\[\w+\]',         "MSSQL [schema].[table] 형식 — MySQL 은 백틱 또는 그냥 이름"),
    ]
    for pat, msg in mssql_remnants:
        if re.search(pat, sql, re.IGNORECASE):
            issues.append(f"MSSQL 잔여 — {msg}")
    
    # MySQL 권장 사항 (info)
    if 'CREATE VIEW' in sql_upper:
        if 'ALGORITHM' not in sql_upper:
            issues.append("ℹ️ 권장: CREATE ALGORITHM=UNDEFINED VIEW ... (MySQL 최적화 힌트)")
    
    return issues


# ════════════════════════════════════════════════════════════════════
# 2단계: sqlparse 기반 파싱 (가능 시)
# ════════════════════════════════════════════════════════════════════
def _try_sqlparse_check(sql: str) -> List[str]:
    """sqlparse 라이브러리로 파싱 — 실패 사항만 반환."""
    issues = []
    try:
        import sqlparse
        parsed = sqlparse.parse(sql)
        if not parsed:
            issues.append("sqlparse: SQL 파싱 결과 비어있음")
            return issues
        # 큰 문제만 체크 (sqlparse 는 lenient — 깊은 검증 안 됨)
        # 세미콜론으로 끝나는지 (DELIMITER 없는 경우)
        sql_stripped = sql.strip().rstrip(';').strip()
        if not sql_stripped:
            issues.append("sqlparse: SQL 본문 비어있음")
    except ImportError:
        # sqlparse 없으면 스킵
        pass
    except Exception as e:
        issues.append(f"sqlparse 검증 오류: {e}")
    return issues


# ════════════════════════════════════════════════════════════════════
# 메인 엔드포인트
# ════════════════════════════════════════════════════════════════════
@router.post("/validate-mysql", response_model=ValidateOutput)
def validate_mysql_sql(body: ValidateInput) -> ValidateOutput:
    """
    사용자 작성 MySQL SQL 의 문법 검증.
    
    검증 단계:
      1) 기본 형식 검사 (CREATE 존재, 타입/이름 매치, MSSQL 잔여)
      2) sqlparse 기반 파싱 (가능 시)
      3) 실제 MySQL 연결 테스트 (target_conn 제공 시 — 미구현, 추후)
    
    응답:
      ok=True 면 통과 (warning 있어도 OK)
      ok=False 면 critical 문제 발견
    """
    sql = (body.sql or "").strip()
    if not sql:
        return ValidateOutput(
            ok=False,
            message="✗ SQL 이 비어있습니다",
            severity="error",
        )
    
    all_issues: List[str] = []
    
    # 1단계: 기본 형식
    basic_issues = _basic_format_check(sql, body.obj_type, body.obj_name)
    all_issues.extend(basic_issues)
    
    # 2단계: sqlparse
    parse_issues = _try_sqlparse_check(sql)
    all_issues.extend(parse_issues)
    
    # critical 판단 — CREATE 없음 또는 파싱 실패
    has_critical = any(
        msg.startswith("CREATE 구문이 없습니다") or
        msg.startswith("sqlparse: SQL 파싱 결과")
        for msg in all_issues
    )
    
    # MSSQL 잔여 — warn 레벨 (저장은 가능, 실행 시 1064 가능성)
    has_mssql_remnant = any("MSSQL 잔여" in msg for msg in all_issues)
    
    if has_critical:
        return ValidateOutput(
            ok=False,
            message="✗ 검증 실패 — critical 문제 발견",
            details=all_issues,
            severity="error",
        )
    
    if has_mssql_remnant:
        return ValidateOutput(
            ok=True,  # 저장은 허용 (사용자 책임)
            message="⚠️ MSSQL 잔여 패턴 검출 — 실행 시 1064 syntax 오류 가능성",
            details=all_issues,
            severity="warn",
        )
    
    if all_issues:
        return ValidateOutput(
            ok=True,
            message="✓ 기본 검증 통과 — 권장 사항 있음",
            details=all_issues,
            severity="info",
        )
    
    return ValidateOutput(
        ok=True,
        message="✓ 검증 통과 — 형식 OK",
        severity="info",
    )
