<template>
  <div>
    <div class="page-title">검증 & 대사</div>
    <div class="page-desc">이관된 테이블·오브젝트가 소스와 일치하는지 검증합니다</div>

    <!-- 연결 상태 배너 -->
    <div v-if="!connector.bothConnected" class="warn-banner" style="margin-bottom:10px">
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px;flex-shrink:0"><path d="M8 2L14 14H2L8 2z"/></svg>
      소스·타겟 DB 연결이 필요합니다.
      <button class="act-btn" style="margin-left:8px" @click="$router.push('/connector')">커넥터 관리</button>
    </div>

    <!-- 설정 패널 -->
    <div class="card cfg-panel">
      <div class="cfg-row">
        <!-- 소스 DB 정보 -->
        <div class="cfg-db-box src">
          <span class="db-lbl">소스</span>
          <span class="db-name">{{ connector.source.database || '미연결' }}</span>
          <span class="db-type">{{ connector.source.dbType }}</span>
        </div>
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:16px;height:16px;color:var(--text-tertiary)">
          <line x1="2" y1="8" x2="14" y2="8"/><polyline points="9,4 14,8 9,12"/>
        </svg>
        <div class="cfg-db-box tgt">
          <span class="db-lbl">타겟</span>
          <span class="db-name">{{ connector.target.database || '미연결' }}</span>
          <span class="db-type">{{ connector.target.dbType }}</span>
        </div>
      </div>

      <!-- 검증 유형 탭 -->
      <div class="vtype-tabs">
        <button class="vtab" :class="{active:vType==='table'}" @click="vType='table'">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><rect x="1" y="2" width="12" height="10" rx="1"/><line x1="1" y1="5" x2="13" y2="5"/><line x1="5" y1="2" x2="5" y2="12"/></svg>
          테이블 검증
        </button>
        <button class="vtab" :class="{active:vType==='object'}" @click="vType='object';loadSrcObjects()">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><path d="M2 2h4v4H2z"/><path d="M8 2h4v4H8z"/><path d="M2 8h4v4H2z"/><path d="M8 8h4v4H8z"/></svg>
          오브젝트 검증
        </button>
      </div>

      <!-- ── 테이블 검증 설정 ── -->
      <template v-if="vType==='table'">
        <div class="sel-row">
          <div style="flex:1">
            <div class="field-label">검증할 테이블 (비워두면 전체)</div>
            <input type="text" v-model="tableInput" placeholder="table1, table2, ... (쉼표 구분, 공백이면 전체)"/>
          </div>
          <div>
            <div class="field-label">검증 모드</div>
            <div class="sel-wrap"><select v-model="mode">
              <option value="count">COUNT(*) 대사</option>
              <option value="sample">샘플 데이터 비교</option>
              <option value="checksum">체크섬 비교</option>
            </select><Chev/></div>
          </div>
          <div>
            <div class="field-label">결과 필터</div>
            <div class="sel-wrap"><select v-model="filterMode">
              <option value="all">전체</option>
              <option value="fail">불일치만</option>
              <option value="ok">일치만</option>
            </select><Chev/></div>
          </div>
          <button class="btn btn-primary" style="align-self:flex-end" @click="runValidate" :disabled="running||!connector.bothConnected">
            <span v-if="running" class="spinner" style="width:12px;height:12px;border-top-color:#fff;display:inline-block"></span>
            {{ running?'검증 중...':'검증 실행' }}
          </button>
        </div>
        <!-- 테이블 결과 -->
        <div v-if="results.length" class="val-result-area">
          <div class="val-kpi-row">
            <div class="vkpi ok"><div class="vkpi-n">{{ results.filter(r=>r.match).length }}</div><div class="vkpi-l">일치</div></div>
            <div class="vkpi fail"><div class="vkpi-n">{{ results.filter(r=>!r.match).length }}</div><div class="vkpi-l">불일치</div></div>
            <div class="vkpi info"><div class="vkpi-n">{{ results.length }}</div><div class="vkpi-l">전체</div></div>
            <div class="vkpi warn"><div class="vkpi-n">{{ results.filter(r=>!r.tgt_exist).length }}</div><div class="vkpi-l">타겟 없음</div></div>
            <button v-if="failCount>0" class="btn btn-primary" style="margin-left:auto" @click="reRunAll">
              ↺ 불일치 {{ failCount }}개 일괄 재이관
            </button>
          </div>
          <div class="card tbl-wrap" style="margin-top:0">
            <table class="val-tbl">
              <thead><tr>
                <th><input type="checkbox" @change="toggleAllTbl" :checked="allTblSel"/></th>
                <th @click="tblSort='table'" class="sortable">테이블</th>
                <th @click="tblSort='src_count'" class="sortable">소스 rows</th>
                <th @click="tblSort='tgt_count'" class="sortable">타겟 rows</th>
                <th>차이</th><th>상태</th><th>액션</th>
              </tr></thead>
              <tbody>
                <tr v-for="r in filteredResults" :key="r.table" :class="{'row-fail':!r.match,'row-ok':r.match}" @click="detailRow=r">
                  <td @click.stop><input type="checkbox" v-model="r._sel"/></td>
                  <td style="font-family:'Consolas','SF Mono',monospace;font-weight:500">{{ r.table }}</td>
                  <td>{{ r.src_count?.toLocaleString() ?? '—' }}</td>
                  <td>{{ r.tgt_count?.toLocaleString() ?? '—' }}</td>
                  <td>
                    <span v-if="!r.tgt_exist" class="stat-badge miss">타겟없음</span>
                    <span v-else-if="r.match" class="stat-badge ok">0</span>
                    <span v-else class="stat-badge fail">{{ ((r.src_count||0)-(r.tgt_count||0)).toLocaleString() }}</span>
                  </td>
                  <td>
                    <span class="stat-badge" :class="r.match?'ok':r.tgt_exist?'fail':'miss'">
                      {{ r.match?'일치':r.tgt_exist?'불일치':'타겟없음' }}
                    </span>
                  </td>
                  <td @click.stop>
                    <div style="display:flex;gap:4px;flex-wrap:nowrap">
                      <button v-if="!r.match || !r.tgt_exist" class="act-btn" @click.stop="reRun(r.table)">↺ 재이관</button>
                      <button v-if="!r.tgt_exist" class="act-btn ok" @click.stop="createTable(r.table)">+ 테이블생성</button>
                      <button v-if="r.match" class="act-btn info" @click.stop="detailRow=r">📋 상세</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>

      <!-- ── 오브젝트 검증 설정 ── -->
      <template v-if="vType==='object'">
        <div class="sel-row" style="align-items:flex-end">
          <div style="flex:1">
            <div class="field-label">오브젝트 유형</div>
            <div style="display:flex;gap:6px;flex-wrap:wrap">
              <label v-for="t in objTypes" :key="t.v" class="obj-type-chk">
                <input type="checkbox" v-model="selObjTypes" :value="t.v" style="accent-color:var(--accent-blue)"/>
                <span class="otc-ico" :class="t.v">{{ t.icon }}</span>
                {{ t.label }}
              </label>
            </div>
          </div>
          <button class="btn btn-primary" @click="runObjValidate" :disabled="objRunning||!connector.bothConnected||!selObjTypes.length">
            <span v-if="objRunning" class="spinner" style="width:12px;height:12px;border-top-color:#fff;display:inline-block"></span>
            {{ objRunning?'검증 중...':'오브젝트 검증' }}
          </button>
        </div>

        <!-- 오브젝트 선택 목록 -->
        <div v-if="srcObjects && hasAnyObjects" class="obj-sel-panel">
          <div class="obj-sel-header">
            소스 오브젝트 목록
            <div style="display:flex;gap:5px">
              <button class="mini-btn" @click="selAllObjs">전체 선택</button>
              <button class="mini-btn" @click="clearAllObjs">해제</button>
            </div>
          </div>

          <div v-for="grp in objGroups" :key="grp.type" v-show="selObjTypes.includes(grp.type)&&grp.items.length">
            <div class="obj-grp-header">
              <input type="checkbox" :checked="grp.items.every(o=>o._sel)" @change="toggleGrp(grp)" style="accent-color:var(--accent-blue)"/>
              <span class="otc-ico" :class="grp.type">{{ grp.icon }}</span>
              {{ grp.label }} ({{ grp.items.length }})
            </div>
            <div class="obj-list-grid">
              <label v-for="obj in grp.items" :key="obj.name" class="obj-row-chk">
                <input type="checkbox" v-model="obj._sel" style="accent-color:var(--accent-blue)"/>
                <span class="obj-nm">{{ obj.name }}</span>
                <span v-if="obj.event" class="obj-meta">{{ obj.event }}</span>
              </label>
            </div>
          </div>
        </div>

        <!-- 오브젝트 검증 결과 -->
        <div v-if="objResults.length" class="val-result-area">
          <div class="val-kpi-row">
            <div class="vkpi ok"><div class="vkpi-n">{{ objResults.filter(r=>r.status==='ok').length }}</div><div class="vkpi-l">존재</div></div>
            <div class="vkpi fail"><div class="vkpi-n">{{ objResults.filter(r=>r.status==='missing').length }}</div><div class="vkpi-l">미이관</div></div>
            <div class="vkpi warn"><div class="vkpi-n">{{ objResults.filter(r=>r.status==='error').length }}</div><div class="vkpi-l">오류</div></div>
            <button v-if="objResults.filter(r=>r.status==='missing').length" class="btn btn-primary" style="margin-left:auto" @click="deployMissing">
              🚀 미이관 오브젝트 타겟에 생성
            </button>
          </div>
          <div class="card tbl-wrap" style="margin-top:0">
            <table class="val-tbl">
              <thead><tr>
                <th><input type="checkbox" @change="toggleAllObj" :checked="allObjSel"/></th>
                <th>유형</th><th>오브젝트명</th><th>소스</th><th>타겟</th><th>상태</th><th>액션</th>
              </tr></thead>
              <tbody>
                <tr v-for="r in objResults" :key="r.name+r.type" :class="{'row-fail':r.status!=='ok','row-ok':r.status==='ok'}">
                  <td><input type="checkbox" v-model="r._sel" style="accent-color:var(--accent-blue)"/></td>
                  <td>
                    <span class="otc-ico sm" :class="r.type">{{ objTypes.find(t=>t.v===r.type)?.icon }}</span>
                  </td>
                  <td style="font-family:'Consolas','SF Mono',monospace;font-weight:500">{{ r.name }}</td>
                  <td><span class="stat-badge ok">존재</span></td>
                  <td>
                    <span v-if="r.status==='ok'" class="stat-badge ok">존재</span>
                    <span v-else-if="r.status==='missing'" class="stat-badge miss">없음</span>
                    <span v-else class="stat-badge fail">오류</span>
                  </td>
                  <td>
                    <span class="stat-badge" :class="r.status==='ok'?'ok':r.status==='missing'?'miss':'fail'">
                      {{ r.status==='ok'?'일치':'미이관' }}
                    </span>
                  </td>
                  <td>
                    <div style="display:flex;flex-direction:column;gap:3px">
                      <button v-if="r.status==='missing'||r.status==='error'" class="act-btn ok" @click="deployOne(r)" :disabled="r.deploying">
                        <span v-if="r.deploying" class="spinner" style="width:10px;height:10px;display:inline-block;margin-right:3px"></span>
                        {{ r.deploying?'AI 변환중...':'🚀 타겟생성' }}
                      </button>
                      <span v-if="r.notes" style="font-size:10px;color:var(--text-success);max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" :title="r.notes">{{ r.notes }}</span>
                      <span v-if="r.deployError" style="font-size:10px;color:var(--text-danger);max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" :title="r.deployError">✗ {{ r.deployError.slice(0,50) }}</span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </div>

    <!-- 테이블 상세 모달 -->
    <div v-if="detailRow" class="modal-overlay" @click.self="detailRow=null">
      <div class="modal">
        <div class="modal-title">{{ detailRow.table }} — 상세</div>
        <table class="det-tbl">
          <tr><td>소스 COUNT(*)</td><td><b>{{ detailRow.src_count?.toLocaleString() }}</b></td></tr>
          <tr><td>타겟 COUNT(*)</td><td><b>{{ detailRow.tgt_count?.toLocaleString() }}</b></td></tr>
          <tr><td>차이</td><td><b :style="{color:detailRow.match?'var(--text-success)':'var(--text-danger)'}">{{ ((detailRow.src_count||0)-(detailRow.tgt_count||0)).toLocaleString() }}</b></td></tr>
          <tr><td>검증 시각</td><td>{{ detailRow.checked_at }}</td></tr>
        </table>
        <div class="modal-btns">
          <button class="btn" @click="detailRow=null">닫기</button>
          <button v-if="!detailRow.match" class="btn btn-primary" @click="reRun(detailRow.table);detailRow=null">재이관</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, reactive, onMounted } from 'vue'
