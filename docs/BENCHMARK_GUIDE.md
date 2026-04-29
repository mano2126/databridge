# DataBridge Studio — 벤치마크 가이드

> 성능 측정 시 일관된 방법론. 고객 제안 시 객관적 수치 제시용.

---

## 1. 측정 환경 표준

### 하드웨어 (기준 세트)
- **서버**: 16 vCPU / 64GB RAM / NVMe SSD (AWS m6i.4xlarge 동등)
- **네트워크**: 10Gbps (내부망), 1Gbps (WAN 시뮬레이션)
- **DB 서버**: 별도 인스턴스 (동일 사양)

### 소프트웨어
- DataBridge: 단일 인스턴스, Docker Compose 기본 설정
- 소스 DB: MSSQL 2019 / MySQL 8.0.35
- 타겟 DB: MySQL 8.0.35 / MSSQL 2022
- 측정 도구: `time`, `iostat`, Prometheus `/metrics`

---

## 2. 표준 테스트 데이터셋

### Small (스모크 테스트)
- 테이블 10개
- 100만 행
- 총 크기 500MB

### Medium (대표 케이스)
- 테이블 100개
- 1,000만 행
- 총 크기 10GB
- 주요 DDL 패턴 포함: PK, FK, 인덱스 3~5개, 트리거 2개

### Large (엔터프라이즈)
- 테이블 500개
- 1억 행
- 총 크기 100GB
- 오브젝트: 프로시저 50개, 함수 30개, 트리거 20개, 뷰 40개

### Industry (금융권 모의)
- 실제 캐피탈사 도메인 모사: 고객/계약/거래 테이블
- BLOB/TEXT 대용량 컬럼 포함
- 개인정보 암호화 컬럼 포함 (단방향)

---

## 3. 측정 지표

### 속도 (Throughput)
| 지표 | 단위 | 계산 |
|---|---|---|
| 행/초 | rows/s | 총 행 수 / 이관 시간(초) |
| GB/분 | GB/min | 총 크기 / 이관 시간(분) |
| 테이블/분 | tbl/min | 총 테이블 / 이관 시간(분) |

### 품질 (Correctness)
| 지표 | 측정 |
|---|---|
| 데이터 정합률 | `SELECT COUNT(*) / CHECKSUM` 소스·타겟 비교 |
| 스키마 정합률 | `information_schema.columns` 비교 |
| 오브젝트 변환 성공률 | 생성 성공 / 전체 오브젝트 |

### 자원
| 지표 | 측정 도구 |
|---|---|
| 서버 CPU 피크 | `top`, Prometheus |
| 서버 메모리 피크 | `free`, `/proc/meminfo` |
| 네트워크 | `iftop`, `/proc/net/dev` |
| DB I/O | `iostat -x` |

### AI 효율성 (DataBridge 특화)
| 지표 | 측정 위치 |
|---|---|
| 총 AI 호출 수 | `/api/v1/kb/conversion/metrics` |
| 로컬 KB 처리 비율 | `local_hits / (ai_calls + local_hits)` |
| 자동 학습 규칙 수 | `/api/v1/kb/conversion/overview` |
| 호출당 평균 비용 | input_tokens × $3/1M + output_tokens × $15/1M |

---

## 4. 실행 프로토콜

### 4.1 Cold Run (1회)
- 빈 KB, 빈 캐시 상태에서 실행
- AI 호출 수·비용 측정의 상한선 확인

### 4.2 Warm Run (3회 평균)
- Cold Run 후 동일 데이터셋으로 3회 반복
- 학습 효과 반영한 실제 운영 성능
- AI 호출 수가 감소해야 정상

### 4.3 Mixed Workload (선택)
- 동시 Job 2~4개 실행
- 병목 지점 파악 (CPU/메모리/DB 락)

---

## 5. 측정 스크립트 템플릿

```bash
#!/bin/bash
# benchmark.sh — 표준 측정

JOB_ID=$1  # DataBridge Job ID
OUTPUT_DIR=./bench_results/$(date +%Y%m%d_%H%M%S)
mkdir -p $OUTPUT_DIR

# 시작 메트릭 스냅샷
curl -s http://localhost:8000/metrics > $OUTPUT_DIR/metrics_before.txt
curl -s http://localhost:8000/api/v1/kb/conversion/overview > $OUTPUT_DIR/kb_before.json

# 이관 실행 (API 트리거)
START=$(date +%s)
curl -X POST http://localhost:8000/api/v1/jobs/$JOB_ID/start \
  -H "Authorization: Bearer $TOKEN"

# 완료 대기 (polling)
while true; do
    STATUS=$(curl -s http://localhost:8000/api/v1/jobs/$JOB_ID \
        -H "Authorization: Bearer $TOKEN" | jq -r .status)
    if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
        break
    fi
    sleep 5
done
END=$(date +%s)

# 종료 메트릭
curl -s http://localhost:8000/metrics > $OUTPUT_DIR/metrics_after.txt
curl -s http://localhost:8000/api/v1/kb/conversion/overview > $OUTPUT_DIR/kb_after.json
curl -s http://localhost:8000/api/v1/jobs/$JOB_ID > $OUTPUT_DIR/job_result.json

# 결과 요약
DURATION=$((END - START))
echo "Duration: ${DURATION}s" > $OUTPUT_DIR/summary.txt
jq -r '.rows_migrated' $OUTPUT_DIR/job_result.json >> $OUTPUT_DIR/summary.txt
```

---

## 6. 리포트 포맷

고객 제안용 벤치마크 리포트 1페이지 구성:

```
┌─────────────────────────────────────────────┐
│  DataBridge Studio — 벤치마크 결과          │
│  [날짜] 측정자: [이름]                       │
└─────────────────────────────────────────────┘

환경: 16 vCPU / 64GB RAM / NVMe SSD / 10Gbps
시나리오: MSSQL 2019 → MySQL 8.0 (10GB, 1000만 행)

속도 (3회 평균)
  • Cold Run:  XX분 YY초  (X,XXX rows/s)
  • Warm Run:  XX분 YY초  (X,XXX rows/s)

품질
  • 데이터 정합:   100.00%
  • 스키마 정합:   100.00%
  • 오브젝트 변환: XX / XX (XX%)

AI 효율
  • Cold Run AI 호출: XXX회
  • Warm Run AI 호출: XX회  (▼ XX% 절감)
  • 총 API 비용: $XX.XX

비교 (참고)
  • AWS DMS 대비 속도: +XX% / -XX%
  • 장점: AI 기반 오브젝트 자동 변환
  • 단점: (객관적으로 기재)
```

---

## 7. 공개 배포 원칙

- 벤치마크 결과는 **측정 환경·버전·날짜** 명시
- 경쟁 제품 비교는 **동일 조건** 보장 (한쪽 튜닝 금지)
- 불리한 결과도 숨기지 않음 (신뢰 기반)
- 고객별 환경이 다름 → "귀사 환경 파일럿 권장" 명시
