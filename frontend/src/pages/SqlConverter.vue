<template>
  <div class="sql-converter">

    <!-- v91p5: 미연결 → DB 연결 패널 (Validate.vue 와 동일 패턴) -->
    <ConnectPanel v-if="!connector.bothConnected" @connected="onConnected" />

    <!-- v91p5: 연결 후 → DB 정보 헤더 (v91p10: disconnect 이벤트 연결) -->
    <PageHeader v-else :show-db="true" :src-db="connector.source" :tgt-db="connector.target"
                @disconnect="onDisconnect">
      <template #actions>
        <button class="chip" @click="onResetAll" title="모든 입력/결과 초기화">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px">
            <path d="M11 3a5 5 0 1 0 1.5 3.5"/><polyline points="11,1 11,3 13,3"/>
          </svg>
          초기화
        </button>
      </template>
    </PageHeader>

    <!-- ── 재이관 모드 배너 ── -->
    <div v-if="showRemigrateBar" class="sc-remig-bar">
      <div class="sc-remig-bar-left">
        <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:13px;height:13px;flex-shrink:0;color:#2563eb">
          <path d="M2 7a5 5 0 1 0 5-5"/><polyline points="4,1 1,1 1,4"/>
          <line x1="7" y1="9" x2="7" y2="6"/><line x1="5.5" y1="9" x2="8.5" y2="9"/>
        </svg>
        <span class="sc-remig-bar-title">재이관 모드</span>
        <span class="sc-remig-bar-info">
          {{ remigrateQueue.length }}개 오브젝트 대기 중
          <template v-if="remigrateRunning"> — {{ remigrateIdx }}/{{ remigrateTotal }} 변환 중...</template>
        </span>
      </div>
      <div style="display:flex;gap:6px;align-items:center">
        <!-- 진행 현황 -->
        <template v-if="remigrateResults.length">
          <span style="font-size:11px;color:#166534">✓ {{ remigrateResults.filter(r=>r.success).length }}개</span>
          <span v-if="remigrateResults.filter(r=>!r.success).length" style="font-size:11px;color:#dc2626">
            ✗ {{ remigrateResults.filter(r=>!r.success).length }}개
          </span>
        </template>
        <button class="chip chip-run" @click="startRemigrateAll" :disabled="remigrateRunning">
          <span v-if="remigrateRunning" class="vp-spin" style="width:10px;height:10px;border-width:1.5px"></span>
          <svg v-else viewBox="0 0 12 12" fill="currentColor" style="width:9px;height:9px"><polygon points="2,1 10,6 2,11"/></svg>
          {{ remigrateRunning ? `변환 중 (${remigrateIdx}/${remigrateTotal})` : '전체 순차 변환 시작' }}
        </button>
        <!-- 변환 대상 목록 미리보기 -->
        <div class="sc-remig-list-wrap">
          <button class="chip" style="font-size:11px" @click="showRemigrateList=!showRemigrateList">
            목록 {{ showRemigrateList ? '▲' : '▼' }}
          </button>
          <div v-if="showRemigrateList" class="sc-remig-list">
            <div v-for="(item, i) in remigrateQueue" :key="i" class="sc-remig-list-item"
                 :class="{done: remigrateResults.find(r=>r.name===item.name)?.success,
                          fail: remigrateResults.find(r=>r.name===item.name) && !remigrateResults.find(r=>r.name===item.name)?.success}"
                 @click="textSrc=item.ddl; showRemigrateList=false">
              <span style="font-size:10px;font-weight:700;color:var(--text-tertiary)">{{ item.type.substring(0,4) }}</span>
              <span style="font-size:11.5px">{{ item.name }}</span>
              <span v-if="remigrateResults.find(r=>r.name===item.name)?.success" style="color:#16a34a;margin-left:auto">✓</span>
              <span v-else-if="remigrateResults.find(r=>r.name===item.name)" style="color:#dc2626;margin-left:auto">✗</span>
            </div>
          </div>
        </div>
        <button class="chip chip-clear" @click="skipRemigrate" style="font-size:11px">✕ 재이관 종료</button>
      </div>
    </div>

    <!-- v91p5 헤더 (JobMonitor 톤) — 페이지 타이틀 + 모드 탭 -->
    <div class="sc-header">
      <div class="sc-title-wrap">
        <div class="page-title">SQL 쿼리 변환기</div>
        <div class="page-desc">SQL 방언 변환 + AI 튜닝으로 데이터 일치 + 속도 개선 비교</div>
      </div>
      <div class="sc-header-controls">
        <div class="sc-mode-tabs">
          <button class="sc-mode-tab" :class="{active:mode==='text'}"   @click="mode='text'">텍스트</button>
          <button class="sc-mode-tab" :class="{active:mode==='file'}"   @click="mode='file'">파일</button>
          <button class="sc-mode-tab" :class="{active:mode==='folder'}" @click="mode='folder'">폴더</button>
        </div>
      </div>
    </div>

    <!-- v91p5 통합 진행 표시 — 텍스트 변환/파일 일괄/튜닝 모두 -->
    <div v-if="converting || fileBatchRunning || tuning || (mode==='file' && fileBatchProgress.total > 0 && fileBatchProgress.done >= fileBatchProgress.total)"
         class="batch-progress-bar">
      <div class="bp-head">
        <div class="bp-title">
          <span v-if="converting || fileBatchRunning || tuning" class="spinner"></span>
          <span v-else class="bp-done-ico">✓</span>
          <span class="bp-label">
            <template v-if="tuning">🚀 AI 튜닝 진행 중</template>
            <template v-else-if="fileBatchRunning">일괄 변환 중</template>
            <template v-else-if="converting">{{ mode === 'text' ? '텍스트 변환 중' : (mode === 'folder' ? '폴더 변환 중' : '파일 변환 중') }}</template>
            <template v-else>변환 완료</template>
          </span>
          <span class="bp-current" v-if="tuning && tuneStatus">— {{ tuneStatus }}</span>
          <span class="bp-current" v-else-if="fileBatchProgress.currentName">— {{ fileBatchProgress.currentName }}</span>
          <span class="bp-current" v-else-if="converting && convEngine === 'claude'">— Claude AI 호출 중...</span>
          <span class="bp-current" v-else-if="converting && convEngine === 'auto'">— AI 우선 / 실패 시 규칙 기반...</span>
          <span class="bp-current" v-else-if="converting">— 규칙 기반 변환 중...</span>
        </div>
        <div class="bp-stats" v-if="mode === 'file' && fileBatchProgress.total">
          <span class="bp-stat">{{ fileBatchProgress.done }}/{{ fileBatchProgress.total }}</span>
          <span class="bp-stat ok" v-if="fileBatchProgress.ok > 0">✓ {{ fileBatchProgress.ok }}</span>
          <span class="bp-stat fail" v-if="fileBatchProgress.fail > 0">✗ {{ fileBatchProgress.fail }}</span>
          <span class="bp-stat pct">
            {{ fileBatchProgress.total ? Math.round(fileBatchProgress.done / fileBatchProgress.total * 100) : 0 }}%
          </span>
        </div>
      </div>
      <div class="bp-track">
        <!-- 일괄변환은 비율, 텍스트/튜닝은 indeterminate (인디터미닛) -->
        <div v-if="mode === 'file' && fileBatchProgress.total" class="bp-fill"
             :style="{width: (fileBatchProgress.done / fileBatchProgress.total * 100) + '%'}"></div>
        <div v-else class="bp-fill bp-indeterminate"></div>
      </div>
    </div>

    <!-- v91p6: 변환 방식 + 변환 규칙 + 스키마 정책 통합 (호소 ②③) -->
    <!--   상단 PageHeader 에 DB 정보 이미 표시되므로 소스/타겟 셀렉트 제거  -->
    <div class="engine-bar">
      <span class="engine-bar-label">변환 방식</span>
      <label class="engine-chip" :class="[{active:convEngine==='none'},'none']" @click="convEngine='none'">
        <input type="radio" v-model="convEngine" value="none"/>
        — 변환 안함 <span class="chip-desc">원문 그대로 출력</span>
      </label>
      <label class="engine-chip" :class="[{active:convEngine==='auto'},'auto']" @click="convEngine='auto'">
        <input type="radio" v-model="convEngine" value="auto"/>
        ⚡ 자동 <span class="chip-desc">AI 우선, 실패 시 규칙</span>
      </label>
      <label class="engine-chip" :class="[{active:convEngine==='rules'},'rules']" @click="convEngine='rules'">
        <input type="radio" v-model="convEngine" value="rules"/>
        ⚙ 규칙 기반 <span class="chip-desc">내장 규칙만 사용</span>
      </label>
      <label class="engine-chip" :class="[{active:convEngine==='claude'},'claude']" @click="convEngine='claude'">
        <input type="radio" v-model="convEngine" value="claude"/>
        🤖 Claude AI <span class="chip-desc">고품질, API 키 필요</span>
      </label>
      
      <!-- 구분선 -->
      <span class="cfg-divider"></span>
      
      <!-- 변환 규칙 + 스키마 정책 (이전 cfg-bar 에서 이동) -->
      <div class="rule-badge">변환 규칙 <b>{{ ruleCount }}</b>개</div>
      <div class="cfg-pair"
           :title="schemaStrategy === 'underscore' ? 'customer.profile → customer_profile (권장)' :
                   schemaStrategy === 'drop' ? 'customer.profile → profile (기존)' :
                   'customer.profile → customer_db.profile (별도 DB)'">
        <span class="cfg-label">스키마</span>
        <div class="sel-wrap">
          <select v-model="schemaStrategy">
            <option value="underscore">underscore (권장)</option>
            <option value="drop">drop</option>
            <option value="database">database</option>
          </select><Chev/>
        </div>
      </div>
      
      <div v-if="lastMethod" class="method-badge" :class="lastMethod" style="margin-left:auto">
        {{ {'claude-ai':'🤖 Claude AI 변환','rules':'⚙ 규칙 기반 변환',
            'rules_fallback':'⚙ 규칙(AI 폴백)','none':'— 변환 안함'}[lastMethod] || lastMethod }}
      </div>
    </div>

    <!-- API 키 경고 배너 -->
    <div v-if="apiKeyOk===false && (convEngine==='claude'||convEngine==='auto')"
         class="api-warn-bar">
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"
           style="width:14px;height:14px;flex-shrink:0">
        <path d="M8 2L14 14H2L8 2z"/><line x1="8" y1="7" x2="8" y2="10"/>
        <circle cx="8" cy="12" r=".5" fill="currentColor"/>
      </svg>
      Claude AI API 키가 설정되지 않아 규칙 기반으로 변환됩니다.
      <button class="api-warn-btn" @click="$router.push('/settings')">
        시스템 설정 → API 키 입력
      </button>
    </div>

    <!-- API 키 없음 팝업 -->
    <teleport to="body">
      <div v-if="showApiPopup" class="api-popup-overlay" @click.self="showApiPopup=false">
        <div class="api-popup">
          <div class="api-popup-icon">🤖</div>
          <div class="api-popup-title">Claude AI API 키가 설정되지 않았습니다</div>
          <div class="api-popup-desc">
            Claude AI로 변환하려면 Anthropic API 키가 필요합니다.<br>
            지금 설정하거나, 규칙 기반 변환으로 계속할 수 있습니다.
          </div>
          <div class="api-popup-btns">
            <button class="api-popup-btn primary" @click="$router.push('/settings'); showApiPopup=false">
              ⚙ 시스템 설정 → API 키 입력
            </button>
            <button class="api-popup-btn rules" @click="cStore.convEngine='rules'; showApiPopup=false; doConvertFolder()">
              ⚡ 규칙 기반으로 변환 계속
            </button>
            <button class="api-popup-btn cancel" @click="showApiPopup=false">
              취소
            </button>
          </div>
        </div>
      </div>
    </teleport>

    <!-- ══ 텍스트 모드 ══ -->
    <template v-if="mode==='text'">

      <!-- 에디터 -->
      <div class="editor-layout">
        <div class="editor-panel">
          <div class="ep-head src">
            <span>소스 ({{ srcDb }})</span>
            <div style="display:flex;gap:5px">
              <button class="mini-btn" @click="loadSample">샘플</button>
              <button class="mini-btn" @click="textSrc=''">지우기</button>
            </div>
          </div>
          <textarea v-model="textSrc" class="sql-ed" :placeholder="`${srcDb} SQL/DDL을 붙여넣기...`" spellcheck="false"/>
          <div class="ep-foot">{{ lineCount(textSrc) }}줄 · {{ textSrc.length }}자</div>
        </div>

        <div class="mid-panel">
          <!-- v91p11: 변환 중일 때 버튼이 명확히 다른 모습 — 빙글빙글 + 빛나는 효과 -->
          <button class="conv-btn" :class="{converting: converting}"
                  @click="doConvertText" :disabled="converting||!textSrc.trim()">
            <template v-if="converting">
              <!-- v91p15: Windows 설치 스타일 — 부드러운 호 회전 (3/4 원, 끝부분 페이드) -->
              <svg class="conv-spin-ring" viewBox="0 0 24 24" style="width:22px;height:22px">
                <defs>
                  <linearGradient id="convSpinGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%"  stop-color="rgba(255,255,255,0)"/>
                    <stop offset="50%" stop-color="rgba(255,255,255,0.85)"/>
                    <stop offset="100%" stop-color="rgba(255,255,255,1)"/>
                  </linearGradient>
                </defs>
                <!-- 옅은 풀 원 (배경 트랙) -->
                <circle cx="12" cy="12" r="9"
                        fill="none" stroke="rgba(255,255,255,0.25)" stroke-width="2"/>
                <!-- 회전하는 호 (3/4 원, 양 끝 둥글게) -->
                <path d="M 12 3 A 9 9 0 0 1 21 12"
                      fill="none" stroke="url(#convSpinGrad)" stroke-width="2.2" stroke-linecap="round"/>
              </svg>
            </template>
            <template v-else>
              <svg viewBox="0 0 14 14" fill="none" stroke="white" stroke-width="2" style="width:14px;height:14px">
                <line x1="2" y1="7" x2="12" y2="7"/><polyline points="8,3 12,7 8,11"/>
              </svg>
            </template>
            <span class="conv-btn-label">{{ converting ? '변환중' : '변환' }}</span>
          </button>
          <div v-if="converting" class="conv-progress-text">
            <span class="conv-dots"></span>
            <span>잠시만 기다려주세요</span>
          </div>
          <div v-if="!converting && textChanges.length" class="change-cnt ok">{{ textChanges.length }}건 변경</div>
          <div v-if="!converting && textWarnings.length" class="change-cnt warn">{{ textWarnings.length }}건 확인</div>
        </div>

        <div class="editor-panel" style="position:relative">
          <div class="ep-head tgt">
            <span>결과 ({{ tgtDb }})</span>
            <div style="display:flex;gap:5px">
              <button class="mini-btn" @click="copyText"     :disabled="!textResult">복사</button>
              <button class="mini-btn" @click="downloadText" :disabled="!textResult">저장</button>
            </div>
          </div>
          <textarea v-model="textResult" class="sql-ed result" readonly spellcheck="false"/>
          <div class="ep-foot">{{ lineCount(textResult) }}줄 · {{ textResult.length }}자</div>
          
          <!-- v91p10: 변환 중 오버레이 (빙글빙글 + 진행 메시지) -->
          <div v-if="converting" class="conv-overlay">
            <div class="conv-spinner-big"></div>
            <div class="conv-overlay-text">
              <div class="conv-overlay-title">
                <template v-if="convEngine === 'claude'">🤖 Claude AI 변환 중...</template>
                <template v-else-if="convEngine === 'auto'">⚡ 자동 변환 중 (AI 우선)...</template>
                <template v-else>⚙ 규칙 기반 변환 중...</template>
              </div>
              <div class="conv-overlay-sub">잠시만 기다려주세요</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 변환 내역 -->
      <div v-if="textChanges.length||textWarnings.length" class="card" style="margin-top:8px;padding:10px 14px">
        <div class="change-grid">
          <div v-for="c in textChanges"  :key="c" class="ctag ok">✓ {{ c }}</div>
          <div v-for="w in textWarnings" :key="w" class="ctag warn">⚠ {{ w }}</div>
        </div>
      </div>

      <!-- ══ v91 튜닝 섹션 (변환 결과 있을 때 표시) ══ -->
      <div v-if="textResult" class="tune-section">
        <div class="tune-head">
          <div class="tune-title">
            <span class="tune-ico">🚀</span>
            <span>AI 튜닝 — 5개 variant 비교</span>
            <span v-if="tuneResults.length" class="tune-meta">
              ({{ tuneResults.length }}개 생성 · {{ tuneRecommendedCount }}개 추천)
            </span>
          </div>
          <div class="tune-controls">
            <!-- v91p14: 정렬 셀렉트 -->
            <select v-if="tuneResults.length" v-model="tuneSort" class="tune-sel" title="정렬 기준">
              <option value="rank">⭐ 추천 순</option>
              <option value="speed">⚡ 빠른 순</option>
              <option value="cost">💰 cost 낮은 순</option>
              <option value="id"># 생성 순</option>
            </select>
            <select v-model="tuneMeasure" class="tune-sel" :disabled="tuning">
              <option value="explain">EXPLAIN 만</option>
              <option value="execute">실측 만</option>
              <option value="both">EXPLAIN + 실측</option>
            </select>
            <button class="tune-btn" @click="doTune" :disabled="tuning || !textResult">
              <span v-if="tuning" class="spinner"></span>
              <span v-else>🚀</span>
              <span>{{ tuning ? '튜닝 중...' : '튜닝 시작' }}</span>
            </button>
          </div>
        </div>

        <!-- 진행 상태 -->
        <div v-if="tuning" class="tune-progress">
          <span>{{ tuneStatus }}</span>
        </div>

        <!-- 오류 -->
        <div v-if="tuneError" class="tune-error">
          ⚠ {{ tuneError }}
        </div>

        <!-- 기준 (base) 정보 -->
        <div v-if="tuneBaseMetrics && tuneBaseMetrics.execute" class="tune-base">
          <span class="tune-base-label">기준 (base)</span>
          <span class="tune-base-stat">평균 {{ tuneBaseMetrics.execute.avg_ms }}ms</span>
          <span class="tune-base-stat">행 {{ tuneBaseMetrics.execute.rows_returned }}</span>
          <span v-if="tuneBaseMetrics.explain && tuneBaseMetrics.explain.cost"
                class="tune-base-stat">
            cost {{ tuneBaseMetrics.explain.cost.toFixed(2) }}
          </span>
        </div>

        <!-- Variant 카드들 (v91p14: 정렬 적용 + 랭크 표시 + 복사 버튼) -->
        <div v-if="tuneResults.length" class="tune-grid">
          <div v-for="(v, idx) in sortedTuneResults" :key="v.id"
               class="tune-card"
               :class="{recommended: v.recommended, mismatch: v.data_match === false, top: idx===0 && tuneSort==='rank'}">
            <div class="tune-card-head">
              <label class="tune-check">
                <input type="checkbox" v-model="v._selected"/>
                <!-- v91p14: 랭크 표시 (추천 순 정렬일 때 1~5위) -->
                <span class="tune-rank" v-if="tuneSort==='rank'">
                  <span v-if="idx===0" class="rank-medal gold">🥇</span>
                  <span v-else-if="idx===1" class="rank-medal silver">🥈</span>
                  <span v-else-if="idx===2" class="rank-medal bronze">🥉</span>
                  <span v-else class="rank-num">{{ idx+1 }}</span>
                </span>
                <span class="tune-id">#{{ v.id }}</span>
              </label>
              <div class="tune-label">{{ v.label }}</div>
              <div class="tune-badges">
                <span v-if="v.recommended" class="tune-badge ok">⭐ 추천</span>
                <span v-if="v.data_match === true" class="tune-badge ok-soft">✓ 일치</span>
                <span v-if="v.data_match === false" class="tune-badge fail">✗ 불일치</span>
                <span v-if="v.speed_delta !== null && v.speed_delta < 0"
                      class="tune-badge fast">⚡ {{ Math.abs(v.speed_delta) }}% ↓</span>
                <span v-if="v.speed_delta !== null && v.speed_delta > 0"
                      class="tune-badge slow">{{ v.speed_delta }}% ↑</span>
                <!-- v91p14: 복사 버튼 -->
                <button class="tune-card-copy" @click="copyVariantSql(v)" :title="`#${v.id} SQL 복사`">
                  📋 복사
                </button>
              </div>
            </div>
            <div class="tune-card-strategy">
              {{ v.strategy }}
              <!-- v91p17: 전략 설명 툴팁 -->
              <span v-if="strategyHelp(v.strategy)" class="strategy-info"
                    :title="strategyHelp(v.strategy)">ⓘ</span>
            </div>
            <div class="tune-card-reason">{{ v.reason }}</div>
            <div class="tune-card-stats">
              <!-- v91p8: 비교 표시 강화 — base 대비 -->
              <span v-if="v.execute && v.execute.avg_ms !== undefined" class="ts-stat">
                <b>{{ v.execute.avg_ms }}ms</b>
                <span v-if="tuneBaseMetrics?.execute?.avg_ms"
                      class="ts-vs">vs {{ tuneBaseMetrics.execute.avg_ms }}ms (base)</span>
              </span>
              <span v-if="v.execute && v.execute.rows_returned !== undefined" class="ts-stat">
                <b>{{ v.execute.rows_returned }}</b>행
                <span v-if="tuneBaseMetrics?.execute?.rows_returned !== undefined &&
                            tuneBaseMetrics.execute.rows_returned !== v.execute.rows_returned"
                      class="ts-vs ts-warn">
                  (base {{ tuneBaseMetrics.execute.rows_returned }}행과 다름)
                </span>
              </span>
              <span v-if="v.explain && v.explain.cost" class="ts-stat">
                cost <b>{{ v.explain.cost.toFixed(2) }}</b>
                <span v-if="tuneBaseMetrics?.explain?.cost"
                      class="ts-vs">vs {{ tuneBaseMetrics.explain.cost.toFixed(2) }} (base)</span>
              </span>
              <span v-if="v.error" class="ts-stat ts-error">⚠ {{ v.error }}</span>
            </div>
            <!-- v91p8: 진단 정보 (data_match 상세) -->
            <div v-if="v.match_detail" class="tune-card-detail" :class="{
                ok: v.data_match === true,
                fail: v.data_match === false,
                unknown: v.data_match === null
              }">
              {{ v.match_detail }}
            </div>
            <pre class="tune-card-sql">{{ formatSql(v.sql) }}</pre>
          </div>
        </div>

        <!-- 선택된 variant 저장 -->
        <div v-if="tuneResults.length" class="tune-actions">
          <button class="tune-action-btn" @click="saveTuneSelections" :disabled="tuneSelectedCount===0">
            💾 선택한 {{ tuneSelectedCount }}개 저장
          </button>
          <button class="tune-action-btn ghost" @click="copyTuneSelected" :disabled="tuneSelectedCount===0">
            📋 선택한 SQL 복사
          </button>
        </div>
      </div>
    </template>

    <!-- ══ 파일 모드 (폴더 모드와 동일한 레이아웃) ══ -->
    <template v-if="mode==='file'">
      <div class="card folder-panel">
        <div class="folder-layout">

          <!-- 소스 파일 패널 -->
          <div class="folder-box">
            <div class="fb-label">소스 파일</div>
            <div class="fb-path" :class="{selected:files.length}">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px;flex-shrink:0"><path d="M2 1h7l3 3v9H2z"/><polyline points="9,1 9,4 12,4"/></svg>
              <span>{{ files.length ? files.length+'개 파일 선택됨' : '파일을 선택하세요' }}</span>
            </div>
            <div style="display:flex;gap:6px;align-items:center">
              <button class="btn btn-primary" @click="$refs.fileInput.click()">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><path d="M2 1h7l3 3v9H2z"/></svg>
                파일 선택
              </button>
              <input ref="fileInput" type="file" accept=".sql,.ddl,.txt" multiple
                     style="display:none" @change="onFileSelect"/>
              <button v-if="files.length" class="mini-btn" @click="clearFileMode" style="color:var(--text-danger)">초기화</button>
            </div>
            <!-- 파일 목록 -->
            <div v-if="files.length" class="folder-file-list">
              <div class="ffl-header">
                SQL 파일 ({{ files.length }}개)
                <div style="display:flex;gap:5px">
                  <button class="mini-btn" @click="fileSelAll">전체 선택</button>
                  <button class="mini-btn" @click="fileSelNone">해제</button>
                </div>
              </div>
              <label v-for="(f,i) in files" :key="i" class="ffl-row">
                <input type="checkbox" :checked="f.selected" @change="f.selected=!f.selected" style="accent-color:var(--accent-blue)"/>
                <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px;flex-shrink:0;color:var(--text-tertiary)"><path d="M2 1h7l3 3v9H2z"/></svg>
                <span class="f-name" style="flex:1">{{ f.name }}</span>
                <span class="f-size">{{ fmtSize(f.size) }}</span>
                <span v-if="f.converted" class="f-badge ok">완료</span>
              </label>
            </div>
            <div v-else class="ffl-placeholder">
              .sql / .ddl / .txt 파일을 선택하세요
            </div>
          </div>

          <!-- 화살표 -->
          <div class="folder-arrow">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" style="width:22px;height:22px;color:var(--text-tertiary)"><line x1="2" y1="10" x2="18" y2="10"/><polyline points="12,4 18,10 12,16"/></svg>
            <div style="font-size:10px;color:var(--text-tertiary);text-align:center;margin-top:4px">변환</div>
          </div>

          <!-- 타겟(출력) 패널 -->
          <div class="folder-box">
            <div class="fb-label-row">
              <span class="fb-label">타겟 파일 (출력)</span>
              <div class="naming-inline">
                <label class="fo-radio" :class="{active:namingMode==='same'}">
                  <input type="radio" v-model="namingMode" value="same"/> 덮어쓰기
                </label>
                <label class="fo-radio" :class="{active:namingMode==='trans'}">
                  <input type="radio" v-model="namingMode" value="trans"/> _trans 추가
                </label>
              </div>
            </div>
            <!-- 저장 폴더 선택 -->
            <div class="fb-path" :class="{selected:fileTgtFolder}">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px;flex-shrink:0"><path d="M1 3h5l1 2h8v9H1z"/></svg>
              <span>{{ fileTgtFolder || '저장 폴더를 선택하세요 (미선택 시 ZIP 다운로드)' }}</span>
            </div>
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
              <button class="btn" @click="pickFileTgtFolder">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><path d="M1 3h5l1 2h8v9H1z"/></svg>
                저장 폴더 선택
              </button>
              <button v-if="fileTgtFolder" class="mini-btn" @click="fileTgtFolder='';_fileTgtDirHandle=null">✕ 해제</button>
              <button v-if="fileResults.length" class="btn btn-primary" @click="downloadZip">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" style="width:12px;height:12px"><path d="M8 2v8M5 7l3 3 3-3"/><path d="M3 12h10"/></svg>
                ZIP 다운로드
              </button>
              <!-- 툴팁 아이콘 -->
              <div class="tgt-tip-wrap">
                <svg class="tgt-tip-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px"><circle cx="8" cy="8" r="6"/><line x1="8" y1="6" x2="8" y2="8"/><line x1="8" y1="10" x2="8" y2="11"/></svg>
                <div class="tgt-tip-box">
                  저장 폴더 선택 시 → 해당 폴더에 직접 저장<br/>
                  미선택 시 → 완료 후 ZIP 다운로드<br/>
                  파일명: query.sql → <b>{{ namingMode==='trans' ? 'query_trans.sql' : 'query.sql' }}</b>
                </div>
              </div>
            </div>
            <!-- 출력 파일 목록 -->
            <div v-if="fileResults.length" class="folder-file-list">
              <div class="ffl-header">
                출력 파일 ({{ fileResults.length }}개)
                <span class="f-badge ok" style="margin-left:4px">
                  {{ fileResults.reduce((s,r)=>s+r.changes.length,0) }}건 변환
                </span>
              </div>
              <div v-for="(r,i) in fileResults" :key="i" class="ffl-row" style="cursor:pointer" @click="r._open=!r._open">
                <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px;flex-shrink:0;color:var(--text-success)"><polyline points="2,7 5,10 12,4"/></svg>
                <span class="f-name" style="flex:1">{{ r.filename }}</span>
                <span class="f-badge ok">{{ r.changes.length }}건</span>
                <span v-if="r.warnings.length" class="f-badge warn">⚠{{ r.warnings.length }}</span>
                <svg :style="{transform:r._open?'rotate(90deg)':'',transition:'transform .15s'}"
                     viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"
                     style="width:10px;height:10px;margin-left:4px"><polyline points="3,2 9,6 3,10"/></svg>
                <div v-if="r._open" style="width:100%;margin-top:6px" @click.stop>
                  <textarea class="sql-ed result" style="height:160px" :value="r.converted" readonly spellcheck="false"/>
                  <!-- v91: 파일 모드에도 튜닝 버튼 (호소 ④) -->
                  <div style="display:flex;justify-content:flex-end;margin-top:6px;gap:6px">
                    <button class="mini-btn" @click.stop="loadFileToText(r)">
                      📝 텍스트 모드로 → 튜닝
                    </button>
                  </div>
                </div>
              </div>
            </div>
            <div v-else-if="files.length" class="ffl-placeholder">
              변환 실행 후 파일이 여기에 표시됩니다
            </div>
          </div>
        </div><!-- /folder-layout -->

        <!-- 진행바 -->
        <div v-if="folderProgress.total>0" class="folder-progress">
          <div class="fp-bar-wrap">
            <div class="fp-bar" :style="{width:(folderProgress.done/folderProgress.total*100)+'%'}"></div>
          </div>
          <div class="fp-text">{{ folderProgress.done }}/{{ folderProgress.total }} 완료 · {{ folderProgress.changes }}건 변환됨</div>
        </div>
      </div><!-- /card folder-panel -->

      <!-- 하단 액션 바 -->
      <div class="folder-action-bar">
        <div class="fab-left">
          <span class="folder-action-info">
            선택된 파일 <b>{{ files.filter(f=>f.selected!==false).length }}</b>개
          </span>
          <div v-if="folderProgress.total > 0" class="fab-status">
            <div class="fab-bar-wrap">
              <div class="fab-bar-fill ok" :style="{width:(folderProgress.ok/folderProgress.total*100)+'%'}"></div>
              <div class="fab-bar-fill fail" :style="{left:(folderProgress.ok/folderProgress.total*100)+'%',width:(folderProgress.fail/folderProgress.total*100)+'%'}"></div>
            </div>
            <div class="fab-badges">
              <span class="fab-badge total">{{ folderProgress.done }}/{{ folderProgress.total }}</span>
              <span v-if="folderProgress.ok" class="fab-badge ok">✓ {{ folderProgress.ok }}성공</span>
              <span v-if="folderProgress.fail" class="fab-badge fail">✗ {{ folderProgress.fail }}실패</span>
              <span v-if="folderProgress.changes" class="fab-badge changes">⚡ {{ folderProgress.changes }}건</span>
              <span v-if="folderProgress.aiUsed" class="fab-badge ai">🤖 AI {{ folderProgress.aiUsed }}건</span>
              <span v-if="!converting&&folderProgress.done===folderProgress.total&&folderProgress.total>0" class="fab-badge done">완료</span>
              <button v-if="!converting&&convertReport.length>0"
                class="rpt-btn" @click="exportConvertReport('txt')">📄 리포트</button>
              <button v-if="!converting&&convertReport.length>0"
                class="rpt-btn blue" @click="exportConvertReport('html')">HTML</button>
            </div>
          </div>
        </div>
        <div style="display:flex;gap:8px;align-items:center;flex-shrink:0">
          <button v-if="fileResults.length" class="btn" @click="downloadZip">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" style="width:12px;height:12px"><path d="M8 2v8M5 7l3 3 3-3"/><path d="M3 12h10"/></svg>
            ZIP 다운로드
          </button>
          <button class="btn btn-primary" style="padding:8px 24px;font-size:13px"
              @click="doConvertFilesNew"
              :disabled="converting||!files.filter(f=>f.selected!==false).length">
            <span v-if="converting" class="spinner" style="width:13px;height:13px;border-top-color:#fff;display:inline-block;margin-right:5px"></span>
            <svg v-else viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px;margin-right:4px"><line x1="2" y1="8" x2="14" y2="8"/><polyline points="9,3 14,8 9,13"/></svg>
            {{ converting ? '변환 중...' : '→ 일괄 변환' }}
          </button>
        </div>
      </div>
    </template>

    <!-- ══ 폴더 모드 ══ -->
    <template v-if="mode==='folder'">
      <div class="card folder-panel">
        <div class="folder-layout">
          <!-- 소스 폴더 -->
          <div class="folder-box">
            <div class="fb-label">소스 폴더</div>
            <div class="fb-path" :class="{selected:srcFolder}">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px;flex-shrink:0"><path d="M1 3h5l1 2h8v9H1z"/></svg>
              <span>{{ srcFolder || '폴더를 선택하세요' }}</span>
            </div>
            <button class="btn btn-primary" @click="pickSrcFolder">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><path d="M1 3h5l1 2h8v9H1z"/></svg>
              소스 폴더 선택
            </button>
            <div v-if="folderFiles.length" class="folder-file-list">
              <div class="ffl-header">
                SQL 파일 ({{ folderFiles.length }}개)
                <div style="display:flex;gap:5px">
                  <button class="mini-btn" @click="selAll">전체 선택</button>
                  <button class="mini-btn" @click="selNone">해제</button>
                </div>
              </div>
              <label v-for="(f,i) in folderFiles" :key="i" class="ffl-row">
                <input type="checkbox" :checked="f.selected" @change="f.selected=!f.selected" style="accent-color:var(--accent-blue)"/>
                <span class="f-ico">📄</span>
                <span class="f-name" style="flex:1">{{ f.name }}</span>
                <span class="f-size">{{ fmtSize(f.size) }}</span>
                <span v-if="f.converted" class="f-badge ok">완료</span>
              </label>
            </div>
          </div>

          <!-- 화살표 -->
          <div class="folder-arrow">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" style="width:22px;height:22px;color:var(--text-tertiary)"><line x1="2" y1="10" x2="18" y2="10"/><polyline points="12,4 18,10 12,16"/></svg>
            <div style="font-size:10px;color:var(--text-tertiary);text-align:center;margin-top:4px">변환</div>
          </div>

          <!-- 타겟 폴더 -->
          <div class="folder-box">
            <div class="fb-label-row">
              <span class="fb-label">타겟 폴더 (출력)</span>
              <div class="naming-inline">
                <label class="fo-radio" :class="{active:namingMode==='same'}">
                  <input type="radio" v-model="namingMode" value="same"/> 덮어쓰기
                </label>
                <label class="fo-radio" :class="{active:namingMode==='trans'}">
                  <input type="radio" v-model="namingMode" value="trans"/> _trans 추가
                </label>
              </div>
            </div>
            <div class="fb-path" :class="{selected:tgtFolder}">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:14px;height:14px;flex-shrink:0"><path d="M1 3h5l1 2h8v9H1z"/></svg>
              <span>{{ tgtFolder || '저장할 폴더를 선택하세요' }}</span>
            </div>
            <div style="display:flex;align-items:center;gap:8px">
              <button class="btn btn-primary" @click="pickTgtFolder">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><path d="M1 3h5l1 2h8v9H1z"/></svg>
                타겟 폴더 선택
              </button>
              <span style="font-size:10.5px;color:var(--text-tertiary)">
                예: query.sql → {{ namingMode==='trans' ? 'query_trans.sql' : 'query.sql' }}
              </span>
            </div>
            <div v-if="tgtFiles.length" class="folder-file-list">
              <div class="ffl-header">출력 파일 ({{ tgtFiles.length }}개)</div>
              <div v-for="(f,i) in tgtFiles" :key="i" class="ffl-row">
                <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px;flex-shrink:0;color:var(--text-success)"><polyline points="2,7 5,10 12,4"/></svg>
                <span class="f-name" style="flex:1">{{ f.name }}</span>
                <span class="f-size">{{ fmtSize(f.size) }}</span>
              </div>
            </div>
            <div v-else-if="folderFiles.length" class="ffl-placeholder">
              변환 실행 후 파일이 여기에 표시됩니다
            </div>
          </div>
        </div><!-- /folder-layout -->

        <!-- 진행바 -->
        <div v-if="folderProgress.total>0" class="folder-progress">
          <div class="fp-bar-wrap">
            <div class="fp-bar" :style="{width:(folderProgress.done/folderProgress.total*100)+'%'}"></div>
          </div>
          <div class="fp-text">{{ folderProgress.done }}/{{ folderProgress.total }} 완료 · {{ folderProgress.changes }}건 변환됨</div>
        </div>

        <!-- FSA 미지원 안내 -->
        <div v-if="fsaNotSupported" class="warn-banner" style="margin-top:10px">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:12px;height:12px;flex-shrink:0"><path d="M8 2L14 14H2L8 2z"/></svg>
          이 브라우저는 폴더 직접 쓰기를 지원하지 않습니다. 변환 후 ZIP으로 다운로드하세요.
        </div>
      </div><!-- /card folder-panel -->

      <!-- 하단 액션 바 -->
      <div class="folder-action-bar">
        <!-- 왼쪽: 선택 정보 + 상태바 -->
        <div class="fab-left">
          <span class="folder-action-info">
            선택된 파일 <b>{{ folderFiles.filter(f=>f.selected).length }}</b>개
          </span>

          <!-- 상태바: 변환 진행 중이거나 완료 후 -->
          <div v-if="folderProgress.total > 0" class="fab-status">
            <!-- 진행바 -->
            <div class="fab-bar-wrap">
              <div class="fab-bar-fill ok"
                :style="{width: (folderProgress.ok/folderProgress.total*100)+'%'}"></div>
              <div class="fab-bar-fill fail"
                :style="{left:(folderProgress.ok/folderProgress.total*100)+'%',
                         width:(folderProgress.fail/folderProgress.total*100)+'%'}"></div>
            </div>
            <!-- 상태 뱃지들 -->
            <div class="fab-badges">
              <span class="fab-badge total">
                <svg viewBox="0 0 10 10" fill="currentColor" style="width:8px;height:8px"><rect x="1" y="1" width="8" height="8" rx="1"/></svg>
                {{ folderProgress.done }}/{{ folderProgress.total }}
              </span>
              <span v-if="folderProgress.ok" class="fab-badge ok">
                ✓ {{ folderProgress.ok }}성공
              </span>
              <span v-if="folderProgress.fail" class="fab-badge fail">
                ✗ {{ folderProgress.fail }}실패
              </span>
              <span v-if="folderProgress.changes" class="fab-badge changes">
                ⚡ {{ folderProgress.changes }}건 변환
              </span>
              <span v-if="folderProgress.aiUsed" class="fab-badge ai">
                🤖 AI {{ folderProgress.aiUsed }}건
              </span>
              <span v-if="!converting && folderProgress.done===folderProgress.total && folderProgress.total>0"
                class="fab-badge done">완료</span>
            </div>
          </div>
        </div>

        <!-- 오른쪽: 버튼 -->
        <div style="display:flex;gap:6px;align-items:center;flex-shrink:0;flex-wrap:wrap">
          <!-- 완료 후 버튼 -->
          <template v-if="isDone">
            <button v-if="tgtFiles.length" class="btn" @click="downloadFolderZip">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" style="width:12px;height:12px"><path d="M8 2v8M5 7l3 3 3-3"/><path d="M3 12h10"/></svg>
              ZIP
            </button>
            <button v-if="convertReport.length" class="rpt-btn" @click="exportConvertReport('txt')">📄 리포트</button>
            <button v-if="convertReport.length" class="rpt-btn blue" @click="exportConvertReport('html')">HTML</button>
            <button class="btn btn-primary" style="padding:8px 20px;font-size:13px"
                @click="cStore.reset(); doConvertFolder()"
                :disabled="!folderFiles.filter(f=>f.selected).length">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px;margin-right:4px"><line x1="2" y1="8" x2="14" y2="8"/><polyline points="9,3 14,8 9,13"/></svg>
              재실행
            </button>
          </template>
          <!-- 실행 중 버튼 -->
          <template v-else-if="running">
            <button class="ctrl-btn-cv" @click="paused ? unpauseConvert() : pauseConvert()">
              <span v-if="paused">▶ 계속</span>
              <span v-else>⏸ 일시정지</span>
            </button>
            <button class="ctrl-btn-cv stop" @click="stopConvert">⏹ 중단</button>
            <span class="conv-progress-txt">
              {{ paused ? '⏸ 일시정지됨' : '변환 중...' }}
              {{ folderProgress.done }}/{{ folderProgress.total }}
              ({{ pct }}%)
            </span>
          </template>
          <!-- 대기 버튼 -->
          <template v-else>
            <button class="btn btn-primary" style="padding:8px 24px;font-size:13px"
                @click="doConvertFolder"
                :disabled="!folderFiles.filter(f=>f.selected).length">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px;margin-right:4px"><line x1="2" y1="8" x2="14" y2="8"/><polyline points="9,3 14,8 9,13"/></svg>
              → 폴더 일괄 변환
            </button>
          </template>
        </div>
      </div>
    </template>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore }      from '@/store/appStore.js'
