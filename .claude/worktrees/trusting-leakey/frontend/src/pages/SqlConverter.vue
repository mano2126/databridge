<template>
  <div class="sql-converter">
    <div class="page-title">SQL 쿼리 변환기</div>
    <div class="page-desc">텍스트 입력, 파일 업로드, 또는 <b>폴더 일괄 변환</b>으로 SQL 방언을 변환합니다</div>

    <!-- DB 선택 바 -->
    <div class="card cfg-bar">
      <div class="cfg-pair">
        <span class="cfg-label">소스 DB</span>
        <div class="sel-wrap">
          <select v-model="srcDb" @change="clearAll">
            <option v-for="d in allDbs" :key="d.v" :value="d.v">{{ d.n }}</option>
          </select><Chev/>
        </div>
      </div>
      <div class="arrow-ico">
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" style="width:18px;height:18px"><line x1="2" y1="10" x2="18" y2="10"/><polyline points="12,4 18,10 12,16"/></svg>
      </div>
      <div class="cfg-pair">
        <span class="cfg-label">타겟 DB</span>
        <div class="sel-wrap">
          <select v-model="tgtDb" @change="clearAll">
            <option v-for="d in allDbs" :key="d.v" :value="d.v">{{ d.n }}</option>
          </select><Chev/>
        </div>
      </div>
      <div class="rule-badge">변환 규칙 <b>{{ ruleCount }}</b>개</div>
      <div style="margin-left:auto;display:flex;gap:5px">
        <button class="mode-btn" :class="{active:mode==='text'}"  @click="mode='text'">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><rect x="1" y="1" width="12" height="12" rx="1"/><line x1="3" y1="5" x2="11" y2="5"/><line x1="3" y1="8" x2="9" y2="8"/></svg> 텍스트
        </button>
        <button class="mode-btn" :class="{active:mode==='file'}"  @click="mode='file'">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><path d="M2 1h7l3 3v9H2z"/><polyline points="9,1 9,4 12,4"/></svg> 파일
        </button>
        <button class="mode-btn" :class="{active:mode==='folder'}" @click="mode='folder'">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><path d="M1 3h5l1 2h6v7H1z"/></svg> 폴더
        </button>
      </div>
    </div>

    <!-- ══ 텍스트 모드 ══ -->
    <template v-if="mode==='text'">
      <div class="editor-layout">
        <div class="editor-panel">
          <div class="ep-head src">
            <span>소스 ({{ srcDb }})</span>
            <div style="display:flex;gap:5px">
              <button class="mini-btn" @click="loadSample">샘플</button>
              <button class="mini-btn" @click="textSrc=''">지우기</button>
            </div>
          </div>
          <textarea v-model="textSrc" class="sql-ed" :placeholder="`${srcDb} SQL/DDL을 붙여넣기...`" spellcheck="false"/>
          <div class="ep-foot">{{ lineCount(textSrc) }}줄 · {{ textSrc.length }}자</div>
        </div>
        <div class="mid-panel">
          <button class="conv-btn" @click="doConvertText" :disabled="converting||!textSrc.trim()">
            <span v-if="converting" class="spinner" style="width:13px;height:13px;border-top-color:#fff;display:inline-block"></span>
            <svg v-else viewBox="0 0 14 14" fill="none" stroke="white" stroke-width="2" style="width:14px;height:14px"><line x1="2" y1="7" x2="12" y2="7"/><polyline points="8,3 12,7 8,11"/></svg>
            <span style="font-size:9px;font-weight:700">변환</span>
          </button>
          <div v-if="textChanges.length" class="change-cnt ok">{{ textChanges.length }}건 변경</div>
          <div v-if="textWarnings.length" class="change-cnt warn">{{ textWarnings.length }}건 확인</div>
        </div>
        <div class="editor-panel">
          <div class="ep-head tgt">
            <span>결과 ({{ tgtDb }})</span>
            <div style="display:flex;gap:5px">
              <button class="mini-btn" @click="copyText" :disabled="!textResult">복사</button>
              <button class="mini-btn" @click="downloadText" :disabled="!textResult">저장</button>
            </div>
          </div>
          <textarea v-model="textResult" class="sql-ed result" readonly spellcheck="false"/>
          <div class="ep-foot">{{ lineCount(textResult) }}줄 · {{ textResult.length }}자</div>
        </div>
      </div>
      <div v-if="textChanges.length||textWarnings.length" class="card" style="margin-top:8px;padding:10px 14px">
        <div class="change-grid">
          <div v-for="c in textChanges" :key="c" class="ctag ok">✓ {{ c }}</div>
          <div v-for="w in textWarnings" :key="w" class="ctag warn">⚠ {{ w }}</div>
        </div>
      </div>
    </template>

    <!-- ══ 파일 모드 ══ -->
    <template v-if="mode==='file'">
      <div class="card drop-zone" :class="{drag:isDragging}"
           @dragover.prevent="isDragging=true" @dragleave="isDragging=false" @drop.prevent="onDrop">
        <svg viewBox="0 0 44 44" fill="none" stroke="currentColor" stroke-width="1.4" style="width:36px;height:36px;color:var(--text-tertiary)">
          <path d="M6 34V10l8-8h22v32H6z"/><polyline points="14,2 14,10 6,10"/>
          <line x1="14" y1="22" x2="30" y2="22"/><polyline points="22,16 22,28"/>
        </svg>
        <div class="dz-main">.sql / .ddl 파일을 드래그하거나 클릭하여 선택</div>
        <div class="dz-sub">여러 파일 동시 선택 · UTF-8 인코딩 권장</div>
        <input type="file" ref="fileInput" accept=".sql,.ddl,.txt" multiple style="display:none" @change="onFileSelect"/>
        <button class="btn btn-primary" style="margin-top:10px" @click="$refs.fileInput.click()">파일 선택</button>
      </div>
      <div v-if="files.length" class="card" style="margin-top:8px">
        <div class="sec-header">
          파일 목록 ({{ files.length }}개)
          <div style="display:flex;gap:6px">
            <button class="btn btn-primary" @click="doConvertFiles" :disabled="converting">
              <span v-if="converting" class="spinner" style="width:12px;height:12px;border-top-color:#fff;display:inline-block"></span>
              {{ converting?'변환 중...':'일괄 변환' }}
            </button>
            <button class="btn icon-only-btn" @click="files=[];fileResults=[]" title="초기화">
              <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:11px;height:11px"><line x1="2" y1="2" x2="12" y2="12"/><line x1="12" y1="2" x2="2" y2="12"/></svg>
            </button>
          </div>
        </div>
        <div v-for="(f,i) in files" :key="i" class="file-row">
          <span class="f-ico">📄</span>
          <span class="f-name">{{ f.name }}</span>
          <span class="f-size">{{ fmtSize(f.size) }}</span>
          <span v-if="fileResults[i]" class="f-badge ok">{{ fileResults[i].changes.length }}건</span>
          <span v-if="fileResults[i]?.warnings.length" class="f-badge warn">⚠{{ fileResults[i].warnings.length }}</span>
          <button class="mini-btn del" @click="files.splice(i,1);fileResults.splice(i,1)">✕</button>
        </div>
      </div>
      <template v-if="fileResults.length">
        <div class="card" style="margin-top:8px">
          <div class="sec-header">
            변환 결과
            <button class="btn btn-primary" @click="downloadZip" title="ZIP 파일로 다운로드">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" style="width:12px;height:12px"><path d="M8 2v8M5 7l3 3 3-3"/><path d="M3 12h10"/></svg>
            </button>
          </div>
          <div class="sum-row">
            <div class="sum-kpi"><div class="sk-n info">{{ fileResults.length }}</div><div class="sk-l">변환 파일</div></div>
            <div class="sum-kpi"><div class="sk-n ok">{{ fileResults.reduce((s,r)=>s+r.changes.length,0) }}</div><div class="sk-l">총 변경</div></div>
            <div class="sum-kpi"><div class="sk-n warn">{{ fileResults.reduce((s,r)=>s+r.warnings.length,0) }}</div><div class="sk-l">확인 필요</div></div>
          </div>
          <div v-for="(r,i) in fileResults" :key="i" class="result-row" @click="r._open=!r._open">
            <span class="f-ico">📄</span>
            <span class="f-name">{{ r.filename }}</span>
            <span class="f-badge ok">{{ r.changes.length }}건</span>
            <span v-if="r.warnings.length" class="f-badge warn">⚠{{ r.warnings.length }}</span>
            <svg :style="{transform:r._open?'rotate(90deg)':'',transition:'transform .2s'}" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px;margin-left:auto"><polyline points="3,2 9,6 3,10"/></svg>
          </div>
        </div>
      </template>
    </template>

    <!-- ══ 폴더 모드 ══ -->
    <template v-if="mode==='folder'">
      <div class="card folder-panel">
        <div class="folder-layout">
          <!-- 소스 폴더 -->
          <div class="folder-box">
            <div class="fb-label">소스 폴더</div>
            <div class="fb-path" :class="{selected:srcFolder}">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px;flex-shrink:0"><path d="M1 3h5l1 2h8v9H1z"/></svg>
              <span>{{ srcFolder || '폴더를 선택하세요' }}</span>
            </div>
            <button class="btn btn-primary" @click="pickSrcFolder">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><path d="M1 3h5l1 2h8v9H1z"/></svg>
              소스 폴더 선택
            </button>
            <div v-if="folderFiles.length" class="folder-file-list">
              <div class="ffl-header">
                SQL 파일 ({{ folderFiles.length }}개)
                <div style="display:flex;gap:5px">
                  <button class="mini-btn" @click="selAll">전체 선택</button>
                  <button class="mini-btn" @click="selNone">해제</button>
                </div>
              </div>
              <label v-for="(f,i) in folderFiles" :key="i" class="ffl-row">
                <input type="checkbox" v-model="f.selected" style="accent-color:var(--accent-blue)"/>
                <span class="f-ico">📄</span>
                <span class="f-name" style="flex:1">{{ f.name }}</span>
                <span class="f-size">{{ fmtSize(f.size) }}</span>
                <span v-if="f.converted" class="f-badge ok">완료</span>
              </label>
            </div>
          </div>

          <!-- 화살표 -->
          <div class="folder-arrow">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" style="width:22px;height:22px;color:var(--text-tertiary)"><line x1="2" y1="10" x2="18" y2="10"/><polyline points="12,4 18,10 12,16"/></svg>
            <div style="font-size:10px;color:var(--text-tertiary);text-align:center;margin-top:4px">변환</div>
          </div>

          <!-- 타겟 폴더 -->
          <div class="folder-box">
            <!-- 레이블 + 명명 방식 한 줄 -->
            <div class="fb-label-row">
              <span class="fb-label">타겟 폴더 (출력)</span>
              <div class="naming-inline">
                <label class="fo-radio" :class="{active:namingMode==='same'}">
                  <input type="radio" v-model="namingMode" value="same"/>
                  덮어쓰기
                </label>
                <label class="fo-radio" :class="{active:namingMode==='trans'}">
                  <input type="radio" v-model="namingMode" value="trans"/>
                  _trans 추가
                </label>
              </div>
            </div>
            <!-- 경로 표시 - 선택 시 소스와 동일하게 파란색 -->
            <div class="fb-path" :class="{selected:tgtFolder}">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px;flex-shrink:0"><path d="M1 3h5l1 2h8v9H1z"/></svg>
              <span>{{ tgtFolder || '저장할 폴더를 선택하세요' }}</span>
            </div>
            <div style="display:flex;align-items:center;gap:8px">
              <button class="btn btn-primary" @click="pickTgtFolder">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><path d="M1 3h5l1 2h8v9H1z"/></svg>
                타겟 폴더 선택
              </button>
              <span v-if="namingMode==='trans'" style="font-size:10.5px;color:var(--text-tertiary)">
                예: query.sql → query_trans.sql
              </span>
              <span v-else style="font-size:10.5px;color:var(--text-tertiary)">
                예: query.sql → query.sql
              </span>
            </div>
            <!-- 출력 파일 목록 - 소스와 동일한 구조 -->
            <div v-if="tgtFiles.length" class="folder-file-list">
              <div class="ffl-header">출력 파일 ({{ tgtFiles.length }}개)</div>
              <div v-for="(f,i) in tgtFiles" :key="i" class="ffl-row">
                <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px;flex-shrink:0;color:var(--text-success)"><polyline points="2,7 5,10 12,4"/></svg>
                <span class="f-name" style="flex:1">{{ f.name }}</span>
                <span class="f-size">{{ fmtSize(f.size) }}</span>
              </div>
            </div>
            <!-- 파일 없을 때 소스와 동일 높이 유지 -->
            <div v-else-if="folderFiles.length" class="ffl-placeholder">
              변환 실행 후 파일이 여기에 표시됩니다
            </div>
          </div>
        </div>

        <!-- 변환 실행 버튼 -->
        <div class="folder-actions">
          <div style="font-size:12px;color:var(--text-secondary)">
            선택된 파일 <b>{{ folderFiles.filter(f=>f.selected).length }}</b>개
          </div>
          <div style="display:flex;gap:8px">
            <button class="btn btn-primary" style="padding:8px 20px"
              @click="doConvertFolder" :disabled="converting||!folderFiles.filter(f=>f.selected).length">
              <span v-if="converting" class="spinner" style="width:13px;height:13px;border-top-color:#fff;display:inline-block;margin-right:5px"></span>
              <svg v-else viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px"><line x1="2" y1="8" x2="14" y2="8"/><polyline points="9,3 14,8 9,13"/></svg>
              {{ converting?'변환 중...':'폴더 일괄 변환' }}
            </button>
            <button v-if="tgtFiles.length" class="btn" @click="downloadFolderZip" title="전체 ZIP 다운로드">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" style="width:12px;height:12px"><path d="M8 2v8M5 7l3 3 3-3"/><path d="M3 12h10"/></svg>
            </button>
          </div>
        </div>

        <!-- 변환 진행 상황 -->
        <div v-if="folderProgress.total>0" class="folder-progress">
          <div class="fp-bar-wrap">
            <div class="fp-bar" :style="{width:(folderProgress.done/folderProgress.total*100)+'%'}"></div>
          </div>
          <div class="fp-text">{{ folderProgress.done }}/{{ folderProgress.total }} 완료 · {{ folderProgress.changes }}건 변환됨</div>
        </div>

        <!-- FSA 미지원 안내 -->
        <div v-if="fsaNotSupported" class="warn-banner" style="margin-top:10px">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:12px;height:12px;flex-shrink:0"><path d="M8 2L14 14H2L8 2z"/></svg>
          이 브라우저는 폴더 직접 쓰기를 지원하지 않습니다. 변환 후 ZIP으로 다운로드하세요.
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAppStore } from '@/store/appStore.js'
import axios from 'axios'

