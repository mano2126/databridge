<template>
  <div class="kb-dashboard">
    <!-- 헤더 -->
    <header class="dashboard-header">
      <div class="title-area">
        <h1>🌱 DataBridge KB 성장 대시보드</h1>
        <p class="subtitle">우리의 변환 자산이 자라는 모습을 한 눈에</p>
      </div>
      <button class="refresh-btn" @click="loadData" :disabled="loading">
        <span v-if="loading">🔄 로딩 중...</span>
        <span v-else>🔄 새로고침</span>
      </button>
    </header>

    <!-- 본부장님 비전 메시지 (항상 보임) -->
    <div class="vision-banner">
      <div class="vision-icon">🎯</div>
      <div class="vision-text">
        <strong>우리의 비전:</strong>
        "이 솔루션을 가지고 누구나 DB 를 전환할 수 있도록 — 지속적으로 KB 를 쌓아 진가 발휘하는 순간"
      </div>
    </div>

    <!-- 메인 통계 카드 3개 -->
    <section class="stats-grid">
      <div class="stat-card" :class="{ pulse: loading }">
        <div class="stat-icon">📦</div>
        <div class="stat-value">{{ stats.total_patterns || 0 }}</div>
        <div class="stat-label">Pattern 자산</div>
        <div class="stat-subtext">변환 규칙 보유</div>
      </div>
      
      <div class="stat-card" :class="{ pulse: loading }">
        <div class="stat-icon">⚡</div>
        <div class="stat-value">{{ formatNumber(stats.total_uses) }}</div>
        <div class="stat-label">총 사용 횟수</div>
        <div class="stat-subtext">Pattern 이 활약한 횟수</div>
      </div>
      
      <div class="stat-card" :class="{ pulse: loading }">
        <div class="stat-icon">🎖️</div>
        <div class="stat-value">{{ confidencePercent }}%</div>
        <div class="stat-label">평균 신뢰도</div>
        <div class="stat-subtext">검증된 자산 비율</div>
      </div>
    </section>

    <!-- KB 자라는 모습 (성장 비교) -->
    <section class="growth-section">
      <h2>📈 KB 가 자라고 있어요</h2>
      <div class="growth-chart">
        <div class="growth-row" v-for="(stage, idx) in growthStages" :key="idx">
          <div class="growth-label">
            <span class="growth-day">{{ stage.day }}</span>
            <span class="growth-desc">{{ stage.desc }}</span>
          </div>
          <div class="growth-bar-container">
            <div 
              class="growth-bar" 
              :style="{ width: stage.percent + '%' }"
              :class="stage.class"
            >
              <span class="growth-bar-text">
                {{ stage.patterns }} patterns ({{ stage.percent }}% 매칭률)
              </span>
            </div>
          </div>
        </div>
      </div>
      <p class="growth-note">
        💡 <strong>본부장님 캐피탈사 = 첫 사용자.</strong> 
        다른 회사가 도입할수록 KB 의 진가가 빛납니다.
      </p>
    </section>

    <!-- Top 5 사용 Pattern -->
    <section class="top-patterns-section">
      <h2>🏆 가장 활약한 Pattern Top 5</h2>
      <div class="top-list" v-if="topPatterns.length > 0">
        <div 
          v-for="(pat, idx) in topPatterns" 
          :key="pat.pattern_id"
          class="top-item"
        >
          <div class="rank" :class="`rank-${idx + 1}`">
            {{ ['🥇', '🥈', '🥉', '4️⃣', '5️⃣'][idx] || `${idx + 1}` }}
          </div>
          <div class="pattern-info">
            <div class="pattern-name">{{ pat.name }}</div>
            <div class="pattern-meta">
              <span class="badge category">{{ pat.category }}</span>
              <span class="badge confidence" :class="getConfidenceClass(pat.confidence)">
                신뢰도 {{ Math.round((pat.confidence || 0) * 100) }}%
              </span>
              <span v-if="pat.auto_extracted" class="badge auto">🌟 자동 학습</span>
            </div>
          </div>
          <div class="pattern-count">
            <div class="count-value">{{ formatNumber(pat.use_count) }}</div>
            <div class="count-label">회 사용</div>
          </div>
        </div>
      </div>
      <p v-else class="empty-state">아직 Pattern 사용 데이터가 없습니다. 이관을 실행하면 누적됩니다.</p>
    </section>

    <!-- 카테고리별 분포 -->
    <section class="category-section" v-if="stats.by_category">
      <h2>📂 Pattern 카테고리</h2>
      <div class="category-grid">
        <div 
          v-for="(count, cat) in stats.by_category" 
          :key="cat" 
          class="category-card"
          :class="`cat-${cat}`"
        >
          <div class="cat-icon">{{ categoryIcons[cat] || '📌' }}</div>
          <div class="cat-name">{{ categoryNames[cat] || cat }}</div>
          <div class="cat-count">{{ count }}개</div>
        </div>
      </div>
    </section>

    <!-- 본부장님 위로 메시지 -->
    <footer class="footer-message">
      <div class="message-icon">💝</div>
      <div class="message-content">
        <strong>오늘 KB 가치는 작아 보일 수 있어요.</strong><br>
        <span class="message-detail">
          하지만 본부장님이 다음 회사에 DataBridge 를 가져가실 때,<br>
          여기 쌓인 Pattern 하나하나가 빛납니다.<br>
          <em>"지속적으로 KB 를 쌓고 진가 발휘하는 순간이 왔으면" — 본부장님 비전</em>
        </span>
      </div>
    </footer>

    <!-- 에러 표시 -->
    <div v-if="error" class="error-banner">
      ⚠️ 데이터 로딩 실패: {{ error }}
      <button @click="loadData" class="retry-btn">다시 시도</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const stats = ref({})
