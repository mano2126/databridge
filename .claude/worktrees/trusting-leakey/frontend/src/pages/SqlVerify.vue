<template>
  <div>
    <div class="page-title">쿼리 검증 비교</div>
    <div class="page-desc">소스/타겟 DB에 쿼리를 실행하고 결과를 비교 검증합니다</div>

    <!-- ══ DB 연결 ══════════════════════════════════════════════════ -->
    <div class="card cfg-card">
      <div class="cfg-row">

        <!-- 소스 DB -->
        <div class="conn-block">
          <!-- 연결됨 상태 -->
          <div v-if="connOk.src" class="conn-summary">
            <div class="conn-summary-left">
              <span class="conn-dot on"/>
              <div>
                <div class="conn-summary-title">소스 DB 연결됨</div>
                <div class="conn-summary-sub">
                  <span class="db-type-tag">{{ srcConn.db_type }}</span>
                  {{ srcConn.host }}:{{ srcConn.port }} / <b>{{ srcConn.database }}</b>
                </div>
              </div>
            </div>
            <button class="conn-change-btn" @click="connOk.src=false">변경</button>
          </div>

          <!-- 미연결 상태 - 입력 폼 -->
          <template v-else>
            <div class="conn-title">
              <span class="conn-dot off"/>
              소스 DB
              <span class="conn-hint">연결 정보를 입력하고 연결하세요</span>
            </div>
            <div class="conn-fields">
              <select v-model="srcConn.db_type" class="f-sel">
                <option v-for="d in dbs" :key="d.v" :value="d.v">{{ d.n }}</option>
              </select>
              <input v-model="srcConn.host"     class="f-inp" placeholder="호스트"/>
              <input v-model="srcConn.port"     class="f-inp sm" placeholder="포트"/>
              <input v-model="srcConn.database" class="f-inp" placeholder="DB명"/>
              <input v-model="srcConn.username" class="f-inp" placeholder="사용자"/>
              <input v-model="srcConn.password" class="f-inp" type="password" placeholder="비밀번호"/>
            </div>
            <div class="conn-foot">
              <button class="act-btn" @click="loadConn('src')">
                <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px"><path d="M2 2h4l1 1h5v8H2z"/></svg>
                커넥터 불러오기
              </button>
              <button class="conn-btn" @click="connectAndSave('src')" :disabled="testing.src || !srcConn.host">
                <span v-if="testing.src" class="spinner" style="width:9px;height:9px;display:inline-block;margin-right:3px"/>
                <svg v-else viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" style="width:10px;height:10px"><path d="M2 6a4 4 0 1 1 4 4"/><polyline points="6,2 8,4 6,6"/></svg>
                {{ testing.src ? '연결 중...' : '연결' }}
              </button>
              <span v-if="connMsg.src" class="cmsg" :class="connMsg.src.ok?'ok':'err'">{{ connMsg.src.msg }}</span>
            </div>
          </template>
        </div>

        <!-- 교환 버튼 -->
        <div class="swap-col">
          <button class="swap-btn" @click="swapConns" title="소스/타겟 교환">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:14px;height:14px">
              <path d="M2 5h12M10 2l4 3-4 3"/><path d="M14 11H2M6 8l-4 3 4 3"/>
            </svg>
          </button>
        </div>

        <!-- 타겟 DB -->
        <div class="conn-block">
          <!-- 연결됨 상태 -->
          <div v-if="connOk.tgt" class="conn-summary">
            <div class="conn-summary-left">
              <span class="conn-dot on"/>
              <div>
                <div class="conn-summary-title">타겟 DB 연결됨</div>
                <div class="conn-summary-sub">
                  <span class="db-type-tag">{{ tgtConn.db_type }}</span>
                  {{ tgtConn.host }}:{{ tgtConn.port }} / <b>{{ tgtConn.database }}</b>
                </div>
              </div>
            </div>
            <button class="conn-change-btn" @click="connOk.tgt=false">변경</button>
          </div>

          <!-- 미연결 상태 - 입력 폼 -->
          <template v-else>
            <div class="conn-title">
              <span class="conn-dot off"/>
              타겟 DB
              <span class="conn-hint">연결 정보를 입력하고 연결하세요</span>
            </div>
            <div class="conn-fields">
              <select v-model="tgtConn.db_type" class="f-sel">
                <option v-for="d in dbs" :key="d.v" :value="d.v">{{ d.n }}</option>
              </select>
              <input v-model="tgtConn.host"     class="f-inp" placeholder="호스트"/>
              <input v-model="tgtConn.port"     class="f-inp sm" placeholder="포트"/>
              <input v-model="tgtConn.database" class="f-inp" placeholder="DB명"/>
              <input v-model="tgtConn.username" class="f-inp" placeholder="사용자"/>
              <input v-model="tgtConn.password" class="f-inp" type="password" placeholder="비밀번호"/>
            </div>
            <div class="conn-foot">
              <button class="act-btn" @click="loadConn('tgt')">
                <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px"><path d="M2 2h4l1 1h5v8H2z"/></svg>
                커넥터 불러오기
              </button>
              <button class="conn-btn" @click="connectAndSave('tgt')" :disabled="testing.tgt || !tgtConn.host">
                <span v-if="testing.tgt" class="spinner" style="width:9px;height:9px;display:inline-block;margin-right:3px"/>
                <svg v-else viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" style="width:10px;height:10px"><path d="M2 6a4 4 0 1 1 4 4"/><polyline points="6,2 8,4 6,6"/></svg>
                {{ testing.tgt ? '연결 중...' : '연결' }}
              </button>
              <span v-if="connMsg.tgt" class="cmsg" :class="connMsg.tgt.ok?'ok':'err'">{{ connMsg.tgt.msg }}</span>
            </div>
          </template>
        </div>

      </div>
    </div><!-- ══ 입력 모드 + 옵션 바 ══════════════════════════════════════ -->
    <div class="card opt-bar">
      <div style="display:flex;align-items:center;gap:8px">
        <!-- 모드 탭 -->
        <div class="mode-grp">
          <button class="mtab" :class="{active:inputMode==='text'}"   @click="setMode('text')">✏ 직접 입력</button>
          <button class="mtab" :class="{active:inputMode==='file'}"   @click="setMode('file')">📄 파일 선택</button>
          <button class="mtab" :class="{active:inputMode==='folder'}" @click="setMode('folder')">📁 폴더 선택</button>
        </div>
        <!-- Clear 버튼 (파일/폴더 모드에서만) -->
        <button v-if="inputMode!=='text'" class="clear-btn" @click="clearAll" title="전체 초기화">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:11px;height:11px"><line x1="2" y1="2" x2="12" y2="12"/><line x1="12" y1="2" x2="2" y2="12"/></svg>
        </button>
      </div>
      <div style="display:flex;align-items:center;gap:8px">
        <!-- 변환 방식 -->
        <div class="cv-grp">
          <span class="cv-label">쿼리 변환</span>
          <!-- 변환 그룹 -->
          <div class="cv-seg-group">
            <div class="cv-seg-label">자동 변환</div>
            <button class="cv-btn" :class="{active:convMethod==='auto'}" @click="convMethod='auto'">
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px"><path d="M2 6a4 4 0 1 1 4 4"/><polyline points="6,2 8,4 6,6"/></svg>
              규칙 기반
            </button>
            <button class="cv-btn claude-btn" :class="{active:convMethod==='claude'}" @click="convMethod='claude'">
              <span class="claude-spark">✦</span> Claude AI
              <span v-if="apiAvail" class="api-ok">✓</span>
              <span v-else class="api-na">키 필요</span>
            </button>
          </div>
          <div class="cv-divider"></div>
          <!-- 변환 안함 -->
          <button class="cv-btn none-btn" :class="{active:convMethod==='none'}" @click="convMethod='none'">
            <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px"><circle cx="6" cy="6" r="5"/><line x1="3.5" y1="3.5" x2="8.5" y2="8.5"/></svg>
            변환 안함
          </button>
        </div>
        <select v-model="maxRows" class="rows-sel">
          <option value="50">50행</option><option value="100">100행</option>
          <option value="200">200행</option><option value="500">500행</option>
        </select>
      </div>
    </div>

    <!-- ══ 직접 입력 모드 ═══════════════════════════════════════════ -->
    <template v-if="inputMode==='text'">
      <div class="editor-grid">
        <div class="qpanel">
          <div class="qph src">소스 쿼리 ({{ srcConn.db_type }})</div>
          <textarea v-model="srcSql" class="sql-ed" :placeholder="srcConn.db_type + ' SQL 입력...'" spellcheck="false" @input="onSrcInput"/>
          <div class="qpf">{{ srcSql.split('\n').length }}줄 · {{ srcSql.length }}자</div>
        </div>
        <div class="mid-col">
          <button class="run-btn" @click="runText" :disabled="running||(!srcSql.trim()&&!tgtSql.trim())">
            <span v-if="running" class="spinner" style="width:13px;height:13px;border-top-color:#fff;display:inline-block"></span>
            <svg v-else viewBox="0 0 14 14" fill="none" stroke="white" stroke-width="2" style="width:14px;height:14px"><polygon points="2,2 12,7 2,12"/></svg>
            <span style="font-size:9px;font-weight:700">{{ running?'실행중':'실행' }}</span>
          </button>
          <button class="mini-act" @click="convertOnly" :disabled="!srcSql.trim()||convMethod==='none'">변환만</button>
          <button class="mini-act" @click="()=>{srcSql='';tgtSql='';result=null;convInfo=null}">지우기</button>
        </div>
        <div class="qpanel">
          <div class="qph tgt">타겟 쿼리 ({{ tgtConn.db_type }})</div>
          <textarea v-model="tgtSql" class="sql-ed" :placeholder="tgtConn.db_type + ' 변환 결과...'" spellcheck="false"/>
          <div class="qpf">{{ tgtSql.split('\n').length }}줄 · {{ tgtSql.length }}자</div>
        </div>
      </div>
    </template>

    <!-- ══ 파일/폴더 모드 ═══════════════════════════════════════════ -->
    <template v-else>
      <!-- 소스 / 타겟 독립 패널 -->
      <div class="fp-layout">

        <!-- 소스 패널 -->
        <div class="fp-panel card">
          <div class="fp-hdr src">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><path d="M2 2h8l2 2v8H2z"/></svg>
            소스 ({{ srcConn.db_type }})
            <span v-if="srcPath" class="fp-path">
              📁 {{ srcPath }}
            </span>
            <span v-if="srcFiles.length" class="fp-cnt">{{ srcFiles.length }}개</span>
            <button v-if="srcFiles.length" class="fp-clear" @click="clearSrc" title="소스 초기화">×</button>
            <div style="margin-left:auto">
              <button v-if="inputMode==='file'" class="fp-sel-btn" @click="$refs.srcFileInp.click()">파일 선택</button>
              <button v-else class="fp-sel-btn" @click="$refs.srcFolderInp.click()">폴더 선택</button>
              <input ref="srcFileInp"   type="file" accept=".sql,.txt" multiple  style="display:none" @change="onSrcFileSelect"/>
              <input ref="srcFolderInp" type="file" webkitdirectory              style="display:none" @change="onSrcFolderSelect"/>
            </div>
          </div>

          <!-- 드롭존 (파일 없을 때) -->
          <div v-if="!srcFiles.length" class="fp-drop"
               @dragover.prevent @drop.prevent="onDrop($event,'src')"
               @click="inputMode==='file'?$refs.srcFileInp.click():$refs.srcFolderInp.click()">
            <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1" style="width:36px;height:36px;opacity:.35">
              <path v-if="inputMode==='folder'" d="M2 6h10l2 3h16v19H2z"/>
              <path v-else d="M4 4h16l6 6v18H4z"/><polyline v-if="inputMode==='file'" points="20,4 20,10 26,10"/>
            </svg>
            <div style="font-size:13px;color:var(--text-secondary);margin-top:8px">
              {{ inputMode==='folder' ? '소스 폴더 클릭 또는 드래그' : '소스 .sql/.txt 파일 클릭 또는 드래그' }}
            </div>
          </div>

          <!-- 파일 목록 -->
          <div v-else class="fp-list">
            <div v-for="(f,i) in srcFiles" :key="i" class="fp-item"
                 :class="{active: activePair===i, running: runningIdx===i}"
                 @click="previewSrc(i)">
              <span class="fnum">{{ i+1 }}</span>
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.2" style="width:11px;height:11px;flex-shrink:0;color:var(--text-tertiary)"><path d="M1 1h7l2 2v8H1z"/></svg>
              <span class="fname">{{ f.name }}</span>
              <span class="fsize">{{ fmtSize(f.size) }}</span>
              <!-- 실행 결과 배지 -->
              <span v-if="fileResults[i]" class="res-badge" :class="fileResults[i].comparison?.match?'ok':'fail'">
                {{ fileResults[i].comparison?.match ? '✓' : '✗' }}
              </span>
              <span v-else-if="runningIdx===i" class="res-badge running">
                <span class="spinner" style="width:8px;height:8px;display:inline-block"></span>
              </span>
              <button class="frm" @click.stop="removeSrc(i)">×</button>
            </div>
          </div>
        </div>

        <!-- 가운데 컬럼 -->
        <div class="fp-mid">
          <!-- 변환 있는 경우 (자동/Claude) -->
          <template v-if="convMethod!=='none'">
            <div class="fp-mid-flow">
              <!-- 소스 -->
              <div class="flow-node src-node">소스<br/><span>{{ srcConn.db_type }}</span></div>
              <!-- 변환 화살표 -->
              <div class="flow-conv">
                <svg viewBox="0 0 8 24" fill="none" stroke="currentColor" stroke-width="1.3" style="width:8px;height:20px;color:var(--text-tertiary)"><line x1="4" y1="0" x2="4" y2="24"/><polyline points="1,18 4,24 7,18"/></svg>
                <div class="flow-conv-badge" :class="convMethod==='claude'?'ai':'rule'">
                  <span v-if="convMethod==='claude'">✦ AI</span>
                  <span v-else>⚙ 규칙</span>
                </div>
                <svg viewBox="0 0 8 24" fill="none" stroke="currentColor" stroke-width="1.3" style="width:8px;height:20px;color:var(--text-tertiary)"><line x1="4" y1="0" x2="4" y2="24"/><polyline points="1,18 4,24 7,18"/></svg>
              </div>
              <!-- 타겟 -->
              <div class="flow-node tgt-node">타겟<br/><span>{{ tgtConn.db_type }}</span></div>
            </div>
            <!-- 실행 버튼 -->
            <div class="flow-run">
              <svg viewBox="0 0 8 16" fill="none" stroke="currentColor" stroke-width="1.3" style="width:8px;height:14px;color:var(--text-tertiary)"><line x1="4" y1="0" x2="4" y2="16"/><polyline points="1,11 4,16 7,11"/></svg>
              <button v-if="srcFiles.length" class="run-all-btn" @click="runAll" :disabled="running">
                <span v-if="running" class="spinner" style="width:11px;height:11px;display:inline-block;border-top-color:#fff"></span>
                <svg v-else viewBox="0 0 14 14" fill="none" stroke="white" stroke-width="2" style="width:12px;height:12px"><polygon points="2,2 12,7 2,12"/></svg>
                                <span v-if="running" style="font-size:9px;font-weight:700">{{ runProg }}/{{ srcFiles.length }}</span><span v-else style="font-size:9px;font-weight:700">쿼리실행</span>
              </button>
            </div>
          </template>

          <!-- 변환 안함 -->
          <template v-else>
            <div class="fp-mid-flow noconv">
              <!-- 소스 -->
              <div class="flow-node src-node">소스<br/><span>{{ srcConn.db_type }}</span></div>
              <!-- 직선 화살표 (변환 없음) -->
              <div class="flow-noconv-arr">
                <svg viewBox="0 0 8 32" fill="none" stroke="currentColor" stroke-width="1.3" style="width:8px;height:28px;color:var(--border-mid)"><line x1="4" y1="0" x2="4" y2="32"/><polyline points="1,26 4,32 7,26"/></svg>
                <div class="flow-noconv-badge">직접 비교</div>
              </div>
              <!-- 타겟 -->
              <div class="flow-node tgt-node">타겟<br/><span>{{ tgtConn.db_type }}</span></div>
            </div>
            <!-- 쿼리 실행 버튼 -->
            <div class="flow-run">
              <svg viewBox="0 0 8 16" fill="none" stroke="currentColor" stroke-width="1.3" style="width:8px;height:14px;color:var(--text-tertiary)"><line x1="4" y1="0" x2="4" y2="16"/><polyline points="1,11 4,16 7,11"/></svg>
              <button v-if="srcFiles.length" class="run-all-btn exec-btn" @click="runAll" :disabled="running">
                <span v-if="running" class="spinner" style="width:11px;height:11px;display:inline-block;border-top-color:#fff"></span>
                <svg v-else viewBox="0 0 14 14" fill="none" stroke="white" stroke-width="2" style="width:12px;height:12px"><polygon points="2,2 12,7 2,12"/></svg>
                <span v-if="running" style="font-size:9px;font-weight:700">{{ runProg }}/{{ srcFiles.length }}</span>
                <span v-else style="font-size:9px;font-weight:700">쿼리실행</span>
              </button>
            </div>
          </template>

          <button v-if="fileResults.some(r=>r)" class="report-btn" @click="exportReport" title="검증 리포트 다운로드">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:12px;height:12px">
            <rect x="2" y="1" width="10" height="12" rx="1"/><line x1="4" y1="5" x2="10" y2="5"/><line x1="4" y1="8" x2="8" y2="8"/>
          </svg>
        </button>
        </div>

        <!-- 타겟 패널 -->
        <div class="fp-panel card">
          <div class="fp-hdr tgt">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" style="width:12px;height:12px"><path d="M2 2h8l2 2v8H2z"/></svg>
            타겟 ({{ tgtConn.db_type }})
            <span v-if="tgtPath" class="fp-path">
              📁 {{ tgtPath }}
            </span>
            <span v-if="tgtFiles.length" class="fp-cnt">{{ tgtFiles.length }}개</span>
            <button v-if="tgtFiles.length" class="fp-clear" @click="clearTgt" title="타겟 초기화">×</button>
            <div v-if="convMethod==='none'" style="margin-left:auto">
              <button v-if="inputMode==='file'" class="fp-sel-btn tgt" @click="$refs.tgtFileInp.click()">파일 선택</button>
              <button v-else class="fp-sel-btn tgt" @click="$refs.tgtFolderInp.click()">폴더 선택</button>
              <input ref="tgtFileInp"   type="file" accept=".sql,.txt" multiple  style="display:none" @change="onTgtFileSelect"/>
              <input ref="tgtFolderInp" type="file" webkitdirectory              style="display:none" @change="onTgtFolderSelect"/>
            </div>
          </div>

          <!-- 변환 안함이 아닐 때: 안내 메시지 -->
          <div v-if="convMethod!=='none'" class="fp-auto-msg">
            <div class="auto-icon">
              <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" style="width:28px;height:28px;opacity:.5"><circle cx="10" cy="10" r="8"/><path d="M7 10 L10 13 L14 7"/></svg>
            </div>
            <div style="font-size:12.5px;font-weight:600;color:var(--text-secondary);margin-top:6px">
              {{ convMethod==='claude' ? '✦ Claude AI 자동 변환' : '⚙ 규칙 기반 자동 변환' }}
            </div>
            <div style="font-size:11px;color:var(--text-tertiary);margin-top:4px">
              소스 쿼리를 {{ tgtConn.db_type }} 문법으로<br/>자동 변환 후 실행합니다
            </div>
            <div style="font-size:11px;color:var(--text-warning);margin-top:8px;padding:5px 10px;background:var(--bg-warning);border-radius:var(--radius-sm)">
              타겟 폴더를 선택하려면<br/>위에서 <b>변환 안함</b>을 선택하세요
            </div>
            <div v-if="convMethod==='claude'&&!apiAvail" style="font-size:11px;color:var(--text-warning);margin-top:6px;background:var(--bg-warning);padding:4px 10px;border-radius:var(--radius-sm)">
              ⚠ API 키 미설정 → 규칙 기반 폴백
            </div>
          </div>

          <!-- 변환 안함: 드롭존 또는 파일 목록 -->
          <template v-else>
            <div v-if="!tgtFiles.length" class="fp-drop"
                 @dragover.prevent @drop.prevent="onDrop($event,'tgt')"
                 @click="inputMode==='file'?$refs.tgtFileInp.click():$refs.tgtFolderInp.click()">
              <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1" style="width:36px;height:36px;opacity:.35">
                <path v-if="inputMode==='folder'" d="M2 6h10l2 3h16v19H2z"/>
                <path v-else d="M4 4h16l6 6v18H4z"/><polyline v-if="inputMode==='file'" points="20,4 20,10 26,10"/>
              </svg>
              <div style="font-size:13px;color:var(--text-secondary);margin-top:8px">
                {{ inputMode==='folder' ? '타겟 폴더 클릭 또는 드래그' : '타겟 .sql/.txt 파일 클릭 또는 드래그' }}
              </div>
              <div style="font-size:11px;color:var(--text-tertiary);margin-top:4px">
                같은 파일명 또는 <code>_trans</code> 접미사로 자동 매핑
              </div>
            </div>

            <div v-else class="fp-list">
              <div v-for="(f,i) in tgtFiles" :key="i" class="fp-item tgt-item">
                <span class="fnum tgt-num">{{ i+1 }}</span>
                <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.2" style="width:11px;height:11px;flex-shrink:0;color:var(--text-tertiary)"><path d="M1 1h7l2 2v8H1z"/></svg>
                <span class="fname">{{ f.name }}</span>
                <span class="fsize">{{ fmtSize(f.size) }}</span>
                <span v-if="getMappedSrc(i)" class="map-badge ok">↔ {{ getMappedSrc(i) }}</span>
                <span v-else class="map-badge miss">미매핑</span>
                <button class="frm" @click.stop="tgtFiles.splice(i,1);fileResults=[]">×</button>
              </div>
            </div>
          </template>
        </div>
      </div>

      <!-- 매핑 요약 (파일/폴더 모두 선택됐을 때) -->
      <div v-if="filePairs.length" class="pair-summary card">
        <div class="ps-hdr">
          <span class="ps-title">파일 매핑 현황</span>
          <span class="schip info">총 {{ filePairs.length }}쌍</span>
          <span class="schip ok">일치 {{ fileResults.filter(r=>r?.comparison?.match).length }}</span>
          <span class="schip fail">불일치 {{ fileResults.filter(r=>r&&!r.comparison?.match).length }}</span>
          <span class="schip pend">대기 {{ filePairs.length - fileResults.filter(r=>r).length }}</span>
        </div>
        <div class="ps-table">
          <div class="ps-row hdr">
            <span style="width:24px">#</span>
            <span style="flex:1">소스 파일</span>
            <span style="width:16px"></span>
            <span style="flex:1">타겟 ({{ convMethod==='none'?'파일':'자동변환' }})</span>
            <span style="width:130px;text-align:center">결과</span>
          </div>
          <div v-for="(p,i) in filePairs" :key="i" class="ps-row"
               :class="{active:activePair===i, 'has-result':!!fileResults[i]}"
               @click="showResult(i)">
            <span style="width:24px;color:var(--text-tertiary);font-size:10px">{{ i+1 }}</span>
            <span class="ps-name src">{{ p.srcName }}</span>
            <span style="width:16px;text-align:center;font-size:10px;color:var(--text-tertiary)">→</span>
            <span class="ps-name tgt" :class="{auto:!p.tgtFile}">
              {{ p.tgtFile ? p.tgtName : (convMethod==='none' ? '⚠ 미매핑' : '자동 변환') }}
            </span>
            <span style="width:130px;text-align:center">
              <template v-if="fileResults[i]">
                <span class="res-pill" :class="fileResults[i].comparison?.match?'ok':'fail'">
                  {{ fileResults[i].comparison?.match ? '✓ 일치' : '✗ ' + (fileResults[i].comparison?.reason?.slice(0,18)||'불일치') }}
                </span>
              </template>
              <span v-else-if="runningIdx===i" class="res-pill running">
                <span class="spinner" style="width:8px;height:8px;display:inline-block;margin-right:3px"></span>실행 중
              </span>
              <span v-else class="res-pill pend">대기</span>
            </span>
          </div>
        </div>
      </div>
    </template>

    <!-- ══ 변환 정보 바 ══════════════════════════════════════════════ -->
    <div v-if="convInfo&&convInfo.method!=='none'" class="conv-bar">
      <span class="cv-badge" :class="convInfo.method==='claude-ai'?'ai':convInfo.method==='rules_fallback'?'warn':'rule'">
        {{ convInfo.method==='claude-ai' ? '✦ Claude AI' : convInfo.method==='rules_fallback' ? '⚠ 규칙 폴백' : '⚙ 규칙 기반' }}
      </span>
      <span v-for="c in convInfo.changes" :key="c" class="ctag ok">✓ {{ c }}</span>
      <span v-for="w in convInfo.warnings" :key="w" class="ctag warn">⚠ {{ w }}</span>
    </div>

    <!-- ══ 비교 결과 ══════════════════════════════════════════════════ -->
    <div v-if="result">
      <!-- 배너 -->
      <div class="cmp-banner" :class="result.comparison.match?'match':'diff'">
        <div class="cb-icon">{{ result.comparison.match?'✓':'✗' }}</div>
        <div>
          <div class="cb-title">{{ result.comparison.match?'결과 일치':'결과 불일치' }}</div>
          <div class="cb-sub">{{ result.comparison.reason }}</div>
        </div>
        <div class="cb-stats">
          <div class="cs"><span>소스 rows</span><b>{{ result.src.row_count }}</b></div>
          <div class="cs"><span>타겟 rows</span><b>{{ result.tgt.row_count }}</b></div>
          <div class="cs"><span>소스 시간</span><b>{{ result.src.elapsed_ms }}ms</b></div>
          <div class="cs"><span>타겟 시간</span><b>{{ result.tgt.elapsed_ms }}ms</b></div>
        </div>
      </div>

      <!-- 불일치 상세 -->
      <div v-if="!result.comparison.match && result.comparison.diff_rows?.length" class="card diff-detail">
        <div class="card-header">⚠ 불일치 상세 ({{ result.comparison.diff_rows.length }}개 행)</div>
        <div v-for="dr in result.comparison.diff_rows" :key="dr.row" class="dr">
          <span class="dr-num">행 {{ dr.row }}</span>
          <div v-for="d in dr.diffs" :key="d.col_src" class="dc">
            <span class="dcn">{{ d.col_src }}</span>
            <span class="dcs">{{ d.src }}</span>
            <span style="color:var(--text-tertiary)">≠</span>
            <span class="dct">{{ d.tgt }}</span>
          </div>
        </div>
      </div>

      <!-- 오류 -->
      <div v-if="!result.src.ok||!result.tgt.ok" class="card" style="padding:12px 16px;margin-bottom:10px">
        <div v-if="!result.src.ok" class="err-banner" style="margin-bottom:6px">소스 오류: {{ result.src.error }}</div>
        <div v-if="!result.tgt.ok" class="err-banner">타겟 오류: {{ result.tgt.error }}</div>
      </div>

      <!-- 양쪽 결과 테이블 -->
      <div class="res-layout">
        <div class="card res-card" v-for="side in ['src','tgt']" :key="side">
          <div class="rc-hdr" :class="side">
            {{ side==='src'?'소스':'타겟' }} ({{ side==='src'?srcConn.db_type:tgtConn.db_type }})
            <span class="rc-badge">{{ result[side].row_count }}행 · {{ result[side].elapsed_ms }}ms</span>
          </div>
          <div v-if="!result[side].ok" class="empty-state" style="padding:14px;color:var(--text-danger)">{{ result[side].error }}</div>
          <div v-else-if="!result[side].rows.length" class="empty-state" style="padding:14px">결과 없음 (0행)</div>
          <div v-else class="tbl-wrap">
            <table class="res-tbl">
              <thead><tr><th v-for="c in result[side].cols" :key="c">{{ c }}</th></tr></thead>
              <tbody>
                <tr v-for="(row,ri) in result[side].rows" :key="ri" :class="{diffrow:isDiffRow(ri)}">
                  <td v-for="(v,ci) in row" :key="ci" :class="{diffcell:side==='src'&&isDiffCell(ri,ci)}">
                    <span v-if="v===null" class="nv">NULL</span><span v-else>{{ v }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, watch } from 'vue'
