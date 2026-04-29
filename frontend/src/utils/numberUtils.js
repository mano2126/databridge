/**
 * numberUtils.js — DataBridge 공통 숫자 유틸
 * frontend/src/utils/numberUtils.js
 */

/** 행 수 → 한국어 단위 (만/억) 또는 천단위 콤마 */
export function fmtRows(n) {
  if (!n && n !== 0) return '0'
  n = Number(n)
  if (n >= 1_0000_0000) return (n / 1_0000_0000).toFixed(1) + '억'
  if (n >= 1_0000)      return (n / 1_0000).toFixed(1) + '만'
  if (n >= 1_000)       return n.toLocaleString()
  return String(n)
}

/** 숫자 → 천단위 콤마 */
export function fmtNum(n) {
  if (!n && n !== 0) return '0'
  return Number(n).toLocaleString()
}

/** rows/s 속도 표시 */
export function fmtSpeed(n) {
  if (!n && n !== 0) return '—'
  if (n >= 1_000) return Math.round(n / 1_000) + 'K rows/s'
  return n + ' rows/s'
}