const app = useAppStore()
const Chev = { template: '<div class="chev-ico"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px;display:block"><polyline points="2,4 6,8 10,4"/></svg></div>' }

const mode      = ref('text')
const srcDb     = ref('mysql')
const tgtDb     = ref('mssql')
const converting= ref(false)
const isDragging= ref(false)

// 텍스트 모드
const textSrc      = ref('')
const textResult   = ref('')
const textChanges  = ref([])
const textWarnings = ref([])

// 파일 모드
const fileInput   = ref(null)
const files       = ref([])
const fileResults = ref([])

// 폴더 모드
const srcFolder         = ref('')
const tgtFolder         = ref('')
const namingMode        = ref('trans')
const folderFiles       = ref([])
const tgtFiles          = ref([])
const folderProgress    = ref({ total:0, done:0, changes:0 })
const fsaNotSupported   = ref(false)
const _srcDirHandle     = ref(null)
const _tgtDirHandle     = ref(null)

const allDbs = [
  {v:'mysql',    n:'MySQL / MariaDB'},
  {v:'mssql',    n:'SQL Server'},
  {v:'oracle',   n:'Oracle'},
  {v:'postgresql',n:'PostgreSQL'},
  {v:'db2',      n:'IBM DB2'},
  {v:'snowflake',n:'Snowflake'},
  {v:'bigquery', n:'BigQuery'},
  {v:'sqlite',   n:'SQLite'},
]

