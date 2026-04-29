<template>
  <div class="jm">

    <!-- ── 헤더 ── -->
    <div class="jm-header">
      <div class="jm-title-wrap">
        <div class="page-title">이관 작업 모니터</div>
        <div class="page-desc">테이블 · 오브젝트 별 실시간 진행 상황</div>
      </div>
      <div class="jm-controls">
        <div class="job-select-wrap">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" class="select-ico">
            <rect x="1" y="1" width="12" height="12" rx="2"/>
            <line x1="4" y1="5" x2="10" y2="5"/><line x1="4" y1="7" x2="8" y2="7"/>
          </svg>
          <select v-model="selectedJobId" class="job-select" @change="onJobChange">
            <option value="">— 작업 선택 —</option>
            <option v-for="j in jobs" :key="j.id" :value="j.id">
              {{ j.name }} ({{ statusLabel(j.status) }})
            </option>
          </select>
        </div>
        <button class="ctrl-btn" :class="{spinning: polling}" @click="refresh" title="새로고침">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M12 3A5.5 5.5 0 1 1 7 1.5"/><polyline points="8,1 12,1 12,4"/>
          </svg>
        </button>
        <button class="ctrl-btn clear-btn" @click="clearScreen" title="화면 초기화">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M2 2l10 10M12 2L2 12"/>
          </svg>
          <span style="font-size:.72rem;font-weight:600;margin-left:3px">Clear</span>
        </button>
        <label class="auto-label">
          <input type="checkbox" v-model="autoRefresh" @change="toggleAuto"/>
          <span class="auto-track"><span class="auto-thumb"></span></span>
          <span class="auto-txt">{{ autoRefresh ? "자동 ●" : "자동" }}</span>
        </label>
      </div>
    </div>

    <!-- ── 빈 상태 ── -->
    <div v-if="!job" class="empty-state">
      <div class="empty-icon">
        <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.2">
          <rect x="6" y="10" width="36" height="28" rx="3"/>
          <line x1="6" y1="17" x2="42" y2="17"/>
          <line x1="15" y1="24" x2="33" y2="24" stroke-width="1.5"/>
          <line x1="15" y1="29" x2="27" y2="29"/>
        </svg>
      </div>
      <div class="empty-title">모니터링할 작업을 선택하세요</div>
      <div class="empty-desc">위 드롭다운에서 이관 Job을 선택하면<br>실시간 진행 현황을 확인할 수 있습니다</div>
    </div>

    <template v-else>

      <!-- ── KPI 카드 ── -->
      <div class="kpi-grid">
        <div class="kpi-card" :class="'kpi-'+job.status">
          <div class="kpi-header">
            <span class="kpi-label">상태</span>
            <span class="kpi-dot" :class="job.status"></span>
          </div>
          <div class="kpi-sub" style="font-size:.72rem;color:var(--text-tertiary);margin-bottom:6px">
            {{ job.src_db?.toUpperCase() }} → {{ job.tgt_db?.toUpperCase() }}
          </div>
          <!-- 단계별 색깔 버튼 (진행중/완료) -->
          <div v-if="job.status==='running'||job.status==='completed'" class="phase-steps">
            <!-- 1. FK/트리거 비활성화 -->
            <div class="phase-step"
                 :class="phaseStepClass('FK_DISABLE')">
              <span class="ps-icon">{{ phaseStepIcon('FK_DISABLE') }}</span>
              <span class="ps-label">FK·트리거 비활성화</span>
            </div>
            <!-- 2. 데이터 이관 -->
            <div class="phase-step"
                 :class="phaseStepClass('RUNNING')">
              <span class="ps-icon">{{ phaseStepIcon('RUNNING') }}</span>
              <span class="ps-label">데이터 이관</span>
            </div>
            <!-- 3. 오브젝트 이관 -->
            <div class="phase-step"
                 :class="phaseStepClass('OBJECTS')">
              <span class="ps-icon">{{ phaseStepIcon('OBJECTS') }}</span>
              <span class="ps-label">SP·FN·VW·TR 이관</span>
            </div>
            <!-- 4. FK/트리거 복원 -->
            <div class="phase-step"
                 :class="phaseStepClass('FK_RESTORE')">
              <span class="ps-icon">{{ phaseStepIcon('FK_RESTORE') }}</span>
              <span class="ps-label">FK·트리거 복원</span>
            </div>
          </div>
          <div v-else class="kpi-value status-text" :class="job.status">{{ statusLabel(job.status) }}</div>
        </div>

        <div class="kpi-card kpi-prog-card">
          <div class="kpi-header">
            <span class="kpi-label">전체 진행</span>
            <span class="kpi-pct-badge">{{ safeProgress }}%</span>
          </div>
          <div class="kpi-prog-track"><div class="kpi-prog-fill" :style="{width:safeProgress+'%'}"></div></div>
          <div class="kpi-sub">테이블 {{ job.table_done||0 }} / {{ job.table_total||0 }} 완료</div>
        </div>

        <div class="kpi-card">
          <div class="kpi-header"><span class="kpi-label">처리 행</span></div>
          <div class="kpi-value">{{ fmtNum(job.rows_processed) }}<span class="kpi-unit"> rows</span></div>
          <div class="kpi-sub">전체 {{ job.rows_total ? fmtNum(job.rows_total) : '측정 중' }}</div>
        </div>

        <div class="kpi-card">
          <div class="kpi-header"><span class="kpi-label">처리 속도</span></div>
          <div class="kpi-value">{{ fmtNum(job.speed) }}<span class="kpi-unit"> rows/s</span></div>
          <div class="kpi-sub">{{ job.status==='running'?'실시간':'—' }}</div>
        </div>

        <div class="kpi-card" :class="{'kpi-error': hasAnyError}">
          <div class="kpi-header">
            <span class="kpi-label">오류</span>
          </div>
          <div class="kpi-value" :class="{'err-val': hasAnyError}">{{ fmtNum(job.rows_error||0) }}<span class="kpi-unit"> 건</span></div>
          <div class="kpi-sub">
            <button v-if="(job.rows_error||0)>0||errItems.length>0" class="err-open-btn" @click="openErrModal">
              <span class="err-btn-dot"></span>
              <span class="err-btn-text">{{ errItems.length > 0 ? errItems.length + '개 항목' : '행 오류' }}</span>
              <span class="err-btn-divider"></span>
              <span class="err-btn-action">상세 보기</span>
              <svg viewBox="0 0 8 8" fill="none" stroke="currentColor" stroke-width="1.5" style="width:8px;height:8px;opacity:.6">
                <polyline points="1.5,3 4,5.5 6.5,3"/>
              </svg>
            </button>
            <span v-else>정상</span>
          </div>
        </div>
      </div>

      <!-- ── 현재 진행 중 ── -->
      <div v-if="job.status==='running'&&job.current_table" class="current-bar">
        <div class="cur-left">
          <span class="live-badge"><span class="live-dot"></span>LIVE</span>
          <span class="cur-name">{{ job.current_table }}</span>
        </div>
        <div class="cur-mid">
          <div class="cur-track"><div class="cur-fill" :style="{width:tableProgress+'%'}"></div></div>
        </div>
        <div class="cur-right">
          <span class="cur-pct">{{ tableProgress }}%</span>
          <span class="cur-rows">{{ fmtNum(job.current_table_rows_done) }} / {{ fmtNum(job.current_table_rows_total) }} rows</span>
        </div>
      </div>

      <!-- ── 툴바 ── -->
      <div class="toolbar">
        <div class="search-box">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px;opacity:.4;flex-shrink:0">
            <circle cx="6" cy="6" r="4"/><line x1="9.5" y1="9.5" x2="13" y2="13"/>
          </svg>
          <input v-model="search" placeholder="이름 검색..." class="search-inp"/>
          <button v-if="search" class="search-clear" @click="search=''">✕</button>
        </div>
        <div class="filter-group">
          <button v-for="f in filters" :key="f.v" class="filter-btn"
            :class="{active:activeFilter===f.v, 'mismatch-filter': f.v==='mismatch' && activeFilter===f.v}"
            @click="activeFilter=f.v">
            <span v-if="f.v!=='all'" class="fdot" :class="f.v"></span>
            {{ f.l }}<span class="fcnt">{{ filterCount(f.v) }}</span>
          </button>
        </div>
        <div class="type-group">
          <button v-for="t in types" :key="t.v" class="type-btn" :class="{active:activeType===t.v}" @click="activeType=t.v">{{ t.l }}</button>
        </div>
      </div>

      <!-- ── 아이템 테이블 ── -->
      <div class="item-table">
        <div class="item-head">
          <span class="ic-name ih-sort" @click="setSort('name')">이름<span class="sort-arrow">{{ sortKey==='name'?(sortDir==='asc'?'↑':'↓'):'' }}</span></span>
          <span class="ic-type">유형</span>
          <span class="ic-prog">진행</span>
          <span class="ic-pct ih-sort" @click="setSort('progress')">%<span class="sort-arrow">{{ sortKey==='progress'?(sortDir==='asc'?'↑':'↓'):'' }}</span></span>
          <span class="ic-rowcnt ih-sort" @click="setSort('rows')">건수<span class="sort-arrow">{{ sortKey==='rows'?(sortDir==='asc'?'↑':'↓'):'' }}</span></span>
          <span class="ic-time ih-sort" @click="setSort('finished_at')">완료 시각<span class="sort-arrow">{{ sortKey==='finished_at'?(sortDir==='asc'?'↑':'↓'):'' }}</span></span>
          <span class="ic-stat ih-sort" @click="setSort('status')">상태<span class="sort-arrow">{{ sortKey==='status'?(sortDir==='asc'?'↑':'↓'):'' }}</span></span>
        </div>

        <div v-if="filteredItems.length===0" class="no-items">검색 결과가 없습니다</div>

        <transition-group name="rf" tag="div">
          <div v-for="item in filteredItems" :key="item.name"
               class="item-row" :class="item.status" @click="toggleDetail(item.name)">
            <span class="ic-name">
              <span class="item-ico" :class="item.type">{{ typeIcon(item.type) }}</span>
              <span class="item-nm" :title="item.name">{{ item.name }}</span>
            </span>
            <span class="ic-type">
              <span class="type-pill" :class="item.type">{{ typeLabelShort(item.type) }}</span>
            </span>
            <!-- 진행 바 (가변) -->
            <span class="ic-prog">
              <div class="prog-track">
                <div class="prog-fill" :class="item.status" :style="{width:itemProgress(item)+'%'}"></div>
              </div>
            </span>
            <!-- % 고정 -->
            <span class="ic-pct">
              <span class="row-pct" :class="item.status">{{ item.type==='table' ? progLabel(item) : '—' }}</span>
            </span>
            <!-- 건수 고정 -->
            <span class="ic-rowcnt">
              <template v-if="item.type==='table'">
                <template v-if="item.status==='running'">
                  <span class="rows-inline">{{ fmtNum(job.current_table_rows_done) }}<span class="row-arr">→</span>{{ fmtNum(job.current_table_rows_total) }}</span>
                </template>
                <template v-else-if="item.status==='done'||item.rows_src>0">
                  <span class="rows-inline" :class="{mismatch: item.rows_tgt!==undefined && item.rows_tgt!==(item.rows_src||item.rows||0)}">
                    {{ fmtNum(item.rows_src||item.rows||0) }}<span class="row-arr">→</span>{{ fmtNum(item.rows_tgt!==undefined?item.rows_tgt:(item.rows_src||item.rows||0)) }}
                  </span>
                </template>
                <template v-else><span class="muted">—</span></template>
              </template>
              <span v-else class="muted">—</span>
            </span>
            <span class="ic-time muted">{{ fmtTime(item.finished_at) }}</span>
            <span class="ic-stat">
              <span class="stat-pill" :class="item.status">
                <svg v-if="item.status==='running'" class="spin" viewBox="0 0 12 12">
                  <circle cx="6" cy="6" r="4.5" stroke="currentColor" stroke-width="1.5" fill="none" stroke-dasharray="20" stroke-dashoffset="7"/>
                </svg>
                <svg v-else-if="item.status==='done'" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2"><polyline points="2,6 4.5,9 10,3"/></svg>
                <svg v-else-if="item.status==='error'" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="3" x2="9" y2="9"/><line x1="9" y1="3" x2="3" y2="9"/></svg>
                <svg v-else viewBox="0 0 12 12" fill="currentColor"><circle cx="6" cy="6" r="2.5"/></svg>
                {{ statusLabel(item.status) }}
              </span>
            </span>
            <!-- 오류 상세 + 재이관 버튼 -->
            <div v-if="expanded[item.name]&&item.error" class="err-row" @click.stop>
              <div class="err-msg">{{ item.error }}</div>
              <button v-if="item.type==='table'" class="err-remig-btn" @click.stop="openRemig(item)">
                <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" style="width:10px;height:10px">
                  <path d="M10 2A4.5 4.5 0 1 1 5.5 1"/><polyline points="7,0 10,2 8,5"/>
                </svg>
                재이관
              </button>
              <button v-else-if="['function','procedure','trigger','view'].includes(item.type)" class="err-remig-btn obj-remig" @click.stop="openObjRemig(item)">
                <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" style="width:10px;height:10px">
                  <path d="M10 2A4.5 4.5 0 1 1 5.5 1"/><polyline points="7,0 10,2 8,5"/>
                </svg>
                재이관
              </button>
            </div>

            <!-- 오브젝트 재이관 모달 -->
            <div v-if="objRemigTarget&&objRemigTarget.name===item.name" class="remig-modal" @click.stop>
              <div class="remig-header">
                <span class="remig-title">{{ item.type?.toUpperCase() }} [{{ item.name }}] — 재이관</span>
                <button class="remig-close" @click="objRemigTarget=null">✕</button>
              </div>
              <div class="remig-body">
                <div v-if="item.error" class="remig-error">
                  <svg viewBox="0 0 12 12" fill="none" stroke="#ef4444" stroke-width="1.5" style="width:11px;height:11px;flex-shrink:0">
                    <circle cx="6" cy="6" r="4.5"/><line x1="6" y1="3.5" x2="6" y2="6.5"/>
                  </svg>
                  {{ item.error }}
                </div>
                <div class="remig-section-label">이관 방식</div>
                <div class="remig-opts">
                  <label class="remig-opt" :class="{active: objRemigMode==='drop_recreate'}">
                    <input type="radio" v-model="objRemigMode" value="drop_recreate"/>
                    <div class="remig-opt-body">
                      <span class="remig-opt-title">🔄 DROP 후 재생성</span>
                      <span class="remig-opt-desc">기존 오브젝트 삭제 후 재생성</span>
                    </div>
                  </label>
                  <label class="remig-opt" :class="{active: objRemigMode==='ai'}">
                    <input type="radio" v-model="objRemigMode" value="ai"/>
                    <div class="remig-opt-body">
                      <span class="remig-opt-title">🤖 AI 변환</span>
                      <span class="remig-opt-desc">Claude AI가 오류 분석 후 DDL 변환 및 재생성</span>
                    </div>
                  </label>
                </div>
              </div>
              <div class="remig-footer">
                <button class="remig-cancel" @click="objRemigTarget=null">취소</button>
                <button class="remig-run" @click="doObjRemig(item)" :disabled="objRemigRunning">
                  <span v-if="objRemigRunning" class="spin-sm"></span>
                  재이관 실행
                </button>
              </div>
            </div>

            <!-- 테이블 재이관 모달 -->
            <div v-if="remigTarget&&remigTarget.name===item.name" class="remig-modal" @click.stop>
              <div class="remig-header">
                <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px;flex-shrink:0">
                  <rect x="1" y="1" width="12" height="12" rx="1.5"/>
                  <line x1="3" y1="5" x2="11" y2="5"/><line x1="3" y1="8" x2="9" y2="8"/>
                </svg>
                <span class="remig-title">{{ remigTarget.name }} — 재이관</span>
                <button class="remig-close" @click="remigTarget=null">✕</button>
              </div>
              <div class="remig-body">
                <!-- 현재 오류 -->
                <div class="remig-error">
                  <svg viewBox="0 0 12 12" fill="none" stroke="#ef4444" stroke-width="1.5" style="width:11px;height:11px;flex-shrink:0;margin-top:1px">
                    <circle cx="6" cy="6" r="4.5"/><line x1="6" y1="3.5" x2="6" y2="6.5"/><circle cx="6" cy="8.5" r=".6" fill="#ef4444"/>
                  </svg>
                  {{ remigTarget.error }}
                </div>
                <!-- 누적 오류 히스토리 -->
                <template v-if="errorHistory[remigTarget.name]?.length > 1">
                  <div class="remig-section-label">
                    오류 히스토리 ({{ errorHistory[remigTarget.name].length }}회 시도)
                    <span style="color:#2563eb;font-weight:500"> → AI에 모두 전달됩니다</span>
                  </div>
                  <div class="remig-hist-list">
                    <div v-for="h in errorHistory[remigTarget.name]" :key="h.attempt" class="remig-hist-row">
                      <span class="remig-hist-num">#{{ h.attempt }}</span>
                      <span class="remig-hist-ts">{{ h.ts }}</span>
                      <span class="remig-hist-err">{{ h.error }}</span>
                    </div>
                  </div>
                </template>
                <!-- Job 원본 설정 표시 -->
                <div class="remig-job-opts">
                  <span class="remig-job-opt-lbl">원본 Job 설정</span>
                  <span class="remig-job-opt-val">
                    {{ {schema_data:'스키마+데이터',data_only:'데이터만',schema_only:'스키마만'}[job.table_mode]||job.table_mode||'스키마+데이터' }}
                    <span v-if="job.drop_table"> · DROP 후 재생성</span>
                    <span v-if="job.truncate_target"> · TRUNCATE 후 이관</span>
                  </span>
                </div>

                <div class="remig-section-label">재이관 방식 선택</div>
                <div class="remig-opts">
                  <label class="remig-opt" :class="{active: remigMode==='original'}">
                    <input type="radio" v-model="remigMode" value="original"/>
                    <div class="remig-opt-body">
                      <span class="remig-opt-title">⚡ 원본 설정 그대로</span>
                      <span class="remig-opt-desc">처음 이관 시 선택한 옵션으로 재시도</span>
                    </div>
                  </label>
                  <label class="remig-opt" :class="{active: remigMode==='skip_geo'}">
                    <input type="radio" v-model="remigMode" value="skip_geo"/>
                    <div class="remig-opt-body">
                      <span class="remig-opt-title">🔧 미지원 컬럼 스킵</span>
                      <span class="remig-opt-desc">geography, geometry 등 NULL 처리 후 재이관</span>
                    </div>
                  </label>
                  <label class="remig-opt" :class="{active: remigMode==='drop_recreate'}">
                    <input type="radio" v-model="remigMode" value="drop_recreate"/>
                    <div class="remig-opt-body">
                      <span class="remig-opt-title">🔄 DROP 후 재생성</span>
                      <span class="remig-opt-desc">타겟 테이블 완전 삭제 후 스키마·데이터 재구성</span>
                    </div>
                  </label>
                  <label class="remig-opt" :class="{active: remigMode==='ai'}">
                    <input type="radio" v-model="remigMode" value="ai"/>
                    <div class="remig-opt-body">
                      <span class="remig-opt-title">🤖 AI 이관</span>
                      <span class="remig-opt-desc">Claude AI가 오류 분석 후 스키마 변환 및 재이관</span>
                    </div>
                  </label>
                </div>
              </div>
              <div class="remig-footer">
                <button class="remig-cancel" @click="remigTarget=null">취소</button>
                <button class="remig-run" @click="doRemig(remigTarget)" :disabled="remigRunning">
                  <span v-if="remigRunning" class="spin-sm"></span>
                  재이관 실행
                </button>
              </div>
            </div>
          </div>
        </transition-group>
      </div>

      <!-- ── 하단 요약 ── -->
      <div class="foot-summary">
        <span class="foot-total">전체 {{ allItems.length }}개</span>
        <span class="foot-sep">|</span>
        <span class="foot-item"><span class="fdot done"></span>완료 {{ countByStatus('done') }}</span>
        <span class="foot-item"><span class="fdot running"></span>진행중 {{ countByStatus('running') }}</span>
        <span class="foot-item"><span class="fdot pending"></span>대기 {{ countByStatus('pending') }}</span>
        <span v-if="countByStatus('error')" class="foot-item err"><span class="fdot error"></span>오류 {{ countByStatus('error') }}</span>
      </div>

      <!-- 오류 상세 모달 -->
      <div v-if="showErrModal" style="position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:9999;display:flex;align-items:center;justify-content:center" @click.self="showErrModal=false">
        <div style="background:var(--bg-primary);border-radius:14px;width:min(680px,95vw);max-height:80vh;display:flex;flex-direction:column;box-shadow:0 8px 40px rgba(0,0,0,.3);overflow:hidden">
          <!-- 헤더 -->
          <div style="display:flex;align-items:center;gap:8px;padding:14px 18px;border-bottom:0.5px solid var(--border-light)">
            <span style="font-size:.88rem;font-weight:600;color:var(--text-primary);flex:1">오류 상세 — {{ errItems.length }}개 항목 / 오류 행 {{ fmtNum(job.rows_error||0) }}건</span>
            <button @click="showErrModal=false" style="border:none;background:none;cursor:pointer;font-size:1rem;color:var(--text-tertiary);padding:2px 8px">✕</button>
          </div>
          <!-- 요약 바 -->
          <div style="display:flex;gap:0;border-bottom:0.5px solid var(--border-light);background:var(--bg-secondary)">
            <div style="flex:1;text-align:center;padding:10px 6px">
              <div style="font-size:1.1rem;font-weight:700;color:var(--text-primary)">{{ errItems.filter(i=>i.status==='error').length }}</div>
              <div style="font-size:.68rem;color:var(--text-tertiary);margin-top:2px">항목 오류</div>
            </div>
            <div style="flex:1;text-align:center;padding:10px 6px;border-left:0.5px solid var(--border-light)">
              <div style="font-size:1.1rem;font-weight:700;color:var(--text-primary)">{{ errItems.filter(i=>i.batch_errors?.length).length }}</div>
              <div style="font-size:.68rem;color:var(--text-tertiary);margin-top:2px">배치 오류 테이블</div>
            </div>
            <div style="flex:1;text-align:center;padding:10px 6px;border-left:0.5px solid var(--border-light)">
              <div style="font-size:1.1rem;font-weight:700;color:#ef4444">{{ fmtNum(job.rows_error||0) }}</div>
              <div style="font-size:.68rem;color:var(--text-tertiary);margin-top:2px">실패 행</div>
            </div>
          </div>
          <!-- 목록 -->
          <div style="overflow-y:auto;flex:1">
            <div v-if="!errItems.length" style="padding:24px;text-align:center;font-size:12px;color:var(--text-tertiary)">
              이관된 Job의 오류 정보가 없습니다. 새 이관을 실행해야 기록됩니다.
            </div>
            <div v-for="item in errItems" :key="item.name" class="emd-item">
              <!-- 항목 헤더 -->
              <div class="emd-row">
                <span class="emd-badge" :class="item.status==='error'?'err':'warn'">{{ item.type?.toUpperCase() }}</span>
                <span class="emd-name">{{ item.name }}</span>
                <span v-if="item.batch_error_rows" class="emd-fail-rows">{{ fmtNum(item.batch_error_rows) }}행 실패</span>
                <span v-if="item.finished_at" class="emd-time">{{ new Date(item.finished_at+'Z').toLocaleTimeString('ko-KR') }}</span>
                <button v-if="item.type==='table'||['function','procedure','trigger','view'].includes(item.type)"
                        class="emd-remig-btn"
                        @click="item.type==='table'?toggleInlineRemig(item.name):openObjRemigFromModal(item)">
                  <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" style="width:10px;height:10px">
                    <path d="M10 2A4.5 4.5 0 1 1 5.5 1"/><polyline points="7,0 10,2 8,5"/>
                  </svg>
                  재이관
                  <svg viewBox="0 0 10 6" fill="none" stroke="currentColor" stroke-width="1.5" style="width:8px;height:8px;transition:transform .2s"
                       :style="{transform: inlineRemigOpen[item.name]?'rotate(180deg)':'rotate(0deg)'}">
                    <polyline points="1,1 5,5 9,1"/>
                  </svg>
                </button>
              </div>
              <!-- 오류 메시지 -->
              <div v-if="item.error" class="emd-error-msg">{{ item.error }}</div>
              <!-- 배치 오류 -->
              <div v-if="item.batch_errors?.length" class="emd-batch-errs">
                <div class="emd-batch-label">배치 오류 내역 ({{ item.batch_errors.length }}건)</div>
                <div v-for="(be,bi) in item.batch_errors" :key="bi" class="emd-batch-row">
                  <span class="emd-batch-num">#{{ bi+1 }}</span>{{ be }}
                </div>
              </div>
              <!-- 인라인 재이관 패널 -->
              <div v-if="inlineRemigOpen[item.name]" class="emd-remig-panel">
                <div class="emd-remig-opts">
                  <label v-for="opt in remigOpts" :key="opt.value"
                         class="emd-remig-opt"
                         :class="{active: (inlineRemigMode[item.name]||'drop_recreate')===opt.value}"
                         @click="inlineRemigMode[item.name]=opt.value">
                    <span class="emd-remig-opt-icon">{{ opt.icon }}</span>
                    <div class="emd-remig-opt-body">
                      <span class="emd-remig-opt-title">{{ opt.title }}</span>
                      <span class="emd-remig-opt-desc">{{ opt.desc }}</span>
                    </div>
                    <span v-if="(inlineRemigMode[item.name]||'drop_recreate')===opt.value" class="emd-remig-check">✓</span>
                  </label>
                </div>
                <div class="emd-remig-actions">
                  <button class="emd-remig-cancel" @click="inlineRemigOpen[item.name]=false">취소</button>
                  <button class="emd-remig-run" :disabled="remigRunning"
                          @click="runInlineRemig(item)">
                    <span v-if="remigRunning" class="spin-sm"></span>
                    재이관 실행
                  </button>
                </div>
              </div>
            </div>
          </div>
          <!-- 푸터 -->
          <div style="display:flex;justify-content:flex-end;padding:12px 18px;border-top:0.5px solid var(--border-light)">
            <button @click="showErrModal=false" style="padding:6px 20px;border-radius:7px;background:#2563eb;color:#fff;border:none;font-size:.82rem;font-weight:600;cursor:pointer">닫기</button>
          </div>
        </div>
      </div>

    </template>
  <!-- 오류 상세 모달 -->

  </div>
