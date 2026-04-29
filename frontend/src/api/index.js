import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1', timeout: 20000 })

// ── 인증 토큰 관리 (localStorage) ───────────────────────
// RBAC 활성일 때 모든 요청에 X-Auth-Token 헤더를 자동 주입.
const TOKEN_KEY = 'databridge_auth_token'

export function getAuthToken() {
  try { return localStorage.getItem(TOKEN_KEY) || '' } catch { return '' }
}
export function setAuthToken(t) {
  try {
    if (t) localStorage.setItem(TOKEN_KEY, t)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {}
}
export function clearAuthToken() { setAuthToken('') }

// ── 요청 인터셉터: 토큰 헤더 자동 주입 ──────────────────
api.interceptors.request.use(cfg => {
  const t = getAuthToken()
  if (t) {
    cfg.headers = cfg.headers || {}
    cfg.headers['X-Auth-Token'] = t
  }
  return cfg
})

// ────────────────────────────────────────────────────────────
// v9 패치 #3: 레거시 페이지 구제 — 원시 axios + 원시 fetch
// ────────────────────────────────────────────────────────────
// 기존 페이지 100+ 곳이 `api/index.js`의 axios 인스턴스를 안 쓰고
// 순정 `import axios from 'axios'` 를 직접 호출하거나 원시 fetch()로
// /api/v1/* 를 부릅니다. 이 요청들은 인터셉터가 없어 토큰이 안 실리고 401.
//
// 100+ 곳을 일일이 고치는 대신, 전역 default axios와 window.fetch 에
// 동일한 토큰 주입 로직을 추가하여 일괄 해결.

// 1) 순정 axios 에도 같은 인터셉터
axios.interceptors.request.use(cfg => {
  const t = getAuthToken()
  if (t) {
    cfg.headers = cfg.headers || {}
    if (!cfg.headers['X-Auth-Token']) {
      cfg.headers['X-Auth-Token'] = t
    }
  }
  return cfg
})

// 2) window.fetch monkey-patch (자체 API 경로에만 토큰 주입)
if (typeof window !== 'undefined' && window.fetch) {
  const _originalFetch = window.fetch.bind(window)
  window.fetch = function patchedFetch(input, init = {}) {
    try {
      const url =
        typeof input === 'string' ? input :
        (input && input.url) || ''
      // 자체 API(/api/v1/, localhost:8000) 에만 토큰 주입
      const isOurApi =
        url.startsWith('/api/') ||
        url.startsWith('api/') ||
        url.includes('://localhost:8000/') ||
        url.includes('://127.0.0.1:8000/')
      if (isOurApi) {
        const t = getAuthToken()
        if (t) {
          init = { ...init }
          // Headers 객체 또는 plain object 모두 지원
          if (init.headers instanceof Headers) {
            if (!init.headers.has('X-Auth-Token')) {
              init.headers.set('X-Auth-Token', t)
            }
          } else {
            init.headers = { ...(init.headers || {}) }
            if (!init.headers['X-Auth-Token']) {
              init.headers['X-Auth-Token'] = t
            }
          }
        }
      }
    } catch (_e) { /* 헤더 주입 실패해도 fetch 자체는 계속 */ }
    return _originalFetch(input, init)
  }
}

// ── 전역 에러 인터셉터 (appStore 연동 + 401/403 처리) ────
api.interceptors.response.use(
  r => r,
  e => {
    const status = e.response?.status
    const url    = String(e.config?.url || '')

    // 401 처리 정책 (v9 패치 #2):
    //   - /auth/login 이나 /auth/me 호출 자체가 401 → 토큰 무효 확정 → 삭제
    //   - 그 외 엔드포인트의 401 → 단순 에러로 전파 (토큰 건드리지 않음)
    //     이유: Dashboard 초기 폴링 레이스 컨디션으로 토큰이 있는데도 401 날 수 있음.
    //           그때마다 clearAuthToken()하면 로그인 직후에도 세션이 날아감.
    //     진짜 만료면 /auth/me가 실패하면서 authStore.init()이 정리함.
    if (status === 401) {
      const isAuthEndpoint = url.includes('/auth/login') || url.includes('/auth/me')
      if (isAuthEndpoint) {
        clearAuthToken()
        if (!String(window.location?.hash || '').includes('/login')
            && !String(window.location?.pathname || '').includes('/login')) {
          try { window.location.hash = '#/login' } catch {}
        }
      }
      // 다른 엔드포인트의 401은 토큰 건드리지 않고 단순 전파
    }

    // pinia 스토어는 컴포넌트 밖에서도 사용 가능하지만
    // 순환 import 방지를 위해 동적으로 import
    import('@/store/appStore.js').then(({ useAppStore }) => {
      const app = useAppStore()
      // noToast 옵션이 있는 요청은 토스트 생략 (조용한 폴링용)
      if (!e.config?._noToast) {
        app.handleApiError(e)
      }
    }).catch(() => {
      console.error('[API]', status, e.config?.url, e.message)
    })
    return Promise.reject(e)
  }
)

/** 조용한 요청 (에러 토스트 생략) */
export function silent(config = {}) {
  return { ...config, _noToast: true }
}

// ── 공통 유틸 ─────────────────────────────────────────────
const d = r => r.data

// ── Connector ─────────────────────────────────────────────
export const connectorApi = {
  test:          p      => api.post('/connectors/test', p).then(d),
  getProfiles:   ()     => api.get('/connectors/profiles').then(d),
  getProfile:    id     => api.get(`/connectors/profiles/${id}`).then(d),
  saveProfile:   p      => api.post('/connectors/profiles', p).then(d),
  updateProfile: (id,p) => api.put(`/connectors/profiles/${id}`, p).then(d),
  deleteProfile: id     => api.delete(`/connectors/profiles/${id}`),
}

// ── Jobs ──────────────────────────────────────────────────
export const jobsApi = {
  list:    ()       => api.get('/jobs/', silent()).then(d),
  get:     id       => api.get(`/jobs/${id}`, silent()).then(d),
  create:  p        => api.post('/jobs/', p).then(d),
  pause:   id       => api.post(`/jobs/${id}/pause`).then(d),
  resume:  id       => api.post(`/jobs/${id}/resume`).then(d),
  stop:    id       => api.post(`/jobs/${id}/stop`).then(d),
  del:     id       => api.delete(`/jobs/${id}`),
  bulkDel: ids      => api.post('/jobs/bulk-delete', { ids }).then(d),
  logs:    id       => api.get(`/jobs/${id}/logs`, silent()).then(d),
  restart: (id, p)  => api.post(`/jobs/${id}/restart`, p || {}).then(d),
  stats:   ()       => api.get('/jobs/stats', silent()).then(d),
}

// ── Schedules ─────────────────────────────────────────────
export const scheduleApi = {
  list:   ()   => api.get('/jobs/schedules', silent()).then(d),
  create: p    => api.post('/jobs/schedules', p).then(d),
  del:    id   => api.delete(`/jobs/schedules/${id}`),
  runNow: id   => api.post(`/jobs/schedules/${id}/run-now`).then(d),
}

// ── Schema ────────────────────────────────────────────────
export const schemaApi = {
  connect:         p           => api.post('/schema/connection', p).then(d),
  tables:          cid         => api.get(`/schema/${cid}/tables`, silent()).then(d),
  tablesByParams:  params      => api.get('/schema/tables', { params }).then(d),
  detail:          (cid, t)    => api.get(`/schema/${cid}/tables/${t}`).then(d),
  diff:            (s, t, tbl) => api.get('/schema/diff', { params: { src: s, tgt: t, table: tbl } }).then(d),
  ddl:             (cid, tbls) => api.post(`/schema/${cid}/ddl`, { tables: tbls }).then(d),
  deps:            (cid, t)    => api.get(`/schema/${cid}/deps`, { params: { table: t } }).then(d),
  objects:         params      => api.get('/schema/objects', { params }).then(d),
  warnings:        p           => api.post('/schema/analyze-warnings', p).then(d),
  convertObject:   p           => api.post('/schema/convert-object', p).then(d),
  executeObject:   p           => api.post('/schema/execute-object', p).then(d),
}

// ── Mapping ───────────────────────────────────────────────
export const mappingApi = {
  list:   (s, t) => api.get('/mapping/rules', { params: { src_db: s, tgt_db: t } }).then(d),
  create: p      => api.post('/mapping/rules', p).then(d),
  update: (id,p) => api.put(`/mapping/rules/${id}`, p).then(d),
  del:    id     => api.delete(`/mapping/rules/${id}`),
}

// ── SQL Converter ─────────────────────────────────────────
export const sqlApi = {
  convert: p => api.post('/sql-converter/convert', p).then(d),
}

// ── Validate ──────────────────────────────────────────────
export const validateApi = {
  run:     p => api.post('/validate/run', p).then(d),
  history: () => api.get('/validate/history', silent()).then(d),
}

// ── Report ────────────────────────────────────────────────
export const reportApi = {
  history:   p          => api.get('/report/history', { params: p }).then(d),
  stats:     ()         => api.get('/report/stats', silent()).then(d),
  export:    (id, fmt)  => api.get(`/report/export/${id}`, { params: { format: fmt }, responseType: 'blob' }).then(d),
  exportAll: (fmt)      => api.get('/report/export-all', { params: { format: fmt }, responseType: 'blob' }).then(d),
}

// ── Settings ──────────────────────────────────────────────
export const settingsApi = {
  get:         ()       => api.get('/settings/').then(d),
  update:      p        => api.put('/settings/', p).then(d),
  testApiKey:  ()       => api.post('/settings/api-key-test').then(d),
  logTail:     (n, src) => api.get('/settings/log-tail', { params: { lines: n, source: src }, ...silent() }).then(d),
  logInfo:     src      => api.get('/settings/log-info', { params: { source: src }, ...silent() }).then(d),
  logInfoBoth: ()       => api.get('/settings/log-info-both', silent()).then(d),
  logRotate:   ()       => api.post('/settings/log-rotate').then(d),
  frontendLog: p        => api.post('/settings/frontend-log', p, silent()).then(d),
}

// ── Auth (RBAC) ────────────────────────────────────────
export const authApi = {
  status:         ()     => api.get('/auth/status', silent()).then(d),
  login:          p      => api.post('/auth/login', p).then(d),
  logout:         ()     => api.post('/auth/logout').then(d),
  me:             ()     => api.get('/auth/me', silent()).then(d),
  changePassword: p      => api.post('/auth/change-password', p).then(d),
  listUsers:      ()     => api.get('/auth/users').then(d),
  createUser:     p      => api.post('/auth/users', p).then(d),
  updateUser:     (u, p) => api.put(`/auth/users/${u}`, p).then(d),
  resetPassword:  (u, p) => api.post(`/auth/users/${u}/reset-password`, p).then(d),
  deleteUser:     u      => api.delete(`/auth/users/${u}`),
}