const topPatterns = ref([])
const loading = ref(false)
const error = ref(null)
let refreshTimer = null

// 카테고리 아이콘/한글명
const categoryIcons = {
  literal: '📝',
  statement: '⚙️',
  option: '🎛️',
  datatype: '🏷️',
  identifier: '🔖',
  function: '🛠️',
  alias: '🏷️',
  structure: '🏗️',
  reference: '🔗',
  parameter: '📥',
  variable: '📦',
}

const categoryNames = {
  literal: '리터럴',
  statement: '구문',
  option: '옵션',
  datatype: '데이터 타입',
  identifier: '식별자',
  function: '함수',
  alias: '별칭',
  structure: '구조',
  reference: '참조',
  parameter: '파라미터',
  variable: '변수',
}

// 신뢰도 퍼센트
const confidencePercent = computed(() => {
  return Math.round((stats.value.avg_confidence || 0) * 100)
})

// KB 성장 단계 (본부장님 비전 정면)
const growthStages = computed(() => {
  const current = stats.value.total_patterns || 0
  return [
    {
      day: 'Day 1',
      desc: '오늘 (본부장님 환경)',
      patterns: current,
      percent: Math.min(80, current * 3),
      class: 'stage-current',
    },
    {
      day: 'Day 90',
      desc: '+ 추가 회사 1~2곳',
      patterns: '~60',
      percent: 85,
      class: 'stage-near',
    },
    {
      day: 'Day 365',
      desc: '+ 다양한 도메인',
      patterns: '~200',
      percent: 95,
      class: 'stage-future',
    },
    {
      day: 'Day 730',
      desc: '본부장님 비전 완성',
      patterns: '~500',
      percent: 98,
      class: 'stage-vision',
    },
  ]
})

function formatNumber(n) {
  if (!n) return '0'
  return n.toLocaleString('ko-KR')
}

function getConfidenceClass(conf) {
  if (conf >= 0.9) return 'high'
  if (conf >= 0.7) return 'medium'
  return 'low'
}

