import { createRouter, createWebHistory } from 'vue-router'

const r = (path, comp, title, section='') => ({
  path, component: () => import(`@/pages/${comp}.vue`), meta:{title,section}
})

const routes = [
  {path:'/', redirect:'/dashboard'},
  r('/dashboard',         'Dashboard',        '대시보드',           'Overview'),
  r('/monitor',           'Monitor',          '실시간 모니터',       'Overview'),
  r('/connector',         'Connector',        '커넥터 관리',         '연결 관리'),
  r('/connector/profiles','ConnProfiles',     '저장된 프로파일',     '연결 관리'),
  r('/connector/ssh',     'ConnSSH',          'SSH 터널링',          '연결 관리'),
  r('/connector/ssl',     'ConnSSL',          'SSL/TLS 설정',        '연결 관리'),
  r('/schema',            'Schema',           '스키마 탐색기',       '스키마 분석'),
  r('/schema/tables',     'Schema',           '테이블·컬럼 탐색',    '스키마 분석'),
  r('/schema/diff',       'SchemaDiff',       '변환 Diff 미리보기',  '스키마 분석'),
  r('/schema/deps',       'SchemaDeps',       '객체 의존성 맵',      '스키마 분석'),
  r('/mapping',           'TypeMapping',      '타입 매핑 테이블',    '변환 규칙'),
  r('/mapping/objects',   'ObjectMapping',    '오브젝트 매핑 관리',  '변환 규칙'),
  r('/jobs/wizard',       'JobWizard',        'Job 생성 위저드',     '마이그레이션'),
  r('/jobs',              'JobList',          'Job 관리',            '마이그레이션'),
  r('/jobs/monitor',      'JobMonitor',       '이관 작업 모니터',    '마이그레이션'),
  r('/schedules',        'ScheduleManager',  '스케줄 관리',         '마이그레이션'),
  r('/cdc',               'Cdc',              '증가분 처리',         '마이그레이션'),
  r('/validate',          'Validate',         '검증 & 대사',         '데이터 품질'),
  r('/validate/tables',   'Validate',         '테이블·오브젝트 검증', '데이터 품질'),
  r('/report',            'Report',           '실행 리포트',         '리포트'),
  // v9 패치 #26: 단일 Job 이관 리포트 (새 창 전용)
  { path:'/report/job/:jobId', component: () => import('@/pages/MigrationReport.vue'), meta:{title:'이관 리포트', section:'리포트', standalone:true} },
  r('/settings',          'Settings',         '시스템 설정',         '설정'),
  r('/object-explorer',   'ObjectExplorer',   '오브젝트 탐색기',    '오브젝트 탐색기'),
  r('/sql-converter',      'SqlConverter',     'SQL 쿼리 변환기',     '변환 도구'),
  r('/sql-verify',         'SqlVerify',        '쿼리 검증 비교',      '변환 도구'),
  r('/plugins',           'Plugins',          '플러그인 마켓',       '설정'),
  r('/appearance',        'Appearance',       '모양 및 느낌',       '설정'),
  // 관리자 전용
  r('/admin/users',       'AdminUsers',       '사용자 관리',         '관리자'),
  r('/admin/audit',       'AdminAudit',       '감사 로그',           '관리자'),
  r('/admin/license',     'AdminLicense',     '라이선스 관리',       '관리자'),
  r('/admin/kb',          'AdminKb',          '에러 프롬프트 KB',    '관리자'),
  // v59: 이미 존재하던 AdminKbConversion.vue 페이지가 라우터에 등록 안 돼서 접근 불가 상태였음.
  //      변환 KB(TypeMapping/ObjectMapping) 누적 현황 + AI 호출 추이 대시보드.
  r('/admin/kb/conversion', 'AdminKbConversion','변환 KB 대시보드',   '관리자'),
  // 인증 관련 (네비게이션 메뉴에는 안 나옴)
  r('/login',             'Login',            '로그인',              '인증'),
]

const router = createRouter({ history: createWebHistory(), routes })

// ── 네비게이션 가드 ─────────────────────────────────────
// RBAC 활성 + 비인증 상태면 /login 으로 리다이렉트.
// 로그인 페이지 자체는 가드 생략.
// /admin/* 경로는 admin 역할이 필요.
router.beforeEach(async (to, from) => {
  if (to.path === '/login') return true   // 로그인 화면은 통과

  // authStore를 동적으로 가져옴 (순환 import 방지)
  const { useAuthStore } = await import('@/store/authStore.js')
  const auth = useAuthStore()
  if (!auth.initialized) {
    await auth.init()
  }
  if (!auth.rbacEnabled) return true      // RBAC 비활성이면 무조건 통과
  if (!auth.isAuthenticated) {
    return { path: '/login', query: { next: to.fullPath } }
  }
  // /admin/* 은 admin 역할 필요
  if (to.path.startsWith('/admin/') && !auth.hasRole('admin')) {
    return { path: '/dashboard' }  // 권한 없으면 대시보드로
  }
  return true
})

export default router
