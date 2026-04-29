<template>
  <div>
    <div class="page-title">Job 생성 위저드</div>
    <div class="page-desc">마이그레이션 Job을 단계별로 설정합니다</div>

    <!-- Steps -->
    <div class="card steps-bar">
      <div v-for="(st,i) in steps" :key="i" class="step" :class="{active:cur===i,done:cur>i}">
        <div class="step-num">
          <svg v-if="cur>i" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" style="width:11px;height:11px"><polyline points="2,8 6,12 14,4"/></svg>
          <span v-else>{{ i+1 }}</span>
        </div>
        <span class="step-lbl">{{ st }}</span>
      </div>
    </div>

    <div class="card wiz-body">

      <!-- ── Step 0: DB 선택 ── -->
      <template v-if="cur===0">
        <div class="conn-summary" v-if="connector.bothConnected">
          <span class="cs-item">
            <span class="mini-ico" :style="{background:m(connector.source.dbType)?.bg,color:m(connector.source.dbType)?.color}">{{ m(connector.source.dbType)?.label }}</span>
            {{ connector.source.database }} ({{ connector.source.host }})
          </span>
          <span class="cs-arrow">→</span>
          <span class="cs-item">
            <span class="mini-ico" :style="{background:m(connector.target.dbType)?.bg,color:m(connector.target.dbType)?.color}">{{ m(connector.target.dbType)?.label }}</span>
            {{ connector.target.database }} ({{ connector.target.host }})
          </span>
          <span class="cs-ok">연결 완료 ✓</span>
        </div>
        <div v-if="!connector.bothConnected" class="warn-banner" style="margin-bottom:14px">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px;flex-shrink:0"><path d="M8 2L14 14H2L8 2z"/><line x1="8" y1="7" x2="8" y2="10"/></svg>
          소스와 타겟 DB가 연결되지 않았습니다.
          <button class="act-btn" style="margin-left:8px" @click="$router.push('/connector')">커넥터 관리</button>
        </div>
        <h4 class="wh">소스 DB</h4>
        <div class="db-grid">
          <div v-for="d in srcDbs" :key="d.value" class="db-card"
               :class="{sel:form.srcDb===d.value,cur:connector.source.dbType===d.value}"
               @click="form.srcDb=d.value">
            <div class="db-card-ico" :style="{background:d.bg,color:d.color}">{{ d.label }}</div>
            <div class="db-card-name">{{ d.name }}</div>
            <div v-if="connector.source.dbType===d.value" class="db-card-badge">연결됨</div>
          </div>
        </div>
        <h4 class="wh" style="margin-top:18px">타겟 DB</h4>
        <div class="db-grid">
          <div v-for="d in tgtDbs" :key="d.value" class="db-card"
               :class="{sel:form.tgtDb===d.value,cur:connector.target.dbType===d.value}"
               @click="form.tgtDb=d.value">
            <div class="db-card-ico" :style="{background:d.bg,color:d.color}">{{ d.label }}</div>
            <div class="db-card-name">{{ d.name }}</div>
            <div v-if="connector.target.dbType===d.value" class="db-card-badge tgt">연결됨</div>
          </div>
        </div>
      </template>

      <!-- ── Step 1: 테이블 + 오브젝트 선택 ── -->
      <template v-if="cur===1">
        <!-- 탭: 테이블 / 오브젝트 -->
        <div class="obj-tabs">
          <button v-for="t in objTabs" :key="t.v"
            class="otab" :class="{active:objTab===t.v, 'all-sel': isAllSelForTab(t.v)}" @click="toggleTab(t.v)"
            :title="objTab===t.v ? (isAllSelForTab(t.v)?'클릭하면 전체 해제':'클릭하면 전체 선택') : t.label + ' 탭으로 이동'">
            <span class="otab-ico">{{ t.icon }}</span>
            {{ t.label }}
            <span class="otab-cnt" v-if="getSelCount(t.v)>0">{{ getSelCount(t.v) }}</span>
            <span v-if="objTab===t.v" class="otab-toggle-hint">{{ isAllSelForTab(t.v) ? '✓전체' : '전체↑' }}</span>
          </button>
          <div style="margin-left:auto;display:flex;gap:6px;align-items:center">
            <input type="text" v-model="objSearch" placeholder="검색..." style="padding:4px 10px;font-size:12px;width:140px"/>
            <button class="act-btn" @click="selAllTab">전체 선택</button>
            <button class="act-btn" @click="clearTab">해제</button>
          </div>
        </div>

        <!-- 로딩 -->
        <div v-if="loadingObjs" class="empty-state" style="padding:30px">
          <span class="spinner" style="width:18px;height:18px;display:inline-block;margin-right:8px"></span>
          {{ connector.source.database }} 오브젝트 조회 중...
        </div>
        <div v-else-if="objError" class="err-banner">
          {{ objError }}
          <button class="act-btn" style="margin-left:8px" @click="loadAll">다시 시도</button>
        </div>

        <!-- 테이블 목록 -->
        <template v-else-if="objTab==='tables'">
          <div class="info-banner" style="margin-bottom:8px" v-if="allTables.length">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:12px;height:12px;flex-shrink:0"><circle cx="8" cy="8" r="7"/><line x1="8" y1="5" x2="8" y2="9"/></svg>
            <b>{{ connector.source.database }}</b> — 테이블 {{ allTables.length }}개
          </div>
          <div class="obj-list">
            <label v-for="t in filteredTables" :key="t.table_name" class="obj-row">
              <input type="checkbox" v-model="form.tables" :value="t.table_name"/>
              <span class="obj-type-ico tbl">▤</span>
              <span class="obj-name">{{ t.schema_name }}.{{ t.table_name }}</span>
              <span class="obj-meta">{{ fmtRows(t.row_count||0) }} rows</span>
              <span class="obj-meta">{{ t.size_mb ? t.size_mb+'MB' : '' }}</span>
            </label>
          </div>
          <div class="sel-summary">{{ form.tables.length }}개 선택 · 예상 {{ fmtRows(selRows) }} rows</div>
        </template>

        <!-- 프로시저 -->
        <template v-else-if="objTab==='procedures'">
          <div class="obj-list">
            <label v-for="o in filteredObjs('procedures')" :key="o.name" class="obj-row">
              <input type="checkbox" v-model="form.procedures" :value="o.name"/>
              <span class="obj-type-ico proc">⚙</span>
              <span class="obj-name">{{ o.name }}</span>
              <span class="obj-meta">PROCEDURE</span>
              <span class="obj-meta">{{ o.created?.slice(0,10) }}</span>
            </label>
            <div v-if="!filteredObjs('procedures').length" class="empty-state" style="padding:16px">프로시저가 없습니다</div>
          </div>
        </template>

        <!-- 함수 -->
        <template v-else-if="objTab==='functions'">
          <div class="obj-list">
            <label v-for="o in filteredObjs('functions')" :key="o.name" class="obj-row">
              <input type="checkbox" v-model="form.functions" :value="o.name"/>
              <span class="obj-type-ico func">ƒ</span>
              <span class="obj-name">{{ o.name }}</span>
              <span class="obj-meta">{{ o.return_type }}</span>
              <span class="obj-meta">FUNCTION</span>
            </label>
            <div v-if="!filteredObjs('functions').length" class="empty-state" style="padding:16px">함수가 없습니다</div>
          </div>
        </template>

        <!-- 트리거 -->
        <template v-else-if="objTab==='triggers'">
          <div class="obj-list">
            <label v-for="o in filteredObjs('triggers')" :key="o.name" class="obj-row">
              <input type="checkbox" v-model="form.triggers" :value="o.name"/>
              <span class="obj-type-ico trig">⚡</span>
              <span class="obj-name">{{ o.name }}</span>
              <span class="obj-meta">{{ o.event }}</span>
              <span class="obj-meta">on {{ o.table }}</span>
            </label>
            <div v-if="!filteredObjs('triggers').length" class="empty-state" style="padding:16px">트리거가 없습니다</div>
          </div>
        </template>

        <!-- 뷰 -->
        <template v-else-if="objTab==='views'">
          <div class="obj-list">
            <label v-for="o in filteredObjs('views')" :key="o.name" class="obj-row">
              <input type="checkbox" v-model="form.views" :value="o.name"/>
              <span class="obj-type-ico view">👁</span>
              <span class="obj-name">{{ o.name }}</span>
              <span class="obj-meta">VIEW</span>
            </label>
            <div v-if="!filteredObjs('views').length" class="empty-state" style="padding:16px">뷰가 없습니다</div>
          </div>
        </template>

        <!-- 전체 선택 요약 -->
        <div class="total-sel-bar" v-if="totalSelCount>0">
          <span>선택 합계:</span>
          <span v-if="form.tables.length"    class="sel-chip tbl">테이블 {{ form.tables.length }}</span>
          <span v-if="form.procedures.length" class="sel-chip proc">프로시저 {{ form.procedures.length }}</span>
          <span v-if="form.functions.length"  class="sel-chip func">함수 {{ form.functions.length }}</span>
          <span v-if="form.triggers.length"   class="sel-chip trig">트리거 {{ form.triggers.length }}</span>
          <span v-if="form.views.length"      class="sel-chip view">뷰 {{ form.views.length }}</span>
        </div>
      </template>

      <!-- ── Step 2: 변환 규칙 ── -->
      <template v-if="cur===2">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
          <h4 class="wh" style="margin:0">타입 변환 경고 분석</h4>
          <div style="margin-left:auto;display:flex;align-items:center;gap:8px">
            <span style="font-size:11px;color:var(--text-tertiary)">자동 수정 전체</span>
            <div class="toggle" :class="{on:autoFixAll}" @click="toggleAutoFixAll"></div>
          </div>
        </div>
        <div v-if="analyzingWarn" class="info-banner">
          <span class="spinner" style="width:12px;height:12px;display:inline-block;margin-right:6px"></span>
          선택 오브젝트 {{ totalSelCount }}개 분석 중...
        </div>
        <template v-else>
          <div v-if="warnCount>0" class="warn-banner" style="margin-bottom:10px">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px;flex-shrink:0"><path d="M8 2L14 14H2L8 2z"/><line x1="8" y1="7" x2="8" y2="10"/></svg>
            경고 <b>{{ warnCount }}건</b> — 자동 수정 가능 {{ autoFixableCount }}건
          </div>
          <div v-else class="card" style="padding:10px 14px;border-color:var(--accent-green)">
            <span style="color:var(--text-success);font-size:12.5px;font-weight:500">✓ 변환 경고가 없습니다</span>
          </div>
          <div v-for="(rule,ri) in warnRules" :key="ri" class="rule-card" :class="'rule-'+rule.level" v-show="rule.level!=='none'">
            <div class="rule-header" @click="openRules[ri]=!openRules[ri]">
              <span class="rule-level-dot" :class="'dot-'+rule.level"></span>
              <div class="rule-title-area">
                <span class="rule-title">{{ rule.title }}</span>
                <span class="rule-types">
                  <span class="type-chip src">{{ rule.src_type }}</span>
                  <span style="margin:0 4px;color:var(--text-tertiary)">→</span>
                  <span class="type-chip tgt">{{ rule.tgt_type }}</span>
                </span>
              </div>
              <div class="rule-right">
                <span v-if="rule.affected_count>0" class="affected-badge">{{ rule.affected_count }}개 컬럼</span>
                <span v-else class="affected-none">해당 없음</span>
                <div v-if="rule.auto_fix&&rule.affected_count>0" class="fix-toggle" @click.stop>
                  <span class="fix-label">자동 수정</span>
                  <div class="toggle sm" :class="{on:rule.fixEnabled}" @click="rule.fixEnabled=!rule.fixEnabled"></div>
                </div>
                <svg :style="{transform:openRules[ri]?'rotate(90deg)':'',transition:'transform .2s'}" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:11px;height:11px;flex-shrink:0"><polyline points="3,2 9,6 3,10"/></svg>
              </div>
            </div>
            <div v-if="openRules[ri]" class="rule-detail">
              <div class="rule-info-grid">
                <div class="ri-box reason"><div class="ri-label">원인</div><div class="ri-text">{{ rule.reason }}</div></div>
                <div class="ri-box fix" :class="{active:rule.fixEnabled}">
                  <div class="ri-label">자동 수정 방법</div>
                  <div class="ri-text">{{ rule.fix }}</div>
                  <div v-if="rule.fixEnabled" class="fix-on-badge">✓ 자동 수정 ON</div>
                </div>
              </div>
              <div v-if="rule.affected_tables?.length" class="affected-list">
                <div class="al-header">영향받는 테이블 · 컬럼 ({{ rule.affected_tables.length }}개)</div>
                <div class="al-grid">
                  <div v-for="(a,ai) in rule.affected_tables" :key="ai" class="al-item">
                    <span class="al-table">{{ a.table }}</span><span class="al-dot">·</span>
                    <span class="al-col">{{ a.column }}</span>
                    <span class="al-type">{{ a.col_type }}</span>
                    <span v-if="rule.fixEnabled" class="al-fix-ico">✓</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </template>

      <!-- ── Step 3: 실행 옵션 ── -->
      <template v-if="cur===3">
        <div class="opts-grid">
          <div>
            <div class="field-label">Job 이름 *</div>
            <input type="text" v-model="form.name" :placeholder="`${connector.source.database} → ${connector.target.database} 이관`" :class="{err:v3&&!form.name}"/>
            <div class="field-label">배치 크기 (rows)</div>
            <input type="number" v-model="form.batchSize" min="100" max="100000"/>
            <div class="field-label">병렬 처리 수</div>
            <div class="sel-wrap"><select v-model="form.workers"><option v-for="n in [1,2,4,8,16]" :key="n" :value="n">{{ n }}개 스레드</option></select><div class="chev"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div></div>
            <div class="field-label">오류 처리</div>
            <div class="sel-wrap"><select v-model="form.onError"><option value="skip">오류 row 건너뜀</option><option value="retry">재시도 후 건너뜀</option><option value="abort">즉시 중단</option></select><div class="chev"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div></div>
          </div>
          <div>
            <div class="field-label">타겟 테이블 처리</div>
            <label class="opt-chk"><input type="checkbox" v-model="form.truncate"/> 이관 전 타겟 TRUNCATE</label>
            <label class="opt-chk"><input type="checkbox" v-model="form.createTbl"/> 타겟 테이블 없으면 자동 생성</label>
            <label class="opt-chk"><input type="checkbox" v-model="form.withIdx"/> 인덱스 함께 생성</label>
            <label class="opt-chk" v-if="hasObjects"><input type="checkbox" v-model="form.convertObjs"/> 오브젝트 방언 자동 변환 후 이관</label>
          </div>
        </div>
      </template>

      <!-- ── Step 4: 검토 & 실행 + 스케줄링 ── -->
      <template v-if="cur===4">
        <h4 class="wh">설정 최종 검토</h4>
        <div class="review-grid">
          <div class="rv-item"><span class="rv-l">Job 이름</span><span class="rv-v">{{ form.name }}</span></div>
          <div class="rv-item"><span class="rv-l">소스 DB</span><span class="rv-v">{{ form.srcDb }} / {{ connector.source.database }}</span></div>
          <div class="rv-item"><span class="rv-l">타겟 DB</span><span class="rv-v">{{ form.tgtDb }} / {{ connector.target.database }}</span></div>
          <div class="rv-item"><span class="rv-l">테이블</span><span class="rv-v">{{ form.tables.length }}개</span></div>
          <div class="rv-item"><span class="rv-l">프로시저</span><span class="rv-v">{{ form.procedures.length }}개</span></div>
          <div class="rv-item"><span class="rv-l">함수</span><span class="rv-v">{{ form.functions.length }}개</span></div>
          <div class="rv-item"><span class="rv-l">트리거</span><span class="rv-v">{{ form.triggers.length }}개</span></div>
          <div class="rv-item"><span class="rv-l">뷰</span><span class="rv-v">{{ form.views.length }}개</span></div>
          <div class="rv-item"><span class="rv-l">배치 크기</span><span class="rv-v">{{ form.batchSize.toLocaleString() }}</span></div>
          <div class="rv-item"><span class="rv-l">자동 수정</span><span class="rv-v" style="color:var(--text-success)">{{ autoFixEnabledCount }}건</span></div>
          <div class="rv-item"><span class="rv-l">오브젝트 변환</span><span class="rv-v">{{ form.convertObjs?'자동 변환':'수동' }}</span></div>
          <div class="rv-item"><span class="rv-l">TRUNCATE</span><span class="rv-v">{{ form.truncate?'예':'아니오' }}</span></div>
        </div>

        <!-- ── 스케줄링 섹션 ── -->
        <div class="sched-section">
          <div class="sched-header">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px"><rect x="1" y="2" width="14" height="13" rx="1"/><line x1="1" y1="6" x2="15" y2="6"/><line x1="5" y1="1" x2="5" y2="4"/><line x1="11" y1="1" x2="11" y2="4"/></svg>
            <span class="sched-title">실행 스케줄</span>
          </div>

          <!-- 실행 방식 선택 카드 -->
          <div class="sched-mode-row">
            <div class="sched-mode-card" :class="{active: !schedEnabled}" @click="schedEnabled=false">
              <div class="smc-ico">
                <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" style="width:22px;height:22px">
                  <circle cx="10" cy="10" r="8"/>
                  <polygon points="8,6.5 15,10 8,13.5" fill="currentColor" stroke="none"/>
                </svg>
              </div>
              <div class="smc-body">
                <div class="smc-title">즉시 실행</div>
                <div class="smc-desc">저장 즉시 마이그레이션 시작</div>
              </div>
              <div class="smc-radio" :class="{on: !schedEnabled}"/>
            </div>

            <div class="sched-mode-card" :class="{active: schedEnabled}" @click="schedEnabled=true">
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
                <div class="smc-desc">지정한 날짜·시간에 자동 실행</div>
              </div>
              <div class="smc-radio" :class="{on: schedEnabled}"/>
            </div>
          </div>

          <template v-if="schedEnabled">
            <div class="sched-type-row">
              <button v-for="t in schedTypes" :key="t.v"
                class="stype-btn" :class="{active:schedType===t.v}" @click="schedType=t.v">
                {{ t.label }}
              </button>
            </div>

            <!-- 1회 실행 -->
            <div v-if="schedType==='once'" class="sched-fields">
              <div class="sf-row">
                <div class="sf-group">
                  <div class="field-label">날짜</div>
                  <input type="date" v-model="sched.date" :min="today"/>
                </div>
                <div class="sf-group">
                  <div class="field-label">시간</div>
                  <input type="time" v-model="sched.time"/>
                </div>
              </div>
              <div class="sched-preview" v-if="sched.date&&sched.time">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><circle cx="8" cy="8" r="7"/><polyline points="8,4 8,8 11,10"/></svg>
                {{ sched.date }} {{ sched.time }} 에 1회 실행
              </div>
            </div>

            <!-- 반복 실행 -->
            <div v-if="schedType==='repeat'" class="sched-fields">
              <div class="sf-row">
                <div class="sf-group">
                  <div class="field-label">반복 주기</div>
                  <div class="sel-wrap"><select v-model="sched.interval"><option value="hourly">매시간</option><option value="daily">매일</option><option value="weekly">매주</option><option value="monthly">매월</option></select><div class="chev"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div></div>
                </div>
                <div class="sf-group">
                  <div class="field-label">시작 시간</div>
                  <input type="time" v-model="sched.time"/>
                </div>
                <div class="sf-group" v-if="sched.interval==='weekly'">
                  <div class="field-label">요일</div>
                  <div class="dow-row">
                    <button v-for="d in dows" :key="d.v" class="dow-btn" :class="{active:sched.dows.includes(d.v)}" @click="toggleDow(d.v)">{{ d.l }}</button>
                  </div>
                </div>
                <div class="sf-group" v-if="sched.interval==='monthly'">
                  <div class="field-label">실행 일자</div>
                  <input type="number" v-model="sched.day" min="1" max="28" style="width:80px"/>
                  <span style="font-size:11.5px;color:var(--text-tertiary);margin-left:4px">일</span>
                </div>
              </div>
              <div class="sf-row">
                <div class="sf-group">
                  <div class="field-label">종료 조건</div>
                  <div class="sel-wrap"><select v-model="sched.endType"><option value="never">종료 없음</option><option value="date">특정 날짜</option><option value="count">횟수 제한</option></select><div class="chev"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div></div>
                </div>
                <div class="sf-group" v-if="sched.endType==='date'">
                  <div class="field-label">종료 날짜</div>
                  <input type="date" v-model="sched.endDate" :min="today"/>
                </div>
                <div class="sf-group" v-if="sched.endType==='count'">
                  <div class="field-label">실행 횟수</div>
                  <input type="number" v-model="sched.count" min="1" max="9999" style="width:100px"/>
                  <span style="font-size:11.5px;color:var(--text-tertiary);margin-left:4px">회</span>
                </div>
              </div>
              <div class="sched-preview" v-if="schedPreview">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><circle cx="8" cy="8" r="7"/><polyline points="8,4 8,8 11,10"/></svg>
                {{ schedPreview }}
              </div>
            </div>

            <!-- Cron 직접 입력 -->
            <div v-if="schedType==='cron'" class="sched-fields">
              <div class="sf-row">
                <div class="sf-group" style="flex:1">
                  <div class="field-label">Cron 표현식</div>
                  <input type="text" v-model="sched.cron" placeholder="예) 0 2 * * * (매일 새벽 2시)" style="font-family:'Consolas','SF Mono',monospace"/>
                </div>
              </div>
              <div class="cron-help">
                <span v-for="ex in cronExamples" :key="ex.v" class="cron-ex" @click="sched.cron=ex.v">{{ ex.label }}</span>
              </div>
              <div class="sched-preview" v-if="sched.cron">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><circle cx="8" cy="8" r="7"/><polyline points="8,4 8,8 11,10"/></svg>
                Cron: <code style="font-family:'Consolas','SF Mono',monospace">{{ sched.cron }}</code>
              </div>
            </div>
          </template>
        </div>

        <!-- 자동 수정 요약 -->
        <div v-if="autoFixEnabledCount>0" class="card" style="margin-top:10px;border-color:var(--accent-green);padding:12px 14px">
          <div style="font-size:12px;font-weight:500;color:var(--text-success);margin-bottom:6px">✓ 자동 수정 {{ autoFixEnabledCount }}건 적용 예정</div>
          <div v-for="r in warnRules.filter(r=>r.fixEnabled&&r.affected_count>0)" :key="r.title" style="font-size:11.5px;color:var(--text-secondary);padding:3px 0;display:flex;align-items:center;gap:6px">
            <span style="color:var(--text-success)">✓</span>{{ r.title }}
          </div>
        </div>
      </template>
    </div>

    <!-- Nav -->
    <div class="wiz-nav">
      <button class="btn" @click="cur>0?cur--:$router.push('/connector')">← {{ cur>0?'이전':'연결 설정' }}</button>
      <div style="flex:1"></div>
      <button v-if="cur<4" class="btn btn-primary" @click="nextStep">다음 →</button>
      <div v-else style="display:flex;gap:8px">
        <button class="btn btn-success" @click="submit(false)" :disabled="submitting">
          <span v-if="submitting&&!schedEnabled" class="spinner" style="width:13px;height:13px;border-top-color:#fff"></span>
          <svg v-else viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px"><polygon points="3,2 14,8 3,14"/></svg>
          {{ schedEnabled?'즉시 실행':'Job 실행 시작' }}
        </button>
        <button v-if="schedEnabled" class="btn btn-primary" @click="submit(true)" :disabled="submitting">
          <span v-if="submitting" class="spinner" style="width:13px;height:13px;border-top-color:#fff"></span>
          <svg v-else viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px"><rect x="1" y="2" width="14" height="13" rx="1"/><line x1="1" y1="6" x2="15" y2="6"/></svg>
          스케줄 등록
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useJobStore } from '@/store/jobStore.js'
import { useAppStore } from '@/store/appStore.js'
import { useConnectorStore } from '@/store/connectorStore.js'
import { DB_META, SOURCE_DBS, TARGET_DBS } from '@/constants/dbMeta.js'
import axios from 'axios'