import { useConnectorStore } from '@/store/connectorStore.js'
import axios from 'axios'

const connector = useConnectorStore()

const dbs = [
  {v:'mssql',n:'SQL Server'},{v:'mysql',n:'MySQL'},{v:'mariadb',n:'MariaDB'},
  {v:'postgresql',n:'PostgreSQL'},{v:'aurora',n:'Aurora'},{v:'tidb',n:'TiDB'},
]

// --  ----------------------------------------------
const srcConn = reactive({db_type:'mssql',host:'',port:'1434',database:'',username:'',password:''})
const tgtConn = reactive({db_type:'mysql',host:'',port:'3306',database:'',username:'',password:''})

// Vue reactive Proxy  JSON   plain object 
function connPlain(c) {
  const dbType = String(c.db_type || '')
  const defPort = (dbType==='mssql'||dbType==='azure') ? 1434 : (dbType==='postgresql'?5432:3306)
  return {
    db_type:  dbType,
    host:     String(c.host     || ''),
    port:     Number(c.port)    || defPort,
    database: String(c.database || ''),
    username: String(c.username || ''),
    password: String(c.password || ''),
  }
}
const testing = reactive({src:false,tgt:false})
const connMsg = reactive({src:null,tgt:null})
const connOk  = reactive({src:false,tgt:false})

