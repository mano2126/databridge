<template>
  <div class="jm">

    <!-- v90.15: DB 접속 패널 (미연결 + 활성 Job 도 없을 때만) -->
    <ConnectPanel v-if="!isEffectivelyConnected" @connected="onConnected" />

    <!-- DB 연결 정보 헤더 (연결 후) -->
    <PageHeader v-else :show-db="true" :src-db="effectiveSrcDb" :tgt-db="effectiveTgtDb" />

    <!-- ── 헤더 ── -->
    <div class="jm-header">
      <div class="jm-title-wrap">
        <div class="page-title">이관 작업 모니터</div>
        <div class="page-desc">테이블 · 오브젝트 별 실시간 진행 상황</div>
      </div>
      <div class="jm-controls">
        <!-- 커스텀 작업 선택 드롭다운 -->
        <div class="job-picker">
          <!-- 트리거 버튼 -->
          <div class="job-picker-btn" @click="jobPickerOpen=!jobPickerOpen">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px;opacity:.5;flex-shrink:0">
              <rect x="1" y="1" width="12" height="12" rx="2"/>
              <line x1="4" y1="5" x2="10" y2="5"/><line x1="4" y1="7" x2="8" y2="7"/>
            </svg>
            <template v-if="job">
              <span class="jp-btn-status" :class="job.status"></span>
              <span class="jp-btn-name">{{ job.name }}</span>
              <span class="jp-btn-meta">{{ (job.src_database||job.src_db) }} → {{ (job.tgt_database||job.tgt_db) }}</span>
            </template>
            <template v-else>
              <span class="jp-btn-placeholder">— 작업 선택 —</span>
            </template>
            <svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5" style="width:9px;height:9px;margin-left:auto;flex-shrink:0;opacity:.4">
              <polyline points="2,3.5 5,6.5 8,3.5"/>
            </svg>
          </div>

          <!-- 드롭다운 목록 -->
          <div v-if="jobPickerOpen" class="job-picker-list">
            <!-- 정렬 헤더 -->
            <div class="jp-sort-bar">
              <span class="jp-sort-label">정렬</span>
              <button class="jp-sort-btn" :class="{on: jpSortKey==='created_at'}"
                      @click.stop="toggleJpSort('created_at')">
                날짜{{ jpSortKey==='created_at' ? (jpSortDir==='desc'?'↓':'↑') : '' }}
              </button>
              <button class="jp-sort-btn" :class="{on: jpSortKey==='status'}"
                      @click.stop="toggleJpSort('status')">
                상태{{ jpSortKey==='status' ? (jpSortDir==='asc'?'↓':'↑') : '' }}
              </button>
              <button class="jp-sort-btn" :class="{on: jpSortKey==='rows_processed'}"
                      @click.stop="toggleJpSort('rows_processed')">
                건수{{ jpSortKey==='rows_processed' ? (jpSortDir==='desc'?'↓':'↑') : '' }}
              </button>
              <button class="jp-sort-btn" :class="{on: jpSortKey==='name'}"
                      @click.stop="toggleJpSort('name')">
                이름{{ jpSortKey==='name' ? (jpSortDir==='asc'?'↓':'↑') : '' }}
              </button>
            </div>
            <div v-if="!jobs.length" class="jp-empty">작업 없음</div>
            <div v-for="j in sortedJobs" :key="j.id"
                 class="jp-item" :class="{active: selectedJobId===j.id}"
                 @click="selectedJobId=j.id; onJobChange(); jobPickerOpen=false">
              <!-- 상태 도트 + 이름 -->
              <div class="jp-row1">
                <span class="jp-status-dot" :class="j.status"></span>
                <span class="jp-name">{{ j.name }}</span>
                <span class="jp-badge" :class="j.status">{{ statusLabel(j.status) }}</span>
              </div>
              <!-- DB 경로 + 날짜 -->
              <div class="jp-row2">
                <span class="jp-db">
                  <span class="jp-db-src">{{ (j.src_db||'').toUpperCase() }}</span>
                  {{ j.src_database||j.src_db }}
                  <span style="opacity:.4">→</span>
                  <span class="jp-db-tgt">{{ (j.tgt_db||'').toUpperCase() }}</span>
                  {{ j.tgt_database||j.tgt_db }}
                </span>
                <span class="jp-date">{{ fmtDateShort(j.created_at) }}</span>
              </div>
              <!-- 테이블 진행 + rows -->
              <div class="jp-row3">
                <span class="jp-prog-wrap">
                  <span class="jp-prog-bar">
                    <span class="jp-prog-fill" :style="{width:(j.progress||0)+'%'}"></span>
                  </span>
                  <span class="jp-prog-txt">{{ (j.progress||0).toFixed(0) }}%</span>
                </span>
                <span class="jp-tbl">테이블 {{ j.table_done||0 }}/{{ j.table_total||0 }}</span>
                <span class="jp-rows">{{ fmtRowsShort(j.rows_processed||0) }} rows</span>
                <span v-if="j.rows_error>0" class="jp-err">오류 {{ j.rows_error }}</span>
              </div>
            </div>
          </div>
        </div>
        <button class="ctrl-btn refresh-btn" :class="{spinning: polling}" @click="refresh" title="새로고침">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M12 3A5.5 5.5 0 1 1 7 1.5"/><polyline points="8,1 12,1 12,4"/>
          </svg>
          <span style="font-size:.72rem;font-weight:600;margin-left:3px">새로고침</span>
        </button>
        <!-- v10 #22: 실시간 리소스 모니터 토글 -->
        <!-- v90.62: 모니터 글자 옆 라이브 점멸 인디케이터 (폴링 활성 시 ● 깜빡임) -->
        <button class="ctrl-btn monitor-btn" :class="{active: monitorStore.visible, polling: monitorStore.isPolling}"
                @click="monitorStore.toggle()"
                :title="monitorStore.visible ? '모니터 닫기' : (monitorStore.isPolling ? '실시간 리소스 모니터 열기 (라이브 갱신 중)' : '실시간 리소스 모니터 열기')">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
            <rect x="1.5" y="2.5" width="11" height="8" rx="1"/>
            <line x1="1.5" y1="8" x2="12.5" y2="8"/>
            <polyline points="3,6.5 5,4.5 7,6 9,3.5 11,5"/>
          </svg>
          <span style="font-size:.72rem;font-weight:600;margin-left:3px">모니터</span>
          <!-- v90.62: 폴링 활성 시 점멸하는 라이브 점 (visible 무관) -->
          <span v-if="monitorStore.isPolling" class="monitor-live-dot" aria-hidden="true"></span>
          <span v-if="monitorStore.totalAlerts > 0"
                class="monitor-badge" :class="monitorStore.criticalAlerts.length ? 'crit' : 'warn'">
            {{ monitorStore.totalAlerts }}
          </span>
        </button>
        <button class="ctrl-btn clear-btn" @click="clearScreen" title="화면 초기화">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M2 2l10 10M12 2L2 12"/>
          </svg>
          <span style="font-size:.72rem;font-weight:600;margin-left:3px">Clear</span>
        </button>
        <!-- v9 패치 #26: 이관 리포트 (완료 Job만) -->
        <button v-if="job && ['completed','done','error','aborted'].includes(job.status)"
                class="ctrl-btn report-btn"
                @click="openReport"
                title="이관 완료 리포트를 새 창으로 열기">
          <span style="font-size:.9rem">📄</span>
          <span style="font-size:.72rem;font-weight:600;margin-left:3px">리포트</span>
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

      <!-- ════════════════════════════════════════════════════════════ -->
      <!-- v95_p91_compact (2026-05-08 본부장님 본질 처방):                -->
      <!-- "위 카드 줄이고 진행 중인 리스트 더 크게"                       -->
      <!--                                                                  -->
      <!-- 상단 카드:                                                       -->
      <!--   - 펼침 모드 (기본): 기존 5개 카드 그대로                        -->
      <!--   - 접힘 모드 (compact): 진행 중인 단계 + 진행률만 깜빡거림       -->
      <!--   - 토글 버튼으로 전환                                            -->
      <!-- ════════════════════════════════════════════════════════════ -->
      
      <!-- 컴팩트 진행 바 (접힘 모드에서만 표시) -->
      <div v-if="!kpiExpanded" class="kpi-compact-bar">
        <button class="kpi-toggle-btn" @click="kpiExpanded = true"
                title="상세 보기 (펼치기)">
          ▼
        </button>
        <span class="kpi-compact-status" :class="'compact-'+job.status">
          <span class="kpi-compact-dot" :class="job.status"></span>
          {{ statusLabel(job.status) }}
        </span>
        
        <!-- 현재 진행 중인 단계 (깜빡임) -->
        <span v-if="!isCdc && job.status==='running' && currentPhaseLabel"
              class="kpi-compact-phase">
          <span class="kpi-compact-blink">⟳</span>
          {{ currentPhaseLabel }}
        </span>
        
        <!-- ════════════════════════════════════════════════════════════
             v95_p107 hotfix_029 (2026-05-11 본부장님 본질 처방):
               접힌 모드에서도 테이블/객체 진행 둘 다 분리 표시
             
             본부장님 본질 지적:
               "테이블 진행과 오브젝트 진행 두개를 보여 줘야 될 것 같아.
                테이블이 100%면 조그맣게 100%로 보여주고
                오브젝트 진행 상태를 잘 보여줘."
             
             처방: 펼친 모드의 effectiveProgress + objectsOverallProgress 를
                   접힌 모드에서도 인라인으로 분리 표시.
             ════════════════════════════════════════════════════════════ -->
        
        <!-- 테이블 진행 (작게) -->
        <span class="kpi-compact-progress kpi-compact-progress-tbl">
          <span class="kpi-compact-mini-label">테이블</span>
          <span class="kpi-compact-mini-count">{{ job.table_done||0 }}/{{ job.table_total||0 }}</span>
          <span class="kpi-compact-mini-pct">{{ effectiveProgress }}%</span>
        </span>
        
        <!-- 객체 진행 (객체 단계 진행 중이면 강조) -->
        <span v-if="objectsOverallProgress" class="kpi-compact-progress kpi-compact-progress-obj"
              :class="{ 'obj-active': isObjectPhaseRunning, 'obj-failed': objectsOverallProgress.failed > 0 }">
          <span class="kpi-compact-mini-label">객체</span>
          <span class="kpi-compact-mini-count">{{ objectsOverallProgress.done }}/{{ objectsOverallProgress.total }}</span>
          <span class="kpi-compact-pct">{{ objectsOverallProgress.pct }}%</span>
          <div class="kpi-compact-bar-track">
            <div class="kpi-compact-bar-fill"
                 :class="{
                   'bar-failed': objectsOverallProgress.failed > 0,
                   'bar-done': objectsOverallProgress.done === objectsOverallProgress.total && objectsOverallProgress.failed === 0
                 }"
                 :style="`width:${objectsOverallProgress.pct}%`"></div>
          </div>
        </span>
        
        <!-- 객체 변환 단계 없으면 (테이블만 작업) 기존 통합 진행률 fallback -->
        <span v-else class="kpi-compact-progress">
          <span class="kpi-compact-pct">{{ totalProgressPct }}%</span>
          <div class="kpi-compact-bar-track">
            <div class="kpi-compact-bar-fill" :style="`width:${totalProgressPct}%`"></div>
          </div>
        </span>
        
        <!-- 현재 진행 중인 객체 타입 (있을 때만) -->
        <span v-if="currentObjectStatus" class="kpi-compact-obj">
          {{ currentObjectStatus }}
        </span>
        
        <!-- 오류 (있을 때만) -->
        <span v-if="hasAnyError" class="kpi-compact-err"
              @click="$emit('open-errors') || scrollToErrors()">
          ⚠ 오류 {{ errorTotalCount }}건
        </span>
      </div>
      
      <!-- ── KPI 카드 (펼침 모드에서만 표시) ── -->
      <div v-if="kpiExpanded" class="kpi-section-wrapper">
        <button class="kpi-toggle-btn kpi-toggle-collapse" @click="kpiExpanded = false"
                title="접기 (간단히 보기)">
          ▲ 접기
        </button>
        <div class="kpi-grid">
        <div class="kpi-card" :class="'kpi-'+job.status">
          <div class="kpi-header">
            <span class="kpi-label">상태</span>
            <span class="kpi-dot" :class="job.status"></span>
          </div>
          <!-- v92p9 (2026-04-30): MSSQL→MYSQL 줄 제거 (헤더에 이미 표시됨) -->
          <!-- 단계별 색깔 버튼 (진행중/완료, CDC는 표시 안함) -->
          <div v-if="!isCdc && (job.status==='running'||job.status==='completed')" class="phase-steps">
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
            <!-- v92p12: 4. AI DBA 권고 적용 -->
            <div v-if="hasAdvisorDecisions" class="phase-step"
                 :class="phaseStepClass('ADVISOR_APPLY')">
              <span class="ps-icon">{{ phaseStepIcon('ADVISOR_APPLY') }}</span>
              <span class="ps-label">
                🤖 AI 권고 적용
                <span v-if="advisorApplyProgress" class="ps-sub">
                  ({{ advisorApplyProgress.done }}/{{ advisorApplyProgress.total }}<span
                    v-if="advisorApplyProgress.failed > 0"
                    style="color:#dc2626;font-weight:700"> · {{ advisorApplyProgress.failed }} 실패</span>)
                </span>
              </span>
            </div>
            <!-- 5. FK/트리거 복원 -->
            <div class="phase-step"
                 :class="phaseStepClass('FK_RESTORE')">
              <span class="ps-icon">{{ phaseStepIcon('FK_RESTORE') }}</span>
              <span class="ps-label">FK·트리거 복원</span>
            </div>
          </div>
          <!-- v92p6: FK_DISABLE 단계 60초 이상 정체 시 경고 -->
          <div v-if="!isCdc && job.status==='running' && job.phase==='FK_DISABLE' && phaseStuckSec >= 60"
               class="phase-stuck-warn">
            <span class="psw-ico">⚠</span>
            <span class="psw-msg">
              FK 비활성화 단계 {{ phaseStuckSec }}초 진행 중 — 타겟 DB 응답 지연/락 가능성
            </span>
            <button class="psw-btn" @click="cancelStuckJob">⏹ 중단</button>
          </div>
          <!-- CDC 단순 상태 표시 -->
          <div v-if="isCdc && (job.status==='running'||job.status==='completed')" class="cdc-phase-simple">
            <span class="cdc-phase-ico">↻</span>
            <span class="cdc-phase-txt">변경분 이관 {{ job.status==='completed' ? '완료' : '진행 중' }}</span>
          </div>
          <!-- v92p9: 진행중 라벨 (깜박임) + 객체 카운트 인라인 -->
          <div v-else-if="!isCdc" class="kpi-status-row">
            <span class="kpi-value status-text" :class="[job.status, {'status-blink': job.status==='running'}]">
              {{ statusLabel(job.status) }}
            </span>
            <span v-if="objectsProgress" class="kpi-obj-inline"
                  :class="{fail: objectsProgress.failed > 0,
                           done: objectsProgress.done === objectsProgress.total}">
              <span class="koi-icon">ƒ</span>
              <span class="koi-val">{{ objectsProgress.done }} / {{ objectsProgress.total }}</span>
              <span v-if="objectsProgress.failed > 0" class="koi-fail">({{ objectsProgress.failed }} 오류)</span>
            </span>
            <!-- v92p13 (2026-04-30): 테이블 카운트를 진행중 옆으로 이동 (UI 줄 수 절약) -->
            <span v-if="!isCdc && job.table_total > 0" class="kpi-tbl-inline"
                  :class="{done: (job.table_done||0) === job.table_total}"
                  title="이관 완료 테이블 / 전체 테이블">
              <span class="kti-icon">⊞</span>
              <span class="kti-val">{{ job.table_done||0 }} / {{ job.table_total }}</span>
            </span>
            <!-- v92p11 (2026-04-30): AI 자동이관 ON/OFF 배지
                 v92p15 (2026-04-30): 클릭으로 실시간 토글 가능 -->
            <button class="kpi-ai-toggle" :class="{ on: job.ai_auto_retry }"
                  type="button"
                  :disabled="aiToggleBusy || !['running','paused'].includes(job.status)"
                  @click="toggleAiAutoRetry"
                  :title="job.ai_auto_retry
                    ? `AI 자동 재이관 활성 — 객체 실패 시 자동 재시도 (최대 ${job.ai_retry_count||2}회). 클릭하여 OFF`
                    : `AI 자동 재이관 비활성 — 실패 시 멈춤 (수동 재이관 필요). 클릭하여 ON`">
              <span class="kat-ico">🤖</span>
              <span class="kat-txt">자동이관 {{ job.ai_auto_retry ? 'ON' : 'OFF' }}</span>
              <span v-if="aiToggleBusy" class="kat-spinner">⟳</span>
            </button>
          </div>
          <div v-else class="kpi-value status-text" :class="job.status">{{ statusLabel(job.status) }}</div>
        </div>

        <div class="kpi-card kpi-prog-card">
          <div class="kpi-header">
            <span class="kpi-label">전체 진행</span>
            <span class="kpi-pct-badge">{{ effectiveProgress }}%</span>
          </div>
          <div class="kpi-prog-track"><div class="kpi-prog-fill" :style="{width:effectiveProgress+'%'}"></div></div>
          <div class="kpi-sub">테이블 {{ job.table_done||0 }} / {{ job.table_total||0 }} 완료</div>

          <!-- v95_p47 (2026-05-05 본부장님): 객체 진행바 분리 + 한 줄 표시 -->
          <template v-if="objectsOverallProgress">
            <div class="kpi-obj-divider"></div>
            <!-- 객체 진행바 (테이블 진행바와 시각 구분) -->
            <div class="kpi-obj-prog-header">
              <span class="kpi-obj-prog-label">객체 변환</span>
              <span class="kpi-obj-prog-badge">{{ objectsOverallProgress.pct }}%</span>
            </div>
            <div class="kpi-obj-prog-track">
              <div class="kpi-obj-prog-fill"
                   :class="{
                     'obj-prog-failed': objectsOverallProgress.failed > 0,
                     'obj-prog-done': objectsOverallProgress.done === objectsOverallProgress.total
                   }"
                   :style="{width: objectsOverallProgress.pct + '%'}"></div>
            </div>
            <!-- 4개 카운트 한 줄 (FN/SP/VW/TR) -->
            <div class="kpi-obj-row kpi-obj-row-compact">
              <span v-if="objectsProgress.function.total > 0" class="kpi-obj-item kpi-obj-item-compact"
                    :class="{ 'obj-running': objectsProgress.function.running > 0,
                              'obj-done': objectsProgress.function.done === objectsProgress.function.total,
                              'obj-failed': objectsProgress.function.failed > 0 }"
                    :title="`Function: ${objectsProgress.function.done}/${objectsProgress.function.total} 완료`">
                <span class="kpi-obj-icon">ƒ</span>
                <span class="kpi-obj-text">FN {{ objectsProgress.function.done }}/{{ objectsProgress.function.total }}</span>
                <span v-if="objectsProgress.function.failed > 0" class="kpi-obj-fail-badge">{{ objectsProgress.function.failed }}</span>
              </span>
              <span v-if="objectsProgress.procedure.total > 0" class="kpi-obj-item kpi-obj-item-compact"
                    :class="{ 'obj-running': objectsProgress.procedure.running > 0,
                              'obj-done': objectsProgress.procedure.done === objectsProgress.procedure.total,
                              'obj-failed': objectsProgress.procedure.failed > 0 }"
                    :title="`Procedure: ${objectsProgress.procedure.done}/${objectsProgress.procedure.total} 완료`">
                <span class="kpi-obj-icon">⚙</span>
                <span class="kpi-obj-text">SP {{ objectsProgress.procedure.done }}/{{ objectsProgress.procedure.total }}</span>
                <span v-if="objectsProgress.procedure.failed > 0" class="kpi-obj-fail-badge">{{ objectsProgress.procedure.failed }}</span>
              </span>
              <span v-if="objectsProgress.view.total > 0" class="kpi-obj-item kpi-obj-item-compact"
                    :class="{ 'obj-running': objectsProgress.view.running > 0,
                              'obj-done': objectsProgress.view.done === objectsProgress.view.total,
                              'obj-failed': objectsProgress.view.failed > 0 }"
                    :title="`View: ${objectsProgress.view.done}/${objectsProgress.view.total} 완료`">
                <span class="kpi-obj-icon">👁</span>
                <span class="kpi-obj-text">VW {{ objectsProgress.view.done }}/{{ objectsProgress.view.total }}</span>
                <span v-if="objectsProgress.view.failed > 0" class="kpi-obj-fail-badge">{{ objectsProgress.view.failed }}</span>
              </span>
              <span v-if="objectsProgress.trigger.total > 0" class="kpi-obj-item kpi-obj-item-compact"
                    :class="{ 'obj-running': objectsProgress.trigger.running > 0,
                              'obj-done': objectsProgress.trigger.done === objectsProgress.trigger.total,
                              'obj-failed': objectsProgress.trigger.failed > 0 }"
                    :title="`Trigger: ${objectsProgress.trigger.done}/${objectsProgress.trigger.total} 완료`">
                <span class="kpi-obj-icon">⚡</span>
                <span class="kpi-obj-text">TR {{ objectsProgress.trigger.done }}/{{ objectsProgress.trigger.total }}</span>
                <span v-if="objectsProgress.trigger.failed > 0" class="kpi-obj-fail-badge">{{ objectsProgress.trigger.failed }}</span>
              </span>
            </div>
          </template>
          <!-- ── ETA 블록 ── -->
          <div v-if="job.status==='running'" class="eta-block">
            <div class="eta-divider"></div>
            <template v-if="eta.remains">
              <!-- v10 #26: 현재 작업 + 전체 작업 잔여시간 나란히 표시 -->
              <div class="eta-block-row eta-dual-row">
                <div class="eta-dual-col">
                  <span class="eta-block-label">현재 작업 남은 시간</span>
                  <span class="eta-block-remain current-task">
                    {{ currentTaskEta || '—' }}
                  </span>
                  <span v-if="currentTaskName" class="current-task-name" :title="currentTaskName">
                    [{{ currentTaskName }}]
                  </span>
                </div>
                <div class="eta-dual-sep"></div>
                <div class="eta-dual-col">
                  <span class="eta-block-label">전체 이관 예상 남은 시간</span>
                  <span class="eta-block-remain">{{ eta.remains }}</span>
                  <span v-if="eta.cardClass==='eta-soon'" class="eta-soon-badge">곧 완료!</span>
                </div>
              </div>
              <div class="eta-block-row">
                <span class="eta-block-label">완료 예상</span>
                <span class="eta-block-time">🕐 {{ eta.finishAt }}</span>
              </div>
              <div v-if="eta.accuracy" class="eta-block-hint">{{ eta.accuracy }}</div>
            </template>
            <template v-else>
              <div class="eta-block-row">
                <span class="eta-block-label">예상 종료</span>
                <span class="eta-block-calc">속도 측정 중...</span>
              </div>
            </template>
          </div>
          <div v-else-if="job.status==='completed'" class="eta-block">
            <div class="eta-divider"></div>
            <div class="eta-block-row">
              <span class="eta-block-label">완료 시각</span>
              <span class="eta-block-time">✓ {{ fmtTime(job.finished_at) }}</span>
            </div>
          </div>
        </div>

        <div class="kpi-card">
          <div class="kpi-header"><span class="kpi-label">처리 행</span></div>
          <div class="kpi-value">{{ fmtNum(rowsProcessedLive) }}<span class="kpi-unit"> rows</span></div>
          <div class="kpi-sub">전체 {{ rowsTotalLive ? fmtNum(rowsTotalLive) : '측정 중' }}</div>
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
          <!-- v90.66: 행 단위 vs 객체 단위 구분 명확화 -->
          <!-- 큰 숫자는 더 의미있는 쪽 (객체 오류가 있으면 객체 수, 없으면 행 오류) -->
          <div v-if="errItems.length > 0" class="kpi-value" :class="{'err-val': hasAnyError}">
            {{ errItems.length }}<span class="kpi-unit"> 항목</span>
          </div>
          <div v-else class="kpi-value" :class="{'err-val': hasAnyError}">
            {{ fmtNum(job.rows_error||0) }}<span class="kpi-unit"> 행</span>
          </div>
          <div class="kpi-sub">
            <button v-if="errItems.length > 0" class="err-open-btn" @click="openErrModal">
              <span class="err-btn-dot"></span>
              <span class="err-btn-text">
                <!-- v90.66: 보조 정보로 행 오류도 같이 표시 (있을 때만) -->
                <template v-if="(job.rows_error||0) > 0">
                  객체 {{ errItems.length }} · 행 {{ fmtNum(job.rows_error) }}
                </template>
                <template v-else>{{ errItems.length }}개 객체 실패</template>
              </span>
              <span class="err-btn-divider"></span>
              <span class="err-btn-action">상세 보기</span>
              <svg viewBox="0 0 8 8" fill="none" stroke="currentColor" stroke-width="1.5" style="width:8px;height:8px;opacity:.6">
                <polyline points="1.5,3 4,5.5 6.5,3"/>
              </svg>
            </button>
            <span v-else-if="(job.rows_error||0) > 0">테이블 이관 행 오류</span>
            <span v-else>정상</span>
          </div>
        </div>
      </div>
      </div>  <!-- /v95_p91_compact: kpi-section-wrapper 닫기 -->

      <!-- ── 현재 진행 중 ── -->
      <div v-if="job.status==='running'&&job.current_table" class="current-bar">
        <div class="cur-left">
          <span class="live-badge"><span class="live-dot"></span>LIVE</span>
          <span class="cur-name">{{ job.current_table }}</span>
        </div>
        <div class="cur-mid">
          <!-- v92p12: ADVISOR_APPLY 중이면 현재 권고명 표시 -->
          <div v-if="job.phase==='ADVISOR_APPLY' && advisorApplyProgress?.current"
               class="adv-current">{{ advisorApplyProgress.current }}</div>
          <div v-else class="cur-track"><div class="cur-fill" :style="{width:tableProgress+'%'}"></div></div>
        </div>
        <div class="cur-right">
          <!-- v92p12: 권고 적용 중이면 카운트, 그 외엔 % + rows -->
          <template v-if="job.phase==='ADVISOR_APPLY' && advisorApplyProgress">
            <span class="cur-pct">{{ advisorApplyProgress.done }} / {{ advisorApplyProgress.total }}</span>
            <span v-if="advisorApplyProgress.failed > 0" class="cur-rows" style="color:#dc2626">
              {{ advisorApplyProgress.failed }} 실패
            </span>
          </template>
          <template v-else>
            <span class="cur-pct">{{ tableProgress }}%</span>
            <span class="cur-rows">{{ fmtNum(job.current_table_rows_done) }} / {{ fmtNum(job.current_table_rows_total) }} rows</span>
            <!-- v9 패치 #34: 현재 테이블 잔여 시간 -->
            <span v-if="currentTableEta" class="cur-eta" :title="'현재 테이블 완료까지'">
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px;vertical-align:-1px;margin-right:3px"><circle cx="6" cy="6" r="5"/><polyline points="6,3 6,6 8,7"/></svg>
              남은 {{ currentTableEta }}
            </span>
          </template>
        </div>
      </div>

      <!-- v90.14: Adaptive Resource Panel 은 FloatingMonitor 로 이동됨 -->


      <!-- ── 툴바 ── -->
      <div class="toolbar">
        <!-- 일괄 재이관 바 -->
        <transition name="bulk-bar">
          <div v-if="bulkSelected.size > 0" class="bulk-bar">
            <label class="bulk-chk-all" @click.stop>
              <input type="checkbox" :checked="isBulkAllSelected" @change="toggleBulkAll"/>
              <span class="bulk-chk-label">{{ bulkSelected.size }}개 선택됨</span>
            </label>
            <button class="bulk-run-btn" @click="openBulkModal" :disabled="bulkRunning">
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" style="width:10px;height:10px">
                <path d="M10 2A4.5 4.5 0 1 1 5.5 1"/><polyline points="7,0 10,2 8,5"/>
              </svg>
              일괄 재이관
            </button>
            <button class="bulk-clear-btn" @click="bulkSelected.clear(); bulkSelected = new Set()">✕ 선택 해제</button>
          </div>
        </transition>
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
      <div class="item-table-outer">
        <!-- v10: 빠른 점프 툴바 (긴 목록 드래그 해소) -->
        <div v-if="filteredItems.length > 20" class="jump-bar">
          <div class="jump-left">
            <span class="jump-total">{{ filteredItems.length.toLocaleString() }}건</span>
            <div class="jump-scroll-indicator" :title="`${Math.round(scrollProgress)}% 위치`">
              <div class="jsi-fill" :style="{width: scrollProgress+'%'}"></div>
            </div>
          </div>
          <div class="jump-center">
            <button class="jump-btn" @click="scrollItemsTop" title="맨 위로 (Alt+Home)">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" style="width:11px;height:11px"><polyline points="4,10 8,6 12,10"/><line x1="4" y1="3" x2="12" y2="3"/></svg>
              <span>맨 위</span>
            </button>
            <button class="jump-btn" @click="scrollToNextStatus('error')" :disabled="!hasStatus('error')" title="다음 오류 항목 (Alt+E)">
              <span class="jump-dot err"></span>
              <span>오류 {{ countByStatus('error') }}</span>
            </button>
            <button class="jump-btn" @click="scrollToNextStatus('running')" :disabled="!hasStatus('running')" title="다음 실행중 (Alt+R)">
              <span class="jump-dot run"></span>
              <span>실행중 {{ countByStatus('running') }}</span>
            </button>
            <button class="jump-btn" @click="scrollToNextStatus('pending')" :disabled="!hasStatus('pending')" title="다음 대기">
              <span class="jump-dot pen"></span>
              <span>대기 {{ countByStatus('pending') }}</span>
            </button>
            <button class="jump-btn" @click="scrollItemsBottom" title="맨 아래로 (Alt+End)">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" style="width:11px;height:11px"><polyline points="4,6 8,10 12,6"/><line x1="4" y1="13" x2="12" y2="13"/></svg>
              <span>맨 아래</span>
            </button>
          </div>
          <div class="jump-right">
            <input type="number" v-model.number="jumpToRow" min="1" :max="filteredItems.length"
                   placeholder="N"
                   class="jump-row-input"
                   @keyup.enter="scrollToRow(jumpToRow)"
                   title="행 번호로 이동 (Enter)"/>
            <button class="jump-btn small" @click="scrollToRow(jumpToRow)" :disabled="!jumpToRow" title="해당 행으로 이동">이동</button>
          </div>
        </div>

        <div class="item-table" ref="itemTableRef">
        <div class="item-head">
          <span class="ic-name ih-sort" style="gap:6px" @click="setSort('name')">
            <input type="checkbox" class="bulk-hd-chk" style="flex-shrink:0"
              :checked="isBulkAllErrSelected"
              @change.stop="toggleBulkAllErr"
              @click.stop/>
            이름<span class="sort-arrow">{{ sortKey==='name'?(sortDir==='asc'?'↑':'↓'):'' }}</span>
          </span>
          <span class="ic-type">유형</span>
          <span class="ic-prog">진행</span>
          <span class="ic-pct ih-sort" @click="setSort('progress')">%<span class="sort-arrow">{{ sortKey==='progress'?(sortDir==='asc'?'↑':'↓'):'' }}</span></span>
          <span class="ic-rowcnt ih-sort" @click="setSort('rows')">건수<span class="sort-arrow">{{ sortKey==='rows'?(sortDir==='asc'?'↑':'↓'):'' }}</span></span>
          <span class="ic-time ih-sort" @click="setSort('finished_at')">완료 시각<span class="sort-arrow">{{ sortKey==='finished_at'?(sortDir==='asc'?'↑':'↓'):'' }}</span></span>
          <span class="ic-elapsed">경과</span>
          <span class="ic-eta-col">≈ 잔여시간</span>
          <span class="ic-stat ih-sort" @click="setSort('status')">상태<span class="sort-arrow">{{ sortKey==='status'?(sortDir==='asc'?'↑':'↓'):'' }}</span></span>
        </div>

        <div v-if="filteredItems.length===0" class="no-items">검색 결과가 없습니다</div>

        <transition-group name="rf" tag="div">
          <div v-for="item in filteredItems" :key="item.name"
               class="item-row" :class="item.status" @click="toggleDetail(item.name)">
            <span class="ic-name" style="gap:6px">
              <input v-if="item.status==='error'" type="checkbox"
                class="bulk-item-chk" style="flex-shrink:0"
                :checked="bulkSelected.has(item.name)"
                @change.stop="toggleBulkItem(item.name)"
                @click.stop/>
              <span v-else style="width:14px;height:14px;flex-shrink:0;display:inline-block"></span>
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
                  <!-- v9 패치 #24c: 진행건수 → 전체건수 -->
                  <!-- v90.60: 본부장님 환경에서 진행 중에 item_statuses 의 rows_src/tgt 가
                       0 으로 비어 있고 top-level current_table_rows_done 만 갱신되는 케이스 발견.
                       이 행이 바로 그 진행 중 테이블이면 (item.name === job.current_table)
                       top-level 카운터를 fallback 으로 사용해서 사용자에게는 정확한 진행 표시. -->
                  <span class="rows-inline">{{ fmtNum(_displayRowsDone(item)) }}<span class="row-arr">→</span>{{ fmtNum(_displayRowsTotal(item)) }}</span>
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
            <span class="ic-elapsed">
              <!-- v95_p107 hotfix_063: 경과시간 fallback (실패 시 started_at 없으면 retry_duration_s 사용) -->
              <span class="elapsed-badge" :class="elapsedClass(item)">{{ _h063ElapsedDisplay(item) }}</span>
            </span>
            <span class="ic-eta-col">
              <span v-if="item.status==='running' && fmtItemEta(item)" class="item-eta-badge">
                {{ fmtItemEta(item) }}
              </span>
              <span v-else class="muted">—</span>
            </span>
            <span class="ic-stat">
              <span class="stat-pill" :class="[item.status, {'via-ai': item.via_ai_remig && item.status==='done', 'recovered': item.had_error && item.status==='done' && !item.via_ai_remig}]">
                <svg v-if="item.status==='running'" class="spin" viewBox="0 0 12 12">
                  <circle cx="6" cy="6" r="4.5" stroke="currentColor" stroke-width="1.5" fill="none" stroke-dasharray="20" stroke-dashoffset="7"/>
                </svg>
                <!-- v90.67: AI 재이관으로 성공 = 🤖 아이콘 -->
                <svg v-else-if="item.status==='done' && item.via_ai_remig" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
                  <rect x="2.5" y="3.5" width="7" height="6" rx="1"/>
                  <line x1="6" y1="1.5" x2="6" y2="3.5"/>
                  <circle cx="4.5" cy="6.5" r=".7" fill="currentColor"/>
                  <circle cx="7.5" cy="6.5" r=".7" fill="currentColor"/>
                </svg>
                <!-- v90.67: 1차 실패 후 retry 로 성공 = ↻ 아이콘 -->
                <svg v-else-if="item.status==='done' && item.had_error" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8">
                  <path d="M10 2A4.5 4.5 0 1 1 5.5 1"/><polyline points="7,0 10,2 8,5"/>
                </svg>
                <svg v-else-if="item.status==='done'" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2"><polyline points="2,6 4.5,9 10,3"/></svg>
                <svg v-else-if="item.status==='error'" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="3" x2="9" y2="9"/><line x1="9" y1="3" x2="3" y2="9"/></svg>
                <svg v-else viewBox="0 0 12 12" fill="currentColor"><circle cx="6" cy="6" r="2.5"/></svg>
                <!-- v90.67: 라벨 — AI 재이관 / 재시도 후 성공 / 일반 완료 구분 -->
                <!-- v95_p107 hotfix_013: conversion_path 가 있으면 상세 라벨 우선 표시 -->
                <span v-if="conversionPathLbl(item.conversion_path, item.status)"
                      :title="`변환 경로: ${(item.conversion_path||[]).join(' → ')} (${item.attempts || 1}회 시도)`">
                  <span class="stp-process">{{ conversionProcessLbl(item.conversion_path, item.status) }}</span><span v-if="conversionOutcomeCode(item.conversion_path, item.status)" class="stp-outcome" :class="conversionOutcomeCode(item.conversion_path, item.status)">{{ conversionOutcomeLbl(item.conversion_path, item.status) }}</span>
                </span>
                <span v-else-if="item.status==='done' && item.via_ai_remig" :title="`AI 재이관으로 성공 (${item.attempts || 2}회 시도)`">AI 재이관 성공</span>
                <span v-else-if="item.status==='done' && item.had_error" :title="`재시도 후 성공 (${item.attempts || 2}회 시도)`">재시도 성공</span>
                <span v-else>{{ statusLabel(item.status) }}</span>
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
                      <span class="remig-opt-desc">기존 오브젝트 삭제 후 내부 변환 규칙으로 재생성</span>
                    </div>
                  </label>
                  <label class="remig-opt" :class="{active: objRemigMode==='rules'}">
                    <input type="radio" v-model="objRemigMode" value="rules"/>
                    <div class="remig-opt-body">
                      <span class="remig-opt-title">⚙ 규칙 기반 변환</span>
                      <span class="remig-opt-desc">내장 SQL 변환 규칙으로 DDL 재변환 후 재배포 (API 키 불필요)</span>
                    </div>
                  </label>
                  <label class="remig-opt" :class="{active: objRemigMode==='ai'}">
                    <input type="radio" v-model="objRemigMode" value="ai"/>
                    <div class="remig-opt-body">
                      <span class="remig-opt-title">🤖 AI 변환</span>
                      <span class="remig-opt-desc">내부 AI(Gemini 기본)가 오류 분석 후 DDL 변환 및 재생성 (API 키 필요)</span>
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
                      <span class="remig-opt-desc">내부 AI(Gemini 기본)가 오류 분석 후 스키마 변환 및 재이관</span>
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
      </div><!-- /.item-table-outer -->

      <!-- ── 하단 요약 ── -->
      <div class="foot-summary">
        <span class="foot-total">전체 {{ allItems.length }}개</span>
        <span class="foot-sep">|</span>
        <span class="foot-item"><span class="fdot done"></span>완료 {{ countByStatus('done') }}</span>
        <span class="foot-item"><span class="fdot running"></span>진행중 {{ countByStatus('running') }}</span>
        <span class="foot-item"><span class="fdot pending"></span>대기 {{ countByStatus('pending') }}</span>
        <span v-if="countByStatus('error')" class="foot-item err"><span class="fdot error"></span>오류 {{ countByStatus('error') }}</span>
      </div>

      <!-- ── 일괄 재이관 모달 ── -->
      <div v-if="showBulkModal" class="bulk-modal-overlay" @click.self="showBulkModal=false">
        <div class="bulk-modal">
          <!-- 헤더 -->
          <div class="bulk-modal-header">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:13px;height:13px;flex-shrink:0">
              <path d="M12 2A5.5 5.5 0 1 1 6.5 1"/><polyline points="8,0 12,2 10,6"/>
            </svg>
            <span>일괄 재이관 — {{ bulkSelected.size }}개 항목</span>
            <button class="remig-close" @click="showBulkModal=false">✕</button>
          </div>
          <!-- 선택 항목 목록 -->
          <div class="bulk-modal-list">
            <div v-for="name in [...bulkSelected]" :key="name" class="bulk-modal-item">
              <span class="bulk-modal-type-ico">{{ typeIcon(allItems.find(i=>i.name===name)?.type) }}</span>
              <span class="bulk-modal-name">{{ name }}</span>
              <span class="bulk-modal-type">{{ typeLabelShort(allItems.find(i=>i.name===name)?.type) }}</span>
              <button class="bulk-modal-remove" @click="toggleBulkItem(name)">✕</button>
            </div>
          </div>
          <!-- 이관 방식 선택 -->
          <div class="bulk-modal-body">
            <div class="remig-section-label" style="display:flex;align-items:center;gap:8px">
              이관 방식 선택 (전체 적용)
              <span class="bulk-auto-badge">
                ✦ 자동 선택됨
              </span>
            </div>
            <div class="remig-opts">
              <!-- 테이블/오브젝트 공통 옵션 -->
              <label class="remig-opt" :class="{active: bulkMode==='drop_recreate'}">
                <input type="radio" v-model="bulkMode" value="drop_recreate"/>
                <div class="remig-opt-body">
                  <span class="remig-opt-title">🔄 DROP 후 재생성</span>
                  <span class="remig-opt-desc">기존 항목 삭제 후 재생성 (테이블·오브젝트 공통)</span>
                </div>
              </label>
              <label class="remig-opt" :class="{active: bulkMode==='original'}">
                <input type="radio" v-model="bulkMode" value="original"/>
                <div class="remig-opt-body">
                  <span class="remig-opt-title">⚡ 원본 설정 그대로</span>
                  <span class="remig-opt-desc">처음 이관 시 옵션 그대로 재시도 (테이블만)</span>
                </div>
              </label>
              <label class="remig-opt" :class="{active: bulkMode==='rules'}">
                <input type="radio" v-model="bulkMode" value="rules"/>
                <div class="remig-opt-body">
                  <span class="remig-opt-title">⚙ 규칙 기반 변환</span>
                  <span class="remig-opt-desc">내장 SQL 변환 규칙으로 DDL 재변환 (오브젝트만)</span>
                </div>
              </label>
              <label class="remig-opt" :class="{active: bulkMode==='ai'}">
                <input type="radio" v-model="bulkMode" value="ai"/>
                <div class="remig-opt-body">
                  <span class="remig-opt-title">🤖 AI 변환</span>
                  <span class="remig-opt-desc">내부 AI(Gemini 기본)가 오류 분석 후 DDL 변환 및 재생성</span>
                </div>
              </label>
            </div>

            <!-- 진행 상황 -->
            <div v-if="bulkRunning" class="bulk-progress">
              <div class="bulk-prog-bar">
                <div class="bulk-prog-fill" :style="{width: bulkProgress + '%'}"></div>
              </div>
              <div class="bulk-prog-text">
                {{ bulkDoneCount }} / {{ bulkTotal }}개 완료
                <span v-if="bulkCurrentName" class="bulk-cur-name">— {{ bulkCurrentName }}</span>
              </div>
            </div>

            <!-- 결과 요약 -->
            <div v-if="bulkResult.length" class="bulk-result-list">
              <div v-for="r in bulkResult" :key="r.name" class="bulk-result-row" :class="r.ok?'ok':'err'">
                <span class="bulk-result-ico">{{ r.ok ? '✓' : '✗' }}</span>
                <span class="bulk-result-name">{{ r.name }}</span>
                <span class="bulk-result-msg">{{ r.msg }}</span>
              </div>
            </div>
          </div>
          <!-- 푸터 -->
          <div class="remig-footer">
            <button class="remig-cancel" @click="showBulkModal=false" :disabled="bulkRunning">닫기</button>
            <button class="remig-run" @click="doBulkRemig"
              :disabled="bulkRunning || bulkSelected.size===0">
              <span v-if="bulkRunning" class="spin-sm"></span>
              {{ bulkRunning ? '처리 중...' : '일괄 재이관 실행' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 오류 상세 모달 -->
      <!-- v95_p107 hotfix_046: 오류 상세 모달 → 플로팅 윈도우 (배경 dim 제거, 바깥 클릭 안 닫힘, 드래그+최소화) -->
      <div v-if="showErrModal" class="emd-float-root" :class="{'emd-float-min': errMinimized}">
        <div class="emd-float-card" :style="errFloatStyle">
          <!-- 헤더 -->
          <div class="emd-float-header" @pointerdown="startErrDrag">
            <span style="font-size:.88rem;font-weight:600;color:var(--text-primary);flex:1">
  오류 상세
  <span v-if="errItems.length"> — {{ errItems.length }}개 항목</span>
  <span v-if="errItems.length > 0 && job.rows_error > 0"> / 실패 행 {{ fmtNum(job.rows_error||0) }}건</span>
</span>
            <button @click="errMinimized=!errMinimized" :title="errMinimized?'펼치기':'접기'" style="border:none;background:none;cursor:pointer;font-size:1rem;color:var(--text-tertiary);padding:2px 8px;line-height:1">{{ errMinimized ? '□' : '─' }}</button>
            <button @click="showErrModal=false" style="border:none;background:none;cursor:pointer;font-size:1rem;color:var(--text-tertiary);padding:2px 8px">✕</button>
          </div>
          <!-- 요약 바 -->
          <div style="display:flex;gap:0;border-bottom:0.5px solid var(--border-light);background:var(--bg-secondary)">
            <div style="flex:1;text-align:center;padding:10px 6px">
              <div style="font-size:1.1rem;font-weight:700;color:var(--text-primary)">{{ errItems.filter(i=>i.status==='error').length }}</div>
              <div style="font-size:.68rem;color:var(--text-tertiary);margin-top:2px">항목 오류</div>
            </div>
            <div style="flex:1;text-align:center;padding:10px 6px;border-left:0.5px solid var(--border-light)">
              <div style="font-size:1.1rem;font-weight:700;color:var(--text-primary)">{{ errItems.filter(i=>i.batch_errors?.length||i.batch_error_rows>0).length }}</div>
              <div style="font-size:.68rem;color:var(--text-tertiary);margin-top:2px">배치 오류 테이블</div>
            </div>
            <div style="flex:1;text-align:center;padding:10px 6px;border-left:0.5px solid var(--border-light)">
              <div style="font-size:1.1rem;font-weight:700;color:#ef4444">{{ fmtNum(job.rows_error||0) }}</div>
              <div style="font-size:.68rem;color:var(--text-tertiary);margin-top:2px">실패 행</div>
            </div>
          </div>

          <!-- v10: 일괄 재처리 툴바 -->
          <div v-if="errItems.length > 0" class="bulk-retry-bar">
            <label class="bulk-check-label">
              <input type="checkbox" :checked="isBulkRetryAllSelected" :indeterminate.prop="isBulkRetryIndeterminate" @change="toggleBulkRetryAll"/>
              <span>전체 선택</span>
              <span class="bulk-count">({{ bulkSelectedRetry.size }}/{{ errItems.length }})</span>
            </label>
            <!-- v95_p107 hotfix_047: 오류만 선택 (status='error' 항목만 set) -->
            <button class="bulk-only-err-btn" @click="selectOnlyErrors" :disabled="errOnlyCount === 0" :title="`status='error' 인 항목만 선택 (${errOnlyCount}건)`">
              ⚠ 오류만 ({{ errOnlyCount }})
            </button>
            <div class="bulk-filters">
              <select v-model="bulkFilterType" class="bulk-sel">
                <option value="">전체 유형</option>
                <option value="table">TABLE</option>
                <option value="procedure">PROC</option>
                <option value="function">FUNC</option>
                <option value="view">VIEW</option>
                <option value="trigger">TRIGGER</option>
              </select>
              <select v-model="bulkFilterErrCode" class="bulk-sel">
                <option value="">전체 에러</option>
                <option value="1064">1064 (syntax)</option>
                <option value="1075">1075 (auto_increment)</option>
                <option value="1118">1118 (row size)</option>
                <option value="1419">1419 (super)</option>
                <option value="other">기타</option>
              </select>
            </div>
            <button class="bulk-open-btn"
                    :disabled="bulkSelectedRetry.size === 0"
                    @click="bulkRetryPanelOpen = !bulkRetryPanelOpen"
                    :class="{open: bulkRetryPanelOpen}">
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" style="width:11px;height:11px">
                <path d="M10 2A4.5 4.5 0 1 1 5.5 1"/><polyline points="7,0 10,2 8,5"/>
              </svg>
              일괄 재처리 ({{ bulkSelectedRetry.size }}건)
              <svg viewBox="0 0 10 6" fill="none" stroke="currentColor" stroke-width="1.5" style="width:8px;height:8px;transition:transform .2s"
                   :style="{transform: bulkRetryPanelOpen?'rotate(180deg)':'rotate(0deg)'}">
                <polyline points="1,1 5,5 9,1"/>
              </svg>
            </button>
          </div>

          <!-- v10: 일괄 처리 방식 선택 패널 -->
          <div v-if="bulkRetryPanelOpen && bulkSelectedRetry.size > 0" class="bulk-retry-panel">
            <div class="brp-header">처리 방식 선택 — 선택한 {{ bulkSelectedRetry.size }}건에 동일하게 적용됩니다</div>
            <div class="brp-grid" :class="{'has-ai-active': bulkRetryMode === 'ai'}">
              <label v-for="opt in bulkRetryOpts" :key="opt.value"
                     class="brp-opt"
                     :class="[{active: bulkRetryMode === opt.value}, 'brp-opt-' + opt.value]"
                     @click="bulkRetryMode = opt.value">
                <div class="brp-opt-head">
                  <span class="brp-opt-icon">{{ opt.icon }}</span>
                  <span class="brp-opt-title">{{ opt.title }}</span>
                  <span v-if="opt.recommended" class="brp-opt-rec">추천</span>
                  <span v-if="bulkRetryMode === opt.value" class="brp-opt-check">✓</span>
                </div>
                <div class="brp-opt-desc">{{ opt.desc }}</div>
                <!-- AI 모드 선택 시 재시도 횟수 -->
                <div v-if="opt.value === 'ai' && bulkRetryMode === 'ai'" class="brp-ai-opts">
                  <!-- v95_p107 hotfix_048: provider 선택 (관리자 등록 AI 중) -->
                  <div class="brp-ai-field">
                    <span class="brp-ai-lbl">AI Provider</span>
                    <select v-model="bulkAiProvider" class="brp-sel" @click.stop>
                      <option value="">(기본 설정)</option>
                      <option v-for="p in availableProviders" :key="p.id" :value="p.id">{{ p.name }}</option>
                    </select>
                  </div>
                  <div v-if="bulkAiProvider && availableModels.length" class="brp-ai-field">
                    <span class="brp-ai-lbl">모델</span>
                    <select v-model="bulkAiModel" class="brp-sel" @click.stop>
                      <option value="">(provider 기본)</option>
                      <option v-for="m in availableModels" :key="m.id" :value="m.id">{{ m.label }}</option>
                    </select>
                  </div>
                  <div class="brp-ai-field">
                    <span class="brp-ai-lbl">최대 재시도</span>
                    <select v-model.number="bulkAiMaxRetries" class="brp-sel" @click.stop>
                      <option :value="1">1회</option>
                      <option :value="2">2회</option>
                      <option :value="3">3회</option>
                      <option :value="5">5회</option>
                      <option :value="7">7회</option>
                    </select>
                  </div>
                  <!-- v95_p107 hotfix_068: 동시 처리 (병렬) -->
                  <div class="brp-ai-field">
                    <span class="brp-ai-lbl">동시 처리</span>
                    <select v-model.number="bulkConcurrency" class="brp-sel" @click.stop>
                      <option :value="1">1개 (순차, 로컬 AI 권장)</option>
                      <option :value="3">3개 동시</option>
                      <option :value="5">5개 동시</option>
                      <option :value="10">10개 동시</option>
                    </select>
                  </div>
                  <span class="brp-ai-hint">에러 누적 후 재시도. 로컬 AI(Ollama)는 1개 순차, Claude API 는 3~5개 동시 권장.</span>
                </div>
              </label>
            </div>
            <div class="brp-actions">
              <button class="brp-cancel" @click="bulkRetryPanelOpen = false">취소</button>
              <button class="brp-run" :disabled="bulkRetryRunning || !bulkRetryMode" @click="runBulkRetry">
                <span v-if="bulkRetryRunning" class="spin-sm"></span>
                <span v-else>{{ bulkSelectedRetry.size }}건 일괄 재처리 시작</span>
              </button>
            </div>
          </div>

          <!-- 목록 -->
          <div style="overflow-y:auto;flex:1">
            <div v-if="!errItems.length" style="padding:28px;text-align:center;font-size:12px;color:var(--text-tertiary)">
              <template v-if="(job.rows_error||0) > 0">
                <!-- 행 오류는 있지만 item_statuses에 기록 없음 → 이전 이관 데이터 -->
                <div style="font-size:1.8rem;margin-bottom:8px">⚠️</div>
                <div style="font-weight:600;color:var(--text-secondary);margin-bottom:4px">
                  이관 중 {{ fmtNum(job.rows_error) }}행이 실패했습니다
                </div>
                <div style="font-size:.72rem;line-height:1.6">
                  on_error = skip 설정으로 해당 행을 건너뛰고 계속 진행했습니다.<br>
                  항목별 상세 오류는 이관 로그에서 확인하세요.
                </div>
              </template>
              <template v-else>
                <div style="font-size:1.8rem;margin-bottom:8px">✅</div>
                <div style="font-weight:600;color:var(--text-secondary)">오류 항목이 없습니다</div>
              </template>
            </div>
            <div v-for="item in filteredErrItems" :key="item.name" class="emd-item"
                 :class="{'emd-item-retrying': item.retry_status==='retrying', 'emd-item-retried': item.retry_status==='retry_done'}">
              <!-- 항목 헤더 -->
              <div class="emd-row">
                <input type="checkbox" class="emd-bulk-chk"
                       :checked="bulkSelectedRetry.has(item.name)"
                       @change.stop="toggleBulkRetryItem(item.name)"
                       @click.stop/>
                <span class="emd-badge" :class="item.status==='error'?'err':'warn'">{{ item.type?.toUpperCase() }}</span>
                <span v-if="extractErrCode(item.error)" class="emd-errcode">{{ extractErrCode(item.error) }}</span>
                <span class="emd-name">{{ item.name }}</span>
                <!-- v10 #33: 대기 상태 배지 (해당 차례가 아직 안 옴) -->
                <span v-if="item.retry_status==='queued'" class="emd-retry-badge queued">
                  <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:9px;height:9px">
                    <circle cx="6" cy="6" r="4.5"/><polyline points="6,3 6,6 8,7"/>
                  </svg>
                  대기 중
                  <span v-if="item.retry_queue_index" class="emd-retry-attempt">#{{ item.retry_queue_index }}</span>
                </span>
                <span v-else-if="item.retry_status==='retrying'" class="emd-retry-badge running">
                  <span class="emd-retry-dot"></span>
                  재이관중 {{ fmtRetryElapsed(item) }}
                  <span v-if="item.retry_attempt" class="emd-retry-attempt">AI {{ item.retry_attempt }}/{{ item.retry_max || bulkAiMaxRetries }}</span>
                </span>
                <span v-else-if="item.retry_status==='retry_done'" class="emd-retry-badge done">
                  <svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="2" style="width:9px;height:9px"><polyline points="2,5 4.5,7.5 8.5,2.5"/></svg>
                  재이관완료<span v-if="item.retry_attempt && item.retry_attempt > 1" class="emd-retry-attempt-cnt"> · {{ item.retry_attempt }}회 만에</span>{{ item.retry_duration_s ? ' · ' + item.retry_duration_s + '초' : '' }}
                </span>
                <span v-else-if="item.retry_status==='retry_failed'" class="emd-retry-badge failed" :title="item.retry_last_error || ''">
                  ⚠ 재이관실패 {{ item.retry_duration_s ? '· ' + item.retry_duration_s + '초' : '' }}
                </span>
                <span v-if="item.batch_error_rows" class="emd-fail-rows">{{ fmtNum(item.batch_error_rows) }}행 실패</span>
                <span v-if="item.finished_at && !item.retry_status" class="emd-time">{{ parseDate(item.finished_at)?.toLocaleTimeString('ko-KR')||'' }}</span>
                <button v-if="(item.type==='table'||['function','procedure','trigger','view'].includes(item.type)) && !item.retry_status"
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
          <!-- v10 #33: 일괄 재처리 진행 상태 바 (배치 실행 중이거나 완료/실패 이력이 남아있을 때) -->
          <div v-if="bulkBatchTotal > 0" class="emd-progress-footer">
            <div class="emd-prog-row">
              <div class="emd-prog-label">
                <span v-if="bulkRetryRunning" class="emd-prog-spinner"></span>
                <span v-if="bulkRetryRunning">일괄 재처리 진행 중</span>
                <span v-else>일괄 재처리 완료</span>
                <span class="emd-prog-count">{{ bulkBatchDone }}/{{ bulkBatchTotal }} ({{ bulkBatchProgress }}%)</span>
              </div>
              <div class="emd-prog-times">
                <span>경과 {{ fmtBulkMs(bulkBatchElapsed) }}</span>
                <span v-if="bulkRetryRunning && bulkBatchEtaSec != null" class="emd-prog-eta">
                  · 예상 남은 {{ fmtBulkMs(bulkBatchEtaSec) }}
                </span>
                <!-- v95_p107 hotfix_054: 중지 버튼 -->
                <button v-if="bulkRetryRunning && !bulkRetryAborted"
                        class="emd-prog-abort-btn"
                        @click="abortBulkRetry">
                  ■ 중지
                </button>
                <span v-else-if="bulkRetryRunning && bulkRetryAborted" class="emd-prog-aborting">
                  중지 중...
                </span>
              </div>
            </div>
            <div class="emd-prog-bar">
              <div class="emd-prog-fill" :style="{width: bulkBatchProgress + '%'}"></div>
            </div>
            <div v-if="bulkRetryRunning && bulkCurrentItem" class="emd-prog-current">
              🔄 지금 처리 중: <b>{{ bulkCurrentItem.name }}</b>
              <span v-if="bulkCurrentItem.attempt"> · AI {{ bulkCurrentItem.attempt }}/{{ bulkCurrentItem.maxAttempt }}</span>
            </div>
          </div>
          <!-- 푸터 -->
          <div style="display:flex;justify-content:flex-end;padding:12px 18px;border-top:0.5px solid var(--border-light)">
            <button @click="showErrModal=false" style="padding:6px 20px;border-radius:7px;background:#2563eb;color:#fff;border:none;font-size:.82rem;font-weight:600;cursor:pointer">닫기</button>
          </div>
          <!-- v95_p107 hotfix_051: resize handle (우하단 드래그) -->
          <div v-if="!errMinimized" class="emd-float-resize" @pointerdown="startErrResize" title="크기 조정 (드래그)"></div>
        </div>
      </div>

    </template>
  <!-- 오류 상세 모달 -->

  </div>
</template>

<script setup>
import { fmtDate, fmtDateShort, fmtElapsed, fmtTime, parseDate, toMs } from '@/utils/dateUtils.js'
defineOptions({ name: 'JobMonitor' })
import { ref, computed, onMounted, onActivated, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useConnectorStore } from '@/store/connectorStore.js'
import { useAppStore }       from '@/store/appStore.js'
import { useMonitorStore }   from '@/store/monitorStore.js'  // v10 #22
import ConnectPanel          from '@/components/common/ConnectPanel.vue'
import PageHeader            from '@/components/layout/PageHeader.vue'
import axios                 from 'axios'   // v92p6: stuck job 중단용
import { useDragFloat }      from '@/composables/useDragFloat.js'  // v95_p107 hotfix_046: 오류 상세 모달 플로팅

const conn = useConnectorStore()
const app  = useAppStore()
const monitorStore = useMonitorStore()  // v10 #22: 플로팅 모니터 토글/배지용

// v90.15: 효과적 연결 상태 - 직접 연결 OR Job 정보 OR 활성 Job 존재
//   본부장님 시나리오: Job 만들고 모니터 진입했는데 conn.bothConnected=false
//   → ConnectPanel 이 잘못 떠있는 문제 해결
const isEffectivelyConnected = computed(() => {
  // 1) 직접 연결돼있으면 OK
  if (conn.bothConnected) return true
  // 2) 선택된 Job 이 있고 src/tgt DB 정보 있으면 OK
  if (job.value && (job.value.src_database || job.value.src_db)) return true
  // 3) 활성 Job 이 있으면 OK (이관 진행 중)
  if (jobs.value && jobs.value.some(j => j.status === 'running')) return true
  return false
})

// v90.15: 표시용 DB 정보 (직접 연결 우선, 없으면 Job 정보 사용)
const effectiveSrcDb = computed(() => {
  if (conn.source.status === 'ok') return conn.source
  if (job.value) {
    return {
      dbType: job.value.src_db || 'mysql',
      database: job.value.src_database || '',
      host: job.value.src_host || '',
      status: 'ok',  // 표시용
    }
  }
  return conn.source
})

const effectiveTgtDb = computed(() => {
  if (conn.target.status === 'ok') return conn.target
  if (job.value) {
    return {
      dbType: job.value.tgt_db || 'mssql',
      database: job.value.tgt_database || '',
      host: job.value.tgt_host || '',
      status: 'ok',  // 표시용
    }
  }
  return conn.target
})

function onConnected() {
  app.notify('DB 연결 완료!', 'success')
}

const API = '/api/v1/jobs'
const jobs = ref([]); const job = ref(null); const selectedJobId = ref('')
const jobPickerOpen  = ref(false)
const jpSortKey      = ref('created_at')  // 기본: 최신순
const jpSortDir      = ref('desc')

// ════════════════════════════════════════════════════════════════
// v95_p91_compact (2026-05-08 본부장님 본질 처방):
// "위 카드 줄이고 진행 중인 리스트 더 크게 보이게"
//
// kpiExpanded: 상단 카드 펼침/접힘 (localStorage 저장)
// 기본값: false (접힘) — 본부장님 비전 그대로 진행 리스트 우선
// ════════════════════════════════════════════════════════════════
const kpiExpanded = ref(
  // localStorage 에서 복원, 없으면 기본 false (접힘)
  (() => {
    try {
      const saved = localStorage.getItem('jobMonitor.kpiExpanded')
      return saved === null ? false : saved === 'true'
    } catch { return false }
  })()
)
// 변경 시 자동 저장
watch(kpiExpanded, (val) => {
  try { localStorage.setItem('jobMonitor.kpiExpanded', String(val)) } catch {}
})

// 드롭다운 정렬 토글
function toggleJpSort(key) {
  if (jpSortKey.value === key) jpSortDir.value = jpSortDir.value === 'asc' ? 'desc' : 'asc'
  else { jpSortKey.value = key; jpSortDir.value = key === 'created_at' ? 'desc' : 'asc' }
}

// 드롭다운용 정렬된 jobs
const sortedJobs = computed(() => {
  const list = [...jobs.value]
  const key = jpSortKey.value
  const dir = jpSortDir.value === 'asc' ? 1 : -1
  list.sort((a, b) => {
    let av = a[key], bv = b[key]
    if (key === 'created_at' || key === 'started_at') {
      av = av ? new Date(av).getTime() : 0
      bv = bv ? new Date(bv).getTime() : 0
    } else if (key === 'rows_processed') {
      av = Number(av || 0); bv = Number(bv || 0)
    } else if (key === 'status') {
      // running 먼저
      const order = {running:0,paused:1,completed:2,error:3,aborted:4}
      av = order[av] ?? 9; bv = order[bv] ?? 9
    } else {
      av = String(av || '').toLowerCase()
      bv = String(bv || '').toLowerCase()
    }
    return av === bv ? 0 : (av < bv ? -dir : dir)
  })
  return list
})


function fmtRowsShort(n) {
  if (!n) return '0'
  if (n >= 1000000) return (n/1000000).toFixed(1) + 'M'
  if (n >= 1000)    return Math.round(n/1000) + 'K'
  return String(n)
}
const search = ref(''); const activeFilter = ref('all'); const activeType = ref('all')
const expanded = ref({}); const polling = ref(false); const autoRefresh = ref(false)
let autoTimer = null
// ── ETA 고정 완료시각 (단조 감소 보장) ─────────────────────────
const etaFixedMs = ref(0)   // 예상 완료 Unix ms
const etaJobId   = ref('')  // 추적 중인 Job ID

const filters = [
  {v:'all',l:'전체'},{v:'running',l:'진행중'},{v:'done',l:'완료'},
  {v:'pending',l:'대기'},{v:'error',l:'오류'},{v:'mismatch',l:'불일치'},
]
const types = [
  {v:'all',l:'전체'},{v:'table',l:'테이블'},{v:'view',l:'뷰'},
  {v:'procedure',l:'프로시저'},{v:'function',l:'함수'},{v:'trigger',l:'트리거'},
]

const route = useRoute()

async function loadJobs(opts = {}) {
  const {force = false} = opts
  try {
    const r = await fetch(API); if (r.ok) jobs.value = await r.json()
    if (!selectedJobId.value || force) {
      // ── URL 쿼리 jobId: 특정 Job 바로 선택 ──
      const qJobId = route.query.jobId
      if (qJobId) {
        const found = jobs.value.find(j => j.id === qJobId)
        if (found) { selectedJobId.value = found.id; await loadJob(); return }
      }
      // ── URL 쿼리 filter=error: 오류 Job 자동 선택 ──
      const filter = route.query.filter
      if (filter === 'error') {
        const errJob = [...jobs.value]
          .filter(j => j.status === 'error' || (j.status === 'completed' && (j.rows_error || 0) > 0))
          .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0]
        if (errJob) { selectedJobId.value = errJob.id; await loadJob(); return }
      }
      // 기본: 실행 중인 Job 자동 선택 → 없으면 가장 최신 Job 선택
      const running = jobs.value.find(j => j.status === 'running' || j.status === 'paused')
      if (running) {
        selectedJobId.value = running.id; await loadJob()
      } else {
        // 실행 중 없으면 가장 최신 Job 자동 선택
        const latest = [...jobs.value].sort((a,b) => new Date(b.created_at||0) - new Date(a.created_at||0))[0]
        if (latest) { selectedJobId.value = latest.id; await loadJob() }
      }
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

// v9 패치 #26: 이관 리포트 새 창
function openReport() {
  if (!selectedJobId.value) return
  const url = `/report/job/${selectedJobId.value}?style=formal`
  window.open(url, '_blank', 'width=1100,height=900,menubar=no,toolbar=no')
}
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

// v9 패치 #10: 실행 중/대기중 Job 있으면 자동 새로고침 켜는 공통 헬퍼
function _autoEnableIfActive() {
  const hasActive = jobs.value.some(j =>
    j.status === 'running' || j.status === 'paused' ||
    j.status === 'idle'    || j.status === 'pending'
  )
  if (hasActive && !autoRefresh.value) {
    autoRefresh.value = true
    toggleAuto()
  }
}

// v9 패치 #24: 최신 실행 Job으로 강제 전환 (페이지 복귀/새 Job 시작 시)
function _forceSelectLatestRunning() {
  const running = [...jobs.value]
    .filter(j => j.status === 'running' || j.status === 'paused')
    .sort((a,b) => new Date(b.created_at||0) - new Date(a.created_at||0))[0]
  if (running && running.id !== selectedJobId.value) {
    // 이전 Job 잔상 제거
    job.value = null
    expanded.value = {}
    selectedJobId.value = running.id
    loadJob()
    return true
  }
  return false
}

onMounted(async () => {
  await loadJobs()
  // 진행 중/대기 Job 있으면 자동 새로고침 켜기
  _autoEnableIfActive()
  // v90.59: 사용자가 모니터 버튼을 누르기 전부터 백그라운드로 워밍업.
  //   클릭 즉시 데이터가 보이도록.
  // v90.62: primeBackground (1회) 대신 startBackgroundPolling (지속 폴링) 으로 변경.
  //   본부장님 호소: "모니터 버튼 옆에 LIVE 인디케이터 + 자동 갱신"
  //   화면의 LIVE 배너 / current_table 업데이트 등이 지속 폴링 데이터에 의존.
  monitorStore.startBackgroundPolling()
})

// keep-alive 복귀 시 — 최신 Job 강제 재선택 + 잔상 clear + 자동 갱신 ON
onActivated(async () => {
  await loadJobs()
  // v9 패치 #24: 실행 중인 새 Job이 있으면 강제 전환 (잔상 제거)
  _forceSelectLatestRunning()
  _autoEnableIfActive()
  // v90.62: 페이지 재진입 시에도 백그라운드 폴링 시작 (이미 동작 중이면 no-op)
  monitorStore.startBackgroundPolling()
})
onUnmounted(()=>{
  clearInterval(autoTimer); clearInterval(_tickTimer)
  // v90.62: 페이지 떠날 때 백그라운드 폴링 정리 (visible 상태면 정지 안 함)
  monitorStore.stopBackgroundPolling()
})
// 외부 클릭 시 드롭다운 닫기
onMounted(() => {
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.job-picker')) jobPickerOpen.value = false
  })
})
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

// v90.24: 객체별 진행 상태 (SP/Function/View/Trigger)
//   본부장님 지적: "전체 진행 99.9% 인데 객체 정보 안 보임 → 0.1% 가 뭐 때문?"
//   item_statuses 에서 type 별로 done/total 집계
const objectsProgress = computed(() => {
  const j = job.value
  if (!j || !j.item_statuses) return null
  
  const result = {
    function:  { done: 0, total: 0, running: 0, failed: 0 },
    procedure: { done: 0, total: 0, running: 0, failed: 0 },
    view:      { done: 0, total: 0, running: 0, failed: 0 },
    trigger:   { done: 0, total: 0, running: 0, failed: 0 },
  }
  
  for (const s of Object.values(j.item_statuses)) {
    if (!s) continue
    const t = (s.type || '').toLowerCase()
    if (!result[t]) continue  // 테이블은 제외
    
    result[t].total++
    if (s.status === 'done' || s.status === 'completed') {
      result[t].done++
    } else if (s.status === 'running') {
      result[t].running++
    } else if (s.status === 'failed' || s.status === 'error') {
      result[t].failed++
    }
  }
  
  // 합계
  let totalAll = 0, doneAll = 0, runningAll = 0, failedAll = 0
  for (const k of Object.keys(result)) {
    totalAll   += result[k].total
    doneAll    += result[k].done
    runningAll += result[k].running
    failedAll  += result[k].failed
  }
  
  if (totalAll === 0) return null  // 객체 없으면 표시 안 함
  
  return {
    ...result,
    total:   totalAll,
    done:    doneAll,
    running: runningAll,
    failed:  failedAll,
  }
})

// ════════════════════════════════════════════════════════════════
// v95_p91_compact (2026-05-08 본부장님): 컴팩트 모드 헬퍼
// ════════════════════════════════════════════════════════════════
// statusLabel() 은 line 2212 의 기존 함수 사용 (중복 정의 회피)

// v95_p107 hotfix_063: 경과시간 표시 헬퍼 (실패 항목 fallback)
function _h063ElapsedDisplay(item) {
  // 1. started_at + finished_at 있으면 정상 계산
  if (item.started_at) {
    return fmtElapsed(item.started_at, item.finished_at)
  }
  // 2. 재이관 시간 있으면 (모달 일괄 재처리 결과)
  if (item.retry_duration_s != null && item.retry_duration_s >= 0) {
    const s = Number(item.retry_duration_s)
    if (s >= 3600) return Math.floor(s / 3600) + '시간 ' + String(Math.floor((s%3600)/60)).padStart(2,'0') + '분'
    if (s >= 60)   return Math.floor(s / 60) + '분 ' + String(s % 60).padStart(2,'0') + '초'
    return s + '초'
  }
  // 3. duration_s 또는 elapsed_s (백엔드가 직접 계산해 준 경우)
  if (item.duration_s != null) {
    const s = Number(item.duration_s)
    return s + '초'
  }
  return '—'
}

// 현재 진행 중인 단계 라벨 (running 상태에서만)
const currentPhaseLabel = computed(() => {
  const j = job.value
  if (!j || j.status !== 'running') return ''
  const phase = j.phase || ''
  const phaseMap = {
    'FK_DISABLE':     'FK·트리거 비활성화 중',
    'DATA_MIGRATE':   '데이터 이관 중',
    'OBJECT_CONVERT': '객체 변환 중 (SP/FN/VW/TR)',
    'FK_RESTORE':     'FK·트리거 복원 중',
    'CDC_RUNNING':    'CDC 변경분 이관 중',
    'ADVISOR_APPLY':  'AI 권고 적용 중',
  }
  return phaseMap[phase] || (phase ? `${phase} 진행 중` : '')
})

// v95_p107 hotfix_029 (2026-05-11 본부장님 본질 처방):
// 객체 변환 단계 진행 중인지 — 접힌 헤더에서 객체 진행률 강조 표시용
const isObjectPhaseRunning = computed(() => {
  const j = job.value
  if (!j || j.status !== 'running') return false
  return j.phase === 'OBJECT_CONVERT'
})

// 전체 진행률 (effectiveProgress 와 동일)
const totalProgressPct = computed(() => {
  try {
    return Math.round(effectiveProgress.value || 0)
  } catch {
    return Math.round(safeProgress.value || 0)
  }
})

// 현재 객체 변환 상태 (객체 변환 중일 때만)
const currentObjectStatus = computed(() => {
  const j = job.value
  if (!j || j.status !== 'running' || j.phase !== 'OBJECT_CONVERT') return ''
  const op = objectsProgress.value
  if (!op) return ''
  for (const key of ['function', 'procedure', 'view', 'trigger']) {
    const cat = op[key]
    if (cat && cat.done < cat.total) {
      const labels = { function: 'FN', procedure: 'SP', view: 'VW', trigger: 'TR' }
      return `${labels[key]} ${cat.done}/${cat.total}`
    }
  }
  return ''
})

// 오류 총 건수
const errorTotalCount = computed(() => {
  const j = job.value
  if (!j) return 0
  const op = objectsProgress.value
  return (op?.failed || 0) + (j.rows_error || 0)
})

// 오류 상세로 스크롤
function scrollToErrors() {
  const el = document.querySelector('.kpi-error') || document.querySelector('[data-errors]')
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

// ════════════════════════════════════════════════════════════════

//   본부장님 호소: "전체 진행 상태바 안 움직여"
//   원인: backend job.progress 는 테이블 이관 단계만 추적.
//         테이블 다 끝나고 객체 변환 (FN/SP/VW/TR) 진행 중인데도
//         progress=0 으로 멈춰 있음.
//   처방: backend progress 가 0 일 때 객체 진행률 직접 계산해서 사용.
//
// safeProgress 를 그대로 두고 별도 effectiveProgress 만들어 template 에서 우선 사용.
// 이렇게 하면 다른 곳 (jobs panel 등) 에서 safeProgress 쓰는 곳 영향 없음.
// ════════════════════════════════════════════════════════════════
// ════════════════════════════════════════════════════════════════
const effectiveProgress = computed(() => {
  const backend = safeProgress.value
  const j = job.value
  // v95_p47 (2026-05-05 본부장님): 전체 진행 = 테이블 단계만 표시 (객체는 별도 진행바)
  //   본부장님 호소: "테이블 71/71 완료인데 99.9% — 100% 가 맞다"
  //                 "스테이터스바 따로 하나 만들어서 객체 진행 보여달라"
  //   본질: 전체 진행 = 테이블 이관 단계, 객체 변환은 별도 진행바로 분리
  //   처방: 테이블 모두 완료 시 100% 강제, 객체는 objectsOverallProgress 진행바
  if (j && j.table_total > 0 && (j.table_done || 0) >= j.table_total) {
    // 테이블 모두 완료 → 100% 고정 (객체 진행은 별도 진행바)
    return 100
  }
  // backend 가 충분히 의미있으면 그대로
  if (backend > 0) return backend

  // backend 가 0 인데 객체 변환 중이면 객체 진행률 사용 (테이블 없는 잡)
  const op = objectsProgress.value
  if (op && op.total > 0 && (!j || !j.table_total || j.table_total === 0)) {
    const processedAll = op.done + op.failed
    return Math.min(100, Math.round((processedAll / op.total) * 100 * 10) / 10)
  }
  
  return 0
})

// v95_p47 (2026-05-05 본부장님): 객체 전체 진행률 (별도 진행바용)
//   본부장님 호소: "객체는 시간 말고 단순 상태바로 따로 보여달라"
//   처방: 객체 (FN/SP/VW/TR) 의 (done + failed) / total * 100
const objectsOverallProgress = computed(() => {
  const op = objectsProgress.value
  if (!op || op.total === 0) return null
  const processed = op.done + op.failed
  return {
    pct: Math.round((processed / op.total) * 100 * 10) / 10,
    done: op.done,
    failed: op.failed,
    running: op.running,
    total: op.total,
    waiting: op.total - processed - op.running,
  }
})

// ── ETA 포맷 공통 함수 ──────────────────────────────────────────
function _fmtRemain(sec) {
  if (sec <= 0) return '거의 완료'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  if (h > 0) return h + '시간 ' + String(m).padStart(2,'0') + '분 ' + String(s).padStart(2,'0') + '초'
  if (m > 0) return m + '분 ' + String(s).padStart(2,'0') + '초'
  return s + '초'
}
function _fmtFinishAt(ms) {
  const d = new Date(ms)
  const h = d.getHours(), m = d.getMinutes(), s = d.getSeconds()
  const ampm = h < 12 ? '오전' : '오후'
  return ampm + ' ' + String(h % 12 || 12).padStart(2,'0') + '시 ' +
         String(m).padStart(2,'0') + '분 ' + String(s).padStart(2,'0') + '초'
}

// ── ETA: 완료시각 고정 (최초 계산 후 절대 재계산 안함) ───────────
// 접근 방식: 경과시간 기반 선형 예측만 사용 (speed 변동 무관)
// 완료시각 = 시작시각 + (경과시간 / 진행률) × 100
// → 진행률이 올라가면 자연스럽게 완료시각이 앞당겨짐
const etaAccuracy = ref(null)

// v10 #24 (2026-04-24): ETA 안정화 상태
// Choi 피드백: "남은 시간이 완전 들쭉 날쭉" — 19:14 → 16:20 식 3시간 급변
// 개선 3종:
//   1. EMA(지수 이동평균) 으로 속도 smoothing
//   2. 단조 감소 보장 (큰 폭 증가 억제)
//   3. 변동 폭 > 30% 이면 "재계산 중..." 일시 표시
const etaEmaRemainSec = ref(null)      // 지수이동평균 남은 시간 (초)
const etaLastShownSec = ref(null)      // 마지막으로 표시한 값 (단조 감소용)
const etaRecalcCount  = ref(0)         // 급변 감지 카운터
const etaRecentSamples = ref([])       // v90.22: 최근 5개 ETA 샘플 (단순 평균용)
const etaEmaAlpha     = 0.15           // EMA 가중치 (낮을수록 부드러움)
const etaMaxJumpPct   = 0.30           // 30% 넘게 변하면 "재계산 중"
const etaDownThrottle = 0.10           // 한 번에 최대 10% 만 줄어들 수 있음 (단조 감소 억제)

// 1초 tick
const nowMs  = ref(Date.now())
let _tickTimer = null
watch(() => job.value?.status, (s) => {
  clearInterval(_tickTimer)
  if (s === 'running') {
    _tickTimer = setInterval(() => { nowMs.value = Date.now() }, 1000)
  } else {
    etaFixedMs.value = 0; etaJobId.value = ''; etaAccuracy.value = null
    // v10 #24: ETA 안정화 상태 리셋
    etaEmaRemainSec.value = null
    etaLastShownSec.value = null
    etaRecalcCount.value = 0
    etaRecentSamples.value = []  // v90.22: 새 Job 진입 시 샘플 초기화
  }
}, { immediate: true })

// eta: 단순 명확한 계산 — (전체 rows - 처리된 rows) / 평균 속도
// v9 패치 #38: 이전 로직은 너무 복잡해서 "3초 곧 완료" 같은 버그 발생.
// 단순 공식으로 회귀: 남은 rows / 속도 = 남은 시간
const eta = computed(() => {
  const j = job.value
  if (!j || j.status !== 'running' || !j.started_at)
    return { remains: null, finishAt: null, cardClass: '', accuracy: null }

  const now     = nowMs.value
  const startMs = toMs(j.started_at)
  const elapsed = (now - startMs) / 1000

  if (elapsed < 5) return { remains: null, finishAt: null, cardClass: '', accuracy: null }

  const statuses = j.item_statuses || {}

  // v10 #4 (2026-04-20): 테이블별 합산 ETA
  //
  // 기존 문제: (전체 남은 행 / 전체 평균 속도) — 평균이 대형 테이블에 편향.
  //   예) 62 테이블 중 61개 작은 테이블이 빨리 끝나면 평균속도 부풀려짐.
  //        마지막 남은 cus_m 대형 테이블은 실제 훨씬 느려서 "14분" 이라 거짓표시.
  //        사용자 체감: 실제 43분 걸려서 "잔여시간이 엉망" 이란 불만.
  //
  // 개선: 각 테이블별 남은행/속도 합산.
  //   - running: 해당 테이블 순간 speed 우선 (없으면 Job 평균)
  //   - pending: 현재 러닝 테이블 speed 로 추정 (같은 타겟 DB 가정)
  //   - done   : 스킵
  //
  // 폴백: 테이블별 rows_total 이 전부 0 이면 기존 평균 방식 (하위호환)

  // --- 평균/순간 속도 계산 (폴백 및 pending 테이블 추정용) ---
  let totalTableCount = 0
  let knownTableCount = 0
  let processedSoFar = 0
  for (const s of Object.values(statuses)) {
    if (!s || s.type !== 'table') continue
    totalTableCount++
    const rt = Number(s.rows_total || s.rows_src || s.rows || 0)
    if (rt > 0) knownTableCount++
    if (s.status === 'done' || s.status === 'completed') {
      processedSoFar += Number(s.rows_tgt || s.rows_src || s.rows || 0)
    } else if (s.status === 'running') {
      processedSoFar += Number(s.rows_tgt || 0)
    }
  }
  const avgRps = elapsed > 0 && processedSoFar > 0 ? processedSoFar / elapsed : 0
  const instantSpeed = Number(j.speed || 0)
  // 순간이 급등하면 일부 반영 (기존 로직 보존)
  let blendedAvg = avgRps
  if (instantSpeed > avgRps * 1.5) {
    blendedAvg = avgRps * 0.7 + instantSpeed * 0.3
  }

  // 현재 러닝 테이블의 순간속도 — pending 추정용
  let runningRps = 0
  for (const s of Object.values(statuses)) {
    if (!s || s.type !== 'table') continue
    if (s.status === 'running') {
      const r = Number(s.speed || 0)
      if (r > runningRps) runningRps = r
    }
  }
  const pendingRps = runningRps > 0 ? runningRps : blendedAvg

  // --- 테이블별 합산 ---
  let remainingSec = 0
  let usedPerTable = false
  let anyUnknown = false
  let pendingObjects = 0  // v90.23: 처리 대기 중인 객체 수

  for (const s of Object.values(statuses)) {
    if (!s || s.type !== 'table') continue
    if (s.status === 'done' || s.status === 'completed') continue

    const tTotal = Number(s.rows_total || s.rows_src || 0)
    if (tTotal <= 0) {
      anyUnknown = true    // 정확도 힌트용 — 총 행수 모르는 테이블 있음
      continue
    }
    const tDone = Number(s.rows_tgt || 0)
    const tLeft = Math.max(0, tTotal - tDone)
    if (tLeft === 0) continue

    let rps
    if (s.status === 'running') {
      rps = Number(s.speed || 0) || blendedAvg
    } else {
      rps = pendingRps
    }
    if (rps < 1) { anyUnknown = true; continue }

    remainingSec += tLeft / rps
    usedPerTable = true
  }
  
  // v90.23: SP/Function/View/Trigger 객체 처리 시간 추가
  //   본부장님 지적: "object 적용시간은 1개에 대략 3분 정도, ETA 에 빠져있음"
  //
  //   추정 시간 (사용자 경험치):
  //     - AI 변환 (Claude API): 약 60~120초/개 (가변)
  //     - rule-based 변환:      약 5~15초/개
  //     - 보수적으로 평균 값 사용
  //
  //   가능한 병렬도: SP/FN/VW 는 서로 독립적이면 병렬 (현재 백엔드 미구현)
  //                  TRIGGER 는 테이블 의존이라 마지막 처리 (순차)
  //   → 현재 백엔드는 모두 순차 → ETA 는 순차 기준으로 계산
  
  // 객체 종류별 평균 시간 추정 (초/개)
  //   AI 모드: SP/FN 가 가장 무거움, View 는 단순, Trigger 는 중간
  const OBJ_TIME_ESTIMATE = {
    function:  90,   // 1.5분 (AI 변환 + 검증)
    procedure: 120,  // 2분 (가장 복잡)
    view:      30,   // 30초 (대체로 단순)
    trigger:   60,   // 1분 (테이블 의존)
  }
  
  for (const s of Object.values(statuses)) {
    if (!s) continue
    const t = (s.type || '').toLowerCase()
    if (!['function','procedure','view','trigger'].includes(t)) continue
    if (s.status === 'done' || s.status === 'completed') continue
    if (s.status === 'running') {
      // 진행 중 객체는 절반 정도 남았다고 가정 (완료 시점 추정 어려움)
      remainingSec += (OBJ_TIME_ESTIMATE[t] || 60) * 0.5
    } else {
      // pending
      remainingSec += OBJ_TIME_ESTIMATE[t] || 60
    }
    pendingObjects++
  }

  // --- 폴백: 테이블별 데이터 부족 시 기존 평균 방식 ---
  if (!usedPerTable) {
    let totalRows = 0
    for (const s of Object.values(statuses)) {
      if (s && s.type === 'table') {
        totalRows += Number(s.rows_total || s.rows_src || s.rows || 0)
      }
    }
    const engineEstimate = Number(j.rows_total || 0)
    if (knownTableCount < totalTableCount && engineEstimate > totalRows) {
      totalRows = engineEstimate
    }
    if (totalRows <= 0) totalRows = engineEstimate
    if (totalRows <= 0) return { remains: null, finishAt: null, cardClass: '', accuracy: null }

    const remainingRows = Math.max(0, totalRows - processedSoFar)
    if (remainingRows <= 0) {
      return { remains: '완료 직전', finishAt: _fmtFinishAt(now), cardClass: 'eta-soon', accuracy: null }
    }
    if (blendedAvg < 1) return { remains: null, finishAt: null, cardClass: '', accuracy: null }
    remainingSec = remainingRows / blendedAvg
  }

  if (remainingSec < 1) {
    return { remains: '완료 직전', finishAt: _fmtFinishAt(now), cardClass: 'eta-soon', accuracy: null }
  }

  // v90.22 (2026-04-26): "재계산 중" 무한 루프 해결
  //
  // 본부장님 피드백:
  //   - 61/62 테이블 완료, 마지막 거대 테이블 1개 남음
  //   - 평균 속도 기반 계산이 70배 변동
  //   - "재계산 중..." 무한 표시 → 사용자에게 의미 없음
  //
  // 새 알고리즘 (단순화):
  //   - 테이블별 합산 ETA 그대로 표시 (이미 정확)
  //   - 최근 5개 평균만 사용 (smoothing 1단계로 축소)
  //   - 단조 감소 억제 / 재계산 표시 모두 제거
  //   - 정확도가 떨어져 보여도 "구체적 숫자" 가 "재계산 중" 보다 유용
  
  const rawRemainSec = remainingSec
  
  // 최근 N개 ETA 의 평균 (간단 smoothing - 흔들림만 약간 완화)
  if (!Array.isArray(etaRecentSamples.value)) {
    etaRecentSamples.value = []
  }
  etaRecentSamples.value.push(rawRemainSec)
  if (etaRecentSamples.value.length > 5) {
    etaRecentSamples.value.shift()  // 최근 5개만
  }
  // 단순 평균
  const sum = etaRecentSamples.value.reduce((a, b) => a + b, 0)
  const smoothedSec = sum / etaRecentSamples.value.length
  
  const displaySec = Math.max(1, Math.round(smoothedSec))
  const finishMs   = now + displaySec * 1000
  const remains    = _fmtRemain(displaySec)
  const finishAt   = _fmtFinishAt(finishMs)
  const cardClass  = displaySec < 60 ? 'eta-soon' : displaySec < 300 ? 'eta-near' : ''
  
  // 정확도 힌트 — 대기 테이블 속도 추정이 섞이면 표시
  let accuracy = null
  if (usedPerTable && anyUnknown) {
    accuracy = '일부 테이블 속도 미확정 — 추정치 포함'
  }
  
  // v90.23: 처리 대기 객체 있으면 알림 (ETA 에 추정 시간 포함됨)
  if (pendingObjects > 0) {
    accuracy = (accuracy ? accuracy + ' · ' : '') + `오브젝트 ${pendingObjects}개 추정치 포함`
  }
  
  // 마지막 1~2 테이블 남았으면 알려주기 (현재 표시 ETA 의 의미 명확화)
  const remainingTableCount = (Number(j.table_total) || 0) - (Number(j.table_done) || 0)
  if (remainingTableCount === 1) {
    accuracy = (accuracy ? accuracy + ' · ' : '') + '마지막 테이블 진행 중'
  } else if (remainingTableCount > 1 && remainingTableCount <= 3) {
    accuracy = (accuracy ? accuracy + ' · ' : '') + `남은 테이블 ${remainingTableCount}개`
  }
  
  return { remains, finishAt, cardClass, accuracy }
})
const sortKey = ref('')
const sortDir = ref('asc')
function setSort(key) {
  if (sortKey.value === key) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else { sortKey.value = key; sortDir.value = 'asc' }
}

const allItems = computed(()=>{
  if(!job.value) return []
  // v92p16 (2026-04-30): 유령 항목 필터링
  //   본부장님 호소: 빈 ○ 38개가 표시됨
  //   원인: 백엔드가 src_bare 와 tgt_table 두 키로 같은 테이블을 등록 (이전 잔재).
  //   안전망: status/type 도 없고 시작/완료 시간도 없는 항목은 표시 제외.
  //          (백엔드 v92p16 패치로 신규 Job 은 자동 해소되지만, 기존 Job 화면 보호)
  //
  // v95_p17 (2026-05-03): 첫 시도 — return false (type 만 있어도 제외)
  //   → 본부장님 환경에 미작동
  //
  // v95_p22 (2026-05-03): 진짜 본질 확정 — 본부장님 콘솔 진단 결과:
  //   Person_AddressType → {checkpoint, rows_src:6, rows_tgt:6, rows_total:6, speed:17}
  //   - rows 데이터는 있음 (이관은 됨)
  //   - 그러나 type/status/started_at/finished_at 모두 없음 ← schema_name 중복 잔재!
  //   - 이미 위에 bare name (AddressType) 으로 정상 표시됨
  //   - 화면에 ○ 로 보이는 이유: type 필드 없어서 아이콘 결정 안 됨
  //
  // 본질 처방: type 없으면 schema_name 중복 잔재로 판단 → 제외
  //   (본부장님 v95_p15 의 양방향 등록 처방 — 95% 도달 핵심 — 은 그대로 유지.
  //    프론트 가드만 추가로 정제.)
  return Object.entries(job.value.item_statuses||{})
    .map(([name,v])=>({name,...v}))
    .filter(item => {
      // v95_p22: type 필드가 없으면 schema_name 중복 잔재 → 무조건 제외
      //   (정상 항목은 백엔드가 type='table'/'function'/... 항상 설정함)
      if (!item.type) return false
      // 이하 v95_p17 가드 (type 있는 항목 중 의미 있는 것만 표시)
      if (item.status && item.status !== '') return true
      if (item.started_at || item.finished_at) return true
      if (item.rows || item.rows_total || item.rows_src || item.rows_tgt) return true
      // type 만 있고 나머지 다 비어있으면 → pending 객체 (정상 표시)
      return true
    })
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

// v9 패치 #34: 현재 테이블 잔여 시간
// 테이블 단독 속도 우선, 없으면 Job 전체 speed 사용
const currentTableEta = computed(() => {
  const j = job.value
  if (!j || j.status !== 'running') return null
  const done  = Number(j.current_table_rows_done || 0)
  const total = Number(j.current_table_rows_total || 0)
  if (total <= 0 || done >= total) return null

  // item_statuses 에서 현재 테이블의 speed 를 우선 사용
  let rps = 0
  const curName = j.current_table
  if (curName && j.item_statuses && j.item_statuses[curName]) {
    rps = Number(j.item_statuses[curName].speed || 0)
  }
  // 폴백: Job 전체 speed
  if (rps < 1) rps = Number(j.speed || 0)
  if (rps < 1) return null

  const remainSec = Math.max(1, Math.round((total - done) / rps))
  return fmtEtaSec(remainSec)
})

// 초 → 사람친화 (짧게): "45초", "2분 30초", "1시간 05분"
function fmtEtaSec(sec) {
  if (!sec || sec < 0) return '—'
  if (sec < 60) return sec + '초'
  const m = Math.floor(sec / 60)
  const s = sec % 60
  if (m < 60) return s > 0 ? `${m}분 ${s}초` : `${m}분`
  const h = Math.floor(m / 60)
  const mm = m % 60
  return mm > 0 ? `${h}시간 ${String(mm).padStart(2,'0')}분` : `${h}시간`
}

// v9 패치 #30: KPI "처리 행" — 완료 테이블 합 + 진행 중 테이블 현재값
// 백엔드 rows_processed 는 "테이블 완료 시점" 에만 누적되므로
// 진행 중 테이블 rows 를 추가해야 실제 누적 수치와 일치
const rowsProcessedLive = computed(() => {
  if (!job.value) return 0
  const items = job.value.item_statuses || {}
  let total = 0
  for (const [name, st] of Object.entries(items)) {
    if (!st || st.type !== 'table') continue
    if (st.status === 'done' || st.status === 'completed') {
      total += Number(st.rows_tgt || st.rows_src || st.rows || 0)
    } else if (st.status === 'running') {
      total += Number(st.rows_tgt || 0)
    }
  }
  return total
})

// v9 패치 #30: 전체 행수 — 테이블별 확정값(rows_total) 합계를 우선.
// 엔진 초기 추정값 rows_total 보다 정확.
const rowsTotalLive = computed(() => {
  if (!job.value) return 0
  const items = job.value.item_statuses || {}
  let itemSum = 0
  let runningOrDoneCount = 0
  let totalTableCount = 0
  for (const [name, st] of Object.entries(items)) {
    if (!st || st.type !== 'table') continue
    totalTableCount++
    const rt = Number(st.rows_total || st.rows_src || 0)
    if (rt > 0) {
      itemSum += rt
      runningOrDoneCount++
    }
  }
  // v9 패치 #41: 대기 테이블은 rows_total 이 0 일 수 있음
  // → 엔진 초기 추정값 job.rows_total 과 비교해 더 큰 값 사용
  // (완료/진행 중인 테이블만 집계되면 총합이 과소 측정됨)
  const engineEstimate = Number(job.value.rows_total || 0)
  if (itemSum > 0 && engineEstimate > 0) {
    // 모든 테이블의 rows_total 이 채워졌으면 item 합계 사용 (더 정확)
    // 일부만 채워졌으면 engine 추정치와 max
    if (runningOrDoneCount >= totalTableCount) return itemSum
    return Math.max(itemSum, engineEstimate)
  }
  return Math.max(itemSum, engineEstimate)
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

// ═══ v10: 긴 목록 드래그 해소 — 점프 툴바 기능 ═══
const itemTableRef  = ref(null)
const jumpToRow     = ref(null)
const scrollProgress = ref(0)

function hasStatus(s) {
  return filteredItems.value.some(i => i.status === s)
}
function scrollItemsTop() {
  const el = itemTableRef.value
  if (!el) { window.scrollTo({top:0, behavior:'smooth'}); return }
  el.scrollTo({ top: 0, behavior: 'smooth' })
}
function scrollItemsBottom() {
  const el = itemTableRef.value
  if (!el) { window.scrollTo({top: document.body.scrollHeight, behavior:'smooth'}); return }
  el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
}
function scrollToRow(n) {
  if (!n || n < 1) return
  const idx = Math.max(0, Math.min(filteredItems.value.length - 1, Math.floor(n) - 1))
  scrollToIndex(idx)
}
function scrollToIndex(idx) {
  const el = itemTableRef.value
  if (!el) return
  const rows = el.querySelectorAll('.item-row')
  if (rows[idx]) {
    rows[idx].scrollIntoView({ behavior: 'smooth', block: 'center' })
    rows[idx].classList.add('jump-flash')
    setTimeout(() => rows[idx].classList.remove('jump-flash'), 1400)
  }
}
function scrollToNextStatus(status) {
  const list = filteredItems.value
  if (!list.length) return
  const el = itemTableRef.value
  if (!el) return
  const rows = el.querySelectorAll('.item-row')
  if (!rows.length) return

  const viewportTop = el.scrollTop
  const viewportCenter = viewportTop + el.clientHeight / 2
  let currentIdx = 0
  rows.forEach((r, i) => {
    if (r.offsetTop <= viewportCenter) currentIdx = i
  })

  let targetIdx = -1
  for (let i = currentIdx + 1; i < list.length; i++) {
    if (list[i].status === status) { targetIdx = i; break }
  }
  if (targetIdx < 0) {
    for (let i = 0; i <= currentIdx; i++) {
      if (list[i].status === status) { targetIdx = i; break }
    }
  }
  if (targetIdx >= 0) scrollToIndex(targetIdx)
}
function updateScrollProgress() {
  const el = itemTableRef.value
  if (!el) { scrollProgress.value = 0; return }
  const max = el.scrollHeight - el.clientHeight
  if (max <= 0) { scrollProgress.value = 0; return }
  scrollProgress.value = Math.min(100, Math.max(0, (el.scrollTop / max) * 100))
}
onMounted(() => {
  const attach = () => {
    const el = itemTableRef.value
    if (el) {
      el.addEventListener('scroll', updateScrollProgress, { passive: true })
      updateScrollProgress()
    }
  }
  setTimeout(attach, 100)
  window.addEventListener('keydown', handleMonitorKeydown)
})
onUnmounted(() => {
  window.removeEventListener('keydown', handleMonitorKeydown)
  const el = itemTableRef.value
  if (el) el.removeEventListener('scroll', updateScrollProgress)
})
function handleMonitorKeydown(e) {
  if (e.target && ['INPUT','TEXTAREA'].includes(e.target.tagName)) return
  if (!itemTableRef.value) return
  if (e.altKey && e.key === 'Home')      { e.preventDefault(); scrollItemsTop() }
  else if (e.altKey && e.key === 'End')  { e.preventDefault(); scrollItemsBottom() }
  else if (e.altKey && e.key.toLowerCase() === 'e') { e.preventDefault(); scrollToNextStatus('error') }
  else if (e.altKey && e.key.toLowerCase() === 'r') { e.preventDefault(); scrollToNextStatus('running') }
}
// ═══ /v10 점프 기능 ═══

// ════════════════════════════════════════════════════════════════════
// v90.60 (2026-04-28): 진행 중 표시 데이터 fallback
//   본부장님 환경: kyc_document 진행 중인데 item_statuses[].rows_src 가
//                 0/없음 으로 보이는 케이스 (LIVE 배너는 정상 표시되는데).
//   원인 후보: backend 가 current_table_rows_done 만 갱신, item_statuses
//              갱신은 race condition / 타이밍 이슈로 누락
//   처방: 이 행이 현재 진행 중 테이블 (item.name === job.current_table) 이면
//        top-level current_table_rows_done / current_table_rows_total 을
//        fallback 으로 사용. 양쪽 모두 backend 가 적극 갱신하는 필드.
// ════════════════════════════════════════════════════════════════════
function _isCurrentTable(item) {
  const j = job.value
  return j && j.current_table && item && item.name === j.current_table
}
function _displayRowsDone(item) {
  // 우선순위: item.rows_tgt > item.rows_src > current_table_rows_done (현재 테이블만)
  const v = Number(item.rows_tgt || item.rows_src || 0)
  if (v > 0) return v
  if (_isCurrentTable(item)) {
    return Number(job.value.current_table_rows_done || 0)
  }
  return 0
}
function _displayRowsTotal(item) {
  // 우선순위: item.rows_total > current_table_rows_total (현재 테이블만)
  const v = Number(item.rows_total || 0)
  if (v > 0) return v
  if (_isCurrentTable(item)) {
    return Number(job.value.current_table_rows_total || 0)
  }
  return 0
}

function progLabel(item){
  if(item.status==='done') return '100%'
  if(item.status==='running') {
    // v9 패치 #24: 병렬 처리 대응 - 테이블별 개별 진행률
    // 1) item 에 total 있고 tgt 가 있으면 그걸로 계산
    // 2) v90.60: 없으면 top-level fallback (현재 테이블 일치 시)
    // 3) 그것도 없으면 전역 tableProgress (단일 실행일 때만 맞음)
    const tgt = Number(item.rows_tgt || 0)
    const total = Number(item.rows_total || item.rows || 0)
    if (total > 0 && tgt > 0) {
      return Math.min(100, Math.round(tgt / total * 100)) + '%'
    }
    // v90.60 fallback
    if (_isCurrentTable(item)) {
      const fallbackDone = Number(job.value.current_table_rows_done || 0)
      const fallbackTotal = Number(job.value.current_table_rows_total || 0)
      if (fallbackTotal > 0) {
        return Math.min(100, Math.round(fallbackDone / fallbackTotal * 100)) + '%'
      }
    }
    return tableProgress.value + '%'
  }
  if(item.status==='error') return '오류'
  return '대기'
}
function statusLabel(s){ return {running:'진행중',done:'완료',pending:'대기',error:'오류',completed:'완료',idle:'대기',aborted:'중단'}[s]??s }

// v95_p107 hotfix_013 (2026-05-10 본부장님 본질 처방):
//   변환 경로 (conversion_path) 배열 → 한 눈에 읽는 라벨
//   예: ["rule_fail","ai_ollama_ok"]  → "실패→AI(Gemma)성공"
//       ["kb_match"]                  → "KB 매칭"
//       ["rule_ok"]                   → "" (단순 완료, 라벨 생략)
//       ["rule_fail","ai_ollama_fail","ai_anthropic_ok"]
//                                     → "실패→AI(Gemma)실패→AI(Claude)성공"
const __PROVIDER_LBL = { anthropic:'Claude', ollama:'Ollama', gemma:'Gemma', claude:'Claude', openai:'OpenAI' }
function _pathStep(step) {
  if (!step) return ''
  if (step === 'rule')        return 'Rule'
  if (step === 'rule_ok')     return ''  // 단순 완료는 라벨 없음
  if (step === 'rule_fail')   return '실패'
  if (step === 'kb_match')    return 'KB매칭'
  if (step === 'kb_miss')     return 'KB매칭없음'  // v95_p107_hotfix_042_v2
  if (step === 'ai_initial')  return 'AI'
  const m = step.match(/^ai_([a-z0-9]+?)(_ok|_fail)?$/)
  if (m) {
    const prov = __PROVIDER_LBL[m[1]] || m[1]
    const tail = m[2] === '_ok' ? '응답수신' : (m[2] === '_fail' ? '응답없음' : '')
    return tail ? `AI(${prov})${tail}` : `AI(${prov})`
  }
  return step
}
function conversionPathLbl(path, itemStatus) {
  // v95_p107_hotfix_042_v2: MySQL 실행 결과까지 정확히 표시 (본부장님 모토 #14)
  if (!path || !path.length) return ''
  // 단순 완료 (rule_ok 만) 는 라벨 생략 — 기존 "완료" 표기에 위임
  if (path.length === 1 && path[0] === 'rule_ok') return ''
  const base = path.map(_pathStep).filter(Boolean).join('→')
  // AI 응답수신 단계가 있으면 MySQL 실행 결과 추가
  if (base && itemStatus && base.includes('응답수신')) {
    if (itemStatus === 'done')   return base + '→MySQL성공'
    if (itemStatus === 'error')  return base + '→MySQL실패'
  }
  return base
}

// v95_p107 hotfix_045: 과정/결과 분리 표시 (본부장님 — 결과만 색깔 강조)
function conversionProcessLbl(path, itemStatus) {
  const full = conversionPathLbl(path, itemStatus)
  if (!full) return ''
  if (full.endsWith('성공')) return full.slice(0, -2)
  if (full.endsWith('실패')) return full.slice(0, -2)
  if (full.endsWith('응답없음')) return full.slice(0, -4)
  return full
}
function conversionOutcomeCode(path, itemStatus) {
  const full = conversionPathLbl(path, itemStatus)
  if (!full) return ''
  if (full.endsWith('성공')) return 'ok'
  if (full.endsWith('실패')) return 'ng'
  if (full.endsWith('응답없음')) return 'ng'
  return ''
}
function conversionOutcomeLbl(path, itemStatus) {
  const full = conversionPathLbl(path, itemStatus)
  if (!full) return ''
  if (full.endsWith('성공')) return '성공'
  if (full.endsWith('실패')) return '실패'
  if (full.endsWith('응답없음')) return '응답없음'
  return ''
}

// phase 순서 정의
// v92p12 (2026-04-30): ADVISOR_APPLY 단계 추가 — AI DBA 권고 자동 적용
const PHASE_ORDER = ['FK_DISABLE','RUNNING','OBJECTS','ADVISOR_APPLY','FK_RESTORE','DONE']
const isCdc = computed(() => job.value?.job_type === 'cdc')

// v92p12: AI DBA 권고가 적용 결정된 게 있는지 (단계 표시 여부)
const hasAdvisorDecisions = computed(() => {
  const decs = job.value?.advisor_decisions || []
  return decs.some(d => d?.decision === 'applied' || d?.decision === 'edited')
})
// v92p12: 권고 적용 단계 진행률 (백엔드 self.job["advisor_apply"] 미러)
const advisorApplyProgress = computed(() => {
  const ap = job.value?.advisor_apply
  if (!ap || !ap.total) return null
  return {
    total:  ap.total || 0,
    done:   ap.done || 0,
    failed: ap.failed || 0,
    current: ap.current || '',
  }
})

// v92p6 (2026-04-30): phase 정체 감지 — FK_DISABLE 등에서 stuck 되는지 카운트
const phaseStuckSec = ref(0)
let _phaseStuckTimer = null
let _lastPhase = null
let _phaseStartedAt = Date.now()
function _trackPhaseStuck() {
  const cur = job.value?.phase || ''
  if (cur !== _lastPhase) {
    _lastPhase = cur
    _phaseStartedAt = Date.now()
    phaseStuckSec.value = 0
    return
  }
  if (job.value?.status === 'running') {
    phaseStuckSec.value = Math.floor((Date.now() - _phaseStartedAt) / 1000)
  } else {
    phaseStuckSec.value = 0
  }
}
onMounted(() => {
  _phaseStuckTimer = setInterval(_trackPhaseStuck, 1000)
})
onUnmounted(() => {
  if (_phaseStuckTimer) { clearInterval(_phaseStuckTimer); _phaseStuckTimer = null }
})

async function cancelStuckJob() {
  if (!job.value?.id) return
  if (!confirm(`Job ${job.value.id.substring(0,8)} 을 중단할까요? (FK 단계 stuck)`)) return
  try {
    await axios.post(`/api/v1/jobs/${job.value.id}/stop`)
    app.notify('중단 요청 전송됨', 'success')
  } catch (e) {
    app.notify('중단 실패: ' + e.message, 'error')
  }
}

// v92p15 (2026-04-30): AI 자동 재이관 실시간 토글
//   본부장님 호소: "JobMonitor 의 자동이관 배지 클릭이 안 된다"
//   진행 중인 Job 의 ai_auto_retry 플래그를 즉시 변경 → 다음 객체 이관부터 반영.
const aiToggleBusy = ref(false)
async function toggleAiAutoRetry() {
  if (!job.value?.id) return
  if (aiToggleBusy.value) return
  if (!['running','paused'].includes(job.value.status)) {
    app.notify('진행 중이거나 일시정지된 Job 만 토글 가능합니다', 'warn')
    return
  }
  const newVal = !job.value.ai_auto_retry
  // 사용자 명시 확인 (실수 방지)
  const confirmMsg = newVal
    ? '🤖 AI 자동 재이관을 켤까요?\n\n실패한 객체를 백엔드가 자동으로 AI 재시도합니다.\n다음 객체 이관부터 즉시 반영됩니다.'
    : '🤖 AI 자동 재이관을 끌까요?\n\n앞으로 실패한 객체는 멈춥니다.\n수동으로 🤖 AI 재이관 버튼을 눌러야 재시도됩니다.'
  if (!confirm(confirmMsg)) return

  aiToggleBusy.value = true
  try {
    const { data } = await axios.patch(
      `/api/v1/jobs/${job.value.id}/ai-auto-retry`,
      { enabled: newVal }
    )
    // 즉시 화면 반영 (서버 응답 기다리지 않음, polling 으로도 결국 갱신됨)
    job.value.ai_auto_retry = data.ai_auto_retry
    if (data.ai_retry_count != null) job.value.ai_retry_count = data.ai_retry_count
    app.notify(
      `🤖 AI 자동 재이관 ${newVal ? 'ON' : 'OFF'} 적용됨`,
      'success'
    )
  } catch (e) {
    app.notify(
      'AI 자동 재이관 토글 실패: ' + (e.response?.data?.detail || e.message),
      'error'
    )
  } finally {
    aiToggleBusy.value = false
  }
}

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
function typeLabelShort(t){ return {table:'TABLE',view:'VIEW',procedure:'PROC',function:'FUNC',trigger:'TRIG'}[t] ?? (t || '').toString().toUpperCase() }
function fmtNum(n){ if(!n&&n!==0) return '0'; return Number(n).toLocaleString() }


function elapsedClass(item) {
  if (!item.started_at) return 'elapsed-none'
  if (item.status === 'running') return 'elapsed-running'
  if (item.status === 'error')   return 'elapsed-error'
  if (item.status === 'done')    return 'elapsed-done'
  return 'elapsed-none'
}
// running 항목의 예상 남은 시간 (현재 테이블 rows 기반)
function fmtItemEta(item) {
  if (item.status !== 'running') return ''
  const j = job.value
  if (!j) return ''
  // v9 패치 #37: 아이템별 개별 계산 — 이전엔 job.current_* 만 써서
  // 모든 테이블에 같은 ETA 가 표시됨 (버그)
  const itemSt = (j.item_statuses || {})[item.name] || {}

  // 이 테이블의 총 rows (rows_total > rows_src > item.rows 순)
  // v90.60: 모두 비어있고 현재 테이블이면 top-level current_table_rows_total fallback
  let total = Number(itemSt.rows_total || itemSt.rows_src || item.rows_src || item.rows || 0)
  // 이 테이블에 이미 삽입된 rows
  let done  = Number(itemSt.rows_tgt || 0)
  if (total <= 0 && _isCurrentTable(item)) {
    total = Number(j.current_table_rows_total || 0)
  }
  if (done <= 0 && _isCurrentTable(item)) {
    done = Number(j.current_table_rows_done || 0)
  }
  if (total <= 0 || done >= total) return ''

  // 이 테이블의 실시간 속도 (item_statuses[name].speed)
  // 없으면 Job 전체 speed 를 폴백으로 (여러 테이블 병렬일 땐 부정확할 수 있음)
  let rps = Number(itemSt.speed || 0)
  if (rps < 1) {
    // 폴백: Job 전체 speed 를 병렬 테이블 수로 나눔 (근사)
    const runningCount = Object.values(j.item_statuses || {}).filter(
      s => s && s.type === 'table' && s.status === 'running'
    ).length || 1
    rps = Number(j.speed || 0) / runningCount
  }
  if (rps < 1) return ''

  const remainSec = Math.round((total - done) / rps)
  if (remainSec <= 0) return ''
  const h = Math.floor(remainSec / 3600)
  const m = Math.floor((remainSec % 3600) / 60)
  const s = remainSec % 60
  if (h > 0) return h + '시간 ' + String(m).padStart(2,'0') + '분 ' + String(s).padStart(2,'0') + '초'
  if (m > 0) return m + '분 ' + String(s).padStart(2,'0') + '초'
  return s + '초'
}

// v10 #26: 현재 실행 중인 테이블의 잔여시간 + 이름
//   - 병렬로 여러 개 돌고 있으면 "가장 큰 테이블" (진행률 낮은 것) 기준
//   - 없거나 측정 불가면 빈 문자열
// v90.25: 진행 중 항목 - 테이블 + 객체 (SP/Function/View/Trigger) 모두 포함
//   본부장님 지적: "테이블 다 끝났는데 트리거 진행 중인데 '대기' 로 표시 + 현재 작업 — 표시"
//   원인: 기존엔 type === 'table' 만 인식
//   해결: 객체 타입도 모두 인식
const RUNNING_ITEM_TYPES = new Set(['table', 'function', 'procedure', 'view', 'trigger'])

const runningItems = computed(() => {
  const j = job.value
  if (!j || !j.item_statuses) return []
  return Object.entries(j.item_statuses)
    .filter(([_, st]) => st && RUNNING_ITEM_TYPES.has(st.type) && st.status === 'running')
    .map(([name, st]) => ({ name, ...st }))
})

const currentRunningItem = computed(() => {
  const items = runningItems.value
  if (!items.length) return null
  
  // v90.25: 우선순위 - 테이블이 가장 우선 (큰 작업), 없으면 객체
  //   - 테이블 진행 중: 가장 많이 남은 것
  //   - 테이블 없음: 첫 번째 객체 (보통 1~2개만 동시 진행)
  const tables = items.filter(it => it.type === 'table')
  if (tables.length > 0) {
    return tables.reduce((biggest, cur) => {
      const curLeft = Number(cur.rows_total || 0) - Number(cur.rows_tgt || 0)
      const bigLeft = Number(biggest.rows_total || 0) - Number(biggest.rows_tgt || 0)
      return curLeft > bigLeft ? cur : biggest
    })
  }
  // 객체 진행 중 → 첫 번째 (보통 동시 1~4개)
  return items[0]
})

const currentTaskEta = computed(() => {
  const it = currentRunningItem.value
  if (!it) return ''
  
  // v90.25: 객체는 행수 기반 ETA 계산 불가 → 추정 시간 표시
  if (it.type !== 'table') {
    const OBJ_TIME = { function: 90, procedure: 120, view: 30, trigger: 60 }
    const estSec = OBJ_TIME[it.type] || 60
    // 시작 시각 알면 경과 시간 빼기
    if (it.started_at) {
      const elapsed = Math.floor((Date.now() - new Date(it.started_at).getTime()) / 1000)
      const remain = Math.max(5, estSec - elapsed)
      return `약 ${fmtEtaSec(remain)} (추정)`
    }
    return `약 ${fmtEtaSec(estSec)} (추정)`
  }
  
  // 테이블 - 기존 정확 계산
  return fmtItemEta({ name: it.name, status: 'running' })
})

// v90.25: 현재 작업 이름 + 타입 (트리거/SP 등 표시)
const currentTaskName = computed(() => {
  const it = currentRunningItem.value
  if (!it) return ''
  // 객체는 type 도 함께 표시 - "crec_recfile_upd (TRIGGER)"
  if (it.type !== 'table') {
    const typeLabel = {
      function:  '함수',
      procedure: 'SP',
      view:      'View',
      trigger:   '트리거',
    }[it.type] || (it.type || '').toString().toUpperCase()
    return `${it.name} (${typeLabel})`
  }
  return it.name
})

function toggleDetail(name){ expanded.value={...expanded.value,[name]:!expanded.value[name]} }

const remigTarget    = ref(null)
const objRemigTarget = ref(null)
const objRemigMode   = ref('drop_recreate')
const objRemigRunning = ref(false)
const remigMode    = ref('skip_geo')
const remigRunning = ref(false)
const showErrModal = ref(false)

// ── v95_p107 hotfix_046: 오류 상세 모달 → 플로팅 윈도우 ─────────────
const errMinimized   = ref(false)
const errFloatPos    = ref({ x: 0, y: 0, w: 680, h: 600 })
let   _errFloatInited = false
function _initErrFloatPos() {
  if (_errFloatInited) return
  const W = 680
  const H = Math.min((window.innerHeight || 800) * 0.8, 700)
  errFloatPos.value = {
    x: Math.max(10, Math.round(((window.innerWidth  || 1200) - W) / 2)),
    y: Math.max(10, Math.round(((window.innerHeight || 800)  - H) / 2)),
    w: W,
    h: Math.round(H),
  }
  _errFloatInited = true
}
const errFloatStyle = computed(() => {
  _initErrFloatPos()
  return {
    position: 'fixed',
    left: errFloatPos.value.x + 'px',
    top:  errFloatPos.value.y + 'px',
    width:  errFloatPos.value.w + 'px',
    height: errMinimized.value ? 'auto' : (errFloatPos.value.h + 'px'),
    maxWidth: '95vw',
    maxHeight: '95vh',
    background: 'var(--bg-primary)',
    borderRadius: '14px',
    display: 'flex',
    flexDirection: 'column',
    boxShadow: '0 8px 40px rgba(0,0,0,.3)',
    overflow: 'hidden',
    zIndex: 9999,
    pointerEvents: 'auto',
  }
})
const { startDrag: startErrDrag } = useDragFloat({
  pos: errFloatPos,
  onMove: (x, y) => { errFloatPos.value = { ...errFloatPos.value, x, y } },
})

// v95_p107 hotfix_051: 모달 resize (우하단 핸들 드래그)
function startErrResize(e) {
  if (e.button !== undefined && e.button !== 0) return
  const startX = e.clientX, startY = e.clientY
  const startW = errFloatPos.value.w
  const startH = errFloatPos.value.h
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'nwse-resize'
  function onMove(ev) {
    const nw = Math.max(420, Math.round(startW + (ev.clientX - startX)))
    const nh = Math.max(320, Math.round(startH + (ev.clientY - startY)))
    errFloatPos.value = { ...errFloatPos.value, w: nw, h: nh }
  }
  function onUp() {
    document.body.style.userSelect = ''
    document.body.style.cursor = ''
    document.removeEventListener('pointermove', onMove)
  }
  document.addEventListener('pointermove', onMove)
  document.addEventListener('pointerup', onUp, { once: true })
  document.addEventListener('pointercancel', onUp, { once: true })
  e.preventDefault()
  e.stopPropagation()
}
// ── /h046 ────────────────────────────────────────────────────────

// ── 일괄 재이관 상태 ──────────────────────────────────────────
const bulkSelected   = ref(new Set())   // 선택된 항목명 Set
const showBulkModal  = ref(false)
const bulkMode       = ref('drop_recreate')
const bulkRunning    = ref(false)
const bulkDoneCount  = ref(0)
const bulkTotal      = ref(0)
const bulkProgress   = ref(0)
const bulkCurrentName = ref('')
const bulkResult     = ref([])   // [{name, ok, msg}]

// 오류 항목 중 전체 선택 여부
const isBulkAllErrSelected = computed(() => {
  const errNames = errItems.value.map(i => i.name)
  return errNames.length > 0 && errNames.every(n => bulkSelected.value.has(n))
})
// 현재 필터된 오류 항목 전체 선택 여부
const isBulkAllSelected = computed(() => {
  const errFiltered = filteredItems.value.filter(i => i.status === 'error')
  return errFiltered.length > 0 && errFiltered.every(i => bulkSelected.value.has(i.name))
})

function toggleBulkItem(name) {
  const s = new Set(bulkSelected.value)
  s.has(name) ? s.delete(name) : s.add(name)
  bulkSelected.value = s
}

function toggleBulkAllErr() {
  const errNames = errItems.value.map(i => i.name)
  const s = new Set(bulkSelected.value)
  if (isBulkAllErrSelected.value) {
    errNames.forEach(n => s.delete(n))
  } else {
    errNames.forEach(n => s.add(n))
  }
  bulkSelected.value = s
}

function toggleBulkAll() {
  const errFiltered = filteredItems.value.filter(i => i.status === 'error')
  const s = new Set(bulkSelected.value)
  if (isBulkAllSelected.value) {
    errFiltered.forEach(i => s.delete(i.name))
  } else {
    errFiltered.forEach(i => s.add(i.name))
  }
  bulkSelected.value = s
}

function openBulkModal() {
  // ── 선택 항목 분석 → 자동 이관 방식 결정 ──────────────────
  const items = [...bulkSelected.value]
    .map(name => allItems.value.find(i => i.name === name))
    .filter(Boolean)

  const OBJ_TYPES = ['function','procedure','trigger','view']
  const hasObj   = items.some(i => OBJ_TYPES.includes(i.type))
  const hasTable = items.some(i => i.type === 'table')

  if (hasObj && !hasTable) {
    // 오브젝트만 → AI 변환이 가장 효과적
    bulkMode.value = 'ai'
  } else if (hasTable && !hasObj) {
    // 테이블만 → DROP 후 재생성
    bulkMode.value = 'drop_recreate'
  } else {
    // 혼합 → AI (오브젝트에 최적화)
    bulkMode.value = 'ai'
  }

  bulkResult.value = []
  bulkDoneCount.value = 0
  bulkProgress.value = 0
  bulkCurrentName.value = ''
  showBulkModal.value = true
}

// ── 항목 완료 대기 폴링 (running 상태 벗어날 때까지) ──────────
async function _waitItemDone(name, maxSec = 120) {
  const intervalMs = 2000
  const maxTries   = Math.ceil((maxSec * 1000) / intervalMs)
  for (let i = 0; i < maxTries; i++) {
    await new Promise(r => setTimeout(r, intervalMs))
    await loadJob()
    const st = job.value?.item_statuses?.[name]?.status
    if (st && st !== 'running') return st  // 'done' | 'error'
  }
  return 'timeout'
}

async function doBulkRemig() {
  if (!job.value || bulkRunning.value || bulkSelected.value.size === 0) return
  bulkRunning.value = true
  bulkResult.value = []
  bulkDoneCount.value = 0

  const items = [...bulkSelected.value]
    .map(name => allItems.value.find(i => i.name === name))
    .filter(Boolean)
  bulkTotal.value = items.length

  const OBJ_TYPES = ['function','procedure','trigger','view']

  for (let idx = 0; idx < items.length; idx++) {
    const item = items[idx]
    bulkCurrentName.value = item.name
    bulkProgress.value = Math.round((idx / items.length) * 100)

    // UI 즉시 running으로 반영
    if (job.value.item_statuses?.[item.name]) {
      job.value.item_statuses[item.name].status = 'running'
      job.value.item_statuses[item.name].error  = null
    }

    try {
      const isObj = OBJ_TYPES.includes(item.type)
      let res

      if (isObj) {
        // 오브젝트 재이관 (백그라운드 실행 → 완료 대기 필요)
        res = await fetch('/api/v1/jobs/' + job.value.id + '/remig-object', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name:          item.name,
            type:          item.type,
            mode:          bulkMode.value === 'rules' ? 'drop_recreate' : bulkMode.value,
            obj_engine:    bulkMode.value === 'ai' ? 'claude' : 'rules',
            force_convert: bulkMode.value === 'rules',
            error_hint:    item.error
          })
        })
        if (res.ok) {
          // ★ 백엔드가 즉시 반환하므로 완료될 때까지 폴링
          const finalSt = await _waitItemDone(item.name)
          const ok = finalSt === 'done'
          const err = job.value?.item_statuses?.[item.name]?.error
          bulkResult.value.push({
            name: item.name,
            ok,
            msg: ok ? '재이관 완료' : finalSt === 'timeout' ? '시간 초과 (120초)' : (err || '오류 발생')
          })
        } else {
          const e = await res.json()
          bulkResult.value.push({ name: item.name, ok: false, msg: e.detail || '요청 실패' })
          if (job.value.item_statuses?.[item.name])
            job.value.item_statuses[item.name].status = 'error'
        }
      } else {
        // 테이블 재이관
        const tableMode = bulkMode.value === 'rules' ? 'original' : bulkMode.value
        res = await fetch('/api/v1/jobs/' + job.value.id + '/remig-table', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            table:           item.name,
            mode:            tableMode,
            error_hint:      item.error,
            error_history:   errorHistory.value[item.name] || [],
            table_mode:      job.value?.table_mode,
            drop_table:      job.value?.drop_table,
            truncate_target: job.value?.truncate_target,
            create_table:    job.value?.create_table
          })
        })
        if (res.ok) {
          const finalSt = await _waitItemDone(item.name, 300)  // 테이블은 5분까지
          const ok = finalSt === 'done'
          const err = job.value?.item_statuses?.[item.name]?.error
          bulkResult.value.push({
            name: item.name,
            ok,
            msg: ok ? '재이관 완료' : finalSt === 'timeout' ? '시간 초과' : (err || '오류 발생')
          })
        } else {
          const e = await res.json()
          bulkResult.value.push({ name: item.name, ok: false, msg: e.detail || '요청 실패' })
          if (job.value.item_statuses?.[item.name])
            job.value.item_statuses[item.name].status = 'error'
        }
      }
    } catch(e) {
      bulkResult.value.push({ name: item.name, ok: false, msg: e.message })
      if (job.value.item_statuses?.[item.name])
        job.value.item_statuses[item.name].status = 'error'
    }

    bulkDoneCount.value = idx + 1
  }

  bulkProgress.value = 100
  bulkCurrentName.value = ''
  bulkRunning.value = false
  bulkSelected.value = new Set()
  await loadJob()
}
function openErrModal() { showErrModal.value = true }

// 오류 항목 목록 — status=error 또는 batch_errors 있는 항목 (done이어도 포함)
const errItems = computed(() => {
  if (!job.value?.item_statuses) return []
  return Object.entries(job.value.item_statuses)
    .filter(([, v]) =>
      (v.status === 'error' && v.error) ||   // 항목 전체 실패
      v.batch_errors?.length ||              // 배치 부분 실패
      (v.batch_error_rows > 0)              // 행 오류 있음
    )
    .map(([name, v]) => ({ name, ...v }))
    .sort((a, b) => {
      // error 먼저, 그 다음 batch_errors, done 순
      const score = v => v.status === 'error' ? 0 : v.batch_errors?.length ? 1 : 2
      return score(a) - score(b) || (a.finished_at||'').localeCompare(b.finished_at||'')
    })
})
// KPI 카드 빨간색: 항목 오류이거나 batch_error_rows가 있을 때만
const hasAnyError = computed(() => {
  // 현재 item_statuses 기준으로 실제 오류 항목이 있는지만 판단
  // rows_error 숫자가 남아있어도 실제 오류 항목이 없으면 정상 표시
  return errItems.value.length > 0
})

// ═══ v10: 일괄 재처리 기능 ═══
const bulkSelectedRetry = ref(new Set())       // 선택한 item name 들
const bulkFilterType    = ref('')              // '' | 'table' | 'procedure' | ...
const bulkFilterErrCode = ref('')              // '' | '1064' | '1075' | ...
const bulkRetryPanelOpen = ref(false)
const bulkRetryMode     = ref('ai')            // 'ai' | 'drop_recreate' | 'engine_only' | 'passthrough'
const bulkAiMaxRetries  = ref(2)  // v95_p107 hotfix_062: 5→2 (본부장님 토큰 절감)
const bulkConcurrency   = ref(3)  // v95_p107 hotfix_068: 동시 처리 개수 (1=순차, 3=기본, 5/10=병렬)
const bulkRetryRunning  = ref(false)
// v95_p107 hotfix_054: 일괄 재처리 중지 신호
const bulkRetryAborted  = ref(false)
const bulkAbortController = ref(null)  // v95_p107 hotfix_057: AbortController
function abortBulkRetry() {
  bulkRetryAborted.value = true
  // h057: 진행 중 fetch 강제 취소
  if (bulkAbortController.value) {
    try { bulkAbortController.value.abort() } catch (_) {}
  }
  // h057: 진행 중/대기 중 retry 항목 즉시 갱신 (frontend 로컬 — UI spinner 끔)
  const _h057Aborted = []
  for (const name in retryStatusMap.value) {
    const st = retryStatusMap.value[name]
    if (st.status === 'retrying' || st.status === 'queued') {
      const dur = st.startAt ? Math.round((Date.now() - st.startAt) / 1000) : 0
      retryStatusMap.value[name] = {
        ...st,
        status:    'retry_failed',
        lastError: '사용자 중지',
        durationS: dur,
      }
      _h057Aborted.push(name)
      // main monitor 의 item_statuses 도 frontend 로컬 갱신 (spinner 즉시 끔)
      if (job.value?.item_statuses?.[name]) {
        job.value.item_statuses[name] = {
          ...job.value.item_statuses[name],
          status: 'error',
          error:  '사용자 중지 (백엔드 정리 중)',
        }
      }
    }
  }
  // h057: 백엔드에도 stop 신호 (best effort — 일괄 재처리는 별도 thread 라 부분 효과)
  if (job.value?.id) {
    fetch(`/api/v1/jobs/${job.value.id}/stop`, { method: 'POST' }).catch(() => {})
  }
  app.notify(`일괄 재처리 중지 — ${_h057Aborted.length}건 UI 즉시 갱신`, 'warn')
}

// v95_p107 hotfix_048: AI provider 선택 (관리자 등록 AI 중 골라 재처리)
const bulkAiProvider     = ref('')   // '' = 백엔드 기본 설정 사용
const bulkAiModel        = ref('')
const availableProviders = ref([])   // [{ id, name, models, requires, air_gapped }]
const availableModels = computed(() => {
  const p = availableProviders.value.find(p => p.id === bulkAiProvider.value)
  return p?.models || []
})
async function loadAiProviders() {
  try {
    const res = await fetch('/api/v1/ai-providers/list')
    if (!res.ok) return
    const j = await res.json()
    availableProviders.value = Object.entries(j.providers || {}).map(([id, p]) => ({ id, ...p }))
  } catch (e) { /* silent */ }
}
onMounted(loadAiProviders)
watch(bulkAiProvider, () => { bulkAiModel.value = '' })

// 재이관 상태 추적 (item_name → { status, startAt, attempt, maxAttempt, lastError, duration })
const retryStatusMap    = ref({})
// 경과 시간 실시간 업데이트용 tick
const retryTick         = ref(0)
let retryTickTimer      = null

// v10 #33: 일괄 재처리 배치 진행 상태 (팝업 하단 프로그레스 바용)
const bulkBatchTotal    = ref(0)          // 전체 개수
const bulkBatchDone     = ref(0)          // 완료 개수 (성공+실패)
const bulkBatchStartedAt= ref(null)       // 배치 시작 시각

// 배치 진행률 파생 상태
const bulkBatchProgress = computed(() => {
  const total = bulkBatchTotal.value
  if (!total) return 0
  return Math.round((bulkBatchDone.value / total) * 100)
})
const bulkBatchElapsed = computed(() => {
  // retryTick 에 의존해서 매초 재계산
  retryTick.value  // eslint-disable-line no-unused-expressions
  if (!bulkBatchStartedAt.value) return 0
  return Math.floor((Date.now() - bulkBatchStartedAt.value) / 1000)
})
const bulkBatchEtaSec = computed(() => {
  // 완료된 건수로 평균 속도 추정 → 남은 건수 × 평균 시간
  retryTick.value  // eslint-disable-line no-unused-expressions
  const done = bulkBatchDone.value
  const total = bulkBatchTotal.value
  if (!done || done >= total || !bulkBatchStartedAt.value) return null
  const elapsedMs = Date.now() - bulkBatchStartedAt.value
  const avgMsPerItem = elapsedMs / done
  const remain = total - done
  return Math.round((remain * avgMsPerItem) / 1000)
})
function fmtBulkMs(s) {
  if (s == null || s < 0) return '—'
  const m = Math.floor(s / 60), ss = s % 60
  return m > 0 ? `${m}분 ${ss}초` : `${ss}초`
}

// 현재 재처리 중인 항목 이름 (프로그레스 바 하단 표시용)
const bulkCurrentItem = computed(() => {
  for (const [name, st] of Object.entries(retryStatusMap.value)) {
    if (st.status === 'retrying') return { name, ...st }
  }
  return null
})

// 재처리 히스토리 (성공/실패 기록 유지 — errItems 에서 사라진 항목도 팝업에 남김)
const bulkBatchHistory = computed(() => {
  retryTick.value  // eslint-disable-line no-unused-expressions
  const arr = []
  for (const [name, st] of Object.entries(retryStatusMap.value)) {
    if (st.status === 'retry_done' || st.status === 'retry_failed') {
      arr.push({ name, ...st })
    }
  }
  return arr.sort((a, b) => (a.queueIndex||0) - (b.queueIndex||0))
})

// 에러코드 추출 (정규식)
function extractErrCode(errMsg) {
  if (!errMsg) return ''
  const m = String(errMsg).match(/\((\d{4}),/)
  return m ? m[1] : ''
}

// 필터링된 오류 항목
const filteredErrItems = computed(() => {
  // v10 #33: 재처리 세션 중에는 이미 완료된 항목(retryStatusMap 에 기록됨)도 목록에 유지
  //   이전엔 재처리 성공 → errItems 에서 사라짐 → 목록에서 증발 → "방금 뭐가 끝났지?" 확인 불가
  //   개선: errItems + retryStatusMap 의 모든 항목을 합쳐서 렌더링. 완료/실패 항목도 유지.
  const baseItems = errItems.value.slice()
  const seenNames = new Set(baseItems.map(i => i.name))
  // retryStatusMap 에 있지만 errItems 에서 빠진 항목을 다시 추가 (히스토리 유지)
  for (const [name, rs] of Object.entries(retryStatusMap.value)) {
    if (seenNames.has(name)) continue
    // job.item_statuses 에서 원본 메타 가져오기 (type, finished_at 등)
    const orig = job.value?.item_statuses?.[name]
    if (!orig) continue
    baseItems.push({ name, ...orig, _ghost: true })  // _ghost: 이미 처리된 히스토리 항목
  }
  return baseItems.filter(item => {
    if (bulkFilterType.value && item.type !== bulkFilterType.value) return false
    if (bulkFilterErrCode.value) {
      const code = extractErrCode(item.error)
      if (bulkFilterErrCode.value === 'other') {
        if (['1064','1075','1118','1419'].includes(code)) return false
      } else {
        if (code !== bulkFilterErrCode.value) return false
      }
    }
    return true
  }).map(item => {
    // retry_status 붙여서 내려주기
    const rs = retryStatusMap.value[item.name]
    return rs
      ? { ...item, retry_status: rs.status, retry_attempt: rs.attempt, retry_max: rs.maxAttempt,
          retry_start_at: rs.startAt, retry_duration_s: rs.durationS, retry_last_error: rs.lastError,
          retry_queue_index: rs.queueIndex,
          _tick: retryTick.value /* reactivity trigger */ }
      : item
  }).sort((a, b) => {
    // v10 #33: 재처리 세션 중에는 상태별 정렬
    //   retrying(진행중) → queued(대기) → retry_done(완료) → retry_failed(실패) → 원래 상태
    const order = { retrying: 0, queued: 1, retry_done: 2, retry_failed: 3 }
    const ao = order[a.retry_status] ?? 9
    const bo = order[b.retry_status] ?? 9
    if (ao !== bo) return ao - bo
    // 같은 상태면 queue 순서대로
    return (a.retry_queue_index || 0) - (b.retry_queue_index || 0)
  })
})

// 전체 선택 체크박스 상태
const isBulkRetryAllSelected = computed(() => {
  return filteredErrItems.value.length > 0 &&
         filteredErrItems.value.every(i => bulkSelectedRetry.value.has(i.name))
})
const isBulkRetryIndeterminate = computed(() => {
  const sel = filteredErrItems.value.filter(i => bulkSelectedRetry.value.has(i.name)).length
  return sel > 0 && sel < filteredErrItems.value.length
})

function toggleBulkRetryAll() {
  const s = new Set(bulkSelectedRetry.value)
  if (isBulkRetryAllSelected.value) {
    // 해제
    filteredErrItems.value.forEach(i => s.delete(i.name))
  } else {
    // 선택
    filteredErrItems.value.forEach(i => s.add(i.name))
  }
  bulkSelectedRetry.value = s
}
function toggleBulkRetryItem(name) {
  const s = new Set(bulkSelectedRetry.value)
  if (s.has(name)) s.delete(name); else s.add(name)
  bulkSelectedRetry.value = s
}

// v95_p107 hotfix_047: 오류만 선택 (filteredErrItems 중 status='error' 만)
const errOnlyCount = computed(() => filteredErrItems.value.filter(i => i.status === 'error').length)
function selectOnlyErrors() {
  const s = new Set()
  filteredErrItems.value.filter(i => i.status === 'error').forEach(i => s.add(i.name))
  bulkSelectedRetry.value = s
}

// 재이관 처리 옵션
const bulkRetryOpts = [
  {
    value: 'drop_recreate',
    icon:  '🗑',
    title: 'DROP 후 재생성',
    desc:  '기존 객체 삭제 후 동일 DDL로 재시도. 잠금/잔재 해결용.',
  },
  {
    value: 'engine_only',
    icon:  '⚙',
    title: '자체 이관 (엔진 규칙)',
    desc:  'DataBridge 변환 규칙만 재적용. AI 호출 없음, 빠름/무료.',
  },
  {
    value: 'passthrough',
    icon:  '📝',
    title: '원본 설정 그대로',
    desc:  'MSSQL 원본 DDL을 변환 없이 그대로 전송. DB가 호환되면 통과.',
  },
  {
    value: 'ai',
    icon:  '🤖',
    title: 'AI 이관',
    desc:  'AI 엔진으로 재변환. 재시도 N회 = 시간/비용 N배 (Claude API 는 토큰비, 로컬은 GPU 시간). 2회 권장.',
    recommended: true,
  },
]

// 경과 시간 포맷 (00:00:00)
function fmtRetryElapsed(item) {
  const rs = retryStatusMap.value[item.name]
  if (!rs || !rs.startAt) return ''
  const elapsed = Math.floor((Date.now() - rs.startAt) / 1000)
  const h = Math.floor(elapsed / 3600)
  const m = Math.floor((elapsed % 3600) / 60)
  const s = elapsed % 60
  return (h > 0 ? String(h).padStart(2,'0') + ':' : '') +
         String(m).padStart(2,'0') + ':' + String(s).padStart(2,'0')
}

// 일괄 재처리 실행
async function runBulkRetry() {
  if (bulkSelectedRetry.value.size === 0) return
  const selectedNames = [...bulkSelectedRetry.value]
  const targets = errItems.value.filter(i => bulkSelectedRetry.value.has(i.name))

  const modeTxt = bulkRetryOpts.find(o => o.value === bulkRetryMode.value)?.title || bulkRetryMode.value
  const ok = confirm(`${selectedNames.length}건을 "${modeTxt}" 방식으로 일괄 재처리합니다.\n\n${bulkRetryMode.value === 'ai' ? `실패 시 최대 ${bulkAiMaxRetries.value}회까지 AI 재시도 합니다.\n` : ''}진행하시겠습니까?`)
  if (!ok) return

  bulkRetryRunning.value = true
  bulkRetryAborted.value = false  // h054
  bulkRetryPanelOpen.value = false

  // v10 #33: 이전 배치 상태 초기화 (새 배치 시작 시)
  //   이전 배치의 retry_done/retry_failed 이 남아있으면 filteredErrItems 에 유령 항목으로 보임
  retryStatusMap.value = {}

  // v10 #33: 진행 상태 추적 개선
  //   이전: 선택된 모든 항목을 즉시 'retrying' + 동일한 startAt → 16건 모두 동일 시간 흐름
  //   개선: 선택 시점에는 'queued' (대기) 상태. 루프 안에서 해당 차례에 'retrying' + 개별 startAt
  bulkBatchTotal.value = targets.length
  bulkBatchDone.value  = 0
  bulkBatchStartedAt.value = Date.now()

  targets.forEach((item, idx) => {
    retryStatusMap.value[item.name] = {
      status:      'queued',             // 대기 중
      queueIndex:  idx + 1,              // 전체 N개 중 몇 번째인지
      startAt:     null,                 // 아직 실행 전
      attempt:     null,
      maxAttempt:  bulkRetryMode.value === 'ai' ? bulkAiMaxRetries.value : null,
      lastError:   null,
      durationS:   null,
    }
  })
  // 실시간 경과 시간 업데이트 시작
  startRetryTick()

  // v95_p107 hotfix_068: 동시 처리 (병렬) — bulkConcurrency 만큼 동시에
  let okCount = 0, failCount = 0
  let abortedCount = 0

  // 단일 항목 처리 함수
  async function _h068_processOne(item) {
    if (bulkRetryAborted.value) return
    const t0 = Date.now()
    retryStatusMap.value[item.name] = {
      ...retryStatusMap.value[item.name],
      status:   'retrying',
      startAt:  t0,
      attempt:  bulkRetryMode.value === 'ai' ? 1 : null,
    }
    try {
      const success = await _runOneBulkRetry(item)
      const dur = Math.round((Date.now() - t0) / 1000)
      if (success) {
        retryStatusMap.value[item.name] = {
          ...retryStatusMap.value[item.name],
          status:    'retry_done',
          durationS: dur,
        }
        okCount++
      } else {
        retryStatusMap.value[item.name] = {
          ...retryStatusMap.value[item.name],
          status:    'retry_failed',
          durationS: dur,
        }
        failCount++
      }
    } catch (e) {
      retryStatusMap.value[item.name] = {
        ...retryStatusMap.value[item.name],
        status:    'retry_failed',
        lastError: e.message,
        durationS: Math.round((Date.now() - t0) / 1000),
      }
      failCount++
    }
    bulkBatchDone.value++
  }

  // chunked Promise.all 병렬 처리
  const _h068_concurrency = Math.max(1, bulkConcurrency.value || 1)
  for (let _h068_i = 0; _h068_i < targets.length; _h068_i += _h068_concurrency) {
    if (bulkRetryAborted.value) {
      abortedCount = targets.length - okCount - failCount
      break
    }
    const _h068_batch = targets.slice(_h068_i, _h068_i + _h068_concurrency)
    await Promise.all(_h068_batch.map(_h068_processOne))
  }

  bulkRetryRunning.value = false
  stopRetryTick()
  // 선택 초기화
  bulkSelectedRetry.value = new Set()

  if (bulkRetryAborted.value && abortedCount > 0) {
    app.notify(
      `일괄 재처리 중지됨 — 성공 ${okCount}건, 실패 ${failCount}건, 미처리 ${abortedCount}건`,
      'warn'
    )
  } else {
    app.notify(
      `일괄 재처리 완료 — 성공 ${okCount}건, 실패 ${failCount}건`,
      failCount === 0 ? 'success' : (okCount === 0 ? 'error' : 'warn')
    )
  }
}

// 개별 항목 재이관 (AI 모드일 때 재시도 루프)
async function _runOneBulkRetry(item) {
  const isTable = item.type === 'table'
  const mode = bulkRetryMode.value

  // AI 모드: 실패 시 에러를 error_history 에 누적하여 재시도
  if (mode === 'ai') {
    const maxAttempts = bulkAiMaxRetries.value
    let accumulatedErrors = item.error ? [{ attempt: 0, error: item.error }] : []

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      retryStatusMap.value[item.name] = {
        ...retryStatusMap.value[item.name],
        attempt,
      }
      // 경과 tick 트리거
      retryTick.value++

      const ok = await _callRemigEndpoint(item, {
        mode: 'ai',
        error_history: accumulatedErrors,
      })
      if (ok.success) return true
      accumulatedErrors.push({ attempt, error: ok.error || '변환 실패' })
      retryStatusMap.value[item.name] = {
        ...retryStatusMap.value[item.name],
        lastError: ok.error,
      }
    }
    return false
  }

  // 그 외 모드: 단일 호출
  const backendMode = {
    drop_recreate: 'drop_recreate',
    engine_only:   'original',       // 기존 remig-table 의 'original' 이 규칙 기반
    passthrough:   'passthrough',    // 백엔드에 해당 모드 있어야 함 (없으면 'original' 로 fallback)
  }[mode] || 'drop_recreate'

  const ok = await _callRemigEndpoint(item, { mode: backendMode, backendMode })
  return ok.success
}

// 기존 remig-table / remig-object 엔드포인트 호출 래퍼
async function _callRemigEndpoint(item, opts) {
  const isTable = item.type === 'table'
  // v95_p107 hotfix_057: AbortController — 중지 클릭 시 진행 중 fetch 즉시 취소
  bulkAbortController.value = new AbortController()
  const _h057_signal = bulkAbortController.value.signal
  try {
    let res
    if (isTable) {
      res = await fetch('/api/v1/jobs/' + job.value.id + '/remig-table', {
        method: 'POST',
        signal: _h057_signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          table:           item.name,
          mode:            opts.backendMode || opts.mode,
          error_hint:      item.error,
          error_history:   opts.error_history || errorHistory.value[item.name] || [],
          table_mode:      job.value?.table_mode,
          drop_table:      job.value?.drop_table,
          truncate_target: job.value?.truncate_target,
          create_table:    job.value?.create_table,
          // v95_p107 hotfix_048: provider override
          ai_provider:     bulkAiProvider.value || undefined,
          ai_model:        bulkAiModel.value || undefined,
        })
      })
    } else {
      res = await fetch('/api/v1/jobs/' + job.value.id + '/remig-object', {
        method: 'POST',
        signal: _h057_signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          object_name:   item.name,
          object_type:   item.type,
          mode:          opts.mode,
          error_history: opts.error_history || [],
          // v95_p107 hotfix_048: provider override
          ai_provider:   bulkAiProvider.value || undefined,
          ai_model:      bulkAiModel.value || undefined,
        })
      })
    }
    if (!res.ok) {
      const e = await res.json().catch(() => ({}))
      return { success: false, error: e.detail || `HTTP ${res.status}` }
    }
    // 완료 대기 (기존 _waitItemDone 패턴 재사용)
    const finalSt = await _waitItemDone(item.name, isTable ? 300 : 120)
    // v95_p107 hotfix_059: 새 결과 즉시 폴링 (item.error 캐시 갱신 — 본부장님 진가 표시)
    try { await loadJob() } catch (_) {}
    if (finalSt === 'done') return { success: true }
    const err = job.value?.item_statuses?.[item.name]?.error
    return { success: false, error: err || finalSt }
  } catch (e) {
    // v95_p107 hotfix_057: AbortError 인 경우 — 사용자 중지
    if (e.name === 'AbortError') {
      return { success: false, error: '사용자 중지' }
    }
    return { success: false, error: e.message }
  }
}

