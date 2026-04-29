<template>
  <div>
    <!-- 필터 바 -->
    <div class="card filter-bar">
      <div class="fb-group">
        <span class="fb-label">소스 DB</span>
        <div class="sel-w"><select v-model="srcF"><option value="">전체</option><option v-for="d in allDbs" :key="d.v" :value="d.v">{{ d.n }}</option></select><Chev/></div>
      </div>
      <!-- v10 #32: 양방향 스왑 버튼 (ObjectMapping 과 동일) -->
      <button v-if="srcF&&tgtF" class="swap-btn" @click="swapDb" title="소스↔타겟 교환">⇄</button>
      <div class="fb-group">
        <span class="fb-label">타겟 DB</span>
        <div class="sel-w"><select v-model="tgtF"><option value="">전체</option><option v-for="d in allDbs" :key="d.v" :value="d.v">{{ d.n }}</option></select><Chev/></div>
      </div>
      <div class="fb-group">
        <span class="fb-label">카테고리</span>
        <div class="sel-w"><select v-model="catF"><option value="">전체</option><option v-for="c in categories" :key="c" :value="c">{{ c }}</option></select><Chev/></div>
      </div>
      <input type="text" v-model="typeQ" placeholder="타입명·키워드 검색..." class="search-input"/>
      <!-- 빠른 필터 토글 -->
      <div class="quick-filters">
        <button class="qf-btn" :class="{active:qfWarn}"    @click="qfWarn=!qfWarn">⚠ 주의 필요</button>
        <button class="qf-btn" :class="{active:qfCustom}"  @click="qfCustom=!qfCustom">✎ 커스텀</button>
        <button class="qf-btn" :class="{active:qfPairOnly&&pairKey}" @click="qfPairOnly=!qfPairOnly" :disabled="!srcF||!tgtF" :title="srcF&&tgtF?'현재 소스→타겟 조합만':'소스+타겟 DB를 먼저 선택하세요'">
          🔗 이 조합만
        </button>
      </div>
      <div class="fb-right">
        <span class="total-badge">{{ filtered.length }}개 규칙</span>
        <button class="btn" @click="openAdd">+ 규칙 추가</button>
        <button class="btn" @click="seedDefaults" :disabled="seeding" title="시스템 내장 283개 기본 규칙을 병합 (중복은 건너뜀)">
          <span v-if="seeding" class="spinner" style="width:12px;height:12px"/>
          📦 기본 규칙 시드
        </button>
        <button class="btn" @click="load" title="서버에서 다시 불러오기">↻ 새로고침</button>
      </div>
    </div>

    <!-- 통계 키트 (v10 #32: 서버 /stats API 기반, ObjectMapping 과 동일) -->
    <div class="kpi-row">
      <div class="kpi"><div class="kpi-n info">{{ stats.total }}</div><div class="kpi-l">전체 규칙</div></div>
      <div class="kpi"><div class="kpi-n">{{ stats.pairs }}</div><div class="kpi-l">DB 조합</div></div>
      <div class="kpi"><div class="kpi-n warn">{{ stats.warning }}</div><div class="kpi-l">주의 필요</div></div>
      <div class="kpi"><div class="kpi-n ok">{{ stats.custom }}</div><div class="kpi-l">커스텀</div></div>
      <div class="kpi"><div class="kpi-n ai">{{ stats.ai_learned || 0 }}</div><div class="kpi-l">🤖 AI 학습</div></div>
    </div>

    <!-- v10 #32: 카테고리 탭 (ObjectMapping 의 obj-tabs 와 동일 패턴) -->
    <div class="cat-tabs">
      <button class="otab" :class="{active:catF===''}" @click="catF=''">전체 ({{ stats.total }})</button>
      <button v-for="(cnt, cat) in stats.by_category" :key="cat"
        class="otab" :class="{active:catF===cat}" @click="catF=cat">
        {{ CAT_ICON[cat] || '📂' }} {{ cat }} <span class="otab-cnt">{{ cnt }}</span>
      </button>
    </div>

    <!-- 테이블 -->
    <div class="tbl-outer">
      <!-- v10: 스크롤 진행률 인디케이터 (긴 목록 시 도움) -->
      <div v-if="filtered.length > 30" class="tbl-scroll-ind" :title="`${Math.round(tblScrollProgress)}% 위치 · ${filtered.length}건`">
        <div class="tbl-scroll-ind-fill" :style="{width: tblScrollProgress+'%'}"></div>
      </div>

      <div class="card tbl-wrap" ref="tblWrapRef">
        <table class="map-tbl">
          <thead>
            <tr>
              <th @click="setSort('category')" class="sortable">카테고리<SortIco :col="'category'" :sort="sortCol" :dir="sortDir"/></th>
              <th @click="setSort('src_db')" class="sortable">소스 DB<SortIco :col="'src_db'" :sort="sortCol" :dir="sortDir"/></th>
              <th @click="setSort('src_type')" class="sortable">소스 타입<SortIco :col="'src_type'" :sort="sortCol" :dir="sortDir"/></th>
              <th @click="setSort('tgt_db')" class="sortable">타겟 DB<SortIco :col="'tgt_db'" :sort="sortCol" :dir="sortDir"/></th>
              <th @click="setSort('tgt_type')" class="sortable">타겟 타입<SortIco :col="'tgt_type'" :sort="sortCol" :dir="sortDir"/></th>
              <th @click="setSort('note')" class="sortable">주의사항<SortIco :col="'note'" :sort="sortCol" :dir="sortDir"/></th><th>출처</th><th>커스텀</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in filtered" :key="r.id" :class="{warn:r.warning}">
              <td><span class="cat-chip" :style="catStyle(r.category)">{{ r.category }}</span></td>
              <td><span class="dbc" :style="{background:m(r.src_db)?.bg,color:m(r.src_db)?.color}">{{ m(r.src_db)?.label||r.src_db }}</span></td>
              <td><span class="type-src">{{ r.src_type }}</span></td>
              <td><span class="dbc" :style="{background:m(r.tgt_db)?.bg,color:m(r.tgt_db)?.color}">{{ m(r.tgt_db)?.label||r.tgt_db }}</span></td>
              <td><span class="type-tgt">{{ r.tgt_type }}</span></td>
              <td>
                <span v-if="r.note" class="note-chip" :class="r.warning?'w':'i'">{{ r.note }}</span>
                <span v-else class="no-note">—</span>
              </td>
              <td>
                <span v-if="(r.source||'manual') === 'ai_learned'"
                      class="src-badge ai"
                      :class="{shadow: r.status==='shadow', rejected: r.status==='rejected'}"
                      :title="`confidence: ${r.confidence||0} · ${r.status||'active'} · 최근 ${r.last_seen||'-'}`">
                  🤖 AI 학습
                  <small v-if="r.confidence">×{{ r.confidence }}</small>
                </span>
                <span v-else class="src-badge manual" title="수동 등록 규칙">✍ 수동</span>
              </td>
              <td><div class="toggle" :class="{on:r.custom}" @click="r.custom=!r.custom; markDirty(r)"></div></td>
              <td>
                <div style="display:flex;gap:4px;flex-wrap:nowrap;white-space:nowrap">
                  <button class="act-btn" style="color:var(--text-info)" @click="openEdit(r)">편집</button>
                  <button class="act-btn del" @click="deleteRule(r)">삭제</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 추가/편집 모달 (v10 #19) -->
    <div v-if="modal.show" class="modal-overlay" @click.self="modal.show=false">
      <div class="modal">
        <div class="modal-title">{{ modal.isEdit ? '타입 매핑 규칙 편집' : '변환 규칙 추가' }}</div>
        <div class="modal-grid">
          <div>
            <div class="field-label">소스 DB</div>
            <div class="sel-w"><select v-model="modal.f.src_db"><option v-for="d in allDbs" :key="d.v" :value="d.v">{{ d.n }}</option></select><Chev/></div>
          </div>
          <div>
            <div class="field-label">소스 타입</div>
            <input v-model="modal.f.src_type" placeholder="예) NVARCHAR(n)"/>
          </div>
          <div>
            <div class="field-label">타겟 DB</div>
            <div class="sel-w"><select v-model="modal.f.tgt_db"><option v-for="d in allDbs" :key="d.v" :value="d.v">{{ d.n }}</option></select><Chev/></div>
          </div>
          <div>
            <div class="field-label">타겟 타입</div>
            <input v-model="modal.f.tgt_type" placeholder="예) VARCHAR({n})"/>
          </div>
          <div>
            <div class="field-label">카테고리</div>
            <div class="sel-w"><select v-model="modal.f.category"><option v-for="c in categories" :key="c" :value="c">{{ c }}</option></select><Chev/></div>
          </div>
          <div>
            <div class="field-label">주의사항 (선택)</div>
            <input v-model="modal.f.note" placeholder="데이터 손실 가능 등"/>
          </div>
          <div style="grid-column:1/-1;display:flex;align-items:center;gap:16px;flex-wrap:wrap">
            <label class="chk-label">
              <input type="checkbox" v-model="modal.f.warning" style="accent-color:var(--accent-orange)"/> ⚠ 주의 표시
            </label>
            <label class="chk-label">
              <input type="checkbox" v-model="modal.f.custom"/> ✎ 커스텀 규칙
            </label>
          </div>
          <!-- 편집 모드 전용: AI 학습 규칙 메타 정보 -->
          <div v-if="modal.isEdit && modal.f.source === 'ai_learned'" style="grid-column:1/-1" class="ai-meta-box">
            <div class="field-label">🤖 AI 학습 규칙 정보</div>
            <div class="meta-grid">
              <span>상태: <b>{{ modal.f.status || 'active' }}</b></span>
              <span>confidence: <b>{{ modal.f.confidence || 0 }}</b></span>
              <span>최초 학습: <b>{{ modal.f.first_seen || '-' }}</b></span>
              <span>최근 학습: <b>{{ modal.f.last_seen || '-' }}</b></span>
            </div>
          </div>
        </div>
        <div class="modal-btns">
          <button class="btn" @click="modal.show=false">취소</button>
          <button class="btn btn-primary" @click="submitRule">
            {{ modal.isEdit ? '수정 저장' : '규칙 추가' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, h } from 'vue'
import axios from 'axios'
import { useAppStore } from '@/store/appStore.js'
import { DB_META } from '@/constants/dbMeta.js'

const app = useAppStore()
const srcF = ref(''), tgtF = ref(''), catF = ref(''), typeQ = ref('')
const qfWarn     = ref(false)
const qfCustom   = ref(false)
const qfPairOnly = ref(false)
const sortCol    = ref('src_db')
const sortDir    = ref('asc')  // 'asc' | 'desc'

// v10 #32: 서버 stats 상태 (ObjectMapping 과 동일 구조)
const stats = ref({ total:0, pairs:0, warning:0, custom:0, ai_learned:0, by_category:{} })

const pairKey = computed(() => srcF.value && tgtF.value ? `${srcF.value}→${tgtF.value}` : '')

function setSort(col) {
  if (sortCol.value === col) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else { sortCol.value = col; sortDir.value = 'asc' }
}

// v10 #32: 소스 ↔ 타겟 스왑 (ObjectMapping 과 동일)
function swapDb() {
  const t = srcF.value
  srcF.value = tgtF.value
  tgtF.value = t
}

// v10 #32: 카테고리별 아이콘 매핑 (ObjectMapping 의 OBJ_ICON 패턴)
const CAT_ICON = {
  '문자열': '🔤', '숫자': '🔢', '날짜시간': '📅', '부울': '☑',
  '바이너리': '💾', 'JSON-XML': '📄', '날짜함수': '🕐',
  '문자열함수': '✂️', '페이징': '📃', 'DDL문법': '🏗️',
  '식별자': '🔖', 'CREATE TABLE': '🗂️', 'SYNTAX': '⚙️',
}

// v10 #32: 카테고리 색상 팔레트 + 안정적 해시 매핑 (ObjectMapping 과 동일)
const CAT_COLORS = [
  { bg:'#e0e7ff', color:'#3730a3' },
  { bg:'#fef3c7', color:'#92400e' },
  { bg:'#d1fae5', color:'#065f46' },
  { bg:'#fce7f3', color:'#9f1239' },
  { bg:'#e0f2fe', color:'#075985' },
  { bg:'#f3e8ff', color:'#6b21a8' },
  { bg:'#fef9c3', color:'#854d0e' },
  { bg:'#ffe4e6', color:'#9f1239' },
  { bg:'#ccfbf1', color:'#115e59' },
  { bg:'#e0e7ff', color:'#4338ca' },
]
function _hashStr(s) {
  let h = 0
  for (let i=0; i<s.length; i++) h = ((h<<5)-h) + s.charCodeAt(i) | 0
  return Math.abs(h)
}
function catStyle(cat) {
  const c = CAT_COLORS[_hashStr(cat||'') % CAT_COLORS.length]
  return { background: c.bg, color: c.color }
}

// SortIco 컴포넌트 (v10 #19 hotfix2 — render 함수로 변경, 런타임 컴파일러 불필요)
const SortIco = {
  props: ['col', 'sort', 'dir'],
  setup(props) {
    return () => h(
      'span',
      { style: 'margin-left:4px;font-size:10px;opacity:.6;display:inline-block' },
      props.col === props.sort
        ? (props.dir === 'asc' ? '▲' : '▼')
        : h('span', { style: 'opacity:.3' }, '⇅')
    )
  },
}
// ── 모달 상태 (v10 #19 — 추가/편집 겸용) ──
const modal = reactive({
  show: false,
  isEdit: false,
  f: {},
})
function _blankRule() {
  return {
    src_db: srcF.value || 'mysql',
    tgt_db: tgtF.value || 'mssql',
    src_type: '', tgt_type: '',
    category: catF.value || '문자열',
    note: '', warning: false, custom: true,
  }
}
function openAdd() {
  modal.isEdit = false
  modal.f = _blankRule()
  modal.show = true
}
function openEdit(r) {
  modal.isEdit = true
  // 깊은 복사 (직접 참조 시 취소해도 목록에 반영되어 버림)
  modal.f = JSON.parse(JSON.stringify(r))
  modal.show = true
}

// Chev 아이콘 (v10 #19 hotfix2 — innerHTML 방식, SVG 네임스페이스 안전)
const _CHEV_SVG = '<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg>'
const Chev = {
  setup() {
    return () => h('div', { class: 'chev-ico', innerHTML: _CHEV_SVG })
  },
}

const m = t => DB_META[t] || { label: t?.toUpperCase().slice(0,3)||'??', bg:'#e8e8e8', color:'#555' }

// v10: 스크롤 진행률 추적
const tblWrapRef = ref(null)
const tblScrollProgress = ref(0)
function updateTblScroll() {
  const el = tblWrapRef.value
  if (!el) { tblScrollProgress.value = 0; return }
  const max = el.scrollHeight - el.clientHeight
  if (max <= 0) { tblScrollProgress.value = 0; return }
  tblScrollProgress.value = Math.min(100, Math.max(0, (el.scrollTop / max) * 100))
}
onMounted(() => {
  setTimeout(() => {
    const el = tblWrapRef.value
    if (el) {
      el.addEventListener('scroll', updateTblScroll, { passive: true })
      updateTblScroll()
    }
  }, 100)
})
onUnmounted(() => {
  const el = tblWrapRef.value
  if (el) el.removeEventListener('scroll', updateTblScroll)
})

const allDbs = [
  {v:'mysql',n:'MySQL/MariaDB'},{v:'mssql',n:'SQL Server'},{v:'oracle',n:'Oracle'},
  {v:'postgresql',n:'PostgreSQL'},{v:'db2',n:'IBM DB2'},{v:'sybase',n:'Sybase ASE'},
  {v:'snowflake',n:'Snowflake'},{v:'bigquery',n:'BigQuery'},{v:'redshift',n:'Redshift'},
  {v:'clickhouse',n:'ClickHouse'},{v:'mongodb',n:'MongoDB'},{v:'sqlite',n:'SQLite'},
]

// ══════════════════════════════════════════════════════════
// 백엔드 연동 — v10 #19 (하드코딩 제거, REST API 기반)
// ══════════════════════════════════════════════════════════
const rules = ref([])

async function load() {
  try {
    // v10 #32: stats API 도 함께 호출 (ObjectMapping 과 동일 패턴)
    const [rRes, cRes, sRes] = await Promise.all([
      axios.get('/api/v1/mapping/rules'),
      axios.get('/api/v1/mapping/categories'),
      axios.get('/api/v1/mapping/stats'),
    ])
    rules.value = Array.isArray(rRes.data) ? rRes.data : []
    _serverCategories.value = Array.isArray(cRes.data) ? cRes.data : []
    stats.value = sRes.data || { total:0, pairs:0, warning:0, custom:0, ai_learned:0, by_category:{} }
  } catch (e) {
    app.notify('타입 매핑 로드 실패: ' + (e.response?.data?.detail || e.message), 'error')
  }
}
const _serverCategories = ref([])

async function submitRule() {
  if (!modal.f.src_type || !modal.f.tgt_type) {
    app.notify('소스/타겟 타입을 입력하세요', 'error'); return
  }
  try {
    if (modal.isEdit) {
      const res = await axios.put(`/api/v1/mapping/rules/${modal.f.id}`, modal.f)
      const idx = rules.value.findIndex(r => r.id === modal.f.id)
      if (idx >= 0) rules.value[idx] = res.data
      app.notify('수정 저장됨', 'success')
    } else {
      const res = await axios.post('/api/v1/mapping/rules', modal.f)
      rules.value.push(res.data)
      app.notify('규칙 추가됨', 'success')
    }
    modal.show = false
  } catch (e) {
    app.notify('저장 실패: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

async function deleteRule(r) {
  const label = `${r.src_db} → ${r.tgt_db} : ${r.src_type} → ${r.tgt_type}`
  if (!confirm(`다음 규칙을 삭제하시겠습니까?\n\n${label}`)) return
  try {
    await axios.delete(`/api/v1/mapping/rules/${r.id}`)
    rules.value = rules.value.filter(x => x.id !== r.id)
    app.notify('삭제됨', 'info')
  } catch (e) {
    app.notify('삭제 실패: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

// ── 기본 규칙 시드 (v10 #19b) ────────────────────────
const seeding = ref(false)
async function seedDefaults() {
  if (!confirm(
    '시스템 내장 기본 타입 매핑 규칙 283개를 병합합니다.\n\n' +
    '• 이미 있는 규칙(소스DB+타겟DB+소스타입 동일)은 건너뜁니다\n' +
    '• 새 규칙만 추가되며 기존 사용자 수정본은 보존됩니다\n\n' +
    '계속하시겠습니까?'
  )) return
  seeding.value = true
  try {
    const { data } = await axios.post('/api/v1/mapping/seed-defaults')
    const msg = `기본 규칙 병합 완료 — 추가 ${data.inserted}개, 건너뜀 ${data.skipped}개, 총 ${data.total_after}개`
    app.notify(msg, 'success')
    // 건너뛴 규칙이 있고 아무것도 추가되지 않았다면 → 전체 덮어쓰기 제안
    if (data.inserted === 0 && data.skipped > 0) {
      if (confirm(
        `모든 규칙이 이미 존재해서 추가된 것이 없습니다.\n` +
        `시스템 기본값으로 전체 갱신하시겠습니까? (카테고리/주의사항/타입 표기가 최신 값으로 업데이트됨)\n\n` +
        `※ 사용자 '커스텀' 플래그는 유지됩니다.`
      )) {
        const { data: d2 } = await axios.post('/api/v1/mapping/seed-defaults?overwrite=true')
        app.notify(
          `전체 갱신 완료 — 갱신 ${d2.overwritten}개, 총 ${d2.total_after}개`,
          'success'
        )
      }
    }
    await load()
  } catch (e) {
    app.notify('시드 실패: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    seeding.value = false
  }
}

// 인라인 토글(커스텀) 즉시 저장 — ObjectMapping 과 동일 UX
function markDirty(r) {
  // 토글 직후 서버 반영
  axios.put(`/api/v1/mapping/rules/${r.id}`, r).catch(e => {
    app.notify('저장 실패: ' + (e.response?.data?.detail || e.message), 'error')
  })
}

// ── 파생 데이터 ────────────────────────────────────────
const categories = computed(() => {
  // 서버 목록 + 현재 rules 에서 추출한 것 합집합
  const set = new Set(_serverCategories.value)
  for (const r of rules.value) if (r.category) set.add(r.category)
  return [...set].sort((a,b) => a.localeCompare(b, 'ko'))
})

const pairCount = computed(() => new Set(rules.value.map(r=>`${r.src_db}→${r.tgt_db}`)).size)

const filtered = computed(() => {
  let result = rules.value.filter(r => {
    if (srcF.value && r.src_db !== srcF.value) return false
    if (tgtF.value && r.tgt_db !== tgtF.value) return false
    if (catF.value && r.category !== catF.value) return false
    if (typeQ.value) {
      const q = typeQ.value.toLowerCase()
      if (!(r.src_type||'').toLowerCase().includes(q) &&
          !(r.tgt_type||'').toLowerCase().includes(q)) return false
    }
    if (qfWarn.value && !r.warning) return false
    if (qfCustom.value && !r.custom) return false
    if (qfPairOnly.value && pairKey.value) {
      if (r.src_db !== srcF.value || r.tgt_db !== tgtF.value) return false
    }
    return true
  })
  const col = sortCol.value, dir = sortDir.value
  result = [...result].sort((a,b) => {
    const av = (a[col]||'').toString().toLowerCase()
    const bv = (b[col]||'').toString().toLowerCase()
    return dir === 'asc' ? av.localeCompare(bv,'ko') : bv.localeCompare(av,'ko')
  })
  return result
})

// 초기 로드
onMounted(load)
</script>

<style scoped>
.filter-bar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:10px 14px;margin-bottom:10px}
.fb-group{display:flex;align-items:center;gap:6px}
.fb-label{font-size:11.5px;color:var(--text-secondary);white-space:nowrap}
.sel-w{position:relative;min-width:140px}
.sel-w select{width:100%;appearance:none;-webkit-appearance:none;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:var(--radius-md);padding:6px 28px 6px 10px;font-size:12px;color:var(--text-primary);cursor:pointer;font-family:var(--font)}
.sel-w select:focus{outline:none;border-color:var(--accent-blue)}
.chev-ico{position:absolute;right:8px;top:50%;transform:translateY(-50%);pointer-events:none;color:var(--text-tertiary)}
.chev-ico svg{width:10px;height:10px;display:block}
.search-input{padding:6px 10px;font-size:12px;width:160px;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:var(--radius-md);color:var(--text-primary);font-family:var(--font)}
.search-input:focus{outline:none;border-color:var(--accent-blue)}
.fb-right{display:flex;align-items:center;gap:8px;margin-left:auto}
.quick-filters{display:flex;gap:5px;flex-wrap:wrap}
.qf-btn{padding:4px 10px;border-radius:var(--radius-md);border:0.5px solid var(--border-mid);background:transparent;cursor:pointer;font-size:11.5px;font-family:var(--font);color:var(--text-secondary);transition:all .12s;white-space:nowrap}
.qf-btn:hover{background:var(--bg-secondary)}
.qf-btn.active{background:var(--bg-warning);color:var(--text-warning);border-color:var(--text-warning)}
.qf-btn:disabled{opacity:.4;cursor:not-allowed}
.sortable{cursor:pointer;user-select:none;white-space:nowrap}
.sortable:hover{color:var(--text-primary);background:var(--bg-primary)}
.total-badge{font-size:11px;background:var(--bg-info);color:var(--text-info);padding:2px 10px;border-radius:8px;font-weight:500}
.btn{display:inline-flex;align-items:center;gap:4px;padding:6px 12px;border-radius:var(--radius-md);font-size:12px;font-weight:500;font-family:var(--font);cursor:pointer;transition:all .12s;border:0.5px solid var(--border-mid);background:transparent;color:var(--text-secondary)}
.btn:hover{background:var(--bg-secondary);color:var(--text-primary)}
.btn-primary{background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue)}
.btn-primary:hover{background:var(--accent-blue);color:#fff}

.kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:10px}
.kpi{background:var(--bg-primary);border:0.5px solid var(--border-light);border-radius:var(--radius-lg);padding:12px 16px;text-align:center}
.kpi-n{font-size:22px;font-weight:700;color:var(--text-primary)}.kpi-n.warn{color:var(--text-warning)}.kpi-n.info{color:var(--text-info)}.kpi-n.ok{color:var(--text-success)}
.kpi-l{font-size:10.5px;color:var(--text-tertiary);margin-top:2px}

/* v10: 테이블 외곽 + 진행률 인디케이터 */
.tbl-outer{ display: block; }
.tbl-scroll-ind{
  height: 3px;
  background: var(--bg-tertiary, #f3f4f6);
  border-radius: 2px;
  overflow: hidden;
  margin: 0 0 4px;
}
.tbl-scroll-ind-fill{
  height: 100%;
  background: linear-gradient(90deg, var(--accent-blue, #2563eb), var(--accent-green, #22c55e));
  transition: width .15s;
  border-radius: 2px;
}

/* v10: 자체 스크롤 + 굵은 스크롤바 + sticky 헤더 */
.tbl-wrap{
  padding:0;
  overflow-y:auto;
  overflow-x:auto;
  max-height: calc(100vh - 280px);
  min-height: 240px;
  scrollbar-width: auto;
  scrollbar-color: var(--border-strong, #9ca3af) var(--bg-tertiary, #f3f4f6);
  position: relative;
}
@media(max-width: 900px){
  .tbl-wrap{ max-height: calc(100vh - 340px) }
}
.tbl-wrap::-webkit-scrollbar{ width:14px; height:14px }
.tbl-wrap::-webkit-scrollbar-track{
  background: var(--bg-tertiary, #f3f4f6);
  border-left: 1px solid var(--border-light, #e5e7eb);
}
.tbl-wrap::-webkit-scrollbar-thumb{
  background: var(--border-strong, #9ca3af);
  border: 3px solid var(--bg-tertiary, #f3f4f6);
  border-radius: 7px;
  min-height: 40px;
}
.tbl-wrap::-webkit-scrollbar-thumb:hover{ background: var(--text-tertiary, #6b7280) }
.tbl-wrap::-webkit-scrollbar-thumb:active{ background: var(--accent-blue, #2563eb) }
.tbl-wrap::-webkit-scrollbar-corner{ background: var(--bg-tertiary, #f3f4f6) }

.map-tbl{width:100%;border-collapse:collapse;font-size:12px}
.map-tbl thead{
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--bg-secondary);
}
.map-tbl th{background:var(--bg-secondary);padding:8px 12px;text-align:left;font-size:11px;font-weight:600;color:var(--text-tertiary);border-bottom:0.5px solid var(--border-mid);white-space:nowrap}
.map-tbl td{padding:7px 12px;border-bottom:0.5px solid var(--border-light);vertical-align:middle}
.map-tbl tr:last-child td{border-bottom:none}
.map-tbl tr:hover td{background:var(--bg-secondary)}
.map-tbl tr.warn td{background:rgba(234,179,8,.04)}

.cat-chip{font-size:10px;padding:2px 7px;border-radius:4px;font-weight:500;background:var(--bg-tertiary);color:var(--text-secondary)}
.cat-chip.문자열{background:#f0f4ff;color:#2563eb}.cat-chip.숫자{background:#f0fdf4;color:#16a34a}
.cat-chip.날짜시간{background:#fff7ed;color:#c2410c}.cat-chip.바이너리{background:#fdf4ff;color:#7e22ce}
.cat-chip.부울{background:#f0f9ff;color:#0369a1}.cat-chip.JSON-XML{background:#fefce8;color:#a16207}
.cat-chip.공간{background:#ecfdf5;color:#065f46}.cat-chip.기타{background:#f9fafb;color:#6b7280}

.dbc{display:inline-block;font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px}
.type-src{font-family:'Consolas','SF Mono',monospace;font-size:12px;color:var(--text-info);background:var(--bg-info);padding:2px 7px;border-radius:4px}
.type-tgt{font-family:'Consolas','SF Mono',monospace;font-size:12px;color:var(--text-success);background:var(--bg-success);padding:2px 7px;border-radius:4px}
.note-chip{font-size:11px;padding:2px 7px;border-radius:4px}
.note-chip.w{background:var(--bg-warning);color:var(--text-warning)}.note-chip.i{background:var(--bg-info);color:var(--text-info)}
.no-note{color:var(--text-tertiary);font-size:12px}

.toggle{position:relative;width:32px;height:17px;background:var(--border-mid);border-radius:9px;cursor:pointer;transition:background .2s;flex-shrink:0}
.toggle.on{background:var(--accent-blue)}
.toggle::after{content:'';position:absolute;top:2px;left:2px;width:13px;height:13px;border-radius:50%;background:white;transition:transform .2s}
.toggle.on::after{transform:translateX(15px)}
.del-btn{background:transparent;border:none;cursor:pointer;color:var(--text-tertiary);padding:3px 7px;border-radius:var(--radius-sm);transition:all .12s;font-size:12px}
.del-btn:hover{background:var(--bg-danger);color:var(--text-danger)}

.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;z-index:999}
.modal{background:var(--bg-primary);border-radius:var(--radius-lg);padding:20px;width:480px;border:0.5px solid var(--border-mid)}
.modal-title{font-size:14px;font-weight:600;color:var(--text-primary);margin-bottom:14px}
.modal-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.field-label{font-size:11px;font-weight:500;color:var(--text-secondary);margin-bottom:4px;margin-top:6px}
input[type="text"]{width:100%;padding:7px 10px;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:var(--radius-md);font-size:12px;color:var(--text-primary);font-family:var(--font)}
input[type="text"]:focus{outline:none;border-color:var(--accent-blue)}
.modal-btns{display:flex;justify-content:flex-end;gap:8px;margin-top:14px}
/* ── 출처 뱃지 (v10 #18) ─────────────────────────────── */
.src-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}
.src-badge.manual { background: #dbeafe; color: #1e40af; }
.src-badge.ai { background: #d1fae5; color: #065f46; }
.src-badge.ai.shadow { background: #fef3c7; color: #92400e; }
.src-badge.ai.rejected { background: #f3f4f6; color: #6b7280; text-decoration: line-through; }
.src-badge small { font-size: 10px; opacity: 0.8; font-weight: 500; }

/* ── 편집/삭제 버튼 + 체크박스 + AI 메타 박스 (v10 #19) ── */
.act-btn {
  padding: 3px 10px; font-size: 11.5px;
  border: 0.5px solid var(--border-mid); border-radius: var(--radius-sm);
  background: var(--bg-secondary); color: var(--text-secondary);
  cursor: pointer; white-space: nowrap;
  transition: background .12s, color .12s, border-color .12s;
}
.act-btn:hover { background: var(--bg-hover); color: var(--text-primary); border-color: var(--accent-blue); }
.act-btn.del { color: var(--text-danger, #dc2626); }
.act-btn.del:hover { background: var(--bg-danger, #fef2f2); border-color: var(--text-danger, #dc2626); }

.chk-label { display: flex; align-items: center; gap: 6px; font-size: 12px; cursor: pointer; color: var(--text-secondary); }

.ai-meta-box {
  padding: 10px 12px;
  background: var(--bg-secondary);
  border: 0.5px solid var(--border-light);
  border-left: 3px solid #10b981;
  border-radius: var(--radius-md);
  margin-top: 6px;
}
.meta-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px 14px;
  font-size: 11.5px;
  color: var(--text-secondary);
  margin-top: 4px;
}
.meta-grid b { color: var(--text-primary); font-weight: 600; }

/* 모달 버튼 기본 스타일 (페이지에서 누락된 경우 대비) */
.modal-btns .btn {
  padding: 7px 18px; border-radius: var(--radius-md); font-size: 12.5px;
  border: 0.5px solid var(--border-mid); background: var(--bg-secondary);
  color: var(--text-primary); cursor: pointer;
}
.modal-btns .btn:hover { background: var(--bg-hover); }
.modal-btns .btn-primary { background: var(--accent-blue); border-color: var(--accent-blue); color: #fff; }
.modal-btns .btn-primary:hover { filter: brightness(1.1); }

/* ════════════════════════════════════════════════════════════
 * v10 #32: ObjectMapping 과 UI 통일용 추가 스타일
 * ════════════════════════════════════════════════════════════ */

/* 소스↔타겟 스왑 버튼 */
.swap-btn {
  background: var(--bg-secondary);
  border: 0.5px solid var(--border-mid);
  border-radius: var(--radius-md);
  padding: 4px 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-secondary);
  transition: all .12s;
}
.swap-btn:hover {
  background: var(--bg-info);
  color: var(--text-info);
}

/* 카테고리 탭 바 */
.cat-tabs {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin: 10px 0;
}
.otab {
  font-size: 11px;
  padding: 5px 10px;
  border-radius: var(--radius-md);
  border: 0.5px solid var(--border-mid);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  cursor: pointer;
  font-family: var(--font);
  transition: all .12s;
  white-space: nowrap;
}
.otab:hover { background: var(--bg-primary); }
.otab.active {
  background: var(--bg-info);
  color: var(--text-info);
  border-color: var(--accent-blue);
  font-weight: 500;
}
.otab-cnt {
  background: var(--accent-blue);
  color: #fff;
  font-size: 9px;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 6px;
  margin-left: 3px;
}

/* KPI 카드의 AI 학습 숫자 색상 (기존 info/warn/ok 와 구분) */
.kpi-n.ai { color: #065f46; }
</style>
