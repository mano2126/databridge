<template>
  <div class="audit-page">
    <!-- ─────────── 헤더 ─────────── -->
    <div class="page-header">
      <div>
        <h2>감사 로그 <span class="badge-shield" title="SHA-256 해시 체인으로 변조 방지">🛡️</span></h2>
        <p class="muted">누가 · 언제 · 무엇을 했는지 전부 추적. 금융권 감사 대응용. (admin 전용)</p>
      </div>
      <div class="header-actions">
        <button class="btn-ghost" @click="load" :disabled="loading">
          <span v-if="loading" class="spin">↻</span>
          <span v-else>↻ 새로고침</span>
        </button>
      </div>
    </div>

    <!-- ─────────── 보안 증명 카드 ─────────── -->
    <div class="trust-section">
      <div class="trust-card integrity">
        <div class="trust-header">
          <span class="trust-title">🔗 해시 체인 무결성</span>
          <button class="btn-verify" @click="verifyIntegrity" :disabled="verifying">
            {{ verifying ? '검증 중...' : '검증 실행' }}
          </button>
        </div>
        <div class="trust-body">
          <div v-if="!verifyResult" class="trust-desc">
            모든 감사 레코드는 <b>SHA-256 해시 체인</b>으로 연결됨. 과거 1건만 변조되어도 이후 전부 깨짐 → 즉시 탐지됨.
          </div>
          <div v-else-if="verifyResult.ok" class="trust-ok">
            ✓ 무결성 검증 통과 ·
            검사 {{ verifyResult.total.toLocaleString() }}건
            <span v-if="verifyResult.legacy">(해시 없는 레거시 {{ verifyResult.legacy }}건 제외)</span>
            <span class="trust-ts">· {{ verifyResult._ts }}</span>
          </div>
          <div v-else class="trust-broken">
            ✗ 변조 탐지됨! · 레코드 <code>{{ verifyResult.broken_at }}</code> 에서
            <b>{{ verifyResult.broken_reason }}</b>. 즉시 보안팀 보고 필요.
          </div>
        </div>
      </div>

      <div class="trust-card pii">
        <div class="trust-title">🔒 민감 정보 자동 마스킹</div>
        <div class="trust-desc">
          비밀번호 · 토큰 · API 키 필드는 <code>***REDACTED***</code> 로 저장.
          로그 전체에 주민번호 · 카드번호 · 계좌 · 전화 · 이메일 패턴 전역 마스킹 적용.
        </div>
      </div>

      <div class="trust-card retention">
        <div class="trust-title">📅 보존 정책</div>
        <div class="trust-desc">
          금융권 권장 <b>5년</b> 이상 보존. 관리자가 직접 정리 가능 (아래 "오래된 로그 정리" 버튼).
        </div>
      </div>
    </div>

    <!-- ─────────── 요약 통계 ─────────── -->
    <div class="stats-grid" v-if="stats">
      <div class="stat-card">
        <div class="stat-label">전체 이벤트</div>
        <div class="stat-value">{{ stats.total.toLocaleString() }}</div>
      </div>
      <div class="stat-card ok">
        <div class="stat-label">성공</div>
        <div class="stat-value">{{ (stats.by_status.ok || 0).toLocaleString() }}</div>
      </div>
      <div class="stat-card fail">
        <div class="stat-label">실패</div>
        <div class="stat-value">{{ (stats.by_status.fail || 0).toLocaleString() }}</div>
      </div>
      <div class="stat-card denied">
        <div class="stat-label">차단</div>
        <div class="stat-value">{{ (stats.by_status.denied || 0).toLocaleString() }}</div>
      </div>
    </div>

    <!-- ─────────── 필터 ─────────── -->
    <div class="filters">
      <!-- v10 #22: 사용자 선택 — datalist 로 select+입력 겸용 -->
      <label>
        <span>사용자</span>
        <input list="audit-users" v-model="filters.username"
               placeholder="예: admin  (목록에서 선택 또는 직접 입력)"
               @keyup.enter="applyFilter"/>
        <datalist id="audit-users">
          <option v-for="u in userList" :key="u" :value="u"/>
        </datalist>
      </label>
      <label>
        <span>Action prefix</span>
        <select v-model="filters.action_prefix" @change="applyFilter">
          <option value="">전체</option>
          <option value="auth.">auth.* (인증)</option>
          <option value="user.">user.* (사용자)</option>
          <option value="job.">job.* (이관 Job)</option>
          <option value="profile.">profile.* (프로파일)</option>
          <option value="settings.">settings.* (설정)</option>
          <option value="cdc.">cdc.* (증분)</option>
          <option value="audit.">audit.* (감사)</option>
        </select>
      </label>
      <label>
        <span>상태</span>
        <select v-model="filters.status" @change="applyFilter">
          <option value="">전체</option>
          <option value="ok">성공 (ok)</option>
          <option value="fail">실패 (fail)</option>
          <option value="denied">차단 (denied)</option>
        </select>
      </label>
      <!-- v10 #22: 기간 필터 -->
      <label>
        <span>시작</span>
        <input type="date" v-model="filters.since_date" @change="applyFilter"/>
      </label>
      <label>
        <span>종료</span>
        <input type="date" v-model="filters.until_date" @change="applyFilter"/>
      </label>
      <button class="btn-primary" @click="applyFilter">조회</button>
      <button class="btn-ghost" @click="resetFilters">초기화</button>
      <div style="flex:1"></div>
      <button class="btn-sm-danger" @click="openPurgeDialog">🗑 오래된 로그 정리</button>
    </div>

    <!-- ─────────── 로딩 ─────────── -->
    <div v-if="loading" class="loading">불러오는 중...</div>

    <!-- ─────────── 테이블 ─────────── -->
    <!-- v10 #22b: 테이블 래퍼 — 페이지당 100건 이상 시 세로 스크롤. 우측 레일은 마우스 드래그 스크롤 지원 -->
    <div v-if="!loading" class="table-wrap" ref="tableWrapRef">
      <table class="audit-table">
        <thead>
          <tr>
            <th class="sortable" @click="sortBy('ts')">
              시각 <span class="sort-arrow">{{ sortArrow('ts') }}</span>
            </th>
          <th class="sortable" @click="sortBy('username')">
            사용자 <span class="sort-arrow">{{ sortArrow('username') }}</span>
          </th>
          <th class="sortable" @click="sortBy('role')">
            역할 <span class="sort-arrow">{{ sortArrow('role') }}</span>
          </th>
          <th class="sortable" @click="sortBy('action')">
            Action <span class="sort-arrow">{{ sortArrow('action') }}</span>
          </th>
          <th>리소스</th>
          <th class="sortable" @click="sortBy('status')">
            상태 <span class="sort-arrow">{{ sortArrow('status') }}</span>
          </th>
          <th>IP</th>
          <th>상세</th>
          <th title="해시 체인 연결 확인">🔗</th>
        </tr>
      </thead>
      <tbody>
        <!-- v10 #22: 우클릭 컨텍스트 메뉴 지원 -->
        <tr v-for="item in sortedItems" :key="item.id"
            :class="'row-' + item.status"
            @contextmenu.prevent="openContextMenu($event, item)">
          <td class="ts">{{ fmt(item.ts) }}</td>
          <td>{{ item.username || '—' }}</td>
          <td><span class="role-badge" :class="'role-' + item.role">{{ item.role }}</span></td>
          <td><code>{{ item.action }}</code></td>
          <td>
            {{ item.resource || '—' }}
            <span v-if="item.resource_id" class="rid">#{{ String(item.resource_id).substring(0,8) }}</span>
          </td>
          <td><span class="status-badge" :class="'st-' + item.status">{{ item.status }}</span></td>
          <td class="small">{{ item.ip || '—' }}</td>
          <td>
            <button v-if="item.details && Object.keys(item.details).length"
                    class="btn-link" @click="viewDetails(item)">보기</button>
          </td>
          <td class="hash-cell"
              :title="hashTooltip(item)">
            <span v-if="item.this_hash" class="hash-ok">✓</span>
            <span v-else class="hash-legacy" title="해시 체인 이전 레거시 레코드">–</span>
          </td>
        </tr>
        <tr v-if="!items.length">
          <td colspan="9" class="empty">조건에 맞는 로그가 없습니다.</td>
        </tr>
      </tbody>
    </table>
    <!-- v10 #22b: 우측 드래그 스크롤 레일 — 스크롤바 잡을 필요 없이 이 영역 아무 곳이나 클릭+드래그로 스크롤 -->
    <div class="drag-rail"
         @mousedown="onRailMouseDown"
         title="마우스로 누른 채 위아래로 드래그하면 테이블이 스크롤됩니다">
      <div class="drag-rail-hint">⇅<br/>드래그<br/>스크롤</div>
    </div>
    </div><!-- /.table-wrap -->

    <!-- ─────────── v10 #22: 강화된 페이지네이션 ─────────── -->
    <div v-if="total > 0" class="pagination-bar">
      <div class="page-left">
        <span class="page-info">
          {{ total.toLocaleString() }}건 중
          <b>{{ (offset + 1).toLocaleString() }} – {{ Math.min(offset + limit, total).toLocaleString() }}</b>
        </span>
        <label class="page-size">
          페이지당
          <select v-model.number="limit" @change="changeLimit">
            <option :value="25">25</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
            <option :value="200">200</option>
            <option :value="500">500</option>
          </select>
        </label>
      </div>
      <div class="page-right">
        <button class="btn-page" :disabled="currentPage === 1" @click="gotoPage(1)" title="맨 앞">«</button>
        <button class="btn-page" :disabled="currentPage === 1" @click="gotoPage(currentPage - 1)" title="이전">‹</button>
        <button v-for="p in visiblePages" :key="p"
                class="btn-page"
                :class="{active: p === currentPage}"
                @click="gotoPage(p)">{{ p }}</button>
        <button class="btn-page" :disabled="currentPage === totalPages" @click="gotoPage(currentPage + 1)" title="다음">›</button>
        <button class="btn-page" :disabled="currentPage === totalPages" @click="gotoPage(totalPages)" title="맨 뒤">»</button>
        <span class="page-jump">
          <input type="number" v-model.number="jumpInput" min="1" :max="totalPages"
                 @keyup.enter="gotoPage(jumpInput)"/>
          <span class="of">/ {{ totalPages }}</span>
        </span>
      </div>
    </div>

    <!-- ─────────── 우클릭 컨텍스트 메뉴 ─────────── -->
    <div v-if="ctxMenu.show"
         class="ctx-menu"
         :style="{top: ctxMenu.y + 'px', left: ctxMenu.x + 'px'}"
         @click.stop>
      <div class="ctx-item" @click="ctxCopyCell">📋 셀 값 복사</div>
      <div class="ctx-item" @click="ctxCopyRow">📄 행 전체 복사 (JSON)</div>
      <div class="ctx-sep"></div>
      <div class="ctx-item" @click="ctxFilterBy('username')">👤 이 사용자로 필터</div>
      <div class="ctx-item" @click="ctxFilterBy('action')">🎯 이 action 으로 필터</div>
      <div class="ctx-item" @click="ctxFilterBy('resource_id')">🔖 이 리소스로 필터</div>
      <div class="ctx-sep"></div>
      <div class="ctx-item" @click="viewDetails(ctxMenu.item); closeContextMenu()">🔍 상세 보기</div>
      <div v-if="ctxMenu.item?.this_hash" class="ctx-item"
           @click="showHashInfo(ctxMenu.item); closeContextMenu()">🔗 해시 체인 정보</div>
    </div>

    <!-- ─────────── 상세 다이얼로그 ─────────── -->
    <!-- ─────────── v10 #22c: 상세 다이얼로그 (원본 + 해설) ─────────── -->
    <div v-if="selectedItem" class="modal-backdrop" @click.self="selectedItem=null">
      <div class="modal modal-lg">
        <h3>감사 이벤트 상세</h3>

        <!-- 상단: 이벤트 요약 (읽기 쉬운 한 줄) -->
        <div class="evt-summary" :class="'evt-' + selectedItem.status">
          <div class="evt-summary-title">
            <span class="evt-time">{{ fmt(selectedItem.ts) }}</span>
            <span class="evt-user">{{ selectedItem.username || '(익명)' }}</span>
            <span class="evt-verb">{{ humanAction(selectedItem.action) }}</span>
            <span class="evt-status-chip" :class="'st-' + selectedItem.status">{{ statusText(selectedItem.status) }}</span>
          </div>
          <div class="evt-summary-sub">
            {{ humanSummary(selectedItem) }}
          </div>
        </div>

        <!-- 원본 JSON -->
        <div class="section-label">원본 레코드 (JSON)</div>
        <pre class="json-raw">{{ JSON.stringify(selectedItem.details || {}, null, 2) }}</pre>

        <!-- 필드별 해설 -->
        <div class="section-label">이 이벤트가 의미하는 것</div>
        <table class="explain-table">
          <!-- v95_p32 본질 1 (2026-05-04 본부장님): HTML 표준 위반 처방
               <table> 직속 자식은 <tbody>/<thead>/<tfoot> 만 허용 (Vite 경고 4건+) -->
          <tbody>
          <tr>
            <th>무엇을 했나</th>
            <td>
              <code>{{ selectedItem.action }}</code><br/>
              <span class="mute-small">→ {{ humanAction(selectedItem.action) }}</span>
            </td>
          </tr>
          <tr>
            <th>누가 / 어떤 권한으로</th>
            <td>
              <b>{{ selectedItem.username || '(비로그인·익명)' }}</b>
              <span class="role-badge" :class="'role-' + selectedItem.role">{{ selectedItem.role }}</span>
            </td>
          </tr>
          <tr>
            <th>언제</th>
            <td>{{ fmt(selectedItem.ts) }} <span class="mute-small">(KST)</span></td>
          </tr>
          <tr>
            <th>어디서 (IP)</th>
            <td>{{ selectedItem.ip || '(기록 없음 — 내부 작업이거나 백그라운드 트리거)' }}</td>
          </tr>
          <tr>
            <th>대상 리소스</th>
            <td>
              <span v-if="selectedItem.resource">{{ selectedItem.resource }}</span>
              <span v-if="selectedItem.resource_id"> · <code>{{ selectedItem.resource_id }}</code></span>
              <span v-if="!selectedItem.resource && !selectedItem.resource_id" class="mute-small">(없음)</span>
            </td>
          </tr>
          <tr>
            <th>결과</th>
            <td>
              <span class="status-badge" :class="'st-' + selectedItem.status">{{ selectedItem.status }}</span>
              <span class="mute-small"> · {{ statusText(selectedItem.status) }}</span>
            </td>
          </tr>
          <tr v-for="(v, k) in detailFields" :key="k">
            <th>{{ detailFieldLabel(k) }}</th>
            <td>
              <span v-if="k === 'password' || k.includes('token') || k.includes('secret')" class="masked-chip">
                *** 자동 마스킹됨 (민감정보)
              </span>
              <span v-else>
                <code v-if="typeof v === 'object'">{{ JSON.stringify(v) }}</code>
                <span v-else>{{ v }}</span>
              </span>
              <div class="mute-small">{{ detailFieldExplain(k, v) }}</div>
            </td>
          </tr>
          <tr>
            <th>무결성 해시</th>
            <td>
              <span v-if="selectedItem.this_hash" class="hash-ok">
                ✓ 체인 연결됨 · <code class="hash-short">{{ selectedItem.this_hash.substring(0, 16) }}…</code>
              </span>
              <span v-else class="mute-small">(해시 체인 이전 레거시 레코드)</span>
            </td>
          </tr>
          </tbody>
        </table>

        <div class="modal-actions">
          <button class="btn-ghost" @click="copyItemJson">📋 전체 복사</button>
          <button class="btn-primary" @click="selectedItem=null">닫기</button>
        </div>
      </div>
    </div>

    <!-- ─────────── 해시 정보 다이얼로그 ─────────── -->
    <div v-if="hashInfo" class="modal-backdrop" @click.self="hashInfo=null">
      <div class="modal modal-lg">
        <h3>🔗 해시 체인 정보</h3>
        <p class="muted">이 레코드의 해시 체인 연결 상태입니다. 체인이 깨졌다면 즉시 보안팀에 보고하세요.</p>
        <table class="hash-table">
          <!-- v95_p32 본질 1 (2026-05-04 본부장님): HTML 표준 위반 처방 -->
          <tbody>
          <tr>
            <th>레코드 ID</th>
            <td><code>{{ hashInfo.id }}</code></td>
          </tr>
          <tr>
            <th>이전 해시 (prev)</th>
            <td><code class="hash-short">{{ hashInfo.prev_hash || '(최초 레코드)' }}</code></td>
          </tr>
          <tr>
            <th>이 레코드 해시 (this)</th>
            <td><code class="hash-short">{{ hashInfo.this_hash }}</code></td>
          </tr>
          <tr>
            <th>Action</th>
            <td><code>{{ hashInfo.action }}</code></td>
          </tr>
          <tr>
            <th>시각</th>
            <td>{{ fmt(hashInfo.ts) }}</td>
          </tr>
          </tbody>
        </table>
        <div class="modal-actions">
          <button class="btn-primary" @click="hashInfo=null">닫기</button>
        </div>
      </div>
    </div>

    <!-- ─────────── v10 #22: 개선된 정리 다이얼로그 ─────────── -->
    <div v-if="showPurge" class="modal-backdrop" @click.self="showPurge=false">
      <div class="modal">
        <h3>🗑 오래된 로그 정리</h3>
        <p class="muted">선택한 기준일 이전의 감사 로그를 영구 삭제합니다. 되돌릴 수 없습니다.</p>

        <div class="purge-modes">
          <label class="radio">
            <input type="radio" v-model="purgeMode" value="date"/>
            <span>특정 날짜 이전 삭제</span>
          </label>
          <label class="radio">
            <input type="radio" v-model="purgeMode" value="days"/>
            <span>N일 이전 삭제</span>
          </label>
        </div>

        <div v-if="purgeMode === 'date'" class="purge-input">
          <label>기준 날짜
            <input type="date" v-model="purgeDate" :max="todayISO"/>
          </label>
          <p class="purge-preview" v-if="purgeDate">
            → <b>{{ purgeDate }}</b> 이전 기록 삭제 ({{ purgeDaysFromDate }}일 전)
          </p>
        </div>
        <div v-else class="purge-input">
          <label>보관 기간 (일)
            <input type="number" v-model.number="purgeDays" min="1" max="3650"/>
          </label>
          <p class="purge-preview">
            → 약 <b>{{ purgeDateFromDays }}</b> 이전 기록 삭제
          </p>
        </div>

        <div class="modal-actions">
          <button class="btn-ghost" @click="showPurge=false">취소</button>
          <button class="btn-sm-danger" @click="submitPurge" :disabled="purgeLoading || !purgeDaysComputed">
            {{ purgeLoading ? '삭제 중...' : `${purgeDaysComputed || 0}일 이전 삭제` }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, reactive, computed } from 'vue'

