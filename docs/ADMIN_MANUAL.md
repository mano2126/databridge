# DataBridge Studio — 관리자 매뉴얼

> **대상**: 시스템 운영자, 보안 담당자, 감사 담당자
> **버전**: v2.0 기준 (v10 #21 패치 포함)

---

## 1. 설치 및 초기 구성

### 1.1 요구 환경

| 항목 | 최소 | 권장 |
|---|---|---|
| OS | Linux / Windows Server 2019+ | Ubuntu 22.04 LTS |
| Python | 3.11 | 3.11 |
| Node.js (빌드) | 18 | 20 |
| RAM | 4GB | 16GB 이상 |
| 디스크 | 20GB 여유 | 100GB (이관 로그 고려) |
| Docker (선택) | 24.x | 최신 안정판 |

### 1.2 docker-compose 배포 (권장)

```bash
cd /opt/databridge
docker compose up -d
# 기동 확인
curl http://localhost:8000/health
```

### 1.3 수동 설치

```bash
# 백엔드
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000

# 프론트엔드
cd frontend
npm ci
npm run build              # dist/ 를 백엔드 static 에 연결
```

### 1.4 초기 관리자 계정

최초 기동 시 기본 관리자 계정이 생성됩니다. 첫 로그인 후 **반드시 비밀번호 변경** 하세요.

```
기본 ID: admin
기본 PW: (설치 문서 별도 제공)
```

---

## 2. 일상 운영

### 2.1 헬스체크

| 엔드포인트 | 용도 | 인증 |
|---|---|---|
| `GET /health` | L4 로드밸런서 체크 | 불필요 |
| `GET /api/v1/health/detailed` | 운영자 상세 진단 | viewer+ |
| `GET /metrics` | Prometheus scrape | 불필요 (방화벽 제한 권장) |

**/api/v1/health/detailed 응답 예시**:
```json
{
  "ok": true,
  "version": "2.0.0",
  "uptime_sec": 86400,
  "database": {"ok": true, "store": "sqlite"},
  "disk": {"ok": true, "total_gb": 100.5, "used_pct": 34.2, "free_gb": 66.1},
  "active_jobs": 2,
  "api_key_configured": true
}
```

**Prometheus 메트릭 예시**:
```
databridge_uptime_seconds 86400
databridge_jobs_active 2
databridge_disk_used_percent 34.2
databridge_ai_calls_today 45
databridge_local_hits_today 180
databridge_patterns_learned_today 12
databridge_db_healthy 1
```

### 2.2 백업

내부 메타데이터는 `backend/data/databridge.db` 단일 SQLite 파일.

```bash
# 안전한 온라인 백업 (WAL 체크포인트 후)
sqlite3 backend/data/databridge.db ".backup '/backup/databridge_$(date +%Y%m%d).db'"

# 권장: 매일 02:00 cron
0 2 * * * /opt/databridge/scripts/backup.sh
```

백업 대상 경로:
- `backend/data/databridge.db` — 모든 메타/이력
- `backend/data/_migrated/` — 구 JSON 마이그레이션 흔적 (선택)
- `config/` — 외부 설정 (있을 경우)

### 2.3 로그

| 로그 | 경로 | 설명 |
|---|---|---|
| 애플리케이션 | `backend/logs/databridge.log` | 요청/에러/잡 실행 |
| 이관 상세 | `backend/logs/jobs/<job_id>.log` | 각 Job 별 상세 로그 |
| 감사 로그 | `backend/data/databridge.db` (store_audit_logs 테이블) | API 로 조회 |

**중요**: v10 #21 부터 **전역 PII 마스킹 필터** 가 자동 설치되어 로그에 주민번호/카드번호/계좌/전화/이메일 등이 절대 평문으로 기록되지 않습니다. 금융권 운영 시 필수.

---

## 3. 업그레이드 절차

### 3.1 패치 zip 적용 (표준 방식)

```bash
# 1. 현재 상태 백업
cp -r /opt/databridge /opt/databridge.bak.$(date +%Y%m%d)

# 2. 패치 해제 (기존 파일 덮어씀)
cd /opt
unzip databridge_patch_v10_21.zip

# 3. 의존성 업데이트 (requirements 변경된 경우)
cd databridge/backend
pip install -r requirements.txt

# 4. 프론트엔드 재빌드 (프론트 파일 바뀐 경우)
cd ../frontend
npm run build

# 5. 재기동
cd /opt/databridge
docker compose restart
# 또는 systemctl restart databridge
```

### 3.2 롤백

적용한 패치에 문제 있으면 백업 디렉토리로 복원:

```bash
cd /opt
rm -rf databridge
mv databridge.bak.YYYYMMDD databridge
docker compose restart
```

### 3.3 DB 스키마 마이그레이션

v10 #19 이후 `mapping_rules` 테이블에 `source`, `confidence`, `status` 등 필드 소프트 추가. 기존 규칙 레코드에는 이 필드가 없지만 코드에서 default 로 처리되어 호환. 별도 마이그레이션 스크립트 불필요.

---

## 4. 장애 대응

### 4.1 이관 Job 행잉 (응답 없음)

1. `GET /api/v1/health/detailed` 로 `active_jobs` 확인
2. `backend/logs/jobs/<job_id>.log` 마지막 라인 확인
3. 필요시 프로세스 강제 종료 후 Job 상태를 `failed` 로 수동 업데이트:
   ```bash
   # SQLite 직접 수정 (극단적 상황에만)
   sqlite3 backend/data/databridge.db
   > UPDATE store_jobs SET value=json_set(value, '$.status', 'failed')
     WHERE key='job_abc123';
   ```

### 4.2 디스크 부족

`/api/v1/health/detailed` → `disk.ok=false` 이면 즉시 조치:
- 오래된 Job 로그 정리: `backend/logs/jobs/` 내 30일 이전 파일 삭제
- 감사 로그 정리: 관리자 UI → 감사 로그 → "N일 이전 삭제"
  또는 API: `DELETE /api/v1/audit/purge?days=365`

### 4.3 API 키 오류

- 증상: AI 변환 실패, `API 키 없음` 에러
- 조치: 관리자 UI → 시스템 설정 → Anthropic API 키 재입력 → 연결 테스트

### 4.4 DB 파일 손상

WAL 체크포인트 실패, `database disk image is malformed` 등 증상 시:
```bash
# 1. 서비스 중지
docker compose stop
# 2. integrity 체크
sqlite3 backend/data/databridge.db "PRAGMA integrity_check"
# 3. 손상이 확인되면 백업에서 복원
cp /backup/databridge_YYYYMMDD.db backend/data/databridge.db
# 4. 서비스 재기동
docker compose up -d
```

---

## 5. 감사 및 컴플라이언스

### 5.1 감사 로그 무결성 (v10 #21)

모든 감사 로그 레코드는 SHA-256 해시 체인으로 연결됩니다. 누군가 과거 레코드를 변조하면 **이후 모든 레코드의 해시가 깨짐 → 탐지 가능**.

**정기 점검** (월 1회 권장):
```
GET /api/v1/audit/verify
```

응답 예시 (정상):
```json
{"ok": true, "total": 12853, "legacy": 0, "broken_at": null}
```

이상 감지 시:
```json
{
  "ok": false,
  "broken_at": "uuid-of-record",
  "broken_reason": "hash_mismatch",
  "expected_hash": "...",
  "actual_hash": "..."
}
```
즉시 해당 시각 시스템 로그 / 백업과 대조 필요.

### 5.2 감사 로그 보존 정책

금융권 권장: **최소 5년** 보존. 자동 정리는 관리자가 직접 실행:
```
DELETE /api/v1/audit/purge?days=1826
# 5년 = 365 * 5 + 1 (윤년)
```

### 5.3 민감정보 마스킹

v10 #21 전역 PII 필터로 자동 처리되는 대상:
- 주민번호 (뒷 7자리 마스킹)
- 신용카드 (앞 4 / 뒤 4 외 마스킹)
- 계좌번호 (뒷 4 외 마스킹)
- 전화번호 (중간 자리 마스킹)
- 이메일 (로컬 파트 마스킹, 도메인 유지)
- 공개 IP (뒷 두 옥텟 마스킹, 사설/로컬 IP 는 유지)
- API 키 (Anthropic sk-ant-, AWS AKIA)
- 로그의 `password=` `pwd:` 등 key-value

**확인**:
```
GET /api/v1/health/detailed 후 로그 확인 — 어떤 상황에도 평문 PII 가 로그에 찍히면 버그.
즉시 보고 요망.
```

---

## 6. 보안 체크리스트

운영 전 반드시 확인. 자세한 내용은 [SECURITY_CHECKLIST.md](./SECURITY_CHECKLIST.md) 참조.

- [ ] 기본 admin 비밀번호 변경 완료
- [ ] HTTPS (TLS 1.2 이상) 강제 — 리버스 프록시 (nginx/Apache) 구성
- [ ] 방화벽: `/metrics` 는 모니터링 서버에서만 접근
- [ ] Anthropic API 키가 평문 JSON 파일로 저장되지 않음 (자동 암호화 확인)
- [ ] 감사 로그 `/api/v1/audit/verify` 정기 실행 cron 등록
- [ ] 백업 스크립트 cron 등록
- [ ] 로그 파일 rotation 설정 (logrotate)
- [ ] DB 접속 계정 최소 권한 원칙 적용

---

## 7. 지원 연락처

- 기술 지원: (고객사 계약서 별도 기재)
- 보안 이슈 신고: security@databridge.example
- 긴급 장애 (24/7): (고객사 계약서 별도 기재)
