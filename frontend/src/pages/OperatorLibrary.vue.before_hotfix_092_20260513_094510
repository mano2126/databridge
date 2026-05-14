<template>
  <div class="op-lib">
    <!-- ════════════════════════════════════════════════════════
         v93_LIB (2026-05-01): 본부장님 요청
         망분리 환경에서 AI 도움 없이도 운영자가 셀프 해결할 수 있는
         명령 라이브러리. 모든 명령은 ROOT 경로 자동 치환됨.
         ════════════════════════════════════════════════════════ -->

    <!-- 헤더 -->
    <div class="page-header">
      <div>
        <h2>📚 운영자 라이브러리</h2>
        <p class="muted">망분리 환경/AI 미지원 상황 대비 셀프 운영 매뉴얼.
                         프로젝트 ROOT 경로 입력 시 모든 명령이 자동 치환됩니다.</p>
      </div>
    </div>

    <!-- 상단: 컴팩트 컨트롤 바 — v94_LIB4: ROOT 절반 축소 + 강화된 필터 -->
    <div class="control-bar">
      <div class="root-input">
        <label title="프로젝트 ROOT 경로">📁</label>
        <input v-model="root" @input="saveRoot"
               placeholder="D:\project\databridge_full"
               class="vp-search-input root-field"/>
        <button class="chip-mini" @click="resetRoot" title="기본값으로 초기화">↺</button>
      </div>
      <div class="search-box">
        <input v-model="search" placeholder="🔍 명령/설명/사용시점 검색..." class="vp-search-input"/>
        <span v-if="search" class="match-count">{{ filteredCount }} / {{ totalCount }}</span>
      </div>
      <!-- v94_LIB4: 강화된 필터 (shell / 위험도 / OS / 즐겨찾기) -->
      <div class="filter-group">
        <select v-model="filterShell" class="filter-select" title="Shell 종류">
          <option value="all">Shell: 전체</option>
          <option value="powershell">PowerShell</option>
          <option value="cmd">CMD</option>
          <option value="bash">Bash</option>
          <option value="sql">SQL</option>
        </select>
        <select v-model="filterSeverity" class="filter-select" title="위험도">
          <option value="all">위험도: 전체</option>
          <option value="safe">안전 (배지 없음)</option>
          <option value="warn">주의 (warn)</option>
          <option value="danger">위험 (danger)</option>
        </select>
        <select v-model="filterOs" class="filter-select" title="운영체제">
          <option value="all">OS: 전체</option>
          <option value="win">Windows</option>
          <option value="linux">Linux</option>
          <option value="cross">공통</option>
        </select>
        <button class="chip-mini fav-toggle" :class="{ on: filterFav }"
                @click="filterFav = !filterFav"
                :title="filterFav ? '즐겨찾기만 보기 ON — 클릭해서 끄기' : '즐겨찾기만 보기'">
          {{ filterFav ? '⭐ 즐겨찾기' : '☆ 전체' }}
        </button>
        <button v-if="hasActiveFilters" class="chip-mini clear-filters"
                @click="clearFilters" title="모든 필터 초기화">
          ✕ 필터 초기화
        </button>
      </div>
    </div>

    <!-- 좌측: 카테고리 + 우측: 명령 목록 -->
    <div class="lib-layout">
      <!-- 카테고리 사이드 -->
      <aside class="cat-sidebar">
        <button v-for="c in categories" :key="c.id"
                :class="['cat-btn', { active: activeCat === c.id }]"
                @click="activeCat = c.id">
          <span class="cat-icon">{{ c.icon }}</span>
          <span class="cat-label">{{ c.label }}</span>
          <span class="cat-count">{{ countByCategory[c.id] || 0 }}</span>
        </button>
        <div class="cat-divider"></div>
        <button :class="['cat-btn', { active: activeCat === 'all' }]"
                @click="activeCat = 'all'">
          <span class="cat-icon">🗂</span>
          <span class="cat-label">전체</span>
          <span class="cat-count">{{ totalCount }}</span>
        </button>
      </aside>

      <!-- 명령 목록 -->
      <main class="cmd-main">
        <div v-if="!filtered.length" class="empty">
          <p>검색 결과가 없습니다.</p>
        </div>
        
        <div v-for="cmd in filtered" :key="cmd.id" class="cmd-card"
             :data-cmd-id="cmd.id"
             :class="{ 'cmd-warn': cmd.severity === 'warn',
                       'cmd-danger': cmd.severity === 'danger' }">
          <!-- 카드 헤더 -->
          <div class="cmd-hdr">
            <div class="cmd-title-row">
              <span class="cmd-shell-badge" :class="`shell-${cmd.shell}`">
                {{ cmd.shell.toUpperCase() }}
              </span>
              <!-- v94_LIB4: OS 배지 -->
              <span v-if="cmd.os" class="cmd-os-badge" :class="`os-${cmd.os}`"
                    :title="osTooltip(cmd.os)">
                {{ osLabel(cmd.os) }}
              </span>
              <h4 class="cmd-title">{{ cmd.title }}</h4>
              <span v-if="cmd.severity === 'danger'" class="severity-badge danger">⚠ 주의</span>
              <span v-else-if="cmd.severity === 'warn'" class="severity-badge warn">주의</span>
              <!-- v94_LIB4: 즐겨찾기 별표 -->
              <button class="cmd-fav-btn" @click.stop="toggleFav(cmd.id)"
                      :class="{ on: isFav(cmd.id) }"
                      :title="isFav(cmd.id) ? '즐겨찾기 해제' : '즐겨찾기 추가'">
                {{ isFav(cmd.id) ? '⭐' : '☆' }}
              </button>
            </div>
            <p class="cmd-desc">{{ cmd.desc }}</p>
            <p v-if="cmd.when" class="cmd-when">📍 사용 시점: {{ cmd.when }}</p>
          </div>

          <!-- 명령 본체 -->
          <div class="cmd-body">
            <pre class="cmd-block"><code>{{ resolved(cmd.cmd) }}</code></pre>
            <div class="cmd-actions">
              <button class="chip-action" @click="copyCmd(cmd)">
                {{ copiedId === cmd.id ? '✓ 복사됨' : '📋 복사' }}
              </button>
              <button v-if="cmd.runnable" class="chip-action runnable"
                      @click="runCmd(cmd)" :disabled="cmd._running">
                {{ cmd._running ? '⏳' : '▶ 실행' }}
              </button>
            </div>
          </div>

          <!-- 예상 출력 -->
          <details v-if="cmd.expected" class="cmd-expected">
            <summary>예상 출력 / 결과</summary>
            <pre><code>{{ cmd.expected }}</code></pre>
          </details>

          <!-- 실패 시 처방 -->
          <details v-if="cmd.troubleshoot" class="cmd-trouble">
            <summary>🔧 실패 시 처방</summary>
            <div v-html="cmd.troubleshoot"></div>
          </details>

          <!-- 관련 명령 -->
          <div v-if="cmd.related && cmd.related.length" class="cmd-related">
            <span class="related-label">🔗 관련:</span>
            <button v-for="rid in cmd.related" :key="rid"
                    class="related-link"
                    @click="jumpTo(rid)">
              {{ findCmdTitle(rid) }}
            </button>
          </div>

          <!-- 출력 영역 (실행 시) -->
          <pre v-if="cmd._output" class="cmd-output">{{ cmd._output }}</pre>
        </div>
      </main>
    </div>

    <!-- 인쇄 안내 -->
    <div class="print-hint">
      💡 망분리 환경 운영을 위해 이 페이지를 PDF 로 출력 (Ctrl+P)하면 오프라인 매뉴얼이 됩니다.
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { CATEGORIES, COMMANDS } from './operatorLibraryData.js'

