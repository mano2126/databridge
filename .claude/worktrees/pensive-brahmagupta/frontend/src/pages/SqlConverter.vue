<template>
  <div class="sql-converter">

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

    <div class="page-title">SQL 쿼리 변환기</div>
    <div class="page-desc">텍스트 입력, 파일 업로드, 또는 <b>폴더 일괄 변환</b>으로 SQL 방언을 변환합니다</div>

    <!-- ── 상단 설정 바 ── -->
    <div class="card cfg-bar">
      <div class="cfg-pair">
        <span class="cfg-label">소스 DB</span>
        <div class="sel-wrap">
          <select v-model="srcDb" @change="clearAll">
            <option v-for="d in allDbs" :key="d.v" :value="d.v">{{ d.n }}</option>
          </select><Chev/>
        </div>
      </div>
      <div class="arrow-ico">→</div>
      <div class="cfg-pair">
        <span class="cfg-label">타겟 DB</span>
        <div class="sel-wrap">
          <select v-model="tgtDb" @change="clearAll">
            <option v-for="d in allDbs" :key="d.v" :value="d.v">{{ d.n }}</option>
          </select><Chev/>
        </div>
      </div>
      <div class="rule-badge">변환 규칙 <b>{{ ruleCount }}</b>개</div>
      <div style="margin-left:auto;display:flex;gap:5px">
        <button class="mode-btn" :class="{active:mode==='text'}"   @click="mode='text'">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><rect x="1" y="1" width="12" height="12" rx="1"/><line x1="3" y1="5" x2="11" y2="5"/><line x1="3" y1="8" x2="9" y2="8"/></svg> 텍스트
        </button>
        <button class="mode-btn" :class="{active:mode==='file'}"   @click="mode='file'">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><path d="M2 1h7l3 3v9H2z"/><polyline points="9,1 9,4 12,4"/></svg> 파일
        </button>
        <button class="mode-btn" :class="{active:mode==='folder'}" @click="mode='folder'">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><path d="M1 3h5l1 2h6v7H1z"/></svg> 폴더
        </button>
      </div>
    </div>

    <!-- ══ 변환 방식 (항상 표시) ══ -->
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
          <button class="conv-btn" @click="doConvertText" :disabled="converting||!textSrc.trim()">
            <span v-if="converting" class="spinner"></span>
            <svg v-else viewBox="0 0 14 14" fill="none" stroke="white" stroke-width="2" style="width:14px;height:14px"><line x1="2" y1="7" x2="12" y2="7"/><polyline points="8,3 12,7 8,11"/></svg>
            <span style="font-size:9px;font-weight:700">변환</span>
          </button>
          <div v-if="textChanges.length" class="change-cnt ok">{{ textChanges.length }}건 변경</div>
          <div v-if="textWarnings.length" class="change-cnt warn">{{ textWarnings.length }}건 확인</div>
        </div>

        <div class="editor-panel">
          <div class="ep-head tgt">
            <span>결과 ({{ tgtDb }})</span>
            <div style="display:flex;gap:5px">
              <button class="mini-btn" @click="copyText"     :disabled="!textResult">복사</button>
              <button class="mini-btn" @click="downloadText" :disabled="!textResult">저장</button>
            </div>
          </div>
          <textarea v-model="textResult" class="sql-ed result" readonly spellcheck="false"/>
          <div class="ep-foot">{{ lineCount(textResult) }}줄 · {{ textResult.length }}자</div>
        </div>
      </div>

      <!-- 변환 내역 -->
      <div v-if="textChanges.length||textWarnings.length" class="card" style="margin-top:8px;padding:10px 14px">
        <div class="change-grid">
          <div v-for="c in textChanges"  :key="c" class="ctag ok">✓ {{ c }}</div>
          <div v-for="w in textWarnings" :key="w" class="ctag warn">⚠ {{ w }}</div>
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
import axios from 'axios'

const app    = useAppStore()
const cStore = useConverterStore()
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

// ── store 연동 (화면 이탈 후에도 상태 유지) ─────────────────
const srcDb       = computed({ get: () => cStore.srcDb,      set: v => cStore.srcDb = v })
const tgtDb       = computed({ get: () => cStore.tgtDb,      set: v => cStore.tgtDb = v })
const convEngine  = computed({ get: () => cStore.convEngine,  set: v => cStore.convEngine = v })
const namingMode  = computed({ get: () => cStore.namingMode,  set: v => cStore.namingMode = v })
const folderFiles    = computed(() => cStore.folderFiles)
const tgtFiles       = computed(() => cStore.tgtFiles)
const convertReport  = computed(() => cStore.convertReport)
const folderProgress = computed(() => cStore.folderProgress)
const running     = computed(() => cStore.running)
const paused      = computed(() => cStore.paused)
const runningIdx  = computed(() => cStore.runningIdx)
const isDone      = computed(() => cStore.isDone)
const pct         = computed(() => cStore.pct)
const converting  = computed(() => cStore.running)  // 호환성용

