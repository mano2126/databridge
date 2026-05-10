<template>
  <div class="monitor-page">

    <!--
      v10 #23h: ConnectPanel 제거.
      이관 Job 은 백엔드에서 실행되므로 프론트가 DB 에 연결되어 있을 필요 없음.
      그런데도 "DB 연결이 필요합니다" 패널이 뜨면 UX 망가짐 — 특히 Job 제출 직후
      redirect 되어 왔는데 다시 접속 요구하는 꼴이라 사용자 혼란 야기.
      대신 연결 정보가 있으면 PageHeader 로 간단히 표시만 함.
    -->
    <PageHeader v-if="conn.source?.database || conn.target?.database"
                :show-db="true"
                :src-db="conn.source"
                :tgt-db="conn.target" />

    <!-- 헤더 -->
    <div class="mon-header">
      <div>
        <div class="page-title">실시간 모니터</div>
        <div class="page-desc">실행 중인 마이그레이션 Job의 진행 상황을 실시간으로 확인합니다</div>
      </div>
      <div class="header-actions">
        <div class="ws-status" :class="wsConnected ? 'ws-ok' : 'ws-off'">
          <span class="ws-dot"></span>
          <span>{{ wsConnected ? 'WebSocket 연결됨' : '폴링 모드' }}</span>
        </div>
        <button class="act-btn icon-only" @click="manualRefresh" title="즉시 새로고침">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.6"
               style="width:12px;height:12px" :class="{spinning: refreshing}">
            <path d="M12 7A5 5 0 1 1 7 2"/><polyline points="8,2 12,2 12,5.5"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- KPI -->
    <div class="kpi-grid" style="margin-bottom:12px">
      <div class="kpi-card">
        <div class="kpi-label">실행 중</div>
        <div class="kpi-value" :class="running.length > 0 ? 'ok' : ''">{{ running.length }}<span class="kpi-unit">개</span></div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">처리 속도 (rows/s)</div>
        <div class="kpi-value info">{{ totalSpeed.toLocaleString() }}<span class="kpi-unit">rows/s</span></div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">누적 처리 rows</div>
        <div class="kpi-value">{{ fmtRows(cumulativeRows) }}<span class="kpi-unit">rows</span></div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">오류 건수</div>
        <div class="kpi-value" :class="totalErrors > 0 ? 'err' : ''">{{ totalErrors }}<span class="kpi-unit">건</span></div>
      </div>
    </div>

    <!-- 실행 중 Job 패널 -->
    <div class="card" style="margin-bottom:12px;padding:0;overflow:hidden">
      <div class="card-header">
        <span>실행 중인 Job</span>
        <div style="display:flex;align-items:center;gap:8px">
          <span class="refresh-dot" :class="{active: wsConnected || autoRefresh}"></span>
          <span style="font-size:11px;color:var(--text-tertiary)">
            {{ wsConnected ? 'WebSocket 실시간' : '2초 폴링' }}
          </span>
          <div class="toggle sm" :class="{on: autoRefresh}" @click="autoRefresh=!autoRefresh"></div>
          <button class="act-btn icon-only" @click="clearLogs" title="로그 초기화">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px">
              <polyline points="2,3.5 12,3.5"/>
              <path d="M5,3.5 V2 H9 V3.5"/>
              <path d="M3.5,3.5 L4.5,12 H9.5 L10.5,3.5"/>
            </svg>
          </button>
        </div>
      </div>

      <div v-if="!running.length" class="empty-state" style="padding:28px">
        <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.2"
             style="width:32px;height:32px;opacity:.3">
          <circle cx="24" cy="24" r="20"/>
          <polyline points="16,24 22,30 32,18"/>
        </svg>
        <p>현재 실행 중인 Job이 없습니다</p>
      </div>

      <div v-for="j in running" :key="j.id" class="mon-row">
        <div class="db-icon" :style="{background:m(j.src_db)?.bg, color:m(j.src_db)?.color}">
          {{ m(j.src_db)?.label }}
        </div>
        <div class="mon-info">
          <div class="item-name">{{ j.name }}</div>
          <div class="item-desc">
            <span v-if="j.job_type==='cdc'" class="cdc-badge">CDC</span>
            {{ j.src_database||j.src_db }} → {{ j.tgt_database||j.tgt_db }}
          </div>
          <div style="margin-top:4px;display:flex;align-items:center;gap:6px">
            <span class="pill" :class="pillCls(j.status)">{{ statusLbl(j.status) }}</span>
            <span v-if="j.table_total > 0" style="font-size:10.5px;color:var(--text-tertiary)">
              테이블 {{ j.table_done }}/{{ j.table_total }}
            </span>
          </div>
        </div>
        <div class="mon-prog">
          <div v-if="j.current_table" class="cur-tbl-row">
            <span class="cur-tbl-label">현재:</span>
            <span class="cur-tbl-name">{{ j.current_table }}</span>
            <span v-if="j.current_table_rows_total > 0" class="cur-tbl-cnt">
              {{ (j.current_table_rows_done||0).toLocaleString() }}
              / {{ (j.current_table_rows_total||0).toLocaleString() }} rows
            </span>
            <span v-if="jobCurrentTableEta(j)" class="cur-tbl-eta">⏱ {{ jobCurrentTableEta(j) }}</span>
          </div>
          <div class="prog-meta">
            <span class="prog-pct">{{ (j.progress||0).toFixed(1) }}%</span>
            <span>{{ (j.speed||0).toLocaleString() }} rows/s</span>
            <span v-if="jobTotalEta(j)" class="prog-eta">전체 남은 {{ jobTotalEta(j) }}</span>
            <span v-if="j.rows_error > 0" style="color:var(--text-danger)">오류 {{ j.rows_error }}건</span>
          </div>
          <div class="progress-wrap">
            <div class="progress-fill" :class="j.status==='paused'?'warn':'blue'"
                 :style="{width:(j.progress||0)+'%'}"></div>
          </div>
          <div class="rows-meta">
            처리: <b>{{ jobRowsProcessed(j).toLocaleString() }}</b> rows
            / 전체: {{ jobRowsTotal(j).toLocaleString() }} rows
          </div>
        </div>
        <div class="mon-acts">
          <button v-if="j.status==='running'" class="act-btn warn" @click="doPause(j.id)">일시정지</button>
          <button v-if="j.status==='paused'"  class="act-btn ok"   @click="doResume(j.id)">재개</button>
          <button v-if="['running','paused'].includes(j.status)"
                  class="act-btn del" @click="doStop(j.id)">중단</button>
          <button class="act-btn" @click="focusJob(j.id)" title="로그 보기">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px">
              <circle cx="6" cy="6" r="4"/><line x1="9.5" y1="9.5" x2="13" y2="13"/>
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- v9 패치 #20: 두 섹션(전체 Job 현황 / 실시간 로그) 순서 교체 가능 -->
    <!-- 전체 Job 현황 -->
    <div class="card" :style="{order: swapLayout ? 2 : 1, marginBottom:'12px', padding:0, overflow:'hidden'}">
      <div class="card-header">
        <span>전체 Job 현황</span>
        <div style="display:flex;align-items:center;gap:8px">
          <label class="chk-all">
            <input type="checkbox"
              :checked="pagedJobs.length > 0 && pagedJobs.every(j => selectedIds.has(j.id))"
              :indeterminate.prop="selectedIds.size > 0 && !pagedJobs.every(j => selectedIds.has(j.id))"
              @change="togglePageAll"
              style="accent-color:var(--accent-blue);width:13px;height:13px"/>
            <span style="font-size:11.5px;color:var(--text-secondary)">
              {{ selectedIds.size > 0 ? selectedIds.size + '개 선택됨' : '전체 선택' }}
            </span>
          </label>
          <button v-if="selectedIds.size > 0" class="act-btn del-sel" @click="deleteSelected">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px">
              <polyline points="2,3.5 12,3.5"/>
              <path d="M5,3.5 V2 H9 V3.5"/>
              <path d="M3.5,3.5 L4.5,12 H9.5 L10.5,3.5"/>
            </svg>
            {{ selectedIds.size }}개 삭제
          </button>
          <div class="sel-wrap" style="min-width:0">
            <select v-model="pageSize" style="font-size:11px;padding:3px 22px 3px 6px">
              <option :value="3">3개</option>
              <option :value="5">5개</option>
              <option :value="10">10개</option>
              <option :value="20">20개</option>
              <option :value="50">50개</option>
            </select>
            <div class="chevron"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>
          </div>
          <span style="font-size:11px;color:var(--text-tertiary)">총 {{ groupedJobs.length }}개 <span v-if="groupedJobs.length!==allJobs.length" style="opacity:.6">(실행 {{ allJobs.length }})</span></span>
          <button class="act-btn swap-btn" @click="swapLayout = !swapLayout"
                  :title="swapLayout ? '원래대로 (Job 현황이 위)' : '위치 교체 (로그를 위로)'"
                  style="padding:3px 9px;font-size:11px;font-weight:600">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.8" style="width:11px;height:11px;margin-right:3px">
              <polyline points="3,4 6,1 9,4"/><line x1="6" y1="1" x2="6" y2="7"/>
              <polyline points="3,10 6,13 9,10"/><line x1="6" y1="7" x2="6" y2="13"/>
            </svg>
            {{ swapLayout ? '↓ 아래로' : '↑ 위로' }}
          </button>
        </div>
      </div>

      <div v-if="!allJobs.length" class="empty-state">Job이 없습니다</div>
      <template v-else>
        <!-- 헤더 행 -->
        <div class="list-head">
          <span class="lh-chk">
            <input type="checkbox"
              :checked="pagedJobs.length > 0 && pagedJobs.every(j => selectedIds.has(j.id))"
              :indeterminate.prop="selectedIds.size > 0 && !pagedJobs.every(j => selectedIds.has(j.id))"
              @change="togglePageAll"
              style="accent-color:var(--accent-blue);width:13px;height:13px;cursor:pointer"/>
          </span>
          <span></span>
          <span class="lh-col lh-sort" @click="setSort('name')">
            Job 이름 <span class="sort-ico">{{ sortIco('name') }}</span>
          </span>
          <span class="lh-col lh-sort" @click="setSort('src_database')">
            소스 → 타겟 <span class="sort-ico">{{ sortIco('src_database') }}</span>
          </span>
          <span class="lh-col lh-sort" @click="setSort('created_at')">
            수행일시 <span class="sort-ico">{{ sortIco('created_at') }}</span>
          </span>
          <span class="lh-col" style="text-align:right">테이블</span>
          <span class="lh-col lh-sort" style="text-align:right" @click="setSort('rows_processed')">
            처리 rows <span class="sort-ico">{{ sortIco('rows_processed') }}</span>
          </span>
          <span class="lh-col" style="text-align:right">소요시간</span>
          <span class="lh-col lh-sort" style="text-align:right" @click="setSort('progress')">
            진행 <span class="sort-ico">{{ sortIco('progress') }}</span>
          </span>
          <span class="lh-col lh-sort" style="text-align:center" @click="setSort('status')">
            상태 <span class="sort-ico">{{ sortIco('status') }}</span>
          </span>
          <span></span>
        </div>

        <template v-for="j in pagedJobs" :key="j.id">
          <div class="list-row" :class="{'row-selected': selectedIds.has(j.id), 'row-grouped': (j._group_count||1) > 1}"
               @click.self="toggleSelect(j.id)">
          <!-- 체크박스 (대표 자기만 선택 / 자식 선택은 펼침 헤더에서) -->
          <input type="checkbox"
            :checked="selectedIds.has(j.id)"
            @change="toggleSelect(j.id)" @click.stop
            style="accent-color:var(--accent-blue);width:13px;height:13px;flex-shrink:0;cursor:pointer"/>
          <!-- DB 아이콘 -->
          <div class="db-icon" :style="{background:m(j.src_db)?.bg, color:m(j.src_db)?.color}">{{ m(j.src_db)?.label }}</div>
          <!-- Job 이름 + 실행중 테이블 배지 + 그룹 배지 -->
          <span class="lc-name">
            <!-- v9 #63b: 그룹 펼치기 토글 - 눈에 띄게 크게 개선 -->
            <button v-if="(j._group_count||1) > 1" class="group-toggle-btn"
                    :class="{open: expandedGroups.has(j._group_key)}"
                    @click.stop="toggleGroup(j._group_key)"
                    :title="expandedGroups.has(j._group_key) ? '접기' : '이전 실행 이력 펼치기'">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="5,3 11,8 5,13"/>
              </svg>
              <span class="grp-cnt">{{ j._group_count }}</span>
            </button>
            {{ j.name }}
            <span v-if="j.current_table && j.status==='running'" class="tbl-badge">{{ j.current_table }}</span>
          </span>
          <!-- 소스→타겟 -->
          <span class="lc-db">{{ j.src_database||j.src_db }} → {{ j.tgt_database||j.tgt_db }}</span>
          <!-- 수행일시 -->
          <span class="lc-date">{{ fmtDate(j.created_at) }}</span>
          <!-- 테이블 -->
          <span class="lc-num">{{ j.table_done||0 }}/{{ j.table_total||0 }}<span class="lc-unit">개</span></span>
          <!-- rows -->
          <span class="lc-num" style="text-align:right;justify-content:flex-end">{{ fmtRows(j.rows_processed||0) }}<span class="lc-unit">rows</span><span v-if="(j.rows_error||0)>0" class="lc-err"> ✕{{ j.rows_error }}</span></span>
          <!-- 소요시간 -->
          <span class="lc-num">{{ j.started_at ? fmtElapsed(j.started_at, j.finished_at) : '—' }}<span class="lc-unit" v-if="j.started_at">초</span></span>
          <!-- 진행률 -->
          <span class="lc-prog">
            <div v-if="j.status==='running'" class="progress-wrap" style="width:54px;margin-bottom:2px">
              <div class="progress-fill blue" :style="{width:(j.progress||0)+'%'}"></div>
            </div>
            <span class="lc-pct">{{ (j.progress||0).toFixed(0) }}%</span>
          </span>
          <!-- 상태 -->
          <span class="lc-status">
            <span class="pill" :class="pillCls(j.status)">{{ statusLbl(j.status) }}</span>
          </span>
          <!-- 삭제 -->
          <span class="lc-act">
            <button v-if="!['running','paused'].includes(j.status)"
                    class="act-btn icon-only del-btn" @click.stop="doDel(j.id)"
                    :title="(j._group_count||1) > 1 ? '이 실행만 삭제 (자식 제외)' : '삭제'">
              <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px">
                <polyline points="2,3.5 12,3.5"/>
                <path d="M5,3.5 V2 H9 V3.5"/>
                <path d="M3.5,3.5 L4.5,12 H9.5 L10.5,3.5"/>
              </svg>
            </button>
          </span>
          </div>
          <!-- 펼쳐진 자식 행들 (과거 실행 이력) -->
          <template v-if="expandedGroups.has(j._group_key) && j._group_children?.length">
          <!-- v9 #63e: 자식 일괄 선택 헤더 -->
          <div class="list-row list-row-child-header" @click.stop>
            <input type="checkbox"
              :checked="areAllChildrenSelected(j)"
              :indeterminate.prop="areSomeChildrenSelected(j)"
              @change="toggleChildrenSelect(j)" @click.stop
              :title="`이전 실행 ${j._group_children.length}개 전체 선택`"
              style="accent-color:var(--accent-blue);width:13px;height:13px;flex-shrink:0;cursor:pointer"/>
            <span class="child-header-label">
              ↳ 이전 실행 {{ j._group_children.length }}개
              <span v-if="childrenSelectedCount(j) > 0" class="child-sel-count">
                ({{ childrenSelectedCount(j) }}개 선택됨)
              </span>
            </span>
            <button v-if="childrenSelectedCount(j) > 0"
                    class="child-del-sel-btn" @click.stop="deleteSelectedChildren(j)">
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px">
                <polyline points="2,3.5 10,3.5"/>
                <path d="M4,3.5 V2 H8 V3.5"/>
                <path d="M3,3.5 L3.8,10 H8.2 L9,3.5"/>
              </svg>
              선택 {{ childrenSelectedCount(j) }}개 삭제
            </button>
            <button class="child-del-all-btn" @click.stop="deleteGroup(j, true)"
                    :title="`이전 실행 ${j._group_children.length}개 모두 삭제 (지금 보이는 최신 실행 제외)`">
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px">
                <polyline points="2,3.5 10,3.5"/>
                <path d="M4,3.5 V2 H8 V3.5"/>
                <path d="M3,3.5 L3.8,10 H8.2 L9,3.5"/>
              </svg>
              전체 {{ j._group_children.length }}개 삭제
            </button>
          </div>
          <div v-for="child in j._group_children" :key="child.id"
               class="list-row list-row-child"
               :class="{'row-selected': selectedIds.has(child.id)}"
               @click.self="toggleSelect(child.id)">
            <input type="checkbox"
              :checked="selectedIds.has(child.id)"
              @change="toggleSelect(child.id)" @click.stop
              style="accent-color:var(--accent-blue);width:13px;height:13px;flex-shrink:0;cursor:pointer"/>
            <div class="db-icon child-db-icon" :style="{background:m(child.src_db)?.bg, color:m(child.src_db)?.color}">{{ m(child.src_db)?.label }}</div>
            <span class="lc-name lc-name-child">
              <span class="child-indent">↳ 이전 실행 #{{ j._group_children.indexOf(child) + 2 }}</span>
            </span>
            <span class="lc-db">{{ child.src_database||child.src_db }} → {{ child.tgt_database||child.tgt_db }}</span>
            <span class="lc-date">{{ fmtDate(child.created_at) }}</span>
            <span class="lc-num">{{ child.table_done||0 }}/{{ child.table_total||0 }}<span class="lc-unit">개</span></span>
            <span class="lc-num" style="text-align:right;justify-content:flex-end">{{ fmtRows(child.rows_processed||0) }}<span class="lc-unit">rows</span><span v-if="(child.rows_error||0)>0" class="lc-err"> ✕{{ child.rows_error }}</span></span>
            <span class="lc-num">{{ child.started_at ? fmtElapsed(child.started_at, child.finished_at) : '—' }}<span class="lc-unit" v-if="child.started_at">초</span></span>
            <span class="lc-prog">
              <span class="lc-pct">{{ (child.progress||0).toFixed(0) }}%</span>
            </span>
            <span class="lc-status">
              <span class="pill" :class="pillCls(child.status)">{{ statusLbl(child.status) }}</span>
            </span>
            <span class="lc-act">
              <button v-if="!['running','paused'].includes(child.status)"
                      class="act-btn icon-only del-btn" @click.stop="doDel(child.id)" title="삭제">
                <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px">
                  <polyline points="2,3.5 12,3.5"/>
                  <path d="M5,3.5 V2 H9 V3.5"/>
                  <path d="M3.5,3.5 L4.5,12 H9.5 L10.5,3.5"/>
                </svg>
              </button>
            </span>
          </div>
          </template><!-- /펼침 조건 -->
        </template><!-- /v-for pagedJobs -->
        <div v-if="totalPages > 1" class="pagination">
          <button class="pg-btn" :disabled="page===1" @click="page=1">«</button>
          <button class="pg-btn" :disabled="page===1" @click="page--">‹</button>
          <button v-for="p in pageNums" :key="p"
                  class="pg-btn" :class="{active: p===page}" @click="page=p">{{ p }}</button>
          <button class="pg-btn" :disabled="page===totalPages" @click="page++">›</button>
          <button class="pg-btn" :disabled="page===totalPages" @click="page=totalPages">»</button>
          <span class="pg-info">{{ page }} / {{ totalPages }}</span>
        </div>
      </template>
    </div>

    <!-- v9 패치 #22: 두 섹션 사이 교체 구분선 -->
    <div class="swap-divider" style="order:1.5" @click="swapLayout = !swapLayout"
         :title="swapLayout ? '원래대로 (Job 현황이 위)' : '위치 교체 (로그를 위로)'">
      <div class="swap-line"></div>
      <div class="swap-btn-center">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" style="width:14px;height:14px">
          <polyline points="4,5 8,1 12,5"/><line x1="8" y1="1" x2="8" y2="7"/>
          <polyline points="4,11 8,15 12,11"/><line x1="8" y1="9" x2="8" y2="15"/>
        </svg>
        <span>위치 교체</span>
      </div>
      <div class="swap-line"></div>
    </div>

    <!-- 실시간 로그 -->
    <div class="card log-card" :style="{order: swapLayout ? 1 : 2}">
      <div class="card-header">
        <div style="display:flex;align-items:center;gap:8px">
          <span>실시간 로그</span>
          <span v-if="swapLayout" class="ws-badge" style="background:var(--bg-info);color:var(--text-info)" title="위로 이동됨">↑ 상단</span>
          <span v-if="wsConnected" class="ws-badge">
            <span class="ws-live-dot"></span> LIVE
          </span>
          <span v-else class="poll-badge">POLL</span>
        </div>
        <div style="display:flex;gap:6px;align-items:center">
          <div class="log-level-filter">
            <button v-for="lv in ['all','debug','info','warn','error']" :key="lv"
                    class="lv-btn" :class="{active: logLevel===lv, ['lv-'+lv]: true}"
                    @click="logLevel=lv">
              {{ lv==='all' ? '전체' : lv.toUpperCase() }}
            </button>
          </div>
          <div class="sel-wrap" style="min-width:140px">
            <select v-model="logFilter" style="font-size:11.5px;padding:4px 24px 4px 8px">
              <option value="">전체 Job</option>
              <option v-for="j in allJobs" :key="j.id" :value="j.id">{{ j.name.slice(0,22) }}</option>
            </select>
            <div class="chevron"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>
          </div>
          <label class="auto-scroll-toggle">
            <input type="checkbox" v-model="autoScroll" style="accent-color:var(--accent-blue)"/>
            <span style="font-size:11px;color:var(--text-tertiary)">자동 스크롤</span>
          </label>
          <button class="act-btn" @click="clearLogs">지우기</button>
        </div>
      </div>

      <div class="log-box" ref="logBox">
        <template v-if="filteredLogs.length">
          <div v-for="(l, i) in filteredLogs.slice(-300)" :key="i"
               class="log-line" :class="'log-' + l.level">
            <span class="log-t">{{ l.time }}</span>
            <span class="log-tag">{{ l.tag }}</span>
            <span class="log-msg">{{ l.message }}</span>
          </div>
        </template>
        <div v-else class="empty-state" style="padding:16px;font-size:12px">로그가 없습니다</div>
      </div>

      <div class="log-footer">
        <span>총 {{ logs.length }}줄</span>
        <span class="log-stat info">INFO {{ logCounts.info }}</span>
        <span class="log-stat warn">WARN {{ logCounts.warn }}</span>
        <span class="log-stat error">ERR {{ logCounts.error }}</span>
        <span style="margin-left:auto;font-size:10.5px;color:var(--text-tertiary)">
          마지막 갱신: {{ lastRefreshStr }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { fmtDate, fmtElapsed, parseDate } from '@/utils/dateUtils.js'
import { fmtRows } from '@/utils/numberUtils.js'
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useJobStore }       from '@/store/jobStore.js'
import { useAppStore }       from '@/store/appStore.js'
import { useConnectorStore } from '@/store/connectorStore.js'
import { jobsApi , getAuthToken}           from '@/api/index.js'
import { DB_META }           from '@/constants/dbMeta.js'
import PageHeader            from '@/components/layout/PageHeader.vue'