const ruleMap = {
  'mysql→mssql':23,'mysql→postgresql':20,'mssql→mysql':14,
  'oracle→mysql':20,'oracle→postgresql':18,'postgresql→mysql':15,
  'db2→mysql':12,'mysql→snowflake':10,'mysql→bigquery':12,
}
const ruleCount = computed(() => ruleMap[`${srcDb.value}→${tgtDb.value}`] || 0)
const lineCount  = s => (s.match(/\n/g)||[]).length + 1
const fmtSize    = n => n > 1024 ? (n/1024).toFixed(1)+'KB' : n+'B'

function clearAll() {
  textSrc.value=''; textResult.value=''; textChanges.value=[]; textWarnings.value=[]
  files.value=[]; fileResults.value=[]; folderFiles.value=[]; tgtFiles.value=[]
}

// ── 텍스트 변환 ──
async function doConvertText() {
  if (!textSrc.value.trim()) return
  converting.value = true
  try {
    const { data } = await axios.post('/api/v1/sql-converter/convert', {
      sql: textSrc.value, src_db: srcDb.value, tgt_db: tgtDb.value
    })
    textResult.value  = data.converted
    textChanges.value = data.changes
    textWarnings.value= data.warnings
    app.notify(`변환 완료 — ${data.changes.length}건 변경`, 'success')
  } catch(e) { app.notify('변환 실패: '+e.message,'error') }
  finally { converting.value=false }
}