// 텍스트 모드
const textSrc      = ref(sessionStorage.getItem('sc_src') || '')
const textResult   = ref(sessionStorage.getItem('sc_result') || '')
const textChanges  = ref([])
const textWarnings = ref([])

// 파일 모드
const fileInput   = ref(null)
const files       = ref([])
const fileResults = ref([])

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

// ── 텍스트 변환 ──
async function doConvertText() {
  if (!textSrc.value.trim()) return
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
  const endpoint = convEngine.value==='rules'
      ? '/api/v1/sql-converter/convert'
      : '/api/v1/sql-converter/convert-ai'
    const { data } = await axios.post(endpoint, {
      sql: textSrc.value, src_db: srcDb.value, tgt_db: tgtDb.value, engine: convEngine.value
    })
    textResult.value  = data.converted
    textChanges.value = data.changes  || []
    textWarnings.value= data.warnings || []
    lastMethod.value  = data.method   || 'rules'
    const lbl = {'claude-ai':'🤖 Claude AI','rules':'⚙ 규칙 기반','rules_fallback':'⚙ 규칙(폴백)'}[lastMethod.value] || lastMethod.value
    app.notify(`변환 완료 [${lbl}] — ${textChanges.value.length}건 변경`, 'success')
    sessionStorage.setItem('sc_src',    textSrc.value)
    sessionStorage.setItem('sc_result', textResult.value)
  } catch(e) { app.notify('변환 실패: '+e.message,'error') }
  finally { converting.value=false }
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
      // 파일별 엔진 결정: 대용량이면 규칙 기반 강제
      const isLarge = content_txt.length > 80000
      const endpoint = (convEngine.value === 'claude' || convEngine.value === 'auto')
        ? '/api/v1/sql-converter/convert-ai'
        : '/api/v1/sql-converter/convert'
      let converted, changes = [], warnings = [], method = 'none'
      if (convEngine.value === 'none') {
        converted = content_txt
      } else {
        const { data } = await axios.post(endpoint, {
          sql: content_txt, src_db: srcDb.value, tgt_db: tgtDb.value, engine: convEngine.value
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
  converting.value=true
  try {
    const contents = await readFiles(files.value.map(f => f.file || f))
    const fileEndpoint = convEngine.value === 'none'
      ? '/api/v1/sql-converter/convert-files'
      : convEngine.value === 'claude' || convEngine.value === 'auto'
        ? '/api/v1/sql-converter/convert-files-ai'
        : '/api/v1/sql-converter/convert-files'
    const { data } = await axios.post(fileEndpoint, {
      files: contents, src_db: srcDb.value, tgt_db: tgtDb.value,
      engine: convEngine.value
    })
    fileResults.value = data.files.map(r=>({...r, _open:false}))
    app.notify(`${data.total_files}개 변환 완료`, 'success')
  } catch(e) { app.notify('변환 실패','error') }
  finally { converting.value=false }
}

async function downloadZip() {
  // 파일 모드: 이미 변환된 결과 사용
  if (mode.value === 'file' && _fileConvertedList.value.length) {
    const resp = await axios.post('/api/v1/sql-converter/convert-files/download',
      { files: _fileConvertedList.value.map(f=>({name:f.name,content:f.content})),
        src_db: srcDb.value, tgt_db: tgtDb.value }, { responseType:'blob' })
    const cd = resp.headers['content-disposition']||''
    const name = cd.match(/filename="(.+?)"/)?.[1]||'converted.zip'
    const a = document.createElement('a'); a.href=URL.createObjectURL(new Blob([resp.data])); a.download=name; a.click()
    return
  }
  // 기존 방식
  const contents = await readFiles(files.value.map(f => f.file || f))
  const resp = await axios.post('/api/v1/sql-converter/convert-files/download',
    { files: contents, src_db: srcDb.value, tgt_db: tgtDb.value }, { responseType:'blob' })
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
      { files: result, src_db: cStore.srcDb, tgt_db: cStore.tgtDb }, { responseType: 'blob' })
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
    { files:contents, src_db:srcDb.value, tgt_db:tgtDb.value }, { responseType:'blob' })
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
.sql-converter { display:flex; flex-direction:column; gap:10px; }
/* 상단 설정 바 */
.cfg-bar { display:flex;align-items:center;gap:10px;padding:10px 14px;flex-wrap:wrap; }
.cfg-pair { display:flex;align-items:center;gap:6px; }
.cfg-label { font-size:11px;font-weight:600;color:var(--text-tertiary); }
.sel-wrap { position:relative;min-width:160px; }
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
.engine-bar { display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:8px 12px;background:var(--bg-secondary);border-radius:10px;border:0.5px solid var(--border-light); }
.engine-bar-label { font-size:.75rem;font-weight:600;color:var(--text-tertiary);margin-right:4px;white-space:nowrap; }
.engine-chip { display:inline-flex;align-items:center;gap:5px;padding:5px 12px;border-radius:20px;border:1.5px solid var(--border-light);background:var(--bg-primary);cursor:pointer;font-size:.78rem;font-weight:500;color:var(--text-secondary);transition:all .15s;white-space:nowrap; }
.engine-chip input { display:none; }
.engine-chip:hover { border-color:var(--border-mid);color:var(--text-primary); }
.engine-chip.active.none   { border-color:#6b7280;background:rgba(107,114,128,.08);color:#374151;font-weight:700; }
.engine-chip.active.auto   { border-color:#f59e0b;background:rgba(245,158,11,.1);color:#b45309;font-weight:700; }
.engine-chip.active.rules  { border-color:#3b82f6;background:rgba(59,130,246,.1);color:#1d4ed8;font-weight:700; }
.engine-chip.active.claude { border-color:#8b5cf6;background:rgba(139,92,246,.1);color:#6d28d9;font-weight:700; }
.chip-desc { font-size:.67rem;color:var(--text-tertiary);margin-left:2px; }
.method-badge { display:inline-flex;align-items:center;padding:2px 8px;border-radius:8px;font-size:.68rem;font-weight:700;white-space:nowrap; }
.method-badge.claude-ai      { background:rgba(139,92,246,.15);color:#6d28d9;border:1px solid rgba(139,92,246,.25); }
.method-badge.rules          { background:rgba(59,130,246,.12);color:#1d4ed8;border:1px solid rgba(59,130,246,.2); }
.method-badge.rules_fallback { background:rgba(245,158,11,.12);color:#b45309;border:1px solid rgba(245,158,11,.2); }
/* 에디터 */
.editor-layout { display:grid;grid-template-columns:1fr 60px 1fr;gap:0;align-items:start; }
.editor-panel { display:flex;flex-direction:column;border:0.5px solid var(--border-light);border-radius:10px;overflow:hidden;background:var(--bg-primary); }
.ep-head { display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:var(--bg-secondary);border-bottom:0.5px solid var(--border-light);font-size:12px;font-weight:600; }
.ep-head.src { color:var(--text-info); }
.ep-head.tgt { color:#16a34a; }
.sql-ed { flex:1;min-height:420px;padding:12px;font-family:'Consolas','SF Mono',monospace;font-size:12px;line-height:1.6;border:none;background:var(--bg-primary);color:var(--text-primary);resize:none;outline:none; }
.sql-ed.result { background:var(--bg-secondary);color:var(--text-secondary); }
.ep-foot { padding:5px 12px;font-size:10.5px;color:var(--text-tertiary);background:var(--bg-secondary);border-top:0.5px solid var(--border-light); }
.mid-panel { display:flex;flex-direction:column;align-items:center;justify-content:center;padding-top:180px;gap:6px; }
.conv-btn { width:44px;height:44px;border-radius:50%;background:var(--accent-blue,#3b82f6);border:none;cursor:pointer;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;color:#fff;transition:all .15s;box-shadow:0 2px 8px rgba(59,130,246,.4); }
.conv-btn:hover:not(:disabled) { transform:scale(1.08);box-shadow:0 4px 12px rgba(59,130,246,.5); }
.conv-btn:disabled { opacity:.5;cursor:not-allowed; }
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
/* 폴더 모드 */
.folder-panel { padding:16px; }
.folder-layout { display:grid;grid-template-columns:1fr 60px 1fr;gap:0;align-items:start;margin-bottom:14px; }
.folder-box { display:flex;flex-direction:column;gap:10px; }
.fb-label { font-size:12px;font-weight:700;color:var(--text-secondary); }
.fb-label-row { display:flex;align-items:center;justify-content:space-between; }
.naming-inline { display:flex;gap:4px; }
.fo-radio { display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:12px;border:0.5px solid var(--border-mid);cursor:pointer;font-size:11px;color:var(--text-secondary);transition:all .12s; }
.fo-radio input { width:0;height:0;opacity:0;position:absolute; }
.fo-radio.active { background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue); }
.fb-path { display:flex;align-items:center;gap:8px;padding:10px 12px;border:1.5px dashed var(--border-mid);border-radius:8px;font-size:12px;color:var(--text-tertiary);background:var(--bg-secondary); }
.fb-path.selected { border-color:var(--accent-blue);color:var(--text-info);background:var(--bg-info); }
.folder-arrow { display:flex;flex-direction:column;align-items:center;justify-content:center;padding-top:80px; }
.folder-file-list { border:0.5px solid var(--border-light);border-radius:8px;overflow:hidden;max-height:340px;overflow-y:auto; }
.ffl-header { display:flex;align-items:center;justify-content:space-between;padding:7px 10px;background:var(--bg-tertiary);font-size:11px;font-weight:600;color:var(--text-secondary);border-bottom:0.5px solid var(--border-light); }
.ffl-row { display:flex;align-items:center;gap:6px;padding:6px 10px;border-bottom:0.5px solid var(--border-light);cursor:pointer;font-size:11.5px; }
.ffl-row:last-child { border-bottom:none; }
.ffl-row:hover { background:var(--bg-secondary); }
.ffl-placeholder { padding:20px;text-align:center;font-size:12px;color:var(--text-tertiary); }
.f-size { font-size:10.5px;color:var(--text-tertiary); }
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

</style>
