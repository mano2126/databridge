<template>
  <div class="appearance-page">
    <div class="page-header">
      <div>
        <h2>모양 및 느낌</h2>
        <p class="muted">테마, 밀도, 글자 크기를 취향에 맞게 조정합니다. 설정은 브라우저에 저장됩니다.</p>
      </div>
      <button class="btn-ghost" @click="reset">기본값으로 되돌리기</button>
    </div>

    <!-- 테마 -->
    <section class="sec">
      <h3>테마</h3>
      <div class="theme-options">
        <button class="theme-card" :class="{ active: app.theme === 'light' }"
                @click="app.setTheme('light')">
          <div class="preview light"></div>
          <span>라이트</span>
        </button>
        <button class="theme-card" :class="{ active: app.theme === 'dark' }"
                @click="app.setTheme('dark')">
          <div class="preview dark"></div>
          <span>다크</span>
        </button>
        <button class="theme-card" :class="{ active: app.theme === 'auto' }"
                @click="app.setTheme('auto')">
          <div class="preview auto"></div>
          <span>자동 (OS 설정)</span>
        </button>
      </div>
    </section>

    <!-- 밀도 -->
    <section class="sec">
      <h3>밀도</h3>
      <p class="hint">목록·테이블의 행 높이와 여백을 조절합니다.</p>
      <div class="radio-group">
        <label :class="{ active: app.density === 'compact' }">
          <input type="radio" value="compact" :checked="app.density === 'compact'" @change="app.setDensity('compact')"/>
          <strong>Compact</strong>
          <span>많은 정보를 한눈에 (28px 행)</span>
        </label>
        <label :class="{ active: app.density === 'comfortable' }">
          <input type="radio" value="comfortable" :checked="app.density === 'comfortable'" @change="app.setDensity('comfortable')"/>
          <strong>Comfortable</strong>
          <span>기본값 (36px 행)</span>
        </label>
        <label :class="{ active: app.density === 'spacious' }">
          <input type="radio" value="spacious" :checked="app.density === 'spacious'" @change="app.setDensity('spacious')"/>
          <strong>Spacious</strong>
          <span>여유로운 여백 (44px 행)</span>
        </label>
      </div>
    </section>

    <!-- 글자 크기 -->
    <section class="sec">
      <h3>글자 크기</h3>
      <p class="hint">현재 {{ app.fontSize }}px</p>
      <input type="range" min="12" max="18" step="1" :value="app.fontSize"
             @input="e => app.setFontSize(e.target.value)" class="slider"/>
      <div class="slider-labels">
        <span>12</span><span>14</span><span>16</span><span>18</span>
      </div>
      <div class="font-preview" :style="{ fontSize: app.fontSize + 'px' }">
        예시 텍스트 — DataBridge Studio 이관 작업 상태
      </div>
    </section>

    <!-- 포인트 색 -->
    <section class="sec">
      <h3>포인트 색상</h3>
      <p class="hint">버튼, 링크, 배지에 사용되는 주 색상</p>
      <div class="color-swatches">
        <button v-for="c in presetColors" :key="c.hex"
                class="swatch" :class="{ active: app.accentColor === c.hex }"
                :style="{ background: c.hex }"
                :title="c.name"
                @click="app.setAccentColor(c.hex)"></button>
        <label class="swatch-custom">
          <input type="color" :value="app.accentColor"
                 @input="e => app.setAccentColor(e.target.value)"/>
          <span>커스텀</span>
        </label>
      </div>
    </section>

    <!-- 사이드바 너비 -->
    <section class="sec">
      <h3>사이드바 너비</h3>
      <p class="hint">현재 {{ app.sidebarWidth }}px</p>
      <input type="range" min="200" max="360" step="10" :value="app.sidebarWidth"
             @input="e => app.setSidebarWidth(e.target.value)" class="slider"/>
      <div class="slider-labels">
        <span>200</span><span>240</span><span>280</span><span>320</span><span>360</span>
      </div>
    </section>

    <!-- v10: 마스코트 -->
    <section class="sec">
      <h3>메뉴 마스코트</h3>
      <p class="hint">선택된 메뉴에서 걷는 캐릭터. 글자 오른쪽부터 메뉴 끝까지 왕복합니다.</p>
      <div class="mascot-grid">
        <button v-for="m in mascotOptions" :key="m.key"
                class="mascot-opt"
                :class="{ active: app.mascot === m.key }"
                @click="app.setMascot(m.key)">
          <div class="mascot-preview-wrap">
            <svg v-if="m.key === 'person'" viewBox="0 0 14 20" fill="currentColor" class="m-preview m-walk">
              <circle cx="7" cy="3" r="2"/>
              <path d="M7 5.5 L7 12" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linecap="round"/>
              <path d="M7 7 L10 10" stroke="currentColor" stroke-width="1.4" fill="none" stroke-linecap="round"/>
              <path d="M7 7 L4 9" stroke="currentColor" stroke-width="1.4" fill="none" stroke-linecap="round" opacity=".6"/>
              <path d="M7 12 L4 17" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linecap="round"/>
              <path d="M7 12 L10 17" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linecap="round" opacity=".7"/>
            </svg>
            <svg v-else-if="m.key === 'cat'" viewBox="0 0 20 14" fill="currentColor" class="m-preview m-walk">
              <ellipse cx="9" cy="8" rx="6" ry="3.5"/>
              <circle cx="14.5" cy="6" r="2.2"/>
              <path d="M 13.2 4.5 L 12.5 3 M 15.8 4.5 L 16.5 3" stroke="currentColor" stroke-width="0.8" fill="none"/>
              <circle cx="15.3" cy="5.8" r="0.4" fill="#fff"/>
              <path d="M 3 7 Q 1.5 4 2 3" stroke="currentColor" stroke-width="1.2" fill="none" stroke-linecap="round"/>
              <line x1="6" y1="10.5" x2="6" y2="13" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
              <line x1="11" y1="10.5" x2="11" y2="13" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
            </svg>
            <svg v-else-if="m.key === 'dog'" viewBox="0 0 20 14" fill="currentColor" class="m-preview m-walk">
              <ellipse cx="9" cy="8" rx="6" ry="4"/>
              <circle cx="14.5" cy="6" r="2.5"/>
              <path d="M 13 4 L 12 2.5 M 16 4 L 17 2.5" stroke="currentColor" stroke-width="1.2" fill="none" stroke-linecap="round"/>
              <circle cx="15.5" cy="5.5" r="0.4" fill="#fff"/>
              <circle cx="15" cy="7" r="0.3"/>
              <path d="M 3 9 Q 1.5 8 2 6" stroke="currentColor" stroke-width="1.3" fill="none" stroke-linecap="round"/>
              <line x1="6" y1="11" x2="6" y2="13" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
              <line x1="11" y1="11" x2="11" y2="13" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
            </svg>
            <svg v-else-if="m.key === 'robot'" viewBox="0 0 14 20" fill="currentColor" class="m-preview m-walk">
              <rect x="3" y="2" width="8" height="7" rx="1.5"/>
              <circle cx="5" cy="5" r="0.8" fill="#fff"/>
              <circle cx="9" cy="5" r="0.8" fill="#fff"/>
              <line x1="3" y1="3" x2="1.5" y2="1.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
              <line x1="11" y1="3" x2="12.5" y2="1.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
              <rect x="3" y="9" width="8" height="5"/>
              <line x1="11" y1="10.5" x2="13" y2="13" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
              <line x1="3" y1="10.5" x2="1" y2="13" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" opacity=".7"/>
              <line x1="5" y1="14" x2="4" y2="18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
              <line x1="9" y1="14" x2="10" y2="18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" opacity=".7"/>
            </svg>
            <svg v-else-if="m.key === 'ghost'" viewBox="0 0 14 18" fill="currentColor" class="m-preview m-float">
              <path d="M 2 13 Q 2 4 7 3 Q 12 4 12 13 Q 12 17 10 15.5 Q 7 17 4 15.5 Q 2 17 2 13 Z"/>
              <circle cx="5" cy="9" r="0.9" fill="#fff"/>
              <circle cx="9" cy="9" r="0.9" fill="#fff"/>
            </svg>
            <span v-else-if="m.key === 'none'" class="m-none">∅</span>
          </div>
          <span class="mascot-label">{{ m.name }}</span>
        </button>
      </div>
    </section>

    <!-- 접근성 -->
    <section class="sec">
      <h3>접근성</h3>
      <div class="toggle-row">
        <label class="toggle">
          <input type="checkbox" :checked="app.reducedMotion"
                 @change="e => app.setReducedMotion(e.target.checked)"/>
          <span class="toggle-slider"></span>
          <span class="toggle-label">
            <strong>애니메이션 감소</strong>
            <small>페이지 전환, 마스코트, 호버 효과 등을 최소화</small>
          </span>
        </label>
      </div>
      <div class="toggle-row">
        <label class="toggle">
          <input type="checkbox" :checked="app.highContrast"
                 @change="e => app.setHighContrast(e.target.checked)"/>
          <span class="toggle-slider"></span>
          <span class="toggle-label">
            <strong>고대비 모드</strong>
            <small>텍스트와 배경 대비를 높임</small>
          </span>
        </label>
      </div>
    </section>

    <!-- 키보드 단축키 -->
    <section class="sec">
      <h3>키보드 단축키</h3>
      <div class="shortcuts">
        <div class="shortcut"><kbd>Ctrl</kbd><kbd>/</kbd><span>명령 팔레트 (검색)</span></div>
        <div class="shortcut"><kbd>Ctrl</kbd><kbd>B</kbd><span>사이드바 접기/펴기</span></div>
        <div class="shortcut"><kbd>Ctrl</kbd><kbd>Shift</kbd><kbd>L</kbd><span>다크모드 전환</span></div>
        <div class="shortcut"><kbd>Esc</kbd><span>다이얼로그·팝업 닫기</span></div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useAppStore } from '@/store/appStore.js'
