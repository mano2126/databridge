<template>
  <div class="page admin-process">
    <div class="page-title">백엔드 프로세스</div>
    <div class="page-desc">DataBridge 백엔드 프로세스의 상태를 확인하고 시작·중지·재시작합니다</div>

    <!-- ════════════════════════════════════════════════════════════ -->
    <!-- v95_p104 (2026-05-09 본부장님): 백엔드 프로세스 관리            -->
    <!-- 본부장님 비전: 엔터프라이즈급 — 시작/중지/재시작 + 상태 표시   -->
    <!-- ════════════════════════════════════════════════════════════ -->

    <!-- ── 상태 카드 ─────────────────────────────────────── -->
    <div class="card setting-card">
      <div class="sc-header">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px">
          <circle cx="8" cy="8" r="6"/>
          <circle cx="8" cy="8" r="2.5" fill="currentColor"/>
        </svg>
        프로세스 상태
        <span style="margin-left:auto;font-size:.7rem;color:var(--text-tertiary)">
          {{ statusUpdatedAgo }}
        </span>
      </div>

      <!-- 상태 라이트 + 핵심 정보 -->
      <div class="status-hero">
        <div class="status-light-wrap">
          <span class="status-light" :class="statusLightClass">
            <span class="status-light-inner"></span>
          </span>
          <div class="status-text">
            <div class="status-label" :class="statusLightClass">{{ statusLabel }}</div>
            <div class="status-detail" v-if="status">
              <span v-if="status.running">PID {{ status.pid }} · 모드 {{ modeKor }} · 가동 {{ uptimeText }}</span>
              <span v-else style="color:#dc2626">백엔드 응답 없음 — launchd / systemd / 터미널에서 시작 필요</span>
            </div>
          </div>
        </div>

        <!-- 액션 버튼 그룹 -->
        <div class="action-group">
          <!-- 모드 셀렉트 (시작 전 선택) -->
          <select v-model="selectedMode" class="mode-select" :disabled="actionInFlight">
            <option value="safe">SAFE — 안전 (4,800 rows/s)</option>
            <option value="multiprocess">MULTIPROCESS — 빠름 (9,300 rows/s)</option>
            <option value="thread">THREAD — 진단용</option>
          </select>

          <!-- 재시작 -->
          <button class="btn-action btn-restart"
                  @click="onRestart"
                  :disabled="!canRestart"
                  :title="restartTooltip">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" style="width:13px;height:13px">
              <path d="M3 8a5 5 0 1 0 1.5-3.5L3 6M3 3v3h3" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            재시작
          </button>

          <!-- 중지 -->
          <button class="btn-action btn-stop"
                  @click="onStop"
                  :disabled="!canStop"
                  :title="stopTooltip">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" style="width:13px;height:13px">
              <rect x="4" y="4" width="8" height="8" rx="1"/>
            </svg>
            중지
          </button>

          <!-- 시작 (백엔드 죽었을 때만 활성) -->
          <button class="btn-action btn-start"
                  @click="onStart"
                  :disabled="!canStart"
                  :title="startTooltip">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" style="width:13px;height:13px">
              <path d="M5 3l8 5-8 5z" stroke-linejoin="round"/>
            </svg>
            시작
          </button>
        </div>
      </div>

      <!-- 정보 영역 -->
      <div class="info-grid" v-if="status">
        <div class="info-cell">
          <div class="info-label">PID</div>
          <div class="info-value mono">{{ status.pid || '—' }}</div>
        </div>
        <div class="info-cell">
          <div class="info-label">모드</div>
          <div class="info-value">
            <span class="mode-badge" :class="'mode-' + status.mode">{{ modeKor }}</span>
          </div>
        </div>
        <div class="info-cell">
          <div class="info-label">가동 시간</div>
          <div class="info-value mono">{{ uptimeText }}</div>
        </div>
        <div class="info-cell">
          <div class="info-label">시작 시각</div>
          <div class="info-value mono">{{ startedAtText }}</div>
        </div>
        <div class="info-cell">
          <div class="info-label">플랫폼</div>
          <div class="info-value">{{ status.platform || '—' }}</div>
        </div>
        <div class="info-cell">
          <div class="info-label">Launcher</div>
          <div class="info-value mono" :title="status.launcher_script">
            <span :class="status.launcher_exists ? 'tag-ok' : 'tag-warn'">
              {{ status.launcher_exists ? '✓ 존재' : '⚠ 없음' }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 동작 메시지 ─────────────────────────────────────── -->
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

    <!-- ── 안내 ─────────────────────────────────────── -->
    <div class="card setting-card">
      <div class="sc-header">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px">
          <path d="M8 2L2 13h12z"/>
          <line x1="8" y1="6" x2="8" y2="9"/>
          <circle cx="8" cy="11" r=".6" fill="currentColor"/>
        </svg>
        프로세스 관리 안내
      </div>
      <div class="guide-body">
        <div class="guide-row">
          <span class="guide-key">중지/재시작 시</span>
          <span class="guide-val">
            백엔드 프로세스가 종료됩니다. UI 가 일시적으로 응답하지 않을 수 있습니다.
            launchd (macOS) / systemd (Linux) KeepAlive 가 설정되어 있으면 자동 재시작됩니다.
          </span>
        </div>
        <div class="guide-row">
          <span class="guide-key">자동 재시작 미설정 시</span>
          <span class="guide-val">
            중지 후 터미널에서 <code class="mono">bash run_backend.sh</code> 직접 실행 필요.
            모드 인자 가능: <code class="mono">bash run_backend.sh safe</code>
          </span>
        </div>
        <div class="guide-row">
          <span class="guide-key">모드 변경 시</span>
          <span class="guide-val">
            셀렉트에서 모드 선택 후 재시작. 환경 변수 (DATABRIDGE_CHUNK_EXPERIMENT, DATABRIDGE_CHUNK_MODE) 가 설정됩니다.
          </span>
        </div>
        <div class="guide-row">
          <span class="guide-key">권한</span>
          <span class="guide-val">시작/중지/재시작은 관리자(admin) 만 가능. 상태 조회는 모든 사용자.</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/store/authStore.js'

const authStore = useAuthStore()
const status = ref(null)
const selectedMode = ref('safe')
const actionInFlight = ref(false)
const actionMsg = ref('')
const actionMsgKind = ref('info')   // info | success | error
const actionMsgTime = ref('')
const lastFetchTs = ref(0)

let pollTimer = null
let nowTimer = null
const now = ref(Date.now())

// ─── 상태 라이트 클래스 ────────────────────────
const statusLightClass = computed(() => {
  if (!status.value) return 'light-unknown'
  if (!status.value.running) return 'light-off'
  return 'light-on'
})

const statusLabel = computed(() => {
  if (!status.value) return '확인 중'
  if (!status.value.running) return '중지됨'
  return '실행 중'
})

const modeKor = computed(() => {
  const m = status.value?.mode
  return ({
    safe: 'SAFE',
    multiprocess: 'MULTIPROCESS',
    thread: 'THREAD',
  })[m] || (m || '—')
})

const uptimeText = computed(() => {
  const s = status.value?.uptime_seconds
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
})

const startedAtText = computed(() => {
  const t = status.value?.started_at
  if (!t) return '—'
  const d = new Date(t * 1000)
  return d.toLocaleString('ko-KR', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
})

const statusUpdatedAgo = computed(() => {
  if (!lastFetchTs.value) return ''
  const sec = Math.floor((now.value - lastFetchTs.value) / 1000)
  if (sec < 5) return '방금 업데이트'
  if (sec < 60) return `${sec}초 전 업데이트`
  return `${Math.floor(sec / 60)}분 전 업데이트`
})

// ─── 권한 + 활성화 ──────────────────────────────
const isAdmin = computed(() => {
  if (!authStore?.hasRole) return true   // RBAC 비활성 환경
  return authStore.hasRole('admin')
})

const canStart = computed(() =>
  isAdmin.value && !actionInFlight.value && status.value && !status.value.running
)
const canStop = computed(() =>
  isAdmin.value && !actionInFlight.value && status.value && status.value.running
)
const canRestart = computed(() => canStop.value)

const startTooltip = computed(() => {
  if (!isAdmin.value) return '관리자 권한 필요'
  if (status.value?.running) return '이미 실행 중입니다'
  return `${selectedMode.value} 모드로 시작`
})
const stopTooltip = computed(() => {
  if (!isAdmin.value) return '관리자 권한 필요'
  if (!status.value?.running) return '이미 중지됨'
  return '백엔드 프로세스 중지'
})
const restartTooltip = computed(() => {
  if (!isAdmin.value) return '관리자 권한 필요'
  if (!status.value?.running) return '실행 중일 때만 재시작 가능'
  return `${selectedMode.value} 모드로 재시작`
})

// ─── API 호출 ──────────────────────────────────
async function fetchStatus(silent = false) {
  try {
    const r = await fetch('/api/v1/process/status', { credentials: 'include' })
    if (!r.ok) throw new Error('status HTTP ' + r.status)
    status.value = await r.json()
    lastFetchTs.value = Date.now()
  } catch (e) {
    if (!silent) {
      // 응답 못 받으면 → 백엔드 죽은 거 (가장 흔한 케이스)
      status.value = {
        running: false,
        pid: null,
        mode: '',
        uptime_seconds: null,
        started_at: null,
        launcher_script: '',
        launcher_exists: false,
        platform: '',
        self_pid: 0,
      }
      lastFetchTs.value = Date.now()
    }
  }
}

function showActionMsg(msg, kind = 'info') {
  actionMsg.value = msg
  actionMsgKind.value = kind
  actionMsgTime.value = new Date().toLocaleTimeString('ko-KR')
}

async function onStart() {
  if (!confirm(`백엔드를 [${selectedMode.value}] 모드로 시작하시겠습니까?`)) return
  actionInFlight.value = true
  try {
    const r = await fetch('/api/v1/process/start', {
      method: 'POST', credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: selectedMode.value }),
    })
    const data = await r.json()
    if (data.ok) {
      showActionMsg(data.message, 'success')
      await new Promise(res => setTimeout(res, 1500))
      await fetchStatus()
    } else {
      showActionMsg(data.message || '시작 실패', 'error')
    }
  } catch (e) {
    showActionMsg('시작 요청 실패: ' + e.message, 'error')
  } finally {
    actionInFlight.value = false
  }
}

