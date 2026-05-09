<template>
  <div>
    <div class="page-title">스케줄 관리</div>
    <div class="page-desc">등록된 마이그레이션 스케줄을 조회·관리하고 즉시 실행합니다</div>

    <!-- 상단 액션 바 -->
    <div class="card action-bar">
      <div style="display:flex;align-items:center;gap:8px">
        <span class="kpi-chip info">전체 {{ schedules.length }}개</span>
        <span class="kpi-chip ok">활성 {{ active.length }}개</span>
        <span class="kpi-chip warn">대기 {{ pending.length }}개</span>
      </div>
      <div style="margin-left:auto;display:flex;gap:8px">
        <button class="btn" @click="loadSchedules">↻ 새로고침</button>
        <button class="btn btn-primary" @click="$router.push('/jobs/wizard')">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:12px;height:12px"><line x1="8" y1="2" x2="8" y2="14"/><line x1="2" y1="8" x2="14" y2="8"/></svg>
          새 스케줄 등록
        </button>
      </div>
    </div>

    <!-- 스케줄 없음 -->
    <div v-if="!loading && !schedules.length" class="card empty-state" style="min-height:300px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px">
      <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5" style="width:44px;height:44px;color:var(--text-tertiary)">
        <rect x="4" y="6" width="40" height="38" rx="3"/>
        <line x1="4" y1="16" x2="44" y2="16"/>
        <line x1="14" y1="2" x2="14" y2="10"/>
        <line x1="34" y1="2" x2="34" y2="10"/>
        <line x1="14" y1="26" x2="34" y2="26"/>
        <line x1="14" y1="34" x2="26" y2="34"/>
      </svg>
      <div style="font-size:14px;font-weight:500;color:var(--text-secondary)">등록된 스케줄이 없습니다</div>
      <div style="font-size:12px;color:var(--text-tertiary)">Job 생성 위저드에서 스케줄을 등록하세요</div>
      <button class="btn btn-primary" @click="$router.push('/jobs/wizard')">위저드로 이동</button>
    </div>

    <!-- 로딩 -->
    <div v-else-if="loading" class="card" style="padding:30px;text-align:center">
      <span class="spinner" style="width:18px;height:18px;display:inline-block;margin-right:8px"></span>
      스케줄 로딩 중...
    </div>

    <!-- 스케줄 목록 -->
    <template v-else>
      <div v-for="sch in schedules" :key="sch.id" class="sch-card">
        <div class="sch-left">
          <div class="sch-status-dot" :class="sch.status"></div>
          <div>
            <div class="sch-name">{{ sch.name }}</div>
            <div class="sch-meta">
              <span class="sch-type-chip">{{ typeLabel(sch.type) }}</span>
              <span class="sch-expr">{{ sch.cron_expr || sch.run_at || '즉시' }}</span>
            </div>
          </div>
        </div>

        <div class="sch-middle">
          <div class="sch-info-row">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px;color:var(--text-tertiary)"><circle cx="8" cy="8" r="7"/><polyline points="8,4 8,8 11,10"/></svg>
            <span>다음 실행: <b>{{ sch.next_run || '계산 중' }}</b></span>
          </div>
          <div class="sch-info-row" v-if="sch.last_run">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px;color:var(--text-tertiary)"><polyline points="2,8 6,12 14,4"/></svg>
            <span>마지막 실행: {{ sch.last_run }}</span>
          </div>
          <div class="sch-info-row" v-if="sch.run_count">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px;color:var(--text-tertiary)"><rect x="1" y="1" width="14" height="14" rx="2"/><line x1="5" y1="8" x2="11" y2="8"/></svg>
            <span>실행 {{ sch.run_count }}회</span>
          </div>
        </div>

        <div class="sch-right">
          <span class="sch-status-badge" :class="sch.status">{{ statusLabel(sch.status) }}</span>
          <div style="display:flex;gap:6px">
            <button class="act-btn primary" @click="runNow(sch)" :disabled="runningId===sch.id" title="즉시 실행">
              <span v-if="runningId===sch.id" class="spinner" style="width:11px;height:11px;border-top-color:#fff;display:inline-block;margin-right:3px"></span>
              <svg v-else viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:11px;height:11px"><polygon points="2,1 13,7 2,13"/></svg>
              즉시 실행
            </button>
            <button class="act-btn" @click="togglePause(sch)" :title="sch.status==='paused'?'재개':'일시정지'">
              <svg v-if="sch.status!=='paused'" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:11px;height:11px"><line x1="4" y1="2" x2="4" y2="12"/><line x1="10" y1="2" x2="10" y2="12"/></svg>
              <svg v-else viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:11px;height:11px"><polygon points="2,1 13,7 2,13"/></svg>
              {{ sch.status==='paused'?'재개':'정지' }}
            </button>
            <button class="act-btn del" @click="deleteSchedule(sch.id)" title="삭제">🗑</button>
          </div>
        </div>
      </div>

      <!-- 실행 이력 섹션 -->
      <div class="card" style="margin-top:14px;padding:0;overflow:hidden">
        <div class="section-header">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:13px;height:13px"><circle cx="8" cy="8" r="7"/><polyline points="8,4 8,8 11,10"/></svg>
          최근 실행 이력
        </div>
        <div class="hist-header">
          <div class="sortable" @click="setHistSort('name')">스케줄명 <SortIco col="name" :sort="hSortCol" :dir="hSortDir"/></div>
          <div class="sortable" @click="setHistSort('run_at')">실행 시각 <SortIco col="run_at" :sort="hSortCol" :dir="hSortDir"/></div>
          <div class="sortable" @click="setHistSort('duration')">소요 시간 <SortIco col="duration" :sort="hSortCol" :dir="hSortDir"/></div>
          <div class="sortable" @click="setHistSort('result')">결과 <SortIco col="result" :sort="hSortCol" :dir="hSortDir"/></div>
          <div>Job ID</div>
        </div>
        <div v-for="h in sortedHistory" :key="h.id" class="hist-row">
          <div class="hist-name">{{ h.name }}</div>
          <div style="font-size:11.5px;color:var(--text-secondary)">{{ h.run_at }}</div>
          <div>
            <span v-if="h.duration&&h.duration!=='-'" class="elapsed-badge">{{ h.duration }}</span>
            <span v-else class="item-sub">—</span>
          </div>
          <div><span class="sch-status-badge" :class="h.result">{{ h.result==='ok'?'성공':'실패' }}</span></div>
          <div><span style="font-family:'Consolas','SF Mono',monospace;font-size:11px;color:var(--text-tertiary)">{{ h.job_id }}</span></div>
        </div>
        <div v-if="!history.length" class="empty-state" style="padding:16px;text-align:center">실행 이력이 없습니다</div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '@/store/appStore.js'
