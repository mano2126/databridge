<template>
  <div>

    <!-- ── 위저드 헤더 ── -->
    <div class="wiz-topbar">
      <div class="wiz-topbar-left">
        <div class="wiz-title">이관 Job 생성</div>
        <div class="wiz-subtitle">소스에서 타겟으로 데이터를 안전하게 이관합니다</div>
      </div>
      <!-- 단계 네비게이터 — 클릭으로 이동 가능 -->
      <div class="wiz-steps">
        <template v-for="(st, i) in steps" :key="i">
          <button class="wiz-step" :class="{active: cur===i, done: cur>i, reachable: cur>=i}"
                  @click="goStep(i)" :title="cur>=i ? st : '이전 단계를 완료하세요'">
            <span class="wiz-step-num">
              <svg v-if="cur>i" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2.2">
                <polyline points="1.5,6 4.5,9 10.5,3"/>
              </svg>
              <span v-else>{{ i+1 }}</span>
            </span>
            <span class="wiz-step-lbl">{{ st }}</span>
          </button>
          <span v-if="i < steps.length-1" class="wiz-step-line" :class="{done: cur>i}"></span>
        </template>
      </div>
    </div><!-- wiz-topbar -->

    <!-- ══ 변환 엔진 선택 ══ -->
    <div class="wiz-engine-bar">
      <div class="eb-row">
        <span class="eb-lbl">DDL 엔진</span>
        <span class="eb-sub2">테이블 · 뷰</span>
        <div class="eb-opts">
          <label v-for="e in engines" :key="e.v" class="eb-opt" :class="{active: form.ddlEngine===e.v}">
            <input type="radio" v-model="form.ddlEngine" :value="e.v" style="display:none"/>
            <span class="eb-opt-ico">{{ e.ico }}</span>
            <span class="eb-opt-lbl">{{ e.l }}</span>
          </label>
        </div>
      </div>
      <div class="eb-divider2"></div>
      <div class="eb-row">
        <span class="eb-lbl">오브젝트 엔진</span>
        <span class="eb-sub2">SP · 함수 · 트리거</span>
        <div class="eb-opts">
          <label v-for="e in engines" :key="e.v" class="eb-opt" :class="{active: form.objEngine===e.v}">
            <input type="radio" v-model="form.objEngine" :value="e.v" style="display:none"/>
            <span class="eb-opt-ico">{{ e.ico }}</span>
            <span class="eb-opt-lbl">{{ e.l }}</span>
          </label>
        </div>
      </div>
    </div>


      <!-- ── Step 0: DB 선택 ── -->
      <template v-if="cur===0">

        <!-- 💾 저장된 프로파일 빠른 불러오기 -->
        <div v-if="connector.profiles.length" class="profile-quick-panel">
          <div class="pq-header">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px">
              <ellipse cx="7" cy="4" rx="4.5" ry="1.8"/>
              <path d="M2.5 4v3c0 .9 2 1.8 4.5 1.8s4.5-.9 4.5-1.8V4"/>
              <path d="M2.5 7v3c0 .9 2 1.8 4.5 1.8s4.5-.9 4.5-1.8V7"/>
            </svg>
            저장된 프로파일로 빠른 시작
            <button class="pq-manage" @click="$router.push('/connector/profiles')">전체 프로파일 →</button>
          </div>
          <div class="pq-list">
            <div v-for="p in sortedProfiles.slice(0,6)" :key="p.id"
                 class="pq-item"
                 :class="{
                   applied: appliedProfileId===p.id,
                   recent:  mostRecentProfileId===p.id && appliedProfileId!==p.id
                 }"
                 @click="applyProfile(p)" :title="p.name">
              <!-- v10 #11: recent 배지 — 가장 최근 사용한 프로파일 표시 -->
              <div v-if="mostRecentProfileId===p.id && appliedProfileId!==p.id"
                   class="pq-recent-badge" title="최근 사용">최근</div>
              <div class="pq-dbs">
                <span class="pq-chip" :style="{background:m(p.source?.db_type||p.source?.dbType)?.bg, color:m(p.source?.db_type||p.source?.dbType)?.color}">
                  {{ m(p.source?.db_type||p.source?.dbType)?.label }}
                </span>
                <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:9px;height:9px;opacity:.4">
                  <line x1="1" y1="6" x2="11" y2="6"/><polyline points="7,2 11,6 7,10"/>
                </svg>
                <span class="pq-chip" :style="{background:m(p.target?.db_type||p.target?.dbType)?.bg, color:m(p.target?.db_type||p.target?.dbType)?.color}">
                  {{ m(p.target?.db_type||p.target?.dbType)?.label }}
                </span>
              </div>
              <div class="pq-name">{{ p.name }}</div>
              <div v-if="appliedProfileId!==p.id" class="pq-hosts">{{ p.source?.database }}/{{ p.source?.host }}</div>
              <div v-else class="pq-applied">
                <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2.2" style="width:10px;height:10px">
                  <polyline points="1,6 4.5,9.5 11,2"/>
                </svg>
                적용됨
              </div>
            </div>
          </div>
        </div>

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

        <!-- v90.1: DB 선택 영역 가로 배치 (소스 ←→ 타겟) -->
        <div class="db-horizontal-layout">
          <!-- 소스 DB -->
          <div class="db-side db-side-source">
            <h4 class="wh db-side-title">
              <span class="db-side-icon">📤</span>
              <span>소스 DB</span>
              <span v-if="connector.source.dbType" class="db-side-status">
                ✓ {{ connector.source.dbType.toUpperCase() }}
              </span>
            </h4>
            <div class="db-split-layout">
              <!-- 자주 쓰는 DB (큰 카드 3개) -->
              <div class="db-frequent-col">
                <div v-for="d in frequentSrcDbs" :key="d.value" class="db-card db-card-large"
                     :class="{sel:form.srcDb===d.value,cur:connector.source.dbType===d.value}"
                     @click="form.srcDb=d.value">
                  <div class="db-card-dot" :style="{background:d.bg}"></div>
                  <div class="db-card-name">{{ d.name }}</div>
                  <div class="db-card-abbr-txt" :style="{color:d.color}">{{ d.label }}</div>
                  <div v-if="connector.source.dbType===d.value" class="db-card-badge">연결됨</div>
                  <div v-if="d.useCount" class="db-card-usecount">{{ d.useCount }}회</div>
                </div>
              </div>
              <!-- 안 쓰는 DB (얇은 리스트) -->
              <div class="db-rare-col">
                <div v-for="d in rareSrcDbs" :key="d.value" class="db-rare-item"
                     :class="{sel:form.srcDb===d.value,cur:connector.source.dbType===d.value}"
                     @click="form.srcDb=d.value">
                  <div class="db-rare-dot" :style="{background:d.bg}"></div>
                  <div class="db-rare-name">{{ d.name }}</div>
                  <div v-if="connector.source.dbType===d.value" class="db-rare-badge">✓</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 화살표 -->
          <div class="db-arrow">
            <div class="db-arrow-line"></div>
            <div class="db-arrow-icon">→</div>
            <div class="db-arrow-line"></div>
          </div>

          <!-- 타겟 DB -->
          <div class="db-side db-side-target">
            <h4 class="wh db-side-title">
              <span class="db-side-icon">📥</span>
              <span>타겟 DB</span>
              <span v-if="connector.target.dbType" class="db-side-status">
                ✓ {{ connector.target.dbType.toUpperCase() }}
              </span>
            </h4>
            <div class="db-split-layout">
              <!-- 자주 쓰는 DB (큰 카드 3개) -->
              <div class="db-frequent-col">
                <div v-for="d in frequentTgtDbs" :key="d.value" class="db-card db-card-large"
                     :class="{sel:form.tgtDb===d.value,cur:connector.target.dbType===d.value}"
                     @click="form.tgtDb=d.value">
                  <div class="db-card-dot" :style="{background:d.bg}"></div>
                  <div class="db-card-name">{{ d.name }}</div>
                  <div class="db-card-abbr-txt" :style="{color:d.color}">{{ d.label }}</div>
                  <div v-if="connector.target.dbType===d.value" class="db-card-badge tgt">연결됨</div>
                  <div v-if="d.useCount" class="db-card-usecount">{{ d.useCount }}회</div>
                </div>
              </div>
              <!-- 안 쓰는 DB (얇은 리스트) -->
              <div class="db-rare-col">
                <div v-for="d in rareTgtDbs" :key="d.value" class="db-rare-item"
                     :class="{sel:form.tgtDb===d.value,cur:connector.target.dbType===d.value}"
                     @click="form.tgtDb=d.value">
                  <div class="db-rare-dot" :style="{background:d.bg}"></div>
                  <div class="db-rare-name">{{ d.name }}</div>
                  <div v-if="connector.target.dbType===d.value" class="db-rare-badge">✓</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- v90.1: 이관 시나리오 선택 -->
        <ScenarioSelector v-model="form.migrationScenario" />
      </template>

      <!-- ── Step 1: 객체 선택 (v90.11 - 5박스 동시 표시) ── -->
      <template v-if="cur===1">
        <!-- 컴팩트 카드 헤더 (5개) - 카드 클릭 = 전체 선택/해제 토글 -->
        <div class="obj-cards-compact">
          <div v-for="t in objTabs" :key="t.v"
               class="obj-card-mini"
               :class="{
                 'active': isAllSelForTab(t.v),
                 'partial': isPartialSelForTab(t.v),
                 'empty': getTotalCount(t.v) === 0,
               }"
               @click="toggleAllForTab(t.v)"
               :title="getTotalCount(t.v) === 0 ? `${t.label}: 0개` : 
                       (isAllSelForTab(t.v) ? '클릭하여 전체 해제' : '클릭하여 전체 선택')">
            <span class="obj-card-mini-icon">{{ t.icon }}</span>
            <span class="obj-card-mini-label">{{ t.label }}</span>
            <span class="obj-card-mini-count">({{ getTotalCount(t.v) }})</span>
            <span v-if="getSelCount(t.v) > 0" class="obj-card-mini-sel">
              ✓{{ getSelCount(t.v) }}
            </span>
          </div>
          <!-- 검색창 -->
          <div class="obj-search-wrap">
            <input type="text" v-model="objSearch" 
                   placeholder="🔍 검색..." 
                   class="obj-search-input-mini"/>
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

        <!-- v90.48: schema 정책 카드 + 정렬 툴바 (본부장님 결정 2026-04-27) -->
        <div v-else>
          <div class="policy-card">
            <div class="policy-card-header">
              <span class="policy-icon">⚙</span>
              <span class="policy-title">스키마 변환 정책</span>
              <span class="policy-help" :title="policyHelpText">ⓘ</span>
            </div>
            <div class="policy-options">
              <label class="policy-opt" :class="{active: form.schemaStrategy === 'underscore'}">
                <input type="radio" v-model="form.schemaStrategy" value="underscore"/>
                <div class="policy-opt-body">
                  <div class="policy-opt-title">언더스코어 결합 <span class="policy-recommended">권장</span></div>
                  <div class="policy-opt-desc">customer.profile → <b>customer_profile</b></div>
                  <div class="policy-opt-note">충돌 없음, 도메인 정보 보존, 본부장님 환경 적합</div>
                </div>
              </label>
              <label class="policy-opt" :class="{active: form.schemaStrategy === 'drop'}">
                <input type="radio" v-model="form.schemaStrategy" value="drop"/>
                <div class="policy-opt-body">
                  <div class="policy-opt-title">접두어 제거</div>
                  <div class="policy-opt-desc">customer.profile → <b>profile</b></div>
                  <div class="policy-opt-note">짧지만 동명 테이블 충돌 위험</div>
                </div>
              </label>
              <label class="policy-opt" :class="{active: form.schemaStrategy === 'database'}">
                <input type="radio" v-model="form.schemaStrategy" value="database"/>
                <div class="policy-opt-body">
                  <div class="policy-opt-title">별도 DB</div>
                  <div class="policy-opt-desc">customer.profile → <b>customer_db.profile</b></div>
                  <div class="policy-opt-note">멀티 DB 환경 (고급)</div>
                </div>
              </label>
            </div>
            <div class="policy-preview" v-if="policyPreviewSamples.length">
              <span class="policy-preview-label">미리보기:</span>
              <span v-for="(p, i) in policyPreviewSamples" :key="i" class="policy-preview-sample">
                <code>{{ p.src }}</code> → <code class="policy-preview-tgt">{{ p.tgt }}</code>
              </span>
            </div>
          </div>

          <!-- v90.75: 상단 정렬 툴바 제거 — 각 박스 컬럼 헤더 클릭으로 대체 -->

        <!-- 5개 박스 동시 표시 -->
        <div class="obj-boxes-grid">
          
          <!-- 테이블 박스 -->
          <div class="obj-box obj-box-tables" :class="{'box-active': form.tables.length > 0}">
            <div class="obj-box-header obj-box-header-clickable"
                 @click="toggleAllForTab('tables')"
                 :title="isAllSelForTab('tables') ? '전체 해제' : '전체 선택'">
              <span class="obj-box-icon">▤</span>
              <span class="obj-box-title">테이블</span>
              <span class="obj-box-count">({{ allTables.length }})</span>
              <span v-if="form.tables.length" class="obj-box-sel-badge">✓{{ form.tables.length }}</span>
              <span class="obj-box-toggle-icon">{{ isAllSelForTab('tables') ? '☑' : isPartialSelForTab('tables') ? '◧' : '☐' }}</span>
            </div>
            <div class="obj-box-body">
              <div v-if="!allTables.length" class="obj-box-empty">테이블 없음</div>
              <!-- v90.75: 컬럼 헤더 행 (클릭하여 정렬) -->
              <div v-if="allTables.length" class="obj-row-head obj-row-table-head">
                <span class="orh-check"></span>
                <span class="orh-name sortable" @click="toggleTableSort('name')">
                  테이블명 <span class="orh-sort-icon">{{ tableSortIcon('name') }}</span>
                </span>
                <span class="orh-arrow"></span>
                <span class="orh-tgt sortable" @click="toggleTableSort('name')">
                  타겟 테이블명
                </span>
                <span class="orh-rows sortable" @click="toggleTableSort('rows')">
                  행수 <span class="orh-sort-icon">{{ tableSortIcon('rows') }}</span>
                </span>
                <span class="orh-size sortable" @click="toggleTableSort('size')">
                  크기 <span class="orh-sort-icon">{{ tableSortIcon('size') }}</span>
                </span>
              </div>
              <!-- v90.74/75: 테이블 행 — 컬럼 라인 정렬, 행수 콤마 표기 -->
              <label v-for="t in filteredTables" :key="t.table_name"
                     class="obj-row obj-row-table"
                     :class="{'obj-row-empty': (t.row_count||0) === 0}"
                     :title="`${t.schema_name}.${t.table_name}` + (t.row_count ? ` (${fmtRowsComma(t.row_count)} rows)` : ' (empty)')">
                <input type="checkbox" v-model="form.tables" :value="t.table_name"/>
                <span class="obj-name">{{ t.schema_name }}.{{ t.table_name }}</span>
                <span class="obj-tgt-arrow">→</span>
                <span class="obj-tgt-name" :title="`정책: ${form.schemaStrategy}`">
                  {{ previewTargetName(t.schema_name, t.table_name) }}
                </span>
                <span class="obj-meta obj-meta-rows"
                      :class="_rowCountClass(t.row_count||0)">{{ fmtRowsComma(t.row_count||0) }}</span>
                <span class="obj-meta obj-meta-size">{{ t.size_mb ? t.size_mb+'MB' : '' }}</span>
              </label>
            </div>
          </div>

          <!-- 프로시저 박스 -->
          <div class="obj-box obj-box-proc" :class="{'box-active': form.procedures.length > 0}">
            <div class="obj-box-header obj-box-header-clickable"
                 @click="toggleAllForTab('procedures')"
                 :title="isAllSelForTab('procedures') ? '전체 해제' : '전체 선택'">
              <span class="obj-box-icon">⚙</span>
              <span class="obj-box-title">프로시저</span>
              <span class="obj-box-count">({{ (allObjects.procedures||[]).length }})</span>
              <span v-if="form.procedures.length" class="obj-box-sel-badge">✓{{ form.procedures.length }}</span>
              <span class="obj-box-toggle-icon">{{ isAllSelForTab('procedures') ? '☑' : isPartialSelForTab('procedures') ? '◧' : '☐' }}</span>
            </div>
            <div class="obj-box-body">
              <div v-if="!(allObjects.procedures||[]).length" class="obj-box-empty">프로시저 없음</div>
              <!-- v90.75: 프로시저 컬럼 헤더 (이름 / 생성일) -->
              <div v-if="(allObjects.procedures||[]).length" class="obj-row-head obj-row-obj-head">
                <span class="orh-check"></span>
                <span class="orh-name sortable" @click="toggleProcSort('name')">
                  이름 <span class="orh-sort-icon">{{ procSortIcon('name') }}</span>
                </span>
                <span class="orh-meta sortable" @click="toggleProcSort('date')">
                  생성일 <span class="orh-sort-icon">{{ procSortIcon('date') }}</span>
                </span>
              </div>
              <label v-for="o in filteredObjs('procedures')" :key="o.name" class="obj-row">
                <input type="checkbox" v-model="form.procedures" :value="o.name"/>
                <span class="obj-name">{{ o.name }}</span>
                <span class="obj-meta">{{ o.created?.slice(0,10) }}</span>
              </label>
            </div>
          </div>

          <!-- 함수 박스 -->
          <div class="obj-box obj-box-func" :class="{'box-active': form.functions.length > 0}">
            <div class="obj-box-header obj-box-header-clickable"
                 @click="toggleAllForTab('functions')"
                 :title="isAllSelForTab('functions') ? '전체 해제' : '전체 선택'">
              <span class="obj-box-icon">ƒ</span>
              <span class="obj-box-title">함수</span>
              <span class="obj-box-count">({{ (allObjects.functions||[]).length }})</span>
              <span v-if="form.functions.length" class="obj-box-sel-badge">✓{{ form.functions.length }}</span>
              <span class="obj-box-toggle-icon">{{ isAllSelForTab('functions') ? '☑' : isPartialSelForTab('functions') ? '◧' : '☐' }}</span>
            </div>
            <div class="obj-box-body">
              <div v-if="!(allObjects.functions||[]).length" class="obj-box-empty">함수 없음</div>
              <!-- v90.75: 함수 컬럼 헤더 (이름 / 반환타입) -->
              <div v-if="(allObjects.functions||[]).length" class="obj-row-head obj-row-obj-head">
                <span class="orh-check"></span>
                <span class="orh-name sortable" @click="toggleFuncSort('name')">
                  이름 <span class="orh-sort-icon">{{ funcSortIcon('name') }}</span>
                </span>
                <span class="orh-meta sortable" @click="toggleFuncSort('type')">
                  반환타입 <span class="orh-sort-icon">{{ funcSortIcon('type') }}</span>
                </span>
              </div>
              <label v-for="o in filteredObjs('functions')" :key="o.name" class="obj-row">
                <input type="checkbox" v-model="form.functions" :value="o.name"/>
                <span class="obj-name">{{ o.name }}</span>
                <span class="obj-meta">{{ o.return_type }}</span>
              </label>
            </div>
          </div>

          <!-- 트리거 박스 -->
          <div class="obj-box obj-box-trig" :class="{'box-active': form.triggers.length > 0}">
            <div class="obj-box-header obj-box-header-clickable"
                 @click="toggleAllForTab('triggers')"
                 :title="isAllSelForTab('triggers') ? '전체 해제' : '전체 선택'">
              <span class="obj-box-icon">⚡</span>
              <span class="obj-box-title">트리거</span>
              <span class="obj-box-count">({{ (allObjects.triggers||[]).length }})</span>
              <span v-if="form.triggers.length" class="obj-box-sel-badge">✓{{ form.triggers.length }}</span>
              <span class="obj-box-toggle-icon">{{ isAllSelForTab('triggers') ? '☑' : isPartialSelForTab('triggers') ? '◧' : '☐' }}</span>
            </div>
            <div class="obj-box-body">
              <div v-if="!(allObjects.triggers||[]).length" class="obj-box-empty">트리거 없음</div>
              <!-- v90.75: 트리거 컬럼 헤더 (이름 / 이벤트 / 대상테이블) -->
              <div v-if="(allObjects.triggers||[]).length" class="obj-row-head obj-row-trig-head">
                <span class="orh-check"></span>
                <span class="orh-name sortable" @click="toggleTrigSort('name')">
                  이름 <span class="orh-sort-icon">{{ trigSortIcon('name') }}</span>
                </span>
                <span class="orh-meta sortable" @click="toggleTrigSort('event')">
                  이벤트 <span class="orh-sort-icon">{{ trigSortIcon('event') }}</span>
                </span>
                <span class="orh-meta sortable" @click="toggleTrigSort('table')">
                  대상 <span class="orh-sort-icon">{{ trigSortIcon('table') }}</span>
                </span>
              </div>
              <label v-for="o in filteredObjs('triggers')" :key="o.name" class="obj-row">
                <input type="checkbox" v-model="form.triggers" :value="o.name"/>
                <span class="obj-name">{{ o.name }}</span>
                <span class="obj-meta">{{ o.event }}</span>
                <span class="obj-meta">{{ o.table }}</span>
              </label>
            </div>
          </div>

          <!-- 뷰 박스 -->
          <div class="obj-box obj-box-view" :class="{'box-active': form.views.length > 0}">
            <div class="obj-box-header obj-box-header-clickable"
                 @click="toggleAllForTab('views')"
                 :title="isAllSelForTab('views') ? '전체 해제' : '전체 선택'">
              <span class="obj-box-icon">👁</span>
              <span class="obj-box-title">뷰</span>
              <span class="obj-box-count">({{ (allObjects.views||[]).length }})</span>
              <span v-if="form.views.length" class="obj-box-sel-badge">✓{{ form.views.length }}</span>
              <span class="obj-box-toggle-icon">{{ isAllSelForTab('views') ? '☑' : isPartialSelForTab('views') ? '◧' : '☐' }}</span>
            </div>
            <div class="obj-box-body">
              <div v-if="!(allObjects.views||[]).length" class="obj-box-empty">뷰 없음</div>
              <!-- v90.75: 뷰 컬럼 헤더 (이름) -->
              <div v-if="(allObjects.views||[]).length" class="obj-row-head obj-row-obj-head">
                <span class="orh-check"></span>
                <span class="orh-name sortable" @click="toggleViewSort('name')">
                  이름 <span class="orh-sort-icon">{{ viewSortIcon('name') }}</span>
                </span>
                <span class="orh-meta">타입</span>
              </div>
              <label v-for="o in filteredObjs('views')" :key="o.name" class="obj-row">
                <input type="checkbox" v-model="form.views" :value="o.name"/>
                <span class="obj-name">{{ o.name }}</span>
                <span class="obj-meta">VIEW</span>
              </label>
            </div>
          </div>
        </div>
        </div><!-- /v-else wrapper for policy + sort + grid (v90.48) -->

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

        <!-- ── v95_p23a (2026-05-03 본부장님 본질 처방): 사전 분석 결과 ── -->
        <!-- 본부장님 호소: "Dead lock 걸릴 거 분석해서 회피" -->
        <div v-if="preflightAnalyzing" class="preflight-banner preflight-loading">
          <span class="spinner" style="width:14px;height:14px;display:inline-block"></span>
          <span><strong>사전 분석 진행 중…</strong> Deadlock / AI 변환 / 의존성 / 성능 위험 검사</span>
        </div>
        <div v-else-if="preflightSummary.total > 0" class="preflight-banner"
             :class="preflightSummary.critical > 0 ? 'preflight-critical' :
                     preflightSummary.warn > 0 ? 'preflight-warn' : 'preflight-info'">
          <div class="preflight-header" @click="preflightOpen=!preflightOpen" style="cursor:pointer">
            <span class="preflight-icon">
              {{ preflightSummary.critical > 0 ? '🔴' :
                 preflightSummary.warn > 0 ? '🟡' : 'ℹ️' }}
            </span>
            <span class="preflight-title">
              <strong>사전 분석 완료</strong> — 위험 {{ preflightSummary.total }}건 감지
              <span v-if="preflightSummary.critical > 0" class="preflight-badge crit">긴급 {{ preflightSummary.critical }}</span>
              <span v-if="preflightSummary.warn > 0" class="preflight-badge warn">주의 {{ preflightSummary.warn }}</span>
              <span v-if="preflightSummary.info > 0" class="preflight-badge info">정보 {{ preflightSummary.info }}</span>
              <span v-if="preflightSummary.auto_fix_count > 0" class="preflight-badge fix">
                ✓ 자동 수정 {{ preflightSummary.auto_fix_count }}
              </span>
            </span>
            <!-- v95_p37 본질 1 (2026-05-05 본부장님): sort 토글 -->
            <div v-if="preflightOpen" class="pf-sort-controls" @click.stop>
              <span class="pf-sort-label">정렬:</span>
              <button class="pf-sort-btn" :class="{'on': pfSortMode==='severity'}"
                      @click="pfSortMode='severity'" title="긴급 → 주의 → 정보 순">위험도</button>
              <button class="pf-sort-btn" :class="{'on': pfSortMode==='category'}"
                      @click="pfSortMode='category'" title="카테고리 그룹 순">카테고리</button>
              <button class="pf-sort-btn" :class="{'on': pfSortMode==='affected'}"
                      @click="pfSortMode='affected'" title="영향 객체 많은 순">영향순</button>
            </div>
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5"
                 :style="{transform:preflightOpen?'rotate(180deg)':'rotate(0)',transition:'transform .2s',width:'12px',height:'12px',marginLeft:'10px',opacity:.6}">
              <polyline points="2,5 7,10 12,5"/>
            </svg>
          </div>
          <!-- v95_p37 본질 1 (2026-05-05): 좌-우 마스터-디테일 레이아웃 -->
          <div v-if="preflightOpen" class="pf-master-detail">
            <!-- 좌측: 간략 리스트 (sort 적용) -->
            <div class="pf-list">
              <!-- v95_p84 (2026-05-06 본부장님): 일괄 처리 헤더 -->
              <!--   본부장님 호소: "오른쪽 창을 끝까지 드레그 한 후 하나씩 선택하기 너무 번거로워" -->
              <!--   효과: 위험 객체 N개 → 한 번 클릭으로 모두 같은 결정 -->
              <div v-if="objectRiskCount > 0" class="pf-bulk-actions">
                <span class="pf-bulk-label">⚡ 일괄 처리 ({{ objectRiskCount }}건):</span>
                <!-- v95_p89_ux (2026-05-07 본부장님): 라벨 + 더 명확한 title -->
                <button class="pf-bulk-btn pf-bulk-auto"
                        @click="setAllObjectDecisions('auto')"
                        title="🤖 모든 위험 객체를 [자동 변환] 으로 — AI 가 변환 + 안전 검증 (추천)">
                  🤖 모두 자동
                </button>
                <button class="pf-bulk-btn pf-bulk-exclude"
                        @click="setAllObjectDecisions('exclude')"
                        title="⊘ 모든 위험 객체를 [이관 제외] 로 — 이관하지 않음">
                  ⊘ 모두 제외
                </button>
                <button class="pf-bulk-btn pf-bulk-clear"
                        @click="clearAllObjectDecisions()"
                        title="↻ 모든 결정 초기화 — 다시 선택할 수 있게 비움">
                  ↻ 초기화
                </button>
              </div>
              
              <div v-for="(r,ri) in sortedPreflightRisks" :key="ri"
                   class="pf-list-item"
                   :class="['pf-level-' + r.level, {'pf-selected': pfSelectedIdx === ri}]"
                   @click="pfSelectedIdx = ri">
                <span class="pf-list-level" :class="'level-' + r.level">
                  {{ r.level === 'critical' ? '긴급' : r.level === 'warn' ? '주의' : '정보' }}
                </span>
                <span class="pf-list-cat-icon">
                  {{ r.category === 'deadlock_risk' ? '🔒' :
                     r.category === 'ai_conversion' ? '🤖' :
                     r.category === 'dependency' ? '🔗' :
                     r.category === 'performance' ? '⚡' :
                     r.category === 'object_risk' ? '⚠️' : '📋' }}
                </span>
                <span class="pf-list-title">{{ r.title }}</span>
                <!-- v95_p75 (2026-05-06 본부장님): 객체별 결정 뱃지 표시 -->
                <span v-if="r.category === 'object_risk' && r.risk_meta && getObjectDecision(r.risk_meta.obj_name)"
                      class="pf-list-decision-badge"
                      :class="'pf-list-decision-' + getObjectDecision(r.risk_meta.obj_name)"
                      :title="'결정: ' + getObjectDecisionLabel(r.risk_meta.obj_name)">
                  {{ getObjectDecision(r.risk_meta.obj_name) === 'auto' ? '🤖' :
                     getObjectDecision(r.risk_meta.obj_name) === 'manual' ? '✍️' :
                     getObjectDecision(r.risk_meta.obj_name) === 'exclude' ? '⊘' : '' }}
                </span>
                <span v-if="r.affected_count" class="pf-list-count">{{ r.affected_count }}</span>
                <!-- v95_p84 (2026-05-06 본부장님): 좌측 인라인 결정 버튼 -->
                <!--   본부장님 호소:                                          -->
                <!--   "오른쪽 창을 끝까지 드레그 한 후 하나씩 선택하기 너무 번거로워" -->
                <!--   효과: 좌측에서 즉시 결정 가능 — 우측 드래그 0          -->
                <span v-if="r.category === 'object_risk' && r.risk_meta"
                      class="pf-list-quick-actions"
                      @click.stop>
                  <!-- ════════════════════════════════════════════════════════ -->
                  <!-- v95_p89_ux (2026-05-07 본부장님 본질 처방):                 -->
                  <!-- 풍선 도움말 강화 — title 만으로 부족 → data-tip + CSS tooltip -->
                  <!-- 본부장님 호소: "로봇/손글씨 무슨 뜻인지 모르겠어"            -->
                  <!-- ════════════════════════════════════════════════════════ -->
                  <button class="pf-quick-btn pf-quick-auto"
                          :class="{ active: getObjectDecision(r.risk_meta.obj_name) === 'auto' }"
                          @click.stop="setObjectDecision(r.risk_meta.obj_name, 'auto')"
                          title="🤖 자동 변환 — AI 가 변환 후 안전 검증 (추천)"
                          data-tip="🤖 자동 변환 (AI + 안전 검증)">
                    🤖
                  </button>
                  <button class="pf-quick-btn pf-quick-manual"
                          :class="{ active: getObjectDecision(r.risk_meta.obj_name) === 'manual' }"
                          @click.stop="setObjectDecision(r.risk_meta.obj_name, 'manual'); pfSelectedIdx = ri; openManualSqlModal(r.risk_meta.obj_name)"
                          title="✍️ 직접 작성 — DBA 가 직접 SQL 작성 (전문가용)"
                          data-tip="✍️ 직접 작성 (DBA 전문가)">
                    ✍️
                  </button>
                  <button class="pf-quick-btn pf-quick-exclude"
                          :class="{ active: getObjectDecision(r.risk_meta.obj_name) === 'exclude' }"
                          @click.stop="setObjectDecision(r.risk_meta.obj_name, 'exclude')"
                          title="⊘ 이관 제외 — 이 객체는 이관하지 않음"
                          data-tip="⊘ 이관 제외">
                    ⊘
                  </button>
                </span>
              </div>
            </div>
            <!-- 우측: 상세 -->
            <div class="pf-detail">
              <template v-if="selectedRisk">
                <div class="pf-detail-head">
                  <span class="pf-detail-level" :class="'level-' + selectedRisk.level">
                    {{ selectedRisk.level === 'critical' ? '긴급' :
                       selectedRisk.level === 'warn' ? '주의' : '정보' }}
                  </span>
                  <span class="pf-detail-cat">
                    {{ selectedRisk.category === 'deadlock_risk' ? '🔒 Deadlock' :
                       selectedRisk.category === 'ai_conversion' ? '🤖 AI 변환' :
                       selectedRisk.category === 'dependency' ? '🔗 의존성' :
                       selectedRisk.category === 'performance' ? '⚡ 성능' :
                       selectedRisk.category === 'object_risk' ? '⚠️ 객체 변환 위험' : selectedRisk.category }}
                  </span>
                  <span class="pf-detail-title">{{ selectedRisk.title }}</span>
                </div>
                <div class="pf-detail-desc">{{ selectedRisk.desc }}</div>
                <div v-if="selectedRisk.affected && selectedRisk.affected.length > 0"
                     class="pf-detail-affected">
                  <div class="pf-detail-section-label">
                    영향 객체 <span class="pf-detail-section-count">({{ selectedRisk.affected_count || selectedRisk.affected.length }}개)</span>
                  </div>
                  <div class="pf-detail-chips">
                    <span v-for="(a,ai) in (showAllAffected ? selectedRisk.affected : selectedRisk.affected.slice(0, 10))"
                          :key="ai" class="preflight-chip">{{ a }}</span>
                    <button v-if="selectedRisk.affected.length > 10 || (selectedRisk.affected_count > selectedRisk.affected.length)"
                            class="pf-show-more-btn"
                            @click="showAllAffected=!showAllAffected">
                      {{ showAllAffected ? '접기' :
                         `+${(selectedRisk.affected_count || selectedRisk.affected.length) - 10}개 더 보기` }}
                    </button>
                  </div>
                </div>
                <!-- v95_p64 (2026-05-05 본부장님): object_risk 상세 메타 카드 -->
                <!--   본부장님 결정: "5 Phase 모두 순차 — 엔터프라이즈 솔루션" -->
                <!--   검출된 위험 패턴 + 자동 변환 신뢰도 + MySQL 대안 가이드 -->
                <div v-if="selectedRisk.category === 'object_risk' && selectedRisk.risk_meta"
                     class="pf-detail-risk-meta">
                  <!-- 신뢰도 게이지 -->
                  <div v-if="selectedRisk.risk_meta.confidence_pct !== undefined"
                       class="pf-rm-confidence">
                    <div class="pf-rm-conf-label">
                      자동 변환 신뢰도
                      <strong :class="{
                        'pf-rm-conf-low':  selectedRisk.risk_meta.confidence_pct < 30,
                        'pf-rm-conf-mid':  selectedRisk.risk_meta.confidence_pct >= 30 && selectedRisk.risk_meta.confidence_pct < 70,
                        'pf-rm-conf-high': selectedRisk.risk_meta.confidence_pct >= 70,
                      }">{{ selectedRisk.risk_meta.confidence_pct }}%</strong>
                    </div>
                    <div class="pf-rm-conf-bar">
                      <div class="pf-rm-conf-fill"
                           :style="{
                             width: selectedRisk.risk_meta.confidence_pct + '%',
                             background: selectedRisk.risk_meta.confidence_pct < 30 ? '#dc2626' :
                                         selectedRisk.risk_meta.confidence_pct < 70 ? '#f59e0b' : '#16a34a'
                           }">
                      </div>
                    </div>
                  </div>
                  <!-- 검출 패턴 목록 -->
                  <div v-if="selectedRisk.risk_meta.detected_patterns && selectedRisk.risk_meta.detected_patterns.length > 0"
                       class="pf-rm-patterns">
                    <div class="pf-detail-section-label">
                      검출된 위험 패턴
                      <span class="pf-detail-section-count">({{ selectedRisk.risk_meta.detected_patterns.length }}개)</span>
                    </div>
                    <div v-for="(p, pi) in selectedRisk.risk_meta.detected_patterns" :key="pi"
                         class="pf-rm-pattern-card"
                         :class="'pf-rm-pat-' + (p.risk_level || '').toLowerCase()">
                      <div class="pf-rm-pat-head">
                        <span class="pf-rm-pat-level">
                          {{ p.risk_level === 'HIGH' ? '🔴 HIGH' :
                             p.risk_level === 'MEDIUM' ? '🟡 MEDIUM' : '🟢 LOW' }}
                        </span>
                        <span class="pf-rm-pat-label">{{ p.label }}</span>
                      </div>
                      <div v-if="p.description" class="pf-rm-pat-desc">{{ p.description }}</div>
                      <div v-if="p.mysql_alternative" class="pf-rm-pat-alt">
                        <strong>💡 대안:</strong> {{ p.mysql_alternative }}
                      </div>
                      <div v-if="p.matches && p.matches.length > 0" class="pf-rm-pat-matches">
                        <code v-for="(m, mi) in p.matches.slice(0, 2)" :key="mi"
                              class="pf-rm-pat-match">{{ m }}</code>
                      </div>
                    </div>
                  </div>
                  <!-- 권장 처리 -->
                  <div v-if="selectedRisk.risk_meta.recommendation"
                       class="pf-rm-recommendation">
                    {{ selectedRisk.risk_meta.recommendation }}
                  </div>
                  <!-- v95_p73: 사용자 친화 추가 안내 (HIGH 위험 객체용) -->
                  <div v-if="selectedRisk.risk_meta.overall_risk === 'HIGH'"
                       class="pf-rm-friendly-note">
                    <strong>💡 걱정하지 마세요!</strong><br>
                    DataBridge 가 알아서 처리합니다. 아래 [자동 변환 시도] 를 선택하시면:
                    <ul class="pf-rm-friendly-list">
                      <li>AI 가 MSSQL → MySQL 변환을 시도합니다</li>
                      <li>가짜 테이블 등 오류는 <strong>자동으로 검출 + 수정</strong> 됩니다 (v95_p72)</li>
                      <li>이관 후 검토 화면에서 변환 결과 + 자동 수정 노트 확인 가능</li>
                      <li>문제가 있으면 [이관 제외] 로 다시 처리 가능 (테이블 데이터는 이관됨)</li>
                    </ul>
                  </div>
                  <!-- v95_p65 (2026-05-05 본부장님): 사용자 결정 3-옵션 버튼 -->
                  <!-- v95_p73 (2026-05-06 본부장님 5번째 통찰): 사용자 친화 -->
                  <!-- v95_p76 (2026-05-06 본부장님 추가): 컴팩트 라디오 리스트 -->
                  <!--   본부장님 호소:                                       -->
                  <!--   "3가지 선택할 수 있는 블록은 조금 줄여도 될 것 같아"  -->
                  <!--   "check box 로 선택할 수 있게 해주는것도 좋겠어"      -->
                  <!--   효과:                                                 -->
                  <!--   - 가로 카드 3개 → 세로 라디오 3줄 (높이 절반)        -->
                  <!--   - 라디오 형태로 명확한 선택 표시                       -->
                  <!--   - 우측 상세 영역 줄어든 폭에 맞음                     -->
                  <div class="pf-rm-decision pf-rm-decision-compact">
                    <div class="pf-rm-decision-label">
                      📋 변환 방법 선택
                    </div>
                    <div class="pf-rm-decision-help">
                      💡 잘 모르시면 <strong>[자동 변환 시도]</strong> 추천 — AI 변환 + 환각 자동 검증
                    </div>
                    <!-- v95_p76: 라디오 리스트 (컴팩트) -->
                    <div class="pf-rm-radio-list">
                      <label class="pf-rm-radio-row pf-rm-radio-auto"
                             :class="{ active: getObjectDecision(selectedRisk.risk_meta.obj_name) === 'auto' }">
                        <input type="radio"
                               :name="'decision-' + selectedRisk.risk_meta.obj_name"
                               :checked="getObjectDecision(selectedRisk.risk_meta.obj_name) === 'auto'"
                               @change="setObjectDecision(selectedRisk.risk_meta.obj_name, 'auto')"
                               class="pf-rm-radio-input">
                        <span class="pf-rm-radio-icon">🤖</span>
                        <span class="pf-rm-radio-text">
                          <strong>자동 변환 시도</strong>
                          <span class="pf-rm-radio-sub">AI 변환 + 환각 자동 검증 (추천)</span>
                        </span>
                      </label>
                      <label class="pf-rm-radio-row pf-rm-radio-manual"
                             :class="{ active: getObjectDecision(selectedRisk.risk_meta.obj_name) === 'manual' }">
                        <input type="radio"
                               :name="'decision-' + selectedRisk.risk_meta.obj_name"
                               :checked="getObjectDecision(selectedRisk.risk_meta.obj_name) === 'manual'"
                               @change="setObjectDecision(selectedRisk.risk_meta.obj_name, 'manual'); openManualSqlModal(selectedRisk.risk_meta.obj_name)"
                               class="pf-rm-radio-input">
                        <span class="pf-rm-radio-icon">✍️</span>
                        <span class="pf-rm-radio-text">
                          <strong>전문가 직접 작성</strong>
                          <span class="pf-rm-radio-sub">DBA 만 권장 (MySQL DDL 직접)</span>
                        </span>
                      </label>
                      <label class="pf-rm-radio-row pf-rm-radio-exclude"
                             :class="{ active: getObjectDecision(selectedRisk.risk_meta.obj_name) === 'exclude' }">
                        <input type="radio"
                               :name="'decision-' + selectedRisk.risk_meta.obj_name"
                               :checked="getObjectDecision(selectedRisk.risk_meta.obj_name) === 'exclude'"
                               @change="setObjectDecision(selectedRisk.risk_meta.obj_name, 'exclude')"
                               class="pf-rm-radio-input">
                        <span class="pf-rm-radio-icon">⊘</span>
                        <span class="pf-rm-radio-text">
                          <strong>이관 제외</strong>
                          <span class="pf-rm-radio-sub">이 객체 없이 진행</span>
                        </span>
                      </label>
                    </div>
                    <!-- v95_p73: 결정별 짧은 설명 (컴팩트하게) -->
                    <div v-if="getObjectDecision(selectedRisk.risk_meta.obj_name) === 'manual'"
                         class="pf-rm-d-explain pf-rm-d-explain-manual pf-rm-d-explain-compact">
                      ⚠️ <strong>전문가 모드</strong> — 잘못 작성 시 이관 실패 가능
                    </div>
                    <div v-if="getObjectDecision(selectedRisk.risk_meta.obj_name) === 'exclude'"
                         class="pf-rm-d-explain pf-rm-d-explain-exclude pf-rm-d-explain-compact">
                      ⊘ <strong>이관 제외</strong> — 응용 프로그램에서 이 VIEW 사용 시 별도 처리 필요
                    </div>
                    <!-- v95_p75 (이전): 현재 결정 표시 강화 -->
                    <!--   본부장님 호소: "어떤걸 선택했는지 보여 주자"        -->
                    <!--   강화: 큰 뱃지 + 색상 + 아이콘으로 즉시 인식 가능   -->
                    <div v-if="getObjectDecision(selectedRisk.risk_meta.obj_name)"
                         class="pf-rm-d-status pf-rm-d-status-strong"
                         :class="'pf-rm-d-status-strong-' + getObjectDecision(selectedRisk.risk_meta.obj_name)">
                      <span class="pf-rm-d-status-icon">
                        {{ getObjectDecision(selectedRisk.risk_meta.obj_name) === 'auto' ? '🤖' :
                           getObjectDecision(selectedRisk.risk_meta.obj_name) === 'manual' ? '✍️' :
                           getObjectDecision(selectedRisk.risk_meta.obj_name) === 'exclude' ? '⊘' : '' }}
                      </span>
                      <span class="pf-rm-d-status-text">
                        <span class="pf-rm-d-status-label">선택됨:</span>
                        <span class="pf-rm-d-status-value"
                              :class="'pf-rm-d-status-' + getObjectDecision(selectedRisk.risk_meta.obj_name)">
                          {{ getObjectDecisionLabel(selectedRisk.risk_meta.obj_name) }}
                        </span>
                      </span>
                      <button class="pf-rm-d-clear" @click="clearObjectDecision(selectedRisk.risk_meta.obj_name)">
                        ↻ 변경
                      </button>
                    </div>
                  </div>
                </div>
                <div v-if="selectedRisk.auto_fix" class="pf-detail-fix">
                  <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2"
                       style="width:13px;height:13px;flex-shrink:0">
                    <polyline points="2,6 5,9 10,3"/>
                  </svg>
                  <span>{{ selectedRisk.auto_fix }}</span>
                </div>
              </template>
              <div v-else class="pf-detail-empty">
                ← 좌측에서 항목을 선택하세요
              </div>
            </div>
          </div>
        </div>

        <!-- ── 타입 정규화 규칙 ── -->
        <div class="norm-section">
          <div class="norm-header" @click="normOpen=!normOpen" style="cursor:pointer">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4"
                 :style="{transform:normOpen?'rotate(0)':'rotate(-90deg)',transition:'transform .2s'}"
                 style="width:9px;height:9px;opacity:.5">
              <polyline points="1,3 7,9 13,3"/>
            </svg>
            <span class="norm-title">타입 정규화 규칙</span>
            <span v-if="activeNormCount" class="norm-badge">{{ activeNormCount }} / {{ normRules.length }}개 적용</span>
            <span v-else-if="normRules.length" class="norm-badge" style="background:var(--surface-subtle);color:var(--text-tertiary)">
              0 / {{ normRules.length }}개 적용
            </span>
            <span class="norm-desc">{{ form.srcDb?.toUpperCase() }} → {{ form.tgtDb?.toUpperCase() }} 타입 변환 규칙을 선택하세요</span>
            <!-- v95_p25 (2026-05-04 본부장님 본질 처방): 전체선택/전체해제 버튼 -->
            <div v-if="normRules.length" class="norm-bulk-actions" @click.stop>
              <button class="norm-bulk-btn" @click="selectAllNorms" :disabled="isAllNormsSelected"
                      :title="isAllNormsSelected ? '이미 모두 선택됨' : `${normRules.length}개 규칙 모두 선택`">
                ✓ 전체 선택
              </button>
              <button class="norm-bulk-btn" @click="clearAllNorms" :disabled="!form.normActions.length"
                      :title="!form.normActions.length ? '선택된 규칙 없음' : '모두 해제'">
                ✗ 전체 해제
              </button>
            </div>
          </div>

          <template v-if="normOpen">
            <div v-if="!normRules.length" style="padding:12px 14px;font-size:12px;color:var(--text-tertiary)">
              해당 DB 조합의 정규화 규칙이 없습니다
            </div>
            <template v-else>
              <!-- v95_p37 본질 2 (2026-05-05 본부장님): 적용 규칙 먼저 + 미적용 접힘 -->
              <!-- 적용된 규칙 (체크된 것) — 항상 펼쳐짐 -->
              <div v-if="appliedNormRules.length" class="norm-list norm-applied">
                <div class="norm-group-label norm-group-applied">
                  <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2"
                       style="width:11px;height:11px"><polyline points="2,6 5,9 10,3"/></svg>
                  <span>적용 규칙 ({{ appliedNormRules.length }}개)</span>
                </div>
                <label v-for="rule in appliedNormRules" :key="rule.fix_action"
                       class="norm-item active">
                  <input type="checkbox" style="display:none"
                    :checked="form.normActions.includes(rule.fix_action)"
                    @change="toggleNorm(rule.fix_action)"/>
                  <div class="norm-item-left">
                    <span class="norm-chk on">
                      <svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="1.5,5 4,7.5 8.5,2"/>
                      </svg>
                    </span>
                    <div>
                      <div class="norm-item-title">{{ rule.title }}</div>
                      <div class="norm-item-types">
                        <span class="type-chip src">{{ rule.src_type }}</span>
                        <svg viewBox="0 0 10 8" fill="none" stroke="currentColor" stroke-width="1.3" style="width:10px;height:8px;opacity:.4"><path d="M1 4h8M6 1l3 3-3 3"/></svg>
                        <span class="type-chip tgt">{{ rule.tgt_type }}</span>
                      </div>
                    </div>
                  </div>
                  <span class="norm-item-level" :class="rule.level">{{ rule.level==='warn'?'주의':'정보' }}</span>
                </label>
              </div>
              <!-- 미적용 규칙 — 기본 접힘, 클릭하면 펼침 -->
              <div v-if="unappliedNormRules.length" class="norm-list norm-unapplied">
                <div class="norm-group-label norm-group-collapsible"
                     @click="normUnappliedOpen=!normUnappliedOpen"
                     style="cursor:pointer">
                  <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4"
                       :style="{transform:normUnappliedOpen?'rotate(0)':'rotate(-90deg)',transition:'transform .2s'}"
                       style="width:9px;height:9px;opacity:.5">
                    <polyline points="1,3 7,9 13,3"/>
                  </svg>
                  <span>미적용 규칙 ({{ unappliedNormRules.length }}개)</span>
                  <span class="norm-group-hint">클릭하여 펼치기</span>
                </div>
                <template v-if="normUnappliedOpen">
                  <label v-for="rule in unappliedNormRules" :key="rule.fix_action"
                         class="norm-item">
                    <input type="checkbox" style="display:none"
                      :checked="form.normActions.includes(rule.fix_action)"
                      @change="toggleNorm(rule.fix_action)"/>
                    <div class="norm-item-left">
                      <span class="norm-chk"></span>
                      <div>
                        <div class="norm-item-title">{{ rule.title }}</div>
                        <div class="norm-item-types">
                          <span class="type-chip src">{{ rule.src_type }}</span>
                          <svg viewBox="0 0 10 8" fill="none" stroke="currentColor" stroke-width="1.3" style="width:10px;height:8px;opacity:.4"><path d="M1 4h8M6 1l3 3-3 3"/></svg>
                          <span class="type-chip tgt">{{ rule.tgt_type }}</span>
                        </div>
                      </div>
                    </div>
                    <span class="norm-item-level" :class="rule.level">{{ rule.level==='warn'?'주의':'정보' }}</span>
                  </label>
                </template>
              </div>
            </template>
          </template>
        </div>

        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;margin-top:16px">
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

      <!-- ── Step 3: AI 분석 센터 (v90.17: v-show 로 변경 - 단계 이동해도 분석 상태 유지) ── -->
      <template v-if="analysisTabsLoaded">
        <div v-show="cur===3">
          <AnalysisTabs
            :migration-scenario="form.migrationScenario"
            :src-db="form.srcDb"
            :tgt-db="form.tgtDb"
            :selection="{
              tables: form.tables,
              procedures: form.procedures,
              functions: form.functions,
              triggers: form.triggers,
              views: form.views,
            }"
            :source-profile-id="form.srcConnId || ''"
            :initial-advisor-analysis="form.advisorAnalysis"
            :initial-active-tab="form.activeAnalysisTab"
            @update:advisor-mode="(m) => form.advisorMode = m"
            @update:advisor-decisions="(d) => form.advisorDecisions = d"
            @update:advisor-analysis="(a) => form.advisorAnalysis = a"
            @advisor-skip="onAdvisorSkip"
            @update:privacy-preset="(p) => form.privacyPreset = p"
            @update:privacy-decisions="(d) => form.privacyDecisions = d"
            @update:privacy-scan-result="(r) => form.privacyScan = r"
            @privacy-skip="onPrivacySkip"
            @tab-visited="onTabVisited"
          />
        </div>
      </template>

      <!-- ── Step 4: 실행 옵션 (v88: 기존 Step 3에서 재번호) ── -->
      <template v-if="cur===4">
        <div class="opts-grid">
          <div>
            <div class="field-label">Job 이름 *</div>
            <input type="text" v-model="form.name" :placeholder="`${connector.source.database} → ${connector.target.database} 이관`" :class="{err:v3&&!form.name}"/>
            <div class="field-label">배치 크기 (rows)</div>
            <input type="number" v-model="form.batchSize" min="100" max="100000"/>
            <!-- v9 패치 #20: Bulk 로더 선택 -->
            <div class="field-label">이관 엔진 <span style="color:var(--accent-blue);font-size:10px">(대용량)</span></div>
            <div class="sel-wrap">
              <select v-model="form.bulkMode">
                <option value="auto">🚀 자동 (대용량 자동 BCP)</option>
                <option value="executemany">⚙ Executemany (표준 INSERT)</option>
                <option value="bcp">⚡ MSSQL BCP (최고속, bcp.exe 필요)</option>
                <option value="pymssql">🔧 pymssql bulk (중간, 추가설치 없음)</option>
              </select>
              <div class="chev"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>
            </div>
            <div class="field-label">Bulk 전환 임계값 (auto 모드)</div>
            <input type="number" v-model.number="form.bulkThresholdRows" min="1000" max="10000000" step="10000"/>
            <!-- v9 패치 #23: 테이블 병렬도 -->
            <div class="field-label">테이블 동시 처리 수 <span style="color:var(--accent-blue);font-size:10px">(FK 레벨별)</span></div>
            <div class="sel-wrap">
              <select v-model.number="form.parallelTables">
                <option :value="1">1개 (순차, 안전)</option>
                <option :value="2">2개 동시</option>
                <option :value="3">3개 동시 (권장)</option>
                <option :value="5">5개 동시</option>
                <option :value="8">8개 동시 (고성능 서버)</option>
              </select>
              <div class="chev"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>
            </div>
            <!-- v9 패치 #23: MSSQL 튜닝 -->
            <div class="field-label">MSSQL 타겟 튜닝 <span style="color:#eab308;font-size:10px">(주의: 이관 전용)</span></div>
            <label style="display:flex;align-items:center;gap:6px;font-size:12px;margin:4px 0">
              <input type="checkbox" v-model="form.mssqlTuning"/>
              Recovery Model → BULK_LOGGED (로그 크기 감소)
            </label>
            <label style="display:flex;align-items:center;gap:6px;font-size:12px;margin:4px 0">
              <input type="checkbox" v-model="form.mssqlDisableIndexes"/>
              대용량 테이블 비클러스터 인덱스 일시 비활성화
            </label>
            <div class="field-label">병렬 처리 수 (테이블 내부)</div>
            <div class="sel-wrap"><select v-model="form.workers"><option v-for="n in [1,2,4,8,16]" :key="n" :value="n">{{ n }}개 스레드</option></select><div class="chev"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div></div>
            <div class="field-label">오류 처리</div>
            <div class="sel-wrap"><select v-model="form.onError"><option value="skip">오류 row 건너뜀</option><option value="retry">재시도 후 건너뜀</option><option value="abort">즉시 중단</option></select><div class="chev"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div></div>
          </div>
          <div>
            <template v-if="form.tables.length > 0">
            <div class="mode-section-hd mode-hd-blue">
              <span class="mode-section-ico">⊞</span>
              <span class="mode-section-title">테이블 이관 모드</span>
            </div>
            <div class="mode-cards-h">
              <label v-for="m in tableModes" :key="m.v"
                class="mode-card-h" :class="[{active: form.tableMode===m.v}, m.color]">
                <input type="radio" v-model="form.tableMode" :value="m.v"/>
                <div class="mch-icon">{{ m.icon }}</div>
                <div class="mch-body">
                  <div class="mch-title">{{ m.label }}</div>
                  <div class="mch-desc">{{ m.desc }}</div>
                </div>
                <div class="mch-check" v-if="form.tableMode===m.v">✓</div>
              </label>
            </div>

            <div class="tbl-opts-box">
              <div class="tbl-opts-title">추가 옵션</div>
              
              <!-- v90.16: 위험 경고 - drop=False AND truncate=False 일 때 -->
              <div v-if="form.tableMode!=='schema_only' && !form.dropTbl && !form.truncate"
                   class="tbl-opt-warning">
                <div class="tbl-opt-warn-icon">⚠️</div>
                <div class="tbl-opt-warn-content">
                  <div class="tbl-opt-warn-title">데이터 정리 옵션이 모두 꺼져있습니다</div>
                  <div class="tbl-opt-warn-desc">
                    타겟에 이미 데이터가 있으면 <b>"Duplicate entry for PRIMARY"</b> 같은 PK 충돌 오류가 발생합니다.<br>
                    아래 <b>TRUNCATE</b> 또는 <b>DROP</b> 옵션을 켜는 것을 권장합니다.
                  </div>
                </div>
              </div>
              
              <!-- DROP TABLE 옵션 -->
              <label class="tbl-opt-row drop-opt" v-if="form.tableMode!=='data_only'">
                <input type="checkbox" v-model="form.dropTbl"/>
                <div class="tbl-opt-info">
                  <div class="tbl-opt-label">
                    <span class="opt-tag danger">DROP</span>
                    이관 전 타겟 테이블 DROP
                  </div>
                  <span class="tbl-opt-desc">타겟 테이블을 DROP 후 재생성 — 구조 변경 시 사용 (데이터 완전 삭제)</span>
                </div>
              </label>
              <!-- TRUNCATE 옵션 (DROP과 상호 배타) -->
              <label class="tbl-opt-row" v-if="form.tableMode!=='schema_only' && !form.dropTbl">
                <input type="checkbox" v-model="form.truncate"/>
                <div class="tbl-opt-info">
                  <div class="tbl-opt-label">
                    <span class="opt-tag warn">TRUNCATE</span>
                    이관 전 타겟 데이터 삭제 <span class="opt-recommend">(권장)</span>
                  </div>
                  <span class="tbl-opt-desc">기존 데이터만 지우고 구조는 유지한 채로 새로 채움 — Duplicate Key 오류 방지</span>
                </div>
              </label>
              <label class="tbl-opt-row" v-if="form.tableMode!=='data_only'">
                <input type="checkbox" v-model="form.createTbl"/>
                <div class="tbl-opt-info">
                  <span class="tbl-opt-label">타겟 테이블 없으면 자동 생성</span>
                  <span class="tbl-opt-desc">DDL을 자동 변환해서 타겟에 테이블 생성</span>
                </div>
              </label>
              <label class="tbl-opt-row" v-if="form.tableMode!=='data_only'">
                <input type="checkbox" v-model="form.withIdx"/>
                <div class="tbl-opt-info">
                  <span class="tbl-opt-label">인덱스 함께 생성</span>
                  <span class="tbl-opt-desc">소스 테이블의 인덱스를 타겟에도 생성</span>
                </div>
              </label>
              <label class="tbl-opt-row" v-if="hasObjects">
                <input type="checkbox" v-model="form.convertObjs"/>
                <div class="tbl-opt-info">
                  <span class="tbl-opt-label">오브젝트 방언 자동 변환</span>
                  <span class="tbl-opt-desc">SP/Function/Trigger/View를 타겟 DB 문법으로 변환</span>
                </div>
              </label>
              <!-- v90.32: 트리거 skip 옵션 (복잡한 트리거로 hang 방지) -->
              <label class="tbl-opt-row" v-if="form.triggers && form.triggers.length > 0">
                <input type="checkbox" v-model="form.skipTriggers"/>
                <div class="tbl-opt-info">
                  <div class="tbl-opt-label">
                    <span class="opt-tag warn">SKIP</span>
                    트리거 이관 건너뛰기
                  </div>
                  <span class="tbl-opt-desc">
                    복잡한 트리거가 변환 중 hang 되는 경우 사용 — 트리거는 수동으로 처리
                    (현재 선택된 트리거 {{ form.triggers.length }}개)
                  </span>
                </div>
              </label>
              <!-- v92p11 (2026-04-30): AI 자동 재이관 토글
                   본부장님 결정 — 기본 OFF. 명시적 ON 시에만 자동 재시도.
                   OFF 일 때는 실패 객체를 화면에서 🤖 AI 재이관 버튼으로 수동 처리. -->
              <label class="tbl-opt-row" v-if="hasObjects">
                <input type="checkbox" v-model="form.aiAutoRetry"/>
                <div class="tbl-opt-info">
                  <div class="tbl-opt-label">
                    <span class="opt-tag" style="background:#a855f7;color:white">🤖 AUTO</span>
                    AI 자동 재이관
                    <span v-if="form.aiAutoRetry" style="margin-left:8px;font-size:.72rem;color:#16a34a;font-weight:700">활성</span>
                    <span v-else style="margin-left:8px;font-size:.72rem;color:var(--text-tertiary)">비활성 (기본)</span>
                  </div>
                  <span class="tbl-opt-desc">
                    객체 이관 실패 시 AI 가 오류를 분석해 자동 재시도 (최대 {{ form.aiAutoRetryCount }}회).
                    <span style="color:#dc2626">OFF 권장 — 운영 환경에선 실패를 인지 후 수동 재이관이 안전.</span>
                  </span>
                </div>
              </label>
            </div>
            </template><!-- /tables > 0 -->

            <!-- 엔진 선택: 상단 공통 바로 이동됨 -->

            <!-- 뷰 이관 모드: 뷰 선택 시만 표시 -->
            <template v-if="form.views.length > 0">
              <div class="mode-section-hd mode-hd-green" style="margin-top:14px">
                <span class="mode-section-ico">◫</span>
                <span class="mode-section-title">뷰(View) 이관 모드</span>
              </div>
              <div class="mode-cards-h">
                <label v-for="m in viewModes" :key="m.v"
                  class="mode-card-h" :class="[{active: form.viewMode===m.v}, m.color]">
                  <input type="radio" v-model="form.viewMode" :value="m.v"/>
                  <div class="mch-icon">{{ m.icon }}</div>
                  <div class="mch-body">
                    <div class="mch-title">{{ m.label }}</div>
                    <div class="mch-desc">{{ m.desc }}</div>
                  </div>
                  <div class="mch-check" v-if="form.viewMode===m.v">✓</div>
                </label>
              </div>
            </template><!-- /views > 0 -->

            <!-- 프로시저/함수/트리거 이관 모드 -->
            <template v-if="(form.procedures.length + form.functions.length + form.triggers.length) > 0">
              <div class="mode-section-hd mode-hd-purple" style="margin-top:14px">
                <span class="mode-section-ico">⚙</span>
                <span class="mode-section-title">오브젝트(SP/FN/TR) 이관 모드</span>
                <span class="mode-section-badge">Claude AI 변환 지원</span>
              </div>
              <div class="mode-cards-h">
                <label v-for="m in objModes" :key="m.v"
                  class="mode-card-h" :class="[{active: form.objMode===m.v}, m.color]">
                  <input type="radio" v-model="form.objMode" :value="m.v"/>
                  <div class="mch-icon">{{ m.icon }}</div>
                  <div class="mch-body">
                    <div class="mch-title">{{ m.label }}</div>
                    <div class="mch-desc">{{ m.desc }}</div>
                  </div>
                  <div class="mch-check" v-if="form.objMode===m.v">✓</div>
                </label>
              </div>
              <div class="tbl-opts-box" style="margin-top:6px">
                <div class="tbl-opts-title">오브젝트 옵션</div>
                <label class="tbl-opt-row">
                  <input type="checkbox" v-model="form.convertObjs"/>
                  <div class="tbl-opt-info">
                    <span class="tbl-opt-label">방언 자동 변환</span>
                    <span class="tbl-opt-desc">소스 DB 문법을 타겟 DB 문법으로 자동 변환 후 이관</span>
                  </div>
                </label>
              </div>
            </template><!-- /objs > 0 -->
          </div>
        </div>
      </template>

      <!-- ── Step 5: 검토 & 실행 + 스케줄링 (v88: 기존 Step 4에서 재번호) ── -->
      <template v-if="cur===5">
        <h4 class="wh">설정 최종 검토</h4>

        <!-- v95_p37 본질 4 (2026-05-05 본부장님): 두 블록으로 분리 (기본 + 상세) -->

        <!-- 기본 정보 블록 — 한눈에 봐야 할 핵심 정보 -->
        <!-- v95_p40 (2026-05-05 본부장님): 기본 정보 — Job 이름 헤더로, 소스/타겟 좌우, 2줄 압축 -->
        <div class="review-section">
          <div class="review-section-head review-section-head-primary">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5"
                 style="width:13px;height:13px;color:#2563eb">
              <circle cx="7" cy="7" r="5.5"/>
              <line x1="7" y1="4" x2="7" y2="7.5"/>
              <circle cx="7" cy="9.8" r="0.6" fill="currentColor"/>
            </svg>
            <span class="review-section-title">기본 정보</span>
            <!-- v95_p40: Job 이름을 섹션 헤더 우측에 배치 -->
            <span class="review-section-jobname" :title="form.name">{{ form.name || '(이름 없음)' }}</span>
          </div>
          <!-- v95_p40: 2줄 압축 — 1줄: 소스 DB ↔ 타겟 DB, 2줄: 이관 모드 / AI DBA 분석 / 자동 수정 -->
          <div class="review-basic-body">
            <!-- 1줄: 소스 (좌) → 타겟 (우) -->
            <div class="review-dbflow-row">
              <div class="review-db-card review-db-source">
                <div class="review-db-label">소스 DB</div>
                <div class="review-db-value">
                  <span class="review-db-engine">{{ form.srcDb }}</span>
                  <span class="review-db-sep">/</span>
                  <span class="review-db-name">{{ connector.source.database }}</span>
                </div>
              </div>
              <div class="review-dbflow-arrow">
                <svg viewBox="0 0 24 12" fill="none" stroke="currentColor" stroke-width="1.5"
                     style="width:32px;height:14px;color:#2563eb">
                  <path d="M2 6 L20 6 M16 2 L20 6 L16 10"/>
                </svg>
              </div>
              <div class="review-db-card review-db-target">
                <div class="review-db-label">타겟 DB</div>
                <div class="review-db-value">
                  <span class="review-db-engine">{{ form.tgtDb }}</span>
                  <span class="review-db-sep">/</span>
                  <span class="review-db-name">{{ connector.target.database }}</span>
                </div>
              </div>
            </div>
            <!-- v95_p52 (2026-05-05 본부장님): 5칸 한 줄 — DDL/객체 엔진 합침 -->
            <div class="review-attr-row review-attr-row-5col">
              <div class="rv-item rv-item-compact">
                <span class="rv-l">이관 모드</span>
                <span class="rv-v">
                  {{ {schema_only:'스키마만', schema_data:'스키마+데이터', data_only:'데이터만'}[form.tableMode] }}
                </span>
              </div>
              <div class="rv-item rv-item-compact">
                <span class="rv-l">AI DBA 분석</span>
                <span class="rv-v" :style="form.advisorSkipped?'color:var(--text-tertiary)':'color:#6d28d9;font-weight:600'">
                  {{ form.advisorSkipped
                      ? '건너뜀'
                      : ({smart:'🟢 경제형', hybrid:'🟡 균형형', deep:'🔴 전수 분석'}[form.advisorMode] || form.advisorMode) }}
                </span>
              </div>
              <div class="rv-item rv-item-compact">
                <span class="rv-l">자동 수정</span>
                <span class="rv-v" style="color:var(--text-success)">{{ autoFixEnabledCount }}건</span>
              </div>
              <div class="rv-item rv-item-compact">
                <span class="rv-l">DDL 엔진</span>
                <span class="rv-v" :style="{color:form.ddlEngine==='claude'?'#6d28d9':'var(--text-secondary)', fontWeight: 600}">
                  {{ form.ddlEngine==='claude'?'🤖 AI':'⚙ 규칙' }}
                </span>
              </div>
              <div class="rv-item rv-item-compact">
                <span class="rv-l">객체 엔진</span>
                <span class="rv-v" :style="{color:form.objEngine==='claude'?'#6d28d9':'var(--text-secondary)', fontWeight: 600}">
                  {{ form.objEngine==='claude'?'🤖 AI':'⚙ 규칙' }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- v95_p48 (2026-05-05 본부장님): 이관 객체 + 변환·실행 한 카드, 표 형식, 4-column -->
        <div class="review-section">
          <div class="review-section-head review-section-head-collapsible"
               @click="reviewDetailOpen=!reviewDetailOpen" style="cursor:pointer">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4"
                 :style="{transform:reviewDetailOpen?'rotate(0)':'rotate(-90deg)',transition:'transform .2s'}"
                 style="width:9px;height:9px;opacity:.5;color:var(--text-secondary)">
              <polyline points="1,3 7,9 13,3"/>
            </svg>
            <span class="review-section-title">상세 정보</span>
            <span class="review-section-count">
              테이블 {{ form.tables.length }} ·
              SP {{ form.procedures.length }} ·
              FUNC {{ form.functions.length }} ·
              TRIG {{ form.triggers.length }} ·
              VIEW {{ form.views.length }}
              &nbsp;|&nbsp;
              {{ form.ddlEngine==='claude'?'🤖':'⚙' }} DDL ·
              {{ form.objEngine==='claude'?'🤖':'⚙' }} 객체 ·
              배치 {{ form.batchSize.toLocaleString() }}
            </span>
          </div>
          <div v-if="reviewDetailOpen" class="review-detail-body">
            <!-- v95_p50 (2026-05-05 본부장님): 이관 객체 + 변환·실행 각각 한 줄 -->
            <!-- ── 그룹 1: 이관 객체 (한 줄, 6 컬럼) ─────────── -->
            <div class="review-group">
              <div class="review-group-title">
                <span class="review-group-bullet"></span>
                이관 객체
              </div>
              <table class="review-table review-table-6col">
                <tbody>
                  <tr class="review-table-labels">
                    <td>테이블</td>
                    <td>프로시저</td>
                    <td>함수</td>
                    <td>트리거</td>
                    <td>뷰</td>
                    <td>적용 권고</td>
                  </tr>
                  <tr class="review-table-values">
                    <td>{{ form.tables.length }}<span class="review-unit">개</span></td>
                    <td>{{ form.procedures.length }}<span class="review-unit">개</span></td>
                    <td>{{ form.functions.length }}<span class="review-unit">개</span></td>
                    <td>{{ form.triggers.length }}<span class="review-unit">개</span></td>
                    <td>{{ form.views.length }}<span class="review-unit">개</span></td>
                    <td v-if="!form.advisorSkipped && form.advisorDecisions.length > 0">
                      {{ form.advisorDecisions.filter(d => d.decision === 'applied' || d.decision === 'edited').length }}<span class="review-unit"> / {{ form.advisorDecisions.length }}건</span>
                    </td>
                    <td v-else><span class="review-unit">—</span></td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- ── 그룹 2: 변환 · 실행 설정 (v95_p54: 6칸 한 줄 — 이관 객체와 통일) ──── -->
            <div class="review-group">
              <div class="review-group-title">
                <span class="review-group-bullet review-group-bullet-cfg"></span>
                변환 · 실행 설정
              </div>
              <table class="review-table review-table-6col">
                <tbody>
                  <tr class="review-table-labels">
                    <td>배치 크기</td>
                    <td v-if="form.views.length > 0">뷰 모드</td>
                    <td v-else>—</td>
                    <td v-if="(form.procedures.length+form.functions.length+form.triggers.length)>0">객체 모드</td>
                    <td v-else>—</td>
                    <td>객체 변환</td>
                    <td>이관전 DROP</td>
                    <td>TRUNCATE</td>
                  </tr>
                  <tr class="review-table-values">
                    <td>{{ form.batchSize.toLocaleString() }}</td>
                    <td v-if="form.views.length > 0">
                      {{ {drop_recreate:'DROP 후 재생성', skip_existing:'스킵', replace:'OR REPLACE'}[form.viewMode] }}
                    </td>
                    <td v-else><span class="review-unit">—</span></td>
                    <td v-if="(form.procedures.length+form.functions.length+form.triggers.length)>0">
                      {{ {drop_recreate:'DROP 후 재생성', skip_existing:'스킵'}[form.objMode] }}
                    </td>
                    <td v-else><span class="review-unit">—</span></td>
                    <td>{{ form.convertObjs?'자동 변환':'수동' }}</td>
                    <td :class="{'rv-warn': form.dropTbl}">
                      {{ form.dropTbl?'✓ DROP':'아니오' }}
                    </td>
                    <td>{{ form.dropTbl?'—':form.truncate?'예':'아니오' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
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
      <!-- API 키 배너 (v88: Step 5 = 검토 & 실행, Claude AI 선택 시) — 버튼 위 전체 너비 -->
      <template v-if="cur===5 && needsClaudeAI">
        <div v-if="!claudeApiKeyOk"
             style="display:flex;align-items:center;gap:8px;width:100%;border:1px solid rgba(239,68,68,.25);border-radius:8px;overflow:hidden;background:var(--bg-primary)">
          <div style="padding:8px 12px;background:rgba(239,68,68,.06);display:flex;align-items:center;gap:7px;flex-shrink:0">
            <svg viewBox="0 0 14 14" fill="none" stroke="#dc2626" stroke-width="1.5" style="width:12px;height:12px">
              <circle cx="7" cy="7" r="5.5"/><line x1="7" y1="4" x2="7" y2="7.5"/><circle cx="7" cy="9.5" r=".7" fill="#dc2626"/>
            </svg>
            <span style="font-size:.76rem;color:#dc2626;white-space:nowrap"><b>Claude API 키 미설정</b></span>
          </div>
          <input v-model="inlineApiKey" type="password" placeholder="sk-ant-api03-..." @keyup.enter="saveInlineApiKey"
            style="flex:1;padding:6px 10px;border:none;border-left:0.5px solid var(--border-light);font-size:.8rem;background:transparent;color:var(--text-primary);font-family:var(--font);outline:none"/>
          <button @click="saveInlineApiKey" :disabled="!inlineApiKey||savingApiKey"
            style="padding:6px 14px;margin-right:8px;border-radius:6px;background:#2563eb;color:#fff;border:none;font-size:.77rem;font-weight:600;cursor:pointer;white-space:nowrap;flex-shrink:0">
            {{ savingApiKey ? '저장 중...' : '저장' }}
          </button>
        </div>
        <div v-else
             style="width:100%;padding:6px 12px;background:rgba(22,163,74,.06);border:1px solid rgba(22,163,74,.2);border-radius:6px;font-size:.75rem;color:#15803d;display:flex;align-items:center;gap:5px">
          <svg viewBox="0 0 12 12" fill="none" stroke="#16a34a" stroke-width="2" style="width:10px;height:10px"><polyline points="2,6 4.5,9 10,3"/></svg>
          Claude API 키 설정됨 — AI 변환 사용 가능
        </div>
      </template>
      <!-- 버튼 행 — 항상 한 줄 -->
      <!-- 2026-04-23 UX: [이전] 옆에 [다음 단계] 바로 붙임, 오른쪽은 비움 -->
      <!-- 의도: Step 3 AI DBA 화면에서 '분석 시작' 이 주 CTA가 되도록 상단 강조.
           전 스텝 일관성 유지 (모든 스텝에서 동일 배치). -->
      <!-- v95_p25 (2026-05-04 본부장님 본질 처방): [새로 시작] 버튼 추가
           본부장님 호소: "단계별로 새로시작 버튼 좀 달아줘 새로시작하면
                          단계전체가 clear 되서 새로시작할 수 있는 기능이야"
           - 모든 단계에서 표시 (Step 0 부터 Step 5 까지)
           - 클릭 시 확인 다이얼로그 → form/sched/cur/sessionStorage 모두 초기화 -->
      <div style="display:flex;align-items:center;gap:8px;width:100%">
        <button class="btn" @click="cur>0?cur--:$router.push('/connector')">← {{ cur>0?'이전':'연결 설정' }}</button>
        <button v-if="cur<5" class="wiz-btn-next" @click="nextStep" :disabled="analyzingWarn" :style="analyzingWarn?'opacity:.5;cursor:not-allowed':''">
          다음 단계
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px">
            <polyline points="4,2 10,7 4,12"/>
          </svg>
        </button>
        <div style="flex:1"></div>
        <button class="btn wiz-btn-restart" @click="restartWizard"
                title="모든 입력값을 초기화하고 처음부터 다시 시작합니다">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.6" style="width:12px;height:12px">
            <path d="M2 7a5 5 0 1 0 1.5-3.5"/>
            <polyline points="2,2 2,5 5,5"/>
          </svg>
          새로 시작
        </button>
        <template v-if="cur===5">
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
        </template>
      </div>
    </div>
    <!-- ════════════════════════════════════════════════════════════ -->
    <!-- v95_p66 (2026-05-05 본부장님): 수동 SQL 입력 모달 (Phase 5-1) -->
    <!-- ════════════════════════════════════════════════════════════ -->
    <div v-if="manualSqlModal.open" class="msql-modal-overlay" @click.self="closeManualSqlModal">
      <div class="msql-modal">
        <div class="msql-modal-head">
          <h3>✍️ 수동 SQL 작성 — {{ manualSqlModal.obj_name }}</h3>
          <button class="msql-modal-close" @click="closeManualSqlModal" title="닫기">✕</button>
        </div>
        <div class="msql-modal-body">
          <!-- 좌측: MSSQL 원본 -->
          <div class="msql-modal-pane msql-pane-src">
            <div class="msql-pane-label">
              <span class="msql-pane-icon">📜</span>
              MSSQL 원본 DDL ({{ manualSqlModal.obj_type }}) — <em>참고용</em>
            </div>
            <textarea class="msql-textarea msql-textarea-readonly"
                      readonly
                      :value="manualSqlModal.src_ddl"></textarea>
          </div>
          <!-- 우측: MySQL 사용자 작성 -->
          <div class="msql-modal-pane msql-pane-tgt">
            <div class="msql-pane-label">
              <span class="msql-pane-icon">⚡</span>
              MySQL DDL — <strong>직접 작성</strong>
            </div>
            <textarea class="msql-textarea msql-textarea-editable"
                      v-model="manualSqlModal.mysql_sql"
                      placeholder="CREATE VIEW vMyView AS&#10;SELECT ...&#10;FROM ...;&#10;&#10;-- MSSQL XML/CROSS APPLY 등 → MySQL JSON_EXTRACT/LATERAL JOIN 으로 변환"></textarea>
            <!-- 검증 결과 -->
            <div v-if="manualSqlModal.validation" class="msql-validation"
                 :class="{ ok: manualSqlModal.validation.ok, fail: !manualSqlModal.validation.ok }">
              {{ manualSqlModal.validation.message }}
              <ul v-if="manualSqlModal.validation.details && manualSqlModal.validation.details.length > 0">
                <li v-for="(d, di) in manualSqlModal.validation.details" :key="di">{{ d }}</li>
              </ul>
            </div>
          </div>
        </div>
        <!-- 검출 패턴 가이드 -->
        <div v-if="manualSqlModal.patterns && manualSqlModal.patterns.length > 0"
             class="msql-pattern-guide">
          <div class="msql-pg-label">💡 검출된 위험 패턴 + MySQL 변환 가이드:</div>
          <div v-for="(p, pi) in manualSqlModal.patterns" :key="pi" class="msql-pg-item">
            <span class="msql-pg-level" :class="'msql-pg-' + (p.risk_level || '').toLowerCase()">
              {{ p.risk_level === 'HIGH' ? '🔴' : p.risk_level === 'MEDIUM' ? '🟡' : '🟢' }}
              {{ p.label }}
            </span>
            <span v-if="p.mysql_alternative" class="msql-pg-alt">→ {{ p.mysql_alternative }}</span>
          </div>
        </div>
        <!-- 버튼 -->
        <div class="msql-modal-foot">
          <button class="msql-btn msql-btn-validate"
                  @click="validateManualSql"
                  :disabled="manualSqlModal.validating || !manualSqlModal.mysql_sql.trim()">
            <span v-if="manualSqlModal.validating" class="spinner" style="width:12px;height:12px"></span>
            🔎 SQL 문법 검증
          </button>
          <button class="msql-btn msql-btn-cancel" @click="closeManualSqlModal">
            취소
          </button>
          <button class="msql-btn msql-btn-save"
                  @click="saveManualSql"
                  :disabled="!manualSqlModal.mysql_sql.trim()">
            💾 저장 + KB 등록
          </button>
        </div>
      </div>
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useJobStore } from '@/store/jobStore.js'
import { useAppStore } from '@/store/appStore.js'
import { useConnectorStore } from '@/store/connectorStore.js'
import { DB_META, SOURCE_DBS, TARGET_DBS } from '@/constants/dbMeta.js'
import AnalysisTabs from '@/components/analysis/AnalysisTabs.vue'  // v89: AI DBA + PII Privacy 통합 탭
import ScenarioSelector from '@/components/wizard/ScenarioSelector.vue'  // v90.1: 이관 시나리오 선택
import axios from 'axios'

const router    = useRouter()
const route     = useRoute()  // v90.19: 위저드 상태 복원/리셋 판별용

const tableModes = [
  { v: 'schema_only', label: '스키마만',       desc: '테이블 구조만 생성, 데이터 이관 안 함',           icon: '📐', color: 'mode-purple' },
  { v: 'schema_data', label: '스키마 + 데이터', desc: '구조 생성 후 데이터 전체 이관 (권장)',             icon: '🚀', color: 'mode-blue'   },
  { v: 'data_only',   label: '데이터만',        desc: '기존 테이블에 데이터만 추가, 구조 변경 없음',     icon: '📦', color: 'mode-green'  },
]

const viewModes = [
  { v: 'drop_recreate', label: 'DROP 후 재생성', desc: '기존 뷰를 삭제하고 새로 생성 (항상 최신 반영)', icon: '🔄', color: 'mode-blue'   },
  { v: 'skip_existing', label: '있으면 스킵',    desc: '타겟에 이미 있는 뷰는 건너뜀',                  icon: '⏭', color: 'mode-gray'  },
  { v: 'replace',       label: 'OR REPLACE',     desc: '뷰가 있으면 교체, 없으면 새로 생성',            icon: '♻️', color: 'mode-green'  },
]

const objModes = [
  { v: 'drop_recreate', label: 'DROP 후 재생성', desc: '기존 오브젝트를 삭제하고 새로 생성', icon: '🔄', color: 'mode-blue'  },
  { v: 'skip_existing', label: '있으면 스킵',    desc: '타겟에 이미 있는 오브젝트는 건너뜀', icon: '⏭', color: 'mode-gray' },
]

const jobs      = useJobStore()
const app       = useAppStore()
const connector = useConnectorStore()

const cur         = ref(0)
const v3          = ref(false)
const submitting    = ref(false)
const inlineApiKey  = ref('')
const needsClaudeAI = computed(() => form.value.ddlEngine === 'claude' || form.value.objEngine === 'claude')
const savingApiKey  = ref(false)

async function saveInlineApiKey() {
  if (!inlineApiKey.value) return
  savingApiKey.value = true
  try {
    await axios.put('/api/v1/settings/', { anthropic_api_key: inlineApiKey.value })
    claudeApiKeyOk.value = true
    inlineApiKey.value = ''
    app.notify('Claude API 키가 저장됐습니다', 'success')
  } catch(e) {
    app.notify('API 키 저장 실패: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    savingApiKey.value = false
  }
}
const claudeApiKeyOk = ref(false)
// API 키 확인 함수
async function checkApiKey() {
  try {
    const { data } = await axios.get('/api/v1/settings/')
    claudeApiKeyOk.value = !!(data?.anthropic_api_key_set)
  } catch { claudeApiKeyOk.value = false }
}

// 마운트 + 5단계 진입 시 재확인
onMounted(checkApiKey)

import { watch } from 'vue'
watch(() => cur.value, v => { if (v === 4) checkApiKey() })

// ── Step 1 상태 ──
const objTab      = ref('tables')
const objSearch   = ref('')
const loadingObjs = ref(false)
const objError    = ref('')
const allTables   = ref([])
const allObjects  = ref({ procedures:[], functions:[], triggers:[], views:[] })

// ── Step 2 경고 ──
const warnRules    = ref([])
const normRules    = ref([])   // 정규화 규칙 목록
const normOpen     = ref(true) // 기본 펼침
const activeNormCount = computed(() => form.value.normActions.length)
const analyzingWarn= ref(false)
const openRules    = ref({})

// v95_p23a (2026-05-03 본부장님 본질 처방): 사전 분석 (Pre-Flight)
//   본부장님 호소: 위저드 다음 단계로 넘어갈 때 위험 분석 → 회피
const preflightAnalyzing = ref(false)
const preflightRisks     = ref([])         // 위험 목록
const preflightSummary   = ref({total:0, critical:0, warn:0, info:0, auto_fix_count:0})
const preflightOpen      = ref(false)      // 결과 패널 표시 여부

// v95_p37 본질 1 (2026-05-05 본부장님): 사전 분석 마스터-디테일 + sort
const pfSelectedIdx   = ref(0)              // 선택된 위험 인덱스 (좌측 클릭)
const pfSortMode      = ref('severity')     // 'severity' | 'category' | 'affected'
const showAllAffected = ref(false)          // 영향 객체 더보기 토글

// 정렬된 위험 목록 (좌측 리스트용)
const sortedPreflightRisks = computed(() => {
  const list = [...(preflightRisks.value || [])]
  if (pfSortMode.value === 'severity') {
    const order = { critical: 0, warn: 1, info: 2 }
    list.sort((a, b) => (order[a.level] ?? 9) - (order[b.level] ?? 9))
  } else if (pfSortMode.value === 'category') {
    list.sort((a, b) => String(a.category || '').localeCompare(String(b.category || '')))
  } else if (pfSortMode.value === 'affected') {
    list.sort((a, b) => (b.affected_count || 0) - (a.affected_count || 0))
  }
  return list
})

// 우측 상세에 표시될 선택된 위험 (sortedPreflightRisks 기준)
const selectedRisk = computed(() => {
  const list = sortedPreflightRisks.value
  if (!list.length) return null
  const idx = Math.min(Math.max(0, pfSelectedIdx.value), list.length - 1)
  return list[idx]
})

// v95_p37 본질 2 (2026-05-05 본부장님): 타입 정규화 적용/미적용 그룹 분리
const normUnappliedOpen = ref(false)  // 미적용 그룹 기본 접힘
const appliedNormRules = computed(() =>
  (normRules.value || []).filter(r => form.value.normActions.includes(r.fix_action))
)
const unappliedNormRules = computed(() =>
  (normRules.value || []).filter(r => !form.value.normActions.includes(r.fix_action))
)

// v95_p37 본질 4 (2026-05-05 본부장님): Step 6 검토 화면 두 블록 분리
const reviewObjOpen = ref(true)   // 이관 객체 블록 - 기본 펼침
const reviewCfgOpen = ref(true)   // 변환·실행 설정 블록 - 기본 펼침
// v95_p48 (2026-05-05 본부장님): 두 블록 합친 상세 정보 — 기본 펼침
const reviewDetailOpen = ref(true)

// 사전 분석 패널 펼쳐질 때 인덱스 초기화 (sort 변경 시에도)
watch([pfSortMode, preflightOpen], () => {
  pfSelectedIdx.value = 0
  showAllAffected.value = false
})

// ── Step 4 스케줄 ──
const schedEnabled = ref(false)
const schedType    = ref('once')
const sched = ref({
  date:'', time:'09:00', interval:'daily', dows:[], day:1,
  endType:'never', endDate:'', count:1, cron:''
})

const steps   = ['DB 선택','객체 선택','변환 규칙','AI DBA 권고','실행 옵션','검토 & 실행']
const engines = [
  { v:'auto',   l:'자동',       ico:'⚡' },
  { v:'rules',  l:'규칙 기반',  ico:'⚙' },
  { v:'claude', l:'Claude AI',  ico:'🤖' },
]
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
  dropTbl:false, truncate:true, createTbl:true, withIdx:true, convertObjs:true,
  skipTriggers:false,  // v90.32: 트리거 hang 방지용 옵션
  // v90.48: schema 정책 (테이블 + 객체 이관 시 동일 적용)
  //   underscore: customer.profile → customer_profile (권장, 충돌 방지)
  //   drop:       customer.profile → profile (기존 동작, 충돌 위험)
  //   database:   별도 DB 분리 (고급)
  schemaStrategy: 'underscore',
  tableMode:'schema_data',   // schema_only | schema_data | data_only
  viewMode:'drop_recreate',  // drop_recreate | skip_existing | replace
  objMode:'drop_recreate',   // drop_recreate | skip_existing
  ddlEngine:'claude',        // DDL 변환 엔진: auto | rules | claude
  objEngine:'claude',        // 오브젝트 변환 엔진: auto | rules | claude
  // v92p11 (2026-04-30): 본부장님 호소 — "자동 재이관은 명시적 토글로만"
  //   기본값 false — 실패 시 멈추고 사용자가 수동 🤖 AI 재이관 클릭
  //   true 로 켤 경우만 백엔드가 자동으로 AI 재시도 (최대 2회)
  aiAutoRetry: false,
  aiAutoRetryCount: 2,
  // v9 패치 #20: 대량 이관 로더 선택
  bulkMode: 'auto',          // auto | executemany | bcp | pymssql
  bulkThresholdRows: 100000,
  // v9 패치 #23: 테이블 병렬 처리 + MSSQL 튜닝
  parallelTables: 3,
  mssqlTuning: false,
  mssqlDisableIndexes: false,
  normActions: [],            // 선택된 정규화 fix_action 목록

  // v88 P1: AI DBA Consultant (Stage 4) ─────────────────────
  advisorMode: 'smart',       // 'smart' | 'hybrid' | 'deep'
  advisorSkipped: false,      // "원본 그대로" 선택 시 true → Stage 4 건너뜀
  advisorDecisions: [],       // 각 권고에 대한 사용자 결정 (P2+ 채워짐)
  // v90.20: AdvisorPanel 의 전체 분석 상태 (sessionStorage 보존용)
  //   분석 결과 + 카테고리 탭 + 선택된 권고 + 결정 맵 모두 포함
  advisorAnalysis: null,      // { analyzed, mode, recommendations, summary, decisionMap, ... }
  
  // v90.20: AnalysisTabs 의 활성 탭 (advisor / privacy / compliance / preflight)
  activeAnalysisTab: 'advisor',

  // v89: PII Privacy (Step 3 Tab 2) ─────────────────────────
  privacyPreset: '',          // 'dev_environment' | 'qa_environment' 등
  privacyDecisions: [],       // 컬럼별 마스킹 결정
  privacyScan: null,          // 스캔 결과 종합
  privacySkipped: false,      // PII 스킵 여부

  // v90.1: 이관 시나리오 (Step 0 에서 선택, AI DBA + PII 자동 적용)
  migrationScenario: '',      // 'prod_to_dev' / 'prod_to_qa' / 'prod_to_dr' 등
  
  // ════════════════════════════════════════════════════════════
  // v95_p65 (2026-05-05 본부장님): 객체 변환 결정 (Phase 4-2)
  // ════════════════════════════════════════════════════════════
  // 본부장님 결정: "5 Phase 모두 — 엔터프라이즈 솔루션"
  //
  // 본질: vProductModelInstructions / vJobCandidateEducation 같은 위험 객체에
  //       대해 사용자가 명시적 결정 가능 (자동/수동/제외)
  //
  // 구조: { obj_name: { decision: 'auto'|'manual'|'exclude',
  //                     manual_sql: '...' (수동 시),
  //                     decided_at: ISO date } }
  //
  // Phase 5 에서 manual_sql 작성 → KB 등록
  // Phase 6 (실행) 에서 obj_executor 가 결정 우선 적용:
  //   exclude → 이관 스킵
  //   manual  → manual_sql 직접 사용 (AI 호출 0)
  //   auto    → 기존 AI 변환 흐름
  //
  // 부작용 0:
  //   - 빈 객체 ({}) 면 옛 흐름 그대로 (auto)
  //   - v95_p60 위저드 state 보존에 자동 통합 (form 일부)
  // ════════════════════════════════════════════════════════════
  objectDecisions: {},
})

// v90.12 + v90.20: PII 탭 방문 + 활성 탭 저장 (sessionStorage 보존)
const privacyTabVisited = ref(false)
function onTabVisited(tabId) {
  if (tabId === 'privacy') {
    privacyTabVisited.value = true
  }
  // v90.20: 마지막으로 본 탭 기억
  form.value.activeAnalysisTab = tabId
}

// v90.17: AnalysisTabs 한번 진입하면 이후 unmount 안 함 (분석 상태 유지)
const analysisTabsLoaded = ref(false)

// ════════════════════════════════════════════════════════════════
// v90.19: 위저드 상태 sessionStorage 저장/복원
// ════════════════════════════════════════════════════════════════
//   - 다른 페이지(타입매핑 등) 갔다 와도 cur + form + 모든 입력 유지
//   - 브라우저 탭 닫으면 자동 정리 (sessionStorage)
//   - 새 위저드 시작 ("+ New Job") 또는 submit 성공 시 명시적 클리어
const WIZARD_STATE_KEY = 'databridge.wizard.state.v1'

function saveWizardState() {
  try {
    const state = {
      cur: cur.value,
      form: form.value,
      privacyTabVisited: privacyTabVisited.value,
      analysisTabsLoaded: analysisTabsLoaded.value,
      // v95_p59: allObjects + allTables 도 저장
      allTables: allTables.value,
      allObjects: allObjects.value,
      // ════════════════════════════════════════════════════════════
      // v95_p60 (2026-05-05 본부장님): 위저드 전체 사용자 작업 데이터 저장
      // ════════════════════════════════════════════════════════════
      // 본부장님 호소: "변환규칙도 선택후 다른 화면 갔다 오면 없어져 버려"
      //               "위저드 전체적으로 다른 화면 갔다 오면 변경된 내용까지 유지"
      //
      // 본질: form/allObjects 외에 사용자 작업 데이터가 여러 ref 에 분산:
      //   - warnRules/normRules: AI 분석 결과 (API 호출 비용 큼!)
      //   - preflightRisks: AI DBA 분석 결과 (역시 비용)
      //   - sched: 스케줄 설정
      //   - objTab/objSearch: UI 상태 (덜 중요하지만 UX 향상)
      //
      // 처방: 사용자 작업/AI 분석 결과 모두 저장 → 복원 시 즉시 복귀
      // 효과:
      //   - 다른 화면 → 위저드 복귀 시 모든 작업 보존 ✅
      //   - AI 재분석 비용 0 (warnRules/preflightRisks 보존)
      //
      // 부작용 0:
      //   - sessionStorage 5MB 한계 vs 전체 ~200KB 추산
      //   - 1시간 TTL 그대로
      //   - 새로 시작 (?fresh=1) 흐름 그대로
      // ════════════════════════════════════════════════════════════
      // 변환 규칙 (사용자 작업 + AI 분석 결과)
      warnRules: warnRules.value,
      normRules: normRules.value,
      normOpen: normOpen.value,
      openRules: openRules.value,
      normUnappliedOpen: normUnappliedOpen.value,
      // AI DBA 분석 결과
      preflightRisks: preflightRisks.value,
      preflightSummary: preflightSummary.value,
      preflightOpen: preflightOpen.value,
      pfSelectedIdx: pfSelectedIdx.value,
      pfSortMode: pfSortMode.value,
      showAllAffected: showAllAffected.value,
      // 스케줄
      schedEnabled: schedEnabled.value,
      schedType: schedType.value,
      sched: sched.value,
      // 검토 화면 펼침 상태
      reviewObjOpen: reviewObjOpen.value,
      reviewCfgOpen: reviewCfgOpen.value,
      reviewDetailOpen: reviewDetailOpen.value,
      // UI 상태 (UX 향상)
      objTab: objTab.value,
      objSearch: objSearch.value,
      tableSort: tableSort.value,
      procSort: procSort.value,
      funcSort: funcSort.value,
      trigSort: trigSort.value,
      viewSort: viewSort.value,
      // 상태 저장 시각 (오래된 상태 자동 폐기용)
      savedAt: Date.now(),
    }
    sessionStorage.setItem(WIZARD_STATE_KEY, JSON.stringify(state))
  } catch (e) {
    console.warn('[Wizard] 상태 저장 실패:', e)
  }
}

function restoreWizardState() {
  try {
    const raw = sessionStorage.getItem(WIZARD_STATE_KEY)
    if (!raw) return false
    const state = JSON.parse(raw)
    // 1시간 이상 지난 상태는 폐기 (오래된 작업 잔존 방지)
    if (Date.now() - (state.savedAt || 0) > 3600000) {
      sessionStorage.removeItem(WIZARD_STATE_KEY)
      return false
    }
    if (typeof state.cur === 'number') cur.value = state.cur
    if (state.form) {
      // form 의 모든 키를 복원 (누락된 신규 키 대비 spread)
      form.value = { ...form.value, ...state.form }
    }
    // v95_p59: allTables / allObjects 복원
    if (Array.isArray(state.allTables)) {
      allTables.value = state.allTables
    }
    if (state.allObjects && typeof state.allObjects === 'object') {
      allObjects.value = {
        procedures: Array.isArray(state.allObjects.procedures) ? state.allObjects.procedures : [],
        functions:  Array.isArray(state.allObjects.functions)  ? state.allObjects.functions  : [],
        triggers:   Array.isArray(state.allObjects.triggers)   ? state.allObjects.triggers   : [],
        views:      Array.isArray(state.allObjects.views)      ? state.allObjects.views      : [],
      }
    }
    if (state.privacyTabVisited) privacyTabVisited.value = true
    if (state.analysisTabsLoaded) analysisTabsLoaded.value = true
    // ════════════════════════════════════════════════════════════
    // v95_p60: 전체 사용자 작업 데이터 복원
    // ════════════════════════════════════════════════════════════
    // 변환 규칙 복원 (AI 재분석 비용 절감)
    if (Array.isArray(state.warnRules)) warnRules.value = state.warnRules
    if (Array.isArray(state.normRules)) normRules.value = state.normRules
    if (typeof state.normOpen === 'boolean') normOpen.value = state.normOpen
    if (state.openRules && typeof state.openRules === 'object') openRules.value = state.openRules
    if (typeof state.normUnappliedOpen === 'boolean') normUnappliedOpen.value = state.normUnappliedOpen
    // AI DBA 분석 결과 복원
    if (Array.isArray(state.preflightRisks)) preflightRisks.value = state.preflightRisks
    if (state.preflightSummary && typeof state.preflightSummary === 'object') preflightSummary.value = state.preflightSummary
    if (typeof state.preflightOpen === 'boolean') preflightOpen.value = state.preflightOpen
    if (typeof state.pfSelectedIdx === 'number') pfSelectedIdx.value = state.pfSelectedIdx
    if (typeof state.pfSortMode === 'string') pfSortMode.value = state.pfSortMode
    if (typeof state.showAllAffected === 'boolean') showAllAffected.value = state.showAllAffected
    // 스케줄 복원
    if (typeof state.schedEnabled === 'boolean') schedEnabled.value = state.schedEnabled
    if (typeof state.schedType === 'string') schedType.value = state.schedType
    if (state.sched && typeof state.sched === 'object') sched.value = { ...sched.value, ...state.sched }
    // 검토 화면 펼침 상태 복원
    if (typeof state.reviewObjOpen === 'boolean') reviewObjOpen.value = state.reviewObjOpen
    if (typeof state.reviewCfgOpen === 'boolean') reviewCfgOpen.value = state.reviewCfgOpen
    if (typeof state.reviewDetailOpen === 'boolean') reviewDetailOpen.value = state.reviewDetailOpen
    // UI 상태 복원
    if (typeof state.objTab === 'string') objTab.value = state.objTab
    if (typeof state.objSearch === 'string') objSearch.value = state.objSearch
    if (state.tableSort && typeof state.tableSort === 'object') tableSort.value = state.tableSort
    if (state.procSort && typeof state.procSort === 'object') procSort.value = state.procSort
    if (state.funcSort && typeof state.funcSort === 'object') funcSort.value = state.funcSort
    if (state.trigSort && typeof state.trigSort === 'object') trigSort.value = state.trigSort
    if (state.viewSort && typeof state.viewSort === 'object') viewSort.value = state.viewSort
    // ════════════════════════════════════════════════════════════
    console.log(`[Wizard v95_p60] 상태 복원 - cur=${cur.value}, allTables=${allTables.value.length}, warnRules=${warnRules.value.length}, normRules=${normRules.value.length}, preflightRisks=${preflightRisks.value.length}`)
    return true
  } catch (e) {
    console.warn('[Wizard] 상태 복원 실패:', e)
    return false
  }
}

function clearWizardState() {
  try {
    sessionStorage.removeItem(WIZARD_STATE_KEY)
  } catch (e) { /* 무시 */ }
}

// ────────────────────────────────────────────────────────────────────
// v95_p25 (2026-05-04 본부장님 본질 처방): 단계별 [새로 시작] 버튼
// ────────────────────────────────────────────────────────────────────
// 본부장님 호소:
//   "단계별로 새로시작 버튼 좀 달아줘 새로시작하면
//    단계전체가 clear 되서 새로시작할 수 있는 기능이야"
//
// 처방 흐름:
//   1) 사용자 확인 다이얼로그 (실수 클릭 방지)
//   2) sessionStorage 의 위저드 상태 제거
//   3) 모든 ref 상태를 초기값으로 리셋
//   4) cur = 0 (Step 0 으로 이동)
//
// 부작용 0:
//   - 사용자 확인 안 하면 아무 변경 없음
//   - connector store 는 건드리지 않음 (DB 연결 정보는 보존 — 이게 "위저드만"
//     리셋의 의미)
function restartWizard() {
  // eslint-disable-next-line no-alert
  const ok = confirm(
    '위저드를 처음부터 새로 시작하시겠습니까?\n\n'
    + '입력하신 모든 내용이 초기화됩니다:\n'
    + '  · 객체 선택 (테이블/프로시저/함수/트리거/뷰)\n'
    + '  · 변환 규칙 / 자동 수정 토글\n'
    + '  · AI DBA 권고 결정\n'
    + '  · PII 마스킹 결정\n'
    + '  · 실행 옵션 / 스케줄\n\n'
    + '※ DB 연결 정보는 그대로 유지됩니다.'
  )
  if (!ok) return

  // 1) sessionStorage 정리
  clearWizardState()

  // 2) form 전체 초기화 (Vue ref 재할당으로 watcher 트리거)
  form.value = {
    srcDb: connector.source.dbType || 'mysql',
    tgtDb: connector.target.dbType || 'mssql',
    tables: [], procedures: [], functions: [], triggers: [], views: [],
    name: (connector.source.database && connector.target.database)
      ? `${connector.source.database} → ${connector.target.database} 이관`
      : '',
    batchSize: 5000, workers: 4, onError: 'skip',
    dropTbl: false, truncate: true, createTbl: true, withIdx: true, convertObjs: true,
    skipTriggers: false,
    schemaStrategy: 'underscore',
    tableMode: 'schema_data',
    viewMode: 'drop_recreate',
    objMode: 'drop_recreate',
    ddlEngine: 'claude',
    objEngine: 'claude',
    aiAutoRetry: false,
    aiAutoRetryCount: 2,
    bulkMode: 'auto',
    bulkThresholdRows: 100000,
    parallelTables: 3,
    mssqlTuning: false,
    mssqlDisableIndexes: false,
    normActions: [],
    advisorMode: 'smart',
    advisorSkipped: false,
    advisorDecisions: [],
    advisorAnalysis: null,
    activeAnalysisTab: 'advisor',
    privacyPreset: '',
    privacyDecisions: [],
    privacyScan: null,
    privacySkipped: false,
    migrationScenario: '',
  }

  // 3) 단계별 ref 리셋
  cur.value = 0
  warnRules.value = []
  normRules.value = []
  openRules.value = {}
  preflightRisks.value = []
  preflightSummary.value = { total: 0, critical: 0, warn: 0, info: 0, auto_fix_count: 0 }
  preflightOpen.value = false
  allTables.value = []
  allObjects.value = { procedures: [], functions: [], triggers: [], views: [] }
  privacyTabVisited.value = false
  analysisTabsLoaded.value = false
  schedEnabled.value = false
  schedType.value = 'once'
  sched.value = {
    date: '', time: '09:00', interval: 'daily', dows: [], day: 1,
    endType: 'never', endDate: '', count: 1, cron: '',
  }

  console.log('[v95_p25] 위저드 새로 시작 — 모든 상태 초기화 완료')
  // 4) 사용자에게 시각 피드백 (notify 가능하면 사용)
  try {
    if (typeof app !== 'undefined' && app.notify) {
      app.notify('위저드를 처음부터 새로 시작합니다', 'info')
    }
  } catch { /* notify 미지원 환경 무시 */ }
}

// cur 변경 시 자동 저장
watch(() => cur.value, () => saveWizardState())

// form 의 모든 변경 시 자동 저장 (deep)
watch(form, () => saveWizardState(), { deep: true })

// privacyTabVisited 도 자동 저장
watch(privacyTabVisited, () => saveWizardState())
watch(analysisTabsLoaded, () => saveWizardState())

// v95_p59 (2026-05-05 본부장님): allTables / allObjects 도 자동 저장
//   본부장님 호소: "다른 화면 갔다 왔더니 카드 비어있음"
//   본질: 객체 목록 변경 시 sessionStorage 갱신 안 됨 → 복원 시 누락
watch(allTables, () => saveWizardState(), { deep: true })
watch(allObjects, () => saveWizardState(), { deep: true })

// ════════════════════════════════════════════════════════════
// v95_p60 (2026-05-05 본부장님): 위저드 전체 사용자 작업 watch
// ════════════════════════════════════════════════════════════
// 본부장님 호소: "위저드 전체적으로 다른 화면 갔다 오면 변경된 내용까지 유지"
// 처방: 모든 사용자 작업/AI 분석 결과 변경 시 자동 저장
// 변환 규칙
watch(warnRules, () => saveWizardState(), { deep: true })
watch(normRules, () => saveWizardState(), { deep: true })
watch(normOpen, () => saveWizardState())
watch(openRules, () => saveWizardState(), { deep: true })
watch(normUnappliedOpen, () => saveWizardState())
// AI DBA 분석
watch(preflightRisks, () => saveWizardState(), { deep: true })
watch(preflightSummary, () => saveWizardState(), { deep: true })
watch(preflightOpen, () => saveWizardState())
watch(pfSelectedIdx, () => saveWizardState())
watch(pfSortMode, () => saveWizardState())
watch(showAllAffected, () => saveWizardState())
// 스케줄
watch(schedEnabled, () => saveWizardState())
watch(schedType, () => saveWizardState())
watch(sched, () => saveWizardState(), { deep: true })
// 검토 화면 펼침 상태
watch(reviewObjOpen, () => saveWizardState())
watch(reviewCfgOpen, () => saveWizardState())
watch(reviewDetailOpen, () => saveWizardState())
// UI 상태 (UX 향상)
watch(objTab, () => saveWizardState())
watch(objSearch, () => saveWizardState())
// v95_p61: tableSort/procSort/funcSort/trigSort/viewSort watch 는
//          정의 (line 2048+) 후로 이동 — TDZ 회피

const dbUsageHistory = ref({ source: [], target: [] })  // v90.2: DB 사용 이력

// DB 별 사용 횟수 매핑
const srcUsageMap = computed(() => {
  const m = {}
  for (const h of dbUsageHistory.value.source || []) {
    m[h.db_type] = h.use_count || 0
  }
  return m
})
const tgtUsageMap = computed(() => {
  const m = {}
  for (const h of dbUsageHistory.value.target || []) {
    m[h.db_type] = h.use_count || 0
  }
  return m
})

// 소스 DB - 사용 횟수 추가 + 정렬
const srcDbsWithUsage = computed(() => {
  return SOURCE_DBS.map(d => ({
    ...d,
    ...DB_META[d.value],
    useCount: srcUsageMap.value[d.value] || 0,
  })).sort((a, b) => {
    // 1순위: 현재 연결된 DB 가 맨 앞
    if (connector.source.dbType === a.value) return -1
    if (connector.source.dbType === b.value) return 1
    // 2순위: 사용 횟수
    return (b.useCount || 0) - (a.useCount || 0)
  })
})
const tgtDbsWithUsage = computed(() => {
  return TARGET_DBS.map(d => ({
    ...d,
    ...DB_META[d.value],
    useCount: tgtUsageMap.value[d.value] || 0,
  })).sort((a, b) => {
    if (connector.target.dbType === a.value) return -1
    if (connector.target.dbType === b.value) return 1
    return (b.useCount || 0) - (a.useCount || 0)
  })
})

// 자주 쓰는 3개 + 나머지
const frequentSrcDbs = computed(() => srcDbsWithUsage.value.slice(0, 3))
const rareSrcDbs = computed(() => srcDbsWithUsage.value.slice(3))
const frequentTgtDbs = computed(() => tgtDbsWithUsage.value.slice(0, 3))
const rareTgtDbs = computed(() => tgtDbsWithUsage.value.slice(3))

// 백엔드에서 DB 사용 이력 로드
async function loadDbHistory() {
  try {
    const r = await fetch('/api/v1/user/preferences/dbs', { credentials: 'include' })
    if (r.ok) {
      const data = await r.json()
      dbUsageHistory.value = {
        source: data.source_history || [],
        target: data.target_history || [],
      }
    }
  } catch (e) {
    console.warn('[DB History] 로드 실패:', e.message)
  }
}

// DB 사용 기록 (다음 단계 클릭 시 호출)
async function recordDbUse(dbType, side) {
  if (!dbType) return
  try {
    await fetch('/api/v1/user/preferences/dbs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ db_type: dbType, side }),
    })
  } catch (e) {
    console.warn('[DB Record] 기록 실패:', e.message)
  }
}

