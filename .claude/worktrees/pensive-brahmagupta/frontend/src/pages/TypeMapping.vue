<template>
  <div>
    <div class="page-title">타입 매핑 테이블</div>
    <div class="page-desc">소스→타겟 DB 조합별 데이터 타입 변환 규칙 — 주요 DB 전 조합 수록</div>

    <!-- 필터 바 -->
    <div class="card filter-bar">
      <div class="fb-group">
        <span class="fb-label">소스 DB</span>
        <div class="sel-w"><select v-model="srcF"><option value="">전체</option><option v-for="d in allDbs" :key="d.v" :value="d.v">{{ d.n }}</option></select><Chev/></div>
      </div>
      <div class="fb-group">
        <span class="fb-label">타겟 DB</span>
        <div class="sel-w"><select v-model="tgtF"><option value="">전체</option><option v-for="d in allDbs" :key="d.v" :value="d.v">{{ d.n }}</option></select><Chev/></div>
      </div>
      <div class="fb-group">
        <span class="fb-label">카테고리</span>
        <div class="sel-w"><select v-model="catF"><option value="">전체</option><option v-for="c in categories" :key="c" :value="c">{{ c }}</option></select><Chev/></div>
      </div>
      <input type="text" v-model="typeQ" placeholder="타입명 검색..." class="search-input"/>
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
        <button class="btn" @click="showAdd=true">+ 규칙 추가</button>
        <button class="btn btn-primary" @click="saveAll" :disabled="saving"><span v-if="saving" class="spinner" style="width:12px;height:12px"/>저장</button>
      </div>
    </div>

    <!-- 통계 키트 -->
    <div class="kpi-row">
      <div class="kpi"><div class="kpi-n">{{ rules.length }}</div><div class="kpi-l">전체 규칙</div></div>
      <div class="kpi"><div class="kpi-n warn">{{ rules.filter(r=>r.warning).length }}</div><div class="kpi-l">주의 필요</div></div>
      <div class="kpi"><div class="kpi-n info">{{ pairCount }}</div><div class="kpi-l">DB 조합</div></div>
      <div class="kpi"><div class="kpi-n ok">{{ rules.filter(r=>r.custom).length }}</div><div class="kpi-l">커스텀 규칙</div></div>
    </div>

    <!-- 테이블 -->
    <div class="card tbl-wrap">
      <table class="map-tbl">
        <thead>
          <tr>
            <th @click="setSort('category')" class="sortable">카테고리<SortIco :col="'category'" :sort="sortCol" :dir="sortDir"/></th>
            <th @click="setSort('src_db')" class="sortable">소스 DB<SortIco :col="'src_db'" :sort="sortCol" :dir="sortDir"/></th>
            <th @click="setSort('src_type')" class="sortable">소스 타입<SortIco :col="'src_type'" :sort="sortCol" :dir="sortDir"/></th>
            <th @click="setSort('tgt_db')" class="sortable">타겟 DB<SortIco :col="'tgt_db'" :sort="sortCol" :dir="sortDir"/></th>
            <th @click="setSort('tgt_type')" class="sortable">타겟 타입<SortIco :col="'tgt_type'" :sort="sortCol" :dir="sortDir"/></th>
            <th @click="setSort('note')" class="sortable">주의사항<SortIco :col="'note'" :sort="sortCol" :dir="sortDir"/></th><th>커스텀</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in filtered" :key="r.id" :class="{warn:r.warning}">
            <td><span class="cat-chip" :class="r.category">{{ r.category }}</span></td>
            <td><span class="dbc" :style="{background:m(r.src_db)?.bg,color:m(r.src_db)?.color}">{{ m(r.src_db)?.label||r.src_db }}</span></td>
            <td><span class="type-src">{{ r.src_type }}</span></td>
            <td><span class="dbc" :style="{background:m(r.tgt_db)?.bg,color:m(r.tgt_db)?.color}">{{ m(r.tgt_db)?.label||r.tgt_db }}</span></td>
            <td><span class="type-tgt">{{ r.tgt_type }}</span></td>
            <td>
              <span v-if="r.note" class="note-chip" :class="r.warning?'w':'i'">{{ r.note }}</span>
              <span v-else class="no-note">—</span>
            </td>
            <td><div class="toggle" :class="{on:r.custom}" @click="r.custom=!r.custom"></div></td>
            <td><button class="del-btn" @click="rules.splice(rules.indexOf(r),1)" title="삭제">✕</button></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 추가 모달 -->
    <div v-if="showAdd" class="modal-overlay" @click.self="showAdd=false">
      <div class="modal">
        <div class="modal-title">변환 규칙 추가</div>
        <div class="modal-grid">
          <div>
            <div class="field-label">소스 DB</div>
            <div class="sel-w"><select v-model="nr.src_db"><option v-for="d in allDbs" :key="d.v" :value="d.v">{{ d.n }}</option></select><Chev/></div>
          </div>
          <div>
            <div class="field-label">소스 타입</div>
            <input v-model="nr.src_type" placeholder="예) NVARCHAR(n)"/>
          </div>
          <div>
            <div class="field-label">타겟 DB</div>
            <div class="sel-w"><select v-model="nr.tgt_db"><option v-for="d in allDbs" :key="d.v" :value="d.v">{{ d.n }}</option></select><Chev/></div>
          </div>
          <div>
            <div class="field-label">타겟 타입</div>
            <input v-model="nr.tgt_type" placeholder="예) VARCHAR({n})"/>
          </div>
          <div>
            <div class="field-label">카테고리</div>
            <div class="sel-w"><select v-model="nr.category"><option v-for="c in categories" :key="c" :value="c">{{ c }}</option></select><Chev/></div>
          </div>
          <div>
            <div class="field-label">주의사항 (선택)</div>
            <input v-model="nr.note" placeholder="데이터 손실 가능 등"/>
          </div>
          <div style="grid-column:1/-1;display:flex;align-items:center;gap:8px">
            <label style="display:flex;align-items:center;gap:6px;font-size:12px;cursor:pointer">
              <input type="checkbox" v-model="nr.warning" style="accent-color:var(--accent-orange)"/> 주의 표시
            </label>
          </div>
        </div>
        <div class="modal-btns">
          <button class="btn" @click="showAdd=false">취소</button>
          <button class="btn btn-primary" @click="addRule">추가</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAppStore } from '@/store/appStore.js'
import { DB_META } from '@/constants/dbMeta.js'

const app = useAppStore()
const srcF = ref(''), tgtF = ref(''), catF = ref(''), typeQ = ref('')
const qfWarn     = ref(false)
const qfCustom   = ref(false)
const qfPairOnly = ref(false)
const sortCol    = ref('src_db')
const sortDir    = ref('asc')  // 'asc' | 'desc'

const pairKey = computed(() => srcF.value && tgtF.value ? `${srcF.value}→${tgtF.value}` : '')

function setSort(col) {
  if (sortCol.value === col) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else { sortCol.value = col; sortDir.value = 'asc' }
}

// SortIco 컴포넌트
const SortIco = {
  props: ['col','sort','dir'],
  template: `<span style="margin-left:4px;font-size:10px;opacity:.6">
    <span v-if="col===sort">{{ dir==='asc'?'▲':'▼' }}</span>
    <span v-else style="opacity:.3">⇅</span>
  </span>`
}
const showAdd = ref(false)

const Chev = { template: '<div class="chev-ico"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>' }

const m = t => DB_META[t] || { label: t?.toUpperCase().slice(0,3)||'??', bg:'#e8e8e8', color:'#555' }

const allDbs = [
  {v:'mysql',n:'MySQL/MariaDB'},{v:'mssql',n:'SQL Server'},{v:'oracle',n:'Oracle'},
  {v:'postgresql',n:'PostgreSQL'},{v:'db2',n:'IBM DB2'},{v:'sybase',n:'Sybase ASE'},
  {v:'snowflake',n:'Snowflake'},{v:'bigquery',n:'BigQuery'},{v:'redshift',n:'Redshift'},
  {v:'clickhouse',n:'ClickHouse'},{v:'mongodb',n:'MongoDB'},{v:'sqlite',n:'SQLite'},
]
const categories = computed(() => {
  const cats = [...new Set(rules.value.map(r => r.category))].sort()
  return cats
})

const nr = ref({ src_db:'mysql', tgt_db:'mssql', src_type:'', tgt_type:'', category:'문자열', note:'', warning:false, custom:true })

let _id = 1000
function mkid() { return ++_id }

const saving = ref(false)
async function saveAll() {
  saving.value = true
  try {
    const dirty = rules.value.filter(r => r._dirty)
    await Promise.all(dirty.map(r =>
      import('axios').then(m => m.default.put(`/api/v1/mapping/rules/${r.id}`, r))
    ))
    rules.value.forEach(r => delete r._dirty)
    // 새 규칙 저장
    const newRules = rules.value.filter(r => r._new)
    for (const r of newRules) {
      await import('axios').then(m => m.default.post('/api/v1/mapping/rules', r))
      delete r._new
    }
    app.notify('저장됐습니다', 'success')
  } catch(e) {
    app.notify('저장 실패: ' + e.message, 'error')
  } finally { saving.value = false }
}

