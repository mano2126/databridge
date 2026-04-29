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
      <div style="margin-left:auto;display:flex;align-items:center;gap:8px">
        <template v-if="selected.size > 0">
          <span style="font-size:12px;color:var(--text-secondary)">{{ selected.size }}개 선택됨</span>
          <button class="btn btn-danger" @click="deleteSelected">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:11px;height:11px"><polyline points="2,4 12,4"/><path d="M5,4V2h4v2"/><rect x="3" y="4" width="8" height="8" rx="1"/></svg>
            선택 삭제
          </button>
        </template>
        <button class="btn" @click="loadSchedules">↻ 새로고침</button>
        <button class="btn btn-primary" @click="$router.push('/jobs/wizard')">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:12px;height:12px"><line x1="8" y1="2" x2="8" y2="14"/><line x1="2" y1="8" x2="14" y2="8"/></svg>
          새 스케줄 등록
        </button>
      </div>
    </div>

    <!-- 빈 상태 -->
    <div v-if="!loading && !schedules.length" class="card empty-state">
      <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5" style="width:44px;height:44px;color:var(--text-tertiary)">
        <rect x="4" y="6" width="40" height="38" rx="3"/><line x1="4" y1="16" x2="44" y2="16"/>
        <line x1="14" y1="2" x2="14" y2="10"/><line x1="34" y1="2" x2="34" y2="10"/>
        <line x1="14" y1="26" x2="34" y2="26"/><line x1="14" y1="34" x2="26" y2="34"/>
      </svg>
      <div style="font-size:14px;font-weight:500;color:var(--text-secondary)">등록된 스케줄이 없습니다</div>
      <div style="font-size:12px;color:var(--text-tertiary)">Job 생성 위저드에서 스케줄을 등록하세요</div>
      <button class="btn btn-primary" @click="$router.push('/jobs/wizard')">위저드로 이동</button>
    </div>

    <!-- 스케줄 테이블 -->
    <div v-else-if="schedules.length" class="card tbl-wrap">
      <table class="sch-tbl">
        <colgroup>
          <col style="width:36px"><col><col style="width:72px">
          <col style="width:155px"><col style="width:145px">
          <col style="width:145px"><col style="width:68px"><col style="width:190px">
        </colgroup>
        <thead>
          <tr>
            <th class="th-chk">
              <div class="chk-wrap" @click="toggleAll">
                <span class="chk-icon" :class="{checked:allSel, partial:selected.size>0&&!allSel}">
                  <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline v-if="allSel" points="2,6 5,9 10,3"/>
                    <line v-else-if="selected.size>0" x1="2" y1="6" x2="10" y2="6"/>
                  </svg>
                </span>
              </div>
            </th>
            <th class="th-sort" @click="setSort('name')">스케줄명 <SortIco col="name" :cur="sortCol" :dir="sortDir"/></th>
            <th class="th-sort" @click="setSort('type')">유형 <SortIco col="type" :cur="sortCol" :dir="sortDir"/></th>
            <th class="th-sort" @click="setSort('run_at')">실행 시각/주기 <SortIco col="run_at" :cur="sortCol" :dir="sortDir"/></th>
            <th class="th-sort" @click="setSort('next_run')">다음 실행 <SortIco col="next_run" :cur="sortCol" :dir="sortDir"/></th>
            <th class="th-sort" @click="setSort('last_run')">마지막 실행 <SortIco col="last_run" :cur="sortCol" :dir="sortDir"/></th>
            <th class="th-sort" @click="setSort('status')">상태 <SortIco col="status" :cur="sortCol" :dir="sortDir"/></th>
            <th>작업</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="sch in sorted" :key="sch.id"
              :class="{'row-sel': selected.has(sch.id), 'row-expired': sch.status==='expired'}"
              @click.exact="toggleOne(sch.id)">
            <td class="td-chk" @click.stop="toggleOne(sch.id)">
              <div class="chk-wrap">
                <span class="chk-icon" :class="{checked: selected.has(sch.id)}">
                  <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline v-if="selected.has(sch.id)" points="2,6 5,9 10,3"/>
                  </svg>
                </span>
              </div>
            </td>
            <td>
              <div class="sch-name">{{ sch.name }}</div>
              <div class="sch-id">{{ sch.id }}</div>
            </td>
            <td><span class="type-chip" :class="sch.type">{{ typeLabel(sch.type) }}</span>
              <span v-if="isCdc(sch)" class="cdc-sch-badge">CDC</span></td>
            <td>
              <span v-if="sch.cron_expr" class="expr-txt">{{ sch.cron_expr }}</span>
              <span v-else-if="sch.run_at" class="expr-txt">{{ fmtDateTime(sch.run_at) }}</span>
              <span v-else class="text-dim">즉시</span>
            </td>
            <td>
              <span v-if="sch.type!=='once' && sch.next_run" class="next-run">{{ fmtDateTime(sch.next_run) }}</span>
              <span v-else class="text-dim">—</span>
            </td>
            <td><span v-if="sch.last_run" style="font-size:11.5px">{{ fmtDateTime(sch.last_run) }}</span><span v-else class="text-dim">—</span></td>
            <td><span class="status-badge" :class="sch.status">{{ statusLabel(sch.status) }}</span></td>
            <td @click.stop>
              <div class="act-group">
                <button class="act-btn run" @click="runNow(sch)" :disabled="runningId===sch.id">
                  <span v-if="runningId===sch.id" class="spinner" style="width:9px;height:9px;display:inline-block"></span>
                  <svg v-else viewBox="0 0 10 10" fill="currentColor" style="width:9px;height:9px"><polygon points="1,1 9,5 1,9"/></svg>
                  즉시
                </button>
                <button class="act-btn" @click="togglePause(sch)">
                  <svg v-if="sch.status!=='paused'" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.8" style="width:9px;height:9px"><line x1="2" y1="1" x2="2" y2="9"/><line x1="8" y1="1" x2="8" y2="9"/></svg>
                  <svg v-else viewBox="0 0 10 10" fill="currentColor" style="width:9px;height:9px"><polygon points="1,1 9,5 1,9"/></svg>
                  {{ sch.status==='paused' ? '재개' : '정지' }}
                </button>
                <button class="act-btn del" @click="deleteSchedule(sch.id)">
                  <svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5" style="width:9px;height:9px"><polyline points="1,3 9,3"/><path d="M3,3V2h4v1"/><rect x="1.5" y="3" width="7" height="6" rx="1"/></svg>
                  삭제
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 실행 이력 -->
    <div class="card" style="margin-top:14px;padding:0;overflow:hidden">
      <div class="section-header">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:13px;height:13px"><circle cx="8" cy="8" r="7"/><polyline points="8,4 8,8 11,10"/></svg>
        최근 실행 이력
        <span v-if="history.length" style="margin-left:8px;font-size:11px;color:var(--text-tertiary);font-weight:500">({{ history.length }}건)</span>
        <span style="margin-left:auto;display:flex;align-items:center;gap:6px">
          <label style="font-size:11px;color:var(--text-tertiary)">페이지당</label>
          <select v-model.number="histPageSize" @change="histPage=1"
                  style="font-size:11px;padding:3px 22px 3px 6px">
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
          </select>
        </span>
      </div>
      <table class="sch-tbl">
        <colgroup><col><col style="width:150px"><col style="width:100px"><col style="width:100px"><col style="width:70px"><col style="width:140px"></colgroup>
        <thead>
          <tr>
            <th class="th-sort" @click="setHistSort('name')">스케줄명 <SortIco col="name" :cur="histSortCol" :dir="histSortDir"/></th>
            <th class="th-sort" @click="setHistSort('run_at')">실행 시각 <SortIco col="run_at" :cur="histSortCol" :dir="histSortDir"/></th>
            <th class="th-sort" @click="setHistSort('duration_sec')">소요 시간 <SortIco col="duration_sec" :cur="histSortCol" :dir="histSortDir"/></th>
            <th class="th-sort" @click="setHistSort('rows')">처리 rows <SortIco col="rows" :cur="histSortCol" :dir="histSortDir"/></th>
            <th class="th-sort" @click="setHistSort('result')">결과 <SortIco col="result" :cur="histSortCol" :dir="histSortDir"/></th>
            <th>Job ID</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!history.length"><td colspan="6" style="text-align:center;padding:20px;color:var(--text-tertiary)">실행 이력이 없습니다</td></tr>
          <tr v-for="h in pagedHistory" :key="h.id">
            <td>{{ h.name }}</td>
            <td style="color:var(--text-secondary);font-size:11.5px">{{ fmtDateTime(h.run_at) }}</td>
            <td><span v-if="h.duration&&h.duration!=='-'" style="font-family:'Consolas',monospace;font-size:11.5px">{{ h.duration }}</span><span v-else class="text-dim">—</span></td>
            <td style="font-family:'Consolas',monospace;font-size:11.5px;color:var(--text-secondary)">
              <span v-if="h.rows">{{ (h.rows||0).toLocaleString() }}</span><span v-else class="text-dim">—</span>
              <span v-if="h.errors" style="color:var(--text-danger);font-weight:600"> ✕{{ h.errors }}</span>
            </td>
            <td><span class="status-badge" :class="h.result==='ok' ? 'active' : (h.result==='running' ? 'waiting' : 'error')">{{ h.result==='ok'?'성공' : (h.result==='running' ? '진행중' : '실패') }}</span></td>
            <td style="font-family:'Consolas','SF Mono',monospace;font-size:11px;color:var(--text-tertiary)">{{ String(h.job_id||'').slice(0,12) }}</td>
          </tr>
        </tbody>
      </table>
      <!-- 페이지네이션 -->
      <div v-if="histTotalPages > 1" class="hist-pagination">
        <button class="pg-btn" :disabled="histPage===1" @click="histPage=1">«</button>
        <button class="pg-btn" :disabled="histPage===1" @click="histPage--">‹</button>
        <button v-for="p in histPageNums" :key="p"
                class="pg-btn" :class="{active: p===histPage}" @click="histPage=p">{{ p }}</button>
        <button class="pg-btn" :disabled="histPage===histTotalPages" @click="histPage++">›</button>
        <button class="pg-btn" :disabled="histPage===histTotalPages" @click="histPage=histTotalPages">»</button>
        <span class="pg-info">{{ histPage }} / {{ histTotalPages }}</span>
      </div>
    </div>
  </div>