async function onStop() {
  if (!confirm('백엔드 프로세스를 중지하시겠습니까?\n중지 후 UI 가 일시적으로 응답하지 않을 수 있습니다.')) return
  actionInFlight.value = true
  showActionMsg('중지 신호 전송 중...', 'info')
  try {
    const r = await fetch('/api/v1/process/stop', {
      method: 'POST', credentials: 'include',
    })
    const data = await r.json()
    showActionMsg(data.message, 'success')
    
    // 1초 후부터 상태 폴링 — 응답 없어지면 "중지됨" 으로 전환
    setTimeout(async () => {
      await fetchStatus(true)   // silent: 에러 시 running=false 표시
    }, 2000)
  } catch (e) {
    // 정상 — 백엔드가 죽으면서 응답 못 보낼 수도 있음
    showActionMsg('중지됨 (응답 없음 = 정상 종료)', 'success')
    setTimeout(async () => {
      await fetchStatus(true)
    }, 2000)
  } finally {
    actionInFlight.value = false
  }
}

async function onRestart() {
  if (!confirm(`백엔드를 [${selectedMode.value}] 모드로 재시작하시겠습니까?\n자동 재시작 (launchd/systemd) 미설정 환경에서는 수동 재실행 필요.`)) return
  actionInFlight.value = true
  showActionMsg('재시작 신호 전송 중...', 'info')
  try {
    const r = await fetch('/api/v1/process/restart', {
      method: 'POST', credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: selectedMode.value }),
    })
    const data = await r.json()
    showActionMsg(data.message, 'success')
    setTimeout(async () => {
      await fetchStatus(true)
    }, 3000)
  } catch (e) {
    showActionMsg('재시작 신호 전송됨 (응답 없음 = 정상)', 'success')
    setTimeout(async () => {
      await fetchStatus(true)
    }, 3000)
  } finally {
    actionInFlight.value = false
  }
}

