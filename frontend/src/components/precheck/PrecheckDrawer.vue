<!--
  PrecheckDrawer.vue — v4
  ========================
  변경점 (v3 → v4):
   1. 각 SQL/네트워크/권한 블록을 "아코디언" 으로 변환 (기본 접힘)
   2. 우선순위별로 정렬 후 그룹 표시 (필수 → 권장 → 참고)
   3. 검색 기능: 제목 / 설명 / SQL / 타겟 / 확인명령어 전부 검색
   4. 매칭 시 자동 펼침 + <mark> 하이라이트 + 테두리 강조
   5. 미매칭 항목은 opacity 낮춰서 표시 (맥락 유지)
   6. 체크리스트 탭은 기존 방식 유지 (그 자체가 리스트)

  사용법:
    <PrecheckDrawer v-model="visible" :srcType="..." :tgtType="..." />
-->
<template>
  <transition name="pc-fade">
    <div v-if="modelValue" class="pc-overlay" @click.self="close">
      <transition name="pc-slide" appear>
        <aside v-if="modelValue" class="pc-drawer" role="dialog" aria-label="이관 전 사전점검 가이드">
          <!-- 헤더 -->
          <header class="pc-header">
            <div class="pc-header-main">
              <div class="pc-title">이관 전 사전점검 가이드</div>
              <div class="pc-subtitle">고객사 DBA에게 복사해서 전달하세요</div>
            </div>
            <div class="pc-header-side">
              <span v-if="config" class="pill pill-info">{{ comboLabel }}</span>
              <span v-else class="pill pill-warn">미지원 조합</span>
              <button class="pc-close-btn" @click="close" aria-label="닫기">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8">
                  <line x1="3" y1="3" x2="13" y2="13"/>
                  <line x1="13" y1="3" x2="3" y2="13"/>
                </svg>
              </button>
            </div>
          </header>

          <!-- 빈 상태 -->
          <div v-if="!config" class="pc-empty">
            <div class="pc-empty-icon">
              <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.2">
                <circle cx="24" cy="24" r="20"/>
                <line x1="24" y1="14" x2="24" y2="26"/>
                <circle cx="24" cy="32" r="1.5" fill="currentColor"/>
              </svg>
            </div>
            <div class="pc-empty-msg">{{ emptyMessage }}</div>
            <button class="btn btn-primary" @click="close">닫기</button>
          </div>

          <template v-else>
            <!-- ★ 검색바 + 정렬/우선순위 안내 -->
            <div v-if="activeTab !== 'checklist'" class="pc-searchbar">
              <div class="pc-search-input-wrap">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" class="pc-search-ic">
                  <circle cx="7" cy="7" r="5"/>
                  <line x1="11" y1="11" x2="14" y2="14"/>
                </svg>
                <input
                  type="text"
                  v-model="searchQuery"
                  placeholder="제목, SQL, 설명에서 검색... (예: timeout, 권한, collation)"
                  class="pc-search-input"
                  @keydown.escape="searchQuery=''"
                />
                <span v-if="searchQuery" class="pc-search-count">
                  {{ currentTabMatchCount }}건 매칭
                </span>
                <button v-if="searchQuery" class="pc-search-clear" @click="searchQuery=''" title="검색 지우기">
                  <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8">
                    <line x1="3" y1="3" x2="9" y2="9"/>
                    <line x1="9" y1="3" x2="3" y2="9"/>
                  </svg>
                </button>
              </div>
              <!-- 우선순위 요약 + 전체 펼침/접기 -->
              <div class="pc-searchbar-footer">
                <div class="pc-priority-summary">
                  <span class="pc-ps-item"><span class="pc-ps-dot" style="background:#E24B4A"></span>필수 {{ countByPrio.critical }}</span>
                  <span class="pc-ps-item"><span class="pc-ps-dot" style="background:#EF9F27"></span>권장 {{ countByPrio.warning }}</span>
                  <span class="pc-ps-item"><span class="pc-ps-dot" style="background:#378add"></span>참고 {{ countByPrio.info }}</span>
                </div>
                <div class="pc-expand-controls">
                  <button class="act-btn" @click="expandAll">모두 펼침</button>
                  <button class="act-btn" @click="collapseAll">모두 접기</button>
                </div>
              </div>
            </div>

            <!-- 탭 -->
            <nav class="pc-tabs" role="tablist">
              <button
                v-for="t in tabs"
                :key="t.key"
                class="pc-tab"
                :class="{ active: activeTab === t.key }"
                role="tab"
                :aria-selected="activeTab === t.key"
                @click="activeTab = t.key"
              >
                {{ t.label }}
                <span v-if="t.key === 'checklist' && totalChecklistCount > 0" class="pc-tab-badge">
                  {{ checkedCount }}/{{ totalChecklistCount }}
                </span>
                <span v-else-if="searchQuery && tabMatchCounts[t.key] !== undefined" class="pc-tab-badge match">
                  {{ tabMatchCounts[t.key] }}
                </span>
              </button>
            </nav>

            <div class="pc-body">
              <!-- 탭 1: DBA SQL -->
              <div v-show="activeTab==='sql'" class="pc-tab-content">
                <AccordionGroup
                  v-for="g in sqlGrouped"
                  :key="'sql-'+g.priority"
                  :group="g"
                  :search-query="searchQuery"
                  :expanded-set="expandedSet"
                  @toggle="toggleItem"
                  content-type="sql"
                />
                <div v-if="searchQuery && currentTabMatchCount === 0" class="pc-no-match">
                  "{{ searchQuery }}" 에 매칭되는 항목이 없습니다
                </div>
              </div>

              <!-- 탭 2: 네트워크 -->
              <div v-show="activeTab==='network'" class="pc-tab-content">
                <AccordionGroup
                  v-for="g in networkGrouped"
                  :key="'net-'+g.priority"
                  :group="g"
                  :search-query="searchQuery"
                  :expanded-set="expandedSet"
                  @toggle="toggleItem"
                  content-type="network"
                />
                <div v-if="!config.networkChecks.length" class="pc-empty-sub">
                  이 조합의 네트워크 체크 항목이 아직 등록되지 않았습니다
                </div>
                <div v-else-if="searchQuery && currentTabMatchCount === 0" class="pc-no-match">
                  "{{ searchQuery }}" 에 매칭되는 항목이 없습니다
                </div>
              </div>

              <!-- 탭 3: 권한 -->
              <div v-show="activeTab==='permission'" class="pc-tab-content">
                <AccordionGroup
                  v-for="g in permissionGrouped"
                  :key="'perm-'+g.priority"
                  :group="g"
                  :search-query="searchQuery"
                  :expanded-set="expandedSet"
                  @toggle="toggleItem"
                  content-type="permission"
                />
                <div v-if="!config.permissionChecks.length" class="pc-empty-sub">
                  권한 체크 항목이 아직 등록되지 않았습니다
                </div>
                <div v-else-if="searchQuery && currentTabMatchCount === 0" class="pc-no-match">
                  "{{ searchQuery }}" 에 매칭되는 항목이 없습니다
                </div>
              </div>

              <!-- 탭 4: 방문 체크리스트 (아코디언 아님, 기존 리스트) -->
              <div v-show="activeTab==='checklist'" class="pc-tab-content">
                <!-- 체크리스트 탭에서도 검색바 -->
                <div class="pc-cl-searchbar">
                  <div class="pc-search-input-wrap">
                    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" class="pc-search-ic">
                      <circle cx="7" cy="7" r="5"/>
                      <line x1="11" y1="11" x2="14" y2="14"/>
                    </svg>
                    <input
                      type="text"
                      v-model="checklistSearch"
                      placeholder="체크리스트 검색..."
                      class="pc-search-input"
                      @keydown.escape="checklistSearch=''"
                    />
                    <button v-if="checklistSearch" class="pc-search-clear" @click="checklistSearch=''">
                      <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8">
                        <line x1="3" y1="3" x2="9" y2="9"/>
                        <line x1="9" y1="3" x2="3" y2="9"/>
                      </svg>
                    </button>
                  </div>
                </div>

                <!-- 진행률 -->
                <div class="pc-progress-wrap">
                  <div class="pc-progress-info">
                    <span>진행률: <strong>{{ checkedCount }}</strong> / {{ totalChecklistCount }} ({{ checklistPercent }}%)</span>
                    <button class="act-btn" @click="resetChecklist">모두 해제</button>
                  </div>
                  <div class="pc-progress-bar">
                    <div class="pc-progress-fill" :style="{width:checklistPercent+'%'}"></div>
                  </div>
                </div>

                <!-- 체크리스트 (필수 먼저 + 검색 필터) -->
                <div
                  v-for="group in checklistFiltered"
                  :key="group.category"
                  class="pc-cl-group"
                >
                  <div class="pc-cl-cat">{{ group.category }}</div>
                  <label
                    v-for="item in group.items"
                    :key="item.key"
                    class="pc-cl-item"
                    :class="{ checked: isChecked(item.key), critical: item.critical }"
                  >
                    <input
                      type="checkbox"
                      :checked="isChecked(item.key)"
                      @change="toggleCheck(item.key)"
                    />
                    <span class="pc-cl-mark"></span>
                    <span class="pc-cl-text" v-html="highlightText(item.text, checklistSearch)"></span>
                    <span v-if="item.critical" class="pill pill-err pc-cl-req">필수</span>
                  </label>
                </div>
                <div v-if="checklistSearch && checklistFiltered.length === 0" class="pc-no-match">
                  "{{ checklistSearch }}" 에 매칭되는 항목이 없습니다
                </div>
              </div>
            </div>

            <!-- 푸터 -->
            <footer class="pc-footer">
              <div class="pc-footer-info">{{ summary }}</div>
              <div class="pc-footer-actions">
                <button class="btn" @click="copyAllSQL" title="모든 SQL 을 주석 포함하여 한 번에 복사">
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:12px;height:12px">
                    <rect x="4" y="4" width="9" height="10" rx="1"/>
                    <path d="M10 2H4a1 1 0 0 0-1 1v9"/>
                  </svg>
                  SQL 전체 복사
                </button>
                <button class="btn btn-primary" @click="exportAsText" title="사전점검 가이드를 텍스트 파일로 저장">
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:12px;height:12px">
                    <path d="M8 2v9"/>
                    <polyline points="4,7 8,11 12,7"/>
                    <line x1="2" y1="14" x2="14" y2="14"/>
                  </svg>
                  텍스트로 내보내기
                </button>
              </div>
            </footer>
          </template>
        </aside>
      </transition>
    </div>
  </transition>
