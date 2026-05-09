# DataBridge Studio — 개선 사항 (2026-03-21)

## 적용 방법

아래 파일들을 각각 해당 경로에 덮어쓰세요.

```
backend/app/core/store.py          ← 신규 생성
backend/app/api/routes/connector.py
backend/app/api/routes/jobs.py
backend/app/api/routes/settings.py
frontend/src/api/index.js
frontend/src/pages/Dashboard.vue
frontend/src/pages/Report.vue
frontend/src/pages/Plugins.vue
```

## 변경 내역

### 백엔드
**1. `app/core/store.py` (신규)**
- JSON 파일 기반 영속성 레이어
- `backend/data/` 폴더에 자동 저장 (`jobs.json`, `profiles.json`, `schedules.json`, `settings.json`)
- 서버 재시작해도 Job 목록·프로파일·스케줄·설정 모두 유지됨
- Thread-safe (lock 사용), atomic write (tmp → rename)

**2. `connector.py`**
- `_profiles` dict → `Store("profiles")` 로 교체 → 재시작해도 프로파일 유지
- `PUT /profiles/{pid}` API 추가 (프로파일 수정)
- 실제 DB 연결 실패 시 Mock 대신 실제 에러 메시지 반환

**3. `jobs.py`**
- `_jobs`, `_schedules` → `Store` 로 교체 → 재시작해도 Job 목록 유지
- `_job_logs`는 메모리 전용 유지 (로그는 재시작 시 삭제 — 의도적)
- Job 완료/실패 시 자동으로 파일에 flush

**4. `settings.py`**
- `_settings` → `Store("settings")` 로 교체 → 시스템 설정 영속화
- 기본값과 저장값을 merge하는 `_cfg()` 함수로 항상 안전한 값 반환
- `ANTHROPIC_API_KEY` 환경변수가 있으면 환경변수 우선

### 프론트엔드
**5. `api/index.js`**
- `settingsApi.get/update` URL 수정 (`/settings/` 로 통일)
- `scheduleApi` 추가 (스케줄 CRUD)
- `sqlApi`, `schemaApi.connect/deps/objects/warnings` 추가
- `connectorApi.updateProfile` 추가

**6. `Dashboard.vue`**
- 하드코딩 제거 → `jobsApi.list()` + `jobsApi.stats()` 실제 API 연동
- `/health` 엔드포인트 호출로 백엔드 상태 실시간 확인
- 빠른 이동 버튼 2개 추가 (SQL 변환기, 실행 리포트)

**7. `Report.vue`**
- 하드코딩 데이터 제거 → 실제 Job 목록 API 연동
- 상태 필터, 상세 모달, CSV 내보내기 기능 추가

**8. `Plugins.vue`**
- 빈 페이지 → 완성된 플러그인 마켓 UI
- 검색, 카테고리 필터, 설치/제거/업데이트 인터랙션 구현
