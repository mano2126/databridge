<!--
  ════════════════════════════════════════════════════════════════════
  AdminConsole.vue — 관리자 콘솔 새창 통합 화면 (v95_p89_admin)
  
  본부장님 본질 처방:
    - 메인 화면 (사이드바 + 탑바) 와 분리된 별도 새창
    - 좌측: admin 전용 메뉴 (사용자/감사/라이선스/KB/AI통계/운영매뉴얼/시스템설정)
    - 우측: router-view 로 자식 라우트 컴포넌트 표시 (기존 admin 페이지 재활용)
  
  본부장님 모토:
    - 본질에 충실: 본부장님 환경의 standalone 인프라 그대로 활용
    - 부작용 0: 기존 admin 페이지 컴포넌트 그대로 재사용 (수정 X)
    - 한방에: 좌측 메뉴 + 우측 컨텐츠 = 완전한 관리자 콘솔
    - 하드코딩 0%: 메뉴 항목 배열로 정의, 추가 시 1줄로 가능
  ════════════════════════════════════════════════════════════════════
-->
<template>
  <div class="admin-console" :data-theme="app.theme">
    <!-- 상단 헤더 -->
    <header class="ac-header">
      <div class="ac-title">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:18px;height:18px">
          <circle cx="8" cy="8" r="6"/>
          <path d="M5 8l2 2 4-4" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span>DataBridge 관리자 콘솔</span>
        <span class="ac-badge">{{ authStore.user?.username || '?' }} · {{ authStore.role || '?' }}</span>
      </div>
      <div class="ac-actions">
        <span class="ac-current">{{ route.meta?.title || '관리자' }}</span>
        <button class="ac-close-btn" @click="closeWindow" title="콘솔 닫기 (메인 화면으로)">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" style="width:14px;height:14px">
            <line x1="3" y1="3" x2="13" y2="13"/>
            <line x1="13" y1="3" x2="3" y2="13"/>
          </svg>
          닫기
        </button>
      </div>
    </header>

    <!-- 본문: 좌측 메뉴 + 우측 컨텐츠 -->
    <div class="ac-body">
      <!-- 좌측 admin 메뉴 -->
      <aside class="ac-side">
        <div v-for="grp in MENU_GROUPS" :key="grp.label" class="ac-grp">
          <div class="ac-grp-label">{{ grp.label }}</div>
          <router-link v-for="item in grp.items" :key="item.path"
            :to="item.path"
            class="ac-item"
            active-class="ac-item-active">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"
                 class="ac-item-icon" v-html="item.icon"></svg>
            <span class="ac-item-text">{{ item.label }}</span>
          </router-link>
        </div>
      </aside>

      <!-- 우측 컨텐츠 (router-view) -->
      <main class="ac-content">
        <router-view v-slot="{ Component }">
          <keep-alive>
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/store/appStore.js'
import { useAuthStore } from '@/store/authStore.js'

const route = useRoute()
const app = useAppStore()
const authStore = useAuthStore()

// ── 메뉴 정의 (그룹별) ─────────────────────────────────────
// 새 admin 페이지 추가 시 이 배열에만 한 줄 추가하면 됨.
const MENU_GROUPS = [
  // ════════════════════════════════════════════════════════════════
  // v95_p104 (2026-05-09 본부장님): 프로세스 관리 (최상위)
  //   본부장님 비전 — 엔터프라이즈급 시작/중지/재시작 + 빨간불/초록불
  // ════════════════════════════════════════════════════════════════
  {
    label: '프로세스',
    items: [
      { path: '/admin/console/process',
        label: '백엔드 프로세스',
        icon: '<rect x="2" y="3" width="12" height="10" rx="1"/><circle cx="5" cy="6" r=".7" fill="currentColor"/><line x1="7.5" y1="6" x2="12.5" y2="6"/><line x1="4" y1="9" x2="12" y2="9"/><line x1="4" y1="11" x2="9" y2="11"/>' },
    ]
  },
  {
    label: '사용자 & 감사',
    items: [
      { path: '/admin/console/users',
        label: '사용자 관리',
        icon: '<circle cx="8" cy="6" r="3"/><path d="M2 14c0-3 3-5 6-5s6 2 6 5"/>' },
      { path: '/admin/console/audit',
        label: '감사 로그',
        icon: '<rect x="3" y="2" width="10" height="12" rx="1"/><line x1="5.5" y1="6" x2="10.5" y2="6"/><line x1="5.5" y1="9" x2="10.5" y2="9"/><line x1="5.5" y1="12" x2="9" y2="12"/>' },
      { path: '/admin/console/license',
        label: '라이선스 관리',
        icon: '<rect x="2.5" y="4" width="11" height="8" rx="1"/><circle cx="6" cy="8" r="1.5"/><line x1="9" y1="7" x2="11.5" y2="7"/><line x1="9" y1="9" x2="11.5" y2="9"/>' },
    ]
  },
  {
    label: 'KB 관리',
    items: [
      { path: '/admin/console/kb',
        label: '에러 프롬프트 KB',
        icon: '<path d="M3 3h7l3 3v7H3z"/><line x1="5" y1="6" x2="9" y2="6"/><line x1="5" y1="9" x2="11" y2="9"/>' },
      { path: '/admin/console/kb/conversion',
        label: '변환 KB 대시보드',
        icon: '<path d="M2 13l3-4 3 2 3-5 3 3"/><circle cx="2" cy="13" r="1"/><circle cx="14" cy="9" r="1"/>' },
    ]
  },
  {
    label: 'AI · 운영',
    items: [
      { path: '/admin/console/ai-stats',
        label: 'AI 사용 통계',
        icon: '<rect x="2" y="9" width="2" height="5"/><rect x="6" y="6" width="2" height="8"/><rect x="10" y="3" width="2" height="11"/>' },
      { path: '/admin/console/operator-library',
        label: '운영자 라이브러리',
        icon: '<rect x="3" y="2" width="10" height="12" rx="1"/><line x1="3" y1="5" x2="13" y2="5"/><circle cx="6" cy="9" r=".7"/><line x1="8" y1="9" x2="11" y2="9"/>' },
    ]
  },
  {
    label: '시스템',
    items: [
      { path: '/admin/console/settings',
        label: '시스템 설정',
        icon: '<circle cx="8" cy="8" r="2.5"/><path d="M8 1.5v1M8 13.5v1M1.5 8h1M13.5 8h1M3.4 3.4l.7.7M11.9 11.9l.7.7M3.4 12.6l.7-.7M11.9 4.1l.7-.7"/>' },
    ]
  },
]

