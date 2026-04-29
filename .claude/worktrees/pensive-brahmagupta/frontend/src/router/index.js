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
  r('/schema/diff',       'SchemaDiff',       '변환 Diff 미리보기',  '스키마 분석'),
  r('/schema/deps',       'SchemaDeps',       '객체 의존성 맵',      '스키마 분석'),
  r('/mapping',           'TypeMapping',      '타입 매핑 테이블',    '변환 규칙'),
  r('/mapping/objects',   'ObjectMapping',    '오브젝트 매핑 관리',  '변환 규칙'),
  r('/jobs/wizard',       'JobWizard',        'Job 생성 위저드',     '마이그레이션'),
  r('/jobs',              'JobList',          'Job 관리',            '마이그레이션'),
  r('/jobs/monitor',      'JobMonitor',       '이관 작업 모니터',    '마이그레이션'),
  r('/schedules',        'ScheduleManager',  '스케줄 관리',         '마이그레이션'),
  r('/validate',          'Validate',         '검증 & 대사',         '데이터 품질'),
  r('/report',            'Report',           '실행 리포트',         '리포트'),
  r('/settings',          'Settings',         '시스템 설정',         '설정'),
  r('/object-explorer',   'ObjectExplorer',   '오브젝트 탐색기',    '오브젝트 탐색기'),
  r('/sql-converter',      'SqlConverter',     'SQL 쿼리 변환기',     '변환 도구'),
  r('/sql-verify',         'SqlVerify',        '쿼리 검증 비교',      '변환 도구'),
  r('/plugins',           'Plugins',          '플러그인 마켓',       '설정'),
]

export default createRouter({ history: createWebHistory(), routes })
