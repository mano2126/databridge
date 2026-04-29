<template>
  <div class="conn-panel" :class="side">
    <div class="cp-label" :class="side"><span class="dot"></span>{{ side==='source'?'Source Database':'Target Database' }}</div>
    <div class="field-label">데이터베이스 종류</div>
    <DbSelector :mode="mode" :modelValue="dbType" @update:modelValue="onDbChange"/>
    <div class="field-label">버전</div>
    <div class="sel-wrap">
      <select :value="version" @change="$emit('update:version',$event.target.value)">
        <option v-for="v in versions" :key="v">{{ v }}</option>
      </select>
      <div class="chevron"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>
    </div>
    <div class="field-label">호스트</div>
    <input type="text" :value="host" @input="$emit('update:host',$event.target.value)" :placeholder="hostPh" :class="{err:v&&!host}"/>
    <div class="row2">
      <div>
        <div class="field-label" style="margin-top:0">포트</div>
        <input type="number" :value="port" @input="$emit('update:port',Number($event.target.value))"/>
      </div>
      <div>
        <div class="field-label" style="margin-top:0">{{ side==='source'?'인증':'인코딩' }}</div>
        <div class="sel-wrap">
          <select v-if="side==='source'"><option>SQL 인증</option><option>Windows 인증</option><option>Kerberos</option></select>
          <select v-else><option>utf8mb4</option><option>utf8</option><option>latin1</option></select>
          <div class="chevron"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>
        </div>
      </div>
    </div>
    <div class="field-label">사용자명</div>
    <input type="text" :value="username" @input="$emit('update:username',$event.target.value)" placeholder="사용자명" :class="{err:v&&!username}"/>
    <div class="field-label">비밀번호</div>
    <div class="pw-wrap">
      <input :type="showPw?'text':'password'" :value="password" @input="$emit('update:password',$event.target.value)" placeholder="••••••••"/>
      <button class="eye" @click="showPw=!showPw" type="button"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" style="width:13px;height:13px"><path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z"/><circle cx="8" cy="8" r="2"/></svg></button>
    </div>
    <div class="field-label">데이터베이스명</div>
    <input type="text" :value="database" @input="$emit('update:database',$event.target.value)" placeholder="DB 이름" :class="{err:v&&!database}"/>
    <div v-if="v&&valMsg" class="val-msg">{{ valMsg }}</div>
    <button class="test-btn" :class="side+'-btn'" @click="handleTest" :disabled="status==='testing'">
      <span class="btn-ic"><svg v-if="status!=='testing'" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px"><polyline points="2,8 6,12 14,4"/></svg><span v-else class="spinner"></span></span>
      {{ status==='testing'?'연결 확인 중...':(side==='source'?'소스':'타겟')+' 연결 테스트' }}
    </button>
    <transition name="sl">
      <div v-if="status!=='idle'" class="sbar" :class="'sb-'+status">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:12px;height:12px;flex-shrink:0;margin-top:1px">
          <template v-if="status==='ok'"><circle cx="8" cy="8" r="7"/><polyline points="5,8 7,10 11,6"/></template>
          <template v-else-if="status==='error'"><circle cx="8" cy="8" r="7"/><line x1="5" y1="5" x2="11" y2="11"/><line x1="11" y1="5" x2="5" y2="11"/></template>
          <template v-else><circle cx="8" cy="8" r="7"/><line x1="8" y1="5" x2="8" y2="9"/></template>
        </svg>
        <div><div class="sb-main">{{ sbMain }}</div>
          <div v-if="status==='ok'&&latency" class="sb-sub">지연 {{ latency }}ms &nbsp;·&nbsp; {{ (versionResult||'').slice(0,45) }}</div>
          <div v-if="status==='error'" class="sb-sub">{{ message }}</div>
        </div>
      </div>
    </transition>
  </div>
