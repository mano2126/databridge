<template>
  <header class="topbar">
    <div class="bc"><span class="bc-sec">{{ route.meta?.section }}</span><span class="bc-sep">/</span><b>{{ route.meta?.title }}</b></div>
    <div class="tbr">
      <span class="sdot" :class="online?'on':'off'"></span>
      <span class="ver">v2.0.0</span>
      <span class="clock">{{ clock }}</span>
      <button class="tbtn" @click="startNewJob">+ New Job</button>
      <!-- 모양/테마 아이콘 (v9) -->
      <button class="tbtn-icon" @click="router.push('/appearance')" title="모양 및 느낌">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px">
          <circle cx="8" cy="8" r="3"/>
          <path d="M8 1v2M8 13v2M3.5 3.5l1.5 1.5M11 11l1.5 1.5M1 8h2M13 8h2M3.5 12.5L5 11M11 5l1.5-1.5"/>
        </svg>
      </button>
      <!-- 설정 아이콘 -->
      <button class="tbtn-icon" @click="router.push('/settings')" title="시스템 설정">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px">
          <circle cx="8" cy="8" r="2.5"/>
          <path d="M8 1.5v1M8 13.5v1M1.5 8h1M13.5 8h1M3.4 3.4l.7.7M11.9 11.9l.7.7M3.4 12.6l.7-.7M11.9 4.1l.7-.7"/>
        </svg>
      </button>
      <!-- 사용자 메뉴 (RBAC 활성 시) -->
      <div v-if="authStore.isAuthenticated && !authStore.user?.rbac_disabled" class="user-menu">
        <button class="user-btn" @click="userMenuOpen = !userMenuOpen">
          <span class="user-name">{{ authStore.user?.username }}</span>
          <span class="user-role" :class="'role-' + authStore.role">{{ authStore.role }}</span>
          <svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px">
            <polyline points="2,4 5,7 8,4"/>
          </svg>
        </button>
        <div v-if="userMenuOpen" class="user-dropdown" @click="userMenuOpen=false">
          <button @click="onLogout">로그아웃</button>
        </div>
      </div>
    </div>
  </header>
</template>
<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store/authStore.js'
import { useConnectorStore } from '@/store/connectorStore.js'
const route = useRoute(); const router = useRouter()
const authStore = useAuthStore()
const connector = useConnectorStore()
const userMenuOpen = ref(false)
const online = ref(true)

/**
 * v10 #20 + v90.19: "+ New Job" 버튼 — 새 Job 시작 시 이전 연결 상태 + 위저드 상태 강제 초기화.
 * 이유: 같은 /jobs/wizard 라우트에 머물러 있을 때 router.push 만으로는
 *       컴포넌트가 재마운트되지 않아 이전 프로파일/연결 잔상이 남는 문제 해결.
 *       v90.19: sessionStorage 의 위저드 상태도 함께 클리어 (?fresh=1).
 */
async function startNewJob() {
  connector.resetConnections()
  // v90.19: 위저드 상태 명시적 리셋
  try { sessionStorage.removeItem('databridge.wizard.state.v1') } catch (e) { /* 무시 */ }
  // 이미 wizard 라우트에 있다면 route.replace 로 replace → 강제 재진입 유도
  if (route.path === '/jobs/wizard') {
    // 쿼리 파라미터에 fresh=1 + 타임스탬프 얹어서 route 가 "달라지게" 만듦 → 재마운트 유발
    await router.replace({ path: '/jobs/wizard', query: { fresh: '1', t: Date.now() } })
  } else {
    await router.push({ path: '/jobs/wizard', query: { fresh: '1' } })
  }
}

async function onLogout() {
  await authStore.logout()
  router.replace('/login')
}

function getNow() {
  const d = new Date()
  const yyyy = d.getFullYear()
  const mo = String(d.getMonth()+1).padStart(2,'0')
  const dd = String(d.getDate()).padStart(2,'0')
  const hh = String(d.getHours()).padStart(2,'0')
  const mm = String(d.getMinutes()).padStart(2,'0')
  const ss = String(d.getSeconds()).padStart(2,'0')
  return `${yyyy}.${mo}.${dd} ${hh}:${mm}:${ss}`
}
const clock = ref(getNow())
let timer = null
onMounted(() => { timer = setInterval(() => { clock.value = getNow() }, 1000) })
onUnmounted(() => clearInterval(timer))
</script>
<style scoped>
.topbar{height:var(--topbar-h);flex-shrink:0;background:var(--bg-primary);border-bottom:0.5px solid var(--border-light);display:flex;align-items:center;padding:0 20px;gap:8px}
.bc{font-size:11.5px;color:var(--text-tertiary);display:flex;align-items:center;gap:6px}
.bc-sep{color:var(--border-strong)}.bc b{color:var(--text-primary);font-weight:500}
.tbr{margin-left:auto;display:flex;align-items:center;gap:8px}
.sdot{width:7px;height:7px;border-radius:50%}
.sdot.on{background:#639922;animation:pulse 2s infinite}.sdot.off{background:#e24b4a}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.ver{font-size:11.5px;color:var(--text-tertiary)}
.clock{font-size:11.5px;color:var(--text-tertiary);font-family:'Consolas','SF Mono',monospace;letter-spacing:.3px}
.tbtn{font-size:11.5px;color:var(--text-secondary);border:0.5px solid var(--border-mid);padding:4px 10px;border-radius:var(--radius-sm);background:transparent;cursor:pointer;font-family:var(--font);transition:all .12s}
.tbtn:hover{background:var(--bg-secondary);color:var(--text-primary)}
.tbtn-icon{display:flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:transparent;cursor:pointer;color:var(--text-tertiary);transition:all .12s}
.tbtn-icon:hover{background:var(--bg-secondary);color:var(--text-primary)}

/* ── 사용자 메뉴 (RBAC 활성 시만 표시) ───────── */
.user-menu{position:relative;margin-left:8px}
.user-btn{
  display:flex;align-items:center;gap:8px;
  background:transparent;border:0.5px solid var(--border-mid);
  padding:4px 10px;border-radius:var(--radius-sm);
  cursor:pointer;font-family:var(--font);font-size:11.5px;
  color:var(--text-secondary);transition:all .12s;
}
.user-btn:hover{background:var(--bg-secondary);color:var(--text-primary)}
.user-name{font-weight:500}
.user-role{
  font-size:10px;padding:1px 6px;border-radius:3px;font-weight:600;
  text-transform:uppercase;letter-spacing:.3px;
}
.user-role.role-admin   {background:#fecaca;color:#991b1b}
.user-role.role-operator{background:#bfdbfe;color:#1e40af}
.user-role.role-viewer  {background:#e5e7eb;color:#374151}

.user-dropdown{
  position:absolute;top:calc(100% + 4px);right:0;
  background:var(--bg-primary);border:0.5px solid var(--border-mid);
  border-radius:var(--radius-sm);box-shadow:0 6px 20px rgba(0,0,0,.08);
  min-width:140px;z-index:50;
  padding:4px 0;
}
.user-dropdown button{
  width:100%;text-align:left;padding:8px 14px;
  background:transparent;border:none;cursor:pointer;
  font-size:12px;color:var(--text-primary);font-family:var(--font);
}
.user-dropdown button:hover{background:var(--bg-secondary)}
</style>
