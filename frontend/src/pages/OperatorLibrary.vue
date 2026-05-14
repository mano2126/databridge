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
      <!-- v95_p107 hotfix_092 (2026-05-13 본부장님): 내 OS 선택 (Win / Mac) -->
      <div class="my-os-toggle" title="내 환경 — 이 OS 의 명령이 강조되어 표시됨">
        <button class="os-chip" :class="{ on: userOS === 'win' }" @click="setUserOS('win')">
          🪟 Win
        </button>
        <button class="os-chip" :class="{ on: userOS === 'mac' }" @click="setUserOS('mac')">
          🍎 Mac
        </button>
      </div>
      <!-- v95_p107 hotfix_093 (2026-05-13 본부장님 본질 처방):
           "화면이 너무 길면 잘리네 — 폭을 가변적으로 조정"
           표시 모드: 내 OS 만 (기본, 폭 100%) / 둘 다 (2단, 비교용) -->
      <div class="view-mode-toggle" title="명령 표시 모드 — 내 OS 만 vs 양쪽 비교">
        <button class="vm-chip" :class="{ on: viewMode === 'single' }"
                @click="viewMode = 'single'" title="내 OS 명령만 (넓게)">
          {{ userOS === 'mac' ? '🍎 Mac만' : '🪟 Win만' }}
        </button>
        <button class="vm-chip" :class="{ on: viewMode === 'both' }"
                @click="viewMode = 'both'" title="Win + Mac 동시 비교">
          📋 둘 다
        </button>
      </div>
      <div class="root-input">
        <label title="프로젝트 ROOT 경로">📁</label>
        <input v-model="root" @input="saveRoot"
               :placeholder="userOS === 'mac' ? '~/project/databridge_full' : 'D:\\project\\databridge_full'"
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

          <!-- 명령 본체 — v95_p107 hotfix_093: viewMode 별 분기 -->
          <div class="cmd-body">
            <!-- SQL 은 OS 무관 — 단일 표시 -->
            <div v-if="cmd.shell === 'sql'" class="cmd-block-wrap">
              <pre class="cmd-block sql-block"><code>{{ convertCmd(cmd, 'mac') }}</code></pre>
              <div class="cmd-actions">
                <button class="chip-action" @click="copyCmdOS(cmd, userOS)">
                  {{ copiedId === cmd.id ? '✓ 복사됨' : '📋 복사' }}
                </button>
              </div>
            </div>
            <!-- 단일 모드 — 내 OS 만 (기본, 폭 100% 사용) -->
            <div v-else-if="viewMode === 'single'" class="cmd-single">
              <div class="cmd-col-hdr">
                <span class="cmd-os-tag" :class="userOS === 'mac' ? 'tag-mac' : 'tag-win'">
                  {{ userOS === 'mac' ? '🍎 macOS (bash/zsh)' : '🪟 Windows (PowerShell)' }}
                </span>
                <span v-if="userOS === 'mac' && cmd.shell !== 'bash' && cmd.shell !== 'sql'"
                      class="cmd-auto-tag" title="원본 PowerShell/CMD 에서 자동 변환됨 — 검증 권장">
                  auto
                </span>
                <span v-if="userOS === 'win' && cmd.shell === 'bash'"
                      class="cmd-auto-tag" title="원본 bash 에서 자동 변환됨 — 검증 권장">
                  auto
                </span>
                <button class="chip-mini-copy" @click="copyCmdOS(cmd, userOS)" title="복사">
                  {{ copiedId === cmd.id + ':' + userOS ? '✓ 복사됨' : '📋 복사' }}
                </button>
                <button class="chip-mini-copy" @click="viewMode = 'both'"
                        title="다른 OS 명령도 함께 보기">
                  ⇄ 둘 다 보기
                </button>
              </div>
              <pre class="cmd-block" :class="userOS === 'mac' ? 'mac-block' : 'win-block'"><code>{{ convertCmd(cmd, userOS) }}</code></pre>
            </div>
            <!-- 비교 모드 — Win / Mac 2단 (또는 좁으면 자동 적층) -->
            <div v-else class="cmd-dual">
              <div class="cmd-col" :class="{ 'is-active-os': userOS === 'win' }">
                <div class="cmd-col-hdr">
                  <span class="cmd-os-tag tag-win">🪟 Windows</span>
                  <button class="chip-mini-copy" @click="copyCmdOS(cmd, 'win')" title="Windows 명령 복사">
                    {{ copiedId === cmd.id + ':win' ? '✓' : '📋' }}
                  </button>
                </div>
                <pre class="cmd-block win-block"><code>{{ convertCmd(cmd, 'win') }}</code></pre>
              </div>
              <div class="cmd-col" :class="{ 'is-active-os': userOS === 'mac' }">
                <div class="cmd-col-hdr">
                  <span class="cmd-os-tag tag-mac">🍎 macOS</span>
                  <span v-if="cmd.shell !== 'bash'" class="cmd-auto-tag" title="원본 PowerShell/CMD 에서 자동 변환됨 — 검증 권장">
                    auto
                  </span>
                  <button class="chip-mini-copy" @click="copyCmdOS(cmd, 'mac')" title="macOS 명령 복사">
                    {{ copiedId === cmd.id + ':mac' ? '✓' : '📋' }}
                  </button>
                </div>
                <pre class="cmd-block mac-block"><code>{{ convertCmd(cmd, 'mac') }}</code></pre>
              </div>
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
import { ref, computed, onMounted, watch } from 'vue'
import { CATEGORIES, COMMANDS } from './operatorLibraryData.js'