import { useConverterStore } from '@/store/converterStore.js'
import { useConnectorStore } from '@/store/connectorStore.js'   // v91p5: DB 연결
import ConnectPanel from '@/components/common/ConnectPanel.vue'  // v91p5
import PageHeader   from '@/components/layout/PageHeader.vue'    // v91p5
import axios from 'axios'

const app    = useAppStore()
const cStore = useConverterStore()
const connector = useConnectorStore()   // v91p5: DB 연결 정보
const route  = useRoute()
const router = useRouter()

// ── 재이관 모드 상태 ──────────────────────────────────────────
const remigrateQueue   = ref([])   // [{name, type, ddl, error}]
const remigrateIdx     = ref(0)
const remigrateTotal   = ref(0)
const remigrateResults = ref([])   // [{name, type, success, converted_ddl, error}]
const remigrateRunning = ref(false)
const showRemigrateBar  = ref(false)
const showRemigrateList = ref(false)
const Chev = { template: '<div class="chev-ico"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px;display:block"><polyline points="2,4 6,8 10,4"/></svg></div>' }

const mode       = ref('text')
const isDragging = ref(false)
const lastMethod = ref('')

// ── v91 튜닝 상태 (로컬: 진행 중 status / error 만) ───────────
const tuning          = ref(false)
const tuneStatus      = ref('')
const tuneError       = ref('')

