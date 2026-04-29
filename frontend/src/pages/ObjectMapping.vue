<template>
  <div>
    <div class="page-title">오브젝트 매핑 관리</div>
    <div class="page-desc">
      테이블·인덱스·제약조건·프로시저·함수·트리거·뷰·시퀀스·쿼리문법·내장함수·트랜잭션·예외처리·커서·임시테이블·동적SQL·권한
      — 모든 DB 오브젝트 변환 규칙 양방향 관리
    </div>

    <!-- 필터 바 -->
    <div class="card filter-bar">
      <div class="fb-group">
        <span class="fb-label">소스 DB</span>
        <div class="sel-w"><select v-model="srcF">
          <option value="">전체</option>
          <option v-for="d in ALL_DBS" :key="d.v" :value="d.v">{{ d.n }}</option>
        </select><Chev/></div>
      </div>
      <button v-if="srcF&&tgtF" class="swap-btn" @click="swapDb" title="소스↔타겟 교환">⇄</button>
      <div class="fb-group">
        <span class="fb-label">타겟 DB</span>
        <div class="sel-w"><select v-model="tgtF">
          <option value="">전체</option>
          <option v-for="d in ALL_DBS" :key="d.v" :value="d.v">{{ d.n }}</option>
        </select><Chev/></div>
      </div>
      <div class="fb-group">
        <span class="fb-label">오브젝트 타입</span>
        <div class="sel-w"><select v-model="objF">
          <option value="">전체</option>
          <option v-for="o in objTypes" :key="o" :value="o">{{ o }}</option>
        </select><Chev/></div>
      </div>
      <div class="fb-group">
        <span class="fb-label">카테고리</span>
        <div class="sel-w"><select v-model="catF">
          <option value="">전체</option>
          <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
        </select><Chev/></div>
      </div>
      <input type="text" v-model="q" placeholder="구문·키워드 검색..." class="search-input"/>
      <div class="quick-filters">
        <button class="qf-btn" :class="{active:qfWarn}"   @click="qfWarn=!qfWarn">⚠ 주의</button>
        <button class="qf-btn" :class="{active:qfCustom}" @click="qfCustom=!qfCustom">✎ 커스텀</button>
        <button class="qf-btn" :class="{active:qfPair&&pairKey}"
          @click="qfPair=!qfPair" :disabled="!srcF||!tgtF" title="현재 조합만">🔗 이 조합만</button>
      </div>
      <div class="fb-right">
        <span class="total-badge">{{ filtered.length }}개 규칙</span>
        <button class="btn" @click="openAdd">+ 규칙 추가</button>
        <button class="btn btn-primary" @click="saveAll" :disabled="saving">
          <span v-if="saving" class="spinner" style="width:12px;height:12px"/>저장
        </button>
      </div>
    </div>

    <!-- KPI 요약 -->
    <div class="kpi-row">
      <div class="kpi"><div class="kpi-n info">{{ stats.total }}</div><div class="kpi-l">전체 규칙</div></div>
      <div class="kpi"><div class="kpi-n">{{ stats.pairs }}</div><div class="kpi-l">DB 조합</div></div>
      <div class="kpi"><div class="kpi-n warn">{{ stats.warning }}</div><div class="kpi-l">주의 필요</div></div>
      <div class="kpi"><div class="kpi-n ok">{{ stats.custom }}</div><div class="kpi-l">커스텀</div></div>
    </div>

    <!-- 오브젝트 타입별 탭 -->
    <div class="obj-tabs">
      <button class="otab" :class="{active:objF===''}" @click="objF=''">전체 ({{ stats.total }})</button>
      <button v-for="(cnt, ot) in stats.by_obj_type" :key="ot"
        class="otab" :class="{active:objF===ot}" @click="objF=ot">
        {{ OBJ_ICON[ot]||'◆' }} {{ ot }} <span class="otab-cnt">{{ cnt }}</span>
      </button>
    </div>

    <!-- 테이블 -->
    <div class="tbl-outer">
      <!-- v10: 스크롤 진행률 인디케이터 -->
      <div v-if="filtered.length > 30" class="tbl-scroll-ind" :title="`${Math.round(tblScrollProgress)}% 위치 · ${filtered.length}건`">
        <div class="tbl-scroll-ind-fill" :style="{width: tblScrollProgress+'%'}"></div>
      </div>

      <div class="card tbl-wrap" ref="tblWrapRef">
        <div v-if="loading" class="empty-state">
          <span class="spinner" style="width:16px;height:16px"/>
        </div>
        <table v-else class="map-tbl">
        <thead>
          <tr>
            <th @click="setSort('category')"   class="sortable">카테고리<S col="category"  :s="sortCol" :d="sortDir"/></th>
            <th @click="setSort('obj_type')"   class="sortable">오브젝트<S col="obj_type"  :s="sortCol" :d="sortDir"/></th>
            <th @click="setSort('src_db')"     class="sortable">소스 DB<S col="src_db"    :s="sortCol" :d="sortDir"/></th>
            <th @click="setSort('src_syntax')" class="sortable" style="min-width:200px">소스 구문<S col="src_syntax" :s="sortCol" :d="sortDir"/></th>
            <th @click="setSort('tgt_db')"     class="sortable">타겟 DB<S col="tgt_db"    :s="sortCol" :d="sortDir"/></th>
            <th style="min-width:200px">타겟 구문</th>
            <th @click="setSort('note')" class="sortable">주의사항<S col="note" :s="sortCol" :d="sortDir"/></th>
            <th>출처</th>
            <th>커스텀</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="filtered.length===0">
            <td colspan="10" style="text-align:center;padding:30px;color:var(--text-tertiary)">
              조건에 맞는 규칙이 없습니다
            </td>
          </tr>
          <tr v-for="r in filtered" :key="r.id" :class="{warn:r.warning}">
            <td><span class="cat-chip" :style="catStyle(r.category)">{{ r.category }}</span></td>
            <td>
              <span class="obj-chip" :style="objStyle(r.obj_type)">
                {{ OBJ_ICON[r.obj_type]||'◆' }} {{ r.obj_type }}
              </span>
            </td>
            <td><DbBadge :db="r.src_db"/></td>
            <td><code class="syntax src" :title="r.src_syntax">{{ r.src_syntax }}</code></td>
            <td><DbBadge :db="r.tgt_db"/></td>
            <td><code class="syntax tgt" :title="r.tgt_syntax">{{ r.tgt_syntax }}</code></td>
            <td>
              <span v-if="r.note" class="note-chip" :class="r.warning?'w':'i'">
                {{ r.warning ? '⚠ ' : '' }}{{ r.note }}
              </span>
              <span v-else class="no-note">—</span>
            </td>
            <td>
              <span v-if="(r.source||'manual') === 'ai_learned'"
                    class="src-badge ai"
                    :class="{shadow: r.status==='shadow', rejected: r.status==='rejected'}"
                    :title="`confidence: ${r.confidence||0} · ${r.status||'active'} · 최근 ${r.last_seen||'-'}`">
                🤖 AI 학습<small v-if="r.confidence"> ×{{ r.confidence }}</small>
              </span>
              <span v-else class="src-badge manual" title="수동 등록 규칙">✍ 수동</span>
            </td>
            <td>
              <div class="toggle" :class="{on:r.custom}" @click="r.custom=!r.custom; markDirty(r)"/>
            </td>
            <td>
              <div style="display:flex;gap:4px">
                <button class="act-btn" style="color:var(--text-info)" @click="openEdit(r)">편집</button>
                <button class="act-btn del" @click="deleteRule(r)">삭제</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      </div><!-- /.tbl-wrap -->
    </div><!-- /.tbl-outer -->

    <!-- 추가/편집 모달 -->
    <div v-if="modal.show" class="modal-overlay" @click.self="modal.show=false">
      <div class="modal" style="max-width:680px;width:96%">
        <div class="modal-title">{{ modal.isEdit ? '규칙 편집' : '오브젝트 변환 규칙 추가' }}</div>
        <div class="modal-grid">
          <div>
            <div class="field-label">소스 DB</div>
            <div class="sel-w"><select v-model="modal.f.src_db">
              <option v-for="d in ALL_DBS" :key="d.v" :value="d.v">{{ d.n }}</option>
            </select><Chev/></div>
          </div>
          <div>
            <div class="field-label">타겟 DB</div>
            <div class="sel-w"><select v-model="modal.f.tgt_db">
              <option v-for="d in ALL_DBS" :key="d.v" :value="d.v">{{ d.n }}</option>
            </select><Chev/></div>
          </div>
          <div>
            <div class="field-label">오브젝트 타입</div>
            <div class="sel-w"><select v-model="modal.f.obj_type">
              <option v-for="o in OBJ_TYPES" :key="o" :value="o">{{ OBJ_ICON[o]||'' }} {{ o }}</option>
            </select><Chev/></div>
          </div>
          <div>
            <div class="field-label">카테고리</div>
            <div class="sel-w"><select v-model="modal.f.category">
              <option v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</option>
            </select><Chev/></div>
          </div>
          <div style="grid-column:1/-1">
            <div class="field-label">소스 구문 (소스 DB의 원래 문법)</div>
            <textarea v-model="modal.f.src_syntax" rows="3"
              placeholder="예) IF condition THEN ... ELSEIF ... ELSE ... END IF;"/>
          </div>
          <div style="grid-column:1/-1">
            <div class="field-label">타겟 구문 (타겟 DB로 변환된 문법)</div>
            <textarea v-model="modal.f.tgt_syntax" rows="3"
              placeholder="예) IF condition BEGIN ... END ELSE IF ... BEGIN ... END"/>
          </div>
          <div style="grid-column:1/-1">
            <div class="field-label">주의사항/설명</div>
            <input v-model="modal.f.note" placeholder="예) 파라미터 순서가 반대입니다 — 확인 필요"/>
          </div>
          <div style="grid-column:1/-1;display:flex;gap:20px;align-items:center;flex-wrap:wrap">
            <label class="chk-label">
              <input type="checkbox" v-model="modal.f.warning" style="accent-color:#f59e0b"/>
              ⚠ 주의 필요 (수동 검토 권장)
            </label>
            <label class="chk-label">
              <input type="checkbox" v-model="modal.f.is_regex"/>
              🔤 소스 구문이 정규식
            </label>
            <label class="chk-label">
              <input type="checkbox" v-model="modal.f.custom"/>
              ✎ 커스텀 규칙
            </label>
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
import { ref, computed, reactive, onMounted, onUnmounted, h } from 'vue'
import axios from 'axios'
import { useAppStore } from '@/store/appStore.js'

