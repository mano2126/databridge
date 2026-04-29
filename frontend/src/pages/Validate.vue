<template>
  <div class="vp">

    <!-- 미연결 → 인라인 커넥터 선택 패널 -->
    <ConnectPanel v-if="!connector.bothConnected && !_isAutoConnecting" @connected="onConnected" />
    
    <!-- v90.69: 자동 재연결 중 표시 -->
    <div v-if="_isAutoConnecting" class="vp-auto-connect">
      <span class="vp-auto-spinner"></span>
      <span>이전 연결 정보로 자동 접속 중... ({{ connector.source.host }} → {{ connector.target.host }})</span>
    </div>
    
    <!-- v90.72: vp-conn-status 제거 — PageHeader 의 src-db/tgt-db 표시와 중복 -->

        <!-- 이관 진행 중 안내 -->
    <div v-if="migratingNow && connector.bothConnected" class="vp-migrating-warn">
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px;flex-shrink:0">
        <circle cx="8" cy="8" r="6"/><line x1="8" y1="5" x2="8" y2="8.5"/><circle cx="8" cy="11" r=".7" fill="currentColor"/>
      </svg>
      <div>
        <strong>이관 작업이 진행 중입니다.</strong>
        <span style="font-weight:400">
          테이블 구조(스키마) 검증은 가능하지만, 데이터 건수 검증은 이관 완료 후 실행하세요.
          이관 중 MSSQL 연결 수 제한으로 검증이 실패할 수 있습니다.
        </span>
      </div>
      <button class="vp-warn-btn" @click="$router.push('/jobs/monitor')">이관 모니터 →</button>
    </div>

    <!-- ── 상단 컨트롤 바 (PageHeader 공통 스타일) ── -->
    <PageHeader :show-db="true" :src-db="connector.source" :tgt-db="connector.target"
                @disconnect="onDisconnect">
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

      <!-- Row1: 왼쪽=검증방법 설명, 오른쪽=탭 버튼 -->
      <div class="vp-tab-row">
        <!-- 검증방법 설명 (테이블 탭일 때만) -->
        <div v-if="vType==='table'" class="vm-inline-desc">
          <template v-if="mode==='row_count'">
            <span class="vm-icon">🔢</span>
            <div class="vm-info">
              <span class="vm-name">행수 비교</span>
              <span class="vm-badge fast">빠름</span>
              <span class="vm-sep">·</span>
              <span class="vm-detail">소스·타겟 COUNT(*) 비교. 데이터 내용은 검증하지 않음</span>
            </div>
            <div class="vm-tags"><span class="vm-chk on">✓ 행수</span><span class="vm-chk off">✗ 내용</span></div>
          </template>
          <template v-else-if="mode==='checksum'">
            <span class="vm-icon">🔐</span>
            <div class="vm-info">
              <span class="vm-name">체크섬 비교</span>
              <span class="vm-badge slow">느림</span>
              <span class="vm-sep">·</span>
              <span class="vm-detail">행별 MD5 해시 누적 비교. 값이 달라도 탐지 가능. 대형 테이블은 시간 소요</span>
            </div>
            <div class="vm-tags"><span class="vm-chk on">✓ 행수</span><span class="vm-chk on">✓ 데이터 내용</span></div>
          </template>
          <template v-else-if="mode==='sample'">
            <span class="vm-icon">🔍</span>
            <div class="vm-info">
              <span class="vm-name">행수+샘플 비교</span>
              <span class="vm-badge mid">보통</span>
              <span class="vm-sep">·</span>
              <span class="vm-detail">행수 + 상위 5건 실제 값 비교. 오류 유형 빠르게 파악</span>
            </div>
            <div class="vm-tags"><span class="vm-chk on">✓ 행수</span><span class="vm-chk mid">△ 샘플 5건</span></div>
          </template>
          <template v-else-if="mode==='column_stats'">
            <span class="vm-icon">📊</span>
            <div class="vm-info">
              <span class="vm-name">컬럼 통계 비교</span>
              <span class="vm-badge mid">보통</span>
              <span class="vm-sep">·</span>
              <span class="vm-detail">컬럼별 MIN·MAX·AVG·NULL 수 비교. 값 분포 이상 탐지</span>
            </div>
            <div class="vm-tags"><span class="vm-chk on">✓ 행수</span><span class="vm-chk on">✓ MIN/MAX</span><span class="vm-chk on">✓ NULL</span></div>
          </template>
          <template v-else-if="mode==='full'">
            <span class="vm-icon">🛡</span>
            <div class="vm-info">
              <span class="vm-name">전체 검증</span>
              <span class="vm-badge slow">가장 느림</span>
              <span class="vm-sep">·</span>
              <span class="vm-detail">행수·체크섬·샘플·컬럼통계 모두 실행. 가장 정확</span>
            </div>
            <div class="vm-tags"><span class="vm-chk on">✓ 행수</span><span class="vm-chk on">✓ 체크섬</span><span class="vm-chk on">✓ 통계</span></div>
          </template>
        </div>
        <div v-else class="vm-inline-desc"></div>
        <!-- 탭 버튼 -->
        <div class="vp-tabs">
          <button class="vp-tab"
                  :class="{active:vType==='table' && tabTouched, 'vp-pulse-next': connector.bothConnected && !tabTouched && !running && !objRunning}"
                  @click="tabTouched=true; vType='table'; if(!srcTables.length) loadTables()">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px">
              <rect x="1" y="1" width="12" height="12" rx="1.5"/>
              <line x1="1" y1="5" x2="13" y2="5"/><line x1="5" y1="5" x2="5" y2="13"/>
            </svg>
            테이블 검증
          </button>
          <button class="vp-tab"
                  :class="{active:vType==='object' && tabTouched, 'vp-pulse-next': connector.bothConnected && !tabTouched && !running && !objRunning}"
                  @click="tabTouched=true; vType='object'; loadSrcObjects(false)">
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
        <!-- v43: 실행 / 일시정지 / 중단 3단계 버튼 그룹 -->
        <div class="vp-run-grp">
          <!-- 대기 상태: 단일 실행 버튼 -->
          <button v-if="!running && !objRunning && !tblRs.isPaused.value && !objRs.isPaused.value"
                  class="chip chip-run"
                  :class="{'vp-pulse-next': tabTouched && !results.length && !objResults.length && connector.bothConnected &&
                              (vType==='table' ? srcTables.length>0 : hasAnyObjects)}"
                  @click="handleStart"
                  :disabled="aborting || (vType==='table' ? (loadingTables || !connector.bothConnected) : (!connector.source.host))">
            <svg viewBox="0 0 12 12" fill="currentColor" style="width:10px;height:10px"><polygon points="2,1 10,6 2,11"/></svg>
            <template v-if="vType==='table'">
              {{ loadingTables ? '테이블 로딩 중...' : `검증 실행 ${selTables.length ? '('+selTables.length+'개)' : '(전체)'}` }}
            </template>
            <template v-else>
              오브젝트 검증 실행 {{ selectedObjCount ? '('+selectedObjCount+'개)' : '' }}
            </template>
          </button>

          <!-- 실행 중 / 일시정지 됨 : 두 개 버튼 (일시정지·재개 + 중단) -->
          <template v-else>
            <!-- 일시정지 / 재개 토글 -->
            <button class="chip chip-pause"
                    :class="{'paused': (vType==='table' ? tblRs.isPaused.value : objRs.isPaused.value)}"
                    @click="handleRunPause"
                    :disabled="aborting">
              <template v-if="(vType==='table' ? tblRs.isPaused.value : objRs.isPaused.value)">
                <svg viewBox="0 0 12 12" fill="currentColor" style="width:10px;height:10px"><polygon points="2,1 10,6 2,11"/></svg>
                계속
              </template>
              <template v-else>
                <svg viewBox="0 0 12 12" fill="currentColor" style="width:10px;height:10px">
                  <rect x="2.5" y="2" width="2.5" height="8" rx=".3"/>
                  <rect x="7" y="2" width="2.5" height="8" rx=".3"/>
                </svg>
                일시정지
                <span v-if="progTotal > 0 && vType==='table'" class="vp-btn-cnt">{{ progCurrent }}/{{ progTotal }}</span>
              </template>
            </button>

            <!-- 중단 -->
            <button class="chip chip-stop"
                    @click="handleStop"
                    :disabled="aborting">
              <span v-if="aborting" class="vp-spin" style="width:10px;height:10px;border-width:1.5px"></span>
              <svg v-else viewBox="0 0 12 12" fill="currentColor" style="width:9px;height:9px">
                <rect x="2" y="2" width="8" height="8" rx="1"/>
              </svg>
              <template v-if="aborting">중단 중...</template>
              <template v-else>중단</template>
            </button>
          </template>
        </div>

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
                <span v-if="tableMatchInfo.matched_count" class="vp-only-badge" style="background:#dcfce7;color:#166534">매칭 {{ tableMatchInfo.matched_count }}</span>
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

          <!-- v36: bare name 충돌 경고 배너 -->
          <div v-if="!loadingTables && srcTables.length && tableMatchInfo.has_conflict"
               style="margin:8px 12px;padding:10px 12px;border-left:3px solid #d97706;background:#fffbeb;border-radius:4px;font-size:13px;color:#78350f">
            <div style="font-weight:600;margin-bottom:4px">
              ⚠ 테이블명 충돌 {{ tableMatchInfo.conflicts.length }}건 — 검증이 거부될 수 있습니다
            </div>
            <div style="font-size:12px;line-height:1.5">
              소스 DB 에 동일한 이름이 여러 스키마에 존재합니다:
              <span v-for="(c,i) in tableMatchInfo.conflicts.slice(0,5)" :key="c.bare">
                <b>{{ c.bare }}</b>({{ c.schemas.join(', ') }}){{ i < Math.min(tableMatchInfo.conflicts.length,5)-1 ? ', ' : '' }}
              </span>
              <span v-if="tableMatchInfo.conflicts.length > 5"> 외 {{ tableMatchInfo.conflicts.length - 5 }}건</span>
              <br>
              현재 검증은 이름 기반(임시 모드)이라 오판정 가능성이 있어 백엔드가 실행을 거부합니다.
              v2.0 의 name_map 기반 검증에서 완전 해결 예정입니다.
            </div>
          </div>

          <!-- v90.49: schema 정책 표시 + 변경 가능 드롭다운 (본부장님 요청 2026-04-27) -->
          <div v-if="!loadingTables && srcTables.length"
               class="vp-policy-bar">
            <span class="vp-policy-icon">🔗</span>
            <span class="vp-policy-label">매칭 정책:</span>
            <select v-model="schemaStrategy" class="vp-policy-select"
                    title="이관 시 사용한 스키마 정책과 동일해야 정확히 매칭됩니다">
              <option value="underscore">underscore — customer.profile ↔ customer_profile (권장)</option>
              <option value="drop">drop — customer.profile ↔ profile</option>
              <option value="database">database — 별도 DB</option>
            </select>
            <span class="vp-policy-hint">정책 변경 시 매칭 결과가 즉시 갱신됩니다</span>
            <button class="vp-icon-btn" @click="loadTables" :disabled="loadingTables" 
                    style="margin-left:auto" title="정책 적용 후 다시 매칭">
              <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px">
                <polyline points="13,4 9,4 9,8"/><path d="M13,4 a6,6 0 1,1 -2.5,7.5"/>
              </svg>
            </button>
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

          <!-- 2컬럼 리스트 — 페어 행 방식 (소스 기준 정렬, 타겟 같은 행 매칭) -->
          <div v-else class="vp-list-wrap">

            <!-- 공통 헤더 -->
            <div class="vp-pair-hdr">
              <!-- 소스 헤더 -->
              <div class="vp-pair-hdr-col src">
                <label class="vp-list-chk-all">
                  <input type="checkbox"
                    :checked="srcOnlyFiltered.every(t=>selTables.includes(t.name)) && srcOnlyFiltered.length>0"
                    @change="toggleColAll('src', $event)" class="vp-chk"/>
                </label>
                <span class="vp-list-col-dot src"></span>
                <span class="vp-list-col-title">소스 <span class="vp-list-col-cnt">{{ srcOnlyFiltered.length }}</span></span>
                <div class="vp-list-sort-btns">
                  <button class="vp-sort-btn" :class="{on:listSort.src==='name'}" @click="toggleListSort('src','name')" title="이름순">
                    A↕ <span v-if="listSort.src==='name'">{{ listSortDir.src==='asc'?'↑':'↓' }}</span>
                  </button>
                  <button class="vp-sort-btn" :class="{on:listSort.src==='status'}" @click="toggleListSort('src','status')" title="상태순">
                    ●↕ <span v-if="listSort.src==='status'">{{ listSortDir.src==='asc'?'↑':'↓' }}</span>
                  </button>
                </div>
              </div>
              <!-- 구분선 -->
              <div class="vp-list-divider" style="height:36px"></div>
              <!-- 타겟 헤더 -->
              <div class="vp-pair-hdr-col tgt">
                <label class="vp-list-chk-all">
                  <input type="checkbox"
                    :checked="tgtOnlyFiltered.every(t=>selTables.includes(t.name)) && tgtOnlyFiltered.length>0"
                    @change="toggleColAll('tgt', $event)" class="vp-chk"/>
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
            </div>

            <!-- 페어 행 목록 -->
            <div class="vp-pair-body">
              <div v-for="(pair, idx) in pairedRows" :key="idx" class="vp-pair-row"
                :class="{
                  'pair-match':    pair.src && pair.tgt && lastResultMap[pair.src?.name]?.match,
                  'pair-mismatch': pair.src && pair.tgt && lastResultMap[pair.src?.name] && !lastResultMap[pair.src?.name]?.match,
                  'pair-active':   running && (progTable === pair.src?.name || progTable === pair.tgt?.name),
                }">

                <!-- 소스 셀 -->
                <label class="vp-pair-cell src"
                  :class="{
                    selected:   pair.src && selTables.includes(pair.src.name),
                    'src-only': pair.src?.srcOnly,
                    'r-ok':     pair.src && results.length && lastResultMap[pair.src.name]?.match,
                    'r-fail':   pair.src && results.length && lastResultMap[pair.src.name] && !lastResultMap[pair.src.name]?.match,
                    'pair-empty': !pair.src,
                  }">
                  <template v-if="pair.src">
                    <input type="checkbox" :value="pair.src.name" v-model="selTables" class="vp-chk"/>
                    <span class="vp-list-ico">
                      <span v-if="running && progTable === pair.src.name" class="vp-list-ico-spin"></span>
                      <template v-else-if="lastResultMap[pair.src.name]?.match"><svg viewBox="0 0 12 12" fill="none" stroke="#16a34a" stroke-width="2.2" style="width:11px;height:11px"><polyline points="1.5,6 4.5,9.5 10.5,2.5"/></svg></template>
                      <template v-else-if="lastResultMap[pair.src.name] && !lastResultMap[pair.src.name].match"><svg viewBox="0 0 12 12" fill="none" stroke="#dc2626" stroke-width="2" style="width:11px;height:11px"><line x1="2" y1="2" x2="10" y2="10"/><line x1="10" y1="2" x2="2" y2="10"/></svg></template>
                      <template v-else-if="pair.src.srcOnly"><svg viewBox="0 0 12 12" fill="#d97706" style="width:11px;height:11px"><path d="M6 1.5L11 10H1L6 1.5z"/><line x1="6" y1="5" x2="6" y2="7.5" stroke="white" stroke-width="1.2"/><circle cx="6" cy="9" r=".7" fill="white"/></svg></template>
                      <template v-else><svg viewBox="0 0 12 12" fill="none" stroke="#94a3b8" stroke-width="1.4" style="width:11px;height:11px"><ellipse cx="6" cy="6" rx="4.5" ry="2.5"/><circle cx="6" cy="6" r="1.5" fill="#94a3b8" stroke="none"/></svg></template>
                    </span>
                    <span class="vp-list-nm">{{ pair.src.name }}</span>
                    <span v-if="lastResultMap[pair.src.name]" class="vp-list-diff"
                      :class="lastResultMap[pair.src.name].match ? 'ok' : 'fail'">
                      {{ lastResultMap[pair.src.name].match ? '일치' : fmtDiff(lastResultMap[pair.src.name].diff) }}
                    </span>
                    <span v-else-if="pair.src.srcOnly" class="vp-list-badge src-only">소스전용</span>
                  </template>
                  <template v-else>
                    <span class="vp-pair-empty-cell">—</span>
                  </template>
                </label>

                <!-- 구분선 -->
                <div class="vp-list-divider" style="height:30px;align-self:center"></div>

                <!-- 타겟 셀 -->
                <label class="vp-pair-cell tgt"
                  :class="{
                    selected:   pair.tgt && selTables.includes(pair.tgt.name),
                    'tgt-only': pair.tgt?.tgtOnly,
                    'r-ok':     pair.tgt && results.length && lastResultMap[pair.tgt.name]?.match,
                    'r-fail':   pair.tgt && results.length && lastResultMap[pair.tgt.name] && !lastResultMap[pair.tgt.name]?.match,
                    'pair-empty': !pair.tgt,
                  }">
                  <template v-if="pair.tgt">
                    <input type="checkbox" :value="pair.tgt.name" v-model="selTables" class="vp-chk"/>
                    <span class="vp-list-ico">
                      <span v-if="running && progTable === pair.tgt.name" class="vp-list-ico-spin"></span>
                      <template v-else-if="lastResultMap[pair.tgt.name]?.match"><svg viewBox="0 0 12 12" fill="none" stroke="#16a34a" stroke-width="2.2" style="width:11px;height:11px"><polyline points="1.5,6 4.5,9.5 10.5,2.5"/></svg></template>
                      <template v-else-if="lastResultMap[pair.tgt.name] && !lastResultMap[pair.tgt.name].match"><svg viewBox="0 0 12 12" fill="none" stroke="#dc2626" stroke-width="2" style="width:11px;height:11px"><line x1="2" y1="2" x2="10" y2="10"/><line x1="10" y1="2" x2="2" y2="10"/></svg></template>
                      <template v-else-if="pair.tgt.tgtOnly"><svg viewBox="0 0 12 12" fill="#8b5cf6" style="width:11px;height:11px"><path d="M6 1.5L11 10H1L6 1.5z"/><line x1="6" y1="5" x2="6" y2="7.5" stroke="white" stroke-width="1.2"/><circle cx="6" cy="9" r=".7" fill="white"/></svg></template>
                      <template v-else><svg viewBox="0 0 12 12" fill="none" stroke="#94a3b8" stroke-width="1.4" style="width:11px;height:11px"><ellipse cx="6" cy="6" rx="4.5" ry="2.5"/><circle cx="6" cy="6" r="1.5" fill="#94a3b8" stroke="none"/></svg></template>
                    </span>
                    <span class="vp-list-nm">{{ pair.tgt.name }}</span>
                    <span v-if="lastResultMap[pair.tgt.name]" class="vp-list-diff"
                      :class="lastResultMap[pair.tgt.name].match ? 'ok' : 'fail'">
                      {{ lastResultMap[pair.tgt.name].match ? '일치' : fmtDiff(lastResultMap[pair.tgt.name].diff) }}
                    </span>
                    <span v-else-if="pair.tgt.tgtOnly" class="vp-list-badge tgt-only">타겟전용</span>
                  </template>
                  <template v-else>
                    <span class="vp-pair-empty-cell">—</span>
                  </template>
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


        <!-- KPI + 진행블록 통합 행 -->
        <div v-if="results.length || running" class="vp-kpi-row">
          <!-- v42: 중단됨 배지 -->
          <div v-if="summary?.aborted" class="vp-aborted-badge">
            <svg viewBox="0 0 12 12" fill="currentColor" style="width:10px;height:10px"><rect x="2" y="2" width="8" height="8" rx="1"/></svg>
            검증 중단됨 ({{ results.length }}개 부분 결과)
          </div>
          <!-- v43: 일시정지 중 배지 -->
          <div v-if="tblRs.isPaused.value || objRs.isPaused.value" class="vp-paused-badge">
            <svg viewBox="0 0 12 12" fill="currentColor" style="width:10px;height:10px">
              <rect x="2.5" y="2" width="2.5" height="8" rx=".3"/>
              <rect x="7" y="2" width="2.5" height="8" rx=".3"/>
            </svg>
            일시정지됨 — "계속" 버튼을 눌러 이어서 진행하세요
          </div>
          <!-- KPI 카드들 (결과 있을 때) -->
          <template v-if="results.length">
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
            <div class="vp-kpi-sep"></div>
          </template>

          <!-- 진행 블록 (검증 중일 때 KPI와 나란히) -->
          <div v-if="running" class="vp-kpi-prog-block">
            <div class="vp-kpi-prog-header">
              <span class="vp-spin" style="width:9px;height:9px;border-width:1.5px;flex-shrink:0"></span>
              <span class="vp-kpi-prog-tbl">{{ progTable || '준비 중...' }}</span>
              <span v-if="progTotal>0" class="vp-kpi-prog-cnt">{{ progCurrent }}/{{ progTotal }}</span>
              <span v-if="progTotal>0" class="vp-kpi-prog-pct">{{ progPct }}%</span>
            </div>
            <div class="vp-kpi-prog-bar">
              <div class="vp-kpi-prog-fill" :style="{width:progPct+'%'}"></div>
            </div>
            <div class="vp-kpi-time-row">
              <span class="vp-kpi-time-item">
                <span class="vp-kti-icon">⏱</span>
                <span class="vp-kti-lbl">경과</span>
                <span class="vp-kti-val">{{ fmtElapsed(progElapsed) }}</span>
              </span>
              <span class="vp-kti-sep">·</span>
              <span class="vp-kpi-time-item" :class="{dim: progCurrent < 2}">
                <span class="vp-kti-icon">⏳</span>
                <span class="vp-kti-lbl">남은</span>
                <span class="vp-kti-val">{{ fmtRemainTime(progCurrent, progTotal, progElapsed) }}</span>
              </span>
              <span class="vp-kti-sep">·</span>
              <span class="vp-kpi-time-item" :class="{dim: progCurrent < 2}">
                <span class="vp-kti-icon">🕐</span>
                <span class="vp-kti-lbl">완료</span>
                <span class="vp-kti-val">{{ fmtETA(progCurrent, progTotal, progElapsed) }}</span>
              </span>
            </div>
          </div>

          <!-- 재이관 버튼 -->
          <div style="margin-left:auto;display:flex;gap:6px;align-items:center;flex-shrink:0">
            <!-- v39: 정렬 상태 표시 (최신순 기본) -->
            <span v-if="results.length" class="vp-sort-status">
              <template v-if="!sortUserChosen">
                <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.4" style="width:10px;height:10px"><path d="M6 1v10M2 5l4-4 4 4"/></svg>
                최신 검증 상단
              </template>
              <template v-else>
                정렬: {{ sortCol }} ({{ sortDir==='asc'?'↑':'↓' }})
                <button class="vp-sort-status-clear" @click="resetSortToRecent">최신순 복원</button>
              </template>
            </span>
            <button v-if="failCount>0" class="vp-action-btn warn" @click="reRunAll">
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px"><path d="M1 6a5 5 0 1 0 5-5"/><polyline points="3.5,1 1,1 1,3.5"/></svg>
              불일치 {{ failCount }}개 재이관
            </button>
          </div>
        </div>



        <!-- 결과 테이블 -->
        <div v-if="results.length" class="vp-res-wrap">
          <div class="vp-res-scroll">
          <table class="vp-tbl">
            <colgroup>
              <col style="width:32px">
              <col>
              <col style="width:110px">
              <col style="width:110px">
              <col style="width:80px">
              <template v-if="mode!=='row_count'"><col style="width:90px"></template>
              <template v-if="mode==='column_stats'||mode==='full'"><col style="width:90px"></template>
              <col style="width:72px">
              <col style="width:90px">
            </colgroup>
            <thead>
              <tr>
                <th><input type="checkbox" @change="toggleAll" :checked="allSel" class="vp-chk"/></th>
                <th class="vp-sort" @click="setSort('table')">테이블 <span class="vp-sico">{{ sortIco('table') }}</span></th>
                <th class="vp-sort vp-num" @click="setSort('src_count')">소스 행수 <span class="vp-sico">{{ sortIco('src_count') }}</span></th>
                <th class="vp-sort vp-num" @click="setSort('tgt_count')">타겟 행수 <span class="vp-sico">{{ sortIco('tgt_count') }}</span></th>
                <th class="vp-sort vp-num" @click="setSort('diff')">차이 <span class="vp-sico">{{ sortIco('diff') }}</span></th>
                <th v-if="mode!=='row_count'" class="vp-sort" @click="setSort('checksum_match')">체크섬 <span class="vp-sico">{{ sortIco('checksum_match') }}</span></th>
                <th v-if="mode==='column_stats'||mode==='full'" class="vp-sort" @click="setSort('stats_match')">컬럼통계 <span class="vp-sico">{{ sortIco('stats_match') }}</span></th>
                <th class="vp-sort" style="text-align:center" @click="setSort('match')">상태 <span class="vp-sico">{{ sortIco('match') }}</span></th>
                <th>액션</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="r in filteredResults" :key="r.table">
                <tr class="vp-row" :class="{'vp-row-fail':!r.match,'vp-row-ok':r.match,'vp-row-just-updated':r._justUpdated}" @click="toggleDetail(r)">
                  <td @click.stop><input type="checkbox" v-model="r._sel" class="vp-chk"/></td>
                  <td class="vp-tbl-nm-cell">
                    <div class="vp-tbl-nm">
                      <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.3" style="width:10px;height:10px;flex-shrink:0;opacity:.4"><rect x="1" y="1" width="10" height="10" rx="1"/><line x1="1" y1="4.5" x2="11" y2="4.5"/><line x1="4.5" y1="4.5" x2="4.5" y2="11"/></svg>
                      {{ r.table }}
                    </div>
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
                    <!-- v49: 재이관 배지 우선 표시 (영구 — 다음 수동 검증까지) -->
                    <span v-if="r._remigResult?.status === 'success'"
                          class="vp-remig-badge success"
                          :title="`재이관 성공 (${_fmtRemigMode(r._remigResult.mode)}, ${_fmtRemigAt(r._remigResult.at)})`">
                      ✓ 재이관 성공
                    </span>
                    <span v-else-if="r._remigResult?.status === 'failed'"
                          class="vp-remig-badge failed"
                          :title="`재이관 실패 (${_fmtRemigMode(r._remigResult.mode)}, ${_fmtRemigAt(r._remigResult.at)})`">
                      ✗ 재이관 실패
                    </span>
                    <span v-else class="vp-status-ico">
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
                  <td @click.stop class="vp-act-td">
                    <!-- v49: 우클릭 = 직전 모드 즉시 재시도 (_lastRemigMode 있을 때) -->
                    <button v-if="!r.match" class="vp-act-btn warn"
                            @click="openRemigModal(r)"
                            @contextmenu.prevent="quickRetryRemig(r)"
                            @mousedown="startLongPressRemig(r, $event)"
                            @mouseup="cancelLongPressRemig()"
                            @mouseleave="cancelLongPressRemig()"
                            @touchstart="startLongPressRemig(r, $event)"
                            @touchend="cancelLongPressRemig()"
                            :title="r._lastRemigMode ? '클릭: 옵션 선택 팝업 · 우클릭/길게누름: ' + _fmtRemigMode(r._lastRemigMode) + ' 즉시 재시도' : '재이관 옵션 선택'">
                      재이관
                    </button>
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

                      <!-- 체크섬 상세 -->
                      <template v-if="r.checksum_error || (r.checksum_match === false && !r.src_sample?.length && !r.col_stats?.length)">
                        <div class="vp-det-title" style="color:#d97706">⚠ 체크섬 불일치 상세</div>
                        <div class="vp-checksum-info">
                          <div v-if="r.checksum_error" class="vp-cs-error">
                            <span class="vp-cs-err-label">오류 내용</span>
                            <span class="vp-cs-err-msg">{{ r.checksum_error }}</span>
                          </div>
                          <div v-else class="vp-cs-diff">
                            <div class="vp-cs-row">
                              <span class="vp-cs-side src">소스 해시</span>
                              <code class="vp-cs-hash">{{ r.src_checksum || '—' }}</code>
                            </div>
                            <div class="vp-cs-row">
                              <span class="vp-cs-side tgt">타겟 해시</span>
                              <code class="vp-cs-hash" :class="r.src_checksum !== r.tgt_checksum ? 'diff' : ''">{{ r.tgt_checksum || '—' }}</code>
                            </div>
                          </div>
                          <div class="vp-cs-actions">
                            <div class="vp-cs-hint">
                              행수가 일치하지만 체크섬이 다른 경우, 데이터 타입 변환(datetime 밀리초, 소수점 등) 차이일 수 있습니다.
                            </div>
                            <button class="vp-cs-accept-btn" @click.stop="acceptChecksum(r)">
                              ✓ 허용 처리 (검증 통과로 표시)
                            </button>
                          </div>
                        </div>
                      </template>

                      <div v-if="!r.src_sample?.length && !r.col_stats?.length && !r.checksum_error && r.checksum_match !== false" class="vp-no-detail">
                        샘플 또는 컬럼통계 모드로 재실행하세요
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
          </div>
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

                <!-- 섹션 헤더 (v90.78: 헤더 전체 영역 클릭으로 전체 선택/해제) -->
                <div class="vp-obj-sec-hdr vp-obj-sec-hdr-clickable"
                     @click="toggleGrp(grp)"
                     :title="`${grp.label} 전체 ${grp.items.every(o=>o._sel) ? '해제' : '선택'}`">
                  <label class="vp-obj-sec-chk-all" @click.stop>
                    <input type="checkbox"
                      :checked="grp.items.every(o=>o._sel)"
                      :indeterminate.prop="grp.items.some(o=>o._sel) && !grp.items.every(o=>o._sel)"
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
                  <th>전체</th>
                  <th>존재</th>
                  <th>미이관</th>
                  <th>오류</th>
                  <th v-if="objResults.some(r=>r.srcTestStatus||r.testStatus)">테스트 성공</th>
                  <th v-if="objResults.some(r=>r.srcTestStatus||r.testStatus)">테스트 검토</th>
                  <th v-if="objResults.some(r=>r.srcTestStatus||r.testStatus)">테스트 실패</th>
                </tr>
              </thead>
              <tbody>
                <!-- v83: 소스/타겟 "존재" 를 동일한 기준으로 정리
                     - 소스 전체 = DataBridge 가 소스 DB 에서 조회한 오브젝트 (기준)
                     - 소스 존재 = 전체 수 (소스는 우리가 목록 가져온 것이 곧 존재)
                     - 타겟 존재 = status === 'ok' (확실히 있음) + status === 'error' (있는데 문제)
                     - 타겟 미이관 = status === 'missing' -->
                <tr>
                  <td class="vp-obj-stat-row-lbl">소스</td>
                  <td><span class="vp-ostat ok">{{ objResults.length }}</span></td>
                  <td><span class="vp-ostat ok">{{ objResults.length }}</span></td>
                  <td><span class="vp-ostat muted">—</span></td>
                  <td><span class="vp-ostat muted">—</span></td>
                  <td v-if="objResults.some(r=>r.srcTestStatus||r.testStatus)">
                    <span class="vp-ostat pass">{{ objResults.filter(r=>r.srcTestStatus==='pass').length }}</span>
                  </td>
                  <td v-if="objResults.some(r=>r.srcTestStatus||r.testStatus)">
                    <span class="vp-ostat" :class="objResults.filter(r=>r.srcTestStatus==='review').length ? 'warn' : 'muted'">
                      {{ objResults.filter(r=>r.srcTestStatus==='review').length || '—' }}
                    </span>
                  </td>
                  <td v-if="objResults.some(r=>r.srcTestStatus||r.testStatus)">
                    <span class="vp-ostat" :class="objResults.filter(r=>r.srcTestStatus==='fail').length ? 'fail' : 'muted'">
                      {{ objResults.filter(r=>r.srcTestStatus==='fail').length || '—' }}
                    </span>
                  </td>
                </tr>
                <tr>
                  <td class="vp-obj-stat-row-lbl">타겟</td>
                  <td><span class="vp-ostat ok">{{ objResults.length }}</span></td>
                  <td>
                    <!-- 타겟 존재 = 이관 성공(ok) + 이관됐지만 오류(error) = 타겟에 실제로 존재하는 것 -->
                    <span class="vp-ostat ok">
                      {{ objResults.filter(r=>r.status==='ok' || r.status==='error').length }}
                    </span>
                  </td>
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
                    <span class="vp-ostat" :class="objResults.filter(r=>r.testStatus==='review').length ? 'warn' : 'muted'">
                      {{ objResults.filter(r=>r.testStatus==='review').length || '—' }}
                    </span>
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

              <!-- v74: 기본 정렬 (최근 검증 시간 우선) — 본부장 요청. 전체 열기 왼쪽에 위치 -->
              <button class="chip" @click="setObjSortRecent"
                      :class="{'chip-active': objSortMode==='recent'}"
                      :title="objSortMode==='recent' ? '현재 활성 — 최근 검증된 항목이 맨 위' : '최근 검증 시간 우선 정렬로 전환 (진행 중인 것은 맨 위 고정)'">
                <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px">
                  <circle cx="6" cy="6" r="4.5"/>
                  <polyline points="6,3.5 6,6 8,7"/>
                </svg>
                기본 정렬
              </button>
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
                      @click="runSelectedObjTest" :disabled="objTesting || remigrateLoading"
                      :title="remigrateLoading ? '재이관 완료 후 사용 가능' : ''">
                <span v-if="objTesting" class="vp-spin" style="width:11px;height:11px;border-width:1.5px"></span>
                <svg v-else viewBox="0 0 12 12" fill="currentColor" style="width:10px;height:10px"><polygon points="2,1 10,6 2,11"/></svg>
                {{ objTesting ? '테스트 중...' : `▶ 선택 실행 (${selObjCount}개)` }}
              </button>
              <!-- 전체 실행 -->
              <button v-if="objResults.filter(r=>r.status==='ok').length" class="chip"
                      :class="selObjCount>0 ? '' : 'chip-run'"
                      @click="runAllObjTest" :disabled="objTesting || remigrateLoading"
                      :title="remigrateLoading ? '재이관 완료 후 사용 가능' : ''">
                <span v-if="objTesting" class="vp-spin" style="width:11px;height:11px;border-width:1.5px"></span>
                <svg v-else viewBox="0 0 12 12" fill="currentColor" style="width:10px;height:10px"><polygon points="2,1 10,6 2,11"/></svg>
                {{ objTesting ? '테스트 중...' : '▶ 전체 실행' }}
              </button>
              <button v-if="objResults.filter(r=>r.status==='missing').length" class="chip chip-report" @click="deployMissing"
                      :disabled="objTesting || remigrateLoading"
                      :title="objTesting ? '검증 완료 후 사용 가능' : (remigrateLoading ? '이전 재이관 완료 후 사용 가능' : `미이관 오브젝트를 Claude AI로 MySQL 문법에 맞게 변환하고 배포합니다 (약 ${objResults.filter(r=>r.status==='missing').length * 15}초 소요)`)">
                <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px"><line x1="6" y1="10" x2="6" y2="2"/><polyline points="2,6 6,2 10,6"/></svg>
                🤖 미이관 {{ objResults.filter(r=>r.status==='missing').length }}개 AI 배포
              </button>
              <!-- 재이관 버튼 — 실패 항목 있을 때 -->
              <button v-if="objResults.some(r=>r.testStatus==='fail'||r.srcTestStatus==='fail')"
                      class="chip chip-clear" @click="openRemigrateModal()"
                      :disabled="objTesting || remigrateLoading"
                      :title="objTesting ? '검증 완료 후 사용 가능' : (remigrateLoading ? '이전 재이관 완료 후 사용 가능' : '')">
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
                <col style="width:110px">
                <col style="width:100px">
                <col style="width:100px">
                <col style="width:110px">
                <!-- v80: '테스트' 와 'AI' 를 별도 컬럼으로 분리 — 본부장 요청 "라인 맞춤" -->
                <col style="width:70px">
                <col style="width:50px">
              </colgroup>
              <thead><tr>
                <th><input type="checkbox" @change="toggleAllObj" :checked="allObjSel" class="vp-chk"/></th>
                <th class="vp-sort" @click="setObjSort('type')">유형 <span class="vp-sico">{{ objSortIco('type') }}</span></th>
                <th class="vp-sort" @click="setObjSort('name')">오브젝트명 <span class="vp-sico">{{ objSortIco('name') }}</span></th>
                <!-- v77: 이관 컬럼 -->
                <th class="vp-sort" style="text-align:center" @click="setObjSort('status')">
                  이관 <span class="vp-sico">{{ objSortIco('status') }}</span>
                </th>
                <th class="vp-sort" style="text-align:center" @click="setObjSort('srcTestStatus')">
                  소스 테스트 <span class="vp-sico">{{ objSortIco('srcTestStatus') }}</span>
                </th>
                <th class="vp-sort" style="text-align:center" @click="setObjSort('testStatus')">
                  타겟 테스트 <span class="vp-sico">{{ objSortIco('testStatus') }}</span>
                </th>
                <!-- v77: 재이관 컬럼 -->
                <th style="text-align:center">재이관</th>
                <!-- v80: 액션 → 테스트 / AI 분리 -->
                <th style="text-align:center">테스트</th>
                <th style="text-align:center">AI</th>
              </tr></thead>
              <tbody>
                <template v-for="r in sortedObjResults" :key="r.name+r.type">
                  <tr class="vp-row"
                      :class="{'vp-row-fail': r.status!=='ok'||r.srcTestStatus==='fail'||r.testStatus==='fail', 'vp-row-review': r.status==='ok'&&(r.srcTestStatus==='review'||r.testStatus==='review')&&r.srcTestStatus!=='fail'&&r.testStatus!=='fail', 'vp-row-ok': r.status==='ok'&&r.srcTestStatus==='pass'&&r.testStatus==='pass', 'vp-row-running': r.testing||r.srcTesting}"
                      @click="toggleObjDetail(r)" style="cursor:pointer">
                    <!-- v65: scrollIntoView 제거. 이제 진행 행이 정렬로 항상 최상단이므로
                         자동 스크롤 불필요. smooth 애니메이션이 본부장님 보고한 "왔다갔다"
                         어지러움의 원인 중 하나였음. -->
                    <td @click.stop><input type="checkbox" v-model="r._sel" class="vp-chk"/></td>
                    <td><span class="vp-otype-tag" :class="r.type.toLowerCase()">{{ r.type.substring(0,4) }}</span></td>
                    <!-- v77: 오브젝트명만 — 기존 서브텍스트(소스 ✓ · 타겟 없음 · 진단, 재이관 배지)는 별도 컬럼으로 이동 -->
                    <td style="overflow:hidden">
                      <div class="vp-obj-nm-cell">
                        <span class="vp-obj-nm-text" :title="r.name">{{ r.name }}</span>
                        <!-- 이름 변형 힌트는 이름 옆에 둠 (MSSQL 스키마 → MySQL 테이블 변환 시 필요) -->
                        <span v-if="r.name_variant" class="vp-name-variant"
                              :title="`소스: ${r.name} / 타겟에 실제 존재: ${r.name_variant}`">
                          ({{ r.name_variant }})
                        </span>
                      </div>
                    </td>
                    <!-- v77: 이관 컬럼 — 소스/타겟 DB 존재 상태 요약 -->
                    <!-- v81: 초기 로딩 시 status 가 아직 세팅 안 된 상태에서 "타겟 오류" 로 표시되던 버그 수정.
                             본부장 보고: "검색 시작하면 '타겟 오류' 가 모든 행에 쭉~~뜬다".
                             원인: v-else 가 status === undefined/null 도 '타겟 오류' 로 잡음.
                             해결: 명시적 'error' 일 때만 '타겟 오류', 그 외 미판정은 빈 셀(—). -->
                    <td style="text-align:center">
                      <span v-if="r.status==='ok'" class="vp-badge ok" title="소스·타겟 모두 존재">✓ 이관됨</span>
                      <span v-else-if="r.status==='missing'" class="vp-badge fail" title="타겟에 오브젝트 없음">
                        타겟 없음
                      </span>
                      <span v-else-if="r.status==='error'" class="vp-badge fail" title="타겟 오브젝트 오류">타겟 오류</span>
                      <span v-else class="vp-badge gray" style="opacity:.3" title="검색 중 또는 미판정">—</span>
                      <!-- v50: 진단 버튼 — 타겟 없음 상태에서 실제 DB 내용 확인 -->
                      <button v-if="r.status==='missing' && r.diagnostics" class="vp-diag-btn"
                              @click.stop="showObjDiagnostics(r)"
                              style="margin-left:4px"
                              :title="'진단 정보 보기 — DB 내 ' + (r.diagnostics.total_in_db || 0) + '개 오브젝트 존재'">
                        🔍
                      </button>
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
                    <!-- v77: 재이관 컬럼 — 기존엔 오브젝트명 옆에 배지, 의미 충돌 있어 분리 -->
                    <td style="text-align:center" @click.stop>
                      <span v-if="r._remigResult?.status === 'success'"
                            class="vp-remig-badge success"
                            :title="`재이관 성공 (${_fmtRemigAt(r._remigResult.at)})`">
                        ✓ 성공
                      </span>
                      <span v-else-if="r._remigResult?.status === 'failed'"
                            class="vp-remig-badge failed"
                            :title="`재이관 실패 — ${r._remigResult.error || '오류'} (${_fmtRemigAt(r._remigResult.at)})`">
                        ✗ 실패
                      </span>
                      <span v-else class="vp-badge gray" style="opacity:.4">—</span>
                    </td>
                    <!-- v80: 테스트 컬럼 -->
                    <td @click.stop style="text-align:center">
                      <button class="vp-act-btn info" @click="runObjTest(r)"
                              :disabled="r.testing||r.srcTesting" title="소스+타겟 실행 테스트">
                        {{ (r.testing||r.srcTesting) ? '…' : '▶ 테스트' }}
                      </button>
                    </td>
                    <!-- v80: AI 컬럼 (분리) — 필요 없는 행은 빈 셀로 유지해 줄 맞춤 -->
                    <td @click.stop style="text-align:center">
                      <button v-if="r.status==='missing' || r.testStatus==='fail' || r.srcTestStatus==='fail'"
                              class="vp-act-btn warn"
                              @click="runSingleObjAiRemig(r)"
                              :disabled="r._aiRetrying || r.testing || r.srcTesting || objTesting || remigrateLoading"
                              :title="r._aiRetrying ? 'AI 재변환 진행 중' : (objTesting ? '검증 완료 후 사용 가능' : (remigrateLoading ? '이전 재이관 완료 후 사용 가능' : '이 오브젝트만 AI로 재변환 + 배포 + 재검증'))">
                        {{ r._aiRetrying ? '🤖…' : '🤖 AI' }}
                      </button>
                      <span v-else class="vp-badge gray" style="opacity:.25;font-size:10px">—</span>
                    </td>
                  </tr>
                  <!-- 테스트 결과 상세 — 클릭 시 펼치기 -->
                  <tr v-if="objDetailRows[r.name+r.type]" class="vp-detail-row">
                    <td colspan="9" style="padding:8px 10px">
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

                        <!-- v82: 좌/우 블록 완전 분리 레이아웃 + 입력칸 확대 -->
                        <div v-if="r._params?.length" class="vp-param-split">
                          <!-- ─── 왼쪽: 소스 영역 ─── -->
                          <div class="vp-param-side vp-param-side-src">
                            <div class="vp-param-side-hdr">
                              <span class="vp-param-side-ttl">◀ 소스 (MSSQL)</span>
                              <span v-if="r._autoSuggested" class="vp-param-auto-badge" title="자동 추천값 세팅됨">📊 자동</span>
                            </div>
                            <div class="vp-param-rows">
                              <div v-for="(p, i) in r._params" :key="'s'+i" class="vp-param-row-v82">
                                <div class="vp-param-lbl">
                                  <span class="vp-param-nm">{{ p.name }}</span>
                                  <span class="vp-param-type">{{ p.data_type }}</span>
                                  <span v-if="p.is_output" class="vp-param-out">OUT</span>
                                </div>
                                <div class="vp-param-val">
                                  <input v-if="!p.is_output"
                                         v-model="p.src_value"
                                         class="vp-param-inp-wide"
                                         :placeholder="p.data_type"
                                         @click.stop
                                         :title="'MSSQL 소스 DB 에서 쓸 값'"/>
                                  <span v-else class="vp-param-out-note">OUT 파라미터</span>
                                  <span v-if="p.suggestion_source" class="vp-param-src"
                                        :title="p.suggestion_source">
                                    {{ p.suggestion_source.includes('.')? '📊' : p.suggestion_source==='패턴 추천'?'🔤':'💡' }}
                                  </span>
                                </div>
                              </div>
                            </div>
                            <button class="chip chip-run vp-param-side-btn"
                                    style="background:#2563eb;border-color:#2563eb"
                                    @click.stop="runObjTestWithParams(r, 'src')"
                                    :disabled="r.testing||r.srcTesting">
                              <span v-if="r.srcTesting" class="vp-spin" style="width:10px;height:10px;border-width:1.5px"></span>
                              <svg v-else viewBox="0 0 12 12" fill="currentColor" style="width:9px;height:9px"><polygon points="2,1 10,6 2,11"/></svg>
                              {{ r.srcTesting ? '소스 실행 중...' : '▶ 소스 테스트' }}
                            </button>
                          </div>

                          <!-- ─── 가운데: 복사/양쪽 실행 ─── -->
                          <div class="vp-param-mid">
                            <button v-for="(p, i) in r._params" :key="'m'+i"
                                    class="vp-param-copy-btn-v82"
                                    v-show="!p.is_output"
                                    @click.stop="p.tgt_value = p.src_value"
                                    title="소스 값을 타겟에 복사">⇒</button>
                            <div class="vp-param-mid-spacer"></div>
                            <button class="chip chip-run vp-param-mid-btn"
                                    @click.stop="runObjTestWithParams(r, 'both')"
                                    :disabled="r.testing||r.srcTesting">
                              <span v-if="r.testing||r.srcTesting" class="vp-spin" style="width:10px;height:10px;border-width:1.5px"></span>
                              <svg v-else viewBox="0 0 12 12" fill="currentColor" style="width:9px;height:9px"><polygon points="2,1 10,6 2,11"/></svg>
                              {{ (r.testing||r.srcTesting) ? '실행 중...' : '▶ 양쪽 동시' }}
                            </button>
                          </div>

                          <!-- ─── 오른쪽: 타겟 영역 ─── -->
                          <div class="vp-param-side vp-param-side-tgt">
                            <div class="vp-param-side-hdr">
                              <span class="vp-param-side-ttl">타겟 (MySQL) ▶</span>
                              <span v-if="r._autoSuggested" class="vp-param-auto-badge" title="자동 추천값 세팅됨">📊 자동</span>
                            </div>
                            <div class="vp-param-rows">
                              <div v-for="(p, i) in r._params" :key="'t'+i" class="vp-param-row-v82">
                                <div class="vp-param-lbl">
                                  <span class="vp-param-nm">{{ p.name }}</span>
                                  <span class="vp-param-type">{{ p.data_type }}</span>
                                  <span v-if="p.is_output" class="vp-param-out">OUT</span>
                                </div>
                                <div class="vp-param-val">
                                  <input v-if="!p.is_output"
                                         v-model="p.tgt_value"
                                         class="vp-param-inp-wide"
                                         :placeholder="p.data_type"
                                         @click.stop
                                         :title="'MySQL 타겟 DB 에서 쓸 값'"/>
                                  <span v-else class="vp-param-out-note">OUT 파라미터</span>
                                </div>
                              </div>
                            </div>
                            <button class="chip chip-run vp-param-side-btn"
                                    style="background:#16a34a;border-color:#16a34a"
                                    @click.stop="runObjTestWithParams(r, 'tgt')"
                                    :disabled="r.testing||r.srcTesting">
                              <span v-if="r.testing" class="vp-spin" style="width:10px;height:10px;border-width:1.5px"></span>
                              <svg v-else viewBox="0 0 12 12" fill="currentColor" style="width:9px;height:9px"><polygon points="2,1 10,6 2,11"/></svg>
                              {{ r.testing ? '타겟 실행 중...' : '▶ 타겟 테스트' }}
                            </button>
                          </div>
                        </div>

                        <!-- v82: AI 재이관 버튼 — 하단 단독 배치 -->
                        <div v-if="r._params?.length" class="vp-param-ai-row">
                          <button class="chip chip-clear" @click.stop="openRemigrateModal([r])"
                                  title="이 오브젝트를 AI로 재이관">
                            <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px">
                              <path d="M2 6a4 4 0 1 0 4-4"/><polyline points="4,1 1,1 1,4"/>
                              <line x1="7" y1="8" x2="7" y2="5"/><line x1="5.5" y1="8" x2="8.5" y2="8"/>
                            </svg>
                            AI 재이관
                          </button>
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
    <!-- v54: backdrop 클릭 시 닫힘 제거 — 본부장 보고: AI 변환 결과 복사하려다 실수로 닫힘.
         이제 우상단 ✕ 버튼 또는 ESC 키(로딩 중 아닐 때)로만 닫음. -->
    <div v-if="showRemigrate" class="vp-modal-overlay">
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
          <div style="display:flex;gap:6px;align-items:center">
            <!-- v76: 최소화 버튼 — 실행 중 혹은 완료 후에도 항상 사용 가능 -->
            <button class="vp-modal-close" @click="remigrateMinimize"
                    style="font-size:18px;font-weight:700"
                    title="최소화 — 진행은 계속되며 하단 바에서 다시 열 수 있습니다">−</button>
            <!-- 닫기 ✕ — 실행 중엔 비활성, 완료 후엔 정상 동작 -->
            <button class="vp-modal-close" @click="showRemigrate=false"
                    :disabled="remigrateLoading"
                    :title="remigrateLoading ? '진행 중엔 닫을 수 없습니다 (최소화는 가능)' : '닫기 (ESC)'">✕</button>
          </div>
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
        <!-- v72: 루프 종료 후에도 결과 확인 위해 유지 (이전엔 remigrateLoading 만 조건) -->
        <div v-if="remigrateLoading || remigrateAllDone || remigrateProgress.length" class="vp-remig-progress">
          <div class="vp-remig-step">{{ remigrateStep }}</div>
          <div class="vp-remig-prog-list">
            <div v-for="row in remigrateProgress" :key="row.name"
                 class="vp-remig-prog-item" :class="row.status">
              <span class="vp-remig-prog-icon">
                <span v-if="row.status==='running'" class="vp-spin" style="width:9px;height:9px;border-width:1.5px;display:inline-block"></span>
                <span v-else-if="row.status==='done'" style="color:#16a34a">✓</span>
                <span v-else-if="row.status==='fail'" style="color:#dc2626">✗</span>
                <span v-else-if="row.status==='skip'" style="color:#9ca3af" title="사용자 중단으로 건너뜀">⊘</span>
                <span v-else style="color:var(--text-tertiary)">○</span>
              </span>
              <span class="vp-otype-tag" :class="row.type.toLowerCase()" style="font-size:9px;padding:0 4px">{{ row.type.substring(0,4) }}</span>
              <span class="vp-remig-prog-nm">{{ row.name }}</span>
              <span class="vp-remig-prog-msg" :style="{color: row.status==='skip' ? '#9ca3af' : ''}">{{ row.msg }}</span>
            </div>
          </div>
        </div>

        <!-- 푸터 -->
        <div class="vp-modal-footer">
          <!-- v66: missing(이관 자체 안 된 것) 포함 시 이 체크박스는 의미 없음 — 숨김 -->
          <label class="vp-remig-chk"
                 v-if="!remigrateLoading && !remigrateAllDone && !remigrateTargets.some(r => r.status === 'missing')">
            <input type="checkbox" v-model="remigrateOnlyFail"/>
            성공한 오브젝트 제외, 실패만 처리
          </label>
          <!-- v66: missing 포함 시 안내 문구 -->
          <div v-else-if="!remigrateLoading && !remigrateAllDone && remigrateTargets.some(r => r.status === 'missing')"
               style="font-size:11.5px;color:var(--text-secondary)">
            미이관 오브젝트 포함 — 전체 대상 AI 변환 + 배포
          </div>
          <div v-if="remigrateLoading" style="font-size:11.5px;color:var(--text-secondary)">
            {{ remigratePaused ? '⏸ 일시정지됨 — 재개 또는 중단 선택' : (remigrateStopRequested ? '중단 처리 중...' : '실행 중 — 중간에 멈추거나 중단할 수 있습니다') }}
          </div>
          <!-- v56: 루프 완료 후 안내 — 결과 확인 후 직접 닫도록 유도 -->
          <div v-else-if="remigrateAllDone"
               style="font-size:11.5px;color:#15803d;font-weight:600">
            ✓ 모든 항목 처리됨 — 결과를 확인 후 닫아주세요
          </div>
          <div style="display:flex;gap:6px;margin-left:auto">
            <!-- v72: 실행 중 일 때는 일시정지/재개 + 중단 버튼 노출 -->
            <template v-if="remigrateLoading">
              <button class="chip" @click="remigratePauseToggle" :disabled="remigrateStopRequested"
                      :title="remigratePaused ? '재개' : '일시정지 (현재 항목 종료 후 멈춤)'">
                <svg v-if="!remigratePaused" viewBox="0 0 12 12" fill="currentColor" style="width:9px;height:9px">
                  <rect x="2.5" y="2" width="2.5" height="8" rx=".3"/>
                  <rect x="7" y="2" width="2.5" height="8" rx=".3"/>
                </svg>
                <svg v-else viewBox="0 0 12 12" fill="currentColor" style="width:10px;height:10px"><polygon points="2,1 10,6 2,11"/></svg>
                {{ remigratePaused ? '재개' : '일시정지' }}
              </button>
              <button class="chip" @click="remigrateAbort" :disabled="remigrateStopRequested"
                      style="background:#fef2f2;color:#b91c1c;border-color:#fca5a5"
                      title="중단 (현재 항목은 마치고 나머지 건너뜀)">
                <svg viewBox="0 0 12 12" fill="currentColor" style="width:9px;height:9px"><rect x="2" y="2" width="8" height="8" rx="1"/></svg>
                중단
              </button>
            </template>
            <!-- 실행 중 아닐 때: 기존 취소/닫기 + 시작 버튼 -->
            <template v-else>
              <button class="chip" @click="showRemigrate=false"
                      :class="{'chip-done-close': remigrateAllDone}">
                {{ remigrateAllDone ? '완료 — 닫기' : '취소' }}
              </button>
              <button v-if="!remigrateAllDone" class="chip chip-run" @click="startRemigrate">
                <svg viewBox="0 0 12 12" fill="currentColor" style="width:9px;height:9px"><polygon points="2,1 10,6 2,11"/></svg>
                {{ remigrateAction==='ai' ? 'AI 재변환 + 배포' : '오브젝트 매핑으로 이동' }}
              </button>
            </template>
          </div>
        </div>
      </div>
    </div>

    <!-- v76: 재이관 최소화 미니바 — 하단 고정, 클릭 시 팝업 복구 -->
    <div v-if="remigrateMinimized" class="vp-remig-minibar"
         @click.self="remigrateRestore">
      <div class="vp-remig-minibar-icon">
        <span v-if="remigrateLoading" class="vp-spin" style="width:12px;height:12px;border-width:2px"></span>
        <span v-else-if="remigrateAllDone" style="color:#16a34a;font-size:14px">✓</span>
        <span v-else style="color:#6b7280;font-size:14px">🔄</span>
      </div>
      <div class="vp-remig-minibar-text" @click="remigrateRestore">
        <div class="vp-remig-minibar-title">
          <template v-if="remigrateLoading">
            재이관 진행 중 —
            {{ remigrateProgress.filter(r => r.status === 'done' || r.status === 'fail').length }}
            /
            {{ remigrateProgress.length }}
          </template>
          <template v-else-if="remigrateAllDone">
            재이관 완료 — 클릭해서 결과 확인
          </template>
          <template v-else>
            재이관 (대기)
          </template>
        </div>
        <div class="vp-remig-minibar-sub">{{ remigrateStep || '클릭해서 상세 보기' }}</div>
      </div>
      <!-- 진행률 바 -->
      <div v-if="remigrateLoading && remigrateProgress.length" class="vp-remig-minibar-progress">
        <div class="vp-remig-minibar-progress-fill"
             :style="{width: (remigrateProgress.filter(r => r.status === 'done' || r.status === 'fail').length / remigrateProgress.length * 100) + '%'}"></div>
      </div>
      <!-- 완료 후에만 닫기 버튼 노출 -->
      <button v-if="!remigrateLoading" @click.stop="remigrateMinibarClose"
              class="vp-remig-minibar-close" title="미니바 닫기 (결과는 메인 리스트에서 확인 가능)">✕</button>
    </div>
  </teleport>

  <!-- ── 재이관 모달 ── -->
  <teleport to="body">
    <div v-if="remigModal" class="vp-remig-overlay" @click.self="!remigRunning && closeRemigModal()">
      <div class="vp-remig-modal">
        <!-- 헤더 -->
        <div class="vp-remig-modal-header">
          <span class="vp-remig-modal-icon">🔄</span>
          <div class="vp-remig-modal-title">
            <div class="vp-remig-modal-name">{{ remigRow?._bulk ? `불일치 ${remigRow._rows?.length}개 일괄 재이관` : remigRow?.table }}</div>
            <div class="vp-remig-modal-sub">
              소스 {{ connector.source?.host }}/{{ connector.source?.database }}
              → 타겟 {{ connector.target?.host }}/{{ connector.target?.database }}
            </div>
          </div>
          <button class="vp-remig-modal-close" @click="!remigRunning && closeRemigModal()" :disabled="remigRunning">✕</button>
        </div>

        <!-- 불일치 요약 -->
        <div v-if="remigRow && !remigRow._bulk" class="vp-remig-modal-diff">
          <span class="vp-remig-diff-label">소스</span>
          <span class="vp-remig-diff-val">{{ (remigRow.src_count||0).toLocaleString() }}행</span>
          <span class="vp-remig-diff-arrow">→</span>
          <span class="vp-remig-diff-label">타겟</span>
          <span class="vp-remig-diff-val" :class="{'vp-remig-diff-bad': remigRow.src_count !== remigRow.tgt_count}">
            {{ (remigRow.tgt_count||0).toLocaleString() }}행
          </span>
          <span class="vp-remig-diff-gap" v-if="remigRow.src_count !== remigRow.tgt_count">
            ({{ (remigRow.tgt_count||0) - (remigRow.src_count||0) > 0 ? '+' : '' }}{{ ((remigRow.tgt_count||0)-(remigRow.src_count||0)).toLocaleString() }})
          </span>
        </div>

        <!-- 방식 선택 (실행 전) -->
        <template v-if="remigJobStatus === 'idle'">
          <div class="vp-remig-modal-section-label">재이관 방식 선택</div>
          <div class="vp-remig-modal-opts">
            <label v-for="opt in remigOpts" :key="opt.v"
                   class="vp-remig-modal-opt" :class="{active: remigMode===opt.v}"
                   @click="remigMode=opt.v">
              <input type="radio" :value="opt.v" v-model="remigMode"/>
              <span class="vp-remig-opt-icon">{{ opt.icon }}</span>
              <div class="vp-remig-opt-body">
                <span class="vp-remig-opt-title">{{ opt.title }}</span>
                <span class="vp-remig-opt-desc">{{ opt.desc }}</span>
              </div>
              <span v-if="remigMode===opt.v" class="vp-remig-opt-check">✓</span>
            </label>
          </div>
        </template>

        <!-- 진행 상황 (실행 후) -->
        <template v-if="remigJobStatus !== 'idle'">
          <div class="vp-remig-modal-section-label">진행 상황</div>

          <!-- v37: 메인 진행률 상태바 ─────────────────────────── -->
          <div class="vp-remig-progress-card">
            <!-- 상단: 큰 진행률 숫자 + 테이블명 -->
            <div class="vp-remig-progress-top">
              <div class="vp-remig-progress-pct-wrap">
                <div class="vp-remig-progress-pct">{{ remigProg.pct }}<span class="vp-remig-progress-pct-unit">%</span></div>
                <div class="vp-remig-progress-status" :class="remigJobStatus">
                  <span v-if="remigJobStatus==='running'" class="vp-spin" style="width:10px;height:10px;border-width:1.5px"></span>
                  <span v-else-if="remigJobStatus==='completed'">✓</span>
                  <span v-else-if="remigJobStatus==='error' || remigJobStatus==='aborted'">✕</span>
                  {{ {running:'이관 중', completed:'완료', error:'오류', aborted:'중단'}[remigJobStatus] || remigJobStatus }}
                </div>
              </div>
              <div class="vp-remig-progress-meta">
                <div v-if="remigProg.currentTable" class="vp-remig-progress-table">
                  <span class="vp-remig-progress-meta-lbl">현재 테이블</span>
                  <span class="vp-remig-progress-meta-val">{{ remigProg.currentTable }}</span>
                </div>
                <div v-if="remigProg.tablesTotal > 1" class="vp-remig-progress-tables">
                  <span class="vp-remig-progress-meta-lbl">테이블</span>
                  <span class="vp-remig-progress-meta-val">{{ remigProg.tablesDone }} / {{ remigProg.tablesTotal }}</span>
                </div>
              </div>
            </div>

            <!-- 진행률 바 -->
            <div class="vp-remig-progress-bar-wrap">
              <div class="vp-remig-progress-bar"
                   :class="remigJobStatus"
                   :style="{width: remigProg.pct + '%'}"></div>
            </div>

            <!-- 하단: 4개 통계 카드 -->
            <div class="vp-remig-progress-stats">
              <div class="vp-remig-stat">
                <div class="vp-remig-stat-lbl">경과 시간</div>
                <div class="vp-remig-stat-val">{{ _fmtDur(remigProg.elapsedSec) }}</div>
              </div>
              <div class="vp-remig-stat">
                <div class="vp-remig-stat-lbl">남은 시간 (예상)</div>
                <div class="vp-remig-stat-val" :class="{'vp-remig-stat-measuring': remigProg.etaSec == null}">
                  <template v-if="remigJobStatus==='completed'">완료</template>
                  <template v-else-if="remigProg.etaSec == null">측정 중...</template>
                  <template v-else-if="remigProg.etaSec <= 1">거의 완료</template>
                  <template v-else>{{ _fmtDur(remigProg.etaSec) }}</template>
                </div>
              </div>
              <div class="vp-remig-stat">
                <div class="vp-remig-stat-lbl">완료 예상</div>
                <div class="vp-remig-stat-val" :class="{'vp-remig-stat-measuring': remigProg.etaSec == null}">
                  <template v-if="remigJobStatus==='completed'">—</template>
                  <template v-else-if="remigProg.etaSec == null">—</template>
                  <template v-else>{{ _fmtFinishTime(remigProg.etaSec) }}</template>
                </div>
              </div>
              <div class="vp-remig-stat">
                <div class="vp-remig-stat-lbl">처리 속도</div>
                <div class="vp-remig-stat-val">{{ _fmtRowsPerSec(remigProg.rowsPerSec) }}</div>
              </div>
            </div>

            <!-- 행 카운트 (rowsTotal 이 알려진 경우) -->
            <div v-if="remigProg.rowsDone > 0 || remigProg.rowsTotal > 0" class="vp-remig-progress-rows">
              <span class="vp-remig-progress-rows-done">{{ remigProg.rowsDone.toLocaleString() }}</span>
              <span class="vp-remig-progress-rows-sep"> / </span>
              <span class="vp-remig-progress-rows-total">{{ remigProg.rowsTotal > 0 ? remigProg.rowsTotal.toLocaleString() : '—' }}</span>
              <span class="vp-remig-progress-rows-unit"> rows</span>
            </div>
          </div>

          <!-- 상세 로그 (기존 유지) -->
          <div class="vp-remig-log-box" ref="remigLogRef">
            <div v-for="(log,i) in remigLogs" :key="i" class="vp-remig-log-line"
                 :class="{'log-ok':log.startsWith('✅')||log.startsWith('🎉'), 'log-err':log.startsWith('❌'), 'log-info':log.startsWith('📊')||log.startsWith('📡')}">
              {{ log }}
            </div>
          </div>
          <!-- 상태 배지 -->
          <div class="vp-remig-status-row">
            <span class="vp-remig-status-badge" :class="remigJobStatus">
              <span v-if="remigJobStatus==='running'" class="vp-spin"></span>
              {{ {idle:'대기',running:'이관 중',completed:'완료',error:'오류',aborted:'중단'}[remigJobStatus] || remigJobStatus }}
            </span>
            <span v-if="remigJobStatus==='completed'" class="vp-remig-done-hint">검증 결과를 자동으로 갱신합니다...</span>
          </div>
        </template>

        <!-- 푸터 -->
        <!-- v45: 상태별 버튼 세트. 왼쪽=보조(닫기/취소), 오른쪽=주 액션(실행/일시정지/중단/재실행). -->
        <div class="vp-remig-modal-footer">
          <!-- 왼쪽: 닫기/취소 (보조) -->
          <button v-if="remigJobStatus === 'idle'"
                  class="vp-remig-modal-cancel" @click="closeRemigModal">
            취소
          </button>
          <button v-else-if="['running','paused','aborting'].includes(remigJobStatus)"
                  class="vp-remig-modal-cancel" @click="closeRemigModal"
                  title="모달만 닫습니다 — 이관 작업은 백그라운드에서 계속됩니다">
            닫기 (백그라운드 유지)
          </button>
          <button v-else
                  class="vp-remig-modal-cancel" @click="closeRemigModal">
            닫기
          </button>

          <!-- 오른쪽: 주 액션 (선택→수행 흐름) -->
          <div class="vp-remig-btn-grp">
            <!-- 대기: 재이관 시작 -->
            <button v-if="remigJobStatus === 'idle'"
                    class="vp-remig-modal-run" @click="doRemig" :disabled="remigRunning">
              <svg viewBox="0 0 12 12" fill="currentColor" style="width:10px;height:10px"><polygon points="2,1 10,6 2,11"/></svg>
              재이관 시작
            </button>

            <!-- 실행 중: 일시정지 + 중단 -->
            <template v-else-if="remigJobStatus === 'running'">
              <button class="vp-remig-btn-pause" @click="remigPause">
                <svg viewBox="0 0 12 12" fill="currentColor" style="width:10px;height:10px">
                  <rect x="2.5" y="2" width="2.5" height="8" rx=".3"/>
                  <rect x="7" y="2" width="2.5" height="8" rx=".3"/>
                </svg>
                일시정지
              </button>
              <button class="vp-remig-btn-stop" @click="remigStop">
                <svg viewBox="0 0 12 12" fill="currentColor" style="width:9px;height:9px"><rect x="2" y="2" width="8" height="8" rx="1"/></svg>
                중단
              </button>
            </template>

            <!-- 일시정지됨: 계속 + 중단 -->
            <template v-else-if="remigJobStatus === 'paused'">
              <button class="vp-remig-modal-run" @click="remigResume">
                <svg viewBox="0 0 12 12" fill="currentColor" style="width:10px;height:10px"><polygon points="2,1 10,6 2,11"/></svg>
                계속
              </button>
              <button class="vp-remig-btn-stop" @click="remigStop">
                <svg viewBox="0 0 12 12" fill="currentColor" style="width:9px;height:9px"><rect x="2" y="2" width="8" height="8" rx="1"/></svg>
                중단
              </button>
            </template>

            <!-- 중단 중: 스피너 -->
            <button v-else-if="remigJobStatus === 'aborting'"
                    class="vp-remig-btn-stop" disabled>
              <span class="vp-spin" style="width:10px;height:10px;border-width:1.5px"></span>
              중단 중...
            </button>

            <!-- 에러/중단됨: 재실행 -->
            <button v-else-if="['error','aborted'].includes(remigJobStatus)"
                    class="vp-remig-modal-run" @click="remigRestart">
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px">
                <path d="M1 6a5 5 0 1 0 5-5"/><polyline points="3.5,1 1,1 1,3.5"/>
              </svg>
              재실행
            </button>

            <!-- 완료: 닫기 강조 -->
            <button v-else-if="remigJobStatus === 'completed'"
                    class="vp-remig-modal-run done" @click="closeRemigModal">
              ✓ 완료 — 닫기
            </button>
          </div>
        </div>
      </div>
    </div>
  </teleport>

