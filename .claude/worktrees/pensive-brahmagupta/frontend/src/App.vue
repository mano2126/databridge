<template>
  <div class="app-shell" :data-theme="app.theme">
    <Sidebar />
    <div class="app-body">
      <Topbar />
      <main class="app-main">
        <!-- SqlVerify는 페이지 이동 후 복귀해도 상태 유지 (파일·결과 보존) -->
        <router-view v-slot="{ Component, route }">
          <keep-alive :include="['SqlVerify','Validate','JobMonitor']">
            <component :is="Component" :key="route.path" />
          </keep-alive>
        </router-view>
      </main>
    </div>
    <ToastNotif />
  </div>
</template>
<script setup>
import { onMounted } from 'vue'
import { useAppStore } from '@/store/appStore.js'
import Sidebar from '@/components/layout/Sidebar.vue'
import Topbar  from '@/components/layout/Topbar.vue'
import ToastNotif from '@/components/common/ToastNotif.vue'
const app = useAppStore()

// 저장된 아이콘 테마 초기 적용
onMounted(() => {
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
})
</script>
<style scoped>
.app-shell{display:flex;height:100vh;overflow:hidden}
.app-body{flex:1;display:flex;flex-direction:column;min-width:0;height:100vh}
.app-main{flex:1;overflow-y:auto;background:var(--bg-tertiary);padding:20px}
</style>
