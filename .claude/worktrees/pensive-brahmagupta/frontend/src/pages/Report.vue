<template>
  <div>
    <div class="page-title">실행 리포트</div>
    <div class="page-desc">마이그레이션 실행 히스토리 및 성능 분석</div>

    <!-- KPI -->
    <div class="kpi-row">
      <div class="kpi-card" v-for="k in kpis" :key="k.label" :class="k.cls">
        <div class="kpi-ico" v-html="k.icon"/>
        <div class="kpi-val">{{ k.val }}</div>
        <div class="kpi-lbl">{{ k.label }}</div>
      </div>
    </div>

    <!-- 차트 + 상태 분포 -->
    <div class="chart-grid">

      <!-- 상태별 분포 도넛 -->
      <div class="card chart-card">
        <div class="card-header"><span>상태별 분포</span></div>
        <div class="donut-wrap">
          <svg class="donut-svg" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r="48" fill="none" stroke="var(--border-light)" stroke-width="14"/>
            <circle v-for="(s,i) in donutSegs" :key="i"
              cx="60" cy="60" r="48" fill="none"
              :stroke="s.color" stroke-width="14"
              :stroke-dasharray="`${s.len} ${301 - s.len}`"
              :stroke-dashoffset="-s.offset"
              stroke-linecap="butt"
              style="transform:rotate(-90deg);transform-origin:60px 60px;transition:all .5s"
            />
            <text x="60" y="56" text-anchor="middle" font-size="18" font-weight="700"
                  fill="var(--text-primary)">{{ stats.totalJobs }}</text>
            <text x="60" y="70" text-anchor="middle" font-size="8"
                  fill="var(--text-tertiary)">전체 Job</text>
          </svg>
          <div class="donut-legend">
            <div v-for="s in donutSegs" :key="s.label" class="legend-row">
              <div class="legend-dot" :style="{background: s.color}"/>
              <span class="legend-lbl">{{ s.label }}</span>
              <span class="legend-val">{{ s.count }}</span>
              <span class="legend-pct">{{ s.pct }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 이관 rows 요약 -->
      <div class="card chart-card">
        <div class="card-header"><span>이관 데이터 요약</span></div>
        <div class="summary-grid">
          <div class="sum-item">
            <div class="sum-val">{{ fmtRows(stats.totalRows) }}</div>
            <div class="sum-lbl">총 이관 rows</div>
          </div>
          <div class="sum-item">
            <div class="sum-val">{{ avgRows }}</div>
            <div class="sum-lbl">Job 평균 rows</div>
          </div>
          <div class="sum-item">
            <div class="sum-val ok">{{ stats.completedToday }}</div>
            <div class="sum-lbl">완료된 Job</div>
          </div>
          <div class="sum-item">
            <div class="sum-val" :class="stats.errors > 0 ? 'err' : ''">{{ stats.errors }}</div>
            <div class="sum-lbl">오류 Job</div>
          </div>
        </div>
        <!-- 완료율 게이지 -->
        <div class="gauge-wrap" v-if="stats.totalJobs > 0">
          <div class="gauge-label">
            <span>완료율</span>
            <span class="gauge-pct">{{ completedRate }}%</span>
          </div>
          <div class="gauge-track">
            <div class="gauge-fill ok" :style="{width: completedRate + '%'}"/>
            <div class="gauge-fill err" :style="{width: errorRate + '%', marginLeft: completedRate + '%'}"/>
          </div>
          <div class="gauge-legend">
            <span class="g-ok">■ 완료 {{ completedRate }}%</span>
            <span class="g-err">■ 오류 {{ errorRate }}%</span>
            <span class="g-idle">■ 기타 {{ 100 - completedRate - errorRate }}%</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 히스토리 테이블 -->
    <div class="card">
      <div class="card-header">
        <span>실행 히스토리</span>
        <div class="filter-row">
          <input v-model="searchQ" class="search-inp" placeholder="🔍  Job명 검색..."/>
          <select v-model="filterStatus" class="filter-sel">
            <option value="">전체 상태</option>
            <option value="completed">완료</option>
            <option value="error">오류</option>
            <option value="running">실행중</option>
            <option value="aborted">중단</option>
            <option value="idle">대기</option>
          </select>
          <!-- 선택 삭제 버튼 -->
          <button v-if="selectedIds.length>0" class="act-btn danger" @click="deleteSelected">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:12px;height:12px">
              <polyline points="2,4 12,4"/><path d="M5 4V2h4v2"/><rect x="3" y="4" width="8" height="8" rx="1"/>
              <line x1="5" y1="7" x2="5" y2="10"/><line x1="9" y1="7" x2="9" y2="10"/>
            </svg>
            {{ selectedIds.length }}개 삭제
          </button>
          <button class="act-btn icon-only" @click="loadJobs" :disabled="loading" title="새로고침">
            <span v-if="loading" class="spinner" style="width:11px;height:11px;display:inline-block"/>
            <svg v-else viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" style="width:13px;height:13px" :class="{spinning: loading}">
              <path d="M14 8A6 6 0 1 1 8 2"/>
              <polyline points="10,2 14,2 14,6"/>
            </svg>
          </button>
          <button class="act-btn icon-only" @click="exportCsv" title="CSV 내보내기">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" style="width:13px;height:13px">
              <path d="M8 2v8M5 7l3 3 3-3"/>
              <path d="M3 12h10"/>
            </svg>
          </button>
        </div>
      </div>

      <div v-if="loading && jobs.length===0" class="empty-state" style="padding:40px">
        <span class="spinner" style="width:20px;height:20px;display:inline-block"/>
      </div>

      <table v-else class="r-tbl">
        <thead>
          <tr>
            <th class="chk-col">
              <input type="checkbox" class="row-chk"
                :checked="filtered.length>0 && filtered.every(j=>selectedIds.includes(j.id))"
                :indeterminate="filtered.some(j=>selectedIds.includes(j.id)) && !filtered.every(j=>selectedIds.includes(j.id))"
                @change="toggleAll($event.target.checked)"/>
            </th>
            <th @click="setSort('name')" class="sortable">
              Job 이름 <span class="sort-ico">{{ sortIco('name') }}</span>
            </th>
            <th>소스 → 타겟</th>
            <th @click="setSort('created_at')" class="sortable">
              생성일 <span class="sort-ico">{{ sortIco('created_at') }}</span>
            </th>
            <th @click="setSort('rows_processed')" class="sortable">
              이관 Rows <span class="sort-ico">{{ sortIco('rows_processed') }}</span>
            </th>
            <th>진행률</th>
            <th @click="setSort('status')" class="sortable">
              상태 <span class="sort-ico">{{ sortIco('status') }}</span>
            </th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="filtered.length===0">
            <td colspan="8" style="text-align:center;color:var(--text-tertiary);padding:32px">
              데이터가 없습니다
            </td>
          </tr>
          <tr v-for="j in filtered" :key="j.id" class="data-row"
              :class="{selected: selectedIds.includes(j.id)}"
              @click="openDetail(j)">
            <td class="chk-col" @click.stop>
              <input type="checkbox" class="row-chk"
                :checked="selectedIds.includes(j.id)"
                @change="toggleSelect(j.id)"/>
            </td>
            <td>
              <div class="job-name-cell">{{ j.name }}</div>
            </td>
            <td>
              <div class="db-flow">
                <span class="db-tag" :style="{background:m(j.src_db).bg, color:m(j.src_db).color}">
                  {{ m(j.src_db).label }}
                </span>
                <svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px;color:var(--text-tertiary)"><path d="M1 5h8M6 2l3 3-3 3"/></svg>
                <span class="db-tag" :style="{background:m(j.tgt_db).bg, color:m(j.tgt_db).color}">
                  {{ m(j.tgt_db).label }}
                </span>
              </div>
            </td>
            <td class="meta-cell">{{ fmtDate(j.created_at) }}</td>
            <td class="rows-cell">{{ fmtRows(j.rows_processed) }}</td>
            <td>
              <div class="prog-wrap">
                <div class="prog-track">
                  <div class="prog-fill" :class="progressColor(j.status)"
                       :style="{width: j.progress+'%'}"/>
                </div>
                <span class="prog-pct">{{ j.progress }}%</span>
              </div>
            </td>
            <td>
              <span class="status-pill" :class="statusPill(j.status)">
                {{ statusLabel(j.status) }}
              </span>
            </td>
            <td>
              <button class="icon-btn" @click.stop="openDetail(j)" title="상세보기">
                <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:12px;height:12px"><circle cx="7" cy="7" r="5"/><line x1="7" y1="5" x2="7" y2="9"/><circle cx="7" cy="4" r=".5" fill="currentColor"/></svg>
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <div class="tbl-footer">
        <span>{{ filtered.length }}개 / 전체 {{ jobs.length }}개</span><span v-if="selectedIds.length" style="margin-left:8px;color:var(--text-info);font-weight:500">{{ selectedIds.length }}개 선택됨</span>
      </div>
    </div>

    <!-- ── 오브젝트 재이관 현황 ── -->
    <div class="card obj-remig-card">
      <!-- 헤더 — 클릭으로 접기/펼치기 -->
      <div class="card-header" @click="remigOpen=!remigOpen" style="cursor:pointer;user-select:none">
        <div style="display:flex;align-items:center;gap:8px;flex:1">
          <svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5"
               :style="{transform:remigOpen?'rotate(0deg)':'rotate(-90deg)',transition:'transform .2s'}"
               style="width:9px;height:9px;opacity:.5;flex-shrink:0">
            <polyline points="1,3 5,7 9,3"/>
          </svg>
          <span>오브젝트 재이관 현황 (AI 변환)</span>
          <span v-if="remigHistory.length" style="font-size:11px;color:var(--text-tertiary)">
            총 {{ remigHistory.length }}건 ·
            입력 {{ remigHistory.reduce((s,r)=>s+(r.in||0),0).toLocaleString() }} ·
            출력 {{ remigHistory.reduce((s,r)=>s+(r.out||0),0).toLocaleString() }} 토큰
          </span>
        </div>
        <div style="display:flex;align-items:center;gap:6px" @click.stop>
          <!-- 선택 삭제 버튼 -->
          <button v-if="selectedRemigKeys.length>0" class="act-btn danger" @click="deleteRemigSelected">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:11px;height:11px">
              <polyline points="2,4 12,4"/><path d="M5 4V2h4v2"/><rect x="3" y="4" width="8" height="8" rx="1"/>
            </svg>
            {{ selectedRemigKeys.length }}개 삭제
          </button>
          <button class="act-btn icon-only" @click="loadRemigHistory" title="새로고침">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:12px;height:12px">
              <path d="M1 7a6 6 0 1 0 6-6"/><polyline points="4,1 1,1 1,4"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- 접힌 상태 -->
      <template v-if="remigOpen">
        <div v-if="!remigHistory.length" style="padding:16px;text-align:center;font-size:12px;color:var(--text-tertiary)">
          재이관 이력이 없습니다
        </div>
        <table v-else class="rep-tbl">
          <thead><tr>
            <th class="chk-col">
              <input type="checkbox" class="row-chk"
                :checked="remigHistory.length>0 && remigHistory.every(r=>selectedRemigKeys.includes(r.ts+r.name))"
                @change="toggleAllRemig($event.target.checked)"/>
            </th>
            <th>시각</th>
            <th>오브젝트명</th>
            <th>타입</th>
            <th style="text-align:right">입력</th>
            <th style="text-align:right">출력</th>
            <th style="text-align:center">상태</th>
          </tr></thead>
          <tbody>
            <tr v-for="r in remigHistory" :key="r.ts+r.name" class="rep-row"
                :class="{selected: selectedRemigKeys.includes(r.ts+r.name)}">
              <td class="chk-col" @click.stop>
                <input type="checkbox" class="row-chk"
                  :checked="selectedRemigKeys.includes(r.ts+r.name)"
                  @change="toggleRemig(r.ts+r.name)"/>
              </td>
              <td style="font-size:11px;color:var(--text-tertiary);white-space:nowrap">{{ fmtTs(r.ts) }}</td>
              <td style="font-weight:500;font-size:12px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ r.name }}</td>
              <td>
                <span class="rep-type-badge"
                      :class="r.type?.includes('PROC')?'proc':r.type?.includes('FUNC')?'func':r.type?.includes('TRIG')?'trig':'view'">
                  {{ r.type?.replace('OBJ_REMIGRATE_','') || 'OBJ' }}
                </span>
              </td>
              <td style="text-align:right;font-size:11px;font-family:monospace">{{ r.in?.toLocaleString() || '—' }}</td>
              <td style="text-align:right;font-size:11px;font-family:monospace">{{ r.out?.toLocaleString() || '—' }}</td>
              <td style="text-align:center">
                <span style="font-size:10px;padding:2px 7px;border-radius:5px;background:rgba(22,163,74,.1);color:#166534;font-weight:500">✓ 완료</span>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="selectedRemigKeys.length" class="tbl-footer">
          <span style="color:var(--text-info);font-weight:500">{{ selectedRemigKeys.length }}개 선택됨</span>
        </div>
      </template>
    </div>

    <!-- 상세 모달 -->
    <div v-if="detail" class="modal-overlay" @click.self="detail=null">
      <div class="modal detail-modal">
        <div class="modal-head">
          <div>
            <div class="modal-title">{{ detail.name }}</div>
            <div class="modal-sub">{{ detail.id }}</div>
          </div>
          <span class="status-pill" :class="statusPill(detail.status)" style="font-size:11px">
            {{ statusLabel(detail.status) }}
          </span>
        </div>

        <div class="detail-grid">
          <div class="detail-item">
            <div class="detail-lbl">소스 DB</div>
            <div class="detail-val">
              <span class="db-tag" :style="{background:m(detail.src_db).bg, color:m(detail.src_db).color}">{{ m(detail.src_db).label }}</span>
              {{ detail.src_db }} / {{ detail.src_host||'—' }}
            </div>
          </div>
          <div class="detail-item">
            <div class="detail-lbl">타겟 DB</div>
            <div class="detail-val">
              <span class="db-tag" :style="{background:m(detail.tgt_db).bg, color:m(detail.tgt_db).color}">{{ m(detail.tgt_db).label }}</span>
              {{ detail.tgt_db }} / {{ detail.tgt_host||'—' }}
            </div>
          </div>
          <div class="detail-item">
            <div class="detail-lbl">이관 Rows</div>
            <div class="detail-val">{{ fmtRows(detail.rows_processed) }}</div>
          </div>
          <div class="detail-item">
            <div class="detail-lbl">오류 Rows</div>
            <div class="detail-val" :class="detail.rows_error > 0 ? 'err-txt' : ''">{{ detail.rows_error||0 }}</div>
          </div>
          <div class="detail-item">
            <div class="detail-lbl">테이블 수</div>
            <div class="detail-val">{{ (detail.tables||[]).length }}</div>
          </div>
          <div class="detail-item">
            <div class="detail-lbl">배치 크기</div>
            <div class="detail-val">{{ detail.batch_size||'—' }}</div>
          </div>
          <div class="detail-item">
            <div class="detail-lbl">생성일</div>
            <div class="detail-val">{{ fmtDate(detail.created_at) }}</div>
          </div>
          <div class="detail-item">
            <div class="detail-lbl">완료일</div>
            <div class="detail-val">{{ fmtDate(detail.finished_at) }}</div>
          </div>
        </div>

        <!-- 진행률 -->
        <div class="detail-prog">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px;font-size:11.5px">
            <span>진행률</span><span>{{ detail.progress }}%</span>
          </div>
          <div class="prog-track" style="height:8px">
            <div class="prog-fill" :class="progressColor(detail.status)"
                 :style="{width: detail.progress+'%'}"/>
          </div>
        </div>

        <div v-if="detail.error_message" class="err-banner" style="margin-top:10px;font-size:11.5px">
          ⚠ {{ detail.error_message }}
        </div>

        <div class="modal-btns">
          <button class="btn" @click="detail=null">닫기</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { jobsApi } from '@/api/index.js'
import { DB_META } from '@/constants/dbMeta.js'

const jobs         = ref([])
const selectedIds  = ref([])
const stats        = ref({ totalJobs:0, totalRows:0, completedToday:0, errors:0, running:0, validateRate:0 })
const loading      = ref(false)
const filterStatus = ref('')
const searchQ      = ref('')
const detail       = ref(null)
const sortCol      = ref('created_at')
const sortDir      = ref(-1) // -1 desc, 1 asc

const m          = t => DB_META[t] || { label:'??', bg:'#eee', color:'#333' }
const fmtRows    = n => !n ? '0' : n>=1e6?(n/1e6).toFixed(1)+'M':n>=1e3?(n/1e3).toFixed(1)+'K':String(n)
const statusLabel= s => ({completed:'완료',error:'오류',running:'실행중',idle:'대기',paused:'일시정지',aborted:'중단'}[s]??s)
const statusPill = s => ({completed:'ok',error:'err',running:'run',idle:'idle',paused:'warn',aborted:'warn'}[s]??'idle')
const progressColor=s=>({completed:'ok',error:'err',running:'run',paused:'warn'}[s]??'run')

function fmtDate(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('ko-KR',{month:'2-digit',day:'2-digit'}) + ' ' +
           d.toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit'})
  } catch { return iso.slice(0,16) }
}