</template>

<script setup>
defineOptions({ name: 'Validate' })
import { ref, computed, watch, reactive, onMounted, onActivated, onDeactivated } from 'vue'
import { useConnectorStore } from '@/store/connectorStore.js'
import { useAppStore }       from '@/store/appStore.js'
import { usePageStore }      from '@/store/pageStore.js'
import { useJobStore }       from '@/store/jobStore.js'
// v90.49: schema 정책을 converterStore 에서 가져와서 검증에도 일관 적용
//   본부장님 결정 (2026-04-27): 테이블 이관과 검증&대사 일관성 확보
import { useConverterStore } from '@/store/converterStore.js'
import { useRunPauseStop }   from '@/composables/useRunPauseStop.js'
import axios from 'axios'
import { useRouter } from 'vue-router'
import PageHeader    from '@/components/layout/PageHeader.vue'
import ConnectPanel  from '@/components/common/ConnectPanel.vue'

const connector = useConnectorStore()
const app       = useAppStore()
const jobStore  = useJobStore()
// v90.49: schema 정책 (converterStore 와 공유 — 페이지 이동해도 일관)
const cStore        = useConverterStore()
const schemaStrategy = computed({
  get: () => cStore.schemaStrategy,
  set: v => cStore.schemaStrategy = v,
})
// v90.49: 정책 변경 시 자동 재매칭 watcher 는 loadTables 정의 이후에 등록 (호이스팅 안전)