// store 연동: tuneResults/tuneBaseMetrics/tuneTokensUsed/tuneMeasure
const tuneMeasure     = computed({ get: () => cStore.tuneMeasure,     set: v => cStore.tuneMeasure = v })
const tuneResults     = computed({ get: () => cStore.tuneResults,     set: v => cStore.tuneResults = v })
const tuneBaseMetrics = computed({ get: () => cStore.tuneBaseMetrics, set: v => cStore.tuneBaseMetrics = v })
const tuneTokensUsed  = computed({ get: () => cStore.tuneTokensUsed,  set: v => cStore.tuneTokensUsed = v })

const tuneRecommendedCount = computed(() =>
  tuneResults.value.filter(v => v.recommended).length
)
const tuneSelectedCount = computed(() =>
  tuneResults.value.filter(v => v._selected).length
)

// v91p14: 정렬 + 복사
const tuneSort = ref('rank')   // 'rank' | 'speed' | 'cost' | 'id'

const sortedTuneResults = computed(() => {
  const arr = [...tuneResults.value]
  const mode = tuneSort.value
  
  if (mode === 'rank') {
    // 추천 순: recommended → data_match → speed_delta(빠른 순) → cost
    return arr.sort((a, b) => {
      // 1순위: recommended
      const ra = a.recommended ? 1 : 0
      const rb = b.recommended ? 1 : 0
      if (ra !== rb) return rb - ra
      // 2순위: 데이터 일치 (true > null > false)
      const da = a.data_match === true ? 2 : a.data_match === null ? 1 : 0
      const db = b.data_match === true ? 2 : b.data_match === null ? 1 : 0
      if (da !== db) return db - da
      // 3순위: speed_delta (작을수록 빠름, null 은 뒤로)
      const sa = (a.speed_delta === null || a.speed_delta === undefined) ?  9999 : a.speed_delta
      const sb = (b.speed_delta === null || b.speed_delta === undefined) ?  9999 : b.speed_delta
      if (sa !== sb) return sa - sb
      // 4순위: cost (작을수록 좋음)
      const ca = a.explain?.cost ?? 9e15
      const cb = b.explain?.cost ?? 9e15
      return ca - cb
    })
  }
  if (mode === 'speed') {
    return arr.sort((a, b) => {
      const sa = (a.speed_delta === null || a.speed_delta === undefined) ?  9999 : a.speed_delta
      const sb = (b.speed_delta === null || b.speed_delta === undefined) ?  9999 : b.speed_delta
      return sa - sb
    })
  }
  if (mode === 'cost') {
    return arr.sort((a, b) => (a.explain?.cost ?? 9e15) - (b.explain?.cost ?? 9e15))
  }
  // id (생성 순)
  return arr.sort((a, b) => (a.id || 0) - (b.id || 0))
})

function copyVariantSql(v) {
  const sql = formatSql(v.sql || '')   // v91p17: 포맷된 SQL 복사
  if (!sql) { app.notify('복사할 SQL 없음', 'warn'); return }
  navigator.clipboard?.writeText(sql)
    .then(() => app.notify(`#${v.id} SQL 복사됨 (${sql.length}자)`, 'success'))
    .catch(() => app.notify('복사 실패 — 권한 확인 필요', 'error'))
}