// ─── 라이프사이클 ──────────────────────────────
onMounted(() => {
  fetchStatus()
  // 5초마다 상태 갱신
  pollTimer = setInterval(() => fetchStatus(true), 5000)
  // "n초 전 업데이트" 라벨 갱신용
  nowTimer = setInterval(() => { now.value = Date.now() }, 1000)
})
onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (nowTimer) clearInterval(nowTimer)
})
</script>

<style scoped>
.admin-process {
  padding: 24px 28px;
  max-width: 1080px;
}
.page-title { font-size: 1.05rem; font-weight: 600; color: var(--text-primary); margin-bottom: 4px; }
.page-desc { font-size: .8rem; color: var(--text-secondary); margin-bottom: 18px; }

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

/* ── 상태 hero 영역 ───────────────────────────── */
.status-hero {
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; padding: 22px 18px;
  flex-wrap: wrap;
}
.status-light-wrap {
  display: flex; align-items: center; gap: 14px;
  flex: 1; min-width: 240px;
}
.status-light {
  width: 36px; height: 36px;
  border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.status-light-inner {
  width: 14px; height: 14px;
  border-radius: 50%;
  display: inline-block;
}
.status-light.light-on        { background: rgba(34,197,94,.12); }
.status-light.light-on .status-light-inner {
  background: #22c55e;
  box-shadow: 0 0 0 4px rgba(34,197,94,.2);
  animation: pulse-green 2s infinite;
}
.status-light.light-off       { background: rgba(226,75,74,.12); }
.status-light.light-off .status-light-inner {
  background: #e24b4a;
}
.status-light.light-unknown   { background: rgba(148,163,184,.16); }
.status-light.light-unknown .status-light-inner {
  background: #94a3b8;
  animation: pulse-gray 1.5s infinite;
}
@keyframes pulse-green {
  0%,100% { box-shadow: 0 0 0 4px rgba(34,197,94,.2); }
  50%     { box-shadow: 0 0 0 7px rgba(34,197,94,0); }
}
@keyframes pulse-gray {
  0%,100% { opacity: 1; }
  50%     { opacity: .4; }
}

.status-text { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.status-label {
  font-size: 1.0rem; font-weight: 600;
}
.status-label.light-on        { color: #16a34a; }
.status-label.light-off       { color: #b91c1c; }
.status-label.light-unknown   { color: #64748b; }
.status-detail {
  font-size: .76rem; color: var(--text-secondary);
}

/* ── 액션 버튼 그룹 ───────────────────────────── */
.action-group {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.mode-select {
  font-size: .76rem;
  padding: 6px 28px 6px 10px;
  border: 0.5px solid var(--border-mid, rgba(0,0,0,.15));
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-primary);
  cursor: pointer;
  font-family: var(--font);
}
.mode-select:disabled { opacity: .5; cursor: not-allowed; }

.btn-action {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: .78rem; font-weight: 500;
  padding: 7px 14px;
  border: 0.5px solid var(--border-mid);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-primary);
  cursor: pointer;
  transition: all .12s;
  font-family: var(--font);
}
.btn-action:hover:not(:disabled) {
  background: var(--bg-secondary);
}
.btn-action:disabled { opacity: .35; cursor: not-allowed; }
.btn-start  { color: #16a34a; border-color: rgba(34,197,94,.4); }
.btn-start:hover:not(:disabled)  { background: rgba(34,197,94,.08); }
.btn-stop   { color: #b91c1c; border-color: rgba(226,75,74,.4); }
.btn-stop:hover:not(:disabled)   { background: rgba(226,75,74,.08); }
.btn-restart { color: #6366f1; border-color: rgba(99,102,241,.4); }
.btn-restart:hover:not(:disabled){ background: rgba(99,102,241,.08); }

/* ── 정보 그리드 ─────────────────────────────── */
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 1px;
  background: var(--border-light);
  border-top: 0.5px solid var(--border-light);
}
.info-cell {
  background: var(--bg-primary);
  padding: 10px 14px;
}
.info-label {
  font-size: .68rem;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: .04em;
  margin-bottom: 2px;
}
.info-value {
  font-size: .82rem;
  color: var(--text-primary);
  font-weight: 500;
}
.info-value.mono {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: .76rem;
  word-break: break-all;
}

.mode-badge {
  display: inline-block;
  font-size: .68rem; font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  border: 0.5px solid;
}
.mode-badge.mode-safe {
  background: rgba(34,197,94,.08);
  color: #16a34a;
  border-color: rgba(34,197,94,.3);
}
.mode-badge.mode-multiprocess {
  background: rgba(99,102,241,.08);
  color: #4f46e5;
  border-color: rgba(99,102,241,.3);
}
.mode-badge.mode-thread {
  background: rgba(245,158,11,.08);
  color: #b45309;
  border-color: rgba(245,158,11,.3);
}

.tag-ok   { color: #16a34a; }
.tag-warn { color: #b45309; }

/* ── 동작 메시지 ─────────────────────────────── */
.action-msg {
  display: flex; gap: 12px;
  padding: 12px 16px;
  border-left: 2px solid;
  font-size: .82rem;
}
.action-msg.msg-info    { border-left-color: #6366f1; background: rgba(99,102,241,.04); }
.action-msg.msg-success { border-left-color: #22c55e; background: rgba(34,197,94,.04); }
.action-msg.msg-error   { border-left-color: #e24b4a; background: rgba(226,75,74,.04); color: #b91c1c; }
.action-msg-time {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: .72rem;
  color: var(--text-tertiary);
  flex-shrink: 0;
}
.action-msg-body { flex: 1; }

/* ── 안내 ─────────────────────────────────── */
.guide-body {
  padding: 12px 16px;
  display: flex; flex-direction: column; gap: 10px;
}
.guide-row {
  display: flex; gap: 14px; align-items: flex-start;
  font-size: .76rem;
  padding-bottom: 8px;
  border-bottom: 0.5px dashed var(--border-light);
}
.guide-row:last-child { border-bottom: none; padding-bottom: 0; }
.guide-key {
  width: 130px; flex-shrink: 0;
  font-weight: 600;
  color: var(--text-primary);
}
.guide-val {
  flex: 1; min-width: 0;
  color: var(--text-secondary);
  line-height: 1.5;
}
code.mono {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: .72rem;
  background: var(--bg-secondary);
  padding: 1px 5px;
  border-radius: 3px;
  border: 0.5px solid var(--border-light);
}
</style>
