<template>
  <div>
    <div class="page-title">시스템 설정</div>
    <div class="page-desc">DataBridge Studio 동작 방식, 로그 설정, Anthropic API 키를 관리합니다</div>
    <div v-if="saved" class="save-toast">✓ 설정이 저장됐습니다</div>

    <div class="settings-layout">
      <!-- 왼쪽: 설정 패널 -->
      <div class="settings-main">

        <!-- ── Anthropic API 설정 ── -->
        <div class="card setting-card">
          <div class="sc-header">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px"><circle cx="8" cy="8" r="7"/><line x1="8" y1="5" x2="8" y2="9"/></svg>
            Anthropic API 설정 (오브젝트 AI 변환용)
          </div>
          <div class="cfg-row">
            <div class="cfg-info">
              <div class="cfg-l">API 키</div>
              <div class="cfg-d">오브젝트 DDL 변환에 사용 (claude.ai → 계정 설정 → API Keys)</div>
            </div>
            <div style="display:flex;gap:6px;align-items:center;flex:1;min-width:0">
              <input :type="showKey?'text':'password'" v-model="cfg.anthropic_api_key"
                placeholder="sk-ant-api03-..." class="api-key-input"
                @input="apiTestResult=null"/>
              <button class="mini-btn" @click="showKey=!showKey">{{ showKey?'숨기기':'보기' }}</button>
            </div>
          </div>
          <div class="cfg-row" style="border-bottom:none">
            <div class="cfg-info"><div class="cfg-l">연결 테스트</div></div>
            <div style="display:flex;align-items:center;gap:8px">
              <button class="btn btn-primary" @click="testApiKey" :disabled="apiTesting||!cfg.anthropic_api_key">
                <span v-if="apiTesting" class="spinner" style="width:12px;height:12px;border-top-color:#fff;display:inline-block"></span>
                {{ apiTesting?'테스트 중...':'🔌 API 연결 테스트' }}
              </button>
              <div v-if="apiTestResult" class="api-test-result" :class="apiTestResult.ok?'ok':'err'">
                {{ apiTestResult.ok?'✓ '+apiTestResult.message:'✗ '+apiTestResult.error }}
              </div>
            </div>
          </div>
        </div>

        <!-- ── 이관 설정 ── -->
        <div class="card setting-card">
          <div class="sc-header">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px"><line x1="2" y1="8" x2="14" y2="8"/><polyline points="9,3 14,8 9,13"/></svg>
            이관 설정
          </div>
          <div class="cfg-row">
            <div class="cfg-info"><div class="cfg-l">배치 크기</div><div class="cfg-d">1회 INSERT 행 수</div></div>
            <input type="number" v-model.number="cfg.batch_size" min="100" max="100000" step="100" style="width:100px"/>
          </div>
          <div class="cfg-row">
            <div class="cfg-info"><div class="cfg-l">병렬 처리 수</div></div>
            <div class="sel-wrap w120"><select v-model.number="cfg.parallel_workers">
              <option v-for="n in [1,2,4,8,16]" :key="n" :value="n">{{ n }} 스레드</option>
            </select><Chev/></div>
          </div>
          <div class="cfg-row">
            <div class="cfg-info"><div class="cfg-l">오류 처리</div></div>
            <div class="sel-wrap w160"><select v-model="cfg.on_error">
              <option value="skip">오류 행 건너뜀</option>
              <option value="retry">재시도 후 건너뜀</option>
              <option value="abort">즉시 중단</option>
            </select><Chev/></div>
          </div>
          <div class="cfg-row">
            <div class="cfg-info"><div class="cfg-l">재시도 횟수</div></div>
            <input type="number" v-model.number="cfg.retry_count" min="0" max="10" style="width:80px"/>
          </div>
        </div>


        <!-- ── 아이콘 테마 ── -->
        <div class="card setting-card">
          <div class="sc-header" style="cursor:pointer" @click="themeOpen=!themeOpen">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px">
              <circle cx="8" cy="8" r="6"/>
              <circle cx="5" cy="7" r="1.2" fill="currentColor"/>
              <circle cx="8" cy="5.5" r="1.2" fill="currentColor"/>
              <circle cx="11" cy="7" r="1.2" fill="currentColor"/>
              <path d="M5 10 Q8 13 11 10"/>
            </svg>
            사이드바 아이콘 테마
            <!-- 현재 선택된 테마 이름 표시 -->
            <span style="font-size:11px;font-weight:400;color:var(--text-tertiary);margin-left:6px">
              {{ iconThemes.find(t=>t.id===cfg.iconTheme)?.name || '기본' }}
            </span>
            <svg :style="{transform: themeOpen?'rotate(180deg)':'rotate(0deg)', transition:'transform .2s', marginLeft:'auto'}"
                 viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:11px;height:11px;flex-shrink:0">
              <polyline points="2,4 6,8 10,4"/>
            </svg>
          </div>
          <div v-if="themeOpen" class="theme-grid">
            <div v-for="t in iconThemes" :key="t.id"
                 class="theme-card" :class="{active: cfg.iconTheme===t.id}"
                 @click="cfg.iconTheme=t.id; applyIconTheme(t.id)">
              <div class="theme-preview" :style="{background: t.bg}">
                <div class="theme-icons-row">
                  <div v-for="ic in t.preview" :key="ic.label" class="theme-icon-dot"
                       :style="{background: ic.color}">
                    <span style="font-size:11px">{{ ic.emoji }}</span>
                  </div>
                </div>
              </div>
              <div class="theme-info">
                <div class="theme-name">{{ t.name }}</div>
                <div class="theme-desc">{{ t.desc }}</div>
              </div>
              <div v-if="cfg.iconTheme===t.id" class="theme-check">✓</div>
            </div>
          </div>
        </div>

        <!-- ── 로그 설정 ── -->
        <div class="card setting-card">
          <div class="sc-header">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px"><rect x="1" y="2" width="14" height="12" rx="1"/><line x1="4" y1="6" x2="12" y2="6"/><line x1="4" y1="9" x2="10" y2="9"/></svg>
            로그 설정
          </div>
          <div class="cfg-row">
            <div class="cfg-info"><div class="cfg-l">로그 레벨</div><div class="cfg-d">DEBUG → 상세 오류 포함</div></div>
            <div class="sel-wrap w140"><select v-model="cfg.log_level">
              <option value="DEBUG">DEBUG (상세)</option>
              <option value="INFO">INFO (기본)</option>
              <option value="WARNING">WARNING</option>
              <option value="ERROR">ERROR만</option>
            </select><Chev/></div>
          </div>
          <div class="cfg-row">
            <div class="cfg-info"><div class="cfg-l">로그 포맷</div></div>
            <div class="sel-wrap w120"><select v-model="cfg.log_format">
              <option value="TEXT">TEXT</option>
              <option value="JSON">JSON</option>
            </select><Chev/></div>
          </div>

          <!-- 로그 파일 경로 -->
          <div class="log-path-section">
            <div class="lps-title">📁 로그 파일 경로</div>
            <div class="lps-row">
              <span class="lps-label">🖥 백엔드</span>
              <input type="text" v-model="cfg.backend_log_file" class="path-input"/>
              <button class="mini-btn" @click="loadLogInfo('backend')" title="파일 정보 조회">📊 정보</button>
            </div>
            <div v-if="logInfoMap.backend" class="log-file-info">
              <span class="lib-path lib-link" @click="copyPath(logInfoMap.backend.file)" title="클릭: 경로 복사">
                📂 {{ logInfoMap.backend.file }}
              </span>
              <span :class="logInfoMap.backend.exists?'lib-ok':'lib-miss'">
                {{ logInfoMap.backend.exists ? logInfoMap.backend.size_kb+'KB' : '파일 없음' }}
              </span>
              <span class="level-badge" :class="logInfoMap.backend.level">{{ logInfoMap.backend.level }}</span>
            </div>
            <div class="lps-row" style="margin-top:6px">
              <span class="lps-label">🌐 프론트</span>
              <input type="text" v-model="cfg.frontend_log_file" class="path-input"/>
              <button class="mini-btn" @click="loadLogInfo('frontend')" title="파일 정보 조회">📊 정보</button>
              <button class="mini-btn" @click="testFrontendLog" title="테스트 로그 기록">📝 테스트</button>
            </div>
            <div v-if="logInfoMap.frontend" class="log-file-info">
              <span class="lib-path lib-link" @click="copyPath(logInfoMap.frontend.file)" title="클릭: 경로 복사">
                📂 {{ logInfoMap.frontend.file }}
              </span>
              <span :class="logInfoMap.frontend.exists?'lib-ok':'lib-miss'">
                {{ logInfoMap.frontend.exists ? logInfoMap.frontend.size_kb+'KB' : '없음 (테스트 버튼으로 생성)' }}
              </span>
            </div>
            <div class="lps-row" style="gap:10px;margin-top:6px">
              <span class="lps-label">최대 크기</span>
              <input type="number" v-model.number="cfg.log_max_mb" style="width:70px" min="1" max="500"/>
              <span class="lps-note">MB</span>
              <span class="lps-label" style="margin-left:12px">백업 수</span>
              <input type="number" v-model.number="cfg.log_backup_count" style="width:55px" min="1" max="20"/>
              <span class="lps-note">개</span>
            </div>
          </div>

          <div class="cfg-row" style="margin-top:4px">
            <div class="cfg-info"><div class="cfg-l">보존 기간</div></div>
            <div style="display:flex;align-items:center;gap:6px">
              <input type="number" v-model.number="cfg.log_retention_days" min="1" max="365" style="width:80px"/>
              <span class="lps-note">일</span>
              <button class="mini-btn" @click="rotateLog" :disabled="rotating" style="margin-left:8px">
                <span v-if="rotating" class="spinner" style="width:10px;height:10px;display:inline-block;margin-right:3px"></span>
                🔄 logging 재시작
              </button>
            </div>
          </div>
        </div>

        <!-- 저장 버튼 -->
        <div style="display:flex;gap:8px;margin-top:4px">
          <button class="btn btn-primary" @click="saveSettings" :disabled="saving">
            <span v-if="saving" class="spinner" style="width:12px;height:12px;border-top-color:#fff;display:inline-block"></span>
            {{ saving?'저장 중...':'💾 설정 저장' }}
          </button>
          <button class="btn" @click="resetDefaults">기본값 복원</button>
        </div>
      </div>

      <!-- 오른쪽: 로그 뷰어 -->
      <div class="log-viewer-panel">
        <div class="card lv-card">
          <div class="lv-header">
            <!-- 소스 탭 -->
            <div class="lv-tabs">
              <button class="lv-tab" :class="{active:logSource==='backend'}" @click="logSource='backend';loadLogs()">
                🖥 백엔드
              </button>
              <button class="lv-tab" :class="{active:logSource==='frontend'}" @click="logSource='frontend';loadLogs()">
                🌐 프론트
              </button>
            </div>
            <!-- 필터 & 액션 -->
            <div class="lv-actions">
              <div class="sel-wrap" style="min-width:85px">
                <select v-model="logLevelFilter" style="font-size:11px;padding:3px 22px 3px 7px">
                  <option value="">전체</option>
                  <option value="DEBUG">DEBUG</option>
                  <option value="INFO">INFO</option>
                  <option value="WARNING">WARNING</option>
                  <option value="ERROR">ERROR</option>
                </select><Chev/>
              </div>
              <input type="text" v-model="logSearch" placeholder="검색..." style="width:100px;font-size:11px;padding:3px 7px;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:var(--radius-sm);color:var(--text-primary)"/>
              <button class="mini-btn" @click="loadLogs" title="새로고침">↻</button>
              <button class="mini-btn" :class="{active:autoRefresh}" @click="autoRefresh=!autoRefresh" title="자동 새로고침">
                {{ autoRefresh?'▶ 자동':'⏸' }}
              </button>
              <button class="mini-btn" @click="logLines=[]" title="화면 초기화">🗑</button>
              <button class="mini-btn" @click="copyLogs" title="전체 복사">📋</button>
            </div>
          </div>

          <!-- 로그 내용 -->
          <div class="lv-body" ref="logBodyEl">
            <div v-if="logLoading" class="lv-empty">
              <span class="spinner" style="width:14px;height:14px;display:inline-block;margin-right:6px"></span>로딩 중...
            </div>
            <div v-else-if="!logLines.length" class="lv-empty">
              {{ logSource==='backend' ? '백엔드 로그가 없습니다.' : '프론트 로그가 없습니다. 📝 테스트 버튼을 눌러 생성하세요.' }}
            </div>
            <div v-for="(line,i) in filteredLogs" :key="i" class="log-line" :class="lineClass(line)">{{ line }}</div>
          </div>
          <div class="lv-footer">
            <span>{{ logSource==='backend'?'🖥 백엔드':'🌐 프론트' }} · {{ filteredLogs.length }}/{{ logLines.length }}줄</span>
            <span class="lv-file-path" @click="copyPath(currentLogFile)" style="cursor:pointer" title="클릭: 경로 복사">
              📂 {{ currentLogFile || '파일 없음' }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useAppStore } from '@/store/appStore.js'
