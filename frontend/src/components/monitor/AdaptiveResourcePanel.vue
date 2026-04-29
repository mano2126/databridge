<!--
  AdaptiveResourcePanel.vue — Phase I-7 (2026-04-25)
  
  이관 모니터 팝업에 추가되는 "AI 리소스 제어" 패널.
  
  기능:
    - 현재 시스템 상태 (CPU/메모리/lock) 실시간 표시
    - AI 자동 모드 / 수동 모드 / 하이브리드 토글
    - throttle 슬라이더 (100/75/50/25%)
    - 테이블 일시정지 버튼
    - AI 의사결정 타임라인 (최근 10건)
    - WebSocket 으로 실시간 업데이트
  
  Props:
    jobId: 활성 Job ID
  
  WebSocket: /api/v1/jobs/{jobId}/resource/stream
-->
<template>
  <div class="arc-panel">
    
    <!-- 헤더 -->
    <div class="arc-header">
      <div class="arc-header-icon">⚡</div>
      <div class="arc-header-body">
        <div class="arc-header-title">AI 리소스 제어</div>
        <div class="arc-header-subtitle">
          <span :class="['arc-mode-badge', `arc-mode-${policy.mode}`]">
            {{ modeLabels[policy.mode] }}
          </span>
          <span class="arc-divider">•</span>
          <span class="arc-throttle-current">throttle {{ policy.throttle_pct }}%</span>
          <span class="arc-divider" v-if="!connected">•</span>
          <span class="arc-disconnected" v-if="!connected">⚠️ 연결 끊김</span>
        </div>
      </div>
      <div class="arc-header-status" :class="`arc-health-${currentHealth}`">
        <span class="arc-health-dot"></span>
        {{ healthLabels[currentHealth] }}
      </div>
    </div>

    <!-- 모드 전환 -->
    <div class="arc-section">
      <div class="arc-section-title">제어 모드</div>
      <div class="arc-mode-toggle">
        <button
          v-for="m in modeOptions"
          :key="m.value"
          class="arc-mode-btn"
          :class="{ 'arc-mode-active': policy.mode === m.value }"
          @click="setMode(m.value)"
        >
          <span class="arc-mode-icon">{{ m.icon }}</span>
          <span class="arc-mode-label">{{ m.label }}</span>
          <span class="arc-mode-desc">{{ m.desc }}</span>
        </button>
      </div>
    </div>

    <!-- 메트릭 그리드 -->
    <div class="arc-section">
      <div class="arc-section-title">실시간 메트릭</div>
      <div class="arc-metrics-grid">
        
        <div class="arc-metric" :class="getCpuClass(latestSnapshot?.src_cpu_pct)">
          <div class="arc-metric-label">소스 CPU</div>
          <div class="arc-metric-value">
            {{ formatPct(latestSnapshot?.src_cpu_pct) }}
          </div>
          <div class="arc-metric-bar">
            <div class="arc-metric-fill" 
                 :style="`width: ${latestSnapshot?.src_cpu_pct || 0}%`"></div>
          </div>
        </div>
        
        <div class="arc-metric" :class="getCpuClass(latestSnapshot?.container_cpu_pct)">
          <div class="arc-metric-label">컨테이너 CPU</div>
          <div class="arc-metric-value">
            {{ formatPct(latestSnapshot?.container_cpu_pct) }}
          </div>
          <div class="arc-metric-bar">
            <div class="arc-metric-fill"
                 :style="`width: ${latestSnapshot?.container_cpu_pct || 0}%`"></div>
          </div>
        </div>
        
        <div class="arc-metric" :class="getMemClass(latestSnapshot?.container_mem_pct)">
          <div class="arc-metric-label">메모리</div>
          <div class="arc-metric-value">
            {{ formatPct(latestSnapshot?.container_mem_pct) }}
          </div>
          <div class="arc-metric-bar">
            <div class="arc-metric-fill"
                 :style="`width: ${latestSnapshot?.container_mem_pct || 0}%`"></div>
          </div>
        </div>
        
        <div class="arc-metric" :class="getLockClass(latestSnapshot?.src_lock_wait_count)">
          <div class="arc-metric-label">Lock Waits</div>
          <div class="arc-metric-value">
            {{ latestSnapshot?.src_lock_wait_count ?? '—' }}
          </div>
          <div class="arc-metric-sub">대기 중</div>
        </div>
        
        <div class="arc-metric">
          <div class="arc-metric-label">처리율</div>
          <div class="arc-metric-value">
            {{ formatNumber(latestSnapshot?.rows_per_sec) }}
          </div>
          <div class="arc-metric-sub">rows/sec</div>
        </div>
        
        <div class="arc-metric">
          <div class="arc-metric-label">진행률</div>
          <div class="arc-metric-value">
            {{ formatPct(latestSnapshot?.progress_pct) }}
          </div>
          <div class="arc-metric-bar">
            <div class="arc-metric-fill arc-fill-progress"
                 :style="`width: ${latestSnapshot?.progress_pct || 0}%`"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Throttle 슬라이더 -->
    <div class="arc-section">
      <div class="arc-section-title">
        Throttle
        <span class="arc-section-sub" v-if="policy.mode === 'auto'">
          🤖 AI 가 자동 조절 중 (수동 변경 가능)
        </span>
      </div>
      <div class="arc-throttle-buttons">
        <button
          v-for="pct in [100, 75, 50, 25]"
          :key="pct"
          class="arc-throttle-btn"
          :class="{ 'arc-throttle-active': policy.throttle_pct === pct }"
          @click="setThrottle(pct)"
          :disabled="changing"
        >
          <span class="arc-throttle-pct">{{ pct }}%</span>
          <span class="arc-throttle-batch">batch {{ throttleToBatch(pct) }}</span>
        </button>
      </div>
    </div>

    <!-- 테이블 일시정지 (있으면) -->
    <div class="arc-section" v-if="policy.paused_tables?.length || tablesInProgress.length">
      <div class="arc-section-title">테이블 제어</div>
      
      <div v-if="policy.paused_tables?.length" class="arc-paused-list">
        <div class="arc-paused-label">일시정지 중:</div>
        <div class="arc-paused-tables">
          <div v-for="t in policy.paused_tables" :key="t" class="arc-paused-chip">
            <span>{{ t }}</span>
            <button class="arc-resume-btn" @click="resumeTable(t)">▶ 재개</button>
          </div>
        </div>
      </div>
      
      <div v-if="tablesInProgress.length" class="arc-progress-tables">
        <div class="arc-paused-label">진행 중 (클릭하여 일시정지):</div>
        <div class="arc-progress-list">
          <button
            v-for="t in tablesInProgress.slice(0, 5)"
            :key="t"
            class="arc-pause-btn"
            @click="pauseTable(t)"
          >
            ⏸ {{ t }}
          </button>
        </div>
      </div>
    </div>

    <!-- AI 의사결정 타임라인 -->
    <div class="arc-section">
      <div class="arc-section-title">
        🤖 AI 의사결정 ({{ recentDecisions.length }}건)
      </div>
      
      <div v-if="!recentDecisions.length" class="arc-no-decisions">
        아직 결정 없음 — 시스템 상태 양호
      </div>
      
      <div v-else class="arc-timeline">
        <div
          v-for="d in recentDecisions"
          :key="d.decision_id || d.timestamp"
          class="arc-timeline-item"
          :class="`arc-decision-${d.triggered_by?.startsWith('ai') ? 'ai' : 'manual'}`"
        >
          <div class="arc-timeline-icon">
            {{ d.triggered_by?.startsWith('ai') ? '🤖' : '👤' }}
          </div>
          <div class="arc-timeline-body">
            <div class="arc-timeline-action">
              <span class="arc-timeline-time">{{ formatTime(d.timestamp) }}</span>
              <span class="arc-timeline-change">
                <template v-if="d.action === 'set_throttle'">
                  Throttle <b>{{ d.from || d.from_value }}%</b> → <b>{{ d.to || d.to_value }}%</b>
                </template>
                <template v-else-if="d.action === 'pause_table'">
                  ⏸ <b>{{ d.target }}</b> 일시정지
                </template>
                <template v-else-if="d.action === 'resume_table'">
                  ▶ <b>{{ d.target }}</b> 재개
                </template>
                <template v-else-if="d.action === 'set_mode'">
                  모드 <b>{{ d.from || d.from_value }}</b> → <b>{{ d.to || d.to_value }}</b>
                </template>
                <template v-else>
                  {{ d.action }}
                </template>
              </span>
              <span v-if="d.health_status" 
                    class="arc-timeline-health" 
                    :class="`arc-health-${d.health_status}`">
                {{ healthLabels[d.health_status] }}
              </span>
            </div>
            <div class="arc-timeline-reason">{{ d.reason }}</div>
            <div v-if="d.confidence !== undefined && d.triggered_by?.startsWith('ai')"
                 class="arc-timeline-confidence">
              확신도: {{ Math.round(d.confidence * 100) }}%
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps({
  jobId: { type: String, required: true },
  tablesInProgress: { type: Array, default: () => [] },  // 부모에서 전달
})

