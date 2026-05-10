<template>
  <!-- v9 패치 #29b: 라우트 확정 전엔 둘 다 안 그림 (standalone 창 깜빡임 방지) -->
  <template v-if="$route.matched.length === 0"></template>

  <!-- v9 패치 #28: standalone 라우트 (리포트 등 새창) 는 Sidebar/Topbar 없이 전체 화면 -->
  <div v-else-if="$route.meta?.standalone" :data-theme="app.theme" style="min-height:100vh">
    <router-view />
    <ToastNotif />
    <FloatingMonitor />
  </div>

  <div v-else class="app-shell" :data-theme="app.theme">
    <Sidebar />
    <div class="app-body">
      <Topbar />
      <main class="app-main">
        <!-- SqlVerify는 페이지 이동 후 복귀해도 상태 유지 (파일·결과 보존) -->
        <router-view v-slot="{ Component }">
          <keep-alive :include="['SqlVerify','Validate','JobMonitor']">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </main>
    </div>
    <ToastNotif />
    <!-- v10 #22: 실시간 플로팅 모니터 (페이지 이동해도 유지, 드래그/최소화 가능) -->
    <FloatingMonitor />
  </div>
</template>
<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useAppStore } from '@/store/appStore.js'
import { useJobStore } from '@/store/jobStore.js'
import { useAuthStore } from '@/store/authStore.js'
import Sidebar from '@/components/layout/Sidebar.vue'
import Topbar  from '@/components/layout/Topbar.vue'
import ToastNotif from '@/components/common/ToastNotif.vue'
import FloatingMonitor from '@/components/common/FloatingMonitor.vue'  // v10 #22: 실시간 플로팅 모니터
// v95_p107: SystemTrayWidget 제거 — OS 트레이 앱 (tray_app.py) 으로 대체
const app  = useAppStore()
const jobs = useJobStore()
const authStore = useAuthStore()