import { useConnectorStore } from '@/store/connectorStore.js'
import { useAppStore } from '@/store/appStore.js'
import axios from 'axios'

const connector = useConnectorStore()
const app       = useAppStore()

const Chev = { template: '<div class="chev-ico"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px;display:block"><polyline points="2,4 6,8 10,4"/></svg></div>' }

// 검증 유형
const vType = ref('table')

// ── 테이블 검증 ──
const tableInput = ref('')
const mode       = ref('count')
const filterMode = ref('all')
const running    = ref(false)
const results    = ref([])
const detailRow  = ref(null)
const tblSort    = ref('table')

const failCount       = computed(() => results.value.filter(r=>!r.match).length)
const filteredResults = computed(() => {
  let r = results.value
  if (filterMode.value === 'fail') r = r.filter(x=>!x.match)
  if (filterMode.value === 'ok')   r = r.filter(x=>x.match)
  return r
})
const allTblSel = computed(() => results.value.length && results.value.every(r=>r._sel))
function toggleAllTbl(e) { results.value.forEach(r=>r._sel=e.target.checked) }

// ── 오브젝트 검증 ──
const objTypes   = [
  {v:'PROCEDURE', label:'프로시저', icon:'⚙'},
  {v:'FUNCTION',  label:'함수',    icon:'ƒ'},
  {v:'TRIGGER',   label:'트리거',  icon:'⚡'},
  {v:'VIEW',      label:'뷰',      icon:'👁'},
]
const selObjTypes  = ref(['PROCEDURE','FUNCTION','TRIGGER','VIEW'])
const srcObjects   = ref(null)
const objRunning   = ref(false)
const objResults   = ref([])
const objGroupsRaw = ref([])