// ── 상태 ──
const ws = ref(null)
const connected = ref(false)
const changing = ref(false)
const reconnectTimer = ref(null)

const latestSnapshot = ref(null)
const policy = ref({
  mode: 'hybrid',
  throttle_pct: 100,
  batch_size: 5000,
  parallelism: 3,
  paused_tables: [],
})
const recentDecisions = ref([])

// ── 라벨 ──
const modeLabels = {
  auto: '🤖 AI 자동',
  manual: '👤 수동',
  hybrid: '🤝 하이브리드',
}

const modeOptions = [
  { value: 'auto', icon: '🤖', label: 'AI 자동', desc: 'AI 가 모든 결정' },
  { value: 'hybrid', icon: '🤝', label: '하이브리드', desc: 'AI + 운영자' },
  { value: 'manual', icon: '👤', label: '수동', desc: '운영자만' },
]

const healthLabels = {
  excellent: '🟢 매우 양호',
  good: '🟢 양호',
  warning: '🟡 주의',
  critical: '🔴 위험',
  emergency: '🚨 긴급',
}

// ── 계산 속성 ──
const currentHealth = computed(() => {
  const cpu = latestSnapshot.value?.src_cpu_pct
  const lock = latestSnapshot.value?.src_lock_wait_count
  if (cpu == null) return 'good'
  if (cpu >= 90 || lock >= 200) return 'critical'
  if (cpu >= 75 || lock >= 50) return 'warning'
  if (cpu < 50 && lock < 10) return 'excellent'
  return 'good'
})

