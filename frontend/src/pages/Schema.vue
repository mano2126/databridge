<template>
  <div class="schema-page">
    <!-- 미연결 → ConnectPanel -->
    <ConnectPanel v-if="!connector.bothConnected" @connected="loadAll" />

    <!-- 연결됨 → PageHeader + 소스/타겟 선택 + 검색 -->
    <PageHeader v-if="connector.bothConnected" :show-db="true"
                :src-db="connector.source" :tgt-db="connector.target">
      <template #controls>
        <div class="sc-side-tabs">
          <button class="sc-side-tab" :class="{on: selSide==='source'}" @click="switchSide('source')">소스</button>
          <button class="sc-side-tab" :class="{on: selSide==='target'}" @click="switchSide('target')">타겟</button>
        </div>
        <input v-model="tblSearch" class="sc-search" placeholder="테이블 검색..."/>
      </template>
      <template #actions>
        <button class="btn" style="font-size:11.5px;padding:5px 12px" @click="loadAll">
          <span v-if="loadingTbl" class="spinner" style="width:11px;height:11px;display:inline-block;margin-right:3px"></span>
          {{ loadingTbl ? '조회 중...' : '↻ 새로고침' }}
        </button>
      </template>
    </PageHeader>

    <!-- 메인 레이아웃 -->
    <div class="schema-layout">

      <!-- 좌측 트리 -->
      <div class="tree-panel card">
        <div class="tree-header">
          <div>
            <div style="font-size:12px;font-weight:500;color:var(--text-primary)">
              {{ curConn.database || '데이터베이스' }}
            </div>
            <div style="font-size:10.5px;color:var(--text-tertiary)">
              {{ curConn.dbType }} · {{ curConn.host || '-' }}
            </div>
          </div>
          <span class="tbl-count">{{ filteredTables.length }}개</span>
        </div>

        <div v-if="loadingTbl" class="empty-state" style="padding:24px">
          <span class="spinner" style="width:18px;height:18px;display:inline-block"></span>
        </div>
        <div v-else-if="tableError" class="tree-error">{{ tableError }}</div>
        <template v-else>
          <!-- 테이블 섹션 -->
          <div class="tree-sec" @click="openTbls=!openTbls">
            <svg :style="{transform:openTbls?'rotate(90deg)':'',transition:'transform .2s'}"
                 viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"
                 style="width:9px;height:9px"><polyline points="3,2 9,6 3,10"/></svg>
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3" style="width:12px;height:12px;opacity:.6">
              <rect x="1" y="2" width="12" height="10" rx="1"/><line x1="1" y1="5" x2="13" y2="5"/>
            </svg>
            테이블
            <span class="sec-cnt">{{ filteredTables.length }}</span>
          </div>
          <template v-if="openTbls">
            <div v-for="t in filteredTables" :key="t.table_name"
                 class="tree-item" :class="{sel: selTable===t.table_name, 'obj-item': false}"
                 @click="selectTable(t.table_name)">
              <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3"
                   style="width:11px;height:11px;flex-shrink:0;opacity:.45">
                <rect x="1" y="2" width="12" height="10" rx="1"/><line x1="1" y1="5" x2="13" y2="5"/>
              </svg>
              <span class="tree-name">{{ t.table_name }}</span>
              <span class="tree-rows">{{ fmtRows(t.row_count) }}</span>
            </div>
          </template>

          <!-- 오브젝트 섹션들 -->
          <template v-for="(sec, key) in objSections" :key="key">
            <div v-if="objects[key]?.length" class="tree-sec" @click="sec.open=!sec.open">
              <svg :style="{transform:sec.open?'rotate(90deg)':'',transition:'transform .2s'}"
                   viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"
                   style="width:9px;height:9px"><polyline points="3,2 9,6 3,10"/></svg>
              <span style="font-size:11px">{{ sec.icon }}</span>
              {{ sec.label }}
              <span class="sec-cnt">{{ objects[key].length }}</span>
            </div>
            <template v-if="sec.open && objects[key]?.length">
              <div v-for="obj in objects[key]" :key="obj.name"
                   class="tree-item obj-item"
                   :class="{sel: selObj?.name===obj.name && selObj?.type===key}"
                   @click="selectObj(key, obj)">
                <span class="obj-type-chip" :class="'obj-'+key">{{ sec.chip }}</span>
                <span class="tree-name">{{ obj.name }}</span>
              </div>
            </template>
          </template>
        </template>
      </div>

      <!-- 우측 상세 -->
      <div class="detail-area">
        <!-- 아무것도 선택 안 했을 때 -->
        <div v-if="!selTable && !selObj" class="card empty-detail">
          <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1"
               style="width:40px;height:40px;opacity:.2">
            <rect x="4" y="8" width="40" height="32" rx="3"/>
            <line x1="4" y1="16" x2="44" y2="16"/>
            <line x1="16" y1="8" x2="16" y2="40"/>
          </svg>
          <p>왼쪽 트리에서 테이블 또는 오브젝트를 선택하세요</p>
        </div>

        <!-- 테이블 상세 -->
        <template v-if="selTable">
          <div class="card" style="padding:0;overflow:hidden">
            <!-- 탭 바 -->
            <div class="tab-bar">
              <button v-for="tab in tableTabs" :key="tab.v"
                      class="tab-btn" :class="{active:activeTab===tab.v}"
                      @click="activeTab=tab.v">{{ tab.l }}</button>
              <span style="margin-left:auto;padding:0 14px;font-size:11.5px;color:var(--text-tertiary);display:flex;align-items:center;gap:6px">
                <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3" style="width:11px;height:11px;opacity:.5">
                  <rect x="1" y="2" width="12" height="10" rx="1"/><line x1="1" y1="5" x2="13" y2="5"/>
                </svg>
                {{ selTable }}
                <span v-if="tableInfo.row_count !== undefined" style="color:var(--text-tertiary)">
                  · {{ fmtRows(tableInfo.row_count) }} rows
                </span>
                <span style="color:var(--text-tertiary)">· {{ selCols.length }}개 컬럼</span>
              </span>
            </div>

            <!-- 컬럼 탭 -->
            <div v-if="activeTab==='cols'">
              <div v-if="loadingCols" class="empty-state" style="padding:24px">
                <span class="spinner" style="width:16px;height:16px;display:inline-block"></span>
              </div>
              <table v-else class="col-tbl">
                <thead>
                  <tr>
                    <th>#</th><th>컬럼명</th><th>데이터 타입</th><th>Null</th><th>기본값</th>
                    <th>PK</th><th>AUTO</th><th>크기</th><th>비고</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(c, i) in selCols" :key="c.name||c.COLUMN_NAME">
                    <td style="color:var(--text-tertiary);font-size:10.5px">{{ i+1 }}</td>
                    <td style="font-family:'Consolas','SF Mono',monospace;font-weight:500">
                      {{ c.name || c.COLUMN_NAME }}
                    </td>
                    <td>
                      <span class="type-chip" :class="typeClass(c.data_type||c.DATA_TYPE)">
                        {{ c.data_type || c.DATA_TYPE }}
                      </span>
                    </td>
                    <td>
                      <span :style="{color:(c.nullable||c.IS_NULLABLE==='YES')?'var(--text-tertiary)':'var(--text-danger)'}">
                        {{ (c.nullable||c.IS_NULLABLE==='YES') ? 'YES' : 'NO' }}
                      </span>
                    </td>
                    <td style="font-size:11px;color:var(--text-tertiary);font-family:'Consolas','SF Mono',monospace">
                      {{ c.default || c.COLUMN_DEFAULT || '—' }}
                    </td>
                    <td style="text-align:center">
                      <span v-if="c.is_pk || c.COLUMN_KEY==='PRI'" style="font-size:13px">🔑</span>
                    </td>
                    <td style="text-align:center">
                      <span v-if="c.is_identity || (c.EXTRA||'').includes('auto_increment')"
                            style="color:var(--text-info);font-size:11px;font-weight:600">AI</span>
                    </td>
                    <td style="font-size:11px;color:var(--text-tertiary)">
                      {{ c.CHARACTER_MAXIMUM_LENGTH ? c.CHARACTER_MAXIMUM_LENGTH : '' }}
                    </td>
                    <td style="font-size:11px;color:var(--text-tertiary)">{{ c.comment || '' }}</td>
                  </tr>
                  <tr v-if="!loadingCols && !selCols.length">
                    <td colspan="9" class="empty-state" style="padding:20px">컬럼 정보 없음</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- DDL 탭 -->
            <div v-if="activeTab==='ddl'" style="padding:14px">
              <div class="ddl-toolbar">
                <div class="sel-wrap" style="min-width:80px">
                  <select v-model="ddlTarget" style="font-size:11.5px;padding:4px 24px 4px 8px">
                    <option value="mysql">MySQL</option>
                    <option value="mssql">MSSQL</option>
                    <option value="postgresql">PostgreSQL</option>
                  </select>
                  <div class="chevron"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>
                </div>
                <button class="act-btn" @click="copyDdl">
                  <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px">
                    <rect x="4" y="1" width="9" height="11" rx="1.5"/>
                    <path d="M10 1v-1H1v11h3"/>
                  </svg>
                  복사
                </button>
                <button class="act-btn" @click="downloadDdl">다운로드</button>
              </div>
              <pre class="code-block" style="margin-top:10px;max-height:500px;overflow-y:auto">{{ generatedDdl }}</pre>
            </div>

            <!-- 인덱스 탭 -->
            <div v-if="activeTab==='idx'" style="padding:14px">
              <table class="col-tbl">
                <thead><tr><th>인덱스명</th><th>컬럼</th><th>유형</th><th>고유</th></tr></thead>
                <tbody>
                  <tr v-for="idx in derivedIndexes" :key="idx.name">
                    <td style="font-family:'Consolas','SF Mono',monospace">{{ idx.name }}</td>
                    <td>{{ idx.col }}</td>
                    <td><span class="type-chip num">{{ idx.type }}</span></td>
                    <td>{{ idx.unique ? '✓' : '' }}</td>
                  </tr>
                  <tr v-if="!derivedIndexes.length">
                    <td colspan="4" class="empty-state" style="padding:16px">인덱스 정보 없음</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- 미리보기 탭 -->
            <div v-if="activeTab==='preview'" style="padding:14px">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
                <span style="font-size:12px;color:var(--text-secondary)">상위 {{ previewRows.length }}행</span>
                <button class="act-btn" @click="loadPreview" :disabled="loadingPreview">
                  <span v-if="loadingPreview" class="spinner" style="width:10px;height:10px;display:inline-block;margin-right:3px"></span>
                  {{ loadingPreview ? '조회 중...' : '↻ 새로고침' }}
                </button>
              </div>
              <div v-if="loadingPreview" class="empty-state" style="padding:20px">
                <span class="spinner" style="width:16px;height:16px;display:inline-block"></span>
              </div>
              <div v-else-if="previewRows.length" class="preview-wrap">
                <table class="col-tbl preview-tbl">
                  <thead>
                    <tr>
                      <th v-for="col in previewCols" :key="col">{{ col }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(row, ri) in previewRows" :key="ri">
                      <td v-for="col in previewCols" :key="col" class="preview-cell">
                        {{ row[col] == null ? 'NULL' : String(row[col]).slice(0, 80) }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div v-else class="empty-state" style="padding:20px;font-size:12px">
                데이터가 없습니다
              </div>
            </div>
          </div>
        </template>

        <!-- 오브젝트 상세 (프로시저/함수/트리거/뷰) -->
        <template v-if="selObj">
          <div class="card" style="padding:0;overflow:hidden">
            <div class="tab-bar">
              <span style="padding:0 14px;font-size:12px;font-weight:500;display:flex;align-items:center;gap:6px">
                <span class="obj-type-chip" :class="'obj-'+selObj.type" style="font-size:11px">
                  {{ objSections[selObj.type]?.chip }}
                </span>
                {{ selObj.name }}
              </span>
              <button class="act-btn" style="margin-left:auto;margin-right:10px" @click="copyObjDdl">복사</button>
            </div>
            <div v-if="loadingObj" class="empty-state" style="padding:24px">
              <span class="spinner" style="width:16px;height:16px;display:inline-block"></span>
            </div>
            <pre v-else class="code-block" style="margin:14px;max-height:600px;overflow-y:auto">{{ objDdl || '// DDL을 불러오는 중...' }}</pre>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, watch } from 'vue'
import axios from 'axios'
import PageHeader   from '@/components/layout/PageHeader.vue'
import ConnectPanel from '@/components/common/ConnectPanel.vue'
import { useConnectorStore } from '@/store/connectorStore.js'
import { useAppStore }       from '@/store/appStore.js'
import { usePageStore }      from '@/store/pageStore.js'
import { DB_META }           from '@/constants/dbMeta.js'

const connector = useConnectorStore()
const app       = useAppStore()
const pStore    = usePageStore()

const selSide    = ref(pStore.schema.side    || 'source')
const tblSearch  = ref('')
const loadingTbl = ref(false)
const loadingCols= ref(false)
const loadingObj = ref(false)
const loadingPreview = ref(false)
const tableError = ref('')
const openTbls   = ref(true)
const activeTab  = ref(pStore.schema.activeTab || 'cols')
const ddlTarget  = ref('mysql')

const tables  = ref([])
const selTable= ref(pStore.schema.selTable || '')
watch(tables, v => pStore.saveSchema({ tables: v }), { deep: false })

const selCols = ref([])
const tableInfo = ref({})
const selObj  = ref(null)
const objDdl  = ref('')
const objects = ref({ procedures:[], functions:[], triggers:[], views:[] })
const previewRows = ref([])
const previewCols = ref([])

const objSections = reactive({
  procedures: { label:'프로시저', icon:'⚙', chip:'SP',   open: false },
  functions:  { label:'함수',     icon:'ƒ',  chip:'FN',   open: false },
  triggers:   { label:'트리거',   icon:'⚡', chip:'TRG',  open: false },
  views:      { label:'뷰',       icon:'👁', chip:'VIEW', open: false },
})

const tableTabs = [
  { v:'cols',    l:'컬럼 구조' },
  { v:'ddl',     l:'DDL 생성' },
  { v:'idx',     l:'인덱스' },
  { v:'preview', l:'데이터 미리보기' },
]

const m        = t => DB_META[t] || { label:'??', bg:'#eee', color:'#333' }
const fmtRows  = n => n>=1e6 ? (n/1e6).toFixed(1)+'M' : n>=1e3 ? Math.round(n/1e3)+'K' : String(n||0)
const curConn  = computed(() => connector[selSide.value])

const filteredTables = computed(() =>
  tables.value.filter(t => t.table_name.toLowerCase().includes(tblSearch.value.toLowerCase()))
)

function typeClass(t='') {
  const tl = t.toLowerCase()
  if (/int|bigint|smallint|tinyint|decimal|numeric|float|double|real|money/.test(tl)) return 'num'
  if (/char|text|nvarchar|varchar|clob/.test(tl)) return 'str'
  if (/date|time|timestamp|datetime/.test(tl)) return 'dt'
  if (/bit|bool/.test(tl)) return 'bool'
  if (/blob|binary|varbinary|image/.test(tl)) return 'bin'
  return 'other'
}

// DDL 생성 (클라이언트 사이드, 빠른 미리보기용)
const generatedDdl = computed(() => {
  if (!selCols.value.length) return ''
  const tgt = ddlTarget.value
  const name = selTable.value

  if (tgt === 'mssql') {
    const cols = selCols.value.map(c => {
      const cn   = c.name || c.COLUMN_NAME
      const dt   = c.data_type || c.DATA_TYPE || 'NVARCHAR'
      const null_= (c.nullable || c.IS_NULLABLE==='YES') ? 'NULL' : 'NOT NULL'
      const isAI = c.is_identity || (c.EXTRA||'').includes('auto_increment')
      if (isAI) return `  [${cn}] INT IDENTITY(1,1) NOT NULL`
      const mssqlType = {
        varchar:'NVARCHAR', char:'NCHAR', text:'NVARCHAR(MAX)',
        tinyint:'TINYINT', smallint:'SMALLINT', mediumint:'INT',
        bigint:'BIGINT', int:'INT', decimal:'DECIMAL', float:'FLOAT',
        datetime:'DATETIME2(6)', date:'DATE', timestamp:'DATETIME2(6)',
        bit:'BIT', bool:'BIT',
      }[dt.toLowerCase()] || dt.toUpperCase()
      const len = c.CHARACTER_MAXIMUM_LENGTH
      const finalType = (mssqlType === 'NVARCHAR' && len && len > 0 && len < 4001)
        ? `NVARCHAR(${len})` : mssqlType
      return `  [${cn}] ${finalType} ${null_}`
    })
    const pk = selCols.value.find(c => c.is_pk || c.COLUMN_KEY==='PRI')
    if (pk) cols.push(`  CONSTRAINT [PK_${name}] PRIMARY KEY ([${pk.name||pk.COLUMN_NAME}])`)
    return `IF OBJECT_ID(N'[dbo].[${name}]', N'U') IS NULL\nCREATE TABLE [dbo].[${name}] (\n${cols.join(',\n')}\n)`
  }

  if (tgt === 'postgresql') {
    const cols = selCols.value.map(c => {
      const cn   = c.name || c.COLUMN_NAME
      const dt   = c.data_type || c.DATA_TYPE || 'TEXT'
      const null_= (c.nullable || c.IS_NULLABLE==='YES') ? '' : ' NOT NULL'
      const isAI = c.is_identity || (c.EXTRA||'').includes('auto_increment')
      if (isAI) return `  "${cn}" SERIAL NOT NULL`
      const pgType = { varchar:'VARCHAR', char:'CHAR', text:'TEXT', int:'INTEGER',
        bigint:'BIGINT', smallint:'SMALLINT', decimal:'NUMERIC', float:'REAL',
        datetime:'TIMESTAMP', date:'DATE', timestamp:'TIMESTAMP', bit:'BOOLEAN',
        tinyint:'SMALLINT',
      }[dt.toLowerCase()] || dt.toUpperCase()
      const len = c.CHARACTER_MAXIMUM_LENGTH
      const finalType = (pgType==='VARCHAR' && len && len>0) ? `VARCHAR(${len})` : pgType
      return `  "${cn}" ${finalType}${null_}`
    })
    const pk = selCols.value.find(c => c.is_pk || c.COLUMN_KEY==='PRI')
    const pkLine = pk ? `,\n  PRIMARY KEY ("${pk.name||pk.COLUMN_NAME}")` : ''
    return `CREATE TABLE IF NOT EXISTS "${name}" (\n${cols.join(',\n')}${pkLine}\n);`
  }

  // MySQL (default)
  const cols = selCols.value.map(c => {
    const cn   = c.name || c.COLUMN_NAME
    const dt   = c.data_type || c.DATA_TYPE || 'VARCHAR'
    const null_= (c.nullable || c.IS_NULLABLE==='YES') ? 'NULL' : 'NOT NULL'
    const isAI = c.is_identity || (c.EXTRA||'').includes('auto_increment')
    if (isAI) return `  \`${cn}\` INT NOT NULL AUTO_INCREMENT`
    const len = c.CHARACTER_MAXIMUM_LENGTH
    let finalType = dt.toUpperCase()
    if (/varchar/i.test(dt) && len && len > 0) finalType = `VARCHAR(${Math.min(len, 16383)})`
    else if (/char/i.test(dt) && len && len > 0) finalType = `CHAR(${Math.min(len, 255)})`
    return `  \`${cn}\` ${finalType} ${null_}`
  })
  const pk = selCols.value.find(c => c.is_pk || c.COLUMN_KEY==='PRI')
  if (pk) cols.push(`  PRIMARY KEY (\`${pk.name||pk.COLUMN_NAME}\`)`)
  return `CREATE TABLE IF NOT EXISTS \`${name}\` (\n${cols.join(',\n')}\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;`
})

const derivedIndexes = computed(() => {
  if (!selCols.value.length) return []
  const list = []
  const pk = selCols.value.find(c => c.is_pk || c.COLUMN_KEY==='PRI')
  if (pk) list.push({ name:'PRIMARY', col: pk.name||pk.COLUMN_NAME, type:'BTREE', unique:true })
  selCols.value.filter(c => !c.is_pk && c.COLUMN_KEY==='MUL').forEach(c => {
    list.push({ name:`idx_${selTable.value}_${c.name||c.COLUMN_NAME}`, col: c.name||c.COLUMN_NAME, type:'BTREE', unique:false })
  })
  return list
})

function getConnParams() {
  const c = curConn.value
  return {
    side:     selSide.value,
    db_type:  c.dbType,
    host:     c.host,
    port:     c.port,
    username: c.username,
    password: c.password,
    database: c.database,
  }
}

async function loadAll() {
  const c = curConn.value
  if (!c.host || !c.database) {
    tableError.value = `${selSide.value === 'source' ? '소스' : '타겟'} DB 연결 정보가 없습니다. 커넥터 관리에서 연결 테스트를 먼저 하세요.`
    return
  }
  loadingTbl.value = true
  tableError.value = ''
  tables.value  = []
  objects.value = { procedures:[], functions:[], triggers:[], views:[] }
  selTable.value = ''
  selObj.value   = null

  const params = getConnParams()
  try {
    const { data } = await axios.get('/api/v1/schema/tables', { params })
    tables.value = data
    if (!data.length) tableError.value = `"${c.database}"에 테이블이 없습니다`
  } catch (e) {
    tableError.value = e.response?.data?.detail || e.message
  } finally { loadingTbl.value = false }

  // 오브젝트 조회 (실패해도 무시)
  try {
    const { data } = await axios.get('/api/v1/schema/objects', { params })
    objects.value = data
  } catch { /* 무시 */ }
}

async function selectTable(name) {
  selTable.value = name
  selObj.value   = null
  activeTab.value = 'cols'
  tableInfo.value = tables.value.find(t => t.table_name === name) || {}
  previewRows.value = []
  loadingCols.value = true
  selCols.value = []
  try {
    const c = curConn.value
    const params = {
      db_type:  c.dbType, host: c.host, port: c.port,
      username: c.username, password: c.password, database: c.database,
    }
    const { data } = await axios.get(`/api/v1/schema/${selSide.value}/tables/${name}`, { params })
    selCols.value = data.columns || []
  } catch (e) {
    app.notify('컬럼 조회 실패: ' + (e.response?.data?.detail || e.message), 'error')
  } finally { loadingCols.value = false }
}

async function selectObj(type, obj) {
  selObj.value = { type, ...obj }
  selTable.value = ''
  objDdl.value   = ''
  loadingObj.value = true
  try {
    const c = curConn.value
    const { data } = await axios.post('/api/v1/schema/convert-object', {
      obj_type:    type.replace(/s$/,'').toUpperCase(),
      obj_name:    obj.name,
      src_db_type: c.dbType,
      tgt_db_type: c.dbType,    // 현재 DB 타입 그대로 조회 (변환 없이 DDL만)
      conn_info: { db_type:c.dbType, host:c.host, port:c.port, username:c.username, password:c.password, database:c.database },
    })
    objDdl.value = data.original_ddl || data.converted_ddl || '// DDL 없음'
  } catch (e) {
    objDdl.value = `// 오브젝트 DDL 조회 실패\n// ${e.response?.data?.detail || e.message}`
  } finally { loadingObj.value = false }
}

async function loadPreview() {
  if (!selTable.value) return
  loadingPreview.value = true
  previewRows.value = []
  previewCols.value = []
  try {
    const c = curConn.value
    const { data } = await axios.get(`/api/v1/schema/${selSide.value}/tables/${selTable.value}/preview`, {
      params: { db_type:c.dbType, host:c.host, port:c.port, username:c.username, password:c.password, database:c.database, limit:20 }
    })
    previewRows.value = data.rows || []
    previewCols.value = data.columns || (previewRows.value.length ? Object.keys(previewRows.value[0]) : [])
  } catch (e) {
    app.notify('미리보기 조회 실패: ' + (e.response?.data?.detail || e.message), 'error')
  } finally { loadingPreview.value = false }
}

// 상태 변경 시 pageStore에 저장
watch(selSide,   v => pStore.saveSchema({ side: v }))
watch(selTable,  v => pStore.saveSchema({ selTable: v }))
watch(activeTab, v => pStore.saveSchema({ activeTab: v }))

watch(activeTab, (tab) => {
  if (tab === 'preview' && !previewRows.value.length) loadPreview()
})

function switchSide(side) {
  selSide.value  = side
  selTable.value = ''
  selObj.value   = null
  selCols.value  = []
  tables.value   = []
  tableError.value = ''
  objects.value  = { procedures:[], functions:[], triggers:[], views:[] }
  if (curConn.value.status === 'ok') loadAll()
}

function copyDdl() {
  navigator.clipboard?.writeText(generatedDdl.value)
  app.notify('DDL이 클립보드에 복사됐습니다', 'success')
}

function downloadDdl() {
  const blob = new Blob([generatedDdl.value], { type:'text/plain' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `${selTable.value}_${ddlTarget.value}.sql`
  a.click()
}

function copyObjDdl() {
  navigator.clipboard?.writeText(objDdl.value)
  app.notify('DDL이 클립보드에 복사됐습니다', 'success')
}

onMounted(async () => {
  if (pStore.schema.tables) {
    // 저장된 테이블 목록 복원
    tables.value = pStore.schema.tables
    // 선택된 테이블 복원
    if (pStore.schema.selTable && tables.value.length) {
      await selectTable(pStore.schema.selTable)
    }
  } else if (curConn.value.status === 'ok') {
    loadAll()
  }
})
</script>

<style scoped>
.schema-page { display:flex; flex-direction:column; gap:0; }

/* 연결 선택 바 */
/* 소스/타겟 탭 */
.sc-side-tabs { display:flex; border:0.5px solid var(--border-mid); border-radius:6px; overflow:hidden; }
.sc-side-tab  { padding:3px 12px; font-size:.75rem; font-weight:600; font-family:var(--font); background:transparent; border:none; cursor:pointer; color:var(--text-tertiary); transition:all .12s; }
.sc-side-tab.on { background:var(--accent-blue); color:#fff; }
.sc-search { padding:4px 10px; border:0.5px solid var(--border-mid); border-radius:6px; font-size:.75rem; font-family:var(--font); background:var(--bg-primary); color:var(--text-primary); outline:none; width:140px; }
.sc-search:focus { border-color:var(--accent-blue); }
.conn-bar {
  display:flex; align-items:center; gap:0;
  padding:0; overflow:hidden; margin-bottom:10px;
}
.conn-side {
  display:flex; align-items:center; gap:10px; flex:1;
  padding:12px 16px; cursor:pointer; transition:background .12s;
  border-right:0.5px solid var(--border-light);
}
.conn-side:last-child { border-right:none; }
.conn-side:hover { background:var(--bg-secondary); }
.conn-side.active { background:var(--bg-info); }
.side-ico {
  width:32px; height:32px; border-radius:8px; flex-shrink:0;
  display:flex; align-items:center; justify-content:center;
  font-size:10px; font-weight:700;
}
.side-label { font-size:12px; font-weight:500; color:var(--text-primary); }
.side-sub   { font-size:10.5px; color:var(--text-tertiary); margin-top:2px; }
.conn-pill  { font-size:10px; font-weight:600; padding:2px 8px; border-radius:10px; flex-shrink:0; margin-left:auto; }
.conn-pill.ok  { background:var(--bg-success); color:var(--text-success); }
.conn-pill.err { background:var(--bg-danger); color:var(--text-danger); }
.side-divider  { font-size:16px; color:var(--text-tertiary); padding:0 10px; flex-shrink:0; }

/* 레이아웃 */
.schema-layout { display:grid; grid-template-columns:240px 1fr; gap:10px; align-items:start; }

/* 트리 패널 */
.tree-panel { padding:0; overflow:hidden; max-height:calc(100vh - 320px); overflow-y:auto; }
.tree-header {
  display:flex; align-items:center; justify-content:space-between;
  padding:10px 12px; border-bottom:0.5px solid var(--border-light);
}
.tbl-count { font-size:10px; padding:2px 7px; border-radius:8px; background:var(--bg-secondary); color:var(--text-tertiary); }
.tree-error { padding:12px; font-size:11.5px; color:var(--text-danger); }
.tree-sec {
  display:flex; align-items:center; gap:6px; padding:7px 12px;
  font-size:11.5px; font-weight:500; color:var(--text-secondary);
  cursor:pointer; user-select:none; border-bottom:0.5px solid var(--border-light);
  transition:background .1s;
}
.tree-sec:hover { background:var(--bg-secondary); }
.sec-cnt { margin-left:auto; font-size:10px; color:var(--text-tertiary); background:var(--bg-secondary); padding:1px 6px; border-radius:8px; }
.tree-item {
  display:flex; align-items:center; gap:6px;
  padding:5px 12px 5px 22px; font-size:11.5px;
  color:var(--text-secondary); cursor:pointer; transition:all .1s;
}
.tree-item:hover { background:var(--bg-secondary); color:var(--text-primary); }
.tree-item.sel { background:var(--bg-info); color:var(--text-info); }
.tree-item.obj-item { padding-left:16px; }
.tree-name { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.tree-rows { margin-left:auto; font-size:10px; color:var(--text-tertiary); flex-shrink:0; }

/* 오브젝트 타입 칩 */
.obj-type-chip { display:inline-flex; align-items:center; justify-content:center; width:32px; height:16px; border-radius:3px; font-size:9px; font-weight:700; flex-shrink:0; letter-spacing:.3px; }
.obj-procedures { background:#e6f1fb; color:#185fa5; }
.obj-functions  { background:#eaf3de; color:#3b6d11; }
.obj-triggers   { background:#faeeda; color:#854f0b; }
.obj-views      { background:#f1f0f9; color:#534ab7; }

/* 상세 영역 */
.empty-detail { display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:300px; color:var(--text-tertiary); gap:12px; }
.empty-detail p { font-size:12.5px; }

/* 탭 */
.tab-bar { display:flex; border-bottom:0.5px solid var(--border-light); background:var(--bg-secondary); }
.tab-btn { padding:9px 14px; font-size:12px; border:none; background:transparent; cursor:pointer; color:var(--text-secondary); font-family:var(--font); border-bottom:2px solid transparent; transition:all .12s; }
.tab-btn:hover { color:var(--text-primary); }
.tab-btn.active { color:var(--text-info); border-bottom-color:var(--accent-blue); font-weight:500; }

/* 컬럼 테이블 */
.col-tbl { width:100%; border-collapse:collapse; }
.col-tbl th { background:var(--bg-secondary); font-size:10.5px; font-weight:500; color:var(--text-tertiary); padding:7px 10px; text-align:left; border-bottom:0.5px solid var(--border-light); white-space:nowrap; }
.col-tbl td { padding:7px 10px; font-size:12px; border-bottom:0.5px solid var(--border-light); color:var(--text-primary); }
.col-tbl tr:last-child td { border-bottom:none; }
.col-tbl tr:hover td { background:var(--bg-secondary); }

/* 타입 칩 */
.type-chip { display:inline-block; font-size:10.5px; padding:2px 6px; border-radius:4px; font-family:'Consolas','SF Mono',monospace; font-weight:500; }
.type-chip.num   { background:#e6f1fb; color:#185fa5; }
.type-chip.str   { background:#eaf3de; color:#3b6d11; }
.type-chip.dt    { background:#faeeda; color:#854f0b; }
.type-chip.bool  { background:#fcebeb; color:#a32d2d; }
.type-chip.bin   { background:#f1f0f9; color:#534ab7; }
.type-chip.other { background:var(--bg-secondary); color:var(--text-tertiary); }

/* DDL 툴바 */
.ddl-toolbar { display:flex; gap:6px; align-items:center; margin-bottom:2px; }

/* 미리보기 */
.preview-wrap { overflow-x:auto; max-height:480px; overflow-y:auto; border:0.5px solid var(--border-light); border-radius:var(--radius-md); }
.preview-tbl { min-width:max-content; }
.preview-cell { font-family:'Consolas','SF Mono',monospace; font-size:11.5px; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--text-secondary); }

/* code-block override */
.code-block { font-size:12px; line-height:1.6; }
</style>
