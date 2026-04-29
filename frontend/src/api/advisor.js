/**
 * frontend/src/api/advisor.js — AI DBA Consultant API 래퍼
 * v88 P2 (2026-04-23)
 */
import axios from 'axios'

const BASE = '/api/v1/advisor'

export async function estimateCost({ srcDb, tgtDb, selection }) {
  const { data } = await axios.post(`${BASE}/estimate-cost`, {
    src_db: srcDb, tgt_db: tgtDb,
    selection: {
      tables:     selection.tables     || [],
      procedures: selection.procedures || [],
      functions:  selection.functions  || [],
      triggers:   selection.triggers   || [],
      views:      selection.views      || [],
    },
  })
  return data
}

export async function analyze({ srcDb, tgtDb, selection, mode = 'smart', userHints = '' }) {
  const { data } = await axios.post(`${BASE}/analyze`, {
    src_db: srcDb, tgt_db: tgtDb,
    selection: {
      tables:     selection.tables     || [],
      procedures: selection.procedures || [],
      functions:  selection.functions  || [],
      triggers:   selection.triggers   || [],
      views:      selection.views      || [],
    },
    mode,
    user_hints: userHints,
  })
  return data
}

/**
 * v88 P2 신규 — 사용자 결정 기록.
 *
 * @param {Object} params
 * @param {string} params.srcDb
 * @param {string} params.tgtDb
 * @param {'smart'|'hybrid'|'deep'} params.mode
 * @param {Array<{id,decision,edited_sql?}>} params.decisions
 * @param {string} [params.jobId]
 */
export async function applyDecision({ srcDb, tgtDb, mode, decisions, jobId }) {
  const { data } = await axios.post(`${BASE}/apply-decision`, {
    src_db: srcDb,
    tgt_db: tgtDb,
    mode,
    decisions: decisions.map(d => ({
      id: d.id,
      decision: d.decision,
      edited_sql: d.edited_sql || null,
    })),
    job_id: jobId || null,
  })
  return data
}

export async function health() {
  const { data } = await axios.get(`${BASE}/health`)
  return data
}

export default {
  estimateCost,
  analyze,
  applyDecision,
  health,
}
