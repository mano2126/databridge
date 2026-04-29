// frontend/src/store/monitorStore.js — 플로팅 모니터 전역 상태 (v10 #22)
//
// 책임:
//   1. 폴링 라이프사이클 (이관 중이면 2초, 유휴면 10초)
//   2. 위치/크기/최소화 영속 (localStorage)
//   3. 최근 60개 메트릭 이력 (ring buffer) — 스파크라인용
//   4. 경고 카운트 (Topbar 뱃지용, 향후 확장)
//
// 메모리 전략:
//   - ring buffer 최대 60 포인트 × 소수 대상 = < 100KB
//   - 페이지 이동 시에도 store 는 살아있음 (전역 싱글톤)
//   - 팝업이 닫혀 있으면 폴링 중지 (배터리/네트워크 절약)

import { defineStore } from 'pinia'
import monitorApi from '@/api/monitor.js'

const LS_KEY = 'databridge_monitor_v1'
const RING_SIZE = 60     // 최근 60 포인트 (2초 주기 = 약 2분 이력)

// 기본 위치/크기
const DEFAULT_POS = { x: 20, y: 80, w: 340, h: 420 }

// localStorage 헬퍼 (손상 시 graceful)
// v90.59: 마지막 live 데이터(스냅샷)도 저장 → 모니터 버튼 누르자마자 즉시 표시
function loadState() {
  try {
    const s = JSON.parse(localStorage.getItem(LS_KEY) || '{}')
    return {
      pos:       s.pos || { ...DEFAULT_POS },
      minimized: !!s.minimized,
      visible:   !!s.visible,
      // v90.59: 마지막 스냅샷 (있을 수도 없을 수도 — 첫 사용자는 없음)
      // 너무 오래된 데이터(> 5분)는 무시 (혼동 방지)
      cachedLive: (s.cachedLive && s.cachedLiveTs &&
                   (Date.now() - s.cachedLiveTs) < 5 * 60 * 1000)
                  ? s.cachedLive : null,
      cachedLiveTs: s.cachedLiveTs || 0,
    }
  } catch {
    return { pos: { ...DEFAULT_POS }, minimized: false, visible: false,
             cachedLive: null, cachedLiveTs: 0 }
  }
}

function saveState(state) {
  try {
    // v90.59: 캐시 데이터는 history (큼) 빼고 live (현재 스냅샷) 만 저장
    // — 크기 제한 (~ 50KB 미만) — localStorage 쿼터 절약
    const payload = {
      pos:       state.pos,
      minimized: state.minimized,
      visible:   state.visible,
    }
    if (state.live) {
      // history 는 빼고 본체만 (live 자체는 한 시점 스냅샷이라 적당한 크기)
      payload.cachedLive   = state.live
      payload.cachedLiveTs = Date.now()
    }
    localStorage.setItem(LS_KEY, JSON.stringify(payload))
  } catch {}
}

