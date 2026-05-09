<template>
  <div class="monitor-page">

    <!-- 헤더 -->
    <div class="mon-header">
      <div>
        <div class="page-title">실시간 모니터</div>
        <div class="page-desc">실행 중인 마이그레이션 Job의 진행 상황을 실시간으로 확인합니다</div>
      </div>
      <div class="header-actions">
        <div class="ws-status" :class="wsConnected ? 'ws-ok' : 'ws-off'">
          <span class="ws-dot"></span>
          <span>{{ wsConnected ? 'WebSocket 연결됨' : '폴링 모드' }}</span>
        </div>
        <button class="act-btn icon-only" @click="manualRefresh" title="즉시 새로고침">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.6"
               style="width:12px;height:12px" :class="{spinning: refreshing}">
            <path d="M12 7A5 5 0 1 1 7 2"/><polyline points="8,2 12,2 12,5.5"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- KPI -->
    <div class="kpi-grid" style="margin-bottom:12px">
      <div class="kpi-card">
        <div class="kpi-label">실행 중</div>
        <div class="kpi-value" :class="running.length > 0 ? 'ok' : ''">{{ running.length }}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">처리 속도 (rows/s)</div>
        <div class="kpi-value info">{{ totalSpeed.toLocaleString() }}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">누적 처리 rows</div>
        <div class="kpi-value">{{ fmtRows(cumulativeRows) }}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">오류 건수</div>
        <div class="kpi-value" :class="totalErrors > 0 ? 'err' : ''">{{ totalErrors }}</div>
      </div>
    </div>

    <!-- 실행 중 Job 패널 -->
    <div class="card" style="margin-bottom:12px;padding:0;overflow:hidden">
      <div class="card-header">
        <span>실행 중인 Job</span>
        <div style="display:flex;align-items:center;gap:8px">
          <span class="refresh-dot" :class="{active: wsConnected || autoRefresh}"></span>
          <span style="font-size:11px;color:var(--text-tertiary)">
            {{ wsConnected ? 'WebSocket 실시간' : '2초 폴링' }}
          </span>
          <div class="toggle sm" :class="{on: autoRefresh}" @click="autoRefresh=!autoRefresh"></div>
          <button class="act-btn icon-only" @click="clearLogs" title="로그 초기화">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px">
              <polyline points="2,3.5 12,3.5"/>
              <path d="M5,3.5 V2 H9 V3.5"/>
              <path d="M3.5,3.5 L4.5,12 H9.5 L10.5,3.5"/>
            </svg>
          </button>
        </div>
      </div>

      <div v-if="!running.length" class="empty-state" style="padding:28px">
        <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.2"
             style="width:32px;height:32px;opacity:.3">
          <circle cx="24" cy="24" r="20"/>
          <polyline points="16,24 22,30 32,18"/>
        </svg>
        <p>현재 실행 중인 Job이 없습니다</p>
      </div>

      <div v-for="j in running" :key="j.id" class="mon-row">
        <div class="db-icon" :style="{background:m(j.src_db)?.bg, color:m(j.src_db)?.color}">
          {{ m(j.src_db)?.label }}
        </div>
        <div class="mon-info">
          <div class="item-name">{{ j.name }}</div>
          <div class="item-desc">{{ j.src_database||j.src_db }} → {{ j.tgt_database||j.tgt_db }}</div>
          <div style="margin-top:4px;display:flex;align-items:center;gap:6px">
            <span class="pill" :class="pillCls(j.status)">{{ statusLbl(j.status) }}</span>
            <span v-if="j.table_total > 0" style="font-size:10.5px;color:var(--text-tertiary)">
              테이블 {{ j.table_done }}/{{ j.table_total }}
            </span>
          </div>
        </div>
        <div class="mon-prog">
          <div v-if="j.current_table" class="cur-tbl-row">
            <span class="cur-tbl-label">현재:</span>
            <span class="cur-tbl-name">{{ j.current_table }}</span>
            <span v-if="j.current_table_rows_total > 0" class="cur-tbl-cnt">
              {{ (j.current_table_rows_done||0).toLocaleString() }}
              / {{ (j.current_table_rows_total||0).toLocaleString() }} rows
            </span>
          </div>
          <div class="prog-meta">
            <span class="prog-pct">{{ (j.progress||0).toFixed(1) }}%</span>
            <span>{{ (j.speed||0).toLocaleString() }} rows/s</span>
            <span v-if="j.rows_error > 0" style="color:var(--text-danger)">오류 {{ j.rows_error }}건</span>
          </div>
          <div class="progress-wrap">
            <div class="progress-fill" :class="j.status==='paused'?'warn':'blue'"
                 :style="{width:(j.progress||0)+'%'}"></div>
          </div>
          <div class="rows-meta">
            처리: <b>{{ (j.rows_processed||0).toLocaleString() }}</b> rows
            / 전체: {{ (j.rows_total||0).toLocaleString() }} rows
          </div>
        </div>
        <div class="mon-acts">
          <button v-if="j.status==='running'" class="act-btn warn" @click="doPause(j.id)">일시정지</button>
          <button v-if="j.status==='paused'"  class="act-btn ok"   @click="doResume(j.id)">재개</button>
          <button v-if="['running','paused'].includes(j.status)"
                  class="act-btn del" @click="doStop(j.id)">중단</button>
          <button class="act-btn" @click="focusJob(j.id)" title="로그 보기">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px">
              <circle cx="6" cy="6" r="4"/><line x1="9.5" y1="9.5" x2="13" y2="13"/>
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- 전체 Job 현황 -->
    <div class="card" style="margin-bottom:12px;padding:0;overflow:hidden">
      <div class="card-header">
        <span>전체 Job 현황</span>
        <div style="display:flex;align-items:center;gap:8px">
          <label v-if="pagedJobs.length" class="chk-all">
            <input type="checkbox"
              :checked="selectedIds.size > 0 && pagedJobs.every(j => selectedIds.has(j.id))"
              :indeterminate.prop="selectedIds.size > 0 && !pagedJobs.every(j => selectedIds.has(j.id))"
              @change="togglePageAll"
              style="accent-color:var(--accent-blue);width:13px;height:13px"/>
            <span style="font-size:11.5px;color:var(--text-secondary)">
              {{ selectedIds.size > 0 ? selectedIds.size + '개 선택됨' : '전체 선택' }}
            </span>
          </label>
          <button v-if="selectedIds.size > 0" class="act-btn del-sel" @click="deleteSelected">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px">
              <polyline points="2,3.5 12,3.5"/>
              <path d="M5,3.5 V2 H9 V3.5"/>
              <path d="M3.5,3.5 L4.5,12 H9.5 L10.5,3.5"/>
            </svg>
            {{ selectedIds.size }}개 삭제
          </button>
          <div class="sel-wrap" style="min-width:0">
            <select v-model="pageSize" style="font-size:11px;padding:3px 22px 3px 6px">
              <option :value="10">10개</option>
              <option :value="20">20개</option>
              <option :value="50">50개</option>
            </select>
            <div class="chevron"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>
          </div>
          <span style="font-size:11px;color:var(--text-tertiary)">총 {{ allJobs.length }}개</span>
        </div>
      </div>

      <div v-if="!allJobs.length" class="empty-state">Job이 없습니다</div>
      <template v-else>
        <div v-for="j in pagedJobs" :key="j.id"
             class="list-row" :class="{'row-selected': selectedIds.has(j.id)}"
             @click.self="toggleSelect(j.id)">
          <input type="checkbox"
            :checked="selectedIds.has(j.id)"
            @change="toggleSelect(j.id)" @click.stop
            style="accent-color:var(--accent-blue);width:13px;height:13px;flex-shrink:0;cursor:pointer"/>
          <div class="db-icon" :style="{background:m(j.src_db)?.bg, color:m(j.src_db)?.color}">{{ m(j.src_db)?.label }}</div>
          <div style="flex:1;min-width:0">
            <div class="item-name">
              {{ j.name }}
              <span v-if="j.current_table && j.status==='running'" class="tbl-badge">{{ j.current_table }}</span>
            </div>
            <div class="item-desc">{{ j.src_database||j.src_db }} → {{ j.tgt_database||j.tgt_db }}</div>
          </div>
          <div class="item-right">
            <div v-if="j.status==='running'" class="progress-wrap" style="width:80px">
              <div class="progress-fill blue" :style="{width:(j.progress||0)+'%'}"></div>
            </div>
            <span style="font-size:11px;color:var(--text-tertiary)">{{ (j.progress||0).toFixed(0) }}%</span>
            <span class="pill" :class="pillCls(j.status)">{{ statusLbl(j.status) }}</span>
            <button v-if="!['running','paused'].includes(j.status)"
                    class="act-btn icon-only del-btn" @click.stop="doDel(j.id)" title="삭제">
              <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px">
                <polyline points="2,3.5 12,3.5"/>
                <path d="M5,3.5 V2 H9 V3.5"/>
                <path d="M3.5,3.5 L4.5,12 H9.5 L10.5,3.5"/>
              </svg>
            </button>
          </div>
        </div>
        <div v-if="totalPages > 1" class="pagination">
          <button class="pg-btn" :disabled="page===1" @click="page=1">«</button>
          <button class="pg-btn" :disabled="page===1" @click="page--">‹</button>
          <button v-for="p in pageNums" :key="p"
                  class="pg-btn" :class="{active: p===page}" @click="page=p">{{ p }}</button>
          <button class="pg-btn" :disabled="page===totalPages" @click="page++">›</button>
          <button class="pg-btn" :disabled="page===totalPages" @click="page=totalPages">»</button>
          <span class="pg-info">{{ page }} / {{ totalPages }}</span>
        </div>
      </template>
    </div>

    <!-- 실시간 로그 -->
    <div class="card log-card">
      <div class="card-header">
        <div style="display:flex;align-items:center;gap:8px">
          <span>실시간 로그</span>
          <span v-if="wsConnected" class="ws-badge">
            <span class="ws-live-dot"></span> LIVE
          </span>
          <span v-else class="poll-badge">POLL</span>
        </div>
        <div style="display:flex;gap:6px;align-items:center">
          <div class="log-level-filter">
            <button v-for="lv in ['all','debug','info','warn','error']" :key="lv"
                    class="lv-btn" :class="{active: logLevel===lv, ['lv-'+lv]: true}"
                    @click="logLevel=lv">
              {{ lv==='all' ? '전체' : lv.toUpperCase() }}
            </button>
          </div>
          <div class="sel-wrap" style="min-width:140px">
            <select v-model="logFilter" style="font-size:11.5px;padding:4px 24px 4px 8px">
              <option value="">전체 Job</option>
              <option v-for="j in allJobs" :key="j.id" :value="j.id">{{ j.name.slice(0,22) }}</option>
            </select>
            <div class="chevron"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>
          </div>
          <label class="auto-scroll-toggle">
            <input type="checkbox" v-model="autoScroll" style="accent-color:var(--accent-blue)"/>
            <span style="font-size:11px;color:var(--text-tertiary)">자동 스크롤</span>
          </label>
          <button class="act-btn" @click="clearLogs">지우기</button>
        </div>
      </div>

      <div class="log-box" ref="logBox">
        <template v-if="filteredLogs.length">
          <div v-for="(l, i) in filteredLogs.slice(-300)" :key="i"
               class="log-line" :class="'log-' + l.level">
            <span class="log-t">{{ l.time }}</span>
            <span class="log-tag">{{ l.tag }}</span>
            <span class="log-msg">{{ l.message }}</span>
          </div>
        </template>
        <div v-else class="empty-state" style="padding:16px;font-size:12px">로그가 없습니다</div>
      </div>

      <div class="log-footer">
        <span>총 {{ logs.length }}줄</span>
        <span class="log-stat info">INFO {{ logCounts.info }}</span>
        <span class="log-stat warn">WARN {{ logCounts.warn }}</span>
        <span class="log-stat error">ERR {{ logCounts.error }}</span>
        <span style="margin-left:auto;font-size:10.5px;color:var(--text-tertiary)">
          마지막 갱신: {{ lastRefreshStr }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useJobStore } from '@/store/jobStore.js'
