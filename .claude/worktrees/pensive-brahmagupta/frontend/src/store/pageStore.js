import { defineStore } from 'pinia'

// 페이지별 상태 영속화 스토어
// keep-alive로 컴포넌트가 캐싱되어 있어도
// 브라우저 새로고침 시 복원을 위한 백업용

export const usePageStore = defineStore('page', {
  state: () => ({
    // SQL 변환기
    sqlConverter: {
      srcDb:       localStorage.getItem('sc_srcDb')   || 'mssql',
      tgtDb:       localStorage.getItem('sc_tgtDb')   || 'mysql',
      convEngine:  localStorage.getItem('sc_engine')  || 'none',
      textSrc:     sessionStorage.getItem('sc_src')   || '',
      textResult:  sessionStorage.getItem('sc_result')|| '',
      textChanges: [],
      lastMethod:  '',
    },
    // 검증 & 대사
    validate: {
      vType:      'table',
      mode:       localStorage.getItem('val_mode') || 'row_count',
      filterMode: 'all',
      selTables:  [],
      results:    [],
      summary:    null,
      lastResultMap: {},
      history:    [],
      // 오브젝트 검증 — 화면 이동해도 유지
      objResults:      [],
      objTesting:      false,
      objTestIdx:      0,
      objTestTotal:    0,
      objTestCurName:  '',
      objDetailRows:   {},
      selObjTypes:     [],
    },
    // Job 모니터
    jobMonitor: {
      selectedJobId: sessionStorage.getItem('jm_jobId') || '',
      filterStatus:  'all',
      filterType:    'all',
      searchText:    '',
    },
    // 오브젝트 탐색기
    objectExplorer: {
      selectedDb:   '',
      expandedNodes: [],
      searchText:   '',
    },
  }),

  actions: {
    // SQL 변환기
    saveSqlConverter(state) {
      Object.assign(this.sqlConverter, state)
      if (state.srcDb)      localStorage.setItem('sc_srcDb',   state.srcDb)
      if (state.tgtDb)      localStorage.setItem('sc_tgtDb',   state.tgtDb)
      if (state.convEngine) localStorage.setItem('sc_engine',  state.convEngine)
      if (state.textSrc    !== undefined) sessionStorage.setItem('sc_src',    state.textSrc)
      if (state.textResult !== undefined) sessionStorage.setItem('sc_result', state.textResult)
    },

    // 검증
    saveValidate(state) {
      Object.assign(this.validate, state)
      if (state.mode) localStorage.setItem('val_mode', state.mode)
    },
    saveObjResults(results) {
      this.validate.objResults = results
    },
    saveObjTestingState(state) {
      Object.assign(this.validate, state)
    },

    // Job 모니터
    saveJobMonitor(state) {
      Object.assign(this.jobMonitor, state)
      if (state.selectedJobId !== undefined)
        sessionStorage.setItem('jm_jobId', state.selectedJobId)
    },

    clearSqlConverter() {
      this.sqlConverter.textSrc    = ''
      this.sqlConverter.textResult = ''
      this.sqlConverter.textChanges = []
      this.sqlConverter.lastMethod  = ''
      sessionStorage.removeItem('sc_src')
      sessionStorage.removeItem('sc_result')
    },
  },
})
