<!--
  PrecheckCodeBlock.vue — v4
  ============================
  - 코드 블록 + 복사 버튼
  - searchHighlight prop 을 받아 코드 안에서도 검색어 하이라이트
-->
<template>
  <div class="cb-root" :class="'lang-'+lang">
    <div class="cb-header">
      <span class="cb-label">{{ label || defaultLabel }}</span>
      <button
        class="cb-copy-btn"
        :class="{ok: copied}"
        type="button"
        @click="handleCopy"
      >
        <svg v-if="!copied" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" class="cb-ic">
          <rect x="4" y="4" width="9" height="10" rx="1"/>
          <path d="M10 2H4a1 1 0 0 0-1 1v9"/>
        </svg>
        <svg v-else viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" class="cb-ic">
          <polyline points="3,8 7,12 13,4"/>
        </svg>
        {{ copied ? '복사됨' : '복사' }}
      </button>
    </div>
    <pre class="cb-code"><code v-html="renderedCode"></code></pre>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAppStore } from '@/store/appStore.js'

const props = defineProps({
  code:  { type: String, required: true },
  label: { type: String, default: '' },
  lang:  { type: String, default: 'sql' },
  searchHighlight: { type: String, default: '' },
})

const emit = defineEmits(['copied'])
const app = useAppStore()
const copied = ref(false)

const defaultLabel = computed(() => ({
  sql:        'SQL',
  ini:        '설정 파일 (my.cnf)',
  bash:       'Shell',
  powershell: 'PowerShell',
}[props.lang] || 'Code'))

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const renderedCode = computed(() => {
  const escaped = escapeHtml(props.code || '')
  const q = (props.searchHighlight || '').trim()
  if (!q) return escaped
  const pattern = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const re = new RegExp(pattern, 'gi')
  return escaped.replace(re, m => `<mark class="cb-hl">${m}</mark>`)
})

async function handleCopy() {
  const doFallback = () => {
    const ta = document.createElement('textarea')
    ta.value = props.code
    ta.style.position = 'fixed'
    ta.style.left = '-9999px'
    document.body.appendChild(ta)
    ta.select()
    try { document.execCommand('copy') } finally { document.body.removeChild(ta) }
  }
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(props.code)
    } else {
      doFallback()
    }
    copied.value = true
    emit('copied')
    setTimeout(() => { copied.value = false }, 1800)
  } catch {
    try {
      doFallback()
      copied.value = true
      emit('copied')
      setTimeout(() => { copied.value = false }, 1800)
    } catch {
      app?.notify && app.notify('복사 실패 — 브라우저 권한을 확인해주세요', 'error')
    }
  }
}
</script>

<style scoped>
.cb-root{
  background:var(--bg-secondary);
  border:0.5px solid var(--border-light);
  border-radius:var(--radius-md);
  overflow:hidden;
  margin-top:8px;
}
.cb-header{
  display:flex; justify-content:space-between; align-items:center;
  padding:6px 10px;
  background:var(--bg-tertiary);
  border-bottom:0.5px solid var(--border-light);
}
.cb-label{
  font-size:10.5px;
  color:var(--text-tertiary);
  font-family:ui-monospace,'SF Mono',Consolas,Menlo,monospace;
  letter-spacing:.2px;
}
.cb-copy-btn{
  display:inline-flex; align-items:center; gap:4px;
  padding:3px 8px;
  font-size:10.5px; font-weight:500;
  color:var(--text-info);
  background:transparent;
  border:0.5px solid var(--border-mid);
  border-radius:4px;
  font-family:var(--font);
  cursor:pointer; transition:all .12s;
}
.cb-copy-btn:hover{
  background:var(--bg-info);
  border-color:var(--accent-blue);
}
.cb-copy-btn.ok{
  color:var(--text-success);
  background:var(--bg-success);
  border-color:var(--accent-green);
}
.cb-ic{width:11px;height:11px}
.cb-code{
  margin:0; padding:10px 12px;
  font-family:ui-monospace,'SF Mono',Consolas,Menlo,monospace;
  font-size:12px; line-height:1.55;
  color:var(--text-primary);
  background:transparent;
  overflow-x:auto; white-space:pre;
  max-height:360px; overflow-y:auto;
}
.cb-code code{
  font-family:inherit;
  background:none; padding:0; color:inherit;
}
.cb-code :deep(.cb-hl){
  background:rgba(239,159,39,.35);
  color:inherit;
  padding:0 2px; border-radius:2px;
  font-weight:500;
}
.lang-sql .cb-header{border-left:2px solid var(--accent-blue)}
.lang-ini .cb-header{border-left:2px solid var(--text-warning)}
.lang-bash .cb-header,
.lang-powershell .cb-header{border-left:2px solid var(--accent-green)}
.cb-code::-webkit-scrollbar{height:6px;width:6px}
.cb-code::-webkit-scrollbar-thumb{background:var(--border-mid);border-radius:3px}
.cb-code::-webkit-scrollbar-track{background:transparent}
</style>
