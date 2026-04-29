<template>
  <div>
    <!-- 미연결 시 ConnectPanel -->
    <ConnectPanel v-if="!conn.bothConnected" @connected="loadObjects" />

    <!-- PageHeader: DB 연결 정보 + 컨트롤 -->
    <PageHeader :show-db="true" :src-db="conn.source" :tgt-db="conn.target">
      <template #controls>
        <div class="sc-side-tabs">
          <button class="sc-side-tab" :class="{on: selSide==='source'}" @click="switchSide('source')">소스</button>
          <button class="sc-side-tab" :class="{on: selSide==='target'}" @click="switchSide('target')">타겟</button>
        </div>
      </template>
      <template #actions>
        <button class="btn" @click="loadObjects" :disabled="loading">
          <span v-if="loading" class="spinner" style="width:12px;height:12px;display:inline-block"></span>
          {{ loading ? '조회 중...' : '↻ 새로고침' }}
        </button>
      </template>
    </PageHeader>

    <div class="explorer-layout">
      <!-- 좌측 트리 -->
      <div class="card tree-panel">
        <div v-if="loading" class="empty-state" style="padding:20px">
          <span class="spinner" style="width:18px;height:18px;display:inline-block"></span>
        </div>
        <div v-else-if="!selSide" class="empty-state" style="padding:24px;font-size:12px;text-align:center;color:var(--text-tertiary)">
          상단에서 소스 또는 타겟 DB를 선택하세요
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

            <!-- 통합 툴바: 좌=소스버튼 / 우=방식선택+생성버튼 (같은 선상) -->
            <div class="ddl-toolbar">
              <!-- 왼쪽: 소스 DDL 버튼 -->
              <div class="ddl-toolbar-left">
                <span class="ddl-side-label src">소스 <span class="ddl-side-db">{{ (curConn.dbType||'').toUpperCase() }}</span></span>
                <button class="mini-btn" @click="loadDDL" :disabled="loadingDDL">
                  <span v-if="loadingDDL" class="spinner" style="width:11px;height:11px;display:inline-block"></span>
                  {{ loadingDDL ? '조회 중...' : 'DDL 로드' }}
                </button>
                <button class="mini-btn" @click="copySrcDDL" :disabled="!sourceDDL">📋 복사</button>
                <div class="ddl-toolbar-spacer"></div>
                <button v-if="sourceDDL" class="gen-script-btn" @click="generateScript" :disabled="scriptLoading">
                  <span v-if="scriptLoading" class="spinner" style="width:10px;height:10px;border-width:1.5px"></span>
                  <svg v-else viewBox="0 0 12 12" fill="currentColor" style="width:10px;height:10px;flex-shrink:0"><polygon points="2,1 10,6 2,11"/></svg>
                  {{ scriptLoading ? '생성 중...' : '스크립트 생성' }}
                </button>

              </div>
              <!-- 구분선 -->
              <div class="ddl-toolbar-sep"></div>
              <!-- 오른쪽: 방식 선택 + 스크립트 생성 버튼 -->
              <div class="ddl-toolbar-right">
                <span class="ddl-side-label tgt">타겟 <span class="ddl-side-db">{{ (otherConn.dbType||'').toUpperCase() }}</span></span>
                <div class="oe-mode-tabs">
                  <button class="oe-mode-tab" :class="{active: deployMode==='drop_recreate'}" @click="selectMode('drop_recreate')">🔄 원본 그대로</button>
                  <button class="oe-mode-tab" :class="{active: deployMode==='rules'}"         @click="selectMode('rules')">⚙ 규칙 변환</button>
                  <button class="oe-mode-tab" :class="{active: deployMode==='ai'}"            @click="selectMode('ai')">🤖 AI 변환</button>
                </div>
                <span class="deploy-mode-desc"
                  :style="deployMode==='drop_recreate' ? 'color:#6366f1' :
                           deployMode==='rules'         ? 'color:#059669' :
                           deployMode==='ai'            ? (apiKeySet ? 'color:#059669' : 'color:#d97706') : ''">
                  <template v-if="deployMode==='drop_recreate'">소스 DDL 그대로 타겟에 적용</template>
                  <template v-else-if="deployMode==='rules'">내장 규칙으로 MSSQL → MySQL 자동 변환</template>
                  <template v-else-if="deployMode==='ai'">
                    <span v-if="apiKeySet" style="display:inline-flex;align-items:center;gap:4px">
                      <svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5" style="width:9px;height:9px"><polyline points="1.5,5 3.5,7.5 8.5,2"/></svg>
                      Claude AI 연결됨 — 변환 준비 완료
                    </span>
                    <span v-else>Claude AI 변환 (설정에서 API 키 등록 필요)</span>
                  </template>
                  <template v-else>변환 방식을 선택하세요</template>
                </span>

              </div>
            </div>

            <!-- 2컬럼 레이아웃 -->
            <div class="ddl-split" ref="splitEl">

              <!-- 왼쪽: 소스 DDL -->
              <div class="ddl-panel" :style="{flexBasis: srcWidth+'px', flexGrow:0, flexShrink:0}">
                <pre class="ddl-code">{{ sourceDDL || 'DDL 로드 버튼을 클릭하세요' }}</pre>
              </div>

              <!-- 드래그 리사이저 -->
              <div class="ddl-resizer" @mousedown="startResize">
                <div class="ddl-resizer-handle"></div>
              </div>

              <!-- 오른쪽: 타겟 스크립트 생성 -->
              <div class="ddl-panel tgt-panel" style="flex:1;min-width:0">
                <div v-if="false"><!-- deploy-mode-bar 제거됨: 툴바로 이동 --></div>

                <!-- 생성된 스크립트 -->
                <div v-if="generatedScript" class="generated-script-wrap">
                  <!-- 복사 + 배포 버튼 오버레이 (우측 상단) -->
                  <div class="tgt-action-btns">
                    <span v-if="deployResult" class="tgt-deploy-result" :class="deployResult.ok?'ok':'err'">
                      <svg v-if="deployResult.ok" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" style="width:10px;height:10px"><polyline points="1.5,6 4.5,9.5 10.5,2.5"/></svg>
                      <svg v-else viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" style="width:10px;height:10px"><line x1="2" y1="2" x2="10" y2="10"/><line x1="10" y1="2" x2="2" y2="10"/></svg>
                      {{ deployResult.ok ? '배포 완료' : '실패' }}
                    </span>
                    <button class="tgt-copy-btn" @click="copyGenScript" title="스크립트 복사">
                      <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:12px;height:12px">
                        <rect x="4" y="1" width="9" height="11" rx="1.5"/>
                        <path d="M10 1V0H1v11h3"/>
                      </svg>
                      복사
                    </button>
                    <button class="tgt-deploy-btn" @click="runDeploy" :disabled="deployLoading" title="타겟 DB에 배포">
                      <span v-if="deployLoading" class="spinner" style="width:10px;height:10px;border-width:1.5px"></span>
                      <svg v-else viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:12px;height:12px">
                        <path d="M7 1v8M4 6l3 4 3-4" stroke-linecap="round" stroke-linejoin="round"/>
                        <path d="M2 11h10" stroke-linecap="round"/>
                      </svg>
                      {{ deployLoading ? '배포 중...' : '타겟에 배포' }}
                    </button>
                  </div>
                  <div v-if="scriptWarnings.length" class="gs-warnings-bar">
                    <svg viewBox="0 0 14 14" fill="none" stroke="#d97706" stroke-width="1.5" style="width:12px;height:12px;flex-shrink:0;margin-top:2px"><path d="M7 1L13 12H1Z"/><line x1="7" y1="5" x2="7" y2="8"/><circle cx="7" cy="10.5" r=".5" fill="#d97706"/></svg>
                    <div class="gs-warn-lines">
                      <span v-for="(w,i) in scriptWarnings" :key="i" class="gs-warn-line">{{ w }}</span>
                    </div>
                  </div>
                  <pre class="ddl-code tgt">{{ generatedScript }}</pre>
                </div>

                <!-- 스크립트 미생성 안내 -->
                <div v-else-if="sourceDDL" class="ddl-empty-hint">
                  방식을 선택하고 ▶ 스크립트 생성을 클릭하세요
                </div>
                <div v-else class="ddl-empty-hint">
                  왼쪽에서 DDL을 먼저 로드하세요
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
                    <div class="chevron"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>
                  </div>
                  <input type="text" v-model="p.value" placeholder="테스트 값" style="flex:2"/>
                  <button class="mini-btn del" @click="testParams.splice(i,1)">✕</button>
                </div>
              </div>

              <!-- 실행 버튼 -->
              <div class="test-run-bar">
                <!-- 실행 대상 선택 -->
                <div class="oe-mode-tabs" style="margin-right:6px">
                  <button class="oe-mode-tab" :class="{active: testSide==='source'}" @click="testSide='source'">
                    소스 ({{ (curConn.dbType||'').toUpperCase() }})
                  </button>
                  <button class="oe-mode-tab" :class="{active: testSide==='target'}" @click="testSide='target'">
                    타겟 ({{ (otherConn.dbType||'').toUpperCase() }})
                  </button>
                </div>
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
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import axios from 'axios'
import PageHeader    from '@/components/layout/PageHeader.vue'
import ConnectPanel  from '@/components/common/ConnectPanel.vue'
import { useConnectorStore } from '@/store/connectorStore.js'
import { useAppStore }       from '@/store/appStore.js'
import { usePageStore }      from '@/store/pageStore.js'

