<template>
  <div>
    <div class="page-title">스키마 탐색기</div>
    <div class="page-desc">소스 DB 스키마를 탐색하고 컬럼 구조를 확인합니다</div>

    <!-- DB 선택 -->
    <div class="card" style="margin-bottom:10px;padding:12px 16px">
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
        <div style="display:flex;align-items:center;gap:6px">
          <span style="font-size:11.5px;color:var(--text-secondary)">데이터베이스</span>
          <div class="sel-wrap" style="min-width:160px">
            <select v-model="selDb" @change="onDbChange">
              <option value="source">소스 DB ({{ connector.source.database||'미연결' }})</option>
              <option value="target">타겟 DB ({{ connector.target.database||'미연결' }})</option>
            </select>
            <div class="chevron"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:6px">
          <span style="font-size:11.5px;color:var(--text-secondary)">연결 상태</span>
          <span class="pill" :class="connStatus==='ok'?'pill-ok':'pill-err'">{{ connStatus==='ok'?'연결됨':'미연결' }}</span>
        </div>
        <button class="btn" style="font-size:11.5px;padding:5px 12px" @click="loadTables">
          <span v-if="loadingTbl" class="spinner" style="width:12px;height:12px;display:inline-block;margin-right:4px"></span>
          {{ loadingTbl?'조회 중...':'↻ 테이블 목록 새로고침' }}
        </button>
        <input type="text" v-model="tblSearch" placeholder="테이블 검색..." style="width:160px;padding:5px 10px;font-size:12px"/>
      </div>
    </div>

    <div class="schema-layout">
      <!-- 좌측 트리 -->
      <div class="card tree-panel">
        <div style="padding:10px 12px;border-bottom:0.5px solid var(--border-light)">
          <div style="font-size:12px;font-weight:500;color:var(--text-primary)">
            {{ curDbInfo.database || '데이터베이스 선택' }}
          </div>
          <div style="font-size:10.5px;color:var(--text-tertiary)">{{ curDbInfo.dbType }} · {{ curDbInfo.host }}</div>
        </div>

        <div v-if="loadingTbl" class="empty-state" style="padding:20px">
          <span class="spinner" style="width:16px;height:16px;display:inline-block"></span>
        </div>
        <div v-else-if="tableError" class="empty-state" style="padding:16px;color:var(--text-danger);font-size:11.5px">{{ tableError }}</div>
        <template v-else>
          <div class="tree-sec-label" @click="openTbls=!openTbls">
            <svg :style="{transform:openTbls?'rotate(90deg)':'',transition:'transform .2s'}" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px"><polyline points="3,2 9,6 3,10"/></svg>
            테이블 ({{ filteredTables.length }})
          </div>
          <template v-if="openTbls">
            <div v-for="t in filteredTables" :key="t.table_name"
                 class="tree-item" :class="{sel:selTable===t.table_name}"
                 @click="selectTable(t.table_name)">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px;flex-shrink:0;opacity:.5"><rect x="1" y="3" width="14" height="10" rx="1"/><line x1="1" y1="6" x2="15" y2="6"/></svg>
              <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ t.table_name }}</span>
              <span class="tree-rows">{{ fmtRows(t.row_count) }}</span>
            </div>
          </template>
        </template>
      </div>

      <!-- 우측 상세 -->
      <div class="detail-area">
        <div v-if="!selTable" class="card empty-state" style="min-height:300px;display:flex;align-items:center;justify-content:center">
          왼쪽에서 테이블을 선택하세요
        </div>

        <template v-else>
          <!-- 탭 -->
          <div class="card" style="padding:0;overflow:hidden">
            <div class="tab-bar">
              <button v-for="tab in tabs" :key="tab.v" class="tab-btn" :class="{active:activeTab===tab.v}" @click="activeTab=tab.v">{{ tab.l }}</button>
              <span style="margin-left:auto;padding:0 12px;font-size:11.5px;color:var(--text-tertiary);display:flex;align-items:center">
                {{ selTable }} · {{ selCols.length }}개 컬럼
              </span>
            </div>

            <!-- 컬럼 탭 -->
            <template v-if="activeTab==='cols'">
              <div v-if="loadingCols" class="empty-state" style="padding:20px">
                <span class="spinner" style="width:16px;height:16px;display:inline-block"></span>
              </div>
              <table v-else class="col-tbl">
                <thead><tr><th>컬럼명</th><th>타입</th><th>Null</th><th>기본값</th><th>PK</th><th>AI</th><th>비고</th></tr></thead>
                <tbody>
                  <tr v-for="c in selCols" :key="c.name">
                    <td style="font-family:'Consolas','SF Mono',monospace;font-weight:500">{{ c.name }}</td>
                    <td><span class="type-chip src">{{ c.data_type }}</span></td>
                    <td><span :style="{color:c.nullable?'var(--text-tertiary)':'var(--text-danger)'}">{{ c.nullable?'YES':'NO' }}</span></td>
                    <td style="font-size:11px;color:var(--text-tertiary);font-family:'Consolas','SF Mono',monospace">{{ c.default||'—' }}</td>
                    <td>{{ c.is_pk?'🔑':'' }}</td>
                    <td>{{ c.is_identity?'✓':'' }}</td>
                    <td style="font-size:11px;color:var(--text-tertiary)">{{ c.comment||'' }}</td>
                  </tr>
                </tbody>
              </table>
            </template>

            <!-- DDL 탭 -->
            <div v-if="activeTab==='ddl'" style="padding:14px">
              <div class="ddl-toolbar">
                <button class="act-btn" @click="copyDdl">📋 복사</button>
              </div>
              <pre class="code-block" style="white-space:pre-wrap;margin-top:8px">{{ generatedDdl }}</pre>
            </div>

            <!-- 인덱스 탭 -->
            <div v-if="activeTab==='idx'" style="padding:14px">
              <div class="empty-state" v-if="!selCols.length">인덱스 정보 없음</div>
              <table v-else class="col-tbl">
                <thead><tr><th>인덱스명</th><th>컬럼</th><th>유형</th><th>고유</th></tr></thead>
                <tbody>
                  <tr><td style="font-family:'Consolas','SF Mono',monospace">PRIMARY</td><td>{{ selCols.find(c=>c.is_pk)?.name||'id' }}</td><td>BTREE</td><td>✓</td></tr>
                  <tr v-for="c in selCols.filter(c=>!c.is_pk&&!c.nullable)" :key="c.name">
                    <td style="font-family:'Consolas','SF Mono',monospace">idx_{{ selTable }}_{{ c.name }}</td>
                    <td>{{ c.name }}</td><td>BTREE</td><td></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { useConnectorStore } from '@/store/connectorStore.js'