</template>
<script setup>
import { ref, computed } from 'vue'
import { DB_META } from '@/constants/dbMeta.js'
import DbSelector from './DbSelector.vue'
const p = defineProps({
  side:String,mode:String,
  dbType:{type:String,default:'mssql'},version:{type:String,default:''},
  host:{type:String,default:''},port:{type:Number,default:1433},
  username:{type:String,default:''},password:{type:String,default:''},database:{type:String,default:''},
  status:{type:String,default:'idle'},latency:{type:Number,default:null},
  versionResult:{type:String,default:''},message:{type:String,default:''},
})
const emit = defineEmits(['update:dbType','update:version','update:host','update:port','update:username','update:password','update:database','test'])
const showPw=ref(false); const v=ref(false)
function onDbChange(val){emit('update:dbType',val);const m=DB_META[val];if(m){emit('update:port',m.port);emit('update:version',m.versions[0])}}
const versions=computed(()=>DB_META[p.dbType]?.versions||[p.version])
const hostPh=computed(()=>({mssql:'db-server.company.local',mysql:'192.168.1.10',postgresql:'pg-server.corp',snowflake:'account.snowflakecomputing.com'})[p.dbType]||'호스트명 또는 IP')
const valMsg=computed(()=>!p.host?'호스트를 입력하세요':!p.username?'사용자명을 입력하세요':!p.database?'DB 이름을 입력하세요':'')
function handleTest(){v.value=true;if(!valMsg.value)emit('test')}
const sbMain=computed(()=>({ok:'연결 성공',error:'연결 실패',testing:'연결 확인 중...'})[p.status]||'')
</script>
<style scoped>
.conn-panel{background:var(--bg-primary);border:0.5px solid var(--border-light);border-radius:var(--radius-lg);padding:18px}
.conn-panel.source{border-top:2px solid var(--accent-blue)}.conn-panel.target{border-top:2px solid var(--accent-green)}
.cp-label{display:flex;align-items:center;gap:6px;font-size:9.5px;font-weight:600;letter-spacing:.7px;text-transform:uppercase;margin-bottom:14px}
.cp-label.source{color:#185fa5}.cp-label.target{color:#3b6d11}
.dot{width:6px;height:6px;border-radius:50%;background:currentColor}
.sel-wrap{position:relative}.sel-wrap select{appearance:none;-webkit-appearance:none;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:var(--radius-md);padding:7px 28px 7px 10px;font-size:12.5px;color:var(--text-primary);cursor:pointer;font-family:var(--font);transition:border-color .12s;width:100%}
.sel-wrap select:focus{outline:none;border-color:var(--accent-blue)}
.chevron{position:absolute;right:9px;top:50%;transform:translateY(-50%);pointer-events:none;color:var(--text-tertiary)}.chevron svg{width:11px;height:11px;display:block}
.row2{display:grid;grid-template-columns:2fr 1fr;gap:8px;margin-top:10px}
input[type="text"],input[type="number"],input[type="password"]{width:100%;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:var(--radius-md);padding:7px 10px;font-size:12.5px;color:var(--text-primary);font-family:var(--font);transition:border-color .12s}
input:focus{outline:none;border-color:var(--accent-blue)}input.err{border-color:var(--text-danger)!important}
.pw-wrap{position:relative}.pw-wrap input{padding-right:32px}
.eye{position:absolute;right:8px;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;color:var(--text-tertiary);padding:2px;display:flex}
.eye:hover{color:var(--text-primary)}
.val-msg{font-size:11px;color:var(--text-danger);margin-top:5px}
.test-btn{width:100%;margin-top:12px;padding:9px;border-radius:var(--radius-md);border:0.5px solid var(--border-mid);background:var(--bg-secondary);font-size:12px;color:var(--text-secondary);cursor:pointer;font-family:var(--font);display:flex;align-items:center;justify-content:center;gap:7px;transition:all .15s}
.test-btn:disabled{opacity:.6;cursor:not-allowed}
.source-btn:hover:not(:disabled){border-color:var(--accent-blue);color:#185fa5;background:var(--bg-info)}
.target-btn:hover:not(:disabled){border-color:var(--accent-green);color:#3b6d11;background:var(--bg-success)}
.btn-ic{display:flex;align-items:center;justify-content:center;width:14px;height:14px}
.sbar{margin-top:8px;padding:8px 10px;border-radius:var(--radius-md);font-size:11px;display:flex;align-items:flex-start;gap:7px}
.sb-ok{background:var(--bg-success);color:var(--text-success)}.sb-error{background:var(--bg-danger);color:var(--text-danger)}.sb-testing{background:var(--bg-info);color:var(--text-info)}
.sb-main{font-weight:500}.sb-sub{font-size:10.5px;opacity:.85;margin-top:1px}
.sl-enter-active,.sl-leave-active{transition:all .25s ease}.sl-enter-from,.sl-leave-to{opacity:0;transform:translateY(-4px)}
</style>