const jobs = useJobStore()
const app  = useAppStore()
const conn = useConnectorStore()

const logs        = ref([])
const logFilter   = ref('')
const logLevel    = ref('all')
const logBox      = ref(null)
const autoScroll  = ref(true)
const autoRefresh = ref(true)
const refreshing  = ref(false)
const lastRefresh = ref(new Date())

// v9 패치 #20: 섹션 위치 교체 (localStorage 저장)
const swapLayout = ref(localStorage.getItem('monitor_swap_layout') === '1')
watch(swapLayout, v => localStorage.setItem('monitor_swap_layout', v ? '1' : '0'))

const wsConnected = ref(false)
const wsMap       = ref({})
let   pollTimer   = null
let   monitorWs   = null

const page        = ref(1)
const pageSize    = ref(10)
const selectedIds = ref(new Set())

const m         = t => DB_META[t] || { label:'??', bg:'#eee', color:'#333' }

const statusLbl = s => ({running:'실행 중',completed:'완료',error:'오류',idle:'대기',paused:'일시정지',aborted:'중단'}[s]||s)
const pillCls   = s => ({running:'pill-run',completed:'pill-ok',error:'pill-err',idle:'pill-ready',paused:'pill-warn',aborted:'pill-warn'}[s]||'pill-idle')

