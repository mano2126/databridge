<template>
  <div>
    <div class="page-title">실시간 모니터</div>
    <div class="page-desc">실행 중인 마이그레이션 Job의 진행 상황을 실시간으로 확인합니다</div>

    <!-- KPI -->
    <div class="kpi-grid">
      <div class="kpi-card"><div class="kpi-label">실행 중</div><div class="kpi-value ok">{{ running.length }}</div></div>
      <div class="kpi-card"><div class="kpi-label">처리 속도 (rows/s)</div><div class="kpi-value info">{{ totalSpeed.toLocaleString() }}</div></div>
      <div class="kpi-card"><div class="kpi-label">누적 처리 rows</div><div class="kpi-value">{{ fmtRows(cumulativeRows) }}</div></div>
      <div class="kpi-card"><div class="kpi-label">오류 건수</div><div class="kpi-value err">{{ totalErrors }}</div></div>
    </div>

    <!-- 실행 중 Job 패널 -->
    <div class="card" style="margin-bottom:12px">
      <div class="card-header">
        실행 중인 Job
        <div style="display:flex;align-items:center;gap:8px">
          <span class="refresh-dot" :class="{active: autoRefresh}"></span>
          <span style="font-size:11px;color:var(--text-tertiary)">자동 새로고침 2초</span>
          <div class="toggle sm" :class="{on:autoRefresh}" @click="autoRefresh=!autoRefresh"></div>
          <button class="act-btn icon-only" @click="refresh" title="즉시 새로고침"><svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.6" style="width:12px;height:12px"><path d="M12 7A5 5 0 1 1 7 2"/><polyline points="8,2 12,2 12,5.5"/></svg></button>
          <button class="act-btn icon-only" @click="clearLocalLogs" title="로컬 화면 로그 초기화"><svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><polyline points="2,3.5 12,3.5"/><path d="M5,3.5 V2 H9 V3.5"/><path d="M3.5,3.5 L4.5,12 H9.5 L10.5,3.5"/></svg></button>
        </div>
      </div>

      <div v-if="!running.length && !justStarted.length" class="empty-state" style="padding:24px">
        현재 실행 중인 Job이 없습니다
      </div>

      <!-- 방금 시작된 Job (준비 중 포함) -->
      <div v-for="j in [...running, ...justStarted]" :key="j.id" class="mon-row">
        <div class="db-icon" :style="{background:m(j.src_db)?.bg,color:m(j.src_db)?.color}">
          {{ m(j.src_db)?.label }}
        </div>

        <div class="mon-info">
          <div class="item-name">{{ j.name }}</div>
          <div class="item-desc">
            {{ j.src_database||j.src_db }} → {{ j.tgt_database||j.tgt_db }}
          </div>
          <div style="margin-top:2px">
            <span class="pill" :class="pillCls(j.status)">{{ statusLbl(j.status) }}</span>
            <span v-if="j.table_total>0" style="font-size:10.5px;color:var(--text-tertiary);margin-left:6px">
              테이블 {{ j.table_done }}/{{ j.table_total }}
            </span>
          </div>
        </div>

        <div class="mon-prog">
          <!-- 현재 처리 중인 테이블 -->
          <div class="cur-tbl-row" v-if="j.current_table">
            <span class="cur-tbl-label">테이블:</span>
            <span class="cur-tbl-name">{{ j.current_table }}</span>
            <span v-if="j.current_table_rows_total>0" class="cur-tbl-cnt">
              {{ (j.current_table_rows_done||0).toLocaleString() }}
              /
              {{ (j.current_table_rows_total||0).toLocaleString() }} rows
            </span>
          </div>

          <!-- 진행률 바 -->
          <div class="prog-meta">
            <span class="prog-pct">{{ (j.progress||0).toFixed(1) }}%</span>
            <span>{{ (j.speed||0).toLocaleString() }} rows/s</span>
            <span v-if="j.rows_error>0" style="color:var(--text-danger)">오류 {{ j.rows_error }}건</span>
          </div>
          <div class="progress-wrap">
            <div class="progress-fill" :class="j.status==='paused'?'warn':'blue'"
                 :style="{width:(j.progress||0)+'%'}"></div>
          </div>

          <!-- 처리 rows -->
          <div class="rows-meta">
            처리: <b>{{ (j.rows_processed||0).toLocaleString() }}</b> rows
            / 전체: {{ (j.rows_total||0).toLocaleString() }} rows
          </div>
        </div>

        <div class="mon-acts">
          <button v-if="j.status==='running'"  class="act-btn warn" @click="doPause(j.id)">일시정지</button>
          <button v-if="j.status==='paused'"   class="act-btn ok"   @click="doResume(j.id)">재개</button>
          <button v-if="j.status==='running'||j.status==='paused'" class="act-btn del" @click="doStop(j.id)">중단</button>
        </div>
      </div>
    </div>

    <!-- 전체 Job 현황 -->
    <div class="card" style="margin-bottom:12px">
      <div class="card-header">
        <span>전체 Job 현황</span>
        <div style="display:flex;align-items:center;gap:8px">
          <!-- 전체선택 -->
          <label v-if="pagedJobs.length" class="chk-all" title="현재 페이지 전체 선택">
            <input type="checkbox"
              :checked="selectedIds.size > 0 && pagedJobs.every(j => selectedIds.has(j.id))"
              :indeterminate.prop="selectedIds.size > 0 && !pagedJobs.every(j => selectedIds.has(j.id))"
              @change="togglePageAll"
              style="accent-color:var(--accent-blue);width:13px;height:13px"/>
            <span style="font-size:11.5px;color:var(--text-secondary)">
              {{ selectedIds.size > 0 ? selectedIds.size + '개 선택됨' : '전체 선택' }}
            </span>
          </label>
          <!-- 선택 삭제 -->
          <button v-if="selectedIds.size > 0"
            class="act-btn del-sel"
            @click="deleteSelected"
            title="선택 항목 삭제">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px">
              <polyline points="2,3.5 12,3.5"/>
              <path d="M5,3.5 V2 H9 V3.5"/>
              <path d="M3.5,3.5 L4.5,12 H9.5 L10.5,3.5"/>
            </svg>
            {{ selectedIds.size }}개 삭제
          </button>
          <!-- 페이지 크기 -->
          <select v-model="pageSize" style="font-size:11px;padding:3px 6px;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:var(--bg-secondary);color:var(--text-secondary)">
            <option :value="10">10개</option>
            <option :value="20">20개</option>
            <option :value="50">50개</option>
          </select>
          <span style="font-size:11px;color:var(--text-tertiary)">
            총 {{ allJobs.length }}개
          </span>
        </div>
      </div>

      <div v-if="!allJobs.length" class="empty-state">Job이 없습니다</div>
      <template v-else>
        <div v-for="j in pagedJobs" :key="j.id"
             class="list-row" :class="{'row-selected': selectedIds.has(j.id)}"
             @click.self="toggleSelect(j.id)">
          <!-- 체크박스 -->
          <input type="checkbox"
            :checked="selectedIds.has(j.id)"
            @change="toggleSelect(j.id)"
            @click.stop
            style="accent-color:var(--accent-blue);width:13px;height:13px;flex-shrink:0;cursor:pointer"/>
          <div class="db-icon" :style="{background:m(j.src_db)?.bg,color:m(j.src_db)?.color}">{{ m(j.src_db)?.label }}</div>
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
              class="act-btn icon-only del-btn"
              @click.stop="doDel(j.id)"
              title="삭제">
              <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px">
                <polyline points="2,3.5 12,3.5"/>
                <path d="M5,3.5 V2 H9 V3.5"/>
                <path d="M3.5,3.5 L4.5,12 H9.5 L10.5,3.5"/>
              </svg>
            </button>
          </div>
        </div>

        <!-- 페이지네이션 -->
        <div v-if="totalPages > 1" class="pagination">
          <button class="pg-btn" :disabled="page===1" @click="page=1">«</button>
          <button class="pg-btn" :disabled="page===1" @click="page--">‹</button>
          <button v-for="p in pageNums" :key="p"
            class="pg-btn" :class="{active: p===page}"
            @click="page=p">{{ p }}</button>
          <button class="pg-btn" :disabled="page===totalPages" @click="page++">›</button>
          <button class="pg-btn" :disabled="page===totalPages" @click="page=totalPages">»</button>
          <span class="pg-info">{{ page }} / {{ totalPages }}</span>
        </div>
      </template>
    </div>

    <!-- 로그 -->
    <div class="card">
      <div class="card-header">
        실시간 로그
        <div style="display:flex;gap:6px;align-items:center">
          <select v-model="logFilter" style="font-size:11.5px;padding:3px 8px;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:var(--bg-secondary);color:var(--text-primary)">
            <option value="">전체 Job</option>
            <option v-for="j in allJobs" :key="j.id" :value="j.id">{{ j.name.slice(0,25) }}</option>
          </select>
          <button class="act-btn" @click="logs=[]">지우기</button>
        </div>
      </div>
      <div class="log-box" ref="logBox">
        <div v-for="(l,i) in filteredLogs.slice(-50)" :key="i" class="log-line" :class="'log-'+l.level">
          <span class="log-t">{{ l.time }}</span>
          <span class="log-tag">[{{ l.tag }}]</span>
          <span>{{ l.message }}</span>
        </div>
        <div v-if="!filteredLogs.length" class="empty-state" style="padding:12px">로그가 없습니다</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useJobStore } from '@/store/jobStore.js'