const app    = useAppStore()
const rules  = ref([])
const loading= ref(false)
const saving = ref(false)
const stats  = ref({ total:0, pairs:0, warning:0, custom:0, by_obj_type:{}, by_category:{} })

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
const objTypes  = ref([])
const categories= ref([])

const srcF = ref(''), tgtF = ref(''), objF = ref(''), catF = ref(''), q = ref('')
const qfWarn = ref(false), qfCustom = ref(false), qfPair = ref(false)
const sortCol = ref('category'), sortDir = ref('asc')

const pairKey = computed(() => srcF.value && tgtF.value ? `${srcF.value}→${tgtF.value}` : '')

const ALL_DBS = [
  {v:'mysql',n:'MySQL/MariaDB'},{v:'mssql',n:'SQL Server'},{v:'oracle',n:'Oracle'},
  {v:'postgresql',n:'PostgreSQL'},{v:'db2',n:'IBM DB2'},{v:'sybase',n:'Sybase ASE'},
  {v:'snowflake',n:'Snowflake'},{v:'bigquery',n:'BigQuery'},{v:'redshift',n:'Redshift'},
  {v:'clickhouse',n:'ClickHouse'},{v:'hana',n:'SAP HANA'},{v:'teradata',n:'Teradata'},
  {v:'sqlite',n:'SQLite'},{v:'mongodb',n:'MongoDB'},{v:'aurora',n:'Aurora'},
  {v:'tidb',n:'TiDB'},{v:'duckdb',n:'DuckDB'},{v:'cockroachdb',n:'CockroachDB'},
]
const OBJ_TYPES = [
  'SYNTAX','TABLE','INDEX','CONSTRAINT','VIEW','PROCEDURE','FUNCTION',
  'TRIGGER','SEQUENCE','QUERY','DML','FUNCTION','TEMP_TABLE',
  'TRANSACTION','EXCEPTION','CURSOR','DYNAMIC_SQL','PERMISSION',
]
const CATEGORIES = [
  '식별자','CREATE TABLE','자동증가','일반인덱스','유니크인덱스','전문인덱스',
  '클러스터드인덱스','함수기반인덱스','기본키','외래키','체크제약','기본값',
  '뷰생성','구체화뷰','인덱스드뷰','생성구문','호출','변수선언','IF문','WHILE문',
  'LOOP문','SELECT INTO','임시테이블','SIGNAL','예외처리','오류발생','특성제거',
  '스칼라함수','테이블반환함수','AFTER INSERT','BEFORE INSERT','NEW/OLD 참조',
  'INSTEAD OF','INSERTED/DELETED','트리거생성','FOR LOOP',
  '페이징','TOP','CTE','재귀CTE','계층쿼리','ROWNUM',
  '현재시간','현재날짜','날짜더하기','날짜차이','날짜포맷','날짜추출','날짜변환',
  '부분문자열','문자열길이','문자열연결','NULL연결','집계문자열','NULL대체','조건함수',
  '위치검색','공백제거','문자반복','문자대체',
  '형변환','윈도우함수','분석함수','집계함수',
  '트랜잭션시작','커밋','롤백','저장점','부분롤백','자동커밋',
  '커서선언','커서열기','커서읽기','커서닫기','종료감지',
  '동적실행','UPSERT','MERGE','멀티행INSERT','DELETE JOIN','UPDATE JOIN',
  'DB참조','DUAL','힌트제거','주석','문자열연결','스키마참조',
  '권한부여','권한회수','역할',
]
const OBJ_ICON = {
  TABLE:'▤', INDEX:'◈', CONSTRAINT:'🔒', VIEW:'👁', PROCEDURE:'⚙',
  FUNCTION:'ƒ', TRIGGER:'⚡', SEQUENCE:'🔢', QUERY:'🔍', DML:'✏',
  TEMP_TABLE:'⏱', TRANSACTION:'↔', EXCEPTION:'⚠', CURSOR:'📌',
  DYNAMIC_SQL:'💬', PERMISSION:'🔑', SYNTAX:'🔤',
}

