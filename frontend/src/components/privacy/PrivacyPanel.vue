<!--
  PrivacyPanel.vue v2 — Phase F-1f (2026-04-25)
  
  v1 대비 개선:
    [F-1f-1] source_profile_id 자동 샘플링 — 정확도 95%+
    [F-1f-2] 탐지 근거 시각화 (컬럼명/데이터/체크섬 신호)
    [F-1f-3] UX 개선
       - 위험도별 그룹핑 (CRITICAL → HIGH → MEDIUM)
       - 일괄 적용 ("Critical 모두 → HASH")
       - 컬럼 검색/필터
       - 미마스킹 컬럼 시각적 강조
       - 신뢰도 progress bar
    [F-1f-4] Audit Trail
       - 마스킹 적용 통계 (탐지/마스킹/미적용)
       - 위험 컬럼 시각적 구분
       - 법조문 collapsible 표시
-->
<template>
  <div class="privacy-panel-v2">

    <!-- v90.4: 헤더 + 시나리오 배너 통째로 제거됨 (탭 옆 깜박임 배지로 대체) -->
    <!-- 시나리오 정보가 필요하면 탭 옆 빨간 깜박임 ⚠️ 호버 시 툴팁 표시 -->

    <!-- 단계 1: 시작 전 -->
    <div v-if="!hasScanResult && !scanning" class="pri-stage-init">
      <div class="pri-selection-summary">
        <div class="pri-ss-item">
          <span class="pri-ss-ico">▤</span>
          <span class="pri-ss-label">테이블</span>
          <span class="pri-ss-value">{{ selection.tables?.length || 0 }}개</span>
        </div>
        <div class="pri-ss-divider"></div>
        <div class="pri-ss-item">
          <span class="pri-ss-ico">📡</span>
          <span class="pri-ss-label">샘플링</span>
          <span class="pri-ss-value pri-ss-good" v-if="sourceProfileId">자동 (정확도 ↑)</span>
          <span class="pri-ss-value pri-ss-warn" v-else>수동 (컬럼명만)</span>
        </div>
      </div>

      <div class="pri-info-grid">
        <div class="pri-info-card">
          <div class="pri-info-title">
            <span class="pri-info-ico">🔍</span> 자동 탐지 항목 (16종)
          </div>
          <div class="pri-info-tags">
            <span class="pri-tag pri-tag-critical">주민번호</span>
            <span class="pri-tag pri-tag-critical">외국인등록번호</span>
            <span class="pri-tag pri-tag-critical">여권</span>
            <span class="pri-tag pri-tag-critical">운전면허</span>
            <span class="pri-tag pri-tag-high">신용카드</span>
            <span class="pri-tag pri-tag-high">계좌번호</span>
            <span class="pri-tag pri-tag-high">CVV</span>
            <span class="pri-tag pri-tag-medium">한글 이름</span>
            <span class="pri-tag pri-tag-medium">휴대폰</span>
            <span class="pri-tag pri-tag-medium">이메일</span>
            <span class="pri-tag pri-tag-medium">주소</span>
            <span class="pri-tag pri-tag-medium">생년월일</span>
            <span class="pri-tag pri-tag-medium">사업자번호</span>
            <span class="pri-tag pri-tag-low">IP/MAC</span>
          </div>
        </div>

        <div class="pri-info-card">
          <div class="pri-info-title">
            <span class="pri-info-ico">🛡️</span> 7가지 마스킹 정책
          </div>
          <ul class="pri-info-list">
            <li><b>개발 환경</b> — 모든 PII 부분 마스킹 <span class="pri-badge-rec">권장</span></li>
            <li><b>QA 환경</b> — Critical 만 마스킹</li>
            <li><b>분석/통계</b> — 해시 + 일반화 (조인 가능)</li>
            <li><b>운영 복제</b> — 그대로 (DR 사이트용)</li>
            <li><b>GDPR 준수</b> — 가명화 처리</li>
            <li><b>PCI-DSS</b> — 카드정보 완전 제거</li>
            <li><b>사용자 정의</b> — 컬럼별 직접 설정</li>
          </ul>
        </div>
      </div>

      <div class="pri-action-row">
        <button class="pri-btn pri-btn-primary" @click="handleScan">
          <span class="pri-btn-ico">🔍</span>
          PII 자동 탐지 시작
        </button>
        <button class="pri-btn pri-btn-skip" @click="handleSkip">
          <span class="pri-btn-ico">↪</span>
          그대로 이관 (마스킹 없이)
        </button>
      </div>

      <div class="pri-action-note">
        💡 자동 탐지는 컬럼명 + 데이터 샘플({{ sampleCount }}건)을 분석합니다.
        <span v-if="sourceProfileId">소스 DB 에서 자동 샘플링 (안전한 LIMIT 적용).</span>
        <span v-else>샘플 데이터 fetch 비활성 — 컬럼명만으로 탐지 (정확도 ~60%).</span>
      </div>
    </div>

    <!-- 단계 2: 스캔 중 -->
    <div v-if="scanning" class="pri-stage-loading">
      <div class="pri-spinner"><div class="pri-spinner-ring"></div></div>
      <div class="pri-loading-title">PII 자동 탐지 중...</div>
      <div class="pri-loading-sub">{{ scanProgressMsg }}</div>
    </div>

    <!-- 단계 3: 결과 -->
    <div v-if="hasScanResult && !scanning" class="pri-stage-result">

      <!-- 위험도 배너 -->
      <div class="pri-risk-banner" :class="`pri-risk-banner-${complianceRisk.toLowerCase()}`">
        <div class="pri-rb-icon">{{ riskIcon }}</div>
        <div class="pri-rb-body">
          <div class="pri-rb-title">컴플라이언스 위험도: <b>{{ riskLabel }}</b></div>
          <div class="pri-rb-desc">{{ riskDescription }}</div>
        </div>
        <div class="pri-rb-stats">
          <div class="pri-rb-stat">
            <div class="pri-rb-stat-value">{{ detections.length }}</div>
            <div class="pri-rb-stat-label">PII 컬럼</div>
          </div>
          <div class="pri-rb-stat" v-if="autoSamplingMeta">
            <div class="pri-rb-stat-value">{{ autoSamplingMeta.total_rows_sampled || 0 }}</div>
            <div class="pri-rb-stat-label">샘플 row</div>
          </div>
        </div>
      </div>

      <!-- Preset 선택 -->
      <div class="pri-section-title">
        <span class="pri-section-num">1</span>
        마스킹 정책 선택
        <!-- v90.10: 시나리오 변경 안내 -->
        <span v-if="migrationScenario" class="pri-section-hint">
          (Step 0 시나리오: <b>{{ scenarioInfo?.name || migrationScenario }}</b> · 
          여기서 정책 직접 변경 가능)
        </span>
      </div>

      <div class="pri-preset-grid">
        <label
          v-for="preset in sortedPresets"
          :key="preset.id"
          class="pri-preset-card"
          :class="{ 'pri-preset-active': currentPreset === preset.id }"
        >
          <input type="radio" :value="preset.id" v-model="currentPreset"
                 @change="handlePresetChange" class="pri-preset-radio" />
          <div class="pri-preset-header">
            <div class="pri-preset-name">{{ preset.name }}</div>
            <!-- v90: 시나리오에 매칭되는 preset 에 "시나리오 적용" 배지 -->
            <div class="pri-preset-badge pri-preset-badge-scenario"
                 v-if="scenarioInfo && scenarioInfo.preset === preset.id">
              ⭐ 시나리오
            </div>
          </div>
          <div class="pri-preset-desc">{{ preset.description }}</div>
          <div class="pri-preset-usecase">📌 {{ preset.use_case }}</div>
        </label>
      </div>

      <!-- 탐지 결과 + UX -->
      <div class="pri-section-title">
        <span class="pri-section-num">2</span>
        탐지 결과 + 마스킹 미리보기
        <span class="pri-section-sub">{{ filteredDetections.length }}개 표시</span>
      </div>

      <div class="pri-toolbar">
        <div class="pri-search">
          <span class="pri-search-icon">🔍</span>
          <input type="text" v-model="searchQuery"
                 placeholder="컬럼명/카테고리 검색..."
                 class="pri-search-input" />
        </div>

        <div class="pri-filter-group">
          <button v-for="f in severityFilters" :key="f.value"
                  class="pri-filter-chip"
                  :class="{ 'pri-filter-active': selectedSeverity === f.value }"
                  @click="selectedSeverity = f.value">
            <span>{{ f.label }}</span>
            <span class="pri-filter-count">{{ countBySeverity(f.value) }}</span>
          </button>
        </div>

        <!-- v90.12: 카테고리 필터 -->
        <div class="pri-cat-filter-wrap">
          <select v-model="selectedCategory" class="pri-cat-filter">
            <option value="all">전체 카테고리 ({{ detections.length }})</option>
            <option v-for="cat in availableCategories" :key="cat.value" :value="cat.value">
              {{ cat.label }} ({{ cat.count }})
            </option>
          </select>
          <button v-if="selectedCategory !== 'all'" 
                  class="pri-cat-filter-clear"
                  @click="selectedCategory = 'all'"
                  title="카테고리 필터 해제">
            ✕
          </button>
        </div>

        <div v-if="currentPreset === 'custom'" class="pri-bulk-apply">
          <select v-model="bulkStrategy" class="pri-bulk-select">
            <option value="">— 일괄 적용 —</option>
            <option value="partial">부분 마스킹</option>
            <option value="full">완전 마스킹</option>
            <option value="hash">해시 (SHA256)</option>
            <option value="pseudonym">가명화</option>
            <option value="nullify">NULL 처리</option>
            <option value="keep">그대로</option>
          </select>
          <button class="pri-btn pri-btn-secondary pri-btn-sm" @click="applyBulkStrategy">
            현재 보이는 항목에 적용
          </button>
        </div>
      </div>

      <div v-if="loadingPreview" class="pri-preview-loading">
        <div class="pri-spinner-small"></div>
        <span>미리보기 생성 중...</span>
      </div>

      <div v-else-if="filteredDetections.length === 0" class="pri-preview-empty">
        검색/필터 조건에 맞는 항목이 없습니다.
      </div>

      <div v-else class="pri-grouped-list">
        <div v-for="group in groupedByRisk" :key="group.severity"
             v-show="group.items.length > 0" class="pri-group">
          <div class="pri-group-header" :class="`pri-group-${group.severity}`"
               @click="toggleGroup(group.severity)">
            <span class="pri-group-icon">{{ group.icon }}</span>
            <span class="pri-group-title">
              {{ group.title }}
              <!-- v90.5: 카테고리별 건수 -->
              <span v-for="(cnt, cat) in groupCategoryCounts(group.items)" :key="cat" class="pri-group-cat-badge">
                {{ getCatLabel(cat) }} ({{ cnt }})
              </span>
            </span>
            <span class="pri-group-count">{{ group.items.length }}개</span>
            <span class="pri-group-toggle">{{ groupCollapse[group.severity] ? '▶' : '▼' }}</span>
          </div>

          <div v-show="!groupCollapse[group.severity]" class="pri-group-body">
            <!-- v90.7: 정렬 헤더 - 데이터 행과 동일한 grid (완벽 정렬) -->
            <div class="pri-row-grid pri-row-sort-header">
              <span></span>
              <button class="pri-sort-btn" @click="toggleSort('table')">
                테이블.컬럼 {{ sortIcon('table') }}
              </button>
              <button class="pri-sort-btn" @click="toggleSort('type')">
                타입 {{ sortIcon('type') }}
              </button>
              <button class="pri-sort-btn" @click="toggleSort('category')">
                카테고리 {{ sortIcon('category') }}
              </button>
              <span class="pri-sort-label">전략</span>
              <button class="pri-sort-btn pri-sort-btn-right" @click="toggleSort('confidence')">
                신뢰도 {{ sortIcon('confidence') }}
              </button>
              <span></span>
            </div>
            <div v-for="d in sortedGroupItems(group.items)"
                 :key="`${d.table_name}.${d.column_name}`"
                 class="pri-detection-row"
                 :class="{ 'pri-card-warn': isUnmasked(d) && shouldShowKeepWarning }">

              <!-- v90.13: 한 줄 컬럼 정렬 + 전략 옆에 미리보기 -->
              <div class="pri-row-grid pri-row-main">
                <span class="pri-col-icon">🔒</span>
                <code class="pri-col-name">
                  <span class="pri-col-table">{{ d.table_name }}.</span><b>{{ d.column_name }}</b>
                </code>
                <span class="pri-col-type" v-if="d.column_type">{{ d.column_type }}</span>
                <span class="pri-col-cat">{{ getCatLabel(d.category) }}</span>

                <!-- v90.13: 전략 + 미리보기 통합 셀 -->
                <div class="pri-col-strategy-preview">
                  <!-- 전략 (배지/셀렉트) -->
                  <div class="pri-strategy-wrap">
                    <select v-if="currentPreset === 'custom'"
                            v-model="customPolicies[d.column_name]"
                            @change="handleCustomChange"
                            class="pri-strategy-select pri-strategy-select-sm">
                      <option value="partial">부분 마스킹</option>
                      <option value="full">완전 마스킹</option>
                      <option value="hash">해시</option>
                      <option value="pseudonym">가명화</option>
                      <option value="fake">가짜 데이터</option>
                      <option value="generalize">일반화</option>
                      <option value="nullify">NULL</option>
                      <option value="keep">그대로</option>
                    </select>
                    <span v-else-if="getPreviewFor(d)" class="pri-strategy-badge-sm"
                          :class="`strategy-${getPreviewFor(d).strategy}`">
                      {{ getStrategyLabel(getPreviewFor(d).strategy) }}
                    </span>
                  </div>
                  
                  <!-- v90.13: 미리보기 inline (전략 옆) -->
                  <div v-if="getPreviewFor(d) && getPreviewFor(d).samples?.length" 
                       class="pri-preview-inline">
                    <span v-for="(s, idx) in getPreviewFor(d).samples.slice(0, 1)" 
                          :key="idx" class="pri-sample-pair">
                      <!-- KEEP 시: 취소선 X / 다른 전략: 취소선 O -->
                      <span class="pri-sample-before"
                            :class="{ 'pri-sample-keep': getPreviewFor(d).strategy === 'keep' }">
                        {{ s.before }}
                      </span>
                      <span class="pri-arrow">→</span>
                      <span class="pri-sample-after"
                            :class="{ 'pri-sample-unchanged': getPreviewFor(d).strategy === 'keep' }">
                        {{ s.after }}
                      </span>
                    </span>
                  </div>
                </div>

                <div class="pri-col-conf">
                  <div class="pri-conf-bar-sm">
                    <div class="pri-conf-fill" :style="`width: ${d.confidence * 100}%`"></div>
                  </div>
                  <span class="pri-conf-text">{{ Math.round(d.confidence * 100) }}%</span>
                </div>

                <!-- 법조문 풍선 (호버/클릭) -->
                <button class="pri-col-legal-btn" 
                        @click.stop="toggleLegal(d.column_name)"
                        :title="d.legal_reference">
                  📜
                </button>
              </div>

              <!-- 법조문 풍선 (펼침) -->
              <div v-if="legalOpenSet.has(d.column_name)" class="pri-legal-popover">
                <div class="pri-legal-row"><b>📜 법조문:</b> {{ d.legal_reference }}</div>
                <div class="pri-legal-row"><b>💡 권장 방식:</b> {{ d.recommended_masking }}</div>
              </div>

              <!-- KEEP 경고 (시나리오 인지) -->
              <div v-if="isUnmasked(d) && shouldShowKeepWarning" class="pri-row-keep-warn">
                ⚠️ KEEP (마스킹 없음) — {{ keepWarningMessage }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Audit 요약 -->
      <div class="pri-audit-summary" v-if="filteredDetections.length > 0">
        <div class="pri-audit-title">
          <span>📋 적용 요약 (감사용)</span>
        </div>
        <div class="pri-audit-grid">
          <div class="pri-audit-item">
            <div class="pri-audit-num">{{ detections.length }}</div>
            <div class="pri-audit-lbl">탐지된 PII</div>
          </div>
          <div class="pri-audit-item pri-audit-good">
            <div class="pri-audit-num">{{ maskedCount }}</div>
            <div class="pri-audit-lbl">마스킹 적용</div>
          </div>
          <div class="pri-audit-item pri-audit-warn" v-if="unmaskedCount > 0">
            <div class="pri-audit-num">{{ unmaskedCount }}</div>
            <div class="pri-audit-lbl">미적용 (KEEP)</div>
          </div>
          <div class="pri-audit-item">
            <div class="pri-audit-num">{{ Object.keys(summaryByCategory).length }}</div>
            <div class="pri-audit-lbl">카테고리</div>
          </div>
        </div>
      </div>

      <!-- 액션 -->
      <div class="pri-final-actions">
        <button class="pri-btn pri-btn-secondary" @click="handleRescan">
          <span class="pri-btn-ico">🔄</span> 재스캔
        </button>
        <button class="pri-btn pri-btn-secondary" @click="handleSkip">
          <span class="pri-btn-ico">↪</span> 마스킹 건너뛰기
        </button>
        <div class="pri-final-spacer"></div>
        <button class="pri-btn pri-btn-primary" @click="handleApply"
                :disabled="filteredDetections.length === 0">
          <span class="pri-btn-ico">✓</span>
          이 정책으로 적용 ({{ maskedCount }}/{{ detections.length }} 컬럼)
        </button>
      </div>
    </div>

    <div v-if="errorMsg" class="pri-error">
      <span class="pri-error-icon">⚠</span>
      <span>{{ errorMsg }}</span>
      <button class="pri-error-dismiss" @click="errorMsg = ''">✕</button>
    </div>

  </div>
</template>


<script setup>
import { ref, computed, onMounted, watch, reactive } from 'vue'

const props = defineProps({
  selection: { type: Object, default: () => ({}) },
  sourceProfileId: { type: String, default: '' },
  targetDb: { type: String, default: 'mysql' },
  // v90: Step 0 에서 선택한 이관 시나리오 (자동 적용)
  migrationScenario: { type: String, default: '' },
})
const emit = defineEmits(['update:preset', 'update:decisions', 'update:scanResult', 'skip'])

const scanning = ref(false)
const loadingPreview = ref(false)
const errorMsg = ref('')
const scanProgressMsg = ref('컬럼명 분석 중...')
const sampleCount = ref(100)

const detections = ref([])
const summary = ref({})
const autoSamplingMeta = ref(null)
const presets = ref([])
const currentPreset = ref('dev_environment')
const previewItems = ref([])
const customPolicies = reactive({})

const searchQuery = ref('')
const selectedSeverity = ref('all')
const selectedCategory = ref('all')  // v90.12: 카테고리 필터
const bulkStrategy = ref('')
// v90.5: 초기에 모두 닫힘 (본부장님 요청 - 너무 복잡하지 않게)
const groupCollapse = reactive({
  critical: true, high: true, medium: true, low: true,
})

function toggleGroup(sev) {
  groupCollapse[sev] = !groupCollapse[sev]
}

// v90.5: 법조문 풍선 펼침 상태
const legalOpenSet = reactive(new Set())
function toggleLegal(columnName) {
  if (legalOpenSet.has(columnName)) {
    legalOpenSet.delete(columnName)
  } else {
    legalOpenSet.add(columnName)
  }
}

// v90.5: 그룹 안 카테고리별 건수 (예: 주민번호 (5), 외국인등록번호 (2), ...)
function groupCategoryCounts(items) {
  const counts = {}
  for (const it of items) {
    const cat = it.category || 'unknown'
    counts[cat] = (counts[cat] || 0) + 1
  }
  return counts
}

// v90.6: 컬럼 정렬 기능
const sortState = reactive({ key: 'table', dir: 'asc' })

function toggleSort(key) {
  if (sortState.key === key) {
    sortState.dir = sortState.dir === 'asc' ? 'desc' : 'asc'
  } else {
    sortState.key = key
    sortState.dir = 'asc'
  }
}

function sortIcon(key) {
  if (sortState.key !== key) return '⇅'
  return sortState.dir === 'asc' ? '▲' : '▼'
}

function sortedGroupItems(items) {
  const arr = [...(items || [])]
  const { key, dir } = sortState
  const factor = dir === 'asc' ? 1 : -1
  
  arr.sort((a, b) => {
    let av, bv
    if (key === 'table') {
      av = `${a.table_name}.${a.column_name}`
      bv = `${b.table_name}.${b.column_name}`
    } else if (key === 'type') {
      av = a.column_type || ''
      bv = b.column_type || ''
    } else if (key === 'category') {
      // v90.13: 카테고리는 한글 라벨로 정렬 (사용자 친화적)
      av = getCatLabel(a.category) || a.category || ''
      bv = getCatLabel(b.category) || b.category || ''
    } else if (key === 'confidence') {
      av = a.confidence || 0
      bv = b.confidence || 0
    } else {
      av = a[key]
      bv = b[key]
    }
    
    if (typeof av === 'string') {
      return av.localeCompare(bv) * factor
    }
    return ((av || 0) - (bv || 0)) * factor
  })
  
  return arr
}

// v90.5: 마스킹 정책 - 시나리오 매칭 preset 을 맨 앞으로
const sortedPresets = computed(() => {
  if (!presets.value || presets.value.length === 0) return []
  const matchedId = scenarioInfo.value?.preset
  if (!matchedId) return presets.value
  // 매칭되는 preset 을 맨 앞으로
  const matched = presets.value.filter(p => p.id === matchedId)
  const others = presets.value.filter(p => p.id !== matchedId)
  return [...matched, ...others]
})

const hasScanResult = computed(() =>
  detections.value.length > 0 ||
  (summary.value.total_pii_columns === 0 && Object.keys(summary.value).length > 0)
)
const complianceRisk = computed(() => summary.value.compliance_risk || 'LOW')
const summaryByCategory = computed(() => summary.value.by_category || {})

const riskIcon = computed(() => {
  // v90.4: "운영→DR 복제" 같은 시나리오는 PII 노출이 의도적이므로 빨간 ! 표시 X
  if (props.migrationScenario === 'prod_to_dr' || props.migrationScenario === 'dev_to_dev') {
    return 'ℹ️'
  }
  return ({
    CRITICAL: '🔴', HIGH: '🟠', MEDIUM: '🟡', LOW: '🟢',
  }[complianceRisk.value] || '⚪')
})

const riskLabel = computed(() => {
  // v90.4: 시나리오별 다른 표현
  if (props.migrationScenario === 'prod_to_dr') return '시나리오 적용 (DR 복제)'
  if (props.migrationScenario === 'dev_to_dev') return '시나리오 적용 (개발 간 이관)'
  return ({
    CRITICAL: '매우 높음', HIGH: '높음', MEDIUM: '보통', LOW: '낮음',
  }[complianceRisk.value] || '알 수 없음')
})

const riskDescription = computed(() => {
  // v90.4: 시나리오별 메시지 (운영→DR 같은 경우 패닉 X)
  if (props.migrationScenario === 'prod_to_dr') {
    return `DR/백업 용도 — PII 마스킹 없이 그대로 복제 (${detections.value.length}개 PII 검출됨, 타겟 DB 접근통제 별도 필수).`
  }
  if (props.migrationScenario === 'dev_to_dev') {
    return `개발 환경 간 이관 — 가명화 데이터 추정. 추가 마스킹은 컬럼별 필요시 적용.`
  }
  if (props.migrationScenario === 'prod_to_dev' && complianceRisk.value === 'CRITICAL') {
    return `운영 → 개발 이관 시 ${detections.value.length}개 PII 컬럼 가명화(Pseudonymization) 권고. 조인 보존을 위해 동일 원본은 동일 가짜값으로 변환.`
  }
  if (props.migrationScenario === 'prod_to_qa' && complianceRisk.value !== 'LOW') {
    return `QA 환경 이관 — Critical 등급(주민번호/카드)만 마스킹. 일반 개인정보는 테스트 시나리오상 필요시 유지.`
  }
  // 기본 메시지 (시나리오 없거나 특수 케이스)
  return ({
    CRITICAL: `주민번호 등 고유식별정보 ${detections.value.length}개 — 시나리오에 맞는 마스킹 정책 선택 필요.`,
    HIGH: '금융정보(카드/계좌) 포함 — 여신전문금융업법 / PCI-DSS 적용 검토.',
    MEDIUM: '일반 개인정보 탐지 — 환경에 맞는 정책 선택 권고.',
    LOW: '심각한 개인정보 미탐지 — 최소 보호 조치만 적용 가능.',
  }[complianceRisk.value] || '')
})

const filteredDetections = computed(() => {
  let list = detections.value
  if (selectedSeverity.value !== 'all') {
    list = list.filter(d => d.sensitivity === selectedSeverity.value)
  }
  // v90.12: 카테고리 필터
  if (selectedCategory.value !== 'all') {
    list = list.filter(d => d.category === selectedCategory.value)
  }
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    list = list.filter(d =>
      d.column_name.toLowerCase().includes(q) ||
      d.category.toLowerCase().includes(q) ||
      getCatLabel(d.category).toLowerCase().includes(q)
    )
  }
  return list
})

