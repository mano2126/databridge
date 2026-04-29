<template>
  <div class="kb-page">
    <div class="page-header">
      <div>
        <h2>지식 베이스 관리</h2>
        <p class="muted">AI 호출을 절감하기 위한 에러 패턴 및 변환 규칙의 지식 자산 축적 대시보드.</p>
      </div>
    </div>

    <!-- 탭 바 (v10 #18) -->
    <div class="tab-bar">
      <button class="tab" :class="{active: tab === 'error'}" @click="tab = 'error'">
        🚨 에러 KB
      </button>
      <button class="tab" :class="{active: tab === 'conversion'}" @click="tab = 'conversion'">
        🔄 변환 KB (타입/오브젝트 자동 학습)
      </button>
    </div>

    <!-- 탭 2: 변환 KB -->
    <AdminKbConversion v-if="tab === 'conversion'" />

    <!-- 탭 1: 기존 에러 KB (원본 유지) -->
    <div v-show="tab === 'error'" class="kb-inner">
      <div class="page-header" style="margin-top:0">
        <div>
          <h3 style="margin:0">에러 프롬프트 지식 베이스</h3>
          <p class="muted">AI 재이관 효율을 높이기 위한 에러 패턴별 교정 지침 관리. (v10 #17)</p>
        </div>
        <div style="display:flex;gap:8px">
          <select v-model.number="days" @change="load" class="days-sel">
            <option :value="7">최근 7일</option>
            <option :value="30">최근 30일</option>
            <option :value="90">최근 90일</option>
            <option :value="365">최근 1년</option>
          </select>
          <button class="btn-ghost" @click="reloadKb" :disabled="reloading">
            <span v-if="reloading" class="spin-sm"></span>
            <span v-else>📂 YAML 재로드</span>
          </button>
          <button class="btn-ghost" @click="load">🔄 새로고침</button>
        </div>
      </div>

    <!-- 상단 통계 카드 4개 -->
    <div class="stats-grid" v-if="stats">
      <div class="stat-card">
        <div class="stat-label">총 재처리 시도</div>
        <div class="stat-value">{{ (stats.total_attempts || 0).toLocaleString() }}</div>
        <div class="stat-sub">최근 {{ days }}일</div>
      </div>
      <div class="stat-card ok">
        <div class="stat-label">성공</div>
        <div class="stat-value">{{ (stats.total_success || 0).toLocaleString() }}</div>
        <div class="stat-sub">{{ Math.round((stats.overall_rate || 0) * 100) }}% 성공률</div>
      </div>
      <div class="stat-card ai">
        <div class="stat-label">AI 호출</div>
        <div class="stat-value">{{ (stats.ai_attempts || 0).toLocaleString() }}</div>
        <div class="stat-sub">{{ stats.ai_attempts ? Math.round((stats.total_success || 0) / stats.ai_attempts * 100) : 0 }}% 성공</div>
      </div>
      <div class="stat-card saved">
        <div class="stat-label">AI 호출 절감</div>
        <div class="stat-value">{{ (stats.ai_saved || 0).toLocaleString() }}</div>
        <div class="stat-sub">설정·엔진 규칙으로 해결</div>
      </div>
    </div>

    <!-- 본문 2단 -->
    <div class="kb-body">
      <!-- 좌: 패턴 목록 -->
      <div class="panel">
        <div class="panel-head">
          <h3>등록된 패턴 <span class="count">({{ patterns.length }})</span></h3>
          <div class="filter-bar">
            <select v-model="filterCategory" class="filter-sel">
              <option value="">모든 카테고리</option>
              <option value="SYNTAX">SYNTAX (1064)</option>
              <option value="PERMISSION">PERMISSION</option>
              <option value="DDL">DDL</option>
              <option value="RUNTIME">RUNTIME</option>
              <option value="TYPE">TYPE</option>
              <option value="SEMANTIC">SEMANTIC</option>
            </select>
            <select v-model="filterFixType" class="filter-sel">
              <option value="">모든 처리 유형</option>
              <option value="prompt_injection">AI 프롬프트 주입</option>
              <option value="config_change">설정 변경 (DBA)</option>
              <option value="engine_rule">엔진 자동 처리</option>
            </select>
          </div>
        </div>

        <div class="pattern-list">
          <div v-if="!patterns.length" class="empty">
            등록된 패턴이 없습니다. YAML 파일을 확인하세요.
          </div>
          <div v-for="p in filteredPatterns" :key="p.id" class="pattern-card" :class="'fix-' + p.fix_type">
            <div class="pc-head">
              <span class="pc-id">{{ p.id }}</span>
              <span class="pc-code">{{ p.error_code }}</span>
              <span class="pc-cat" :class="'cat-' + (p.category || '').toLowerCase()">{{ p.category || '-' }}</span>
              <span v-if="p.ai_skip" class="pc-badge ai-skip" title="AI 호출 없이 해결">⏭ AI 스킵</span>
              <span v-else class="pc-badge ai-use" title="AI 프롬프트에 주입">💉 AI 주입</span>
            </div>
            <div class="pc-cause">{{ p.cause || '-' }}</div>
            <div class="pc-stats" v-if="patternStatsMap[p.id]">
              <span>시도 <b>{{ patternStatsMap[p.id].attempts }}</b></span>
              <span>성공 <b>{{ patternStatsMap[p.id].success }}</b></span>
              <span :class="{'good': patternStatsMap[p.id].rate >= 0.8, 'poor': patternStatsMap[p.id].rate < 0.5}">
                성공률 <b>{{ Math.round(patternStatsMap[p.id].rate * 100) }}%</b>
              </span>
              <span class="pc-last">{{ fmtDate(patternStatsMap[p.id].last_seen) }}</span>
            </div>
            <div v-else class="pc-stats-empty">
              아직 실전 통계 없음 (0건)
            </div>
          </div>
        </div>
      </div>

      <!-- 우: 테스트 매칭 + 미매칭 샘플 -->
      <div class="panel">
        <div class="panel-head">
          <h3>패턴 매칭 테스트</h3>
        </div>
        <div class="test-box">
          <textarea v-model="testError"
                    placeholder="실제 에러 메시지를 붙여넣어 어떤 패턴이 매칭되는지 확인..."
                    rows="5"/>
          <button class="btn-primary" @click="runTest" :disabled="!testError.trim() || testing">
            <span v-if="testing" class="spin-sm"></span>
            <span v-else>매칭 테스트 실행</span>
          </button>
          <div v-if="testResult" class="test-result">
            <div v-if="testResult.matched" class="test-hit">
              <div class="th-label">✅ 매칭된 패턴:</div>
              <div class="th-id">{{ testResult.matched.id }}</div>
              <div class="th-meta">
                카테고리: {{ testResult.matched.category }} ·
                처리 방식: {{ testResult.matched.fix_type }}
                <span v-if="testResult.matched.ai_skip"> · AI 스킵</span>
              </div>
              <div class="th-cause">{{ testResult.matched.cause }}</div>
              <details v-if="testResult.prompt_hint_preview">
                <summary>AI 프롬프트에 들어갈 지침 ({{ testResult.hint_chars }}자)</summary>
                <pre class="th-prompt">{{ testResult.prompt_hint_preview }}</pre>
              </details>
            </div>
            <div v-else class="test-miss">
              ❌ 매칭된 패턴이 없습니다. 신규 패턴 후보로 기록됩니다.
            </div>
          </div>
        </div>

        <div class="panel-head" style="margin-top:24px">
          <h3>미매칭 에러 (신규 패턴 후보) <span class="count">({{ unmatched.length }})</span></h3>
        </div>
        <div class="unmatched-list">
          <div v-if="!unmatched.length" class="empty">
            미매칭 에러가 없습니다. 현재 KB 로 모든 에러가 대응되고 있습니다. 🎉
          </div>
          <div v-for="(u, i) in unmatched" :key="i" class="unmatched-card">
            <div class="uc-head">
              <span class="uc-item">{{ u.item_name || '(알수없음)' }}</span>
              <span class="uc-job">Job: {{ (u.job_id || '').slice(0, 8) }}</span>
              <span class="uc-ts">{{ fmtDate(u.ts) }}</span>
              <span class="uc-result" :class="u.success ? 'ok' : 'fail'">
                {{ u.success ? '✓ 성공' : '✗ 실패' }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
    </div><!-- /v-show error tab -->

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import kbApi from '@/api/kb.js'
import AdminKbConversion from './AdminKbConversion.vue'

defineOptions({ name: 'AdminKb' })

const tab = ref('error')  // 'error' | 'conversion'  (v10 #18)
const days = ref(30)
const stats = ref(null)
const patterns = ref([])
const unmatched = ref([])
const testError = ref('')
const testResult = ref(null)
const testing = ref(false)
const reloading = ref(false)
const filterCategory = ref('')
const filterFixType = ref('')

// 패턴별 통계 맵 (id → stats)
const patternStatsMap = computed(() => {
  const m = {}
  const list = stats.value?.by_pattern || []
  for (const s of list) m[s.pattern_id] = s
  return m
})

// 필터링된 패턴
const filteredPatterns = computed(() => {
  return patterns.value.filter(p => {
    if (filterCategory.value && p.category !== filterCategory.value) return false
    if (filterFixType.value && p.fix_type !== filterFixType.value) return false
    return true
  })
})

async function load() {
  try {
    const [pat, st, un] = await Promise.all([
      kbApi.listPatterns(),
      kbApi.getStats(days.value),
      kbApi.getUnmatched(days.value, 30),
    ])
    patterns.value  = pat.patterns || []
    stats.value     = st
    unmatched.value = un.samples || []
  } catch (e) {
    console.error('KB load 실패:', e)
  }
}

async function runTest() {
  if (!testError.value.trim()) return
  testing.value = true
  try {
    testResult.value = await kbApi.testMatch(testError.value)
  } catch (e) {
    testResult.value = { matched: null, error: e.message }
  } finally {
    testing.value = false
  }
}

async function reloadKb() {
  reloading.value = true
  try {
    const r = await kbApi.reload()
    if (r.ok) {
      alert(`YAML 재로드 완료 — ${r.patterns_loaded}개 패턴`)
      load()
    } else {
      alert('재로드 실패: ' + (r.error || ''))
    }
  } catch (e) {
    alert('재로드 오류: ' + e.message)
  } finally {
    reloading.value = false
  }
}

function fmtDate(iso) {
  if (!iso) return '-'
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('ko-KR') + ' ' + d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })
  } catch { return iso }
}

