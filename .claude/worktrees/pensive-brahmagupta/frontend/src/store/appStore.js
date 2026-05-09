import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', {
  state: () => ({
    theme:            localStorage.getItem('theme') || 'light',
    sidebarCollapsed: localStorage.getItem('sidebarCollapsed') === 'true',
    toasts:           [],          // 복수 토스트 지원
    // 구버전 호환 (일부 컴포넌트가 app.toast.show 를 직접 참조)
    toast: { show: false, msg: '', type: 'info' },
  }),

  actions: {
    toggleTheme() {
      this.theme = this.theme === 'light' ? 'dark' : 'light'
      localStorage.setItem('theme', this.theme)
    },

    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
      localStorage.setItem('sidebarCollapsed', this.sidebarCollapsed)
    },

    notify(msg, type = 'info', duration = 3000) {
      const id = Date.now() + Math.random()
      this.toasts.push({ id, msg, type })

      // 최대 5개 유지
      if (this.toasts.length > 5) this.toasts.shift()

      // 자동 제거
      setTimeout(() => this.dismiss(id), duration)

      // 구버전 호환
      this.toast = { show: true, msg, type }
      clearTimeout(this._legacyTimer)
      this._legacyTimer = setTimeout(() => { this.toast.show = false }, duration)
    },

    dismiss(id) {
      const idx = this.toasts.findIndex(t => t.id === id)
      if (idx >= 0) this.toasts.splice(idx, 1)
    },

    /** 전역 API 에러 처리 — axios 인터셉터에서 호출 */
    handleApiError(error) {
      const status  = error.response?.status
      const detail  = error.response?.data?.detail || error.message || '알 수 없는 오류'
      const url     = error.config?.url || ''

      if (status === 404)      this.notify(`리소스를 찾을 수 없습니다 (${url})`, 'warn')
      else if (status === 422) this.notify(`입력값 오류: ${detail}`, 'error')
      else if (status === 500) this.notify(`서버 오류: ${detail}`, 'error')
      else if (!status)        this.notify('서버에 연결할 수 없습니다', 'error', 4000)
      else                     this.notify(`오류 ${status}: ${detail}`, 'error')
    },
  },
})