</template>

<script>
const SortIco = {
  props: ['col','cur','dir'],
  template: `<span class="sort-ico" :class="{active: col===cur}">
    <svg viewBox="0 0 10 14" fill="none" stroke="currentColor" stroke-width="1.6" style="width:8px;height:11px">
      <polyline :stroke="col===cur&&dir==='asc'?'var(--accent-blue)':'currentColor'" points="1,6 5,1 9,6"/>
      <polyline :stroke="col===cur&&dir==='desc'?'var(--accent-blue)':'currentColor'" points="1,8 5,13 9,8"/>
    </svg>
  </span>`
}
</script>

<script setup>
import { fmtDateTime, fmtLocale } from '@/utils/dateUtils.js'
import { ref, computed, reactive, onMounted, onBeforeUnmount } from 'vue'
import { useAppStore } from '@/store/appStore.js'
import axios from 'axios'

const app       = useAppStore()
const loading   = ref(false)
const schedules = ref([])
const history   = ref([])
const runningId = ref(null)
const selected  = reactive(new Set())
const sortCol   = ref('status')
const sortDir   = ref('asc')

const active  = computed(() => schedules.value.filter(s => s.status === 'active'))
const pending = computed(() => schedules.value.filter(s => ['pending','waiting'].includes(s.status)))
const allSel  = computed(() => schedules.value.length > 0 && selected.size === schedules.value.length)

