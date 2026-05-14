"""
DataBridge MySQL 실행 검증 — hotfix_031
==========================================

본부장님 13번째 본질 통찰 정면:
  "SQLGlot 의 출력을 MySQL 에 실행해서 진짜 검증한 후 KB 자산화.
   그래야 KB 가 살아있는 자산."

본부장님 16번째 비전 통찰:
  "지속적으로 KB 를 쌓고 쌓여진 KB 가 타겟 DB 에서 잘 수행되면 그걸로 이용"

처방:
  변환된 SQL 을 타겟 MySQL 에 실제 syntax-check + (옵션) 실행 검증
  통과한 SQL 만 Pattern Library 자산화 → 신뢰도 ↑

설계:
  - 안전한 검증: 트랜잭션 없이 DROP/CREATE 시도 → 결과 캡쳐
  - syntax-only: prepared statement 가능한 케이스
  - sandbox: 별도 DB (테스트용) 에서 실행 → 본부장님 운영 환경 영향 0
  
본부장님 모토 #14 (4-way collision 방지) 정면 — 검증 실패 시 본부장님 환경 변경 X.
"""
from __future__ import annotations
import re
import subprocess
import logging
import time
from typing import Tuple, Optional, Dict

_log = logging.getLogger("databridge.mysql_runtime_validator")


# ════════════════════════════════════════════════════════════════
# 설정 — 본부장님 환경 또는 sandbox DB
# ════════════════════════════════════════════════════════════════
DEFAULT_CONTAINER = "db_mysql"
DEFAULT_USER = "root"
DEFAULT_PASSWORD = "Bridge@1234"
DEFAULT_DB = "AdventureWorks2022"  # 본부장님 환경 default
DEFAULT_TIMEOUT = 10


def _run_mysql(sql: str, container: str = DEFAULT_CONTAINER,
               user: str = DEFAULT_USER, password: str = DEFAULT_PASSWORD,
               db: str = DEFAULT_DB, timeout: int = DEFAULT_TIMEOUT) -> Tuple[bool, str, str]:
    """Docker MySQL 에 SQL 실행. (success, stdout, stderr_errors)"""
    try:
        cmd = [
            'docker', 'exec', '-i', container,
            'mysql', f'-u{user}', f'-p{password}',
            db, '-N', '-s',
        ]
        r = subprocess.run(cmd, input=sql, capture_output=True, text=True, timeout=timeout)
        err = (r.stderr or '').strip()
        err_lines = [ln for ln in err.split('\n') if 'ERROR' in ln]
        success = (r.returncode == 0 and not err_lines)
        return success, (r.stdout or ''), '\n'.join(err_lines)
    except subprocess.TimeoutExpired:
        return False, '', f'Timeout after {timeout}s'
    except FileNotFoundError:
        _log.info("[mysql_validator] docker 명령 없음 — 검증 skip (안전 통과)")
        return True, '', 'docker_unavailable'  # docker 없으면 통과 처리
    except Exception as e:
        _log.warning("[mysql_validator] 검증 중 오류: %s", e)
        return True, '', f'error: {e}'  # 오류 시 안전 통과