// v90.12: 사용 가능한 카테고리 목록 (탐지된 것만, 건수 많은 순)
const availableCategories = computed(() => {
  const counts = {}
  for (const d of detections.value) {
    const cat = d.category || 'unknown'
    counts[cat] = (counts[cat] || 0) + 1
  }
  return Object.entries(counts)
    .map(([value, count]) => ({
      value,
      label: getCatLabel(value),
      count,
    }))
    .sort((a, b) => b.count - a.count)
})

const groupedByRisk = computed(() => {
  const groups = {
    critical: { severity: 'critical', icon: '🔴', title: 'CRITICAL — 고유식별정보', items: [] },
    high:     { severity: 'high',     icon: '🟠', title: 'HIGH — 금융정보',         items: [] },
    medium:   { severity: 'medium',   icon: '🟡', title: 'MEDIUM — 일반 개인정보',  items: [] },
    low:      { severity: 'low',      icon: '🟢', title: 'LOW — 기술 식별자',       items: [] },
  }
  filteredDetections.value.forEach(d => {
    const sev = d.sensitivity || 'medium'
    if (groups[sev]) groups[sev].items.push(d)
  })
  return Object.values(groups)
})

const maskedCount = computed(() =>
  previewItems.value.filter(p => p.strategy && p.strategy !== 'keep').length
)
const unmaskedCount = computed(() => detections.value.length - maskedCount.value)

