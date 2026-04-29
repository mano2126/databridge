<template>
  <div>
    <div class="page-title">오브젝트 탐색기</div>
    <div class="page-desc">Function, Procedure, Trigger, View 등 오브젝트를 탐색하고 테스트합니다</div>

    <!-- DB 선택 바 -->
    <div class="card cfg-bar">
      <div style="display:flex;align-items:center;gap:8px">
        <span class="cfg-lbl">DB 선택</span>
        <div class="sel-wrap" style="min-width:160px">
          <select v-model="selSide" @change="loadObjects">
            <option value="source">소스 — {{ conn.source.dbType||'DB' }} / {{ conn.source.database||'미연결' }}</option>
            <option value="target">타겟 — {{ conn.target.dbType||'DB' }} / {{ conn.target.database||'미연결' }}</option>
          </select>
          <div class="chev"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>
        </div>
        <!-- DB 종류 배지 -->
        <span class="db-type-badge">{{ (curConn.dbType||'').toUpperCase() }}</span>
        <span class="pill" :class="curConn.status==='ok'?'pill-ok':'pill-err'">{{ curConn.status==='ok'?'연결됨':'미연결' }}</span>
      </div>
      <div style="margin-left:auto;display:flex;gap:6px">
        <button class="btn" @click="loadObjects" :disabled="loading">
          <span v-if="loading" class="spinner" style="width:12px;height:12px;display:inline-block"></span>
          {{ loading?'조회 중...':'↻ 새로고침' }}
        </button>
      </div>
    </div>

    <div class="explorer-layout">
      <!-- 좌측 트리 -->
      <div class="card tree-panel">
        <div v-if="loading" class="empty-state" style="padding:20px">
          <span class="spinner" style="width:18px;height:18px;display:inline-block"></span>
        </div>
        <div v-else-if="!curConn.host" class="empty-state" style="padding:20px;font-size:12px">
          커넥터 관리에서 연결 테스트를 먼저 하세요
        </div>
        <template v-else>
          <!-- 오브젝트 카테고리 트리 -->
          <div v-for="cat in categories" :key="cat.key" class="tree-cat">
            <div class="tree-cat-header" @click="cat.open=!cat.open">
              <svg :style="{transform:cat.open?'rotate(90deg)':'',transition:'transform .2s'}"
                viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"
                style="width:10px;height:10px;flex-shrink:0">
                <polyline points="3,2 9,6 3,10"/>
              </svg>
              <span class="cat-icon">{{ cat.icon }}</span>
              <span class="cat-name">{{ cat.label }}</span>
              <span class="cat-cnt">{{ objects[cat.key]?.length||0 }}</span>
            </div>
            <template v-if="cat.open">
              <div v-if="!objects[cat.key]?.length" class="tree-empty">없음</div>
              <div v-for="obj in objects[cat.key]" :key="obj.name"
                class="tree-item" :class="{sel:selObj?.name===obj.name&&selObjType===cat.key}"
                @click="selectObject(cat.key, obj)">
                <span class="obj-name">{{ obj.name }}</span>
                <span v-if="obj.return_type" class="obj-meta">{{ obj.return_type }}</span>
                <span v-if="obj.event" class="obj-meta">{{ obj.timing }} {{ obj.event }}</span>
              </div>
            </template>
          </div>
        </template>
      </div>

      <!-- 우측 상세 -->
      <div class="detail-area" v-if="selObj">
        <!-- 탭 바 -->
        <div class="card" style="padding:0;overflow:hidden;margin-bottom:10px">
          <div class="tab-bar">
            <button v-for="t in detailTabs" :key="t.v"
              class="tab-btn" :class="{active:activeTab===t.v}"
              @click="activeTab=t.v">
              {{ t.l }}
            </button>
            <div class="tab-info">{{ selObjType }} · {{ selObj.name }}</div>
          </div>

          <!-- DDL 탭 -->
          <div v-if="activeTab==='ddl'" class="ddl-area">
            <div class="ddl-toolbar">
              <button class="mini-btn" @click="loadDDL" :disabled="loadingDDL">
                <span v-if="loadingDDL" class="spinner" style="width:11px;height:11px;display:inline-block"></span>
                {{ loadingDDL?'조회 중...':'DDL 로드' }}
              </button>
              <button class="mini-btn" @click="copyDDL" :disabled="!sourceDDL">📋 복사</button>
              <button class="mini-btn" @click="convertDDL" :disabled="!sourceDDL||converting">
                <span v-if="converting" class="spinner" style="width:11px;height:11px;display:inline-block"></span>
                {{ converting?'변환 중...':'→ 타겟 DB로 변환' }}
              </button>
              <button v-if="convertedDDL" class="mini-btn deploy" @click="deployToTarget" :disabled="deployLoading">
                <span v-if="deployLoading" class="spinner" style="width:11px;height:11px;display:inline-block"></span>
                🚀 {{ deployLoading?'생성 중...':'타겟에 생성' }}
              </button>
              <span v-if="deployResult" class="deploy-badge" :class="deployResult.ok?'ok':'err'">
                {{ deployResult.ok?'✓ 생성 완료':'✗ 실패' }}
              </span>
            </div>

            <div class="ddl-split">
              <div class="ddl-side">
                <div class="ddl-label src">소스 DDL ({{ curConn.dbType }})</div>
                <pre class="ddl-code">{{ sourceDDL||'DDL 로드 버튼을 클릭하세요' }}</pre>
              </div>
              <div class="ddl-side" v-if="convertedDDL">
                <div class="ddl-label tgt">변환 결과 ({{ otherConn.dbType }})</div>
                <pre class="ddl-code tgt">{{ convertedDDL }}</pre>
                <div v-if="convChanges.length||convWarnings.length" class="conv-summary">
                  <div v-for="c in convChanges" :key="c" class="cv-item ok">✓ {{ c }}</div>
                  <div v-for="w in convWarnings" :key="w" class="cv-item warn">⚠ {{ w }}</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 테스트 탭 -->
          <div v-if="activeTab==='test'" class="test-area">
            <div v-if="!['function','procedure','view'].includes(selObjType)" class="empty-state" style="padding:20px">
              {{ selObjType }}은 테스트 실행을 지원하지 않습니다
            </div>
            <template v-else>
              <!-- 파라미터 입력 (function/procedure) -->
              <div v-if="['function','procedure'].includes(selObjType)" class="param-section">
                <div class="param-header">
                  <span>입력 파라미터</span>
                  <button class="mini-btn" @click="addParam">+ 파라미터 추가</button>
                </div>
                <div v-if="!testParams.length" class="empty-state" style="padding:12px;font-size:11.5px">
                  파라미터가 없으면 빈 채로 실행하거나, 위 버튼으로 추가하세요
                </div>
                <div v-for="(p,i) in testParams" :key="i" class="param-row">
                  <input type="text" v-model="p.name" placeholder="파라미터명" style="flex:1"/>
                  <div class="sel-wrap" style="min-width:100px">
                    <select v-model="p.type" style="font-size:12px;padding:5px 24px 5px 8px">
                      <option>VARCHAR</option><option>INT</option><option>DECIMAL</option>
                      <option>DATETIME</option><option>BOOLEAN</option><option>TEXT</option>
                    </select>
                    <div class="chev"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>
                  </div>
                  <input type="text" v-model="p.value" placeholder="테스트 값" style="flex:2"/>
                  <button class="mini-btn del" @click="testParams.splice(i,1)">✕</button>
                </div>
              </div>

              <!-- 실행 버튼 -->
              <div class="test-run-bar">
                <button class="btn btn-primary" @click="runTest" :disabled="testRunning">
                  <span v-if="testRunning" class="spinner" style="width:13px;height:13px;border-top-color:#fff"></span>
                  <svg v-else viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px">
                    <polygon points="4,2 14,8 4,14" fill="currentColor" stroke="none"/>
                  </svg>
                  {{ testRunning?'실행 중...':'▶ 테스트 실행' }}
                </button>
                <span v-if="testResult" class="test-elapsed">{{ testResult.elapsed_ms }}ms</span>
                <span v-if="testResult" class="pill" :class="testResult.success?'pill-ok':'pill-err'">
                  {{ testResult.success?'성공':'실패' }}
                </span>
              </div>

              <!-- 실행 결과 -->
              <div v-if="testResult" class="test-result">
                <div class="tr-header">
                  <span>실행된 SQL</span>
                </div>
                <pre class="ddl-code" style="font-size:11.5px;padding:8px 12px">{{ testResult.sql }}</pre>

                <div class="tr-header" style="margin-top:8px">
                  결과 <span v-if="testResult.row_count!==undefined">({{ testResult.row_count }}건)</span>
                </div>

                <div v-if="testResult.success">
                  <!-- 단일 값 (function) -->
                  <div v-if="testResult.result && !Array.isArray(testResult.result)" class="func-result">
                    <span class="fr-label">반환값</span>
                    <span class="fr-val">{{ JSON.stringify(Object.values(testResult.result)[0]) }}</span>
                  </div>

                  <!-- 테이블 결과 (procedure/view) -->
                  <div v-else-if="Array.isArray(testResult.result)&&testResult.result.length" class="result-table-wrap">
                    <table class="result-tbl">
                      <thead>
                        <tr>
                          <th v-for="col in Object.keys(testResult.result[0])" :key="col">{{ col }}</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="(row,ri) in testResult.result.slice(0,20)" :key="ri">
                          <td v-for="(val,col) in row" :key="col">{{ val }}</td>
                        </tr>
                      </tbody>
                    </table>
                    <div v-if="testResult.result.length>20" style="font-size:11px;color:var(--text-tertiary);padding:6px">
                      최대 20건만 표시 (전체 {{ testResult.result.length }}건)
                    </div>
                  </div>

                  <div v-else class="empty-state" style="padding:12px;font-size:11.5px">결과 없음</div>
                </div>

                <div v-else class="err-banner" style="margin-top:6px">
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px;flex-shrink:0"><circle cx="8" cy="8" r="7"/><line x1="5" y1="5" x2="11" y2="11"/><line x1="11" y1="5" x2="5" y2="11"/></svg>
                  {{ testResult.error }}
                </div>
              </div>
            </template>
          </div>

          <!-- 정보 탭 -->
          <div v-if="activeTab==='info'" class="info-area">
            <table class="info-tbl">
              <tr v-for="(v,k) in selObjInfo" :key="k">
                <th>{{ k }}</th>
                <td>{{ v }}</td>
              </tr>
            </table>
          </div>
        </div>
      </div>

      <div v-else class="card empty-state" style="min-height:300px;display:flex;align-items:center;justify-content:center">
        왼쪽에서 오브젝트를 선택하세요
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { useConnectorStore } from '@/store/connectorStore.js'
import { useAppStore }       from '@/store/appStore.js'