// ─────────── HTTP 헬퍼 ───────────
async function apiGet(path, params = {}) {
  const qs = new URLSearchParams()
  for (const k of Object.keys(params)) {
    if (params[k] !== '' && params[k] != null) qs.set(k, params[k])
  }
  const q = qs.toString()
  const url = `/api/v1${path}${q ? '?' + q : ''}`
  const token = localStorage.getItem('databridge_auth_token') || ''
  const r = await fetch(url, { headers: { 'X-Auth-Token': token } })
  if (!r.ok) throw new Error(`${r.status}`)
  return r.json()
}
async function apiDelete(path, params = {}) {
  const qs = new URLSearchParams()
  for (const k of Object.keys(params)) {
    if (params[k] !== '' && params[k] != null) qs.set(k, params[k])
  }
  const q = qs.toString()
  const url = `/api/v1${path}${q ? '?' + q : ''}`
  const token = localStorage.getItem('databridge_auth_token') || ''
  const r = await fetch(url, { method: 'DELETE', headers: { 'X-Auth-Token': token } })
  if (!r.ok) throw new Error(`${r.status}`)
  return r.json()
}

// ─────────── 상태 ───────────
const filters = reactive({
  username: '', action_prefix: '', status: '',
  since_date: '', until_date: '',
})
const items   = ref([])
const total   = ref(0)
const offset  = ref(0)
const limit   = ref(50)
const loading = ref(false)
const stats   = ref(null)
const userList = ref([])        // datalist 용