// v91p17: SQL 자동 포맷 (백엔드가 한 줄로 반환하는 경우 대비)
//   본부장님 호소: "튜닝된 쿼리가 줄 바꿈이 없는거 같아"
function formatSql(sql) {
  if (!sql) return ''
  // 이미 줄바꿈이 충분히 있으면 그대로
  if ((sql.match(/\n/g) || []).length >= 4) return sql
  
  // 주요 SQL 키워드 앞에서 줄바꿈
  let s = sql.replace(/\s+/g, ' ').trim()
  const KEYWORDS = [
    'WITH ', 'SELECT ', 'FROM ', 'INNER JOIN ', 'LEFT JOIN ', 'RIGHT JOIN ',
    'OUTER JOIN ', 'CROSS JOIN ', 'JOIN ', 'WHERE ', 'GROUP BY ', 'HAVING ',
    'ORDER BY ', 'LIMIT ', 'UNION ', 'UNION ALL ', 'ON '
  ]
  // 보호: 문자열 리터럴 안의 키워드는 건드리지 않음 (단순 처리)
  KEYWORDS.forEach(kw => {
    // 단어 경계로 매칭, 대소문자 무시
    const re = new RegExp('\\s+' + kw.trim() + '\\b', 'gi')
    s = s.replace(re, '\n' + kw.trim() + ' ')
  })
  // SELECT 컬럼 쉼표 줄바꿈 (간단히 — 첫 SELECT 블록만)
  // SELECT ~ FROM 사이의 콤마 뒤에 줄바꿈
  s = s.replace(/(SELECT[^]*?)(?=\nFROM|$)/i, (match) => {
    return match.replace(/, /g, ',\n    ')
  })
  return s.trim()
}

// v91p17: 튜닝 전략별 설명 사전 (본부장님 호소: "CTE 구조화 옆에 참조표시해서 설명")
const STRATEGY_HELP = {
  'JOIN 순서 최적화': '큰 테이블/필터 강한 테이블을 먼저 처리하여 중간 결과셋 크기를 최소화합니다. 옵티마이저가 실행 계획을 더 효율적으로 수립할 수 있게 됩니다.',
  '인덱스 힌트': 'FORCE INDEX 또는 USE INDEX 로 특정 인덱스를 강제 사용합니다. 옵티마이저가 잘못된 인덱스를 선택할 때 효과적입니다.',
  'WHERE절 선행필터': '가장 선택성 높은 조건(결과 행을 가장 많이 줄이는 조건)을 먼저 평가하여 스캔 범위를 축소합니다.',
  'STRAIGHT_JOIN 사용': 'MySQL 옵티마이저의 조인 순서 자동 결정을 무시하고 FROM 절에 작성된 순서대로 강제 조인합니다. 실행계획 안정화에 사용.',
  '서브쿼리 활용': '필터링/집계를 인라인 뷰(서브쿼리)로 먼저 수행하여 후속 JOIN 의 데이터량을 줄입니다.',
  'CTE 구조화': 'WITH 절(Common Table Expression)로 복잡한 쿼리를 단계별로 분해합니다. 가독성 향상 + MySQL 8.0+ 에서 옵티마이저가 재사용 가능하게 처리.',
  'EXISTS 변환': 'IN/JOIN 을 EXISTS 로 변환하여 서브쿼리 결과 전체를 평가하지 않고 첫 매칭에서 종료. 서브쿼리 결과가 큰 경우 효과적.',
  '윈도우 함수': 'ROW_NUMBER, RANK 등 윈도우 함수로 자체 조인이나 상관 서브쿼리를 대체. 메모리 효율적인 단일 패스 처리.',
  '집계 최적화': 'GROUP BY 컬럼 순서, HAVING vs WHERE 분리, 사전 집계로 데이터량 축소.',
  '커버링 인덱스': 'SELECT 모든 컬럼이 인덱스에 포함되어 테이블 룩업 없이 인덱스만으로 결과 반환.',
  '파티션 프루닝': '파티션 키 조건을 명시하여 불필요한 파티션 스캔 회피.',
  'LIMIT 푸시다운': 'LIMIT 을 서브쿼리 안쪽으로 이동시켜 정렬 대상 데이터량 축소.',
  'NOLOCK 제거': 'MSSQL 의 WITH(NOLOCK) 은 MySQL 에 없으므로 제거. MySQL 의 트랜잭션 격리수준은 READ COMMITTED 가 기본.',
  '날짜 함수 변환': 'DATEADD/DATEDIFF/CONVERT 등 MSSQL 전용 함수를 DATE_ADD/TIMESTAMPDIFF/DATE_FORMAT 등 MySQL 함수로 변환.',
}
function strategyHelp(strategy) {
  if (!strategy) return ''
  // 키워드 부분 매칭
  for (const k in STRATEGY_HELP) {
    if (strategy.includes(k.replace(' 사용','').replace(' 변환','').replace(' 활용',''))) return STRATEGY_HELP[k]
  }
  return STRATEGY_HELP[strategy] || ''
}

// ── store 연동 (화면 이탈 후에도 상태 유지) ─────────────────
const srcDb       = computed({ get: () => cStore.srcDb,      set: v => cStore.srcDb = v })
const tgtDb       = computed({ get: () => cStore.tgtDb,      set: v => cStore.tgtDb = v })
const convEngine  = computed({ get: () => cStore.convEngine,  set: v => cStore.convEngine = v })
const namingMode  = computed({ get: () => cStore.namingMode,  set: v => cStore.namingMode = v })
// v90.48: schema 정책 (본부장님 결정 — 테이블 이관과 일관성)
const schemaStrategy = computed({ get: () => cStore.schemaStrategy, set: v => cStore.schemaStrategy = v })
const folderFiles    = computed(() => cStore.folderFiles)
const tgtFiles       = computed(() => cStore.tgtFiles)
const convertReport  = computed(() => cStore.convertReport)
const folderProgress = computed(() => cStore.folderProgress)
const running     = computed(() => cStore.running)
const paused      = computed(() => cStore.paused)
const runningIdx  = computed(() => cStore.runningIdx)
const isDone      = computed(() => cStore.isDone)
const pct         = computed(() => cStore.pct)
// v91p13 fix: 본부장님 호소 "변환 버튼 눌러도 아무 동작 안 함"
//   원인: converting 이 computed (read-only) 인데 doConvertText 에서 .value=true 쓰려다 에러
//   처방: 텍스트 변환 전용 ref 로 분리 (파일/폴더 모드 cStore.running 과 별도)
const converting  = ref(false)

// v91: 텍스트 모드 — store 바인딩
const textSrc      = computed({ get: () => cStore.textSrc,      set: v => cStore.textSrc = v })
const textResult   = computed({ get: () => cStore.textResult,   set: v => cStore.textResult = v })
const textChanges  = computed({ get: () => cStore.textChanges,  set: v => cStore.textChanges = v })
const textWarnings = computed({ get: () => cStore.textWarnings, set: v => cStore.textWarnings = v })

// v91: 파일 모드 — store 바인딩
const fileInput   = ref(null)
const files       = computed({ get: () => cStore.fileItems, set: v => cStore.fileItems = v })
const fileResults = ref([])
const fileBatchProgress = computed({ get: () => cStore.fileBatchProgress, set: v => cStore.fileBatchProgress = v })
const fileBatchRunning  = computed({ get: () => cStore.fileBatchRunning,  set: v => cStore.fileBatchRunning = v })

// 폴더 모드 (store 연동으로 이동됨)
const srcFolder  = ref('')
const tgtFolder  = ref('')

// API 키 상태
const apiKeyOk   = ref(null)
const showApiPopup = ref(false)  // API 키 없을 때 팝업

async function checkApiKey() {
  try {
    const { data } = await axios.get('/api/v1/settings/')
    // 보안상 실제 키는 안 오고 anthropic_api_key_set(bool) 으로 판단
    apiKeyOk.value = data.anthropic_api_key_set === true
  } catch { apiKeyOk.value = false }
}
const _fileConvertedList = ref([])  // 파일 모드 변환 결과 (ZIP용)
const fileTgtFolder      = ref('')  // 파일 모드 저장 폴더명
let   _fileTgtDirHandle  = null     // 파일 모드 저장 폴더 핸들
const fsaNotSupported= ref(false)
const _srcDirHandle  = ref(null)
const _tgtDirHandle  = ref(null)

const allDbs = [
  {v:'mssql',      n:'SQL Server'},
  {v:'mysql',      n:'MySQL / MariaDB'},
  {v:'oracle',     n:'Oracle'},
  {v:'postgresql', n:'PostgreSQL'},
  {v:'db2',        n:'IBM DB2'},
  {v:'snowflake',  n:'Snowflake'},
  {v:'bigquery',   n:'BigQuery'},
  {v:'sqlite',     n:'SQLite'},
]

const ruleMap = {
  'mysql→mssql':23,'mssql→mysql':14,'mysql→postgresql':20,
  'oracle→mysql':20,'oracle→postgresql':18,'postgresql→mysql':15,
  'db2→mysql':12,'mysql→snowflake':10,'mysql→bigquery':12,
}
const ruleCount = computed(() => ruleMap[`${srcDb.value}→${tgtDb.value}`] || 0)
const lineCount  = s => (s.match(/\n/g)||[]).length + 1
const fmtSize    = n => n > 1024 ? (n/1024).toFixed(1)+'KB' : n+'B'

function clearAll() {
  textSrc.value=''; textResult.value=''; textChanges.value=[]; textWarnings.value=[]
  files.value=[]; fileResults.value=[]; folderFiles.value=[]; tgtFiles.value=[]
  lastMethod.value=''
  sessionStorage.removeItem('sc_src')
  sessionStorage.removeItem('sc_result')
}

// DB 변경 시 선택 저장
watch([srcDb, tgtDb, convEngine], () => {
  localStorage.setItem('sc_srcDb',  srcDb.value)
  localStorage.setItem('sc_tgtDb',  tgtDb.value)
  localStorage.setItem('sc_engine', convEngine.value)
})

// ════════════════════════════════════════════════════════════
// v91 (2026-04-29): SQL 튜닝 — 5개 variant + EXPLAIN + 실측
// ════════════════════════════════════════════════════════════
async function doTune() {
  if (!textResult.value.trim()) {
    app.notify('먼저 변환을 실행하세요', 'warn')
    return
  }
  tuning.value = true
  tuneError.value = ''
  tuneResults.value = []
  tuneBaseMetrics.value = null
  tuneStatus.value = '5개 variant 생성 중... (Claude API 호출)'
  
  // v91p5: target connection — connector store 의 target 자동 사용 (호소 ②)
  //   본부장님 비전: 상단 DB 연결 정보 기반으로 튜닝 실측 자동 진행
  let targetConn = null
  if (connector.target?.host && connector.target?.status === 'ok') {
    targetConn = {
      host:     connector.target.host,
      port:     connector.target.port,
      username: connector.target.username,
      password: connector.target.password,
      database: connector.target.database,
    }
  }
  
  // connector 정보 없으면 EXPLAIN 만 가능 (실측 불가) — 자동 fallback
  if (!targetConn && (tuneMeasure.value === 'execute' || tuneMeasure.value === 'both')) {
    app.notify('타겟 DB 연결 정보 없음 → EXPLAIN 만 측정 (실측 불가)', 'warn')
    tuneMeasure.value = 'explain'
  }
  
  try {
    const { data } = await axios.post('/api/v1/sql-converter/convert-tuned', {
      sql: textSrc.value,
      src_db: srcDb.value,
      tgt_db: tgtDb.value,
      measure: tuneMeasure.value,
      target_conn: targetConn,
      schema_strategy: schemaStrategy.value,    // v91p12: 본부장님 호소 "underscore 정책 적용 안됨"
    }, { timeout: 300000 })  // 5분
    
    if (data.error) {
      tuneError.value = data.error
      tuning.value = false
      return
    }
    
    // _selected 필드 추가 (자동 추천 = 자동 체크)
    tuneResults.value = (data.variants || []).map(v => ({
      ...v,
      _selected: !!v.recommended  // 추천된 것 자동 체크
    }))
    tuneBaseMetrics.value = data.base_metrics
    tuneTokensUsed.value = data.tokens_used || 0
    tuneStatus.value = ''
    
    const recCount = tuneResults.value.filter(v => v.recommended).length
    app.notify(
      `튜닝 완료 — ${tuneResults.value.length}개 생성, ${recCount}개 자동 추천 (${data.total_ms}ms)`,
      'success'
    )
  } catch (e) {
    tuneError.value = '튜닝 실패: ' + (e.response?.data?.detail || e.message)
    tuneStatus.value = ''
  } finally {
    tuning.value = false
  }
}

function saveTuneSelections() {
  const selected = tuneResults.value.filter(v => v._selected)
  if (!selected.length) return
  
  // KB 누적 — localStorage 에 저장 (추후 backend KB API 연동 가능)
  const kbKey = 'sc_tune_kb'
  let kb = []
  try {
    const stored = localStorage.getItem(kbKey)
    if (stored) kb = JSON.parse(stored)
  } catch (e) {}
  
  const now = new Date().toISOString()
  for (const v of selected) {
    kb.push({
      saved_at: now,
      src_db: srcDb.value,
      tgt_db: tgtDb.value,
      original_sql: textSrc.value.substring(0, 500),
      variant_label: v.label,
      variant_strategy: v.strategy,
      variant_sql: v.sql,
      speed_delta: v.speed_delta,
      data_match: v.data_match,
      reason: v.reason,
    })
  }
  // 최대 100개 유지 (오래된 것 제거)
  if (kb.length > 100) kb = kb.slice(-100)
  localStorage.setItem(kbKey, JSON.stringify(kb))
  
  app.notify(`${selected.length}개 variant 저장됨 (KB 총 ${kb.length}개)`, 'success')
}

function copyTuneSelected() {
  const selected = tuneResults.value.filter(v => v._selected)
  if (!selected.length) return
  const txt = selected.map(v => 
    `-- [${v.label}] ${v.strategy}\n-- 속도: ${v.speed_delta}% / 일치: ${v.data_match}\n${v.sql}`
  ).join('\n\n-- ═══════════════════\n\n')
  navigator.clipboard?.writeText(txt)
  app.notify(`${selected.length}개 variant SQL 복사됨`, 'success')
}