const srcDbs = SOURCE_DBS.map(d=>({...d,...DB_META[d.value]}))
const tgtDbs = TARGET_DBS.map(d=>({...d,...DB_META[d.value]}))
const m      = t => DB_META[t]||{label:'??',bg:'#eee',color:'#333'}
const fmtRows= n => n>=1e6?(n/1e6).toFixed(1)+'M':n>=1e3?Math.round(n/1e3)+'K':String(n||0)
// v90.75: 본부장님 호소 — "1,000건 이런 단위 형태로 보기 쉽게"
//   → M/K 줄임 표기 폐지, 천단위 콤마로 변경
const fmtRowsComma = n => {
  const v = Number(n) || 0
  return v.toLocaleString('en-US')   // 1234567 → "1,234,567"
}
// v90.74: 행 수에 따른 색상 클래스 (M / K / 일반)
const _rowCountClass = n => {
  const v = Number(n) || 0
  if (v >= 1e6) return 'is-million'
  if (v >= 1e3) return 'is-thousand'
  return ''
}

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

// ════════════════════════════════════════════════════════════════════
// v90.75 (2026-04-28): 박스별 독립 정렬 (이전 단일 sortKey/sortDir 폐기)
//   본부장님 호소: "각각 객체별로 정렬 기능을 구현하고 싶어"
//   변경: 5개 박스 마다 sort state 분리
//         상단 정렬 툴바 제거 → 각 컬럼 헤더 클릭으로 정렬
// ════════════════════════════════════════════════════════════════════
const tableSort = ref({ key: 'name', dir: 'asc' })   // name | size | rows
const procSort  = ref({ key: 'name', dir: 'asc' })   // name | date
const funcSort  = ref({ key: 'name', dir: 'asc' })   // name | type | date
const trigSort  = ref({ key: 'name', dir: 'asc' })   // name | event | table
const viewSort  = ref({ key: 'name', dir: 'asc' })   // name

