<template>
  <div>
    <div class="page-title">변환 Diff 미리보기</div>
    <div class="page-desc">소스 테이블을 타겟 DB로 변환했을 때의 DDL 차이를 확인합니다</div>

    <div class="card" style="margin-bottom:12px;padding:12px 16px">
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
        <div style="display:flex;align-items:center;gap:6px">
          <span style="font-size:11.5px;color:var(--text-secondary)">소스</span>
          <span class="db-badge src">{{ connector.source.database||'미연결' }}</span>
        </div>
        <span style="color:var(--text-tertiary)">→</span>
        <div style="display:flex;align-items:center;gap:6px">
          <span style="font-size:11.5px;color:var(--text-secondary)">타겟</span>
          <span class="db-badge tgt">{{ connector.target.database||'미연결' }}</span>
        </div>
        <div class="sel-wrap" style="min-width:160px">
          <select v-model="selTable" @change="loadDiff">
            <option value="">테이블 선택...</option>
            <option v-for="t in tables" :key="t.table_name" :value="t.table_name">{{ t.table_name }}</option>
          </select>
          <div class="chevron"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>
        </div>
        <button class="btn" @click="loadTables" style="font-size:11.5px;padding:5px 12px">
          <span v-if="loading" class="spinner" style="width:12px;height:12px;display:inline-block;margin-right:4px"></span>
          {{ loading?'조회 중...':'테이블 목록 로드' }}
        </button>
      </div>
    </div>

    <div v-if="selTable && diffData" class="card" style="padding:0;overflow:hidden">
      <!-- 경고 배너 -->
      <div v-if="diffData.warnings?.length" style="padding:10px 14px;background:var(--bg-warning);border-bottom:0.5px solid var(--border-light)">
        <div v-for="w in diffData.warnings" :key="w" style="display:flex;align-items:center;gap:6px;font-size:11.5px;color:var(--text-warning)">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:12px;height:12px;flex-shrink:0"><path d="M8 2L14 14H2L8 2z"/><line x1="8" y1="7" x2="8" y2="10"/></svg>
          {{ w }}
        </div>
      </div>

      <!-- Diff 헤더 -->
      <div class="diff-header">
        <div class="diff-col src">소스 ({{ connector.source.dbType }}) — {{ selTable }}</div>
        <div class="diff-col tgt">타겟 ({{ connector.target.dbType }}) — {{ selTable }}</div>
      </div>

      <!-- Diff 본문 -->
      <div class="diff-body">
        <div class="diff-side">
          <div v-for="(l,i) in srcLines" :key="i" class="diff-line" :class="l.cls">{{ l.text }}</div>
        </div>
        <div class="diff-side">
          <div v-for="(l,i) in tgtLines" :key="i" class="diff-line" :class="l.cls">{{ l.text }}</div>
        </div>
      </div>

      <!-- 범례 -->
      <div style="padding:8px 14px;background:var(--bg-secondary);border-top:0.5px solid var(--border-light);display:flex;gap:14px;font-size:11px">
        <span style="display:flex;align-items:center;gap:4px"><span style="width:12px;height:12px;background:#faeeda;border-radius:2px;display:inline-block"></span>변환됨</span>
        <span style="display:flex;align-items:center;gap:4px"><span style="width:12px;height:12px;background:#eaf3de;border-radius:2px;display:inline-block"></span>추가됨</span>
        <span style="display:flex;align-items:center;gap:4px"><span style="width:12px;height:12px;background:#fcebeb;border-radius:2px;display:inline-block"></span>제거됨</span>
      </div>
    </div>

    <div v-else-if="!selTable" class="card empty-state">테이블을 선택하면 DDL 변환 결과를 확인할 수 있습니다</div>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { useConnectorStore } from '@/store/connectorStore.js'
const connector = useConnectorStore()
const tables=ref([]); const selTable=ref(''); const diffData=ref(null); const loading=ref(false)