defineOptions({ name: 'OperatorLibrary' })

// ════════════════════════════════════════════════════════════
// ROOT 경로 (자동 치환 변수)
// ════════════════════════════════════════════════════════════
const _LS_KEY = 'opLib_rootPath'
const DEFAULT_ROOT = 'D:\\project\\databridge_full'
const root = ref(localStorage.getItem(_LS_KEY) || DEFAULT_ROOT)

function saveRoot() {
  localStorage.setItem(_LS_KEY, root.value)
}
function resetRoot() {
  root.value = DEFAULT_ROOT
  saveRoot()
}

// 명령 본문의 ${ROOT} 를 입력값으로 치환
function resolved(cmd) {
  if (!cmd) return ''
  return cmd.replace(/\$\{ROOT\}/g, root.value || DEFAULT_ROOT)
}

// ════════════════════════════════════════════════════════════
// 검색 + 카테고리
// ════════════════════════════════════════════════════════════
const search = ref('')
const activeCat = ref('start')

// v94_LIB4: 강화된 필터 state
const filterShell    = ref('all')   // all / powershell / cmd / bash / sql
const filterSeverity = ref('all')   // all / safe / warn / danger
const filterOs       = ref('all')   // all / win / linux / cross
const filterFav      = ref(false)   // 즐겨찾기만

