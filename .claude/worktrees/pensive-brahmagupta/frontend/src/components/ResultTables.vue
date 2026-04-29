<template>
  <div class="res-tables">
    <div v-for="side in ['src','tgt']" :key="side" class="res-tbl-panel">
      <div class="res-tbl-hdr" :class="side">
        <span class="tbl-side-label">{{ side==='src'?'🔵 소스':'🟢 타겟' }}</span>
        <span class="tbl-row-cnt">{{ result[side].row_count }}행</span>
        <span class="tbl-ms">{{ result[side].elapsed_ms }}ms</span>
        <span v-if="sortCol[side]" class="sort-badge">
          {{ sortCol[side] }} {{ sortDir[side]==='asc'?'▲':'▼' }}
          <button class="sort-clear" @click.stop="sortCol[side]='';sortDir[side]='asc'">✕</button>
        </span>
      </div>
      <div class="res-tbl-scroll">
        <table v-if="result[side].rows?.length" class="rt">
          <thead>
            <tr>
              <th v-for="c in result[side].cols" :key="c"
                  @click="toggleSort(side,c)" class="rt-th-sort">
                {{ c }}<span class="sort-ico">{{ sortCol[side]===c?(sortDir[side]==='asc'?'▲':'▼'):'⇅' }}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row,ri) in sortedRows(side)" :key="ri"
                :class="{diffrow: side==='src' && diffRowSet.has(ri)}">
              <td v-for="(cell,ci) in row" :key="ci"
                  :class="{'diffcell': side==='src' && diffCellMap[ri]?.has(ci)}"
                  :title="String(cell??'')">{{ cell ?? '' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else-if="result[side].ok" class="tbl-empty">결과 없음</div>
        <div v-else class="tbl-empty tbl-err">✗ {{ result[side].error }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue'

const props = defineProps({
  result:     { type: Object, required: true },
  diffRowSet: { type: Object, default: () => new Set() },
  diffCellMap:{ type: Object, default: () => ({}) },
})

const sortCol = reactive({ src: '', tgt: '' })
const sortDir = reactive({ src: 'asc', tgt: 'asc' })

// result 바뀌면 정렬 초기화
watch(() => props.result, () => {
  sortCol.src = ''; sortCol.tgt = ''
  sortDir.src = 'asc'; sortDir.tgt = 'asc'
})

function toggleSort(side, col) {
  if (sortCol[side] === col) {
    sortDir[side] = sortDir[side] === 'asc' ? 'desc' : 'asc'
  } else {
    sortCol[side] = col
    sortDir[side] = 'asc'
  }
}

function sortedRows(side) {
  if (!props.result?.[side]?.rows) return []
  const rows = props.result[side].rows
  const col  = sortCol[side]
  if (!col) return rows
  const ci  = props.result[side].cols.indexOf(col)
  if (ci < 0) return rows
  const dir = sortDir[side] === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    const av = a[ci] ?? '', bv = b[ci] ?? ''
    if (av === bv) return 0
    if (av === null || av === '') return dir
    if (bv === null || bv === '') return -dir
    const an = parseFloat(av), bn = parseFloat(bv)
    if (!isNaN(an) && !isNaN(bn)) return (an - bn) * dir
    return String(av).localeCompare(String(bv)) * dir
  })
}
</script>

<style scoped>
.res-tables {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  padding: 10px;
}
.res-tbl-panel {
  display: flex;
  flex-direction: column;
  border: 0.5px solid var(--border-light);
  border-radius: 8px;
  overflow: hidden;
  min-height: 0;
}
.res-tbl-hdr {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  font-size: .72rem;
  font-weight: 700;
  border-bottom: 0.5px solid var(--border-light);
  background: var(--bg-secondary);
  flex-shrink: 0;
}
.res-tbl-hdr.src { color: #2563eb; }
.res-tbl-hdr.tgt { color: #059669; }
.tbl-side-label  { font-size: .7rem; }
.tbl-row-cnt     { font-size: .65rem; color: var(--text-tertiary); }
.tbl-ms          { font-size: .62rem; color: var(--text-tertiary); margin-left: auto; }
.sort-badge {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: .62rem;
  background: rgba(37,99,235,.08);
  color: #2563eb;
  padding: 1px 5px;
  border-radius: 6px;
}
.sort-clear {
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--text-tertiary);
  font-size: .65rem;
  padding: 0;
  line-height: 1;
}
.res-tbl-scroll {
  overflow: auto;
  max-height: 320px;
  flex: 1;
}
.res-tbl-scroll::-webkit-scrollbar { height: 5px; width: 5px; }
.res-tbl-scroll::-webkit-scrollbar-thumb { background: var(--border-mid); border-radius: 3px; }
.rt {
  border-collapse: collapse;
  font-size: .68rem;
  width: max-content;
  min-width: 100%;
}
.rt-th-sort {
  position: sticky;
  top: 0;
  background: var(--bg-secondary);
  padding: 4px 8px;
  text-align: left;
  font-weight: 700;
  white-space: nowrap;
  border-bottom: 0.5px solid var(--border-mid);
  cursor: pointer;
  user-select: none;
  color: var(--text-secondary);
}
.sort-ico { margin-left: 3px; font-size: .58rem; color: var(--text-tertiary); }
.rt tbody tr:hover td { background: var(--bg-hover); }
.rt td {
  padding: 3px 8px;
  border-bottom: 0.5px solid var(--border-light);
  white-space: nowrap;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.diffrow td  { background: rgba(220,38,38,.04); }
.diffcell    { background: rgba(245,158,11,.15) !important; font-weight: 600; }
.tbl-empty   { padding: 16px; text-align: center; font-size: .72rem; color: var(--text-tertiary); }
.tbl-err     { color: #dc2626; }
</style>