// 현재 이관 진행 중인 Job 감지
const migratingNow = computed(() =>
  jobStore.jobs?.some(j => j.status === 'running' || j.status === 'paused') ?? false
)

// ── 인라인 빠른 연결 ────────────────────────────────────────────
const quickSrc = reactive({ dbType:'mssql', host:'', port:1433, username:'', password:'', database:'' })
const quickTgt = reactive({ dbType:'mysql',  host:'', port:3306, username:'', password:'', database:'' })
const quickTesting = ref(false)
// v90.69: 자동 재연결 시도 중 플래그 (ConnectPanel 깜빡임 방지)
const _isAutoConnecting = ref(false)

function onConnected() { loadTables(); connector.loadProfiles() }

// v91p10: DB 접속 해제 (다른 DB 테스트 위해 — 전 화면 공통 적용)
function onDisconnect() {
  if (connector.source) {
    connector.source.status = 'idle'
    connector.source.host = ''
    connector.source.password = ''
  }
  if (connector.target) {
    connector.target.status = 'idle'
    connector.target.host = ''
    connector.target.password = ''
  }
  // 검증 결과도 클리어
  results.value = []
  objResults.value = []
  app.notify('DB 연결 해제 완료 — 다시 연결하세요', 'info')
}

// ════════════════════════════════════════════════════════════════════
// v90.69 (2026-04-28): 페이지 진입 시 자동 재연결
//   본부장님 호소: "DB 접속이 이미 접속되 있으면 상단 처리"
//   원인: connectorStore.state 가 메모리 only — 페이지 이동/새로고침 시 status 리셋
//        화면 진입할 때마다 ConnectPanel 다시 떠서 또 접속하라고 함
//   처방: host/username/database 정보 있으면 자동 testConn 호출
//        성공 시 ConnectPanel 자동 숨김 + loadTables 자동 실행
// ════════════════════════════════════════════════════════════════════
async function _autoReconnectIfPossible() {
  // 이미 연결된 상태면 아무것도 안 함
  if (connector.bothConnected) return
  
  const src = connector.source
  const tgt = connector.target
  
  // host + username + database 가 모두 채워져 있어야 자동 시도 가능
  const _hasInfo = (c) => c.host && c.username && c.database
  if (!_hasInfo(src) || !_hasInfo(tgt)) return
  
  // 둘 다 idle 또는 error 상태일 때만 시도 (testing 중이면 skip)
  if (src.status === 'testing' || tgt.status === 'testing') return
  
  _isAutoConnecting.value = true
  try {
    // 양쪽 동시 testConn 시도
    await Promise.all([
      connector.testConn('source'),
      connector.testConn('target'),
    ])
    if (connector.bothConnected) {
      // 자동 재연결 성공 → 테이블 로드
      app.notify('이전 연결 정보로 자동 접속됨', 'info')
      loadTables()
    }
  } catch {
    // 자동 재연결 실패는 조용히 — 사용자가 ConnectPanel 보고 수동 입력
  } finally {
    _isAutoConnecting.value = false
  }
}

// v90.72: _disconnectAll 함수 제거 — vp-conn-status 와 함께 사용처 없어짐.
//         다른 DB 변경하려면 Connector 화면에서 직접 변경 → Validate 진입 시 자동 재연결.

async function applyAndTest(profile) {
  connector.applyProfile(profile)
  quickTesting.value = true
  try {
    await connector.testConn('source')
    await connector.testConn('target')
    if (connector.bothConnected) {
      app.notify('연결 성공!', 'success')
      loadTables()
    } else {
      app.notify('연결 실패 — 커넥터 관리에서 확인하세요', 'error')
    }
  } finally { quickTesting.value = false }
}

async function quickConnect() {
  quickTesting.value = true
  try {
    Object.assign(connector.source, quickSrc)
    Object.assign(connector.target, quickTgt)
    await connector.testConn('source')
    await connector.testConn('target')
    if (connector.bothConnected) {
      app.notify('연결 성공!', 'success')
      loadTables()
    } else {
      app.notify('연결 실패 — 입력 정보를 확인하세요', 'error')
    }
  } finally { quickTesting.value = false }
}

const pStore    = usePageStore()
const vType = ref('table')
const tabTouched = ref(false)  // 탭 클릭 전엔 active 표시 안 함

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
// v36: bare name 매칭 상태 / 충돌 감지 결과
const tableMatchInfo = ref({ has_conflict:false, conflicts:[], src_count:0, tgt_count:0, matched_count:0, validation_mode:'' })

// 소스/타겟 리스트 스크롤 연동
const srcListBodyRef = ref(null)
const tgtListBodyRef = ref(null)
let _scrollLock = false
function onListScroll(e, side) {
  if (_scrollLock) return
  _scrollLock = true
  const other = side === 'src' ? tgtListBodyRef.value : srcListBodyRef.value
  if (other) other.scrollTop = e.target.scrollTop
  requestAnimationFrame(() => { _scrollLock = false })
}

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

// ── 페어 행 — 소스 기준으로 타겟을 같은 행에 매핑 ──────────────
const pairedRows = computed(() => {
  const srcList = sortedSrcList.value
  const tgtMap  = {}
  sortedTgtList.value.forEach(t => { tgtMap[t.name] = t })

  // 소스 기준 행 생성
  const rows = srcList.map(s => ({
    src: s,
    tgt: tgtMap[s.name] || null,   // 소스와 동일 이름 타겟
  }))

  // 타겟에만 있는 항목 (소스에 없음) → 빈 소스 + 타겟
  const srcNames = new Set(srcList.map(t => t.name))
  sortedTgtList.value
    .filter(t => t.tgtOnly && !srcNames.has(t.name))
    .forEach(t => rows.push({ src: null, tgt: t }))

  return rows
})

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

    // ── v36 (2026-04-22) 매칭 로직 전면 수정 ────────────────────────────
    // 문제 이력:
    //   - 이전 로직은 소스(MSSQL)는 'credit.contract' 로, 타겟(MySQL)은 tgt.database
    //     와 schema_name 이 같다는 이유로 'contract' 로 정규화 → 두 문자열이 달라
    //     Set 비교에서 "소스 전용 42개, 타겟 전용 42개" 로 오판정.
    //   - 즉 소스/타겟 동일 테이블임에도 짝짓기에 실패.
    //
    // v36 전략 (v35 백엔드 임시 가드와 동일 철학):
    //   (1) 매칭 키는 bare name (점 뒷부분) 으로 통일 — 양쪽을 같은 키로 비교
    //   (2) 화면 표시는 소스 이름 우선 (스키마 유지), 소스 없으면 타겟 이름
    //   (3) 소스에서 bare name 충돌 (예: credit.contract + settlement.contract)
    //       을 감지해 has_conflict 플래그로 표시 → 경고 배너 노출 가능
    //   (4) 검증 실행 시 백엔드가 한 번 더 충돌 감지 (이중 방어)
    // TEMP-GUARD-V34C: 본 매칭은 이름 추측 기반. STEP 2 에서 Job.name_map 기반
    //                  으로 교체될 예정.
    const _bare = (t) => {
      if (typeof t === 'string') return t.includes('.') ? t.split('.').slice(-1)[0] : t
      return t.table_name || ''
    }
    const _display = (t, fallbackDb) => {
      if (typeof t === 'string') return t
      const sn = t.schema_name || ''
      const tn = t.table_name  || ''
      if (!sn || sn === 'dbo' || sn === fallbackDb) return tn
      return `${sn}.${tn}`
    }
    // v90.49: 정책에 따라 소스 이름을 타겟 이름 형식으로 변환 (매칭 키 일관화)
    //   본부장님 결정 (2026-04-27): underscore 정책 — customer.profile → customer_profile
    //   백엔드 schema_conversion_policy.map_table_name 과 동일 로직 (프론트 미러)
    const _policyKey = (t) => {
      let sch = ''
      let bare = ''
      if (typeof t === 'string') {
        if (t.includes('.')) {
          const parts = t.split('.')
          sch  = parts[0]
          bare = parts.slice(-1)[0]
        } else {
          bare = t
        }
      } else {
        sch  = (t.schema_name || '').trim()
        bare = (t.table_name || '').trim()
      }
      if (!bare) return ''
      // dbo / 빈 schema 는 결합 안 함
      if (!sch || sch.toLowerCase() === 'dbo') return bare
      // 이미 schema_ 접두어 있으면 중복 방지
      if (bare.toLowerCase().startsWith(sch.toLowerCase() + '_')) return bare
      const strat = schemaStrategy.value || 'underscore'
      if (strat === 'underscore') return `${sch}_${bare}`
      // drop / database 정책: bare 만
      return bare
    }

    const srcRaw = sRes.data || []
    const tgtRaw = tRes.data || []

    // bare name → 객체 매핑 (충돌 감지도 동시에)
    // v90.49: 매칭 키는 schema 정책 적용된 이름 (양쪽이 같은 키로 비교됨)
    //   소스 customer.profile → 매칭키 customer_profile
    //   타겟 customer_profile → 매칭키 customer_profile (이미 결합됨)
    //   → 매칭 성공
    const srcByBare = new Map()
    const srcConflicts = []  // [{bare, schemas:[...]}]
    for (const t of srcRaw) {
      const b = _policyKey(t)  // v90.49: bare → policyKey
      if (!b) continue
      const disp = _display(t, src.database)
      const sch  = (typeof t === 'object' && t.schema_name) ? t.schema_name : ''
      if (srcByBare.has(b)) {
        // 동일 매칭키 다중 스키마 → 충돌
        const prev = srcByBare.get(b)
        let entry = srcConflicts.find(c => c.bare === b)
        if (!entry) {
          entry = { bare: b, schemas: prev._schema ? [prev._schema] : [] }
          srcConflicts.push(entry)
        }
        if (sch && !entry.schemas.includes(sch)) entry.schemas.push(sch)
      } else {
        srcByBare.set(b, { name: disp, _schema: sch })
      }
    }
    const tgtByBare = new Map()
    for (const t of tgtRaw) {
      const b = _policyKey(t)  // v90.49: 타겟도 동일 함수 — 결과는 bare 와 같음 (이미 결합돼있거나 dbo)
      if (!b) continue
      tgtByBare.set(b, { name: _display(t, tgt.database) })
    }

    // 양쪽 bare name 의 합집합으로 표 구성
    const allBares = new Set([...srcByBare.keys(), ...tgtByBare.keys()])
    const rows = [...allBares].map(b => {
      const s = srcByBare.get(b)
      const t = tgtByBare.get(b)
      // 표시 이름: 소스 있으면 소스 이름 (스키마 정보 살아있음), 없으면 타겟 이름
      const displayName = s ? s.name : t.name
      return {
        name:     displayName,
        bareKey:  b,
        srcOnly:  !!s && !t,
        tgtOnly:  !s && !!t,
      }
    }).sort((a, b) => a.name.localeCompare(b.name))

    srcTables.value = rows
    // 기본 선택: 소스에 있는 테이블 전체 (displayName 기준, 검증 API 에 그대로 전달)
    selTables.value = rows.filter(r => !r.tgtOnly).map(r => r.name)

    // 충돌 정보 노출용 (프론트 다른 부분에서 참조 가능)
    tableMatchInfo.value = {
      has_conflict:   srcConflicts.length > 0,
      conflicts:      srcConflicts,
      src_count:      srcByBare.size,
      tgt_count:      tgtByBare.size,
      matched_count:  rows.filter(r => !r.srcOnly && !r.tgtOnly).length,
      validation_mode:'bare_name_match_v34c_tempguard',
    }

    const msg = srcConflicts.length > 0
      ? `테이블 ${rows.length}개 로드 (bare name 충돌 ${srcConflicts.length}건 탐지 — 검증 실행 시 백엔드가 거부)`
      : `테이블 ${rows.length}개 로드 (매칭 ${tableMatchInfo.value.matched_count}건, 소스전용 ${rows.filter(r=>r.srcOnly).length}건, 타겟전용 ${rows.filter(r=>r.tgtOnly).length}건)`
    app.notify(msg, srcConflicts.length > 0 ? 'warning' : 'success')
  } catch(e) { app.notify('테이블 목록 로드 실패: ' + e.message, 'error') }
  finally { loadingTables.value = false }
}

// v90.49: schema 정책 변경 시 자동 재매칭
//   소스/타겟 데이터는 변경 없으니 재 fetch 후 매칭 로직만 다시 적용.
//   본부장님 사용 시나리오: 정책 잘못 골라서 매칭 0개일 때 드롭다운만 바꾸면 즉시 재계산.
watch(schemaStrategy, async (newVal, oldVal) => {
  if (newVal !== oldVal && srcTables.value && srcTables.value.length > 0) {
    await loadTables()
  }
})

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

// v43: 실행/일시정지/중단 관리 — 테이블 검증용, 오브젝트 검증용 각각
const tblRs = useRunPauseStop({
  // 서버측 pause/resume/stop 은 현재 검증 엔진이 지원 안 해서 프론트에서만 처리.
  // 추후 백엔드에 /validate/pause 생기면 onPause 에 axios 호출 추가.
})
const objRs = useRunPauseStop()
// v42 호환: 기존 ref 는 composable 상태와 동기화 (하위 바인딩 유지)
const aborting = computed(() => tblRs.isAborting.value || objRs.isAborting.value)

const passRate  = computed(() => results.value.length ? Math.round(results.value.filter(r=>r.match).length/results.value.length*100) : 0)
const failCount = computed(() => results.value.filter(r=>!r.match).length)
const allSel    = computed(() => results.value.length && results.value.every(r=>r._sel))

function toggleAll(e) { results.value.forEach(r=>r._sel=e.target.checked) }
function toggleDetail(r) {
  // 보여줄 상세 내용이 있을 때만 토글
  const hasDetail = r.src_sample?.length || r.col_stats?.length ||
                    r.checksum_match === false || r.checksum_error ||
                    r.stats_match === false || r.stats_error
  if (!hasDetail) return
  detailRows[r.table] = !detailRows[r.table]
}
// v39: 사용자가 명시적으로 컬럼 정렬을 지정했는지 추적
// - false: 기본 "최신 검증 상단" 정렬
// - true: 사용자가 컬럼 헤더 클릭해서 설정한 정렬 사용
const sortUserChosen = ref(false)

function setSort(col) {
  sortUserChosen.value = true  // v39: 사용자가 명시적 정렬 선택
  if(sortCol.value===col) sortDir.value=sortDir.value==='asc'?'desc':'asc'
  else{sortCol.value=col;sortDir.value='asc'}
}
function sortIco(col) { if(sortCol.value!==col)return'↕'; return sortDir.value==='asc'?'↑':'↓' }
// v39: "최신순 정렬" 해제 (기본으로 돌아가기)
function resetSortToRecent() {
  sortUserChosen.value = false
}

