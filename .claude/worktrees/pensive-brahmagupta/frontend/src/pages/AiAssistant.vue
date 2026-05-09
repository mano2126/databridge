<template>
  <div class="ai-wrap">

    <!-- 헤더 -->
    <div class="page-title">AI 어시스턴트</div>
    <div class="page-desc">DB 이관 관련 질문, DDL 변환, 오류 분석을 AI가 도와드립니다</div>

    <!-- 상태 배지 -->
    <div class="status-row">
      <span class="status-dot" :class="apiStatus"></span>
      <span class="status-txt">{{ statusText }}</span>
      <button class="mini-btn" @click="checkStatus" style="margin-left:6px">↻ 확인</button>
      <span v-if="apiStatus==='not_configured' || apiStatus==='error'" class="status-hint">
        → <a href="/settings" @click.prevent="$router.push('/settings')">시스템 설정</a>에서 API 키를 입력해 주세요
      </span>
    </div>

    <!-- 탭 -->
    <div class="tab-bar">
      <button :class="['tab-btn', {active: tab==='chat'}]"    @click="tab='chat'">💬 대화</button>
      <button :class="['tab-btn', {active: tab==='convert'}]" @click="tab='convert'">🔄 DDL 변환</button>
      <button :class="['tab-btn', {active: tab==='analyze'}]" @click="tab='analyze'">🔍 오류 분석</button>
    </div>

    <!-- ── 탭 1: 대화 ── -->
    <div v-if="tab==='chat'" class="card chat-card">
      <!-- 메시지 영역 -->
      <div class="chat-messages" ref="chatBox">
        <div v-if="chatHistory.length===0" class="chat-empty">
          <div class="chat-empty-icon">🤖</div>
          <p>안녕하세요! DB 이관 관련 무엇이든 물어보세요.</p>
          <div class="quick-btns">
            <button v-for="q in quickQuestions" :key="q" @click="quickAsk(q)" class="quick-btn">{{ q }}</button>
          </div>
        </div>
        <template v-for="(msg, i) in chatHistory" :key="i">
          <div :class="['chat-msg', msg.role]">
            <div class="msg-avatar">{{ msg.role==='user' ? '나' : 'AI' }}</div>
            <div class="msg-bubble" v-html="renderMarkdown(msg.content)"></div>
          </div>
        </template>
        <div v-if="chatLoading" class="chat-msg assistant">
          <div class="msg-avatar">AI</div>
          <div class="msg-bubble loading-bubble">
            <span class="dot"></span><span class="dot"></span><span class="dot"></span>
          </div>
        </div>
      </div>

      <!-- 입력 -->
      <div class="chat-input-row">
        <textarea
          v-model="chatInput"
          placeholder="메시지를 입력하세요... (Enter: 전송 / Shift+Enter: 줄바꿈)"
          @keydown.enter.exact.prevent="sendChat"
          rows="2"
          class="chat-textarea"
        ></textarea>
        <div class="chat-actions">
          <button class="mini-btn" @click="clearChat" title="대화 초기화">🗑</button>
          <button class="btn btn-primary send-btn" @click="sendChat"
            :disabled="chatLoading || !chatInput.trim() || apiStatus!=='ok'">
            <span v-if="chatLoading" class="spinner" style="width:11px;height:11px;border-top-color:#fff;display:inline-block"></span>
            {{ chatLoading ? '응답 중...' : '전송' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── 탭 2: DDL 변환 ── -->
    <div v-if="tab==='convert'" class="card" style="padding:14px">
      <div class="form-row" style="margin-bottom:12px">
        <label class="cfg-l">오브젝트 타입</label>
        <div class="sel-wrap w120"><select v-model="conv.objType"><Chev/>
          <option>TRIGGER</option><option>PROCEDURE</option>
          <option>FUNCTION</option><option>VIEW</option>
        </select><Chev/></div>
        <label class="cfg-l" style="margin-left:12px">소스 DB</label>
        <div class="sel-wrap w120"><select v-model="conv.srcDb">
          <option>mssql</option><option>mysql</option><option>oracle</option><option>postgresql</option>
        </select><Chev/></div>
        <label class="cfg-l" style="margin-left:12px">타겟 DB</label>
        <div class="sel-wrap w120"><select v-model="conv.tgtDb">
          <option>mysql</option><option>mssql</option><option>oracle</option><option>postgresql</option>
        </select><Chev/></div>
      </div>

      <div class="editors-row">
        <div class="editor-box">
          <div class="editor-label">원본 DDL ({{ conv.srcDb.toUpperCase() }})</div>
          <textarea v-model="conv.inputDdl" placeholder="변환할 DDL을 입력하세요..." rows="14" class="code-area"></textarea>
        </div>
        <div class="editor-box">
          <div class="editor-label" style="display:flex;justify-content:space-between">
            <span>변환 결과 ({{ conv.tgtDb.toUpperCase() }})</span>
            <button v-if="conv.outputDdl" class="mini-btn" @click="copyDdl">📋 복사</button>
          </div>
          <textarea v-model="conv.outputDdl" placeholder="변환된 DDL이 여기 표시됩니다..." rows="14" class="code-area" readonly></textarea>
        </div>
      </div>

      <div class="form-row" style="margin-top:10px;gap:8px">
        <label class="cfg-l" style="white-space:nowrap">이전 오류 (선택)</label>
        <input v-model="conv.errorMsg" placeholder="이전 변환 시 오류가 있었다면 입력하세요" class="err-input"/>
      </div>

      <div style="display:flex;gap:8px;margin-top:12px;align-items:center">
        <button class="btn btn-primary" @click="convertDdl"
          :disabled="convLoading || !conv.inputDdl.trim() || apiStatus!=='ok'">
          <span v-if="convLoading" class="spinner" style="width:11px;height:11px;border-top-color:#fff;display:inline-block"></span>
          {{ convLoading ? 'AI 변환 중...' : '🤖 AI로 변환' }}
        </button>
        <button class="btn" @click="conv.inputDdl='';conv.outputDdl='';conv.errorMsg=''">초기화</button>
        <span v-if="convUsage" class="usage-txt">토큰: 입력 {{ convUsage.input_tokens.toLocaleString() }} / 출력 {{ convUsage.output_tokens.toLocaleString() }}</span>
      </div>
    </div>

    <!-- ── 탭 3: 오류 분석 ── -->
    <div v-if="tab==='analyze'" class="card" style="padding:14px">
      <div class="form-row" style="margin-bottom:10px">
        <label class="cfg-l">소스 DB</label>
        <div class="sel-wrap w120"><select v-model="ana.srcDb">
          <option>mssql</option><option>mysql</option><option>oracle</option><option>postgresql</option>
        </select><Chev/></div>
        <label class="cfg-l" style="margin-left:12px">타겟 DB</label>
        <div class="sel-wrap w120"><select v-model="ana.tgtDb">
          <option>mysql</option><option>mssql</option><option>oracle</option><option>postgresql</option>
        </select><Chev/></div>
      </div>

      <div class="form-group">
        <div class="editor-label">오류 메시지 *</div>
        <textarea v-model="ana.errorMsg" placeholder="오류 메시지를 붙여넣으세요..." rows="4" class="code-area"></textarea>
      </div>
      <div class="form-group" style="margin-top:10px">
        <div class="editor-label">관련 DDL (선택)</div>
        <textarea v-model="ana.ddl" placeholder="오류가 발생한 DDL을 붙여넣으세요..." rows="6" class="code-area"></textarea>
      </div>

      <div style="display:flex;gap:8px;margin-top:12px;align-items:center">
        <button class="btn btn-primary" @click="analyzeError"
          :disabled="anaLoading || !ana.errorMsg.trim() || apiStatus!=='ok'">
          <span v-if="anaLoading" class="spinner" style="width:11px;height:11px;border-top-color:#fff;display:inline-block"></span>
          {{ anaLoading ? 'AI 분석 중...' : '🔍 AI로 분석' }}
        </button>
        <button class="btn" @click="ana.errorMsg='';ana.ddl='';ana.result=''">초기화</button>
        <span v-if="anaUsage" class="usage-txt">토큰: {{ (anaUsage.input_tokens+anaUsage.output_tokens).toLocaleString() }}</span>
      </div>

      <div v-if="ana.result" class="analysis-result" v-html="renderMarkdown(ana.result)"></div>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useAppStore } from '@/store/appStore.js'
import axios from 'axios'

const API = '/api/v1/ai'
const app = useAppStore()
const Chev = { template: '<div class="chev-ico"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" style="width:10px;height:10px;display:block"><polyline points="2,4 6,8 10,4"/></svg></div>' }

const tab        = ref('chat')
const apiStatus  = ref('unknown')
const statusText = ref('확인 중...')

// 대화
const chatHistory = ref([])
const chatInput   = ref('')
const chatLoading = ref(false)
const chatBox     = ref(null)
const quickQuestions = [
  'MySQL→MSSQL 트리거 변환 주의사항은?',
  '이관 배치 사이즈 추천값은?',
  'MSSQL IDENTITY → MySQL AUTO_INCREMENT 이관 방법',
  '트리거 이관 시 FOR EACH ROW 오류 해결법',
]

// DDL 변환
const conv      = ref({ objType:'TRIGGER', srcDb:'mssql', tgtDb:'mysql', inputDdl:'', outputDdl:'', errorMsg:'' })
const convLoading = ref(false)
const convUsage   = ref(null)

// 오류 분석
const ana       = ref({ srcDb:'mssql', tgtDb:'mysql', errorMsg:'', ddl:'', result:'' })
const anaLoading  = ref(false)
const anaUsage    = ref(null)

onMounted(() => checkStatus())

async function checkStatus() {
  apiStatus.value = 'unknown'
  statusText.value = '확인 중...'
  try {
    const { data } = await axios.get(`${API}/status`)
    apiStatus.value = data.status
    statusText.value = data.message
  } catch {
    apiStatus.value = 'error'
    statusText.value = '연결 실패'
  }
}

async function sendChat() {
  const msg = chatInput.value.trim()
  if (!msg || chatLoading.value) return
  chatHistory.value.push({ role:'user', content:msg })
  chatInput.value = ''
  chatLoading.value = true
  await nextTick(); chatBox.value?.scrollTo(0, chatBox.value.scrollHeight)
  try {
    const { data } = await axios.post(`${API}/chat`, {
      message: msg,
      history: chatHistory.value.slice(-12).slice(0, -1)
    })
    chatHistory.value.push({ role:'assistant', content:data.reply })
  } catch (e) {
    chatHistory.value.push({ role:'assistant', content:`오류: ${e.response?.data?.detail || e.message}` })
  } finally {
    chatLoading.value = false
    await nextTick(); chatBox.value?.scrollTo(0, chatBox.value.scrollHeight)
  }
}

function quickAsk(q) { chatInput.value = q; sendChat() }
function clearChat() { chatHistory.value = []; chatInput.value = '' }

async function convertDdl() {
  convLoading.value = true; convUsage.value = null
  try {
    const { data } = await axios.post(`${API}/convert-ddl`, {
      ddl:       conv.value.inputDdl,
      obj_type:  conv.value.objType,
      src_db:    conv.value.srcDb,
      tgt_db:    conv.value.tgtDb,
      error_msg: conv.value.errorMsg || null
    })
    conv.value.outputDdl = data.converted_ddl
    convUsage.value      = data.usage
    app.notify('DDL 변환 완료!', 'success')
  } catch (e) {
    conv.value.outputDdl = `-- 오류: ${e.response?.data?.detail || e.message}`
    app.notify('변환 실패: ' + (e.response?.data?.detail || e.message), 'error')
  } finally { convLoading.value = false }
}

function copyDdl() {
  navigator.clipboard?.writeText(conv.value.outputDdl)
  app.notify('DDL 복사됨', 'success')
}

async function analyzeError() {
  anaLoading.value = true; ana.value.result = ''; anaUsage.value = null
  try {
    const { data } = await axios.post(`${API}/analyze-error`, {
      error_msg: ana.value.errorMsg,
      ddl:       ana.value.ddl || null,
      src_db:    ana.value.srcDb,
      tgt_db:    ana.value.tgtDb
    })
    ana.value.result = data.analysis
    anaUsage.value   = data.usage
  } catch (e) {
    ana.value.result = `오류: ${e.response?.data?.detail || e.message}`
  } finally { anaLoading.value = false }
}

function renderMarkdown(text) {
  if (!text) return ''
  return text
    .replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/^#{1,3}\s+(.+)$/gm, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}
</script>

<style scoped>
.ai-wrap { display:flex; flex-direction:column; gap:10px; }

/* 상태 바 */
.status-row { display:flex; align-items:center; gap:6px; font-size:12px; color:var(--text-secondary); margin-bottom:2px; }
.status-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
.status-dot.ok            { background:var(--accent-green); }
.status-dot.not_configured { background:var(--text-tertiary); }
.status-dot.error         { background:#e24b4a; }
.status-dot.unknown       { background:var(--text-tertiary); }
.status-txt { font-size:12px; color:var(--text-secondary); }
.status-hint { font-size:11.5px; color:var(--text-tertiary); }
.status-hint a { color:var(--text-info); text-decoration:none; }
.status-hint a:hover { text-decoration:underline; }

/* 탭 */
.tab-bar { display:flex; gap:6px; }
.tab-btn { padding:6px 14px; border-radius:var(--radius-md); border:0.5px solid var(--border-mid);
  background:transparent; color:var(--text-secondary); cursor:pointer; font-size:12.5px; font-family:var(--font); transition:all .12s; }
.tab-btn:hover { background:var(--bg-secondary); }
.tab-btn.active { background:var(--bg-info); color:var(--text-info); border-color:var(--accent-blue); font-weight:500; }

/* 채팅 카드 */
.chat-card { display:flex; flex-direction:column; height:calc(100vh - 260px); min-height:480px; padding:0; overflow:hidden; }

/* 메시지 영역 */
.chat-messages { flex:1; overflow-y:auto; padding:14px; display:flex; flex-direction:column; gap:12px; }
.chat-messages::-webkit-scrollbar { width:4px; }
.chat-messages::-webkit-scrollbar-thumb { background:var(--border-mid); border-radius:2px; }

.chat-empty { text-align:center; padding:48px 20px; color:var(--text-tertiary); }
.chat-empty-icon { font-size:36px; margin-bottom:12px; }
.chat-empty p { font-size:13.5px; margin-bottom:16px; }
.quick-btns { display:flex; flex-wrap:wrap; gap:6px; justify-content:center; }
.quick-btn { padding:5px 12px; border-radius:20px; border:0.5px solid var(--border-mid);
  background:var(--bg-secondary); color:var(--text-secondary); cursor:pointer; font-size:12px;
  font-family:var(--font); transition:all .12s; }
.quick-btn:hover { background:var(--bg-tertiary); color:var(--text-primary); }

/* 메시지 버블 */
.chat-msg { display:flex; gap:8px; align-items:flex-start; }
.chat-msg.user { flex-direction:row-reverse; }
.msg-avatar { width:28px; height:28px; border-radius:50%; display:flex; align-items:center;
  justify-content:center; font-size:10px; font-weight:600; flex-shrink:0; }
.chat-msg.user .msg-avatar { background:var(--accent-blue); color:#fff; }
.chat-msg.assistant .msg-avatar { background:var(--bg-tertiary); color:var(--text-secondary);
  border:0.5px solid var(--border-mid); }
.msg-bubble { max-width:75%; padding:10px 13px; border-radius:var(--radius-lg); font-size:13.5px;
  line-height:1.65; }
.chat-msg.user .msg-bubble { background:var(--accent-blue); color:#fff; border-radius:var(--radius-lg) var(--radius-sm) var(--radius-lg) var(--radius-lg); }
.chat-msg.assistant .msg-bubble { background:var(--bg-secondary); color:var(--text-primary);
  border:0.5px solid var(--border-light); border-radius:var(--radius-sm) var(--radius-lg) var(--radius-lg) var(--radius-lg); }
.msg-bubble :deep(pre) { background:var(--bg-tertiary); border:0.5px solid var(--border-mid);
  border-radius:var(--radius-sm); padding:8px 10px; margin:6px 0; overflow-x:auto;
  font-family:'Consolas','SF Mono',monospace; font-size:12px; }
.msg-bubble :deep(strong) { font-weight:600; }
.msg-bubble :deep(code) { font-family:'Consolas','SF Mono',monospace; font-size:12px; }

.loading-bubble { display:flex; gap:4px; align-items:center; padding:12px 16px; }
.dot { width:7px; height:7px; border-radius:50%; background:var(--text-tertiary); animation:bounce 1.2s infinite; }
.dot:nth-child(2) { animation-delay:.2s; }
.dot:nth-child(3) { animation-delay:.4s; }
@keyframes bounce { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-7px)} }

/* 채팅 입력 */
.chat-input-row { display:flex; gap:8px; padding:10px 14px; border-top:0.5px solid var(--border-light);
  background:var(--bg-secondary); align-items:flex-end; }
.chat-textarea { flex:1; background:var(--bg-primary); border:0.5px solid var(--border-mid);
  border-radius:var(--radius-md); color:var(--text-primary); padding:8px 10px; resize:none;
  font-size:13px; font-family:var(--font); outline:none; transition:border-color .12s; }
.chat-textarea:focus { border-color:var(--accent-blue); }
.chat-actions { display:flex; flex-direction:column; gap:5px; align-items:flex-end; }
.send-btn { padding:7px 16px; font-size:12.5px; }

/* DDL 에디터 */
.editors-row { display:flex; gap:12px; }
.editor-box { flex:1; display:flex; flex-direction:column; gap:5px; }
.editor-label { font-size:12px; font-weight:500; color:var(--text-secondary); }
.code-area { background:var(--bg-secondary); border:0.5px solid var(--border-mid);
  border-radius:var(--radius-md); color:var(--text-primary); padding:10px;
  font-family:'Consolas','SF Mono',monospace; font-size:12.5px; resize:vertical;
  outline:none; transition:border-color .12s; line-height:1.55; }
.code-area:focus { border-color:var(--accent-blue); }

/* 폼 공통 */
.form-row { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.form-group { display:flex; flex-direction:column; gap:5px; }
.cfg-l { font-size:12px; color:var(--text-secondary); white-space:nowrap; }
.err-input { flex:1; padding:6px 10px; background:var(--bg-secondary); border:0.5px solid var(--border-mid);
  border-radius:var(--radius-md); font-size:12px; color:var(--text-primary); outline:none; font-family:var(--font); }
.err-input:focus { border-color:var(--accent-blue); }
.sel-wrap { position:relative; }
.sel-wrap select { width:100%; appearance:none; background:var(--bg-secondary); border:0.5px solid var(--border-mid);
  border-radius:var(--radius-md); padding:5px 24px 5px 8px; font-size:12px; color:var(--text-primary);
  cursor:pointer; font-family:var(--font); outline:none; }
.sel-wrap select:focus { border-color:var(--accent-blue); }
.chev-ico { position:absolute; right:6px; top:50%; transform:translateY(-50%); pointer-events:none; color:var(--text-tertiary); }
.w120 { min-width:110px; }

/* 오류 분석 결과 */
.analysis-result { margin-top:14px; background:var(--bg-secondary); border:0.5px solid var(--border-mid);
  border-radius:var(--radius-md); padding:14px 16px; font-size:13.5px; line-height:1.7;
  color:var(--text-primary); }
.analysis-result :deep(pre) { background:var(--bg-tertiary); border:0.5px solid var(--border-mid);
  border-radius:var(--radius-sm); padding:10px 12px; overflow-x:auto; margin:8px 0;
  font-family:'Consolas','SF Mono',monospace; font-size:12px; }
.analysis-result :deep(strong) { color:var(--text-info); font-weight:600; }
.analysis-result :deep(code) { font-family:'Consolas','SF Mono',monospace; font-size:12px; }

/* 토큰 사용량 */
.usage-txt { font-size:11px; color:var(--text-tertiary); }

/* 공통 버튼 */
.btn { display:inline-flex; align-items:center; gap:5px; padding:7px 14px; border-radius:var(--radius-md);
  font-size:12px; font-weight:500; font-family:var(--font); cursor:pointer; border:0.5px solid var(--border-mid);
  background:transparent; color:var(--text-secondary); transition:all .12s; }
.btn:hover { background:var(--bg-secondary); }
.btn-primary { background:var(--bg-info); color:var(--text-info); border-color:var(--accent-blue); }
.btn-primary:hover { background:var(--accent-blue); color:#fff; }
.btn:disabled { opacity:.4; cursor:not-allowed; }
.mini-btn { font-size:11px; padding:3px 8px; border-radius:var(--radius-sm); border:0.5px solid var(--border-mid);
  background:transparent; cursor:pointer; font-family:var(--font); color:var(--text-secondary); }
.mini-btn:hover { background:var(--bg-secondary); }
.spinner { border:2px solid rgba(255,255,255,.3); border-radius:50%; animation:spin .7s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }
</style>
