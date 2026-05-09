<template>
  <div>
    <div class="page-title">플러그인 마켓</div>
    <div class="page-desc">커넥터, 변환기, 검증기 등 확장 플러그인을 설치하고 관리합니다</div>

    <!-- 필터 / 검색 -->
    <div class="toolbar">
      <div class="search-wrap">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
        <input v-model="search" type="text" placeholder="플러그인 검색…" class="search-input"/>
      </div>
      <div class="tab-bar">
        <button
          v-for="tab in TABS" :key="tab.id"
          class="tab-btn" :class="{ active: activeTab === tab.id }"
          @click="activeTab = tab.id"
        >{{ tab.label }}</button>
      </div>
    </div>

    <!-- 설치된 플러그인 요약 -->
    <div class="kpi-grid" style="margin-bottom:14px">
      <div class="kpi-card">
        <div class="kpi-label">설치됨</div>
        <div class="kpi-value info">{{ installedCount }}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">업데이트 가능</div>
        <div class="kpi-value warn">{{ updateCount }}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">전체 플러그인</div>
        <div class="kpi-value">{{ PLUGINS.length }}</div>
      </div>
    </div>

    <!-- 플러그인 그리드 -->
    <div class="plugin-grid">
      <div
        v-for="p in filtered" :key="p.id"
        class="plugin-card"
        :class="{ installed: p.installed }"
      >
        <!-- 헤더 -->
        <div class="plugin-header">
          <div class="plugin-icon" :style="{ background: p.color + '22', color: p.color }">
            {{ p.icon }}
          </div>
          <div class="plugin-meta">
            <div class="plugin-name">{{ p.name }}</div>
            <div class="plugin-author">by {{ p.author }}</div>
          </div>
          <div class="plugin-badges">
            <span v-if="p.official" class="badge badge-b">공식</span>
            <span v-if="p.installed && p.hasUpdate" class="badge badge-y">업데이트</span>
            <span v-if="p.installed && !p.hasUpdate" class="badge badge-g">설치됨</span>
          </div>
        </div>

        <!-- 설명 -->
        <div class="plugin-desc">{{ p.desc }}</div>

        <!-- 태그 -->
        <div class="plugin-tags">
          <span v-for="t in p.tags" :key="t" class="tag">{{ t }}</span>
        </div>

        <!-- 하단 -->
        <div class="plugin-footer">
          <div class="plugin-ver">v{{ p.version }}</div>
          <div class="plugin-dl">↓ {{ p.downloads }}</div>
          <div class="plugin-actions">
            <template v-if="p.installed">
              <button v-if="p.hasUpdate" class="act-btn" @click="doUpdate(p)">업데이트</button>
              <button class="act-btn" @click="toggle(p)">
                {{ p.enabled ? '비활성화' : '활성화' }}
              </button>
              <button class="act-btn del" @click="doUninstall(p)">제거</button>
            </template>
            <button v-else class="act-btn" :disabled="installing === p.id" @click="doInstall(p)">
              <span v-if="installing === p.id" class="spinner" style="width:10px;height:10px"/>
              {{ installing === p.id ? '설치 중…' : '설치' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 결과 없음 -->
    <div v-if="filtered.length === 0" class="empty-state card">
      검색 결과가 없습니다
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAppStore } from '@/store/appStore.js'

const app = useAppStore()
const search     = ref('')
const activeTab  = ref('all')
const installing = ref(null)

const TABS = [
  { id: 'all',       label: '전체' },
  { id: 'installed', label: '설치됨' },
  { id: 'connector', label: '커넥터' },
  { id: 'converter', label: '변환기' },
  { id: 'validator', label: '검증기' },
]

const PLUGINS = ref([
  {
    id: 'oracle-conn', name: 'Oracle Connector', author: 'DataBridge',
    icon: '🔶', color: '#e85d04', official: true,
    desc: 'Oracle 11g~21c 완전 지원. TNS/SID/서비스명 연결 방식 모두 지원합니다.',
    tags: ['connector', 'oracle'], version: '2.1.0', downloads: '12.4k',
    installed: true, enabled: true, hasUpdate: false, category: 'connector',
  },
  {
    id: 'snowflake-conn', name: 'Snowflake Connector', author: 'DataBridge',
    icon: '❄️', color: '#29b5e8', official: true,
    desc: 'Snowflake Data Cloud 전용 커넥터. Bulk Load 최적화로 대용량 이관 가속.',
    tags: ['connector', 'snowflake', 'cloud'], version: '1.8.2', downloads: '8.9k',
    installed: true, enabled: true, hasUpdate: true, category: 'connector',
  },
  {
    id: 'bigquery-conn', name: 'BigQuery Connector', author: 'Google',
    icon: '📊', color: '#4285f4', official: false,
    desc: 'Google BigQuery 커넥터. 서비스 계정 키 기반 인증 지원.',
    tags: ['connector', 'bigquery', 'gcp'], version: '1.3.1', downloads: '5.2k',
    installed: false, enabled: false, hasUpdate: false, category: 'connector',
  },
  {
    id: 'mongodb-conn', name: 'MongoDB Connector', author: 'MongoDB Inc.',
    icon: '🍃', color: '#4db33d', official: false,
    desc: 'MongoDB → 관계형 DB 자동 스키마 변환. 중첩 문서 플래튼 지원.',
    tags: ['connector', 'mongodb', 'nosql'], version: '0.9.5', downloads: '3.1k',
    installed: false, enabled: false, hasUpdate: false, category: 'connector',
  },
  {
    id: 'mysql-pg-conv', name: 'MySQL→PG Converter', author: 'DataBridge',
    icon: '⚙️', color: '#7c3aed', official: true,
    desc: 'MySQL 방언을 PostgreSQL SQL로 정밀 변환. 함수, 트리거, 뷰 포함.',
    tags: ['converter', 'mysql', 'postgresql'], version: '3.0.1', downloads: '21.7k',
    installed: true, enabled: true, hasUpdate: false, category: 'converter',
  },
  {
    id: 'mssql-mysql-conv', name: 'MSSQL→MySQL Converter', author: 'DataBridge',
    icon: '🔄', color: '#0ea5e9', official: true,
    desc: 'T-SQL → MySQL 문법 변환기. 저장 프로시저, 함수 자동 변환.',
    tags: ['converter', 'mssql', 'mysql'], version: '2.4.0', downloads: '15.3k',
    installed: false, enabled: false, hasUpdate: false, category: 'converter',
  },
  {
    id: 'charset-fixer', name: 'Charset Fixer', author: 'Community',
    icon: '🔤', color: '#f59e0b', official: false,
    desc: '한글·일본어 등 멀티바이트 문자셋 자동 감지 및 변환. EUC-KR → UTF-8 포함.',
    tags: ['converter', 'charset', 'encoding'], version: '1.1.0', downloads: '4.7k',
    installed: false, enabled: false, hasUpdate: false, category: 'converter',
  },
  {
    id: 'row-count-val', name: 'Row Count Validator', author: 'DataBridge',
    icon: '✅', color: '#10b981', official: true,
    desc: '소스/타겟 Row Count 비교 검증. 테이블별 오차 허용 범위 설정 지원.',
    tags: ['validator', 'rowcount'], version: '2.0.3', downloads: '9.8k',
    installed: true, enabled: true, hasUpdate: false, category: 'validator',
  },
  {
    id: 'checksum-val', name: 'Checksum Validator', author: 'DataBridge',
    icon: '🔍', color: '#6366f1', official: true,
    desc: '컬럼별 해시 비교로 데이터 정합성 검증. MD5/SHA256 선택 가능.',
    tags: ['validator', 'checksum', 'integrity'], version: '1.5.0', downloads: '6.2k',
    installed: false, enabled: false, hasUpdate: false, category: 'validator',
  },
  {
    id: 'slack-notifier', name: 'Slack Notifier', author: 'Community',
    icon: '💬', color: '#e01e5a', official: false,
    desc: 'Job 완료/오류 시 Slack 채널에 자동 알림. Webhook URL 설정만으로 즉시 사용.',
    tags: ['notification', 'slack'], version: '1.0.2', downloads: '2.3k',
    installed: false, enabled: false, hasUpdate: false, category: 'notification',
  },
])

const installedCount = computed(() => PLUGINS.value.filter(p => p.installed).length)
const updateCount    = computed(() => PLUGINS.value.filter(p => p.installed && p.hasUpdate).length)

const filtered = computed(() => {
  let list = PLUGINS.value
  if (activeTab.value === 'installed') list = list.filter(p => p.installed)
  else if (activeTab.value !== 'all') list = list.filter(p => p.category === activeTab.value)
  if (search.value) {
    const q = search.value.toLowerCase()
    list = list.filter(p =>
      p.name.toLowerCase().includes(q) ||
      p.desc.toLowerCase().includes(q) ||
      p.tags.some(t => t.includes(q))
    )
  }
  return list
})

async function doInstall(plugin) {
  installing.value = plugin.id
  await new Promise(r => setTimeout(r, 1200))
  plugin.installed = true
  plugin.enabled   = true
  installing.value = null
  app.notify(`${plugin.name} 설치 완료`, 'success')
}

function doUninstall(plugin) {
  plugin.installed = false
  plugin.enabled   = false
  app.notify(`${plugin.name} 제거됨`, 'info')
}

function doUpdate(plugin) {
  plugin.hasUpdate = false
  app.notify(`${plugin.name} 업데이트 완료`, 'success')
}

function toggle(plugin) {
  plugin.enabled = !plugin.enabled
  app.notify(
    `${plugin.name} ${plugin.enabled ? '활성화' : '비활성화'}됨`,
    plugin.enabled ? 'success' : 'info'
  )
}
</script>

<style scoped>
.toolbar { display:flex; align-items:center; gap:10px; margin-bottom:14px; flex-wrap:wrap; }
.search-wrap { display:flex; align-items:center; gap:6px; background:var(--bg-primary); border:0.5px solid var(--border-mid); border-radius:var(--radius-md); padding:6px 10px; flex:1; min-width:160px; }
.search-wrap svg { color:var(--text-tertiary); flex-shrink:0; }
.search-input { border:none; background:transparent; font-size:12.5px; color:var(--text-primary); font-family:var(--font); outline:none; width:100%; }
.tab-bar { display:flex; gap:4px; }
.tab-btn { font-size:11.5px; font-weight:500; font-family:var(--font); padding:5px 11px; border-radius:var(--radius-md); border:0.5px solid var(--border-mid); background:var(--bg-secondary); color:var(--text-secondary); cursor:pointer; transition:all .12s; }
.tab-btn.active { background:var(--bg-info); color:var(--text-info); border-color:var(--accent-blue); }
.tab-btn:hover:not(.active) { background:var(--bg-primary); color:var(--text-primary); }

.plugin-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:10px; }
.plugin-card { background:var(--bg-primary); border:0.5px solid var(--border-light); border-radius:var(--radius-lg); padding:14px; display:flex; flex-direction:column; gap:10px; transition:border-color .15s; }
.plugin-card:hover { border-color:var(--border-mid); }
.plugin-card.installed { border-color:var(--accent-blue); border-left:2.5px solid var(--accent-blue); }

.plugin-header { display:flex; align-items:center; gap:10px; }
.plugin-icon { width:36px; height:36px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:17px; flex-shrink:0; }
.plugin-meta { flex:1; min-width:0; }
.plugin-name { font-size:12.5px; font-weight:600; color:var(--text-primary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.plugin-author { font-size:10.5px; color:var(--text-tertiary); }
.plugin-badges { display:flex; gap:4px; flex-wrap:wrap; }

.plugin-desc { font-size:11.5px; color:var(--text-secondary); line-height:1.55; flex:1; }
.plugin-tags { display:flex; gap:4px; flex-wrap:wrap; }
.tag { font-size:10px; padding:2px 7px; border-radius:6px; background:var(--bg-secondary); color:var(--text-tertiary); border:0.5px solid var(--border-light); }

.plugin-footer { display:flex; align-items:center; gap:6px; margin-top:auto; }
.plugin-ver { font-size:10px; color:var(--text-tertiary); }
.plugin-dl { font-size:10px; color:var(--text-tertiary); margin-left:2px; }
.plugin-actions { margin-left:auto; display:flex; gap:4px; }
</style>