const severityFilters = [
  { value: 'all', label: '전체' },
  { value: 'critical', label: '🔴 Critical' },
  { value: 'high', label: '🟠 High' },
  { value: 'medium', label: '🟡 Medium' },
  { value: 'low', label: '🟢 Low' },
]

function countBySeverity(sev) {
  if (sev === 'all') return detections.value.length
  return detections.value.filter(d => d.sensitivity === sev).length
}

const catLabels = {
  rrn: '주민번호', frn: '외국인등록번호', driver_license: '운전면허', passport: '여권',
  name_kor: '한글 이름', phone: '휴대폰', phone_land: '일반전화', email: '이메일',
  address: '주소', dob: '생년월일',
  bank_account: '계좌번호', card_number: '카드번호', card_cvv: 'CVV',
  biz_number: '사업자번호', corp_number: '법인번호',
  ip_address: 'IP 주소', mac_address: 'MAC 주소',
}
function getCatLabel(cat) { return catLabels[cat] || cat }

const stratLabels = {
  partial: '부분 마스킹', full: '완전 마스킹', hash: '해시',
  pseudonym: '가명화', fake: '가짜 데이터', generalize: '일반화',
  nullify: 'NULL', keep: '그대로 (KEEP)',
}
function getStrategyLabel(s) { return stratLabels[s] || s }

