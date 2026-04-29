// frontend/src/composables/useDragFloat.js — 플로팅 요소 드래그 (v10 #22)
//
// Pointer Events 기반 (터치/마우스 통합).
// 특정 요소(handle)만 드래그 시작점으로 지정 가능 → 내부 버튼 클릭과 분리.
//
// 사용법:
//   const { startDrag } = useDragFloat({
//     pos: computed(() => store.pos),
//     onMove: (x, y) => store.setPos(x, y),
//   })
//   <div class="drag-handle" @pointerdown="startDrag">
//
// 장점:
//   - 창 밖으로 벗어나도 계속 따라옴 (document 레벨 리스너)
//   - 드래그 중 text selection 방지
//   - cleanup 자동

import { ref, onUnmounted } from 'vue'

export function useDragFloat({ pos, onMove }) {
  const dragging = ref(false)
  // 드래그 시작 시의 오프셋 (팝업 왼쪽 위 기준)
  let offsetX = 0
  let offsetY = 0

  function startDrag(e) {
    // 왼쪽 버튼만 (혹은 터치)
    if (e.button !== undefined && e.button !== 0) return
    // 내부 버튼/입력 클릭은 드래그 시작 안 함
    const tag = (e.target?.tagName || '').toUpperCase()
    if (['BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'A'].includes(tag)) return

    const p = pos.value || { x: 0, y: 0 }
    offsetX = e.clientX - p.x
    offsetY = e.clientY - p.y
    dragging.value = true
    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'grabbing'

    document.addEventListener('pointermove', handleMove)
    document.addEventListener('pointerup',   handleUp, { once: true })
    document.addEventListener('pointercancel', handleUp, { once: true })
    e.preventDefault()
  }

  function handleMove(e) {
    if (!dragging.value) return
    const nx = e.clientX - offsetX
    const ny = e.clientY - offsetY
    onMove?.(nx, ny)
  }

  function handleUp() {
    dragging.value = false
    document.body.style.userSelect = ''
    document.body.style.cursor = ''
    document.removeEventListener('pointermove', handleMove)
  }

  // 안전장치: 컴포넌트 unmount 시 리스너 제거
  onUnmounted(() => {
    document.removeEventListener('pointermove', handleMove)
  })

  return { dragging, startDrag }
}

export default useDragFloat
