<template>
  <div class="kb-dashboard">
    <!-- v94_p3 (2026-05-01): 본부장님 호소 처방
         "KB 추가 어디서 확인 가능?" + "조회 더 잘 할 수 있도록 보강"
         → 검색/필터/그룹/상세보기/패턴화 워크플로우 한 화면 -->

    <!-- ━━━ 상단 요약 카드 ━━━ -->
    <div class="summary-grid" v-if="dashData">
      <div class="summary-card">
        <div class="card-label">등록 패턴</div>
        <div class="card-value">{{ dashData.summary.total_patterns }}<span class="card-unit">개</span></div>
        <div class="card-sub">에러 KB 정식 등록</div>
      </div>
      <div class="summary-card">
        <div class="card-label">KB 후보 케이스</div>
        <div class="card-value">{{ casesData.total || 0 }}<span class="card-unit">건</span></div>
        <div class="card-sub">error_cases.txt 누적</div>
      </div>
      <div class="summary-card success">
        <div class="card-label">전체 적중률</div>
        <div class="card-value">{{ dashData.summary.overall_rate }}<span class="card-unit">%</span></div>
        <div class="card-sub">{{ dashData.summary.total_success }}건 / {{ formatNum(dashData.summary.total_attempts) }}회</div>
      </div>
      <div class="summary-card highlight">
        <div class="card-label">AI 호출 절약</div>
        <div class="card-value">{{ dashData.summary.ai_saved_rate }}<span class="card-unit">%</span></div>
        <div class="card-sub">{{ formatNum(dashData.summary.ai_saved) }}회 절감</div>
      </div>
    </div>

    <!-- ━━━ 카테고리 분포 + Top 패턴 (기존 유지) ━━━ -->
    <div class="panel" v-if="dashData?.patterns_by_category">
      <h3>카테고리별 패턴 분포</h3>
      <div class="cat-grid">
        <div v-for="(cnt, cat) in dashData.patterns_by_category" :key="cat" class="cat-item">
          <span class="cat-name">{{ cat }}</span>
          <span class="cat-count">{{ cnt }}개</span>
          <div class="cat-bar" :style="{ width: (cnt / maxCatCount * 100) + '%' }"></div>
        </div>
      </div>
    </div>

    <div class="panel" v-if="dashData?.top_patterns?.length">
      <h3>최다 활용 패턴 (Top 10)</h3>
      <table class="kb-table">
        <thead>
          <tr>
            <th>패턴 ID</th><th>코드</th><th>카테고리</th>
            <th class="num">시도</th><th class="num">성공</th>
            <th class="num">적중률</th><th>마지막 사용</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in dashData.top_patterns" :key="p.pattern_id">
            <td class="pattern-id">{{ p.pattern_id }}</td>
            <td>{{ p.error_code }}</td>
            <td><span class="cat-badge">{{ p.category }}</span></td>
            <td class="num">{{ p.attempts }}</td>
            <td class="num">{{ p.success }}</td>
            <td class="num"><span :class="rateClass(p.rate)">{{ Math.round(p.rate * 100) }}%</span></td>
            <td class="ts">{{ formatTs(p.last_seen) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
         v94_p3 강화: KB 후보 케이스 조회 영역
         ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
    <div class="panel cases-panel">
      <div class="cases-header">
        <h3>📋 KB 후보 케이스 조회</h3>
        <p class="muted">파일: <code>{{ casesData.file }}</code> ({{ formatBytes(casesData.file_size_bytes) }})</p>
      </div>

      <!-- v94_p3: 검색/필터 컨트롤 -->
      <div class="filter-row">
        <input v-model="q" @input="debouncedReload"
               placeholder="🔍 객체명/에러/DDL 검색..."
               class="filter-input search-input"/>
        <select v-model="filterObjType" @change="reloadCases" class="filter-select">
          <option value="">객체 타입: 전체</option>
          <option v-for="t in casesData.all_obj_types || []" :key="t" :value="t">{{ t }}</option>
        </select>
        <select v-model="filterErrorCode" @change="reloadCases" class="filter-select">
          <option value="">에러코드: 전체</option>
          <option v-for="c in casesData.all_error_codes || []" :key="c" :value="c">{{ c }}</option>
        </select>
        <input v-model="dateFrom" @change="reloadCases" type="date" class="filter-input date-input" title="시작 날짜"/>
        <span class="filter-sep">~</span>
        <input v-model="dateTo" @change="reloadCases" type="date" class="filter-input date-input" title="종료 날짜"/>
        <select v-model="groupBy" @change="reloadCases" class="filter-select">
          <option value="">그룹화: 없음</option>
          <option value="object">객체별</option>
          <option value="date">날짜별</option>
          <option value="error_code">에러코드별</option>
        </select>
        <button v-if="hasActiveCaseFilters" class="filter-clear" @click="clearCaseFilters">
          ✕ 필터 초기화
        </button>
      </div>

      <div class="result-bar">
        <span class="match-count">{{ casesData.matched || 0 }} / {{ casesData.total || 0 }}건</span>
        <span v-if="loading" class="loading-tag">로딩 중...</span>
      </div>

      <!-- v94_p3: 그룹 결과 -->
      <div v-if="groupBy && casesData.groups && Object.keys(casesData.groups).length"
           class="groups-panel">
        <h4>{{ groupByLabel }} 분포 ({{ Object.keys(casesData.groups).length }}개 그룹)</h4>
        <div class="group-grid">
          <div v-for="(cnt, key) in sortedGroups" :key="key" class="group-item"
               @click="drillDownGroup(key)" :title="`'${key}' 클릭하면 필터링`">
            <span class="group-key">{{ key || '(unknown)' }}</span>
            <span class="group-count">{{ cnt }}건</span>
            <div class="group-bar" :style="{ width: (cnt / maxGroupCnt * 100) + '%' }"></div>
          </div>
        </div>
      </div>

      <!-- v94_p3: 케이스 목록 (확장형) -->
      <div v-if="casesData.cases && casesData.cases.length" class="cases-list">
        <div v-for="(c, i) in casesData.cases" :key="c.timestamp + i" class="case-item">
          <div class="case-row" @click="toggleExpand(c.timestamp)">
            <span class="case-ts">{{ c.timestamp.replace('T', ' ') }}</span>
            <span v-if="c.obj_type" class="case-obj-type" :class="`type-${c.obj_type.toLowerCase()}`">
              {{ c.obj_type }}
            </span>
            <span class="case-obj-name">{{ c.obj_name || '(unknown)' }}</span>
            <span v-if="c.error_code" class="case-err-code">{{ c.error_code }}</span>
            <span class="case-summary">{{ c.first_error_line || c.summary }}</span>
            <span class="case-expand-ico">{{ expandedTs === c.timestamp ? '▼' : '▶' }}</span>
          </div>
          <div v-if="expandedTs === c.timestamp" class="case-detail">
            <div v-if="caseDetailLoading" class="detail-loading">상세 로딩 중...</div>
            <div v-else-if="caseDetail">
              <div class="detail-actions">
                <button class="action-btn" @click="copyDetail">📋 본문 복사</button>
                <button class="action-btn primary" @click="goToYmlEditor(c)">
                  📝 정식 패턴으로 등록 →
                </button>
              </div>
              <pre class="detail-body">{{ caseDetail.full_content }}</pre>
            </div>
          </div>
        </div>
      </div>
      <div v-else-if="!loading" class="empty-cases">
        <p>{{ hasActiveCaseFilters ? '필터에 매칭되는 케이스 없음' : '아직 KB 후보 케이스가 없습니다.' }}</p>
      </div>
    </div>

    <!-- ━━━ 미매칭 케이스 ━━━ -->
    <div class="panel warning" v-if="dashData?.unmatched_recent?.length">
      <h3>🔬 미매칭 에러 (KB 보강 후보)</h3>
      <p class="muted">아래는 KB 패턴에 매칭 안 된 최근 오류입니다. 정식 패턴으로 추가하면 자동 처방 가능.</p>
      <ul class="unmatched-list">
        <li v-for="(e, i) in dashData.unmatched_recent" :key="i" class="unmatched-item">
          <code>{{ (e.error_message || e).substring(0, 200) }}</code>
        </li>
      </ul>
    </div>

    <div v-if="!loading && !dashData" class="empty">
      <p>KB 통계 로드 실패. 백엔드 응답 확인 필요.</p>
      <button @click="loadAll" class="btn-reload">다시 시도</button>
    </div>
    <div v-if="loading && !dashData" class="loading">로딩 중...</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

defineOptions({ name: 'AdminKbDashboard' })

const dashData = ref(null)
const casesData = ref({})
const loading = ref(false)

// v94_p3: 케이스 검색/필터 state
const q              = ref('')
const filterObjType  = ref('')
const filterErrorCode = ref('')
const dateFrom       = ref('')
const dateTo         = ref('')
const groupBy        = ref('')

const expandedTs    = ref('')
const caseDetail    = ref(null)
const caseDetailLoading = ref(false)

const maxCatCount = computed(() => {
  if (!dashData.value?.patterns_by_category) return 1
  return Math.max(...Object.values(dashData.value.patterns_by_category), 1)
})
const groupByLabel = computed(() => ({
  object: '객체별', date: '날짜별', error_code: '에러코드별',
})[groupBy.value] || '')
const sortedGroups = computed(() => {
  const g = casesData.value?.groups || {}
  return Object.fromEntries(
    Object.entries(g).sort((a, b) => b[1] - a[1])
  )
})
const maxGroupCnt = computed(() =>
  Math.max(1, ...Object.values(casesData.value?.groups || {}))
)
const hasActiveCaseFilters = computed(() =>
  !!(q.value || filterObjType.value || filterErrorCode.value ||
     dateFrom.value || dateTo.value || groupBy.value)
)

function formatNum(n) {
  if (n == null) return '-'
  if (n >= 10000) return (n / 10000).toFixed(1) + '만'
  return Number(n).toLocaleString()
}
function formatTs(ts) {
  if (!ts) return '-'
  return ts.replace('T', ' ').substring(0, 19)
}
function formatBytes(b) {
  if (!b) return '0 B'
  if (b < 1024) return b + ' B'
  if (b < 1024 * 1024) return (b / 1024).toFixed(1) + ' KB'
  return (b / 1024 / 1024).toFixed(1) + ' MB'
}
function rateClass(rate) {
  if (rate >= 0.9) return 'rate-high'
  if (rate >= 0.7) return 'rate-mid'
  return 'rate-low'
}

async function loadDashboard() {
  try {
    const res = await axios.get('/api/v1/kb/dashboard')
    dashData.value = res.data
  } catch (e) {
    console.error('[KB Dashboard] dashboard 로드 실패:', e)
  }
}

async function reloadCases() {
  loading.value = true
  try {
    const params = new URLSearchParams({
      limit: '100',
      q: q.value,
      obj_type: filterObjType.value,
      error_code: filterErrorCode.value,
      date_from: dateFrom.value,
      date_to: dateTo.value,
      group_by: groupBy.value,
    })
    const res = await axios.get('/api/v1/kb/cases-recent?' + params.toString())
    casesData.value = res.data
  } catch (e) {
    console.error('[KB Dashboard] cases 로드 실패:', e)
    casesData.value = { cases: [], total: 0, matched: 0 }
  } finally {
    loading.value = false
  }
}

let _timer = null
function debouncedReload() {
  if (_timer) clearTimeout(_timer)
  _timer = setTimeout(reloadCases, 400)
}

async function loadAll() {
  loading.value = true
  await Promise.all([loadDashboard(), reloadCases()])
  loading.value = false
}

function clearCaseFilters() {
  q.value = ''
  filterObjType.value = ''
  filterErrorCode.value = ''
  dateFrom.value = ''
  dateTo.value = ''
  groupBy.value = ''
  reloadCases()
}

function drillDownGroup(key) {
  if (groupBy.value === 'object') q.value = key
  else if (groupBy.value === 'error_code') filterErrorCode.value = key
  else if (groupBy.value === 'date') {
    dateFrom.value = key
    dateTo.value = key
  }
  groupBy.value = ''
  reloadCases()
}

async function toggleExpand(ts) {
  if (expandedTs.value === ts) {
    expandedTs.value = ''
    caseDetail.value = null
    return
  }
  expandedTs.value = ts
  caseDetailLoading.value = true
  try {
    const res = await axios.get('/api/v1/kb/cases-detail', { params: { timestamp: ts } })
    caseDetail.value = res.data
  } catch (e) {
    console.error('[KB Dashboard] case detail 실패:', e)
    caseDetail.value = { full_content: '(상세 로드 실패)' }
  } finally {
    caseDetailLoading.value = false
  }
}

async function copyDetail() {
  if (!caseDetail.value) return
  try {
    await navigator.clipboard.writeText(caseDetail.value.full_content)
    alert('✓ 본문 복사됨')
  } catch (e) {
    alert('복사 실패: ' + e.message)
  }
}

function goToYmlEditor(c) {
  const hint = `정식 KB 패턴 등록 가이드:

대상 케이스: ${c.timestamp} - ${c.obj_name} (${c.obj_type})
에러 코드: ${c.error_code || '(unknown)'}

다음 단계:
1. '에러 프롬프트 KB' 탭으로 이동
2. 새 패턴 추가 — pattern_id 작성
   추천: ${c.error_code || 'XXX'}_${(c.obj_name || 'CASE').toUpperCase()}_FIX
3. regex 작성 — 위 에러 메시지에 매칭되도록
4. fix_prompt 작성 — AI 가 다음에 안 깨지도록 가이드

본문이 클립보드에 복사됩니다.`
  if (caseDetail.value?.full_content) {
    navigator.clipboard.writeText(caseDetail.value.full_content).catch(() => {})
  }
  alert(hint)
}

onMounted(loadAll)
defineExpose({ loadAll, reloadCases })
</script>

<style scoped>
.kb-dashboard { padding: 16px; }

.summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.summary-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 16px; }
.summary-card.success { border-left: 3px solid #10b981; }
.summary-card.highlight { border-left: 3px solid #6366f1; background: linear-gradient(135deg, #eef2ff, #fff); }
.card-label { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.04em; }
.card-value { font-size: 28px; font-weight: 700; color: #0f172a; margin: 4px 0; }
.card-unit { font-size: 14px; color: #64748b; margin-left: 4px; font-weight: 400; }
.card-sub { font-size: 11px; color: #94a3b8; }

.panel { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 16px; margin-bottom: 16px; }
.panel h3 { margin: 0 0 8px; font-size: 14px; color: #0f172a; }
.panel.warning { border-left: 3px solid #f59e0b; }

.cat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; }
.cat-item { position: relative; padding: 6px 10px; background: #f8fafc; border-radius: 4px; font-size: 12px; }
.cat-name { color: #1e293b; font-weight: 500; }
.cat-count { color: #64748b; margin-left: 8px; }
.cat-bar { position: absolute; bottom: 0; left: 0; height: 2px; background: #6366f1; transition: width 0.3s; }

.kb-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.kb-table th, .kb-table td { padding: 6px 8px; text-align: left; border-bottom: 1px solid #f1f5f9; }
.kb-table th { background: #f8fafc; color: #475569; font-weight: 600; font-size: 11px; }
.kb-table .num { text-align: right; font-variant-numeric: tabular-nums; }
.kb-table .pattern-id { font-family: ui-monospace, monospace; color: #6366f1; }
.kb-table .ts { color: #94a3b8; font-size: 11px; }
.cat-badge { padding: 1px 6px; background: #f1f5f9; border-radius: 3px; font-size: 10px; color: #475569; }
.rate-high { color: #15803d; font-weight: 600; }
.rate-mid  { color: #b45309; font-weight: 600; }
.rate-low  { color: #b91c1c; font-weight: 600; }

.cases-panel { border-left: 3px solid #6366f1; }
.cases-header { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-bottom: 10px; }
.cases-header .muted { font-size: 11px; color: #64748b; margin: 0; }

.filter-row {
  display: flex; gap: 6px; align-items: center; flex-wrap: wrap;
  padding: 10px 0; border-bottom: 1px dashed #e2e8f0; margin-bottom: 10px;
}
.filter-input, .filter-select {
  padding: 5px 8px; font-size: 12px; border: 1px solid #cbd5e1;
  border-radius: 4px; background: #fff;
}
.search-input { flex: 1; min-width: 220px; }
.date-input { width: 130px; }
.filter-sep { color: #94a3b8; font-size: 12px; }
.filter-clear {
  padding: 5px 10px; background: #fee2e2; color: #991b1b;
  border: 1px solid #fca5a5; border-radius: 4px; cursor: pointer; font-size: 11.5px;
}

.result-bar { display: flex; gap: 12px; align-items: center; padding: 4px 0; }
.match-count { font-size: 12px; color: #6366f1; font-weight: 600; }
.loading-tag { font-size: 11px; color: #94a3b8; }

.groups-panel {
  background: #f0f9ff; border: 1px solid #bae6fd;
  border-radius: 6px; padding: 10px 12px; margin: 10px 0;
}
.groups-panel h4 { margin: 0 0 6px; font-size: 12px; color: #0c4a6e; }
.group-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 6px; }
.group-item {
  position: relative; padding: 5px 9px; background: #fff;
  border: 1px solid #bae6fd; border-radius: 4px; font-size: 11.5px;
  cursor: pointer; transition: background 0.1s;
}
.group-item:hover { background: #e0f2fe; }
.group-key { color: #0f172a; font-weight: 500; }
.group-count { color: #0284c7; margin-left: 6px; font-weight: 600; }
.group-bar { position: absolute; bottom: 0; left: 0; height: 2px; background: #0284c7; transition: width 0.3s; }

.cases-list { display: flex; flex-direction: column; gap: 4px; }
.case-item { background: #fff; border: 1px solid #e2e8f0; border-radius: 4px; }
.case-row {
  display: grid;
  grid-template-columns: 130px 70px 200px 50px 1fr 20px;
  gap: 8px; padding: 6px 10px; font-size: 11.5px; cursor: pointer; align-items: center;
}
.case-row:hover { background: #f8fafc; }
.case-ts { color: #64748b; font-family: ui-monospace, monospace; font-size: 10.5px; }
.case-obj-type {
  font-size: 9px; padding: 1px 5px; border-radius: 3px;
  font-weight: 600; text-align: center; text-transform: uppercase;
}
.case-obj-type.type-function    { background: #dcfce7; color: #15803d; border: 1px solid #86efac; }
.case-obj-type.type-procedure   { background: #ede9fe; color: #6d28d9; border: 1px solid #c4b5fd; }
.case-obj-type.type-trigger     { background: #fed7aa; color: #9a3412; border: 1px solid #fb923c; }
.case-obj-type.type-view        { background: #dbeafe; color: #1e40af; border: 1px solid #93c5fd; }
.case-obj-name { font-family: ui-monospace, monospace; color: #0f172a; font-weight: 500; }
.case-err-code {
  font-size: 10px; padding: 1px 5px; background: #fee2e2;
  color: #991b1b; border-radius: 3px; font-weight: 600; text-align: center;
}
.case-summary { color: #475569; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; }
.case-expand-ico { color: #94a3b8; font-size: 10px; text-align: center; }

.case-detail { padding: 10px 14px; background: #f8fafc; border-top: 1px solid #e2e8f0; }
.detail-loading { color: #94a3b8; font-size: 12px; padding: 8px; text-align: center; }
.detail-actions { display: flex; gap: 8px; margin-bottom: 8px; }
.action-btn {
  padding: 4px 10px; background: #fff; border: 1px solid #cbd5e1;
  border-radius: 4px; cursor: pointer; font-size: 11.5px; color: #475569;
}
.action-btn:hover { background: #f1f5f9; }
.action-btn.primary { background: #eef2ff; border-color: #c7d2fe; color: #4338ca; font-weight: 500; }
.detail-body {
  background: #0f172a; color: #e2e8f0; padding: 10px;
  font-size: 11px; font-family: ui-monospace, monospace;
  border-radius: 4px; max-height: 400px; overflow: auto;
  white-space: pre-wrap; word-break: break-word;
}

.empty-cases { padding: 30px; text-align: center; color: #94a3b8; font-size: 12px; }
.empty { padding: 30px; text-align: center; color: #94a3b8; }
.btn-reload { padding: 6px 14px; background: #6366f1; color: #fff; border: 0; border-radius: 4px; cursor: pointer; }
.loading { padding: 30px; text-align: center; color: #94a3b8; }

.unmatched-list { list-style: none; padding: 0; margin: 0; }
.unmatched-item { padding: 6px 0; border-bottom: 1px solid #f1f5f9; font-size: 11px; }
.unmatched-item code { background: #fef3c7; padding: 1px 5px; border-radius: 3px; color: #92400e; }
</style>