defineOptions({ name: 'OperatorLibrary' })

// ════════════════════════════════════════════════════════════
// ROOT 경로 (자동 치환 변수)
// ════════════════════════════════════════════════════════════
const _LS_KEY = 'opLib_rootPath'
const DEFAULT_ROOT = 'D:\\project\\databridge_full'
const root = ref(localStorage.getItem(_LS_KEY) || DEFAULT_ROOT)

// ════════════════════════════════════════════════════════════
// v95_p107 hotfix_092 (2026-05-13 본부장님 본질 처방):
//   "내가 맥을 쓴다는 생각을 못했어. Mac 의 경우 명령을 어떻게 날리는지
//    지금 보여지는 명령을 반으로 나눠서 Windows 와 Mac 으로 쪼개서 보여줘"
//
// 본부장님 환경 = macOS. 기존 데이터 파일 (2595줄, 184 PowerShell 명령) 손대지 않고
// UI 레벨에서 자동 변환 + 좌우 분할 표시.
//
// 감지: 브라우저 navigator.platform 으로 자동 — macOS 면 Mac 우측 / Win 좌측, 
//      Windows 면 Win 좌측 / Mac 우측. 둘 다 한 화면에 보이므로 본부장님이 비교 가능.
// ════════════════════════════════════════════════════════════
function detectOS() {
  const p = (navigator.platform || '').toLowerCase()
  const ua = (navigator.userAgent || '').toLowerCase()
  if (p.includes('mac') || ua.includes('mac os')) return 'mac'
  if (p.includes('win') || ua.includes('windows')) return 'win'
  if (p.includes('linux') || ua.includes('linux')) return 'mac'  // Linux도 bash 와 호환
  return 'mac'  // 본부장님 환경 기본값
}
const userOS = ref(localStorage.getItem('opLib_userOS') || detectOS())
function setUserOS(os) {
  userOS.value = os
  localStorage.setItem('opLib_userOS', os)
}
// v95_p107 hotfix_093 (2026-05-13 본부장님): 표시 모드 — 단일 (내 OS, 기본) / 양쪽 비교
const viewMode = ref(localStorage.getItem('opLib_viewMode') || 'single')
watch(viewMode, (v) => localStorage.setItem('opLib_viewMode', v))
// 본부장님 환경의 macOS ROOT 기본값
const DEFAULT_ROOT_MAC = '~/project/databridge_full'