</template>

<script setup>
import { ref, computed, watch, onMounted, h } from 'vue'
import { useAppStore } from '@/store/appStore.js'
import CodeBlock from './PrecheckCodeBlock.vue'
import { getPrecheckConfig } from './precheckData.js'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  srcType:    { type: String,  default: '' },
  tgtType:    { type: String,  default: '' },
})
const emit = defineEmits(['update:modelValue'])
const app  = useAppStore()

// ─── 탭 ─────────────────────────────────
const tabs = [
  { key: 'sql',        label: 'DBA 실행용 SQL' },
  { key: 'network',    label: '네트워크 체크' },
  { key: 'permission', label: '권한 체크' },
  { key: 'checklist',  label: '방문 체크리스트' },
]
const activeTab = ref('sql')

// ─── 설정 ────────────────────────────────
const config = computed(() => getPrecheckConfig(props.srcType, props.tgtType))
const comboLabel = computed(() => {
  if (!props.srcType || !props.tgtType) return ''
  return `${props.srcType.toUpperCase()} → ${props.tgtType.toUpperCase()}`
})
const emptyMessage = computed(() => {
  if (!props.srcType || !props.tgtType)
    return '소스 DB와 타겟 DB를 먼저 선택해주세요'
  return `${comboLabel.value} 조합의 사전점검 데이터가 아직 준비되지 않았습니다`
})

