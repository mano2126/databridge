<template>
  <div class="dashboard">

    <!-- 헤더 -->
    <div class="dash-header">
      <div>
        <div class="page-title">대시보드</div>
        <div class="page-desc">{{ greeting }} · {{ nowStr }}</div>
      </div>
      <button class="refresh-btn" @click="load" :disabled="loadingJobs" title="새로고침">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"
             :class="{spinning: loadingJobs}" style="width:13px;height:13px">
          <path d="M14 8A6 6 0 1 1 8 2"/>
          <polyline points="10,2 14,2 14,6"/>
        </svg>
      </button>
    </div>

    <!-- KPI 카드 -->
    <div class="kpi-row">
      <div class="kpi-card" v-for="k in kpis" :key="k.label" :class="[k.cls, k.to ? 'kpi-clickable' : '']"
           @click="k.to && $router.push(k.to)"
           :title="k.to ? k.label + ' 상세 보기' : ''">
        <div class="kpi-top">
          <div class="kpi-ico" v-html="k.icon"></div>
          <div class="kpi-trend" v-if="k.trend != null" :class="k.trend >= 0 ? 'up':'down'">
            {{ k.trend >= 0 ? '↑' : '↓' }} {{ Math.abs(k.trend) }}
          </div>
        </div>
        <div class="kpi-val">{{ k.val }}</div>
        <div class="kpi-lbl">{{ k.label }}</div>
      </div>
    </div>

    <!-- 메인 그리드 -->
    <div class="main-grid">

      <!-- 좌: 최근 Job -->
      <div class="card job-card">
        <div class="card-header">
          <span>최근 Job 실행</span>
          <button class="link-btn" @click="$router.push('/jobs')">전체 보기 →</button>
        </div>
        <div v-if="loadingJobs" class="loading-state">
          <div class="loading-dots"><span/><span/><span/></div>
        </div>
        <div v-else-if="recentJobs.length === 0" class="empty-state">
          <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.2" style="width:36px;height:36px;opacity:.3"><rect x="8" y="8" width="32" height="32" rx="4"/><path d="M16 24h16M16 32h10"/></svg>
          <p>실행된 Job이 없습니다</p>
        </div>
        <div v-else class="job-list">
          <div v-for="j in recentJobs" :key="j.id" class="job-row"
               @click="$router.push('/jobs')">
            <div class="job-db-badge" :style="{background:m(j.src_db).bg, color:m(j.src_db).color}">
              {{ m(j.src_db).label }}
            </div>
            <div class="job-info">
              <div class="job-name">{{ j.name }}</div>
              <div class="job-sub">
                <span>{{ j.src_db }} → {{ j.tgt_db }}</span>
                <span class="dot">·</span>
                <span>{{ fmtDate(j.created_at) }}</span>
              </div>
            </div>
            <div class="job-right">
              <div v-if="j.status==='running'" class="mini-progress">
                <div class="mini-fill" :style="{width: j.progress+'%'}"/>
                <span class="mini-pct">{{ j.progress }}%</span>
              </div>
              <span class="status-pill" :class="pillCls(j.status)">{{ statusLbl(j.status) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 우: 연결 상태 + 빠른 이동 -->
      <div class="side-col">

        <!-- 연결 상태 -->
        <div class="card conn-card">
          <div class="card-header">
            <span>연결 상태</span>
            <button class="link-btn" @click="checkHealth" :disabled="checkingHealth">
              <span v-if="checkingHealth" class="spinner" style="width:9px;height:9px;display:inline-block;margin-right:2px"/>
              확인
            </button>
          </div>
          <div class="conn-list">
            <div v-for="c in connStatus" :key="c.label" class="conn-item">
              <div class="conn-dot" :class="c.ok ? 'ok' : 'err'"/>
              <div class="conn-info">
                <div class="conn-name">{{ c.label }}</div>
                <div class="conn-sub">{{ c.sub }}</div>
              </div>
              <div class="conn-badge" :class="c.ok ? 'ok' : 'err'">
                {{ c.ok ? '정상' : '오프라인' }}
              </div>
            </div>
          </div>
        </div>

        <!-- 빠른 이동 -->
        <div class="card quick-card">
          <div class="card-header"><span>빠른 이동</span></div>
          <div class="quick-grid">
            <button v-for="q in quickLinks" :key="q.label" class="quick-item"
                    @click="$router.push(q.to)">
              <div class="quick-ico" v-html="q.icon"/>
              <span>{{ q.label }}</span>
            </button>
          </div>
        </div>

      </div>
    </div>

    <!-- 하단: 이관 현황 바 + 최근 활동 -->
    <div class="bottom-grid">

      <!-- 상태별 현황 -->
      <div class="card stat-card">
        <div class="card-header"><span>Job 상태 현황</span></div>
        <div class="stat-bars">
          <div v-for="s in statusBars" :key="s.label" class="stat-bar-row">
            <div class="stat-bar-label">{{ s.label }}</div>
            <div class="stat-bar-track">
              <div class="stat-bar-fill" :class="s.cls"
                   :style="{width: s.pct + '%'}"/>
            </div>
            <div class="stat-bar-val">{{ s.count }}</div>
          </div>
          <div v-if="!stats.totalJobs" class="empty-state" style="padding:12px 0;font-size:12px">
            아직 Job이 없습니다
          </div>
        </div>
        <div class="stat-total">총 {{ stats.totalJobs }}개 Job · {{ fmtRows(stats.totalRows) }} rows 이관</div>
      </div>

      <!-- 최근 활동 로그 -->
      <div class="card activity-card">
        <div class="card-header">
          <span>최근 활동</span>
          <button class="link-btn" @click="$router.push('/report')">리포트 →</button>
        </div>
        <div class="activity-list">
          <div v-if="activityLog.length === 0" class="empty-state" style="font-size:12px;padding:12px 0">
            활동 내역이 없습니다
          </div>
          <div v-for="(a,i) in activityLog" :key="i" class="activity-row">
            <div class="activity-dot" :class="a.cls"/>
            <div class="activity-body">
              <div class="activity-msg">{{ a.msg }}</div>
              <div class="activity-time">{{ a.time }}</div>
            </div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { fmtDate } from '@/utils/dateUtils.js'
import { ref, computed, onMounted } from 'vue'
import { jobsApi } from '@/api/index.js'
import { DB_META } from '@/constants/dbMeta.js'
import axios from 'axios'

const stats        = ref({ totalJobs:0, running:0, errors:0, error_job_ids:[], completedToday:0, totalRows:0, validateRate:0 })
const recentJobs   = ref([])
const loadingJobs  = ref(false)
const connStatus   = ref([])
const checkingHealth = ref(false)
const activityLog  = ref([])

const m = t => DB_META[t] || { label:'??', bg:'#eee', color:'#333' }

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6)  return '새벽이네요'
  if (h < 12) return '좋은 아침입니다'
  if (h < 18) return '좋은 오후입니다'
  return '좋은 저녁입니다'
})

