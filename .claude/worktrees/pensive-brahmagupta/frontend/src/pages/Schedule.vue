<template>
  <div>
    <div class="page-title">스케줄 관리</div>
    <div class="page-desc">특정 시간 또는 주기적으로 실행될 마이그레이션 Job을 관리합니다</div>

    <div class="card" style="margin-bottom:10px;padding:10px 16px;display:flex;gap:8px;align-items:center">
      <button class="btn btn-primary" style="font-size:12px" @click="showAdd=true">+ 새 스케줄 등록</button>
      <button class="btn" style="font-size:12px" @click="loadSchedules">↻ 새로고침</button>
      <span style="margin-left:auto;font-size:11.5px;color:var(--text-tertiary)">총 {{ schedules.length }}개 스케줄</span>
    </div>

    <div class="card" style="padding:0;overflow:hidden">
      <table class="sch-tbl">
        <thead>
          <tr><th>이름</th><th>유형</th><th>실행 시간</th><th>소스 → 타겟</th><th>상태</th><th>다음 실행</th><th>실행 횟수</th><th>작업</th></tr>
        </thead>
        <tbody>
          <tr v-for="s in schedules" :key="s.id">
            <td style="font-weight:500">{{ s.name }}</td>
            <td>
              <span class="type-badge" :class="s.type">
                {{ {once:'1회',cron:'반복',interval:'주기'}[s.type]||s.type }}
              </span>
            </td>
            <td style="font-family:'Consolas','SF Mono',monospace;font-size:11.5px">
              <span v-if="s.type==='once'">{{ fmtDt(s.run_at) }}</span>
              <span v-else-if="s.type==='cron'">{{ s.cron_expr }}</span>
              <span v-else>{{ s.interval_min }}분마다</span>
            </td>
            <td style="font-size:11.5px;color:var(--text-tertiary)">
              {{ s.job_config?.src_db||'-' }} → {{ s.job_config?.tgt_db||'-' }}
            </td>
            <td>
              <span class="pill" :class="statusCls(s.status)">{{ statusLbl(s.status) }}</span>
            </td>
            <td style="font-size:11px;color:var(--text-tertiary)">{{ fmtDt(s.next_run)||'-' }}</td>
            <td style="font-size:12px;text-align:center">{{ s.run_count||0 }}</td>
            <td>
              <div style="display:flex;gap:4px">
                <button class="act-btn" @click="runNow(s.id)" title="지금 즉시 실행">▶ 즉시실행</button>
                <button class="act-btn del" @click="delSchedule(s.id)">삭제</button>
              </div>
            </td>
          </tr>
          <tr v-if="!schedules.length">
            <td colspan="8" class="empty-state" style="padding:30px">등록된 스케줄이 없습니다</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 스케줄 등록 모달 -->
    <div v-if="showAdd" class="modal-overlay" @click.self="showAdd=false">
      <div class="modal" style="max-width:500px;width:94%">
        <div class="modal-title">새 스케줄 등록</div>

        <div class="field-label">스케줄 이름</div>
        <input type="text" v-model="form.name" placeholder="예) 매일 새벽 sakila 이관"/>

        <div class="field-label">실행 유형</div>
        <div class="type-btns">
          <button v-for="t in types" :key="t.v" class="type-btn" :class="{active:form.type===t.v}" @click="form.type=t.v">
            {{ t.icon }} {{ t.l }}
          </button>
        </div>

        <!-- 1회 실행 -->
        <template v-if="form.type==='once'">
          <div class="field-label">실행 일시</div>
          <input type="datetime-local" v-model="form.run_at"/>
        </template>

        <!-- 반복 cron -->
        <template v-if="form.type==='cron'">
          <div class="field-label">Cron 표현식</div>
          <input type="text" v-model="form.cron_expr" placeholder="예) 0 2 * * * (매일 새벽 2시)"/>
          <div class="cron-presets">
            <button v-for="p in cronPresets" :key="p.v" class="preset-btn" @click="form.cron_expr=p.v">{{ p.l }}</button>
          </div>
          <div style="font-size:11px;color:var(--text-tertiary);margin-top:4px">
            분 시 일 월 요일 형식 · 0=일요일
          </div>
        </template>

        <!-- 주기 interval -->
        <template v-if="form.type==='interval'">
          <div class="field-label">실행 간격 (분)</div>
          <input type="number" v-model="form.interval_min" min="1" max="10080"/>
        </template>

        <div class="field-label">연결된 Job 설정 (Job 관리에서 가져오기)</div>
        <div class="sel-wrap">
          <select v-model="form.selectedJob" @change="onJobSelect">
            <option value="">-- Job 선택 (선택 시 연결 정보 자동 입력) --</option>
            <option v-for="j in jobs.jobs" :key="j.id" :value="j.id">{{ j.name }}</option>
          </select>
          <div class="chev"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="2,4 6,8 10,4"/></svg></div>
        </div>

        <div v-if="form.job_config.src_db" class="job-summary">
          <div>소스: {{ form.job_config.src_db }} / {{ form.job_config.src_database }}</div>
          <div>타겟: {{ form.job_config.tgt_db }} / {{ form.job_config.tgt_database }}</div>
          <div>테이블: {{ form.job_config.tables?.length||0 }}개</div>
        </div>

        <div class="modal-btns">
          <button class="btn" @click="showAdd=false">취소</button>
          <button class="btn btn-primary" @click="doAdd" :disabled="!form.name||(form.type==='once'&&!form.run_at)||(form.type==='cron'&&!form.cron_expr)">
            스케줄 등록
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useJobStore } from '@/store/jobStore.js'
import { useAppStore } from '@/store/appStore.js'
import axios from 'axios'