import { useAppStore }  from '@/store/appStore.js'
import { jobsApi }      from '@/api/index.js'
import { DB_META }      from '@/constants/dbMeta.js'

const jobs = useJobStore()
const app  = useAppStore()

const logs        = ref([])
const logFilter   = ref('')
const logLevel    = ref('all')
const logBox      = ref(null)
const autoScroll  = ref(true)
const autoRefresh = ref(true)
const refreshing  = ref(false)
const lastRefresh = ref(new Date())

const wsConnected = ref(false)
const wsMap       = ref({})
let   pollTimer   = null
let   monitorWs   = null

const page        = ref(1)
const pageSize    = ref(10)
const selectedIds = ref(new Set())

const m         = t => DB_META[t] || { label:'??', bg:'#eee', color:'#333' }
const fmtRows   = n => n>=1e6 ? (n/1e6).toFixed(1)+'M' : n>=1e3 ? Math.round(n/1e3)+'K' : String(n||0)
const pillCls   = s => ({running:'pill-run',completed:'pill-ok',error:'pill-err',idle:'pill-idle',paused:'pill-pause',aborted:'pill-idle'}[s]||'pill-idle')
const statusLbl = s => ({running:'실행 중',completed:'완료',error:'오류',idle:'대기',paused:'일시정지',aborted:'중단'}[s]||s)