const router    = useRouter()
const jobs      = useJobStore()
const app       = useAppStore()
const connector = useConnectorStore()

const cur         = ref(0)
const v3          = ref(false)
const submitting  = ref(false)

// ── Step 1 상태 ──
const objTab      = ref('tables')
const objSearch   = ref('')
const loadingObjs = ref(false)
const objError    = ref('')
const allTables   = ref([])
const allObjects  = ref({ procedures:[], functions:[], triggers:[], views:[] })

// ── Step 2 경고 ──
const warnRules    = ref([])
const analyzingWarn= ref(false)
const openRules    = ref({})

// ── Step 4 스케줄 ──
const schedEnabled = ref(false)
const schedType    = ref('once')
const sched = ref({
  date:'', time:'09:00', interval:'daily', dows:[], day:1,
  endType:'never', endDate:'', count:1, cron:''
})

const steps   = ['DB 선택','객체 선택','변환 규칙','실행 옵션','검토 & 실행']
const objTabs = [
  {v:'tables',     label:'테이블',    icon:'▤'},
  {v:'procedures', label:'프로시저',  icon:'⚙'},
  {v:'functions',  label:'함수',      icon:'ƒ'},
  {v:'triggers',   label:'트리거',    icon:'⚡'},
  {v:'views',      label:'뷰',        icon:'👁'},
]
const schedTypes = [
  {v:'once', label:'1회 실행'},{v:'repeat', label:'반복 실행'},{v:'cron', label:'Cron 표현식'}
]
const dows = [{v:0,l:'일'},{v:1,l:'월'},{v:2,l:'화'},{v:3,l:'수'},{v:4,l:'목'},{v:5,l:'금'},{v:6,l:'토'}]
const cronExamples = [
  {label:'매일 02:00', v:'0 2 * * *'},
  {label:'매시간',     v:'0 * * * *'},
  {label:'매주 월 09:00', v:'0 9 * * 1'},
  {label:'매월 1일 00:00', v:'0 0 1 * *'},
]
const today = new Date().toISOString().slice(0,10)