// DB 색상
const DB_BG = {
  mysql:'#e8f5e9', mssql:'#e3f2fd', oracle:'#fff3e0', postgresql:'#ede7f6',
  db2:'#fce4ec', sybase:'#f3e5f5', snowflake:'#e1f5fe', bigquery:'#e8f5e9',
  redshift:'#fff8e1', clickhouse:'#fff3e0', hana:'#fce4ec', teradata:'#e8eaf6',
  sqlite:'#f1f8e9', mongodb:'#e8f5e9', aurora:'#e3f2fd', tidb:'#fce4ec',
  duckdb:'#fff8e1', cockroachdb:'#e1f5fe',
}
const DB_COLOR = {
  mysql:'#2e7d32', mssql:'#1565c0', oracle:'#e65100', postgresql:'#512da8',
  db2:'#c62828', sybase:'#6a1b9a', snowflake:'#0277bd', bigquery:'#2e7d32',
  redshift:'#f57f17', clickhouse:'#bf360c', hana:'#880e4f', teradata:'#283593',
  sqlite:'#33691e', mongodb:'#1b5e20', aurora:'#1a237e', tidb:'#880e4f',
  duckdb:'#e65100', cockroachdb:'#01579b',
}

// 컴포넌트들
const DbBadge = {
  props:['db'],
  setup(props) {
    return () => h('span', {
      style: {
        background: DB_BG[props.db] || '#f5f5f5',
        color: DB_COLOR[props.db] || '#333',
        padding:'2px 7px', borderRadius:'5px',
        fontSize:'10.5px', fontWeight:700, whiteSpace:'nowrap'
      }
    }, props.db?.toUpperCase())
  }
}
const S = {
  props:['col','s','d'],
  template:`<span style="margin-left:3px;font-size:9px;opacity:.6">
    <span v-if="col===s">{{d==='asc'?'▲':'▼'}}</span>
    <span v-else style="opacity:.3">⇅</span>
  </span>`
}
const Chev = { template:'<div class="chev-ico"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>' }

