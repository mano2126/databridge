# DataBridge Studio — 변환 규칙 폴더 (trans/)

## 폴더 구조
```
trans/
├── mssql_to_mysql/       ← SQL Server → MySQL (JSON 10개, 규칙 431개)
├── mysql_to_mssql/       ← MySQL → SQL Server (JSON 4개, 규칙 171개)
├── mssql_to_postgresql/  ← (준비중 — JSON 추가 시 자동 활성화)
├── mysql_to_postgresql/  ← (준비중)
├── oracle_to_mysql/      ← (준비중)
├── oracle_to_postgresql/ ← (준비중)
├── postgresql_to_mysql/  ← (준비중)
└── postgresql_to_mssql/  ← (준비중)
```

## JSON 규칙 파일 형식
```json
{
  "_meta": { "title": "...", "src_db": "mssql", "tgt_db": "mysql", "version": "1.0" },
  "rules": [
    {
      "id":      "고유ID",
      "src":     "변환할 패턴 (리터럴 또는 정규식)",
      "tgt":     "변환 결과",
      "regex":   true,        ← 정규식 여부 (false면 리터럴 치환)
      "warning": false,       ← 경고 출력 여부
      "note":    "설명",
      "category":"DATATYPE"
    }
  ]
}
```

## 규칙 추가 방법
1. 해당 폴더의 JSON 파일에 규칙 추가
2. 새 파일은 `NN_category.json` 형식으로 저장 (숫자 순서대로 로드)
3. 서버 재시작 없이 적용 (LRU 캐시 사용, 재시작 시 자동 갱신)

## 파일 명명 규칙
- `01_datatypes.json`        — 데이터 타입 변환
- `02_ddl_table.json`        — CREATE/ALTER TABLE
- `03_functions_datetime.json` — 날짜/시간 함수
- `04_functions_string.json`   — 문자열 함수
- `05_functions_math_system.json` — 수학/시스템 함수
- `06_procedure_syntax.json`  — 프로시저/함수 구문
- `07_trigger_syntax.json`    — 트리거 구문
- `08_query_dml.json`         — SELECT/DML
- `09_window_functions.json`  — 윈도우 함수
- `10_view_function_syntax.json` — 뷰/함수 구문