// ROOT 값 — OS 별로 다르게 표시 (사용자 입력 우선)
const rootForOS = (os) => {
  // 사용자가 본부장님 환경에 맞춰 ROOT 설정해뒀으면 그걸 사용
  // 자동 변환 — Windows ROOT 가 입력돼있고 mac 표시 시 ~로 변환
  const cur = root.value || ''
  if (os === 'mac') {
    if (cur.match(/^[a-zA-Z]:\\/)) return DEFAULT_ROOT_MAC  // Windows 경로 입력 → mac 기본값
    return cur || DEFAULT_ROOT_MAC
  }
  // win
  if (cur.startsWith('~') || cur.startsWith('/')) return DEFAULT_ROOT  // mac 경로 입력 → win 기본값
  return cur || DEFAULT_ROOT
}

// Windows PowerShell/CMD → macOS bash 자동 변환
function winToMac(cmd) {
  if (!cmd) return cmd
  let s = cmd
  // 1. cd /d X:\path → cd path (앞에 mac 경로는 rootForOS 가 처리)
  s = s.replace(/cd\s+\/d\s+/gi, 'cd ')
  // 2. .bat 파일 호출 → 같은 이름의 .sh
  s = s.replace(/(\w+)\.bat/gi, 'bash $1.sh')
  // 3. PowerShell 환경변수 $env:VAR="val" → export VAR="val"
  s = s.replace(/\$env:(\w+)\s*=\s*"([^"]*)"/g, 'export $1="$2"')
  s = s.replace(/\$env:(\w+)\s*=\s*'([^']*)'/g, "export $1='$2'")
  // 4. Get-Process X | Stop-Process -Force → pkill -9 -f X
  s = s.replace(/Get-Process\s+(\S+)\s*\|\s*Stop-Process\s+-Force/gi, 'pkill -9 -f $1')
  // 5. Stop-Process -Id N -Force → kill -9 N
  s = s.replace(/Stop-Process\s+-Id\s+(\d+)\s+-Force/gi, 'kill -9 $1')
  // 6. Get-Process | ... → ps aux | grep ...
  s = s.replace(/Get-Process\s+(\w+)/gi, 'pgrep -af $1')
  // 7. Format-Table → 그대로 두되 주석
  s = s.replace(/\|\s*Format-Table[^\n]*/g, '')
  // 8. Test-Connection X -Count N → ping -c N X
  s = s.replace(/Test-Connection\s+(\S+)\s+-Count\s+(\d+)/gi, 'ping -c $2 $1')
  // 9. Test-NetConnection X -Port N → nc -zv X N
  s = s.replace(/Test-NetConnection\s+(\S+)\s+-Port\s+(\d+)/gi, 'nc -zv $1 $2')
  // 10. Invoke-WebRequest / curl.exe → curl
  s = s.replace(/Invoke-WebRequest/gi, 'curl')
  s = s.replace(/curl\.exe/gi, 'curl')
  // 11. Select-String "X" → grep "X"
  s = s.replace(/\|\s*Select-String\s+/gi, '| grep ')
  // 12. Out-File X → > X
  s = s.replace(/\|\s*Out-File\s+(\S+)/gi, '> $1')
  // 13. dir → ls -la
  s = s.replace(/(?<![\w-])dir(?=\s|$)/g, 'ls -la')
  // 14. type X → cat X
  s = s.replace(/(?<![\w-])type\s+/g, 'cat ')
  // 15. \\ 경로 구분자 → / (단, escape 가 아닌 진짜 backslash 인 경우만)
  //     문자열 안 ${ROOT}\backend 같은 패턴
  s = s.replace(/\\/g, '/')
  // 16. tasklist | findstr X → ps aux | grep X
  s = s.replace(/tasklist\s*\|\s*findstr\s+/gi, 'ps aux | grep ')
  s = s.replace(/tasklist/gi, 'ps aux')
  // 17. findstr → grep
  s = s.replace(/findstr/gi, 'grep')
  // 18. netstat -ano | findstr → lsof -iTCP -sTCP:LISTEN | grep
  s = s.replace(/netstat\s+-ano\s*\|\s*grep\s+:(\d+)/gi, 'lsof -iTCP:$1 -sTCP:LISTEN')
  return s
}

