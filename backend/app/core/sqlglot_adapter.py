"""
DataBridge SQLGlot Adapter — Layer 3 (격리, 선택적)
====================================================

본부장님 6번째 본질 통찰 (2026-05-10):
  "SQLGlot 에 너무 디펜던트 해지는 거 아닐까?"

격리 원칙:
  - SQLGlot 없어도 DataBridge 작동 (try/except ImportError)
  - 결과는 항상 ConversionResult 표준 스키마로 반환
  - 실패 시 None 반환 → Layer 4 (AI) 로 위임
  - SQLGlot 결과는 Layer 2 (Rule Engine) 에 학습됨 (의존성 시간 갈수록 ↓)

dialect 매핑:
  DataBridge   →  SQLGlot
  ---------    ----------
  mssql           tsql
  azure           tsql
  sqlserver       tsql
  mysql           mysql
  aurora          mysql
  mariadb         mysql
  tidb            mysql
  cloudsql        mysql

골격 상태 (2026-05-10):
  - 인터페이스 + dialect 매핑 완성
  - 실제 SQLGlot 호출은 Phase 1 (다음 세션) 본부장님 PoC 검증 후
  - 검증 대상: 본부장님 ufnGetContactInformation
"""
from __future__ import annotations
import logging
from typing import Optional, Any

_log = logging.getLogger("databridge.sqlglot_adapter")


# DataBridge dialect → SQLGlot dialect 매핑
_DIALECT_MAP = {
    "mssql": "tsql",
    "azure": "tsql",
    "sqlserver": "tsql",
    "mysql": "mysql",
    "aurora": "mysql",
    "mariadb": "mysql",
    "tidb": "mysql",
    "cloudsql": "mysql",
    "postgres": "postgres",
    "postgresql": "postgres",
    "oracle": "oracle",
}


class SQLGlotAdapter:
    """SQLGlot 격리 호출 어댑터."""

    def __init__(self):
        self._sqlglot_available = self._check_availability()

    def _check_availability(self) -> bool:
        """SQLGlot 라이브러리 설치 여부 확인."""
        try:
            import sqlglot  # noqa
            return True
        except ImportError:
            _log.info("[SQLGlot] 라이브러리 미설치 — Layer 3 비활성화")
            return False

    def is_available(self) -> bool:
        return self._sqlglot_available

    # ════════════════════════════════════════════════════════════
    # 메인 변환 함수
    # ════════════════════════════════════════════════════════════
    def transpile(
        self,
        src_ddl: str,
        obj_type: str,
        obj_name: str,
        src_dialect: str,
        tgt_dialect: str,
    ):
        """SQLGlot 으로 SQL 변환 시도.

        Phase 1 (다음 세션) 구현:
          1. dialect 매핑
          2. sqlglot.transpile() 호출
          3. ParseError 등 예외 안전 처리
          4. 결과를 ConversionResult 로 wrapping

        현재 (골격): None 반환
        """
        if not self._sqlglot_available:
            return None

        try:
            from app.core.conversion_engine import ConversionResult
            import sqlglot
            from sqlglot.errors import ParseError, UnsupportedError

            sg_src = _DIALECT_MAP.get(src_dialect.lower())
            sg_tgt = _DIALECT_MAP.get(tgt_dialect.lower())
            if not sg_src or not sg_tgt:
                _log.warning("[SQLGlot] dialect 매핑 없음: %s → %s",
                             src_dialect, tgt_dialect)
                return None

            # ⭐ Phase 1 다음 세션: 본부장님 ufnGetContactInformation 으로 PoC 검증
            # 현재는 골격만 — 실제 호출 비활성화 (return None)
            #
            # transpiled = sqlglot.transpile(
            #     src_ddl,
            #     read=sg_src,
            #     write=sg_tgt,
            #     identify=True,           # 식별자 quoting 자동
            #     pretty=False,
            # )
            # if not transpiled:
            #     return None
            #
            # return ConversionResult(
            #     success=True,
            #     statements=transpiled,
            #     layer_used="sqlglot",
            #     sqlglot_used=True,
            #     sqlglot_dialect_pair=f"{sg_src}->{sg_tgt}",
            #     notes=f"SQLGlot transpile {sg_src}→{sg_tgt}",
            # )

            return None  # Phase 1 까지

        except ParseError as e:
            _log.info("[SQLGlot] 파싱 실패 (정상 fallback): %s", str(e)[:100])
            return None
        except UnsupportedError as e:
            _log.info("[SQLGlot] 미지원 케이스 (정상 fallback): %s", str(e)[:100])
            return None
        except Exception as e:
            _log.warning("[SQLGlot] 예외 (안전 fallback): %s", e)
            return None

    # ════════════════════════════════════════════════════════════
    # AST 활용 — 본부장님 비즈니스 로직 적용 (Phase 2)
    # ════════════════════════════════════════════════════════════
    def apply_business_rules_via_ast(self, src_ddl: str, src_dialect: str) -> Optional[str]:
        """SQLGlot AST 로 본부장님 비즈니스 로직 적용.

        예: customer.profile → customer_profile (스키마 평탄화)

        Phase 2 (다음 세션) 구현:
          - sqlglot.parse_one(ddl, dialect=...)
          - ast.find_all(sqlglot.exp.Table) 로 테이블 참조 모두 찾기
          - schema 가 있으면 평탄화
          - ast.sql(dialect=tgt) 로 출력
        """
        return None

    # ════════════════════════════════════════════════════════════
    # 통계 (가시성 페이지용)
    # ════════════════════════════════════════════════════════════
    def get_stats(self) -> dict:
        """SQLGlot 호출 통계 — /api/v1/sqlglot/stats 가 반환.

        Phase 4 (다음 세션) 구현:
          - 호출 횟수, 성공/실패 비율
          - dialect 쌍별 성공률
          - Rule Engine 흡수율 (몇 % 가 영구 자산화됐나)
        """
        return {
            "available": self._sqlglot_available,
            "version": self._get_version(),
            "supported_dialects": list(_DIALECT_MAP.keys()),
        }

    def _get_version(self) -> str:
        if not self._sqlglot_available:
            return "n/a"
        try:
            import sqlglot
            return getattr(sqlglot, "__version__", "unknown")
        except Exception:
            return "unknown"
