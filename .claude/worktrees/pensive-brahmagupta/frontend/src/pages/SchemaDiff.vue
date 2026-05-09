<template>
  <div class="sd-wrap">

    <!-- 연결 경고 -->
    <div v-if="!connector.source.host" class="sd-warn">
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px;flex-shrink:0"><path d="M8 2L14 14H2L8 2z"/><line x1="8" y1="7" x2="8" y2="10"/><circle cx="8" cy="12" r=".5" fill="currentColor"/></svg>
      소스 DB 연결이 필요합니다.
      <button class="sd-warn-btn" @click="$router.push('/connector')">커넥터 관리 →</button>
    </div>

    <!-- 상단 컨트롤 바 (PageHeader 공통 스타일) -->
    <PageHeader :show-db="true" :src-db="connector.source" :tgt-db="connector.target">
      <template #controls>
        <div class="ph-group">
          <span class="ph-group-label">테이블</span>
          <div class="sd-sel-wrap">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px;flex-shrink:0;color:var(--text-tertiary)">
              <rect x="1" y="1" width="12" height="12" rx="1.5"/>
              <line x1="1" y1="5" x2="13" y2="5"/><line x1="5" y1="5" x2="5" y2="13"/>
            </svg>
            <select v-model="selTable" @change="loadDiff" class="sd-select">
              <option value="">테이블 선택...</option>
              <option v-for="t in tables" :key="t.table_name" :value="t.table_name">{{ t.table_name }}</option>
            </select>
          </div>
          <button class="chip" @click="loadTables" :disabled="loading">
            <span v-if="loading" class="sd-spin"></span>
            <svg v-else viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px">
              <path d="M1 7a6 6 0 1 0 6-6"/><polyline points="4,1 1,1 1,4"/>
            </svg>
            {{ loading ? '조회 중...' : '목록 로드' }}
          </button>
        </div>
        <!-- 통계 -->
        <template v-if="selTable && diffData">
          <div class="ph-group">
            <span class="sd-stat-chip changed">
              <span class="sd-stat-dot changed"></span>변환 {{ changedCount }}줄
            </span>
            <span v-if="diffData.warnings?.length" class="sd-stat-chip warn">
              <span class="sd-stat-dot warn"></span>주의 {{ diffData.warnings.length }}건
            </span>
          </div>
        </template>
      </template>
    </PageHeader>

    <!-- 경고 배너 -->
    <div v-if="diffData?.warnings?.length" class="sd-warn-bar">
      <div v-for="w in diffData.warnings" :key="w" class="sd-warn-item">
        <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:11px;height:11px;flex-shrink:0"><path d="M6 1L11 11H1L6 1z"/><line x1="6" y1="5" x2="6" y2="8"/></svg>
        {{ w }}
      </div>
    </div>

    <!-- 빈 상태 -->
    <div v-if="!selTable" class="sd-empty">
      <div class="sd-empty-icon">
        <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.2" style="width:48px;height:48px;opacity:.25">
          <rect x="4" y="4" width="40" height="40" rx="4"/>
          <line x1="4" y1="16" x2="44" y2="16"/>
          <line x1="4" y1="28" x2="44" y2="28"/>
          <line x1="16" y1="16" x2="16" y2="44"/>
        </svg>
      </div>
      <div class="sd-empty-text">테이블을 선택하면 DDL 변환 Diff를 확인할 수 있습니다</div>
      <div class="sd-empty-sub">소스 DDL → 타겟 DB 방언으로 변환된 결과를 나란히 비교합니다</div>
    </div>

    <!-- Diff 뷰어 -->
    <div v-else-if="diffData" class="sd-diff-card">

      <!-- Diff 헤더 -->
      <div class="sd-diff-header">
        <div class="sd-diff-col-hdr src">
          <div class="sd-dh-badge src">소스 · {{ srcDbLabel }}</div>
          <div class="sd-dh-detail">
            <span class="sd-dh-db">{{ connector.source.database }}</span>
            <span class="sd-dh-sep">›</span>
            <span class="sd-dh-tbl">{{ selTable }}</span>
          </div>
        </div>
        <div class="sd-diff-col-hdr tgt">
          <div class="sd-dh-badge tgt">타겟 · {{ tgtDbLabel }}</div>
          <div class="sd-dh-detail">
            <span class="sd-dh-db">{{ connector.target.database }}</span>
            <span class="sd-dh-sep">›</span>
            <span class="sd-dh-tbl">{{ selTable }}</span>
          </div>
        </div>
      </div>

      <!-- Diff 본문 -->
      <div class="sd-diff-body">
        <!-- 소스 -->
        <div class="sd-diff-pane">
          <div v-for="(l, i) in srcLines" :key="i"
               class="sd-line" :class="l.cls">
            <span class="sd-ln">{{ i + 1 }}</span>
            <span class="sd-lc" :class="l.cls">{{ l.text || ' ' }}</span>
          </div>
        </div>
        <!-- 타겟 -->
        <div class="sd-diff-pane sd-diff-pane-right">
          <div v-for="(l, i) in tgtLines" :key="i"
               class="sd-line" :class="l.cls">
            <span class="sd-ln">{{ i + 1 }}</span>
            <span class="sd-lc" :class="l.cls">{{ l.text || ' ' }}</span>
          </div>
        </div>
      </div>

      <!-- 범례 푸터 -->
      <div class="sd-footer">
        <div class="sd-legend">
          <span class="sd-leg-item">
            <span class="sd-leg-swatch changed"></span>변환됨
          </span>
          <span class="sd-leg-item">
            <span class="sd-leg-swatch added"></span>추가됨
          </span>
          <span class="sd-leg-item">
            <span class="sd-leg-swatch removed"></span>제거됨
          </span>
        </div>
        <div class="sd-footer-stats">
          총 {{ Math.max(srcLines.length, tgtLines.length) }}줄
          <span class="sd-dot-sep">·</span>
          변환 {{ changedCount }}줄
          <span v-if="diffData.warnings?.length" class="sd-dot-sep">·</span>
          <span v-if="diffData.warnings?.length" style="color:var(--text-warning)">주의 {{ diffData.warnings.length }}건</span>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { useConnectorStore } from '@/store/connectorStore.js'
