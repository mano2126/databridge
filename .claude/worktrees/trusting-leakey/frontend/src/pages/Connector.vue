<template>
  <div>
    <div class="page-title">커넥터 관리</div>
    <div class="page-desc">소스와 타겟 데이터베이스를 선택하고 연결 정보를 설정하세요</div>
    <div class="conn-layout">
      <ConnectionForm side="source" mode="source"
        v-model:dbType="s.source.dbType" v-model:version="s.source.version"
        v-model:host="s.source.host" v-model:port="s.source.port"
        v-model:username="s.source.username" v-model:password="s.source.password"
        v-model:database="s.source.database"
        :status="s.source.status" :latency="s.source.latency"
        :versionResult="s.source.versionResult" :message="s.source.message"
        @test="doTest('source')"/>
      <div class="arrow-col">
        <div class="arrow-circle" :class="{active:s.bothConnected}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="4" y1="12" x2="20" y2="12"/><polyline points="14,6 20,12 14,18"/></svg>
        </div>
        <div class="arrow-lbl">Migration<br>Pipeline</div>
        <div v-if="s.bothConnected" class="ok-badge">연결 완료 ✓</div>
      </div>
      <ConnectionForm side="target" mode="target"
        v-model:dbType="s.target.dbType" v-model:version="s.target.version"
        v-model:host="s.target.host" v-model:port="s.target.port"
        v-model:username="s.target.username" v-model:password="s.target.password"
        v-model:database="s.target.database"
        :status="s.target.status" :latency="s.target.latency"
        :versionResult="s.target.versionResult" :message="s.target.message"
        @test="doTest('target')"/>
    </div>

    <button class="go-btn" :class="{on:s.bothConnected}" @click="goWizard">
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" style="width:15px;height:15px"><line x1="4" y1="8" x2="12" y2="8"/><polyline points="9,5 12,8 9,11"/></svg>
      {{ s.bothConnected?'연결 확인 완료 — Job 생성 위저드로 이동':'소스와 타겟 연결 테스트를 먼저 완료하세요' }}
    </button>

    <div class="card" style="margin-top:14px">
      <div class="card-header">저장된 연결 프로파일
        <div style="display:flex;gap:6px">
          <button class="act-btn" @click="showSave=true">+ 현재 설정 저장</button>
          <button class="act-btn" @click="s.loadProfiles()">↻</button>
        </div>
      </div>
      <div v-if="!s.profiles.length" class="empty-state">저장된 프로파일이 없습니다</div>
      <div v-for="p in s.profiles" :key="p.id" class="list-row">
        <div class="db-icon" :style="{background:m(p.source?.db_type||p.source?.dbType)?.bg,color:m(p.source?.db_type||p.source?.dbType)?.color}">{{ m(p.source?.db_type||p.source?.dbType)?.label }}</div>
        <div>
          <div class="item-name">{{ p.name }}</div>
          <div class="item-desc">{{ p.source?.host||'?' }} → {{ p.target?.host||'?' }}</div>
        </div>
        <div class="item-right">
          <span class="pill" :class="p.status==='ok'?'pill-ok':'pill-warn'">{{ p.status==='ok'?'연결됨':'만료' }}</span>
          <button class="act-btn" @click="s.applyProfile(p);app.notify('프로파일을 불러왔습니다','success')">불러오기</button>
          <button class="act-btn del" @click="s.removeProfile(p.id);app.notify('삭제되었습니다')">삭제</button>
        </div>
      </div>
    </div>

    <div v-if="showSave" class="modal-overlay" @click.self="showSave=false">
      <div class="modal">
        <div class="modal-title">프로파일 이름 입력</div>
        <input type="text" v-model="saveName" placeholder="예) MSSQL Prod → MySQL 이관" @keyup.enter="doSave"/>
        <div class="modal-btns">
          <button class="btn" @click="showSave=false">취소</button>
          <button class="btn btn-primary" @click="doSave">저장</button>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useConnectorStore } from '@/store/connectorStore.js'
import { useAppStore } from '@/store/appStore.js'
import { DB_META } from '@/constants/dbMeta.js'
import ConnectionForm from '@/components/connector/ConnectionForm.vue'
const s=useConnectorStore(); const app=useAppStore(); const router=useRouter()
const showSave=ref(false); const saveName=ref('')
const m = t => DB_META[t]||{label:'??',bg:'#eee',color:'#333'}
onMounted(()=>s.loadProfiles())
async function doTest(side){await s.testConn(side);app.notify(s[side].status==='ok'?'연결 성공!':'연결 실패',s[side].status==='ok'?'success':'error')}
function goWizard(){if(s.bothConnected)router.push('/jobs/wizard')}
async function doSave(){if(!saveName.value.trim())return;await s.saveProfile(saveName.value.trim());saveName.value='';showSave.value=false;app.notify('프로파일이 저장되었습니다','success')}
</script>
<style scoped>
.conn-layout{display:grid;grid-template-columns:1fr 68px 1fr;gap:0;align-items:start}
.arrow-col{display:flex;flex-direction:column;align-items:center;justify-content:center;padding-top:80px;gap:8px}
.arrow-circle{width:40px;height:40px;border-radius:50%;border:1.5px solid var(--border-mid);display:flex;align-items:center;justify-content:center;color:var(--text-tertiary);transition:all .3s}
.arrow-circle.active{border-color:var(--accent-blue);color:var(--accent-blue);background:var(--bg-info)}
.arrow-circle svg{width:18px;height:18px}
.arrow-lbl{font-size:9.5px;color:var(--text-tertiary);text-align:center;line-height:1.4}
.ok-badge{font-size:10px;background:var(--bg-success);color:var(--text-success);padding:2px 8px;border-radius:8px;font-weight:500}
.go-btn{width:100%;margin-top:14px;padding:11px;border-radius:var(--radius-md);border:1.5px solid var(--border-mid);background:var(--bg-secondary);font-size:13px;font-weight:500;color:var(--text-tertiary);cursor:not-allowed;font-family:var(--font);display:flex;align-items:center;justify-content:center;gap:8px;transition:all .2s}
.go-btn.on{border-color:var(--accent-blue);background:var(--bg-info);color:var(--text-info);cursor:pointer}
.go-btn.on:hover{background:var(--accent-blue);color:#fff}
</style>
