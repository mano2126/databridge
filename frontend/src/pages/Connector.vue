<template>
  <div>
    <div class="page-title">커넥터 관리</div>
    <div class="page-desc">소스와 타겟 데이터베이스를 선택하고 연결 정보를 설정하세요</div>

    <!-- ★ 사전점검 버튼 (상단 우측, 소스/타겟 선택 시 활성화) -->
    <div class="pc-toolbar">
      <button
        class="pc-open-btn"
        :class="{enabled: canOpenPrecheck}"
        :disabled="!canOpenPrecheck"
        :title="precheckTooltip"
        @click="precheckVisible = true"
      >
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px">
          <rect x="2.5" y="2" width="11" height="12" rx="1"/>
          <line x1="5" y1="5.5" x2="11" y2="5.5"/>
          <line x1="5" y1="8" x2="11" y2="8"/>
          <line x1="5" y1="10.5" x2="9" y2="10.5"/>
        </svg>
        이관 전 사전점검
      </button>
    </div>

    <div class="conn-layout">
      <ConnectionForm side="source" mode="source"
        v-model:dbType="s.source.dbType" v-model:version="s.source.version"
        v-model:host="s.source.host" v-model:port="s.source.port"
        v-model:username="s.source.username" v-model:password="s.source.password"
        v-model:database="s.source.database"
        :status="s.source.status" :latency="s.source.latency"
        :versionResult="s.source.versionResult" :message="s.source.message"
        @test="doTest('source')"/>
      <div class="arrow-col">
        <div class="arrow-circle" :class="{active:s.bothConnected}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="4" y1="12" x2="20" y2="12"/><polyline points="14,6 20,12 14,18"/></svg>
        </div>
        <div class="arrow-lbl">Migration<br>Pipeline</div>
        <div v-if="s.bothConnected" class="ok-badge">연결 완료 ✓</div>
      </div>
      <ConnectionForm side="target" mode="target"
        v-model:dbType="s.target.dbType" v-model:version="s.target.version"
        v-model:host="s.target.host" v-model:port="s.target.port"
        v-model:username="s.target.username" v-model:password="s.target.password"
        v-model:database="s.target.database"
        :status="s.target.status" :latency="s.target.latency"
        :versionResult="s.target.versionResult" :message="s.target.message"
        @test="doTest('target')"/>
    </div>

    <button class="go-btn" :class="{on:s.bothConnected}" @click="goWizard">
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:15px;height:15px"><line x1="4" y1="8" x2="12" y2="8"/><polyline points="9,5 12,8 9,11"/></svg>
      {{ s.bothConnected?'연결 확인 완료 — Job 생성 위저드로 이동':'소스와 타겟 연결 테스트를 먼저 완료하세요' }}
    </button>

    <!-- v10 #23d: 테이블 형태로 통일. 기본정보 컬럼 + 정렬 헤더 클릭. -->
    <div class="card profile-card" style="margin-top:14px">
      <!-- 상단 툴바 -->
      <div class="profile-toolbar">
        <div class="pt-left">
          <span class="pt-title">저장된 연결 프로파일</span>
          <span class="pt-count">{{ sortedProfiles.length }}개</span>
        </div>
        <div class="pt-right">
          <button class="act-btn" :class="{'pulse-save': s.bothConnected}" @click="showSave=true">+ 현재 설정 저장</button>
          <button class="act-btn" @click="s.loadProfiles()" title="새로고침">↻</button>
        </div>
      </div>

      <!-- 테이블 -->
      <div v-if="!sortedProfiles.length" class="empty-state" style="padding:28px">저장된 프로파일이 없습니다</div>
      <template v-else>
        <div class="p-header">
          <div class="sortable" @click="setSort('name')">
            이름 <SortIco col="name" :sort="sortCol" :dir="sortDir"/>
          </div>
          <div class="sortable" @click="setSort('src_db')">
            소스 <SortIco col="src_db" :sort="sortCol" :dir="sortDir"/>
          </div>
          <div class="sortable" @click="setSort('tgt_db')">
            타겟 <SortIco col="tgt_db" :sort="sortCol" :dir="sortDir"/>
          </div>
          <div>연결 정보</div>
          <div class="sortable" @click="setSort('status')">
            상태 <SortIco col="status" :sort="sortCol" :dir="sortDir"/>
          </div>
          <div class="sortable" @click="setSort('created_at')">
            생성일 <SortIco col="created_at" :sort="sortCol" :dir="sortDir"/>
          </div>
          <div class="sortable" @click="setSort('last_used_at')">
            최근 사용 <SortIco col="last_used_at" :sort="sortCol" :dir="sortDir"/>
          </div>
          <div>작업</div>
        </div>

        <div v-for="p in sortedProfiles" :key="p.id" class="p-row">
          <div class="p-name" :title="p.name">{{ p.name }}</div>
          <div>
            <span class="db-chip" :style="{background:m(p.source?.db_type||p.source?.dbType)?.bg,color:m(p.source?.db_type||p.source?.dbType)?.color}">
              {{ m(p.source?.db_type||p.source?.dbType)?.label }}
            </span>
          </div>
          <div>
            <span class="db-chip" :style="{background:m(p.target?.db_type||p.target?.dbType)?.bg,color:m(p.target?.db_type||p.target?.dbType)?.color}">
              {{ m(p.target?.db_type||p.target?.dbType)?.label }}
            </span>
          </div>
          <div class="p-conn" :title="(p.source?.host||'?') + ' → ' + (p.target?.host||'?')">
            {{ p.source?.host||'?' }} → {{ p.target?.host||'?' }}
          </div>
          <div>
            <span class="pill" :class="p.status==='ok'?'pill-ok':'pill-warn'">
              {{ p.status==='ok'?'연결됨':'만료' }}
            </span>
          </div>
          <div class="p-meta">{{ fmtAgo(p.created_at) }}</div>
          <div class="p-meta">{{ fmtLastUsed(p.id) }}</div>
          <div class="p-actions">
            <button class="act-btn" @click="loadProfile(p)">불러오기</button>
            <button class="act-btn del" @click="s.removeProfile(p.id);app.notify('삭제되었습니다')">삭제</button>
          </div>
        </div>
      </template>
    </div>

    <div v-if="showSave" class="modal-overlay" @click.self="showSave=false">
      <div class="modal">
        <div class="modal-title">프로파일 이름 입력</div>
        <input type="text" v-model="saveName" placeholder="예) MSSQL Prod → MySQL 이관" @keyup.enter="doSave"/>
        <div class="modal-btns">
          <button class="btn" @click="showSave=false">취소</button>
          <button class="btn btn-primary" @click="doSave">저장</button>
        </div>
      </div>
    </div>

    <!-- ★ 사전점검 드로어 -->
    <PrecheckDrawer
      v-model="precheckVisible"
      :src-type="s.source.dbType"
      :tgt-type="s.target.dbType"
    />
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useConnectorStore } from '@/store/connectorStore.js'
import { useAppStore } from '@/store/appStore.js'
import { DB_META } from '@/constants/dbMeta.js'
import ConnectionForm from '@/components/connector/ConnectionForm.vue'
import PrecheckDrawer from '@/components/precheck/PrecheckDrawer.vue'