const lastRefreshStr = computed(() => {
  const d = lastRefresh.value
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`
})

const sortCol = ref('created_at')   // 기본: 최신순
const sortDir = ref('desc')

function setSort(col) {
  if (sortCol.value === col) sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'
  else { sortCol.value = col; sortDir.value = 'desc' }
  page.value = 1
}
function sortIco(col) {
  if (sortCol.value !== col) return '↕'
  return sortDir.value === 'desc' ? '↓' : '↑'
}

const allJobs = computed(() => {
  const list = [...jobs.jobs]
  const col = sortCol.value, dir = sortDir.value
  list.sort((a, b) => {
    let va = a[col], vb = b[col]
    if (col === 'created_at') { va = new Date(va||0); vb = new Date(vb||0) }
    else if (typeof va === 'string') { va = va.toLowerCase(); vb = (vb||'').toLowerCase() }
    else { va = va||0; vb = vb||0 }
    return dir === 'desc' ? (va > vb ? -1 : va < vb ? 1 : 0)
                          : (va < vb ? -1 : va > vb ? 1 : 0)
  })
  return list
})

// v9 패치 #62/#64: CDC 그룹화
// #64 이후: CDC Job 은 cfg_id 당 1개만 존재 (매분 업데이트). 그룹화 불필요.
// 다만 기존에 누적된 (suffix 가진) 옛 Job 들은 여전히 남아있을 수 있으니
// 같은 cfg_id prefix 기준으로 그룹화 시도 — 새 스타일 Job (id = cfg_id) 이 있으면 그걸 대표로.
const groupedJobs = computed(() => {
  const groups = new Map()
  for (const j of allJobs.value) {
    let key
    if (j.job_type === 'cdc' && j.id) {
      // 신스타일: id = cfg_id (suffix 없음). 구스타일: cfg_id_suffix
      const m = String(j.id).match(/^(.+)_[0-9a-f]{6}$/i)
      const cfgId = m ? m[1] : j.id
      key = `cdc:${cfgId}`
    } else {
      key = `job:${j.id}`
    }
    if (!groups.has(key)) groups.set(key, { key, children: [] })
    groups.get(key).children.push(j)
  }
  const result = []
  for (const g of groups.values()) {
    // 대표 우선순위: (1) 신스타일(suffix 없음) (2) 실행 중 (3) 최신
    g.children.sort((a, b) => {
      const aNew = a.job_type === 'cdc' && !String(a.id).match(/_[0-9a-f]{6}$/i)
      const bNew = b.job_type === 'cdc' && !String(b.id).match(/_[0-9a-f]{6}$/i)
      if (aNew !== bNew) return aNew ? -1 : 1
      const aRun = a.status === 'running' ? 0 : 1
      const bRun = b.status === 'running' ? 0 : 1
      if (aRun !== bRun) return aRun - bRun
      return new Date(b.started_at||b.last_run_at||b.created_at||0) -
             new Date(a.started_at||a.last_run_at||a.created_at||0)
    })
    const head = { ...g.children[0], _group_key: g.key,
                   _group_count: g.children.length,
                   _group_children: g.children.slice(1) }
    result.push(head)
  }
  // 그룹 간 정렬 — 현재 sortCol 유지
  result.sort((a, b) => {
    let va = a[sortCol.value], vb = b[sortCol.value]
    if (sortCol.value === 'created_at') { va = new Date(va||0); vb = new Date(vb||0) }
    else if (typeof va === 'string') { va = va.toLowerCase(); vb = (vb||'').toLowerCase() }
    else { va = va||0; vb = vb||0 }
    return sortDir.value === 'desc' ? (va > vb ? -1 : va < vb ? 1 : 0)
                                    : (va < vb ? -1 : va > vb ? 1 : 0)
  })
  return result
})

// 그룹 펼치기 상태
const expandedGroups = ref(new Set())
function toggleGroup(key) {
  const s = new Set(expandedGroups.value)
  if (s.has(key)) s.delete(key); else s.add(key)
  expandedGroups.value = s
}
const running        = computed(() => [...jobs.jobs.filter(j => j.status==='running' || j.status==='paused')].sort((a,b)=>new Date(b.started_at||0)-new Date(a.started_at||0)))
const totalSpeed     = computed(() => running.value.reduce((s,j) => s+(j.speed||0), 0))
const cumulativeRows = computed(() => jobs.jobs.reduce((s,j) => s+(j.rows_processed||0), 0))

// v9 패치 #30: Job 별 실시간 처리 행수 (진행 중 테이블 + 완료 테이블 합)
function jobRowsProcessed(j) {
  if (!j) return 0
  const items = j.item_statuses || {}
  let total = 0
  let hasAny = false
  for (const [name, st] of Object.entries(items)) {
    if (!st || st.type !== 'table') continue
    hasAny = true
    if (st.status === 'done' || st.status === 'completed') {
      total += Number(st.rows_tgt || st.rows_src || st.rows || 0)
    } else if (st.status === 'running') {
      total += Number(st.rows_tgt || 0)
    }
  }
  return hasAny ? total : Number(j.rows_processed || 0)
}
function jobRowsTotal(j) {
  if (!j) return 0
  const items = j.item_statuses || {}
  let total = 0
  let totalTables = 0
  let knownTables = 0
  for (const [name, st] of Object.entries(items)) {
    if (!st || st.type !== 'table') continue
    totalTables++
    const rt = Number(st.rows_total || st.rows_src || 0)
    if (rt > 0) { total += rt; knownTables++ }
  }
  // v9 패치 #41: 대기 테이블은 rows_total 이 0 → 엔진 추정값과 max
  const engineEstimate = Number(j.rows_total || 0)
  if (knownTables < totalTables && engineEstimate > total) {
    return engineEstimate
  }
  return total > 0 ? total : engineEstimate
}

// v9 패치 #34: Monitor - 현재 테이블 잔여 시간
function jobCurrentTableEta(j) {
  if (!j || j.status !== 'running') return null
  const done  = Number(j.current_table_rows_done || 0)
  const total = Number(j.current_table_rows_total || 0)
  if (total <= 0 || done >= total) return null

  let rps = 0
  const curName = j.current_table
  if (curName && j.item_statuses && j.item_statuses[curName]) {
    rps = Number(j.item_statuses[curName].speed || 0)
  }
  if (rps < 1) rps = Number(j.speed || 0)
  if (rps < 1) return null

  return _fmtEtaSec(Math.max(1, Math.round((total - done) / rps)))
}

// v10 #4 (2026-04-20): 전체 Job 잔여 시간 — 테이블별 합산 방식
//
// 문제점 (기존 v9 #34):
//   전체 남은 행 / j.speed (평균 누적 속도) — 단순 평균이 대형 테이블에 편향됨.
//   작은 테이블 여럿이 빠르게 끝나면 평균속도가 부풀려지고,
//   마지막에 남은 큰 테이블의 실제 속도는 훨씬 느려서 과소평가 발생.
//   예: 98%일 때 "14분" 표시되었는데 실제 현재 테이블 ETA 는 "43분"
//
// 개선:
//   각 테이블별로 남은행/속도 계산 후 합산.
//   - running 테이블: 해당 테이블 속도 사용
//   - pending 테이블: 현재 러닝 테이블 속도 또는 Job 평균 속도로 추정
//   - done    테이블: 스킵
//   속도 정보가 없으면 Job 평균 속도(j.speed)로 폴백 → 기존 동작 보존
function jobTotalEta(j) {
  if (!j || j.status !== 'running') return null

  const items = j.item_statuses || {}
  const avgRps = Number(j.speed || 0)
  let remainingSec = 0
  let usedPerTable = false

  // 1) 현재 러닝 테이블의 속도 — pending 테이블 추정용
  let runningRps = 0
  for (const st of Object.values(items)) {
    if (!st || st.type !== 'table') continue
    if (st.status === 'running') {
      const r = Number(st.speed || 0)
      if (r > 0 && r > runningRps) runningRps = r
    }
  }
  const pendingRps = runningRps > 0 ? runningRps : avgRps  // 앞으로 할 테이블에 적용

  // 2) 각 테이블 별 잔여시간 합산
  for (const st of Object.values(items)) {
    if (!st || st.type !== 'table') continue
    if (st.status === 'done' || st.status === 'completed') continue

    const tTotal = Number(st.rows_total || st.rows_src || 0)
    if (tTotal <= 0) continue      // 총 행수 모르는 테이블은 스킵

    const tDone  = Number(st.rows_tgt || 0)
    const tLeft  = Math.max(0, tTotal - tDone)
    if (tLeft === 0) continue

    let rps
    if (st.status === 'running') {
      rps = Number(st.speed || 0) || avgRps    // 현재 테이블 — 자기 속도 우선
    } else {
      rps = pendingRps                          // 대기 테이블 — 러닝 속도로 추정
    }
    if (rps < 1) continue                       // 속도 불명이면 기여분 0

    remainingSec += tLeft / rps
    usedPerTable = true
  }

  // 3) 테이블별 합산이 성립 안 됐으면 기존 방식으로 폴백 (하위호환)
  if (!usedPerTable) {
    const processed = jobRowsProcessed(j)
    const total     = jobRowsTotal(j)
    if (total <= 0 || processed >= total) return null
    if (avgRps < 1) return null
    remainingSec = (total - processed) / avgRps
  }

  if (remainingSec < 1) return null
  return _fmtEtaSec(Math.max(1, Math.round(remainingSec)))
}

function _fmtEtaSec(sec) {
  if (!sec || sec < 0) return '—'
  if (sec < 60) return sec + '초'
  const m = Math.floor(sec / 60)
  const s = sec % 60
  if (m < 60) return s > 0 ? `${m}분 ${s}초` : `${m}분`
  const h = Math.floor(m / 60)
  const mm = m % 60
  return mm > 0 ? `${h}시간 ${String(mm).padStart(2,'0')}분` : `${h}시간`
}
const totalErrors    = computed(() => jobs.jobs.reduce((s,j) => s+(j.rows_error||0), 0))

const totalPages = computed(() => Math.max(1, Math.ceil(groupedJobs.value.length / pageSize.value)))
const pagedJobs  = computed(() => {
  const s = (page.value - 1) * pageSize.value
  return groupedJobs.value.slice(s, s + pageSize.value)
})
const pageNums = computed(() => {
  const t = totalPages.value, c = page.value, d = 2, r = []
  for (let i = Math.max(1,c-d); i <= Math.min(t,c+d); i++) r.push(i)
  return r
})

const filteredLogs = computed(() => {
  let list = logFilter.value ? logs.value.filter(l => l.job_id === logFilter.value) : logs.value
  if (logLevel.value !== 'all') list = list.filter(l => l.level === logLevel.value)
  return [...list].reverse()   // 최신 위로
})

const logCounts = computed(() => ({
  debug: logs.value.filter(l => l.level==='debug').length,
  info:  logs.value.filter(l => l.level==='info').length,
  warn:  logs.value.filter(l => l.level==='warn').length,
  error: logs.value.filter(l => l.level==='error').length,
}))

watch(page, () => { selectedIds.value = new Set() })
watch(pageSize, () => { page.value = 1; selectedIds.value = new Set() })
watch(() => allJobs.value.length, () => {
  if (page.value > totalPages.value) page.value = Math.max(1, totalPages.value)
})

// 로그 추가 (중복 방지)
const _logKeys = new Set()
function addLog(level, tag, msg, job_id='') {
  // SQL/PARAM 로그는 중복 허용 (테이블마다 다른 실행)
  const isSqlLog = tag.startsWith('CDC/') || msg.startsWith('[SQL]') || msg.startsWith('[PARAM]')
  const ts = isSqlLog ? Date.now() : ''
  const key = `${tag}|${msg}|${job_id}|${ts}`
  if (!isSqlLog && _logKeys.has(key)) return
  _logKeys.add(key)
  if (_logKeys.size > 600) {
    const it = _logKeys.values()
    for (let i = 0; i < 100; i++) _logKeys.delete(it.next().value)
  }
  const now = new Date()
  const t = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`
  logs.value.push({ time:t, level, tag:`[${tag}]`, message:msg, job_id })
  if (logs.value.length > 500) logs.value.splice(0, 50)
  // 최신 로그가 상단에 표시되므로 스크롤은 맨 위로
  if (autoScroll.value) nextTick(() => { if (logBox.value) logBox.value.scrollTop = 0 })
}

// ── WebSocket 연결 ────────────────────────────────────
function connectMonitorWs() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  try {
    monitorWs = new WebSocket(`${proto}://${location.host}/ws/monitor?token=${encodeURIComponent(getAuthToken()||'')}`)
    monitorWs.onopen = () => {
      wsConnected.value = true
      addLog('info', 'WebSocket', '모니터 WebSocket 연결됨')
    }
    monitorWs.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (Array.isArray(data.jobs)) jobs.jobs = data.jobs
        if (data.log) addLog(data.log.level||'info', data.log.tag||'Server', data.log.message, data.log.job_id||'')
        lastRefresh.value = new Date()
      } catch { /* ignore */ }
    }
    monitorWs.onclose = () => { wsConnected.value = false; setTimeout(connectMonitorWs, 3000) }
    monitorWs.onerror = () => { wsConnected.value = false; monitorWs?.close() }
  } catch { wsConnected.value = false }
}