// ─── 검색 상태 ───────────────────────────
const searchQuery = ref('')
const checklistSearch = ref('')

// ─── 아코디언 펼침 상태 (Set) ─────────────
// key 포맷: `${tab}::${id}` (예: "sql::mysql-local-infile")
const expandedSet = ref(new Set())

function toggleItem(key) {
  const s = new Set(expandedSet.value)
  if (s.has(key)) s.delete(key); else s.add(key)
  expandedSet.value = s
}

function expandAll() {
  const s = new Set()
  if (!config.value) return
  const prefix = activeTab.value
  const list = getListForTab(activeTab.value)
  list.forEach(item => s.add(`${prefix}::${item.id}`))
  expandedSet.value = s
}
function collapseAll() {
  // 현재 탭만 접기
  const prefix = activeTab.value + '::'
  const s = new Set(expandedSet.value)
  ;[...s].forEach(k => { if (k.startsWith(prefix)) s.delete(k) })
  expandedSet.value = s
}

function getListForTab(tab) {
  if (!config.value) return []
  if (tab === 'sql')        return config.value.sqlBlocks
  if (tab === 'network')    return config.value.networkChecks
  if (tab === 'permission') return config.value.permissionChecks
  return []
}

// ─── 검색 매칭 ───────────────────────────
const q = computed(() => (searchQuery.value || '').trim().toLowerCase())

function matchesQuery(item, tab) {
  if (!q.value) return true
  const fields = []
  fields.push(item.title || '')
  fields.push(item.description || '')
  fields.push(item.target || '')
  if (tab === 'sql' || tab === 'permission') {
    fields.push(item.sql || '')
    if (item.followUp) {
      fields.push(item.followUp.condition || '')
      fields.push(item.followUp.note || '')
      fields.push(item.followUp.sql || '')
      if (item.followUp.permanent) fields.push(item.followUp.permanent.sql || '')
    }
  }
  if (tab === 'network') {
    fields.push(item.command || '')
    fields.push(item.expected || '')
  }
  const haystack = fields.join('\n').toLowerCase()
  return haystack.includes(q.value)
}

// ─── 우선순위 그룹화 (필수 → 권장 → 참고) ──
const PRIORITY_ORDER = ['critical', 'warning', 'info']
const PRIORITY_META = {
  critical: { label: '필수', color: '#E24B4A', order: 0 },
  warning:  { label: '권장', color: '#EF9F27', order: 1 },
  info:     { label: '참고', color: '#378add', order: 2 },
}
const NETWORK_DEFAULT_PRIO  = 'info'  // 네트워크는 우선순위 없으므로 기본 info
const PERMISSION_DEFAULT_PRIO = 'info'

function groupByPriority(list, tab, defaultPrio = 'info') {
  const buckets = { critical: [], warning: [], info: [] }
  list.forEach((item, idx) => {
    const p = (item.priority || defaultPrio).toLowerCase()
    const prio = PRIORITY_ORDER.includes(p) ? p : defaultPrio
    // 원본 순서 보존용 idx 저장
    buckets[prio].push({ ...item, _origIndex: idx + 1, _tab: tab, _key: `${tab}::${item.id}` })
  })
  return PRIORITY_ORDER
    .map(p => ({
      priority: p,
      meta: PRIORITY_META[p],
      items: buckets[p],
      matchCount: buckets[p].filter(it => matchesQuery(it, tab)).length,
    }))
    .filter(g => g.items.length > 0)
}

const sqlGrouped        = computed(() => config.value ? groupByPriority(config.value.sqlBlocks,        'sql')                    : [])
const networkGrouped    = computed(() => config.value ? groupByPriority(config.value.networkChecks,    'network',    NETWORK_DEFAULT_PRIO)    : [])
const permissionGrouped = computed(() => config.value ? groupByPriority(config.value.permissionChecks, 'permission', PERMISSION_DEFAULT_PRIO) : [])

// 탭별 매칭 건수
const tabMatchCounts = computed(() => {
  const r = {}
  if (!config.value) return r
  if (q.value) {
    r.sql        = config.value.sqlBlocks.filter(it => matchesQuery(it, 'sql')).length
    r.network    = config.value.networkChecks.filter(it => matchesQuery(it, 'network')).length
    r.permission = config.value.permissionChecks.filter(it => matchesQuery(it, 'permission')).length
  }
  return r
})

const currentTabMatchCount = computed(() => tabMatchCounts.value[activeTab.value] ?? 0)

// ─── 검색 변경 시 매칭 항목 자동 펼침 ─────
watch(searchQuery, (newQ) => {
  if (!newQ || !config.value) return
  const tab = activeTab.value
  if (tab === 'checklist') return
  const list = getListForTab(tab)
  const s = new Set(expandedSet.value)
  list.forEach(item => {
    if (matchesQuery(item, tab)) {
      s.add(`${tab}::${item.id}`)
    }
  })
  expandedSet.value = s
})

