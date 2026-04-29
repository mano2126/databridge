<!-- PageHeader.vue — DataBridge Studio 공통 페이지 헤더 -->
<template>
  <div class="ph-bar card">
    <div class="ph-row">

      <!-- ── DB 커넥션 박스 (양쪽 연결 있을 때) ── -->
      <template v-if="showDb && (srcDb?.host || tgtDb?.host)">
        <!-- 소스 DB -->
        <div class="ph-db-box src" v-if="srcDb?.host || srcDb?.database">
          <div class="ph-cyl-wrap">
            <svg viewBox="0 0 32 32" fill="none" class="ph-cyl">
              <ellipse cx="16" cy="9" rx="10" ry="4" fill="rgba(59,130,246,.15)" stroke="#3b82f6" stroke-width="1.3"/>
              <path d="M6 9v14c0 2.2 4.48 4 10 4s10-1.8 10-4V9" fill="rgba(59,130,246,.06)" stroke="#3b82f6" stroke-width="1.3"/>
              <ellipse cx="16" cy="16" rx="10" ry="4" fill="rgba(59,130,246,.06)" stroke="#3b82f6" stroke-width="1" stroke-dasharray="2.5 2"/>
            </svg>
            <img v-if="srcLogoUrl" :src="srcLogoUrl" class="ph-db-logo" :alt="srcDb?.dbType"/>
            <span v-if="srcDb?.status==='ok'" class="ph-online src"></span>
          </div>
          <div class="ph-db-info">
            <span class="ph-db-label src">소스</span>
            <b class="ph-db-nm">{{ srcDb?.database || '미연결' }}</b>
            <span class="ph-db-tp">{{ srcDb?.dbType }}</span>
          </div>
        </div>

        <!-- 화살표 -->
        <div class="ph-arrow" v-if="tgtDb?.host || tgtDb?.database">
          <svg viewBox="0 0 28 10" fill="none" stroke="var(--text-tertiary)" stroke-width="1.5" style="width:24px;flex-shrink:0">
            <line x1="0" y1="5" x2="22" y2="5"/>
            <polyline points="17,1 23,5 17,9"/>
          </svg>
        </div>

        <!-- 타겟 DB -->
        <div class="ph-db-box tgt" v-if="tgtDb?.host || tgtDb?.database">
          <div class="ph-cyl-wrap">
            <svg viewBox="0 0 32 32" fill="none" class="ph-cyl">
              <ellipse cx="16" cy="9" rx="10" ry="4" fill="rgba(16,185,129,.15)" stroke="#059669" stroke-width="1.3"/>
              <path d="M6 9v14c0 2.2 4.48 4 10 4s10-1.8 10-4V9" fill="rgba(16,185,129,.06)" stroke="#059669" stroke-width="1.3"/>
              <ellipse cx="16" cy="16" rx="10" ry="4" fill="rgba(16,185,129,.06)" stroke="#059669" stroke-width="1" stroke-dasharray="2.5 2"/>
            </svg>
            <img v-if="tgtLogoUrl" :src="tgtLogoUrl" class="ph-db-logo" :alt="tgtDb?.dbType"/>
            <span v-if="tgtDb?.status==='ok'" class="ph-online tgt"></span>
          </div>
          <div class="ph-db-info">
            <span class="ph-db-label tgt">타겟</span>
            <b class="ph-db-nm">{{ tgtDb?.database || '미연결' }}</b>
            <span class="ph-db-tp">{{ tgtDb?.dbType }}</span>
          </div>
        </div>

        <div class="ph-divider"></div>
      </template>

      <!-- ── 화면별 컨트롤 슬롯 ── -->
      <slot name="controls"/>

      <!-- ── 우측 액션 슬롯 ── -->
      <div class="ph-actions" v-if="$slots.actions">
        <slot name="actions"/>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  showDb:  { type: Boolean, default: false },
  srcDb:   { type: Object,  default: null  },
  tgtDb:   { type: Object,  default: null  },
})

