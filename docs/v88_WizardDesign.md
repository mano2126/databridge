# DataBridge — v88 Wizard Design

> 🎯 **이 문서의 목적**
> v86 JobWizard(5단계)를 v88 6단계로 확장하고, 핵심 차별화 지점인 **Stage 4 AI DBA 분석 & 권고**를 상세 설계한다.
> 모든 Stage 4 구현은 이 문서로 돌아와 검증한다.

**Version:** 1.0 (확정)
**Last Updated:** 2026-04-23
**Author:** 본부장님 × Claude
**관련 문서:** `DataBridge_Vision.md`

---

## 1. 위저드 전체 구조 (v86 → v88)

### 1.1. 최종 확정 6단계

| # | 라벨 | 역할 한 줄 | v86 대응 |
|:---:|:---|:---|:---:|
| 1 | **DB 선택** | 소스/타겟 DB + 변환 엔진 선택 | Step 0 |
| 2 | **객체 선택** | 테이블/SP/Function/Trigger/View 선별 | Step 1 |
| 3 | **변환 규칙** (타입 호환성) | 타입 정규화 + 변환 경고 자동수정 | Step 2 |
| 4 | **★ AI DBA 분석 & 권고** | 구조·성능 관점 4대 카테고리 권고 | ❌ 신규 |
| 5 | **실행 옵션** | 배치/병렬/모드/스케줄 | Step 3 |
| 6 | **검토 & 실행** | 최종 확인 + Dry-run + GO | Step 4 |

### 1.2. 단계 분리 원칙

**Stage 3 vs Stage 4 — 성격이 다르므로 반드시 분리한다.**

| | Stage 3. 변환 규칙 | Stage 4. AI DBA 권고 |
|:---|:---|:---|
| 분석 단위 | **타입 단위** (DATETIMEOFFSET 등) | **구조·성능 단위** (파티션/인덱스/SP) |
| 질문 | "이관이 **되느냐**?" (호환성) | "이관 후 **잘 도느냐**?" (최적화) |
| 결과 | 자동 수정 on/off 토글 | 권고 수용/거부/부분수용 |
| 실패 시 | 이관 불가 | 이관은 됨 (성능만 저하) |

### 1.3. 위저드 밖에 유지할 것

- **사전점검 (PrecheckDrawer)** — Stage 1/2에서 언제든 슬라이드로 펼침. 위저드 단계에 넣지 않음.
- **검증 + 리포트 (MigrationReport)** — 이관 실행 후 자동 이동하는 별도 페이지. Hero Moment 전용 UI.

### 1.4. 단계 스킵 규칙

- **Stage 3 스킵**: 소스/타겟이 같은 DB 그룹이면 `needsNormStep()==false` → Stage 4로 점프
- **Stage 4 스킵**: 사용자가 "원본 그대로 이관" 버튼 클릭 시 → Stage 5로 점프 (`form.advisorSkipped = true`)

---

## 2. Stage 4 상세 설계

### 2.1. 화면 최상단 구조

```
┌─────────────────────────────────────────────────────────────┐
│  🧠 AI DBA Consultant                                        │
│  선택된 이관 대상을 종합 분석하여 최적화 권고를 제시합니다.  │
│  이관 = 최적화의 유일한 기회                                │
├─────────────────────────────────────────────────────────────┤
│  [선택 대상 요약 바]                                         │
│  ▤ 테이블 47  │  ⚙ 프로시저 12  │  ƒ 함수 8  │  ⚡ 0  │ 👁 3│
├─────────────────────────────────────────────────────────────┤
│  [분석 모드 선택 — 3-tier]                                   │
│  ...                                                         │
└─────────────────────────────────────────────────────────────┘
```

### 2.2. ★ 3-Tier 분석 모드 (v88 핵심 결정)

**리스크 허용도에 따라 사용자가 직접 선택**한다. 본부장님 결정: 금융권·핵심 시스템은 "비용이 아니라 실패 불가"가 기본 감각이므로 Deep 모드를 정식 옵션으로 제공.

