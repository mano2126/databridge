<template>
  <div>
    <div class="page-title">SSL/TLS 설정</div>
    <div class="page-desc">DB 연결 시 SSL/TLS 암호화를 설정합니다</div>
    <div class="ssl-grid">
      <div class="card">
        <div class="card-header">소스 DB SSL 설정</div>
        <div class="cfg-row"><div><div class="cfg-l">SSL 활성화</div><div class="cfg-s">소스 DB TLS 암호화 연결</div></div><div class="toggle" :class="{on:src.enabled}" @click="src.enabled=!src.enabled"></div></div>
        <template v-if="src.enabled">
          <div class="cfg-row"><div><div class="cfg-l">인증서 검증</div><div class="cfg-s">서버 인증서 유효성 검사</div></div><div class="toggle" :class="{on:src.verify}" @click="src.verify=!src.verify"></div></div>
          <div class="field-label">CA 인증서 경로</div>
          <input type="text" v-model="src.ca" placeholder="예) C:\certs\ca.pem"/>
          <div class="field-label">클라이언트 인증서 (선택)</div>
          <input type="text" v-model="src.cert" placeholder="예) C:\certs\client-cert.pem"/>
          <div class="field-label">클라이언트 키 (선택)</div>
          <input type="text" v-model="src.key" placeholder="예) C:\certs\client-key.pem"/>
          <div class="field-label">TLS 버전</div>
          <div class="sel-wrap"><select v-model="src.tlsVer"><option>TLSv1.3</option><option>TLSv1.2</option><option>TLSv1.1</option></select><div class="chevron"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div></div>
        </template>
      </div>
      <div class="card">
        <div class="card-header">타겟 DB SSL 설정</div>
        <div class="cfg-row"><div><div class="cfg-l">SSL 활성화</div><div class="cfg-s">타겟 DB TLS 암호화 연결</div></div><div class="toggle" :class="{on:tgt.enabled}" @click="tgt.enabled=!tgt.enabled"></div></div>
        <template v-if="tgt.enabled">
          <div class="cfg-row"><div><div class="cfg-l">인증서 검증</div><div class="cfg-s">서버 인증서 유효성 검사</div></div><div class="toggle" :class="{on:tgt.verify}" @click="tgt.verify=!tgt.verify"></div></div>
          <div class="cfg-row"><div><div class="cfg-l">자체 서명 인증서 허용</div><div class="cfg-s">TrustServerCertificate=yes</div></div><div class="toggle" :class="{on:tgt.trustSelf}" @click="tgt.trustSelf=!tgt.trustSelf"></div></div>
          <div class="field-label">CA 인증서 경로</div>
          <input type="text" v-model="tgt.ca" placeholder="예) C:\certs\ca.pem"/>
          <div class="field-label">TLS 버전</div>
          <div class="sel-wrap"><select v-model="tgt.tlsVer"><option>TLSv1.3</option><option>TLSv1.2</option></select><div class="chevron"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div></div>
        </template>
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
const src=ref({enabled:false,verify:true,ca:'',cert:'',key:'',tlsVer:'TLSv1.3'})
const tgt=ref({enabled:false,verify:false,trustSelf:true,ca:'',tlsVer:'TLSv1.3'})
function save(){app.notify('SSL/TLS 설정 저장됨','success')}
</script>
<style scoped>
.ssl-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.cfg-row{display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:0.5px solid var(--border-light)}
.cfg-row:last-of-type{border-bottom:none}
.cfg-l{font-size:12px;color:var(--text-primary)}.cfg-s{font-size:10.5px;color:var(--text-tertiary);margin-top:1px}
.sel-wrap{position:relative}.sel-wrap select{width:100%;appearance:none;-webkit-appearance:none;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:var(--radius-md);padding:7px 28px 7px 10px;font-size:12.5px;color:var(--text-primary);cursor:pointer;font-family:var(--font)}.chevron{position:absolute;right:9px;top:50%;transform:translateY(-50%);pointer-events:none;color:var(--text-tertiary)}.chevron svg{width:11px;height:11px;display:block}
</style>