const conn = useConnectorStore()
const app  = useAppStore()

const selSide   = ref('source')
const loading   = ref(false)
const loadingDDL= ref(false)
const converting= ref(false)
const testRunning=ref(false)

const objects    = ref({functions:[],procedures:[],triggers:[],views:[],events:[]})
const selObj     = ref(null)
const selObjType = ref('')
const sourceDDL  = ref('')
const convertedDDL=ref('')
const convChanges = ref([])
const convWarnings= ref([])
const testParams  = ref([])
const testResult  = ref(null)
const activeTab   = ref('ddl')

const curConn  = computed(() => conn[selSide.value])
const otherConn= computed(() => conn[selSide.value==='source'?'target':'source'])

const categories = ref([
  {key:'functions',  label:'Functions',   icon:'⚡', open:true},
  {key:'procedures', label:'Procedures',  icon:'⚙', open:true},
  {key:'triggers',   label:'Triggers',    icon:'🔔', open:false},
  {key:'views',      label:'Views',       icon:'👁', open:false},
  {key:'events',     label:'Events',      icon:'📅', open:false},
])

const detailTabs = [
  {v:'ddl',  l:'DDL / 변환'},
  {v:'test', l:'테스트 실행'},
  {v:'info', l:'상세 정보'},
]

const selObjInfo = computed(() => {
  if (!selObj.value) return {}
  const o = selObj.value
  return Object.fromEntries(
    Object.entries(o).filter(([k,v]) => v && k !== 'definition')
  )
})