const form = ref({
  srcDb:'mysql', tgtDb:'mssql',
  tables:[], procedures:[], functions:[], triggers:[], views:[],
  name:'', batchSize:5000, workers:4, onError:'skip',
  truncate:false, createTbl:true, withIdx:true, convertObjs:true,
})

const srcDbs = SOURCE_DBS.map(d=>({...d,...DB_META[d.value]}))
const tgtDbs = TARGET_DBS.map(d=>({...d,...DB_META[d.value]}))
const m      = t => DB_META[t]||{label:'??',bg:'#eee',color:'#333'}
const fmtRows= n => n>=1e6?(n/1e6).toFixed(1)+'M':n>=1e3?Math.round(n/1e3)+'K':String(n||0)

const selRows       = computed(()=>allTables.value.filter(t=>form.value.tables.includes(t.table_name)).reduce((s,t)=>s+(t.row_count||0),0))
const totalSelCount = computed(()=>form.value.tables.length+form.value.procedures.length+form.value.functions.length+form.value.triggers.length+form.value.views.length)
const hasObjects    = computed(()=>form.value.procedures.length+form.value.functions.length+form.value.triggers.length+form.value.views.length > 0)
const warnCount     = computed(()=>warnRules.value.filter(r=>r.level==='warn'&&r.affected_count>0).length)
const autoFixableCount = computed(()=>warnRules.value.filter(r=>r.auto_fix&&r.affected_count>0).length)
const autoFixEnabledCount = computed(()=>warnRules.value.filter(r=>r.fixEnabled&&r.affected_count>0).length)
const autoFixAll    = computed(()=>warnRules.value.filter(r=>r.auto_fix&&r.affected_count>0).every(r=>r.fixEnabled))