onMounted(load)
</script>

<style scoped>
/* ── 탭 바 (v10 #18) ───────────────────────────────────── */
.tab-bar {
  display: flex;
  gap: 4px;
  border-bottom: 2px solid var(--border-color, #e5e7eb);
  margin-bottom: 20px;
}
.tab-bar .tab {
  padding: 10px 20px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-muted, #6b7280);
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: color 0.15s, border-color 0.15s;
}
.tab-bar .tab:hover {
  color: var(--text-color, #111827);
}
.tab-bar .tab.active {
  color: #6366f1;
  border-bottom-color: #6366f1;
  font-weight: 600;
}
.kb-inner { display: flex; flex-direction: column; gap: 16px; }
/* 탭 바 (v10 #18) */
.tab-bar {
  display: flex;
  gap: 4px;
  border-bottom: 2px solid var(--border-color, #e5e7eb);
  margin-bottom: 16px;
  padding: 0 4px;
}
.tab {
  padding: 10px 18px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-muted, #6b7280);
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.15s;
}
.tab:hover { color: var(--text-color, #111827); }
.tab.active {
  color: #6366f1;
  border-bottom-color: #6366f1;
  font-weight: 600;
}

.kb-inner { display: flex; flex-direction: column; gap: 16px; }

.kb-page { padding: 20px; max-width: 1400px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-header h2 { margin: 0 0 4px; font-size: 1.3rem; }
.muted { color: var(--text-tertiary); font-size: .82rem; margin: 0; }
.days-sel, .filter-sel {
  padding: 6px 10px; border: 0.5px solid var(--border-mid); border-radius: 6px;
  background: var(--bg-primary); font-family: var(--font); font-size: .82rem;
}
.btn-ghost {
  padding: 6px 14px; border: 0.5px solid var(--border-mid); background: var(--bg-primary);
  border-radius: 6px; cursor: pointer; font-size: .82rem; color: var(--text-secondary);
  font-family: var(--font);
}
.btn-ghost:hover { background: var(--bg-secondary); }
.btn-ghost:disabled { opacity: .5; cursor: not-allowed; }
.btn-primary {
  padding: 8px 16px; border: none; background: #2563eb; color: #fff;
  border-radius: 6px; cursor: pointer; font-size: .85rem; font-weight: 500;
  font-family: var(--font);
}
.btn-primary:hover:not(:disabled) { background: #1d4ed8; }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }

.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
@media (max-width: 900px) { .stats-grid { grid-template-columns: repeat(2, 1fr); } }
.stat-card {
  background: var(--bg-secondary); border: 0.5px solid var(--border-light); border-radius: 10px;
  padding: 14px 16px;
}
.stat-card.ok    { border-left: 3px solid #22c55e; border-radius: 10px; }
.stat-card.ai    { border-left: 3px solid #3b82f6; border-radius: 10px; }
.stat-card.saved { border-left: 3px solid #a855f7; border-radius: 10px; }
.stat-label { font-size: .7rem; color: var(--text-tertiary); font-weight: 600;
              text-transform: uppercase; letter-spacing: .04em; margin-bottom: 6px; }
.stat-value { font-size: 1.6rem; font-weight: 700; color: var(--text-primary); line-height: 1; }
.stat-sub { font-size: .72rem; color: var(--text-tertiary); margin-top: 4px; }

.kb-body { display: grid; grid-template-columns: 1.3fr 1fr; gap: 16px; }
@media (max-width: 1000px) { .kb-body { grid-template-columns: 1fr; } }

.panel { background: var(--bg-primary); border: 0.5px solid var(--border-light);
         border-radius: 12px; padding: 16px; }
.panel-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px; }
.panel-head h3 { margin: 0; font-size: 1rem; }
.count { color: var(--text-tertiary); font-weight: 400; font-size: .88rem; }
.filter-bar { display: flex; gap: 6px; flex-wrap: wrap; }

.pattern-list { display: flex; flex-direction: column; gap: 8px; max-height: 70vh; overflow-y: auto; }
.pattern-card {
  background: var(--bg-secondary); border: 0.5px solid var(--border-light);
  border-left: 3px solid var(--border-mid);
  border-radius: 8px; padding: 10px 12px;
}
.pattern-card.fix-config_change   { border-left-color: #f59e0b; }
.pattern-card.fix-engine_rule     { border-left-color: #22c55e; }
.pattern-card.fix-prompt_injection { border-left-color: #3b82f6; }

.pc-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 5px; }
.pc-id { font-family: ui-monospace, monospace; font-size: .78rem; font-weight: 600; color: var(--text-primary); }
.pc-code { font-size: .66rem; background: var(--bg-primary); color: var(--text-tertiary);
           padding: 1px 5px; border-radius: 3px; border: 0.5px solid var(--border-light); }
.pc-cat { font-size: .66rem; padding: 1px 6px; border-radius: 3px; font-weight: 600; }
.cat-syntax     { background: #fef3c7; color: #92400e; }
.cat-permission { background: #fecaca; color: #991b1b; }
.cat-ddl        { background: #dbeafe; color: #1e40af; }
.cat-runtime    { background: #e0e7ff; color: #3730a3; }
.cat-type       { background: #ddd6fe; color: #5b21b6; }
.cat-semantic   { background: #fce7f3; color: #9f1239; }

.pc-badge { font-size: .66rem; padding: 1px 6px; border-radius: 3px; margin-left: auto; }
.pc-badge.ai-skip { background: #d1fae5; color: #065f46; }
.pc-badge.ai-use  { background: #dbeafe; color: #1e40af; }

.pc-cause { font-size: .78rem; color: var(--text-secondary); line-height: 1.4; margin: 4px 0; }
.pc-stats { display: flex; gap: 12px; font-size: .72rem; color: var(--text-tertiary); margin-top: 6px;
            padding-top: 6px; border-top: 0.5px solid var(--border-light); flex-wrap: wrap; }
.pc-stats b { color: var(--text-primary); }
.pc-stats .good b { color: #22c55e; }
.pc-stats .poor b { color: #ef4444; }
.pc-stats-empty { font-size: .7rem; color: var(--text-tertiary); font-style: italic;
                  margin-top: 6px; padding-top: 6px; border-top: 0.5px solid var(--border-light); }
.pc-last { margin-left: auto; font-size: .68rem; }

.test-box { display: flex; flex-direction: column; gap: 10px; }
.test-box textarea {
  padding: 10px; border: 0.5px solid var(--border-mid); border-radius: 6px;
  background: var(--bg-primary); color: var(--text-primary);
  font-family: ui-monospace, monospace; font-size: .78rem; resize: vertical;
}
.test-result { margin-top: 10px; padding: 12px; background: var(--bg-secondary); border-radius: 8px; }
.test-hit .th-label { font-size: .78rem; color: #22c55e; font-weight: 600; margin-bottom: 6px; }
.test-hit .th-id { font-family: ui-monospace, monospace; font-weight: 700; font-size: .88rem;
                   color: var(--text-primary); margin-bottom: 4px; }
.test-hit .th-meta { font-size: .72rem; color: var(--text-tertiary); margin-bottom: 6px; }
.test-hit .th-cause { font-size: .8rem; color: var(--text-secondary); line-height: 1.4; margin-bottom: 8px; }
.test-hit details { margin-top: 8px; }
.test-hit summary { cursor: pointer; font-size: .76rem; color: #2563eb; }
.test-hit .th-prompt { background: var(--bg-primary); padding: 10px; border-radius: 6px;
                       font-family: ui-monospace, monospace; font-size: .72rem;
                       white-space: pre-wrap; max-height: 400px; overflow-y: auto;
                       border: 0.5px solid var(--border-light); margin-top: 6px; }
.test-miss { color: #ef4444; font-size: .85rem; }

.unmatched-list { display: flex; flex-direction: column; gap: 6px; max-height: 40vh; overflow-y: auto; }
.unmatched-card { padding: 8px 10px; background: var(--bg-secondary); border-radius: 6px;
                  border: 0.5px solid var(--border-light); }
.uc-head { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; font-size: .74rem; }
.uc-item { font-family: ui-monospace, monospace; color: var(--text-primary); font-weight: 500; }
.uc-job { color: var(--text-tertiary); }
.uc-ts { color: var(--text-tertiary); margin-left: auto; }
.uc-result { padding: 1px 6px; border-radius: 3px; font-size: .68rem; font-weight: 600; }
.uc-result.ok { background: #d1fae5; color: #065f46; }
.uc-result.fail { background: #fee2e2; color: #991b1b; }

.empty { padding: 28px; text-align: center; color: var(--text-tertiary); font-size: .82rem; }

.spin-sm { width: 12px; height: 12px; border: 2px solid rgba(0,0,0,.1); border-top-color: currentColor;
           border-radius: 50%; animation: spin .6s linear infinite; display: inline-block; vertical-align: middle; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