import axios from 'axios'

const app = useAppStore()
const Chev = { template: '<div class="chev-ico"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px;display:block"><polyline points="2,4 6,8 10,4"/></svg></div>' }

const DEFAULTS = {
  batch_size:5000, parallel_workers:4, on_error:'skip', retry_count:3,
  log_level:'INFO', log_format:'TEXT', log_retention_days:30,
  backend_log_file:'./logs/databridge_backend.log',
  frontend_log_file:'./logs/databridge_frontend.log',
  log_max_mb:50, log_backup_count:5,
  notify_email:false, notify_slack:false,
  anthropic_api_key:'',
}

const cfg      = ref({...DEFAULTS})
const saving   = ref(false)
const saved    = ref(false)
const showKey  = ref(false)
const rotating = ref(false)

// API 테스트
const apiTesting   = ref(false)
const apiTestResult= ref(null)

// 로그 파일 정보 (source별)
const logInfoMap = ref({ backend: null, frontend: null })

// 로그 뷰어
const logSource       = ref('backend')
const logLines        = ref([])
const logLevelFilter  = ref('')
const logSearch       = ref('')
const autoRefresh     = ref(false)
const logLoading      = ref(false)
const logBodyEl       = ref(null)
let   _autoTimer      = null

const currentLogFile = computed(() =>
  logSource.value === 'backend'
    ? logInfoMap.value.backend?.file || cfg.value.backend_log_file
    : logInfoMap.value.frontend?.file || cfg.value.frontend_log_file
)