// 카테고리 색상 (해시 기반)
const CAT_COLORS = [
  '#e3f2fd/#1565c0','#f3e5f5/#6a1b9a','#fff3e0/#e65100','#e8f5e9/#2e7d32',
  '#fce4ec/#c62828','#fbe9e7/#bf360c','#e8eaf6/#283593','#f9fbe7/#558b2f',
  '#e0f7fa/#006064','#fff8e1/#f57f17','#f1f8e9/#33691e','#fde7f3/#880e4f',
]
function catStyle(cat) {
  const idx = Math.abs([...cat].reduce((h,c)=>h*31+c.charCodeAt(0),0)) % CAT_COLORS.length
  const [bg, color] = CAT_COLORS[idx].split('/')
  return { background:bg, color, padding:'2px 7px', borderRadius:'8px', fontSize:'10px', fontWeight:500, whiteSpace:'nowrap' }
}
function objStyle(ot) {
  const colors = {
    TABLE:'#e3f2fd/#1565c0', INDEX:'#e8eaf6/#3949ab', CONSTRAINT:'#fce4ec/#c62828',
    VIEW:'#e8f5e9/#2e7d32', PROCEDURE:'#f3e5f5/#7b1fa2', FUNCTION:'#e1f5fe/#0277bd',
    TRIGGER:'#fff8e1/#f57f17', SEQUENCE:'#f9fbe7/#558b2f', QUERY:'#e0f7fa/#00838f',
    DML:'#fff3e0/#bf360c', TEMP_TABLE:'#ede7f6/#512da8',
    TRANSACTION:'#e8f5e9/#1b5e20', EXCEPTION:'#fbe9e7/#b71c1c',
    CURSOR:'#f3e5f5/#6a1b9a', DYNAMIC_SQL:'#e3f2fd/#0d47a1',
    PERMISSION:'#fce4ec/#880e4f', SYNTAX:'#f5f5f5/#424242',
  }
  const [bg, color] = (colors[ot] || '#f5f5f5/#555').split('/')
  return { background:bg, color, padding:'2px 6px', borderRadius:'4px', fontSize:'10px', fontWeight:600, whiteSpace:'nowrap' }
}