import { useAppStore } from '@/store/appStore.js'
import { jobsApi } from '@/api/index.js'
import { DB_META } from '@/constants/dbMeta.js'

const jobs = useJobStore()
const router = useRouter()
const app  = useAppStore()

const logs        = ref([])
const logFilter   = ref('')
const logBox      = ref(null)
const autoRefresh = ref(true)
let   timer       = null

const m         = t => DB_META[t]||{label:'??',bg:'#eee',color:'#333'}
const fmtRows   = n => n>=1e6?(n/1e6).toFixed(1)+'M':n>=1e3?Math.round(n/1e3)+'K':String(n||0)
const pillCls   = s => ({running:'pill-run',completed:'pill-ok',error:'pill-err',
                          idle:'pill-idle',paused:'pill-pause',aborted:'pill-idle'}[s]||'pill-idle')
const statusLbl = s => ({running:'실행 중',completed:'완료',error:'오류',
                          idle:'대기',paused:'일시정지',aborted:'중단'}[s]||s)

const allJobs      = computed(() => jobs.jobs)

// ── 페이징 + 다중선택 ──────────────────────────────────────
const page       = ref(1)
const pageSize   = ref(10)
const selectedIds = ref(new Set())

const totalPages = computed(() => Math.max(1, Math.ceil(allJobs.value.length / pageSize.value)))
const pagedJobs  = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return allJobs.value.slice(start, start + pageSize.value)
})
const pageNums = computed(() => {
  const total = totalPages.value
  const cur   = page.value
  const delta = 2
  const range = []
  for (let i = Math.max(1, cur - delta); i <= Math.min(total, cur + delta); i++) range.push(i)
  return range
})