const hasAnyObjects = computed(() => srcObjects.value && (
  srcObjects.value.procedures?.length || srcObjects.value.functions?.length ||
  srcObjects.value.triggers?.length   || srcObjects.value.views?.length
))

const objGroups = computed(() => objGroupsRaw.value)

watch(srcObjects, (data) => {
  if (!data) { objGroupsRaw.value = []; return }
  objGroupsRaw.value = [
    {type:'PROCEDURE', label:'프로시저', icon:'⚙', items:(data.procedures||[]).map(o=>reactive({...o,_sel:true}))},
    {type:'FUNCTION',  label:'함수',    icon:'ƒ',  items:(data.functions||[]).map(o=>reactive({...o,_sel:true}))},
    {type:'TRIGGER',   label:'트리거',  icon:'⚡', items:(data.triggers||[]).map(o=>reactive({...o,_sel:true}))},
    {type:'VIEW',      label:'뷰',      icon:'👁',  items:(data.views||[]).map(o=>reactive({...o,_sel:true}))},
  ]
})

const allObjSel = computed(() => objResults.value.length && objResults.value.every(r=>r._sel))
function toggleAllObj(e) { objResults.value.forEach(r=>r._sel=e.target.checked) }
function toggleGrp(grp) { const all=grp.items.every(o=>o._sel); grp.items.forEach(o=>o._sel=!all) }
function selAllObjs() { objGroups.value.forEach(g=>g.items.forEach(o=>o._sel=true)) }
function clearAllObjs() { objGroups.value.forEach(g=>g.items.forEach(o=>o._sel=false)) }