</template>

<script setup>
defineOptions({ name: 'JobMonitor' })
import { ref, computed, onMounted, onActivated, onUnmounted, watch } from 'vue'

const API = '/api/v1/jobs'
const jobs = ref([]); const job = ref(null); const selectedJobId = ref('')
const search = ref(''); const activeFilter = ref('all'); const activeType = ref('all')
const expanded = ref({}); const polling = ref(false); const autoRefresh = ref(false)
let autoTimer = null

const filters = [
  {v:'all',l:'전체'},{v:'running',l:'진행중'},{v:'done',l:'완료'},
  {v:'pending',l:'대기'},{v:'error',l:'오류'},{v:'mismatch',l:'불일치'},
]
const types = [
  {v:'all',l:'전체'},{v:'table',l:'테이블'},{v:'view',l:'뷰'},
  {v:'procedure',l:'프로시저'},{v:'function',l:'함수'},{v:'trigger',l:'트리거'},
]

async function loadJobs() {
  try {
    const r = await fetch(API); if (r.ok) jobs.value = await r.json()
    if (!selectedJobId.value) {
      const running = jobs.value.find(j=>j.status==='running')
      if (running) { selectedJobId.value = running.id; await loadJob() }
    }
  } catch {}
}
async function loadJob() {
  if (!selectedJobId.value) { job.value = null; return }
  polling.value = true
  try { const r = await fetch(`${API}/${selectedJobId.value}`); if (r.ok) job.value = await r.json() } catch {}
  polling.value = false
}
async function refresh() { await loadJobs(); await loadJob() }
function clearScreen() {
  selectedJobId.value = ''
  job.value = null
  expanded.value = {}
  remigTarget.value = null
  showErrModal.value = false
  autoRefresh.value = false
  toggleAuto()
  loadJobs()
}
function onJobChange() { loadJob() }
function toggleAuto() { clearInterval(autoTimer); if (autoRefresh.value) autoTimer = setInterval(loadJob,2000) }
onMounted(async()=>{ await loadJobs() })

