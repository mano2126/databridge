# DataBridge Studio v2.0 — 통합 수정 패키지

## 적용 파일 목록

### Backend
| 파일 | 경로 |
|------|------|
| jobs.py | backend/app/api/routes/ |
| schema.py | backend/app/api/routes/ |
| validate.py | backend/app/api/routes/ |
| db_conn.py | backend/app/core/ |
| load_conv_rules.py | backend/ |
| mssql_to_mysql/*.json | backend/mssql_to_mysql/ |

### Frontend
| 파일 | 경로 |
|------|------|
| Monitor.vue | frontend/src/pages/ |
| JobWizard.vue | frontend/src/pages/ |
| index.js | frontend/src/api/ |

## 배포 방법

### 1. 파일 교체
```
backend/app/api/routes/jobs.py     → D:\project\databridge_full\backend\app\api\routes\
backend/app/api/routes/schema.py   → D:\project\databridge_full\backend\app\api\routes\
backend/app/api/routes/validate.py → D:\project\databridge_full\backend\app\api\routes\
backend/app/core/db_conn.py        → D:\project\databridge_full\backend\app\core\
backend/load_conv_rules.py         → D:\project\databridge_full\backend\
backend/mssql_to_mysql/            → D:\project\databridge_full\backend\mssql_to_mysql\
frontend/src/pages/Monitor.vue     → D:\project\databridge_full\frontend\src\pages\
frontend/src/pages/JobWizard.vue   → D:\project\databridge_full\frontend\src\pages\
frontend/src/api/index.js          → D:\project\databridge_full\frontend\src\api\
```

### 2. 변환 규칙 로드 (선택)
```cmd
cd D:\project\databridge_full\backend
venv\Scripts\activate
python load_conv_rules.py
```

### 3. 서버 재시작
```cmd
cd D:\project\databridge_full\backend
venv\Scripts\activate
python -m uvicorn main:app --port 8000
```

```cmd
cd D:\project\databridge_full\frontend
npm run dev
```

## 주요 수정 내역

### jobs.py
- create_job: objects/convert_objects/src_port/tgt_port 저장 추가 (핵심!)
- _connect_src: MSSQL 포트 1434 자동 인식
- _connect_tgt MySQL: autocommit=True (오류 1422 방지)
- do_exec: schema.py의 _rule_based_ddl_convert 직접 호출
- bulk-delete: /{jid} 앞에 등록 (405 오류 방지)

### schema.py
- _rule_based_ddl_convert: MSSQL→MySQL 실제 변환 실행 블록 추가
- PROCEDURE/FUNCTION/TRIGGER: DROP+CREATE 두 문장 분리
- FUNCTION: DETERMINISTIC 자동 추가
- TRIGGER: RAISERROR 있으면 AFTER→BEFORE 변환, ROLLBACK 제거
- pymysql: autocommit=True

### db_conn.py
- make_mssql_conn: 핸드셰이크 오류(08001) 시 0.5초 후 자동 재시도

### validate.py
- _connect: make_mssql_conn 사용 (드라이버 자동선택 + 재시도)

### Monitor.vue
- checkedIds: ref(new Set()) → ref([]) (Vue 3 반응성)
- 페이지네이션: 10/25/50 단위
- 일괄 삭제: 체크박스 선택 후 일괄 삭제

### JobWizard.vue
- nextStep: Job명 미입력 시 placeholder 자동 채움 (Step 3→4 전환 막힘 방지)

### api/index.js
- bulkDel: .then(d) 추가 (405 → 정상 응답)
