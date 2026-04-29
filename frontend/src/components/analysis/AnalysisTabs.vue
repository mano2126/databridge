<!--
  AnalysisTabs.vue — Stage 4 통합 Tab 컨테이너
  ============================================
  Phase F-1d (2026-04-25)

  Step 4 에 들어가는 "AI 분석 센터".
  - Tab 1: AI DBA Consultant (기존 AdvisorPanel)
  - Tab 2: PII Privacy Scanner (신규 PrivacyPanel)
  - Tab 3+ : 미래 (Compliance / Pre-Flight 등)

  부모 (JobWizard.vue) 에서 이 컴포넌트 하나만 사용하면
  내부의 두 패널을 알아서 관리.

  Props:
    selection — 부모의 form.selection
    sourceProfileId, targetDb — 소스/타겟 컨텍스트

  Events (부모로 그대로 forward):
    @update:advisor-mode, @update:advisor-decisions, @advisor-skip
    @update:privacy-preset, @update:privacy-decisions, @privacy-skip
    @update:privacy-scan-result
-->
<template>
  <div class="analysis-tabs">

    <!-- Tab 헤더 -->
    <div class="at-tab-header">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="at-tab-btn"
        :class="{ 'at-tab-active': activeTab === tab.id, 'at-tab-disabled': tab.disabled }"
        :disabled="tab.disabled"
        @click="!tab.disabled && handleTabClick(tab.id)"
      >
        <span class="at-tab-ico">{{ tab.icon }}</span>
        <span class="at-tab-label">{{ tab.label }}</span>
        <span v-if="tab.badge" class="at-tab-badge" :class="tab.badgeClass">{{ tab.badge }}</span>
        <!-- v90.4: 시나리오 배지 (PII 탭 옆 작은 깜박임) -->
        <span v-if="tab.scenarioBadge" 
              class="at-tab-scenario-badge"
              :class="tab.scenarioBadgeClass"
              :title="tab.scenarioTooltip">
          {{ tab.scenarioBadge }}
        </span>
      </button>
    </div>

    <!-- Tab 본문 -->
    <div class="at-tab-body">

      <!-- Tab 1: AI DBA Consultant -->
      <div v-show="activeTab === 'advisor'" class="at-tab-content">
        <AdvisorPanel
          :src-db="srcDb"
          :tgt-db="tgtDb"
          :selection="selection"
          :source-profile-id="sourceProfileId"
          :target-db="targetDb"
          :initial-analysis="initialAdvisorAnalysis"
          @update:mode="(m) => $emit('update:advisor-mode', m)"
          @update:decisions="(d) => {
            advisorDecisionCount = (d || []).length;
            $emit('update:advisor-decisions', d);
          }"
          @update:analysis="(a) => $emit('update:advisor-analysis', a)"
          @skip="$emit('advisor-skip')"
        />
      </div>

      <!-- Tab 2: PII Privacy Scanner -->
      <div v-show="activeTab === 'privacy'" class="at-tab-content">
        <PrivacyPanel
          :migration-scenario="migrationScenario"
          :selection="selection"
          :source-profile-id="sourceProfileId"
          :target-db="targetDb"
          @update:preset="(p) => $emit('update:privacy-preset', p)"
          @update:decisions="(d) => {
            privacyDecisionCount = (d || []).length;
            $emit('update:privacy-decisions', d);
          }"
          @update:scanResult="(r) => {
            privacyRiskLevel = r.summary?.compliance_risk || 'LOW';
            $emit('update:privacy-scan-result', r);
          }"
          @skip="$emit('privacy-skip')"
        />
      </div>

      <!-- Tab 3+ : 미래 확장 placeholder -->
      <div v-show="activeTab === 'compliance'" class="at-tab-content at-coming-soon">
        <div class="at-cs-icon">📋</div>
        <div class="at-cs-title">Compliance Check</div>
        <div class="at-cs-desc">
          ISMS-P / 개인정보보호법 / GDPR / PCI-DSS 자동 점검 (Phase F-2 예정)
        </div>
      </div>

      <div v-show="activeTab === 'preflight'" class="at-tab-content at-coming-soon">
        <div class="at-cs-icon">🚀</div>
        <div class="at-cs-title">Pre-Flight Assessment</div>
        <div class="at-cs-desc">
          이관 비용/시간/위험도 사전 진단 + 임원 보고서 자동 생성 (Phase G 예정)
        </div>
      </div>

    </div>

  </div>
</template>


<script setup>
import { ref, computed } from 'vue'
import AdvisorPanel from '@/components/advisor/AdvisorPanel.vue'
import PrivacyPanel from '@/components/privacy/PrivacyPanel.vue'

