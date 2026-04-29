import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

export const useConverterStore = defineStore('converter', () => {

  // ── 상태 (화면 이탈 후 복귀해도 유지) ──────────────────────
  const srcDb       = ref('mssql')
  const tgtDb       = ref('mysql')
  const convEngine  = ref('claude')
  const namingMode  = ref('trans')
  // v90.48: schema 정책 (테이블 이관과 동일하게 sql 변환에도 적용)
  //   underscore: customer.profile → customer_profile (권장)
  //   drop:       customer.profile → profile
  //   database:   별도 DB
  const schemaStrategy = ref('underscore')

  const folderFiles    = ref([])   // {name, handle, selected, converted, method}
  const tgtFiles       = ref([])
  const convertReport  = ref([])
  const folderProgress = ref({ total:0, done:0, changes:0, ok:0, fail:0, aiUsed:0 })

  // ── v91 (2026-04-29): 텍스트/파일/튜닝 상태 보존 ─────────────
  // 본부장님 호소 ②: "다른 화면 갔다 오면 초기화 되는거 막아줘"
  const textSrc        = ref('')
  const textResult     = ref('')
  const textChanges    = ref([])
  const textWarnings   = ref([])
  const lastMethod     = ref('')
  
  // 파일 모드 (handle 은 직렬화 안 되니 메모리만)
  const fileItems      = ref([])   // {name, content, converted, changes, warnings, status}
  const fileBatchProgress = ref({ total:0, done:0, ok:0, fail:0, currentName:'' })
  const fileBatchRunning  = ref(false)
  
  // 튜닝 (텍스트 모드)
  const tuneResults     = ref([])
  const tuneBaseMetrics = ref(null)
  const tuneTokensUsed  = ref(0)
  const tuneMeasure     = ref('both')

  const running   = ref(false)
  const paused    = ref(false)
  const stopped   = ref(false)
  const runningIdx = ref(-1)

  // ── 내부 ──────────────────────────────────────────────────
  let _pauseResolve = null

  async function _waitIfPaused() {
    while (paused.value && !stopped.value) {
      await new Promise(r => { _pauseResolve = r })
    }
  }

  // ── 실행 제어 ──────────────────────────────────────────────
  function pause()   { paused.value = true }
  function unpause() {
    paused.value = false
    if (_pauseResolve) { _pauseResolve(); _pauseResolve = null }
  }
  function stop()    {
    stopped.value = true
    paused.value = false
    if (_pauseResolve) { _pauseResolve(); _pauseResolve = null }
  }
  function reset() {
    running.value = false; paused.value = false; stopped.value = false
    runningIdx.value = -1; folderProgress.value = { total:0,done:0,changes:0,ok:0,fail:0,aiUsed:0 }
    folderFiles.value = []; tgtFiles.value = []; convertReport.value = []
  }
  
  // v91: 전체 초기화 (본부장님 호소 ①)
  function resetAll() {
    reset()
    textSrc.value = ''; textResult.value = ''
    textChanges.value = []; textWarnings.value = []
    lastMethod.value = ''
    fileItems.value = []
    fileBatchProgress.value = { total:0, done:0, ok:0, fail:0, currentName:'' }
    fileBatchRunning.value = false
    tuneResults.value = []
    tuneBaseMetrics.value = null
    tuneTokensUsed.value = 0
  }

  // ── 폴더 변환 실행 ─────────────────────────────────────────
  async function runConvert(selected, tgtDirHandle) {
    if (running.value) return
    running.value = true
    paused.value  = false
    stopped.value = false
    folderProgress.value = { total:selected.length, done:0, changes:0, ok:0, fail:0, aiUsed:0 }
    tgtFiles.value = []
    convertReport.value = []
    const allConverted = []

    const endpoint = (convEngine.value === 'claude' || convEngine.value === 'auto')
      ? '/api/v1/sql-converter/convert-ai'
      : '/api/v1/sql-converter/convert'

    for (let i = 0; i < selected.length; i++) {
      if (stopped.value) break
      await _waitIfPaused()
      if (stopped.value) break

      runningIdx.value = i
      const f = selected[i]

      try {
        const file    = await f.handle.getFile()
        const content = await file.text()

        let data
        if (convEngine.value === 'none') {
          data = { converted: content, changes: [], warnings: ['변환 안함'], method: 'none' }
        } else {
          const resp = await axios.post(endpoint, {
            sql: content, src_db: srcDb.value, tgt_db: tgtDb.value, engine: convEngine.value
          })
          data = resp.data
        }

        const outName = namingMode.value === 'trans'
          ? f.name.replace(/(\.[^.]+)$/, '_trans$1') : f.name

        allConverted.push({ name: outName, content: data.converted })

        if (tgtDirHandle) {
          const oh = await tgtDirHandle.getFileHandle(outName, { create: true })
          const wr = await oh.createWritable()
          await wr.write(data.converted); await wr.close()
        }

        f.converted = true
        f.method = data.method || 'rules'
        tgtFiles.value.push({ name: outName, size: new Blob([data.converted]).size })
        folderProgress.value.done++
        folderProgress.value.ok++
        folderProgress.value.changes += (data.changes || []).length
        if (data.method === 'claude-ai') folderProgress.value.aiUsed++

        convertReport.value.push({
          name: f.name, outName, ok: true,
          method: data.method || 'rules',
          changes: (data.changes || []).length,
          warnings: (data.warnings || []).length,
          changesDetail: (data.changes || []).slice(0, 20),
        })
      } catch(e) {
        if (stopped.value) break
        folderProgress.value.done++
        folderProgress.value.fail++
        f.converted = false
        f.error = e.message || '오류'
        convertReport.value.push({
          name: f.name, ok: false, method: 'error', changes: 0, error: e.message || '오류'
        })
      }
    }

    runningIdx.value = -1
    running.value = false
    paused.value  = false

    if (!stopped.value && !tgtDirHandle && allConverted.length) {
      return allConverted  // ZIP 다운로드용
    }
    return null
  }

  // ── 통계 computed ──────────────────────────────────────────
  const pct         = computed(() => folderProgress.value.total
    ? Math.round(folderProgress.value.done / folderProgress.value.total * 100) : 0)
  const isDone      = computed(() =>
    !running.value && folderProgress.value.total > 0 &&
    folderProgress.value.done >= folderProgress.value.total)

  return {
    srcDb, tgtDb, convEngine, namingMode,
    schemaStrategy,  // v90.48
    folderFiles, tgtFiles, convertReport, folderProgress,
    running, paused, stopped, runningIdx,
    pct, isDone,
    pause, unpause, stop, reset, resetAll, runConvert,
    // v91: 텍스트/파일/튜닝 상태 보존
    textSrc, textResult, textChanges, textWarnings, lastMethod,
    fileItems, fileBatchProgress, fileBatchRunning,
    tuneResults, tuneBaseMetrics, tuneTokensUsed, tuneMeasure,
  }
})