// ── 텍스트 변환 ──
async function doConvertText() {
  if (!textSrc.value.trim()) return
  window.__sc_convStart = Date.now()    // v91p6: 시작 시각 기록 (진행바 최소 표시)
  converting.value=true; lastMethod.value=''
  try {
    // none: 변환 없이 원문 그대로
  if (convEngine.value === 'none') {
    textResult.value  = textSrc.value
    textChanges.value = []
    textWarnings.value= ['변환 안함 모드 — 원문 그대로 출력됩니다.']
    lastMethod.value  = 'none'
    converting.value  = false
    return
  }
  // ── 대용량 텍스트 처리: 80KB 초과 시 규칙 기반 강제 ──────────────
  const sqlBytes = new TextEncoder().encode(textSrc.value).length
  const isLargeText = sqlBytes > 80 * 1024  // 80KB
  if (isLargeText && (convEngine.value === 'claude' || convEngine.value === 'auto')) {
    app.notify(
      `SQL이 ${Math.round(sqlBytes/1024)}KB입니다. 80KB 초과로 규칙 기반 변환합니다.`,
      'warn'
    )
  }
  const endpoint = (convEngine.value === 'rules' || isLargeText)
      ? '/api/v1/sql-converter/convert'
      : '/api/v1/sql-converter/convert-ai'
    const { data } = await axios.post(endpoint, {
      sql: textSrc.value, src_db: srcDb.value, tgt_db: tgtDb.value, engine: convEngine.value, schema_strategy: schemaStrategy.value
    }, { timeout: 120000 })
    textResult.value  = data.converted
    textChanges.value = data.changes  || []
    textWarnings.value= data.warnings || []
    lastMethod.value  = data.method   || 'rules'
    const lbl = {'claude-ai':'🤖 Claude AI','rules':'⚙ 규칙 기반','rules_fallback':'⚙ 규칙(폴백)'}[lastMethod.value] || lastMethod.value
    app.notify(`변환 완료 [${lbl}] — ${textChanges.value.length}건 변경`, 'success')
    sessionStorage.setItem('sc_src',    textSrc.value)
    sessionStorage.setItem('sc_result', textResult.value)
  } catch(e) { app.notify('변환 실패: '+e.message,'error') }
  finally {
    // v91p6: 진행바 최소 800ms 표시 (너무 빨리 끝나면 못 봄)
    const elapsed = Date.now() - (window.__sc_convStart || 0)
    if (elapsed < 800) await new Promise(r => setTimeout(r, 800 - elapsed))
    converting.value=false
  }
}

function copyText()     { navigator.clipboard?.writeText(textResult.value); app.notify('복사됨','success') }
function downloadText() {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([textResult.value],{type:'text/plain;charset=utf-8'}))
  a.download = `converted_${srcDb.value}_to_${tgtDb.value}.sql`; a.click()
}

// ── 파일 모드 ──
function _wrapFile(f) {
  // File 객체를 reactive 래퍼로 감싸기
  return { file: f, name: f.name, size: f.size, selected: true, converted: false }
}
function onFileSelect(e) {
  const newFiles = Array.from(e.target.files)
    .filter(f => /\.(sql|ddl|txt)$/i.test(f.name))
    .map(f => _wrapFile(f))
  newFiles.forEach(f => { if (!files.value.find(ex=>ex.name===f.name)) files.value.push(f) })
  e.target.value = ''
}
function fileSelAll()  { files.value = files.value.map(f => ({...f, selected:true})) }
function fileSelNone() { files.value = files.value.map(f => ({...f, selected:false})) }
function onDrop(e) { isDragging.value=false; addFiles(Array.from(e.dataTransfer.files).filter(f=>/\.(sql|ddl|txt)$/i.test(f.name))) }
function addFiles(nf) { nf.forEach(f => { if (!files.value.find(ex=>ex.name===f.name)) files.value.push(_wrapFile(f)) }) }

// ── 파일 모드: 폴더 모드와 동일하게 namingMode 적용 ──
function clearFileMode() {
  files.value = []
  fileResults.value = []
  _fileConvertedList.value = []
  folderProgress.value = { total:0, done:0, changes:0, ok:0, fail:0, aiUsed:0 }
}

async function pickFileTgtFolder() {
  if (!window.showDirectoryPicker) {
    fsaNotSupported.value = true
    app.notify('이 브라우저는 폴더 직접 쓰기를 지원하지 않습니다. ZIP으로 다운로드하세요.', 'warn')
    return
  }
  try {
    _fileTgtDirHandle = await window.showDirectoryPicker({ mode: 'readwrite' })
    fileTgtFolder.value = _fileTgtDirHandle.name
    app.notify('저장 폴더 선택됨: ' + _fileTgtDirHandle.name, 'success')
  } catch(e) {
    if (e.name !== 'AbortError') app.notify('폴더 접근 실패', 'error')
  }
}

async function doConvertFilesNew() {
  const selected = files.value.filter(f => f.selected !== false)
  if (!selected.length) return

  // 748KB 같은 대용량 파일 + Claude AI 선택 시 사전 경고
  const bigFiles = selected.filter(f => f.size > 80 * 1024)
  if (bigFiles.length && (convEngine.value === 'claude' || convEngine.value === 'auto')) {
    app.notify(
      `${bigFiles.length}개 파일(${bigFiles.map(f=>f.name).join(', ')})이 80KB를 초과합니다. 규칙 기반으로 자동 처리됩니다.`,
      'warn'
    )
  }

  converting.value = true
  folderProgress.value = { total: selected.length, done: 0, changes: 0, ok: 0, fail: 0, aiUsed: 0 }
  const allConverted = []
  for (const f of selected) {
    try {
      const content_txt = await (f.file || f).text()
      // ── 파일별 엔진 결정: 대용량(80KB↑)이면 규칙 기반 강제 ──────────
      // isLarge를 엔드포인트 분기에 반드시 적용 (748KB 오류 원인 수정)
      const fileSizeBytes = new TextEncoder().encode(content_txt).length
      const isLarge = fileSizeBytes > 80 * 1024
      const useAI   = (convEngine.value === 'claude' || convEngine.value === 'auto') && !isLarge
      const endpoint = useAI
        ? '/api/v1/sql-converter/convert-ai'
        : '/api/v1/sql-converter/convert'
      if (isLarge && (convEngine.value === 'claude' || convEngine.value === 'auto')) {
        const kb = Math.round(fileSizeBytes / 1024)
        console.info(`[SQL변환] ${f.name} (${kb}KB) 대용량 → 규칙 기반 처리`)
      }
      let converted, changes = [], warnings = [], method = 'none'
      if (convEngine.value === 'none') {
        converted = content_txt
      } else {
        const { data } = await axios.post(endpoint, {
          sql: content_txt, src_db: srcDb.value, tgt_db: tgtDb.value, engine: convEngine.value, schema_strategy: schemaStrategy.value
        }, { timeout: 120000 })  // 대용량 파일 대비 2분 타임아웃
        converted = data.converted || content_txt
        changes = data.changes || []
        warnings = data.warnings || []
        method = data.method || 'rules'
      }
      const outName = namingMode.value === 'trans'
        ? f.name.replace(/(\.[^.]+)$/, '_trans$1')
        : f.name
      allConverted.push({ name: outName, content: converted })
      fileResults.value.push({ filename: outName, converted, changes, warnings, method, _open: false })
      f.converted = true  // 래퍼 객체 프로퍼티 직접 수정 (반응형)
      // 저장 폴더 선택된 경우 직접 저장
      if (_fileTgtDirHandle) {
        try {
          const oh = await _fileTgtDirHandle.getFileHandle(outName, { create: true })
          const wr = await oh.createWritable()
          await wr.write(converted)
          await wr.close()
        } catch(e) { /* 저장 실패 시 무시 - ZIP으로 다운로드 가능 */ }
      }
      folderProgress.value.done++
      folderProgress.value.ok++
      folderProgress.value.changes += changes.length
      if (method === 'claude-ai') folderProgress.value.aiUsed++
    } catch(e) {
      folderProgress.value.done++
      folderProgress.value.fail++
      convertReport.value.push({ name:f.name, ok:false, method:'error', changes:0, error:e.message||'오류' })
    }
  }
  converting.value = false
  app.notify(`${allConverted.length}개 파일 변환 완료`, 'success')
  // ZIP 다운로드 준비
  _fileConvertedList.value = allConverted
}

