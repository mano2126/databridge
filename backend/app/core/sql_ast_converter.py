"""
app/core/sql_ast_converter.py
sqlglot 기반 SQL 방언 변환기.

역할:
  기존 regex 기반 변환기(convert_sql)의 1차 변환 엔진으로 동작.
  파싱 성공 → AST 트랜스파일 반환 + 변환 노트.
  파싱 실패 → None 반환 → 호출부가 regex 폴백 경로 진행.

장점:
  - 복합 CTE, 중첩 서브쿼리, 함수 시그니처 같은 구문을 정확히 처리
  - 화이트스페이스·대소문자에 민감하지 않음
  - 방언별 예약어 · 함수명 변환을 라이브러리가 관리

한계:
  - sqlglot이 모든 DB 방언을 100% 지원하지는 않음
  - MSSQL의 SWITCHOFFSET, hierarchyid, datetimeoffset 같은 특수 타입은 별도 후처리 필요
  - 따라서 하이브리드 전략이 필수

의존성:
  pip install sqlglot>=20.0.0
  (미설치시 graceful degrade — is_available()이 False, convert_via_ast는 None 반환)
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger("databridge.sql_ast")

try:
    import sqlglot
    from sqlglot import exp
    _HAS_SQLGLOT = True
except ImportError:
    _HAS_SQLGLOT = False
    sqlglot = None  # type: ignore
    exp = None      # type: ignore
    logger.warning(
        "sqlglot 미설치 — SQL 변환기는 regex 전용 모드로 동작. "
        "'pip install sqlglot' 권장."
    )


# ── DB 방언 → sqlglot 방언 키 매핑 ───────────────────────
# sqlglot이 이해하는 dialect 이름으로 변환
_DIALECT_MAP = {
    "mysql":      "mysql",
    "mariadb":    "mysql",       # 호환
    "aurora":     "mysql",
    "cloudsql":   "mysql",
    "tidb":       "mysql",
    "mssql":      "tsql",        # sqlglot은 TSQL로 부름
    "sqlserver":  "tsql",
    "azure":      "tsql",
    "postgresql": "postgres",
    "oracle":     "oracle",
    "sqlite":     "sqlite",
    "redshift":   "redshift",
    "snowflake":  "snowflake",
    "bigquery":   "bigquery",
    "clickhouse": "clickhouse",
    "duckdb":     "duckdb",
    "hana":       "hana",
}


def is_available() -> bool:
    """sqlglot 사용 가능 여부"""
    return _HAS_SQLGLOT


def dialect_for(db: str) -> Optional[str]:
    """DataBridge DB 키 → sqlglot dialect 이름. 미지원이면 None."""
    return _DIALECT_MAP.get((db or "").lower())


def convert_via_ast(
    sql: str,
    src_db: str,
    tgt_db: str,
    *,
    pretty: bool = True,
) -> Optional[dict]:
    """
    sqlglot을 사용해 SQL을 변환.

    Returns:
      성공 시: {
        "converted": str,        # 변환된 SQL
        "engine": "ast",
        "src_dialect": str,      # sqlglot이 사용한 dialect
        "tgt_dialect": str,
        "statements": int,       # 처리한 문장 수
        "warnings": list[str],   # AST 변환 중 주의사항
        "notes": list[str],      # 변환 로그
      }
      실패 시: None (파싱 불가 / sqlglot 미설치 / 방언 미매핑)
    """
    if not _HAS_SQLGLOT:
        return None
    if not sql or not sql.strip():
        return None

    src = dialect_for(src_db)
    tgt = dialect_for(tgt_db)
    if not src or not tgt:
        return None  # 매핑 안 된 방언 → 호출부가 regex 폴백

    notes: list[str] = []
    warnings: list[str] = []

    # 1. 파싱 — 여러 문장이 세미콜론으로 연결된 경우도 처리
    try:
        parsed = sqlglot.parse(sql, read=src)
    except Exception as e:
        # 파싱 실패 → 규식 폴백 경로로
        logger.debug("AST 파싱 실패 [%s→%s]: %s", src_db, tgt_db, str(e)[:120])
        return None

    if not parsed:
        return None

    # 2. 변환 — 각 문장 개별 처리
    converted_parts: list[str] = []
    statements = 0
    for tree in parsed:
        if tree is None:
            continue
        statements += 1
        try:
            # AST 레벨 후처리 훅 (여기서 DataBridge 특화 규칙 적용 가능)
            tree = _apply_tree_transforms(tree, src, tgt, notes, warnings,
                                          original_sql=sql)
            out = tree.sql(dialect=tgt, pretty=pretty)
            converted_parts.append(out)
        except Exception as e:
            # 개별 문장 변환 실패 시 전체 실패로 간주 (부분 변환은 위험)
            logger.debug("AST 트랜스파일 실패: %s", str(e)[:120])
            return None

    if not converted_parts:
        return None

    converted = ";\n\n".join(converted_parts)
    # 마지막 세미콜론 보장
    if not converted.rstrip().endswith(";"):
        converted = converted.rstrip() + ";"

    return {
        "converted": converted,
        "engine": "ast",
        "src_dialect": src,
        "tgt_dialect": tgt,
        "statements": statements,
        "warnings": warnings,
        "notes": notes,
    }


# ── AST 후처리 훅 ──────────────────────────────────────────

def _apply_tree_transforms(tree, src: str, tgt: str,
                           notes: list, warnings: list,
                           original_sql: str = ""):
    """
    sqlglot이 기본 제공하지 않는 DataBridge 특화 변환/검증을 AST 레벨에서 처리.

    original_sql: sqlglot이 이미 파싱하면서 변환한 상태라 AST로는 감지 불가한
                  구문(예: CROSS APPLY → LATERAL JOIN 자동 변환)은 원본 텍스트에서 감지.
    """
    # ── MSSQL → MySQL 방향 ──────────────────────────────
    if src == "tsql" and tgt == "mysql":
        # rowversion/timestamp 컬럼 (완전 다른 의미)
        for col_def in tree.find_all(exp.ColumnDef):
            kind = col_def.args.get("kind")
            if kind and str(kind).lower() in ("rowversion", "timestamp"):
                warnings.append(
                    f"컬럼 '{col_def.name}': MSSQL rowversion/timestamp는 "
                    f"자동 증가 행버전. MySQL에서는 BIGINT 또는 BINARY(8)로 수동 매핑 권장."
                )

        # IDENTITY 컬럼
        for col_def in tree.find_all(exp.ColumnDef):
            for c in col_def.find_all(exp.GeneratedAsIdentityColumnConstraint):
                warnings.append(
                    f"컬럼 '{col_def.name}': IDENTITY(n,m) → AUTO_INCREMENT 변환됨. "
                    f"시작값/증분 세밀 제어는 MySQL에서 불가."
                )

        # OUTPUT 절 (MSSQL 고유 — MySQL은 미지원)
        for stmt in tree.find_all((exp.Update, exp.Delete, exp.Insert)):
            if stmt.args.get("returning"):
                warnings.append(
                    "OUTPUT/RETURNING 절: MySQL은 DML 결과 반환 미지원. "
                    "별도 SELECT로 분리하거나 애플리케이션에서 rowcount 사용."
                )

        # CROSS APPLY / OUTER APPLY — 원본 SQL에서 직접 감지
        # (sqlglot이 이미 LATERAL로 변환해버리기 때문)
        orig_upper = (original_sql or "").upper()
        if "CROSS APPLY" in orig_upper or "OUTER APPLY" in orig_upper:
            warnings.append(
                "CROSS APPLY / OUTER APPLY는 MySQL에서 직접 지원되지 않음. "
                "sqlglot이 LATERAL JOIN (MySQL 8.0.14+)으로 변환 — MySQL 버전 확인 필요. "
                "구 버전 MySQL에서는 서브쿼리 또는 상관 서브쿼리로 재작성 권장."
            )

        # PIVOT
        for p in tree.find_all(exp.Pivot):
            warnings.append(
                "PIVOT: MySQL 미지원. sqlglot이 CASE WHEN으로 부분 변환할 수 있으나 "
                "결과 검토 필수. 큰 pivot은 애플리케이션 레벨 처리 권장."
            )
            break

        # MERGE INTO
        for m in tree.find_all(exp.Merge):
            warnings.append(
                "MERGE INTO: MySQL 미지원. "
                "INSERT ... ON DUPLICATE KEY UPDATE 패턴으로 재작성 필요."
            )
            break

        # TOP → LIMIT 변환 로그
        if any(True for _ in tree.find_all(exp.Limit)):
            notes.append("TOP n → LIMIT n 변환 (AST)")

    # ── MySQL → MSSQL 방향 ──────────────────────────────
    if src == "mysql" and tgt == "tsql":
        # AUTO_INCREMENT → IDENTITY
        for col_def in tree.find_all(exp.ColumnDef):
            for c in col_def.constraints or []:
                if "AUTO_INCREMENT" in str(c).upper():
                    notes.append(
                        f"컬럼 '{col_def.name}': AUTO_INCREMENT → IDENTITY(1,1) 변환"
                    )

        # ON DUPLICATE KEY UPDATE
        if any("ON DUPLICATE KEY" in str(n).upper() for n in tree.find_all(exp.Insert)):
            warnings.append(
                "INSERT ... ON DUPLICATE KEY UPDATE: MSSQL 미지원. "
                "MERGE INTO 패턴으로 재작성 필요 (sqlglot이 시도하나 검토 필수)."
            )

        # LIMIT → OFFSET FETCH 변환 로그
        if any(True for _ in tree.find_all(exp.Limit)):
            notes.append("LIMIT n → TOP n / OFFSET FETCH 변환 (AST)")

        # COUNT(*) → COUNT_BIG(*) sqlglot이 자동 변환
        has_count_big = any(
            isinstance(f, exp.Count) and f.args.get("big")
            for f in tree.find_all(exp.Count)
        )
        if has_count_big:
            notes.append("COUNT(*) → COUNT_BIG(*) 자동 승격 (20억 행 초과 대비)")

    # ── PostgreSQL 대응 ──────────────────────────────
    if src == "postgres" or tgt == "postgres":
        sql_str = str(tree).upper()
        if "->>" in sql_str or (" -> " in sql_str and ("JSON" in sql_str or "JSONB" in sql_str)):
            if tgt != "postgres":
                warnings.append(
                    "PostgreSQL JSON 연산자 (->, ->>)는 타겟 방언에서 지원 안 될 수 있음. "
                    "JSON_EXTRACT, JSON_VALUE 같은 함수로 수동 변환 검토."
                )

        if "ARRAY_AGG" in sql_str and tgt != "postgres":
            warnings.append(
                "PostgreSQL ARRAY_AGG는 MySQL/MSSQL 미지원. "
                "STRING_AGG/GROUP_CONCAT으로 변환하거나 JSON 배열로 우회."
            )

    # ── Oracle 대응 ──────────────────────────────────
    if src == "oracle":
        sql_str = str(tree).upper()
        if "CONNECT BY" in sql_str:
            warnings.append(
                "Oracle CONNECT BY (계층형 쿼리): sqlglot이 WITH RECURSIVE CTE로 변환 시도하나 "
                "LEVEL, PRIOR 등 의사컬럼은 수동 매핑 필요."
            )
        if "SYSDATE" in sql_str and tgt != "oracle":
            notes.append("SYSDATE → CURRENT_TIMESTAMP 변환")
        if "DUAL" in sql_str and tgt != "oracle":
            warnings.append(
                "Oracle DUAL 테이블 참조 감지. 타겟 DB에서 FROM DUAL 제거 필요할 수 있음."
            )

    # ── 공통: 시간대 ─────────────────────────────────
    sql_str = str(tree)
    if "AT TIME ZONE" in sql_str.upper():
        notes.append("AT TIME ZONE 구문 감지 — 타겟 방언 시간대 지원 방식 확인 필요")

    return tree


# ── 공개 편의 API ─────────────────────────────────────────

def parse_check(sql: str, dialect: str) -> tuple[bool, str]:
    """
    주어진 SQL이 해당 방언으로 파싱 가능한지 검사.
    Validate 화면 / CLI 진단용.

    Returns: (success, error_message)
    """
    if not _HAS_SQLGLOT:
        return False, "sqlglot 미설치"
    d = dialect_for(dialect) or dialect
    try:
        sqlglot.parse(sql, read=d)
        return True, ""
    except Exception as e:
        return False, str(e)[:200]