function addRule() {
  if (!nr.value.src_type || !nr.value.tgt_type) { app.notify('타입을 입력하세요','error'); return }
  rules.value.push({ ...nr.value, id: mkid() })
  nr.value = { src_db:'mysql', tgt_db:'mssql', src_type:'', tgt_type:'', category:'문자열', note:'', warning:false, custom:true }
  showAdd.value = false
  app.notify('규칙 추가됨','success')
}

const pairCount = computed(() => new Set(rules.value.map(r=>`${r.src_db}→${r.tgt_db}`)).size)

const filtered = computed(() => {
  let result = rules.value.filter(r => {
    if (srcF.value && r.src_db !== srcF.value) return false
    if (tgtF.value && r.tgt_db !== tgtF.value) return false
    if (catF.value && r.category !== catF.value) return false
    if (typeQ.value) {
      const q = typeQ.value.toLowerCase()
      if (!r.src_type.toLowerCase().includes(q) && !r.tgt_type.toLowerCase().includes(q)) return false
    }
    if (qfWarn.value && !r.warning) return false
    if (qfCustom.value && !r.custom) return false
    if (qfPairOnly.value && pairKey.value) {
      if (r.src_db !== srcF.value || r.tgt_db !== tgtF.value) return false
    }
    return true
  })
  // 정렬
  const col = sortCol.value; const dir = sortDir.value
  result = [...result].sort((a,b) => {
    const av = (a[col]||'').toLowerCase(); const bv = (b[col]||'').toLowerCase()
    return dir === 'asc' ? av.localeCompare(bv,'ko') : bv.localeCompare(av,'ko')
  })
  return result
})

