import { defineStore } from 'pinia'
import { jobsApi } from '@/api/index.js'

export const useJobStore = defineStore('jobs', {
  state: () => ({
    jobs:    [],
    loading: false,
    wsMap:   {},
    stats: {
      totalJobs: 0, running: 0, errors: 0,
      completedToday: 0, totalRows: 0, validateRate: 99.1,
    },
  }),

  getters: {
    runningJobs: s => s.jobs.filter(j => j.status === 'running'),
    failedJobs:  s => s.jobs.filter(j => j.status === 'error'),
  },

  actions: {
    async fetch() {
      this.loading = true
      try { this.jobs = await jobsApi.list() }
      catch (e) { console.error('[jobStore] fetch 실패', e) }
      finally { this.loading = false }
    },

    async fetchStats() {
      try { this.stats = await jobsApi.stats() } catch { /* 무시 */ }
    },

    async create(payload) {
      const j = await jobsApi.create(payload)
      this.jobs.unshift(j)
      return j
    },

    async pause(id) {
      await jobsApi.pause(id)
      this._setStatus(id, 'paused')
    },

    async resume(id) {
      await jobsApi.resume(id)
      this._setStatus(id, 'running')
    },

    async stop(id) {
      await jobsApi.stop(id)
      this._setStatus(id, 'aborted')
    },

    async del(id) {
      await jobsApi.del(id)
      this.jobs = this.jobs.filter(j => j.id !== id)
      this.disconnectWs(id)
    },

    async restart(id, extraPayload = {}) {
      const newJob = await jobsApi.restart(id, extraPayload)
      // 기존 Job 상태 초기화
      const existing = this.jobs.find(j => j.id === id)
      if (existing) {
        existing.status = 'running'; existing.progress = 0
        existing.rows_processed = 0; existing.rows_error = 0
        existing.speed = 0; existing.table_done = 0
        existing.current_table = ''; existing.error_message = null
      }
      // 새 Job 목록 맨 앞에 추가
      this.jobs.unshift(newJob)
      return newJob
    },

    _setStatus(id, status) {
      const j = this.jobs.find(j => j.id === id)
      if (j) j.status = status
    },

    // ── WebSocket ─────────────────────────────────────────
    connectWs(jobId) {
      if (this.wsMap[jobId]) return  // 이미 연결됨

      // vite 개발 프록시를 통해 연결 (절대 포트 하드코딩 금지)
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${location.host}/ws/jobs/${jobId}`)

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          const j = this.jobs.find(j => j.id === jobId)
          if (j && !data.error) {
            // new_logs는 store에 저장하지 않음 (Monitor.vue가 직접 관리)
            const { new_logs, ...rest } = data
            Object.assign(j, rest)
          }
        } catch { /* 무시 */ }
      }

      ws.onerror = () => { this.disconnectWs(jobId) }

      ws.onclose = () => {
        delete this.wsMap[jobId]
        // 아직 running 상태면 3초 후 재연결
        const j = this.jobs.find(j => j.id === jobId)
        if (j && j.status === 'running') {
          setTimeout(() => this.connectWs(jobId), 3000)
        }
      }

      this.wsMap[jobId] = ws
    },

    disconnectWs(jobId) {
      const ws = this.wsMap[jobId]
      if (ws) {
        ws.onclose = null   // 재연결 방지
        ws.close()
        delete this.wsMap[jobId]
      }
    },

    disconnectAll() {
      Object.values(this.wsMap).forEach(ws => {
        try { ws.onclose = null; ws.close() } catch { /* 무시 */ }
      })
      this.wsMap = {}
    },
  },
})
