<template>
  <div class="toast-container">
    <transition-group name="toast" tag="div">
      <div
        v-for="t in app.toasts"
        :key="t.id"
        class="toast"
        :class="'toast-' + t.type"
        @click="app.dismiss(t.id)"
      >
        <span class="toast-icon">{{ ICONS[t.type] || 'ℹ' }}</span>
        <span class="toast-msg">{{ t.msg }}</span>
        <button class="toast-close" @click.stop="app.dismiss(t.id)">✕</button>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { useAppStore } from '@/store/appStore.js'
const app = useAppStore()
const ICONS = { info: 'ℹ', success: '✓', error: '✕', warn: '⚠' }
</script>

<style scoped>
.toast-container {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-end;
}
.toast {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 14px 9px 12px;
  border-radius: var(--radius-md);
  font-size: 12.5px;
  font-weight: 500;
  max-width: 360px;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(0,0,0,.18);
  pointer-events: all;
}
.toast-icon { font-size: 13px; flex-shrink: 0; }
.toast-msg  { flex: 1; line-height: 1.4; }
.toast-close {
  background: none; border: none; cursor: pointer;
  font-size: 11px; opacity: 0.6; padding: 0 0 0 4px;
  color: inherit; font-family: var(--font);
}
.toast-close:hover { opacity: 1; }

.toast-info    { background: var(--text-primary);  color: var(--bg-primary); }
.toast-success { background: #2d6b0e; color: #fff; }
.toast-error   { background: #9c2424; color: #fff; }
.toast-warn    { background: #7d4a09; color: #fff; }

.toast-enter-active { transition: all .22s ease; }
.toast-leave-active { transition: all .18s ease; }
.toast-enter-from   { opacity: 0; transform: translateX(20px); }
.toast-leave-to     { opacity: 0; transform: translateX(20px); }
.toast-move         { transition: transform .2s ease; }
</style>