// keep-alive 복귀 시 — 항상 최신 Job 목록 새로고침
onActivated(async () => {
  await loadJobs()
  // 실행 중인 Job이 있으면 자동 새로고침 켜기
  if (job.value?.status === 'running' && !autoRefresh.value) {
    autoRefresh.value = true
    toggleAuto()
  }
})
onUnmounted(()=>{ clearInterval(autoTimer) })
watch(()=>job.value?.status, async s=>{
  if(s && s!=='running' && autoRefresh.value) {
    autoRefresh.value = false
    clearInterval(autoTimer)
    await loadJob()  // 완료 시 마지막 한 번 갱신
  }
})

const safeProgress = computed(()=>{
  if(!job.value) return 0
  return Math.min(100,Math.max(0,Math.round((job.value.progress||0)*10)/10))
})
const sortKey = ref('')
const sortDir = ref('asc')
function setSort(key) {
  if (sortKey.value === key) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else { sortKey.value = key; sortDir.value = 'asc' }
}

const allItems = computed(()=>{
  if(!job.value) return []
  return Object.entries(job.value.item_statuses||{}).map(([name,v])=>({name,...v}))
})
const filteredItems = computed(()=>{
  let list = allItems.value
  if(search.value) list = list.filter(i=>i.name.toLowerCase().includes(search.value.toLowerCase()))
  if(activeFilter.value==='mismatch') list = list.filter(isMismatch)
  else if(activeFilter.value!=='all') list = list.filter(i=>i.status===activeFilter.value)
  if(activeType.value!=='all')   list = list.filter(i=>i.type===activeType.value)
  const order={running:0,error:1,done:2,pending:3}
  // 컬럼 정렬
  if (sortKey.value) {
    const k = sortKey.value
    const dir = sortDir.value === 'asc' ? 1 : -1
    list = [...list].sort((a, b) => {
      let av = a[k] ?? '', bv = b[k] ?? ''
      if (k === 'rows') { av = a.rows||0; bv = b.rows||0; return (av-bv)*dir }
      if (k === 'status') {
        const o = {running:0,error:1,done:2,pending:3}
        return ((o[av]??9)-(o[bv]??9))*dir
      }
      return av < bv ? -dir : av > bv ? dir : 0
    })
    return list
  }
  return [...list].sort((a,b)=>(order[a.status]??9)-(order[b.status]??9))
})
const tableProgress = computed(()=>{
  if(!job.value) return 0
  const t = job.value.current_table_rows_total; if(!t) return 0
  return Math.min(100,Math.round(job.value.current_table_rows_done/t*100))
})
function itemProgress(item) {
  if(item.status==='running') return tableProgress.value
  if(item.status==='done') return 100
  return 0
}
function isMismatch(i) {
  return i.type==='table' && i.rows_tgt !== undefined && i.rows_tgt !== (i.rows_src || i.rows || 0)
}
function filterCount(v) {
  if (v === 'all') return allItems.value.length
  if (v === 'mismatch') return allItems.value.filter(isMismatch).length
  return allItems.value.filter(i => i.status === v).length
}
function countByStatus(s){ return allItems.value.filter(i=>i.status===s).length }
function progLabel(item){
  if(item.status==='done') return '100%'
  if(item.status==='running') return tableProgress.value+'%'
  if(item.status==='error') return '오류'
  return '대기'
}
function statusLabel(s){ return {running:'진행중',done:'완료',pending:'대기',error:'오류',completed:'완료',idle:'대기',aborted:'중단'}[s]??s }