defineOptions({ name: 'Appearance' })
const app = useAppStore()

const presetColors = [
  { name: '파랑',   hex: '#1f6feb' },
  { name: '보라',   hex: '#8b5cf6' },
  { name: '청록',   hex: '#0891b2' },
  { name: '초록',   hex: '#10b981' },
  { name: '주황',   hex: '#f59e0b' },
  { name: '빨강',   hex: '#ef4444' },
  { name: '분홍',   hex: '#ec4899' },
  { name: '회색',   hex: '#475569' },
]

const mascotOptions = [
  { key: 'person', name: '사람' },
  { key: 'cat',    name: '고양이' },
  { key: 'dog',    name: '강아지' },
  { key: 'robot',  name: '로봇' },
  { key: 'ghost',  name: '유령' },
  { key: 'none',   name: '없음' },
]

function reset() {
  if (confirm('모든 UI 설정을 기본값으로 되돌립니다. 계속하시겠습니까?')) {
    app.resetUI()
    app.setTheme('light')
  }
}

onMounted(() => {
  app.applyUI()
  app.applyTheme()
})
</script>

<style scoped>
/* v10.1: 전역 CSS 충돌 방어를 위해 모든 레이아웃 규칙에 !important 적용 */
.appearance-page {
  display: block !important;
  padding: 24px !important;
  max-width: 800px !important;
  box-sizing: border-box !important;
}
.appearance-page * { box-sizing: border-box !important; }

