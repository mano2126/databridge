/**
 * dateUtils.js — DataBridge 공통 날짜 유틸
 * frontend/src/utils/dateUtils.js
 *
 * 백엔드가 KST(+09:00) isoformat으로 저장하므로
 * 시간대 없는 값도 KST로 파싱합니다.
 */

/**
 * 날짜 문자열 → Date 객체 (KST 기준)
 *   "2026-04-12T17:37:00+09:00"  → 그대로 파싱
 *   "2026-04-12 17:37:00"        → KST(+09:00)로 파싱
 *   "2026-04-12T17:37:00Z"       → UTC로 파싱
 *   "+09:00Z" 이중 suffix         → 자동 제거
 */
export function parseDate(ts) {
  if (!ts) return null
  let s = String(ts).trim()
  // +09:00Z 이중 suffix 제거
  s = s.replace(/([+-]\d{2}:\d{2})Z$/, '$1')
  // 시간대 없으면 KST(+09:00) 간주
  if (!s.includes('+') && !s.match(/[+-]\d{2}:\d{2}$/) && !s.endsWith('Z')) {
    s = s.replace(' ', 'T') + '+09:00'
  }
  const d = new Date(s)
  return isNaN(d) ? null : d
}

/** "M/D HH:MM" — Cdc.vue 등 짧은 표시 */
export function fmtShort(ts) {
  const d = parseDate(ts)
  if (!d) return '미실행'
  return `${d.getMonth()+1}/${d.getDate()} ` +
    `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

/** "MM.DD HH:MM" — Monitor 리스트 */
export function fmtDateShort(ts) {
  const d = parseDate(ts)
  if (!d) return ''
  return `${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getDate()).padStart(2,'0')} ` +
    `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

/** "MM/DD HH:MM" — JobMonitor 리스트 */
export function fmtDate(ts) {
  const d = parseDate(ts)
  if (!d) return '—'
  return d.toLocaleDateString('ko-KR', { month: '2-digit', day: '2-digit' }) + ' ' +
    d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })
}

/** "YYYY-MM-DD HH:MM" — 상세 표시 */
export function fmtDateTime(ts) {
  const d = parseDate(ts)
  if (!d) return '—'
  const yyyy = d.getFullYear()
  const mo   = String(d.getMonth()+1).padStart(2,'0')
  const dd   = String(d.getDate()).padStart(2,'0')
  const hh   = String(d.getHours()).padStart(2,'0')
  const mm   = String(d.getMinutes()).padStart(2,'0')
  return `${yyyy}-${mo}-${dd} ${hh}:${mm}`
}

/** "오전/오후 HH시 MM분 SS초" — 이관 작업 모니터 완료 시각 */
export function fmtTime(ts) {
  const d = parseDate(ts)
  if (!d) return '—'
  const h = d.getHours(), m = d.getMinutes(), s = d.getSeconds()
  const ampm = h < 12 ? '오전' : '오후'
  return `${ampm} ${String(h % 12 || 12).padStart(2,'0')}시 ` +
    `${String(m).padStart(2,'0')}분 ${String(s).padStart(2,'0')}초`
}

/** "toLocaleString('ko-KR')" — Schedule, 범용 */
export function fmtLocale(ts) {
  const d = parseDate(ts)
  if (!d) return ''
  return d.toLocaleString('ko-KR')
}

/** 경과 시간 계산 → "N분 NN초" */
export function fmtElapsed(startTs, endTs) {
  const s = parseDate(startTs)
  if (!s) return '—'
  const e = endTs ? (parseDate(endTs) || new Date()) : new Date()
  const sec = Math.max(0, Math.round((e - s) / 1000))
  const h  = Math.floor(sec / 3600)
  const m  = Math.floor((sec % 3600) / 60)
  const s2 = sec % 60
  if (h > 0) return `${h}시간 ${String(m).padStart(2,'0')}분 ${String(s2).padStart(2,'0')}초`
  if (m > 0) return `${m}분 ${String(s2).padStart(2,'0')}초`
  return `${s2}초`
}

/** 밀리초 반환 (정렬/diff 계산용) */
export function toMs(ts) {
  const d = parseDate(ts)
  return d ? d.getTime() : 0
}