const lastRefreshStr = computed(() => {
  const d = lastRefresh.value
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`
})

const allJobs        = computed(() => jobs.jobs)
const running        = computed(() => jobs.jobs.filter(j => j.status==='running' || j.status==='paused'))
const totalSpeed     = computed(() => running.value.reduce((s,j) => s+(j.speed||0), 0))
const cumulativeRows = computed(() => jobs.jobs.reduce((s,j) => s+(j.rows_processed||0), 0))
const totalErrors    = computed(() => jobs.jobs.reduce((s,j) => s+(j.rows_error||0), 0))

const totalPages = computed(() => Math.max(1, Math.ceil(allJobs.value.length / pageSize.value)))
const pagedJobs  = computed(() => {
  const s = (page.value - 1) * pageSize.value
  return allJobs.value.slice(s, s + pageSize.value)
})
const pageNums = computed(() => {
  const t = totalPages.value, c = page.value, d = 2, r = []
  for (let i = Math.max(1,c-d); i <= Math.min(t,c+d); i++) r.push(i)
  return r
})

const filteredLogs = computed(() => {
  let list = logFilter.value ? logs.value.filter(l => l.job_id === logFilter.value) : logs.value
  return logLevel.value !== 'all' ? list.filter(l => l.level === logLevel.value) : list
})

const logCounts = computed(() => ({
  debug: logs.value.filter(l => l.level==='debug').length,
  info:  logs.value.filter(l => l.level==='info').length,
  warn:  logs.value.filter(l => l.level==='warn').length,
  error: logs.value.filter(l => l.level==='error').length,
}))

watch(page, () => { selectedIds.value = new Set() })
watch(pageSize, () => { page.value = 1; selectedIds.value = new Set() })
watch(() => allJobs.value.length, () => {
  if (page.value > totalPages.value) page.value = Math.max(1, totalPages.value)
})

// 로그 추가 (중복 방지)
const _logKeys = new Set()
function addLog(level, tag, msg, job_id='') {
  const key = `${tag}|${msg}|${job_id}`
  if (_logKeys.has(key)) return
  _logKeys.add(key)
  if (_logKeys.size > 600) {
    const it = _logKeys.values()
    for (let i = 0; i < 100; i++) _logKeys.delete(it.next().value)
  }
  const now = new Date()
  const t = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`
  logs.value.push({ time:t, level, tag:`[${tag}]`, message:msg, job_id })
  if (logs.value.length > 500) logs.value.splice(0, 50)
  if (autoScroll.value) nextTick(() => { if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight })
}

// ── WebSocket 연결 ────────────────────────────────────
function connectMonitorWs() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  try {
    monitorWs = new WebSocket(`${proto}://${location.host}/ws/monitor`)
    monitorWs.onopen = () => {
      wsConnected.value = true
      addLog('info', 'WebSocket', '모니터 WebSocket 연결됨')
    }
    monitorWs.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (Array.isArray(data.jobs)) jobs.jobs = data.jobs
        if (data.log) addLog(data.log.level||'info', data.log.tag||'Server', data.log.message, data.log.job_id||'')
        lastRefresh.value = new Date()
      } catch { /* ignore */ }
    }
    monitorWs.onclose = () => { wsConnected.value = false; setTimeout(connectMonitorWs, 3000) }
    monitorWs.onerror = () => { wsConnected.value = false; monitorWs?.close() }
  } catch { wsConnected.value = false }
}

