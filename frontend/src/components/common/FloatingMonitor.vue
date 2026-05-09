<!--
  FloatingMonitor.vue — 실시간 리소스 모니터 플로팅 팝업 (v10 #22)

  요구사항 반영:
    ✅ 드래그로 어디든 이동
    ✅ 펼침/최소화 토글 — 최소화 시 1줄 요약
    ✅ 페이지 이동해도 유지 (App.vue 루트에 배치)
    ✅ 실시간이지만 메모리 최소 — SVG 스파크라인(DOM 3줄), ring buffer
    ✅ 기존 DataBridge 테마/CSS 변수 100% 재사용
    ✅ 다크모드 자동 적용
-->
<template>
  <Teleport to="body">
    <div
      v-if="store.visible"
      class="fm-root"
      :class="{ 'fm-min': store.minimized, 'fm-dragging': dragging }"
      :style="rootStyle"
      role="dialog"
      aria-label="실시간 리소스 모니터"
    >
      <!-- ── 헤더 (드래그 핸들) ─────────────────────── -->
      <div class="fm-header" @pointerdown="startDrag">
        <span class="fm-dot" :class="alertDotClass" />
        <span class="fm-title">
          <template v-if="!store.minimized">실시간 모니터</template>
          <template v-else>{{ minimizedSummary }}</template>
        </span>
        <div class="fm-actions" @pointerdown.stop>
          <!-- v10 Phase A-3.5: 범례 버튼 -->
          <button class="fm-btn" :class="{ 'is-active': showLegend }"
                  title="표시 기준 설명 보기" @click="showLegend = !showLegend">
            <svg viewBox="0 0 12 12" width="10" height="10">
              <circle cx="6" cy="6" r="5" fill="none" stroke="currentColor" stroke-width="1.3"/>
              <text x="6" y="9" text-anchor="middle" font-size="8" fill="currentColor" font-weight="700">?</text>
            </svg>
          </button>
          <button class="fm-btn" :title="store.minimized ? '펼치기' : '접기'"
                  @click="store.toggleMinimize()">
            <svg v-if="store.minimized" viewBox="0 0 12 12" width="10" height="10">
              <polyline points="2,4 6,8 10,4" fill="none" stroke="currentColor" stroke-width="1.6"/>
            </svg>
            <svg v-else viewBox="0 0 12 12" width="10" height="10">
              <line x1="2" y1="6" x2="10" y2="6" stroke="currentColor" stroke-width="1.6"/>
            </svg>
          </button>
          <button class="fm-btn" title="닫기" @click="store.hide()">
            <svg viewBox="0 0 12 12" width="10" height="10">
              <line x1="2.5" y1="2.5" x2="9.5" y2="9.5" stroke="currentColor" stroke-width="1.6"/>
              <line x1="9.5" y1="2.5" x2="2.5" y2="9.5" stroke="currentColor" stroke-width="1.6"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- ── 본문 (펼친 상태에만) ───────────────────── -->
      <div v-if="!store.minimized" class="fm-body">
        <!-- v10 Phase A-3.5: 범례 패널 -->
        <div v-if="showLegend" class="fm-legend">
          <h4 class="fm-legend-title">📊 표시 기준 설명</h4>
          <div class="fm-legend-section">
            <strong>🖥 로컬 이 PC — 호스트 전체 리소스</strong>
            <ul>
              <li><b>메모리</b>: PC 전체 RAM 사용률</li>
              <li><b>CPU</b>: 모든 코어 평균 사용률</li>
              <li><b>디스크</b>: DataBridge 설치 드라이브</li>
            </ul>
          </div>
          <div class="fm-legend-section">
            <strong>🐳 Docker — 컨테이너별 리소스</strong>
            <ul>
              <li><b>메모리</b>: 컨테이너 할당량 중 사용률</li>
              <li><b>CPU</b>: 컨테이너 CPU 사용률</li>
              <li><b>● 아이콘</b>: 녹=healthy / 빨강=unhealthy / 노랑=starting</li>
            </ul>
          </div>
          <div class="fm-legend-section">
            <strong>🎨 색상 기준</strong>
            <div class="fm-legend-colors">
              <span class="fm-lc fm-lc-ok">🟢 안전</span>
              <span class="fm-lc fm-lc-warn">🟡 주의</span>
              <span class="fm-lc fm-lc-crit">🔴 위험</span>
            </div>
            <p class="fm-legend-note">
              각 지표마다 임계값 상이.
              <br>메모리·디스크: 85% 주의 / 95% 위험
              <br>CPU: 80% 주의 / 95% 위험
              <br><em>각 수치에 마우스 올리면 상세 설명.</em>
            </p>
          </div>
        </div>

        <!-- 에러 표시 -->
        <div v-if="store.error" class="fm-error">
          <strong>연결 오류:</strong> {{ store.error }}
        </div>

        <!-- 활성 Job 요약 (항상 최상단) -->
        <section v-if="activeJobs.length" class="fm-section fm-jobs">
          <h4 class="fm-section-title">
            <span class="fm-running-dot"></span>
            진행 중 이관 · {{ activeJobs.length }}건
          </h4>
          <div v-for="job in activeJobs" :key="job.id" class="fm-job-row">
            <div class="fm-job-top">
              <span class="fm-job-name" :title="job.name">{{ job.name || '(unnamed)' }}</span>
              <!-- v90.42: 활성 영역(테이블/객체) 중 큰 % 표시 -->
              <span class="fm-job-pct">{{ getOverallPct(job) }}%</span>
            </div>
            <!-- v90.42: 테이블 진행 막대 (있을 때만) -->
            <div v-if="(job.table_total||0) > 0" class="fm-bar fm-bar-tbl"
                 :title="`테이블 ${job.table_done||0}/${job.table_total||0}`">
              <div class="fm-bar-fill" :style="{ width: `${Math.min(100, job.progress || 0)}%` }"></div>
            </div>
            <!-- v90.42: 객체 진행 막대 (있을 때만) -->
            <div v-if="(job.obj_total||0) > 0" class="fm-bar fm-bar-obj"
                 :title="`객체 ${job.obj_done||0}/${job.obj_total||0}`">
              <div class="fm-bar-fill fm-obj-fill" :style="{ width: `${Math.min(100, job.obj_progress || 0)}%` }"></div>
            </div>
            <div class="fm-job-meta">
              <span v-if="(job.table_total||0) > 0">
                📊 테이블 {{ job.table_done||0 }}/{{ job.table_total||0 }}
              </span>
              <span v-if="(job.obj_total||0) > 0">
                <span v-if="(job.table_total||0) > 0"> · </span>
                ⚙ 객체 {{ job.obj_done||0 }}/{{ job.obj_total||0 }}
                <span v-if="(job.obj_running||0) > 0">⟳{{ job.obj_running }}</span>
                <span v-if="(job.obj_failed||0) > 0" class="fm-fail">✗{{ job.obj_failed }}</span>
              </span>
              <span v-if="(job.rows_total||0) > 0">
                · {{ fmtNum(job.rows_processed) }}/{{ fmtNum(job.rows_total) }} rows
              </span>
            </div>
            
            <!-- v90.14: 미니 Throttle 컨트롤 (Adaptive Resource) -->
            <div class="fm-throttle-mini">
              <div class="fm-throttle-row">
                <span class="fm-throttle-label">⚡ Throttle</span>
                <button v-for="pct in [100, 75, 50, 25]" :key="pct"
                        class="fm-throttle-btn"
                        :class="{ active: getJobThrottle(job.id) === pct }"
                        @click="setJobThrottle(job.id, pct)"
                        :title="`${pct}% 속도로 조정`">
                  {{ pct }}%
                </button>
              </div>
              <div class="fm-throttle-row">
                <span class="fm-throttle-label">🎚 모드</span>
                <button v-for="mode in [
                  {v:'auto', l:'AI'},
                  {v:'hybrid', l:'하이브리드'},
                  {v:'manual', l:'수동'}
                ]" :key="mode.v"
                  class="fm-mode-btn"
                  :class="{ active: getJobMode(job.id) === mode.v }"
                  @click="setJobMode(job.id, mode.v)"
                  :title="`${mode.l} 모드`">
                  {{ mode.l }}
                </button>
              </div>
              <!-- AI 의사결정 (가장 최근 1개) -->
              <div v-if="jobLastDecision[job.id]" class="fm-ai-decision">
                🤖 {{ jobLastDecision[job.id] }}
              </div>
              <!-- v95_p44 (2026-05-05 본부장님): Throttle + Mode 동시 표시 (덮어쓰기 X) -->
              <!-- Throttle 변경 카드 (있을 때만) -->
              <div v-if="jobLastChange[job.id] && jobLastChange[job.id].throttle"
                   class="fm-change-detail">
                <div class="fm-change-rows">
                  <div class="fm-change-row">
                    <span class="fm-change-label">⚙️ Thread</span>
                    <span class="fm-change-arrow">
                      <span class="fm-change-from">{{ jobLastChange[job.id].throttle.before.parallelism }}개</span>
                      <span class="fm-change-mid">→</span>
                      <span class="fm-change-to" :class="threadDeltaClass(jobLastChange[job.id].throttle)">
                        {{ jobLastChange[job.id].throttle.after.parallelism }}개
                      </span>
                    </span>
                  </div>
                  <div class="fm-change-row">
                    <span class="fm-change-label">📦 Batch</span>
                    <span class="fm-change-arrow">
                      <span class="fm-change-from">{{ jobLastChange[job.id].throttle.before.batch_size.toLocaleString() }}</span>
                      <span class="fm-change-mid">→</span>
                      <span class="fm-change-to" :class="batchDeltaClass(jobLastChange[job.id].throttle)">
                        {{ jobLastChange[job.id].throttle.after.batch_size.toLocaleString() }} 행
                      </span>
                    </span>
                  </div>
                  <div class="fm-change-hint">
                    {{ throttleHint(jobLastChange[job.id].throttle) }}
                  </div>
                </div>
              </div>
              <!-- Mode 변경 카드 (있을 때만) — Throttle 카드와 독립 -->
              <div v-if="jobLastChange[job.id] && jobLastChange[job.id].mode"
                   class="fm-change-detail fm-change-mode-card">
                <div class="fm-change-rows">
                  <div class="fm-change-row">
                    <span class="fm-change-label">🎚 모드</span>
                    <span class="fm-change-arrow">
                      <span class="fm-change-from">{{ jobLastChange[job.id].mode.before.mode }}</span>
                      <span class="fm-change-mid">→</span>
                      <span class="fm-change-to">{{ jobLastChange[job.id].mode.after.mode }}</span>
                    </span>
                  </div>
                  <div class="fm-change-hint">
                    {{ modeHint(jobLastChange[job.id].mode.after.mode) }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- 스크롤 영역 (타겟 목록) -->
        <div class="fm-scroll">
          <!-- 타겟 없음 -->
          <div v-if="!targets.length" class="fm-empty">
            <p>모니터 대상이 없습니다.</p>
            <p class="fm-empty-hint">백엔드 API에서 자동 감지 중...</p>
          </div>

          <!-- 각 타겟 카드 -->
          <section v-for="t in targets" :key="t.target_id" class="fm-section">
            <h4 class="fm-section-title">
              <span class="fm-type-pill" :class="`t-${t.target_type}`">
                {{ typeLabel(t.target_type) }}
              </span>
              <span class="fm-target-name" :title="t.target_display">{{ t.target_display }}</span>
            </h4>

            <!-- 에러 있으면 이유 표시 -->
            <div v-if="hasErrors(t)" class="fm-target-error">
              ⚠ {{ Object.values(t.errors)[0] }}
            </div>

            <!-- System 지표 -->
            <template v-if="t.system">
              <div class="fm-metric"
                   :title="`호스트 PC 전체 메모리 사용률
${systemMemTooltip(t.system)}

🟢 <85% 정상
🟡 85-95% 주의
🔴 >95% 위험 (OOM 가능)`">
                <label>메모리</label>
                <div class="fm-bar">
                  <div class="fm-bar-fill" :class="levelClass(t.system.mem_pct, 85, 95)"
                       :style="{ width: `${t.system.mem_pct}%` }"></div>
                </div>
                <span class="fm-metric-val" :class="levelTextClass(t.system.mem_pct, 85, 95)">
                  {{ t.system.mem_pct?.toFixed(0) }}%
                </span>
              </div>
              <div class="fm-metric"
                   :title="`호스트 PC 전체 CPU 사용률 (모든 코어 평균)

🟢 <80% 정상
🟡 80-95% 주의 (이관 속도 저하)
🔴 >95% 과부하`">
                <label>CPU</label>
                <div class="fm-bar">
                  <div class="fm-bar-fill" :class="levelClass(t.system.cpu_pct, 80, 95)"
                       :style="{ width: `${t.system.cpu_pct}%` }"></div>
                </div>
                <span class="fm-metric-val" :class="levelTextClass(t.system.cpu_pct, 80, 95)">
                  {{ t.system.cpu_pct?.toFixed(0) }}%
                </span>
              </div>
              <div v-if="t.system.disk_used_pct != null" class="fm-metric"
                   :title="`호스트 PC 디스크 사용률 (DataBridge 설치 드라이브)

🟢 <85% 정상
🟡 85-95% 주의 (로그/캐시 공간 부족 우려)
🔴 >95% 위험`">
                <label>디스크</label>
                <div class="fm-bar">
                  <div class="fm-bar-fill" :class="levelClass(t.system.disk_used_pct, 85, 95)"
                       :style="{ width: `${t.system.disk_used_pct}%` }"></div>
                </div>
                <span class="fm-metric-val" :class="levelTextClass(t.system.disk_used_pct, 85, 95)">
                  {{ t.system.disk_used_pct?.toFixed(0) }}%
                </span>
              </div>
            </template>

            <!-- Docker 컨테이너 -->
            <template v-if="t.docker">
              <div v-for="c in t.docker.containers || []" :key="c.name" class="fm-container">
                <div class="fm-container-head">
                  <span class="fm-health" :class="`h-${c.health || 'none'}`"
                        :title="`상태: ${healthLabel(c.health)}`"></span>
                  <span class="fm-container-name" :title="c.name">{{ c.name }}</span>
                </div>
                <!-- v10 Phase A-3.5: 메모리와 CPU 라벨 명확히 분리 + 툴팁 -->
                <div class="fm-container-metric"
                     :title="memTooltip(c)">
                  <span class="fm-metric-tiny-label">메모리</span>
                  <div class="fm-bar fm-bar-sm">
                    <div class="fm-bar-fill" :class="levelClass(c.mem_pct, 80, 95)"
                         :style="{ width: `${c.mem_pct}%` }"></div>
                  </div>
                  <span class="fm-metric-tiny-val" :class="levelTextClass(c.mem_pct, 80, 95)">
                    {{ c.mem_pct?.toFixed(0) }}%
                  </span>
                </div>
                <div v-if="c.cpu_pct != null" class="fm-container-metric"
                     :title="`컨테이너 CPU 사용률: ${c.cpu_pct.toFixed(1)}%`">
                  <span class="fm-metric-tiny-label">CPU</span>
                  <div class="fm-bar fm-bar-sm">
                    <div class="fm-bar-fill" :class="levelClass(c.cpu_pct, 70, 90)"
                         :style="{ width: `${c.cpu_pct}%` }"></div>
                  </div>
                  <span class="fm-metric-tiny-val" :class="levelTextClass(c.cpu_pct, 70, 90)">
                    {{ c.cpu_pct?.toFixed(0) }}%
                  </span>
                </div>
              </div>
            </template>

            <!-- DB Native (Migration-Aware!) -->
            <template v-if="t.db">
              <div v-if="t.db.buffer_cache_hit_ratio != null" class="fm-kv">
                <span class="fm-kv-k">버퍼 캐시</span>
                <span class="fm-kv-v" :class="bcrClass(t.db.buffer_cache_hit_ratio)">
                  {{ t.db.buffer_cache_hit_ratio.toFixed(1) }}%
                </span>
              </div>
              <div v-if="t.db.page_life_expectancy != null" class="fm-kv">
                <span class="fm-kv-k">Page Life</span>
                <span class="fm-kv-v" :class="pleClass(t.db.page_life_expectancy)">
                  {{ t.db.page_life_expectancy.toFixed(0) }}초
                </span>
              </div>
              <div v-if="t.db.buffer_pool_used_pct != null" class="fm-kv">
                <span class="fm-kv-k">Buffer Pool</span>
                <span class="fm-kv-v">{{ t.db.buffer_pool_used_pct.toFixed(0) }}%</span>
              </div>
              <div v-if="t.db.active_sessions != null" class="fm-kv">
                <span class="fm-kv-k">활성 세션</span>
                <span class="fm-kv-v">{{ t.db.active_sessions }}</span>
              </div>
              <div v-if="t.db.blocked_sessions" class="fm-kv">
                <span class="fm-kv-k">블로킹</span>
                <span class="fm-kv-v fm-warn">{{ t.db.blocked_sessions }}</span>
              </div>
              <div v-if="t.db.tempdb_free_mb != null" class="fm-kv">
                <span class="fm-kv-k">tempdb 여유</span>
                <span class="fm-kv-v" :class="t.db.tempdb_free_mb < 500 ? 'fm-crit' : ''">
                  {{ fmtNum(t.db.tempdb_free_mb) }} MB
                </span>
              </div>
            </template>

            <!-- 경고 -->
            <div v-if="t.alerts?.length" class="fm-alerts">
              <div v-for="(a, i) in t.alerts.slice(0, 3)" :key="i"
                   class="fm-alert" :class="`lv-${a.level}`">
                <span class="fm-alert-icon">{{ a.level === 'critical' ? '🔴' : a.level === 'warning' ? '🟡' : 'ℹ️' }}</span>
                <span>{{ a.message }}</span>
              </div>
            </div>

            <!-- 스파크라인 (메모리 추이) -->
            <div v-if="sparkData(t.target_id).length > 1" class="fm-spark-wrap">
              <svg class="fm-spark" viewBox="0 0 100 20" preserveAspectRatio="none">
                <polyline
                  :points="sparkPoints(t.target_id)"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1"
                  stroke-linejoin="round"
                  stroke-linecap="round"
                />
              </svg>
            </div>
          </section>
        </div>

        <!-- Footer -->
        <div class="fm-footer">
          <span class="fm-poll-ind" :class="{ 'is-polling': store.loading }">●</span>
          <span class="fm-poll-text">
            {{ store.hasActiveJobs ? '2초' : '10초' }} 갱신
          </span>
          <span class="fm-sep">·</span>
          <span>{{ store.pollCount }}회</span>
          <button class="fm-reset-btn" title="위치 초기화" @click="store.resetPos()">
            <svg viewBox="0 0 12 12" width="10" height="10">
              <path d="M9 3a4 4 0 1 1-3.5-1.7" fill="none" stroke="currentColor" stroke-width="1.3"/>
              <polyline points="6,0.5 9,3 7,5" fill="none" stroke="currentColor" stroke-width="1.3"/>
            </svg>
          </button>
        </div>
      </div>
      
      <!-- v90.21: 우하단 리사이즈 핸들 -->
      <div v-if="!store.minimized" 
           class="fm-resize-handle" 
           @pointerdown.stop="startResize"
           title="크기 조정 (드래그)">
        <svg viewBox="0 0 16 16" width="14" height="14">
          <line x1="4" y1="14" x2="14" y2="4" stroke="currentColor" stroke-width="1.5" opacity="0.6"/>
          <line x1="8" y1="14" x2="14" y2="8" stroke="currentColor" stroke-width="1.5" opacity="0.6"/>
          <line x1="12" y1="14" x2="14" y2="12" stroke="currentColor" stroke-width="1.5" opacity="0.6"/>
        </svg>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, ref, reactive } from 'vue'
import { useMonitorStore } from '@/store/monitorStore.js'
import { useDragFloat } from '@/composables/useDragFloat.js'
import { fmtNum } from '@/utils/numberUtils.js'

const store = useMonitorStore()

// v10 Phase A-3.5: 범례 토글
const showLegend = ref(false)

// v90.14: Adaptive Resource 미니 컨트롤 state
const jobThrottle = reactive({})        // job_id → throttle_pct (100/75/50/25)
const jobMode = reactive({})            // job_id → 'auto'/'hybrid'/'manual'
const jobLastDecision = reactive({})    // job_id → 가장 최근 AI 의사결정 텍스트

// v95_p39 (2026-05-05 본부장님): 변경 효과 상세 표시 — 이전/이후 policy
//   본부장님 호소: "Throttle 100→75 변경 시 구체적으로 어떻게 변경되는지 보여줘"
//                "Thread X개 → Thread Y개 처럼"
//   진단: 백엔드 API 가 policy 객체 (throttle_pct, batch_size, parallelism) 응답
//   처방: 응답 받아서 변경 전후 비교를 두세줄로 표시
const jobLastChange = reactive({})      // job_id → {action, before:{...}, after:{...}, time}

// v90.21: 우하단 리사이즈 핸들
function startResize(ev) {
  ev.preventDefault()
  const startX = ev.clientX
  const startY = ev.clientY
  const startW = store.pos.w
  const startH = store.pos.h
  const minW = 280
  const minH = 200
  const maxW = Math.min(window.innerWidth - 40, 900)
  const maxH = Math.min(window.innerHeight - 40, 1200)
  
  function onMove(e) {
    const dx = e.clientX - startX
    const dy = e.clientY - startY
    const newW = Math.max(minW, Math.min(maxW, startW + dx))
    const newH = Math.max(minH, Math.min(maxH, startH + dy))
    if (typeof store.setSize === 'function') {
      store.setSize(newW, newH)
    } else {
      // store.setSize 미구현 시 fallback - pos 직접 변경
      store.pos.w = newW
      store.pos.h = newH
    }
  }
  function onUp() {
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
  document.body.style.cursor = 'nwse-resize'
  document.body.style.userSelect = 'none'
}

// v90.17: job 별 throttle/mode helper - default 100%/hybrid (선택 안 됐을 때 표시용)
function getJobThrottle(jobId) {
  return jobThrottle[jobId] ?? 100  // default 100%
}
function getJobMode(jobId) {
  return jobMode[jobId] ?? 'hybrid'  // default 하이브리드
}

// v90.42: 활성 영역(테이블/객체) 중 진행률 표시
//   - 테이블만 있으면 테이블 %
//   - 객체만 있으면 객체 %
//   - 둘 다면 더 큰 쪽 (사용자 입장에서 "방금 본 진행도" 와 일치)
function getOverallPct(job) {
  if (!job) return 0
  const tblTotal = Number(job.table_total) || 0
  const objTotal = Number(job.obj_total) || 0
  const tblPct = tblTotal > 0 ? (Number(job.progress) || 0) : -1
  const objPct = objTotal > 0 ? (Number(job.obj_progress) || 0) : -1
  if (tblPct < 0 && objPct < 0) return 0
  return Math.round(Math.max(tblPct, objPct))
}

async function setJobThrottle(jobId, pct) {
  // v95_p39 (2026-05-05 본부장님): 변경 전 정책 캡처 (이전 → 이후 비교용)
  const prevThrottle = jobThrottle[jobId] ?? 100
  const prevPolicy = computeLocalPolicy(prevThrottle)
  jobThrottle[jobId] = pct  // 낙관적 UI 업데이트
  try {
    const r = await fetch(`/api/v1/jobs/${jobId}/resource/throttle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ throttle_pct: pct, user: 'admin' }),
    })
    const data = await r.json().catch(() => ({}))
    if (!r.ok) {
      const detail = data.detail || `HTTP ${r.status}`
      throw new Error(detail)
    }
    // v95_p39: 백엔드 응답의 policy 활용 — Thread 수 + Batch 크기 변화
    const newPolicy = data.policy || computeLocalPolicy(pct)
    // v95_p44 (2026-05-05 본부장님): 슬롯 분리 — throttle 슬롯만 갱신 (mode 정보 보존)
    if (!jobLastChange[jobId] || typeof jobLastChange[jobId] !== 'object'
        || jobLastChange[jobId].action !== undefined) {
      // 기존 단일 객체 형태 → 새 슬롯 형태로 마이그레이션
      jobLastChange[jobId] = { throttle: null, mode: null }
    }
    jobLastChange[jobId].throttle = {
      before: prevPolicy,
      after: {
        throttle_pct: newPolicy.throttle_pct ?? pct,
        batch_size: newPolicy.batch_size ?? computeLocalPolicy(pct).batch_size,
        parallelism: newPolicy.parallelism ?? computeLocalPolicy(pct).parallelism,
      },
      time: Date.now(),
      manual: true,
    }
    jobLastDecision[jobId] = `Throttle ${prevThrottle}% → ${pct}% (수동) ✓`
    console.log('[FloatingMonitor] throttle 적용 성공:', data)
  } catch (e) {
    console.warn('[FloatingMonitor] throttle 실패:', e.message)
    jobLastDecision[jobId] = `⚠️ ${e.message}`
    // v95_p44: 실패 시 throttle 슬롯만 비움 (mode 슬롯 보존)
    if (jobLastChange[jobId] && typeof jobLastChange[jobId] === 'object'
        && jobLastChange[jobId].action === undefined) {
      jobLastChange[jobId].throttle = null
    } else {
      jobLastChange[jobId] = { throttle: null, mode: null }
    }
  }
}