// 정렬 (클라이언트 측)
const sortKey = ref('ts')
const sortDir = ref('desc')
function sortBy(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'desc'
  }
}
function sortArrow(key) {
  if (sortKey.value !== key) return ''
  return sortDir.value === 'asc' ? '▲' : '▼'
}
const sortedItems = computed(() => {
  const arr = [...items.value]
  const k = sortKey.value
  const dir = sortDir.value === 'asc' ? 1 : -1
  arr.sort((a, b) => {
    const va = a?.[k] ?? ''
    const vb = b?.[k] ?? ''
    if (va < vb) return -1 * dir
    if (va > vb) return 1 * dir
    return 0
  })
  return arr
})

// 모달
// v10 #22c: 상세 모달에 action/user/시각/해시까지 전부 표시하도록
// details 만 담던 selectedDetails 를 item 전체 담는 selectedItem 으로 변경.
const selectedItem = ref(null)
const hashInfo = ref(null)
const showPurge   = ref(false)
const purgeMode   = ref('days')      // 'days' | 'date'
const purgeDays   = ref(90)
const purgeDate   = ref('')
const purgeLoading = ref(false)

// 무결성 검증
const verifying = ref(false)
const verifyResult = ref(null)

// 우클릭 컨텍스트 메뉴
const ctxMenu = reactive({ show: false, x: 0, y: 0, item: null, cellText: '' })