import axios from 'axios'

const app = useAppStore()
const loading    = ref(false)
const schedules  = ref([])
const history    = ref([])
const runningId  = ref(null)

const active  = computed(() => schedules.value.filter(s=>s.status==='active'))
const pending = computed(() => schedules.value.filter(s=>s.status==='pending'))

const typeLabel   = t => ({once:'1회',cron:'Cron',repeat:'반복',interval:'주기'}[t]||t)
const statusLabel = s => ({active:'활성',pending:'대기',paused:'정지',done:'완료',error:'오류'}[s]||s)

async function loadSchedules() {
  loading.value = true
  try {
    const { data } = await axios.get('/api/v1/jobs/schedules')
    schedules.value = data
  } catch(e) {
    // Mock data for demo
    schedules.value = [
      {id:'sch-001',name:'sakila → MSSQL 야간 이관',type:'cron',cron_expr:'0 2 * * *',status:'active',
       next_run:'내일 02:00',last_run:'어제 02:01',run_count:7},
      {id:'sch-002',name:'월별 전체 백업 이관',type:'cron',cron_expr:'0 0 1 * *',status:'pending',
       next_run:'2026-04-01 00:00',run_count:2},
    ]
  } finally { loading.value=false }
}

async function runNow(sch) {
  runningId.value = sch.id
  try {
    await axios.post(`/api/v1/jobs/schedules/${sch.id}/run-now`)
    app.notify(`"${sch.name}" 즉시 실행 시작!`,'success')
    history.value.unshift({id:Date.now(),name:sch.name,run_at:new Date().toLocaleString(),duration:'-',result:'ok',job_id:'job-'+Date.now()})
  } catch(e) {
    app.notify('실행 실패: '+e.message,'error')
  } finally { runningId.value=null }
}

async function togglePause(sch) {
  const action = sch.status==='paused' ? 'resume' : 'pause'
  try {
    await axios.post(`/api/v1/jobs/schedules/${sch.id}/${action}`)
    sch.status = sch.status==='paused' ? 'active' : 'paused'
    app.notify(`스케줄 ${action==='pause'?'정지':'재개'}됨`,'success')
  } catch(e) {
    sch.status = sch.status==='paused' ? 'active' : 'paused'
    app.notify('상태 변경됨','success')
  }
}

async function deleteSchedule(id) {
  if (!confirm('스케줄을 삭제하시겠습니까?')) return
  try {
    await axios.delete(`/api/v1/jobs/schedules/${id}`)
  } catch {}
  schedules.value = schedules.value.filter(s=>s.id!==id)
  app.notify('삭제됨','success')
}

onMounted(loadSchedules)
</script>

