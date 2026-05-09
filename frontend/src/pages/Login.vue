<template>
  <div class="login-root">
    <!-- 배경: Landing 페이지 (시작하기 버튼 이벤트 받음) -->
    <Landing class="landing-bg" @start="openLogin" />

    <!-- 로그인 카드 (시작하기 클릭 시에만 표시, 드래그 가능) -->
    <Transition name="card-fade">
      <div
        v-if="showLogin"
        class="login-card"
        :class="{ minimized: isMinimized }"
        :style="cardStyle"
        ref="cardRef"
      >
        <!-- 드래그 핸들 (헤더 전체) -->
        <div
          class="card-header"
          @mousedown="startDrag"
          @touchstart="startDrag"
          title="드래그하여 이동"
        >
          <div class="brand">
            <div class="logo">DB</div>
            <div>
              <h1>DataBridge Studio</h1>
              <p class="muted">엔터프라이즈 데이터 이관 플랫폼</p>
            </div>
          </div>

          <!-- 컨트롤 버튼 -->
          <div class="card-controls">
            <button
              type="button"
              class="ctrl-btn"
              @click.stop="resetPosition"
              title="가운데로"
            >⊙</button>
            <button
              type="button"
              class="ctrl-btn"
              @click.stop="toggleMinimize"
              :title="isMinimized ? '펼치기' : '최소화'"
            >{{ isMinimized ? '▢' : '—' }}</button>
            <button
              type="button"
              class="ctrl-btn ctrl-close"
              @click.stop="closeLogin"
              title="닫기"
            >✕</button>
          </div>
        </div>

        <!-- 폼 본문 (최소화 시 숨김) -->
        <form v-show="!isMinimized" class="form" @submit.prevent="onSubmit">
          <label>
            <span>사용자 이름</span>
            <input v-model="username" autocomplete="username"
                   ref="usernameInput"
                   required :disabled="authStore.loading"/>
          </label>
          <label>
            <span>비밀번호</span>
            <input v-model="password" type="password" autocomplete="current-password"
                   required :disabled="authStore.loading"/>
          </label>

          <div v-if="authStore.error" class="err">{{ authStore.error }}</div>

          <button type="submit" class="btn-primary" :disabled="authStore.loading">
            {{ authStore.loading ? '로그인 중...' : '로그인' }}
          </button>

          <p class="hint">
            첫 로그인은 서버 로그의 임시 admin 비번 사용. 로그인 후 즉시 변경하세요.
          </p>
        </form>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/store/authStore.js'
import { useJobStore } from '@/store/jobStore.js'
import Landing from '@/pages/Landing.vue'

const authStore = useAuthStore()
const jobStore  = useJobStore()
const router    = useRouter()
const route     = useRoute()

const username = ref('')
const password = ref('')
const usernameInput = ref(null)

/* ============================================================
 * 로그인 카드 표시 제어
 * ------------------------------------------------------------
 * - 초기 진입 시 Landing 만 보임
 * - Landing 의 "시작하기" 버튼 클릭 시 @start 이벤트 → 카드 표시
 * - 카드 우상단 ✕ 버튼으로 닫기
 * ============================================================ */
const showLogin = ref(false)

function openLogin() {
  showLogin.value = true
  // 카드가 DOM 에 마운트된 후 username 입력칸에 포커스
  nextTick(() => {
    usernameInput.value?.focus()
  })
}

function closeLogin() {
  showLogin.value = false
  // 닫을 때 위치 리셋 + 최소화 해제 (다음에 열 때 깨끗한 상태)
  offsetX.value = 0
  offsetY.value = 0
  isMinimized.value = false
  // 에러 메시지도 정리
  authStore.error = null
}

/* ============================================================
 * 드래그 로직
 * ============================================================ */
const cardRef    = ref(null)
const isMinimized = ref(false)

const offsetX = ref(0)
const offsetY = ref(0)

let dragging   = false
let dragStartX = 0
let dragStartY = 0
let originX    = 0
let originY    = 0

const cardStyle = computed(() => ({
  transform: `translate(calc(-50% + ${offsetX.value}px), calc(-50% + ${offsetY.value}px))`,
}))

function getPoint(e) {
  if (e.touches && e.touches.length) {
    return { x: e.touches[0].clientX, y: e.touches[0].clientY }
  }
  return { x: e.clientX, y: e.clientY }
}

function startDrag(e) {
  if (e.target.closest('.ctrl-btn')) return

  dragging = true
  const p = getPoint(e)
  dragStartX = p.x
  dragStartY = p.y
  originX = offsetX.value
  originY = offsetY.value

  document.body.style.userSelect = 'none'
  document.body.style.cursor     = 'grabbing'

  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup',   endDrag)
  window.addEventListener('touchmove', onDrag, { passive: false })
  window.addEventListener('touchend',  endDrag)
}