async function loadObjects() {
  const c = curConn.value
  if (!c.host || !c.database) return
  loading.value = true
  try {
    const { data } = await axios.get('/api/v1/schema/objects', {
      params: {
        side: selSide.value, db_type: c.dbType, host: c.host,
        port: c.port, username: c.username, password: c.password, database: c.database
      }
    })
    objects.value = data
  } catch(e) {
    app.notify('오브젝트 조회 실패: '+e.message, 'error')
  } finally { loading.value = false }
}

function selectObject(type, obj) {
  selObjType.value = type.slice(0,-1)  // functions → function
  selObj.value     = obj
  sourceDDL.value  = ''
  convertedDDL.value = ''
  convChanges.value  = []
  convWarnings.value = []
  testResult.value   = null
  testParams.value   = []
  activeTab.value    = 'ddl'
}

async function loadDDL() {
  const c = curConn.value
  loadingDDL.value = true
  try {
    const { data } = await axios.get('/api/v1/schema/objects/ddl', {
      params: {
        db_type:c.dbType, host:c.host, port:c.port,
        username:c.username, password:c.password, database:c.database,
        obj_type: selObjType.value, obj_name: selObj.value.name
      }
    })
    sourceDDL.value = data.ddl || '(DDL 없음)'
  } catch(e) {
    app.notify('DDL 조회 실패: '+e.message, 'error')
  } finally { loadingDDL.value = false }
}