// v10 #22b: 우측 레일 드래그 스크롤
const tableWrapRef = ref(null)
const railDrag = reactive({ active: false, startY: 0, startScroll: 0 })
function onRailMouseDown(e) {
  if (e.button !== 0) return   // 좌클릭만
  if (!tableWrapRef.value) return
  railDrag.active = true
  railDrag.startY = e.clientY
  railDrag.startScroll = tableWrapRef.value.scrollTop
  document.body.style.cursor = 'ns-resize'
  document.body.style.userSelect = 'none'
  window.addEventListener('mousemove', onRailMouseMove)
  window.addEventListener('mouseup',   onRailMouseUp)
  e.preventDefault()
}
function onRailMouseMove(e) {
  if (!railDrag.active || !tableWrapRef.value) return
  const dy = e.clientY - railDrag.startY
  // 1:1 비율 대신 테이블 총 스크롤 높이 / 레일 높이 비례로 빠르게 스크롤
  const wrap = tableWrapRef.value
  const railHeight = Math.max(1, wrap.clientHeight)
  const scrollable = wrap.scrollHeight - wrap.clientHeight
  const ratio = scrollable / railHeight
  wrap.scrollTop = railDrag.startScroll + dy * Math.max(1, ratio)
}
function onRailMouseUp() {
  railDrag.active = false
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
  window.removeEventListener('mousemove', onRailMouseMove)
  window.removeEventListener('mouseup',   onRailMouseUp)
}

// ─────────── 페이지네이션 ───────────
const jumpInput = ref(1)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / limit.value)))
const currentPage = computed(() => Math.floor(offset.value / limit.value) + 1)
// v10 #22b: 상용 솔루션 표준 10버튼 슬라이딩 윈도우
// 예) 1/40 → [1 2 3 4 5 6 7 8 9 10]
//    7/40 → [1 2 3 4 5 6 7 8 9 10]   (아직 왼쪽 이동 없음)
//   15/40 → [11 12 13 14 15 16 17 18 19 20]
//   37/40 → [31 32 33 34 35 36 37 38 39 40]
const visiblePages = computed(() => {
  const cur = currentPage.value, tot = totalPages.value
  const size = 10
  if (tot <= size) return Array.from({length: tot}, (_, i) => i + 1)
  // 현재 페이지가 속한 10-단위 윈도우의 시작
  let start = Math.floor((cur - 1) / size) * size + 1
  let end = Math.min(tot, start + size - 1)
  // 마지막 윈도우라 10개 미만이면 채워서 10개 맞춤
  if (end - start + 1 < size) start = Math.max(1, end - size + 1)
  const pages = []
  for (let p = start; p <= end; p++) pages.push(p)
  return pages
})
function gotoPage(p) {
  const tgt = Math.max(1, Math.min(totalPages.value, Number(p) || 1))
  offset.value = (tgt - 1) * limit.value
  jumpInput.value = tgt
  load()
}
function changeLimit() {
  offset.value = 0
  jumpInput.value = 1
  load()
}

