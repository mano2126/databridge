# DataBridge 근본 재설계 — 본부장님 본질 비전
## 2026-05-14 결정 — 다음 세션 시작 시 첫 메시지로 사용

---

## ▶ 보존 (commercial 자산)

- ✅ Pattern KB v3.0 (49패턴) — 변환 패턴 라이브러리
- ✅ Pattern Auto-Extract — 새 패턴 자동 학습
- ✅ Ollama (내부 sLLM) — 망분리 환경 본질
- ✅ 4-Layer 비전 자체

## ▶ 제거 (양파 구조)

- ❌ hotfix_023 Rule Engine (TVF→SP Python 변환)
- ❌ R-100~R-127 정화 룰 27개
- ❌ hotfix_014 KB 게이트 5종 검사 (false positive)
- ❌ 객체 변환쌍 KB (commercial 무용지물)
- ❌ hotfix_102~108 (오늘 추가한 양파)

## ▶ 새 아키텍처 (3-Phase)
## ▶ 본질 결정

- KB Auto-Growth (객체쌍) = commercial 무용지물 (100개 객체 + 도메인 다양성 매칭 0%)
- Pattern 라이브러리 = 진짜 자산 (다음 고객사도 작동)
- Docker 의존 X (사용자 환경 다양성)
- Transaction 검증 본질 — MySQL DDL implicit commit 제약 검토 필요

## ▶ 본부장님 통찰 (2026-05-14)

1. "다람쥐 쳇바퀴" — 증상 처방 자동화 함정 인식
2. "100개 + 망분리" — commercial 본질 검증
3. "KB 포기 고민" — 본질로 답 (Pattern KB 보존)
4. "사용자 db 환경 너무 다양" — Docker 의존 X
5. "외부 LLM 별도 환경" — 망분리 보안 정책 본질

## ▶ 다음 세션 작업

### Session N+1: 양파 매핑 (1-2시간)
- 본부장님 27개+ hotfix 각각 본질? 양파?
- 의존성 그래프 (어떤 hotfix 가 어떤 hotfix 의존)
- 안전 제거 순서 결정
- 진짜 본질 코드 식별 (Pattern KB, Auto-Extract, sLLM 호출)

### Session N+2: 단순화 빌드 (2-3시간)
- 양파 제거 (단계별)
- Transaction 검증 본질 처방
- 단순화된 코드 검증

### Session N+3: commercial 시나리오 검증
- 본부장님 AdventureWorks 35개로 검증
- "다음 고객사 100개" 시뮬레이션
- Pattern KB 성장 추적

## ▶ 본부장님 모토

"본질에 충실, 신중하게, 한방에" — 임시방편 아니라 근본 해결

---

**다음 세션 시작 메시지**:
"이 NEXT_SESSION_BRIEF.md 를 봐줘. 어제 결정한 방향으로 양파 매핑 작업 시작하자."

