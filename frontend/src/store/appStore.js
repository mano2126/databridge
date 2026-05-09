import { defineStore } from 'pinia'

const _LS = {
  get(key, defaultVal) {
    try {
      const v = localStorage.getItem(key)
      return v == null ? defaultVal : v
    } catch { return defaultVal }
  },
  set(key, val) {
    try { localStorage.setItem(key, String(val)) } catch {}
  },
}

export const useAppStore = defineStore('app', {
  state: () => ({
    theme:            _LS.get('theme', 'light'),
    sidebarCollapsed: _LS.get('sidebarCollapsed', 'false') === 'true',

    // ── UI 커스터마이즈 (v9+) ────────────────────────────
    density:          _LS.get('density', 'comfortable'),    // compact | comfortable | spacious
    fontSize:         parseInt(_LS.get('fontSize', '14')),  // 12~18 px
    accentColor:      _LS.get('accentColor', '#1f6feb'),    // 포인트 색
    reducedMotion:    _LS.get('reducedMotion', 'false') === 'true',   // 애니메이션 감소
    highContrast:     _LS.get('highContrast', 'false') === 'true',    // 고대비 모드
    sidebarWidth:     parseInt(_LS.get('sidebarWidth', '240')),       // 200~360 px
    mascot:           _LS.get('mascot', 'person'),                    // person | cat | dog | robot | ghost | none

    toasts:           [],
    toast: { show: false, msg: '', type: 'info' },

    // ════════════════════════════════════════════════════════════════
    // v95_p7 (2026-05-02) 본부장님 명령 — 좌측 메뉴 진행 표시기
    //   "진행되고 있는 화면의 경우 왼쪽 메뉴 오른쪽에 수레바퀴"
    //   "어느 페이지에서 작업 수행 중인지 알 수 있어야"
    //
    // 본질 진단:
    //   기존 busyRoutes 는 *이관 작업 (Job)* 만 인식
    //   검증 작업 (테이블/오브젝트) 은 컴포넌트 로컬 상태 → 좌측 인식 X
    //
    // 본질 처방:
    //   검증 진행 상태를 *전역 store* 로 승격
    //   - validateRunning: 어떤 검증이 진행 중인지 (table | object | null)
    //   - validateProgress: { current, total, label }
    //   Sidebar 가 이 상태 보고 수레바퀴 표시
    // ════════════════════════════════════════════════════════════════
    validateRunning:  null,                     // null | 'table' | 'object'
    validateProgress: { current: 0, total: 0, label: '' },
  }),

  actions: {
    toggleTheme() {
      this.theme = this.theme === 'light' ? 'dark' : 'light'
      _LS.set('theme', this.theme)
      this.applyTheme()
    },

    setTheme(t) {
      if (['light', 'dark', 'auto'].includes(t)) {
        this.theme = t
        _LS.set('theme', t)
        this.applyTheme()
      }
    },

    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
      _LS.set('sidebarCollapsed', this.sidebarCollapsed)
    },

    setDensity(d) {
      if (['compact', 'comfortable', 'spacious'].includes(d)) {
        this.density = d
        _LS.set('density', d)
        this.applyUI()
      }
    },

    setFontSize(n) {
      const v = Math.max(12, Math.min(18, parseInt(n) || 14))
      this.fontSize = v
      _LS.set('fontSize', v)
      this.applyUI()
    },

    setAccentColor(c) {
      if (/^#[0-9a-f]{6}$/i.test(c)) {
        this.accentColor = c
        _LS.set('accentColor', c)
        this.applyUI()
      }
    },

    setReducedMotion(v) {
      this.reducedMotion = !!v
      _LS.set('reducedMotion', this.reducedMotion)
      this.applyUI()
    },

    setHighContrast(v) {
      this.highContrast = !!v
      _LS.set('highContrast', this.highContrast)
      this.applyUI()
    },

    setSidebarWidth(n) {
      const v = Math.max(200, Math.min(360, parseInt(n) || 240))
      this.sidebarWidth = v
      _LS.set('sidebarWidth', v)
      document.documentElement.style.setProperty('--sidebar-w', v + 'px')
    },

    // v10: 마스코트 캐릭터 선택 (선택된 메뉴에서 걷는 애니메이션)
    setMascot(m) {
      const valid = ['person', 'cat', 'dog', 'robot', 'ghost', 'none']
      if (!valid.includes(m)) m = 'person'
      this.mascot = m
      _LS.set('mascot', m)
      document.documentElement.setAttribute('data-mascot', m)
    },

    /**
     * 모든 UI 설정을 문서 루트에 적용 — 기동 시 1회 + 변경 시마다 호출.
     */
    applyUI() {
      const r = document.documentElement
      // 밀도: CSS var --row-h, --gap 등에 반영
      const densityMap = {
        compact:      { row: 28, gap: 6,  pad: 8 },
        comfortable:  { row: 36, gap: 10, pad: 12 },
        spacious:     { row: 44, gap: 14, pad: 16 },
      }
      const d = densityMap[this.density] || densityMap.comfortable
      r.style.setProperty('--density-row-h', d.row + 'px')
      r.style.setProperty('--density-gap',   d.gap + 'px')
      r.style.setProperty('--density-pad',   d.pad + 'px')

      // 폰트 크기
      r.style.setProperty('--base-font-size', this.fontSize + 'px')
      r.style.fontSize = this.fontSize + 'px'

      // 포인트 색
      r.style.setProperty('--accent', this.accentColor)
      r.style.setProperty('--accent-hover', _darken(this.accentColor, 12))

      // 사이드바 너비
      r.style.setProperty('--sidebar-w', this.sidebarWidth + 'px')

      // 접근성 플래그
      r.classList.toggle('reduced-motion', this.reducedMotion)
      r.classList.toggle('high-contrast',  this.highContrast)

      // v10: 마스코트
      r.setAttribute('data-mascot', this.mascot || 'person')
    },

    applyTheme() {
      // 'auto'는 OS 설정 따라감
      let t = this.theme
      if (t === 'auto') {
        t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
      }
      document.documentElement.setAttribute('data-theme', t)
    },

    /** 모든 커스터마이즈 초기화 */
    resetUI() {
      this.density = 'comfortable'
      this.fontSize = 14
      this.accentColor = '#1f6feb'
      this.reducedMotion = false
      this.highContrast = false
      this.sidebarWidth = 240
      this.mascot = 'person'
      ;['density', 'fontSize', 'accentColor', 'reducedMotion', 'highContrast', 'sidebarWidth', 'mascot']
        .forEach(k => _LS.set(k, { density:'comfortable', fontSize:14,
          accentColor:'#1f6feb', reducedMotion:false, highContrast:false,
          sidebarWidth:240, mascot:'person' }[k]))
      this.applyUI()
    },

    notify(msg, type = 'info', duration = 3000) {
      const id = Date.now() + Math.random()
      this.toasts.push({ id, msg, type })
      if (this.toasts.length > 5) this.toasts.shift()
      setTimeout(() => this.dismiss(id), duration)
      this.toast = { show: true, msg, type }
      clearTimeout(this._legacyTimer)
      this._legacyTimer = setTimeout(() => { this.toast.show = false }, duration)
    },

    dismiss(id) {
      const idx = this.toasts.findIndex(t => t.id === id)
      if (idx >= 0) this.toasts.splice(idx, 1)
    },

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

    // ════════════════════════════════════════════════════════════════
    // v95_p7 (2026-05-02) 검증 진행 상태 actions
    // ════════════════════════════════════════════════════════════════
    setValidateRunning(kind, total = 0, label = '') {
      // kind: 'table' | 'object' | null
      this.validateRunning = kind
      this.validateProgress = { current: 0, total, label }
    },
    updateValidateProgress(current, label = '') {
      if (this.validateRunning) {
        this.validateProgress.current = current
        if (label) this.validateProgress.label = label
      }
    },
    clearValidateRunning() {
      this.validateRunning = null
      this.validateProgress = { current: 0, total: 0, label: '' }
    },
  },
})

// ── 유틸: 색 어둡게 ───────────────────────────────────
function _darken(hex, pct) {
  const c = hex.replace('#', '')
  const num = parseInt(c, 16)
  let r = (num >> 16) & 0xff
  let g = (num >> 8) & 0xff
  let b = num & 0xff
  r = Math.max(0, r - Math.round((r * pct) / 100))
  g = Math.max(0, g - Math.round((g * pct) / 100))
  b = Math.max(0, b - Math.round((b * pct) / 100))
  return '#' + [r, g, b].map(x => x.toString(16).padStart(2, '0')).join('')
}