import PageHeader from '@/components/layout/PageHeader.vue'

const connector = useConnectorStore()
const tables   = ref([])
const selTable = ref('')
const diffData = ref(null)
const loading  = ref(false)

const DB_LABELS = {
  mssql:'SQL Server', sqlserver:'SQL Server', azure:'Azure SQL',
  mysql:'MySQL', mariadb:'MariaDB', aurora:'Aurora MySQL',
  postgresql:'PostgreSQL', postgres:'PostgreSQL',
  oracle:'Oracle', db2:'IBM DB2', tidb:'TiDB', snowflake:'Snowflake',
}
const srcDbLabel = computed(() => {
  const t = connector.source.dbType || connector.source.db_type || ''
  return DB_LABELS[t.toLowerCase()] || t.toUpperCase() || 'DB'
})
const tgtDbLabel = computed(() => {
  const t = connector.target.dbType || connector.target.db_type || ''
  return DB_LABELS[t.toLowerCase()] || t.toUpperCase() || 'DB'
})

async function loadTables() {
  const c = connector.source
  if (!c.host || !c.database) return
  loading.value = true
  try {
    const { data } = await axios.get('/api/v1/schema/tables', {
      params: { side:'source', db_type:c.dbType, host:c.host, port:c.port,
                username:c.username, password:c.password, database:c.database }
    })
    tables.value = data
  } catch(e) { console.error(e) }
  finally { loading.value = false }
}