function connectJobWs(jobId) {
  if (wsMap.value[jobId]) return
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  try {
    const ws = new WebSocket(`${proto}://${location.host}/ws/jobs/${jobId}?token=${encodeURIComponent(getAuthToken()||'')}`)
    ws.onopen = () => addLog('info', `Job#${jobId.slice(0,6)}`, 'WebSocket 연결됨', jobId)
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        const idx = jobs.jobs.findIndex(j => j.id === jobId)
        if (idx >= 0 && data.status) Object.assign(jobs.jobs[idx], data)
        if (Array.isArray(data.new_logs)) {
          data.new_logs.forEach(l => addLog(l.level||'info', l.tag||`Job#${jobId.slice(0,6)}`, l.message, jobId))
        }
        if (['completed','error','aborted'].includes(data.status)) {
          ws.close(); delete wsMap.value[jobId]
        }
        lastRefresh.value = new Date()
      } catch { /* ignore */ }
    }
    ws.onclose = () => { delete wsMap.value[jobId] }
    wsMap.value[jobId] = ws
  } catch { /* WS 불가 → 폴링 폴백 */ }
}

function disconnectJobWs(jobId) {
  if (wsMap.value[jobId]) {
    wsMap.value[jobId].onclose = null
    wsMap.value[jobId].close()
    delete wsMap.value[jobId]
  }
}