// v94_LIB4: 즐겨찾기 (localStorage 보존)
const _FAV_KEY = 'opLib_favorites'
const favSet = ref(new Set(JSON.parse(localStorage.getItem(_FAV_KEY) || '[]')))
function isFav(id) { return favSet.value.has(id) }
function toggleFav(id) {
  const next = new Set(favSet.value)
  if (next.has(id)) next.delete(id); else next.add(id)
  favSet.value = next
  localStorage.setItem(_FAV_KEY, JSON.stringify([...next]))
}
function osLabel(os) {
  return ({ win: '🪟 Win', linux: '🐧 Linux', cross: '🔀 공통' })[os] || ''
}
function osTooltip(os) {
  return ({ win: 'Windows 전용', linux: 'Linux 전용', cross: 'Windows / Linux 공통' })[os] || ''
}

// CATEGORIES + COMMANDS imported from operatorLibraryData.js
const categories = CATEGORIES

// ════════════════════════════════════════════════════════════
// 명령 라이브러리 — 본부장님과 작업하면서 사용한 모든 명령
// ════════════════════════════════════════════════════════════
const commands = COMMANDS

// ════════════════════════════════════════════════════════════
// 컴퓨티드: 카테고리별 카운트 + 필터링
// ════════════════════════════════════════════════════════════
const totalCount = computed(() => commands.length)

const countByCategory = computed(() => {
  const m = {}
  for (const c of commands) m[c.cat] = (m[c.cat] || 0) + 1
  return m
})

// v94_LIB4: 활성 필터 있나 판단 (필터 초기화 버튼 표시용)
const hasActiveFilters = computed(() =>
  filterShell.value !== 'all' ||
  filterSeverity.value !== 'all' ||
  filterOs.value !== 'all' ||
  filterFav.value
)
function clearFilters() {
  filterShell.value = 'all'
  filterSeverity.value = 'all'
  filterOs.value = 'all'
  filterFav.value = false
}

const filtered = computed(() => {
  let list = commands
  // 카테고리
  if (activeCat.value !== 'all') {
    list = list.filter(c => c.cat === activeCat.value)
  }
  // v94_LIB4: shell 필터
  if (filterShell.value !== 'all') {
    list = list.filter(c => c.shell === filterShell.value)
  }
  // v94_LIB4: 위험도 필터
  if (filterSeverity.value === 'safe') {
    list = list.filter(c => !c.severity)
  } else if (filterSeverity.value !== 'all') {
    list = list.filter(c => c.severity === filterSeverity.value)
  }
  // v94_LIB4: OS 필터 — 'cross' 는 항상 포함, win/linux 는 해당 + cross
  if (filterOs.value !== 'all') {
    list = list.filter(c => {
      // os 필드 없는 명령은 Windows 기본 (대부분 PowerShell 임)
      const cmdOs = c.os || (c.shell === 'bash' ? 'linux' : 'win')
      if (filterOs.value === 'cross') return cmdOs === 'cross'
      return cmdOs === filterOs.value || cmdOs === 'cross'
    })
  }
  // v94_LIB4: 즐겨찾기 필터
  if (filterFav.value) {
    list = list.filter(c => favSet.value.has(c.id))
  }
  // 검색
  const q = (search.value || '').toLowerCase().trim()
  if (q) {
    list = list.filter(c =>
      (c.title || '').toLowerCase().includes(q) ||
      (c.desc || '').toLowerCase().includes(q) ||
      (c.cmd || '').toLowerCase().includes(q) ||
      (c.when || '').toLowerCase().includes(q)
    )
  }
  return list
})
const filteredCount = computed(() => filtered.value.length)

// ════════════════════════════════════════════════════════════
// 인터랙션
// ════════════════════════════════════════════════════════════
const copiedId = ref('')
async function copyCmd(cmd) {
  const text = resolved(cmd.cmd)
  try {
    await navigator.clipboard.writeText(text)
    copiedId.value = cmd.id
    setTimeout(() => { if (copiedId.value === cmd.id) copiedId.value = '' }, 1500)
  } catch (e) {
    // fallback for older browsers
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    try { document.execCommand('copy') } catch {}
    document.body.removeChild(ta)
    copiedId.value = cmd.id
    setTimeout(() => { if (copiedId.value === cmd.id) copiedId.value = '' }, 1500)
  }
}

function findCmdTitle(id) {
  const c = commands.find(x => x.id === id)
  return c ? c.title : id
}