async function loadTables(){
  const c=connector.source; if(!c.host||!c.database) return
  loading.value=true
  try{const {data}=await axios.get('/api/v1/schema/tables',{params:{side:'source',db_type:c.dbType,host:c.host,port:c.port,username:c.username,password:c.password,database:c.database}});tables.value=data}
  catch(e){console.error(e)}finally{loading.value=false}
}

async function loadDiff(){
  if(!selTable.value) return
  try{
    // 연결 정보를 먼저 백엔드에 저장 (_conns 업데이트)
    const src=connector.source; const tgt=connector.target
    if(src.host){
      await axios.post('/api/v1/schema/connection',{side:'source',db_type:src.dbType,host:src.host,port:src.port,username:src.username,password:src.password,database:src.database})
    }
    if(tgt.host){
      await axios.post('/api/v1/schema/connection',{side:'target',db_type:tgt.dbType,host:tgt.host,port:tgt.port,username:tgt.username,password:tgt.password,database:tgt.database})
    }
    const {data}=await axios.get('/api/v1/schema/diff',{params:{src:'source',tgt:'target',table:selTable.value}})
    diffData.value=data
  }catch(e){console.error(e)}
}

const srcLines=computed(()=>{
  if(!diffData.value) return []
  return buildDiffLines(diffData.value.src_ddl, 'src')
})
const tgtLines=computed(()=>{
  if(!diffData.value) return []
  return buildDiffLines(diffData.value.tgt_ddl, 'tgt')
})

function buildDiffLines(ddl, side){
  if(!ddl) return []
  const pairs=[
    {src:'INT AUTO_INCREMENT',tgt:'INT IDENTITY(1,1)'},
    {src:'VARCHAR(',tgt:'NVARCHAR('},
    {src:'TINYINT(1)',tgt:'BIT'},
    {src:'DATETIME',tgt:'DATETIME2'},
    {src:'LONGTEXT',tgt:'NVARCHAR(MAX)'},
    {src:'LONGBLOB',tgt:'VARBINARY(MAX)'},
  ]
  return ddl.split('\n').map(line=>{
    const l=line.trim()
    let cls=''
    for(const p of pairs){
      if(side==='src'&&l.includes(p.src)) cls='changed'
      if(side==='tgt'&&l.includes(p.tgt)) cls='added'
    }
    return {text:line, cls}
  })
}

onMounted(()=>{ if(connector.source.status==='ok') loadTables() })
</script>
<style scoped>
.db-badge{font-size:11px;font-weight:500;padding:2px 8px;border-radius:6px}
.db-badge.src{background:var(--bg-info);color:var(--text-info)}
.db-badge.tgt{background:var(--bg-success);color:var(--text-success)}
.sel-wrap{position:relative}.sel-wrap select{width:100%;appearance:none;-webkit-appearance:none;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:var(--radius-md);padding:7px 28px 7px 10px;font-size:12px;color:var(--text-primary);cursor:pointer;font-family:var(--font)}.sel-wrap select:focus{outline:none;border-color:var(--accent-blue)}.chevron{position:absolute;right:9px;top:50%;transform:translateY(-50%);pointer-events:none;color:var(--text-tertiary)}.chevron svg{width:11px;height:11px;display:block}
.diff-header{display:flex;border-bottom:0.5px solid var(--border-light);background:var(--bg-secondary)}
.diff-col{flex:1;padding:8px 12px;font-size:11.5px;font-weight:500;border-right:0.5px solid var(--border-light)}
.diff-col:last-child{border-right:none}
.diff-col.src{color:#185fa5}.diff-col.tgt{color:#3b6d11}
.diff-body{display:grid;grid-template-columns:1fr 1fr}
.diff-side{padding:10px 12px;font-family:'Consolas','SF Mono',monospace;font-size:11.5px;overflow-x:auto}
.diff-side:first-child{border-right:0.5px solid var(--border-light)}
.diff-line{padding:2px 6px;line-height:1.7;color:var(--text-secondary);border-radius:2px;white-space:pre}
.diff-line.changed{background:#faeeda;color:#854f0b}
.diff-line.added{background:#eaf3de;color:#3b6d11}
.diff-line.removed{background:#fcebeb;color:#a32d2d;text-decoration:line-through}
</style>