| 항목 | 🟢 **경제형** (Default) | 🟡 **균형형** | 🔴 **전수 분석** |
|:---|:---|:---|:---|
| **내부명** | `smart` | `hybrid` | `deep` |
| **전체명** | Smart Analysis | Hybrid Analysis | Deep Analysis |
| **규칙 필터** | 1차 스크리닝 | 1차 스크리닝 | 1차 스크리닝 |
| **AI 분석 범위** | HIGH 후보만 (약 15%) | HIGH + MED 후보 (약 40%) | **전체 대상 100%** |
| **예상 토큰** | ~5~20K | ~30~80K | ~150~500K+ |
| **예상 시간** | 30초~1분 | 1~3분 | 3~10분+ |
| **추천 대상** | 일반 이관, 반복 이관 | 중요 이관, 첫 이관 | **핵심 시스템·금융·장애 시 영향 큰 시스템** |
| **UI 경고** | 없음 | 없음 | **빨간색 강조 + 2단계 확인 다이얼로그** |

#### 2.2.1. 비용 산정 공식

비용은 AI 호출 없이 **규칙 기반으로 사전 계산**한다 (UI의 "예상 비용" 표시용).

```python
# app/core/advisor/base_advisor.py 에 구현됨
_MODE_COEFFICIENTS = {
    "smart":  {"rate_tables": 0.15, "rate_objects": 0.15, ...},
    "hybrid": {"rate_tables": 0.40, "rate_objects": 0.40, ...},
    "deep":   {"rate_tables": 1.00, "rate_objects": 1.00, ...},
}
# Claude Sonnet 4 기준: Input $3/M, Output $15/M
cost_usd = (tokens_in * 3 + tokens_out * 15) / 1_000_000
```

**계수(0.15, 0.40)는 P6의 `advisor_learner`가 실측값으로 자동 갱신**한다. 첫 100회 이관 동안 추정치 → 이후 정확한 실측치로 수렴.

#### 2.2.2. Deep 모드 확인 다이얼로그

```
┌──────────────────────────────────────────────────┐
│ ⚠  전수 분석 확인                                │
│                                                  │
│ 예상 비용: ~$1.90 (약 ₩2,600)                   │
│ 예상 시간: ~8분                                  │
│                                                  │
│ 이 모드는 다음 경우에 권장됩니다:                │
│  ✓ 핵심 거래 시스템 이관                         │
│  ✓ 금융/원장 DB 이관                             │
│  ✓ 장애 시 외부 영향이 큰 시스템                 │
│  ✓ 첫 이관이고 향후 KB 축적이 목적인 경우        │
│                                                  │
│ [ 취소 ]              [ 이해했습니다 · 시작 ]    │
└──────────────────────────────────────────────────┘
```

### 2.3. 4개 카테고리 Advisor

각 Advisor는 **독립적인 백엔드 모듈**(`app/core/advisor/{table,object,index,server}_advisor.py`).
공통 인터페이스:

```python
class BaseAdvisor(ABC):
    category: Category   # "table" | "object" | "index" | "server"

    @abstractmethod
    def analyze(self, selection: JobSelection, context: AnalysisContext) -> list[Recommendation]:
        ...

    @abstractmethod
    def estimate_tokens(self, selection: JobSelection, mode: AnalysisMode) -> dict:
        ...

    def supports(self, src_db: str, tgt_db: str) -> bool:
        return True   # 기본: 모두 지원. 필요 시 자식 클래스가 재정의
```

`Recommendation` 공통 스키마 (이미 `base_advisor.py`에 정의됨):
- `id`, `category`, `severity`, `title`, `target`, `reason`
- `before`, `after`, `estimated_impact`
- `auto_applicable`, `default_action`, `source`, `confidence`, `rule_id`
- `decision` (applied/skipped/edited/pending), `edited_sql`

#### ① TableAdvisor (`table_advisor.py`) — P3

대용량 테이블 파티셔닝, 컬럼 타입 오버스펙, PK 전략(UNIQUEIDENTIFIER→BINARY(16)), 통계 자동갱신 설정.

#### ② ObjectAdvisor (`object_advisor.py`) — P4

WHERE 컬럼 함수 래핑, CURSOR→Set-based 재작성, SELECT *→명시 컬럼, WITH (NOLOCK) 변환 위험성.

#### ③ IndexAdvisor (`index_advisor.py`) — P5, 가장 복잡

쿼리 로그 있으면 실사용 기반, 없으면 SP/View WHERE·JOIN·ORDER BY 정적 분석. 중복/불필요 인덱스 탐지.

