<template>
  <aside class="sidebar" :class="{collapsed: app.sidebarCollapsed}">

    <!-- 로고 -->
    <div class="logo">
      <div class="logo-ico">
        <svg viewBox="0 0 16 16" fill="none" stroke="white" stroke-width="1.5" style="width:16px;height:16px">
          <ellipse cx="8" cy="4" rx="5.5" ry="2"/>
          <path d="M2.5 4v4c0 1.1 2.5 2 5.5 2s5.5-.9 5.5-2V4"/>
          <path d="M2.5 8v4c0 1.1 2.5 2 5.5 2s5.5-.9 5.5-2V8"/>
        </svg>
      </div>
      <transition name="fade">
        <div v-if="!app.sidebarCollapsed" class="logo-txt">
          <div class="logo-name">DataBridge</div>
          <div class="logo-sub">Studio v2.0</div>
        </div>
      </transition>
      <button class="collapse-btn" @click="app.toggleSidebar()"
              :title="app.sidebarCollapsed ? '메뉴 펼치기' : '메뉴 접기'">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8"
             :style="{transform: app.sidebarCollapsed ? 'rotate(180deg)' : 'rotate(0deg)', transition:'transform .3s'}">
          <polyline points="10,3 4,8 10,13"/>
        </svg>
      </button>
    </div>

    <!-- 네비게이션 -->
    <nav class="nav">
      <template v-for="sec in menu" :key="sec.label">

        <!-- 섹션 헤더 -->
        <div v-if="!app.sidebarCollapsed" class="sec-header" @click="toggleSection(sec.label)">
          <div class="sec-header-line"/>
          <span class="sec-header-label">{{ sec.label }}</span>
          <div class="sec-header-line"/>
          <svg :style="{transform: openSections[sec.label]===false?'rotate(-90deg)':'rotate(0deg)', transition:'transform .2s'}"
               viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5"
               style="width:9px;height:9px;flex-shrink:0;opacity:.4">
            <polyline points="1,3 5,7 9,3"/>
          </svg>
        </div>
        <div v-else class="sec-divider"/>

        <!-- 아이템들 -->
        <template v-if="openSections[sec.label] !== false">
          <template v-for="item in sec.items" :key="item.to||item.label">
            <router-link v-if="item.to" :to="item.to"
              class="ni"
              :class="{
                'ni-main':  !item.sub,
                'ni-sub':    item.sub && !app.sidebarCollapsed,
                'ni-icon':   app.sidebarCollapsed,
              }"
              active-class="active"
              :title="app.sidebarCollapsed ? item.label : ''">

              <span v-if="!item.sub" class="ni-ico-wrap">
                <svg v-if="item.icon" viewBox="0 0 16 16" fill="none" stroke="currentColor"
                     stroke-width="1.3" v-html="item.icon"
                     style="width:13px;height:13px;flex-shrink:0;display:block"/>
              </span>

              <!-- 서브메뉴 인디케이터 -->
              <span v-if="item.sub && !app.sidebarCollapsed" class="sub-connector">
                <span class="sub-dot"/>
              </span>

              <transition name="fade">
                <span v-if="!app.sidebarCollapsed" class="ni-label"
                      :class="{'ni-label-main': !item.sub, 'ni-label-sub': item.sub}">
                  {{ item.label }}
                </span>
              </transition>

              <transition name="fade">
                <span v-if="!app.sidebarCollapsed && item.badge" class="bdg" :class="'bdg-'+item.bdgType">
                  {{ item.badge }}
                </span>
              </transition>
            </router-link>
          </template>
        </template>

      </template>
    </nav>

    <!-- 푸터 -->
    <div class="sidebar-footer">
      <div class="av">AD</div>
      <transition name="fade">
        <div v-if="!app.sidebarCollapsed" class="user-info">
          <div class="uname">Admin</div>
          <div class="urole">Super Admin</div>
        </div>
      </transition>
      <button class="theme-btn" @click="app.toggleTheme()" title="다크/라이트 전환"
              style="margin-left:auto">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"
             style="width:13px;height:13px">
          <circle cx="8" cy="8" r="3"/>
          <line x1="8" y1="1" x2="8" y2="3"/><line x1="8" y1="13" x2="8" y2="15"/>
          <line x1="1" y1="8" x2="3" y2="8"/><line x1="13" y1="8" x2="15" y2="8"/>
        </svg>
      </button>
    </div>
  </aside>
</template>

