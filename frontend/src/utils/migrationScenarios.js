/**
 * migrationScenarios.js — 이관 시나리오 정의 (v90)
 *
 * 본부장님 통찰:
 * "DB 선택 후 '왜 이관하는지' 를 먼저 선언 → 시스템 전체가 자동 적용"
 *
 * 사용처:
 *   - JobWizard Step 0 의 시나리오 선택 UI
 *   - PrivacyPanel 의 default 정책 자동 결정
 *   - AI DBA 의 컨텍스트 prompt
 */

export const MIGRATION_SCENARIOS = [
  {
    id: 'prod_to_dev',
    name: '운영 → 개발',
    icon: '🛠️',
    description: '개발자가 운영 데이터로 디버깅/조회 테스트',
    sourceEnv: 'production',
    targetEnv: 'development',
    piiPreset: 'dev_environment',
    piiAutoStart: true,
    riskLevel: 'high',
    legalNote: '개인정보보호법 §28의2 (가명정보 처리)',
    tooltip: '같은 원본 → 같은 가짜값 (조인 보존). 정합성 테스트 가능.',
    advisorContext: '개발 환경 이관입니다. 인덱스/통계는 운영과 동일 유지하되, ' +
                    '데이터는 가명화되므로 PK/FK 무결성만 검증해주세요.',
    badge: { text: '권장: 가명화', color: '#3b82f6' },

  },
  {
    id: 'prod_to_qa',
    name: '운영 → QA',
    icon: '🧪',
    description: 'QA/테스트 — Critical 등급 PII 만 마스킹',
    sourceEnv: 'production',
    targetEnv: 'qa',
    piiPreset: 'qa_environment',
    piiAutoStart: true,
    riskLevel: 'medium',
    legalNote: '개인정보보호법 §24 (고유식별정보)',
    tooltip: '주민번호/카드 등 Critical 만 마스킹. 일반 정보는 그대로.',
    advisorContext: 'QA 환경 이관입니다. 운영과 동일한 스키마/인덱스 유지가 중요. ' +
                    'Critical PII 만 마스킹되므로 테스트 시나리오 영향 최소.',
    badge: { text: '권장: 부분 마스킹', color: '#f59e0b' },
  },
  {
    id: 'prod_to_analytics',
    name: '운영 → 분석/통계',
    icon: '📊',
    description: 'BI/통계 — 해시 + 일반화. 개인 식별 불가.',
    sourceEnv: 'production',
    targetEnv: 'analytics',
    piiPreset: 'analytics',
    piiAutoStart: true,
    riskLevel: 'low',
    legalNote: '개인정보보호법 §28의2 (가명정보)',
    tooltip: '집계는 가능, 개인 식별은 불가. BI 도구 안전.',
    advisorContext: '분석/통계 환경 이관입니다. 인덱스보다 파티셔닝/컬럼 압축 ' +
                    '같은 분석 워크로드 최적화를 권고해주세요.',
    badge: { text: '권장: 해시', color: '#8b5cf6' },
  },
  {
    id: 'prod_to_dr',
    name: '운영 → 운영 (DR 복제)',
    icon: '🔁',
    description: 'DR/백업 — 데이터 그대로 복제',
    sourceEnv: 'production',
    targetEnv: 'production',
    piiPreset: 'production_clone',
    piiAutoStart: false, // DR 은 PII 탐지 불필요
    riskLevel: 'critical',
    legalNote: '개인정보보호법 §29 (안전성 확보)',
    tooltip: 'PII 마스킹 없음. DR/재해복구 용도. 별도 접근통제 필수.',
    advisorContext: 'DR 사이트 이관입니다. 운영과 100% 동일한 환경 유지. ' +
                    '인덱스/제약조건/트리거 모두 그대로 복제.',
    badge: { text: '그대로 복제', color: '#ef4444' },
    warning: '⚠️ PII 노출 가능 — 타겟 DB 접근권한 운영급으로 제한 필수',
  },
  {
    id: 'dev_to_dev',
    name: '개발 → 개발',
    icon: '💻',
    description: '개발 환경 간 이동 — 마스킹 불필요',
    sourceEnv: 'development',
    targetEnv: 'development',
    piiPreset: 'production_clone',
    piiAutoStart: false,
    riskLevel: 'low',
    legalNote: '— (PII 없음 가정)',
    tooltip: '이미 가명화된 개발 데이터 이동. 마스킹 추가 불필요.',
    advisorContext: '개발 → 개발 이관입니다. 가벼운 검증만 필요.',
    badge: { text: '마스킹 불필요', color: '#10b981' },
  },
  {
    id: 'gdpr_compliant',
    name: 'GDPR 준수',
    icon: '🇪🇺',
    description: 'EU 시민 데이터 — 가명화 + 매핑테이블',
    sourceEnv: 'production',
    targetEnv: 'development',
    piiPreset: 'gdpr_compliant',
    piiAutoStart: true,
    riskLevel: 'high',
    legalNote: 'GDPR Art. 4(5), Art. 25 (Privacy by Design)',
    tooltip: 'EU 일반개인정보보호규정 준수. 매핑테이블로 복원 가능.',
    advisorContext: 'GDPR 준수 이관입니다. 가명화 매핑테이블을 별도 보관하며, ' +
                    '데이터 주체 권리(삭제/이전 등) 처리 가능하게 설계해주세요.',
    badge: { text: '권장: 가명화+매핑', color: '#06b6d4' },
  },
  {
    id: 'pci_dss',
    name: 'PCI-DSS 준수',
    icon: '💳',
    description: '카드/CVV 완전 제거 — 결제 시스템',
    sourceEnv: 'production',
    targetEnv: 'qa',
    piiPreset: 'pci_dss',
    piiAutoStart: true,
    riskLevel: 'critical',
    legalNote: 'PCI-DSS Requirement 3.4',
    tooltip: '카드번호/CVV 영구 제거. 결제 토큰화 권장.',
    advisorContext: 'PCI-DSS 준수 이관입니다. 카드/CVV 컬럼은 완전 마스킹 또는 ' +
                    '제거. 결제 토큰 컬럼이 별도로 있다면 그것만 유지.',
    badge: { text: 'PCI-DSS', color: '#dc2626' },
  },
  {
    id: 'custom',
    name: '사용자 정의',
    icon: '⚙️',
    description: '컬럼별로 직접 정책 선택',
    sourceEnv: 'custom',
    targetEnv: 'custom',
    piiPreset: 'custom',
    piiAutoStart: true,
    riskLevel: 'unknown',
    legalNote: '직접 검토 필요',
    tooltip: '복합 시나리오 — Step 4 에서 컬럼별 정책 직접 선택.',
    advisorContext: '사용자 정의 이관입니다. 표준 권고를 제시하되 사용자 결정 우선.',
    badge: { text: '컬럼별 선택', color: '#64748b' },
  },
]

/** 시나리오 ID 로 시나리오 정의 찾기 */
export function getScenario(scenarioId) {
  return MIGRATION_SCENARIOS.find(s => s.id === scenarioId) || null
}

/** 시나리오 ID → PII Preset ID */
export function scenarioToPiiPreset(scenarioId) {
  const sc = getScenario(scenarioId)
  return sc ? sc.piiPreset : 'dev_environment'
}

/** 시나리오 ID → AI DBA 컨텍스트 */
export function scenarioToAdvisorContext(scenarioId) {
  const sc = getScenario(scenarioId)
  return sc ? sc.advisorContext : ''
}

/** 자동 PII 탐지 시작 여부 */
export function shouldAutoStartPii(scenarioId) {
  const sc = getScenario(scenarioId)
  return sc ? !!sc.piiAutoStart : false
}

/** 위험도별 색상 */
export function getRiskColor(level) {
  return {
    low: '#10b981',
    medium: '#f59e0b',
    high: '#3b82f6',
    critical: '#dc2626',
    unknown: '#64748b',
  }[level] || '#64748b'
}