async function loadSrcObjects() {
  if (connector.source.status !== 'ok' || srcObjects.value) return
  const c = connector.source
  try {
    const {data} = await axios.get('/api/v1/schema/objects', {
      params:{side:'source',db_type:c.dbType,host:c.host,port:c.port,
              username:c.username,password:c.password,database:c.database}
    })
    srcObjects.value = data
  } catch(e) { app.notify('오브젝트 조회 실패: '+e.message,'error') }
}

// ── 오브젝트 타겟 존재 여부 확인 ──
async function checkObjExists(db_type, host, port, username, password, database, obj_type, obj_name) {
  try {
    const {data} = await axios.post('/api/v1/schema/execute-object', {
      db_type, host, port, username, password, database,
      obj_type: 'CHECK_EXISTS', obj_name, params:[]
    })
    return data.success && data.rows?.length > 0
  } catch { return false }
}

async function runObjValidate() {
  // 선택된 오브젝트 수집
  const selected = []
  for (const grp of objGroups.value) {
    if (!selObjTypes.value.includes(grp.type)) continue
    for (const obj of grp.items) {
      if (obj._sel) selected.push({name:obj.name, type:grp.type, body:obj.body||''})
    }
  }
  if (!selected.length) { app.notify('오브젝트를 선택하세요','error'); return }

  objRunning.value = true; objResults.value = []
  const tgt = connector.target

  for (const obj of selected) {
    const exists = await checkObjExists(
      tgt.dbType, tgt.host, tgt.port, tgt.username, tgt.password, tgt.database,
      obj.type, obj.name
    )
    objResults.value.push({ ...obj, status: exists?'ok':'missing', _sel:false, deploying:false })
  }
  objRunning.value = false
  const miss = objResults.value.filter(r=>r.status==='missing').length
  app.notify(`오브젝트 검증 완료 — 미이관 ${miss}개`, miss?'warn':'success')
}