// ── 폴링 폴백 ────────────────────────────────────────
const prevStates = ref({})

async function pollRefresh() {
  if (wsConnected.value) return
  await jobs.fetch()
  lastRefresh.value = new Date()

  jobs.jobs.forEach(j => {
    const prev = prevStates.value[j.id]
    if (!prev) {
      if (j.status === 'running') addLog('info', `Job#${j.id.slice(0,6)}`, `새 Job: ${j.name}`, j.id)
    } else {
      if (prev.status !== j.status) {
        const lvl = j.status==='error' ? 'error' : j.status==='completed' ? 'info' : 'warn'
        addLog(lvl, `Job#${j.id.slice(0,6)}`, `[${j.name.slice(0,20)}] ${statusLbl(prev.status)} → ${statusLbl(j.status)}`, j.id)
      }
      if (j.status==='running' && prev.table !== j.current_table && j.current_table && j.current_table!=='준비 중...') {
        addLog('info', `Job#${j.id.slice(0,6)}`, `테이블: ${j.current_table} (${(j.rows_processed||0).toLocaleString()} rows)`, j.id)
      }
    }
    prevStates.value[j.id] = { status: j.status, table: j.current_table }
  })

  for (const j of running.value.slice(0, 3)) {
    try {
      const bl = await jobsApi.logs(j.id)
      bl.slice(-5).forEach(l => addLog(l.level||'info', l.tag||`Job#${j.id.slice(0,6)}`, l.message, j.id))
    } catch { /* 무시 */ }
  }
}