<script setup>
import { computed, reactive } from 'vue'
import { useAppStore } from '@/store/appStore.js'
import { useJobStore } from '@/store/jobStore.js'

const app  = useAppStore()
const jobs = useJobStore()
const running = computed(() => jobs.runningJobs?.length || null)

const STORAGE_KEY = 'sidebar_sections'
const _saved = (() => { try { return JSON.parse(localStorage.getItem(STORAGE_KEY)||'{}') } catch { return {} } })()
const openSections = reactive({ ..._saved })

function toggleSection(label) {
  const cur = openSections[label]
  openSections[label] = cur === false ? true : false
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify({...openSections})) } catch {}
}

const ICONS = {
  // 대시보드 - 격자 레이아웃 (세련된 대시보드 느낌)
  dashboard: `<rect x="1" y="1" width="6" height="6" rx="1.5" fill="currentColor" opacity=".2"/>
    <rect x="9" y="1" width="6" height="6" rx="1.5" fill="currentColor" opacity=".15"/>
    <rect x="1" y="9" width="6" height="6" rx="1.5" fill="currentColor" opacity=".15"/>
    <rect x="9" y="9" width="6" height="6" rx="1.5" fill="currentColor" opacity=".2"/>
    <rect x="1" y="1" width="6" height="6" rx="1.5"/>
    <rect x="9" y="1" width="6" height="6" rx="1.5"/>
    <rect x="1" y="9" width="6" height="6" rx="1.5"/>
    <rect x="9" y="9" width="6" height="6" rx="1.5"/>`,

  // 모니터 - 실시간 파형
  monitor: `<rect x="1" y="2" width="14" height="10" rx="2" fill="currentColor" opacity=".1" stroke-width="1.3"/>
    <rect x="1" y="2" width="14" height="10" rx="2" stroke-width="1.3"/>
    <polyline points="2.5,9.5 4.5,6.5 6.5,8.5 9,4 11,7 13,5.5" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
    <line x1="5" y1="14" x2="11" y2="14" stroke-width="1.3" stroke-linecap="round"/>
    <line x1="8" y1="12" x2="8" y2="14" stroke-width="1.3"/>`,

  // 커넥터 - 데이터베이스 원통
  connector: `<ellipse cx="8" cy="4.5" rx="5.5" ry="2" fill="currentColor" opacity=".15" stroke-width="1.3"/>
    <ellipse cx="8" cy="4.5" rx="5.5" ry="2" stroke-width="1.3"/>
    <path d="M2.5 4.5v4c0 1.1 2.5 2 5.5 2s5.5-.9 5.5-2v-4" stroke-width="1.3"/>
    <path d="M2.5 8.5v3c0 1.1 2.5 2 5.5 2s5.5-.9 5.5-2v-3" stroke-width="1.3"/>
    <ellipse cx="8" cy="8.5" rx="5.5" ry="2" fill="currentColor" opacity=".08"/>`,

  // 스키마 - 테이블 구조
  schema: `<rect x="1" y="2" width="14" height="12" rx="1.5" fill="currentColor" opacity=".1" stroke-width="1.3"/>
    <rect x="1" y="2" width="14" height="12" rx="1.5" stroke-width="1.3"/>
    <rect x="1" y="2" width="14" height="4" rx="1.5" fill="currentColor" opacity=".2"/>
    <line x1="1" y1="6" x2="15" y2="6" stroke-width="1.2"/>
    <line x1="6" y1="6" x2="6" y2="14" stroke-width="1"/>
    <line x1="1" y1="9.5" x2="15" y2="9.5" stroke-width=".8" stroke-dasharray="1.5 1"/>`,

  // 타입 매핑 - 화살표 양방향
  mapping: `<rect x="1" y="2" width="5" height="12" rx="1.2" fill="currentColor" opacity=".12" stroke-width="1.3"/>
    <rect x="10" y="2" width="5" height="12" rx="1.2" fill="currentColor" opacity=".12" stroke-width="1.3"/>
    <rect x="1" y="2" width="5" height="12" rx="1.2" stroke-width="1.3"/>
    <rect x="10" y="2" width="5" height="12" rx="1.2" stroke-width="1.3"/>
    <path d="M6.5 6.5 L9.5 6.5 M8.2 5.2 L9.5 6.5 L8.2 7.8" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M9.5 9.5 L6.5 9.5 M7.8 8.2 L6.5 9.5 L7.8 10.8" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>`,

  // 오브젝트 탐색기 - 트리 구조
  explorer: `<circle cx="3.5" cy="3.5" r="2" fill="currentColor" opacity=".2" stroke-width="1.3"/>
    <circle cx="3.5" cy="3.5" r="2" stroke-width="1.3"/>
    <circle cx="12.5" cy="8" r="2" fill="currentColor" opacity=".15" stroke-width="1.2"/>
    <circle cx="12.5" cy="8" r="2" stroke-width="1.2"/>
    <circle cx="12.5" cy="12.5" r="1.7" fill="currentColor" opacity=".15" stroke-width="1.1"/>
    <circle cx="12.5" cy="12.5" r="1.7" stroke-width="1.1"/>
    <path d="M3.5 5.5 v2.5 Q3.5 10 5.5 10 h5" stroke-width="1.2" fill="none" stroke-linecap="round"/>
    <path d="M5.5 10 v2.5 Q5.5 14 7 14 h3.8" stroke-width="1.2" fill="none" stroke-linecap="round"/>`,

  // Job 위저드 - 마법 지팡이/별
  wizard: `<path d="M9 1 L10.5 5.5 L15 7 L10.5 8.5 L9 13 L7.5 8.5 L3 7 L7.5 5.5 Z"
    fill="currentColor" opacity=".15" stroke-width="1.3" stroke-linejoin="round"/>
    <path d="M9 1 L10.5 5.5 L15 7 L10.5 8.5 L9 13 L7.5 8.5 L3 7 L7.5 5.5 Z"
    stroke-width="1.3" stroke-linejoin="round"/>
    <line x1="3" y1="13" x2="1" y2="15" stroke-width="1.4" stroke-linecap="round"/>`,

  // 검증 - 실드 + 체크
  validate: `<path d="M8 1.5 L14 4 V9 C14 12.3 11.2 14.5 8 15.5 C4.8 14.5 2 12.3 2 9 V4 Z"
    fill="currentColor" opacity=".12" stroke-width="1.3" stroke-linejoin="round"/>
    <path d="M8 1.5 L14 4 V9 C14 12.3 11.2 14.5 8 15.5 C4.8 14.5 2 12.3 2 9 V4 Z"
    stroke-width="1.3" stroke-linejoin="round"/>
    <polyline points="5.5,8.5 7.2,10.2 10.8,6.5" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>`,

  // SQL 변환기 - 코드 화살표
  converter: `<rect x="1" y="2" width="14" height="12" rx="1.5" fill="currentColor" opacity=".1" stroke-width="1.3"/>
    <rect x="1" y="2" width="14" height="12" rx="1.5" stroke-width="1.3"/>
    <polyline points="4,6.5 2.5,8 4,9.5" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
    <polyline points="12,6.5 13.5,8 12,9.5" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
    <line x1="9.5" y1="5" x2="6.5" y2="11" stroke-width="1.3" stroke-linecap="round"/>`,

  // 스케줄 - 달력 + 시계
  schedule: `<rect x="1.5" y="3" width="13" height="11.5" rx="1.5" fill="currentColor" opacity=".1" stroke-width="1.3"/>
    <rect x="1.5" y="3" width="13" height="11.5" rx="1.5" stroke-width="1.3"/>
    <rect x="1.5" y="3" width="13" height="3.5" rx="1.5" fill="currentColor" opacity=".2"/>
    <line x1="5.5" y1="1.5" x2="5.5" y2="4.5" stroke-width="1.4" stroke-linecap="round"/>
    <line x1="10.5" y1="1.5" x2="10.5" y2="4.5" stroke-width="1.4" stroke-linecap="round"/>
    <circle cx="8" cy="10.5" r="2.5" stroke-width="1.2"/>
    <polyline points="8,9 8,10.5 9.2,11.2" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>`,

  // 리포트 - 차트 있는 문서
  report: `<rect x="2.5" y="1" width="11" height="14" rx="1.5" fill="currentColor" opacity=".1" stroke-width="1.3"/>
    <rect x="2.5" y="1" width="11" height="14" rx="1.5" stroke-width="1.3"/>
    <line x1="5" y1="5" x2="11" y2="5" stroke-width="1.2" stroke-linecap="round"/>
    <line x1="5" y1="7.5" x2="9" y2="7.5" stroke-width="1.2" stroke-linecap="round"/>
    <polyline points="5,12.5 6.5,10.5 8,11.5 9.5,9.5 11,11" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>`,

  // 설정 - 톱니바퀴
  settings: `<circle cx="8" cy="8" r="2.5" fill="currentColor" opacity=".2" stroke-width="1.3"/>
    <circle cx="8" cy="8" r="2.5" stroke-width="1.3"/>
    <path d="M8 1.5 L8 3 M8 13 L8 14.5 M1.5 8 L3 8 M13 8 L14.5 8
      M3.4 3.4 L4.4 4.4 M11.6 11.6 L12.6 12.6
      M12.6 3.4 L11.6 4.4 M4.4 11.6 L3.4 12.6"
    stroke-width="1.5" stroke-linecap="round"/>`,

  // 플러그인 - 퍼즐 조각
  plugin: `<path d="M2 7 H5.5 C5.5 7 5.5 5.5 7 5.5 C8.5 5.5 8.5 7 8.5 7 H12 V10.5
    C12 10.5 13.5 10.5 13.5 12 C13.5 13.5 12 13.5 12 13.5 V15.5 H2 Z"
    fill="currentColor" opacity=".12" stroke-width="1.3" stroke-linejoin="round"/>
    <path d="M2 7 H5.5 C5.5 7 5.5 5.5 7 5.5 C8.5 5.5 8.5 7 8.5 7 H12 V10.5
    C12 10.5 13.5 10.5 13.5 12 C13.5 13.5 12 13.5 12 13.5 V15.5 H2 Z"
    stroke-width="1.3" stroke-linejoin="round"/>`,
}