function setSort(col) {
  if (sortCol.value === col) sortDir.value *= -1
  else { sortCol.value = col; sortDir.value = -1 }
}
function sortIco(col) {
  if (sortCol.value !== col) return '↕'
  return sortDir.value === -1 ? '↓' : '↑'
}

const filtered = computed(() => {
  let r = jobs.value
  if (filterStatus.value) r = r.filter(j => j.status === filterStatus.value)
  if (searchQ.value.trim()) {
    const q = searchQ.value.toLowerCase()
    r = r.filter(j => j.name?.toLowerCase().includes(q))
  }
  return [...r].sort((a,b) => {
    const va = a[sortCol.value] ?? ''
    const vb = b[sortCol.value] ?? ''
    if (typeof va === 'number') return (va - vb) * sortDir.value
    return String(va).localeCompare(String(vb)) * sortDir.value
  })
})

const avgRows = computed(() => {
  if (!stats.value.totalJobs) return '0'
  return fmtRows(Math.round(stats.value.totalRows / stats.value.totalJobs))
})
const completedRate = computed(() => {
  if (!stats.value.totalJobs) return 0
  return Math.round(stats.value.completedToday / stats.value.totalJobs * 100)
})
const errorRate = computed(() => {
  if (!stats.value.totalJobs) return 0
  return Math.round(stats.value.errors / stats.value.totalJobs * 100)
})