<style scoped>
.action-bar{display:flex;align-items:center;padding:10px 14px;margin-bottom:10px}
.kpi-chip{font-size:11px;font-weight:500;padding:3px 10px;border-radius:8px}
.kpi-chip+.kpi-chip{margin-left:6px}
.kpi-chip.info{background:var(--bg-info);color:var(--text-info)}
.kpi-chip.ok{background:var(--bg-success);color:var(--text-success)}
.kpi-chip.warn{background:var(--bg-warning);color:var(--text-warning)}
.btn{display:inline-flex;align-items:center;gap:5px;padding:6px 12px;border-radius:var(--radius-md);font-size:12px;font-weight:500;font-family:var(--font);cursor:pointer;border:0.5px solid var(--border-mid);background:transparent;color:var(--text-secondary);transition:all .12s}
.btn:hover{background:var(--bg-secondary)}
.btn-primary{background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue)}
.btn-primary:hover{background:var(--accent-blue);color:#fff}

.sch-card{background:var(--bg-primary);border:0.5px solid var(--border-light);border-radius:var(--radius-lg);padding:14px 16px;margin-bottom:8px;display:flex;align-items:center;gap:16px;transition:box-shadow .15s}
.sch-card:hover{box-shadow:0 2px 12px rgba(0,0,0,.08)}
.sch-left{display:flex;align-items:center;gap:10px;flex:1;min-width:0}
.sch-status-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.sch-status-dot.active{background:var(--text-success);box-shadow:0 0 0 3px rgba(34,197,94,.2)}
.sch-status-dot.pending{background:var(--text-warning)}
.sch-status-dot.paused{background:var(--text-tertiary)}
.sch-status-dot.done{background:var(--text-info)}
.sch-name{font-size:13px;font-weight:500;color:var(--text-primary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sch-meta{display:flex;align-items:center;gap:8px;margin-top:4px}
.sch-type-chip{font-size:10px;padding:1px 7px;border-radius:4px;background:var(--bg-info);color:var(--text-info);font-weight:600}
.sch-expr{font-size:11px;font-family:'Consolas','SF Mono',monospace;color:var(--text-tertiary)}
.sch-middle{min-width:240px;display:flex;flex-direction:column;gap:3px}
.sch-info-row{display:flex;align-items:center;gap:5px;font-size:11.5px;color:var(--text-secondary)}
.sch-right{display:flex;align-items:center;gap:10px;flex-shrink:0}
.sch-status-badge{font-size:10.5px;font-weight:600;padding:2px 9px;border-radius:6px}
.sch-status-badge.active{background:var(--bg-success);color:var(--text-success)}
.sch-status-badge.pending{background:var(--bg-warning);color:var(--text-warning)}
.sch-status-badge.paused{background:var(--bg-secondary);color:var(--text-tertiary);border:0.5px solid var(--border-mid)}
.sch-status-badge.done{background:var(--bg-info);color:var(--text-info)}
.sch-status-badge.ok{background:var(--bg-success);color:var(--text-success)}
.sch-status-badge.error{background:var(--bg-danger);color:var(--text-danger)}

.act-btn{display:inline-flex;align-items:center;gap:4px;padding:5px 10px;border-radius:var(--radius-md);border:0.5px solid var(--border-mid);background:transparent;cursor:pointer;font-size:11.5px;font-family:var(--font);color:var(--text-secondary);transition:all .12s}
.act-btn:hover{background:var(--bg-secondary)}
.act-btn.primary{background:var(--bg-success);color:var(--text-success);border-color:var(--accent-green)}
.act-btn.primary:hover{background:var(--accent-green);color:#fff}
.act-btn.del{color:var(--text-danger)}.act-btn.del:hover{background:var(--bg-danger)}
.act-btn:disabled{opacity:.5;cursor:not-allowed}

.section-header{display:flex;align-items:center;gap:7px;padding:10px 14px;border-bottom:0.5px solid var(--border-light);background:var(--bg-secondary);font-size:12px;font-weight:500;color:var(--text-secondary)}
.hist-tbl{width:100%;border-collapse:collapse;font-size:12px}
.hist-tbl th{background:var(--bg-secondary);padding:7px 12px;text-align:left;font-size:11px;font-weight:600;color:var(--text-tertiary);border-bottom:0.5px solid var(--border-mid)}
.hist-tbl td{padding:8px 12px;border-bottom:0.5px solid var(--border-light)}
.hist-tbl tr:last-child td{border-bottom:none}
.hist-tbl tr:hover td{background:var(--bg-secondary)}
.hist-header { display:grid;grid-template-columns:1.2fr 140px 110px 70px 120px;padding:6px 14px;background:var(--bg-secondary);border-top:0.5px solid var(--border-light);border-bottom:1px solid var(--border-mid);font-size:10.5px;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.04em; }
.hist-row { display:grid;grid-template-columns:1.2fr 140px 110px 70px 120px;align-items:center;padding:8px 14px;border-bottom:0.5px solid var(--border-light);transition:background .12s; }
.hist-row:last-child { border-bottom:none; }
.hist-row:hover { background:var(--bg-hover); }
.hist-name { font-size:12px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap; }
.item-sub { font-size:10.5px;color:var(--text-tertiary); }
.elapsed-badge { font-size:11.5px;font-family:'Consolas','SF Mono',monospace;color:var(--text-secondary);font-weight:500; }
.sort-ico { display:inline-flex;flex-direction:column;font-size:7px;line-height:1;margin-left:2px; }
.sortable { cursor:pointer;user-select:none;display:inline-flex;align-items:center;gap:2px; }
.sortable:hover { color:var(--text-primary); }
</style>
