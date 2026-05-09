<!--
  PreflightPanel.vue — Pre-Flight Assessment (2026-05-03)
  ═══════════════════════════════════════════════════════════════
  본부장님 원칙: "이관 Job 생성에서 최대한 분석 후 사용자에게 안내"
  
  분석 항목 (모두 일반 패턴 — 어떤 MSSQL DB든 작동):
    1) 컬럼 메타 분석 (UDT, PK NULL, 특수타입)
    2) 객체 DDL 정적 분석 (T-SQL 위험 패턴)
    3) 의존성 그래프 (FK, 순환 참조)
    4) 대용량 테이블
    5) 종합 위험도 (안전/주의/고위험)
-->
<template>
  <div class="preflight-panel">
    <!-- 헤더 -->
    <div class="pf-header">
      <h3 class="pf-title">🚀 Pre-Flight Assessment</h3>
      <p class="pf-subtitle">
        선택한 객체에 대해 이관 전 본질 분석을 수행합니다.
        sys 카탈로그 + 표준 패턴 기반 (어떤 MSSQL DB든 동일하게 작동).
      </p>
    </div>

    <!-- 시작 버튼 -->
    <div v-if="!analysis && !analyzing" class="pf-start">
      <div class="pf-start-info">
        선택 항목: <strong>{{ selectionSummary }}</strong>
      </div>
      <button class="pf-start-btn" @click="runAnalysis">
        🔍 사전 분석 시작
      </button>
    </div>

    <!-- 진행 중 -->
    <div v-if="analyzing" class="pf-loading">
      <div class="pf-spinner">⏳</div>
      <div>분석 중... ({{ progressText }})</div>
    </div>

    <!-- 결과 -->
    <div v-if="analysis && !analyzing" class="pf-result">
      <!-- 종합 위험도 -->
      <div class="pf-overall" :class="`pf-risk-${analysis.overall_risk?.level}`">
        <div class="pf-overall-icon">
          {{ analysis.overall_risk?.level === 'high' ? '🔴' : 
             analysis.overall_risk?.level === 'medium' ? '🟡' : '🟢' }}
        </div>
        <div class="pf-overall-text">
          <div class="pf-overall-title">{{ overallTitle }}</div>
          <div class="pf-overall-summary">{{ analysis.overall_risk?.summary }}</div>
        </div>
      </div>

      <!-- 1. 컬럼 메타 분석 -->
      <div class="pf-section">
        <h4 class="pf-section-title">📊 컬럼 메타 분석</h4>
        <div class="pf-section-body">
          <!-- UDT -->
          <div class="pf-item pf-info" v-if="(analysis.columns?.udt_columns || []).length > 0">
            <span class="pf-item-icon">✅</span>
            <span class="pf-item-label">UDT 컬럼</span>
            <span class="pf-item-count">{{ analysis.columns.udt_columns.length }}개</span>
            <span class="pf-item-desc">자동 base type 해석됨 (v95_p13 처방)</span>
            <button class="pf-detail-btn" @click="toggleDetail('udt')">
              {{ details.udt ? '▼' : '▶' }}
            </button>
          </div>
          <div v-show="details.udt" class="pf-detail">
            <div v-for="(c, i) in (analysis.columns?.udt_columns || []).slice(0, 20)" :key="i"
                 class="pf-detail-row">
              <code>{{ c.schema }}.{{ c.table }}.{{ c.column }}</code>
              <span class="pf-arrow">→</span>
              <code>{{ c.udt_name }}</code>
              <span class="pf-arrow">⇒</span>
              <code>{{ c.base_type }}</code>
            </div>
          </div>

          <!-- PK NULL -->
          <div class="pf-item pf-warn" v-if="(analysis.columns?.pk_null_columns || []).length > 0">
            <span class="pf-item-icon">⚠️</span>
            <span class="pf-item-label">PK NULL 허용 컬럼</span>
            <span class="pf-item-count">{{ analysis.columns.pk_null_columns.length }}건</span>
            <span class="pf-item-desc">NOT NULL 강제 (Phase 1-C)</span>
            <button class="pf-detail-btn" @click="toggleDetail('pkNull')">
              {{ details.pkNull ? '▼' : '▶' }}
            </button>
          </div>
          <div v-show="details.pkNull" class="pf-detail">
            <div v-for="(c, i) in (analysis.columns?.pk_null_columns || [])" :key="i" class="pf-detail-row">
              <code>{{ c.schema }}.{{ c.table }}.{{ c.column }}</code>
              <span>({{ c.type }})</span>
            </div>
          </div>

          <!-- nvarchar(max) PK -->
          <div class="pf-item pf-warn" v-if="(analysis.columns?.nvarchar_max_pk || []).length > 0">
            <span class="pf-item-icon">⚠️</span>
            <span class="pf-item-label">nvarchar(max) PK</span>
            <span class="pf-item-count">{{ analysis.columns.nvarchar_max_pk.length }}건</span>
            <span class="pf-item-desc">VARCHAR(255) 강제 (Phase 1-D)</span>
          </div>

          <!-- 특수 시스템 타입 -->
          <div v-for="(items, typeName) in (analysis.columns?.special_types || {})" :key="typeName"
               class="pf-item" :class="`pf-${specialTypeRisk(typeName)}`">
            <span class="pf-item-icon">{{ specialTypeIcon(typeName) }}</span>
            <span class="pf-item-label">{{ typeName }}</span>
            <span class="pf-item-count">{{ items.length }}개</span>
            <span class="pf-item-desc">{{ specialTypeDesc(typeName) }}</span>
            <button class="pf-detail-btn" @click="toggleDetail(typeName)">
              {{ details[typeName] ? '▼' : '▶' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 2. 객체 DDL 정적 분석 -->
      <div class="pf-section">
        <h4 class="pf-section-title">⚙️ 객체 변환 사전 분석</h4>
        <div class="pf-section-body">
          <div class="pf-item pf-info">
            <span class="pf-item-icon">📦</span>
            <span class="pf-item-label">총 객체 수</span>
            <span class="pf-item-count">{{ analysis.objects?.total_objects || 0 }}개</span>
          </div>

          <!-- 위험 패턴별 그룹 -->
          <div v-for="(items, riskId) in groupedRiskyPatterns" :key="riskId"
               class="pf-item pf-high">
            <span class="pf-item-icon">🔴</span>
            <span class="pf-item-label">{{ items[0]?.desc || riskId }}</span>
            <span class="pf-item-count">{{ items.length }}건</span>
            <span class="pf-item-desc">{{ items[0]?.fix }}</span>
            <button class="pf-detail-btn" @click="toggleDetail(`risk_${riskId}`)">
              {{ details[`risk_${riskId}`] ? '▼' : '▶' }}
            </button>
          </div>
          <div v-for="(items, riskId) in groupedRiskyPatterns" :key="`d_${riskId}`"
               v-show="details[`risk_${riskId}`]" class="pf-detail">
            <div v-for="(o, i) in items" :key="i" class="pf-detail-row">
              <code>{{ o.schema }}.{{ o.object }}</code>
              <span class="pf-tag">{{ o.type }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 3. 의존성 그래프 -->
      <div class="pf-section">
        <h4 class="pf-section-title">🔗 의존성 그래프</h4>
        <div class="pf-section-body">
          <div class="pf-item pf-info">
            <span class="pf-item-icon">📐</span>
            <span class="pf-item-label">FK 개수</span>
            <span class="pf-item-count">{{ analysis.dependencies?.total_fks || 0 }}개</span>
          </div>
          <div class="pf-item" :class="(analysis.dependencies?.circular_refs?.length || 0) > 0 ? 'pf-warn' : 'pf-info'">
            <span class="pf-item-icon">{{ (analysis.dependencies?.circular_refs?.length || 0) > 0 ? '🔁' : '✅' }}</span>
            <span class="pf-item-label">순환 참조</span>
            <span class="pf-item-count">{{ analysis.dependencies?.circular_refs?.length || 0 }}건</span>
            <span class="pf-item-desc">FK 임시 비활성화로 처리</span>
          </div>
          <div class="pf-item pf-info">
            <span class="pf-item-icon">📏</span>
            <span class="pf-item-label">참조 깊이</span>
            <span class="pf-item-count">{{ analysis.dependencies?.max_depth || 0 }}단계</span>
          </div>
        </div>
      </div>

      <!-- 4. 대용량 -->
      <div class="pf-section" v-if="(analysis.sizes?.huge_tables?.length || 0) + (analysis.sizes?.large_tables?.length || 0) > 0">
        <h4 class="pf-section-title">⏱️ 대용량 / 성능 분석</h4>
        <div class="pf-section-body">
          <div class="pf-item pf-info">
            <span class="pf-item-icon">📊</span>
            <span class="pf-item-label">전체 행 수</span>
            <span class="pf-item-count">{{ formatNumber(analysis.sizes?.total_rows) }}</span>
          </div>
          <div v-if="(analysis.sizes?.huge_tables?.length || 0) > 0" class="pf-item pf-warn">
            <span class="pf-item-icon">🐘</span>
            <span class="pf-item-label">100만 행 이상</span>
            <span class="pf-item-count">{{ analysis.sizes.huge_tables.length }}건</span>
            <span class="pf-item-desc">청크 병렬 권장</span>
          </div>
          <div v-if="(analysis.sizes?.large_tables?.length || 0) > 0" class="pf-item pf-info">
            <span class="pf-item-icon">📦</span>
            <span class="pf-item-label">10만 행 이상</span>
            <span class="pf-item-count">{{ analysis.sizes.large_tables.length }}건</span>
          </div>
        </div>
      </div>

      <!-- 액션 -->
      <div class="pf-actions">
        <button class="pf-action-btn" @click="runAnalysis">🔄 다시 분석</button>
        <button class="pf-action-btn pf-action-secondary" @click="$emit('skip')">계속 진행</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import axios from 'axios'

const props = defineProps({
  selection: { type: Object, default: () => ({}) },
  conn: { type: Object, default: () => ({}) },  // {host, port, username, password, database, src_db}
})

const emit = defineEmits(['skip', 'analysis-complete'])

const analysis = ref(null)
const analyzing = ref(false)
const progressText = ref('초기화')
const details = reactive({})

const SPECIAL_TYPES_INFO = {
  hierarchyid:    { icon: '🔴', risk: 'high',   desc: '계층 경로 — ToString() 변환 필요' },
  geography:      { icon: '🔴', risk: 'high',   desc: '공간 — STAsText() 변환 필요' },
  geometry:       { icon: '🔴', risk: 'high',   desc: '공간 — STAsText() 변환 필요' },
  sql_variant:    { icon: '⚠️', risk: 'warn',   desc: '다중 타입 — 미지원' },
  xml:            { icon: 'ℹ️', risk: 'info',   desc: 'LONGTEXT 매핑' },
  image:          { icon: '⚠️', risk: 'warn',   desc: 'Deprecated' },
  ntext:          { icon: 'ℹ️', risk: 'info',   desc: 'Deprecated' },
  text:           { icon: 'ℹ️', risk: 'info',   desc: 'Deprecated' },
  rowversion:     { icon: '⚠️', risk: 'warn',   desc: 'BIGINT 변환' },
  timestamp:      { icon: '⚠️', risk: 'warn',   desc: 'BIGINT 변환' },
  datetimeoffset: { icon: '⚠️', risk: 'warn',   desc: 'DATETIME(6) — TZ 손실' },
}

const selectionSummary = computed(() => {
  const sel = props.selection || {}
  const tables = (sel.tables || []).length
  const objs = (sel.objects || []).length
  return `테이블 ${tables}개 + 객체 ${objs}개`
})

const overallTitle = computed(() => {
  const lv = analysis.value?.overall_risk?.level
  if (lv === 'high') return '🔴 고위험 — 신중한 검토 권장'
  if (lv === 'medium') return '🟡 주의 — 일부 위험 항목 존재'
  return '🟢 안전 — 표준 처방으로 처리 가능'
})

const groupedRiskyPatterns = computed(() => {
  const items = analysis.value?.objects?.risky_patterns || []
  const groups = {}
  items.forEach(it => {
    if (!groups[it.risk_id]) groups[it.risk_id] = []
    groups[it.risk_id].push(it)
  })
  return groups
})

function specialTypeIcon(t) { return SPECIAL_TYPES_INFO[t]?.icon || 'ℹ️' }
function specialTypeRisk(t) { return SPECIAL_TYPES_INFO[t]?.risk || 'info' }
function specialTypeDesc(t) { return SPECIAL_TYPES_INFO[t]?.desc || '' }

function toggleDetail(key) { details[key] = !details[key] }

function formatNumber(n) {
  if (!n) return '0'
  return Number(n).toLocaleString()
}

async function runAnalysis() {
  analyzing.value = true
  analysis.value = null
  progressText.value = '연결 중'

  try {
    const sel = props.selection || {}
    const schemas = sel.schemas || []
    const tables = (sel.tables || []).map(t => 
      typeof t === 'string' ? t : t.name || t.table
    )
    
    progressText.value = '메타 분석 중'
    const { data } = await axios.post('/api/v1/preflight-analysis', {
      conn:    props.conn,
      schemas: schemas.length > 0 ? schemas : null,
      tables:  tables.length > 0 ? tables : null,
    })
    
    analysis.value = data
    emit('analysis-complete', data)
  } catch (e) {
    console.error('Pre-Flight 분석 실패:', e)
    alert('분석 실패: ' + (e.response?.data?.detail || e.message))
  } finally {
    analyzing.value = false
  }
}
</script>

<style scoped>
.preflight-panel {
  padding: 16px 20px;
  font-family: -apple-system, system-ui, sans-serif;
}
.pf-header { margin-bottom: 16px; }
.pf-title { margin: 0 0 6px 0; font-size: 18px; }
.pf-subtitle { margin: 0; color: #666; font-size: 13px; line-height: 1.5; }

.pf-start {
  background: #f8f9fa;
  border: 1px dashed #cbd5e0;
  border-radius: 8px;
  padding: 24px;
  text-align: center;
  margin: 16px 0;
}
.pf-start-info { font-size: 14px; color: #4a5568; margin-bottom: 12px; }
.pf-start-btn {
  background: #4299e1; color: white; border: none;
  padding: 10px 24px; border-radius: 6px; font-size: 14px;
  cursor: pointer; font-weight: 600;
}
.pf-start-btn:hover { background: #3182ce; }

.pf-loading {
  text-align: center; padding: 40px; color: #4a5568;
}
.pf-spinner { font-size: 32px; margin-bottom: 8px; }

.pf-overall {
  display: flex; align-items: center; gap: 16px;
  padding: 16px 20px;
  border-radius: 8px;
  margin: 12px 0 20px 0;
  border-left: 4px solid;
}
.pf-overall.pf-risk-low    { background: #f0fff4; border-color: #38a169; }
.pf-overall.pf-risk-medium { background: #fffaf0; border-color: #ed8936; }
.pf-overall.pf-risk-high   { background: #fff5f5; border-color: #e53e3e; }
.pf-overall-icon { font-size: 36px; }
.pf-overall-title { font-size: 16px; font-weight: 600; }
.pf-overall-summary { font-size: 13px; color: #718096; margin-top: 2px; }

.pf-section {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 12px;
  overflow: hidden;
}
.pf-section-title {
  margin: 0; padding: 12px 16px;
  background: #f7fafc; border-bottom: 1px solid #e2e8f0;
  font-size: 14px;
}
.pf-section-body { padding: 8px 0; }

.pf-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 16px;
  border-bottom: 1px solid #f1f5f9;
  font-size: 13px;
}
.pf-item:last-child { border-bottom: none; }
.pf-item-icon { width: 22px; }
.pf-item-label { font-weight: 600; min-width: 140px; }
.pf-item-count { 
  background: #edf2f7; padding: 2px 8px; border-radius: 4px;
  font-weight: 600; color: #4a5568;
}
.pf-item-desc { color: #718096; flex: 1; font-size: 12px; }

.pf-info { background: white; }
.pf-warn { background: #fffaf0; }
.pf-warn .pf-item-count { background: #fed7aa; color: #c05621; }
.pf-high { background: #fff5f5; }
.pf-high .pf-item-count { background: #fed7d7; color: #c53030; }

.pf-detail-btn {
  background: none; border: 1px solid #cbd5e0;
  padding: 2px 8px; border-radius: 4px;
  cursor: pointer; font-size: 11px;
}

.pf-detail {
  padding: 8px 16px 12px 50px;
  background: #f7fafc;
  font-size: 12px;
  border-top: 1px solid #f1f5f9;
}
.pf-detail-row {
  display: flex; align-items: center; gap: 8px;
  padding: 3px 0;
}
.pf-detail code {
  background: white; padding: 1px 6px; border-radius: 3px;
  font-family: 'Consolas', 'Monaco', monospace;
  border: 1px solid #e2e8f0;
}
.pf-arrow { color: #a0aec0; }
.pf-tag {
  background: #e2e8f0; padding: 1px 6px; border-radius: 3px;
  font-size: 10px;
}

.pf-actions {
  display: flex; gap: 8px; justify-content: flex-end;
  margin-top: 16px; padding-top: 16px;
  border-top: 1px solid #e2e8f0;
}
.pf-action-btn {
  padding: 8px 16px; border-radius: 6px;
  border: 1px solid #cbd5e0; background: white;
  cursor: pointer; font-size: 13px;
}
.pf-action-btn:hover { background: #f7fafc; }
.pf-action-secondary { background: #4299e1; color: white; border-color: #4299e1; }
.pf-action-secondary:hover { background: #3182ce; }
</style>