// ── 헬퍼 ──
function formatPct(v) {
  if (v == null) return '—'
  return `${Math.round(v)}%`
}

function formatNumber(v) {
  if (v == null) return '—'
  if (v < 1000) return Math.round(v).toLocaleString()
  return `${(v / 1000).toFixed(1)}k`
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return d.toTimeString().slice(0, 8)
}

function throttleToBatch(pct) {
  return Math.max(500, Math.round(5000 * pct / 100))
}

function getCpuClass(v) {
  if (v == null) return ''
  if (v >= 90) return 'arc-metric-critical'
  if (v >= 75) return 'arc-metric-warning'
  if (v < 50) return 'arc-metric-good'
  return ''
}

function getMemClass(v) {
  if (v == null) return ''
  if (v >= 95) return 'arc-metric-critical'
  if (v >= 80) return 'arc-metric-warning'
  return ''
}

function getLockClass(v) {
  if (v == null) return ''
  if (v >= 200) return 'arc-metric-critical'
  if (v >= 50) return 'arc-metric-warning'
  return ''
}

// ── WebSocket 연결 ──
function connect() {
  if (ws.value) return
  
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${proto}//${window.location.host}/api/v1/jobs/${props.jobId}/resource/stream`
  
  try {
    ws.value = new WebSocket(url)
  } catch (e) {
    console.warn('[ARC] WebSocket 생성 실패:', e)
    scheduleReconnect()
    return
  }
  
  ws.value.onopen = () => {
    connected.value = true
    console.log('[ARC] WebSocket 연결됨')
  }
  
  ws.value.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      handleMessage(msg)
    } catch (e) {
      console.warn('[ARC] 메시지 파싱 실패:', e)
    }
  }
  
  ws.value.onclose = () => {
    connected.value = false
    ws.value = null
    scheduleReconnect()
  }
  
  ws.value.onerror = (e) => {
    console.warn('[ARC] WebSocket 에러:', e)
    connected.value = false
  }
}