#### ④ ServerAdvisor (`server_advisor.py`) — P2, 가장 단순 → 먼저 구현

MySQL 타겟 기준 `innodb_buffer_pool_size`, `innodb_log_file_size`, `max_allowed_packet`, `innodb_flush_log_at_trx_commit` 등. `my.cnf` 패치 스니펫 + 적용 가이드 출력.

### 2.4. 권고 수용 메커니즘 (비전 문서 준수)

| 버튼 | 동작 |
|:---|:---|
| **일괄 적용** | 모든 HIGH/MED 권고를 `apply` |
| **권장만 적용** | `default_action == "apply"`인 것만 |
| **원본 그대로 이관** | 모든 권고 `skip` — 신뢰 보장 fallback |
| **AI 재분석** | 사용자 컨텍스트 추가 후 재호출 |
| 카드별 개별 토글 | 선별 수용 |

### 2.5. 지식 누적 훅 (Living Asset 원칙)

사용자 결정 시마다 `advisor_learner.py`(P6)가 `conversion_learner.py`와 동일한 패턴으로 KB 학습:
- `rule_id` 있으면 → 해당 규칙 confidence 갱신
- `rule_id` 없음(AI 신규 패턴) → shadow rule 저장, 3회 수용 시 active 승격
- 거부 권고 → 다음번 동일 패턴에서 severity 하향

**효과:** 박과장이 이관할 때마다 AI DBA가 똑똑해지고, AI 호출 비용이 점점 감소 (userMemories의 "지식 누적 flow" 원칙).

### 2.6. 백엔드 API (v88 P1 구현 범위)

| Endpoint | P1 상태 | 설명 |
|:---|:---:|:---|
| `POST /advisor/estimate-cost` | ✅ 구현 | 3-tier 모드별 예상 비용 산정 (AI 호출 없음) |
| `POST /advisor/analyze` | 🚧 placeholder | P2~P5에서 실제 4개 Advisor 호출로 교체 |
| `POST /advisor/refine` | ⏳ 503 | 특정 권고 AI 재질의 (P2+) |
| `POST /advisor/apply-decision` | ⏳ 503 | 권고 결정 반영 + KB 축적 (P6) |
| `GET  /advisor/health` | ✅ 구현 | 라우터 헬스체크 |

### 2.7. 프론트엔드 컴포넌트

| 파일 | P1 상태 |
|:---|:---:|
| `components/advisor/AdvisorPanel.vue` | ✅ 구현 (모드 선택 UI + 결과 placeholder) |
| `components/advisor/RecommendationCard.vue` | 🚧 P2+ |
| `components/advisor/BeforeAfterDiff.vue` | 🚧 P2+ |
| `api/advisor.js` | ✅ 구현 |

---

## 3. 구현 로드맵

### Phase 1 (완료 — 2026-04-23) ✅

**목표:** Wizard 6단계 확장 + Stage 4 뼈대 + 3-tier 비용 산정 UI

- ✅ `JobWizard.vue` 6단계 재배치 (`steps`, `cur===*`, `nextStep()`, `goStep()`, 검토화면 리뷰)
- ✅ `AdvisorPanel.vue` 구현 (3-tier 모드 카드, Deep 확인 다이얼로그, 결과 placeholder)
- ✅ `BaseAdvisor` 추상 인터페이스
- ✅ `Recommendation` 데이터클래스
- ✅ `estimate_analysis_cost()` 비용 산정 공식
- ✅ `/advisor/estimate-cost` 엔드포인트
- ✅ `/advisor/analyze` placeholder 엔드포인트
- ✅ `main.py` 라우터 등록
- ✅ form에 `advisorMode`, `advisorSkipped`, `advisorDecisions` 필드

### Phase 2 (다음 세션)

**목표:** ServerAdvisor 구현 (가장 단순, 전체 플로우 검증용 end-to-end 첫 사례)

- `server_advisor.py` — MySQL 타겟 기준 `my.cnf` 권고 생성기
- `/advisor/analyze`에 ServerAdvisor 연결
- `RecommendationCard.vue` 첫 구현 (Before/After 표시)
- `AdvisorPanel.vue`에 결과 리스트 렌더링

### Phase 3~6

