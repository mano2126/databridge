<template>
  <div>
    <div class="page-title">저장된 프로파일 관리</div>
    <div class="page-desc">저장된 DB 연결 프로파일을 관리합니다</div>

    <!-- 툴바 -->
    <div class="card toolbar-card">
      <div class="toolbar-left">
        <button class="btn btn-primary" style="font-size:12px" @click="$router.push('/connector')">+ 새 프로파일 추가</button>
        <button class="act-btn" @click="store.loadProfiles()">↻ 새로고침</button>
      </div>
      <div class="toolbar-right">
        <span class="total-badge">{{ sorted.length }}개 프로파일</span>
        <span style="font-size:11.5px;color:var(--text-tertiary)">페이지당</span>
        <div class="per-page-group">
          <button v-for="n in [10,25,50]" :key="n" class="per-page-btn" :class="{active:pageSize===n}" @click="pageSize=n;page=1">{{ n }}</button>
        </div>
      </div>
    </div>

    <!-- 테이블 -->
    <div class="card" style="padding:0;overflow:hidden">
      <div class="list-header">
        <div class="sortable" @click="setSort('name')">이름 <SortIco col="name" :sort="sortCol" :dir="sortDir"/></div>
        <div class="sortable" @click="setSort('src_db')">소스 DB <SortIco col="src_db" :sort="sortCol" :dir="sortDir"/></div>
        <div class="sortable" @click="setSort('tgt_db')">타겟 DB <SortIco col="tgt_db" :sort="sortCol" :dir="sortDir"/></div>
        <div>소스 호스트</div>
        <div>타겟 호스트</div>
        <div class="sortable" @click="setSort('status')">상태 <SortIco col="status" :sort="sortCol" :dir="sortDir"/></div>
        <div class="sortable" @click="setSort('created_at')">생성일 <SortIco col="created_at" :sort="sortCol" :dir="sortDir"/></div>
        <div class="sortable" @click="setSort('last_used_at')">최근 사용 <SortIco col="last_used_at" :sort="sortCol" :dir="sortDir"/></div>
        <div>작업</div>
      </div>

      <div v-if="paged.length===0" class="empty-state" style="padding:28px">저장된 프로파일이 없습니다</div>

      <div v-for="p in paged" :key="p.id" class="list-row-item">
        <div class="item-name">{{ p.name }}</div>
        <div>
          <div style="display:flex;align-items:center;gap:5px">
            <span class="db-chip" :style="{background:m(p.source?.db_type||p.source?.dbType)?.bg, color:m(p.source?.db_type||p.source?.dbType)?.color}">
              {{ m(p.source?.db_type||p.source?.dbType)?.label }}
            </span>
            <span style="font-size:11.5px">{{ p.source?.db_type || p.source?.dbType || '?' }}</span>
          </div>
        </div>
        <div>
          <div style="display:flex;align-items:center;gap:5px">
            <span class="db-chip" :style="{background:m(p.target?.db_type||p.target?.dbType)?.bg, color:m(p.target?.db_type||p.target?.dbType)?.color}">
              {{ m(p.target?.db_type||p.target?.dbType)?.label }}
            </span>
            <span style="font-size:11.5px">{{ p.target?.db_type || p.target?.dbType || '?' }}</span>
          </div>
        </div>
        <div class="mono-text">{{ p.source?.host||'-' }}:{{ p.source?.port||'-' }}</div>
        <div class="mono-text">{{ p.target?.host||'-' }}:{{ p.target?.port||'-' }}</div>
        <div><span class="pill" :class="p.status==='ok'?'pill-ok':'pill-warn'">{{ p.status==='ok'?'연결됨':'만료' }}</span></div>
        <div class="item-sub">{{ fmtDate(p.created_at) }}</div>
        <div class="item-sub">{{ fmtLastUsed(p.id) }}</div>
        <div>
          <div style="display:flex;gap:4px;flex-wrap:nowrap;white-space:nowrap">
            <button class="act-btn" @click="loadAndGo(p)">불러오기</button>
            <button class="act-btn" @click="testProfile(p)">테스트</button>
            <button class="act-btn del" @click="store.removeProfile(p.id);app.notify('삭제됨')">삭제</button>
          </div>
        </div>
      </div>

      <!-- 페이지네이션 -->
      <div v-if="totalPages>1" class="pagination">
        <button class="page-btn" :disabled="page===1" @click="page=1">«</button>
        <button class="page-btn" :disabled="page===1" @click="page--">‹</button>
        <button v-for="p in visiblePages" :key="p" class="page-btn" :class="{active:p===page}" @click="page=p">{{ p }}</button>
        <button class="page-btn" :disabled="page===totalPages" @click="page++">›</button>
        <button class="page-btn" :disabled="page===totalPages" @click="page=totalPages">»</button>
        <span class="page-info">{{ (page-1)*pageSize+1 }}–{{ Math.min(page*pageSize,sorted.length) }} / {{ sorted.length }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { fmtDate } from '@/utils/dateUtils.js'
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useConnectorStore } from '@/store/connectorStore.js'
import { useAppStore } from '@/store/appStore.js'
import { DB_META } from '@/constants/dbMeta.js'