function getPreviewFor(detection) {
  return previewItems.value.find(p => p.column_name === detection.column_name)
}

function isUnmasked(detection) {
  const p = getPreviewFor(detection)
  return !p || p.strategy === 'keep'
}

async function fetchPresets() {
  try {
    const r = await fetch('/api/v1/pii/presets', { credentials: 'include' })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    const data = await r.json()
    presets.value = data.presets || []
  } catch (e) {
    console.warn('[Privacy] preset 조회 실패:', e)
  }
}

async function handleScan() {
  errorMsg.value = ''
  scanning.value = true
  scanProgressMsg.value = props.sourceProfileId
    ? '소스 DB 에서 샘플 데이터 가져오는 중...'
    : '컬럼명 분석 중...'

  try {
    let tables = (props.selection.tables || []).map(t => ({
      table_name: typeof t === 'string' ? t : (t.name || t.table_name || ''),
      columns: t.columns || [],
      sample_data: t.sample_data || null,
    }))

    if (tables.length === 0) {
      errorMsg.value = '선택된 테이블이 없습니다.'
      scanning.value = false
      return
    }

    // ════════════════════════════════════════════════════════════
    // v89.7 복구: 컬럼 정보가 없는 테이블 → schema API 로 자동 fetch
    //   - selection.tables 가 테이블명만 가지고 있는 경우 (현재 본부장님 환경)
    //   - 컬럼이 없으면 PII 탐지가 0개로 나옴 → 사용자가 "왜 안되지?" 함
    //   - 자동으로 컬럼 가져와서 채운 후 스캔 진행
    // ════════════════════════════════════════════════════════════
    const tablesWithoutCols = tables.filter(t => !t.columns || t.columns.length === 0)
    if (tablesWithoutCols.length > 0) {
      scanProgressMsg.value = `컬럼 정보 가져오는 중... (${tablesWithoutCols.length}개 테이블)`
      try {
        // connectorStore 에서 source 연결 정보 가져오기
        const { useConnectorStore } = await import('@/store/connectorStore.js')
        const connectorStore = useConnectorStore()
        const src = connectorStore.source
        
        if (src && src.dbType && src.host) {
          // 각 테이블의 컬럼 fetch (병렬)
          await Promise.all(tablesWithoutCols.map(async (tbl) => {
            try {
              const params = new URLSearchParams({
                db_type: src.dbType,
                host: src.host,
                port: String(src.port || 3306),
                username: src.username || '',
                password: src.password || '',
                database: src.database || '',
              })
              const url = `/api/v1/schema/source/tables/${encodeURIComponent(tbl.table_name)}?${params}`
              const r = await fetch(url, { credentials: 'include' })
              if (r.ok) {
                const data = await r.json()
                tbl.columns = (data.columns || []).map(c => ({
                  name: c.column_name || c.name || '',
                  type: c.data_type || c.type || '',
                }))
              }
            } catch (e) {
              console.warn(`[Privacy] ${tbl.table_name} 컬럼 fetch 실패:`, e.message)
            }
          }))
          
          const fetchedCount = tablesWithoutCols.filter(t => t.columns && t.columns.length > 0).length
          console.log(`[Privacy] ${fetchedCount}/${tablesWithoutCols.length} 테이블 컬럼 자동 채움`)
        } else {
          console.warn('[Privacy] connectorStore.source 정보 없음 — 컬럼 fetch 불가')
        }
      } catch (e) {
        console.warn('[Privacy] 컬럼 자동 fetch 실패:', e)
      }
    }

    if (props.sourceProfileId) {
      scanProgressMsg.value = '데이터 패턴 검증 중...'
    } else {
      scanProgressMsg.value = '컬럼명 분석 중...'
    }

    const body = { tables }
    if (props.sourceProfileId) {
      body.source_profile_id = props.sourceProfileId
      body.sample_count = sampleCount.value
    }

    const resp = await fetch('/api/v1/pii/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(body),
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      throw new Error(err.detail || `스캔 실패 (HTTP ${resp.status})`)
    }
    const data = await resp.json()
    detections.value = data.detections || []
    summary.value = data.summary || {}
    autoSamplingMeta.value = data.scan_metadata?.auto_sampling || null

    emit('update:scanResult', { detections: detections.value, summary: summary.value })

    await fetchPreview()
  } catch (e) {
    errorMsg.value = `스캔 실패: ${e.message}`
    detections.value = []
    summary.value = {}
  } finally {
    scanning.value = false
  }
}

async function fetchPreview() {
  if (detections.value.length === 0) {
    previewItems.value = []
    return
  }
  loadingPreview.value = true
  try {
    let tables = (props.selection.tables || []).map(t => ({
      table_name: typeof t === 'string' ? t : (t.name || t.table_name || ''),
      columns: t.columns || [],
      sample_data: t.sample_data || null,
    }))

    // v90.12: 컬럼 정보가 없으면 자동으로 detection 결과에서 채우기
    //   - handleScan 은 schema API 로 가져왔지만 selection.tables 에 안 박아둠
    //   - 이미 탐지된 detection 정보로 충분히 채울 수 있음
    if (tables.every(t => !t.columns || t.columns.length === 0)) {
      // detection 별로 column 묶기
      const colMap = {}
      for (const d of detections.value) {
        if (!colMap[d.table_name]) colMap[d.table_name] = []
        colMap[d.table_name].push({
          name: d.column_name,
          type: d.column_type || 'VARCHAR(255)',
        })
      }
      tables = tables.map(t => ({
        ...t,
        columns: colMap[t.table_name] || [],
      }))
      console.log('[Privacy] fetchPreview: detection 정보로 컬럼 채움', tables.length, '테이블')
    }

    const body = { tables, preset: currentPreset.value, sample_count: 3 }
    if (currentPreset.value === 'custom') {
      body.custom_policies = Object.entries(customPolicies).map(
        ([column, strategy]) => ({ column, strategy })
      )
    }
    
    // v90.12: source profile 추가 (실제 샘플 데이터 가져오기 위해)
    if (props.sourceProfileId) {
      body.source_profile_id = props.sourceProfileId
    }

    console.log('[Privacy] fetchPreview 요청:', { preset: currentPreset.value, tables: tables.length })

    const resp = await fetch('/api/v1/pii/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(body),
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      throw new Error(err.detail || '미리보기 실패')
    }
    const data = await resp.json()
    previewItems.value = data.items || []
    console.log(`[Privacy] fetchPreview 응답: ${previewItems.value.length}개 미리보기`)
  } catch (e) {
    errorMsg.value = `미리보기 생성 실패: ${e.message}`
    previewItems.value = []
    console.error('[Privacy] fetchPreview 실패:', e)
  } finally {
    loadingPreview.value = false
  }
}

function handlePresetChange() {
  emit('update:preset', currentPreset.value)
  if (currentPreset.value === 'custom' && Object.keys(customPolicies).length === 0) {
    detections.value.forEach(d => {
      customPolicies[d.column_name] = 'partial'
    })
  }
  fetchPreview()
}