const jobs = useJobStore()
const app  = useAppStore()

const schedules = ref([])
const showAdd   = ref(false)
const form      = ref({
  name:'', type:'once', run_at:'', cron_expr:'', interval_min:60,
  selectedJob:'', job_config:{}
})

const types = [{v:'once',icon:'🕐',l:'1회 실행'},{v:'cron',icon:'🔄',l:'반복 (cron)'},{v:'interval',icon:'⏱',l:'주기 실행'}]
const cronPresets = [
  {l:'매일 새벽 2시',v:'0 2 * * *'},
  {l:'매주 일요일 0시',v:'0 0 * * 0'},
  {l:'매시간',v:'0 * * * *'},
  {l:'매분',v:'* * * * *'},
  {l:'평일 오전 9시',v:'0 9 * * 1-5'},
]

const fmtDt = d => { try { return d?new Date(d).toLocaleString('ko-KR'):'' } catch { return d||'' } }
const statusCls = s => ({waiting:'pill-idle',running:'pill-run',done:'pill-ok',error:'pill-err'}[s]||'pill-idle')
const statusLbl = s => ({waiting:'대기',running:'실행 중',done:'완료',error:'오류'}[s]||s)

async function loadSchedules() {
  try { const {data}=await axios.get('/api/v1/jobs/schedules'); schedules.value=data } catch{}
}

function onJobSelect() {
  const j = jobs.jobs.find(j=>j.id===form.value.selectedJob)
  if (!j) return
  form.value.job_config = {
    name:j.name, src_db:j.src_db, tgt_db:j.tgt_db,
    src_host:j.src_host, src_database:j.src_database,
    src_username:j.src_username||'', src_password:j.src_password||'',
    tgt_host:j.tgt_host, tgt_database:j.tgt_database,
    tgt_username:j.tgt_username||'', tgt_password:j.tgt_password||'',
    tables:j.tables||[], batch_size:j.batch_size||5000,
    truncate_target:j.truncate_target||false, create_table:j.create_table||true,
    on_error:j.on_error||'skip',
  }
}

