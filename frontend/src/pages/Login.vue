<template>
  <div class="login-root">
    <div class="login-card">
      <div class="brand">
        <div class="logo">DB</div>
        <div>
          <h1>DataBridge Studio</h1>
          <p class="muted">엔터프라이즈 데이터 이관 플랫폼</p>
        </div>
      </div>

      <form class="form" @submit.prevent="onSubmit">
        <label>
          <span>사용자 이름</span>
          <input v-model="username" autocomplete="username"
                 autofocus required :disabled="authStore.loading"/>
        </label>
        <label>
          <span>비밀번호</span>
          <input v-model="password" type="password" autocomplete="current-password"
                 required :disabled="authStore.loading"/>
        </label>

        <div v-if="authStore.error" class="err">{{ authStore.error }}</div>

        <button type="submit" class="btn-primary" :disabled="authStore.loading">
          {{ authStore.loading ? '로그인 중...' : '로그인' }}
        </button>

        <p class="hint">
          첫 로그인은 서버 로그의 임시 admin 비번 사용. 로그인 후 즉시 변경하세요.
        </p>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/store/authStore.js'
import { useJobStore } from '@/store/jobStore.js'

const authStore = useAuthStore()
const jobStore  = useJobStore()
const router    = useRouter()
const route     = useRoute()

const username = ref('')
const password = ref('')

async function onSubmit() {
  const ok = await authStore.login(username.value, password.value)
  if (ok) {
    // v9 패치 #2: 로그인 직후 폴링 시작 (App.vue 에서 비로그인 상태로 기동 시 스킵됐으므로)
    try { jobStore.startGlobalPolling?.() } catch {}
    // 원래 가려던 페이지로 (가드가 설정한 redirect 쿼리)
    const next = route.query.next || '/'
    router.replace(next)
  }
}
</script>

<style scoped>
.login-root {
  min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #0f1925 0%, #1a2a3f 100%);
}
.login-card {
  width: 420px;
  background: #fff;
  padding: 40px;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0,0,0,.25);
}
.brand { display: flex; align-items: center; gap: 16px; margin-bottom: 32px; }
.logo {
  width: 56px; height: 56px; border-radius: 12px;
  background: linear-gradient(135deg, #1f6feb, #2ea043);
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 20px;
}
h1 { margin: 0; font-size: 20px; color: #1f2937; }
.muted { margin: 4px 0 0; font-size: 13px; color: #6b7280; }

.form { display: flex; flex-direction: column; gap: 16px; }
.form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #374151; }
.form input {
  padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 14px;
}
.form input:focus { outline: 2px solid #1f6feb33; border-color: #1f6feb; }

.btn-primary {
  background: #1f6feb; color: #fff; border: none; padding: 12px;
  border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer;
  margin-top: 8px;
}
.btn-primary:disabled { opacity: .6; cursor: not-allowed; }
.btn-primary:hover:not(:disabled) { background: #1a5fcc; }

.err {
  background: #fef2f2; color: #991b1b; padding: 8px 12px;
  border-radius: 6px; font-size: 13px; border: 1px solid #fecaca;
}
.hint {
  margin: 0; font-size: 12px; color: #6b7280; line-height: 1.5;
  padding-top: 8px; border-top: 1px solid #f3f4f6;
}
</style>