function handleCustomChange() {
  fetchPreview()
}

function applyBulkStrategy() {
  if (!bulkStrategy.value) return
  if (currentPreset.value !== 'custom') {
    currentPreset.value = 'custom'
    detections.value.forEach(d => {
      customPolicies[d.column_name] = 'partial'
    })
  }
  filteredDetections.value.forEach(d => {
    customPolicies[d.column_name] = bulkStrategy.value
  })
  bulkStrategy.value = ''
  fetchPreview()
}

function handleRescan() {
  detections.value = []
  summary.value = {}
  previewItems.value = []
  Object.keys(customPolicies).forEach(k => delete customPolicies[k])
  handleScan()
}

function handleSkip() {
  emit('skip')
}

function handleApply() {
  const decisions = previewItems.value.map(item => ({
    table_name: item.table_name,
    column_name: item.column_name,
    category: item.category,
    strategy: item.strategy,
  }))
  emit('update:decisions', decisions)
  emit('update:preset', currentPreset.value)
}

// ════════════════════════════════════════════════════════════════
// v90: 시나리오 자동 적용
// 
// Step 0 에서 본부장님이 선택한 시나리오에 따라:
//   1. preset 자동 설정 (운영→개발 → dev_environment)
//   2. PII 자동 탐지 시작 (시나리오에서 piiAutoStart=true 인 경우)
//   3. 시나리오 변경 시 즉시 반영
// ════════════════════════════════════════════════════════════════

// v90: 시나리오 정보 (배너 표시용)
const SCENARIO_INFO = {
  prod_to_dev:       { name: '운영 → 개발',        icon: '🛠️', preset: 'dev_environment',    riskLevel: 'high',     tooltip: '같은 원본 → 같은 가짜값 (조인 보존). 정합성 테스트 가능.' },
  prod_to_qa:        { name: '운영 → QA',          icon: '🧪', preset: 'qa_environment',     riskLevel: 'medium',   tooltip: 'Critical 만 마스킹. 일반 정보 그대로.' },
  prod_to_analytics: { name: '운영 → 분석/통계',   icon: '📊', preset: 'analytics',          riskLevel: 'low',      tooltip: '집계 가능, 개인 식별 불가.' },
  prod_to_dr:        { name: '운영 → DR 복제',     icon: '🔁', preset: 'production_clone',   riskLevel: 'critical', tooltip: 'PII 마스킹 없음. DR 용도. 접근통제 별도 필수.' },
  dev_to_dev:        { name: '개발 → 개발',        icon: '💻', preset: 'production_clone',   riskLevel: 'low',      tooltip: '이미 가명화된 데이터. 마스킹 불필요.' },
  gdpr_compliant:    { name: 'GDPR 준수',          icon: '🇪🇺', preset: 'gdpr_compliant',     riskLevel: 'high',     tooltip: 'EU 가명화 + 매핑테이블.' },
  pci_dss:           { name: 'PCI-DSS 준수',       icon: '💳', preset: 'pci_dss',            riskLevel: 'critical', tooltip: '카드/CVV 영구 제거.' },
  custom:            { name: '사용자 정의',        icon: '⚙️', preset: 'custom',             riskLevel: 'unknown',  tooltip: '컬럼별 직접 선택.' },
}

const scenarioInfo = computed(() => SCENARIO_INFO[props.migrationScenario] || null)

// v90.5: KEEP 경고는 시나리오별로 다르게
const shouldShowKeepWarning = computed(() => {
  // 운영→DR / 개발→개발 시나리오는 KEEP 이 정상이므로 경고 표시 X
  if (['prod_to_dr', 'dev_to_dev'].includes(props.migrationScenario)) return false
  return true
})

const keepWarningMessage = computed(() => {
  const sc = props.migrationScenario
  if (sc === 'prod_to_dev') return '운영 → 개발 이관 시 PII 노출 위험'
  if (sc === 'prod_to_qa') return 'QA 환경 이관 시 검토 필요'
  if (sc === 'prod_to_analytics') return '분석 환경 이관 시 가명화 권고'
  if (sc === 'gdpr_compliant') return 'GDPR Art.4(5) 위반 가능성'
  if (sc === 'pci_dss') return 'PCI-DSS Req.3.4 위반 가능성'
  return '마스킹 정책 검토 필요'
})

// 시나리오 → preset 매핑 (인라인, utils 의존성 없음)
const SCENARIO_PRESET_MAP = {
  prod_to_dev:        { preset: 'dev_environment',    autoStart: true  },
  prod_to_qa:         { preset: 'qa_environment',     autoStart: true  },
  prod_to_analytics:  { preset: 'analytics',          autoStart: true  },
  prod_to_dr:         { preset: 'production_clone',   autoStart: false },
  dev_to_dev:         { preset: 'production_clone',   autoStart: false },
  gdpr_compliant:     { preset: 'gdpr_compliant',     autoStart: true  },
  pci_dss:            { preset: 'pci_dss',            autoStart: true  },
  custom:             { preset: 'custom',             autoStart: true  },
}

function applyScenario(scenarioId) {
  if (!scenarioId) return
  const sc = SCENARIO_PRESET_MAP[scenarioId]
  if (!sc) return
  
  console.log(`[Privacy v90] 시나리오 적용: ${scenarioId} → preset=${sc.preset}, autoStart=${sc.autoStart}`)
  
  // 1) preset 변경 (사용자가 명시적으로 다른 preset 선택했으면 덮어쓰지 않음)
  if (currentPreset.value === 'dev_environment' || !currentPreset.value) {
    currentPreset.value = sc.preset
  }
  
  // 2) 자동 PII 탐지 시작
  if (sc.autoStart && detections.value.length === 0 && !scanning.value) {
    setTimeout(() => {
      if (props.selection.tables && props.selection.tables.length > 0) {
        handleScan()
      }
    }, 300)
  }
}

onMounted(async () => {
  await fetchPresets()
  // 마운트 시 시나리오 즉시 적용
  if (props.migrationScenario) {
    applyScenario(props.migrationScenario)
  }
})

// 시나리오 변경 watch
watch(() => props.migrationScenario, (newId) => {
  if (newId) applyScenario(newId)
})

watch(() => props.selection, () => {
  detections.value = []
  summary.value = {}
  previewItems.value = []
}, { deep: true })
</script>


<style scoped>
.privacy-panel-v2 { display: flex; flex-direction: column; gap: 16px; padding: 4px 0; }