const s=useConnectorStore(); const app=useAppStore(); const router=useRouter()
const showSave=ref(false); const saveName=ref('')
const m = t => DB_META[t]||{label:'??',bg:'#eee',color:'#333'}

// v10 #23d: 헤더 클릭 정렬 (ConnProfiles 페이지와 같은 방식)
const sortCol = ref('last_used_at')
const sortDir = ref('desc')
function setSort(col) {
  if (sortCol.value === col) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortCol.value = col
    // 날짜/최근사용은 기본 내림차순, 그 외는 오름차순
    sortDir.value = (col === 'created_at' || col === 'last_used_at') ? 'desc' : 'asc'
  }
}
const SortIco = {
  props: ['col', 'sort', 'dir'],
  template: `<span class="sort-ico">
    <span :style="{opacity:sort===col&&dir==='asc'?1:0.2}">▲</span>
    <span :style="{opacity:sort===col&&dir==='desc'?1:0.2}">▼</span>
  </span>`
}

const lastUsedMap = ref({})
function reloadLastUsed() {
  try {
    const raw = localStorage.getItem('databridge.profile.lastUsed')
    lastUsedMap.value = raw ? JSON.parse(raw) : {}
  } catch (e) { lastUsedMap.value = {} }
}
function lastUsedTs(id) { return lastUsedMap.value[id] || 0 }

