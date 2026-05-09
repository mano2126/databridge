<template>
  <div>
    <div class="page-title">Job 관리</div>
    <div class="page-desc">마이그레이션 Job 목록을 관리합니다</div>

    <div class="kpi-grid">
      <div class="kpi-card"><div class="kpi-label">전체</div><div class="kpi-value info">{{ jobs.jobs.length }}</div></div>
      <div class="kpi-card"><div class="kpi-label">실행 중</div><div class="kpi-value ok">{{ jobs.runningJobs.length }}</div></div>
      <div class="kpi-card"><div class="kpi-label">완료</div><div class="kpi-value">{{ jobs.jobs.filter(j=>j.status==='completed').length }}</div></div>
      <div class="kpi-card"><div class="kpi-label">오류/중단</div><div class="kpi-value err">{{ jobs.jobs.filter(j=>j.status==='error'||j.status==='aborted').length }}</div></div>
    </div>

    <!-- 필터 + 버튼 -->
    <div class="card" style="margin-bottom:10px;padding:10px 14px">
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
        <span style="font-size:11.5px;color:var(--text-secondary)">상태 필터</span>
        <button v-for="f in filters" :key="f.v"
          class="filter-btn" :class="{active:activeFilter===f.v}"
          @click="activeFilter=f.v">
          {{ f.label }}
          <span class="f-cnt">{{ filterCount(f.v) }}</span>
        </button>
        <div style="margin-left:auto;display:flex;gap:6px;align-items:center">
          <span v-if="selected.size > 0" style="font-size:11px;color:var(--text-tertiary)">
            {{ selected.size }}개 선택됨
          </span>
          <button v-if="selected.size > 0" class="act-btn danger" @click="doBulkDel"
            title="선택 항목 삭제">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px">
              <polyline points="2,3.5 12,3.5"/><path d="M5,3.5 V2 H9 V3.5"/>
              <path d="M3.5,3.5 L4.5,12 H9.5 L10.5,3.5"/>
            </svg>
            선택 삭제
          </button>
          <button class="act-btn" @click="jobs.fetch()" title="새로고침">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.6" style="width:12px;height:12px">
              <path d="M13 2.5A6 6 0 1 1 7.5 1"/><polyline points="8,1 13,1 13,5"/>
            </svg>
          </button>
          <button class="btn btn-primary" style="padding:5px 12px;font-size:12px"
            @click="$router.push({ path: '/jobs/wizard', query: { fresh: '1' } })">+ New Job</button>
        </div>
      </div>
    </div>

    <!-- Job 테이블 -->
    <div class="card" style="padding:0;overflow:hidden">
      <table class="job-tbl">
        <thead>
          <tr>
            <!-- 전체선택 체크박스 아이콘 -->
            <th class="th-chk" @click="toggleAll" :title="allSelected ? '전체 해제' : '전체 선택'">
              <div class="chk-wrap">
                <span class="chk-icon" :class="{checked: allSelected, partial: someSelected && !allSelected}">
                  <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline v-if="allSelected" points="1.5,6 4.5,9 10.5,3" stroke-linecap="round" stroke-linejoin="round"/>
                    <line v-else-if="someSelected" x1="1.5" y1="6" x2="10.5" y2="6" stroke-linecap="round"/>
                  </svg>
                </span>
              </div>
            </th>
            <th class="th-sort" :class="{'sort-active': sortCol==='name'}" @click="setSort('name')">
              Job 이름 <SortIco :col="'name'" :cur="sortCol" :dir="sortDir"/>
            </th>
            <th>소스 → 타겟</th>
            <th class="th-sort" :class="{'sort-active': sortCol==='progress'}" @click="setSort('progress')">
              진행률 <SortIco :col="'progress'" :cur="sortCol" :dir="sortDir"/>
            </th>
            <th>처리 rows</th>
            <th>현재 테이블</th>
            <th class="th-sort" :class="{'sort-active': sortCol==='speed'}" @click="setSort('speed')">
              속도 <SortIco :col="'speed'" :cur="sortCol" :dir="sortDir"/>
            </th>
            <th class="th-sort" :class="{'sort-active': sortCol==='status'}" @click="setSort('status')">
              상태 <SortIco :col="'status'" :cur="sortCol" :dir="sortDir"/>
            </th>
            <th class="th-sort" :class="{'sort-active': sortCol==='created_at'}" @click="setSort('created_at')">
              생성일 <SortIco :col="'created_at'" :cur="sortCol" :dir="sortDir"/>
            </th>
            <th class="th-sort" :class="{'sort-active': sortCol==='started_at'}" @click="setSort('started_at')">
              시작 시각 <SortIco :col="'started_at'" :cur="sortCol" :dir="sortDir"/>
            </th>
            <th class="th-sort" :class="{'sort-active': sortCol==='finished_at'}" @click="setSort('finished_at')">
              완료 시각 <SortIco :col="'finished_at'" :cur="sortCol" :dir="sortDir"/>
            </th>
            <th class="th-sort" :class="{'sort-active': sortCol==='duration'}" @click="setSort('duration')">
              실행 시간 <SortIco :col="'duration'" :cur="sortCol" :dir="sortDir"/>
            </th>
            <th style="min-width:160px">작업</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="j in groupedJobList" :key="j.id">
          <tr
              :class="{'row-err':j.status==='error','row-run':j.status==='running','row-sel':selected.has(j.id),'row-cdc-group':(j._group_count||1)>1}"
              @click.exact="toggleOne(j.id)">
            <!-- 체크박스 셀 -->
            <td class="td-chk" @click.stop="toggleOne(j.id)">
              <div class="chk-wrap">
                <span class="chk-icon" :class="{checked: selected.has(j.id)}">
                  <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline v-if="selected.has(j.id)" points="1.5,6 4.5,9 10.5,3" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </span>
              </div>
            </td>
            <td class="job-name-cell" :title="j.name">
              <!-- CDC 그룹 펼치기 버튼 -->
              <button v-if="(j._group_count||1) > 1" class="cdc-grp-btn"
                      :class="{open: expandedJobGroups.has(j._group_key)}"
                      @click.stop="toggleJobGroup(j._group_key)"
                      :title="expandedJobGroups.has(j._group_key) ? '접기' : `실행 이력 ${j._group_count-1}건 펼치기`">
                <svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="3,2 7,5 3,8"/>
                </svg>
                <span class="cdc-grp-cnt">{{ j._group_count }}</span>
              </button>
              {{ j.name }}
            </td>
            <td>
              <div style="display:flex;align-items:center;gap:4px">
                <span class="mini-ico" :style="{background:m(j.src_db)?.bg,color:m(j.src_db)?.color}">{{ m(j.src_db)?.label }}</span>
                <span style="font-size:10px;color:var(--text-tertiary)">→</span>
                <span class="mini-ico" :style="{background:m(j.tgt_db)?.bg,color:m(j.tgt_db)?.color}">{{ m(j.tgt_db)?.label }}</span>
                <span style="font-size:10.5px;color:var(--text-tertiary);max-width:80px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                  {{ j.tgt_database||j.tgt_db }}
                </span>
              </div>
            </td>
            <td>
              <div style="display:flex;align-items:center;gap:6px">
                <div class="progress-wrap" style="width:60px">
                  <div class="progress-fill" :class="j.status==='error'?'red':j.status==='completed'?'green':'blue'"
                       :style="{width:(j.progress||0)+'%'}"></div>
                </div>
                <span style="font-size:11px;color:var(--text-tertiary)">{{ (j.progress||0).toFixed(0) }}%</span>
              </div>
            </td>
            <td style="font-size:11.5px;color:var(--text-secondary)">
              {{ fmtRows(j.rows_processed||0) }} / {{ fmtRows(j.rows_total||0) }}
              <span v-if="j.rows_error>0" style="color:var(--text-danger);font-size:10.5px;margin-left:4px">
                (오류 {{ j.rows_error }})
              </span>
            </td>
            <td>
              <span v-if="j.current_table&&j.status==='running'" class="tbl-tag">{{ j.current_table }}</span>
              <span v-else style="color:var(--text-tertiary);font-size:11px">—</span>
            </td>
            <td style="font-size:11.5px;color:var(--text-secondary)">
              {{ j.status==='running'?(j.speed||0).toLocaleString()+' /s':'-' }}
            </td>
            <td><span class="pill" :class="pillCls(j.status)">{{ statusLbl(j.status) }}</span></td>
            <td style="font-size:11px;color:var(--text-tertiary)">{{ fmtDate(j.created_at) }}</td>
            <td class="time-cell">{{ fmtDateTime(j.started_at) }}</td>
            <td class="time-cell">{{ fmtDateTime(j.finished_at) }}</td>
            <td class="time-cell dur" :class="{dur_running: j.status==='running'}" :title="calcDurationSec(j)+'초'">{{ fmtDuration(j) }}</td>
            <td>
              <div class="btn-group">
                <!-- 실행 중 -->
                <template v-if="j.status==='running'">
                  <button class="jb warn" @click="doPause(j.id)" title="일시정지"><svg viewBox="0 0 14 14" fill="currentColor" stroke="none" style="width:11px;height:11px"><rect x="2" y="1" width="3.5" height="12" rx="1"/><rect x="8.5" y="1" width="3.5" height="12" rx="1"/></svg></button>
                  <button class="jb danger" @click="doStop(j.id)" title="이관 중단"><svg viewBox="0 0 14 14" fill="currentColor" stroke="none" style="width:11px;height:11px"><rect x="1.5" y="1.5" width="11" height="11" rx="2"/></svg></button>
                </template>
                <!-- 일시정지 -->
                <template v-else-if="j.status==='paused'">
                  <button class="jb ok" @click="doResume(j.id)" title="재개"><svg viewBox="0 0 14 14" fill="currentColor" stroke="none" style="width:11px;height:11px"><polygon points="2,1 13,7 2,13"/></svg></button>
                  <button class="jb danger" @click="doStop(j.id)" title="중단">⏹ 중단</button>
                </template>
                <!-- 완료/오류/중단 → 재실행 가능 -->
                <template v-else-if="['completed','error','aborted','idle'].includes(j.status)">
                  <button class="jb primary" @click="doRestart(j)" title="재실행"><svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.8" style="width:11px;height:11px"><path d="M13 3A6 6 0 1 1 8 1"/><polyline points="9,1 13,1 13,4"/></svg></button>
                </template>

                <!-- 공통 버튼 -->
                <button class="jb" @click.stop="$router.push('/jobs/monitor')" title="이관 모니터에서 보기"><svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px"><rect x="1" y="2" width="12" height="8" rx="1"/><polyline points="3,8 5,5.5 7,6.5 9,4 11,5.5" stroke-width="1.3"/><line x1="4" y1="12" x2="10" y2="12"/><line x1="7" y1="10" x2="7" y2="12"/></svg></button>
                <button class="jb" @click="showLogs(j)" title="실행 로그 보기"><svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px"><rect x="1.5" y="1" width="11" height="12" rx="1.5"/><line x1="4" y1="4.5" x2="10" y2="4.5"/><line x1="4" y1="7" x2="10" y2="7"/><line x1="4" y1="9.5" x2="7.5" y2="9.5"/></svg></button>
                <button class="jb danger" @click="doDel(j.id)" title="삭제"><svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px"><polyline points="2,3.5 12,3.5"/><path d="M5,3.5 V2 H9 V3.5"/><path d="M3.5,3.5 L4.5,12 H9.5 L10.5,3.5"/><line x1="6" y1="6" x2="6" y2="9.5"/><line x1="8" y1="6" x2="8" y2="9.5"/></svg></button>
              </div>
            </td>
          </tr>
          <!-- 펼쳐진 CDC 그룹 자식들 -->
          <template v-if="(j._group_count||1) > 1 && expandedJobGroups.has(j._group_key)">
            <tr v-for="child in j._group_children" :key="child.id"
                :class="{'row-err':child.status==='error','row-run':child.status==='running','row-sel':selected.has(child.id),'row-cdc-child':true}"
                @click.exact="toggleOne(child.id)">
              <td class="td-chk" @click.stop="toggleOne(child.id)">
                <div class="chk-wrap">
                  <span class="chk-icon" :class="{checked: selected.has(child.id)}">
                    <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline v-if="selected.has(child.id)" points="1.5,6 4.5,9 10.5,3" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                  </span>
                </div>
              </td>
              <td class="job-name-cell job-name-child" :title="child.name">
                <span class="child-prefix">↳</span> {{ child.name }}
              </td>
              <td>
                <div style="display:flex;align-items:center;gap:4px">
                  <span class="mini-ico" :style="{background:m(child.src_db)?.bg,color:m(child.src_db)?.color}">{{ m(child.src_db)?.label }}</span>
                  <span style="font-size:10px;color:var(--text-tertiary)">→</span>
                  <span class="mini-ico" :style="{background:m(child.tgt_db)?.bg,color:m(child.tgt_db)?.color}">{{ m(child.tgt_db)?.label }}</span>
                  <span style="font-size:10.5px;color:var(--text-tertiary);max-width:80px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ child.tgt_database||child.tgt_db }}</span>
                </div>
              </td>
              <td>
                <div style="display:flex;align-items:center;gap:6px">
                  <div class="progress-wrap" style="width:60px">
                    <div class="progress-fill" :class="child.status==='error'?'red':child.status==='completed'?'green':'blue'"
                         :style="{width:(child.progress||0)+'%'}"></div>
                  </div>
                  <span style="font-size:11px;color:var(--text-tertiary)">{{ (child.progress||0).toFixed(0) }}%</span>
                </div>
              </td>
              <td style="font-size:11.5px;color:var(--text-secondary)">
                {{ fmtRows(child.rows_processed||0) }} / {{ fmtRows(child.rows_total||0) }}
                <span v-if="child.rows_error>0" style="color:var(--text-danger);font-size:10.5px;margin-left:4px">(오류 {{ child.rows_error }})</span>
              </td>
              <td>
                <span v-if="child.current_table&&child.status==='running'" class="tbl-tag">{{ child.current_table }}</span>
                <span v-else style="color:var(--text-tertiary);font-size:11px">—</span>
              </td>
              <td style="font-size:11.5px;color:var(--text-secondary)">
                {{ child.status==='running'?(child.speed||0).toLocaleString()+' /s':'-' }}
              </td>
              <td><span class="pill" :class="pillCls(child.status)">{{ statusLbl(child.status) }}</span></td>
              <td style="font-size:11px;color:var(--text-tertiary)">{{ fmtDate(child.created_at) }}</td>
              <td class="time-cell">{{ fmtDateTime(child.started_at) }}</td>
              <td class="time-cell">{{ fmtDateTime(child.finished_at) }}</td>
              <td class="time-cell dur" :class="{dur_running: child.status==='running'}" :title="calcDurationSec(child)+'초'">{{ fmtDuration(child) }}</td>
              <td>
                <div class="btn-group">
                  <button class="jb" @click="showLogs(child)" title="실행 로그 보기"><svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px"><rect x="1.5" y="1" width="11" height="12" rx="1.5"/><line x1="4" y1="4.5" x2="10" y2="4.5"/><line x1="4" y1="7" x2="10" y2="7"/><line x1="4" y1="9.5" x2="7.5" y2="9.5"/></svg></button>
                  <button class="jb danger" @click="doDel(child.id)" title="삭제"><svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px"><polyline points="2,3.5 12,3.5"/><path d="M5,3.5 V2 H9 V3.5"/><path d="M3.5,3.5 L4.5,12 H9.5 L10.5,3.5"/><line x1="6" y1="6" x2="6" y2="9.5"/><line x1="8" y1="6" x2="8" y2="9.5"/></svg></button>
                </div>
              </td>
            </tr>
          </template>
          </template>
          <tr v-if="!filtered.length">
            <td colspan="13" class="empty-state">Job이 없습니다</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 로그 모달 -->
    <div v-if="logJob" class="modal-overlay" @click.self="logJob=null">
      <div class="modal" style="max-width:680px;width:95%">
        <div class="modal-title" style="display:flex;align-items:center;justify-content:space-between">
          <span>{{ logJob.name }} — 실행 로그</span>
          <span class="pill" :class="pillCls(logJob.status)">{{ statusLbl(logJob.status) }}</span>
        </div>

        <!-- Job 요약 -->
        <div class="log-summary">
          <div class="ls-item"><span class="ls-l">소스</span><span class="ls-v">{{ logJob.src_db }} / {{ logJob.src_database }}</span></div>
          <div class="ls-item"><span class="ls-l">타겟</span><span class="ls-v">{{ logJob.tgt_db }} / {{ logJob.tgt_database }}</span></div>
          <div class="ls-item"><span class="ls-l">진행률</span><span class="ls-v">{{ (logJob.progress||0).toFixed(1) }}%</span></div>
          <div class="ls-item"><span class="ls-l">처리 rows</span><span class="ls-v">{{ (logJob.rows_processed||0).toLocaleString() }}</span></div>
          <div class="ls-item"><span class="ls-l">오류 rows</span><span class="ls-v" :style="{color:logJob.rows_error>0?'var(--text-danger)':'var(--text-success)'}">{{ logJob.rows_error||0 }}</span></div>
          <div class="ls-item" v-if="logJob.error_message"><span class="ls-l">오류 메시지</span><span class="ls-v" style="color:var(--text-danger)">{{ logJob.error_message }}</span></div>
        </div>

        <!-- 로그 -->
        <div class="log-box" ref="logBoxEl">
          <div v-if="loadingLogs" class="empty-state" style="padding:20px">
            <span class="spinner" style="width:16px;height:16px;display:inline-block"></span>
          </div>
          <template v-else>
            <div v-for="(l,i) in logItems" :key="i" class="log-line" :class="'log-'+l.level">
              <span class="log-t">{{ l.time }}</span>
              <span class="log-tag">[{{ l.tag }}]</span>
              <span>{{ l.message }}</span>
            </div>
            <div v-if="!logItems.length" class="empty-state" style="padding:16px">로그가 없습니다</div>
          </template>
        </div>

        <div class="modal-btns">
          <button class="btn" @click="logJob=null">닫기</button>
          <button class="btn" @click="showLogs(logJob)">↻</button>
          <button v-if="['completed','error','aborted','idle'].includes(logJob.status)"
            class="btn btn-primary" @click="doRestart(logJob);logJob=null">
            ↺ 재실행
          </button>
        </div>
      </div>
    </div>

    <!-- 재실행 확인 모달 -->
    <div v-if="restartTarget" class="modal-overlay" @click.self="restartTarget=null">
      <div class="modal" style="max-width:480px">
        <div class="modal-title">Job 재실행 확인</div>

        <div class="restart-info">
          <div class="ri-row">
            <span class="ri-l">Job 이름</span>
            <span class="ri-v">{{ restartTarget.name }}</span>
          </div>
          <div class="ri-row">
            <span class="ri-l">소스 DB</span>
            <span class="ri-v">{{ restartTarget.src_db }} / {{ restartTarget.src_database }}</span>
          </div>
          <div class="ri-row">
            <span class="ri-l">타겟 DB</span>
            <span class="ri-v">{{ restartTarget.tgt_db }} / {{ restartTarget.tgt_database }}</span>
          </div>
          <div class="ri-row">
            <span class="ri-l">이관 테이블</span>
            <span class="ri-v">{{ restartTarget.tables?.length || 0 }}개</span>
          </div>
          <div class="ri-row">
            <span class="ri-l">이전 상태</span>
            <span class="ri-v"><span class="pill" :class="pillCls(restartTarget.status)">{{ statusLbl(restartTarget.status) }}</span></span>
          </div>
        </div>

        <!-- 재실행 옵션 -->
        <div class="restart-opts">
          <label class="opt-chk">
            <input type="checkbox" v-model="restartOpts.truncate"/>
            타겟 테이블 TRUNCATE 후 재이관
          </label>
          <label class="opt-chk">
            <input type="checkbox" v-model="restartOpts.createTbl"/>
            테이블 없으면 자동 생성
          </label>
        </div>

        <div v-if="restartOpts.truncate" class="warn-banner" style="margin-top:10px">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px;flex-shrink:0"><path d="M8 2L14 14H2L8 2z"/><line x1="8" y1="7" x2="8" y2="10"/></svg>
          타겟 테이블의 기존 데이터가 모두 삭제됩니다
        </div>

        <div class="modal-btns">
          <button class="btn" @click="restartTarget=null">취소</button>
          <button class="btn btn-primary" @click="confirmRestart" :disabled="restarting">
            <span v-if="restarting" class="spinner" style="width:13px;height:13px;border-top-color:#fff"></span>
            <svg v-else viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px">
              <polyline points="1,4 1,1 4,1"/><path d="M1 1 A7 7 0 1 1 14 8"/>
            </svg>
            {{ restarting ? '재실행 중...' : '재실행 시작' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<!-- v90.26: SortIco render function 으로 - script setup 안에서 정의 -->

<script setup>
import { fmtDate, fmtDateTime } from '@/utils/dateUtils.js'
import { ref, computed, onMounted, nextTick, h } from 'vue'
import { useConnectorStore } from '@/store/connectorStore.js'
import { useJobStore } from '@/store/jobStore.js'
import { useAppStore } from '@/store/appStore.js'
import { jobsApi } from '@/api/index.js'

// v90.26: 정렬 아이콘 - render function (template 문자열 X)
const SortIco = {
  props: ['col','cur','dir'],
  render() {
    const isActive = this.col === this.cur
    const isAsc  = isActive && this.dir === 'asc'
    const isDesc = isActive && this.dir === 'desc'
    const accent = 'var(--accent-blue)'
    return h('span', { class: ['sort-ico', { active: isActive }] }, [
      h('svg', {
        viewBox: '0 0 10 14',
        fill: 'none',
        stroke: 'currentColor',
        'stroke-width': '1.6',
        style: 'width:8px;height:11px',
      }, [
        h('polyline', { stroke: isAsc ? accent : 'currentColor',  points: '1,6 5,1 9,6' }),
        h('polyline', { stroke: isDesc ? accent : 'currentColor', points: '1,8 5,13 9,8' }),
      ]),
    ])
  },
}
import { DB_META } from '@/constants/dbMeta.js'

const jobs = useJobStore()
const connector = useConnectorStore()
const app  = useAppStore()

const activeFilter  = ref('all')
const logJob        = ref(null)

// ── 정렬 ────────────────────────────────────
const sortCol = ref('created_at')
const sortDir = ref('desc')

function setSort(col) {
  if (sortCol.value === col) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortCol.value = col
    sortDir.value = 'desc'
  }
}

// ── 선택 ────────────────────────────────────
const selected = ref(new Set())

const allSelected = computed(() =>
  filtered.value.length > 0 && filtered.value.every(j => selected.value.has(j.id))
)
const someSelected = computed(() =>
  filtered.value.some(j => selected.value.has(j.id))
)

function toggleOne(id) {
  const s = new Set(selected.value)
  s.has(id) ? s.delete(id) : s.add(id)
  selected.value = s
}

function toggleAll() {
  if (allSelected.value) {
    selected.value = new Set()
  } else {
    selected.value = new Set(filtered.value.map(j => j.id))
  }
}
const logItems      = ref([])
const logBoxEl      = ref(null)
const loadingLogs   = ref(false)
const restartTarget = ref(null)
const restarting    = ref(false)
const restartOpts   = ref({ truncate: false, createTbl: true })

const filters = [
  { v:'all',      label:'전체' },
  { v:'running',  label:'실행 중' },
  { v:'paused',   label:'일시정지' },
  { v:'completed',label:'완료' },
  { v:'error',    label:'오류' },
  { v:'aborted',  label:'중단' },
  { v:'idle',     label:'대기' },
]

const m         = t => DB_META[t]||{label:'??',bg:'#eee',color:'#333'}
const fmtRows   = n => n>=1e6?(n/1e6).toFixed(1)+'M':n>=1e3?Math.round(n/1e3)+'K':String(n||0)

// 날짜+시각 (시:분:초)


// 실행 시간 (초 단위)
function calcDurationSec(j) {
  if (!j.started_at) return 0
  const start = new Date(j.started_at).getTime()
  const end   = j.finished_at ? new Date(j.finished_at).getTime() : Date.now()
  return Math.max(0, Math.floor((end - start) / 1000))
}

// 실행 시간 표시 (1h 23m 45s)
function fmtDuration(j) {
  if (!j.started_at) return '—'
  const sec = calcDurationSec(j)
  if (sec < 60) return sec + 's'
  const m = Math.floor(sec / 60)
  const s = sec % 60
  if (m < 60) return m + 'm ' + s + 's'
  const h = Math.floor(m / 60)
  return h + 'h ' + (m % 60) + 'm ' + s + 's'
}
const pillCls   = s => ({running:'pill-run',completed:'pill-ok',error:'pill-err',idle:'pill-idle',paused:'pill-pause',aborted:'pill-idle'}[s]||'pill-idle')
const statusLbl = s => ({running:'실행 중',completed:'완료',error:'오류',idle:'대기',paused:'일시정지',aborted:'중단'}[s]||s)

const filtered = computed(() =>
  activeFilter.value === 'all'
    ? jobs.jobs
    : jobs.jobs.filter(j => j.status === activeFilter.value)
)

const sortedFiltered = computed(() => {
  const list = [...filtered.value]
  const col  = sortCol.value
  const dir  = sortDir.value === 'asc' ? 1 : -1

  return list.sort((a, b) => {
    let av = a[col] ?? ''
    let bv = b[col] ?? ''

    // 실행시간은 계산값
    if (col === 'duration') {
      av = calcDurationSec(a)
      bv = calcDurationSec(b)
    }
    // 숫자
    if (typeof av === 'number' || col === 'progress' || col === 'speed' || col === 'duration') {
      return (Number(av||0) - Number(bv||0)) * dir
    }
    // 날짜 문자열
    if (col.endsWith('_at')) {
      return (av < bv ? -1 : av > bv ? 1 : 0) * dir
    }
    // 문자열
    return String(av).localeCompare(String(bv), 'ko') * dir
  })
})

// v9 #64: CDC Job 그룹화
// CDC Job 은 매 실행마다 새로 생기므로, Job 관리 화면에서는
// "같은 cdc_cfg_id" 인 Job 들을 하나로 묶어서 '가장 먼저 생성된 것' 을 대표로 표시.
// 나머지는 펼침으로 접근.
const expandedJobGroups = ref(new Set())
function toggleJobGroup(key) {
  const s = new Set(expandedJobGroups.value)
  s.has(key) ? s.delete(key) : s.add(key)
  expandedJobGroups.value = s
}

const groupedJobList = computed(() => {
  const groups = new Map()
  for (const j of sortedFiltered.value) {
    let key
    if (j.job_type === 'cdc') {
      // cdc_cfg_id 필드 우선, 없으면 id 에서 suffix 제거
      const cfgId = j.cdc_cfg_id
        || (String(j.id).match(/^(.+)_[0-9a-f]{6}$/i)?.[1] ?? j.id)
      key = `cdc:${cfgId}`
    } else {
      key = `job:${j.id}`
    }
    if (!groups.has(key)) groups.set(key, { key, items: [] })
    groups.get(key).items.push(j)
  }
  const result = []
  for (const g of groups.values()) {
    // 대표: '가장 먼저 생성된 것' (CIO 요청)
    g.items.sort((a, b) =>
      new Date(a.created_at||a.started_at||0) - new Date(b.created_at||b.started_at||0))
    const head = {
      ...g.items[0],
      _group_key: g.key,
      _group_count: g.items.length,
      _group_children: g.items.slice(1),  // 더 나중 것들
    }
    result.push(head)
  }
  // 그룹 간 정렬 — 현재 sortCol 기준
  const col = sortCol.value
  const dir = sortDir.value === 'asc' ? 1 : -1
  result.sort((a, b) => {
    let av = a[col] ?? '', bv = b[col] ?? ''
    if (col === 'duration') { av = calcDurationSec(a); bv = calcDurationSec(b) }
    if (typeof av === 'number' || col === 'progress' || col === 'speed' || col === 'duration') {
      return (Number(av||0) - Number(bv||0)) * dir
    }
    if (col.endsWith('_at')) return (av < bv ? -1 : av > bv ? 1 : 0) * dir
    return String(av).localeCompare(String(bv), 'ko') * dir
  })
  return result
})

const filterCount = v => v==='all' ? jobs.jobs.length : jobs.jobs.filter(j=>j.status===v).length

onMounted(() => jobs.fetch())

/* ── 액션 ─────────────────────────────────────────── */
async function doPause(id) {
  await jobs.pause(id)
  app.notify('일시정지됨', 'warn')
}
async function doResume(id) {
  await jobs.resume(id)
  app.notify('재개됨', 'success')
}
async function doStop(id) {
  if (!confirm('이관을 중단하시겠습니까?')) return
  await jobs.stop(id)
  app.notify('중단됨', 'warn')
}
async function doDel(id) {
  if (!confirm('이 Job을 삭제하시겠습니까?')) return
  await jobs.del(id)
  selected.value = new Set([...selected.value].filter(s => s !== id))
  app.notify('삭제됨')
}

async function doBulkDel() {
  const cnt = selected.value.size
  if (!confirm(`선택한 ${cnt}개 Job을 삭제하시겠습니까?`)) return
  const ids = [...selected.value]
  for (const id of ids) {
    await jobs.del(id)
  }
  selected.value = new Set()
  app.notify(`${cnt}개 삭제됨`)
}

/* ── 로그 보기 ──────────────────────────────────── */
async function showLogs(j) {
  logJob.value    = j
  logItems.value  = []
  loadingLogs.value = true
  try {
    logItems.value = await jobsApi.logs(j.id)
    await nextTick()
    if (logBoxEl.value) logBoxEl.value.scrollTop = logBoxEl.value.scrollHeight
  } catch (e) {
    logItems.value = [{ time:'--:--:--', level:'error', tag:'System', message:'로그 조회 실패: ' + e.message }]
  } finally {
    loadingLogs.value = false
  }
}

/* ── 재실행 ─────────────────────────────────────── */
function doRestart(j) {
  restartTarget.value = j
  restartOpts.value   = { truncate: false, createTbl: true }
}

async function confirmRestart() {
  if (!restartTarget.value) return
  restarting.value = true
  const j = restartTarget.value

  try {
    // 재실행 옵션 적용
    j.truncate_target = restartOpts.value.truncate
    j.create_table    = restartOpts.value.createTbl

    // 현재 커넥터 정보를 credentials로 전송 (저장된 job credentials 덮어씀)
    const cred = {}
    if (connector.source.status === 'ok') {
      cred.src_host     = connector.source.host
      cred.src_database = connector.source.database
      cred.src_username = connector.source.username
      cred.src_password = connector.source.password
      cred.src_port     = connector.source.port || 3306
    }
    if (connector.target.status === 'ok') {
      cred.tgt_host     = connector.target.host
      cred.tgt_database = connector.target.database
      cred.tgt_username = connector.target.username
      cred.tgt_password = connector.target.password
      cred.tgt_port     = connector.target.port || 1433
    }
    const res = await import('axios').then(m =>
      m.default.post(`/api/v1/jobs/${j.id}/restart`, cred)
    )

    // 스토어 상태 즉시 업데이트
    const storeJob = jobs.jobs.find(jj => jj.id === j.id)
    if (storeJob) {
      storeJob.status          = 'running'
      storeJob.progress        = 0
      storeJob.rows_processed  = 0
      storeJob.rows_error      = 0
      storeJob.speed           = 0
      storeJob.table_done      = 0
      storeJob.current_table   = ''
      storeJob.error_message   = null
    }

    // 새 Job을 store에 추가하고 즉시 fetch
    const newJob = res.data
    jobs.jobs.unshift(newJob)
    await jobs.fetch()   // 전체 목록 갱신

    app.notify(`"${newJob.name}" 재실행 시작! 모니터로 이동합니다`, 'success')
    restartTarget.value = null

    // 실시간 모니터로 자동 이동
    setTimeout(() => router.push('/monitor'), 300)

  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '재실행 실패'
    app.notify('재실행 실패: ' + msg, 'error')
  } finally {
    restarting.value = false
  }
}
</script>

<style scoped>
/* 필터 */
.filter-btn{font-size:11px;padding:3px 10px;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:transparent;color:var(--text-secondary);cursor:pointer;font-family:var(--font);transition:all .12s;display:flex;align-items:center;gap:4px}
.filter-btn:hover{background:var(--bg-secondary)}
.filter-btn.active{background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue)}
.f-cnt{font-size:10px;background:var(--bg-tertiary);color:var(--text-tertiary);padding:0 5px;border-radius:8px}
.filter-btn.active .f-cnt{background:var(--accent-blue);color:#fff}

/* 테이블 — v95_p16_ui (2026-05-03): 본부장님 컴팩트화 처방 — 엔터프라이즈 룩 */
/* 기존: padding:9px 10px / 12px → 행 높이 약 50px (정보 밀도 낮음) */
/* 처방: padding:5px 8px / 11.5px → 행 높이 약 35px (30% 감소, 한 화면 ~16개) */
.job-tbl{width:100%;border-collapse:collapse}
.job-tbl th{background:var(--bg-secondary);font-size:10.5px;font-weight:500;color:var(--text-tertiary);padding:6px 8px;text-align:left;border-bottom:0.5px solid var(--border-light);white-space:nowrap;letter-spacing:0.2px}
.job-tbl td{padding:5px 8px;font-size:11.5px;border-bottom:0.5px solid var(--border-light);color:var(--text-primary);vertical-align:middle;line-height:1.4}
.job-tbl tr:last-child td{border-bottom:none}
.job-tbl tr.row-err td{background:rgba(163,45,45,.04)}
.job-tbl tr.row-run td{background:rgba(55,138,221,.03)}
.job-tbl tr:hover td{filter:brightness(.97)}
.job-name-cell{font-weight:500;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mini-ico{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:4px;font-size:8px;font-weight:700;flex-shrink:0}
.tbl-tag{background:var(--bg-info);color:var(--text-info);padding:1px 6px;border-radius:3px;font-family:'Consolas','SF Mono',monospace;font-size:10.5px;font-weight:500}

/* v9 #64: CDC Job 그룹화 UI */
.row-cdc-group td{background:rgba(37,99,235,.035)}
.row-cdc-group:hover td{background:rgba(37,99,235,.075)}
.row-cdc-child td{background:var(--bg-secondary) !important;opacity:.9}
.row-cdc-child td:first-child{border-left:2px solid rgba(37,99,235,.4)}
.row-cdc-child:hover td{opacity:1}
.job-name-child{font-weight:400;color:var(--text-secondary)}
.child-prefix{color:#2563eb;font-weight:600;margin-right:4px}

.cdc-grp-btn{
  display:inline-flex;align-items:center;gap:3px;
  background:linear-gradient(135deg,#3b82f6,#2563eb);color:#fff;
  border:none;border-radius:9px;padding:2px 7px 2px 5px;
  font-size:10.5px;font-weight:700;cursor:pointer;
  margin-right:6px;vertical-align:middle;
  box-shadow:0 1px 2px rgba(37,99,235,.28);
  transition:all .15s;font-variant-numeric:tabular-nums;
}
.cdc-grp-btn:hover{
  background:linear-gradient(135deg,#2563eb,#1d4ed8);
  transform:translateY(-1px);
  box-shadow:0 2px 5px rgba(37,99,235,.4);
}
.cdc-grp-btn svg{width:9px;height:9px;transition:transform .2s}
.cdc-grp-btn.open svg{transform:rotate(90deg)}
.cdc-grp-cnt{font-size:10.5px;font-weight:700}

/* 버튼 그룹 — v95_p16_ui: 컴팩트화 (10.5px 7px → 9.5px 5px) */
.btn-group{display:flex;gap:2px;flex-wrap:wrap}
.jb{font-size:9.5px;padding:2px 5px;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:transparent;color:var(--text-secondary);cursor:pointer;font-family:var(--font);transition:all .12s;white-space:nowrap;line-height:1.2}
.jb:hover{background:var(--bg-secondary);color:var(--text-primary)}
.jb.primary{border-color:var(--accent-blue);color:var(--text-info);background:var(--bg-info)}
.jb.primary:hover{background:var(--accent-blue);color:#fff}
.jb.ok{border-color:var(--accent-green);color:var(--text-success);background:var(--bg-success)}
.jb.ok:hover{background:var(--accent-green);color:#fff}
.jb.warn{border-color:#ef9f27;color:var(--text-warning);background:var(--bg-warning)}
.jb.danger{border-color:#f09595;color:var(--text-danger)}
.jb.danger:hover{background:var(--bg-danger)}

/* 로그 모달 */
.log-summary{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-bottom:10px}
.ls-item{display:flex;align-items:baseline;gap:6px;padding:4px 8px;background:var(--bg-secondary);border-radius:var(--radius-sm);font-size:11.5px}
.ls-l{color:var(--text-tertiary);font-size:10.5px;min-width:60px;flex-shrink:0}
.ls-v{color:var(--text-primary);font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.log-box{background:var(--bg-secondary);border-radius:var(--radius-md);padding:10px 12px;max-height:300px;overflow-y:auto;font-family:'Consolas','SF Mono',monospace}
.log-line{display:flex;gap:8px;font-size:11.5px;padding:2px 0;line-height:1.6;color:var(--text-secondary)}
.log-t{color:var(--text-tertiary);flex-shrink:0}
.log-tag{color:var(--text-info);flex-shrink:0;min-width:90px}
.log-warn{color:var(--text-warning)}.log-error{color:var(--text-danger)}

/* 재실행 모달 */
.restart-info{background:var(--bg-secondary);border-radius:var(--radius-md);padding:10px 12px;margin-bottom:12px}
.ri-row{display:flex;align-items:center;gap:10px;padding:5px 0;border-bottom:0.5px solid var(--border-light);font-size:12px}
.ri-row:last-child{border-bottom:none;padding-bottom:0}
.ri-l{color:var(--text-tertiary);font-size:11px;min-width:70px;flex-shrink:0}
.ri-v{color:var(--text-primary);font-weight:500}
.restart-opts{display:flex;flex-direction:column;gap:8px;padding:10px 0}
.opt-chk{display:flex;align-items:center;gap:7px;font-size:12px;color:var(--text-secondary);cursor:pointer}
.opt-chk input{accent-color:var(--accent-blue)}

/* ── 체크박스 아이콘 ── */
.th-chk,.td-chk{width:36px;min-width:36px;max-width:36px;padding:0;text-align:center;vertical-align:middle}
.th-chk{cursor:pointer}
.chk-wrap{display:flex;align-items:center;justify-content:center;width:36px;height:36px}
.chk-icon{display:flex;align-items:center;justify-content:center;
          width:16px;height:16px;border-radius:3px;
          border:1.5px solid var(--border-mid);background:var(--bg-secondary);
          color:transparent;transition:all .12s;cursor:pointer;flex-shrink:0}
.chk-icon svg{width:12px;height:12px;display:block;flex-shrink:0}
.chk-icon:hover{border-color:var(--accent-blue)}
.chk-icon.checked{border-color:var(--accent-blue);background:var(--accent-blue);color:#fff}
.chk-icon.partial{border-color:var(--accent-blue);background:var(--bg-info);color:var(--accent-blue)}
.row-sel td{background:rgba(59,130,246,.07)!important}
.job-tbl tr.row-sel:hover td{background:rgba(59,130,246,.12)!important}

/* ── 정렬 헤더 ── */
.th-sort{cursor:pointer;user-select:none;white-space:nowrap}
.th-sort:hover{color:var(--text-primary);background:var(--bg-primary)}
.th-sort.sort-active{color:var(--accent-blue)!important;background:rgba(59,130,246,.06)}
.sort-ico{display:inline-flex;align-items:center;margin-left:3px;opacity:.4;vertical-align:middle}
.sort-ico.active{opacity:1}

/* ── 시간 컬럼 ── */
.time-cell{font-size:11px;color:var(--text-tertiary);white-space:nowrap;min-width:90px}
.dur{font-weight:600;color:var(--text-secondary)}
.dur_running{color:var(--text-info)}

/* ── 일괄 삭제 버튼 ── */
.act-btn{display:inline-flex;align-items:center;gap:4px;font-size:11.5px;padding:4px 9px;
         border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);
         background:var(--bg-secondary);color:var(--text-secondary);cursor:pointer;
         font-family:var(--font);transition:all .12s}
.act-btn:hover{background:var(--bg-primary);color:var(--text-primary)}
.act-btn.danger{border-color:#f09595;color:var(--text-danger)}
.act-btn.danger:hover{background:var(--bg-danger)}
</style>
