<template>
  <div class="page admin-process">
    <div class="page-title">프로세스</div>
    <div class="page-desc">
      DataBridge Supervisor (port 8765) 가 Frontend + Backend 를 통합 관리합니다.
      JEUS NodeManager 동급 — KeepAlive 자동 재시작.
    </div>

    <div class="card setting-card supervisor-banner" :class="supervisorClass">
      <div class="sc-header">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px">
          <path d="M3 11h10M3 5h10M5 3v10M11 3v10"/>
        </svg>
        Supervisor
        <span class="badge-supervisor" :class="supervisorClass">{{ supervisorLabel }}</span>
        <span style="margin-left:auto;font-size:.7rem;color:var(--text-tertiary)">
          {{ statusUpdatedAgo }}
        </span>
      </div>
      <div class="supervisor-detail">
        <div v-if="status?.supervisor_running">
          ✓ Supervisor 실행 중 — PID {{ status.supervisor_pid }} · {{ status.supervisor_url || 'http://127.0.0.1:8765' }}
        </div>
        <div v-else style="color:#dc2626">
          ✗ Supervisor 응답 없음 — 터미널에서 <code class="mono">bash run_supervisor.sh start</code> 필요
        </div>
      </div>
    </div>

    <div class="card setting-card">
      <div class="sc-header">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px">
          <rect x="2" y="3" width="12" height="9" rx="1"/>
          <line x1="2" y1="6" x2="14" y2="6"/>
          <circle cx="4" cy="4.5" r=".5" fill="currentColor"/>
          <circle cx="5.5" cy="4.5" r=".5" fill="currentColor"/>
        </svg>
        Frontend (Vite · port {{ feStatus?.port || 3000 }})
      </div>
      <div class="status-hero">
        <div class="status-light-wrap">
          <span class="status-light" :class="feLightClass"><span class="status-light-inner"></span></span>
          <div class="status-text">
            <div class="status-label" :class="feLightClass">{{ feStatusLabel }}</div>
            <div class="status-detail" v-if="feStatus">
              <span v-if="feStatus.running">PID {{ feStatus.pid }} · 모드 {{ feModeKor }} · 가동 {{ feUptimeText }}</span>
              <span v-else style="color:#dc2626">{{ feOffReason }}</span>
            </div>
          </div>
        </div>
        <div class="action-group">
          <select v-model="selectedFeMode" class="mode-select" :disabled="feActionInFlight || !status?.supervisor_running">
            <option value="auto">AUTO</option>
            <option value="dev">DEV — npm run dev (HMR)</option>
            <option value="release">RELEASE — npx serve dist</option>
          </select>
          <button class="btn-action btn-restart" @click="onFeRestart" :disabled="!canFeRestart">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" style="width:13px;height:13px"><path d="M3 8a5 5 0 1 0 1.5-3.5L3 6M3 3v3h3" stroke-linecap="round" stroke-linejoin="round"/></svg>
            재시작
          </button>
          <button class="btn-action btn-stop" @click="onFeStop" :disabled="!canFeStop">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" style="width:13px;height:13px"><rect x="4" y="4" width="8" height="8" rx="1"/></svg>
            중지
          </button>
          <button class="btn-action btn-start" @click="onFeStart" :disabled="!canFeStart">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" style="width:13px;height:13px"><path d="M5 3l8 5-8 5z" stroke-linejoin="round"/></svg>
            시작
          </button>
        </div>
      </div>
      <div class="info-grid" v-if="feStatus?.running || feStatus?.frontend_dir">
        <div class="info-cell"><div class="info-label">PID</div><div class="info-value mono">{{ feStatus.pid || '—' }}</div></div>
        <div class="info-cell"><div class="info-label">모드</div><div class="info-value"><span class="mode-badge" :class="'mode-fe-' + feStatus.mode">{{ feModeKor }}</span></div></div>
        <div class="info-cell"><div class="info-label">가동 시간</div><div class="info-value mono">{{ feUptimeText }}</div></div>
        <div class="info-cell"><div class="info-label">포트</div><div class="info-value mono">{{ feStatus.port || 3000 }}</div></div>
        <div class="info-cell"><div class="info-label">dist 빌드</div><div class="info-value"><span :class="feStatus.dist_exists ? 'tag-ok' : 'tag-warn'">{{ feStatus.dist_exists ? '✓ 존재' : '⚠ 없음' }}</span></div></div>
        <div class="info-cell"><div class="info-label">npm</div><div class="info-value mono" :title="feStatus.npm_path"><span :class="feStatus.npm_path ? 'tag-ok' : 'tag-warn'">{{ feStatus.npm_path ? '✓ 감지됨' : '⚠ 못 찾음' }}</span></div></div>
      </div>
    </div>

    <div class="card setting-card">
      <div class="sc-header">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px">
          <rect x="2" y="3" width="12" height="3.5" rx=".7"/>
          <rect x="2" y="9.5" width="12" height="3.5" rx=".7"/>
          <circle cx="4.5" cy="4.75" r=".7" fill="currentColor"/>
          <circle cx="4.5" cy="11.25" r=".7" fill="currentColor"/>
        </svg>
        Backend (FastAPI · port 8000)
      </div>
      <div class="status-hero">
        <div class="status-light-wrap">
          <span class="status-light" :class="beLightClass"><span class="status-light-inner"></span></span>
          <div class="status-text">
            <div class="status-label" :class="beLightClass">{{ beStatusLabel }}</div>
            <div class="status-detail" v-if="status">
              <span v-if="status.running">PID {{ status.pid }} · 모드 {{ beModeKor }} · 가동 {{ beUptimeText }}</span>
              <span v-else style="color:#dc2626">{{ beOffReason }}</span>
            </div>
          </div>
        </div>
        <div class="action-group">
          <select v-model="selectedBeMode" class="mode-select" :disabled="beActionInFlight || !status?.supervisor_running">
            <option value="safe">SAFE — 안전 (4,800 rows/s)</option>
            <option value="multiprocess">MULTIPROCESS — 빠름 (9,300 rows/s)</option>
            <option value="thread">THREAD — 진단용</option>
          </select>
          <button class="btn-action btn-restart" @click="onBeRestart" :disabled="!canBeRestart">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" style="width:13px;height:13px"><path d="M3 8a5 5 0 1 0 1.5-3.5L3 6M3 3v3h3" stroke-linecap="round" stroke-linejoin="round"/></svg>
            재시작
          </button>
          <button class="btn-action btn-stop" @click="onBeStop" :disabled="!canBeStop">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" style="width:13px;height:13px"><rect x="4" y="4" width="8" height="8" rx="1"/></svg>
            중지
          </button>
          <button class="btn-action btn-start" @click="onBeStart" :disabled="!canBeStart">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" style="width:13px;height:13px"><path d="M5 3l8 5-8 5z" stroke-linejoin="round"/></svg>
            시작
          </button>
        </div>
      </div>
      <div class="info-grid" v-if="status?.running">
        <div class="info-cell"><div class="info-label">PID</div><div class="info-value mono">{{ status.pid || '—' }}</div></div>
        <div class="info-cell"><div class="info-label">모드</div><div class="info-value"><span class="mode-badge" :class="'mode-' + status.mode">{{ beModeKor }}</span></div></div>
        <div class="info-cell"><div class="info-label">가동 시간</div><div class="info-value mono">{{ beUptimeText }}</div></div>
        <div class="info-cell"><div class="info-label">시작 시각</div><div class="info-value mono">{{ beStartedAtText }}</div></div>
        <div class="info-cell"><div class="info-label">콘솔 라인</div><div class="info-value mono">{{ status.console_lines || 0 }}</div></div>
      </div>
    </div>

    <div class="card setting-card console-card">
      <div class="sc-header console-header">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px">
          <rect x="2" y="3" width="12" height="10" rx="1"/>
          <path d="M5 7l2 1.5-2 1.5M9 11h3" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        실시간 콘솔
        <div class="console-tabs">
          <button :class="['tab', { active: activeConsole === 'frontend' }]" @click="switchConsole('frontend')">
            <span class="tab-dot" :class="frontendOn ? 'on' : 'off'"></span>
            Frontend
            <span class="tab-count" v-if="feLines.length">{{ feLines.length }}</span>
          </button>
          <button :class="['tab', { active: activeConsole === 'backend' }]" @click="switchConsole('backend')">
            <span class="tab-dot" :class="backendOn ? 'on' : 'off'"></span>
            Backend
            <span class="tab-count" v-if="beLines.length">{{ beLines.length }}</span>
          </button>
          <span style="flex:1"></span>
          <button class="popup-btn" @click="openPopup" :title="`${activeConsole === 'frontend' ? 'Frontend' : 'Backend'} 콘솔을 새창으로 열기`">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px">
              <path d="M9 2h5v5"/>
              <path d="M14 2L8 8"/>
              <path d="M11 9v4a1 1 0 01-1 1H3a1 1 0 01-1-1V6a1 1 0 011-1h4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            새창
          </button>
        </div>
      </div>
      <div class="console-toolbar">
        <input v-model="consoleFilter" :placeholder="`필터 (${activeConsole === 'frontend' ? 'Frontend' : 'Backend'} 라인)`" class="filter-input" />
        <label class="lbl"><input type="checkbox" v-model="autoScroll" /> 자동 스크롤</label>
        <span class="spacer"></span>
        <span class="conn-state" :class="currentConnected ? 'ok' : 'off'">● {{ currentConnected ? '실시간 연결됨' : 'WebSocket 끊김' }}</span>
        <button class="mini-btn" @click="copyCurrent">복사</button>
        <button class="mini-btn" @click="clearCurrent">지우기</button>
        <button class="mini-btn" @click="reconnectCurrent">재연결</button>
      </div>
      <div class="console-body" ref="consoleBodyEl">
        <div v-for="(l, idx) in filteredLines" :key="idx" class="line" :class="'stream-' + l.stream">
          <span class="ts">{{ l.ts }}</span>
          <span class="stream-tag">{{ l.stream }}</span>
          <span class="text">{{ l.line }}</span>
        </div>
        <div v-if="!filteredLines.length" class="empty">
          {{ currentConnected ? '아직 출력 없음...' : 'WebSocket 연결 대기 중' }}
        </div>
      </div>
      <div class="console-footer">{{ filteredLines.length }} / {{ currentLines.length }} lines · port 8765</div>
    </div>

    <div class="card setting-card" v-if="actionMsg">
      <div class="sc-header">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px">
          <circle cx="8" cy="8" r="7"/>
          <line x1="8" y1="5" x2="8" y2="9"/>
          <circle cx="8" cy="11.5" r=".7" fill="currentColor"/>
        </svg>
        동작 결과
      </div>
      <div class="action-msg" :class="'msg-' + actionMsgKind">
        <div class="action-msg-time">{{ actionMsgTime }}</div>
        <div class="action-msg-body">{{ actionMsg }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useAuthStore } from '@/store/authStore.js'