function copyText() { navigator.clipboard?.writeText(textResult.value); app.notify('복사됨','success') }
function downloadText() {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([textResult.value],{type:'text/plain;charset=utf-8'}))
  a.download = `converted_${srcDb.value}_to_${tgtDb.value}.sql`; a.click()
}

// ── 파일 드롭/선택 ──
function onFileSelect(e) { addFiles(Array.from(e.target.files)); e.target.value='' }
function onDrop(e) { isDragging.value=false; addFiles(Array.from(e.dataTransfer.files).filter(f=>/\.(sql|ddl|txt)$/i.test(f.name))) }
function addFiles(newFiles) { newFiles.forEach(f => { if (!files.value.find(ex=>ex.name===f.name)) files.value.push(f) }) }

async function doConvertFiles() {
  converting.value = true
  try {
    const contents = await readFiles(files.value)
    const { data } = await axios.post('/api/v1/sql-converter/convert-files', {
      files: contents, src_db: srcDb.value, tgt_db: tgtDb.value
    })
    fileResults.value = data.files.map(r=>({...r, _open:false}))
    app.notify(`${data.total_files}개 변환 완료`, 'success')
  } catch(e) { app.notify('변환 실패','error') }
  finally { converting.value=false }
}

async function downloadZip() {
  const contents = await readFiles(files.value)
  const resp = await axios.post('/api/v1/sql-converter/convert-files/download',
    { files: contents, src_db: srcDb.value, tgt_db: tgtDb.value }, { responseType:'blob' })
  const cd = resp.headers['content-disposition']||''
  const name = cd.match(/filename="(.+?)"/)?.[1]||'converted.zip'
  const a = document.createElement('a'); a.href=URL.createObjectURL(new Blob([resp.data])); a.download=name; a.click()
}

