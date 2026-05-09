<template>
  <div class="landing">

    <!-- 메인 섹션 -->
    <div class="wrap">
      <div class="eyebrow">Any DB → Any DB Migration Platform</div>

      <!-- 로고 -->
      <div class="logo">
        <div class="logo-mark">
          <svg viewBox="0 0 20 20" fill="none">
            <rect x="1" y="1" width="7.5" height="7.5" rx="2" stroke="currentColor" stroke-width="1.2"/>
            <rect x="11.5" y="1" width="7.5" height="7.5" rx="2" stroke="currentColor" stroke-width="1.2" opacity=".4"/>
            <rect x="1" y="11.5" width="7.5" height="7.5" rx="2" stroke="currentColor" stroke-width="1.2" opacity=".4"/>
            <rect x="11.5" y="11.5" width="7.5" height="7.5" rx="2" stroke="currentColor" stroke-width="1.2"/>
          </svg>
        </div>
        <div class="logo-name">Data<b>Bridge</b> Studio</div>
      </div>
      <p class="slogan">어떤 데이터베이스든, 어디서든</p>

      <!-- DB 다이어그램 -->
      <div class="diagram">
        <div class="ring"></div>
        <div class="ring-inner"></div>

        <!-- 연결선 SVG -->
        <svg class="lines" viewBox="0 0 320 320" fill="none" ref="linesSvg">
          <!-- 중심 → 각 DB 실선 -->
          <line v-for="l in centerLines" :key="l.id"
            :x1="l.x1" :y1="l.y1" :x2="l.x2" :y2="l.y2"
            stroke="var(--border-light)" stroke-width="0.8"/>
          <!-- DB ↔ DB 점선 -->
          <line v-for="l in crossLines" :key="l.id"
            :x1="l.x1" :y1="l.y1" :x2="l.x2" :y2="l.y2"
            stroke="var(--border-light)" stroke-width="0.6"
            stroke-dasharray="3 5" opacity="0.4"/>
          <!-- 흐르는 점 -->
          <circle v-for="d in dots" :key="d.id"
            :cx="d.cx" :cy="d.cy" r="2.5"
            :fill="d.color" :opacity="d.opacity"/>
        </svg>

        <!-- 중앙 허브 -->
        <div class="center-hub">
          <svg viewBox="0 0 24 24" fill="none">
            <rect x="1" y="1" width="9" height="9" rx="2.2" stroke="currentColor" stroke-width="1.3"/>
            <rect x="14" y="1" width="9" height="9" rx="2.2" stroke="currentColor" stroke-width="1.3" opacity=".4"/>
            <rect x="1" y="14" width="9" height="9" rx="2.2" stroke="currentColor" stroke-width="1.3" opacity=".4"/>
            <rect x="14" y="14" width="9" height="9" rx="2.2" stroke="currentColor" stroke-width="1.3"/>
          </svg>
          <span class="hub-label">STUDIO</span>
        </div>

        <!-- DB 노드 -->
        <div v-for="db in dbs" :key="db.name"
          class="db-node"
          :style="`top:${db.y}px;left:${db.x}px`">
          <div class="db-icon">
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
              <rect x="4" y="6" width="20" height="16" rx="3" stroke="var(--text-tertiary)" stroke-width="1.2"/>
              <ellipse cx="14" cy="10" rx="10" ry="4" fill="none" :stroke="db.color" stroke-width="1.3"/>
              <line x1="4" y1="14" x2="24" y2="14" stroke="var(--text-tertiary)" stroke-width="1" opacity=".5"/>
              <ellipse cx="14" cy="18" rx="10" ry="2" fill="none" stroke="var(--text-tertiary)" stroke-width="0.8" opacity=".3"/>
            </svg>
          </div>
          <span class="db-label" :style="db.active ? `color:${db.color}` : ''">{{ db.name }}</span>
        </div>
      </div>

      <!-- CTA -->
      <div class="cta">
        <button class="btn" @click="$emit('start')">시작하기</button>
        <span class="hint">MSSQL · MySQL · MariaDB · PostgreSQL · Oracle · SQLite</span>
      </div>

      <!-- 푸터 -->
      <div class="footer">
        <span class="ft-l">DataBridge Studio v2.0</span>
        <div class="ft-r">
          <span>Vue 3</span>
          <span>FastAPI</span>
          <span>Claude AI</span>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

defineEmits(['start'])

// ── DB 정보 ─────────────────────────────────────────────────
// 원형 배치: 중심(160,160), 반지름 132, 12시부터 시계방향
const positions = [
  { x: 160, y: 28  },   // 0 - 12시
  { x: 279, y: 91  },   // 1 -  2시
  { x: 279, y: 229 },   // 2 -  4시
  { x: 160, y: 292 },   // 3 -  6시
  { x: 41,  y: 229 },   // 4 -  8시
  { x: 41,  y: 91  },   // 5 - 10시
]

const dbs = [
  { name: 'MSSQL',      color: '#6366f1', active: true,  ...positions[0] },
  { name: 'MySQL',      color: '#e37c27', active: true,  ...positions[1] },
  { name: 'MariaDB',    color: '#c0765a', active: false, ...positions[2] },
  { name: 'PostgreSQL', color: '#336791', active: false, ...positions[3] },
  { name: 'Oracle',     color: '#c74634', active: false, ...positions[4] },
  { name: 'SQLite',     color: '#4a90d9', active: false, ...positions[5] },
]

