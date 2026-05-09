<template>
  <div>
    <div class="page-title">SSH 터널링</div>
    <div class="page-desc">SSH 터널을 통해 방화벽 내부 DB에 안전하게 연결합니다</div>
    <div class="ssh-grid">
      <div class="card">
        <div class="card-header">SSH 서버 설정</div>
        <div class="field-label">SSH 호스트</div>
        <input type="text" v-model="cfg.sshHost" placeholder="예) bastion.company.com"/>
        <div class="field-label">SSH 포트</div>
        <input type="number" v-model="cfg.sshPort" placeholder="22"/>
        <div class="field-label">SSH 사용자명</div>
        <input type="text" v-model="cfg.sshUser" placeholder="예) ec2-user"/>
        <div class="field-label">인증 방식</div>
        <div class="sel-wrap">
          <select v-model="cfg.authType">
            <option value="key">SSH 키 파일</option>
            <option value="password">비밀번호</option>
            <option value="agent">SSH Agent</option>
          </select>
          <div class="chevron"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>
        </div>
        <div v-if="cfg.authType==='key'">
          <div class="field-label">SSH 키 파일 경로</div>
          <input type="text" v-model="cfg.keyPath" placeholder="예) C:\Users\user\.ssh\id_rsa"/>
          <div class="field-label">키 패스프레이즈 (선택)</div>
          <input type="password" v-model="cfg.passphrase" placeholder="••••••••"/>
        </div>
        <div v-if="cfg.authType==='password'">
          <div class="field-label">SSH 비밀번호</div>
          <input type="password" v-model="cfg.sshPw" placeholder="••••••••"/>
        </div>
      </div>
      <div class="card">
        <div class="card-header">터널 포트 포워딩</div>
        <div class="info-banner" style="margin-bottom:12px">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:13px;height:13px;flex-shrink:0"><circle cx="8" cy="8" r="7"/><line x1="8" y1="5" x2="8" y2="9"/></svg>
          SSH 터널은 로컬 포트를 원격 DB에 포워딩합니다
        </div>
        <div class="tunnel-row">
          <div><div class="field-label">로컬 포트</div><input type="number" v-model="cfg.localPort" placeholder="예) 13306"/></div>
          <div class="arrow-mid">→</div>
          <div><div class="field-label">원격 DB 호스트</div><input type="text" v-model="cfg.remoteHost" placeholder="예) db.internal"/></div>
          <div class="arrow-mid">:</div>
          <div><div class="field-label">원격 포트</div><input type="number" v-model="cfg.remotePort" placeholder="3306"/></div>
        </div>
        <div class="field-label">연결 후 커넥터 호스트</div>
        <div class="code-block">localhost:{{ cfg.localPort || '13306' }}</div>
        <div style="font-size:11px;color:var(--text-tertiary);margin-top:4px">커넥터 관리에서 호스트를 위 주소로 입력하세요</div>
        <div style="margin-top:16px;display:flex;gap:8px">
          <button class="btn btn-primary" @click="connect" :disabled="tunneling">
            <span v-if="tunneling" class="spinner" style="width:13px;height:13px;border-top-color:#fff"></span>
            {{ tunneling?'연결 중...':'SSH 터널 연결' }}
          </button>
          <button v-if="tunneling||connected" class="btn" @click="disconnect">연결 해제</button>
        </div>
        <div v-if="connected" class="card" style="margin-top:10px;border-color:var(--accent-green);padding:10px 12px;background:var(--bg-success)">
          <div style="font-size:12px;font-weight:500;color:var(--text-success)">✓ SSH 터널 연결됨</div>
          <div style="font-size:11px;color:var(--text-success);margin-top:2px">localhost:{{ cfg.localPort }} → {{ cfg.remoteHost }}:{{ cfg.remotePort }}</div>
        </div>
      </div>
    </div>
    <div style="margin-top:14px;text-align:right">
      <button class="btn btn-primary" @click="save">설정 저장</button>
    </div>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { useAppStore } from '@/store/appStore.js'
const app=useAppStore()
const tunneling=ref(false); const connected=ref(false)
const cfg=ref({sshHost:'',sshPort:22,sshUser:'',authType:'key',keyPath:'',passphrase:'',sshPw:'',localPort:13306,remoteHost:'',remotePort:3306})
async function connect(){tunneling.value=true;await new Promise(r=>setTimeout(r,1200));tunneling.value=false;connected.value=true;app.notify('SSH 터널 연결됨','success')}
function disconnect(){connected.value=false;app.notify('SSH 터널 해제됨')}
function save(){app.notify('SSH 설정 저장됨','success')}
</script>
<style scoped>
.ssh-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.sel-wrap{position:relative}.sel-wrap select{width:100%;appearance:none;-webkit-appearance:none;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:var(--radius-md);padding:7px 28px 7px 10px;font-size:12.5px;color:var(--text-primary);cursor:pointer;font-family:var(--font)}.sel-wrap select:focus{outline:none;border-color:var(--accent-blue)}.chevron{position:absolute;right:9px;top:50%;transform:translateY(-50%);pointer-events:none;color:var(--text-tertiary)}.chevron svg{width:11px;height:11px;display:block}
.tunnel-row{display:grid;grid-template-columns:1fr auto 1fr auto 100px;align-items:end;gap:6px}
.arrow-mid{display:flex;align-items:flex-end;padding-bottom:9px;font-size:16px;color:var(--text-tertiary);justify-content:center}
</style>