const props = defineProps({
  selection: { type: Object, default: () => ({}) },
  sourceProfileId: { type: String, default: '' },
  targetDb: { type: String, default: 'mysql' },
  // v90.5: AdvisorPanel 에 srcDb/tgtDb required - JobWizard 에서 전달받음
  srcDb: { type: String, default: 'mysql' },
  tgtDb: { type: String, default: 'mysql' },
  // v90: 이관 시나리오 (Step 0 에서 선택, 자식 PrivacyPanel 로 전달)
  migrationScenario: { type: String, default: '' },
  // v90.20: AdvisorPanel 분석 결과 복원용
  initialAdvisorAnalysis: { type: Object, default: null },
  // v90.20: 마지막으로 보던 탭 복원
  initialActiveTab: { type: String, default: 'advisor' },
})

const emit = defineEmits([
  'update:advisor-mode',
  'update:advisor-decisions',
  'update:advisor-analysis',  // v90.20: AdvisorPanel 전체 상태 (sessionStorage 보존용)
  'advisor-skip',
  'update:privacy-preset',
  'update:privacy-decisions',
  'update:privacy-scan-result',
  'privacy-skip',
  'tab-visited',  // v90.12: 탭 방문 추적용
])

// v90.20: 활성 탭 - 부모에서 받은 값으로 복원
const activeTab = ref(props.initialActiveTab || 'advisor')

// v90.12: 탭 클릭 핸들러 - 부모에 방문 알림
function handleTabClick(tabId) {
  activeTab.value = tabId
  emit('tab-visited', tabId)
}

// 각 탭의 의사결정 수 (badge 표시용)
const advisorDecisionCount = ref(0)
const privacyDecisionCount = ref(0)
const privacyRiskLevel = ref('')  // CRITICAL/HIGH/... — Privacy 탭 위험도

// 탭 정의
const tabs = computed(() => [
  {
    id: 'advisor',
    icon: '🧠',
    label: 'AI DBA Consultant',
    badge: advisorDecisionCount.value > 0 ? advisorDecisionCount.value : null,
    badgeClass: 'at-badge-info',
    disabled: false,
  },
  {
    id: 'privacy',
    icon: '🛡️',
    label: 'PII Privacy',
    badge: getPrivacyBadge(),
    badgeClass: getPrivacyBadgeClass(),
    disabled: false,
    scenarioBadge: getScenarioBadge(),  // v90.4: 시나리오 배지
    scenarioBadgeClass: getScenarioBadgeClass(),
    scenarioTooltip: getScenarioTooltip(),
  },
  {
    id: 'compliance',
    icon: '📋',
    label: 'Compliance',
    badge: 'Soon',
    badgeClass: 'at-badge-coming',
    disabled: true,
  },
  {
    id: 'preflight',
    icon: '🚀',
    label: 'Pre-Flight',
    badge: 'Soon',
    badgeClass: 'at-badge-coming',
    disabled: true,
  },
])

function getPrivacyBadge() {
  if (privacyDecisionCount.value > 0) return privacyDecisionCount.value
  if (privacyRiskLevel.value === 'CRITICAL') return '!'
  if (privacyRiskLevel.value === 'HIGH') return '!'
  return null
}

function getPrivacyBadgeClass() {
  if (privacyRiskLevel.value === 'CRITICAL') return 'at-badge-critical'
  if (privacyRiskLevel.value === 'HIGH') return 'at-badge-warn'
  return 'at-badge-info'
}

// v90.4: 시나리오 배지 (탭 옆 작은 ⚠️ 깜박임)
const SCENARIO_INFO_AT = {
  prod_to_dev:       { icon: '🛠️', name: '운영 → 개발',       riskLevel: 'high' },
  prod_to_qa:        { icon: '🧪', name: '운영 → QA',         riskLevel: 'medium' },
  prod_to_analytics: { icon: '📊', name: '운영 → 분석/통계',  riskLevel: 'low' },
  prod_to_dr:        { icon: '🔁', name: '운영 → DR 복제',    riskLevel: 'critical' },
  dev_to_dev:        { icon: '💻', name: '개발 → 개발',       riskLevel: 'low' },
  gdpr_compliant:    { icon: '🇪🇺', name: 'GDPR 준수',         riskLevel: 'high' },
  pci_dss:           { icon: '💳', name: 'PCI-DSS 준수',      riskLevel: 'critical' },
  custom:            { icon: '⚙️', name: '사용자 정의',       riskLevel: 'unknown' },
}