// running 변화 → Job별 WS 관리
watch(running, (newR, oldR) => {
  newR.forEach(j => {
    if (!oldR.find(o => o.id === j.id)) {
      connectJobWs(j.id)
      logFilter.value = j.id
      addLog('info', 'Monitor', `새 Job 시작: ${j.name}`, j.id)
    }
  })
  oldR.forEach(j => {
    if (!newR.find(o => o.id === j.id)) disconnectJobWs(j.id)
  })
}, { deep: false })

async function manualRefresh() {
  refreshing.value = true
  await jobs.fetch()
  lastRefresh.value = new Date()
  setTimeout(() => { refreshing.value = false }, 500)
}

function focusJob(jobId) {
  logFilter.value = jobId
  nextTick(() => { if (logBox.value) logBox.value.scrollTop = 0 })
}

function clearLogs() {
  logs.value = []
  _logKeys.clear()
  app.notify('로그 초기화됨', 'info')
}

function toggleSelect(id) {
  const s = new Set(selectedIds.value)
  s.has(id) ? s.delete(id) : s.add(id)
  selectedIds.value = s
}

// v9 #63c: 그룹 전체 선택/해제 — 대표 + 모든 자식을 한 번에
function toggleGroupSelect(headJob) {
  const allIds = [headJob.id, ...(headJob._group_children || []).map(c => c.id)]
      .filter(id => {
        const job = jobs.jobs.find(j => j.id === id)
        return job && !['running','paused'].includes(job.status)
      })
  const s = new Set(selectedIds.value)
  // 전부 선택돼있으면 → 전부 해제, 아니면 → 전부 선택
  const allSelected = allIds.length > 0 && allIds.every(id => s.has(id))
  if (allSelected) {
    allIds.forEach(id => s.delete(id))
  } else {
    allIds.forEach(id => s.add(id))
  }
  selectedIds.value = s
}

// v9 #63c: 그룹이 전부 선택된 상태인지 (체크박스 체크 상태용)
function isGroupAllSelected(headJob) {
  const allIds = [headJob.id, ...(headJob._group_children || []).map(c => c.id)]
      .filter(id => {
        const job = jobs.jobs.find(j => j.id === id)
        return job && !['running','paused'].includes(job.status)
      })
  return allIds.length > 0 && allIds.every(id => selectedIds.value.has(id))
}

// v9 #63c: 그룹이 일부만 선택됐는지 (indeterminate 표시용)
function isGroupPartialSelected(headJob) {
  const allIds = [headJob.id, ...(headJob._group_children || []).map(c => c.id)]
  const some = allIds.some(id => selectedIds.value.has(id))
  const all  = allIds.every(id => selectedIds.value.has(id))
  return some && !all
}

// v9 #63e: 자식만 대상 — 전부 선택됐는지
function areAllChildrenSelected(headJob) {
  const ids = (headJob._group_children || [])
    .filter(c => !['running','paused'].includes(c.status))
    .map(c => c.id)
  return ids.length > 0 && ids.every(id => selectedIds.value.has(id))
}
function areSomeChildrenSelected(headJob) {
  const ids = (headJob._group_children || []).map(c => c.id)
  const some = ids.some(id => selectedIds.value.has(id))
  const all  = ids.every(id => selectedIds.value.has(id))
  return some && !all
}
function childrenSelectedCount(headJob) {
  const ids = (headJob._group_children || []).map(c => c.id)
  return ids.filter(id => selectedIds.value.has(id)).length
}
function toggleChildrenSelect(headJob) {
  const ids = (headJob._group_children || [])
    .filter(c => !['running','paused'].includes(c.status))
    .map(c => c.id)
  const s = new Set(selectedIds.value)
  const allSelected = ids.length > 0 && ids.every(id => s.has(id))
  if (allSelected) ids.forEach(id => s.delete(id))
  else             ids.forEach(id => s.add(id))
  selectedIds.value = s
}
async function deleteSelectedChildren(headJob) {
  const ids = (headJob._group_children || [])
    .map(c => c.id)
    .filter(id => {
      if (!selectedIds.value.has(id)) return false
      const job = jobs.jobs.find(j => j.id === id)
      return job && !['running','paused'].includes(job.status)
    })
  if (!ids.length) return
  if (!confirm(`선택한 이전 실행 ${ids.length}개를 삭제하시겠습니까?`)) return
  for (const id of ids) { try { await jobs.del(id) } catch {} }
  const s = new Set(selectedIds.value)
  ids.forEach(id => s.delete(id))
  selectedIds.value = s
  app.notify(`${ids.length}개 삭제됨`, 'success')
}

// v9 #63c: 그룹 일괄 삭제 — 대표 + 모든 자식을 한 번에
// v9 #63e: excludeHead=true 면 대표(지금 보이는 최신 실행) 제외하고 자식만 삭제
async function deleteGroup(headJob, excludeHead = false) {
  const childIds = (headJob._group_children || []).map(c => c.id)
  const allIds = excludeHead ? childIds : [headJob.id, ...childIds]
  // 실행 중 상태 제외
  const targetIds = allIds.filter(id => {
    const job = jobs.jobs.find(j => j.id === id)
    return job && !['running','paused'].includes(job.status)
  })
  if (!targetIds.length) {
    app.notify('삭제 가능한 실행이 없습니다 (실행 중 제외)', 'warn')
    return
  }
  const scope = excludeHead ? '이전 실행 이력' : '그룹 전체'
  if (!confirm(`"${headJob.name}" ${scope} ${targetIds.length}개를 삭제하시겠습니까?`)) return
  for (const id of targetIds) { try { await jobs.del(id) } catch { /* 무시 */ } }
  // 선택 상태에서도 제거
  const s = new Set(selectedIds.value)
  targetIds.forEach(id => s.delete(id))
  selectedIds.value = s
  app.notify(`${targetIds.length}개 삭제됨`, 'success')
}
function togglePageAll(e) {
  const s = new Set(selectedIds.value)
  const del = pagedJobs.value.filter(j => !['running','paused'].includes(j.status))
  if (e.target.checked) del.forEach(j => s.add(j.id))
  else del.forEach(j => s.delete(j.id))
  selectedIds.value = s
}
async function deleteSelected() {
  const ids = [...selectedIds.value]
  if (!ids.length) return
  if (!confirm(`선택한 ${ids.length}개 Job을 삭제하시겠습니까?`)) return
  for (const id of ids) { try { await jobs.del(id) } catch { /* 무시 */ } }
  selectedIds.value = new Set()
  app.notify(`${ids.length}개 삭제됨`, 'success')
}

async function doPause(id)  { await jobs.pause(id);  addLog('warn','Monitor','일시정지',id); app.notify('일시정지됨','warn') }
async function doResume(id) { await jobs.resume(id); addLog('info','Monitor','재개',id);      app.notify('재개됨','success') }
async function doStop(id)   {
  if (!confirm('이관을 중단하시겠습니까?')) return
  await jobs.stop(id); addLog('warn','Monitor','중단',id); app.notify('중단됨','warn')
}
async function doDel(id) {
  if (!confirm('이 Job을 삭제하시겠습니까?')) return
  await jobs.del(id); app.notify('삭제됨')
}

onMounted(async () => {
  await jobs.fetch()
  jobs.jobs.forEach(j => { prevStates.value[j.id] = { status: j.status, table: j.current_table } })
  addLog('info', 'Monitor', `모니터링 시작 — Job ${jobs.jobs.length}개 로드됨`)
  if (running.value.length > 0) {
    logFilter.value = running.value[0].id
    running.value.forEach(j => connectJobWs(j.id))
  }
  connectMonitorWs()
  // v95_p107 hotfix_002: 2000 → 5000. Docker stats 호출 부하 ↓ (5초 충분히 빠름)
  pollTimer = setInterval(async () => { if (autoRefresh.value) await pollRefresh() }, 5000)
})