function jumpTo(id) {
  const c = commands.find(x => x.id === id)
  if (!c) return
  activeCat.value = c.cat
  search.value = ''
  setTimeout(() => {
    const el = document.querySelector(`[data-cmd-id="${id}"]`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, 100)
}

async function runCmd(cmd) {
  // 미래 확장 — 백엔드에 안전한 명령만 실행 가능
  alert('실행 기능은 보안 검토 후 추가 예정입니다. 현재는 복사만 가능합니다.')
}

// ════════════════════════════════════════════════════════════
// 마운트
// ════════════════════════════════════════════════════════════
onMounted(() => {
  // URL 해시로 바로가기 지원: #cmd=xxx
  const m = window.location.hash.match(/cmd=([\w_]+)/)
  if (m) {
    setTimeout(() => jumpTo(m[1]), 200)
  }
})
</script>

<style scoped>
.op-lib {
  padding: 16px 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header h2 { margin: 0 0 4px; font-size: 22px; }
.page-header .muted { color: #64748b; font-size: 13px; margin: 0; }

/* 컨트롤 바 — v94_LIB4: ROOT 축소 + 필터 그룹 */
.control-bar {
  display: flex;
  gap: 10px;
  align-items: center;
  margin: 16px 0 20px;
  padding: 10px 14px;
  background: linear-gradient(135deg, #f0f9ff, #fff);
  border: 1px solid #bae6fd;
  border-radius: 8px;
  flex-wrap: wrap;
}
/* v94_LIB4: ROOT 절반 축소 (280px+ → 약 140~180px) */
.root-input { display: flex; gap: 4px; align-items: center; }
.root-input label { font-size: 14px; color: #0c4a6e; cursor: help; }
.root-field {
  font-family: ui-monospace, monospace;
  width: 180px;       /* 고정 폭 — 더 이상 flex:1 로 늘어나지 않음 */
  font-size: 11.5px;
  padding: 4px 8px;
}
.chip-mini {
  padding: 4px 8px;
  background: #fff;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  cursor: pointer;
  font-size: 11.5px;
  color: #475569;
  white-space: nowrap;
}
.chip-mini:hover { background: #f1f5f9; }
.chip-mini.fav-toggle.on {
  background: #fef3c7;
  border-color: #fbbf24;
  color: #92400e;
  font-weight: 600;
}
.chip-mini.clear-filters {
  background: #fee2e2;
  border-color: #fca5a5;
  color: #991b1b;
}

/* 검색 박스 */
.search-box { position: relative; flex: 1; min-width: 200px; }
.search-box .vp-search-input { width: 100%; padding: 4px 60px 4px 8px; font-size: 11.5px; }
.match-count {
  position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
  font-size: 11px; color: #64748b; pointer-events: none;
  background: rgba(255,255,255,0.85); padding: 0 4px;
}

/* v94_LIB4: 필터 그룹 */
.filter-group {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
}
.filter-select {
  padding: 4px 8px;
  font-size: 11.5px;
  background: #fff;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  color: #1e293b;
  cursor: pointer;
}
.filter-select:hover { background: #f1f5f9; }
.filter-select:focus { outline: 2px solid #3b82f6; outline-offset: -1px; }

/* v94_LIB4: OS 배지 */
.cmd-os-badge {
  font-size: 9.5px;
  padding: 2px 6px;
  border-radius: 3px;
  font-weight: 600;
  white-space: nowrap;
}
.cmd-os-badge.os-win   { background: #dbeafe; color: #1e40af; border: 1px solid #93c5fd; }
.cmd-os-badge.os-linux { background: #fef3c7; color: #92400e; border: 1px solid #fbbf24; }
.cmd-os-badge.os-cross { background: #d1fae5; color: #065f46; border: 1px solid #6ee7b7; }

/* v94_LIB4: 즐겨찾기 별표 — 우측 정렬 */
.cmd-fav-btn {
  margin-left: auto;
  background: none;
  border: none;
  font-size: 16px;
  cursor: pointer;
  padding: 0 4px;
  color: #cbd5e1;
  line-height: 1;
  transition: transform 0.1s, color 0.15s;
}
.cmd-fav-btn:hover { transform: scale(1.2); color: #fbbf24; }
.cmd-fav-btn.on { color: #f59e0b; }

/* 레이아웃 */
.lib-layout {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 16px;
}

/* 카테고리 사이드 */
.cat-sidebar {
  display: flex;
  flex-direction: column;
  gap: 4px;
  position: sticky;
  top: 16px;
  align-self: start;
}
.cat-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  cursor: pointer;
  text-align: left;
  font-size: 13px;
  color: #1e293b;
  transition: all 0.15s;
}
.cat-btn:hover { background: #f1f5f9; }
.cat-btn.active {
  background: linear-gradient(135deg, #1e293b, #334155);
  color: #fff;
  border-color: #1e293b;
}
.cat-icon { font-size: 16px; }
.cat-label { flex: 1; }
.cat-count {
  font-size: 11px;
  color: #94a3b8;
  background: #f1f5f9;
  padding: 1px 6px;
  border-radius: 10px;
}
.cat-btn.active .cat-count { background: rgba(255,255,255,0.2); color: #fff; }
.cat-divider { height: 1px; background: #e2e8f0; margin: 8px 0; }

/* 명령 카드 */
.cmd-main { display: flex; flex-direction: column; gap: 14px; }
.empty { text-align: center; padding: 40px; color: #64748b; }

.cmd-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  transition: box-shadow 0.15s;
}
.cmd-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.06); }
.cmd-card.cmd-warn { border-left: 3px solid #f59e0b; }
.cmd-card.cmd-danger { border-left: 3px solid #dc2626; background: #fef2f2; }

.cmd-hdr { padding: 12px 14px 10px; border-bottom: 1px solid #f1f5f9; }
.cmd-title-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.cmd-title { margin: 0; font-size: 14px; color: #0f172a; }
.cmd-shell-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 3px;
  letter-spacing: 0.3px;
}
.shell-powershell { background: #1e3a8a; color: #dbeafe; }
.shell-cmd        { background: #44403c; color: #fef3c7; }
.shell-bash       { background: #15803d; color: #dcfce7; }
.shell-sql        { background: #7e22ce; color: #f3e8ff; }
.severity-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 600;
}
.severity-badge.warn { background: #fef3c7; color: #92400e; }
.severity-badge.danger { background: #fee2e2; color: #991b1b; }

.cmd-desc { margin: 6px 0 4px; font-size: 12px; color: #475569; }
.cmd-when { margin: 4px 0 0; font-size: 11px; color: #64748b; font-style: italic; }

.cmd-body { padding: 10px 14px; }
.cmd-block {
  background: #0f172a;
  color: #e2e8f0;
  padding: 10px 12px;
  border-radius: 4px;
  margin: 0;
  font-size: 12px;
  font-family: ui-monospace, 'Consolas', monospace;
  overflow-x: auto;
  white-space: pre;
  line-height: 1.5;
}
.cmd-actions { display: flex; gap: 6px; margin-top: 8px; }
.chip-action {
  padding: 4px 10px;
  background: #fff;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  cursor: pointer;
  font-size: 11px;
  color: #1e293b;
}
.chip-action:hover { background: #f1f5f9; }
.chip-action.runnable { background: #dbeafe; color: #1e40af; border-color: #93c5fd; }

.cmd-expected, .cmd-trouble {
  border-top: 1px solid #f1f5f9;
  padding: 8px 14px;
  font-size: 12px;
}
.cmd-expected summary, .cmd-trouble summary {
  cursor: pointer;
  color: #475569;
  font-weight: 500;
  user-select: none;
}
.cmd-expected pre {
  background: #f8fafc;
  padding: 8px;
  border-radius: 4px;
  margin: 6px 0 0;
  font-size: 11px;
  white-space: pre-wrap;
}
.cmd-trouble :deep(code) {
  background: #fef3c7;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 11px;
}

.cmd-related {
  padding: 6px 14px 10px;
  border-top: 1px solid #f1f5f9;
  font-size: 11px;
}
.related-label { color: #64748b; margin-right: 6px; }
.related-link {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1e40af;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  cursor: pointer;
  margin-right: 4px;
}
.related-link:hover { background: #dbeafe; }

.cmd-output {
  background: #1e293b; color: #e2e8f0;
  padding: 8px; margin: 8px 14px;
  font-size: 11px; border-radius: 4px;
  max-height: 200px; overflow: auto;
}

.print-hint {
  margin-top: 24px;
  padding: 10px 14px;
  background: #f0fdf4;
  border: 1px dashed #86efac;
  border-radius: 6px;
  font-size: 12px;
  color: #166534;
  text-align: center;
}

/* 인쇄 시 최적화 */
@media print {
  .control-bar, .cat-sidebar, .cmd-actions, .print-hint { display: none; }
  .lib-layout { grid-template-columns: 1fr; }
  .cmd-card { page-break-inside: avoid; }
}
</style>