// ─────────── 필터 ───────────
function applyFilter() {
  offset.value = 0
  jumpInput.value = 1
  load()
}
function resetFilters() {
  filters.username = ''
  filters.action_prefix = ''
  filters.status = ''
  filters.since_date = ''
  filters.until_date = ''
  offset.value = 0
  jumpInput.value = 1
  load()
}

// ─────────── 데이터 로드 ───────────
function toEpoch(isoDate) {
  if (!isoDate) return null
  return Math.floor(new Date(isoDate + 'T00:00:00').getTime() / 1000)
}
async function load() {
  loading.value = true
  try {
    const params = {
      username:       filters.username,
      action_prefix:  filters.action_prefix,
      status:         filters.status,
      since_epoch:    toEpoch(filters.since_date),
      until_epoch:    filters.until_date ? toEpoch(filters.until_date) + 86400 : null,
      limit:  limit.value,
      offset: offset.value,
    }
    const r = await apiGet('/audit/logs', params)
    items.value = r.items
    total.value = r.total
    const s = await apiGet('/audit/stats')
    stats.value = s
  } catch (e) {
    console.error(e)
  } finally { loading.value = false }
}

// 사용자 목록 로드 (datalist)
async function loadUsers() {
  try {
    const r = await apiGet('/auth/users')
    // 감사 로그에서 본 사용자명도 추가 — 삭제된 사용자도 포함
    const fromAudit = new Set((items.value || []).map(i => i.username).filter(Boolean))
    const usernames = new Set()
    if (Array.isArray(r)) r.forEach(u => u?.username && usernames.add(u.username))
    else if (r?.users) r.users.forEach(u => u?.username && usernames.add(u.username))
    fromAudit.forEach(u => usernames.add(u))
    userList.value = [...usernames].sort()
  } catch (e) {
    // /auth/users 실패해도 감사 로그에서 본 사용자명으로라도 채움
    userList.value = [...new Set((items.value || []).map(i => i.username).filter(Boolean))].sort()
  }
}

// ─────────── 무결성 검증 ───────────
async function verifyIntegrity() {
  verifying.value = true
  try {
    const r = await apiGet('/audit/verify')
    r._ts = new Date().toLocaleString('ko-KR')
    verifyResult.value = r
  } catch (e) {
    verifyResult.value = {
      ok: false, total: 0, legacy: 0,
      broken_at: '요청 실패',
      broken_reason: e.message || String(e),
      _ts: new Date().toLocaleString('ko-KR'),
    }
  } finally { verifying.value = false }
}

// ─────────── 우클릭 컨텍스트 메뉴 ───────────
function openContextMenu(evt, item) {
  // 클릭된 셀의 텍스트 저장
  const td = evt.target.closest('td')
  ctxMenu.cellText = td ? (td.innerText || '').trim() : ''
  ctxMenu.item = item
  // 메뉴 위치 (화면 밖으로 안 나가게 제한)
  const maxX = window.innerWidth - 220
  const maxY = window.innerHeight - 320
  ctxMenu.x = Math.min(evt.clientX, maxX)
  ctxMenu.y = Math.min(evt.clientY, maxY)
  ctxMenu.show = true
}
function closeContextMenu() {
  ctxMenu.show = false
  ctxMenu.item = null
}
function ctxCopyCell() {
  navigator.clipboard.writeText(ctxMenu.cellText || '').catch(() => {})
  closeContextMenu()
}
function ctxCopyRow() {
  if (!ctxMenu.item) return
  navigator.clipboard.writeText(JSON.stringify(ctxMenu.item, null, 2)).catch(() => {})
  closeContextMenu()
}
function ctxFilterBy(field) {
  const item = ctxMenu.item
  if (!item) return
  if (field === 'username') filters.username = item.username || ''
  else if (field === 'action') filters.action_prefix = (item.action || '').split('.')[0] + '.'
  else if (field === 'resource_id') {
    // 정확 매칭은 백엔드가 지원하지 않아서 username + action_prefix 조합으로 대체
    // 사용자에게 안내
    if (item.resource_id) {
      filters.action_prefix = (item.resource ? item.resource + '.' : '')
    }
  }
  closeContextMenu()
  applyFilter()
}
function showHashInfo(item) {
  hashInfo.value = item
}
function hashTooltip(item) {
  if (!item.this_hash) return '해시 체인 이전 레거시 레코드'
  const prev = (item.prev_hash || '(최초)').substring(0, 16)
  const ths  = item.this_hash.substring(0, 16)
  return `prev: ${prev}…\nthis: ${ths}…\n(우클릭 → 해시 체인 정보)`
}

// ─────────── 오래된 로그 정리 ───────────
const todayISO = computed(() => new Date().toISOString().slice(0, 10))
const purgeDaysFromDate = computed(() => {
  if (!purgeDate.value) return 0
  const diff = Date.now() - new Date(purgeDate.value + 'T00:00:00').getTime()
  return Math.max(1, Math.floor(diff / 86400000))
})
const purgeDateFromDays = computed(() => {
  const d = new Date(Date.now() - purgeDays.value * 86400000)
  return d.toISOString().slice(0, 10)
})
const purgeDaysComputed = computed(() => {
  return purgeMode.value === 'date' ? purgeDaysFromDate.value : purgeDays.value
})