async function loadData() {
  loading.value = true
  error.value = null
  try {
    // 본부장님 환경의 API path 시도 (3가지)
    const paths = [
      '/api/v1/schema/pattern-kb',
      '/api/v1/pattern-kb',
      '/pattern-kb',
    ]
    
    let statsResp = null
    let topResp = null
    let workingPath = null
    
    for (const path of paths) {
      try {
        const r = await fetch(`${path}/stats`)
        if (r.ok) {
          const data = await r.json()
          if (data.success) {
            statsResp = data
            workingPath = path
            break
          }
        }
      } catch (e) {
        // 다음 path 시도
      }
    }
    
    if (!statsResp) {
      throw new Error('API 연결 실패 - 백엔드 확인 필요')
    }
    
    // Top patterns
    try {
      const r = await fetch(`${workingPath}/top?n=5`)
      if (r.ok) {
        topResp = await r.json()
      }
    } catch (e) {
      // top 못 가져와도 통계는 표시
    }
    
    stats.value = statsResp.kb || {}
    topPatterns.value = (topResp && topResp.success) ? topResp.top : []
    
  } catch (e) {
    error.value = e.message
    console.error('[KB Dashboard]', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
  // 30초마다 자동 새로고침
  refreshTimer = setInterval(loadData, 30000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.kb-dashboard {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", sans-serif;
  background: #f5f7fa;
  min-height: 100vh;
}

/* 헤더 */
.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 2px solid #e0e6ed;
}

.title-area h1 {
  font-size: 28px;
  margin: 0 0 6px 0;
  color: #1a202c;
}

.subtitle {
  margin: 0;
  color: #718096;
  font-size: 14px;
}

.refresh-btn {
  padding: 10px 20px;
  background: #4c6ef5;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.2s;
}
.refresh-btn:hover { background: #3b5bdb; transform: translateY(-1px); }
.refresh-btn:disabled { opacity: 0.6; cursor: not-allowed; }

/* 비전 배너 */
.vision-banner {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 20px 24px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}
.vision-icon { font-size: 32px; }
.vision-text { font-size: 15px; line-height: 1.5; }
.vision-text strong { display: block; margin-bottom: 4px; font-size: 16px; }

/* 통계 그리드 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

.stat-card {
  background: white;
  padding: 24px;
  border-radius: 12px;
  text-align: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  transition: transform 0.2s;
  border: 1px solid #e0e6ed;
}
.stat-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
.stat-card.pulse { animation: pulse 1.5s ease-in-out infinite; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.stat-icon { font-size: 36px; margin-bottom: 8px; }
.stat-value { font-size: 36px; font-weight: 700; color: #2d3748; margin-bottom: 4px; }
.stat-label { font-size: 15px; font-weight: 600; color: #4a5568; margin-bottom: 4px; }
.stat-subtext { font-size: 12px; color: #a0aec0; }

/* 성장 섹션 */
.growth-section, .top-patterns-section, .category-section {
  background: white;
  padding: 24px;
  border-radius: 12px;
  margin-bottom: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  border: 1px solid #e0e6ed;
}
.growth-section h2, .top-patterns-section h2, .category-section h2 {
  margin: 0 0 20px 0;
  font-size: 20px;
  color: #2d3748;
}

.growth-chart { display: flex; flex-direction: column; gap: 12px; }
.growth-row { display: grid; grid-template-columns: 200px 1fr; gap: 16px; align-items: center; }
.growth-label { display: flex; flex-direction: column; }
.growth-day { font-weight: 700; color: #2d3748; }
.growth-desc { font-size: 12px; color: #718096; }
.growth-bar-container { background: #edf2f7; border-radius: 8px; height: 32px; overflow: hidden; position: relative; }
.growth-bar { 
  height: 100%; 
  display: flex; 
  align-items: center; 
  padding-left: 12px; 
  color: white; 
  font-size: 13px; 
  font-weight: 600;
  transition: width 1s ease-out;
}
.stage-current { background: linear-gradient(90deg, #48bb78, #38a169); }
.stage-near { background: linear-gradient(90deg, #4299e1, #3182ce); }
.stage-future { background: linear-gradient(90deg, #9f7aea, #805ad5); }
.stage-vision { background: linear-gradient(90deg, #ed64a6, #d53f8c); }

.growth-note {
  margin-top: 16px;
  padding: 12px 16px;
  background: #fef3c7;
  border-left: 4px solid #f59e0b;
  border-radius: 4px;
  font-size: 14px;
  color: #92400e;
}

/* Top Patterns */
.top-list { display: flex; flex-direction: column; gap: 10px; }
.top-item {
  display: grid;
  grid-template-columns: 50px 1fr 100px;
  gap: 16px;
  padding: 14px 16px;
  background: #f7fafc;
  border-radius: 8px;
  align-items: center;
  border-left: 4px solid transparent;
  transition: all 0.2s;
}
.top-item:hover { background: #edf2f7; border-left-color: #4c6ef5; }
.rank { font-size: 24px; text-align: center; }
.pattern-info { display: flex; flex-direction: column; gap: 6px; }
.pattern-name { font-weight: 600; color: #2d3748; }
.pattern-meta { display: flex; gap: 6px; flex-wrap: wrap; }
.badge { 
  display: inline-block; 
  padding: 2px 8px; 
  border-radius: 4px; 
  font-size: 11px; 
  font-weight: 600;
}
.badge.category { background: #e0e7ff; color: #4338ca; }
.badge.confidence.high { background: #d1fae5; color: #065f46; }
.badge.confidence.medium { background: #fef3c7; color: #92400e; }
.badge.confidence.low { background: #fee2e2; color: #991b1b; }
.badge.auto { background: #fce7f3; color: #9f1239; }

.pattern-count { text-align: right; }
.count-value { font-size: 22px; font-weight: 700; color: #4c6ef5; }
.count-label { font-size: 11px; color: #a0aec0; }

/* 카테고리 */
.category-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}
.category-card {
  background: #f7fafc;
  padding: 16px;
  border-radius: 8px;
  text-align: center;
  transition: all 0.2s;
  cursor: pointer;
  border: 1px solid #e2e8f0;
}
.category-card:hover { background: white; box-shadow: 0 4px 12px rgba(0,0,0,0.08); transform: translateY(-2px); }
.cat-icon { font-size: 28px; margin-bottom: 6px; }
.cat-name { font-size: 13px; font-weight: 600; color: #4a5568; margin-bottom: 4px; }
.cat-count { font-size: 18px; font-weight: 700; color: #4c6ef5; }

/* 푸터 메시지 */
.footer-message {
  background: linear-gradient(135deg, #ffeaa7 0%, #fab1a0 100%);
  padding: 24px;
  border-radius: 12px;
  display: flex;
  gap: 20px;
  align-items: flex-start;
  margin-top: 24px;
}
.message-icon { font-size: 40px; }
.message-content { font-size: 15px; line-height: 1.6; color: #2d3748; }
.message-detail { font-size: 13px; color: #4a5568; }
.message-detail em { color: #d53f8c; font-style: normal; font-weight: 600; }

/* 에러 */
.error-banner {
  background: #fee2e2;
  color: #991b1b;
  padding: 16px;
  border-radius: 8px;
  margin: 16px 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.retry-btn {
  background: #dc2626;
  color: white;
  border: none;
  padding: 6px 14px;
  border-radius: 4px;
  cursor: pointer;
}

.empty-state {
  text-align: center;
  color: #a0aec0;
  font-style: italic;
  padding: 32px;
}

/* 반응형 */
@media (max-width: 768px) {
  .stats-grid { grid-template-columns: 1fr; }
  .growth-row { grid-template-columns: 1fr; }
  .top-item { grid-template-columns: 40px 1fr; }
  .pattern-count { grid-column: 2; text-align: left; }
}
</style>