const authStore = useAuthStore()
const status = ref(null)
const selectedBeMode = ref('safe')
const selectedFeMode = ref('auto')
const beActionInFlight = ref(false)
const feActionInFlight = ref(false)
const actionMsg = ref('')
const actionMsgKind = ref('info')
const actionMsgTime = ref('')
const lastFetchTs = ref(0)

const activeConsole = ref('frontend')
const consoleFilter = ref('')
const autoScroll = ref(true)
const consoleBodyEl = ref(null)
const beLines = ref([])
const feLines = ref([])
const beConnected = ref(false)
const feConnected = ref(false)
const MAX_LINES = 5000

let pollTimer = null
let nowTimer = null
let beWs = null
let feWs = null
let beReconnectTimer = null
let feReconnectTimer = null
const now = ref(Date.now())

const supervisorClass = computed(() => {
  if (!status.value) return 'sup-unknown'
  return status.value.supervisor_running ? 'sup-on' : 'sup-off'
})
const supervisorLabel = computed(() => {
  if (!status.value) return '확인 중...'
  return status.value.supervisor_running ? '실행 중' : '중지됨'
})

const backendOn = computed(() => !!status.value?.running)
const beLightClass = computed(() => {
  if (!status.value || !status.value.supervisor_running) return 'light-unknown'
  return status.value.running ? 'light-on' : 'light-off'
})
const beStatusLabel = computed(() => {
  if (!status.value?.supervisor_running) return 'Supervisor 응답 없음'
  return status.value.running ? '실행 중' : '중지됨'
})
const beOffReason = computed(() => {
  if (!status.value) return ''
  if (!status.value.supervisor_running) return 'Supervisor 부팅 필요'
  return 'Backend 중지됨'
})
const beModeKor = computed(() => {
  const m = status.value?.mode
  return ({safe:'SAFE', multiprocess:'MULTIPROCESS', thread:'THREAD'})[m] || (m || '—')
})

