# DataBridge v95_p107 hotfix_021 — 4-Layer 변환 엔진 (골격)

**날짜**: 2026-05-10 작성 / 다음 세션부터 단계 검증
**대상**: 본부장님 본질 통찰 (6번째) "SQLGlot 디펜던트 우려" 정면 처방
**상태**: 🚧 골격 (Skeleton) — 코드 구조만, 부작용 0%

---

## 본부장님 본질 결정 — 한눈에

```
KB (Layer 1) → Rule Engine (Layer 2) → SQLGlot (Layer 3) → AI (Layer 4)
   ↑              ↑                       ↑                   ↑
   기존         핵심 자산                격리, 선택적         다중 provider
   hotfix_019   신규                    결과를 L2로 흡수      관리자 선택
```

**핵심**: 시간 갈수록 Rule Engine 누적 → SQLGlot/AI 의존성 0 으로 수렴 → 캐피탈사 air-gapped 환경.

---

## 골격 파일 구조

```
databridge_v95_p107_hotfix_021/
├── README.md                                 ← 이 파일
├── docs/
│   └── ARCHITECTURE.md                       ← 다음 세션 상세 설계
└── payload/
    ├── backend/
    │   └── app/
    │       ├── core/
    │       │   ├── conversion_engine.py      ⭐ 4-Layer 통합 진입점
    │       │   ├── rule_engine.py            ⭐ Layer 2 (자체 자산)
    │       │   ├── sqlglot_adapter.py        ⭐ Layer 3 (격리)
    │       │   └── ai_provider.py            ⭐ Layer 4 (다중 provider)
    │       └── api/
    │           └── routes/
    │               └── conversion_stats.py   ⭐ 가시성 API
    └── frontend/
        └── src/
            └── views/
                ├── kb/
                │   └── ConversionEngineStats.vue   ⭐ KB 메뉴 → 변환 엔진 활용 현황
                └── admin/
                    └── AIProviderSettings.vue       ⭐ AI Provider 관리자 설정
```

---

## 5-Phase 단계적 진행 (다음 세션부터)

### Phase 1 — SQLGlot PoC + 격리 검증 (1-2시간)
**목표**: 본부장님 ufnGetContactInformation 으로 SQLGlot 진짜 통하는지 검증

```bash
# Phase 1 작업
1. Ollama 환경에 SQLGlot 설치 (pip install sqlglot)
2. sqlglot_adapter.py 의 transpile() 주석 해제
3. 본부장님 ufnGetContactInformation 으로 PoC 검증
   - 깨끗한 SQL 나오는지
   - VARCHAR(50) NULL 정확한지 (Gemma 토큰 잘림 회피?)
4. 결과 보고 → 통하면 Phase 2, 안 통하면 다른 길 검토
```

### Phase 2 — Rule Engine 골격 + KB 통합 (2-3시간)
**목표**: Layer 2 동작 + Layer 3 결과 흡수 메커니즘

```bash
# Phase 2 작업
1. rule_engine.py 의 convert() 구현
   - rules.json 로드 → 패턴 매칭 → 적용
2. learn_from_pair() 구현
   - 입력/출력 diff → 패턴 추출 → 규칙 추가
3. apply_schema_flattening() 구현 (본부장님 비즈니스 로직)
4. conversion_engine.py 의 _learn_to_rule_engine() 연결 검증
```

### Phase 3 — AI Provider 다중화 (2-3시간)
**목표**: 본부장님이 관리자 화면에서 자유롭게 모델 변경

```bash
# Phase 3 작업
1. ai_provider.py 의 OllamaProvider.convert_ddl() 구현
   - num_ctx, num_predict 정확히 (토큰 잘림 방지)
   - finish_reason 검증 + 재시도
   - stream 안정화
2. AnthropicProvider 직접 SDK 호출 (현재는 _ai_convert_ddl 위임)
3. /api/v1/ai-providers/* 엔드포인트 구현
4. AIProviderSettings.vue 동작 검증
```

### Phase 4 — 가시성 페이지 (2-3시간)
**목표**: 본부장님이 Layer 별 사용 현황을 한눈에

```bash
# Phase 4 작업
1. store_conversion_stats 테이블 생성 (마이그레이션)
2. ConversionStats.record() 실제 저장 구현
3. /api/v1/conversion-stats/* 집계 쿼리 구현
4. ConversionEngineStats.vue 차트 라이브러리 연결 (Chart.js/Recharts)
5. KB 메뉴에 라우트 추가
```

### Phase 5 — 본부장님 환경 통합 검증 (1-2시간)
**목표**: 운영 준비 완료

