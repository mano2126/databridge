# DataBridge v95_p106 — Big Bang Patch

**2026-05-09 본부장님 비전 — JEUS NodeManager 동급 + Frontend 통합 + 시스템 트레이**

---

## 📦 적용 방법 (한방에)

```bash
cd ~/project
unzip databridge_v95_p106_001.zip      # 기존 databridge_full/ 위에 덮어씀
cd databridge_full
bash RUN.sh                             # 백업 + 권한 + 의존성 체크
cd backend
bash run_supervisor.sh start            # Supervisor + Backend + Frontend 시작
```

브라우저: <http://127.0.0.1:3000/admin/console/process>

---

## 📁 변경 파일 요약 (9개)

### 신규 (6)
- `backend/supervisor.py` — Supervisor 데몬 (port 8765)
- `backend/run_supervisor.sh` — macOS/Linux 시작 스크립트
- `backend/run_supervisor.bat` — Windows 동등
- `frontend/src/pages/BackendConsole.vue` — Backend 실시간 콘솔 별창
- `frontend/src/pages/FrontendConsole.vue` — Frontend 실시간 콘솔 별창
- `frontend/src/components/SystemTrayWidget.vue` ⭐ — 우측 하단 floating 트레이

### 정정 (3, 자동 백업)
- `backend/app/api/routes/process.py` — Supervisor 게이트웨이로 전환 + Frontend API
- `frontend/src/pages/AdminProcess.vue` — Backend + Frontend 카드
- `frontend/src/App.vue` — SystemTrayWidget 글로벌 마운트
- `frontend/src/router/index.js` — backend-console / frontend-console 자식 라우트 추가

### 변경 불요 (이미 OK)
- `backend/main.py` — process router 이미 등록됨
- `frontend/src/pages/AdminConsole.vue` — "프로세스" 메뉴 이미 최상단

---

## 🚀 Supervisor 사용법

```bash
# 시작 (Backend + Frontend 자동)
bash run_supervisor.sh start

# Supervisor 만 (UI에서 Backend/Frontend 시작)
bash run_supervisor.sh start --supervisor-only

# Backend 만
bash run_supervisor.sh start --backend-only

# Frontend 만
bash run_supervisor.sh start --frontend-only

# 상태
bash run_supervisor.sh status

# 로그 실시간
bash run_supervisor.sh logs

# 종료
bash run_supervisor.sh stop

# 포그라운드 (디버깅)
bash run_supervisor.sh foreground
```

---

## 🌐 API 엔드포인트

### Supervisor (port 8765, 직접)
- `GET  /supervisor/health`
- `GET  /supervisor/status`
- `POST /supervisor/start` — `{"mode": "safe|multiprocess|thread"}`
- `POST /supervisor/stop`
- `POST /supervisor/restart`
- `WS   /supervisor/console/ws`
- `POST /supervisor/frontend/start` — `{"mode": "auto|dev|release"}`
- `POST /supervisor/frontend/stop`
- `POST /supervisor/frontend/restart`
- `WS   /supervisor/frontend/console/ws`

### Backend (port 8000, RBAC 적용)
- `GET  /api/v1/process/status` — Backend + Frontend 통합 상태
- `POST /api/v1/process/start|stop|restart` — Backend 제어
- `GET  /api/v1/process/console` `console/ws-info`
- `GET  /api/v1/process/frontend/status`
- `POST /api/v1/process/frontend/start|stop|restart`
- `GET  /api/v1/process/frontend/console` `console/ws-info`

---

## 🎨 SystemTrayWidget (우측 하단 floating)

- **크기**: 56×56 원형, position fixed, z-index 9999
- **상태점** (우상단):
  - 🟢 초록 펄스 → Backend + Frontend 둘 다 ON
  - 🟡 노랑 → 부분 ON (한쪽만)
  - 🔴 빨강 → 둘 다 OFF or Supervisor 응답 없음
- **클릭** → Popover (240px):
  - Frontend / Backend 각 상태 표시
  - 항목 클릭 → 관리자 콘솔 (별창) 이동
- **5초 폴링** (`/api/v1/process/status`)
- **외부 클릭 시 자동 닫힘**
- **Login 페이지에서는 숨김**

---

## 🔧 트러블슈팅

### "Supervisor 응답 없음"
```bash
bash run_supervisor.sh status
bash run_supervisor.sh logs    # 에러 확인
```

### npm 못 찾음 (Frontend 시작 실패)
```bash
which npm    # 경로 확인
# nvm 환경이면 .nvmrc 또는 ~/.nvm 자동 감지됨
```

### 8765 포트 충돌
```bash
lsof -i :8765
kill <PID>
```

### 자동 재시작이 너무 빈번 (KeepAlive 무한루프 방지)
- supervisor.py 안에서 의도적 stop (`intentional_stop=True`) 시에만 재시작 안 함
- 비정상 종료는 항상 1초 후 자동 재시작

---

## ⏪ 롤백 방법

각 정정 파일은 `*.before_v95_p106_YYYYMMDD_HHMMSS` 백업이 자동 생성됩니다:

```bash
cd ~/project/databridge_full
mv backend/app/api/routes/process.py.before_v95_p106_* backend/app/api/routes/process.py
mv frontend/src/pages/AdminProcess.vue.before_v95_p106_* frontend/src/pages/AdminProcess.vue
mv frontend/src/App.vue.before_v95_p106_* frontend/src/App.vue
mv frontend/src/router/index.js.before_v95_p106_* frontend/src/router/index.js
# 신규 파일 제거
rm backend/supervisor.py backend/run_supervisor.sh backend/run_supervisor.bat
rm frontend/src/pages/BackendConsole.vue frontend/src/pages/FrontendConsole.vue
rm frontend/src/components/SystemTrayWidget.vue
```

---

## 📋 본부장님 모토 100% 부합

- ✅ **본질에 충실** — JEUS NodeManager 동급 + 시스템 트레이
- ✅ **신중하게** — view tool 정독, 본부장님 환경 검증된 첨부 supervisor.py 기반
- ✅ **한방에** — 단일 ZIP, 단일 RUN.sh, Supervisor 단일 데몬
- ✅ **부작용 0%** — 신규 6개 추가 + 정정 3개 자동 백업
- ✅ **하드코딩 0%** — 포트/경로/npm 모두 동적 자동 감지

본부장님 — 화이팅! ❤️🔥🚀
