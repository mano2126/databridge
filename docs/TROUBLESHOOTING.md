# DataBridge Studio — 트러블슈팅 FAQ

> 자주 발생하는 문제와 해결책.
> 이 문서로 해결 안 되는 이슈는 기술지원 연락.

---

## 이관 관련

### Q1. 이관 Job 이 "running" 상태로 멈춰있고 진행률이 안 올라가요

**점검 순서**:
1. `backend/logs/jobs/<job_id>.log` 마지막 100줄 확인
   ```bash
   tail -100 backend/logs/jobs/<job_id>.log
   ```
2. 대표적 원인:
   - 대용량 테이블 + 느린 bulk insert → `parallelTables` 값 낮춰보기
   - 타겟 DB 락 경합 → 다른 세션 확인
   - 네트워크 순단 → 소스/타겟 DB ping 테스트

**강제 종료 후 재실행**:
```sql
-- SQLite 직접 수정 (최후의 수단)
UPDATE store_jobs
SET value = json_set(value, '$.status', 'failed',
                           '$.error',  'manually terminated')
WHERE key = '<job_id>';
```
그 후 Job 목록에서 재실행 버튼 클릭.

### Q2. `_ai_convert_ddl: 빈 응답` 로그가 계속 나와요

**원인**: Claude API 호출은 성공했지만 응답 본문이 비어있음.
**조치**:
1. Anthropic API 키 유효성 확인 (관리자 UI → 시스템 설정 → 연결 테스트)
2. 해당 DDL 내용이 너무 커서 `max_tokens` 초과했을 가능성 — `max_tokens` 설정 상향 검토
3. 일시적 API 장애일 수 있음 — 몇 분 후 재시도

### Q3. MSSQL → MySQL 이관 시 `Illegal mix of collations` (1270) 발생