// 탭 전환 시 검색어 유지 (그대로 둠)

// ─── 우선순위 요약 카운트 ────────────────
const countByPrio = computed(() => {
  const list = getListForTab(activeTab.value)
  const r = { critical: 0, warning: 0, info: 0 }
  list.forEach(it => {
    const p = (it.priority || (activeTab.value === 'sql' ? 'info' : 'info')).toLowerCase()
    if (r[p] !== undefined) r[p]++
  })
  return r
})

// ─── 체크리스트 (기존 로직 유지 + 필수 먼저 + 검색) ───
const STORAGE_KEY = computed(() => `databridge_precheck_${props.srcType}_${props.tgtType}`)
const checkedSet  = ref(new Set())

function isChecked(k) { return checkedSet.value.has(k) }
function toggleCheck(k) {
  const s = new Set(checkedSet.value)
  if (s.has(k)) s.delete(k); else s.add(k)
  checkedSet.value = s
  saveChecklist()
}
function resetChecklist() {
  checkedSet.value = new Set()
  saveChecklist()
}
function loadChecklist() {
  try {
    const v = localStorage.getItem(STORAGE_KEY.value)
    checkedSet.value = v ? new Set(JSON.parse(v)) : new Set()
  } catch { checkedSet.value = new Set() }
}
function saveChecklist() {
  try {
    localStorage.setItem(STORAGE_KEY.value, JSON.stringify([...checkedSet.value]))
  } catch {}
}

watch(() => props.modelValue, v => { if (v && config.value) loadChecklist() })
watch(() => STORAGE_KEY.value, () => { if (props.modelValue) loadChecklist() })

const checklistByCategory = computed(() => {
  if (!config.value) return []
  const map = {}
  config.value.visitChecklist.forEach((item, idx) => {
    const key = `${item.category}__${idx}`
    if (!map[item.category]) map[item.category] = { category: item.category, items: [] }
    map[item.category].items.push({ ...item, key })
  })
  // 각 카테고리 내에서 critical 먼저 정렬
  Object.values(map).forEach(group => {
    group.items.sort((a, b) => {
      if (a.critical === b.critical) return 0
      return a.critical ? -1 : 1
    })
  })
  return Object.values(map)
})

const checklistFiltered = computed(() => {
  const q = (checklistSearch.value || '').trim().toLowerCase()
  if (!q) return checklistByCategory.value
  return checklistByCategory.value
    .map(g => ({
      ...g,
      items: g.items.filter(it =>
        it.text.toLowerCase().includes(q) ||
        g.category.toLowerCase().includes(q)
      )
    }))
    .filter(g => g.items.length > 0)
})

const totalChecklistCount = computed(() => config.value?.visitChecklist.length || 0)
const checkedCount        = computed(() => checkedSet.value.size)
const checklistPercent    = computed(() => {
  if (!totalChecklistCount.value) return 0
  return Math.round((checkedCount.value / totalChecklistCount.value) * 100)
})

// ─── 요약 문구 ──────────────────────────
const summary = computed(() => {
  if (!config.value) return ''
  const c = config.value
  return `SQL ${c.sqlBlocks.length}개 · 네트워크 ${c.networkChecks.length}개 · 권한 ${c.permissionChecks.length}개 · 체크리스트 ${c.visitChecklist.length}개`
})

function close() { emit('update:modelValue', false) }

function onCopied() {
  app?.notify && app.notify('복사됨', 'success')
}

// ─── 하이라이트 (XSS 안전 — 텍스트만 대상) ──
function highlightText(text, query) {
  if (!text) return ''
  const escapeHtml = s => s
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;')
  const q = (query || '').trim()
  if (!q) return escapeHtml(text)
  const escaped = escapeHtml(text)
  // 정규식 특수문자 이스케이프
  const pattern = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const re = new RegExp(pattern, 'gi')
  return escaped.replace(re, m => `<mark class="pc-hl">${m}</mark>`)
}

// ─── 복사/내보내기 (기존 로직 그대로) ──────
async function copyAllSQL() {
  if (!config.value) return
  let t = `-- DataBridge 이관 사전점검 SQL (${comboLabel.value})\n`
  t += `-- Generated: ${new Date().toISOString()}\n\n`
  config.value.sqlBlocks.forEach((b, i) => {
    t += `-- ${i+1}. ${b.title} [${PRIORITY_META[b.priority]?.label || ''}]\n`
    if (b.description) t += `-- ${b.description}\n`
    t += `${b.sql}\n\n`
    if (b.followUp) {
      t += `-- └─ ${b.followUp.condition}\n${b.followUp.sql}\n\n`
      if (b.followUp.permanent) {
        t += `-- └─ ${b.followUp.permanent.note}\n${b.followUp.permanent.sql}\n\n`
      }
    }
    t += '\n'
  })
  await copyToClipboard(t, `${config.value.sqlBlocks.length}개 SQL 블록 복사됨`)
}

async function copyToClipboard(text, successMsg) {
  const doFallback = () => {
    const ta = document.createElement('textarea')
    ta.value = text; ta.style.position='fixed'; ta.style.left='-9999px'
    document.body.appendChild(ta); ta.select()
    try { document.execCommand('copy') } finally { document.body.removeChild(ta) }
  }
  try {
    if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text)
    else doFallback()
    app?.notify && app.notify(successMsg, 'success')
  } catch {
    try { doFallback(); app?.notify && app.notify(successMsg, 'success') }
    catch { app?.notify && app.notify('복사 실패', 'error') }
  }
}