const filteredLogs = computed(() => {
  let lines = logLines.value
  if (logLevelFilter.value) lines = lines.filter(l => l.includes(logLevelFilter.value))
  if (logSearch.value) {
    const q = logSearch.value.toLowerCase()
    lines = lines.filter(l => l.toLowerCase().includes(q))
  }
  return lines
})

function lineClass(line) {
  if (line.includes('ERROR') || line.includes('CRITICAL')) return 'log-err'
  if (line.includes('WARNING') || line.includes('WARN'))   return 'log-warn'
  if (line.includes('DEBUG'))                              return 'log-debug'
  return 'log-info'
}

// -- 설정 저장/로드 --
async function loadSettings() {
  try {
    const {data} = await axios.get('/api/v1/settings/')
    cfg.value = {...DEFAULTS, ...data}
  } catch { cfg.value = {...DEFAULTS} }
}

async function saveSettings() {
  saving.value = true
  try {
    await axios.put('/api/v1/settings/', cfg.value)
    saved.value = true
    setTimeout(() => saved.value=false, 2500)
    app.notify('설정 저장 완료 — 레벨: '+cfg.value.log_level, 'success')
    await loadLogInfo('backend')
    await loadLogInfo('frontend')
  } catch(e) { app.notify('저장 실패: '+e.message,'error') }
  saving.value = false
}