async function loadConn(side) {
  // store  
  const c = side==='src' ? connector.source : connector.target
  if (c && c.host) {
    applyStore(side, c)
    connMsg[side] = { ok:true, msg:'커넥터에서 불러옴' }
    connOk[side]  = true
    return
  }
  // store   API 
  try {
    const {data: profiles} = await axios.get('/api/v1/connector/profiles')
    if (profiles && profiles.length > 0) {
      const p = profiles[0]
      const src_or_tgt = side==='src' ? p.source : p.target
      if (src_or_tgt && src_or_tgt.host) {
        applyStore(side, {
          dbType: src_or_tgt.dbType, host: src_or_tgt.host,
          port: src_or_tgt.port,     database: src_or_tgt.database,
          username: src_or_tgt.username, password: src_or_tgt.password,
        })
        connMsg[side] = { ok:true, msg:'프로파일에서 불러옴' }
        connOk[side]  = true
        return
      }
    }
    alert('저장된 커넥터 프로파일이 없습니다. 커넥터 관리에서 먼저 연결하세요.')
  } catch {
    alert('커넥터 정보를 불러오는 데 실패했습니다.')
  }
}
function swapConns() {
  const tmp={...srcConn}; Object.assign(srcConn,tgtConn); Object.assign(tgtConn,tmp)
  const t=srcSql.value; srcSql.value=tgtSql.value; tgtSql.value=t
}
//    -     connOk=true ( )
async function connectAndSave(side) {
  const c = side==='src' ? srcConn : tgtConn
  testing[side] = true; connMsg[side] = null
  try {
    await axios.post('/api/v1/schema/connection', {
      db_type: c.db_type, host: c.host, port: Number(c.port)||0,
      username: c.username, password: c.password||'', database: c.database
    })
    connMsg[side] = { ok:true, msg:'연결 성공' }
    connOk[side]  = true  // 폼 접힘
  } catch(e) {
    connMsg[side] = { ok:false, msg:'실패: '+(e.response?.data?.detail||e.message).slice(0,50) }
    connOk[side]  = false
  } finally { testing[side] = false }
}

