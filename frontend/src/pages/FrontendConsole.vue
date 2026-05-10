<template>
  <div class="console-page" :data-theme="'dark'">
    <div class="toolbar">
      <div class="title">
        <span class="dot" :class="{ on: connected }"></span>
        Frontend 콘솔
        <span class="badge fe-badge">{{ engine }}</span>
        <span class="conn-state">{{ connState }}</span>
      </div>
      <div class="ctrls">
        <input v-model="filter" placeholder="필터 (라인 일부 일치)" class="filter-input" />
        <label class="lbl"><input type="checkbox" v-model="autoScroll" /> 자동 스크롤</label>
        <button class="btn" @click="copyAll">복사</button>
        <button class="btn" @click="saveAll">저장</button>
        <button class="btn" @click="clearAll">지우기</button>
        <button class="btn" @click="reconnect">재연결</button>
      </div>
    </div>
    <div class="console-body" ref="bodyEl">
      <div v-for="(l, idx) in filteredLines" :key="idx"
           class="line" :class="'stream-' + l.stream">
        <span class="ts">{{ l.ts }}</span>
        <span class="stream-tag">{{ l.stream }}</span>
        <span class="text">{{ l.line }}</span>
      </div>
      <div v-if="!filteredLines.length" class="empty">
        {{ connected ? '아직 출력 없음...' : 'Supervisor WebSocket 연결 대기 중' }}
      </div>
    </div>
    <div class="footer">
      <span>{{ filteredLines.length }} / {{ lines.length }} lines</span>
      <span>port 8765 · /supervisor/frontend/console/ws</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'

const engine = 'frontend'
const lines = ref([])
const filter = ref('')
const autoScroll = ref(true)
const connected = ref(false)
const connState = ref('연결 중...')
const bodyEl = ref(null)

let ws = null
let reconnectTimer = null
const MAX_LINES = 5000

const filteredLines = computed(() => {
  if (!filter.value) return lines.value
  const f = filter.value.toLowerCase()
  return lines.value.filter(l => (l.line || '').toLowerCase().includes(f))
})

async function fetchHistory() {
  try {
    const r = await fetch('/api/v1/process/frontend/console?tail=300', { credentials: 'include' })
    if (r.ok) {
      const data = await r.json()
      lines.value = data.lines || []
      scrollBottom()
    }
  } catch (e) {}
}

async function connectWS() {
  try {
    const info = await fetch('/api/v1/process/frontend/console/ws-info', { credentials: 'include' }).then(r => r.json())
    if (!info.enabled) {
      connState.value = 'WS 비활성'
      return
    }
    ws = new WebSocket(info.ws_url)
    connState.value = '연결 중...'
    ws.onopen = () => {
      connected.value = true
      connState.value = '연결됨'
    }
    ws.onmessage = (ev) => {
      try {
        const entry = JSON.parse(ev.data)
        if (entry.type === 'ping') return
        lines.value.push(entry)
        if (lines.value.length > MAX_LINES) {
          lines.value = lines.value.slice(-MAX_LINES)
        }
        scrollBottom()
      } catch (e) {}
    }
    ws.onerror = () => { connState.value = '오류 — 재연결 대기' }
    ws.onclose = () => {
      connected.value = false
      connState.value = '연결 끊김 — 5초 후 재연결'
      reconnectTimer = setTimeout(connectWS, 5000)
    }
  } catch (e) {
    connState.value = '연결 실패: ' + e.message
    reconnectTimer = setTimeout(connectWS, 5000)
  }
}

function scrollBottom() {
  if (!autoScroll.value) return
  nextTick(() => {
    if (bodyEl.value) bodyEl.value.scrollTop = bodyEl.value.scrollHeight
  })
}

function reconnect() {
  if (ws) try { ws.close() } catch (e) {}
  if (reconnectTimer) clearTimeout(reconnectTimer)
  connectWS()
}
function clearAll() { lines.value = [] }
function copyAll() {
  const text = filteredLines.value.map(l => `[${l.ts}] ${l.stream} | ${l.line}`).join('\n')
  navigator.clipboard.writeText(text).then(
    () => alert(`${filteredLines.value.length} 라인 복사됨`),
    () => alert('클립보드 복사 실패')
  )
}
function saveAll() {
  const text = filteredLines.value.map(l => `[${l.ts}] ${l.stream} | ${l.line}`).join('\n')
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `frontend-console-${new Date().toISOString().slice(0,19).replace(/[:T]/g,'-')}.txt`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(async () => {
  await fetchHistory()
  await connectWS()
})
onUnmounted(() => {
  if (ws) try { ws.close() } catch (e) {}
  if (reconnectTimer) clearTimeout(reconnectTimer)
})
</script>

<style scoped>
.console-page {
  display: flex; flex-direction: column;
  height: 100vh; background: #0e1116; color: #e6edf3;
  font-family: 'SF Mono', 'Consolas', 'Menlo', monospace;
}
.toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 14px; background: #161b22; border-bottom: 1px solid #30363d;
  font-size: .8rem; gap: 12px; flex-wrap: wrap;
}
.title { display: flex; align-items: center; gap: 8px; font-weight: 600; }
.dot {
  width: 9px; height: 9px; border-radius: 50%;
  background: #94a3b8; box-shadow: 0 0 0 3px rgba(148,163,184,.2);
}
.dot.on { background: #22c55e; box-shadow: 0 0 0 3px rgba(34,197,94,.25); animation: pulse 2s infinite; }
@keyframes pulse {
  0%,100% { box-shadow: 0 0 0 3px rgba(34,197,94,.25); }
  50%     { box-shadow: 0 0 0 6px rgba(34,197,94,0); }
}
.badge {
  font-size: .65rem; padding: 2px 6px; border-radius: 3px;
  color: #fff; font-weight: 500;
}
.fe-badge { background: #6366f1; }
.conn-state { font-size: .7rem; color: #8b949e; font-weight: 400; }

.ctrls { display: flex; align-items: center; gap: 6px; }
.filter-input {
  background: #0d1117; border: 1px solid #30363d; border-radius: 4px;
  padding: 4px 8px; color: #e6edf3; font-family: inherit; font-size: .75rem;
  width: 200px;
}
.lbl { font-size: .72rem; color: #8b949e; display: flex; align-items: center; gap: 4px; }
.btn {
  background: #21262d; border: 1px solid #30363d; border-radius: 4px;
  padding: 4px 10px; color: #e6edf3; font-size: .72rem; cursor: pointer;
}
.btn:hover { background: #30363d; }

.console-body {
  flex: 1; overflow-y: auto; padding: 10px 14px;
  font-size: .76rem; line-height: 1.45;
}
.line { display: flex; gap: 8px; padding: 1px 0; white-space: pre-wrap; word-break: break-all; }
.line.stream-stderr { color: #f85149; }
.ts { color: #8b949e; flex-shrink: 0; font-size: .7rem; }
.stream-tag {
  font-size: .65rem; color: #8b949e; flex-shrink: 0; min-width: 42px;
  text-transform: uppercase;
}
.line.stream-stderr .stream-tag { color: #f85149; }
.text { flex: 1; }
.empty { color: #8b949e; padding: 20px; text-align: center; font-style: italic; }

.footer {
  padding: 6px 14px; background: #161b22; border-top: 1px solid #30363d;
  font-size: .7rem; color: #8b949e;
  display: flex; justify-content: space-between;
}
</style>