function resetDefaults() { cfg.value={...DEFAULTS}; app.notify('기본값 복원됨','info') }

// -- API 테스트 --
async function testApiKey() {
  apiTesting.value = true; apiTestResult.value = null
  // 먼저 현재 입력된 키를 임시 저장
  try { await axios.put('/api/v1/settings/', { anthropic_api_key: cfg.value.anthropic_api_key }) } catch {}
  try {
    const {data} = await axios.post('/api/v1/settings/api-key-test')
    apiTestResult.value = data
    app.notify(data.ok ? '✓ API 연결 성공!' : '✗ API 연결 실패: '+data.error, data.ok?'success':'error')
  } catch(e) { apiTestResult.value = { ok:false, error:e.message } }
  apiTesting.value = false
}

// -- 로그 파일 정보 --
async function loadLogInfo(source) {
  try {
    const {data} = await axios.get('/api/v1/settings/log-info', { params:{ source } })
    logInfoMap.value[source] = data
    if (source === logSource.value) app.notify(`${source} 로그 정보 갱신됨`, 'success')
  } catch(e) { app.notify('정보 조회 실패','error') }
}

// -- 로그 뷰어 --
async function loadLogs() {
  logLoading.value = true
  try {
    const {data} = await axios.get('/api/v1/settings/log-tail', {
      params: { lines:400, source: logSource.value }
    })
    logLines.value = data.lines || []
    // 파일 정보 업데이트
    logInfoMap.value[logSource.value] = {
      ...(logInfoMap.value[logSource.value]||{}),
      file: data.file, exists: data.exists
    }
    await nextTick()
    if (logBodyEl.value) logBodyEl.value.scrollTop = logBodyEl.value.scrollHeight
  } catch(e) {
    logLines.value = [`[오류] 로그 파일 읽기 실패: ${e.message}`,
                      `경로: ${logSource.value==='backend'?cfg.value.backend_log_file:cfg.value.frontend_log_file}`]
  } finally { logLoading.value = false }
}

