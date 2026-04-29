import { defineStore } from 'pinia'
import { authApi, setAuthToken, clearAuthToken, getAuthToken } from '@/api/index.js'

/**
 * authStore
 * RBAC 상태 + 현재 사용자 + 로그인/로그아웃 흐름 관리.
 *
 * 사용처:
 *   - App.vue  : 기동 시 status/me 체크
 *   - Login.vue: 로그인 폼
 *   - 라우터 가드: hasRole(required) 로 이동 차단
 */
export const useAuthStore = defineStore('auth', {
  state: () => ({
    rbacEnabled: true,     // 서버 /auth/status 에서 초기값 채움
    initialized: false,
    user: null,            // { username, role, expires_at }
    loading: false,
    error: '',
  }),

  getters: {
    isAuthenticated: (s) => !!s.user,
    role:            (s) => s.user?.role || 'guest',
    hasRole: (s) => (required) => {
      const rank = { admin: 3, operator: 2, viewer: 1, guest: 0 }
      const cur = rank[s.user?.role || 'guest'] || 0
      const req = rank[required] || 999
      return cur >= req
    },
  },

  actions: {
    /** 앱 기동 시 1회 호출 — RBAC 활성 여부 + 토큰이 있으면 me 조회 */
    async init() {
      try {
        const st = await authApi.status()
        this.rbacEnabled = !!st.rbac_enabled
      } catch {
        this.rbacEnabled = true   // 기본은 활성으로 보수적 취급
      }
      if (!this.rbacEnabled) {
        this.user = { username: 'admin', role: 'admin', rbac_disabled: true }
        this.initialized = true
        return
      }
      // 저장된 토큰이 있으면 me 체크
      if (getAuthToken()) {
        try {
          const me = await authApi.me()
          this.user = me
        } catch {
          clearAuthToken()
          this.user = null
        }
      }
      this.initialized = true
    },

    async login(username, password) {
      this.loading = true
      this.error = ''
      try {
        const r = await authApi.login({ username, password })
        setAuthToken(r.token)
        this.user = { username: r.username, role: r.role, expires_at: r.expires_at }
        return true
      } catch (e) {
        this.error = e.response?.data?.detail || '로그인 실패'
        return false
      } finally {
        this.loading = false
      }
    },

    async logout() {
      try { await authApi.logout() } catch {}
      clearAuthToken()
      this.user = null
    },
  },
})