// 페이지 변경 시 선택 초기화
watch(page, () => { selectedIds.value = new Set() })
watch(pageSize, () => { page.value = 1; selectedIds.value = new Set() })
// Job 수 변경 시 페이지 범위 보정
watch(() => allJobs.value.length, () => {
  if (page.value > totalPages.value) page.value = Math.max(1, totalPages.value)
})

function toggleSelect(id) {
  const s = new Set(selectedIds.value)
  s.has(id) ? s.delete(id) : s.add(id)
  selectedIds.value = s
}

function togglePageAll(e) {
  const s = new Set(selectedIds.value)
  const deletable = pagedJobs.value.filter(j => !['running','paused'].includes(j.status))
  if (e.target.checked) {
    deletable.forEach(j => s.add(j.id))
  } else {
    deletable.forEach(j => s.delete(j.id))
  }
  selectedIds.value = s
}

async function deleteSelected() {
  const ids = [...selectedIds.value]
  if (!ids.length) return
  if (!confirm(`선택한 ${ids.length}개 Job을 삭제하시겠습니까?`)) return
  for (const id of ids) {
    try { await jobs.del(id) } catch {}
  }
  selectedIds.value = new Set()
  addLog('info', 'Monitor', `${ids.length}개 Job 삭제됨`)
  app.notify(`${ids.length}개 삭제됨`, 'success')
}

// 실행 중 + 일시정지
const running      = computed(() =>
  jobs.jobs.filter(j => j.status==='running' || j.status==='paused')
)

// 방금 시작된 Job (idle이지만 30초 이내 생성된 것 — 아직 running 전환 전)
const justStarted  = computed(() => {
  const now = Date.now()
  return jobs.jobs.filter(j => {
    if (j.status !== 'idle') return false
    if (!j.started_at) return false
    try {
      return (now - new Date(j.started_at).getTime()) < 30000
    } catch { return false }
  })
})

const totalSpeed     = computed(() => running.value.reduce((s,j) => s+(j.speed||0), 0))
const cumulativeRows = computed(() => jobs.jobs.reduce((s,j) => s+(j.rows_processed||0), 0))
const totalErrors    = computed(() => jobs.jobs.reduce((s,j) => s+(j.rows_error||0), 0))