async function loadDiff() {
  if (!selTable.value) return
  try {
    const src = connector.source, tgt = connector.target
    if (src.host) await axios.post('/api/v1/schema/connection', {
      side:'source', db_type:src.dbType, host:src.host, port:src.port,
      username:src.username, password:src.password, database:src.database
    })
    if (tgt.host) await axios.post('/api/v1/schema/connection', {
      side:'target', db_type:tgt.dbType, host:tgt.host, port:tgt.port,
      username:tgt.username, password:tgt.password, database:tgt.database
    })
    const { data } = await axios.get('/api/v1/schema/diff', {
      params: { src:'source', tgt:'target', table:selTable.value }
    })
    diffData.value = data
  } catch(e) { console.error(e) }
}

const DIFF_PAIRS = [
  { src:'AUTO_INCREMENT', tgt:'IDENTITY' },
  { src:'VARCHAR(',       tgt:'NVARCHAR(' },
  { src:'TINYINT(1)',     tgt:'BIT' },
  { src:'DATETIME',       tgt:'DATETIME2' },
  { src:'LONGTEXT',       tgt:'NVARCHAR(MAX)' },
  { src:'LONGBLOB',       tgt:'VARBINARY(MAX)' },
  { src:'ENGINE=',        tgt:'-- ENGINE' },
  { src:'BIGINT UNSIGNED',tgt:'DECIMAL(20,0)' },
  { src:'INT UNSIGNED',   tgt:'BIGINT' },
  { src:'CHARACTER SET',  tgt:'-- CHARSET' },
]

function buildDiffLines(ddl, side) {
  if (!ddl) return []
  return ddl.split('\n').map(line => {
    const u = line.toUpperCase()
    let cls = ''
    for (const p of DIFF_PAIRS) {
      const key = side === 'src' ? p.src : p.tgt
      if (u.includes(key.toUpperCase())) { cls = side === 'src' ? 'changed' : 'added'; break }
    }
    if (side === 'src' && (u.includes('ENGINE=') || u.includes('CHARSET=') || u.includes('CHARACTER SET')))
      cls = 'removed'
    return { text: line, cls }
  })
}

const srcLines     = computed(() => diffData.value ? buildDiffLines(diffData.value.src_ddl, 'src') : [])
const tgtLines     = computed(() => diffData.value ? buildDiffLines(diffData.value.tgt_ddl, 'tgt') : [])
const changedCount = computed(() =>
  srcLines.value.filter(l => l.cls).length + tgtLines.value.filter(l => l.cls).length)

onMounted(() => { if (connector.source.status === 'ok') loadTables() })
</script>

<style scoped>
/* ── 레이아웃 ── */
.sd-wrap { display:flex; flex-direction:column; gap:10px; }

/* ── 경고 ── */
.sd-warn {
  display:flex; align-items:center; gap:8px;
  padding:9px 14px; background:var(--bg-warning);
  border-radius:8px; font-size:12px; color:var(--text-warning);
}
.sd-warn-btn {
  margin-left:auto; font-size:11px; padding:3px 9px;
  border-radius:6px; border:0.5px solid rgba(245,158,11,.4);
  background:transparent; color:#b45309; cursor:pointer;
  font-family:var(--font);
}
.sd-warn-btn:hover { background:rgba(245,158,11,.1); }

/* ── 상단 컨트롤 바 ── */
.sd-topbar {
  display:flex; align-items:center; gap:10px; flex-wrap:wrap;
  padding:10px 14px;
  background:var(--bg-primary);
  border:0.5px solid var(--border-light);
  border-radius:10px;
}

/* DB 칩 */
.sd-db-chip {
  display:flex; align-items:center; gap:8px;
  padding:5px 10px 5px 6px;
  border-radius:8px; border:0.5px solid var(--border-light);
  background:var(--bg-secondary);
}
.sd-db-cyl { flex-shrink:0; }
.sd-db-info { display:flex; flex-direction:column; gap:1px; }
.sd-db-type {
  font-size:9.5px; font-weight:700; letter-spacing:.4px;
  text-transform:uppercase; padding:1px 5px; border-radius:4px;
  display:inline-block;
}
.sd-db-type.src { background:var(--bg-info); color:var(--text-info); }
.sd-db-type.tgt { background:var(--bg-success); color:var(--text-success); }
.sd-db-name {
  font-size:12.5px; font-weight:600; color:var(--text-primary);
  font-family:'Consolas','SF Mono',monospace;
}