// phase 순서 정의
const PHASE_ORDER = ['FK_DISABLE','RUNNING','OBJECTS','FK_RESTORE','DONE']

function phaseStepClass(step) {
  const phase = job.value?.phase || 'INIT'
  const status = job.value?.status
  const cur = PHASE_ORDER.indexOf(phase)
  const idx = PHASE_ORDER.indexOf(step)
  if (status === 'completed') return 'ps-done'
  if (phase === step) return 'ps-active'
  if (cur > idx) return 'ps-done'
  return 'ps-pending'
}

function phaseStepIcon(step) {
  const cls = phaseStepClass(step)
  if (cls === 'ps-done')   return '✓'
  if (cls === 'ps-active') return '⟳'
  return '○'
}
function typeIcon(t){ return {table:'⊞',view:'◫',procedure:'⚙',function:'ƒ',trigger:'⚡'}[t]??'○' }
function typeLabelShort(t){ return {table:'TABLE',view:'VIEW',procedure:'PROC',function:'FUNC',trigger:'TRIG'}[t]??t.toUpperCase() }
function fmtNum(n){ if(!n&&n!==0) return '0'; return Number(n).toLocaleString() }
function fmtTime(ts){ if(!ts) return '—'; return new Date(ts).toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit',second:'2-digit'}) }
function toggleDetail(name){ expanded.value={...expanded.value,[name]:!expanded.value[name]} }

const remigTarget    = ref(null)
const objRemigTarget = ref(null)
const objRemigMode   = ref('drop_recreate')
const objRemigRunning = ref(false)
const remigMode    = ref('skip_geo')
const remigRunning = ref(false)
const showErrModal = ref(false)
function openErrModal() { showErrModal.value = true }

// 오류 항목 목록 — status=error 또는 batch_errors 있는 항목
const errItems = computed(() => {
  if (!job.value?.item_statuses) return []
  return Object.entries(job.value.item_statuses)
    .filter(([, v]) => (v.status === 'error' && v.error) || v.batch_errors?.length)
    .map(([name, v]) => ({ name, ...v }))
    .sort((a, b) => (a.finished_at||'').localeCompare(b.finished_at||''))
})
const hasAnyError = computed(() => errItems.value.length > 0 || (job.value?.rows_error || 0) > 0)

function copyErrReport() {
  const j = job.value
  const errList = errItems.value.map(i => '[' + i.type.toUpperCase() + '] ' + i.name + ': ' + i.error).join('\n')
  const report = [
    '=== 오류 리포트 ===',
    'Job: ' + (j?.name || ''),
    '시각: ' + new Date().toLocaleString('ko-KR'),
    '오류 항목: ' + errItems.value.length + '개 / 오류 행: ' + (j?.rows_error || 0).toLocaleString() + '건',
    '',
    errList
  ].join('\n')
  navigator.clipboard.writeText(report)
    .then(() => alert('클립보드에 복사됐습니다'))
    .catch(() => alert('복사 실패'))
}
// 테이블별 오류 히스토리 누적 { tableName: [{attempt, error, ts}] }
const errorHistory = ref({})

function onModalRemig(item) {
  showErrModal.value = false
  setTimeout(() => openRemig(item), 150)
}

// 인라인 재이관 패널
const inlineRemigOpen = ref({})
const inlineRemigMode = ref({})
const remigOpts = [
  { value:'drop_recreate', icon:'🔄', title:'DROP 후 재생성',     desc:'타겟 테이블 삭제 후 스키마·데이터 완전 재구성' },
  { value:'skip_geo',      icon:'🔧', title:'자체 이관',           desc:'미지원 컬럼(geography 등) NULL 처리 후 재이관' },
  { value:'original',      icon:'⚡', title:'원본 설정 그대로',    desc:'처음 이관 시 선택한 옵션으로 재시도' },
  { value:'ai',            icon:'🤖', title:'AI 이관',             desc:'Claude AI가 오류 분석 후 스키마 변환 및 재이관' },
]

function toggleInlineRemig(name) {
  inlineRemigOpen.value = { ...inlineRemigOpen.value, [name]: !inlineRemigOpen.value[name] }
  if (!inlineRemigMode.value[name]) inlineRemigMode.value[name] = 'drop_recreate'
}

async function runInlineRemig(item) {
  if (!job.value || remigRunning.value) return
  remigRunning.value = true
  const mode = inlineRemigMode.value[item.name] || 'drop_recreate'
  // item_statuses 즉시 running으로
  if (job.value.item_statuses?.[item.name]) {
    job.value.item_statuses[item.name].status = 'running'
    job.value.item_statuses[item.name].error  = null
  }
  inlineRemigOpen.value[item.name] = false
  try {
    const res = await fetch('/api/v1/jobs/' + job.value.id + '/remig-table', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        table: item.name, mode,
        error_hint: item.error,
        error_history: errorHistory.value[item.name] || [],
        table_mode: job.value?.table_mode,
        drop_table: job.value?.drop_table,
        truncate_target: job.value?.truncate_target,
        create_table: job.value?.create_table
      })
    })
    if (!res.ok) {
      const e = await res.json()
      alert('재이관 실패: ' + (e.detail || '알 수 없는 오류'))
    } else {
      setTimeout(async () => { await loadJob() }, 3000)
    }
  } catch(e) {
    alert('재이관 오류: ' + e.message)
  } finally {
    remigRunning.value = false
  }
}

