import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1', timeout: 20000 })

// ── 전역 에러 인터셉터 (appStore 연동) ───────────────────
api.interceptors.response.use(
  r => r,
  e => {
    // pinia 스토어는 컴포넌트 밖에서도 사용 가능하지만
    // 순환 import 방지를 위해 동적으로 import
    import('@/store/appStore.js').then(({ useAppStore }) => {
      const app = useAppStore()
      // noToast 옵션이 있는 요청은 토스트 생략 (조용한 폴링용)
      if (!e.config?._noToast) {
        app.handleApiError(e)
      }
    }).catch(() => {
      // 스토어 로드 실패 시 콘솔에만 출력
      console.error('[API]', e.response?.status, e.config?.url, e.message)
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
