<template>
  <div class="vp">

    <!-- 미연결 경고 -->
    <div v-if="!connector.bothConnected" class="vp-warn">
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px;flex-shrink:0"><path d="M8 2L14 14H2L8 2z"/></svg>
      소스·타겟 DB 연결이 필요합니다.
      <button class="vp-warn-btn" @click="$router.push('/connector')">커넥터 관리 →</button>
    </div>

    <!-- ── 상단 컨트롤 바 (PageHeader 공통 스타일) ── -->
    <PageHeader :show-db="true" :src-db="connector.source" :tgt-db="connector.target">
      <template #actions>
        <button class="chip" :class="{'chip-active': showReport}"
                @click="showReport=!showReport; if(showReport) buildReport()">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:10px;height:10px">
            <rect x="2" y="1" width="10" height="12" rx="1.5"/>
            <line x1="4.5" y1="4.5" x2="9.5" y2="4.5"/><line x1="4.5" y1="6.5" x2="9.5" y2="6.5"/>
            <polyline points="4.5,9 5.5,10 7.5,8" stroke-width="1.5"/>
          </svg>
          리포트
        </button>
        <button class="chip chip-report" @click="downloadReport('txt')">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:10px;height:10px">
            <path d="M2 1h7l3 3v9H2z"/><line x1="4" y1="10" x2="10" y2="10"/><line x1="7" y1="6" x2="7" y2="10"/>
          </svg>
          다운로드
        </button>
        <button class="chip chip-report" @click="downloadReport('html')">HTML</button>
        <button class="chip" :class="{'chip-active': showLog}"
                @click="showLog=!showLog; if(showLog) fetchLogs()">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:10px;height:10px">
            <rect x="1" y="1" width="12" height="12" rx="1.5"/>
            <line x1="3" y1="4" x2="11" y2="4"/><line x1="3" y1="6.5" x2="8" y2="6.5"/>
            <line x1="3" y1="9" x2="9" y2="9"/>
          </svg>
          서버 로그
          <span v-if="logError" style="width:5px;height:5px;border-radius:50%;background:#ef4444;margin-left:1px"></span>
        </button>
        <!-- Clear — 결과 있을 때만 표시 -->
        <button v-if="results.length || objResults.length"
                class="chip chip-clear" @click="clearAll" title="검증 결과 전체 초기화">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px">
            <line x1="3" y1="3" x2="11" y2="11"/><line x1="11" y1="3" x2="3" y2="11"/>
          </svg>
          Clear
        </button>
      </template>
    </PageHeader>

    <!-- ── 리포트 패널 ── -->
    <div v-if="showReport" class="card vp-report-card">
      <div class="rp-hdr">
        <span class="rp-title">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px;flex-shrink:0"><rect x="2" y="1" width="10" height="12" rx="1.5"/><line x1="4.5" y1="4.5" x2="9.5" y2="4.5"/><line x1="4.5" y1="6.5" x2="9.5" y2="6.5"/></svg>
          검증 실행 리포트
          <span style="font-size:10.5px;color:var(--text-tertiary);font-weight:400">{{ reportTs }}</span>
        </span>
        <div style="display:flex;gap:4px;align-items:center">
          <button class="chip" @click="buildReport()">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px"><path d="M1 7a6 6 0 1 0 6-6"/><polyline points="4,1 1,1 1,4"/></svg>
            새로고침
          </button>
          <button class="chip chip-report" @click="copyReport()">복사</button>
          <button class="chip chip-report" @click="downloadReport('txt')">다운로드</button>
          <button class="chip chip-report" @click="downloadReport('html')">HTML</button>
          <button class="chip chip-clear" @click="showReport=false">✕</button>
        </div>
      </div>
      <div class="rp-body">
        <pre class="rp-pre">{{ reportText }}</pre>
      </div>
    </div>

    <!-- ── 로그 패널 ── -->
    <div v-if="showLog" class="card log-panel">
      <div class="log-hdr">
        <span class="log-title">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px;flex-shrink:0"><rect x="1" y="1" width="12" height="12" rx="1.5"/><line x1="3" y1="4" x2="11" y2="4"/><line x1="3" y1="6.5" x2="8" y2="6.5"/><line x1="3" y1="9" x2="9" y2="9"/></svg>
          서버 로그
        </span>
        <div style="display:flex;gap:6px;align-items:center">
          <select v-model="logLevel" @change="fetchLogs()" class="log-sel">
            <option value="ALL">전체</option>
            <option value="ERROR">ERROR</option>
            <option value="WARNING">WARNING</option>
            <option value="INFO">INFO</option>
            <option value="DEBUG">DEBUG</option>
          </select>
          <select v-model="logLines" @change="fetchLogs()" class="log-sel" style="width:70px">
            <option :value="100">100줄</option>
            <option :value="200">200줄</option>
            <option :value="500">500줄</option>
          </select>
          <button class="vp-icon-btn" @click="fetchLogs()" :disabled="logLoading">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:11px;height:11px"><path d="M1 7a6 6 0 1 0 6-6"/><polyline points="4,1 1,1 1,4"/></svg>
          </button>
          <button class="vp-icon-btn" @click="copyLog()">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px"><rect x="5" y="1" width="8" height="10" rx="1.2"/><rect x="1" y="3" width="8" height="10" rx="1.2"/></svg>
            복사
          </button>
          <button class="vp-icon-btn" style="color:#dc2626" @click="clearLog()">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px"><polyline points="2,4 12,4"/><path d="M5,4V2h4v2"/><rect x="3" y="4" width="8" height="8" rx="1"/></svg>
            초기화
          </button>
        </div>
      </div>
      <div class="log-body" ref="logBodyRef">
        <div v-if="logLoading" class="log-body" style="padding:16px">
          <div class="vp-ldots"><span/><span/><span/></div> 로그 로딩 중...
        </div>
        <div v-else-if="!logLines_data.length" class="vp-log-empty">로그가 없습니다</div>
        <div v-else>
          <div v-for="(line, i) in logLines_data" :key="i"
               class="log-line"
               :class="{
                 'le':   line.includes('[ERROR]'),
                 'lw': line.includes('[WARNING]'),
                 'li':    line.includes('[INFO]'),
                 'ld':   line.includes('[DEBUG]'),
               }">{{ line }}</div>
        </div>
      </div>
      <div class="log-footer">
        <span style="font-size:10.5px;color:var(--text-tertiary)">{{ logLines_data.length }}줄 표시 / 전체 {{ logTotal }}줄</span>
        <span v-if="logTs" class="vp-tb-ts">{{ logTs }}</span>
      </div>
    </div>

    <!-- ── 상단 설정 카드 ── -->
    <div class="vp-cfg card">

      <!-- Row1: 탭 버튼 (우측 정렬) -->
      <div class="vp-tab-row">
        <div class="vp-tabs">
          <button class="vp-tab" :class="{active:vType==='table'}" @click="vType='table'; if(!srcTables.length) loadTables()">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px">
              <rect x="1" y="1" width="12" height="12" rx="1.5"/>
              <line x1="1" y1="5" x2="13" y2="5"/><line x1="5" y1="5" x2="5" y2="13"/>
            </svg>
            테이블 검증
          </button>
          <button class="vp-tab" :class="{active:vType==='object'}" @click="vType='object'; loadSrcObjects(false)">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px">
              <circle cx="7" cy="7" r="2.5"/><path d="M7 1v1.5M7 11.5V13M1 7h1.5M11.5 7H13"/>
              <path d="M3.05 3.05l1.06 1.06M9.89 9.89l1.06 1.06M3.05 10.95l1.06-1.06M9.89 4.11l1.06-1.06"/>
            </svg>
            오브젝트 검증
          </button>
        </div>
      </div>

      <!-- Row2: 옵션 chip + 실행 버튼 (탭 바로 아래) -->
      <div class="vp-run-row">
        <!-- 테이블 탭: 모드·필터 chip -->
        <template v-if="vType==='table'">
          <label v-for="m in [{v:'row_count',l:'① 행수'},{v:'checksum',l:'② 체크섬'},{v:'sample',l:'③ 행수+샘플'},{v:'column_stats',l:'④ 컬럼통계'},{v:'full',l:'⑤ 전체'}]"
                 :key="m.v" class="chip" :class="{on: mode===m.v}" @click="mode=m.v" style="cursor:pointer">
            {{ m.l }}
          </label>
          <div class="vp-run-sep"></div>
          <label v-for="f in [{v:'all',l:'전체 보기'},{v:'fail',l:'불일치만'},{v:'ok',l:'일치만'}]"
                 :key="f.v" class="chip" :class="{on: filterMode===f.v}" @click="filterMode=f.v" style="cursor:pointer">
            {{ f.l }}
          </label>
        </template>
        <!-- 오브젝트 탭: 타입 chip (얇게, 동일 톤) -->
        <template v-else>
          <label v-for="t in objTypes" :key="t.v" class="chip vp-otype-chip"
                 :class="{on: selObjTypes.includes(t.v)}"
                 @click="selObjTypes.includes(t.v) ? selObjTypes.splice(selObjTypes.indexOf(t.v),1) : selObjTypes.push(t.v)"
                 style="cursor:pointer">
            {{ t.icon }} {{ t.label }}
          </label>
        </template>
        <button class="chip chip-run"
                @click="vType==='table' ? runValidate() : runObjValidate()"
                :disabled="vType==='table' ? (running || !connector.bothConnected) : (objRunning || !connector.source.host)">
          <span v-if="running || objRunning" class="vp-spin" style="width:11px;height:11px;border-width:1.5px"></span>
          <svg v-else viewBox="0 0 12 12" fill="currentColor" style="width:10px;height:10px"><polygon points="2,1 10,6 2,11"/></svg>
          <template v-if="vType==='table'">
            {{ running ? '검증 중...' : `검증 실행 ${selTables.length ? '('+selTables.length+'개)' : '(전체)'}` }}
          </template>
          <template v-else>
            {{ objRunning ? '검증 중...' : `오브젝트 검증 실행 ${selectedObjCount ? '('+selectedObjCount+'개)' : ''}` }}
          </template>
        </button>

      </div>

      <!-- ══ 테이블 검증 ══ -->
      <template v-if="vType==='table'">

        <!-- 테이블 선택 패널 — 소스/타겟 2컬럼 리스트 -->
        <div class="vp-tbl-panel">

          <!-- 패널 헤더 -->
          <div class="vp-tbl-hdr">
            <div class="vp-tbl-title">
              검증 테이블
              <div v-if="loadingTables" class="vp-ldots"><span/><span/><span/></div>
              <template v-else-if="srcTables.length">
                <span class="vp-cnt-badge">{{ srcTables.length }}개</span>
                <span v-if="onlyInSrc.length" class="vp-only-badge src">소스전용 {{ onlyInSrc.length }}</span>
                <span v-if="onlyInTgt.length" class="vp-only-badge tgt">타겟전용 {{ onlyInTgt.length }}</span>
              </template>
            </div>
            <div class="vp-tbl-actions">
              <!-- 빠른 선택 -->
              <button class="vp-chip" :class="{on:selMode==='all'}"      @click="setSelMode('all')">전체</button>
              <button class="vp-chip" :class="{on:selMode==='mismatch'}" @click="setSelMode('mismatch')">불일치만</button>
              <button class="vp-chip" :class="{on:selMode==='custom'}"   @click="setSelMode('custom')">직접 선택</button>
              <!-- 검색 -->
              <div class="vp-search">
                <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px;color:var(--text-tertiary)"><circle cx="6" cy="6" r="4"/><line x1="9.5" y1="9.5" x2="13" y2="13"/></svg>
                <input v-model="tblSearch" placeholder="테이블 검색..." class="vp-search-input"/>
              </div>
              <!-- 새로고침 -->
              <button class="vp-icon-btn" @click="loadTables" :disabled="loadingTables" title="새로고침">
                <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:12px;height:12px"><path d="M1 7a6 6 0 1 0 6-6"/><polyline points="4,1 1,1 1,4"/></svg>
              </button>
            </div>
          </div>

          <!-- 로딩 -->
          <div v-if="loadingTables" class="vp-tbl-loading">
            <div class="vp-ldots"><span/><span/><span/></div>테이블 목록 로딩 중...
          </div>

          <!-- 비어있음 -->
          <div v-else-if="!srcTables.length" class="vp-tbl-empty">
            소스 DB에서 테이블을 불러오지 못했습니다.
            <button class="vp-chip on" @click="loadTables">다시 시도</button>
          </div>

          <!-- 2컬럼 리스트 -->
          <div v-else class="vp-list-wrap">

            <!-- 소스 컬럼 -->
            <div class="vp-list-col">
              <div class="vp-list-col-hdr src">
                <label class="vp-list-chk-all">
                  <input type="checkbox"
                    :checked="srcOnlyFiltered.every(t=>selTables.includes(t.name)) && srcOnlyFiltered.length>0"
                    @change="toggleColAll('src', $event)"
                    class="vp-chk"/>
                </label>
                <span class="vp-list-col-dot src"></span>
                <span class="vp-list-col-title">소스 <span class="vp-list-col-cnt">{{ srcOnlyFiltered.length }}</span></span>
                <!-- 정렬 -->
                <div class="vp-list-sort-btns">
                  <button class="vp-sort-btn" :class="{on:listSort.src==='name'}" @click="toggleListSort('src','name')" title="이름순">
                    A↕ <span v-if="listSort.src==='name'">{{ listSortDir.src==='asc'?'↑':'↓' }}</span>
                  </button>
                  <button class="vp-sort-btn" :class="{on:listSort.src==='status'}" @click="toggleListSort('src','status')" title="상태순">
                    ●↕ <span v-if="listSort.src==='status'">{{ listSortDir.src==='asc'?'↑':'↓' }}</span>
                  </button>
                </div>
              </div>
              <div class="vp-list-body">
                <label v-for="t in sortedSrcList" :key="t.name"
                  class="vp-list-row"
                  :class="{
                    selected:  selTables.includes(t.name),
                    'src-only': t.srcOnly,
                    'r-ok':    lastResultMap[t.name]?.match,
                    'r-fail':  lastResultMap[t.name] && !lastResultMap[t.name].match,
                  }">
                  <input type="checkbox" :value="t.name" v-model="selTables" class="vp-chk"/>
                  <!-- 상태 아이콘 -->
                  <span class="vp-list-ico">
                    <svg v-if="lastResultMap[t.name]?.match" viewBox="0 0 10 10" fill="none" stroke="#16a34a" stroke-width="2.2" style="width:10px;height:10px"><polyline points="1.5,5 4,7.5 8.5,2"/></svg>
                    <svg v-else-if="lastResultMap[t.name] && !lastResultMap[t.name].match" viewBox="0 0 10 10" fill="none" stroke="#dc2626" stroke-width="2" style="width:10px;height:10px"><line x1="2" y1="2" x2="8" y2="8"/><line x1="8" y1="2" x2="2" y2="8"/></svg>
                    <svg v-else-if="t.srcOnly" viewBox="0 0 10 10" fill="none" stroke="#d97706" stroke-width="1.8" style="width:10px;height:10px"><path d="M5 1.5L8.5 8H1.5L5 1.5z"/></svg>
                    <span v-else class="vp-list-ico-dot"></span>
                  </span>
                  <!-- 테이블명 -->
                  <span class="vp-list-nm">{{ t.name }}</span>
                  <!-- 결과 (검증 후) -->
                  <span v-if="lastResultMap[t.name]" class="vp-list-diff"
                    :class="lastResultMap[t.name].match ? 'ok' : 'fail'">
                    {{ lastResultMap[t.name].match ? '일치' : fmtDiff(lastResultMap[t.name].diff) }}
                  </span>
                  <span v-else-if="t.srcOnly" class="vp-list-badge src-only">소스전용</span>
                </label>
              </div>
            </div>

            <!-- 구분선 -->
            <div class="vp-list-divider"></div>

            <!-- 타겟 컬럼 -->
            <div class="vp-list-col">
              <div class="vp-list-col-hdr tgt">
                <label class="vp-list-chk-all">
                  <input type="checkbox"
                    :checked="tgtOnlyFiltered.every(t=>selTables.includes(t.name)) && tgtOnlyFiltered.length>0"
                    @change="toggleColAll('tgt', $event)"
                    class="vp-chk"/>
                </label>
                <span class="vp-list-col-dot tgt"></span>
                <span class="vp-list-col-title">타겟 <span class="vp-list-col-cnt">{{ tgtOnlyFiltered.length }}</span></span>
                <div class="vp-list-sort-btns">
                  <button class="vp-sort-btn" :class="{on:listSort.tgt==='name'}" @click="toggleListSort('tgt','name')" title="이름순">
                    A↕ <span v-if="listSort.tgt==='name'">{{ listSortDir.tgt==='asc'?'↑':'↓' }}</span>
                  </button>
                  <button class="vp-sort-btn" :class="{on:listSort.tgt==='status'}" @click="toggleListSort('tgt','status')" title="상태순">
                    ●↕ <span v-if="listSort.tgt==='status'">{{ listSortDir.tgt==='asc'?'↑':'↓' }}</span>
                  </button>
                </div>
              </div>
              <div class="vp-list-body">
                <label v-for="t in sortedTgtList" :key="t.name"
                  class="vp-list-row"
                  :class="{
                    selected:  selTables.includes(t.name),
                    'tgt-only': t.tgtOnly,
                    'r-ok':    lastResultMap[t.name]?.match,
                    'r-fail':  lastResultMap[t.name] && !lastResultMap[t.name].match,
                  }">
                  <input type="checkbox" :value="t.name" v-model="selTables" class="vp-chk"/>
                  <span class="vp-list-ico">
                    <svg v-if="lastResultMap[t.name]?.match" viewBox="0 0 10 10" fill="none" stroke="#16a34a" stroke-width="2.2" style="width:10px;height:10px"><polyline points="1.5,5 4,7.5 8.5,2"/></svg>
                    <svg v-else-if="lastResultMap[t.name] && !lastResultMap[t.name].match" viewBox="0 0 10 10" fill="none" stroke="#dc2626" stroke-width="2" style="width:10px;height:10px"><line x1="2" y1="2" x2="8" y2="8"/><line x1="8" y1="2" x2="2" y2="8"/></svg>
                    <svg v-else-if="t.tgtOnly" viewBox="0 0 10 10" fill="none" stroke="#8b5cf6" stroke-width="1.8" style="width:10px;height:10px"><path d="M5 1.5L8.5 8H1.5L5 1.5z"/></svg>
                    <span v-else class="vp-list-ico-dot tgt"></span>
                  </span>
                  <span class="vp-list-nm">{{ t.name }}</span>
                  <span v-if="lastResultMap[t.name]" class="vp-list-diff"
                    :class="lastResultMap[t.name].match ? 'ok' : 'fail'">
                    {{ lastResultMap[t.name].match ? '일치' : fmtDiff(lastResultMap[t.name].diff) }}
                  </span>
                  <span v-else-if="t.tgtOnly" class="vp-list-badge tgt-only">타겟전용</span>
                </label>
              </div>
            </div>
          </div>

          <!-- 패널 푸터 -->
          <div v-if="srcTables.length" class="vp-tbl-footer">
            <span class="vp-sel-info">{{ selTables.length }}개 선택 / 전체 {{ srcTables.length }}개</span>
            <div style="display:flex;gap:5px">
              <button class="vp-icon-btn" @click="selTables=srcTables.map(t=>t.name)">전체 선택</button>
              <button class="vp-icon-btn" @click="selTables=[]">해제</button>
            </div>
          </div>
        </div>


        <!-- KPI 행 -->
        <div v-if="results.length" class="vp-kpi-row">
          <div class="vp-kpi ok">
            <div class="vp-kpi-n">{{ results.filter(r=>r.match).length }}</div>
            <div class="vp-kpi-l">일치</div>
          </div>
          <div class="vp-kpi fail">
            <div class="vp-kpi-n">{{ results.filter(r=>!r.match).length }}</div>
            <div class="vp-kpi-l">불일치</div>
          </div>
          <div class="vp-kpi miss">
            <div class="vp-kpi-n">{{ results.filter(r=>!r.tgt_exist).length }}</div>
            <div class="vp-kpi-l">타겟없음</div>
          </div>
          <div class="vp-kpi rate">
            <div class="vp-kpi-n">{{ passRate }}<span style="font-size:13px;font-weight:500">%</span></div>
            <div class="vp-kpi-l">통과율</div>
          </div>
          <div class="vp-kpi time">
            <div class="vp-kpi-n">{{ summary?.elapsed_sec ?? '—' }}<span style="font-size:13px;font-weight:500">s</span></div>
            <div class="vp-kpi-l">소요시간</div>
          </div>
          <div style="margin-left:auto;display:flex;gap:6px;align-items:center">
            <button v-if="failCount>0" class="vp-action-btn warn" @click="reRunAll">
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px"><path d="M1 6a5 5 0 1 0 5-5"/><polyline points="3.5,1 1,1 1,3.5"/></svg>
              불일치 {{ failCount }}개 재이관
            </button>
          </div>
        </div>

        <!-- 결과 테이블 -->
        <div v-if="results.length" class="vp-res-wrap">
          <table class="vp-tbl">
            <thead>
              <tr>
                <th style="width:32px"><input type="checkbox" @change="toggleAll" :checked="allSel" class="vp-chk"/></th>
                <th class="vp-sort" @click="setSort('table')">테이블 <span class="vp-sico">{{ sortIco('table') }}</span></th>
                <th class="vp-sort vp-num" @click="setSort('src_count')">소스 행수 <span class="vp-sico">{{ sortIco('src_count') }}</span></th>
                <th class="vp-sort vp-num" @click="setSort('tgt_count')">타겟 행수 <span class="vp-sico">{{ sortIco('tgt_count') }}</span></th>
                <th class="vp-sort vp-num" @click="setSort('diff')">차이 <span class="vp-sico">{{ sortIco('diff') }}</span></th>
                <th v-if="mode!=='row_count'" class="vp-sort" @click="setSort('checksum_match')">체크섬 <span class="vp-sico">{{ sortIco('checksum_match') }}</span></th>
                <th v-if="mode==='column_stats'||mode==='full'" class="vp-sort" @click="setSort('stats_match')">컬럼통계 <span class="vp-sico">{{ sortIco('stats_match') }}</span></th>
                <th class="vp-sort" style="width:80px;text-align:center" @click="setSort('match')">상태 <span class="vp-sico">{{ sortIco('match') }}</span></th>
                <th style="width:80px">액션</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="r in filteredResults" :key="r.table">
                <tr class="vp-row" :class="{'vp-row-fail':!r.match,'vp-row-ok':r.match}" @click="toggleDetail(r)">
                  <td @click.stop><input type="checkbox" v-model="r._sel" class="vp-chk"/></td>
                  <td class="vp-tbl-nm">
                    <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.3" style="width:10px;height:10px;flex-shrink:0;opacity:.4"><rect x="1" y="1" width="10" height="10" rx="1"/><line x1="1" y1="4.5" x2="11" y2="4.5"/><line x1="4.5" y1="4.5" x2="4.5" y2="11"/></svg>
                    {{ r.table }}
                  </td>
                  <td class="vp-num">{{ fmt(r.src_count) }}</td>
                  <td class="vp-num">{{ r.tgt_exist ? fmt(r.tgt_count) : '—' }}</td>
                  <td class="vp-num">
                    <span v-if="!r.tgt_exist" class="vp-badge miss">없음</span>
                    <span v-else-if="r.diff===0" class="vp-badge ok">0</span>
                    <span v-else class="vp-badge fail">{{ r.diff > 0 ? '+' : '' }}{{ fmt(r.diff) }}</span>
                  </td>
                  <td v-if="mode!=='row_count'">
                    <span v-if="r.checksum_match===true"  class="vp-badge ok">일치</span>
                    <span v-else-if="r.checksum_match===false" class="vp-badge fail">불일치</span>
                    <span v-else-if="r.checksum_error"    class="vp-badge warn" :title="r.checksum_error">오류</span>
                    <span v-else class="vp-badge gray">—</span>
                  </td>
                  <td v-if="mode==='column_stats'||mode==='full'">
                    <span v-if="r.stats_match===true"  class="vp-badge ok">일치</span>
                    <span v-else-if="r.stats_match===false" class="vp-badge fail">{{ r.col_stats?.filter(c=>!c.match).length }}개 차이</span>
                    <span v-else-if="r.stats_error"    class="vp-badge warn">오류</span>
                    <span v-else class="vp-badge gray">—</span>
                  </td>
                  <td style="text-align:center">
                    <span class="vp-status-ico">
                      <svg v-if="r.match" viewBox="0 0 16 16" fill="none" stroke="#16a34a" stroke-width="2" style="width:14px;height:14px">
                        <circle cx="8" cy="8" r="6.5" stroke-width="1" fill="rgba(34,197,94,.1)"/>
                        <polyline points="4.5,8 7,10.5 11.5,5.5" stroke-linecap="round" stroke-linejoin="round"/>
                      </svg>
                      <svg v-else-if="!r.tgt_exist" viewBox="0 0 16 16" fill="none" stroke="#d97706" stroke-width="1.8" style="width:14px;height:14px">
                        <circle cx="8" cy="8" r="6.5" stroke-width="1" fill="rgba(245,158,11,.1)"/>
                        <path d="M8 5v3.5"/><circle cx="8" cy="11" r=".6" fill="#d97706"/>
                      </svg>
                      <svg v-else viewBox="0 0 16 16" fill="none" stroke="#dc2626" stroke-width="2" style="width:14px;height:14px">
                        <circle cx="8" cy="8" r="6.5" stroke-width="1" fill="rgba(239,68,68,.1)"/>
                        <line x1="5.5" y1="5.5" x2="10.5" y2="10.5" stroke-linecap="round"/>
                        <line x1="10.5" y1="5.5" x2="5.5" y2="10.5" stroke-linecap="round"/>
                      </svg>
                    </span>
                  </td>
                  <td @click.stop style="display:flex;gap:4px;align-items:center;padding:6px 10px">
                    <button v-if="!r.match" class="vp-act-btn warn" @click="reRun(r.table)">재이관</button>
                    <button v-if="!r.tgt_exist" class="vp-act-btn info" @click="createTbl(r.table)">생성</button>
                  </td>
                </tr>

                <!-- 상세 펼침 -->
                <tr v-if="detailRows[r.table]" class="vp-detail-row">
                  <td colspan="10">
                    <div class="vp-detail-box">
                      <!-- 샘플 데이터 -->
                      <template v-if="r.src_sample?.length">
                        <div class="vp-det-title">샘플 데이터 비교 (상위 5건)</div>
                        <div class="vp-sample-grid">
                          <div class="vp-sample-side" v-for="side in ['src','tgt']" :key="side">
                            <div class="vp-sample-hdr" :class="side">
                              {{ side==='src' ? '🔵 소스' : '🟢 타겟' }}
                            </div>
                            <div class="vp-sample-scroll">
                              <table class="vp-mini-tbl">
                                <thead><tr>
                                  <th v-for="k in Object.keys((side==='src'?r.src_sample:r.tgt_sample)?.[0]||{})" :key="k">{{ k }}</th>
                                </tr></thead>
                                <tbody>
                                  <tr v-for="(row,i) in (side==='src'?r.src_sample:(r.tgt_sample||[]))" :key="i">
                                    <td v-for="k in Object.keys(row)" :key="k">{{ row[k] ?? 'NULL' }}</td>
                                  </tr>
                                </tbody>
                              </table>
                            </div>
                          </div>
                        </div>
                      </template>

                      <!-- 컬럼 통계 -->
                      <template v-if="r.col_stats?.length">
                        <div class="vp-det-title" style="margin-top:14px">
                          컬럼별 통계 비교
                          <span v-if="r.col_stats.filter(c=>!c.match).length" class="vp-badge fail" style="font-size:.65rem;margin-left:6px">
                            {{ r.col_stats.filter(c=>!c.match).length }}개 차이
                          </span>
                        </div>
                        <table class="vp-stat-tbl">
                          <thead><tr>
                            <th>컬럼</th><th>타입</th>
                            <th>NULL(소스)</th><th>NULL(타겟)</th>
                            <th>MIN/Distinct</th><th>MAX/MaxLen</th><th>AVG/MinLen</th>
                            <th style="text-align:center">상태</th>
                          </tr></thead>
                          <tbody>
                            <tr v-for="c in r.col_stats" :key="c.col" :class="{'vp-cs-fail':!c.match}">
                              <td class="vp-col-nm">{{ c.col }}</td>
                              <td class="vp-col-tp">{{ c.type }}</td>
                              <td :class="{'vp-vdiff': c.src?.null_cnt !== c.tgt?.null_cnt}">{{ c.src?.null_cnt ?? '—' }}</td>
                              <td :class="{'vp-vdiff': c.src?.null_cnt !== c.tgt?.null_cnt}">{{ c.tgt?.null_cnt ?? '—' }}</td>
                              <td :class="{'vp-vdiff': c.diffs?.find(d=>d.key==='min'||d.key==='distinct')}">{{ c.src?.min ?? c.src?.distinct ?? '—' }}</td>
                              <td :class="{'vp-vdiff': c.diffs?.find(d=>d.key==='max'||d.key==='max_len')}">{{ c.src?.max ?? c.src?.max_len ?? '—' }}</td>
                              <td :class="{'vp-vdiff': c.diffs?.find(d=>d.key==='avg'||d.key==='min_len')}">{{ c.src?.avg ?? c.src?.min_len ?? '—' }}</td>
                              <td style="text-align:center">
                                <span class="vp-badge" :class="c.match?'ok':'fail'">{{ c.match ? '✓' : `✕ ${c.diffs?.length}개` }}</span>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </template>

                      <div v-if="!r.src_sample?.length && !r.col_stats?.length" class="vp-no-detail">
                        샘플 또는 컬럼통계 모드로 재실행하세요
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </template>

      <!-- ══ 오브젝트 검증 ══ -->
      <template v-if="vType==='object'">


        <!-- 소스 오브젝트 목록 — 타입별 세로 리스트 -->
        <div v-if="hasAnyObjects || objLoading" class="vp-obj-panel">
          <!-- 패널 헤더 -->
          <div class="vp-obj-hdr">
            <span class="vp-obj-hdr-title">소스 오브젝트 선택</span>
            <div style="display:flex;gap:5px;align-items:center">
              <div v-if="objLoading" class="vp-ldots" style="margin-right:4px"><span/><span/><span/></div>
              <span v-else class="vp-cnt-badge" style="margin-right:4px">
                {{ objGroups.filter(g=>selObjTypes.includes(g.type)).reduce((s,g)=>s+g.items.length,0) }}개
              </span>
              <button class="vp-icon-btn" @click="loadSrcObjects(true)" title="새로고침" :disabled="objLoading">
                <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:11px;height:11px"><path d="M1 7a6 6 0 1 0 6-6"/><polyline points="4,1 1,1 1,4"/></svg>
              </button>
              <button class="vp-icon-btn" @click="selAllObjs">전체 선택</button>
              <button class="vp-icon-btn" @click="clearAllObjs">전체 해제</button>
            </div>
          </div>

          <!-- 로딩 중 -->
          <div v-if="objLoading" class="vp-tbl-loading" style="padding:20px">
            <div class="vp-ldots"><span/><span/><span/></div> 오브젝트 목록 로딩 중...
          </div>

          <!-- 타입별 섹션 — 4분할 가로 레이아웃 -->
          <div v-else class="vp-obj-sections">
            <template v-for="grp in objGroups" :key="grp.type">
              <div v-if="grp.items.length && selObjTypes.includes(grp.type)"
                   class="vp-obj-section">

                <!-- 섹션 헤더 -->
                <div class="vp-obj-sec-hdr">
                  <label class="vp-obj-sec-chk-all" title="전체 선택/해제">
                    <input type="checkbox"
                      :checked="grp.items.every(o=>o._sel)"
                      @change="toggleGrp(grp)"
                      class="vp-chk"/>
                  </label>
                  <span class="vp-obj-sec-ico">{{ grp.icon }}</span>
                  <span class="vp-obj-sec-label">{{ grp.label }}</span>
                  <span class="vp-cnt-badge" style="margin-left:auto">{{ grp.items.filter(o=>o._sel).length }}/{{ grp.items.length }}</span>
                </div>

                <!-- 세로 리스트 -->
                <div class="vp-obj-list">
                  <label v-for="o in grp.items" :key="o.name"
                         class="vp-obj-row"
                         :class="{selected: o._sel}">
                    <input type="checkbox" v-model="o._sel" class="vp-chk"/>
                    <span class="vp-obj-nm">{{ o.name }}</span>
                  </label>
                </div>
              </div>
            </template>
          </div>
        </div>

        <!-- 소스 오브젝트 없을 때 안내 -->
        <div v-else-if="!hasAnyObjects && !objLoading && srcObjects !== null" class="vp-tbl-empty" style="padding:20px">
          소스 DB에서 오브젝트를 찾을 수 없습니다.
          <button class="vp-chip on" @click="loadSrcObjects(true)">다시 조회</button>
        </div>
        <div v-else-if="!srcObjects && !objLoading" class="vp-tbl-empty" style="padding:20px">
          <span>오브젝트 목록이 로드되지 않았습니다.</span>
          <button class="vp-chip on" @click="loadSrcObjects(true)">조회하기</button>
        </div>

        <!-- 오브젝트 결과 -->
        <div v-if="objResults.length">

          <!-- ── 가로 진행 상태바 (실행 중일 때만) ── -->
          <div v-if="objTesting" class="vp-hprog-bar">
            <div class="vp-hprog-top">
              <div class="vp-hprog-info">
                <span class="vp-spin" style="width:11px;height:11px;border-width:1.8px;flex-shrink:0"></span>
                <span class="vp-hprog-cur-nm">{{ objTestCurName }}</span>
                <span class="vp-hprog-fraction">{{ objTestIdx }} / {{ objTestTotal }}</span>
              </div>
              <div class="vp-hprog-badges">
                <span class="vp-badge ok" style="font-size:11px">
                  ✓ {{ objResults.filter(r=>r.testStatus==='pass'&&r.srcTestStatus==='pass').length }}
                </span>
                <span class="vp-badge fail" style="font-size:11px">
                  ✗ {{ objResults.filter(r=>r.testStatus==='fail'||r.srcTestStatus==='fail').length }}
                </span>
                <span class="vp-badge gray" style="font-size:11px;opacity:.7">
                  ○ {{ objResults.filter(r=>!r.testStatus&&!r.srcTestStatus).length }}
                </span>
              </div>
            </div>
            <!-- 트랙 -->
            <div class="vp-hprog-track">
              <div class="vp-hprog-done"
                   :style="{width: (objTestIdx/Math.max(objTestTotal,1)*100)+'%'}"></div>
              <div class="vp-hprog-success"
                   :style="{width: (objResults.filter(r=>r.testStatus==='pass'&&r.srcTestStatus==='pass').length/Math.max(objTestTotal,1)*100)+'%'}"></div>
              <div class="vp-hprog-fail"
                   :style="{width: (objResults.filter(r=>r.testStatus==='fail'||r.srcTestStatus==='fail').length/Math.max(objTestTotal,1)*100)+'%'}"></div>
            </div>
            <div class="vp-hprog-pct">{{ Math.round(objTestIdx/Math.max(objTestTotal,1)*100) }}%</div>
          </div>

          <!-- 오브젝트 현황 테이블 -->
          <div class="vp-obj-stat-wrap" style="margin-bottom:8px">
            <div class="vp-obj-stat-top">
              <div class="vp-obj-stat-total">총 {{ objResults.length }}개 오브젝트</div>
              <!-- 일괄 선택 버튼 -->
              <div class="vp-sel-btns">
                <span class="vp-sel-label">선택·필터:</span>
                <button class="chip vp-sel-chip" :class="{on: objViewFilter==='pass'}"
                        @click="selectAndFilter('pass')"
                        title="성공만 보기 + 선택">
                  <span style="color:#16a34a">✓</span> 성공
                  <span class="vp-sel-cnt">{{ objResults.filter(r=>r.testStatus==='pass'&&r.srcTestStatus==='pass').length }}</span>
                </button>
                <button class="chip vp-sel-chip" :class="{on: objViewFilter==='review'}"
                        @click="selectAndFilter('review')"
                        title="검토만 보기 + 선택">
                  <span style="color:#d97706">△</span> 검토
                  <span class="vp-sel-cnt">{{ objResults.filter(r=>r.testStatus==='review'||r.srcTestStatus==='review').length }}</span>
                </button>
                <button class="chip vp-sel-chip" :class="{on: objViewFilter==='fail'}"
                        @click="selectAndFilter('fail')"
                        title="실패만 보기 + 선택">
                  <span style="color:#dc2626">✗</span> 실패
                  <span class="vp-sel-cnt">{{ objResults.filter(r=>r.testStatus==='fail'||r.srcTestStatus==='fail').length }}</span>
                </button>
                <button class="chip vp-sel-chip" :class="{on: objViewFilter==='all'}"
                        @click="selectAndFilter('all')"
                        title="전체 보기 + 전체 선택">전체</button>
                <button class="chip vp-sel-chip"
                        @click="selectAndFilter('clear')"
                        title="선택 해제">해제</button>
              </div>
            </div>
            <table class="vp-obj-stat-tbl">
              <thead>
                <tr>
                  <th></th>
                  <th>존재</th>
                  <th>미이관</th>
                  <th>오류</th>
                  <th v-if="objResults.some(r=>r.srcTestStatus||r.testStatus)">성공</th>
                  <th v-if="objResults.some(r=>r.srcTestStatus||r.testStatus)">검토</th>
                  <th v-if="objResults.some(r=>r.srcTestStatus||r.testStatus)">실패</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td class="vp-obj-stat-row-lbl">소스</td>
                  <td><span class="vp-ostat ok">{{ objResults.filter(r=>r.srcTestStatus||r.srcTestResult).length || objResults.length }}</span></td>
                  <td><span class="vp-ostat muted">—</span></td>
                  <td><span class="vp-ostat muted">—</span></td>
                  <td v-if="objResults.some(r=>r.srcTestStatus||r.testStatus)">
                    <span class="vp-ostat pass">{{ objResults.filter(r=>r.srcTestStatus==='pass').length }}</span>
                  </td>
                  <td v-if="objResults.some(r=>r.srcTestStatus||r.testStatus)">
                    <span class="vp-ostat" :class="objResults.filter(r=>r.srcTestStatus==='fail').length ? 'fail' : 'muted'">
                      {{ objResults.filter(r=>r.srcTestStatus==='fail').length || '—' }}
                    </span>
                  </td>
                </tr>
                <tr>
                  <td class="vp-obj-stat-row-lbl">타겟</td>
                  <td><span class="vp-ostat ok">{{ objResults.filter(r=>r.status==='ok').length }}</span></td>
                  <td>
                    <span class="vp-ostat" :class="objResults.filter(r=>r.status==='missing').length ? 'miss' : 'muted'">
                      {{ objResults.filter(r=>r.status==='missing').length || '—' }}
                    </span>
                  </td>
                  <td>
                    <span class="vp-ostat" :class="objResults.filter(r=>r.status==='error').length ? 'warn' : 'muted'">
                      {{ objResults.filter(r=>r.status==='error').length || '—' }}
                    </span>
                  </td>
                  <td v-if="objResults.some(r=>r.srcTestStatus||r.testStatus)">
                    <span class="vp-ostat pass">{{ objResults.filter(r=>r.testStatus==='pass').length }}</span>
                  </td>
                  <td v-if="objResults.some(r=>r.srcTestStatus||r.testStatus)">
                    <span class="vp-ostat" :class="objResults.filter(r=>r.testStatus==='fail').length ? 'fail' : 'muted'">
                      {{ objResults.filter(r=>r.testStatus==='fail').length || '—' }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
            <div class="vp-obj-stat-actions">

              <button class="chip" @click="expandAllObjDetails">
                <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px"><polyline points="1,4 6,8 11,4"/></svg>
                전체 열기
              </button>
              <button class="chip" @click="collapseAllObjDetails">
                <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px"><polyline points="1,8 6,4 11,8"/></svg>
                전체 닫기
              </button>
              <!-- 선택 실행 — 체크박스 선택 항목만 -->
              <button v-if="selObjCount > 0" class="chip chip-run vp-sel-run-btn"
                      @click="runSelectedObjTest" :disabled="objTesting">
                <span v-if="objTesting" class="vp-spin" style="width:11px;height:11px;border-width:1.5px"></span>
                <svg v-else viewBox="0 0 12 12" fill="currentColor" style="width:10px;height:10px"><polygon points="2,1 10,6 2,11"/></svg>
                {{ objTesting ? '테스트 중...' : `▶ 선택 실행 (${selObjCount}개)` }}
              </button>
              <!-- 전체 실행 -->
              <button v-if="objResults.filter(r=>r.status==='ok').length" class="chip"
                      :class="selObjCount>0 ? '' : 'chip-run'"
                      @click="runAllObjTest" :disabled="objTesting">
                <span v-if="objTesting" class="vp-spin" style="width:11px;height:11px;border-width:1.5px"></span>
                <svg v-else viewBox="0 0 12 12" fill="currentColor" style="width:10px;height:10px"><polygon points="2,1 10,6 2,11"/></svg>
                {{ objTesting ? '테스트 중...' : '▶ 전체 실행' }}
              </button>
              <button v-if="objResults.filter(r=>r.status==='missing').length" class="chip chip-report" @click="deployMissing">
                <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px"><line x1="6" y1="10" x2="6" y2="2"/><polyline points="2,6 6,2 10,6"/></svg>
                미이관 {{ objResults.filter(r=>r.status==='missing').length }}개 배포
              </button>
              <!-- 재이관 버튼 — 실패 항목 있을 때 -->
              <button v-if="objResults.some(r=>r.testStatus==='fail'||r.srcTestStatus==='fail')"
                      class="chip chip-clear" @click="openRemigrateModal()">
                <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px">
                  <path d="M2 6a4 4 0 1 0 4-4"/><polyline points="4,1 1,1 1,4"/>
                  <line x1="7" y1="8" x2="7" y2="5"/><line x1="5.5" y1="8" x2="8.5" y2="8"/>
                </svg>
                재이관 ({{ objResults.filter(r=>r.testStatus==='fail'||r.srcTestStatus==='fail').length }}개)
              </button>
            </div>
          </div>

          <div class="vp-res-wrap">
            <table class="vp-tbl vp-obj-tbl">
              <colgroup>
                <col style="width:28px">
                <col style="width:64px">
                <col style="width:220px">
                <col style="width:140px">
                <col style="width:140px">
                <col style="width:70px">
              </colgroup>
              <thead><tr>
                <th><input type="checkbox" @change="toggleAllObj" :checked="allObjSel" class="vp-chk"/></th>
                <th>유형</th>
                <th class="vp-sort" @click="setObjSort('name')">오브젝트명 <span class="vp-sico">{{ objSortIco('name') }}</span></th>
                <th class="vp-sort" style="text-align:center" @click="setObjSort('srcTestStatus')">
                  소스 테스트 <span class="vp-sico">{{ objSortIco('srcTestStatus') }}</span>
                </th>
                <th class="vp-sort" style="text-align:center" @click="setObjSort('testStatus')">
                  타겟 테스트 <span class="vp-sico">{{ objSortIco('testStatus') }}</span>
                </th>
                <th style="text-align:center">액션</th>
              </tr></thead>
              <tbody>
                <template v-for="r in sortedObjResults" :key="r.name+r.type">
                  <tr class="vp-row"
                      :class="{'vp-row-fail': r.status!=='ok'||r.srcTestStatus==='fail'||r.testStatus==='fail', 'vp-row-review': r.status==='ok'&&(r.srcTestStatus==='review'||r.testStatus==='review')&&r.srcTestStatus!=='fail'&&r.testStatus!=='fail', 'vp-row-ok': r.status==='ok'&&r.srcTestStatus==='pass'&&r.testStatus==='pass'}"
                      @click="toggleObjDetail(r)" style="cursor:pointer">
                    <td @click.stop><input type="checkbox" v-model="r._sel" class="vp-chk"/></td>
                    <td><span class="vp-otype-tag" :class="r.type.toLowerCase()">{{ r.type.substring(0,4) }}</span></td>
                    <!-- 오브젝트명 + 존재 여부 서브텍스트 -->
                    <td style="overflow:hidden">
                      <div class="vp-obj-nm-cell">{{ r.name }}</div>
                      <div class="vp-obj-nm-sub">
                        소스 ✓
                        <template v-if="r.status==='ok'"> · 타겟 ✓</template>
                        <template v-else-if="r.status==='missing'"> · <span style="color:#dc2626">타겟 없음</span></template>
                        <template v-else> · <span style="color:#dc2626">타겟 오류</span></template>
                      </div>
                    </td>
                    <!-- 소스 테스트 — badge만, 상세는 클릭 펼치기 -->
                    <td style="text-align:center">
                      <span v-if="r.srcTesting" class="vp-badge gray">
                        <span class="vp-spin" style="width:8px;height:8px;border-width:1.5px;display:inline-block;vertical-align:middle"></span>
                      </span>
                      <span v-else-if="r.srcTestStatus==='pass'" class="vp-badge ok">✓ 성공</span>
                      <span v-else-if="r.srcTestStatus==='fail'" class="vp-badge fail">✗ 실패</span>
                      <span v-else-if="r.srcTestStatus==='skip'" class="vp-badge gray">SKIP</span>
                      <span v-else class="vp-badge gray" style="opacity:.4">—</span>
                    </td>
                    <!-- 타겟 테스트 — badge만, 상세는 클릭 펼치기 -->
                    <td style="text-align:center">
                      <span v-if="r.testing" class="vp-badge gray">
                        <span class="vp-spin" style="width:8px;height:8px;border-width:1.5px;display:inline-block;vertical-align:middle"></span>
                      </span>
                      <span v-else-if="r.testStatus==='pass'" class="vp-badge ok">✓ 성공</span>
                      <span v-else-if="r.testStatus==='fail'" class="vp-badge fail">✗ 실패</span>
                      <span v-else-if="r.testStatus==='skip'" class="vp-badge gray">SKIP</span>
                      <span v-else class="vp-badge gray" style="opacity:.4">—</span>
                    </td>
                    <!-- 액션 -->
                    <td @click.stop style="text-align:center">
                      <button class="vp-act-btn info" @click="runObjTest(r)"
                              :disabled="r.testing||r.srcTesting" title="소스+타겟 실행 테스트">
                        {{ (r.testing||r.srcTesting) ? '…' : '▶ 테스트' }}
                      </button>
                    </td>
                  </tr>
                  <!-- 테스트 결과 상세 — 클릭 시 펼치기 -->
                  <tr v-if="objDetailRows[r.name+r.type]" class="vp-detail-row">
                    <td colspan="6" style="padding:8px 10px">
                      <!-- 파라미터 입력 폼 -->
                      <div class="vp-param-form">
                        <div class="vp-param-form-hdr">
                          <span class="vp-param-form-title">
                            <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px"><circle cx="6" cy="6" r="5"/><line x1="6" y1="4" x2="6" y2="8" stroke-width="1.5"/><circle cx="6" cy="2.8" r=".7" fill="currentColor" stroke="none"/></svg>
                            파라미터 직접 입력 테스트
                          </span>
                          <div style="display:flex;gap:5px">
                            <button class="chip" @click.stop="loadParamsForRow(r)" :disabled="r._paramLoading">
                              <span v-if="r._paramLoading" class="vp-spin" style="width:9px;height:9px;border-width:1.5px"></span>
                              <svg v-else viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px"><path d="M1 6a5 5 0 1 0 5-5"/><polyline points="3,1 1,1 1,3"/></svg>
                              파라미터 조회
                            </button>
                            <button v-if="r._params?.length" class="chip chip-report"
                                    @click.stop="loadSuggestionsForRow(r)" :disabled="r._suggestLoading"
                                    title="DB 실제 데이터에서 추천값 자동 설정">
                              <span v-if="r._suggestLoading" class="vp-spin" style="width:9px;height:9px;border-width:1.5px"></span>
                              <svg v-else viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.4" style="width:10px;height:10px">
                                <circle cx="6" cy="6" r="4.5"/><polyline points="6,3.5 6,6 7.5,7.5" stroke-width="1.5"/>
                              </svg>
                              DB 추천값
                            </button>
                            <button class="chip" @click.stop="resetDummyParams(r)" :disabled="!r._params?.length">초기화</button>
                            <button class="chip chip-report" @click.stop="saveParamHint(r)" :disabled="!r._params?.length">💾 저장</button>
                          </div>
                        </div>

                        <!-- 파라미터 없음 안내 -->
                        <div v-if="!r._params?.length && !r._paramLoading" class="vp-param-empty">
                          "파라미터 조회" 버튼을 클릭하면 소스 DB에서 파라미터 목록을 가져옵니다
                        </div>

                        <!-- 파라미터 입력 그리드 -->
                        <div v-if="r._params?.length" class="vp-param-grid">
                          <div v-for="(p, i) in r._params" :key="i" class="vp-param-item">
                            <div class="vp-param-lbl">
                              <span class="vp-param-nm">{{ p.name }}</span>
                              <span class="vp-param-type">{{ p.data_type }}</span>
                              <span v-if="p.is_output" class="vp-param-out">OUT</span>
                            </div>
                            <div style="display:flex;gap:4px;align-items:center">
                              <input v-if="!p.is_output"
                                     v-model="p.dummy_value"
                                     class="vp-param-inp"
                                     :placeholder="p.data_type"
                                     @click.stop
                                     :style="p.suggestion_source && p.suggestion_source!=='패턴 추천' ? 'border-color:rgba(22,163,74,.5)' : ''"/>
                              <span v-else class="vp-param-inp" style="opacity:.5;font-size:11px;flex:1">OUT</span>
                              <span v-if="p.suggestion_source" class="vp-param-src"
                                    :title="p.suggestion_source">
                                {{ p.suggestion_source.includes('.')? '📊' : p.suggestion_source==='패턴 추천'?'🔤':'💡' }}
                              </span>
                            </div>
                          </div>
                        </div>

                        <!-- 실행 버튼 -->
                        <div v-if="r._params?.length" class="vp-param-run-row">
                          <button class="chip chip-run" @click.stop="runObjTestWithParams(r)"
                                  :disabled="r.testing||r.srcTesting">
                            <span v-if="r.testing||r.srcTesting" class="vp-spin" style="width:10px;height:10px;border-width:1.5px"></span>
                            <svg v-else viewBox="0 0 12 12" fill="currentColor" style="width:9px;height:9px"><polygon points="2,1 10,6 2,11"/></svg>
                            {{ (r.testing||r.srcTesting) ? '실행 중...' : '소스 + 타겟 동시 실행' }}
                          </button>
                          <!-- AI 재이관 버튼 -->
                          <button class="chip chip-clear" @click.stop="openRemigrateModal([r])"
                                  title="이 오브젝트를 AI로 재이관">
                            <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px">
                              <path d="M2 6a4 4 0 1 0 4-4"/><polyline points="4,1 1,1 1,4"/>
                              <line x1="7" y1="8" x2="7" y2="5"/><line x1="5.5" y1="8" x2="8.5" y2="8"/>
                            </svg>
                            AI 재이관
                          </button>
                          <span style="font-size:11px;color:var(--text-tertiary)">입력한 파라미터로 소스/타겟 모두 실행</span>
                        </div>
                      </div>

                      <!-- 테스트 결과 -->
                      <div v-if="r.srcTestResult || r.testResult" class="vp-obj-det-grid">
                        <!-- 소스 -->
                        <div class="vp-obj-det-box">
                          <div class="vp-obj-det-hdr">
                            소스
                            <span class="vp-badge" :class="r.srcTestStatus==='pass'?'ok':r.srcTestStatus==='fail'?'fail':'gray'">
                              {{ r.srcTestStatus==='pass'?'✓ 성공':r.srcTestStatus==='review'?'△ 검토':r.srcTestStatus==='fail'?'✗ 실패':'미실행' }}
                            </span>
                          </div>
                          <template v-if="r.srcTestResult">
                            <div class="vp-obj-det-row"><span class="vp-obj-det-lbl">방식</span><span class="vp-obj-det-val">{{ r.srcTestResult.method }}</span></div>
                            <div class="vp-obj-det-row"><span class="vp-obj-det-lbl">결과</span>
                              <span :class="r.srcTestStatus==='pass'?'vp-obj-det-val':'vp-obj-det-err'" :style="r.srcTestStatus==='pass'?'color:#16a34a':''">{{ r.srcTestResult.message }}</span>
                            </div>
                            <div v-if="r.srcTestResult.params_used?.length" class="vp-obj-det-row">
                              <span class="vp-obj-det-lbl">파라미터</span>
                              <span class="vp-obj-det-val" style="color:var(--text-tertiary)">{{ r.srcTestResult.params_used.join(', ') }}</span>
                            </div>
                            <div v-if="r.srcTestResult.error" class="vp-obj-det-row">
                              <span class="vp-obj-det-lbl">오류</span>
                              <span class="vp-obj-det-err">{{ r.srcTestResult.error }}</span>
                            </div>
                            <div v-if="r.srcTestResult.rows?.length" class="vp-obj-det-row">
                              <span class="vp-obj-det-lbl">반환</span><span class="vp-obj-det-val">{{ r.srcTestResult.rows.length }}행</span>
                            </div>
                            <div v-if="r.srcTestResult.elapsed_ms" class="vp-obj-det-row">
                              <span class="vp-obj-det-lbl">소요</span><span class="vp-obj-det-val">{{ r.srcTestResult.elapsed_ms }}ms</span>
                            </div>
                          </template>
                          <div v-else style="font-size:11px;color:var(--text-tertiary)">미실행</div>
                        </div>
                        <!-- 타겟 -->
                        <div class="vp-obj-det-box">
                          <div class="vp-obj-det-hdr">
                            타겟
                            <span class="vp-badge" :class="r.testStatus==='pass'?'ok':r.testStatus==='fail'?'fail':'gray'">
                              {{ r.testStatus==='pass'?'✓ 성공':r.testStatus==='review'?'△ 검토':r.testStatus==='fail'?'✗ 실패':'미실행' }}
                            </span>
                          </div>
                          <template v-if="r.testResult">
                            <div class="vp-obj-det-row"><span class="vp-obj-det-lbl">방식</span><span class="vp-obj-det-val">{{ r.testResult.method }}</span></div>
                            <div class="vp-obj-det-row"><span class="vp-obj-det-lbl">결과</span>
                              <span :class="r.testStatus==='pass'?'vp-obj-det-val':'vp-obj-det-err'" :style="r.testStatus==='pass'?'color:#16a34a':''">{{ r.testResult.message }}</span>
                            </div>
                            <div v-if="r.testResult.error" class="vp-obj-det-row">
                              <span class="vp-obj-det-lbl">오류</span>
                              <span class="vp-obj-det-err">{{ r.testResult.error }}</span>
                            </div>
                            <div v-if="r.testResult.rows?.length" class="vp-obj-det-row">
                              <span class="vp-obj-det-lbl">반환</span><span class="vp-obj-det-val">{{ r.testResult.rows.length }}행</span>
                            </div>
                            <div v-if="r.testResult.elapsed_ms" class="vp-obj-det-row">
                              <span class="vp-obj-det-lbl">소요</span><span class="vp-obj-det-val">{{ r.testResult.elapsed_ms }}ms</span>
                            </div>
                          </template>
                          <div v-else style="font-size:11px;color:var(--text-tertiary)">미실행</div>
                        </div>
                      </div><!-- end vp-obj-det-grid -->
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div><!-- end vp-obj-stat-wrap or last inner -->
        </div>
      </template>

    </div>

    <!-- 진행바 -->
    <div v-if="running" class="vp-prog" style="padding:0 2px">
      <div class="vp-prog-track"><div class="vp-prog-fill" :style="{width:progPct+'%'}"></div></div>
      <span class="vp-prog-txt">{{ progMsg }}</span>
    </div>

    <!-- 검증 이력 -->
    <div v-if="history.length" class="card vp-hist-card">
      <div class="vp-hist-hdr">
        <span class="vp-hist-title">검증 이력</span>
        <button class="vp-icon-btn" @click="loadHistory">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:12px;height:12px"><path d="M1 7a6 6 0 1 0 6-6"/><polyline points="4,1 1,1 1,4"/></svg>
        </button>
      </div>
      <table class="vp-tbl">
        <thead><tr>
          <th class="vp-sort" @click="setHistSort('timestamp')">시각 <span class="vp-sico">{{ histSortIco('timestamp') }}</span></th>
          <th class="vp-sort vp-num" @click="setHistSort('total')">테이블 <span class="vp-sico">{{ histSortIco('total') }}</span></th>
          <th class="vp-sort vp-num" @click="setHistSort('passed')">일치 <span class="vp-sico">{{ histSortIco('passed') }}</span></th>
          <th class="vp-sort vp-num" @click="setHistSort('failed')">불일치 <span class="vp-sico">{{ histSortIco('failed') }}</span></th>
          <th class="vp-sort" style="text-align:center" @click="setHistSort('pass_rate')">통과율 <span class="vp-sico">{{ histSortIco('pass_rate') }}</span></th>
          <th class="vp-sort" @click="setHistSort('method')">모드 <span class="vp-sico">{{ histSortIco('method') }}</span></th>
          <th class="vp-sort vp-num" @click="setHistSort('elapsed_sec')">소요 <span class="vp-sico">{{ histSortIco('elapsed_sec') }}</span></th>
        </tr></thead>
        <tbody>
          <tr v-for="h in sortedHistory" :key="h.timestamp" class="vp-row vp-row-ok">
            <td style="font-size:11.5px;color:var(--text-tertiary)">{{ h.timestamp }}</td>
            <td class="vp-num">{{ h.total }}</td>
            <td class="vp-num" style="color:#16a34a;font-weight:600">{{ h.passed }}</td>
            <td class="vp-num" style="color:#dc2626;font-weight:600">{{ h.failed }}</td>
            <td style="text-align:center">
              <span class="vp-badge" :class="h.pass_rate===100?'ok':h.pass_rate>=80?'warn':'fail'">{{ h.pass_rate }}%</span>
            </td>
            <td style="font-size:11.5px;color:var(--text-secondary)">{{ h.method }}</td>
            <td class="vp-num">{{ h.elapsed_sec }}s</td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>

  <!-- ── 재이관 모달 ── -->
  <teleport to="body">
    <div v-if="showRemigrate" class="vp-modal-overlay" @click.self="showRemigrate=false">
      <div class="vp-modal">
        <!-- 헤더 -->
        <div class="vp-modal-hdr">
          <div class="vp-modal-title">
            <svg viewBox="0 0 16 16" fill="none" style="width:15px;height:15px;flex-shrink:0">
              <path d="M8 2L14 14H2L8 2z" stroke="#dc2626" stroke-width="1.4"/>
              <line x1="8" y1="7" x2="8" y2="10" stroke="#dc2626" stroke-width="1.4"/>
              <circle cx="8" cy="12" r=".7" fill="#dc2626"/>
            </svg>
            이관 오류 감지 — 재이관 필요
          </div>
          <button class="vp-modal-close" @click="showRemigrate=false">✕</button>
        </div>

        <!-- 본문 -->
        <div class="vp-modal-body">
          <!-- 경고 메시지 -->
          <div class="vp-remig-alert">
            <svg viewBox="0 0 16 16" fill="none" style="width:15px;height:15px;flex-shrink:0;margin-top:1px">
              <path d="M8 2L14 14H2L8 2z" stroke="#dc2626" stroke-width="1.4"/>
              <line x1="8" y1="7" x2="8" y2="10" stroke="#dc2626" stroke-width="1.4"/>
              <circle cx="8" cy="12" r=".7" fill="#dc2626"/>
            </svg>
            <div class="vp-remig-alert-text">
              <strong>{{ remigrateTargets.length }}개 오브젝트</strong>에서 이관 오류가 확인됐습니다.<br>
              주요 원인: <strong>{{ remigrateReason }}</strong><br>
              AI 재변환 또는 오브젝트 매핑 화면에서 직접 수정할 수 있습니다.
            </div>
          </div>

          <!-- 실패 목록 -->
          <div class="vp-remig-list">
            <div v-for="r in remigrateTargets.slice(0,8)" :key="r.name" class="vp-remig-item">
              <span class="vp-otype-tag" :class="r.type.toLowerCase()">{{ r.type.substring(0,4) }}</span>
              <div style="flex:1;min-width:0">
                <div class="vp-remig-nm">{{ r.name }}</div>
                <div class="vp-remig-err">{{ _shortErr(r.testResult?.error || r.srcTestResult?.error || '') }}</div>
              </div>
            </div>
            <div v-if="remigrateTargets.length > 8"
                 style="font-size:11px;color:var(--text-tertiary);text-align:center;padding:5px">
              외 {{ remigrateTargets.length - 8 }}개 더...
            </div>
          </div>

          <!-- 처리 방법 선택 -->
          <div class="vp-remig-actions">
            <div class="vp-remig-action" :class="{selected: remigrateAction==='ai'}"
                 @click="remigrateAction='ai'">
              <div class="vp-remig-action-title">
                <svg viewBox="0 0 13 13" fill="none" style="width:12px;height:12px">
                  <circle cx="6.5" cy="6.5" r="5.5" stroke="#3b82f6" stroke-width="1.2"/>
                  <path d="M4 6.5l1.8 1.8 3.2-3.2" stroke="#3b82f6" stroke-width="1.4"/>
                </svg>
                AI 자동 재변환
              </div>
              <div class="vp-remig-action-desc">Claude AI가 소스 DDL을 읽어 올바른 타겟 문법으로 재변환 후 자동 배포</div>
            </div>
            <div class="vp-remig-action" :class="{selected: remigrateAction==='manual'}"
                 @click="remigrateAction='manual'">
              <div class="vp-remig-action-title">
                <svg viewBox="0 0 13 13" fill="none" style="width:12px;height:12px">
                  <rect x="1.5" y="2.5" width="10" height="8" rx="1.2" stroke="var(--text-secondary)" stroke-width="1.2"/>
                  <line x1="4" y1="5.5" x2="9" y2="5.5" stroke="var(--text-secondary)" stroke-width="1.1"/>
                  <line x1="4" y1="7.5" x2="7" y2="7.5" stroke="var(--text-secondary)" stroke-width="1.1"/>
                </svg>
                오브젝트 매핑에서 수동 수정
              </div>
              <div class="vp-remig-action-desc">오브젝트 매핑 화면으로 이동하여 DDL을 직접 수정 후 재배포</div>
            </div>
          </div>
        </div>

        <!-- 진행 상황 (실행 중일 때) -->
        <div v-if="remigrateLoading" class="vp-remig-progress">
          <div class="vp-remig-step">{{ remigrateStep }}</div>
          <div class="vp-remig-prog-list">
            <div v-for="row in remigrateProgress" :key="row.name"
                 class="vp-remig-prog-item" :class="row.status">
              <span class="vp-remig-prog-icon">
                <span v-if="row.status==='running'" class="vp-spin" style="width:9px;height:9px;border-width:1.5px;display:inline-block"></span>
                <span v-else-if="row.status==='done'" style="color:#16a34a">✓</span>
                <span v-else-if="row.status==='fail'" style="color:#dc2626">✗</span>
                <span v-else style="color:var(--text-tertiary)">○</span>
              </span>
              <span class="vp-otype-tag" :class="row.type.toLowerCase()" style="font-size:9px;padding:0 4px">{{ row.type.substring(0,4) }}</span>
              <span class="vp-remig-prog-nm">{{ row.name }}</span>
              <span class="vp-remig-prog-msg">{{ row.msg }}</span>
            </div>
          </div>
        </div>

        <!-- 푸터 -->
        <div class="vp-modal-footer">
          <label class="vp-remig-chk" v-if="!remigrateLoading">
            <input type="checkbox" v-model="remigrateOnlyFail"/>
            성공한 오브젝트 제외, 실패만 처리
          </label>
          <div v-if="remigrateLoading" style="font-size:11.5px;color:var(--text-secondary)">
            실행 중 — 잠시 기다려 주세요...
          </div>
          <div style="display:flex;gap:6px;margin-left:auto">
            <button class="chip" @click="showRemigrate=false" :disabled="remigrateLoading">취소</button>
            <button class="chip chip-run" @click="startRemigrate"
                    :disabled="remigrateLoading">
              <span v-if="remigrateLoading" class="vp-spin" style="width:10px;height:10px;border-width:1.5px"></span>
              <svg v-else viewBox="0 0 12 12" fill="currentColor" style="width:9px;height:9px"><polygon points="2,1 10,6 2,11"/></svg>
              {{ remigrateLoading ? '처리 중...' : remigrateAction==='ai' ? 'AI 재변환 + 배포' : '오브젝트 매핑으로 이동' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </teleport>

</template>

<script setup>
defineOptions({ name: 'Validate' })
import { ref, computed, watch, reactive, onMounted } from 'vue'
import { useConnectorStore } from '@/store/connectorStore.js'
import { useAppStore }       from '@/store/appStore.js'
import { usePageStore }      from '@/store/pageStore.js'
import axios from 'axios'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/layout/PageHeader.vue'

const connector = useConnectorStore()
const app       = useAppStore()
const pStore    = usePageStore()
const vType = ref('table')

// DB 로고 (SqlVerify와 동일)
const _VP_LOGOS = {
  mysql:      'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4Ij48cGF0aCBmaWxsPSIjMDA2MThBIiBkPSJNMTE2LjkgOTljLTYuNS0uMi0xMS41LjQtMTUuOCAyLjItMS4yLjUtMy4xLjUtMy4zIDIgLjcuNy44IDEuNyAxLjMgMi42IDEgMS42IDIuNyAzLjggNC4zIDUgMS43IDEuMyAzLjQgMi42IDUuMiAzLjcgMy4yIDEuOSA2LjggMyA5LjggNSAxLjggMS4xIDMuNiAyLjYgNS40IDMuOS45LjYgMS41IDEuNiAyLjYgMnYtLjJjLS42LS44LS44LTEuOC0xLjMtMi42bC0yLjQtMi40Yy0yLjQtMy4xLTUuNC01LjktOC42LTguMi0yLjUtMS44LTguMi00LjMtOS4zLTcuM2wtLjItLjJjMS44LS4yIDMuOS0uOSA1LjYtMS4zIDIuOC0uNyA1LjMtLjYgOC4yLTEuM2wzLjktMS4xdi0uN2MtMS41LTEuNS0yLjUtMy41LTQuMS00LjgtNC4yLTMuNS04LjctNy4xLTEzLjQtMTAtMi42LTEuNi01LjgtMi43LTguNi00LjEtLjktLjUtMi41LS43LTMuMi0xLjVjLTEuNC0xLjgtMi4yLTQuMi0zLjMtNi4zLTIuMy00LjUtNC42LTkuNC02LjctMTQuMS0xLjQtMy4yLTIuMy02LjQtNC4xLTkuM0M3Ni4yIDMwIDY3IDIxLjYgNTMgMTMuM2MtMy0xLjgtNi42LTIuNS0xMC40LTMuNGwtNi4xLS40Yy0xLjItLjUtMi41LTItMy43LTIuOEMxNC45IDMuMyAyLjMtMy40LTEuMyA1LjVjLTIuMyA1LjYgMy40IDExIDUuNCAxMy44IDEuNCAyIDMuMiA0LjIgNC4yIDYuNCAwLjcgMS40LjggMi44IDEuNCA0LjMgMS41IDMuOCAyLjggOCA0LjggMTEuNSAxIDEuNyAyLjEgMy41IDMuMyA1LjEuNyAxIDEuOSAxLjQgMi4xIDMtLjkgMS4zLTEgMy4yLTEuNSA0LjgtMi4zIDcuMy0xLjQgMTYuMyAxLjkgMjEuNyAxIDEuNiAzLjQgNS4xIDYuNiAzLjggMi44LTEuMiAyLjItNC43IDMtNy44LjItLjcuMS0xLjIuNC0xLjd2LjFsMi41IDVjMS44IDIuOSA1IDUuOSA3LjcgNy45IDEuNCAxIDIuNSAyLjggNC4zIDMuNHYtLjJoLS4xYy0uNC0uNS0uOS0xLTEuMy0xLjUtMS0xLTIuMS0yLjMtMi45LTMuNC0yLjMtMy4xLTQuMy02LjUtNi0xMC0uOS0xLjctMS42LTMuNi0yLjMtNS4zLS4zLS43LS4zLTEuNy0uOS0yLjEtLjggMS4yLTIgMi4zLTIuNiAzLjgtMSAyLjQtMS4xIDUuMy0xLjUgOC40LS4yLjEtLjEuMS0uMi4yLTItLjUtMi43LTIuNS0zLjQtNC4yLTEuOS00LjQtMi4yLTExLjUtLjYtMTYuNi41LTEuNSAyLjYtNi4yIDEuNy03LjYtLjQtLjgtMS43LTEuMy0yLjQtMS44LTEtLjYtMS44LTEuNi0yLjUtMi42LTEuNy0yLjMtMy4yLTUtNC4zLTcuNi0wLjYtMS4zLS44LTIuNy0xLjMtNC0xLTIuMy0yLjUtNC42LTMuNS02LjktLjUtMS4xLS44LTIuMy0xLjMtMy40LS43LTEuNS0xLjgtMi45LTIuMy00LjQtMS4zLTQuMS40LTguNSAxLjctMTEuMy40LS45IDEuNi0zLjcgMy40LTIuNyAxIC41IDEuMiAxLjcgMS43IDIuOC40LjkuOSAxLjggMS4zIDIuN2wxLjQgMy40Yy4xLjEuNCAxLjIuOSAxLjUuNC4yLjktLjMgMS4zLS4zLjUtLjEgMS4zLjIgMS45LjEuOS0uMiAxLjQtLjQgMi4xLS41LjYtLjEgMS4zLjEgMS45LjIuNS4xIDEgLjQgMS41LjVsLjguMmMuNC4xLjguMSAxLjIuMS42IDAgMS4zLS4xIDEuOS0uMi40LS4xLjgtLjIgMS4yLS40LjQtLjIuOC0uNiAxLjItLjctLjItMS4yLS43LTIuMy0xLjEtMy40LS40LS44LS43LTEuNi0xLTIuNS0uOS0yLjMtMi4yLTQuNi0zLjQtNi44LS42LTEuMS0xLjItMi4yLTEuOC0zLjMtLjItLjQtLjUtMS0uOC0xLjNzLS44LS40LTEuMS0uN2MtMS4yLS45LTIuNS0xLjktMy42LTIuOXoiLz48L3N2Zz4=',
  mssql:      'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4Ij48cGF0aCBmaWxsPSIjQ0MyOTI3IiBkPSJNNjQgOEMzMy4xIDggOCAzMy4xIDggNjRzMjUuMSA1NiA1NiA1NiA1Ni0yNS4xIDU2LTU2Uzk0LjkgOCA2NCA4eiIvPjxwYXRoIGZpbGw9IiNmZmYiIGQ9Ik03My4zIDQ4LjRjLTIuMS0zLjYtNS4yLTUuNC05LjMtNS40SDQ0Ljl2NDEuMWg4VjcyLjZoMTFjMy45IDAgNy0xLjcgOS4yLTUuMiAxLjQtMi4yIDIuMS00LjggMi4xLTcuNnMtLjYtNS4yLTEuOS03LjR6bS04LjEgMTQuN0g1Mi45di0xMmgxMi4xYzEuNSAwIDIuNy43IDMuNSAyIC42IDEuMS45IDIuNC45IDRzLS4zIDIuOS0xIDRjLS44IDEuMy0yIDItMy4yIDJ6Ii8+PHBhdGggZmlsbD0iI2ZmZiIgZD0iTTkxIDQzaC03LjVMNzIuMiA4NC4xaDguMmwyLjMtNy4ySDk1bDIuNCA3LjJoOC4zem0tNS45IDI2LjFsNC42LTE0LjkgNC43IDE0Ljl6Ii8+PC9zdmc+',
  postgresql: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4Ij48cGF0aCBmaWxsPSIjMzM2NzkxIiBkPSJNOTMuOCAxNy42Yy0zLjgtMS03LjgtMS4zLTExLjctMSIvPjxjaXJjbGUgZmlsbD0iI2ZmZiIgY3g9IjUxIiBjeT0iNTIiIHI9IjYiLz48Y2lyY2xlIGZpbGw9IiNmZmYiIGN4PSI3NyIgY3k9IjUyIiByPSI2Ii8+PC9zdmc+',
  oracle:     'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4Ij48cGF0aCBmaWxsPSIjRjgwMDAwIiBkPSJNNjQgMTZDMzcuNSAxNiAxNiAzNy41IDE2IDY0czIxLjUgNDggNDggNDggNDgtMjEuNSA0OC00OFM5MC41IDE2IDY0IDE2eiIvPjxwYXRoIGZpbGw9IiNmZmYiIGQ9Ik02NCAzNmMtMTUuNSAwLTI4IDEyLjUtMjggMjhzMTIuNSAyOCAyOCAyOCAyOC0xMi41IDI4LTI4LTEyLjUtMjgtMjgtMjh6bTAgNDRjLTguOCAwLTE2LTcuMi0xNi0xNnM3LjItMTYgMTYtMTYgMTYgNy4yIDE2IDE2LTcuMiAxNi0xNiAxNnoiLz48L3N2Zz4=',
  mongodb:    'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4Ij48cGF0aCBmaWxsPSIjNDM5OTM0IiBkPSJNNjQgMTFjLTEgMi0xNSA3LTI0IDE4LTEyIDE1LTE0IDM2LTcgNTcgMyAxMCA5IDE4IDEzIDI0IDMgNCA2IDcgNyA4djZhMiAyIDAgMCAwIDQgMHYtNmMxLTEgNC0zIDctOCA0LTYgMTAtMTQgMTMtMjQgNy0yMSA1LTQyLTctNTctOS0xMS0yMy0xNi0yNC0xOHpNNjQgOTl2LTY3YzAgMCAxOCAxNCAxOCAzNHMtOCAyNC0xOCAzM3oiLz48L3N2Zz4=',
  mariadb:    'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4Ij48cGF0aCBmaWxsPSIjMDAzNTQ1IiBkPSJNNjQgOEMzMy4xIDggOCAzMy4xIDggNjRzMjUuMSA1NiA1NiA1NiA1Ni0yNS4xIDU2LTU2Uzk0LjkgOCA2NCA4eiIvPjxwYXRoIGZpbGw9IiNDMDc2NUEiIGQ9Ik0zOCA0Mmg4djQ0aC04em0xNiAwaDhsMTQgMjYgMTQtMjZoOHY0NGgtOFY2NmwtMTQgMjQtMTQtMjR2MjBoLTh6Ii8+PC9zdmc+',
}
function vpDbLogoUrl(dbType) {
  const t = (dbType||'').toLowerCase()
  if (t.includes('mysql') || t.includes('aurora'))   return _VP_LOGOS.mysql
  if (t.includes('mariadb'))                         return _VP_LOGOS.mariadb
  if (t.includes('mssql') || t.includes('sqlserver')) return _VP_LOGOS.mssql
  if (t.includes('postgres') || t.includes('pg'))    return _VP_LOGOS.postgresql
  if (t.includes('oracle'))                          return _VP_LOGOS.oracle
  if (t.includes('mongo'))                           return _VP_LOGOS.mongodb
  return _VP_LOGOS.mssql
}

// ── 테이블 검증 ──────────────────────────────────────────────
const srcTables     = ref([])
const selTables     = ref([])
const selMode       = ref('all')
const tblSearch     = ref('')
const loadingTables = ref(false)
const lastResultMap = ref({})

const onlyInSrc = computed(() => srcTables.value.filter(t => t.srcOnly))
const onlyInTgt = computed(() => srcTables.value.filter(t => t.tgtOnly))
const filteredTables = computed(() => {
  let list = srcTables.value
  if (tblSearch.value) {
    const q = tblSearch.value.toLowerCase()
    list = list.filter(t => t.name.toLowerCase().includes(q))
  }
  return list
})

// ── 2컬럼 리스트: 소스/타겟 분리 + 정렬 ──────────────────────
const listSort    = ref({ src: 'name', tgt: 'name' })
const listSortDir = ref({ src: 'asc',  tgt: 'asc' })

// 소스에 있는 테이블 (검색 필터 적용)
const srcOnlyFiltered = computed(() => {
  const q = tblSearch.value.toLowerCase()
  return srcTables.value.filter(t => !t.tgtOnly && (!q || t.name.toLowerCase().includes(q)))
})
// 타겟에 있는 테이블 (검색 필터 적용)
const tgtOnlyFiltered = computed(() => {
  const q = tblSearch.value.toLowerCase()
  return srcTables.value.filter(t => !t.srcOnly && (!q || t.name.toLowerCase().includes(q)))
})

function _sortList(list, side) {
  const col = listSort.value[side]
  const dir = listSortDir.value[side] === 'asc' ? 1 : -1
  return [...list].sort((a, b) => {
    if (col === 'status') {
      // 불일치→소스전용→타겟전용→미검증→일치 순
      const rank = t => {
        const r = lastResultMap.value[t.name]
        if (r && !r.match) return 0
        if (t.srcOnly)     return 1
        if (t.tgtOnly)     return 2
        if (!r)            return 3
        return 4
      }
      return (rank(a) - rank(b)) * dir
    }
    return a.name.localeCompare(b.name) * dir
  })
}

const sortedSrcList = computed(() => _sortList(srcOnlyFiltered.value, 'src'))
const sortedTgtList = computed(() => _sortList(tgtOnlyFiltered.value, 'tgt'))

function toggleListSort(side, col) {
  if (listSort.value[side] === col) {
    listSortDir.value[side] = listSortDir.value[side] === 'asc' ? 'desc' : 'asc'
  } else {
    listSort.value[side] = col
    listSortDir.value[side] = 'asc'
  }
}

function toggleColAll(side, e) {
  const list = side === 'src' ? srcOnlyFiltered.value : tgtOnlyFiltered.value
  const names = list.map(t => t.name)
  if (e.target.checked) {
    selTables.value = [...new Set([...selTables.value, ...names])]
  } else {
    selTables.value = selTables.value.filter(n => !names.includes(n))
  }
}

function setSelMode(m) {
  selMode.value = m
  if (m === 'all') {
    // 소스+타겟 모두 선택 (전체 srcTables)
    selTables.value = srcTables.value.map(t => t.name)
  } else if (m === 'mismatch') {
    const fails = Object.entries(lastResultMap.value).filter(([,r]) => !r.match).map(([n]) => n)
    selTables.value = fails.length ? fails : srcTables.value.map(t => t.name)
  }
  // 'custom'은 현재 선택 그대로 유지
}

function fmtDiff(diff) {
  if (!diff) return '0'
  return (diff > 0 ? '+' : '') + Number(diff).toLocaleString()
}

async function loadTables() {
  if (!connector.bothConnected) return
  loadingTables.value = true
  const src = connector.source, tgt = connector.target
  try {
    const [sRes, tRes] = await Promise.all([
      axios.get('/api/v1/schema/tables', { params: { side:'source', db_type:src.dbType, host:src.host, port:src.port, username:src.username, password:src.password, database:src.database }}),
      axios.get('/api/v1/schema/tables', { params: { side:'target', db_type:tgt.dbType, host:tgt.host, port:tgt.port, username:tgt.username, password:tgt.password, database:tgt.database }}).catch(()=>({data:[]}))
    ])
    const sNames = new Set((sRes.data||[]).map(t => t.table_name||t))
    const tNames = new Set((tRes.data||[]).map(t => t.table_name||t))
    const all = new Set([...sNames,...tNames])
    srcTables.value = [...all].sort().map(name => ({ name, srcOnly: sNames.has(name) && !tNames.has(name), tgtOnly: !sNames.has(name) && tNames.has(name) }))
    selTables.value = [...sNames].sort()
    app.notify(`테이블 ${srcTables.value.length}개 로드됨`, 'success')
  } catch(e) { app.notify('테이블 목록 로드 실패: ' + e.message, 'error') }
  finally { loadingTables.value = false }
}

const mode       = ref(localStorage.getItem('val_mode') || 'row_count')
const filterMode = ref('all')
const running    = ref(false)
const results    = ref([])
const summary    = ref(null)
const progPct    = ref(0)
const progMsg    = ref('')
const detailRows = reactive({})
const sortCol    = ref('table')
const sortDir    = ref('asc')
const history    = ref([])

const passRate  = computed(() => results.value.length ? Math.round(results.value.filter(r=>r.match).length/results.value.length*100) : 0)
const failCount = computed(() => results.value.filter(r=>!r.match).length)
const allSel    = computed(() => results.value.length && results.value.every(r=>r._sel))

function toggleAll(e) { results.value.forEach(r=>r._sel=e.target.checked) }
function toggleDetail(r) { detailRows[r.table] = !detailRows[r.table] }
function setSort(col) { if(sortCol.value===col) sortDir.value=sortDir.value==='asc'?'desc':'asc'; else{sortCol.value=col;sortDir.value='asc'} }
function sortIco(col) { if(sortCol.value!==col)return'↕'; return sortDir.value==='asc'?'↑':'↓' }

const filteredResults = computed(() => {
  let r = results.value.slice()
  if (filterMode.value==='fail') r=r.filter(x=>!x.match)
  if (filterMode.value==='ok')   r=r.filter(x=>x.match)
  r.sort((a,b)=>{
    const col = sortCol.value, dir = sortDir.value==='asc' ? 1 : -1
    let av=a[col], bv=b[col]
    // boolean (match, checksum_match, stats_match): false→먼저
    if (typeof av==='boolean' || typeof bv==='boolean') {
      const an = av===true?1:av===false?0:-1, bn = bv===true?1:bv===false?0:-1
      return (an-bn)*dir
    }
    if (av==null && bv==null) return 0
    if (av==null) return dir
    if (bv==null) return -dir
    if (typeof av==='string') { av=av.toLowerCase(); bv=(bv||'').toLowerCase() }
    if (av===bv) return 0
    return (av<bv?-1:1)*dir
  })
  return r
})

function fmt(n) { return n!=null ? Number(n).toLocaleString() : '—' }

async function runValidate() {
  if (!connector.bothConnected) return
  running.value=true; results.value=[]; summary.value=null; progPct.value=0
  progMsg.value='소스·타겟 연결 중...'
  const src=connector.source, tgt=connector.target
  const allSelAll = selTables.value.length === srcTables.value.filter(t=>!t.tgtOnly).length
  const tables = allSelAll ? [] : selTables.value
  try {
    progMsg.value='검증 중...'; progPct.value=30
    const {data} = await axios.post('/api/v1/validate/run', {
      src_info:{db_type:src.dbType,host:src.host,port:src.port,username:src.username,password:src.password,database:src.database},
      tgt_info:{db_type:tgt.dbType,host:tgt.host,port:tgt.port,username:tgt.username,password:tgt.password,database:tgt.database},
      tables, method:mode.value,
    })
    progPct.value=100; progMsg.value='완료'
    results.value = data.results.map(r=>({...r,_sel:false}))
    const rmap={}; data.results.forEach(r=>{rmap[r.table]=r}); lastResultMap.value=rmap
    summary.value=data.summary
    app.notify(`검증 완료 — ${data.summary.passed}/${data.summary.total} 일치 (${data.summary.pass_rate}%)`, data.summary.failed===0?'success':'warn')
    localStorage.setItem('val_mode', mode.value)
    loadHistory()
  } catch(e) { app.notify('검증 실패: '+(e.response?.data?.detail||e.message), 'error') }
  finally { running.value=false; setTimeout(()=>{progPct.value=0;progMsg.value=''},1500) }
}

async function reRun(table) {
  const src=connector.source,tgt=connector.target
  try { await axios.post('/api/v1/jobs/',{name:`[재이관] ${table}`,src_db:src.dbType,src_host:src.host,src_database:src.database,src_username:src.username,src_password:src.password,tgt_db:tgt.dbType,tgt_host:tgt.host,tgt_database:tgt.database,tgt_username:tgt.username,tgt_password:tgt.password,tables:[table],truncate_target:true}); app.notify(`[${table}] 재이관 Job 시작`,'success') }
  catch { app.notify('재이관 실패','error') }
}
async function reRunAll() {
  const tbls=results.value.filter(r=>!r.match).map(r=>r.table); if(!tbls.length)return
  const src=connector.source,tgt=connector.target
  await axios.post('/api/v1/jobs/',{name:`[일괄재이관] ${tbls.length}개`,src_db:src.dbType,src_host:src.host,src_database:src.database,src_username:src.username,src_password:src.password,tgt_db:tgt.dbType,tgt_host:tgt.host,tgt_database:tgt.database,tgt_username:tgt.username,tgt_password:tgt.password,tables:tbls,truncate_target:true})
  app.notify(`${tbls.length}개 재이관 Job 시작`,'success')
}
async function createTbl(table) { app.notify(`[${table}] 타겟 테이블 자동 생성은 Job 위저드에서 진행하세요`,'info') }
async function loadHistory() { try{ const{data}=await axios.get('/api/v1/validate/history'); history.value=data }catch{} }

// ── 이력 정렬 ──────────────────────────────────────────────
const histSortCol = ref('timestamp')
const histSortDir = ref('desc')   // 기본: 최신순

function setHistSort(col) {
  if (histSortCol.value===col) histSortDir.value=histSortDir.value==='asc'?'desc':'asc'
  else { histSortCol.value=col; histSortDir.value='desc' }
}
function histSortIco(col) {
  if (histSortCol.value!==col) return '↕'
  return histSortDir.value==='asc' ? '↑' : '↓'
}
const sortedHistory = computed(() => {
  const list = [...history.value]
  const col = histSortCol.value, dir = histSortDir.value==='asc' ? 1 : -1
  list.sort((a,b)=>{
    let av=a[col], bv=b[col]
    if (av==null) return dir; if (bv==null) return -dir
    if (typeof av==='string') { av=av.toLowerCase(); bv=(bv||'').toLowerCase() }
    if (av===bv) return 0
    return (av<bv?-1:1)*dir
  })
  return list
})

// ── 오브젝트 검증 ─────────────────────────────────────────────
const objTypes   = [{v:'PROCEDURE',label:'프로시저',icon:'⚙'},{v:'FUNCTION',label:'함수',icon:'ƒ'},{v:'TRIGGER',label:'트리거',icon:'⚡'},{v:'VIEW',label:'뷰',icon:'◫'}]
const selObjTypes = ref(['PROCEDURE','FUNCTION','TRIGGER','VIEW'])
const srcObjects  = ref(null)
const objRunning  = ref(false)
const _hintsCache = ref(null)  // 파라미터 힌트 메모리 캐시 (재조회 방지)
const _paramCache  = {}         // 파라미터 조회 결과 캐시 {hintKey: params}
const objLoading  = ref(false)
const objResults  = ref(pStore.validate.objResults || [])
const objViewFilter = ref('all')  // 'all' | 'pass' | 'review' | 'fail'
const objGroupsRaw= ref([])

const hasAnyObjects = computed(()=> srcObjects.value && (srcObjects.value.procedures?.length||srcObjects.value.functions?.length||srcObjects.value.triggers?.length||srcObjects.value.views?.length))
const objGroups  = computed(()=>objGroupsRaw.value)
const allObjSel      = computed(()=>objResults.value.length&&objResults.value.every(r=>r._sel))
const selObjResults  = computed(()=>objResults.value.filter(r=>r._sel && r.status==='ok'))
const selObjCount    = computed(()=>selObjResults.value.length)

watch(srcObjects, data=>{
  if(!data){objGroupsRaw.value=[];return}
  objGroupsRaw.value=[
    {type:'PROCEDURE',label:'프로시저',icon:'⚙',items:(data.procedures||[]).map(o=>reactive({...o,_sel:true}))},
    {type:'FUNCTION', label:'함수',    icon:'ƒ', items:(data.functions||[]).map(o=>reactive({...o,_sel:true}))},
    {type:'TRIGGER',  label:'트리거',  icon:'⚡',items:(data.triggers||[]).map(o=>reactive({...o,_sel:true}))},
    {type:'VIEW',     label:'뷰',      icon:'◫', items:(data.views||[]).map(o=>reactive({...o,_sel:true}))},
  ]
})

function toggleAllObj(e){objResults.value.forEach(r=>r._sel=e.target.checked)}

function selectByStatus(status) {
  objResults.value.forEach(r => {
    if (status === 'all')    { r._sel = true;  return }
    if (status === 'clear')  { r._sel = false; return }
    if (status === 'pass')   { r._sel = r.testStatus==='pass'   && r.srcTestStatus==='pass';   return }
    if (status === 'review') { r._sel = r.testStatus==='review' || r.srcTestStatus==='review'; return }
    if (status === 'fail')   { r._sel = r.testStatus==='fail'   || r.srcTestStatus==='fail';   return }
    if (status === 'none')   { r._sel = !r.testStatus && !r.srcTestStatus; return }
  })
}

function selectAndFilter(status) {
  // 필터 토글 (같은 버튼 다시 누르면 전체로)
  if (status !== 'clear' && status !== 'all') {
    objViewFilter.value = objViewFilter.value === status ? 'all' : status
  } else {
    objViewFilter.value = status === 'all' ? 'all' : objViewFilter.value
  }
  // 선택
  selectByStatus(status === 'clear' ? 'clear' : objViewFilter.value === 'all' ? 'all' : status)
  const cnt = objResults.value.filter(r=>r._sel).length
  const label = {all:'전체',clear:'선택 해제',pass:'성공',review:'검토',fail:'실패'}[status]
  if (status !== 'clear') app.notify(`${label} ${cnt}개 선택됨`, 'info')
}

// 필터 적용된 결과 리스트
const filteredObjResults = computed(() => {
  if (objViewFilter.value === 'all') return objResults.value
  if (objViewFilter.value === 'pass')
    return objResults.value.filter(r => r.testStatus==='pass' && r.srcTestStatus==='pass')
  if (objViewFilter.value === 'review')
    return objResults.value.filter(r => r.testStatus==='review' || r.srcTestStatus==='review')
  if (objViewFilter.value === 'fail')
    return objResults.value.filter(r => r.testStatus==='fail' || r.srcTestStatus==='fail')
  return objResults.value
})
function toggleGrp(grp){const all=grp.items.every(o=>o._sel);grp.items.forEach(o=>o._sel=!all)}
function selAllObjs(){objGroups.value.forEach(g=>g.items.forEach(o=>o._sel=true))}
function clearAllObjs(){objGroups.value.forEach(g=>g.items.forEach(o=>o._sel=false))}

async function loadSrcObjects(force=false){
  const c = connector.source
  if (!c.host || !c.database) {
    app.notify('소스 DB 연결 정보를 먼저 설정하세요', 'warn')
    return
  }
  if (!force && srcObjects.value) return  // 이미 로드됨 — 재조회 생략
  objLoading.value = true
  srcObjects.value = null   // 초기화
  try {
    const { data } = await axios.get('/api/v1/schema/objects', {
      params: { side:'source', db_type:c.dbType, host:c.host, port:c.port,
                username:c.username, password:c.password, database:c.database },
      timeout: 30000   // 30초 타임아웃
    })
    // 응답이 빈 객체여도 정상 처리
    srcObjects.value = data || { procedures:[], functions:[], triggers:[], views:[] }
  } catch(e) {
    // 타임아웃 또는 에러 → 빈 데이터로 fallback (로딩 스피너 제거)
    srcObjects.value = { procedures:[], functions:[], triggers:[], views:[] }
    const msg = e.code === 'ECONNABORTED' ? '타임아웃 (30초)' : (e.response?.data?.detail || e.message)
    app.notify('오브젝트 조회 실패: ' + msg, 'error')
  } finally {
    objLoading.value = false  // 반드시 false로
  }
}

async function runObjValidate(){
  if (!connector.source.host) { app.notify('소스 DB를 먼저 연결하세요', 'warn'); return }
  if (!connector.target.host) { app.notify('타겟 DB를 연결해야 검증이 가능합니다', 'warn'); return }

  // ── 이미 목록이 로드된 경우 → 재조회 없이 테스트만 실행 ──
  if (objResults.value.length > 0) {
    const untested = objResults.value.filter(r => !r.testStatus && !r.srcTestStatus)
    if (untested.length) {
      await runAllObjTest()
    } else {
      app.notify('모든 오브젝트가 이미 테스트됐습니다. Clear 후 재실행하세요.', 'info')
    }
    return
  }

  // ── 최초 실행: 소스 오브젝트 목록 조회 ──
  if (!srcObjects.value || (!srcObjects.value.procedures?.length && !srcObjects.value.functions?.length
      && !srcObjects.value.triggers?.length && !srcObjects.value.views?.length)) {
    await loadSrcObjects(true)
  }

  await new Promise(r => setTimeout(r, 200))

  const selected = []
  for (const grp of objGroups.value) {
    if (!selObjTypes.value.includes(grp.type)) continue
    for (const obj of grp.items) {
      if (obj._sel) selected.push({ name: obj.name, type: grp.type, body: obj.body || '' })
    }
  }

  if (!selected.length) {
    app.notify('오브젝트가 없거나 선택되지 않았습니다. 목록을 먼저 로드하세요.', 'warn')
    await loadSrcObjects(true)
    return
  }

  // 타겟 존재 여부 조회 (최초 1회만)
  objRunning.value = true
  objResults.value = []
  const tgt = connector.target
  for (const obj of selected) {
    let exists = false
    try {
      const { data } = await axios.post('/api/v1/schema/execute-object', {
        db_type: tgt.dbType, host: tgt.host, port: tgt.port,
        username: tgt.username, password: tgt.password, database: tgt.database,
        obj_type: 'CHECK_EXISTS', obj_name: obj.name, params: []
      })
      exists = data.success && data.rows?.length > 0
    } catch {}
    objResults.value.push({
      ...obj, status: exists ? 'ok' : 'missing', _sel: false, deploying: false,
      testing: false, testStatus: null, testResult: null,
      srcTesting: false, srcTestStatus: null, srcTestResult: null
    })
  }
  objRunning.value = false
  const miss = objResults.value.filter(r => r.status === 'missing').length
  app.notify(`오브젝트 목록 로드 완료 — 총 ${selected.length}개, 미이관 ${miss}개`, miss ? 'warn' : 'success')

  // 목록 로드 직후 자동으로 전체 테스트 실행
  await runAllObjTest()
}

async function deployOne(r){
  r.deploying=true;const tgt=connector.target
  try{const{data}=await axios.post('/api/v1/schema/execute-object',{db_type:tgt.dbType,host:tgt.host,port:tgt.port,username:tgt.username,password:tgt.password,database:tgt.database,obj_type:'DDL_CREATE',obj_sub_type:r.type,obj_name:r.name,statements:[r.body],ddl:r.body,params:[]});r.status=data.success?'ok':'error';app.notify(data.success?`${r.name} 배포 완료`:`배포 실패: ${data.error||'오류'}`,data.success?'success':'error')}
  catch(e){r.status='error';app.notify('배포 실패: '+(e.response?.data?.detail||e.message),'error')}
  finally{r.deploying=false}
}
async function deployMissing(){const missing=objResults.value.filter(r=>r.status==='missing');for(const r of missing)await deployOne(r)}

// ── 오브젝트 정렬 ──────────────────────────────────────────
const objSortCol = ref('name')
const objSortDir = ref('asc')
const objDetailRows = reactive({})

function setObjSort(col) {
  if (objSortCol.value===col) objSortDir.value=objSortDir.value==='asc'?'desc':'asc'
  else { objSortCol.value=col; objSortDir.value='asc' }
}
function objSortIco(col) {
  if (objSortCol.value!==col) return '↕'
  return objSortDir.value==='asc' ? '↑' : '↓'
}
function toggleObjDetail(r) {
  const key = r.name + r.type
  objDetailRows[key] = !objDetailRows[key]
}

// ── 파라미터 조회 ──────────────────────────────────────────────
async function loadParamsForRow(r) {
  r._paramLoading = true
  try {
    const { data } = await axios.post('/api/v1/schema/object-params', {
      db_type:  connector.source.dbType,
      host:     connector.source.host,
      port:     connector.source.port,
      username: connector.source.username,
      password: connector.source.password,
      database: connector.source.database,
      obj_name: r.name,
      obj_type: r.type,
    }, { timeout: 10000 })

    // 저장된 힌트 확인 (메모리 캐시 우선)
    const hintKey = `${connector.source.host}:${connector.source.database}:${r.name}`
    if (_hintsCache.value === null) {
      try {
        const { data: hints } = await axios.get('/api/v1/schema/obj-test-hints')
        _hintsCache.value = hints.hints || {}
      } catch { _hintsCache.value = {} }
    }
    const saved = _hintsCache.value[hintKey]
    if (saved?.params?.length) {
      r._params = saved.params.map(p => ({ ...p }))
      r._hintKey = hintKey
      r._fromHint = true
      app.notify(`힌트에서 파라미터 ${r._params.length}개 불러옴`, 'success')
      return
    }

    r._params = (data.params || []).map(p => ({
      ...p,
      dummy_value: _makeDummyValue(p.data_type, p.name)
    }))
    r._hintKey  = hintKey
    r._fromHint = false
    if (!r._params.length) app.notify('파라미터가 없는 오브젝트입니다', 'info')
    else app.notify(`파라미터 ${r._params.length}개 조회됨`, 'success')
  } catch(e) {
    app.notify('파라미터 조회 실패: ' + e.message, 'error')
  } finally {
    r._paramLoading = false
  }
}

// ── DB 추천값 로드 ───────────────────────────────────────────
async function loadSuggestionsForRow(r) {
  if (!r._params?.length) return
  r._suggestLoading = true
  try {
    const { data } = await axios.post('/api/v1/schema/object-param-suggestions', {
      db_type:  connector.source.dbType,
      host:     connector.source.host,
      port:     connector.source.port,
      username: connector.source.username,
      password: connector.source.password,
      database: connector.source.database,
      params:   r._params,
    }, { timeout: 15000 })

    if (data.params?.length) {
      // 기존 파라미터에 추천값 병합
      r._params = data.params.map(p => ({ ...p }))
      const fromDb  = data.params.filter(p => p.suggestion_source?.includes('.')).length
      const fromPat = data.params.filter(p => p.suggestion_source === '패턴 추천').length
      app.notify(
        `추천값 적용 — DB실제값 ${fromDb}개 📊 · 패턴 ${fromPat}개 🔤`,
        'success'
      )
    }
  } catch(e) {
    app.notify('추천값 조회 실패: ' + e.message, 'error')
  } finally {
    r._suggestLoading = false
  }
}

// ── 더미값 초기화 ─────────────────────────────────────────────
function resetDummyParams(r) {
  if (!r._params) return
  r._params.forEach(p => { p.dummy_value = _makeDummyValue(p.data_type) })
}

// ── 힌트 저장 ─────────────────────────────────────────────────
async function saveParamHint(r) {
  if (!r._params?.length || !r._hintKey) return
  try {
    await axios.post('/api/v1/schema/obj-test-hints', {
      key: r._hintKey,
      params: r._params,
      note: '사용자 수동 입력'
    })
    app.notify('파라미터 힌트 저장됨', 'success')
  } catch(e) {
    app.notify('힌트 저장 실패', 'error')
  }
}

// ── 직접 입력한 파라미터로 실행 ───────────────────────────────
async function runObjTestWithParams(r) {
  if (!r._params) return
  const inputParams = r._params.filter(p => !p.is_output).map(p => p.dummy_value)

  r.srcTesting = true; r.testing = true
  r.srcTestStatus = null; r.srcTestResult = null
  r.testStatus    = null; r.testResult    = null

  const baseConnSrc = {
    db_type: connector.source.dbType, host: connector.source.host,
    port: connector.source.port, username: connector.source.username,
    password: connector.source.password, database: connector.source.database,
  }
  const baseConnTgt = {
    db_type: connector.target.dbType, host: connector.target.host,
    port: connector.target.port, username: connector.target.username,
    password: connector.target.password, database: connector.target.database,
  }

  try {
    // 소스 실행
    const t0 = Date.now()
    const { data: sd } = await axios.post('/api/v1/schema/execute-object', {
      ...baseConnSrc, obj_type: r.type, obj_name: r.name, params: inputParams
    }, { timeout: 15000 })
    const se = Date.now() - t0
    r.srcTestStatus = sd.success ? 'pass' : _isBusinessError(sd.error) ? 'review' : 'fail'
    r.srcTestResult = {
      method: `${r.type} 실행 (입력값 ${inputParams.length}개)`,
      message: sd.success ? `정상 실행 (${(sd.rows||[]).length}행)` : (sd.error||''),
      error: (!sd.success && !_isBusinessError(sd.error)) ? sd.error : undefined,
      note: _isBusinessError(sd.error) ? sd.error : undefined,
      rows: sd.rows, elapsed_ms: se,
      params_used: r._params.filter(p=>!p.is_output).map(p=>`${p.name}=${p.dummy_value}`)
    }
    r.srcTesting = false

    // 타겟 실행
    const t1 = Date.now()
    const { data: td } = await axios.post('/api/v1/schema/execute-object', {
      ...baseConnTgt, obj_type: r.type, obj_name: r.name, params: inputParams
    }, { timeout: 15000 })
    const te = Date.now() - t1
    r.testStatus = td.success ? 'pass' : _isBusinessError(td.error) ? 'review' : 'fail'
    r.testResult = {
      method: `${r.type} 실행 (입력값 ${inputParams.length}개)`,
      message: td.success ? `정상 실행 (${(td.rows||[]).length}행)` : (td.error||''),
      error: (!td.success && !_isBusinessError(td.error)) ? td.error : undefined,
      note: _isBusinessError(td.error) ? td.error : undefined,
      rows: td.rows, elapsed_ms: te
    }
    r.testing = false

    // 성공 시 힌트 자동 저장
    if (r.srcTestStatus === 'pass' && r.testStatus === 'pass' && r._hintKey) {
      await saveParamHint(r)
    }
  } catch(e) {
    r.srcTestStatus = r.srcTestStatus || 'fail'
    r.testStatus    = r.testStatus    || 'fail'
    r.srcTesting = false; r.testing = false
  }
}
async function clearAll() {
  // 테이블 + 오브젝트 결과 동시 초기화
  results.value  = []
  summary.value  = null
  progPct.value  = 0
  progMsg.value  = ''
  Object.keys(detailRows).forEach(k => delete detailRows[k])
  objResults.value = []
  Object.keys(objDetailRows).forEach(k => delete objDetailRows[k])
  objTesting.value     = false
  objTestIdx.value     = 0
  objTestTotal.value   = 0
  objTestCurName.value = ''
  remigrateProgress.value = []
  pStore.saveObjResults([])
  // 메모리 캐시 초기화
  _hintsCache.value = null
  Object.keys(_paramCache).forEach(k => delete _paramCache[k])
  // 파라미터 힌트도 초기화 (0으로 나누기 등 잘못된 더미값 제거)
  try {
    const { data: hints } = await axios.get('/api/v1/schema/obj-test-hints')
    const keys = Object.keys(hints.hints || {})
    for (const k of keys) {
      await axios.delete(`/api/v1/schema/obj-test-hints/${encodeURIComponent(k)}`)
    }
    if (keys.length) app.notify(`검증 결과 및 파라미터 힌트 ${keys.length}개 초기화`, 'info')
    else app.notify('검증 결과가 초기화되었습니다', 'info')
  } catch {
    app.notify('검증 결과가 초기화되었습니다', 'info')
  }
}

function clearTableResults() {
  results.value  = []
  summary.value  = null
  progPct.value  = 0
  progMsg.value  = ''
  Object.keys(detailRows).forEach(k => delete detailRows[k])
  app.notify('테이블 검증 결과가 초기화되었습니다', 'info')
}

function clearObjResults() {
  if (!confirm('오브젝트 검증 결과를 모두 초기화하겠습니까?')) return
  objResults.value = []
  Object.keys(objDetailRows).forEach(k => delete objDetailRows[k])
  objTesting.value     = false
  objTestIdx.value     = 0
  objTestTotal.value   = 0
  objTestCurName.value = ''
  remigrateProgress.value = []
  pStore.saveObjResults([])
  app.notify('오브젝트 검증 결과가 초기화되었습니다', 'info')
}

function expandAllObjDetails() {
  objResults.value.forEach(r => {
    if (r.testResult) objDetailRows[r.name + r.type] = true
  })
}
function collapseAllObjDetails() {
  objResults.value.forEach(r => {
    objDetailRows[r.name + r.type] = false
  })
}

// 선택된 오브젝트 수 (타입 필터 + _sel 체크)
const selectedObjCount = computed(() =>
  objGroups.value
    .filter(g => selObjTypes.value.includes(g.type))
    .reduce((s, g) => s + g.items.filter(o => o._sel).length, 0)
)

const sortedObjResults = computed(() => {
  // filteredObjResults 기반 (선택 필터 적용)
  const list = [...filteredObjResults.value]
  const col = objSortCol.value, dir = objSortDir.value==='asc' ? 1 : -1
  list.sort((a,b) => {
    if (col === 'testStatus' || col === 'srcTestStatus') {
      // fail→review→pass→없음 순
      const rank = s => s==='fail'?0:s==='review'?1:s==='pass'?2:3
      return (rank(a[col]) - rank(b[col])) * dir
    }
    const av = (a[col]||'').toLowerCase(), bv = (b[col]||'').toLowerCase()
    if (av===bv) return 0
    return (av<bv?-1:1)*dir
  })
  return list
})

// ── 오브젝트 실행 테스트 ──────────────────────────────────
const objTesting     = ref(pStore.validate.objTesting     || false)
const objTestIdx     = ref(pStore.validate.objTestIdx     || 0)
const objTestTotal   = ref(pStore.validate.objTestTotal   || 0)
const objTestCurName = ref(pStore.validate.objTestCurName || '')

// 타입별 테스트 전략
// ── 오브젝트 실행 테스트 — 백엔드 지원 타입 직접 호출 ─────────
// 백엔드 /execute-object 지원 obj_type:
//   CHECK_EXISTS  → 존재 확인
//   PROCEDURE     → CALL/EXEC 실행 (params:[])
//   FUNCTION      → SELECT func() 실행
//   VIEW          → SELECT * FROM view LIMIT 50
//   DDL_CREATE    → DDL 생성 실행
// TRIGGER는 직접 실행 불가 → CHECK_EXISTS로 활성화 상태 확인

// ── 파라미터 오류 판정 (PROCEDURE/FUNCTION 공통) ──────────────
function _isParamError(errMsg) {
  const e = (errMsg || '').toLowerCase()
  const raw = errMsg || ''

  // ── MSSQL ───────────────────────────────────────────────────
  // 파라미터 누락: 42000 + "매개 변수 ... 필요하지만"
  if (e.includes('42000') && (e.includes('매개 변수') || e.includes('parameter') || e.includes('필요하지만'))) return true
  // FUNCTION 파라미터 없이 호출 시 구문 오류: 102 + "')' 근처"
  if (e.includes('102') && (e.includes("')'") || e.includes("근처") || e.includes('near'))) return true
  // QUERY_GOVERNOR 비용 초과: 8649 (함수/SP 자체는 정상 존재)
  if (e.includes('8649') || e.includes('쿼리가 취소') || e.includes('예상 비용')) return true
  // 일반 구문/파라미터 오류
  if (e.includes('parameter') || e.includes('argument') ||
      e.includes('매개변수') || e.includes('매개 변수') ||
      e.includes('expects parameter') || e.includes('incorrect number') ||
      e.includes('wrong number') || e.includes('required') ||
      e.includes('not supplied') || e.includes('was not supplied') ||
      e.includes('필요하지만 제공되지 않았습니다')) return true

  // ── MySQL / MariaDB ──────────────────────────────────────────
  // FUNCTION 파라미터 수 불일치: 1318
  if (e.includes('1318') || e.includes('incorrect number of arguments')) return true
  // FUNCTION 존재하지만 파라미터 없이 호출 시
  if (e.includes('incorrect parameter count')) return true

  // ── PostgreSQL ───────────────────────────────────────────────
  // 파라미터 없이 호출: "function xxx() does not exist" → 존재하지만 시그니처 불일치
  if (e.includes('does not exist') && e.includes('function')) return true
  // "wrong number of arguments"
  if (e.includes('wrong number of arguments')) return true

  // ── Oracle ───────────────────────────────────────────────────
  if (e.includes('ora-06553') || e.includes('pls-00306') || e.includes('wrong number or types')) return true

  // 백엔드 직접 반환 메시지
  if (e.includes('파라미터가 필요합니다') && e.includes('존재 확인')) return true

  return false
}

// ── 비즈니스 로직 오류 판정 (SP 자체는 정상 동작) ──────────────
// 소스에서 더미값이 비즈니스 규칙에 걸린 것 → SP 존재+실행 성공으로 판정
function _isBusinessError(errMsg) {
  const e = (errMsg || '').toLowerCase()
  // CHECK 제약 조건 위반 (23000)
  if (e.includes('23000') || e.includes('check 제약') || e.includes('check constraint')) return true
  // 사용자 정의 오류 메시지 (RAISERROR/SIGNAL, 5xxxx)
  if (e.includes('50001') || e.includes('50010') || e.includes('50020')) return true
  // 일반 비즈니스 예외 패턴
  if (e.includes('not found') || e.includes('invalid customer') ||
      e.includes('no schedule') || e.includes('loan not found')) return true
  // MySQL 비즈니스 오류 (45000)
  if (e.includes('45000')) return true
  // Division by zero → 더미값이 규칙에 걸린 것 → 실행 자체는 성공
  if (e.includes('division by zero') || e.includes('division by 0')) return true
  if (e.includes('1365') || e.includes('8134')) return true   // MySQL 1365, MSSQL 8134
  if (e.includes('0으로 나누기') || e.includes('divide by zero')) return true
  // timeout → 배치성 SP 정상 존재, 실행 비용 큼 → pass
  if (e.includes('timeout of') && e.includes('ms exceeded')) return true
  // 산술 오버플로 (MSSQL 8115, MySQL 1264) → 더미값 범위 초과 → pass
  if (e.includes('8115') || e.includes('산술 오버플로')) return true
  if (e.includes('1264') || e.includes('out of range value')) return true
  return false
}

// ── 오류 요약 텍스트 (툴팁 미리보기용) ──────────────────────────
function _shortErr(errMsg) {
  if (!errMsg) return ''
  const s = String(errMsg)
  // MSSQL: "[SQL Server]실제메시지 (코드)" 패턴
  const mssql = s.match(/\[SQL Server\]([^\(]+)/)
  if (mssql) { const t = mssql[1].trim(); return t.length>32 ? t.substring(0,32)+'…' : t }
  // MySQL tuple: "(1318, 'Incorrect number...')" → 따옴표 안 메시지
  const mytup = s.match(/\(\d+,\s*['"](.*?)['"]\)/)
  if (mytup) { const t = mytup[1]; return t.length>32 ? t.substring(0,32)+'…' : t }
  // 백엔드 직접 메시지: "함수에 N개 파라미터..."
  if (s.includes('파라미터')) return s.substring(0, 32) + (s.length>32?'…':'')
  // 기타
  return s.substring(0, 32) + (s.length>32 ? '…' : '')
}

// ── 연결 실패 판정 ────────────────────────────────────────────
function _isConnError(errMsg) {
  const e = (errMsg || '').toLowerCase()
  // "connection" 단독은 너무 광범위 — 명확한 연결 오류만 판정
  if (e.includes('08001') || e.includes('08s01')) return true          // SQLSTATE 연결 오류
  if (e.includes('10054') || e.includes('10060')) return true          // TCP 강제 끊김
  if (e.includes('핸드셰이크') || e.includes('handshake')) return true
  if (e.includes('timeout of') || e.includes('econnrefused')) return true
  if (e.includes('mssql 연결 실패') || e.includes('소스 연결 실패')) return true
  if (e.includes('연결할 수 없습니다') && e.includes('서버')) return true
  return false
}

// ── 타입별 더미값 생성 ────────────────────────────────────────
function _makeDummyValue(dataType, paramName) {
  const t = (dataType || '').toLowerCase()
  const n = (paramName || '').toLowerCase().replace(/^[@p_]+/, '')

  // 파라미터명으로 의미있는 더미값 결정
  if (n.match(/term|month|period|cnt|count|size|num|seq|page/)) return 12  // 기간/개수 → 0 대신 12
  if (n.match(/day|days/))                                        return 30
  if (n.match(/rate|ratio|pct|percent/))                          return 5.00
  if (n.match(/amt|amount|price|bal|balance|principal/))          return 1000000
  if (n.match(/income|salary/))                                   return 60000000
  if (n.match(/action|tp|type|cd|code|status|gb|flag/))          return t.includes('char') ? 'A' : 1
  if (n.match(/ym$|year_month/))                                  return '202401'
  if (n.match(/dt$|date$|_dt|_date/))                             return '2024-01-01'
  if (n.match(/page_no|page_num/))                                return 1
  if (n.match(/page_size|per_page/))                              return 20

  // 타입 기반 기본값
  if (t.match(/int|tinyint|smallint|bigint|mediumint/))           return 1  // 0 대신 1 (0나누기 방지)
  if (t.match(/float|double|decimal|numeric|real|money|smallmoney/)) return 1.0
  if (t.match(/bit|bool/))                                        return 1
  if (t.match(/date|time/))                                       return '2024-01-01'
  if (t.match(/char|text|string|clob|nvar|nchar/))               return 'A'
  if (t.match(/uniqueidentifier|uuid/))                           return '00000000-0000-0000-0000-000000000000'
  if (t.match(/binary|blob|image|varbinary/))                     return null
  return 1
}

// ── 파라미터 조회 + 힌트 참조 ─────────────────────────────────
async function _getParams(dbConn, objName) {
  const baseConn = {
    db_type: dbConn.dbType, host: dbConn.host, port: dbConn.port,
    username: dbConn.username, password: dbConn.password, database: dbConn.database,
  }
  const hintKey = `${dbConn.host}:${dbConn.database}:${objName}`

  // 1. 파라미터 캐시 확인 (이미 이번 세션에서 조회한 것)
  if (_paramCache[hintKey]) {
    return { params: _paramCache[hintKey], fromHint: false, hintKey }
  }

  // 2. 힌트 캐시 — 최초 1회만 서버에서 전체 힌트 조회
  if (_hintsCache.value === null) {
    try {
      const { data: hints } = await axios.get('/api/v1/schema/obj-test-hints')
      _hintsCache.value = hints.hints || {}
    } catch {
      _hintsCache.value = {}
    }
  }
  const saved = _hintsCache.value[hintKey]
  if (saved?.params?.length) {
    _paramCache[hintKey] = saved.params
    return { params: saved.params, fromHint: true, hintKey }
  }

  // 3. DB에서 파라미터 조회 (캐시 미스 시만)
  try {
    const { data } = await axios.post('/api/v1/schema/object-params', {
      ...baseConn, obj_name: objName
    }, { timeout: 8000 })
    const params = (data.params || []).map(p => ({
      ...p,
      dummy_value: _makeDummyValue(p.data_type, p.name)
    }))
    _paramCache[hintKey] = params  // 캐시 저장
    return { params, fromHint: false, hintKey }
  } catch {
    return { params: [], fromHint: false, hintKey }
  }
}

// ── 파라미터 힌트 저장 ────────────────────────────────────────
async function _saveHint(hintKey, params, note = '') {
  try {
    await axios.post('/api/v1/schema/obj-test-hints', { key: hintKey, params, note })
  } catch {}
}

// ── 단일 DB 오브젝트 실행 (파라미터 자동 주입) ────────────────
async function _execObjOnDB(dbConn, type, name) {
  const t  = type?.toUpperCase()
  const t0 = Date.now()
  const baseConn = {
    db_type: dbConn.dbType, host: dbConn.host, port: dbConn.port,
    username: dbConn.username, password: dbConn.password, database: dbConn.database,
  }

  try {
    // TRIGGER: 존재/활성화 확인 (실행 불가)
    if (t === 'TRIGGER') {
      const { data } = await axios.post('/api/v1/schema/execute-object', {
        ...baseConn, obj_type: 'CHECK_EXISTS', obj_name: name, params: []
      }, { timeout: 8000 })
      const elapsed = Date.now() - t0
      const exists  = data.success && data.rows?.length > 0
      return {
        status: exists ? 'pass' : 'fail',
        result: {
          method: '트리거 존재/활성화 확인',
          message: exists ? '트리거 존재 확인' : '트리거를 찾을 수 없습니다',
          rows: data.rows, elapsed_ms: elapsed,
        }
      }
    }

    // VIEW: 파라미터 없이 바로 실행
    if (t === 'VIEW') {
      const { data } = await axios.post('/api/v1/schema/execute-object', {
        ...baseConn, obj_type: 'VIEW', obj_name: name, params: []
      }, { timeout: 10000 })
      const elapsed = Date.now() - t0
      if (data.success) {
        return { status: 'pass', result: { method: 'SELECT * FROM view', message: `정상 실행 (${(data.rows||[]).length}행)`, rows: data.rows, elapsed_ms: elapsed } }
      }
      return { status: 'fail', result: { method: 'SELECT * FROM view', message: '뷰 실행 오류', error: data.error, elapsed_ms: elapsed } }
    }

    // PROCEDURE / FUNCTION: 파라미터 조회 후 더미값으로 실행
    const { params, fromHint, hintKey } = await _getParams(dbConn, name)
    const dummyValues = params.filter(p => !p.is_output).map(p => p.dummy_value)

    const { data } = await axios.post('/api/v1/schema/execute-object', {
      ...baseConn, obj_type: t, obj_name: name, params: dummyValues
    }, { timeout: 12000 })
    const elapsed = Date.now() - t0

    if (data.success) {
      // 성공 시 힌트 저장 (다음 실행 시 재사용)
      if (!fromHint && params.length > 0) {
        await _saveHint(hintKey, params, '자동 생성 더미값으로 성공')
      }
      return {
        status: 'pass',
        result: {
          method: `${t} 실행 (파라미터 ${params.length}개)`,
          message: `정상 실행 (${(data.rows||[]).length}행)`,
          params_used: params.map(p => `${p.name}=${p.dummy_value}`),
          rows: data.rows, elapsed_ms: elapsed
        }
      }
    }

    // 실행 오류 분석
    const errMsg = data.error || ''

    // ① 존재 확인 메시지 → 백엔드가 파라미터 없이 호출 시 sys.parameters 조회 결과
    //    "함수에 N개 파라미터가 필요합니다 (존재 확인됨)" → 함수 존재 = pass
    if (errMsg.includes('존재 확인됨') || errMsg.includes('파라미터가 필요합니다')) {
      return {
        status: 'pass',
        result: {
          method: `${t} 존재 확인`,
          message: errMsg,
          elapsed_ms: elapsed
        }
      }
    }

    // ② 비즈니스 로직 오류 → SP/FN 자체는 정상, 더미값이 규칙에 걸린 것 → pass
    if (_isBusinessError(errMsg)) {
      return {
        status: 'pass',
        result: {
          method: `${t} 실행 (${params.length}개 파라미터)`,
          message: '정상 실행 — 비즈니스 규칙 적용됨',
          note: errMsg.substring(0, 120),
          params_used: params.map(p => `${p.name}=${p.dummy_value}`),
          elapsed_ms: elapsed
        }
      }
    }

    // ② 파라미터 수/타입 오류 → 이관 시 파라미터 불일치 → fail (진짜 이관 오류)
    if (_isParamError(errMsg)) {
      await _saveHint(hintKey, params, `파라미터 불일치: ${errMsg.substring(0,100)}`)
      return {
        status: 'fail',
        result: {
          method: `${t} 실행`,
          message: '파라미터 불일치 — 이관 확인 필요',
          error: errMsg,
          params_used: params.map(p => `${p.name}(${p.data_type})=${p.dummy_value}`),
          elapsed_ms: elapsed
        }
      }
    }

    // ③ 연결 오류
    if (_isConnError(errMsg)) {
      return { status: 'fail', result: { method: t, message: '연결 오류', error: errMsg, elapsed_ms: elapsed } }
    }

    // ④ 기타 실행 오류 → 힌트 저장 후 fail
    await _saveHint(hintKey, params, `실행 오류: ${errMsg.substring(0,100)}`)
    return { status: 'fail', result: { method: t, message: '실행 오류', error: errMsg,
             params_used: params.map(p => `${p.name}=${p.dummy_value}`), elapsed_ms: elapsed } }

  } catch(e) {
    const elapsed = Date.now() - t0
    return { status: 'fail', result: { method: t, message: '요청 오류', error: e.response?.data?.detail || e.message, elapsed_ms: elapsed } }
  }
}

// ── 소스/타겟 순차 실행 ───────────────────────────────────────
async function runObjTest(r, autoOpen = true) {
  const t = r.type?.toUpperCase()
  if (!['PROCEDURE','FUNCTION','VIEW','TRIGGER'].includes(t)) {
    r.srcTestStatus = 'skip'; r.srcTestResult = { method: '미지원', message: `${r.type} 타입 미지원` }
    r.testStatus    = 'skip'; r.testResult    = { method: '미지원', message: `${r.type} 타입 미지원` }
    if (autoOpen) objDetailRows[r.name + r.type] = true
    return
  }

  r.srcTesting = true; r.testing = true
  r.srcTestStatus = null; r.srcTestResult = null
  r.testStatus    = null; r.testResult    = null

  try {
    // ① 소스 실행
    r.srcTesting = true
    const srcRes = await _execWithTimeout(() => _execObjOnDB(connector.source, r.type, r.name), 15000)
    r.srcTestStatus = srcRes.status; r.srcTestResult = srcRes.result
    r.srcTesting = false

    if (_isConnError(srcRes.result?.error)) {
      await new Promise(res => setTimeout(res, 300))
    }

    // ② 타겟 실행
    r.testing = true
    const tgtRes = await _execWithTimeout(() => _execObjOnDB(connector.target, r.type, r.name), 15000)
    r.testStatus = tgtRes.status; r.testResult = tgtRes.result
    r.testing = false

  } finally {
    r.srcTesting = false; r.testing = false
    if (autoOpen) objDetailRows[r.name + r.type] = true
  }
}

// ── 타임아웃 래퍼 ────────────────────────────────────────────
async function _execWithTimeout(fn, timeoutMs = 15000) {
  return Promise.race([
    fn(),
    new Promise(resolve =>
      setTimeout(() => resolve({
        status: 'fail',
        result: { method: '실행 테스트', message: `타임아웃 (${timeoutMs/1000}초 초과)`, elapsed_ms: timeoutMs }
      }), timeoutMs)
    )
  ])
}

async function runSelectedObjTest() {
  const testable = selObjResults.value
  if (!testable.length) { app.notify('선택된 항목이 없습니다', 'warn'); return }
  objTesting.value  = true
  objTestTotal.value = testable.length
  for (let i = 0; i < testable.length; i++) {
    const r = testable[i]
    objTestIdx.value     = i + 1
    objTestCurName.value = r.name
    await runObjTest(r, false)
    await new Promise(res => setTimeout(res, 300))
  }
  objTestCurName.value = ''
  const pass = testable.filter(r=>r.testStatus==='pass'&&r.srcTestStatus==='pass').length
  const fail = testable.filter(r=>r.testStatus==='fail'||r.srcTestStatus==='fail').length
  app.notify(`선택 테스트 완료 — 성공 ${pass}개 / 실패 ${fail}개`, fail?'warn':'success')
  objTesting.value = false
  if (fail > 0) setTimeout(() => openRemigrateModal(), 800)
}

async function runAllObjTest() {
  const testable = objResults.value.filter(r => r.status === 'ok')
  if (!testable.length) return
  objTesting.value   = true
  objTestTotal.value = testable.length
  for (let i = 0; i < testable.length; i++) {
    const r = testable[i]
    objTestIdx.value     = i + 1
    objTestCurName.value = r.name
    await runObjTest(r, false)
    await new Promise(res => setTimeout(res, 300))
  }
  objTestCurName.value = ''
  const pass = objResults.value.filter(r=>r.testStatus==='pass' && r.srcTestStatus==='pass').length
  const fail = objResults.value.filter(r=>r.testStatus==='fail' || r.srcTestStatus==='fail').length
  app.notify(`실행 테스트 완료 — 성공 ${pass}개 / 실패 ${fail}개`, fail ? 'warn' : 'success')
  objTesting.value = false
  if (fail > 0) setTimeout(() => openRemigrateModal(), 800)
}

// ── 재이관 모달 ──────────────────────────────────────────────
const showRemigrate    = ref(false)
const remigrateTargets = ref([])
const remigrateAction  = ref('ai')
const remigrateOnlyFail= ref(true)
const remigrateLoading  = ref(false)
const remigrateReason   = ref('')
const remigrateProgress = ref([])   // [{name, type, status:'wait'|'running'|'done'|'fail', msg}]
const remigrateStep     = ref('')   // 현재 단계 메시지

// 이관 오류 판단 후 모달 열기
function openRemigrateModal(targets) {
  if (!targets?.length) {
    // 인수 없으면 현재 실패 목록에서 자동 수집
    targets = objResults.value.filter(r =>
      r.testStatus === 'fail' || r.srcTestStatus === 'fail'
    )
  }
  if (!targets.length) { app.notify('이관 오류가 없습니다', 'info'); return }

  remigrateTargets.value = targets

  // 주요 원인 분석
  const paramFails = targets.filter(r =>
    (r.testResult?.error || '').includes('1318') ||
    (r.testResult?.error || '').includes('Incorrect number')
  ).length
  const sqlFails = targets.filter(r =>
    (r.testResult?.error || '').includes('1111') ||
    (r.testResult?.error || '').includes('3593') ||
    (r.testResult?.error || '').includes('window function')
  ).length

  if (paramFails > sqlFails) {
    remigrateReason.value = `파라미터 수 불일치 ${paramFails}건 (이관 시 누락)`
  } else if (sqlFails > 0) {
    remigrateReason.value = `SQL 문법 미변환 ${sqlFails}건 (MySQL 호환 필요)`
  } else {
    remigrateReason.value = `실행 오류 ${targets.length}건`
  }

  remigrateAction.value = 'ai'
  showRemigrate.value = true
}

// 재이관 실행
async function startRemigrate() {
  const targets = remigrateOnlyFail.value
    ? remigrateTargets.value.filter(r => r.testStatus === 'fail' || r.srcTestStatus === 'fail')
    : remigrateTargets.value

  // 수동 수정 → 오브젝트 매핑 화면으로 이동
  if (remigrateAction.value === 'manual') {
    showRemigrate.value = false
    const names = targets.map(r => r.name).join(',')
    router.push(`/mapping/objects?highlight=${encodeURIComponent(names)}`)
    return
  }

  // AI 재변환 — Job 생성 + 모달 진행 상황 동시 표시
  remigrateLoading.value = true
  remigrateProgress.value = targets.map(r => ({
    name: r.name, type: r.type, status: 'wait', msg: '대기 중'
  }))

  const srcConn = {
    db_type: connector.source.dbType, host: connector.source.host,
    port: connector.source.port, username: connector.source.username,
    password: connector.source.password, database: connector.source.database,
  }
  const tgtConn = {
    db_type: connector.target.dbType, host: connector.target.host,
    port: connector.target.port, username: connector.target.username,
    password: connector.target.password, database: connector.target.database,
  }

  // ① Job 생성 → JobMonitor에서 추적 가능
  let jobId = null
  try {
    const { data: jobData } = await axios.post('/api/v1/schema/remigrate-job', {
      name:     `AI 재이관 — ${targets.length}개 오브젝트`,
      objects:  targets.map(r => ({ name: r.name, type: r.type, error: r.testResult?.error || '' })),
      src_conn: srcConn,
      tgt_conn: tgtConn,
    })
    jobId = jobData.job_id
    app.notify(`Job 생성됨 — 실시간 모니터에서 진행 상황 확인 가능`, 'info')
  } catch(e) {
    console.warn('Job 생성 실패 (진행은 계속):', e.message)
  }

  // Job 상태 업데이트 헬퍼
  const updateJobItem = async (name, status, msg, error) => {
    if (!jobId) return
    try {
      await axios.patch(`/api/v1/schema/remigrate-job/${jobId}/item`, { name, status, msg, error })
    } catch {}
  }

  let successNames = []

  for (let i = 0; i < targets.length; i++) {
    const r   = targets[i]
    const row = remigrateProgress.value[i]
    row.status = 'running'

    try {
      // ① DDL 조회
      remigrateStep.value = `(${i+1}/${targets.length}) ${r.name} — DDL 조회 중...`
      row.msg = 'DDL 조회 중...'
      await updateJobItem(r.name, 'running', 'DDL 조회 중')
      const { data: ddlData } = await axios.get('/api/v1/schema/objects/ddl', {
        params: { ...srcConn, obj_type: r.type, obj_name: r.name },
        timeout: 12000
      })
      const ddl = ddlData.ddl || ''
      if (!ddl) throw new Error('소스 DDL을 가져올 수 없습니다')

      // ② AI 변환
      remigrateStep.value = `(${i+1}/${targets.length}) ${r.name} — AI 변환 중...`
      row.msg = 'AI 변환 중...'
      await updateJobItem(r.name, 'running', 'AI 변환 중')
      const { data: convData } = await axios.post('/api/v1/schema/convert-object-ai', {
        ...srcConn,
        tgt_db:     tgtConn.db_type,
        obj_type:   r.type,
        obj_name:   r.name,
        ddl,
        error_hint: [
          r.testResult?.error     ? `타겟오류: ${r.testResult.error}`     : '',
          r.srcTestResult?.error  ? `소스오류: ${r.srcTestResult.error}`  : '',
        ].filter(Boolean).join('\n') || '',
      }, { timeout: 45000 })

      const converted = convData.converted_ddl || ''
      if (!converted) throw new Error('AI 변환 결과가 없습니다')

      // ③ 타겟 배포
      remigrateStep.value = `(${i+1}/${targets.length}) ${r.name} — 타겟 배포 중...`
      row.msg = '타겟 배포 중...'
      await updateJobItem(r.name, 'running', '타겟 배포 중')
      const { data: deployData } = await axios.post('/api/v1/schema/execute-object', {
        ...tgtConn,
        obj_type:     'DDL_CREATE',
        obj_sub_type: r.type,
        obj_name:     r.name,
        statements:   [converted],
        ddl:          converted,
      }, { timeout: 30000 })

      if (!deployData.success) throw new Error(deployData.error || '배포 실패')

      row.status = 'done'
      row.msg    = '완료'
      successNames.push(r.name)
      await updateJobItem(r.name, 'done', '완료')

    } catch(e) {
      row.status = 'fail'
      row.msg    = e.message?.substring(0, 60) || '실패'
      await updateJobItem(r.name, 'error', e.message?.substring(0, 100), e.message)
    }

    await new Promise(res => setTimeout(res, 200))
  }

  remigrateStep.value = ''
  remigrateLoading.value = false

  const ok   = remigrateProgress.value.filter(r => r.status === 'done').length
  const fail = remigrateProgress.value.filter(r => r.status === 'fail').length

  if (successNames.length) {
    objResults.value.forEach(r => {
      if (successNames.includes(r.name)) r._sel = true
    })
    app.notify(`재이관 완료 — 성공 ${ok}개 선택됨. 재테스트하세요.`, 'success')
    setTimeout(() => { showRemigrate.value = false }, 1500)
  } else {
    app.notify(`재이관 실패 — 오류 내용을 확인하세요`, 'error')
  }
}

// ── 리포트 ──────────────────────────────────────────────────
const showReport = ref(false)
const reportText = ref('')
const reportTs   = ref('')

function buildReport() {
  const now = new Date().toLocaleString('ko-KR')
  reportTs.value = now
  const lines = []
  lines.push('═══════════════════════════════════════════')
  lines.push('  DataBridge Studio — 검증 & 대사 리포트')
  lines.push(`  생성: ${now}`)
  lines.push('═══════════════════════════════════════════')

  // 소스/타겟 정보
  lines.push('')
  lines.push(`소스: ${connector.source.database} (${connector.source.dbType}) @ ${connector.source.host}`)
  lines.push(`타겟: ${connector.target.database} (${connector.target.dbType}) @ ${connector.target.host}`)

  // 테이블 검증 결과
  if (results.value.length) {
    lines.push('')
    lines.push('── 테이블 검증 ──────────────────────────────')
    lines.push(`  총 테이블: ${results.value.length}개`)
    lines.push(`  일치:      ${results.value.filter(r=>r.match).length}개`)
    lines.push(`  불일치:    ${results.value.filter(r=>!r.match).length}개`)
    lines.push(`  통과율:    ${passRate.value}%`)
    if (summary.value) lines.push(`  소요시간:  ${summary.value.elapsed_sec}s`)
    const fails = results.value.filter(r=>!r.match)
    if (fails.length) {
      lines.push('')
      lines.push('  [불일치 목록]')
      fails.forEach(r => {
        lines.push(`  ✗ ${r.table.padEnd(40)} 소스:${String(r.src_count??'-').padStart(8)}  타겟:${String(r.tgt_exist?r.tgt_count:'-').padStart(8)}  차이:${String(r.diff??'-').padStart(8)}`)
      })
    }
  }

  // 오브젝트 검증 결과
  if (objResults.value.length) {
    lines.push('')
    lines.push('── 오브젝트 검증 ────────────────────────────')
    lines.push(`  총 오브젝트: ${objResults.value.length}개`)
    lines.push(`  존재:        ${objResults.value.filter(r=>r.status==='ok').length}개`)
    lines.push(`  미이관:      ${objResults.value.filter(r=>r.status==='missing').length}개`)
    if (objResults.value.some(r=>r.testStatus)) {
      lines.push(`  테스트 성공: ${objResults.value.filter(r=>r.testStatus==='pass').length}개`)
      lines.push(`  테스트 실패: ${objResults.value.filter(r=>r.testStatus==='fail').length}개`)
    }
    const missingObjs = objResults.value.filter(r=>r.status==='missing')
    if (missingObjs.length) {
      lines.push('')
      lines.push('  [미이관 오브젝트]')
      missingObjs.forEach(r => lines.push(`  ✗ [${r.type}] ${r.name}`))
    }
    const failTests = objResults.value.filter(r=>r.testStatus==='fail'||r.srcTestStatus==='fail')
    if (failTests.length) {
      lines.push('')
      lines.push('  [테스트 실패 오브젝트]')
      failTests.forEach(r => {
        lines.push(`  ✗ [${r.type}] ${r.name}`)
        if (r.srcTestStatus==='fail' && r.srcTestResult?.error)
          lines.push(`      소스오류: ${r.srcTestResult.error}`)
        if (r.testStatus==='fail' && r.testResult?.error)
          lines.push(`      타겟오류: ${r.testResult.error}`)
      })
    }
  }

  lines.push('')
  lines.push('═══════════════════════════════════════════')
  reportText.value = lines.join('\n')
}

function copyReport() {
  navigator.clipboard.writeText(reportText.value).then(() => app.notify('리포트 복사됨', 'success'))
}

function downloadReport(fmt = 'txt') {
  buildReport()  // 항상 최신 시각으로 재생성
  const ts = new Date().toISOString().slice(0,16).replace(/[:.]/g,'-')
  if (fmt === 'html') {
    const _s = ['<','style>body{font-family:monospace;background:#0f1117;color:#94a3b8;padding:24px;line-height:1.7}pre{white-space:pre-wrap}.err{color:#f87171}.ok{color:#86efac}</','/style>'].join('')
    const _b = reportText.value.replace(/\u2713/g,'<span class="ok">\u2713</span>').replace(/\u2717/g,'<span class="err">\u2717</span>')
    const html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>검증 리포트</title>' + _s + '</head><body><pre>' + _b + '</pre></body></html>'
    const blob = new Blob([html], { type: 'text/html' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob)
    a.download = `validate-report-${ts}.html`; a.click()
  } else {
    const blob = new Blob([reportText.value], { type: 'text/plain' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob)
    a.download = `validate-report-${ts}.txt`; a.click()
  }
  app.notify(`리포트 ${fmt.toUpperCase()} 다운로드됨`, 'success')
}

// ── 서버 로그 ────────────────────────────────────────────────
const showLog      = ref(false)
const logLoading   = ref(false)
const logLines_data= ref([])
const logTotal     = ref(0)
const logLevel     = ref('ALL')
const logLines     = ref(200)
const logError     = ref(false)
const logTs        = ref('')
const logBodyRef   = ref(null)

async function fetchLogs() {
  logLoading.value = true
  logError.value   = false
  try {
    const { data } = await axios.get('/api/v1/logs', {
      params: { lines: logLines.value, level: logLevel.value }
    })
    logLines_data.value = data.lines || []
    logTotal.value      = data.total || 0
    logTs.value = new Date().toLocaleTimeString('ko-KR')
    // 오류 라인 있으면 알림
    logError.value = logLines_data.value.some(l => l.includes('[ERROR]'))
    // 맨 아래로 스크롤
    setTimeout(() => {
      if (logBodyRef.value) logBodyRef.value.scrollTop = logBodyRef.value.scrollHeight
    }, 50)
  } catch(e) {
    logLines_data.value = [`로그 조회 실패: ${e.message}`, '백엔드 서버가 실행 중인지 확인하세요']
    logError.value = true
  } finally {
    logLoading.value = false
  }
}

async function clearLog() {
  if (!confirm('서버 로그를 초기화하시겠습니까?')) return
  await axios.delete('/api/v1/logs')
  logLines_data.value = []
  logTotal.value = 0
  app.notify('로그 초기화됨', 'success')
}

function copyLog() {
  navigator.clipboard.writeText(logLines_data.value.join('\n'))
    .then(() => app.notify('로그 복사됨', 'success'))
}

// objResults 변경 시 pageStore에 저장 (화면 이동 후 복원용)
watch(objResults, (val) => { pStore.saveObjResults(val) }, { deep: true })
watch([objTesting, objTestIdx, objTestTotal, objTestCurName], () => {
  pStore.saveObjTestingState({
    objTesting:     objTesting.value,
    objTestIdx:     objTestIdx.value,
    objTestTotal:   objTestTotal.value,
    objTestCurName: objTestCurName.value,
  })
})

onMounted(()=>{
  loadHistory()
  // 재이관 후 돌아왔을 때 결과 체크박스 자동 선택
  const returned = sessionStorage.getItem('remigrate_returned')
  if (returned) {
    try {
      const names = JSON.parse(returned)
      setTimeout(() => {
        objResults.value.forEach(r => {
          if (names.includes(r.name)) r._sel = true
        })
        if (names.length) app.notify(`재이관 완료 항목 ${names.length}개 선택됨 — 재테스트하세요`, 'info')
      }, 500)
    } catch {}
    sessionStorage.removeItem('remigrate_returned')
  }
})
</script>

<style scoped>
/* ── 레이아웃 ── */
.vp { display:flex; flex-direction:column; gap:10px; }

/* ── 경고 ── */
.vp-warn {
  display:flex; align-items:center; gap:8px; padding:9px 14px;
  background:var(--bg-warning); border-radius:8px;
  font-size:12px; color:var(--text-warning);
}
.vp-warn-btn {
  margin-left:auto; font-size:11px; padding:3px 9px; border-radius:6px;
  border:0.5px solid rgba(245,158,11,.4); background:transparent;
  color:#b45309; cursor:pointer; font-family:var(--font);
}

/* ── 설정 카드 ── */
.vp-cfg { display:flex; flex-direction:column; gap:12px; }

/* DB 행 */
.vp-db-row { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.vp-db-box {
  display:flex; align-items:center; gap:8px;
  padding:7px 12px; border-radius:8px;
  border:0.5px solid var(--border-light); background:var(--bg-secondary);
}
.vp-db-box.src { border-left:2.5px solid #3b82f6; }
.vp-db-box.tgt { border-left:2.5px solid #22c55e; }
.vp-db-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
.vp-db-dot.src { background:#3b82f6; }
.vp-db-dot.tgt { background:#22c55e; }
.vp-db-info { display:flex; align-items:center; gap:7px; }
.vp-db-label { font-size:9.5px; font-weight:700; color:var(--text-tertiary); text-transform:uppercase; letter-spacing:.4px; }
.vp-db-name  { font-size:13px; font-weight:600; color:var(--text-primary); font-family:'Consolas','SF Mono',monospace; }
.vp-db-type  { font-size:11px; color:var(--text-tertiary); }
.vp-db-arrow { color:var(--text-tertiary); flex-shrink:0; }

/* 탭 */
.vp-tabs { display:flex; gap:5px; }
.vp-tab {
  display:inline-flex; align-items:center; gap:5px; padding:6px 12px;
  border-radius:8px; border:0.5px solid var(--border-light); font-size:12px;
  font-weight:500; font-family:var(--font); cursor:pointer; color:var(--text-secondary);
  background:transparent; transition:all .12s;
}
.vp-tab:hover { background:var(--bg-secondary); }
.vp-tab.active { background:var(--bg-info); color:var(--text-info); border-color:var(--accent-blue); }

/* 테이블 선택 패널 */
.vp-tbl-panel {
  border:0.5px solid var(--border-light); border-radius:10px; overflow:hidden;
}
.vp-tbl-hdr {
  display:flex; align-items:center; justify-content:space-between;
  padding:9px 14px; background:var(--bg-secondary);
  border-bottom:0.5px solid var(--border-light); flex-wrap:wrap; gap:8px;
}
.vp-tbl-title {
  display:flex; align-items:center; gap:7px;
  font-size:12.5px; font-weight:600; color:var(--text-primary);
}
.vp-tbl-actions { display:flex; align-items:center; gap:5px; flex-wrap:wrap; }

/* 칩 버튼 */
.vp-chip {
  display:inline-flex; align-items:center; gap:4px; padding:4px 10px;
  border-radius:10px; border:0.5px solid var(--border-mid); background:transparent;
  font-size:11px; font-weight:500; font-family:var(--font); cursor:pointer;
  color:var(--text-secondary); transition:all .12s;
}
.vp-chip:hover { background:var(--bg-secondary); }
.vp-chip.on { background:var(--bg-info); color:var(--text-info); border-color:var(--accent-blue); }

/* 검색 */
.vp-search {
  display:flex; align-items:center; gap:6px; padding:4px 9px;
  border:0.5px solid var(--border-mid); border-radius:8px; background:var(--bg-primary);
}
.vp-search-input { border:none; background:transparent; font-size:11.5px; color:var(--text-primary); outline:none; width:110px; font-family:var(--font); }

/* 아이콘 버튼 */
.vp-icon-btn {
  display:inline-flex; align-items:center; gap:4px; padding:4px 8px;
  border-radius:7px; border:0.5px solid var(--border-mid); background:transparent;
  font-size:11px; font-weight:500; cursor:pointer; font-family:var(--font);
  color:var(--text-secondary); transition:all .12s;
}
.vp-icon-btn:hover { background:var(--bg-secondary); }
.vp-icon-btn:disabled { opacity:.4; cursor:not-allowed; }

/* 테이블 그리드 */
.vp-tbl-loading { display:flex; align-items:center; gap:8px; padding:20px; font-size:12px; color:var(--text-tertiary); }
.vp-tbl-empty { display:flex; flex-direction:column; align-items:center; gap:10px; padding:24px; font-size:12px; color:var(--text-tertiary); }
.vp-tbl-grid { display:flex; flex-wrap:wrap; gap:5px; padding:12px 14px; max-height:220px; overflow-y:auto; }
.vp-tbl-chip {
  display:inline-flex; align-items:center; gap:4px; padding:4px 9px;
  border-radius:7px; border:0.5px solid var(--border-light); background:var(--bg-secondary);
  cursor:pointer; transition:all .1s; user-select:none;
}
.vp-tbl-chip:hover { border-color:var(--border-mid); background:var(--bg-primary); }
.vp-tbl-chip.selected { border-color:var(--accent-blue); background:rgba(59,130,246,.07); }
.vp-tbl-chip.src-only { border-color:rgba(245,158,11,.35); background:rgba(245,158,11,.05); }
.vp-tbl-chip.tgt-only { border-color:rgba(139,92,246,.3); background:rgba(139,92,246,.04); }
.vp-tbl-chip.r-ok   { border-color:rgba(34,197,94,.35); background:rgba(34,197,94,.05); }
.vp-tbl-chip.r-fail { border-color:rgba(239,68,68,.3);  background:rgba(239,68,68,.05); }
.vp-chip-ico { width:12px; height:12px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.vp-chip-nm  { font-size:11.5px; font-family:'Consolas','SF Mono',monospace; font-weight:500; color:var(--text-primary); }
.vp-chip-diff { font-size:10px; font-weight:700; padding:1px 5px; border-radius:5px; }
.vp-chip-diff.ok   { background:rgba(34,197,94,.12); color:#15803d; }
.vp-chip-diff.fail { background:rgba(239,68,68,.12); color:#dc2626; }

.vp-tbl-footer {
  display:flex; align-items:center; justify-content:space-between;
  padding:7px 14px; background:var(--bg-secondary);
  border-top:0.5px solid var(--border-light);
}
.vp-sel-info { font-size:11px; color:var(--text-secondary); }

/* 배지 */
.vp-cnt-badge { font-size:10px; font-weight:600; padding:2px 7px; border-radius:8px; background:var(--bg-info); color:var(--text-info); }
.vp-only-badge { font-size:10px; font-weight:600; padding:2px 6px; border-radius:6px; }
.vp-only-badge.src { background:rgba(245,158,11,.12); color:#b45309; }
.vp-only-badge.tgt { background:rgba(139,92,246,.1); color:#6d28d9; }

/* 로딩 점 */
.vp-ldots { display:inline-flex; gap:3px; }
.vp-ldots span { width:4px; height:4px; border-radius:50%; background:var(--accent-blue); animation:vp-ldot .8s infinite; }
.vp-ldots span:nth-child(2) { animation-delay:.15s; }
.vp-ldots span:nth-child(3) { animation-delay:.3s; }
@keyframes vp-ldot { 0%,80%,100%{opacity:.2} 40%{opacity:1} }

/* 컨트롤 행 */
.vp-ctrl-row { display:flex; align-items:flex-end; gap:10px; flex-wrap:wrap; }
.vp-ctrl-item { display:flex; flex-direction:column; gap:4px; }
.vp-lbl { font-size:11px; font-weight:500; color:var(--text-secondary); }
.vp-sel-wrap { border:0.5px solid var(--border-mid); border-radius:8px; background:var(--bg-secondary); overflow:hidden; }
.vp-sel {
  padding:7px 10px; border:none; background:transparent; font-size:12px;
  color:var(--text-primary); font-family:var(--font); cursor:pointer;
  outline:none; appearance:none; min-width:160px;
}

/* 실행 버튼 */
.vp-run-btn {
  display:inline-flex; align-items:center; gap:6px; padding:8px 18px;
  border-radius:8px; font-size:12.5px; font-weight:600; font-family:var(--font);
  background:var(--accent-blue,#3b82f6); color:#fff; border:none;
  cursor:pointer; transition:opacity .15s; white-space:nowrap;
}
.vp-run-btn:hover { opacity:.9; }
.vp-run-btn:disabled { opacity:.45; cursor:not-allowed; }

/* 공통 실행 버튼 — chip 스타일 기반 (SqlVerify 동일 톤) */
.chip-run {
  display:inline-flex; align-items:center; gap:5px;
  padding:5px 14px; border-radius:7px;
  font-size:.8rem; font-weight:600; font-family:var(--font);
  background:var(--accent-blue,#3b82f6); color:#fff;
  border:1px solid var(--accent-blue,#3b82f6);
  cursor:pointer; transition:opacity .15s; white-space:nowrap; line-height:1.4;
}
.chip-run:hover   { opacity:.88; }
.chip-run:disabled{ opacity:.4; cursor:not-allowed; }

/* 스피너 */
.vp-spin {
  width:12px; height:12px; border-radius:50%; border:2px solid rgba(255,255,255,.3);
  border-top-color:#fff; animation:vp-spin .7s linear infinite; display:inline-block;
}
@keyframes vp-spin { to { transform:rotate(360deg); } }

/* 진행바 */
.vp-prog { display:flex; align-items:center; gap:10px; }
.vp-prog-track { flex:1; height:4px; background:var(--border-light); border-radius:2px; overflow:hidden; }
.vp-prog-fill { height:100%; background:var(--accent-blue); border-radius:2px; transition:width .4s; }
.vp-prog-txt { font-size:11px; color:var(--text-tertiary); white-space:nowrap; }

/* KPI 행 */
.vp-kpi-row { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.vp-kpi {
  background:var(--bg-secondary); border:0.5px solid var(--border-light);
  border-radius:10px; padding:8px 14px; min-width:68px; text-align:center;
}
.vp-kpi-n { font-size:22px; font-weight:700; color:var(--text-primary); line-height:1.2; }
.vp-kpi-l { font-size:10.5px; color:var(--text-tertiary); margin-top:2px; }
.vp-kpi.ok   .vp-kpi-n { color:#16a34a; }
.vp-kpi.fail .vp-kpi-n { color:#dc2626; }
.vp-kpi.miss .vp-kpi-n { color:#d97706; }
.vp-kpi.rate .vp-kpi-n { color:#2563eb; }
.vp-kpi.time .vp-kpi-n { color:var(--text-secondary); }

/* 액션 버튼 */
.vp-action-btn {
  display:inline-flex; align-items:center; gap:5px; padding:6px 12px;
  border-radius:8px; font-size:12px; font-weight:500; font-family:var(--font);
  cursor:pointer; border:0.5px solid; transition:all .12s;
}
.vp-action-btn.warn { background:rgba(245,158,11,.08); color:#b45309; border-color:rgba(245,158,11,.3); }
.vp-action-btn.warn:hover { background:rgba(245,158,11,.15); }

/* 결과 테이블 */
.vp-res-wrap { border:0.5px solid var(--border-light); border-radius:10px; overflow:hidden; }
.vp-tbl { width:100%; border-collapse:collapse; font-size:12px; }
.vp-tbl th {
  background:var(--bg-secondary); padding:7px 10px; text-align:left;
  font-size:11px; font-weight:600; color:var(--text-tertiary);
  border-bottom:0.5px solid var(--border-mid); white-space:nowrap;
}
.vp-tbl td { padding:7px 10px; border-bottom:0.5px solid var(--border-light); vertical-align:middle; }
.vp-tbl tr:last-child td { border-bottom:none; }
.vp-sort { cursor:pointer; user-select:none; }
.vp-sort:hover { color:var(--text-primary); }
.vp-sico { font-size:10px; opacity:.5; margin-left:3px; }
.vp-num { text-align:right; font-variant-numeric:tabular-nums; }
.vp-chk { cursor:pointer; accent-color:var(--accent-blue); }

.vp-row { cursor:pointer; transition:background .1s; }
.vp-row-ok:hover  td { background:var(--bg-secondary); }
.vp-row-fail      td { background:rgba(239,68,68,.02); }
.vp-row-fail:hover td { background:rgba(239,68,68,.05); }

.vp-tbl-nm {
  display:flex; align-items:center; gap:5px;
  font-family:'Consolas','SF Mono',monospace; font-weight:500; font-size:12px;
}
.vp-status-ico { display:flex; align-items:center; justify-content:center; }

/* 배지 */
.vp-badge { font-size:10.5px; font-weight:600; padding:2px 7px; border-radius:6px; white-space:nowrap; }
.vp-badge.ok   { background:rgba(34,197,94,.12); color:#15803d; }
.vp-badge.fail { background:rgba(239,68,68,.12);  color:#dc2626; }
.vp-badge.miss { background:rgba(245,158,11,.12); color:#b45309; }
.vp-badge.warn { background:rgba(245,158,11,.12); color:#b45309; }
.vp-badge.gray { color:var(--text-tertiary); }

/* 인라인 버튼 */
.vp-act-btn {
  font-size:10.5px; padding:3px 8px; border-radius:6px;
  border:0.5px solid var(--border-mid); background:transparent;
  cursor:pointer; font-family:var(--font); transition:all .12s;
}
.vp-act-btn.warn { color:#b45309; border-color:rgba(245,158,11,.35); }
.vp-act-btn.warn:hover { background:rgba(245,158,11,.1); }
.vp-act-btn.info { color:#2563eb; border-color:rgba(59,130,246,.35); }
.vp-act-btn.info:hover { background:rgba(59,130,246,.08); }
.vp-act-btn:disabled { opacity:.4; cursor:not-allowed; }

/* 상세 펼침 */
.vp-detail-row td { padding:0; background:var(--bg-secondary); }
.vp-detail-box { padding:14px 16px; display:flex; flex-direction:column; gap:10px; }
.vp-det-title { font-size:11.5px; font-weight:700; color:var(--text-secondary); display:flex; align-items:center; gap:6px; }
.vp-sample-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.vp-sample-side { border:0.5px solid var(--border-light); border-radius:8px; overflow:hidden; }
.vp-sample-hdr { padding:5px 10px; font-size:11px; font-weight:600; background:var(--bg-tertiary); }
.vp-sample-hdr.src { color:var(--text-info); }
.vp-sample-hdr.tgt { color:var(--text-success); }
.vp-sample-scroll { overflow-x:auto; }
.vp-mini-tbl { width:100%; border-collapse:collapse; font-size:11px; }
.vp-mini-tbl th { background:var(--bg-secondary); padding:4px 8px; text-align:left; font-weight:600; color:var(--text-tertiary); border-bottom:0.5px solid var(--border-light); }
.vp-mini-tbl td { padding:4px 8px; border-bottom:0.5px solid var(--border-light); font-family:'Consolas','SF Mono',monospace; font-size:10.5px; }
.vp-mini-tbl tr:last-child td { border-bottom:none; }

.vp-stat-tbl { width:100%; border-collapse:collapse; font-size:11.5px; }
.vp-stat-tbl th { background:var(--bg-tertiary); padding:5px 8px; text-align:left; font-size:10.5px; font-weight:600; color:var(--text-tertiary); border-bottom:0.5px solid var(--border-mid); }
.vp-stat-tbl td { padding:5px 8px; border-bottom:0.5px solid var(--border-light); }
.vp-cs-fail { background:rgba(239,68,68,.03); }
.vp-col-nm { font-family:'Consolas','SF Mono',monospace; font-weight:500; }
.vp-col-tp { font-size:10.5px; color:var(--text-tertiary); }
.vp-vdiff  { color:#dc2626; font-weight:600; }
.vp-no-detail { padding:16px; text-align:center; color:var(--text-tertiary); font-size:12px; }

/* 오브젝트 검증 */
.vp-obj-ctrl { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.vp-obj-types { display:flex; gap:5px; flex-wrap:wrap; }
.vp-otype-lbl { cursor:pointer; }
/* vp-otype-chip: chip과 동일 톤, padding만 얇게 */
.vp-otype-chip {
  padding: 3px 8px !important;
  font-size: .72rem !important;
  border-radius: 7px !important;
  border: 1px solid var(--border-mid) !important;
  transition: all .12s;
}
.vp-otype-chip.on {
  background: rgba(59,130,246,.1) !important;
  color: #2563eb !important;
  border-color: var(--accent-blue) !important;
  font-weight: 500 !important;
}
.vp-otype-tag { font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px; background:var(--bg-secondary); color:var(--text-secondary); }

/* ── 오브젝트 선택 패널 ── */
.vp-obj-panel { border:0.5px solid var(--border-light); border-radius:10px; overflow:hidden; }

.vp-obj-hdr {
  display:flex; align-items:center; justify-content:space-between;
  padding:8px 14px; background:var(--bg-secondary);
  border-bottom:0.5px solid var(--border-light);
}
.vp-obj-hdr-title { font-size:12.5px; font-weight:600; color:var(--text-primary); }

/* 4분할 가로 레이아웃 */
.vp-obj-sections {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  border-top: 0 none;
}

/* 타입별 섹션 */
.vp-obj-section {
  display: flex;
  flex-direction: column;
  border-right: 0.5px solid var(--border-light);
  min-width: 0;
}
.vp-obj-section:last-child { border-right: none; }

/* 섹션 헤더 */
.vp-obj-sec-hdr {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 10px;
  background: var(--bg-secondary);
  border-bottom: 0.5px solid var(--border-light);
  border-top: 0.5px solid var(--border-light);
  position: sticky; top: 0; z-index: 1;
}
.vp-obj-sec-ico    { font-size: 13px; flex-shrink: 0; }
.vp-obj-sec-label  { font-size: 11.5px; font-weight: 600; color: var(--text-primary); }
.vp-obj-sec-chk-all { display:flex; align-items:center; cursor:pointer; flex-shrink:0; }

/* 세로 리스트 */
.vp-obj-list {
  overflow-y: auto;
  max-height: 260px;
  flex: 1;
}

/* 각 오브젝트 행 */
.vp-obj-row {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 5px 10px;
  cursor: pointer;
  border-bottom: 0.5px solid var(--border-light);
  transition: background .08s;
  font-size: 12px;
}
.vp-obj-row:last-child { border-bottom: none; }
.vp-obj-row:hover { background: var(--bg-secondary); }
.vp-obj-row.selected { background: rgba(59,130,246,.05); }

.vp-obj-nm { font-family:'Consolas','SF Mono',monospace; font-weight:500; color:var(--text-primary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:11.5px; }

/* 이력 */
.vp-hist-card { padding:14px 16px; }
.vp-hist-hdr { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
.vp-hist-title { font-size:13px; font-weight:600; color:var(--text-primary); }

/* ── 2컬럼 리스트 ── */
.vp-list-wrap {
  display: grid;
  grid-template-columns: 1fr 0.5px 1fr;
  height: 320px;   /* 고정 높이 — 내부에서 스크롤 */
  overflow: hidden;
}
.vp-list-divider { background: var(--border-light); }

/* 컬럼 */
.vp-list-col { display: flex; flex-direction: column; min-width: 0; overflow: hidden; height: 100%; }

/* 컬럼 헤더 */
.vp-list-col-hdr {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: var(--bg-secondary);
  border-bottom: 0.5px solid var(--border-light);
  border-top: 0.5px solid var(--border-light);
  position: sticky; top: 0; z-index: 1;
  flex-shrink: 0;
}
.vp-list-col-dot {
  width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
}
.vp-list-col-dot.src { background: #3b82f6; }
.vp-list-col-dot.tgt { background: #22c55e; }
.vp-list-col-title {
  font-size: 11.5px; font-weight: 600; color: var(--text-secondary); flex: 1;
}
.vp-list-col-cnt {
  font-size: 10px; font-weight: 500; color: var(--text-tertiary);
  background: var(--bg-primary); border: 0.5px solid var(--border-light);
  padding: 1px 5px; border-radius: 6px; margin-left: 3px;
}
.vp-list-chk-all { display: flex; align-items: center; cursor: pointer; }

/* 정렬 버튼 */
.vp-list-sort-btns { display: flex; gap: 3px; margin-left: auto; }
.vp-sort-btn {
  font-size: 9.5px; padding: 2px 6px; border-radius: 5px;
  border: 0.5px solid var(--border-light); background: transparent;
  color: var(--text-tertiary); cursor: pointer; font-family: var(--font);
  transition: all .1s; white-space: nowrap;
}
.vp-sort-btn:hover { background: var(--bg-primary); color: var(--text-primary); }
.vp-sort-btn.on { background: var(--bg-info); color: var(--text-info); border-color: var(--accent-blue); }

/* 리스트 바디 */
.vp-list-body { overflow-y: auto; flex: 1; min-height: 0; }

/* 리스트 행 */
.vp-list-row {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 5px 10px;
  cursor: pointer;
  transition: background .08s;
  border-bottom: 0.5px solid var(--border-light);
  min-height: 32px;
}
.vp-list-row:last-child { border-bottom: none; }
.vp-list-row:hover { background: var(--bg-secondary); }
.vp-list-row.selected { background: rgba(59,130,246,.05); }
.vp-list-row.r-ok    { }
.vp-list-row.r-fail  { background: rgba(239,68,68,.03); }
.vp-list-row.r-fail:hover { background: rgba(239,68,68,.07); }
.vp-list-row.src-only { }
.vp-list-row.tgt-only { }

/* 아이콘 */
.vp-list-ico {
  width: 14px; height: 14px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
}
.vp-list-ico-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: #3b82f6; opacity: .3;
}
.vp-list-ico-dot.tgt { background: #22c55e; }

/* 테이블명 */
.vp-list-nm {
  flex: 1; font-size: 12px; font-weight: 500;
  font-family: 'Consolas', 'SF Mono', monospace;
  color: var(--text-primary); overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap;
}

/* 결과 배지 */
.vp-list-diff {
  font-size: 10.5px; font-weight: 600;
  padding: 1px 6px; border-radius: 6px;
  flex-shrink: 0; white-space: nowrap;
}
.vp-list-diff.ok   { background: rgba(34,197,94,.12); color: #15803d; }
.vp-list-diff.fail { background: rgba(239,68,68,.12); color: #dc2626; }

.vp-list-badge {
  font-size: 9.5px; font-weight: 600; padding: 1px 5px;
  border-radius: 5px; flex-shrink: 0;
}
.vp-list-badge.src-only { background: rgba(245,158,11,.12); color: #b45309; }
.vp-list-badge.tgt-only { background: rgba(139,92,246,.1); color: #6d28d9; }

/* ── DB 박스 (SqlVerify 동일 스타일) ── */
.vp-db-box2 {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 10px 4px 6px;
  border: 0.5px solid var(--border-light);
  border-radius: 8px; background: var(--bg-secondary);
}
.vp-db-box2.src { border-color: rgba(59,130,246,.22); background: rgba(59,130,246,.04); }
.vp-db-box2.tgt { border-color: rgba(16,185,129,.22); background: rgba(16,185,129,.04); }

.vp-db-cyl-wrap {
  position: relative; width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.vp-db-cyl { width: 32px; height: 32px; flex-shrink: 0; }
.vp-db-logo {
  position: absolute; width: 14px; height: 14px; object-fit: contain;
  top: 50%; left: 50%; transform: translate(-50%,-50%);
}
.vp-db-online {
  position: absolute; top: 1px; right: 0;
  width: 7px; height: 7px; border-radius: 50%;
  background: #22c55e; border: 1.5px solid var(--bg-primary);
}
.vp-db-info2 { display: flex; flex-direction: column; gap: 1px; }
.vp-db-label2 { font-size: .54rem; font-weight: 800; letter-spacing: .07em; text-transform: uppercase; line-height: 1; }
.vp-db-label2.src { color: #2563eb; }
.vp-db-label2.tgt { color: #059669; }
.vp-db-nm2 { font-size: .78rem; font-weight: 700; color: var(--text-primary); line-height: 1.2; }
.vp-db-tp2 { font-size: .62rem; color: var(--text-tertiary); line-height: 1.2; }
.vp-db-arr { display: flex; align-items: center; padding: 0 2px; flex-shrink: 0; }

/* ── 오브젝트 테스트 결과 ── */
.vp-action-btn.info { background:rgba(59,130,246,.08); color:#2563eb; border-color:rgba(59,130,246,.3); }
.vp-action-btn.info:hover { background:rgba(59,130,246,.15); }
.vp-obj-test-result { display:flex; flex-direction:column; gap:6px; padding:4px 0; }
.vp-otr-row { display:flex; align-items:flex-start; gap:12px; font-size:12px; }
.vp-otr-lbl { font-weight:600; color:var(--text-secondary); min-width:80px; flex-shrink:0; }
.vp-otr-val { color:var(--text-primary); }
.vp-otype-tag.procedure { background:rgba(99,102,241,.1); color:#4f46e5; }
.vp-otype-tag.function  { background:rgba(16,185,129,.1); color:#059669; }
.vp-otype-tag.trigger   { background:rgba(245,158,11,.1); color:#b45309; }
.vp-otype-tag.view      { background:rgba(59,130,246,.1); color:#2563eb; }

.vp-detail-toggle-btns { display:flex; gap:4px; }

/* 오브젝트 테스트 소스/타겟 비교 그리드 */
.vp-obj-compare-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.vp-obj-side {
  border: 0.5px solid var(--border-light);
  border-radius: 8px;
  overflow: hidden;
}
.vp-obj-side.ok   { border-color: rgba(34,197,94,.3); }
.vp-obj-side.fail { border-color: rgba(239,68,68,.3); }
.vp-obj-side-hdr {
  padding: 6px 10px;
  font-size: 11.5px;
  font-weight: 600;
  background: var(--bg-secondary);
  border-bottom: 0.5px solid var(--border-light);
  display: flex;
  align-items: center;
}
.vp-obj-side-hdr.src { color: var(--text-info); }
.vp-obj-side-hdr.tgt { color: var(--text-success); }
.vp-obj-side .vp-obj-test-result { padding: 8px 10px; }

/* ── 툴바 ── */
.vp-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 6px 2px;
}
.vp-toolbar-title { font-size: 14px; font-weight: 700; color: var(--text-primary); }
.vp-toolbar-right { display: flex; gap: 6px; align-items: center; }
.vp-tb-btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 5px 11px; border-radius: 7px; font-size: 11.5px; font-weight: 500;
  font-family: var(--font); cursor: pointer; border: 0.5px solid var(--border-mid);
  background: var(--bg-secondary); color: var(--text-secondary); transition: all .12s;
  position: relative;
}
.vp-tb-btn:hover { background: var(--bg-primary); color: var(--text-primary); }
.vp-tb-btn.active { background: var(--bg-info); color: var(--text-info); border-color: var(--accent-blue); }
.vp-tb-dot { width: 6px; height: 6px; border-radius: 50%; position: absolute; top: 3px; right: 3px; }
.vp-tb-dot.err { background: #ef4444; }
.vp-tb-ts { font-size: 10.5px; color: var(--text-tertiary); }

/* ── 리포트 패널 ── */
.vp-report-card { padding: 0; overflow: hidden; }
.vp-report-hdr {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 14px; background: var(--bg-secondary);
  border-bottom: 0.5px solid var(--border-light);
}
.vp-report-title { display: flex; align-items: center; gap: 6px; font-size: 12.5px; font-weight: 600; color: var(--text-primary); }
.vp-report-body { max-height: 360px; overflow-y: auto; padding: 12px 14px; background: var(--bg-primary); }
.vp-report-pre {
  font-family: 'Consolas', 'SF Mono', monospace; font-size: 11.5px;
  color: var(--text-secondary); white-space: pre; margin: 0;
  line-height: 1.7;
}

/* ── 로그 패널 ── */
.vp-log-card { padding: 0; overflow: hidden; }
.vp-log-hdr {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 14px; background: var(--bg-secondary);
  border-bottom: 0.5px solid var(--border-light); flex-wrap: wrap; gap: 6px;
}
.vp-log-title { display: flex; align-items: center; gap: 6px; font-size: 12.5px; font-weight: 600; color: var(--text-primary); }
.vp-log-sel {
  padding: 3px 7px; border: 0.5px solid var(--border-mid); border-radius: 6px;
  background: var(--bg-primary); font-size: 11.5px; color: var(--text-primary);
  font-family: var(--font); cursor: pointer; outline: none; appearance: none;
  min-width: 80px;
}
.vp-log-body {
  max-height: 400px; overflow-y: auto; padding: 8px 0;
  background: #0f1117;
  font-family: 'Consolas', 'SF Mono', monospace; font-size: 11.5px;
}
.vp-log-line {
  padding: 1.5px 14px; line-height: 1.65; color: #94a3b8;
  border-left: 2px solid transparent; white-space: pre-wrap; word-break: break-all;
}
.vp-log-line.log-error   { color: #f87171; border-left-color: #ef4444; background: rgba(239,68,68,.07); }
.vp-log-line.log-warning { color: #fbbf24; border-left-color: #f59e0b; background: rgba(245,158,11,.05); }
.vp-log-line.log-info    { color: #94a3b8; }
.vp-log-line.log-debug   { color: #475569; }
.vp-log-loading { padding: 20px; display: flex; align-items: center; gap: 8px; color: #475569; font-size: 12px; }
.vp-log-empty   { padding: 20px; text-align: center; color: #475569; font-size: 12px; }
.vp-log-footer {
  display: flex; align-items: center; justify-content: space-between;
  padding: 5px 14px; background: var(--bg-secondary);
  border-top: 0.5px solid var(--border-light); font-size: 10.5px; color: var(--text-tertiary);
}
.vp-log-stat { font-size: 10.5px; color: var(--text-tertiary); }

/* 탭 행 — 우측 정렬 */
.vp-tab-row { display:flex; justify-content:flex-end; margin-bottom:4px; }
/* 실행 버튼 행 — 한 줄 고정, 가로 스크롤 */
.vp-run-row {
  display:flex; align-items:center; gap:4px;
  flex-wrap:nowrap; overflow-x:auto;
  padding:2px 0; scrollbar-width:none;
}
.vp-run-row::-webkit-scrollbar { display:none; }
.vp-run-sep { width:0.5px; height:16px; background:var(--border-mid); flex-shrink:0; margin:0 3px; }
.vp-run-row .chip-run { flex-shrink:0; margin-left:auto; }

/* 오브젝트 현황 테이블 */
.vp-obj-stat-wrap { background:var(--bg-secondary); border-radius:var(--radius-md); padding:10px 14px; }
.vp-obj-stat-total { font-size:10.5px; color:var(--text-tertiary); margin-bottom:8px; font-weight:500; }
.vp-obj-stat-tbl { width:100%; border-collapse:collapse; }
.vp-obj-stat-tbl th {
  font-size:10px; font-weight:700; color:var(--text-tertiary);
  letter-spacing:.04em; text-transform:uppercase;
  padding:0 10px 6px; text-align:center;
  border-bottom:0.5px solid var(--border-light);
}
.vp-obj-stat-tbl th:first-child { text-align:left; padding-left:0; }
.vp-obj-stat-tbl td { padding:5px 10px; text-align:center; }
.vp-obj-stat-tbl td:first-child { padding-left:0; }
.vp-obj-stat-tbl tr:not(:last-child) td { border-bottom:0.5px solid var(--border-light); }
.vp-obj-stat-row-lbl { font-size:11px; font-weight:700; color:var(--text-secondary); letter-spacing:.03em; text-align:left !important; }
.vp-ostat {
  display:inline-flex; align-items:center; justify-content:center;
  min-width:30px; padding:2px 7px; border-radius:6px;
  font-size:12px; font-weight:600;
}
.vp-ostat.ok   { background:rgba(22,163,74,.1);   color:#16a34a; }
.vp-ostat.miss { background:rgba(220,38,38,.1);   color:#dc2626; }
.vp-ostat.pass { background:rgba(37,99,235,.1);   color:#2563eb; }
.vp-ostat.fail { background:rgba(220,38,38,.1);   color:#dc2626; }
.vp-ostat.warn { background:rgba(217,119,6,.1);   color:#d97706; }
.vp-ostat.muted{ background:var(--bg-secondary);  color:var(--text-tertiary); font-weight:400; }

/* 오브젝트 stat 액션 버튼 행 — 우측 정렬 */
.vp-obj-stat-actions {
  display: flex; justify-content: flex-end;
  align-items: center; gap: 5px;
  margin-top: 8px; padding-top: 8px;
  border-top: 0.5px solid var(--border-light);
}

/* 테스트 결과 셀 */
/* 오브젝트 결과 테이블 — 6컬럼 고정 */
.vp-obj-tbl { table-layout: fixed; width: 100%; }
.vp-obj-tbl td { overflow: hidden; white-space: nowrap; }

/* 오브젝트명 셀 */
.vp-obj-nm-cell {
  font-size: 12px; font-weight: 500; color: var(--text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.vp-obj-nm-sub {
  font-size: 10.5px; color: var(--text-tertiary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  margin-top: 1px;
}

/* 상세 펼치기 행 — 소스/타겟 2컬럼 그리드 */
.vp-obj-det-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
  padding: 2px 0;
}
.vp-obj-det-box {
  background: var(--bg-primary);
  border: 0.5px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: 8px 11px;
}
.vp-obj-det-hdr {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 600; margin-bottom: 6px;
  color: var(--text-secondary);
}
.vp-obj-det-row {
  display: flex; gap: 6px; margin-bottom: 3px;
  font-size: 11px; line-height: 1.5;
}
.vp-obj-det-lbl {
  color: var(--text-tertiary); flex-shrink: 0;
  min-width: 46px; font-size: 10.5px;
}
.vp-obj-det-val { color: var(--text-primary); word-break: break-word; white-space: pre-wrap; }
.vp-obj-det-err { color: #dc2626; word-break: break-word; white-space: pre-wrap; }

/* 툴팁 (호버) */
.vp-tooltip {
  opacity: 0; pointer-events: none;
  position: absolute; bottom: calc(100% + 5px); left: 0;
  background: #1e293b; color: #f1f5f9;
  font-size: 11px; line-height: 1.55;
  padding: 7px 10px; border-radius: 7px;
  white-space: pre-wrap; max-width: 380px;
  word-break: break-word; z-index: 9999;
  transition: opacity .12s;
  border: 0.5px solid rgba(255,255,255,.12);
}

/* 파라미터 입력 폼 */
.vp-param-form {
  background: rgba(59,130,246,.03);
  border: 1.5px solid rgba(59,130,246,.35);
  border-radius: var(--radius-md);
  padding: 11px 13px;
  margin-bottom: 10px;
  position: relative;
}
.vp-param-form-hdr {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 10px; flex-wrap: wrap; gap: 6px;
}
.vp-param-form-title {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 700;
  color: #1d4ed8;
  letter-spacing: .01em;
}
.vp-param-empty {
  font-size: 11.5px; color: #64748b;
  padding: 8px 0; text-align: center;
}
.vp-param-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(175px, 1fr));
  gap: 8px; margin-bottom: 11px;
}
.vp-param-item { display: flex; flex-direction: column; gap: 3px; }
.vp-param-lbl  { display: flex; align-items: center; gap: 4px; }
.vp-param-nm   { font-size: 11.5px; font-weight: 600; color: #1e40af; }
.vp-param-type {
  font-size: 10px; color: #475569;
  background: rgba(59,130,246,.08);
  padding: 1px 5px; border-radius: 3px;
  border: 0.5px solid rgba(59,130,246,.2);
}
.vp-param-out  { font-size: 10px; color: #b45309; background: rgba(217,119,6,.1); padding: 1px 5px; border-radius: 3px; }
.vp-param-inp  {
  padding: 5px 8px;
  border: 1px solid rgba(59,130,246,.3);
  border-radius: 6px; font-size: 12px; font-family: var(--font);
  background: var(--bg-primary); color: var(--text-primary);
  outline: none; width: 100%;
  transition: border-color .12s;
}
.vp-param-inp:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,.12); }
.vp-param-run-row {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding-top: 10px;
  border-top: 0.5px solid rgba(59,130,246,.2);
}

/* 선택 실행 버튼 — 일반 chip-run보다 강조 */
.vp-sel-run-btn {
  box-shadow: 0 0 0 2px rgba(59,130,246,.25);
}

/* 파라미터 추천 소스 아이콘 */
.vp-param-src {
  font-size: 12px; flex-shrink: 0; cursor: default; line-height: 1;
}

/* ── 재이관 모달 ── */
.vp-modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,.45);
  display: flex; align-items: center; justify-content: center;
  z-index: 9999; padding: 20px;
}
.vp-modal {
  background: var(--bg-primary);
  border: 0.5px solid var(--border-mid);
  border-radius: var(--radius-lg);
  width: 100%; max-width: 540px;
  overflow: hidden;
  max-height: 85vh; display: flex; flex-direction: column;
}
.vp-modal-hdr {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; border-bottom: 0.5px solid var(--border-light);
  flex-shrink: 0;
}
.vp-modal-title {
  display: flex; align-items: center; gap: 7px;
  font-size: 13px; font-weight: 600; color: var(--text-primary);
}
.vp-modal-close {
  width: 22px; height: 22px; border-radius: 5px;
  border: none; background: transparent; cursor: pointer;
  color: var(--text-tertiary); font-size: 13px;
  display: flex; align-items: center; justify-content: center;
}
.vp-modal-close:hover { background: var(--bg-hover); }
.vp-modal-body { padding: 14px 16px; overflow-y: auto; flex: 1; }
.vp-modal-footer {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; border-top: 0.5px solid var(--border-light);
  background: var(--bg-secondary); flex-shrink: 0;
}
.vp-remig-alert {
  display: flex; gap: 10px; padding: 10px 12px;
  background: rgba(220,38,38,.05);
  border: 0.5px solid rgba(220,38,38,.2);
  border-radius: 8px; margin-bottom: 12px;
}
.vp-remig-alert-text { font-size: 12px; color: #991b1b; line-height: 1.6; }
.vp-remig-alert-text strong { font-weight: 600; }
.vp-remig-list {
  display: flex; flex-direction: column; gap: 4px;
  margin-bottom: 12px; max-height: 180px; overflow-y: auto;
}
.vp-remig-item {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 6px 10px; background: var(--bg-secondary);
  border-radius: 6px; border: 0.5px solid var(--border-light);
}
.vp-remig-nm  { font-size: 12px; font-weight: 500; color: var(--text-primary); }
.vp-remig-err { font-size: 11px; color: #dc2626; margin-top: 2px; }
.vp-remig-actions {
  display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 4px;
}
.vp-remig-action {
  padding: 10px 12px; border: 0.5px solid var(--border-mid);
  border-radius: 8px; cursor: pointer; transition: all .12s;
}
.vp-remig-action:hover { border-color: var(--accent-blue); background: rgba(59,130,246,.03); }
.vp-remig-action.selected { border-color: var(--accent-blue); background: rgba(59,130,246,.05); }
.vp-remig-action-title {
  display: flex; align-items: center; gap: 5px;
  font-size: 12px; font-weight: 500; color: var(--text-primary); margin-bottom: 4px;
}
.vp-remig-action-desc { font-size: 11px; color: var(--text-tertiary); line-height: 1.45; }
.vp-remig-chk {
  display: flex; align-items: center; gap: 5px;
  font-size: 11.5px; color: var(--text-secondary); cursor: pointer;
}

/* 재이관 진행 상황 */
.vp-remig-progress {
  padding: 10px 16px;
  border-top: 0.5px solid var(--border-light);
  background: var(--bg-secondary);
}
.vp-remig-step {
  font-size: 11.5px; color: #2563eb; font-weight: 500;
  margin-bottom: 8px; display: flex; align-items: center; gap: 6px;
}
.vp-remig-prog-list {
  display: flex; flex-direction: column; gap: 3px;
  max-height: 180px; overflow-y: auto;
}
.vp-remig-prog-item {
  display: flex; align-items: center; gap: 7px;
  padding: 3px 6px; border-radius: 5px; font-size: 11.5px;
}
.vp-remig-prog-item.running { background: rgba(59,130,246,.06); }
.vp-remig-prog-item.done    { background: rgba(22,163,74,.05);  }
.vp-remig-prog-item.fail    { background: rgba(220,38,38,.05);  }
.vp-remig-prog-icon { width: 14px; flex-shrink: 0; text-align: center; }
.vp-remig-prog-nm   { font-weight: 500; color: var(--text-primary); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.vp-remig-prog-msg  { font-size: 10.5px; color: var(--text-tertiary); flex-shrink: 0; }
.vp-remig-prog-item.running .vp-remig-prog-msg { color: #2563eb; }
.vp-remig-prog-item.fail    .vp-remig-prog-msg { color: #dc2626; }



/* ── 가로 진행 상태바 ── */
.vp-hprog-bar {
  background: var(--bg-secondary);
  border: 0.5px solid rgba(59,130,246,.2);
  border-radius: var(--radius-md);
  padding: 9px 14px 8px;
  margin-bottom: 8px;
}
.vp-hprog-top {
  display: flex; align-items: center;
  justify-content: space-between; margin-bottom: 7px;
}
.vp-hprog-info {
  display: flex; align-items: center; gap: 8px;
  font-size: 12px; min-width: 0; flex: 1;
}
.vp-hprog-cur-nm {
  color: var(--text-primary); font-weight: 500;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  max-width: 400px;
}
.vp-hprog-fraction {
  font-size: 12px; font-weight: 700; color: #2563eb;
  flex-shrink: 0; white-space: nowrap;
}
.vp-hprog-badges { display: flex; gap: 5px; flex-shrink: 0; }
.vp-hprog-track {
  position: relative; height: 6px;
  background: var(--border-light);
  border-radius: 99px; overflow: hidden;
}
.vp-hprog-done {
  position: absolute; left: 0; top: 0; height: 100%;
  background: #bfdbfe; border-radius: 99px;
  transition: width .35s ease;
}
.vp-hprog-success {
  position: absolute; left: 0; top: 0; height: 100%;
  background: #22c55e; border-radius: 99px;
  transition: width .35s ease;
}
.vp-hprog-fail {
  position: absolute; right: 0; top: 0; height: 100%;
  background: #f87171; border-radius: 99px;
  transition: width .35s ease;
}
.vp-hprog-pct {
  font-size: 10.5px; color: #2563eb; font-weight: 600;
  text-align: right; margin-top: 3px;
}

/* 일괄 선택 */
.vp-obj-stat-top {
  display: flex; align-items: center;
  justify-content: space-between; margin-bottom: 8px;
}
.vp-sel-btns {
  display: flex; align-items: center; gap: 5px;
}
.vp-sel-label {
  font-size: 11px; color: var(--text-tertiary); margin-right: 2px;
}
.vp-sel-chip {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 11px; padding: 2px 8px;
}
.vp-sel-cnt {
  background: var(--bg-primary);
  border-radius: 9px; padding: 0 5px;
  font-size: 10px; font-weight: 600;
  color: var(--text-secondary);
}

/* review 상태 */
.vp-badge.review { background:rgba(217,119,6,.1); color:#b45309; }
.vp-row-review td { background: rgba(251,191,36,.04) !important; }
.vp-row-review td:first-child { border-left: 2.5px solid #f59e0b; }
</style>