// ── 폴더 선택 (File System Access API) ──
async function pickSrcFolder() {
  if (!window.showDirectoryPicker) { fsaNotSupported.value=true; return }
  try {
    _srcDirHandle.value = await window.showDirectoryPicker({ mode:'read' })
    srcFolder.value = _srcDirHandle.value.name
    await loadFolderFiles()
  } catch(e) { if (e.name!=='AbortError') app.notify('폴더 접근 실패','error') }
}

async function pickTgtFolder() {
  if (!window.showDirectoryPicker) { fsaNotSupported.value=true; return }
  try {
    _tgtDirHandle.value = await window.showDirectoryPicker({ mode:'readwrite' })
    tgtFolder.value = _tgtDirHandle.value.name
    app.notify('타겟 폴더 선택됨','success')
  } catch(e) { if (e.name!=='AbortError') app.notify('폴더 접근 실패','error') }
}

async function loadFolderFiles() {
  folderFiles.value = []
  if (!_srcDirHandle.value) return
  for await (const [name, handle] of _srcDirHandle.value.entries()) {
    if (handle.kind === 'file' && /\.(sql|ddl|txt)$/i.test(name)) {
      const file = await handle.getFile()
      folderFiles.value.push({ name, size: file.size, selected: true, handle, converted: false })
    }
  }
  app.notify(`${folderFiles.value.length}개 SQL 파일 발견`, 'success')
}

function selAll()  { folderFiles.value.forEach(f=>f.selected=true) }
function selNone() { folderFiles.value.forEach(f=>f.selected=false) }

async function doConvertFolder() {
  const selected = folderFiles.value.filter(f=>f.selected)
  if (!selected.length) return
  converting.value = true
  folderProgress.value = { total: selected.length, done: 0, changes: 0 }
  tgtFiles.value = []

  const _tgtDir = _tgtDirHandle.value  // may be null → download only
  const allConverted = []

  for (const f of selected) {
    try {
      const file    = await f.handle.getFile()
      const content = await file.text()
      const { data } = await axios.post('/api/v1/sql-converter/convert', {
        sql: content, src_db: srcDb.value, tgt_db: tgtDb.value
      })
      const outName = namingMode.value==='trans'
        ? f.name.replace(/(\.[^.]+)$/, '_trans$1')
        : f.name

      allConverted.push({ name: outName, content: data.converted, changes: data.changes.length })

      // 타겟 폴더 직접 저장
      if (_tgtDir) {
        const outHandle = await _tgtDir.getFileHandle(outName, { create: true })
        const writable  = await outHandle.createWritable()
        await writable.write(data.converted)
        await writable.close()
      }

      f.converted = true
      tgtFiles.value.push({ name: outName, size: new Blob([data.converted]).size })
      folderProgress.value.done++
      folderProgress.value.changes += data.changes.length
    } catch(e) {
      folderProgress.value.done++
    }
  }
  converting.value = false
  const saved = _tgtDir ? '폴더에 저장됨' : 'ZIP으로 다운로드하세요'
  app.notify(`${allConverted.length}개 파일 변환 완료 — ${saved}`, 'success')
  if (!_tgtDir) {
    // 자동 ZIP 다운로드
    const resp = await axios.post('/api/v1/sql-converter/convert-files/download',
      { files: allConverted.map(f=>({name:f.name, content:f.content})), src_db:srcDb.value, tgt_db:tgtDb.value },
      { responseType:'blob' })
    const a = document.createElement('a'); a.href=URL.createObjectURL(new Blob([resp.data])); a.download='converted_folder.zip'; a.click()
  }
}

