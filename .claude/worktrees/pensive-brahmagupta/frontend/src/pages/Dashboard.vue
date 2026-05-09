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
      <div class="kpi-card" v-for="k in kpis" :key="k.label" :class="k.cls">
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
import { ref, computed, onMounted } from 'vue'
import { jobsApi } from '@/api/index.js'
import { DB_META } from '@/constants/dbMeta.js'
import axios from 'axios'

const stats        = ref({ totalJobs:0, running:0, errors:0, completedToday:0, totalRows:0, validateRate:0 })
const recentJobs   = ref([])
const loadingJobs  = ref(false)
const health       = ref({ api: true })
const checkingHealth = ref(false)

const m        = t => DB_META[t] || { label: '??', bg:'#eee', color:'#333' }
const fmtRows  = n => n >= 1e6 ? (n/1e6).toFixed(1)+'M' : n >= 1e3 ? Math.round(n/1e3)+'K' : String(n||0)
const pillCls  = s => ({running:'run', completed:'ok', error:'err', idle:'idle', paused:'warn', aborted:'idle'}[s]||'idle')
const statusLbl= s => ({running:'실행 중', completed:'완료', error:'오류', idle:'대기', paused:'일시정지', aborted:'중단'}[s]||s)

function fmtDate(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('ko-KR',{month:'2-digit',day:'2-digit'}) + ' ' +
           d.toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit'})
  } catch { return iso.slice(0,16) }
}

const now = ref(new Date())
setInterval(() => now.value = new Date(), 60000)

const nowStr = computed(() => now.value.toLocaleDateString('ko-KR',{year:'numeric',month:'long',day:'numeric',weekday:'short'}))
const greeting = computed(() => {
  const h = now.value.getHours()
  if (h < 6) return '🌙 야간 작업 중'
  if (h < 12) return '☀️ 좋은 아침입니다'
  if (h < 18) return '🌤 좋은 오후입니다'
  return '🌇 좋은 저녁입니다'
})