const store  = useConnectorStore()
const app    = useAppStore()
const router = useRouter()

const m       = t => DB_META[t] || { label:'??', bg:'#eee', color:'#333' }

// v10 #23: localStorage 의 "최근 사용" 맵
const lastUsedMap = ref({})
function reloadLastUsed() {
  try {
    const raw = localStorage.getItem('databridge.profile.lastUsed')
    lastUsedMap.value = raw ? JSON.parse(raw) : {}
  } catch (e) { lastUsedMap.value = {} }
}
function lastUsedTs(id) {
  return lastUsedMap.value[id] || 0
}
function fmtLastUsed(id) {
  const ts = lastUsedTs(id)
  if (!ts) return '-'
  // 상대 시간 포맷 (오늘, 어제, N일 전, 아니면 날짜)
  const now = Date.now()
  const diffMs = now - ts
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffDays === 0) {
    const h = Math.floor(diffMs / 3600000)
    if (h === 0) return '방금'
    return `${h}시간 전`
  }
  if (diffDays === 1) return '어제'
  if (diffDays < 7) return `${diffDays}일 전`
  // 그 이상이면 날짜
  return new Date(ts).toISOString().slice(0, 10)
}

// ── 정렬 ──────────────────────────────────────────────
const sortCol = ref('created_at')
const sortDir = ref('desc')
function setSort(col) {
  if (sortCol.value===col) sortDir.value = sortDir.value==='asc'?'desc':'asc'
  else { sortCol.value=col; sortDir.value='asc' }
  page.value=1
}
const SortIco = {
  props:['col','sort','dir'],
  template:`<span class="sort-ico">
    <span :style="{opacity:sort===col&&dir==='asc'?1:0.2}">▲</span>
    <span :style="{opacity:sort===col&&dir==='desc'?1:0.2}">▼</span>
  </span>`
}

// ── 페이징 ────────────────────────────────────────────
const pageSize = ref(25)
const page     = ref(1)

// v10 #23: 날짜/숫자/문자 구분해서 정확히 정렬
const sorted = computed(() => {
  const list = [...store.profiles]
  const col=sortCol.value, dir=sortDir.value==='asc'?1:-1

  const isDateCol = col === 'created_at' || col === 'last_used_at'
  const getVal = (o,c) => {
    if(c==='name') return o.name||''
    if(c==='src_db') return o.source?.db_type||o.source?.dbType||''
    if(c==='tgt_db') return o.target?.db_type||o.target?.dbType||''
    if(c==='status') return o.status||''
    if(c==='created_at') {
      const d = Date.parse(o.created_at || '')
      return isNaN(d) ? 0 : d
    }
    if(c==='last_used_at') return lastUsedTs(o.id)
    return o[c]||''
  }

  list.sort((a,b) => {
    const av=getVal(a,col), bv=getVal(b,col)
    if (isDateCol) {
      // 숫자 비교
      return (av - bv) * dir
    }
    // 문자열 비교
    return String(av).localeCompare(String(bv))*dir
  })
  return list
})