function copyLogs() {
  navigator.clipboard?.writeText(filteredLogs.value.join('\n'))
  app.notify('로그 복사됨','success')
}

function copyPath(path) {
  if (!path) return
  navigator.clipboard?.writeText(path).then(() => {
    app.notify('📋 경로 복사됨: '+path.split(/[\\/]/).pop(), 'success')
  })
}

// -- Logging 재시작 --
async function rotateLog() {
  if (!confirm('현재 로그를 타임스탬프로 백업하고 새로 시작하시겠습니까?')) return
  rotating.value = true
  try {
    const {data} = await axios.post('/api/v1/settings/log-rotate')
    if (data.ok) {
      app.notify(`로그 재시작 완료! 백업: ${data.backup.split(/[\\/]/).pop()}`, 'success')
      await loadLogs()
    } else {
      app.notify('재시작 실패: '+data.error,'error')
    }
  } catch(e) { app.notify('오류: '+e.message,'error') }
  rotating.value = false
}

// -- 프론트 로그 테스트 --
async function testFrontendLog() {
  try {
    await axios.post('/api/v1/settings/frontend-log', {
      level:'INFO', page:'Settings',
      message:'프론트엔드 로그 테스트',
      detail:`시각: ${new Date().toLocaleString()}`
    })
    app.notify('프론트 로그 기록 완료!','success')
    await loadLogInfo('frontend')
    if (logSource.value==='frontend') await loadLogs()
  } catch(e) { app.notify('실패: '+e.message,'error') }
}

// autoRefresh watch
watch(autoRefresh, v => {
  clearInterval(_autoTimer)
  if (v) _autoTimer = setInterval(loadLogs, 3000)
})


const themeOpen = ref(false)  // 아이콘 테마 섹션 열림/닫힘
const iconThemes = [
  {
    id: 'default',
    name: '기본 (모노크롬)',
    desc: '깔끔한 단색 아이콘',
    bg: 'linear-gradient(135deg,#f8fafc,#e2e8f0)',
    preview: [
      { emoji: '⊞', color: '#64748b' },
      { emoji: '◎', color: '#64748b' },
      { emoji: '⋯', color: '#64748b' },
    ]
  },
  {
    id: 'neon',
    name: '네온 (Neon)',
    desc: '사이버펑크 형광 컬러',
    bg: 'linear-gradient(135deg,#0f0c29,#302b63)',
    preview: [
      { emoji: '⊞', color: '#00f5ff' },
      { emoji: '◎', color: '#ff00ff' },
      { emoji: '⋯', color: '#39ff14' },
    ]
  },
  {
    id: 'pastel',
    name: '파스텔 (Pastel)',
    desc: '부드럽고 따뜻한 파스텔',
    bg: 'linear-gradient(135deg,#ffecd2,#fcb69f)',
    preview: [
      { emoji: '⊞', color: '#ff9a9e' },
      { emoji: '◎', color: '#a8edea' },
      { emoji: '⋯', color: '#ffd1ff' },
    ]
  },
  {
    id: 'material',
    name: '머테리얼 (Material)',
    desc: 'Google Material 스타일',
    bg: 'linear-gradient(135deg,#fff8e1,#ffe0b2)',
    preview: [
      { emoji: '⊞', color: '#4285f4' },
      { emoji: '◎', color: '#34a853' },
      { emoji: '⋯', color: '#ea4335' },
    ]
  },
  {
    id: 'kakao',
    name: '카카오 (Kakao)',
    desc: '카카오 스타일 노란 계열',
    bg: 'linear-gradient(135deg,#fee500,#ffd43b)',
    preview: [
      { emoji: '⊞', color: '#3c1e1e' },
      { emoji: '◎', color: '#3c1e1e' },
      { emoji: '⋯', color: '#3c1e1e' },
    ]
  },
  {
    id: 'ocean',
    name: '오션 (Ocean)',
    desc: '딥블루 오션 그라디언트',
    bg: 'linear-gradient(135deg,#667eea,#764ba2)',
    preview: [
      { emoji: '⊞', color: '#a8edea' },
      { emoji: '◎', color: '#fed6e3' },
      { emoji: '⋯', color: '#ffd89b' },
    ]
  },
]