const kpis = computed(() => {
  const s = stats.value
  const total = s.totalJobs || 1
  return [
    { label:'전체 Job',     val: s.totalJobs,          cls:'info',    trend: null,
      icon:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:16px;height:16px"><rect x="2" y="3" width="12" height="10" rx="1.5"/><line x1="5" y1="7" x2="11" y2="7"/><line x1="5" y1="10" x2="8" y2="10"/></svg>' },
    { label:'실행 중',      val: s.running,            cls:'run',     trend: null,
      icon:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:16px;height:16px"><circle cx="8" cy="8" r="6"/><polygon points="6,5 12,8 6,11" fill="currentColor" stroke="none"/></svg>' },
    { label:'완료',         val: s.completedToday,     cls:'ok',      trend: null,
      icon:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:16px;height:16px"><circle cx="8" cy="8" r="6"/><polyline points="5,8 7,10 11,6"/></svg>' },
    { label:'오류',         val: s.errors,             cls: s.errors > 0 ? 'err' : '',  trend: null,
      icon:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:16px;height:16px"><circle cx="8" cy="8" r="6"/><line x1="8" y1="5" x2="8" y2="9"/><circle cx="8" cy="11" r="0.5" fill="currentColor"/></svg>' },
    { label:'이관 Rows',    val: fmtRows(s.totalRows), cls:'',        trend: null,
      icon:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:16px;height:16px"><path d="M2 12 L5 5 L8 9 L11 4 L14 8"/></svg>' },
    { label:'검증 통과율',  val: s.validateRate + '%', cls:'ok',      trend: null,
      icon:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:16px;height:16px"><path d="M8 2 L14 5 V9 C14 12 11 14 8 14 C5 14 2 12 2 9 V5 Z"/><polyline points="5.5,8 7,9.5 10.5,6"/></svg>' },
  ]
})

const statusBars = computed(() => {
  const s = stats.value
  const total = s.totalJobs || 1
  return [
    { label:'완료',    count: s.completedToday, pct: Math.round(s.completedToday/total*100), cls:'ok'  },
    { label:'실행 중', count: s.running,         pct: Math.round(s.running/total*100),        cls:'run' },
    { label:'오류',    count: s.errors,          pct: Math.round(s.errors/total*100),          cls:'err' },
    { label:'대기',    count: Math.max(0, s.totalJobs-s.completedToday-s.running-s.errors),
                       pct:  Math.max(0, Math.round((s.totalJobs-s.completedToday-s.running-s.errors)/total*100)), cls:'idle' },
  ]
})

const activityLog = computed(() => {
  return recentJobs.value.slice(0,8).map(j => ({
    msg:  `${j.name} — ${statusLbl(j.status)}`,
    time: fmtDate(j.finished_at || j.created_at),
    cls:  pillCls(j.status),
  }))
})

const connStatus = ref([
  { label:'백엔드 API', sub:'http://localhost:8000', ok: true },
  { label:'WebSocket',  sub:'ws://localhost:8000/ws', ok: true },
  { label:'스케줄러',   sub:'APScheduler', ok: true },
  { label:'데이터 저장',sub:'backend/data/', ok: true },
])

const quickLinks = [
  { label:'커넥터 관리', to:'/connector',
    icon:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:18px;height:18px"><ellipse cx="8" cy="4" rx="5.5" ry="2"/><path d="M2.5 4v4c0 1.1 2.5 2 5.5 2s5.5-.9 5.5-2V4"/><path d="M2.5 8v4c0 1.1 2.5 2 5.5 2s5.5-.9 5.5-2V8"/></svg>' },
  { label:'Job 생성',    to:'/jobs/wizard',
    icon:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:18px;height:18px"><circle cx="8" cy="8" r="6"/><line x1="8" y1="5" x2="8" y2="11"/><line x1="5" y1="8" x2="11" y2="8"/></svg>' },
  { label:'스키마 탐색', to:'/schema',
    icon:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:18px;height:18px"><rect x="1" y="3" width="14" height="10" rx="1"/><line x1="1" y1="6" x2="15" y2="6"/><line x1="5" y1="3" x2="5" y2="13"/></svg>' },
  { label:'SQL 변환기',  to:'/sql-converter',
    icon:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:18px;height:18px"><path d="M3 4h10M3 8h6M3 12h4"/><path d="M11 10l3 2-3 2"/></svg>' },
  { label:'쿼리 검증',   to:'/sql-verify',
    icon:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:18px;height:18px"><polyline points="2,9 5,12 10,5"/><circle cx="12" cy="12" r="3"/><line x1="14.1" y1="14.1" x2="16" y2="16"/></svg>' },
  { label:'실행 리포트', to:'/report',
    icon:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:18px;height:18px"><rect x="2" y="2" width="12" height="12" rx="1"/><path d="M5 11l2-4 2 3 2-5"/></svg>' },
]

async function load() {
  loadingJobs.value = true
  try {
    const [jobs, s] = await Promise.all([jobsApi.list(), jobsApi.stats()])
    recentJobs.value = [...jobs]
      .sort((a,b) => new Date(b.created_at)-new Date(a.created_at))
      .slice(0,8)
    stats.value = s
  } catch(e) { console.error(e) }
  finally { loadingJobs.value = false }
}

async function checkHealth() {
  checkingHealth.value = true
  try {
    await axios.get('/health', { timeout:3000 })
    connStatus.value[0].ok = true
  } catch {
    connStatus.value[0].ok = false
  } finally { checkingHealth.value = false }
}

onMounted(() => { load(); checkHealth() })
</script>

<style scoped>
.dashboard { display:flex; flex-direction:column; gap:14px; }

/* 헤더 */
.dash-header { display:flex; align-items:flex-start; justify-content:space-between; }
.refresh-btn { display:flex; align-items:center; gap:5px; padding:6px 12px; border-radius:var(--radius-md); border:0.5px solid var(--border-mid); background:transparent; color:var(--text-secondary); font-size:12px; font-family:var(--font); cursor:pointer; transition:all .12s; }
.refresh-btn:hover { background:var(--bg-secondary); color:var(--text-primary); }
.refresh-btn:disabled { opacity:.5; cursor:not-allowed; }
@keyframes spin { to { transform:rotate(360deg); } }
.spinning { animation:spin .8s linear infinite; }

/* KPI */
.kpi-row { display:grid; grid-template-columns:repeat(6,1fr); gap:10px; }
.kpi-card { background:var(--bg-card,var(--bg-secondary)); border:0.5px solid var(--border-light); border-radius:var(--radius-lg,12px); padding:14px 16px; transition:box-shadow .15s; }
.kpi-card:hover { box-shadow:0 2px 12px rgba(0,0,0,.08); }
.kpi-top { display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; }
.kpi-ico { color:var(--text-tertiary); opacity:.7; }
.kpi-trend { font-size:10px; font-weight:600; padding:2px 5px; border-radius:4px; }
.kpi-trend.up   { color:var(--text-success); background:var(--bg-success); }
.kpi-trend.down { color:var(--text-danger);  background:rgba(239,68,68,.1); }
.kpi-val { font-size:26px; font-weight:700; color:var(--text-primary); line-height:1; margin-bottom:4px; }
.kpi-lbl { font-size:11px; color:var(--text-tertiary); }
.kpi-card.info .kpi-val { color:var(--text-info); }
.kpi-card.ok   .kpi-val { color:var(--text-success); }
.kpi-card.err  .kpi-val { color:var(--text-danger); }
.kpi-card.run  .kpi-val { color:#f59e0b; }

/* 메인 그리드 */
.main-grid { display:grid; grid-template-columns:1fr 320px; gap:12px; align-items:start; }

/* Job 카드 */
.job-card { padding:0; overflow:hidden; }
.job-list { overflow-y:auto; max-height:340px; }
.job-row { display:flex; align-items:center; gap:10px; padding:10px 16px; border-bottom:0.5px solid var(--border-light); cursor:pointer; transition:background .1s; }
.job-row:last-child { border-bottom:none; }
.job-row:hover { background:var(--bg-secondary); }
.job-db-badge { font-size:10px; font-weight:700; padding:3px 7px; border-radius:var(--radius-sm); flex-shrink:0; }
.job-info { flex:1; min-width:0; }
.job-name { font-size:12.5px; font-weight:500; color:var(--text-primary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.job-sub { font-size:10.5px; color:var(--text-tertiary); display:flex; align-items:center; gap:4px; margin-top:2px; }
.dot { opacity:.4; }
.job-right { display:flex; align-items:center; gap:6px; flex-shrink:0; }
.mini-progress { display:flex; align-items:center; gap:4px; }
.mini-fill { height:4px; background:var(--accent-blue); border-radius:2px; min-width:2px; transition:width .3s; }
.mini-pct { font-size:10px; color:var(--text-tertiary); }

/* 상태 pill */
.status-pill { font-size:10px; font-weight:600; padding:2px 8px; border-radius:10px; }
.status-pill.ok   { background:var(--bg-success); color:var(--text-success); }
.status-pill.err  { background:rgba(239,68,68,.1); color:var(--text-danger); }
.status-pill.run  { background:rgba(245,158,11,.12); color:#d97706; }
.status-pill.warn { background:var(--bg-warning); color:var(--text-warning); }
.status-pill.idle { background:var(--bg-secondary); color:var(--text-tertiary); }

/* 우측 패널 */
.side-col { display:flex; flex-direction:column; gap:12px; }

/* 연결 상태 */
.conn-card { padding:0; overflow:hidden; }
.conn-list { padding:4px 0; }
.conn-item { display:flex; align-items:center; gap:10px; padding:8px 16px; }
.conn-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
.conn-dot.ok  { background:#4ade80; box-shadow:0 0 6px rgba(74,222,128,.4); }
.conn-dot.err { background:#f87171; box-shadow:0 0 6px rgba(248,113,113,.4); }
.conn-info { flex:1; }
.conn-name { font-size:12px; font-weight:500; color:var(--text-primary); }
.conn-sub  { font-size:10px; color:var(--text-tertiary); }
.conn-badge { font-size:10px; font-weight:600; padding:2px 7px; border-radius:8px; }
.conn-badge.ok  { background:var(--bg-success); color:var(--text-success); }
.conn-badge.err { background:rgba(239,68,68,.1); color:var(--text-danger); }

/* 빠른 이동 */
.quick-card { padding:0; overflow:hidden; }
.quick-grid { display:grid; grid-template-columns:1fr 1fr; gap:1px; background:var(--border-light); }
.quick-item { display:flex; align-items:center; gap:8px; padding:12px 14px; background:var(--bg-primary); border:none; cursor:pointer; font-size:12px; font-family:var(--font); color:var(--text-secondary); transition:all .12s; text-align:left; }
.quick-item:hover { background:var(--bg-info); color:var(--text-info); }
.quick-ico { color:var(--text-tertiary); flex-shrink:0; }
.quick-item:hover .quick-ico { color:var(--text-info); }

/* 하단 그리드 */
.bottom-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }

/* 상태 바 */
.stat-card { padding:0; overflow:hidden; }
.stat-bars { padding:14px 16px; display:flex; flex-direction:column; gap:10px; }
.stat-bar-row { display:flex; align-items:center; gap:10px; }
.stat-bar-label { font-size:11.5px; color:var(--text-secondary); width:48px; flex-shrink:0; }
.stat-bar-track { flex:1; height:6px; background:var(--bg-secondary); border-radius:3px; overflow:hidden; }
.stat-bar-fill { height:100%; border-radius:3px; transition:width .6s ease; min-width:2px; }
.stat-bar-fill.ok   { background:var(--text-success); }
.stat-bar-fill.run  { background:#f59e0b; }
.stat-bar-fill.err  { background:var(--text-danger); }
.stat-bar-fill.idle { background:var(--border-mid); }
.stat-bar-val { font-size:11px; color:var(--text-tertiary); width:24px; text-align:right; flex-shrink:0; }
.stat-total { padding:0 16px 14px; font-size:11px; color:var(--text-tertiary); border-top:0.5px solid var(--border-light); padding-top:10px; }

/* 활동 로그 */
.activity-card { padding:0; overflow:hidden; }
.activity-list { padding:8px 0; max-height:200px; overflow-y:auto; }
.activity-row { display:flex; align-items:flex-start; gap:10px; padding:8px 16px; }
.activity-dot { width:7px; height:7px; border-radius:50%; flex-shrink:0; margin-top:4px; }
.activity-dot.ok   { background:var(--text-success); }
.activity-dot.err  { background:var(--text-danger); }
.activity-dot.run  { background:#f59e0b; }
.activity-dot.idle { background:var(--border-mid); }
.activity-dot.warn { background:var(--text-warning); }
.activity-body { flex:1; min-width:0; }
.activity-msg  { font-size:12px; color:var(--text-primary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.activity-time { font-size:10.5px; color:var(--text-tertiary); margin-top:1px; }

/* 공통 */
.card-header { display:flex; align-items:center; justify-content:space-between; padding:12px 16px; border-bottom:0.5px solid var(--border-light); font-size:13px; font-weight:600; color:var(--text-primary); }
.link-btn { font-size:11.5px; color:var(--text-info); background:none; border:none; cursor:pointer; font-family:var(--font); padding:0; }
.link-btn:hover { text-decoration:underline; }
.loading-state { display:flex; justify-content:center; padding:32px; }
.loading-dots { display:flex; gap:5px; }
.loading-dots span { width:6px; height:6px; border-radius:50%; background:var(--text-tertiary); animation:dot-blink 1.2s infinite; }
.loading-dots span:nth-child(2) { animation-delay:.2s; }
.loading-dots span:nth-child(3) { animation-delay:.4s; }
@keyframes dot-blink { 0%,80%,100%{opacity:.2} 40%{opacity:1} }
.empty-state { display:flex; flex-direction:column; align-items:center; gap:8px; padding:24px; color:var(--text-tertiary); text-align:center; }
.empty-state p { font-size:12.5px; margin:0; }

@media(max-width:1100px) { .kpi-row { grid-template-columns:repeat(3,1fr); } }
@media(max-width:900px)  { .main-grid { grid-template-columns:1fr; } .bottom-grid { grid-template-columns:1fr; } }
</style>