function openObjRemig(item) {
  objRemigTarget.value = { ...item }
  objRemigMode.value = 'drop_recreate'
}
function openObjRemigFromModal(item) {
  showErrModal.value = false
  setTimeout(() => openObjRemig(item), 150)
}
async function doObjRemig(item) {
  if (!job.value || objRemigRunning.value) return
  objRemigRunning.value = true
  if (job.value.item_statuses?.[item.name]) {
    job.value.item_statuses[item.name].status = 'running'
    job.value.item_statuses[item.name].error  = null
  }
  objRemigTarget.value = null
  try {
    const res = await fetch('/api/v1/jobs/' + job.value.id + '/remig-object', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: item.name,
        type: item.type,
        mode: objRemigMode.value,
        error_hint: item.error
      })
    })
    if (!res.ok) {
      const e = await res.json()
      alert('재이관 실패: ' + (e.detail || '오류'))
    } else {
      setTimeout(() => loadJob(), 3000)
    }
  } catch(e) {
    alert('재이관 오류: ' + e.message)
  } finally {
    objRemigRunning.value = false
  }
}

function openRemig(item) {
  remigTarget.value = { ...item }
  remigMode.value = 'original'  // 기본: 원본 설정 그대로
  // 오류 히스토리 누적
  if (item.error) {
    const hist = errorHistory.value[item.name] || []
    const already = hist.some(h => h.error === item.error)
    if (!already) {
      errorHistory.value[item.name] = [
        ...hist,
        { attempt: hist.length + 1, error: item.error, ts: new Date().toLocaleTimeString('ko-KR') }
      ]
    }
  }
}

async function doRemig(item) {
  if (!job.value || remigRunning.value) return
  remigRunning.value = true

  // 즉시 UI 상태를 "running"으로 변경
  if (job.value.item_statuses?.[item.name]) {
    job.value.item_statuses[item.name].status = 'running'
    job.value.item_statuses[item.name].error  = null
  }
  remigTarget.value = null  // 모달 닫기

  try {
    const j = job.value
    const res = await fetch('/api/v1/jobs/' + j.id + '/remig-table', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        table: item.name,
        mode: remigMode.value,
        error_hint: item.error,
        error_history: errorHistory.value[item.name] || [],
        // 원본 Job 설정 전달 (original 모드에서 사용)
        table_mode:       job.value?.table_mode,
        drop_table:       job.value?.drop_table,
        truncate_target:  job.value?.truncate_target,
        create_table:     job.value?.create_table
      })
    })
    if (res.ok) {
      remigTarget.value = null
      // 재이관 완료 후 결과 확인 — 오류 시 히스토리에 추가
      setTimeout(async () => {
        await loadJob()
        const newItem = allItems.value.find(i => i.name === item.name)
        if (newItem?.status === 'error' && newItem.error) {
          const hist = errorHistory.value[item.name] || []
          const already = hist.some(h => h.error === newItem.error)
          if (!already) {
            errorHistory.value[item.name] = [
              ...hist,
              { attempt: hist.length + 1, error: newItem.error, ts: new Date().toLocaleTimeString('ko-KR') }
            ]
          }
        }
      }, 3000)
    } else {
      const err = await res.json()
      alert('재이관 실패: ' + (err.detail || '알 수 없는 오류'))
    }
  } catch(e) {
    alert('재이관 요청 오류: ' + e.message)
  } finally {
    remigRunning.value = false
  }
}
</script>

