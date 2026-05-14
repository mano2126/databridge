"""
DataBridge Post-Execution Verifier — hotfix_035
====================================================

본부장님 17번째 본질 통찰 정면 처방:
  "AI 변환 성공  ≠  MySQL 객체 생성 성공"
  화면 "✓ 성공" 표시되지만 실제로는 MySQL 에 없는 본질.

처방:
  AI 가 SQL 반환 → 실행 시도 → 결과 → MySQL 에서 객체 존재 확인 → 화면 정확 표시
  
검증 단계:
  1. AI 반환 SQL → MySQL 실행 시도
  2. 실행 결과 ERROR 캡쳐
  3. 객체 이름 후보 추출 (다양한 prefix 패턴)
  4. MySQL information_schema 에서 진짜 존재 확인
  5. 진짜 존재하면 → success=True
     없으면 → success=False (화면에 정확히 실패 표시)

본부장님 모토 #14 (정확한 표현) 정면.
"""
from __future__ import annotations
import re
import subprocess
import logging
from typing import Tuple, Optional, List, Dict

_log = logging.getLogger("databridge.post_exec_verifier")


def _run_mysql_query(sql: str, db: str = "AdventureWorks2022",
                     container: str = "db_mysql", timeout: int = 10) -> Tuple[bool, str]:
    """MySQL 쿼리 실행 (결과 반환용)."""
    try:
        cmd = ['docker', 'exec', '-i', container,
               'mysql', '-uroot', '-pBridge@1234', db, '-N', '-s']
        r = subprocess.run(cmd, input=sql, capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout or '').strip()
    except Exception as e:
        return False, str(e)


def _generate_name_candidates(obj_schema: str, obj_name: str,
                                obj_type: str) -> List[str]:
    """객체 이름의 다양한 후보 생성 (AI 변환 결과 추적용).
    
    본부장님 환경 데이터 기반 (실제 발견된 패턴):
      ufnGetStock              → dbo_ufnGetStock
      uspGetWhereUsedProductID → production_uspGetWhereUsedProductID  
      iuPerson                 → Person_iuPerson_update / Person_iuPerson_insert
      iduSalesOrderDetail      → Sales_iduSalesOrderDetail_DELETE
      ufnLeadingZeros          → dbo_ufnLeading_zeros (snake_case 변환!)
    """
    schema_lower = obj_schema.lower() if obj_schema else 'dbo'
    schema_capital = obj_schema if obj_schema else 'dbo'
    
    candidates = [
        # 가장 일반적 패턴
        f"{schema_capital}_{obj_name}",                # Sales_uSalesOrderHeader
        f"{schema_lower}_{obj_name}",                  # sales_uSalesOrderHeader
        f"dbo_{obj_name}",                              # dbo_ufnGetStock
        obj_name,                                       # 원본 (드물게)
    ]
    
    # TRIGGER 의 경우 _insert/_update/_delete 접미사
    if obj_type and obj_type.upper() == 'TRIGGER':
        # iuPerson → Person_iuPerson_update / Person_iuPerson_insert
        for suffix in ['_insert', '_update', '_delete', '_INSERT', '_UPDATE', '_DELETE']:
            candidates.append(f"{schema_capital}_{obj_name}{suffix}")
            candidates.append(f"{schema_lower}_{obj_name}{suffix}")
            candidates.append(f"dbo_{obj_name}{suffix}")
    
    # snake_case 변환 시도 (ufnLeadingZeros → ufn_leading_zeros 등)
    snake = re.sub(r'(?<!^)(?=[A-Z])', '_', obj_name).lower()
    if snake != obj_name.lower():
        candidates.extend([
            f"{schema_capital}_{snake}",
            f"{schema_lower}_{snake}",
            f"dbo_{snake}",
            snake,
        ])
    
    return list(dict.fromkeys(candidates))  # 중복 제거


def verify_object_exists_in_mysql(
    obj_schema: str,
    obj_name: str,
    obj_type: str,
    db: str = "AdventureWorks2022",
) -> Tuple[bool, Optional[str], List[str]]:
    """MySQL 에 객체가 진짜 존재하는지 확인.
    
    Args:
        obj_schema: MSSQL 스키마 (예: 'dbo', 'Sales')
        obj_name: MSSQL 객체 이름 (예: 'ufnGetStock')
        obj_type: 'PROCEDURE' | 'FUNCTION' | 'TRIGGER' | 'VIEW'
    
    Returns:
        (exists: 진짜 존재?, found_name: 발견된 실제 이름, candidates: 검사된 후보들)
    """
    candidates = _generate_name_candidates(obj_schema, obj_name, obj_type)
    
    obj_type_upper = obj_type.upper() if obj_type else ''
    
    # MySQL information_schema 에서 검색
    if obj_type_upper in ('PROCEDURE', 'FUNCTION'):
        # ROUTINES 테이블
        in_list = ", ".join(f"'{c}'" for c in candidates)
        sql = (
            f"SELECT ROUTINE_NAME FROM information_schema.ROUTINES "
            f"WHERE ROUTINE_SCHEMA = '{db}' "
            f"AND ROUTINE_TYPE = '{obj_type_upper}' "
            f"AND ROUTINE_NAME IN ({in_list}) "
            f"LIMIT 1;"
        )
    elif obj_type_upper == 'TRIGGER':
        in_list = ", ".join(f"'{c}'" for c in candidates)
        sql = (
            f"SELECT TRIGGER_NAME FROM information_schema.TRIGGERS "
            f"WHERE TRIGGER_SCHEMA = '{db}' "
            f"AND TRIGGER_NAME IN ({in_list}) "
            f"LIMIT 1;"
        )
    elif obj_type_upper == 'VIEW':
        in_list = ", ".join(f"'{c}'" for c in candidates)
        sql = (
            f"SELECT TABLE_NAME FROM information_schema.VIEWS "
            f"WHERE TABLE_SCHEMA = '{db}' "
            f"AND TABLE_NAME IN ({in_list}) "
            f"LIMIT 1;"
        )
    else:
        return False, None, candidates
    
    ok, result = _run_mysql_query(sql, db=db)
    
    if ok and result:
        found_name = result.split('\n')[0].strip()
        _log.info(
            "[v95_p107-OBJ-VERIFY-OK] %s [%s].[%s] → MySQL [%s] 존재 확인",
            obj_type, obj_schema, obj_name, found_name,
        )
        return True, found_name, candidates
    
    _log.warning(
        "[v95_p107-OBJ-VERIFY-FAIL] %s [%s].[%s] → MySQL 에 없음 "
        "(검사한 이름: %s)",
        obj_type, obj_schema, obj_name, candidates[:5],
    )
    return False, None, candidates


def verify_object_creation(
    obj_schema: str,
    obj_name: str,
    obj_type: str,
    tgt_ddl: str,
    db: str = "AdventureWorks2022",
) -> Dict:
    """객체 생성 검증 결과.
    
    Returns:
        {
            'created': bool,                # 진짜 만들어졌는지
            'actual_name': str | None,      # 실제 MySQL 이름
            'name_candidates': List[str],   # 검사한 후보들
            'verified_by': 'exists_check'
        }
    """
    exists, actual_name, candidates = verify_object_exists_in_mysql(
        obj_schema, obj_name, obj_type, db,
    )
    return {
        'created': exists,
        'actual_name': actual_name,
        'name_candidates': candidates,
        'verified_by': 'exists_check',
    }
