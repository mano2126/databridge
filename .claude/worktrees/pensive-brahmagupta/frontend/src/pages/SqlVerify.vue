<template>
  <div class="sv-wrap">

    <!-- 미연결 경고 -->
    <div v-if="!connector.bothConnected" class="warn-banner">
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px;flex-shrink:0"><path d="M8 2L14 14H2L8 2z"/></svg>
      소스·타겟 DB 연결이 필요합니다.
      <button class="act-btn" @click="$router.push('/connector')">커넥터 관리 →</button>
    </div>

    <!-- 옵션 바 -->
    <div class="card opt-bar">
      <div class="opt-row">
        <!-- ── DB 소스 박스 ── -->
        <div class="db-box2 src">
          <div class="db-icon-wrap">
            <!-- 실린더 + 공식 DB 로고 겹치기 -->
            <div class="db-cyl-wrap">
              <svg viewBox="0 0 32 32" fill="none" class="db-cyl">
                <ellipse cx="16" cy="9" rx="10" ry="4" fill="rgba(59,130,246,.15)" stroke="#3b82f6" stroke-width="1.3"/>
                <path d="M6 9v14c0 2.2 4.48 4 10 4s10-1.8 10-4V9" fill="rgba(59,130,246,.06)" stroke="#3b82f6" stroke-width="1.3"/>
                <ellipse cx="16" cy="16" rx="10" ry="4" fill="rgba(59,130,246,.06)" stroke="#3b82f6" stroke-width="1" stroke-dasharray="2.5 2"/>
              </svg>
              <!-- DB 공식 로고 -->
              <img :src="dbLogoUrl(connector.source.dbType)" class="db-logo-img" :alt="connector.source.dbType"/>
              <!-- 연결 상태 점 -->
              <span v-if="connector.source.status==='ok'" class="db-online-dot"></span>
            </div>
            <span class="db-label src">소스</span>
          </div>
          <div class="db-info">
            <b class="db-nm2">{{ connector.source.database||'미연결' }}</b>
            <span class="db-tp2">{{ connector.source.dbType }}</span>
          </div>
        </div>
        <div class="db-arrow">
          <svg viewBox="0 0 28 10" fill="none" stroke="var(--text-tertiary)" stroke-width="1.5" style="width:26px;flex-shrink:0">
            <line x1="0" y1="5" x2="22" y2="5"/>
            <polyline points="17,1 23,5 17,9"/>
          </svg>
        </div>
        <!-- ── DB 타겟 박스 ── -->
        <div class="db-box2 tgt">
          <div class="db-icon-wrap">
            <div class="db-cyl-wrap">
              <svg viewBox="0 0 32 32" fill="none" class="db-cyl">
                <ellipse cx="16" cy="9" rx="10" ry="4" fill="rgba(16,185,129,.15)" stroke="#059669" stroke-width="1.3"/>
                <path d="M6 9v14c0 2.2 4.48 4 10 4s10-1.8 10-4V9" fill="rgba(16,185,129,.06)" stroke="#059669" stroke-width="1.3"/>
                <ellipse cx="16" cy="16" rx="10" ry="4" fill="rgba(16,185,129,.06)" stroke="#059669" stroke-width="1" stroke-dasharray="2.5 2"/>
              </svg>
              <img :src="dbLogoUrl(connector.target.dbType)" class="db-logo-img" :alt="connector.target.dbType"/>
              <span v-if="connector.target.status==='ok'" class="db-online-dot"></span>
            </div>
            <span class="db-label tgt">타겟</span>
          </div>
          <div class="db-info">
            <b class="db-nm2">{{ connector.target.database||'미연결' }}</b>
            <span class="db-tp2">{{ connector.target.dbType }}</span>
          </div>
        </div>
        <!-- ── 그룹1: 입력 방식 ── -->
        <div class="opt-group">
          <span class="opt-lbl">입력</span>
          <label class="chip" :class="{on:inputMode==='file'}" @click="inputMode='file'" title="파일 선택">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px"><path d="M2 1h7l3 3v9H2z"/><polyline points="9,1 9,4 12,4"/></svg>
            파일
          </label>
          <label class="chip" :class="{on:inputMode==='folder'}" @click="inputMode='folder'" title="폴더 선택">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px"><path d="M1 3h4l1 2h7v7H1z"/></svg>
            폴더
          </label>
          <label class="chip" :class="{on:inputMode==='text'}" @click="inputMode='text'" title="텍스트 직접 입력">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px"><rect x="1" y="1" width="12" height="12" rx="1"/><line x1="3" y1="5" x2="11" y2="5"/><line x1="3" y1="8" x2="8" y2="8"/></svg>
            텍스트
          </label>
        </div>
        <!-- ── 그룹2: 변환 방식 ── -->
        <div class="opt-group">
          <span class="opt-lbl">변환</span>
          <label class="chip" :class="{on:convMethod==='none'}" @click="convMethod='none'" title="변환 없이 원본 비교">안함</label>
          <label class="chip chip-auto" :class="{on:convMethod==='auto'}" @click="convMethod='auto'" title="규칙 기반 자동 변환">⚡ 자동</label>
          <label class="chip chip-ai" :class="{on:convMethod==='claude'}" @click="convMethod='claude'" title="Claude AI 변환">🤖 AI</label>
        </div>
        <!-- ── 그룹3: 검증 설정 ── -->
        <div class="opt-group">
          <span class="opt-lbl">최대행수</span>
          <select v-model="maxRowsSel" class="sel-sm" @change="onMaxRowsSel">
            <option :value="10">10</option><option :value="50">50</option>
            <option :value="100">100</option><option :value="200">200</option>
            <option :value="500">500</option><option :value="1000">1,000</option>
            <option :value="5000">5,000</option>
            <option :value="10000">10,000</option>
            <option :value="50000">50,000</option>
            <option :value="100000">100,000</option>
            <option :value="999999">MAX (전체)</option>
            <option :value="-1">직접입력...</option>
          </select>
          <input v-if="maxRowsCustom" v-model.number="maxRowsCustomVal"
            type="number" min="1" max="999999" placeholder="행수 입력"
            class="sel-sm" style="width:90px"
            @change="maxRows = maxRowsCustomVal || 200"
            @keyup.enter="maxRows = maxRowsCustomVal || 200"/>
          <span class="opt-lbl" style="margin-left:6px">검증방식</span>
          <select v-model="verifyMode" class="sel-sm sel-verify">
            <option v-for="m in verifyModes" :key="m.key" :value="m.key">{{ m.label }}</option>
          </select>
          <button class="chip chip-norm" :class="{on:showNormPanel}" @click="showNormPanel=!showNormPanel"
            title="소수점·날짜·타입 정규화 옵션">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px"><circle cx="7" cy="7" r="2"/><path d="M7 1v2M7 11v2M1 7h2M11 7h2M3 3l1.4 1.4M9.6 9.6L11 11M3 11l1.4-1.4M9.6 4.4L11 3"/></svg>
            정규화
          </button>
        </div>
        <!-- ── 그룹4: 액션 (완료 후) ── -->
        <template v-if="inputMode!=='text' && doneCount>0 && !running">
          <div class="opt-group">
            <button class="chip chip-report" @click="exportReport('txt')" title="TXT 리포트 다운로드">
              <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px"><path d="M2 1h7l3 3v9H2z"/><line x1="4" y1="7" x2="10" y2="7"/><line x1="4" y1="9" x2="8" y2="9"/></svg>
              리포트
            </button>
            <button class="chip chip-report" @click="exportReport('html')" title="HTML 리포트 다운로드">HTML</button>
            <button class="chip chip-clear" @click="clearAll" title="전체 초기화">
              <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px"><polyline points="3,3 7,7 11,3"/><path d="M7 7v5"/><line x1="2" y1="13" x2="12" y2="13"/></svg>
              Clear
            </button>
          </div>
        </template>
      </div>
    </div>

    <!-- 검증방식 설명 -->
    <transition name="vmode-slide">
      <div v-if="currentVerifyMode" class="vmode-desc-bar">
        <span class="vmode-tag">{{ currentVerifyMode.label }}</span>
        <span class="vmode-hint-text">{{ currentVerifyMode.hint }}</span>
        <div class="vmode-detail">
          <span v-for="(line, i) in currentVerifyMode.details" :key="i" class="vmode-detail-item">
            <svg viewBox="0 0 8 8" fill="none" style="width:6px;height:6px;flex-shrink:0;margin-top:3px">
              <circle cx="4" cy="4" r="2.5" fill="currentColor" opacity=".5"/>
            </svg>
            {{ line }}
          </span>
        </div>
      </div>
    </transition>

    <!-- 정규화 옵션 패널 -->
    <transition name="vmode-slide">
      <div v-if="showNormPanel" class="norm-panel">
        <div class="norm-panel-title">
          <span>타입 정규화 옵션</span>
          <span class="norm-panel-sub">DB간 타입 차이로 인한 불일치를 허용 범위 내에서 흡수합니다</span>
        </div>
        <div class="norm-grid">

          <!-- 소수점 -->
          <div class="norm-group">
            <div class="norm-group-label">
              <label class="norm-chk">
                <input type="checkbox" v-model="normOpts.decimal.enabled"/>
                <span>소수점 처리</span>
              </label>
            </div>
            <div v-if="normOpts.decimal.enabled" class="norm-sub">
              <select v-model="normOpts.decimal.mode" class="sel-sm">
                <option value="round">반올림</option>
                <option value="floor">내림</option>
                <option value="ceil">올림</option>
                <option value="trunc">버림 (소수점 제거)</option>
                <option value="ignore">원본 그대로 (비교 안 함)</option>
                <option value="skip_below">X자리 이하 무시</option>
              </select>
              <select v-if="normOpts.decimal.mode !== 'ignore'" v-model="normOpts.decimal.digits" class="sel-sm" style="width:70px">
                <option v-for="d in [0,1,2,3,4,5,6]" :key="d" :value="d">{{ d }}자리</option>
              </select>
              <span class="norm-hint">
                <template v-if="normOpts.decimal.mode==='skip_below'">예) 4자리 이하 무시 → 503925549.4772 까지만 비교</template>
                <template v-else-if="normOpts.decimal.mode==='ignore'">소수점 전체 무시 → 503925549 만 비교</template>
                <template v-else>예) 503925549.477227 ↔ 503925549.47722787</template>
              </span>
            </div>
          </div>

          <!-- 날짜/시간 -->
          <div class="norm-group">
            <div class="norm-group-label">
              <label class="norm-chk">
                <input type="checkbox" v-model="normOpts.datetime.enabled"/>
                <span>날짜/시간 처리</span>
              </label>
            </div>
            <div v-if="normOpts.datetime.enabled" class="norm-sub">
              <select v-model="normOpts.datetime.mode" class="sel-sm">
                <option value="date">날짜만 비교 (시간 무시)</option>
                <option value="datetime">날짜+시간 비교</option>
                <option value="ym">연월만 비교 (YYYY-MM)</option>
                <option value="year">연도만 비교 (YYYY)</option>
              </select>
              <span class="norm-hint">예) datetime2 ↔ DATETIME 포맷 차이</span>
            </div>
          </div>

          <!-- 문자열 -->
          <div class="norm-group">
            <div class="norm-group-label">
              <label class="norm-chk">
                <input type="checkbox" v-model="normOpts.string.trim"/>
                <span>문자열 후행공백 제거</span>
              </label>
              <label class="norm-chk" style="margin-top:4px">
                <input type="checkbox" v-model="normOpts.string.caseInsensitive"/>
                <span>대소문자 구분 안 함</span>
              </label>
            </div>
            <div class="norm-sub">
              <span class="norm-hint">CHAR(10) 후행공백, NVARCHAR ↔ VARCHAR 차이 흡수</span>
            </div>
          </div>

          <!-- NULL / 빈값 -->
          <div class="norm-group">
            <div class="norm-group-label">
              <label class="norm-chk">
                <input type="checkbox" v-model="normOpts.nullEmpty"/>
                <span>NULL ↔ 빈문자열 동일 처리</span>
              </label>
              <label class="norm-chk" style="margin-top:4px">
                <input type="checkbox" v-model="normOpts.boolInt"/>
                <span>TRUE/FALSE ↔ 1/0 동일 처리</span>
              </label>
            </div>
            <div class="norm-sub">
              <span class="norm-hint">BIT ↔ TINYINT, NULL ↔ '' 차이 흡수</span>
            </div>
          </div>

          <!-- ORDER BY 자동 정렬 -->
          <div class="norm-group" style="grid-column:1/-1">
            <label class="norm-chk">
              <input type="checkbox" v-model="normOpts.autoOrderBy"/>
              <span>ORDER BY 없는 쿼리 자동 정렬</span>
            </label>
            <div class="norm-sub" style="display:flex;flex-direction:column;gap:3px">
              <span class="norm-hint">
                ORDER BY가 없는 SELECT 쿼리는 소스/타겟 DB가 서로 다른 순서로 행을 반환해 집합 비교 시 불일치가 발생할 수 있습니다.
                이 옵션을 켜면 실행 시점에 자동으로 정렬을 추가합니다.
              </span>
              <span class="norm-hint" style="color:var(--text-secondary)">
                · 일반 SELECT → <code>SELECT * FROM (...) ORDER BY 1</code> 로 감싸기
              </span>
              <span class="norm-hint" style="color:var(--text-secondary)">
                · GROUP BY 포함 → GROUP BY 컬럼을 <code>ORDER BY</code> 에 직접 추가
                  <span style="color:#b45309">(서브쿼리 감싸기 시 MySQL strict mode 오류 방지)</span>
              </span>
              <span class="norm-hint" style="color:var(--text-secondary)">
                · 이미 ORDER BY 있는 쿼리 / CALL·SET 구문 → 변경 없음
              </span>
            </div>
          </div>

          <!-- 경계값 허용 -->
          <div class="norm-group" style="grid-column:1/-1">
            <label class="norm-chk">
              <input type="checkbox" v-model="normOpts.boundaryTolerance"/>
              경계값 허용 (TOP/LIMIT 경계 동일값 허용)
            </label>
            <div class="norm-sub" style="display:flex;flex-direction:column;gap:3px">
              <span class="norm-hint">
                소스/타겟이 같은 행수를 가져오지만 <code>TOP N</code> / <code>LIMIT N</code> 경계에서
                <b>동일한 값</b>을 가진 서로 다른 행이 선택된 경우 통과로 처리합니다.
              </span>
              <span class="norm-hint" style="color:var(--text-secondary)">
                · 예) principal_amt=997,000,000 인 고객이 200명 이상일 때 → 소스/타겟이 서로 다른 고객을 반환
              </span>
              <span class="norm-hint" style="color:#059669">
                · 쿼리 변환은 정확하나 데이터 볼륨으로 인한 경계 차이 → 변환 오류 아님
              </span>
            </div>
          </div>

          <!-- 월수 계산 허용 -->
          <div class="norm-group" style="grid-column:1/-1">
            <label class="norm-chk">
              <input type="checkbox" v-model="normOpts.monthTolerance"/>
              월수 계산 허용 (DATEDIFF vs TIMESTAMPDIFF ±1개월)
            </label>
            <div class="norm-sub" style="display:flex;flex-direction:column;gap:3px">
              <span class="norm-hint">
                MSSQL <code>DATEDIFF(MONTH)</code>와 MySQL <code>TIMESTAMPDIFF(MONTH)</code>의
                월말 경계 계산 방식 차이를 <b>±1개월</b> 범위에서 허용합니다.
              </span>
              <span class="norm-hint" style="color:var(--text-secondary)">
                · 예) 실행일 1월31일 → 만기 2월28일: MSSQL=1개월, MySQL=0개월 → 허용
              </span>
            </div>
          </div>

        </div>
        <div class="norm-footer">
          <button class="norm-apply-btn" @click="saveNormOpts">✓ 적용</button>
          <button class="norm-reset-btn" @click="resetNormOpts">초기화</button>
          <span class="norm-status">{{ normStatusText }}</span>
        </div>
      </div>
    </transition>

    <!-- ══ 텍스트 모드 ══ -->
    <template v-if="inputMode==='text'">
      <div class="text-layout">
        <div class="card sql-panel">
          <div class="panel-hdr src">소스 SQL <span class="hdr-db">{{ connector.source.dbType }}</span>
            <button class="hdr-btn" @click="srcSql=''">지우기</button>
          </div>
          <textarea v-model="srcSql" class="sql-ta" placeholder="소스 SQL 붙여넣기..." spellcheck="false" @input="onSrcInput"/>
        </div>
        <div class="text-mid">
          <button class="exec-btn" @click="runText" :disabled="running||!srcSql.trim()||!connector.bothConnected">
            <span v-if="running" class="spinner"></span>
            <svg v-else viewBox="0 0 14 14" fill="none" stroke="white" stroke-width="2" style="width:13px;height:13px"><line x1="2" y1="7" x2="12" y2="7"/><polyline points="8,3 12,7 8,11"/></svg>
            <span style="font-size:9px;font-weight:700">{{ running?'실행중':'실행' }}</span>
          </button>
        </div>
        <div class="card sql-panel">
          <div class="panel-hdr tgt">타겟 SQL <span class="hdr-db">{{ connector.target.dbType }}</span></div>
          <textarea v-model="tgtSql" class="sql-ta" placeholder="타겟 SQL" spellcheck="false"/>
        </div>
      </div>
      <div v-if="convInfo&&convInfo.method!=='none'" class="conv-bar">
        <span class="cv-bd" :class="convInfo.method==='claude-ai'?'ai':'rule'">{{ convInfo.method==='claude-ai'?'✦ Claude AI':'⚙ 규칙' }}</span>
        <span v-for="c in convInfo.changes" :key="c" class="ctag ok">✓ {{ c }}</span>
      </div>
      <div v-if="result" class="result-frame card">
        <div class="res-banner" :class="bannerCls">
          <span class="res-icon">{{ bannerIcon }}</span>
          <div><div class="res-title">{{ bannerTitle }}</div><div class="res-reason">{{ result.comparison.reason }}</div></div>
          <div class="res-stats">
            <div class="stat"><span>소스</span><b>{{ result.src.row_count }}행</b></div>
            <div class="stat"><span>타겟</span><b>{{ result.tgt.row_count }}행</b></div>
          </div>
        </div>
        <ResultTables :result="result" :diffRowSet="diffRowSet" :diffCellMap="diffCellMap"/>
      </div>
    </template>

    <!-- ══ 파일/폴더 모드 ══ -->
    <template v-else>

      <!-- 파일 프레임 (고정 높이, 스크롤) -->
      <div class="file-frames">
        <!-- 소스 -->
        <div class="card file-frame">
          <div class="panel-hdr src">
            소스 ({{ connector.source.dbType }})
            <span v-if="filePairs.length" class="hdr-cnt">{{ srcFiles.length }}개</span>
            <template v-if="filePairs.length">
              <button class="hdr-btn blue" @click="selectAll" title="전체 선택">☑ 전체</button>
              <button class="hdr-btn red" @click="clearSrc">초기화</button>
            </template>
            <button class="hdr-btn" style="margin-left:auto" @click="openSrc">
              {{ inputMode==='folder'?'폴더 선택':'파일 선택' }}
            </button>
          </div>
          <div v-if="!filePairs.length" class="frame-empty" @click="openSrc" @dragover.prevent @drop.prevent="onDrop($event,'src')">
            <svg viewBox="0 0 40 40" fill="none" stroke="currentColor" stroke-width="1.2" style="width:28px;height:28px;color:var(--text-tertiary)">
              <g v-if="inputMode==='folder'"><path d="M4 30V14l6-4h20v20H4z"/><path d="M4 14h26"/></g><g v-else><path d="M8 30V10h16l6 6v14H8z"/><polyline points="24,10 24,16 30,16"/></g>
            </svg>
            <span>{{ inputMode==='folder'?'폴더 선택 또는 드래그':'파일 선택 또는 드래그' }}</span>
          </div>
          <div v-else class="frame-list" ref="srcListEl" @scroll="onSrcScroll" @dragover.prevent @drop.prevent="onDrop($event,'src')">
            <div v-for="(p,i) in filePairs" :key="p.srcName||p.tgtName" class="frow"
                 :class="{active:activePair===i, running:runningIdx===i,
                           'frow-selected':selectedIdxs.has(i),
                           'frow-skip': p.srcOnly||p.tgtOnly}"
                 :data-idx="i"
                 @click="selectPair(i)">
              <label class="frow-chk" @click.stop>
                <input type="checkbox"
                  :checked="selectedIdxs.has(i)"
                  @change="toggleSelect(i)"/>
              </label>
              <span class="frow-num">{{ i+1 }}</span>
              <!-- 소스 파일명 -->
              <span class="frow-name" :title="p.srcName">
                <template v-if="p.tgtOnly">
                  <span class="frow-missing">— 소스 없음</span>
                </template>
                <template v-else>{{ p.srcName }}</template>
              </span>
              <span class="frow-badge" :class="getBadgeClass(i)">{{ getBadgeText(i) }}</span>
            </div>
          </div>
        </div>

        <!-- 타겟 -->
        <div class="card file-frame">
          <div class="panel-hdr tgt">
            타겟 ({{ connector.target.dbType }})
            <span v-if="tgtFiles.length" class="hdr-cnt">{{ tgtFiles.length }}개</span>
            <button v-if="tgtFiles.length" class="hdr-btn red" @click="clearTgt">초기화</button>
            <template v-if="convMethod==='none'">
              <button class="hdr-btn tgt" style="margin-left:auto" @click="openTgt">
                {{ inputMode==='folder'?'폴더 선택':'파일 선택' }}
              </button>
            </template>
          </div>
          <div v-if="convMethod!=='none'" class="frame-auto">
            {{ convMethod==='claude'?'🤖 Claude AI':'⚡ 자동' }} 변환 후 실행
          </div>
          <div v-else-if="!tgtFiles.length" class="frame-empty" @click="openTgt" @dragover.prevent @drop.prevent="onDrop($event,'tgt')">
            <svg viewBox="0 0 40 40" fill="none" stroke="currentColor" stroke-width="1.2" style="width:28px;height:28px;color:var(--text-tertiary)">
              <g v-if="inputMode==='folder'"><path d="M4 30V14l6-4h20v20H4z"/><path d="M4 14h26"/></g><g v-else><path d="M8 30V10h16l6 6v14H8z"/><polyline points="24,10 24,16 30,16"/></g>
            </svg>
            <span>{{ inputMode==='folder'?'폴더 선택 또는 드래그':'파일 선택 또는 드래그' }}</span>
          </div>
          <div v-else class="frame-list" ref="tgtListEl" @scroll="onTgtScroll" @dragover.prevent @drop.prevent="onDrop($event,'tgt')">
            <div v-for="(p,i) in filePairs" :key="p.tgtName||p.srcName" class="frow"
                 :class="{active:activePair===i,
                           'frow-skip': p.srcOnly||p.tgtOnly}"
                 :data-idx="i"
                 @click="selectPair(i)">
              <span class="frow-num">{{ i+1 }}</span>
              <!-- 타겟 파일명 -->
              <span class="frow-name" :title="p.tgtName">
                <template v-if="p.srcOnly">
                  <span class="frow-missing">— 타겟 없음</span>
                </template>
                <template v-else>{{ p.tgtName || '(자동변환)' }}</template>
              </span>
              <span v-if="p.srcOnly||p.tgtOnly" class="frow-badge frow-badge-skip">SKIP</span>
              <span v-else class="frow-badge" :class="getBadgeClass(i)">{{ getBadgeText(i) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- hidden inputs (별도로 분리) -->
      <input ref="srcInp" type="file" style="display:none" @change="onSrcSelect"/>
      <input ref="tgtInp" type="file" style="display:none" @change="onTgtSelect"/>

      <!-- 실행 바 -->
      <div class="card run-bar">
        <div class="run-bar-left">
          <!-- 매핑 현황 요약 -->
          <span class="schip info">{{ filePairs.length }}쌍</span>
          <span v-if="okCount" class="schip ok">✓ {{ okCount }}</span>
          <span v-if="zeroCount" class="schip" style="background:rgba(156,163,175,.15);color:#6b7280">⚠ 0행 {{ zeroCount }}</span>
          <span v-if="failCount" class="schip fail">✗ {{ failCount }}</span>
          <span v-if="reviewedCount()" class="schip reviewed">☑ 검토완료 {{ reviewedCount() }}</span>
          <span v-if="filePairs.length" class="schip" style="background:rgba(99,102,241,.1);color:#4f46e5">
            실질통과 {{ effectivePassCount }}/{{ filePairs.length - skipCount }}
            ({{ filePairs.length - skipCount > 0 ? Math.round(effectivePassCount/(filePairs.length-skipCount)*100) : 0 }}%)
          </span>
          <span v-if="skipCount" class="schip" style="background:rgba(245,158,11,.1);color:#b45309">
            SKIP {{ skipCount }}개
          </span>
          <span v-if="pendCount&&filePairs.length" class="schip pend">대기 {{ pendCount }}</span>
          <!-- 진행바 -->
          <div v-if="filePairs.length" class="prog-wrap">
            <div class="prog-track">
              <div class="prog-ok"  :style="{width:pctOk+'%'}"></div>
              <div class="prog-fail":style="{left:pctOk+'%',width:pctFail+'%'}"></div>
            </div>
            <span class="prog-txt">{{ doneCount }}/{{ filePairs.length }}</span>
          </div>
          <!-- 실행 중 표시 -->
          <span v-if="running" class="run-status" :class="{paused:paused}">
            <span v-if="!paused" class="spinner-sm"></span>
            <span v-else style="font-size:11px">⏸</span>
            {{ paused ? '일시정지됨' : '검증 중' }} {{ runProg }}/{{ filePairs.length }}
          </span>
        </div>
        <div class="run-bar-right">
          <!-- 매핑 현황 토글 -->
          <button v-if="filePairs.length" class="hdr-btn" @click="showMap=!showMap">
            📋 매핑 현황 {{ showMap?'▲':'▼' }}
          </button>
          <!-- Check Sum 패널 토글 -->
          <button v-if="doneCount>0" class="hdr-btn hdr-btn-summary" @click="showSummary=!showSummary"
                  :class="{'summary-active': showSummary}">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:11px;height:11px">
              <rect x="1" y="1" width="12" height="12" rx="1.5"/>
              <line x1="3.5" y1="4.5" x2="6" y2="4.5"/><circle cx="8.5" cy="4.5" r="1.5" fill="currentColor" stroke="none" opacity=".7"/>
              <line x1="3.5" y1="7" x2="6" y2="7"/><circle cx="8.5" cy="7" r="1.5" fill="currentColor" stroke="none" opacity=".7"/>
              <line x1="3.5" y1="9.5" x2="6" y2="9.5"/><circle cx="8.5" cy="9.5" r="1.5" fill="currentColor" stroke="none" opacity=".7"/>
            </svg>
            Check Sum {{ showSummary?'▲':'▼' }}
          </button>
          <!-- 실행 중 컨트롤 버튼 -->
          <template v-if="running">
            <button class="ctrl-btn pause-btn" @click="paused ? unpauseRun() : pauseRun()"
              :title="paused ? '계속 실행' : '일시정지'">
              <span v-if="paused">▶</span>
              <span v-else>⏸</span>
              {{ paused ? '계속' : '일시정지' }}
            </button>
            <button class="ctrl-btn stop-btn" @click="stopRun" title="중지">
              ⏹ 중지
            </button>
            <span class="run-counter">{{ runProg }}/{{ filePairs.length }}</span>
          </template>
          <!-- 대기/완료 상태 버튼 -->
          <template v-else>
            <button v-if="doneCount>0 && doneCount<filePairs.length"
              class="ctrl-btn resume-btn" @click="resumeRun"
              :disabled="!connector.bothConnected" title="이어서 실행">
              ↩ 이어서 실행
            </button>
            <!-- 선택 실행 버튼 -->
            <template v-if="selectedIdxs.size > 0">
              <button class="run-big run-sel" @click="runSelectedPairs"
                :disabled="!connector.bothConnected">
                <svg viewBox="0 0 14 14" fill="none" stroke="white" stroke-width="1.8" style="width:12px;height:12px;flex-shrink:0">
                  <polygon points="3,2 11,7 3,12"/>
                </svg>
                선택 {{ selectedIdxs.size }}개 실행
              </button>
              <button class="ctrl-btn" @click="clearSelect" style="font-size:.68rem">선택 해제</button>
            </template>
            <button class="run-big" @click="runAll"
              :disabled="!filePairs.length||!connector.bothConnected">
              <svg viewBox="0 0 14 14" fill="none" stroke="white" stroke-width="2" style="width:12px;height:12px"><polygon points="2,2 12,7 2,12" fill="white"/></svg>
              {{ doneCount>0 ? '▶ 재실행' : '▶ 쿼리 실행' }}
            </button>
          </template>
        </div>
      </div>

      <!-- 매핑 현황 테이블 (토글) - 가벼운 구조 -->
      <div v-if="showMap && filePairs.length" class="card map-table">
        <div class="mt-hdr">
          <span style="width:28px">#</span>
          <span style="flex:1">소스</span>
          <span style="width:14px"></span>
          <span style="flex:1">타겟</span>
          <span style="width:120px;text-align:center">결과</span>
        </div>
        <div class="mt-body" ref="pairListEl">
          <div v-for="(p,i) in filePairs" :key="p.srcName||p.tgtName"
               class="mt-row" :class="{active:activePair===i, 'mt-row-skip': p.srcOnly||p.tgtOnly}"
               :data-idx="i"
               @click="selectPair(i)">
            <span style="width:28px;color:var(--text-tertiary);font-size:10px">{{ i+1 }}</span>
            <span class="mn src" :title="p.srcName">
              {{ p.srcName || '—' }}
              <span v-if="p.tgtOnly" style="color:#b45309;font-size:9px">⚠ 소스없음</span>
            </span>
            <span style="width:14px;text-align:center;color:var(--text-tertiary);font-size:10px">→</span>
            <span class="mn" :class="p.tgtFile?'tgt':(p.srcOnly?'warn':p.tgtOnly?'warn':'auto')">
              <template v-if="p.srcOnly">⚠ 타겟 파일 없음</template>
              <template v-else-if="p.tgtOnly">— (소스 없음)</template>
              <template v-else>{{ p.tgtFile ? p.tgtName : '자동' }}</template>
            </span>
            <span style="width:140px;text-align:center;display:flex;align-items:center;gap:4px;justify-content:center">
              <span v-if="fileResults[i]" class="rpill"
                :class="isReviewed(i)?'reviewed':(fileResults[i].comparison?.match?'ok':'fail')">
                {{ isReviewed(i)?'☑ 검토완료':(fileResults[i].comparison?.match?'✓ 일치':'✗ '+(fileResults[i].comparison?.reason?.slice(0,14)||'불일치')) }}
              </span>
              <span v-else-if="runningIdx===i" class="rpill run" :class="{paused:paused}">
                {{ paused ? '⏸ 대기' : '▶ 실행 중' }}
              </span>
              <span v-else class="rpill pend">대기</span>
              <!-- 불일치/오류 시 검토완료 체크박스 -->
              <label v-if="fileResults[i] && !fileResults[i].comparison?.match"
                class="review-chk" :title="isReviewed(i)?'검토완료 취소':'검토완료 표시'"
                @click.stop="toggleReviewed(i)">
                <input type="checkbox" :checked="isReviewed(i)" style="display:none"/>
                {{ isReviewed(i)?'✓':'○' }}
              </label>
            </span>
          </div>
        </div>
      </div>

      <!-- ★ Check Sum -->
      <transition name="summary-slide">
        <div v-if="showSummary && doneCount>0" class="checksum-panel">

          <!-- 헤더 -->
          <div class="cs-header">
            <div class="cs-title">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:14px;height:14px;flex-shrink:0">
                <path d="M2 2h12v3H2z" rx="1"/><path d="M2 7h8v2H2z"/><path d="M2 11h5v2H2z"/>
                <circle cx="12.5" cy="12.5" r="2.5" fill="currentColor" opacity=".15"/>
                <circle cx="12.5" cy="12.5" r="2.5"/>
                <line x1="11.5" y1="12.5" x2="13.5" y2="12.5"/><line x1="12.5" y1="11.5" x2="12.5" y2="13.5"/>
              </svg>
              Check Sum
              <span class="cs-subtitle">전체 검증 데이터 합산 비교</span>
            </div>
            <div class="cs-meta">
              <span class="cs-meta-chip">{{ doneCount }}개 파일</span>
              <span class="cs-meta-chip">{{ csSorted.length }}개 항목</span>
              <span v-if="checksumMismatch > 0" class="cs-badge cs-badge-fail">
                <svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.8" style="width:8px;height:8px"><line x1="2" y1="2" x2="8" y2="8"/><line x1="8" y1="2" x2="2" y2="8"/></svg>
                {{ checksumMismatch }}개 불일치
              </span>
              <span v-else class="cs-badge cs-badge-ok">
                <svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="2" style="width:8px;height:8px"><polyline points="1,5 4,8 9,2"/></svg>
                전체 일치
              </span>
            </div>
          </div>

          <!-- 합산 비교 테이블 -->
          <div class="cs-table-wrap">
            <table class="cs-table">
              <thead>
                <tr>
                  <th class="cs-th cs-th-item" @click="csSort('key')">
                    항목 <span class="cs-sico">{{ csSortCol==='key'?(csSortDir==='asc'?'↑':'↓'):'↕' }}</span>
                  </th>
                  <th class="cs-th cs-th-num" @click="csSort('src')">
                    <span class="cs-src-dot"></span>소스 합계 <span class="cs-sico">{{ csSortCol==='src'?(csSortDir==='asc'?'↑':'↓'):'↕' }}</span>
                  </th>
                  <th class="cs-th cs-th-num" @click="csSort('tgt')">
                    <span class="cs-tgt-dot"></span>타겟 합계 <span class="cs-sico">{{ csSortCol==='tgt'?(csSortDir==='asc'?'↑':'↓'):'↕' }}</span>
                  </th>
                  <th class="cs-th cs-th-num cs-th-diff" @click="csSort('diff')">
                    차이 <span class="cs-sico">{{ csSortCol==='diff'?(csSortDir==='asc'?'↑':'↓'):'↕' }}</span>
                  </th>
                  <th class="cs-th cs-th-status" @click="csSort('match')" title="상태로 정렬">
                    <span class="cs-sico" style="font-size:11px">{{ csSortCol==='match'?(csSortDir==='asc'?'↑':'↓'):'⇅' }}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!csSorted.length">
                  <td colspan="5" class="cs-empty">
                    숫자형 데이터가 없거나 검증이 완료되지 않았습니다
                  </td>
                </tr>
                <tr v-for="(row, ri) in csSorted" :key="row.key"
                    class="cs-row" :class="row.match ? 'cs-row-ok' : 'cs-row-fail'">
                  <td class="cs-td cs-td-item">
                    <span class="cs-row-num">{{ ri+1 }}</span>
                    {{ row.key }}
                  </td>
                  <td class="cs-td cs-td-num">{{ fmtNum(row.src) }}</td>
                  <td class="cs-td cs-td-num">{{ fmtNum(row.tgt) }}</td>
                  <td class="cs-td cs-td-diff" :class="row.match ? 'cs-diff-ok' : 'cs-diff-bad'">
                    {{ row.match ? '—' : (row.diff > 0 ? '+' : '') + fmtNum(row.diff) }}
                  </td>
                  <td class="cs-td cs-td-status">
                    <!-- 일치: 초록 체크, 불일치: 빨간 X -->
                    <span class="cs-ico-ok"   v-if="row.match">
                      <svg viewBox="0 0 16 16" fill="none" stroke="#16a34a" stroke-width="2.2" style="width:15px;height:15px">
                        <circle cx="8" cy="8" r="6.5" stroke="#16a34a" stroke-width="1" fill="rgba(34,197,94,.12)"/>
                        <polyline points="4.5,8 7,10.5 11.5,5.5" stroke-linecap="round" stroke-linejoin="round"/>
                      </svg>
                    </span>
                    <span class="cs-ico-fail" v-else>
                      <svg viewBox="0 0 16 16" fill="none" stroke="#dc2626" stroke-width="2" style="width:15px;height:15px">
                        <circle cx="8" cy="8" r="6.5" stroke="#dc2626" stroke-width="1" fill="rgba(239,68,68,.10)"/>
                        <line x1="5.5" y1="5.5" x2="10.5" y2="10.5" stroke-linecap="round"/>
                        <line x1="10.5" y1="5.5" x2="5.5" y2="10.5" stroke-linecap="round"/>
                      </svg>
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </transition>

            <!-- 미실행 파일 선택 시 안내 -->
      <div v-if="!result && activePair >= 0 && filePairs.length" class="card not-run-notice">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px;flex-shrink:0;opacity:.5">
          <circle cx="8" cy="8" r="6.5"/>
          <line x1="8" y1="5" x2="8" y2="8.5"/><circle cx="8" cy="11" r=".6" fill="currentColor"/>
        </svg>
        <span>
          <b>{{ filePairs[activePair]?.srcName }}</b> 파일은 아직 실행되지 않았습니다.
          <span style="color:var(--text-tertiary)">▶ 실행 버튼을 눌러 검증하세요.</span>
        </span>
      </div>

      <!-- 결과 프레임 -->
      <div v-if="result" class="card result-frame">

        <!-- ① 검토완료 바 -->
        <div v-if="!result.comparison?.match" class="review-bar">
          <label class="review-bar-chk" @click.prevent="toggleReviewed(activePair)">
            <input type="checkbox" :checked="isReviewed(activePair)" style="accent-color:#059669;width:14px;height:14px"/>
            <span>{{ isReviewed(activePair) ? '☑ 검토완료 (불일치 인정)' : '○ 검토완료로 표시' }}</span>
          </label>
          <span v-if="isReviewed(activePair)" style="font-size:.72rem;color:#059669;font-style:italic">— 실질 통과로 처리됨</span>
        </div>

        <!-- ② 결과 배너 -->
        <div class="res-banner" :class="bannerCls">
          <span class="res-icon">{{ bannerIcon }}</span>
          <div style="flex:1;min-width:0">
            <div class="res-title">{{ bannerTitle }}</div>
            <div class="res-reason">{{ result.comparison.reason }}</div>
          </div>
          <div class="res-stats">
            <div class="stat"><span>소스</span><b>{{ result.src.row_count }}행</b></div>
            <div class="stat"><span>타겟</span><b>{{ result.tgt.row_count }}행</b></div>
            <div class="stat"><span>소스</span><b>{{ result.src.elapsed_ms }}ms</b></div>
            <div class="stat"><span>타겟</span><b>{{ result.tgt.elapsed_ms }}ms</b></div>
          </div>
          <div v-if="activePair>=0" class="res-fname">{{ filePairs[activePair]?.srcName }}</div>
        </div>

        <!-- ③ 경고/오류 -->
        <div v-if="result.comparison.warning" class="res-warn">⚠ {{ result.comparison.warning }}</div>

        <!-- ★ HINT 진단 패널 -->
        <div v-if="!result.comparison.match" class="hint-panel">
          <div class="hint-panel-hdr">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px">
              <circle cx="8" cy="8" r="6"/><line x1="8" y1="6" x2="8" y2="9"/><circle cx="8" cy="11" r=".6" fill="currentColor"/>
            </svg>
            진단 &amp; 권고사항
          </div>
          <div v-for="(h,hi) in diagnose(result, filePairs[activePair])" :key="hi"
               class="hint-item" :class="'hint-'+h.level">
            <div class="hint-icon">{{ h.icon }}</div>
            <div class="hint-body">
              <div class="hint-title">{{ h.title }}</div>
              <div class="hint-msg">{{ h.msg }}</div>
              <div v-if="h.action" class="hint-action">→ {{ h.action }}</div>
            </div>
          </div>
          <div v-if="!diagnose(result, filePairs[activePair]).length" class="hint-item hint-info">
            <div class="hint-icon">🔍</div>
            <div class="hint-body">
              <div class="hint-msg">불일치 상세 샘플을 확인하여 원인을 파악하세요.</div>
            </div>
          </div>
        </div>
        <!-- 0행 일치 알림 -->
        <div v-if="_isZeroRes" class="res-zero-warn">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"
               style="width:13px;height:13px;flex-shrink:0">
            <path d="M8 2L14 14H2L8 2z"/><line x1="8" y1="7" x2="8" y2="10"/>
            <circle cx="8" cy="12" r=".5" fill="currentColor"/>
          </svg>
          소스/타겟 모두 <b>0행</b>을 반환했습니다.
          쿼리 변환은 일치하나 조건에 해당하는 데이터가 없습니다.
          쿼리 조건(WHERE절)이 올바른지 확인하세요.
        </div>
        <div v-if="result.tgt?.pk_method" class="res-pkinfo">
          🔑 PK 일치 검증 — 소스 {{ result.tgt.pk_count }}행의 <b>{{ result.tgt.pk_col }}</b> 값으로 타겟 재조회
        </div>
        <!-- 소스/타겟 파일 없음 (스킵) -->
        <div v-if="result.comparison?.skipped" class="skip-banner">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"
               style="width:14px;height:14px;flex-shrink:0">
            <path d="M8 2L14 14H2L8 2z"/><line x1="8" y1="7" x2="8" y2="10"/>
            <circle cx="8" cy="12" r=".5" fill="currentColor"/>
          </svg>
          {{ result.comparison.reason }}
          <span style="font-size:.7rem;opacity:.7;margin-left:4px">— 검증 제외됨</span>
        </div>
        <div v-else-if="!result.src.ok||!result.tgt.ok" class="res-err">
          <div v-if="!result.src.ok">소스 오류: {{ result.src.error }}</div>
          <div v-if="!result.tgt.ok">타겟 오류: {{ result.tgt.error }}</div>
        </div>

        <!-- ④ 불일치 상세 — 테이블 형태 -->
        <div v-if="!result.comparison.match && result.comparison.diff_rows?.length" class="diff-section">
          <div class="diff-hdr">
            <span style="font-weight:700;font-size:.8rem">불일치 상세</span>
            <span class="diff-count-badge">{{ result.comparison.diff_rows.length }}개 샘플</span>
            <span class="diff-legend-wrap">
              <span class="dl-dot" style="background:#dc2626"></span>
              <span>소스만 <b style="color:#dc2626">{{ result.comparison.diff_rows.filter(r=>r.type==='src_only').length }}</b></span>
              <span class="dl-dot" style="background:#059669;margin-left:10px"></span>
              <span>타겟만 <b style="color:#059669">{{ result.comparison.diff_rows.filter(r=>r.type==='tgt_only').length }}</b></span>
              <span class="dl-dot" style="background:#f59e0b;margin-left:10px"></span>
              <span>값다름 <b style="color:#b45309">{{ result.comparison.diff_rows.filter(r=>r.type==='both').length }}</b></span>
            </span>
          </div>
          <!-- 불일치 테이블 -->
          <div class="diff-tbl-wrap">
            <table class="diff-tbl">
              <thead>
                <tr>
                  <th class="dt-no">#</th>
                  <th class="dt-type">구분</th>
                  <th v-for="col in diffCols" :key="col" class="dt-col">{{ col }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(dr,di) in result.comparison.diff_rows" :key="di"
                    :class="dr.type==='src_only'?'dt-src':dr.type==='tgt_only'?'dt-tgt':'dt-both'">
                  <td class="dt-no">{{ dr.row }}</td>
                  <td class="dt-type-cell">
                    <span class="dt-badge"
                      :style="dr.type==='src_only'?'background:rgba(220,38,38,.12);color:#dc2626':
                               dr.type==='tgt_only'?'background:rgba(5,150,105,.12);color:#059669':
                               'background:rgba(245,158,11,.12);color:#b45309'">
                      {{ dr.type==='src_only'?'소스전용':dr.type==='tgt_only'?'타겟전용':'값다름' }}
                    </span>
                  </td>
                  <td v-for="col in diffCols" :key="col" class="dt-val"
                      :class="getCellClass(dr, col)">
                    {{ getCellVal(dr, col) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- ⑤ 소스/타겟 결과 테이블 (좌우 스크롤) -->
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
                  <tr v-for="(row,ri) in pagedRows(side)" :key="ri"
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
            <!-- 더보기 -->
            <div v-if="hasMore(side)" class="tbl-load-more">
              <button class="load-more-btn" @click="loadMore(side)">
                {{ pagedRows(side).length }}행 표시 중 /
                전체 {{ result[side].row_count }}행
                — 100행 더 보기
              </button>
            </div>
            <div v-else-if="result[side].rows?.length > PAGE_SIZE" class="tbl-all-shown">
              전체 {{ result[side].row_count }}행 표시 완료
            </div>
          </div>
        </div>

      </div>

    </template>

  </div>
</template>

<script setup>
// keep-alive 캐시 대상 지정용 컴포넌트 이름
defineOptions({ name: 'SqlVerify' })
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { useVerifyStore } from '@/store/verifyStore.js'
import axios from 'axios'
import { useConnectorStore } from '@/store/connectorStore.js'

const connector  = useConnectorStore()
const vStore     = useVerifyStore()

// ── store 상태 (페이지 이동해도 유지) ────────────────────
// srcFiles/tgtFiles: store에서 관리 → 라우터 이동 후 복귀해도 파일 목록/결과 그대로 유지
const srcFiles    = computed({ get: () => vStore.srcFiles,  set: v => vStore.srcFiles  = v })
const tgtFiles    = computed({ get: () => vStore.tgtFiles,  set: v => vStore.tgtFiles  = v })
const fileResults = computed({ get: () => vStore.fileResults, set: v => vStore.fileResults = v })
const activePair  = computed({ get: () => vStore.activePair,  set: v => vStore.activePair = v })
const running     = computed(() => vStore.running)
const paused      = computed(() => vStore.paused)
const runningIdx  = computed(() => vStore.runningIdx)
const runProg     = computed(() => vStore.runProg)
const convMethod  = computed({ get: () => vStore.convMethod,  set: v => { vStore.convMethod = v; localStorage.setItem('sv_method', v) }})
const maxRows     = computed({ get: () => vStore.maxRows,     set: v => vStore.maxRows = v })
const maxRowsSel  = ref(vStore.maxRows)  // select 바인딩용
const maxRowsCustom = ref(false)         // 직접입력 모드
const maxRowsCustomVal = ref(vStore.maxRows)

function onMaxRowsSel(e) {
  const v = Number(e.target.value)
  if (v === -1) {
    maxRowsCustom.value = true
    maxRowsSel.value = -1
  } else {
    maxRowsCustom.value = false
    maxRows.value = v
    maxRowsSel.value = v
  }
}

// maxRows 변경 시 select 동기화
watch(() => vStore.maxRows, v => {
  if (v !== maxRowsSel.value && maxRowsSel.value !== -1) maxRowsSel.value = v
})

// ── 검증 방식 ──────────────────────────────────────────────
const verifyMode = computed({
  get: () => vStore.verifyMode,
  set: v => { vStore.verifyMode = v; localStorage.setItem('sv_verify_mode', v) }
})

const verifyModes = [
  {
    key:    'pk_match',
    label:  'PK 일치 \u2605\u2605 최강',
    hint:   '소스 PK로 타겟을 정확히 찾아서 비교 \u2014 TOP N 동점 문제 완전 해소',
    details: [
      '소스에서 MAX행수만큼 읽고 PK 컬럼(xxx_id, xxx_no)을 자동 탐지합니다',
      '타겟은 소스 PK 값으로 WHERE pk IN (...) 재조회 \u2014 완전히 같은 행만 비교',
      'TOP 200 동점으로 서로 다른 행이 뽑히던 문제를 근본적으로 해소합니다',
      '적합: 이관 검증 최우선 방식 · PK가 있는 모든 테이블/쿼리',
    ],
  },
  {
    key:    'order',
    label:  '순서 일치',
    hint:   '행 순서까지 완전히 같아야 통과 \u2014 가장 엄격',
    details: [
      '소스·타겟의 행을 위치 그대로 1:1 비교합니다',
      'ORDER BY 절이 완전히 동일한 경우에만 사용하세요',
      '정렬이 조금만 달라도 불일치로 판정됩니다',
      '적합: 동일한 ORDER BY가 보장된 단순 변환 검증',
    ],
  },
  {
    key:    'set',
    label:  '집합 비교 \u2605 권장',
    hint:   '순서 무관 · 데이터 집합이 같으면 통과 · MSSQL\u2194MySQL 정렬 차이 자동 허용',
    details: [
      '행 순서를 무시하고 데이터 집합 자체를 비교합니다',
      'MSSQL\u2194MySQL 간 정렬 기준 차이를 자동으로 허용합니다',
      '소수점·후행공백·날짜포맷 등 타입 표현 차이도 정규화해서 비교합니다',
      '적합: 대부분의 이관 검증에 권장하는 기본 방식',
    ],
  },
  {
    key:    'col_sort',
    label:  '컬럼 정렬 비교',
    hint:   '컬럼별 값을 정렬 후 비교 · 행 순서 완전 무관 · 소량(10/50행) 정밀 검증',
    details: [
      '각 컬럼의 값 목록을 정렬한 후 비교합니다 — 행 순서가 달라도 같은 값이면 통과',
      'ORDER BY 차이, 동순위 처리 방식 등 DB 엔진 차이를 완전히 무시합니다',
      '최대행수를 10~50으로 줄이고 사용하면 정확한 변환 오류를 검출할 수 있습니다',
      '적합: ORDER BY 노이즈를 완전히 제거하고 값 자체만 비교하고 싶을 때',
    ],
  },
  {
    key:    'checksum',
    label:  '체크섬',
    hint:   '전체 데이터를 해시 하나로 압축 비교 \u2014 빠르지만 어디가 다른지 알 수 없음',
    details: [
      '모든 행의 값을 MD5 해시 하나로 압축해서 비교합니다',
      '일치/불일치 여부만 알 수 있고 어느 행이 다른지는 모릅니다',
      '수백만 행도 수초 안에 검증 가능 \u2014 속도가 가장 빠릅니다',
      '적합: 대용량 테이블 빠른 1차 확인 · 전수 검증 전 스크린',
    ],
  },
  {
    key:    'hash_row',
    label:  '행 해시',
    hint:   '각 행을 해시로 비교 \u2014 어느 행이 다른지 특정 가능 · 대용량에 적합',
    details: [
      '각 행마다 해시값을 계산해서 소스\u2194타겟을 비교합니다',
      '어느 행이 다른지 정확히 찾아낼 수 있습니다',
      '체크섬보다 느리지만 집합비교보다 메모리 효율적입니다',
      '적합: 대용량 테이블에서 불일치 행을 정확히 찾을 때',
    ],
  },
  {
    key:    'column_stats',
    label:  '컬럼 통계',
    hint:   'MIN · MAX · AVG · NULL수를 컬럼별로 비교 \u2014 데이터 품질 검증에 특화',
    details: [
      '각 컬럼의 MIN, MAX, AVG, NULL 개수를 비교합니다',
      '행 단위가 아닌 컬럼 단위로 데이터 분포를 검증합니다',
      '금액·날짜·비율 등 수치 컬럼의 이상 여부를 빠르게 확인합니다',
      '적합: 이관 후 데이터 품질 점검 · 컬럼 범위 이상 감지',
    ],
  },
]

const currentVerifyMode = computed(() =>
  verifyModes.find(m => m.key === verifyMode.value) || null
)
const EM_DASH = '\u2014'

// ── 불일치 테이블 헬퍼 ───────────────────────────────────────
const diffCols = computed(() => {
  if (!result.value?.comparison?.diff_rows?.length) return []
  const cols = new Set()
  result.value.comparison.diff_rows.forEach(dr => {
    ;(dr.diffs || []).forEach(d => cols.add(d.col_src || d.col_tgt))
  })
  return [...cols]
})

function getCellVal(dr, col) {
  const d = (dr.diffs || []).find(x => (x.col_src || x.col_tgt) === col)
  if (!d) return ''
  if (dr.type === 'src_only') return d.src ?? EM_DASH
  if (dr.type === 'tgt_only') return d.tgt ?? EM_DASH
  // 값다름: 소스→타겟
  return (d.src ?? EM_DASH) + ' \u2192 ' + (d.tgt ?? EM_DASH)
}

function getCellClass(dr, col) {
  const d = (dr.diffs || []).find(x => (x.col_src || x.col_tgt) === col)
  if (!d) return ''
  if (d.src === EM_DASH || d.src == null) return 'dt-missing'
  if (d.tgt === EM_DASH || d.tgt == null) return 'dt-extra'
  return 'dt-changed'
}

const filePairs   = computed(() => vStore.buildPairs(srcFiles.value, tgtFiles.value))
const reviewed    = vStore.reviewed
const doneCount   = computed(() => vStore.doneCount)
const okCount     = computed(() => vStore.okCount)
const failCount   = computed(() => vStore.failCount)
const skipCount   = computed(() => vStore.skipCount)
const zeroCount   = computed(() => fileResults.value.filter(r =>
  r?.comparison?.match && r?.src?.row_count === 0 && r?.tgt?.row_count === 0
).length)
const reviewedCount  = () => vStore.reviewedCount.value
const effectivePassCount = computed(() => vStore.effectivePassCount)
function toggleReviewed(i) { vStore.toggleReviewed(i) }
function isReviewed(i)     { return vStore.isReviewed(i) }

const inputMode  = ref('file')

// ── 선택 재실행 ───────────────────────────────────────────────
const selectedIdxs = computed(() => vStore.selectedIdxs)

function toggleSelect(i) {
  const s = new Set(vStore.selectedIdxs)
  if (s.has(i)) s.delete(i)
  else s.add(i)
  vStore.selectedIdxs = s
}
function selectAll() {
  vStore.selectedIdxs = new Set(filePairs.value.map((_,i) => i))
}
function clearSelect() {
  vStore.selectedIdxs = new Set()
}
async function runSelectedPairs() {
  if (!vStore.selectedIdxs.size) return
  const idxArr = [...vStore.selectedIdxs].sort((a,b)=>a-b)
  await vStore.runSelected(srcPlain(), tgtPlain(), new Set(vStore.selectedIdxs), filePairs.value)
  // 선택 실행 완료 후 마지막 선택 파일 결과 표시
  const lastIdx = idxArr[idxArr.length - 1]
  if (lastIdx >= 0 && vStore.fileResults[lastIdx]) {
    vStore.activePair = lastIdx
    result.value = vStore.fileResults[lastIdx]
  }
}

function srcPlain() {
  const s = connector.source
  return { db_type:s.dbType, host:s.host, port:Number(s.port)||0, database:s.database, username:s.username, password:s.password||'' }
}
function tgtPlain() {
  const t = connector.target
  return { db_type:t.dbType, host:t.host, port:Number(t.port)||0, database:t.database, username:t.username, password:t.password||'' }
}

// ── 텍스트 모드 ──────────────────────────────────────────
const srcSql   = ref('')
const tgtSql   = ref('')
const result   = ref(null)
const convInfo = ref(null)

let cvTimer = null
function onSrcInput() {
  if (convMethod.value === 'none') return
  clearTimeout(cvTimer); cvTimer = setTimeout(convertOnly, 800)
}
async function convertOnly() {
  if (!srcSql.value.trim()) return
  try {
    const ep = convMethod.value === 'claude' ? '/api/v1/sql-converter/convert-ai' : '/api/v1/sql-converter/convert'
    const { data } = await axios.post(ep, { sql:srcSql.value, src_db:connector.source.dbType, tgt_db:connector.target.dbType })
    tgtSql.value = data.converted || srcSql.value
    convInfo.value = data
  } catch {}
}
async function runText() {
  if (!srcSql.value.trim() || !connector.bothConnected) return
  running.value = true; result.value = null
  if (convMethod.value !== 'none' && !tgtSql.value.trim()) await convertOnly()
  try {
    const { data } = await axios.post('/api/v1/sql-converter/compare', {
      src_sql:srcSql.value, tgt_sql:tgtSql.value||srcSql.value,
      src_conn:srcPlain(), tgt_conn:tgtPlain(), max_rows:maxRows.value,
    })
    result.value = data
      dispPage.value = {src:1, tgt:1}
  } catch(e) {
    result.value = { src:{ok:false,error:e.message,row_count:0,cols:[],rows:[],elapsed_ms:0},
                    tgt:{ok:false,error:e.message,row_count:0,cols:[],rows:[],elapsed_ms:0},
                    comparison:{match:false,reason:'오류: '+e.message} }
  } finally { running.value = false }
}

// ── 파일 선택 (input 완전 분리) ─────────────────────────
const srcInp    = ref(null)
const tgtInp    = ref(null)
const srcListEl = ref(null)   // 소스 목록 스크롤 컨테이너
const tgtListEl = ref(null)   // 타겟 목록 스크롤 컨테이너
const pairListEl = ref(null)  // 결과 매핑 목록 스크롤 컨테이너

// ── 자동 스크롤: 실행 중 항목을 화면 하단에 표시, 소스/타겟 동기화 ──
watch(runningIdx, (idx) => {
  if (idx < 0) return
  nextTick(() => {
    // 소스 기준으로 scrollTop 계산 → 소스/타겟 동일 적용
    const scrollTop = calcScrollTop(srcListEl.value, idx)
      ?? calcScrollTop(tgtListEl.value, idx)
      ?? null

    if (scrollTop !== null) {
      // 소스/타겟 완전 동기화 (같은 scrollTop)
      syncScroll(srcListEl.value,  scrollTop)
      syncScroll(tgtListEl.value,  scrollTop)
    }
    // 결과 매핑 목록은 별도 (구조가 다를 수 있음)
    const pairTop = calcScrollTop(pairListEl.value, idx)
    if (pairTop !== null) syncScroll(pairListEl.value, pairTop)
  })
})

// 현재 행이 컨테이너 맨 아래에 보이도록 scrollTop 계산
function calcScrollTop(container, idx) {
  if (!container) return null
  const row = container.querySelector(`[data-idx="${idx}"]`)
  if (!row) return null

  const rowH = row.offsetHeight || 32
  // offsetTop은 부모(frame-list) 기준 → 그게 곧 스크롤 기준
  // 단, 컨테이너 안에 헤더 등 다른 요소가 있을 경우를 위해
  // container 상단으로부터의 실제 거리를 계산
  const containerRect = container.getBoundingClientRect()
  const rowRect       = row.getBoundingClientRect()
  // 현재 스크롤 위치 기준 행의 절대 위치
  const rowAbsTop = container.scrollTop + (rowRect.top - containerRect.top)
  // 목표: 행 하단이 컨테이너 하단에 딱 붙게
  const target = rowAbsTop + rowH - container.clientHeight + 4
  return Math.max(0, target)
}

// 부드럽게 스크롤 적용
function syncScroll(container, scrollTop) {
  if (!container) return
  // 현재 위치와 많이 차이날 때만 스크롤
  if (Math.abs(container.scrollTop - scrollTop) > 5) {
    container.scrollTo({ top: scrollTop, behavior: 'smooth' })
  }
}

// 사용자가 소스 목록을 수동 스크롤하면 타겟도 동기화
let _userScrolling = false
function onSrcScroll(e) {
  if (_userScrolling) return
  _userScrolling = true
  if (tgtListEl.value) tgtListEl.value.scrollTop = e.target.scrollTop
  requestAnimationFrame(() => { _userScrolling = false })
}
function onTgtScroll(e) {
  if (_userScrolling) return
  _userScrolling = true
  if (srcListEl.value) srcListEl.value.scrollTop = e.target.scrollTop
  requestAnimationFrame(() => { _userScrolling = false })
}

// inputMode에 따라 input 속성 설정 후 클릭
function openSrc() {
  const el = srcInp.value
  if (!el) return
  el.removeAttribute('webkitdirectory')
  el.removeAttribute('multiple')
  el.removeAttribute('accept')
  if (inputMode.value === 'folder') {
    el.setAttribute('webkitdirectory', '')
  } else {
    el.setAttribute('multiple', '')
    el.setAttribute('accept', '.sql,.txt')
  }
  el.value = ''
  // setTimeout으로 현재 이벤트 루프 완료 후 클릭 → UI 블로킹 방지
  setTimeout(() => el.click(), 50)
}
function openTgt() {
  const el = tgtInp.value
  if (!el) return
  el.removeAttribute('webkitdirectory')
  el.removeAttribute('multiple')
  el.removeAttribute('accept')
  if (inputMode.value === 'folder') {
    el.setAttribute('webkitdirectory', '')
  } else {
    el.setAttribute('multiple', '')
    el.setAttribute('accept', '.sql,.txt')
  }
  el.value = ''
  setTimeout(() => el.click(), 50)
}

// 파일 목록 처리 - 가능한 빠르게
function toList(files) {
  const list = []
  const ext = /\.(sql|txt)$/i
  for (const f of files) {
    if (!ext.test(f.name)) continue
    // 폴더 모드: 최상위 파일만 (depth 1)
    if (f.webkitRelativePath && f.webkitRelativePath.split('/').length > 2) continue
    list.push({ name:f.name, size:f.size, file:f })
    if (list.length >= 200) break
  }
  return list
}

const showMap      = ref(false)
const showNormPanel = ref(false)
const showSummary   = ref(false)

// ── Check Sum 정렬 상태 ──────────────────────────────────────
const csSortCol = ref('key')   // key | src | tgt | diff | match
const csSortDir = ref('asc')

function csSort(col) {
  if (csSortCol.value === col) {
    csSortDir.value = csSortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    csSortCol.value = col
    csSortDir.value = col === 'match' ? 'asc' : 'desc'  // 상태는 불일치 먼저
  }
}

// 정렬된 Check Sum 행
const csSorted = computed(() => {
  const list = [...checksumRows.value]
  const col = csSortCol.value
  const dir = csSortDir.value === 'asc' ? 1 : -1
  list.sort((a, b) => {
    let av = a[col], bv = b[col]
    if (col === 'match') { av = a.match ? 1 : 0; bv = b.match ? 1 : 0 }
    if (col === 'key') return String(av).localeCompare(String(bv)) * dir
    return ((av ?? 0) - (bv ?? 0)) * dir
  })
  return list
})

// ── Check Sum 합산 비교 ─────────────────────────────────────
// fileResults 의 모든 파일 rows를 합산 → 항목별 src합계 vs tgt합계
const checksumRows = computed(() => {
  const srcSum = {}  // key → 합계
  const tgtSum = {}

  fileResults.value.forEach(r => {
    if (!r || r.comparison?.skipped || !r.src?.ok || !r.tgt?.ok) return

    // 소스 rows 합산
    if (r.src.cols?.length >= 2 && r.src.rows?.length) {
      // col 0 = 항목명, col 1 = 값  (metric/val 구조)
      // 또는 단순 숫자 컬럼이면 컬럼명이 key
      const isKV = r.src.cols.length === 2  // metric | val 구조
      if (isKV) {
        r.src.rows.forEach(row => {
          const key = String(row[0] ?? '')
          const val = Number(String(row[1] ?? '').replace(/,/g, ''))
          if (key && !isNaN(val)) {
            srcSum[key] = (srcSum[key] || 0) + val
          }
        })
      } else {
        // 다중 컬럼: 숫자 컬럼만 합산
        r.src.cols.forEach((col, ci) => {
          r.src.rows.forEach(row => {
            const val = Number(String(row[ci] ?? '').replace(/,/g, ''))
            if (!isNaN(val) && val !== 0) {
              srcSum[col] = (srcSum[col] || 0) + val
            }
          })
        })
      }
    }

    // 타겟 rows 합산
    if (r.tgt.cols?.length >= 2 && r.tgt.rows?.length) {
      const isKV = r.tgt.cols.length === 2
      if (isKV) {
        r.tgt.rows.forEach(row => {
          const key = String(row[0] ?? '')
          const val = Number(String(row[1] ?? '').replace(/,/g, ''))
          if (key && !isNaN(val)) {
            tgtSum[key] = (tgtSum[key] || 0) + val
          }
        })
      } else {
        r.tgt.cols.forEach((col, ci) => {
          r.tgt.rows.forEach(row => {
            const val = Number(String(row[ci] ?? '').replace(/,/g, ''))
            if (!isNaN(val) && val !== 0) {
              tgtSum[col] = (tgtSum[col] || 0) + val
            }
          })
        })
      }
    }
  })

  // 소스+타겟 키 합집합 → 비교 행 생성
  const allKeys = new Set([...Object.keys(srcSum), ...Object.keys(tgtSum)])
  return [...allKeys].sort().map(key => {
    const s = srcSum[key] ?? 0
    const t = tgtSum[key] ?? 0
    // 부동소수점 오차 방지: 소수점 6자리 반올림 후 비교
    const rounded_s = Math.round(s * 1e6) / 1e6
    const rounded_t = Math.round(t * 1e6) / 1e6
    const diff = rounded_t - rounded_s
    return { key, src: s, tgt: t, diff, match: Math.abs(diff) < 1e-9 }
  })
})

const checksumMismatch = computed(() => checksumRows.value.filter(r => !r.match).length)

function fmtNum(n) {
  if (n == null) return '—'
  if (!isFinite(n)) return String(n)
  // 소수점 있으면 최대 2자리
  const abs = Math.abs(n)
  if (abs > 0 && abs < 1) return n.toFixed(4)
  if (Number.isInteger(n)) return n.toLocaleString('ko-KR')
  return n.toLocaleString('ko-KR', { maximumFractionDigits: 2 })
}

// ── Check Sum 헬퍼 ──────────────────────────────────────────
function getSumClass(i) {
  const r = fileResults.value[i]
  if (!r) return runningIdx.value === i ? 'sum-running' : 'sum-pending-card'
  if (r.comparison?.skipped) return 'sum-skip'
  if (isReviewed(i)) return 'sum-reviewed'
  if (r.comparison?.match) {
    return r.comparison.warning ? 'sum-warn' : 'sum-ok'
  }
  if (!r.src?.ok || !r.tgt?.ok) return 'sum-error'
  return 'sum-fail'
}

function getSumIcon(i) {
  const r = fileResults.value[i]
  if (!r) return runningIdx.value === i ? '▶' : '○'
  if (r.comparison?.skipped) return '—'
  if (isReviewed(i)) return '☑'
  if (r.comparison?.match) return r.comparison.warning ? '⚠' : '✓'
  if (!r.src?.ok || !r.tgt?.ok) return '🔴'
  return '✗'
}

function getSumBadgeCls(i) {
  const r = fileResults.value[i]
  if (!r) return 'sbdg-pend'
  if (r.comparison?.skipped) return 'sbdg-skip'
  if (isReviewed(i)) return 'sbdg-reviewed'
  if (r.comparison?.match) return r.comparison.warning ? 'sbdg-warn' : 'sbdg-ok'
  if (!r.src?.ok || !r.tgt?.ok) return 'sbdg-error'
  return 'sbdg-fail'
}

function getSumBadgeText(i) {
  const r = fileResults.value[i]
  if (!r) return runningIdx.value === i ? '실행 중' : '대기'
  if (r.comparison?.skipped) return 'SKIP'
  if (isReviewed(i)) return '검토완료'
  if (r.comparison?.match) return r.comparison.warning ? '일치(정렬차이)' : '완전 일치'
  if (!r.src?.ok || !r.tgt?.ok) return '오류'
  const reason = r.comparison?.reason || ''
  if (reason.includes('행수')) return '행수 불일치'
  if (reason.includes('값')) return '값 불일치'
  return '불일치'
}

// 배너 스택용 — 이미지의 "데이터 일치 (정렬 차이)" 스타일 그대로
function getSumBannerCls(i) {
  const r = fileResults.value[i]
  if (!r) return runningIdx.value === i ? 'sbanner-run' : 'sbanner-pend'
  if (r.comparison?.skipped) return 'sbanner-skip'
  if (isReviewed(i)) return 'sbanner-reviewed'
  if (r.comparison?.match) return r.comparison.warning ? 'sbanner-warn' : 'sbanner-ok'
  if (!r.src?.ok || !r.tgt?.ok) return 'sbanner-error'
  return 'sbanner-fail'
}

function getSumBannerTitle(i) {
  const r = fileResults.value[i]
  if (!r) return runningIdx.value === i ? '실행 중...' : '대기'
  if (r.comparison?.skipped) return 'SKIP — ' + (r.comparison.reason || '')
  if (isReviewed(i)) return '검토완료 (불일치 인정)'
  if (!r.src?.ok || !r.tgt?.ok) return '실행 오류'
  if (r.comparison?.match) return r.comparison.warning ? '데이터 일치 (정렬 차이)' : '결과 완전 일치'
  const rc = r.src?.row_count, rt = r.tgt?.row_count
  if (rc !== undefined && rt !== undefined && rc !== rt) return '행수 불일치'
  return '결과 불일치'
}

// ── 전체결과 패널용 — result-frame 의 bannerCls/Icon/Title 과 동일 로직 ──
function rBannerCls(r) {
  if (!r?.comparison) return 'diff'
  const isZero = r.comparison.match && r.src?.row_count === 0 && r.tgt?.row_count === 0
  if (isZero) return 'zero'
  return r.comparison.match ? (r.comparison.warning ? 'warn' : 'match') : 'diff'
}
function rBannerIcon(r) {
  if (!r?.comparison) return '✗'
  const isZero = r.comparison.match && r.src?.row_count === 0 && r.tgt?.row_count === 0
  if (isZero) return '⚠'
  return r.comparison.match ? (r.comparison.warning ? '⚠' : '✓') : '✗'
}
function rBannerTitle(r) {
  if (!r?.comparison) return ''
  const isZero = r.comparison.match && r.src?.row_count === 0 && r.tgt?.row_count === 0
  if (isZero) return '데이터 없음 (0행 일치)'
  return r.comparison.match ? (r.comparison.warning ? '데이터 일치 (정렬 차이)' : '결과 완전 일치') : '결과 불일치'
}

// ── 정규화 옵션 ───────────────────────────────────────────────
const NORM_KEY = 'sv_norm_opts'
const defaultNorm = () => ({
  decimal:   { enabled: true,  mode: 'round', digits: 4 },
  datetime:  { enabled: true,  mode: 'date' },
  string:    { trim: true, caseInsensitive: false },
  nullEmpty: true,
  boolInt:   false,
  autoOrderBy: true,       // ORDER BY 없는 쿼리 자동 정렬
  boundaryTolerance: true, // 경계값 허용 (TOP/LIMIT 경계에서 동일값 다른 행)
  monthTolerance: false,   // 월수 계산 허용 (DATEDIFF vs TIMESTAMPDIFF ±1개월)
})
let _savedNorm = defaultNorm()
try {
  const _p = JSON.parse(localStorage.getItem(NORM_KEY))
  if (_p) {
    // 새로 추가된 키는 defaultNorm 값으로 채움 (마이그레이션)
    const _def = defaultNorm()
    _savedNorm = { ..._def, ..._p }
  }
} catch {}
const normOpts = reactive(_savedNorm)

function saveNormOpts() {
  localStorage.setItem(NORM_KEY, JSON.stringify({ ...normOpts }))
  vStore.normOpts = JSON.parse(JSON.stringify({ ...normOpts }))
  showNormPanel.value = false
}
function resetNormOpts() {
  const d = defaultNorm()
  normOpts.decimal  = { ...d.decimal }
  normOpts.datetime = { ...d.datetime }
  normOpts.string   = { ...d.string }
  normOpts.nullEmpty = d.nullEmpty
  normOpts.boolInt   = d.boolInt
  vStore.normOpts = JSON.parse(JSON.stringify({ ...normOpts }))
}
vStore.normOpts = JSON.parse(JSON.stringify({ ...normOpts }))

const DECIMAL_MODE_LABEL = {
  round: '반올림', floor: '내림', ceil: '올림', trunc: '버림',
  ignore: '소수점무시', skip_below: 'X자리이하무시'
}
const DATETIME_MODE_LABEL = {
  date: '날짜만(시간무시)', datetime: '날짜+시간', ym: '년월', year: '년도'
}
const normStatusText = computed(() => {
  const parts = []
  if (normOpts.decimal?.enabled) {
    const ml = DECIMAL_MODE_LABEL[normOpts.decimal.mode] || normOpts.decimal.mode
    const dig = normOpts.decimal.mode !== 'ignore' ? ` ${normOpts.decimal.digits}자리` : ''
    parts.push(`소수점: ${ml}${dig}`)
  }
  if (normOpts.datetime?.enabled) {
    const dl = DATETIME_MODE_LABEL[normOpts.datetime.mode] || normOpts.datetime.mode
    parts.push(`날짜: ${dl}`)
  }
  if (normOpts.string?.trim)             parts.push('공백제거')
  if (normOpts.string?.caseInsensitive)  parts.push('대소문자무시')
  if (normOpts.nullEmpty)                parts.push('NULL=빈값')
  if (normOpts.boolInt)                  parts.push('BOOL=INT')
  if (normOpts.autoOrderBy)                parts.push('자동정렬')
  if (normOpts.boundaryTolerance)          parts.push('경계값허용')
  if (normOpts.monthTolerance)             parts.push('월수±1허용')
  return parts.length ? '적용중: ' + parts.join(' · ') : '기본값'
})

function onSrcSelect(e) {
  const list = toList(e.target.files)
  e.target.value = ''
  srcFiles.value = list          // 로컬 ref 직접 할당
  tgtFiles.value = []
  vStore.fileResults = []
  vStore.activePair = -1
  result.value = null
}
function onTgtSelect(e) {
  const list = toList(e.target.files)
  e.target.value = ''
  tgtFiles.value = list          // 로컬 ref 직접 할당
}
function onDrop(e, side) {
  const raw = e.dataTransfer.items
    ? [...e.dataTransfer.items].filter(i=>i.kind==='file').map(i=>i.getAsFile()).filter(Boolean)
    : [...e.dataTransfer.files]
  const list = toList(raw)
  if (side==='src') {
    srcFiles.value=list; tgtFiles.value=[]
    vStore.fileResults=[]; vStore.activePair=-1; result.value=null
  } else {
    tgtFiles.value=list
  }
}

function removeSrc(i) {
  const s = [...srcFiles.value]; s.splice(i, 1); srcFiles.value = s
  const r = [...vStore.fileResults]; r.splice(i, 1); vStore.fileResults = r
}
function clearSrc()   {
  srcFiles.value=[]; tgtFiles.value=[]
  vStore.fileResults=[]; vStore.activePair=-1
  result.value=null
}
function clearTgt()   { tgtFiles.value=[] }
function clearAll()   {
  vStore.reset()
  result.value=null
  srcSql.value=''; tgtSql.value=''
}

const pendCount = computed(() => filePairs.value.length - doneCount.value)
const pctOk     = computed(() => filePairs.value.length ? okCount.value/filePairs.value.length*100 : 0)
const pctFail   = computed(() => filePairs.value.length ? failCount.value/filePairs.value.length*100 : 0)

// 배지 (함수로 - computed 남발 방지)
// DB 타입별 로고 (로컬 base64 인라인 - 인터넷 불필요)
const _DB_LOGOS = {
  mysql:      'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4Ij4KICA8cGF0aCBmaWxsPSIjMDA2MThBIiBkPSJNMTE2LjkgOTljLTYuNS0uMi0xMS41LjQtMTUuOCAyLjItMS4yLjUtMy4xLjUtMy4zIDIgLjcuNy44IDEuNyAxLjMgMi42IDEgMS42IDIuNyAzLjggNC4zIDUgMS43IDEuMyAzLjQgMi42IDUuMiAzLjcgMy4yIDEuOSA2LjggMyA5LjggNSAxLjggMS4xIDMuNiAyLjYgNS40IDMuOS45LjYgMS41IDEuNiAyLjYgMnYtLjJjLS42LS44LS44LTEuOC0xLjMtMi42bC0yLjQtMi40Yy0yLjQtMy4xLTUuNC01LjktOC42LTguMi0yLjUtMS44LTguMi00LjMtOS4zLTcuM2wtLjItLjJjMS44LS4yIDMuOS0uOSA1LjYtMS4zIDIuOC0uNyA1LjMtLjYgOC4yLTEuM2wzLjktMS4xdi0uN2MtMS41LTEuNS0yLjUtMy41LTQuMS00LjgtNC4yLTMuNS04LjctNy4xLTEzLjQtMTAtMi42LTEuNi01LjgtMi43LTguNi00LjEtLjktLjUtMi41LS43LTMuMi0xLjUtMS40LTEuOC0yLjItNC4yLTMuMy02LjMtMi4zLTQuNS00LjYtOS40LTYuNy0xNC4xLTEuNC0zLjItMi4zLTYuNC00LjEtOS4zLTguNS0xMy45LTE3LjYtMjIuMy0zMS43LTMwLjYtMy0xLjgtNi42LTIuNS0xMC40LTMuNGwtNi4xLS40Yy0xLjItLjUtMi41LTItMy43LTIuOEMxNC45IDMuMyAyLjMtMy40LTEuMyA1LjVjLTIuMyA1LjYgMy40IDExIDUuNCAxMy44IDEuNCAyIDMuMiA0LjIgNC4yIDYuNCAwLjcgMS40LjggMi44IDEuNCA0LjMgMS41IDMuOCAyLjggOCA0LjggMTEuNSAxIDEuNyAyLjEgMy41IDMuMyA1LjEuNyAxIDEuOSAxLjQgMi4xIDMtLjkgMS4zLTEgMy4yLTEuNSA0LjgtMi4zIDcuMy0xLjQgMTYuMyAxLjkgMjEuNyAxIDEuNiAzLjQgNS4xIDYuNiAzLjggMi44LTEuMiAyLjItNC43IDMtNy44LjItLjcuMS0xLjIuNC0xLjd2LjFsMi41IDVjMS44IDIuOSA1IDUuOSA3LjcgNy45IDEuNCAxIDIuNSAyLjggNC4zIDMuNHYtLjJoLS4xYy0uNC0uNS0uOS0xLTEuMy0xLjUtMS0xLTIuMS0yLjMtMi45LTMuNC0yLjMtMy4xLTQuMy02LjUtNi0xMC0uOS0xLjctMS42LTMuNi0yLjMtNS4zLS4zLS43LS4zLTEuNy0uOS0yLjEtLjggMS4yLTIgMi4zLTIuNiAzLjgtMSAyLjQtMS4xIDUuMy0xLjUgOC40LS4yLjEtLjEuMS0uMi4yLTItLjUtMi43LTIuNS0zLjQtNC4yLTEuOS00LjQtMi4yLTExLjUtLjYtMTYuNi41LTEuNSAyLjYtNi4yIDEuNy03LjYtLjQtLjgtMS43LTEuMy0yLjQtMS44LTEtLjYtMS44LTEuNi0yLjUtMi42LTEuNy0yLjMtMy4yLTUtNC4zLTcuNi0wLjYtMS4zLS44LTIuNy0xLjMtNC0xLTIuMy0yLjUtNC42LTMuNS02LjktLjUtMS4xLS44LTIuMy0xLjMtMy40LS43LTEuNS0xLjgtMi45LTIuMy00LjQtMS4zLTQuMS40LTguNSAxLjctMTEuMy40LS45IDEuNi0zLjcgMy40LTIuNyAxIC41IDEuMiAxLjcgMS43IDIuOC40LjkuOSAxLjggMS4zIDIuN2wxLjQgMy40Yy4xLjEuNCAxLjIuOSAxLjUuNC4yLjktLjMgMS4zLS4zLjUtLjEgMS4zLjIgMS45LjEuOS0uMiAxLjQtLjQgMi4xLS41LjYtLjEgMS4zLjEgMS45LjIuNS4xIDEgLjQgMS41LjVsLjguMmMuNC4xLjguMSAxLjIuMS42IDAgMS4zLS4xIDEuOS0uMi40LS4xLjgtLjIgMS4yLS40LjQtLjIuOC0uNiAxLjItLjctLjItMS4yLS43LTIuMy0xLjEtMy40LS40LS44LS43LTEuNi0xLTIuNS0uOS0yLjMtMi4yLTQuNi0zLjQtNi44LS42LTEuMS0xLjItMi4yLTEuOC0zLjMtLjItLjQtLjUtMS0uOC0xLjNzLS44LS40LTEuMS0uN2MtMS4yLS45LTIuNS0xLjktMy42LTIuOXoiLz4KICA8cGF0aCBmaWxsPSIjRTQ4RTAwIiBkPSJNMTcuMyA4LjdjLS42LjEtMSAuMS0xLjUuMy0uNC4xLS44LjUtMS4yLjdsMS4yIDIuNmMxIDIuMyAyLjQgNC42IDMuNCA2LjguMy44LjcgMS42IDEgMi41LjQgMS4xLjkgMi4yIDEuMSAzLjQtLjQuMS0uOC41LTEuMi43LS40LjItLjguMy0xLjIuNC0uNi4xLTEuMy4yLTEuOS4yLS40IDAtLjggMC0xLjItLjFsLS44LS4yYy0uNS0uMS0xLS40LTEuNS0uNS0uNi0uMS0xLjMtLjMtMS45LS4yLS43LjEtMS4yLjMtMi4xLjUtLjYuMS0xLjQtLjItMS45LS4xLS40IDAtLjkuNS0xLjMuMy0uNS0uMy0uOC0xLjQtLjktMS41TDUuMiAyMGMtLjQtLjktLjktMS44LTEuMy0yLjctLjUtMS4xLS43LTIuMy0xLjctMi44LTEuOC0xLTMgMS44LTMuNCAyLjctMS4zIDIuOC0zIDcuMi0xLjcgMTEuMy41IDEuNSAxLjYgMi45IDIuMyA0LjQuNSAxLjEuOCAyLjMgMS4zIDMuNCAxIDIuMyAyLjUgNC42IDMuNSA2LjkuNSAxLjMuNyAyLjcgMS4zIDQgMS4xIDIuNiAyLjYgNS4zIDQuMyA3LjYuNyAxIDEuNSAyIDIuNSAyLjYuNy41IDIgMSAyLjQgMS44LjkgMS40LTEuMiA2LjEtMS43IDcuNi0xLjYgNS4xLTEuMyAxMi4yLjYgMTYuNi43IDEuNyAxLjQgMy43IDMuNCA0LjIuMS0uMSAwLS4xLjItLjIuNC0zLjEuNS02IDEuNS04LjQuNi0xLjUgMS44LTIuNiAyLjYtMy44LjYuNC42IDEuNC45IDIuMS43IDEuNyAxLjQgMy42IDIuMyA1LjMgMS43IDMuNSAzLjcgNi45IDYgMTAgLjggMS4xIDEuOSAyLjQgMi45IDMuNC40LjUuOSAxIDEuMyAxLjVoLjF2LjJjLTEuOC0uNi0yLjktMi40LTQuMy0zLjQtMi43LTItNS45LTUtNy43LTcuOWwtMi41LTV2LS4xYy0uMy41LS4yIDEtLjQgMS43LS44IDMuMS0uMiA2LjYtMyA3LjgtMy4yIDEuMy01LjYtMi4yLTYuNi0zLjgtMy4zLTUuNC00LjItMTQuNC0xLjktMjEuNy41LTEuNi42LTMuNSAxLjUtNC44LS4yLTEuNi0xLjQtMi0yLjEtMy0xLjItMS42LTIuMy0zLjQtMy4zLTUuMS0yLTMuNS0zLjMtNy43LTQuOC0xMS41LS42LTEuNS0uNy0yLjktMS40LTQuMy0xLTIuMi0yLjgtNC40LTQuMi02LjRDLTEuOCAxNi41LTcuNSAxMS4xLTUuMiA1LjVjMy42LTguOSAxNi4yLTIuMiAxOS4xLS40IDEuMi44IDIuNSAyLjMgMy43IDIuOGw2LjEuNGMzLjguOSA3LjQgMS42IDEwLjQgMy40eiIvPgo8L3N2Zz4=',
  mssql:      'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4Ij4KICA8cGF0aCBmaWxsPSIjQ0MyOTI3IiBkPSJNNjQgOEMzMy4xIDggOCAzMy4xIDggNjRzMjUuMSA1NiA1NiA1NiA1Ni0yNS4xIDU2LTU2Uzk0LjkgOCA2NCA4eiIvPgogIDxwYXRoIGZpbGw9IiNmZmYiIGQ9Ik03My4zIDQ4LjRjLTIuMS0zLjYtNS4yLTUuNC05LjMtNS40SDQ0Ljl2NDEuMWg4VjcyLjZoMTFjMy45IDAgNy0xLjcgOS4yLTUuMiAxLjQtMi4yIDIuMS00LjggMi4xLTcuNnMtLjYtNS4yLTEuOS03LjR6bS04LjEgMTQuN0g1Mi45di0xMmgxMi4xYzEuNSAwIDIuNy43IDMuNSAyIC42IDEuMS45IDIuNC45IDRzLS4zIDIuOS0xIDRjLS44IDEuMy0yIDItMy4yIDJ6Ii8+CiAgPHBhdGggZmlsbD0iI2ZmZiIgZD0iTTkxIDQzaC03LjVMNzIuMiA4NC4xaDguMmwyLjMtNy4ySDk1bDIuNCA3LjJoOC4zem0tNS45IDI2LjFsNC42LTE0LjkgNC43IDE0Ljl6Ii8+Cjwvc3ZnPg==',
  postgresql: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4Ij4KICA8cGF0aCBmaWxsPSIjMzM2NzkxIiBkPSJNOTMuOCAxNy42Yy0zLjgtMS03LjgtMS4zLTExLjctMS0zLjguMy03LjQgMS4xLTEwLjcgMi40QzY1IDE2LjIgNTcuMyAxNSA0OS44IDE2Yy03LjYgMS0xNC42IDQtMjAgOC44LTUuMyA0LjgtOC45IDExLjMtOS44IDE4LjUtLjkgNy4xLjggMTQuNCA0LjggMjAuNSAyLjEgMy4yIDQuNyA1LjkgNy44IDggLjkgNS44IDIuNyAxMS41IDUuMyAxNi44IDIuOCA1LjcgNi41IDEwLjggMTEgMTQuOS41LjUgMS4xLjkgMS43IDEuMS42LjMgMS4zLjQgMiAuMy43LS4xIDEuMy0uNCAxLjgtLjguNS0uNS45LTEuMSAxLTEuOGwxLjUtOS40YzEuOS4zIDMuOC41IDUuNy41IDEuOSAwIDMuOS0uMiA1LjgtLjVsMS41IDkuNGMuMi43LjUgMS4zIDEgMS44LjUuNSAxLjEuOCAxLjguOC43LjEgMS40IDAgMi0uMy42LS4zIDEuMi0uNyAxLjctMS4xIDQuNS00LjEgOC4yLTkuMiAxMS0xNC45IDIuNi01LjMgNC40LTExIDUuMy0xNi44IDMuMS0yLjEgNS43LTQuOCA3LjgtOCA0LTYuMSA1LjctMTMuNCA0LjgtMjAuNS0uOS03LjItNC41LTEzLjctOS44LTE4LjUtMS44LTEuNi0zLjctMy01LjktNC4xLjctLjcgMS4zLTEuNCAxLjgtMi4yem0tMzAgNzkuNWMtMi4yIDAtNC40LS4zLTYuNS0uOWwuOC01YzEuOC40IDMuNy42IDUuNy42IDIgMCAzLjktLjIgNS43LS42bC44IDVjLTIuMS42LTQuMy45LTYuNS45eiIvPgogIDxjaXJjbGUgZmlsbD0iI2ZmZiIgY3g9IjUxIiBjeT0iNTIiIHI9IjYiLz4KICA8Y2lyY2xlIGZpbGw9IiNmZmYiIGN4PSI3NyIgY3k9IjUyIiByPSI2Ii8+CiAgPGNpcmNsZSBmaWxsPSIjMzM2NzkxIiBjeD0iNTEiIGN5PSI1MiIgcj0iMyIvPgogIDxjaXJjbGUgZmlsbD0iIzMzNjc5MSIgY3g9Ijc3IiBjeT0iNTIiIHI9IjMiLz4KPC9zdmc+',
  oracle:     'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4Ij4KICA8cGF0aCBmaWxsPSIjRjgwMDAwIiBkPSJNNjQgMTZDMzcuNSAxNiAxNiAzNy41IDE2IDY0czIxLjUgNDggNDggNDggNDgtMjEuNSA0OC00OFM5MC41IDE2IDY0IDE2eiIvPgogIDxwYXRoIGZpbGw9IiNmZmYiIGQ9Ik02NCAzNmMtMTUuNSAwLTI4IDEyLjUtMjggMjhzMTIuNSAyOCAyOCAyOCAyOC0xMi41IDI4LTI4LTEyLjUtMjgtMjgtMjh6bTAgNDRjLTguOCAwLTE2LTcuMi0xNi0xNnM3LjItMTYgMTYtMTYgMTYgNy4yIDE2IDE2LTcuMiAxNi0xNiAxNnoiLz4KPC9zdmc+',
  mongodb:    'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4Ij4KICA8cGF0aCBmaWxsPSIjNDM5OTM0IiBkPSJNODkuMiAyOS40QzgwLjUgMTguMyA3MC4yIDEzLjUgNjUuMiAxMS41Yy0uNC0uMi0uOC0uMy0xLjItLjNzLS44LjEtMS4yLjNjLTUgMi0xNS4zIDYuOC0yNCAxNy45LTExLjYgMTUtMTQgMzYuMy03LjIgNTYuNSAzLjUgMTAuNCA4LjggMTguNSAxMyAyMy45IDMuNSA0LjUgNS45IDYuOCA3LjIgNy43djYuNGMwIC43LjMgMS40LjkgMS45LjUuNSAxLjIuNyAxLjkuNi42LS4xIDEuMi0uNCAxLjYtLjkuNC0uNS42LTEgLjYtMS42di02LjRjMS4zLS45IDMuNy0zLjIgNy4yLTcuNyA0LjItNS40IDkuNS0xMy41IDEzLTIzLjkgNi44LTIwLjIgNC40LTQxLjUtNy4yLTU2LjV6TTY0IDk5LjVWMzIuM2MwIDAgMTguNCAxNC4zIDE4LjQgMzMuN0M4Mi40IDg0IDc0IDk1LjIgNjQgOTkuNXoiLz4KPC9zdmc+',
  mariadb:    'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4Ij4KICA8cGF0aCBmaWxsPSIjMDAzNTQ1IiBkPSJNNjQgOEMzMy4xIDggOCAzMy4xIDggNjRzMjUuMSA1NiA1NiA1NiA1Ni0yNS4xIDU2LTU2Uzk0LjkgOCA2NCA4eiIvPgogIDxwYXRoIGZpbGw9IiNDMDc2NUEiIGQ9Ik0zOCA0Mmg4djQ0aC04em0xNiAwaDhsMTQgMjYgMTQtMjZoOHY0NGgtOFY2NmwtMTQgMjQtMTQtMjR2MjBoLTh6Ii8+Cjwvc3ZnPg==',
}
function dbLogoUrl(dbType) {
  const t = (dbType||'').toLowerCase()
  if (t.includes('mysql') || t.includes('aurora'))   return _DB_LOGOS.mysql
  if (t.includes('mariadb'))                         return _DB_LOGOS.mariadb
  if (t.includes('mssql') || t.includes('sqlserver') || t.includes('microsoft')) return _DB_LOGOS.mssql
  if (t.includes('postgres') || t.includes('pg'))    return _DB_LOGOS.postgresql
  if (t.includes('oracle'))                          return _DB_LOGOS.oracle
  if (t.includes('mongo'))                           return _DB_LOGOS.mongodb
  return _DB_LOGOS.mssql  // 기본값
}

// ── 진단 엔진 ────────────────────────────────────────────────
function diagnose(result, pair) {
  const hints = []
  if (!result || result.comparison?.match) return hints
  const src = result.src, tgt = result.tgt
  const diff = result.comparison
  const srcRows = src?.row_count || 0
  const tgtRows = tgt?.row_count || 0
  const diffCount = diff?.diff_rows?.length || 0
  const srcOnly = diff?.diff_rows?.filter(r=>r.type==='src_only').length || 0
  const tgtOnly = diff?.diff_rows?.filter(r=>r.type==='tgt_only').length || 0
  const bothDiff = diff?.diff_rows?.filter(r=>r.type==='both').length || 0
  const maxRows = normOpts.value?.maxRows || 200

  // 1. 실행 오류
  if (!src?.ok) hints.push({ level:'error', icon:'🔴', title:'소스 실행 오류', msg: src.error, action: null })
  if (!tgt?.ok) hints.push({ level:'error', icon:'🔴', title:'타겟 실행 오류', msg: tgt.error, action: null })

  // 2. 최대행수 부족
  if (srcRows > 0 && tgtRows > 0) {
    const n = Math.max(srcRows, tgtRows)
    if (srcOnly > 0 && tgtOnly > 0 && srcOnly === tgtOnly && srcRows === tgtRows) {
      const nextStep = n <= 200 ? '1,000' : n <= 1000 ? '5,000' : n <= 5000 ? '10,000' : n <= 10000 ? '50,000' : n <= 50000 ? '100,000' : 'MAX(전체)'
      hints.push({ level:'warn', icon:'⚠️', title:'최대행수 부족 의심',
        msg:`소스 ${srcRows}행 / 타겟 ${tgtRows}행 — 양쪽 행수는 같지만 서로 다른 행 집합입니다. 전체 데이터가 최대행수(${n}행)보다 많아 소스/타겟이 각기 다른 ${n}행을 가져온 것으로 보입니다.`,
        action:`최대행수를 ${nextStep}으로 올리고 재실행하세요.` })
    }
    if (srcRows !== tgtRows) {
      hints.push({ level:'warn', icon:'⚠️', title:'행 수 불일치',
        msg:`소스 ${srcRows}행 vs 타겟 ${tgtRows}행 — 쿼리 결과 건수 자체가 다릅니다.`,
        action: srcRows > tgtRows
          ? '타겟(MySQL)에 데이터가 덜 이관됐거나 WHERE 조건이 다르게 동작할 수 있습니다.'
          : '소스(MSSQL)에 데이터가 적거나 변환된 쿼리의 JOIN/WHERE 조건을 확인하세요.' })
    }
  }

  // 3. 값 다름 (같은 키, 다른 값)
  if (bothDiff > 0 && srcOnly === 0 && tgtOnly === 0) {
    // 어떤 컬럼이 다른지
    const badCols = {}
    diff.diff_rows.filter(r=>r.type==='both').forEach(r => {
      r.diffs?.forEach(d => { badCols[d.col_src] = (badCols[d.col_src]||0)+1 })
    })
    const topCol = Object.entries(badCols).sort((a,b)=>b[1]-a[1])[0]
    if (topCol) {
      const col = topCol[0]
      const isDate = col.includes('dt') || col.includes('date') || col.includes('ym')
      const isNum = col.includes('amt') || col.includes('rate') || col.includes('cnt') || col.includes('month')
      if (isDate) hints.push({ level:'warn', icon:'📅', title:`날짜 형식 차이 (${col})`,
        msg:'MSSQL datetime2와 MySQL DATETIME의 소수점 초 또는 타임존 차이일 수 있습니다.',
        action:'정규화 옵션에서 "날짜만 비교(시간 무시)"를 켜고 재실행하세요.' })
      else if (isNum) hints.push({ level:'warn', icon:'🔢', title:`숫자 계산 차이 (${col})`,
        msg:'DATEDIFF(MONTH) vs TIMESTAMPDIFF(MONTH) 등 DB별 함수 계산 방식 차이일 수 있습니다.',
        action:'정규화 옵션에서 "월수 계산 허용 (±1개월)"을 켜고 재실행하세요.' })
      else hints.push({ level:'info', icon:'🔍', title:`값 불일치 컬럼: ${col}`,
        msg:`${topCol[1]}개 행에서 ${col} 컬럼 값이 다릅니다.`,
        action:'실행된 소스/타겟 SQL에서 해당 컬럼의 변환 로직을 확인하세요.' })
    }
  }

  // 4. 소스만 / 타겟만 패턴
  if (srcOnly > 0 && tgtOnly === 0) hints.push({ level:'warn', icon:'🔵', title:'소스에만 있는 데이터',
    msg:`${srcOnly}개 행이 소스(MSSQL)에만 존재합니다. 이관 누락이거나 WHERE 조건 차이입니다.`,
    action:'타겟(MySQL) 테이블에서 해당 데이터를 직접 조회해 이관 여부를 확인하세요.' })
  if (tgtOnly > 0 && srcOnly === 0) hints.push({ level:'warn', icon:'🟢', title:'타겟에만 있는 데이터',
    msg:`${tgtOnly}개 행이 타겟(MySQL)에만 존재합니다. 중복 이관이거나 변환 쿼리 오류일 수 있습니다.`,
    action:'변환된 MySQL 쿼리의 JOIN 조건이나 WHERE절을 점검하세요.' })

  return hints
}

function isZeroMatch(r) {
  // 소스/타겟 모두 0행이면서 일치 → "데이터 없음" 케이스
  return r?.comparison?.match && r?.src?.row_count === 0 && r?.tgt?.row_count === 0
}
function getBadgeClass(i) {
  if (!fileResults.value[i]) return runningIdx.value===i ? 'run' : ''
  if (fileResults.value[i].comparison?.skipped) return 'skip'
  if (isZeroMatch(fileResults.value[i])) return 'zero'
  return fileResults.value[i].comparison?.match ? 'ok' : 'fail'
}
function getBadgeText(i) {
  if (!fileResults.value[i]) return runningIdx.value===i ? '\u25b6' : ''
  if (fileResults.value[i].comparison?.skipped) return 'SKIP'
  if (isZeroMatch(fileResults.value[i])) return '0행'
  return fileResults.value[i].comparison?.match ? '\u2713' : '\u2717'
}

function selectPair(i) {
  vStore.activePair = i
  // 결과가 있으면 표시, 없으면 null로 초기화 (하단에 "미실행" 안내 표시)
  result.value = vStore.fileResults[i] || null
}

async function runAll() {
  if (!connector.bothConnected) { alert('소스/타겟 DB 연결을 먼저 확인하세요'); return }
  result.value = null
  await vStore.runAll(srcPlain(), tgtPlain(), filePairs.value)
  const last = filePairs.value.length - 1
  if (last >= 0 && vStore.fileResults[last]) result.value = vStore.fileResults[last]
}

function pauseRun()  { vStore.pause() }
function unpauseRun(){ vStore.unpause() }
function stopRun()   { vStore.stop() }
async function resumeRun() {
  await vStore.resume()
  // 완료된 마지막 파일 표시
  const results = vStore.fileResults
  for (let i = results.length - 1; i >= 0; i--) {
    if (results[i]) { result.value = results[i]; vStore.activePair = i; break }
  }
}

// ── 배너 ─────────────────────────────────────────────────
const _isZeroRes  = computed(() => isZeroMatch(result.value))
const bannerCls   = computed(() => {
  if (!result.value?.comparison) return 'diff'
  if (_isZeroRes.value) return 'zero'
  return result.value.comparison.match ? (result.value.comparison.warning?'warn':'match') : 'diff'
})
const bannerIcon  = computed(() => {
  if (_isZeroRes.value) return '\u26a0'
  return result.value?.comparison?.match ? (result.value.comparison.warning?'\u26a0':'\u2713') : '\u2717'
})
const bannerTitle = computed(() => {
  if (_isZeroRes.value) return '데이터 없음 (0행 일치)'
  return result.value?.comparison?.match ? (result.value.comparison.warning?'데이터 일치 (정렬 차이)':'결과 완전 일치') : '결과 불일치'
})

// ── 불일치 하이라이트 (일반 객체 - reactive 오버헤드 없음) ─

// ── 정렬 ─────────────────────────────────────────────────
const sortCol = reactive({src:'', tgt:''})
const PAGE_SIZE = 100
const dispPage = ref({src:1, tgt:1})
const sortDir = reactive({src:'asc', tgt:'asc'})

function toggleSort(side, col) {
  if (sortCol[side] === col) {
    sortDir[side] = sortDir[side] === 'asc' ? 'desc' : 'asc'
  } else {
    sortCol[side] = col
    sortDir[side] = 'asc'
  }
}

function pagedRows(side) {
  const all = sortedRows(side)
  const page = dispPage.value[side] || 1
  return all.slice(0, page * PAGE_SIZE)
}
function hasMore(side) {
  return sortedRows(side).length > (dispPage.value[side] || 1) * PAGE_SIZE
}
function loadMore(side) {
  dispPage.value[side] = (dispPage.value[side] || 1) + 1
}

function sortedRows(side) {
  if (!result.value?.[side]?.rows) return []
  const rows = result.value[side].rows
  const col = sortCol[side]
  if (!col) return rows
  const ci = result.value[side].cols.indexOf(col)
  if (ci < 0) return rows
  const dir = sortDir[side] === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    const av = a[ci] ?? '', bv = b[ci] ?? ''
    if (av === bv) return 0
    if (av === null || av === '') return dir
    if (bv === null || bv === '') return -dir
    // 숫자면 숫자 비교
    const an = parseFloat(av), bn = parseFloat(bv)
    if (!isNaN(an) && !isNaN(bn)) return (an - bn) * dir
    return String(av).localeCompare(String(bv)) * dir
  })
}

// fileResults 변화 감지 → 실행 완료된 파일을 자동으로 하단에 표시
watch(() => vStore.fileResults, (results) => {
  // 실행 완료된 마지막 파일을 자동 표시
  // (activePair가 -1이거나 현재 표시 중인 파일 기준)
  const cur = vStore.activePair
  if (cur >= 0 && results[cur]) {
    result.value = results[cur]
  } else {
    // activePair 미설정 → 완료된 가장 마지막 파일 표시
    for (let i = results.length - 1; i >= 0; i--) {
      if (results[i]) {
        result.value = results[i]
        vStore.activePair = i
        break
      }
    }
  }
}, { deep: true })

// watch result 변경 시 정렬 초기화
watch(result, () => { sortCol.src=''; sortCol.tgt=''; sortDir.src='asc'; sortDir.tgt='asc' })

const diffRowSet  = computed(() => new Set((result.value?.comparison?.diff_rows||[]).map(d=>d.row-1)))
const diffCellMap = computed(() => {
  const m = {}
  ;(result.value?.comparison?.diff_rows||[]).forEach(dr => {
    m[dr.row-1] = m[dr.row-1] || new Set()
    dr.diffs.forEach(d => { const ci = result.value.src.cols.indexOf(d.col_src); if(ci>=0) m[dr.row-1].add(ci) })
  }); return m
})

// ── 리포트 (전체 상세 버전) ──────────────────────────────
function exportReport(fmt='txt') {
  const now  = new Date().toLocaleString('ko-KR')
  const src  = connector.source, tgt = connector.target
  // filePairs가 비어있을 수 있으므로 fileResults 기준으로 계산
  const pairs = filePairs.value.length > 0
    ? filePairs.value
    : vStore.fileResults.map((r,i) => ({
        srcName: r?._src_file || `소스${i+1}`,
        tgtName: r?._tgt_file || `타겟${i+1}`,
        srcFile: null, tgtFile: null, srcOnly: false, tgtOnly: false
      }))
  const results = vStore.fileResults
  const total   = Math.max(pairs.length, results.filter(r=>r).length)
  const done    = results.filter(r => r !== null).length
  const matched = results.filter(r => r?.comparison?.match).length
  const failed  = results.filter(r => r && !r.comparison?.match && !r.comparison?.skipped).length
  const pending = total - done

  if (fmt === 'txt') {
    const SEP = '='.repeat(70)
    const S2  = '-'.repeat(70)
    const L = []
    L.push('DataBridge Studio \u2014 쿼리 검증 비교 리포트')
    L.push(SEP)
    L.push(`생성: ${now}`)
    L.push(`소스: ${src.dbType}/${src.database}  \u2192  타겟: ${tgt.dbType}/${tgt.database}`)
    L.push(`검증방식: ${currentVerifyMode.value?.label || verifyMode.value}`)
    L.push(`최대행수: ${maxRows.value >= 999999 ? 'MAX(전체)' : maxRows.value.toLocaleString()+'행'}`)
    // 정규화 설정
    const no = normOpts
    const _DML = {round:'반올림',floor:'내림',ceil:'올림',trunc:'버림',ignore:'소수점무시',skip_below:'X자리이하무시'}
    const _DTL = {date:'날짜만(시간무시)',datetime:'날짜+시간',ym:'년월',year:'년도'}
    const normLines = []
    if (no.decimal?.enabled) {
      const ml = _DML[no.decimal.mode] || no.decimal.mode
      const dig = no.decimal.mode !== 'ignore' ? `(${no.decimal.digits}자리)` : ''
      normLines.push(`소수점: ${ml}${dig}`)
    }
    if (no.datetime?.enabled) {
      normLines.push(`날짜: ${_DTL[no.datetime.mode] || no.datetime.mode}`)
    }
    if (no.string?.trim) normLines.push('공백제거')
    if (no.string?.caseInsensitive) normLines.push('대소문자무시')
    if (no.nullEmpty) normLines.push('NULL=빈값')
    if (no.boolInt) normLines.push('BOOL=INT')
    L.push(`정규화: ${normLines.length ? normLines.join(' | ') : '없음'}`)
    L.push('')
    L.push(`총 ${total}쌍   \u2713 일치: ${matched}   \u2717 불일치: ${failed}   \u2717 오류: 0   \u25cb 미실행: ${pending}`)
    // 실행 오류 / 불일치 / 일치 통계
    const errList  = [], failList = [], okList = []
    pairs.forEach((p, i) => {
      const r = results[i]
      if (!r) return
      if (!r.src.ok || !r.tgt.ok) errList.push(i)
      else if (!r.comparison.match) failList.push(i)
      else okList.push(i)
    })
    L.push(`  \u2713 완전일치: ${okList.length}   \u2717 값불일치: ${failList.length}   \u2717 실행오류: ${errList.length}   \u25cb 미실행: ${pending}`)
    L.push(SEP)
    L.push('')

    // ── 전체 항목 상세 출력 ──
    pairs.forEach((p, i) => {
      const r   = results[i]
      const num = String(i+1).padStart(2, '0')
      L.push(`${num}. ${p.srcName}`)
      L.push(`    \u2192 ${p.tgtName || '(자동변환)'}`)

      if (!r) {
        L.push(`    \u25cb 미실행`)
        L.push('')
        return
      }

      // 실행 오류
      if (!r.src.ok || !r.tgt.ok) {
        L.push(`    \u2717 실행 오류`)
        if (!r.src.ok) L.push(`    소스 오류: ${r.src.error}`)
        if (!r.tgt.ok) L.push(`    타겟 오류: ${r.tgt.error}`)
        L.push(`    소스: ${r.src.row_count}행 ${r.src.elapsed_ms}ms  타겟: ${r.tgt.row_count}행 ${r.tgt.elapsed_ms}ms`)
        // 실제 실행된 SQL
        if (r._src_sql) {
          L.push(`    [ 실행된 소스 SQL ]`)
          r._src_sql.trim().split('\n').slice(0,5).forEach(ln => L.push(`      ${ln}`))
        }
        if (r._tgt_sql) {
          L.push(`    [ 실행된 타겟 SQL ]`)
          r._tgt_sql.trim().split('\n').slice(0,5).forEach(ln => L.push(`      ${ln}`))
        }
        L.push(S2)
        L.push('')
        return
      }

      // 결과 요약
      const icon = r.comparison.match ? '\u2713' : '\u2717'
      L.push(`    ${icon} ${r.comparison.reason}`)
      if (r.comparison.warning) L.push(`    \u26a0 ${r.comparison.warning}`)
      L.push(`    소스: ${r.src.row_count}행 ${r.src.elapsed_ms}ms  타겟: ${r.tgt.row_count}행 ${r.tgt.elapsed_ms}ms`)
      // 실제 실행된 SQL (파일 내용 확인용)
      if (r._src_sql) {
        L.push(`    [ 실행된 소스 SQL (${r._src_file || ''}) ]`)
        r._src_sql.trim().split('\n').forEach(ln => L.push(`      ${ln}`))
      }
      if (r._tgt_sql) {
        L.push(`    [ 실행된 타겟 SQL (${r._tgt_file || ''}) ]`)
        r._tgt_sql.trim().split('\n').forEach(ln => L.push(`      ${ln}`))
      }

      // 컬럼 목록
      if (r.src.cols?.length) {
        L.push(`    컬럼(${r.src.cols.length}개): ${r.src.cols.join(', ')}`)
      }

      // 불일치 상세 - 샘플 전체 출력
      if (!r.comparison.match && r.comparison.diff_rows?.length) {
        L.push(`    [ 불일치 샘플 (${r.comparison.diff_rows.length}행) ]`)
        r.comparison.diff_rows.forEach(dr => {
          const typeLabel = dr.type==='src_only'?'소스전용':dr.type==='tgt_only'?'타겟전용':'값다름'
          L.push(`    행 ${dr.row} [${typeLabel}]:`)
          ;(dr.diffs||[]).forEach(d => {
            L.push(`      ${String(d.col_src).padEnd(20)} : ${String(d.src?? '\u2014').padEnd(25)} \u2192 ${d.tgt?? '\u2014'}`)
          })
        })
      }

      // 소스 데이터 전체 (최대 200행)
      if (r.src.rows?.length) {
        L.push(`    [ 소스 데이터 (${r.src.row_count}행) ]`)
        L.push(`    ${r.src.cols.map(c=>String(c).padEnd(18)).join(' ')}`)
        L.push(`    ${'-'.repeat(Math.min(r.src.cols.length*19, 60))}`)
        r.src.rows.forEach(row => {
          L.push(`    ${row.map(v=>String(v??'').padEnd(18)).join(' ')}`)
        })
      }

      // 타겟 데이터 전체 (불일치인 경우만)
      if (!r.comparison.match && r.tgt.rows?.length) {
        L.push(`    [ 타겟 데이터 (${r.tgt.row_count}행) ]`)
        L.push(`    ${r.tgt.cols.map(c=>String(c).padEnd(18)).join(' ')}`)
        L.push(`    ${'-'.repeat(Math.min(r.tgt.cols.length*19, 60))}`)
        r.tgt.rows.forEach(row => {
          L.push(`    ${row.map(v=>String(v??'').padEnd(18)).join(' ')}`)
        })
      }

      L.push(S2)
      L.push('')
    })

    L.push(SEP)
    L.push(`END`)
    const blob = new Blob([L.join('\n')], {type:'text/plain;charset=utf-8'})
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `verify_${new Date().toISOString().slice(0,10)}.txt`
    a.click()

  } else {
    // ── HTML 리포트 ──────────────────────────────────────
    const esc = s => String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')

    const stl = `
*{box-sizing:border-box}
body{font-family:'Malgun Gothic',Consolas,sans-serif;font-size:12px;background:#f3f4f6;margin:0;padding:16px}
h1{font-size:16px;margin:0 0 4px}
.meta{color:#6b7280;font-size:11px;margin-bottom:12px}
.summary{display:flex;gap:12px;margin-bottom:14px;flex-wrap:wrap}
.sum-card{background:#fff;border-radius:8px;padding:10px 18px;text-align:center;border:1px solid #e5e7eb}
.sum-card .n{font-size:22px;font-weight:700}
.sum-card .l{font-size:10px;color:#6b7280}
.ok-c .n{color:#059669} .fail-c .n{color:#dc2626} .err-c .n{color:#f59e0b} .pend-c .n{color:#6b7280}
.q-block{background:#fff;border:1px solid #e5e7eb;border-radius:8px;margin-bottom:10px;overflow:hidden}
.q-hdr{display:flex;align-items:center;gap:8px;padding:8px 12px;cursor:pointer;user-select:none}
.q-hdr:hover{background:#f9fafb}
.q-num{background:#f3f4f6;border-radius:5px;padding:1px 7px;font-size:10px;font-weight:700;color:#374151}
.q-name{font-weight:600;font-size:11px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.q-arrow{font-size:10px;color:#9ca3af}
.badge{font-size:10px;padding:1px 8px;border-radius:10px;font-weight:700}
.ok{background:#dcfce7;color:#166534} .fail{background:#fee2e2;color:#991b1b}
.warn{background:#fef3c7;color:#92400e} .err-b{background:#ffedd5;color:#c2410c}
.pend-b{background:#f3f4f6;color:#6b7280}
.q-body{border-top:1px solid #f3f4f6;display:none}
.q-body.open{display:block}
.sect{padding:8px 12px;border-bottom:1px solid #f3f4f6}
.sect-title{font-size:10px;font-weight:700;color:#6b7280;margin-bottom:5px;text-transform:uppercase;letter-spacing:.05em}
.meta-row{display:flex;gap:16px;font-size:11px}
.meta-row span{color:#374151} .meta-row b{color:#1f2937}
.err-box{background:#fff5f5;border:1px solid #fecaca;border-radius:5px;padding:6px 10px;font-size:11px;color:#dc2626;margin-top:4px}
.warn-box{background:#fffbeb;border:1px solid #fde68a;border-radius:5px;padding:5px 10px;font-size:11px;color:#92400e;margin-top:4px}
.diff-wrap{display:flex;flex-wrap:wrap;gap:6px}
.diff-item{border:1px solid #e5e7eb;border-radius:6px;overflow:hidden;min-width:220px;flex:1}
.diff-item-hdr{padding:3px 8px;font-size:10px;font-weight:700;background:#f9fafb;display:flex;gap:6px;align-items:center}
.src-tag{color:#dc2626} .tgt-tag{color:#059669} .val-tag{color:#b45309}
.diff-field{display:grid;grid-template-columns:90px 1fr 12px 1fr;gap:4px;padding:3px 8px;font-size:10px;border-top:1px solid #f3f4f6}
.col-nm{color:#1d4ed8;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sv{color:#dc2626;font-family:Consolas,monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tv{color:#059669;font-family:Consolas,monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.missing{color:#9ca3af;font-style:italic}
.tbl-wrap{overflow-x:auto;max-height:300px;overflow-y:auto}
table.dt{border-collapse:collapse;font-size:10px;min-width:100%}
table.dt th{background:#374151;color:#fff;padding:4px 8px;white-space:nowrap;position:sticky;top:0}
table.dt td{padding:3px 8px;border-bottom:1px solid #f3f4f6;white-space:nowrap}
table.dt tr:nth-child(even) td{background:#f9fafb}
table.dt tr.diff-r td{background:#fef2f2}
`

    // 통계
    const errList=[], failList=[], okList=[], pendList=[]
    pairs.forEach((p,i)=>{
      const r=fileResults.value[i]
      if(!r){pendList.push(i);return}
      if(!r.src.ok||!r.tgt.ok){errList.push(i);return}
      if(!r.comparison.match){failList.push(i);return}
      okList.push(i)
    })

    const sumCards = `
      <div class="sum-card ok-c"><div class="n">${okList.length}</div><div class="l">\u2713 일치</div></div>
      <div class="sum-card fail-c"><div class="n">${failList.length}</div><div class="l">\u2717 불일치</div></div>
      <div class="sum-card err-c"><div class="n">${errList.length}</div><div class="l">\u2717 실행오류</div></div>
      <div class="sum-card pend-c"><div class="n">${pendList.length}</div><div class="l">\u25cb 미실행</div></div>
      <div class="sum-card"><div class="n">${total}</div><div class="l">전체</div></div>`

    const blocks = pairs.map((p,i)=>{
      const r = results[i]

      // 배지
      let badge, bodyHtml = ''
      if(!r){
        badge=`<span class="badge pend-b">미실행</span>`
      } else if(!r.src.ok||!r.tgt.ok){
        badge=`<span class="badge err-b">실행오류</span>`
        bodyHtml += `<div class="sect"><div class="sect-title">오류 내용</div>`
        if(!r.src.ok) bodyHtml+=`<div class="err-box">소스: ${esc(r.src.error)}</div>`
        if(!r.tgt.ok) bodyHtml+=`<div class="err-box">타겟: ${esc(r.tgt.error)}</div>`
        bodyHtml+=`</div>`
      } else if(r.comparison.match){
        badge=`<span class="badge ok">\u2713 일치</span>`
        if(r.comparison.warning) badge+=`<span class="badge warn">\u26a0 정렬차이</span>`
      } else {
        badge=`<span class="badge fail">\u2717 불일치</span>`
      }

      if(r){
        // 실행 정보
        bodyHtml += `<div class="sect"><div class="meta-row">
          <span>소스 <b>${r.src.row_count}행</b></span>
          <span><b>${r.src.elapsed_ms}ms</b></span>
          <span style="color:#e5e7eb">|</span>
          <span>타겟 <b>${r.tgt.row_count}행</b></span>
          <span><b>${r.tgt.elapsed_ms}ms</b></span>
          <span style="color:#e5e7eb">|</span>
          <span>${esc(r.comparison.reason)}</span>
        </div>${r.comparison.warning?`<div class="warn-box">\u26a0 ${esc(r.comparison.warning)}</div>`:''}</div>`

        // 불일치 상세
        if(!r.comparison.match && r.comparison.diff_rows?.length){
          let diffHtml='<div class="diff-wrap">'
          r.comparison.diff_rows.forEach(dr=>{
            const typeLabel=dr.type==='src_only'?'소스전용':dr.type==='tgt_only'?'타겟전용':'값다름'
            const tagCls=dr.type==='src_only'?'src-tag':dr.type==='tgt_only'?'tgt-tag':'val-tag'
            diffHtml+=`<div class="diff-item"><div class="diff-item-hdr">
              <span>행 ${dr.row}</span><span class="${tagCls}">${typeLabel}</span></div>`
            ;(dr.diffs||[]).forEach(d=>{
              diffHtml+=`<div class="diff-field">
                <span class="col-nm">${esc(d.col_src)}</span>
                <span class="sv ${d.src==='\u2014'?'missing':''}">${esc(d.src?? '\u2014')}</span>
                <span style="color:#9ca3af">\u2192</span>
                <span class="tv ${d.tgt==='\u2014'||d.tgt==null?'missing':''}">${esc(d.tgt?? '\u2014')}</span>
              </div>`
            })
            diffHtml+=`</div>`
          })
          diffHtml+='</div>'
          bodyHtml+=`<div class="sect"><div class="sect-title">불일치 샘플 (${r.comparison.diff_rows.length}개)</div>${diffHtml}</div>`
        }

        // 소스 결과 테이블
        if(r.src.rows?.length){
          let tblH=`<table class="dt"><thead><tr>${r.src.cols.map(c=>`<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>`
          r.src.rows.forEach((row,ri)=>{
            const isDiff = !r.comparison.match && r.comparison.diff_rows?.some(dr=>dr.row===ri+1)
            tblH+=`<tr${isDiff?' class="diff-r"':''}>${row.map(v=>`<td>${esc(v)}</td>`).join('')}</tr>`
          })
          tblH+=`</tbody></table>`
          bodyHtml+=`<div class="sect"><div class="sect-title">소스 결과 (${r.src.row_count}행)</div><div class="tbl-wrap">${tblH}</div></div>`
        }

        // 타겟 결과 테이블
        if(r.tgt.rows?.length){
          let tblH=`<table class="dt"><thead><tr>${r.tgt.cols.map(c=>`<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>`
          r.tgt.rows.forEach(row=>{
            tblH+=`<tr>${row.map(v=>`<td>${esc(v)}</td>`).join('')}</tr>`
          })
          tblH+=`</tbody></table>`
          bodyHtml+=`<div class="sect"><div class="sect-title">타겟 결과 (${r.tgt.row_count}행)</div><div class="tbl-wrap">${tblH}</div></div>`
        }
      }

      return `<div class="q-block">
        <div class="q-hdr" onclick="var b=this.nextSibling;b.classList.toggle('open');this.querySelector('.q-arrow').textContent=b.classList.contains('open')?'\u25b2':'\u25bc'">
          <span class="q-num">${i+1}</span>
          <span class="q-name">${esc(p.srcName)}</span>
          <span style="color:#9ca3af;font-size:10px">\u2192 ${esc(p.tgtName||'자동')}</span>
          ${badge}
          <span class="q-arrow">\u25bc</span>
        </div>
        <div class="q-body">${bodyHtml}</div>
      </div>`
    }).join('')

    const _s = '<'+'style>'
    const _es = '<'+'/style>'
    const _hb = '<'+'/head><body>'
    const _eb = '<'+'/body><'+'/html>'
    const html = '<!DOCTYPE html>'
      + '<html lang="ko"><head><meta charset="UTF-8">'
      + '<title>쿼리 검증 리포트 \u2014 ' + esc(now) + '</title>'
      + _s + stl + _es
      + _hb
      + '<h1>DataBridge Studio \u2014 쿼리 검증 비교 리포트</h1>'
      + '<div class="meta">생성: ' + now + ' &nbsp;|&nbsp; 소스: '
      + (connector.source?.database||'') + ' \u2192 타겟: '
      + (connector.target?.database||'') + '</div>'
      + '<div class="meta" style="margin-top:4px">'
      + '\u2713 검증방식: <b>' + (currentVerifyMode.value?.label || verifyMode.value) + '</b>'
      + ' &nbsp;|&nbsp; 최대행수: <b>' + maxRows.value + '행</b>'
      + ' &nbsp;|&nbsp; 정규화: <b>' + (() => {
          const _n = normOpts
          const _dm = {round:'반올림',floor:'내림',ceil:'올림',trunc:'버림',ignore:'소수점무시',skip_below:'X자리이하무시'}
          const _dt = {date:'날짜만(시간무시)',datetime:'날짜+시간',ym:'년월',year:'년도'}
          const _p = []
          if (_n.decimal?.enabled) _p.push('소수점:' + (_dm[_n.decimal.mode]||_n.decimal.mode) + (_n.decimal.mode!=='ignore'?'('+_n.decimal.digits+'자리)':''))
          if (_n.datetime?.enabled) _p.push('날짜:' + (_dt[_n.datetime.mode]||_n.datetime.mode))
          if (_n.string?.trim) _p.push('공백제거')
          if (_n.string?.caseInsensitive) _p.push('대소문자무시')
          if (_n.nullEmpty) _p.push('NULL=빈값')
          if (_n.boolInt) _p.push('BOOL=INT')
          return _p.length ? _p.join(' | ') : '없음'
        })() + '</b>'
      + '</div>'
      + '<div class="summary">'
      + '<div class="sum-card ok-c"><div class="n">' + okList.length + '</div><div class="l">완전일치</div></div>'
      + '<div class="sum-card fail-c"><div class="n">' + failList.length + '</div><div class="l">불일치</div></div>'
      + '<div class="sum-card err-c"><div class="n">' + errList.length + '</div><div class="l">오류</div></div>'
      + '<div class="sum-card pend-c"><div class="n">' + pendList.length + '</div><div class="l">미실행</div></div>'
      + '</div>'
      + qBlocks
      + _eb

    const blob = new Blob([html], {type:'text/html;charset=utf-8'})
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href     = url
    a.download = 'verify_' + new Date().toISOString().slice(0,10) + '.html'
    a.click()
    URL.revokeObjectURL(url)
  }
}

</script>

<style>
.sv-wrap{display:flex;flex-direction:column;gap:10px}
.warn-banner{display:flex;align-items:center;gap:8px;padding:10px 14px;background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.3);border-radius:10px;font-size:.8rem;color:#b45309}
.act-btn{padding:3px 10px;border-radius:6px;border:1px solid #b45309;background:transparent;cursor:pointer;font-size:.72rem;color:#b45309}
.card{background:var(--bg-primary);border-radius:10px;border:0.5px solid var(--border-light)}
/* 옵션 바 */
.opt-bar{padding:6px 14px}
.opt-row{display:flex;align-items:center;gap:0;overflow-x:auto;white-space:nowrap;flex-wrap:nowrap}
/* ── DB 박스 ── */
.db-box2{display:flex;align-items:center;gap:8px;padding:4px 10px 4px 6px;
  border-radius:10px;border:1px solid transparent;transition:border-color .15s}
.db-box2.src{border-color:rgba(59,130,246,.22);background:rgba(59,130,246,.04)}
.db-box2.tgt{border-color:rgba(16,185,129,.22);background:rgba(16,185,129,.04)}
.db-icon-wrap{display:flex;flex-direction:column;align-items:center;gap:2px}
.db-cyl-wrap{position:relative;width:32px;height:32px;display:flex;align-items:center;justify-content:center}
.db-cyl{width:32px;height:32px;flex-shrink:0}
.db-logo-img{position:absolute;width:14px;height:14px;object-fit:contain;top:50%;left:50%;
  transform:translate(-50%,-44%);filter:drop-shadow(0 1px 1px rgba(0,0,0,.15))}
.db-online-dot{position:absolute;top:1px;right:0;width:7px;height:7px;
  border-radius:50%;background:#16a34a;border:1.5px solid white}
.db-label{font-size:.54rem;font-weight:800;letter-spacing:.07em;text-transform:uppercase;line-height:1}
.db-label.src{color:#2563eb}
.db-label.tgt{color:#059669}
.db-info{display:flex;flex-direction:column;gap:1px}
.db-nm2{font-size:.78rem;font-weight:700;color:var(--text-primary);line-height:1.2}
.db-tp2{font-size:.62rem;color:var(--text-tertiary);line-height:1.2}
.db-arrow{display:flex;align-items:center;padding:0 2px;flex-shrink:0}
/* 하위 호환 */
.db-box{display:flex;align-items:center;gap:5px}
.db-tag{font-size:.68rem;font-weight:700;padding:2px 7px;border-radius:7px}
.db-tag.src{background:rgba(59,130,246,.12);color:#2563eb}
.db-tag.tgt{background:rgba(16,185,129,.12);color:#059669}
.db-nm{font-size:.8rem}.db-tp{font-size:.68rem;color:var(--text-tertiary)}.dot-ok{color:#16a34a;font-size:.7rem}.arr{color:var(--text-tertiary)}
.opt-div{width:1px;height:20px;background:var(--border-mid);flex-shrink:0;margin:0 2px}
.opt-lbl{font-size:.65rem;font-weight:700;color:var(--text-tertiary);white-space:nowrap;letter-spacing:.02em;text-transform:uppercase}
/* ── 그룹 컨테이너 ── */
.opt-group{display:inline-flex;align-items:center;gap:3px;padding:0 10px;
  border-left:1.5px solid var(--border-mid);height:32px;flex-shrink:0}
.opt-group:first-of-type{border-left:none;padding-left:4px}
/* ── 칩 공통 ── */
.chip{display:inline-flex;align-items:center;gap:3px;font-size:.72rem;padding:3px 8px;
  border-radius:7px;border:1px solid var(--border-mid);cursor:pointer;
  color:var(--text-secondary);user-select:none;transition:all .12s;background:transparent;
  font-family:var(--font);white-space:nowrap;line-height:1.4}
.chip:hover{background:var(--bg-hover);color:var(--text-primary);border-color:var(--border-strong)}
.chip.on{background:var(--accent,#3b82f6);border-color:var(--accent,#3b82f6);color:#fff;font-weight:600}
/* ── 변환 칩 색상 ── */
.chip-auto:hover{border-color:#f59e0b;color:#b45309}
.chip-auto.on{background:#f59e0b;border-color:#f59e0b;color:#fff}
.chip-ai:hover{border-color:#7c3aed;color:#7c3aed}
.chip-ai.on{background:#7c3aed;border-color:#7c3aed;color:#fff}
/* ── 정규화 칩 ── */
.chip-norm:hover{border-color:#3b82f6;color:#2563eb}
.chip-norm.on{background:rgba(59,130,246,.1);border-color:#3b82f6;color:#2563eb;font-weight:600}
/* ── 액션 칩 ── */
.chip-report{color:var(--accent,#3b82f6);border-color:rgba(59,130,246,.35)}
.chip-report:hover{background:rgba(59,130,246,.07)}
.chip-clear{color:#dc2626;border-color:rgba(220,38,38,.35)}
.chip-clear:hover{background:rgba(220,38,38,.07)}
.sel-sm{padding:4px 7px;border:0.5px solid var(--border-mid);border-radius:6px;font-size:.72rem;background:var(--bg-input,#fff);color:var(--text-primary)}
.rpt-btn{font-size:.7rem;padding:4px 10px;border-radius:7px;border:0.5px solid var(--border-mid);background:transparent;cursor:pointer;color:var(--text-secondary);white-space:nowrap}
.rpt-btn.blue{border-color:rgba(59,130,246,.4);color:#3b82f6}
.rpt-btn.red{border-color:rgba(239,68,68,.3);color:#dc2626}
/* 텍스트 모드 */
.text-layout{display:grid;grid-template-columns:1fr 52px 1fr;gap:8px}
.sql-panel{padding:0;overflow:hidden;display:flex;flex-direction:column}
.panel-hdr{display:flex;align-items:center;gap:6px;padding:7px 12px;background:var(--bg-secondary);border-bottom:0.5px solid var(--border-light);font-size:.75rem;font-weight:700;flex-shrink:0}
.panel-hdr.src{color:#2563eb}.panel-hdr.tgt{color:#059669}
.hdr-db{font-size:.68rem;font-weight:400;color:var(--text-tertiary)}
.hdr-cnt{font-size:.68rem;padding:1px 6px;border-radius:7px;background:var(--bg-info);color:var(--text-info)}
.hdr-btn{font-size:.68rem;padding:2px 8px;border-radius:6px;border:0.5px solid var(--border-mid);background:transparent;cursor:pointer;color:var(--text-secondary);position:relative;z-index:10}
.hdr-btn.tgt{border-color:rgba(16,185,129,.4);color:#059669}
.hdr-btn.red{border-color:rgba(239,68,68,.3);color:#dc2626}
.sql-ta{flex:1;width:100%;min-height:260px;padding:10px;border:none;background:transparent;font-family:monospace;font-size:12px;resize:none;color:var(--text-primary);box-sizing:border-box;outline:none}
.text-mid{display:flex;align-items:center;justify-content:center}
.exec-btn{display:flex;flex-direction:column;align-items:center;gap:4px;padding:12px 10px;border-radius:10px;border:none;background:#3b82f6;color:#fff;cursor:pointer}
.exec-btn:disabled{opacity:.5;cursor:not-allowed}
.conv-bar{display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:6px 12px;background:var(--bg-secondary);border-radius:8px}
.cv-bd{font-size:.7rem;font-weight:700;padding:2px 8px;border-radius:8px}
.cv-bd.ai{background:rgba(139,92,246,.15);color:#6d28d9}.cv-bd.rule{background:var(--bg-info);color:var(--text-info)}
.ctag{font-size:.68rem;padding:1px 7px;border-radius:8px;background:rgba(34,197,94,.1);color:#15803d}
/* 파일 프레임 */
.file-frames{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.file-frame{padding:0;overflow:hidden;display:flex;flex-direction:column;height:260px}
.frame-empty{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;font-size:.75rem;color:var(--text-tertiary);cursor:pointer;border:1.5px dashed var(--border-mid);margin:8px;border-radius:8px}
.frame-empty:hover{border-color:#3b82f6;color:#3b82f6}
.frame-auto{flex:1;display:flex;align-items:center;justify-content:center;font-size:.78rem;color:var(--text-tertiary)}
.frame-list{overflow-y:auto;flex:1}
.frow{display:flex;align-items:center;gap:5px;padding:5px 10px;border-bottom:0.5px solid var(--border-light);cursor:pointer;font-size:11px}
.frow:last-child{border-bottom:none}
.frow:hover,.frow.active{background:var(--bg-hover)}
.frow.running{background:rgba(59,130,246,.05)}
.frow-num{font-size:10px;color:var(--text-tertiary);width:18px;flex-shrink:0}
.frow-name{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.72rem}
.frow-badge{font-size:10px;padding:1px 5px;border-radius:6px;font-weight:700;flex-shrink:0;min-width:16px;text-align:center}
.frow-badge.ok{background:rgba(34,197,94,.15);color:#15803d}
.frow-badge.fail{background:rgba(239,68,68,.12);color:#dc2626}
.frow-badge.run{background:rgba(59,130,246,.12);color:#2563eb}
.frow-rm{border:none;background:none;cursor:pointer;color:var(--text-tertiary);font-size:13px;padding:0 2px;flex-shrink:0}
/* 실행 바 */
.run-bar{display:flex;align-items:center;gap:10px;padding:10px 16px;position:relative}
.run-bar-left{display:flex;align-items:center;gap:8px;flex:1;flex-wrap:wrap}
.run-bar-right{display:flex;align-items:center;gap:6px;flex-shrink:0}
.schip{font-size:10.5px;padding:2px 8px;border-radius:10px;font-weight:500}
.schip.info{background:rgba(59,130,246,.1);color:#2563eb}
.schip.ok{background:rgba(34,197,94,.12);color:#15803d}
.schip.fail{background:rgba(239,68,68,.1);color:#dc2626}
.schip.pend{background:var(--bg-secondary);color:var(--text-tertiary)}
.prog-wrap{display:flex;align-items:center;gap:6px}
.prog-track{position:relative;width:120px;height:7px;background:var(--border-light);border-radius:4px;overflow:hidden}
.prog-ok{position:absolute;top:0;left:0;height:100%;background:#22c55e;border-radius:4px}
.prog-fail{position:absolute;top:0;height:100%;background:#ef4444;border-radius:4px}
.prog-txt{font-size:.68rem;color:var(--text-secondary);white-space:nowrap}
.run-status{display:flex;align-items:center;gap:5px;font-size:.72rem;color:#3b82f6;font-weight:600}
.run-big{display:flex;align-items:center;gap:6px;padding:8px 18px;border-radius:9px;border:none;background:#3b82f6;color:#fff;cursor:pointer;font-size:13px;font-weight:600;font-family:var(--font)}
.run-big:disabled{opacity:.5;cursor:not-allowed}
/* 매핑 테이블 */
.map-table{padding:0;overflow:hidden;max-height:260px;display:flex;flex-direction:column}
.mt-hdr{display:flex;align-items:center;gap:6px;padding:5px 14px;background:var(--bg-tertiary,#f3f4f6);font-size:10.5px;font-weight:600;color:var(--text-tertiary);border-bottom:0.5px solid var(--border-light);flex-shrink:0}
.mt-body{overflow-y:auto;flex:1}
.mt-row{display:flex;align-items:center;gap:6px;padding:5px 14px;border-bottom:0.5px solid var(--border-light);font-size:11px;cursor:pointer}
.mt-row:hover,.mt-row.active{background:var(--bg-hover)}
.mt-row:last-child{border-bottom:none}
.mn{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.7rem}
.mn.src{color:#2563eb}.mn.tgt{color:#059669}.mn.auto{color:#d97706;font-style:italic}
.rpill{display:inline-flex;align-items:center;font-size:10px;padding:2px 7px;border-radius:8px;font-weight:500;max-width:118px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rpill.ok{background:rgba(34,197,94,.12);color:#15803d}
.rpill.fail{background:rgba(239,68,68,.1);color:#dc2626}
.rpill.run{background:rgba(59,130,246,.1);color:#2563eb}
.rpill.pend{background:var(--bg-secondary);color:var(--text-tertiary)}
/* 결과 */
.result-frame{padding:0;overflow:hidden}
.res-banner{display:flex;align-items:center;gap:12px;padding:12px 16px;border-bottom:0.5px solid var(--border-light)}
.res-banner.match{background:rgba(34,197,94,.06)}.res-banner.warn{background:rgba(245,158,11,.06)}.res-banner.diff{background:rgba(239,68,68,.06)}
.res-icon{font-size:20px;font-weight:700;width:28px;text-align:center}
.match .res-icon{color:#16a34a}.warn .res-icon{color:#d97706}.diff .res-icon{color:#dc2626}
.res-title{font-size:.82rem;font-weight:700}.res-reason{font-size:.72rem;color:var(--text-secondary);margin-top:2px}
.res-stats{display:flex;gap:14px}.stat{display:flex;flex-direction:column;align-items:center;font-size:.68rem}
.stat span{color:var(--text-tertiary)}.stat b{font-size:.82rem}
.res-fname{font-size:.68rem;color:var(--text-tertiary);max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding:2px 8px;background:var(--bg-secondary);border-radius:6px}
.res-warn{padding:7px 16px;font-size:.75rem;color:#b45309;background:rgba(245,158,11,.06);border-bottom:0.5px solid rgba(245,158,11,.2)}
.res-err{padding:7px 16px;font-size:.75rem;color:#dc2626;background:rgba(239,68,68,.06);border-bottom:0.5px solid rgba(239,68,68,.2)}
.diff-section{border-bottom:0.5px solid var(--border-light)}
/* 불일치 카드 */

.diff-hdr{padding:7px 16px;font-size:.75rem;font-weight:700;color:#b45309;background:rgba(245,158,11,.06)}

.drow{display:flex;flex-wrap:wrap;align-items:center;gap:6px;padding:4px 16px;border-bottom:0.5px solid var(--border-light);font-size:.72rem}
.drow:last-child{border-bottom:none}
.drow-num{font-size:10px;background:rgba(245,158,11,.1);color:#b45309;padding:1px 7px;border-radius:8px;font-weight:600;flex-shrink:0}
.dcell{display:flex;align-items:center;gap:4px}
.dcol{font-weight:600;color:#1d4ed8;font-size:.68rem}.dsrc{color:#dc2626}.dtgt{color:#16a34a}.dne{color:var(--text-tertiary)}
.res-tables{display:grid;grid-template-columns:1fr 1fr;border-top:0.5px solid var(--border-light)}
.res-tbl-panel{display:flex;flex-direction:column;border-right:0.5px solid var(--border-light)}
.res-tbl-panel:last-child{border-right:none}
.res-tbl-hdr{padding:6px 12px;font-size:.72rem;font-weight:700;background:var(--bg-secondary);border-bottom:0.5px solid var(--border-light);flex-shrink:0}
.res-tbl-hdr.src{color:#2563eb}.res-tbl-hdr.tgt{color:#059669}

.rt{border-collapse:collapse;font-size:11px;white-space:nowrap;width:max-content;min-width:100%}
.rt th{padding:5px 10px;background:var(--bg-secondary);border-bottom:0.5px solid var(--border-mid);font-weight:600;position:sticky;top:0;z-index:1}
.rt td{padding:4px 10px;border-bottom:0.5px solid var(--border-light)}
.rt tr.diffrow td{background:rgba(239,68,68,.06)}
.rt td.diffcell{background:rgba(239,68,68,.15);font-weight:600}
.tbl-empty{padding:20px;text-align:center;font-size:.75rem;color:var(--text-tertiary)}
/* 스피너 */
.spinner{display:inline-block;width:14px;height:14px;border:2px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:spin .7s linear infinite;flex-shrink:0}
.spinner-sm{display:inline-block;width:10px;height:10px;border:1.5px solid rgba(59,130,246,.3);border-top-color:#3b82f6;border-radius:50%;animation:spin .7s linear infinite}
.restore-notice{display:flex;align-items:center;gap:8px;padding:5px 12px;background:rgba(59,130,246,.08);border-bottom:0.5px solid rgba(59,130,246,.2);font-size:.72rem;color:#2563eb}
/* 검토완료 */
.rpill.reviewed{background:rgba(5,150,105,.12);color:#059669;border:1px solid rgba(5,150,105,.25)}
.schip.reviewed{background:rgba(5,150,105,.12);color:#059669}
.review-chk{display:inline-flex;align-items:center;width:16px;height:16px;cursor:pointer;font-size:12px;color:var(--text-tertiary);flex-shrink:0;user-select:none;transition:color .15s}
.review-chk:hover{color:#059669}
.review-bar{display:flex;align-items:center;gap:10px;padding:7px 16px;background:rgba(5,150,105,.06);border-bottom:0.5px solid rgba(5,150,105,.2)}
.review-bar-chk{display:flex;align-items:center;gap:6px;cursor:pointer;font-size:.78rem;font-weight:500;color:var(--text-primary);user-select:none}
.review-bar-chk:hover{color:#059669}
.review-reason{font-size:.72rem;color:#059669;font-style:italic}
/* 결과 테이블 스크롤/정렬 */

.rt{border-collapse:collapse;font-size:11px;white-space:nowrap;width:max-content;min-width:100%}
.rt-th-sort{cursor:pointer;user-select:none;padding:5px 10px;background:var(--bg-secondary);border-bottom:0.5px solid var(--border-mid);font-weight:600;position:sticky;top:0;z-index:1;white-space:nowrap}
.rt-th-sort:hover{background:var(--bg-hover)}
.sort-ico{font-size:.6rem;margin-left:3px;color:var(--text-tertiary)}
.sort-badge{font-size:.65rem;padding:2px 6px;border-radius:6px;background:rgba(59,130,246,.1);color:#2563eb;margin-left:8px;font-weight:500}
.sort-clear{border:none;background:none;cursor:pointer;color:#2563eb;font-size:10px;margin-left:2px;padding:0}
/* 불일치 상세 테이블 */
.diff-legend{float:right;font-size:.65rem;display:flex;gap:8px}
.diff-legend-src{color:#dc2626}.diff-legend-tgt{color:#059669}
.diff-tbl{width:100%;border-collapse:collapse;font-size:.72rem}
.diff-tbl th{padding:5px 10px;background:var(--bg-tertiary,#f3f4f6);border-bottom:0.5px solid var(--border-mid);font-size:.68rem;font-weight:600;text-align:left;position:sticky;top:0}
.diff-tbl td{padding:4px 10px;border-bottom:0.5px solid var(--border-light);vertical-align:middle}
.diff-tr:hover td{background:var(--bg-hover)}
.diff-rownum{text-align:center;font-size:10px;background:rgba(245,158,11,.1);color:#b45309;font-weight:700;border-right:0.5px solid var(--border-light)}
.diff-col{font-weight:700;color:#1d4ed8;font-size:.68rem;white-space:nowrap}
.diff-src-val{color:#dc2626;font-family:monospace;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.diff-tgt-val{color:#059669;font-family:monospace;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.diff-ne{text-align:center;color:var(--text-tertiary);font-size:.8rem;padding:0 4px}
@keyframes spin{to{transform:rotate(360deg)}}

/* ── 불일치 상세 카드 ─────────────────────────── */
.diff-section{border-bottom:0.5px solid var(--border-light)}
.diff-hdr{display:flex;align-items:center;gap:8px;padding:7px 14px;background:var(--bg-secondary);border-bottom:0.5px solid var(--border-light);font-size:.75rem}
.diff-count-badge{background:rgba(245,158,11,.15);color:#b45309;padding:1px 7px;border-radius:8px;font-size:.67rem;font-weight:700}
.diff-legend-wrap{margin-left:auto;display:flex;align-items:center;gap:4px;font-size:.65rem;color:var(--text-tertiary)}
.dl-dot{display:inline-block;width:7px;height:7px;border-radius:50%;flex-shrink:0}
.diff-cards-wrap{display:flex;flex-wrap:wrap;gap:8px;padding:10px 14px;max-height:220px;overflow-y:auto}
.diff-card{border:0.5px solid var(--border-light);border-radius:8px;overflow:hidden;font-size:.71rem;min-width:240px;flex:1}
.diff-card-top{display:flex;align-items:center;gap:6px;padding:4px 9px;background:var(--bg-secondary);border-bottom:0.5px solid var(--border-light)}
.diff-num{background:rgba(245,158,11,.12);color:#b45309;padding:1px 6px;border-radius:5px;font-weight:700;font-size:.65rem}
.diff-type-badge{font-size:.64rem;padding:1px 6px;border-radius:5px;font-weight:600}
.diff-fields{display:flex;flex-direction:column}
.diff-field-row{display:grid;grid-template-columns:90px 1fr 16px 1fr;align-items:center;padding:3px 9px;border-bottom:0.5px solid var(--border-light);gap:4px}
.diff-field-row:last-child{border-bottom:none}
.diff-field-row:hover{background:var(--bg-hover)}
.df-col{font-weight:700;color:#1d4ed8;font-size:.66rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.df-src{color:#dc2626;font-family:monospace;font-size:.68rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.df-arrow{text-align:center;color:var(--text-tertiary)}
.df-tgt{color:#059669;font-family:monospace;font-size:.68rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.df-src.missing,.df-tgt.missing{color:var(--text-tertiary);font-style:italic}
/* ── 결과 테이블 (좌우 스크롤) ───────────────── */
.res-tables{display:grid;grid-template-columns:1fr 1fr;border-top:0.5px solid var(--border-light);min-height:0}
.res-tbl-panel{display:flex;flex-direction:column;border-right:0.5px solid var(--border-light);min-width:0;overflow:hidden}
.res-tbl-panel:last-child{border-right:none}
.res-tbl-hdr{display:flex;align-items:center;gap:5px;padding:5px 10px;background:var(--bg-secondary);border-bottom:0.5px solid var(--border-light);font-size:.72rem;flex-shrink:0}
.tbl-side-label{font-weight:600}
.tbl-row-cnt{font-weight:700}
.tbl-ms{color:var(--text-tertiary);font-size:.67rem}
.res-tbl-scroll{overflow-x:auto;overflow-y:auto;max-height:340px;-webkit-overflow-scrolling:touch}
.res-tbl-scroll::-webkit-scrollbar{height:6px;width:6px}
.res-tbl-scroll::-webkit-scrollbar-track{background:var(--bg-secondary);border-radius:3px}
.res-tbl-scroll::-webkit-scrollbar-thumb{background:var(--border-mid);border-radius:3px}
.res-tbl-scroll::-webkit-scrollbar-thumb:hover{background:var(--text-tertiary)}
.tbl-empty{padding:20px;text-align:center;color:var(--text-tertiary);font-size:.78rem}
.tbl-err{color:#dc2626}

/* ── 실행 컨트롤 버튼 ─────────────────────────── */
.ctrl-btn{display:inline-flex;align-items:center;gap:5px;padding:6px 14px;border-radius:8px;border:none;cursor:pointer;font-size:12px;font-weight:600;font-family:var(--font);transition:opacity .15s;position:relative;z-index:10}
.ctrl-btn:disabled{opacity:.4;cursor:not-allowed}
.pause-btn{background:rgba(245,158,11,.15);color:#b45309;border:1px solid rgba(245,158,11,.3)}
.pause-btn:hover:not(:disabled){background:rgba(245,158,11,.25)}
.stop-btn{background:rgba(220,38,38,.12);color:#dc2626;border:1px solid rgba(220,38,38,.25)}
.stop-btn:hover:not(:disabled){background:rgba(220,38,38,.22)}
.resume-btn{background:rgba(16,185,129,.12);color:#059669;border:1px solid rgba(16,185,129,.25)}
.resume-btn:hover:not(:disabled){background:rgba(16,185,129,.22)}
.run-counter{font-size:12px;font-weight:700;color:var(--text-secondary);padding:0 4px}
.run-status.paused{color:#b45309}
.rpill.run.paused{background:rgba(245,158,11,.15);color:#b45309;border-color:rgba(245,158,11,.3)}

/* ── 검증방식 선택 ───────────────────────────────── */
.sel-verify{min-width:130px}
.vmode-desc-bar{
  display:flex;flex-direction:column;gap:5px;
  padding:8px 16px 10px;
  background:var(--bg-secondary);
  border-bottom:0.5px solid var(--border-light);
  font-size:.72rem;
}
.vmode-tag{
  display:inline-block;
  background:rgba(59,130,246,.1);color:#2563eb;
  padding:1px 8px;border-radius:8px;
  font-size:.68rem;font-weight:700;margin-bottom:2px;
  width:fit-content;
}
.vmode-hint-text{
  font-size:.73rem;color:var(--text-secondary);font-weight:500;margin-bottom:3px;
}
.vmode-detail{display:flex;flex-wrap:wrap;gap:4px 16px}
.vmode-detail-item{
  display:flex;align-items:flex-start;gap:4px;
  font-size:.69rem;color:var(--text-tertiary);
  flex:1;min-width:200px;
}
.vmode-slide-enter-active,.vmode-slide-leave-active{transition:all .2s ease}
.vmode-slide-enter-from,.vmode-slide-leave-to{opacity:0;transform:translateY(-4px)}

/* ── 정규화 패널 ─────────────────────────────── */
.rpt-btn.active{background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue)}
.norm-panel{background:var(--bg-secondary);border-bottom:0.5px solid var(--border-light);padding:12px 16px;display:flex;flex-direction:column;gap:10px}
.norm-panel-title{display:flex;align-items:baseline;gap:8px;font-size:12px;font-weight:700;color:var(--text-primary)}
.norm-panel-sub{font-size:11px;font-weight:400;color:var(--text-tertiary)}
.norm-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
@media(max-width:700px){.norm-grid{grid-template-columns:1fr}}
.tbl-load-more{padding:6px 10px;text-align:center;border-top:0.5px solid var(--border-light)}
.load-more-btn{font-size:.7rem;color:#2563eb;background:rgba(37,99,235,.06);border:0.5px solid rgba(37,99,235,.2);border-radius:6px;padding:4px 14px;cursor:pointer;transition:background .15s}
.load-more-btn:hover{background:rgba(37,99,235,.12)}
.tbl-all-shown{padding:5px 10px;text-align:center;font-size:.68rem;color:var(--text-tertiary)}
.hint-panel{margin:10px 0;border-radius:8px;overflow:hidden;border:0.5px solid var(--border-mid)}
.hint-panel-hdr{display:flex;align-items:center;gap:6px;padding:7px 12px;background:rgba(37,99,235,.06);font-size:.72rem;font-weight:700;color:var(--text-secondary);border-bottom:0.5px solid var(--border-light)}
.hint-item{display:flex;gap:10px;padding:10px 14px;border-bottom:0.5px solid var(--border-light)}
.hint-item:last-child{border-bottom:none}
.hint-item.hint-error{background:rgba(220,38,38,.04)}
.hint-item.hint-warn{background:rgba(245,158,11,.04)}
.hint-item.hint-info{background:rgba(37,99,235,.03)}
.hint-icon{font-size:1.1rem;line-height:1.4;flex-shrink:0}
.hint-body{display:flex;flex-direction:column;gap:3px;min-width:0}
.hint-title{font-size:.75rem;font-weight:700;color:var(--text-primary)}
.hint-msg{font-size:.72rem;color:var(--text-secondary);line-height:1.5}
.hint-action{font-size:.71rem;color:#2563eb;font-weight:600;margin-top:2px}
.norm-group{background:var(--bg-primary);border:0.5px solid var(--border-light);border-radius:8px;padding:10px 12px;display:flex;flex-direction:column;gap:6px}
.norm-group-label{display:flex;flex-direction:column;gap:4px}
.norm-chk{display:flex;align-items:center;gap:6px;font-size:12px;font-weight:500;color:var(--text-primary);cursor:pointer}
.norm-chk input{accent-color:var(--accent-blue);width:13px;height:13px}
.norm-sub{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:2px}
.norm-hint{font-size:10px;color:var(--text-tertiary);font-style:italic}
.norm-footer{display:flex;align-items:center;gap:8px}
.norm-apply-btn{padding:5px 14px;border-radius:6px;border:none;background:var(--accent-blue);color:#fff;font-size:12px;font-weight:600;cursor:pointer;font-family:var(--font)}
.norm-apply-btn:hover{opacity:.85}
.norm-reset-btn{padding:5px 10px;border-radius:6px;border:0.5px solid var(--border-mid);background:transparent;font-size:12px;color:var(--text-secondary);cursor:pointer;font-family:var(--font)}
.norm-status{font-size:11px;color:var(--text-tertiary);font-style:italic;margin-left:4px}
/* ── 불일치 테이블 ───────────────────────────── */
.diff-tbl-wrap{overflow-x:auto;max-height:260px;overflow-y:auto}
.diff-tbl-wrap::-webkit-scrollbar{height:5px;width:5px}
.diff-tbl-wrap::-webkit-scrollbar-thumb{background:var(--border-mid);border-radius:3px}
.diff-tbl{border-collapse:collapse;font-size:.7rem;width:100%;min-width:max-content}
.diff-tbl thead th{position:sticky;top:0;background:var(--bg-secondary);padding:5px 10px;text-align:left;font-weight:700;font-size:.67rem;color:var(--text-secondary);border-bottom:0.5px solid var(--border-mid);white-space:nowrap}
.diff-tbl tbody td{padding:4px 10px;border-bottom:0.5px solid var(--border-light);white-space:nowrap}
.diff-tbl tbody tr:hover td{background:var(--bg-hover)}
.dt-no{width:30px;text-align:center;color:var(--text-tertiary);font-size:.65rem}
.dt-type{width:64px}
.dt-badge{font-size:.62rem;padding:1px 6px;border-radius:8px;font-weight:700;white-space:nowrap}
.dt-val{max-width:180px;overflow:hidden;text-overflow:ellipsis}
.dt-src td,.dt-tgt td,.dt-both td{background:transparent}
.diff-tbl tr.dt-src td{background:rgba(220,38,38,.03)}
.diff-tbl tr.dt-tgt td{background:rgba(5,150,105,.03)}
.diff-tbl tr.dt-both td{background:rgba(245,158,11,.03)}
.dt-missing{color:var(--text-tertiary);font-style:italic}
.dt-extra{color:#059669;font-weight:600}
.dt-changed{color:#b45309}
.dt-col{font-size:.67rem;color:var(--text-secondary)}


/* ── 신규 기능 CSS ── */
.opt-row::-webkit-scrollbar{height:3px}
.opt-row::-webkit-scrollbar-thumb{background:var(--border-mid);border-radius:2px}
.sel-verify{width:120px}
.norm-panel{background:var(--bg-secondary);border-top:2px solid #2563eb;border-bottom:0.5px solid var(--border-light);padding:12px 16px;display:flex;flex-direction:column;gap:10px;box-shadow:0 2px 8px rgba(37,99,235,.06)}
.norm-panel-title{display:flex;align-items:baseline;gap:8px;font-size:12px;font-weight:700;color:var(--text-primary)}
.norm-panel-sub{font-size:11px;font-weight:400;color:var(--text-tertiary)}
.norm-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
.tbl-load-more{padding:6px 10px;text-align:center;border-top:0.5px solid var(--border-light)}
.load-more-btn{font-size:.7rem;color:#2563eb;background:rgba(37,99,235,.06);border:0.5px solid rgba(37,99,235,.2);border-radius:6px;padding:4px 14px;cursor:pointer;transition:background .15s}
.load-more-btn:hover{background:rgba(37,99,235,.12)}
.tbl-all-shown{padding:5px 10px;text-align:center;font-size:.68rem;color:var(--text-tertiary)}
.hint-panel{margin:10px 0;border-radius:8px;overflow:hidden;border:0.5px solid var(--border-mid)}
.hint-panel-hdr{display:flex;align-items:center;gap:6px;padding:7px 12px;background:rgba(37,99,235,.06);font-size:.72rem;font-weight:700;color:var(--text-secondary);border-bottom:0.5px solid var(--border-light)}
.hint-item{display:flex;gap:10px;padding:10px 14px;border-bottom:0.5px solid var(--border-light)}
.hint-item:last-child{border-bottom:none}
.hint-item.hint-error{background:rgba(220,38,38,.04)}
.hint-item.hint-warn{background:rgba(245,158,11,.04)}
.hint-item.hint-info{background:rgba(37,99,235,.03)}
.hint-icon{font-size:1.1rem;line-height:1.4;flex-shrink:0}
.hint-body{display:flex;flex-direction:column;gap:3px;min-width:0}
.hint-title{font-size:.75rem;font-weight:700;color:var(--text-primary)}
.hint-msg{font-size:.72rem;color:var(--text-secondary);line-height:1.5}
.hint-action{font-size:.71rem;color:#2563eb;font-weight:600;margin-top:2px}
.norm-group{background:var(--bg-primary);border:1px solid var(--border-light);border-radius:8px;padding:10px 12px;display:flex;flex-direction:column;gap:6px;transition:border-color .15s}
.norm-group:hover{border-color:rgba(37,99,235,.35)}
.norm-chk{display:flex;align-items:center;gap:6px;font-size:12px;font-weight:500;color:var(--text-primary);cursor:pointer}
.norm-chk input{accent-color:var(--accent-blue);width:13px;height:13px}
.norm-sub{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:2px}
.norm-hint{font-size:10px;color:var(--text-tertiary);font-style:italic}
.norm-footer{display:flex;align-items:center;gap:8px}
.norm-apply-btn{padding:5px 14px;border-radius:6px;border:none;background:var(--accent-blue);color:#fff;font-size:12px;font-weight:600;cursor:pointer;font-family:var(--font)}
.norm-reset-btn{padding:5px 10px;border-radius:6px;border:0.5px solid var(--border-mid);background:transparent;font-size:12px;color:var(--text-secondary);cursor:pointer;font-family:var(--font)}
.norm-status{font-size:11px;color:var(--text-tertiary);font-style:italic;margin-left:4px}
.vmode-desc-bar{display:flex;flex-direction:column;gap:5px;padding:8px 16px 10px;background:var(--bg-secondary);border-bottom:0.5px solid var(--border-light);border-left:3px solid #2563eb;font-size:.72rem}
.vmode-tag{display:inline-block;background:rgba(37,99,235,.1);color:#2563eb;border:1px solid rgba(37,99,235,.25);padding:1px 8px;border-radius:8px;font-size:.68rem;font-weight:700;margin-bottom:2px;width:fit-content}
.vmode-hint-text{font-size:.73rem;color:var(--text-secondary);font-weight:500;margin-bottom:3px}
.vmode-detail{display:flex;flex-wrap:wrap;gap:4px 16px}
.vmode-detail-item{display:flex;align-items:flex-start;gap:4px;font-size:.69rem;color:var(--text-tertiary);flex:1;min-width:200px}
.vmode-slide-enter-active,.vmode-slide-leave-active{transition:all .2s ease}
.vmode-slide-enter-from,.vmode-slide-leave-to{opacity:0;transform:translateY(-4px)}
.res-tables{display:grid;grid-template-columns:1fr 1fr;gap:0;border-top:0.5px solid var(--border-light)}
.res-tbl-panel{display:flex;flex-direction:column;min-height:0}
.res-tbl-panel:first-child{border-right:0.5px solid var(--border-light)}
.res-tbl-hdr{display:flex;align-items:center;gap:6px;padding:5px 10px;font-size:.68rem;font-weight:600;background:var(--bg-secondary);border-bottom:0.5px solid var(--border-light);flex-shrink:0}
.res-tbl-hdr.src{color:var(--text-info)}.res-tbl-hdr.tgt{color:var(--text-success)}
.res-tbl-scroll{overflow:auto;max-height:240px;flex:1}
.rt{border-collapse:collapse;font-size:.68rem;width:max-content;min-width:100%}
.rt th{position:sticky;top:0;background:var(--bg-secondary);padding:4px 8px;text-align:left;font-weight:700;white-space:nowrap;border-bottom:0.5px solid var(--border-mid);cursor:pointer;user-select:none;color:var(--text-secondary);font-size:.65rem}
.rt td{padding:3px 8px;border-bottom:0.5px solid var(--border-light);white-space:nowrap;max-width:200px;overflow:hidden;text-overflow:ellipsis}
.rt tbody tr:hover td{background:var(--bg-hover)}
.rt tbody tr.diffrow td{background:rgba(220,38,38,.05)}
.rt td.diffcell{background:rgba(220,38,38,.15);color:#dc2626;font-weight:600}
.sort-ico{font-size:.58rem;color:var(--text-tertiary);margin-left:2px}
.sort-badge{font-size:.62rem;color:var(--text-info);background:var(--bg-info);padding:1px 6px;border-radius:8px;display:flex;align-items:center;gap:3px}
.sort-clear{border:none;background:transparent;cursor:pointer;font-size:.6rem;color:var(--text-tertiary);padding:0 1px}
.frow-chk{display:flex;align-items:center;padding:0 4px 0 2px;flex-shrink:0}
.frow-chk input{width:12px;height:12px;accent-color:var(--accent-blue);cursor:pointer}
.frow-selected{background:rgba(59,130,246,.06) !important}
.run-sel{background:linear-gradient(135deg,#7c3aed,#2563eb) !important;margin-right:4px}
.hdr-btn.blue{color:#2563eb;border-color:#2563eb}
.res-banner{display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:0.5px solid var(--border-light)}
.res-banner.match{background:rgba(5,150,105,.06)}.res-banner.warn{background:rgba(245,158,11,.06)}.res-banner.diff{background:rgba(220,38,38,.06)}
.res-icon{font-size:18px;flex-shrink:0}
.res-title{font-size:.8rem;font-weight:700;color:var(--text-primary)}
.res-reason{font-size:.7rem;color:var(--text-secondary);margin-top:2px}
.res-stats{display:flex;gap:8px;margin-left:auto;flex-shrink:0}
.stat{display:flex;flex-direction:column;align-items:center;gap:1px}
.stat span{font-size:.62rem;color:var(--text-tertiary)}.stat b{font-size:.75rem;font-weight:700;color:var(--text-primary)}
.res-fname{font-size:.65rem;color:var(--text-tertiary);max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex-shrink:0}
.res-pkinfo{padding:4px 14px;font-size:.7rem;background:rgba(99,102,241,.06);color:#4f46e5;border-bottom:0.5px solid rgba(99,102,241,.12)}
.diff-tbl-wrap{overflow-x:auto;max-height:260px;overflow-y:auto}
.diff-tbl{border-collapse:collapse;font-size:.7rem;width:100%;min-width:max-content}
.diff-tbl thead th{position:sticky;top:0;background:var(--bg-secondary);padding:5px 10px;text-align:left;font-weight:700;font-size:.67rem;color:var(--text-secondary);border-bottom:0.5px solid var(--border-mid);white-space:nowrap}
.diff-tbl tbody td{padding:4px 10px;border-bottom:0.5px solid var(--border-light);white-space:nowrap}
.dt-no{width:30px;text-align:center;color:var(--text-tertiary);font-size:.65rem}
.dt-type{width:64px}.dt-badge{font-size:.62rem;padding:1px 6px;border-radius:8px;font-weight:700;white-space:nowrap}
.dt-val{max-width:180px;overflow:hidden;text-overflow:ellipsis}
.dt-missing{color:var(--text-tertiary);font-style:italic}.dt-extra{color:#059669;font-weight:600}.dt-changed{color:#b45309}
/* run-bar CSS는 위에서 정의됨 */

.sum-bar{display:flex;gap:8px;flex-wrap:wrap;padding:6px 10px;flex-shrink:0;border-top:0.5px solid var(--border-light)}

/* ══════════════════════════════════════════════════
   Check Sum 패널
══════════════════════════════════════════════════ */
.hdr-btn-summary { border-color:rgba(99,102,241,.35); color:#4f46e5; }
.hdr-btn-summary:hover, .hdr-btn-summary.summary-active { background:rgba(99,102,241,.1); border-color:#4f46e5; }

.summary-slide-enter-active, .summary-slide-leave-active { transition:opacity .18s, transform .18s; }
.summary-slide-enter-from,   .summary-slide-leave-to     { opacity:0; transform:translateY(-4px); }

/* ══════════════════════════════════════════════════
   Check Sum 패널
══════════════════════════════════════════════════ */
.checksum-panel {
  background: var(--bg-primary);
  border: 0.5px solid var(--border-light);
  border-radius: var(--radius-lg);
  overflow: hidden;
  margin-bottom: 10px;
}

/* 헤더 */
.cs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 7px 12px;
  border-bottom: 0.5px solid var(--border-light);
  background: var(--bg-secondary);
  gap: 10px;
  flex-wrap: wrap;
}
.cs-title {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}
.cs-subtitle {
  font-size: 11px;
  font-weight: 400;
  color: var(--text-tertiary);
}
.cs-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.cs-meta-chip {
  font-size: .68rem;
  color: var(--text-tertiary);
  background: var(--bg-primary);
  border: 0.5px solid var(--border-light);
  padding: 1px 7px;
  border-radius: 8px;
}
.cs-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: .68rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 8px;
}
.cs-badge-ok   { background: var(--bg-success); color: var(--text-success); }
.cs-badge-fail { background: var(--bg-danger);  color: var(--text-danger); }

/* 테이블 래퍼 */
.cs-table-wrap {
  overflow-x: auto;
  max-height: 60vh;
  overflow-y: auto;
}
.cs-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: .72rem;
}
.cs-th {
  background: var(--bg-secondary);
  font-size: .68rem;
  font-weight: 600;
  color: var(--text-secondary);
  padding: 4px 10px;
  text-align: left;
  border-bottom: 0.5px solid var(--border-mid);
  white-space: nowrap;
  position: sticky;
  top: 0;
  z-index: 1;
  cursor: pointer;
  user-select: none;
}
.cs-th:hover { color: var(--text-primary); }
.cs-th-num    { text-align: right; width: 155px; }
.cs-th-status { text-align: center; width: 38px; }
.cs-th-item   { width: auto; }
.cs-th-diff   { text-align: right; width: 90px; }

.cs-sico { display:inline-block; margin-left:3px; font-size:10px; opacity:.45; }

/* 소스/타겟 점 */
.cs-src-dot {
  display: inline-block;
  width: 7px; height: 7px;
  border-radius: 50%;
  background: #3b82f6;
  margin-right: 3px;
  vertical-align: middle;
}
.cs-tgt-dot {
  display: inline-block;
  width: 7px; height: 7px;
  border-radius: 50%;
  background: #22c55e;
  margin-right: 3px;
  vertical-align: middle;
}

/* 행 */
.cs-row { transition: background .1s; }
.cs-row-ok:hover   td { background: rgba(34,197,94,.04); }
.cs-row-fail       td { background: rgba(239,68,68,.03); }
.cs-row-fail:hover td { background: rgba(239,68,68,.08); }

/* 셀 */
.cs-td {
  padding: 3px 10px;
  font-size: .72rem;
  border-bottom: 0.5px solid var(--border-light);
  vertical-align: middle;
}
.cs-table tr:last-child .cs-td { border-bottom: none; }

/* 행 번호 */
.cs-row-num { font-size:.62rem; color:var(--text-tertiary); margin-right:5px; min-width:14px; display:inline-block; text-align:right; opacity:.5; }

.cs-td-item {
  font-weight: 600;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cs-td-num {
  text-align: right;
  font-family: 'Consolas','SF Mono',monospace;
  font-size: .72rem;
  color: var(--text-primary);
  letter-spacing: -.2px;
}
.cs-td-diff {
  text-align: right;
  font-family: 'Consolas','SF Mono',monospace;
  font-size: .72rem;
  font-weight: 600;
}
.cs-diff-ok  { color: var(--text-tertiary); }
.cs-diff-bad { color: var(--text-danger); }
.cs-td-status { text-align: center; }

.cs-ico-ok, .cs-ico-fail { display:inline-flex; align-items:center; justify-content:center; }

/* 빈 상태 */
.cs-empty { text-align:center; padding:20px; color:var(--text-tertiary); font-size:.72rem; }


.not-run-notice {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  font-size: 12.5px;
  color: var(--text-secondary);
  margin-bottom: 0;
}
</style>