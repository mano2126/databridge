"""
v93_C (2026-05-01): Post-Migration Audit Engine

본부장님 통찰: "이관 시점에 점검해야 진짜 AI 이관 툴"

이관 완료 직후 자동 실행되는 5단계 검증:
  1. INDEX 누락       — 소스 vs 타겟 secondary index 카운트 비교
  2. FK 깨짐          — 참조 무결성 위반 탐지
  3. OBJECT 누락      — 소스에 있고 타겟에 없는 SP/FUNC/VIEW/TRIGGER
  4. ROW COUNT 차이   — 모든 테이블 src vs tgt
  5. 타입 손실        — varchar(max) 등 폭 손실

각 검증은 독립적으로 실행 가능 (개별 호출 + 통합 호출 모두 지원).
결과는 dict 로 반환 → migration_engine 의 run() 끝에서 self.job["audit_report"] 에 저장.
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger("databridge.audit")


class AuditEngine:
    """이관 사후 검증 엔진"""
    
    def __init__(self, src_conn, tgt_conn, src_type: str, tgt_type: str,
                 src_db: str, tgt_db: str, schema_strategy: str = "underscore",
                 logger_func=None):
        """
        Args:
            src_conn, tgt_conn: 이미 열린 DB 커넥션
            src_type, tgt_type: 'mssql' / 'mysql' 등
            src_db, tgt_db: 데이터베이스 이름
            schema_strategy: 'underscore' (schema.table → schema_table) 등
            logger_func: 로그 콜백 (level, msg) — 없으면 logger.info 사용
        """
        self.src_conn = src_conn
        self.tgt_conn = tgt_conn
        self.src_type = (src_type or "").lower()
        self.tgt_type = (tgt_type or "").lower()
        self.src_db   = src_db
        self.tgt_db   = tgt_db
        self.schema_strategy = schema_strategy
        self._log = logger_func or (lambda lvl, msg: logger.info(f"[{lvl}] {msg}"))
    
    # ─────────────────────────────────────────────────────
    # 1. INDEX 누락 검증
    # ─────────────────────────────────────────────────────
    def check_indexes(self) -> dict:
        """소스 vs 타겟 secondary index 비교
        
        Returns:
            {
              'tables': [{table, src_idx_count, tgt_idx_count, missing: [...]}, ...],
              'total_missing': int,
              'severity': 'ok' | 'warn' | 'critical',
            }
        """
        result = {"tables": [], "total_missing": 0, "severity": "ok"}
        try:
            src_idx = self._collect_indexes(self.src_conn, self.src_type, self.src_db)
            tgt_idx = self._collect_indexes(self.tgt_conn, self.tgt_type, self.tgt_db)
            
            # 테이블명 매핑 (underscore 정책)
            for src_tbl, src_idx_list in src_idx.items():
                tgt_tbl = self._map_table_name(src_tbl)
                tgt_idx_list = tgt_idx.get(tgt_tbl, [])
                
                # 컬럼 시그니처 비교 (인덱스 이름은 다를 수 있어도 대상 컬럼은 같아야 함)
                src_sigs = {tuple(sorted(idx["columns"])) for idx in src_idx_list if not idx.get("is_pk")}
                tgt_sigs = {tuple(sorted(idx["columns"])) for idx in tgt_idx_list if not idx.get("is_pk")}
                missing_sigs = src_sigs - tgt_sigs
                
                if missing_sigs:
                    missing_list = []
                    for sig in missing_sigs:
                        # 원본 인덱스 정보 찾기 (이름 표시용)
                        for idx in src_idx_list:
                            if tuple(sorted(idx["columns"])) == sig:
                                missing_list.append({
                                    "name": idx.get("name", "?"),
                                    "columns": list(sig),
                                    "is_unique": idx.get("is_unique", False),
                                })
                                break
                    result["tables"].append({
                        "table": src_tbl, "tgt_table": tgt_tbl,
                        "src_idx_count": len(src_sigs),
                        "tgt_idx_count": len(tgt_sigs),
                        "missing": missing_list,
                    })
                    result["total_missing"] += len(missing_list)
            
            # severity
            if result["total_missing"] == 0:
                result["severity"] = "ok"
            elif result["total_missing"] < 5:
                result["severity"] = "warn"
            else:
                result["severity"] = "critical"
            
            self._log("info", f"[Audit/Index] 누락 인덱스: {result['total_missing']}개 (severity={result['severity']})")
        except Exception as e:
            result["error"] = str(e)
            result["severity"] = "error"
            self._log("error", f"[Audit/Index] 검증 실패: {e}")
        return result
    
    # ─────────────────────────────────────────────────────
    # 2. FK 무결성 검증
    # ─────────────────────────────────────────────────────
    def check_foreign_keys(self) -> dict:
        """타겟 FK 무결성 검증 — 참조 깨진 행 카운트
        
        Returns:
            {
              'fks': [{table, fk_name, ref_table, broken_count}, ...],
              'total_broken': int,
              'severity': 'ok' | 'warn' | 'critical',
            }
        """
        result = {"fks": [], "total_broken": 0, "severity": "ok"}
        try:
            fks = self._collect_fks(self.tgt_conn, self.tgt_type, self.tgt_db)
            
            for fk in fks:
                # SELECT COUNT(*) FROM child WHERE child.col NOT IN (SELECT col FROM parent)
                tbl  = fk["table"]
                col  = fk["column"]
                ref_tbl = fk["ref_table"]
                ref_col = fk["ref_column"]
                
                broken = self._count_broken_fk(
                    self.tgt_conn, self.tgt_type, self.tgt_db,
                    tbl, col, ref_tbl, ref_col,
                )
                if broken > 0:
                    result["fks"].append({
                        "table": tbl, "column": col,
                        "ref_table": ref_tbl, "ref_column": ref_col,
                        "fk_name": fk.get("name", "?"),
                        "broken_count": broken,
                    })
                    result["total_broken"] += broken
            
            if result["total_broken"] == 0:
                result["severity"] = "ok"
            elif result["total_broken"] < 100:
                result["severity"] = "warn"
            else:
                result["severity"] = "critical"
            
            self._log("info", f"[Audit/FK] 깨진 참조: {result['total_broken']}건 (severity={result['severity']})")
        except Exception as e:
            result["error"] = str(e)
            result["severity"] = "error"
            self._log("error", f"[Audit/FK] 검증 실패: {e}")
        return result
    
    # ─────────────────────────────────────────────────────
    # 3. OBJECT 누락 검증
    # ─────────────────────────────────────────────────────
    def check_objects(self) -> dict:
        """소스에 있고 타겟에 없는 SP/FUNC/VIEW/TRIGGER 탐지
        
        Returns:
            {
              'missing': [{type, name, src_schema}, ...],
              'total_missing': int,
              'severity': 'ok' | 'warn' | 'critical',
            }
        """
        result = {"missing": [], "total_missing": 0, "severity": "ok"}
        try:
            src_objs = self._collect_objects(self.src_conn, self.src_type, self.src_db)
            tgt_objs = self._collect_objects(self.tgt_conn, self.tgt_type, self.tgt_db)
            
            # 타겟 객체명 set (대소문자 무시)
            tgt_names = {o["name"].lower() for o in tgt_objs}
            
            for src_obj in src_objs:
                # 매핑된 이름 (schema_name 정책)
                mapped = self._map_object_name(src_obj["schema"], src_obj["name"]).lower()
                if mapped not in tgt_names and src_obj["name"].lower() not in tgt_names:
                    result["missing"].append({
                        "type": src_obj["type"],
                        "name": src_obj["name"],
                        "src_schema": src_obj.get("schema", ""),
                        "expected_tgt_name": mapped,
                    })
                    result["total_missing"] += 1
            
            if result["total_missing"] == 0:
                result["severity"] = "ok"
            elif result["total_missing"] < 3:
                result["severity"] = "warn"
            else:
                result["severity"] = "critical"
            
            self._log("info", f"[Audit/Object] 누락 객체: {result['total_missing']}개 (severity={result['severity']})")
        except Exception as e:
            result["error"] = str(e)
            result["severity"] = "error"
            self._log("error", f"[Audit/Object] 검증 실패: {e}")
        return result
    
    # ─────────────────────────────────────────────────────
    # 4. ROW COUNT 차이 검증
    # ─────────────────────────────────────────────────────
    def check_row_counts(self) -> dict:
        """모든 테이블의 src_count vs tgt_count 비교
        
        Returns:
            {
              'tables': [{table, src_count, tgt_count, diff}, ...],
              'total_diff_tables': int,
              'severity': 'ok' | 'warn' | 'critical',
            }
        """
        result = {"tables": [], "total_diff_tables": 0, "severity": "ok"}
        try:
            src_tables = self._list_tables(self.src_conn, self.src_type, self.src_db)
            
            for src_tbl in src_tables:
                tgt_tbl = self._map_table_name(src_tbl)
                try:
                    src_cnt = self._row_count(self.src_conn, self.src_type, self.src_db, src_tbl)
                except Exception as e:
                    src_cnt = -1
                try:
                    tgt_cnt = self._row_count(self.tgt_conn, self.tgt_type, self.tgt_db, tgt_tbl)
                except Exception as e:
                    tgt_cnt = -1
                
                if src_cnt != tgt_cnt:
                    result["tables"].append({
                        "table": src_tbl, "tgt_table": tgt_tbl,
                        "src_count": src_cnt, "tgt_count": tgt_cnt,
                        "diff": tgt_cnt - src_cnt,
                    })
                    result["total_diff_tables"] += 1
            
            if result["total_diff_tables"] == 0:
                result["severity"] = "ok"
            elif result["total_diff_tables"] < 3:
                result["severity"] = "warn"
            else:
                result["severity"] = "critical"
            
            self._log("info", f"[Audit/RowCount] 차이 테이블: {result['total_diff_tables']}개 (severity={result['severity']})")
        except Exception as e:
            result["error"] = str(e)
            result["severity"] = "error"
            self._log("error", f"[Audit/RowCount] 검증 실패: {e}")
        return result
    
    # ─────────────────────────────────────────────────────
    # 5. 타입 손실 검증 (varchar/text 폭 검증)
    # ─────────────────────────────────────────────────────
    def check_type_loss(self) -> dict:
        """varchar(max), nvarchar(max), text → 타겟 폭 손실 탐지
        
        Returns:
            {
              'columns': [{table, column, src_type, tgt_type, risk}, ...],
              'total_risky': int,
              'severity': 'ok' | 'warn' | 'critical',
            }
        """
        result = {"columns": [], "total_risky": 0, "severity": "ok"}
        try:
            src_cols = self._collect_columns(self.src_conn, self.src_type, self.src_db)
            tgt_cols = self._collect_columns(self.tgt_conn, self.tgt_type, self.tgt_db)
            
            for src_col in src_cols:
                src_tbl = src_col["table"]
                tgt_tbl = self._map_table_name(src_tbl)
                col_name = src_col["column"].lower()
                
                # 타겟에서 같은 컬럼 찾기
                matching = [c for c in tgt_cols
                           if c["table"].lower() == tgt_tbl.lower()
                           and c["column"].lower() == col_name]
                if not matching:
                    continue
                tgt_col = matching[0]
                
                risk = self._assess_type_loss(src_col, tgt_col)
                if risk:
                    result["columns"].append({
                        "table": src_tbl, "tgt_table": tgt_tbl,
                        "column": col_name,
                        "src_type": src_col.get("type_full", "?"),
                        "tgt_type": tgt_col.get("type_full", "?"),
                        "risk": risk,
                    })
                    result["total_risky"] += 1
            
            if result["total_risky"] == 0:
                result["severity"] = "ok"
            elif result["total_risky"] < 5:
                result["severity"] = "warn"
            else:
                result["severity"] = "critical"
            
            self._log("info", f"[Audit/TypeLoss] 위험 컬럼: {result['total_risky']}개 (severity={result['severity']})")
        except Exception as e:
            result["error"] = str(e)
            result["severity"] = "error"
            self._log("error", f"[Audit/TypeLoss] 검증 실패: {e}")
        return result
    
    # ─────────────────────────────────────────────────────
    # 통합 실행 — 5개 모두 실행
    # ─────────────────────────────────────────────────────
    def run_all(self) -> dict:
        """모든 검증을 순차 실행하고 통합 리포트 반환"""
        from datetime import datetime
        report = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "src_db": self.src_db,
            "tgt_db": self.tgt_db,
            "checks": {},
            "overall_severity": "ok",
        }
        
        self._log("info", "═══════════ Post-Migration Audit 시작 ═══════════")
        
        report["checks"]["index"]     = self.check_indexes()
        report["checks"]["fk"]        = self.check_foreign_keys()
        report["checks"]["object"]    = self.check_objects()
        report["checks"]["row_count"] = self.check_row_counts()
        report["checks"]["type_loss"] = self.check_type_loss()
        
        # 전체 심각도 결정
        severities = [c.get("severity", "ok") for c in report["checks"].values()]
        if "critical" in severities:
            report["overall_severity"] = "critical"
        elif "error" in severities:
            report["overall_severity"] = "error"
        elif "warn" in severities:
            report["overall_severity"] = "warn"
        else:
            report["overall_severity"] = "ok"
        
        # 요약
        summary = []
        for k, c in report["checks"].items():
            if k == "index":
                summary.append(f"Index 누락 {c.get('total_missing', 0)}개")
            elif k == "fk":
                summary.append(f"FK 깨짐 {c.get('total_broken', 0)}건")
            elif k == "object":
                summary.append(f"Object 누락 {c.get('total_missing', 0)}개")
            elif k == "row_count":
                summary.append(f"행수 차이 {c.get('total_diff_tables', 0)}개 테이블")
            elif k == "type_loss":
                summary.append(f"타입 손실 위험 {c.get('total_risky', 0)}개 컬럼")
        report["summary"] = " | ".join(summary)
        
        self._log("info", f"[Audit] {report['summary']}")
        self._log("info", f"═══════════ Audit 완료 (전체 심각도: {report['overall_severity']}) ═══════════")
        return report
    
    # ═════════════════════════════════════════════════════
    # Helper 메서드들 — DB 별 구현
    # ═════════════════════════════════════════════════════
    
    def _map_table_name(self, src_table: str) -> str:
        """schema.table → schema_table (underscore 정책)"""
        if self.schema_strategy == "underscore" and "." in src_table:
            return src_table.replace(".", "_")
        return src_table
    
    def _map_object_name(self, src_schema: str, name: str) -> str:
        """schema 객체명 → 매핑된 타겟 객체명"""
        if self.schema_strategy == "underscore" and src_schema:
            return f"{src_schema}_{name}"
        return name
    
    def _collect_indexes(self, conn, db_type: str, db_name: str) -> dict:
        """{table_name: [{name, columns: [...], is_pk, is_unique}, ...]}"""
        result = {}
        cur = conn.cursor()
        if db_type in ("mssql", "azure", "sqlserver"):
            cur.execute("""
                SELECT s.name + '.' + t.name AS tbl, i.name AS idx_name,
                       c.name AS col, i.is_primary_key, i.is_unique
                  FROM sys.indexes i
                  JOIN sys.tables t ON i.object_id = t.object_id
                  JOIN sys.schemas s ON t.schema_id = s.schema_id
                  JOIN sys.index_columns ic ON i.object_id=ic.object_id AND i.index_id=ic.index_id
                  JOIN sys.columns c ON ic.object_id=c.object_id AND ic.column_id=c.column_id
                 WHERE i.is_hypothetical = 0 AND i.type > 0
                 ORDER BY tbl, idx_name, ic.key_ordinal
            """)
        elif db_type in ("mysql", "aurora", "mariadb", "tidb", "cloudsql"):
            cur.execute(f"""
                SELECT TABLE_NAME AS tbl, INDEX_NAME AS idx_name,
                       COLUMN_NAME AS col,
                       CASE WHEN INDEX_NAME='PRIMARY' THEN 1 ELSE 0 END AS is_pk,
                       CASE WHEN NON_UNIQUE=0 THEN 1 ELSE 0 END AS is_unique
                  FROM information_schema.STATISTICS
                 WHERE TABLE_SCHEMA = '{db_name}'
                 ORDER BY tbl, idx_name, SEQ_IN_INDEX
            """)
        else:
            return result
        
        idx_map = {}  # (tbl, idx_name) → {columns, is_pk, is_unique}
        for row in cur.fetchall():
            tbl, idx_name, col, is_pk, is_unique = row[0], row[1], row[2], row[3], row[4]
            key = (tbl, idx_name)
            if key not in idx_map:
                idx_map[key] = {"name": idx_name, "columns": [], "is_pk": bool(is_pk), "is_unique": bool(is_unique)}
            idx_map[key]["columns"].append(col)
        
        for (tbl, idx_name), info in idx_map.items():
            result.setdefault(tbl, []).append(info)
        return result
    
    def _collect_fks(self, conn, db_type: str, db_name: str) -> list:
        """[{name, table, column, ref_table, ref_column}, ...]"""
        cur = conn.cursor()
        if db_type in ("mysql", "aurora", "mariadb", "tidb", "cloudsql"):
            cur.execute(f"""
                SELECT CONSTRAINT_NAME, TABLE_NAME, COLUMN_NAME,
                       REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                  FROM information_schema.KEY_COLUMN_USAGE
                 WHERE TABLE_SCHEMA = '{db_name}'
                   AND REFERENCED_TABLE_NAME IS NOT NULL
            """)
        elif db_type in ("mssql", "azure", "sqlserver"):
            cur.execute("""
                SELECT fk.name, OBJECT_NAME(fkc.parent_object_id),
                       c1.name, OBJECT_NAME(fkc.referenced_object_id), c2.name
                  FROM sys.foreign_keys fk
                  JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
                  JOIN sys.columns c1 ON fkc.parent_object_id=c1.object_id AND fkc.parent_column_id=c1.column_id
                  JOIN sys.columns c2 ON fkc.referenced_object_id=c2.object_id AND fkc.referenced_column_id=c2.column_id
            """)
        else:
            return []
        
        return [{"name": r[0], "table": r[1], "column": r[2],
                 "ref_table": r[3], "ref_column": r[4]} for r in cur.fetchall()]
    
    def _count_broken_fk(self, conn, db_type, db_name, tbl, col, ref_tbl, ref_col) -> int:
        """child.col 값 중 parent.col 에 없는 것 카운트"""
        cur = conn.cursor()
        try:
            if db_type in ("mssql", "azure", "sqlserver"):
                sql = f"""
                    SELECT COUNT(*) FROM [{tbl}] c
                    WHERE c.[{col}] IS NOT NULL
                      AND NOT EXISTS (SELECT 1 FROM [{ref_tbl}] p WHERE p.[{ref_col}] = c.[{col}])
                """
            else:
                sql = f"""
                    SELECT COUNT(*) FROM `{tbl}` c
                    WHERE c.`{col}` IS NOT NULL
                      AND NOT EXISTS (SELECT 1 FROM `{ref_tbl}` p WHERE p.`{ref_col}` = c.`{col}`)
                """
            cur.execute(sql)
            row = cur.fetchone()
            return int(row[0]) if row else 0
        except Exception as e:
            self._log("warn", f"[Audit/FK] {tbl}.{col} 검증 실패: {e}")
            return 0
    
    def _collect_objects(self, conn, db_type: str, db_name: str) -> list:
        """[{type, name, schema}, ...]"""
        cur = conn.cursor()
        result = []
        if db_type in ("mssql", "azure", "sqlserver"):
            cur.execute("""
                SELECT s.name AS sch, o.name AS nm, o.type_desc
                  FROM sys.objects o
                  JOIN sys.schemas s ON o.schema_id = s.schema_id
                 WHERE o.type IN ('P','FN','TF','IF','V','TR')
                   AND o.is_ms_shipped = 0
            """)
            for r in cur.fetchall():
                t = r[2]
                otype = ("PROCEDURE" if t.startswith("SQL_STORED") else
                         "FUNCTION"  if "FUNC" in t else
                         "VIEW"      if "VIEW" in t else
                         "TRIGGER"   if "TRIG" in t else "UNKNOWN")
                result.append({"type": otype, "name": r[1], "schema": r[0]})
        elif db_type in ("mysql", "aurora", "mariadb", "tidb", "cloudsql"):
            cur.execute(f"""
                SELECT ROUTINE_NAME, ROUTINE_TYPE FROM information_schema.ROUTINES
                 WHERE ROUTINE_SCHEMA='{db_name}'
            """)
            for r in cur.fetchall():
                result.append({"type": r[1], "name": r[0], "schema": ""})
            cur.execute(f"""
                SELECT TABLE_NAME FROM information_schema.VIEWS
                 WHERE TABLE_SCHEMA='{db_name}'
            """)
            for r in cur.fetchall():
                result.append({"type": "VIEW", "name": r[0], "schema": ""})
            cur.execute(f"""
                SELECT TRIGGER_NAME FROM information_schema.TRIGGERS
                 WHERE TRIGGER_SCHEMA='{db_name}'
            """)
            for r in cur.fetchall():
                result.append({"type": "TRIGGER", "name": r[0], "schema": ""})
        return result
    
    def _list_tables(self, conn, db_type: str, db_name: str) -> list:
        cur = conn.cursor()
        if db_type in ("mssql", "azure", "sqlserver"):
            cur.execute("""
                SELECT s.name + '.' + t.name FROM sys.tables t
                  JOIN sys.schemas s ON t.schema_id = s.schema_id
            """)
            return [r[0] for r in cur.fetchall()]
        elif db_type in ("mysql", "aurora", "mariadb", "tidb", "cloudsql"):
            cur.execute(f"""
                SELECT TABLE_NAME FROM information_schema.TABLES
                 WHERE TABLE_SCHEMA='{db_name}' AND TABLE_TYPE='BASE TABLE'
            """)
            return [r[0] for r in cur.fetchall()]
        return []
    
    def _row_count(self, conn, db_type: str, db_name: str, table: str) -> int:
        cur = conn.cursor()
        if db_type in ("mssql", "azure", "sqlserver"):
            sql = f"SELECT COUNT(*) FROM [{table}]"
        else:
            sql = f"SELECT COUNT(*) FROM `{table}`"
        cur.execute(sql)
        row = cur.fetchone()
        return int(row[0]) if row else 0
    
    def _collect_columns(self, conn, db_type: str, db_name: str) -> list:
        cur = conn.cursor()
        result = []
        if db_type in ("mssql", "azure", "sqlserver"):
            cur.execute("""
                SELECT s.name + '.' + t.name, c.name, ty.name AS type_name,
                       c.max_length, c.precision, c.scale
                  FROM sys.columns c
                  JOIN sys.tables t ON c.object_id = t.object_id
                  JOIN sys.schemas s ON t.schema_id = s.schema_id
                  JOIN sys.types ty ON c.user_type_id = ty.user_type_id
            """)
            for r in cur.fetchall():
                tbl, col, type_name, max_len, prec, scale = r[0], r[1], r[2], r[3], r[4], r[5]
                full = type_name
                if type_name in ("varchar","nvarchar","char","nchar"):
                    if max_len == -1:
                        full = f"{type_name}(max)"
                    else:
                        actual = max_len // 2 if type_name.startswith("n") else max_len
                        full = f"{type_name}({actual})"
                elif type_name in ("decimal","numeric"):
                    full = f"{type_name}({prec},{scale})"
                result.append({"table": tbl, "column": col, "type": type_name,
                              "type_full": full, "max_length": max_len})
        elif db_type in ("mysql", "aurora", "mariadb", "tidb", "cloudsql"):
            cur.execute(f"""
                SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, COLUMN_TYPE,
                       CHARACTER_MAXIMUM_LENGTH
                  FROM information_schema.COLUMNS
                 WHERE TABLE_SCHEMA='{db_name}'
            """)
            for r in cur.fetchall():
                result.append({"table": r[0], "column": r[1], "type": r[2],
                              "type_full": r[3], "max_length": r[4]})
        return result
    
    def _assess_type_loss(self, src_col: dict, tgt_col: dict) -> Optional[str]:
        """타입 손실 위험 평가. 위험 있으면 설명 문자열, 없으면 None"""
        src_type = (src_col.get("type") or "").lower()
        tgt_type = (tgt_col.get("type") or "").lower()
        src_full = (src_col.get("type_full") or "").lower()
        tgt_full = (tgt_col.get("type_full") or "").lower()
        src_len = src_col.get("max_length")
        tgt_len = tgt_col.get("max_length")
        
        # MSSQL varchar(max) / nvarchar(max) → MySQL
        if "max" in src_full:
            if tgt_type not in ("longtext", "mediumtext", "text"):
                return f"varchar(max) → {tgt_full} 폭 제한 가능"
        
        # 길이 축소
        try:
            if src_len and tgt_len and src_len > 0 and tgt_len > 0:
                if int(src_len) > int(tgt_len):
                    return f"길이 축소: {src_len} → {tgt_len}"
        except Exception:
            pass
        
        # decimal precision/scale 체크는 type_full 비교로
        if src_type in ("decimal", "numeric") and tgt_type in ("decimal", "numeric"):
            if src_full != tgt_full and "(" in src_full and "(" in tgt_full:
                return f"decimal 정밀도 차이: {src_full} → {tgt_full}"
        
        # MSSQL datetime2 → MySQL datetime (마이크로초 손실 가능)
        if src_type == "datetime2" and tgt_type == "datetime":
            return "datetime2 → datetime: 마이크로초 정밀도 손실 가능"
        
        return None