const feStatus = computed(() => status.value?.frontend || {})
const frontendOn = computed(() => !!feStatus.value.running)
const feLightClass = computed(() => {
  if (!status.value?.supervisor_running) return 'light-unknown'
  return feStatus.value.running ? 'light-on' : 'light-off'
})
const feStatusLabel = computed(() => {
  if (!status.value?.supervisor_running) return 'Supervisor 응답 없음'
  return feStatus.value.running ? '실행 중' : '중지됨'
})
const feOffReason = computed(() => {
  if (!status.value?.supervisor_running) return 'Supervisor 부팅 필요'
  if (!feStatus.value.frontend_dir) return 'frontend 디렉토리 못 찾음'
  if (!feStatus.value.npm_path) return 'npm 경로 못 찾음'
  return 'Frontend 중지됨'
})
const feModeKor = computed(() => {
  const m = feStatus.value.mode
  return ({auto:'AUTO', dev:'DEV', release:'RELEASE'})[m] || (m || '—')
})

function fmtUptime(s) {
  if (!s) return '—'
  const sec = Math.floor(s)
  const d = Math.floor(sec / 86400)
  const h = Math.floor((sec % 86400) / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const ss = sec % 60
  if (d > 0) return `${d}일 ${h}시간 ${m}분`
  if (h > 0) return `${h}시간 ${m}분`
  if (m > 0) return `${m}분 ${ss}초`
  return `${ss}초`
}
function fmtStartedAt(t) {
  if (!t) return '—'
  return new Date(t * 1000).toLocaleString('ko-KR', {
    year:'numeric', month:'2-digit', day:'2-digit',
    hour:'2-digit', minute:'2-digit', second:'2-digit',
  })
}

const beUptimeText = computed(() => fmtUptime(status.value?.uptime_seconds))
const beStartedAtText = computed(() => fmtStartedAt(status.value?.started_at))
const feUptimeText = computed(() => fmtUptime(feStatus.value.uptime_seconds))

const statusUpdatedAgo = computed(() => {
  if (!lastFetchTs.value) return ''
  const sec = Math.floor((now.value - lastFetchTs.value) / 1000)
  if (sec < 5) return '방금 업데이트'
  if (sec < 60) return `${sec}초 전 업데이트`
  return `${Math.floor(sec / 60)}분 전 업데이트`
})

const isAdmin = computed(() => {
  if (!authStore?.hasRole) return true
  return authStore.hasRole('admin')
})
const supOk = computed(() => status.value?.supervisor_running === true)

const canBeStart = computed(() => isAdmin.value && supOk.value && !beActionInFlight.value && status.value && !status.value.running)
const canBeStop = computed(() => isAdmin.value && supOk.value && !beActionInFlight.value && status.value && status.value.running)
const canBeRestart = computed(() => canBeStop.value)
const canFeStart = computed(() => isAdmin.value && supOk.value && !feActionInFlight.value && !feStatus.value.running)
const canFeStop = computed(() => isAdmin.value && supOk.value && !feActionInFlight.value && feStatus.value.running)
const canFeRestart = computed(() => canFeStop.value)

const currentLines = computed(() => activeConsole.value === 'frontend' ? feLines.value : beLines.value)
const currentConnected = computed(() => activeConsole.value === 'frontend' ? feConnected.value : beConnected.value)
const filteredLines = computed(() => {
  if (!consoleFilter.value) return currentLines.value
  const f = consoleFilter.value.toLowerCase()
  return currentLines.value.filter(l => (l.line || '').toLowerCase().includes(f))
})

function switchConsole(which) {
  activeConsole.value = which
  consoleFilter.value = ''
  scrollConsoleBottom()
}
function scrollConsoleBottom() {
  if (!autoScroll.value) return
  nextTick(() => {
    if (consoleBodyEl.value) consoleBodyEl.value.scrollTop = consoleBodyEl.value.scrollHeight
  })
}
watch(() => currentLines.value.length, () => scrollConsoleBottom())

async function fetchHistoryOnce(which) {
  const path = which === 'frontend' ? '/api/v1/process/frontend/console?tail=300' : '/api/v1/process/console?tail=300'
  try {
    const r = await fetch(path, { credentials: 'include' })
    if (r.ok) {
      const data = await r.json()
      const target = which === 'frontend' ? feLines : beLines
      target.value = data.lines || []
    }
  } catch (e) {}
}

async function connectWS(which) {
  const wsInfoPath = which === 'frontend' ? '/api/v1/process/frontend/console/ws-info' : '/api/v1/process/console/ws-info'
  try {
    const info = await fetch(wsInfoPath, { credentials: 'include' }).then(r => r.json())
    if (!info.enabled) return
    const ws = new WebSocket(info.ws_url)
    ws.onopen = () => {
      if (which === 'frontend') feConnected.value = true
      else beConnected.value = true
    }
    ws.onmessage = (ev) => {
      try {
        const entry = JSON.parse(ev.data)
        if (entry.type === 'ping') return
        const target = which === 'frontend' ? feLines : beLines
        target.value.push(entry)
        if (target.value.length > MAX_LINES) target.value = target.value.slice(-MAX_LINES)
      } catch (e) {}
    }
    ws.onerror = () => {}
    ws.onclose = () => {
      if (which === 'frontend') {
        feConnected.value = false
        feReconnectTimer = setTimeout(() => connectWS('frontend'), 5000)
      } else {
        beConnected.value = false
        beReconnectTimer = setTimeout(() => connectWS('backend'), 5000)
      }
    }
    if (which === 'frontend') feWs = ws
    else beWs = ws
  } catch (e) {}
}

function reconnectCurrent() {
  if (activeConsole.value === 'frontend') {
    if (feWs) try { feWs.close() } catch (e) {}
    if (feReconnectTimer) clearTimeout(feReconnectTimer)
    connectWS('frontend')
  } else {
    if (beWs) try { beWs.close() } catch (e) {}
    if (beReconnectTimer) clearTimeout(beReconnectTimer)
    connectWS('backend')
  }
}
function clearCurrent() {
  if (activeConsole.value === 'frontend') feLines.value = []
  else beLines.value = []
}
function copyCurrent() {
  const text = filteredLines.value.map(l => `[${l.ts}] ${l.stream} | ${l.line}`).join('\n')
  navigator.clipboard.writeText(text).then(
    () => showActionMsg(`${filteredLines.value.length} 라인 복사됨`, 'success'),
    () => showActionMsg('클립보드 복사 실패', 'error')
  )
}
function openPopup() {
  // v95_p107 hotfix_005: 콘솔 전용 standalone 라우트 (사이드바/탑바 없이 풀스크린)
  const path = activeConsole.value === 'frontend'
    ? '/console-popup/frontend'
    : '/console-popup/backend'
  const name = activeConsole.value + '-console'
  // 도커 콘솔 창처럼 적당한 사이즈
  window.open(path, name, 'width=1000,height=640,scrollbars=no,resizable=yes,menubar=no,toolbar=no,location=no,status=no')
}

async function fetchStatus(silent = false) {
  try {
    const r = await fetch('/api/v1/process/status', { credentials: 'include' })
    if (!r.ok) throw new Error('status HTTP ' + r.status)
    status.value = await r.json()
    lastFetchTs.value = Date.now()
  } catch (e) {
    if (!silent) {
      status.value = { supervisor_running: false, running: false, frontend: { running: false } }
      lastFetchTs.value = Date.now()
    }
  }
}

function showActionMsg(msg, kind = 'info') {
  actionMsg.value = msg
  actionMsgKind.value = kind
  actionMsgTime.value = new Date().toLocaleTimeString('ko-KR')
}

async function callAction(method, url, body) {
  const r = await fetch(url, {
    method, credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : null,
  })
  return r.json()
}

async function onBeStart() {
  if (!confirm(`Backend를 [${selectedBeMode.value}] 모드로 시작하시겠습니까?`)) return
  beActionInFlight.value = true
  try {
    const data = await callAction('POST', '/api/v1/process/start', { mode: selectedBeMode.value })
    showActionMsg(data.message, data.ok ? 'success' : 'error')
    setTimeout(() => fetchStatus(true), 1500)
  } catch (e) { showActionMsg('Backend 시작 실패: ' + e.message, 'error') }
  finally { beActionInFlight.value = false }
}
async function onBeStop() {
  if (!confirm('Backend 프로세스를 중지하시겠습니까?')) return
  beActionInFlight.value = true
  try {
    const data = await callAction('POST', '/api/v1/process/stop')
    showActionMsg(data.message, data.ok ? 'success' : 'error')
    setTimeout(() => fetchStatus(true), 2000)
  } catch (e) { showActionMsg('Backend 중지 실패: ' + e.message, 'error') }
  finally { beActionInFlight.value = false }
}
async function onBeRestart() {
  if (!confirm(`Backend를 [${selectedBeMode.value}] 모드로 재시작하시겠습니까?`)) return
  beActionInFlight.value = true
  try {
    const data = await callAction('POST', '/api/v1/process/restart', { mode: selectedBeMode.value })
    showActionMsg(data.message, data.ok ? 'success' : 'error')
    setTimeout(() => fetchStatus(true), 3000)
  } catch (e) { showActionMsg('Backend 재시작 실패: ' + e.message, 'error') }
  finally { beActionInFlight.value = false }
}
async function onFeStart() {
  if (!confirm(`Frontend를 [${selectedFeMode.value}] 모드로 시작하시겠습니까?`)) return
  feActionInFlight.value = true
  try {
    const data = await callAction('POST', '/api/v1/process/frontend/start', { mode: selectedFeMode.value })
    showActionMsg(data.message, data.ok ? 'success' : 'error')
    setTimeout(() => fetchStatus(true), 2500)
  } catch (e) { showActionMsg('Frontend 시작 실패: ' + e.message, 'error') }
  finally { feActionInFlight.value = false }
}
async function onFeStop() {
  if (!confirm('Frontend 프로세스를 중지하시겠습니까?')) return
  feActionInFlight.value = true
  try {
    const data = await callAction('POST', '/api/v1/process/frontend/stop')
    showActionMsg(data.message, data.ok ? 'success' : 'error')
    setTimeout(() => fetchStatus(true), 2000)
  } catch (e) { showActionMsg('Frontend 중지 실패: ' + e.message, 'error') }
  finally { feActionInFlight.value = false }
}
async function onFeRestart() {
  if (!confirm(`Frontend를 [${selectedFeMode.value}] 모드로 재시작하시겠습니까?`)) return
  feActionInFlight.value = true
  try {
    const data = await callAction('POST', '/api/v1/process/frontend/restart', { mode: selectedFeMode.value })
    showActionMsg(data.message, data.ok ? 'success' : 'error')
    setTimeout(() => fetchStatus(true), 3000)
  } catch (e) { showActionMsg('Frontend 재시작 실패: ' + e.message, 'error') }
  finally { feActionInFlight.value = false }
}

onMounted(async () => {
  await fetchStatus()
  pollTimer = setInterval(() => fetchStatus(true), 5000)
  nowTimer = setInterval(() => { now.value = Date.now() }, 1000)
  await fetchHistoryOnce('frontend')
  await fetchHistoryOnce('backend')
  await connectWS('frontend')
  await connectWS('backend')
  scrollConsoleBottom()
})
onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (nowTimer) clearInterval(nowTimer)
  if (feWs) try { feWs.close() } catch (e) {}
  if (beWs) try { beWs.close() } catch (e) {}
  if (feReconnectTimer) clearTimeout(feReconnectTimer)
  if (beReconnectTimer) clearTimeout(beReconnectTimer)
})
</script>

