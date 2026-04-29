/**
 * constants/dbMeta.js
 *
 * 프론트엔드 DB 메타데이터.
 * UI 표시용 색상/라벨/포트 등 시각 자원은 여기서 정적 관리하고,
 * tier(지원 레벨)는 런타임에 백엔드 /api/v1/connectors/supported-dbs에서
 * 가져와 덮어씌운다 (loadSupportTiers 호출).
 *
 * Tier 정의:
 *   full    : 완전 지원 (연결+스키마+이관+SQL변환)
 *   connect : 연결·스키마 조회만
 *   planned : 로드맵 (선택 불가)
 */

export const TIER = Object.freeze({
  FULL: 'full',
  CONNECT: 'connect',
  PLANNED: 'planned',
})

/**
 * DB_META 기본값 — 백엔드 SSOT와 동기화되는 것이 원칙.
 * 백엔드 응답이 오기 전에 UI가 깜빡이지 않도록 fallback 역할.
 */
export const DB_META = {
  // ── Tier 1: Full Support ──
  mssql:      {label:'MS', bg:'#e6f1fb', color:'#185fa5', port:1433,  tier: TIER.FULL,    versions:['SQL Server 2022','SQL Server 2019','SQL Server 2017','SQL Server 2016']},
  mysql:      {label:'My', bg:'#eaf3de', color:'#3b6d11', port:3306,  tier: TIER.FULL,    versions:['MySQL 8.0','MySQL 5.7']},
  mariadb:    {label:'Ma', bg:'#eaf3de', color:'#3b6d11', port:3306,  tier: TIER.FULL,    versions:['MariaDB 10.11','MariaDB 10.6']},
  postgresql: {label:'PG', bg:'#e6f1fb', color:'#185fa5', port:5432,  tier: TIER.FULL,    versions:['PostgreSQL 16','PostgreSQL 15','PostgreSQL 14','PostgreSQL 13']},
  aurora:     {label:'Au', bg:'#eaf3de', color:'#3b6d11', port:3306,  tier: TIER.FULL,    versions:['Aurora MySQL 3','Aurora MySQL 2']},
  cloudsql:   {label:'GC', bg:'#faeeda', color:'#854f0b', port:3306,  tier: TIER.FULL,    versions:['Cloud SQL MySQL 8']},
  tidb:       {label:'Ti', bg:'#eeedfe', color:'#534ab7', port:4000,  tier: TIER.FULL,    versions:['TiDB 7']},
  azure:      {label:'Az', bg:'#e6f1fb', color:'#185fa5', port:1433,  tier: TIER.FULL,    versions:['Azure SQL 2022','Azure SQL 2019']},

  // ── Tier 2: Connect only ──
  oracle:     {label:'Or', bg:'#fff0eb', color:'#993c1d', port:1521,  tier: TIER.CONNECT, versions:['Oracle 21c','Oracle 19c','Oracle 12c','Oracle 11g']},
  sqlite:     {label:'SL', bg:'#f1efe8', color:'#5f5e5a', port:null,  tier: TIER.CONNECT, versions:['SQLite 3.x']},

  // ── Tier 3: Planned (UI에 회색/disabled 표시) ──
  redshift:   {label:'RS', bg:'#e6f1fb', color:'#185fa5', port:5439,  tier: TIER.PLANNED, versions:['Redshift (최신)']},
  snowflake:  {label:'SF', bg:'#faece7', color:'#993c1d', port:443,   tier: TIER.PLANNED, versions:['Snowflake (최신)']},
  bigquery:   {label:'BQ', bg:'#eaf3de', color:'#3b6d11', port:443,   tier: TIER.PLANNED, versions:['BigQuery (최신)']},
  mongodb:    {label:'Mo', bg:'#eaf3de', color:'#3b6d11', port:27017, tier: TIER.PLANNED, versions:['MongoDB 7','MongoDB 6']},
  db2:        {label:'DB', bg:'#eeedfe', color:'#534ab7', port:50000, tier: TIER.PLANNED, versions:['DB2 12','DB2 11.5']},
  hana:       {label:'HA', bg:'#faeeda', color:'#854f0b', port:30015, tier: TIER.PLANNED, versions:['HANA 2.0 SPS07']},
  sybase:     {label:'Sy', bg:'#faece7', color:'#993c1d', port:5000,  tier: TIER.PLANNED, versions:['ASE 16']},
  teradata:   {label:'Td', bg:'#eeedfe', color:'#534ab7', port:1025,  tier: TIER.PLANNED, versions:['Teradata 17']},
  clickhouse: {label:'CH', bg:'#faeeda', color:'#854f0b', port:8123,  tier: TIER.PLANNED, versions:['ClickHouse 23']},
  duckdb:     {label:'DK', bg:'#f1efe8', color:'#5f5e5a', port:null,  tier: TIER.PLANNED, versions:['DuckDB 0.9']},
}