import { useAppStore } from '@/store/appStore.js'
const connector=useConnectorStore(); const app=useAppStore()
const selDb=ref('source'); const selTable=ref(''); const tblSearch=ref('')
const tables=ref([]); const selCols=ref([])
const loadingTbl=ref(false); const loadingCols=ref(false)
const tableError=ref(''); const openTbls=ref(true); const activeTab=ref('cols')
const tabs=[{v:'cols',l:'컬럼 구조'},{v:'ddl',l:'DDL 생성'},{v:'idx',l:'인덱스'}]
const fmtRows=n=>n>=1e6?(n/1e6).toFixed(1)+'M':n>=1e3?Math.round(n/1e3)+'K':String(n||0)
const curDbInfo=computed(()=>{const c=connector[selDb.value];return{database:c.database,dbType:c.dbType,host:c.host}})
const connStatus=computed(()=>connector[selDb.value].status)
const filteredTables=computed(()=>tables.value.filter(t=>t.table_name.toLowerCase().includes(tblSearch.value.toLowerCase())))

const generatedDdl=computed(()=>{
  if(!selCols.value.length) return ''
  const cols=selCols.value.map(c=>{
    const null_=c.nullable?'NULL':'NOT NULL'
    if(c.is_identity) return `  \`${c.name}\` INT AUTO_INCREMENT ${null_}`
    return `  \`${c.name}\` ${c.data_type} ${null_}`
  }).join(',\n')
  const pk=selCols.value.find(c=>c.is_pk)
  const pkLine=pk?`,\n  PRIMARY KEY (\`${pk.name}\`)`:''
  return `CREATE TABLE \`${selTable.value}\` (\n${cols}${pkLine}\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;`
})