function connectJobWs(jobId) {
  if (wsMap.value[jobId]) return
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  try {
    const ws = new WebSocket(`${proto}://${location.host}/ws/jobs/${jobId}`)
    ws.onopen = () => addLog('info', `Job#${jobId.slice(0,6)}`, 'WebSocket 연결됨', jobId)
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        const idx = jobs.jobs.findIndex(j => j.id === jobId)
        if (idx >= 0 && data.status) Object.assign(jobs.jobs[idx], data)
        if (Array.isArray(data.new_logs)) {
          data.new_logs.forEach(l => addLog(l.level||'info', l.tag||`Job#${jobId.slice(0,6)}`, l.message, jobId))
        }
        if (['completed','error','aborted'].includes(data.status)) {
          ws.close(); delete wsMap.value[jobId]
        }
        lastRefresh.value = new Date()
      } catch { /* ignore */ }
    }
    ws.onclose = () => { delete wsMap.value[jobId] }
    wsMap.value[jobId] = ws
  } catch { /* WS 불가 → 폴링 폴백 */ }
}

function disconnectJobWs(jobId) {
  if (wsMap.value[jobId]) {
    wsMap.value[jobId].onclose = null
    wsMap.value[jobId].close()
    delete wsMap.value[jobId]
  }
}

// ── 폴링 폴백 ────────────────────────────────────────
const prevStates = ref({})