async function testConn(side) {
  await connectAndSave(side)
}

// --  ----------------------------------------------
const inputMode  = ref('text')
const convMethod = ref('auto')
const maxRows    = ref(200)
const apiAvail   = ref(false)

const convLabel = computed(() => ({
  auto:   '자동 변환',
  claude: 'Claude AI 변환',
  none:   '변환 안함',
}[convMethod.value]))

// -- connectorStore   (setup ) ------------------------
function applyStore(side, s) {
  const t = side === 'src' ? srcConn : tgtConn
  if (!s || !s.host) return
  t.db_type  = s.dbType || s.db_type || (side==='src'?'mssql':'mysql')
  t.host     = s.host     || ''
  t.port     = String(s.port || (t.db_type==='mssql'||t.db_type==='azure'?1434:t.db_type==='postgresql'?5432:3306))
  t.database = s.database || ''
  t.username = s.username || ''
  t.password = s.password || ''
}

//     
watch(() => connector.source, (s) => applyStore('src', s), { immediate:true, deep:true })
watch(() => connector.target, (t) => applyStore('tgt', t), { immediate:true, deep:true })

onMounted(async () => {
  // 1)      (store  )
  try {
    const {data: profiles} = await axios.get('/api/v1/connector/profiles')
    if (profiles && profiles.length > 0) {
      //    
      const p = profiles[0]
      if (p.source && p.source.host) {
        srcConn.db_type  = p.source.dbType || p.source.db_type || 'mssql'
        srcConn.host     = p.source.host     || ''
        srcConn.port     = String(p.source.port || 1434)
        srcConn.database = p.source.database  || ''
        srcConn.username = p.source.username  || ''
        srcConn.password = p.source.password  || ''
        connOk.src = p.source.status === 'ok'
      }
      if (p.target && p.target.host) {
        tgtConn.db_type  = p.target.dbType || p.target.db_type || 'mysql'
        tgtConn.host     = p.target.host     || ''
        tgtConn.port     = String(p.target.port || 3306)
        tgtConn.database = p.target.database  || ''
        tgtConn.username = p.target.username  || ''
        tgtConn.password = p.target.password  || ''
        connOk.tgt = p.target.status === 'ok'
      }
    }
  } catch {}

  // 2) store   (store   )
  autoLoadFromStore()

  // 3) Claude API  
  try {
    const {data}=await axios.post('/api/v1/sql-converter/convert-ai',{sql:'SELECT 1',src_db:'mysql',tgt_db:'mssql'})
    apiAvail.value=data.api_available||false
  } catch {}
})