// 스케줄 미리보기
const schedPreview = computed(()=>{
  if (!schedEnabled.value||schedType.value!=='repeat') return ''
  const intervalMap = {hourly:'매시간',daily:'매일',weekly:'매주',monthly:'매월'}
  const base = `${intervalMap[sched.value.interval]} ${sched.value.time||''}`
  const end  = sched.value.endType==='date' ? ` ~ ${sched.value.endDate}` : sched.value.endType==='count' ? ` (${sched.value.count}회)` : ''
  return base+end
})

// 필터링
const filteredTables = computed(()=>allTables.value.filter(t=>t.table_name.toLowerCase().includes(objSearch.value.toLowerCase())))
const filteredObjs   = type => (allObjects.value[type]||[]).filter(o=>o.name.toLowerCase().includes(objSearch.value.toLowerCase()))
const getSelCount    = tab => ({tables:form.value.tables.length,procedures:form.value.procedures.length,functions:form.value.functions.length,triggers:form.value.triggers.length,views:form.value.views.length}[tab]||0)

function toggleAutoFixAll(){ const t=!autoFixAll.value; warnRules.value.forEach(r=>{if(r.auto_fix)r.fixEnabled=t}) }
function toggleDow(v){ const i=sched.value.dows.indexOf(v); i>=0?sched.value.dows.splice(i,1):sched.value.dows.push(v) }
function isAllSelForTab(tab){
  const all=getAllForTab(tab)
  const sel=getSelForTab(tab)
  return all.length>0 && sel.length===all.length
}
function getAllForTab(tab){
  if(tab==='tables') return allTables.value.map(t=>t.table_name)
  const map={procedures:'procedures',functions:'functions',triggers:'triggers',views:'views'}
  return (allObjects.value[map[tab]]||[]).map(o=>o.name)
}
function getSelForTab(tab){
  const map={tables:'tables',procedures:'procedures',functions:'functions',triggers:'triggers',views:'views'}
  return form.value[map[tab]]||[]
}
function toggleTab(tab){
  if(objTab.value===tab){
    // 같은 탭 재클릭 → 전체선택/해제 토글
    const all=getAllForTab(tab)
    const sel=getSelForTab(tab)
    const allSelected = all.length>0 && sel.length===all.length
    if(allSelected){
      // 전체 해제
      if(tab==='tables') form.value.tables=[]
      else if(tab==='procedures') form.value.procedures=[]
      else if(tab==='functions')  form.value.functions=[]
      else if(tab==='triggers')   form.value.triggers=[]
      else if(tab==='views')      form.value.views=[]
    } else {
      // 전체 선택
      if(tab==='tables') form.value.tables=allTables.value.map(t=>t.table_name)
      else if(tab==='procedures') form.value.procedures=allObjects.value.procedures.map(o=>o.name)
      else if(tab==='functions')  form.value.functions=allObjects.value.functions.map(o=>o.name)
      else if(tab==='triggers')   form.value.triggers=allObjects.value.triggers.map(o=>o.name)
      else if(tab==='views')      form.value.views=allObjects.value.views.map(o=>o.name)
    }
  } else {
    objTab.value=tab
  }
}
function selAllTab(){
  if(objTab.value==='tables') form.value.tables=allTables.value.map(t=>t.table_name)
  else if(objTab.value==='procedures') form.value.procedures=allObjects.value.procedures.map(o=>o.name)
  else if(objTab.value==='functions')  form.value.functions=allObjects.value.functions.map(o=>o.name)
  else if(objTab.value==='triggers')   form.value.triggers=allObjects.value.triggers.map(o=>o.name)
  else if(objTab.value==='views')      form.value.views=allObjects.value.views.map(o=>o.name)
}
function clearTab(){
  if(objTab.value==='tables')     form.value.tables=[]
  else if(objTab.value==='procedures') form.value.procedures=[]
  else if(objTab.value==='functions')  form.value.functions=[]
  else if(objTab.value==='triggers')   form.value.triggers=[]
  else if(objTab.value==='views')      form.value.views=[]
}