async function pollRefresh() {
  if (wsConnected.value) return
  await jobs.fetch()
  lastRefresh.value = new Date()

  jobs.jobs.forEach(j => {
    const prev = prevStates.value[j.id]
    if (!prev) {
      if (j.status === 'running') addLog('info', `Job#${j.id.slice(0,6)}`, `새 Job: ${j.name}`, j.id)
    } else {
      if (prev.status !== j.status) {
        const lvl = j.status==='error' ? 'error' : j.status==='completed' ? 'info' : 'warn'
        addLog(lvl, `Job#${j.id.slice(0,6)}`, `[${j.name.slice(0,20)}] ${statusLbl(prev.status)} → ${statusLbl(j.status)}`, j.id)
      }
      if (j.status==='running' && prev.table !== j.current_table && j.current_table && j.current_table!=='준비 중...') {
        addLog('info', `Job#${j.id.slice(0,6)}`, `테이블: ${j.current_table} (${(j.rows_processed||0).toLocaleString()} rows)`, j.id)
      }
    }
    prevStates.value[j.id] = { status: j.status, table: j.current_table }
  })

  for (const j of running.value.slice(0, 3)) {
    try {
      const bl = await jobsApi.logs(j.id)
      bl.slice(-5).forEach(l => addLog(l.level||'info', l.tag||`Job#${j.id.slice(0,6)}`, l.message, j.id))
    } catch { /* 무시 */ }
  }
}

// running 변화 → Job별 WS 관리
watch(running, (newR, oldR) => {
  newR.forEach(j => {
    if (!oldR.find(o => o.id === j.id)) {
      connectJobWs(j.id)
      logFilter.value = j.id
      addLog('info', 'Monitor', `새 Job 시작: ${j.name}`, j.id)
    }
  })
  oldR.forEach(j => {
    if (!newR.find(o => o.id === j.id)) disconnectJobWs(j.id)
  })
}, { deep: false })

async function manualRefresh() {
  refreshing.value = true
  await jobs.fetch()
  lastRefresh.value = new Date()
  setTimeout(() => { refreshing.value = false }, 500)
}

function focusJob(jobId) {
  logFilter.value = jobId
  nextTick(() => { if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight })
}

function clearLogs() {
  logs.value = []
  _logKeys.clear()
  app.notify('로그 초기화됨', 'info')
}

function toggleSelect(id) {
  const s = new Set(selectedIds.value)
  s.has(id) ? s.delete(id) : s.add(id)
  selectedIds.value = s
}
function togglePageAll(e) {
  const s = new Set(selectedIds.value)
  const del = pagedJobs.value.filter(j => !['running','paused'].includes(j.status))
  if (e.target.checked) del.forEach(j => s.add(j.id))
  else del.forEach(j => s.delete(j.id))
  selectedIds.value = s
}
async function deleteSelected() {
  const ids = [...selectedIds.value]
  if (!ids.length) return
  if (!confirm(`선택한 ${ids.length}개 Job을 삭제하시겠습니까?`)) return
  for (const id of ids) { try { await jobs.del(id) } catch { /* 무시 */ } }
  selectedIds.value = new Set()
  app.notify(`${ids.length}개 삭제됨`, 'success')
}