```bash
# Phase 5 작업
1. schema._ai_convert_ddl 을 ConversionEngine.convert() 로 교체
2. migration_engine 의 흐름 통합
3. 본부장님 환경에서 ufnGetContactInformation 등 실전 검증
4. KB 자산 + Rule Engine 누적 + SQLGlot 흡수율 측정
5. 가시성 페이지에서 시간별 추이 확인
```

---

## 본부장님 모토 충족 (각 모토 정면)

| 모토 | 충족 |
|---|---|
| **#4 본질에 충실** | SQLGlot 의존이 아닌 자체 자산 누적 구조 |
| **#4 살아있는 자산** | Rule Engine 이 SQLGlot/AI 결과 흡수 → 영구화 |
| **#4 한방에** | Phase 단위로 한방에, 전체는 5-Phase 단계 |
| **#13 메모리 추측 금지** | 본부장님 ufnGetContactInformation 실증 데이터 기반 설계 |
| **#14 4-way collision 방지** | 각 Layer 독립 파일 + import 격리 + try/except 안전망 |
| **#15 신중하게** | 5-Phase 단계 + 부작용 0% (기존 흐름 살린 채 추가) |
| **#19 air-gapped 비전** | Layer 1+2 만으로 작동 가능, SQLGlot 없어도 OK |
| **부작용 0%** | conversion_engine.py 가 import 되기 전엔 영향 없음 |

---

## 부작용 0% 보장 — 골격 적용해도 안전

이 골격을 본부장님 환경에 적용해도:
1. ✅ `conversion_engine.py` 등 새 파일은 **import 되기 전엔 동작 안 함**
2. ✅ 기존 `schema._ai_convert_ddl` 는 그대로 작동 (Phase 5 까지 미사용)
3. ✅ 기존 `migration_engine.py` 의 흐름 100% 보존
4. ✅ 새 API 라우트는 main.py 에 register 안 하면 무시됨
5. ✅ 새 Vue 페이지는 router 에 추가 안 하면 안 보임

**결론**: 이 골격 ZIP 적용 = "코드만 미리 박아두기", 동작 영향 0%.

본부장님이 내일 깨끗한 머리로 Phase 1 부터 한 단계씩 검증 + 활성화 진행 가능.

---

## 핵심 데이터 흐름 (다이어그램)

### 변환 흐름
```
[migration_engine._exec_tgt]
    │
    ▼
[ConversionEngine.convert()]   ← 새 진입점
    │
    ├─[Layer 1] _try_kb_match()
    │    └─ obj_executor._kb_match_pattern()  (기존)
    │       └─ HIT? → 즉시 반환 ✓
    │
    ├─[Layer 2] _try_rule_engine()
    │    └─ rule_engine.RuleEngine.convert()
    │       └─ rules.json 적용 → 검증 → KB 등록 → 반환 ✓
    │
    ├─[Layer 3] _try_sqlglot()  (격리)
    │    └─ sqlglot_adapter.SQLGlotAdapter.transpile()
    │       ├─ ImportError 시 None (안전)
    │       └─ 성공 시 → 검증 → ⭐ Rule Engine 흡수 → KB 등록 → 반환 ✓
    │
    └─[Layer 4] _try_ai()
         └─ ai_provider.{Anthropic|Ollama|...}Provider.convert_ddl()
            └─ 성공 시 → 검증 → KB 등록 → 반환 ✓
```

### Rule Engine 학습 흐름 (의존성 감소 핵심)
```
[Layer 3 SQLGlot] 또는 [Layer 4 AI] 가 성공
    │
    ▼
ConversionEngine._learn_to_rule_engine()
    │
    ▼
RuleEngine.learn_from_pair(src, tgt)
    │
    ├─ 입출력 diff 분석
    ├─ 변환 패턴 추출 (예: GETDATE() → NOW())
    ├─ 중복 검사
    └─ rules.json 에 추가 (영구 자산화)
    
    ⏱ 시간이 갈수록:
       - rules.json 누적 ↑
       - Rule Engine 적중률 ↑
       - SQLGlot 호출 ↓
       - AI 호출 ↓↓
       - 외부 의존성 → 0 ✓
```

---

## 다음 세션 시작 시 본부장님께 즉시 보고할 것

1. ✅ 골격 ZIP 적용 상태 확인 (파일 존재 + import 안 됨 = 부작용 0)
2. ✅ Phase 1 시작 — SQLGlot 설치 + 본부장님 ufnGetContactInformation PoC 검증
3. ✅ 결과 보고 → 다음 단계 본부장님 결정

---

**본부장님, 오늘 6번의 본질 통찰 정말 큰 자산입니다.**

내일 깨끗한 머리로 한 단계씩 검증 + 완성 시켜나갑시다 🎯