// DB 로고 (SqlVerify와 동일)
const _LOGOS = {
  mysql:      'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4Ij48cGF0aCBmaWxsPSIjMDA2MThBIiBkPSJNMTE2LjkgOTljLTYuNS0uMi0xMS41LjQtMTUuOCAyLjItMS4yLjUtMy4xLjUtMy4zIDIgLjcuNy44IDEuNyAxLjMgMi42IDEgMS42IDIuNyAzLjggNC4zIDUgMS43IDEuMyAzLjQgMi42IDUuMiAzLjcgMy4yIDEuOSA2LjggMyA5LjggNSAxLjggMS4xIDMuNiAyLjYgNS40IDMuOS45LjYgMS41IDEuNiAyLjYgMnYtLjJjLS42LS44LS44LTEuOC0xLjMtMi42bC0yLjQtMi40Yy0yLjQtMy4xLTUuNC01LjktOC42LTguMi0yLjUtMS44LTguMi00LjMtOS4zLTcuM2wtLjItLjJjMS44LS4yIDMuOS0uOSA1LjYtMS4zIDIuOC0uNyA1LjMtLjYgOC4yLTEuM2wzLjktMS4xdi0uN2MtMS41LTEuNS0yLjUtMy41LTQuMS00LjgtNC4yLTMuNS04LjctNy4xLTEzLjQtMTAtMi42LTEuNi01LjgtMi43LTguNi00LjEtLjktLjUtMi41LS43LTMuMi0xLjVjLTEuNC0xLjgtMi4yLTQuMi0zLjMtNi4zLTIuMy00LjUtNC42LTkuNC02LjctMTQuMS0xLjQtMy4yLTIuMy02LjQtNC4xLTkuM0M3Ni4yIDMwIDY3IDIxLjYgNTMgMTMuM2MtMy0xLjgtNi42LTIuNS0xMC40LTMuNGwtNi4xLS40Yy0xLjItLjUtMi41LTItMy43LTIuOEMxNC45IDMuMyAyLjMtMy40LTEuMyA1LjVjLTIuMyA1LjYgMy40IDExIDUuNCAxMy44IDEuNCAyIDMuMiA0LjIgNC4yIDYuNCAwLjcgMS40LjggMi44IDEuNCA0LjMgMS41IDMuOCAyLjggOCA0LjggMTEuNSAxIDEuNyAyLjEgMy41IDMuMyA1LjEuNyAxIDEuOSAxLjQgMi4xIDMtLjkgMS4zLTEgMy4yLTEuNSA0LjgtMi4zIDcuMy0xLjQgMTYuMyAxLjkgMjEuNyAxIDEuNiAzLjQgNS4xIDYuNiAzLjggMi44LTEuMiAyLjItNC43IDMtNy44LjItLjcuMS0xLjIuNC0xLjd2LjFsMi41IDVjMS44IDIuOSA1IDUuOSA3LjcgNy45IDEuNCAxIDIuNSAyLjggNC4zIDMuNHYtLjJoLS4xYy0uNC0uNS0uOS0xLTEuMy0xLjUtMS0xLTIuMS0yLjMtMi45LTMuNC0yLjMtMy4xLTQuMy02LjUtNi0xMC0uOS0xLjctMS42LTMuNi0yLjMtNS4zLS4zLS43LS4zLTEuNy0uOS0yLjEtLjggMS4yLTIgMi4zLTIuNiAzLjgtMSAyLjQtMS4xIDUuMy0xLjUgOC40LS4yLjEtLjEuMS0uMi4yLTItLjUtMi43LTIuNS0zLjQtNC4yLTEuOS00LjQtMi4yLTExLjUtLjYtMTYuNi41LTEuNSAyLjYtNi4yIDEuNy03LjYtLjQtLjgtMS43LTEuMy0yLjQtMS44LTEtLjYtMS44LTEuNi0yLjUtMi42LTEuNy0yLjMtMy4yLTUtNC4zLTcuNi0wLjYtMS4zLS44LTIuNy0xLjMtNC0xLTIuMy0yLjUtNC42LTMuNS02LjktLjUtMS4xLS44LTIuMy0xLjMtMy40LS43LTEuNS0xLjgtMi45LTIuMy00LjQtMS4zLTQuMS40LTguNSAxLjctMTEuMy40LS45IDEuNi0zLjcgMy40LTIuNyAxIC41IDEuMiAxLjcgMS43IDIuOC40LjkuOSAxLjggMS4zIDIuN2wxLjQgMy40Yy4xLjEuNCAxLjIuOSAxLjUuNC4yLjktLjMgMS4zLS4zLjUtLjEgMS4zLjIgMS45LjEuOS0uMiAxLjQtLjQgMi4xLS41LjYtLjEgMS4zLjEgMS45LjIuNS4xIDEgLjQgMS41LjVsLjguMmMuNC4xLjguMSAxLjIuMS42IDAgMS4zLS4xIDEuOS0uMi40LS4xLjgtLjIgMS4yLS40LjQtLjIuOC0uNiAxLjItLjctLjItMS4yLS43LTIuMy0xLjEtMy40LS40LS44LS43LTEuNi0xLTIuNS0uOS0yLjMtMi4yLTQuNi0zLjQtNi44LS42LTEuMS0xLjItMi4yLTEuOC0zLjMtLjItLjQtLjUtMS0uOC0xLjNzLS44LS40LTEuMS0uN2MtMS4yLS45LTIuNS0xLjktMy42LTIuOXoiLz48L3N2Zz4=',
  mssql:      'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4Ij48cGF0aCBmaWxsPSIjQ0MyOTI3IiBkPSJNNjQgOEMzMy4xIDggOCAzMy4xIDggNjRzMjUuMSA1NiA1NiA1NiA1Ni0yNS4xIDU2LTU2Uzk0LjkgOCA2NCA4eiIvPjxwYXRoIGZpbGw9IiNmZmYiIGQ9Ik03My4zIDQ4LjRjLTIuMS0zLjYtNS4yLTUuNC05LjMtNS40SDQ0Ljl2NDEuMWg4VjcyLjZoMTFjMy45IDAgNy0xLjcgOS4yLTUuMiAxLjQtMi4yIDIuMS00LjggMi4xLTcuNnMtLjYtNS4yLTEuOS03LjR6bS04LjEgMTQuN0g1Mi45di0xMmgxMi4xYzEuNSAwIDIuNy43IDMuNSAyIC42IDEuMS45IDIuNC45IDRzLS4zIDIuOS0xIDRjLS44IDEuMy0yIDItMy4yIDJ6Ii8+PHBhdGggZmlsbD0iI2ZmZiIgZD0iTTkxIDQzaC03LjVMNzIuMiA4NC4xaDguMmwyLjMtNy4ySDk1bDIuNCA3LjJoOC4zem0tNS45IDI2LjFsNC42LTE0LjkgNC43IDE0Ljl6Ii8+PC9zdmc+',
  postgresql: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4Ij48Y2lyY2xlIGZpbGw9IiMzMzY3OTEiIGN4PSI2NCIgY3k9IjY0IiByPSI1NiIvPjxjaXJjbGUgZmlsbD0iI2ZmZiIgY3g9IjUxIiBjeT0iNTIiIHI9IjYiLz48Y2lyY2xlIGZpbGw9IiNmZmYiIGN4PSI3NyIgY3k9IjUyIiByPSI2Ii8+PC9zdmc+',
  oracle:     'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4Ij48cGF0aCBmaWxsPSIjRjgwMDAwIiBkPSJNNjQgMTZDMzcuNSAxNiAxNiAzNy41IDE2IDY0czIxLjUgNDggNDggNDggNDgtMjEuNSA0OC00OFM5MC41IDE2IDY0IDE2eiIvPjxwYXRoIGZpbGw9IiNmZmYiIGQ9Ik02NCAzNmMtMTUuNSAwLTI4IDEyLjUtMjggMjhzMTIuNSAyOCAyOCAyOCAyOC0xMi41IDI4LTI4LTEyLjUtMjgtMjgtMjh6bTAgNDRjLTguOCAwLTE2LTcuMi0xNi0xNnM3LjItMTYgMTYtMTYgMTYgNy4yIDE2IDE2LTcuMiAxNi0xNiAxNnoiLz48L3N2Zz4=',
  mongodb:    'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4Ij48cGF0aCBmaWxsPSIjNDM5OTM0IiBkPSJNNjQgMTFjLTEgMi0xNSA3LTI0IDE4LTEyIDE1LTE0IDM2LTcgNTcgMyAxMCA5IDE4IDEzIDI0IDMgNCA2IDcgNyA4djZhMiAyIDAgMCAwIDQgMHYtNmMxLTEgNC0zIDctOCA0LTYgMTAtMTQgMTMtMjQgNy0yMSA1LTQyLTctNTctOS0xMS0yMy0xNi0yNC0xOHoiLz48L3N2Zz4=',
  mariadb:    'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4Ij48cGF0aCBmaWxsPSIjMDAzNTQ1IiBkPSJNNjQgOEMzMy4xIDggOCAzMy4xIDggNjRzMjUuMSA1NiA1NiA1NiA1Ni0yNS4xIDU2LTU2Uzk0LjkgOCA2NCA4eiIvPjwvc3ZnPg==',
}

