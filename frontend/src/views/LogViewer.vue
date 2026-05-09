<template>
  <div class="log-viewer">
    <!-- 헤더 -->
    <div class="lv-header">
      <h2>로그 뷰어 <span class="lv-badge">v95_p9</span></h2>
      <div class="lv-meta">
        파일: {{ fileInfo }} · 크기: {{ sizeKb }} KB · 표시: {{ filteredLines.length }}건 (최신 ↑)
      </div>
    </div>

    <!-- 컨트롤 바 -->
    <div class="lv-controls">
      <select v-model="level" @change="loadLog" class="lv-select">
        <option value="ALL">전체 레벨</option>
        <option value="INFO">INFO</option>
        <option value="WARNING">WARNING</option>
        <option value="ERROR">ERROR</option>
        <option value="CRITICAL">CRITICAL</option>
        <option value="DEBUG">DEBUG</option>
      </select>

      <input
        v-model="keyword"
        @keyup.enter="loadLog"
        placeholder="키워드 (예: view-analyzer, safe_mode)"
        class="lv-input"
      />

      <select v-model.number="lineCount" @change="loadLog" class="lv-select">
        <option :value="200">최근 200줄</option>
        <option :value="500">최근 500줄</option>
        <option :value="1000">최근 1000줄</option>
        <option :value="2000">최근 2000줄</option>
        <option :value="5000">최근 5000줄</option>
      </select>

      <label class="lv-checkbox">
        <input type="checkbox" v-model="autoRefresh" />
        자동 새로고침 (5초)
      </label>

      <button @click="loadLog" class="lv-btn lv-btn-primary">🔄 새로고침</button>
      <button @click="openSettings" class="lv-btn">⚙ 회전 설정</button>
      <button @click="confirmClear" class="lv-btn lv-btn-danger">🗑 초기화</button>
      <button @click="loadArchives" class="lv-btn">📦 백업 ({{ archives.length }})</button>
    </div>

    <!-- 로그 본문 (최신 위) -->
    <div class="lv-body" ref="bodyRef">
      <div v-if="loading" class="lv-empty">불러오는 중...</div>
      <div v-else-if="filteredLines.length === 0" class="lv-empty">
        표시할 로그가 없습니다.
      </div>
      <div v-else>
        <div
          v-for="(row, idx) in filteredLines"
          :key="idx"
          class="lv-row"
          :class="rowClass(row)"
        >
          <span class="lv-row-num">{{ filteredLines.length - idx }}</span>
          <span class="lv-row-text">{{ row }}</span>
        </div>
      </div>
    </div>

    <!-- 회전 설정 모달 -->
    <div v-if="showSettings" class="lv-modal-bg" @click.self="showSettings = false">
      <div class="lv-modal">
        <h3>로그 회전 설정</h3>
        <p class="lv-modal-desc">
          사이즈 또는 시간 중 <b>먼저 도달하는 조건</b>으로 회전됩니다.
        </p>

        <div class="lv-form-row">
          <label>파일 사이즈 임계값</label>
          <select v-model.number="settings.size_mb">
            <option :value="1">1 MB</option>
            <option :value="2">2 MB</option>
            <option :value="3">3 MB</option>
            <option :value="4">4 MB</option>
            <option :value="5">5 MB</option>
          </select>
        </div>

        <div class="lv-form-row">
          <label>시간 임계값</label>
          <select v-model.number="settings.interval_hours">
            <option :value="1">1 시간</option>
            <option :value="2">2 시간</option>
            <option :value="4">4 시간</option>
            <option :value="6">6 시간</option>
            <option :value="12">12 시간</option>
            <option :value="24">24 시간</option>
          </select>
        </div>

        <div class="lv-form-row">
          <label>백업 보관 기간</label>
          <select v-model.number="settings.retention_days">
            <option :value="7">7 일</option>
            <option :value="14">14 일</option>
            <option :value="30">30 일</option>
            <option :value="60">60 일</option>
            <option :value="90">90 일</option>
            <option :value="180">180 일</option>
            <option :value="365">365 일</option>
          </select>
        </div>

        <div class="lv-modal-actions">
          <button @click="saveSettings" class="lv-btn lv-btn-primary">저장</button>
          <button @click="showSettings = false" class="lv-btn">취소</button>
        </div>
      </div>
    </div>

    <!-- 백업 목록 모달 -->
    <div v-if="showArchives" class="lv-modal-bg" @click.self="showArchives = false">
      <div class="lv-modal lv-modal-wide">
        <h3>백업 파일 목록 ({{ archives.length }}건)</h3>
        <div class="lv-archive-list">
          <div v-if="archives.length === 0" class="lv-empty">백업 파일이 없습니다.</div>
          <div v-for="ar in archives" :key="ar.name" class="lv-archive-row">
            <span class="lv-archive-name">{{ ar.name }}</span>
            <span class="lv-archive-meta">{{ ar.size_kb }} KB · {{ ar.modified }}</span>
            <button @click="viewArchive(ar.name)" class="lv-btn lv-btn-sm">조회</button>
          </div>
        </div>
        <div class="lv-modal-actions">
          <button @click="manualCleanup" class="lv-btn">만료분 정리</button>
          <button @click="showArchives = false" class="lv-btn">닫기</button>
        </div>
      </div>
    </div>

    <!-- 백업 내용 조회 모달 -->
    <div v-if="archiveContent" class="lv-modal-bg" @click.self="archiveContent = null">
      <div class="lv-modal lv-modal-wide">
        <h3>{{ archiveContent.name }}</h3>
        <div class="lv-archive-body">
          <div v-for="(row, idx) in archiveContent.lines" :key="idx"
               class="lv-row" :class="rowClass(row)">
            <span class="lv-row-num">{{ archiveContent.lines.length - idx }}</span>
            <span class="lv-row-text">{{ row }}</span>
          </div>
        </div>
        <div class="lv-modal-actions">
          <button @click="archiveContent = null" class="lv-btn">닫기</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import axios from 'axios'