const menu = computed(() => [
  { label: 'Overview', items: [
    { to: '/dashboard', label: '대시보드',      badge: 'Live', bdgType: 'g', icon: ICONS.dashboard },
    { to: '/monitor',   label: '실시간 모니터', badge: running.value, bdgType: 'y', icon: ICONS.monitor },
  ]},
  { label: '연결 관리', items: [
    { to: '/connector',          label: '커넥터 관리',    icon: ICONS.connector },
    { to: '/connector/profiles', label: '저장된 프로파일', sub: true },
    { to: '/connector/ssh',      label: 'SSH 터널링',     sub: true },
    { to: '/connector/ssl',      label: 'SSL/TLS 설정',   sub: true },
  ]},
  { label: '스키마 분석', items: [
    { to: '/schema',       label: '스키마 탐색기',      icon: ICONS.schema },
    { to: '/schema/diff',  label: '변환 Diff 미리보기', sub: true },
    { to: '/schema/deps',  label: '객체 의존성 맵',     sub: true },
  ]},
  { label: '매핑 관리', items: [
    { to: '/mapping',         label: '타입 매핑 관리',     icon: ICONS.mapping },
    { to: '/mapping/objects', label: '오브젝트 매핑 관리', sub: true },
  ]},
  { label: '오브젝트 탐색기', items: [
    { to: '/object-explorer', label: '오브젝트 탐색기', icon: ICONS.explorer },
  ]},
  { label: '마이그레이션', items: [
    { to: '/jobs/wizard', label: 'Job 생성 위저드',  icon: ICONS.wizard },
    { to: '/jobs',        label: 'Job 목록 관리',    sub: true, badge: running.value, bdgType: 'y' },
    { to: '/schedules',   label: '스케줄 관리',      icon: ICONS.schedule, badge: 'NEW', bdgType: 'b' },
  ]},
  { label: '데이터 품질', items: [
    { to: '/validate', label: '검증 & 대사', icon: ICONS.validate },
  ]},
  { label: '변환 도구', items: [
    { to: '/sql-converter', label: 'SQL 변환기',    icon: ICONS.converter },
    { to: '/sql-verify',    label: '쿼리 검증 비교', sub: true },
  ]},
  { label: '리포트 & 설정', items: [
    { to: '/report',   label: '실행 리포트',  icon: ICONS.report },
    { to: '/settings', label: '시스템 설정',  icon: ICONS.settings },
    { to: '/plugins',  label: '플러그인',     badge: '48', bdgType: 'b', icon: ICONS.plugin },
  ]},
])
</script>