function setSort(col) {
  if (sortCol.value === col) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else { sortCol.value = col; sortDir.value = 'asc' }
}

function swapDb() {
  const tmp = srcF.value
  srcF.value = tgtF.value
  tgtF.value = tmp
}

const filtered = computed(() => {
  let list = rules.value.filter(r => {
    if (srcF.value  && r.src_db   !== srcF.value)  return false
    if (tgtF.value  && r.tgt_db   !== tgtF.value)  return false
    if (objF.value  && r.obj_type !== objF.value)  return false
    if (catF.value  && r.category !== catF.value)  return false
    if (qfWarn.value  && !r.warning)               return false
    if (qfCustom.value && !r.custom)               return false
    if (qfPair.value && pairKey.value)
      if (r.src_db !== srcF.value || r.tgt_db !== tgtF.value) return false
    if (q.value) {
      const ql = q.value.toLowerCase()
      if (!r.src_syntax?.toLowerCase().includes(ql) &&
          !r.tgt_syntax?.toLowerCase().includes(ql) &&
          !r.note?.toLowerCase().includes(ql) &&
          !r.category?.toLowerCase().includes(ql) &&
          !r.obj_type?.toLowerCase().includes(ql)) return false
    }
    return true
  })
  const col = sortCol.value, dir = sortDir.value
  return [...list].sort((a,b) => {
    const av = (a[col]||'').toLowerCase()
    const bv = (b[col]||'').toLowerCase()
    return dir === 'asc' ? av.localeCompare(bv,'ko') : bv.localeCompare(av,'ko')
  })
})

// 모달
const modal = reactive({
  show:false, isEdit:false,
  f:{ src_db:'mysql', tgt_db:'mssql', obj_type:'SYNTAX', category:'식별자',
      src_syntax:'', tgt_syntax:'', note:'', warning:false, is_regex:false, custom:true }
})
function openAdd() {
  modal.isEdit = false
  modal.f = { src_db: srcF.value||'mysql', tgt_db: tgtF.value||'mssql',
              obj_type: objF.value||'SYNTAX', category: catF.value||'식별자',
              src_syntax:'', tgt_syntax:'', note:'', warning:false, is_regex:false, custom:true }
  modal.show = true
}
function openEdit(r) {
  modal.isEdit = true
  modal.f = { ...r }
  modal.show = true
}

