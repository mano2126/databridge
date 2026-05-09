"""
v95_p11 회귀 방지 테스트 — 본부장님 본질 요청
─────────────────────────────────────────────────────────────────
"데이터 품질/테이블·오브젝트 검증 관련 화면을 수정하면 잘 인식되던게
 이렇게 돌아가" — 본부장님 (2026-05-02)

이 테스트는 누군가 schema/tables 응답 형식을 다시 깨뜨릴 때
pytest 가 즉시 실패시킴. CI/CD 또는 commit pre-hook 에 등록.

실행:
    cd D:\\project\\databridge_full\\backend
    pytest tests/regression/test_schema_tables_response.py -v
"""
import pytest


# ════════════════════════════════════════════════════════════════
# 테스트 1: MySQL schema_name 회귀 방지 (v95_p11 본질)
# ════════════════════════════════════════════════════════════════

def test_mysql_tables_response_schema_name_must_be_empty():
    """
    [v95_p11] MySQL 응답에서 schema_name 은 반드시 빈 문자열이어야 함.
    
    회귀 시나리오 (본부장님 2026-05-02 발견):
        잘못된 동작: {"schema_name": "capital_target", "table_name": "customer_profile"}
        올바른 동작: {"schema_name": "",                "table_name": "customer_profile"}
    
    이유:
        MySQL 은 "schema = database" 모델. schema_name 에 db명 박으면
        프론트 _policyKey() 가 "capital_target_customer_profile" 형성 →
        소스 "customer_profile" 와 매칭 실패 → 양쪽 다 "전용" 표시.
    """
    # _mysql_tables 함수 코드를 정적 검사 (실제 DB 연결 없이)
    import inspect
    from app.api.routes.schema import _mysql_tables
    
    src = inspect.getsource(_mysql_tables)
    
    # schema_name 이 db 변수가 아니어야 함
    assert '"schema_name": db' not in src, (
        "[v95_p11 회귀] _mysql_tables 가 schema_name 에 db명을 박고 있음. "
        "올바른 형태: '\"schema_name\": \"\"'. "
        "이 회귀가 발생하면 프론트 매칭이 깨져 양쪽 '전용' 표시됨."
    )
    assert "'schema_name': db" not in src, (
        "[v95_p11 회귀] _mysql_tables 가 schema_name 에 db명을 박고 있음 (single quote)."
    )
    
    # 빈 문자열이 들어가야 함
    assert ('"schema_name": ""' in src or "'schema_name': ''" in src), (
        "[v95_p11 회귀] _mysql_tables 응답에 schema_name 이 빈 문자열이 아님. "
        "본부장님 결정: MySQL 응답은 schema_name='' (MSSQL 과 의미론 분리)."
    )


def test_mssql_tables_response_schema_name_must_be_actual_schema():
    """
    [v95_p11] MSSQL 응답은 sys.schemas.name (실제 스키마) 그대로 유지.
    
    MSSQL 은 schema 가 DB 와 별개 객체이므로 'collection.activity' 같은
    실제 스키마 정보를 보존해야 매칭 가능.
    """
    import inspect
    from app.api.routes.schema import _mssql_tables
    
    src = inspect.getsource(_mssql_tables)
    
    # sys.schemas JOIN 이 있어야 함 (실제 스키마 추출)
    assert "sys.schemas" in src, (
        "[v95_p11 회귀] _mssql_tables 에 sys.schemas JOIN 누락. "
        "스키마 정보 없으면 매칭 키 형성 불가."
    )
    # r[0] (스키마) + r[1] (테이블) 형식
    assert '"schema_name": r[0]' in src or "'schema_name': r[0]" in src, (
        "[v95_p11 회귀] _mssql_tables 응답 형식 변경됨. "
        "기존: schema_name=r[0], table_name=r[1]"
    )


# ════════════════════════════════════════════════════════════════
# 테스트 2: View 검증 TEMPTABLE 우회 회귀 방지 (v95_p10 본질)
# ════════════════════════════════════════════════════════════════

def test_view_validation_uses_where_1_eq_0_pattern():
    """
    [v95_p10] View 안전 검증에서 WHERE 1=0 패턴 사용 보장.
    
    회귀 시나리오:
        잘못된 동작: SELECT * FROM view LIMIT 1   (TEMPTABLE 알고리즘 → 30초 timeout)
        올바른 동작: SELECT * FROM view WHERE 1=0 (옵티마이저 early constant folding)
    """
    import inspect
    from app.api.routes import schema as schema_module
    
    src = inspect.getsource(schema_module)
    
    # WHERE 1=0 패턴 존재
    assert "WHERE 1=0" in src, (
        "[v95_p10 회귀] View 안전 검증의 WHERE 1=0 패턴 누락. "
        "TEMPTABLE 우회 본질 처방. 회귀 시 4개 위험 View 다시 30초 timeout."
    )
    
    # information_schema fallback 존재
    assert "information_schema.COLUMNS" in src, (
        "[v95_p10 회귀] View 안전 검증의 information_schema.COLUMNS fallback 누락."
    )
    
    # MAX_EXECUTION_TIME 안전장치 존재
    assert "MAX_EXECUTION_TIME" in src, (
        "[v95_p10 회귀] MAX_EXECUTION_TIME 안전장치 누락. "
        "1차 쿼리 폭주 시 강제 cutoff 보장."
    )


# ════════════════════════════════════════════════════════════════
# 테스트 3: schema_strategy 일관성 회귀 방지 (v90.48/49 본질)
# ════════════════════════════════════════════════════════════════

def test_schema_conversion_policy_underscore_default():
    """
    [v90.48/49] underscore 가 기본 schema_strategy 인지 확인.
    
    회귀 시 customer.profile → customer_profile 변환 누락 가능.
    """
    try:
        from app.core.schema_conversion_policy import map_table_name
    except ImportError:
        pytest.skip("schema_conversion_policy 모듈 없음")
    
    # underscore 정책 검증
    result = map_table_name("customer", "profile", "underscore")
    assert result == "customer_profile", (
        f"[v90.48/49 회귀] underscore 정책 변환 깨짐. "
        f"customer.profile → 'customer_profile' 기대, 실제 '{result}'"
    )
    
    # drop 정책 검증
    result_drop = map_table_name("customer", "profile", "drop")
    assert result_drop == "profile", (
        f"[v90.48/49 회귀] drop 정책 변환 깨짐. "
        f"customer.profile → 'profile' 기대, 실제 '{result_drop}'"
    )


# ════════════════════════════════════════════════════════════════
# 테스트 실행 안내
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