// ── AI DDL 변환 (브라우저에서 Anthropic API 직접 호출) ──
async function aiConvertDDL(mysqlDdl, objType, objName, srcDb, tgtTables) {
  // 백엔드 프록시를 통해 Anthropic API 호출 (CORS/방화벽 우회)
  try {
    const {data} = await axios.post('/api/v1/schema/ai-convert-ddl', {
      ddl:         mysqlDdl,
      obj_type:    objType,
      obj_name:    objName,
      src_db:      srcDb,
      tgt_tables:  tgtTables || [],
      tgt_db_type: connector.target.dbType || 'mssql',
    })
    if (data.error) {
      // 오류 로그를 백엔드 파일에 기록
      axios.post('/api/v1/settings/frontend-log', {
        level:'ERROR', page:'Validate',
        message: `AI DDL 변환 실패 [${objName}]: ${data.error}`
      }).catch(()=>{})
      return { statements: [], error: data.error, notes: data.notes || '' }
    }
    return data
  } catch(e) {
    const errMsg = e.response?.data?.detail || e.message
    axios.post('/api/v1/settings/frontend-log', {
      level:'ERROR', page:'Validate',
      message: `AI DDL axios 오류 [${objName}]`,
      detail: errMsg
    }).catch(()=>{})
    return { statements: [], error: errMsg, notes: '' }
  }
}