// ── 완전한 타입 매핑 데이터 ─────────────────────────────────
const rules = ref([
// ═══════════════════════════ MySQL → SQL Server ════════════════════
{id:1,  src_db:'mysql',src_type:'TINYINT(1)',      tgt_db:'mssql',tgt_type:'BIT',                category:'부울',    note:'0/1 → false/true',warning:false,custom:false},
{id:2,  src_db:'mysql',src_type:'TINYINT UNSIGNED',tgt_db:'mssql',tgt_type:'SMALLINT',           category:'숫자',    note:'',warning:false,custom:false},
{id:3,  src_db:'mysql',src_type:'TINYINT',         tgt_db:'mssql',tgt_type:'TINYINT',            category:'숫자',    note:'',warning:false,custom:false},
{id:4,  src_db:'mysql',src_type:'SMALLINT UNSIGNED',tgt_db:'mssql',tgt_type:'INT',               category:'숫자',    note:'범위 확장',warning:false,custom:false},
{id:5,  src_db:'mysql',src_type:'SMALLINT',        tgt_db:'mssql',tgt_type:'SMALLINT',           category:'숫자',    note:'',warning:false,custom:false},
{id:6,  src_db:'mysql',src_type:'MEDIUMINT',       tgt_db:'mssql',tgt_type:'INT',                category:'숫자',    note:'',warning:false,custom:false},
{id:7,  src_db:'mysql',src_type:'INT UNSIGNED',    tgt_db:'mssql',tgt_type:'BIGINT',             category:'숫자',    note:'범위 확장',warning:false,custom:false},
{id:8,  src_db:'mysql',src_type:'INT',             tgt_db:'mssql',tgt_type:'INT',                category:'숫자',    note:'',warning:false,custom:false},
{id:9,  src_db:'mysql',src_type:'BIGINT UNSIGNED', tgt_db:'mssql',tgt_type:'DECIMAL(20,0)',      category:'숫자',    note:'오버플로 주의',warning:true,custom:false},
{id:10, src_db:'mysql',src_type:'BIGINT',          tgt_db:'mssql',tgt_type:'BIGINT',             category:'숫자',    note:'',warning:false,custom:false},
{id:11, src_db:'mysql',src_type:'FLOAT',           tgt_db:'mssql',tgt_type:'REAL',               category:'숫자',    note:'',warning:false,custom:false},
{id:12, src_db:'mysql',src_type:'DOUBLE',          tgt_db:'mssql',tgt_type:'FLOAT',              category:'숫자',    note:'',warning:false,custom:false},
{id:13, src_db:'mysql',src_type:'DECIMAL(p,s)',    tgt_db:'mssql',tgt_type:'DECIMAL(p,s)',       category:'숫자',    note:'',warning:false,custom:false},
{id:14, src_db:'mysql',src_type:'VARCHAR(n)',      tgt_db:'mssql',tgt_type:'NVARCHAR(n)',        category:'문자열',  note:'Collation 변경',warning:false,custom:false},
{id:15, src_db:'mysql',src_type:'CHAR(n)',         tgt_db:'mssql',tgt_type:'NCHAR(n)',           category:'문자열',  note:'',warning:false,custom:false},
{id:16, src_db:'mysql',src_type:'TEXT',            tgt_db:'mssql',tgt_type:'NVARCHAR(MAX)',      category:'문자열',  note:'',warning:false,custom:false},
{id:17, src_db:'mysql',src_type:'MEDIUMTEXT',      tgt_db:'mssql',tgt_type:'NVARCHAR(MAX)',      category:'문자열',  note:'',warning:false,custom:false},
{id:18, src_db:'mysql',src_type:'LONGTEXT',        tgt_db:'mssql',tgt_type:'NVARCHAR(MAX)',      category:'문자열',  note:'',warning:false,custom:false},
{id:19, src_db:'mysql',src_type:'ENUM',            tgt_db:'mssql',tgt_type:'NVARCHAR(255)',      category:'문자열',  note:'CHECK 제약 추가 권장',warning:true,custom:false},
{id:20, src_db:'mysql',src_type:'SET',             tgt_db:'mssql',tgt_type:'NVARCHAR(500)',      category:'문자열',  note:'정규화 권장',warning:true,custom:false},
{id:21, src_db:'mysql',src_type:'DATE',            tgt_db:'mssql',tgt_type:'DATE',               category:'날짜시간',note:'',warning:false,custom:false},
{id:22, src_db:'mysql',src_type:'TIME',            tgt_db:'mssql',tgt_type:'TIME(7)',            category:'날짜시간',note:'',warning:false,custom:false},
{id:23, src_db:'mysql',src_type:'DATETIME',        tgt_db:'mssql',tgt_type:'DATETIME2(6)',       category:'날짜시간',note:'',warning:false,custom:false},
{id:24, src_db:'mysql',src_type:'TIMESTAMP',       tgt_db:'mssql',tgt_type:'DATETIME2(6)',       category:'날짜시간',note:'시간대 주의',warning:true,custom:false},
{id:25, src_db:'mysql',src_type:'YEAR',            tgt_db:'mssql',tgt_type:'SMALLINT',           category:'날짜시간',note:'',warning:false,custom:false},
{id:26, src_db:'mysql',src_type:'BLOB',            tgt_db:'mssql',tgt_type:'VARBINARY(MAX)',     category:'바이너리',note:'',warning:false,custom:false},
{id:27, src_db:'mysql',src_type:'MEDIUMBLOB',      tgt_db:'mssql',tgt_type:'VARBINARY(MAX)',     category:'바이너리',note:'',warning:false,custom:false},
{id:28, src_db:'mysql',src_type:'LONGBLOB',        tgt_db:'mssql',tgt_type:'VARBINARY(MAX)',     category:'바이너리',note:'',warning:false,custom:false},
{id:29, src_db:'mysql',src_type:'BINARY(n)',       tgt_db:'mssql',tgt_type:'BINARY(n)',          category:'바이너리',note:'',warning:false,custom:false},
{id:30, src_db:'mysql',src_type:'VARBINARY(n)',    tgt_db:'mssql',tgt_type:'VARBINARY(n)',       category:'바이너리',note:'',warning:false,custom:false},
{id:31, src_db:'mysql',src_type:'JSON',            tgt_db:'mssql',tgt_type:'NVARCHAR(MAX)',      category:'JSON-XML',note:'JSON 검증 없음',warning:true,custom:false},
{id:32, src_db:'mysql',src_type:'GEOMETRY',        tgt_db:'mssql',tgt_type:'GEOMETRY',          category:'공간',    note:'SRID 확인',warning:true,custom:false},
// ═══════════════════════════ MySQL → PostgreSQL ════════════════════
{id:101,src_db:'mysql',src_type:'TINYINT(1)',      tgt_db:'postgresql',tgt_type:'BOOLEAN',       category:'부울',    note:'',warning:false,custom:false},
{id:102,src_db:'mysql',src_type:'TINYINT',         tgt_db:'postgresql',tgt_type:'SMALLINT',      category:'숫자',    note:'',warning:false,custom:false},
{id:103,src_db:'mysql',src_type:'SMALLINT',        tgt_db:'postgresql',tgt_type:'SMALLINT',      category:'숫자',    note:'',warning:false,custom:false},
{id:104,src_db:'mysql',src_type:'MEDIUMINT',       tgt_db:'postgresql',tgt_type:'INTEGER',       category:'숫자',    note:'',warning:false,custom:false},
{id:105,src_db:'mysql',src_type:'INT',             tgt_db:'postgresql',tgt_type:'INTEGER',       category:'숫자',    note:'',warning:false,custom:false},
{id:106,src_db:'mysql',src_type:'INT AUTO_INCREMENT',tgt_db:'postgresql',tgt_type:'SERIAL',     category:'숫자',    note:'',warning:false,custom:false},
{id:107,src_db:'mysql',src_type:'BIGINT',          tgt_db:'postgresql',tgt_type:'BIGINT',        category:'숫자',    note:'',warning:false,custom:false},
{id:108,src_db:'mysql',src_type:'FLOAT',           tgt_db:'postgresql',tgt_type:'REAL',          category:'숫자',    note:'',warning:false,custom:false},
{id:109,src_db:'mysql',src_type:'DOUBLE',          tgt_db:'postgresql',tgt_type:'DOUBLE PRECISION',category:'숫자', note:'',warning:false,custom:false},
{id:110,src_db:'mysql',src_type:'DECIMAL(p,s)',    tgt_db:'postgresql',tgt_type:'NUMERIC(p,s)',  category:'숫자',    note:'',warning:false,custom:false},
{id:111,src_db:'mysql',src_type:'VARCHAR(n)',      tgt_db:'postgresql',tgt_type:'VARCHAR(n)',    category:'문자열',  note:'',warning:false,custom:false},
{id:112,src_db:'mysql',src_type:'TEXT',            tgt_db:'postgresql',tgt_type:'TEXT',          category:'문자열',  note:'',warning:false,custom:false},
{id:113,src_db:'mysql',src_type:'LONGTEXT',        tgt_db:'postgresql',tgt_type:'TEXT',          category:'문자열',  note:'',warning:false,custom:false},
{id:114,src_db:'mysql',src_type:'ENUM',            tgt_db:'postgresql',tgt_type:'TEXT',          category:'문자열',  note:'CREATE TYPE 권장',warning:true,custom:false},
{id:115,src_db:'mysql',src_type:'DATETIME',        tgt_db:'postgresql',tgt_type:'TIMESTAMP',     category:'날짜시간',note:'',warning:false,custom:false},
{id:116,src_db:'mysql',src_type:'TIMESTAMP',       tgt_db:'postgresql',tgt_type:'TIMESTAMPTZ',   category:'날짜시간',note:'시간대 처리',warning:true,custom:false},
{id:117,src_db:'mysql',src_type:'BLOB',            tgt_db:'postgresql',tgt_type:'BYTEA',         category:'바이너리',note:'',warning:false,custom:false},
{id:118,src_db:'mysql',src_type:'JSON',            tgt_db:'postgresql',tgt_type:'JSONB',         category:'JSON-XML',note:'JSONB 인덱싱 가능',warning:false,custom:false},
{id:119,src_db:'mysql',src_type:'GEOMETRY',        tgt_db:'postgresql',tgt_type:'GEOMETRY (PostGIS)',category:'공간',note:'PostGIS 설치 필요',warning:true,custom:false},
// ═══════════════════════════ SQL Server → MySQL ════════════════════
{id:201,src_db:'mssql',src_type:'BIT',             tgt_db:'mysql',tgt_type:'TINYINT(1)',         category:'부울',    note:'',warning:false,custom:false},
{id:202,src_db:'mssql',src_type:'TINYINT',         tgt_db:'mysql',tgt_type:'TINYINT UNSIGNED',   category:'숫자',    note:'MSSQL은 0~255',warning:false,custom:false},
{id:203,src_db:'mssql',src_type:'SMALLINT',        tgt_db:'mysql',tgt_type:'SMALLINT',           category:'숫자',    note:'',warning:false,custom:false},
{id:204,src_db:'mssql',src_type:'INT',             tgt_db:'mysql',tgt_type:'INT',                category:'숫자',    note:'',warning:false,custom:false},
{id:205,src_db:'mssql',src_type:'BIGINT',          tgt_db:'mysql',tgt_type:'BIGINT',             category:'숫자',    note:'',warning:false,custom:false},
{id:206,src_db:'mssql',src_type:'REAL',            tgt_db:'mysql',tgt_type:'FLOAT',              category:'숫자',    note:'',warning:false,custom:false},
{id:207,src_db:'mssql',src_type:'FLOAT',           tgt_db:'mysql',tgt_type:'DOUBLE',             category:'숫자',    note:'',warning:false,custom:false},
{id:208,src_db:'mssql',src_type:'DECIMAL(p,s)',    tgt_db:'mysql',tgt_type:'DECIMAL(p,s)',       category:'숫자',    note:'',warning:false,custom:false},
{id:209,src_db:'mssql',src_type:'MONEY',           tgt_db:'mysql',tgt_type:'DECIMAL(19,4)',      category:'숫자',    note:'',warning:false,custom:false},
{id:210,src_db:'mssql',src_type:'SMALLMONEY',      tgt_db:'mysql',tgt_type:'DECIMAL(10,4)',      category:'숫자',    note:'',warning:false,custom:false},
{id:211,src_db:'mssql',src_type:'NVARCHAR(MAX)',   tgt_db:'mysql',tgt_type:'LONGTEXT',           category:'문자열',  note:'',warning:false,custom:false},
{id:212,src_db:'mssql',src_type:'NVARCHAR(n)',     tgt_db:'mysql',tgt_type:'VARCHAR(n)',         category:'문자열',  note:'UTF8MB4 설정',warning:false,custom:false},
{id:213,src_db:'mssql',src_type:'VARCHAR(MAX)',    tgt_db:'mysql',tgt_type:'LONGTEXT',           category:'문자열',  note:'',warning:false,custom:false},
{id:214,src_db:'mssql',src_type:'VARCHAR(n)',      tgt_db:'mysql',tgt_type:'VARCHAR(n)',         category:'문자열',  note:'',warning:false,custom:false},
{id:215,src_db:'mssql',src_type:'CHAR(n)',         tgt_db:'mysql',tgt_type:'CHAR(n)',            category:'문자열',  note:'',warning:false,custom:false},
{id:216,src_db:'mssql',src_type:'NCHAR(n)',        tgt_db:'mysql',tgt_type:'CHAR(n)',            category:'문자열',  note:'',warning:false,custom:false},
{id:217,src_db:'mssql',src_type:'TEXT',            tgt_db:'mysql',tgt_type:'LONGTEXT',           category:'문자열',  note:'deprecated 타입',warning:true,custom:false},
{id:218,src_db:'mssql',src_type:'DATE',            tgt_db:'mysql',tgt_type:'DATE',               category:'날짜시간',note:'',warning:false,custom:false},
{id:219,src_db:'mssql',src_type:'TIME(n)',         tgt_db:'mysql',tgt_type:'TIME(6)',            category:'날짜시간',note:'',warning:false,custom:false},
{id:220,src_db:'mssql',src_type:'DATETIME',        tgt_db:'mysql',tgt_type:'DATETIME',           category:'날짜시간',note:'밀리초 손실',warning:true,custom:false},
{id:221,src_db:'mssql',src_type:'DATETIME2(n)',    tgt_db:'mysql',tgt_type:'DATETIME(6)',        category:'날짜시간',note:'',warning:false,custom:false},
{id:222,src_db:'mssql',src_type:'SMALLDATETIME',   tgt_db:'mysql',tgt_type:'DATETIME',           category:'날짜시간',note:'분 단위 정밀도',warning:false,custom:false},
{id:223,src_db:'mssql',src_type:'DATETIMEOFFSET',  tgt_db:'mysql',tgt_type:'DATETIME(6)',        category:'날짜시간',note:'시간대 정보 손실',warning:true,custom:false},
{id:224,src_db:'mssql',src_type:'VARBINARY(MAX)',  tgt_db:'mysql',tgt_type:'LONGBLOB',           category:'바이너리',note:'',warning:false,custom:false},
{id:225,src_db:'mssql',src_type:'VARBINARY(n)',    tgt_db:'mysql',tgt_type:'VARBINARY(n)',       category:'바이너리',note:'',warning:false,custom:false},
{id:226,src_db:'mssql',src_type:'BINARY(n)',       tgt_db:'mysql',tgt_type:'BINARY(n)',          category:'바이너리',note:'',warning:false,custom:false},
{id:227,src_db:'mssql',src_type:'UNIQUEIDENTIFIER',tgt_db:'mysql',tgt_type:'CHAR(36)',           category:'문자열',  note:'UUID 형식',warning:false,custom:false},
{id:228,src_db:'mssql',src_type:'XML',             tgt_db:'mysql',tgt_type:'LONGTEXT',           category:'JSON-XML',note:'XML 검증 없음',warning:true,custom:false},
// ═══════════════════════════ Oracle → MySQL ════════════════════════
{id:301,src_db:'oracle',src_type:'NUMBER(1)',       tgt_db:'mysql',tgt_type:'TINYINT(1)',         category:'숫자',    note:'',warning:false,custom:false},
{id:302,src_db:'oracle',src_type:'NUMBER(p,s)',     tgt_db:'mysql',tgt_type:'DECIMAL(p,s)',       category:'숫자',    note:'',warning:false,custom:false},
{id:303,src_db:'oracle',src_type:'NUMBER(p)',       tgt_db:'mysql',tgt_type:'BIGINT',             category:'숫자',    note:'p≤18',warning:false,custom:false},
{id:304,src_db:'oracle',src_type:'NUMBER',          tgt_db:'mysql',tgt_type:'DOUBLE',             category:'숫자',    note:'정밀도 주의',warning:true,custom:false},
{id:305,src_db:'oracle',src_type:'FLOAT',           tgt_db:'mysql',tgt_type:'DOUBLE',             category:'숫자',    note:'',warning:false,custom:false},
{id:306,src_db:'oracle',src_type:'BINARY_FLOAT',    tgt_db:'mysql',tgt_type:'FLOAT',              category:'숫자',    note:'',warning:false,custom:false},
{id:307,src_db:'oracle',src_type:'BINARY_DOUBLE',   tgt_db:'mysql',tgt_type:'DOUBLE',             category:'숫자',    note:'',warning:false,custom:false},
{id:308,src_db:'oracle',src_type:'VARCHAR2(n)',     tgt_db:'mysql',tgt_type:'VARCHAR(n)',         category:'문자열',  note:'',warning:false,custom:false},
{id:309,src_db:'oracle',src_type:'NVARCHAR2(n)',    tgt_db:'mysql',tgt_type:'VARCHAR(n)',         category:'문자열',  note:'UTF8MB4',warning:false,custom:false},
{id:310,src_db:'oracle',src_type:'CHAR(n)',         tgt_db:'mysql',tgt_type:'CHAR(n)',            category:'문자열',  note:'',warning:false,custom:false},
{id:311,src_db:'oracle',src_type:'NCHAR(n)',        tgt_db:'mysql',tgt_type:'CHAR(n)',            category:'문자열',  note:'',warning:false,custom:false},
{id:312,src_db:'oracle',src_type:'CLOB',            tgt_db:'mysql',tgt_type:'LONGTEXT',           category:'문자열',  note:'',warning:false,custom:false},
{id:313,src_db:'oracle',src_type:'NCLOB',           tgt_db:'mysql',tgt_type:'LONGTEXT',           category:'문자열',  note:'',warning:false,custom:false},
{id:314,src_db:'oracle',src_type:'LONG',            tgt_db:'mysql',tgt_type:'LONGTEXT',           category:'문자열',  note:'deprecated',warning:true,custom:false},
{id:315,src_db:'oracle',src_type:'DATE',            tgt_db:'mysql',tgt_type:'DATETIME',           category:'날짜시간',note:'Oracle DATE는 시간 포함',warning:true,custom:false},
{id:316,src_db:'oracle',src_type:'TIMESTAMP(n)',    tgt_db:'mysql',tgt_type:'DATETIME(6)',        category:'날짜시간',note:'',warning:false,custom:false},
{id:317,src_db:'oracle',src_type:'TIMESTAMP WITH TIME ZONE',tgt_db:'mysql',tgt_type:'DATETIME(6)',category:'날짜시간',note:'시간대 손실',warning:true,custom:false},
{id:318,src_db:'oracle',src_type:'INTERVAL YEAR TO MONTH',tgt_db:'mysql',tgt_type:'VARCHAR(30)', category:'날짜시간',note:'수동 변환 필요',warning:true,custom:false},
{id:319,src_db:'oracle',src_type:'BLOB',            tgt_db:'mysql',tgt_type:'LONGBLOB',           category:'바이너리',note:'',warning:false,custom:false},
{id:320,src_db:'oracle',src_type:'RAW(n)',          tgt_db:'mysql',tgt_type:'VARBINARY(n)',       category:'바이너리',note:'',warning:false,custom:false},
{id:321,src_db:'oracle',src_type:'LONG RAW',        tgt_db:'mysql',tgt_type:'LONGBLOB',           category:'바이너리',note:'deprecated',warning:true,custom:false},
{id:322,src_db:'oracle',src_type:'XMLTYPE',         tgt_db:'mysql',tgt_type:'LONGTEXT',           category:'JSON-XML',note:'XML 검증 없음',warning:true,custom:false},
{id:323,src_db:'oracle',src_type:'ROWID',           tgt_db:'mysql',tgt_type:'VARCHAR(18)',        category:'기타',    note:'의미 변환 필요',warning:true,custom:false},
// ═══════════════════════════ Oracle → PostgreSQL ═══════════════════
{id:401,src_db:'oracle',src_type:'NUMBER(p,s)',     tgt_db:'postgresql',tgt_type:'NUMERIC(p,s)', category:'숫자',    note:'',warning:false,custom:false},
{id:402,src_db:'oracle',src_type:'NUMBER(p)',       tgt_db:'postgresql',tgt_type:'BIGINT',        category:'숫자',    note:'',warning:false,custom:false},
{id:403,src_db:'oracle',src_type:'NUMBER',          tgt_db:'postgresql',tgt_type:'NUMERIC',       category:'숫자',    note:'',warning:false,custom:false},
{id:404,src_db:'oracle',src_type:'VARCHAR2(n)',     tgt_db:'postgresql',tgt_type:'VARCHAR(n)',    category:'문자열',  note:'',warning:false,custom:false},
{id:405,src_db:'oracle',src_type:'CLOB',            tgt_db:'postgresql',tgt_type:'TEXT',          category:'문자열',  note:'',warning:false,custom:false},
{id:406,src_db:'oracle',src_type:'DATE',            tgt_db:'postgresql',tgt_type:'TIMESTAMP',     category:'날짜시간',note:'Oracle DATE 시간 포함',warning:true,custom:false},
{id:407,src_db:'oracle',src_type:'TIMESTAMP(n)',    tgt_db:'postgresql',tgt_type:'TIMESTAMP(n)', category:'날짜시간',note:'',warning:false,custom:false},
{id:408,src_db:'oracle',src_type:'TIMESTAMP WITH TIME ZONE',tgt_db:'postgresql',tgt_type:'TIMESTAMPTZ',category:'날짜시간',note:'',warning:false,custom:false},
{id:409,src_db:'oracle',src_type:'BLOB',            tgt_db:'postgresql',tgt_type:'BYTEA',         category:'바이너리',note:'',warning:false,custom:false},
{id:410,src_db:'oracle',src_type:'RAW(n)',          tgt_db:'postgresql',tgt_type:'BYTEA',         category:'바이너리',note:'',warning:false,custom:false},
{id:411,src_db:'oracle',src_type:'XMLTYPE',         tgt_db:'postgresql',tgt_type:'XML',           category:'JSON-XML',note:'',warning:false,custom:false},
{id:412,src_db:'oracle',src_type:'SDO_GEOMETRY',    tgt_db:'postgresql',tgt_type:'GEOMETRY (PostGIS)',category:'공간',note:'PostGIS 필요',warning:true,custom:false},
// ═══════════════════════════ Oracle → SQL Server ═══════════════════
{id:501,src_db:'oracle',src_type:'NUMBER(p,s)',     tgt_db:'mssql',tgt_type:'DECIMAL(p,s)',      category:'숫자',    note:'',warning:false,custom:false},
{id:502,src_db:'oracle',src_type:'NUMBER(p)',       tgt_db:'mssql',tgt_type:'BIGINT',             category:'숫자',    note:'',warning:false,custom:false},
{id:503,src_db:'oracle',src_type:'NUMBER',          tgt_db:'mssql',tgt_type:'FLOAT',              category:'숫자',    note:'',warning:false,custom:false},
{id:504,src_db:'oracle',src_type:'VARCHAR2(n)',     tgt_db:'mssql',tgt_type:'NVARCHAR(n)',       category:'문자열',  note:'',warning:false,custom:false},
{id:505,src_db:'oracle',src_type:'NVARCHAR2(n)',    tgt_db:'mssql',tgt_type:'NVARCHAR(n)',       category:'문자열',  note:'',warning:false,custom:false},
{id:506,src_db:'oracle',src_type:'CLOB',            tgt_db:'mssql',tgt_type:'NVARCHAR(MAX)',     category:'문자열',  note:'',warning:false,custom:false},
{id:507,src_db:'oracle',src_type:'BLOB',            tgt_db:'mssql',tgt_type:'VARBINARY(MAX)',    category:'바이너리',note:'',warning:false,custom:false},
{id:508,src_db:'oracle',src_type:'DATE',            tgt_db:'mssql',tgt_type:'DATETIME2(0)',      category:'날짜시간',note:'Oracle DATE 시간 포함',warning:true,custom:false},
{id:509,src_db:'oracle',src_type:'TIMESTAMP(n)',    tgt_db:'mssql',tgt_type:'DATETIME2(n)',      category:'날짜시간',note:'',warning:false,custom:false},
{id:510,src_db:'oracle',src_type:'XMLTYPE',         tgt_db:'mssql',tgt_type:'XML',               category:'JSON-XML',note:'',warning:false,custom:false},
// ═══════════════════════════ PostgreSQL → MySQL ════════════════════
{id:601,src_db:'postgresql',src_type:'BOOLEAN',     tgt_db:'mysql',tgt_type:'TINYINT(1)',        category:'부울',    note:'',warning:false,custom:false},
{id:602,src_db:'postgresql',src_type:'SMALLINT',    tgt_db:'mysql',tgt_type:'SMALLINT',          category:'숫자',    note:'',warning:false,custom:false},
{id:603,src_db:'postgresql',src_type:'INTEGER',     tgt_db:'mysql',tgt_type:'INT',               category:'숫자',    note:'',warning:false,custom:false},
{id:604,src_db:'postgresql',src_type:'BIGINT',      tgt_db:'mysql',tgt_type:'BIGINT',            category:'숫자',    note:'',warning:false,custom:false},
{id:605,src_db:'postgresql',src_type:'SERIAL',      tgt_db:'mysql',tgt_type:'INT AUTO_INCREMENT',category:'숫자',    note:'',warning:false,custom:false},
{id:606,src_db:'postgresql',src_type:'BIGSERIAL',   tgt_db:'mysql',tgt_type:'BIGINT AUTO_INCREMENT',category:'숫자', note:'',warning:false,custom:false},
{id:607,src_db:'postgresql',src_type:'REAL',        tgt_db:'mysql',tgt_type:'FLOAT',             category:'숫자',    note:'',warning:false,custom:false},
{id:608,src_db:'postgresql',src_type:'DOUBLE PRECISION',tgt_db:'mysql',tgt_type:'DOUBLE',       category:'숫자',    note:'',warning:false,custom:false},
{id:609,src_db:'postgresql',src_type:'NUMERIC(p,s)',tgt_db:'mysql',tgt_type:'DECIMAL(p,s)',      category:'숫자',    note:'',warning:false,custom:false},
{id:610,src_db:'postgresql',src_type:'VARCHAR(n)',  tgt_db:'mysql',tgt_type:'VARCHAR(n)',        category:'문자열',  note:'',warning:false,custom:false},
{id:611,src_db:'postgresql',src_type:'TEXT',        tgt_db:'mysql',tgt_type:'LONGTEXT',          category:'문자열',  note:'',warning:false,custom:false},
{id:612,src_db:'postgresql',src_type:'CHAR(n)',     tgt_db:'mysql',tgt_type:'CHAR(n)',           category:'문자열',  note:'',warning:false,custom:false},
{id:613,src_db:'postgresql',src_type:'TIMESTAMP',   tgt_db:'mysql',tgt_type:'DATETIME(6)',       category:'날짜시간',note:'',warning:false,custom:false},
{id:614,src_db:'postgresql',src_type:'TIMESTAMPTZ', tgt_db:'mysql',tgt_type:'DATETIME(6)',       category:'날짜시간',note:'시간대 손실',warning:true,custom:false},
{id:615,src_db:'postgresql',src_type:'DATE',        tgt_db:'mysql',tgt_type:'DATE',              category:'날짜시간',note:'',warning:false,custom:false},
{id:616,src_db:'postgresql',src_type:'TIME',        tgt_db:'mysql',tgt_type:'TIME',              category:'날짜시간',note:'',warning:false,custom:false},
{id:617,src_db:'postgresql',src_type:'BYTEA',       tgt_db:'mysql',tgt_type:'LONGBLOB',          category:'바이너리',note:'',warning:false,custom:false},
{id:618,src_db:'postgresql',src_type:'JSON',        tgt_db:'mysql',tgt_type:'JSON',              category:'JSON-XML',note:'',warning:false,custom:false},
{id:619,src_db:'postgresql',src_type:'JSONB',       tgt_db:'mysql',tgt_type:'JSON',              category:'JSON-XML',note:'인덱스 정보 손실',warning:true,custom:false},
{id:620,src_db:'postgresql',src_type:'UUID',        tgt_db:'mysql',tgt_type:'CHAR(36)',          category:'문자열',  note:'',warning:false,custom:false},
{id:621,src_db:'postgresql',src_type:'ARRAY',       tgt_db:'mysql',tgt_type:'JSON',              category:'기타',    note:'정규화 권장',warning:true,custom:false},
{id:622,src_db:'postgresql',src_type:'HSTORE',      tgt_db:'mysql',tgt_type:'JSON',              category:'JSON-XML',note:'',warning:false,custom:false},
// ═══════════════════════════ DB2 → MySQL ══════════════════════════
{id:701,src_db:'db2',src_type:'SMALLINT',           tgt_db:'mysql',tgt_type:'SMALLINT',          category:'숫자',    note:'',warning:false,custom:false},
{id:702,src_db:'db2',src_type:'INTEGER',            tgt_db:'mysql',tgt_type:'INT',               category:'숫자',    note:'',warning:false,custom:false},
{id:703,src_db:'db2',src_type:'BIGINT',             tgt_db:'mysql',tgt_type:'BIGINT',            category:'숫자',    note:'',warning:false,custom:false},
{id:704,src_db:'db2',src_type:'DECIMAL(p,s)',       tgt_db:'mysql',tgt_type:'DECIMAL(p,s)',      category:'숫자',    note:'',warning:false,custom:false},
{id:705,src_db:'db2',src_type:'REAL',               tgt_db:'mysql',tgt_type:'FLOAT',             category:'숫자',    note:'',warning:false,custom:false},
{id:706,src_db:'db2',src_type:'DOUBLE',             tgt_db:'mysql',tgt_type:'DOUBLE',            category:'숫자',    note:'',warning:false,custom:false},
{id:707,src_db:'db2',src_type:'VARCHAR(n)',         tgt_db:'mysql',tgt_type:'VARCHAR(n)',        category:'문자열',  note:'',warning:false,custom:false},
{id:708,src_db:'db2',src_type:'CHAR(n)',            tgt_db:'mysql',tgt_type:'CHAR(n)',           category:'문자열',  note:'',warning:false,custom:false},
{id:709,src_db:'db2',src_type:'CLOB(n)',            tgt_db:'mysql',tgt_type:'LONGTEXT',          category:'문자열',  note:'',warning:false,custom:false},
{id:710,src_db:'db2',src_type:'DATE',               tgt_db:'mysql',tgt_type:'DATE',              category:'날짜시간',note:'',warning:false,custom:false},
{id:711,src_db:'db2',src_type:'TIME',               tgt_db:'mysql',tgt_type:'TIME',              category:'날짜시간',note:'',warning:false,custom:false},
{id:712,src_db:'db2',src_type:'TIMESTAMP(n)',       tgt_db:'mysql',tgt_type:'DATETIME(6)',       category:'날짜시간',note:'',warning:false,custom:false},
{id:713,src_db:'db2',src_type:'BLOB(n)',            tgt_db:'mysql',tgt_type:'LONGBLOB',          category:'바이너리',note:'',warning:false,custom:false},
{id:714,src_db:'db2',src_type:'XML',                tgt_db:'mysql',tgt_type:'LONGTEXT',          category:'JSON-XML',note:'',warning:false,custom:false},
// ═══════════════════════════ MySQL → Snowflake ════════════════════
{id:801,src_db:'mysql',src_type:'TINYINT',          tgt_db:'snowflake',tgt_type:'NUMBER(3,0)',   category:'숫자',    note:'',warning:false,custom:false},
{id:802,src_db:'mysql',src_type:'INT',              tgt_db:'snowflake',tgt_type:'NUMBER(10,0)',  category:'숫자',    note:'',warning:false,custom:false},
{id:803,src_db:'mysql',src_type:'BIGINT',           tgt_db:'snowflake',tgt_type:'NUMBER(19,0)',  category:'숫자',    note:'',warning:false,custom:false},
{id:804,src_db:'mysql',src_type:'FLOAT',            tgt_db:'snowflake',tgt_type:'FLOAT',         category:'숫자',    note:'',warning:false,custom:false},
{id:805,src_db:'mysql',src_type:'DOUBLE',           tgt_db:'snowflake',tgt_type:'DOUBLE',        category:'숫자',    note:'',warning:false,custom:false},
{id:806,src_db:'mysql',src_type:'DECIMAL(p,s)',     tgt_db:'snowflake',tgt_type:'NUMBER(p,s)',   category:'숫자',    note:'',warning:false,custom:false},
{id:807,src_db:'mysql',src_type:'VARCHAR(n)',       tgt_db:'snowflake',tgt_type:'VARCHAR(n)',    category:'문자열',  note:'최대 16777216',warning:false,custom:false},
{id:808,src_db:'mysql',src_type:'TEXT',             tgt_db:'snowflake',tgt_type:'TEXT',          category:'문자열',  note:'',warning:false,custom:false},
{id:809,src_db:'mysql',src_type:'DATETIME',         tgt_db:'snowflake',tgt_type:'TIMESTAMP_NTZ', category:'날짜시간',note:'',warning:false,custom:false},
{id:810,src_db:'mysql',src_type:'TIMESTAMP',        tgt_db:'snowflake',tgt_type:'TIMESTAMP_LTZ', category:'날짜시간',note:'',warning:false,custom:false},
{id:811,src_db:'mysql',src_type:'DATE',             tgt_db:'snowflake',tgt_type:'DATE',          category:'날짜시간',note:'',warning:false,custom:false},
{id:812,src_db:'mysql',src_type:'BLOB',             tgt_db:'snowflake',tgt_type:'BINARY',        category:'바이너리',note:'최대 8MB',warning:true,custom:false},
{id:813,src_db:'mysql',src_type:'JSON',             tgt_db:'snowflake',tgt_type:'VARIANT',       category:'JSON-XML',note:'',warning:false,custom:false},
// ═══════════════════════════ MySQL → BigQuery ════════════════════
{id:901,src_db:'mysql',src_type:'TINYINT',          tgt_db:'bigquery',tgt_type:'INT64',          category:'숫자',    note:'',warning:false,custom:false},
{id:902,src_db:'mysql',src_type:'INT',              tgt_db:'bigquery',tgt_type:'INT64',          category:'숫자',    note:'',warning:false,custom:false},
{id:903,src_db:'mysql',src_type:'BIGINT',           tgt_db:'bigquery',tgt_type:'INT64',          category:'숫자',    note:'',warning:false,custom:false},
{id:904,src_db:'mysql',src_type:'FLOAT',            tgt_db:'bigquery',tgt_type:'FLOAT64',        category:'숫자',    note:'',warning:false,custom:false},
{id:905,src_db:'mysql',src_type:'DOUBLE',           tgt_db:'bigquery',tgt_type:'FLOAT64',        category:'숫자',    note:'',warning:false,custom:false},
{id:906,src_db:'mysql',src_type:'DECIMAL(p,s)',     tgt_db:'bigquery',tgt_type:'NUMERIC(p,s)',   category:'숫자',    note:'최대 NUMERIC(29,9)',warning:true,custom:false},
{id:907,src_db:'mysql',src_type:'TINYINT(1)',       tgt_db:'bigquery',tgt_type:'BOOL',           category:'부울',    note:'',warning:false,custom:false},
{id:908,src_db:'mysql',src_type:'VARCHAR(n)',       tgt_db:'bigquery',tgt_type:'STRING',         category:'문자열',  note:'',warning:false,custom:false},
{id:909,src_db:'mysql',src_type:'TEXT',             tgt_db:'bigquery',tgt_type:'STRING',         category:'문자열',  note:'',warning:false,custom:false},
{id:910,src_db:'mysql',src_type:'DATETIME',         tgt_db:'bigquery',tgt_type:'DATETIME',       category:'날짜시간',note:'',warning:false,custom:false},
{id:911,src_db:'mysql',src_type:'TIMESTAMP',        tgt_db:'bigquery',tgt_type:'TIMESTAMP',      category:'날짜시간',note:'',warning:false,custom:false},
{id:912,src_db:'mysql',src_type:'DATE',             tgt_db:'bigquery',tgt_type:'DATE',           category:'날짜시간',note:'',warning:false,custom:false},
{id:913,src_db:'mysql',src_type:'BLOB',             tgt_db:'bigquery',tgt_type:'BYTES',          category:'바이너리',note:'최대 10MB',warning:true,custom:false},
{id:914,src_db:'mysql',src_type:'JSON',             tgt_db:'bigquery',tgt_type:'JSON',           category:'JSON-XML',note:'',warning:false,custom:false},
// ═══════════════════════════ MySQL → ClickHouse ═══════════════════
{id:1001,src_db:'mysql',src_type:'TINYINT',         tgt_db:'clickhouse',tgt_type:'Int8',         category:'숫자',    note:'',warning:false,custom:false},
{id:1002,src_db:'mysql',src_type:'SMALLINT',        tgt_db:'clickhouse',tgt_type:'Int16',        category:'숫자',    note:'',warning:false,custom:false},
{id:1003,src_db:'mysql',src_type:'INT',             tgt_db:'clickhouse',tgt_type:'Int32',        category:'숫자',    note:'',warning:false,custom:false},
{id:1004,src_db:'mysql',src_type:'BIGINT',          tgt_db:'clickhouse',tgt_type:'Int64',        category:'숫자',    note:'',warning:false,custom:false},
{id:1005,src_db:'mysql',src_type:'INT UNSIGNED',    tgt_db:'clickhouse',tgt_type:'UInt32',       category:'숫자',    note:'',warning:false,custom:false},
{id:1006,src_db:'mysql',src_type:'FLOAT',           tgt_db:'clickhouse',tgt_type:'Float32',      category:'숫자',    note:'',warning:false,custom:false},
{id:1007,src_db:'mysql',src_type:'DOUBLE',          tgt_db:'clickhouse',tgt_type:'Float64',      category:'숫자',    note:'',warning:false,custom:false},
{id:1008,src_db:'mysql',src_type:'DECIMAL(p,s)',    tgt_db:'clickhouse',tgt_type:'Decimal(p,s)', category:'숫자',    note:'',warning:false,custom:false},
{id:1009,src_db:'mysql',src_type:'VARCHAR(n)',      tgt_db:'clickhouse',tgt_type:'String',       category:'문자열',  note:'ClickHouse String은 가변',warning:false,custom:false},
{id:1010,src_db:'mysql',src_type:'TEXT',            tgt_db:'clickhouse',tgt_type:'String',       category:'문자열',  note:'',warning:false,custom:false},
{id:1011,src_db:'mysql',src_type:'CHAR(n)',         tgt_db:'clickhouse',tgt_type:'FixedString(n)',category:'문자열',  note:'',warning:false,custom:false},
{id:1012,src_db:'mysql',src_type:'DATE',            tgt_db:'clickhouse',tgt_type:'Date',         category:'날짜시간',note:'',warning:false,custom:false},
{id:1013,src_db:'mysql',src_type:'DATETIME',        tgt_db:'clickhouse',tgt_type:'DateTime64(6)',category:'날짜시간',note:'',warning:false,custom:false},
{id:1014,src_db:'mysql',src_type:'TINYINT(1)',      tgt_db:'clickhouse',tgt_type:'Bool',         category:'부울',    note:'',warning:false,custom:false},
{id:1015,src_db:'mysql',src_type:'JSON',            tgt_db:'clickhouse',tgt_type:'String',       category:'JSON-XML',note:'JSON 파싱은 함수 사용',warning:false,custom:false},
// ═════════════════ MySQL → MSSQL 함수/문법 변환 규칙 ══════════════════
// 날짜함수
{id:2001,src_db:'mysql',src_type:"DATE_FORMAT(col,'%Y-%m-%d')",tgt_db:'mssql',tgt_type:"FORMAT(col,'yyyy-MM-dd')",category:'날짜함수',note:'포맷: %Y→yyyy %m→MM %d→dd %H→HH %i→mm %s→ss',warning:false,custom:false},
{id:2002,src_db:'mysql',src_type:"DATE_FORMAT(col,'%Y-%m')",   tgt_db:'mssql',tgt_type:"FORMAT(col,'yyyy-MM')",  category:'날짜함수',note:'월 단위 집계. GROUP BY 포함 동일 변환',warning:false,custom:false},
{id:2003,src_db:'mysql',src_type:"DATE_FORMAT(col,'%H:%i:%s')",tgt_db:'mssql',tgt_type:"FORMAT(col,'HH:mm:ss')", category:'날짜함수',note:'시간 포맷',warning:false,custom:false},
{id:2004,src_db:'mysql',src_type:'NOW()',                       tgt_db:'mssql',tgt_type:'GETDATE()',              category:'날짜함수',note:'현재 날짜/시간',warning:false,custom:false},
{id:2005,src_db:'mysql',src_type:'CURDATE()',                   tgt_db:'mssql',tgt_type:'CAST(GETDATE() AS DATE)',category:'날짜함수',note:'날짜만 반환',warning:false,custom:false},
{id:2006,src_db:'mysql',src_type:'CURTIME()',                   tgt_db:'mssql',tgt_type:'CAST(GETDATE() AS TIME)',category:'날짜함수',note:'시간만 반환',warning:false,custom:false},
{id:2007,src_db:'mysql',src_type:'DATEDIFF(a,b)',               tgt_db:'mssql',tgt_type:'DATEDIFF(day,b,a)',     category:'날짜함수',note:'⚠ 인자 순서 반대! MySQL=a-b, MSSQL=단위+역순',warning:true,custom:false},
{id:2008,src_db:'mysql',src_type:'DATE_ADD(col,INTERVAL n DAY)',tgt_db:'mssql',tgt_type:'DATEADD(day,n,col)',   category:'날짜함수',note:'INTERVAL DAY/MONTH/YEAR/HOUR/MINUTE/SECOND',warning:false,custom:false},
{id:2009,src_db:'mysql',src_type:'DATE_SUB(col,INTERVAL n DAY)',tgt_db:'mssql',tgt_type:'DATEADD(day,-n,col)',  category:'날짜함수',note:'DATE_SUB → DATEADD 음수값',warning:false,custom:false},
{id:2010,src_db:'mysql',src_type:'TIMESTAMPDIFF(MONTH,a,b)',    tgt_db:'mssql',tgt_type:'DATEDIFF(month,a,b)',  category:'날짜함수',note:'단위가 첫 번째 인자로 이동',warning:false,custom:false},
{id:2011,src_db:'mysql',src_type:'HOUR(col)/MINUTE(col)/SECOND(col)',tgt_db:'mssql',tgt_type:'DATEPART(hour/minute/second,col)',category:'날짜함수',note:'',warning:false,custom:false},
{id:2012,src_db:'mysql',src_type:'DAYOFWEEK(col)',              tgt_db:'mssql',tgt_type:'DATEPART(weekday,col)', category:'날짜함수',note:'⚠ SET DATEFIRST 영향. 확인 필요',warning:true,custom:false},
{id:2013,src_db:'mysql',src_type:'WEEK(col)',                   tgt_db:'mssql',tgt_type:'DATEPART(week,col)',    category:'날짜함수',note:'⚠ 주차 계산 기준 다를 수 있음',warning:true,custom:false},
{id:2014,src_db:'mysql',src_type:'STR_TO_DATE(str,fmt)',        tgt_db:'mssql',tgt_type:'CONVERT(DATETIME,str,120)',category:'날짜함수',note:'형식 120=ISO datetime 112=yyyyMMdd',warning:true,custom:false},
{id:2015,src_db:'mysql',src_type:'FROM_UNIXTIME(ts)',           tgt_db:'mssql',tgt_type:"DATEADD(second,ts,'1970-01-01')",category:'날짜함수',note:'Unix 타임스탬프 변환',warning:false,custom:false},
{id:2016,src_db:'mysql',src_type:'UNIX_TIMESTAMP(col)',         tgt_db:'mssql',tgt_type:"DATEDIFF(second,'1970-01-01',col)",category:'날짜함수',note:'Unix 타임스탬프 역변환',warning:false,custom:false},
{id:2017,src_db:'mysql',src_type:'LAST_DAY(col)',               tgt_db:'mssql',tgt_type:'EOMONTH(col)',           category:'날짜함수',note:'월 마지막 날. MSSQL 2012+',warning:false,custom:false},
// 문자열함수
{id:2101,src_db:'mysql',src_type:'IFNULL(a,b)',                 tgt_db:'mssql',tgt_type:'ISNULL(a,b)',            category:'문자열함수',note:'NULL 대체',warning:false,custom:false},
{id:2102,src_db:'mysql',src_type:'IF(cond,a,b)',                tgt_db:'mssql',tgt_type:'IIF(cond,a,b)',          category:'문자열함수',note:'MSSQL 2012+. 구버전은 CASE WHEN',warning:false,custom:false},
{id:2103,src_db:'mysql',src_type:"GROUP_CONCAT(col SEPARATOR ',')",tgt_db:'mssql',tgt_type:"STRING_AGG(col,',')",category:'문자열함수',note:'⚠ MSSQL 2017+. 구버전은 FOR XML PATH',warning:true,custom:false},
{id:2104,src_db:'mysql',src_type:"GROUP_CONCAT(col ORDER BY col)",tgt_db:'mssql',tgt_type:"STRING_AGG(col,',') WITHIN GROUP (ORDER BY col)",category:'문자열함수',note:'정렬 포함',warning:false,custom:false},
{id:2105,src_db:'mysql',src_type:'SUBSTR(str,pos,len)',         tgt_db:'mssql',tgt_type:'SUBSTRING(str,pos,len)', category:'문자열함수',note:'함수명만 다름',warning:false,custom:false},
{id:2106,src_db:'mysql',src_type:'LOCATE(sub,str)',             tgt_db:'mssql',tgt_type:'CHARINDEX(sub,str)',      category:'문자열함수',note:'인자 순서 동일',warning:false,custom:false},
{id:2107,src_db:'mysql',src_type:'INSTR(str,sub)',              tgt_db:'mssql',tgt_type:'CHARINDEX(sub,str)',      category:'문자열함수',note:'⚠ 인자 순서 반대! INSTR(str,sub)→CHARINDEX(sub,str)',warning:true,custom:false},
{id:2108,src_db:'mysql',src_type:'LENGTH(str)',                 tgt_db:'mssql',tgt_type:'LEN(str)',                category:'문자열함수',note:'⚠ MySQL=바이트수 vs MSSQL=문자수. 멀티바이트 주의',warning:true,custom:false},
{id:2109,src_db:'mysql',src_type:'CHAR_LENGTH(str)',            tgt_db:'mssql',tgt_type:'LEN(str)',                category:'문자열함수',note:'문자 수 기준 동일',warning:false,custom:false},
{id:2110,src_db:'mysql',src_type:'LPAD(str,len,pad)',           tgt_db:'mssql',tgt_type:'RIGHT(REPLICATE(pad,len)+str,len)',category:'문자열함수',note:'MSSQL LPAD 없음',warning:false,custom:false},
{id:2111,src_db:'mysql',src_type:'RPAD(str,len,pad)',           tgt_db:'mssql',tgt_type:'LEFT(str+REPLICATE(pad,len),len)',category:'문자열함수',note:'MSSQL RPAD 없음',warning:false,custom:false},
{id:2112,src_db:'mysql',src_type:'REPEAT(str,n)',               tgt_db:'mssql',tgt_type:'REPLICATE(str,n)',        category:'문자열함수',note:'함수명만 다름',warning:false,custom:false},
{id:2113,src_db:'mysql',src_type:'INSERT(str,pos,len,new)',     tgt_db:'mssql',tgt_type:'STUFF(str,pos,len,new)',  category:'문자열함수',note:'함수명만 다름',warning:false,custom:false},
{id:2114,src_db:'mysql',src_type:'SUBSTRING_INDEX(str,del,n)',  tgt_db:'mssql',tgt_type:'/* CHARINDEX 조합 필요 */', category:'문자열함수',note:'⚠ MSSQL 직접 미지원',warning:true,custom:false},
{id:2115,src_db:'mysql',src_type:'ELT(n,v1,v2)',               tgt_db:'mssql',tgt_type:'CHOOSE(n,v1,v2)',          category:'문자열함수',note:'MSSQL 2012+',warning:false,custom:false},
{id:2116,src_db:'mysql',src_type:'FIELD(val,v1,v2)',            tgt_db:'mssql',tgt_type:'CASE WHEN val=v1 THEN 1 WHEN val=v2 THEN 2 END',category:'문자열함수',note:'⚠ MSSQL 미지원',warning:true,custom:false},
// 수학함수
{id:2201,src_db:'mysql',src_type:'TRUNCATE(n,d)',               tgt_db:'mssql',tgt_type:'ROUND(n,d,1)',            category:'수학함수',note:'3번째 인자=1이면 TRUNCATE 동작',warning:false,custom:false},
{id:2202,src_db:'mysql',src_type:'POW(a,b)',                    tgt_db:'mssql',tgt_type:'POWER(a,b)',              category:'수학함수',note:'함수명만 다름',warning:false,custom:false},
{id:2203,src_db:'mysql',src_type:'STD(col)',                    tgt_db:'mssql',tgt_type:'STDEV(col)',              category:'수학함수',note:'표본표준편차',warning:false,custom:false},
{id:2204,src_db:'mysql',src_type:'GREATEST(a,b,...)',           tgt_db:'mssql',tgt_type:'(SELECT MAX(v) FROM (VALUES(a),(b)) t(v))',category:'수학함수',note:'⚠ MSSQL 미지원',warning:true,custom:false},
{id:2205,src_db:'mysql',src_type:'LEAST(a,b,...)',              tgt_db:'mssql',tgt_type:'(SELECT MIN(v) FROM (VALUES(a),(b)) t(v))',category:'수학함수',note:'⚠ MSSQL 미지원',warning:true,custom:false},
// 조건함수
{id:2301,src_db:'mysql',src_type:'ISNULL(col) 불리언반환',     tgt_db:'mssql',tgt_type:'CASE WHEN col IS NULL THEN 1 ELSE 0 END',category:'조건함수',note:'⚠ MySQL ISNULL=불리언 vs MSSQL ISNULL=대체값. 완전히 다름',warning:true,custom:false},
{id:2302,src_db:'mysql',src_type:'COALESCE(a,b,...)',           tgt_db:'mssql',tgt_type:'COALESCE(a,b,...)',        category:'조건함수',note:'동일',warning:false,custom:false},
{id:2303,src_db:'mysql',src_type:'GREATEST/LEAST',             tgt_db:'mssql',tgt_type:'VALUES 서브쿼리',           category:'조건함수',note:'⚠ MSSQL 미지원',warning:true,custom:false},
// 페이징
{id:2401,src_db:'mysql',src_type:'LIMIT n',                     tgt_db:'mssql',tgt_type:'SELECT TOP n ...',        category:'페이징',note:'⚠ LIMIT 제거 후 SELECT 뒤 TOP n으로 이동',warning:true,custom:false},
{id:2402,src_db:'mysql',src_type:'LIMIT n OFFSET m',            tgt_db:'mssql',tgt_type:'OFFSET m ROWS FETCH NEXT n ROWS ONLY',category:'페이징',note:'ORDER BY 필수. MSSQL 2012+',warning:true,custom:false},
// JSON함수
{id:2501,src_db:'mysql',src_type:"JSON_EXTRACT(col,'$.key')",   tgt_db:'mssql',tgt_type:"JSON_VALUE(col,'$.key')", category:'JSON함수',note:'스칼라 값 추출',warning:false,custom:false},
{id:2502,src_db:'mysql',src_type:"col->'$.key' 단축문법",       tgt_db:'mssql',tgt_type:"JSON_VALUE(col,'$.key')", category:'JSON함수',note:'',warning:false,custom:false},
{id:2503,src_db:'mysql',src_type:"JSON_EXTRACT(col,'$.arr') 배열",tgt_db:'mssql',tgt_type:"JSON_QUERY(col,'$.arr')",category:'JSON함수',note:'객체/배열은 JSON_QUERY',warning:false,custom:false},
{id:2504,src_db:'mysql',src_type:'JSON_ARRAYAGG(col)',          tgt_db:'mssql',tgt_type:"'['+STRING_AGG(col,',')+']'",category:'JSON함수',note:'⚠ MSSQL 2017+',warning:true,custom:false},
// DDL문법
{id:2601,src_db:'mysql',src_type:'AUTO_INCREMENT',              tgt_db:'mssql',tgt_type:'IDENTITY(1,1)',            category:'DDL문법',note:'',warning:false,custom:false},
{id:2602,src_db:'mysql',src_type:'`백틱 식별자`',               tgt_db:'mssql',tgt_type:'[대괄호 식별자]',           category:'DDL문법',note:'',warning:false,custom:false},
{id:2603,src_db:'mysql',src_type:'ENGINE=InnoDB CHARSET=utf8mb4',tgt_db:'mssql',tgt_type:'/* 제거 */',             category:'DDL문법',note:'MSSQL에 없는 개념',warning:false,custom:false},
{id:2604,src_db:'mysql',src_type:'UNSIGNED INT',                tgt_db:'mssql',tgt_type:'INT (UNSIGNED 미지원)',    category:'DDL문법',note:'⚠ 범위 초과 주의',warning:true,custom:false},
{id:2605,src_db:'mysql',src_type:'ENUM("a","b")',               tgt_db:'mssql',tgt_type:'VARCHAR(n) + CHECK 제약',  category:'DDL문법',note:'⚠ ENUM 없음',warning:true,custom:false},
{id:2606,src_db:'mysql',src_type:'INSERT INTO ... ON DUPLICATE KEY UPDATE',tgt_db:'mssql',tgt_type:'MERGE INTO ... WHEN MATCHED UPDATE WHEN NOT MATCHED INSERT',category:'DDL문법',note:'⚠ UPSERT 문법 완전히 다름',warning:true,custom:false},
{id:2607,src_db:'mysql',src_type:'INSERT IGNORE INTO',          tgt_db:'mssql',tgt_type:'TRY/CATCH 또는 MERGE',    category:'DDL문법',note:'⚠ IGNORE 없음',warning:true,custom:false},
{id:2608,src_db:'mysql',src_type:'REPLACE INTO',                tgt_db:'mssql',tgt_type:'MERGE INTO',               category:'DDL문법',note:'DELETE+INSERT → MERGE',warning:true,custom:false},
// ═════════════════ MSSQL → MySQL 함수/문법 변환 규칙 ══════════════════
{id:3001,src_db:'mssql',src_type:"FORMAT(col,'yyyy-MM-dd')",    tgt_db:'mysql',tgt_type:"DATE_FORMAT(col,'%Y-%m-%d')",category:'날짜함수',note:'포맷 역변환',warning:false,custom:false},
{id:3002,src_db:'mssql',src_type:"FORMAT(col,'yyyy-MM')",       tgt_db:'mysql',tgt_type:"DATE_FORMAT(col,'%Y-%m')",  category:'날짜함수',note:'',warning:false,custom:false},
{id:3003,src_db:'mssql',src_type:'GETDATE()',                   tgt_db:'mysql',tgt_type:'NOW()',                     category:'날짜함수',note:'',warning:false,custom:false},
{id:3004,src_db:'mssql',src_type:'GETUTCDATE()',                tgt_db:'mysql',tgt_type:'UTC_TIMESTAMP()',           category:'날짜함수',note:'',warning:false,custom:false},
{id:3005,src_db:'mssql',src_type:'DATEADD(day,n,col)',          tgt_db:'mysql',tgt_type:'DATE_ADD(col,INTERVAL n DAY)',category:'날짜함수',note:'인자 순서 다름',warning:false,custom:false},
{id:3006,src_db:'mssql',src_type:'DATEDIFF(day,a,b)',           tgt_db:'mysql',tgt_type:'DATEDIFF(b,a)',             category:'날짜함수',note:'⚠ 인자 순서 반대!',warning:true,custom:false},
{id:3007,src_db:'mssql',src_type:'DATEPART(month,col)',         tgt_db:'mysql',tgt_type:'MONTH(col)',                category:'날짜함수',note:'year→YEAR month→MONTH day→DAY',warning:false,custom:false},
{id:3008,src_db:'mssql',src_type:'CONVERT(VARCHAR,col,120)',    tgt_db:'mysql',tgt_type:"DATE_FORMAT(col,'%Y-%m-%d %H:%i:%s')",category:'날짜함수',note:'형식 120=ISO datetime',warning:false,custom:false},
{id:3009,src_db:'mssql',src_type:'EOMONTH(col)',                tgt_db:'mysql',tgt_type:'LAST_DAY(col)',             category:'날짜함수',note:'월 마지막 날',warning:false,custom:false},
{id:3101,src_db:'mssql',src_type:'ISNULL(a,b)',                 tgt_db:'mysql',tgt_type:'IFNULL(a,b)',               category:'문자열함수',note:'',warning:false,custom:false},
{id:3102,src_db:'mssql',src_type:'IIF(cond,a,b)',               tgt_db:'mysql',tgt_type:'IF(cond,a,b)',              category:'문자열함수',note:'',warning:false,custom:false},
{id:3103,src_db:'mssql',src_type:"STRING_AGG(col,',')",         tgt_db:'mysql',tgt_type:"GROUP_CONCAT(col SEPARATOR ',')",category:'문자열함수',note:'',warning:false,custom:false},
{id:3104,src_db:'mssql',src_type:'CHARINDEX(sub,str)',          tgt_db:'mysql',tgt_type:'LOCATE(sub,str)',           category:'문자열함수',note:'',warning:false,custom:false},
{id:3105,src_db:'mssql',src_type:'LEN(str)',                    tgt_db:'mysql',tgt_type:'CHAR_LENGTH(str)',          category:'문자열함수',note:'',warning:false,custom:false},
{id:3106,src_db:'mssql',src_type:'REPLICATE(str,n)',            tgt_db:'mysql',tgt_type:'REPEAT(str,n)',             category:'문자열함수',note:'',warning:false,custom:false},
{id:3107,src_db:'mssql',src_type:'STUFF(str,pos,len,new)',      tgt_db:'mysql',tgt_type:'INSERT(str,pos,len,new)',   category:'문자열함수',note:'',warning:false,custom:false},
{id:3201,src_db:'mssql',src_type:'SELECT TOP n ...',            tgt_db:'mysql',tgt_type:'SELECT ... LIMIT n',        category:'페이징',note:'⚠ TOP 제거 후 끝에 LIMIT',warning:true,custom:false},
{id:3202,src_db:'mssql',src_type:'OFFSET n ROWS FETCH NEXT m ROWS ONLY',tgt_db:'mysql',tgt_type:'LIMIT m OFFSET n',category:'페이징',note:'',warning:false,custom:false},
{id:3301,src_db:'mssql',src_type:'IDENTITY(1,1)',               tgt_db:'mysql',tgt_type:'AUTO_INCREMENT',            category:'DDL문법',note:'',warning:false,custom:false},
{id:3302,src_db:'mssql',src_type:'[대괄호 식별자]',             tgt_db:'mysql',tgt_type:'`백틱 식별자`',             category:'DDL문법',note:'',warning:false,custom:false},
{id:3303,src_db:'mssql',src_type:'NVARCHAR(n)',                 tgt_db:'mysql',tgt_type:'VARCHAR(n)',                 category:'DDL문법',note:'MySQL VARCHAR는 모두 유니코드',warning:false,custom:false},
{id:3304,src_db:'mssql',src_type:'NVARCHAR(MAX)',               tgt_db:'mysql',tgt_type:'LONGTEXT',                  category:'DDL문법',note:'',warning:false,custom:false},
{id:3305,src_db:'mssql',src_type:'CREATE OR ALTER PROCEDURE',  tgt_db:'mysql',tgt_type:'DROP PROCEDURE IF EXISTS + CREATE',category:'DDL문법',note:'⚠ MySQL OR REPLACE 없음',warning:true,custom:false},
{id:3306,src_db:'mssql',src_type:'ROLLBACK (트리거 내)',        tgt_db:'mysql',tgt_type:'SIGNAL SQLSTATE 45000 (BEFORE 트리거)',category:'DDL문법',note:'⚠ MySQL 트리거 ROLLBACK 불가',warning:true,custom:false},
{id:3307,src_db:'mssql',src_type:'MERGE INTO ... WHEN MATCHED',tgt_db:'mysql',tgt_type:'INSERT ON DUPLICATE KEY UPDATE',category:'DDL문법',note:'⚠ UPSERT 문법 완전히 다름',warning:true,custom:false},
{id:3308,src_db:'mssql',src_type:'WITH CTE AS (...)',           tgt_db:'mysql',tgt_type:'WITH CTE AS (...)',          category:'DDL문법',note:'MySQL 8.0+. 구버전 서브쿼리 대체',warning:false,custom:false},
])
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

.tbl-wrap{padding:0;overflow:hidden}
.map-tbl{width:100%;border-collapse:collapse;font-size:12px}
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
</style>