// 실시간 경과 시간 tick
function startRetryTick() {
  if (retryTickTimer) return
  retryTickTimer = setInterval(() => { retryTick.value++ }, 1000)
}
function stopRetryTick() {
  if (retryTickTimer) { clearInterval(retryTickTimer); retryTickTimer = null }
}
// 컴포넌트 언마운트 시 정리
onUnmounted(() => { stopRetryTick() })
// ═══ /v10 일괄 재처리 ═══

function copyErrReport() {
  const j = job.value
  const errList = errItems.value.map(i => '[' + (i.type || '').toString().toUpperCase() + '] ' + i.name + ': ' + i.error).join('\n')
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
  { value:'ai',            icon:'🤖', title:'AI 이관',             desc:'내부 AI(Gemini 기본)가 오류 분석 후 스키마 변환 및 재이관' },
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
        name:        item.name,
        type:        item.type,
        mode:        objRemigMode.value === 'rules' ? 'drop_recreate' : objRemigMode.value,
        obj_engine:  objRemigMode.value === 'ai' ? 'claude' : 'rules',
        force_convert: objRemigMode.value === 'rules',  // 강제 규칙 재변환
        error_hint:  item.error
      })
    })
    if (!res.ok) {
      const e = await res.json()
      alert('재이관 실패: ' + (e.detail || '오류'))
      await loadJob()
    } else {
      // 재이관 완료될 때까지 폴링 (최대 120초, 2초 간격)
      let tries = 0
      const poll = setInterval(async () => {
        tries++
        await loadJob()
        // item_statuses에서 해당 아이템이 running이 아니면 완료
        const st = job.value?.item_statuses?.[item.name]?.status
        if (st && st !== 'running' || tries >= 60) {
          clearInterval(poll)
        }
      }, 2000)
    }
  } catch(e) {
    alert('재이관 오류: ' + e.message)
    await loadJob()
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
.jm{display:flex;flex-direction:column;gap:14px;max-width:1380px;margin:0 auto}
.jm-header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.page-title{font-size:1.25rem;font-weight:700;color:var(--text-primary)}
.page-desc{font-size:.78rem;color:var(--text-tertiary);margin-top:2px}
.jm-controls{display:flex;align-items:center;gap:8px}
/* ── 커스텀 작업 선택 드롭다운 ── */
.job-picker { position:relative; min-width:340px; }
.job-picker-btn {
  display:flex; align-items:center; gap:7px;
  background:var(--bg-secondary); border:0.5px solid var(--border-mid);
  border-radius:var(--radius-md); padding:6px 10px;
  cursor:pointer; transition:border-color .12s; user-select:none;
}
.job-picker-btn:hover { border-color:var(--accent-blue); }
.jp-btn-status { width:7px; height:7px; border-radius:50%; flex-shrink:0; }
.jp-btn-status.running  { background:#16a34a; animation:pulse .8s infinite; }
.jp-btn-status.completed{ background:#2563eb; }
.jp-btn-status.error    { background:#dc2626; }
.jp-btn-status.aborted  { background:#9ca3af; }
.jp-btn-name { font-size:.82rem; font-weight:600; color:var(--text-primary); flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.jp-btn-meta { font-size:.68rem; color:var(--text-tertiary); white-space:nowrap; flex-shrink:0; }
.jp-btn-placeholder { font-size:.8rem; color:var(--text-tertiary); flex:1; }
.job-picker-list {
  position:absolute; top:calc(100% + 4px); left:0; right:0;
  background:var(--bg-primary); border:0.5px solid var(--border-mid);
  border-radius:var(--radius-md); box-shadow:0 6px 24px rgba(0,0,0,.14);
  z-index:500; max-height:360px; overflow-y:auto;
}
.jp-sort-bar {
  display:flex; align-items:center; gap:4px;
  padding:6px 10px; border-bottom:0.5px solid var(--border-light);
  background:var(--bg-secondary); position:sticky; top:0; z-index:1;
}
.jp-sort-label { font-size:.62rem; color:var(--text-tertiary); font-weight:600; margin-right:2px; }
.jp-sort-btn {
  padding:2px 8px; border-radius:99px; border:0.5px solid var(--border-light);
  background:transparent; font-size:.65rem; color:var(--text-tertiary);
  cursor:pointer; font-family:var(--font); transition:all .1s;
}
.jp-sort-btn:hover { border-color:var(--accent-blue); color:var(--accent-blue); }
.jp-sort-btn.on { background:var(--accent-blue); color:#fff; border-color:var(--accent-blue); font-weight:600; }
.jp-empty { padding:12px 14px; font-size:.78rem; color:var(--text-tertiary); text-align:center; }
.jp-item {
  padding:9px 12px; cursor:pointer; transition:background .1s;
  border-bottom:0.5px solid var(--border-light); display:flex; flex-direction:column; gap:4px;
}
.jp-item:last-child { border-bottom:none; }
.jp-item:hover  { background:var(--bg-secondary); }
.jp-item.active { background:rgba(37,99,235,.05); border-left:2px solid var(--accent-blue); }
.jp-row1 { display:flex; align-items:center; gap:6px; }
.jp-status-dot { width:6px; height:6px; border-radius:50%; flex-shrink:0; }
.jp-status-dot.running  { background:#16a34a; animation:pulse .8s infinite; }
.jp-status-dot.completed{ background:#2563eb; }
.jp-status-dot.error    { background:#dc2626; }
.jp-status-dot.aborted  { background:#9ca3af; }
.jp-name  { font-size:.82rem; font-weight:600; color:var(--text-primary); flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.jp-badge { font-size:.62rem; font-weight:700; padding:1px 6px; border-radius:99px; flex-shrink:0; }
.jp-badge.running  { background:rgba(22,163,74,.12); color:#15803d; }
.jp-badge.completed{ background:rgba(37,99,235,.10); color:#1d4ed8; }
.jp-badge.error    { background:rgba(220,38,38,.10);  color:#dc2626; }
.jp-badge.aborted  { background:var(--bg-tertiary);   color:var(--text-tertiary); }
.jp-row2 { display:flex; align-items:center; gap:6px; }
.jp-db   { font-size:.7rem; color:var(--text-secondary); flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.jp-db-src { font-weight:700; color:#dc2626; font-size:.62rem; }
.jp-db-tgt { font-weight:700; color:#16a34a; font-size:.62rem; }
.jp-date { font-size:.67rem; color:var(--text-tertiary); flex-shrink:0; font-variant-numeric:tabular-nums; }
.jp-row3 { display:flex; align-items:center; gap:7px; }
.jp-prog-wrap { display:flex; align-items:center; gap:4px; flex:1; min-width:0; }
.jp-prog-bar  { flex:1; height:3px; background:var(--border-light); border-radius:2px; overflow:hidden; }
.jp-prog-fill { height:100%; background:var(--accent-blue); border-radius:2px; transition:width .3s; }
.jp-prog-txt  { font-size:.65rem; color:var(--text-tertiary); flex-shrink:0; font-variant-numeric:tabular-nums; }
.jp-tbl  { font-size:.67rem; color:var(--text-tertiary); flex-shrink:0; }
.jp-rows { font-size:.67rem; color:var(--text-tertiary); flex-shrink:0; font-variant-numeric:tabular-nums; }
.jp-err  { font-size:.65rem; color:#dc2626; font-weight:600; flex-shrink:0; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
.ctrl-btn{width:30px;height:30px;display:flex;align-items:center;justify-content:center;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:var(--bg-secondary);cursor:pointer;color:var(--text-secondary);transition:all .12s}
.clear-btn{width:auto !important;padding:0 10px;gap:2px;color:var(--text-tertiary)}.clear-btn:hover{color:#ef4444;border-color:rgba(239,68,68,.3);background:rgba(239,68,68,.06)}
/* v9 패치 #13: 새로고침 버튼 가시성 개선 */
.refresh-btn{width:auto !important;padding:0 10px;gap:2px;color:var(--accent-blue);border-color:rgba(59,130,246,.35)}
.refresh-btn:hover{color:#fff;background:var(--accent-blue);border-color:var(--accent-blue)}
/* v9 패치 #26: 리포트 버튼 */
.report-btn{width:auto !important;padding:0 10px;gap:2px;color:#6d28d9;border-color:rgba(109,40,217,.35);background:rgba(109,40,217,.06)}
.report-btn:hover{color:#fff;background:#6d28d9;border-color:#6d28d9}
/* v10 #22: 모니터 버튼 (초록 계열 - 실시간/헬스 느낌) */
.monitor-btn{width:auto !important;padding:0 10px;gap:2px;color:#059669;border-color:rgba(5,150,105,.35);background:rgba(5,150,105,.06);position:relative}
.monitor-btn:hover{color:#fff;background:#059669;border-color:#059669}
.monitor-btn.active{color:#fff;background:#059669;border-color:#059669;box-shadow:inset 0 0 0 1px rgba(255,255,255,.2)}
.monitor-badge{position:absolute;top:-4px;right:-4px;min-width:16px;height:16px;padding:0 4px;border-radius:8px;background:#eab308;color:#fff;font-size:10px;font-weight:700;display:inline-flex;align-items:center;justify-content:center;line-height:1;box-shadow:0 1px 3px rgba(0,0,0,.2);font-variant-numeric:tabular-nums}
.monitor-badge.crit{background:#dc2626;animation:mon-badge-pulse 1.4s infinite}
@keyframes mon-badge-pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.12)}}
/* v90.62: 모니터 글자 옆 라이브 점멸 (폴링 활성 시) — 본부장님 요청 */
.monitor-live-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#10b981;margin-left:5px;flex-shrink:0;animation:mon-live-pulse 1.2s ease-in-out infinite;box-shadow:0 0 0 0 rgba(16,185,129,.6)}
.monitor-btn.active .monitor-live-dot{background:#fff;box-shadow:0 0 0 0 rgba(255,255,255,.6)}
@keyframes mon-live-pulse{
  0%   {opacity:.4;transform:scale(.85);box-shadow:0 0 0 0 rgba(16,185,129,.6)}
  50%  {opacity:1; transform:scale(1.1); box-shadow:0 0 0 4px rgba(16,185,129,0)}
  100% {opacity:.4;transform:scale(.85);box-shadow:0 0 0 0 rgba(16,185,129,0)}
}
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

/* v90.67: 상태 카드 키우고 (1.1→1.4fr) 우측 KPI 카드 폭 약간 줄임 (1→0.85fr).
   전체 진행 카드는 1.8→1.6fr 로 살짝 양보. */
.kpi-grid{display:grid;grid-template-columns:1.4fr 1.6fr 0.85fr 0.85fr 0.85fr;gap:10px}

/* ════════════════════════════════════════════════════════════════ */
/* v95_p91_compact (2026-05-08 본부장님 본질 처방):                    */
/* 위 카드 줄이고 진행 중인 리스트 더 크게                             */
/* ════════════════════════════════════════════════════════════════ */

/* 컴팩트 진행 바 (접힘 모드) */
.kpi-compact-bar {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 14px;
  background: var(--bg-secondary, #f8fafc);
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 10px;
  margin-bottom: 12px;
  font-size: 13px;
}
.kpi-toggle-btn {
  background: transparent;
  border: 1px solid var(--border-light, #cbd5e1);
  color: var(--text-secondary, #64748b);
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  cursor: pointer;
  transition: all .15s;
  flex-shrink: 0;
}
.kpi-toggle-btn:hover {
  background: var(--bg-primary, #fff);
  color: var(--text-primary, #1e293b);
  border-color: #94a3b8;
}
.kpi-toggle-collapse {
  position: absolute;
  top: 8px;
  right: 12px;
  z-index: 5;
}
.kpi-section-wrapper {
  position: relative;
  margin-bottom: 12px;
}

.kpi-compact-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  flex-shrink: 0;
}
.kpi-compact-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #94a3b8;
}
.kpi-compact-dot.running { background: #14b8a6; animation: pulse-running 1.5s ease-in-out infinite; }
.kpi-compact-dot.completed { background: #16a34a; }
.kpi-compact-dot.failed { background: #ef4444; }
.kpi-compact-dot.paused { background: #f59e0b; }

@keyframes pulse-running {
  0%, 100% { box-shadow: 0 0 0 0 rgba(20, 184, 166, 0.6); }
  50% { box-shadow: 0 0 0 6px rgba(20, 184, 166, 0); }
}

/* 현재 진행 중 단계 (깜빡임) */
.kpi-compact-phase {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--text-secondary, #475569);
  font-weight: 500;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kpi-compact-blink {
  display: inline-block;
  color: #14b8a6;
  font-size: 14px;
  animation: spin-blink 1.2s linear infinite;
}
@keyframes spin-blink {
  0% { transform: rotate(0deg); opacity: 1; }
  50% { transform: rotate(180deg); opacity: 0.6; }
  100% { transform: rotate(360deg); opacity: 1; }
}

/* 진행률 (컴팩트) */
.kpi-compact-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  min-width: 140px;
}
.kpi-compact-pct {
  font-weight: 700;
  color: var(--text-primary, #0f172a);
  min-width: 38px;
  text-align: right;
}
.kpi-compact-bar-track {
  flex: 1;
  height: 6px;
  min-width: 80px;
  background: var(--bg-tertiary, #e2e8f0);
  border-radius: 3px;
  overflow: hidden;
}
.kpi-compact-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #14b8a6, #0d9488);
  border-radius: 3px;
  transition: width .3s;
}

/* ════════════════════════════════════════════════════════════════
   v95_p107 hotfix_029 (2026-05-11 본부장님 본질 처방):
     접힌 헤더에서 테이블/객체 진행률 분리 표시
   ════════════════════════════════════════════════════════════════ */

/* 테이블 진행 (작게, 자리만 차지) */
.kpi-compact-progress-tbl {
  min-width: auto;
  gap: 4px;
  padding: 3px 8px;
  background: rgba(148, 163, 184, .08);
  border-radius: 5px;
  font-size: 12px;
  color: var(--text-secondary, #475569);
}
.kpi-compact-progress-tbl .kpi-compact-mini-label {
  font-weight: 600;
  font-size: 11px;
  color: var(--text-tertiary, #94a3b8);
}
.kpi-compact-progress-tbl .kpi-compact-mini-count {
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
.kpi-compact-progress-tbl .kpi-compact-mini-pct {
  font-weight: 700;
  color: var(--text-primary, #334155);
  font-variant-numeric: tabular-nums;
}

/* 객체 진행 (강조 — 바 포함) */
.kpi-compact-progress-obj {
  min-width: 220px;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 5px;
  background: rgba(20, 184, 166, .06);
  border: 1px solid rgba(20, 184, 166, .15);
  transition: all .3s;
}
.kpi-compact-progress-obj.obj-active {
  background: rgba(20, 184, 166, .12);
  border-color: rgba(20, 184, 166, .35);
  animation: kpi-obj-pulse 2s ease-in-out infinite;
}
.kpi-compact-progress-obj.obj-failed {
  background: rgba(239, 68, 68, .08);
  border-color: rgba(239, 68, 68, .25);
}
@keyframes kpi-obj-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(20, 184, 166, .25); }
  50%      { box-shadow: 0 0 0 4px rgba(20, 184, 166, .08); }
}
.kpi-compact-progress-obj .kpi-compact-mini-label {
  font-weight: 700;
  font-size: 11px;
  color: #0d9488;
  letter-spacing: .02em;
}
.kpi-compact-progress-obj.obj-failed .kpi-compact-mini-label {
  color: #dc2626;
}
.kpi-compact-progress-obj .kpi-compact-mini-count {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--text-primary, #0f172a);
}
.kpi-compact-progress-obj .kpi-compact-pct {
  font-weight: 700;
  color: #0d9488;
  font-variant-numeric: tabular-nums;
  min-width: 36px;
  text-align: right;
}
.kpi-compact-progress-obj.obj-failed .kpi-compact-pct {
  color: #dc2626;
}
/* 객체 진행바 색깔 변형 */
.kpi-compact-bar-fill.bar-failed {
  background: linear-gradient(90deg, #ef4444, #dc2626);
}
.kpi-compact-bar-fill.bar-done {
  background: linear-gradient(90deg, #10b981, #059669);
}

/* 객체 진행 상태 */
.kpi-compact-obj {
  font-size: 12px;
  background: rgba(20, 184, 166, .1);
  color: #0d9488;
  padding: 3px 8px;
  border-radius: 5px;
  font-weight: 600;
  flex-shrink: 0;
}

/* 오류 배지 */
.kpi-compact-err {
  display: flex;
  align-items: center;
  gap: 4px;
  background: rgba(239, 68, 68, .1);
  color: #dc2626;
  padding: 3px 10px;
  border-radius: 5px;
  font-weight: 600;
  font-size: 12px;
  cursor: pointer;
  flex-shrink: 0;
  transition: all .15s;
}
.kpi-compact-err:hover {
  background: rgba(239, 68, 68, .2);
}

/* 모바일 */
@media (max-width: 768px) {
  .kpi-compact-bar { flex-wrap: wrap; gap: 8px; }
  .kpi-compact-progress { min-width: 100%; order: 99; }
}
@media(max-width:900px){.kpi-grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:600px){.kpi-grid{grid-template-columns:repeat(2,1fr)}}
.kpi-card{background:var(--bg-secondary);border:0.5px solid var(--border-light);border-radius:12px;padding:14px 16px;display:flex;flex-direction:column;gap:5px;position:relative;overflow:visible}
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

/* v92p9 (2026-04-30): 상태 카드 압축
   본부장님 호소: "줄 수가 너무 많아" → MSSQL→MYSQL 줄 제거,
   진행중 라벨 옆에 객체 카운트 인라인 배치 */
.kpi-status-row {
  display: flex; align-items: center; gap: 10px;
  margin-top: 4px; flex-wrap: wrap;
}
.status-blink { animation: status-blink-anim 1s ease-in-out infinite; }
@keyframes status-blink-anim {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.45; }
}
.kpi-obj-inline {
  display: inline-flex; align-items: baseline; gap: 4px;
  font-size: .78rem; font-weight: 600;
  color: var(--text-secondary);
  padding: 2px 8px;
  background: var(--bg-secondary);
  border: 0.5px solid var(--border-light);
  border-radius: 6px;
  font-variant-numeric: tabular-nums;
}
.kpi-obj-inline.fail { color: #b91c1c; background: rgba(239,68,68,.06); border-color: rgba(239,68,68,.25); }
.kpi-obj-inline.done { color: #15803d; background: rgba(22,163,74,.08); border-color: rgba(22,163,74,.25); }
.koi-icon { font-size: .85rem; font-weight: 700; font-style: italic; }
.koi-val  { font-size: .75rem; }
.koi-fail { font-size: .68rem; color: #dc2626; font-weight: 700; margin-left: 2px; }

/* v92p13 (2026-04-30): 테이블 카운트 인라인 배지 (진행중 옆) */
.kpi-tbl-inline {
  display: inline-flex; align-items: baseline; gap: 4px;
  font-size: .78rem; font-weight: 600;
  color: var(--text-secondary);
  padding: 2px 8px;
  background: var(--bg-secondary);
  border: 0.5px solid var(--border-light);
  border-radius: 6px;
  font-variant-numeric: tabular-nums;
}
.kpi-tbl-inline.done {
  color: #15803d;
  background: rgba(22,163,74,.08);
  border-color: rgba(22,163,74,.25);
}
.kti-icon { font-size: .85rem; font-weight: 700; }
.kti-val  { font-size: .75rem; }

/* v92p11 (2026-04-30): AI 자동이관 ON/OFF 배지
   v92p15 (2026-04-30): 클릭 가능한 button 으로 변경 */
.kpi-ai-toggle {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 6px;
  font-size: .72rem; font-weight: 700;
  background: var(--bg-secondary);
  color: var(--text-tertiary);
  border: 0.5px solid var(--border-light);
  cursor: pointer;
  transition: all .15s;
  font-family: inherit;
  line-height: 1.4;
}
.kpi-ai-toggle:not(:disabled):hover {
  filter: brightness(1.05);
  transform: translateY(-1px);
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.kpi-ai-toggle:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.kpi-ai-toggle.on {
  background: rgba(168,85,247,.1);
  color: #7c3aed;
  border-color: rgba(168,85,247,.3);
}
.kpi-ai-toggle.on:not(:disabled):hover {
  background: rgba(168,85,247,.15);
  border-color: rgba(168,85,247,.5);
}
.kat-ico { font-size: .8rem; }
.kat-txt { letter-spacing: .02em; }
.kat-spinner {
  display: inline-block;
  animation: spin .8s linear infinite;
  font-size: .85rem;
  margin-left: 2px;
}

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
/* v9 패치 #34: 현재 테이블 잔여 시간 */
.cur-eta{font-size:.73rem;color:var(--accent-blue);font-weight:600;white-space:nowrap;display:inline-flex;align-items:center;padding:2px 8px;background:rgba(59,130,246,0.08);border-radius:10px}

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

.item-table-outer{margin-top:8px}

/* v10: 점프 툴바 */
.jump-bar{
  display:flex; align-items:center; gap:10px;
  padding:8px 12px; margin-bottom:8px;
  background:var(--bg-secondary);
  border:0.5px solid var(--border-light);
  border-radius:10px;
  position:sticky; top:0; z-index:5;
  flex-wrap:wrap;
}
.jump-left{display:flex;align-items:center;gap:10px;min-width:180px}
.jump-total{
  font-size:.75rem; font-weight:600;
  color:var(--text-secondary);
  padding:3px 9px;
  background:var(--bg-primary);
  border:0.5px solid var(--border-light);
  border-radius:12px;
  flex-shrink:0;
}
.jump-scroll-indicator{
  flex:1; min-width:80px; max-width:140px;
  height:4px;
  background:var(--bg-tertiary);
  border-radius:2px;
  overflow:hidden;
}
.jsi-fill{
  height:100%;
  background:linear-gradient(90deg,var(--accent-blue),var(--accent-green));
  transition:width .15s;
}
.jump-center{display:flex; gap:4px; flex:1; justify-content:center; flex-wrap:wrap}
.jump-btn{
  display:inline-flex; align-items:center; gap:5px;
  padding:5px 10px;
  font-size:.72rem; font-weight:500;
  color:var(--text-secondary);
  background:var(--bg-primary);
  border:0.5px solid var(--border-mid);
  border-radius:var(--radius-md);
  cursor:pointer; white-space:nowrap;
  font-family:var(--font);
  transition:all .12s;
}
.jump-btn:hover:not(:disabled){
  background:var(--bg-info);
  color:var(--text-info);
  border-color:var(--accent-blue);
}
.jump-btn:disabled{opacity:.35;cursor:not-allowed}
.jump-btn.small{padding:4px 9px;font-size:.7rem}
.jump-btn svg{color:var(--text-tertiary)}
.jump-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.jump-dot.err{background:#ef4444}
.jump-dot.run{background:#3b82f6;animation:pulse 1.5s infinite}
.jump-dot.pen{background:#9ca3af}
.jump-right{display:flex;gap:5px;align-items:center;flex-shrink:0}
.jump-row-input{
  width:56px; padding:4px 8px;
  font-size:.72rem;
  border:0.5px solid var(--border-mid);
  border-radius:var(--radius-md);
  background:var(--bg-primary);
  color:var(--text-primary);
  font-family:var(--font);
  text-align:center;
}
.jump-row-input:focus{outline:none;border-color:var(--accent-blue);box-shadow:0 0 0 2px var(--bg-info)}

.item-row.jump-flash{animation: jump-flash 1.4s ease-out}
@keyframes jump-flash {
  0%   { background-color: rgba(251,191,36,.45); box-shadow: 0 0 0 2px #fbbf24 inset; }
  60%  { background-color: rgba(251,191,36,.18); box-shadow: 0 0 0 1px rgba(251,191,36,.4) inset; }
  100% { background-color: transparent; box-shadow: none; }
}

/* v10: item-table 자체 스크롤 + 굵은 스크롤바 */
.item-table{
  background:var(--bg-secondary);
  border:0.5px solid var(--border-light);
  border-radius:12px;
  overflow-y:auto;
  overflow-x:hidden;
  max-height: calc(100vh - 380px);
  min-height: 240px;
  position: relative;
  scrollbar-width: auto;
  scrollbar-color: var(--border-strong) var(--bg-tertiary);
}
@media(max-width: 900px){
  .item-table{ max-height: calc(100vh - 440px) }
}
.item-table::-webkit-scrollbar{width:14px;height:14px}
.item-table::-webkit-scrollbar-track{
  background: var(--bg-tertiary);
  border-left: 1px solid var(--border-light);
}
.item-table::-webkit-scrollbar-thumb{
  background: var(--border-strong);
  border: 3px solid var(--bg-tertiary);
  border-radius: 7px;
  min-height: 40px;
}
.item-table::-webkit-scrollbar-thumb:hover{background: var(--text-tertiary)}
.item-table::-webkit-scrollbar-thumb:active{background: var(--accent-blue)}
.item-head{display:grid;grid-template-columns:1.7fr .6fr .9fr 48px 80px .65fr 48px 72px minmax(220px,1.5fr);gap:8px;padding:8px 16px;background:var(--bg-primary);border-bottom:0.5px solid var(--border-light);font-size:.66rem;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.06em;position:sticky;top:0;z-index:2}
.ih-sort{cursor:pointer;user-select:none;display:inline-flex;align-items:center;gap:3px;transition:color .1s}.ih-sort:hover{color:var(--text-primary)}
.sort-arrow{color:#2563eb;font-weight:700;font-size:.8rem}
.item-row{display:grid;grid-template-columns:1.7fr .6fr .9fr 48px 80px .65fr 48px 72px minmax(220px,1.5fr);gap:8px;padding:9px 16px;align-items:center;border-bottom:0.5px solid var(--border-light);cursor:pointer;transition:background .12s;font-size:.82rem}
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
.ic-time{font-size:.75rem;text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
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
.stat-pill{display:inline-flex;align-items:center;gap:3px;font-size:.7rem;font-weight:500;padding:3px 8px;border-radius:99px;white-space:nowrap;max-width:100%;background:transparent}
.stat-pill svg{width:10px;height:10px;flex-shrink:0}
.stat-pill.running{background:rgba(59,130,246,.1);color:#1d4ed8;animation:pillBlink 1.2s ease-in-out infinite}
.stat-pill.done{color:#15803d}
.stat-pill.error{color:#b91c1c}
.stat-pill.pending{color:var(--text-tertiary)}
/* v95_p107 hotfix_045: 과정/결과 분리 — 과정은 회색, 결과만 강조 */
.stp-process{color:var(--text-tertiary);font-weight:500;opacity:.85}
.stp-outcome{font-weight:700;margin-left:2px}
.stp-outcome.ok{color:#15803d}
.stp-outcome.ng{color:#b91c1c}
/* v90.67: AI 재이관으로 성공 — 보라색 (특별한 성공) */
.stat-pill.done.via-ai{background:linear-gradient(135deg,rgba(139,92,246,.12),rgba(168,85,247,.08));color:#6d28d9;border:1px solid rgba(139,92,246,.2)}
/* v90.67: 1차 실패 → 재시도로 성공 — 청록색 (회복) */
.stat-pill.done.recovered{background:rgba(20,184,166,.1);color:#0f766e;border:1px solid rgba(20,184,166,.18)}
/* v9 패치 #39: 진행중 상태 깜빡임 */
@keyframes pillBlink {
  0%,100% { background:rgba(59,130,246,.1); color:#1d4ed8; }
  50%     { background:rgba(59,130,246,.35); color:#0c3b9c; }
}
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

/* v92p12: phase-step 안의 카운트 표시 */
.ps-sub {
  font-size: .65rem;
  color: var(--text-tertiary);
  margin-left: 4px;
  font-weight: 500;
}
.ps-active .ps-sub { color: #1d4ed8; font-weight: 600; }
.ps-done   .ps-sub { color: #15803d; }

/* v92p12: ADVISOR_APPLY 중 현재 권고 표시 */
.adv-current {
  font-size: .78rem;
  font-weight: 500;
  color: var(--text-secondary);
  font-style: italic;
  padding: 4px 12px;
  background: rgba(168,85,247,.06);
  border-radius: 6px;
  border-left: 2px solid #a855f7;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* v92p6 (2026-04-30): phase 정체 경고 배너 */
.phase-stuck-warn {
  display: flex; align-items: center; gap: 8px;
  margin-top: 8px; padding: 6px 10px;
  background: rgba(239,68,68,0.08);
  border: 0.5px solid rgba(239,68,68,0.3);
  border-radius: 6px;
  font-size: .72rem; color: #b91c1c;
}
.psw-ico { font-size: .85rem; }
.psw-msg { flex: 1; font-weight: 500; }
.psw-btn {
  padding: 3px 9px; border-radius: 5px;
  background: #dc2626; color: white; border: none;
  font-size: .68rem; font-weight: 600; cursor: pointer;
}
.psw-btn:hover { background: #b91c1c; }

@keyframes phase-pulse{0%,100%{opacity:1}50%{opacity:.6}}

/* v90.67: 상태 카드 하단 — 테이블/객체 분리 진행률 */
.phase-counts{margin-top:8px;padding-top:8px;border-top:0.5px dashed var(--border-light);display:flex;flex-direction:column;gap:4px}
.phase-count-row{display:flex;align-items:center;gap:6px;font-size:.72rem}
.phase-count-icon{font-size:.85rem;width:14px;text-align:center;color:var(--text-tertiary);flex-shrink:0}
.phase-count-label{color:var(--text-tertiary);min-width:32px}
.phase-count-val{font-weight:600;color:var(--text-secondary);font-variant-numeric:tabular-nums;margin-left:auto}
.phase-count-val.done{color:#15803d}
.phase-count-val.fail{color:#b45309}
.phase-count-fail{color:#dc2626;font-weight:500;margin-left:4px;font-size:.68rem}
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

/* v10: 일괄 재처리 관련 */
.bulk-retry-bar{
  display:flex; align-items:center; gap:12px;
  padding:9px 18px;
  background:var(--bg-primary);
  border-bottom:0.5px solid var(--border-light);
  flex-wrap:wrap;
}
.bulk-check-label{
  display:inline-flex; align-items:center; gap:6px;
  font-size:.78rem; font-weight:500;
  color:var(--text-secondary);
  cursor:pointer;
}
.bulk-check-label input[type=checkbox]{
  width:14px; height:14px; margin:0; cursor:pointer;
}
.bulk-count{
  font-size:.72rem; color:var(--text-tertiary); font-weight:400;
  margin-left:2px;
}
.bulk-filters{display:flex; gap:6px; flex:1; min-width:120px}
.bulk-sel{
  font-size:.72rem; padding:3px 6px;
  border:0.5px solid var(--border-mid);
  border-radius:4px;
  background:var(--bg-primary);
  color:var(--text-primary);
  font-family:var(--font);
}
.bulk-open-btn{
  display:inline-flex; align-items:center; gap:5px;
  padding:6px 12px;
  font-size:.78rem; font-weight:500;
  color:#fff;
  background:#2563eb;
  border:none;
  border-radius:6px;
  cursor:pointer;
  font-family:var(--font);
  transition:all .12s;
}
.bulk-open-btn:hover:not(:disabled){background:#1d4ed8}
.bulk-open-btn:disabled{opacity:.35; cursor:not-allowed; background:var(--border-mid); color:var(--text-tertiary)}
.bulk-open-btn.open{background:#1e40af}

/* 일괄 처리 패널 */
.bulk-retry-panel{
  padding:14px 18px;
  background:var(--bg-secondary);
  border-bottom:0.5px solid var(--border-light);
  animation: brpSlide .22s ease;
}
@keyframes brpSlide{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:translateY(0)}}
.brp-header{
  font-size:.75rem; color:var(--text-tertiary); margin-bottom:10px;
}
.brp-grid{display:grid; grid-template-columns:1fr 1fr; gap:8px}
@media(max-width:680px){.brp-grid{grid-template-columns:1fr}}
.brp-opt{
  display:flex; flex-direction:column; gap:4px;
  padding:10px 12px;
  background:var(--bg-primary);
  border:0.5px solid var(--border-light);
  border-radius:8px;
  cursor:pointer;
  transition:all .12s;
}
.brp-opt:hover{border-color:var(--border-mid)}
.brp-opt.active{
  border: 2px solid #2563eb;
  background:var(--bg-info);
  padding:9px 11px;  /* 2px border 보상 */
}
.brp-opt-head{display:flex; align-items:center; gap:8px}
.brp-opt-icon{font-size:14px}
.brp-opt-title{font-size:.82rem; font-weight:600; color:var(--text-primary); flex:1}
.brp-opt-rec{
  font-size:.62rem; font-weight:700;
  background:#2563eb; color:#fff;
  padding:1px 6px; border-radius:3px;
  letter-spacing:.02em;
}
.brp-opt-check{color:#2563eb; font-weight:700; font-size:.9rem}
.brp-opt-desc{
  font-size:.72rem; color:var(--text-secondary);
  line-height:1.45;
}
.brp-ai-opts{
  display:flex;
  flex-wrap:wrap;
  align-items:center;
  gap:8px 14px;
  margin-top:8px;
  padding:10px 12px;
  background:var(--bg-primary);
  border:0.5px solid var(--border-light);
  border-radius:6px;
  font-size:.72rem;
}
.brp-ai-field{
  display:inline-flex;
  align-items:center;
  gap:6px;
  white-space:nowrap;
}
.brp-ai-lbl{
  color:var(--text-secondary);
  font-weight:500;
}
.brp-sel{
  font-size:.72rem; padding:3px 8px;
  border:0.5px solid var(--border-mid);
  border-radius:4px;
  background:var(--bg-primary);
  color:var(--text-primary);
  font-family:var(--font);
}
.brp-ai-hint{
  flex-basis:100%;
  margin-top:4px;
  padding-top:8px;
  border-top:0.5px dashed var(--border-light);
  color:var(--text-tertiary);
  font-size:.68rem;
  line-height:1.5;
}
.brp-actions{
  display:flex; gap:8px; justify-content:flex-end;
  margin-top:12px; padding-top:10px;
  border-top:0.5px solid var(--border-light);
}
.brp-cancel{
  padding:7px 16px;
  border:0.5px solid var(--border-mid);
  background:transparent;
  border-radius:6px;
  font-size:.75rem; cursor:pointer; color:var(--text-secondary);
  font-family:var(--font);
}
.brp-cancel:hover{background:var(--bg-primary)}
.brp-run{
  padding:7px 18px;
  border:none;
  background:#2563eb; color:#fff;
  border-radius:6px;
  font-size:.75rem; font-weight:600; cursor:pointer;
  font-family:var(--font);
  display:inline-flex; align-items:center; gap:6px;
}
.brp-run:hover:not(:disabled){background:#1d4ed8}
.brp-run:disabled{opacity:.5; cursor:not-allowed}

/* 항목별 체크박스 */
.emd-bulk-chk{
  width:14px; height:14px; margin:0; cursor:pointer; flex-shrink:0;
}
/* 재이관 진행/완료 뱃지 */
.emd-errcode{
  font-size:.66rem; font-family:ui-monospace,monospace;
  color:var(--text-tertiary);
  padding:1px 5px;
  background:var(--bg-primary);
  border:0.5px solid var(--border-light);
  border-radius:3px;
  flex-shrink:0;
}
.emd-retry-badge{
  display:inline-flex; align-items:center; gap:4px;
  font-size:.68rem; font-weight:500;
  padding:2px 7px;
  border-radius:10px;
  margin-left:4px;
  white-space:nowrap;
}
.emd-retry-badge.running{
  background:var(--bg-info); color:var(--text-info);
  border:0.5px solid rgba(55,138,221,.3);
}
.emd-retry-dot{
  display:inline-block;
  width:6px; height:6px; border-radius:50%;
  background:var(--accent-blue);
  animation:pulse 1.5s infinite;
}
.emd-retry-attempt{
  font-size:.62rem; color:var(--text-tertiary);
  background:var(--bg-primary);
  padding:1px 5px; border-radius:2px;
  margin-left:3px;
}
.emd-retry-badge.done{
  background:var(--bg-success); color:var(--text-success);
  border:0.5px solid rgba(99,153,34,.3);
}
.emd-retry-badge.failed{
  background:var(--bg-danger); color:var(--text-danger);
  border:0.5px solid rgba(239,68,68,.3);
  cursor:help;
}
/* v10 #33: 대기 상태 배지 (아직 실행 전) */
.emd-retry-badge.queued{
  background: rgba(107,114,128,.08);
  color: var(--text-tertiary);
  border: 0.5px solid rgba(107,114,128,.25);
}
.emd-retry-badge.queued svg { opacity: 0.7 }
.emd-item-retrying{background:rgba(55,138,221,.03)}
.emd-item-retried{background:rgba(99,153,34,.03); opacity:0.75}

/* v10 #33: 팝업 하단 진행 상태 바 */
.emd-progress-footer {
  padding: 12px 18px;
  border-top: 0.5px solid var(--border-light);
  background: var(--bg-secondary);
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.emd-prog-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.emd-prog-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-primary);
}
.emd-prog-count {
  font-weight: 500;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}
.emd-prog-times {
  font-size: 0.73rem;
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}
.emd-prog-eta { color: var(--text-info); font-weight: 500 }
.emd-prog-bar {
  width: 100%;
  height: 6px;
  background: var(--bg-primary);
  border-radius: 3px;
  overflow: hidden;
}
.emd-prog-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #2563eb);
  transition: width .4s ease;
}
.emd-prog-current {
  font-size: 0.73rem;
  color: var(--text-secondary);
  padding-top: 2px;
}
.emd-prog-current b { color: var(--text-primary); font-weight: 600 }
.emd-prog-spinner {
  display: inline-block;
  width: 10px; height: 10px;
  border: 1.5px solid var(--bg-info);
  border-top-color: var(--accent-blue);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
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
/* ── 예상 종료 카드 ── */
/* ── ETA 블록 (전체진행 카드 내부) ── */
.eta-block{display:flex;flex-direction:column;gap:6px;margin-top:4px;padding-top:8px;border-top:0.5px solid var(--border-light)}
.eta-divider{display:none}
.eta-block-row{display:flex;align-items:baseline;gap:6px}
.eta-block-label{font-size:.65rem;font-weight:600;color:var(--text-tertiary);white-space:nowrap;flex-shrink:0}
.eta-block-remain{font-size:.9rem;font-weight:800;color:var(--text-primary);letter-spacing:-.02em;line-height:1.2}
.eta-block-time{font-size:.75rem;color:var(--text-secondary);font-variant-numeric:tabular-nums;font-weight:500}
.eta-block-calc{font-size:.72rem;color:var(--text-tertiary);font-style:italic}
.eta-block-hint{font-size:.62rem;color:var(--text-tertiary);font-style:italic;padding-left:56px;margin-top:-2px}
.eta-soon-badge{font-size:.63rem;font-weight:700;color:#d97706;background:rgba(245,158,11,.12);padding:1px 8px;border-radius:99px;white-space:nowrap;animation:pulse .8s infinite}

/* v10 #26: 현재 작업 + 전체 작업 나란히 표시 */
.eta-dual-row {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 10px;
  align-items: flex-start;
}
.eta-dual-col {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.eta-dual-sep {
  width: 1px;
  align-self: stretch;
  background: var(--border-light);
  opacity: .7;
}
.eta-block-remain.current-task {
  color: #2563eb;  /* 파란 — 현재 작업은 시선 끌기 */
}
.current-task-name {
  font-size: .65rem;
  font-weight: 500;
  color: var(--text-tertiary);
  font-family: 'Consolas','SF Mono',monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}
/* ── 리스트 행 예상시간 배지 ── */
.ic-elapsed{font-size:.72rem;white-space:nowrap;text-align:right;display:flex;justify-content:flex-end}
.ic-eta-col{font-size:.72rem;white-space:nowrap;text-align:right;display:flex;justify-content:flex-end}
.item-eta-badge{font-size:.68rem;font-weight:600;color:#7c3aed;background:rgba(124,58,237,.09);padding:1px 5px;border-radius:5px;white-space:nowrap;font-variant-numeric:tabular-nums}
.elapsed-badge{display:inline-block;padding:1px 6px;border-radius:5px;font-size:.69rem;font-weight:600;font-variant-numeric:tabular-nums}
.elapsed-running{background:rgba(59,130,246,.1);color:#1d4ed8}
.elapsed-done{background:rgba(22,163,74,.1);color:#15803d}
.elapsed-error{background:rgba(239,68,68,.1);color:#dc2626}
.elapsed-none{color:var(--text-tertiary)}
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

/* ── 체크박스 ── */
.bulk-item-chk, .bulk-hd-chk {
  width:14px; height:14px; cursor:pointer; accent-color:#2563eb; flex-shrink:0;
}

/* ── 일괄 재이관 바 ── */
.bulk-bar {
  display:flex; align-items:center; gap:8px;
  padding:7px 12px; border-radius:8px;
  background:rgba(37,99,235,.07);
  border:0.5px solid rgba(37,99,235,.25);
  margin-bottom:6px;
}
.bulk-chk-all { display:flex; align-items:center; gap:6px; cursor:pointer; font-size:.78rem; }
.bulk-chk-label { color:var(--text-primary); font-weight:600; }
.bulk-run-btn {
  display:inline-flex; align-items:center; gap:5px;
  padding:5px 12px; border-radius:6px;
  background:#2563eb; color:#fff;
  border:none; cursor:pointer;
  font-size:.75rem; font-weight:600; font-family:var(--font);
  transition:background .12s;
}
.bulk-run-btn:hover { background:#1d4ed8; }
.bulk-run-btn:disabled { opacity:.5; cursor:not-allowed; }
.bulk-clear-btn {
  margin-left:auto; font-size:.72rem; color:var(--text-tertiary);
  background:none; border:none; cursor:pointer; padding:2px 6px;
  border-radius:4px; font-family:var(--font);
}
.bulk-clear-btn:hover { color:#ef4444; }

/* ── 일괄 재이관 모달 ── */
.bulk-modal-overlay {
  position:fixed; inset:0; background:rgba(0,0,0,.5);
  z-index:9999; display:flex; align-items:center; justify-content:center;
}
.bulk-modal {
  background:var(--bg-primary); border-radius:14px;
  width:min(680px,95vw); max-height:88vh;
  display:flex; flex-direction:column;
  box-shadow:0 8px 40px rgba(0,0,0,.3); overflow:hidden;
}
.bulk-modal-header {
  display:flex; align-items:center; gap:8px;
  padding:13px 18px; border-bottom:0.5px solid var(--border-light);
  font-size:.88rem; font-weight:600; color:var(--text-primary);
}
.bulk-modal-list {
  max-height:180px; overflow-y:auto;
  padding:8px 12px; border-bottom:0.5px solid var(--border-light);
  display:flex; flex-direction:column; gap:4px;
  background:var(--bg-secondary);
}
.bulk-modal-item {
  display:flex; align-items:center; gap:8px;
  padding:5px 8px; border-radius:6px;
  background:var(--bg-primary);
  border:0.5px solid var(--border-light);
  font-size:.78rem;
}
.bulk-modal-type-ico { font-size:.85rem; flex-shrink:0; }
.bulk-modal-name { flex:1; font-weight:500; color:var(--text-primary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.bulk-modal-type { font-size:.67rem; color:var(--text-tertiary); background:var(--bg-secondary); padding:1px 6px; border-radius:4px; flex-shrink:0; }
.bulk-modal-remove { background:none; border:none; cursor:pointer; color:var(--text-tertiary); font-size:.8rem; padding:0 4px; line-height:1; flex-shrink:0; }
.bulk-modal-remove:hover { color:#ef4444; }
.bulk-modal-body { padding:14px 18px; overflow-y:auto; display:flex; flex-direction:column; gap:12px; }

/* ── 진행 바 ── */
.bulk-progress { display:flex; flex-direction:column; gap:6px; }
.bulk-prog-bar { height:6px; background:var(--bg-secondary); border-radius:99px; overflow:hidden; }
.bulk-prog-fill { height:100%; background:#2563eb; border-radius:99px; transition:width .3s ease; }
.bulk-prog-text { font-size:.75rem; color:var(--text-secondary); display:flex; align-items:center; gap:4px; }
.bulk-cur-name { color:var(--text-tertiary); font-size:.72rem; }

/* ── 결과 목록 ── */
.bulk-result-list { display:flex; flex-direction:column; gap:3px; max-height:200px; overflow-y:auto; }
.bulk-result-row {
  display:flex; align-items:center; gap:7px;
  padding:5px 8px; border-radius:6px; font-size:.76rem;
}
.bulk-result-row.ok  { background:rgba(22,163,74,.07);  border:0.5px solid rgba(22,163,74,.2); }
.bulk-result-row.err { background:rgba(239,68,68,.07);  border:0.5px solid rgba(239,68,68,.2); }
.bulk-result-ico { font-size:.8rem; flex-shrink:0; }
.bulk-result-row.ok  .bulk-result-ico { color:#16a34a; }
.bulk-result-row.err .bulk-result-ico { color:#ef4444; }
.bulk-result-name { font-weight:600; color:var(--text-primary); flex-shrink:0; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.bulk-result-msg { color:var(--text-tertiary); font-size:.72rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

/* ── 자동 선택 뱃지 ── */
.bulk-auto-badge {
  font-size:.65rem; font-weight:700;
  padding:1px 7px; border-radius:99px;
  background:rgba(37,99,235,.1);
  color:#2563eb;
  letter-spacing:.03em;
}

/* ── 트랜지션 ── */
.bulk-bar-enter-active, .bulk-bar-leave-active { transition:all .2s ease; }
.bulk-bar-enter-from, .bulk-bar-leave-to { opacity:0; transform:translateY(-6px); max-height:0; }

.cdc-badge-jm{font-size:.6rem;font-weight:700;padding:1px 5px;border-radius:3px;background:rgba(139,92,246,.12);color:#6d28d9;margin-right:4px;flex-shrink:0}
.cdc-phase-simple{display:flex;align-items:center;gap:6px;padding:8px 0;font-size:.82rem;color:#6d28d9}
.cdc-phase-ico{font-size:1rem}
.cdc-phase-txt{font-weight:600}
/* v90.24: 전체 진행 KPI 카드의 객체 진행 표시 */
.kpi-obj-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed var(--border-light, #e2e8f0);
}

/* ════════════════════════════════════════════════════════════ */
/* v95_p47 (2026-05-05 본부장님): 객체 진행바 분리 + 한 줄 표시   */
/* ════════════════════════════════════════════════════════════ */
.kpi-obj-divider {
  margin-top: 10px;
  margin-bottom: 8px;
  border-top: 1px dashed var(--border-light, #e2e8f0);
}
.kpi-obj-prog-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 4px;
}
.kpi-obj-prog-label {
  font-size: 11px;
  color: var(--color-text-secondary, #64748b);
  font-weight: 600;
}
.kpi-obj-prog-badge {
  font-size: 11px; font-weight: 700;
  color: var(--color-text-primary, #0f172a);
}
.kpi-obj-prog-track {
  height: 6px;
  background: var(--color-background-tertiary, #f1f5f9);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 6px;
}
.kpi-obj-prog-fill {
  height: 100%;
  background: linear-gradient(to right, #3b82f6, #6366f1);
  border-radius: 3px;
  transition: width 0.4s ease;
}
.kpi-obj-prog-fill.obj-prog-done {
  background: linear-gradient(to right, #22c55e, #16a34a);
}
.kpi-obj-prog-fill.obj-prog-failed {
  background: linear-gradient(to right, #f59e0b, #dc2626);
}

/* v95_p47: 한 줄 compact 객체 카운트 */
.kpi-obj-row-compact {
  display: flex;
  flex-wrap: nowrap;          /* 한 줄 강제 */
  gap: 4px;
  margin-top: 4px;
  padding-top: 0;
  border-top: none;
  overflow: hidden;
}
.kpi-obj-item-compact {
  flex: 1 1 0;                /* 균등 분배 */
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
  padding: 2px 4px;
  font-size: 9.5px;           /* 약간 축소 */
  font-weight: 600;
  border-radius: 4px;
  white-space: nowrap;
  overflow: hidden;
}
.kpi-obj-item-compact .kpi-obj-icon {
  font-size: 10px;
  flex-shrink: 0;
}
.kpi-obj-item-compact .kpi-obj-text {
  overflow: hidden;
  text-overflow: ellipsis;
}

.kpi-obj-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 7px;
  font-size: 10px;
  font-weight: 600;
  background: var(--color-background-tertiary, #f1f5f9);
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 99px;
  color: var(--color-text-secondary, #64748b);
  transition: all 0.2s;
}
.kpi-obj-item.obj-done {
  background: rgba(34, 197, 94, 0.08);
  border-color: rgba(34, 197, 94, 0.3);
  color: #16a34a;
}
.kpi-obj-item.obj-running {
  background: rgba(59, 130, 246, 0.1);
  border-color: rgba(59, 130, 246, 0.4);
  color: #2563eb;
}
.kpi-obj-item.obj-failed {
  background: rgba(239, 68, 68, 0.08);
  border-color: rgba(239, 68, 68, 0.3);
  color: #dc2626;
}
.kpi-obj-icon {
  font-size: 11px;
  font-weight: 700;
}
.kpi-obj-text {
  font-variant-numeric: tabular-nums;
}
.kpi-obj-spinner {
  font-size: 10px;
  animation: kpi-obj-spin 1.5s linear infinite;
  display: inline-block;
}
@keyframes kpi-obj-spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
.kpi-obj-fail-badge {
  background: #dc2626;
  color: #fff;
  font-size: 8px;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 99px;
  margin-left: 1px;
}


/* ── v95_p107 hotfix_046: 오류 상세 모달 → 플로팅 윈도우 ───────── */
.emd-float-root{
  position:fixed; inset:0; z-index:9999;
  pointer-events:none; /* 배경 클릭 통과 — 화면 컨트롤 가능 */
}
.emd-float-root > *{ pointer-events:auto; }
.emd-float-header{
  display:flex; align-items:center; gap:8px;
  padding:14px 18px;
  border-bottom:0.5px solid var(--border-light);
  cursor:move;
  user-select:none;
  touch-action:none;
}
.emd-float-header > span{ cursor:move; }
.emd-float-header button{ cursor:pointer; }
.emd-float-root.emd-float-min .emd-float-card > *:not(.emd-float-header){
  display:none !important;
}
.emd-float-root.emd-float-min .emd-float-card{
  max-height:none !important;
  height:auto !important;
}
/* ── /h046 ────────────────────────────────────────────────────── */


/* ── v95_p107 hotfix_047: 오류만 선택 + 시도 횟수 표시 ────────── */
.bulk-only-err-btn{
  display:inline-flex; align-items:center; gap:4px;
  padding:4px 10px;
  border:1px solid rgba(220,38,38,.3);
  background:rgba(220,38,38,.05);
  color:#b91c1c;
  border-radius:6px;
  font-size:.72rem;
  font-weight:600;
  cursor:pointer;
  margin-left:8px;
  transition: background .12s;
}
.bulk-only-err-btn:hover:not(:disabled){ background:rgba(220,38,38,.12); }
.bulk-only-err-btn:disabled{ opacity:.5; cursor:not-allowed; }
.emd-retry-attempt-cnt{ font-weight:700; color:#1d4ed8; }
/* ── /h047 ────────────────────────────────────────────────────── */


/* ── v95_p107 hotfix_051: 모달 resize handle + AI 모드 카드 레이아웃 ───── */
.emd-float-resize{
  position:absolute; bottom:0; right:0;
  width:18px; height:18px;
  cursor:nwse-resize;
  opacity:.35;
  background-image:
    linear-gradient(135deg,
      transparent 0%, transparent 38%,
      var(--text-tertiary) 38%, var(--text-tertiary) 46%,
      transparent 46%, transparent 60%,
      var(--text-tertiary) 60%, var(--text-tertiary) 68%,
      transparent 68%, transparent 82%,
      var(--text-tertiary) 82%, var(--text-tertiary) 90%,
      transparent 90%);
  z-index:10;
}
.emd-float-resize:hover{ opacity:.7; }

/* AI 모드 선택 시: 나머지 3카드 컴팩트, AI 카드는 우측 컬럼 전체 차지 */
.brp-grid.has-ai-active{
  grid-template-columns: 0.75fr 1.25fr;
}
.brp-grid.has-ai-active .brp-opt:not(.brp-opt-ai){
  padding: 6px 10px;
}
.brp-grid.has-ai-active .brp-opt:not(.brp-opt-ai) .brp-opt-desc{
  display: none;
}
.brp-grid.has-ai-active .brp-opt:not(.brp-opt-ai) .brp-opt-head{
  gap: 6px;
}
.brp-grid.has-ai-active .brp-opt.brp-opt-ai{
  grid-column: 2;
  grid-row: 1 / -1;
}
/* ── /h051 ──────────────────────────────────────────────────────────── */


/* ── v95_p107 hotfix_054: 일괄 재처리 중지 버튼 ─────────────────────── */
.emd-prog-abort-btn{
  padding: 3px 10px;
  border: 1px solid rgba(220,38,38,.4);
  background: rgba(220,38,38,.06);
  color: #b91c1c;
  border-radius: 5px;
  font-size: .68rem;
  font-weight: 700;
  cursor: pointer;
  margin-left: 8px;
  transition: background .12s;
}
.emd-prog-abort-btn:hover{ background: rgba(220,38,38,.15); }
.emd-prog-aborting{
  color: #b91c1c;
  font-weight: 600;
  font-size: .68rem;
  margin-left: 8px;
  font-style: italic;
}
/* ── /h054 ───────────────────────────────────────────────────────── */

</style>