function applyIconTheme(id) {
  // appStore에 테마 저장
  try { localStorage.setItem('iconTheme', id) } catch {}
  // 루트 CSS 변수로 적용
  const themes = {
    default: { '--icon-db':'#6366f1','--icon-monitor':'#14b8a6','--icon-conn':'#f59e0b','--icon-schema':'#3b82f6','--icon-map':'#8b5cf6','--icon-exp':'#06b6d4','--icon-job':'#f97316','--icon-valid':'#22c55e','--icon-conv':'#6366f1','--icon-sched':'#ec4899','--icon-rep':'#0ea5e9','--icon-set':'#64748b','--icon-plug':'#a855f7' },
    neon:    { '--icon-db':'#00f5ff','--icon-monitor':'#ff00ff','--icon-conn':'#39ff14','--icon-schema':'#00f5ff','--icon-map':'#ff00ff','--icon-exp':'#ffd700','--icon-job':'#ff6700','--icon-valid':'#39ff14','--icon-conv':'#00f5ff','--icon-sched':'#ff00ff','--icon-rep':'#00f5ff','--icon-set':'#39ff14','--icon-plug':'#ff00ff' },
    pastel:  { '--icon-db':'#ff9a9e','--icon-monitor':'#fecfef','--icon-conn':'#ffeaa7','--icon-schema':'#a8edea','--icon-map':'#fed6e3','--icon-exp':'#d4fc79','--icon-job':'#ffd1ff','--icon-valid':'#96fbc4','--icon-conv':'#a8edea','--icon-sched':'#ffeaa7','--icon-rep':'#ffd1ff','--icon-set':'#c3cfe2','--icon-plug':'#fed6e3' },
    material:{ '--icon-db':'#4285f4','--icon-monitor':'#34a853','--icon-conn':'#fbbc04','--icon-schema':'#4285f4','--icon-map':'#ea4335','--icon-exp':'#34a853','--icon-job':'#ff6d00','--icon-valid':'#34a853','--icon-conv':'#4285f4','--icon-sched':'#fbbc04','--icon-rep':'#4285f4','--icon-set':'#9e9e9e','--icon-plug':'#ab47bc' },
    kakao:   { '--icon-db':'#3c1e1e','--icon-monitor':'#3c1e1e','--icon-conn':'#3c1e1e','--icon-schema':'#3c1e1e','--icon-map':'#3c1e1e','--icon-exp':'#3c1e1e','--icon-job':'#3c1e1e','--icon-valid':'#3c1e1e','--icon-conv':'#3c1e1e','--icon-sched':'#3c1e1e','--icon-rep':'#3c1e1e','--icon-set':'#3c1e1e','--icon-plug':'#3c1e1e' },
    ocean:   { '--icon-db':'#a8edea','--icon-monitor':'#fed6e3','--icon-conn':'#ffd89b','--icon-schema':'#a8edea','--icon-map':'#d4fc79','--icon-exp':'#96fbc4','--icon-job':'#ffd89b','--icon-valid':'#96fbc4','--icon-conv':'#a8edea','--icon-sched':'#ffd89b','--icon-rep':'#fed6e3','--icon-set':'#c3cfe2','--icon-plug':'#d4fc79' },
  }
  const vars = themes[id] || themes.default
  const root = document.documentElement
  Object.entries(vars).forEach(([k,v]) => root.style.setProperty(k, v))
}

// 초기 로드 시 저장된 테마 적용
onMounted(async () => {
  const saved = localStorage.getItem('iconTheme') || 'default'
  if (!cfg.value.iconTheme) cfg.value.iconTheme = saved
  applyIconTheme(cfg.value.iconTheme || 'default')

  await loadSettings()
  await loadLogInfo('backend')
  await loadLogInfo('frontend')
  await loadLogs()
  // 전역 에러 자동 프론트 로그
  window.__fe_log_err = (e) => {
    axios.post('/api/v1/settings/frontend-log', {
      level:'ERROR', page: window.location.pathname,
      message: e.message||'JS Error',
      detail: (e.filename||'')+(e.lineno?':'+e.lineno:'')
    }).catch(()=>{})
  }
  window.addEventListener('error', window.__fe_log_err)
  window.addEventListener('unhandledrejection', (e) => {
    axios.post('/api/v1/settings/frontend-log', {
      level:'ERROR', page: window.location.pathname,
      message:'UnhandledPromise: '+String(e.reason).slice(0,100)
    }).catch(()=>{})
  })
})
onUnmounted(() => {
  clearInterval(_autoTimer)
  window.removeEventListener('error', window.__fe_log_err)
})
</script>