async function doAdd() {
  try {
    const payload = {
      name: form.value.name,
      type: form.value.type,
      run_at: form.value.run_at,
      cron_expr: form.value.cron_expr,
      interval_min: form.value.interval_min,
      job_config: form.value.job_config,
    }
    const {data} = await axios.post('/api/v1/jobs/schedules', payload)
    schedules.value.unshift(data)
    showAdd.value = false
    form.value = {name:'',type:'once',run_at:'',cron_expr:'',interval_min:60,selectedJob:'',job_config:{}}
    app.notify('스케줄 등록 완료!','success')
  } catch(e) { app.notify('등록 실패: '+e.message,'error') }
}

async function runNow(sid) {
  if (!confirm('지금 즉시 실행하시겠습니까?')) return
  try { await axios.post(`/api/v1/jobs/schedules/${sid}/run-now`); app.notify('즉시 실행 시작!','success'); loadSchedules() }
  catch(e) { app.notify('실행 실패: '+e.message,'error') }
}

async function delSchedule(sid) {
  if (!confirm('스케줄을 삭제하시겠습니까?')) return
  try { await axios.delete(`/api/v1/jobs/schedules/${sid}`); schedules.value=schedules.value.filter(s=>s.id!==sid); app.notify('삭제됨') }
  catch(e) { app.notify('삭제 실패: '+e.message,'error') }
}

onMounted(()=>{ jobs.fetch(); loadSchedules() })
</script>

<style scoped>
.sch-tbl{width:100%;border-collapse:collapse}
.sch-tbl th{background:var(--bg-secondary);font-size:11px;font-weight:500;color:var(--text-tertiary);padding:9px 10px;text-align:left;border-bottom:0.5px solid var(--border-light);white-space:nowrap}
.sch-tbl td{padding:9px 10px;font-size:12px;border-bottom:0.5px solid var(--border-light);color:var(--text-primary)}
.sch-tbl tr:last-child td{border-bottom:none}.sch-tbl tr:hover td{background:var(--bg-secondary)}
.type-badge{font-size:10.5px;font-weight:500;padding:2px 8px;border-radius:8px}
.type-badge.once{background:var(--bg-info);color:var(--text-info)}.type-badge.cron{background:var(--bg-success);color:var(--text-success)}.type-badge.interval{background:var(--bg-warning);color:var(--text-warning)}
.act-btn{font-size:10.5px;padding:3px 8px;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:transparent;color:var(--text-secondary);cursor:pointer;font-family:var(--font);transition:all .12s}
.act-btn:hover{background:var(--bg-secondary)}.act-btn.del{color:var(--text-danger)}.act-btn.del:hover{background:var(--bg-danger);border-color:var(--text-danger)}
.type-btns{display:flex;gap:6px;margin-bottom:4px}
.type-btn{font-size:12px;padding:7px 14px;border-radius:var(--radius-md);border:0.5px solid var(--border-mid);background:transparent;color:var(--text-secondary);cursor:pointer;font-family:var(--font);transition:all .12s}
.type-btn:hover{background:var(--bg-secondary)}.type-btn.active{background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue)}
.cron-presets{display:flex;gap:5px;flex-wrap:wrap;margin-top:6px}
.preset-btn{font-size:11px;padding:3px 8px;border-radius:var(--radius-sm);border:0.5px solid var(--border-mid);background:transparent;color:var(--text-secondary);cursor:pointer;font-family:var(--font);transition:all .12s}
.preset-btn:hover{background:var(--bg-info);color:var(--text-info);border-color:var(--accent-blue)}
.job-summary{background:var(--bg-secondary);border-radius:var(--radius-md);padding:8px 12px;font-size:11.5px;color:var(--text-secondary);line-height:1.7;margin-top:4px}
.sel-wrap{position:relative}.sel-wrap select{width:100%;appearance:none;-webkit-appearance:none;background:var(--bg-secondary);border:0.5px solid var(--border-mid);border-radius:var(--radius-md);padding:7px 28px 7px 10px;font-size:12.5px;color:var(--text-primary);cursor:pointer;font-family:var(--font)}.sel-wrap select:focus{outline:none;border-color:var(--accent-blue)}.chev{position:absolute;right:9px;top:50%;transform:translateY(-50%);pointer-events:none;color:var(--text-tertiary)}.chev svg{width:10px;height:10px;display:block}
</style>