async function convertDDL() {
  if (!sourceDDL.value) return
  converting.value = true
  try {
    const { data } = await axios.post('/api/v1/schema/objects/convert', {
      src_db:   curConn.value.dbType,
      tgt_db:   otherConn.value.dbType,
      obj_type: selObjType.value,
      obj_name: selObj.value.name,
      ddl:      sourceDDL.value,
    })
    convertedDDL.value  = data.converted_ddl
    convChanges.value   = data.changes
    convWarnings.value  = data.warnings
    app.notify(`변환 완료 — ${data.changes.length}건 변경`, 'success')
  } catch(e) {
    app.notify('변환 실패: '+e.message, 'error')
  } finally { converting.value = false }
}

function copyDDL() {
  navigator.clipboard?.writeText(sourceDDL.value)
  app.notify('DDL이 클립보드에 복사됐습니다', 'success')
}

async function aiConvertDDL(mysqlDdl, objType, objName, srcDb) {
  try {
    const {data} = await axios.post('/api/v1/schema/ai-convert-ddl', {
      ddl: mysqlDdl, obj_type: objType, obj_name: objName, src_db: srcDb,
      tgt_db_type: otherConn.value?.dbType || 'mssql', tgt_tables: [],
    })
    if (data.error) return { statements: [], error: data.error, notes: '' }
    return data
  } catch(e) {
    const errMsg = e.response?.data?.detail || e.message
    axios.post('/api/v1/settings/frontend-log', {
      level:'ERROR', page:'ObjectExplorer',
      message:`AI DDL 오류 [${objName}]: ${errMsg}`
    }).catch(()=>{})
    return { statements: [], error: errMsg, notes: '' }
  }
}