function openPurgeDialog() {
  purgeMode.value = 'days'
  purgeDays.value = 90
  purgeDate.value = ''
  showPurge.value = true
}
async function submitPurge() {
  const days = purgeDaysComputed.value
  if (!days) return
  if (!confirm(`${days}일 이전 (약 ${new Date(Date.now() - days*86400000).toLocaleDateString('ko-KR')} 이전) 감사 로그를 영구 삭제합니다.\n정말 계속하시겠습니까?`)) return
  purgeLoading.value = true
  try {
    const r = await apiDelete('/audit/purge', { days })
    alert(`${r.removed.toLocaleString()}건 삭제되었습니다.`)
    showPurge.value = false
    await load()
  } catch (e) {
    alert('삭제 실패: ' + e.message)
  } finally { purgeLoading.value = false }
}

// ─────────── v10 #22c: 사람이 읽을 수 있는 해설 ───────────
// ─── 상세 모달 열기 / 복사 ───
function viewDetails(item) {
  selectedItem.value = item
}
function copyItemJson() {
  if (!selectedItem.value) return
  navigator.clipboard.writeText(JSON.stringify(selectedItem.value, null, 2)).catch(() => {})
}

// action 코드 → 한국어 동사. 없는 키는 원문 그대로.
const ACTION_MAP = {
  // 인증
  'auth.login.success':   '로그인 성공',
  'auth.login.fail':      '로그인 실패',
  'auth.logout':          '로그아웃',
  'auth.denied':          '인증 거부 (권한 부족 또는 토큰 만료)',
  'auth.password.change': '비밀번호 변경',
  'auth.password.reset':  '관리자에 의한 비밀번호 재설정',
  // 사용자
  'user.create':   '신규 사용자 생성',
  'user.update':   '사용자 정보 수정',
  'user.disable':  '사용자 비활성화',
  'user.enable':   '사용자 활성화',
  'user.delete':   '사용자 삭제',
  // Job
  'job.create':        '이관 Job 생성',
  'job.start':         '이관 Job 실행 시작',
  'job.stop':          '이관 Job 중지',
  'job.delete':        '이관 Job 삭제',
  'job.bulk.delete':   '이관 Job 일괄 삭제',
  'job.restart':       '이관 Job 재실행',
  'job.resume':        '이관 Job 재개 (중단 지점부터)',
  // 프로파일
  'profile.create':    '연결 프로파일 생성',
  'profile.update':    '연결 프로파일 수정',
  'profile.delete':    '연결 프로파일 삭제',
  // 설정
  'settings.update':   '시스템 설정 변경',
  // CDC
  'cdc.run.start':     'CDC 증분 감시 시작',
  'cdc.run.complete':  'CDC 증분 감시 완료',
  'cdc.run.fail':      'CDC 증분 감시 실패',
  // 감사 로그 자체
  'audit.purge':       '감사 로그 일괄 정리',
}
function humanAction(code) {
  if (!code) return ''
  if (ACTION_MAP[code]) return ACTION_MAP[code]
  // 알려지지 않은 code 라도 패밀리(prefix) 만 해석
  const prefix = code.split('.')[0]
  const family = {
    auth: '인증 관련', user: '사용자 관련', job: '이관 관련',
    profile: '프로파일 관련', settings: '설정 관련',
    cdc: 'CDC 관련', audit: '감사 관련',
  }[prefix]
  return family ? `${family} 이벤트 (${code})` : code
}
function statusText(s) {
  return ({
    ok:     '정상 처리됨',
    fail:   '실패 — 처리 중 에러',
    denied: '차단됨 — 권한 없음',
  })[s] || s
}
function humanSummary(item) {
  const who = item.username || '익명'
  const act = humanAction(item.action)
  const rid = item.resource_id ? ` (${item.resource || ''} #${String(item.resource_id).substring(0, 8)})` : ''
  if (item.status === 'ok')     return `${who} 님이 ${act}${rid} 을 수행했습니다.`
  if (item.status === 'fail')   return `${who} 님의 ${act}${rid} 시도가 실패했습니다.`
  if (item.status === 'denied') return `${who} 님의 ${act}${rid} 시도가 권한 부족으로 차단되었습니다.`
  return `${who} · ${act}${rid}`
}

// details 필드 해설
const DETAIL_LABEL = {
  name:     '이관 Job 이름',
  src_db:   '소스 DB',
  tgt_db:   '타겟 DB',
  tables:   '선택된 테이블 수',
  role:     '부여된 역할',
  days:     '보관 기간 (일)',
  removed:  '삭제된 레코드 수',
  reason:   '사유',
  method:   'HTTP 메서드',
  path:     '요청 경로',
  required_role: '필요했던 권한',
  user_role:     '현재 사용자 권한',
}
function detailFieldLabel(k) { return DETAIL_LABEL[k] || k }
function detailFieldExplain(k, v) {
  if (k === 'src_db' || k === 'tgt_db') return `DB 종류 (${v})`
  if (k === 'tables') return `${v}개 테이블 선택됨`
  if (k === 'role')   return `${v} 권한으로 생성·변경됨`
  if (k === 'removed') return `${v}건이 영구 삭제됨`
  if (k === 'days')    return `${v}일 이전 레코드 대상`
  return ''
}

const detailFields = computed(() => {
  if (!selectedItem.value?.details) return {}
  // 이미 상단 표에 나온 항목은 중복 안 보이게 필터
  const skip = new Set(['ip', 'ts', 'username', 'role', 'action', 'resource', 'resource_id', 'status'])
  const out = {}
  for (const [k, v] of Object.entries(selectedItem.value.details)) {
    if (!skip.has(k)) out[k] = v
  }
  return out
})

// ─────────── 포맷 ───────────
function fmt(iso) {
  if (!iso) return ''
  return iso.substring(0, 19).replace('T', ' ')
}

// ─────────── 라이프사이클 ───────────
function onGlobalClick() {
  if (ctxMenu.show) closeContextMenu()
}
function onEsc(e) {
  if (e.key === 'Escape') {
    closeContextMenu()
    if (selectedItem.value) selectedItem.value = null
    if (hashInfo.value) hashInfo.value = null
    if (showPurge.value) showPurge.value = false
  }
}
onMounted(async () => {
  await load()
  await loadUsers()
  window.addEventListener('click', onGlobalClick)
  window.addEventListener('keydown', onEsc)
})
onUnmounted(() => {
  window.removeEventListener('click', onGlobalClick)
  window.removeEventListener('keydown', onEsc)
})
</script>