// 저장된 아이콘 테마 + 여백 설정 초기 적용
onMounted(async () => {
  // ── RBAC 활성 여부 확인 + 현재 사용자 복원 (v9 패치 #2) ────────
  // await 로 먼저 끝낸 뒤 폴링을 시작해야 토큰이 요청에 실림.
  // 실패해도 (비로그인 상태 등) 앱은 계속 동작해야 하므로 catch만.
  try {
    await authStore.init()
  } catch (_) {}

  // ── UI 커스터마이즈 적용 (v9+) ─────────────────────────────
  app.applyUI()
  app.applyTheme()
  // OS 다크모드 변경 감지 (theme=auto 일 때)
  if (window.matchMedia) {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    mq.addEventListener('change', () => {
      if (app.theme === 'auto') app.applyTheme()
    })
  }

  // ── 전역 Job 상태 폴링 시작 (사이드바 작업중 표시용) ──────────
  // 인증된 경우에만 폴링 시작. 비로그인이면 Login.vue 진입 → 로그인 후 폴링은
  // router의 네비게이션 가드나 authStore.login() 후 수동 시작으로 처리.
  if (!authStore.rbacEnabled || authStore.isAuthenticated) {
    jobs.startGlobalPolling()
  }
  // ── 여백 복원 ──────────────────────────────────────────────────
  try {
    const sp = JSON.parse(localStorage.getItem('layout_spacing') || '{}')
    const r  = document.documentElement
    r.style.setProperty('--topbar-h',  (sp.top     ?? 44)  + 'px')
    r.style.setProperty('--sidebar-w', (sp.left    ?? 240) + 'px')
    r.style.setProperty('--content-p', (sp.content ?? 16)  + 'px')
  } catch {}

  const saved = localStorage.getItem('iconTheme') || 'default'
  const themes = {
    default: { '--icon-db':'#6366f1','--icon-monitor':'#14b8a6','--icon-conn':'#f59e0b','--icon-schema':'#3b82f6','--icon-map':'#8b5cf6','--icon-exp':'#06b6d4','--icon-job':'#f97316','--icon-valid':'#22c55e','--icon-conv':'#6366f1','--icon-sched':'#ec4899','--icon-rep':'#0ea5e9','--icon-set':'#64748b','--icon-plug':'#a855f7' },
    neon:    { '--icon-db':'#00f5ff','--icon-monitor':'#ff00ff','--icon-conn':'#39ff14','--icon-schema':'#00f5ff','--icon-map':'#ff00ff','--icon-exp':'#ffd700','--icon-job':'#ff6700','--icon-valid':'#39ff14','--icon-conv':'#00f5ff','--icon-sched':'#ff00ff','--icon-rep':'#00f5ff','--icon-set':'#39ff14','--icon-plug':'#ff00ff' },
    pastel:  { '--icon-db':'#ff9a9e','--icon-monitor':'#fecfef','--icon-conn':'#ffeaa7','--icon-schema':'#a8edea','--icon-map':'#fed6e3','--icon-exp':'#d4fc79','--icon-job':'#ffd1ff','--icon-valid':'#96fbc4','--icon-conv':'#a8edea','--icon-sched':'#ffeaa7','--icon-rep':'#ffd1ff','--icon-set':'#c3cfe2','--icon-plug':'#fed6e3' },
    material:{ '--icon-db':'#4285f4','--icon-monitor':'#34a853','--icon-conn':'#fbbc04','--icon-schema':'#4285f4','--icon-map':'#ea4335','--icon-exp':'#34a853','--icon-job':'#ff6d00','--icon-valid':'#34a853','--icon-conv':'#4285f4','--icon-sched':'#fbbc04','--icon-rep':'#4285f4','--icon-set':'#9e9e9e','--icon-plug':'#ab47bc' },
    kakao:   { '--icon-db':'#3c1e1e','--icon-monitor':'#3c1e1e','--icon-conn':'#3c1e1e','--icon-schema':'#3c1e1e','--icon-map':'#3c1e1e','--icon-exp':'#3c1e1e','--icon-job':'#3c1e1e','--icon-valid':'#3c1e1e','--icon-conv':'#3c1e1e','--icon-sched':'#3c1e1e','--icon-rep':'#3c1e1e','--icon-set':'#3c1e1e','--icon-plug':'#3c1e1e' },
    ocean:   { '--icon-db':'#a8edea','--icon-monitor':'#fed6e3','--icon-conn':'#ffd89b','--icon-schema':'#a8edea','--icon-map':'#d4fc79','--icon-exp':'#96fbc4','--icon-job':'#ffd89b','--icon-valid':'#96fbc4','--icon-conv':'#a8edea','--icon-sched':'#ffd89b','--icon-rep':'#fed6e3','--icon-set':'#c3cfe2','--icon-plug':'#d4fc79' },
  }
  const vars = themes[saved] || themes.default
  const root = document.documentElement
  Object.entries(vars).forEach(([k, v]) => root.style.setProperty(k, v))

  // ── 전역 키보드 단축키 (v9+) ────────────────────────────
  window.addEventListener('keydown', handleGlobalKeydown)
})

function handleGlobalKeydown(e) {
  // input/textarea 포커스 중이면 단축키 무시 (타이핑 방해 방지)
  const tag = (e.target?.tagName || '').toLowerCase()
  const isEditing = ['input', 'textarea', 'select'].includes(tag) ||
                    e.target?.isContentEditable
  if (isEditing) return

  // Ctrl+B: 사이드바 토글
  if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
    e.preventDefault()
    app.toggleSidebar()
    return
  }
  // Ctrl+Shift+L: 다크모드 전환
  if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'l') {
    e.preventDefault()
    app.toggleTheme()
    return
  }
  // Ctrl+/: 명령 팔레트 자리 (현재는 단축키 안내만)
  if ((e.ctrlKey || e.metaKey) && e.key === '/') {
    e.preventDefault()
    app.notify('명령 팔레트는 다음 버전에서 제공됩니다', 'info', 2000)
    return
  }
}

onUnmounted(() => {
  jobs.stopGlobalPolling()
  window.removeEventListener('keydown', handleGlobalKeydown)
})
</script>
<style scoped>
.app-shell{display:flex;height:100vh;overflow:hidden}
.app-body{flex:1;display:flex;flex-direction:column;min-width:0;height:100vh}
.app-main{flex:1;overflow-y:auto;background:var(--bg-tertiary);padding:var(--content-p,16px)}
</style>