<style scoped>
/* ── 전체 구조 ── */
.sidebar {
  width: var(--sidebar-w); min-width: var(--sidebar-w);
  background: var(--bg-sidebar, var(--bg-secondary));
  border-right: 1px solid var(--border-light);
  display: flex; flex-direction: column;
  height: 100vh; overflow: hidden;
  transition: width .25s cubic-bezier(.4,0,.2,1), min-width .25s cubic-bezier(.4,0,.2,1);
}
.sidebar.collapsed { width: 56px; min-width: 56px; }

/* ── 로고 ── */
.logo {
  padding: 0 10px;
  border-bottom: 1px solid var(--border-light);
  display: flex; align-items: center; gap: 9px;
  flex-shrink: 0; height: 54px; overflow: hidden;
}
.logo-ico {
  width: 32px; height: 32px; border-radius: 8px; flex-shrink: 0;
  background: linear-gradient(135deg, #1a5fb4 0%, #3584e4 100%);
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 2px 8px rgba(26,95,180,.35);
}
.logo-txt { flex: 1; overflow: hidden; }
.logo-name { font-size: 13px; font-weight: 700; color: var(--text-primary); white-space: nowrap; letter-spacing: -.2px; }
.logo-sub  { font-size: 10px; color: var(--text-tertiary); white-space: nowrap; margin-top: 1px; }
.collapse-btn {
  width: 22px; height: 22px; border-radius: 6px;
  border: 1px solid var(--border-mid); background: transparent;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  color: var(--text-tertiary); flex-shrink: 0; margin-left: auto;
  transition: all .12s;
}
.collapse-btn:hover { background: var(--bg-primary); color: var(--text-primary); }
.collapse-btn svg { width: 11px; height: 11px; }

/* ── 네비게이션 ── */
.nav {
  flex: 1; overflow-y: auto; overflow-x: hidden;
  padding: 6px 0 12px;
}
.nav::-webkit-scrollbar { width: 3px; }
.nav::-webkit-scrollbar-thumb { background: var(--border-mid); border-radius: 2px; }

/* ── 섹션 헤더 ── */
.sec-header {
  display: flex; align-items: center; gap: 6px;
  padding: 10px 10px 4px;
  cursor: pointer; user-select: none;
}
.sec-header:first-child { padding-top: 6px; }
.sec-header-line {
  height: 1px; flex: 1;
  background: var(--border-light);
}
.sec-header-label {
  font-size: 9px; font-weight: 700;
  color: var(--text-tertiary);
  letter-spacing: 1px; text-transform: uppercase;
  white-space: nowrap; flex-shrink: 0;
}
.sec-header:hover .sec-header-label { color: var(--text-secondary); }
.sec-divider {
  height: 1px; margin: 6px 8px;
  background: var(--border-light);
}

/* ── 대메뉴 아이템 ── */
.ni {
  display: flex; align-items: center;
  text-decoration: none; user-select: none;
  white-space: nowrap; overflow: hidden;
  transition: all .1s;
  position: relative;
}

/* 대메뉴 */
.ni.ni-main {
  gap: 9px;
  padding: 0 10px;
  height: 34px;
  font-size: 12.5px; font-weight: 500;
  color: var(--text-secondary);
  border-radius: 0;
}
.ni.ni-main:hover {
  color: var(--text-primary);
  background: var(--bg-primary);
}
.ni.ni-main.active {
  color: var(--text-info);
  background: var(--bg-info);
  font-weight: 600;
}
.ni.ni-main.active .ni-ico-wrap svg { opacity: 1; }
.ni.ni-main.active::before {
  content: '';
  position: absolute; left: 0; top: 4px; bottom: 4px;
  width: 3px; background: var(--accent-blue);
  border-radius: 0 3px 3px 0;
}

/* 서브메뉴 */
.ni.ni-sub {
  gap: 0;
  padding: 0 10px 0 36px;
  height: 28px;
  font-size: 12px; font-weight: 400;
  color: var(--text-tertiary);
}
.ni.ni-sub:hover {
  color: var(--text-primary);
  background: var(--bg-primary);
}
.ni.ni-sub.active {
  color: var(--text-info);
  font-weight: 500;
}
.ni.ni-sub.active .sub-dot {
  background: var(--accent-blue);
  transform: scale(1.3);
}

/* 접힌 상태 */
.ni.ni-icon {
  padding: 8px; justify-content: center;
  height: 38px;
}
.ni.ni-icon:hover { background: var(--bg-primary); }
.ni.ni-icon.active {
  background: var(--bg-info);
  border-radius: 6px;
  margin: 1px 8px;
  width: auto;
}
.ni.ni-icon.active svg { opacity: 1; color: var(--text-info); }

/* 아이콘 래퍼 */
.ni-ico-wrap {
  width: 22px; height: 22px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  border-radius: 6px;
  background: var(--bg-secondary);
  border: 0.5px solid var(--border-light);
  transition: all .12s;
}
.ni.ni-main:hover .ni-ico-wrap {
  background: var(--bg-primary);
  border-color: var(--border-mid);
}
.ni.ni-main.active .ni-ico-wrap {
  background: rgba(59,130,246,.12);
  border-color: rgba(59,130,246,.25);
}
.ni.ni-main svg { opacity: .85; width: 13px; height: 13px; }
.ni.ni-main:hover svg { opacity: 1; }
.ni.ni-main.active svg { opacity: 1; }

/* 아이콘별 테마 색상 */
.ni[href="/dashboard"] .ni-ico-wrap svg,
.ni[href="/dashboard"].active .ni-ico-wrap svg      { color: var(--icon-db,     #6366f1); }
.ni[href="/monitor"] .ni-ico-wrap svg                { color: var(--icon-monitor,#14b8a6); }
.ni[href="/connector"] .ni-ico-wrap svg              { color: var(--icon-conn,   #f59e0b); }
.ni[href="/schema"] .ni-ico-wrap svg                 { color: var(--icon-schema, #3b82f6); }
.ni[href="/mapping"] .ni-ico-wrap svg                { color: var(--icon-map,    #8b5cf6); }
.ni[href="/object-explorer"] .ni-ico-wrap svg        { color: var(--icon-exp,    #06b6d4); }
.ni[href="/jobs/wizard"] .ni-ico-wrap svg            { color: var(--icon-job,    #f97316); }
.ni[href="/validate"] .ni-ico-wrap svg               { color: var(--icon-valid,  #22c55e); }
.ni[href="/sql-converter"] .ni-ico-wrap svg          { color: var(--icon-conv,   #6366f1); }
.ni[href="/schedules"] .ni-ico-wrap svg              { color: var(--icon-sched,  #ec4899); }
.ni[href="/report"] .ni-ico-wrap svg                 { color: var(--icon-rep,    #0ea5e9); }
.ni[href="/settings"] .ni-ico-wrap svg               { color: var(--icon-set,    #64748b); }
.ni[href="/plugins"] .ni-ico-wrap svg                { color: var(--icon-plug,   #a855f7); }

/* 서브 점 + 연결선 */
.sub-connector {
  width: 26px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: flex-end;
  padding-right: 8px;
  position: relative;
}
.sub-connector::before {
  content: '';
  position: absolute;
  left: 8px; top: 50%;
  width: 10px; height: 0;
  border-bottom: 1px solid var(--border-mid);
}
.sub-dot {
  width: 4px; height: 4px; border-radius: 50%;
  background: var(--border-strong);
  flex-shrink: 0;
  transition: all .15s;
}

.ni-label { flex: 1; overflow: hidden; text-overflow: ellipsis; }
.ni-label-main { font-weight: 500; }
.ni-label-sub  { font-size: 12px; }

/* 배지 */
.bdg {
  flex-shrink: 0; font-size: 9.5px; font-weight: 600;
  padding: 1px 5px; border-radius: 6px; letter-spacing: .2px;
}
.bdg-g { background: var(--bg-success); color: var(--text-success); }
.bdg-b { background: var(--bg-info);    color: var(--text-info); }
.bdg-y { background: var(--bg-warning); color: var(--text-warning); }

/* ── 푸터 ── */
.sidebar-footer {
  padding: 8px 10px;
  border-top: 1px solid var(--border-light);
  flex-shrink: 0; display: flex; align-items: center; gap: 8px;
  overflow: hidden;
}
.av {
  width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0;
  background: linear-gradient(135deg, #1a5fb4, #3584e4);
  display: flex; align-items: center; justify-content: center;
  font-size: 10px; font-weight: 700; color: #fff;
  letter-spacing: .5px;
}
.user-info { flex: 1; overflow: hidden; }
.uname { font-size: 12px; font-weight: 600; color: var(--text-primary); white-space: nowrap; }
.urole { font-size: 10px; color: var(--text-tertiary); }
.theme-btn {
  width: 28px; height: 28px; border-radius: 6px;
  border: 1px solid var(--border-mid); background: transparent;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  color: var(--text-tertiary); flex-shrink: 0; transition: all .12s;
}
.theme-btn:hover { background: var(--bg-primary); color: var(--text-primary); }

.fade-enter-active, .fade-leave-active { transition: opacity .15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
