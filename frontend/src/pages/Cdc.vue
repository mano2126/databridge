<template>
  <div class="cdc-wrap">

    <!-- DB 접속 패널 -->
    <ConnectPanel v-if="!connector.bothConnected" @connected="onConnected"/>
    <PageHeader   v-else :show-db="true" :src-db="connector.source" :tgt-db="connector.target"/>

    <!-- 페이지 헤더 -->
    <div class="wiz-topbar">
      <div class="wiz-topbar-left">
        <div class="wiz-title">증가분 처리</div>
        <div class="wiz-subtitle">소스의 변경된 데이터만 타겟에 반영합니다. timestamp 기반 증분 동기화 또는 DB 로그 기반 CDC 를 선택하세요.</div>
      </div>
      <button v-if="!modeInfoOpen" class="btn btn-outline" style="font-size:11px"
              @click="modeInfoOpen = true">동기화 모드 비교 보기</button>
    </div>

    <!-- 동기화 모드 비교 배너 -->
    <div v-if="modeInfoOpen" class="mode-banner">
      <div class="mode-banner-header">
        <strong>동기화 모드 비교</strong>
        <button class="btn-icon-close" @click="modeInfoOpen = false">✕</button>
      </div>
      <div class="mode-grid">
        <div v-for="m in syncModes" :key="m.key" class="mode-card" :class="{ available: isModeAvailable(m.key) }">
          <div class="mode-name">{{ m.display_name }}</div>
          <div class="mode-latency">지연: {{ m.latency }}</div>
          <div class="mode-desc">{{ m.description }}</div>
          <div class="mode-dbs">지원 DB: {{ m.supported_dbs.join(', ') }}</div>
          <div v-if="m.limitations" class="mode-limits">⚠ {{ m.limitations.substring(0, 80) }}...</div>
        </div>
      </div>
      <div class="mode-banner-note">
        <strong>📌 용어 정리:</strong>
        "CDC"라는 용어는 전통적으로 DB 트랜잭션 로그(binlog/WAL) 기반을 뜻합니다.
        본 시스템의 "증분 동기화(incremental)"는 실제로는 <code>updated_at</code> 컬럼 폴링 방식으로,
        물리 DELETE 감지 등에 한계가 있습니다. 삭제 추적이 필수라면 진짜 CDC 모드(binlog_cdc / pg_cdc / mssql_cdc)를 사용하세요.
      </div>
    </div>

    <!-- ══ 설정 없음 ══ -->
    <div v-if="!configs.length && editingId!=='__new__'" class="cdc-empty">
      <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.2"
           style="width:48px;height:48px;opacity:.25">
        <circle cx="24" cy="24" r="20"/>
        <path d="M16 24h16M24 16l8 8-8 8"/>
      </svg>
      <div style="margin-top:10px;font-size:.85rem;color:var(--text-tertiary)">저장된 CDC 설정이 없습니다</div>
      <button class="btn btn-primary" style="margin-top:14px" @click="startNew">+ 첫 번째 CDC 설정 만들기</button>
    </div>

    <!-- ══ 목록 ══ -->
    <div v-else class="cdc-list-wrap">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
        <span style="font-size:.82rem;font-weight:600;color:var(--text-secondary)">
          저장된 설정 {{ configs.length }}개
        </span>
        <button class="btn btn-primary btn-sm" @click="startNew">
          <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" style="width:10px;height:10px">
            <line x1="6" y1="1" x2="6" y2="11"/><line x1="1" y1="6" x2="11" y2="6"/>
          </svg>
          새 설정
        </button>
      </div>

      <div class="cdc-cards">

        <!-- 기존 설정 카드 (v9 #58: __new__ 같은 잘못된 ID 는 목록에서 제외) -->
        <div v-for="cfg in configs.filter(c => c.id && c.id !== '__new__')" :key="cfg.id" class="card cdc-cfg-card"
             :class="{'cdc-running': !!runningMap[cfg.id], 'cdc-expanded': expandedCfg===cfg.id, 'cdc-editing': editingId===cfg.id}">

          <!-- 카드 헤더 -->
          <div class="cdc-cfg-top"
               @click="editingId!==cfg.id && (expandedCfg = expandedCfg===cfg.id ? null : cfg.id)"
               :style="editingId!==cfg.id ? 'cursor:pointer' : 'cursor:default'">
            <div class="cdc-cfg-name">
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8"
                   style="width:11px;height:11px;color:var(--text-tertiary);flex-shrink:0;transition:transform .18s"
                   :style="(expandedCfg===cfg.id||editingId===cfg.id) ? 'transform:rotate(180deg)' : ''">
                <polyline points="2,4 6,8 10,4"/>
              </svg>
              <span class="cfg-title">{{ cfg.name || '이름 없음' }}</span>
              <span v-if="runningMap[cfg.id]" class="run-badge">
                <span class="run-dot"></span>실행 중
              </span>
              <span v-if="editingId===cfg.id" class="edit-badge">편집 중</span>
            </div>
            <div class="cdc-cfg-btns" @click.stop>
              <span class="db-pill src" style="font-size:.62rem">{{ cfg.src_conn?.db_type?.toUpperCase() }}</span>
              <span class="conn-host-sm">{{ cfg.src_conn?.database }}</span>
              <svg viewBox="0 0 14 6" fill="none" stroke="currentColor" stroke-width="1.2"
                   style="width:14px;height:6px;opacity:.4;flex-shrink:0">
                <line x1="0" y1="3" x2="10" y2="3"/><polyline points="7,1 10,3 7,5"/>
              </svg>
              <span class="db-pill tgt" style="font-size:.62rem">{{ cfg.tgt_conn?.db_type?.toUpperCase() }}</span>
              <span class="conn-host-sm">{{ cfg.tgt_conn?.database }}</span>
              <span class="tbl-count-badge">테이블 {{ (cfg.tables||[]).length }}개</span>
              <div style="width:1px;height:16px;background:var(--border-light);margin:0 4px"></div>
              <!-- 편집 중: 취소 버튼 -->
              <template v-if="editingId===cfg.id">
                <button class="icon-btn" @click.stop.prevent="cancelEdit()" title="편집 취소">
                  <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px">
                    <line x1="2" y1="2" x2="12" y2="12"/>
                    <line x1="12" y1="2" x2="2" y2="12"/>
                  </svg>
                </button>
              </template>
              <!-- 편집 중 아님: 편집 + 삭제 버튼 -->
              <template v-else>
                <button class="cdc-txt-btn edit-btn" @click.stop.prevent="editCfg(cfg)">
                  <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px;flex-shrink:0">
                    <path d="M9.5 2.5l2 2-7 7H2.5v-2l7-7z"/>
                  </svg>
                  편집
                </button>
                <button class="cdc-txt-btn del-btn" @click.stop.prevent="deleteCfg(cfg.id)">
                  <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px;flex-shrink:0">
                    <polyline points="2,3.5 12,3.5"/>
                    <path d="M5,3.5V2H9v1.5"/>
                    <path d="M3.5,3.5l1,8.5h5l1-8.5"/>
                  </svg>
                  삭제
                </button>
              </template>
              <template v-if="editingId!==cfg.id">
                <!-- 스케줄 등록 버튼 -->
                <button class="cdc-act-btn sch-btn" @click.stop.prevent="openSchedule(cfg)"
                        :class="{active: scheduleMap[cfg.id]}"
                        :title="scheduleMap[cfg.id] ? '스케줄 활성 — 클릭하여 수정' : '스케줄 등록'">
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:13px;height:13px;flex-shrink:0">
                    <rect x="1" y="2" width="14" height="13" rx="1.5"/>
                    <line x1="1" y1="6" x2="15" y2="6" stroke-width="1.2"/>
                    <line x1="5" y1="1" x2="5" y2="4" stroke-width="1.8" stroke-linecap="round"/>
                    <line x1="11" y1="1" x2="11" y2="4" stroke-width="1.8" stroke-linecap="round"/>
                    <circle v-if="scheduleMap[cfg.id]" cx="11" cy="11" r="3" fill="currentColor" opacity=".25"/>
                    <polyline points="9.5,9.5 11,11 13,9" stroke-width="1.4" stroke-linecap="round" v-if="scheduleMap[cfg.id]"/>
                  </svg>
                  <span>{{ scheduleMap[cfg.id] ? '스케줄' : '스케줄' }}</span>
                  <span v-if="scheduleMap[cfg.id]" class="sch-dot"/>
                </button>
                <!-- 즉시 실행 버튼 -->
                <button class="cdc-act-btn run-btn"
                        @click="runCfg(cfg)" :disabled="!!runningMap[cfg.id]">
                  <span v-if="runningMap[cfg.id]" class="mini-spin" style="width:11px;height:11px;border-color:rgba(255,255,255,.3);border-top-color:#fff"/>
                  <svg v-else viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:13px;height:13px;flex-shrink:0">
                    <circle cx="7" cy="7" r="6"/>
                    <polygon points="5.5,4.5 10.5,7 5.5,9.5" fill="currentColor" stroke="none"/>
                  </svg>
                  <span>{{ runningMap[cfg.id] ? '실행중' : '즉시실행' }}</span>
                </button>
              </template>
            </div>
          </div>

          <!-- 스케줄 등록 패널 (JobWizard 스타일) -->
          <div v-if="scheduleOpenId===cfg.id" class="cdc-schedule-panel" @click.stop>
            <div class="sch-panel-hdr">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px">
                <rect x="1" y="2" width="14" height="13" rx="1"/><line x1="1" y1="6" x2="15" y2="6"/>
                <line x1="5" y1="1" x2="5" y2="4"/><line x1="11" y1="1" x2="11" y2="4"/>
              </svg>
              <span>실행 스케줄 — {{ cfg.name }}</span>
              <div style="margin-left:auto;display:flex;align-items:center;gap:6px">
                <span v-if="scheduleMap[cfg.id]" class="sch-active-badge">
                  활성 · 다음: {{ fmtShort(scheduleMap[cfg.id]?.next_run) }}
                </span>
                <button v-if="scheduleMap[cfg.id]" class="btn-sch-del"
                        @click.stop="deleteSchedule(cfg.id)">스케줄 삭제</button>
                <button class="icon-btn" @click.stop="scheduleOpenId=null">
                  <svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.8" style="width:9px;height:9px">
                    <line x1="1" y1="1" x2="9" y2="9"/><line x1="9" y1="1" x2="1" y2="9"/>
                  </svg>
                </button>
              </div>
            </div>
            <div class="sch-panel-body">

              <!-- 실행 방식 선택 카드 (JobWizard 동일) -->
              <div class="sched-mode-row">
                <div class="sched-mode-card" :class="{active: schForm[cfg.id]?.mode==='now'}"
                     @click.stop="setSchMode(cfg.id,'now')">
                  <div class="smc-ico">
                    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" style="width:22px;height:22px">
                      <circle cx="10" cy="10" r="8"/>
                      <polygon points="8,6.5 15,10 8,13.5" fill="currentColor" stroke="none"/>
                    </svg>
                  </div>
                  <div class="smc-body">
                    <div class="smc-title">즉시 실행</div>
                    <div class="smc-desc">지금 바로 변경분 이관 시작</div>
                  </div>
                  <div class="smc-radio" :class="{on: schForm[cfg.id]?.mode==='now'}"/>
                </div>
                <div class="sched-mode-card" :class="{active: schForm[cfg.id]?.mode==='schedule'}"
                     @click.stop="setSchMode(cfg.id,'schedule')">
                  <div class="smc-ico">
                    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" style="width:22px;height:22px">
                      <rect x="2" y="3" width="16" height="15" rx="2"/>
                      <line x1="2" y1="8" x2="18" y2="8" stroke-width="1.4"/>
                      <line x1="6" y1="1.5" x2="6" y2="5" stroke-width="1.8" stroke-linecap="round"/>
                      <line x1="14" y1="1.5" x2="14" y2="5" stroke-width="1.8" stroke-linecap="round"/>
                      <circle cx="10" cy="13" r="2.2" fill="currentColor" opacity=".2"/>
                      <circle cx="10" cy="13" r="2.2"/>
                    </svg>
                  </div>
                  <div class="smc-body">
                    <div class="smc-title">스케줄 등록</div>
                    <div class="smc-desc">지정한 주기·시간에 자동 실행</div>
                  </div>
                  <div class="smc-radio" :class="{on: schForm[cfg.id]?.mode==='schedule'}"/>
                </div>
              </div>

              <!-- 스케줄 설정 (mode=schedule) -->
              <template v-if="schForm[cfg.id]?.mode==='schedule'">
                <div class="sched-type-row">
                  <button v-for="t in schTypes" :key="t.key"
                          class="stype-btn" :class="{active: schForm[cfg.id]?.type===t.key}"
                          @click.stop="setSchType(cfg.id, t.key)">{{ t.label }}</button>
                </div>

                <!-- 반복 실행 -->
                <div v-if="schForm[cfg.id]?.type==='repeat'" class="sched-fields">
                  <div class="sf-row">
                    <div class="sf-group">
                      <div class="field-label">반복 주기</div>
                      <div class="sel-wrap">
                        <select v-model="schForm[cfg.id].interval">
                          <option value="every_n">N분마다</option>
                          <option value="hourly">매시간</option>
                          <option value="daily">매일</option>
                          <option value="weekly">매주</option>
                          <option value="monthly">매월</option>
                        </select>
                        <div class="chev"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>
                      </div>
                    </div>
                    <!-- N분마다: 직접 입력 -->
                    <div v-if="schForm[cfg.id]?.interval==='every_n'" class="sf-group">
                      <div class="field-label">반복 간격</div>
                      <div style="display:flex;align-items:center;gap:6px">
                        <input v-model.number="schForm[cfg.id].every_n_min" type="number"
                               min="1" max="1440" class="sch-n-input"
                               placeholder="10"/>
                        <span style="font-size:12px;color:var(--text-tertiary)">분마다</span>
                      </div>
                      <div style="font-size:11px;color:var(--text-tertiary);margin-top:3px">
                        예: 10 = 10분마다 / 30 = 30분마다
                      </div>
                    </div>
                    <!-- 매시간: 몇 분에 실행 -->
                    <div v-if="schForm[cfg.id]?.interval==='hourly'" class="sf-group">
                      <div class="field-label">실행 분</div>
                      <div class="sel-wrap">
                        <select v-model="schForm[cfg.id].minute">
                          <option value="0">0분 (정각)</option>
                          <option value="5">5분</option>
                          <option value="10">10분</option>
                          <option value="15">15분</option>
                          <option value="20">20분</option>
                          <option value="30">30분</option>
                          <option value="45">45분</option>
                        </select>
                        <div class="chev"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>
                      </div>
                    </div>
                    <!-- 매일/매주/매월: 실행 시간 -->
                    <div v-if="!['hourly','every_n'].includes(schForm[cfg.id]?.interval)" class="sf-group">
                      <div class="field-label">실행 시간</div>
                      <input type="time" v-model="schForm[cfg.id].time"/>
                    </div>
                  </div>
                  <div class="sched-preview" v-if="schPreview(cfg.id)">
                    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><circle cx="8" cy="8" r="7"/><polyline points="8,4 8,8 11,10"/></svg>
                    {{ schPreview(cfg.id) }}
                  </div>
                </div>

                <!-- Cron 직접 입력 -->
                <div v-if="schForm[cfg.id]?.type==='cron'" class="sched-fields">
                  <div class="sf-row">
                    <div class="sf-group" style="flex:1">
                      <div class="field-label">Cron 표현식</div>
                      <input type="text" v-model="schForm[cfg.id].cron_expr"
                             placeholder="예) 0 2 * * * (매일 새벽 2시)"
                             style="font-family:var(--font-mono,monospace)"/>
                    </div>
                  </div>
                  <div class="cron-help">
                    <span v-for="ex in cronExamples" :key="ex.v"
                          class="cron-ex" @click.stop="schForm[cfg.id].cron_expr=ex.v">{{ ex.label }}</span>
                  </div>
                </div>

                <!-- 1회 실행 -->
                <div v-if="schForm[cfg.id]?.type==='once'" class="sched-fields">
                  <div class="sf-row">
                    <div class="sf-group" style="min-width:200px">
                      <div class="field-label">실행 일시</div>
                      <div class="dt-input-wrap">
                        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"
                             style="width:13px;height:13px;flex-shrink:0;color:var(--text-tertiary)">
                          <rect x="1" y="2" width="14" height="13" rx="1.5"/>
                          <line x1="1" y1="6" x2="15" y2="6" stroke-width="1.1"/>
                          <line x1="5" y1="1" x2="5" y2="4" stroke-width="1.6" stroke-linecap="round"/>
                          <line x1="11" y1="1" x2="11" y2="4" stroke-width="1.6" stroke-linecap="round"/>
                        </svg>
                        <input type="date" v-model="schForm[cfg.id].date" class="dt-part-input"/>
                        <span style="color:var(--text-tertiary);font-size:12px">|</span>
                        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"
                             style="width:12px;height:12px;flex-shrink:0;color:var(--text-tertiary)">
                          <circle cx="8" cy="8" r="6.5"/>
                          <polyline points="8,4.5 8,8 10.5,10"/>
                        </svg>
                        <input type="time" v-model="schForm[cfg.id].time" class="dt-part-input"/>
                      </div>
                    </div>
                  </div>
                  <div class="sched-preview" v-if="schForm[cfg.id]?.date&&schForm[cfg.id]?.time">
                    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><circle cx="8" cy="8" r="7"/><polyline points="8,4 8,8 11,10"/></svg>
                    {{ schForm[cfg.id].date }} {{ schForm[cfg.id].time }} 에 1회 실행
                  </div>
                </div>
              </template>

              <!-- 액션 버튼 -->
              <div class="sch-actions">
                <button class="btn" @click.stop="scheduleOpenId=null">취소</button>
                <button v-if="schForm[cfg.id]?.mode==='now'"
                        class="btn btn-success" @click.stop="runCfg(cfg); scheduleOpenId=null"
                        :disabled="!!runningMap[cfg.id]">
                  <svg viewBox="0 0 12 12" fill="currentColor" style="width:9px;height:9px;margin-right:3px">
                    <polygon points="2,1 10,6 2,11"/>
                  </svg>
                  즉시 실행
                </button>
                <button v-if="schForm[cfg.id]?.mode==='schedule'"
                        class="btn btn-primary" @click.stop="saveSchedule(cfg)"
                        :disabled="schSaving">
                  <span v-if="schSaving" class="mini-spin"></span>
                  {{ scheduleMap[cfg.id] ? '스케줄 수정' : '스케줄 등록' }}
                </button>
              </div>
            </div>
          </div>

          <!-- 인라인 편집 패널 -->
          <div v-if="editingId===cfg.id" class="cfg-inline-edit">
            <div class="inline-wiz-hdr">
              <div class="inline-wiz-steps">
                <template v-for="(st, i) in steps" :key="i">
                  <button class="iwiz-step" :class="{active:cur===i,done:cur>i,reachable:cur>=i}" @click="goStep(i)">
                    <span class="iwiz-num">
                      <svg v-if="cur>i" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="1,5 4,8 9,2"/>
                      </svg>
                      <span v-else>{{ i+1 }}</span>
                    </span>
                    <span class="iwiz-lbl">{{ st }}</span>
                  </button>
                  <span v-if="i<steps.length-1" class="iwiz-line" :class="{done:cur>i}"/>
                </template>
              </div>
            </div>
            <!-- Step 0 -->
            <div v-if="cur===0" class="iwiz-body">
              <div class="opts-grid-2">
                <div>
                  <div class="field-label">설정 이름 *</div>
                  <input v-model="form.name" class="field-input" placeholder="소스 → 타겟 변경분 이관"/>
                  <div class="field-label" style="margin-top:14px">배치 크기 (건)</div>
                  <input v-model.number="form.batch_size" type="number" min="100" max="50000"
                         class="field-input" style="max-width:160px"/>
                  <div class="field-desc">한 번에 처리할 최대 행 수 (기본 5,000)</div>
                </div>
                <div class="strat-guide">
                  <div class="strat-guide-title">이관 전략 안내</div>
                  <div class="strat-row"><span class="strat-badge append">Append</span><span class="strat-desc">INSERT만 — 이력 테이블</span></div>
                  <div class="strat-row"><span class="strat-badge upsert">UPSERT</span><span class="strat-desc">있으면 UPDATE, 없으면 INSERT</span></div>
                  <div class="strat-row"><span class="strat-badge full">Full</span><span class="strat-desc">전체 삭제 후 재입력</span></div>
                </div>
              </div>
            </div>
            <!-- Step 1 -->
            <div v-if="cur===1" class="iwiz-body iwiz-tbl">
              <div class="tbl-toolbar">
                <!-- 1행: 검색 + 상태탭 | 조건필터 + 자동감지 + 다운로드 -->
                <div class="tbl-toolbar-row">
                  <!-- 왼쪽: 검색 + 상태탭 -->
                  <input v-model="tblSearch" class="tbl-search" placeholder="테이블명 검색..." @input="tblPage=1"/>
                  <div class="filter-tabs">
                    <button v-for="f in filterTabs" :key="f.key" class="ftab"
                            :class="{active:tblFilter===f.key}" @click="tblFilter=f.key;tblPage=1">
                      {{ f.label }} <span class="ftab-cnt">{{ scanCounts[f.key]||0 }}</span>
                    </button>
                  </div>
                  <!-- 오른쪽: 조건 필터 + 자동감지 + 다운로드 -->
                  <div class="tbl-toolbar-right">
                    <span class="tbl-result-info">
                      <b>{{ totalFiltered }}</b> / {{ scanRows.length }}개
                    </span>
                    <div class="group-filter-wrap">
                      <span class="group-filter-label">조건 필터</span>
                      <select v-model="tblGroupFilter" class="group-filter-sel" @change="tblPage=1">
                        <option value="all">전체</option>
                        <optgroup label="기준 컬럼">
                          <option value="has_ts">기준 컬럼 있음</option>
                          <option value="no_ts">기준 컬럼 없음</option>
                        </optgroup>
                        <optgroup label="기준일자">
                          <option value="has_date">기준일자 설정됨</option>
                        </optgroup>
                        <optgroup label="PK">
                          <option value="no_pk">PK 없음</option>
                        </optgroup>
                        <optgroup label="전략">
                          <option value="append">Append 만</option>
                          <option value="upsert">UPSERT 만</option>
                          <option value="full">Full 만</option>
                        </optgroup>
                      </select>
                    </div>
                    <button class="btn btn-sm" @click="scanAll" :disabled="scanning">
                      <span v-if="scanning" class="mini-spin" style="width:11px;height:11px;border-color:rgba(0,0,0,.15);border-top-color:var(--text-secondary)"/>
                      <svg v-else viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:11px;height:11px">
                        <circle cx="6" cy="6" r="5"/><path d="M4 6l1.5 1.5L8 4"/>
                      </svg>
                      전체 자동감지
                    </button>
                    <button class="btn btn-sm" @click="downloadTestSql" :disabled="!scanRows.length || dlLoading"
                            title="기준컬럼 있는 테이블 최대 5개의 INSERT/DELETE/SELECT 쿼리를 SQL 파일로 다운로드">
                      <span v-if="dlLoading" class="mini-spin" style="width:11px;height:11px"/>
                      <svg v-else viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:11px;height:11px">
                        <path d="M6 1v7M3 6l3 3 3-3"/><line x1="1" y1="11" x2="11" y2="11"/>
                      </svg>
                      테스트 SQL
                    </button>
                  </div>
                </div>
              </div>
              <div v-if="scanning && !scanRows.length" class="scan-loading">
                <div class="scan-spin"></div><span>소스 DB 분석 중...</span>
              </div>
              <div v-else-if="!scanRows.length && !scanning" class="scan-empty">
                <div style="font-size:.82rem;color:var(--text-tertiary);margin-bottom:10px">
                  전체 자동감지를 실행하면 소스 DB 테이블이 표시됩니다.
                </div>
                <button class="btn btn-primary btn-sm" @click="scanAll">자동감지 시작</button>
              </div>
              <div v-else class="tbl-grid">
                <div class="tbl-grid-hdr">
                  <div class="tg-chk">
                    <input type="checkbox" @change="toggleAllCheck($event)" :checked="allChecked"
                           style="width:13px;height:13px;accent-color:#2563eb"/>
                  </div>
                  <div class="tg-no">#</div>
                  <div class="tg-name tg-sortable" @click="toggleSort('table')">
                    테이블명 <span class="sort-icon">{{ sortIcon('table') }}</span>
                  </div>
                  <div class="tg-cnt tg-sortable" @click="toggleSort('row_count')">
                    건수 <span class="sort-icon">{{ sortIcon('row_count') }}</span>
                  </div>
                  <div class="tg-ts">기준 컬럼 / 기준일자</div>
                  <div class="tg-where">추가 WHERE 조건</div>
                  <div class="tg-strat tg-sortable" @click="toggleSort('strategy')">
                    전략 <span class="sort-icon">{{ sortIcon('strategy') }}</span>
                  </div>
                  <div class="tg-sync tg-sortable" @click="toggleSort('base_date')">
                    동기화 <span class="sort-icon">{{ sortIcon('base_date') }}</span>
                  </div>
                  <div class="tg-chevron"></div>
                </div>
                <template v-for="(row, rowIdx) in pagedRows" :key="row.table">
                  <div class="tbl-grid-row"
                       :class="{'row-expanded':expandedRow===row.table,'row-excluded':row.excluded,'row-saved':row.is_saved}"
                       @click="toggleExpand(row.table)">
                    <div class="tg-chk" @click.stop>
                      <input type="checkbox" :checked="!row.excluded"
                             @change="toggleExclude(row,$event)"
                             style="width:13px;height:13px;accent-color:#2563eb"/>
                    </div>
                    <div class="tg-no">{{ (tblPage-1)*tblPageSize + rowIdx + 1 }}</div>
                    <div class="tg-name">
                      <span class="row-tbl-name" :class="{'excluded-name':row.excluded}">{{ row.table }}</span>
                      <span v-if="!row.pk_cols?.length" class="no-pk-badge">PK없음</span>
                      <span v-if="row.is_saved" class="saved-badge">저장됨</span>
                    </div>
                    <div class="tg-cnt">
                      <span v-if="row.row_count!=null" class="cnt-text">{{ row.row_count.toLocaleString() }}</span>
                      <span v-else class="cnt-loading">—</span>
                    </div>
                    <div class="tg-ts">
                      <template v-if="row.ts_col">
                        <span class="ts-pill" :class="row.is_saved?'user':'auto'">
                          {{ row.ts_col }}
                          <span v-if="!row.is_saved&&row.recommended_ts" style="opacity:.6;font-size:.85em"> 추천</span>
                        </span>
                        <span v-if="row.base_date" class="base-date-badge" title="기준일자 고정">
                          ▶ {{ row.base_date }}
                        </span>
                      </template>
                      <span v-else class="ts-pill none">없음 → Full</span>
                    </div>
                    <div class="tg-where">
                      <span v-if="row.extra_where" class="where-text">{{ row.extra_where }}</span>
                      <span v-else style="color:var(--text-tertiary);font-size:.72rem">—</span>
                    </div>
                    <div class="tg-strat" @click.stop>
                      <select v-model="row.strategy" class="strat-sel-inline" :class="row.strategy">
                        <option value="append">Append</option>
                        <option value="upsert">UPSERT</option>
                        <option value="full">Full</option>
                      </select>
                    </div>
                    <div class="tg-sync">
                      <span class="sync-ts-text">{{ fmtShort(savedState[row.table]?.last_sync) }}</span>
                      <button v-if="savedState[row.table]?.last_sync"
                              class="reset-btn" @click.stop="resetOneSync(row.table)" title="초기화">↺</button>
                    </div>
                    <div class="tg-chevron" :class="{open:expandedRow===row.table}">
                      <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:11px;height:11px">
                        <polyline points="3,4 6,7 9,4"/>
                      </svg>
                    </div>
                  </div>
                  <!-- 행 펼침 패널 -->
                  <div v-if="expandedRow===row.table" class="expand-panel" @click.stop>
                    <div v-if="row.excluded" class="exp-excluded">
                      <span>제외된 테이블입니다. 체크박스를 선택하면 포함됩니다.</span>
                    </div>
                    <template v-else>
                      <div class="exp-field" style="min-width:220px;max-width:240px;position:relative">
                        <div class="exp-label">기준 컬럼
                          <span v-if="row.recommended_ts&&!row.is_saved" class="auto-tag">자동감지</span>
                        </div>
                        <div style="display:flex;align-items:center;gap:6px">
                          <div class="col-picker-wrap" @click.stop>
                            <input v-model="row.ts_col" class="exp-input mono"
                                   placeholder="클릭하여 컬럼 선택..."
                                   @click.stop="openColPicker(row)" @change="onTsColChange(row)" readonly/>
                            <button class="col-picker-clear" v-if="row.ts_col"
                                    @click="row.ts_col='';onTsColChange(row)" title="컬럼 초기화">
                              <svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.8" style="width:9px;height:9px"><line x1="2" y1="2" x2="8" y2="8"/><line x1="8" y1="2" x2="2" y2="8"/></svg>
                            </button>
                          </div>
                          <span v-if="row.ts_col" class="gt-sign" title="기준 컬럼 > 기준일자 조건으로 조회">&gt;</span>
                        </div>
                        <div v-if="colPickerRow===row.table" class="col-dropdown" @click.stop>
                          <input v-model="colSearch" class="col-search" placeholder="컬럼명 검색..." @click.stop autofocus/>
                          <div class="col-dropdown-list">
                            <div v-for="col in filteredAllCols(row)" :key="col.name"
                                 class="col-option"
                                 :class="{active:row.ts_col===col.name,recommended:row.ts_candidates?.includes(col.name)}"
                                 @click.stop="selectCol(row,col.name)">
                              <span class="col-opt-name">{{ col.name }}</span>
                              <span class="col-opt-type">{{ col.type }}</span>
                              <span v-if="row.ts_candidates?.includes(col.name)" class="col-opt-rec">추천</span>
                            </div>
                            <div v-if="!filteredAllCols(row).length" class="col-option-empty">검색 결과 없음</div>
                          </div>
                        </div>
                        <div v-if="row.ts_candidates?.length" style="margin-top:6px">
                          <div class="exp-hint">datetime 후보:</div>
                          <div class="cand-btns">
                            <button v-for="c in row.ts_candidates" :key="c"
                                    class="cand-btn" :class="{active:row.ts_col===c}"
                                    @click="row.ts_col=c;onTsColChange(row);colPickerRow=null">{{ c }}</button>
                          </div>
                        </div>
                        <div v-else-if="!row.ts_col" class="exp-hint warn">datetime 컬럼 없음 — Full 권장</div>
                      </div>
                      <div class="exp-field" style="min-width:180px;max-width:200px">
                        <div class="exp-label">기준일자</div>
                        <input v-model="row.base_date" class="exp-input mono" placeholder="YYYY-MM-DD HH:MM:SS"/>
                        <div class="exp-hint">비우면 last_sync 자동 사용</div>
                      </div>
                      <div class="exp-field" style="flex:1">
                        <div class="exp-label">추가 WHERE <span style="opacity:.6">(선택)</span></div>
                        <input v-model="row.extra_where" class="exp-input mono"
                               placeholder="예) use_yn = 'Y'"
                               :disabled="!row.ts_col&&row.strategy==='full'"/>
                        <div class="exp-hint">
                          조건 1개: use_yn = 'Y'<br>
                          2개 이상: use_yn = 'Y' AND code = '01'
                        </div>
                      </div>
                      <div class="exp-field" style="min-width:110px;max-width:130px">
                        <div class="exp-label">전략</div>
                        <select v-model="row.strategy" class="exp-select" :class="row.strategy">
                          <option value="append">Append</option>
                          <option value="upsert" :disabled="!row.pk_cols?.length">
                            UPSERT{{ !row.pk_cols?.length?' (PK없음)':'' }}
                          </option>
                          <option value="full">Full</option>
                        </select>
                        <div v-if="!row.pk_cols?.length" class="exp-hint warn">PK 없음</div>
                      </div>
                      <div class="exp-actions">
                        <button class="btn-row-reset" @click="resetRow(row)">↺ 초기화</button>
                        <button class="btn-row-save" @click="saveRow(row)">저장</button>
                        <button class="btn-row-test" @click.stop="generateTestQuery(row)" title="변경분 테스트 쿼리 생성">
                          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px">
                            <polyline points="1,4 5,4 5,1"/><path d="M5,4 A6,6 0 1,1 1,8"/>
                          </svg>
                          테스트 쿼리
                        </button>
                      </div>
                      <!-- 테스트 쿼리 출력 -->
                      <div v-if="testQueryMap[row.table]" class="test-query-panel">
                        <!-- 탭 헤더 -->
                        <div class="tq-tabs">
                          <button v-for="tab in ['INSERT','DELETE','SELECT']" :key="tab"
                                  class="tq-tab" :class="{active: (tqActiveTab[row.table]||'INSERT')===tab}"
                                  @click.stop="setTqTab(row.table, tab)">
                            {{ tab }}
                          </button>
                          <div style="flex:1"/>
                          <button class="tq-copy" @click.stop="copyTqTab(row.table)">
                            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px">
                              <rect x="4" y="4" width="9" height="9" rx="1"/><path d="M1 9V1h8"/>
                            </svg>
                            {{ copiedTable===row.table ? '복사됨!' : '복사' }}
                          </button>
                          <button class="tq-close" @click.stop="testQueryMap[row.table]=null">✕</button>
                        </div>
                        <!-- 쿼리 본문 -->
                        <pre class="test-query-body">{{ getActiveTqSql(row.table) }}</pre>
                        <!-- 안내 -->
                        <div class="test-query-note">
                          <b>소스 DB({{ form.src_conn?.db_type?.toUpperCase() }})에서 직접 실행하세요.</b>
                          {{ testQueryMap[row.table].note }}
                        </div>
                      </div>
                    </template>
                  </div>
                </template>
                <div v-if="!pagedRows.length" class="tbl-no-result">검색 결과 없음</div>
              </div>
              <!-- 페이징 -->
              <div v-if="totalFiltered>0" class="tbl-paging">
                <div style="display:flex;align-items:center;gap:10px">
                  <div style="display:flex;align-items:center;gap:6px">
                    <span class="page-info-label">페이지당</span>
                    <select v-model="tblPageSize" class="page-size-sel" @change="tblPage=1">
                      <option :value="10">10개</option>
                      <option :value="20">20개</option>
                      <option :value="30">30개</option>
                      <option :value="50">50개</option>
                      <option :value="100">100개</option>
                    </select>
                  </div>
                  <span class="page-info">
                    전체 {{ totalFiltered }}개 중
                    {{ Math.min((tblPage-1)*tblPageSize+1,totalFiltered) }}–{{ Math.min(tblPage*tblPageSize,totalFiltered) }}
                  </span>
                </div>
                <div class="page-btns">
                  <button class="pg-btn" @click="tblPage=1" :disabled="tblPage<=1">«</button>
                  <button class="pg-btn" @click="tblPage--" :disabled="tblPage<=1">‹</button>
                  <template v-for="p in pageNumbers" :key="p">
                    <span v-if="p===-1" class="pg-ellipsis">…</span>
                    <button v-else class="pg-btn" :class="{active:tblPage===p}" @click="tblPage=p">{{ p }}</button>
                  </template>
                  <button class="pg-btn" @click="tblPage++" :disabled="tblPage>=totalPages">›</button>
                  <button class="pg-btn" @click="tblPage=totalPages" :disabled="tblPage>=totalPages">»</button>
                </div>
              </div>
            </div>
            <!-- Step 2 -->
            <div v-if="cur===2" class="iwiz-body">
              <div class="confirm-grid">
                <div class="confirm-block">
                  <div class="confirm-label">설정 이름</div>
                  <div class="confirm-val">{{ form.name }}</div>
                </div>
                <div class="confirm-block">
                  <div class="confirm-label">배치 크기</div>
                  <div class="confirm-val">{{ (form.batch_size||5000).toLocaleString() }}건</div>
                </div>
                <div class="confirm-block">
                  <div class="confirm-label">소스</div>
                  <div class="confirm-val">
                    <span class="db-pill src sm">{{ form.src_conn?.db_type?.toUpperCase() }}</span>
                    {{ form.src_conn?.host }}/{{ form.src_conn?.database }}
                  </div>
                </div>
                <div class="confirm-block">
                  <div class="confirm-label">타겟</div>
                  <div class="confirm-val">
                    <span class="db-pill tgt sm">{{ form.tgt_conn?.db_type?.toUpperCase() }}</span>
                    {{ form.tgt_conn?.host }}/{{ form.tgt_conn?.database }}
                  </div>
                </div>
              </div>
              <div class="confirm-tbl-wrap">
                <div class="confirm-label" style="padding:10px 14px 6px;font-size:.7rem">
                  테이블 설정 ({{ form.tables.length }}개)
                </div>
                <div class="confirm-tbl-hdr">
                  <span>테이블명</span><span>기준 컬럼</span><span>추가 조건</span><span>전략</span>
                </div>
                <div v-for="t in form.tables" :key="t.table" class="confirm-tbl-row">
                  <span class="mono">{{ t.table }}</span>
                  <span class="mono" style="color:var(--text-info)">{{ t.ts_col||'—' }}</span>
                  <span class="mono" style="color:var(--text-tertiary)">{{ t.extra_where||'—' }}</span>
                  <span class="strat-badge sm" :class="t.strategy">{{ t.strategy }}</span>
                </div>
              </div>
            </div>
            <!-- 네비 -->
            <div class="iwiz-nav">
              <button class="btn" @click="cancelEdit">취소</button>
              <div style="display:flex;gap:8px">
                <button v-if="cur>0" class="btn" @click="cur--">← 이전</button>
                <button v-if="cur<steps.length-1" class="btn btn-primary" @click="nextStep">다음 →</button>
                <button v-else class="btn btn-primary" @click="saveConfig" :disabled="saving">
                  <span v-if="saving" class="mini-spin"></span>
                  💾 저장
                </button>
              </div>
            </div>
          </div>

          <!-- 펼침: 테이블 상세 목록 (편집 중이 아닐 때) -->
          <div v-if="expandedCfg===cfg.id && editingId!==cfg.id" class="cfg-detail">
            <div v-if="resultMap[cfg.id]" class="cdc-result-bar" style="margin-bottom:10px">
              <template v-if="resultMap[cfg.id].status==='running'">
                <span class="mini-spin" style="width:10px;height:10px;border-color:rgba(59,130,246,.3);border-top-color:#2563eb"/>
                <span style="font-size:.75rem;color:var(--text-secondary)">
                  {{ resultMap[cfg.id].current_table || '처리 중...' }} 처리 중
                </span>
              </template>
              <template v-else>
                <span class="result-summary">
                  ✓ {{ resultMap[cfg.id].results?.filter(r=>r.status==='done').length||0 }}개 성공
                  <span v-if="resultMap[cfg.id].results?.some(r=>r.status==='error')"
                        style="color:#dc2626;margin-left:6px">
                    ✗ {{ resultMap[cfg.id].results?.filter(r=>r.status==='error').length }}개 오류
                  </span>
                </span>
              </template>
            </div>
            <div class="detail-grid">
              <div class="detail-hdr">
                <span>테이블명</span><span>기준 컬럼</span>
                <span>추가 조건</span><span>전략</span>
                <span>기준일자</span><span>마지막 동기화</span><span>결과</span>
              </div>
              <div v-for="t in (cfg.tables||[])" :key="t.table" class="detail-row">
                <span class="detail-tbl">{{ t.table }}</span>
                <span class="detail-mono" style="color:var(--text-info)">{{ t.ts_col||'—' }}</span>
                <span class="detail-mono" style="color:var(--text-tertiary)">{{ t.extra_where||'—' }}</span>
                <span class="strat-badge sm" :class="t.strategy">{{ t.strategy }}</span>
                <span class="detail-mono" style="color:var(--text-tertiary)">{{ t.base_date||'자동' }}</span>
                <span class="detail-sync">{{ fmtShort(stateMap[cfg.id]?.[t.table]?.last_sync) }}</span>
                <span v-if="getResult(cfg.id,t.table)" class="res-chip" :class="getResult(cfg.id,t.table).status">
                  {{ getResult(cfg.id,t.table).status==='done'?'✓':getResult(cfg.id,t.table).status==='error'?'✗':'…' }}
                  {{ getResult(cfg.id,t.table).rows?getResult(cfg.id,t.table).rows.toLocaleString()+'행':'' }}
                </span>
                <span v-else class="detail-empty">—</span>
              </div>
            </div>
          </div>

        </div><!-- /cfg 카드 -->

        <!-- 새 설정 카드 (v9 #55: 편집 중이면 절대 표시 안 됨) -->
        <div v-if="editingId==='__new__'" class="card cdc-cfg-card cdc-expanded" style="margin-top:8px">
          <div class="cdc-cfg-top" style="cursor:default">
            <div class="cdc-cfg-name">
              <span class="cfg-title">새 CDC 설정</span>
              <span class="edit-badge">작성 중</span>
            </div>
            <div class="cdc-cfg-btns" @click.stop>
              <button class="icon-btn danger" @click="cancelEdit" title="취소">
                <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px">
                  <line x1="2" y1="2" x2="12" y2="12"/><line x1="12" y1="2" x2="2" y2="12"/>
                </svg>
              </button>
            </div>
          </div>
          <div class="cfg-inline-edit">
            <div class="inline-wiz-hdr">
              <div class="inline-wiz-steps">
                <template v-for="(st, i) in steps" :key="i">
                  <button class="iwiz-step" :class="{active:cur===i,done:cur>i,reachable:cur>=i}" @click="goStep(i)">
                    <span class="iwiz-num">
                      <svg v-if="cur>i" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="1,5 4,8 9,2"/>
                      </svg>
                      <span v-else>{{ i+1 }}</span>
                    </span>
                    <span class="iwiz-lbl">{{ st }}</span>
                  </button>
                  <span v-if="i<steps.length-1" class="iwiz-line" :class="{done:cur>i}"/>
                </template>
              </div>
            </div>
            <div v-if="cur===0" class="iwiz-body">
              <div class="opts-grid-2">
                <div>
                  <div class="field-label">설정 이름 *</div>
                  <input v-model="form.name" class="field-input" placeholder="소스 → 타겟 변경분 이관"/>
                  <div class="field-label" style="margin-top:14px">배치 크기 (건)</div>
                  <input v-model.number="form.batch_size" type="number" min="100" max="50000"
                         class="field-input" style="max-width:160px"/>
                  <div class="field-desc">한 번에 처리할 최대 행 수 (기본 5,000)</div>
                </div>
                <div class="strat-guide">
                  <div class="strat-guide-title">이관 전략 안내</div>
                  <div class="strat-row"><span class="strat-badge append">Append</span><span class="strat-desc">INSERT만 — 이력 테이블</span></div>
                  <div class="strat-row"><span class="strat-badge upsert">UPSERT</span><span class="strat-desc">있으면 UPDATE, 없으면 INSERT</span></div>
                  <div class="strat-row"><span class="strat-badge full">Full</span><span class="strat-desc">전체 삭제 후 재입력</span></div>
                </div>
              </div>
            </div>
            <div v-if="cur===1" class="iwiz-body iwiz-tbl">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap">
                <input v-model="tblSearch" class="tbl-search" placeholder="테이블 검색..." @input="tblPage=1"/>
                <div class="filter-tabs">
                  <button v-for="f in filterTabs" :key="f.key" class="ftab"
                          :class="{active:tblFilter===f.key}" @click="tblFilter=f.key;tblPage=1">
                    {{ f.label }} <span class="ftab-cnt">{{ scanCounts[f.key]||0 }}</span>
                  </button>
                </div>
                <button class="btn btn-sm" @click="scanAll" :disabled="scanning">
                  <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:11px;height:11px">
                    <circle cx="6" cy="6" r="5"/><path d="M4 6l1.5 1.5L8 4"/>
                  </svg>
                  전체 자동감지
                </button>
              </div>
              <div v-if="!scanRows.length&&!scanning" class="scan-empty">
                <div style="font-size:.82rem;color:var(--text-tertiary)">자동감지를 실행하면 소스 DB 테이블이 표시됩니다.</div>
              </div>
            </div>
            <div v-if="cur===2" class="iwiz-body">
              <div class="confirm-grid">
                <div class="confirm-block"><div class="confirm-label">설정 이름</div><div class="confirm-val">{{ form.name }}</div></div>
                <div class="confirm-block"><div class="confirm-label">테이블 수</div><div class="confirm-val">{{ form.tables.length }}개</div></div>
              </div>
            </div>
            <div class="iwiz-nav">
              <button class="btn" @click="cancelEdit">취소</button>
              <div style="display:flex;gap:8px">
                <button v-if="cur>0" class="btn" @click="cur--">← 이전</button>
                <button v-if="cur<steps.length-1" class="btn btn-primary" @click="nextStep">다음 →</button>
                <button v-else class="btn btn-primary" @click="saveConfig" :disabled="saving">
                  <span v-if="saving" class="mini-spin"></span>
                  💾 저장
                </button>
              </div>
            </div>
          </div>
        </div><!-- /새 설정 카드 -->

      </div><!-- /cdc-cards -->
    </div><!-- /cdc-list-wrap -->

  </div>
</template>

<script setup>
import { fmtShort } from '@/utils/dateUtils.js'
import { ref, reactive, computed, onMounted, onActivated, onUnmounted } from 'vue'
import axios from 'axios'
import ConnectPanel from '@/components/common/ConnectPanel.vue'
import PageHeader   from '@/components/layout/PageHeader.vue'
import { useConnectorStore } from '@/store/connectorStore.js'
import { useAppStore }       from '@/store/appStore.js'

const API       = '/api/v1/cdc'
const connector = useConnectorStore()
const app       = useAppStore()

const steps = ['기본 정보', '테이블 설정', '확인 및 저장']
const cur   = ref(0)
const mode  = ref('list')  // 레거시 — 현재 미사용

// ── 목록 상태 ──────────────────────────────────────────────
const configs    = ref([])
const stateMap   = ref({})
const runningMap = ref({})
const resultMap  = ref({})
const saving     = ref(false)
const editingId  = ref(null)
const expandedCfg  = ref(null)  // 목록에서 펼쳐진 설정 ID
const pollingTimers = {}           // { cfgId: timerId } — 페이지 이탈 후 복원용

// ── 테이블 스캔 상태 ──────────────────────────────────────
const scanning     = ref(false)
const scanRows     = ref([])          // 전체 스캔 결과
const scanCounts   = ref({ all:0, recommended:0, unset:0, excluded:0 })
const tblSearch    = ref('')
const tblFilter    = ref('all')
const tblGroupFilter = ref('all')  // 그룹 필터: all|no_ts|has_date
const tblSort      = ref({ key:'', dir:1 })  // 정렬
const tblPage      = ref(1)
const tblPageSize  = ref(10)
const expandedRow      = ref(null)
const testQueryMap     = ref({})   // {table: {select, insert, delete, note}}
const tqActiveTab      = ref({})   // {table: 'INSERT'|'DELETE'|'SELECT'}
const copiedTable      = ref(null)
const copiedInsertTable = ref(null)
const dlLoading         = ref(false)
const scheduleOpenId    = ref(null)   // 스케줄 패널 열린 cfg.id
const scheduleMap       = ref({})     // { cfg.id: schedule 객체 }
const schForm           = ref({})     // { cfg.id: { type, interval_min, cron_expr, run_at } }
const schSaving         = ref(false)
const schTypes = [
  { key: 'repeat', label: '반복 실행' },
  { key: 'cron',   label: 'Cron 표현식' },
  { key: 'once',   label: '1회 실행' },
]
const cronExamples = [
  { label: '매일 02:00',     v: '0 2 * * *'   },
  { label: '매시간',         v: '0 * * * *'   },
  { label: '매주 월 09:00',  v: '0 9 * * 1'   },
  { label: '매월 1일 00:00', v: '0 0 1 * *'   },
]
const colPickerRow = ref(null)   // 컬럼 드롭다운 열린 행
const colSearch    = ref('')      // 컬럼 검색어
const savedState   = ref({})          // {table: {last_sync, ...}}

const filterTabs = [
  { key:'all',         label:'전체' },
  { key:'recommended', label:'추천됨' },
  { key:'unset',       label:'미설정' },
  { key:'excluded',    label:'제외' },
]

const defaultForm = () => ({
  name: '',
  src_conn: { db_type:'mssql', host:'', port:1433, database:'', username:'', password:'' },
  tgt_conn: { db_type:'mysql',  host:'', port:3306, database:'', username:'', password:'' },
  batch_size: 5000,
  tables: [],
})
const form = reactive(defaultForm())

// ── 필터/페이징 computed ──────────────────────────────────
const filteredRows = computed(() => {
  let rows = scanRows.value
  // 텍스트 검색
  if (tblSearch.value) {
    const q = tblSearch.value.toLowerCase()
    rows = rows.filter(r => r.table.toLowerCase().includes(q))
  }
  // 상태 탭 필터
  if (tblFilter.value === 'recommended')
    rows = rows.filter(r => r.status === 'recommended' || r.status === 'saved')
  else if (tblFilter.value === 'unset')
    rows = rows.filter(r => r.status === 'unset')
  else if (tblFilter.value === 'excluded')
    rows = rows.filter(r => r.excluded)
  // 그룹 필터 (select box)
  if (tblGroupFilter.value === 'no_ts')
    rows = rows.filter(r => !r.ts_col)
  else if (tblGroupFilter.value === 'has_ts')
    rows = rows.filter(r => !!r.ts_col)
  else if (tblGroupFilter.value === 'has_date')
    rows = rows.filter(r => !!r.base_date)
  else if (tblGroupFilter.value === 'no_pk')
    rows = rows.filter(r => !r.pk_cols?.length)
  else if (tblGroupFilter.value === 'append')
    rows = rows.filter(r => r.strategy === 'append')
  else if (tblGroupFilter.value === 'upsert')
    rows = rows.filter(r => r.strategy === 'upsert')
  else if (tblGroupFilter.value === 'full')
    rows = rows.filter(r => r.strategy === 'full')
  // 정렬
  const { key, dir } = tblSort.value
  if (key) {
    rows = [...rows].sort((a, b) => {
      let av = a[key], bv = b[key]
      if (key === 'row_count') { av = av??-1; bv = bv??-1 }
      if (key === 'table') { av = av||''; bv = bv||'' }
      if (typeof av === 'string') return av.localeCompare(bv) * dir
      return ((av??0) - (bv??0)) * dir
    })
  }
  return rows
})
const totalFiltered = computed(() => filteredRows.value.length)
const totalPages    = computed(() => Math.ceil(totalFiltered.value / tblPageSize.value))
const pagedRows     = computed(() => {
  const s = (tblPage.value - 1) * tblPageSize.value
  return filteredRows.value.slice(s, s + tblPageSize.value)
})
const pageNumbers = computed(() => {
  const total = totalPages.value
  const cur   = tblPage.value
  if (total <= 7) {
    // 7페이지 이하 → 전부 표시
    return Array.from({ length: total }, (_, i) => i + 1)
  }
  // 7페이지 초과 → 현재 ±2 + 첫/마지막, 생략은 -1로 표시
  const pages = new Set([1, total])
  for (let i = Math.max(1, cur-2); i <= Math.min(total, cur+2); i++) pages.add(i)
  const sorted = [...pages].sort((a,b) => a-b)
  const result = []
  let prev = 0
  for (const p of sorted) {
    if (p - prev > 1) result.push(-1)  // ... 생략 표시
    result.push(p)
    prev = p
  }
  return result
})
const allChecked = computed(() =>
  pagedRows.value.length > 0 && pagedRows.value.every(r => !r.excluded)
)

// ── ConnectPanel 연결 완료 ─────────────────────────────
function onConnected() {
  const s = connector.source; const t = connector.target
  if (s?.host) form.src_conn = { db_type:s.dbType||s.db_type||'mssql', host:s.host, port:s.port||1433, database:s.database||'', username:s.username||'', password:s.password||'' }
  if (t?.host) form.tgt_conn = { db_type:t.dbType||t.db_type||'mysql',  host:t.host, port:t.port||3306, database:t.database||'', username:t.username||'', password:t.password||'' }
}

// ── 목록 로드 ─────────────────────────────────────────
async function loadConfigs() {
  try {
    const { data } = await axios.get(`${API}/configs`)
    // v9 패치 #58: __new__ 같은 잘못된 ID 자동 감지 & 제거
    // 이전 버그로 잘못된 ID 의 설정이 저장돼있으면
    //   → 편집/새설정 누를 때마다 레이어 2개씩 열리는 원인
    const INVALID_IDS = ['__new__', '', null, undefined]
    const orphans = data.filter(c => INVALID_IDS.includes(c.id))
    if (orphans.length) {
      console.warn('[CDC] 잘못된 ID 의 설정 발견 — 자동 삭제:', orphans)
      for (const bad of orphans) {
        try {
          await axios.delete(`${API}/configs/${encodeURIComponent(bad.id || '__new__')}`)
        } catch (e) {
          console.warn('삭제 실패 (무시):', e?.message)
        }
      }
      // 삭제 후 다시 로드
      const again = await axios.get(`${API}/configs`)
      configs.value = again.data.filter(c => !INVALID_IDS.includes(c.id))
    } else {
      configs.value = data
    }
    for (const cfg of configs.value) await loadState(cfg)
  } catch(e) { console.error(e) }
}
async function loadState(cfg) {
  try {
    const { data } = await axios.get(`${API}/state`, {
      params: { src_host:cfg.src_conn?.host, src_db:cfg.src_conn?.database,
                tgt_host:cfg.tgt_conn?.host, tgt_db:cfg.tgt_conn?.database }
    })
    stateMap.value[cfg.id] = data
  } catch {}
}

// ── 위저드 제어 ──────────────────────────────────────
function startNew() {
  // v9 패치 #55: 기존 편집/신규 작성 중이면 자동으로 닫고 새로 시작
  // (이전엔 "test 편집 중" 카드 + "새 CDC 설정 작성 중" 카드가 동시에 떴음)
  if (editingId.value) {
    // 편집 중이거나 '__new__' 작성 중 → 정리
    editingId.value = null
    expandedCfg.value = null
    cur.value = 0
    scanRows.value = []
  }
  Object.assign(form, defaultForm())
  const s = connector.source; const t = connector.target
  if (s?.host) form.src_conn = { db_type:s.dbType||'mssql', host:s.host, port:s.port||1433, database:s.database||'', username:s.username||'', password:s.password||'' }
  if (t?.host) form.tgt_conn = { db_type:t.dbType||'mysql',  host:t.host, port:t.port||3306, database:t.database||'', username:t.username||'', password:t.password||'' }
  scanRows.value = []; tblSearch.value = ''; tblFilter.value = 'all'; tblPage.value = 1
  editingId.value = '__new__'; cur.value = 0; expandedCfg.value = '__new__'
}
function editCfg(cfg) {
  // v9 패치 #55: 이전에 "+ 새 설정" 작성 중이던 '__new__' 카드가 있으면 먼저 닫음
  // (editingId 를 cfg.id 로만 덮으면 '__new__' 카드는 v-if 로 사라지는 게 맞지만
  //  혹시 남아있을 가능성 대비해서 명시적 초기화)
  if (editingId.value === '__new__') {
    editingId.value = null
    scanRows.value = []
  }
  Object.assign(form, JSON.parse(JSON.stringify(cfg)))
  // 저장된 테이블 설정을 scanRows로 복원 (Step 1 진입 시 바로 보이도록)
  const savedMap = {}
  for (const t of (cfg.tables || [])) savedMap[t.table] = t
  form._savedMap = savedMap

  // 저장된 테이블 목록을 scanRows에 미리 세팅
  const stMap = stateMap.value[cfg.id] || {}
  scanRows.value = (cfg.tables || []).map(t => {
    // base_date 없으면 last_sync 자동 채우기
    const lastSync = stMap[t.table]?.last_sync || ''
    const baseDate = t.base_date || _cleanSyncVal(lastSync)
    return {
      table:         t.table,
      ts_col:        t.ts_col || '',
      extra_where:   t.extra_where || '',
      strategy:      t.strategy || 'append',
      base_date:     baseDate,
      pk_cols:       t.pk_cols || [],
      ts_candidates: [],
      recommended_ts: t.ts_col || null,
      is_saved:      true,
      excluded:      false,
      status:        'saved',
      all_cols:      [],
      row_count:     null,
    }
  })
  scanCounts.value = {
    all:         scanRows.value.length,
    recommended: scanRows.value.length,
    unset:       0,
    excluded:    0,
  }

  tblSearch.value = ''; tblFilter.value = 'all'; tblPage.value = 1
  savedState.value = stateMap.value[cfg.id] || {}
  editingId.value = cfg.id
  cur.value = 0
  expandedCfg.value = cfg.id
}
// ── 스케줄 관련 ──────────────────────────────────────────
async function loadSchedules() {
  try {
    const { data } = await axios.get('/api/v1/jobs/schedules')
    const map = {}
    for (const s of data) {
      if (s.job_type === 'cdc' && s.job_config?.cdc_cfg_id) {
        map[s.job_config.cdc_cfg_id] = s
      }
    }
    scheduleMap.value = map
  } catch(e) { /* 무시 */ }
}

function openSchedule(cfg) {
  if (scheduleOpenId.value === cfg.id) {
    scheduleOpenId.value = null
    return
  }
  scheduleOpenId.value = cfg.id
  // 기존 스케줄 있으면 폼에 채우기
  const existing = scheduleMap.value[cfg.id]
  schForm.value[cfg.id] = existing ? {
    mode:         'schedule',
    type:         existing.type === 'interval' ? 'repeat' : (existing.type || 'repeat'),
    interval:     existing.interval || 'every_n',
    every_n_min:  existing.every_n_min || 10,
    minute:       existing.minute || '0',
    time:         existing.time || '00:00',
    cron_expr:    existing.cron_expr || '',
    date:         existing.date || '',
    run_at:       existing.run_at || '',
  } : {
    mode:         'now',
    type:         'repeat',
    interval:     'every_n',
    every_n_min:  10,
    minute:       '0',
    time:         '00:00',
    cron_expr:    '',
    date:         '',
    run_at:       '',
  }
}

function setSchMode(cfgId, mode) {
  if (!schForm.value[cfgId]) schForm.value[cfgId] = {}
  schForm.value[cfgId].mode = mode
}

function schPreview(cfgId) {
  const f = schForm.value[cfgId]
  if (!f || f.type !== 'repeat') return ''
  if (f.interval === 'every_n') {
    const n = f.every_n_min || 10
    return `매 ${n}분마다 실행 (cron: */${n} * * * *)`
  }
  if (f.interval === 'hourly') {
    const min = f.minute || '0'
    return `매시 ${min}분에 실행 (cron: ${min} * * * *)`
  }
  const map = { daily:'매일', weekly:'매주 월요일', monthly:'매월 1일' }
  return `${map[f.interval]||''} ${f.time||''} 실행`
}

function setSchType(cfgId, type) {
  if (!schForm.value[cfgId]) schForm.value[cfgId] = {}
  schForm.value[cfgId].type = type
}

async function saveSchedule(cfg) {
  const f = schForm.value[cfg.id]
  if (!f) return

  schSaving.value = true
  try {
    // 기존 스케줄 있으면 삭제 후 재등록
    const existing = scheduleMap.value[cfg.id]
    if (existing) {
      await axios.delete(`/api/v1/jobs/schedules/${existing.id}`)
    }

    // repeat → interval_min 계산
    const intervalMinMap = { hourly:60, daily:1440, weekly:10080, monthly:43200 }
    const minute = f.interval === 'hourly' ? (f.minute || '0') : '0'
    // repeat → cron 표현식으로 변환 (매시간 분 지정 포함)
    let schType, cronExpr = '', intervalMin = 60, runAt = ''
    if (f.type === 'repeat') {
      schType  = 'cron'
      const t  = (f.time || '00:00').split(':')
      const hh = t[0] || '0', mm = t[1] || '0'
      const min = f.minute || '0'
      const n = f.every_n_min || 10
      const cronMap = {
        every_n: `*/${n} * * * *`,       // N분마다
        hourly:  `${min} * * * *`,       // 매시 N분
        daily:   `${mm} ${hh} * * *`,    // 매일 HH:MM
        weekly:  `${mm} ${hh} * * 1`,    // 매주 월요일
        monthly: `${mm} ${hh} 1 * *`,    // 매월 1일
      }
      cronExpr = cronMap[f.interval] || `0 * * * *`
    } else if (f.type === 'cron') {
      schType  = 'cron'
      cronExpr = f.cron_expr || ''
    } else {
      schType  = 'once'
      runAt    = `${f.date}T${f.time}:00`
    }
    const payload = {
      name:         cfg.name + ' (CDC)',
      type:         schType,
      interval_min: intervalMin,
      cron_expr:    cronExpr,
      run_at:       runAt,
      interval:     f.interval,
      minute:       f.minute || '0',
      time:         f.time || '00:00',
      cdc_cfg_id:   cfg.id,
      cdc_config:   cfg,
    }

    await axios.post('/api/v1/jobs/cdc-schedules', payload)
    await loadSchedules()
    scheduleOpenId.value = null
    app.notify('스케줄이 등록됐습니다', 'success')
  } catch(e) {
    app.notify('스케줄 등록 실패: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    schSaving.value = false
  }
}

async function deleteSchedule(cfgId) {
  const sch = scheduleMap.value[cfgId]
  if (!sch) return
  if (!confirm('스케줄을 삭제할까요?')) return
  try {
    await axios.delete(`/api/v1/jobs/schedules/${sch.id}`)
    delete scheduleMap.value[cfgId]
    app.notify('스케줄이 삭제됐습니다', 'success')
  } catch(e) {
    app.notify('스케줄 삭제 실패', 'error')
  }
}

function cancelEdit() { editingId.value = null; expandedCfg.value = null; cur.value = 0; scanRows.value = [] }
function goStep(i)    { if (i <= cur.value) cur.value = i }
function nextStep() {
  if (cur.value === 0 && !form.name.trim()) { app.notify('설정 이름을 입력하세요', 'warn'); return }
  if (cur.value === 1) {
    const selected = scanRows.value.filter(r => !r.excluded)
    if (!selected.length) { app.notify('테이블을 하나 이상 선택하세요', 'warn'); return }
    // form.tables에 현재 선택된 행 반영
    form.tables = selected.map(r => ({
      table:       r.table,
      ts_col:      r.ts_col || '',
      extra_where: r.extra_where || '',
      strategy:    r.strategy,
      base_date:   r.base_date  || '',
    }))
  }
  cur.value++
}

// ── 테이블 전체 스캔 ──────────────────────────────────
async function scanAll() {
  if (!form.src_conn.host) { app.notify('소스 DB 연결 정보가 없습니다', 'warn'); return }
  scanning.value = true; expandedRow.value = null
  try {
    // 저장된 테이블 설정
    const savedMap = {}
    if (editingId.value) {
      const cfg = configs.value.find(c => c.id === editingId.value)
      if (cfg) for (const t of (cfg.tables||[])) savedMap[t.table] = t
    }
    // form._savedMap이 있으면 우선
    if (form._savedMap) Object.assign(savedMap, form._savedMap)

    const { data } = await axios.post(`${API}/scan-tables`, {
      conn_info:     { ...form.src_conn },
      tgt_conn_info: { ...form.tgt_conn },   // v9 #60: 타겟 PK 폴백용
      saved_tables: savedMap,
      page:         1,
      page_size:    9999,
    })
    // base_date에 last_sync 자동 채우기
    const curSavedState = savedState.value || {}
    scanRows.value  = (data.tables || []).map(r => {
      const lastSync = curSavedState[r.table]?.last_sync || ''
      return {
        ...r,
        base_date: r.base_date || _cleanSyncVal(lastSync),
        all_cols:  [],
        row_count: null,
      }
    })
    scanCounts.value = {
      all:         scanRows.value.length,
      recommended: scanRows.value.filter(r => r.status==='recommended'||r.status==='saved').length,
      unset:       scanRows.value.filter(r => r.status==='unset').length,
      excluded:    scanRows.value.filter(r => r.excluded).length,
    }
    app.notify(`${data.total}개 테이블 분석 완료`, 'success')
    // 첫 페이지 건수 미리 로드 (비동기)
    const first10 = (data.tables || []).slice(0, 10)
    for (const row of first10) loadRowCount(row)
  } catch(e) {
    app.notify('스캔 실패: ' + (e.response?.data?.detail || e.message), 'error')
  } finally { scanning.value = false }
}

// ── 컬럼 피커 ────────────────────────────────────────
function openColPicker(row) {
  colPickerRow.value = colPickerRow.value === row.table ? null : row.table
  colSearch.value = ''
  // 전체 컬럼 목록이 없으면 로드
  if (!row.all_cols?.length) loadAllCols(row)
}
function selectCol(row, colName) {
  row.ts_col = colName
  onTsColChange(row)
  colPickerRow.value = null
  colSearch.value = ''
}
function filteredAllCols(row) {
  const cols = row.all_cols || []
  if (!colSearch.value) return cols
  const q = colSearch.value.toLowerCase()
  return cols.filter(c => c.name.toLowerCase().includes(q))
}
async function loadAllCols(row) {
  if (!form.src_conn.host) return
  try {
    const { data } = await axios.post(`${API}/table-columns`, {
      conn_info: { ...form.src_conn },
      table: row.table,
    })
    row.all_cols = data.columns || []
    // 컬럼 로드 완료 → 테스트 쿼리 자동 갱신
    if (testQueryMap.value[row.table]) generateTestQuery(row)
  } catch(e) { console.error('컬럼 로드 실패', e) }
}

// ── 건수 조회 ─────────────────────────────────────────
async function loadRowCount(row) {
  if (row.row_count != null || !form.src_conn.host) return
  try {
    const { data } = await axios.post(`${API}/table-count`, {
      conn_info: { ...form.src_conn },
      table: row.table,
    })
    row.row_count = data.count
  } catch {}
}

// ── 행 조작 ──────────────────────────────────────────
function toggleSort(key) {
  if (tblSort.value.key === key) {
    tblSort.value.dir *= -1
  } else {
    tblSort.value = { key, dir: 1 }
  }
  tblPage.value = 1
}
function sortIcon(key) {
  if (tblSort.value.key !== key) return '↕'
  return tblSort.value.dir === 1 ? '↑' : '↓'
}

function toggleExpand(table) {
  expandedRow.value = expandedRow.value === table ? null : table
  colPickerRow.value = null
  // 펼칠 때 건수 로드
  if (expandedRow.value === table) {
    const row = scanRows.value.find(r => r.table === table)
    if (row) loadRowCount(row)
  }
}
function toggleExclude(row, e) {
  row.excluded = !e.target.checked
  // 카운트 갱신
  scanCounts.value.excluded = scanRows.value.filter(r => r.excluded).length
}
function toggleAllCheck(e) {
  pagedRows.value.forEach(r => r.excluded = !e.target.checked)
  scanCounts.value.excluded = scanRows.value.filter(r => r.excluded).length
}
function onTsColChange(row) {
  if (!row.ts_col) row.strategy = 'full'
  else if (row.strategy === 'full' && row.pk_cols?.length) row.strategy = 'upsert'
}
// ── 테스트 쿼리 생성 ──────────────────────────────────────
function generateTestQuery(row) {
  const srcDb   = (form.src_conn?.db_type || 'mssql').toLowerCase()
  const table   = row.table
  const tsCol   = row.ts_col
  const baseDate = row.base_date || _cleanSyncVal(savedState.value[table]?.last_sync) || '1900-01-01 00:00:00'
  const extra   = (row.extra_where || '').trim().replace(/^AND\s+/i, '')
  const strat   = row.strategy

  // 소스 DB 인용부호 (소스 DB 기준 — 거기서 실행할 쿼리)
  const q    = (col) => srcDb.includes('mssql') ? `[${col}]` : `\`${col}\``
  const nolock = srcDb.includes('mssql') ? ' WITH(NOLOCK)' : ''
  const now  = new Date().toISOString().slice(0,19).replace('T',' ')

  // 컬럼 목록
  const allCols = row.all_cols?.length ? row.all_cols : []
  const pkCols  = row.pk_cols || []

  // 기준 WHERE
  let baseWhere = ''
  if (tsCol) {
    baseWhere = `${q(tsCol)} > '${baseDate}'`
    if (extra) baseWhere += `\n  AND ${extra}`
  } else if (extra) {
    baseWhere = extra
  }

  // ── SELECT: 변경분 확인 ──
  let selectSql = ''
  if (strat === 'full') {
    selectSql = `-- [확인] 전체 데이터 조회 (Full 전략)\nSELECT TOP 100 *\nFROM ${q(table)}${nolock}`
    if (extra) selectSql += `\nWHERE ${extra}`
    selectSql += `\n-- 행 수 확인\n-- SELECT COUNT(*) FROM ${q(table)}${extra ? ' WHERE '+extra : ''}`
  } else if (tsCol) {
    selectSql = `-- [확인] 변경분 조회 — 이 데이터가 이관 대상입니다\nSELECT TOP 100 *\nFROM ${q(table)}${nolock}\nWHERE ${baseWhere}\nORDER BY ${q(tsCol)}\n\n-- 변경분 건수 확인\nSELECT COUNT(*) AS cnt\nFROM ${q(table)}${nolock}\nWHERE ${baseWhere}`
  } else {
    selectSql = `-- 기준 컬럼이 없습니다. Full 전략을 권장합니다.`
  }

  // ── INSERT: 소스 DB에 테스트 데이터 삽입 ──
  let insertSql = ''
  if (!allCols.length) {
    insertSql = `-- 컬럼 피커를 열면 전체 컬럼 목록이 로드됩니다\n-- 로드 후 다시 [테스트 쿼리] 버튼을 클릭하세요\n\nINSERT INTO ${q(table)} (...) VALUES (...)`
  } else {
    const notNullCols = allCols.filter(c => c.nullable === 'NO' || pkCols.includes(c.name))
    const targetCols  = notNullCols.length ? notNullCols : allCols.slice(0, Math.min(6, allCols.length))
    const colNames    = targetCols.map(c => q(c.name)).join(',\n  ')

    // 타입별 샘플값 생성
    const sampleVal = (c) => {
      const t = (c.type || '').toLowerCase()
      if (pkCols.includes(c.name)) return srcDb.includes('mssql') ? '/* PK값 */' : '/* PK값 */'
      if (t.includes('int') || t.includes('numeric') || t.includes('decimal') || t.includes('float')) return '1'
      if (t.includes('datetime') || t.includes('timestamp') || t === 'date') return `'${now}'`
      if (t.includes('char') || t.includes('text') || t.includes('varchar')) return `'TEST_${c.name.slice(0,8).toUpperCase()}'`
      if (t.includes('bit') || t.includes('bool')) return '1'
      return `'TEST'`
    }

    const valList = targetCols.map(c => sampleVal(c)).join(',\n  ')
    const omitted = allCols.length - targetCols.length
    const omitNote = omitted > 0 ? `\n-- ※ NULL 허용 컬럼 ${omitted}개 생략 (필요시 추가)` : ''

    insertSql = `-- [테스트] 소스 DB에 테스트 데이터 삽입${omitNote}\nINSERT INTO ${q(table)} (\n  ${colNames}\n) VALUES (\n  ${valList}\n)`

    if (tsCol) {
      insertSql += `\n\n-- ※ ${q(tsCol)} 컬럼을 현재 시각보다 크게 설정하면\n--   다음 CDC 실행 시 이관 대상이 됩니다`
    }
  }

  // ── DELETE: 테스트 데이터 삭제 ──
  let deleteSql = ''
  if (!allCols.length) {
    deleteSql = `-- 컬럼 피커를 열면 전체 컬럼 목록이 로드됩니다\n\nDELETE FROM ${q(table)}\nWHERE /* 조건 입력 */`
  } else {
    const pkWhere = pkCols.length
      ? pkCols.map(c => `${q(c)} = /* 값 */`).join('\n  AND ')
      : `/* PK 없음 — 조건 직접 입력 */`

    deleteSql = `-- [정리] 테스트 데이터 삭제 (반복 테스트 시)\n-- 삭제 전 반드시 SELECT로 확인하세요!\n\n-- 1) 삭제 대상 확인\nSELECT * FROM ${q(table)}${nolock}\nWHERE ${pkWhere}\n\n-- 2) 삭제 실행\nDELETE FROM ${q(table)}\nWHERE ${pkWhere}`

    if (tsCol) {
      deleteSql += `\n\n-- 또는 테스트로 삽입한 최근 데이터만 삭제\nDELETE FROM ${q(table)}\nWHERE ${q(tsCol)} >= '${now}'`
    }
  }

  testQueryMap.value[table] = {
    select: selectSql,
    insert: insertSql,
    delete: deleteSql,
    note: tsCol ? ` 기준: ${q(tsCol)} > '${baseDate}'` : '',
  }
  if (!tqActiveTab.value[table]) tqActiveTab.value[table] = 'INSERT'

  // 컬럼 없으면 자동 로드
  if (!row.all_cols?.length) loadAllCols(row)
}

async function downloadTestSql() {
  // 기준컬럼 있는 테이블 최대 5개
  const targets = scanRows.value
    .filter(r => r.ts_col && !r.excluded)
    .slice(0, 5)
    .map(r => ({
      table:    r.table,
      ts_col:   r.ts_col,
      pk_cols:  r.pk_cols || [],
      strategy: r.strategy,
    }))
  if (!targets.length) {
    app.notify('기준 컬럼이 설정된 테이블이 없습니다', 'warn')
    return
  }
  dlLoading.value = true
  try {
    const res = await axios.post(`${API}/generate-test-sql`, {
      conn_info:    { ...form.src_conn },
      tables:       targets,
      max_tables:   5,
      rows_per_table: 100,
    }, { responseType: 'blob' })
    // 파일 다운로드
    const url  = URL.createObjectURL(new Blob([res.data], { type: 'text/plain' }))
    const a    = document.createElement('a')
    const cd   = res.headers['content-disposition'] || ''
    const match = cd.match(/filename="(.+)"/)
    a.href     = url
    a.download = match ? match[1] : 'cdc_test.sql'
    a.click()
    URL.revokeObjectURL(url)
    app.notify(`테스트 SQL 다운로드 완료 (${targets.length}개 테이블)`, 'success')
  } catch(e) {
    app.notify('다운로드 실패: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    dlLoading.value = false
  }
}

function setTqTab(table, tab) {
  tqActiveTab.value[table] = tab
}

function getActiveTqSql(table) {
  const tab = tqActiveTab.value[table] || 'INSERT'
  const m   = testQueryMap.value[table] || {}
  if (tab === 'INSERT') return m.insert || ''
  if (tab === 'DELETE') return m.delete || ''
  return m.select || ''
}

async function copyTqTab(table) {
  const sql = getActiveTqSql(table)
  await navigator.clipboard.writeText(sql)
  copiedTable.value = table
  setTimeout(() => { copiedTable.value = null }, 2000)
}


function saveRow(row) {
  row.is_saved = true
  row.status   = 'saved'
  // base_date가 있으면 savedState에 반영
  if (row.base_date) {
    if (!savedState.value[row.table]) savedState.value[row.table] = {}
    savedState.value[row.table].last_sync = row.base_date
  }
  expandedRow.value = null
  colPickerRow.value = null
  app.notify(`${row.table} 설정 저장됨`, 'success')
}
function resetRow(row) {
  row.ts_col      = row.recommended_ts || ''
  row.extra_where = ''
  row.strategy    = row.recommended_ts ? (row.pk_cols?.length ? 'upsert' : 'append') : 'full'
  row.is_saved    = false
  row.status      = row.recommended_ts ? 'recommended' : 'unset'
}
async function resetOneSync(table) {
  const cfg = configs.value.find(c => c.id === editingId.value); if (!cfg) return
  await axios.delete(`${API}/state/table`, {
    params: { src_host:cfg.src_conn.host, src_db:cfg.src_conn.database,
              tgt_host:cfg.tgt_conn.host, tgt_db:cfg.tgt_conn.database, table }
  })
  await loadState(cfg)
  savedState.value = stateMap.value[editingId.value] || {}
  app.notify(`${table} 초기화 완료`, 'success')
}

// ── 저장 ─────────────────────────────────────────────
async function saveConfig() {
  saving.value = true
  try {
    const payload = JSON.parse(JSON.stringify(form))
    delete payload._savedMap
    // v9 패치 #56: '__new__' 는 "신규 작성 중" 임시 마커이지 실제 ID 가 아님
    // 기존 코드: if (editingId.value) PUT  → '__new__' 도 truthy 라 PUT 호출됨
    //           → 서버가 ID='__new__' 로 저장 → 다음 편집 시 editingId 판별 꼬임
    // 수정: '__new__' 는 명시적으로 POST 로 신규 생성
    const isNew = !editingId.value || editingId.value === '__new__'
    if (isNew) {
      // 서버가 ID 발급 — payload 의 id 필드 제거해서 혼동 방지
      delete payload.id
      await axios.post(`${API}/configs`, payload)
    } else {
      await axios.put(`${API}/configs/${editingId.value}`, payload)
    }
    app.notify('CDC 설정 저장 완료', 'success')
    editingId.value = null; expandedCfg.value = null; cur.value = 0; scanRows.value = []
    await loadConfigs()
  } catch(e) { app.notify('저장 실패: ' + (e.response?.data?.detail || e.message), 'error') }
  finally    { saving.value = false }
}

// ── 삭제 ─────────────────────────────────────────────
async function deleteCfg(id) {
  if (!confirm('삭제할까요?')) return
  await axios.delete(`${API}/configs/${id}`)
  app.notify('삭제 완료', 'success'); await loadConfigs()
}

// ── 실행 ─────────────────────────────────────────────
async function runCfg(cfg) {
  if (runningMap.value[cfg.id]) return
  try {
    const { data } = await axios.post(`${API}/run/${cfg.id}`)
    runningMap.value[cfg.id] = data.cdc_id
    resultMap.value[cfg.id]  = { status:'running', results:[] }
    pollStatus(cfg.id, data.cdc_id)
    app.notify(`${cfg.name} 실행 시작`, 'info')
  } catch(e) { app.notify('실행 실패: ' + (e.response?.data?.detail || e.message), 'error') }
}
function pollStatus(cfgId, cdcId) {
  // 기존 타이머 있으면 정리
  if (pollingTimers[cfgId]) clearInterval(pollingTimers[cfgId])

  const timer = setInterval(async () => {
    try {
      const { data } = await axios.get(`${API}/status/${cdcId}`)
      resultMap.value[cfgId] = data
      if (data.status !== 'running') {
        clearInterval(timer)
        delete pollingTimers[cfgId]
        delete runningMap.value[cfgId]
        const cfg = configs.value.find(c => c.id === cfgId)
        if (cfg) await loadState(cfg)
        const ok   = data.results?.filter(r => r.status==='done').length  || 0
        const fail = data.results?.filter(r => r.status==='error').length || 0
        const failMsg = fail ? ' / 오류 ' + fail + '개' : ''
        app.notify('CDC 완료 — 성공 ' + ok + '개' + failMsg, fail ? 'warn' : 'success')
      }
    } catch {
      clearInterval(timer)
      delete pollingTimers[cfgId]
      delete runningMap.value[cfgId]
    }
  }, 2000)

  pollingTimers[cfgId] = timer
}

// ── 실행 중인 CDC 상태 복원 ──────────────────────────────
async function restoreRunning() {
  try {
    const { data } = await axios.get(`${API}/status`)
    // data = { cdcId: { status, results, ... } }
    for (const [cdcId, state] of Object.entries(data)) {
      if (state.status !== 'running') continue
      // cdcId 형식: "{configId}_{hex}" → configId 추출
      const cfgId = cdcId.split('_').slice(0, -1).join('_')
      const cfg = configs.value.find(c => c.id === cfgId)
      if (!cfg) continue
      // 이미 폴링 중이면 스킵
      if (pollingTimers[cfgId]) continue
      runningMap.value[cfgId]  = cdcId
      resultMap.value[cfgId]   = state
      pollStatus(cfgId, cdcId)
      app.notify(cfg.name + ' 실행 재연결됨', 'info')
    }
  } catch(e) { console.error('CDC 상태 복원 실패', e) }
}

function getResult(cfgId, table) {
  return resultMap.value[cfgId]?.results?.find(r => r.table === table)
}

// last_sync 값을 base_date 입력용으로 정리 (마이크로초 제거)
function _cleanSyncVal(val) {
  if (!val || val.startsWith('1900')) return ''
  // .530000 → .530 밀리초만 유지, 또는 초 단위로 자름
  let s = String(val).replace('T', ' ').replace(/Z$/, '').replace(/[+-]\d{2}:\d{2}$/, '')
  // 마이크로초 .NNNNNN → .NNN
  s = s.replace(/(\.\d{3})\d+/, '$1')
  // .000 이면 제거
  s = s.replace(/\.000$/, '')
  return s.trim()
}



// ── 동기화 모드 비교 배너 (v9+) ─────────────────────
const modeInfoOpen = ref(false)
const syncModes = ref([])
const enginesAvailable = ref({})

async function loadSyncModes() {
  try {
    // v9 패치 #57: @/api/index.js 는 default export 가 없음 → 직접 axios 사용
    const r = await axios.get('/api/v1/cdc/modes')
    syncModes.value = r.data.modes || []
    enginesAvailable.value = r.data.engines_available || {}
  } catch (e) {
    console.error('동기화 모드 로드 실패:', e)
  }
}

function isModeAvailable(key) {
  if (key === 'migration' || key === 'incremental') return true
  return enginesAvailable.value[key] === true
}

onMounted(async () => {
  await loadConfigs()
  await restoreRunning()
  await loadSchedules()
  loadSyncModes()  // 비동기, 실패해도 기능에 영향 없음
  document.addEventListener('click', () => { colPickerRow.value = null })
})

// 다른 페이지 갔다 돌아왔을 때도 복원
onActivated(async () => {
  await loadConfigs()
  await restoreRunning()
})

// 페이지 언마운트 시 타이머 정리 (메모리 누수 방지)
onUnmounted(() => {
  for (const timer of Object.values(pollingTimers)) clearInterval(timer)
})
</script>


<style scoped>
.cdc-wrap{display:flex;flex-direction:column;gap:0}

/* ── 동기화 모드 비교 배너 (v9+) ─────────────────── */
.mode-banner {
  background: var(--bg-primary); border: 0.5px solid var(--border-mid);
  border-radius: var(--radius-md); padding: 16px; margin-bottom: 16px;
}
.mode-banner-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 12px; font-size: 13px;
}
.btn-icon-close {
  background: transparent; border: none; cursor: pointer; font-size: 13px;
  color: var(--text-tertiary); padding: 4px 8px;
}
.btn-icon-close:hover { color: var(--text-primary); }
.mode-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 8px; margin-bottom: 12px;
}
.mode-card {
  padding: 10px 12px; border: 1px solid var(--border-light); border-radius: 6px;
  background: var(--bg-secondary); opacity: 0.55;
  font-size: 11.5px; line-height: 1.5;
}
.mode-card.available { opacity: 1; border-color: var(--accent-blue); background: var(--bg-primary); }
.mode-name { font-weight: 600; color: var(--text-primary); margin-bottom: 2px; font-size: 12.5px; }
.mode-latency { color: var(--accent-blue); font-size: 10.5px; margin-bottom: 6px; }
.mode-desc { color: var(--text-secondary); margin-bottom: 6px; }
.mode-dbs { color: var(--text-tertiary); font-size: 10.5px; margin-bottom: 4px; }
.mode-limits { color: var(--text-warning); font-size: 10.5px; }
.mode-banner-note {
  background: var(--bg-info); padding: 10px 12px; border-radius: 4px;
  font-size: 11.5px; color: var(--text-secondary); line-height: 1.6;
}
.mode-banner-note code {
  background: var(--bg-primary); padding: 1px 5px; border-radius: 3px;
  font-family: monospace; font-size: 10.5px;
}
.btn-outline {
  background: transparent; border: 1px solid var(--border-mid);
  padding: 5px 10px; border-radius: 4px; cursor: pointer; color: var(--text-secondary);
}
.btn-outline:hover { background: var(--bg-secondary); color: var(--text-primary); }


/* ── 위저드 헤더 ── */
.wiz-topbar{display:flex;align-items:center;justify-content:space-between;padding:14px 0 12px;border-bottom:0.5px solid var(--border-light);margin-bottom:16px;flex-wrap:wrap;gap:12px}
.wiz-topbar-left{display:flex;flex-direction:column;gap:2px}
.wiz-title{font-size:1.15rem;font-weight:700;color:var(--text-primary)}
.wiz-subtitle{font-size:.75rem;color:var(--text-tertiary)}
.wiz-steps{display:flex;align-items:center}
.wiz-step{display:flex;align-items:center;gap:6px;padding:6px 10px;border:none;background:none;cursor:default;color:var(--text-tertiary);font-family:var(--font);font-size:.78rem}
.wiz-step.reachable{cursor:pointer}
.wiz-step.reachable:hover{color:var(--text-secondary)}
.wiz-step-num{width:20px;height:20px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:.68rem;font-weight:700;border:1.5px solid var(--border-mid);background:var(--bg-secondary)}
.wiz-step-lbl{font-size:.75rem;font-weight:500;white-space:nowrap}
.wiz-step.active{color:#2563eb}
.wiz-step.active .wiz-step-num{border-color:#2563eb;background:rgba(37,99,235,.1)}
.wiz-step.done{color:#16a34a}
.wiz-step.done .wiz-step-num{border-color:#16a34a;background:rgba(22,163,74,.1)}
.wiz-step-line{flex:1;height:1px;background:var(--border-light);min-width:20px}
.wiz-step-line.done{background:#16a34a}

/* ── 섹션 ── */
.wiz-section{background:var(--bg-secondary);border:0.5px solid var(--border-light);border-radius:12px;padding:20px;margin-bottom:12px}
.wiz-section-title{font-size:.82rem;font-weight:600;color:var(--text-secondary);margin-bottom:14px;padding-bottom:8px;border-bottom:0.5px solid var(--border-light)}
.opts-grid-2{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.field-label{font-size:.72rem;color:var(--text-tertiary);font-weight:500;margin-bottom:5px}
.field-input{width:100%;border:0.5px solid var(--border-mid);border-radius:7px;padding:8px 11px;font-size:.82rem;background:var(--bg-primary);color:var(--text-primary);font-family:var(--font);box-sizing:border-box}
.field-input:focus{outline:none;border-color:#2563eb}
.field-desc{font-size:.68rem;color:var(--text-tertiary);margin-top:4px}
.strat-guide{background:var(--bg-primary);border:0.5px solid var(--border-light);border-radius:8px;padding:14px;display:flex;flex-direction:column;gap:10px}
.strat-guide-title{font-size:.68rem;font-weight:700;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.05em}
.strat-row{display:flex;align-items:center;gap:10px}
.strat-desc{font-size:.75rem;color:var(--text-secondary)}
.strat-badge{font-size:.68rem;font-weight:700;padding:2px 9px;border-radius:99px;flex-shrink:0}
.strat-badge.append{background:rgba(22,163,74,.1);color:#15803d}
.strat-badge.upsert{background:rgba(249,115,22,.1);color:#c2410c}
.strat-badge.full{background:rgba(139,92,246,.1);color:#6d28d9}
.strat-badge.sm{font-size:.62rem;padding:1px 7px}

/* ── 테이블 검색/필터 ── */
.tbl-search{padding:5px 10px;border:0.5px solid var(--border-mid);border-radius:6px;font-size:.78rem;background:var(--bg-primary);color:var(--text-primary);font-family:var(--font);width:160px}
.tbl-search:focus{outline:none;border-color:#2563eb}
.filter-tabs{display:flex;gap:3px}
.ftab{padding:4px 10px;border:0.5px solid var(--border-light);border-radius:99px;background:var(--bg-primary);font-size:.72rem;color:var(--text-tertiary);cursor:pointer;display:flex;align-items:center;gap:4px;font-family:var(--font)}
.ftab:hover{border-color:var(--border-mid);color:var(--text-secondary)}
.ftab.active{background:#2563eb;color:#fff;border-color:#2563eb}
.ftab-cnt{font-size:.65rem;opacity:.8}

/* ── 로딩/빈상태 ── */
.scan-loading{display:flex;align-items:center;justify-content:center;gap:10px;padding:40px;font-size:.82rem;color:var(--text-tertiary)}
.scan-spin{width:18px;height:18px;border:2px solid var(--border-mid);border-top-color:#2563eb;border-radius:50%;animation:spin .7s linear infinite;flex-shrink:0}
.scan-empty{padding:32px;text-align:center}
.tbl-no-result{padding:20px;text-align:center;font-size:.8rem;color:var(--text-tertiary)}
.tg-no{padding:6px 4px;font-size:.68rem;color:var(--text-tertiary);text-align:center;display:flex;align-items:center;justify-content:center}
.tg-sortable{cursor:pointer;user-select:none}
.tg-sortable:hover{color:var(--text-primary)}
.sort-icon{font-size:.65rem;opacity:.6;margin-left:2px}
.tbl-toolbar{display:flex;flex-direction:column;margin-bottom:10px}
.tbl-toolbar-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.tbl-toolbar-right{margin-left:auto;display:flex;align-items:center;gap:7px;flex-shrink:0}
.group-filter-wrap{display:flex;align-items:center;gap:5px;padding:3px 8px 3px 6px;border:0.5px solid var(--border-light);border-radius:6px;background:var(--bg-secondary)}
.group-filter-label{font-size:.72rem;font-weight:600;color:var(--text-tertiary);white-space:nowrap}
.group-filter-sel{padding:2px 4px;border:none;border-radius:4px;font-size:.75rem;background:transparent;color:var(--text-secondary);cursor:pointer;font-family:var(--font);outline:none}
.group-filter-sel:focus{color:var(--text-primary)}
.tbl-result-info{font-size:.72rem;color:var(--text-tertiary);white-space:nowrap}
.tbl-result-info b{color:var(--text-primary);font-weight:600}
@keyframes spin{to{transform:rotate(360deg)}}

/* ── 그리드 ── */
.tbl-grid{border:0.5px solid var(--border-light);border-radius:10px;overflow:hidden;margin-top:4px}
.tbl-grid-hdr{display:grid;grid-template-columns:32px 36px 2fr 70px 1.8fr 1.2fr .8fr .85fr 28px;gap:0;background:var(--bg-primary);border-bottom:0.5px solid var(--border-light)}
.tbl-grid-hdr>div{padding:7px 10px;font-size:.65rem;font-weight:700;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.04em}
.tbl-grid-row{display:grid;grid-template-columns:32px 36px 2fr 70px 1.8fr 1.2fr .8fr .85fr 28px;gap:0;border-bottom:0.5px solid var(--border-light);align-items:center;cursor:pointer;transition:background .1s;min-height:38px}
.tbl-grid-row:last-of-type{border-bottom:none}
.tbl-grid-row:hover{background:var(--bg-secondary)}
.tbl-grid-row.row-expanded{background:var(--bg-secondary)}
.tbl-grid-row.row-excluded{opacity:.5}
.tg-chk{display:flex;align-items:center;justify-content:center;padding:0 6px}
.tg-name,.tg-where,.tg-strat,.tg-sync{padding:6px 10px;font-size:.78rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:flex;align-items:center;gap:5px}
.tg-ts{padding:6px 8px;font-size:.78rem;display:flex;flex-direction:column;align-items:flex-start;gap:2px;overflow:hidden}
.tg-chevron{display:flex;align-items:center;justify-content:center;padding:0 6px;color:var(--text-tertiary);transition:transform .18s}
.tg-chevron.open{transform:rotate(180deg)}

/* ── 행 내 요소 ── */
.row-tbl-name{font-weight:600;color:var(--text-primary);font-size:.8rem}
.excluded-name{color:var(--text-tertiary);text-decoration:line-through}
.no-pk-badge{font-size:.62rem;padding:1px 5px;border-radius:3px;background:rgba(239,68,68,.1);color:#dc2626;flex-shrink:0}
.saved-badge{font-size:.62rem;padding:1px 5px;border-radius:3px;background:rgba(22,163,74,.1);color:#15803d;flex-shrink:0}
.ts-pill{display:inline-block;padding:2px 7px;border-radius:99px;font-size:.7rem;font-weight:600;font-family:var(--font-mono,monospace)}
.ts-pill.auto{background:#E6F1FB;color:#0C447C}
.ts-pill.user{background:#EAF3DE;color:#27500A}
.ts-pill.none{background:#F1EFE8;color:#5F5E5A}
.where-text{font-family:var(--font-mono,monospace);font-size:.72rem;color:var(--text-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.strat-sel-inline{padding:3px 6px;border:0.5px solid var(--border-mid);border-radius:5px;font-size:.72rem;font-weight:600;background:var(--bg-primary);cursor:pointer;color:var(--text-primary);font-family:var(--font)}
.strat-sel-inline.append{color:#15803d}
.strat-sel-inline.upsert{color:#c2410c}
.strat-sel-inline.full{color:#6d28d9}
.sync-ts-text{font-size:.7rem;color:var(--text-tertiary)}
.reset-btn{background:none;border:none;cursor:pointer;font-size:.75rem;color:var(--text-tertiary);padding:0 2px}
.reset-btn:hover{color:#2563eb}

/* ── 펼침 패널 ── */
.expand-panel{background:var(--bg-primary);border-bottom:0.5px solid var(--border-light);padding:14px 16px;display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap}
.exp-excluded{font-size:.78rem;color:var(--text-secondary);padding:8px;flex:1}
.exp-field{display:flex;flex-direction:column;gap:5px}
.exp-label{font-size:.65rem;font-weight:700;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.04em}
.exp-input{padding:6px 9px;border:0.5px solid var(--border-mid);border-radius:6px;font-size:.78rem;background:var(--bg-secondary);color:var(--text-primary)}
.exp-input:focus{outline:none;border-color:#2563eb}
.exp-input.mono{font-family:var(--font-mono,monospace)}
.exp-input:disabled{opacity:.5;cursor:not-allowed}
.exp-hint{font-size:.68rem;color:var(--text-tertiary);line-height:1.5}
.exp-hint.warn{color:#d97706}
.exp-select{padding:6px 8px;border:0.5px solid var(--border-mid);border-radius:6px;font-size:.78rem;font-weight:600;background:var(--bg-secondary);color:var(--text-primary)}
.exp-select.append{color:#15803d}
.exp-select.upsert{color:#c2410c}
.exp-select.full{color:#6d28d9}
.cand-btns{display:flex;gap:4px;flex-wrap:wrap;margin-top:3px}
.cand-btn{padding:2px 8px;border:0.5px solid var(--border-light);border-radius:99px;font-size:.68rem;font-family:var(--font-mono,monospace);background:var(--bg-secondary);cursor:pointer;color:var(--text-secondary)}
.cand-btn:hover{border-color:#2563eb;color:#2563eb}
.cand-btn.active{background:#2563eb;color:#fff;border-color:#2563eb}
.auto-tag{font-size:.62rem;padding:1px 5px;border-radius:3px;background:#E6F1FB;color:#0C447C;margin-left:3px;font-family:var(--font);font-weight:400;text-transform:none;letter-spacing:0}
.exp-actions{display:flex;gap:6px;align-items:flex-end;padding-top:14px}
.btn-row-save{padding:5px 14px;border-radius:6px;background:#2563eb;color:#fff;border:none;font-size:.78rem;cursor:pointer;font-family:var(--font)}
.btn-row-save:hover{background:#1d4ed8}
.btn-row-reset{padding:5px 10px;border-radius:6px;border:0.5px solid var(--border-mid);background:var(--bg-secondary);font-size:.78rem;cursor:pointer;color:var(--text-secondary);font-family:var(--font)}

/* ── 페이징 ── */
.tbl-paging{display:flex;align-items:center;justify-content:space-between;margin-top:10px;font-size:.75rem;color:var(--text-tertiary);flex-wrap:wrap;gap:8px}
.page-info-label{font-size:.72rem;color:var(--text-tertiary)}
.page-info{font-size:.72rem;color:var(--text-tertiary)}
.page-size-sel{padding:3px 6px;border:0.5px solid var(--border-mid);border-radius:5px;font-size:.75rem;background:var(--bg-secondary);color:var(--text-secondary);cursor:pointer;font-family:var(--font)}
.page-btns{display:flex;gap:3px}
.pg-btn{width:28px;height:28px;border:0.5px solid var(--border-light);border-radius:6px;background:var(--bg-secondary);cursor:pointer;font-size:.75rem;color:var(--text-secondary);display:flex;align-items:center;justify-content:center;font-family:var(--font)}
.pg-btn:hover{background:var(--bg-primary)}
.pg-btn:disabled{opacity:.4;cursor:not-allowed}
.pg-btn.active{background:#2563eb;color:#fff;border-color:#2563eb}
.pg-ellipsis{width:24px;height:28px;display:flex;align-items:center;justify-content:center;font-size:.75rem;color:var(--text-tertiary)}

/* ── 확인 화면 ── */
.confirm-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px}
.confirm-block{background:var(--bg-primary);border:0.5px solid var(--border-light);border-radius:8px;padding:12px 14px}
.confirm-label{font-size:.65rem;color:var(--text-tertiary);font-weight:700;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px}
.confirm-val{font-size:.82rem;color:var(--text-primary);font-weight:500;display:flex;align-items:center;gap:6px}
.confirm-tbl-wrap{background:var(--bg-primary);border:0.5px solid var(--border-light);border-radius:8px;overflow:hidden}
.confirm-tbl-hdr{display:grid;grid-template-columns:1.4fr 1fr 1.6fr .7fr;gap:8px;padding:7px 14px;background:var(--bg-secondary);font-size:.65rem;font-weight:700;color:var(--text-tertiary);text-transform:uppercase}
.confirm-tbl-row{display:grid;grid-template-columns:1.4fr 1fr 1.6fr .7fr;gap:8px;padding:7px 14px;border-top:0.5px solid var(--border-light);font-size:.75rem;align-items:center}
.mono{font-family:var(--font-mono,monospace)}

/* ── 네비 ── */
.wiz-nav{display:flex;justify-content:space-between;align-items:center;padding:14px 0 0;border-top:0.5px solid var(--border-light);margin-top:4px}

/* ── 목록 카드 ── */
.cdc-empty{display:flex;flex-direction:column;align-items:center;padding:60px 20px}
.cdc-cards{display:flex;flex-direction:column;gap:10px}
.cdc-cfg-card{padding:16px}
.cdc-running{border-color:rgba(59,130,246,.3) !important}
.cdc-cfg-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.cdc-cfg-name{display:flex;align-items:center;gap:7px;font-size:.88rem;font-weight:600;color:var(--text-primary)}
.run-badge{display:inline-flex;align-items:center;gap:4px;font-size:.65rem;font-weight:700;padding:2px 8px;border-radius:99px;background:rgba(59,130,246,.1);color:#2563eb}
.run-dot{width:5px;height:5px;border-radius:50%;background:#2563eb;animation:pulse 1.2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.cdc-cfg-btns{display:flex;align-items:center;gap:6px}
.icon-btn{width:28px;height:28px;border-radius:6px;border:0.5px solid var(--border-mid);background:var(--bg-secondary);cursor:pointer;display:flex;align-items:center;justify-content:center;color:var(--text-tertiary);transition:all .12s}
.icon-btn:hover{background:var(--bg-primary);color:var(--text-secondary)}
.icon-btn.danger:hover{color:#ef4444;border-color:rgba(239,68,68,.3)}
.cdc-cfg-conn{display:flex;align-items:center;gap:7px;margin-bottom:8px}
.db-pill{font-size:.62rem;font-weight:800;padding:2px 7px;border-radius:4px;flex-shrink:0}
.db-pill.src{background:rgba(59,130,246,.1);color:#1d4ed8}
.db-pill.tgt{background:rgba(22,163,74,.1);color:#15803d}
.db-pill.sm{font-size:.58rem;padding:1px 5px}
.conn-host{font-size:.75rem;color:var(--text-secondary);font-family:monospace}
.cdc-tbl-summary{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:8px}
.tbl-chip{display:inline-flex;align-items:center;gap:4px;font-size:.7rem;padding:2px 8px;border-radius:5px;background:var(--bg-primary);border:0.5px solid var(--border-light);color:var(--text-secondary)}
.tbl-chip.more{color:var(--text-tertiary)}
.strat-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.strat-dot.append{background:#16a34a}
.strat-dot.upsert{background:#f97316}
.strat-dot.full{background:#8b5cf6}
.cdc-result-bar{display:flex;flex-wrap:wrap;gap:5px;padding-top:8px;border-top:0.5px solid var(--border-light);align-items:center}
.res-chip{font-size:.7rem;padding:2px 8px;border-radius:5px;display:flex;align-items:center;gap:4px}
.res-chip.done{background:rgba(22,163,74,.08);color:#15803d}
.res-chip.error{background:rgba(239,68,68,.08);color:#dc2626}
.res-chip.running{background:rgba(59,130,246,.08);color:#2563eb}
.cdc-sync-row{display:flex;flex-wrap:wrap;gap:10px;padding-top:6px;border-top:0.5px solid var(--border-light)}
.sync-item{display:flex;align-items:center;gap:5px;font-size:.7rem}
.sync-tbl{color:var(--text-tertiary)}
.sync-ts{color:var(--text-secondary);font-weight:500}
.cdc-list-wrap{display:flex;flex-direction:column}

/* ── 공통 버튼 ── */
.btn{padding:7px 16px;border-radius:7px;border:0.5px solid var(--border-mid);background:var(--bg-secondary);color:var(--text-secondary);font-size:.8rem;font-family:var(--font);cursor:pointer;transition:all .12s;display:inline-flex;align-items:center;gap:5px}
.btn:hover{background:var(--bg-primary)}
.btn-primary{background:#2563eb;color:#fff;border-color:#2563eb}
.btn-primary:hover{background:#1d4ed8}
.btn-primary:disabled{opacity:.5;cursor:not-allowed}
.btn-sm{padding:5px 12px;font-size:.75rem}
.mini-spin{width:11px;height:11px;border:2px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:spin .7s linear infinite;display:inline-block;flex-shrink:0}
.info-box{display:flex;gap:8px;padding:10px 12px;border-radius:8px;background:rgba(37,99,235,.05);border:0.5px solid rgba(37,99,235,.15)}
.info-box code{background:var(--bg-secondary);padding:1px 5px;border-radius:3px;font-family:monospace;font-size:.72rem}

/* ── 건수 컬럼 ── */
.tg-cnt{padding:6px 10px;font-size:.78rem;display:flex;align-items:center}
.cnt-text{font-family:var(--font-mono,monospace);font-size:.75rem;color:var(--text-secondary)}
.cnt-loading{color:var(--text-tertiary);font-size:.72rem}

/* ── 기준일자 ── */
.base-date-row{display:flex;align-items:center;gap:4px;margin-top:3px}
.base-date-label{font-size:.65rem;color:var(--text-tertiary);white-space:nowrap;flex-shrink:0;font-weight:500}
.base-date-input{padding:2px 6px;border:0.5px solid var(--border-light);border-radius:4px;font-size:.65rem;font-family:var(--font-mono,monospace);background:var(--bg-secondary);color:var(--text-secondary);width:100%;min-width:140px;max-width:200px}
.base-date-input::placeholder{color:var(--text-tertiary);font-style:italic}
.base-date-badge{font-size:.62rem;color:#d97706;background:rgba(217,119,6,.08);border:0.5px solid rgba(217,119,6,.3);border-radius:3px;padding:1px 5px;white-space:nowrap;margin-top:2px}
.base-date-input:focus{outline:none;border-color:#2563eb}

/* ── 컬럼 피커 ── */
.col-picker-wrap{position:relative;display:flex;align-items:center}
.col-picker-wrap .exp-input{padding-right:24px;cursor:pointer}
.col-picker-clear{position:absolute;right:6px;background:none;border:none;cursor:pointer;color:var(--text-tertiary);padding:0 3px;line-height:1;display:flex;align-items:center}
.col-picker-clear:hover{color:#ef4444}
.gt-sign{font-size:.9rem;font-weight:700;color:#2563eb;opacity:.7;flex-shrink:0;font-family:var(--font-mono,monospace)}
.btn-row-test{padding:5px 10px;border-radius:6px;border:0.5px solid var(--border-mid);background:var(--bg-secondary);font-size:.75rem;cursor:pointer;color:var(--text-secondary);font-family:var(--font);display:inline-flex;align-items:center;gap:4px}
.btn-row-test:hover{border-color:#2563eb;color:#2563eb}
.test-query-panel{margin-top:10px;border:0.5px solid var(--border-mid);border-radius:8px;overflow:hidden;width:100%}
.test-query-hdr{display:flex;align-items:center;gap:8px;padding:6px 10px;background:var(--bg-secondary);font-size:.72rem;font-weight:600;color:var(--text-secondary)}
.test-query-hdr span{flex:1}
.tq-copy{padding:2px 8px;border:0.5px solid var(--border-mid);border-radius:4px;background:var(--bg-primary);font-size:.68rem;cursor:pointer;color:var(--text-secondary);font-family:var(--font)}
.tq-copy:hover{border-color:#2563eb;color:#2563eb}
.tq-close{background:none;border:none;cursor:pointer;font-size:.8rem;color:var(--text-tertiary);padding:0 4px}
.tq-tabs{display:flex;align-items:center;gap:2px;padding:6px 8px;background:var(--bg-secondary);border-bottom:0.5px solid var(--border-light)}
.tq-tab{padding:4px 12px;border:0.5px solid var(--border-light);border-radius:5px;background:var(--bg-primary);font-size:.72rem;cursor:pointer;color:var(--text-tertiary);font-family:var(--font);font-weight:500}
.tq-tab:hover{color:var(--text-secondary)}
.tq-tab.active{background:#2563eb;color:#fff;border-color:#2563eb}
.test-query-body{margin:0;padding:10px 12px;font-size:.72rem;font-family:var(--font-mono,monospace);color:var(--text-primary);background:var(--bg-primary);white-space:pre-wrap;word-break:break-all;line-height:1.6;max-height:200px;overflow-y:auto}
.test-query-note{padding:6px 10px;font-size:.7rem;color:#d97706;background:rgba(217,119,6,.06);border-top:0.5px solid var(--border-light)}
.col-dropdown{position:absolute;top:calc(100% + 4px);left:0;z-index:999;
  background:var(--bg-primary);border:0.5px solid var(--border-mid);
  border-radius:8px;box-shadow:0 4px 20px rgba(0,0,0,.12);
  width:260px;display:flex;flex-direction:column;overflow:hidden}
.col-search{padding:7px 10px;border:none;border-bottom:0.5px solid var(--border-light);
  font-size:.78rem;font-family:var(--font-mono,monospace);background:var(--bg-secondary);
  color:var(--text-primary);outline:none}
.col-dropdown-list{max-height:200px;overflow-y:auto}
.col-option{display:flex;align-items:center;gap:6px;padding:6px 10px;cursor:pointer;
  font-size:.75rem;transition:background .1s}
.col-option:hover{background:var(--bg-secondary)}
.col-option.active{background:rgba(37,99,235,.08)}
.col-option.recommended{border-left:2px solid #2563eb}
.col-opt-name{font-family:var(--font-mono,monospace);font-weight:600;color:var(--text-primary);flex:1}
.col-opt-type{font-size:.65rem;color:var(--text-tertiary);flex-shrink:0}
.col-opt-rec{font-size:.6rem;padding:1px 5px;border-radius:3px;background:#E6F1FB;color:#0C447C;flex-shrink:0}
.col-option-empty{padding:12px;text-align:center;font-size:.75rem;color:var(--text-tertiary)}

/* ── 목록 카드 개선 ── */
.cfg-title{font-size:.88rem;font-weight:600;color:var(--text-primary)}
.conn-host-sm{font-size:.75rem;color:var(--text-secondary);font-family:monospace}
.tbl-count-badge{font-size:.68rem;padding:2px 7px;border-radius:99px;background:var(--bg-secondary);border:0.5px solid var(--border-light);color:var(--text-tertiary)}
.cdc-expanded{border-color:rgba(37,99,235,.25) !important}
.cdc-editing{border:2px solid #2563eb !important;box-shadow:0 0 0 3px rgba(37,99,235,.08) !important}
.cdc-editing .cdc-cfg-top{background:rgba(37,99,235,.04)}
@keyframes edit-pulse{0%,100%{opacity:1}50%{opacity:.7}}

/* ── 펼침 상세 ── */
.cfg-detail{border-top:0.5px solid var(--border-light);padding-top:12px;margin-top:10px}
.result-summary{font-size:.75rem;color:#15803d;font-weight:600}
.detail-grid{border:0.5px solid var(--border-light);border-radius:8px;overflow:hidden}
.detail-hdr{display:grid;grid-template-columns:2fr 1fr 1.5fr .7fr 1.1fr 1fr .8fr;gap:0;
  padding:6px 12px;background:var(--bg-secondary);border-bottom:0.5px solid var(--border-light);
  font-size:.65rem;font-weight:700;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.04em}
.detail-row{display:grid;grid-template-columns:2fr 1fr 1.5fr .7fr 1.1fr 1fr .8fr;gap:0;
  padding:7px 12px;border-bottom:0.5px solid var(--border-light);align-items:center;font-size:.75rem}
.detail-row:last-child{border-bottom:none}
.detail-row:hover{background:var(--bg-secondary)}
.detail-tbl{font-weight:600;color:var(--text-primary);font-size:.78rem}
.detail-mono{font-family:var(--font-mono,monospace);font-size:.72rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.detail-sync{font-size:.72rem;color:var(--text-tertiary)}
.detail-empty{font-size:.72rem;color:var(--text-tertiary)}

/* ── 인라인 편집 패널 ── */
.cdc-schedule-panel{border-top:2px solid #7c3aed;background:rgba(124,58,237,.03);padding:12px 16px}
.sch-panel-hdr{display:flex;align-items:center;gap:7px;font-size:.78rem;font-weight:600;color:var(--text-secondary);margin-bottom:12px}
.sch-panel-body{display:flex;flex-direction:column;gap:12px}
.sch-field-row{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start}
.sch-field{display:flex;flex-direction:column;gap:4px;min-width:160px}
.sch-label{font-size:.7rem;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.04em}
.sch-type-btns{display:flex;gap:4px}
.sch-type-btn{padding:4px 10px;border:0.5px solid var(--border-mid);border-radius:5px;background:var(--bg-secondary);font-size:.72rem;cursor:pointer;color:var(--text-secondary);font-family:var(--font)}
.sch-type-btn.active{background:#7c3aed;color:#fff;border-color:#7c3aed}
.sch-input{padding:4px 8px;border:0.5px solid var(--border-mid);border-radius:5px;font-size:.75rem;font-family:var(--font);background:var(--bg-secondary);color:var(--text-primary);width:100%}
.sch-input:focus{outline:none;border-color:#7c3aed}
.sch-input.mono{font-family:var(--font-mono,monospace)}
.sch-hint{font-size:.67rem;color:var(--text-tertiary)}
.sch-cron-ex{color:#7c3aed;cursor:pointer;margin-left:4px;text-decoration:underline;font-size:.67rem}
.sch-actions{display:flex;justify-content:flex-end;gap:8px;padding-top:4px;border-top:0.5px solid var(--border-light)}
.sch-active-badge{font-size:.68rem;padding:2px 7px;border-radius:4px;background:rgba(124,58,237,.1);color:#7c3aed;font-weight:600}
.btn-sch-del{padding:3px 8px;border:0.5px solid var(--border-danger,#fca5a5);border-radius:5px;background:transparent;font-size:.7rem;color:var(--text-danger,#dc2626);cursor:pointer;font-family:var(--font)}
.btn-sch-del:hover{background:rgba(220,38,38,.06)}
.icon-btn.active{color:#7c3aed;border-color:#7c3aed;background:rgba(124,58,237,.08)}
.edit-badge{font-size:.7rem;font-weight:700;padding:3px 8px;border-radius:4px;background:#2563eb;color:#fff;margin-left:8px;letter-spacing:.02em;animation:edit-pulse 2s ease-in-out infinite}
.cfg-inline-edit{border-top:2px solid #2563eb;margin-top:0;padding-top:0}
.inline-wiz-hdr{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:var(--bg-secondary);border-bottom:0.5px solid var(--border-light)}
.inline-wiz-steps{display:flex;align-items:center;gap:0}
.iwiz-step{display:flex;align-items:center;gap:5px;padding:5px 8px;border:none;background:none;cursor:default;color:var(--text-tertiary);font-size:.75rem;font-family:var(--font)}
.iwiz-step.reachable{cursor:pointer}
.iwiz-step.active{color:#2563eb}
.iwiz-step.done{color:#16a34a}
.iwiz-num{width:18px;height:18px;border-radius:50%;border:1.5px solid var(--border-mid);background:var(--bg-secondary);display:flex;align-items:center;justify-content:center;font-size:.65rem;font-weight:700;flex-shrink:0}
.iwiz-step.active .iwiz-num{border-color:#2563eb;background:rgba(37,99,235,.1)}
.iwiz-step.done .iwiz-num{border-color:#16a34a;background:rgba(22,163,74,.1)}
.iwiz-lbl{font-size:.72rem;font-weight:500;white-space:nowrap}
.iwiz-line{flex:none;width:20px;height:1px;background:var(--border-light)}
.iwiz-line.done{background:#16a34a}
.iwiz-close{background:none;border:none;cursor:pointer;font-size:.9rem;color:var(--text-tertiary);padding:4px 8px;border-radius:4px}
.iwiz-close:hover{background:var(--bg-primary);color:var(--text-secondary)}
.iwiz-body{padding:16px 14px}
.iwiz-tbl{padding:12px 14px}
.iwiz-nav{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-top:0.5px solid var(--border-light);background:var(--bg-secondary)}

/* ── 스케줄 패널 (JobWizard 동일 스타일) ── */
.sched-mode-row{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px}
.sched-mode-card{display:flex;align-items:center;gap:12px;padding:12px 14px;background:var(--bg-primary);border:1.5px solid var(--border-mid);border-radius:var(--radius-lg,10px);cursor:pointer;transition:all .15s;user-select:none}
.sched-mode-card:hover{border-color:var(--accent-blue,#2563eb);background:var(--bg-info)}
.sched-mode-card.active{border-color:var(--accent-blue,#2563eb);background:var(--bg-info);box-shadow:0 0 0 3px rgba(59,130,246,.12)}
.smc-ico{color:var(--text-tertiary);flex-shrink:0;transition:color .15s}
.sched-mode-card:hover .smc-ico,.sched-mode-card.active .smc-ico{color:var(--text-info)}
.smc-body{flex:1;min-width:0}
.smc-title{font-size:13px;font-weight:600;color:var(--text-primary)}
.smc-desc{font-size:11px;color:var(--text-tertiary);margin-top:2px}
.sched-mode-card.active .smc-title{color:var(--text-info)}
.smc-radio{width:16px;height:16px;border-radius:50%;border:1.5px solid var(--border-mid);flex-shrink:0;transition:all .15s;position:relative}
.smc-radio.on{border-color:var(--accent-blue,#2563eb);background:var(--accent-blue,#2563eb)}
.smc-radio.on::after{content:'';position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:6px;height:6px;border-radius:50%;background:#fff}
.sched-type-row{display:flex;gap:6px;margin-bottom:12px}
.stype-btn{padding:6px 14px;border-radius:var(--radius-md,6px);border:0.5px solid var(--border-mid);background:transparent;cursor:pointer;font-size:12px;font-family:var(--font);color:var(--text-secondary);transition:all .12s}
.stype-btn:hover{background:var(--bg-primary)}
.stype-btn.active{background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue,#2563eb);font-weight:500}
.sched-fields{background:var(--bg-primary);border-radius:var(--radius-md,6px);padding:14px;border:0.5px solid var(--border-light);margin-bottom:8px}
.sf-row{display:flex;align-items:flex-start;gap:12px;margin-bottom:10px;flex-wrap:wrap}
.sf-row:last-child{margin-bottom:0}
.sf-group{display:flex;flex-direction:column;gap:4px;min-width:140px}
.sched-preview{display:flex;align-items:center;gap:6px;margin-top:10px;padding:8px 12px;background:var(--bg-info);border-radius:var(--radius-md,6px);font-size:12px;color:var(--text-info)}
.cron-help{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}
.cron-ex{font-size:11px;padding:3px 8px;background:var(--bg-secondary);border-radius:4px;border:0.5px solid var(--border-mid);cursor:pointer;color:var(--text-secondary);font-family:'Consolas','SF Mono',monospace;transition:all .12s}
.cron-ex:hover{background:var(--bg-info);color:var(--text-info)}
.sel-wrap{position:relative}
.sel-wrap select{width:100%;appearance:none;-webkit-appearance:none;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:var(--radius-md,6px);padding:7px 28px 7px 10px;font-size:12.5px;color:var(--text-primary);cursor:pointer;font-family:var(--font)}
.sel-wrap select:focus{outline:none;border-color:var(--accent-blue,#2563eb)}
.chev{position:absolute;right:9px;top:50%;transform:translateY(-50%);pointer-events:none;color:var(--text-tertiary)}
.sch-n-input{width:72px;padding:6px 8px;border:0.5px solid var(--border-mid);border-radius:var(--radius-md,6px);font-size:13px;font-family:var(--font);background:var(--bg-secondary);color:var(--text-primary);text-align:center}
.sch-n-input:focus{outline:none;border-color:var(--accent-blue,#2563eb)}
.btn-success{background:#16a34a;color:#fff;border:none;padding:6px 14px;border-radius:var(--radius-md,6px);cursor:pointer;font-family:var(--font);font-size:13px;display:inline-flex;align-items:center;gap:4px}
.btn-success:hover{background:#15803d}

/* ── CDC 카드 액션 버튼 ── */
.cdc-act-btn{display:inline-flex;align-items:center;gap:5px;padding:5px 10px;border-radius:6px;font-size:.72rem;font-weight:500;cursor:pointer;font-family:var(--font);border:0.5px solid;transition:all .15s;white-space:nowrap}
.sch-btn{background:var(--bg-secondary);border-color:var(--border-mid);color:var(--text-secondary)}
.sch-btn:hover{border-color:#7c3aed;color:#7c3aed;background:rgba(124,58,237,.06)}
.sch-btn.active{background:rgba(124,58,237,.08);border-color:#7c3aed;color:#7c3aed}
.sch-dot{width:6px;height:6px;border-radius:50%;background:#7c3aed;flex-shrink:0;animation:pulse-dot 2s infinite}
@keyframes pulse-dot{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.6;transform:scale(.8)}}
.run-btn{background:#2563eb;border-color:#2563eb;color:#fff}
.run-btn:hover:not(:disabled){background:#1d4ed8;border-color:#1d4ed8}
.run-btn:disabled{opacity:.6;cursor:not-allowed}

/* ── 편집/삭제 텍스트 버튼 ── */
.cdc-txt-btn{display:inline-flex;align-items:center;gap:4px;padding:4px 9px;border-radius:5px;font-size:.72rem;font-weight:500;cursor:pointer;font-family:var(--font);border:0.5px solid;transition:all .13s;white-space:nowrap}
.edit-btn{background:var(--bg-secondary);border-color:var(--border-mid);color:var(--text-secondary)}
.edit-btn:hover{border-color:var(--accent-blue,#2563eb);color:var(--accent-blue,#2563eb);background:var(--bg-info)}
.del-btn{background:var(--bg-secondary);border-color:var(--border-mid);color:var(--text-secondary)}
.del-btn:hover{border-color:#dc2626;color:#dc2626;background:rgba(220,38,38,.06)}

/* ── 날짜+시간 커스텀 입력 ── */
.dt-input-wrap{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border:0.5px solid var(--border-mid);border-radius:6px;background:var(--bg-secondary);width:100%}
.dt-input-wrap:focus-within{border-color:var(--accent-blue,#2563eb)}
.dt-part-input{border:none;background:transparent;font-size:12.5px;font-family:var(--font);color:var(--text-primary);outline:none;min-width:0}
.dt-part-input[type="date"]{width:110px}
.dt-part-input[type="time"]{width:80px}
.dt-part-input::-webkit-calendar-picker-indicator{opacity:.4;cursor:pointer;width:12px;height:12px}
</style>