const API_BASE = '/api/logs'

const loading = ref(false)
const lines = ref([])
const fileInfo = ref('')
const sizeKb = ref(0)

const level = ref('ALL')
const keyword = ref('')
const lineCount = ref(500)
const autoRefresh = ref(false)
let refreshTimer = null

const showSettings = ref(false)
const settings = ref({ size_mb: 5, interval_hours: 1, retention_days: 30 })

const showArchives = ref(false)
const archives = ref([])
const archiveContent = ref(null)

const filteredLines = computed(() => lines.value)

function rowClass(row) {
  if (row.includes('[ERROR]') || row.includes('[CRITICAL]')) return 'lv-row-error'
  if (row.includes('[WARNING]')) return 'lv-row-warn'
  if (row.includes('[DEBUG]')) return 'lv-row-debug'
  return 'lv-row-info'
}

async function loadLog() {
  loading.value = true
  try {
    const res = await axios.get(`${API_BASE}/tail`, {
      params: { lines: lineCount.value, level: level.value, keyword: keyword.value }
    })
    lines.value = res.data.lines || []
    fileInfo.value = res.data.file || ''
    sizeKb.value = res.data.size_kb || 0
  } catch (e) {
    console.error('[LogViewer] load 실패', e)
    lines.value = [`[CLIENT ERROR] 로그 조회 실패: ${e.message}`]
  } finally {
    loading.value = false
  }
}

async function loadSettingsFromServer() {
  try {
    const res = await axios.get(`${API_BASE}/settings`)
    settings.value = { ...settings.value, ...res.data }
  } catch (e) {
    console.error('[LogViewer] settings load 실패', e)
  }
}

function openSettings() {
  loadSettingsFromServer().then(() => { showSettings.value = true })
}

async function saveSettings() {
  try {
    await axios.post(`${API_BASE}/settings`, settings.value)
    showSettings.value = false
    alert('설정이 저장되었습니다. 다음 회전부터 적용됩니다.')
    loadLog()
  } catch (e) {
    alert(`저장 실패: ${e.message}`)
  }
}

function confirmClear() {
  if (!confirm('현재 로그를 백업한 뒤 화면과 파일을 초기화합니다. 진행할까요?')) return
  axios.post(`${API_BASE}/clear`).then((res) => {
    alert(`초기화 완료\n백업: ${res.data.archived_to || '(빈 파일)'}`)
    loadLog()
    loadArchives(false)
  }).catch((e) => {
    alert(`초기화 실패: ${e.message}`)
  })
}

async function loadArchives(openModal = true) {
  try {
    const res = await axios.get(`${API_BASE}/archives`)
    archives.value = res.data.archives || []
    if (openModal) showArchives.value = true
  } catch (e) {
    console.error('[LogViewer] archives 실패', e)
  }
}

async function viewArchive(name) {
  try {
    const res = await axios.get(`${API_BASE}/archive/${encodeURIComponent(name)}`, {
      params: { lines: 2000 }
    })
    archiveContent.value = res.data
  } catch (e) {
    alert(`백업 조회 실패: ${e.message}`)
  }
}

