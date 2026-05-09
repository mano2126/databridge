<!--
  v92 (2026-04-30): 일괄 튜닝 권장 패널
  본부장님 비전:
    - 변환 후 자동 plan 분석 → 튜닝 필요 건만 추출 (AI 미사용, 무료)
    - 사용자가 선택 → AI 튜닝 → 좌(쿼리 목록) / 우(3개 variant, 추천 상단)
-->
<template>
  <div class="btp-root" v-if="visible">
    <!-- 헤더 -->
    <div class="btp-header">
      <div class="btp-title">
        <span class="btp-icon">⚙</span>
        <span>튜닝 권장 분석</span>
        <span class="btp-meta" v-if="summary">
          · 총 {{ summary.total }}개 ·
          <span class="btp-pill red" v-if="summary.red">🔴 {{ summary.red }}</span>
          <span class="btp-pill yellow" v-if="summary.yellow">🟡 {{ summary.yellow }}</span>
          <span class="btp-pill green" v-if="summary.green">⚪ {{ summary.green }}</span>
        </span>
      </div>
      <div class="btp-actions">
        <span v-if="threshold" class="btp-thr">
          임계 <input type="number" v-model.number="thresholdInput" @change="onThresholdChange"
                       min="100" max="60000" step="100" class="btp-thr-input"/>ms
        </span>
        <button class="btp-mini-btn" @click="$emit('reanalyze', thresholdInput)" :disabled="analyzing || tuning">
          🔄 재분석
        </button>
        <button class="btp-mini-btn ghost" @click="$emit('close')">✕ 닫기</button>
      </div>
    </div>

    <!-- 분석 진행 중 -->
    <div v-if="analyzing" class="btp-loading">
      <span class="btp-spin"></span>
      <span>EXPLAIN + 실측 분석 중... ({{ analyzeProgress.done }}/{{ analyzeProgress.total }})</span>
    </div>

    <!-- 분석 결과 없음 -->
    <div v-else-if="!items.length" class="btp-empty">
      변환된 SELECT 쿼리가 없습니다. (DDL/INSERT/UPDATE 는 분석 대상 아님)
    </div>

    <!-- ═══ 단계 1: 권장 목록 (튜닝 시작 전) ═══ -->
    <div v-else-if="!tuneItems.length" class="btp-list-mode">
      <div class="btp-list-bar">
        <label class="btp-sel-all">
          <input type="checkbox" :checked="allSelected" @change="toggleAll"/>
          전체 선택
        </label>
        <span class="btp-sel-count">{{ selectedCount }}개 선택됨</span>
        <span class="btp-spacer"></span>
        <button class="btp-only-red" @click="selectByRank('red')" :disabled="!summary?.red">🔴 만 선택</button>
        <button class="btp-only-red" @click="selectByRank('redyellow')" :disabled="!(summary?.red||summary?.yellow)">🔴+🟡 선택</button>
        <button class="btp-go-btn" :disabled="!selectedCount || tuning" @click="startTune">
          <span v-if="tuning" class="btp-spin sm"></span>
          🤖 AI 튜닝 시작 ({{ selectedCount }})
        </button>
      </div>

      <div class="btp-list">
        <div v-for="(it, idx) in items" :key="idx" class="btp-item" :class="['rank-' + it.rank]">
          <input type="checkbox" v-model="it._selected" class="btp-check"/>
          <span class="btp-rank-ico">
            <template v-if="it.rank === 'red'">🔴</template>
            <template v-else-if="it.rank === 'yellow'">🟡</template>
            <template v-else>⚪</template>
          </span>
          <div class="btp-item-main">
            <div class="btp-item-name">{{ it.filename }}</div>
            <div class="btp-item-reasons">
              <span v-for="(r, i) in it.reasons" :key="i" class="btp-reason">{{ r }}</span>
            </div>
          </div>
          <div class="btp-item-metrics">
            <span v-if="it.metrics?.avg_ms !== null && it.metrics?.avg_ms !== undefined"
                  class="btp-m">⏱ {{ it.metrics.avg_ms }}ms</span>
            <span v-if="it.metrics?.ratio" class="btp-m">📊 {{ it.metrics.ratio }}x</span>
            <span v-if="it.metrics?.cost" class="btp-m">cost {{ Math.round(it.metrics.cost) }}</span>
            <span class="btp-score">{{ it.score }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══ 단계 2: 좌(쿼리 목록) / 우(variant 카드) ═══ -->
    <div v-else class="btp-split">
      <!-- 좌측: 쿼리 목록 -->
      <div class="btp-left">
        <div class="btp-left-head">
          <span>튜닝 결과 ({{ tuneItems.length }}개)</span>
          <button class="btp-mini-btn ghost" @click="resetTune">← 목록으로</button>
        </div>
        <div class="btp-left-list">
          <div v-for="(t, i) in tuneItems" :key="i"
               class="btp-tune-row"
               :class="{active: activeIdx === i}"
               @click="activeIdx = i">
            <div class="btp-tune-row-name">{{ t.filename }}</div>
            <div class="btp-tune-row-summary">
              <span v-if="topVariant(t)?.recommended" class="btp-rec-mark">⭐</span>
              <span v-if="topVariant(t)?.speed_delta !== null && topVariant(t)?.speed_delta !== undefined"
                    :class="{ok: topVariant(t).speed_delta < 0, bad: topVariant(t).speed_delta > 5}">
                {{ topVariant(t).speed_delta > 0 ? '+' : '' }}{{ topVariant(t).speed_delta }}%
              </span>
              <span class="btp-tune-row-cnt">{{ (t.variants||[]).length }}개 변형</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 우측: 활성 항목의 3개 variant -->
      <div class="btp-right">
        <div class="btp-right-head" v-if="active">
          <div class="btp-right-title">
            <span class="btp-rt-name">{{ active.filename }}</span>
            <span class="btp-rt-meta" v-if="active.base_metrics?.execute?.avg_ms">
              base: {{ active.base_metrics.execute.avg_ms }}ms
            </span>
          </div>
          <button class="btp-mini-btn" @click="copyOriginal">📋 원본 복사</button>
        </div>
        <div v-if="active && active.error" class="btp-error">
          ⚠ {{ active.error }}
        </div>
        <div v-if="active && !active.variants?.length && !active.error" class="btp-empty">
          variant 없음
        </div>
        <div v-if="active" class="btp-variants">
          <div v-for="(v, i) in active.variants || []" :key="i"
               class="btp-variant"
               :class="{recommended: v.recommended, top: i === 0}">
            <div class="btp-v-head">
              <span class="btp-v-rank" v-if="i === 0">🥇</span>
              <span class="btp-v-rank" v-else-if="i === 1">🥈</span>
              <span class="btp-v-rank" v-else-if="i === 2">🥉</span>
              <span class="btp-v-label">{{ v.label }}</span>
              <span class="btp-v-strategy" :title="v.strategy">{{ v.strategy }}</span>
              <span class="btp-spacer"></span>
              <span v-if="v.recommended" class="btp-v-badge rec">⭐ 추천</span>
              <span v-if="v.data_match === true" class="btp-v-badge ok">데이터 일치</span>
              <span v-else-if="v.data_match === false" class="btp-v-badge bad">데이터 불일치</span>
              <span v-if="v.speed_delta !== null && v.speed_delta !== undefined"
                    class="btp-v-badge" :class="{ok: v.speed_delta < -5, bad: v.speed_delta > 5}">
                {{ v.speed_delta > 0 ? '+' : '' }}{{ v.speed_delta }}%
              </span>
              <button class="btp-mini-btn" @click="copyVariantSql(v)">📋</button>
            </div>
            <div class="btp-v-reason" v-if="v.reason">{{ v.reason }}</div>
            <pre class="btp-v-sql">{{ formatSql(v.sql) }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  items: { type: Array, default: () => [] },         // analyze-batch 결과
  summary: { type: Object, default: null },
  threshold: { type: Number, default: 500 },
  analyzing: { type: Boolean, default: false },
  analyzeProgress: { type: Object, default: () => ({ done: 0, total: 0 }) },
  tuning: { type: Boolean, default: false },
  tuneItems: { type: Array, default: () => [] },     // tune-batch 결과
})
const emit = defineEmits(['reanalyze', 'tune', 'close', 'reset-tune', 'notify'])