async function deployOne(r) {
  r.deploying = true; r.notes = ''; r.deployError = ''
  const tgt = connector.target
  try {
    // STEP 1: 백엔드 변환 (AI 우선, 실패 시 rule-based 폴백)
    app.notify(`${r.name} 변환 중...`, 'info')
    let statements = []
    let convNotes  = ''

    // 1-a. AI 변환 시도
    const aiResult = await aiConvertDDL(r.body, r.type, r.name,
      connector.source.database, [])
    if (aiResult.statements?.length) {
      statements = aiResult.statements
      convNotes  = aiResult.notes || 'AI 변환'
    } else {
      // 1-b. AI 실패 → 백엔드 rule-based 변환 폴백
      app.notify(`${r.name} AI 실패 — 규칙 기반 변환`, 'warn')
      try {
        const { data: rbData } = await axios.post('/api/v1/schema/ai-convert-ddl', {
          ddl:         r.body,
          obj_type:    r.type,
          obj_name:    r.name,
          src_db:      connector.source.database,
          tgt_db_type: tgt.dbType || 'mssql',
          force_rule:  true,   // API 키 무시하고 rule-based 강제
        })
        statements = rbData.statements || []
        convNotes  = rbData.notes || '규칙 기반 변환'
      } catch(fe) {
        // rule-based도 실패하면 원본 DDL을 단일 statement로 사용
        statements = [r.body]
        convNotes  = '원본 DDL 직접 실행'
      }
    }

    if (!statements.length) {
      throw new Error('변환 결과 없음 — 원본 DDL을 확인하세요')
    }

    // STEP 2: 백엔드에 statements 전달하여 실행
    const {data} = await axios.post('/api/v1/schema/execute-object', {
      db_type:      tgt.dbType,
      host:         tgt.host,
      port:         tgt.port,
      username:     tgt.username,
      password:     tgt.password,
      database:     tgt.database,
      obj_type:     'DDL_CREATE',
      obj_sub_type: r.type,
      obj_name:     r.name,
      statements:   statements,
      notes:        convNotes,
      ddl:          r.body,
      params:       [],
    })
    r.status = data.success ? 'ok' : 'error'
    r.notes  = data.notes || data.output || convNotes || ''
    r.deployError = data.success ? '' : (data.error || '실패')
    app.notify(
      data.success ? `${r.name} 생성 완료` : `생성 실패: ${data.error||'오류'}`,
      data.success ? 'success' : 'error'
    )
    if (data.warnings?.length) data.warnings.slice(0,2).forEach(w=>app.notify('⚠ '+w.slice(0,50),'warn'))
  } catch(e) {
    r.status = 'error'; r.deployError = e.response?.data?.detail || e.message
    app.notify('생성 실패: '+r.deployError, 'error')
  } finally {
    r.deploying = false   // 항상 해제
  }
}

async function deployMissing() {
  const missing = objResults.value.filter(r=>r.status==='missing')
  for (const r of missing) await deployOne(r)
  app.notify(`${missing.length}개 오브젝트 생성 완료`,'success')
}

// ── 테이블 검증 ──
async function runValidate() {
  running.value = true; results.value = []
  const src = connector.source; const tgt = connector.target
  const tables = tableInput.value ? tableInput.value.split(',').map(t=>t.trim()).filter(Boolean) : []
  try {
    const {data} = await axios.post('/api/v1/validate/run', {
      src_info: {
        db_type:  src.dbType,
        host:     src.host,
        port:     src.port || 3306,
        username: src.username,
        password: src.password,
        database: src.database,
      },
      tgt_info: {
        db_type:  tgt.dbType,
        host:     tgt.host,
        port:     tgt.port || 1433,
        username: tgt.username,
        password: tgt.password,
        database: tgt.database,
      },
      tables,
      method: mode.value === 'count' ? 'row_count' : mode.value,
    })
    results.value = data.results.map(r=>({
      ...r,
      src_count: r.src,
      tgt_count: r.tgt,
      _sel: false,
    }))
    app.notify(`검증 완료 — ${failCount.value}개 불일치`, failCount.value?'warn':'success')
  } catch(e) { app.notify('검증 실패: '+e.message,'error') }
  running.value = false
}

async function reRun(table) {
  const src = connector.source; const tgt = connector.target
  try {
    await axios.post('/api/v1/jobs/', {
      name: `[재이관] ${table}`,
      src_db: src.dbType, src_host:src.host, src_database:src.database,
      src_username:src.username, src_password:src.password,
      tgt_db: tgt.dbType, tgt_host:tgt.host, tgt_database:tgt.database,
      tgt_username:tgt.username, tgt_password:tgt.password,
      tables:[table], truncate_target:true,
    })
    app.notify(`[${table}] 재이관 Job 시작`,'success')
  } catch(e) { app.notify('재이관 실패','error') }
}

async function reRunAll() {
  const tables = results.value.filter(r=>!r.match).map(r=>r.table)
  if (!tables.length) return
  const src=connector.source; const tgt=connector.target
  await axios.post('/api/v1/jobs/', {
    name:`[일괄재이관] ${tables.length}개 테이블`,
    src_db:src.dbType, src_host:src.host, src_database:src.database,
    src_username:src.username, src_password:src.password,
    tgt_db:tgt.dbType, tgt_host:tgt.host, tgt_database:tgt.database,
    tgt_username:tgt.username, tgt_password:tgt.password,
    tables, truncate_target:true,
  })
  app.notify(`${tables.length}개 테이블 재이관 Job 시작`,'success')
}

