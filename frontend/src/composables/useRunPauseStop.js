/**
 * useRunPauseStop — 공통 실행/일시정지/중단 상태 관리 composable
 * --------------------------------------------------------------------
 * v43 (2026-04-22): Validate.vue 에서 첫 도입. 추후 JobMonitor, SqlVerify,
 *                   재이관 모달 등에 동일 패턴으로 적용 예정.
 *
 * 제공하는 것:
 *   - state.value: 'idle' | 'running' | 'paused' | 'aborting'
 *   - start(), pause(), resume(), stop() — 상태 전환 함수
 *   - abortCtl: 활성 AbortController (fetch 기반 작업용)
 *   - pauseFlag, stopFlag — 루프 기반 작업이 체크할 ref
 *   - waitIfPaused() — 루프 안에서 호출하면 paused 동안 대기
 *
 * 두 가지 사용 패턴:
 *   [A] fetch/SSE 기반 작업:
 *       const rs = useRunPauseStop()
 *       await rs.start()
 *       fetch(url, { signal: rs.abortCtl.signal })
 *       // 중단은 사용자가 rs.stop() 버튼 클릭 시 자동
 *
 *   [B] 순차 루프 작업 (axios.post 반복 등):
 *       const rs = useRunPauseStop()
 *       await rs.start()
 *       for (const item of items) {
 *         await rs.waitIfPaused()   // 일시정지 동안 대기
 *         if (rs.stopFlag.value) break  // 중단 시 루프 탈출
 *         await axios.post(...)
 *       }
 *       rs.finish()
 *
 * 외부 (서버) 제어가 필요한 경우:
 *   onPause, onResume, onStop 콜백을 옵션으로 받아 백엔드 API 호출 가능
 *   예: useRunPauseStop({ onPause: () => axios.post('/jobs/123/pause') })
 */
import { ref, computed } from 'vue'

export function useRunPauseStop(options = {}) {
  const { onStart, onPause, onResume, onStop } = options

  // 핵심 상태
  const state = ref('idle')   // idle | running | paused | aborting
  const pauseFlag = ref(false)
  const stopFlag  = ref(false)
  let abortCtl = null

  // 파생 상태 (템플릿 바인딩 편의)
  const isIdle    = computed(() => state.value === 'idle')
  const isRunning = computed(() => state.value === 'running')
  const isPaused  = computed(() => state.value === 'paused')
  const isAborting= computed(() => state.value === 'aborting')
  const isActive  = computed(() => state.value === 'running' || state.value === 'paused')

  async function start() {
    abortCtl = new AbortController()
    pauseFlag.value = false
    stopFlag.value  = false
    state.value = 'running'
    if (onStart) { try { await onStart() } catch (e) { console.error('[useRunPauseStop] onStart error', e) } }
  }

  async function pause() {
    if (state.value !== 'running') return
    pauseFlag.value = true
    state.value = 'paused'
    if (onPause) { try { await onPause() } catch (e) { console.error('[useRunPauseStop] onPause error', e) } }
  }

  async function resume() {
    if (state.value !== 'paused') return
    pauseFlag.value = false
    state.value = 'running'
    if (onResume) { try { await onResume() } catch (e) { console.error('[useRunPauseStop] onResume error', e) } }
  }

  async function stop() {
    if (state.value === 'idle' || state.value === 'aborting') return
    state.value = 'aborting'
    stopFlag.value  = true
    pauseFlag.value = false   // paused 상태에서 stop 시 대기 루프가 빠져나오도록
    if (abortCtl) { try { abortCtl.abort() } catch {} }
    if (onStop) { try { await onStop() } catch (e) { console.error('[useRunPauseStop] onStop error', e) } }
    // 최종 idle 전환은 finish() 로 — 서버 정리가 끝난 뒤 호출할 것
  }

  function finish() {
    state.value = 'idle'
    pauseFlag.value = false
    stopFlag.value  = false
    abortCtl = null
  }

  /**
   * 루프 안에서 호출. state 가 paused 인 동안 대기, running 으로 돌아오면 resolve.
   * state 가 aborting 으로 바뀌면 즉시 resolve (호출부가 stopFlag 체크해 break).
   * 폴링 간격 100ms.
   */
  function waitIfPaused() {
    if (state.value === 'running' || state.value === 'aborting') return Promise.resolve()
    return new Promise(resolve => {
      const check = () => {
        if (state.value === 'running' || state.value === 'aborting' || state.value === 'idle') {
          resolve()
        } else {
          setTimeout(check, 100)
        }
      }
      check()
    })
  }

  return {
    state, isIdle, isRunning, isPaused, isAborting, isActive,
    pauseFlag, stopFlag,
    get abortCtl() { return abortCtl },   // getter — 매 호출마다 최신 ctl 반환
    start, pause, resume, stop, finish, waitIfPaused,
  }
}