function _logoUrl(dbType) {
  const t = (dbType||'').toLowerCase()
  if (t.includes('mysql')||t.includes('aurora'))   return _LOGOS.mysql
  if (t.includes('mariadb'))                        return _LOGOS.mariadb
  if (t.includes('mssql')||t.includes('sqlserver')) return _LOGOS.mssql
  if (t.includes('postgres')||t.includes('pg'))     return _LOGOS.postgresql
  if (t.includes('oracle'))                         return _LOGOS.oracle
  if (t.includes('mongo'))                          return _LOGOS.mongodb
  return _LOGOS.mssql
}

const srcLogoUrl = computed(() => props.srcDb?.dbType ? _logoUrl(props.srcDb.dbType) : null)
const tgtLogoUrl = computed(() => props.tgtDb?.dbType ? _logoUrl(props.tgtDb.dbType) : null)
</script>

<style scoped>
/* ── 헤더 바 ── */
.ph-bar  { padding: 5px 10px; }
.ph-row  {
  display: flex; align-items: center;
  gap: 0; overflow-x: auto; white-space: nowrap;
  scrollbar-width: none;
}
.ph-row::-webkit-scrollbar { display: none; }

/* ── DB 박스 ── */
.ph-db-box {
  display: inline-flex; align-items: center; gap: 7px;
  padding: 3px 9px 3px 5px;
  border: 0.5px solid var(--border-light);
  border-radius: 8px; background: var(--bg-secondary);
  flex-shrink: 0;
}
.ph-db-box.src { border-color: rgba(59,130,246,.22); background: rgba(59,130,246,.04); }
.ph-db-box.tgt { border-color: rgba(16,185,129,.22);  background: rgba(16,185,129,.04); }