<style scoped>
.jm{display:flex;flex-direction:column;gap:14px;padding:24px;max-width:1380px;margin:0 auto}
.jm-header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.page-title{font-size:1.25rem;font-weight:700;color:var(--text-primary)}
.page-desc{font-size:.78rem;color:var(--text-tertiary);margin-top:2px}
.jm-controls{display:flex;align-items:center;gap:8px}
.job-select-wrap{display:flex;align-items:center;gap:7px;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:var(--radius-md);padding:5px 10px;min-width:240px}
.select-ico{width:12px;height:12px;opacity:.4;flex-shrink:0}
.job-select{border:none;outline:none;background:transparent;font-size:.82rem;color:var(--text-primary);font-family:var(--font);flex:1;cursor:pointer}
.ctrl-btn{width:30px;height:30px;display:flex;align-items:center;justify-content:center;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:var(--bg-secondary);cursor:pointer;color:var(--text-secondary);transition:all .12s}
.clear-btn{width:auto !important;padding:0 10px;gap:2px;color:var(--text-tertiary)}.clear-btn:hover{color:#ef4444;border-color:rgba(239,68,68,.3);background:rgba(239,68,68,.06)}
.ctrl-btn svg{width:12px;height:12px}
.ctrl-btn:hover{background:var(--bg-primary);color:var(--text-primary)}
.ctrl-btn.spinning svg{animation:spin 1s linear infinite}
.auto-label{display:flex;align-items:center;gap:6px;cursor:pointer;user-select:none}
.auto-label input{display:none}
.auto-track{width:28px;height:16px;border-radius:99px;background:var(--border-mid);position:relative;transition:background .2s}
.auto-label input:checked~.auto-track{background:#3b82f6}
.auto-thumb{position:absolute;top:2px;left:2px;width:12px;height:12px;border-radius:50%;background:#fff;transition:transform .2s;box-shadow:0 1px 3px rgba(0,0,0,.2)}
.auto-label input:checked~.auto-track .auto-thumb{transform:translateX(12px)}
.auto-txt{font-size:.75rem;color:var(--text-tertiary)}

.empty-state{display:flex;flex-direction:column;align-items:center;gap:10px;padding:72px 20px;color:var(--text-tertiary)}
.empty-icon{width:56px;height:56px;border-radius:16px;background:var(--bg-secondary);display:flex;align-items:center;justify-content:center}
.empty-icon svg{width:28px;height:28px;opacity:.4}
.empty-title{font-size:.95rem;font-weight:600;color:var(--text-secondary)}
.empty-desc{font-size:.78rem;color:var(--text-tertiary);text-align:center;line-height:1.6}

.kpi-grid{display:grid;grid-template-columns:1.1fr 1.6fr 1fr 1fr 1fr;gap:10px}
@media(max-width:900px){.kpi-grid{grid-template-columns:repeat(3,1fr)}}
.kpi-card{background:var(--bg-secondary);border:0.5px solid var(--border-light);border-radius:12px;padding:14px 16px;display:flex;flex-direction:column;gap:5px;position:relative;overflow:hidden}
.kpi-card::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:transparent;border-radius:3px 0 0 3px}
.kpi-running::before{background:#3b82f6}
.kpi-completed::before,.kpi-done::before{background:#22c55e}
.kpi-error::before{background:#ef4444}
.kpi-header{display:flex;align-items:center;justify-content:space-between}
.kpi-label{font-size:.67rem;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.06em}
.kpi-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.kpi-dot.running{background:#3b82f6;animation:pulse 1.5s infinite}
.kpi-dot.completed,.kpi-dot.done{background:#22c55e}
.kpi-dot.error{background:#ef4444}
.kpi-dot.idle,.kpi-dot.pending{background:#94a3b8}
.kpi-value{font-size:1.3rem;font-weight:700;color:var(--text-primary);line-height:1.2}
.kpi-unit{font-size:.7rem;font-weight:400;color:var(--text-tertiary)}
.kpi-sub{font-size:.7rem;color:var(--text-tertiary)}
.err-val{color:#ef4444}
.status-text.running{color:#3b82f6}
.status-text.completed,.status-text.done{color:#22c55e}
.status-text.error{color:#ef4444}
.status-text.idle,.status-text.pending{color:var(--text-secondary)}
.kpi-pct-badge{font-size:.73rem;font-weight:700;color:#3b82f6;background:rgba(59,130,246,.1);padding:1px 7px;border-radius:99px}
.kpi-prog-track{height:5px;background:var(--border-light);border-radius:99px;overflow:hidden}
.kpi-prog-fill{height:100%;background:#3b82f6;border-radius:99px;transition:width .5s ease}

.current-bar{background:linear-gradient(135deg,rgba(59,130,246,.05),rgba(99,102,241,.05));border:0.5px solid rgba(59,130,246,.18);border-radius:var(--radius-md);padding:10px 16px;display:flex;align-items:center;gap:16px}
.cur-left{display:flex;align-items:center;gap:10px;min-width:0;flex:0 0 auto;max-width:320px}
.cur-mid{flex:1}
.cur-right{display:flex;align-items:center;gap:12px;flex-shrink:0}
.live-badge{display:inline-flex;align-items:center;gap:4px;font-size:.63rem;font-weight:700;color:#3b82f6;background:rgba(59,130,246,.1);padding:2px 7px;border-radius:99px;letter-spacing:.06em;flex-shrink:0}
.live-dot{width:5px;height:5px;border-radius:50%;background:#3b82f6;animation:pulse 1s infinite}
.cur-name{font-size:.84rem;font-weight:600;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cur-track{height:6px;background:rgba(59,130,246,.15);border-radius:99px;overflow:hidden}
.cur-fill{height:100%;background:#3b82f6;border-radius:99px;transition:width .3s ease}
.cur-pct{font-size:.8rem;font-weight:700;color:#3b82f6}
.cur-rows{font-size:.73rem;color:var(--text-tertiary);white-space:nowrap}

.toolbar{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.search-box{display:flex;align-items:center;gap:6px;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:var(--radius-sm);padding:5px 9px;min-width:180px}
.search-inp{border:none;outline:none;background:transparent;font-size:.8rem;color:var(--text-primary);flex:1;font-family:var(--font)}
.search-clear{border:none;background:none;cursor:pointer;color:var(--text-tertiary);font-size:.72rem;padding:0 2px;line-height:1}
.filter-group,.type-group{display:flex;gap:3px;flex-wrap:wrap}
.filter-btn,.type-btn{display:inline-flex;align-items:center;gap:3px;padding:4px 8px;border-radius:var(--radius-sm);border:0.5px solid var(--border-light);background:var(--bg-secondary);color:var(--text-tertiary);font-size:.73rem;cursor:pointer;transition:all .12s;font-family:var(--font)}
.filter-btn:hover,.type-btn:hover{border-color:var(--border-mid);color:var(--text-secondary)}
.filter-btn.active,.type-btn.active{background:var(--text-primary);color:var(--bg-primary);border-color:var(--text-primary)}
.fdot{width:6px;height:6px;border-radius:50%;flex-shrink:0;display:inline-block}
.fdot.running{background:#3b82f6}.fdot.done{background:#22c55e}.fdot.pending{background:#94a3b8}.fdot.error{background:#ef4444}
.fcnt{background:rgba(0,0,0,.06);border-radius:99px;padding:0 4px;font-size:.68rem}
.filter-btn.active .fcnt,.type-btn.active .fcnt{background:rgba(255,255,255,.2)}

.item-table{background:var(--bg-secondary);border:0.5px solid var(--border-light);border-radius:12px;overflow:hidden}
.item-head{display:grid;grid-template-columns:2.2fr .65fr 1fr 52px 90px .9fr .85fr;gap:8px;padding:8px 16px;background:var(--bg-primary);border-bottom:0.5px solid var(--border-light);font-size:.66rem;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.06em}
.ih-sort{cursor:pointer;user-select:none;display:inline-flex;align-items:center;gap:3px;transition:color .1s}.ih-sort:hover{color:var(--text-primary)}
.sort-arrow{color:#2563eb;font-weight:700;font-size:.8rem}
.item-row{display:grid;grid-template-columns:2.2fr .65fr 1fr 52px 90px .9fr .85fr;gap:8px;padding:9px 16px;align-items:center;border-bottom:0.5px solid var(--border-light);cursor:pointer;transition:background .12s;font-size:.82rem}
.item-row:last-child{border-bottom:none}
.item-row:hover{background:var(--bg-primary)}
.item-row.running{background:rgba(59,130,246,.03)}
.item-row.error{background:rgba(239,68,68,.03)}
.no-items{display:flex;align-items:center;justify-content:center;gap:8px;padding:32px;color:var(--text-tertiary);font-size:.8rem}
.ic-name{display:flex;align-items:center;gap:8px;min-width:0}
.ic-prog{display:flex;align-items:center;gap:6px}
.ic-stat{display:flex;justify-content:flex-end}
.ic-rows{display:none}
.ic-pct{font-size:.76rem;font-weight:600;text-align:right;white-space:nowrap}
.ic-rowcnt{font-size:.72rem;white-space:nowrap;color:var(--text-secondary)}
.rows-inline{display:inline-flex;align-items:center;gap:2px}
.rows-inline.mismatch{color:#dc2626;font-weight:600}
.ic-time{font-size:.78rem}
.row-pct{font-size:.75rem;font-weight:700;color:var(--text-secondary)}
.row-pct.done{color:#16a34a}.row-pct.running{color:#2563eb}.row-pct.error{color:#ef4444}.row-pct.pending{color:var(--text-tertiary)}
.row-counts{font-size:.7rem;color:var(--text-tertiary);font-variant-numeric:tabular-nums}
.item-ico{width:22px;height:22px;display:flex;align-items:center;justify-content:center;border-radius:5px;font-size:.82rem;flex-shrink:0}
.item-ico.table{background:rgba(59,130,246,.1)}.item-ico.view{background:rgba(124,58,237,.1)}.item-ico.procedure{background:rgba(22,163,74,.1)}.item-ico.function{background:rgba(202,138,4,.1)}.item-ico.trigger{background:rgba(220,38,38,.1)}
.item-nm{font-size:.82rem;font-weight:500;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.type-pill{font-size:.61rem;font-weight:700;padding:2px 5px;border-radius:4px;letter-spacing:.04em}
.type-pill.table{background:rgba(59,130,246,.1);color:#1d4ed8}.type-pill.view{background:rgba(124,58,237,.1);color:#6d28d9}.type-pill.procedure{background:rgba(22,163,74,.1);color:#15803d}.type-pill.function{background:rgba(202,138,4,.1);color:#92400e}.type-pill.trigger{background:rgba(220,38,38,.1);color:#b91c1c}
.prog-track{flex:1;height:5px;background:var(--border-light);border-radius:99px;overflow:hidden;min-width:50px}
.prog-fill{height:100%;border-radius:99px;transition:width .3s}
.prog-fill.running{background:#3b82f6}.prog-fill.done{background:#22c55e}.prog-fill.error{background:#ef4444}
.prog-pct{font-size:.7rem;font-weight:600;color:var(--text-secondary);min-width:30px;text-align:right;flex-shrink:0}
.prog-pct.error{color:#ef4444}.prog-pct.pending{color:var(--text-tertiary)}
.muted{color:var(--text-tertiary)}
.stat-pill{display:inline-flex;align-items:center;gap:4px;font-size:.7rem;font-weight:600;padding:3px 8px;border-radius:99px}
.stat-pill svg{width:10px;height:10px;flex-shrink:0}
.stat-pill.running{background:rgba(59,130,246,.1);color:#1d4ed8}.stat-pill.done{background:rgba(22,163,74,.1);color:#15803d}.stat-pill.error{background:rgba(220,38,38,.1);color:#b91c1c}.stat-pill.pending{background:var(--border-light);color:var(--text-tertiary)}
.err-row{grid-column:1/-1;padding:7px 11px;background:rgba(239,68,68,.06);border:0.5px solid rgba(239,68,68,.18);border-radius:7px;font-size:.73rem;color:#b91c1c;word-break:break-all;margin-top:3px}
.foot-summary{display:flex;align-items:center;gap:9px;font-size:.73rem;color:var(--text-tertiary);padding:2px 0}
.foot-total{font-weight:600;color:var(--text-secondary)}
.foot-sep{opacity:.3}
.foot-item{display:flex;align-items:center;gap:4px}
.foot-item.err{color:#ef4444}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
/* ── 오류 버튼 ── */
.err-open-btn{
  display:inline-flex;align-items:center;gap:5px;
  padding:4px 11px;border-radius:20px;
  background:rgba(239,68,68,.08);color:#dc2626;
  border:0.5px solid rgba(239,68,68,.2);
  font-size:.72rem;cursor:pointer;font-family:var(--font);
  white-space:nowrap;transition:all .15s;
}
.err-open-btn:hover{background:rgba(239,68,68,.16);border-color:rgba(239,68,68,.4);box-shadow:0 2px 8px rgba(239,68,68,.15)}
.err-btn-dot{width:7px;height:7px;border-radius:50%;background:#ef4444;flex-shrink:0;animation:pulse-err 1.5s ease-in-out infinite}
@keyframes pulse-err{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.8)}}
/* 단계 표시 */
.phase-indicator{display:flex;align-items:center;gap:6px;padding:4px 0}
/* 단계별 버튼 */
.prog-inline-info{display:none}
.row-sep{color:var(--text-tertiary);opacity:.4}
.row-arr{color:var(--text-tertiary);opacity:.5;font-size:.68rem;padding:0 1px}
.phase-steps{display:flex;flex-direction:column;gap:4px;width:100%}
.phase-step{display:flex;align-items:center;gap:6px;padding:3px 8px;border-radius:6px;font-size:.72rem;font-weight:500;transition:all .2s}
.phase-step.ps-done{background:rgba(22,163,74,.1);color:#15803d;border:0.5px solid rgba(22,163,74,.2)}
.phase-step.ps-active{background:rgba(37,99,235,.1);color:#1d4ed8;border:0.5px solid rgba(37,99,235,.25);animation:phase-pulse .8s ease-in-out infinite}
.phase-step.ps-pending{background:var(--bg-secondary);color:var(--text-tertiary);border:0.5px solid var(--border-light)}
.ps-icon{font-size:.8rem;width:14px;text-align:center;flex-shrink:0}
.ps-active .ps-icon{animation:spin .8s linear infinite;display:inline-block}
.ps-label{font-size:.71rem}
@keyframes phase-pulse{0%,100%{opacity:1}50%{opacity:.6}}
.phase-spinner{width:12px;height:12px;border:2px solid rgba(37,99,235,.2);border-top-color:#2563eb;border-radius:50%;animation:spin .8s linear infinite;flex-shrink:0}
.phase-text{font-size:.78rem;font-weight:600}
.phase-text.prep{color:#2563eb}
.phase-text.running{color:#16a34a}
.phase-running-dot{width:8px;height:8px;border-radius:50%;background:#22c55e;flex-shrink:0;animation:pulse .8s ease-in-out infinite}
.mismatch-filter{background:rgba(249,115,22,.12) !important;color:#ea580c !important;border-color:rgba(249,115,22,.3) !important}
/* 오류 모달 항목 */
.emd-item{border-bottom:0.5px solid var(--border-light)}
.emd-row{display:flex;align-items:center;gap:8px;padding:10px 18px;background:var(--bg-secondary)}
.emd-badge{font-size:.67rem;font-weight:700;padding:1px 6px;border-radius:4px;flex-shrink:0}
.emd-badge.err{background:rgba(239,68,68,.1);color:#dc2626}
.emd-badge.warn{background:rgba(245,158,11,.1);color:#b45309}
.emd-name{font-size:.84rem;font-weight:600;color:var(--text-primary);flex:1}
.emd-fail-rows{font-size:.7rem;color:#ef4444;font-weight:600;flex-shrink:0}
.emd-time{font-size:.68rem;color:var(--text-tertiary);flex-shrink:0}
.emd-remig-btn{display:inline-flex;align-items:center;gap:4px;padding:4px 10px;border-radius:6px;background:#2563eb;color:#fff;border:none;font-size:.72rem;font-weight:600;cursor:pointer;flex-shrink:0;transition:background .12s}
.emd-remig-btn:hover{background:#1d4ed8}
.emd-error-msg{font-size:.73rem;color:#b91c1c;background:rgba(239,68,68,.04);border-left:3px solid #ef4444;padding:7px 12px 7px 14px;margin:0 18px 8px;border-radius:0 6px 6px 0;word-break:break-all;line-height:1.5}
.emd-batch-errs{padding:0 18px 10px}
.emd-batch-label{font-size:.67rem;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.04em;margin-bottom:5px}
.emd-batch-row{font-size:.71rem;color:#b91c1c;background:rgba(239,68,68,.04);border:0.5px solid rgba(239,68,68,.1);border-radius:5px;padding:5px 9px;margin-bottom:4px;word-break:break-all;line-height:1.5;font-family:monospace}
.emd-batch-num{color:#9ca3af;margin-right:6px}
/* 인라인 재이관 패널 */
.emd-remig-panel{border-top:0.5px solid rgba(37,99,235,.15);background:rgba(37,99,235,.03);padding:12px 18px}
.emd-remig-opts{display:flex;flex-direction:column;gap:5px;margin-bottom:12px}
.emd-remig-opt{display:flex;align-items:flex-start;gap:10px;padding:9px 12px;border-radius:8px;border:0.5px solid var(--border-light);cursor:pointer;background:var(--bg-primary);transition:all .12s}
.emd-remig-opt.active{border-color:#2563eb;background:rgba(37,99,235,.05)}
.emd-remig-opt-icon{font-size:1rem;flex-shrink:0;margin-top:1px}
.emd-remig-opt-body{display:flex;flex-direction:column;gap:2px;flex:1}
.emd-remig-opt-title{font-size:.8rem;font-weight:600;color:var(--text-primary)}
.emd-remig-opt.active .emd-remig-opt-title{color:#1d4ed8}
.emd-remig-opt-desc{font-size:.7rem;color:var(--text-tertiary);line-height:1.4}
.emd-remig-check{font-size:.8rem;color:#2563eb;font-weight:700;flex-shrink:0;margin-top:2px}
.emd-remig-actions{display:flex;justify-content:flex-end;gap:8px}
.emd-remig-cancel{padding:5px 14px;border-radius:6px;border:0.5px solid var(--border-mid);background:transparent;cursor:pointer;font-size:.78rem;color:var(--text-secondary);font-family:var(--font)}
.emd-remig-cancel:hover{background:var(--bg-secondary)}
.emd-remig-run{display:inline-flex;align-items:center;gap:5px;padding:5px 18px;border-radius:6px;background:#2563eb;color:#fff;border:none;font-size:.78rem;font-weight:600;cursor:pointer;font-family:var(--font);transition:background .12s}
.emd-remig-run:hover{background:#1d4ed8}
.emd-remig-run:disabled{opacity:.55;cursor:not-allowed}
.err-btn-text{font-weight:700;font-size:.73rem}
.err-btn-divider{width:1px;height:11px;background:rgba(239,68,68,.25);flex-shrink:0;margin:0 1px}
.err-btn-action{font-size:.68rem;opacity:.75}
/* ── 처리행 소스→타겟 ── */
.rows-src{color:var(--text-tertiary);font-size:.77rem}
.rows-tgt{color:var(--text-primary);font-weight:500;font-size:.77rem}
.rows-tgt.mismatch{color:#ef4444 !important;font-weight:700 !important}
.row-counts{display:flex;align-items:center;gap:3px}
.spin{animation:spin .9s linear infinite}
.rf-enter-active,.rf-leave-active{transition:all .18s}
.rf-enter-from,.rf-leave-to{opacity:0;transform:translateY(-3px)}

/* ── 오류 행 ── */
.err-row{grid-column:1/-1;padding:8px 12px;background:rgba(239,68,68,.06);border:0.5px solid rgba(239,68,68,.18);border-radius:7px;font-size:.73rem;color:#b91c1c;word-break:break-all;margin-top:3px;display:flex;align-items:flex-start;gap:10px}
.err-msg{flex:1;line-height:1.5}
.err-remig-btn{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:5px;background:#2563eb;color:#fff;border:none;font-size:.7rem;font-weight:600;cursor:pointer;white-space:nowrap;flex-shrink:0;transition:background .12s}
.err-remig-btn:hover{background:#1d4ed8}
.obj-remig{background:#7c3aed}.obj-remig:hover{background:#6d28d9}

/* ── 재이관 모달 ── */
.remig-modal{grid-column:1/-1;border:0.5px solid rgba(37,99,235,.2);border-radius:10px;background:var(--bg-primary);overflow:hidden;margin-top:4px;box-shadow:0 4px 20px rgba(0,0,0,.1)}
.remig-header{display:flex;align-items:center;gap:7px;padding:9px 14px;background:rgba(37,99,235,.05);border-bottom:0.5px solid rgba(37,99,235,.12)}
.remig-title{font-size:.8rem;font-weight:600;color:#1d4ed8;flex:1}
.remig-close{border:none;background:none;cursor:pointer;color:var(--text-tertiary);font-size:.82rem;line-height:1;padding:2px 5px;border-radius:4px}
.remig-close:hover{background:var(--bg-secondary)}
.remig-body{padding:12px 14px;display:flex;flex-direction:column;gap:10px}
.remig-error{display:flex;align-items:flex-start;gap:7px;font-size:.72rem;color:#b91c1c;background:rgba(239,68,68,.05);border:0.5px solid rgba(239,68,68,.15);border-radius:6px;padding:7px 10px;word-break:break-all;line-height:1.5}
.remig-section-label{font-size:.67rem;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.06em}
.remig-opts{display:flex;flex-direction:column;gap:5px}
.remig-opt{display:flex;align-items:flex-start;gap:9px;padding:9px 11px;border-radius:8px;border:0.5px solid var(--border-light);cursor:pointer;transition:all .12s;background:var(--bg-secondary)}
.remig-opt.active{border-color:#2563eb;background:rgba(37,99,235,.05)}
.remig-opt input{flex-shrink:0;margin-top:2px;accent-color:#2563eb}
.remig-opt-body{display:flex;flex-direction:column;gap:2px}
.remig-opt-title{font-size:.8rem;font-weight:600;color:var(--text-primary)}
.remig-opt.active .remig-opt-title{color:#1d4ed8}
.remig-opt-desc{font-size:.7rem;color:var(--text-tertiary);line-height:1.4}
.remig-footer{display:flex;justify-content:flex-end;gap:7px;padding:10px 14px;border-top:0.5px solid var(--border-light)}
.remig-cancel{padding:5px 14px;border-radius:6px;border:0.5px solid var(--border-mid);background:transparent;cursor:pointer;font-size:.78rem;color:var(--text-secondary);font-family:var(--font)}
.remig-cancel:hover{background:var(--bg-secondary)}
.remig-run{display:inline-flex;align-items:center;gap:5px;padding:5px 16px;border-radius:6px;background:#2563eb;color:#fff;border:none;font-size:.78rem;font-weight:600;cursor:pointer;transition:background .12s;font-family:var(--font)}
.remig-run:hover{background:#1d4ed8}
.remig-run:disabled{opacity:.55;cursor:not-allowed}
.spin-sm{width:10px;height:10px;border:2px solid rgba(255,255,255,.4);border-top-color:#fff;border-radius:50%;animation:spin .8s linear infinite;flex-shrink:0}
.remig-hist-list{display:flex;flex-direction:column;gap:3px;max-height:100px;overflow-y:auto;border:0.5px solid var(--border-light);border-radius:6px;padding:4px}
.remig-hist-row{display:flex;align-items:flex-start;gap:6px;font-size:.69rem;padding:3px 5px;border-radius:4px}
.remig-hist-row:nth-child(odd){background:var(--bg-secondary)}
.remig-hist-num{font-weight:700;color:#2563eb;flex-shrink:0;min-width:18px}
.remig-hist-ts{color:var(--text-tertiary);flex-shrink:0;white-space:nowrap}
.remig-hist-err{color:#b91c1c;word-break:break-all;line-height:1.4}
.remig-job-opts{display:flex;align-items:center;gap:8px;padding:7px 10px;background:rgba(37,99,235,.05);border:0.5px solid rgba(37,99,235,.15);border-radius:6px}
.remig-job-opt-lbl{font-size:.7rem;font-weight:600;color:var(--text-tertiary);white-space:nowrap}
.remig-job-opt-val{font-size:.75rem;color:#1d4ed8;font-weight:500}
</style>