async function doPause(id)  { await jobs.pause(id);  addLog('warn','Monitor','일시정지',id); app.notify('일시정지됨','warn') }
async function doResume(id) { await jobs.resume(id); addLog('info','Monitor','재개',id);      app.notify('재개됨','success') }
async function doStop(id)   {
  if (!confirm('이관을 중단하시겠습니까?')) return
  await jobs.stop(id); addLog('warn','Monitor','중단',id); app.notify('중단됨','warn')
}
async function doDel(id) {
  if (!confirm('이 Job을 삭제하시겠습니까?')) return
  await jobs.del(id); app.notify('삭제됨')
}

onMounted(async () => {
  await jobs.fetch()
  jobs.jobs.forEach(j => { prevStates.value[j.id] = { status: j.status, table: j.current_table } })
  addLog('info', 'Monitor', `모니터링 시작 — Job ${jobs.jobs.length}개 로드됨`)
  if (running.value.length > 0) {
    logFilter.value = running.value[0].id
    running.value.forEach(j => connectJobWs(j.id))
  }
  connectMonitorWs()
  pollTimer = setInterval(async () => { if (autoRefresh.value) await pollRefresh() }, 2000)
})

onUnmounted(() => {
  clearInterval(pollTimer)
  if (monitorWs) { monitorWs.onclose = null; monitorWs.close() }
  Object.values(wsMap.value).forEach(ws => { ws.onclose = null; ws.close() })
})
</script>

<style scoped>
.monitor-page { display:flex; flex-direction:column; gap:0; }
.mon-header { display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:14px; }
.header-actions { display:flex; align-items:center; gap:8px; }

.ws-status { display:flex; align-items:center; gap:5px; font-size:11px; padding:4px 10px; border-radius:20px; border:0.5px solid var(--border-mid); }
.ws-status.ws-ok  { background:var(--bg-success); color:var(--text-success); border-color:var(--accent-green); }
.ws-status.ws-off { background:var(--bg-secondary); color:var(--text-tertiary); }
.ws-dot { width:6px; height:6px; border-radius:50%; background:currentColor; }
.ws-ok .ws-dot { animation:ws-pulse 1.5s infinite; }
@keyframes ws-pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

.mon-row { display:flex; align-items:flex-start; gap:14px; padding:14px 16px; border-bottom:0.5px solid var(--border-light); }
.mon-row:last-child { border-bottom:none; }
.mon-info { min-width:180px; flex-shrink:0; }
.mon-prog { flex:1; min-width:0; }
.mon-acts { display:flex; flex-direction:column; gap:5px; flex-shrink:0; }