const typeLabel   = t => ({ once:'1회', cron:'Cron', repeat:'반복', interval:'주기' }[t] || t)
const isCdc = s => s.job_type === 'cdc'
const statusLabel = s => ({ active:'활성', pending:'대기', waiting:'대기', paused:'정지', done:'완료', error:'오류', expired:'만료' }[s] || s)

const sorted = computed(() => {
  return [...schedules.value].sort((a, b) => {
    let va = a[sortCol.value] ?? '', vb = b[sortCol.value] ?? ''
    if (typeof va === 'string') va = va.toLowerCase()
    if (typeof vb === 'string') vb = vb.toLowerCase()
    return sortDir.value === 'asc' ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1)
  })
})

// v9 #63e: 이력 정렬/페이징
const histSortCol  = ref('run_at')
const histSortDir  = ref('desc')
const histPage     = ref(1)
const histPageSize = ref(10)

function setHistSort(col) {
  if (histSortCol.value === col) histSortDir.value = histSortDir.value === 'asc' ? 'desc' : 'asc'
  else { histSortCol.value = col; histSortDir.value = col === 'run_at' ? 'desc' : 'asc' }
  histPage.value = 1
}

// duration 문자열 → 초로 변환 (정렬용)
function _durationToSec(dur) {
  if (!dur || dur === '-') return 0
  let sec = 0
  const h = dur.match(/(\d+)\s*시간/); if (h) sec += parseInt(h[1]) * 3600
  const m = dur.match(/(\d+)\s*분/);   if (m) sec += parseInt(m[1]) * 60
  const s = dur.match(/(\d+)\s*초/);   if (s) sec += parseInt(s[1])
  return sec
}