const nowStr = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getDate()).padStart(2,'0')}`
})

const kpis = computed(() => [
  {
    label: '전체 Job',
    val: stats.value.totalJobs,
    icon: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" style="width:18px;height:18px"><rect x="3" y="3" width="14" height="14" rx="2"/><line x1="7" y1="8" x2="13" y2="8"/><line x1="7" y1="12" x2="11" y2="12"/></svg>',
    cls: '',
    to: '/jobs'
  },
  {
    label: '실행 중',
    val: stats.value.running,
    icon: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" style="width:18px;height:18px"><circle cx="10" cy="10" r="7"/><polygon points="8,7 14,10 8,13" fill="currentColor" stroke="none"/></svg>',
    cls: stats.value.running > 0 ? 'running' : '',
    to: '/monitor'
  },
  {
    label: '오류',
    val: stats.value.errors,
    icon: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" style="width:18px;height:18px"><circle cx="10" cy="10" r="7"/><line x1="10" y1="7" x2="10" y2="11"/><circle cx="10" cy="13.5" r=".8" fill="currentColor"/></svg>',
    cls: stats.value.errors > 0 ? 'err' : '',
    to: stats.value.errors > 0 ? '/monitor?filter=error' : null
  },
  {
    label: '오늘 완료',
    val: stats.value.completedToday,
    icon: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" style="width:18px;height:18px"><circle cx="10" cy="10" r="7"/><polyline points="7,10 9,12 13,8"/></svg>',
    cls: 'ok',
    to: null
  },
])

const statusBars = computed(() => {
  const total = stats.value.totalJobs || 1
  return [
    { label:'완료', count: stats.value.completedToday, pct: Math.round(stats.value.completedToday/total*100), cls:'ok' },
    { label:'실행중', count: stats.value.running, pct: Math.round(stats.value.running/total*100), cls:'run' },
    { label:'오류', count: stats.value.errors, pct: Math.round(stats.value.errors/total*100), cls:'err' },
  ]
})

const pillCls  = s => ({ running:'pill-run', completed:'pill-ok', error:'pill-err', paused:'pill-warn' }[s] || 'pill-idle')
const statusLbl = s => ({ running:'실행 중', completed:'완료', error:'오류', paused:'일시정지' }[s] || s)

const fmtRows = n => n >= 1e6 ? (n/1e6).toFixed(1)+'M' : n >= 1e3 ? Math.round(n/1e3)+'K' : String(n||0)

async function load() {
  loadingJobs.value = true
  try {
    const { data } = await axios.get('/api/v1/jobs/')
    const jobs = Array.isArray(data) ? data : []
    const today = new Date().toDateString()

    stats.value = {
      totalJobs: jobs.length,
      running: jobs.filter(j => j.status === 'running').length,
      errors: jobs.filter(j => j.status === 'error').length,
      error_job_ids: jobs.filter(j => j.status === 'error').map(j => j.id),
      completedToday: jobs.filter(j => j.status === 'completed' && new Date(j.finished_at||j.created_at).toDateString() === today).length,
      totalRows: jobs.reduce((s,j) => s+(j.rows_processed||0), 0),
    }

    recentJobs.value = [...jobs]
      .sort((a,b) => new Date(b.created_at||0) - new Date(a.created_at||0))
      .slice(0, 8)

    activityLog.value = recentJobs.value.slice(0, 10).map(j => ({
      msg: `${j.name} — ${statusLbl(j.status)}`,
      time: fmtDate(j.created_at),
      cls: pillCls(j.status),
    }))
  } catch(e) {
    console.error('Dashboard 로드 실패', e)
  } finally {
    loadingJobs.value = false
  }
}

async function checkHealth() {
  checkingHealth.value = true
  try {
    const src = await axios.post('/api/v1/connectors/test', {
      db_type: 'mssql', host: '127.0.0.1', port: 1433,
      database: 'crec', username: 'sa', password: 'Bridge@1234'
    }).catch(() => ({ data: { ok: false } }))
    const tgt = await axios.post('/api/v1/connectors/test', {
      db_type: 'mysql', host: '127.0.0.1', port: 3306,
      database: 'testdb', username: 'bridge', password: 'bridge1234'
    }).catch(() => ({ data: { ok: false } }))
    connStatus.value = [
      { label:'MSSQL (crec)', sub:'127.0.0.1:1433', ok: src.data?.ok },
      { label:'MySQL (testdb)', sub:'127.0.0.1:3306', ok: tgt.data?.ok },
    ]
  } finally {
    checkingHealth.value = false
  }
}

const quickLinks = [
  { label:'이관 생성', to:'/jobs/wizard', icon:'<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" style="width:16px;height:16px"><rect x="3" y="3" width="14" height="14" rx="2"/><line x1="10" y1="7" x2="10" y2="13"/><line x1="7" y1="10" x2="13" y2="10"/></svg>' },
  { label:'변경분 이관', to:'/cdc', icon:'<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" style="width:16px;height:16px"><polyline points="4,10 8,6 12,10 16,6"/><polyline points="4,14 8,10 12,14 16,10"/></svg>' },
  { label:'모니터', to:'/monitor', icon:'<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" style="width:16px;height:16px"><rect x="2" y="3" width="16" height="11" rx="1"/><line x1="7" y1="17" x2="13" y2="17"/><line x1="10" y1="14" x2="10" y2="17"/></svg>' },
  { label:'스케줄', to:'/schedule', icon:'<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" style="width:16px;height:16px"><rect x="3" y="3" width="14" height="14" rx="1"/><line x1="3" y1="8" x2="17" y2="8"/><line x1="8" y1="2" x2="8" y2="5"/><line x1="12" y1="2" x2="12" y2="5"/></svg>' },
]

onMounted(async () => {
  await load()
  await checkHealth()
})
</script>

<style scoped>
.dashboard { display:flex; flex-direction:column; gap:16px; }
.dash-header { display:flex; align-items:flex-start; justify-content:space-between; }
.page-title { font-size:1.3rem; font-weight:600; color:var(--text-primary); }
.page-desc  { font-size:.8rem; color:var(--text-tertiary); margin-top:2px; }
.refresh-btn { background:transparent; border:0.5px solid var(--border-mid); border-radius:6px; padding:6px 8px; cursor:pointer; color:var(--text-secondary); display:flex; align-items:center; }
.refresh-btn:hover { background:var(--bg-secondary); }
.spinning { animation: spin .8s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }

.kpi-row { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }
.kpi-card { background:var(--bg-primary); border:0.5px solid var(--border-light); border-radius:10px; padding:14px 16px; display:flex; flex-direction:column; gap:6px; }
.kpi-card.kpi-clickable { cursor:pointer; }
.kpi-card.kpi-clickable:hover { box-shadow:0 4px 16px rgba(0,0,0,.12); transform:translateY(-1px); transition:all .15s; }
.kpi-card.err.kpi-clickable:hover { box-shadow:0 4px 16px rgba(239,68,68,.2); }
.kpi-top { display:flex; align-items:center; justify-content:space-between; }
.kpi-ico { color:var(--text-tertiary); }
.kpi-trend { font-size:.72rem; padding:2px 6px; border-radius:4px; }
.kpi-trend.up { background:rgba(34,197,94,.1); color:#16a34a; }
.kpi-trend.down { background:rgba(239,68,68,.1); color:#dc2626; }
.kpi-val { font-size:1.6rem; font-weight:600; color:var(--text-primary); line-height:1; }
.kpi-lbl { font-size:.75rem; color:var(--text-tertiary); }
.kpi-card.ok .kpi-val { color:#16a34a; }
.kpi-card.err .kpi-val { color:#dc2626; }
.kpi-card.running .kpi-val { color:#2563eb; }

.main-grid { display:grid; grid-template-columns:1fr 320px; gap:16px; }
.side-col { display:flex; flex-direction:column; gap:16px; }

.card { background:var(--bg-primary); border:0.5px solid var(--border-light); border-radius:10px; }
.card-header { display:flex; align-items:center; justify-content:space-between; padding:12px 16px; border-bottom:0.5px solid var(--border-light); font-size:.82rem; font-weight:600; color:var(--text-primary); }
.link-btn { font-size:.75rem; color:var(--accent-blue,#2563eb); background:transparent; border:none; cursor:pointer; padding:2px 4px; }
.link-btn:hover { text-decoration:underline; }

.job-list { padding:4px 0; }
.job-row { display:flex; align-items:center; gap:10px; padding:8px 16px; cursor:pointer; transition:background .12s; }
.job-row:hover { background:var(--bg-secondary); }
.job-db-badge { font-size:.62rem; font-weight:700; padding:2px 6px; border-radius:4px; flex-shrink:0; }
.job-info { flex:1; min-width:0; }
.job-name { font-size:.8rem; font-weight:500; color:var(--text-primary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.job-sub { font-size:.72rem; color:var(--text-tertiary); display:flex; gap:4px; margin-top:1px; }
.dot { color:var(--border-mid); }
.job-right { display:flex; flex-direction:column; align-items:flex-end; gap:3px; }
.mini-progress { display:flex; align-items:center; gap:4px; }
.mini-fill { height:3px; background:var(--accent-blue,#2563eb); border-radius:2px; transition:width .3s; }
.mini-pct { font-size:.68rem; color:var(--text-tertiary); }
.status-pill { font-size:.68rem; padding:2px 7px; border-radius:4px; font-weight:600; white-space:nowrap; }
.pill-run  { background:rgba(37,99,235,.1); color:#2563eb; }
.pill-ok   { background:rgba(34,197,94,.1); color:#16a34a; }
.pill-err  { background:rgba(239,68,68,.1); color:#dc2626; }
.pill-warn { background:rgba(245,158,11,.1); color:#d97706; }
.pill-idle { background:var(--bg-secondary); color:var(--text-tertiary); }

.conn-list { padding:8px 0; }
.conn-item { display:flex; align-items:center; gap:10px; padding:8px 16px; }
.conn-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
.conn-dot.ok  { background:#16a34a; }
.conn-dot.err { background:#dc2626; }
.conn-info { flex:1; }
.conn-name { font-size:.8rem; font-weight:500; color:var(--text-primary); }
.conn-sub  { font-size:.7rem; color:var(--text-tertiary); }
.conn-badge { font-size:.68rem; padding:2px 7px; border-radius:4px; font-weight:600; }
.conn-badge.ok  { background:rgba(34,197,94,.1); color:#16a34a; }
.conn-badge.err { background:rgba(239,68,68,.1); color:#dc2626; }

.quick-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; padding:12px 16px; }
.quick-item { display:flex; flex-direction:column; align-items:center; gap:6px; padding:12px 8px; border:0.5px solid var(--border-light); border-radius:8px; background:transparent; cursor:pointer; font-size:.75rem; color:var(--text-secondary); transition:all .12s; font-family:var(--font); }
.quick-item:hover { background:var(--bg-secondary); color:var(--text-primary); border-color:var(--border-mid); }
.quick-ico { color:var(--text-tertiary); }

.bottom-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
.stat-bars { padding:12px 16px; }
.stat-bar-row { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
.stat-bar-label { font-size:.75rem; color:var(--text-secondary); width:40px; flex-shrink:0; }
.stat-bar-track { flex:1; height:6px; background:var(--bg-secondary); border-radius:3px; overflow:hidden; }
.stat-bar-fill { height:100%; border-radius:3px; transition:width .4s; }
.stat-bar-fill.ok  { background:#16a34a; }
.stat-bar-fill.run { background:#2563eb; }
.stat-bar-fill.err { background:#dc2626; }
.stat-bar-val { font-size:.75rem; color:var(--text-tertiary); width:24px; text-align:right; }
.stat-total { font-size:.72rem; color:var(--text-tertiary); padding:0 16px 12px; border-top:0.5px solid var(--border-light); padding-top:8px; margin-top:4px; }

.activity-list { padding:4px 0; }
.activity-row { display:flex; align-items:flex-start; gap:10px; padding:7px 16px; }
.activity-dot { width:7px; height:7px; border-radius:50%; background:var(--text-tertiary); flex-shrink:0; margin-top:4px; }
.activity-dot.pill-ok   { background:#16a34a; }
.activity-dot.pill-err  { background:#dc2626; }
.activity-dot.pill-run  { background:#2563eb; }
.activity-dot.pill-warn { background:#d97706; }
.activity-body { flex:1; }
.activity-msg  { font-size:.78rem; color:var(--text-primary); }
.activity-time { font-size:.7rem; color:var(--text-tertiary); margin-top:1px; }

.loading-state { display:flex; justify-content:center; padding:24px; }
.loading-dots { display:flex; gap:5px; }
.loading-dots span { width:6px; height:6px; border-radius:50%; background:var(--text-tertiary); animation:bounce .8s infinite alternate; }
.loading-dots span:nth-child(2) { animation-delay:.2s; }
.loading-dots span:nth-child(3) { animation-delay:.4s; }
@keyframes bounce { to { transform:translateY(-6px); opacity:.4; } }

.empty-state { display:flex; flex-direction:column; align-items:center; justify-content:center; padding:24px; gap:8px; color:var(--text-tertiary); font-size:.8rem; }

@media (max-width:900px) {
  .kpi-row { grid-template-columns:repeat(2,1fr); }
  .main-grid { grid-template-columns:1fr; }
  .bottom-grid { grid-template-columns:1fr; }
}
</style>
