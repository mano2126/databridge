# MSSQL → MySQL 변환 규칙 시스템

## 구조

```
backend/
├── mssql_to_mysql/              ← 카테고리별 규칙 JSON 파일
│   ├── 01_datatypes.json        데이터 타입 변환 (47개)
│   ├── 02_ddl_table.json        DDL/테이블/인덱스/제약조건 (38개)
│   ├── 03_functions_datetime.json  날짜/시간 함수 (47개)
│   ├── 04_functions_string.json  문자열 함수 (40개)
│   ├── 05_functions_math_system.json  수학/시스템/변환 함수 (55개)
│   ├── 06_procedure_syntax.json  프로시저/함수 구문 (45개)
│   ├── 07_trigger_syntax.json   트리거 구문 (30개)
│   ├── 08_query_dml.json        쿼리/DML/CTE/페이징 (35개)
│   ├── 09_window_functions.json  윈도우 함수 (20개)
│   └── 10_view_function_syntax.json  뷰/스칼라함수/TVF (25개)
│
└── load_conv_rules.py           규칙 로더 — sql_converter.py 업데이트
```

## 규칙 추가 방법

### 1. 새 규칙 JSON에 항목 추가

```json
{
  "id": "고유 ID",
  "src": "MSSQL 소스 패턴",
  "tgt": "MySQL 변환 결과",
  "note": "설명",
  "warning": false,        // true면 ⚠ 표시
  "regex": false,          // true면 src를 정규식으로 사용
  "category": "카테고리명"
}
```

### 2. 로더 실행

```cmd
cd D:\project\databridge_full\backend
venv\Scripts\activate
python load_conv_rules.py
python -m uvicorn main:app --port 8000
```

## 규칙 JSON 필드

| 필드 | 필수 | 설명 |
|------|------|------|
| id | ✓ | 고유 식별자 (중복 없게) |
| src | ✓ | MSSQL 소스 (리터럴 또는 정규식) |
| tgt | ✓ | MySQL 변환 대상 |
| note | ✓ | 변환 설명 |
| warning | - | true = 수동 검토 필요 |
| regex | - | true = src가 정규식 |
| category | - | 카테고리명 |

## 새 카테고리 파일 추가

파일명을 `11_새카테고리.json` 형식으로 만들고 위 구조 참고.
`load_conv_rules.py` 실행 시 자동으로 포함됩니다.

## ⚠ 주의 항목

- INSERTED/DELETED 테이블 (트리거 내 JOIN) → MySQL 미지원
- TOP n PERCENT → 서브쿼리 필요
- MERGE → ON DUPLICATE KEY UPDATE로 재작성
- TVF (테이블 반환 함수) → 뷰/프로시저로 대체
- DATEDIFF — 인자 순서 반대 (MSSQL: 단위,시작,끝 / MySQL: 끝,시작)
- CHARINDEX vs LOCATE — 인자 순서 동일하지만 동작 확인 필요