function onDrag(e) {
  if (!dragging) return
  if (e.cancelable) e.preventDefault()

  const p = getPoint(e)
  let nx = originX + (p.x - dragStartX)
  let ny = originY + (p.y - dragStartY)

  const card = cardRef.value
  if (card) {
    const w = card.offsetWidth
    const h = card.offsetHeight
    const halfW = w / 2
    const halfH = h / 2
    const cx = window.innerWidth  / 2
    const cy = window.innerHeight / 2

    const minX = -(cx + halfW - 60)
    const maxX =   cx + halfW - 60
    const minY = -(cy - 8)
    const maxY =   cy + halfH - 60

    nx = Math.max(minX, Math.min(maxX, nx))
    ny = Math.max(minY, Math.min(maxY, ny))
  }

  offsetX.value = nx
  offsetY.value = ny
}

function endDrag() {
  dragging = false
  document.body.style.userSelect = ''
  document.body.style.cursor     = ''

  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup',   endDrag)
  window.removeEventListener('touchmove', onDrag)
  window.removeEventListener('touchend',  endDrag)
}

function resetPosition() {
  offsetX.value = 0
  offsetY.value = 0
}

function toggleMinimize() {
  isMinimized.value = !isMinimized.value
}

onUnmounted(() => {
  endDrag()
})

/* ============================================================
 * 로그인 처리
 * ============================================================ */
async function onSubmit() {
  const ok = await authStore.login(username.value, password.value)
  if (ok) {
    try { jobStore.startGlobalPolling?.() } catch {}
    const next = route.query.next || '/'
    router.replace(next)
  }
}
</script>

<style scoped>
/* 루트 */
.login-root {
  position: relative;
  min-height: 100vh;
  width: 100%;
  overflow: hidden;
}

/* 배경 Landing */
.landing-bg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
}

/* 로그인 카드 */
.login-card {
  position: fixed;
  top: 50%;
  left: 50%;
  z-index: 100;

  width: 420px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 25px 70px rgba(0, 0, 0, 0.25),
              0 10px 30px rgba(0, 0, 0, 0.12);

  will-change: transform;
}

/* 카드 등장/퇴장 트랜지션 */
.card-fade-enter-active,
.card-fade-leave-active {
  transition: opacity .25s ease, transform .25s ease;
}
.card-fade-enter-from {
  opacity: 0;
  transform: translate(-50%, calc(-50% + 20px)) !important;
}
.card-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, calc(-50% - 10px)) !important;
}

/* 헤더: 드래그 핸들 */
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 20px 24px 16px;
  cursor: grab;
  border-bottom: 1px solid #f3f4f6;
  user-select: none;
  border-radius: 12px 12px 0 0;
  background: linear-gradient(180deg, #fafbfc 0%, #ffffff 100%);
}
.card-header:active { cursor: grabbing; }

.login-card.minimized .card-header {
  border-bottom: none;
  border-radius: 12px;
}

.brand { display: flex; align-items: center; gap: 14px; flex: 1; min-width: 0; }
.logo {
  width: 48px; height: 48px; border-radius: 10px;
  background: linear-gradient(135deg, #1f6feb, #2ea043);
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 18px;
  flex-shrink: 0;
}
h1 { margin: 0; font-size: 17px; color: #1f2937; }
.muted { margin: 2px 0 0; font-size: 12px; color: #6b7280; }

.card-controls {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}
.ctrl-btn {
  width: 28px; height: 28px;
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  color: #6b7280;
  display: flex; align-items: center; justify-content: center;
  transition: all .15s;
}
.ctrl-btn:hover {
  background: #f3f4f6;
  color: #1f2937;
  border-color: #d1d5db;
}
.ctrl-close:hover {
  background: #fef2f2;
  color: #dc2626;
  border-color: #fecaca;
}

/* 폼 */
.form {
  display: flex; flex-direction: column; gap: 16px;
  padding: 20px 24px 28px;
}
.form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #374151; }
.form input {
  padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 14px;
}
.form input:focus { outline: 2px solid #1f6feb33; border-color: #1f6feb; }

.btn-primary {
  background: #1f6feb; color: #fff; border: none; padding: 12px;
  border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer;
  margin-top: 8px;
}
.btn-primary:disabled { opacity: .6; cursor: not-allowed; }
.btn-primary:hover:not(:disabled) { background: #1a5fcc; }

.err {
  background: #fef2f2; color: #991b1b; padding: 8px 12px;
  border-radius: 6px; font-size: 13px; border: 1px solid #fecaca;
}
.hint {
  margin: 0; font-size: 12px; color: #6b7280; line-height: 1.5;
  padding-top: 8px; border-top: 1px solid #f3f4f6;
}
</style>
