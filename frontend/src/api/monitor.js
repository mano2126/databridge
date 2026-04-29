// frontend/src/api/monitor.js — 실시간 모니터 API 래퍼 (v10 #22)
import axios from 'axios'

// 기존 api 인스턴스(인터셉터 있음) 재사용을 위해 /api/v1 prefix 사용
const BASE = '/api/v1/system'

export const monitorApi = {
  // ── 메인 스냅샷 (폴링) ────────────────────────────
  async fetchLive() {
    const r = await axios.get(`${BASE}/live`)
    return r.data
  },

  // ── 가용성 체크 ──────────────────────────────────
  async fetchHealth() {
    const r = await axios.get(`${BASE}/health`)
    return r.data
  },

  // ── 어댑터 메타 ──────────────────────────────────
  async listAdapters() {
    const r = await axios.get(`${BASE}/adapters`)
    return r.data.adapters || []
  },

  async listProfiles() {
    const r = await axios.get(`${BASE}/profiles`)
    return r.data.profiles || []
  },

  // ── 대상 CRUD ────────────────────────────────────
  async listTargets() {
    const r = await axios.get(`${BASE}/targets`)
    return r.data.targets || []
  },

  async getTarget(id) {
    const r = await axios.get(`${BASE}/targets/${id}`)
    return r.data
  },

  async createTarget(body) {
    const r = await axios.post(`${BASE}/targets`, body)
    return r.data
  },

  async updateTarget(id, patch) {
    const r = await axios.put(`${BASE}/targets/${id}`, patch)
    return r.data
  },

  async deleteTarget(id) {
    await axios.delete(`${BASE}/targets/${id}`)
  },

  async testTarget(id) {
    const r = await axios.post(`${BASE}/targets/${id}/test`)
    return r.data
  },
}

export default monitorApi
