"""
v93_A (2026-05-01): Index Auto-Migration

본부장님 발견: 22개 큰 테이블에 PK 만 있고 secondary index 0개
v_customer_360 EXPLAIN 28조 회 풀스캔 → 운영 환경 시작 불가

처방: 데이터 이관 완료 후 자동으로 소스 인덱스를 타겟에 생성.

흐름:
  1. 소스에서 모든 인덱스 메타 수집 (PK 제외)
  2. DB 종류별 CREATE INDEX DDL 생성
  3. 타겟에 적용 (실패 시 개별 격리, 전체 중단 안 함)
  4. 결과 리포트 반환
"""
from __future__ import annotations
import logging
from typing import Optional, Callable

logger = logging.getLogger("databridge.index_migrator")


class IndexMigrator:
    """소스 → 타겟 인덱스 자동 이관"""
    
    def __init__(self, src_conn, tgt_conn, src_type: str, tgt_type: str,
                 src_db: str, tgt_db: str, schema_strategy: str = "underscore",
                 logger_func: Optional[Callable] = None,
                 skip_existing: bool = True):
        self.src_conn = src_conn
        self.tgt_conn = tgt_conn
        self.src_type = (src_type or "").lower()
        self.tgt_type = (tgt_type or "").lower()
        self.src_db   = src_db
        self.tgt_db   = tgt_db
        self.schema_strategy = schema_strategy
        self.skip_existing = skip_existing  # 이미 같은 시그니처 인덱스 있으면 skip
        self._log = logger_func or (lambda lvl, msg: logger.info(f"[{lvl}] {msg}"))
    
    def run(self, table_filter: Optional[list] = None) -> dict:
        """인덱스 이관 실행
        
        Args:
            table_filter: 특정 테이블만 이관 시 ['schema.table', ...]. None 이면 전체
        
        Returns:
            {
              'attempted': N, 'created': N, 'skipped': N, 'failed': N,
              'details': [...],
              'failures': [...],
            }
        """
        result = {"attempted": 0, "created": 0, "skipped": 0, "failed": 0,
                  "details": [], "failures": []}
        
        try:
            self._log("info", "═══ 인덱스 자동 이관 시작 ═══")
            
            # 1. 소스 인덱스 수집
            src_indexes = self._collect_source_indexes()
            self._log("info", f"소스 인덱스 수집: {len(src_indexes)}개 (PK 제외)")
            
            # 2. 타겟 기존 인덱스 (중복 방지용)
            existing_tgt = self._collect_target_signatures() if self.skip_existing else set()
            
            # 3. 테이블 필터 적용
            if table_filter:
                filter_set = set(table_filter)
                src_indexes = [idx for idx in src_indexes if idx["src_table"] in filter_set]
                self._log("info", f"필터 적용: {len(src_indexes)}개 인덱스")
            
            # 4. DDL 생성 + 적용
            for idx in src_indexes:
                result["attempted"] += 1
                tgt_table = self._map_table_name(idx["src_table"])
                idx["tgt_table"] = tgt_table
                
                # 시그니처: (table, sorted columns) — 이름 무시
                sig = (tgt_table.lower(), tuple(sorted(c.lower() for c in idx["columns"])))
                if sig in existing_tgt:
                    result["skipped"] += 1
                    result["details"].append({
                        "table": tgt_table, "index": idx["name"],
                        "status": "skipped", "reason": "already exists"
                    })
                    continue
                
                ddl = self._build_create_index_ddl(idx, tgt_table)
                if not ddl:
                    result["failed"] += 1
                    result["failures"].append({
                        "table": tgt_table, "index": idx["name"],
                        "error": "DDL 생성 실패 (지원 안 되는 인덱스 타입)"
                    })
                    continue
                
                try:
                    cur = self.tgt_conn.cursor()
                    cur.execute(ddl)
                    self.tgt_conn.commit()
                    result["created"] += 1
                    result["details"].append({
                        "table": tgt_table, "index": idx["name"],
                        "columns": idx["columns"],
                        "status": "created", "ddl": ddl[:200]
                    })
                    self._log("info", f"  ✓ [{tgt_table}] {idx['name']} 생성")
                except Exception as e:
                    # ════════════════════════════════════════════════════════════
                    # v94_p6 (2026-05-01): 1061 Duplicate key name 자동 skip
                    #
                    # 본부장님 모토: "지금은 발생해도 앞으로 똑같은건 발생 시키지 않는다"
                    #
                    # 시그니처 수집이 실패하거나 (이전 버그), 또는 다른 경로로
                    # 인덱스가 만들어진 경우 — 1061 발생 시 실패가 아닌 skip 처리.
                    # 시그니처 수집 정상화 (위 _row_values 처방) 와 함께 작동하는 안전망.
                    # ════════════════════════════════════════════════════════════
                    err_str = str(e)
                    is_duplicate = (
                        "1061" in err_str or
                        "Duplicate key name" in err_str or
                        "already exists" in err_str.lower()
                    )
                    if is_duplicate:
                        result["skipped"] += 1
                        result["details"].append({
                            "table": tgt_table, "index": idx["name"],
                            "status": "skipped",
                            "reason": "already exists (1061 fallback)"
                        })
                        self._log("info",
                            f"  → [{tgt_table}] {idx['name']} 이미 존재 (skip)")
                    else:
                        result["failed"] += 1
                        result["failures"].append({
                            "table": tgt_table, "index": idx["name"],
                            "error": err_str[:200], "ddl": ddl[:300]
                        })
                        self._log("warn",
                            f"  ✗ [{tgt_table}] {idx['name']} 실패: {err_str[:100]}")
                    try: self.tgt_conn.rollback()
                    except Exception: pass
            
            self._log("info",
                f"═══ 인덱스 이관 완료: 시도={result['attempted']}, "
                f"생성={result['created']}, skip={result['skipped']}, "
                f"실패={result['failed']} ═══")
        except Exception as e:
            result["error"] = str(e)
            self._log("error", f"인덱스 이관 치명 오류: {e}")
        return result
    
    # ─────────────────────────────────────────────────────
    # 소스 인덱스 수집
    # ─────────────────────────────────────────────────────
    def _collect_source_indexes(self) -> list:
        """소스에서 secondary index 메타 수집 (PK 제외)
        
        Returns:
            [{src_table, name, columns: [...], is_unique, type}, ...]
        """
        if self.src_type in ("mssql", "azure", "sqlserver"):
            return self._collect_mssql_indexes()
        elif self.src_type in ("mysql", "aurora", "mariadb", "tidb", "cloudsql"):
            return self._collect_mysql_indexes()
        return []
    
    def _collect_mssql_indexes(self) -> list:
        cur = self.src_conn.cursor()
        cur.execute("""
            SELECT s.name + '.' + t.name AS tbl,
                   i.name AS idx_name,
                   i.is_unique,
                   i.type_desc,
                   c.name AS col,
                   ic.is_descending_key,
                   ic.is_included_column
              FROM sys.indexes i
              JOIN sys.tables t  ON i.object_id = t.object_id
              JOIN sys.schemas s ON t.schema_id = s.schema_id
              JOIN sys.index_columns ic ON i.object_id=ic.object_id AND i.index_id=ic.index_id
              JOIN sys.columns c ON ic.object_id=c.object_id AND ic.column_id=c.column_id
             WHERE i.is_primary_key = 0
               AND i.is_unique_constraint = 0
               AND i.type > 0
               AND i.is_hypothetical = 0
               AND i.name IS NOT NULL
             ORDER BY tbl, idx_name, ic.key_ordinal
        """)
        idx_map = {}  # (tbl, idx_name) -> dict
        for r in cur.fetchall():
            # v94_p6: dict/tuple 양쪽 안전 접근 (DictCursor 호환)
            v = self._row_values(r, ["tbl", "idx_name", "is_unique", "type_desc",
                                     "col", "is_descending_key", "is_included_column"], 7)
            tbl, idx_name, is_unique, type_desc, col, is_desc, is_incl = v
            key = (tbl, idx_name)
            if key not in idx_map:
                idx_map[key] = {
                    "src_table": tbl, "name": idx_name,
                    "is_unique": bool(is_unique),
                    "type": type_desc,
                    "columns": [], "included_columns": [],
                }
            if is_incl:
                idx_map[key]["included_columns"].append(col)
            else:
                idx_map[key]["columns"].append(col)
        return list(idx_map.values())
    
    def _collect_mysql_indexes(self) -> list:
        cur = self.src_conn.cursor()
        cur.execute(f"""
            SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, INDEX_TYPE,
                   COLUMN_NAME, SEQ_IN_INDEX
              FROM information_schema.STATISTICS
             WHERE TABLE_SCHEMA = '{self.src_db}'
               AND INDEX_NAME != 'PRIMARY'
             ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
        """)
        idx_map = {}
        for r in cur.fetchall():
            # v94_p6: dict/tuple 양쪽 안전 접근
            v = self._row_values(r, ["TABLE_NAME", "INDEX_NAME", "NON_UNIQUE",
                                     "INDEX_TYPE", "COLUMN_NAME", "SEQ_IN_INDEX"], 6)
            tbl, idx_name, non_unique, idx_type, col, seq = v
            key = (tbl, idx_name)
            if key not in idx_map:
                idx_map[key] = {
                    "src_table": tbl, "name": idx_name,
                    "is_unique": (int(non_unique) == 0),
                    "type": idx_type,
                    "columns": [], "included_columns": [],
                }
            idx_map[key]["columns"].append(col)
        return list(idx_map.values())
    
    # ════════════════════════════════════════════════════════════════
    # v94_p6 (2026-05-01) 본질 처방: 본부장님 호소
    #   "기존 인덱스 시그니처 수집 실패: 0" → 33개 인덱스 모두 1061 충돌
    #
    # 진짜 원인 (DictCursor 호환):
    #   migration_engine.py L878 에서 tgt_conn 을 pymysql.cursors.DictCursor 로 생성
    #   IndexMigrator 의 fetchall 결과를 r[0], r[1] 같은 정수 인덱스로 접근
    #   → DictCursor 는 dict 반환 → KeyError(0) → str(KeyError(0)) == "0"
    #   → 본부장님이 본 "수집 실패: 0" 의 정체
    #
    # 본질 처방: 4곳 모두 dict/tuple 양쪽 안전한 헬퍼 사용
    # ════════════════════════════════════════════════════════════════
    @staticmethod
    def _row_values(row, dict_keys: list, expected_n: int) -> list:
        """fetchall row 에서 컬럼 값을 dict/tuple 양쪽 안전하게 추출.

        - row 가 dict (DictCursor) 인 경우: dict_keys 로 lookup (대소문자 무시)
        - row 가 tuple/list 인 경우: 정수 인덱스로 lookup
        - row 가 sqlalchemy Row 인 경우: ._mapping 사용 (있으면)
        """
        # dict / dict-like
        if isinstance(row, dict):
            out = []
            # case-insensitive lookup (MSSQL 의 sys.* 컬럼이 lowercase 로 올 수도)
            ci_map = {k.lower(): k for k in row.keys()}
            for key in dict_keys:
                actual = ci_map.get(key.lower())
                if actual is not None:
                    out.append(row[actual])
                else:
                    out.append(None)
            return out
        # sqlalchemy Row
        if hasattr(row, "_mapping"):
            try:
                m = row._mapping
                ci_map = {k.lower(): k for k in m.keys()}
                return [m.get(ci_map.get(k.lower())) if ci_map.get(k.lower()) else None for k in dict_keys]
            except Exception:
                pass
        # tuple / list
        if hasattr(row, "__getitem__") and hasattr(row, "__len__"):
            out = []
            for i in range(expected_n):
                try:
                    out.append(row[i])
                except (IndexError, KeyError):
                    out.append(None)
            return out
        return [None] * expected_n

    # ─────────────────────────────────────────────────────
    # 타겟 기존 인덱스 시그니처 (중복 방지)
    # ─────────────────────────────────────────────────────
    def _collect_target_signatures(self) -> set:
        """타겟에 이미 있는 인덱스 시그니처 set: {(table_lower, (col1_lower, col2_lower, ...))}"""
        signatures = set()
        cur = self.tgt_conn.cursor()
        try:
            if self.tgt_type in ("mysql", "aurora", "mariadb", "tidb", "cloudsql"):
                cur.execute(f"""
                    SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME
                      FROM information_schema.STATISTICS
                     WHERE TABLE_SCHEMA = '{self.tgt_db}'
                """)
                idx_cols = {}
                for r in cur.fetchall():
                    # v94_p6: dict/tuple 양쪽 안전 접근
                    v = self._row_values(r, ["TABLE_NAME", "INDEX_NAME", "COLUMN_NAME"], 3)
                    tbl_v, idx_v, col_v = v
                    if tbl_v is None or col_v is None:
                        continue
                    tbl, idx, col = str(tbl_v).lower(), idx_v, str(col_v).lower()
                    idx_cols.setdefault((tbl, idx), []).append(col)
                for (tbl, idx), cols in idx_cols.items():
                    signatures.add((tbl, tuple(sorted(cols))))
            elif self.tgt_type in ("mssql", "azure", "sqlserver"):
                cur.execute("""
                    SELECT t.name AS tbl, i.name AS idx, c.name AS col
                      FROM sys.indexes i
                      JOIN sys.tables t ON i.object_id = t.object_id
                      JOIN sys.index_columns ic ON i.object_id=ic.object_id AND i.index_id=ic.index_id
                      JOIN sys.columns c ON ic.object_id=c.object_id AND ic.column_id=c.column_id
                     WHERE i.type > 0 AND i.is_hypothetical = 0
                """)
                idx_cols = {}
                for r in cur.fetchall():
                    # v94_p6: dict/tuple 양쪽 안전 접근
                    v = self._row_values(r, ["tbl", "idx", "col"], 3)
                    tbl_v, idx_v, col_v = v
                    if tbl_v is None or col_v is None:
                        continue
                    tbl, idx, col = str(tbl_v).lower(), (idx_v or ""), str(col_v).lower()
                    idx_cols.setdefault((tbl, idx), []).append(col)
                for (tbl, idx), cols in idx_cols.items():
                    signatures.add((tbl, tuple(sorted(cols))))
        except Exception as e:
            # v94_p6: 진짜 원인을 알 수 있게 type(e) 도 함께 로그
            self._log("warn", f"기존 인덱스 시그니처 수집 실패: {type(e).__name__}: {e}")
        # v94_p6: 수집된 시그니처 카운트도 로그 (정상 작동 검증용)
        try:
            self._log("info", f"기존 인덱스 시그니처 수집: {len(signatures)}개")
        except Exception:
            pass
        return signatures
    
    # ─────────────────────────────────────────────────────
    # CREATE INDEX DDL 생성
    # ─────────────────────────────────────────────────────
    def _build_create_index_ddl(self, idx: dict, tgt_table: str) -> Optional[str]:
        """DB 종류별 CREATE INDEX DDL 생성
        
        - 인덱스 이름은 충돌 방지 위해 'idx_{table}_{cols}' 패턴
        - MSSQL → MySQL 의 INCLUDE columns 는 단순 무시 (MySQL 미지원)
        """
        if not idx.get("columns"):
            return None
        
        cols = idx["columns"]
        is_unique = idx.get("is_unique", False)
        
        # 새 인덱스 이름 (충돌 방지)
        bare_table = tgt_table.split(".")[-1] if "." in tgt_table else tgt_table
        col_part = "_".join(c[:10] for c in cols[:3])
        new_name = f"idx_{bare_table}_{col_part}"[:64]  # MySQL 인덱스 이름 64자 제한
        
        if self.tgt_type in ("mysql", "aurora", "mariadb", "tidb", "cloudsql"):
            unique_kw = "UNIQUE " if is_unique else ""
            cols_sql = ", ".join(f"`{c}`" for c in cols)
            return f"CREATE {unique_kw}INDEX `{new_name}` ON `{tgt_table}` ({cols_sql})"
        elif self.tgt_type in ("mssql", "azure", "sqlserver"):
            unique_kw = "UNIQUE " if is_unique else ""
            cols_sql = ", ".join(f"[{c}]" for c in cols)
            schema, table = (tgt_table.split(".", 1) + ["dbo"])[:2] if "." in tgt_table else ("dbo", tgt_table)
            return f"CREATE {unique_kw}INDEX [{new_name}] ON [{schema}].[{table}] ({cols_sql})"
        return None
    
    def _map_table_name(self, src_table: str) -> str:
        """schema.table → schema_table (underscore 정책)"""
        if self.schema_strategy == "underscore" and "." in src_table:
            return src_table.replace(".", "_")
        return src_table