<style scoped>
.settings-layout { display:grid; grid-template-columns:400px 1fr; gap:12px; align-items:start; }
.settings-main { display:flex; flex-direction:column; gap:10px; }
.setting-card { padding:0; overflow:hidden; }
.sc-header { display:flex; align-items:center; gap:7px; padding:10px 14px; border-bottom:0.5px solid var(--border-light); background:var(--bg-secondary); font-size:12.5px; font-weight:600; color:var(--text-primary); transition:background .12s; }
.sc-header[style*="cursor:pointer"]:hover { background:var(--bg-primary); }
.cfg-row { display:flex; align-items:center; justify-content:space-between; padding:9px 14px; border-bottom:0.5px solid var(--border-light); gap:12px; }
.cfg-row:last-child { border-bottom:none; }
.cfg-info { flex:1; }
.cfg-l { font-size:12.5px; font-weight:500; color:var(--text-primary); }
.cfg-d { font-size:11px; color:var(--text-tertiary); margin-top:1px; }
.api-key-input { flex:1; min-width:0; padding:6px 10px; background:var(--bg-secondary); border:0.5px solid var(--border-mid); border-radius:var(--radius-md); font-size:12px; color:var(--text-primary); font-family:'Consolas','SF Mono',monospace; }
.api-key-input:focus { outline:none; border-color:var(--accent-blue); }
.api-test-result { font-size:11.5px; font-weight:500; padding:4px 10px; border-radius:var(--radius-md); }
.api-test-result.ok { background:var(--bg-success); color:var(--text-success); }
.api-test-result.err { background:var(--bg-danger); color:var(--text-danger); max-width:300px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
input[type="number"], input[type="text"] { padding:6px 10px; background:var(--bg-secondary); border:0.5px solid var(--border-mid); border-radius:var(--radius-md); font-size:12px; color:var(--text-primary); font-family:var(--font); }
input:focus { outline:none; border-color:var(--accent-blue); }
.sel-wrap { position:relative; }
.sel-wrap select { width:100%; appearance:none; -webkit-appearance:none; background:var(--bg-secondary); border:0.5px solid var(--border-mid); border-radius:var(--radius-md); padding:6px 24px 6px 9px; font-size:12px; color:var(--text-primary); cursor:pointer; font-family:var(--font); }
.sel-wrap select:focus { outline:none; border-color:var(--accent-blue); }
.chev-ico { position:absolute; right:7px; top:50%; transform:translateY(-50%); pointer-events:none; color:var(--text-tertiary); }
.chev-ico svg { width:10px; height:10px; display:block; }
.w120 { min-width:120px; } .w140 { min-width:140px; } .w160 { min-width:160px; }

.log-path-section { padding:12px 14px; border-top:0.5px solid var(--border-light); background:var(--bg-secondary); }
.lps-title { font-size:11.5px; font-weight:600; color:var(--text-secondary); margin-bottom:8px; }
.lps-row { display:flex; align-items:center; gap:6px; margin-bottom:5px; flex-wrap:wrap; }
.lps-label { font-size:11.5px; font-weight:500; color:var(--text-secondary); min-width:60px; flex-shrink:0; }
.path-input { flex:1; min-width:160px; font-family:'Consolas','SF Mono',monospace; font-size:11.5px; padding:5px 8px; }
.lps-note { font-size:11px; color:var(--text-tertiary); }
.log-file-info { display:flex; align-items:center; gap:8px; padding:4px 0 4px 66px; flex-wrap:wrap; }
.lib-path { font-family:'Consolas','SF Mono',monospace; font-size:11px; color:var(--text-info); overflow:hidden; text-overflow:ellipsis; flex:1; }
.lib-link { cursor:pointer; }
.lib-link:hover { text-decoration:underline; }
.lib-ok { color:var(--text-success); font-size:11.5px; font-weight:500; }
.lib-miss { color:var(--text-tertiary); font-size:11px; font-style:italic; }
.level-badge { font-size:10px; font-weight:700; padding:1px 7px; border-radius:4px; }
.level-badge.DEBUG { background:#e8f5e9; color:#2e7d32; }
.level-badge.INFO  { background:var(--bg-info); color:var(--text-info); }
.level-badge.WARNING { background:var(--bg-warning); color:var(--text-warning); }
.level-badge.ERROR { background:var(--bg-danger); color:var(--text-danger); }

.btn { display:inline-flex; align-items:center; gap:5px; padding:7px 14px; border-radius:var(--radius-md); font-size:12px; font-weight:500; font-family:var(--font); cursor:pointer; border:0.5px solid var(--border-mid); background:transparent; color:var(--text-secondary); transition:all .12s; }
.btn:hover { background:var(--bg-secondary); }
.btn-primary { background:var(--bg-info); color:var(--text-info); border-color:var(--accent-blue); }
.btn-primary:hover { background:var(--accent-blue); color:#fff; }
.btn:disabled { opacity:.5; cursor:not-allowed; }
.mini-btn { font-size:11px; padding:3px 8px; border-radius:var(--radius-sm); border:0.5px solid var(--border-mid); background:transparent; cursor:pointer; font-family:var(--font); color:var(--text-secondary); white-space:nowrap; }
.mini-btn:hover { background:var(--bg-secondary); }
.mini-btn.active { background:var(--bg-success); color:var(--text-success); border-color:var(--accent-green); }

/* 로그 뷰어 */
.log-viewer-panel { height:calc(100vh - 120px); min-height:500px; }
.lv-card { display:flex; flex-direction:column; height:100%; padding:0; overflow:hidden; }
.lv-header { display:flex; align-items:center; gap:8px; padding:8px 10px; border-bottom:0.5px solid var(--border-light); background:var(--bg-secondary); flex-shrink:0; flex-wrap:wrap; }
.lv-tabs { display:flex; gap:4px; }
.lv-tab { padding:5px 12px; border-radius:var(--radius-md); border:0.5px solid var(--border-mid); background:transparent; cursor:pointer; font-size:12px; font-family:var(--font); color:var(--text-secondary); transition:all .12s; }
.lv-tab:hover { background:var(--bg-primary); }
.lv-tab.active { background:var(--bg-info); color:var(--text-info); border-color:var(--accent-blue); font-weight:500; }
.lv-actions { display:flex; align-items:center; gap:5px; flex-wrap:wrap; }
.lv-body { flex:1; overflow-y:auto; background:var(--bg-primary); padding:6px 4px; font-family:'Consolas','SF Mono',monospace; font-size:11.5px; }
.lv-body::-webkit-scrollbar { width:5px; }
.lv-body::-webkit-scrollbar-thumb { background:var(--border-mid); border-radius:3px; }
.lv-empty { padding:24px; text-align:center; color:var(--text-tertiary); font-size:12px; font-family:var(--font); }
.log-line { padding:1.5px 8px; line-height:1.6; white-space:pre-wrap; word-break:break-all; }
.log-err  { background:rgba(239,68,68,.08); color:#dc2626; }
.log-warn { background:rgba(234,179,8,.08); color:#b45309; }
.log-debug { color:var(--text-tertiary); }
.log-info { color:var(--text-secondary); }
.lv-footer { padding:5px 10px; border-top:0.5px solid var(--border-light); background:var(--bg-secondary); font-size:10.5px; color:var(--text-tertiary); display:flex; align-items:center; justify-content:space-between; flex-shrink:0; }
.lv-file-path { font-family:'Consolas','SF Mono',monospace; font-size:10px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:350px; }
.lv-file-path:hover { color:var(--text-info); text-decoration:underline; }

.save-toast { position:fixed; top:14px; right:14px; background:var(--accent-green); color:#fff; padding:8px 16px; border-radius:var(--radius-md); font-size:12.5px; font-weight:500; z-index:9999; box-shadow:0 4px 12px rgba(0,0,0,.15); }
/* 아이콘 테마 */
.theme-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; padding:14px; }
.theme-card { border:1.5px solid var(--border-light); border-radius:10px; overflow:hidden; cursor:pointer; transition:all .15s; position:relative; }
.theme-card:hover { border-color:var(--accent-blue); transform:translateY(-1px); box-shadow:0 4px 12px rgba(0,0,0,.1); }
.theme-card.active { border-color:var(--accent-blue); box-shadow:0 0 0 2px rgba(59,130,246,.2); }
.theme-preview { height:64px; display:flex; align-items:center; justify-content:center; }
.theme-icons-row { display:flex; gap:8px; }
.theme-icon-dot { width:28px; height:28px; border-radius:8px; display:flex; align-items:center; justify-content:center; }
.theme-info { padding:8px 10px; }
.theme-name { font-size:12px; font-weight:600; color:var(--text-primary); }
.theme-desc { font-size:10.5px; color:var(--text-tertiary); margin-top:2px; }
.theme-check { position:absolute; top:7px; right:7px; width:18px; height:18px; border-radius:50%; background:var(--accent-blue); color:#fff; font-size:10px; display:flex; align-items:center; justify-content:center; font-weight:700; }

</style>