const totalPages = computed(() => Math.max(1, Math.ceil(sorted.value.length/pageSize.value)))
const visiblePages = computed(() => {
  const t=totalPages.value,c=page.value; let s=Math.max(1,c-2),e=Math.min(t,c+2)
  if(e-s<4){s=Math.max(1,e-4);e=Math.min(t,s+4)} const r=[];for(let i=s;i<=e;i++)r.push(i);return r
})
const paged = computed(() => sorted.value.slice((page.value-1)*pageSize.value, page.value*pageSize.value))

function loadAndGo(p) { store.applyProfile(p); reloadLastUsed(); app.notify('프로파일을 불러왔습니다','success'); router.push('/connector') }
function testProfile(p) { store.applyProfile(p); reloadLastUsed(); router.push('/connector'); app.notify('커넥터 화면에서 연결 테스트를 실행하세요','info') }

onMounted(() => { store.loadProfiles(); reloadLastUsed() })
</script>

<style scoped>
.toolbar-card { display:flex;align-items:center;gap:8px;padding:10px 14px;margin-bottom:10px; }
.toolbar-left { display:flex;gap:6px;align-items:center; }
.toolbar-right { display:flex;gap:6px;align-items:center;margin-left:auto; }
.total-badge { font-size:11px;color:var(--text-tertiary);padding:2px 8px;background:var(--bg-secondary);border-radius:10px; }
.per-page-group { display:flex;border:0.5px solid var(--border-mid);border-radius:var(--radius-sm);overflow:hidden; }
.per-page-btn { padding:3px 8px;font-size:11px;border:none;background:var(--bg-secondary);color:var(--text-secondary);cursor:pointer;border-right:0.5px solid var(--border-light); }
.per-page-btn:last-child { border-right:none; }
.per-page-btn.active { background:var(--accent-blue);color:#fff;font-weight:600; }

.list-header { display:grid;grid-template-columns:1.2fr 110px 110px 130px 130px 70px 100px 100px 180px;padding:6px 14px;background:var(--bg-secondary);border-bottom:1px solid var(--border-mid);font-size:10.5px;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.04em; }
.list-row-item { display:grid;grid-template-columns:1.2fr 110px 110px 130px 130px 70px 100px 100px 180px;align-items:center;padding:9px 14px;border-bottom:0.5px solid var(--border-light);transition:background .12s; }
.list-row-item:last-child { border-bottom:none; }
.list-row-item:hover { background:var(--bg-hover); }
.sortable { cursor:pointer;user-select:none;display:inline-flex;align-items:center;gap:2px; }
.sortable:hover { color:var(--text-primary); }
.sort-ico { display:inline-flex;flex-direction:column;font-size:7px;line-height:1;margin-left:2px; }
.item-name { font-size:12.5px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap; }
.item-sub { font-size:10.5px;color:var(--text-tertiary); }
.mono-text { font-family:'Consolas','SF Mono',monospace;font-size:11.5px;color:var(--text-secondary); }
.db-chip { display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:4px;font-size:9px;font-weight:700;flex-shrink:0; }
.pagination { display:flex;align-items:center;justify-content:center;gap:4px;padding:12px;border-top:0.5px solid var(--border-light); }
.page-btn { min-width:28px;height:26px;padding:0 8px;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:var(--bg-secondary);color:var(--text-secondary);font-size:12px;cursor:pointer; }
.page-btn:hover:not(:disabled) { background:var(--bg-hover);border-color:var(--accent-blue);color:var(--accent-blue); }
.page-btn.active { background:var(--accent-blue);border-color:var(--accent-blue);color:#fff;font-weight:600; }
.page-btn:disabled { opacity:.35;cursor:not-allowed; }
.page-info { font-size:11px;color:var(--text-tertiary);margin-left:8px; }
</style>
