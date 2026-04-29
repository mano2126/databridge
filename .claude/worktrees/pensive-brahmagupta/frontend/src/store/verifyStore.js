import { defineStore } from 'pinia'
import { ref, computed, reactive } from 'vue'
import axios from 'axios'

export const useVerifyStore = defineStore('verify', () => {

  // ── 상태 ──────────────────────────────────────────────
  // srcFiles/tgtFiles: 파일 메타 + 핸들을 store에서 관리 → 페이지 이동해도 유지
  // File 핸들은 직렬화 불가 → 별도 Map으로 보관, store엔 메타만 저장
  const srcFiles    = ref([])   // [{ name, size, file(File) }]
  const tgtFiles    = ref([])
  const fileResults = ref([])
  const activePair  = ref(-1)
  const running     = ref(false)
  const selectedIdxs = ref(new Set())   // 선택 재실행용
  const paused      = ref(false)   // 일시정지 상태
  const stopped     = ref(false)   // 중지 플래그
  const runningIdx  = ref(-1)
  const runProg     = ref(0)
  const reviewed    = reactive({})
  const convMethod  = ref(localStorage.getItem('sv_method') || 'none')
  const maxRows     = ref(200)
  const verifyMode  = ref(localStorage.getItem('sv_verify_mode') || 'pk_match')
  const normOpts    = ref(null)   // 페이지에서 주입

  // 재실행 시 사용할 연결 정보 보관
  let _srcConn   = null
  let _tgtConn   = null
  let _pairs     = []     // 현재 실행 중인 filePairs
  let _abortCtrl = null   // 현재 HTTP 요청 취소용

  // ── 통계 ──────────────────────────────────────────────
  const doneCount  = computed(() => fileResults.value.filter(r => r).length)
  const okCount    = computed(() => fileResults.value.filter(r => r?.comparison?.match).length)
  const skipCount  = computed(() => fileResults.value.filter(r => r?.comparison?.skipped).length)
  const failCount  = computed(() => fileResults.value.filter(r => r && !r?.comparison?.match && !r?.comparison?.skipped).length)
  const reviewedCount = computed(() => Object.values(reviewed).filter(Boolean).length)
  const effectivePassCount = computed(() => {
    let cnt = 0
    fileResults.value.forEach((r, i) => {
      if (r?.comparison?.match) cnt++
      else if (isReviewed(i)) cnt++
    })
    return cnt
  })

  // ── 검토완료 ──────────────────────────────────────────
  function toggleReviewed(pairIdx) {
    const key = String(pairIdx)
    reviewed[key] = !reviewed[key]
  }
  function isReviewed(pairIdx) {
    return !!reviewed[String(pairIdx)]
  }

  // ── 파일 매핑 ─────────────────────────────────────────
  // 파일명에서 베이스 키 추출 (확장자 + _trans/_converted 제거)
  function _baseKey(name) {
    return name
      .replace(/\.(sql|ddl|txt)$/i, '')
      .replace(/[_\-](trans|converted|target|tgt)$/i, '')
      .toLowerCase()
  }

  // filePairs: srcFiles/tgtFiles를 인자로 받아 계산 (store에 파일 저장 안 함)
  function buildPairs(srcFileList, tgtFileList) {
    if (!srcFileList.length && !tgtFileList.length) return []

    const srcMap = new Map()
    srcFileList.forEach(sf => {
      const key = _baseKey(sf.name)
      srcMap.set(key, sf)
    })

    const tgtMap = new Map()
    tgtFileList.forEach(tf => {
      const key = _baseKey(tf.name)
      tgtMap.set(key, tf)
    })

    // 소스+타겟 모든 키 합집합
    const allKeys = new Set([...srcMap.keys(), ...tgtMap.keys()])

    // 키 기준으로 정렬 후 쌍 생성
    return [...allKeys].sort().map(key => {
      const sf = srcMap.get(key) || null
      const tf = tgtMap.get(key) || null
      return {
        srcName: sf?.name || '',
        tgtName: tf?.name || '',
        srcFile: sf,
        tgtFile: tf,
        srcOnly: !!sf && !tf,
        tgtOnly: !sf && !!tf,
      }
    })
  }

  // ── 일시정지 대기 헬퍼 ────────────────────────────────
  async function _waitIfPaused() {
    while (paused.value && !stopped.value) {
      await new Promise(r => setTimeout(r, 200))
    }
  }

  // ── 실행 (처음 또는 중지 후 재실행) ──────────────────
  async function runAll(srcConn, tgtConn, pairs) {
    if (running.value) return
    _srcConn = srcConn; _tgtConn = tgtConn; _pairs = pairs
    running.value = true
    paused.value  = false
    stopped.value = false
    runProg.value = 0
    fileResults.value = new Array(_pairs.length).fill(null)
    await _runLoop(0)
  }

  // ── 선택 항목만 실행 ──────────────────────────────────
  async function runSelected(srcConn, tgtConn, idxSet, pairs) {
    if (running.value) return
    _srcConn = srcConn; _tgtConn = tgtConn; _pairs = pairs
    running.value = true
    paused.value  = false
    stopped.value = false

    const idxArr = [...idxSet].sort((a,b) => a-b)
    for (let n = 0; n < idxArr.length; n++) {
      if (stopped.value) break
      await _waitIfPaused()
      if (stopped.value) break

      const i = idxArr[n]
      runningIdx.value = i
      runProg.value    = n

      const p = _pairs[i]
      // 소스 또는 타겟 파일 없는 쌍은 스킵
      if (!p.srcFile || !p.tgtFile) {
        const arr2 = [...fileResults.value]
        arr2[i] = {
          src: { ok: false, error: p.tgtOnly ? '소스 파일 없음' : '타겟 파일 없음', rows:[], cols:[], row_count:0, elapsed_ms:0 },
          tgt: { ok: false, error: p.srcOnly ? '타겟 파일 없음' : '소스 파일 없음', rows:[], cols:[], row_count:0, elapsed_ms:0 },
          comparison: { match: false, reason: p.tgtOnly ? '⚠ 소스 파일 없음' : '⚠ 타겟 파일 없음', diff_rows:[], skipped: true }
        }
        fileResults.value = arr2
        continue
      }
      try {
        if (!p.srcFile?.file) throw new Error('파일을 다시 선택해주세요')
        // 항상 디스크에서 새로 읽기 (File 객체 재생성으로 캐시 우회)
        const srcBlob = p.srcFile.file.slice(0, p.srcFile.file.size)
        const srcText = await srcBlob.text()
        let tgtText = srcText

        if (convMethod.value !== 'none') {
          const ep = convMethod.value === 'claude'
            ? '/api/v1/sql-converter/convert-ai'
            : '/api/v1/sql-converter/convert'
          const { data: cv } = await axios.post(ep, {
            sql: srcText, src_db: _srcConn.db_type, tgt_db: _tgtConn.db_type
          })
          tgtText = cv.converted || srcText
        } else if (p.tgtFile?.file) {
          const tgtBlob = p.tgtFile.file.slice(0, p.tgtFile.file.size)
          tgtText = await tgtBlob.text()
        }

        _abortCtrl = new AbortController()
        const { data } = await axios.post('/api/v1/sql-converter/compare', {
          src_sql: srcText, tgt_sql: tgtText,
          src_conn: _srcConn, tgt_conn: _tgtConn,
          max_rows: maxRows.value,
          verify_mode: verifyMode.value,
          norm_opts: normOpts.value || {},
        }, { signal: _abortCtrl.signal })
        _abortCtrl = null
        const arr = [...fileResults.value]
        // 실행된 실제 쿼리를 결과에 포함 (리포트 확인용)
        arr[i] = { ...data, _src_sql: srcText, _tgt_sql: tgtText,
                   _src_file: p.srcName, _tgt_file: p.tgtName }
        fileResults.value = arr
      } catch(e) {
        _abortCtrl = null
        // 중지(abort)로 인한 오류는 무시하고 루프 종료
        if (stopped.value || e.name === 'AbortError' || e.name === 'CanceledError') break
        const arr = [...fileResults.value]
        arr[i] = {
          src: { ok:false, error:e.message||'오류', row_count:0, cols:[], rows:[], elapsed_ms:0 },
          tgt: { ok:false, error:e.message||'오류', row_count:0, cols:[], rows:[], elapsed_ms:0 },
          comparison: { match:false, reason:'오류: '+(e.message||'오류') }
        }
        fileResults.value = arr
      }
    }

    runningIdx.value = -1
    runProg.value    = _pairs.length
    running.value    = false
    paused.value     = false
    _abortCtrl       = null
    selectedIdxs.value = new Set()
  }

  // ── 재실행 (이어서) ────────────────────────────────────
  async function resume() {
    if (running.value) return
    if (!_srcConn || !_tgtConn) return
    running.value = true
    paused.value  = false
    stopped.value = false
    // 마지막으로 완료된 위치 다음부터
    const startFrom = fileResults.value.findIndex(r => !r)
    if (startFrom < 0) {
      running.value = false
      return
    }
    await _runLoop(startFrom)
  }

  // ── 내부 루프 ─────────────────────────────────────────
  async function _runLoop(startIdx) {
    for (let i = startIdx; i < _pairs.length; i++) {

      // 중지 확인
      if (stopped.value) break

      // 일시정지 대기
      await _waitIfPaused()
      if (stopped.value) break

      runningIdx.value = i
      runProg.value    = i

      const p = _pairs[i]
      // 소스 또는 타겟 파일 없는 쌍은 스킵
      if (!p.srcFile || !p.tgtFile) {
        const arr2 = [...fileResults.value]
        arr2[i] = {
          src: { ok: false, error: p.tgtOnly ? '소스 파일 없음' : '타겟 파일 없음', rows:[], cols:[], row_count:0, elapsed_ms:0 },
          tgt: { ok: false, error: p.srcOnly ? '타겟 파일 없음' : '소스 파일 없음', rows:[], cols:[], row_count:0, elapsed_ms:0 },
          comparison: { match: false, reason: p.tgtOnly ? '⚠ 소스 파일 없음' : '⚠ 타겟 파일 없음', diff_rows:[], skipped: true }
        }
        fileResults.value = arr2
        continue
      }
      try {
        if (!p.srcFile?.file) throw new Error('파일을 다시 선택해주세요')

        // 항상 디스크에서 새로 읽기 (File 객체 재생성으로 캐시 우회)
        const srcBlob = p.srcFile.file.slice(0, p.srcFile.file.size)
        const srcText = await srcBlob.text()
        let tgtText = srcText

        if (convMethod.value !== 'none') {
          const ep = convMethod.value === 'claude'
            ? '/api/v1/sql-converter/convert-ai'
            : '/api/v1/sql-converter/convert'
          const { data: cv } = await axios.post(ep, {
            sql: srcText, src_db: _srcConn.db_type, tgt_db: _tgtConn.db_type
          })
          tgtText = cv.converted || srcText
        } else if (p.tgtFile?.file) {
          const tgtBlob = p.tgtFile.file.slice(0, p.tgtFile.file.size)
          tgtText = await tgtBlob.text()
        }

        _abortCtrl = new AbortController()
        const { data } = await axios.post('/api/v1/sql-converter/compare', {
          src_sql: srcText, tgt_sql: tgtText,
          src_conn: _srcConn, tgt_conn: _tgtConn,
          max_rows: maxRows.value,
          verify_mode: verifyMode.value,
          norm_opts: normOpts.value || {},
        }, { signal: _abortCtrl.signal })
        _abortCtrl = null
        const arr = [...fileResults.value]
        // 실행된 실제 쿼리를 결과에 포함 (리포트 확인용)
        arr[i] = { ...data, _src_sql: srcText, _tgt_sql: tgtText,
                   _src_file: p.srcName, _tgt_file: p.tgtName }
        fileResults.value = arr

      } catch(e) {
        _abortCtrl = null
        if (stopped.value || e.name === 'AbortError' || e.name === 'CanceledError') break
        const msg = e.message || '오류'
        const arr = [...fileResults.value]
        arr[i] = {
          src: { ok: false, error: msg, row_count: 0, cols: [], rows: [], elapsed_ms: 0 },
          tgt: { ok: false, error: msg, row_count: 0, cols: [], rows: [], elapsed_ms: 0 },
          comparison: { match: false, reason: '오류: ' + msg }
        }
        fileResults.value = arr
      }
    }

    runningIdx.value = -1
    runProg.value    = _pairs.length
    running.value    = false
    paused.value     = false

    if (!stopped.value) {
      const last = _pairs.length - 1
      if (last >= 0) activePair.value = last
    }
    stopped.value = false
  }

  // ── 컨트롤 ────────────────────────────────────────────
  function pause()  { if (running.value) paused.value = true }
  function unpause(){ paused.value = false }
  function stop()   {
    stopped.value = true
    paused.value  = false
    // 현재 진행 중인 HTTP 요청 즉시 취소
    if (_abortCtrl) { _abortCtrl.abort(); _abortCtrl = null }
  }

  // ── 초기화 ────────────────────────────────────────────
  function reset() {
    stopped.value = true; paused.value = false
    srcFiles.value = []; tgtFiles.value = []
    fileResults.value = []; activePair.value = -1
    running.value = false; runningIdx.value = -1; runProg.value = 0
    Object.keys(reviewed).forEach(k => delete reviewed[k])
    _srcConn = null; _tgtConn = null
  }

  return {
    buildPairs, srcFiles, tgtFiles, fileResults, activePair,
    running, paused, stopped, runningIdx, runProg,
    reviewed, convMethod, maxRows,
    doneCount, okCount, failCount, skipCount, reviewedCount, effectivePassCount,
    toggleReviewed, isReviewed,
    verifyMode, normOpts,
    selectedIdxs,
    runAll, runSelected, resume, pause, unpause, stop, reset,
  }
})