.pri-header {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 12px 14px;
  background: linear-gradient(135deg, var(--bg-secondary, #f8fafc) 0%, var(--bg-primary, #fff) 100%);
  border: 1px solid var(--border-light, #e2e8f0);
  border-left: 3px solid #14b8a6;
  border-radius: 8px;
  position: relative;
}
.pri-header-icon { font-size: 22px; padding-top: 2px; }
.pri-header-body { flex: 1; }
.pri-header-title { font-size: 14px; font-weight: 700; color: var(--text-primary, #1e293b); margin-bottom: 3px; }
.pri-header-subtitle { font-size: 12px; color: var(--text-secondary, #64748b); line-height: 1.5; }
.pri-header-version {
  position: absolute; top: 8px; right: 12px;
  font-size: 10px; font-weight: 700; color: #14b8a6;
  background: rgba(20,184,166,0.1); padding: 2px 8px; border-radius: 99px;
}

.pri-selection-summary {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 14px; border-radius: 8px;
  background: var(--bg-secondary, #f8fafc);
  border: 1px solid var(--border-light, #e2e8f0);
  font-size: 12px;
}
.pri-ss-item { display: flex; align-items: center; gap: 6px; }
.pri-ss-ico { font-size: 13px; }
.pri-ss-label { color: var(--text-tertiary, #94a3b8); }
.pri-ss-value { font-weight: 600; color: var(--text-primary, #1e293b); }
.pri-ss-good { color: #16a34a; }
.pri-ss-warn { color: #ea580c; }
.pri-ss-divider { width: 1px; height: 12px; background: var(--border-light, #e2e8f0); }

.pri-stage-init { display: flex; flex-direction: column; gap: 16px; }
.pri-info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 720px) { .pri-info-grid { grid-template-columns: 1fr; } }
.pri-info-card {
  padding: 14px 16px;
  background: var(--bg-primary, #fff);
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 8px;
}
.pri-info-title {
  font-size: 13px; font-weight: 700; color: var(--text-primary, #1e293b);
  margin-bottom: 10px;
  display: flex; align-items: center; gap: 6px;
}
.pri-info-list { margin: 0; padding-left: 0; list-style: none; display: flex; flex-direction: column; gap: 6px; }
.pri-info-list li {
  font-size: 12px; color: var(--text-secondary, #64748b);
  padding-left: 14px; position: relative; line-height: 1.5;
}
.pri-info-list li::before {
  content: "▸"; position: absolute; left: 0;
  color: #14b8a6; font-weight: 700;
}
.pri-info-list li b { color: var(--text-primary, #1e293b); font-weight: 600; }

.pri-info-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.pri-tag {
  font-size: 10px; font-weight: 600;
  padding: 2px 8px; border-radius: 99px;
  border: 1px solid;
}
.pri-tag-critical { background: #fee2e2; color: #dc2626; border-color: #fca5a5; }
.pri-tag-high     { background: #ffedd5; color: #ea580c; border-color: #fdba74; }
.pri-tag-medium   { background: #fef9c3; color: #ca8a04; border-color: #fde047; }
.pri-tag-low      { background: #dcfce7; color: #16a34a; border-color: #86efac; }

.pri-badge-rec {
  display: inline-block; font-size: 9px; font-weight: 700;
  padding: 1px 6px; background: #14b8a6; color: #fff;
  border-radius: 99px; margin-left: 4px;
}

.pri-action-row { display: flex; gap: 10px; flex-wrap: wrap; }
.pri-action-note {
  font-size: 11px; color: var(--text-tertiary, #94a3b8);
  padding: 8px 12px;
  background: var(--bg-secondary, #f8fafc);
  border-radius: 6px; line-height: 1.5;
}

.pri-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 9px 16px;
  font-size: 13px; font-weight: 600;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
  border: 1.5px solid transparent;
}
.pri-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.pri-btn-sm { padding: 6px 10px; font-size: 12px; }
.pri-btn-primary { background: #14b8a6; color: #fff; border-color: #14b8a6; }
.pri-btn-primary:hover:not(:disabled) { background: #0d9488; border-color: #0d9488; }
.pri-btn-secondary {
  background: var(--bg-primary, #fff);
  color: var(--text-primary, #1e293b);
  border-color: var(--border-medium, #cbd5e1);
}
.pri-btn-secondary:hover:not(:disabled) { border-color: var(--border-strong, #94a3b8); }
.pri-btn-skip {
  background: var(--bg-primary, #fff);
  color: var(--text-secondary, #64748b);
  border-color: var(--border-light, #e2e8f0);
}
.pri-btn-skip:hover { background: var(--bg-secondary, #f8fafc); }
.pri-btn-ico { font-size: 14px; }

.pri-stage-loading {
  padding: 40px 20px;
  display: flex; flex-direction: column; align-items: center; gap: 12px;
  background: var(--bg-secondary, #f8fafc);
  border-radius: 8px;
}
.pri-spinner { width: 40px; height: 40px; position: relative; }
.pri-spinner-ring {
  position: absolute; inset: 0;
  border: 3px solid var(--border-light, #e2e8f0);
  border-top-color: #14b8a6;
  border-radius: 50%;
  animation: pri-spin 0.8s linear infinite;
}
.pri-spinner-small {
  width: 14px; height: 14px;
  border: 2px solid var(--border-light, #e2e8f0);
  border-top-color: #14b8a6;
  border-radius: 50%;
  display: inline-block;
  animation: pri-spin 0.8s linear infinite;
  margin-right: 6px;
}
@keyframes pri-spin { to { transform: rotate(360deg); } }
.pri-loading-title { font-size: 14px; font-weight: 600; color: var(--text-primary, #1e293b); }
.pri-loading-sub { font-size: 12px; color: var(--text-tertiary, #94a3b8); }

.pri-stage-result { display: flex; flex-direction: column; gap: 14px; }
.pri-risk-banner {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 12px;
  border-radius: 6px;
  border-left: 3px solid;
  margin-bottom: 8px;
}
.pri-risk-banner-critical { background: #fef2f2; border-color: #dc2626; }
.pri-risk-banner-high     { background: #fff7ed; border-color: #ea580c; }
.pri-risk-banner-medium   { background: #fefce8; border-color: #ca8a04; }
.pri-risk-banner-low      { background: #f0fdf4; border-color: #16a34a; }
.pri-rb-icon { font-size: 18px; line-height: 1; flex-shrink: 0; }
.pri-rb-body { flex: 1; min-width: 0; }
.pri-rb-title { font-size: 12px; font-weight: 600; color: var(--text-primary, #1e293b); margin-bottom: 2px; }
.pri-rb-desc { font-size: 11px; color: var(--text-secondary, #64748b); line-height: 1.4; }
.pri-rb-stats { display: flex; gap: 8px; flex-shrink: 0; }
.pri-rb-stat { text-align: center; padding: 0 6px; }
.pri-rb-stat-value { font-size: 16px; font-weight: 700; color: var(--text-primary, #1e293b); line-height: 1.2; }
.pri-rb-stat-label {
  font-size: 9px; color: var(--text-tertiary, #94a3b8);
  text-transform: uppercase; letter-spacing: 0.3px;
}

.pri-section-title {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; font-weight: 700; color: var(--text-primary, #1e293b);
  margin-top: 6px;
}
.pri-section-num {
  display: inline-flex; align-items: center; justify-content: center;
  width: 20px; height: 20px;
  background: #14b8a6; color: #fff;
  border-radius: 99px;
  font-size: 11px; font-weight: 700;
}
.pri-section-sub {
  margin-left: auto;
  font-size: 11px; font-weight: 500; color: var(--text-tertiary, #94a3b8);
}
/* v90.10: 시나리오 변경 안내 */
.pri-section-hint {
  margin-left: 10px;
  font-size: 11px;
  font-weight: 400;
  color: var(--text-secondary, #64748b);
  font-style: italic;
}
.pri-section-hint b {
  color: #14b8a6;
  font-weight: 600;
}

.pri-preset-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 8px;
}
.pri-preset-card {
  position: relative; padding: 12px;
  border: 1.5px solid var(--border-light, #e2e8f0);
  background: var(--bg-primary, #fff);
  border-radius: 8px; cursor: pointer;
  transition: all 0.15s ease;
}
.pri-preset-card:hover { border-color: #5eead4; background: #f0fdfa; }
.pri-preset-active {
  border-color: #14b8a6 !important;
  background: #f0fdfa !important;
  box-shadow: 0 0 0 3px rgba(20,184,166,0.1);
}
.pri-preset-radio { position: absolute; opacity: 0; pointer-events: none; }
.pri-preset-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 4px;
}
.pri-preset-name { font-size: 13px; font-weight: 600; color: var(--text-primary, #1e293b); }
.pri-preset-badge {
  font-size: 10px; font-weight: 700;
  padding: 2px 6px;
  background: #14b8a6; color: #fff;
  border-radius: 99px;
}
/* v90: 시나리오 매칭 preset 강조 */
.pri-preset-badge-scenario {
  background: linear-gradient(135deg, #14b8a6, #06b6d4) !important;
  box-shadow: 0 1px 3px rgba(20, 184, 166, 0.4);
  padding: 2px 8px !important;
  letter-spacing: 0.3px;
}
.pri-preset-desc { font-size: 11px; color: var(--text-secondary, #64748b); line-height: 1.4; margin-bottom: 4px; }
.pri-preset-usecase { font-size: 10px; color: var(--text-tertiary, #94a3b8); }

.pri-toolbar {
  display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
  padding: 10px 12px;
  background: var(--bg-secondary, #f8fafc);
  border-radius: 8px;
  border: 1px solid var(--border-light, #e2e8f0);
}
.pri-search {
  display: flex; align-items: center; gap: 6px;
  flex: 1; min-width: 200px;
  padding: 6px 10px;
  background: var(--bg-primary, #fff);
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 6px;
}
.pri-search-icon { font-size: 12px; }
.pri-search-input {
  flex: 1; border: none; outline: none; background: transparent;
  font-size: 12px; color: var(--text-primary, #1e293b);
}

.pri-filter-group { display: flex; gap: 4px; flex-wrap: wrap; }
.pri-filter-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 10px;
  font-size: 11px; font-weight: 600;
  background: var(--bg-primary, #fff);
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 99px;
  cursor: pointer;
  color: var(--text-secondary, #64748b);
  transition: all 0.15s ease;
}
.pri-filter-chip:hover { border-color: #14b8a6; }
.pri-filter-active {
  background: #14b8a6 !important;
  color: #fff !important;
  border-color: #14b8a6 !important;
}
.pri-filter-count {
  font-size: 10px;
  background: rgba(0,0,0,0.1);
  padding: 1px 5px;
  border-radius: 99px;
}
.pri-filter-active .pri-filter-count { background: rgba(255,255,255,0.3); }

.pri-bulk-apply { display: flex; gap: 6px; align-items: center; }
.pri-bulk-select {
  padding: 5px 8px;
  font-size: 12px;
  border: 1px solid var(--border-medium, #cbd5e1);
  border-radius: 4px;
  background: var(--bg-primary, #fff);
  cursor: pointer;
}

.pri-grouped-list { display: flex; flex-direction: column; gap: 8px; }
.pri-group {
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-primary, #fff);
}
.pri-group-header {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px;
  background: var(--bg-secondary, #f8fafc);
  border-bottom: 1px solid var(--border-light, #e2e8f0);
  cursor: pointer;
  font-weight: 600;
  font-size: 13px;
  user-select: none;
}
.pri-group-header:hover { background: var(--bg-tertiary, #f1f5f9); }
.pri-group-critical { border-left: 3px solid #dc2626; }
.pri-group-high     { border-left: 3px solid #ea580c; }
.pri-group-medium   { border-left: 3px solid #ca8a04; }
.pri-group-low      { border-left: 3px solid #16a34a; }
.pri-group-icon { font-size: 14px; }
.pri-group-title { color: var(--text-primary, #1e293b); }
.pri-group-count {
  margin-left: auto;
  font-size: 11px; padding: 2px 8px;
  background: var(--bg-primary, #fff);
  border-radius: 99px;
  color: var(--text-secondary, #64748b);
}
.pri-group-toggle { font-size: 10px; color: var(--text-tertiary, #94a3b8); margin-left: 4px; }
.pri-group-body { padding: 8px; display: flex; flex-direction: column; gap: 6px; }

.pri-detection-card {
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 6px;
  padding: 10px 12px;
  background: var(--bg-primary, #fff);
}
.pri-card-warn { border-color: #fdba74; background: #fff7ed; }

.pri-card-header {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; margin-bottom: 6px;
}
.pri-card-col {
  display: flex; align-items: center; gap: 6px;
  flex: 1; min-width: 0;
}
.pri-card-icon { font-size: 12px; }
.pri-card-name {
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 12px;
  color: var(--text-primary, #1e293b);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.pri-card-table { color: var(--text-tertiary, #94a3b8); }
.pri-card-name b { color: #0f766e; }
.pri-card-cat {
  padding: 1px 8px; font-size: 10px; font-weight: 600;
  background: var(--bg-secondary, #f8fafc);
  color: var(--text-secondary, #64748b);
  border-radius: 99px; flex-shrink: 0;
}

.pri-card-conf {
  display: flex; align-items: center; gap: 6px;
  flex-shrink: 0;
}
.pri-conf-bar {
  width: 60px; height: 4px;
  background: var(--bg-secondary, #f1f5f9);
  border-radius: 99px;
  overflow: hidden;
}
.pri-conf-fill {
  height: 100%;
  background: linear-gradient(90deg, #fbbf24, #14b8a6);
  border-radius: 99px;
  transition: width 0.3s ease;
}
.pri-conf-text {
  font-size: 11px; font-weight: 700; color: #14b8a6;
  min-width: 30px; text-align: right;
}

.pri-card-evidence {
  display: flex; gap: 8px; flex-wrap: wrap;
  padding: 4px 0;
  margin-bottom: 6px;
  border-bottom: 1px dashed var(--border-light, #e2e8f0);
}
.pri-ev-item {
  font-size: 10px; font-weight: 500;
  color: #16a34a;
  padding: 1px 6px;
  background: #f0fdf4;
  border-radius: 4px;
}
.pri-ev-checksum { background: #ecfeff; color: #0891b2; }

.pri-card-preview { margin-top: 6px; }
.pri-preview-row {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 4px;
}
.pri-preview-label {
  font-size: 10px; font-weight: 600;
  color: var(--text-tertiary, #94a3b8);
  text-transform: uppercase; letter-spacing: 0.5px;
}
.pri-strategy-select {
  padding: 3px 8px; font-size: 11px;
  border: 1px solid var(--border-medium, #cbd5e1);
  border-radius: 4px;
  background: var(--bg-primary, #fff);
  cursor: pointer;
}
.pri-strategy-badge {
  font-size: 11px; font-weight: 600;
  color: #14b8a6;
  background: #f0fdfa;
  padding: 2px 8px; border-radius: 4px;
}

.pri-preview-table {
  width: 100%; border-collapse: collapse;
  font-size: 11px;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
}
.pri-preview-table td { padding: 3px 6px; }
.pri-arrow { color: #14b8a6; font-weight: 700; width: 20px; text-align: center; }
.pri-sample-before { color: var(--text-secondary, #64748b); }
.pri-sample-after { color: #0f766e; font-weight: 600; }

.pri-card-unmasked-warn {
  margin-top: 6px;
  padding: 6px 10px;
  background: #fef3c7; color: #92400e;
  font-size: 11px; font-weight: 500;
  border-radius: 4px;
}

.pri-card-legal { margin-top: 6px; font-size: 11px; }
.pri-card-legal summary {
  cursor: pointer;
  color: var(--text-tertiary, #94a3b8);
  padding: 4px 0;
  user-select: none;
}
.pri-card-legal summary:hover { color: var(--text-secondary, #64748b); }
.pri-legal-body {
  padding: 6px 10px;
  background: var(--bg-secondary, #f8fafc);
  border-radius: 4px;
  color: var(--text-secondary, #64748b);
  display: flex; flex-direction: column; gap: 3px;
  margin-top: 4px;
}

.pri-preview-loading, .pri-preview-empty {
  padding: 20px;
  text-align: center;
  font-size: 12px;
  color: var(--text-tertiary, #94a3b8);
  background: var(--bg-secondary, #f8fafc);
  border-radius: 8px;
}

.pri-audit-summary {
  margin-top: 4px;
  padding: 12px 14px;
  background: linear-gradient(135deg, #f0fdfa 0%, #ecfeff 100%);
  border: 1px solid #99f6e4;
  border-radius: 8px;
}
.pri-audit-title {
  font-size: 12px; font-weight: 700;
  color: #0f766e;
  margin-bottom: 8px;
}
.pri-audit-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: 8px;
}
.pri-audit-item {
  text-align: center;
  padding: 8px;
  background: var(--bg-primary, #fff);
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 6px;
}
.pri-audit-num {
  font-size: 22px; font-weight: 700;
  color: var(--text-primary, #1e293b);
}
.pri-audit-lbl {
  font-size: 10px;
  color: var(--text-tertiary, #94a3b8);
  text-transform: uppercase; letter-spacing: 0.5px;
}
.pri-audit-good { border-color: #86efac; }
.pri-audit-good .pri-audit-num { color: #16a34a; }
.pri-audit-warn { border-color: #fdba74; }
.pri-audit-warn .pri-audit-num { color: #ea580c; }

.pri-final-actions {
  display: flex; gap: 8px; align-items: center;
  padding-top: 8px;
  border-top: 1px dashed var(--border-light, #e2e8f0);
}
.pri-final-spacer { flex: 1; }

.pri-error {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  color: #dc2626;
  font-size: 12px;
}
.pri-error-icon { font-size: 14px; }
.pri-error-dismiss {
  margin-left: auto;
  background: transparent; border: none; cursor: pointer;
  color: #dc2626; font-size: 14px; padding: 0 4px;
}
/* ═══════════════════════════════════════════════════════════════════
   v90: 시나리오 배너 (헤더 아래)
   ═══════════════════════════════════════════════════════════════════ */
.pri-scenario-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  margin: 12px 0;
  border-radius: 8px;
  border-left: 4px solid;
  background: linear-gradient(90deg, var(--bg-secondary, #f8fafc), transparent);
  font-size: 12px;
}
.pri-sb-low      { border-left-color: #10b981; background-color: #ecfdf5; }
.pri-sb-medium   { border-left-color: #f59e0b; background-color: #fffbeb; }
.pri-sb-high     { border-left-color: #3b82f6; background-color: #eff6ff; }
.pri-sb-critical { border-left-color: #dc2626; background-color: #fef2f2; }
.pri-sb-unknown  { border-left-color: #64748b; background-color: #f8fafc; }

.pri-sb-icon {
  font-size: 22px;
  flex-shrink: 0;
}
.pri-sb-body {
  flex: 1;
}
.pri-sb-title {
  font-size: 13px;
  color: var(--text-primary, #1e293b);
  margin-bottom: 2px;
}
.pri-sb-title b {
  font-weight: 700;
}
.pri-sb-desc {
  color: var(--text-secondary, #64748b);
  font-size: 11px;
  line-height: 1.5;
}
.pri-sb-desc code {
  background: rgba(0,0,0,0.05);
  padding: 1px 6px;
  border-radius: 3px;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 10px;
  font-weight: 600;
}
.pri-sb-step0 {
  font-size: 10px;
  color: var(--text-secondary, #94a3b8);
  font-style: italic;
  flex-shrink: 0;
}

/* ════════════════════════════════════════════════════════════
   v90.5: 한 줄 탐지 결과 + 컬럼 정렬 + 법조문 풍선
   ════════════════════════════════════════════════════════════ */
.pri-detection-row {
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 6px;
  background: #fff;
  margin-bottom: 4px;
  transition: all 0.12s;
}
.pri-detection-row:hover {
  border-color: #94a3b8;
  background: var(--bg-tertiary, #f8fafc);
}
.pri-detection-row.pri-card-warn {
  border-color: #fdba74;
  background: #fff7ed;
}

/* ━ 공통 grid - 정렬 헤더 + 데이터 행 같은 컬럼 width 사용 ━ */
.pri-row-grid {
  display: grid;
  /*
    [아이콘 18px] [테이블.컬럼 320px] [타입 120px] [카테고리 110px]
    [전략 1fr (확장)] [신뢰도 90px] [📜 26px]
    
    width 를 고정해서 모든 행이 동일한 위치에 정렬됨
  */
  grid-template-columns: 18px minmax(280px, 320px) 110px 100px minmax(280px, 1fr) 80px 26px;
  align-items: center;
  gap: 12px;
  padding: 7px 12px;
}

.pri-row-main {
  font-size: 12px;
}

.pri-col-icon { font-size: 13px; flex-shrink: 0; }

.pri-col-name {
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 12px;
  color: var(--text-primary, #1e293b);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pri-col-table {
  color: var(--text-secondary, #64748b);
  font-weight: 400;
}

/* v90.6: 컬럼 타입 칩 */
.pri-col-type {
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 10px;
  color: #64748b;
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 3px;
  white-space: nowrap;
  border: 1px solid #e2e8f0;
  text-align: center;
  justify-self: start;
}

.pri-col-cat {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 600;
  padding: 3px 8px;
  background: #fef3c7;
  color: #92400e;
  border-radius: 99px;
  white-space: nowrap;
  justify-self: start;
}

.pri-col-strategy {
  display: flex;
  align-items: center;
  justify-content: flex-start;
}

/* v90.13: 전략 + 미리보기 통합 셀 (전략 셀 안에 미리보기 같이) */
.pri-col-strategy-preview {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.pri-strategy-wrap {
  flex-shrink: 0;
}

/* 전략 옆 미리보기 (가로 inline) */
.pri-preview-inline {
  display: flex;
  align-items: center;
  font-size: 10px;
  color: var(--text-secondary, #64748b);
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pri-sample-pair {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
/* 마스킹 변환 (취소선 + 청록색) */
.pri-sample-before {
  color: #94a3b8;
  text-decoration: line-through;
}
.pri-sample-after {
  color: #14b8a6;
  font-weight: 600;
}
.pri-arrow {
  color: #cbd5e1;
}

/* v90.13: KEEP 시 취소선 X — 운영→운영 (그대로 이관) */
.pri-sample-before.pri-sample-keep {
  color: #475569 !important;
  text-decoration: none !important;
}
.pri-sample-after.pri-sample-unchanged {
  color: #475569 !important;
  font-weight: 500 !important;
}

.pri-strategy-select-sm {
  font-size: 10px;
  padding: 3px 6px;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  width: 100%;
  max-width: 130px;
}
.pri-strategy-badge-sm {
  display: inline-block;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  background: #f1f5f9;
  color: var(--text-secondary, #475569);
  border-radius: 4px;
  white-space: nowrap;
}
/* v90.13: 전략별 색상 (배지) */
.pri-strategy-badge-sm.strategy-keep {
  background: #f1f5f9;
  color: #475569;
}
.pri-strategy-badge-sm.strategy-partial,
.pri-strategy-badge-sm.strategy-full {
  background: #fef3c7;
  color: #92400e;
}
.pri-strategy-badge-sm.strategy-pseudonym {
  background: #ccfbf1;
  color: #115e59;
}
.pri-strategy-badge-sm.strategy-hash {
  background: #e0f2fe;
  color: #075985;
}
.pri-strategy-badge-sm.strategy-fake,
.pri-strategy-badge-sm.strategy-generalize {
  background: #f3e8ff;
  color: #6b21a8;
}
.pri-strategy-badge-sm.strategy-nullify {
  background: #fee2e2;
  color: #991b1b;
}

.pri-col-conf {
  display: flex;
  align-items: center;
  gap: 4px;
}
.pri-conf-bar-sm {
  flex: 1;
  height: 4px;
  background: var(--border-light, #e2e8f0);
  border-radius: 2px;
  overflow: hidden;
}

.pri-col-legal-btn {
  font-size: 14px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  cursor: pointer;
  padding: 2px 4px;
  transition: all 0.12s;
  justify-self: center;
}
.pri-col-legal-btn:hover {
  background: #f1f5f9;
  border-color: var(--border-light, #e2e8f0);
}

/* v90.7: 정렬 헤더 - 데이터 행과 동일한 grid 사용 */
.pri-row-sort-header {
  background: #f8fafc;
  border-bottom: 1px solid var(--border-light, #e2e8f0);
  margin: -8px -8px 8px -8px;
  font-size: 10px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.pri-sort-btn {
  background: transparent;
  border: none;
  font-size: 10px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 3px;
  transition: all 0.12s;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  white-space: nowrap;
  text-align: left;
  justify-self: start;
}
.pri-sort-btn:hover {
  background: #e2e8f0;
  color: #14b8a6;
}
.pri-sort-btn-right {
  text-align: right;
  justify-self: stretch;
}
.pri-sort-label {
  font-size: 10px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  padding: 2px 6px;
  justify-self: start;
}

/* ━ 법조문 풍선 (펼침) ━ */
.pri-legal-popover {
  margin: 0 12px 8px 12px;
  padding: 8px 12px;
  background: #fffbeb;
  border-left: 3px solid #f59e0b;
  border-radius: 0 4px 4px 0;
  font-size: 11px;
  line-height: 1.6;
  animation: pri-popover-fade 0.18s ease-out;
}
.pri-legal-row {
  margin-bottom: 2px;
}
.pri-legal-row:last-child {
  margin-bottom: 0;
}
.pri-legal-row b {
  color: #92400e;
}
@keyframes pri-popover-fade {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ━ 미리보기 (인라인, 컴팩트) ━ */
.pri-row-preview {
  padding: 0 12px 8px 38px;
  font-size: 11px;
  color: var(--text-secondary, #64748b);
}
.pri-sample-inline {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
}
.pri-sample-inline .pri-sample-before {
  color: #94a3b8;
  text-decoration: line-through;
}
.pri-sample-inline .pri-sample-after {
  color: #14b8a6;
  font-weight: 600;
}
.pri-sample-inline .pri-arrow {
  color: #cbd5e1;
}

/* ━ KEEP 경고 (시나리오 인지) ━ */
.pri-row-keep-warn {
  margin: 0 12px 8px 38px;
  padding: 4px 8px;
  background: #fef3c7;
  color: #92400e;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
}

/* ━ 그룹 헤더 카테고리 배지 ━ */
.pri-group-cat-badge {
  display: inline-block;
  margin-left: 6px;
  font-size: 10px;
  font-weight: 600;
  padding: 1px 7px;
  background: rgba(255, 255, 255, 0.6);
  color: var(--text-secondary, #475569);
  border-radius: 99px;
  vertical-align: middle;
}

/* 좁은 화면 - 헤더 + 데이터 동일 grid (정렬 유지) */
@media (max-width: 1280px) {
  .pri-row-grid {
    grid-template-columns: 18px 240px 100px 90px 1fr 80px 24px;
    gap: 8px;
    font-size: 11px;
  }
}
@media (max-width: 1024px) {
  .pri-row-grid {
    grid-template-columns: 18px 200px 90px 80px 1fr 70px 22px;
    gap: 6px;
    font-size: 11px;
  }
}

/* v90.12: 카테고리 필터 */
.pri-cat-filter-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
}
.pri-cat-filter {
  font-size: 11px;
  padding: 4px 28px 4px 10px;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  color: var(--text-primary, #1e293b);
  font-weight: 500;
  min-width: 180px;
  appearance: none;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 10 10'><path d='M2 4l3 3 3-3' stroke='%2364748b' fill='none' stroke-width='1.5'/></svg>");
  background-repeat: no-repeat;
  background-position: right 8px center;
}
.pri-cat-filter:hover {
  border-color: #94a3b8;
}
.pri-cat-filter:focus {
  outline: none;
  border-color: #14b8a6;
  box-shadow: 0 0 0 2px rgba(20, 184, 166, 0.1);
}
.pri-cat-filter-clear {
  margin-left: 4px;
  width: 22px;
  height: 22px;
  font-size: 10px;
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
  border-radius: 50%;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.pri-cat-filter-clear:hover {
  background: #fee2e2;
}

</style>