const thresholdInput = ref(props.threshold || 500)
watch(() => props.threshold, v => thresholdInput.value = v || 500)
function onThresholdChange() {}

const allSelected = computed(() => props.items.length > 0 && props.items.every(it => it._selected))
const selectedCount = computed(() => props.items.filter(it => it._selected).length)

function toggleAll(e) {
  const v = e.target.checked
  props.items.forEach(it => it._selected = v)
}
function selectByRank(mode) {
  props.items.forEach(it => {
    if (mode === 'red') it._selected = (it.rank === 'red')
    else if (mode === 'redyellow') it._selected = (it.rank === 'red' || it.rank === 'yellow')
  })
}
function startTune() {
  const sel = props.items.filter(it => it._selected)
  if (!sel.length) return
  emit('tune', sel)
}

// 좌/우 split
const activeIdx = ref(0)
watch(() => props.tuneItems.length, n => { if (n > 0) activeIdx.value = 0 })
const active = computed(() => props.tuneItems[activeIdx.value] || null)

function topVariant(t) {
  return (t.variants || [])[0] || null
}
function resetTune() {
  emit('reset-tune')
}

function copyOriginal() {
  if (!active.value) return
  navigator.clipboard?.writeText(active.value.original_sql || '')
  emit('notify', { msg: '원본 SQL 복사됨', type: 'success' })
}
function copyVariantSql(v) {
  navigator.clipboard?.writeText(formatSql(v.sql || ''))
  emit('notify', { msg: `${v.label} 복사됨`, type: 'success' })
}