/**
 * 백엔드 SSOT에서 지원 정보를 가져와 DB_META를 동기화.
 * 앱 부트스트랩 시 한 번 호출하면 이후 전역에서 최신 tier를 참조.
 * 실패해도 앱은 정상 동작 (정적 기본값 유지).
 */
export async function loadSupportTiers() {
  try {
    // X-Auth-Token 헤더 직접 주입 (axios 인스턴스 순환 import 회피)
    const token = localStorage.getItem('databridge_auth_token') || ''
    const res = await fetch('/api/v1/connectors/supported-dbs', {
      headers: token ? { 'X-Auth-Token': token } : {},
    })
    if (!res.ok) return false
    const { dbs } = await res.json()
    if (!Array.isArray(dbs)) return false
    for (const d of dbs) {
      const key = (d.key || '').toLowerCase()
      if (DB_META[key]) {
        DB_META[key].tier = d.tier
        if (d.label) DB_META[key].serverLabel = d.label
        if (d.note)  DB_META[key].note = d.note
      }
    }
    return true
  } catch (_e) {
    return false
  }
}

export function isFullySupported(key) {
  return DB_META[key]?.tier === TIER.FULL
}

export function isSelectable(key) {
  const t = DB_META[key]?.tier
  return t === TIER.FULL || t === TIER.CONNECT
}

export function tierBadge(key) {
  switch (DB_META[key]?.tier) {
    case TIER.FULL:    return { text: '지원', kind: 'success' }
    case TIER.CONNECT: return { text: '연결만', kind: 'warning' }
    case TIER.PLANNED: return { text: '준비중', kind: 'muted'   }
    default:           return { text: '?',      kind: 'muted'   }
  }
}

export function listDbs(filter = 'all') {
  const order = { [TIER.FULL]: 0, [TIER.CONNECT]: 1, [TIER.PLANNED]: 2 }
  const entries = Object.entries(DB_META).map(([key, v]) => ({ key, ...v }))
  const filtered = filter === 'all'         ? entries
                 : filter === 'selectable'  ? entries.filter(e => isSelectable(e.key))
                 : filter === 'full'        ? entries.filter(e => e.tier === TIER.FULL)
                 : entries
  return filtered.sort((a, b) => (order[a.tier] ?? 9) - (order[b.tier] ?? 9))
}

// ── 레거시 호환 (기존 페이지들이 import하던 구조 유지) ──
// 정직화: SOURCE/TARGET에 "선택 가능한 DB"만 포함 (planned 제외)
export const SOURCE_DBS = [
  {value:'mssql',      name:'Microsoft SQL Server'},
  {value:'mysql',      name:'MySQL'},
  {value:'mariadb',    name:'MariaDB'},
  {value:'postgresql', name:'PostgreSQL'},
  {value:'aurora',     name:'Amazon Aurora (MySQL)'},
  {value:'cloudsql',   name:'Google Cloud SQL (MySQL)'},
  {value:'tidb',       name:'TiDB'},
  {value:'azure',      name:'Azure SQL Database'},
  {value:'oracle',     name:'Oracle Database'},
  {value:'sqlite',     name:'SQLite'},
]

export const TARGET_DBS = [
  {value:'mysql',      name:'MySQL'},
  {value:'mariadb',    name:'MariaDB'},
  {value:'postgresql', name:'PostgreSQL'},
  {value:'mssql',      name:'Microsoft SQL Server'},
  {value:'aurora',     name:'Amazon Aurora (MySQL)'},
  {value:'cloudsql',   name:'Google Cloud SQL (MySQL)'},
  {value:'tidb',       name:'TiDB'},
  {value:'azure',      name:'Azure SQL Database'},
  // v10 #20c: UI 일관성 — 소스와 동일 10종. 이관 가능 여부는 백엔드
  // is_migration_supported() 검증에서 걸러짐 (Oracle/SQLite 는 현재 CONNECT tier).
  {value:'oracle',     name:'Oracle Database'},
  {value:'sqlite',     name:'SQLite'},
]