const filteredResults = computed(() => {
  let r = results.value.slice()
  if (filterMode.value==='fail') r=r.filter(x=>!x.match)
  if (filterMode.value==='ok')   r=r.filter(x=>x.match)

  // v65: 먼저 '진행 중' 행을 최상단 고정 (본부장 요청: 화면 왔다갔다 방지).
  //   오브젝트 검증과 동일한 UX.
  //   오브젝트 쪽은 testing/srcTesting 플래그, 테이블은 running/checking 플래그 사용.
  const pinBusy = (a, b) => {
    const aBusy = (a.running || a.checking || a.testing) ? 0 : 1
    const bBusy = (b.running || b.checking || b.testing) ? 0 : 1
    return aBusy - bBusy
  }

  // v39: 기본 정렬 — 최신 검증이 상단 (재이관 후 갱신된 행이 위로)
  if (!sortUserChosen.value) {
    r.sort((a, b) => {
      const p = pinBusy(a, b)
      if (p !== 0) return p
      return (b._updatedAt || 0) - (a._updatedAt || 0)
    })
    return r
  }

  // 사용자 선택 정렬
  r.sort((a,b)=>{
    const p = pinBusy(a, b)
    if (p !== 0) return p   // v65: 진행 중 우선
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

// ── 검증 진행 상태 ────────────────────────────────────────────
const progCurrent = ref(0)   // 현재 처리 테이블 번호
const progTotal   = ref(0)   // 전체 테이블 수
const progTable   = ref('')  // 현재 처리 중인 테이블명
const progElapsed = ref(0)   // 경과시간 (초)
let   _progTimer  = null

function _startProgTimer() {
  const t0 = Date.now()
  _progTimer = setInterval(() => { progElapsed.value = Math.round((Date.now()-t0)/1000) }, 1000)
}
function _stopProgTimer() { clearInterval(_progTimer); _progTimer = null }

// 경과시간 포맷
function fmtElapsed(sec) {
  if (sec < 60) return sec + '초'
  const m = Math.floor(sec/60), s = sec%60
  return m + '분 ' + String(s).padStart(2,'0') + '초'
}
// 예상 완료 시각
function fmtRemainTime(current, total, elapsedSec) {
  if (current < 2 || elapsedSec < 2) return '측정 중...'
  const remainSec = Math.round(elapsedSec / current * (total - current))
  if (remainSec <= 0) return '거의 완료'
  const h = Math.floor(remainSec / 3600)
  const m = Math.floor((remainSec % 3600) / 60)
  const s = remainSec % 60
  if (h > 0) return h + '시간 ' + String(m).padStart(2,'0') + '분 ' + String(s).padStart(2,'0') + '초'
  if (m > 0) return m + '분 ' + String(s).padStart(2,'0') + '초'
  return s + '초'
}
function fmtETA(current, total, elapsedSec) {
  if (current < 2 || elapsedSec < 2) return '측정 중...'
  const remainSec = Math.round(elapsedSec / current * (total - current))
  const fin = new Date(Date.now() + remainSec * 1000)
  const h = fin.getHours(), m = fin.getMinutes(), s = fin.getSeconds()
  const ampm = h < 12 ? '오전' : '오후'
  return ampm + ' ' + String(h%12||12).padStart(2,'0') + ':' + String(m).padStart(2,'0') + ':' + String(s).padStart(2,'0')
}

async function runValidate() {
  if (!connector.bothConnected) {
    app.notify(`검증 불가: 연결 상태 확인 필요 (소스=${connector.source.status}, 타겟=${connector.target.status})`, 'error')
    return
  }
  // v90.76 (2026-04-28): 검증 실행 시 무조건 테이블 목록 새로고침
  //   본부장님 호소: "AI로 만든 후 검증 버튼 누르면 다시 DB에서 읽어 와야"
  //   이전: srcTables 비어있을 때만 loadTables → 캐시된 리스트 사용 → AI 변경 반영 안 됨
  //   처방: 매 검증 실행마다 강제 reload — 최신 DB 상태로 검증
  await loadTables()
  if (!srcTables.value.length) { app.notify('테이블 목록을 불러오지 못했습니다', 'error'); return }
  
  running.value=true; results.value=[]; summary.value=null
  progPct.value=0; progCurrent.value=0; progTotal.value=0
  progTable.value=''; progElapsed.value=0
  _startProgTimer()

  const src=connector.source, tgt=connector.target
  const allSelAll = selTables.value.length === srcTables.value.filter(t=>!t.tgtOnly).length
  const tables = allSelAll ? [] : selTables.value

  const body = {
    src_info:{db_type:src.dbType,host:src.host,port:src.port,username:src.username,password:src.password,database:src.database},
    tgt_info:{db_type:tgt.dbType,host:tgt.host,port:tgt.port,username:tgt.username,password:tgt.password,database:tgt.database},
    tables, method:mode.value,
  }

  // v43: composable 로 상태 관리 시작
  await tblRs.start()
  let _wasAborted = false

  try {
    const res = await fetch('/api/v1/validate/run/stream', {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body),
      signal: tblRs.abortCtl.signal,
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)

    const reader = res.body.getReader()
    const dec    = new TextDecoder()
    let   buf    = ''

    while (true) {
      // v43: 일시정지 상태면 대기 (SSE 스트림 읽기 자체를 늦춤)
      //      백엔드가 버퍼를 쌓아뒀다가 resume 시 흘려보내줌.
      //      중단(abort) 시 waitIfPaused 가 즉시 빠져나와 다음 read 에서 AbortError 발생.
      await tblRs.waitIfPaused()
      if (tblRs.stopFlag.value) break

      const { done, value } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      const lines = buf.split("\n")
      buf = lines.pop()
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue
        try {
          const ev = JSON.parse(line.slice(6))
          if (ev.type === 'start') {
            progTotal.value = ev.total
            progMsg.value   = `0 / ${ev.total} 테이블 검증 중...`
          } else if (ev.type === 'progress') {
            progCurrent.value = ev.current
            progTable.value   = ev.table
            progPct.value     = Math.round(ev.current / ev.total * 100)
            progMsg.value     = `${ev.current} / ${ev.total} — ${ev.table}`
          } else if (ev.type === 'result') {
            progCurrent.value = ev.current
            progPct.value     = Math.round(ev.current / ev.total * 100)
            progElapsed.value = Math.round(ev.elapsed)
            results.value.push({...ev.item, _sel:false, _updatedAt: Date.now()})
          } else if (ev.type === 'done') {
            progPct.value = 100
            const _now = Date.now()
            results.value = ev.results.map((r, i) => ({...r, _sel:false, _updatedAt: _now - (ev.results.length - i)}))
            const rmap={}; ev.results.forEach(r=>{rmap[r.table]=r}); lastResultMap.value=rmap
            summary.value = ev.summary
            app.notify(`검증 완료 — ${ev.summary.passed}/${ev.summary.total} 일치 (${ev.summary.pass_rate}%)`,
              ev.summary.failed===0?'success':'warn')
            localStorage.setItem('val_mode', mode.value)
            loadHistory()
          } else if (ev.type === 'error') {
            app.notify('검증 오류: ' + ev.msg, 'error')
          }
        } catch { /* JSON 파싱 실패 무시 */ }
      }
    }
  } catch(e) {
    if (e.name === 'AbortError') {
      _wasAborted = true
      const partialCount = results.value.length
      const passed = results.value.filter(r=>r.match).length
      summary.value = {
        total: partialCount, passed, failed: partialCount - passed,
        pass_rate: partialCount > 0 ? Math.round(passed/partialCount*100*10)/10 : 0,
        aborted: true,
        elapsed_sec: progElapsed.value,
      }
      app.notify(`검증 중단됨 — ${partialCount}개 부분 결과 보존`, 'warn')
    } else {
      app.notify('검증 실패: ' + e.message, 'error')
    }
  } finally {
    running.value=false
    tblRs.finish()  // v43: composable 상태 idle 로 복원
    _stopProgTimer()
    if (!_wasAborted) {
      setTimeout(()=>{ progPct.value=0; progMsg.value=''; progTable.value=''; progCurrent.value=0 }, 2000)
    } else {
      setTimeout(()=>{ progPct.value=0; progMsg.value=''; progTable.value=''; progCurrent.value=0 }, 5000)
    }
  }
}

// v43: 공통 진입점 — 실행 / 일시정지 / 재개 / 중단
async function handleRunPause() {
  // 현재 활성 composable 결정 (탭 기준 + 실제 활성 상태)
  const rs = vType.value === 'table' ? tblRs : objRs
  if (rs.isRunning.value)      { await rs.pause()  }
  else if (rs.isPaused.value)  { await rs.resume() }
}
async function handleStop() {
  const rs = vType.value === 'table' ? tblRs : objRs
  await rs.stop()
}
async function handleStart() {
  if (vType.value === 'table') { await runValidate() }
  else                          { await runObjValidate() }
}

// ── 재이관 모달 state ──────────────────────────────────────────
const remigModal   = ref(false)
const remigRow     = ref(null)      // 선택한 결과 행
const remigMode    = ref('truncate') // truncate | drop_recreate | ai
const remigRunning = ref(false)
const remigJobId   = ref('')
const remigJobStatus = ref('')       // idle | running | done | error
const remigLogs    = ref([])
let   remigPollTimer = null
const remigLogRef = ref(null)

// ── v37: 재이관 진행률 상태바용 ────────────────────────────────
// 백엔드 /api/v1/jobs/{id} 응답의 progress/rows_processed/rows_total/started_at
// 등을 활용해 실시간 상태바·경과시간·ETA·처리속도 등을 표시.
const remigProg = ref({
  pct:          0,      // 진행률 (0-100)
  rowsDone:     0,      // 처리된 행 수
  rowsTotal:    0,      // 전체 예상 행 수
  tablesDone:   0,      // 완료된 테이블 수
  tablesTotal:  0,      // 전체 테이블 수
  currentTable: '',     // 현재 처리 중 테이블명
  elapsedSec:   0,      // 경과 시간 (초)
  etaSec:       null,   // 예상 남은 시간 (초, null = 측정 중)
  rowsPerSec:   0,      // 처리 속도 (rows/sec)
  startedAt:    0,      // Date.now() 기준 시작 시각 (프론트 로컬)
})
let remigElapsedTimer = null  // 1초마다 경과시간 업데이트용 setInterval

const remigOpts = [
  { v:'truncate',     icon:'🗑',  title:'TRUNCATE 후 재이관',  desc:'데이터만 삭제 후 다시 INSERT (스키마 유지)' },
  { v:'drop_recreate',icon:'🔄',  title:'DROP 후 재생성',       desc:'테이블 완전 삭제 후 스키마·데이터 재구성' },
  { v:'ai',           icon:'🤖',  title:'AI 변환 재이관',       desc:'Claude AI가 불일치 원인 분석 후 자동 재이관' },
]

function openRemigModal(row) {
  remigRow.value     = row
  remigModal.value   = true
  remigMode.value    = 'truncate'
  remigRunning.value = false
  remigJobId.value   = ''
  remigJobStatus.value = 'idle'
  remigLogs.value    = []
  clearInterval(remigPollTimer)
  // v37: 진행률 상태 초기화
  remigProg.value = { pct:0, rowsDone:0, rowsTotal:0, tablesDone:0, tablesTotal:0,
                      currentTable:'', elapsedSec:0, etaSec:null, rowsPerSec:0, startedAt:0 }
  clearInterval(remigElapsedTimer); remigElapsedTimer = null
}
function closeRemigModal() {
  remigModal.value = false
  clearInterval(remigPollTimer)
  clearInterval(remigElapsedTimer); remigElapsedTimer = null  // v37
  remigRow.value   = null
  // v49: 모달 폴링은 종료하되, activeRemigJobs 의 백그라운드 추적은 계속된다.
  // 사용자가 모달을 닫았다고 해서 이미 시작된 재이관을 놓치면 안 된다.
}

// ── v49: 백그라운드 재이관 추적 ──────────────────────────────
// 팝업 닫아도 완료된 재이관을 놓치지 않도록 전역 폴링 유지.
// 구조: { jobId: { table, mode, startedAt } }
const activeRemigJobs = ref({})
let bgRemigPollTimer = null

// 완료 감지 시 해당 테이블 단건 재검증 + 결과 행에 _remigResult 마킹
async function _handleBgRemigFinish(jobId, info, finalStatus) {
  const table = info.table
  // 활성 목록에서 제거 (중복 처리 방지)
  const newMap = { ...activeRemigJobs.value }
  delete newMap[jobId]
  activeRemigJobs.value = newMap

  if (finalStatus === 'completed') {
    // 자동 재검증
    try {
      const src = connector.source, tgt = connector.target
      const { data } = await axios.post('/api/v1/validate/run', {
        src_info: { db_type:src.dbType, host:src.host, port:src.port, username:src.username, password:src.password, database:src.database },
        tgt_info: { db_type:tgt.dbType, host:tgt.host, port:tgt.port, username:tgt.username, password:tgt.password, database:tgt.database },
        tables: [table], method: mode.value,
      })
      // 매칭 — 정확 → bare 순
      let newRow = data.results?.find(r => r.table === table)
      if (!newRow && data.results?.length) {
        const bare = table.includes('.') ? table.split('.').slice(-1)[0] : table
        newRow = data.results.find(r => {
          const rb = (r.table || '').includes('.') ? r.table.split('.').slice(-1)[0] : r.table
          return rb === bare
        })
      }
      if (newRow) {
        let idx = results.value.findIndex(r => r.table === table)
        if (idx < 0) {
          const bare = table.includes('.') ? table.split('.').slice(-1)[0] : table
          idx = results.value.findIndex(r => {
            const rb = (r.table || '').includes('.') ? r.table.split('.').slice(-1)[0] : r.table
            return rb === bare
          })
        }
        if (idx >= 0) {
          const prev = results.value[idx]
          results.value.splice(idx, 1, {
            ...newRow,
            table: prev.table,
            _sel: false,
            _updatedAt: Date.now(),
            _justUpdated: true,
            _lastRemigMode: info.mode,
            // v49: 영구 배지 — 재이관 성공/실패 마킹. 수동 runValidate 시 제거됨.
            _remigResult: {
              status: newRow.match ? 'success' : 'failed',
              at: Date.now(),
              mode: info.mode,
            },
          })
          // lastResultMap + summary 갱신
          const newRmap = { ...lastResultMap.value }
          newRmap[prev.table] = newRow
          if (newRow.table && newRow.table !== prev.table) newRmap[newRow.table] = newRow
          lastResultMap.value = newRmap
          const total  = results.value.length
          const passed = results.value.filter(r => r.match).length
          summary.value = { total, passed, failed: total - passed,
                            pass_rate: total > 0 ? Math.round(passed/total*100) : 0 }
          setTimeout(() => {
            const cur = results.value.findIndex(r => r._updatedAt === results.value[idx]?._updatedAt)
            if (cur >= 0 && results.value[cur]?._justUpdated) {
              results.value[cur] = { ...results.value[cur], _justUpdated: false }
            }
          }, 3000)
          app.notify(
            `[${table}] 재이관 ${newRow.match ? '성공' : '실패'} — 결과 갱신됨`,
            newRow.match ? 'success' : 'warn'
          )
        }
      }
    } catch (e) {
      console.error('[v49 bg 재검증 실패]', e)
      app.notify(`[${table}] 재이관 후 재검증 오류 — 수동 검증 필요`, 'error')
    }
  } else {
    // error / aborted — 성공 배지 달지 않고 실패 표시
    const idx = results.value.findIndex(r => r.table === table)
    if (idx >= 0) {
      results.value[idx] = {
        ...results.value[idx],
        _updatedAt: Date.now(),
        _remigResult: { status: 'failed', at: Date.now(), mode: info.mode },
      }
    }
    app.notify(
      `[${table}] 재이관 ${finalStatus === 'aborted' ? '중단됨' : '실패'}`,
      'error'
    )
  }
}

async function _tickBgRemigPolling() {
  const jobs = activeRemigJobs.value
  const jobIds = Object.keys(jobs)
  if (!jobIds.length) return
  // 각 Job 상태 조회 (병렬)
  const checks = jobIds.map(async (jid) => {
    try {
      const { data: jd } = await axios.get(`/api/v1/jobs/${jid}`)
      if (['completed', 'error', 'aborted'].includes(jd.status)) {
        await _handleBgRemigFinish(jid, jobs[jid], jd.status)
      }
    } catch (e) {
      // 404: Job 삭제됨 — 정리
      if (e.response?.status === 404) {
        const newMap = { ...activeRemigJobs.value }
        delete newMap[jid]
        activeRemigJobs.value = newMap
      }
    }
  })
  await Promise.all(checks)
}

function startBgRemigPolling() {
  if (bgRemigPollTimer) return
  bgRemigPollTimer = setInterval(_tickBgRemigPolling, 15000)  // 15초 주기
}
function stopBgRemigPolling() {
  if (bgRemigPollTimer) { clearInterval(bgRemigPollTimer); bgRemigPollTimer = null }
}

// v49: 빠른 재시도 — 우클릭 또는 길게누름 시 직전 모드 그대로 즉시 재이관
async function quickRetryRemig(row) {
  const lastMode = row._lastRemigMode
  if (!lastMode) {
    // 이전 재이관 기록 없으면 정상 팝업 열기
    openRemigModal(row)
    return
  }
  app.notify(`[${row.table}] ${_fmtRemigMode(lastMode)} 모드로 즉시 재시도`, 'info')
  // openRemigModal + remigMode 설정 + doRemig 를 순차 호출
  openRemigModal(row)
  remigMode.value = lastMode
  // 다음 tick 까지 기다려 모달 반응형이 안정된 후 실행
  await nextTick()
  doRemig()
}

// 길게 누름 (500ms) 감지 — 터치/마우스 공통
let longPressTimer = null
function startLongPressRemig(row, ev) {
  cancelLongPressRemig()
  // 좌클릭/주 터치만 (우클릭은 contextmenu 가 이미 잡음)
  if (ev.type === 'mousedown' && ev.button !== 0) return
  longPressTimer = setTimeout(() => {
    longPressTimer = null
    quickRetryRemig(row)
  }, 500)
}
function cancelLongPressRemig() {
  if (longPressTimer) { clearTimeout(longPressTimer); longPressTimer = null }
}

function _fmtRemigMode(m) {
  return ({ truncate: 'TRUNCATE', drop_recreate: 'DROP 재생성', ai: 'AI 변환' })[m] || m || '—'
}
function _fmtRemigAt(ts) {
  if (!ts) return '—'
  const d = new Date(ts)
  return `${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

// v45: 재이관 일시정지/재개/중단 — 백엔드 /jobs/{id}/pause,resume,stop 호출
// v46: 폴링 가드 — 사용자가 pause 클릭한 직후 서버가 비동기 반영 전 running 을
// 돌려줘서 UI 가 paused 분기로 전환 안 되던 문제 대비. 최근 요청 시각을
// remigPauseGuardTs 에 찍고, 폴링 쪽에서 3초 이내면 paused 로 고정한다.
// v48: 로그에 시각 + 행동 명시 — 사용자가 실제로 어떤 버튼을 언제 눌렀는지
// 추적 가능하게 하여 "재시작했는데 진행 안 됨" 같은 증상 원인 분석 돕는다.
const remigPauseGuardTs = ref(0)
function _nowHms() {
  const d = new Date()
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`
}
async function remigPause() {
  if (!remigJobId.value || remigJobStatus.value !== 'running') return
  try {
    remigLogs.value.push(`👤 [${_nowHms()}] 사용자 클릭: 일시정지`)
    await axios.post(`/api/v1/jobs/${remigJobId.value}/pause`)
    remigJobStatus.value = 'paused'
    remigPauseGuardTs.value = Date.now()
    remigLogs.value.push('⏸ 일시정지됨 — 계속 버튼을 누르면 이어서 진행됩니다')
    app.notify('재이관 일시정지', 'info')
  } catch (e) {
    app.notify('일시정지 실패: ' + (e.response?.data?.detail || e.message), 'error')
  }
}
async function remigResume() {
  if (!remigJobId.value || remigJobStatus.value !== 'paused') return
  try {
    remigLogs.value.push(`👤 [${_nowHms()}] 사용자 클릭: 계속 (재개)`)
    await axios.post(`/api/v1/jobs/${remigJobId.value}/resume`)
    remigJobStatus.value = 'running'
    remigPauseGuardTs.value = 0
    remigLogs.value.push('▶ 재개 요청 전송됨 — 서버 응답 대기 중...')
    app.notify('재이관 재개', 'info')
  } catch (e) {
    app.notify('재개 실패: ' + (e.response?.data?.detail || e.message), 'error')
  }
}
async function remigStop() {
  if (!remigJobId.value || !['running', 'paused'].includes(remigJobStatus.value)) return
  if (!confirm('진행 중인 재이관을 중단하시겠습니까?\n(이미 이관된 부분은 타겟에 남아있을 수 있습니다)')) return
  try {
    remigLogs.value.push(`👤 [${_nowHms()}] 사용자 클릭: 중단`)
    await axios.post(`/api/v1/jobs/${remigJobId.value}/stop`)
    remigJobStatus.value = 'aborting'
    remigLogs.value.push('🛑 중단 요청 전송 — 서버 정리 대기 중...')
  } catch (e) {
    app.notify('중단 실패: ' + (e.response?.data?.detail || e.message), 'error')
  }
}
// v45: 에러/중단 상태에서 재실행 — Job 설정 그대로 다시 시작
async function remigRestart() {
  if (!['error', 'aborted'].includes(remigJobStatus.value)) return
  // 상태 초기화 (openRemigModal 과 동일하되 row 는 유지)
  remigJobStatus.value = 'idle'
  remigJobId.value = ''
  remigLogs.value = []
  remigProg.value = { pct:0, rowsDone:0, rowsTotal:0, tablesDone:0, tablesTotal:0,
                      currentTable:'', elapsedSec:0, etaSec:null, rowsPerSec:0, startedAt:0 }
  // doRemig 가 처음부터 다시 실행
  await doRemig()
}

// ── v37: 시간/속도 포맷 헬퍼 ─────────────────────────────────
function _fmtDur(sec) {
  if (sec == null || !isFinite(sec) || sec < 0) return '—'
  sec = Math.round(sec)
  if (sec < 60) return sec + '초'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  if (h > 0) return `${h}시간 ${String(m).padStart(2,'0')}분`
  return `${m}분 ${String(s).padStart(2,'0')}초`
}
function _fmtFinishTime(etaSec) {
  if (etaSec == null || !isFinite(etaSec) || etaSec < 0) return '—'
  const fin = new Date(Date.now() + etaSec * 1000)
  const h = fin.getHours(), m = fin.getMinutes()
  const ampm = h < 12 ? '오전' : '오후'
  return `${ampm} ${String(h%12||12).padStart(2,'0')}:${String(m).padStart(2,'0')}`
}
function _fmtRowsPerSec(rps) {
  if (!rps || !isFinite(rps) || rps <= 0) return '—'
  if (rps >= 1000) return `${(rps/1000).toFixed(1)}K rows/s`
  return `${Math.round(rps)} rows/s`
}

async function doRemig() {
  if (!remigRow.value || remigRunning.value) return
  remigRunning.value   = true
  remigJobStatus.value = 'running'
  remigLogs.value      = ['⏳ 재이관 Job 생성 중...']

  // v37: 재이관 시작 시각 기록 + 1초마다 경과시간 업데이트 타이머 가동
  // v45: 일시정지 중엔 경과시간 누적 멈춤 — paused 진입 시 보정용 오프셋 사용
  remigProg.value.startedAt = Date.now()
  remigProg.value.elapsedSec = 0
  remigProg.value.etaSec = null
  clearInterval(remigElapsedTimer)
  let _lastTick = Date.now()
  remigElapsedTimer = setInterval(() => {
    if (!remigProg.value.startedAt) return
    const now = Date.now()
    // v45: running 중일 때만 elapsed 증가. paused/aborting 은 유지.
    if (remigJobStatus.value === 'running') {
      remigProg.value.elapsedSec += Math.max(0, Math.floor((now - _lastTick) / 1000))
    }
    _lastTick = now
    const pct = remigProg.value.pct
    if (pct > 0 && pct < 100 && remigProg.value.elapsedSec >= 3) {
      remigProg.value.etaSec = Math.max(0, Math.round(remigProg.value.elapsedSec * (100 - pct) / pct))
    } else if (remigJobStatus.value === 'paused') {
      // 일시정지 중엔 ETA "—" 로 표시
      remigProg.value.etaSec = null
    }
  }, 1000)

  const src = connector.source
  const tgt = connector.target
  const table = remigRow.value.table

  try {
    const payload = {
      name:         `[재이관] ${table}`,
      src_db:       src.dbType,   src_host: src.host,
      src_database: src.database, src_username: src.username,
      src_password: src.password, src_port: src.port,
      tgt_db:       tgt.dbType,   tgt_host: tgt.host,
      tgt_database: tgt.database, tgt_username: tgt.username,
      tgt_password: tgt.password, tgt_port: tgt.port,
      tables:       [table],
      table_mode:   'schema_data',
      drop_table:   remigMode.value === 'drop_recreate',
      truncate_target: remigMode.value === 'truncate',
      obj_convert:  remigMode.value === 'ai',
      obj_engine:   remigMode.value === 'ai' ? 'claude' : 'rules',
    }
    const { data } = await axios.post('/api/v1/jobs/', payload)
    remigJobId.value = data.id || data.job_id || ''
    remigLogs.value.push(`✅ Job 생성됨 (ID: ${remigJobId.value})`)
    remigLogs.value.push('📡 진행 상황 모니터링 중...')

    // v49: 백그라운드 추적용 등록 — 팝업 닫아도 이 Job 이 완료되면
    // 결과 행이 자동 갱신되도록 activeRemigJobs 맵에 추가.
    if (remigJobId.value && table) {
      activeRemigJobs.value[remigJobId.value] = {
        table,
        mode: remigMode.value,
        startedAt: Date.now(),
      }
      // 행에 _lastRemigMode 기록 — 나중에 우클릭 빠른 재시도용
      const rowIdx = results.value.findIndex(r => r.table === table)
      if (rowIdx >= 0) {
        results.value[rowIdx] = { ...results.value[rowIdx], _lastRemigMode: remigMode.value }
      }
    }

    // 폴링으로 Job 상태 추적
    remigPollTimer = setInterval(async () => {
      if (!remigJobId.value) return
      try {
        const { data: jd } = await axios.get(`/api/v1/jobs/${remigJobId.value}`)
        let st = jd.status
        // v46: pause 요청 직후 3초 가드 — 서버가 비동기 반영 전 'running' 을
        // 돌려줘도 UI 는 paused 유지. 단 'completed'/'error'/'aborted' 는 최종 상태이므로 덮어씀.
        if (remigPauseGuardTs.value > 0
            && (Date.now() - remigPauseGuardTs.value) < 3000
            && !['completed','error','aborted'].includes(st)) {
          st = 'paused'
        } else if (remigPauseGuardTs.value > 0
                   && (Date.now() - remigPauseGuardTs.value) >= 3000) {
          remigPauseGuardTs.value = 0  // 가드 만료
        }
        remigJobStatus.value = st

        // 기본 카운트
        const done = jd.table_done || 0
        const tot  = jd.table_total || 1
        const pct  = jd.progress || 0
        // item_statuses에서 현재 진행 중인 테이블명 표시
        const statuses = jd.item_statuses || {}
        const runningTbl = Object.entries(statuses).find(([,v]) => v.status === 'running')?.[0] || ''
        const doneTbls   = Object.values(statuses).filter(v => v.status === 'done' || v.status === 'completed').length
        const displayDone = doneTbls || done

        // ── v41: rowsDone/rowsTotal 우선순위 폴백 ───────────────────
        // 문제: jd.rows_processed 는 "완료된 테이블 누적" 이라 이관 중엔 0 에 머문다.
        //       단일 테이블 재이관이면 완료 순간에만 값이 올라옴 → "퍼센트는 올라가는데
        //       건수는 0" 증상.
        //
        // 해결:
        //   - 이관 중 (runningTbl 있음): rows_processed(완료누적) + current_table_rows_done(현재)
        //   - 완료 후 (runningTbl 없음): rows_processed 만 (current_table_rows_done 은
        //     마지막 테이블 값이 그대로 남아있어서 더하면 더블카운트)
        //
        //   1순위 파생: current_table_rows_done (엔진이 청크마다 갱신)
        //   2순위 폴백: item_statuses[runningTbl].rows_src (같은 값, 다른 경로)
        const _currentTblRows = runningTbl ? (
          (jd.current_table_rows_done ?? null) !== null ? jd.current_table_rows_done :
          (statuses[runningTbl]?.rows_src) ? statuses[runningTbl].rows_src :
          0
        ) : 0
        const _completedRows = jd.rows_processed || 0
        const rowsDone  = _completedRows + _currentTblRows

        // rowsTotal: 단일 테이블이면 현재 테이블 total, 아니면 전체 Job rows_total
        const _currentTblTotal = jd.current_table_rows_total || 0
        const _jobRowsTotal    = jd.rows_total || 0
        // 단일 테이블 재이관의 경우 (tot === 1) 현재 테이블 total 이 더 정확
        const rowsTotal = (tot === 1 && _currentTblTotal > 0)
          ? _currentTblTotal
          : (_jobRowsTotal || _currentTblTotal)

        // ── v37: 상태바 정보 갱신 ────────────────────────────
        // pct: 백엔드 progress 를 우선, 없으면 rows 기반 계산
        let effectivePct = pct
        if ((!effectivePct || effectivePct === 0) && rowsTotal > 0) {
          effectivePct = Math.round(rowsDone / rowsTotal * 100)
        }
        const elapsed = remigProg.value.elapsedSec  // 타이머가 이미 갱신 중
        const rowsPerSec = elapsed > 0 ? rowsDone / elapsed : 0
        // ETA: 진행률 기반 (타이머 블록에서도 계산하지만, 여기서 한 번 더 즉시 반영)
        let etaSec = remigProg.value.etaSec
        if (effectivePct > 0 && effectivePct < 100 && elapsed >= 3) {
          etaSec = Math.max(0, Math.round(elapsed * (100 - effectivePct) / effectivePct))
        } else if (effectivePct >= 100) {
          etaSec = 0
        }
        remigProg.value = {
          ...remigProg.value,
          pct:          Math.min(100, Math.max(0, effectivePct)),
          rowsDone,
          rowsTotal,
          tablesDone:   displayDone,
          tablesTotal:  tot,
          currentTable: runningTbl || (effectivePct >= 100 ? '' : (remigRow.value?.table || '')),
          etaSec,
          rowsPerSec,
        }

        // 로그: 압축된 한 줄 (v41: rowsDone 에 진행 중 테이블 실시간 반영)
        const rowsStr = rowsDone.toLocaleString()
        const totalStr = rowsTotal > 0 ? `/${rowsTotal.toLocaleString()}` : ''
        const newLog = runningTbl
          ? `📊 ${displayDone}/${tot} · ${runningTbl} 이관 중 · ${rowsStr}${totalStr} rows · ${effectivePct}%`
          : `📊 ${displayDone}/${tot} 테이블 · ${rowsStr}${totalStr} rows · ${effectivePct}%`
        const lastLog = remigLogs.value[remigLogs.value.length - 1] || ''
        if (!lastLog.startsWith('📊')) remigLogs.value.push(newLog)
        else remigLogs.value[remigLogs.value.length - 1] = newLog
        // 로그박스 자동 스크롤
        await nextTick(); if (remigLogRef.value) remigLogRef.value.scrollTop = remigLogRef.value.scrollHeight

        // item_statuses가 모두 완료됐는데 status가 completed로 안 바뀐 경우 보완
        const allDone = tot > 0 && Object.values(jd.item_statuses || {}).length >= tot &&
          Object.values(jd.item_statuses || {}).every(v => v.status === 'done' || v.status === 'error')
        if (st === 'completed' || allDone) {
          clearInterval(remigPollTimer)
          clearInterval(remigElapsedTimer); remigElapsedTimer = null  // v37
          remigRunning.value = false
          // v37: 완료 시 100% 로 마감
          remigProg.value = { ...remigProg.value, pct:100, etaSec:0, currentTable:'' }
          remigLogs.value.push(`🎉 완료! ${rowsStr} rows 이관됨 (${_fmtDur(remigProg.value.elapsedSec)} 소요)`)
          // v49: 모달이 처리했으니 백그라운드 추적 맵에서 제거 (중복 재검증 방지)
          if (remigJobId.value && activeRemigJobs.value[remigJobId.value]) {
            const m = { ...activeRemigJobs.value }
            delete m[remigJobId.value]
            activeRemigJobs.value = m
          }
          // 해당 테이블만 단건 재검증 (전체 runValidate 대신)
          setTimeout(async () => {
            const table = remigRow.value?.table
            if (!table || remigRow.value?._bulk) {
              runValidate()
              return
            }
            try {
              const src = connector.source, tgt = connector.target
              console.log('[v39 재검증 요청]', { table, method: mode.value })
              const { data } = await axios.post('/api/v1/validate/run', {
                src_info: { db_type:src.dbType, host:src.host, port:src.port, username:src.username, password:src.password, database:src.database },
                tgt_info: { db_type:tgt.dbType, host:tgt.host, port:tgt.port, username:tgt.username, password:tgt.password, database:tgt.database },
                tables: [table], method: mode.value,
              })
              console.log('[v39 재검증 응답]', data)

              // v39: 방어적 매칭 — 정확히 일치 시도 → 실패 시 bare name 으로 재시도
              let newRow = data.results?.find(r => r.table === table)
              if (!newRow && data.results?.length) {
                // 응답 테이블명이 변형됐을 가능성 (schema prefix 제거/추가 등)
                const bare = table.includes('.') ? table.split('.').slice(-1)[0] : table
                newRow = data.results.find(r => {
                  const rb = (r.table || '').includes('.') ? r.table.split('.').slice(-1)[0] : r.table
                  return rb === bare
                })
                if (newRow) {
                  console.warn(`[v39] 재검증 응답 table 변형 감지 — 요청=${table}, 응답=${newRow.table} (bare name 매칭)`)
                  // 기존 행을 찾을 때도 bare name 매칭
                }
              }

              if (newRow) {
                // v39: 결과 리스트에서 기존 행 찾기 — 정확 일치 우선, 실패 시 bare
                let idx = results.value.findIndex(r => r.table === table)
                if (idx < 0) {
                  const bare = table.includes('.') ? table.split('.').slice(-1)[0] : table
                  idx = results.value.findIndex(r => {
                    const rb = (r.table || '').includes('.') ? r.table.split('.').slice(-1)[0] : r.table
                    return rb === bare
                  })
                }
                // v39: 결과 행에 _updatedAt 타임스탬프 추가 (정렬 및 하이라이트용)
                // 원본 테이블명은 그대로 유지 (표시명 일관성)
                // v49: _remigResult 배지 마킹 + _lastRemigMode 저장 (빠른 재시도용)
                const newRowUi = {
                  ...newRow,
                  table: (idx >= 0 ? results.value[idx].table : newRow.table),  // 표시명 유지
                  _sel: false,
                  _updatedAt: Date.now(),
                  _justUpdated: true,   // 잠깐 하이라이트용
                  _lastRemigMode: remigMode.value,
                  _remigResult: {
                    status: newRow.match ? 'success' : 'failed',
                    at: Date.now(),
                    mode: remigMode.value,
                  },
                }
                if (idx >= 0) {
                  results.value.splice(idx, 1, newRowUi)
                  console.log(`[v39] 행 ${idx} 갱신 완료 — match=${newRowUi.match}, diff=${newRowUi.diff}`)
                } else {
                  results.value.push(newRowUi)
                  console.warn(`[v39] 기존 행 못 찾음 — 새로 추가 (table=${table})`)
                }
                // lastResultMap 갱신 — 리스트 색상 즉시 반영 (두 키 모두 매핑 — 원본/bare)
                const newMap = { ...lastResultMap.value }
                newMap[newRowUi.table] = newRow
                if (newRow.table && newRow.table !== newRowUi.table) newMap[newRow.table] = newRow
                lastResultMap.value = newMap
                // summary 재계산
                const total  = results.value.length
                const passed = results.value.filter(r => r.match).length
                const failed = total - passed
                summary.value = { total, passed, failed, pass_rate: total > 0 ? Math.round(passed/total*100) : 0 }
                remigLogs.value.push(`✅ 재검증 완료 — ${newRow.match ? '✓ 일치' : '✗ 불일치 (차이: ' + newRow.diff + ')'}`)
                // v39: 3초 후 하이라이트 해제
                setTimeout(() => {
                  const cur = results.value.findIndex(r => r._updatedAt === newRowUi._updatedAt)
                  if (cur >= 0 && results.value[cur]._justUpdated) {
                    results.value[cur]._justUpdated = false
                  }
                }, 3000)
              } else {
                // 매칭 완전 실패 — 전체 재검증으로 fallback
                console.warn('[v39] 재검증 응답에서 해당 테이블을 못 찾음 — 전체 재검증으로 fallback')
                remigLogs.value.push(`⚠ 단건 재검증 매칭 실패 — 전체 재검증 실행`)
                runValidate()
              }
            } catch (e) {
              console.error('[v39] 재검증 예외', e)
              remigLogs.value.push(`⚠ 재검증 오류 (${e.message}) — 전체 재검증 실행`)
              runValidate()
            }
          }, 1500)
        } else if (st === 'error' || st === 'aborted') {
          clearInterval(remigPollTimer)
          clearInterval(remigElapsedTimer); remigElapsedTimer = null  // v37
          remigRunning.value = false
          remigLogs.value.push(`❌ 오류: ${jd.error_message || '알 수 없는 오류'}`)
          // v49: activeRemigJobs 정리 + 실패 배지 마킹
          if (remigJobId.value && activeRemigJobs.value[remigJobId.value]) {
            const m = { ...activeRemigJobs.value }
            delete m[remigJobId.value]
            activeRemigJobs.value = m
          }
          const failTable = remigRow.value?.table
          if (failTable && !remigRow.value?._bulk) {
            const idx = results.value.findIndex(r => r.table === failTable)
            if (idx >= 0) {
              results.value[idx] = {
                ...results.value[idx],
                _updatedAt: Date.now(),
                _lastRemigMode: remigMode.value,
                _remigResult: {
                  status: 'failed',
                  at: Date.now(),
                  mode: remigMode.value,
                },
              }
            }
          }
        }
      } catch {}
    }, 2000)

  } catch(e) {
    remigRunning.value   = false
    remigJobStatus.value = 'error'
    clearInterval(remigElapsedTimer); remigElapsedTimer = null  // v37
    remigLogs.value.push(`❌ Job 생성 실패: ${e.message}`)
  }
}

async function reRun(table) {
  // 기존 호환성 유지 (직접 호출 시 모달 없이 truncate 재이관)
  const r = results.value.find(x => x.table === table)
  if (r) openRemigModal(r)
}
async function reRunAll() {
  const tbls = results.value.filter(r => !r.match)
  if (!tbls.length) return
  // 불일치 첫 번째 테이블로 모달 오픈 (일괄은 모달에서 확인 후 진행)
  openRemigModal({ table: tbls.map(r=>r.table).join(', '), _bulk: true, _rows: tbls })
}
// 체크섬 불일치 허용 처리 (검증 통과로 강제 표시)
function acceptChecksum(row) {
  row.checksum_match = true
  row.match = row.count_match !== false
  // summary 재계산
  if (summary.value) {
    const passed = results.value.filter(r => r.match).length
    const total  = results.value.length
    summary.value = {
      ...summary.value,
      passed, failed: total - passed,
      pass_rate: total > 0 ? Math.round(passed/total*100*10)/10 : 0
    }
  }
  app.notify(`[${row.table}] 체크섬 허용 처리됨`, 'info')
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

// v90.78e: reload 시 _sel 깜박임 제거를 위한 pending backup
//   runObjValidate 가 loadSrcObjects 호출 전에 이 맵에 백업
//   → watch(srcObjects) 가 새 _sel 만들 때 즉시 이 맵 참조 (default=true 안 거침)
const _pendingSelBackup = ref(null)

watch(srcObjects, data=>{
  if(!data){objGroupsRaw.value=[];return}
  // v90.78e: 우선순위 1 — pending backup (사용자가 reload 직전 가진 선택 상태)
  //          우선순위 2 — 기존 objGroupsRaw 의 _sel
  //          우선순위 3 — default true
  const prevSelMap = _pendingSelBackup.value || new Map()
  if (!_pendingSelBackup.value) {
    for (const grp of (objGroupsRaw.value || [])) {
      for (const obj of (grp.items || [])) {
        prevSelMap.set(`${grp.type}::${obj.name}`, obj._sel)
      }
    }
  }
  const _wrap = (type, items) => items.map(o => {
    const prev = prevSelMap.get(`${type}::${o.name}`)
    return reactive({ ...o, _sel: prev !== undefined ? prev : true })
  })
  objGroupsRaw.value=[
    {type:'PROCEDURE',label:'프로시저',icon:'⚙',items:_wrap('PROCEDURE', data.procedures||[])},
    {type:'FUNCTION', label:'함수',    icon:'ƒ', items:_wrap('FUNCTION',  data.functions||[])},
    {type:'TRIGGER',  label:'트리거',  icon:'⚡',items:_wrap('TRIGGER',   data.triggers||[])},
    {type:'VIEW',     label:'뷰',      icon:'◫', items:_wrap('VIEW',      data.views||[])},
  ]
  _pendingSelBackup.value = null   // 사용 후 클리어
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
  console.log('[DEBUG runObjValidate] start', {
    src: connector.source.host,
    tgt: connector.target.host,
    existingResults: objResults.value.length,
  })
  if (!connector.source.host) { app.notify('소스 DB를 먼저 연결하세요', 'warn'); return }
  if (!connector.target.host) { app.notify('타겟 DB를 연결해야 검증이 가능합니다', 'warn'); return }

  // v90.78e (2026-04-29): _sel 깜박임 제거
  //   호소: "2개만 체크했는데 검증 실행 시 16개 다 실행됨" (v90.78d 에서 fix 했지만 깜박임)
  //   원인: loadSrcObjects → watch 가 default true 로 만든 후 사후 복원 → 깜박임
  //   처방: reload 직전 _pendingSelBackup 에 백업 → watch 가 처음부터 그 값 사용 (깜박임 X)
  const userSelBackup = new Map()
  for (const grp of (objGroupsRaw.value || [])) {
    for (const obj of (grp.items || [])) {
      userSelBackup.set(`${grp.type}::${obj.name}`, obj._sel)
    }
  }
  _pendingSelBackup.value = userSelBackup
  console.log('[v90.78e] _sel backup before reload:', userSelBackup.size, 'items')
  
  console.log('[v90.76] reloading src objects for fresh validation')
  await loadSrcObjects(true)
  await new Promise(r => setTimeout(r, 200))

  // v10 #34-B 수정: 기존엔 objResults 가 이미 있으면 타겟 존재 재확인 없이 테스트만 돌렸음.
  //   → 1차로 전부 "타겟 없음" 으로 굳은 상태에서 다시 "검증 실행" 눌러도 재조회 안 됨.
  //   → 수정: 기존 결과가 있으면 status 만 초기화하고 CHECK_EXISTS 재조회.
  const hadExisting = objResults.value.length > 0
  if (hadExisting) {
    console.log('[DEBUG runObjValidate] existing results detected, refreshing target status')
    
    // v90.78 (2026-04-29): 재실행 시 _sel 기반 필터링
    //   호소: "전부 해제하고 프로시저 하나만 선택하고 검증 실행 했는데 전체가 다 실행"
    //   처방: objGroups[*]._sel → selectedSet → objResults filter
    const selectedSet = new Set()
    for (const grp of objGroups.value) {
      if (!selObjTypes.value.includes(grp.type)) continue
      for (const obj of grp.items) {
        if (obj._sel) selectedSet.add(`${grp.type}::${obj.name}`)
      }
    }
    
    if (selectedSet.size === 0) {
      app.notify('선택된 객체가 없습니다. 좌측에서 객체를 체크해주세요.', 'warn')
      return
    }
    
    let filteredResults = objResults.value.filter(r =>
      selectedSet.has(`${r.type}::${r.name}`)
    )
    
    // 신규 선택된 객체 추가 (이전 실행에 없던 것)
    const existingKeys = new Set(filteredResults.map(r => `${r.type}::${r.name}`))
    for (const grp of objGroups.value) {
      if (!selObjTypes.value.includes(grp.type)) continue
      for (const obj of grp.items) {
        const k = `${grp.type}::${obj.name}`
        if (obj._sel && !existingKeys.has(k)) {
          filteredResults.push({
            name: obj.name, type: grp.type, body: obj.body || '',
            schema_name: obj.schema_name || '',
            status: 'checking', _sel: false, deploying: false,
            matched_name: null, name_variant: null,
            testing: false, testStatus: null, testResult: null,
            srcTesting: false, srcTestStatus: null, srcTestResult: null,
          })
        }
      }
    }
    objResults.value = filteredResults
    console.log('[v90.78] filtered to selected:', filteredResults.length)
    
    // testStatus 는 유지 (이미 테스트한 건 결과 보존), status/matched_name 만 초기화
    // v56: _remigResult (재이관 배지) 도 초기화 — 수동 검증 기준 리셋. 테이블쪽 v49 와 동일 정책.
    for (const r of objResults.value) {
      r.status = 'checking'
      r.matched_name = null
      r.name_variant = null
      if (r._remigResult) r._remigResult = null   // v56
    }
  } else {
    // ── 최초 실행: (v90.76 에서 위에서 이미 loadSrcObjects 호출함) ──
    const selected = []
    for (const grp of objGroups.value) {
      if (!selObjTypes.value.includes(grp.type)) continue
      for (const obj of grp.items) {
        if (obj._sel) selected.push({
          name: obj.name, type: grp.type, body: obj.body || '',
          schema_name: obj.schema_name || '',   // v52: MSSQL 스키마 유지
        })
      }
    }
    console.log('[DEBUG runObjValidate] selected count:', selected.length,
                'selObjTypes:', selObjTypes.value)

    if (!selected.length) {
      app.notify('오브젝트가 없거나 선택되지 않았습니다. 목록을 먼저 로드하세요.', 'warn')
      await loadSrcObjects(true)
      return
    }

    objResults.value = selected.map(obj => ({
      ...obj, status: 'checking', _sel: false, deploying: false,
      matched_name: null, name_variant: null,
      testing: false, testStatus: null, testResult: null,
      srcTesting: false, srcTestStatus: null, srcTestResult: null
    }))
  }

  // 타겟 존재 여부 조회 (기존 항목 or 신규 항목 공통)
  objRunning.value = true
  await objRs.start()  // v43
  const tgt = connector.target
  let _objAborted = false
  for (const r of objResults.value) {
    // v43: 일시정지 대기 + 중단 플래그 체크
    await objRs.waitIfPaused()
    if (objRs.stopFlag.value) {
      _objAborted = true
      console.log('[v43 runObjValidate] stopped by user at', r.name)
      break
    }
    let exists = false
    let matchedName = null
    let nameVariant = null
    let diagnostics = null   // v50: 진단 정보
    try {
      const { data } = await axios.post('/api/v1/schema/execute-object', {
        db_type: tgt.dbType, host: tgt.host, port: tgt.port,
        username: tgt.username, password: tgt.password, database: tgt.database,
        obj_type: 'CHECK_EXISTS', obj_name: r.name, params: [],
        // v57: MSSQL 소스 스키마를 함께 전달 → 백엔드가 `{schema}_{name}`, `{schema}__{name}`
        // 후보를 제대로 만들 수 있음. 기존엔 `obj_schema` 가 빠져서 후보 1개만 생성되어
        // `settlement_sp_reverse_trx` 같은 변형된 이름을 못 찾던 버그.
        obj_schema: r.schema_name || '',
      })
      exists = data.success && (data.exists || data.rows?.length > 0)
      matchedName = data.matched_name || null
      nameVariant = data.name_variant || null
      diagnostics = data.diagnostics || null

      // v57: similar_names 에 단 1개만 있으면 — 즉 이름 prefix/suffix 만 다른 변형이
      // 타겟에 확실히 존재하면 — 그 이름을 실제 매칭으로 인정.
      // 예: bare='sp_reverse_trx' similar=['settlement_sp_reverse_trx'] → 존재 인정.
      // 이렇게 해야 사용자가 "타겟 없음" 으로 오진단받고 AI 재변환을 다시 돌리는 헛수고를 없앰.
      if (!exists && diagnostics?.similar_names?.length === 1) {
        exists = true
        matchedName = diagnostics.similar_names[0]
        nameVariant = diagnostics.similar_names[0]
        console.info(
          `[CHECK_EXISTS] ✓ ${r.name} (similar_names 자동 매칭 → '${matchedName}')`
        )
      } else if (!exists && diagnostics) {
        // v50: 진단 로그 — "타겟 없음" 오진단 시 콘솔에서 즉시 원인 파악 가능
        console.warn(
          `[CHECK_EXISTS] ✗ NOT FOUND: ${r.name}`,
          `\n  타겟 DB: ${diagnostics.db}`,
          `\n  DB 내 전체 오브젝트 수: ${diagnostics.total_in_db}`,
          `\n  유사한 이름: ${JSON.stringify(diagnostics.similar_names || [])}`,
          `\n  전체 샘플 (상위 20): ${JSON.stringify(diagnostics.sample_names || [])}`,
          `\n  시도한 후보: ${JSON.stringify(data.candidates_tried || [])}`,
        )
      } else if (exists && diagnostics?.match_type === 'case_insensitive') {
        console.info(
          `[CHECK_EXISTS] ✓ ${r.name} (대소문자 폴백: 요청='${diagnostics.requested}' → 실제='${diagnostics.actual}')`
        )
      }
    } catch(e) {
      console.error('[DEBUG CHECK_EXISTS 오류]', r.name, e.response?.data || e.message)
    }
    r.status = exists ? 'ok' : 'missing'
    r.matched_name = matchedName
    r.name_variant = nameVariant
    r.diagnostics = diagnostics   // v50: 진단 정보 행에 저장 — UI 툴팁/펼침용
  }
  objRunning.value = false
  objRs.finish()  // v43

  if (_objAborted) {
    const checked = objResults.value.filter(r => r.status !== 'checking').length
    app.notify(`오브젝트 검증 중단됨 — ${checked}/${objResults.value.length}개 부분 결과 보존`, 'warn')
    return
  }

  const miss = objResults.value.filter(r => r.status === 'missing').length
  app.notify(`오브젝트 검증 완료 — 총 ${objResults.value.length}개, 미이관 ${miss}개`, miss ? 'warn' : 'success')

  // 목록 로드 직후 자동으로 전체 테스트 실행
  await runAllObjTest()
}

// v50: 진단 정보 표시 — "타겟 없음"인데 실제로 존재하는 경우 원인 분석
function showObjDiagnostics(r) {
  const d = r.diagnostics || {}
  const lines = []
  lines.push(`🔍 오브젝트 진단 — ${r.name} (${r.type})`)
  lines.push('')
  lines.push(`타겟 DB: ${d.db || '—'}`)
  lines.push(`DB 내 전체 오브젝트 수: ${d.total_in_db ?? '—'}개`)
  lines.push(`매칭 결과: ${d.match_type || '—'}`)
  lines.push('')
  if (d.similar_names?.length) {
    lines.push(`⚠ 유사한 이름 발견 (이름이 약간 달라서 매칭 실패했을 가능성):`)
    d.similar_names.forEach(n => lines.push(`   · ${n}`))
    lines.push('')
  }
  if (d.sample_names?.length) {
    lines.push(`타겟 DB 내 오브젝트 목록 (상위 ${d.sample_names.length}개):`)
    d.sample_names.forEach(n => lines.push(`   · ${n}`))
    if (d.total_in_db > d.sample_names.length) {
      lines.push(`   ... (${d.total_in_db - d.sample_names.length}개 더 있음)`)
    }
    lines.push('')
  }
  lines.push(`시도한 후보 이름:`)
  const cands = r.diagnostics?.candidates_tried || []
  if (cands.length) {
    cands.forEach(c => lines.push(`   · ${c}`))
  } else {
    lines.push(`   (응답에 없음)`)
  }
  lines.push('')
  lines.push(`💡 만약 위 "유사한 이름" 또는 "샘플" 에 찾고 있던 오브젝트가 있다면,`)
  lines.push(`   이름 매칭 로직에 추가 규칙이 필요합니다. 이 내용을 복사해서 제공 부탁드립니다.`)
  // 일단 alert — 추후 모달로 승격 가능
  alert(lines.join('\n'))
}

// v64: [DEPRECATED] 기존 단순 배포 — MSSQL 원본 DDL 을 그대로 MySQL 에 꽂는 방식.
// @param, NVARCHAR, DATETIME2, schema.table 등 MSSQL 전용 구문이 그대로 남아
// 대부분 실패. 더 이상 기본 경로에서 사용하지 않음. runSingleObjAiRemig 의
// AI 변환 경로 (runBulkAiDeploy) 로 일원화됨. 개별 오브젝트에 수동 배포 필요 시
// 디버그 용도로만 남겨둠.
async function deployOne(r){
  r.deploying=true;const tgt=connector.target
  try{const{data}=await axios.post('/api/v1/schema/execute-object',{db_type:tgt.dbType,host:tgt.host,port:tgt.port,username:tgt.username,password:tgt.password,database:tgt.database,obj_type:'DDL_CREATE',obj_sub_type:r.type,obj_name:r.name,statements:[r.body],ddl:r.body,params:[]});r.status=data.success?'ok':'error';app.notify(data.success?`${r.name} 배포 완료`:`배포 실패: ${data.error||'오류'}`,data.success?'success':'error')}
  catch(e){r.status='error';app.notify('배포 실패: '+(e.response?.data?.detail||e.message),'error')}
  finally{r.deploying=false}
}

// v64: 미이관 오브젝트 일괄 AI 배포 — 기존 deployMissing 교체.
// 변경 이유: 단순 배포(deployOne) 는 MSSQL 원본 DDL 그대로 사용해서 대부분 실패.
//   로그 증거: Unknown database 'ref', Unknown database 'settlement', near '@param' 등.
// 새 흐름: runSingleObjAiRemig 와 동일한 AI 변환 파이프라인을 일괄로 태움.
//   1. 미이관 목록 수집 (status === 'missing')
//   2. 기존 재이관 팝업(openRemigrateModal + startRemigrate) 재사용
//      → v55 의 3회 재시도, v58 KB 학습, v54 타임아웃, v56 배지 모두 자동 적용
//   3. 사용자는 진행 상황을 팝업에서 확인, 끝나면 수동 닫기
async function deployMissing() {
  // v71: 방식 A (순차 실행) — 검증 진행 중이면 진행 불가.
  //   v70 은 confirm 으로 선택권 줬지만, 순차 원칙에 맞게 단순 거부.
  //   검증 버튼 자체도 재이관 중엔 막혀 있으므로 양방향 완전 배타.
  if (objTesting.value) {
    app.notify('오브젝트 검증이 진행 중입니다. 완료된 후 다시 시도해 주세요.', 'warn')
    return
  }
  if (remigrateLoading.value) {
    app.notify('이전 재이관 작업이 아직 진행 중입니다. 완료 후 다시 시도해 주세요.', 'warn')
    return
  }

  const missing = objResults.value.filter(r => r.status === 'missing')
  if (!missing.length) {
    app.notify('미이관 오브젝트가 없습니다', 'info')
    return
  }

  // 사용자 확인 — 21건 AI 호출은 시간 걸리고 API 비용도 나감
  const ok = confirm(
    `미이관 오브젝트 ${missing.length}개를 AI 변환 + 배포합니다.\n\n` +
    `· 각 오브젝트마다 소스 DDL 읽기 → Claude AI 변환 → 타겟 CREATE\n` +
    `· 예상 소요: 약 ${Math.ceil(missing.length * 15 / 60)}분 (1건당 약 15초)\n` +
    `· 중간에 실패한 건은 3회 재시도 후 건너뜀\n\n` +
    `계속하시겠습니까?`
  )
  if (!ok) return

  // v64: startRemigrate 는 기본 remigrateOnlyFail=true 라서 testStatus==='fail' 만 남김.
  //   미이관 오브젝트는 testStatus 가 없는(missing) 상태라 그대로 두면 타겟이 0건 됨.
  //   따라서 호출 전에 false 로 세팅해서 전체 targets 을 태우게 함.
  remigrateOnlyFail.value = false

  // 기존 재이관 팝업 흐름 그대로 태움 — 명시적 인수이므로 필터링 안 됨 (v60 로직 참조)
  openRemigrateModal(missing)
  await nextTick()
  await startRemigrate()
}

// ── 오브젝트 정렬 ──────────────────────────────────────────
const objSortCol = ref('name')
const objSortDir = ref('asc')
// v74: 정렬 모드 — 'user'(컬럼 헤더 클릭 기반) / 'recent'(최근 검증 시간 우선)
//   기본값은 'user' — 이름순.
//   '기본 정렬 (최근 우선)' 버튼 누르면 'recent' 로 전환 + 컬럼 정렬 무시.
//   다시 컬럼 헤더 클릭하면 'user' 로 복귀.
const objSortMode = ref('user')
const objDetailRows = reactive({})

function setObjSort(col) {
  // v74: 사용자가 컬럼 헤더 클릭하면 user 모드로 복귀 (recent 모드였어도)
  objSortMode.value = 'user'
  if (objSortCol.value===col) objSortDir.value=objSortDir.value==='asc'?'desc':'asc'
  else { objSortCol.value=col; objSortDir.value='asc' }
}
function objSortIco(col) {
  // v74: recent 모드에선 컬럼 아이콘 표시 안 함
  if (objSortMode.value === 'recent') return ''
  if (objSortCol.value!==col) return '↕'
  return objSortDir.value==='asc' ? '↑' : '↓'
}
// v74: '기본 정렬 (최근 검증 시간 우선)' 활성화 — 전체 열기 버튼 옆에 붙는 액션
function setObjSortRecent() {
  objSortMode.value = 'recent'
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
      // ★ 캐시에서 불러올 때도 dummy_value 재계산 (이전 잘못된 형식 덮어쓰기)
      r._params = saved.params.map(p => {
        const dv = _makeDummyValue(p.data_type, p.name, p.max_length ?? data.params?.find(d=>d.name===p.name)?.max_length)
        return {
          ...p,
          dummy_value: dv,
          // v79: 소스/타겟 별도 값 (하위호환 위해 dummy_value 도 유지)
          //   캐시에 src/tgt 저장되어 있으면 그것 우선, 없으면 dummy_value 로 초기화
          src_value: p.src_value ?? dv,
          tgt_value: p.tgt_value ?? dv,
        }
      })
      r._hintKey = hintKey
      r._fromHint = true
      app.notify(`힌트에서 파라미터 ${r._params.length}개 불러옴`, 'success')
      return
    }

    r._params = (data.params || []).map(p => {
      const dv = _makeDummyValue(p.data_type, p.name, p.max_length)
      return {
        ...p,
        dummy_value: dv,
        // v79: 소스/타겟 각자 값으로 시작 (처음엔 같은 값)
        src_value: dv,
        tgt_value: dv,
      }
    })
    // max_length 정보도 힌트 캐시에 반영 (다음 로드 시 사용)
    if (_hintsCache.value && _hintsCache.value[hintKey]) {
      _hintsCache.value[hintKey].params = r._params.map(p => ({ ...p }))
    }
    r._hintKey  = hintKey
    r._fromHint = false
    if (!r._params.length) app.notify('파라미터가 없는 오브젝트입니다', 'info')
    else app.notify(`파라미터 ${r._params.length}개 조회됨`, 'success')

    // v82: 파라미터 조회 직후 DB 추천값 자동 적용 (기존 v80 의 조용한 실패 방지)
    //   본부장 요청: "네가 추천값을 세팅해 둘꺼지?"
    //   기존 v80 에선 silent 실패 가능성 있었음. v82 에선:
    //     - 진행 로그 남김 (디버그 가능)
    //     - 실패해도 상태 플래그로 UI 에 표시 가능
    if (r._params.length) {
      r._autoSuggested = false
      console.log(`[v82] 자동 추천값 조회 시작: ${r.name} (파라미터 ${r._params.length}개)`)
      try {
        await loadSuggestionsForRow(r, true)   // silent = true
        r._autoSuggested = true
        console.log(`[v82] 자동 추천값 조회 완료: ${r.name}`)
      } catch(e) {
        console.warn(`[v82] 자동 추천값 로드 실패: ${r.name} -`, e.message)
        r._autoSuggested = false
      }
    }
  } catch(e) {
    app.notify('파라미터 조회 실패: ' + e.message, 'error')
  } finally {
    r._paramLoading = false
  }
}

// ── DB 추천값 로드 ───────────────────────────────────────────
//   v80: silent=true 면 알림 억제 (파라미터 조회 직후 자동 호출용)
//   v85: 소스와 타겟 DB 각각에서 추천값 조회 (핵심 수정)
//     - 이전: 소스 DB 만 조회 → 소스엔 존재하지만 타겟엔 없는 값일 수 있음 (contract_id=1 등)
//     - v85: 소스는 src_value, 타겟은 tgt_value 로 각자 DB 에서 실제 존재하는 값 사용
async function loadSuggestionsForRow(r, silent = false) {
  if (!r._params?.length) return
  r._suggestLoading = true
  try {
    // ① 소스 DB 추천값 조회
    const srcP = axios.post('/api/v1/schema/object-param-suggestions', {
      db_type:  connector.source.dbType,
      host:     connector.source.host,
      port:     connector.source.port,
      username: connector.source.username,
      password: connector.source.password,
      database: connector.source.database,
      params:   r._params,
    }, { timeout: 15000 })

    // ② 타겟 DB 추천값 조회 (병렬)
    const tgtP = axios.post('/api/v1/schema/object-param-suggestions', {
      db_type:  connector.target.dbType,
      host:     connector.target.host,
      port:     connector.target.port,
      username: connector.target.username,
      password: connector.target.password,
      database: connector.target.database,
      params:   r._params,
    }, { timeout: 15000 })

    const [srcRes, tgtResSettled] = await Promise.all([
      srcP,
      tgtP.catch(e => ({ _err: e }))   // 타겟 실패해도 소스만으로 진행
    ])

    const srcData = srcRes.data
    const tgtData = tgtResSettled?._err ? null : tgtResSettled.data

    if (!srcData.params?.length) {
      if (!silent) app.notify('추천값이 없습니다', 'info')
      return
    }

    // 소스/타겟 각각의 추천값으로 src_value / tgt_value 각자 세팅
    const srcByName = Object.fromEntries(srcData.params.map(p => [p.name, p]))
    const tgtByName = tgtData?.params
      ? Object.fromEntries(tgtData.params.map(p => [p.name, p]))
      : {}

    r._params = r._params.map(p => {
      const srcSuggest = srcByName[p.name]
      const tgtSuggest = tgtByName[p.name]
      return {
        ...p,
        // 소스 추천값 → src_value 로 (없으면 기존 유지)
        src_value: srcSuggest?.dummy_value ?? p.src_value ?? p.dummy_value,
        // 타겟 추천값 → tgt_value 로 (없으면 소스 추천값이라도 사용, 그것도 없으면 기존)
        tgt_value: tgtSuggest?.dummy_value ?? srcSuggest?.dummy_value ?? p.tgt_value ?? p.dummy_value,
        // suggestion_source 는 소스 기준 유지 (UI 아이콘용)
        suggestion_source: srcSuggest?.suggestion_source ?? p.suggestion_source,
      }
    })

    const srcFromDb = srcData.params.filter(p => p.suggestion_source?.includes('.')).length
    const tgtFromDb = tgtData?.params?.filter(p => p.suggestion_source?.includes('.')).length ?? 0

    if (!silent) {
      app.notify(
        `추천값 적용 — 소스 ${srcFromDb}개 📊 · 타겟 ${tgtFromDb}개 📊`,
        'success'
      )
    } else if (srcFromDb > 0 || tgtFromDb > 0) {
      app.notify(`자동 추천값 — 소스 ${srcFromDb} / 타겟 ${tgtFromDb} 📊`, 'info')
    }
  } catch(e) {
    if (!silent) app.notify('추천값 조회 실패: ' + e.message, 'error')
    console.warn('[v85] 추천값 조회 예외:', e.message)
  } finally {
    r._suggestLoading = false
  }
}

// ── 더미값 초기화 ─────────────────────────────────────────────
function resetDummyParams(r) {
  if (!r._params) return
  // v79: src_value, tgt_value 모두 리셋 (하위호환 위해 dummy_value 도)
  r._params.forEach(p => {
    const dv = _makeDummyValue(p.data_type, p.name, p.max_length)
    p.dummy_value = dv
    p.src_value = dv
    p.tgt_value = dv
  })
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
// v79: side = 'src' | 'tgt' | 'both' (default 'both')
//   'src'  : 소스만 실행 (r._params 의 src_value 사용)
//   'tgt'  : 타겟만 실행 (r._params 의 tgt_value 사용)
//   'both' : 양쪽 실행 (각자 값으로)
async function runObjTestWithParams(r, side = 'both') {
  if (!r._params) return

  // 파라미터 값 추출 함수 — side 에 따라 src_value / tgt_value / dummy_value 선택
  //   하위호환: src_value 없으면 dummy_value 사용
  const getValues = (useSide) => r._params
    .filter(p => !p.is_output)
    .map(p => {
      if (useSide === 'src') return p.src_value ?? p.dummy_value
      if (useSide === 'tgt') return p.tgt_value ?? p.dummy_value
      return p.dummy_value
    })

  const srcParams = getValues('src')
  const tgtParams = getValues('tgt')

  // 상태 초기화 — side 에 해당하는 쪽만
  if (side === 'src' || side === 'both') {
    r.srcTesting = true
    r.srcTestStatus = null
    r.srcTestResult = null
  }
  if (side === 'tgt' || side === 'both') {
    r.testing = true
    r.testStatus = null
    r.testResult = null
  }

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
    if (side === 'src' || side === 'both') {
      const t0 = Date.now()
      const { data: sd } = await axios.post('/api/v1/schema/execute-object', {
        ...baseConnSrc, obj_type: r.type, obj_name: r.name, params: srcParams,
        obj_schema: r.schema_name || ''
      }, { timeout: 15000 })
      const se = Date.now() - t0
      r.srcTestStatus = sd.success ? 'pass' : _isBusinessError(sd.error) ? 'review' : 'fail'
      r.srcTestResult = {
        method: `${r.type} 실행 (소스, 입력값 ${srcParams.length}개)`,
        message: sd.success ? `정상 실행 (${(sd.rows||[]).length}행)` : (sd.error||''),
        error: (!sd.success && !_isBusinessError(sd.error)) ? sd.error : undefined,
        note: _isBusinessError(sd.error) ? sd.error : undefined,
        rows: sd.rows, elapsed_ms: se,
        params_used: r._params.filter(p=>!p.is_output)
          .map(p=>`${p.name}=${p.src_value ?? p.dummy_value}`)
      }
      r.srcTesting = false
    }

    // 타겟 실행
    if (side === 'tgt' || side === 'both') {
      const t1 = Date.now()
      // v90.70: 타겟 호출 시 name_variant (변환된 실제 이름) 우선 사용
      const _tgtName = r.name_variant || r.name
      const { data: td } = await axios.post('/api/v1/schema/execute-object', {
        ...baseConnTgt, obj_type: r.type, obj_name: _tgtName, params: tgtParams,
        obj_schema: r.schema_name || ''
      }, { timeout: 15000 })
      const te = Date.now() - t1
      r.testStatus = td.success ? 'pass' : _isBusinessError(td.error) ? 'review' : 'fail'
      r.testResult = {
        method: `${r.type} 실행 (타겟, 입력값 ${tgtParams.length}개)`,
        message: td.success ? `정상 실행 (${(td.rows||[]).length}행)` : (td.error||''),
        error: (!td.success && !_isBusinessError(td.error)) ? td.error : undefined,
        note: _isBusinessError(td.error) ? td.error : undefined,
        rows: td.rows, elapsed_ms: te,
        params_used: r._params.filter(p=>!p.is_output)
          .map(p=>`${p.name}=${p.tgt_value ?? p.dummy_value}`)
      }
      r.testing = false
    }

    // 성공 시 힌트 자동 저장 — 양쪽 다 pass 일 때만
    if (r.srcTestStatus === 'pass' && r.testStatus === 'pass' && r._hintKey) {
      await saveParamHint(r)
    }
    // v74: 최근 검증 시간 기록
    r._updatedAt = Date.now()
  } catch(e) {
    // v79: side 에 해당하는 쪽만 fail 로 처리
    if (side === 'src' || side === 'both') {
      r.srcTestStatus = r.srcTestStatus || 'fail'
      r.srcTesting = false
    }
    if (side === 'tgt' || side === 'both') {
      r.testStatus = r.testStatus || 'fail'
      r.testing = false
    }
    r._updatedAt = Date.now()   // v74: 실패도 최근 시도 시간 기록
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

  // v74: recent 모드 — 최근 검증(_updatedAt) 시간 내림차순.
  //   진행 중(busy) 행 최상단 고정은 유지 (v65).
  //   검증 안 한 항목은 맨 아래 (자연스러운 순서).
  if (objSortMode.value === 'recent') {
    list.sort((a, b) => {
      const aBusy = a.testing || a.srcTesting ? 0 : 1
      const bBusy = b.testing || b.srcTesting ? 0 : 1
      if (aBusy !== bBusy) return aBusy - bBusy
      return (b._updatedAt || 0) - (a._updatedAt || 0)
    })
    return list
  }

  const col = objSortCol.value, dir = objSortDir.value==='asc' ? 1 : -1

  list.sort((a,b) => {
    // v65: "진행 중" 인 행은 언제나 최상단 고정.
    //   본부장 요청: 검증 중 리스트가 왔다갔다 해서 어지러움 → 진행 행을 top 으로 올려 고정.
    //   테이블 검증 v42 와 동일한 UX.
    //   우선순위: (1) 현재 실행 중(testing/srcTesting) → 항상 맨 위
    //           (2) 그 다음은 기존 컬럼 정렬
    const aBusy = a.testing || a.srcTesting ? 0 : 1
    const bBusy = b.testing || b.srcTesting ? 0 : 1
    if (aBusy !== bBusy) return aBusy - bBusy   // busy 먼저

    if (col === 'testStatus' || col === 'srcTestStatus') {
      // fail→review→pass→없음 순
      const rank = s => s==='fail'?0:s==='review'?1:s==='pass'?2:3
      return (rank(a[col]) - rank(b[col])) * dir
    }
    // v77: 이관 상태(status) 정렬 — 문제 있는 것 먼저 (missing→error→ok)
    if (col === 'status') {
      const rank = s => s==='missing'?0:s==='error'?1:s==='ok'?2:3
      const r = (rank(a.status) - rank(b.status)) * dir
      if (r !== 0) return r
      // 2차: 이름순
      const na = (a.name||'').toLowerCase(), nb = (b.name||'').toLowerCase()
      return na<nb?-1:(na>nb?1:0)
    }
    // v69: 유형(type) 컬럼 정렬 — 1차 타입, 2차 이름 (같은 타입끼리 모이되 그 안은 가나다순)
    if (col === 'type') {
      const ta = (a.type||'').toLowerCase(), tb = (b.type||'').toLowerCase()
      if (ta !== tb) return (ta<tb?-1:1) * dir
      // 2차 정렬: 이름 오름차순 고정 (방향 영향 안 받음)
      const na = (a.name||'').toLowerCase(), nb = (b.name||'').toLowerCase()
      return na<nb?-1:(na>nb?1:0)
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
  // MySQL 비즈니스 오류 (45000, 1644)
  //   v85: MySQL SIGNAL SQLSTATE '45000' 로 던져도 Python connector 는 
  //        (1644, '메시지') 튜플로 반환. 에러 문자열에 '45000' 안 포함되고 
  //        '1644' 만 포함되는 경우가 많음 → 1644 명시적 추가.
  if (e.includes('45000') || e.includes('1644')) return true
  // 한글 비즈니스 오류 패턴 (프로시저가 한글로 SIGNAL 던진 경우)
  //   v85: capital_midsize 의 프로시저들이 한글 에러 메시지 사용
  if (e.includes('찾을 수 없습니다') || e.includes('찾을수없습니다') ||
      e.includes('없습니다') || e.includes('존재하지') ||
      e.includes('유효하지') || e.includes('잘못된')) return true
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
// v90.68 (2026-04-28): targetMaxLength 추가 — 소스/타겟 중 더 짧은 길이 기준으로 입력값 만들기
//   본부장님 환경 SP_STATRECORD 의 1406 오류 — 소스 VARCHAR(8) 인데 타겟 변환이 짧으면
//   '20240101' 입력해도 1406. 타겟 길이를 추가로 받아서 안전한 입력값 생성.
function _makeDummyValue(dataType, paramName, maxLength, targetMaxLength) {
  console.log('[v90.79 CALL]', {dataType, paramName, maxLength, targetMaxLength})
  const t = (dataType || '').toLowerCase()
  const n = (paramName || '').toLowerCase().replace(/^[@p_]+/, '')
  const ml = Number(maxLength) || 0  // max_length (소스 백엔드에서 전달)
  const tml = Number(targetMaxLength) || 0  // v90.68: 타겟 max_length
  // 더 짧은 길이를 기준 (안전 — 둘 다 통과해야 함)
  const safe_ml = (tml > 0 && ml > 0) ? Math.min(ml, tml) : (ml || tml || 0)

  // ── 날짜 형식: max_length로 정확히 결정 ──────────────────────
  // VARCHAR(8) → '20240101' (8자리 숫자형)
  // VARCHAR(10) 이상 또는 DATE 타입 → '2024-01-01'
  const isDateParam = n.match(/dt$|date$|_dt|_date|sdate|edate|_ymd|start_date|end_date|from_date|to_date/)
  const isDateType  = t.match(/^date$|^datetime/)

  if (isDateParam || isDateType) {
    // ════════════════════════════════════════════════════════════
    // v90.79 (2026-04-29): 본부장님 호소 — 날짜 dummy 가 size 안 맞음
    //   원칙: object 의 datatype + size 를 읽어 그에 맞는 값 자동 입력
    //   1. char/varchar 타입은 길이 우선 검사 (size 누락이라도 8자 default)
    //   2. DATE/DATETIME 타입은 ISO 형식
    //   3. 날짜 파라미터인데 size 불명이면 → 가장 안전한 8자 (YYYYMMDD)
    // ════════════════════════════════════════════════════════════
    const isCharType = t.match(/char|text|string|nvar|nchar/)
    if (isCharType) {
      // VARCHAR/CHAR: 길이가 명시된 경우 그에 맞춤
      if (safe_ml > 0) {
        if (safe_ml >= 19) return '2024-01-01 00:00:00'  // DATETIME 문자열
        if (safe_ml >= 10) return '2024-01-01'           // ISO 날짜
        if (safe_ml >= 8)  return '20240101'             // YYYYMMDD
        if (safe_ml >= 6)  return '202401'               // YYYYMM
        if (safe_ml >= 4)  return '2024'                 // YYYY
        return '20240101'.substring(0, safe_ml)
      }
      // size 불명 + char 타입 + 날짜 파라미터 → 가장 안전한 8자
      return '20240101'
    }
    // DATE / DATETIME 타입 (사이즈 무관)
    if (t.match(/^datetime/)) return '2024-01-01 00:00:00'
    return '2024-01-01'
  }

  // 파라미터명으로 의미있는 더미값 결정
  if (n.match(/term|month|period|cnt|count|size|num|seq|page/)) return 12
  if (n.match(/day|days/))                                        return 30
  if (n.match(/rate|ratio|pct|percent/))                          return 5.00
  if (n.match(/amt|amount|price|bal|balance|principal/))          return 1000000
  if (n.match(/income|salary/))                                   return 60000000
  if (n.match(/action|tp|type|cd|code|status|gb|flag/))          return t.includes('char') ? 'A' : 1
  if (n.match(/ym$|year_month/))                                  return '202401'
  if (n.match(/page_no|page_num/))                                return 1
  if (n.match(/page_size|per_page/))                              return 20

  // 타입 기반 기본값
  if (t.match(/int|tinyint|smallint|bigint|mediumint/))           return 1
  if (t.match(/float|double|decimal|numeric|real|money|smallmoney/)) return 1.0
  if (t.match(/bit|bool/))                                        return 1
  if (t.match(/^datetime/))                                       return '2024-01-01 00:00:00'
  if (t.match(/date|time/))                                       return '2024-01-01'
  if (t.match(/char|text|string|clob|nvar|nchar/)) {
    // v90.79: 문자열도 정확히 size 맞춤
    if (safe_ml > 0) {
      if (safe_ml >= 5) return 'A'.repeat(Math.min(safe_ml, 10))  // 최대 10자
      return 'A'.repeat(safe_ml)
    }
    return 'A'
  }
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
      dummy_value: _makeDummyValue(p.data_type, p.name, p.max_length)
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
// v84 A: side ('src'/'tgt') + r (오브젝트 행) 인수 추가
//   - r._params 이미 있으면 src_value/tgt_value 재사용 (본부장 요청: 자동 루프도 타겟 값 사용)
//   - 없으면 기존대로 _getParams 로 소스에서 조회
async function _execObjOnDB(dbConn, type, name, side = 'src', r = null) {
  const t  = type?.toUpperCase()
  const t0 = Date.now()
  const baseConn = {
    db_type: dbConn.dbType, host: dbConn.host, port: dbConn.port,
    username: dbConn.username, password: dbConn.password, database: dbConn.database,
  }

  // v84 A: 파라미터 값 선택 함수 — side 에 따라 src/tgt 구분
  const pickValue = (p) => {
    if (side === 'tgt' && p.tgt_value !== undefined && p.tgt_value !== null) return p.tgt_value
    if (side === 'src' && p.src_value !== undefined && p.src_value !== null) return p.src_value
    return p.dummy_value  // fallback (하위호환)
  }

  try {
    // v90.70: 타겟 호출 시 name_variant (변환된 실제 이름) 우선 사용
    const _ckName = (side === 'tgt' && r && r.name_variant) ? r.name_variant : name

    // TRIGGER: 존재/활성화 확인 (실행 불가)
    if (t === 'TRIGGER') {
      const { data } = await axios.post('/api/v1/schema/execute-object', {
        ...baseConn, obj_type: 'CHECK_EXISTS', obj_name: _ckName, params: []
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
      // v60: 10 → 30초. 대용량 뷰(JOIN 다수, 집계 등)는 정상 응답에도 10초 넘을 수 있음.
      // 서버 로그에서 뷰 DDL 조회가 수 초 걸리는 사례 확인됨.
      try {
        const { data } = await axios.post('/api/v1/schema/execute-object', {
          ...baseConn, obj_type: 'VIEW', obj_name: _ckName, params: []
        }, { timeout: 30000 })
        const elapsed = Date.now() - t0
        if (data.success) {
          return { status: 'pass', result: { method: 'SELECT * FROM view', message: `정상 실행 (${(data.rows||[]).length}행)`, rows: data.rows, elapsed_ms: elapsed } }
        }
        return { status: 'fail', result: { method: 'SELECT * FROM view', message: '뷰 실행 오류', error: data.error, elapsed_ms: elapsed } }
      } catch (e) {
        const elapsed = Date.now() - t0
        if (e.code === 'ECONNABORTED') {
          // v60: 타임아웃은 "실패" 가 아니라 별도 상태로 — review (검토필요)
          return { status: 'review', result: {
            method: 'SELECT * FROM view',
            message: `시간 초과 (${Math.round(elapsed/1000)}초)`,
            error: `테스트가 30초 내 완료되지 않았습니다. 대용량 뷰라 정상 동작일 가능성이 있습니다. 수동 테스트 필요.`,
            elapsed_ms: elapsed,
            is_timeout: true,
          } }
        }
        throw e
      }
    }

    // PROCEDURE / FUNCTION: 파라미터 조회 후 더미값으로 실행
    // v84 A: r._params 가 이미 있으면 재사용 (사용자가 입력/저장한 값 우선)
    //         없으면 기존대로 _getParams 로 소스에서 조회
    // v90.70: _getParams 도 타겟 호출 시 name_variant 사용 (정확한 이름으로 파라미터 조회)
    let params, fromHint, hintKey
    if (r && r._params?.length) {
      params   = r._params
      fromHint = true   // 이미 힌트/사용자값 있음
      hintKey  = r._hintKey
    } else {
      // v90.70: 타겟이면 변환된 이름으로 파라미터 조회 (소스 측엔 name 그대로)
      const _paramName = (side === 'tgt' && r && r.name_variant) ? r.name_variant : name
      const result = await _getParams(dbConn, _paramName)
      params   = result.params
      fromHint = result.fromHint
      hintKey  = result.hintKey
    }
    // v84 A: side 에 따라 src_value / tgt_value 선택 (없으면 dummy_value fallback)
    const dummyValues = params.filter(p => !p.is_output).map(pickValue)
    
    // ════════════════════════════════════════════════════════════════════
    // v90.70 (2026-04-28): 타겟 호출 시 name_variant (변환된 실제 이름) 우선 사용
    //   본부장님 호소: "sp_Softphone_UpdateRecord(dbo_sp_Softphone_UpdateRecord)"
    //                   1305 'PROCEDURE testdb.sp_Softphone_UpdateRecord does not exist'
    //   원인: CHECK_EXISTS 가 매치한 실제 이름은 r.name_variant 에 저장되는데,
    //         _execObjOnDB 의 PROCEDURE 실행 시 r.name (소스 원본) 만 사용 →
    //         타겟 DB 에 없는 이름으로 호출 → 1305 'does not exist' 오류
    //   처방: side==='tgt' 일 때 r.name_variant 가 있으면 그것 우선
    //   주: 위 _ckName 와 같은 로직 — PROCEDURE/FUNCTION 도 동일 적용
    // ════════════════════════════════════════════════════════════════════

    // v60: 12 → 60초. 배치성 PROC (sp_daily_batch, sp_reverse_trx 등) 은
    //   실제로 수십 초 걸리는 게 정상. 12초에 끊어버리면 정상 동작도 실패로 잡힘.
    //   타임아웃이 발생해도 '실패' 대신 'review(검토필요)' 로 분류.
    let data
    try {
      const resp = await axios.post('/api/v1/schema/execute-object', {
        ...baseConn, obj_type: t, obj_name: _ckName, params: dummyValues
      }, { timeout: 60000 })
      data = resp.data
    } catch (e) {
      const elapsed = Date.now() - t0
      if (e.code === 'ECONNABORTED') {
        return { status: 'review', result: {
          method: `${t} with dummy params`,
          message: `시간 초과 (${Math.round(elapsed/1000)}초)`,
          error: `테스트가 60초 내 완료되지 않았습니다. 배치성 프로시저라 정상 동작일 수 있습니다. 수동 확인 필요.`,
          elapsed_ms: elapsed,
          is_timeout: true,
        } }
      }
      throw e
    }
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

  // v84 A: PROC/FUNC 이고 아직 파라미터 로드 안 됐으면 자동 로드 (타겟값 자동 사용 전제)
  //   본부장 요청: "자동 루프가 tgt_value 사용하도록"
  //   pre-load 해두면 _execObjOnDB 가 r._params 재사용해서 src_value/tgt_value 각각 사용
  if ((t === 'PROCEDURE' || t === 'FUNCTION') && !r._params?.length && !r._paramLoading) {
    try {
      console.log(`[v84] 자동 루프 - 파라미터 사전 로드: ${r.name}`)
      await loadParamsForRow(r)   // 내부에서 자동 추천값까지 호출됨 (v80)
    } catch(e) {
      console.warn(`[v84] 자동 루프 - 파라미터 로드 실패: ${r.name}`, e.message)
      // 실패해도 계속 진행 (기존 _getParams fallback 동작)
    }
  }

  try {
    // ① 소스 실행
    //   v78: 15초 → 30초 상향. Docker MSSQL 이 재이관 부하 후 warm-up 느려짐.
    //        PROC/TRIG 실제 실행이 타임아웃 먹는 sp_merge_customer 사례 발생.
    //   v84 A: side='src' + r 전달 → r._params 의 src_value 사용
    //   v86: 30초 → 60초. 내부 axios 도 60초라 외부가 먼저 끊어버리던 버그 수정.
    r.srcTesting = true
    const srcRes = await _execWithTimeout(() => _execObjOnDB(connector.source, r.type, r.name, 'src', r), 60000)
    r.srcTestStatus = srcRes.status; r.srcTestResult = srcRes.result
    r.srcTesting = false

    if (_isConnError(srcRes.result?.error)) {
      await new Promise(res => setTimeout(res, 300))
    }

    // ② 타겟 실행
    //   v78: 15초 → 30초 상향 (소스와 대칭)
    //   v84 A: side='tgt' + r 전달 → r._params 의 tgt_value 사용
    //   v86: 30초 → 60초 (소스와 대칭)
    r.testing = true
    const tgtRes = await _execWithTimeout(() => _execObjOnDB(connector.target, r.type, r.name, 'tgt', r), 60000)
    r.testStatus = tgtRes.status; r.testResult = tgtRes.result
    r.testing = false

    // ── v78: status 자동 승격 ─────────────────────────────────
    //   본부장 지적: fn_delinq_stage 가 "타겟 없음" + "타겟 테스트 ✓ 성공 (1행 반환)" 모순.
    //   원인: status 필드는 최초 오브젝트 검색 시에만 설정되고 runObjTest 에선 갱신 안 됨.
    //         재이관 성공해서 타겟에 생성됐는데도 status='missing' 유지.
    //   해결: 타겟 테스트가 성공했다면 타겟에 실존 → status='ok' 로 승격.
    //         반대로 status='ok' 였는데 타겟 테스트에서 "오브젝트 없음" 에러면 강등.
    if (r.testStatus === 'pass' && r.status !== 'ok') {
      console.log(`[v78] status 승격: ${r.name} (${r.status} → ok)`)
      r.status = 'ok'
    }

  } finally {
    r.srcTesting = false; r.testing = false
    // v74: 최근 검증 시간 — '기본 정렬 (최근 우선)' 모드의 정렬 키
    r._updatedAt = Date.now()
    if (autoOpen) objDetailRows[r.name + r.type] = true

    // ── Vue 3 reactivity 강제 트리거 ──────────────────────────
    // 객체 내부 프로퍼티만 바꾸면 배열 감지 못하는 경우 방지
    const idx = objResults.value.findIndex(x => x.name === r.name && x.type === r.type)
    if (idx !== -1) {
      objResults.value.splice(idx, 1, { ...objResults.value[idx] })
    }
  }
}

// ── 타임아웃 래퍼 ────────────────────────────────────────────
//   v86: 외부 래퍼 타임아웃도 'review' 로 분류 (실패 아님)
//     - 이전: status='fail' + is_timeout 없음 → 재이관 대상에 포함되는 버그
//     - 본부장 지적 "sp_merge_customer 30초 타임아웃" 정확히 일치
//     - 타임아웃 = AI 변환 문제 아님 = 재이관 대상 아님 (이미 존재하는 4619 로직과 일관)
//   v86: 기본 타임아웃 30s → 60s 상향 (_execObjOnDB 내부 axios 타임아웃과 일치)
async function _execWithTimeout(fn, timeoutMs = 60000) {
  return Promise.race([
    fn(),
    new Promise(resolve =>
      setTimeout(() => resolve({
        status: 'review',   // v86: fail → review
        result: {
          method: '실행 테스트',
          message: `시간 초과 (${Math.round(timeoutMs/1000)}초)`,
          error: `외부 타임아웃 (${Math.round(timeoutMs/1000)}초) — 배치성 프로시저 또는 대용량 뷰일 가능성. AI 재변환 대상 아님.`,
          elapsed_ms: timeoutMs,
          is_timeout: true,   // v86: 재이관 필터가 제외할 수 있도록 플래그 세팅
        }
      }), timeoutMs)
    )
  ])
}

async function runSelectedObjTest() {
  // v70: 재이관 루프 중이면 거부 — 동시 실행 시 testStatus/_remigResult 가 서로 덮어써서 UI 혼란
  if (remigrateLoading.value) {
    app.notify('재이관 작업이 진행 중입니다. 완료 후 다시 시도해 주세요.', 'warn')
    return
  }
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
  // v70: 자동 팝업 — 이미 재이관 팝업/루프 실행 중이면 무시.
  //   예전엔 검증 끝 → 800ms 후 무조건 openRemigrateModal() → 기존 팝업 덮어써서 루프 중단 버그 유발.
  if (fail > 0) {
    setTimeout(() => {
      if (remigrateLoading.value || showRemigrate.value) {
        app.notify(`검증 완료 (실패 ${fail}개) — 진행 중인 재이관 작업이 끝난 후 '재이관' 버튼으로 확인하세요.`, 'warn')
        return
      }
      openRemigrateModal()
    }, 800)
  }
}

async function runAllObjTest() {
  // v70: 재이관 루프 중이면 거부
  if (remigrateLoading.value) {
    app.notify('재이관 작업이 진행 중입니다. 완료 후 다시 시도해 주세요.', 'warn')
    return
  }
  // v90.78c: 본부장님 호소 — "2개 선택했는데 검증 시 전체 실행됨"
  //   원인: status='ok' 인 모든 객체 자동 테스트 (선택 무관)
  //   처방: objGroups 의 _sel 기반으로 필터링 (사용자가 선택한 것만)
  const selectedKeys = new Set()
  for (const grp of objGroups.value) {
    if (!selObjTypes.value.includes(grp.type)) continue
    for (const obj of grp.items) {
      if (obj._sel) selectedKeys.add(`${grp.type}::${obj.name}`)
    }
  }
  const testable = objResults.value.filter(r =>
    r.status === 'ok' && selectedKeys.has(`${r.type}::${r.name}`)
  )
  console.log('[v90.78c] runAllObjTest filtered:', testable.length, '/ ok:', objResults.value.filter(r => r.status === 'ok').length)
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
  // v70: 동일한 방어 — 진행 중 재이관 덮어쓰기 방지
  if (fail > 0) {
    setTimeout(() => {
      if (remigrateLoading.value || showRemigrate.value) {
        app.notify(`검증 완료 (실패 ${fail}개) — 진행 중인 재이관 작업이 끝난 후 '재이관' 버튼으로 확인하세요.`, 'warn')
        return
      }
      openRemigrateModal()
    }, 800)
  }
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
const remigrateAllDone  = ref(false)   // v56: 루프 종료 플래그 (완료 배지/닫기 강조용)

// v72: 재이관 루프 제어 플래그 — 본부장 요청 '실행 멈춤/재실행/중단' 기능.
//   테이블 검증 쪽 useRunPauseStop composable 과 같은 의미론이지만,
//   이 팝업은 프론트 루프(startRemigrate)만 돌아서 별도 플래그로 충분.
//   한계: 각 iteration 사이에서만 반영됨 (현재 in-flight axios 요청은 끝까지 진행).
//   즉 "일시정지" 누르면 '지금 건' 은 마저 하고 다음 건 가기 전에 멈춤.
const remigratePaused = ref(false)
const remigrateStopRequested = ref(false)

// v76: 재이관 팝업 최소화 — 본부장 요청. 팝업 닫아도 진행은 계속, 하단 미니바로 복귀 가능.
//   showRemigrate=false + remigrateMinimized=true 조합이 '최소화 상태'.
//   remigrateLoading (실행 중) 또는 remigrateAllDone (완료 확인 대기) 중 어느 쪽이어도 최소화 가능.
const remigrateMinimized = ref(false)

// 팝업 최소화
function remigrateMinimize() {
  remigrateMinimized.value = true
  showRemigrate.value = false
}

// 미니바 클릭 — 팝업 복구
function remigrateRestore() {
  remigrateMinimized.value = false
  showRemigrate.value = true
}

// 미니바 닫기 (완료 상태에서만 가능) — 완전 종료
function remigrateMinibarClose() {
  if (remigrateLoading.value) return   // 실행 중엔 불가 (x 아이콘 숨김)
  remigrateMinimized.value = false
  showRemigrate.value = false
  // progress 는 유지 — 혹시 다시 열어보고 싶을 수 있음
}

// 일시정지 액션
function remigratePauseToggle() {
  if (!remigrateLoading.value) return
  remigratePaused.value = !remigratePaused.value
  if (remigratePaused.value) {
    app.notify('재이관 일시정지 — 현재 처리 중인 항목이 끝난 후 멈춥니다', 'info')
  } else {
    app.notify('재이관 재개', 'info')
  }
}

// 중단 액션 (확인 후)
function remigrateAbort() {
  if (!remigrateLoading.value) return
  if (!confirm('재이관을 중단하시겠습니까?\n\n이미 처리된 항목은 롤백되지 않습니다. 현재 처리 중인 항목이 끝난 후 나머지는 건너뜁니다.')) return
  remigrateStopRequested.value = true
  remigratePaused.value = false   // paused 상태여도 중단은 진행
  app.notify('중단 요청됨 — 현재 항목 종료 후 멈춥니다', 'warn')
}

// v54: ESC 로 AI 재변환 모달 닫기 (backdrop 클릭 제거 대체)
//      단 remigrateLoading 중엔 닫히지 않음 — 사용자 실수로 진행 중단 방지
function _handleRemigrateEsc(e) {
  if (e.key === 'Escape' && showRemigrate.value && !remigrateLoading.value) {
    showRemigrate.value = false
  }
}
// watch 로 모달 열림/닫힘에 따라 리스너 등록/해제
watch(showRemigrate, (open) => {
  if (open) {
    document.addEventListener('keydown', _handleRemigrateEsc)
  } else {
    document.removeEventListener('keydown', _handleRemigrateEsc)
  }
})

// 이관 오류 판단 후 모달 열기
function openRemigrateModal(targets) {
  // v70: 동시성 락 — 이미 재이관 루프가 돌고 있는 중에 이 함수가 다시 호출되면
  //   전역 remigrateTargets/Progress 가 덮어씌워져 진행 중 루프가 깨짐.
  //   본부장 보고 증상: 미이관 AI 배포 1건 돌리는 중 백그라운드 검증이 끝나면서
  //     자동 openRemigrateModal() 이 튀어나와 기존 팝업을 덮고, 원래 루프는 중단된 것처럼 보임.
  //   정책: 이미 실행 중이면 (a) 자동 호출은 조용히 무시, (b) 사용자 명시 호출은 경고 후 무시.
  if (remigrateLoading.value) {
    const isAuto = !arguments[0]   // 인수 없이 호출되면 자동 경로 (setTimeout 등)
    if (!isAuto) {
      app.notify('이미 재이관 작업이 진행 중입니다. 완료 후 다시 시도해 주세요.', 'warn')
    } else {
      // 자동 호출은 조용히 스킵 — 완료 후 사용자가 직접 재이관 버튼 누르면 됨
      console.log('[openRemigrateModal] 진행 중인 작업 있음 — 자동 호출 스킵')
    }
    return
  }

  // v61: 팝업 새로 열 때마다 완료 플래그 리셋.
  //   이게 없어서 이전 루프의 완료 상태가 그대로 남아, 새 팝업이 뜨자마자
  //   "✓ 모든 항목 처리됨" 이 표시되고 AI 재변환 버튼이 숨겨지는 버그 발생했음.
  remigrateAllDone.value = false
  remigrateLoading.value = false
  remigrateStep.value = ''
  remigrateProgress.value = []
  // v72: 루프 제어 플래그도 리셋
  remigratePaused.value = false
  remigrateStopRequested.value = false
  // v76: 최소화 상태 리셋 — 새 재이관 시작 시 항상 팝업이 전면에 나옴
  remigrateMinimized.value = false

  if (!targets?.length) {
    // 인수 없으면 현재 실패 목록에서 자동 수집
    // v84 B: 본부장 요청 "출력 정확도 최상"
    //   재이관 대상에서 아래 경우 제외:
    //   - SIGNAL 비즈니스 에러 (프로시저가 정상 동작한 증거, AI 가 고칠 필요 없음)
    //   - status='ok' + testStatus='review' (타겟에 존재하고 비즈니스 로직만 검토 필요)
    //   - 이미 타겟에 있는데 데이터 부재로 실패한 것 (_isBusinessError 로 식별)
    targets = objResults.value.filter(r => {
      // 소스/타겟 어느 쪽도 실패가 아니면 재이관 대상 아님
      if (r.testStatus !== 'fail' && r.srcTestStatus !== 'fail') return false

      // v84 B: 타겟 실패지만 비즈니스 에러 (SIGNAL) 이면 → 이관은 OK, 데이터 문제
      if (r.testStatus === 'fail' && r.testResult?.error) {
        if (_isBusinessError(r.testResult.error)) {
          console.log(`[v84 B] 재이관 제외 - 비즈니스 에러: ${r.name} - ${r.testResult.error.slice(0,60)}`)
          return false
        }
      }
      // 소스 실패도 비즈니스 에러면 제외
      if (r.srcTestStatus === 'fail' && r.srcTestResult?.error) {
        if (_isBusinessError(r.srcTestResult.error)) {
          console.log(`[v84 B] 재이관 제외 - 소스 비즈니스 에러: ${r.name}`)
          return false
        }
      }
      // v86: testStatus 또는 srcTestStatus 가 'review' 면 제외
      //   본부장 지적: sp_merge_customer 가 30초 타임아웃 → 'review' 인데 재이관 대상에 포함됨.
      //   타임아웃 = 데이터량 / 락 / 성능 문제이지 AI 변환 문제 아님.
      if (r.testStatus === 'review' || r.srcTestStatus === 'review') {
        console.log(`[v86] 재이관 제외 - review 상태(타임아웃/검토): ${r.name}`)
        return false
      }
      return true
    })
  }

  // v60: 팝업 대상 필터링 — 본부장 지적 "매번 같은 게 재등장" 해결
  //   (a) 이미 재이관 성공한 것 (_remigResult.status === 'success') 제외
  //       → AI 로 한 번 고쳤는데 검증 로직이 계속 실패로 잡을 때 사용자 혼란 방지
  //   (b) 타임아웃 review 상태는 제외 (AI 가 해결 못 함)
  //   (c) 단, 인수로 명시적으로 전달된 경우는 예외 (runSingleObjAiRemig 용)
  const wasExplicit = arguments[0]?.length > 0
  if (!wasExplicit) {
    targets = targets.filter(r => {
      // 이미 재이관 성공 → 제외
      if (r._remigResult?.status === 'success') return false
      // 타임아웃 review 상태 → 제외 (AI 영역 밖)
      if (r.testResult?.is_timeout || r.srcTestResult?.is_timeout) return false
      return true
    })
  }

  if (!targets.length) { app.notify('이관 오류가 없습니다', 'info'); return }

  remigrateTargets.value = targets

  // v60: 원인 분류 — 본부장 요청
  // AI 재변환으로 해결 가능한 것 / 타임아웃 / 테스트 더미값 문제 를 분리해 표시
  const timeoutCount = targets.filter(r =>
    r.testResult?.is_timeout || r.srcTestResult?.is_timeout
  ).length
  const dummyCount = targets.filter(r => {
    const err = r.testResult?.error || r.srcTestResult?.error || ''
    return err.includes('cannot be null') || err.includes('Incorrect number of arguments')
  }).length
  const paramFails = targets.filter(r =>
    (r.testResult?.error || '').includes('1318') ||
    (r.testResult?.error || '').includes('Incorrect number')
  ).length
  const sqlFails = targets.filter(r =>
    (r.testResult?.error || '').includes('1111') ||
    (r.testResult?.error || '').includes('3593') ||
    (r.testResult?.error || '').includes('window function')
  ).length

  if (timeoutCount > 0 && timeoutCount >= targets.length / 2) {
    remigrateReason.value = `타임아웃 ${timeoutCount}건 — AI 재변환보다 수동 확인 필요`
  } else if (dummyCount > 0 && dummyCount >= targets.length / 2) {
    remigrateReason.value = `테스트 더미값 문제 ${dummyCount}건 — 파라미터 힌트 보완 필요`
  } else if (paramFails > sqlFails) {
    remigrateReason.value = `파라미터 수 불일치 ${paramFails}건 (이관 시 누락)`
  } else if (sqlFails > 0) {
    remigrateReason.value = `SQL 문법 미변환 ${sqlFails}건 (MySQL 호환 필요)`
  } else {
    remigrateReason.value = `실행 오류 ${targets.length}건`
  }

  remigrateAction.value = 'ai'
  showRemigrate.value = true
}

// v59: 단건 AI 재변환 — 행의 🤖 AI 버튼에서 호출.
// 기존 팝업 흐름을 재사용하되 단 1건으로 자동 시작. 팝업은 열려서 진행 상태 보여줌.
async function runSingleObjAiRemig(r) {
  if (r._aiRetrying) return   // 중복 방지
  // v71: 방식 A — 검증 중엔 단건 AI 버튼도 차단
  if (objTesting.value) {
    app.notify('오브젝트 검증이 진행 중입니다. 완료된 후 다시 시도해 주세요.', 'warn')
    return
  }
  if (remigrateLoading.value) {
    app.notify('이전 재이관 작업이 아직 진행 중입니다.', 'warn')
    return
  }
  r._aiRetrying = true
  try {
    // v64: 단건이 missing(타겟 없음) 상태이면 remigrateOnlyFail 플래그 off —
    //   그렇지 않으면 startRemigrate 가 testStatus==='fail' 필터로 0건 처리해버림.
    if (r.status === 'missing') {
      remigrateOnlyFail.value = false
    }
    // 테스트 결과가 없으면 에러 힌트 없이 "이관 누락" 의도로 처리
    openRemigrateModal([r])
    // 모달이 뜬 후 다음 tick 에 자동 실행
    await nextTick()
    await startRemigrate()
  } finally {
    r._aiRetrying = false
  }
}

// 재이관 실행
async function startRemigrate() {
  // v66: missing 상태 오브젝트(이관 자체가 안 된 것)는 testStatus 가 없어서
  //   remigrateOnlyFail 필터에 걸리면 0건이 됨. 전체 targets 에 missing 이 있으면
  //   onlyFail 플래그를 무시하고 전체를 돌림.
  const hasMissing = remigrateTargets.value.some(r => r.status === 'missing')

  let targets
  if (hasMissing) {
    // missing 포함 — 모두 돌림 (사용자가 체크박스 실수로 켜도 무시)
    targets = remigrateTargets.value
  } else if (remigrateOnlyFail.value) {
    targets = remigrateTargets.value.filter(r => r.testStatus === 'fail' || r.srcTestStatus === 'fail')
  } else {
    targets = remigrateTargets.value
  }

  // v66: 필터 후 0건이면 사용자 안내 (이전엔 조용히 완료 처리해서 혼란 유발)
  if (!targets.length) {
    app.notify('처리할 대상이 없습니다. "성공한 오브젝트 제외" 체크를 해제하고 다시 시도하세요.', 'warn')
    remigrateAllDone.value = true
    return
  }

  // 수동 수정 → 오브젝트 매핑 화면으로 이동
  if (remigrateAction.value === 'manual') {
    showRemigrate.value = false
    const names = targets.map(r => r.name).join(',')
    router.push(`/mapping/objects?highlight=${encodeURIComponent(names)}`)
    return
  }

  // AI 재변환 — Job 생성 + 모달 진행 상황 동시 표시
  remigrateLoading.value = true
  remigrateAllDone.value = false   // v56: 새 실행 시작 시 초기화
  remigrateProgress.value = targets.map(r => ({
    name: r.name, type: r.type, status: 'wait', msg: '대기 중'
  }))

  // v56: 메인 오브젝트 리스트 배지 기록 헬퍼.
  // 테이블 쪽 v49 의 `_remigResult` 패턴을 오브젝트에도 동일하게 적용.
  // 사용자 이득:
  //   - 팝업을 닫은 뒤에도 각 오브젝트가 최근에 재이관 시도했는지/성공했는지 한눈에
  //   - 여러 번 시도한 경우 마지막 결과가 남음
  //   - 수동 runObjValidate 실행 시 초기화됨 (아래 runObjValidate 에서 처리)
  function _markObjRemigResult(objName, status, errMsg) {
    const idx = objResults.value.findIndex(r => r.name === objName)
    if (idx < 0) return
    const prev = objResults.value[idx]
    // v78: 재이관 성공이면 이관 상태(status) 도 'ok' 로 승격.
    //   기존엔 재이관 후 status(missing) 그대로 유지 → "타겟 없음" + "재이관 성공" + "타겟 테스트 ✓" 모순.
    //   재이관이 DDL_CREATE 성공했다는 뜻이므로 타겟에 실존. status 즉시 반영.
    const nextStatus = status === 'success' ? 'ok' : prev.status
    objResults.value[idx] = {
      ...prev,
      status: nextStatus,
      _remigResult: {
        status,              // 'success' | 'failed'
        at:    Date.now(),
        error: errMsg || null,
      },
    }
  }


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
    // v72: 중단 요청 확인 — 즉시 루프 종료
    if (remigrateStopRequested.value) {
      remigrateStep.value = `사용자 중단 — ${i}개 처리 후 나머지 ${targets.length - i}개 건너뜀`
      // 남은 항목들을 'skip' 상태로 표시
      for (let j = i; j < targets.length; j++) {
        const skipRow = remigrateProgress.value[j]
        if (skipRow && skipRow.status === 'wait') {
          skipRow.status = 'skip'
          skipRow.msg = '건너뜀 (중단)'
        }
      }
      break
    }

    // v72: 일시정지 상태면 재개 또는 중단될 때까지 대기
    //   100ms 간격으로 깨어나서 상태 확인 — UI 반응성 보장
    while (remigratePaused.value && !remigrateStopRequested.value) {
      remigrateStep.value = `⏸ 일시정지됨 — 재개 버튼을 누르면 (${i+1}/${targets.length}) 부터 계속`
      await new Promise(res => setTimeout(res, 100))
    }
    // paused 였다가 stop 으로 바뀐 경우 루프 상단으로 돌아가 break 처리
    if (remigrateStopRequested.value) {
      i--   // 이번 iteration 시작 전이므로 i 복구
      continue
    }

    const r   = targets[i]
    const row = remigrateProgress.value[i]
    row.status = 'running'

    try {
      // ① DDL 조회
      remigrateStep.value = `(${i+1}/${targets.length}) ${r.name} — DDL 조회 중...`
      row.msg = 'DDL 조회 중...'
      await updateJobItem(r.name, 'running', 'DDL 조회 중')
      const { data: ddlData } = await axios.get('/api/v1/schema/objects/ddl', {
        params: {
          ...srcConn,
          obj_type: r.type, obj_name: r.name,
          obj_schema: r.schema_name || '',   // v53: MSSQL 스키마 힌트 (OBJECT_ID 정확히 찾기)
        },
        timeout: 30000   // v54: 12 → 30초 (MSSQL 과부하 시 대비)
      })
      const ddl = ddlData.ddl || ''
      if (!ddl) throw new Error('소스 DDL을 가져올 수 없습니다')

      // ② AI 변환 + ③ 배포 — v55: 문법 오류 시 에러 힌트 전달하며 최대 3회 재시도
      // 배경: AI 생성 DDL 이 MySQL 문법 오류 (ex. 세미콜론 위치, 예약어 충돌) 를
      //   내는 케이스가 있음. 에러 메시지를 AI 에게 다시 주면 고칠 수 있는 경우가 많음.
      // 루프: 최대 3회 (초회 1회 + 재시도 2회). 성공 시 즉시 종료.
      const MAX_ATTEMPTS = 3
      let converted = ''
      let deployData = null
      let lastError = ''
      let attemptOk = false

      for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
        // ── AI 변환 ──────────────────────────────
        const stepLabel = attempt === 1 ? 'AI 변환 중...' : `AI 재변환 중 (${attempt}/${MAX_ATTEMPTS}회)...`
        remigrateStep.value = `(${i+1}/${targets.length}) ${r.name} — ${stepLabel}`
        row.msg = stepLabel
        await updateJobItem(r.name, 'running', stepLabel)

        // 에러 힌트 조립 — 초회는 테스트 오류, 재시도는 직전 배포 오류 포함
        const hintParts = []
        if (attempt === 1) {
          if (r.testResult?.error)    hintParts.push(`타겟 테스트 오류: ${r.testResult.error}`)
          if (r.srcTestResult?.error) hintParts.push(`소스 테스트 오류: ${r.srcTestResult.error}`)
        } else {
          // 재시도 — 직전 변환 결과와 실제 MySQL 에러를 함께 전달
          hintParts.push(`⚠ 이전 변환 결과가 MySQL 에서 문법 오류를 냈습니다.`)
          hintParts.push(`직전 MySQL 에러: ${lastError}`)
          if (converted) {
            // DDL 일부만 전달 (너무 길면 AI 컨텍스트 낭비)
            const ddlSnip = converted.length > 2000 ? converted.slice(0, 2000) + '\n-- (이하 생략)' : converted
            hintParts.push(`직전 변환 DDL (참고, 같은 실수 피하세요):\n${ddlSnip}`)
          }
          hintParts.push(`MySQL 문법 규칙을 엄격히 지켜 다시 변환하세요. 특히 세미콜론 위치, 서브쿼리 alias, DELIMITER 사용을 주의하세요.`)
        }

        const { data: convData } = await axios.post('/api/v1/schema/convert-object-ai', {
          ...srcConn,
          tgt_db:     tgtConn.db_type,
          obj_type:   r.type,
          obj_name:   r.name,
          ddl,
          error_hint: hintParts.join('\n\n') || '',
        }, { timeout: 90000 })

        converted = convData.converted_ddl || ''
        if (!converted) {
          lastError = 'AI 변환 결과가 비었습니다'
          continue   // 재시도
        }

        // ── 타겟 배포 ────────────────────────────
        const deployLabel = attempt === 1 ? '타겟 배포 중... (최대 2분)' : `타겟 재배포 중... (${attempt}회)`
        remigrateStep.value = `(${i+1}/${targets.length}) ${r.name} — ${deployLabel}`
        row.msg = deployLabel
        await updateJobItem(r.name, 'running', deployLabel)

        try {
          const deployResp = await axios.post('/api/v1/schema/execute-object', {
            ...tgtConn,
            obj_type:     'DDL_CREATE',
            obj_sub_type: r.type,
            obj_name:     r.name,
            statements:   [converted],
            ddl:          converted,
          }, { timeout: 120000 })
          deployData = deployResp.data
        } catch (e) {
          if (e.code === 'ECONNABORTED') {
            // 타임아웃은 재시도해도 해결 가능성 낮음 — 사용자에게 상태 확인 안내하고 break
            throw new Error('배포가 2분 내 완료되지 않았습니다. 서버에서는 계속 진행 중일 수 있으니 잠시 후 오브젝트 목록을 새로고침하여 실제 생성 여부를 확인하세요.')
          }
          // 기타 네트워크 오류 — 마지막 attempt 가 아니면 재시도
          lastError = e.message || '네트워크 오류'
          if (attempt >= MAX_ATTEMPTS) throw e
          continue
        }

        if (deployData.success) {
          attemptOk = true
          if (attempt > 1) {
            // 재시도로 성공한 경우 로그에 명시 — 사용자가 "아 재시도로 고쳤구나" 이해할 수 있게
            row.msg = `완료 (${attempt}회 시도)`
          }
          break   // 성공 — 루프 탈출
        } else {
          lastError = deployData.error || '알 수 없는 MySQL 오류'
          // 루프 다시 돌면서 재변환
        }
      }

      if (!attemptOk) {
        throw new Error(`${MAX_ATTEMPTS}회 재시도 후에도 실패: ${lastError}`)
      }

      row.status = 'done'
      row.msg    = '완료'
      successNames.push(r.name)
      await updateJobItem(r.name, 'done', '완료')

      // v56: 메인 리스트(objResults)에도 배지 즉시 반영 — 팝업 닫힘 전에도 시각적 확인
      _markObjRemigResult(r.name, 'success', null)

    } catch(e) {
      // v67: axios 500 응답의 실제 에러 메시지 추출
      //   이전엔 'Request failed with status code 500' 만 표시 → 원인 파악 불가.
      //   FastAPI 는 HTTPException detail 을 response.data.detail 에 넣어주고,
      //   500 일반 에러는 response.data 에 문자열로 들어오기도 함.
      let realMsg = e.message || '실패'
      if (e.response?.data) {
        const d = e.response.data
        const detail = typeof d === 'string' ? d : (d.detail || d.error || JSON.stringify(d))
        if (detail) realMsg = `HTTP ${e.response.status}: ${String(detail).slice(0, 200)}`
      }
      row.status = 'fail'
      row.msg    = realMsg.substring(0, 100)
      await updateJobItem(r.name, 'error', realMsg.substring(0, 150), realMsg)

      // v56: 실패도 메인 리스트에 기록 — 사용자가 어느 오브젝트가 마지막에 어떻게 실패했는지
      //      백그라운드 화면에서 바로 확인 가능. 이 배지는 수동 재검증 때까지 유지.
      _markObjRemigResult(r.name, 'failed', realMsg)

      // v67: 첫 실패 시 콘솔에 전체 에러 dump — F12 에서 원인 정확히 볼 수 있게
      console.error(`[재이관 실패] ${r.name}:`, e.response?.data || e.message, e)
    }

    await new Promise(res => setTimeout(res, 200))
  }

  remigrateStep.value = ''
  // v75: remigrateLoading 은 아직 내리지 않음 — 재검증까지 끝나야 진짜 '완료'.
  //   기존 코드는 여기서 바로 false 로 내리고 나서 재검증 루프 돌렸는데,
  //   재검증 중에 UI 는 "완료" 도 "실행 중" 도 아닌 중간 상태가 됨
  //   → '취소' + 'AI 재변환 + 배포' 버튼이 잠깐 다시 노출되는 버그 발생 (본부장 보고).

  // v72: 중단 요청으로 끝난 경우 사용자에게 명확히 알림
  if (remigrateStopRequested.value) {
    const doneCount = remigrateProgress.value.filter(r => r.status === 'done').length
    const skipCount = remigrateProgress.value.filter(r => r.status === 'skip').length
    app.notify(`재이관 중단됨 — 완료 ${doneCount}개, 건너뜀 ${skipCount}개. 이미 성공한 항목은 자동 재검증합니다.`, 'warn')
    // 여기서 return 하지 않고 아래 흐름 계속 — 성공한 만큼은 재검증까지 돌려주는 게 맞음
  }

  const ok   = remigrateProgress.value.filter(r => r.status === 'done').length
  const fail = remigrateProgress.value.filter(r => r.status === 'fail').length

  if (successNames.length) {
    // ── 재이관 성공 항목 자동 재검증 ──────────────────────────
    app.notify(`재이관 완료 — ${ok}개 항목 자동 재검증 중...`, 'success')

    const reTestTargets = objResults.value.filter(r => successNames.includes(r.name))
    for (let ri = 0; ri < reTestTargets.length; ri++) {
      const r = reTestTargets[ri]
      // v75: 재검증 진행도 팝업 step 으로 표시 — 사용자가 뭘 기다리는지 알 수 있게
      remigrateStep.value = `재검증 중 (${ri+1}/${reTestTargets.length}) ${r.name}...`
      // v75: progress 리스트의 해당 행 msg 도 업데이트
      const progRow = remigrateProgress.value.find(p => p.name === r.name)
      if (progRow) progRow.msg = '재검증 중...'
      try {
        // 상태 초기화 후 재검증 실행
        r.testStatus = null; r.testResult = null
        r.srcTestStatus = null; r.srcTestResult = null
        await runObjTest(r, false)   // autoOpen=false: 상세창 자동 열기 안 함
        // v75: 재검증 결과를 progress 에 반영
        if (progRow) {
          if (r.testStatus === 'pass' && r.srcTestStatus === 'pass') {
            progRow.msg = '완료 ✓ 재검증 통과'
          } else {
            progRow.msg = `완료 ⚠ 재검증 ${r.testStatus || 'fail'}`
          }
        }
        await new Promise(res => setTimeout(res, 300))
      } catch(e) {
        console.warn(`[재검증 실패] ${r.name}:`, e.message)
        if (progRow) progRow.msg = '완료 ⚠ 재검증 오류'
      }
    }

    app.notify(
      `재이관 + 재검증 완료 — 성공 ${ok}개` +
      (reTestTargets.filter(r => r.testStatus === 'pass').length === ok
        ? ' ✓ 모두 통과!' : ' (일부 항목 확인 필요)'),
      reTestTargets.filter(r => r.testStatus === 'pass').length === ok ? 'success' : 'warn'
    )
  } else {
    app.notify(`재이관 실패 — 오류 내용을 확인하세요`, 'error')
  }

  // v75: 재검증까지 끝난 뒤 한 번에 상태 전환
  //   이 순서가 중요 — loading=false 를 먼저 내리면 아주 짧게(1 tick) allDone=false 인
  //   상태가 노출됨. 동일 tick 에 둘 다 바꾸면 UI 깜빡임 방지.
  remigrateStep.value = ''
  remigrateAllDone.value = true
  remigrateLoading.value = false
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
  jobStore.fetch()  // 이관 중 감지용
  // 10초마다 job 상태 갱신 → 이관 완료 시 배너 자동 제거
  const jobPollTimer = setInterval(() => jobStore.fetch(), 10000)

  // v49: 백그라운드 재이관 추적 시작 — 팝업 닫혀도 완료 감지 + 결과 자동 갱신
  startBgRemigPolling()

  onActivated(() => {
    Object.keys(detailRows).forEach(k => delete detailRows[k])
    // v49: 페이지 재진입 시 폴링 재시작 (onDeactivated 에서 중지됐을 수 있음)
    startBgRemigPolling()
    // v90.69: 페이지 재진입 시 connector 가 idle 인데 host/db 정보 있으면 자동 재연결
    _autoReconnectIfPossible()
  })
  onDeactivated(() => {
    clearInterval(jobPollTimer)
    stopBgRemigPolling()   // v49: 페이지 이탈 시 폴링 중지 (불필요한 네트워크)
  })
  connector.loadProfiles()  // 프로파일 로드
  loadHistory()
  // v90.69: 첫 진입 시에도 자동 재연결 (이미 다른 페이지에서 입력했던 정보 활용)
  _autoReconnectIfPossible()
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

/* ConnectPanel CSS → ConnectPanel.vue 참조 */
.vp-migrating-warn {
  display:flex; align-items:flex-start; gap:10px;
  padding:10px 16px; margin-bottom:10px;
  background:rgba(245,158,11,.08);
  border:0.5px solid rgba(245,158,11,.35);
  border-radius:var(--radius-md);
  font-size:.8rem; color:#92400e;
  line-height:1.5;
}
.vp-migrating-warn strong { font-weight:700; margin-right:6px; }
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

/* v90.69: 자동 재연결 중 + 연결 완료 슬림 인디케이터 */
.vp-auto-connect {
  display:flex; align-items:center; gap:10px;
  padding:8px 14px; margin-bottom:10px;
  background:rgba(59,130,246,.08);
  border:0.5px solid rgba(59,130,246,.25);
  border-radius:var(--radius-md);
  font-size:.78rem; color:#1d4ed8;
}
.vp-auto-spinner {
  width:12px; height:12px; border-radius:50%;
  border:1.8px solid rgba(59,130,246,.25);
  border-top-color:#3b82f6;
  animation:spin .8s linear infinite;
  flex-shrink:0;
}
/* v90.72: vp-conn-status 관련 CSS 제거 — PageHeader 와 중복이라 사용 안 함 */

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
  font-weight:500; font-family:var(--font); cursor:pointer; color:var(--text-tertiary);
  background:transparent; transition:all .12s;
}
.vp-tab:hover { color:var(--text-primary); border-color:var(--border-mid); }
.vp-tab.active { color:var(--accent-blue); font-weight:700; border-color:var(--accent-blue); background:rgba(59,130,246,.04); }

/* v40: 다음 단계 유도 펄스 — 연결 완료 후 탭을 아직 선택 안 했을 때 두 탭 모두 깜빡임 */
.vp-tab.vp-pulse-next {
  color: var(--accent-blue) !important;
  border-color: var(--accent-blue) !important;
  background: rgba(59,130,246,.06) !important;
  animation: vp-pulse-next 1.6s ease-in-out infinite;
}
.vp-tab.vp-pulse-next:hover {
  animation: none;
  background: var(--accent-blue) !important;
  color: #fff !important;
}
/* v40: 검증 실행 버튼용 펄스 (녹색 — 이미 파란 chip-run 에 올라가는 링) */
.chip-run.vp-pulse-next {
  animation: vp-pulse-next-run 1.4s ease-in-out infinite;
}
.chip-run.vp-pulse-next:hover { animation: none; }
@keyframes vp-pulse-next {
  0%, 100% { box-shadow: 0 0 0 0 rgba(37,99,235,.40); }
  50%      { box-shadow: 0 0 0 6px rgba(37,99,235,0); }
}
@keyframes vp-pulse-next-run {
  0%, 100% { box-shadow: 0 0 0 0 rgba(37,99,235,.55); }
  50%      { box-shadow: 0 0 0 7px rgba(37,99,235,0); }
}
/* 접근성: 모션 감소 설정 시엔 애니메이션 끄고 테두리만 강조 */
@media (prefers-reduced-motion: reduce) {
  .vp-tab.vp-pulse-next,
  .chip-run.vp-pulse-next { animation: none; }
}

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

/* v74: 활성 상태 chip (기본 정렬 토글 등) — 파란 테두리 + 엷은 배경으로 "지금 켜져 있음" 표시 */
.chip.chip-active {
  background: #eff6ff;
  color: #1d4ed8;
  border-color: #93c5fd;
  font-weight: 600;
}
.chip.chip-active:hover { background: #dbeafe; }

/* v76: 재이관 최소화 미니바 — 하단 고정, 클릭 시 팝업 복구 */
.vp-remig-minibar {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 9998;         /* 팝업(9999)보다 한 단계 아래 — 팝업 열리면 가려짐이 맞음 */
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 320px;
  max-width: 480px;
  padding: 10px 14px;
  background: #ffffff;
  border: 1.5px solid var(--accent-blue, #3b82f6);
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0,0,0,.15), 0 2px 6px rgba(0,0,0,.08);
  cursor: pointer;
  font-family: var(--font);
  animation: vpRemigMinibarSlideUp .25s ease-out;
  transition: transform .15s, box-shadow .15s;
}
.vp-remig-minibar:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgba(0,0,0,.18), 0 4px 10px rgba(0,0,0,.1);
}
@keyframes vpRemigMinibarSlideUp {
  from { opacity: 0; transform: translateY(20px); }
  to   { opacity: 1; transform: translateY(0); }
}
.vp-remig-minibar-icon {
  flex-shrink: 0;
  width: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.vp-remig-minibar-text {
  flex: 1;
  min-width: 0;   /* 긴 이름 잘리도록 */
}
.vp-remig-minibar-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-primary, #111827);
  line-height: 1.3;
}
.vp-remig-minibar-sub {
  font-size: 11px;
  color: var(--text-secondary, #6b7280);
  line-height: 1.3;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.vp-remig-minibar-progress {
  position: absolute;
  left: 0; right: 0; bottom: 0;
  height: 3px;
  background: #e5e7eb;
  border-radius: 0 0 8px 8px;
  overflow: hidden;
}
.vp-remig-minibar-progress-fill {
  height: 100%;
  background: var(--accent-blue, #3b82f6);
  transition: width .3s ease;
}
.vp-remig-minibar-close {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border: none;
  background: transparent;
  color: var(--text-tertiary, #9ca3af);
  cursor: pointer;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1;
}
.vp-remig-minibar-close:hover { background: #f3f4f6; color: #374151; }

/* v43: 실행/일시정지/중단 3버튼 그룹 */
/* v44: 선택→수행 시선 흐름 — 버튼 그룹을 오른쪽 끝으로 배치 */
.vp-run-grp { display:inline-flex; gap:6px; align-items:center; margin-left:auto; flex-shrink:0; }

/* v43: 일시정지 버튼 — 노란색 (경고색, 중단과 구분) */
.chip-pause {
  display:inline-flex; align-items:center; gap:5px;
  padding:5px 12px; border-radius:7px;
  font-size:.8rem; font-weight:600; font-family:var(--font);
  background:#f59e0b; color:#fff;
  border:1px solid #f59e0b;
  cursor:pointer; transition:all .15s; white-space:nowrap; line-height:1.4;
  animation: vp-pause-pulse 1.6s ease-in-out infinite;
}
.chip-pause:hover { background:#d97706; border-color:#d97706; animation: none; }
.chip-pause:disabled { opacity:.45; cursor:not-allowed; animation:none; }
/* 일시정지됨 상태 (재개 버튼) — 파란색으로 돌아옴 */
.chip-pause.paused {
  background:#3b82f6; border-color:#3b82f6;
  animation: vp-pulse-next-run 1.4s ease-in-out infinite;
}
.chip-pause.paused:hover { background:#2563eb; border-color:#2563eb; animation:none; }

/* v43: 중단 버튼 — 빨간색 */
.chip-stop {
  display:inline-flex; align-items:center; gap:5px;
  padding:5px 12px; border-radius:7px;
  font-size:.8rem; font-weight:600; font-family:var(--font);
  background:#dc2626; color:#fff;
  border:1px solid #dc2626;
  cursor:pointer; transition:all .15s; white-space:nowrap; line-height:1.4;
}
.chip-stop:hover { background:#b91c1c; border-color:#b91c1c; }
.chip-stop:disabled { opacity:.55; cursor:not-allowed; }

/* v43: 버튼 안의 카운트 배지 (예: 12/42) */
.vp-btn-cnt {
  font-size:.7rem; font-weight:500; opacity:.85;
  padding:1px 6px; border-radius:99px;
  background:rgba(255,255,255,.2);
  margin-left:1px;
}

@keyframes vp-pause-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(245,158,11,.50); }
  50%      { box-shadow: 0 0 0 6px rgba(245,158,11,0); }
}

/* v42: 중단 모드 — 빨간색 + 깜빡이는 링 (하위 호환 유지 — 혹시 다른 곳서 참조) */
.chip-run.vp-stop-btn {
  background: #dc2626 !important;
  border-color: #dc2626 !important;
  animation: vp-stop-pulse 1.4s ease-in-out infinite;
}
.chip-run.vp-stop-btn:hover {
  background: #b91c1c !important;
  border-color: #b91c1c !important;
  animation: none;
}
.chip-run.vp-stop-btn:disabled {
  animation: none;
}
@keyframes vp-stop-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(220,38,38,.50); }
  50%      { box-shadow: 0 0 0 6px rgba(220,38,38,0); }
}
@media (prefers-reduced-motion: reduce) {
  .chip-run.vp-stop-btn,
  .chip-pause,
  .chip-pause.paused { animation: none; }
}

/* v42: 중단됨 배지 (Summary KPI 영역) */
.vp-aborted-badge {
  display:inline-flex; align-items:center; gap:6px;
  padding:4px 11px; border-radius:99px;
  background:rgba(220,38,38,.10); color:#b91c1c;
  border:0.5px solid rgba(220,38,38,.25);
  font-size:11.5px; font-weight:700;
  white-space:nowrap; flex-shrink:0;
}
/* v43: 일시정지됨 배지 */
.vp-paused-badge {
  display:inline-flex; align-items:center; gap:6px;
  padding:4px 11px; border-radius:99px;
  background:rgba(245,158,11,.12); color:#b45309;
  border:0.5px solid rgba(245,158,11,.35);
  font-size:11.5px; font-weight:700;
  white-space:nowrap; flex-shrink:0;
  animation: vp-paused-badge-pulse 2s ease-in-out infinite;
}
@keyframes vp-paused-badge-pulse {
  0%,100% { opacity:1; }
  50%     { opacity:.7; }
}
@media (prefers-reduced-motion: reduce) {
  .vp-paused-badge { animation: none; }
}

/* 스피너 */
.vp-spin {
  width:12px; height:12px; border-radius:50%; border:2px solid rgba(255,255,255,.3);
  border-top-color:#fff; animation:vp-spin .7s linear infinite; display:inline-block;
}
@keyframes vp-spin { to { transform:rotate(360deg); } }

/* 진행바 */
/* ── 검증 진행 상태바 ── */
/* ── KPI 행 인라인 진행 블록 ── */
.vp-kpi-sep { width:0.5px; height:40px; background:var(--border-light); flex-shrink:0; }
.vp-kpi-prog-block {
  flex:2; min-width:320px; max-width:680px;
  display:flex; flex-direction:column; gap:5px;
  padding:8px 12px;
  background:var(--bg-secondary);
  border:0.5px solid var(--border-light);
  border-radius:9px;
}
.vp-kpi-prog-header { display:flex; align-items:center; gap:6px; }
.vp-kpi-prog-tbl { font-size:.75rem; font-weight:600; color:var(--text-primary); flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-family:'Consolas','SF Mono',monospace; }
.vp-kpi-prog-cnt { font-size:.68rem; color:var(--text-tertiary); flex-shrink:0; }
.vp-kpi-prog-pct { font-size:.72rem; font-weight:700; color:var(--accent-blue); flex-shrink:0; }
.vp-kpi-prog-bar { height:4px; background:var(--border-light); border-radius:2px; overflow:hidden; }
.vp-kpi-prog-fill { height:100%; background:var(--accent-blue); border-radius:2px; transition:width .3s; }
.vp-kpi-time-row { display:flex; align-items:center; gap:5px; flex-wrap:nowrap; overflow:hidden; }
.vp-kpi-time-item { display:inline-flex; align-items:center; gap:3px; }
.vp-kti-icon { font-size:.7rem; flex-shrink:0; }
.vp-kti-lbl { font-size:.62rem; color:var(--text-tertiary); flex-shrink:0; }
.vp-kti-val { font-size:.7rem; font-weight:600; color:var(--text-secondary); white-space:nowrap; font-variant-numeric:tabular-nums; }
.vp-kpi-time-item.dim .vp-kti-val { color:var(--text-tertiary); font-weight:400; }
.vp-kti-sep { color:var(--border-strong); font-size:.65rem; flex-shrink:0; }
.vp-prog-header { display:flex; align-items:center; gap:8px; }
.vp-prog-cur-tbl { font-size:.8rem; font-weight:600; color:var(--text-primary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-family:'Consolas','SF Mono',monospace; flex:1; min-width:0; }
.vp-prog-count { font-size:.7rem; color:var(--text-tertiary); white-space:nowrap; flex-shrink:0; background:var(--bg-primary); padding:2px 8px; border-radius:99px; border:0.5px solid var(--border-light); }
.vp-prog-pct-badge { font-size:.72rem; font-weight:700; color:var(--accent-blue); flex-shrink:0; }
.vp-prog-track { height:5px; background:var(--border-light); border-radius:3px; overflow:hidden; }
.vp-prog-fill { height:100%; background:var(--accent-blue); border-radius:3px; transition:width .4s; }
/* 시간 카드 3개 */
.vp-prog-time-row { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:2px; }
.vp-time-card { display:flex; align-items:center; gap:9px; padding:8px 12px; background:var(--bg-primary); border:0.5px solid var(--border-light); border-radius:8px; transition:opacity .2s; }
.vp-time-card.dim { opacity:.45; }
.vp-time-card.accent { border-color:rgba(37,99,235,.25); background:rgba(37,99,235,.04); }
.vp-time-icon { font-size:1.1rem; flex-shrink:0; line-height:1; }
.vp-time-body { display:flex; flex-direction:column; gap:2px; min-width:0; }
.vp-time-label { font-size:.62rem; font-weight:600; color:var(--text-tertiary); text-transform:uppercase; letter-spacing:.04em; white-space:nowrap; }
.vp-time-value { font-size:.82rem; font-weight:700; color:var(--text-primary); white-space:nowrap; font-variant-numeric:tabular-nums; }
.vp-time-card.accent .vp-time-value { color:#1d4ed8; }
/* 체크섬 상세 */
.vp-checksum-info { background:var(--bg-secondary); border:0.5px solid rgba(245,158,11,.3); border-radius:8px; padding:10px 12px; display:flex; flex-direction:column; gap:8px; }
.vp-cs-error { display:flex; gap:8px; align-items:flex-start; }
.vp-cs-err-label { font-size:.68rem; font-weight:700; color:#d97706; white-space:nowrap; flex-shrink:0; }
.vp-cs-err-msg { font-size:.7rem; color:var(--text-secondary); line-height:1.5; word-break:break-all; }
.vp-cs-diff { display:flex; flex-direction:column; gap:4px; }
.vp-cs-row { display:flex; align-items:center; gap:8px; }
.vp-cs-side { font-size:.68rem; font-weight:700; padding:1px 7px; border-radius:4px; flex-shrink:0; width:52px; text-align:center; }
.vp-cs-side.src { background:rgba(37,99,235,.1); color:#1d4ed8; }
.vp-cs-side.tgt { background:rgba(22,163,74,.1); color:#15803d; }
.vp-cs-hash { font-size:.72rem; font-family:'Consolas','SF Mono',monospace; color:var(--text-secondary); background:var(--bg-primary); padding:2px 8px; border-radius:4px; }
.vp-cs-hash.diff { color:#dc2626; background:rgba(239,68,68,.06); }
.vp-cs-actions { display:flex; align-items:center; justify-content:space-between; gap:10px; padding-top:6px; border-top:0.5px solid var(--border-light); }
.vp-cs-hint { font-size:.7rem; color:var(--text-tertiary); line-height:1.5; flex:1; }
.vp-cs-accept-btn { padding:5px 12px; border-radius:6px; background:rgba(22,163,74,.1); color:#15803d; border:0.5px solid rgba(22,163,74,.3); font-size:.75rem; font-weight:600; cursor:pointer; font-family:var(--font); white-space:nowrap; transition:all .12s; flex-shrink:0; }
.vp-cs-accept-btn:hover { background:rgba(22,163,74,.2); }

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
/* v39: 스크롤 가능한 영역 — 최대 높이 제한 + overflow-y:auto.
        thead 는 sticky 로 상단 고정. */
.vp-res-wrap { border:0.5px solid var(--border-light); border-radius:10px; overflow:hidden; }
.vp-res-scroll { max-height:calc(100vh - 380px); min-height:260px; overflow-y:auto; overflow-x:auto; }
.vp-tbl { width:100%; border-collapse:collapse; font-size:12px; }
.vp-tbl th {
  background:var(--bg-secondary); padding:7px 10px; text-align:left;
  font-size:11px; font-weight:600; color:var(--text-tertiary);
  border-bottom:0.5px solid var(--border-mid); white-space:nowrap;
  position:sticky; top:0; z-index:5;
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

/* v39: 방금 재검증된 행 하이라이트 — 3초간 노란 깜빡임 */
.vp-row.vp-row-just-updated td {
  background:rgba(250,204,21,.22) !important;
  animation:vp-row-flash 3s ease-out;
}
@keyframes vp-row-flash {
  0%   { background:rgba(250,204,21,.55); }
  50%  { background:rgba(250,204,21,.32); }
  100% { background:rgba(250,204,21,.12); }
}

/* v39: 정렬 상태 표시용 작은 배지 (기본 "최신순") */
.vp-sort-status {
  display:inline-flex; align-items:center; gap:5px;
  font-size:11px; color:var(--text-tertiary);
  padding:3px 9px; border-radius:99px;
  background:var(--bg-secondary); border:0.5px solid var(--border-light);
  margin-left:8px;
}
.vp-sort-status-clear {
  background:transparent; border:none; color:#2563eb;
  cursor:pointer; font-size:11px; padding:0 2px; font-family:var(--font);
}
.vp-sort-status-clear:hover { text-decoration:underline; }

.vp-tbl-nm-cell { vertical-align:middle; }
.vp-tbl-nm {
  display:flex; align-items:center; gap:5px;
  font-family:'Consolas','SF Mono',monospace; font-weight:500; font-size:12px;
}
.vp-status-ico { display:flex; align-items:center; justify-content:center; }

/* v49: 재이관 결과 영구 배지 — 다음 수동 검증 전까지 유지 */
.vp-remig-badge {
  display:inline-flex; align-items:center; gap:3px;
  padding:2px 7px; border-radius:10px;
  font-size:.68rem; font-weight:600;
  white-space:nowrap;
  border:0.5px solid transparent;
}
.vp-remig-badge.success {
  background: rgba(22,163,74,.1);
  color:#15803d;
  border-color: rgba(22,163,74,.3);
}
.vp-remig-badge.failed {
  background: rgba(220,38,38,.08);
  color:#b91c1c;
  border-color: rgba(220,38,38,.3);
}
/* v56: 재이관 루프 완료 후 "완료 — 닫기" 버튼 강조 (초록 톤) */
.chip.chip-done-close {
  background: #16a34a;
  color: #fff;
  border-color: #15803d;
  font-weight: 600;
}
.chip.chip-done-close:hover { background: #15803d; }

/* v56: 이름셀 내부에 배지가 오니까 여백 약간 확보 + 줄바꿈 방지 */
.vp-obj-nm-cell .vp-remig-badge { margin-left: 6px; vertical-align: middle; }

/* 배지 */
.vp-badge { font-size:10.5px; font-weight:600; padding:2px 7px; border-radius:6px; white-space:nowrap; }
.vp-badge.ok   { background:rgba(34,197,94,.12); color:#15803d; }
.vp-badge.fail { background:rgba(239,68,68,.12);  color:#dc2626; }
.vp-badge.miss { background:rgba(245,158,11,.12); color:#b45309; }
.vp-badge.warn { background:rgba(245,158,11,.12); color:#b45309; }
.vp-badge.gray { color:var(--text-tertiary); }

/* 인라인 버튼 */
.vp-act-td { padding:5px 8px !important; white-space:nowrap; text-align:center; }
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
.vp-detail-row td { padding:0; background:var(--bg-secondary); border-bottom:0.5px solid var(--border-light) !important; }
.vp-no-detail { padding:8px; font-size:11px; color:var(--text-tertiary); text-align:center; }
.vp-detail-box { padding:10px 16px 0; display:flex; flex-direction:column; gap:8px; }
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
/* v90.78: 헤더 전체 클릭 가능 */
.vp-obj-sec-hdr-clickable {
  cursor: pointer;
  user-select: none;
  transition: background 0.12s;
}
.vp-obj-sec-hdr-clickable:hover {
  background: rgba(20, 184, 166, 0.08);
}
.vp-obj-sec-hdr-clickable:hover .vp-obj-sec-label {
  color: #14b8a6;
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
.vp-row-running { background: rgba(37,99,235,.06) !important; }
.vp-row-running td:nth-child(3) .vp-obj-nm-cell { color: var(--accent-blue); font-weight:600; }
.vp-obj-row.selected { background: rgba(59,130,246,.05); }

.vp-obj-nm { font-family:'Consolas','SF Mono',monospace; font-weight:500; color:var(--text-primary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:11.5px; }

/* 이력 */
.vp-hist-card { padding:14px 16px; }
.vp-hist-hdr { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
.vp-hist-title { font-size:13px; font-weight:600; color:var(--text-primary); }

/* ── 2컬럼 리스트 ── */
.vp-list-wrap {
  display: flex;
  flex-direction: column;
  height: 320px;
  overflow: hidden;
}
.vp-list-divider { background: var(--border-light); flex-shrink: 0; width: 0.5px; }

/* 컬럼 */

/* ── 페어 행 방식 CSS ── */
.vp-pair-hdr {
  display: flex; align-items: center;
  border-bottom: 0.5px solid var(--border-mid);
  background: var(--bg-secondary);
  flex-shrink: 0; min-height: 36px;
}
.vp-pair-hdr-col {
  flex: 1; display: flex; align-items: center; gap: 6px;
  padding: 5px 10px; min-width: 0;
}
.vp-pair-body { overflow-y: auto; flex: 1; min-height: 0; }
.vp-pair-row {
  display: flex; align-items: stretch;
  border-bottom: 0.5px solid var(--border-light);
  transition: background .1s; min-height: 30px;
}
.vp-pair-row:hover { background: var(--bg-primary); }
.vp-pair-row.pair-match     { background: rgba(22,163,74,.03); }
.vp-pair-row.pair-mismatch  { background: rgba(239,68,68,.03); }
.vp-pair-row.pair-active    { background: rgba(59,130,246,.06); }
.vp-pair-cell {
  flex: 1; display: flex; align-items: center; gap: 6px;
  padding: 6px 10px; cursor: pointer; min-width: 0;
  transition: background .1s;
  /* v46: 선택 상태 왼쪽 막대를 위한 공간 확보 (선택되지 않았을 땐 투명) */
  /* v47: 4px 로 살짝 두껍게 — 배경을 없앤 만큼 막대만으로 식별성 확보 */
  border-left: 4px solid transparent;
}
/* v47: 배경 제거 — 왼쪽 파란 세로 막대로만 선택 표시 (훨씬 깔끔) */
.vp-pair-cell.selected  {
  border-left-color: #2563eb;
}
.vp-pair-cell.src-only  { background: rgba(217,119,6,.04); }
.vp-pair-cell.tgt-only  { background: rgba(139,92,246,.04); }
.vp-pair-cell.r-ok      { background: rgba(22,163,74,.04); }
.vp-pair-cell.r-fail    { background: rgba(239,68,68,.04); }
.vp-pair-cell.pair-empty { opacity: .35; cursor: default; }
.vp-pair-empty-cell {
  font-size: .72rem; color: var(--text-tertiary); padding-left: 20px;
}

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
  padding: 5px 10px 5px 8px;
  cursor: pointer;
  transition: background .08s;
  border-bottom: 0.5px solid var(--border-light);
  border-left: 3px solid transparent;
  min-height: 32px;
}
.vp-list-row:last-child { border-bottom: none; }
.vp-list-row:hover { background: var(--bg-secondary); }
.vp-list-row.selected { background: rgba(59,130,246,.04); }
/* 검증 결과별 행 배경 — 검증 완료 후만 색상 적용 */
.vp-list-row.r-ok   { border-left:3px solid #16a34a !important; background:rgba(22,163,74,.07); }
.vp-list-row.r-ok:hover { background:rgba(22,163,74,.12); }
.vp-list-row.r-ok .vp-list-nm { color:#15803d; font-weight:600; }
.vp-list-row.r-fail  { border-left:3px solid #dc2626 !important; background:rgba(220,38,38,.07); }
.vp-list-row.r-fail:hover { background:rgba(220,38,38,.12); }
.vp-list-row.r-fail .vp-list-nm { color:#b91c1c; font-weight:600; }
.vp-list-row.src-only { border-left:3px solid #d97706 !important; }
.vp-list-row.src-only .vp-list-nm { color:#b45309; }
.vp-list-row.tgt-only { border-left:3px solid #8b5cf6 !important; }
.vp-list-row.tgt-only .vp-list-nm { color: #6d28d9; }

/* 아이콘 */
.vp-list-ico {
  width: 14px; height: 14px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  margin-right: 1px;
}
.vp-list-ico-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: #94a3b8;
}
.vp-list-ico-dot.tgt { background: #22c55e; }
.vp-list-ico-spin { width:9px; height:9px; border:1.5px solid rgba(37,99,235,.3); border-top-color:#2563eb; border-radius:50%; animation:spin .7s linear infinite; flex-shrink:0; }
.vp-list-row.r-active { background:rgba(37,99,235,.1) !important; border-color:rgba(37,99,235,.3) !important; }
.vp-list-row.r-active .vp-list-nm { color:#1d4ed8; font-weight:600; }

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
.vp-list-badge.src-only { background: rgba(245,158,11,.2); color: #92400e; font-weight:700; }
.vp-list-badge.tgt-only { background: rgba(139,92,246,.18); color: #5b21b6; font-weight:700; }

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
.vp-tab-row { display:flex; align-items:center; justify-content:space-between; margin-bottom:4px; gap:12px; }
/* 검증방법 인라인 설명 */
.vm-inline-desc {
  display:flex; align-items:center; gap:8px;
  flex:1; min-width:0; max-width:55%;
  padding:6px 12px;
  background:var(--bg-secondary);
  border:0.5px solid var(--border-light);
  border-radius:var(--radius-md);
  overflow:hidden;
}
.vm-icon  { font-size:1rem; flex-shrink:0; }
.vm-info  { display:flex; align-items:center; gap:5px; flex:1; min-width:0; overflow:hidden; }
.vm-name  { font-size:.75rem; font-weight:700; color:var(--text-primary); white-space:nowrap; flex-shrink:0; }
.vm-sep   { color:var(--border-strong); font-size:.7rem; flex-shrink:0; }
.vm-detail{ font-size:.71rem; color:var(--text-tertiary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.vm-tags  { display:flex; gap:4px; flex-shrink:0; }
.vm-badge { font-size:.62rem; font-weight:600; padding:1px 6px; border-radius:99px; flex-shrink:0; }
.vm-badge.fast { background:rgba(22,163,74,.12); color:#15803d; }
.vm-badge.mid  { background:rgba(245,158,11,.12); color:#b45309; }
.vm-badge.slow { background:rgba(239,68,68,.10);  color:#dc2626; }
.vm-chk { font-size:.65rem; padding:1px 7px; border-radius:99px; font-weight:600; white-space:nowrap; }
.vm-chk.on  { background:rgba(22,163,74,.1);  color:#15803d; }
.vm-chk.mid { background:rgba(245,158,11,.1); color:#b45309; }
.vm-chk.off { background:var(--bg-tertiary);  color:var(--text-tertiary); }
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
/* v10 #34-B: 타겟 이름 변형 매칭 힌트 */
.vp-name-variant {
  display: inline-block;
  margin-left: 4px;
  padding: 0 5px;
  background: rgba(37,99,235,.08);
  color: #2563eb;
  border-radius: 4px;
  font-size: 9.5px;
  font-weight: 600;
  font-family: ui-monospace, Menlo, Consolas, monospace;
  cursor: help;
}

/* v50: 진단 버튼 — "타겟 없음" 오진단 원인 파악용 */
.vp-diag-btn {
  margin-left: 5px;
  padding: 1px 6px;
  border-radius: 4px;
  border: 0.5px solid rgba(220,38,38,.35);
  background: rgba(220,38,38,.06);
  color: #b91c1c;
  font-size: 9.5px;
  font-weight: 600;
  cursor: pointer;
  transition: background .12s;
}
.vp-diag-btn:hover { background: rgba(220,38,38,.14); }

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

/* v79: 소스 → 타겟 값 복사 버튼 */
.vp-param-copy-btn {
  border: 0.5px solid var(--border-mid);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  border-radius: 4px;
  padding: 0 5px;
  font-size: 11px;
  line-height: 1.6;
  cursor: pointer;
  flex-shrink: 0;
  transition: background .12s, color .12s;
}
.vp-param-copy-btn:hover {
  background: #3b82f6;
  color: #fff;
  border-color: #3b82f6;
}

/* v79: 파라미터 헤더 */
.vp-param-hdr-lbl, .vp-param-hdr-val {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.3px;
  padding: 2px 0;
  border-bottom: 0.5px dashed rgba(59,130,246,.15);
}

/* ═══════════════════════════════════════════════════════════════════════════
 * v82: 좌/우 완전 분리 레이아웃
 * ═══════════════════════════════════════════════════════════════════════════ */

/* 전체 컨테이너 — 그리드 3열: 소스 / 가운데 / 타겟 */
.vp-param-split {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 10px;
  padding: 12px;
  border: 0.5px solid rgba(59,130,246,.2);
  border-radius: 8px;
  background: var(--bg-secondary);
  margin: 6px 0;
}

/* 소스/타겟 각 사이드 박스 */
.vp-param-side {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border-radius: 8px;
  border: 0.5px solid;
  background: var(--bg-primary);
}
.vp-param-side-src {
  border-color: rgba(37,99,235,.35);
  background: linear-gradient(180deg, rgba(37,99,235,.04) 0%, var(--bg-primary) 40%);
}
.vp-param-side-tgt {
  border-color: rgba(22,163,74,.35);
  background: linear-gradient(180deg, rgba(22,163,74,.04) 0%, var(--bg-primary) 40%);
}

/* 사이드 헤더 */
.vp-param-side-hdr {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 8px;
  border-bottom: 0.5px solid rgba(100,100,100,.15);
}
.vp-param-side-ttl {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.3px;
}
.vp-param-side-src .vp-param-side-ttl { color: #2563eb; }
.vp-param-side-tgt .vp-param-side-ttl { color: #16a34a; }

/* 자동 추천 배지 */
.vp-param-auto-badge {
  font-size: 9.5px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 10px;
  background: rgba(22,163,74,.12);
  color: #16a34a;
  border: 0.5px solid rgba(22,163,74,.3);
}

/* 행 리스트 */
.vp-param-rows {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* v82: 한 행 레이아웃 — 라벨 위, 입력칸 아래 (세로형) */
.vp-param-row-v82 {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.vp-param-row-v82 .vp-param-lbl {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding-left: 2px;
}
.vp-param-row-v82 .vp-param-val {
  display: flex;
  align-items: center;
  gap: 5px;
}

/* v82: 확대된 입력칸 — 가로 100%, 세로 28px */
.vp-param-inp-wide {
  flex: 1;
  padding: 6px 10px;
  border: 0.5px solid rgba(59,130,246,.3);
  border-radius: 5px;
  font-size: 13px;
  font-family: var(--font-mono, 'SF Mono', Consolas, monospace);
  background: var(--bg-primary);
  color: var(--text-primary);
  outline: none;
  transition: border-color .12s, box-shadow .12s;
  min-height: 28px;
  letter-spacing: 0.2px;
}
.vp-param-inp-wide:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59,130,246,.12);
}
.vp-param-side-tgt .vp-param-inp-wide {
  border-color: rgba(22,163,74,.3);
}
.vp-param-side-tgt .vp-param-inp-wide:focus {
  border-color: #16a34a;
  box-shadow: 0 0 0 2px rgba(22,163,74,.12);
}

/* OUT 파라미터 표시 */
.vp-param-out-note {
  flex: 1;
  font-size: 11px;
  color: var(--text-tertiary);
  opacity: 0.5;
  font-style: italic;
  padding: 6px 10px;
}

/* 사이드 하단 실행 버튼 */
.vp-param-side-btn {
  margin-top: auto;
  padding: 8px 12px !important;
  font-size: 12px !important;
  font-weight: 600;
  justify-content: center;
}

/* 가운데 영역 */
.vp-param-mid {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-items: center;
  gap: 6px;
  padding: 36px 4px 0 4px;  /* 헤더만큼 여백 */
  min-width: 40px;
}
/* 가운데 복사 버튼 (소스 → 타겟) */
.vp-param-copy-btn-v82 {
  width: 30px;
  height: 30px;
  border: 0.5px solid var(--border-mid);
  background: var(--bg-primary);
  color: var(--text-secondary);
  border-radius: 50%;
  font-size: 15px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all .15s;
}
.vp-param-copy-btn-v82:hover {
  background: #3b82f6;
  color: #fff;
  border-color: #3b82f6;
  transform: scale(1.1);
}
.vp-param-mid-spacer { flex: 1; min-height: 8px; }
.vp-param-mid-btn {
  padding: 8px 10px !important;
  font-size: 11px !important;
  font-weight: 600;
}

/* v82: AI 재이관 버튼 하단 단독 */
.vp-param-ai-row {
  display: flex;
  justify-content: flex-end;
  padding: 8px 2px 0 2px;
  border-top: 0.5px dashed rgba(100,100,100,.15);
  margin-top: 8px;
}

/* 반응형 — 좁은 화면에선 세로 스택 */
@media (max-width: 900px) {
  .vp-param-split {
    grid-template-columns: 1fr;
  }
  .vp-param-mid {
    flex-direction: row;
    padding: 8px 0;
  }
  .vp-param-copy-btn-v82 {
    display: none;  /* 모바일에선 복사 버튼 숨김 */
  }
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
/* ── 재이관 모달 ── */
.vp-remig-overlay{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:9999;display:flex;align-items:center;justify-content:center;padding:20px}
.vp-remig-modal{background:var(--bg-primary);border-radius:14px;width:min(520px,96vw);max-height:86vh;display:flex;flex-direction:column;box-shadow:0 12px 48px rgba(0,0,0,.22);overflow:hidden}
.vp-remig-modal-header{display:flex;align-items:center;gap:10px;padding:14px 18px;border-bottom:0.5px solid var(--border-light);flex-shrink:0}
.vp-remig-modal-icon{font-size:1.2rem;flex-shrink:0}
.vp-remig-modal-title{flex:1;min-width:0}
.vp-remig-modal-name{font-size:.9rem;font-weight:700;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.vp-remig-modal-sub{font-size:.68rem;color:var(--text-tertiary);margin-top:1px}
.vp-remig-modal-close{border:none;background:none;cursor:pointer;color:var(--text-tertiary);font-size:.9rem;padding:4px 8px;border-radius:5px;transition:all .1s;flex-shrink:0}
.vp-remig-modal-close:hover{background:var(--bg-danger);color:var(--text-danger)}
.vp-remig-modal-close:disabled{opacity:.3;cursor:not-allowed}
.vp-remig-modal-diff{display:flex;align-items:center;gap:7px;padding:10px 18px;background:rgba(239,68,68,.04);border-bottom:0.5px solid var(--border-light);font-size:.8rem;flex-shrink:0}
.vp-remig-diff-label{font-size:.68rem;font-weight:600;color:var(--text-tertiary)}
.vp-remig-diff-val{font-weight:700;color:var(--text-primary)}
.vp-remig-diff-bad{color:#dc2626}
.vp-remig-diff-arrow{color:var(--text-tertiary);opacity:.5}
.vp-remig-diff-gap{font-size:.75rem;color:#dc2626;font-weight:600}
.vp-remig-modal-section-label{font-size:.67rem;font-weight:700;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.06em;padding:12px 18px 6px;flex-shrink:0}
.vp-remig-modal-opts{display:flex;flex-direction:column;gap:6px;padding:0 18px 14px;overflow-y:auto;flex:1}
.vp-remig-modal-opt{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:9px;border:1px solid var(--border-light);cursor:pointer;transition:all .12s;background:var(--bg-secondary)}
.vp-remig-modal-opt input{display:none}
.vp-remig-modal-opt.active{border-color:#2563eb;background:rgba(37,99,235,.05)}
.vp-remig-opt-icon{font-size:1.1rem;flex-shrink:0;width:24px;text-align:center}
.vp-remig-opt-body{display:flex;flex-direction:column;gap:2px;flex:1}
.vp-remig-opt-title{font-size:.82rem;font-weight:600;color:var(--text-primary)}
.vp-remig-modal-opt.active .vp-remig-opt-title{color:#1d4ed8}
.vp-remig-opt-desc{font-size:.7rem;color:var(--text-tertiary);line-height:1.4}
.vp-remig-opt-check{font-size:.8rem;color:#2563eb;font-weight:700;flex-shrink:0}

/* ── v37: 재이관 진행 상태 카드 ───────────────────────────────── */
.vp-remig-progress-card{margin:0 18px 12px;padding:16px;border:0.5px solid var(--border-light);border-radius:10px;background:linear-gradient(135deg,#f8fafc 0%,#eff6ff 100%);display:flex;flex-direction:column;gap:12px}
.vp-remig-progress-top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap}
.vp-remig-progress-pct-wrap{display:flex;flex-direction:column;gap:4px}
.vp-remig-progress-pct{font-size:2.2rem;font-weight:700;color:#1e40af;line-height:1;font-family:var(--font);letter-spacing:-1px}
.vp-remig-progress-pct-unit{font-size:1.1rem;font-weight:600;color:#64748b;margin-left:2px}
.vp-remig-progress-status{display:inline-flex;align-items:center;gap:5px;padding:2px 10px;border-radius:99px;font-size:.72rem;font-weight:700;width:fit-content}
.vp-remig-progress-status.running{background:rgba(37,99,235,.15);color:#1d4ed8}
.vp-remig-progress-status.completed{background:rgba(22,163,74,.15);color:#15803d}
.vp-remig-progress-status.error,.vp-remig-progress-status.aborted{background:rgba(220,38,38,.1);color:#dc2626}
.vp-remig-progress-meta{display:flex;flex-direction:column;gap:4px;align-items:flex-end;font-size:.75rem}
.vp-remig-progress-table,.vp-remig-progress-tables{display:flex;gap:6px;align-items:center}
.vp-remig-progress-meta-lbl{color:var(--text-tertiary);font-size:.7rem}
.vp-remig-progress-meta-val{color:var(--text-primary);font-weight:600;font-family:'Consolas',monospace}
.vp-remig-progress-bar-wrap{height:10px;background:rgba(148,163,184,.18);border-radius:99px;overflow:hidden;position:relative}
.vp-remig-progress-bar{height:100%;background:linear-gradient(90deg,#3b82f6 0%,#2563eb 100%);border-radius:99px;transition:width .4s ease-out;position:relative;overflow:hidden}
.vp-remig-progress-bar.completed{background:linear-gradient(90deg,#22c55e 0%,#16a34a 100%)}
.vp-remig-progress-bar.error,.vp-remig-progress-bar.aborted{background:linear-gradient(90deg,#ef4444 0%,#dc2626 100%)}
.vp-remig-progress-bar.running::after{content:'';position:absolute;top:0;left:0;bottom:0;right:0;background:linear-gradient(90deg,transparent,rgba(255,255,255,.35),transparent);animation:vp-remig-shimmer 1.6s linear infinite}
@keyframes vp-remig-shimmer{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}
.vp-remig-progress-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.vp-remig-stat{display:flex;flex-direction:column;gap:3px;padding:8px 10px;background:#ffffff;border:0.5px solid var(--border-light);border-radius:7px}
.vp-remig-stat-lbl{font-size:.65rem;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.3px;font-weight:600}
.vp-remig-stat-val{font-size:.88rem;font-weight:700;color:var(--text-primary);font-family:'Consolas',monospace}
.vp-remig-stat-val.vp-remig-stat-measuring{color:var(--text-tertiary);font-style:italic;font-weight:500;font-size:.78rem}
.vp-remig-progress-rows{text-align:center;padding-top:4px;border-top:0.5px dashed rgba(148,163,184,.3);font-family:'Consolas',monospace;font-size:.8rem}
.vp-remig-progress-rows-done{color:#1e40af;font-weight:700}
.vp-remig-progress-rows-sep{color:var(--text-tertiary)}
.vp-remig-progress-rows-total{color:var(--text-secondary);font-weight:600}
.vp-remig-progress-rows-unit{color:var(--text-tertiary);font-size:.72rem;margin-left:2px}
@media (max-width:640px){.vp-remig-progress-stats{grid-template-columns:repeat(2,1fr)}}

.vp-remig-log-box{margin:0 18px;border:0.5px solid var(--border-light);border-radius:8px;background:var(--bg-secondary);padding:10px 12px;max-height:140px;overflow-y:auto;font-family:'Consolas',monospace;font-size:.72rem;display:flex;flex-direction:column;gap:3px}
.vp-remig-log-line{color:var(--text-secondary);line-height:1.5}
.vp-remig-log-line.log-ok{color:#16a34a;font-weight:600}
.vp-remig-log-line.log-err{color:#dc2626;font-weight:600}
.vp-remig-log-line.log-info{color:#2563eb}
.vp-remig-status-row{display:flex;align-items:center;gap:8px;padding:10px 18px;flex-shrink:0}
.vp-remig-status-badge{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:99px;font-size:.72rem;font-weight:700}
.vp-remig-status-badge.idle{background:var(--bg-secondary);color:var(--text-tertiary)}
.vp-remig-status-badge.running{background:rgba(37,99,235,.15);color:#1d4ed8;border:1px solid rgba(37,99,235,.3)}
.vp-remig-status-badge.completed{background:rgba(22,163,74,.1);color:#15803d}
.vp-remig-status-badge.error{background:rgba(220,38,38,.1);color:#dc2626}
.vp-remig-done-hint{font-size:.68rem;color:var(--text-tertiary);font-style:italic}
/* v45: footer 좌우 분할 — 왼쪽 취소/닫기, 오른쪽 액션 버튼 그룹 (선택→수행) */
.vp-remig-modal-footer{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:12px 18px;border-top:0.5px solid var(--border-light);flex-shrink:0}
.vp-remig-btn-grp{display:inline-flex;gap:8px;align-items:center;margin-left:auto}
.vp-remig-modal-cancel{padding:6px 16px;border-radius:7px;border:0.5px solid var(--border-mid);background:transparent;cursor:pointer;font-size:.8rem;color:var(--text-secondary);font-family:var(--font);transition:all .12s}
.vp-remig-modal-cancel:hover{background:var(--bg-secondary)}
.vp-remig-modal-cancel:disabled{opacity:.4;cursor:not-allowed}
.vp-remig-modal-run{display:inline-flex;align-items:center;gap:6px;padding:6px 20px;border-radius:7px;background:#2563eb;color:#fff;border:none;font-size:.82rem;font-weight:600;cursor:pointer;font-family:var(--font);transition:background .12s}
.vp-remig-modal-run:hover{background:#1d4ed8}
.vp-remig-modal-run:disabled{opacity:.55;cursor:not-allowed}
.vp-remig-modal-run.done{background:#16a34a}
.vp-remig-modal-run.done:hover{background:#15803d}

/* v45: 모달 일시정지 버튼 (노란색 → paused 상태에선 파란색 "계속") */
.vp-remig-btn-pause{
  display:inline-flex;align-items:center;gap:6px;padding:6px 16px;border-radius:7px;
  background:#f59e0b;color:#fff;border:none;
  font-size:.82rem;font-weight:600;cursor:pointer;font-family:var(--font);
  transition:background .12s;
  animation:vp-remig-pause-pulse 1.6s ease-in-out infinite;
}
.vp-remig-btn-pause:hover{background:#d97706;animation:none}
.vp-remig-btn-pause:disabled{opacity:.5;cursor:not-allowed;animation:none}
.vp-remig-btn-pause.paused{
  background:#2563eb;
  animation:vp-remig-resume-pulse 1.4s ease-in-out infinite;
}
.vp-remig-btn-pause.paused:hover{background:#1d4ed8;animation:none}

/* v45: 모달 중단 버튼 (빨간색) */
.vp-remig-btn-stop{
  display:inline-flex;align-items:center;gap:6px;padding:6px 16px;border-radius:7px;
  background:#dc2626;color:#fff;border:none;
  font-size:.82rem;font-weight:600;cursor:pointer;font-family:var(--font);
  transition:background .12s;
}
.vp-remig-btn-stop:hover{background:#b91c1c}
.vp-remig-btn-stop:disabled{opacity:.6;cursor:not-allowed}

@keyframes vp-remig-pause-pulse{
  0%,100%{box-shadow:0 0 0 0 rgba(245,158,11,.50)}
  50%   {box-shadow:0 0 0 6px rgba(245,158,11,0)}
}
@keyframes vp-remig-resume-pulse{
  0%,100%{box-shadow:0 0 0 0 rgba(37,99,235,.50)}
  50%   {box-shadow:0 0 0 6px rgba(37,99,235,0)}
}
@media (prefers-reduced-motion:reduce){
  .vp-remig-btn-pause,.vp-remig-btn-pause.paused{animation:none}
}

.vp-spin{width:12px;height:12px;border:2px solid rgba(37,99,235,.25);border-top-color:#2563eb;border-radius:50%;animation:spin .8s linear infinite;flex-shrink:0}
/* v90.49: schema 정책 표시 바 (검증 & 대사 — 본부장님 결정 2026-04-27) */
.vp-policy-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 8px 12px;
  padding: 8px 12px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.05), rgba(168, 85, 247, 0.05));
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 6px;
  font-size: 12.5px;
}
.vp-policy-icon { font-size: 14px; }
.vp-policy-label { font-weight: 600; color: #4f46e5; }
.vp-policy-select {
  padding: 4px 8px;
  border: 1px solid #c7d2fe;
  border-radius: 5px;
  background: #fff;
  font-size: 12px;
  font-family: inherit;
  color: #1f2937;
  cursor: pointer;
  min-width: 200px;
}
.vp-policy-select:hover { border-color: #818cf8; }
.vp-policy-select:focus { outline: none; border-color: #4f46e5; box-shadow: 0 0 0 2px rgba(99,102,241,0.15); }
.vp-policy-hint {
  font-size: 11px;
  color: #6b7280;
  font-style: italic;
}

</style>