.page-header {
  display: flex !important;
  flex-direction: row !important;
  justify-content: space-between !important;
  align-items: flex-end !important;
  margin-bottom: 20px !important;
  padding-bottom: 16px !important;
  border-bottom: 1px solid var(--border-mid, #e5e7eb) !important;
  width: 100% !important;
}
.page-header h2 { margin: 0 !important; }
.muted { color: #6b7280 !important; font-size: 13px !important; margin: 4px 0 0 !important; white-space: normal !important; }
.hint  { color: #6b7280 !important; font-size: 12px !important; margin: 4px 0 12px !important; white-space: normal !important; }

.sec {
  display: block !important;
  position: relative !important;
  clear: both !important;
  float: none !important;
  padding: 20px 0 !important;
  border-bottom: 1px solid var(--border-light, #f3f4f6) !important;
  width: 100% !important;
}
.sec:last-child { border-bottom: none !important; }
.sec h3 {
  display: block !important;
  margin: 0 0 8px !important;
  font-size: 15px !important;
  color: var(--text-primary, #1f2937) !important;
  white-space: normal !important;
  writing-mode: horizontal-tb !important;
}
.sec > * {
  max-width: 100% !important;
  writing-mode: horizontal-tb !important;
}

.theme-options { display: flex !important; flex-direction: row !important; gap: 12px !important; }
.theme-card {
  flex: 1 1 auto !important;
  min-width: 0 !important;
  padding: 12px !important;
  border: 2px solid var(--border-mid, #e5e7eb) !important;
  background: var(--bg-primary, #fff) !important;
  border-radius: 8px !important;
  cursor: pointer !important;
  display: flex !important;
  flex-direction: column !important;
  align-items: center !important;
  gap: 8px !important;
  font-size: 13px !important;
}
.theme-card:hover { border-color: var(--accent, #1f6feb) !important; }
.theme-card.active { border-color: var(--accent, #1f6feb) !important; box-shadow: 0 0 0 2px rgba(31,111,235,.13) !important; }
.preview { width: 100% !important; height: 40px !important; border-radius: 4px !important; }
.preview.light { background: linear-gradient(to right, #fff 50%, #f3f4f6 50%) !important; border: 1px solid #e5e7eb !important; }
.preview.dark  { background: linear-gradient(to right, #1f2937 50%, #111827 50%) !important; }
.preview.auto  { background: linear-gradient(to right, #fff 50%, #1f2937 50%) !important; }

.radio-group { display: flex !important; flex-direction: column !important; gap: 8px !important; }
.radio-group label {
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  gap: 12px !important;
  padding: 10px 12px !important;
  border: 1px solid var(--border-mid, #e5e7eb) !important;
  border-radius: 6px !important;
  cursor: pointer !important;
  font-size: 13px !important;
  width: 100% !important;
}
.radio-group label:hover { background: var(--bg-secondary, #f9fafb) !important; }
.radio-group label.active { border-color: var(--accent, #1f6feb) !important; background: rgba(31,111,235,.07) !important; }
.radio-group label strong { margin-right: 4px !important; white-space: nowrap !important; }
.radio-group label span { color: #6b7280 !important; font-size: 12px !important; white-space: normal !important; }

.slider {
  display: block !important;
  width: 100% !important;
  margin: 4px 0 !important;
  box-sizing: border-box !important;
}
.slider-labels {
  display: flex !important;
  flex-direction: row !important;
  justify-content: space-between !important;
  width: 100% !important;
  box-sizing: border-box !important;
  font-size: 11px !important;
  color: #9ca3af !important;
  margin-bottom: 12px !important;
}
.slider-labels > span { white-space: nowrap !important; }
.font-preview {
  display: block !important;
  padding: 12px 16px !important;
  background: var(--bg-secondary, #f9fafb) !important;
  border-radius: 6px !important;
  color: var(--text-primary, #1f2937) !important;
  width: 100% !important;
  box-sizing: border-box !important;
}

.color-swatches { display: flex !important; flex-direction: row !important; flex-wrap: wrap !important; gap: 8px !important; align-items: center !important; }
.swatch {
  width: 32px !important;
  height: 32px !important;
  border-radius: 50% !important;
  border: 2px solid transparent !important;
  cursor: pointer !important;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
  flex-shrink: 0 !important;
  padding: 0 !important;
}
.swatch.active { border-color: var(--text-primary, #1f2937) !important; transform: scale(1.1) !important; }
.swatch:hover { transform: scale(1.1) !important; }
.swatch-custom {
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  gap: 4px !important;
  font-size: 12px !important;
  cursor: pointer !important;
  color: #6b7280 !important;
  white-space: nowrap !important;
}
.swatch-custom input[type=color] { width: 32px !important; height: 32px !important; border: none !important; cursor: pointer !important; padding: 0 !important; flex-shrink: 0 !important; }

.mascot-grid {
  display: grid !important;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)) !important;
  gap: 10px !important;
  width: 100% !important;
}
.mascot-opt {
  display: flex !important;
  flex-direction: column !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 6px !important;
  padding: 14px 10px !important;
  background: var(--bg-primary, #fff) !important;
  border: 1px solid var(--border-mid, #e5e7eb) !important;
  border-radius: 8px !important;
  cursor: pointer !important;
  min-width: 0 !important;
  width: 100% !important;
  box-sizing: border-box !important;
  font-family: inherit !important;
}
.mascot-opt:hover { border-color: var(--accent, #1f6feb) !important; }
.mascot-opt.active {
  border: 2px solid var(--accent, #1f6feb) !important;
  background: rgba(31,111,235,.06) !important;
  padding: 13px 9px !important;
}
.mascot-preview-wrap {
  height: 32px !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  width: 100% !important;
}
.m-preview {
  width: 20px !important;
  height: 24px !important;
  color: var(--accent, #1f6feb) !important;
  flex-shrink: 0 !important;
}
.m-preview.m-walk { animation: m-card-walk 2.5s ease-in-out infinite; }
.m-preview.m-float { animation: m-card-float 2.5s ease-in-out infinite; }
.m-none {
  font-size: 18px !important;
  color: var(--text-tertiary, #9ca3af) !important;
  font-weight: 300 !important;
}
.mascot-label {
  display: block !important;
  font-size: 12px !important;
  color: var(--text-secondary, #6b7280) !important;
  white-space: nowrap !important;
  text-align: center !important;
  width: 100% !important;
  writing-mode: horizontal-tb !important;
}
.mascot-opt.active .mascot-label {
  color: var(--accent, #1f6feb) !important;
  font-weight: 500 !important;
}

@keyframes m-card-walk {
  0%, 100% { transform: translateX(-6px); }
  50%      { transform: translateX(6px); }
}
@keyframes m-card-float {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-3px); }
}

.toggle-row {
  display: block !important;
  padding: 8px 0 !important;
  width: 100% !important;
}
.toggle {
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  gap: 12px !important;
  cursor: pointer !important;
  width: 100% !important;
}
.toggle input { display: none !important; }
.toggle-slider {
  width: 36px !important;
  height: 20px !important;
  background: #d1d5db !important;
  border-radius: 10px !important;
  position: relative !important;
  transition: background 0.2s !important;
  flex-shrink: 0 !important;
  display: block !important;
}
.toggle-slider::before {
  content: '' !important;
  position: absolute !important;
  left: 2px !important;
  top: 2px !important;
  width: 16px !important;
  height: 16px !important;
  background: #fff !important;
  border-radius: 50% !important;
  transition: transform 0.2s !important;
}
.toggle input:checked + .toggle-slider { background: var(--accent, #1f6feb) !important; }
.toggle input:checked + .toggle-slider::before { transform: translateX(16px) !important; }
.toggle-label {
  display: flex !important;
  flex-direction: column !important;
  flex: 1 1 auto !important;
  min-width: 0 !important;
  width: auto !important;
  writing-mode: horizontal-tb !important;
}
.toggle-label strong {
  display: block !important;
  font-size: 13px !important;
  white-space: normal !important;
  word-break: keep-all !important;
}
.toggle-label small {
  display: block !important;
  color: #6b7280 !important;
  font-size: 11px !important;
  white-space: normal !important;
  word-break: keep-all !important;
}

.shortcuts {
  display: grid !important;
  grid-template-columns: repeat(2, 1fr) !important;
  gap: 8px !important;
  width: 100% !important;
}
.shortcut {
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  gap: 8px !important;
  padding: 8px 12px !important;
  background: var(--bg-secondary, #f9fafb) !important;
  border-radius: 4px !important;
  font-size: 12px !important;
  min-width: 0 !important;
}
kbd {
  background: #fff !important;
  border: 1px solid #d1d5db !important;
  border-bottom-width: 2px !important;
  padding: 2px 6px !important;
  border-radius: 3px !important;
  font-family: monospace !important;
  font-size: 11px !important;
  color: #374151 !important;
  white-space: nowrap !important;
  flex-shrink: 0 !important;
}
kbd + kbd { margin-left: 2px !important; }
.shortcut span {
  margin-left: auto !important;
  color: #6b7280 !important;
  white-space: nowrap !important;
}

.btn-ghost {
  background: transparent !important;
  border: 1px solid #d1d5db !important;
  color: #6b7280 !important;
  padding: 6px 14px !important;
  border-radius: 4px !important;
  cursor: pointer !important;
  font-size: 13px !important;
  white-space: nowrap !important;
  flex-shrink: 0 !important;
}
.btn-ghost:hover { background: #f3f4f6 !important; }

.reduced-motion .m-preview { animation: none !important; }
</style>