function scheduleReconnect() {
  if (reconnectTimer.value) return
  reconnectTimer.value = setTimeout(() => {
    reconnectTimer.value = null
    connect()
  }, 3000)
}

function handleMessage(msg) {
  if (msg.type === 'snapshot') {
    latestSnapshot.value = msg.data
  } else if (msg.type === 'policy') {
    policy.value = msg.data
  } else if (msg.type === 'decision') {
    // 새 결정 추가 (앞에 끼워넣기)
    recentDecisions.value = [msg.data, ...recentDecisions.value].slice(0, 10)
  } else if (msg.type === 'error') {
    console.warn('[ARC] 서버 에러:', msg.message)
  }
}

// ── 액션 ──
async function setThrottle(pct) {
  if (changing.value) return
  changing.value = true
  try {
    const r = await fetch(`/api/v1/jobs/${props.jobId}/resource/throttle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ throttle_pct: pct, user: 'web-ui' }),
    })
    if (!r.ok) {
      const err = await r.json().catch(() => ({}))
      console.warn('throttle 변경 실패:', err)
    }
  } catch (e) {
    console.warn('[ARC] throttle 변경 에러:', e)
  } finally {
    changing.value = false
  }
}

async function setMode(mode) {
  if (changing.value) return
  changing.value = true
  try {
    await fetch(`/api/v1/jobs/${props.jobId}/resource/mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ mode, user: 'web-ui' }),
    })
  } catch (e) {
    console.warn('[ARC] 모드 변경 에러:', e)
  } finally {
    changing.value = false
  }
}

async function pauseTable(name) {
  try {
    await fetch(`/api/v1/jobs/${props.jobId}/resource/pause`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ table_name: name, user: 'web-ui' }),
    })
  } catch (e) {
    console.warn('[ARC] pause 에러:', e)
  }
}