function getScenarioBadge() {
  const sc = SCENARIO_INFO_AT[props.migrationScenario]
  if (!sc) return null
  return sc.icon
}
function getScenarioBadgeClass() {
  const sc = SCENARIO_INFO_AT[props.migrationScenario]
  if (!sc) return ''
  // v90.17: 분석 완료(decision 있음)면 깜빡임 정지 - "이미 봤다" 신호
  const isAnalyzed = privacyDecisionCount.value > 0
  if (isAnalyzed) return 'at-scenario-info-static'
  // 미분석 + critical 시나리오는 빨간 깜박임
  if (sc.riskLevel === 'critical') return 'at-scenario-critical'
  if (sc.riskLevel === 'high') return 'at-scenario-high'
  return 'at-scenario-info'
}
function getScenarioTooltip() {
  const sc = SCENARIO_INFO_AT[props.migrationScenario]
  if (!sc) return ''
  return `${sc.name} 시나리오 적용 중 (Step 0 에서 변경 가능)`
}
</script>


<style scoped>
.analysis-tabs {
  display: flex; flex-direction: column;
}

.at-tab-header {
  display: flex;
  border-bottom: 2px solid var(--border-light, #e2e8f0);
  margin-bottom: 16px;
  gap: 4px;
  overflow-x: auto;
  padding-bottom: 0;
}
.at-tab-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 10px 16px;
  font-size: 13px; font-weight: 600;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  color: var(--text-tertiary, #94a3b8);
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}
.at-tab-btn:hover:not(:disabled) {
  color: var(--text-secondary, #64748b);
  background: var(--bg-secondary, #f8fafc);
}
.at-tab-active {
  color: var(--text-primary, #1e293b) !important;
  border-bottom-color: #0f766e !important;
}
.at-tab-disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
.at-tab-ico { font-size: 14px; }
.at-tab-label { font-size: 13px; }

.at-tab-badge {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 18px; height: 18px;
  padding: 0 5px;
  font-size: 10px; font-weight: 700;
  border-radius: 99px;
}
.at-badge-info {
  background: #e0f2fe; color: #0369a1;
}
.at-badge-warn {
  background: #fef3c7; color: #d97706;
}
.at-badge-critical {
  background: #fee2e2; color: #dc2626;
  animation: at-pulse 1.5s infinite;
}
.at-badge-coming {
  background: var(--bg-secondary, #f1f5f9);
  color: var(--text-tertiary, #94a3b8);
  font-size: 9px;
  text-transform: uppercase;
}
@keyframes at-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

.at-tab-body {
  min-height: 300px;
}

.at-coming-soon {
  display: flex; flex-direction: column; align-items: center;
  padding: 60px 20px;
  text-align: center;
  background: var(--bg-secondary, #f8fafc);
  border-radius: 8px;
  border: 1px dashed var(--border-light, #e2e8f0);
}
.at-cs-icon { font-size: 36px; margin-bottom: 12px; }
.at-cs-title {
  font-size: 16px; font-weight: 700;
  color: var(--text-primary, #1e293b);
  margin-bottom: 6px;
}
.at-cs-desc {
  font-size: 12px;
  color: var(--text-tertiary, #94a3b8);
}
/* ════════════════════════════════════════════════════════════
   v90.4: 시나리오 배지 (탭 옆 작은 ⚠️ 깜박임)
   ════════════════════════════════════════════════════════════ */
.at-tab-scenario-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  font-size: 11px;
  border-radius: 50%;
  margin-left: 4px;
  flex-shrink: 0;
  cursor: help;
  transition: transform 0.15s;
}
.at-tab-scenario-badge:hover {
  transform: scale(1.15);
}

/* Critical 시나리오 (DR/PCI-DSS) - 빨간 깜박임 */
.at-scenario-critical {
  background: #fee2e2;
  border: 1px solid #dc2626;
  animation: at-scenario-blink-red 1.6s ease-in-out infinite;
  box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.6);
}
@keyframes at-scenario-blink-red {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.6);
    background: #fee2e2;
  }
  50% {
    box-shadow: 0 0 0 4px rgba(220, 38, 38, 0);
    background: #fecaca;
  }
}

/* High 시나리오 (운영→개발/GDPR) - 파란 펄스 */
.at-scenario-high {
  background: #dbeafe;
  border: 1px solid #3b82f6;
  animation: at-scenario-blink-blue 2s ease-in-out infinite;
}
@keyframes at-scenario-blink-blue {
  0%, 100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.5); }
  50%      { box-shadow: 0 0 0 3px rgba(59, 130, 246, 0); }
}

/* Info / Low 시나리오 - 정적 */
.at-scenario-info {
  background: #f0fdfa;
  border: 1px solid #14b8a6;
}

/* v90.17: 분석 완료 후 - 정적 (깜빡임 X) + 체크 표시 효과 */
.at-scenario-info-static {
  background: #d1fae5;
  border: 1px solid #10b981;
  animation: none !important;
  box-shadow: 0 0 0 1px rgba(16, 185, 129, 0.2);
}

</style>