/* 화살표 */
.sd-arrow { display:flex; flex-direction:column; align-items:center; gap:2px; flex-shrink:0; }
.sd-arrow-label { font-size:9.5px; color:var(--text-tertiary); letter-spacing:.3px; white-space:nowrap; }

.sd-divider { width:0.5px; height:28px; background:var(--border-light); flex-shrink:0; margin:0 4px; }

/* 테이블 셀렉트 */
.sd-sel-wrap {
  display:flex; align-items:center; gap:7px;
  padding:6px 10px;
  border:0.5px solid var(--border-mid); border-radius:8px;
  background:var(--bg-secondary); flex:1; min-width:160px; max-width:300px;
}
.sd-select {
  flex:1; border:none; background:transparent; font-size:12.5px;
  color:var(--text-primary); font-family:var(--font); cursor:pointer; outline:none;
  appearance:none;
}

/* 버튼 */
.sd-btn {
  display:inline-flex; align-items:center; gap:5px;
  padding:6px 12px; border-radius:8px; font-size:11.5px; font-weight:500;
  font-family:var(--font); cursor:pointer;
  border:0.5px solid var(--border-mid);
  background:var(--bg-secondary); color:var(--text-secondary);
  transition:all .12s; white-space:nowrap; flex-shrink:0;
}
.sd-btn:hover { background:var(--bg-tertiary); }
.sd-btn:disabled { opacity:.5; cursor:not-allowed; }