<style scoped>
.audit-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 16px; }
.page-header h2 { margin: 0; display: inline-flex; align-items: center; gap: 8px; }
.badge-shield { font-size: 18px; filter: drop-shadow(0 1px 2px rgba(0,0,0,.1)); }
.muted { color: var(--text-tertiary); font-size: 12px; margin: 4px 0 0; }
.spin { display: inline-block; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ─── 보안 증명 카드 ─── */
.trust-section { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin: 12px 0 20px; }
.trust-card { background: var(--bg-primary); border: 1px solid var(--border-light); border-radius: 8px; padding: 14px; }
.trust-card.integrity { border-left: 3px solid #2563eb; }
.trust-card.pii       { border-left: 3px solid #16a34a; }
.trust-card.retention { border-left: 3px solid #d97706; }
.trust-header { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 6px; }
.trust-title { font-size: 13px; font-weight: 600; }
.trust-desc  { font-size: 12px; color: var(--text-secondary); line-height: 1.5; }
.trust-ok    { font-size: 12px; color: #15803d; font-weight: 500; }
.trust-broken{ font-size: 12px; color: #b91c1c; font-weight: 600; }
.trust-ts    { color: var(--text-tertiary); font-weight: 400; margin-left: 6px; }
.btn-verify  { padding: 4px 10px; border: 1px solid #2563eb; background: #fff; color: #2563eb; border-radius: 4px; font-size: 11px; cursor: pointer; font-weight: 500; }
.btn-verify:hover:not(:disabled) { background: #2563eb; color: #fff; }
.btn-verify:disabled { opacity: .5; cursor: not-allowed; }

/* ─── 통계 ─── */
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.stat-card { background: var(--bg-primary); border: 1px solid var(--border-light); border-radius: 8px; padding: 12px 16px; }
.stat-card.ok     { border-left: 3px solid #16a34a; }
.stat-card.fail   { border-left: 3px solid #dc2626; }
.stat-card.denied { border-left: 3px solid #d97706; }
.stat-label { font-size: 11px; color: var(--text-tertiary); }
.stat-value { font-size: 22px; font-weight: 700; margin-top: 4px; }

/* ─── 필터 ─── */
.filters { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; align-items: flex-end; }
.filters label { display: flex; flex-direction: column; font-size: 11px; color: var(--text-tertiary); gap: 3px; }
.filters input, .filters select { padding: 6px 10px; border: 1px solid var(--border-light); border-radius: 4px; font-size: 12px; min-width: 120px; font-family: var(--font); }
.btn-primary  { padding: 7px 14px; background: #2563eb; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: 500; }
.btn-ghost    { padding: 7px 14px; background: transparent; border: 1px solid var(--border-light); border-radius: 4px; cursor: pointer; font-size: 12px; }
.btn-ghost:disabled { opacity: .5; cursor: not-allowed; }
.btn-sm-danger{ padding: 7px 14px; background: #fee; border: 1px solid #fcc; color: #c00; border-radius: 4px; cursor: pointer; font-size: 12px; }

.loading { padding: 40px; text-align: center; color: var(--text-tertiary); }

/* ─── 테이블 ─── */
/* v10 #22b: 래퍼 — 세로 스크롤 영역. 우측 드래그 레일 공간 확보 */
.table-wrap { position: relative; max-height: 65vh; overflow-y: auto; border: 1px solid var(--border-light); border-radius: 8px; background: var(--bg-primary); padding-right: 36px; }
.table-wrap .audit-table { border: none; border-radius: 0; }
.table-wrap .audit-table thead th { position: sticky; top: 0; z-index: 2; }

/* 드래그 스크롤 레일 */
.drag-rail {
  position: absolute; top: 0; right: 0; width: 32px; height: 100%;
  background: linear-gradient(to left, var(--bg-secondary, #f3f4f6), transparent);
  cursor: ns-resize; user-select: none;
  display: flex; align-items: center; justify-content: center;
  border-left: 1px dashed var(--border-light);
  transition: background 0.15s;
}
.drag-rail:hover { background: linear-gradient(to left, #e0e7ff, rgba(224, 231, 255, 0.3)); }
.drag-rail:active { background: linear-gradient(to left, #c7d2fe, rgba(199, 210, 254, 0.4)); }
.drag-rail-hint {
  font-size: 9px; line-height: 1.35; text-align: center;
  color: var(--text-tertiary); letter-spacing: .5px;
  pointer-events: none;
}
.audit-table { width: 100%; border-collapse: collapse; background: var(--bg-primary); border: 1px solid var(--border-light); border-radius: 8px; overflow: hidden; }
.audit-table th, .audit-table td { padding: 8px 12px; text-align: left; font-size: 12px; border-bottom: 1px solid var(--border-light); }
.audit-table th { background: var(--bg-secondary); font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: .5px; color: var(--text-secondary); }
.audit-table th.sortable { cursor: pointer; user-select: none; }
.audit-table th.sortable:hover { background: var(--bg-tertiary, #f0f2f5); }
.sort-arrow { margin-left: 4px; font-size: 10px; color: #2563eb; }
.audit-table tbody tr:hover { background: var(--bg-secondary); }
.audit-table tbody tr.row-fail   { background: #fef2f2; }
.audit-table tbody tr.row-denied { background: #fffbeb; }
.ts { font-family: var(--font-mono, monospace); white-space: nowrap; font-size: 11px; }
.small { font-size: 11px; color: var(--text-tertiary); }
.empty { text-align: center; padding: 40px; color: var(--text-tertiary); font-style: italic; }
.rid { color: var(--text-tertiary); font-size: 11px; margin-left: 3px; }
.role-badge, .status-badge { padding: 2px 7px; border-radius: 3px; font-size: 10.5px; font-weight: 500; }
.role-admin     { background: #fee; color: #c00; }
.role-operator  { background: #eef; color: #339; }
.role-viewer    { background: #eef2f7; color: #667; }
.role-anonymous { background: #eee; color: #999; }
.st-ok     { background: #dcfce7; color: #15803d; }
.st-fail   { background: #fee2e2; color: #b91c1c; }
.st-denied { background: #fef3c7; color: #b45309; }
.btn-link { background: none; border: none; color: #2563eb; cursor: pointer; font-size: 12px; text-decoration: underline; padding: 0; }
.hash-cell { text-align: center; cursor: help; }
.hash-ok { color: #16a34a; font-weight: bold; }
.hash-legacy { color: var(--text-tertiary); }

/* ─── 페이지네이션 ─── */
.pagination-bar { display: flex; justify-content: space-between; align-items: center; padding: 14px 8px; flex-wrap: wrap; gap: 12px; }
.page-left, .page-right { display: flex; align-items: center; gap: 6px; flex-wrap: nowrap; }
.page-info { font-size: 12px; color: var(--text-secondary); white-space: nowrap; }
.page-size { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-tertiary); white-space: nowrap; }
.page-size > span { white-space: nowrap; }
.page-size select { padding: 4px 6px; font-size: 12px; border: 1px solid var(--border-light); border-radius: 3px; background: var(--bg-primary); }
.btn-page { min-width: 30px; padding: 4px 8px; background: var(--bg-primary); border: 1px solid var(--border-light); border-radius: 3px; cursor: pointer; font-size: 12px; font-family: var(--font); }
.btn-page:hover:not(:disabled) { background: var(--bg-secondary); border-color: #93c5fd; }
.btn-page.active { background: #2563eb; color: #fff; border-color: #2563eb; font-weight: 600; }
.btn-page:disabled { opacity: .35; cursor: not-allowed; }
.page-jump { display: inline-flex; align-items: center; gap: 4px; margin-left: 10px; font-size: 11px; color: var(--text-tertiary); white-space: nowrap; }
.page-jump input { width: 44px; padding: 3px 6px; border: 1px solid var(--border-light); border-radius: 3px; font-size: 12px; text-align: center; }
.page-jump .of { white-space: nowrap; }

/* ─── 우클릭 메뉴 ─── */
.ctx-menu { position: fixed; min-width: 200px; background: var(--bg-primary); border: 1px solid var(--border-light); border-radius: 6px; box-shadow: 0 4px 16px rgba(0,0,0,.12); padding: 4px 0; z-index: 9999; font-size: 12px; }
.ctx-item { padding: 7px 14px; cursor: pointer; user-select: none; }
.ctx-item:hover { background: #f0f4ff; }
.ctx-sep { height: 1px; background: var(--border-light); margin: 4px 0; }

/* ─── 모달 ─── */
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: var(--bg-primary); padding: 24px; border-radius: 8px; min-width: 460px; max-width: 760px; max-height: 86vh; overflow-y: auto; }
.modal.modal-lg { min-width: 620px; }
.modal h3 { margin: 0 0 14px; }
.modal pre { background: #f5f5f5; padding: 12px; border-radius: 4px; font-size: 11px; overflow-x: auto; max-height: 260px; }
.modal-actions { margin-top: 16px; display: flex; gap: 10px; justify-content: flex-end; }

/* v10 #22c: 상세 모달 해설 구역 */
.section-label {
  font-size: 11px; font-weight: 600; color: var(--text-tertiary);
  text-transform: uppercase; letter-spacing: .5px; margin: 16px 0 6px;
}
.evt-summary {
  padding: 12px 14px; border-radius: 6px; background: var(--bg-secondary);
  border-left: 3px solid #93c5fd;
}
.evt-summary.evt-ok     { border-left-color: #16a34a; background: #f0fdf4; }
.evt-summary.evt-fail   { border-left-color: #dc2626; background: #fef2f2; }
.evt-summary.evt-denied { border-left-color: #d97706; background: #fffbeb; }
.evt-summary-title {
  display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
  font-size: 13px; font-weight: 500;
}
.evt-time { font-family: var(--font-mono, monospace); color: var(--text-secondary); font-size: 12px; }
.evt-user { font-weight: 700; color: var(--text-primary); }
.evt-verb { color: var(--text-primary); }
.evt-status-chip { font-size: 10.5px; padding: 2px 7px; border-radius: 3px; font-weight: 500; }
.evt-summary-sub {
  margin-top: 6px; font-size: 13px; color: var(--text-secondary); line-height: 1.5;
}
.json-raw {
  margin: 0 !important;
  font-family: var(--font-mono, monospace);
}
.explain-table { width: 100%; border-collapse: collapse; margin: 0 0 8px; }
.explain-table th {
  text-align: left; padding: 7px 10px; width: 150px;
  font-size: 11.5px; font-weight: 600; color: var(--text-secondary);
  background: var(--bg-secondary); vertical-align: top;
}
.explain-table td {
  padding: 7px 10px; font-size: 12px; border-bottom: 1px solid var(--border-light);
  vertical-align: top; line-height: 1.55;
}
.explain-table tr:last-child td { border-bottom: none; }
.mute-small { font-size: 11px; color: var(--text-tertiary); }
.masked-chip {
  display: inline-block; padding: 2px 7px;
  background: #fef3c7; color: #92400e; border-radius: 3px;
  font-size: 10.5px; font-weight: 500;
}

/* 해시 정보 테이블 */
.hash-table { width: 100%; border-collapse: collapse; margin: 10px 0; }
.hash-table th { text-align: left; padding: 8px; width: 170px; font-weight: 600; font-size: 12px; color: var(--text-secondary); background: var(--bg-secondary); }
.hash-table td { padding: 8px; font-size: 12px; }
.hash-short { font-family: var(--font-mono, monospace); font-size: 11px; word-break: break-all; }

/* 정리 다이얼로그 */
.purge-modes { display: flex; gap: 16px; margin: 12px 0 8px; }
.purge-modes .radio { display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 13px; }
.purge-input { padding: 10px 0; }
.purge-input label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--text-secondary); }
.purge-input input { padding: 6px 10px; border: 1px solid var(--border-light); border-radius: 4px; font-size: 13px; width: 180px; }
.purge-preview { margin: 8px 0 0; font-size: 12px; color: var(--text-tertiary); }
</style>
