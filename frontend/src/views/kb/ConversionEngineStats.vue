<!--
  변환 엔진 활용 현황 페이지 (KB 메뉴 아래)
  ===========================================
  
  본부장님 결정 (2026-05-10):
    "관리자 화면의 KB 메뉴 아래에 SQLGlot 관련 호출 횟수와
     어떻게 도움 받았고, 또 어떻게 우리 KB에서 수용 시켰는지
     상세히 볼 수 있는 페이지"
  
  4-Layer 시각화:
    - Layer 사용 비율 (도넛 차트)
    - 시간별 추이 (라인 차트)
    - SQLGlot 호출 상세 (테이블 + 흡수율 강조)
    - Rule Engine 누적 (시계열 그래프)
    - AI Provider 성공률 (막대 차트)
    - 최근 변환 50건 (디테일 테이블)
  
  골격 상태 (2026-05-10):
    - 레이아웃 + 섹션 + API 호출 정의
    - Phase 4 (다음 세션) 에 차트 라이브러리 + 실제 데이터 연결
-->
<template>
  <div class="conversion-engine-stats">
    <!-- 헤더 -->
    <div class="page-header">
      <h1>🧠 변환 엔진 활용 현황</h1>
      <p class="subtitle">
        4-Layer 변환 엔진의 활용 통계, SQLGlot 의존도, Rule Engine 자산 누적, AI Provider 성능
      </p>
      <div class="period-selector">
        <button v-for="p in periods" :key="p.value"
                :class="{ active: period === p.value }"
                @click="period = p.value; loadAll()">
          {{ p.label }}
        </button>
      </div>
    </div>

    <!-- 1. Layer 사용 비율 + 핵심 KPI -->
    <section class="section">
      <h2>Layer 사용 비율</h2>
      <div class="kpi-grid">
        <div class="kpi-card kb">
          <div class="kpi-label">Layer 1 — KB 매칭</div>
          <div class="kpi-value">{{ summary.layer_distribution.kb }}%</div>
          <div class="kpi-note">이미 검증된 자산 즉시 매칭</div>
        </div>
        <div class="kpi-card rule">
          <div class="kpi-label">Layer 2 — Rule Engine</div>
          <div class="kpi-value">{{ summary.layer_distribution.rule }}%</div>
          <div class="kpi-note">DataBridge 자체 변환 규칙</div>
        </div>
        <div class="kpi-card sqlglot">
          <div class="kpi-label">Layer 3 — SQLGlot</div>
          <div class="kpi-value">{{ summary.layer_distribution.sqlglot }}%</div>
          <div class="kpi-note">외부 라이브러리 (격리)</div>
        </div>
        <div class="kpi-card ai">
          <div class="kpi-label">Layer 4 — AI Provider</div>
          <div class="kpi-value">{{ summary.layer_distribution.ai }}%</div>
          <div class="kpi-note">AI fallback (다중 provider)</div>
        </div>
      </div>
      <div class="kpi-summary">
        <div class="summary-row">
          <span class="label">총 변환:</span>
          <span class="value">{{ summary.total_conversions.toLocaleString() }} 건</span>
        </div>
        <div class="summary-row highlight">
          <span class="label">절약된 AI 호출:</span>
          <span class="value">{{ summary.ai_call_saved.toLocaleString() }} 건</span>
          <span class="note">(KB+Rule+SQLGlot 으로 처리)</span>
        </div>
      </div>
      <!-- TODO Phase 4: 시간별 추이 차트 (Chart.js 또는 Recharts) -->
      <div class="chart-placeholder">
        <p>📊 시간별 추이 차트 (Phase 4 구현)</p>
      </div>
    </section>

    <!-- 2. SQLGlot 호출 상세 — 본부장님 의존성 모니터링 -->
    <section class="section sqlglot-section">
      <h2>🔍 SQLGlot 호출 상세 — 의존성 추적</h2>
      <div class="sqlglot-overview">
        <div class="metric">
          <div class="metric-label">호출 횟수 ({{ period }})</div>
          <div class="metric-value">{{ sqlglot.total_calls }}</div>
        </div>
        <div class="metric">
          <div class="metric-label">성공률</div>
          <div class="metric-value">{{ (sqlglot.success_rate * 100).toFixed(1) }}%</div>
        </div>
        <div class="metric highlight">
          <div class="metric-label">⭐ Rule Engine 흡수율</div>
          <div class="metric-value">{{ (sqlglot.rule_absorption_rate * 100).toFixed(1) }}%</div>
          <div class="metric-note">{{ sqlglot.absorbed_count }} 개 규칙이 영구 자산화됨</div>
        </div>
        <div class="metric">
          <div class="metric-label">SQLGlot 버전</div>
          <div class="metric-value">{{ sqlglot.version }}</div>
        </div>
      </div>
      <div class="philosophy-note">
        💡 <strong>본부장님 의존성 우려 정면 대응:</strong>
        SQLGlot 결과는 Rule Engine 으로 흡수되어 영구 자산화됩니다.
        시간이 갈수록 SQLGlot 호출 횟수는 ↓, Rule Engine 누적은 ↑
        — 외부 의존성이 0 으로 수렴하는 구조입니다.
      </div>
      <!-- TODO Phase 4: dialect 쌍별 성공률 + 최근 호출 테이블 -->
      <div class="chart-placeholder">
        <p>📊 dialect 쌍별 성공률 + 최근 SQLGlot 호출 50건 상세 (Phase 4)</p>
      </div>
    </section>

    <!-- 3. Rule Engine 자산 누적 -->
    <section class="section rule-section">
      <h2>📚 Rule Engine 자산 누적</h2>
      <div class="rule-overview">
        <div class="metric">
          <div class="metric-label">총 규칙 수</div>
          <div class="metric-value">{{ ruleEngine.total_rules }}</div>
        </div>
        <div class="metric">
          <div class="metric-label">총 사용 횟수</div>
          <div class="metric-value">{{ ruleEngine.total_use_count }}</div>
        </div>
      </div>
      <div class="category-grid">
        <div v-for="(count, cat) in ruleEngine.by_category" :key="cat" class="category-card">
          <div class="cat-name">{{ formatCategory(cat) }}</div>
          <div class="cat-count">{{ count }}</div>
        </div>
      </div>
      <!-- TODO Phase 4: 시간별 규칙 누적 그래프 + Top 10 사용 규칙 -->
      <div class="chart-placeholder">
        <p>📈 시간별 누적 + Top 10 사용 규칙 (Phase 4)</p>
      </div>
    </section>

    <!-- 4. AI Provider 별 통계 -->
    <section class="section ai-section">
      <h2>🤖 AI Provider 별 사용 + 성공률</h2>
      <!-- TODO Phase 4: provider/model 별 막대 차트 -->
      <div class="chart-placeholder">
        <p>📊 Provider/Model 별 사용 횟수 + 성공률 + 평균 응답 시간 (Phase 4)</p>
      </div>
    </section>

    <!-- 5. 최근 변환 상세 -->
    <section class="section recent-section">
      <h2>🕐 최근 변환 상세 (최근 50건)</h2>
      <table class="recent-table">
        <thead>
          <tr>
            <th>시각</th>
            <th>객체</th>
            <th>Layer 시도 순서</th>
            <th>최종 사용</th>
            <th>모델</th>
            <th>소요(ms)</th>
            <th>KB 동작</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="recent.items.length === 0">
            <td colspan="7" class="empty">데이터 없음 (Phase 4 에서 채워짐)</td>
          </tr>
          <tr v-for="item in recent.items" :key="item.id">
            <td>{{ item.ts }}</td>
            <td>{{ item.obj_type }} [{{ item.obj_name }}]</td>
            <td>{{ (item.layers_attempted || []).join(' → ') }}</td>
            <td><span :class="['layer-badge', item.layer_used]">{{ item.layer_used }}</span></td>
            <td>{{ item.model_used || '-' }}</td>
            <td>{{ item.elapsed_ms }}</td>
            <td>{{ item.kb_action }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script>
import axios from 'axios'

export default {
  name: 'ConversionEngineStats',
  data() {
    return {
      period: '7d',
      periods: [
        { value: '1h', label: '1시간' },
        { value: '24h', label: '24시간' },
        { value: '7d', label: '7일' },
        { value: '30d', label: '30일' },
        { value: 'all', label: '전체' },
      ],
      summary: {
        layer_distribution: { kb: 0, rule: 0, sqlglot: 0, ai: 0 },
        total_conversions: 0,
        ai_call_saved: 0,
      },
      sqlglot: {
        total_calls: 0,
        success_rate: 0,
        rule_absorption_rate: 0,
        absorbed_count: 0,
        version: 'n/a',
      },
      ruleEngine: {
        total_rules: 0,
        total_use_count: 0,
        by_category: {},
      },
      recent: { items: [] },
    }
  },
  mounted() {
    this.loadAll()
  },
  methods: {
    async loadAll() {
      try {
        const [s, sg, r, recent] = await Promise.all([
          axios.get(`/api/v1/conversion-stats/summary?period=${this.period}`),
          axios.get(`/api/v1/conversion-stats/sqlglot?period=${this.period}`),
          axios.get(`/api/v1/conversion-stats/rule-engine`),
          axios.get(`/api/v1/conversion-stats/recent?limit=50`),
        ])
        this.summary = s.data
        this.sqlglot = sg.data
        this.ruleEngine = r.data
        this.recent = recent.data
      } catch (e) {
        console.error('통계 로드 실패:', e)
      }
    },
    formatCategory(cat) {
      const map = {
        function_mapping: '함수 매핑',
        type_mapping: '타입 매핑',
        identifier_quoting: '식별자 quoting',
        schema_flattening: '스키마 평탄화',
        ddl_structure: 'DDL 구조',
        control_flow: '제어 흐름',
      }
      return map[cat] || cat
    },
  },
}
</script>

<style scoped>
.conversion-engine-stats {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}
.page-header {
  margin-bottom: 32px;
}
.page-header h1 {
  font-size: 28px;
  margin-bottom: 8px;
}
.subtitle {
  color: #666;
  margin-bottom: 16px;
}
.period-selector {
  display: flex;
  gap: 8px;
}
.period-selector button {
  padding: 6px 14px;
  border: 1px solid #d0d7de;
  background: #fff;
  border-radius: 6px;
  cursor: pointer;
}
.period-selector button.active {
  background: #0969da;
  color: #fff;
  border-color: #0969da;
}

.section {
  background: #fff;
  border: 1px solid #d0d7de;
  border-radius: 8px;
  padding: 24px;
  margin-bottom: 24px;
}
.section h2 {
  font-size: 20px;
  margin-bottom: 20px;
  border-bottom: 2px solid #f0f0f0;
  padding-bottom: 12px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.kpi-card {
  padding: 20px;
  border-radius: 8px;
  text-align: center;
  border: 2px solid #e1e4e8;
}
.kpi-card.kb { border-color: #2da44e; background: #e6f4ea; }
.kpi-card.rule { border-color: #0969da; background: #e6f0fa; }
.kpi-card.sqlglot { border-color: #bf8700; background: #fff8c5; }
.kpi-card.ai { border-color: #cf222e; background: #ffeef0; }
.kpi-label {
  font-size: 13px;
  font-weight: 600;
  color: #555;
  margin-bottom: 8px;
}
.kpi-value {
  font-size: 36px;
  font-weight: bold;
  margin-bottom: 4px;
}
.kpi-note {
  font-size: 12px;
  color: #666;
}

.kpi-summary {
  background: #f6f8fa;
  padding: 16px;
  border-radius: 6px;
}
.summary-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.summary-row.highlight { font-weight: bold; color: #2da44e; }
.summary-row .label { min-width: 140px; }
.summary-row .value { font-size: 16px; }
.summary-row .note { color: #666; font-size: 12px; }

.sqlglot-overview, .rule-overview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.metric {
  padding: 16px;
  background: #f6f8fa;
  border-radius: 6px;
  border-left: 4px solid #d0d7de;
}
.metric.highlight {
  border-left-color: #2da44e;
  background: #dafbe1;
}
.metric-label {
  font-size: 13px;
  color: #555;
  margin-bottom: 6px;
}
.metric-value {
  font-size: 24px;
  font-weight: bold;
}
.metric-note {
  font-size: 11px;
  color: #666;
  margin-top: 4px;
}

.philosophy-note {
  background: #ddf4ff;
  border-left: 4px solid #0969da;
  padding: 12px 16px;
  border-radius: 4px;
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 16px;
}

.category-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}
.category-card {
  padding: 12px;
  background: #f6f8fa;
  border-radius: 6px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.cat-name { font-weight: 500; }
.cat-count { font-size: 18px; font-weight: bold; color: #0969da; }

.chart-placeholder {
  background: #fafbfc;
  border: 2px dashed #d0d7de;
  padding: 40px;
  text-align: center;
  border-radius: 6px;
  color: #888;
}

.recent-table {
  width: 100%;
  border-collapse: collapse;
}
.recent-table th, .recent-table td {
  padding: 10px;
  border-bottom: 1px solid #e1e4e8;
  text-align: left;
  font-size: 13px;
}
.recent-table th {
  background: #f6f8fa;
  font-weight: 600;
}
.recent-table .empty {
  text-align: center;
  color: #999;
  padding: 30px;
}
.layer-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
}
.layer-badge.kb { background: #dafbe1; color: #1a7f37; }
.layer-badge.rule { background: #ddf4ff; color: #0969da; }
.layer-badge.sqlglot { background: #fff8c5; color: #9a6700; }
.layer-badge.ai { background: #ffeef0; color: #cf222e; }
</style>