// API
async function load() {
  loading.value = true
  try {
    const [rRes, sRes, otRes, cRes] = await Promise.all([
      axios.get('/api/v1/obj-mapping/rules'),
      axios.get('/api/v1/obj-mapping/stats'),
      axios.get('/api/v1/obj-mapping/obj-types'),
      axios.get('/api/v1/obj-mapping/categories'),
    ])
    rules.value      = rRes.data
    stats.value      = sRes.data
    objTypes.value   = otRes.data
    categories.value = cRes.data
  } catch(e) {
    app.notify('로드 실패: ' + e.message, 'error')
  } finally { loading.value = false }
}

async function refreshStats() {
  const [s, ot, c] = await Promise.all([
    axios.get('/api/v1/obj-mapping/stats'),
    axios.get('/api/v1/obj-mapping/obj-types'),
    axios.get('/api/v1/obj-mapping/categories'),
  ])
  stats.value = s.data
  objTypes.value = ot.data
  categories.value = c.data
}

async function submitRule() {
  if (!modal.f.src_syntax || !modal.f.tgt_syntax) {
    app.notify('소스/타겟 구문을 입력하세요', 'error'); return
  }
  try {
    if (modal.isEdit) {
      const res = await axios.put(`/api/v1/obj-mapping/rules/${modal.f.id}`, modal.f)
      const idx = rules.value.findIndex(r => r.id === modal.f.id)
      if (idx >= 0) rules.value[idx] = res.data
      app.notify('수정됨', 'success')
    } else {
      const res = await axios.post('/api/v1/obj-mapping/rules', modal.f)
      rules.value.push(res.data)
      app.notify('추가됨', 'success')
    }
    modal.show = false
    await refreshStats()
  } catch(e) {
    app.notify('저장 실패: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

async function deleteRule(r) {
  if (!confirm(`"${r.src_syntax?.slice(0,40)}" 규칙을 삭제하시겠습니까?`)) return
  try {
    await axios.delete(`/api/v1/obj-mapping/rules/${r.id}`)
    rules.value = rules.value.filter(x => x.id !== r.id)
    app.notify('삭제됨', 'info')
    await refreshStats()
  } catch(e) { app.notify('삭제 실패', 'error') }
}

async function saveAll() {
  saving.value = true
  try {
    const dirty = rules.value.filter(r => r._dirty)
    if (dirty.length === 0) { app.notify('변경 사항 없음', 'info'); return }
    await Promise.all(dirty.map(r => axios.put(`/api/v1/obj-mapping/rules/${r.id}`, r)))
    rules.value.forEach(r => delete r._dirty)
    app.notify(`${dirty.length}개 저장됨`, 'success')
  } catch(e) { app.notify('저장 실패', 'error') }
  finally { saving.value = false }
}

function markDirty(r) { r._dirty = true }

onMounted(load)
</script>

<style scoped>
.filter-bar { display:flex; align-items:center; gap:7px; flex-wrap:wrap; padding:12px 14px; margin-bottom:10px; }
.fb-group { display:flex; align-items:center; gap:5px; }
.fb-label { font-size:11px; color:var(--text-tertiary); white-space:nowrap; }
.sel-w { position:relative; }
.sel-w select { appearance:none; font-size:11.5px; padding:5px 22px 5px 8px; border:0.5px solid var(--border-mid); border-radius:var(--radius-md); background:var(--bg-secondary); color:var(--text-primary); font-family:var(--font); cursor:pointer; }
.chev-ico { position:absolute; right:6px; top:50%; transform:translateY(-50%); pointer-events:none; color:var(--text-tertiary); }
.chev-ico svg { width:9px; height:9px; display:block; }
.swap-btn { background:var(--bg-secondary); border:0.5px solid var(--border-mid); border-radius:var(--radius-md); padding:4px 8px; cursor:pointer; font-size:13px; color:var(--text-secondary); transition:all .12s; }
.swap-btn:hover { background:var(--bg-info); color:var(--text-info); }
.search-input { flex:1; min-width:130px; font-size:12px; padding:5px 10px; border:0.5px solid var(--border-mid); border-radius:var(--radius-md); background:var(--bg-secondary); color:var(--text-primary); font-family:var(--font); }
.quick-filters { display:flex; gap:4px; flex-wrap:wrap; }
.qf-btn { font-size:11px; padding:4px 8px; border-radius:var(--radius-md); border:0.5px solid var(--border-mid); background:var(--bg-secondary); color:var(--text-secondary); cursor:pointer; font-family:var(--font); transition:all .12s; white-space:nowrap; }
.qf-btn.active { background:var(--bg-info); color:var(--text-info); border-color:var(--accent-blue); }
.qf-btn:disabled { opacity:.4; cursor:not-allowed; }
.fb-right { margin-left:auto; display:flex; gap:6px; align-items:center; }
.total-badge { font-size:11px; color:var(--text-tertiary); white-space:nowrap; }

.kpi-row { display:flex; gap:8px; margin-bottom:10px; }
.kpi { background:var(--bg-primary); border:0.5px solid var(--border-light); border-radius:var(--radius-md); padding:10px 16px; flex:1; text-align:center; }
.kpi-n { font-size:20px; font-weight:600; color:var(--text-primary); }
.kpi-n.info { color:var(--text-info); }
.kpi-n.warn { color:var(--text-warning); }
.kpi-n.ok   { color:var(--text-success); }
.kpi-l { font-size:10.5px; color:var(--text-tertiary); margin-top:2px; }

.obj-tabs { display:flex; gap:4px; flex-wrap:wrap; margin-bottom:10px; }
.otab { font-size:11px; padding:5px 10px; border-radius:var(--radius-md); border:0.5px solid var(--border-mid); background:var(--bg-secondary); color:var(--text-secondary); cursor:pointer; font-family:var(--font); transition:all .12s; white-space:nowrap; }
.otab:hover { background:var(--bg-primary); }
.otab.active { background:var(--bg-info); color:var(--text-info); border-color:var(--accent-blue); font-weight:500; }
.otab-cnt { background:var(--accent-blue); color:#fff; font-size:9px; font-weight:700; padding:1px 4px; border-radius:6px; margin-left:3px; }

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
.tbl-wrap {
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

.map-tbl { width:100%; border-collapse:collapse; font-size:11.5px; }
.map-tbl thead {
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--bg-secondary);
}
.map-tbl th { background:var(--bg-secondary); font-size:10.5px; font-weight:500; color:var(--text-tertiary); padding:8px 10px; text-align:left; border-bottom:0.5px solid var(--border-light); white-space:nowrap; user-select:none; }
.map-tbl th.sortable { cursor:pointer; }
.map-tbl th.sortable:hover { color:var(--text-primary); }
.map-tbl td { padding:6px 10px; border-bottom:0.5px solid var(--border-light); vertical-align:top; }
.map-tbl tr:last-child td { border-bottom:none; }
.map-tbl tr:hover td { background:var(--bg-secondary); }
.map-tbl tr.warn { background:#fffdf5; }
.map-tbl tr.warn:hover td { background:#fff8e0; }

.syntax { font-family:'Consolas','SF Mono',monospace; font-size:11px; padding:3px 7px; border-radius:4px; display:block; max-width:240px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; cursor:pointer; }
.syntax:hover { white-space:normal; word-break:break-all; max-width:none; position:relative; z-index:1; box-shadow:0 2px 8px rgba(0,0,0,.15); }
.syntax.src { background:#e8f0fe; color:#1a56a0; }
.syntax.tgt { background:#e6f4ea; color:#1e6e38; }

.note-chip { font-size:10.5px; padding:2px 7px; border-radius:6px; display:inline-block; max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.note-chip.w { background:#fff3cd; color:#856404; }
.note-chip.i { background:#e8f4f8; color:#1a6c8a; }
.no-note { color:var(--text-tertiary); font-size:11px; }

.toggle { position:relative; width:30px; height:16px; background:var(--border-mid); border-radius:8px; cursor:pointer; transition:background .2s; flex-shrink:0; }
.toggle.on { background:var(--accent-blue); }
.toggle::after { content:''; position:absolute; top:2px; left:2px; width:12px; height:12px; border-radius:50%; background:white; transition:transform .2s; }
.toggle.on::after { transform:translateX(14px); }

.modal-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
textarea { width:100%; padding:7px 10px; background:var(--bg-secondary); border:0.5px solid var(--border-mid); border-radius:var(--radius-md); font-size:12px; color:var(--text-primary); font-family:'Consolas','SF Mono',monospace; resize:vertical; }
textarea:focus { outline:none; border-color:var(--accent-blue); }
.chk-label { display:flex; align-items:center; gap:6px; font-size:12px; cursor:pointer; color:var(--text-secondary); }
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
</style>