async function doConvertFiles() {
  // v91 (2026-04-29): 일괄 변환 진행 표시 (본부장님 호소 ③)
  const total = files.value.length
  if (!total) { app.notify('파일이 없습니다', 'warn'); return }
  
  fileBatchRunning.value = true
  fileBatchProgress.value = { total, done: 0, ok: 0, fail: 0, currentName: '' }
  converting.value=true
  
  try {
    const contents = await readFiles(files.value.map(f => f.file || f))
    const fileEndpoint = convEngine.value === 'none'
      ? '/api/v1/sql-converter/convert-files'
      : convEngine.value === 'claude' || convEngine.value === 'auto'
        ? '/api/v1/sql-converter/convert-files-ai'
        : '/api/v1/sql-converter/convert-files'
    
    fileBatchProgress.value.currentName = `${total}개 파일 변환 중...`
    
    const { data } = await axios.post(fileEndpoint, {
      files: contents, src_db: srcDb.value, tgt_db: tgtDb.value,
      engine: convEngine.value
    })
    fileResults.value = data.files.map(r=>({...r, _open:false}))
    
    // 진행 통계 업데이트
    const okCount = data.files.filter(r => !r.error).length
    const failCount = data.files.filter(r => r.error).length
    fileBatchProgress.value = {
      total, done: total, ok: okCount, fail: failCount, currentName: ''
    }
    
    app.notify(`${data.total_files}개 변환 완료 — 성공 ${okCount} / 실패 ${failCount}`, failCount ? 'warn' : 'success')
  } catch(e) {
    fileBatchProgress.value.fail = total
    app.notify('변환 실패: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    converting.value=false
    fileBatchRunning.value = false
  }
}

// v91p5: DB 연결 완료 핸들러 (Validate 와 동일 패턴)
function onConnected() {
  app.notify('DB 연결 완료 — 이제 변환 + 튜닝 가능', 'success')
}

// v91p10: DB 접속 해제 (다른 DB 테스트 위해)
function onDisconnect() {
  // connector store reset — Validate 등 다른 화면도 동시 영향
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
  app.notify('DB 연결 해제 완료 — 다시 연결하세요', 'info')
}

// v91: 화면 전체 초기화 (본부장님 호소 ①)
function onResetAll() {
  if (textSrc.value || textResult.value || files.value.length || tuneResults.value.length || folderFiles.value.length) {
    if (!confirm('모든 입력과 결과가 초기화됩니다. 계속할까요?')) return
  }
  cStore.resetAll()
  fileResults.value = []
  app.notify('초기화 완료', 'success')
}

// v91: 파일 결과를 텍스트 모드로 가져오기 (튜닝하기 위해)
function loadFileToText(r) {
  // 원본 SQL 가져오기
  const origFile = files.value.find(f => (f.name || f.file?.name) === r.filename)
  if (!origFile) { app.notify('원본 파일을 찾을 수 없습니다', 'warn'); return }
  
  // 원본 내용 읽기
  const file = origFile.file || origFile
  const reader = new FileReader()
  reader.onload = (e) => {
    textSrc.value = e.target.result
    textResult.value = r.converted
    textChanges.value = r.changes || []
    textWarnings.value = r.warnings || []
    mode.value = 'text'
    app.notify(`'${r.filename}' 텍스트 모드로 로드됨 — 튜닝 버튼 사용 가능`, 'success')
  }
  reader.readAsText(file)
}

async function downloadZip() {
  // 파일 모드: 이미 변환된 결과 사용
  if (mode.value === 'file' && _fileConvertedList.value.length) {
    const resp = await axios.post('/api/v1/sql-converter/convert-files/download',
      { files: _fileConvertedList.value.map(f=>({name:f.name,content:f.content})),
        src_db: srcDb.value, tgt_db: tgtDb.value, schema_strategy: schemaStrategy.value }, { responseType:'blob' })
    const cd = resp.headers['content-disposition']||''
    const name = cd.match(/filename="(.+?)"/)?.[1]||'converted.zip'
    const a = document.createElement('a'); a.href=URL.createObjectURL(new Blob([resp.data])); a.download=name; a.click()
    return
  }
  // 기존 방식
  const contents = await readFiles(files.value.map(f => f.file || f))
  const resp = await axios.post('/api/v1/sql-converter/convert-files/download',
    { files: contents, src_db: srcDb.value, tgt_db: tgtDb.value, schema_strategy: schemaStrategy.value }, { responseType:'blob' })
  const cd   = resp.headers['content-disposition']||''
  const name = cd.match(/filename="(.+?)"/)?.[1]||'converted.zip'
  const a = document.createElement('a'); a.href=URL.createObjectURL(new Blob([resp.data])); a.download=name; a.click()
}

// ── 폴더 모드 ──
async function pickSrcFolder() {
  if (!window.showDirectoryPicker) { fsaNotSupported.value=true; return }
  try {
    _srcDirHandle.value = await window.showDirectoryPicker({ mode:'read' })
    srcFolder.value = _srcDirHandle.value.name
    await loadFolderFiles()
  } catch(e) { if (e.name!=='AbortError') app.notify('폴더 접근 실패','error') }
}
async function pickTgtFolder() {
  if (!window.showDirectoryPicker) { fsaNotSupported.value=true; return }
  try {
    _tgtDirHandle.value = await window.showDirectoryPicker({ mode:'readwrite' })
    tgtFolder.value = _tgtDirHandle.value.name
    app.notify('타겟 폴더 선택됨','success')
  } catch(e) { if (e.name!=='AbortError') app.notify('폴더 접근 실패','error') }
}
async function loadFolderFiles() {
  cStore.folderFiles=[]
  if (!_srcDirHandle.value) return
  for await (const [name, handle] of _srcDirHandle.value.entries()) {
    if (handle.kind==='file' && /\.(sql|ddl|txt)$/i.test(name)) {
      const file = await handle.getFile()
      cStore.folderFiles.push({ name, size:file.size, selected:true, handle, converted:false })
    }
  }
  app.notify(`${folderFiles.value.length}개 SQL 파일 발견`, 'success')
}
function selAll()  { cStore.folderFiles.forEach(f=>f.selected=true) }
function selNone() { cStore.folderFiles.forEach(f=>f.selected=false) }

async function doConvertFolder() {
  const selected = cStore.folderFiles.filter(f => f.selected)
  if (!selected.length) return

  // Claude AI 선택 시 API 키 실시간 확인
  if (cStore.convEngine === 'claude' || cStore.convEngine === 'auto') {
    await checkApiKey()
    if (apiKeyOk.value === false) {
      showApiPopup.value = true
      return
    }
  }
  const result = await cStore.runConvert(selected, _tgtDirHandle.value)
  if (result) {
    // ZIP 다운로드
    const resp = await axios.post('/api/v1/sql-converter/convert-files/download',
      { files: result, src_db: cStore.srcDb, tgt_db: cStore.tgtDb, schema_strategy: cStore.schemaStrategy }, { responseType: 'blob' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([resp.data]))
    a.download = 'converted_folder.zip'; a.click()
  }
  if (!cStore.stopped) {
    app.notify(`${cStore.folderProgress.ok}개 파일 변환 완료`, 'success')
  }
}

function pauseConvert()  { cStore.pause() }
function unpauseConvert(){ cStore.unpause() }
function stopConvert()   { cStore.stop() }
async function downloadFolderZip() {
  const contents = await Promise.all(
    folderFiles.value.filter(f=>f.selected&&f.converted).map(async f => {
      const file=await f.handle.getFile()
      return { name:f.name, content:await file.text() }
    })
  )
  const resp = await axios.post('/api/v1/sql-converter/convert-files/download',
    { files:contents, src_db:srcDb.value, tgt_db:tgtDb.value, schema_strategy:schemaStrategy.value }, { responseType:'blob' })
  const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([resp.data])); a.download='converted_folder.zip'; a.click()
}

function exportConvertReport(fmt='txt') {
  const now = new Date().toLocaleString('ko-KR')
  const rpt = convertReport.value
  const total   = rpt.length
  const okList  = rpt.filter(r=>r.ok)
  const errList = rpt.filter(r=>!r.ok)
  const aiList  = rpt.filter(r=>r.method==='claude-ai')
  const SEP = '='.repeat(70)

  if (fmt === 'txt') {
    const L = []
    L.push('DataBridge Studio — SQL 변환 리포트')
    L.push(SEP)
    L.push(`생성: ${now}`)
    L.push(`소스 DB: ${srcDb.value}  →  타겟 DB: ${tgtDb.value}`)
    L.push(`변환 방식: ${ {'claude':'🤖 Claude AI','auto':'⚡ 자동(AI우선)','rules':'⚙ 규칙 기반','none':'— 변환 안함'}[convEngine.value] || convEngine.value }`)
    L.push('')
    L.push(`총 ${total}개   ✓ 성공: ${okList.length}   ✗ 실패: ${errList.length}   🤖 AI사용: ${aiList.length}`)
    L.push(SEP)
    L.push('')
    rpt.forEach((r, i) => {
      const num = String(i+1).padStart(2,'0')
      const icon = r.ok ? '✓' : '✗'
      const method = {'claude-ai':'🤖 AI','rules':'⚙ 규칙','rules_fallback':'⚙ 규칙(폴백)','none':'— 원본','error':'✗ 오류'}[r.method]||r.method
      L.push(`${num}. [${icon}] ${r.name}`)
      if (r.outName && r.outName !== r.name) L.push(`    → ${r.outName}`)
      L.push(`    방식: ${method}   변환: ${r.changes}건`)
      if (r.error) L.push(`    오류: ${r.error}`)
      L.push('')
    })
    L.push(SEP)
    L.push('END')
    const blob = new Blob([L.join('\n')], {type:'text/plain;charset=utf-8'})
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `convert_report_${new Date().toISOString().slice(0,10)}.txt`
    a.click(); URL.revokeObjectURL(a.href)
  } else {
    const _s = '<'+'style>'; const _es = '<'+'/style>'
    const _eb = '<'+'/body><'+'/html>'
    const rows = rpt.map((r,i) => {
      const ok = r.ok
      const method = {'claude-ai':'🤖 AI','rules':'⚙ 규칙','rules_fallback':'⚙ 규칙(폴백)','none':'— 원본','error':'✗ 오류'}[r.method]||r.method
      return `<tr class="${ok?'ok-row':'err-row'}">
        <td>${i+1}</td>
        <td>${r.name}</td>
        <td>${r.outName||r.name}</td>
        <td><span class="mbadge ${r.method}">${method}</span></td>
        <td>${r.changes}건</td>
        <td>${r.error||'✓'}</td></tr>`
    }).join('')
    const html = '<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">'
      + '<title>SQL 변환 리포트</title>'
      + _s + `
        *{box-sizing:border-box}body{font-family:'Malgun Gothic',sans-serif;font-size:12px;margin:0;padding:16px;background:#f3f4f6}
        h1{font-size:16px;margin:0 0 4px}.meta{color:#6b7280;font-size:11px;margin-bottom:12px}
        table{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;border:1px solid #e5e7eb}
        th{background:#f9fafb;padding:8px 10px;text-align:left;font-size:11px;color:#6b7280;font-weight:600;border-bottom:1px solid #e5e7eb}
        td{padding:6px 10px;border-bottom:1px solid #f3f4f6;font-size:11px}
        tr:last-child td{border-bottom:none}.ok-row td:first-child{color:#059669}.err-row td:first-child{color:#dc2626}
        .mbadge{font-size:10px;padding:2px 6px;border-radius:8px;font-weight:600}
        .mbadge.claude-ai{background:rgba(139,92,246,.15);color:#6d28d9}
        .mbadge.rules{background:rgba(59,130,246,.1);color:#1d4ed8}
        .mbadge.error{background:rgba(220,38,38,.1);color:#dc2626}
      ` + _es
      + `${'<'+'/head><body>'}<h1>DataBridge Studio — SQL 변환 리포트</h1>`
      + `<div class="meta">생성: ${now} &nbsp;|&nbsp; ${srcDb.value} → ${tgtDb.value} &nbsp;|&nbsp; 총 ${total}개 / 성공 ${okList.length} / AI ${aiList.length}</div>`
      + `<table><thead><tr><th>#</th><th>소스파일</th><th>출력파일</th><th>방식</th><th>변환수</th><th>결과</th></tr></thead><tbody>${rows}</tbody></table>`
      + _eb
    const blob = new Blob([html], {type:'text/html;charset=utf-8'})
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `convert_report_${new Date().toISOString().slice(0,10)}.html`
    a.click(); URL.revokeObjectURL(a.href)
  }
}

async function readFiles(fileList) {
  return Promise.all(fileList.map(item => {
    const f = item.file || item
    return new Promise((res, rej) => {
      const r = new FileReader()
      r.onload = e => res({name: f.name, content: e.target.result})
      r.onerror = rej
      r.readAsText(f, 'utf-8')
    })
  }))
}

const SAMPLES = {
  'mssql→mysql': `-- MSSQL 샘플\nSELECT TOP 10 [id], ISNULL([email], N'없음') AS email\nFROM [dbo].[users]\nWHERE DATEDIFF(DAY, [created_at], GETDATE()) < 30\nORDER BY [created_at] DESC;`,
  'mysql→mssql': `-- MySQL 샘플\nCREATE TABLE \`users\` (\n  \`id\` INT UNSIGNED AUTO_INCREMENT,\n  \`name\` VARCHAR(100) NOT NULL,\n  \`created_at\` DATETIME DEFAULT CURRENT_TIMESTAMP,\n  PRIMARY KEY (\`id\`)\n) ENGINE=InnoDB;\n\nSELECT \`id\`, IFNULL(\`email\`,'없음') AS email FROM \`users\` LIMIT 10;`,
}
function loadSample() {
  textSrc.value = SAMPLES[`${srcDb.value}→${tgtDb.value}`]
    || `-- ${srcDb.value}→${tgtDb.value} 샘플 없음\n-- SQL을 직접 입력하세요`
  textResult.value=''; textChanges.value=[]; textWarnings.value=[]
}
onMounted(() => {
  _checkRemigrateMode()
  
  // v91p5: connector 와 srcDb/tgtDb 자동 동기화
  //   화면 진입 시 → 연결된 DB 종류로 srcDb/tgtDb 초기화
  if (connector.source?.dbType && connector.source.status === 'ok') {
    if (cStore.srcDb !== connector.source.dbType) cStore.srcDb = connector.source.dbType
  }
  if (connector.target?.dbType && connector.target.status === 'ok') {
    if (cStore.tgtDb !== connector.target.dbType) cStore.tgtDb = connector.target.dbType
  }
})

// v91p6: connector 변경 시 srcDb/tgtDb 자동 동기화
watch(() => connector.source?.dbType, (v) => {
  if (v && connector.source.status === 'ok' && cStore.srcDb !== v) cStore.srcDb = v
})
watch(() => connector.target?.dbType, (v) => {
  if (v && connector.target.status === 'ok' && cStore.tgtDb !== v) cStore.tgtDb = v
})

function _checkRemigrateMode() {
  if (route.query.mode !== 'remigrate') return
  const raw = sessionStorage.getItem('remigrate_queue')
  if (!raw) return
  try {
    const q = JSON.parse(raw)
    remigrateQueue.value  = q.items || []
    remigrateTotal.value  = remigrateQueue.value.length
    showRemigrateBar.value = true
    // DB 설정 자동 적용
    if (q.src_db) cStore.srcDb = q.src_db
    if (q.tgt_db) cStore.tgtDb = q.tgt_db
    sessionStorage.removeItem('remigrate_queue')
    app.notify(`재이관 대상 ${remigrateTotal.value}개 로드됨 — 순차 변환을 시작하세요`, 'info')
  } catch {}
}

async function startRemigrateAll() {
  if (!remigrateQueue.value.length) return
  remigrateRunning.value = true
  remigrateResults.value = []

  for (let i = 0; i < remigrateQueue.value.length; i++) {
    remigrateIdx.value = i + 1
    const item = remigrateQueue.value[i]

    // DDL이 없는 경우 소스에서 직접 조회
    let ddl = item.ddl
    if (!ddl) {
      try {
        const srcConn = JSON.parse(sessionStorage.getItem('remigrate_src_conn') || '{}')
        const { data: ddlData } = await axios.get('/api/v1/schema/objects/ddl', {
          params: { ...srcConn, obj_type: item.type, obj_name: item.name },
          timeout: 10000
        })
        ddl = ddlData.ddl || ''
      } catch {}
    }

    if (!ddl) {
      remigrateResults.value.push({ ...item, success: false, error: 'DDL을 가져올 수 없습니다' })
      continue
    }

    // 에디터에 현재 DDL 표시
    textSrc.value = ddl
    textResult.value = ''

    try {
      // ① SP/FN/TRIGGER/VIEW → AI 기반 DDL 변환 전용 API 사용
      const { data } = await axios.post('/api/v1/schema/convert-object-ai', {
        src_db:   cStore.srcDb,
        tgt_db:   cStore.tgtDb,
        schema_strategy: cStore.schemaStrategy,
        obj_type: item.type,
        obj_name: item.name,
        ddl:      ddl,
      }, { timeout: 45000 })

      const converted = data.converted_ddl || data.converted || ''
      if (!converted) throw new Error('변환 결과 없음')

      textResult.value = converted

      // ② 타겟 DB에 즉시 배포
      const tgtConn = JSON.parse(sessionStorage.getItem('remigrate_tgt_conn') || '{}')
      if (tgtConn.host && converted) {
        try {
          await axios.post('/api/v1/schema/execute-object', {
            ...tgtConn,
            obj_type: 'DDL_CREATE',
            obj_sub_type: item.type,
            obj_name: item.name,
            statements: [converted],
            ddl: converted,
          }, { timeout: 30000 })
        } catch(deployErr) {
          // 배포 실패해도 변환은 성공으로 처리
          console.warn(`${item.name} 배포 실패:`, deployErr.message)
        }
      }

      remigrateResults.value.push({
        ...item, ddl, success: true, converted_ddl: converted,
        changes: data.changes || [], warnings: data.warnings || []
      })
      app.notify(`✓ ${item.name} 변환 완료`, 'success')

    } catch(e) {
      remigrateResults.value.push({ ...item, ddl, success: false, error: e.message })
      app.notify(`✗ ${item.name} — ${e.message}`, 'error')
    }
    await new Promise(r => setTimeout(r, 500))
  }

  remigrateRunning.value = false
  const ok   = remigrateResults.value.filter(r => r.success).length
  const fail = remigrateResults.value.filter(r => !r.success).length
  app.notify(`재이관 완료 — 성공 ${ok}개 / 실패 ${fail}개`, fail ? 'warn' : 'success')

  // 성공 항목 이름 저장 → 검증 화면 돌아가면 체크박스 자동 선택
  const successNames = remigrateResults.value.filter(r => r.success).map(r => r.name)
  if (successNames.length) {
    sessionStorage.setItem('remigrate_returned', JSON.stringify(successNames))
    setTimeout(() => {
      router.push('/validate')
    }, 1500)
  }
}

function skipRemigrate() {
  showRemigrateBar.value = false
  remigrateQueue.value   = []
}
</script>

<style>
.sql-converter { display:flex; flex-direction:column; gap:6px; min-width:0; box-sizing:border-box; }   /* v91p8: overflow/max-width 제거 */
/* 상단 설정 바 */
.cfg-bar { display:flex;align-items:center;gap:10px;padding:10px 14px;flex-wrap:wrap; }
.cfg-pair { display:flex;align-items:center;gap:6px; }
.cfg-label { font-size:11px;font-weight:600;color:var(--text-tertiary); }
.sel-wrap { position:relative;min-width:120px; }   /* v91p7: 160 → 120 */
.sel-wrap select { width:100%;appearance:none;-webkit-appearance:none;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:8px;padding:6px 28px 6px 10px;font-size:12.5px;color:var(--text-primary);cursor:pointer;font-family:var(--font); }
.sel-wrap select:focus { outline:none;border-color:var(--accent-blue); }
.chev-ico { position:absolute;right:8px;top:50%;transform:translateY(-50%);pointer-events:none;color:var(--text-tertiary); }
.chev-ico svg { width:10px;height:10px;display:block; }
.arrow-ico { font-size:18px;color:var(--text-tertiary); }
.rule-badge { font-size:11px;padding:4px 10px;border-radius:12px;background:var(--bg-info);color:var(--text-info);border:0.5px solid var(--accent-blue); }
.mode-btn { display:inline-flex;align-items:center;gap:5px;padding:6px 12px;border-radius:8px;border:0.5px solid var(--border-mid);background:transparent;cursor:pointer;font-size:12px;font-weight:500;font-family:var(--font);color:var(--text-secondary);transition:all .12s; }
.mode-btn:hover { background:var(--bg-secondary); }
.mode-btn.active { background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue); }
/* 엔진 선택 바 */
.engine-bar { display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:6px 12px;background:var(--bg-primary);border-radius:var(--radius-md,8px);border:0.5px solid var(--border-light);margin-bottom:0;box-shadow:0 1px 2px rgba(0,0,0,0.03); }   /* v91p7: padding/margin 축소 */
.engine-bar-label { font-size:.75rem;font-weight:600;color:var(--text-tertiary);margin-right:4px;white-space:nowrap; }
/* v91p6: 변환 방식 ↔ 변환 규칙/스키마 구분선 */
.cfg-divider { width:1px;height:18px;background:var(--border-light);margin:0 4px;flex-shrink:0; }
.engine-chip { display:inline-flex;align-items:center;gap:5px;padding:5px 12px;border-radius:20px;border:1px solid var(--border-light);background:var(--bg-secondary);cursor:pointer;font-size:.78rem;font-weight:500;color:var(--text-secondary);transition:all .15s;white-space:nowrap; }
.engine-chip input { display:none; }
.engine-chip:hover { border-color:var(--border-mid);color:var(--text-primary);background:var(--bg-primary); }
.engine-chip.active.none   { border-color:#6b7280;background:rgba(107,114,128,.08);color:#374151;font-weight:700; }
.engine-chip.active.auto   { border-color:#f59e0b;background:rgba(245,158,11,.1);color:#b45309;font-weight:700; }
.engine-chip.active.rules  { border-color:#3b82f6;background:rgba(59,130,246,.1);color:#1d4ed8;font-weight:700; }
.engine-chip.active.claude { border-color:#8b5cf6;background:rgba(139,92,246,.1);color:#6d28d9;font-weight:700; }
.chip-desc { font-size:.67rem;color:var(--text-tertiary);margin-left:2px; }
.method-badge { display:inline-flex;align-items:center;padding:2px 8px;border-radius:8px;font-size:.68rem;font-weight:700;white-space:nowrap;max-width:100%;flex-shrink:0; }
.method-badge.claude-ai      { background:rgba(139,92,246,.15);color:#6d28d9;border:1px solid rgba(139,92,246,.25); }
.method-badge.rules          { background:rgba(59,130,246,.12);color:#1d4ed8;border:1px solid rgba(59,130,246,.2); }
.method-badge.rules_fallback { background:rgba(245,158,11,.12);color:#b45309;border:1px solid rgba(245,158,11,.2); }
/* 에디터 */
.editor-layout { display:grid;grid-template-columns:1fr 60px 1fr;gap:0;align-items:start; }
.editor-panel { display:flex;flex-direction:column;border:0.5px solid var(--border-light);border-radius:var(--radius-md,8px);overflow:hidden;background:var(--bg-primary);box-shadow:0 1px 2px rgba(0,0,0,0.03); }
.ep-head { display:flex;align-items:center;justify-content:space-between;padding:6px 12px;background:var(--bg-secondary);border-bottom:0.5px solid var(--border-light);font-size:.78rem;font-weight:600; }
.ep-head.src { color:var(--text-info); }
.ep-head.tgt { color:#16a34a; }
.sql-ed { flex:1;min-height:280px;padding:10px;font-family:'Consolas','SF Mono',monospace;font-size:12px;line-height:1.5;border:none;background:var(--bg-primary);color:var(--text-primary);resize:none;outline:none; }   /* v91p7: 380 → 280 */
.sql-ed.result { background:var(--bg-secondary);color:var(--text-secondary); }
.ep-foot { padding:5px 12px;font-size:10.5px;color:var(--text-tertiary);background:var(--bg-secondary);border-top:0.5px solid var(--border-light); }
.mid-panel { display:flex;flex-direction:column;align-items:center;justify-content:center;padding-top:120px;gap:6px; }   /* v91p7: 180 → 120 */
.conv-btn { width:50px;height:50px;border-radius:50%;background:var(--accent-blue,#3b82f6);border:none;cursor:pointer;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px;color:#fff;transition:all .15s;box-shadow:0 2px 8px rgba(59,130,246,.4);position:relative; }
.conv-btn:hover:not(:disabled) { transform:scale(1.08);box-shadow:0 4px 12px rgba(59,130,246,.5); }
.conv-btn:disabled:not(.converting) { opacity:.5;cursor:not-allowed; }
.conv-btn-label { font-size:9px;font-weight:700;letter-spacing:0.02em; }

/* v91p15: 변환 중 버튼 — Windows 설치 스타일 부드러운 회전
   본부장님 호소: "막 도는거 너무 경박해 보여 부드럽게 윈도우 설치 하는것 처럼"
   - 펄스/링 제거 (어수선함 제거)
   - 호 회전을 1.4s ease-in-out → 자연스러운 가속/감속
   - 색상 그대로 (청록 = 진행 중 의미) */
.conv-btn.converting {
  background: linear-gradient(135deg, #14b8a6, #0d9488);
  cursor: wait;
  box-shadow: 0 2px 10px rgba(20, 184, 166, 0.35);
  /* 부드러운 박스섀도 호흡 (펄스 대신, 매우 잔잔하게) */
  animation: conv-breath 2.4s ease-in-out infinite;
}
@keyframes conv-breath {
  0%, 100% { box-shadow: 0 2px 10px rgba(20, 184, 166, 0.30); }
  50%      { box-shadow: 0 2px 14px rgba(20, 184, 166, 0.45); }
}

/* 부드러운 호 회전 — Windows 11 설치 스피너 톤 */
.conv-spin-ring {
  animation: conv-smooth-spin 1.4s cubic-bezier(0.65, 0.05, 0.36, 1) infinite;
  transform-origin: 50% 50%;
}
@keyframes conv-smooth-spin {
  0%   { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* "잠시만 기다려주세요" 점점점 */
.conv-progress-text {
  display: flex; align-items: center; gap: 4px;
  font-size: 10px; color: #0d9488; font-weight: 600;
  margin-top: 4px;
  text-align: center;
}
.conv-dots::after {
  content: '...';
  display: inline-block;
  width: 12px;
  text-align: left;
  animation: dots 1.4s steps(4, end) infinite;
  letter-spacing: 1px;
}
@keyframes dots {
  0%   { content: ''; }
  25%  { content: '.'; }
  50%  { content: '..'; }
  75%, 100% { content: '...'; }
}
.spinner { width:13px;height:13px;border-radius:50%;border:2px solid rgba(255,255,255,.3);border-top-color:#fff;animation:spin .7s linear infinite;display:inline-block; }
@keyframes spin { to { transform:rotate(360deg); } }
.change-cnt { font-size:10px;font-weight:700;padding:2px 7px;border-radius:8px; }
.change-cnt.ok   { background:rgba(34,197,94,.12);color:#15803d; }
.change-cnt.warn { background:rgba(245,158,11,.12);color:#b45309; }
.change-grid { display:flex;flex-wrap:wrap;gap:5px; }
.ctag { font-size:10.5px;padding:2px 8px;border-radius:6px; }
.ctag.ok   { background:rgba(34,197,94,.1);color:#15803d; }
.ctag.warn { background:rgba(245,158,11,.1);color:#b45309; }
.mini-btn { font-size:11px;padding:3px 9px;border-radius:6px;border:0.5px solid var(--border-mid);background:transparent;cursor:pointer;font-family:var(--font);color:var(--text-secondary);transition:all .12s; }
.mini-btn:hover { background:var(--bg-secondary); }
.btn { display:inline-flex;align-items:center;gap:5px;padding:6px 12px;border-radius:8px;font-size:12px;font-weight:500;font-family:var(--font);cursor:pointer;border:0.5px solid var(--border-mid);background:transparent;color:var(--text-secondary);transition:all .12s; }
.btn:hover { background:var(--bg-secondary); }
.btn-primary { background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue); }
.btn-primary:hover { background:var(--accent-blue);color:#fff; }
.btn:disabled { opacity:.5;cursor:not-allowed; }
/* 파일 모드 */
.drop-zone { display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;padding:40px 20px;border:2px dashed var(--border-mid);background:var(--bg-secondary);transition:all .15s; }
.drop-zone.drag { border-color:var(--accent-blue);background:var(--bg-info); }
.file-list-hd { display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;font-size:12.5px;font-weight:600;color:var(--text-primary); }
.file-row { display:flex;align-items:center;gap:8px;padding:6px 4px;border-bottom:0.5px solid var(--border-light); }
.file-row:last-child { border-bottom:none; }
.sec-header { display:flex;align-items:center;justify-content:space-between;font-size:12.5px;font-weight:600;color:var(--text-primary);margin-bottom:10px; }
.sum-row { display:flex;gap:10px;margin-bottom:10px; }
.sum-kpi { background:var(--bg-secondary);border:0.5px solid var(--border-light);border-radius:8px;padding:8px 14px;text-align:center; }
.sk-n { font-size:18px;font-weight:700; }
.sk-n.ok   { color:#16a34a; }
.sk-n.info { color:#2563eb; }
.sk-n.warn { color:#d97706; }
.sk-l { font-size:10px;color:var(--text-tertiary); }
.result-row { display:flex;align-items:center;flex-wrap:wrap;gap:6px;padding:8px 4px;border-bottom:0.5px solid var(--border-light);cursor:pointer; }
.result-detail { width:100%;margin-top:6px; }
.f-ico { font-size:13px; }
.f-name { font-size:12px;font-family:'Consolas','SF Mono',monospace;font-weight:500; }
.f-badge { font-size:10px;font-weight:700;padding:2px 7px;border-radius:6px; }
.f-badge.ok   { background:rgba(34,197,94,.12);color:#15803d; }
.f-badge.warn { background:rgba(245,158,11,.12);color:#b45309; }
/* 폴더/파일 모드 — JobMonitor 톤 통일 */
.folder-panel {
  padding: 16px;
  background: var(--bg-primary, #fff);
  border: 0.5px solid var(--border-light, #e5e7eb);
  border-radius: var(--radius-md, 8px);
  box-shadow: 0 1px 2px rgba(0,0,0,0.03);
}
.folder-layout { display:grid;grid-template-columns:1fr 60px 1fr;gap:0;align-items:start;margin-bottom:14px; }
.folder-box { display:flex;flex-direction:column;gap:10px; }
.fb-label { font-size:.78rem;font-weight:600;color:var(--text-secondary); letter-spacing:0.01em; }
.fb-label-row { display:flex;align-items:center;justify-content:space-between; }
.naming-inline { display:flex;gap:4px; }
.fo-radio { display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:12px;border:0.5px solid var(--border-mid);cursor:pointer;font-size:11px;color:var(--text-secondary);transition:all .12s; }
.fo-radio input { width:0;height:0;opacity:0;position:absolute; }
.fo-radio.active { background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue); }
.fb-path { display:flex;align-items:center;gap:8px;padding:10px 12px;border:1px dashed var(--border-mid);border-radius:6px;font-size:12px;color:var(--text-tertiary);background:var(--bg-secondary); }
.fb-path.selected { border-color:var(--accent-blue);color:var(--text-info);background:var(--bg-info);border-style:dashed; }
.folder-arrow { display:flex;flex-direction:column;align-items:center;justify-content:center;padding-top:80px;color:var(--text-tertiary); }
.folder-file-list { border:0.5px solid var(--border-light);border-radius:6px;overflow:hidden;max-height:340px;overflow-y:auto;background:var(--bg-primary); }
.ffl-header { display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:var(--bg-secondary);font-size:.74rem;font-weight:600;color:var(--text-secondary);border-bottom:0.5px solid var(--border-light); }
.ffl-row { display:flex;align-items:center;gap:6px;padding:7px 12px;border-bottom:0.5px solid var(--border-light);cursor:pointer;font-size:.78rem;flex-wrap:wrap; }
.ffl-row:last-child { border-bottom:none; }
.ffl-row:hover { background:var(--bg-secondary); }
.ffl-placeholder { padding:24px;text-align:center;font-size:.78rem;color:var(--text-tertiary); }
.f-size { font-size:.7rem;color:var(--text-tertiary); }
.folder-progress { margin-top:10px; }
.fp-bar-wrap { height:5px;background:var(--border-light);border-radius:3px;overflow:hidden;margin-bottom:5px; }
.fp-bar { height:100%;background:var(--accent-blue);border-radius:3px;transition:width .3s; }
.fp-text { font-size:11px;color:var(--text-secondary); }
.warn-banner { display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--bg-warning);border-radius:8px;font-size:11.5px;color:var(--text-warning); }
/* 하단 액션 바 */
.fab-left { display:flex;flex-direction:column;gap:6px;flex:1;min-width:0; }
.fab-status { display:flex;flex-direction:column;gap:4px; }
.fab-bar-wrap { position:relative;height:6px;background:var(--border-light);border-radius:4px;overflow:hidden; }
.fab-bar-fill { position:absolute;top:0;height:100%;border-radius:4px;transition:width .3s; }
.fab-bar-fill.ok   { background:#22c55e;left:0; }
.fab-bar-fill.fail { background:#ef4444; }
.fab-badges { display:flex;align-items:center;flex-wrap:wrap;gap:4px; }
.fab-badge { display:inline-flex;align-items:center;gap:3px;font-size:.68rem;font-weight:600;padding:1px 7px;border-radius:8px; }
.fab-badge.total   { background:var(--bg-secondary);color:var(--text-secondary);border:0.5px solid var(--border-mid); }
.fab-badge.ok      { background:rgba(34,197,94,.12);color:#15803d; }
.fab-badge.fail    { background:rgba(239,68,68,.12);color:#dc2626; }
.fab-badge.changes { background:rgba(245,158,11,.12);color:#b45309; }
.fab-badge.ai      { background:rgba(139,92,246,.12);color:#6d28d9; }
.fab-badge.done    { background:rgba(34,197,94,.2);color:#15803d;border:1px solid rgba(34,197,94,.4); }
.folder-action-bar {
  display:flex; align-items:center; justify-content:space-between;
  padding:12px 2px 4px;
  border-top:0.5px solid var(--border-light);
  margin-top:4px;
}
.folder-action-info { font-size:12.5px;color:var(--text-secondary); }
.folder-action-info b { color:var(--text-primary); }

/* ── API 키 경고 배너 ── */
.api-warn-bar{display:flex;align-items:center;gap:8px;padding:8px 14px;
  background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.3);
  border-radius:8px;font-size:.75rem;color:#b45309;margin-bottom:6px}
.api-warn-btn{margin-left:auto;padding:3px 10px;border-radius:6px;
  border:1px solid #b45309;background:transparent;cursor:pointer;
  font-size:.7rem;color:#b45309;font-family:var(--font)}
.api-warn-btn:hover{background:rgba(245,158,11,.1)}
/* ── 리포트 버튼 ── */
.rpt-btn{padding:3px 9px;border-radius:6px;border:0.5px solid var(--border-mid);
  background:transparent;font-size:.65rem;cursor:pointer;
  color:var(--text-secondary);font-family:var(--font)}
.rpt-btn:hover{background:var(--bg-hover)}
.rpt-btn.blue{color:#2563eb;border-color:#2563eb}
.rpt-btn.blue:hover{background:rgba(37,99,235,.06)}

/* ── 변환 제어 버튼 ── */
.ctrl-btn-cv{display:flex;align-items:center;gap:4px;padding:6px 12px;border-radius:7px;
  border:0.5px solid var(--border-mid);background:var(--bg-secondary);
  font-size:.72rem;font-weight:600;cursor:pointer;color:var(--text-primary);font-family:var(--font)}
.ctrl-btn-cv:hover{background:var(--bg-hover)}
.ctrl-btn-cv.stop{color:#dc2626;border-color:#dc2626}
.ctrl-btn-cv.stop:hover{background:rgba(220,38,38,.06)}
.conv-progress-txt{font-size:.72rem;color:var(--text-secondary);font-weight:500}


/* ── API 키 팝업 ── */
.api-popup-overlay{
  position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:9999;
  display:flex;align-items:center;justify-content:center;
  animation:fadeIn .15s ease
}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
.api-popup{
  background:var(--bg-primary);border-radius:14px;padding:28px 28px 22px;
  max-width:420px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,.25);
  display:flex;flex-direction:column;gap:14px;
  animation:slideUp .18s ease
}
@keyframes slideUp{from{transform:translateY(12px);opacity:0}to{transform:translateY(0);opacity:1}}
.api-popup-icon{font-size:32px;text-align:center}
.api-popup-title{font-size:.95rem;font-weight:700;color:var(--text-primary);text-align:center}
.api-popup-desc{font-size:.78rem;color:var(--text-secondary);text-align:center;line-height:1.6}
.api-popup-btns{display:flex;flex-direction:column;gap:8px;margin-top:4px}
.api-popup-btn{
  padding:10px 16px;border-radius:8px;border:none;cursor:pointer;
  font-size:.8rem;font-weight:600;font-family:var(--font);transition:all .12s
}
.api-popup-btn.primary{background:#2563eb;color:#fff}
.api-popup-btn.primary:hover{background:#1d4ed8}
.api-popup-btn.rules{background:var(--bg-secondary);color:var(--text-primary);border:1px solid var(--border-mid)}
.api-popup-btn.rules:hover{background:var(--bg-hover)}
.api-popup-btn.cancel{background:transparent;color:var(--text-tertiary);font-size:.72rem;padding:6px}
.api-popup-btn.cancel:hover{color:var(--text-secondary)}

/* ── 재이관 배너 ── */
.sc-remig-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 9px 14px; margin-bottom: 12px;
  background: rgba(37,99,235,.06);
  border: 0.5px solid rgba(37,99,235,.3);
  border-radius: var(--radius-md); flex-wrap: wrap; gap: 8px;
}
.sc-remig-bar-left { display: flex; align-items: center; gap: 8px; }
.sc-remig-bar-title { font-size: 12px; font-weight: 600; color: #1d4ed8; }
.sc-remig-bar-info  { font-size: 11.5px; color: #3b82f6; }
.sc-remig-list-wrap { position: relative; }
.sc-remig-list {
  position: absolute; top: calc(100% + 6px); right: 0;
  background: var(--bg-primary); border: 0.5px solid var(--border-mid);
  border-radius: 8px; min-width: 260px; max-height: 240px; overflow-y: auto;
  z-index: 999; box-shadow: 0 4px 12px rgba(0,0,0,.08);
}
.sc-remig-list-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 12px; font-size: 11.5px; cursor: pointer;
  border-bottom: 0.5px solid var(--border-light); color: var(--text-primary);
}
.sc-remig-list-item:hover { background: var(--bg-secondary); }
.sc-remig-list-item.done { color: #16a34a; }
.sc-remig-list-item.fail { color: #dc2626; }

/* ════ v91 헤더 (JobMonitor 톤) ════════════════════════════════ */
.sc-header {
  display: flex;
  align-items: center;        /* v91p7: 좌측 타이틀 ↔ 우측 모드탭 같은 라인 정렬 */
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 6px;          /* v91p7: 12 → 6 (공백 축소) */
  padding-bottom: 0;
}
.sc-title-wrap { flex: 1; min-width: 0; }
.sc-title-wrap .page-title { line-height: 1.2; }
.sc-title-wrap .page-desc  { font-size: .72rem; color: var(--text-tertiary); margin-top: 1px; }
.sc-header-controls { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }

.sc-mode-tabs {
  display: inline-flex;
  background: var(--bg-secondary, #f3f4f6);
  border: 0.5px solid var(--border-light, #e5e7eb);
  border-radius: 8px;
  padding: 3px;
  gap: 2px;
}
.sc-mode-tab {
  padding: 5px 14px; border-radius: 5px; border: none;
  background: transparent; color: var(--text-secondary, #6b7280);
  font-size: 12px; font-weight: 500; cursor: pointer;
  transition: all 0.15s;
  font-family: var(--font);
}
.sc-mode-tab:hover { color: var(--text-primary, #111827); }
.sc-mode-tab.active {
  background: var(--bg-primary, #fff);
  color: var(--accent-blue, #2563eb);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0,0,0,0.06);
}

.sc-mini-btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 5px 12px; border-radius: 6px;
  border: 0.5px solid var(--border-mid, #d1d5db);
  background: var(--bg-primary, #fff); color: var(--text-secondary, #6b7280);
  font-size: 11.5px; font-weight: 500; cursor: pointer;
  font-family: var(--font);
  transition: all 0.15s;
}
.sc-mini-btn.ghost:hover {
  background: rgba(220, 38, 38, 0.05);
  color: #dc2626; border-color: #dc2626;
}

.sc-cfg-card {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 10px 14px;
  background: var(--bg-primary, #fff);
  border: 0.5px solid var(--border-light, #e5e7eb);
  border-radius: var(--radius-md, 8px);
  margin-bottom: 8px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.03);
}

/* ════ v91p15 변환 중 오버레이 — 얇고 부드럽게 ════════════════ */
/*   본부장님 호소: "상단의 상태바도 너무 부드럽지 못해 조금더 얇게"
     - 테두리 3px → 1.5px (얇게)
     - linear → cubic-bezier ease-in-out (부드럽게)
     - 0.9s → 1.4s (속도 진정) */
.conv-overlay {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(2px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  z-index: 10;
  border-radius: var(--radius-md, 8px);
}
.conv-spinner-big {
  width: 38px; height: 38px;
  border: 1.5px solid rgba(20, 184, 166, 0.12);   /* v91p15: 3px → 1.5px */
  border-top-color: #14b8a6;
  border-right-color: rgba(20, 184, 166, 0.55);    /* v91p15: 그라데이션 효과 */
  border-radius: 50%;
  animation: spin-smooth 1.4s cubic-bezier(0.65, 0.05, 0.36, 1) infinite;
}
@keyframes spin-smooth { to { transform: rotate(360deg); } }
.conv-overlay-text { text-align: center; }
.conv-overlay-title { font-size: 13px; font-weight: 500; color: var(--text-primary); margin-bottom: 4px; letter-spacing: -0.01em; }
.conv-overlay-sub { font-size: 11px; color: var(--text-tertiary); }

/* ════ v91 일괄 변환 진행바 ════════════════════════════════════ */
.batch-progress-bar {
  background: white;
  border: 1px solid var(--border-light, #e5e7eb);
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 10px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.bp-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 8px;
}
.bp-title {
  display: flex; align-items: center; gap: 8px;
  font-size: 12.5px; font-weight: 600;
}
.bp-done-ico {
  display: inline-flex; align-items: center; justify-content: center;
  width: 16px; height: 16px; border-radius: 50%;
  background: #10b981; color: white; font-size: 10px;
}
.bp-current { color: var(--text-secondary, #6b7280); font-weight: 400; font-size: 11.5px; }
.bp-stats { display: flex; gap: 10px; font-size: 11px; }
.bp-stat { color: var(--text-secondary); }
.bp-stat.ok   { color: #10b981; font-weight: 600; }
.bp-stat.fail { color: #dc2626; font-weight: 600; }
.bp-stat.pct  { color: var(--text-primary); font-weight: 700; }
.bp-track {
  height: 6px; background: rgba(0,0,0,0.06); border-radius: 3px; overflow: hidden;
}
.bp-fill {
  height: 100%;
  background: linear-gradient(90deg, #14b8a6, #0d9488);
  transition: width 0.25s ease;
  border-radius: 3px;
}
/* v91p5: 인디터미닛 (텍스트/튜닝 진행 중 — 비율 모름) */
.bp-fill.bp-indeterminate {
  width: 30% !important;
  animation: bp-indet 1.4s ease-in-out infinite;
}
@keyframes bp-indet {
  0%   { transform: translateX(-100%); }
  50%  { transform: translateX(150%); }
  100% { transform: translateX(350%); }
}

/* v91: 초기화 버튼 */
.mode-btn.reset-btn {
  background: white;
  color: var(--text-secondary, #6b7280);
  border: 1px solid var(--border-light, #d1d5db);
}
.mode-btn.reset-btn:hover {
  background: rgba(220, 38, 38, 0.08);
  color: #dc2626;
  border-color: #dc2626;
}

/* ════ v91p8 튜닝 섹션 — 폭 안정화 (튕김 fix) ════════════════ */
.tune-section {
  margin-top: 8px;
  background: var(--bg-elevated, #fff);
  border: 1px solid var(--border-light, #e5e7eb);
  border-radius: 8px;
  padding: 12px 14px 14px 14px;
  width: 100%;
  box-sizing: border-box;
  /* v91p8: overflow:hidden 제거 — 버튼이 잘림 */
}
.tune-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  padding-bottom: 10px;
  padding-right: 4px;     /* v91p8: 우측 여백으로 버튼 안 잘리게 */
  border-bottom: 1px solid var(--border-light, #e5e7eb);
  flex-wrap: wrap;
}
.tune-title { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 13px; flex: 1 1 auto; min-width: 0; }
.tune-ico { font-size: 16px; flex-shrink: 0; }
.tune-meta { font-size: 11px; color: var(--text-secondary, #6b7280); font-weight: 400; white-space: nowrap; }

.tune-controls {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
  flex-wrap: nowrap;
  margin-left: auto;       /* v91p8: 우측 정렬 */
}
.tune-sel {
  font-size: 11px; padding: 4px 8px;
  border: 1px solid var(--border-light, #d1d5db); border-radius: 4px;
  background: white;
  white-space: nowrap; flex-shrink: 0;
  max-width: 130px;
}
.tune-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 14px; border: none; border-radius: 6px;
  background: linear-gradient(135deg, #14b8a6, #0d9488);
  color: white; font-size: 12px; font-weight: 600; cursor: pointer;
  transition: opacity 0.15s;
  white-space: nowrap;
  flex-shrink: 0;
  justify-content: center;
}
.tune-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.tune-btn:hover:not(:disabled) { opacity: 0.9; }

/* v91p16: 튜닝 진행 상태 — 두께 1/2 (본부장님 호소: "지금보다 1/2 로 줄일 수 있어?") */
.tune-progress {
  position: relative;
  padding: 4px 10px 4px 10px;        /* v91p16: 8 → 4 (수직 절반) */
  background: rgba(20, 184, 166, 0.04);
  border-radius: 4px;                 /* v91p16: 6 → 4 */
  font-size: 10.5px;                  /* v91p16: 11.5 → 10.5 */
  line-height: 1.4;                   /* v91p16: 추가 — 행간 컴팩트 */
  color: #0d9488;
  margin-bottom: 6px;                 /* v91p16: 8 → 6 */
  font-weight: 500;
  overflow: hidden;
}
.tune-progress::before {
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 1.5px;                       /* v91p16: 2 → 1.5 (좌측 라인도 얇게) */
  background: linear-gradient(180deg, transparent, #14b8a6, transparent);
  animation: tune-flow 1.8s ease-in-out infinite;
}
@keyframes tune-flow {
  0%   { transform: translateY(-100%); }
  100% { transform: translateY(100%); }
}
.tune-error {
  padding: 10px; background: rgba(220, 38, 38, 0.05);
  border: 1px solid rgba(220, 38, 38, 0.2); border-radius: 4px;
  color: #dc2626; font-size: 12px; margin-bottom: 10px;
}

.tune-base {
  display: flex; gap: 14px; align-items: center;
  padding: 8px 12px; background: rgba(0,0,0,0.02); border-radius: 4px;
  margin-bottom: 10px; font-size: 11px;
}
.tune-base-label { font-weight: 600; color: var(--text-primary); }
.tune-base-stat { color: var(--text-secondary, #6b7280); }

.tune-grid {
  display: grid; grid-template-columns: 1fr; gap: 10px;
  margin-bottom: 12px;
}
.tune-card {
  border: 1.5px solid var(--border-light, #e5e7eb);
  border-radius: 8px; padding: 10px 12px;
  background: white;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.tune-card.recommended {
  border-color: #14b8a6;
  box-shadow: 0 0 0 1px rgba(20, 184, 166, 0.15);
  background: rgba(20, 184, 166, 0.02);
}
.tune-card.mismatch {
  border-color: #f59e0b;
  background: rgba(245, 158, 11, 0.02);
}
/* v91p14: 1위 카드 (rank 정렬) — 골드 강조 */
.tune-card.top {
  border-color: #f59e0b;
  border-width: 2px;
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.18), 0 4px 12px rgba(245, 158, 11, 0.12);
  background: linear-gradient(135deg, rgba(20, 184, 166, 0.04), rgba(245, 158, 11, 0.04));
}

/* v91p14: 랭크 메달 */
.tune-rank { display: inline-flex; align-items: center; margin-right: 4px; }
.rank-medal { font-size: 18px; line-height: 1; filter: drop-shadow(0 1px 2px rgba(0,0,0,0.15)); }
.rank-num {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 50%;
  background: var(--bg-secondary, #f3f4f6);
  color: var(--text-secondary, #6b7280);
  font-size: 11px; font-weight: 700;
  border: 1px solid var(--border-light, #e5e7eb);
}

/* v91p14: 카드별 복사 버튼 */
.tune-card-copy {
  display: inline-flex; align-items: center; gap: 3px;
  padding: 3px 8px; margin-left: 4px;
  border: 1px solid var(--border-light, #d1d5db);
  border-radius: 4px;
  background: white;
  color: var(--text-secondary, #6b7280);
  font-size: 10.5px; font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.tune-card-copy:hover {
  background: rgba(59, 130, 246, 0.06);
  color: #1d4ed8;
  border-color: #3b82f6;
}
.tune-card-head {
  display: flex; align-items: center; gap: 10px; margin-bottom: 6px;
}
.tune-check { display: flex; align-items: center; gap: 6px; cursor: pointer; }
.tune-check input { cursor: pointer; }
.tune-id { font-size: 11px; color: var(--text-secondary); font-weight: 600; }
.tune-label { font-weight: 600; font-size: 12px; flex: 1; }

.tune-badges { display: flex; gap: 5px; flex-wrap: wrap; }
.tune-badge {
  font-size: 10px; padding: 2px 7px; border-radius: 10px;
  font-weight: 600; white-space: nowrap;
}
.tune-badge.ok      { background: #14b8a6; color: white; }
.tune-badge.ok-soft { background: rgba(20, 184, 166, 0.15); color: #0d9488; }
.tune-badge.fast    { background: #10b981; color: white; }
.tune-badge.slow    { background: rgba(245, 158, 11, 0.2); color: #b45309; }
.tune-badge.fail    { background: #dc2626; color: white; }

.tune-card-strategy {
  font-size: 11.5px; color: var(--text-secondary); margin-bottom: 4px;
  display: inline-flex; align-items: center; gap: 6px;
}
/* v91p17: 전략 설명 ⓘ 아이콘 (호버 시 툴팁) */
.strategy-info {
  display: inline-flex; align-items: center; justify-content: center;
  width: 14px; height: 14px;
  border-radius: 50%;
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
  font-size: 10px; font-weight: 700;
  cursor: help;
  transition: all 0.15s;
  font-style: normal;
}
.strategy-info:hover {
  background: #3b82f6;
  color: white;
  transform: scale(1.1);
}
.tune-card-reason {
  font-size: 10.5px; color: var(--text-tertiary, #9ca3af); font-style: italic;
  margin-bottom: 6px;
}
.tune-card-stats {
  display: flex; gap: 14px; font-size: 11px; color: var(--text-secondary);
  margin-bottom: 6px; flex-wrap: wrap; align-items: center;
}
.ts-stat { display: inline-flex; gap: 4px; align-items: baseline; }
.ts-stat b { color: var(--text-primary); font-weight: 600; }
.ts-vs { font-size: 10px; color: var(--text-tertiary); font-weight: 400; }
.ts-vs.ts-warn { color: #f59e0b; font-weight: 500; }
.ts-stat.ts-error { color: #dc2626; font-weight: 500; }

/* v91p8: 진단 상세 박스 */
.tune-card-detail {
  font-size: 10.5px; padding: 5px 8px; border-radius: 4px;
  margin-bottom: 6px; line-height: 1.4;
}
.tune-card-detail.ok      { background: rgba(20, 184, 166, 0.08); color: #0d9488; }
.tune-card-detail.fail    { background: rgba(245, 158, 11, 0.08); color: #b45309; }
.tune-card-detail.unknown { background: rgba(107, 114, 128, 0.08); color: var(--text-secondary); }

.tune-card-sql {
  font-family: 'Consolas', 'Monaco', monospace; font-size: 10.5px;
  background: rgba(0,0,0,0.03); padding: 8px 10px; border-radius: 4px;
  max-height: 180px; overflow-y: auto; white-space: pre-wrap;
  word-break: break-all; margin: 0;
}

.tune-actions {
  display: flex; gap: 8px; justify-content: flex-end;
  padding-top: 10px; border-top: 1px solid var(--border-light, #e5e7eb);
}
.tune-action-btn {
  padding: 6px 14px; border-radius: 6px; border: none;
  font-size: 12px; font-weight: 600; cursor: pointer;
  background: #14b8a6; color: white;
}
.tune-action-btn.ghost { background: white; color: #14b8a6; border: 1px solid #14b8a6; }
.tune-action-btn:disabled { opacity: 0.4; cursor: not-allowed; }

</style>
