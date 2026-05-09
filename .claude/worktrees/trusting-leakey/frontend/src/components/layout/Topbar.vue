<template>
  <header class="topbar">
    <div class="bc"><span class="bc-sec">{{ route.meta?.section }}</span><span class="bc-sep">/</span><b>{{ route.meta?.title }}</b></div>
    <div class="tbr">
      <span class="sdot" :class="online?'on':'off'"></span>
      <span class="ver">v2.0.0</span>
      <button class="tbtn" @click="router.push('/jobs/wizard')">+ New Job</button>
    </div>
  </header>
</template>
<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
const route = useRoute(); const router = useRouter()
const online = ref(true)
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
.tbtn{font-size:11.5px;color:var(--text-secondary);border:0.5px solid var(--border-mid);padding:4px 10px;border-radius:var(--radius-sm);background:transparent;cursor:pointer;font-family:var(--font);transition:all .12s}
.tbtn:hover{background:var(--bg-secondary);color:var(--text-primary)}
</style>