// 콘솔 닫기 — 새창이면 window.close, 동일 창이면 메인으로
function closeWindow() {
  // window.opener 가 있으면 새창 → close
  if (window.opener && !window.opener.closed) {
    window.close()
  } else {
    // 같은 창이면 메인 대시보드로
    window.location.href = '/dashboard'
  }
}
</script>

<style scoped>
.admin-console {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: var(--bg-page, #f7f8fa);
  color: var(--text-primary, #1e293b);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* ── 헤더 ─────────────────────────── */
.ac-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  background: var(--bg-card, #fff);
  border-bottom: 1px solid var(--border-color, rgba(0,0,0,.08));
  box-shadow: 0 1px 2px rgba(0,0,0,.03);
  flex-shrink: 0;
}
.ac-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  font-size: 1rem;
  color: var(--text-primary, #1e293b);
}
.ac-badge {
  margin-left: 8px;
  padding: 3px 10px;
  border-radius: 12px;
  background: rgba(99, 102, 241, .1);
  color: #6366f1;
  font-size: .75rem;
  font-weight: 500;
}
.ac-actions {
  display: flex;
  align-items: center;
  gap: 14px;
}
.ac-current {
  font-size: .8rem;
  color: var(--text-secondary, #64748b);
}
.ac-close-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 6px;
  background: transparent;
  border: 1px solid rgba(0,0,0,.12);
  color: var(--text-primary, #1e293b);
  font-size: .82rem;
  cursor: pointer;
  transition: all .12s;
}
.ac-close-btn:hover {
  background: rgba(239, 68, 68, .08);
  border-color: rgba(239, 68, 68, .3);
  color: #dc2626;
}

/* ── 본문 ─────────────────────────── */
.ac-body {
  display: flex;
  flex: 1;
  min-height: 0;
}

/* ── 좌측 메뉴 ────────────────────── */
.ac-side {
  width: 220px;
  flex-shrink: 0;
  padding: 16px 8px;
  background: var(--bg-sidebar, #fff);
  border-right: 1px solid var(--border-color, rgba(0,0,0,.06));
  overflow-y: auto;
}
.ac-grp {
  margin-bottom: 18px;
}
.ac-grp-label {
  padding: 4px 12px 6px;
  font-size: .68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .5px;
  color: var(--text-tertiary, #94a3b8);
}
.ac-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  margin: 1px 0;
  border-radius: 6px;
  color: var(--text-secondary, #475569);
  text-decoration: none;
  font-size: .87rem;
  transition: all .12s;
}
.ac-item:hover {
  background: rgba(99, 102, 241, .06);
  color: var(--text-primary, #1e293b);
}
.ac-item-active {
  background: rgba(99, 102, 241, .12);
  color: #6366f1;
  font-weight: 600;
}
.ac-item-active .ac-item-icon {
  color: #6366f1;
}
.ac-item-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  color: var(--text-tertiary, #94a3b8);
}
.ac-item-active .ac-item-icon {
  color: #6366f1;
}

/* ── 우측 컨텐츠 ──────────────────── */
.ac-content {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: 0;  /* 자식 컴포넌트가 자체 padding 가짐 */
  background: var(--bg-page, #f7f8fa);
}

/* ── 반응형 ───────────────────────── */
@media (max-width: 900px) {
  .ac-side { width: 180px; }
  .ac-header { padding: 10px 14px; }
  .ac-title { font-size: .9rem; }
  .ac-badge { display: none; }
}
</style>