// macOS bash → Windows PowerShell 역변환 (대칭)
function macToWin(cmd) {
  if (!cmd) return cmd
  let s = cmd
  s = s.replace(/(?<![\w-])bash\s+(\w+)\.sh/gi, '$1.bat')
  s = s.replace(/^cd\s+/gm, 'cd /d ')
  s = s.replace(/export\s+(\w+)\s*=\s*"([^"]*)"/g, '$env:$1="$2"')
  s = s.replace(/export\s+(\w+)\s*=\s*'([^']*)'/g, "$env:$1='$2'")
  s = s.replace(/pkill\s+-9\s+-f\s+(\S+)/gi, 'Get-Process $1 | Stop-Process -Force')
  s = s.replace(/kill\s+-9\s+(\d+)/gi, 'Stop-Process -Id $1 -Force')
  s = s.replace(/pgrep\s+-af\s+(\S+)/gi, 'Get-Process $1')
  s = s.replace(/ping\s+-c\s+(\d+)\s+(\S+)/gi, 'Test-Connection $2 -Count $1')
  s = s.replace(/nc\s+-zv\s+(\S+)\s+(\d+)/gi, 'Test-NetConnection $1 -Port $2')
  s = s.replace(/(?<![\w-])ls\s+-la/g, 'dir')
  s = s.replace(/(?<![\w-])cat\s+/g, 'type ')
  s = s.replace(/lsof\s+-iTCP:(\d+)\s+-sTCP:LISTEN/gi, 'netstat -ano | findstr :$1')
  s = s.replace(/\//g, '\\')   // 경로 구분자
  return s
}

// 통합 변환 — 명령의 원래 shell 보고 대상 OS 로 변환
function convertCmd(cmd, targetOs) {
  if (!cmd) return ''
  const origShell = (cmd.shell || '').toLowerCase()
  // SQL 은 OS 무관 — 그대로
  if (origShell === 'sql') return resolveRoot(cmd.cmd, targetOs)
  // 원본이 mac 호환 (bash) 이고 target 이 win 이면 역변환
  if (origShell === 'bash') {
    if (targetOs === 'win') return resolveRoot(macToWin(cmd.cmd), targetOs)
    return resolveRoot(cmd.cmd, targetOs)
  }
  // 원본이 win (powershell/cmd) 이고 target 이 mac 이면 변환
  if (origShell === 'powershell' || origShell === 'cmd') {
    if (targetOs === 'mac') return resolveRoot(winToMac(cmd.cmd), targetOs)
    return resolveRoot(cmd.cmd, targetOs)
  }
  return resolveRoot(cmd.cmd, targetOs)
}

// ROOT 치환 — OS 별
function resolveRoot(text, targetOs) {
  if (!text) return ''
  const r = rootForOS(targetOs)
  return text.replace(/\$\{ROOT\}/g, r)
}