// 상대시간 포맷
function fmtAgo(iso) {
  if (!iso) return '-'
  const ts = Date.parse(iso)
  if (isNaN(ts)) return '-'
  return relTime(ts)
}
function fmtLastUsed(id) {
  const ts = lastUsedTs(id)
  if (!ts) return '사용 안 함'
  return relTime(ts)
}
function relTime(ts) {
  const diff = Date.now() - ts
  if (diff < 0) return '방금'
  const mm = Math.floor(diff / 60000)
  if (mm < 1) return '방금'
  if (mm < 60) return mm + '분 전'
  const h = Math.floor(mm / 60)
  if (h < 24) return h + '시간 전'
  const d = Math.floor(h / 24)
  if (d === 1) return '어제'
  if (d < 7) return d + '일 전'
  if (d < 30) return Math.floor(d / 7) + '주 전'
  return new Date(ts).toISOString().slice(0, 10)
}

// 헤더 클릭 정렬 computed (날짜/문자 분기)
const sortedProfiles = computed(() => {
  const list = [...(s.profiles || [])]
  const col = sortCol.value
  const dir = sortDir.value === 'asc' ? 1 : -1
  const isDateCol = (col === 'created_at' || col === 'last_used_at')

  const getVal = (o, c) => {
    if (c === 'name') return o.name || ''
    if (c === 'src_db') return o.source?.db_type || o.source?.dbType || ''
    if (c === 'tgt_db') return o.target?.db_type || o.target?.dbType || ''
    if (c === 'status') return o.status || ''
    if (c === 'created_at') {
      const t = Date.parse(o.created_at || '')
      return isNaN(t) ? 0 : t
    }
    if (c === 'last_used_at') return lastUsedTs(o.id)
    return o[c] || ''
  }

  list.sort((a, b) => {
    const av = getVal(a, col), bv = getVal(b, col)
    if (isDateCol) return (av - bv) * dir
    return String(av).localeCompare(String(bv)) * dir
  })
  return list
})

function loadProfile(p) {
  s.applyProfile(p)
  reloadLastUsed()
  app.notify('프로파일을 불러왔습니다','success')
}

// ★ 사전점검 드로어 상태
const precheckVisible = ref(false)
const canOpenPrecheck = computed(() => !!(s.source.dbType && s.target.dbType))
const precheckTooltip = computed(() => {
  if (!s.source.dbType && !s.target.dbType) return '소스와 타겟 DB를 먼저 선택하세요'
  if (!s.source.dbType) return '소스 DB를 먼저 선택하세요'
  if (!s.target.dbType) return '타겟 DB를 먼저 선택하세요'
  return '고객사 DBA에게 전달할 사전점검 가이드 열기'
})