// SqlConverter 와 동일한 formatSql (간단 keyword 줄바꿈)
function formatSql(sql) {
  if (!sql) return ''
  if ((sql.match(/\n/g) || []).length >= 4) return sql
  let s = sql.replace(/\s+/g, ' ').trim()
  const KW = ['WITH ', 'SELECT ', 'FROM ', 'INNER JOIN ', 'LEFT JOIN ', 'RIGHT JOIN ',
              'OUTER JOIN ', 'CROSS JOIN ', 'JOIN ', 'WHERE ', 'GROUP BY ', 'HAVING ',
              'ORDER BY ', 'LIMIT ', 'UNION ALL ', 'UNION ', 'ON ']
  KW.forEach(kw => {
    const re = new RegExp('\\s+' + kw.trim() + '\\b', 'gi')
    s = s.replace(re, '\n' + kw.trim() + ' ')
  })
  s = s.replace(/(SELECT[^]*?)(?=\nFROM|$)/i, m => m.replace(/, /g, ',\n    '))
  return s.trim()
}
</script>

<style scoped>
.btp-root {
  margin-top: 14px;
  background: var(--bg-primary, #fff);
  border: 0.5px solid var(--border-light, #e5e7eb);
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  overflow: hidden;
}
.btp-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px;
  background: linear-gradient(180deg, #fafbfc, #f5f7fa);
  border-bottom: 0.5px solid var(--border-light, #e5e7eb);
}
.btp-title { display:flex; align-items:center; gap:8px; font-size: 13px; font-weight: 700; color: var(--text-primary,#111827); }
.btp-icon { font-size: 14px; }
.btp-meta { font-weight: 400; color: var(--text-tertiary, #9ca3af); font-size: 11.5px; display: inline-flex; gap: 4px; align-items: center; }
.btp-pill { font-size: 11px; padding: 1px 6px; border-radius: 8px; font-weight: 600; }
.btp-pill.red    { background: rgba(239,68,68,0.1); color: #b91c1c; }
.btp-pill.yellow { background: rgba(245,158,11,0.1); color: #b45309; }
.btp-pill.green  { background: rgba(34,197,94,0.1); color: #15803d; }

.btp-actions { display:flex; align-items: center; gap: 6px; }
.btp-thr { font-size: 11px; color: var(--text-tertiary); display: inline-flex; align-items: center; gap: 4px; }
.btp-thr-input {
  width: 60px; padding: 2px 4px; font-size: 11px;
  border: 0.5px solid var(--border-mid, #d1d5db); border-radius: 4px;
  font-family: var(--font); text-align: right;
}
.btp-mini-btn {
  font-size: 11px; padding: 4px 10px; border-radius: 6px;
  border: 0.5px solid var(--border-mid, #d1d5db); background: white;
  cursor: pointer; color: var(--text-secondary, #6b7280); font-family: var(--font);
  transition: all .12s;
}
.btp-mini-btn:hover:not(:disabled) { background: var(--bg-secondary, #f3f4f6); color: var(--text-primary); }
.btp-mini-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btp-mini-btn.ghost { border-color: transparent; }

.btp-loading {
  padding: 18px 14px; display:flex; align-items: center; gap: 10px;
  color: var(--text-secondary); font-size: 12px;
}
.btp-spin {
  width: 14px; height: 14px; border-radius: 50%;
  border: 2px solid rgba(20,184,166,0.2); border-top-color: #14b8a6;
  animation: btp-spin 0.8s linear infinite; display: inline-block;
}
.btp-spin.sm { width: 10px; height: 10px; border-width: 1.5px; }
@keyframes btp-spin { to { transform: rotate(360deg); } }

.btp-empty {
  padding: 22px; text-align: center; color: var(--text-tertiary); font-size: 12px;
}
.btp-error {
  padding: 12px 14px; background: rgba(239,68,68,0.06);
  color: #b91c1c; font-size: 11.5px;
  border-bottom: 0.5px solid var(--border-light);
}

/* === 단계 1: 목록 모드 === */
.btp-list-bar {
  display:flex; align-items: center; gap: 8px;
  padding: 8px 14px;
  background: var(--bg-secondary, #f9fafb);
  border-bottom: 0.5px solid var(--border-light);
  font-size: 11.5px;
}
.btp-sel-all { display:inline-flex; gap:5px; align-items:center; cursor:pointer; }
.btp-sel-count { color: var(--text-tertiary); }
.btp-spacer { flex: 1; }
.btp-only-red {
  font-size: 11px; padding: 3px 8px; border-radius: 6px;
  border: 0.5px solid var(--border-mid); background: white; cursor: pointer;
  font-family: var(--font); color: var(--text-secondary);
}
.btp-only-red:hover:not(:disabled) { background: var(--bg-secondary); }
.btp-only-red:disabled { opacity: 0.4; cursor: not-allowed; }
.btp-go-btn {
  font-size: 12px; padding: 6px 14px; border-radius: 6px; border: none;
  background: linear-gradient(135deg, #8b5cf6, #6d28d9); color: white;
  font-weight: 600; cursor: pointer; font-family: var(--font);
  display: inline-flex; align-items: center; gap: 5px;
}
.btp-go-btn:hover:not(:disabled) { box-shadow: 0 2px 8px rgba(139,92,246,0.4); }
.btp-go-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.btp-list { max-height: 380px; overflow-y: auto; }
.btp-item {
  display:flex; align-items: center; gap: 8px;
  padding: 9px 14px;
  border-bottom: 0.5px solid var(--border-light);
  font-size: 11.5px;
}
.btp-item:hover { background: var(--bg-secondary, #f9fafb); }
.btp-item.rank-red    { border-left: 3px solid #ef4444; }
.btp-item.rank-yellow { border-left: 3px solid #f59e0b; }
.btp-item.rank-green  { border-left: 3px solid #22c55e; }
.btp-check { accent-color: var(--accent-blue, #3b82f6); flex-shrink: 0; }
.btp-rank-ico { font-size: 13px; flex-shrink: 0; }
.btp-item-main { flex: 1; min-width: 0; }
.btp-item-name {
  font-family: 'Consolas', 'SF Mono', monospace; font-weight: 600;
  font-size: 11.5px; color: var(--text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.btp-item-reasons { display: flex; flex-wrap: wrap; gap: 3px; margin-top: 3px; }
.btp-reason {
  font-size: 10px; padding: 1px 6px; border-radius: 4px;
  background: rgba(0,0,0,0.04); color: var(--text-secondary);
}
.btp-item.rank-red    .btp-reason { background: rgba(239,68,68,0.08); color: #b91c1c; }
.btp-item.rank-yellow .btp-reason { background: rgba(245,158,11,0.08); color: #b45309; }

.btp-item-metrics {
  display: inline-flex; gap: 8px; align-items: center;
  font-size: 10.5px; color: var(--text-tertiary); flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
.btp-m { font-weight: 500; }
.btp-score {
  background: var(--bg-secondary); padding: 1px 7px; border-radius: 8px;
  font-weight: 700; color: var(--text-primary); font-size: 10.5px;
}
.btp-item.rank-red .btp-score    { background: rgba(239,68,68,0.12); color: #b91c1c; }
.btp-item.rank-yellow .btp-score { background: rgba(245,158,11,0.12); color: #b45309; }

/* === 단계 2: split === */
.btp-split { display: grid; grid-template-columns: 280px 1fr; min-height: 440px; max-height: 640px; }
.btp-left {
  border-right: 0.5px solid var(--border-light);
  display: flex; flex-direction: column; min-height: 0;
}
.btp-left-head {
  padding: 8px 12px; background: var(--bg-secondary, #f9fafb);
  border-bottom: 0.5px solid var(--border-light);
  font-size: 11.5px; font-weight: 600; color: var(--text-secondary);
  display: flex; justify-content: space-between; align-items: center;
}
.btp-left-list { flex: 1; overflow-y: auto; min-height: 0; }
.btp-tune-row {
  padding: 9px 12px; border-bottom: 0.5px solid var(--border-light);
  cursor: pointer; transition: all .1s;
}
.btp-tune-row:hover { background: var(--bg-secondary); }
.btp-tune-row.active {
  background: rgba(139,92,246,0.06);
  border-left: 3px solid #8b5cf6;
  padding-left: 9px;
}
.btp-tune-row-name {
  font-family: 'Consolas', 'SF Mono', monospace;
  font-size: 11.5px; font-weight: 600; color: var(--text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.btp-tune-row-summary {
  display: inline-flex; gap: 6px; margin-top: 3px; align-items: center;
  font-size: 10.5px; color: var(--text-tertiary);
}
.btp-tune-row-summary .ok  { color: #15803d; font-weight: 600; }
.btp-tune-row-summary .bad { color: #b91c1c; font-weight: 600; }
.btp-rec-mark { font-size: 11px; }
.btp-tune-row-cnt { color: var(--text-tertiary); }

.btp-right {
  display: flex; flex-direction: column; min-height: 0;
  background: var(--bg-secondary, #fafbfc);
}
.btp-right-head {
  padding: 8px 14px; background: white;
  border-bottom: 0.5px solid var(--border-light);
  display: flex; justify-content: space-between; align-items: center;
  flex-shrink: 0;
}
.btp-right-title { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.btp-rt-name {
  font-family: 'Consolas', 'SF Mono', monospace;
  font-size: 12px; font-weight: 700; color: var(--text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 480px;
}
.btp-rt-meta { font-size: 10.5px; color: var(--text-tertiary); }

.btp-variants { flex: 1; overflow-y: auto; padding: 10px 12px; display: flex; flex-direction: column; gap: 10px; }
.btp-variant {
  background: white; border: 0.5px solid var(--border-light);
  border-radius: 8px; overflow: hidden;
  box-shadow: 0 1px 2px rgba(0,0,0,0.03);
}
.btp-variant.recommended { border-color: rgba(139,92,246,0.5); box-shadow: 0 2px 6px rgba(139,92,246,0.12); }
.btp-variant.top { border-width: 1px; }

.btp-v-head {
  display: flex; align-items: center; gap: 6px; padding: 7px 10px;
  background: var(--bg-secondary, #f9fafb);
  border-bottom: 0.5px solid var(--border-light);
  font-size: 11.5px; flex-wrap: wrap;
}
.btp-v-rank { font-size: 12px; flex-shrink: 0; }
.btp-v-label { font-weight: 700; color: var(--text-primary); }
.btp-v-strategy {
  color: var(--text-tertiary); font-size: 10.5px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 240px;
}
.btp-v-badge {
  font-size: 10px; padding: 1px 6px; border-radius: 8px; font-weight: 600;
  background: var(--bg-secondary); color: var(--text-secondary);
}
.btp-v-badge.rec { background: rgba(139,92,246,0.12); color: #6d28d9; }
.btp-v-badge.ok  { background: rgba(34,197,94,0.12); color: #15803d; }
.btp-v-badge.bad { background: rgba(239,68,68,0.12); color: #b91c1c; }
.btp-v-reason {
  padding: 5px 10px; font-size: 10.5px; color: var(--text-secondary);
  background: var(--bg-secondary, #fafbfc);
  border-bottom: 0.5px solid var(--border-light);
}
.btp-v-sql {
  padding: 8px 10px; font-family: 'Consolas', 'SF Mono', monospace;
  font-size: 11px; line-height: 1.5; color: var(--text-primary);
  background: white; margin: 0;
  white-space: pre-wrap; word-break: break-all;
  max-height: 220px; overflow-y: auto;
}
</style>