// ── 연결선 ──────────────────────────────────────────────────
const cx = 160, cy = 160

const centerLines = positions.map((p, i) => ({
  id: `cl${i}`, x1: cx, y1: cy, x2: p.x, y2: p.y,
}))

const crossPairs = [[0,3],[1,4],[2,5],[0,2],[1,5],[3,4]]
const crossLines = crossPairs.map(([a, b], i) => ({
  id: `xl${i}`,
  x1: positions[a].x, y1: positions[a].y,
  x2: positions[b].x, y2: positions[b].y,
}))

// ── 흐르는 점 ───────────────────────────────────────────────
const dots = ref([])
let rafId = null
let startTime = null

function lerp(a, b, t) { return a + (b - a) * t }
function easeInOut(t) {
  if (t < 0.1) return t / 0.1
  if (t > 0.9) return (1 - t) / 0.1
  return 1
}

function animateDots(ts) {
  if (!startTime) startTime = ts
  const elapsed = ts - startTime

  const newDots = []
  let id = 0

  positions.forEach((pos, i) => {
    const color = dbs[i].color
    const duration = 2200 + i * 180

    // 중심 → DB
    const t1 = ((elapsed + i * 400) % duration) / duration
    newDots.push({
      id: id++,
      cx: lerp(cx, pos.x, t1),
      cy: lerp(cy, pos.y, t1),
      color,
      opacity: easeInOut(t1) * 0.9,
    })

    // DB → 중심
    const t2 = ((elapsed + i * 400 + 1200) % duration) / duration
    newDots.push({
      id: id++,
      cx: lerp(pos.x, cx, t2),
      cy: lerp(pos.y, cy, t2),
      color,
      opacity: easeInOut(t2) * 0.9,
    })
  })

  dots.value = newDots
  rafId = requestAnimationFrame(animateDots)
}

onMounted(() => { rafId = requestAnimationFrame(animateDots) })
onUnmounted(() => { if (rafId) cancelAnimationFrame(rafId) })
</script>

<style scoped>
.landing {
  min-height: 100vh;
  background: var(--bg-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}
.wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 56px 32px 40px;
  border-bottom: 0.5px solid var(--border-light);
  max-width: 480px;
  width: 100%;
}

/* 텍스트 */
.eyebrow {
  font-size: 11px;
  letter-spacing: .14em;
  color: var(--text-tertiary);
  text-transform: uppercase;
  margin-bottom: 20px;
  animation: fadeUp .5s ease both;
}
.logo {
  display: flex;
  align-items: center;
  gap: 11px;
  margin-bottom: 10px;
  animation: fadeUp .5s .1s ease both;
}
.logo-mark {
  width: 40px; height: 40px;
  border-radius: 9px;
  border: 0.5px solid var(--border-mid);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-primary);
}
.logo-mark svg { width: 20px; height: 20px; }
.logo-name {
  font-size: 30px;
  font-weight: 500;
  color: var(--text-primary);
  letter-spacing: -.03em;
}
.logo-name b { font-weight: 500; color: var(--accent-blue); }
.slogan {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 44px;
  animation: fadeUp .5s .2s ease both;
}

/* 다이어그램 */
.diagram {
  position: relative;
  width: 320px; height: 320px;
  margin-bottom: 44px;
  animation: fadeUp .6s .3s ease both;
}
.ring {
  position: absolute; inset: 0;
  border-radius: 50%;
  border: 0.5px dashed var(--border-light);
}
.ring-inner {
  position: absolute; inset: 60px;
  border-radius: 50%;
  border: 0.5px dashed var(--border-light);
  opacity: .5;
}
svg.lines {
  position: absolute; inset: 0;
  width: 100%; height: 100%;
  overflow: visible;
}

/* 중앙 허브 */
.center-hub {
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  width: 64px; height: 64px;
  border-radius: 16px;
  background: var(--bg-primary);
  border: 0.5px solid var(--border-mid);
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 3px;
  z-index: 2;
  color: var(--text-primary);
}
.center-hub svg { width: 24px; height: 24px; }
.hub-label {
  font-size: 9px;
  color: var(--text-tertiary);
  letter-spacing: .08em;
}

/* DB 노드 */
.db-node {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  transform: translate(-50%, -50%);
}
.db-icon {
  width: 52px; height: 52px;
  border-radius: 14px;
  border: 0.5px solid var(--border-mid);
  background: var(--bg-primary);
  display: flex; align-items: center; justify-content: center;
  transition: transform .2s, border-color .2s;
}
.db-icon:hover {
  transform: scale(1.1);
  border-color: var(--border-strong);
}
.db-label {
  font-size: 10px;
  color: var(--text-secondary);
  letter-spacing: .04em;
  font-weight: 500;
  white-space: nowrap;
  transition: color .2s;
}

/* CTA */
.cta {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 9px;
  animation: fadeUp .5s .5s ease both;
}
.btn {
  background: var(--text-primary);
  color: var(--bg-primary);
  border: none;
  padding: 11px 38px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity .15s;
  font-family: var(--font);
}
.btn:hover { opacity: .8; }
.hint {
  font-size: 11px;
  color: var(--text-tertiary);
}

/* 푸터 */
.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  margin-top: 32px;
  animation: fadeUp .5s .6s ease both;
}
.ft-l { font-size: 11px; color: var(--text-tertiary); }
.ft-r { display: flex; gap: 12px; }
.ft-r span { font-size: 11px; color: var(--border-strong); }

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
</style>