const filteredLogs = computed(() =>
  logFilter.value ? logs.value.filter(l=>l.job_id===logFilter.value) : logs.value
)

function addLog(level, tag, msg, job_id='') {
  const now = new Date()
  const t = `${now.getHours().toString().padStart(2,'0')}:${now.getMinutes().toString().padStart(2,'0')}:${now.getSeconds().toString().padStart(2,'0')}`
  logs.value.push({ time:t, level, tag, message:msg, job_id })
  if (logs.value.length > 300) logs.value.shift()
  nextTick(() => { if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight })
}

// 이전 상태 캐시
const prevStates = ref({})

async function refresh() {
  await jobs.fetch()

  // 상태 변화 감지 → 로그 자동 추가
  jobs.jobs.forEach(j => {
    const prev = prevStates.value[j.id]
    if (!prev) {
      // 새로 나타난 Job
      if (j.status === 'running') {
        addLog('info', `Job#${j.id.slice(0,6)}`, `새 Job 감지 — 실행 중: ${j.name}`, j.id)
      }
    } else {
      // 상태 변화
      if (prev.status !== j.status) {
        const lvl = j.status==='error'?'error':j.status==='completed'?'info':'warn'
        addLog(lvl, `Job#${j.id.slice(0,6)}`,
          `[${j.name.slice(0,25)}] ${statusLbl(prev.status)} → ${statusLbl(j.status)}`, j.id)
      }
      // 테이블 변경
      if (j.status==='running' && prev.table !== j.current_table && j.current_table && j.current_table!=='준비 중...') {
        addLog('info', `Job#${j.id.slice(0,6)}`,
          `테이블 이관: ${j.current_table} (${(j.rows_processed||0).toLocaleString()} rows 완료)`, j.id)
      }
    }
    prevStates.value[j.id] = { status: j.status, table: j.current_table }
  })

  // 실행 중인 Job의 백엔드 로그 가져오기
  for (const j of running.value.slice(0, 3)) {
    try {
      const bl = await jobsApi.logs(j.id)
      bl.slice(-3).forEach(l => {
        const key = l.time + l.message
        if (!logs.value.find(ex => ex.time+ex.message === key)) {
          logs.value.push({ ...l, job_id: j.id })
        }
      })
    } catch {}
  }
}

async function doPause(id) {
  await jobs.pause(id)
  addLog('warn', `Job#${id.slice(0,6)}`, '일시정지 요청', id)
  app.notify('일시정지됨', 'warn')
}
async function doResume(id) {
  await jobs.resume(id)
  addLog('info', `Job#${id.slice(0,6)}`, '재개 요청', id)
  app.notify('재개됨', 'success')
}
async function doStop(id) {
  if (!confirm('이관을 중단하시겠습니까?')) return
  await jobs.stop(id)
  addLog('warn', `Job#${id.slice(0,6)}`, '중단 요청', id)
  app.notify('중단됨', 'warn')
}

// running Job이 생기면 로그 필터를 해당 Job으로 자동 전환
watch(running, (newRunning, oldRunning) => {
  if (newRunning.length > oldRunning.length) {
    const newJob = newRunning.find(j => !oldRunning.find(o => o.id===j.id))
    if (newJob) {
      logFilter.value = newJob.id
      addLog('info', 'Monitor', `새 Job 시작: ${newJob.name}`, newJob.id)
    }
  }
}, { deep: false })

onMounted(async () => {
  // 즉시 fetch
  await jobs.fetch()

  // 초기 상태 캐시
  jobs.jobs.forEach(j => {
    prevStates.value[j.id] = { status: j.status, table: j.current_table }
  })

  addLog('info', 'Monitor', `모니터링 시작 — Job ${jobs.jobs.length}개 로드됨`)

  // running Job이 있으면 자동으로 로그 필터 설정
  if (running.value.length > 0) {
    logFilter.value = running.value[0].id
  }

  // 2초 폴링
  timer = setInterval(async () => {
    if (autoRefresh.value) await refresh()
  }, 2000)
})

function clearLocalLogs() {
  localLogs.value = []
  app.notify('로컬 로그 초기화됨', 'info')
}

async function doDel(id) {
  if (!confirm('이 Job을 목록에서 삭제하시겠습니까?')) return
  await jobs.del(id)
  addLog('info', 'Monitor', `Job 삭제됨`)
  app.notify('삭제됨')
}

onUnmounted(() => {
  clearInterval(timer)
  jobs.disconnectAll()
})
</script>