// v95_p61 (2026-05-05 본부장님): sort watch 를 정의 직후로 이동 (TDZ 회피)
//   본부장님 환경 에러: "Cannot access 'tableSort' before initialization"
//   본질: v95_p60 watch 가 line 1920 에 있는데 정의는 line 2048
//         → JavaScript Temporal Dead Zone 위반
//   처방: watch 를 정의 직후로 이동 (다른 19개 watch 는 모두 정상)
watch(tableSort, () => saveWizardState(), { deep: true })
watch(procSort,  () => saveWizardState(), { deep: true })
watch(funcSort,  () => saveWizardState(), { deep: true })
watch(trigSort,  () => saveWizardState(), { deep: true })
watch(viewSort,  () => saveWizardState(), { deep: true })

// 박스별 토글 함수 (한 컬럼 다시 클릭 → asc↔desc, 다른 컬럼 클릭 → asc 부터)
function _toggleSortFor(sortRef, key) {
  if (sortRef.value.key === key) {
    sortRef.value.dir = sortRef.value.dir === 'asc' ? 'desc' : 'asc'
  } else {
    sortRef.value.key = key
    sortRef.value.dir = 'asc'
  }
}
function toggleTableSort(key) { _toggleSortFor(tableSort, key) }
function toggleProcSort(key)  { _toggleSortFor(procSort,  key) }
function toggleFuncSort(key)  { _toggleSortFor(funcSort,  key) }
function toggleTrigSort(key)  { _toggleSortFor(trigSort,  key) }
function toggleViewSort(key)  { _toggleSortFor(viewSort,  key) }