// ensureConnInfo:       
async function ensureConnInfo() {
  // 1) UI      
  if (srcConn.host && srcConn.database) return
  // 2) store 
  autoLoadFromStore()
  if (srcConn.host && srcConn.database) return
  // 3)  API 
  try {
    const {data: profiles} = await axios.get('/api/v1/connector/profiles')
    if (profiles && profiles.length > 0) {
      const p = profiles[0]
      if (p.source && p.source.host && !srcConn.host) {
        srcConn.db_type  = p.source.dbType || p.source.db_type || 'mssql'
        srcConn.host     = p.source.host
        srcConn.port     = String(p.source.port || 1434)
        srcConn.database = p.source.database || ''
        srcConn.username = p.source.username || ''
        srcConn.password = p.source.password || ''
      }
      if (p.target && p.target.host && !tgtConn.host) {
        tgtConn.db_type  = p.target.dbType || p.target.db_type || 'mysql'
        tgtConn.host     = p.target.host
        tgtConn.port     = String(p.target.port || 3306)
        tgtConn.database = p.target.database || ''
        tgtConn.username = p.target.username || ''
        tgtConn.password = p.target.password || ''
      }
    }
  } catch {}
}

function autoLoadFromStore() {
  const src = connector.source
  const tgt = connector.target
  if (src && src.host) {
    srcConn.db_type  = src.dbType || src.db_type || 'mssql'
    srcConn.host     = src.host
    srcConn.port     = String(src.port || 1434)
    srcConn.database = src.database || ''
    srcConn.username = src.username || ''
    srcConn.password = src.password || ''
    connOk.src = src.status === 'ok'
  }
  if (tgt && tgt.host) {
    tgtConn.db_type  = tgt.dbType || tgt.db_type || 'mysql'
    tgtConn.host     = tgt.host
    tgtConn.port     = String(tgt.port || 3306)
    tgtConn.database = tgt.database || ''
    tgtConn.username = tgt.username || ''
    tgtConn.password = tgt.password || ''
    connOk.tgt = tgt.status === 'ok'
  }
}

function setMode(m) {
  inputMode.value=m
  clearAll()
}

function clearAll() {
  srcPath.value = ''; tgtPath.value = ''
  srcFiles.value=[]; tgtFiles.value=[]
  fileResults.value=[]; activePair.value=-1; runningIdx.value=-1
  srcSql.value=''; tgtSql.value=''; result.value=null; convInfo.value=null
}

function clearSrc() {
  srcFiles.value = []; fileResults.value = []; srcPath.value = ''
}
function clearTgt() {
  tgtFiles.value = []; fileResults.value = []; tgtPath.value = ''
}

// --   ----------------------------------------
async function doConvert(sql) {
  if (convMethod.value==='none') return {converted:sql,changes:[],warnings:[],method:'none'}
  const ep = (convMethod.value==='claude'||convMethod.value==='auto')
    ? '/api/v1/sql-converter/convert-ai'
    : '/api/v1/sql-converter/convert'
  const {data}=await axios.post(ep,{sql,src_db:srcConn.db_type,tgt_db:tgtConn.db_type})
  return data
}

// --   --------------------------------------
const srcSql  = ref('')
const tgtSql  = ref('')
const running = ref(false)
const result  = ref(null)
const convInfo= ref(null)

let cvTimer=null
function onSrcInput() {
  if (convMethod.value==='none'||!srcSql.value.trim()) return
  clearTimeout(cvTimer); cvTimer=setTimeout(()=>convertOnly(),700)
}
async function convertOnly() {
  if (!srcSql.value.trim()) return
  try { const r=await doConvert(srcSql.value); tgtSql.value=r.converted; convInfo.value=r } catch {}
}
async function runText() {
  if (!srcSql.value.trim()&&!tgtSql.value.trim()) return
  //   : /store 
  await ensureConnInfo()
  // connOk true    -  
  const sp = connPlain(srcConn), tp = connPlain(tgtConn)
  if (!connOk.src && (!sp.host || !sp.database)) {
    // connOk    - srcConn   
    //   
    const msg = '소스 DB 연결 정보가 없습니다.\n' +
      '방법 1: 위의 소스 DB 필드에 직접 호스트/DB명 입력 후 연결 테스트\n' +
      '방법 2: 커넥터 관리에서 먼저 연결 후 커넥터 불러오기 클릭'
    alert(msg)
    return
  }
  running.value=true; result.value=null
  try {
    let tgt=tgtSql.value
    if (convMethod.value!=='none'&&srcSql.value.trim()) {
      const r=await doConvert(srcSql.value); tgt=r.converted; tgtSql.value=tgt; convInfo.value=r
    }
    const {data}=await axios.post('/api/v1/sql-converter/compare',{
      src_sql:srcSql.value,tgt_sql:tgt,src_conn:connPlain(srcConn),tgt_conn:connPlain(tgtConn),max_rows:Number(maxRows.value)
    },{timeout:60000})
    result.value=data
  } catch(e) {alert('실행 실패: '+(e.response?.data?.detail||e.message))}
  finally {running.value=false}
}

// -- /:  ----------------------------------
const srcFiles   = ref([])
const srcPath      = ref('')
const tgtPath      = ref('')
const tgtFiles   = ref([])
const fileResults= ref([])
const activePair = ref(-1)
const runningIdx = ref(-1)
const runProg    = ref(0)

function onSrcFileSelect(e) {
  const files = [...e.target.files]
  srcFiles.value=[...files.map(f=>({name:f.name,size:f.size,file:f}))]
  srcPath.value = files.length ? '파일 ' + files.length + '개 선택됨' : ''
  fileResults.value=[]; e.target.value=''
}
function onSrcFolderSelect(e) {
  const files = [...e.target.files].filter(f=>f.name.match(/\.(sql|txt)$/i))
  srcFiles.value=[...files.map(f=>({name:f.name,size:f.size,file:f}))]
  // : webkitRelativePath   
  if (files.length) {
    const rel = files[0].webkitRelativePath || ''
    srcPath.value = rel ? rel.replace(/\\/g, '/').split('/').slice(0,-1).join('/') : '폴더 선택됨'
  } else { srcPath.value = '' }
  fileResults.value=[]; e.target.value=''
}
function onTgtFileSelect(e) {
  const files = [...e.target.files]
  tgtFiles.value=[...files.map(f=>({name:f.name,size:f.size,file:f}))]
  tgtPath.value = files.length ? '파일 ' + files.length + '개 선택됨' : ''
  fileResults.value=[]; e.target.value=''
}
function onTgtFolderSelect(e) {
  const files = [...e.target.files].filter(f=>f.name.match(/\.(sql|txt)$/i))
  tgtFiles.value=[...files.map(f=>({name:f.name,size:f.size,file:f}))]
  if (files.length) {
    const rel = files[0].webkitRelativePath || ''
    tgtPath.value = rel ? rel.replace(/\\/g, '/').split('/').slice(0,-1).join('/') : '폴더 선택됨'
  } else { tgtPath.value = '' }
  fileResults.value=[]; e.target.value=''
}
function onDrop(e,side) {
  const files=[...e.dataTransfer.files].filter(f=>f.name.match(/\.(sql|txt)$/i)).map(f=>({name:f.name,size:f.size,file:f}))
  if (side==='src') { srcFiles.value=[...srcFiles.value,...files]; if(files.length) srcPath.value='드래그 '+files.length+'개' }
  else { tgtFiles.value=[...tgtFiles.value,...files]; if(files.length) tgtPath.value='드래그 '+files.length+'개' }
  fileResults.value=[]
}
function removeSrc(i) { srcFiles.value.splice(i,1); fileResults.value.splice(i,1) }

//     
function getMappedSrc(tgtIdx) {
  const tf=tgtFiles.value[tgtIdx]; if (!tf) return ''
  const tb=tf.name.replace(/\.(sql|txt)$/i,'').replace(/(_trans|_converted)$/i,'')
  const sf=srcFiles.value.find(sf=>{
    const sb=sf.name.replace(/\.(sql|txt)$/i,'').replace(/(_trans|_converted)$/i,'')
    return sb===tb || sf.name===tf.name
  })
  return sf ? sf.name : ''
}

