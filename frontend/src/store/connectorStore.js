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
    loadedProfileId: null,  // v9 패치 #5: 불러온 프로파일 ID (암호문 복원용)
    loadedJobId:     null,  // v90.55: 활성 Job 으로 채운 경우 Job ID (암호문 복원용)
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
        // v9 패치 #5: 불러온 프로파일의 마스크 비번을 그대로 보내면 백엔드에서
        //           profile_id + side 로 저장된 암호문을 복원해서 사용함.
        // v90.55: loadedJobId 도 동일 패턴으로 사용 (활성 Job 의 password 복원)
        const payload = {
          db_type:  c.dbType,
          host:     c.host,
          port:     c.port,
          username: c.username,
          password: c.password,
          database: c.database,
          version:  c.version,
          side:     side,                          // 'source' | 'target'
        }
        if (this.loadedProfileId) {
          payload.profile_id = this.loadedProfileId
        }
        if (this.loadedJobId) {
          payload.job_id = this.loadedJobId  // v90.55
        }
        const r = await connectorApi.test(payload)
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

      // v10 #23: 같은 프로파일을 다시 적용하면서 이미 연결 테스트 ok 상태라면
      //          status/latency/versionResult 를 **유지**한다.
      //          기존엔 무조건 'idle' 로 돌려버려서, 프로파일 불러오기 → 접속 테스트 →
      //          JobWizard 이동 중 어딘가에서 applyProfile 가 또 불리면 전부 초기화되던 문제 해결.
      const sameProfile = this.loadedProfileId && p.id && this.loadedProfileId === p.id
      const keepSrc = sameProfile && this.source.status === 'ok'
      const keepTgt = sameProfile && this.target.status === 'ok'

      this.source = {
        ...blank(sdb), ...s,
        dbType:  sdb,
        status:  keepSrc ? this.source.status  : 'idle',
        latency: keepSrc ? this.source.latency : null,
        versionResult: keepSrc ? this.source.versionResult : '',
        message: '',
      }
      this.target = {
        ...blank(tdb), ...t,
        dbType:  tdb,
        status:  keepTgt ? this.target.status  : 'idle',
        latency: keepTgt ? this.target.latency : null,
        versionResult: keepTgt ? this.target.versionResult : '',
        message: '',
      }
      // v9 패치 #5: 불러온 프로파일 ID 기억 → testConn 시 백엔드가 암호문 복원 가능
      this.loadedProfileId = p.id || null

      // v10 #11: 최근 사용 시각 localStorage 에 기록 (프로파일 정렬용)
      // 백엔드 API 변경 없이 프론트에서만 관리 → 단일 사용자 시나리오 대응.
      try {
        if (p.id) {
          const key = 'databridge.profile.lastUsed'
          const raw = localStorage.getItem(key)
          const map = raw ? JSON.parse(raw) : {}
          map[p.id] = Date.now()
          localStorage.setItem(key, JSON.stringify(map))
        }
      } catch (e) {
        // localStorage 에러 (privacy mode 등) 시 조용히 무시 — 기능 동작엔 영향 없음
      }
    },

    /**
     * v90.55 신규: 활성 Job 의 연결정보를 connector store 에 적용.
     * 
     * 검증 화면(Validate.vue) 등에서 이관 진행 중인 Job 의 연결정보를
     * 자동으로 가져와 별도 연결 작업 없이 검증 가능하게 함.
     * 
     * 보안 원칙 (v9 패치 #5 의 applyProfile 패턴 동일):
     *   - source/target 의 host/port/database 등 표시용 정보만 채움
     *   - password 는 마스크(MASK_TOKEN) 만 받음
     *   - 실제 password 는 backend 가 loadedJobId 로 자동 복원
     *   - testConn 호출 시 payload.job_id 자동 첨부됨
     * 
     * @param {Object} job  jobStore.jobs 의 Job 객체 (또는 backend /from-job 응답)
     */
    applyJobAsConnection(job) {
      if (!job || !job.id) {
        console.warn('[connectorStore] applyJobAsConnection: invalid job', job)
        return
      }
      
      const sdb = (job.src_db || 'mysql').toLowerCase()
      const tdb = (job.tgt_db || 'mssql').toLowerCase()
      
      // source / target 채움 (password 는 마스크)
      this.source = {
        ...blank(sdb),
        dbType:   sdb,
        host:     job.src_host || '',
        port:     job.src_port || DB_META[sdb]?.port || 3306,
        username: job.src_username || '',
        password: '●●●●●●●●',  // MASK_TOKEN — backend 가 job_id 로 복원
        database: job.src_database || '',
        version:  job.src_version || '',
        status:   'idle',
      }
      this.target = {
        ...blank(tdb),
        dbType:   tdb,
        host:     job.tgt_host || '',
        port:     job.tgt_port || DB_META[tdb]?.port || 3306,
        username: job.tgt_username || '',
        password: '●●●●●●●●',  // MASK_TOKEN — backend 가 job_id 로 복원
        database: job.tgt_database || '',
        version:  job.tgt_version || '',
        status:   'idle',
      }
      
      // v90.55: Job ID 기억 → testConn / API 호출 시 backend 가 password 복원
      this.loadedJobId     = job.id
      this.loadedProfileId = null  // Job 모드일 때는 profile 모드 해제
    },

    /**
     * v10 #23: 연결 상태 초기화
     *
     * JobWizard onMounted 등에서 "잔상 제거" 목적으로 호출하던 함수.
     * 과거엔 무조건 blank 로 밀었으나, 사용자가 방금 테스트한 ok 상태까지
     * 날려버리는 부작용이 있어서 **조건부 동작** 으로 변경.
     *
     * @param {Object} opts
     * @param {boolean} opts.force  true 이면 무조건 초기화 (기본 false)
     *
     * - force=false (기본): source/target 모두 ok 상태면 **아무것도 안 함**.
     *   하나라도 ok 아니면 그 쪽만 idle 로 정리.
     * - force=true: 둘 다 무조건 blank. "+ New Job" 처럼 완전 리셋 시 사용.
     */
    resetConnections(opts = {}) {
      const force = !!opts.force
      if (force) {
        this.source = blank('mysql')
        this.target = blank('mssql')
        this.loadedProfileId = null
        this.loadedJobId     = null  // v90.55
        return
      }
      // 비-force: ok 인 쪽은 건드리지 않음
      if (this.source.status !== 'ok') {
        this.source = { ...this.source, status: 'idle', latency: null, message: '' }
      }
      if (this.target.status !== 'ok') {
        this.target = { ...this.target, status: 'idle', latency: null, message: '' }
      }
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
