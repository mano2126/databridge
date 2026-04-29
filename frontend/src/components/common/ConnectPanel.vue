<template>
  <div class="cp-panel">
    <!-- 헤더 -->
    <div class="cp-header">
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"
           style="width:12px;height:12px;color:#d97706;flex-shrink:0">
        <path d="M8 2L14 14H2L8 2z"/>
        <line x1="8" y1="7" x2="8" y2="10"/>
        <circle cx="8" cy="12" r=".6" fill="currentColor"/>
      </svg>
      <span class="cp-header-txt">DB 연결이 필요합니다</span>
      <button class="cp-link-btn" @click="$router.push('/connector')">커넥터 관리 →</button>
    </div>

    <!-- 본문: 상=프로파일 가로 리스트, 하=직접 입력(접힘) -->
    <div class="cp-body">

      <!-- 상단: 프로파일 가로 그리드 -->
      <div class="cp-profiles-section" v-if="connector.profiles.length">
        <div class="cp-section-label">저장된 프로파일 <span class="cp-count">{{ connector.profiles.length }}</span></div>
        <div class="cp-profile-grid">
          <!-- v10 #34: sortedProfiles 로 최근 사용 프로파일이 맨 앞에 위치 -->
          <div v-for="p in sortedProfiles" :key="p.id"
               class="cp-profile-card"
               :class="{
                 selected: selectedProfile?.id === p.id,
                 recent:   p.id === mostRecentProfileId && selectedProfile?.id !== p.id
               }"
               @click="selectProfile(p)">
            <!-- v10 #34: 최근 사용 배지 -->
            <div v-if="p.id === mostRecentProfileId && selectedProfile?.id !== p.id"
                 class="cp-recent-badge" title="가장 최근에 사용한 프로파일">🕑 최근</div>
            <div class="cp-profile-icon"
                 :style="{background: dbMeta(p.source)?.bg, color: dbMeta(p.source)?.color}">
              {{ dbMeta(p.source)?.label || '??' }}
            </div>
            <div class="cp-profile-info">
              <div class="cp-profile-name" :title="p.name">{{ p.name }}</div>
              <div class="cp-profile-db">
                {{ (p.source?.dbType||p.source?.db_type||'').toUpperCase() }}
                → {{ (p.target?.dbType||p.target?.db_type||'').toUpperCase() }}
              </div>
            </div>
            <svg v-if="selectedProfile?.id === p.id"
                 viewBox="0 0 12 12" fill="currentColor"
                 class="cp-check-ico">
              <polyline points="1,6 4.5,10 11,2" fill="none" stroke="currentColor" stroke-width="1.8"/>
            </svg>
          </div>
        </div>

        <!-- 프로파일 선택 후 연결 버튼 -->
        <button v-if="selectedProfile"
                class="cp-connect-btn" @click="connectProfile" :disabled="testing">
          <span v-if="testing" class="cp-spin"></span>
          <span v-else>⚡</span>
          {{ selectedProfile.name }} 연결
        </button>
      </div>

      <!-- 프로파일이 없을 때만 "없음" 표시 -->
      <div v-else class="cp-no-profile-box">
        <div class="cp-section-label">저장된 프로파일</div>
        <div class="cp-no-profile">저장된 프로파일이 없습니다. <a class="cp-no-profile-link" @click.prevent="router.push('/connector')">커넥터 관리에서 추가</a>하거나 아래 고급 옵션으로 직접 입력하세요.</div>
      </div>

      <!-- v10 #34: 직접 입력은 접기 토글 (기본 숨김) -->
      <div class="cp-advanced-toggle">
        <button class="cp-adv-btn" @click="showDirect = !showDirect"
                :class="{open: showDirect}">
          <svg viewBox="0 0 10 6" fill="none" stroke="currentColor" stroke-width="1.5"
               style="width:9px;height:9px;transition:transform .2s"
               :style="{transform: showDirect?'rotate(180deg)':'rotate(0deg)'}">
            <polyline points="1,1 5,5 9,1"/>
          </svg>
          고급 · 직접 입력
        </button>
      </div>

      <!-- 하단: 직접 입력 (v10 #34: 기본 숨김, 토글로 펼침) -->
      <div class="cp-direct" v-if="showDirect">
        <div class="cp-section-label">직접 입력</div>

        <!-- 소스 -->
        <div class="cp-db-block">
          <div class="cp-db-label src">
            <div class="cp-db-badge" :style="{background:dbMeta(quickSrc)?.bg, color:dbMeta(quickSrc)?.color}">
              {{ dbMeta(quickSrc)?.label }}
            </div>
            소스 DB
            <select v-model="quickSrc.dbType" class="cp-db-type-sel" @change="quickSrc.port=DB_META[quickSrc.dbType]?.port||3306">
              <option v-for="(v,k) in DB_META" :key="k" :value="k">{{ k.toUpperCase() }}</option>
            </select>
          </div>
          <div class="cp-fields">
            <input v-model="quickSrc.host"     class="cp-input cp-host" placeholder="호스트"/>
            <input v-model="quickSrc.port"     class="cp-input cp-port" placeholder="포트" type="number"/>
            <input v-model="quickSrc.database" class="cp-input cp-db"   placeholder="데이터베이스"/>
            <input v-model="quickSrc.username" class="cp-input cp-user" placeholder="사용자"/>
            <input v-model="quickSrc.password" class="cp-input cp-pw"   placeholder="비밀번호" type="password" autocomplete="new-password"/>
          </div>
        </div>

        <!-- 타겟 -->
        <div class="cp-db-block">
          <div class="cp-db-label tgt">
            <div class="cp-db-badge" :style="{background:dbMeta(quickTgt)?.bg, color:dbMeta(quickTgt)?.color}">
              {{ dbMeta(quickTgt)?.label }}
            </div>
            타겟 DB
            <select v-model="quickTgt.dbType" class="cp-db-type-sel" @change="quickTgt.port=DB_META[quickTgt.dbType]?.port||3306">
              <option v-for="(v,k) in DB_META" :key="k" :value="k">{{ k.toUpperCase() }}</option>
            </select>
          </div>
          <div class="cp-fields">
            <input v-model="quickTgt.host"     class="cp-input cp-host" placeholder="호스트"/>
            <input v-model="quickTgt.port"     class="cp-input cp-port" placeholder="포트" type="number"/>
            <input v-model="quickTgt.database" class="cp-input cp-db"   placeholder="데이터베이스"/>
            <input v-model="quickTgt.username" class="cp-input cp-user" placeholder="사용자"/>
            <input v-model="quickTgt.password" class="cp-input cp-pw"   placeholder="비밀번호" type="password" autocomplete="new-password"/>
          </div>
        </div>

        <button class="cp-connect-btn" @click="connectDirect" :disabled="testing">
          <span v-if="testing" class="cp-spin"></span>
          <span v-else>⚡</span>
          연결 테스트
        </button>

        <!-- 연결 결과 -->
        <div v-if="result" class="cp-result" :class="result.ok ? 'ok' : 'err'">
          {{ result.ok ? '✓ 연결 성공' : '✗ ' + result.msg }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useConnectorStore } from '@/store/connectorStore.js'
import { useAppStore }       from '@/store/appStore.js'
import { DB_META }           from '@/constants/dbMeta.js'

const emit = defineEmits(['connected'])
const router    = useRouter()
const connector = useConnectorStore()
const app       = useAppStore()

onMounted(async () => {
  // 프로파일이 없으면 직접 로드
  if (!connector.profiles.length) {
    await connector.loadProfiles()
  }
  // v10 #34: localStorage 에서 최근 사용 맵 읽어서 반응형으로 보관
  _loadLastUsedMap()
})

const selectedProfile = ref(null)
const testing = ref(false)
const result  = ref(null)

// v10 #34: 직접 입력 섹션 기본 숨김 (고급 토글)
const showDirect = ref(false)

// v10 #34: 최근 사용 프로파일 추적
//   connectorStore.applyProfile() 호출 시 localStorage 의 databridge.profile.lastUsed 맵에
//   {profileId: timestamp} 형태로 기록됨. 이를 읽어서 정렬/배지 표시에 사용.
const lastUsedMap = ref({})
function _loadLastUsedMap() {
  try {
    const raw = localStorage.getItem('databridge.profile.lastUsed')
    lastUsedMap.value = raw ? JSON.parse(raw) : {}
  } catch (e) {
    lastUsedMap.value = {}
  }
}

// 가장 최근 사용한 프로파일 ID (하나만)
const mostRecentProfileId = computed(() => {
  const map = lastUsedMap.value
  let topId = null, topTs = 0
  for (const [id, ts] of Object.entries(map)) {
    // 현재 목록에 존재하는 프로파일만 (삭제된 것 제외)
    if (!connector.profiles.some(p => p.id === id)) continue
    if (ts > topTs) { topTs = ts; topId = id }
  }
  return topId
})

// 정렬된 프로파일 목록 — 최근 사용 맨 앞, 나머지는 이름순
const sortedProfiles = computed(() => {
  const profiles = [...(connector.profiles || [])]
  const map = lastUsedMap.value
  const recentId = mostRecentProfileId.value
  return profiles.sort((a, b) => {
    // 1순위: 최근 사용한 프로파일이 최상위
    if (a.id === recentId) return -1
    if (b.id === recentId) return 1
    // 2순위: 최근 사용 맵에 있는 것들끼리는 최신순
    const aTs = map[a.id] || 0
    const bTs = map[b.id] || 0
    if (aTs || bTs) return bTs - aTs
    // 3순위: 이름순
    return (a.name || '').localeCompare(b.name || '', 'ko')
  })
})

const quickSrc = reactive({ dbType:'mssql', host:'', port:1433, username:'', password:'', database:'' })
const quickTgt = reactive({ dbType:'mysql',  host:'', port:3306, username:'', password:'', database:'' })

function dbMeta(conn) {
  const t = conn?.dbType || conn?.db_type || 'mysql'
  return DB_META[t] || { label:'??', bg:'#eee', color:'#333' }
}

function selectProfile(p) {
  selectedProfile.value = selectedProfile.value?.id === p.id ? null : p
}

async function connectProfile() {
  if (!selectedProfile.value) return
  testing.value = true; result.value = null
  try {
    connector.applyProfile(selectedProfile.value)
    // v10 #34: applyProfile 직후 lastUsedMap 갱신 (배지 즉시 반영)
    _loadLastUsedMap()
    await connector.testConn('source')
    await connector.testConn('target')
    if (connector.bothConnected) {
      result.value = { ok: true }
      app.notify('연결 성공!', 'success')
      emit('connected')
    } else {
      const msg = connector.source.status !== 'ok' ? connector.source.message : connector.target.message
      result.value = { ok: false, msg }
    }
  } catch(e) {
    result.value = { ok: false, msg: e.message }
  } finally { testing.value = false }
}

async function connectDirect() {
  testing.value = true; result.value = null
  try {
    Object.assign(connector.source, quickSrc)
    Object.assign(connector.target, quickTgt)
    await connector.testConn('source')
    await connector.testConn('target')
    if (connector.bothConnected) {
      result.value = { ok: true }
      app.notify('연결 성공!', 'success')
      emit('connected')
    } else {
      const msg = connector.source.status !== 'ok' ? connector.source.message : connector.target.message
      result.value = { ok: false, msg: msg?.slice(0, 80) + '...' }
    }
  } catch(e) {
    result.value = { ok: false, msg: e.message }
  } finally { testing.value = false }
}
</script>

<style scoped>
.cp-panel {
  background: var(--bg-primary);
  border: 0.5px solid var(--border-mid);
  border-radius: var(--radius-md);
  overflow: hidden;
  margin-bottom: 12px;
}
.cp-header {
  display: flex; align-items: center; gap: 8px;
  padding: 9px 14px;
  background: rgba(245,158,11,.07);
  border-bottom: 0.5px solid rgba(245,158,11,.2);
  font-size: .78rem;
}
.cp-header-txt { font-weight: 600; color: #92400e; flex: 1; }
.cp-link-btn {
  font-size: .72rem; color: var(--text-tertiary);
  background: none; border: none; cursor: pointer;
  padding: 2px 6px; border-radius: 4px; font-family: var(--font);
}
.cp-link-btn:hover { color: var(--accent-blue); }

.cp-body {
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* ── 상단: 프로파일 가로 그리드 ── */
.cp-profiles-section {
  padding: 10px 14px 12px;
  border-bottom: 0.5px solid var(--border-light);
  display: flex; flex-direction: column; gap: 8px;
}
.cp-section-label {
  font-size: .63rem; font-weight: 700;
  color: var(--text-tertiary);
  text-transform: uppercase; letter-spacing: .06em;
}
.cp-count {
  display: inline-block;
  margin-left: 4px;
  font-size: .62rem;
  padding: 1px 6px;
  border-radius: 8px;
  background: var(--bg-secondary);
  color: var(--text-tertiary);
  letter-spacing: 0;
  text-transform: none;
  font-weight: 600;
}

/* 그리드: 한 줄에 자동 배치, 폭 부족하면 다음 줄로 */
.cp-profile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 6px;
}
.cp-profile-card {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 9px; border-radius: 7px;
  border: 0.5px solid var(--border-light);
  background: var(--bg-secondary);
  cursor: pointer; transition: all .12s;
  min-width: 0;
  position: relative;  /* v10 #34: 최근 배지 절대 위치용 */
}
.cp-profile-card:hover {
  border-color: var(--accent-blue);
  background: rgba(37,99,235,.04);
}
.cp-profile-card.selected {
  border-color: var(--accent-blue);
  background: rgba(37,99,235,.08);
  box-shadow: 0 0 0 2px rgba(37,99,235,.12);
}
/* v10 #34: 최근 사용 프로파일 강조 — 파란 테두리 + 살짝 그림자 */
.cp-profile-card.recent {
  border-color: rgba(37,99,235,.45);
  background: rgba(37,99,235,.03);
  box-shadow: 0 1px 3px rgba(37,99,235,.08);
}
.cp-profile-card.recent:hover {
  border-color: var(--accent-blue);
  background: rgba(37,99,235,.06);
}
/* 최근 배지 — 카드 오른쪽 위 */
.cp-recent-badge {
  position: absolute;
  top: -5px; right: 6px;
  font-size: .58rem;
  font-weight: 700;
  padding: 1px 6px;
  background: #2563eb;
  color: #fff;
  border-radius: 6px;
  letter-spacing: .04em;
  box-shadow: 0 1px 2px rgba(37,99,235,.35);
  pointer-events: none;
}
.cp-profile-icon {
  width: 24px; height: 24px; border-radius: 5px;
  display: flex; align-items: center; justify-content: center;
  font-size: .6rem; font-weight: 800; flex-shrink: 0;
}
.cp-profile-info { flex: 1; min-width: 0; overflow: hidden; }
.cp-profile-name {
  font-size: .76rem; font-weight: 600; color: var(--text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  line-height: 1.25;
}
.cp-profile-db {
  font-size: .63rem; color: var(--text-tertiary);
  white-space: nowrap; line-height: 1.3;
}
.cp-check-ico {
  width: 11px; height: 11px; color: #2563eb; flex-shrink: 0;
}

.cp-no-profile-box {
  padding: 10px 14px 12px;
  border-bottom: 0.5px solid var(--border-light);
}
.cp-no-profile {
  font-size: .75rem;
  color: var(--text-tertiary);
  padding: 6px 0 2px;
}

.cp-hr { display: none; }  /* 상/하 구조로 바뀌어서 세로 구분선은 사용 안함 */

/* ── 하단: 직접 입력 ── */
.cp-direct {
  padding: 11px 14px 13px;
  display: flex; flex-direction: column; gap: 8px;
}
.cp-db-block { display: flex; flex-direction: column; gap: 5px; }
.cp-db-label {
  display: flex; align-items: center; gap: 6px;
  font-size: .72rem; font-weight: 600; color: var(--text-secondary);
}
.cp-db-badge {
  width: 20px; height: 20px; border-radius: 4px;
  display: flex; align-items: center; justify-content: center;
  font-size: .58rem; font-weight: 800; flex-shrink: 0;
}
.cp-db-type-sel {
  margin-left: auto;
  font-size: .67rem; padding: 1px 4px;
  border: 0.5px solid var(--border-mid); border-radius: 4px;
  background: var(--bg-secondary); color: var(--text-secondary);
  font-family: var(--font); cursor: pointer;
}
.cp-fields {
  display: grid;
  grid-template-columns: 2fr 0.7fr 1.3fr 1fr 1.2fr;
  gap: 4px;
}
.cp-input {
  padding: 5px 7px;
  border: 0.5px solid var(--border-mid); border-radius: 5px;
  background: var(--bg-primary); color: var(--text-primary);
  font-size: .73rem; font-family: var(--font);
  outline: none; transition: border-color .1s; width: 100%;
}
.cp-input:focus { border-color: var(--accent-blue); }
.cp-input::placeholder { color: var(--text-tertiary); }

/* ── 연결 버튼 ── */
.cp-connect-btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 6px 14px; border-radius: 6px;
  background: var(--accent-blue); color: #fff;
  border: none; cursor: pointer;
  font-size: .78rem; font-weight: 600; font-family: var(--font);
  transition: background .12s; align-self: flex-start; margin-top: 2px;
}
.cp-connect-btn:hover { background: #1d4ed8; }
.cp-connect-btn:disabled { opacity: .5; cursor: not-allowed; }

/* ── 결과 ── */
.cp-result {
  font-size: .73rem; font-weight: 600;
  padding: 5px 10px; border-radius: 5px;
}
.cp-result.ok  { background: rgba(22,163,74,.1); color: #15803d; }
.cp-result.err { background: rgba(239,68,68,.08); color: #dc2626; }

/* ── 스핀 ── */
.cp-spin {
  width: 11px; height: 11px;
  border: 2px solid rgba(255,255,255,.4);
  border-top-color: #fff; border-radius: 50%;
  animation: cp-spin .7s linear infinite;
}
@keyframes cp-spin { to { transform: rotate(360deg); } }

/* v10 #34: 고급 · 직접 입력 토글 버튼 */
.cp-advanced-toggle {
  padding: 6px 14px;
  border-top: 0.5px solid var(--border-light);
  background: var(--bg-secondary);
}
.cp-adv-btn {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: .7rem; color: var(--text-tertiary);
  background: none; border: none; cursor: pointer;
  padding: 3px 6px; border-radius: 4px; font-family: var(--font);
  transition: color .12s;
}
.cp-adv-btn:hover { color: var(--text-secondary); }
.cp-adv-btn.open { color: var(--text-info); }

/* "연결 관리에서 추가" 링크 */
.cp-no-profile-link {
  color: var(--accent-blue);
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.cp-no-profile-link:hover { opacity: .85; }
</style>