async function loadAll(){
  const c=connector.source
  if(!c.host||!c.database){ objError.value='소스 DB 연결 정보 없음'; return }
  loadingObjs.value=true; objError.value=''
  const params={side:'source',db_type:c.dbType,host:c.host,port:c.port,username:c.username,password:c.password,database:c.database}
  try {
    // 순차 호출 — 동시 호출 시 SQL Server 핸드셰이크 충돌 방지
    const tRes = await axios.get('/api/v1/schema/tables', {params})
    allTables.value = tRes.data

    try {
      const oRes = await axios.get('/api/v1/schema/objects', {params})
      allObjects.value = oRes.data
    } catch(oe) {
      // 오브젝트 조회 실패는 무시 (프로시저/뷰 없는 DB는 정상)
      allObjects.value = {procedures:[], functions:[], triggers:[], views:[]}
      console.warn('오브젝트 조회 실패 (무시):', oe.message)
    }
  } catch(e){ objError.value=e.response?.data?.detail||e.message }
  finally{ loadingObjs.value=false }
}

async function analyzeWarnings(){
  analyzingWarn.value=true; warnRules.value=[]; openRules.value={}
  const c=connector.source
  try{
    const {data}=await axios.post('/api/v1/schema/analyze-warnings',{
      src_db_type:form.value.srcDb, tgt_db_type:form.value.tgtDb,
      tables:form.value.tables,
      conn_info:{db_type:c.dbType,host:c.host,port:c.port,username:c.username,password:c.password,database:c.database}
    })
    warnRules.value=data.map(r=>({...r,fixEnabled:r.auto_fix&&r.affected_count>0}))
    data.forEach((r,i)=>{ if(r.affected_count>0) openRules.value[i]=true })
  } catch(e){ app.notify('경고 분석 실패','error') }
  finally{ analyzingWarn.value=false }
}