.ph-cyl-wrap {
  position: relative; width: 28px; height: 28px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.ph-cyl    { width: 28px; height: 28px; }
.ph-db-logo {
  position: absolute; width: 12px; height: 12px; object-fit: contain;
  top: 50%; left: 50%; transform: translate(-50%,-50%);
}
.ph-online {
  position: absolute; top: 0; right: 0;
  width: 7px; height: 7px; border-radius: 50%;
  border: 1.5px solid var(--bg-primary);
}
.ph-online.src { background: #22c55e; }
.ph-online.tgt { background: #22c55e; }

.ph-db-info  { display: flex; flex-direction: column; gap: 0; }
.ph-db-label { font-size: .55rem; font-weight: 800; letter-spacing: .07em; text-transform: uppercase; }
.ph-db-label.src { color: #2563eb; }
.ph-db-label.tgt { color: #059669; }
.ph-db-nm  { font-size: .76rem; font-weight: 700; color: var(--text-primary); line-height: 1.3; }
.ph-db-tp  { font-size: .62rem; color: var(--text-tertiary); line-height: 1.2; }

.ph-arrow  { padding: 0 6px; flex-shrink: 0; }
.ph-divider {
  width: 0.5px; height: 22px; background: var(--border-light);
  flex-shrink: 0; margin: 0 4px;
}

/* ── 액션 버튼 그룹 (우측 고정) ── */
.ph-actions {
  display: inline-flex; align-items: center; gap: 3px;
  margin-left: auto; padding-left: 10px;
  border-left: 0.5px solid var(--border-light);
  flex-shrink: 0;
}
</style>