async function loadTables(){
  const c=connector[selDb.value]
  if(!c.host||!c.database){tableError.value='DB 연결 정보가 없습니다. 커넥터 관리에서 연결 테스트를 먼저 하세요.';return}
  loadingTbl.value=true; tableError.value=''; tables.value=[]
  try{
    const {data}=await axios.get('/api/v1/schema/tables',{params:{side:selDb.value,db_type:c.dbType,host:c.host,port:c.port,username:c.username,password:c.password,database:c.database}})
    tables.value=data
    if(!data.length) tableError.value=`"${c.database}" 에 테이블이 없습니다`
  }catch(e){tableError.value=e.response?.data?.detail||e.message}
  finally{loadingTbl.value=false}
}

async function selectTable(name){
  selTable.value=name; activeTab.value='cols'
  const c=connector[selDb.value]
  loadingCols.value=true; selCols.value=[]
  try{
    const {data}=await axios.get(`/api/v1/schema/source/tables/${name}`,{params:{db_type:c.dbType,host:c.host,port:c.port,username:c.username,password:c.password,database:c.database}})
    selCols.value=data.columns||[]
  }catch(e){app.notify('컬럼 조회 실패: '+e.message,'error')}
  finally{loadingCols.value=false}
}

function onDbChange(){selTable.value='';tables.value=[];loadTables()}
function copyDdl(){navigator.clipboard?.writeText(generatedDdl.value);app.notify('DDL이 클립보드에 복사됐습니다','success')}

onMounted(()=>{if(connector.source.status==='ok') loadTables()})
</script>
<style scoped>
.schema-layout{display:grid;grid-template-columns:220px 1fr;gap:10px;align-items:start}
.tree-panel{padding:0;overflow:hidden;max-height:calc(100vh - 280px);overflow-y:auto}
.tree-sec-label{display:flex;align-items:center;gap:6px;padding:8px 12px;font-size:11.5px;font-weight:500;color:var(--text-secondary);cursor:pointer;user-select:none;border-bottom:0.5px solid var(--border-light)}
.tree-sec-label:hover{background:var(--bg-secondary)}
.tree-item{display:flex;align-items:center;gap:6px;padding:5px 12px 5px 20px;font-size:11.5px;color:var(--text-secondary);cursor:pointer;transition:all .1s}
.tree-item:hover{background:var(--bg-secondary);color:var(--text-primary)}
.tree-item.sel{background:var(--bg-info);color:var(--text-info)}
.tree-rows{margin-left:auto;font-size:10px;color:var(--text-tertiary);flex-shrink:0}
.detail-area{}
.tab-bar{display:flex;border-bottom:0.5px solid var(--border-light);background:var(--bg-secondary)}
.tab-btn{padding:9px 14px;font-size:12px;border:none;background:transparent;cursor:pointer;color:var(--text-secondary);font-family:var(--font);border-bottom:2px solid transparent;transition:all .12s}
.tab-btn:hover{color:var(--text-primary)}
.tab-btn.active{color:var(--text-info);border-bottom-color:var(--accent-blue);font-weight:500}
.col-tbl{width:100%;border-collapse:collapse}
.col-tbl th{background:var(--bg-secondary);font-size:11px;font-weight:500;color:var(--text-tertiary);padding:7px 10px;text-align:left;border-bottom:0.5px solid var(--border-light)}
.col-tbl td{padding:7px 10px;font-size:12px;border-bottom:0.5px solid var(--border-light);color:var(--text-primary)}
.col-tbl tr:last-child td{border-bottom:none}
.col-tbl tr:hover td{background:var(--bg-secondary)}
.type-chip{display:inline-block;font-size:11px;padding:2px 7px;border-radius:4px;font-family:'Consolas','SF Mono',monospace;font-weight:500}
.type-chip.src{background:var(--bg-info);color:var(--text-info)}
.sel-wrap{position:relative}.sel-wrap select{width:100%;appearance:none;-webkit-appearance:none;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:var(--radius-md);padding:7px 28px 7px 10px;font-size:12.5px;color:var(--text-primary);cursor:pointer;font-family:var(--font)}.sel-wrap select:focus{outline:none;border-color:var(--accent-blue)}.chevron{position:absolute;right:9px;top:50%;transform:translateY(-50%);pointer-events:none;color:var(--text-tertiary)}.chevron svg{width:11px;height:11px;display:block}
.ddl-toolbar{display:flex;gap:6px;margin-bottom:6px}
</style>