//   
const filePairs = computed(() => {
  if (!srcFiles.value.length) return []
  return srcFiles.value.map(sf => {
    const base=sf.name.replace(/\.(sql|txt)$/i,'').replace(/(_trans|_converted)$/i,'')
    let tgtFile=null

    if (tgtFiles.value.length) {
      // 1.   
      tgtFile=tgtFiles.value.find(tf=>tf.name===sf.name)
      // 2. base_trans.sql / base_converted.sql
      if (!tgtFile) tgtFile=tgtFiles.value.find(tf=>{
        const tb=tf.name.replace(/\.(sql|txt)$/i,'')
        return tb===base+'_trans'||tb===base+'_converted'
      })
      // 3. _trans   base  
      if (!tgtFile) tgtFile=tgtFiles.value.find(tf=>{
        const tb=tf.name.replace(/\.(sql|txt)$/i,'').replace(/(_trans|_converted)$/i,'')
        return tb===base
      })
    }
    return {srcFile:sf.file,srcName:sf.name,tgtFile:tgtFile?.file||null,tgtName:tgtFile?.name||null}
  })
})

async function previewSrc(i) {
  activePair.value=i
  if (fileResults.value[i]) {
    result.value=fileResults.value[i]
    return
  }
  //   
  const f=srcFiles.value[i]
  if (f) srcSql.value=await f.file.text()
}

async function runAll() {
  if (!srcFiles.value.length) return
  //   : /store 
  await ensureConnInfo()
  //   
  const sp = connPlain(srcConn), tp = connPlain(tgtConn)
  if (!sp.host || !sp.database) {
    // connOk    - srcConn   
    //   
    const msg = '소스 DB 연결 정보가 없습니다.\n' +
      '방법 1: 위의 소스 DB 필드에 직접 호스트/DB명 입력 후 연결 테스트\n' +
      '방법 2: 커넥터 관리에서 먼저 연결 후 커넥터 불러오기 클릭'
    alert(msg)
    return
  }
  if (!tp.host || !tp.database) {
    alert('타겟 DB 연결 정보가 없습니다.\n커넥터 관리에서 연결 후 "커넥터 불러오기"를 클릭하세요.')
    return
  }
  running.value=true; runProg.value=0
  fileResults.value=new Array(srcFiles.value.length).fill(null)
  for (let i=0;i<filePairs.value.length;i++) {
    runningIdx.value=i; runProg.value=i
    const p=filePairs.value[i]
    try {
      const srcText=await p.srcFile.text()
      let tgtText
      if (p.tgtFile) {
        tgtText=await p.tgtFile.text()
      } else if (convMethod.value==='none') {
        fileResults.value[i]={
          comparison:{match:false,reason:'타겟 파일 없음 - 변환 안함 모드에서는 타겟 파일 필요'},
          src:{ok:false,error:'타겟 파일 없음',rows:[],cols:[],elapsed_ms:0,row_count:0},
          tgt:{ok:false,error:'',rows:[],cols:[],elapsed_ms:0,row_count:0}
        }; continue
      } else {
        const r=await doConvert(srcText); tgtText=r.converted; convInfo.value=r
      }
      const {data}=await axios.post('/api/v1/sql-converter/compare',{
        src_sql:srcText,tgt_sql:tgtText,src_conn:connPlain(srcConn),tgt_conn:connPlain(tgtConn),max_rows:Number(maxRows.value)
      },{timeout:60000})
      fileResults.value[i]=data
    } catch(e) {
      fileResults.value[i]={
        comparison:{match:false,reason:'오류: '+e.message},
        src:{ok:false,error:e.message,rows:[],cols:[],elapsed_ms:0,row_count:0},
        tgt:{ok:false,error:'',rows:[],cols:[],elapsed_ms:0,row_count:0}
      }
    }
  }
  runningIdx.value=-1; runProg.value=srcFiles.value.length; running.value=false
  if (filePairs.value.length>0) showResult(filePairs.value.length-1)
}

async function showResult(i) {
  activePair.value=i
  const r=fileResults.value[i]; if (!r) return
  result.value=r
  const p=filePairs.value[i]; if (!p) return
  srcSql.value=await p.srcFile.text()
  if (p.tgtFile) tgtSql.value=await p.tgtFile.text()
}

function exportReport() {
  const lines=['DataBridge Studio — 쿼리 검증 리포트',
    `생성: ${new Date().toLocaleString('ko-KR')}`,
    `소스: ${srcConn.db_type}/${srcConn.database}  타겟: ${tgtConn.db_type}/${tgtConn.database}`,
    `변환 방식: ${convLabel.value}`,
    `총 ${filePairs.value.length}쌍  일치 ${fileResults.value.filter(r=>r?.comparison?.match).length}  불일치 ${fileResults.value.filter(r=>r&&!r.comparison?.match).length}`,
    '='.repeat(60)]
  filePairs.value.forEach((p,i)=>{
    const r=fileResults.value[i]
    if (!r){lines.push(`\n[${p.srcName}] 미실행`);return}
    lines.push(`\n[${p.srcName}] ->[${p.tgtName||'자동변환'}] ${r.comparison.match?'- 일치':'- 불일치'}: ${r.comparison.reason}`)
    r.comparison.diff_rows?.forEach(dr=>dr.diffs.forEach(d=>lines.push(`  행${dr.row} ${d.col_src}: [${d.src}] != [${d.tgt}]`)))
  })
  const a=document.createElement('a')
  a.href=URL.createObjectURL(new Blob([lines.join('\n')],{type:'text/plain;charset=utf-8'}))
  a.download=`verify_${Date.now()}.txt`; a.click()
}

// --   --------------------------------
const diffRowSet=computed(()=>new Set((result.value?.comparison?.diff_rows||[]).map(d=>d.row-1)))
const diffCellMap=computed(()=>{
  const m={}
  ;(result.value?.comparison?.diff_rows||[]).forEach(dr=>{
    m[dr.row-1]=m[dr.row-1]||new Set()
    dr.diffs.forEach(d=>{const ci=result.value.src.cols.indexOf(d.col_src);if(ci>=0)m[dr.row-1].add(ci)})
  }); return m
})
function isDiffRow(ri){return diffRowSet.value.has(ri)}
function isDiffCell(ri,ci){return diffCellMap.value[ri]?.has(ci)}
function fmtSize(b){return b>1048576?(b/1048576).toFixed(1)+'MB':b>1024?(b/1024).toFixed(0)+'KB':b+'B'}
</script>

<style scoped>
/* ── 연결 ──────────────────────────────────────────────────── */
.cfg-card{padding:14px 16px;margin-bottom:10px}
.cfg-row{display:flex;align-items:stretch;gap:12px}
.conn-block{flex:1;min-width:0}

