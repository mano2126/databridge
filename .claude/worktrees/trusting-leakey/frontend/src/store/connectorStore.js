import { defineStore } from 'pinia'
import { connectorApi } from '@/api/index.js'
import { DB_META } from '@/constants/dbMeta.js'

const blank = (db) => ({
  dbType:        db,
  version:       DB_META[db]?.versions?.[0] || '',
  host:          '',
  port:          DB_META[db]?.port || 3306,
  username:      '',
  password:      '',
  database:      '',
  status:        'idle',   // idle | testing | ok | error
  latency:       null,
  versionResult: '',
  message:       '',
})

export const useConnectorStore = defineStore('connector', {
  state: () => ({
    source:   blank('mysql'),
    target:   blank('mssql'),
    profiles: [],
    loading:  false,
  }),

  getters: {
    bothConnected: s => s.source.status === 'ok' && s.target.status === 'ok',
  },

  actions: {
    changeDb(side, dbType) {
      const prev  = this[side]
      const meta  = DB_META[dbType] || {}
      this[side]  = {
        ...blank(dbType),
        host:     prev.host,
        username: prev.username,
        password: prev.password,
        database: prev.database,
        port:     meta.port || prev.port,
      }
    },

    async testConn(side) {
      const c = this[side]
      c.status  = 'testing'
      c.message = ''
      try {
        const r = await connectorApi.test({
          db_type:  c.dbType,
          host:     c.host,
          port:     c.port,
          username: c.username,
          password: c.password,
          database: c.database,
          version:  c.version,
        })
        c.status        = r.success ? 'ok' : 'error'
        c.latency       = r.latency
        c.versionResult = r.version || ''
        c.message       = r.message
      } catch (e) {
        c.status  = 'error'
        c.message = e.response?.data?.detail || e.message
      }
    },

    async loadProfiles() {
      try {
        this.profiles = await connectorApi.getProfiles()
      } catch { /* 무시 */ }
    },

    async saveProfile(name) {
      const p = await connectorApi.saveProfile({
        name,
        source: { ...this.source },
        target: { ...this.target },
      })
      this.profiles.unshift(p)
      return p
    },

    async updateProfile(id, name) {
      const p = await connectorApi.updateProfile(id, {
        name,
        source: { ...this.source },
        target: { ...this.target },
      })
      const idx = this.profiles.findIndex(x => x.id === id)
      if (idx >= 0) this.profiles[idx] = p
      return p
    },

    applyProfile(p) {
      const s   = p.source || {}
      const t   = p.target || {}
      const sdb = s.db_type || s.dbType || 'mysql'
      const tdb = t.db_type || t.dbType || 'mssql'
      this.source = { ...blank(sdb), ...s, dbType: sdb, status: 'idle', message: '' }
      this.target = { ...blank(tdb), ...t, dbType: tdb, status: 'idle', message: '' }
    },

    async removeProfile(id) {
      await connectorApi.deleteProfile(id)
      this.profiles = this.profiles.filter(p => p.id !== id)
    },

    /** 현재 소스·타겟 연결 정보를 plain object로 반환 (Job 생성 등에 활용) */
    getCredentials() {
      return {
        src_db:       this.source.dbType,
        src_host:     this.source.host,
        src_port:     this.source.port,
        src_database: this.source.database,
        src_username: this.source.username,
        src_password: this.source.password,
        tgt_db:       this.target.dbType,
        tgt_host:     this.target.host,
        tgt_port:     this.target.port,
        tgt_database: this.target.database,
        tgt_username: this.target.username,
        tgt_password: this.target.password,
      }
    },
  },
})