async function downloadFolderZip() {
  const contents = await Promise.all(
    folderFiles.value.filter(f=>f.selected&&f.converted).map(async f => {
      const file = await f.handle.getFile()
      return { name: f.name, content: await file.text() }
    })
  )
  const resp = await axios.post('/api/v1/sql-converter/convert-files/download',
    { files: contents, src_db:srcDb.value, tgt_db:tgtDb.value }, { responseType:'blob' })
  const a = document.createElement('a'); a.href=URL.createObjectURL(new Blob([resp.data])); a.download='converted_folder.zip'; a.click()
}

// 파일 읽기 헬퍼
async function readFiles(fileList) {
  return Promise.all(fileList.map(f => new Promise((res,rej) => {
    const r = new FileReader()
    r.onload = e => res({ name: f.name, content: e.target.result })
    r.onerror = rej; r.readAsText(f,'utf-8')
  })))
}

// 샘플 SQL
const SAMPLES = {
  'mysql→mssql': `-- MySQL 샘플\nCREATE TABLE \`users\` (\n  \`id\` INT UNSIGNED AUTO_INCREMENT,\n  \`name\` VARCHAR(100) NOT NULL,\n  \`email\` VARCHAR(255),\n  \`created_at\` DATETIME DEFAULT CURRENT_TIMESTAMP,\n  PRIMARY KEY (\`id\`)\n) ENGINE=InnoDB;\n\nSELECT \`id\`, IFNULL(\`email\`,'없음') AS email FROM \`users\` LIMIT 10;`,
  'oracle→mysql': `-- Oracle 샘플\nSELECT "USER_ID", NVL("EMAIL",'없음') FROM "USERS" WHERE ROWNUM <= 10;`,
  'mysql→postgresql': `-- MySQL → PostgreSQL\nCREATE TABLE \`products\` (\n  \`id\` INT AUTO_INCREMENT,\n  \`name\` VARCHAR(200),\n  \`flag\` TINYINT(1) DEFAULT 1,\n  PRIMARY KEY(\`id\`)\n) ENGINE=InnoDB;`,
}
function loadSample() {
  textSrc.value = SAMPLES[`${srcDb.value}→${tgtDb.value}`] || `-- ${srcDb.value}→${tgtDb.value} 샘플 없음\n-- SQL을 직접 입력하세요`
  textResult.value=''; textChanges.value=[]; textWarnings.value=[]
}
</script>