function nextStep(){
  if(cur.value===0){ cur.value++; loadAll(); return }
  if(cur.value===1){ cur.value++; analyzeWarnings(); return }
  if(cur.value===3){
    v3.value=true
    // Job 이름 없으면 placeholder 값으로 자동 채움
    if(!form.value.name){
      form.value.name = connector.source.database + ' → ' + connector.target.database + ' 이관'
    }
  }
  if(cur.value<4) cur.value++
}

async function submit(asSchedule=false){
  submitting.value=true
  const src=connector.source; const tgt=connector.target

  // 스케줄 cron 생성
  let cronStr = null
  if(asSchedule && schedEnabled.value){
    if(schedType.value==='once') cronStr=`ONCE:${sched.value.date}T${sched.value.time}`
    else if(schedType.value==='repeat') cronStr=buildCron()
    else cronStr=sched.value.cron
  }

  try{
    const fixActions=warnRules.value.filter(r=>r.fixEnabled&&r.affected_count>0).map(r=>({action:r.fix_action,affected:r.affected_tables}))
    await jobs.create({
      name:form.value.name,
      src_db:form.value.srcDb, tgt_db:form.value.tgtDb,
      src_host:src.host,src_port:src.port,src_database:src.database,src_username:src.username,src_password:src.password,
      tgt_host:tgt.host,tgt_port:tgt.port,tgt_database:tgt.database,tgt_username:tgt.username,tgt_password:tgt.password,
      tables:form.value.tables,
      objects:{procedures:form.value.procedures,functions:form.value.functions,triggers:form.value.triggers,views:form.value.views},
      convert_objects:form.value.convertObjs,
      batch_size:form.value.batchSize, parallel_workers:form.value.workers,
      on_error:form.value.onError, truncate_target:form.value.truncate, create_table:form.value.createTbl,
      auto_fix_actions:fixActions,
      schedule_cron:cronStr,
    })
    const msg = asSchedule ? `스케줄 등록 완료! (${cronStr})` : `"${form.value.name}" Job 시작!`
    app.notify(msg,'success')
    router.push(asSchedule?'/jobs':'/monitor')
  } catch(e){
    app.notify('생성 실패: '+(e.response?.data?.detail||e.message),'error')
  } finally{ submitting.value=false }
}

function buildCron(){
  const t=sched.value.time?.split(':')||['0','0']
  const h=t[0]; const m=t[1]
  if(sched.value.interval==='hourly') return `${m} * * * *`
  if(sched.value.interval==='daily')  return `${m} ${h} * * *`
  if(sched.value.interval==='weekly'){
    const d=sched.value.dows.length?sched.value.dows.join(','):'1'
    return `${m} ${h} * * ${d}`
  }
  if(sched.value.interval==='monthly') return `${m} ${h} ${sched.value.day} * *`
  return `${m} ${h} * * *`
}

onMounted(()=>{
  if(connector.source.dbType) form.value.srcDb=connector.source.dbType
  if(connector.target.dbType) form.value.tgtDb=connector.target.dbType
  if(!form.value.name&&connector.source.database&&connector.target.database)
    form.value.name=`${connector.source.database} → ${connector.target.database} 이관`
})
</script>

<style scoped>
/* Steps */
.steps-bar{display:flex;padding:14px 20px;margin-bottom:10px;gap:0}
.step{display:flex;align-items:center;gap:8px;flex:1;font-size:11.5px;color:var(--text-tertiary);position:relative}
.step:not(:last-child)::after{content:'';position:absolute;right:0;top:50%;transform:translateY(-50%);width:1px;height:22px;background:var(--border-mid)}
.step-num{width:22px;height:22px;border-radius:50%;border:1.5px solid var(--border-mid);display:flex;align-items:center;justify-content:center;font-size:10.5px;font-weight:600;flex-shrink:0}
.step.active{color:var(--text-info)}.step.active .step-num{border-color:var(--accent-blue);background:var(--bg-info);color:var(--text-info)}
.step.done{color:var(--text-success)}.step.done .step-num{border-color:var(--accent-green);background:var(--bg-success);color:var(--text-success)}
.step-lbl{font-size:11.5px;white-space:nowrap}