export const useMonitorStore = defineStore('monitor', {
  state: () => {
    const saved = loadState()
    return {
      // UI
      visible:   saved.visible,
      minimized: saved.minimized,
      pos:       saved.pos,

      // 데이터
      // v90.59: 마지막 스냅샷이 localStorage 에 있으면 즉시 복원 (0초 응답)
      live: saved.cachedLive,
      error: null,
      loading: false,
      // v90.59: 데이터가 캐시(과거)인지 신선한지 구분 (UI 에서 stale 표시 가능)
      isStale: !!saved.cachedLive,
      lastFreshTs: 0,    // 마지막으로 백엔드에서 신선한 데이터 받은 시각

      // 이력 (ring buffer per target)
      // { [targetId]: [{ts, metricKey: value, ...}, ...] }
      history: {},

      // 폴링
      _timer: null,
      _pollInterval: 2000,    // 기본 2초 (이관 중)
      _idleInterval: 10000,   // 유휴 10초
      // v90.62: 백그라운드 폴링 플래그 (visible 안 켰지만 화면에서 데이터 필요할 때)
      _bgPolling: false,

      // 진단
      lastPollTs: 0,
      pollCount: 0,
    }
  },

  getters: {
    // 활성 이관 작업이 있는지
    hasActiveJobs(state) {
      return !!(state.live?.jobs?.length)
    },
    // v90.62: 폴링 활성 상태 (UI 의 라이브 인디케이터용)
    //   visible 폴링 또는 bgPolling 둘 중 하나라도 활성이면 true
    isPolling(state) {
      return !!state._timer
    },
    // 경고 총 카운트 (배지용)
    totalAlerts(state) {
      let n = 0
      for (const t of state.live?.targets || []) {
        n += (t.alerts?.length || 0)
      }
      return n
    },
    // 심각 경고만 필터
    criticalAlerts(state) {
      const out = []
      for (const t of state.live?.targets || []) {
        for (const a of t.alerts || []) {
          if (a.level === 'critical') out.push({ target: t.target_display, ...a })
        }
      }
      return out
    },
  },

  actions: {
    // ── 가시성/위치 ─────────────────────────────────
    show() {
      this.visible = true
      this._persist()
      // v90.59: 캐시된 데이터 있으면 즉시 표시되고, 없어도 정상 폴링.
      // startPolling() 의 fetchOnce() 가 백그라운드 갱신 담당.
      this.startPolling()
    },
    hide() {
      this.visible = false
      this._persist()
      this.stopPolling()
      // v90.62: 패널 닫아도 화면이 폴링 데이터 필요할 수 있으니 자동 bgPolling 재개
      // (사용자가 페이지 떠나면 onUnmounted 의 stopBackgroundPolling 이 정리)
      this.startBackgroundPolling()
    },
    toggle() {
      this.visible ? this.hide() : this.show()
    },
    
    // v90.59: 모니터 패널을 열기 전에 백그라운드에서 미리 데이터 준비.
    //   App.vue 의 onMounted 에서 호출 권장 — 사용자가 모니터 버튼 누르기 전에
    //   캐시가 채워져 있으면 클릭 시 0초 응답 가능.
    //   이미 visible 이거나 폴링 중이면 no-op.
    async primeBackground() {
      if (this.visible || this._timer || this.loading) return
      try {
        // 한 번만 fetch (폴링 시작 안 함 — 사용자가 모니터 안 열었으니까)
        await this.fetchOnce()
      } catch {
        // 워밍업 실패는 조용히 — 사용자가 모니터 열면 그때 다시 시도
      }
    },
    
    // ════════════════════════════════════════════════════════════════════
    // v90.62 (2026-04-28): 화면 진입 시 백그라운드 폴링 (가시성 무관)
    //   본부장님 호소: "모니터가 아직도 동작 안 함, 한 번 열었다 닫으면 정상화"
    //   원인: primeBackground 는 1회 fetch 후 종료 → 갱신 안 됨
    //         show() 만 startPolling() 호출 → 패널 안 열면 폴링 안 됨
    //         그러나 JobMonitor 화면의 LIVE 배너 등은 폴링 데이터 필요!
    //   처방: startBackgroundPolling() — visible 무관하게 백그라운드 폴링 시작.
    //         페이지 떠나면 stopPolling() 으로 정리 (JobMonitor onUnmounted).
    //         _bgPolling 플래그로 백그라운드 폴링과 일반 폴링 구분.
    // ════════════════════════════════════════════════════════════════════
    startBackgroundPolling() {
      // 이미 폴링 중이면 (visible=true 의 일반 폴링 또는 다른 백그라운드 폴링) no-op
      if (this._timer) return
      this._bgPolling = true
      this.fetchOnce()       // 즉시 1회
      this._scheduleNext()   // 그 다음 setTimeout 재귀
    },
    
    stopBackgroundPolling() {
      // 사용자가 모니터 패널을 직접 열어둔 상태 (visible=true) 면 정지하지 않음
      // — 직접 열어둔 폴링이 우선
      if (this.visible) return
      this.stopPolling()
      this._bgPolling = false
    },
    toggleMinimize() {
      this.minimized = !this.minimized
      this._persist()
    },
    setPos(x, y) {
      // 화면 경계 클램핑 (팝업이 화면 밖으로 나가지 않게)
      const w = this.pos.w, h = this.minimized ? 36 : this.pos.h
      const maxX = Math.max(0, window.innerWidth  - w - 8)
      const maxY = Math.max(0, window.innerHeight - h - 8)
      this.pos.x = Math.max(8, Math.min(x, maxX))
      this.pos.y = Math.max(8, Math.min(y, maxY))
      this._persist()
    },
    setSize(w, h) {
      this.pos.w = Math.max(280, Math.min(w, 800))
      this.pos.h = Math.max(240, Math.min(h, 800))
      this._persist()
    },
    resetPos() {
      this.pos = { ...DEFAULT_POS }
      this._persist()
    },
    _persist() {
      saveState(this.$state)
    },

    // ── 폴링 ────────────────────────────────────────
    startPolling() {
      if (this._timer) return
      this.fetchOnce()   // 즉시 1회
      this._scheduleNext()
    },

    stopPolling() {
      if (this._timer) {
        clearTimeout(this._timer)
        this._timer = null
      }
      // v90.62: bgPolling 플래그도 클리어
      this._bgPolling = false
    },

    _scheduleNext() {
      // v90.62: visible 또는 bgPolling 중 하나라도 활성이면 계속
      if (!this.visible && !this._bgPolling) return
      // 이관 중이면 빠르게, 아니면 느리게
      const interval = this.hasActiveJobs ? this._pollInterval : this._idleInterval
      this._timer = setTimeout(async () => {
        await this.fetchOnce()
        this._scheduleNext()
      }, interval)
    },

    async fetchOnce() {
      if (this.loading) return
      this.loading = true
      try {
        const data = await monitorApi.fetchLive()
        this.live = data
        this.error = null
        this.lastPollTs = Date.now()
        this.pollCount++
        // v90.59: backend 가 stale 캐시 표시했으면 그대로, 아니면 신선
        // (backend 의 _cache_stale 메타 활용)
        this.isStale = !!data?._cache_stale
        if (!this.isStale) {
          this.lastFreshTs = Date.now()
        }
        this._updateHistory(data)
        // v90.59: localStorage 에도 저장 (다음 페이지 진입 시 즉시 표시용)
        this._persist()
      } catch (e) {
        this.error = e?.response?.data?.detail || e?.message || String(e)
      } finally {
        this.loading = false
      }
    },

    // ring buffer — 각 target 별로 최근 N 포인트만 유지
    _updateHistory(data) {
      if (!data?.targets) return
      for (const snap of data.targets) {
        const id = snap.target_id
        if (!id) continue
        const point = { ts: snap.ts }

        // 공통 필드 추출 (UI 에서 쉽게 쓰도록 평탄화)
        if (snap.system) {
          point.mem_pct = snap.system.mem_pct
          point.cpu_pct = snap.system.cpu_pct
        }
        if (snap.db) {
          if (snap.db.buffer_cache_hit_ratio != null) point.bcr = snap.db.buffer_cache_hit_ratio
          if (snap.db.page_life_expectancy   != null) point.ple = snap.db.page_life_expectancy
          if (snap.db.buffer_pool_used_pct   != null) point.bpp = snap.db.buffer_pool_used_pct
          if (snap.db.active_sessions        != null) point.sessions = snap.db.active_sessions
        }
        if (snap.docker?.containers?.length) {
          // Docker 는 컨테이너별로 저장하지 않고 대표값(max mem)만
          const maxMem = Math.max(...snap.docker.containers.map(c => c.mem_pct || 0))
          point.docker_max_mem = maxMem
        }

        if (!this.history[id]) this.history[id] = []
        this.history[id].push(point)
        // ring buffer 유지
        if (this.history[id].length > RING_SIZE) {
          this.history[id].splice(0, this.history[id].length - RING_SIZE)
        }
      }

      // 이미 삭제된 target 의 이력은 정리
      const aliveIds = new Set((data.targets || []).map(t => t.target_id))
      for (const id of Object.keys(this.history)) {
        if (!aliveIds.has(id)) delete this.history[id]
      }
    },

    // ── 편의: 특정 타입 스냅샷만 ─────────────────────
    getSnapshotsByType(type) {
      return (this.live?.targets || []).filter(t => t.target_type === type)
    },

    // ── 대상 관리 (팝업 내 설정창용) ─────────────────
    async toggleTargetEnabled(targetId, enabled) {
      await monitorApi.updateTarget(targetId, { enabled })
      await this.fetchOnce()
    },

    async removeTarget(targetId) {
      await monitorApi.deleteTarget(targetId)
      delete this.history[targetId]
      await this.fetchOnce()
    },
  },
})

export default useMonitorStore