async function deployToTarget() {
  if (!sourceDDL.value) { app.notify('먼저 DDL을 로드하세요','warn'); return }
  deployLoading.value = true; deployResult.value = null
  const tgt = otherConn.value
  try {
    // STEP1: 브라우저에서 Anthropic API로 AI 변환
    app.notify(`${selObj.value.name} AI 변환 중...`, 'info')
    const aiResult = await aiConvertDDL(
      sourceDDL.value, selObjType.value, selObj.value.name,
      curConn.value.database
    )
    if (!aiResult.statements?.length) {
      deployResult.value = { ok:false, message:'AI 변환 실패: '+(aiResult.error||'결과 없음') }
      app.notify(deployResult.value.message, 'error')
      deployLoading.value = false; return
    }
    // STEP2: 백엔드에 statements 전달하여 MSSQL 실행
    const { data } = await axios.post('/api/v1/schema/execute-object', {
      db_type:      tgt.dbType,
      host:         tgt.host,
      port:         tgt.port,
      username:     tgt.username,
      password:     tgt.password,
      database:     tgt.database,
      obj_type:     'DDL_CREATE',
      obj_sub_type: selObjType.value,
      obj_name:     selObj.value.name,
      statements:   aiResult.statements,
      notes:        aiResult.notes,
      ddl:          sourceDDL.value,
      params:       [],
    })
    const notes = data.notes || data.output || ''
    deployResult.value = {
      ok: data.success,
      message: data.success
        ? `생성 완료${notes ? ' · '+notes.slice(0,40) : ''}`
        : (data.error || '실패')
    }
    if (data.warnings?.length) {
      data.warnings.forEach(w => app.notify('⚠ '+w.slice(0,60), 'warn'))
    }
    app.notify(data.success ? `${selObj.value.name} 타겟에 생성 완료!` : '생성 실패: '+data.error,
               data.success ? 'success' : 'error')
  } catch(e) {
    deployResult.value = { ok: false, message: e.response?.data?.detail || e.message }
    app.notify('생성 실패: '+deployResult.value.message, 'error')
  } finally { deployLoading.value = false }
}

function addParam() {
  testParams.value.push({ name:'p'+(testParams.value.length+1), type:'VARCHAR', value:'' })
}

async function runTest() {
  const c = curConn.value
  testRunning.value = true
  testResult.value  = null
  try {
    const { data } = await axios.post('/api/v1/schema/objects/test', {
      db_type:  c.dbType, host: c.host, port: c.port,
      username: c.username, password: c.password, database: c.database,
      obj_type: selObjType.value,
      obj_name: selObj.value.name,
      params:   testParams.value,
    })
    testResult.value = data
    app.notify(data.success ? `테스트 성공 (${data.elapsed_ms}ms)` : '테스트 실패', data.success?'success':'error')
  } catch(e) {
    testResult.value = { success:false, error:e.response?.data?.detail||e.message, elapsed_ms:0, sql:'' }
    app.notify('테스트 실패: '+e.message, 'error')
  } finally { testRunning.value = false }
}

onMounted(() => { if(conn.source.status==='ok') loadObjects() })
</script>

