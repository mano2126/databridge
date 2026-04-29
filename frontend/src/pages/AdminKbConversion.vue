<template>
  <div class="kb-conv">
    <!-- 상단 자산 요약 카드 -->
    <div class="stats-grid" v-if="overview">
      <div class="stat-card">
        <div class="stat-label">타입 매핑 규칙</div>
        <div class="stat-value">{{ overview.type_mapping.total.toLocaleString() }}</div>
        <div class="stat-sub">
          수동 <b>{{ overview.type_mapping.manual }}</b> ·
          AI 학습 <b>{{ overview.type_mapping.ai_learned }}</b>
        </div>
      </div>
      <div class="stat-card ok">
        <div class="stat-label">활성 (Active)</div>
        <div class="stat-value">{{ (overview.type_mapping.active + overview.object_mapping.active).toLocaleString() }}</div>
        <div class="stat-sub">즉시 변환에 사용</div>
      </div>
      <div class="stat-card warn">
        <div class="stat-label">검토 대기 (Shadow)</div>
        <div class="stat-value">{{ (overview.type_mapping.shadow + overview.object_mapping.shadow).toLocaleString() }}</div>
        <div class="stat-sub">confidence ≥ 3 시 자동 승격</div>
      </div>
      <div class="stat-card ai">
        <div class="stat-label">오브젝트 매핑 규칙</div>
        <div class="stat-value">{{ overview.object_mapping.total.toLocaleString() }}</div>
        <div class="stat-sub">
          수동 <b>{{ overview.object_mapping.manual }}</b> ·
          AI 학습 <b>{{ overview.object_mapping.ai_learned }}</b>
        </div>
      </div>
    </div>

    <!-- AI 호출 추이 차트 -->
    <div class="panel chart-panel">
      <div class="panel-head">
        <h3>AI 호출 추이 <span class="muted small">(목표: 시간이 지날수록 로컬 비율 ↑)</span></h3>
        <div style="display:flex;gap:8px;align-items:center">
          <select v-model.number="days" @change="load" class="days-sel">
            <option :value="7">최근 7일</option>
            <option :value="30">최근 30일</option>
            <option :value="90">최근 90일</option>
          </select>
          <button class="btn-ghost" @click="load">🔄 새로고침</button>
        </div>
      </div>

      <div class="metric-summary" v-if="metrics">
        <div class="ms-cell">
          <div class="ms-label">AI 호출</div>
          <div class="ms-val">{{ metrics.summary.ai_calls.toLocaleString() }}</div>
        </div>
        <div class="ms-cell">
          <div class="ms-label">로컬 처리</div>
          <div class="ms-val ok">{{ metrics.summary.local_hits.toLocaleString() }}</div>
        </div>
        <div class="ms-cell">
          <div class="ms-label">학습된 패턴</div>
          <div class="ms-val">+{{ metrics.summary.patterns_learned.toLocaleString() }}</div>
        </div>
        <div class="ms-cell">
          <div class="ms-label">로컬 처리율</div>
          <div class="ms-val" :class="{ok: metrics.summary.local_ratio >= 0.5}">
            {{ Math.round((metrics.summary.local_ratio || 0) * 100) }}%
          </div>
        </div>
      </div>

      <!-- SVG 미니 차트 -->
      <div class="chart-wrap" v-if="metrics && metrics.daily.length">
        <svg :viewBox="`0 0 ${chartW} ${chartH}`" class="mini-chart">
          <!-- 격자 -->
          <line v-for="y in [0, 0.25, 0.5, 0.75, 1]" :key="y"
                :x1="40" :x2="chartW - 10"
                :y1="20 + y * (chartH - 40)" :y2="20 + y * (chartH - 40)"
                stroke="var(--border-color, #e5e7eb)" stroke-dasharray="2,4" stroke-width="0.5"/>
          <!-- AI 호출 (주황) -->
          <polyline :points="aiPoints" fill="none" stroke="#f59e0b" stroke-width="2"/>
          <!-- 로컬 처리 (초록) -->
          <polyline :points="localPoints" fill="none" stroke="#10b981" stroke-width="2"/>
          <!-- X축 라벨 (첫/중간/끝) -->
          <text v-for="(d, i) in xLabels" :key="i"
                :x="xFor(d.idx)" :y="chartH - 4"
                text-anchor="middle" font-size="10" fill="var(--text-muted, #6b7280)">
            {{ d.label }}
          </text>
          <!-- Y축 라벨 -->
          <text :x="34" :y="24" text-anchor="end" font-size="10" fill="var(--text-muted, #6b7280)">
            {{ maxY }}
          </text>
          <text :x="34" :y="chartH - 20" text-anchor="end" font-size="10" fill="var(--text-muted, #6b7280)">0</text>
        </svg>
        <div class="legend">
          <span><i style="background:#f59e0b"></i> AI 호출</span>
          <span><i style="background:#10b981"></i> 로컬 처리</span>
        </div>
      </div>
      <div v-else class="empty">
        아직 데이터가 없습니다. 변환 작업을 수행하면 자동으로 집계됩니다.
      </div>
    </div>

    <!-- 2단: 타입매핑 학습 + 오브젝트매핑 학습 -->
    <div class="two-col">
      <div class="panel">
        <div class="panel-head">
          <h3>타입 매핑 — 자산 구성</h3>
        </div>
        <table class="asset-table" v-if="overview">
          <thead><tr><th>구분</th><th>건수</th><th>비율</th></tr></thead>
          <tbody>
            <tr><td><span class="src-badge manual">수동 등록</span></td>
                <td>{{ overview.type_mapping.manual }}</td>
                <td>{{ pct(overview.type_mapping.manual, overview.type_mapping.total) }}%</td></tr>
            <tr><td><span class="src-badge ai">AI 학습 · Active</span></td>
                <td>{{ aiActive('type_mapping') }}</td>
                <td>{{ pct(aiActive('type_mapping'), overview.type_mapping.total) }}%</td></tr>
            <tr><td><span class="src-badge shadow">AI 학습 · Shadow</span></td>
                <td>{{ overview.type_mapping.shadow }}</td>
                <td>{{ pct(overview.type_mapping.shadow, overview.type_mapping.total) }}%</td></tr>
            <tr><td><span class="src-badge rejected">거부됨</span></td>
                <td>{{ overview.type_mapping.rejected }}</td>
                <td>{{ pct(overview.type_mapping.rejected, overview.type_mapping.total) }}%</td></tr>
            <tr class="tot"><td><b>합계</b></td>
                <td><b>{{ overview.type_mapping.total }}</b></td>
                <td>100%</td></tr>
          </tbody>
        </table>
        <div class="panel-hint">
          👉 상세 관리 및 편집: <a href="#/mapping">타입 매핑 페이지</a> 에서 출처 뱃지 / confidence 확인
        </div>
      </div>

      <div class="panel">
        <div class="panel-head">
          <h3>오브젝트 매핑 — 자산 구성</h3>
        </div>
        <table class="asset-table" v-if="overview">
          <thead><tr><th>구분</th><th>건수</th><th>비율</th></tr></thead>
          <tbody>
            <tr><td><span class="src-badge manual">수동 등록</span></td>
                <td>{{ overview.object_mapping.manual }}</td>
                <td>{{ pct(overview.object_mapping.manual, overview.object_mapping.total) }}%</td></tr>
            <tr><td><span class="src-badge ai">AI 학습 · Active</span></td>
                <td>{{ aiActive('object_mapping') }}</td>
                <td>{{ pct(aiActive('object_mapping'), overview.object_mapping.total) }}%</td></tr>
            <tr><td><span class="src-badge shadow">AI 학습 · Shadow</span></td>
                <td>{{ overview.object_mapping.shadow }}</td>
                <td>{{ pct(overview.object_mapping.shadow, overview.object_mapping.total) }}%</td></tr>
            <tr><td><span class="src-badge rejected">거부됨</span></td>
                <td>{{ overview.object_mapping.rejected }}</td>
                <td>{{ pct(overview.object_mapping.rejected, overview.object_mapping.total) }}%</td></tr>
            <tr class="tot"><td><b>합계</b></td>
                <td><b>{{ overview.object_mapping.total }}</b></td>
                <td>100%</td></tr>
          </tbody>
        </table>
        <div class="panel-hint">
          👉 상세 관리 및 편집: <a href="#/obj-mapping">오브젝트 매핑 페이지</a>
        </div>
      </div>
    </div>

    <!-- 운영 가이드 -->
    <div class="panel guide">
      <h3>📘 변환 KB 자동 학습 동작 방식</h3>
      <ol>
        <li>AI 가 DDL 을 변환할 때마다 결과에서 타입쌍·구문쌍을 자동 추출 → <b>shadow</b> 상태로 등록</li>
        <li>같은 패턴이 <b>3회 이상 반복</b>되면 confidence 누적되어 자동으로 <b>active</b> 승격</li>
        <li>Active 규칙은 다음 변환부터 로컬에서 우선 적용 (AI 호출 회피)</li>
        <li>실수 학습이면 관리자가 <b>거부(rejected)</b> 처리 가능 — 이후 해당 규칙은 영구 비활성</li>
      </ol>
      <p class="muted small">
        <b>검증 지표</b>: 위 차트에서 주황선(AI 호출)이 감소하고 초록선(로컬 처리)이 증가하면 KB 자산이 제대로 축적되는 중.
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import kbApi from '@/api/kb.js'