onUnmounted(() => {
  clearInterval(pollTimer)
  if (monitorWs) { monitorWs.onclose = null; monitorWs.close() }
  Object.values(wsMap.value).forEach(ws => { ws.onclose = null; ws.close() })
})
</script>

<style scoped>
.monitor-page { display:flex; flex-direction:column; gap:0; }

/* v9 패치 #22: 섹션 교체 UI */
.swap-btn { border:0.5px solid var(--accent-blue) !important; color:var(--accent-blue) !important; background:var(--bg-info) !important; }
.swap-btn:hover { background:var(--accent-blue) !important; color:#fff !important; }
.swap-divider { display:flex; align-items:center; gap:10px; margin:4px 0 8px; cursor:pointer; user-select:none; }
.swap-line { flex:1; height:0.5px; background:var(--border-mid); transition:background .15s; }
.swap-btn-center { display:flex; align-items:center; gap:5px; padding:4px 12px; border:0.5px dashed var(--border-mid); border-radius:14px; font-size:11px; color:var(--text-tertiary); transition:all .15s; background:var(--bg-primary); }
.swap-divider:hover .swap-btn-center { border-color:var(--accent-blue); color:var(--accent-blue); background:var(--bg-info); }
.swap-divider:hover .swap-line { background:var(--accent-blue); }
.mon-header { display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:14px; }
.header-actions { display:flex; align-items:center; gap:8px; }

.ws-status { display:flex; align-items:center; gap:5px; font-size:11px; padding:4px 10px; border-radius:20px; border:0.5px solid var(--border-mid); }
.ws-status.ws-ok  { background:var(--bg-success); color:var(--text-success); border-color:var(--accent-green); }
.ws-status.ws-off { background:var(--bg-secondary); color:var(--text-tertiary); }
.ws-dot { width:6px; height:6px; border-radius:50%; background:currentColor; }
.ws-ok .ws-dot { animation:ws-pulse 1.5s infinite; }
@keyframes ws-pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

.mon-row { display:flex; align-items:flex-start; gap:14px; padding:14px 16px; border-bottom:0.5px solid var(--border-light); }
.mon-row:last-child { border-bottom:none; }
.mon-info { min-width:180px; flex-shrink:0; }
.mon-prog { flex:1; min-width:0; }
.mon-acts { display:flex; flex-direction:column; gap:5px; flex-shrink:0; }

.cur-tbl-row { display:flex; align-items:center; gap:6px; padding:4px 8px; background:var(--bg-info); border-radius:var(--radius-sm); margin-bottom:6px; font-size:11.5px; }
.cur-tbl-label { color:var(--text-tertiary); flex-shrink:0; }
.cur-tbl-name { font-family:'Consolas','SF Mono',monospace; font-weight:600; color:var(--text-info); flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.cur-tbl-cnt { color:var(--text-tertiary); flex-shrink:0; font-size:10.5px; }

.prog-meta { display:flex; gap:12px; font-size:11px; color:var(--text-tertiary); margin-bottom:5px; align-items:center; }
.prog-eta { color:var(--accent-blue); font-weight:600; }
.cur-tbl-eta { color:var(--accent-blue); font-weight:600; font-size:11px; padding:1px 7px; background:rgba(59,130,246,0.08); border-radius:9px; margin-left:auto; }
.prog-pct { font-size:14px; font-weight:600; color:var(--text-info); }
.rows-meta { font-size:10.5px; color:var(--text-tertiary); margin-top:4px; }
.rows-meta b { color:var(--text-primary); }

.log-card { padding:0; overflow:hidden; }
.log-level-filter { display:flex; border:0.5px solid var(--border-mid); border-radius:var(--radius-sm); overflow:hidden; }
.lv-btn { padding:3px 8px; font-size:10.5px; border:none; background:var(--bg-secondary); color:var(--text-tertiary); cursor:pointer; font-family:var(--font); transition:all .1s; border-right:0.5px solid var(--border-light); }
.lv-btn:last-child { border-right:none; }
.lv-btn:hover { background:var(--bg-primary); color:var(--text-primary); }
.lv-btn.active { font-weight:600; }
.lv-btn.lv-all.active   { background:var(--bg-tertiary); color:var(--text-primary); }
.lv-btn.lv-info.active  { background:var(--bg-info); color:var(--text-info); }
.lv-btn.lv-warn.active  { background:var(--bg-warning); color:var(--text-warning); }
.lv-btn.lv-error.active { background:var(--bg-danger); color:var(--text-danger); }

.ws-badge { display:inline-flex; align-items:center; gap:4px; font-size:10px; font-weight:700; padding:2px 7px; border-radius:8px; background:var(--bg-success); color:var(--text-success); letter-spacing:.5px; }
.ws-live-dot { width:5px; height:5px; border-radius:50%; background:var(--text-success); animation:ws-pulse 1s infinite; }
.poll-badge { font-size:10px; font-weight:600; padding:2px 7px; border-radius:8px; background:var(--bg-secondary); color:var(--text-tertiary); }
.auto-scroll-toggle { display:flex; align-items:center; gap:4px; cursor:pointer; }

.log-box { background:var(--bg-secondary); padding:10px 12px; max-height:340px; overflow-y:auto; font-family:'Consolas','SF Mono',monospace; }
.log-line { display:flex; gap:8px; font-size:11.5px; padding:2px 0; line-height:1.6; color:var(--text-secondary); }
.log-t   { color:var(--text-tertiary); flex-shrink:0; }
.log-tag { color:var(--text-info); flex-shrink:0; min-width:100px; }
.log-msg { flex:1; word-break:break-all; }
.log-warn  .log-tag,.log-warn  .log-msg { color:var(--text-warning); }
.log-error .log-tag,.log-error .log-msg { color:var(--text-danger); }

.log-footer { display:flex; align-items:center; gap:10px; padding:7px 14px; border-top:0.5px solid var(--border-light); font-size:11px; color:var(--text-tertiary); }
.log-stat { font-weight:600; }
.log-stat.info  { color:var(--text-info); }
.log-stat.warn  { color:var(--text-warning); }
.log-stat.error { color:var(--text-danger); }

.refresh-dot { width:7px; height:7px; border-radius:50%; background:var(--border-mid); }
.refresh-dot.active { background:#639922; animation:blink 2s infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }

.toggle { position:relative; width:34px; height:18px; background:var(--border-mid); border-radius:9px; cursor:pointer; transition:background .2s; flex-shrink:0; }
.toggle.sm { width:28px; height:16px; }
.toggle.on { background:var(--accent-blue); }
.toggle::after { content:''; position:absolute; top:2px; left:2px; width:14px; height:14px; border-radius:50%; background:white; transition:transform .2s; }
.toggle.sm::after { width:12px; height:12px; }
.toggle.on::after { transform:translateX(16px); }
.toggle.sm.on::after { transform:translateX(12px); }

/* ── 전체 Job 현황 grid 레이아웃 ── */
/* 체크 | 아이콘 | tblbadge | 이름(넓게) | DB경로 | 수행일시 | 테이블 | rows | 소요 | 진행 | 상태 | 삭제 */
.list-head {
  display:grid;
  grid-template-columns:20px 32px 2fr 1.1fr 120px 56px 72px 72px 74px 60px 30px;
  gap:0 8px; padding:5px 14px;
  background:var(--bg-primary);
  border-bottom:0.5px solid var(--border-light);
}
.lh-col { font-size:.66rem; font-weight:700; color:var(--text-tertiary); text-transform:uppercase; letter-spacing:.05em; white-space:nowrap; }
.list-row {
  display:grid;
  grid-template-columns:20px 32px 2fr 1.1fr 120px 56px 72px 72px 74px 60px 30px;
  gap:0 8px; padding:8px 14px;
  align-items:center; border-bottom:0.5px solid var(--border-light);
  cursor:pointer; transition:background .1s;
}
.list-row:last-child { border-bottom:none; }
.list-row:hover { background:var(--bg-secondary); }
.lc-name  { font-size:12px; font-weight:600; color:var(--text-primary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; display:flex; align-items:center; gap:5px; }
.lc-db    { font-size:11px; color:var(--text-secondary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.lc-date  { font-size:10.5px; color:var(--text-tertiary); white-space:nowrap; font-variant-numeric:tabular-nums; }
.lc-num   { font-size:11px; color:var(--text-secondary); text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }
.lc-err   { color:var(--text-danger); font-weight:600; font-size:10px; }
.lc-prog  { display:flex; flex-direction:column; align-items:flex-end; gap:1px; }
.lc-pct   { font-size:10.5px; color:var(--text-tertiary); font-variant-numeric:tabular-nums; }
.lc-status{ display:flex; justify-content:center; }
.lc-act   { display:flex; justify-content:center; }
.sum-date { display:inline-flex; align-items:center; gap:3px; font-size:10.5px; color:var(--text-tertiary); }
.sum-sep  { font-size:10px; color:var(--border-strong); }
.sum-item { font-size:10.5px; color:var(--text-tertiary); }
.sum-err  { font-size:10.5px; color:var(--text-danger); font-weight:600; }
.tbl-badge { font-size:10px; background:var(--bg-info); color:var(--text-info); padding:1px 6px; border-radius:4px; margin-left:6px; font-family:'Consolas','SF Mono',monospace; }

/* v9 #64: CDC Job 회차 배지 */
.cdc-run-badge {
  font-size: 10px;
  background: rgba(37, 99, 235, 0.10);
  color: #2563eb;
  padding: 1px 6px;
  border-radius: 8px;
  margin-left: 4px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  border: 0.5px solid rgba(37, 99, 235, 0.25);
}

/* v9 패치 #62/#63b: CDC 반복 실행 그룹화 — 눈에 띄는 버튼 */
.row-grouped {
  background: rgba(37, 99, 235, 0.04);
  border-left: 2px solid rgba(37, 99, 235, 0.5);
}
.row-grouped:hover {
  background: rgba(37, 99, 235, 0.08);
}

/* 새 펼치기 버튼 — 작은 알약 형태 + 화살표 + 숫자를 한 컴포넌트로 */
.group-toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #fff;
  border: none;
  border-radius: 10px;
  padding: 3px 8px 3px 6px;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  flex-shrink: 0;
  margin-right: 6px;
  box-shadow: 0 1px 2px rgba(37, 99, 235, 0.3),
              0 0 0 1px rgba(37, 99, 235, 0.15);
  transition: all .18s ease;
  font-variant-numeric: tabular-nums;
  min-width: 38px;
  justify-content: center;
}
.group-toggle-btn:hover {
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.45),
              0 0 0 1px rgba(37, 99, 235, 0.25);
}
.group-toggle-btn:active {
  transform: translateY(0);
}
.group-toggle-btn svg {
  width: 10px;
  height: 10px;
  flex-shrink: 0;
  transition: transform .22s ease;
}
.group-toggle-btn.open svg {
  transform: rotate(90deg);
}
.group-toggle-btn .grp-cnt {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .01em;
}
.group-toggle-btn.open {
  background: linear-gradient(135deg, #2563eb, #1e40af);
}

/* 자식 행 (펼쳐진 이전 실행) */
.list-row-child {
  background: var(--bg-secondary) !important;
  border-bottom-color: transparent;
  opacity: 0.82;
  border-left: 2px solid rgba(37, 99, 235, 0.25);
}
.list-row-child:hover {
  background: var(--bg-tertiary, var(--bg-secondary)) !important;
  opacity: 1;
}
.list-row-child .lc-name {
  font-weight: 400;
  color: var(--text-secondary);
}
.child-indent {
  font-size: 11.5px;
  color: #2563eb;
  padding-left: 42px;  /* 헤더의 펼치기 버튼 너비만큼 들여쓰기 */
  font-style: italic;
  opacity: 0.85;
}
.child-db-icon {
  opacity: 0.6;
}

/* v9 #63c: 그룹 전체 삭제 버튼 */
.group-del-btn {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  background: rgba(239, 68, 68, 0.08);
  color: var(--text-danger, #dc2626);
  border: 0.5px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  padding: 3px 7px 3px 6px;
  font-size: 10.5px;
  font-weight: 700;
  cursor: pointer;
  transition: all .15s;
  font-variant-numeric: tabular-nums;
}
.group-del-btn:hover {
  background: rgba(239, 68, 68, 0.18);
  border-color: rgba(239, 68, 68, 0.5);
  transform: translateY(-1px);
}
.group-del-btn svg {
  flex-shrink: 0;
}
.grp-del-count {
  font-size: 10.5px;
  font-weight: 700;
}

/* v9 #63e: 자식 일괄 선택 헤더 */
.list-row-child-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 14px;
  background: linear-gradient(90deg, rgba(37, 99, 235, 0.08), rgba(37, 99, 235, 0.03));
  border-left: 2px solid rgba(37, 99, 235, 0.5);
  border-bottom: 0.5px solid var(--border-light);
  font-size: 11.5px;
}
.child-header-label {
  color: #2563eb;
  font-weight: 600;
  font-size: 11.5px;
  flex: 1;
}
.child-sel-count {
  color: var(--text-secondary);
  font-weight: 500;
  font-size: 11px;
  margin-left: 6px;
}
.child-del-sel-btn,
.child-del-all-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 0.5px solid rgba(239, 68, 68, 0.35);
  background: rgba(239, 68, 68, 0.08);
  color: var(--text-danger, #dc2626);
  padding: 3px 9px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all .15s;
}
.child-del-sel-btn:hover,
.child-del-all-btn:hover {
  background: rgba(239, 68, 68, 0.18);
  border-color: rgba(239, 68, 68, 0.55);
}
.child-del-sel-btn {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.5);
}
.chk-all { display:flex; align-items:center; gap:5px; cursor:pointer; }
.row-selected { background:var(--bg-info) !important; }
.del-sel { background:rgba(239,68,68,.08); color:var(--text-danger); border-color:rgba(239,68,68,.3); font-size:11.5px; display:inline-flex; align-items:center; gap:4px; padding:4px 8px; border-radius:var(--radius-sm); cursor:pointer; border:0.5px solid rgba(239,68,68,.3); }
.del-sel:hover { background:rgba(239,68,68,.15); }
.del-btn:hover { color:var(--text-danger); border-color:rgba(239,68,68,.3); }

.pagination { display:flex; align-items:center; gap:4px; padding:10px 16px; border-top:0.5px solid var(--border-light); justify-content:center; }
.pg-btn { min-width:28px; height:26px; padding:0 6px; border-radius:var(--radius-sm); border:0.5px solid var(--border-mid); background:transparent; color:var(--text-secondary); font-size:12px; cursor:pointer; font-family:var(--font); transition:all .1s; }
.pg-btn:hover:not(:disabled) { background:var(--bg-info); color:var(--text-info); border-color:var(--accent-blue); }
.pg-btn.active { background:var(--accent-blue); color:#fff; border-color:var(--accent-blue); font-weight:600; }
.pg-btn:disabled { opacity:.35; cursor:not-allowed; }
.pg-info { font-size:11px; color:var(--text-tertiary); margin-left:6px; }

@keyframes spin { to { transform:rotate(360deg); } }
.spinning { animation:spin .7s linear infinite; }
.cdc-badge{font-size:.6rem;font-weight:700;padding:1px 5px;border-radius:3px;background:rgba(139,92,246,.12);color:#6d28d9;margin-right:4px}

.lh-chk{display:flex;align-items:center;justify-content:center;padding:0 4px}
.kpi-unit{font-size:.55rem;font-weight:400;color:var(--text-tertiary);margin-left:2px;vertical-align:middle;line-height:1}
.lc-unit{font-size:.68rem;color:var(--text-tertiary);margin-left:1px}
.lh-sort{cursor:pointer;user-select:none;white-space:nowrap}
.lh-sort:hover{color:var(--text-primary);background:var(--bg-secondary)}
.sort-ico{font-size:.7rem;opacity:.5;margin-left:2px}
.lh-sort:hover .sort-ico{opacity:1}
</style>