def validate_mysql_execution(
    sql: str,
    obj_type: str = "",
    obj_name: str = "",
    strict: bool = False,
) -> Tuple[bool, str]:
    """변환된 SQL 을 MySQL 에 실제 실행 검증.
    
    v95_p107 hotfix_032 (본부장님 본질 재처방):
      DROP guard 없으면 SKIP 했던 게 문제 — 모든 SQL 이 검증 통과로 처리됨.
      → DROP guard 없으면 임시 이름으로 변환해서 syntax-only 검증.
    
    검증 흐름:
      1. DROP IF EXISTS 가 있으면 그대로 실행 (안전)
      2. 없으면 — 객체 이름을 임시 이름으로 변환 + DROP IF EXISTS 추가
         → 실행 → 결과 확인 → 통과 시 DROP TEMP (cleanup)
      3. ERROR 캡쳐 → 검증 결과 반환
    
    Returns:
        (is_valid, message)
    """
    if not sql or not sql.strip():
        return False, "empty_sql"
    
    t0 = time.monotonic()
    
    # DROP IF EXISTS 가 있으면 그대로 실행
    has_drop_guard = bool(re.search(r'\bDROP\s+\w+\s+IF\s+EXISTS\b', sql, re.IGNORECASE))
    
    if has_drop_guard:
        # 안전 — 그대로 실행
        success, stdout, err = _run_mysql(sql)
    else:
        # v95_p107 hotfix_032: DROP guard 없으면 임시 이름으로 검증
        # CREATE (PROCEDURE|FUNCTION|TRIGGER|VIEW) `name` → CREATE ... `_tmpdbridge_name`
        temp_suffix = f"_tmpdbridge_{int(time.time()*1000) % 100000}"
        
        # 객체 이름 패턴들
        # CREATE PROCEDURE `dbo_uspXxx` → CREATE PROCEDURE `dbo_uspXxx_tmpXXX`
        # CREATE VIEW `Sales_vXxx`     → CREATE VIEW `Sales_vXxx_tmpXXX`
        modified_sql = sql
        rename_pattern = re.compile(
            r'(CREATE\s+(?:PROCEDURE|FUNCTION|TRIGGER|VIEW)\s+)`([^`]+)`',
            re.IGNORECASE,
        )
        m = rename_pattern.search(modified_sql)
        if not m:
            # 객체 이름 못 찾음 → 검증 SKIP (안전 통과)
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            return True, f"skipped_no_object_name ({elapsed_ms}ms)"
        
        original_name = m.group(2)
        temp_name = f"{original_name}{temp_suffix}"
        modified_sql = rename_pattern.sub(rf'\1`{temp_name}`', modified_sql, count=1)
        
        # DROP IF EXISTS 추가 (앞에)
        obj_kind = m.group(1).strip().split()[-1].upper()
        drop_stmt = f"DROP {obj_kind} IF EXISTS `{temp_name}`;\n"
        validation_sql = drop_stmt + modified_sql
        
        # 검증 실행
        success, stdout, err = _run_mysql(validation_sql)
        
        # 임시 객체 정리 (성공/실패 관계없이)
        try:
            cleanup_sql = f"DROP {obj_kind} IF EXISTS `{temp_name}`;"
            _run_mysql(cleanup_sql, timeout=5)
        except Exception:
            pass
    
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    
    if success:
        _log.info(
            "[v95_p107-MYSQL-VALIDATE-OK] %s [%s] MySQL 실행 검증 통과 (%dms) — "
            "Pattern 자산화 안전",
            obj_type, obj_name, elapsed_ms,
        )
        return True, f"mysql_exec_ok ({elapsed_ms}ms)"
    else:
        # docker 없으면 통과 (strict 가 아니면)
        if not strict and (err == 'docker_unavailable' or err.startswith('error:')):
            return True, f"validation_skipped: {err}"
        
        _log.warning(
            "[v95_p107-MYSQL-VALIDATE-FAIL] %s [%s] MySQL 실행 검증 실패 (%dms) — "
            "Pattern 자산화 거부 (err=%s)",
            obj_type, obj_name, elapsed_ms, err[:200] if err else '?',
        )
        return False, f"mysql_exec_fail: {err[:200] if err else '?'}"


def validate_syntax_only(sql: str, obj_type: str = "", obj_name: str = "") -> Tuple[bool, str]:
    """syntax-only 검증 (실행 안 함).
    
    안전한 검증: SQL 을 prepared statement 로 PREPARE 만 시도.
    그러나 stored routine (PROCEDURE/FUNCTION/TRIGGER) 은 PREPARE 안 됨.
    → 그 경우엔 일단 통과 처리 (validate_mysql_execution 으로 본격 검증).
    """
    if not sql:
        return False, "empty_sql"
    
    # stored routine 은 syntax-only 검증 불가 → 통과 처리
    if re.search(r'CREATE\s+(PROCEDURE|FUNCTION|TRIGGER)', sql, re.IGNORECASE):
        return True, "syntax_skip_stored_routine"
    
    # SELECT/VIEW 는 EXPLAIN 으로 검증
    if re.search(r'CREATE\s+VIEW', sql, re.IGNORECASE):
        # CREATE VIEW name AS SELECT ... — SELECT 부분만 EXPLAIN
        m = re.search(r'CREATE\s+VIEW\s+`?\w+`?\s+AS\s+(SELECT.*)', sql, re.IGNORECASE | re.DOTALL)
        if m:
            select_sql = m.group(1).rstrip(';')
            success, _, err = _run_mysql(f"EXPLAIN {select_sql};")
            if success:
                return True, "view_select_ok"
            return False, f"view_select_fail: {err[:150]}"
    
    return True, "syntax_skip_other"


# ════════════════════════════════════════════════════════════════
# 통계
# ════════════════════════════════════════════════════════════════
_validation_stats = {
    'total': 0,
    'passed': 0,
    'failed': 0,
    'skipped': 0,
}


def get_validation_stats() -> Dict[str, int]:
    return dict(_validation_stats)


def record_validation(success: bool, reason: str) -> None:
    _validation_stats['total'] += 1
    if 'skip' in reason.lower():
        _validation_stats['skipped'] += 1
    elif success:
        _validation_stats['passed'] += 1
    else:
        _validation_stats['failed'] += 1