<style scoped>
.cfg-bar{display:flex;align-items:center;gap:10px;padding:12px 16px;margin-bottom:10px;flex-wrap:wrap}
.cfg-lbl{font-size:11.5px;color:var(--text-secondary);white-space:nowrap}
.db-type-badge{font-size:11px;font-weight:700;padding:3px 9px;border-radius:var(--radius-sm);background:var(--bg-info);color:var(--text-info);letter-spacing:.04em;border:0.5px solid var(--accent-blue);white-space:nowrap}
.sel-wrap{position:relative}.sel-wrap select{appearance:none;-webkit-appearance:none;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:var(--radius-md);padding:6px 26px 6px 10px;font-size:12.5px;color:var(--text-primary);cursor:pointer;font-family:var(--font);width:100%}.sel-wrap select:focus{outline:none;border-color:var(--accent-blue)}.chev{position:absolute;right:7px;top:50%;transform:translateY(-50%);pointer-events:none;color:var(--text-tertiary)}.chev svg{width:10px;height:10px;display:block}
.btn{display:inline-flex;align-items:center;gap:5px;padding:6px 12px;border-radius:var(--radius-md);font-size:12px;font-weight:500;font-family:var(--font);cursor:pointer;transition:all .12s;border:0.5px solid var(--border-mid);background:transparent;color:var(--text-secondary)}
.btn:hover{background:var(--bg-secondary);color:var(--text-primary)}.btn:disabled{opacity:.5;cursor:not-allowed}
.btn-primary{background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue)}.btn-primary:hover{background:var(--accent-blue);color:#fff}

.explorer-layout{display:grid;grid-template-columns:220px 1fr;gap:10px;align-items:start}
.tree-panel{padding:0;overflow:hidden;max-height:calc(100vh-240px);overflow-y:auto}
.tree-cat{border-bottom:0.5px solid var(--border-light)}
.tree-cat:last-child{border-bottom:none}
.tree-cat-header{display:flex;align-items:center;gap:6px;padding:8px 12px;cursor:pointer;font-size:12px;font-weight:500;color:var(--text-secondary);user-select:none}
.tree-cat-header:hover{background:var(--bg-secondary);color:var(--text-primary)}
.cat-icon{font-size:13px}
.cat-name{flex:1}
.cat-cnt{font-size:10px;background:var(--bg-secondary);color:var(--text-tertiary);padding:1px 6px;border-radius:8px;border:0.5px solid var(--border-mid)}
.tree-item{display:flex;align-items:center;gap:6px;padding:5px 12px 5px 28px;font-size:11.5px;color:var(--text-secondary);cursor:pointer;transition:all .1s}
.tree-item:hover{background:var(--bg-secondary);color:var(--text-primary)}
.tree-item.sel{background:var(--bg-info);color:var(--text-info)}
.obj-name{flex:1;font-family:'Consolas','SF Mono',monospace;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.obj-meta{font-size:10px;color:var(--text-tertiary);background:var(--bg-tertiary);padding:1px 5px;border-radius:3px}
.tree-empty{padding:4px 28px;font-size:11px;color:var(--text-tertiary)}

.tab-bar{display:flex;border-bottom:0.5px solid var(--border-light);background:var(--bg-secondary)}
.tab-btn{padding:9px 14px;font-size:12px;border:none;background:transparent;cursor:pointer;color:var(--text-secondary);font-family:var(--font);border-bottom:2px solid transparent;transition:all .12s}
.tab-btn:hover{color:var(--text-primary)}.tab-btn.active{color:var(--text-info);border-bottom-color:var(--accent-blue);font-weight:500}
.tab-info{margin-left:auto;padding:0 14px;font-size:11px;color:var(--text-tertiary);display:flex;align-items:center}

/* DDL */
.ddl-area{padding:12px}
.ddl-toolbar{display:flex;gap:6px;margin-bottom:10px}
.ddl-split{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.ddl-side{}
.ddl-label{font-size:10px;font-weight:600;letter-spacing:.6px;text-transform:uppercase;margin-bottom:5px}
.ddl-label.src{color:var(--text-info)}.ddl-label.tgt{color:var(--text-success)}
.ddl-code{background:var(--bg-secondary);border-radius:var(--radius-md);padding:12px;font-family:'Consolas','SF Mono',monospace;font-size:11.5px;color:var(--text-secondary);overflow:auto;max-height:360px;white-space:pre;border:0.5px solid var(--border-light)}
.ddl-code.tgt{background:#f0f7ea;border-color:var(--accent-green)}
.conv-summary{margin-top:6px;display:flex;flex-wrap:wrap;gap:3px}
.cv-item{font-size:10.5px;padding:2px 7px;border-radius:4px}
.cv-item.ok{background:var(--bg-success);color:var(--text-success)}.cv-item.warn{background:var(--bg-warning);color:var(--text-warning)}

/* 테스트 */
.test-area{padding:12px}
.param-section{background:var(--bg-secondary);border-radius:var(--radius-md);padding:10px;margin-bottom:10px}
.param-header{display:flex;align-items:center;justify-content:space-between;font-size:12px;font-weight:500;color:var(--text-primary);margin-bottom:8px}
.param-row{display:flex;align-items:center;gap:6px;margin-bottom:6px}
.param-row input{background:var(--bg-primary);border:0.5px solid var(--border-mid);border-radius:var(--radius-sm);padding:5px 8px;font-size:12px;color:var(--text-primary);font-family:var(--font)}
.param-row input:focus{outline:none;border-color:var(--accent-blue)}
.test-run-bar{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.test-elapsed{font-size:11.5px;color:var(--text-tertiary)}
.test-result{background:var(--bg-secondary);border-radius:var(--radius-md);padding:10px}
.tr-header{font-size:11px;font-weight:500;color:var(--text-secondary);margin-bottom:4px}
.func-result{display:flex;align-items:center;gap:8px;padding:10px;background:var(--bg-success);border-radius:var(--radius-md)}
.fr-label{font-size:11px;color:var(--text-success);font-weight:500}
.fr-val{font-size:14px;font-weight:600;color:var(--text-primary);font-family:'Consolas','SF Mono',monospace}
.result-table-wrap{overflow-x:auto}
.result-tbl{width:100%;border-collapse:collapse;font-size:11.5px}
.result-tbl th{background:var(--bg-tertiary);padding:5px 10px;text-align:left;border:0.5px solid var(--border-light);font-size:11px;color:var(--text-tertiary)}
.result-tbl td{padding:5px 10px;border:0.5px solid var(--border-light);color:var(--text-primary);font-family:'Consolas','SF Mono',monospace}

/* 정보 탭 */
.info-area{padding:12px}
.info-tbl{width:100%;border-collapse:collapse}
.info-tbl th{background:var(--bg-secondary);font-size:11px;color:var(--text-tertiary);padding:7px 10px;text-align:left;border-bottom:0.5px solid var(--border-light);width:30%;white-space:nowrap}
.info-tbl td{padding:7px 10px;font-size:12px;border-bottom:0.5px solid var(--border-light);color:var(--text-primary);font-family:'Consolas','SF Mono',monospace;word-break:break-all}
.info-tbl tr:last-child th,.info-tbl tr:last-child td{border-bottom:none}

.mini-btn{font-size:10.5px;padding:3px 8px;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:transparent;color:var(--text-secondary);cursor:pointer;font-family:var(--font);transition:all .12s}
.mini-btn:hover{background:var(--bg-secondary);color:var(--text-primary)}.mini-btn:disabled{opacity:.4;cursor:not-allowed}
.mini-btn.del{color:var(--text-danger)}.mini-btn.del:hover{background:var(--bg-danger)}

.deploy-result{padding:8px 12px;border-radius:var(--radius-md);font-size:12px;font-weight:500;display:flex;align-items:center}
.deploy-result.ok{background:var(--bg-success);color:var(--text-success)}
.deploy-result.err{background:var(--bg-danger);color:var(--text-danger)}
.mini-btn.deploy{background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue)}
.mini-btn.deploy:hover{background:var(--accent-blue);color:#fff}
/* AI 분석 */
.ai-loading{display:flex;align-items:center;gap:12px;padding:20px;background:var(--bg-info);border-radius:var(--radius-lg)}
.ai-spinner{width:24px;height:24px;border:2.5px solid var(--border-mid);border-top-color:var(--accent-blue);border-radius:50%;animation:spin 1s linear infinite;flex-shrink:0}
@keyframes spin{to{transform:rotate(360deg)}}
.ai-error{display:flex;align-items:center;gap:6px;padding:10px 12px;background:var(--bg-danger);border-radius:var(--radius-md);font-size:12px;color:var(--text-danger)}
.ai-header{display:flex;align-items:center;gap:10px;padding:12px 14px;background:linear-gradient(135deg,var(--bg-info),var(--bg-success));border-radius:var(--radius-lg);margin-bottom:12px}
.ai-title{font-size:14px;font-weight:600;color:var(--text-primary)}
.ai-subtitle{font-size:11px;color:var(--text-tertiary);margin-top:2px}
.ai-section{border:0.5px solid var(--border-light);border-radius:var(--radius-md);padding:12px 14px;margin-bottom:8px;background:var(--bg-secondary)}
.ai-section.warn{background:var(--bg-warning);border-color:var(--text-warning)}
.ai-section.high{background:var(--bg-danger);border-color:var(--text-danger)}
.ai-section.medium{background:var(--bg-warning);border-color:var(--text-warning)}
.ai-section.low{background:var(--bg-success);border-color:var(--text-success)}
.ai-sec-title{display:flex;align-items:center;gap:6px;font-size:11.5px;font-weight:600;color:var(--text-secondary);margin-bottom:8px}
.ai-body{font-size:12.5px;color:var(--text-primary);line-height:1.7;white-space:pre-wrap}
.ai-param-grid{display:flex;flex-direction:column;gap:4px}
.ai-param-row{display:flex;align-items:baseline;gap:8px;padding:5px 8px;background:var(--bg-primary);border-radius:var(--radius-sm)}
.ai-param-dir{font-size:10px;font-weight:700;padding:1px 6px;border-radius:4px;flex-shrink:0}
.ai-param-dir.IN{background:#e6f1fb;color:#185fa5}.ai-param-dir.OUT{background:#eaf3de;color:#3b6d11}.ai-param-dir.INOUT{background:#faeeda;color:#854f0b}
.ai-param-name{font-family:'Consolas','SF Mono',monospace;font-weight:600;color:var(--text-info);min-width:120px}
.ai-param-type{font-size:10.5px;background:var(--bg-secondary);color:var(--text-tertiary);padding:1px 6px;border-radius:3px;min-width:80px;flex-shrink:0}
.ai-param-desc{font-size:12px;color:var(--text-secondary)}
.ai-tbl-chip{font-family:'Consolas','SF Mono',monospace;font-size:11px;padding:3px 9px;background:var(--bg-info);color:var(--text-info);border-radius:6px}
.ai-warn-list{margin:0;padding-left:18px;font-size:12.5px;color:var(--text-primary);line-height:1.8}
.risk-badge{font-size:11px;font-weight:700;padding:3px 12px;border-radius:6px}
.risk-badge.low{background:var(--bg-success);color:var(--text-success)}
.risk-badge.medium{background:var(--bg-warning);color:var(--text-warning)}
.risk-badge.high{background:var(--bg-danger);color:var(--text-danger)}
.ai-empty{display:flex;flex-direction:column;align-items:center;padding:40px 20px;cursor:pointer;border:1.5px dashed var(--border-mid);border-radius:var(--radius-lg);transition:all .2s}
.ai-empty:hover{border-color:var(--accent-blue);background:var(--bg-info)}
.ai-empty-ico{font-size:32px;margin-bottom:10px}
.ai-empty-txt{font-size:14px;font-weight:600;color:var(--text-primary);margin-bottom:6px}
.ai-empty-sub{font-size:12px;color:var(--text-tertiary);text-align:center;line-height:1.6}
.tab-btn.ai{background:linear-gradient(135deg,#185fa5,#378add);color:#fff;font-weight:600}
.tab-btn.ai.active{border-bottom-color:#fff;color:#fff}

</style>
