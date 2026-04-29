/**
 * src/composables/useJobSocket.js
 * 특정 Job의 실시간 WebSocket 스트림을 Vue composable로 제공
 *
 * 사용법:
 *   const { state, logs, connected, disconnect } = useJobSocket(jobId)
 */
import { ref, onUnmounted } from 'vue'

export function useJobSocket(jobId) {
  const state     = ref(null)   // 최신 Job 상태 객체
  const logs      = ref([])     // 누적 로그 항목
  const connected = ref(false)
  const error     = ref(null)

  let ws = null
  let reconnectTimer = null
  let reconnectDelay = 1000

  function connect() {
    if (!jobId) return

    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const url   = `${proto}://${location.host}/ws/jobs/${jobId}`

    try {
      ws = new WebSocket(url)

      ws.onopen = () => {
        connected.value  = true
        error.value      = null
        reconnectDelay   = 1000
      }

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          if (data.error) {
            error.value = data.error
            return
          }
          // 상태 업데이트
          state.value = { ...state.value, ...data }
          // 새 로그 추가
          if (data.new_logs?.length) {
            logs.value = [...logs.value, ...data.new_logs].slice(-500)
          }
          // 완료 상태면 더 이상 재연결 안 함
          if (['completed', 'error', 'aborted'].includes(data.status)) {
            connected.value = false
          }
        } catch (err) {
          console.warn('[WS] 메시지 파싱 실패', err)
        }
      }

      ws.onerror = () => {
        error.value = 'WebSocket 연결 오류'
      }

      ws.onclose = () => {
        connected.value = false
        // 진행 중이면 재연결 시도
        if (state.value?.status === 'running' || state.value?.status === 'paused') {
          reconnectTimer = setTimeout(() => {
            reconnectDelay = Math.min(reconnectDelay * 2, 10000)
            connect()
          }, reconnectDelay)
        }
      }
    } catch (err) {
      error.value = String(err)
    }
  }

  function disconnect() {
    clearTimeout(reconnectTimer)
    if (ws) {
      ws.onclose = null   // 재연결 방지
      ws.close()
      ws = null
    }
    connected.value = false
  }

  connect()
  onUnmounted(disconnect)

  return { state, logs, connected, error, disconnect, reconnect: connect }
}


/**
 * useMonitorSocket
 * 전체 Job 현황 요약 스트림 (/ws/monitor)
 */
export function useMonitorSocket() {
  const summary   = ref(null)
  const connected = ref(false)

  let ws = null

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    ws = new WebSocket(`${proto}://${location.host}/ws/monitor`)

    ws.onopen  = () => { connected.value = true }
    ws.onclose = () => {
      connected.value = false
      setTimeout(connect, 3000)
    }
    ws.onmessage = (e) => {
      try { summary.value = JSON.parse(e.data) } catch { /* ignore */ }
    }
  }

  function disconnect() {
    if (ws) { ws.onclose = null; ws.close(); ws = null }
    connected.value = false
  }

  connect()
  onUnmounted(disconnect)

  return { summary, connected, disconnect }
}