defineOptions({ name: 'AdminKbConversion' })

const days = ref(30)
const overview = ref(null)
const metrics = ref(null)

const chartW = 680
const chartH = 180

function pct(a, b) {
  if (!b) return 0
  return Math.round((a / b) * 1000) / 10
}

function aiActive(key) {
  if (!overview.value) return 0
  const o = overview.value[key]
  // active 전체 - 수동 active 추정: overview 에선 manual 을 모두 active 로 가정 (소프트 추가 필드)
  // 정확히는 "ai_learned & active" 개수가 필요하지만 현재 스키마에서는 active - manual 로 근사
  return Math.max(0, (o.active || 0) - (o.manual || 0))
}

const maxY = computed(() => {
  if (!metrics.value || !metrics.value.daily.length) return 1
  let m = 1
  for (const d of metrics.value.daily) {
    m = Math.max(m, d.ai_calls || 0, d.local_hits || 0)
  }
  return m
})

function xFor(i) {
  const n = (metrics.value?.daily.length || 1)
  if (n === 1) return (chartW - 50) / 2 + 40
  return 40 + (i / (n - 1)) * (chartW - 50)
}
function yFor(v) {
  return 20 + (1 - v / maxY.value) * (chartH - 40)
}

const aiPoints = computed(() => {
  if (!metrics.value) return ''
  return metrics.value.daily.map((d, i) => `${xFor(i)},${yFor(d.ai_calls || 0)}`).join(' ')
})
const localPoints = computed(() => {
  if (!metrics.value) return ''
  return metrics.value.daily.map((d, i) => `${xFor(i)},${yFor(d.local_hits || 0)}`).join(' ')
})