async function manualCleanup() {
  try {
    const res = await axios.post(`${API_BASE}/cleanup`)
    alert(`정리 완료: ${res.data.deleted}건 삭제 (보관 ${res.data.retention_days}일)`)
    loadArchives(false)
  } catch (e) {
    alert(`정리 실패: ${e.message}`)
  }
}

watch(autoRefresh, (v) => {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
  if (v) refreshTimer = setInterval(loadLog, 5000)
})

onMounted(() => {
  loadLog()
  loadSettingsFromServer()
  loadArchives(false)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.log-viewer {
  padding: 16px;
  background: #0f1419;
  color: #d4dae0;
  min-height: 100vh;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

.lv-header { margin-bottom: 12px; }
.lv-header h2 { margin: 0; color: #e6edf3; font-size: 18px; }
.lv-badge {
  font-size: 11px; padding: 2px 8px; background: #1f6feb; color: #fff;
  border-radius: 10px; margin-left: 8px; font-weight: normal;
}
.lv-meta { font-size: 12px; color: #7d8590; margin-top: 4px; }

.lv-controls {
  display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px;
  padding: 10px; background: #161b22; border-radius: 6px;
}
.lv-select, .lv-input {
  padding: 6px 10px; background: #0d1117; color: #e6edf3;
  border: 1px solid #30363d; border-radius: 4px; font-size: 13px;
}
.lv-input { flex: 1; min-width: 200px; }
.lv-checkbox { display: flex; align-items: center; gap: 4px; font-size: 13px; }

.lv-btn {
  padding: 6px 12px; background: #21262d; color: #e6edf3;
  border: 1px solid #30363d; border-radius: 4px; cursor: pointer;
  font-size: 13px;
}
.lv-btn:hover { background: #30363d; }
.lv-btn-primary { background: #238636; border-color: #2ea043; }
.lv-btn-primary:hover { background: #2ea043; }
.lv-btn-danger { background: #6e1d24; border-color: #8b2530; }
.lv-btn-danger:hover { background: #8b2530; }
.lv-btn-sm { padding: 3px 8px; font-size: 12px; }

.lv-body {
  background: #010409; border: 1px solid #30363d; border-radius: 6px;
  padding: 8px; max-height: calc(100vh - 200px); overflow-y: auto;
  font-family: 'Consolas', 'Monaco', monospace; font-size: 12.5px;
}
.lv-empty { padding: 20px; text-align: center; color: #7d8590; }

.lv-row {
  display: flex; gap: 10px; padding: 2px 6px; border-radius: 3px;
  white-space: pre-wrap; word-break: break-all; line-height: 1.5;
}
.lv-row:hover { background: #161b22; }
.lv-row-num {
  flex-shrink: 0; width: 50px; text-align: right; color: #484f58;
  user-select: none;
}
.lv-row-text { flex: 1; }
.lv-row-error { color: #ff7b72; }
.lv-row-warn { color: #f0a020; }
.lv-row-debug { color: #7d8590; }
.lv-row-info { color: #d4dae0; }

.lv-modal-bg {
  position: fixed; inset: 0; background: rgba(0,0,0,0.7);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.lv-modal {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  padding: 24px; width: 480px; max-width: 90vw;
}
.lv-modal-wide { width: 800px; max-height: 80vh; display: flex; flex-direction: column; }
.lv-modal h3 { margin: 0 0 12px 0; color: #e6edf3; }
.lv-modal-desc { color: #7d8590; font-size: 13px; margin-bottom: 16px; }

.lv-form-row {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 12px;
}
.lv-form-row label { color: #e6edf3; font-size: 14px; }
.lv-form-row select {
  padding: 6px 10px; background: #0d1117; color: #e6edf3;
  border: 1px solid #30363d; border-radius: 4px; min-width: 140px;
}

.lv-modal-actions {
  display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px;
}

.lv-archive-list {
  flex: 1; overflow-y: auto; max-height: 50vh;
  border: 1px solid #30363d; border-radius: 4px; padding: 4px;
}
.lv-archive-row {
  display: flex; align-items: center; gap: 12px; padding: 8px;
  border-bottom: 1px solid #21262d;
}
.lv-archive-row:last-child { border-bottom: none; }
.lv-archive-name { flex: 1; font-family: monospace; font-size: 13px; }
.lv-archive-meta { color: #7d8590; font-size: 12px; }

.lv-archive-body {
  flex: 1; overflow-y: auto; max-height: 60vh;
  background: #010409; padding: 8px; border-radius: 4px;
  font-family: monospace; font-size: 12px;
}
</style>