function saveRoot() {
  localStorage.setItem(_LS_KEY, root.value)
}
function resetRoot() {
  // v95_p107 hotfix_092: 사용자 OS 에 맞는 기본값
  root.value = userOS.value === 'mac' ? DEFAULT_ROOT_MAC : DEFAULT_ROOT
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

// v95_p107 hotfix_092: 특정 OS 명령만 복사 (Win/Mac 별 복사 버튼용)
async function copyCmdOS(cmd, os) {
  const text = convertCmd(cmd, os)
  const tag = cmd.id + ':' + os
  try {
    await navigator.clipboard.writeText(text)
    copiedId.value = tag
    setTimeout(() => { if (copiedId.value === tag) copiedId.value = '' }, 1500)
  } catch (e) {
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    try { document.execCommand('copy') } catch {}
    document.body.removeChild(ta)
    copiedId.value = tag
    setTimeout(() => { if (copiedId.value === tag) copiedId.value = '' }, 1500)
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

/* v95_p107 hotfix_092 (2026-05-13 본부장님): Win / Mac 2단 분할 */
/* v95_p107 hotfix_093: 컨테이너 쿼리 + 단일 모드 추가 */
.cmd-body { container-type: inline-size }   /* 카드 폭 기준 반응형 활성화 */
.cmd-single { display: flex; flex-direction: column; gap: 4px; }
.cmd-dual {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
/* 카드 자체 폭이 720px 미만이면 자동 세로 적층 (본부장님 좌측 사이드바 등 좁아져도 안전) */
@container (max-width: 720px) {
  .cmd-dual { grid-template-columns: 1fr; }
}
/* 컨테이너 쿼리 미지원 브라우저 fallback */
@media (max-width: 1100px) {
  .cmd-dual { grid-template-columns: 1fr; }
}
.cmd-col {
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-radius: 5px;
  padding: 4px;
  border: 1px solid transparent;
  transition: border-color .12s, background .12s;
}
.cmd-col.is-active-os {
  border-color: rgba(99, 102, 241, .35);
  background: rgba(99, 102, 241, .04);
}
.cmd-col-hdr {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px;
}
.cmd-os-tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
  font-size: 10.5px;
}
.tag-win { background: #dbeafe; color: #1e40af; border: 1px solid #93c5fd; }
.tag-mac { background: #f3e8ff; color: #6b21a8; border: 1px solid #d8b4fe; }
.cmd-auto-tag {
  font-size: 9.5px;
  padding: 1px 5px;
  border-radius: 3px;
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fde68a;
  font-weight: 600;
  text-transform: uppercase;
}
.chip-mini-copy {
  margin-left: auto;
  padding: 2px 7px;
  background: #fff;
  border: 1px solid #cbd5e1;
  border-radius: 3px;
  cursor: pointer;
  font-size: 11px;
  color: #475569;
  line-height: 1.2;
}
.chip-mini-copy:hover { background: #f1f5f9; color: #1e293b; }
.win-block { background: #0f172a; }
.mac-block { background: #1a1625; }   /* macOS purple-ish 톤 */
.sql-block { background: #1e293b; }

/* v95_p107 hotfix_092: 좌상단 내 OS 토글 */
.my-os-toggle {
  display: inline-flex;
  gap: 2px;
  padding: 2px;
  background: #f1f5f9;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
}
.os-chip {
  padding: 4px 10px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  color: #475569;
  font-weight: 500;
}
.os-chip:hover { color: #1e293b; background: rgba(255,255,255,.6); }
.os-chip.on {
  background: #fff;
  color: #4f46e5;
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0,0,0,.06);
}

/* v95_p107 hotfix_093: 표시 모드 토글 (단일 / 둘 다) */
.view-mode-toggle {
  display: inline-flex;
  gap: 2px;
  padding: 2px;
  background: #f1f5f9;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
  margin-left: 4px;
}
.vm-chip {
  padding: 4px 10px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 11.5px;
  color: #475569;
  font-weight: 500;
}
.vm-chip:hover { color: #1e293b; background: rgba(255,255,255,.6); }
.vm-chip.on {
  background: #fff;
  color: #0891b2;
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0,0,0,.06);
}

/* v95_p107 hotfix_093: 긴 명령 가로 스크롤 보장 (잘림 방지) */
.cmd-block {
  overflow-x: auto;
  white-space: pre;
  min-width: 0;   /* grid item overflow 허용 */
  max-width: 100%;
}
.cmd-col { min-width: 0 }  /* grid item shrink 허용 */
.cmd-block::-webkit-scrollbar { height: 8px }
.cmd-block::-webkit-scrollbar-thumb { background: rgba(255,255,255,.2); border-radius: 4px }

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