const sortedHistory = computed(() => {
  const list = [...history.value].map(h => ({
    ...h, _duration_sec: _durationToSec(h.duration || ''),
  }))
  const col = histSortCol.value, dir = histSortDir.value
  list.sort((a, b) => {
    let va, vb
    if (col === 'run_at') { va = new Date(a.run_at || 0); vb = new Date(b.run_at || 0) }
    else if (col === 'duration_sec') { va = a._duration_sec; vb = b._duration_sec }
    else if (col === 'rows') { va = Number(a.rows||0); vb = Number(b.rows||0) }
    else if (col === 'result') {
      const order = { ok: 0, running: 1, error: 2 }
      va = order[a.result] ?? 9; vb = order[b.result] ?? 9
    }
    else {
      va = String(a[col] ?? '').toLowerCase()
      vb = String(b[col] ?? '').toLowerCase()
    }
    return dir === 'desc' ? (va > vb ? -1 : va < vb ? 1 : 0)
                          : (va < vb ? -1 : va > vb ? 1 : 0)
  })
  return list
})
const histTotalPages = computed(() => Math.max(1, Math.ceil(sortedHistory.value.length / histPageSize.value)))
const pagedHistory = computed(() => {
  const s = (histPage.value - 1) * histPageSize.value
  return sortedHistory.value.slice(s, s + histPageSize.value)
})
const histPageNums = computed(() => {
  const t = histTotalPages.value, c = histPage.value, d = 2, r = []
  for (let i = Math.max(1,c-d); i <= Math.min(t,c+d); i++) r.push(i)
  return r
})

function setSort(col) {
  if (sortCol.value === col) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else { sortCol.value = col; sortDir.value = 'asc' }
}
function toggleOne(id) { selected.has(id) ? selected.delete(id) : selected.add(id) }
function toggleAll()   { allSel.value ? selected.clear() : schedules.value.forEach(s => selected.add(s.id)) }

async function loadSchedules() {
  loading.value = true
  try {
    const { data } = await axios.get('/api/v1/jobs/schedules')
    schedules.value = data
  } catch(e) { app.notify('스케줄 조회 실패', 'error') }
  finally { loading.value = false }
  // v9 #63d: 실행 이력도 같이 로드
  loadHistory()
}

async function loadHistory() {
  try {
    const { data } = await axios.get('/api/v1/jobs/schedules/history', { params: { limit: 50 } })
    history.value = data || []
  } catch (e) {
    // 실패해도 UI 유지 (빈 목록)
    console.warn('실행 이력 조회 실패:', e?.message || e)
  }
}