<style scoped>
.admin-process { padding: 24px 28px; max-width: 1080px; }
.page-title { font-size: 1.05rem; font-weight: 600; color: var(--text-primary); margin-bottom: 4px; }
.page-desc { font-size: .8rem; color: var(--text-secondary); margin-bottom: 18px; line-height: 1.6; }

.card.setting-card {
  background: var(--bg-primary, #fff);
  border: 0.5px solid var(--border-light, rgba(0,0,0,.08));
  border-radius: 8px;
  margin-bottom: 14px;
  overflow: hidden;
}
.sc-header {
  display: flex; align-items: center; gap: 8px;
  padding: 11px 14px;
  font-size: .82rem; font-weight: 600;
  color: var(--text-primary);
  border-bottom: 0.5px solid var(--border-light);
  background: var(--bg-secondary, #f8fafc);
}

.supervisor-banner.sup-on { border-left: 3px solid #22c55e; }
.supervisor-banner.sup-off { border-left: 3px solid #e24b4a; background: rgba(226,75,74,.02); }
.supervisor-banner.sup-unknown { border-left: 3px solid #94a3b8; }
.badge-supervisor { display: inline-block; font-size: .68rem; font-weight: 600; padding: 1px 6px; border-radius: 3px; margin-left: 4px; }
.badge-supervisor.sup-on { background: rgba(34,197,94,.12); color: #16a34a; }
.badge-supervisor.sup-off { background: rgba(226,75,74,.12); color: #b91c1c; }
.badge-supervisor.sup-unknown { background: rgba(148,163,184,.16); color: #64748b; }
.supervisor-detail { padding: 8px 14px; font-size: .76rem; color: var(--text-secondary); }
.supervisor-detail code.mono { font-family: 'SF Mono', 'Consolas', monospace; font-size: .72rem; background: var(--bg-secondary); padding: 1px 5px; border-radius: 3px; border: 0.5px solid var(--border-light); }

.status-hero { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 18px 16px; flex-wrap: wrap; }
.status-light-wrap { display: flex; align-items: center; gap: 14px; flex: 1; min-width: 240px; }
.status-light { width: 32px; height: 32px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
.status-light-inner { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
.status-light.light-on { background: rgba(34,197,94,.12); }
.status-light.light-on .status-light-inner { background: #22c55e; box-shadow: 0 0 0 4px rgba(34,197,94,.2); animation: pulse-green 2s infinite; }
.status-light.light-off { background: rgba(226,75,74,.12); }
.status-light.light-off .status-light-inner { background: #e24b4a; }
.status-light.light-unknown { background: rgba(148,163,184,.16); }
.status-light.light-unknown .status-light-inner { background: #94a3b8; animation: pulse-gray 1.5s infinite; }
@keyframes pulse-green { 0%,100% { box-shadow: 0 0 0 4px rgba(34,197,94,.2); } 50% { box-shadow: 0 0 0 7px rgba(34,197,94,0); } }
@keyframes pulse-gray { 0%,100% { opacity: 1; } 50% { opacity: .4; } }

.status-text { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.status-label { font-size: .95rem; font-weight: 600; }
.status-label.light-on { color: #16a34a; }
.status-label.light-off { color: #b91c1c; }
.status-label.light-unknown { color: #64748b; }
.status-detail { font-size: .74rem; color: var(--text-secondary); }

.action-group { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.mode-select { font-size: .74rem; padding: 6px 28px 6px 10px; border: 0.5px solid var(--border-mid, rgba(0,0,0,.15)); border-radius: 6px; background: var(--bg-primary); color: var(--text-primary); cursor: pointer; font-family: var(--font); }
.mode-select:disabled { opacity: .5; cursor: not-allowed; }
.btn-action { display: inline-flex; align-items: center; gap: 5px; font-size: .76rem; font-weight: 500; padding: 7px 13px; border: 0.5px solid var(--border-mid); border-radius: 6px; background: var(--bg-primary); color: var(--text-primary); cursor: pointer; transition: all .12s; font-family: var(--font); }
.btn-action:hover:not(:disabled) { background: var(--bg-secondary); }
.btn-action:disabled { opacity: .35; cursor: not-allowed; }
.btn-start { color: #16a34a; border-color: rgba(34,197,94,.4); }
.btn-start:hover:not(:disabled) { background: rgba(34,197,94,.08); }
.btn-stop { color: #b91c1c; border-color: rgba(226,75,74,.4); }
.btn-stop:hover:not(:disabled) { background: rgba(226,75,74,.08); }
.btn-restart { color: #6366f1; border-color: rgba(99,102,241,.4); }
.btn-restart:hover:not(:disabled) { background: rgba(99,102,241,.08); }

.info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1px; background: var(--border-light); border-top: 0.5px solid var(--border-light); }
.info-cell { background: var(--bg-primary); padding: 9px 13px; }
.info-label { font-size: .66rem; color: var(--text-tertiary); text-transform: uppercase; letter-spacing: .04em; margin-bottom: 2px; }
.info-value { font-size: .8rem; color: var(--text-primary); font-weight: 500; }
.info-value.mono { font-family: 'SF Mono', 'Consolas', monospace; font-size: .74rem; word-break: break-all; }

.mode-badge { display: inline-block; font-size: .66rem; font-weight: 600; padding: 2px 7px; border-radius: 4px; border: 0.5px solid; }
.mode-badge.mode-safe { background: rgba(34,197,94,.08); color: #16a34a; border-color: rgba(34,197,94,.3); }
.mode-badge.mode-multiprocess { background: rgba(99,102,241,.08); color: #4f46e5; border-color: rgba(99,102,241,.3); }
.mode-badge.mode-thread { background: rgba(245,158,11,.08); color: #b45309; border-color: rgba(245,158,11,.3); }
.mode-badge.mode-fe-dev { background: rgba(99,102,241,.08); color: #4f46e5; border-color: rgba(99,102,241,.3); }
.mode-badge.mode-fe-release { background: rgba(34,197,94,.08); color: #16a34a; border-color: rgba(34,197,94,.3); }
.mode-badge.mode-fe-auto { background: rgba(168,85,247,.08); color: #7e22ce; border-color: rgba(168,85,247,.3); }

.tag-ok { color: #16a34a; }
.tag-warn { color: #b45309; }

.action-msg { display: flex; gap: 12px; padding: 12px 16px; border-left: 2px solid; font-size: .82rem; }
.action-msg.msg-info { border-left-color: #6366f1; background: rgba(99,102,241,.04); }
.action-msg.msg-success { border-left-color: #22c55e; background: rgba(34,197,94,.04); }
.action-msg.msg-error { border-left-color: #e24b4a; background: rgba(226,75,74,.04); color: #b91c1c; }
.action-msg-time { font-family: 'SF Mono', 'Consolas', monospace; font-size: .72rem; color: var(--text-tertiary); flex-shrink: 0; }
.action-msg-body { flex: 1; }

.console-card { overflow: hidden; }
.console-header { display: flex; align-items: center; gap: 10px; }
.console-tabs { display: flex; align-items: center; gap: 4px; margin-left: auto; flex: 1; }
.tab { display: inline-flex; align-items: center; gap: 6px; font-size: .74rem; font-weight: 500; padding: 5px 11px; border-radius: 5px; border: 0.5px solid transparent; background: transparent; color: var(--text-secondary); cursor: pointer; transition: all .12s; }
.tab:hover { background: var(--bg-primary); color: var(--text-primary); }
.tab.active { background: var(--bg-primary); color: var(--text-primary); border-color: var(--border-mid, rgba(0,0,0,.15)); }
.tab-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.tab-dot.on { background: #22c55e; box-shadow: 0 0 0 2px rgba(34,197,94,.18); }
.tab-dot.off { background: #cbd5e1; }
.tab-count { font-family: 'SF Mono', 'Consolas', monospace; font-size: .65rem; padding: 1px 5px; border-radius: 3px; background: var(--bg-secondary); color: var(--text-tertiary); }
.popup-btn { display: inline-flex; align-items: center; gap: 4px; font-size: .72rem; padding: 4px 9px; border: 0.5px solid var(--border-mid); border-radius: 5px; background: var(--bg-primary); color: var(--text-secondary); cursor: pointer; transition: all .12s; }
.popup-btn:hover { color: var(--text-primary); background: var(--bg-secondary); }

.console-toolbar { display: flex; align-items: center; gap: 8px; padding: 8px 14px; background: var(--bg-secondary, #f8fafc); border-bottom: 0.5px solid var(--border-light); font-size: .74rem; flex-wrap: wrap; }
.filter-input { background: var(--bg-primary); color: var(--text-primary); border: 0.5px solid var(--border-mid); border-radius: 4px; padding: 4px 8px; font-family: inherit; font-size: .73rem; width: 240px; }
.lbl { font-size: .72rem; color: var(--text-secondary); display: flex; align-items: center; gap: 4px; }
.spacer { flex: 1; }
.conn-state { font-size: .7rem; font-family: 'SF Mono', 'Consolas', monospace; }
.conn-state.ok { color: #16a34a; }
.conn-state.off { color: #b45309; }
.mini-btn { font-size: .7rem; padding: 3px 8px; border: 0.5px solid var(--border-mid); border-radius: 4px; background: var(--bg-primary); color: var(--text-primary); cursor: pointer; }
.mini-btn:hover { background: var(--bg-secondary); }

.console-body { background: #0e1116; color: #e6edf3; font-family: 'SF Mono', 'Consolas', 'Menlo', monospace; font-size: .74rem; line-height: 1.5; height: 360px; overflow-y: auto; padding: 10px 14px; }
.line { display: flex; gap: 8px; padding: 1px 0; white-space: pre-wrap; word-break: break-all; }
.line.stream-stderr { color: #f85149; }
.ts { color: #8b949e; flex-shrink: 0; font-size: .68rem; }
.stream-tag { font-size: .63rem; color: #8b949e; flex-shrink: 0; min-width: 42px; text-transform: uppercase; }
.line.stream-stderr .stream-tag { color: #f85149; }
.text { flex: 1; }
.empty { color: #8b949e; padding: 20px; text-align: center; font-style: italic; }

.console-footer { padding: 6px 14px; background: var(--bg-secondary, #f8fafc); border-top: 0.5px solid var(--border-light); font-size: .68rem; color: var(--text-tertiary); font-family: 'SF Mono', 'Consolas', monospace; }
</style>