/* 통계 칩 */
.sd-stat-chip {
  display:inline-flex; align-items:center; gap:5px;
  font-size:11px; font-weight:500; padding:4px 9px;
  border-radius:8px; white-space:nowrap; flex-shrink:0;
}
.sd-stat-chip.changed { background:rgba(245,158,11,.1); color:#b45309; border:0.5px solid rgba(245,158,11,.3); }
.sd-stat-chip.warn    { background:rgba(239,68,68,.08);  color:#dc2626; border:0.5px solid rgba(239,68,68,.25); }
.sd-stat-dot { width:6px; height:6px; border-radius:50%; flex-shrink:0; }
.sd-stat-dot.changed { background:#f59e0b; }
.sd-stat-dot.warn    { background:#ef4444; }

/* 경고 바 */
.sd-warn-bar {
  padding:8px 14px; background:rgba(245,158,11,.07);
  border:0.5px solid rgba(245,158,11,.25); border-radius:8px;
  display:flex; flex-direction:column; gap:4px;
}
.sd-warn-item {
  display:flex; align-items:center; gap:6px;
  font-size:11.5px; color:#b45309;
}

/* 스피너 */
.sd-spin {
  width:11px; height:11px; border-radius:50%;
  border:1.5px solid var(--border-mid);
  border-top-color:var(--accent-blue);
  animation:sd-spin .7s linear infinite; display:inline-block;
}
@keyframes sd-spin { to { transform:rotate(360deg); } }

/* ── 빈 상태 ── */
.sd-empty {
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  gap:10px; padding:52px 24px;
  background:var(--bg-primary); border:0.5px solid var(--border-light);
  border-radius:10px;
}
.sd-empty-text { font-size:13.5px; font-weight:600; color:var(--text-secondary); }
.sd-empty-sub  { font-size:12px; color:var(--text-tertiary); }

/* ── Diff 카드 ── */
.sd-diff-card {
  background:var(--bg-primary);
  border:0.5px solid var(--border-light);
  border-radius:10px; overflow:hidden;
}

/* Diff 헤더 */
.sd-diff-header { display:grid; grid-template-columns:1fr 1fr; border-bottom:0.5px solid var(--border-light); }
.sd-diff-col-hdr {
  padding:10px 14px; display:flex; flex-direction:column; gap:4px;
}
.sd-diff-col-hdr.src { background:rgba(59,130,246,.04); border-right:0.5px solid var(--border-light); }
.sd-diff-col-hdr.tgt { background:rgba(16,185,129,.04); }

.sd-dh-badge {
  display:inline-flex; align-items:center; gap:4px;
  font-size:10px; font-weight:700; letter-spacing:.5px;
  text-transform:uppercase; padding:2px 7px; border-radius:5px;
  width:fit-content;
}
.sd-dh-badge.src { background:var(--bg-info); color:var(--text-info); }
.sd-dh-badge.tgt { background:var(--bg-success); color:var(--text-success); }

.sd-dh-detail { display:flex; align-items:center; gap:5px; }
.sd-dh-db  { font-size:13px; font-weight:600; color:var(--text-primary); font-family:'Consolas','SF Mono',monospace; }
.sd-dh-sep { font-size:12px; color:var(--text-tertiary); }
.sd-dh-tbl { font-size:12px; color:var(--text-secondary); font-family:'Consolas','SF Mono',monospace;
             background:var(--bg-secondary); padding:1px 7px; border-radius:4px; }

/* Diff 본문 */
.sd-diff-body { display:grid; grid-template-columns:1fr 1fr; }
.sd-diff-pane {
  font-family:'Consolas','SF Mono',monospace; font-size:12px;
  overflow-x:auto; max-height:560px; overflow-y:auto;
  padding:6px 0;
}
.sd-diff-pane-right { border-left:0.5px solid var(--border-light); }

/* 줄 */
.sd-line { display:flex; align-items:baseline; line-height:1.75; min-height:22px; }
.sd-line.changed { background:rgba(251,191,36,.13); }
.sd-line.added   { background:rgba(34,197,94,.1); }
.sd-line.removed { background:rgba(239,68,68,.1); }

.sd-ln {
  width:38px; text-align:right; padding:0 10px 0 0;
  font-size:10.5px; color:var(--text-tertiary);
  user-select:none; flex-shrink:0; line-height:1.75;
}
.sd-line.changed .sd-ln { color:#d97706; }
.sd-line.added   .sd-ln { color:#16a34a; }
.sd-line.removed .sd-ln { color:#dc2626; }

.sd-lc { white-space:pre; color:var(--text-secondary); padding-right:14px; }
.sd-lc.changed { color:#92400e; font-weight:500; }
.sd-lc.added   { color:#14532d; font-weight:500; }
.sd-lc.removed { color:#991b1b; text-decoration:line-through; opacity:.7; }

[data-theme="dark"] .sd-lc.changed { color:#fcd34d; }
[data-theme="dark"] .sd-lc.added   { color:#86efac; }
[data-theme="dark"] .sd-lc.removed { color:#fca5a5; }
[data-theme="dark"] .sd-line.changed { background:rgba(251,191,36,.1); }
[data-theme="dark"] .sd-line.added   { background:rgba(34,197,94,.08); }
[data-theme="dark"] .sd-line.removed { background:rgba(239,68,68,.08); }

/* 푸터 */
.sd-footer {
  display:flex; align-items:center; justify-content:space-between;
  padding:7px 14px; background:var(--bg-secondary);
  border-top:0.5px solid var(--border-light); flex-wrap:wrap; gap:8px;
}
.sd-legend { display:flex; align-items:center; gap:12px; }
.sd-leg-item { display:flex; align-items:center; gap:5px; font-size:11px; color:var(--text-secondary); }
.sd-leg-swatch { width:12px; height:12px; border-radius:2px; flex-shrink:0; }
.sd-leg-swatch.changed { background:rgba(251,191,36,.35); border:0.5px solid #d97706; }
.sd-leg-swatch.added   { background:rgba(34,197,94,.3);   border:0.5px solid #16a34a; }
.sd-leg-swatch.removed { background:rgba(239,68,68,.25);  border:0.5px solid #dc2626; }

.sd-footer-stats { font-size:11px; color:var(--text-tertiary); display:flex; align-items:center; gap:5px; }
.sd-dot-sep { color:var(--border-mid); }
</style>