.cur-tbl-row { display:flex; align-items:center; gap:6px; padding:4px 8px; background:var(--bg-info); border-radius:var(--radius-sm); margin-bottom:6px; font-size:11.5px; }
.cur-tbl-label { color:var(--text-tertiary); flex-shrink:0; }
.cur-tbl-name { font-family:'Consolas','SF Mono',monospace; font-weight:600; color:var(--text-info); flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.cur-tbl-cnt { color:var(--text-tertiary); flex-shrink:0; font-size:10.5px; }

.prog-meta { display:flex; gap:12px; font-size:11px; color:var(--text-tertiary); margin-bottom:5px; align-items:center; }
.prog-pct { font-size:14px; font-weight:600; color:var(--text-info); }
.rows-meta { font-size:10.5px; color:var(--text-tertiary); margin-top:4px; }
.rows-meta b { color:var(--text-primary); }

.log-card { padding:0; overflow:hidden; }
.log-level-filter { display:flex; border:0.5px solid var(--border-mid); border-radius:var(--radius-sm); overflow:hidden; }
.lv-btn { padding:3px 8px; font-size:10.5px; border:none; background:var(--bg-secondary); color:var(--text-tertiary); cursor:pointer; font-family:var(--font); transition:all .1s; border-right:0.5px solid var(--border-light); }
.lv-btn:last-child { border-right:none; }
.lv-btn:hover { background:var(--bg-primary); color:var(--text-primary); }
.lv-btn.active { font-weight:600; }
.lv-btn.lv-all.active   { background:var(--bg-tertiary); color:var(--text-primary); }
.lv-btn.lv-info.active  { background:var(--bg-info); color:var(--text-info); }
.lv-btn.lv-warn.active  { background:var(--bg-warning); color:var(--text-warning); }
.lv-btn.lv-error.active { background:var(--bg-danger); color:var(--text-danger); }

.ws-badge { display:inline-flex; align-items:center; gap:4px; font-size:10px; font-weight:700; padding:2px 7px; border-radius:8px; background:var(--bg-success); color:var(--text-success); letter-spacing:.5px; }
.ws-live-dot { width:5px; height:5px; border-radius:50%; background:var(--text-success); animation:ws-pulse 1s infinite; }
.poll-badge { font-size:10px; font-weight:600; padding:2px 7px; border-radius:8px; background:var(--bg-secondary); color:var(--text-tertiary); }
.auto-scroll-toggle { display:flex; align-items:center; gap:4px; cursor:pointer; }

.log-box { background:var(--bg-secondary); padding:10px 12px; max-height:340px; overflow-y:auto; font-family:'Consolas','SF Mono',monospace; }
.log-line { display:flex; gap:8px; font-size:11.5px; padding:2px 0; line-height:1.6; color:var(--text-secondary); }
.log-t   { color:var(--text-tertiary); flex-shrink:0; }
.log-tag { color:var(--text-info); flex-shrink:0; min-width:100px; }
.log-msg { flex:1; word-break:break-all; }
.log-warn  .log-tag,.log-warn  .log-msg { color:var(--text-warning); }
.log-error .log-tag,.log-error .log-msg { color:var(--text-danger); }

.log-footer { display:flex; align-items:center; gap:10px; padding:7px 14px; border-top:0.5px solid var(--border-light); font-size:11px; color:var(--text-tertiary); }
.log-stat { font-weight:600; }
.log-stat.info  { color:var(--text-info); }
.log-stat.warn  { color:var(--text-warning); }
.log-stat.error { color:var(--text-danger); }

.refresh-dot { width:7px; height:7px; border-radius:50%; background:var(--border-mid); }
.refresh-dot.active { background:#639922; animation:blink 2s infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }

.toggle { position:relative; width:34px; height:18px; background:var(--border-mid); border-radius:9px; cursor:pointer; transition:background .2s; flex-shrink:0; }
.toggle.sm { width:28px; height:16px; }
.toggle.on { background:var(--accent-blue); }
.toggle::after { content:''; position:absolute; top:2px; left:2px; width:14px; height:14px; border-radius:50%; background:white; transition:transform .2s; }
.toggle.sm::after { width:12px; height:12px; }
.toggle.on::after { transform:translateX(16px); }
.toggle.sm.on::after { transform:translateX(12px); }

.tbl-badge { font-size:10px; background:var(--bg-info); color:var(--text-info); padding:1px 6px; border-radius:4px; margin-left:6px; font-family:'Consolas','SF Mono',monospace; }
.chk-all { display:flex; align-items:center; gap:5px; cursor:pointer; }
.row-selected { background:var(--bg-info) !important; }
.del-sel { background:rgba(239,68,68,.08); color:var(--text-danger); border-color:rgba(239,68,68,.3); font-size:11.5px; display:inline-flex; align-items:center; gap:4px; padding:4px 8px; border-radius:var(--radius-sm); cursor:pointer; border:0.5px solid rgba(239,68,68,.3); }
.del-sel:hover { background:rgba(239,68,68,.15); }
.del-btn:hover { color:var(--text-danger); border-color:rgba(239,68,68,.3); }

.pagination { display:flex; align-items:center; gap:4px; padding:10px 16px; border-top:0.5px solid var(--border-light); justify-content:center; }
.pg-btn { min-width:28px; height:26px; padding:0 6px; border-radius:var(--radius-sm); border:0.5px solid var(--border-mid); background:transparent; color:var(--text-secondary); font-size:12px; cursor:pointer; font-family:var(--font); transition:all .1s; }
.pg-btn:hover:not(:disabled) { background:var(--bg-info); color:var(--text-info); border-color:var(--accent-blue); }
.pg-btn.active { background:var(--accent-blue); color:#fff; border-color:var(--accent-blue); font-weight:600; }
.pg-btn:disabled { opacity:.35; cursor:not-allowed; }
.pg-info { font-size:11px; color:var(--text-tertiary); margin-left:6px; }

@keyframes spin { to { transform:rotate(360deg); } }
.spinning { animation:spin .7s linear infinite; }
</style>