onMounted(()=>{ s.loadProfiles(); reloadLastUsed() })
async function doTest(side){await s.testConn(side);app.notify(s[side].status==='ok'?'연결 성공!':'연결 실패',s[side].status==='ok'?'success':'error')}
function goWizard(){if(s.bothConnected)router.push('/jobs/wizard')}
async function doSave(){if(!saveName.value.trim())return;await s.saveProfile(saveName.value.trim());saveName.value='';showSave.value=false;app.notify('프로파일이 저장되었습니다','success')}
</script>
<style scoped>
.conn-layout{display:grid;grid-template-columns:1fr 68px 1fr;gap:0;align-items:start}
.arrow-col{display:flex;flex-direction:column;align-items:center;justify-content:center;padding-top:80px;gap:8px}
.arrow-circle{width:40px;height:40px;border-radius:50%;border:1.5px solid var(--border-mid);display:flex;align-items:center;justify-content:center;color:var(--text-tertiary);transition:all .3s}
.arrow-circle.active{border-color:var(--accent-blue);color:var(--accent-blue);background:var(--bg-info)}
.arrow-circle svg{width:18px;height:18px}
.arrow-lbl{font-size:9.5px;color:var(--text-tertiary);text-align:center;line-height:1.4}
.ok-badge{font-size:10px;background:var(--bg-success);color:var(--text-success);padding:2px 8px;border-radius:8px;font-weight:500}
.go-btn{width:100%;margin-top:14px;padding:11px;border-radius:var(--radius-md);border:1.5px solid var(--border-mid);background:var(--bg-secondary);font-size:13px;font-weight:500;color:var(--text-tertiary);cursor:not-allowed;font-family:var(--font);display:flex;align-items:center;justify-content:center;gap:8px;transition:all .2s}
.go-btn.on{border-color:var(--accent-blue);background:var(--bg-info);color:var(--text-info);cursor:pointer}
.go-btn.on:hover{background:var(--accent-blue);color:#fff}

/* ─── 사전점검 버튼 ────────────────── */
.pc-toolbar{
  display:flex;
  justify-content:flex-end;
  margin-bottom:10px;
}
.pc-open-btn{
  display:inline-flex;
  align-items:center;
  gap:6px;
  padding:7px 13px;
  border-radius:var(--radius-md);
  border:0.5px solid var(--border-mid);
  background:var(--bg-secondary);
  color:var(--text-tertiary);
  font-size:12px;
  font-weight:500;
  font-family:var(--font);
  cursor:not-allowed;
  transition:all .15s;
}
.pc-open-btn.enabled{
  cursor:pointer;
  border-color:var(--accent-blue);
  background:var(--bg-info);
  color:var(--text-info);
}
.pc-open-btn.enabled:hover{
  background:var(--accent-blue);
  color:#fff;
}

/* v10 #23d: ConnProfiles 스타일의 테이블 형태 프로파일 리스트 */
.profile-card { padding:0; overflow:hidden; }

/* 상단 툴바: 타이틀(좌) + 버튼(우) */
.profile-toolbar {
  display:flex;
  align-items:center;
  justify-content:space-between;
  padding:11px 14px;
  border-bottom:0.5px solid var(--border-light);
  gap:12px;
  flex-wrap:nowrap;
}
.pt-left { display:flex; align-items:baseline; gap:8px; min-width:0; }
.pt-right { display:flex; gap:6px; align-items:center; flex-shrink:0; }
.pt-title { font-size:13px; font-weight:600; color:var(--text-primary); white-space:nowrap; }
.pt-count {
  font-size:11px;
  color:var(--text-tertiary);
  padding:1px 7px;
  background:var(--bg-secondary);
  border-radius:9px;
}

/* 테이블 헤더 & 행 - 8컬럼 */
.p-header, .p-row {
  display:grid;
  grid-template-columns: 1.4fr 60px 60px 1.2fr 70px 90px 90px 150px;
  align-items:center;
  gap:8px;
  padding:8px 14px;
}
.p-header {
  background:var(--bg-secondary);
  border-bottom:1px solid var(--border-mid);
  font-size:10.5px;
  font-weight:600;
  color:var(--text-tertiary);
  text-transform:uppercase;
  letter-spacing:.04em;
}
.p-row {
  border-bottom:0.5px solid var(--border-light);
  font-size:12px;
  transition:background .12s;
}
.p-row:last-child { border-bottom:none; }
.p-row:hover { background:var(--bg-hover); }

/* 각 셀 */
.p-name {
  font-weight:500;
  color:var(--text-primary);
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
}
.p-conn {
  font-family:'Consolas','SF Mono',monospace;
  font-size:11.5px;
  color:var(--text-secondary);
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
}
.p-meta { font-size:11px; color:var(--text-tertiary); }
.p-actions {
  display:flex;
  gap:4px;
  flex-wrap:nowrap;
  white-space:nowrap;
  justify-content:flex-end;
}

/* DB 칩 (소스/타겟 컬럼) */
.db-chip {
  display:inline-flex;
  align-items:center;
  justify-content:center;
  width:28px;
  height:22px;
  border-radius:4px;
  font-size:9.5px;
  font-weight:700;
  flex-shrink:0;
}

/* 정렬 표시 */
.sortable {
  cursor:pointer;
  user-select:none;
  display:inline-flex;
  align-items:center;
  gap:2px;
}
.sortable:hover { color:var(--text-primary); }
.sort-ico {
  display:inline-flex;
  flex-direction:column;
  font-size:7px;
  line-height:1;
  margin-left:2px;
}

/* v10 #23e: 양쪽 연결 완료 시 "현재 설정 저장" 버튼 펄스 */
.pulse-save {
  position:relative;
  border-color: var(--accent-blue) !important;
  color: var(--accent-blue) !important;
  background: var(--bg-info) !important;
  animation: pulseSave 1.6s ease-in-out infinite;
}
.pulse-save:hover {
  /* 호버 시 애니메이션 멈추고 명확한 대비 */
  animation: none;
  background: var(--accent-blue) !important;
  color: #fff !important;
}
@keyframes pulseSave {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.35);
  }
  50% {
    box-shadow: 0 0 0 5px rgba(37, 99, 235, 0);
  }
}
/* 접근성: 모션 감소 설정 시엔 애니메이션 끄고 테두리만 강조 */
@media (prefers-reduced-motion: reduce) {
  .pulse-save { animation: none; }
}
</style>