async function runNow(sch) {
  runningId.value = sch.id
  try {
    await axios.post(`/api/v1/jobs/schedules/${sch.id}/run-now`)
    app.notify(`"${sch.name}" 즉시 실행 시작!`, 'success')
    // v9 #63d: 가짜 이력 주입 제거 — 백엔드에서 진짜 이력 조회
    // 조금 기다렸다가 이력 갱신 (실행이 jobs store 에 들어갈 시간)
    setTimeout(() => loadHistory(), 800)
  } catch(e) { app.notify('실행 실패: ' + e.message, 'error') }
  finally { runningId.value = null }
}

async function togglePause(sch) {
  const action = sch.status === 'paused' ? 'resume' : 'pause'
  try {
    await axios.patch(`/api/v1/jobs/schedules/${sch.id}/${action}`)
    sch.status = sch.status === 'paused' ? 'active' : 'paused'
    app.notify(`스케줄 ${action === 'pause' ? '정지' : '재개'}됨`, 'success')
  } catch { app.notify('상태 변경됨', 'success') }
}

async function deleteSelected() {
  if (!selected.size || !confirm(`선택한 스케줄 ${selected.size}개를 삭제할까요?`)) return
  let ok = 0
  for (const id of [...selected]) {
    try { await axios.delete(`/api/v1/jobs/schedules/${id}`); ok++ }
    catch { app.notify('삭제 실패: ' + id, 'error') }
  }
  selected.clear()
  app.notify(`${ok}개 삭제 완료`, 'success')
  await loadSchedules()
}

async function deleteSchedule(id) {
  if (!confirm('스케줄을 삭제하시겠습니까?')) return
  try { await axios.delete(`/api/v1/jobs/schedules/${id}`) } catch {}
  schedules.value = schedules.value.filter(s => s.id !== id)
  selected.delete(id)
  app.notify('삭제됨', 'success')
}

// v9 #63d: 5초마다 자동 갱신 — 스케줄 상태와 이력 같이
let _refreshTimer = null
onMounted(() => {
  loadSchedules()
  _refreshTimer = setInterval(() => {
    loadSchedules()
  }, 5000)
})
onBeforeUnmount(() => {
  if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null }
})
</script>

