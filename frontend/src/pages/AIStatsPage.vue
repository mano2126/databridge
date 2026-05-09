<!--
  AIStatsPage.vue — AI 사용 통계 관리자 화면
  v95_p78 (2026-05-06 본부장님)
  
  본부장님 호소:
    "AI 이용을 최소화 시켰는지 조회하는 관리자 화면"
    "운영화면에서 AI 접속 목록을 보는데 너무 약해서"
    "정확한지도 잘 모르겠어"
    "좀더 강력하고, 다양하게 조회 할 수 있는 화면"
  
  표시 정보:
    1) 요약 카드: AI 호출, 캐시 히트, KB 매칭, 환각 자동 수정, 비용 절감 %
    2) 캐시 통계 (객체 타입별, DB 쌍별)
    3) KB 효과 (사용자 manual / AI 성공 분포 + Top 10)
    4) 환각 검출 + 자동 수정 통계
    5) 차단된 객체 목록 (사용자 결정 필요)
    6) 최근 AI 호출 이력 (실시간)
-->
<template>
  <div class="ai-stats-page">
    <!-- 헤더 -->
    <div class="aip-header">
      <h2>📊 AI 사용 통계 + 비용 모니터링</h2>
      <div class="aip-controls">
        <select v-model="periodHours" @change="loadAll">
          <option :value="1">최근 1시간</option>
          <option :value="6">최근 6시간</option>
          <option :value="24">최근 24시간</option>
          <option :value="168">최근 7일</option>
          <option :value="720">최근 30일</option>
        </select>
        <button @click="loadAll" class="aip-refresh-btn">↻ 새로 고침</button>
      </div>
    </div>
    
    <!-- 요약 카드 -->
    <div class="aip-summary-grid" v-if="summary">
      <div class="aip-card aip-card-primary">
        <div class="aip-card-label">AI 호출 (실제)</div>
        <div class="aip-card-value">{{ summary.ai_calls_total }}</div>
        <div class="aip-card-sub">최근 {{ summary.period_hours }}시간</div>
      </div>
      <div class="aip-card aip-card-success">
        <div class="aip-card-label">💾 캐시 히트</div>
        <div class="aip-card-value">{{ summary.savings.cache_hits }}</div>
        <div class="aip-card-sub">v95_p58 — AI 호출 0</div>
      </div>
      <div class="aip-card aip-card-success">
        <div class="aip-card-label">🧠 KB 매칭</div>
        <div class="aip-card-value">{{ summary.savings.kb_matches }}</div>
        <div class="aip-card-sub">v95_p69 — AI 호출 0</div>
      </div>
      <div class="aip-card aip-card-warning">
        <div class="aip-card-label">⚠️ 환각 검출</div>
        <div class="aip-card-value">{{ summary.hallucination.detected }}</div>
        <div class="aip-card-sub">자동 수정: {{ summary.hallucination.auto_fixed }}</div>
      </div>
      <div class="aip-card aip-card-info">
        <div class="aip-card-label">⊘ 사용자 결정</div>
        <div class="aip-card-value">{{ summary.savings.user_manual + summary.savings.user_exclude }}</div>
        <div class="aip-card-sub">manual: {{ summary.savings.user_manual }} / exclude: {{ summary.savings.user_exclude }}</div>
      </div>
      <div class="aip-card aip-card-highlight">
        <div class="aip-card-label">💰 비용 절감</div>
        <div class="aip-card-value">{{ summary.cost.saved_pct }}%</div>
        <div class="aip-card-sub">{{ summary.cost.total_attempts }} 중 {{ summary.savings.total }} 절감</div>
      </div>
    </div>
    
    <!-- 캐시 통계 -->
    <div class="aip-section" v-if="cacheStats">
      <h3>💾 AI 변환 캐시 (v95_p58)</h3>
      <div class="aip-stats-row">
        <div><strong>총 캐시:</strong> {{ cacheStats.total_cached }}건</div>
        <div v-for="(c, t) in cacheStats.by_type" :key="t" v-if="c > 0">
          <span class="aip-tag">{{ t }}</span> {{ c }}
        </div>
      </div>
      <div class="aip-stats-row" v-if="cacheStats.oldest">
        <small>가장 오래된 캐시: {{ cacheStats.oldest }} / 최근: {{ cacheStats.newest }}</small>
      </div>
    </div>
    
    <!-- KB 통계 -->
    <div class="aip-section" v-if="kbStats">
      <h3>🧠 변환 패턴 KB (v95_p69)</h3>
      <div class="aip-stats-row">
        <div><strong>총 패턴:</strong> {{ kbStats.total_patterns }}건</div>
        <div><span class="aip-tag aip-tag-purple">사용자 작성</span> {{ kbStats.by_source.user_manual }}</div>
        <div><span class="aip-tag aip-tag-green">AI 성공</span> {{ kbStats.by_source.ai_success }}</div>
        <div><strong>총 사용:</strong> {{ kbStats.total_uses }}회 (절감 효과)</div>
      </div>
      <div v-if="kbStats.top_used && kbStats.top_used.length > 0">
        <h4>🏆 Top 10 자주 매칭된 패턴</h4>
        <table class="aip-table">
          <thead>
            <tr><th>객체 타입</th><th>객체명</th><th>출처</th><th>사용 횟수</th><th>등록일</th></tr>
          </thead>
          <tbody>
            <tr v-for="(p, i) in kbStats.top_used" :key="i">
              <td><span class="aip-tag">{{ p.obj_type }}</span></td>
              <td>{{ p.obj_name }}</td>
              <td>
                <span class="aip-tag" :class="p.source === 'user_manual' ? 'aip-tag-purple' : 'aip-tag-green'">
                  {{ p.source === 'user_manual' ? '✍️ 사용자' : '🤖 AI' }}
                </span>
              </td>
              <td><strong>{{ p.use_count }}회</strong></td>
              <td>{{ formatDate(p.registered_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    
    <!-- 차단된 객체 -->
    <div class="aip-section" v-if="failures && failures.blocked_count > 0">
      <h3>🚫 차단된 객체 (v95_p70 — 사용자 결정 필요)</h3>
      <p class="aip-help">AI 가 N회 실패한 객체. 위저드에서 [수동 SQL] 또는 [이관 제외] 결정 필요.</p>
      <table class="aip-table">
        <thead>
          <tr><th>타입</th><th>객체명</th><th>실패 횟수</th><th>마지막 오류</th><th>마지막 실패</th></tr>
        </thead>
        <tbody>
          <tr v-for="(f, i) in failures.blocked" :key="i">
            <td>{{ f.obj_type }}</td>
            <td>{{ f.obj_name_sample }}</td>
            <td><span class="aip-tag aip-tag-red">{{ f.ai_failures }}회</span></td>
            <td class="aip-error-cell">{{ f.last_error }}</td>
            <td>{{ formatDate(f.last_failed_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    
    <!-- 최근 호출 이력 -->
    <div class="aip-section" v-if="recentCalls && recentCalls.length > 0">
      <h3>📜 최근 AI 호출 이력 ({{ recentCalls.length }}건)</h3>
      <table class="aip-table aip-table-compact">
        <thead>
          <tr><th>시간</th><th>타입</th><th>객체</th><th>상태</th><th>방식</th></tr>
        </thead>
        <tbody>
          <tr v-for="(c, i) in recentCalls" :key="i">
            <td><small>{{ c.ts }}</small></td>
            <td>{{ c.obj_type }}</td>
            <td>{{ c.obj_name }}</td>
            <td>
              <span class="aip-tag" :class="c.status === '완료' ? 'aip-tag-green' : c.status === '실패' ? 'aip-tag-red' : 'aip-tag-blue'">
                {{ c.status }}
              </span>
            </td>
            <td>
              <span class="aip-tag" :class="
                c.method === 'ai_cached' ? 'aip-tag-success' :
                c.method === 'kb_matched' ? 'aip-tag-purple' :
                c.method === 'blocked' ? 'aip-tag-red' : 'aip-tag-blue'">
                {{ c.method === 'ai_cached' ? '💾 캐시' :
                   c.method === 'kb_matched' ? '🧠 KB' :
                   c.method === 'blocked' ? '🚫 차단' : '🤖 AI' }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    
    <!-- 로딩/오류 -->
    <div v-if="loading" class="aip-loading">⏳ 로딩 중...</div>
    <div v-if="error" class="aip-error">❌ {{ error }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const periodHours = ref(24)
const summary = ref(null)
const cacheStats = ref(null)
const kbStats = ref(null)
const failures = ref(null)
const recentCalls = ref([])
const loading = ref(false)
const error = ref('')

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [s, c, k, f, r] = await Promise.all([
      axios.get('/api/v1/ai-stats/summary', { params: { hours: periodHours.value } }),
      axios.get('/api/v1/ai-stats/cache-stats'),
      axios.get('/api/v1/ai-stats/kb-stats'),
      axios.get('/api/v1/ai-stats/failures'),
      axios.get('/api/v1/ai-stats/recent-calls', { params: { limit: 50 } }),
    ])
    summary.value = s.data
    cacheStats.value = c.data
    kbStats.value = k.data
    failures.value = f.data
    recentCalls.value = r.data.calls || []
  } catch (e) {
    error.value = e.message || String(e)
    console.error('[v95_p78] AI Stats 로딩 실패:', e)
  } finally {
    loading.value = false
  }
}

function formatDate(s) {
  if (!s) return ''
  return s.replace('T', ' ').slice(0, 19)
}

onMounted(loadAll)
</script>

<style scoped>
.ai-stats-page {
  padding: 20px 24px;
  max-width: 1400px; margin: 0 auto;
}
.aip-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 20px; padding-bottom: 14px;
  border-bottom: 1px solid var(--border-light, #e5e7eb);
}
.aip-header h2 { margin: 0; font-size: 20px; }
.aip-controls { display: flex; gap: 10px; align-items: center; }
.aip-controls select {
  padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px;
  font-size: 13px;
}
.aip-refresh-btn {
  padding: 6px 14px; background: #2563eb; color: white; border: none;
  border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600;
}
.aip-refresh-btn:hover { background: #1d4ed8; }

.aip-summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px; margin-bottom: 24px;
}
.aip-card {
  padding: 16px 18px; background: white;
  border: 1px solid var(--border-light, #e5e7eb);
  border-radius: 8px;
  display: flex; flex-direction: column; gap: 4px;
}
.aip-card-label { font-size: 12px; color: #6b7280; font-weight: 600; }
.aip-card-value { font-size: 28px; font-weight: 700; color: #1f2937; line-height: 1.1; }
.aip-card-sub { font-size: 11px; color: #9ca3af; }
.aip-card-primary { border-left: 4px solid #2563eb; }
.aip-card-success { border-left: 4px solid #16a34a; }
.aip-card-warning { border-left: 4px solid #f59e0b; }
.aip-card-info { border-left: 4px solid #7c3aed; }
.aip-card-highlight {
  border-left: 4px solid #ec4899;
  background: linear-gradient(135deg, rgba(236, 72, 153, 0.05), rgba(124, 58, 237, 0.05));
}
.aip-card-highlight .aip-card-value { color: #ec4899; }

.aip-section {
  margin-bottom: 24px; padding: 18px 20px;
  background: white; border: 1px solid var(--border-light, #e5e7eb);
  border-radius: 8px;
}
.aip-section h3 { margin: 0 0 12px 0; font-size: 15px; }
.aip-section h4 { margin: 14px 0 8px 0; font-size: 13px; color: #6b7280; }
.aip-help { font-size: 12px; color: #6b7280; margin: 0 0 10px 0; }

.aip-stats-row {
  display: flex; gap: 18px; flex-wrap: wrap;
  font-size: 13px; color: #374151;
}

.aip-table {
  width: 100%; border-collapse: collapse; font-size: 12.5px;
}
.aip-table th { background: #f9fafb; padding: 8px 10px; text-align: left; font-weight: 600; }
.aip-table td { padding: 8px 10px; border-top: 1px solid #f3f4f6; }
.aip-table-compact th, .aip-table-compact td { padding: 5px 8px; font-size: 11.5px; }
.aip-error-cell { font-family: monospace; font-size: 11px; max-width: 400px; overflow: hidden; text-overflow: ellipsis; }

.aip-tag {
  display: inline-block; padding: 2px 8px; border-radius: 10px;
  font-size: 10.5px; font-weight: 600;
  background: #f3f4f6; color: #374151;
}
.aip-tag-success, .aip-tag-green { background: rgba(34, 197, 94, 0.15); color: #15803d; }
.aip-tag-red    { background: rgba(220, 38, 38, 0.15); color: #b91c1c; }
.aip-tag-purple { background: rgba(168, 85, 247, 0.15); color: #6d28d9; }
.aip-tag-blue   { background: rgba(37, 99, 235, 0.15); color: #1e40af; }

.aip-loading { text-align: center; padding: 40px; color: #6b7280; }
.aip-error {
  padding: 12px 16px; background: rgba(220, 38, 38, 0.08);
  border: 1px solid rgba(220, 38, 38, 0.3); border-radius: 6px;
  color: #b91c1c; font-size: 13px;
}
</style>