**원인**: MySQL 서버 기본 collation 과 생성된 테이블 collation 불일치.
**조치**:
1. 시스템 설정에서 **에러 KB** 탭 확인 — 1270 패턴이 등록되어 있어야 함 (v10 #17)
2. 재이관 시 **"AI 자동 교정"** 옵션 활성화
3. 수동 해결: 타겟 DB 에서 아래 실행
   ```sql
   ALTER DATABASE mydb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

### Q4. NVARCHAR 컬럼에 한글 데이터 깨짐

**원인**: 소스/타겟 collation 이 각각 `utf8_general_ci` 같이 한글 처리 부실.
**조치**: 타겟 DB/테이블/컬럼 **모두** `utf8mb4_unicode_ci` 또는 `utf8mb4_0900_ai_ci` 로 설정.

---

## UI / 브라우저

### Q5. `Invalid regular expression flags` 에러가 Console 에 떠요

**원인**: v10 #19 이전 버전에서 `/* ... */` 문자열이 데이터에 포함되어 발생했던 이슈.
**조치**: v10 #19b 이상 패치 적용 후 타입매핑 화면의 **[📦 기본 규칙 시드]** 버튼 → "전체 갱신" 선택.

### Q6. 저장된 프로파일 불러와도 다음 단계 버튼이 안 보여요

**원인**: 연결 테스트가 실패했거나 아직 미완료.
**조치**: 프로파일 카드 적용 후 **[다음 단계]** 버튼 근처에 파란색 pulse 효과가 6초간 나타나면 정상. 연결 상태 아이콘이 초록 ✓ 인지 확인.

### Q7. 새로고침(Ctrl+Shift+R) 후에도 이전 연결 상태가 남아있어요

**원인**: v10 #20 이전 버전.
**조치**: v10 #20b 이상 패치 적용. 패치 후에도 문제 있으면:
```js
// F12 Console
JSON.stringify(window.__pinia?._s?.get('connector')?.$state?.source)
```
`status: "ok"` 이면 v20b 미반영. 브라우저 캐시 강제 삭제 후 재시도.

### Q8. 타입 매핑 화면에서 규칙이 14개만 보여요

**원인**: v10 #19 이전 설치 → 283개 카탈로그 자동 시드 안 됨.
**조치**: **[📦 기본 규칙 시드]** 버튼 클릭. "추가 269개, 건너뜀 14개, 총 283개" 알림 확인.

---

## 성능

### Q9. 이관 속도가 너무 느려요

**확인 항목**:
- `form.bulkMode` 가 `auto` 또는 `bcp` (MSSQL 타겟)인지
- `form.batchSize` 5000 ~ 50000 범위 조정
- `form.parallelTables` 2~4 (DB 부하 고려)
- 네트워크 대역폭 측정 (`iperf3` 등)

**권장**:
- 10만 행 이하: `executemany`
- 10만~100만 행: `executemany` + 병렬 2~3
- 100만 행 이상: `bcp` (MSSQL) 또는 `LOAD DATA` (MySQL 타겟)

### Q10. 서버 메모리 사용량이 계속 증가해요

**점검**:
1. `GET /api/v1/health/detailed` 의 `active_jobs` 증가 추세?
2. 대량 이관 중이면 정상. 끝난 후에도 해제 안 되면 메모리 누수 의심.
3. 재기동 후에도 재발하면 해당 Job 의 재현 시나리오와 함께 기술지원 연락.

---

## 인증 · 권한

### Q11. 관리자 계정 비밀번호를 잊었어요

**극단적 복구** (시스템 접근 가능한 경우):
```bash
cd backend
python3 -c "
from app.core.auth import _reset_admin_password
_reset_admin_password('new_secure_password_here')
"
```
(이 함수 존재 여부는 해당 설치 버전에서 확인 필요. 없으면 DB 직접 수정.)

### Q12. `PERMISSION DENIED` 에러

**원인**: 현재 사용자 role 이 요청한 작업에 부족.
**확인**: UI 우측 상단 사용자 메뉴에서 role 확인. operator 이상 권한 필요한 작업 목록은 관리자 매뉴얼 참조.

---

## 백업 · 데이터

### Q13. 감사 로그 무결성 검증에서 `broken_at` 발견

**즉시 조치**:
1. 침해 사고로 간주하고 보안팀 보고
2. 해당 시점의 시스템 로그와 대조
3. 백업본에서 감사 로그 복원 검토
4. 접근 권한 전수 재검토

### Q14. SQLite DB 가 깨졌어요

```bash
# 1. 서비스 중지
docker compose stop

# 2. 손상 확인
sqlite3 backend/data/databridge.db "PRAGMA integrity_check;"

# 3. 복구 시도
sqlite3 backend/data/databridge.db ".recover" > recovered.sql
sqlite3 new_databridge.db < recovered.sql
mv backend/data/databridge.db backend/data/databridge.db.bad
mv new_databridge.db backend/data/databridge.db

# 4. 또는 최근 백업으로 복원
cp /backup/databridge_latest.db backend/data/databridge.db

# 5. 서비스 재기동
docker compose up -d
```

---

## AI / API 키

### Q15. AI 호출이 많아서 비용이 걱정됩니다

**확인**:
- 관리자 UI → 지식 베이스 관리 → 변환 KB 탭
- **AI 호출 추이 차트** 에서 일별 호출 수 확인
- 시간 지날수록 AI 호출이 감소해야 정상 (KB 학습 효과)

**최적화**:
- `shadow` 상태 규칙이 많다면 **confidence** 확인 후 수동 승격 고려
- 반복되는 DDL 패턴은 규칙에 직접 추가 (타입 매핑 / 오브젝트 매핑 화면)

### Q16. API 호출 속도 제한 (rate limit) 에 걸려요

**원인**: Anthropic API 의 분당 요청/토큰 제한 초과.
**조치**:
- 대량 이관 시 `parallelTables` 값을 낮춰서 동시 AI 호출 감소
- Anthropic 계정 tier 상향 검토
- 피크 시간 외로 이관 일정 조정

---

## 기타

### Q17. 로그에 주민번호/카드번호가 평문으로 찍혔어요 (중대)

**즉시 조치**:
1. 해당 로그 파일 보호 (복사 금지, 접근 제한)
2. 보안팀 + 개인정보보호 담당자 긴급 보고
3. 로그 파일 안전 폐기 절차 진행
4. 기술지원팀에 **재현 시나리오와 함께** 즉시 신고
5. PII 마스킹 필터가 설치됐는지 확인:
   ```bash
   grep "전역 PII 마스킹 필터 등록됨" backend/logs/databridge.log
   ```
   → 이 라인이 없으면 v10 #21 미적용 상태. 즉시 패치.

### Q18. 이관 Job 실행 직전에 "검토" 단계에서 경고가 떠요

경고 내용 읽고 판단:
- **데이터 손실 가능**: 타입 호환성 문제. 진행 전 샘플 데이터 재검토
- **컬럼 없음**: 소스/타겟 스키마 불일치. 매핑 재설정
- **주의 규칙 매칭**: 적어도 1개 컬럼이 "warning" 표시된 타입 변환 사용 중

경고 무시하고 진행은 가능하지만 **실패 시 책임은 사용자**.