function exportAsText() {
  if (!config.value) return
  let t = '========================================\n'
  t += 'DataBridge 이관 사전점검 가이드\n'
  t += `${comboLabel.value}\n`
  t += `Generated: ${new Date().toLocaleString()}\n`
  t += '========================================\n\n'

  t += '[1] DBA 실행용 SQL\n' + '─'.repeat(40) + '\n\n'
  config.value.sqlBlocks.forEach((b, i) => {
    t += `${i+1}. ${b.title} [${PRIORITY_META[b.priority]?.label || ''}] — ${b.target}\n`
    if (b.description) t += `   ${b.description}\n`
    t += `\n${b.sql}\n\n`
    if (b.followUp) t += `   └ ${b.followUp.condition}\n\n${b.followUp.sql}\n\n`
    t += '\n'
  })

  if (config.value.networkChecks.length) {
    t += '[2] 네트워크 체크\n' + '─'.repeat(40) + '\n\n'
    config.value.networkChecks.forEach((c, i) => {
      t += `${i+1}. ${c.title}\n`
      if (c.description) t += `   ${c.description}\n`
      t += `\n${c.command}\n`
      if (c.expected) t += `\n   기대 결과: ${c.expected}\n\n`
      t += '\n'
    })
  }

  if (config.value.permissionChecks.length) {
    t += '[3] 권한 체크\n' + '─'.repeat(40) + '\n\n'
    config.value.permissionChecks.forEach((c, i) => {
      t += `${i+1}. ${c.title} — ${c.target}\n`
      if (c.description) t += `   ${c.description}\n`
      t += `\n${c.sql}\n\n`
    })
  }

  t += '[4] 방문 체크리스트\n' + '─'.repeat(40) + '\n\n'
  const grouped = {}
  config.value.visitChecklist.forEach((item, idx) => {
    const key = `${item.category}__${idx}`
    if (!grouped[item.category]) grouped[item.category] = []
    grouped[item.category].push({ ...item, key, checked: checkedSet.value.has(key) })
  })
  Object.entries(grouped).forEach(([cat, items]) => {
    t += `<${cat}>\n`
    items.forEach(it => {
      const mark = it.checked ? '[v]' : '[ ]'
      const req  = it.critical ? ' (필수)' : ''
      t += `  ${mark} ${it.text}${req}\n`
    })
    t += '\n'
  })

  const blob = new Blob([t], { type: 'text/plain;charset=utf-8' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href = url
  const d = new Date().toISOString().slice(0,10)
  a.download = `databridge_precheck_${props.srcType}_to_${props.tgtType}_${d}.txt`
  document.body.appendChild(a); a.click(); document.body.removeChild(a)
  URL.revokeObjectURL(url)
  app?.notify && app.notify('텍스트 파일 다운로드 시작됨', 'success')
}

onMounted(() => { if (props.modelValue && config.value) loadChecklist() })

// ─── AccordionGroup 컴포넌트 (inline, render function) ───
// v-for 반복에서 깊게 중첩되면 복잡해지므로 단일 파일 내 inline 컴포넌트로 처리
// → 별도 파일 분리 가능하지만 사용자 요청은 기능이라 여기에 유지
const AccordionGroup = {
  props: {
    group: { type: Object, required: true },
    searchQuery: { type: String, default: '' },
    expandedSet: { type: Object, required: true },  // Set
    contentType: { type: String, required: true },  // 'sql' | 'network' | 'permission'
  },
  emits: ['toggle'],
  setup(props, { emit }) {
    const q = computed(() => (props.searchQuery || '').trim().toLowerCase())

    function matches(item) {
      if (!q.value) return true
      const fields = [
        item.title || '', item.description || '', item.target || ''
      ]
      if (props.contentType === 'sql' || props.contentType === 'permission') {
        fields.push(item.sql || '')
        if (item.followUp) {
          fields.push(item.followUp.condition || '', item.followUp.note || '', item.followUp.sql || '')
          if (item.followUp.permanent) fields.push(item.followUp.permanent.sql || '')
        }
      }
      if (props.contentType === 'network') {
        fields.push(item.command || '', item.expected || '')
      }
      return fields.join('\n').toLowerCase().includes(q.value)
    }

    function hl(text) {
      return highlightText(text, q.value)
    }

    return () => {
      const g = props.group
      // 검색 중인데 매칭이 0이면 그룹 헤더만 흐리게
      const anyMatch = !q.value || g.matchCount > 0

      return h('div', { class: 'pc-prio-group' }, [
        // 우선순위 헤더
        h('div', { class: ['pc-prio-header', { dim: !anyMatch }] }, [
          h('span', { class: 'pc-prio-dot', style: { background: g.meta.color } }),
          h('span', { class: 'pc-prio-label', style: { color: g.meta.color } },
            `${g.meta.label} · ${q.value ? `${g.matchCount}건 매칭 / ` : ''}${g.items.length}개`
          ),
        ]),
        // 아이템 리스트
        ...g.items.map(item => {
          const isMatch = matches(item)
          const isExpanded = props.expandedSet.has(item._key)
          const dim = q.value && !isMatch

          return h('div', {
            class: ['pc-acc-item', {
              'is-expanded': isExpanded,
              'is-match': q.value && isMatch,
              'is-dim': dim,
            }],
          }, [
            // 헤더 (클릭 토글)
            h('div', {
              class: 'pc-acc-header',
              onClick: () => emit('toggle', item._key),
            }, [
              h('svg', {
                viewBox: '0 0 12 12', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.6',
                class: ['pc-acc-chevron', { 'is-open': isExpanded }],
              }, [ h('polyline', { points: '3,2 9,6 3,10' }) ]),
              h('span', {
                class: ['pc-prio-badge', 'priority-'+g.priority],
              }, String(item._origIndex)),
              h('div', {
                class: 'pc-acc-title',
                innerHTML: hl(item.title || ''),
              }),
              item.target
                ? h('div', { class: 'pc-acc-target', innerHTML: hl(item.target) })
                : null,
            ]),
            // 본문 (펼쳤을 때만 렌더 — 성능 + 폰트 로드 후 정상 렌더)
            isExpanded
              ? h('div', { class: 'pc-acc-body' }, [
                  item.description
                    ? h('div', { class: 'pc-acc-desc', innerHTML: hl(item.description) })
                    : null,
                  // SQL 또는 command 메인 블록
                  h(CodeBlock, {
                    code: item.sql || item.command || '',
                    label: item.target || (props.contentType === 'network' ? '이관 서버에서 실행' : ''),
                    lang: props.contentType === 'network' ? 'powershell' : 'sql',
                    searchHighlight: q.value,
                    onCopied,
                  }),
                  // expected (네트워크 체크 전용)
                  item.expected
                    ? h('div', { class: 'pc-acc-expected' }, [
                        h('svg', {
                          viewBox: '0 0 16 16', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.6',
                          class: 'pc-acc-expected-ic',
                        }, [
                          h('circle', { cx: '8', cy: '8', r: '7' }),
                          h('polyline', { points: '5,8 7,10 11,6' }),
                        ]),
                        h('span', { innerHTML: '기대 결과: ' + hl(item.expected) }),
                      ])
                    : null,
                  // follow-up
                  item.followUp
                    ? h('div', { class: 'pc-followup' }, [
                        h('div', { class: 'pc-followup-header' }, [
                          h('svg', {
                            viewBox: '0 0 16 16', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.6',
                            class: 'pc-followup-icon',
                          }, [
                            h('path', { d: 'M8 1 L15 14 L1 14 Z' }),
                            h('line', { x1: '8', y1: '6', x2: '8', y2: '10' }),
                            h('circle', { cx: '8', cy: '12', r: '0.8', fill: 'currentColor' }),
                          ]),
                          h('span', { innerHTML: hl(item.followUp.condition || '') }),
                        ]),
                        item.followUp.note
                          ? h('div', { class: 'pc-followup-note', innerHTML: hl(item.followUp.note) })
                          : null,
                        h(CodeBlock, {
                          code: item.followUp.sql,
                          searchHighlight: q.value,
                          onCopied,
                        }),
                        item.followUp.permanent
                          ? [
                              h('div', { class: 'pc-followup-note pc-followup-note-perm',
                                innerHTML: hl(item.followUp.permanent.note || '') }),
                              h(CodeBlock, {
                                code: item.followUp.permanent.sql,
                                lang: 'ini',
                                searchHighlight: q.value,
                                onCopied,
                              })
                            ]
                          : null,
                      ])
                    : null,
                ])
              : null,
          ])
        }),
      ])
    }
  }
}
</script>

<style scoped>
/* ─── 오버레이 & 드로어 ─────────────────── */
.pc-overlay{
  position:fixed; inset:0;
  background:rgba(0,0,0,.38);
  z-index:1100;
  display:flex; justify-content:flex-end;
}
.pc-drawer{
  width:min(820px, 72vw);
  height:100vh;
  background:var(--bg-primary);
  border-left:0.5px solid var(--border-mid);
  display:flex; flex-direction:column;
  font-family:var(--font);
  color:var(--text-primary);
}
@media (max-width: 900px){ .pc-drawer{ width:92vw } }

.pc-fade-enter-active,
.pc-fade-leave-active{ transition:opacity .2s ease }
.pc-fade-enter-from,
.pc-fade-leave-to{ opacity:0 }
.pc-slide-enter-active,
.pc-slide-leave-active{ transition:transform .26s cubic-bezier(.2,.8,.2,1) }
.pc-slide-enter-from,
.pc-slide-leave-to{ transform:translateX(100%) }

/* ─── 헤더 ────────────────────────────── */
.pc-header{
  display:flex; justify-content:space-between; align-items:center;
  padding:14px 20px;
  border-bottom:0.5px solid var(--border-light);
  flex-shrink:0;
}
.pc-title{ font-size:15px; font-weight:600; color:var(--text-primary) }
.pc-subtitle{ font-size:11.5px; color:var(--text-tertiary); margin-top:3px }
.pc-header-side{ display:flex; align-items:center; gap:10px }
.pill.pill-info{ background:var(--bg-info); color:var(--text-info); font-weight:500; font-size:10.5px }
.pc-close-btn{
  background:transparent; border:none; cursor:pointer;
  padding:4px; border-radius:var(--radius-sm);
  color:var(--text-tertiary); transition:all .12s;
}
.pc-close-btn:hover{ background:var(--bg-secondary); color:var(--text-primary) }
.pc-close-btn svg{ width:14px; height:14px }

/* ─── 검색바 ─────────────────────────── */
.pc-searchbar, .pc-cl-searchbar{
  padding:10px 20px;
  background:var(--bg-secondary);
  border-bottom:0.5px solid var(--border-light);
  flex-shrink:0;
}
.pc-cl-searchbar{ margin-bottom:12px; margin:0 -20px 14px; padding:0 20px 10px; border-bottom:0.5px solid var(--border-light); background:transparent }
.pc-search-input-wrap{ position:relative }
.pc-search-ic{
  position:absolute; left:10px; top:50%; transform:translateY(-50%);
  width:13px; height:13px; color:var(--text-tertiary);
}
.pc-search-input{
  width:100%; box-sizing:border-box;
  padding:7px 80px 7px 30px;
  font-size:12.5px;
  border:0.5px solid var(--border-mid);
  border-radius:var(--radius-md);
  background:var(--bg-primary);
  color:var(--text-primary);
  font-family:var(--font);
}
.pc-search-input:focus{
  outline:none;
  border-color:var(--accent-blue);
  box-shadow:0 0 0 3px var(--bg-info);
}
.pc-search-count{
  position:absolute; right:34px; top:50%; transform:translateY(-50%);
  font-size:10.5px; color:var(--text-tertiary);
  pointer-events:none;
}
.pc-search-clear{
  position:absolute; right:8px; top:50%; transform:translateY(-50%);
  background:transparent; border:none; cursor:pointer;
  width:20px; height:20px; padding:0;
  display:flex; align-items:center; justify-content:center;
  color:var(--text-tertiary);
  border-radius:4px;
}
.pc-search-clear:hover{ background:var(--bg-tertiary); color:var(--text-primary) }
.pc-search-clear svg{ width:10px; height:10px }

.pc-searchbar-footer{
  display:flex; justify-content:space-between; align-items:center;
  margin-top:8px; gap:10px;
}
.pc-priority-summary{
  display:flex; align-items:center; gap:12px;
  font-size:11px; color:var(--text-tertiary);
}
.pc-ps-item{ display:inline-flex; align-items:center; gap:5px }
.pc-ps-dot{ width:7px; height:7px; border-radius:50% }
.pc-expand-controls{ display:flex; gap:6px }
.pc-expand-controls .act-btn{ font-size:10.5px; padding:2px 8px }

/* ─── 탭 ──────────────────────────────── */
.pc-tabs{
  display:flex;
  border-bottom:0.5px solid var(--border-light);
  background:var(--bg-secondary);
  flex-shrink:0; overflow-x:auto;
}
.pc-tab{
  padding:10px 16px;
  background:transparent; border:none;
  border-bottom:2px solid transparent;
  font-size:12.5px; font-weight:500;
  font-family:var(--font);
  color:var(--text-tertiary);
  cursor:pointer; white-space:nowrap;
  transition:all .15s;
  display:inline-flex; align-items:center; gap:6px;
}
.pc-tab:hover{ color:var(--text-secondary) }
.pc-tab.active{
  color:var(--text-primary);
  border-bottom-color:var(--accent-blue);
  background:var(--bg-primary);
}
.pc-tab-badge{
  font-size:10px; padding:1px 6px; border-radius:8px;
  background:var(--bg-info); color:var(--text-info); font-weight:500;
}
.pc-tab-badge.match{
  background:var(--bg-warning); color:var(--text-warning);
}

/* ─── 본문 ────────────────────────────── */
.pc-body{ flex:1; overflow-y:auto; padding:14px 20px }
.pc-tab-content{ animation: pc-fadeIn .22s ease }
@keyframes pc-fadeIn{ from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:translateY(0)} }

/* ─── 우선순위 그룹 헤더 ───────────────── */
:deep(.pc-prio-group){ margin-bottom:18px }
:deep(.pc-prio-header){
  display:flex; align-items:center; gap:8px;
  margin:4px 0 10px; padding:4px 4px;
  transition:opacity .15s;
}
:deep(.pc-prio-header.dim){ opacity:0.35 }
:deep(.pc-prio-dot){ width:9px; height:9px; border-radius:50% }
:deep(.pc-prio-label){
  font-size:10.5px; font-weight:600;
  text-transform:uppercase; letter-spacing:.5px;
}

/* ─── 아코디언 아이템 ─────────────────── */
:deep(.pc-acc-item){
  border:0.5px solid var(--border-light);
  border-radius:var(--radius-md);
  margin-bottom:5px;
  overflow:hidden;
  transition: border-color .15s, opacity .15s, background .15s;
}
:deep(.pc-acc-item.is-expanded){
  border-color:var(--border-mid);
}
:deep(.pc-acc-item.is-match){
  border-color:var(--accent-blue);
  background:rgba(55,138,221,.04);
}
:deep(.pc-acc-item.is-dim){ opacity:0.4 }
:deep(.pc-acc-header){
  padding:9px 12px;
  display:flex; align-items:center; gap:10px;
  cursor:pointer;
  user-select:none;
}
:deep(.pc-acc-header:hover){ background:var(--bg-secondary) }
:deep(.pc-acc-item.is-expanded .pc-acc-header){
  background:var(--bg-secondary);
  border-bottom:0.5px solid var(--border-light);
}
:deep(.pc-acc-chevron){
  width:9px; height:9px; flex-shrink:0;
  color:var(--text-tertiary);
  transition:transform .2s;
}
:deep(.pc-acc-chevron.is-open){ transform:rotate(90deg) }
:deep(.pc-prio-badge){
  display:inline-flex; align-items:center; justify-content:center;
  width:22px; height:22px; border-radius:50%;
  font-size:10.5px; font-weight:600;
  flex-shrink:0;
}
:deep(.pc-prio-badge.priority-critical){ background:var(--bg-danger);  color:var(--text-danger) }
:deep(.pc-prio-badge.priority-warning) { background:var(--bg-warning); color:var(--text-warning) }
:deep(.pc-prio-badge.priority-info)    { background:var(--bg-info);    color:var(--text-info) }

:deep(.pc-acc-title){
  flex:1; font-size:13px; color:var(--text-primary);
  line-height:1.4; font-weight:500;
}
:deep(.pc-acc-target){
  font-size:10.5px; color:var(--text-tertiary);
  white-space:nowrap; flex-shrink:0;
}
:deep(.pc-acc-body){
  padding:12px 14px 14px;
  background:var(--bg-primary);
  animation: pc-accBody .22s ease;
}
@keyframes pc-accBody{ from{opacity:0;transform:translateY(-4px)} to{opacity:1;transform:translateY(0)} }
:deep(.pc-acc-desc){
  font-size:12px; color:var(--text-secondary);
  line-height:1.5; margin-bottom:8px;
}
:deep(.pc-acc-expected){
  display:flex; align-items:center; gap:6px;
  font-size:11.5px; color:var(--text-success);
  margin-top:8px;
  padding:7px 11px;
  background:var(--bg-success);
  border-radius:var(--radius-md);
}
:deep(.pc-acc-expected-ic){ width:12px; height:12px; flex-shrink:0 }

/* 하이라이트 */
:deep(.pc-hl){
  background:rgba(239,159,39,.35);
  color:inherit;
  padding:0 2px; border-radius:2px;
  font-weight:500;
}

/* follow-up */
:deep(.pc-followup){
  margin:10px 0 0;
  padding:10px 12px;
  background:var(--bg-warning);
  border-left:3px solid var(--text-warning);
  border-radius:var(--radius-md);
}
:deep(.pc-followup-header){
  display:flex; align-items:center; gap:6px;
  font-size:11.5px;
  color:var(--text-warning);
  font-weight:500;
  margin-bottom:5px;
}
:deep(.pc-followup-icon){ width:12px; height:12px }
:deep(.pc-followup-note){
  font-size:11px; color:var(--text-secondary);
  margin:0 0 4px;
}
:deep(.pc-followup-note-perm){ margin-top:10px }

/* ─── 매칭 없음 안내 ─────────────────── */
.pc-no-match{
  padding:40px 20px;
  text-align:center;
  font-size:12.5px;
  color:var(--text-tertiary);
}

/* ─── 체크리스트 ─────────────────────── */
.pc-progress-wrap{
  margin-bottom:16px;
  padding:12px 14px;
  background:var(--bg-secondary);
  border-radius:var(--radius-md);
}
.pc-progress-info{
  display:flex; justify-content:space-between; align-items:center;
  font-size:12px; color:var(--text-secondary);
  margin-bottom:8px;
}
.pc-progress-info strong{ color:var(--text-primary) }
.pc-progress-bar{
  height:6px; background:var(--bg-tertiary);
  border-radius:3px; overflow:hidden;
}
.pc-progress-fill{
  height:100%;
  background:linear-gradient(90deg, var(--accent-blue), var(--accent-green));
  transition:width .3s ease;
}
.pc-cl-group{ margin-bottom:16px }
.pc-cl-cat{
  font-size:11.5px; font-weight:600;
  color:var(--text-tertiary);
  margin:0 0 6px;
  padding-bottom:5px;
  border-bottom:0.5px solid var(--border-light);
  text-transform:uppercase; letter-spacing:.4px;
}
.pc-cl-item{
  display:flex; align-items:flex-start; gap:9px;
  padding:7px 6px;
  border-radius:var(--radius-sm);
  cursor:pointer;
  transition:background .12s;
  position:relative;
}
.pc-cl-item:hover{ background:var(--bg-secondary) }
.pc-cl-item input[type=checkbox]{
  position:absolute; opacity:0; width:0; height:0;
}
.pc-cl-mark{
  flex-shrink:0; width:16px; height:16px;
  border:1.5px solid var(--border-strong);
  border-radius:4px;
  background:var(--bg-primary);
  display:flex; align-items:center; justify-content:center;
  margin-top:1px; transition:all .15s;
}
.pc-cl-item.checked .pc-cl-mark{
  background:var(--accent-blue);
  border-color:var(--accent-blue);
}
.pc-cl-item.checked .pc-cl-mark::after{
  content:''; width:4px; height:8px;
  border:solid #fff; border-width:0 2px 2px 0;
  transform:rotate(45deg) translate(-0.5px, -1px);
}
.pc-cl-text{
  flex:1; font-size:12.5px; color:var(--text-primary); line-height:1.5;
}
.pc-cl-item.checked .pc-cl-text{
  text-decoration:line-through;
  color:var(--text-tertiary);
}
.pc-cl-req{ flex-shrink:0; margin-top:1px }

/* ─── 푸터 ────────────────────────────── */
.pc-footer{
  display:flex; justify-content:space-between; align-items:center;
  padding:12px 20px;
  border-top:0.5px solid var(--border-light);
  background:var(--bg-secondary);
  flex-shrink:0; gap:10px;
}
.pc-footer-info{ font-size:11px; color:var(--text-tertiary) }
.pc-footer-actions{ display:flex; gap:7px }

/* ─── 빈 상태 ──────────────────────────── */
.pc-empty{
  flex:1; display:flex; flex-direction:column;
  align-items:center; justify-content:center;
  gap:14px; padding:40px 20px;
}
.pc-empty-icon{ color:var(--text-tertiary) }
.pc-empty-icon svg{ width:48px; height:48px }
.pc-empty-msg{
  font-size:13px; color:var(--text-secondary);
  text-align:center; max-width:360px;
}
.pc-empty-sub{
  font-size:12px; color:var(--text-tertiary);
  text-align:center; padding:40px 20px;
}
</style>