/* 연결됨 요약 */
.conn-summary{display:flex;align-items:center;justify-content:space-between;background:var(--bg-success,rgba(16,185,129,.06));border:0.5px solid var(--accent-green,#10b981);border-radius:var(--radius-md);padding:12px 14px;min-height:80px}
.conn-summary-left{display:flex;align-items:center;gap:10px}
.conn-summary-title{font-size:12px;font-weight:600;color:var(--text-success);margin-bottom:3px}
.conn-summary-sub{font-size:11px;color:var(--text-secondary);display:flex;align-items:center;gap:5px;flex-wrap:wrap}
.db-type-tag{font-size:10px;font-weight:700;padding:1px 6px;border-radius:4px;background:var(--bg-info);color:var(--text-info);text-transform:uppercase}
.conn-change-btn{font-size:11px;padding:4px 10px;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:var(--bg-primary);color:var(--text-secondary);cursor:pointer;white-space:nowrap}
.conn-change-btn:hover{border-color:var(--accent-blue);color:var(--text-info)}

/* 미연결 폼 */
.conn-title{display:flex;align-items:center;gap:6px;font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:8px}
.conn-hint{font-size:10.5px;font-weight:400;color:var(--text-tertiary);margin-left:2px}
.conn-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.conn-dot.on{background:#4ade80;box-shadow:0 0 5px #4ade8055}.conn-dot.off{background:var(--border-mid)}
.conn-fields{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:8px}
.f-inp{font-size:11.5px;padding:4px 8px;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:var(--bg-secondary);color:var(--text-primary);min-width:90px;flex:1}
.f-inp.sm{max-width:70px;min-width:50px;flex:none}
.f-sel{font-size:11.5px;padding:4px 8px;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:var(--bg-secondary);color:var(--text-primary)}
.conn-foot{display:flex;align-items:center;gap:6px}
.conn-btn{display:inline-flex;align-items:center;gap:5px;padding:5px 14px;border-radius:var(--radius-sm);border:none;background:var(--accent-blue);color:#fff;font-size:11.5px;font-weight:600;cursor:pointer;font-family:var(--font);transition:all .12s}
.conn-btn:hover:not(:disabled){background:#2563eb}.conn-btn:disabled{opacity:.5;cursor:not-allowed}
.cmsg{font-size:11px;font-weight:500}.cmsg.ok{color:var(--text-success)}.cmsg.err{color:var(--text-danger)}
.swap-col{display:flex;align-items:center;justify-content:center;padding:0 4px}
.swap-btn{width:32px;height:32px;border-radius:50%;border:0.5px solid var(--border-mid);background:var(--bg-secondary);color:var(--text-secondary);cursor:pointer;display:flex;align-items:center;justify-content:center}
.swap-btn:hover{background:var(--bg-hover)}

/* ── 옵션 바 ───────────────────────────────────────────────── */
.opt-bar{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;margin-bottom:10px;flex-wrap:wrap;gap:8px}
.mode-grp{display:flex;border:0.5px solid var(--border-mid);border-radius:var(--radius-sm);overflow:hidden}
.mtab{padding:5px 13px;font-size:11.5px;border:none;background:transparent;color:var(--text-secondary);cursor:pointer;transition:all .12s;display:flex;align-items:center;gap:4px}
.mtab.active{background:var(--accent-blue);color:#fff;font-weight:600}
.clear-btn{display:flex;align-items:center;gap:4px;padding:4px 10px;font-size:11px;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:transparent;color:var(--text-tertiary);cursor:pointer;transition:all .12s}
.clear-btn:hover{background:var(--bg-danger,rgba(163,45,45,.1));color:var(--text-danger);border-color:var(--text-danger)}
.cv-grp{display:flex;align-items:center;gap:5px;padding:4px 10px;border-radius:var(--radius-md);border:0.5px solid var(--border-mid);background:var(--bg-secondary)}
.cv-label{font-size:10px;color:var(--text-tertiary);margin-right:2px;white-space:nowrap}
.cv-seg-group{display:flex;align-items:center;gap:1px;background:var(--bg-tertiary,var(--bg-primary));border-radius:var(--radius-sm);padding:2px;border:0.5px solid var(--border-light)}
.cv-seg-label{font-size:9.5px;color:var(--text-tertiary);padding:0 5px;white-space:nowrap}
.cv-btn{padding:3px 9px;font-size:11px;border:none;background:transparent;color:var(--text-secondary);cursor:pointer;border-radius:calc(var(--radius-sm) - 1px);display:inline-flex;align-items:center;gap:3px;transition:all .15s;white-space:nowrap}
.cv-btn.active{background:var(--accent-blue);color:#fff;font-weight:600;box-shadow:0 1px 4px rgba(59,130,246,.3)}
.cv-btn:hover:not(.active){background:var(--bg-hover)}
.claude-btn.active{background:linear-gradient(135deg,#7c3aed,#4f46e5)}
.claude-spark{font-size:10px}
.none-btn{border-left:0.5px solid var(--border-mid);padding-left:9px}
.none-btn.active{background:var(--bg-secondary);color:var(--text-secondary);font-weight:600;box-shadow:none;border:0.5px solid var(--border-mid)}
.cv-divider{width:0.5px;height:20px;background:var(--border-mid);flex-shrink:0}
.api-ok{font-size:9px;background:#10b981;color:#fff;padding:1px 4px;border-radius:4px}
.api-na{font-size:9px;background:rgba(239,68,68,.15);color:var(--text-danger);padding:1px 4px;border-radius:4px}
.rows-sel{font-size:11.5px;padding:3px 8px;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:var(--bg-secondary);color:var(--text-primary)}

/* ── 텍스트 에디터 ─────────────────────────────────────────── */
.editor-grid{display:grid;grid-template-columns:1fr 56px 1fr;border:0.5px solid var(--border-light);border-radius:var(--radius-md);overflow:hidden;margin-bottom:10px}
.qpanel{display:flex;flex-direction:column}
.qph{padding:7px 12px;font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase}
.qph.src{background:rgba(59,130,246,.06);color:var(--text-info)}.qph.tgt{background:rgba(16,185,129,.06);color:var(--text-success)}
.sql-ed{flex:1;min-height:200px;padding:12px;font-family:'Consolas','SF Mono',monospace;font-size:12px;line-height:1.6;border:none;resize:none;background:var(--bg-primary);color:var(--text-primary);outline:none;border-right:0.5px solid var(--border-light)}
.qpanel:last-child .sql-ed{border-right:none;border-left:0.5px solid var(--border-light)}
.qpf{padding:4px 12px;font-size:10.5px;color:var(--text-tertiary);background:var(--bg-secondary);border-top:0.5px solid var(--border-light)}
.mid-col{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;padding:8px 4px;background:var(--bg-secondary)}
.run-btn{width:42px;height:42px;border-radius:50%;background:var(--accent-blue);border:none;cursor:pointer;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;color:#fff;transition:all .15s}
.run-btn:hover:not(:disabled){background:#2563eb;transform:scale(1.05)}.run-btn:disabled{opacity:.5;cursor:not-allowed}
.mini-act{font-size:10px;padding:3px 7px;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:transparent;color:var(--text-secondary);cursor:pointer}
.mini-act:hover{background:var(--bg-hover)}

/* ── 파일/폴더 2패널 레이아웃 ──────────────────────────────── */
.fp-layout{display:grid;grid-template-columns:1fr 64px 1fr;gap:0;margin-bottom:10px;align-items:start}
.fp-panel{padding:0;overflow:hidden;display:flex;flex-direction:column;min-height:200px}
.fp-hdr{display:flex;align-items:center;gap:6px;padding:8px 12px;border-bottom:0.5px solid var(--border-light);font-size:11.5px;font-weight:600}
.fp-hdr.src{color:var(--text-info)}.fp-hdr.tgt{color:var(--text-success)}
.fp-cnt{font-size:10px;background:var(--bg-info);color:var(--text-info);padding:1px 7px;border-radius:10px}
.fp-path{display:inline-flex;align-items:center;gap:4px;font-size:11px;font-weight:600;color:#1e293b;background:rgba(255,255,255,.9);border:none;padding:2px 9px;border-radius:10px;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:'Consolas','SF Mono',monospace;flex-shrink:0}
.fp-clear{padding:1px 6px;border:none;background:transparent;color:var(--text-tertiary);cursor:pointer;font-size:13px;line-height:1}
.fp-clear:hover{color:var(--text-danger)}
.fp-sel-btn{font-size:11px;padding:3px 10px;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:var(--bg-secondary);color:var(--text-secondary);cursor:pointer}
.fp-sel-btn:hover{background:var(--bg-hover)}.fp-sel-btn.tgt{border-color:var(--accent-green);color:var(--text-success)}

.fp-drop{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px 16px;cursor:pointer;border:1.5px dashed var(--border-mid);margin:12px;border-radius:var(--radius-md);transition:border-color .2s;flex:1}
.fp-drop:hover{border-color:var(--accent-blue)}

.fp-list{flex:1;overflow-y:auto;max-height:320px}
.fp-item{display:flex;align-items:center;gap:6px;padding:7px 12px;font-size:11.5px;border-bottom:0.5px solid var(--border-light);cursor:pointer;transition:background .12s}
.fp-item:last-child{border-bottom:none}
.fp-item:hover,.fp-item.active{background:var(--bg-hover)}
.fp-item.running{background:rgba(59,130,246,.06)}
.tgt-item:hover{background:rgba(16,185,129,.04)}
.fnum{width:18px;font-size:10px;color:var(--text-tertiary);text-align:right;flex-shrink:0}
.tgt-num{color:var(--text-success)}
.fname{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text-primary)}
.fsize{font-size:10px;color:var(--text-tertiary);flex-shrink:0}
.res-badge{font-size:10px;padding:1px 6px;border-radius:8px;font-weight:600;flex-shrink:0}
.res-badge.ok{background:var(--bg-success);color:var(--text-success)}
.res-badge.fail{background:rgba(239,68,68,.1);color:var(--text-danger)}
.res-badge.running{background:var(--bg-info);color:var(--text-info)}
.map-badge{font-size:9.5px;padding:1px 6px;border-radius:8px;font-weight:500;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:80px}
.map-badge.ok{background:var(--bg-success);color:var(--text-success)}.map-badge.miss{background:rgba(239,68,68,.1);color:var(--text-danger)}
.frm{padding:1px 5px;border:none;background:transparent;color:var(--text-tertiary);cursor:pointer;flex-shrink:0}
.frm:hover{color:var(--text-danger)}

/* ── 가운데 변환 컬럼 ──────────────────────────────────────── */
.fp-mid{display:flex;flex-direction:column;align-items:center;justify-content:flex-start;padding:16px 2px 0;gap:6px}
.fp-mid-flow{display:flex;flex-direction:column;align-items:center;gap:0;width:56px}
.flow-node{display:flex;flex-direction:column;align-items:center;justify-content:center;width:48px;height:36px;border-radius:var(--radius-sm);font-size:9px;font-weight:600;text-align:center;line-height:1.3;border:1px solid}
.flow-node span{font-size:8.5px;font-weight:500;opacity:.8}
.src-node{background:rgba(59,130,246,.08);border-color:rgba(59,130,246,.3);color:var(--text-info)}
.tgt-node{background:rgba(16,185,129,.08);border-color:rgba(16,185,129,.3);color:var(--text-success)}
.flow-conv{display:flex;flex-direction:column;align-items:center;gap:2px;padding:2px 0}
.flow-conv-badge{font-size:9px;font-weight:600;padding:2px 6px;border-radius:8px;white-space:nowrap}
.flow-conv-badge.ai{background:rgba(124,58,237,.12);color:#7c3aed;border:0.5px solid rgba(124,58,237,.25)}
.flow-conv-badge.rule{background:var(--bg-info);color:var(--text-info);border:0.5px solid rgba(59,130,246,.2)}
.flow-noconv-arr{display:flex;flex-direction:column;align-items:center;gap:2px;padding:3px 0}
.flow-noconv-badge{font-size:8.5px;color:var(--text-tertiary);background:var(--bg-secondary);padding:2px 6px;border-radius:8px;border:0.5px dashed var(--border-mid);white-space:nowrap}
.flow-run{display:flex;flex-direction:column;align-items:center;gap:4px;margin-top:2px}
.run-all-btn{width:44px;height:44px;border-radius:50%;background:var(--accent-blue);border:none;cursor:pointer;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px;color:#fff;transition:all .15s}
.run-all-btn:hover:not(:disabled){background:#2563eb;transform:scale(1.05)}.run-all-btn:disabled{opacity:.5;cursor:not-allowed}
.exec-btn{background:#059669}.exec-btn:hover:not(:disabled){background:#047857}
.report-btn{font-size:10px;padding:4px 8px;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:transparent;color:var(--text-secondary);cursor:pointer;margin-top:4px}
.report-btn:hover{background:var(--bg-hover)}

/* ── 자동변환 안내 ────────────────────────────────────────── */
.fp-auto-msg{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px 16px;flex:1;text-align:center;background:rgba(59,130,246,.03)}

/* ── 매핑 요약 ───────────────────────────────────────────── */
.pair-summary{padding:0;overflow:hidden;margin-bottom:10px}
.ps-hdr{display:flex;align-items:center;gap:8px;padding:10px 14px;border-bottom:0.5px solid var(--border-light);flex-wrap:wrap}
.ps-title{font-size:12px;font-weight:600;color:var(--text-secondary);margin-right:4px}
.schip{font-size:10.5px;padding:2px 8px;border-radius:10px;font-weight:500}
.schip.info{background:var(--bg-info);color:var(--text-info)}.schip.ok{background:var(--bg-success);color:var(--text-success)}
.schip.fail{background:rgba(239,68,68,.1);color:var(--text-danger)}.schip.pend{background:var(--bg-secondary);color:var(--text-tertiary)}
.ps-table{overflow:hidden}
.ps-row{display:flex;align-items:center;gap:6px;padding:7px 14px;border-top:0.5px solid var(--border-light);font-size:11.5px;cursor:pointer;transition:background .12s}
.ps-row.hdr{background:var(--bg-secondary);font-size:10.5px;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.04em;cursor:default}
.ps-row:not(.hdr):hover,.ps-row.active{background:var(--bg-hover)}
.ps-name{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ps-name.src{color:var(--text-info)}.ps-name.tgt{color:var(--text-success)}.ps-name.auto{color:var(--text-warning);font-style:italic}
.res-pill{display:inline-flex;align-items:center;font-size:10.5px;padding:2px 8px;border-radius:10px;font-weight:500;max-width:128px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.res-pill.ok{background:var(--bg-success);color:var(--text-success)}.res-pill.fail{background:rgba(239,68,68,.1);color:var(--text-danger)}
.res-pill.running{background:var(--bg-info);color:var(--text-info)}.res-pill.pend{background:var(--bg-secondary);color:var(--text-tertiary)}

/* ── 변환 정보 바 ────────────────────────────────────────── */
.conv-bar{display:flex;align-items:center;gap:6px;padding:8px 14px;background:var(--bg-secondary);border-radius:var(--radius-md);margin-bottom:10px;flex-wrap:wrap;border:0.5px solid var(--border-light)}
.cv-badge{font-size:11px;font-weight:600;padding:2px 9px;border-radius:10px;flex-shrink:0}
.cv-badge.ai{background:rgba(239,159,39,.15);color:#d97706}.cv-badge.rule{background:var(--bg-info);color:var(--text-info)}.cv-badge.warn{background:var(--bg-warning);color:var(--text-warning)}
.ctag{font-size:10.5px;padding:2px 8px;border-radius:8px}
.ctag.ok{background:var(--bg-info);color:var(--text-info)}.ctag.warn{background:var(--bg-warning);color:var(--text-warning)}

/* ── 비교 배너 ───────────────────────────────────────────── */
.cmp-banner{display:flex;align-items:center;gap:14px;padding:14px 18px;border-radius:var(--radius-md);margin-bottom:10px;border:1px solid}
.cmp-banner.match{background:rgba(16,185,129,.08);border-color:rgba(16,185,129,.3)}.cmp-banner.diff{background:rgba(239,68,68,.07);border-color:rgba(239,68,68,.3)}
.cb-icon{font-size:28px;font-weight:700;flex-shrink:0;line-height:1}
.match .cb-icon{color:var(--text-success)}.diff .cb-icon{color:var(--text-danger)}
.cb-title{font-size:15px;font-weight:700}.match .cb-title{color:var(--text-success)}.diff .cb-title{color:var(--text-danger)}
.cb-sub{font-size:11.5px;color:var(--text-secondary);margin-top:2px}
.cb-stats{display:flex;gap:14px;margin-left:auto}.cs{display:flex;flex-direction:column;align-items:center;gap:2px}
.cs span{font-size:10px;color:var(--text-tertiary)}.cs b{font-size:14px;font-weight:700;color:var(--text-primary)}

/* ── 불일치 상세 ─────────────────────────────────────────── */
.diff-detail{padding:12px 16px;margin-bottom:10px}
.dr{display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:0.5px solid var(--border-light);flex-wrap:wrap}
.dr:last-child{border-bottom:none}.dr-num{font-size:10.5px;background:var(--bg-warning);color:var(--text-warning);padding:1px 7px;border-radius:8px;font-weight:600;flex-shrink:0}
.dc{display:flex;align-items:center;gap:5px;font-size:11.5px;background:var(--bg-secondary);padding:3px 8px;border-radius:var(--radius-sm)}
.dcn{font-weight:600;color:var(--text-tertiary);font-size:10.5px}.dcs{color:var(--text-danger);font-family:'Consolas','SF Mono',monospace}.dct{color:var(--text-success);font-family:'Consolas','SF Mono',monospace}

/* ── 결과 테이블 ─────────────────────────────────────────── */
.res-layout{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.res-card{padding:0;overflow:hidden}
.rc-hdr{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase}
.rc-hdr.src{background:rgba(59,130,246,.06);color:var(--text-info)}.rc-hdr.tgt{background:rgba(16,185,129,.06);color:var(--text-success)}
.rc-badge{font-size:10.5px;font-weight:400;color:var(--text-tertiary);background:var(--bg-secondary);padding:1px 7px;border-radius:8px}
.tbl-wrap{overflow:auto;max-height:420px}
.res-tbl{width:100%;border-collapse:collapse;font-size:11.5px}
.res-tbl th{background:var(--bg-secondary);padding:6px 10px;text-align:left;border-bottom:1px solid var(--border-mid);font-size:10.5px;font-weight:600;color:var(--text-tertiary);white-space:nowrap;position:sticky;top:0}
.res-tbl td{padding:5px 10px;border-bottom:0.5px solid var(--border-light);color:var(--text-primary);white-space:nowrap}
.res-tbl tr:last-child td{border-bottom:none}.res-tbl tr:hover td{background:var(--bg-hover)}
.res-tbl tr.diffrow td{background:rgba(239,68,68,.05)}.res-tbl td.diffcell{background:rgba(239,68,68,.15);color:var(--text-danger);font-weight:600}
.nv{font-size:10.5px;color:var(--text-tertiary);font-style:italic}
</style>