const xLabels = computed(() => {
  if (!metrics.value || !metrics.value.daily.length) return []
  const n = metrics.value.daily.length
  const idxs = n <= 3 ? [...Array(n).keys()] : [0, Math.floor(n / 2), n - 1]
  return idxs.map(i => ({
    idx: i,
    label: (metrics.value.daily[i].date || '').slice(5),  // MM-DD
  }))
})

async function load() {
  try {
    const [ov, mt] = await Promise.all([
      kbApi.conversionOverview(),
      kbApi.conversionMetrics(days.value),
    ])
    overview.value = ov
    metrics.value  = mt
  } catch (e) {
    console.error('변환 KB 로드 실패:', e)
  }
}

onMounted(load)
defineExpose({ reload: load })
</script>

<style scoped>
.kb-conv { display: flex; flex-direction: column; gap: 20px; }

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}
.stat-card {
  background: var(--surface, #fff);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 10px;
  padding: 16px;
}
.stat-card.ok { border-left: 4px solid #10b981; }
.stat-card.warn { border-left: 4px solid #f59e0b; }
.stat-card.ai { border-left: 4px solid #6366f1; }
.stat-label { font-size: 12px; color: var(--text-muted, #6b7280); margin-bottom: 6px; }
.stat-value { font-size: 26px; font-weight: 700; color: var(--text-color, #111827); }
.stat-sub { font-size: 11px; color: var(--text-muted, #6b7280); margin-top: 4px; }

.panel {
  background: var(--surface, #fff);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 10px;
  padding: 16px 18px;
}
.panel-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 12px;
}
.panel-head h3 { margin: 0; font-size: 15px; font-weight: 600; }
.muted { color: var(--text-muted, #6b7280); }
.small { font-size: 11px; font-weight: normal; }

.days-sel {
  padding: 6px 10px;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 6px;
  background: var(--surface, #fff);
  color: var(--text-color, #111827);
}
.btn-ghost {
  padding: 6px 12px;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 6px;
  background: var(--surface, #fff);
  cursor: pointer;
  color: var(--text-color, #111827);
}
.btn-ghost:hover { background: var(--hover-bg, #f3f4f6); }

.metric-summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
  padding: 12px;
  background: var(--subtle-bg, #f9fafb);
  border-radius: 8px;
}
.ms-cell { text-align: center; }
.ms-label { font-size: 11px; color: var(--text-muted, #6b7280); margin-bottom: 4px; }
.ms-val { font-size: 18px; font-weight: 700; }
.ms-val.ok { color: #10b981; }

.chart-wrap {
  background: var(--subtle-bg, #f9fafb);
  border-radius: 8px;
  padding: 8px;
}
.mini-chart { width: 100%; height: auto; display: block; }
.legend {
  display: flex; gap: 16px; justify-content: center; padding-top: 6px;
  font-size: 12px; color: var(--text-muted, #6b7280);
}
.legend i {
  display: inline-block; width: 14px; height: 3px;
  margin-right: 6px; vertical-align: middle;
}

.two-col {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
}
.asset-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.asset-table th, .asset-table td {
  padding: 8px 10px;
  text-align: left;
  border-bottom: 1px solid var(--border-color, #e5e7eb);
}
.asset-table th { font-weight: 600; color: var(--text-muted, #6b7280); font-size: 12px; }
.asset-table tr.tot td { border-top: 2px solid var(--border-color, #e5e7eb); border-bottom: none; }

.src-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}
.src-badge.manual   { background: #dbeafe; color: #1e40af; }
.src-badge.ai       { background: #d1fae5; color: #065f46; }
.src-badge.shadow   { background: #fef3c7; color: #92400e; }
.src-badge.rejected { background: #f3f4f6; color: #6b7280; text-decoration: line-through; }

.panel-hint {
  margin-top: 10px;
  padding: 8px 12px;
  background: var(--subtle-bg, #f9fafb);
  border-radius: 6px;
  font-size: 12px;
  color: var(--text-muted, #6b7280);
}
.panel-hint a { color: #6366f1; text-decoration: none; }
.panel-hint a:hover { text-decoration: underline; }

.guide ol { margin: 10px 0; padding-left: 24px; line-height: 1.7; }
.guide li { font-size: 13px; }

.empty {
  padding: 32px;
  text-align: center;
  color: var(--text-muted, #6b7280);
  font-size: 13px;
}
</style>