// 박스별 아이콘 (현재 정렬 중인 컬럼만 ▲/▼, 나머지는 ↕)
function _iconFor(sortRef, key) {
  if (sortRef.value.key !== key) return '↕'
  return sortRef.value.dir === 'asc' ? '▲' : '▼'
}
function tableSortIcon(key) { return _iconFor(tableSort, key) }
function procSortIcon(key)  { return _iconFor(procSort,  key) }
function funcSortIcon(key)  { return _iconFor(funcSort,  key) }
function trigSortIcon(key)  { return _iconFor(trigSort,  key) }
function viewSortIcon(key)  { return _iconFor(viewSort,  key) }

function _applySortBy(arr, getter, dir) {
  const d = dir === 'desc' ? -1 : 1
  return [...arr].sort((x, y) => _cmp(getter(x), getter(y)) * d)
}

// v90.48: 정책별 타겟 이름 미리보기 (백엔드 map_table_name 과 동일 로직)
function previewTargetName(schema, bare) {
  const sch = (schema || '').trim()
  const b = (bare || '').trim()
  if (!sch || sch.toLowerCase() === 'dbo') return b
  if (!b) return b
  if (b.toLowerCase().startsWith(sch.toLowerCase() + '_')) return b
  if (form.value.schemaStrategy === 'underscore') return `${sch}_${b}`
  if (form.value.schemaStrategy === 'drop')       return b
  if (form.value.schemaStrategy === 'database')   return b
  return b
}

// v90.48: 미리보기 샘플 (정책 카드 하단에 3개 정도 노출)
const policyPreviewSamples = computed(() => {
  const tbls = allTables.value || []
  if (!tbls.length) return []
  // schema 가 다른 다양한 샘플 우선
  const seen = new Set()
  const picks = []
  for (const t of tbls) {
    const sch = t.schema_name || ''
    if (!sch || sch.toLowerCase() === 'dbo') continue
    if (seen.has(sch)) continue
    seen.add(sch)
    picks.push({
      src: `${sch}.${t.table_name}`,
      tgt: previewTargetName(sch, t.table_name),
    })
    if (picks.length >= 3) break
  }
  return picks
})

const policyHelpText = computed(() => {
  if (form.value.schemaStrategy === 'underscore')
    return '소스의 schema 정보를 언더스코어로 결합하여 타겟 테이블 이름 생성. 도메인별 분리가 명확하고 동명 테이블 충돌이 없어 금융권 등 enterprise 환경에 권장됩니다.'
  if (form.value.schemaStrategy === 'drop')
    return 'schema 접두어를 제거하여 짧은 이름 사용. 동명 테이블이 다른 schema 에 있으면 충돌 위험. 단일 schema 환경에만 사용.'
  return '각 schema 를 별도의 MySQL database 로 분리. 멀티테넌시/대규모 시스템에 적합.'
})

function _cmp(a, b) {
  if (a == null && b == null) return 0
  if (a == null) return -1
  if (b == null) return 1
  if (typeof a === 'number' && typeof b === 'number') return a - b
  return String(a).localeCompare(String(b), 'ko')
}
function _applySort(arr, getter) {
  // v90.75: 하위 호환용으로만 남김 (사용처 없음)
  const d = sortDir?.value === 'desc' ? -1 : 1
  return [...arr].sort((x, y) => _cmp(getter(x), getter(y)) * d)
}

// 필터링 + 정렬 (v90.75: 박스별 독립 정렬)
const filteredTables = computed(() => {
  const q = objSearch.value.toLowerCase()
  const filtered = allTables.value.filter(t => t.table_name.toLowerCase().includes(q))
  const getter = {
    name: t => t.table_name,
    rows: t => t.row_count || 0,
    size: t => t.size_mb || 0,
  }[tableSort.value.key] || (t => t.table_name)
  return _applySortBy(filtered, getter, tableSort.value.dir)
})
// v90.75: type 별 sortRef 매핑
const _sortRefFor = type => ({
  procedures: procSort, functions: funcSort, triggers: trigSort, views: viewSort,
}[type] || procSort)
const filteredObjs = type => {
  const q = objSearch.value.toLowerCase()
  const filtered = (allObjects.value[type] || []).filter(o => o.name.toLowerCase().includes(q))
  const sortRef = _sortRefFor(type)
  // 객체 타입별 정렬 가능 컬럼
  const getterMap = {
    procedures: { name: o => o.name, date: o => o.created || '' },
    functions:  { name: o => o.name, type: o => o.return_type || '', date: o => o.created || '' },
    triggers:   { name: o => o.name, event: o => o.event || '', table: o => o.table || '' },
    views:      { name: o => o.name },
  }[type] || { name: o => o.name }
  const getter = getterMap[sortRef.value.key] || (o => o.name)
  return _applySortBy(filtered, getter, sortRef.value.dir)
}
const getSelCount    = tab => ({tables:form.value.tables.length,procedures:form.value.procedures.length,functions:form.value.functions.length,triggers:form.value.triggers.length,views:form.value.views.length}[tab]||0)

function toggleNorm(action) {
  const idx = form.value.normActions.indexOf(action)
  if (idx >= 0) form.value.normActions.splice(idx, 1)
  else form.value.normActions.push(action)
}

// ────────────────────────────────────────────────────────────────────
// v95_p24b (2026-05-04 본부장님 본질 처방): 정규화 규칙 KB 활용
// ────────────────────────────────────────────────────────────────────
// 본부장님 호소:
//   "타입 정규화 규칙도 6개만 보여주고 3개가 적용된다고 기본 check 되있는데,
//    정말 6개가 다야? 3개만 선택된 이유가 뭐야? 필요하면 모두 선택시키고,
//    그리고 KB에 내용이 더 있다면 최대한 이용해서 초기 설정을 하고
//    다음 단계로 들어 가야 되는거 아냐?"
//
// 진짜 본질:
//   - 백엔드 KB (/api/v1/mapping/rules) 에 mssql→mysql 54건 있음 (전체 283건)
//   - 위저드는 자기가 박은 6개 하드코딩만 사용 (KB 무시)
//   - default check 도 'warn' 만 = 6개 중 3개 (자의적)
//
// v95_p24b 처방:
//   - 백엔드 KB API 호출하여 실제 등록된 규칙 가져옴
//   - warning=true 인 규칙은 모두 default check (level='warn' 만 limit 안 함)
//   - 카테고리도 백엔드 KB의 category 사용
//   - 부작용 0: API 실패 시 기존 하드코딩 6개 fallback
//   - 본부장님 모토 "KB = 살아있는 자산, 누적이 미래 AI 호출 빈도 줄임" 충족
async function loadNormRules() {
  const srcKey = (form.value.srcDb || '').toLowerCase()
  const tgtKey = (form.value.tgtDb || '').toLowerCase()

  // ── Phase 1: 하드코딩 fallback 데이터 (KB API 실패 시 사용) ───
  const NORM_RULES_FALLBACK = {
    'mssql→mysql': [
      { fix_action:'DATETIMEOFFSET_TO_DATETIME', title:'DATETIMEOFFSET → DATETIME(6)',   src_type:'DATETIMEOFFSET', tgt_type:'DATETIME(6)',    level:'warn',
        desc:'시간대(UTC) 변환 후 DATETIME(6)으로 저장. 시간대 정보는 소실됩니다.' },
      { fix_action:'ROWVERSION_TO_BIGINT',        title:'TIMESTAMP/ROWVERSION → BIGINT',  src_type:'TIMESTAMP',      tgt_type:'BIGINT',         level:'warn',
        desc:'8바이트 이진값을 정수로 변환. 행 버전 비교용으로는 사용 가능합니다.' },
      { fix_action:'GEO_TO_WKT',                  title:'GEOGRAPHY/GEOMETRY → TEXT(WKT)', src_type:'GEOGRAPHY',      tgt_type:'TEXT',           level:'warn',
        desc:'STAsText()로 WKT 문자열 변환. POINT(127.02 37.56) 형태로 저장됩니다.' },
      { fix_action:'UUID_TO_VARCHAR',             title:'UNIQUEIDENTIFIER → VARCHAR(36)', src_type:'UNIQUEIDENTIFIER', tgt_type:'VARCHAR(36)',  level:'info',
        desc:'UUID 형식(xxxxxxxx-xxxx-...) 그대로 문자열 저장.' },
      { fix_action:'NVARCHAR_TO_VARCHAR',         title:'NVARCHAR → VARCHAR(utf8mb4)',    src_type:'NVARCHAR',       tgt_type:'VARCHAR',        level:'info',
        desc:'utf8mb4 charset에서 VARCHAR는 NVARCHAR와 동일하게 유니코드 지원.' },
      { fix_action:'MONEY_TO_DECIMAL',            title:'MONEY → DECIMAL(19,4)',          src_type:'MONEY',          tgt_type:'DECIMAL(19,4)',  level:'info',
        desc:'동일한 정밀도 유지. 데이터 손실 없음.' },
    ],
    'mysql→mssql': [
      { fix_action:'IDENTITY_INSERT',   title:'AUTO_INCREMENT → IDENTITY(1,1)', src_type:'AUTO_INCREMENT', tgt_type:'IDENTITY(1,1)', level:'warn' },
      { fix_action:'NVARCHAR_CONVERT',  title:'VARCHAR → NVARCHAR',             src_type:'VARCHAR',        tgt_type:'NVARCHAR',      level:'info' },
      { fix_action:'BOOL_CONVERT',      title:'TINYINT(1) → BIT',               src_type:'TINYINT(1)',     tgt_type:'BIT',           level:'info' },
      { fix_action:'ENUM_TO_CHECK',     title:'ENUM → NVARCHAR + CHECK',        src_type:'ENUM',           tgt_type:'NVARCHAR(255)', level:'warn' },
      { fix_action:'DATETIME2_CONVERT', title:'DATETIME → DATETIME2(6)',        src_type:'DATETIME',       tgt_type:'DATETIME2(6)',  level:'info' },
    ],
  }
  const fallbackKey = `${srcKey}→${tgtKey}`
  const fallbackRules = NORM_RULES_FALLBACK[fallbackKey] || []

  // ── Phase 2: 백엔드 KB API 호출 (진짜 자산 활용) ──────────────
  let rulesFromKb = []
  let kbLoaded = false
  try {
    const { data } = await axios.get('/api/v1/mapping/rules', {
      params: { src_db: srcKey, tgt_db: tgtKey },
      timeout: 5000
    })
    if (Array.isArray(data) && data.length > 0) {
      // KB 규칙을 위저드용 형태로 변환
      // KB schema: {id, src_db, tgt_db, src_type, tgt_type, category, note, warning, custom, source}
      // Wizard schema: {fix_action, title, src_type, tgt_type, level, desc}
      rulesFromKb = data.map(r => ({
        fix_action: `KB_${r.id}`,  // KB 규칙은 id 기반 고유 action
        title: `${r.src_type} → ${r.tgt_type}` + (r.category ? ` (${r.category})` : ''),
        src_type: r.src_type,
        tgt_type: r.tgt_type,
        level: r.warning ? 'warn' : 'info',
        desc: r.note || '',
        kb_id: r.id,
        kb_category: r.category || '',
        kb_source: r.source || 'manual',
      }))
      kbLoaded = true
      console.log(`[v95_p24b] KB 규칙 ${rulesFromKb.length}건 로드 (${srcKey}→${tgtKey})`)
    } else {
      console.warn(`[v95_p24b] KB 규칙 0건 (${srcKey}→${tgtKey}) — fallback 사용`)
    }
  } catch (e) {
    console.warn('[v95_p24b] KB API 실패 (fallback 사용):', e.message || e)
  }

  // ── Phase 3: 최종 규칙 결정 (KB 우선, 실패 시 fallback) ────────
  if (kbLoaded && rulesFromKb.length > 0) {
    normRules.value = rulesFromKb
  } else {
    normRules.value = fallbackRules
  }

  // ── Phase 4: default check 강화 ──────────────────────────────
  // 본부장님 호소: "필요하면 모두 선택시키고"
  // 진짜 본질: 'warn' level 만 default check 는 자의적 → KB 의 warning=true 인 모든 규칙 default
  if (normRules.value.length && !form.value.normActions.length) {
    form.value.normActions = normRules.value
      .filter(r => r.level === 'warn')  // 데이터 손실 가능성 있는 것만 default
      .map(r => r.fix_action)
    console.log(`[v95_p24b] default check ${form.value.normActions.length}/${normRules.value.length}건 (warn level 자동 선택)`)
  }
}

// ────────────────────────────────────────────────────────────────────
// v95_p25 (2026-05-04 본부장님 본질 처방): 정규화 규칙 전체선택/해제
// ────────────────────────────────────────────────────────────────────
// 본부장님 호소: "전체선택 버튼 만들어 줘"
//                "지금은 3개 적용이라고 글자가 fix 되 있는데"
//
// 처방:
//   - 전체선택: 모든 normRules 의 fix_action 을 normActions 에 채움
//   - 전체해제: normActions 비우기
//   - "N / M개 적용" 표시는 템플릿에서 처리 (분모 노출)
function selectAllNorms() {
  form.value.normActions = normRules.value.map(r => r.fix_action)
  console.log(`[v95_p25] 전체 선택 ${form.value.normActions.length}/${normRules.value.length}건`)
}

function clearAllNorms() {
  form.value.normActions = []
  console.log('[v95_p25] 전체 해제')
}

const isAllNormsSelected = computed(() => {
  return normRules.value.length > 0
    && form.value.normActions.length === normRules.value.length
})

function toggleAutoFixAll(){ const t=!autoFixAll.value; warnRules.value.forEach(r=>{if(r.auto_fix)r.fixEnabled=t}) }
function toggleDow(v){ const i=sched.value.dows.indexOf(v); i>=0?sched.value.dows.splice(i,1):sched.value.dows.push(v) }
function isAllSelForTab(tab){
  const all=getAllForTab(tab)
  const sel=getSelForTab(tab)
  return all.length>0 && sel.length===all.length
}
// v90.9: 전체 개수 (5블록 카드용)
function getTotalCount(tab){
  return getAllForTab(tab).length
}
// v90.9: 부분 선택 (체크박스 indeterminate 상태)
function isPartialSelForTab(tab){
  const all=getAllForTab(tab)
  const sel=getSelForTab(tab)
  return sel.length > 0 && sel.length < all.length
}
// v90.9: 카드의 체크박스 클릭 → 해당 탭 전체 선택/해제
function toggleAllForTab(tab){
  const isAll = isAllSelForTab(tab)
  if(isAll){
    // 전체 해제
    if(tab==='tables') form.value.tables=[]
    else if(tab==='procedures') form.value.procedures=[]
    else if(tab==='functions')  form.value.functions=[]
    else if(tab==='triggers')   form.value.triggers=[]
    else if(tab==='views')      form.value.views=[]
  } else {
    // 전체 선택
    if(tab==='tables') form.value.tables=allTables.value.map(t=>t.table_name)
    else if(tab==='procedures') form.value.procedures=(allObjects.value.procedures||[]).map(o=>o.name)
    else if(tab==='functions')  form.value.functions=(allObjects.value.functions||[]).map(o=>o.name)
    else if(tab==='triggers')   form.value.triggers=(allObjects.value.triggers||[]).map(o=>o.name)
    else if(tab==='views')      form.value.views=(allObjects.value.views||[]).map(o=>o.name)
  }
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
  await loadNormRules()  // v95_p24b: KB API 호출하므로 async 대기
  const c=connector.source
  try{
    const {data}=await axios.post('/api/v1/schema/analyze-warnings',{
      src_db_type:form.value.srcDb, tgt_db_type:form.value.tgtDb,
      tables:form.value.tables,
      norm_actions: form.value.normActions,
      conn_info:{db_type:c.dbType,host:c.host,port:c.port,username:c.username,password:c.password,database:c.database}
    })
    warnRules.value=data.map(r=>({...r,fixEnabled:r.auto_fix&&r.affected_count>0}))
    data.forEach((r,i)=>{ if(r.affected_count>0) openRules.value[i]=true })
  } catch(e){ app.notify('경고 분석 실패','error') }
  finally{ analyzingWarn.value=false }
}