async function setJobMode(jobId, mode) {
  // v95_p39: 변경 전 모드 캡처
  const prevMode = jobMode[jobId] ?? 'hybrid'
  jobMode[jobId] = mode
  try {
    const r = await fetch(`/api/v1/jobs/${jobId}/resource/mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ mode, user: 'admin' }),
    })
    const data = await r.json().catch(() => ({}))
    if (!r.ok) {
      const detail = data.detail || `HTTP ${r.status}`
      throw new Error(detail)
    }
    const modeName = mode === 'auto' ? 'AI 자동' : mode === 'hybrid' ? '하이브리드' : '수동'
    const prevModeName = prevMode === 'auto' ? 'AI 자동' : prevMode === 'hybrid' ? '하이브리드' : '수동'
    // v95_p39: 모드 변경 효과 (현재 throttle 기반 정책)
    const curThrottle = jobThrottle[jobId] ?? 100
    const curPolicy = computeLocalPolicy(curThrottle)
    // v95_p44 (2026-05-05 본부장님): 슬롯 분리 — mode 슬롯만 갱신 (throttle 정보 보존)
    if (!jobLastChange[jobId] || typeof jobLastChange[jobId] !== 'object'
        || jobLastChange[jobId].action !== undefined) {
      jobLastChange[jobId] = { throttle: null, mode: null }
    }
    jobLastChange[jobId].mode = {
      before: { mode: prevModeName, ...curPolicy },
      after: { mode: modeName, ...curPolicy },
      time: Date.now(),
      manual: true,
    }
    jobLastDecision[jobId] = `모드: ${prevModeName} → ${modeName} ✓`
    console.log('[FloatingMonitor] mode 변경 성공:', data)
  } catch (e) {
    console.warn('[FloatingMonitor] mode 변경 실패:', e.message)
    jobLastDecision[jobId] = `⚠️ ${e.message}`
    // v95_p44: 실패 시 mode 슬롯만 비움 (throttle 슬롯 보존)
    if (jobLastChange[jobId] && typeof jobLastChange[jobId] === 'object'
        && jobLastChange[jobId].action === undefined) {
      jobLastChange[jobId].mode = null
    } else {
      jobLastChange[jobId] = { throttle: null, mode: null }
    }
  }
}

// v95_p39 (2026-05-05 본부장님): throttle_pct → batch_size + parallelism 로컬 매핑
//   백엔드 ThrottleController._throttle_to_batch / _throttle_to_parallelism 와 일치
//   백엔드 응답이 없거나 늦을 때의 즉시 표시용 (낙관적 UI)
function computeLocalPolicy(pct) {
  const BASE_BATCH = 5000
  const batch_size = Math.max(500, Math.floor(BASE_BATCH * pct / 100))
  let parallelism
  if (pct >= 100) parallelism = 3
  else if (pct >= 75) parallelism = 2
  else parallelism = 1
  return { throttle_pct: pct, batch_size, parallelism }
}

// v95_p39: Thread 변화에 따른 클래스 (감소=노란색, 증가=초록, 동일=회색)
function threadDeltaClass(change) {
  const delta = (change.after.parallelism || 0) - (change.before.parallelism || 0)
  if (delta < 0) return 'fm-delta-down'
  if (delta > 0) return 'fm-delta-up'
  return 'fm-delta-same'
}
function batchDeltaClass(change) {
  const delta = (change.after.batch_size || 0) - (change.before.batch_size || 0)
  if (delta < 0) return 'fm-delta-down'
  if (delta > 0) return 'fm-delta-up'
  return 'fm-delta-same'
}

// Throttle 변경 힌트 — 사용자가 효과를 직관적으로 이해
function throttleHint(change) {
  const before = change.before.throttle_pct
  const after = change.after.throttle_pct
  if (after === before) return '— 변화 없음'
  const delta = after - before
  const pctRel = Math.abs(Math.round((delta / before) * 100))
  if (delta < 0) {
    if (after <= 25)
      return `💡 부하 최소화 모드 — DB 부담 ${pctRel}% 경감, 이관 속도 느림`
    if (after <= 50)
      return `💡 부하 절감 — 동시 처리량 ${pctRel}% 감소, 다른 작업과 공존 유리`
    return `💡 부하 살짝 절감 — 메모리/CPU 여유 확보`
  } else {
    if (after >= 100)
      return `🚀 최대 성능 — 모든 자원 사용, 가장 빠른 이관`
    return `🚀 속도 ${pctRel}% 향상 — 이관 시간 단축`
  }
}

// 모드 변경 힌트
function modeHint(modeName) {
  if (modeName === 'AI 자동') return '💡 AI 가 시스템 부하 보고 자동 조정 — 최소 개입'
  if (modeName === '하이브리드') return '💡 AI 권고 + 사용자 승인 — 균형형 (default)'
  if (modeName === '수동') return '💡 사용자 직접 제어 — AI 조정 비활성화'
  return ''
}

// 드래그
const posRef = computed(() => store.pos)
const { dragging, startDrag } = useDragFloat({
  pos: posRef,
  onMove: (x, y) => store.setPos(x, y),
})

// 스타일
const rootStyle = computed(() => ({
  left:  store.pos.x + 'px',
  top:   store.pos.y + 'px',
  width: store.pos.w + 'px',
  height: store.minimized ? 'auto' : (store.pos.h + 'px'),
}))

// 데이터
const targets = computed(() => store.live?.targets || [])
const activeJobs = computed(() => store.live?.jobs || [])

// 알림 기반 상태 도트 색
const alertDotClass = computed(() => {
  const alerts = store.live?.targets?.flatMap(t => t.alerts || []) || []
  if (alerts.some(a => a.level === 'critical')) return 'crit'
  if (alerts.some(a => a.level === 'warning'))  return 'warn'
  if (store.error) return 'crit'
  if (store.loading) return 'polling'
  return 'ok'
})

// 최소화 시 한 줄 요약
const minimizedSummary = computed(() => {
  if (store.error) return '⚠ 연결 오류'
  const parts = []
  // 첫 번째 Localhost
  const local = targets.value.find(t => t.target_type === 'localhost')
  if (local?.system) parts.push(`MEM ${local.system.mem_pct?.toFixed(0)}%`)

  // Docker 컨테이너 수
  const docker = targets.value.find(t => t.target_type === 'docker')
  if (docker?.docker?.containers?.length) {
    parts.push(`🐳 ${docker.docker.containers.length}`)
  }

  // Job 진행
  if (activeJobs.value.length) {
    const j = activeJobs.value[0]
    parts.push(`▶ ${j.progress?.toFixed(0) || 0}%`)
  }

  const crit = store.criticalAlerts.length
  if (crit) parts.push(`🔴 ${crit}`)

  return parts.join(' · ') || '대기 중'
})

// ── 유틸 ────────────────────────────────
function levelClass(value, warn, crit) {
  if (value == null) return ''
  if (value >= crit) return 'lv-crit'
  if (value >= warn) return 'lv-warn'
  return 'lv-ok'
}

// v10 Phase A-3.5: 텍스트 색상도 레벨에 따라
function levelTextClass(value, warn, crit) {
  if (value == null) return ''
  if (value >= crit) return 'txt-crit'
  if (value >= warn) return 'txt-warn'
  return ''
}

// v10 Phase A-3.5: 컨테이너 메모리 툴팁 (1.66 / 3.69 GiB 같은 상세 수치)
function memTooltip(c) {
  const lines = [`컨테이너 메모리 사용률: ${c.mem_pct?.toFixed(1)}%`]
  // 백엔드가 bytes 로 제공 (mem_used, mem_limit)
  if (c.mem_used != null && c.mem_limit != null && c.mem_limit > 0) {
    const usedGiB = (c.mem_used / (1024 ** 3)).toFixed(2)
    const limitGiB = (c.mem_limit / (1024 ** 3)).toFixed(2)
    lines.push(`실사용: ${usedGiB} / ${limitGiB} GiB`)
  }
  lines.push('', '🟢 <80% 안전', '🟡 80-95% 주의', '🔴 >95% 위험 (OOM)')
  return lines.join('\n')
}

// v10 Phase A-3.5: 시스템 메모리 툴팁
function systemMemTooltip(sys) {
  if (!sys) return ''
  const lines = []
  // bytes 또는 MB 필드 둘 다 대응
  if (sys.mem_used != null && sys.mem_total != null) {
    const usedGB = (sys.mem_used / (1024 ** 3)).toFixed(1)
    const totalGB = (sys.mem_total / (1024 ** 3)).toFixed(1)
    lines.push(`실사용: ${usedGB} / ${totalGB} GB`)
  }
  if (sys.mem_available != null) {
    const availGB = (sys.mem_available / (1024 ** 3)).toFixed(1)
    lines.push(`가용: ${availGB} GB`)
  }
  return lines.join('\n')
}

// v10 Phase A-3.5: 상태 한글 라벨
function healthLabel(h) {
  return ({
    healthy: '정상 (healthy)',
    unhealthy: '비정상 (unhealthy)',
    starting: '시작 중 (starting)',
    none: '상태 정보 없음',
  })[h] || '알 수 없음'
}

function bcrClass(v) {
  if (v < 90) return 'fm-crit'
  if (v < 95) return 'fm-warn'
  return ''
}

function pleClass(v) {
  if (v < 180) return 'fm-crit'
  if (v < 300) return 'fm-warn'
  return ''
}

function typeLabel(t) {
  return ({
    localhost: '🖥 로컬',
    docker:    '🐳 Docker',
    db_native: '🗃 DB',
    ssh:       '🔑 SSH',
    winrm:     '🪟 WinRM',
  })[t] || t
}

function hasErrors(t) {
  return t.errors && Object.keys(t.errors).length > 0
}

// 스파크라인 데이터 추출 (메모리 또는 BCR)
function sparkData(targetId) {
  return store.history[targetId] || []
}

function sparkPoints(targetId) {
  const points = sparkData(targetId)
  if (points.length < 2) return ''
  // 우선순위: bcr > mem_pct > docker_max_mem
  const key = points[0].bcr != null ? 'bcr'
            : points[0].mem_pct != null ? 'mem_pct'
            : 'docker_max_mem'
  const vals = points.map(p => p[key] ?? 0)
  const n = vals.length
  // y 범위 고정: bcr 은 90~100, 나머지 0~100
  const [yMin, yMax] = key === 'bcr' ? [90, 100] : [0, 100]
  const scaleY = (v) => {
    const clamped = Math.max(yMin, Math.min(yMax, v))
    return 20 - ((clamped - yMin) / (yMax - yMin)) * 18 - 1  // 상하 1 여백
  }
  return vals.map((v, i) => {
    const x = n > 1 ? (i / (n - 1)) * 100 : 0
    return `${x.toFixed(1)},${scaleY(v).toFixed(1)}`
  }).join(' ')
}
</script>

<style scoped>
/* 루트 — position:fixed 로 페이지 이동 무관 */
.fm-root {
  position: fixed;
  z-index: 9999;
  background: var(--bg-primary);
  border: 0.5px solid var(--border-mid);
  border-radius: var(--radius-lg);
  box-shadow: 0 8px 24px rgba(0, 0, 0, .12), 0 2px 6px rgba(0, 0, 0, .08);
  color: var(--text-primary);
  font-family: var(--font);
  font-size: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: box-shadow .15s ease;
}
.fm-root.fm-dragging {
  box-shadow: 0 16px 32px rgba(0, 0, 0, .2), 0 4px 12px rgba(0, 0, 0, .15);
  cursor: grabbing !important;
}
.fm-root.fm-min {
  height: auto !important;
}
[data-theme="dark"] .fm-root {
  box-shadow: 0 8px 24px rgba(0, 0, 0, .4), 0 2px 6px rgba(0, 0, 0, .3);
}

/* 헤더 */
.fm-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border-bottom: 0.5px solid var(--border-light);
  cursor: grab;
  user-select: none;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}
.fm-header:active { cursor: grabbing; }
.fm-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--accent-green);
  flex-shrink: 0;
}
.fm-dot.warn { background: #eab308; }
.fm-dot.crit { background: #dc2626; animation: fm-pulse 1.2s infinite; }
.fm-dot.polling { background: var(--accent-blue); }
@keyframes fm-pulse { 0%,100% { opacity: 1; } 50% { opacity: .4; } }

.fm-title { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.fm-actions { display: flex; gap: 2px; flex-shrink: 0; }
.fm-btn {
  width: 20px; height: 20px; border: none; background: transparent;
  color: var(--text-secondary); cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 4px;
}
.fm-btn:hover { background: var(--border-light); color: var(--text-primary); }

/* 본문 */
.fm-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.fm-error {
  margin: 8px; padding: 6px 8px;
  background: var(--bg-danger); color: var(--text-danger);
  border-radius: var(--radius-sm);
  font-size: 11px;
}

.fm-section {
  padding: 8px 12px;
  border-bottom: 0.5px solid var(--border-light);
}
.fm-section:last-child { border-bottom: none; }
.fm-jobs {
  background: var(--bg-info);
  border-bottom: 1px solid rgba(55, 138, 221, .2);
}
.fm-section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0 0 6px 0;
  text-transform: uppercase;
  letter-spacing: .3px;
}

.fm-running-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--accent-blue);
  animation: fm-pulse 1.2s infinite;
}

.fm-type-pill {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
  background: var(--bg-tertiary);
  color: var(--text-tertiary);
  text-transform: none;
  letter-spacing: 0;
  font-weight: 500;
}
.fm-type-pill.t-db_native { background: var(--bg-info); color: var(--text-info); }
.fm-type-pill.t-docker    { background: #e0f2fe; color: #075985; }
[data-theme="dark"] .fm-type-pill.t-docker { background: #082f49; color: #7dd3fc; }

.fm-target-name {
  flex: 1;
  font-weight: 500;
  color: var(--text-primary);
  text-transform: none;
  letter-spacing: 0;
  font-size: 11.5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.fm-target-error {
  font-size: 11px;
  color: var(--text-warning);
  padding: 4px 6px;
  background: var(--bg-warning);
  border-radius: var(--radius-sm);
  margin-bottom: 6px;
}

/* Job */
.fm-job-row { margin-bottom: 6px; }
.fm-job-row:last-child { margin-bottom: 0; }
.fm-job-top {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 11px; margin-bottom: 3px;
}
.fm-job-name {
  font-weight: 500; color: var(--text-primary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  max-width: 70%;
}
.fm-job-pct { font-variant-numeric: tabular-nums; color: var(--text-info); font-weight: 600; }
.fm-job-meta { font-size: 10.5px; color: var(--text-tertiary); margin-top: 2px; }

/* 메트릭 행 */
.fm-metric {
  display: grid;
  grid-template-columns: 48px 1fr 36px;
  gap: 8px;
  align-items: center;
  font-size: 11px;
  margin-bottom: 4px;
}
.fm-metric label { color: var(--text-secondary); }
.fm-metric-val {
  text-align: right; font-variant-numeric: tabular-nums;
  color: var(--text-primary); font-weight: 500;
}

/* 바 */
.fm-bar {
  height: 6px;
  background: var(--border-light);
  border-radius: 3px;
  overflow: hidden;
  position: relative;
}
.fm-bar-sm { height: 4px; }
.fm-bar-fill {
  height: 100%;
  background: var(--accent-blue);
  border-radius: 3px;
  transition: width .3s ease;
}
.fm-bar-fill.lv-ok    { background: var(--accent-green); }
.fm-bar-fill.lv-warn  { background: #eab308; }
.fm-bar-fill.lv-crit  { background: #dc2626; }

/* v90.42: 듀얼 진행 막대 (테이블/객체 분리) */
.fm-bar-tbl { margin-bottom: 3px; }
.fm-bar-obj { margin-bottom: 3px; }
.fm-bar-fill.fm-obj-fill { background: #10b981; }   /* 객체는 녹색 */
.fm-job-meta .fm-fail { color: #dc2626; font-weight: 600; margin-left: 4px; }

/* 컨테이너 */
.fm-container {
  margin-bottom: 6px;
  padding: 5px 6px;
  border-radius: 4px;
  background: var(--bg-secondary);
}
.fm-container-head {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; margin-bottom: 4px;
}
.fm-container-name {
  flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  font-family: ui-monospace, 'SF Mono', Menlo, monospace; font-size: 10.5px;
  font-weight: 500;
}
.fm-container-pct { font-variant-numeric: tabular-nums; color: var(--text-secondary); }

/* v10 Phase A-3.5: 컨테이너 메모리/CPU 개별 행 */
.fm-container-metric {
  display: grid;
  grid-template-columns: 36px 1fr 32px;
  gap: 5px;
  align-items: center;
  font-size: 10px;
  margin-top: 2px;
  cursor: help;
}
.fm-metric-tiny-label {
  color: var(--text-tertiary);
  font-size: 9.5px;
  font-weight: 500;
}
.fm-metric-tiny-val {
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: var(--text-secondary);
  font-size: 10px;
  font-weight: 500;
}

/* v10 Phase A-3.5: 텍스트 색상도 레벨 반영 */
.txt-warn { color: #d97706 !important; font-weight: 600; }
.txt-crit { color: #dc2626 !important; font-weight: 700; }

/* v10 Phase A-3.5: 범례 패널 */
.fm-legend {
  padding: 10px 12px;
  background: var(--bg-info);
  border-bottom: 1px solid var(--border-light);
  font-size: 11px;
  line-height: 1.5;
  max-height: 300px;
  overflow-y: auto;
}
.fm-legend-title {
  margin: 0 0 6px 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-info);
}
.fm-legend-section {
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 0.5px solid rgba(55, 138, 221, .15);
}
.fm-legend-section:last-child { border-bottom: none; margin-bottom: 0; }
.fm-legend-section strong {
  display: block; font-size: 11px; color: var(--text-primary); margin-bottom: 3px;
}
.fm-legend-section ul {
  margin: 0 0 0 14px; padding: 0; font-size: 10.5px;
}
.fm-legend-section li { margin-bottom: 1px; color: var(--text-secondary); }
.fm-legend-section li b { color: var(--text-primary); }
.fm-legend-colors {
  display: flex; gap: 6px; margin: 3px 0; flex-wrap: wrap;
}
.fm-lc {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 500;
}
.fm-lc-ok { background: rgba(34,197,94,.15); color: #16a34a; }
.fm-lc-warn { background: rgba(234,179,8,.15); color: #ca8a04; }
.fm-lc-crit { background: rgba(220,38,38,.15); color: #dc2626; }
.fm-legend-note {
  margin: 4px 0 0 0;
  font-size: 10px;
  color: var(--text-tertiary);
  line-height: 1.45;
}
.fm-legend-note em {
  color: var(--text-info);
  font-style: italic;
}

/* 버튼 활성 상태 */
.fm-btn.is-active {
  background: var(--accent-blue);
  color: #fff;
}
.fm-btn.is-active:hover {
  background: var(--accent-blue);
  color: #fff;
  opacity: .9;
}
.fm-health {
  width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
  background: var(--text-tertiary);
}
.fm-health.h-healthy   { background: var(--accent-green); }
.fm-health.h-unhealthy { background: #dc2626; animation: fm-pulse 1.2s infinite; }
.fm-health.h-starting  { background: #eab308; }

/* Key-Value */
.fm-kv {
  display: flex; justify-content: space-between;
  font-size: 11px; padding: 2px 0;
}
.fm-kv-k { color: var(--text-secondary); }
.fm-kv-v { font-variant-numeric: tabular-nums; color: var(--text-primary); font-weight: 500; }
.fm-kv-v.fm-warn { color: var(--text-warning); }
.fm-kv-v.fm-crit { color: var(--text-danger); font-weight: 600; }

/* 경고 */
.fm-alerts { margin-top: 6px; }
.fm-alert {
  display: flex; gap: 6px; font-size: 11px;
  padding: 4px 6px; margin-bottom: 2px;
  border-radius: var(--radius-sm); line-height: 1.3;
}
.fm-alert.lv-critical { background: var(--bg-danger);  color: var(--text-danger); }
.fm-alert.lv-warning  { background: var(--bg-warning); color: var(--text-warning); }
.fm-alert.lv-info     { background: var(--bg-info);    color: var(--text-info); }
.fm-alert-icon { flex-shrink: 0; }

/* 스파크라인 — DOM 3줄, 매우 경량 */
.fm-spark-wrap {
  margin-top: 6px;
  height: 20px;
  color: var(--accent-blue);
  opacity: .6;
}
.fm-spark { width: 100%; height: 100%; }

/* 스크롤 */
.fm-scroll {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}
.fm-scroll::-webkit-scrollbar { width: 6px; }
.fm-scroll::-webkit-scrollbar-thumb { background: var(--border-mid); border-radius: 3px; }

/* 빈 상태 */
.fm-empty { text-align: center; padding: 24px 16px; color: var(--text-tertiary); }
.fm-empty p { margin: 0 0 4px 0; }
.fm-empty-hint { font-size: 10.5px; }

/* Footer */
.fm-footer {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px;
  background: var(--bg-secondary);
  border-top: 0.5px solid var(--border-light);
  font-size: 10.5px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}
.fm-poll-ind { color: var(--text-tertiary); transition: color .2s; }
.fm-poll-ind.is-polling { color: var(--accent-blue); }
.fm-sep { opacity: .4; }
.fm-reset-btn {
  margin-left: auto;
  width: 18px; height: 18px;
  border: none; background: transparent; cursor: pointer;
  color: var(--text-tertiary); display: inline-flex; align-items: center; justify-content: center;
  border-radius: 3px;
}
.fm-reset-btn:hover { background: var(--border-light); color: var(--text-primary); }

/* 접근성: 애니메이션 감소 */
html.reduced-motion .fm-dot.crit,
html.reduced-motion .fm-health.h-unhealthy,
html.reduced-motion .fm-running-dot {
  animation: none !important;
}
/* ════════════════════════════════════════════════════════════
   v90.14: 미니 Throttle / Mode 컨트롤 (FloatingMonitor 안)
   ════════════════════════════════════════════════════════════ */
.fm-throttle-mini {
  margin-top: 8px;
  padding: 6px 8px;
  background: var(--color-background-secondary, #f8fafc);
  border: 1px dashed var(--color-border-secondary, #e2e8f0);
  border-radius: 6px;
}
.fm-throttle-row {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 4px;
}
.fm-throttle-row:last-child {
  margin-bottom: 0;
}
.fm-throttle-label {
  font-size: 9px;
  font-weight: 600;
  color: var(--color-text-secondary, #64748b);
  width: 50px;
  flex-shrink: 0;
  letter-spacing: 0.2px;
}
.fm-throttle-btn,
.fm-mode-btn {
  flex: 1;
  font-size: 10px;
  font-weight: 600;
  padding: 3px 6px;
  background: var(--color-background-primary, #fff);
  color: var(--color-text-primary, #1e293b);
  border: 1px solid var(--color-border-secondary, #e2e8f0);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.12s;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.fm-throttle-btn:hover,
.fm-mode-btn:hover {
  border-color: #94a3b8;
  background: var(--color-background-tertiary, #f1f5f9);
}
.fm-throttle-btn.active {
  background: #14b8a6;
  color: #fff;
  border: 2px solid #0f766e;
  font-weight: 700;
  box-shadow: 0 0 0 2px rgba(20, 184, 166, 0.4);
  position: relative;
}
.fm-throttle-btn.active::before {
  content: '✓ ';
  font-weight: 700;
}
.fm-mode-btn.active {
  background: #3b82f6;
  color: #fff;
  border: 2px solid #1d4ed8;
  font-weight: 700;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.4);
  position: relative;
}
.fm-mode-btn.active::before {
  content: '✓ ';
  font-weight: 700;
}
.fm-ai-decision {
  margin-top: 4px;
  padding: 3px 6px;
  font-size: 9px;
  color: var(--color-text-secondary, #64748b);
  background: rgba(20, 184, 166, 0.05);
  border-left: 2px solid #14b8a6;
  border-radius: 0 3px 3px 0;
  font-style: italic;
}

/* v95_p39 (2026-05-05 본부장님): 변경 효과 상세 표시 */
.fm-change-detail {
  margin-top: 4px;
  padding: 5px 7px;
  background: rgba(99, 102, 241, 0.04);
  border-left: 2px solid #6366f1;
  border-radius: 0 3px 3px 0;
}
/* v95_p44 (2026-05-05 본부장님): Mode 카드 — Throttle 카드와 시각 구분 */
.fm-change-mode-card {
  background: rgba(20, 184, 166, 0.04);
  border-left-color: #14b8a6;
}
.fm-change-rows {
  display: flex; flex-direction: column; gap: 2px;
}
.fm-change-row {
  display: flex; align-items: center;
  font-size: 10px;
  font-family: ui-monospace, SFMono-Regular, monospace;
  letter-spacing: 0.01em;
}
.fm-change-label {
  width: 56px; flex-shrink: 0;
  color: var(--color-text-secondary, #64748b);
  font-family: var(--font, system-ui);
}
.fm-change-arrow {
  display: flex; align-items: center; gap: 5px;
}
.fm-change-from {
  color: var(--color-text-tertiary, #94a3b8);
  font-weight: 500;
}
.fm-change-mid {
  color: var(--color-text-tertiary, #94a3b8);
  opacity: 0.6;
}
.fm-change-to {
  font-weight: 700;
}
.fm-delta-down {
  color: #d97706;  /* 감소 = 노란색 (부하 절감) */
}
.fm-delta-up {
  color: #059669;  /* 증가 = 초록 (성능 향상) */
}
.fm-delta-same {
  color: var(--color-text-secondary, #64748b);
}
.fm-change-hint {
  margin-top: 3px;
  padding-top: 3px;
  border-top: 0.5px dashed rgba(99, 102, 241, 0.15);
  font-size: 9.5px;
  color: var(--color-text-secondary, #64748b);
  font-style: italic;
  line-height: 1.45;
}

/* v90.21: 우하단 리사이즈 핸들 */
.fm-resize-handle {
  position: absolute;
  right: 2px;
  bottom: 2px;
  width: 18px;
  height: 18px;
  cursor: nwse-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-tertiary, #94a3b8);
  z-index: 10;
  border-radius: 0 0 8px 0;
  transition: color 0.15s, background 0.15s;
}
.fm-resize-handle:hover {
  color: #14b8a6;
  background: rgba(20, 184, 166, 0.08);
}

/* fm-root 가 relative 컨테이너인지 확인용 - 이미 있으면 유지 */

</style>