<style scoped>
.page-title{font-size:18px;font-weight:700;color:var(--text-primary);margin-bottom:4px}
.page-desc{font-size:12.5px;color:var(--text-tertiary);margin-bottom:14px}
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
.btn-danger{background:rgba(239,68,68,.08);color:#dc2626;border-color:rgba(239,68,68,.2)}
.btn-danger:hover{background:rgba(239,68,68,.15)}
.empty-state{min-height:280px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px}
.tbl-wrap{padding:0;overflow:hidden}
.sch-tbl{width:100%;border-collapse:collapse;font-size:12px}
.sch-tbl th{background:var(--bg-secondary);padding:8px 10px;text-align:left;font-size:11px;font-weight:600;color:var(--text-tertiary);border-bottom:1px solid var(--border-mid);white-space:nowrap}
.sch-tbl td{padding:8px 10px;border-bottom:0.5px solid var(--border-light);vertical-align:middle}
.sch-tbl tr:last-child td{border-bottom:none}
.sch-tbl tbody tr:hover td{background:var(--bg-secondary)}
.sch-tbl tbody tr.row-sel td{background:rgba(59,130,246,.05)}
.sch-tbl tbody tr.row-expired td{opacity:.55}
.th-sort{cursor:pointer;user-select:none}.th-sort:hover{color:var(--text-primary)}
.th-chk,.td-chk{width:36px;text-align:center;cursor:pointer}
.chk-wrap{display:flex;align-items:center;justify-content:center}
.chk-icon{width:15px;height:15px;border-radius:4px;border:1.5px solid var(--border-mid);background:var(--bg-primary);display:flex;align-items:center;justify-content:center;transition:all .1s;color:transparent}
.chk-icon.checked{background:var(--accent-blue);border-color:var(--accent-blue);color:#fff}
.chk-icon.partial{background:var(--bg-info);border-color:var(--accent-blue);color:var(--accent-blue)}
.sch-name{font-size:12.5px;font-weight:500;color:var(--text-primary)}
.sch-id{font-size:10px;color:var(--text-tertiary);font-family:'Consolas','SF Mono',monospace;margin-top:2px}
.expr-txt{font-family:'Consolas','SF Mono',monospace;font-size:11px;color:var(--text-secondary)}
.next-run{font-size:11.5px;color:var(--text-info);font-weight:500}
.text-dim{color:var(--text-tertiary)}
.type-chip{font-size:10px;padding:2px 7px;border-radius:4px;font-weight:600}
.type-chip.once{background:var(--bg-info);color:var(--text-info)}
.type-chip.cron{background:rgba(139,92,246,.1);color:#6d28d9}
.type-chip.interval{background:var(--bg-success);color:var(--text-success)}
.cdc-sch-badge{font-size:.62rem;padding:1px 5px;border-radius:3px;background:rgba(124,58,237,.1);color:#7c3aed;font-weight:700;margin-left:4px}
.type-chip.repeat{background:var(--bg-warning);color:var(--text-warning)}
.status-badge{font-size:10.5px;font-weight:600;padding:2px 8px;border-radius:6px}
.status-badge.active{background:var(--bg-success);color:var(--text-success)}
.status-badge.pending,.status-badge.waiting{background:var(--bg-warning);color:var(--text-warning)}
.status-badge.paused{background:var(--bg-secondary);color:var(--text-tertiary);border:0.5px solid var(--border-mid)}
.status-badge.done{background:var(--bg-info);color:var(--text-info)}
.status-badge.error{background:var(--bg-danger);color:var(--text-danger)}
.status-badge.expired{background:var(--bg-secondary);color:var(--text-tertiary)}
.act-group{display:flex;gap:4px;flex-wrap:nowrap}
.act-btn{display:inline-flex;align-items:center;gap:3px;padding:4px 8px;border-radius:5px;border:0.5px solid var(--border-mid);background:transparent;cursor:pointer;font-size:11px;font-family:var(--font);color:var(--text-secondary);transition:all .12s;white-space:nowrap}
.act-btn:hover{background:var(--bg-secondary)}
.act-btn.run{color:var(--text-success);border-color:rgba(34,197,94,.25)}
.act-btn.run:hover{background:var(--bg-success)}
.act-btn.del{color:var(--text-danger)}.act-btn.del:hover{background:var(--bg-danger)}
.act-btn:disabled{opacity:.4;cursor:not-allowed}
.section-header{display:flex;align-items:center;gap:7px;padding:10px 14px;border-bottom:0.5px solid var(--border-light);background:var(--bg-secondary);font-size:12px;font-weight:500;color:var(--text-secondary)}
.sort-ico{display:inline-flex;margin-left:3px;vertical-align:middle;color:var(--text-tertiary)}
.sort-ico.active{color:var(--accent-blue)}

/* v9 #63e: 이력 페이지네이션 */
.hist-pagination{display:flex;align-items:center;justify-content:center;gap:4px;padding:10px 14px;border-top:0.5px solid var(--border-light);background:var(--bg-secondary)}
.pg-btn{min-width:28px;height:26px;padding:0 7px;background:var(--bg-primary);border:0.5px solid var(--border-mid);border-radius:5px;font-size:11px;color:var(--text-secondary);cursor:pointer;transition:all .12s;font-variant-numeric:tabular-nums}
.pg-btn:hover:not(:disabled){background:var(--bg-secondary);border-color:var(--border-strong);color:var(--text-primary)}
.pg-btn.active{background:var(--accent-blue);border-color:var(--accent-blue);color:#fff;font-weight:600}
.pg-btn:disabled{opacity:.3;cursor:not-allowed}
.pg-info{margin-left:8px;font-size:11px;color:var(--text-tertiary);font-variant-numeric:tabular-nums}
.text-dim{color:var(--text-tertiary)}
</style>