<style scoped>
.cfg-bar{display:flex;align-items:center;gap:10px;padding:10px 14px;margin-bottom:10px;flex-wrap:wrap}
.cfg-pair{display:flex;align-items:center;gap:7px}
.cfg-label{font-size:11.5px;font-weight:500;color:var(--text-secondary);white-space:nowrap}
.sel-wrap{position:relative;min-width:160px}
.sel-wrap select{width:100%;appearance:none;-webkit-appearance:none;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:var(--radius-md);padding:7px 28px 7px 10px;font-size:12.5px;color:var(--text-primary);cursor:pointer;font-family:var(--font)}
.sel-wrap select:focus{outline:none;border-color:var(--accent-blue)}
.chev-ico{position:absolute;right:8px;top:50%;transform:translateY(-50%);pointer-events:none;color:var(--text-tertiary)}
.arrow-ico{color:var(--text-tertiary);padding:0 4px}
.rule-badge{font-size:11px;background:var(--bg-info);color:var(--text-info);padding:3px 10px;border-radius:8px;white-space:nowrap}
.mode-btn{display:inline-flex;align-items:center;gap:5px;padding:6px 11px;border-radius:var(--radius-md);font-size:11.5px;font-weight:500;font-family:var(--font);cursor:pointer;border:0.5px solid var(--border-mid);background:transparent;color:var(--text-secondary);transition:all .12s}
.mode-btn:hover{background:var(--bg-secondary)}
.mode-btn.active{background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue)}
.btn{display:inline-flex;align-items:center;gap:5px;padding:6px 12px;border-radius:var(--radius-md);font-size:12px;font-weight:500;font-family:var(--font);cursor:pointer;border:0.5px solid var(--border-mid);background:transparent;color:var(--text-secondary);transition:all .12s}
.icon-only-btn{padding:5px 7px!important;min-width:0}
.btn:hover{background:var(--bg-secondary)}
.btn-primary{background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue)}
.btn-primary:hover{background:var(--accent-blue);color:#fff}
.btn:disabled{opacity:.5;cursor:not-allowed}

/* 에디터 */
.editor-layout{display:grid;grid-template-columns:1fr 60px 1fr;gap:0;align-items:start;margin-bottom:8px}
.editor-panel{background:var(--bg-primary);border:0.5px solid var(--border-light);border-radius:var(--radius-lg);overflow:hidden}
.ep-head{display:flex;align-items:center;justify-content:space-between;padding:9px 13px;border-bottom:0.5px solid var(--border-light);background:var(--bg-secondary);font-size:11.5px;font-weight:600;letter-spacing:.4px}
.ep-head.src{color:var(--text-info)}.ep-head.tgt{color:var(--text-success)}
.ep-foot{padding:5px 13px;border-top:0.5px solid var(--border-light);background:var(--bg-secondary);font-size:10px;color:var(--text-tertiary)}
.sql-ed{width:100%;height:380px;padding:13px;background:var(--bg-primary);border:none;font-family:'Consolas','SF Mono',monospace;font-size:12.5px;color:var(--text-primary);resize:none;outline:none;tab-size:2;line-height:1.65}
.sql-ed.result{background:var(--bg-secondary);color:var(--text-secondary)}
.sql-ed::placeholder{color:var(--text-tertiary);font-style:italic}
.mid-panel{display:flex;flex-direction:column;align-items:center;justify-content:center;padding-top:160px;gap:6px}
.conv-btn{width:46px;height:46px;border-radius:50%;background:var(--accent-blue);border:none;cursor:pointer;color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;transition:all .15s;box-shadow:0 2px 8px rgba(55,138,221,.35)}
.conv-btn:hover{background:#185fa5;transform:scale(1.06)}
.conv-btn:disabled{opacity:.5;cursor:not-allowed;transform:none}
.change-cnt{font-size:10.5px;text-align:center}
.change-cnt.ok{color:var(--text-success)}.change-cnt.warn{color:var(--text-warning)}
.change-grid{display:flex;flex-wrap:wrap;gap:4px}
.ctag{font-size:11px;padding:2px 8px;border-radius:4px}
.ctag.ok{background:var(--bg-success);color:var(--text-success)}.ctag.warn{background:var(--bg-warning);color:var(--text-warning)}

/* 드롭존 */
.drop-zone{display:flex;flex-direction:column;align-items:center;padding:36px 20px;border:1.5px dashed var(--border-mid);cursor:pointer;min-height:200px;justify-content:center;gap:4px;transition:all .2s}
.drop-zone.drag,.drop-zone:hover{border-color:var(--accent-blue);background:var(--bg-info)}
.dz-main{font-size:13px;font-weight:500;color:var(--text-primary);margin-top:8px}
.dz-sub{font-size:11.5px;color:var(--text-tertiary)}
.sec-header{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-bottom:0.5px solid var(--border-light);font-size:12.5px;font-weight:500;color:var(--text-primary)}
.file-row{display:flex;align-items:center;gap:6px;padding:7px 14px;border-bottom:0.5px solid var(--border-light);font-size:12px}
.file-row:last-child{border-bottom:none}
.f-ico{font-size:14px;flex-shrink:0}
.f-name{flex:1;font-family:'Consolas','SF Mono',monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text-primary)}
.f-size{font-size:10.5px;color:var(--text-tertiary);flex-shrink:0}
.f-badge{font-size:10px;font-weight:600;padding:1px 6px;border-radius:6px;flex-shrink:0}
.f-badge.ok{background:var(--bg-success);color:var(--text-success)}.f-badge.warn{background:var(--bg-warning);color:var(--text-warning)}
.result-row{display:flex;align-items:center;gap:6px;padding:7px 14px;border-bottom:0.5px solid var(--border-light);cursor:pointer;font-size:12px}
.result-row:last-child{border-bottom:none}
.result-row:hover{background:var(--bg-secondary)}
.sum-row{display:flex;gap:8px;padding:10px 14px}
.sum-kpi{flex:1;background:var(--bg-secondary);border-radius:var(--radius-md);padding:8px 12px;text-align:center}
.sk-n{font-size:18px;font-weight:700}.sk-n.info{color:var(--text-info)}.sk-n.ok{color:var(--text-success)}.sk-n.warn{color:var(--text-warning)}
.sk-l{font-size:10.5px;color:var(--text-tertiary)}

/* 폴더 모드 */
.folder-panel{padding:16px}
.folder-layout{display:grid;grid-template-columns:1fr 60px 1fr;gap:0;align-items:start;margin-bottom:14px}
.folder-box{border:0.5px solid var(--border-light);border-radius:var(--radius-lg);padding:14px;background:var(--bg-secondary);display:flex;flex-direction:column;gap:8px;min-height:200px}
.fb-label{font-size:11px;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.6px}
.fb-label-row{display:flex;align-items:center;justify-content:space-between;gap:8px}
.naming-inline{display:flex;align-items:center;gap:3px}
.fb-path{display:flex;align-items:center;gap:7px;padding:8px 10px;background:var(--bg-primary);border:0.5px dashed var(--border-mid);border-radius:var(--radius-md);font-size:12px;color:var(--text-tertiary);min-height:36px;font-family:'Consolas','SF Mono',monospace}
.fb-path.selected{border-color:var(--accent-blue);color:var(--text-info);background:var(--bg-info)}
.folder-arrow{display:flex;flex-direction:column;align-items:center;justify-content:center;padding-top:80px}
.naming-opt{background:var(--bg-primary);border-radius:var(--radius-md);padding:10px 12px;font-size:12px}
.fo-label{font-size:11px;font-weight:500;color:var(--text-secondary)}
.fo-radio{display:flex;align-items:center;gap:3px;font-size:11px;color:var(--text-tertiary);cursor:pointer;padding:3px 7px;border-radius:var(--radius-sm);border:0.5px solid transparent;transition:all .12s;user-select:none}
.fo-radio.active{background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue)}
.fo-radio:hover:not(.active){background:var(--bg-primary);color:var(--text-primary)}
.fo-radio input{width:0;height:0;opacity:0;position:absolute}
.ffl-placeholder{border:1px dashed var(--border-mid);border-radius:var(--radius-md);padding:14px 10px;font-size:11px;color:var(--text-tertiary);text-align:center;flex:1}
.folder-file-list{background:var(--bg-primary);border-radius:var(--radius-md);overflow:hidden;border:0.5px solid var(--border-light);max-height:240px;overflow-y:auto}
.ffl-header{display:flex;align-items:center;justify-content:space-between;padding:6px 10px;background:var(--bg-secondary);border-bottom:0.5px solid var(--border-light);font-size:11px;font-weight:500;color:var(--text-secondary)}
.ffl-row{display:flex;align-items:center;gap:6px;padding:6px 10px;border-bottom:0.5px solid var(--border-light);cursor:pointer;transition:background .1s;font-size:11.5px}
.ffl-row:last-child{border-bottom:none}
.ffl-row:hover{background:var(--bg-secondary)}
.folder-actions{display:flex;align-items:center;justify-content:space-between;padding:10px 0 0;border-top:0.5px solid var(--border-light)}
.folder-progress{margin-top:10px}
.fp-bar-wrap{height:5px;background:var(--bg-tertiary);border-radius:3px;overflow:hidden;margin-bottom:5px}
.fp-bar{height:100%;background:var(--accent-blue);border-radius:3px;transition:width .3s}
.fp-text{font-size:11px;color:var(--text-secondary)}
.mini-btn{font-size:10.5px;padding:3px 8px;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:transparent;color:var(--text-secondary);cursor:pointer;font-family:var(--font);transition:all .12s}
.mini-btn:hover{background:var(--bg-secondary)}.mini-btn.del{color:var(--text-danger)}.mini-btn.del:hover{background:var(--bg-danger)}
.warn-banner{display:flex;align-items:center;gap:7px;padding:10px 14px;background:var(--bg-warning);border-radius:var(--radius-md);font-size:12px;color:var(--text-warning)}
</style>