async function resumeTable(name) {
  try {
    await fetch(`/api/v1/jobs/${props.jobId}/resource/resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ table_name: name, user: 'web-ui' }),
    })
  } catch (e) {
    console.warn('[ARC] resume 에러:', e)
  }
}

// ── 라이프사이클 ──
onMounted(() => {
  // 초기 상태 로드
  fetch(`/api/v1/jobs/${props.jobId}/resource/status`, { credentials: 'include' })
    .then(r => r.ok ? r.json() : null)
    .then(d => {
      if (d) {
        if (d.policy) policy.value = d.policy
        if (d.recent_decisions) recentDecisions.value = d.recent_decisions
        if (d.latest_snapshot) latestSnapshot.value = d.latest_snapshot
      }
    })
    .catch(() => {})
  
  // WebSocket 연결
  connect()
})

onUnmounted(() => {
  if (reconnectTimer.value) clearTimeout(reconnectTimer.value)
  if (ws.value) {
    try { ws.value.close() } catch (e) {}
    ws.value = null
  }
})

watch(() => props.jobId, () => {
  // jobId 변경 시 재연결
  if (ws.value) {
    try { ws.value.close() } catch (e) {}
    ws.value = null
  }
  connect()
})
</script>

<style scoped>
.arc-panel {
  display: flex; flex-direction: column; gap: 14px;
  font-size: 13px;
}

/* 헤더 */
.arc-header {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 12px 14px;
  background: linear-gradient(135deg, #f0fdfa 0%, #ecfeff 100%);
  border-left: 3px solid #14b8a6;
  border-radius: 8px;
}
.arc-header-icon { font-size: 22px; }
.arc-header-body { flex: 1; }
.arc-header-title { font-size: 14px; font-weight: 700; color: #0f766e; margin-bottom: 4px; }
.arc-header-subtitle { font-size: 11px; color: #475569; display: flex; align-items: center; gap: 4px; }
.arc-divider { color: #cbd5e1; }
.arc-mode-badge {
  display: inline-block; padding: 1px 8px; border-radius: 99px;
  font-size: 10px; font-weight: 700;
}
.arc-mode-auto { background: #ddd6fe; color: #7c3aed; }
.arc-mode-manual { background: #fef3c7; color: #b45309; }
.arc-mode-hybrid { background: #dbeafe; color: #1e40af; }
.arc-throttle-current { font-weight: 600; color: #0f766e; font-family: monospace; }
.arc-disconnected { color: #dc2626; font-weight: 600; }
.arc-header-status {
  display: flex; align-items: center; gap: 5px;
  font-size: 11px; font-weight: 700;
  padding: 4px 10px; border-radius: 99px;
}
.arc-health-dot {
  display: inline-block; width: 8px; height: 8px;
  border-radius: 50%; background: currentColor;
}
.arc-health-excellent { background: #dcfce7; color: #16a34a; }
.arc-health-good { background: #dcfce7; color: #16a34a; }
.arc-health-warning { background: #fef9c3; color: #ca8a04; }
.arc-health-critical { background: #fee2e2; color: #dc2626; }
.arc-health-emergency { background: #fee2e2; color: #991b1b; animation: arc-pulse 1s infinite; }
@keyframes arc-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

/* 섹션 */
.arc-section {
  padding: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}
.arc-section-title {
  font-size: 12px; font-weight: 700; color: #1e293b;
  margin-bottom: 10px;
  display: flex; align-items: center; gap: 8px;
}
.arc-section-sub {
  font-size: 10px; font-weight: 500; color: #94a3b8;
  margin-left: auto;
}

/* 모드 토글 */
.arc-mode-toggle {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px;
}
.arc-mode-btn {
  display: flex; flex-direction: column; align-items: center;
  padding: 10px 6px; gap: 2px;
  background: #f8fafc;
  border: 1.5px solid #e2e8f0;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.arc-mode-btn:hover { border-color: #5eead4; background: #f0fdfa; }
.arc-mode-active {
  background: #14b8a6 !important;
  border-color: #14b8a6 !important;
  color: #fff;
}
.arc-mode-active .arc-mode-desc { color: #ccfbf1; }
.arc-mode-icon { font-size: 18px; }
.arc-mode-label { font-size: 12px; font-weight: 700; }
.arc-mode-desc { font-size: 10px; color: #64748b; }

/* 메트릭 그리드 */
.arc-metrics-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
}
.arc-metric {
  padding: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}
.arc-metric-good { background: #f0fdf4; border-color: #86efac; }
.arc-metric-warning { background: #fef9c3; border-color: #fde047; }
.arc-metric-critical { background: #fee2e2; border-color: #fca5a5; }
.arc-metric-label {
  font-size: 10px; color: #64748b;
  text-transform: uppercase; letter-spacing: 0.5px;
  margin-bottom: 4px;
}
.arc-metric-value {
  font-size: 18px; font-weight: 700; color: #1e293b;
  font-family: 'JetBrains Mono', monospace;
  line-height: 1;
}
.arc-metric-sub {
  font-size: 10px; color: #94a3b8;
  margin-top: 2px;
}
.arc-metric-bar {
  margin-top: 6px;
  height: 4px;
  background: #e2e8f0;
  border-radius: 99px;
  overflow: hidden;
}
.arc-metric-fill {
  height: 100%;
  background: linear-gradient(90deg, #14b8a6, #f59e0b 75%, #dc2626 90%);
  border-radius: 99px;
  transition: width 0.5s ease;
}
.arc-fill-progress { background: #14b8a6 !important; }

/* Throttle 버튼 */
.arc-throttle-buttons {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px;
}
.arc-throttle-btn {
  display: flex; flex-direction: column; align-items: center;
  padding: 10px 4px; gap: 2px;
  background: #fff;
  border: 1.5px solid #e2e8f0;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.arc-throttle-btn:hover { border-color: #5eead4; background: #f0fdfa; }
.arc-throttle-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.arc-throttle-active {
  background: #0f766e !important;
  border-color: #0f766e !important;
  color: #fff;
}
.arc-throttle-pct { font-size: 14px; font-weight: 700; }
.arc-throttle-batch { font-size: 10px; color: #64748b; }
.arc-throttle-active .arc-throttle-batch { color: #ccfbf1; }

/* 테이블 일시정지 */
.arc-paused-list, .arc-progress-tables { margin-bottom: 8px; }
.arc-paused-label {
  font-size: 11px; color: #64748b;
  margin-bottom: 4px;
}
.arc-paused-tables, .arc-progress-list {
  display: flex; flex-wrap: wrap; gap: 4px;
}
.arc-paused-chip {
  display: flex; align-items: center; gap: 4px;
  padding: 3px 8px;
  background: #fef3c7;
  border: 1px solid #fde047;
  border-radius: 99px;
  font-size: 11px;
}
.arc-resume-btn {
  background: #16a34a;
  color: #fff;
  border: none;
  padding: 1px 6px;
  border-radius: 99px;
  font-size: 10px;
  cursor: pointer;
}
.arc-pause-btn {
  padding: 3px 8px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 99px;
  font-size: 11px;
  cursor: pointer;
}
.arc-pause-btn:hover { background: #fef3c7; border-color: #fde047; }

/* AI 의사결정 타임라인 */
.arc-no-decisions {
  padding: 16px;
  text-align: center;
  font-size: 12px;
  color: #94a3b8;
  background: #f8fafc;
  border-radius: 6px;
}
.arc-timeline {
  display: flex; flex-direction: column; gap: 6px;
  max-height: 300px;
  overflow-y: auto;
}
.arc-timeline-item {
  display: flex; gap: 8px;
  padding: 8px 10px;
  background: #f8fafc;
  border-left: 2px solid #14b8a6;
  border-radius: 4px;
}
.arc-decision-manual { border-left-color: #f59e0b; background: #fffbeb; }
.arc-timeline-icon { font-size: 16px; }
.arc-timeline-body { flex: 1; }
.arc-timeline-action {
  display: flex; align-items: center; gap: 8px;
  font-size: 12px;
  margin-bottom: 2px;
}
.arc-timeline-time {
  font-family: monospace;
  font-size: 10px;
  color: #94a3b8;
}
.arc-timeline-change b { color: #0f766e; }
.arc-timeline-health {
  font-size: 9px; padding: 1px 6px; border-radius: 99px;
  margin-left: auto;
}
.arc-timeline-reason {
  font-size: 11px; color: #64748b;
  line-height: 1.4;
}
.arc-timeline-confidence {
  font-size: 10px; color: #14b8a6;
  margin-top: 2px;
}
</style>