// v95_p23a (2026-05-03 본부장님 본질 처방): 사전 분석 (Pre-Flight)
//   본부장님 호소: "Dead lock 걸릴 거 분석해서 회피해서 순서를 정해야 되는거 아냐?"
//
//   분석 카테고리 (4가지):
//     1) deadlock_risk   - 동시 CREATE TABLE lock 충돌 위험
//     2) ai_conversion   - FUNC/SP/TRIG AI 변환 함정 패턴
//     3) dependency      - VIEW 의존 테이블 미선택/미존재
//     4) performance     - 대용량 테이블 동시 처리 위험
//
//   하드코딩 0%: src_db / tgt_db / 객체 종류만으로 동적 분석
//                Northwind / WideWorldImporters / 캐피탈사 운영 DB 동일 작동
// ════════════════════════════════════════════════════════════════
// v95_p65 (2026-05-05 본부장님): 객체별 사용자 결정 헬퍼
// ════════════════════════════════════════════════════════════════
// 
// API:
//   getObjectDecision(name)      → 'auto' | 'manual' | 'exclude' | null
//   setObjectDecision(name, dec) → form.objectDecisions[name] 설정
//   clearObjectDecision(name)    → 결정 제거
//   getObjectDecisionLabel(name) → 사용자 친화 라벨
function getObjectDecision(objName) {
  if (!objName) return null
  const d = (form.value.objectDecisions || {})[objName]
  return d ? d.decision : null
}

function setObjectDecision(objName, decision) {
  if (!objName) return
  if (!form.value.objectDecisions) form.value.objectDecisions = {}
  // 'manual' 결정 시 다음 v95_p66 (수동 SQL 모달) 에서 작성
  // 현재는 결정만 기록 (manual_sql 은 빈 문자열)
  const prev = form.value.objectDecisions[objName] || {}
  form.value.objectDecisions[objName] = {
    decision: decision,
    manual_sql: prev.manual_sql || '',  // 기존 수동 SQL 보존
    decided_at: new Date().toISOString(),
  }
  console.log(`[v95_p65] 객체 결정: [${objName}] → ${decision}`)
  // 안내 (manual 결정 시)
  if (decision === 'manual') {
    try {
      app.notify(
        `[${objName}] 수동 SQL 작성으로 설정 — 다음 v95_p66 패치에서 SQL 입력 모달 사용 가능`,
        'info'
      )
    } catch { /* notify 없으면 무시 */ }
  }
}

function clearObjectDecision(objName) {
  if (!objName || !form.value.objectDecisions) return
  delete form.value.objectDecisions[objName]
  console.log(`[v95_p65] 객체 결정 취소: [${objName}]`)
}

function getObjectDecisionLabel(objName) {
  const dec = getObjectDecision(objName)
  if (dec === 'auto') return '🤖 자동 변환 시도'
  if (dec === 'manual') return '✍️ 수동 SQL 작성'
  if (dec === 'exclude') return '⊘ 이관 제외'
  return ''
}

// ════════════════════════════════════════════════════════════════
// v95_p84 (2026-05-06 본부장님): 일괄 결정 + 좌측 인라인 결정
// ════════════════════════════════════════════════════════════════
// 본부장님 호소:
//   "오른쪽 창을 끝까지 드레그 한 후 하나씩 선택하기 너무 번거로워"
//   "여기 목록에서 AI 바로 선택하게 할 수 있을까?"
// 효과:
//   - 좌측 리스트의 각 객체 옆에 [🤖] [✍️] [⊘] 인라인 버튼
//   - 헤더에 일괄 처리: [모두 자동] [모두 제외] [초기화]
//   - 우측 드래그 + 스크롤 0 — 좌측에서 즉시 결정
// ════════════════════════════════════════════════════════════════

// object_risk 카테고리의 위험 객체 수 (일괄 처리 헤더에 표시)
const objectRiskCount = computed(() => {
  const risks = preflightRisks.value || []
  return risks.filter(r =>
    r.category === 'object_risk' && r.risk_meta && r.risk_meta.obj_name
  ).length
})

// 모든 위험 객체에 일괄 결정 적용
function setAllObjectDecisions(decision) {
  const risks = preflightRisks.value || []
  const objectRisks = risks.filter(r =>
    r.category === 'object_risk' && r.risk_meta && r.risk_meta.obj_name
  )
  if (objectRisks.length === 0) return
  
  // 사용자 확인 (manual 일괄은 의미 없으므로 제외 — auto 또는 exclude 만 일괄)
  const decisionLabel = decision === 'auto' ? '🤖 자동 변환 시도' :
                        decision === 'exclude' ? '⊘ 이관 제외' : decision
  if (!confirm(`${objectRisks.length}개 위험 객체를 모두 [${decisionLabel}] 로 설정할까요?`)) {
    return
  }
  
  let count = 0
  for (const r of objectRisks) {
    setObjectDecision(r.risk_meta.obj_name, decision)
    count++
  }
  console.log(`[v95_p84] 일괄 결정 적용: ${count}건 → ${decision}`)
  
  // 사용자에게 짧은 피드백 (alert 보다 우호적)
  // 결정 뱃지가 자동 표시되므로 추가 UI 불필요
}

// 모든 객체 결정 초기화
function clearAllObjectDecisions() {
  if (!form.value.objectDecisions) return
  const count = Object.keys(form.value.objectDecisions).length
  if (count === 0) return
  if (!confirm(`${count}개 객체의 결정을 모두 초기화할까요?`)) return
  
  form.value.objectDecisions = {}
  console.log(`[v95_p84] 모든 객체 결정 초기화: ${count}건`)
}
// ════════════════════════════════════════════════════════════════

// 객체 결정 통계 (UI 요약용 — Step 6 검토 화면 등에서 활용)
const objectDecisionStats = computed(() => {
  const decisions = form.value.objectDecisions || {}
  const all = Object.values(decisions)
  return {
    total: all.length,
    auto: all.filter(d => d.decision === 'auto').length,
    manual: all.filter(d => d.decision === 'manual').length,
    exclude: all.filter(d => d.decision === 'exclude').length,
  }
})

// ════════════════════════════════════════════════════════════════
// v95_p66 (2026-05-05 본부장님): 수동 SQL 입력 모달 (Phase 5-1)
// ════════════════════════════════════════════════════════════════
// 본부장님 결정: "5 Phase 모두 — 엔터프라이즈 솔루션"
//
// 본부장님 호소: vProductModelInstructions 같은 객체 사용자 직접 처방 필요
//
// 모달 구조:
//   - 좌측: MSSQL 원본 DDL (참고)
//   - 우측: MySQL 사용자 작성 영역 (textarea)
//   - 검출 패턴 + MySQL 대안 가이드 표시
//   - 검증 (v95_p67 SQL parse API) + 저장 + 취소
const manualSqlModal = ref({
  open: false,
  obj_name: '',
  obj_type: '',
  src_ddl: '',
  mysql_sql: '',
  patterns: [],          // 검출된 패턴 (대안 가이드 표시용)
  validation: null,      // { ok: bool, message: str }
  validating: false,
})

function openManualSqlModal(objName) {
  // selectedRisk 에서 risk_meta 추출
  const meta = selectedRisk.value?.risk_meta
  if (!meta || meta.obj_name !== objName) {
    console.warn(`[v95_p66] risk_meta 없음 — objName=${objName}`)
    return
  }
  // allObjects 에서 원본 DDL (body) 찾기
  let srcDdl = ''
  let objType = meta.obj_type || ''
  for (const list of [allObjects.value.views, allObjects.value.procedures,
                       allObjects.value.functions, allObjects.value.triggers]) {
    for (const o of (list || [])) {
      if (o.name === objName) {
        srcDdl = o.body || ''
        objType = (o.type || objType).toUpperCase()
        break
      }
    }
    if (srcDdl) break
  }
  // 기존 작성 SQL 있으면 복원
  const decisions = form.value.objectDecisions || {}
  const prev = decisions[objName] || {}
  
  manualSqlModal.value = {
    open: true,
    obj_name: objName,
    obj_type: objType,
    src_ddl: srcDdl,
    mysql_sql: prev.manual_sql || '',
    patterns: meta.detected_patterns || [],
    validation: null,
    validating: false,
  }
}

function closeManualSqlModal() {
  manualSqlModal.value.open = false
}

async function validateManualSql() {
  const sql = manualSqlModal.value.mysql_sql.trim()
  if (!sql) {
    manualSqlModal.value.validation = { ok: false, message: 'SQL 비어있음' }
    return
  }
  manualSqlModal.value.validating = true
  manualSqlModal.value.validation = null
  try {
    // v95_p67 (다음 패치) 의 검증 API 호출
    const { data } = await axios.post('/api/v1/sql/validate-mysql', {
      sql: sql,
      obj_type: manualSqlModal.value.obj_type,
      obj_name: manualSqlModal.value.obj_name,
    }, { timeout: 8000 })
    
    manualSqlModal.value.validation = {
      ok: !!data.ok,
      message: data.message || (data.ok ? '✓ 문법 검증 통과' : '✗ 문법 오류'),
      details: data.details || [],
    }
  } catch (e) {
    // v95_p67 미배포 시 — 클라이언트 측 기본 검증
    const hasCreate = /\bCREATE\s+(VIEW|PROCEDURE|FUNCTION|TRIGGER|TABLE)\b/i.test(sql)
    if (!hasCreate) {
      manualSqlModal.value.validation = {
        ok: false,
        message: '✗ CREATE 구문이 아닙니다 (CREATE VIEW/PROCEDURE/... 필요)',
      }
    } else {
      // 기본 통과 (백엔드 검증 API 미배포 시)
      manualSqlModal.value.validation = {
        ok: true,
        message: '⚠️ 클라이언트 기본 검증 통과 — 백엔드 검증 API (v95_p67) 미배포',
      }
    }
  } finally {
    manualSqlModal.value.validating = false
  }
}

function saveManualSql() {
  const m = manualSqlModal.value
  if (!m.mysql_sql.trim()) {
    try { app.notify('SQL 을 입력해주세요', 'warn') } catch {}
    return
  }
  // 검증 통과 못한 상태면 경고 (저장은 허용 — 사용자 책임)
  if (m.validation && !m.validation.ok) {
    if (!confirm('검증 실패 상태입니다. 그래도 저장하시겠습니까?')) return
  }
  // form.objectDecisions 에 저장
  if (!form.value.objectDecisions) form.value.objectDecisions = {}
  form.value.objectDecisions[m.obj_name] = {
    decision: 'manual',
    manual_sql: m.mysql_sql.trim(),
    decided_at: new Date().toISOString(),
  }
  console.log(`[v95_p66] 수동 SQL 저장: [${m.obj_name}]`)
  try {
    app.notify(`[${m.obj_name}] 수동 SQL 저장 완료`, 'success')
  } catch {}
  closeManualSqlModal()
}

async function runPreflightAnalysis(){
  preflightAnalyzing.value = true
  preflightRisks.value = []
  preflightSummary.value = {total:0, critical:0, warn:0, info:0, auto_fix_count:0}
  preflightOpen.value = false
  
  const c = connector.source
  
  // ════════════════════════════════════════════════════════════
  // v95_p64 (2026-05-05 본부장님): 객체 DDL 동봉 → 백엔드 패턴 분석
  // ════════════════════════════════════════════════════════════
  // 본부장님 결정: "5 Phase 모두 순차 구현 — 엔터프라이즈 솔루션"
  //
  // 본질:
  //   vProductModelInstructions / vJobCandidateEducation 같은 VIEW 가
  //   XML/CROSS APPLY 패턴으로 자동 변환 실패 → 1146 잔류
  //
  // 처방 (Phase 1-2 + Phase 4):
  //   1) allObjects 의 body (DDL) 를 preflight 에 동봉
  //   2) 백엔드가 v95_p62 패턴 검출 엔진으로 분석
  //   3) HIGH 위험 객체 → object_risk 카테고리 critical 반환
  //   4) UI 카드에 객체별 위험 표시 + 사용자 결정 (다음 v95_p65)
  //
  // 부작용 0:
  //   - 선택된 객체만 DDL 전송 (전체 객체 X)
  //   - 옛 백엔드는 object_ddls 무시 (Optional 필드)
  //   - DDL 누락 시 분석 스킵 (안전)
  // ════════════════════════════════════════════════════════════
  function collectObjectDDLs() {
    const ddls = []
    const selectedProcs = new Set(form.value.procedures || [])
    const selectedFuncs = new Set(form.value.functions || [])
    const selectedTrigs = new Set(form.value.triggers || [])
    const selectedViews = new Set(form.value.views || [])
    
    // 위저드의 allObjects 에서 DDL (body) 추출
    for (const o of (allObjects.value.procedures || [])) {
      if (selectedProcs.has(o.name) && o.body) {
        ddls.push({ name: o.name, type: 'PROCEDURE', ddl: o.body })
      }
    }
    for (const o of (allObjects.value.functions || [])) {
      if (selectedFuncs.has(o.name) && o.body) {
        ddls.push({ name: o.name, type: 'FUNCTION', ddl: o.body })
      }
    }
    for (const o of (allObjects.value.triggers || [])) {
      if (selectedTrigs.has(o.name) && o.body) {
        ddls.push({ name: o.name, type: 'TRIGGER', ddl: o.body })
      }
    }
    for (const o of (allObjects.value.views || [])) {
      if (selectedViews.has(o.name) && o.body) {
        ddls.push({ name: o.name, type: 'VIEW', ddl: o.body })
      }
    }
    return ddls
  }
  
  try {
    const objectDdls = collectObjectDDLs()
    console.log(`[v95_p64-Preflight] 객체 DDL 동봉 ${objectDdls.length}개`)
    
    const {data} = await axios.post('/api/v1/preflight/analyze', {
      src_db: form.value.srcDb,
      tgt_db: form.value.tgtDb,
      selection: {
        tables:     form.value.tables || [],
        procedures: form.value.procedures || [],
        functions:  form.value.functions || [],
        triggers:   form.value.triggers || [],
        views:      form.value.views || [],
        // v95_p64: 객체 DDL 동봉 → 백엔드 v95_p62 패턴 검출
        object_ddls: objectDdls,
      },
      source_conn: c.host ? {
        db_type: c.dbType, host: c.host, port: c.port,
        username: c.username, password: c.password, database: c.database,
      } : null,
      parallel_tables: 3,  // 기본값 (job 의 parallel_tables 와 동일)
    }, { timeout: 15000 })  // v95_p64: 객체 분석 추가로 timeout 약간 늘림
    
    if (data.ok) {
      preflightRisks.value = data.risks || []
      preflightSummary.value = data.summary || {}
      // 위험 발견 시 결과 패널 자동 열기
      if (preflightRisks.value.length > 0) {
        preflightOpen.value = true
      }
      console.log('[v95_p23a-Preflight] 분석 완료:', preflightSummary.value)
      // v95_p64: object_risk 카테고리 통계 추가 로그
      const objRisks = preflightRisks.value.filter(r => r.category === 'object_risk')
      if (objRisks.length > 0) {
        console.log(`[v95_p64-Preflight] 객체 위험 검출: ${objRisks.length}건`)
      }
    } else {
      console.warn('[v95_p23a-Preflight] 분석 실패:', data.error)
    }
  } catch(e) {
    // 사전 분석 실패해도 위저드 진행 차단 안 함 (안전)
    console.warn('[v95_p23a-Preflight] 호출 실패 (무시):', e.message || e)
  } finally {
    preflightAnalyzing.value = false
  }
}

function goStep(i) {
  // 이미 완료된 단계 또는 현재 단계만 이동 가능
  if (i > cur.value) return  // 미완료 단계는 이동 불가
  if (i === cur.value) return
  // v88 P1: Step 3(AI DBA) 으로 되돌아올 때 "원본 그대로" 플래그 리셋
  //   - 사용자가 재검토하려는 의도 → AdvisorPanel 초기 상태로 표시
  if (i === 3 && cur.value > 3) {
    form.value.advisorSkipped = false
  }
  cur.value = i
  if (i >= 1) loadAll()  // 스키마 로딩 필요
}

// 정규화 단계가 필요한지 판단
function needsNormStep() {
  const src = form.value.srcDb
  const tgt = form.value.tgtDb
  // 같은 DB 타입이면 불필요
  const srcGroup = (s) => {
    if (['mssql','azure','sqlserver'].includes(s)) return 'mssql'
    if (['mysql','aurora','mariadb','tidb','cloudsql'].includes(s)) return 'mysql'
    if (['postgresql','postgres','redshift'].includes(s)) return 'pg'
    return s
  }
  if (srcGroup(src) === srcGroup(tgt)) return false
  // 테이블이 없으면 불필요
  if (form.value.tables !== null && form.value.tables.length === 0) return false
  return true
}

function nextStep(){
  if(cur.value===0){
    // v90.1: 시나리오 필수 선택 검증
    if(!form.value.migrationScenario){
      alert('이관 시나리오를 먼저 선택해주세요.\n\n시나리오에 따라 AI DBA + PII 정책이 자동 적용됩니다.')
      return
    }
    // v90.2: DB 사용 기록 (백엔드에 저장 → 다음 진입 시 자주 쓰는 DB 우선)
    if (form.value.srcDb) recordDbUse(form.value.srcDb, 'source')
    if (form.value.tgtDb) recordDbUse(form.value.tgtDb, 'target')
    cur.value++; loadAll(); return
  }
  if(cur.value===1){
    // v95_p23a (2026-05-03 본부장님 본질 처방): 위저드 사전 분석 (Pre-Flight)
    //   본부장님 호소: "위저드에서 테이블 및 오브젝트 전체 선택하고 다음으로
    //                넘어가면 그때 전체 분석할때 이렇게 dead lock 걸릴 거
    //                분석해서 회피해서 순서를 정해야 되는거 아냐?"
    //   처방: 객체 선택 → 다음 클릭 시 사전 분석 자동 실행 (~3초)
    //         위험 발견 시 결과 패널 표시, 사용자 확인 후 진행
    runPreflightAnalysis()  // 비동기, 결과는 preflightRisks ref 에 채움
    
    if(needsNormStep()){
      cur.value++; analyzeWarnings()
    } else {
      // 변환 규칙 단계 스킵 → Stage 4 AI DBA 권고로
      // (v88: 기존에는 cur=3 으로 실행옵션 스킵이었으나, AI DBA 단계 삽입으로 인해 변경)
      cur.value = 3
    }
    return
  }
  // v88 P1: Step 3 = AI DBA 권고 (신규)
  //   - "원본 그대로" 를 선택해도 위저드 단계는 통과만 하면 되므로 별도 검증 불필요
  //   - AdvisorPanel 컴포넌트 내부에서 skip / analyze 이벤트를 부모 form 에 반영
  if(cur.value===3){
    // v90.12: PII 탭 미방문 검증 (개선)
    //   - 사용자가 PII 탭을 한번도 클릭 안 했고
    //   - PII 가능성 있는 시나리오면
    //   - 명시적으로 확인받기
    const piiSensitiveScenarios = ['prod_to_dev', 'prod_to_qa', 'prod_to_analytics', 
                                    'gdpr_compliant', 'pci_dss']
    const isSensitive = piiSensitiveScenarios.includes(form.value.migrationScenario)
    
    if (isSensitive && !privacyTabVisited.value && !form.value.privacySkipped) {
      const sc = form.value.migrationScenario
      const scName = {
        prod_to_dev: '운영 → 개발',
        prod_to_qa: '운영 → QA',
        prod_to_analytics: '운영 → 분석/통계',
        gdpr_compliant: 'GDPR 준수',
        pci_dss: 'PCI-DSS 준수',
      }[sc] || sc
      
      const msg = `⚠️  PII Privacy 탭을 아직 확인하지 않으셨습니다\n\n` +
                  `현재 시나리오: ${scName}\n` +
                  `이 시나리오는 개인정보 마스킹 검토가 필요합니다.\n\n` +
                  `[확인]: PII Privacy 탭으로 이동\n` +
                  `[취소]: 마스킹 없이 그대로 이관 (책임 본인)`
      
      const goCheck = confirm(msg)
      
      if (goCheck) {
        // 본부장님 안내 - PII 탭으로 가달라
        alert('🛡️  Step 3 의 [PII Privacy] 탭을 클릭하여 확인해주세요.\n\n' +
              '확인 후 다시 [다음 단계] 누르시면 진행됩니다.')
        return  // 현재 단계 머무르기
      } else {
        // 명시적 스킵 (책임 인정)
        form.value.privacySkipped = true
        console.warn('[Wizard] PII 검토 명시적 스킵:', form.value.migrationScenario)
      }
    }
    // AI DBA 권고 통과 → 실행 옵션으로
  }
  if(cur.value===4){
    // v88: 실행 옵션 단계 — 유효성 플래그 (기존 v3 재활용 유지)
    v3.value=true
    if(!form.value.name){
      form.value.name = connector.source.database + ' → ' + connector.target.database + ' 이관'
    }
  }
  if(cur.value<5) cur.value++
}

// v88 P1: AdvisorPanel 의 @skip 이벤트 — "원본 그대로" 선택 시
//   - form.advisorSkipped 를 true 로 플래그
//   - form.advisorDecisions 를 초기화 (이전 분석 결과 있으면 날림)
//   - 즉시 다음 단계(실행 옵션)로 진행
function onAdvisorSkip() {
  form.value.advisorSkipped = true
  form.value.advisorDecisions = []
  // 즉시 Step 4(실행 옵션)로 진행
  nextStep()
}

// v89: PII Privacy 스킵 — Step 3 의 PII 탭에서 "마스킹 없이 이관" 클릭 시
function onPrivacySkip() {
  form.value.privacySkipped = true
  form.value.privacyDecisions = []
  // PII 만 스킵 — 위저드는 Step 3 에 머묾 (다른 탭 사용 가능)
}

async function submit(asSchedule=false){
  submitting.value=true
  try {
    const src=connector.source; const tgt=connector.target

    // v10 #23f: form 의 DB 유형이 비어있으면 connector store 에서 자동 채움
    //           (사용자가 1단계 DB 카드를 클릭 안 했어도 프로파일 접속 상태라면 복구)
    if (!form.value.srcDb && src.dbType) form.value.srcDb = src.dbType
    if (!form.value.tgtDb && tgt.dbType) form.value.tgtDb = tgt.dbType

    // 그래도 비어있으면 명확한 에러 메시지
    if (!form.value.srcDb || !form.value.tgtDb) {
      alert('소스/타겟 DB 유형이 지정되지 않았습니다.\n\n1단계 "DB 선택" 으로 돌아가서 소스와 타겟 DB 종류를 먼저 선택해주세요.')
      cur.value = 0
      return
    }

    // 스케줄 cron 생성
    let cronStr = null
    if(asSchedule && schedEnabled.value){
      if(schedType.value==='once') cronStr=`ONCE:${sched.value.date}T${sched.value.time}`
      else if(schedType.value==='repeat') cronStr=buildCron()
      else cronStr=sched.value.cron
    }

    // ── 이관 호환성 사전 검증 (Tier 기반) ─────────────────
    // Tier CONNECT(Oracle/SQLite 등)는 이관 불가 — 조용히 실행되는 대신
    // 명시적으로 차단하여 사용자 혼란 방지.
    try {
      const compat = await fetch('/api/v1/connectors/migration-compatible', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({src_db: form.value.srcDb, tgt_db: form.value.tgtDb})
      }).then(r => r.json())
      if (!compat.compatible) {
        alert(`이관 불가 조합입니다.\n\n소스: ${form.value.srcDb || '(미지정)'}\n타겟: ${form.value.tgtDb || '(미지정)'}\n\n${compat.reason || ''}\n\n소스·타겟을 지원되는 조합(MySQL/MSSQL/PostgreSQL 등 Tier 1)으로 변경해주세요.`)
        return
      }
    } catch (_e) {
      // 검증 엔드포인트 실패는 치명적이지 않음 — 계속 진행
    }

    try{
      const fixActions=warnRules.value.filter(r=>r.fixEnabled&&r.affected_count>0).map(r=>({action:r.fix_action,affected:r.affected_tables}))
      await jobs.create({
        name:form.value.name,
        src_db:form.value.srcDb, tgt_db:form.value.tgtDb,
        src_host:src.host,src_port:src.port,src_database:src.database,src_username:src.username,src_password:src.password,
        tgt_host:tgt.host,tgt_port:tgt.port,tgt_database:tgt.database,tgt_username:tgt.username,tgt_password:tgt.password,
        tables: form.value.tables.length > 0 ? form.value.tables : [],
        objects:{procedures:form.value.procedures,functions:form.value.functions,triggers:form.value.triggers,views:form.value.views},
        convert_objects:form.value.convertObjs,
        ddl_engine:form.value.ddlEngine,
        obj_engine:form.value.objEngine,
        // v92p11: AI 자동 재이관 토글 (본부장님 명시적 ON 일 때만 작동)
        ai_auto_retry: form.value.aiAutoRetry,
        ai_retry_count: form.value.aiAutoRetryCount,
        table_mode:form.value.tableMode,
        view_mode:form.value.viewMode,
        obj_mode:form.value.objMode,
        batch_size:form.value.batchSize, parallel_workers:form.value.workers,
        on_error:form.value.onError, drop_table:form.value.dropTbl, truncate_target:form.value.dropTbl?false:form.value.truncate, create_table:form.value.createTbl,
        skip_triggers: form.value.skipTriggers,  // v90.32: 트리거 hang 회피
        // v90.48: schema 정책 (테이블/객체 이관 일관성)
        schema_strategy: form.value.schemaStrategy,
        // v9 패치 #20: bulk loader
        bulk_mode: form.value.bulkMode,
        bulk_threshold_rows: form.value.bulkThresholdRows,
        // v9 패치 #23: 테이블 병렬 + MSSQL 튜닝
        parallel_tables: form.value.parallelTables,
        mssql_tuning: form.value.mssqlTuning,
        mssql_disable_indexes: form.value.mssqlDisableIndexes,
        auto_fix_actions:fixActions,
        schedule_cron:cronStr,
        // v88 P1: AI DBA 분석 결과 전달 (백엔드는 P6 에서 사용. 지금은 기록용)
        advisor_mode:      form.value.advisorSkipped ? 'skipped' : form.value.advisorMode,
        advisor_decisions: form.value.advisorDecisions,
      })
      const msg = asSchedule ? `스케줄 등록 완료! (${cronStr})` : `"${form.value.name}" Job 시작!`
      app.notify(msg,'success')
      // v90.19: Job 생성 성공 → 위저드 상태 클리어 (다음 진입 시 신규 시작)
      clearWizardState()
      router.push(asSchedule?'/jobs':'/monitor')
    } catch(e){
      app.notify('생성 실패: '+(e.response?.data?.detail||e.message),'error')
    }
  } finally {
    // v10 #23f: 어떤 경로로 return 되든 버튼 잠김 해제 (좀비 상태 방지)
    submitting.value=false
  }
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

// ── 프로파일 자동연동 ──────────────────────────────────
const appliedProfileId = ref('')

// v10 #11: 최근 사용 기준 정렬 + 하이라이트
// 사용자 피드백: "다른 것이 선택된 것처럼 보인다"
//   → 원인: 프로파일 빠른 시작 패널에 저장 순서 그대로 표시됐음
//   → 해결: 최근 사용한 프로파일을 맨 왼쪽으로 + 색상 차별화
//
// localStorage 에 프로파일별 마지막 사용 시각을 저장 (applyProfile 시 갱신).
// 백엔드 API 변경 없이 프론트에서만 정렬.
const _lastUsedVersion = ref(0)  // applyProfile 호출 후 재계산 트리거용

function _getLastUsedMap() {
  try {
    const raw = localStorage.getItem('databridge.profile.lastUsed')
    return raw ? JSON.parse(raw) : {}
  } catch (e) {
    return {}
  }
}

const sortedProfiles = computed(() => {
  // _lastUsedVersion 참조 → applyProfile 후 재계산 유발
  void _lastUsedVersion.value
  const usedMap = _getLastUsedMap()
  const list = [...(connector.profiles || [])]
  // 최근 사용(timestamp 큰 값) 먼저, 미사용은 맨 뒤
  list.sort((a, b) => {
    const ta = usedMap[a.id] || 0
    const tb = usedMap[b.id] || 0
    if (ta !== tb) return tb - ta  // 최근이 앞
    // 둘 다 미사용이면 이름순 (일관성)
    return (a.name || '').localeCompare(b.name || '')
  })
  return list
})

// 최근 사용 여부 판정 — 가장 최근 1개만 'recent' 하이라이트
// 1개만 강조하는 이유: 2~3개 모두 강조하면 시각적 구별력이 떨어짐.
// "사용자가 마지막으로 적용한 그것" 이 가장 중요한 신호.
const mostRecentProfileId = computed(() => {
  void _lastUsedVersion.value
  const usedMap = _getLastUsedMap()
  let bestId = null
  let bestTs = 0
  for (const [pid, ts] of Object.entries(usedMap)) {
    if (ts > bestTs) { bestTs = ts; bestId = pid }
  }
  return bestId
})

function applyProfile(p) {
  connector.applyProfile(p)
  appliedProfileId.value = p.id
  _lastUsedVersion.value++  // sortedProfiles/mostRecentProfileId 재계산 트리거
  // form DB 타입 자동 갱신
  form.value.srcDb = p.source?.db_type || p.source?.dbType || form.value.srcDb
  form.value.tgtDb = p.target?.db_type || p.target?.dbType || form.value.tgtDb
  // Job 이름 자동 채우기
  if (!form.value.name) {
    form.value.name = (p.source?.database||'') + ' → ' + (p.target?.database||'') + ' 이관'
  }
  app.notify(`"${p.name}" 프로파일 적용됨`, 'success')
}

onMounted(async ()=>{
  loadDbHistory()  // v90.2: DB 사용 이력 로드
  // v10 #31: 페이지 진입 시 프로파일 목록이 비어있으면 자동 로드
  //   하드 리프레시 / 새 탭에서 진입 시 "저장된 프로파일로 빠른 시작" 패널이
  //   안 보이던 문제 해결. profiles.length 가 0이면 API 호출.
  if (!connector.profiles || connector.profiles.length === 0) {
    try {
      await connector.loadProfiles()
    } catch (e) {
      // 실패해도 위저드 자체는 계속 사용 가능해야 함 (직접 DB 카드 선택 경로)
      console.warn('프로파일 로드 실패:', e)
    }
  }
  if(connector.source.dbType) form.value.srcDb=connector.source.dbType
  if(connector.target.dbType) form.value.tgtDb=connector.target.dbType
  if(!form.value.name&&connector.source.database&&connector.target.database)
    form.value.name=`${connector.source.database} → ${connector.target.database} 이관`
  
  // v90.19: 마지막에 저장된 상태 복원 (다른 페이지 갔다 왔을 때)
  //   - 라우트 쿼리에 ?fresh=1 이 있으면 복원 안 함 (새 위저드 강제)
  const isFresh = route.query?.fresh === '1' || route.query?.new === '1'
  if (!isFresh) {
    restoreWizardState()
  } else {
    clearWizardState()  // ?fresh=1 진입 시 옛 상태 명시적 정리
  }
  
  // cur 가 3 이면 analysisTabsLoaded 도 true
  if (cur.value === 3) analysisTabsLoaded.value = true
})

// v90.19: cur 가 3 (AI 분석) 진입 시 analysisTabsLoaded 활성화
watch(() => cur.value, (v) => {
  if (v === 3) analysisTabsLoaded.value = true
})
</script>

<style scoped>
/* ── 위저드 루트 ── */
.wiz-root { display:flex; flex-direction:column; gap:0; min-height:100%; }

/* ── 위저드 탑바 ── */
.wiz-topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 20px 28px 16px; gap: 24px; flex-wrap: wrap;
  background: var(--bg-primary);
  border-bottom: 0.5px solid var(--border-light);
  position: sticky; top: 0; z-index: 10;
}
.wiz-title { font-size: 1.1rem; font-weight: 700; color: var(--text-primary); }
.wiz-subtitle { font-size: .75rem; color: var(--text-tertiary); margin-top: 2px; }