- **P3** TableAdvisor (파티셔닝/오버스펙 규칙 엔진)
- **P4** ObjectAdvisor (SP 안티패턴 탐지, AI 중심)
- **P5** IndexAdvisor (정적 분석 fallback → 쿼리 로그 버전)
- **P6** `advisor_learner` 연결 + AdminKb 대시보드 확장

---

## 4. 결정 이력 (Decision Log)

### D1. 2026-04-23 — Stage 4 위치 결정
**이슈:** AI DBA 권고를 몇 번째 Stage에 둘 것인가?
**결정:** Stage 3(변환 규칙) 다음. 호환성 판단 → 최적화 판단의 자연스러운 흐름.
**근거:** 본부장님 제안 + "호환성 vs 최적화"는 질문 성격이 다르므로 분리.

### D2. 2026-04-23 — 3-Tier 분석 모드
**이슈:** AI 호출 비용을 어떻게 관리할 것인가?
**결정:** 단일 모드 대신 **리스크 허용도 기반 3-tier(smart/hybrid/deep)** 제공. smart 기본값.
**근거:** 본부장님 지적 — "리스크 큰 프로젝트는 비용 들어도 한 번은 돌려야". 금융권 타겟 시장과 정합.

### D3. 2026-04-23 — 6단계 vs 7단계
**이슈:** 비전 문서의 7-Stage 중 "사전점검"과 "검증+리포트"를 위저드 단계로 넣을까?
**결정:** 위저드 안은 6단계. 사전점검은 기존 Drawer 유지, 검증+리포트는 실행 후 별도 페이지.
**근거:** 위저드 플로우 길이 최소화. 사전점검은 언제든 펼 수 있어야 하고, 검증은 실행 후 산출물.

### D4. 2026-04-23 — Stage 4 항상 표시 vs 조건부
**이슈:** 권고가 나오지 않을 경우 Stage 4를 건너뛸까?
**결정:** 항상 표시. 권고 없을 때는 "✓ 이미 최적화됨" 축하 화면.
**근거:** 위저드 단계 수가 동적으로 바뀌면 UX 혼란. 사용자에게 "분석은 했다"는 확신 제공.

### D5. 2026-04-23 — "원본 그대로" 버튼 위치
**결정:** 상단 일괄 버튼으로만 제공 (각 카드별은 체크박스 선별로 대체).

### D6. 2026-04-23 — 권고 없을 때 처리
**결정:** "축하합니다 — 이미 최적화된 구성입니다 ✓" Hero 화면. P2에서 구체 디자인.

---

## 5. 주요 파일 맵

### P1 완료 파일
```
backend/
  main.py                                  [수정] advisor 라우터 등록
  app/core/advisor/
    __init__.py                            [신규]
    base_advisor.py                        [신규] 264줄 — 인터페이스 + 비용공식
  app/api/routes/
    advisor.py                             [신규] 198줄 — /estimate-cost 동작

frontend/
  src/pages/
    JobWizard.vue                          [수정] 6단계 재배치, 10개 지점 변경
  src/components/advisor/
    AdvisorPanel.vue                       [신규] 963줄 — 3-tier 모드 UI
  src/api/
    advisor.js                             [신규] 75줄 — API 래퍼
```

### 향후 추가 예정 파일
```
backend/app/core/advisor/
  server_advisor.py     P2
  table_advisor.py      P3
  object_advisor.py     P4
  index_advisor.py      P5
  advisor_learner.py    P6

frontend/src/components/advisor/
  RecommendationCard.vue   P2
  BeforeAfterDiff.vue      P2
  AdvisorCategoryTabs.vue  P2
  AdvisorSummaryBar.vue    P2
  AdvisorBulkActions.vue   P2
```

---

## 6. 다음 세션 시작 체크리스트

새 세션에서 이 문서를 열면 아래 순서로 진행:

1. **GitHub에서 레포 로드** (본부장님 작업 프로토콜)
2. **현재 Phase 확인** — 이 문서 섹션 3의 로드맵에서 "완료" 체크된 다음 Phase
3. **P2 작업 시작 시:** `server_advisor.py`부터 — MySQL 타겟 기준 `my.cnf` 권고 엔진이 가장 단순하고 전체 플로우 검증용으로 이상적

---

*This document is the single source of truth for Stage 4 implementation.*
*모든 Stage 4 기능 결정은 이 문서에 기록하여 세션 간 일관성을 유지한다.*
