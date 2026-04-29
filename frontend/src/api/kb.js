// frontend/src/api/kb.js — KB 관리 API 래퍼 (v10 #18)
import axios from 'axios'

const BASE = '/api/v1/kb'

export const kbApi = {
  // ── 에러 KB (v10 #17) ──────────────────────────────────
  async listPatterns() {
    const { data } = await axios.get(`${BASE}/patterns`)
    return data
  },
  async getStats(days = 30) {
    const { data } = await axios.get(`${BASE}/stats`, { params: { days } })
    return data
  },
  async getUnmatched(days = 30, limit = 20) {
    const { data } = await axios.get(`${BASE}/unmatched`, { params: { days, limit } })
    return data
  },
  async reload() {
    const { data } = await axios.post(`${BASE}/reload`)
    return data
  },
  async testMatch(errorMsg) {
    const { data } = await axios.post(`${BASE}/test-match`, { error: errorMsg })
    return data
  },

  // ── 변환 KB (v10 #18 신규) ─────────────────────────────
  /** 타입/오브젝트 매핑 자산 현황 */
  async conversionOverview() {
    const { data } = await axios.get(`${BASE}/conversion/overview`)
    return data
  },
  /** AI 호출 vs 로컬 처리 일별 추이 */
  async conversionMetrics(days = 30) {
    const { data } = await axios.get(`${BASE}/conversion/metrics`, { params: { days } })
    return data
  },
  /** 규칙 수동 승격/거부 (kind: 'type'|'obj', status: 'active'|'shadow'|'rejected') */
  async promoteRule(kind, ruleId, status) {
    const { data } = await axios.post(`${BASE}/conversion/promote`, {
      kind, rule_id: ruleId, status,
    })
    return data
  },
  /** DDL 로컬 커버리지 미리보기 */
  async coverage(srcDdl, srcDb, tgtDb) {
    const { data } = await axios.post(`${BASE}/conversion/coverage`, {
      src_ddl: srcDdl, src_db: srcDb, tgt_db: tgtDb,
    })
    return data
  },
}

export default kbApi