/* ── 단계 네비게이터 ── */
.wiz-steps { display: flex; align-items: center; gap: 0; }
.wiz-step {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 12px; background: none; border: none;
  cursor: default; font-family: var(--font);
  color: var(--text-tertiary); transition: all .15s;
  border-radius: var(--radius-md);
}
.wiz-step.reachable { cursor: pointer; }
.wiz-step.reachable:hover { background: var(--bg-secondary); color: var(--text-secondary); }
.wiz-step-num {
  width: 24px; height: 24px; border-radius: 50%;
  border: 1.5px solid var(--border-mid);
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; flex-shrink: 0;
  transition: all .15s;
}
.wiz-step-lbl { font-size: 12px; font-weight: 500; white-space: nowrap; }
.wiz-step.active { color: #2563eb; }
.wiz-step.active .wiz-step-num {
  border-color: #2563eb; background: #2563eb; color: #fff;
  box-shadow: 0 0 0 3px rgba(37,99,235,.15);
}
.wiz-step.done { color: #16a34a; }
.wiz-step.done .wiz-step-num {
  border-color: #16a34a; background: #16a34a; color: #fff;
}
.wiz-step-line {
  width: 32px; height: 1.5px; background: var(--border-mid);
  flex-shrink: 0; transition: background .3s;
}
.wiz-step-line.done { background: #16a34a; }

/* ── 엔진 선택 바 ── */
.wiz-engine-bar {
  display: flex; align-items: center; gap: 0;
  background: var(--bg-secondary);
  border-bottom: 0.5px solid var(--border-light);
  padding: 10px 28px; gap: 24px;
}
.eb-row { display: flex; align-items: center; gap: 12px; flex: 1; }
.eb-lbl { font-size: .75rem; font-weight: 600; color: var(--text-primary); white-space: nowrap; }
.eb-sub2 { font-size: .7rem; color: var(--text-tertiary); white-space: nowrap; }
.eb-opts { display: flex; gap: 4px; }
.eb-opt {
  display: flex; align-items: center; gap: 5px;
  padding: 4px 10px; border-radius: var(--radius-sm);
  border: 0.5px solid var(--border-light);
  cursor: pointer; transition: all .12s;
  font-size: .75rem; color: var(--text-tertiary);
  background: var(--bg-primary);
}
.eb-opt:hover { border-color: var(--border-mid); color: var(--text-secondary); }
.eb-opt.active { border-color: #2563eb; background: rgba(37,99,235,.08); color: #2563eb; font-weight: 600; }
.eb-opt-ico { font-size: 13px; line-height: 1; }
.eb-opt-lbl { white-space: nowrap; }
.eb-divider2 { width: 0.5px; height: 28px; background: var(--border-mid); flex-shrink: 0; }

/* ── 위저드 바디 ── */
.wiz-body { flex: 1; padding: 24px 28px; background: var(--bg-primary); }

/* DB 선택 */
.wh {
  font-size: .72rem; font-weight: 600; color: var(--text-tertiary);
  text-transform: uppercase; letter-spacing: .06em;
  margin-bottom: 12px; display: flex; align-items: center; gap: 8px;
}
.wh::after { content: ''; flex: 1; height: 0.5px; background: var(--border-light); }
.conn-summary {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 16px; background: rgba(22,163,74,.06);
  border: 0.5px solid rgba(22,163,74,.2);
  border-radius: var(--radius-md); margin-bottom: 20px; font-size: 12.5px;
}
.cs-item { display: flex; align-items: center; gap: 7px; font-weight: 500; }
.cs-arrow { color: var(--text-tertiary); font-size: 16px; }
.cs-ok {
  margin-left: auto; font-size: 11px;
  color: #16a34a; font-weight: 600;
  display: flex; align-items: center; gap: 4px;
}
.db-grid {
  display: grid; grid-template-columns: repeat(8, 1fr);
  gap: 6px; margin-bottom: 4px;
}
@media(max-width:900px){ .db-grid{ grid-template-columns:repeat(5,1fr); } }
.db-card {
  border: 0.5px solid var(--border-light);
  border-radius: 8px; padding: 11px 5px 10px;
  cursor: pointer; text-align: center;
  background: var(--bg-secondary);
  transition: border-color .12s, background .12s, box-shadow .12s;
  position: relative;
  display: flex; flex-direction: column; align-items: center; gap: 6px;
}
.db-card:hover { border-color: #93c5fd; background: rgba(37,99,235,.03); }
.db-card.sel  { border-color: #2563eb; background: rgba(37,99,235,.05); box-shadow: 0 0 0 2px rgba(37,99,235,.12); }
.db-card.cur  { border-color: #16a34a; background: rgba(22,163,74,.04); }
.db-card.sel.cur { border-color: #2563eb; }

/* ── DB 이름 — 크고 뚜렷하게 ── */
.db-card-name {
  font-size: 11.5px; color: var(--text-primary);
  font-weight: 500; line-height: 1.3;
  word-break: keep-all; text-align: center;
}
.db-card.sel .db-card-name { color: #1d4ed8; font-weight: 600; }
.db-card.cur .db-card-name { color: #15803d; font-weight: 600; }

/* ── 컬러 도트 바 ── */
.db-card-dot {
  width: 24px; height: 3px; border-radius: 99px;
  flex-shrink: 0; opacity: .6;
}
/* ── 약어 — 아주 작게 ── */
.db-card-abbr-txt {
  font-size: 9px; font-weight: 700; letter-spacing: .04em;
  opacity: .55; line-height: 1;
}

/* ── 연결됨 배지 ── */
.db-card-badge {
  position: absolute; top: -6px; right: -4px;
  font-size: 8px; background: #16a34a; color: #fff;
  padding: 1px 5px; border-radius: 99px; font-weight: 700;
  box-shadow: 0 1px 3px rgba(0,0,0,.15);
}
.db-card-badge.tgt { background: #2563eb; }
.mini-ico { display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:4px;font-size:9px;font-weight:700;flex-shrink:0; }

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
/* v9 패치 #12: 정렬 헤더 */
.sort-hdr{display:flex;align-items:center;gap:4px;padding:4px 2px 6px;flex-wrap:wrap}
.sort-lbl{font-size:11px;color:var(--text-tertiary);margin-right:4px}
.sort-btn{padding:3px 10px;font-size:11px;border:1px solid var(--border-color);background:var(--bg-secondary);color:var(--text-secondary);border-radius:12px;cursor:pointer;transition:all .15s}
.sort-btn:hover{background:var(--bg-primary);border-color:var(--accent-blue)}
.sort-btn.on{background:var(--accent-blue);color:#fff;border-color:var(--accent-blue);font-weight:600}

/* v9 패치 #31: 테이블 탭 정렬 헤더 컬럼 위치 정렬 */
.sort-hdr-table{flex-wrap:nowrap;padding:4px 10px 6px;gap:6px}
.sort-hdr-table .sort-hdr-left{display:flex;align-items:center;gap:4px;flex:1;min-width:0}
.sort-hdr-table .sort-btn-rows{width:90px;text-align:center;flex-shrink:0}
.sort-hdr-table .sort-btn-size{width:70px;text-align:center;flex-shrink:0}

.obj-row{display:flex;align-items:center;gap:6px;padding:6px 10px;border-radius:var(--radius-sm);cursor:pointer;font-size:12px}
.obj-row:hover{background:var(--bg-primary)}

/* v9 패치 #31: 테이블 행 — 헤더와 컬럼 일치 */
.obj-row-table .obj-meta-rows{width:90px;text-align:right;flex-shrink:0}
.obj-row-table .obj-meta-size{width:70px;text-align:right;flex-shrink:0}

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
/* ── 이관 모드 섹션 헤더 ── */
.mode-section-hd {
  display:flex; align-items:center; gap:7px;
  margin-top:4px; margin-bottom:8px;
  padding:6px 10px; border-radius:6px;
  border-left:2.5px solid var(--border-mid);
  background:var(--bg-primary);
}
.mode-hd-blue   { border-left-color:#3b82f6; background:rgba(59,130,246,.04); }
.mode-hd-green  { border-left-color:#22c55e; background:rgba(34,197,94,.04);  }
.mode-hd-purple { border-left-color:#8b5cf6; background:rgba(139,92,246,.04); }

.mode-section-ico {
  display:flex; align-items:center; justify-content:center;
  width:20px; height:20px; border-radius:5px; flex-shrink:0;
  font-size:.75rem;
  background:var(--bg-secondary); border:1px solid var(--border-mid);
}
.mode-hd-blue   .mode-section-ico { background:rgba(59,130,246,.1);  border-color:rgba(59,130,246,.2); }
.mode-hd-green  .mode-section-ico { background:rgba(34,197,94,.1);   border-color:rgba(34,197,94,.2);  }
.mode-hd-purple .mode-section-ico { background:rgba(139,92,246,.1);  border-color:rgba(139,92,246,.2); }

.mode-section-title {
  font-size:.8rem; font-weight:600; color:var(--text-primary);
  letter-spacing:-.01em; flex:1;
}
.mode-hd-blue   .mode-section-title { color:#1d4ed8; }
.mode-hd-green  .mode-section-title { color:#15803d; }
.mode-hd-purple .mode-section-title { color:#6d28d9; }

.mode-section-badge {
  font-size:.65rem; font-weight:600; padding:2px 8px; border-radius:10px;
  background:rgba(139,92,246,.12); color:#7c3aed; border:1px solid rgba(139,92,246,.2);
  white-space:nowrap;
}

/* ── 가로 배치 모드 카드 ── */
.mode-cards-h {
  display:grid; grid-template-columns:repeat(auto-fit, minmax(180px,1fr));
  gap:8px; margin-bottom:10px;
}
/* 2026-04-23 fmt: 한 줄 컴팩트 레이아웃 — flex-direction: row 로 아이콘·제목·설명 인라인 */
.mode-card-h {
  display:flex; flex-direction:row; align-items:center; gap:8px;
  padding:8px 12px; border-radius:8px;
  border:1.5px solid var(--border-light);
  background:var(--bg-secondary); cursor:pointer;
  transition:all .15s; position:relative; overflow:hidden;
  min-height:0;
}
.mode-card-h input[type="radio"] { display:none; }
.mode-card-h:hover {
  border-color:var(--border-mid);
  background:var(--bg-primary);
  box-shadow:0 2px 6px rgba(0,0,0,.04);
}
/* 색상별 active 스타일 */
.mode-card-h.active {
  border-color:var(--accent-blue,#3b82f6);
  background:rgba(59,130,246,.05);
  box-shadow:0 0 0 2px rgba(59,130,246,.1);
}
.mode-card-h.mode-blue.active  { border-color:#3b82f6; background:rgba(59,130,246,.05);  box-shadow:0 0 0 2px rgba(59,130,246,.12);  }
.mode-card-h.mode-green.active { border-color:#22c55e; background:rgba(34,197,94,.05);   box-shadow:0 0 0 2px rgba(34,197,94,.12);   }
.mode-card-h.mode-purple.active{ border-color:#8b5cf6; background:rgba(139,92,246,.05);  box-shadow:0 0 0 2px rgba(139,92,246,.12);  }
.mode-card-h.mode-gray.active  { border-color:#6b7280; background:rgba(107,114,128,.05); box-shadow:0 0 0 2px rgba(107,114,128,.1); }

.mch-icon {
  font-size:.95rem; line-height:1;
  opacity:.7;
  transition:opacity .12s;
  flex-shrink:0;
}
.mode-card-h:hover .mch-icon,
.mode-card-h.active .mch-icon { opacity:1; }

/* 2026-04-23 fmt: body 도 row 로 → 제목과 설명이 같은 줄, 설명은 연하게 */
.mch-body {
  flex:1; min-width:0;
  display:flex; align-items:baseline; gap:7px;
  overflow:hidden;
}
.mch-title {
  font-size:.8rem; font-weight:600; color:var(--text-primary); line-height:1.2;
  flex-shrink:0;
}
.mch-desc  {
  font-size:.7rem; color:var(--text-tertiary); line-height:1.35;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
  margin-top:0;
}

.mode-card-h.mode-blue.active  .mch-title { color:#2563eb; }
.mode-card-h.mode-green.active .mch-title { color:#16a34a; }
.mode-card-h.mode-purple.active .mch-title{ color:#7c3aed; }
.mode-card-h.mode-gray.active  .mch-title { color:#4b5563; }

.mch-check {
  position:absolute; top:7px; right:9px;
  width:15px; height:15px; border-radius:50%;
  background:var(--accent-blue,#3b82f6); color:#fff;
  display:flex; align-items:center; justify-content:center;
  font-size:.6rem; font-weight:700;
}
.mode-card-h.mode-green.active .mch-check  { background:#22c55e; }
.mode-card-h.mode-purple.active .mch-check { background:#8b5cf6; }
.mode-card-h.mode-gray.active  .mch-check  { background:#6b7280; }

/* 기존 스타일 (하위 호환) */
.mode-cards { display:flex; flex-direction:column; gap:5px; margin-top:4px; }
.mode-card {
  display:flex; align-items:center; gap:10px;
  padding:10px 13px; border-radius:8px;
  border:1.5px solid var(--border-light);
  background:var(--bg-secondary); cursor:pointer; transition:all .15s;
}
.mode-card input[type="radio"] { display:none; }
.mode-card:hover { border-color:var(--border-mid); background:var(--bg-primary); }
.mode-card.active {
  border-color:var(--accent-blue,#3b82f6);
  background:rgba(59,130,246,.05);
  box-shadow:0 0 0 3px rgba(59,130,246,.1);
}
.mc-radio { flex-shrink:0; }
.mc-dot {
  width:15px; height:15px; border-radius:50%;
  border:2px solid var(--border-mid); background:transparent; transition:all .15s;
  display:flex; align-items:center; justify-content:center;
}
.mc-dot.checked { border-color:var(--accent-blue,#3b82f6); background:var(--accent-blue,#3b82f6); }
.mc-dot-inner { width:5px; height:5px; border-radius:50%; background:#fff; }
.mc-text { display:flex; flex-direction:column; gap:2px; flex:1; }
.mc-title { font-size:.83rem; font-weight:600; color:var(--text-primary); line-height:1; }
.mc-desc  { font-size:.71rem; color:var(--text-tertiary); line-height:1.3; }
.mode-card.active .mc-title { color:var(--accent-blue,#3b82f6); }
.mode-card.active .mc-desc  { color:var(--text-secondary); }

/* 추가 옵션 박스 */
.tbl-opts-box {
  margin-top:10px; border:1px solid var(--border-light);
  border-radius:9px; overflow:hidden; background:var(--bg-secondary);
}
.tbl-opts-title {
  padding:7px 13px; font-size:.7rem; font-weight:700;
  text-transform:uppercase; letter-spacing:.06em;
  color:var(--text-tertiary); background:var(--bg-primary);
  border-bottom:1px solid var(--border-light);
}
.tbl-opt-row {
  display:flex; align-items:center; gap:10px; padding:7px 13px;
  cursor:pointer; transition:background .1s; border-bottom:1px solid var(--border-light);
}
.tbl-opt-row:last-child { border-bottom:none; }
.tbl-opt-row:hover { background:var(--bg-primary); }
.tbl-opt-row input[type="checkbox"] { accent-color:var(--accent-blue,#3b82f6); flex-shrink:0; }
/* 2026-04-23 fmt: 라벨과 설명을 한 줄에 인라인 배치 — 공간 절약 */
.tbl-opt-info {
  display:flex; align-items:baseline; gap:8px;
  flex:1; min-width:0;
  flex-direction:row;
}
.tbl-opt-label {
  font-size:.81rem; font-weight:500; color:var(--text-primary);
  flex-shrink:0;
}
.tbl-opt-desc  {
  font-size:.7rem; color:var(--text-tertiary);
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
  min-width:0;
}
.opt-chk{display:flex;align-items:center;gap:7px;font-size:12px;color:var(--text-secondary);margin-top:8px;cursor:pointer}
.opt-chk input{accent-color:var(--accent-blue)}

/* 검토 */
.review-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:14px}
.rv-item{display:flex;align-items:center;justify-content:space-between;padding:7px 10px;background:var(--bg-secondary);border-radius:var(--radius-sm)}
.rv-l{font-size:11px;color:var(--text-tertiary)}.rv-v{font-size:12px;font-weight:500;color:var(--text-primary)}

/* v95_p37 본질 4 (2026-05-05 본부장님): 검토 화면 블록 분리 */
.review-section{
  background: var(--bg-secondary);
  border: 0.5px solid var(--border-light);
  border-radius: var(--radius-lg);
  margin-bottom: 12px;
  overflow: hidden;
}
.review-section-head{
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px;
  background: var(--bg-primary);
  border-bottom: 0.5px solid var(--border-light);
  font-size: 12.5px;
  user-select: none;
}
.review-section-head-collapsible{
  cursor: pointer; transition: background .12s;
}
.review-section-head-collapsible:hover{
  background: rgba(0,0,0,0.03);
}
.review-section-title{
  font-weight: 600; color: var(--text-primary);
  letter-spacing: 0.01em;
}
.review-section-count{
  margin-left: auto; font-size: 11px; color: var(--text-tertiary);
  font-weight: 500;
}
.review-section .review-grid{
  margin: 0; padding: 10px;
}

/* ════════════════════════════════════════════════════════════ */
/* v95_p40 (2026-05-05 본부장님): 검토 화면 시각 구분 + 레이아웃    */
/* ════════════════════════════════════════════════════════════ */
/* 시각 구분 — 헤더는 약간 더 짙은 배경 + 좌측 색상 띠로 강조 */
.review-section-head-primary{
  background: linear-gradient(to right, rgba(37,99,235,0.06), rgba(37,99,235,0.02) 50%, transparent);
  border-left: 3px solid #2563eb;
  padding-left: 11px;  /* 3px border 보정 */
}
.review-section-head.review-section-head-collapsible{
  background: linear-gradient(to right, rgba(0,0,0,0.025), transparent 50%);
  border-left: 3px solid var(--border-mid);
  padding-left: 11px;
  transition: border-left-color .15s, background .15s;
}
.review-section-head.review-section-head-collapsible:hover{
  border-left-color: #2563eb;
  background: linear-gradient(to right, rgba(37,99,235,0.04), rgba(37,99,235,0.01) 50%, transparent);
}

/* 헤더 우측 Job 이름 표시 */
.review-section-jobname{
  margin-left: auto;
  font-size: 12.5px; font-weight: 600;
  color: #2563eb;
  max-width: 60%;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-family: ui-monospace, SFMono-Regular, monospace;
  letter-spacing: -0.01em;
  padding: 2px 8px;
  background: rgba(37,99,235,0.08);
  border-radius: 4px;
}

/* 기본 정보 본문 — 2줄 압축 */
.review-basic-body{
  padding: 12px;
  display: flex; flex-direction: column; gap: 10px;
}

/* 1줄: 소스 → 타겟 좌우 카드 + 가운데 화살표 */
.review-dbflow-row{
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 10px; align-items: center;
}
.review-db-card{
  padding: 9px 12px;
  background: var(--bg-primary);
  border: 0.5px solid var(--border-light);
  border-radius: 6px;
  display: flex; flex-direction: column; gap: 3px;
  min-width: 0;  /* overflow 보호 */
}
.review-db-source{
  border-left: 3px solid #94a3b8;  /* 회색 — 소스 */
}
.review-db-target{
  border-left: 3px solid #2563eb;  /* 파랑 — 타겟 (강조) */
}
.review-db-label{
  font-size: 10.5px; font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase; letter-spacing: 0.05em;
}
.review-db-value{
  display: flex; align-items: center; gap: 5px;
  font-size: 13px; font-weight: 600;
  color: var(--text-primary);
  font-family: ui-monospace, SFMono-Regular, monospace;
  overflow: hidden;
}
.review-db-engine{
  color: var(--text-secondary); flex-shrink: 0;
}
.review-db-sep{ color: var(--text-tertiary); opacity: 0.5; }
.review-db-name{
  color: #2563eb;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  min-width: 0;
}
.review-dbflow-arrow{
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}

/* 2줄: 이관 모드 / AI DBA / 자동 수정 (3 columns) */
.review-attr-row{
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 6px;
}
/* v95_p52 (2026-05-05 본부장님): 5칸 한 줄 (DDL/객체 엔진 추가) */
.review-attr-row-5col{
  grid-template-columns: 1fr 1fr 1fr 1fr 1fr;
}
.rv-item-compact{
  padding: 7px 10px;
  background: var(--bg-primary);
  border: 0.5px solid var(--border-light);
  border-radius: 6px;
}

/* 좁은 화면 — 세로 스택 */
@media (max-width: 700px){
  .review-dbflow-row{ grid-template-columns: 1fr; gap: 6px; }
  .review-dbflow-arrow{ transform: rotate(90deg); padding: 4px 0; }
  .review-attr-row{ grid-template-columns: 1fr; }
  .review-section-jobname{ max-width: 50%; }
}
/* v95_p52: 5칸 → 좁은 화면 (1024 이하) 자동 3+2 wrap */
@media (max-width: 1024px){
  .review-attr-row-5col{
    grid-template-columns: 1fr 1fr 1fr;
  }
}
@media (max-width: 700px){
  .review-attr-row-5col{
    grid-template-columns: 1fr 1fr;
  }
}

/* ════════════════════════════════════════════════════════════ */
/* v95_p48 (2026-05-05 본부장님): 검토 화면 표 형식 + 그룹 분리   */
/* ════════════════════════════════════════════════════════════ */
/* 본부장님 호소: "컬럼과 관련 정보 너무 떨어져 있음"                */
/*               "한 줄에 4개 정보, 블록 구분, 표 형태로 구분"        */

.review-detail-body{
  padding: 14px;
  background: #ffffff;
}

/* 그룹 (이관 객체 / 변환·실행 설정) */
.review-group{
  margin-bottom: 12px;
}
.review-group:last-child{
  margin-bottom: 0;
}
.review-group-title{
  display: flex; align-items: center; gap: 7px;
  font-size: 12px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(0,0,0,0.06);
  letter-spacing: -0.01em;
}
.review-group-bullet{
  display: inline-block;
  width: 4px; height: 14px;
  background: #2563eb;
  border-radius: 2px;
  flex-shrink: 0;
}
.review-group-bullet-cfg{
  background: #6d28d9;  /* 보라 — 변환·실행 그룹 */
}

/* 표 형식 — 4-column 기본, 6-column 변형, 라벨 행 + 값 행 교대 */
.review-table{
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  table-layout: fixed;
  background: #fafbfc;
  border: 1px solid rgba(0,0,0,0.06);
  border-radius: 6px;
  overflow: hidden;
}
.review-table td{
  padding: 7px 10px;
  width: 25%;            /* 4-column 균등 (기본) */
  /* v95_p54 (2026-05-05 본부장님): 컬럼간 구분선 선명하게 */
  /*   Before: 1px dashed rgba(0,0,0,0.05) — 거의 안 보임 */
  /*   After:  1px solid  rgba(0,0,0,0.12) — 명확히 분리 */
  border-right: 1px solid rgba(0,0,0,0.12);
  border-bottom: 1px solid rgba(0,0,0,0.12);
  vertical-align: middle;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* v95_p50: 6-column 변형 (이관 객체 / 변환·실행 한 줄용) */
.review-table-6col td{
  width: 16.66%;          /* 6-column 균등 */
  padding: 7px 8px;       /* 좁은 컬럼 — 패딩 약간 축소 */
  font-size: 12px;        /* 축소 */
}
.review-table td:last-child{
  border-right: none;
}
.review-table tr:last-child td{
  border-bottom: none;
}

/* v95_p50: 라벨/값 시각 구분 강화 — 라벨과 값 사이 굵은 구분선 */
/* v95_p54: 더 선명하게 (0.12 → 0.30) */
.review-table tr.review-table-labels + tr.review-table-values td{
  border-top: 2px solid rgba(37, 99, 235, 0.30);  /* 선명한 파란 구분선 */
}

/* 라벨 행 — 회색 배경 + uppercase + 작게 + 약하게 */
.review-table-labels td{
  background: rgba(0,0,0,0.04);
  font-size: 10px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.review-table-6col .review-table-labels td{
  font-size: 9.5px;       /* 6-column 더 좁아 — 라벨 폰트 더 축소 */
}

/* 값 행 — 흰 배경 + 진한 검정 + 굵게 (강조) */
.review-table-values td{
  font-size: 13px;
  font-weight: 700;       /* v95_p50: 600 → 700 더 강조 */
  color: #0f172a;
  background: #ffffff;
}
.review-table-6col .review-table-values td{
  font-size: 12.5px;
}

/* 단위 (개, 건 등) — 약하게 */
.review-unit{
  margin-left: 1px;
  font-size: 11px;
  font-weight: 500;
  color: #94a3b8;
}

/* AI 엔진 — 보라색 강조 */
.review-table-values td.rv-engine-ai{
  color: #6d28d9;
}

/* 경고 — 빨강 강조 (이관전 DROP 등) */
.review-table-values td.rv-warn{
  color: #dc2626;
  font-weight: 700;
}

/* 좁은 화면 — 2-column 으로 */
@media (max-width: 700px){
  .review-table td{ width: 50%; }
  .review-table-labels td:nth-child(3),
  .review-table-labels td:nth-child(4),
  .review-table-values td:nth-child(3),
  .review-table-values td:nth-child(4){
    border-top: 1px solid rgba(0,0,0,0.05);
  }
  /* v95_p50: 6-column 도 좁은 화면에선 3-column */
  .review-table-6col td{ width: 33.33%; }
  .review-table-6col .review-table-labels td:nth-child(4),
  .review-table-6col .review-table-labels td:nth-child(5),
  .review-table-6col .review-table-labels td:nth-child(6),
  .review-table-6col .review-table-values td:nth-child(4),
  .review-table-6col .review-table-values td:nth-child(5),
  .review-table-6col .review-table-values td:nth-child(6){
    border-top: 1px solid rgba(0,0,0,0.05);
  }
}

/* 다크 모드 호환 */
.dark .review-detail-body{ background: var(--bg-secondary); }
.dark .review-group-title{ color: var(--text-primary); border-bottom-color: rgba(255,255,255,0.08); }
.dark .review-table{ background: var(--bg-primary); border-color: rgba(255,255,255,0.08); }
.dark .review-table-labels td{ background: rgba(255,255,255,0.03); }
.dark .review-table-values td{ background: var(--bg-primary); color: var(--text-primary); }
.dark .review-table td{ border-right-color: rgba(255,255,255,0.15); border-bottom-color: rgba(255,255,255,0.15); }

/* ════════════════════════════════════════════════════════════ */
/* v95_p43 (2026-05-05 본부장님): 시각 계층 강화 — "구분이 잘 안돼"   */
/* ════════════════════════════════════════════════════════════ */
/* 본부장님 호소: 섹션 헤더와 본문, 라벨과 값 시각 분리 강화          */

/* 섹션 컨테이너 — 흰 배경 + 미세 그림자로 떠있는 카드 인상 */
.review-section{
  background: #ffffff;
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 8px;
  margin-bottom: 14px;
  overflow: hidden;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}

/* 섹션 헤더 — 회색톤 배경으로 본문과 명확히 분리 */
.review-section-head{
  background: linear-gradient(to bottom, #f8fafc, #f1f5f9);
  border-bottom: 1px solid rgba(0,0,0,0.08);
  padding: 11px 14px;
  font-size: 13px;
}

/* 기본 정보 (primary) — 파란 강조 */
.review-section-head-primary{
  background: linear-gradient(to bottom, #eff6ff, #dbeafe 130%);
  border-left: 4px solid #2563eb;
  padding-left: 12px;
}

/* 접힘 가능 헤더 — 회색 띠 + 호버 시 파랑 */
.review-section-head.review-section-head-collapsible{
  background: linear-gradient(to bottom, #f8fafc, #f1f5f9);
  border-left: 4px solid #cbd5e1;
  padding-left: 12px;
}
.review-section-head.review-section-head-collapsible:hover{
  background: linear-gradient(to bottom, #eff6ff, #dbeafe 130%);
  border-left-color: #2563eb;
}

/* 섹션 제목 — 굵은 검정 */
.review-section-title{
  font-weight: 700;
  color: #0f172a;
  font-size: 13px;
  letter-spacing: -0.01em;
}

/* 헤더 우측 카운트/요약 — 약한 회색 + monospace */
.review-section-count{
  color: #64748b;
  font-size: 11.5px;
  font-weight: 500;
  font-family: ui-monospace, SFMono-Regular, monospace;
  letter-spacing: -0.01em;
}

/* 본문 행 (이관 객체 / 변환·실행 설정) — 카드형 + 미세 테두리 */
.review-section .review-grid{
  padding: 12px;
  background: #ffffff;
  gap: 8px;
}
.review-section .rv-item{
  background: #fafbfc;
  border: 1px solid rgba(0,0,0,0.06);
  border-radius: 6px;
  padding: 9px 12px;
  transition: border-color .12s, background .12s;
}
.review-section .rv-item:hover{
  background: #ffffff;
  border-color: rgba(37,99,235,0.2);
}

/* 라벨 — 약한 회색 + 작은 폰트 + uppercase (덜 부각) */
.review-section .rv-l{
  font-size: 10.5px;
  color: #64748b;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
/* 값 — 진한 검정 + 굵은 폰트 (부각) */
.review-section .rv-v{
  font-size: 13px;
  color: #0f172a;
  font-weight: 600;
  letter-spacing: -0.01em;
}

/* 기본 정보 본문 영역 강화 */
.review-basic-body{
  padding: 14px;
  background: #ffffff;
}

/* DB 카드 — 더 진한 라벨 + 더 굵은 값 */
.review-db-card{
  background: #fafbfc;
  border: 1px solid rgba(0,0,0,0.08);
  padding: 11px 14px;
  transition: border-color .12s, background .12s;
}
.review-db-card:hover{
  background: #ffffff;
  border-color: rgba(37,99,235,0.25);
}
.review-db-source{
  border-left: 4px solid #94a3b8;
}
.review-db-target{
  border-left: 4px solid #2563eb;
  background: linear-gradient(to right, rgba(37,99,235,0.03), #fafbfc 30%);
}
.review-db-label{
  font-size: 10px;
  color: #64748b;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.review-db-value{
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}
.review-db-engine{
  color: #475569;
  font-weight: 600;
}
.review-db-name{
  color: #2563eb;
  font-weight: 700;
}

/* 2줄 속성 행 (이관 모드 / AI DBA / 자동 수정) — 카드형 강화 */
.rv-item-compact{
  background: #fafbfc;
  border: 1px solid rgba(0,0,0,0.06);
  padding: 10px 12px;
  transition: border-color .12s, background .12s;
  display: flex; align-items: center; justify-content: space-between;
}
.rv-item-compact:hover{
  background: #ffffff;
  border-color: rgba(37,99,235,0.2);
}
.rv-item-compact .rv-l{
  font-size: 10.5px;
  color: #64748b;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.rv-item-compact .rv-v{
  font-size: 13px;
  color: #0f172a;
  font-weight: 600;
}

/* 다크 모드 호환 — CSS 변수 우선 (테마 전환 시 자동) */
.dark .review-section{
  background: var(--bg-secondary);
  border-color: rgba(255,255,255,0.08);
}
.dark .review-section-head{
  background: linear-gradient(to bottom, var(--bg-primary), rgba(0,0,0,0.05));
  border-bottom-color: rgba(255,255,255,0.06);
}
.dark .review-section-head-primary{
  background: linear-gradient(to bottom, rgba(37,99,235,0.12), rgba(37,99,235,0.04));
}
.dark .review-section-title{ color: var(--text-primary); }
.dark .review-section .rv-item,
.dark .rv-item-compact,
.dark .review-db-card{
  background: var(--bg-primary);
  border-color: rgba(255,255,255,0.08);
}
.dark .review-section .rv-v,
.dark .review-db-value,
.dark .rv-item-compact .rv-v{ color: var(--text-primary); }

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

.norm-section{background:var(--bg-secondary);border:0.5px solid var(--border-light);border-radius:10px;overflow:hidden;margin-bottom:4px}

/* ════════════════════════════════════════════════════════════════ */
/* v95_p23a (2026-05-03 본부장님 본질 처방): 사전 분석 (Pre-Flight) */
/* ════════════════════════════════════════════════════════════════ */
.preflight-banner{
  border-radius: 10px; padding: 12px 14px; margin-bottom: 12px;
  font-size: 12.5px; line-height: 1.5;
  border: 1px solid;
}
.preflight-banner.preflight-loading{
  background: rgba(59,130,246,0.06); border-color: rgba(59,130,246,0.30);
  color: #1e40af; display: flex; gap: 10px; align-items: center;
}
.preflight-banner.preflight-info{
  background: rgba(59,130,246,0.05); border-color: rgba(59,130,246,0.25);
}
.preflight-banner.preflight-warn{
  background: rgba(245,158,11,0.06); border-color: rgba(245,158,11,0.35);
}
.preflight-banner.preflight-critical{
  background: rgba(220,38,38,0.06); border-color: rgba(220,38,38,0.35);
}

.preflight-header{ display:flex; align-items:center; gap:8px; }
.preflight-icon{ font-size:16px; line-height:1; }
.preflight-title{ flex:1; }
.preflight-title strong{ font-weight:700; }

.preflight-badge{
  display: inline-block; font-size: 10.5px; font-weight: 600;
  padding: 2px 7px; border-radius: 10px; margin-left: 6px;
  letter-spacing: 0.02em;
}
.preflight-badge.crit{ background:#dc2626;  color:white; }
.preflight-badge.warn{ background:#f59e0b;  color:white; }
.preflight-badge.info{ background:#3b82f6;  color:white; }
.preflight-badge.fix { background:#16a34a;  color:white; }

.preflight-list{
  margin-top: 10px; padding-top: 10px;
  border-top: 1px dashed rgba(0,0,0,0.10);
  display: flex; flex-direction: column; gap: 8px;
}
.preflight-item{
  background: rgba(255,255,255,0.55); border-radius: 8px; padding: 10px 12px;
  border-left: 3px solid;
}
.preflight-item-info     { border-left-color: #3b82f6; }
.preflight-item-warn     { border-left-color: #f59e0b; }
.preflight-item-critical { border-left-color: #dc2626; }

.preflight-item-head{
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  margin-bottom: 4px;
}
.preflight-item-level{
  font-size: 10px; font-weight: 700; padding: 2px 7px;
  border-radius: 4px; letter-spacing: 0.04em;
}
.preflight-item-level.level-info     { background:#dbeafe; color:#1e40af; }
.preflight-item-level.level-warn     { background:#fef3c7; color:#92400e; }
.preflight-item-level.level-critical { background:#fee2e2; color:#991b1b; }
.preflight-item-cat{
  font-size: 11.5px; font-weight: 600; color: var(--text-secondary);
}
.preflight-item-title{
  font-size: 12.5px; font-weight: 600; color: var(--text-primary);
}
.preflight-item-desc{
  font-size: 11.5px; color: var(--text-secondary);
  line-height: 1.55; margin-top: 2px;
}
.preflight-item-affected{
  display: flex; gap: 6px; align-items: center; flex-wrap: wrap;
  margin-top: 6px; font-size: 11px;
}
.preflight-chip{
  background: rgba(0,0,0,0.06); padding: 1px 7px; border-radius: 4px;
  font-family: ui-monospace, monospace; font-size: 10.5px; color: var(--text-secondary);
}
.preflight-item-fix{
  display: flex; gap: 6px; align-items: center; margin-top: 6px;
  padding: 4px 8px; background: rgba(34,197,94,0.08);
  border-radius: 5px; font-size: 11px; color: #15803d; font-weight: 500;
}

/* ════════════════════════════════════════════════════════════ */
/* v95_p37 본질 1 (2026-05-05 본부장님): 사전 분석 마스터-디테일  */
/* ════════════════════════════════════════════════════════════ */
.pf-sort-controls{
  display: flex; align-items: center; gap: 4px;
  margin-left: auto; padding-left: 12px;
}
.pf-sort-label{
  font-size: 11px; color: var(--text-tertiary); margin-right: 2px;
}
.pf-sort-btn{
  padding: 3px 9px; font-size: 11px; font-weight: 500;
  border: 0.5px solid var(--border-mid);
  background: var(--bg-secondary); color: var(--text-secondary);
  border-radius: 4px; cursor: pointer; transition: all .12s;
  font-family: inherit;
}
.pf-sort-btn:hover{
  background: var(--bg-primary); color: var(--text-primary);
}
.pf-sort-btn.on{
  background: #2563eb; color: white; border-color: #2563eb;
}

.pf-master-detail{
  /* v95_p75 (2026-05-06 본부장님): 좌측 폭 확대 (320 → 420)  */
  /*   본부장님 호소: "폭을 조금더 넓히고, 오른쪽 폭은 조금 줄여야"   */
  /*   효과: 좌측 리스트에 결정 뱃지 + 객체 이름 더 잘 보임           */
  /* v95_p76: 추가 조정 — 좌측 460 으로 확대 (객체 이름 + 뱃지 더 명확) */
  display: grid; grid-template-columns: 460px 1fr; gap: 14px;
  margin-top: 10px; padding-top: 10px;
  border-top: 1px dashed rgba(0,0,0,0.10);
  min-height: 200px;
}
.pf-list{
  display: flex; flex-direction: column; gap: 4px;
  max-height: 460px; overflow-y: auto;
  padding-right: 4px;
}
.pf-list-item{
  display: flex; align-items: center; gap: 8px;
  padding: 9px 10px; border-radius: 6px; cursor: pointer;
  background: rgba(255,255,255,0.55); border-left: 3px solid transparent;
  transition: all .12s; font-size: 12px;
}
.pf-list-item:hover{
  background: rgba(255,255,255,0.9);
}
.pf-list-item.pf-selected{
  background: rgba(37,99,235,0.08); border-left-color: #2563eb;
  box-shadow: 0 0 0 1px rgba(37,99,235,0.15);
}
.pf-list-item.pf-level-critical{ border-left-color: #dc2626; }
.pf-list-item.pf-level-warn    { border-left-color: #f59e0b; }
.pf-list-item.pf-level-info    { border-left-color: #3b82f6; }
.pf-list-level{
  font-size: 10px; font-weight: 700; padding: 2px 6px;
  border-radius: 3px; letter-spacing: 0.04em; flex-shrink: 0;
}
.pf-list-level.level-info     { background:#dbeafe; color:#1e40af; }
.pf-list-level.level-warn     { background:#fef3c7; color:#92400e; }
.pf-list-level.level-critical { background:#fee2e2; color:#991b1b; }
.pf-list-cat-icon{
  font-size: 14px; flex-shrink: 0;}
.pf-list-title{
  flex: 1; font-size: 12px; color: var(--text-primary);
  font-weight: 500; line-height: 1.4;
  overflow: hidden; text-overflow: ellipsis;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}
.pf-list-count{
  font-size: 10.5px; font-weight: 600; color: var(--text-tertiary);
  background: rgba(0,0,0,0.06); padding: 1px 6px; border-radius: 9px;
  flex-shrink: 0; min-width: 20px; text-align: center;
}

/* ════════════════════════════════════════════════════════════ */
/* v95_p75 (2026-05-06 본부장님): 좌측 리스트 결정 뱃지         */
/*   본부장님 호소: "어떤걸 선택했는지 보여 주자"                */
/* ════════════════════════════════════════════════════════════ */
.pf-list-decision-badge{
  flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px;
  border-radius: 50%;
  font-size: 12px; font-weight: 700;
  border: 2px solid;
  box-shadow: 0 1px 2px rgba(0,0,0,0.08);
  cursor: help;
}
.pf-list-decision-auto{
  background: rgba(34, 197, 94, 0.15);
  border-color: #16a34a;
  color: #16a34a;
}
.pf-list-decision-manual{
  background: rgba(168, 85, 247, 0.15);
  border-color: #7c3aed;
  color: #7c3aed;
}
.pf-list-decision-exclude{
  background: rgba(220, 38, 38, 0.15);
  border-color: #dc2626;
  color: #dc2626;
}

/* ════════════════════════════════════════════════════════════ */
/* v95_p84 (2026-05-06 본부장님): 좌측 인라인 결정 버튼 + 일괄 처리  */
/*   본부장님 호소:                                            */
/*   "오른쪽 창을 끝까지 드레그 한 후 하나씩 선택하기 너무 번거로워" */
/*   "여기 목록에서 AI 바로 선택하게 할 수 있을까?"             */
/* ════════════════════════════════════════════════════════════ */

/* 일괄 처리 헤더 */
.pf-bulk-actions{
  display: flex; align-items: center; gap: 6px;
  padding: 8px 10px; margin-bottom: 6px;
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.06), rgba(34, 197, 94, 0.04));
  border: 1px solid rgba(37, 99, 235, 0.15);
  border-radius: 6px;
  flex-wrap: wrap;
}
.pf-bulk-label{
  font-size: 11.5px; font-weight: 700;
  color: var(--text-primary);
  margin-right: 4px;
}
.pf-bulk-btn{
  padding: 4px 9px;
  background: white;
  border: 1.5px solid var(--border-light);
  border-radius: 5px;
  font-size: 11px; font-weight: 600;
  cursor: pointer;
  transition: all .15s;
  user-select: none;
}
.pf-bulk-btn:hover{
  transform: translateY(-1px);
  box-shadow: 0 2px 5px rgba(0,0,0,0.08);
}
.pf-bulk-auto{ color: #15803d; border-color: #16a34a; }
.pf-bulk-auto:hover{ background: rgba(34, 197, 94, 0.1); }
.pf-bulk-exclude{ color: #b91c1c; border-color: #dc2626; }
.pf-bulk-exclude:hover{ background: rgba(220, 38, 38, 0.08); }
.pf-bulk-clear{ color: #6b7280; border-color: #d1d5db; }
.pf-bulk-clear:hover{ background: #f3f4f6; }

/* 좌측 리스트 인라인 결정 버튼 그룹 */
.pf-list-quick-actions{
  flex-shrink: 0;
  display: inline-flex; gap: 3px;
  margin-left: auto;        /* 우측 끝으로 정렬 */
}
.pf-quick-btn{
  width: 24px; height: 24px;
  display: inline-flex; align-items: center; justify-content: center;
  background: white;
  border: 1.5px solid var(--border-light);
  border-radius: 5px;
  font-size: 12px;
  cursor: pointer;
  transition: all .12s;
  user-select: none;
  padding: 0;
}
.pf-quick-btn:hover{
  transform: scale(1.1);
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
/* 각 옵션별 hover 색 */
.pf-quick-auto:hover    { background: rgba(34, 197, 94, 0.12);  border-color: #16a34a; }
.pf-quick-manual:hover  { background: rgba(168, 85, 247, 0.12); border-color: #7c3aed; }
.pf-quick-exclude:hover { background: rgba(220, 38, 38, 0.10);  border-color: #dc2626; }
/* active 상태 (현재 선택된 결정) */
.pf-quick-btn.active{
  border-width: 2px;
  font-weight: 700;
}
.pf-quick-auto.active{
  background: rgba(34, 197, 94, 0.18);  border-color: #16a34a;
  box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.2);
}
.pf-quick-manual.active{
  background: rgba(168, 85, 247, 0.18); border-color: #7c3aed;
  box-shadow: 0 0 0 2px rgba(168, 85, 247, 0.2);
}
.pf-quick-exclude.active{
  background: rgba(220, 38, 38, 0.15);  border-color: #dc2626;
  box-shadow: 0 0 0 2px rgba(220, 38, 38, 0.15);
}

/* ════════════════════════════════════════════════════════════ */
/* v95_p89_ux (2026-05-07 본부장님 본질 처방):                   */
/*   풍선 도움말 강화 — title 만으로 부족 → CSS tooltip          */
/*   본부장님 호소: "로봇/손글씨 무슨 뜻인지 모르겠어"            */
/*                                                                */
/*   효과: data-tip 속성 있는 버튼 호버 시 즉시 라벨 표시         */
/*         (브라우저 title 기본 500ms 지연 → 0ms 즉시)            */
/* ════════════════════════════════════════════════════════════ */
.pf-quick-btn[data-tip],
.pf-bulk-btn[data-tip] {
  position: relative;
}
.pf-quick-btn[data-tip]::after,
.pf-bulk-btn[data-tip]::after {
  content: attr(data-tip);
  position: absolute;
  bottom: calc(100% + 6px);  /* 버튼 위쪽에 표시 */
  left: 50%;
  transform: translateX(-50%);
  background: rgba(15, 23, 42, .95);
  color: #fff;
  padding: 5px 10px;
  border-radius: 6px;
  font-size: 11.5px;
  font-weight: 500;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity .15s ease, transform .15s ease;
  z-index: 1000;
  box-shadow: 0 4px 12px rgba(0, 0, 0, .25);
}
.pf-quick-btn[data-tip]::before,
.pf-bulk-btn[data-tip]::before {
  content: '';
  position: absolute;
  bottom: calc(100% + 1px);
  left: 50%;
  transform: translateX(-50%);
  border: 5px solid transparent;
  border-top-color: rgba(15, 23, 42, .95);
  opacity: 0;
  pointer-events: none;
  transition: opacity .15s ease;
  z-index: 1001;
}
.pf-quick-btn[data-tip]:hover::after,
.pf-quick-btn[data-tip]:hover::before,
.pf-bulk-btn[data-tip]:hover::after,
.pf-bulk-btn[data-tip]:hover::before {
  opacity: 1;
}
.pf-quick-btn[data-tip]:hover::after {
  transform: translateX(-50%) translateY(-2px);
}
/* 결정 뱃지 (기존 v95_p75) — 인라인 버튼이 추가되었으므로 위치 조정 */
.pf-list-item .pf-list-decision-badge{
  margin-left: auto;        /* 인라인 버튼 그룹 직전으로 */
  margin-right: 4px;
}
.pf-list-item .pf-list-quick-actions ~ .pf-list-decision-badge,
.pf-list-item .pf-list-decision-badge ~ .pf-list-quick-actions{
  /* 둘 다 있으면 자연스럽게 옆에 배치 — flex 기본 동작 */
}

.pf-detail{
  background: rgba(255,255,255,0.65); border-radius: 8px;
  padding: 14px 16px; min-height: 180px;
}
.pf-detail-empty{
  display: flex; align-items: center; justify-content: center;
  height: 100%; color: var(--text-tertiary); font-size: 12px;
  font-style: italic;
}
.pf-detail-head{
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  margin-bottom: 8px; padding-bottom: 8px;
  border-bottom: 0.5px solid rgba(0,0,0,0.08);
}
.pf-detail-level{
  font-size: 10.5px; font-weight: 700; padding: 2px 8px;
  border-radius: 4px; letter-spacing: 0.04em;
}
.pf-detail-level.level-info     { background:#dbeafe; color:#1e40af; }
.pf-detail-level.level-warn     { background:#fef3c7; color:#92400e; }
.pf-detail-level.level-critical { background:#fee2e2; color:#991b1b; }
.pf-detail-cat{
  font-size: 12px; font-weight: 600; color: var(--text-secondary);
}
.pf-detail-title{
  font-size: 13.5px; font-weight: 600; color: var(--text-primary);
}
.pf-detail-desc{
  font-size: 12.5px; color: var(--text-secondary);
  line-height: 1.6; margin-bottom: 12px;
}
.pf-detail-section-label{
  font-size: 11px; font-weight: 600; color: var(--text-tertiary);
  text-transform: uppercase; letter-spacing: 0.04em;
  margin-bottom: 6px;
}
.pf-detail-section-count{
  font-size: 11px; font-weight: 500; color: var(--text-tertiary);
  text-transform: none; letter-spacing: 0;
}
.pf-detail-affected{
  margin-bottom: 12px;
}
.pf-detail-chips{
  display: flex; gap: 5px; flex-wrap: wrap;
}
.pf-show-more-btn{
  font-size: 11px; padding: 2px 8px; border-radius: 4px;
  background: rgba(37,99,235,0.08); color: #1d4ed8;
  border: 0.5px solid rgba(37,99,235,0.2);
  cursor: pointer; font-family: inherit; font-weight: 500;
  transition: all .12s;
}
.pf-show-more-btn:hover{
  background: rgba(37,99,235,0.15);
}
.pf-detail-fix{
  display: flex; gap: 8px; align-items: center;
  padding: 8px 12px; background: rgba(34,197,94,0.10);
  border-radius: 6px; font-size: 12px; color: #15803d; font-weight: 500;
  margin-top: 4px;
}

/* ════════════════════════════════════════════════════════════ */
/* v95_p64 (2026-05-05 본부장님): object_risk 상세 메타 카드     */
/*   본부장님 결정: "5 Phase 모두 — 엔터프라이즈 솔루션"          */
/* ════════════════════════════════════════════════════════════ */
.pf-detail-risk-meta{
  display: flex; flex-direction: column; gap: 14px;
  padding: 14px; margin-top: 6px;
  background: rgba(220, 38, 38, 0.04);
  border: 1px solid rgba(220, 38, 38, 0.15);
  border-radius: 8px;
}
/* 신뢰도 게이지 */
.pf-rm-confidence{ display: flex; flex-direction: column; gap: 6px; }
.pf-rm-conf-label{
  font-size: 12px; color: var(--text-secondary);
  display: flex; gap: 8px; align-items: baseline;
}
.pf-rm-conf-label strong{ font-size: 14px; font-weight: 700; }
.pf-rm-conf-low { color: #dc2626; }
.pf-rm-conf-mid { color: #f59e0b; }
.pf-rm-conf-high{ color: #16a34a; }
.pf-rm-conf-bar{
  width: 100%; height: 8px;
  background: rgba(0,0,0,0.06);
  border-radius: 4px; overflow: hidden;
}
.pf-rm-conf-fill{
  height: 100%;
  transition: width .3s ease, background .3s ease;
  border-radius: 4px;
}
/* 검출 패턴 카드 */
.pf-rm-patterns{ display: flex; flex-direction: column; gap: 8px; }
.pf-rm-pattern-card{
  padding: 10px 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border-light);
  border-left: 3px solid #94a3b8;
  border-radius: 6px;
  display: flex; flex-direction: column; gap: 6px;
}
.pf-rm-pat-high   { border-left-color: #dc2626; }
.pf-rm-pat-medium { border-left-color: #f59e0b; }
.pf-rm-pat-low    { border-left-color: #16a34a; }
.pf-rm-pat-head{
  display: flex; gap: 10px; align-items: center;
  font-size: 12.5px;
}
.pf-rm-pat-level{ font-weight: 700; font-size: 11px; }
.pf-rm-pat-label{ color: var(--text-primary); font-weight: 600; }
.pf-rm-pat-desc{
  font-size: 11.5px; color: var(--text-secondary);
  line-height: 1.5;
}
.pf-rm-pat-alt{
  font-size: 11.5px; color: var(--text-primary);
  padding: 6px 10px;
  background: rgba(34, 197, 94, 0.08);
  border-radius: 4px;
}
.pf-rm-pat-matches{ display: flex; flex-wrap: wrap; gap: 6px; }
.pf-rm-pat-match{
  font-family: monospace; font-size: 10.5px;
  padding: 2px 6px;
  background: rgba(0,0,0,0.05);
  border-radius: 3px;
  color: var(--text-secondary);
  max-width: 100%;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.pf-rm-recommendation{
  padding: 10px 12px;
  background: rgba(37, 99, 235, 0.08);
  border-radius: 6px;
  font-size: 12px; font-weight: 500;
  color: var(--text-primary);
}
/* v95_p73 (2026-05-06 본부장님 5번째 통찰): 사용자 친화 안내 */
.pf-rm-friendly-note{
  padding: 12px 14px; margin-top: 8px;
  background: rgba(34, 197, 94, 0.06);
  border: 1px solid rgba(34, 197, 94, 0.2);
  border-radius: 8px;
  font-size: 12.5px; line-height: 1.6;
  color: var(--text-primary);
}
.pf-rm-friendly-list{
  margin: 8px 0 0 0; padding-left: 20px;
  font-size: 11.5px; color: var(--text-secondary);
}
.pf-rm-friendly-list li{ margin: 3px 0; }

.pf-rm-decision-help{
  padding: 8px 12px; margin-bottom: 8px;
  background: rgba(34, 197, 94, 0.08);
  border-left: 3px solid #16a34a;
  border-radius: 4px;
  font-size: 11.5px; color: var(--text-primary);
  line-height: 1.5;
}

.pf-rm-d-explain{
  padding: 10px 12px; margin-top: 6px;
  border-radius: 6px;
  font-size: 11.5px; line-height: 1.6;
}
.pf-rm-d-explain-auto{
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.25);
  color: var(--text-primary);
}
.pf-rm-d-explain-manual{
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  color: #92400e;
}
.pf-rm-d-explain-exclude{
  background: rgba(220, 38, 38, 0.06);
  border: 1px solid rgba(220, 38, 38, 0.2);
  color: var(--text-primary);
}
.pf-rm-d-step{
  display: inline-block; min-width: 18px;
  font-weight: 700; color: #16a34a;
}
.pf-rm-future-hint{
  padding: 8px 12px;
  background: rgba(168, 85, 247, 0.06);
  border: 1px dashed rgba(168, 85, 247, 0.3);
  border-radius: 4px;
  font-size: 11px; color: #7c3aed;
  font-style: italic;
}
/* v95_p65 (2026-05-05 본부장님): 사용자 결정 3-옵션 UI */
.pf-rm-decision{
  display: flex; flex-direction: column; gap: 10px;
  padding: 12px;
  background: rgba(37, 99, 235, 0.04);
  border: 1px solid rgba(37, 99, 235, 0.2);
  border-radius: 8px;
}
.pf-rm-decision-label{
  font-size: 12px; font-weight: 600; color: var(--text-primary);
}
.pf-rm-decision-buttons{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;  /* v95_p75: 8 → 6 컴팩트 */
}
.pf-rm-decision-btn{
  /* v95_p75 (2026-05-06 본부장님): 결정 버튼 컴팩트화 */
  /*   본부장님 호소: "3가지 선택 블록은 조금 줄여도 될 것 같아"     */
  display: flex; flex-direction: column; gap: 2px;
  padding: 7px 8px;  /* 10/12 → 7/8 */
  background: var(--bg-primary);
  border: 1.5px solid var(--border-light);
  border-radius: 6px;
  cursor: pointer;
  transition: all .15s;
  text-align: center;
  position: relative;
}
.pf-rm-decision-btn:hover{
  background: rgba(37, 99, 235, 0.06);
  border-color: rgba(37, 99, 235, 0.3);
}
.pf-rm-decision-btn.active{
  background: rgba(37, 99, 235, 0.1);
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
}
/* v95_p75: active 상태 강화 (선택 결과 명확) */
.pf-rm-decision-btn.active::after{
  content: '✓';
  position: absolute;
  top: -7px; right: -7px;
  width: 20px; height: 20px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; color: white;
  background: #2563eb;
  box-shadow: 0 2px 4px rgba(0,0,0,0.15);
}

/* ════════════════════════════════════════════════════════════ */
/* v95_p76 (2026-05-06 본부장님 추가): 컴팩트 라디오 리스트     */
/*   본부장님 호소:                                            */
/*   "3가지 선택할 수 있는 블록은 조금 줄여도 될 것 같아"        */
/*   "check box 로 선택할 수 있게 해주는것도 좋겠어"            */
/* ════════════════════════════════════════════════════════════ */
.pf-rm-decision-compact{
  /* 컴팩트 결정 영역 — 가로 카드 3개 → 세로 라디오 3줄 */
  padding: 10px 12px;  /* 패딩 약간 축소 */
  gap: 8px;            /* 내부 gap 축소 */
}
.pf-rm-decision-compact .pf-rm-decision-label{
  font-size: 12.5px; font-weight: 700;
  margin-bottom: 2px;
}
.pf-rm-decision-compact .pf-rm-decision-help{
  padding: 6px 10px;
  font-size: 11px;
  margin-bottom: 6px;
}
.pf-rm-radio-list{
  display: flex; flex-direction: column;
  gap: 5px;
}
.pf-rm-radio-row{
  display: flex; align-items: center; gap: 10px;
  padding: 8px 12px;
  background: var(--bg-primary);
  border: 1.5px solid var(--border-light);
  border-radius: 6px;
  cursor: pointer;
  transition: all .15s;
  user-select: none;
}
.pf-rm-radio-row:hover{
  background: rgba(37, 99, 235, 0.05);
  border-color: rgba(37, 99, 235, 0.25);
}
.pf-rm-radio-row.active{
  background: rgba(37, 99, 235, 0.08);
  border-color: #2563eb;
  border-width: 2px;
  padding: 7px 11px;  /* border 보정 */
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12);
}
.pf-rm-radio-auto.active   { background: rgba(34, 197, 94, 0.10);  border-color: #16a34a; box-shadow: 0 0 0 2px rgba(34,197,94,.15); }
.pf-rm-radio-manual.active { background: rgba(168, 85, 247, 0.10); border-color: #7c3aed; box-shadow: 0 0 0 2px rgba(168,85,247,.15); }
.pf-rm-radio-exclude.active{ background: rgba(220, 38, 38, 0.10);  border-color: #dc2626; box-shadow: 0 0 0 2px rgba(220,38,38,.15); }
.pf-rm-radio-input{
  flex-shrink: 0;
  margin: 0;
  width: 16px; height: 16px;
  cursor: pointer;
  accent-color: #2563eb;
}
.pf-rm-radio-auto    .pf-rm-radio-input{ accent-color: #16a34a; }
.pf-rm-radio-manual  .pf-rm-radio-input{ accent-color: #7c3aed; }
.pf-rm-radio-exclude .pf-rm-radio-input{ accent-color: #dc2626; }
.pf-rm-radio-icon{
  flex-shrink: 0;
  font-size: 18px; line-height: 1;
  width: 22px; text-align: center;
}
.pf-rm-radio-text{
  flex: 1; min-width: 0;
  display: flex; flex-direction: column; gap: 1px;
}
.pf-rm-radio-text strong{
  font-size: 12.5px; font-weight: 700;
  color: var(--text-primary);
}
.pf-rm-radio-sub{
  font-size: 10.5px;
  color: var(--text-tertiary);
  line-height: 1.3;
}
.pf-rm-radio-row.active .pf-rm-radio-text strong{
  color: #1e40af;
}
.pf-rm-radio-auto.active    .pf-rm-radio-text strong{ color: #15803d; }
.pf-rm-radio-manual.active  .pf-rm-radio-text strong{ color: #6d28d9; }
.pf-rm-radio-exclude.active .pf-rm-radio-text strong{ color: #b91c1c; }

/* v95_p76: explain 컴팩트화 */
.pf-rm-d-explain-compact{
  padding: 6px 10px !important;
  font-size: 11px !important;
  margin-top: 4px !important;
}
.pf-rm-decision-auto.active::after   { background: #16a34a; }
.pf-rm-decision-manual.active::after { background: #7c3aed; }
.pf-rm-decision-exclude.active::after{ background: #dc2626; }
.pf-rm-decision-auto.active   { background: rgba(34, 197, 94, 0.12); border-color: #16a34a; box-shadow: 0 0 0 2px rgba(34,197,94,.2); }
.pf-rm-decision-manual.active { background: rgba(168, 85, 247, 0.12); border-color: #7c3aed; box-shadow: 0 0 0 2px rgba(168,85,247,.2); }
.pf-rm-decision-exclude.active{ background: rgba(220, 38, 38, 0.12); border-color: #dc2626; box-shadow: 0 0 0 2px rgba(220,38,38,.2); }
.pf-rm-d-icon{ font-size: 15px; line-height: 1; }  /* v95_p75: 18 → 15 컴팩트 */
.pf-rm-d-title{ font-size: 11.5px; font-weight: 700; color: var(--text-primary); }
.pf-rm-d-sub{ font-size: 10px; color: var(--text-tertiary); line-height: 1.25; }

/* 현재 결정 상태 표시 */
.pf-rm-d-status{
  display: flex; gap: 10px; align-items: center;
  padding: 8px 12px;
  background: var(--bg-primary);
  border-radius: 6px;
  font-size: 12px;
  border: 1px solid var(--border-light);
}
.pf-rm-d-status strong{ font-weight: 600; }
.pf-rm-d-status-auto    { color: #16a34a; font-weight: 600; }
.pf-rm-d-status-manual  { color: #7c3aed; font-weight: 600; }
.pf-rm-d-status-exclude { color: #dc2626; font-weight: 600; }

/* v95_p75 (2026-05-06 본부장님): 강화된 결정 표시 */
.pf-rm-d-status-strong{
  padding: 12px 14px;
  border-width: 2px;
  border-radius: 8px;
  font-size: 13px;
  margin-top: 4px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.04);
}
.pf-rm-d-status-strong-auto{
  background: rgba(34, 197, 94, 0.08);
  border-color: #16a34a;
}
.pf-rm-d-status-strong-manual{
  background: rgba(168, 85, 247, 0.08);
  border-color: #7c3aed;
}
.pf-rm-d-status-strong-exclude{
  background: rgba(220, 38, 38, 0.08);
  border-color: #dc2626;
}
.pf-rm-d-status-icon{
  font-size: 24px; line-height: 1;
  flex-shrink: 0;
}
.pf-rm-d-status-text{
  flex: 1;
  display: flex; flex-direction: column; gap: 2px;
}
.pf-rm-d-status-label{
  font-size: 10.5px; color: var(--text-tertiary);
  text-transform: uppercase; letter-spacing: 0.04em;
  font-weight: 600;
}
.pf-rm-d-status-value{
  font-size: 13px; font-weight: 700;
}
.pf-rm-d-clear{
  margin-left: auto;
  padding: 3px 8px;
  background: transparent;
  border: 1px solid var(--border-light);
  border-radius: 4px;
  font-size: 10.5px; color: var(--text-tertiary);
  cursor: pointer;
}
.pf-rm-d-clear:hover{
  background: rgba(0,0,0,0.04);
}
@media (max-width: 700px){
  .pf-rm-decision-buttons{ grid-template-columns: 1fr; }
}
/* 다크 모드 */
.dark .pf-detail-risk-meta{
  background: rgba(220, 38, 38, 0.08);
  border-color: rgba(220, 38, 38, 0.25);
}
.dark .pf-rm-pattern-card{
  background: rgba(255,255,255,0.03);
}

/* 모바일/좁은 화면 — 마스터-디테일 세로 스택 */
@media (max-width: 900px){
  .pf-master-detail{ grid-template-columns: 1fr; }
  .pf-list{ max-height: 240px; }
}

/* ════════════════════════════════════════════════════════════ */
/* v95_p37 본질 2 (2026-05-05 본부장님): 타입 정규화 그룹 분리    */
/* ════════════════════════════════════════════════════════════ */
.norm-group-label{
  display: flex; align-items: center; gap: 7px;
  padding: 8px 14px;
  font-size: 11.5px; font-weight: 600;
  letter-spacing: 0.02em;
  user-select: none;
}
.norm-group-applied{
  background: rgba(34,197,94,0.06);
  color: #15803d;
  border-bottom: 0.5px solid rgba(34,197,94,0.15);
}
.norm-group-collapsible{
  background: var(--bg-primary);
  color: var(--text-secondary);
  border-bottom: 0.5px solid var(--border-light);
  border-top: 0.5px solid var(--border-light);
}
.norm-group-collapsible:hover{
  background: var(--bg-secondary);
  color: var(--text-primary);
}
.norm-group-hint{
  margin-left: auto; font-size: 10.5px; font-weight: 500;
  color: var(--text-tertiary); font-style: italic;
}
.norm-applied{ border-top: none; }
.norm-unapplied{ border-top: none; }

.norm-header{display:flex;align-items:center;gap:8px;padding:10px 14px;cursor:pointer;user-select:none}
.norm-header:hover{background:var(--bg-primary)}
.norm-title{font-size:.82rem;font-weight:600;color:var(--text-primary)}
.norm-badge{font-size:.7rem;font-weight:600;padding:1px 7px;border-radius:99px;background:rgba(37,99,235,.1);color:#1d4ed8}
.norm-desc{font-size:.73rem;color:var(--text-tertiary);margin-left:auto}
.norm-list{border-top:0.5px solid var(--border-light)}
.norm-item{display:flex;align-items:center;justify-content:space-between;padding:9px 14px;cursor:pointer;transition:background .1s;border-bottom:0.5px solid var(--border-light)}
.norm-item:last-child{border-bottom:none}
.norm-item:hover{background:var(--bg-primary)}
.norm-item.active{background:rgba(37,99,235,.04)}
.norm-item-left{display:flex;align-items:flex-start;gap:10px;flex:1}
.norm-chk{width:16px;height:16px;border-radius:4px;border:1.5px solid var(--border-mid);display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px;transition:all .12s}
.norm-chk.on{background:#2563eb;border-color:#2563eb}
.norm-chk svg{width:9px;height:9px;stroke:#fff}
.norm-item-title{font-size:.8rem;font-weight:500;color:var(--text-primary);margin-bottom:3px}
.norm-item-types{display:flex;align-items:center;gap:5px}
.norm-item-level{font-size:.68rem;font-weight:600;padding:2px 7px;border-radius:4px;flex-shrink:0}
.norm-item-level.warn{background:rgba(245,158,11,.1);color:#b45309}
.norm-item-level.info{background:rgba(59,130,246,.08);color:#1d4ed8}
.wiz-nav{display:flex;flex-direction:column;gap:8px;padding:14px 28px;border-top:0.5px solid var(--border-light);background:var(--bg-primary);position:sticky;bottom:0;z-index:10}
.wiz-btn-next{display:inline-flex;align-items:center;gap:6px;padding:8px 20px;border-radius:var(--radius-md);background:#2563eb;color:#fff;border:none;font-size:13px;font-weight:600;cursor:pointer;font-family:var(--font);transition:all .15s;box-shadow:0 1px 3px rgba(37,99,235,.3)}
.wiz-btn-next:hover{background:#1d4ed8;box-shadow:0 2px 8px rgba(37,99,235,.4)}
.wiz-btn-prev{display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:var(--radius-md);background:var(--bg-secondary);color:var(--text-secondary);border:0.5px solid var(--border-mid);font-size:13px;font-weight:500;cursor:pointer;font-family:var(--font);transition:all .15s}
.wiz-btn-prev:hover{background:var(--bg-primary);color:var(--text-primary)}
/* v95_p25 (2026-05-04 본부장님 본질 처방): [새로 시작] 버튼 + 정규화 전체선택/해제 */
.wiz-btn-restart{display:inline-flex;align-items:center;gap:6px;padding:8px 14px;border-radius:var(--radius-md);background:transparent;color:var(--text-tertiary);border:0.5px solid var(--border-mid);font-size:12.5px;font-weight:500;cursor:pointer;font-family:var(--font);transition:all .15s}
.wiz-btn-restart:hover{background:rgba(239,68,68,.06);color:#dc2626;border-color:rgba(239,68,68,.3)}
.norm-bulk-actions{margin-left:auto;display:inline-flex;gap:6px;align-items:center}
.norm-bulk-btn{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:5px;background:transparent;color:var(--text-secondary);border:0.5px solid var(--border-mid);font-size:11.5px;font-weight:500;cursor:pointer;font-family:var(--font);transition:all .12s}
.norm-bulk-btn:hover:not(:disabled){background:var(--bg-primary);color:var(--text-primary);border-color:var(--text-secondary)}
.norm-bulk-btn:disabled{opacity:.4;cursor:not-allowed}
input.err{border-color:var(--text-danger)!important}
.opt-tag { display:inline-flex;align-items:center;padding:1px 6px;border-radius:4px;font-size:.65rem;font-weight:700;margin-right:5px; }
.opt-tag.danger { background:rgba(239,68,68,.12);color:#dc2626;border:0.5px solid rgba(239,68,68,.3); }
.opt-tag.warn   { background:rgba(245,158,11,.12);color:#b45309;border:0.5px solid rgba(245,158,11,.3); }
.drop-opt { border-color:rgba(239,68,68,.25) !important; }
.drop-opt:has(input:checked) { background:rgba(239,68,68,.04) !important; border-color:rgba(239,68,68,.5) !important; }

/* ── 프로파일 빠른 선택 패널 ── */
.profile-quick-panel {
  background: var(--bg-secondary);
  border: 0.5px solid var(--border-mid);
  border-radius: var(--radius-lg);
  padding: 12px 14px;
  margin-bottom: 16px;
}
.pq-header {
  display: flex; align-items: center; gap: 7px;
  font-size: 11.5px; font-weight: 500; color: var(--text-secondary);
  margin-bottom: 10px;
}
.pq-manage {
  margin-left: auto; font-size: 11px; color: var(--text-info);
  background: none; border: none; cursor: pointer; font-family: var(--font);
  padding: 0; transition: opacity .12s;
}
.pq-manage:hover { opacity: .7; }
.pq-list {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px;
}
.pq-item {
  background: var(--bg-primary); border: 0.5px solid var(--border-light);
  border-radius: var(--radius-md); padding: 10px 12px;
  cursor: pointer; transition: all .12s;
  position: relative;  /* v10 #11: 최근 배지 absolute 배치용 */
}
.pq-item:hover {
  border-color: var(--accent-blue); background: var(--bg-info);
  box-shadow: 0 2px 8px rgba(55,138,221,.1);
}
.pq-item.applied {
  border-color: var(--accent-green); background: var(--bg-success);
}
/* v10 #11: 최근 사용 프로파일 하이라이트 (amber/gold)
   - applied(녹색) 와 다른 색으로 구분
   - 사용자가 "마지막에 이거 썼음" 을 즉시 인지 가능
   - 호버/적용 시 자연스럽게 상태 전환 */
.pq-item.recent {
  border-color: #eab308;                       /* amber-500 */
  background: linear-gradient(
    to bottom,
    rgba(234, 179, 8, 0.08) 0%,
    rgba(234, 179, 8, 0.02) 100%
  );
  box-shadow: 0 1px 4px rgba(234, 179, 8, 0.15);
}
.pq-item.recent:hover {
  border-color: var(--accent-blue);            /* hover 시 일반 블루로 */
  background: var(--bg-info);
}
.pq-recent-badge {
  position: absolute;
  top: -6px; right: 8px;
  background: #eab308;                         /* amber-500 */
  color: #fff;
  font-size: 9px; font-weight: 700;
  padding: 2px 6px;
  border-radius: 99px;
  letter-spacing: .04em;
  box-shadow: 0 1px 3px rgba(234, 179, 8, 0.35);
  pointer-events: none;                        /* 클릭 방해 안 함 */
}
.pq-dbs { display: flex; align-items: center; gap: 5px; margin-bottom: 6px; }
.pq-chip {
  display: inline-flex; align-items: center; justify-content: center;
  width: 26px; height: 18px; border-radius: 4px;
  font-size: 9px; font-weight: 700; flex-shrink: 0;
}
.pq-name {
  font-size: 12px; font-weight: 500; color: var(--text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  margin-bottom: 3px;
}
.pq-hosts { font-size: 10.5px; color: var(--text-tertiary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pq-applied {
  display: flex; align-items: center; gap: 4px;
  font-size: 11px; font-weight: 600; color: var(--text-success);
}

/* ═══════════════════════════════════════════════════════════════
   v90.1: DB 선택 가로 배치 + 컴팩트
   ═══════════════════════════════════════════════════════════════ */
.db-horizontal-layout {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 16px;
  align-items: stretch;
  margin-bottom: 12px;
}

.db-side {
  background: var(--bg-secondary, #f8fafc);
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 10px;
  padding: 14px 16px;
}
.db-side-source {
  border-left: 3px solid #3b82f6;
}
.db-side-target {
  border-left: 3px solid #10b981;
}

.db-side-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 10px 0 !important;
  font-size: 13px !important;
  font-weight: 700 !important;
  color: var(--text-primary, #1e293b) !important;
}
.db-side-icon {
  font-size: 16px;
}
.db-side-status {
  margin-left: auto;
  font-size: 11px;
  font-weight: 700;
  color: #14b8a6;
  background: #f0fdfa;
  padding: 2px 8px;
  border-radius: 99px;
  border: 1px solid #5eead4;
  letter-spacing: 0.3px;
}

/* 컴팩트 그리드 (3열, 작은 카드) */
.db-grid-compact {
  display: grid !important;
  grid-template-columns: repeat(3, 1fr) !important;
  gap: 6px !important;
}

.db-card-compact {
  padding: 8px 10px !important;
  min-height: auto !important;
}
.db-card-compact .db-card-name {
  font-size: 11px !important;
  margin-top: 2px !important;
}
.db-card-compact .db-card-abbr-txt {
  font-size: 9px !important;
  margin-top: 1px !important;
}
.db-card-compact .db-card-dot {
  width: 6px !important;
  height: 6px !important;
}
.db-card-compact .db-card-badge {
  font-size: 9px !important;
  padding: 1px 6px !important;
  top: 4px !important;
  right: 4px !important;
}

/* 화살표 */
.db-arrow {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 0 8px;
}
.db-arrow-line {
  flex: 1;
  width: 2px;
  background: linear-gradient(to bottom, transparent, #94a3b8, transparent);
  min-height: 30px;
}
.db-arrow-icon {
  font-size: 24px;
  color: #94a3b8;
  font-weight: 700;
  transform: rotate(0deg);
  background: var(--bg-primary, #fff);
  border: 2px solid #e2e8f0;
  border-radius: 50%;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 모바일 */
@media (max-width: 1024px) {
  .db-horizontal-layout {
    grid-template-columns: 1fr;
    gap: 8px;
  }
  .db-arrow {
    transform: rotate(90deg);
    padding: 8px 0;
  }
  .db-arrow-line {
    min-height: 20px;
  }
  .db-grid-compact {
    grid-template-columns: repeat(4, 1fr) !important;
  }
}


/* ═══════════════════════════════════════════════════════════════
   v90.2: 자주/안쓰는 DB 분리 레이아웃
   ═══════════════════════════════════════════════════════════════ */
.db-split-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  align-items: start;
}

/* ═ 자주 쓰는 DB (큰 카드 3개 세로) ═ */
.db-frequent-col {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.db-card-large {
  position: relative;
  padding: 12px 14px !important;
  background: #fff;
  border: 2px solid var(--border-light, #e2e8f0);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  min-height: 64px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.db-card-large:hover {
  border-color: #94a3b8;
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(0,0,0,0.06);
}
.db-card-large.sel {
  border-color: #14b8a6;
  background: #f0fdfa;
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.1);
}
.db-card-large.cur {
  border-color: #3b82f6;
}
.db-card-large .db-card-dot {
  width: 8px !important;
  height: 8px !important;
  position: absolute;
  top: 10px;
  left: 12px;
}
.db-card-large .db-card-name {
  font-size: 13px !important;
  font-weight: 600 !important;
  margin-top: 0 !important;
  margin-left: 16px;
}
.db-card-large .db-card-abbr-txt {
  font-size: 10px !important;
  margin-top: 2px !important;
  margin-left: 16px;
  opacity: 0.7;
}
.db-card-large .db-card-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  font-size: 9px !important;
  padding: 2px 7px !important;
  background: #14b8a6;
  color: #fff;
  border-radius: 99px;
  font-weight: 700;
}
.db-card-large .db-card-badge.tgt {
  background: #10b981;
}
.db-card-usecount {
  position: absolute;
  bottom: 6px;
  right: 8px;
  font-size: 9px;
  color: #94a3b8;
  font-weight: 600;
}

/* ═ 안 쓰는 DB (얇은 리스트) ═ */
.db-rare-col {
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: var(--bg-tertiary, #f8fafc);
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 8px;
  padding: 4px;
  /* 큰 카드 3개 (각 ~64px + gap 8px*2 = 208px) 와 높이 맞춤 */
  height: 208px;
  overflow-y: auto;
}
.db-rare-col::-webkit-scrollbar {
  width: 6px;
}
.db-rare-col::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

.db-rare-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: #fff;
  border: 1px solid transparent;
  border-radius: 5px;
  cursor: pointer;
  transition: all 0.12s;
  font-size: 12px;
  flex-shrink: 0;
}
.db-rare-item:hover {
  background: #f0fdfa;
  border-color: #5eead4;
}
.db-rare-item.sel {
  background: #f0fdfa !important;
  border-color: #14b8a6 !important;
  font-weight: 600;
}
.db-rare-item.cur {
  border-color: #3b82f6;
  font-weight: 600;
}
.db-rare-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.db-rare-name {
  flex: 1;
  color: var(--text-primary, #1e293b);
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.db-rare-badge {
  font-size: 11px;
  color: #14b8a6;
  font-weight: 700;
  flex-shrink: 0;
}

/* 좁은 화면 */
@media (max-width: 1280px) {
  .db-split-layout {
    grid-template-columns: 1fr;
  }
  .db-rare-col {
    height: auto;
    max-height: 180px;
  }
}

/* ════════════════════════════════════════════════════════════
   v90.11: Step 1 - 컴팩트 카드 + 5박스 동시 표시
   ════════════════════════════════════════════════════════════ */

/* 컴팩트 헤더 카드 (5개) - 클릭 = 전체선택/해제 */
.obj-cards-compact {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: var(--bg-secondary, #f8fafc);
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 8px;
  flex-wrap: wrap;
}

.obj-card-mini {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #fff;
  border: 1.5px solid var(--border-light, #e2e8f0);
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s;
  user-select: none;
  white-space: nowrap;
}
.obj-card-mini:hover {
  border-color: #94a3b8;
  background: #f1f5f9;
}
.obj-card-mini.active {
  background: #f0fdfa;
  border-color: #14b8a6;
  box-shadow: 0 0 0 2px rgba(20, 184, 166, 0.15);
}
.obj-card-mini.partial {
  background: #fffbeb;
  border-color: #f59e0b;
}
.obj-card-mini.empty {
  opacity: 0.5;
  cursor: not-allowed;
}
.obj-card-mini-icon {
  font-size: 14px;
  line-height: 1;
}
.obj-card-mini-label {
  font-weight: 600;
  color: var(--text-primary, #1e293b);
}
.obj-card-mini-count {
  color: var(--text-secondary, #64748b);
  font-size: 11px;
}
.obj-card-mini-sel {
  font-size: 10px;
  font-weight: 700;
  color: #14b8a6;
  background: #ccfbf1;
  padding: 1px 6px;
  border-radius: 99px;
}
.obj-card-mini.active .obj-card-mini-sel {
  background: #14b8a6;
  color: #fff;
}

/* 검색창 (컴팩트 카드 우측) */
.obj-search-wrap {
  margin-left: auto;
  display: flex;
}
.obj-search-input-mini {
  padding: 6px 10px;
  font-size: 12px;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 6px;
  background: #fff;
  width: 160px;
}
.obj-search-input-mini:focus {
  outline: none;
  border-color: #14b8a6;
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.1);
}

/* ━ 5박스 그리드 (v90.74 개편) ━ */
/* 본부장님 호소: "테이블 보는게 너무 불편 — 트리거와 뷰를 위아래 배치하고 테이블 폭 넓게"
 * 
 * 변경 전 (5컬럼 가로):
 *   [테이블 1.5fr] [PROC 1fr] [FN 1fr] [트리거 1fr] [뷰 1fr]
 * 
 * 변경 후 (4컬럼 + 트리거/뷰 같은 컬럼):
 *   [테이블 매우 넓게] [PROC] [FN] [트리거]
 *                                  [뷰   ]   ← 트리거 아래
 */
.obj-boxes-grid {
  display: grid;
  /* 테이블 더 넓게: 2.4fr (이전 1.5fr) — 본부장님 캡처에서 잘림 해결 */
  grid-template-columns: 2.4fr 1fr 1fr 1fr;
  /* v90.74: 트리거(1행)+뷰(2행) 위아래 배치 */
  grid-template-areas:
    "tbl proc func trig"
    "tbl proc func view";
  /* 행 높이: 위아래 박스 합쳐서 한 박스 높이만큼 */
  grid-template-rows: 1fr 1fr;
  gap: 10px;
  margin-bottom: 12px;
}
.obj-box-tables { grid-area: tbl; }
.obj-box-proc   { grid-area: proc; }
.obj-box-func   { grid-area: func; }
.obj-box-trig   { grid-area: trig; }
.obj-box-view   { grid-area: view; }

/* 테이블 박스는 2행 높이 → min/max-height 도 비례 조정 */
.obj-box-tables {
  min-height: 580px;
  max-height: 940px;
}

@media (max-width: 1280px) {
  .obj-boxes-grid {
    /* 좁은 화면: 3컬럼 + 트리거/뷰 한 컬럼에 위아래 */
    grid-template-columns: 1.8fr 1fr 1fr;
    grid-template-areas:
      "tbl proc trig"
      "tbl func view";
  }
}
@media (max-width: 768px) {
  .obj-boxes-grid {
    /* 모바일: 모두 한 줄씩 */
    grid-template-columns: 1fr 1fr;
    grid-template-areas:
      "tbl  tbl"
      "proc func"
      "trig view";
  }
  .obj-box-tables { min-height: 280px; max-height: 460px; }
}

.obj-box {
  background: #fff;
  border: 1.5px solid var(--border-light, #e2e8f0);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all 0.15s;
  min-height: 280px;
  max-height: 460px;
}
.obj-box.box-active {
  border-color: #14b8a6;
  box-shadow: 0 1px 4px rgba(20, 184, 166, 0.15);
}

/* 박스 헤더 - 색상 구분 */
.obj-box-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  background: var(--bg-secondary, #f8fafc);
  border-bottom: 1px solid var(--border-light, #e2e8f0);
  font-size: 12px;
}
.obj-box-tables .obj-box-header { background: #eff6ff; border-bottom-color: #bfdbfe; }
.obj-box-proc   .obj-box-header { background: #fef3c7; border-bottom-color: #fde68a; }
.obj-box-func   .obj-box-header { background: #f3e8ff; border-bottom-color: #e9d5ff; }
.obj-box-trig   .obj-box-header { background: #fee2e2; border-bottom-color: #fecaca; }
.obj-box-view   .obj-box-header { background: #d1fae5; border-bottom-color: #a7f3d0; }

.obj-box-icon {
  font-size: 16px;
  line-height: 1;
}
.obj-box-title {
  font-weight: 700;
  color: var(--text-primary, #1e293b);
}
.obj-box-count {
  color: var(--text-secondary, #64748b);
  font-size: 11px;
}
.obj-box-sel-badge {
  margin-left: auto;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  background: #14b8a6;
  color: #fff;
  border-radius: 99px;
  white-space: nowrap;
}

/* 박스 본문 (스크롤) */
.obj-box-body {
  flex: 1;
  overflow-y: auto;
  padding: 4px;
  background: #fff;
}
.obj-box-body::-webkit-scrollbar {
  width: 6px;
}
.obj-box-body::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}
.obj-box-empty {
  text-align: center;
  padding: 30px 12px;
  color: var(--text-tertiary, #94a3b8);
  font-size: 11px;
  font-style: italic;
}

/* obj-row 컴팩트화 */
.obj-box .obj-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  font-size: 11px;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.1s;
}
.obj-box .obj-row:hover {
  background: var(--bg-tertiary, #f1f5f9);
}
.obj-box .obj-row input[type="checkbox"] {
  width: 13px;
  height: 13px;
  flex-shrink: 0;
  accent-color: #14b8a6;
}
.obj-box .obj-name {
  flex: 1;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 11px;
  color: var(--text-primary, #1e293b);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.obj-box .obj-meta {
  font-size: 10px;
  color: var(--text-tertiary, #94a3b8);
  white-space: nowrap;
}
.obj-box .obj-meta-rows,
.obj-box .obj-meta-size {
  font-variant-numeric: tabular-nums;
}

/* ════════════════════════════════════════════════════════════════════
 * v90.74 (2026-04-28): 테이블 행 가독성 개선
 *   본부장님 호소: "테이블 보는게 너무 불편" - 잘리는 이름 + 0행 의미 없음
 * ════════════════════════════════════════════════════════════════════ */
/* 테이블 행 — title 속성으로 hover 시 풀 이름 보여줌 (template 에서 추가) */
.obj-row-table {
  /* 폰트 약간 확대 + 행 높이 살짝 늘려 가독성 ↑ */
  padding: 6px 8px !important;
}
.obj-row-table .obj-name,
.obj-row-table .obj-tgt-name {
  font-size: 11.5px !important;
}
/* 행 수 (rows) 컬럼 - 우측 정렬 + 색상 강조 */
.obj-row-table .obj-meta-rows {
  font-size: 10.5px !important;
  color: #475569 !important;  /* 기본 dim 보다 진하게 */
  font-weight: 500;
  width: 80px !important;
}
/* 행 수가 0 인 테이블은 흐리게 (의미 없는 빈 테이블) */
.obj-row-table.obj-row-empty {
  opacity: 0.55;
}
.obj-row-table.obj-row-empty .obj-meta-rows {
  color: #94a3b8 !important;
  font-weight: 400;
}
/* 행 수가 큰 테이블 (M/K) 강조 */
.obj-row-table .obj-meta-rows.is-million { color: #0891b2 !important; font-weight: 600; }
.obj-row-table .obj-meta-rows.is-thousand{ color: #0e7490 !important; font-weight: 500; }

/* v90.16: 데이터 정리 옵션 위험 경고 */
.tbl-opt-warning {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  background: #fef3c7;
  border: 1px solid #fbbf24;
  border-left: 3px solid #d97706;
  border-radius: 6px;
  margin-bottom: 8px;
}
.tbl-opt-warn-icon {
  font-size: 18px;
  line-height: 1;
}
.tbl-opt-warn-title {
  font-size: 12px;
  font-weight: 700;
  color: #92400e;
  margin-bottom: 4px;
}
.tbl-opt-warn-desc {
  font-size: 11px;
  color: #78350f;
  line-height: 1.5;
}
.tbl-opt-warn-desc b {
  background: #fde68a;
  padding: 1px 4px;
  border-radius: 3px;
}
.opt-recommend {
  font-size: 9px;
  font-weight: 700;
  color: #047857;
  background: #d1fae5;
  padding: 1px 5px;
  border-radius: 99px;
  margin-left: 4px;
}

/* v90.17: 박스 헤더 클릭 가능 (전체 선택/해제) */
.obj-box-header-clickable {
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}
.obj-box-header-clickable:hover {
  filter: brightness(0.95);
}
.obj-box-toggle-icon {
  margin-left: auto;
  font-size: 14px;
  font-weight: 600;
  color: #14b8a6;
  flex-shrink: 0;
}

/* ════════════════════════════════════════════════════════════════
 * v90.48: 스키마 정책 카드 + 정렬 툴바 + 타겟 미리보기
 * (본부장님 결정 2026-04-27 — underscore 정공법)
 * ════════════════════════════════════════════════════════════════ */
.policy-card {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.04), rgba(168, 85, 247, 0.04));
  border: 1px solid rgba(99, 102, 241, 0.18);
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 14px;
}
.policy-card-header {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 10px; font-weight: 700; color: #4f46e5;
}
.policy-icon { font-size: 16px; }
.policy-title { font-size: 14px; }
.policy-help {
  margin-left: auto; cursor: help;
  font-size: 13px; color: #6b7280;
}
.policy-options {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
@media (max-width: 900px) { .policy-options { grid-template-columns: 1fr; } }
.policy-opt {
  display: flex; gap: 8px; padding: 10px 12px;
  background: #fff; border: 1.5px solid #e2e8f0; border-radius: 8px;
  cursor: pointer; transition: all 0.15s;
}
.policy-opt:hover { border-color: #818cf8; background: #f5f3ff; }
.policy-opt.active {
  border-color: #4f46e5; background: #eef2ff;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.12);
}
.policy-opt input[type="radio"] { margin-top: 3px; flex-shrink: 0; accent-color: #4f46e5; }
.policy-opt-body { flex: 1; min-width: 0; }
.policy-opt-title {
  font-weight: 700; font-size: 12.5px; color: #1f2937; margin-bottom: 3px;
  display: flex; align-items: center; gap: 6px;
}
.policy-recommended {
  font-size: 9px; font-weight: 700;
  padding: 1px 5px; border-radius: 8px;
  background: #16a34a; color: #fff; letter-spacing: 0.05em;
}
.policy-opt-desc { font-size: 11.5px; color: #4b5563; margin-bottom: 2px; font-family: monospace; }
.policy-opt-desc b { color: #4f46e5; }
.policy-opt-note { font-size: 10.5px; color: #6b7280; line-height: 1.35; }
.policy-preview {
  margin-top: 10px; padding: 8px 10px;
  background: rgba(255, 255, 255, 0.6); border-radius: 6px;
  font-size: 11px; color: #4b5563;
  display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
}
.policy-preview-label { font-weight: 600; color: #6b7280; }
.policy-preview-sample code {
  font-family: monospace; padding: 1px 5px; background: #f1f5f9;
  border-radius: 3px; font-size: 10.5px;
}
.policy-preview-tgt { color: #4f46e5; font-weight: 600; }

/* 정렬 툴바 */
.sort-toolbar {
  display: flex; align-items: center; gap: 6px;
  margin-bottom: 10px; padding: 8px 12px;
  background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
  flex-wrap: wrap;
}
.sort-label { font-size: 11.5px; font-weight: 600; color: #6b7280; }
.sort-btn {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 10px; font-size: 11.5px; font-weight: 600;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 6px;
  color: #4b5563; cursor: pointer; transition: all 0.15s;
}
.sort-btn:hover { background: #eef2ff; border-color: #818cf8; color: #4f46e5; }
.sort-btn.active {
  background: #4f46e5; border-color: #4f46e5; color: #fff;
}
.sort-icon { font-size: 9px; opacity: 0.85; }

/* 테이블 행 — 타겟 이름 미리보기 */
.obj-tgt-arrow {
  color: #9ca3af; font-size: 11px; padding: 0 2px;
  flex-shrink: 0;
  width: 14px; text-align: center;
}
.obj-tgt-name {
  font-family: monospace; font-size: 11px; color: #4f46e5;
  font-weight: 600; flex: 1;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* ════════════════════════════════════════════════════════════════════
 * v90.75 (2026-04-28): 박스별 컬럼 헤더 (클릭 정렬)
 *   본부장님 호소: "각 객체별 정렬 + 컬럼 라인 좀 맞추고 행수는 1,000건 단위로"
 * ════════════════════════════════════════════════════════════════════ */
.obj-row-head {
  display: flex; align-items: center; gap: 6px;
  padding: 7px 8px;
  font-size: 10.5px; font-weight: 600; color: #475569;
  border-bottom: 1px solid #e5e7eb;
  background: rgba(241,245,249,0.6);
  position: sticky; top: 0; z-index: 1;
}
.orh-check { width: 13px; flex-shrink: 0; }
.orh-name {
  flex: 1; min-width: 0;
  display: inline-flex; align-items: center; gap: 4px;
}
.orh-arrow { width: 14px; flex-shrink: 0; text-align: center; color: transparent; }
.orh-tgt { flex: 1; min-width: 0; display: inline-flex; align-items: center; gap: 4px; }
.orh-rows { width: 80px; text-align: right; flex-shrink: 0;
            display: inline-flex; align-items: center; justify-content: flex-end; gap: 4px; }
.orh-size { width: 60px; text-align: right; flex-shrink: 0;
            display: inline-flex; align-items: center; justify-content: flex-end; gap: 4px; }
.orh-meta { flex: 0 0 auto;
            display: inline-flex; align-items: center; gap: 4px; color: #6b7280; }

/* 클릭 가능한 컬럼 헤더 */
.orh-name.sortable, .orh-tgt.sortable, .orh-rows.sortable,
.orh-size.sortable, .orh-meta.sortable {
  cursor: pointer; user-select: none;
  transition: color 0.12s;
}
.orh-name.sortable:hover, .orh-tgt.sortable:hover, .orh-rows.sortable:hover,
.orh-size.sortable:hover, .orh-meta.sortable:hover {
  color: #14b8a6;
}
.orh-sort-icon {
  font-size: 9px; opacity: 0.5;
  font-variant: tabular-nums; line-height: 1;
}
.sortable .orh-sort-icon { opacity: 0.7; }
.sortable:hover .orh-sort-icon { opacity: 1; color: #14b8a6; }

/* 컬럼 라인 정렬 — 행과 헤더가 동일 폭/위치 사용 */
.obj-row-table {
  display: flex !important; align-items: center !important;
}
.obj-row-table .obj-name { flex: 1; min-width: 0; }
.obj-row-table .obj-tgt-arrow { width: 14px !important; }
.obj-row-table .obj-tgt-name { flex: 1; min-width: 0; }
.obj-row-table .obj-meta-rows {
  width: 80px !important; text-align: right; flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
.obj-row-table .obj-meta-size {
  width: 60px !important; text-align: right; flex-shrink: 0;
}

/* ════════════════════════════════════════════════════════════ */
/* v95_p66 (2026-05-05 본부장님): 수동 SQL 입력 모달 (Phase 5-1) */
/* ════════════════════════════════════════════════════════════ */
.msql-modal-overlay{
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 9999;
  padding: 30px;
}
.msql-modal{
  background: var(--bg-primary);
  border-radius: 12px;
  width: 100%; max-width: 1200px;
  max-height: 90vh;
  display: flex; flex-direction: column;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
  overflow: hidden;
}
.msql-modal-head{
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-light);
  background: rgba(168, 85, 247, 0.04);
}
.msql-modal-head h3{
  margin: 0; font-size: 15px; font-weight: 700; color: var(--text-primary);
}
.msql-modal-close{
  background: transparent; border: none; cursor: pointer;
  padding: 6px 10px; border-radius: 6px;
  font-size: 16px; color: var(--text-tertiary);
}
.msql-modal-close:hover{ background: rgba(0,0,0,0.05); }
.msql-modal-body{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  padding: 16px 20px;
  flex: 1;
  min-height: 360px;
  overflow: auto;
}
.msql-modal-pane{
  display: flex; flex-direction: column; gap: 6px;
  min-width: 0;
}
.msql-pane-label{
  font-size: 12px; font-weight: 600; color: var(--text-secondary);
  display: flex; gap: 6px; align-items: center;
}
.msql-pane-icon{ font-size: 14px; }
.msql-textarea{
  flex: 1; min-height: 280px;
  padding: 10px 12px;
  font-family: monospace; font-size: 12px; line-height: 1.5;
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  border-radius: 6px;
  resize: vertical;
  color: var(--text-primary);
}
.msql-textarea-readonly{ background: rgba(0,0,0,0.03); }
.msql-textarea-editable:focus{
  outline: none; border-color: #7c3aed;
  box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.15);
}
.msql-validation{
  margin-top: 6px; padding: 8px 12px;
  border-radius: 6px; font-size: 11.5px;
}
.msql-validation.ok{
  background: rgba(34, 197, 94, 0.1);
  color: #15803d;
  border: 1px solid rgba(34, 197, 94, 0.3);
}
.msql-validation.fail{
  background: rgba(220, 38, 38, 0.08);
  color: #b91c1c;
  border: 1px solid rgba(220, 38, 38, 0.3);
}
.msql-validation ul{ margin: 6px 0 0 18px; padding: 0; }

/* 검출 패턴 가이드 */
.msql-pattern-guide{
  padding: 12px 20px;
  background: rgba(168, 85, 247, 0.04);
  border-top: 1px solid var(--border-light);
}
.msql-pg-label{
  font-size: 12px; font-weight: 600;
  color: var(--text-primary); margin-bottom: 6px;
}
.msql-pg-item{
  display: flex; gap: 10px; flex-wrap: wrap;
  font-size: 11.5px; padding: 4px 0;
}
.msql-pg-level{ font-weight: 700; }
.msql-pg-high   { color: #dc2626; }
.msql-pg-medium { color: #f59e0b; }
.msql-pg-low    { color: #16a34a; }
.msql-pg-alt    { color: var(--text-secondary); }

/* 버튼 영역 */
.msql-modal-foot{
  display: flex; gap: 10px; justify-content: flex-end;
  padding: 14px 20px;
  border-top: 1px solid var(--border-light);
  background: var(--bg-secondary);
}
.msql-btn{
  padding: 8px 16px; border-radius: 6px; cursor: pointer;
  font-size: 12.5px; font-weight: 600; display: inline-flex; gap: 6px;
  align-items: center; border: 1px solid;
  transition: all .15s;
}
.msql-btn:disabled{ opacity: .5; cursor: not-allowed; }
.msql-btn-validate{
  background: rgba(37, 99, 235, 0.08);
  border-color: rgba(37, 99, 235, 0.4);
  color: #2563eb;
}
.msql-btn-validate:hover:not(:disabled){
  background: rgba(37, 99, 235, 0.15);
}
.msql-btn-cancel{
  background: transparent;
  border-color: var(--border-light);
  color: var(--text-secondary);
}
.msql-btn-cancel:hover{ background: rgba(0,0,0,0.04); }
.msql-btn-save{
  background: #7c3aed;
  border-color: #7c3aed;
  color: white;
}
.msql-btn-save:hover:not(:disabled){ background: #6d28d9; }

@media (max-width: 900px){
  .msql-modal-body{ grid-template-columns: 1fr; }
}

</style>