async function createTable(table) {
  app.notify(`[${table}] 타겟 테이블 생성 중...`,'info')
}

onMounted(() => { if (connector.source.status==='ok') loadSrcObjects() })
</script>

<style scoped>
.warn-banner{display:flex;align-items:center;gap:8px;padding:10px 14px;background:var(--bg-warning);border-radius:var(--radius-md);font-size:12px;color:var(--text-warning)}
.cfg-panel{margin-bottom:10px}
.cfg-row{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.cfg-db-box{display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--bg-secondary);border-radius:var(--radius-md);border:0.5px solid var(--border-light)}
.cfg-db-box.src{border-left:3px solid var(--accent-blue)}.cfg-db-box.tgt{border-left:3px solid var(--accent-green)}
.db-lbl{font-size:10px;font-weight:700;color:var(--text-tertiary)}.db-name{font-weight:600;font-size:13px;color:var(--text-primary)}.db-type{font-size:11px;color:var(--text-tertiary)}
.vtype-tabs{display:flex;gap:6px;margin-bottom:12px;border-bottom:0.5px solid var(--border-light);padding-bottom:10px}
.vtab{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border-radius:var(--radius-md);border:0.5px solid var(--border-mid);background:transparent;cursor:pointer;font-size:12.5px;font-weight:500;font-family:var(--font);color:var(--text-secondary);transition:all .12s}
.vtab:hover{background:var(--bg-secondary)}.vtab.active{background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue)}
.sel-row{display:flex;align-items:flex-end;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.sel-row>div{display:flex;flex-direction:column;gap:3px}
.field-label{font-size:11px;font-weight:500;color:var(--text-secondary)}
input[type="text"]{padding:7px 10px;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:var(--radius-md);font-size:12px;color:var(--text-primary);font-family:var(--font);width:260px}
input[type="text"]:focus{outline:none;border-color:var(--accent-blue)}
.sel-wrap{position:relative;min-width:140px}.sel-wrap select{width:100%;appearance:none;-webkit-appearance:none;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:var(--radius-md);padding:7px 28px 7px 10px;font-size:12px;color:var(--text-primary);cursor:pointer;font-family:var(--font)}.sel-wrap select:focus{outline:none;border-color:var(--accent-blue)}.chev-ico{position:absolute;right:8px;top:50%;transform:translateY(-50%);pointer-events:none;color:var(--text-tertiary)}.chev-ico svg{width:10px;height:10px;display:block}
/* 오브젝트 타입 선택 */
.obj-type-chk{display:flex;align-items:center;gap:5px;padding:6px 10px;border:0.5px solid var(--border-mid);border-radius:var(--radius-md);cursor:pointer;font-size:12px;color:var(--text-secondary);transition:all .12s}
.obj-type-chk:has(input:checked){background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue)}
.otc-ico{width:20px;height:20px;display:inline-flex;align-items:center;justify-content:center;border-radius:4px;font-size:13px}
.otc-ico.sm{width:16px;height:16px;font-size:11px}
.otc-ico.PROCEDURE{background:#e6f1fb}.otc-ico.FUNCTION{background:#eaf3de}.otc-ico.TRIGGER{background:#faeeda}.otc-ico.VIEW{background:#eeedfe}
/* 오브젝트 선택 패널 */
.obj-sel-panel{background:var(--bg-secondary);border-radius:var(--radius-md);border:0.5px solid var(--border-light);overflow:hidden;margin-bottom:12px;max-height:280px;overflow-y:auto}
.obj-sel-header{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:var(--bg-tertiary);font-size:11.5px;font-weight:500;color:var(--text-secondary);border-bottom:0.5px solid var(--border-light)}
.obj-grp-header{display:flex;align-items:center;gap:7px;padding:7px 12px;background:var(--bg-secondary);font-size:12px;font-weight:500;color:var(--text-primary);border-bottom:0.5px solid var(--border-light);cursor:pointer}
.obj-list-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));padding:4px 8px}
.obj-row-chk{display:flex;align-items:center;gap:6px;padding:5px 8px;cursor:pointer;border-radius:var(--radius-sm);font-size:12px}
.obj-row-chk:hover{background:var(--bg-primary)}.obj-nm{font-family:'Consolas','SF Mono',monospace;font-weight:500;color:var(--text-primary)}.obj-meta{font-size:10.5px;color:var(--text-tertiary)}
/* 결과 */
.val-result-area{margin-top:12px}
.val-kpi-row{display:flex;gap:8px;margin-bottom:10px;align-items:center;flex-wrap:wrap}
.vkpi{background:var(--bg-secondary);border:0.5px solid var(--border-light);border-radius:var(--radius-md);padding:8px 14px;min-width:70px;text-align:center}
.vkpi-n{font-size:20px;font-weight:700}.vkpi-l{font-size:10.5px;color:var(--text-tertiary)}
.vkpi.ok .vkpi-n{color:var(--text-success)}.vkpi.fail .vkpi-n{color:var(--text-danger)}.vkpi.info .vkpi-n{color:var(--text-info)}.vkpi.warn .vkpi-n{color:var(--text-warning)}
.tbl-wrap{padding:0;overflow:hidden}
.val-tbl{width:100%;border-collapse:collapse;font-size:12px}
.val-tbl th{background:var(--bg-secondary);padding:7px 12px;text-align:left;font-size:11px;font-weight:600;color:var(--text-tertiary);border-bottom:0.5px solid var(--border-mid)}
.val-tbl td{padding:7px 12px;border-bottom:0.5px solid var(--border-light);vertical-align:middle}
.val-tbl tr:last-child td{border-bottom:none}.val-tbl tr.row-ok:hover td,.val-tbl tr.row-fail:hover td{filter:brightness(.96)}
.row-ok{background:transparent}.row-fail{background:rgba(239,68,68,.04)}
.stat-badge{font-size:10.5px;font-weight:600;padding:2px 8px;border-radius:6px}
.stat-badge.ok{background:var(--bg-success);color:var(--text-success)}.stat-badge.fail{background:var(--bg-danger);color:var(--text-danger)}.stat-badge.miss{background:var(--bg-warning);color:var(--text-warning)}
.act-btn{font-size:11px;padding:3px 9px;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:transparent;cursor:pointer;color:var(--text-secondary);font-family:var(--font);transition:all .12s}
.act-btn:hover{background:var(--bg-secondary)}.act-btn.ok{color:var(--text-success);border-color:var(--accent-green)}.act-btn.ok:hover{background:var(--bg-success)}
.act-btn:disabled{opacity:.5;cursor:not-allowed}
.act-btn.info{color:var(--text-info);border-color:var(--accent-blue)}.act-btn.info:hover{background:var(--bg-info)}
.sortable{cursor:pointer;user-select:none}.sortable:hover{color:var(--text-primary)}
.btn{display:inline-flex;align-items:center;gap:5px;padding:6px 12px;border-radius:var(--radius-md);font-size:12px;font-weight:500;font-family:var(--font);cursor:pointer;border:0.5px solid var(--border-mid);background:transparent;color:var(--text-secondary);transition:all .12s}
.btn:hover{background:var(--bg-secondary)}.btn-primary{background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue)}.btn-primary:hover{background:var(--accent-blue);color:#fff}.btn:disabled{opacity:.5;cursor:not-allowed}
.mini-btn{font-size:10.5px;padding:3px 8px;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:transparent;cursor:pointer;font-family:var(--font);color:var(--text-secondary)}
.mini-btn:hover{background:var(--bg-secondary)}
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;z-index:999}
.modal{background:var(--bg-primary);border-radius:var(--radius-lg);padding:20px;width:360px;border:0.5px solid var(--border-mid)}
.modal-title{font-size:14px;font-weight:600;color:var(--text-primary);margin-bottom:14px}
.det-tbl{width:100%;border-collapse:collapse;font-size:12.5px}
.det-tbl td{padding:8px 10px;border-bottom:0.5px solid var(--border-light)}
.det-tbl td:first-child{color:var(--text-tertiary);width:40%}
.modal-btns{display:flex;justify-content:flex-end;gap:8px;margin-top:14px}
</style>