// 도넛 차트 세그먼트
const donutSegs = computed(() => {
  const total = stats.value.totalJobs || 1
  const CIRC = 301 // 2π×48
  const segs = [
    { label:'완료',    count: stats.value.completedToday, color:'#22c55e' },
    { label:'오류',    count: stats.value.errors,         color:'#ef4444' },
    { label:'실행 중', count: stats.value.running,        color:'#f59e0b' },
    { label:'대기/기타', count: Math.max(0, stats.value.totalJobs - stats.value.completedToday - stats.value.errors - stats.value.running), color:'var(--border-mid)' },
  ]
  let offset = 0
  return segs.map(s => {
    const pct = Math.round(s.count / total * 100)
    const len = s.count / total * CIRC
    const seg = { ...s, pct, len, offset }
    offset += len
    return seg
  })
})

const kpis = computed(() => {
  const s = stats.value
  return [
    { label:'총 실행 횟수',  val: s.totalJobs,          cls:'info',
      icon:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:16px;height:16px"><rect x="2" y="3" width="12" height="10" rx="1.5"/><line x1="5" y1="7" x2="11" y2="7"/><line x1="5" y1="10" x2="8" y2="10"/></svg>' },
    { label:'총 이관 Rows',  val: fmtRows(s.totalRows),  cls:'',
      icon:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:16px;height:16px"><path d="M2 12 L5 5 L8 9 L11 4 L14 8"/></svg>' },
    { label:'완료',          val: s.completedToday,      cls:'ok',
      icon:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:16px;height:16px"><circle cx="8" cy="8" r="6"/><polyline points="5,8 7,10 11,6"/></svg>' },
    { label:'오류',          val: s.errors,              cls: s.errors>0?'err':'',
      icon:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:16px;height:16px"><circle cx="8" cy="8" r="6"/><line x1="8" y1="5" x2="8" y2="9"/><circle cx="8" cy="11" r=".5" fill="currentColor"/></svg>' },
    { label:'실행 중',       val: s.running,             cls:'run',
      icon:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:16px;height:16px"><polygon points="4,3 13,8 4,13"/></svg>' },
  ]
})

function toggleSelect(id) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}

function toggleAll(checked) {
  selectedIds.value = checked ? filtered.value.map(j => j.id) : []
}

async function deleteSelected() {
  if (!selectedIds.value.length) return
  if (!confirm(`선택한 ${selectedIds.value.length}개 Job을 삭제하시겠습니까?\n(이 작업은 되돌릴 수 없습니다)`)) return
  const ids = [...selectedIds.value]
  try {
    await jobsApi.bulkDel(ids)
    selectedIds.value = []
    await loadJobs()
    app.notify(`${ids.length}개 Job 삭제 완료`, 'success')
  } catch(e) {
    app.notify('삭제 실패: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

async function loadJobs() {
  loading.value = true
  try {
    const [jobList, s] = await Promise.all([jobsApi.list(), jobsApi.stats()])
    jobs.value = [...jobList].sort((a,b) => new Date(b.created_at)-new Date(a.created_at))
    stats.value = s
  } catch(e) { console.error(e) }
  finally { loading.value = false }
}

function openDetail(j) { detail.value = j }

function exportCsv() {
  const header = ['ID','이름','소스DB','타겟DB','상태','이관rows','완료일']
  const rows = jobs.value.map(j => [
    j.id.slice(0,8), j.name, j.src_db, j.tgt_db, j.status, j.rows_processed, j.finished_at||''
  ])
  const csv = [header,...rows].map(r=>r.join(',')).join('\n')
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob(['\uFEFF'+csv],{type:'text/csv;charset=utf-8'}))
  a.download = `databridge_report_${Date.now()}.csv`; a.click()
}

onMounted(() => {
  loadJobs()
  loadRemigHistory()
})

const remigHistory      = ref([])
const remigOpen         = ref(false)   // 기본 접힘
const selectedRemigKeys = ref([])

function fmtTs(ts) {
  if (!ts) return '—'
  // "MM-DD HH:MM:SS" 형식
  if (ts.includes('-') && ts.includes(':')) return ts
  // 구 형식 "HH:MM:SS" → 시각만 표시
  if (/^\d{2}:\d{2}:\d{2}$/.test(ts)) return ts
  // 분:초만 있는 경우 ":SS" → 그대로
  return ts
}

function toggleRemig(key) {
  const idx = selectedRemigKeys.value.indexOf(key)
  if (idx >= 0) selectedRemigKeys.value.splice(idx, 1)
  else selectedRemigKeys.value.push(key)
}

function toggleAllRemig(checked) {
  selectedRemigKeys.value = checked ? remigHistory.value.map(r => r.ts+r.name) : []
}

async function deleteRemigSelected() {
  if (!selectedRemigKeys.value.length) return
  if (!confirm(`선택한 ${selectedRemigKeys.value.length}개 이력을 삭제하시겠습니까?`)) return
  try {
    await axios.delete('/api/v1/settings/claude-usage/objects', {
      data: { keys: selectedRemigKeys.value }
    })
    remigHistory.value = remigHistory.value.filter(
      r => !selectedRemigKeys.value.includes(r.ts+r.name)
    )
    selectedRemigKeys.value = []
    app.notify('삭제 완료', 'success')
  } catch(e) {
    app.notify('삭제 실패: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

async function loadRemigHistory() {
  try {
    const { default: axios } = await import('axios')
    const { data } = await axios.get('/api/v1/settings/claude-usage')
    const objects = data?.objects || []
    remigHistory.value = objects
      .filter(o => o.type?.startsWith('OBJ_REMIGRATE'))
      .reverse()
      .slice(0, 50)
  } catch (e) {
    console.warn('재이관 이력 조회 실패:', e.message)
  }
}
</script>

<style scoped>
/* KPI */
.kpi-row { display:grid; grid-template-columns:repeat(5,1fr); gap:10px; margin-bottom:14px; }
.kpi-card { background:var(--bg-secondary); border:0.5px solid var(--border-light); border-radius:var(--radius-lg,12px); padding:16px; }
.kpi-ico { color:var(--text-tertiary); opacity:.6; margin-bottom:8px; }
.kpi-val { font-size:28px; font-weight:700; color:var(--text-primary); line-height:1; margin-bottom:4px; }
.kpi-lbl { font-size:11px; color:var(--text-tertiary); }
.kpi-card.info .kpi-val { color:var(--text-info); }
.kpi-card.ok   .kpi-val { color:var(--text-success); }
.kpi-card.err  .kpi-val { color:var(--text-danger); }
.kpi-card.run  .kpi-val { color:#f59e0b; }

/* 차트 그리드 */
.chart-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:14px; }
.chart-card { padding:0; overflow:hidden; }

/* 도넛 */
.donut-wrap { display:flex; align-items:center; gap:20px; padding:16px; }
.donut-svg { width:120px; height:120px; flex-shrink:0; }
.donut-legend { flex:1; display:flex; flex-direction:column; gap:8px; }
.legend-row { display:flex; align-items:center; gap:7px; font-size:12px; }
.legend-dot { width:8px; height:8px; border-radius:2px; flex-shrink:0; }
.legend-lbl { flex:1; color:var(--text-secondary); }
.legend-val { font-weight:600; color:var(--text-primary); }
.legend-pct { font-size:10.5px; color:var(--text-tertiary); width:28px; text-align:right; }

/* 요약 카드 */
.summary-grid { display:grid; grid-template-columns:1fr 1fr; gap:1px; background:var(--border-light); border-bottom:0.5px solid var(--border-light); }
.sum-item { padding:14px 16px; background:var(--bg-primary); }
.sum-val { font-size:22px; font-weight:700; color:var(--text-primary); }
.sum-val.ok  { color:var(--text-success); }
.sum-val.err { color:var(--text-danger); }
.sum-lbl { font-size:11px; color:var(--text-tertiary); margin-top:2px; }
.gauge-wrap { padding:12px 16px; }
.gauge-label { display:flex; justify-content:space-between; font-size:11.5px; color:var(--text-secondary); margin-bottom:6px; }
.gauge-pct { font-weight:600; }
.gauge-track { position:relative; height:8px; background:var(--bg-secondary); border-radius:4px; overflow:hidden; }
.gauge-fill { position:absolute; top:0; height:100%; transition:width .5s; }
.gauge-fill.ok  { background:#22c55e; left:0; }
.gauge-fill.err { background:#ef4444; }
.gauge-legend { display:flex; gap:12px; margin-top:6px; font-size:10.5px; }
.g-ok   { color:#22c55e; }
.g-err  { color:#ef4444; }
.g-idle { color:var(--text-tertiary); }

/* 필터 */
.filter-row { display:flex; align-items:center; gap:6px; }
.search-inp { font-size:11.5px; padding:5px 10px; border-radius:var(--radius-md); border:0.5px solid var(--border-mid); background:var(--bg-secondary); color:var(--text-primary); font-family:var(--font); width:160px; }
.search-inp:focus { outline:none; border-color:var(--accent-blue); }
.filter-sel { font-size:11.5px; padding:5px 8px; border-radius:var(--radius-md); border:0.5px solid var(--border-mid); background:var(--bg-secondary); color:var(--text-primary); }

/* 테이블 */
.r-tbl { width:100%; border-collapse:collapse; }
.r-tbl th { background:var(--bg-secondary); font-size:10.5px; font-weight:600; color:var(--text-tertiary); padding:7px 12px; text-align:left; border-bottom:0.5px solid var(--border-light); white-space:nowrap; user-select:none; text-transform:uppercase; letter-spacing:.03em; }
.r-tbl th.sortable { cursor:pointer; }
.r-tbl th.sortable:hover { color:var(--text-primary); }
.sort-ico { font-size:10px; margin-left:3px; }
.r-tbl td { padding:7px 12px; border-bottom:0.5px solid var(--border-light); vertical-align:middle; font-size:12.5px; }
.r-tbl tr:last-child td { border-bottom:none; }
.data-row { cursor:pointer; transition:background .1s; }
.data-row:hover td { background:var(--bg-secondary); }
.job-name-cell { font-size:12.5px; font-weight:500; color:var(--text-primary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.job-id-cell   { font-size:10.5px; color:var(--text-tertiary); margin-top:2px; font-family:monospace; }
.meta-cell     { font-size:11px; color:var(--text-tertiary); }
.rows-cell     { font-size:12px; font-weight:500; }
.db-flow { display:flex; align-items:center; gap:5px; }
.db-tag  { font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px; flex-shrink:0; }
.prog-wrap { display:flex; align-items:center; gap:6px; min-width:90px; }
.prog-track { flex:1; height:5px; background:var(--bg-secondary); border-radius:3px; overflow:hidden; }
.prog-fill { height:100%; border-radius:3px; transition:width .3s; min-width:2px; }
.prog-fill.ok  { background:#22c55e; }
.prog-fill.err { background:#ef4444; }
.prog-fill.run { background:var(--accent-blue); }
.prog-fill.warn{ background:#f59e0b; }
.prog-pct { font-size:10.5px; color:var(--text-tertiary); }
.status-pill { font-size:10px; font-weight:600; padding:2px 8px; border-radius:10px; }
.status-pill.ok   { background:rgba(34,197,94,.12);  color:#16a34a; }
.status-pill.err  { background:rgba(239,68,68,.1);   color:#dc2626; }
.status-pill.run  { background:rgba(245,158,11,.12); color:#d97706; }
.status-pill.warn { background:rgba(245,158,11,.12); color:#d97706; }
.status-pill.idle { background:var(--bg-secondary);  color:var(--text-tertiary); }
.icon-btn { width:26px; height:26px; border-radius:var(--radius-sm); border:0.5px solid var(--border-mid); background:transparent; cursor:pointer; display:flex; align-items:center; justify-content:center; color:var(--text-tertiary); }
.icon-btn:hover { background:var(--bg-secondary); color:var(--text-primary); }
.tbl-footer { padding:8px 16px; font-size:11px; color:var(--text-tertiary); border-top:0.5px solid var(--border-light); }

/* 상세 모달 */
.detail-modal { max-width:560px; }
.modal-head { display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:16px; }
.modal-title { font-size:15px; font-weight:600; color:var(--text-primary); }
.modal-sub   { font-size:10.5px; color:var(--text-tertiary); font-family:monospace; margin-top:2px; }
.detail-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:14px; }
.detail-item { background:var(--bg-secondary); border-radius:var(--radius-md); padding:10px 12px; }
.detail-lbl  { font-size:10.5px; color:var(--text-tertiary); margin-bottom:4px; }
.detail-val  { font-size:12.5px; color:var(--text-primary); font-weight:500; display:flex; align-items:center; gap:5px; flex-wrap:wrap; }
.err-txt     { color:var(--text-danger); }
.detail-prog { background:var(--bg-secondary); border-radius:var(--radius-md); padding:12px; }
.err-banner  { background:rgba(239,68,68,.08); border:0.5px solid rgba(239,68,68,.3); border-radius:var(--radius-md); padding:10px 12px; color:var(--text-danger); }

/* 공통 */
.card-header { display:flex; align-items:center; justify-content:space-between; padding:12px 16px; border-bottom:0.5px solid var(--border-light); font-size:13px; font-weight:600; color:var(--text-primary); flex-wrap:wrap; gap:6px; }
.act-btn { font-size:11.5px; padding:5px 10px; border-radius:var(--radius-md); border:0.5px solid var(--border-mid); background:transparent; color:var(--text-secondary); cursor:pointer; display:flex; align-items:center; gap:4px; transition:all .12s; }
.act-btn:hover { background:var(--bg-secondary); color:var(--text-primary); }
.act-btn:disabled { opacity:.5; cursor:not-allowed; }
.act-btn.icon-only { padding:5px 8px; }
.act-btn.icon-only:hover { background:var(--bg-info); color:var(--text-info); border-color:var(--accent-blue); }
@keyframes spin { to { transform:rotate(360deg); } }
.spinning { animation:spin .7s linear infinite; }
.empty-state { display:flex; justify-content:center; align-items:center; color:var(--text-tertiary); }

@media(max-width:900px) { .kpi-row{grid-template-columns:repeat(3,1fr)} .chart-grid{grid-template-columns:1fr} }

.obj-remig-card { margin-top: 14px; }
.rep-tbl { width: 100%; border-collapse: collapse; font-size: 12px; }
.rep-tbl th { font-size: 10px; font-weight: 500; color: var(--text-tertiary); padding: 6px 10px; border-bottom: 0.5px solid var(--border-light); text-align: left; }
.rep-tbl td { padding: 6px 10px; border-bottom: 0.5px solid var(--border-light); }
.rep-row:hover td { background: var(--bg-secondary); }
.rep-row.selected td { background: rgba(37,99,235,.04) !important; }
/* 체크박스 컬럼 */
.chk-col { width: 36px; padding: 0 8px !important; text-align: center; }
.row-chk { width: 14px; height: 14px; cursor: pointer; accent-color: #2563eb; }
.data-row.selected td { background: rgba(37,99,235,.05) !important; }
.data-row.selected { outline: none; }
/* 삭제 버튼 */
.act-btn.danger {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 4px 10px; border-radius: var(--radius-sm);
  background: rgba(239,68,68,.1); color: #dc2626;
  border: 0.5px solid rgba(239,68,68,.25);
  font-size: 11.5px; font-weight: 600; cursor: pointer;
  transition: all .12s; font-family: var(--font);
  white-space: nowrap; flex-shrink: 0;
}
.act-btn.danger:hover { background: rgba(239,68,68,.18); border-color: rgba(239,68,68,.4); }
.rep-type-badge { display: inline-flex; padding: 1px 6px; border-radius: 4px; font-size: 10px; font-weight: 700; }
.rep-type-badge.proc { background: rgba(99,102,241,.1); color: #4338ca; }
.rep-type-badge.func { background: rgba(16,185,129,.1); color: #065f46; }
.rep-type-badge.trig { background: rgba(245,158,11,.1); color: #b45309; }
.rep-type-badge.view { background: rgba(59,130,246,.1); color: #1e40af; }
</style>