/* DB 선택 */
.wiz-body{margin-bottom:10px;min-height:320px}
.wh{font-size:12.5px;font-weight:500;color:var(--text-primary);margin-bottom:10px}
.conn-summary{display:flex;align-items:center;gap:10px;padding:10px 14px;background:var(--bg-success);border-radius:var(--radius-md);margin-bottom:14px;font-size:12px}
.cs-item{display:flex;align-items:center;gap:6px;font-weight:500}
.cs-arrow{color:var(--text-tertiary);font-size:14px}
.cs-ok{margin-left:auto;font-size:11px;background:var(--bg-primary);color:var(--text-success);padding:2px 8px;border-radius:8px;font-weight:500}
.db-grid{display:grid;grid-template-columns:repeat(8,1fr);gap:8px}
.db-card{border:0.5px solid var(--border-mid);border-radius:var(--radius-md);padding:10px 8px;cursor:pointer;text-align:center;background:var(--bg-secondary);transition:all .12s;position:relative}
.db-card:hover,.db-card.sel{border-color:var(--accent-blue);background:var(--bg-info)}
.db-card.cur{border-color:var(--accent-green);background:var(--bg-success)}
.db-card-ico{width:28px;height:28px;border-radius:var(--radius-sm);display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;margin:0 auto 5px}
.db-card-name{font-size:10px;color:var(--text-primary);line-height:1.3}
.db-card-badge{position:absolute;top:-6px;right:-4px;font-size:9px;background:var(--accent-green);color:#fff;padding:1px 5px;border-radius:6px;font-weight:600}
.db-card-badge.tgt{background:var(--accent-blue)}
.mini-ico{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:4px;font-size:9px;font-weight:700;flex-shrink:0}

/* 오브젝트 탭 */
.obj-tabs{display:flex;align-items:center;gap:4px;margin-bottom:10px;flex-wrap:wrap}
.otab{display:flex;align-items:center;gap:5px;padding:6px 12px;border-radius:var(--radius-md);border:0.5px solid var(--border-mid);background:transparent;cursor:pointer;font-size:12px;font-family:var(--font);color:var(--text-secondary);transition:all .12s}
.otab:hover{background:var(--bg-secondary);color:var(--text-primary)}
.otab.active{background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue);font-weight:500}
.otab-ico{font-size:13px}
.otab-toggle-hint{font-size:9px;padding:1px 5px;border-radius:8px;margin-left:2px;background:var(--accent-blue);color:#fff;font-weight:600;opacity:.85;}
.otab.all-sel .otab-toggle-hint{background:var(--accent-green);}
.otab-cnt{background:var(--accent-blue);color:#fff;font-size:9.5px;font-weight:700;padding:1px 5px;border-radius:8px}
.obj-list{background:var(--bg-secondary);border-radius:var(--radius-md);padding:4px;max-height:280px;overflow-y:auto}
.obj-row{display:flex;align-items:center;gap:6px;padding:6px 10px;border-radius:var(--radius-sm);cursor:pointer;font-size:12px}
.obj-row:hover{background:var(--bg-primary)}
.obj-type-ico{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:4px;font-size:12px;flex-shrink:0}
.obj-type-ico.tbl{background:#e6f1fb;color:#185fa5}
.obj-type-ico.proc{background:#e6f1fb;color:#185fa5}
.obj-type-ico.func{background:#eaf3de;color:#3b6d11}
.obj-type-ico.trig{background:#faeeda;color:#854f0b}
.obj-type-ico.view{background:#eeedfe;color:#534ab7}
.obj-name{flex:1;font-family:'Consolas','SF Mono',monospace;font-weight:500;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.obj-meta{font-size:10.5px;color:var(--text-tertiary)}
.sel-summary{font-size:11px;color:var(--text-info);margin-top:6px;padding:4px 2px}
.total-sel-bar{display:flex;align-items:center;gap:6px;margin-top:8px;padding:8px 10px;background:var(--bg-info);border-radius:var(--radius-md);font-size:11.5px;color:var(--text-info);flex-wrap:wrap}
.sel-chip{font-size:10.5px;font-weight:600;padding:2px 8px;border-radius:6px}
.sel-chip.tbl{background:#185fa5;color:#fff}
.sel-chip.proc{background:#378add;color:#fff}
.sel-chip.func{background:#3b6d11;color:#fff}
.sel-chip.trig{background:#854f0b;color:#fff}
.sel-chip.view{background:#534ab7;color:#fff}

/* 규칙 카드 */
.rule-card{border:0.5px solid var(--border-mid);border-radius:var(--radius-md);margin-bottom:8px;overflow:hidden}
.rule-card.rule-warn{border-left:3px solid var(--text-warning)}
.rule-card.rule-info{border-left:3px solid var(--text-info)}
.rule-header{display:flex;align-items:center;gap:10px;padding:10px 14px;cursor:pointer;background:var(--bg-secondary);transition:background .12s}
.rule-header:hover{background:var(--bg-primary)}
.rule-level-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.dot-warn{background:var(--text-warning)}.dot-info{background:var(--text-info)}
.rule-title-area{display:flex;flex-direction:column;gap:4px;flex:1;min-width:0}
.rule-title{font-size:12.5px;font-weight:500;color:var(--text-primary)}
.rule-types{display:flex;align-items:center;gap:0}
.rule-right{display:flex;align-items:center;gap:8px;flex-shrink:0}
.affected-badge{font-size:10.5px;background:var(--bg-warning);color:var(--text-warning);padding:2px 8px;border-radius:8px;font-weight:500}
.affected-none{font-size:10.5px;color:var(--text-tertiary)}
.fix-toggle{display:flex;align-items:center;gap:5px}
.fix-label{font-size:11px;color:var(--text-secondary)}
.rule-detail{padding:12px 14px;background:var(--bg-primary);border-top:0.5px solid var(--border-light)}
.rule-info-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}
.ri-box{padding:10px 12px;border-radius:var(--radius-md);border:0.5px solid var(--border-light);background:var(--bg-secondary)}
.ri-box.fix.active{background:var(--bg-success);border-color:var(--accent-green)}
.ri-label{font-size:11px;font-weight:600;color:var(--text-secondary);margin-bottom:6px}
.ri-text{font-size:12px;color:var(--text-primary);line-height:1.6}
.fix-on-badge{margin-top:8px;font-size:11px;color:var(--text-success);font-weight:500}
.affected-list{background:var(--bg-secondary);border-radius:var(--radius-md);overflow:hidden}
.al-header{font-size:11px;font-weight:600;color:var(--text-secondary);padding:6px 12px;background:var(--bg-tertiary)}
.al-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));max-height:140px;overflow-y:auto}
.al-item{display:flex;align-items:center;gap:5px;padding:4px 12px;border-bottom:0.5px solid var(--border-light);font-size:11.5px}
.al-table{font-family:'Consolas','SF Mono',monospace;font-weight:500;color:var(--text-primary)}
.al-dot{color:var(--text-tertiary)}
.al-col{font-family:'Consolas','SF Mono',monospace;color:var(--text-info)}
.al-type{font-size:10.5px;color:var(--text-tertiary);background:var(--bg-tertiary);padding:1px 5px;border-radius:3px}
.al-fix-ico{margin-left:auto;color:var(--text-success)}
.type-chip{display:inline-block;font-size:11px;padding:2px 7px;border-radius:4px;font-family:'Consolas','SF Mono',monospace;font-weight:500}
.type-chip.src{background:var(--bg-info);color:var(--text-info)}.type-chip.tgt{background:var(--bg-success);color:var(--text-success)}

/* 옵션 */
.opts-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.sel-wrap{position:relative}.sel-wrap select{width:100%;appearance:none;-webkit-appearance:none;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:var(--radius-md);padding:7px 28px 7px 10px;font-size:12.5px;color:var(--text-primary);cursor:pointer;font-family:var(--font)}.sel-wrap select:focus{outline:none;border-color:var(--accent-blue)}.chev{position:absolute;right:9px;top:50%;transform:translateY(-50%);pointer-events:none;color:var(--text-tertiary)}.chev svg{width:11px;height:11px;display:block}
.opt-chk{display:flex;align-items:center;gap:7px;font-size:12px;color:var(--text-secondary);margin-top:8px;cursor:pointer}
.opt-chk input{accent-color:var(--accent-blue)}

/* 검토 */
.review-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:14px}
.rv-item{display:flex;align-items:center;justify-content:space-between;padding:7px 10px;background:var(--bg-secondary);border-radius:var(--radius-sm)}
.rv-l{font-size:11px;color:var(--text-tertiary)}.rv-v{font-size:12px;font-weight:500;color:var(--text-primary)}

/* 스케줄 */
.sched-section{background:var(--bg-secondary);border-radius:var(--radius-lg);padding:14px;border:0.5px solid var(--border-mid)}
.sched-header{display:flex;align-items:center;gap:8px;margin-bottom:12px;font-size:13px}
.sched-title{font-weight:600;color:var(--text-primary)}
.sched-mode-row{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px}
.sched-mode-card{display:flex;align-items:center;gap:12px;padding:12px 14px;background:var(--bg-primary);border:1.5px solid var(--border-mid);border-radius:var(--radius-lg);cursor:pointer;transition:all .15s;user-select:none}
.sched-mode-card:hover{border-color:var(--accent-blue);background:var(--bg-info)}
.sched-mode-card.active{border-color:var(--accent-blue);background:var(--bg-info);box-shadow:0 0 0 3px rgba(59,130,246,.12)}
.smc-ico{color:var(--text-tertiary);flex-shrink:0;transition:color .15s}
.sched-mode-card:hover .smc-ico,.sched-mode-card.active .smc-ico{color:var(--text-info)}
.smc-body{flex:1;min-width:0}
.smc-title{font-size:13px;font-weight:600;color:var(--text-primary)}
.smc-desc{font-size:11px;color:var(--text-tertiary);margin-top:2px}
.sched-mode-card.active .smc-title{color:var(--text-info)}
.smc-radio{width:16px;height:16px;border-radius:50%;border:1.5px solid var(--border-mid);flex-shrink:0;transition:all .15s;position:relative}
.smc-radio.on{border-color:var(--accent-blue);background:var(--accent-blue)}
.smc-radio.on::after{content:'';position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:6px;height:6px;border-radius:50%;background:#fff}
.sched-type-row{display:flex;gap:6px;margin-bottom:12px}
.stype-btn{padding:6px 14px;border-radius:var(--radius-md);border:0.5px solid var(--border-mid);background:transparent;cursor:pointer;font-size:12px;font-family:var(--font);color:var(--text-secondary);transition:all .12s}
.stype-btn:hover{background:var(--bg-primary)}
.stype-btn.active{background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue);font-weight:500}
.sched-fields{background:var(--bg-primary);border-radius:var(--radius-md);padding:14px;border:0.5px solid var(--border-light)}
.sf-row{display:flex;align-items:flex-start;gap:12px;margin-bottom:10px;flex-wrap:wrap}
.sf-row:last-child{margin-bottom:0}
.sf-group{display:flex;flex-direction:column;gap:2px;min-width:140px}
.dow-row{display:flex;gap:4px;flex-wrap:wrap}
.dow-btn{width:30px;height:30px;border-radius:50%;border:0.5px solid var(--border-mid);background:transparent;cursor:pointer;font-size:11.5px;font-family:var(--font);color:var(--text-secondary);transition:all .12s;display:flex;align-items:center;justify-content:center}
.dow-btn:hover{background:var(--bg-secondary)}
.dow-btn.active{background:var(--accent-blue);color:#fff;border-color:var(--accent-blue)}
.sched-preview{display:flex;align-items:center;gap:6px;margin-top:10px;padding:8px 12px;background:var(--bg-info);border-radius:var(--radius-md);font-size:12px;color:var(--text-info)}
.cron-help{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}
.cron-ex{font-size:11px;padding:3px 8px;background:var(--bg-secondary);border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);cursor:pointer;color:var(--text-secondary);font-family:'Consolas','SF Mono',monospace;transition:all .12s}
.cron-ex:hover{background:var(--bg-info);color:var(--text-info)}

/* toggle */
.toggle{position:relative;width:34px;height:18px;background:var(--border-mid);border-radius:9px;cursor:pointer;transition:background .2s;flex-shrink:0}
.toggle.sm{width:28px;height:16px}
.toggle.on{background:var(--accent-blue)}
.toggle::after{content:'';position:absolute;top:2px;left:2px;width:14px;height:14px;border-radius:50%;background:white;transition:transform .2s}
.toggle.sm::after{width:12px;height:12px}
.toggle.on::after{transform:translateX(16px)}
.toggle.sm.on::after{transform:translateX(12px)}

.wiz-nav{display:flex;align-items:center;gap:8px}
input.err{border-color:var(--text-danger)!important}
</style>