<style scoped>
.mon-row {
  display:flex; align-items:flex-start; gap:14px;
  padding:14px 0; border-bottom:0.5px solid var(--border-light);
}
.mon-row:last-child { border-bottom:none; }

.mon-info { min-width:180px; flex-shrink:0; }
.mon-prog { flex:1; min-width:0; }

/* 현재 테이블 */
.cur-tbl-row {
  display:flex; align-items:center; gap:6px;
  padding:4px 8px; background:var(--bg-info);
  border-radius:var(--radius-sm); margin-bottom:6px;
  font-size:11.5px;
}
.cur-tbl-label { color:var(--text-tertiary); flex-shrink:0; }
.cur-tbl-name  {
  font-family:'Consolas','SF Mono',monospace;
  font-weight:600; color:var(--text-info);
  flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}
.cur-tbl-cnt { color:var(--text-tertiary); flex-shrink:0; font-size:10.5px; }

.prog-meta { display:flex; gap:12px; font-size:11px; color:var(--text-tertiary); margin-bottom:5px; align-items:center; }
.prog-pct  { font-size:14px; font-weight:600; color:var(--text-info); }
.rows-meta { font-size:10.5px; color:var(--text-tertiary); margin-top:4px; }
.rows-meta b { color:var(--text-primary); }

.mon-acts { display:flex; flex-direction:column; gap:5px; flex-shrink:0; }

/* 새로고침 점 애니메이션 */
.refresh-dot { width:7px; height:7px; border-radius:50%; background:var(--border-mid); }
.refresh-dot.active { background:#639922; animation:blink 2s infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }

.tbl-badge {
  font-size:10px; background:var(--bg-info); color:var(--text-info);
  padding:1px 6px; border-radius:4px; margin-left:6px;
  font-family:'Consolas','SF Mono',monospace;
}

/* toggle */
.toggle { position:relative; width:34px; height:18px; background:var(--border-mid); border-radius:9px; cursor:pointer; transition:background .2s; flex-shrink:0; }
.toggle.sm { width:28px; height:16px; }
.toggle.on { background:var(--accent-blue); }
.toggle::after { content:''; position:absolute; top:2px; left:2px; width:14px; height:14px; border-radius:50%; background:white; transition:transform .2s; }
.toggle.sm::after { width:12px; height:12px; }
.toggle.on::after { transform:translateX(16px); }
.toggle.sm.on::after { transform:translateX(12px); }

/* 페이지네이션 */
.pagination { display:flex; align-items:center; gap:4px; padding:10px 16px; border-top:0.5px solid var(--border-light); justify-content:center; }
.pg-btn { min-width:28px; height:26px; padding:0 6px; border-radius:var(--radius-sm); border:0.5px solid var(--border-mid); background:transparent; color:var(--text-secondary); font-size:12px; cursor:pointer; font-family:var(--font); transition:all .1s; }
.pg-btn:hover:not(:disabled) { background:var(--bg-info); color:var(--text-info); border-color:var(--accent-blue); }
.pg-btn.active { background:var(--accent-blue); color:#fff; border-color:var(--accent-blue); font-weight:600; }
.pg-btn:disabled { opacity:.35; cursor:not-allowed; }
.pg-info { font-size:11px; color:var(--text-tertiary); margin-left:6px; }

/* 다중선택 */
.chk-all { display:flex; align-items:center; gap:5px; cursor:pointer; }
.row-selected { background:var(--bg-info) !important; }
.row-selected:hover { background:var(--bg-info) !important; }
.del-sel { background:rgba(239,68,68,.08); color:var(--text-danger); border-color:rgba(239,68,68,.3); font-size:11.5px; display:inline-flex; align-items:center; gap:4px; padding:4px 8px; border-radius:var(--radius-sm); cursor:pointer; }
.del-sel:hover { background:rgba(239,68,68,.15); }
.del-btn:hover { color:var(--text-danger); border-color:rgba(239,68,68,.3); }
.log-box { background:var(--bg-secondary); border-radius:var(--radius-md); padding:10px 12px; max-height:300px; overflow-y:auto; font-family:'Consolas','SF Mono',monospace; }
.log-line { display:flex; gap:8px; font-size:11.5px; padding:2px 0; line-height:1.6; color:var(--text-secondary); }
.log-t    { color:var(--text-tertiary); flex-shrink:0; }
.log-tag  { color:var(--text-info); flex-shrink:0; min-width:90px; }
.log-warn  { color:var(--text-warning); }
.log-error { color:var(--text-danger); }
</style>