const conn = useConnectorStore()
const app    = useAppStore()
const pStore = usePageStore()

const selSide   = ref('')  // 항상 '— DB 선택 —' 으로 시작
const loading   = ref(false)
const loadingDDL= ref(false)
const converting    = ref(false)
const testRunning   = ref(false)
const deployLoading   = ref(false)
const testSide        = ref('source')
const apiKeySet       = ref(false)   // Claude API 키 등록 여부   // 테스트 실행 대상: source | target
const deployResult    = ref(null)
const deployModalOpen = ref(false)
const deployMode      = ref('rules')

const generatedScript = ref('')
const scriptLoading   = ref(false)
const scriptWarnings  = ref([])

function selectMode(mode) {
  deployMode.value     = mode
  generatedScript.value = ''   // 방식 바꾸면 스크립트 초기화
  deployResult.value   = null
}

async function generateScript() {
  if (!sourceDDL.value) return
  scriptLoading.value   = true
  scriptWarnings.value  = []
  generatedScript.value = ''
  try {
    if (deployMode.value === 'drop_recreate') {
      // 원본 그대로
      generatedScript.value = sourceDDL.value
    } else if (deployMode.value === 'rules') {
      // 백엔드 규칙 변환 API 호출
      const { data } = await axios.post('/api/v1/schema/convert-object', {
        src_db:   curConn.value.dbType,
        tgt_db:   otherConn.value.dbType,
        type:     selObjType.value.toUpperCase(),
        name:     selObj.value.name,
        body:     sourceDDL.value,
        obj_type: selObjType.value.toUpperCase(),
        obj_name: selObj.value.name,
      })
      generatedScript.value = data.converted_ddl || data.converted || sourceDDL.value
      if (data.warnings?.length) scriptWarnings.value = data.warnings
    } else if (deployMode.value === 'ai') {
      // AI 변환
      const aiResult = await aiConvertDDL(sourceDDL.value, selObjType.value, selObj.value.name, curConn.value.database)
      if (aiResult.statements?.length) {
        generatedScript.value = aiResult.statements.join(";\n\n")
        if (aiResult.notes) scriptWarnings.value = [aiResult.notes]
      } else {
        app.notify('AI 변환 실패: ' + (aiResult.error || '결과 없음'), 'error')
      }
    }
  } catch(e) {
    app.notify('스크립트 생성 실패: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    scriptLoading.value = false
  }
}

async function copySrcDDL() {
  await navigator.clipboard.writeText(sourceDDL.value)
  app.notify('소스 DDL 복사', 'success')
}

async function copyGenScript() {
  await navigator.clipboard.writeText(generatedScript.value)
  app.notify('스크립트 복사', 'success')
}

function openDeployModal() {
  if (!sourceDDL.value) { app.notify('먼저 DDL을 로드하세요', 'warn'); return }
  deployResult.value    = null
  deployModalOpen.value = true
}

async function runDeploy() {
  deployLoading.value   = true
  deployModalOpen.value = false
  const tgt = otherConn.value
  try {
    if (deployMode.value === 'ai') {
      const aiResult = await aiConvertDDL(sourceDDL.value, selObjType.value, selObj.value.name, curConn.value.database)
      if (!aiResult.statements?.length) {
        deployResult.value = { ok:false, message:'AI 변환 실패: '+(aiResult.error||'결과 없음') }
        app.notify(deployResult.value.message, 'error'); return
      }
      const { data } = await axios.post('/api/v1/schema/execute-object', {
        db_type:tgt.dbType, host:tgt.host, port:tgt.port,
        username:tgt.username, password:tgt.password, database:tgt.database,
        obj_type:'DDL_CREATE', obj_sub_type:selObjType.value, obj_name:selObj.value.name,
        statements:aiResult.statements, ddl:sourceDDL.value, params:[],
      })
      deployResult.value = { ok:data.success, message:data.error||'완료' }
      app.notify(data.success?`${selObj.value.name} 배포 완료!`:'배포 실패: '+data.error, data.success?'success':'error')
      if (data.success) testSide.value = 'target'  // 배포 성공 → 테스트를 타겟으로 자동 전환
    } else {
      const scriptToUse = generatedScript.value || sourceDDL.value
      const { data } = await axios.post('/api/v1/schema/execute-object', {
        db_type:tgt.dbType, host:tgt.host, port:tgt.port,
        username:tgt.username, password:tgt.password, database:tgt.database,
        obj_type:'DDL_CREATE', obj_sub_type:selObjType.value, obj_name:selObj.value.name,
        statements:[scriptToUse],
        drop_first: true,
        ddl:scriptToUse, params:[],
      })
      deployResult.value = { ok:data.success, message:data.error||'완료' }
      app.notify(data.success?`${selObj.value.name} 배포 완료!`:'배포 실패: '+data.error, data.success?'success':'error')
    }
  } catch(e) {
    deployResult.value = { ok:false, message:e.response?.data?.detail||e.message }
    app.notify('배포 오류: '+deployResult.value.message, 'error')
  } finally {
    deployLoading.value = false
  }
}

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

async function aiConvertDDL(ddl, objType, objName, srcDb) {
  try {
    // convert-object-ai: obj_executor 공통 모듈 사용 (규칙+AI 통합)
    const {data} = await axios.post('/api/v1/schema/convert-object-ai', {
      ddl:        ddl,
      obj_type:   objType.toUpperCase(),
      obj_name:   objName,
      src_db:     curConn.value.dbType  || 'mssql',
      tgt_db:     otherConn.value.dbType || 'mysql',
      error_hint: '',
    })
    if (!data.converted_ddl) return { statements: [], error: data.warnings?.join(', ') || '변환 결과 없음', notes: '' }
    return { statements: [data.converted_ddl], notes: data.warnings?.join(' / ') || '', method: data.method }
  } catch(e) {
    const errMsg = e.response?.data?.detail || e.message
    return { statements: [], error: errMsg, notes: '' }
  }
}



function addParam() {
  testParams.value.push({ name:'p'+(testParams.value.length+1), type:'VARCHAR', value:'' })
}

async function runTest() {
  const c = testSide.value === 'target' ? otherConn.value : curConn.value
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

watch(selSide, v => {
  pStore.objectExplorer.selSide = v
  sessionStorage.setItem('oe_side', v)
})
watch(selObj, v => {
  pStore.objectExplorer.selObjName = v?.name || ''
  pStore.objectExplorer.selObjType = selObjType.value || ''
})

function switchSide(side) {
  // 같은 버튼 다시 클릭 시 무시
  if (selSide.value === side) return
  selSide.value = side
  selObj.value = null
  sourceDDL.value = ''
  generatedScript.value = ''
  objects.value = {}
  loadObjects()
}

function onSideChange() {
  switchSide(selSide.value)
}

const splitEl   = ref(null)
const srcWidth  = ref(0)   // 0 = 자동(50%)
let _resizing   = false
let _startX     = 0
let _startW     = 0

function startResize(e) {
  if (!splitEl.value) return
  _resizing = true
  _startX   = e.clientX
  // 현재 소스 패널 너비 측정
  const panels = splitEl.value.querySelectorAll('.ddl-panel')
  _startW = panels[0]?.getBoundingClientRect().width || splitEl.value.offsetWidth / 2
  srcWidth.value = _startW
  document.addEventListener('mousemove', onResize)
  document.addEventListener('mouseup',   stopResize)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}
function onResize(e) {
  if (!_resizing || !splitEl.value) return
  const total = splitEl.value.offsetWidth - 6  // 6px = resizer 너비
  const delta = e.clientX - _startX
  const newW  = Math.min(Math.max(_startW + delta, 120), total - 120)
  srcWidth.value = newW
}
function stopResize() {
  _resizing = false
  document.removeEventListener('mousemove', onResize)
  document.removeEventListener('mouseup',   stopResize)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

watch([() => activeTab.value, () => selObj.value], async ([tab]) => {
  if (tab === 'ddl') await initSplitWidth()
})

async function initSplitWidth() {
  await nextTick()
  await nextTick()  // 두 번 대기 — 탭 렌더링 완료 보장
  if (splitEl.value && splitEl.value.offsetWidth > 0) {
    srcWidth.value = Math.floor((splitEl.value.offsetWidth - 6) / 2)
  }
}

onMounted(async () => {
  // API 키 등록 여부 확인
  try {
    const { data } = await axios.get('/api/v1/settings/')
    apiKeySet.value = data.anthropic_api_key_set || false
  } catch {}
  await initSplitWidth()
})
</script>

<style scoped>
/* ── 배포 모달 ── */
/* ddl-panel CSS: DDL 섹션으로 통합 */
.oe-deploy-overlay { position:fixed; inset:0; background:rgba(0,0,0,.4); z-index:1000; display:flex; align-items:center; justify-content:center; }
.oe-deploy-modal { background:var(--bg-primary); border-radius:12px; box-shadow:0 8px 32px rgba(0,0,0,.2); width:420px; max-width:92vw; overflow:hidden; }
.oe-deploy-header { display:flex; align-items:center; justify-content:space-between; padding:14px 16px; border-bottom:0.5px solid var(--border-light); }
.oe-deploy-title { font-size:.9rem; font-weight:700; color:var(--text-primary); }
.oe-deploy-close { background:none; border:none; cursor:pointer; font-size:1rem; color:var(--text-tertiary); padding:2px 6px; border-radius:4px; }
.oe-deploy-close:hover { background:var(--bg-secondary); }
.oe-deploy-obj { display:flex; align-items:center; gap:7px; padding:10px 16px; background:var(--bg-secondary); font-size:.78rem; flex-wrap:wrap; }
.oe-obj-type { font-size:.65rem; font-weight:700; padding:1px 6px; border-radius:4px; background:rgba(37,99,235,.1); color:#1d4ed8; }
.oe-obj-name { font-weight:700; color:var(--text-primary); font-family:'Consolas','SF Mono',monospace; }
.oe-deploy-arrow { color:var(--text-tertiary); }
.oe-tgt-db { font-size:.72rem; color:var(--text-secondary); }
.oe-deploy-opts { padding:12px 16px; display:flex; flex-direction:column; gap:7px; }
.oe-deploy-opt { display:flex; align-items:flex-start; gap:10px; padding:10px 12px; border:0.5px solid var(--border-mid); border-radius:8px; cursor:pointer; transition:all .12s; }
.oe-deploy-opt input { margin-top:2px; accent-color:var(--accent-blue); flex-shrink:0; }
.oe-deploy-opt:hover { border-color:var(--accent-blue); background:rgba(37,99,235,.03); }
.oe-deploy-opt.active { border-color:var(--accent-blue); background:rgba(37,99,235,.06); }
.oe-opt-body { display:flex; flex-direction:column; gap:3px; }
.oe-opt-title { font-size:.8rem; font-weight:600; color:var(--text-primary); }
.oe-opt-desc { font-size:.7rem; color:var(--text-tertiary); line-height:1.5; }
.oe-deploy-footer { display:flex; justify-content:flex-end; gap:8px; padding:12px 16px; border-top:0.5px solid var(--border-light); }
.oe-cancel-btn { padding:6px 16px; border-radius:6px; border:0.5px solid var(--border-mid); background:var(--bg-secondary); color:var(--text-secondary); font-size:.78rem; font-family:var(--font); cursor:pointer; }
.oe-run-btn { padding:6px 18px; border-radius:6px; border:none; background:var(--accent-blue); color:#fff; font-size:.78rem; font-weight:600; font-family:var(--font); cursor:pointer; display:flex; align-items:center; }
.oe-run-btn:disabled { opacity:.5; cursor:not-allowed; }

.cfg-bar{display:flex;align-items:center;gap:10px;padding:12px 16px;margin-bottom:10px;flex-wrap:wrap}
.cfg-lbl{font-size:11.5px;color:var(--text-secondary);white-space:nowrap}
.db-type-badge{font-size:11px;font-weight:700;padding:3px 9px;border-radius:var(--radius-sm);background:var(--bg-info);color:var(--text-info);letter-spacing:.04em;border:0.5px solid var(--accent-blue);white-space:nowrap}
/* sel-wrap: 글로벌 스타일 사용 */
.sel-wrap select { background:var(--bg-secondary); border:0.5px solid var(--border-mid); border-radius:var(--radius-md); padding:5px 28px 5px 10px; font-size:12.5px; color:var(--text-primary); font-family:var(--font); width:100%; }
/* DB 선택 셀렉트 — PageHeader 슬롯용 */
.oe-db-select-wrap { position:relative; display:inline-flex; align-items:center; }
.oe-db-select {
  appearance:none; -webkit-appearance:none;
  background:var(--bg-primary);
  border:0.5px solid var(--border-mid);
  border-radius:var(--radius-md);
  padding:5px 28px 5px 10px;
  font-size:.75rem; font-weight:500;
  color:var(--text-primary); font-family:var(--font);
  cursor:pointer; min-width:140px;
  transition:border-color .12s;
}
.oe-db-select:focus { outline:none; border-color:var(--accent-blue); }
.oe-db-select:hover { border-color:var(--border-primary); }
.oe-db-chev {
  position:absolute; right:8px; top:50%; transform:translateY(-50%);
  pointer-events:none; width:11px; height:11px;
  color:var(--text-tertiary);
}
.btn{display:inline-flex;align-items:center;gap:5px;padding:6px 12px;border-radius:var(--radius-md);font-size:12px;font-weight:500;font-family:var(--font);cursor:pointer;transition:all .12s;border:0.5px solid var(--border-mid);background:transparent;color:var(--text-secondary)}
.btn:hover{background:var(--bg-secondary);color:var(--text-primary)}.btn:disabled{opacity:.5;cursor:not-allowed}
.btn-primary{background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue)}.btn-primary:hover{background:var(--accent-blue);color:#fff}

.explorer-layout{display:grid;grid-template-columns:200px 1fr;gap:6px;align-items:start;overflow:hidden}
.tree-panel{padding:0;overflow:hidden;max-height:calc(100vh-200px);overflow-y:auto}
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

.tab-bar{display:flex;border-bottom:0.5px solid var(--border-light);background:var(--bg-secondary);overflow:hidden;min-width:0}
.tab-btn{padding:9px 14px;font-size:12px;border:none;background:transparent;cursor:pointer;color:var(--text-secondary);font-family:var(--font);border-bottom:2px solid transparent;transition:all .12s}
.tab-btn:hover{color:var(--text-primary)}.tab-btn.active{color:var(--text-info);border-bottom-color:var(--accent-blue);font-weight:500}
.tab-info{margin-left:auto;padding:0 14px;font-size:11px;color:var(--text-tertiary);display:flex;align-items:center;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px}
/* DDL 탭 패널 제목 (탭바 내) */
.tab-panel-label {
  display:flex; align-items:center; gap:5px;
  padding:0 14px; font-size:.72rem; font-weight:700;
  border-left:0.5px solid var(--border-light); height:100%;
  flex:1;
}
.tab-panel-label.src { color:#2563eb; }
.tab-panel-label.tgt { color:#059669; border-left:0.5px solid var(--border-mid); }
.tab-panel-db { font-size:.62rem; font-weight:400; color:var(--text-tertiary); font-family:'Consolas','SF Mono',monospace; }

/* DDL */
.ddl-area { display:flex; flex-direction:column; height:calc(100vh - 220px); min-height:400px; overflow:hidden; }
.ddl-toolbar { display:flex; align-items:stretch; gap:8px; padding:0 8px; background:var(--bg-secondary); border-bottom:0.5px solid var(--border-light); }
.ddl-toolbar-left  { display:flex; align-items:center; gap:6px; padding:7px 8px; flex:1; min-width:0; }
.ddl-toolbar-spacer { flex:1; }
.ddl-toolbar-sep   { width:0.5px; background:var(--border-mid); margin:6px 0; flex-shrink:0; }
.ddl-toolbar-right { display:flex; align-items:center; gap:5px; padding:7px 8px; flex:1; min-width:0; overflow:hidden; flex-wrap:nowrap; }
/* 두 패널 사이 gap으로 시각적 분리 */
.ddl-split { display:flex; flex:1; min-height:0; gap:0; padding:0; background:var(--bg-secondary); overflow:hidden; width:100%; }
.ddl-panel { flex:1; min-width:0; display:flex; flex-direction:column; border-radius:0; overflow:hidden; border:0.5px solid var(--border-light); background:var(--bg-primary); }
.ddl-resizer { width:6px; flex-shrink:0; background:var(--bg-secondary); border-left:0.5px solid var(--border-light); border-right:0.5px solid var(--border-light); cursor:col-resize; display:flex; align-items:center; justify-content:center; transition:background .12s; z-index:10; }
.ddl-resizer:hover, .ddl-resizer:active { background:var(--accent-blue); }
.ddl-resizer-handle { width:2px; height:32px; background:var(--border-mid); border-radius:1px; pointer-events:none; }
.ddl-resizer:hover .ddl-resizer-handle, .ddl-resizer:active .ddl-resizer-handle { background:#fff; }
.ddl-panel:last-child { border-right:0.5px solid var(--border-light); }
.ddl-panel-hdr {
  display:flex; align-items:center; gap:6px;
  padding:7px 12px; flex-shrink:0;
  background:var(--bg-secondary); border-bottom:0.5px solid var(--border-light);
  height:34px; box-sizing:border-box;
}
.ddl-panel-label { font-size:.72rem; font-weight:700; }
.ddl-panel-hdr.src .ddl-panel-label { color:#2563eb; }
.ddl-panel-hdr.tgt .ddl-panel-label { color:#059669; }
.ddl-panel-db { font-size:.65rem; color:var(--text-tertiary); font-family:'Consolas','SF Mono',monospace; }
/* 소스 DDL 코드 */
.ddl-code {
  flex:1; margin:0; padding:12px;
  font-family:'Consolas','SF Mono',monospace; font-size:11.5px;
  color:var(--text-secondary); background:var(--bg-primary);
  overflow:auto; white-space:pre; border:none; outline:none;
  line-height:1.6;
}
/* 방식 선택 바 — 헤더와 같은 높이로 고정 */
.deploy-mode-bar {
  display:flex; align-items:center; gap:5px;
  padding:5px 10px; flex-shrink:0;
  border-bottom:0.5px solid var(--border-light);
  background:var(--bg-secondary);
  height:34px; box-sizing:border-box; flex-wrap:nowrap; overflow:hidden;
}
.deploy-mode-desc { font-size:.72rem; font-weight:500; color:var(--text-secondary); flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; padding-left:2px; }
/* 생성된 스크립트 영역 */
.generated-script-wrap { display:flex; flex-direction:column; flex:1; min-height:0; }
/* 소스 패널 오버레이 버튼 */
/* src-panel-actions: 툴바로 이동 */
.gen-script-btn {
  display:inline-flex; align-items:center; gap:5px;
  padding:6px 14px; border-radius:7px;
  background:var(--accent-blue); color:#fff;
  border:none; font-size:.76rem; font-weight:600; font-family:var(--font);
  cursor:pointer; box-shadow:0 2px 8px rgba(37,99,235,.35);
  transition:all .12s;
}
.gen-script-btn:hover   { background:#1d4ed8; box-shadow:0 3px 12px rgba(37,99,235,.45); }
.gen-script-btn:disabled { opacity:.5; cursor:not-allowed; }
.tgt-panel { position:relative; }
/* 타겟 창 우측 상단 버튼 그룹 */
.tgt-action-btns {
  position:absolute; top:8px; right:8px; z-index:10;
  display:flex; align-items:center; gap:5px;
}
.tgt-deploy-result {
  display:inline-flex; align-items:center; gap:3px;
  font-size:.68rem; font-weight:700; padding:3px 8px;
  border-radius:5px;
}
.tgt-deploy-result.ok  { background:rgba(22,163,74,.12); color:#15803d; }
.tgt-deploy-result.err { background:rgba(220,38,38,.1);  color:#dc2626; }
.tgt-copy-btn {
  display:inline-flex; align-items:center; gap:4px;
  padding:5px 10px; border-radius:6px;
  background:rgba(255,255,255,.9); color:var(--text-secondary);
  border:0.5px solid var(--border-mid);
  font-size:.7rem; font-weight:600; font-family:var(--font);
  cursor:pointer; transition:all .12s;
  box-shadow:0 1px 3px rgba(0,0,0,.08);
}
.tgt-copy-btn:hover { background:#fff; border-color:var(--accent-blue); color:var(--accent-blue); }
.tgt-deploy-btn {
  display:inline-flex; align-items:center; gap:5px;
  padding:5px 12px; border-radius:6px;
  background:var(--accent-blue); color:#fff;
  border:none; font-size:.73rem; font-weight:600; font-family:var(--font);
  cursor:pointer; transition:all .12s;
  box-shadow:0 2px 6px rgba(37,99,235,.3);
}
.tgt-deploy-btn:hover   { background:#1d4ed8; box-shadow:0 3px 10px rgba(37,99,235,.4); }
.tgt-deploy-btn:disabled { opacity:.5; cursor:not-allowed; }
.gen-copy-btn {
  display:inline-flex; align-items:center; gap:4px;
  padding:5px 10px; border-radius:6px;
  background:rgba(22,163,74,.15); color:#15803d;
  border:0.5px solid rgba(22,163,74,.3);
  font-size:.7rem; font-weight:600; font-family:var(--font);
  cursor:pointer; transition:all .12s;
}
.gen-copy-btn:hover { background:rgba(22,163,74,.25); }
.gs-warnings-bar { display:flex; align-items:flex-start; gap:8px; padding:6px 12px; background:rgba(245,158,11,.07); border-bottom:0.5px solid rgba(245,158,11,.2); flex-shrink:0; max-height:80px; overflow-y:auto; }
.gs-warn-lines { display:flex; flex-direction:column; gap:2px; flex:1; min-width:0; }
.gs-warn-line { font-size:.67rem; color:#b45309; line-height:1.5; word-break:break-word; white-space:pre-wrap; }
/* 생성된 코드 */
.ddl-code.tgt {
  background:rgba(22,163,74,.03); border:none;
  flex:1; margin:0; padding:36px 12px 12px 12px;
  font-family:'Consolas','SF Mono',monospace; font-size:11.5px;
  color:var(--text-secondary); overflow:auto; white-space:pre; line-height:1.6;
}
/* 배포 버튼 바 */
.deploy-action-bar {
  display:flex; align-items:center; justify-content:flex-end; gap:8px;
  padding:8px 12px; flex-shrink:0;
  border-top:0.5px solid var(--border-light);
  background:var(--bg-secondary);
}
.ddl-empty-hint {
  flex:1; display:flex; align-items:center; justify-content:center;
  font-size:.75rem; color:var(--text-tertiary); padding:30px; text-align:center;
}
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
.ddl-side-label { font-size:.68rem; font-weight:700; display:flex; align-items:center; gap:3px; flex-shrink:0; }
.ddl-side-label.src { color:#2563eb; }
.ddl-side-label.tgt { color:#059669; }
.ddl-side-db { font-size:.62rem; font-weight:400; font-family:'Consolas','SF Mono',monospace; opacity:.8; }
/* 소스/타겟 버튼 — Schema.vue와 동일 */
.sc-side-tabs { display:flex; border:0.5px solid var(--border-mid); border-radius:6px; overflow:hidden; }
.sc-side-tab  { padding:3px 14px; font-size:.75rem; font-weight:600; font-family:var(--font); background:transparent; border:none; cursor:pointer; color:var(--text-tertiary); transition:all .12s; }
.sc-side-tab.on { background:var(--accent-blue); color:#fff; }
.oe-mode-tabs { display:flex; background:var(--bg-tertiary,#f1f5f9); border-radius:7px; padding:2px; gap:2px; flex-shrink:0; }
.oe-mode-tab {
  padding:4px 12px; border-radius:5px; border:none;
  font-size:.75rem; font-weight:600; font-family:var(--font);
  cursor:pointer; color:var(--text-tertiary); background:transparent;
  transition:all .15s; white-space:nowrap;
}
.oe-mode-tab:hover { color:var(--text-primary); background:rgba(0,0,0,.06); }
.oe-mode-tab.active {
  background:var(--bg-primary);
  color:var(--accent-blue);
  box-shadow:0 1px 4px rgba(0,0,0,.12);
}
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
