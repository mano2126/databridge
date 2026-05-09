<template>
  <div>
    <div class="page-title">객체 의존성 맵</div>
    <div class="page-desc">테이블 간 외래키 관계를 인터랙티브 그래프로 시각화하고 최적 이관 순서를 계산합니다</div>

    <!-- 툴바 -->
    <div class="card toolbar-card">
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
        <div style="display:flex;align-items:center;gap:6px">
          <div class="conn-dot" :class="connector.source.status==='ok'?'on':'off'"></div>
          <span style="font-size:12px;color:var(--text-secondary)">{{ connector.source.database || '미연결' }}</span>
          <span style="font-size:10.5px;color:var(--text-tertiary)">({{ connector.source.dbType || '-' }})</span>
        </div>
        <button class="btn btn-primary" style="font-size:12px" @click="loadDeps" :disabled="loading">
          <span v-if="loading" class="spinner" style="width:12px;height:12px;display:inline-block;margin-right:5px;border-top-color:#fff"></span>
          {{ loading ? '분석 중...' : '의존성 분석 실행' }}
        </button>
        <div v-if="nodes.length" style="display:flex;gap:6px;align-items:center">
          <span class="stat-chip info">테이블 {{ nodes.length }}개</span>
          <span class="stat-chip warn">FK {{ edges.length }}개</span>
        </div>
        <div v-if="nodes.length" style="margin-left:auto;display:flex;gap:6px;align-items:center">
          <button class="act-btn" @click="resetView">⌂ 리셋</button>
          <button class="act-btn" @click="toggleSim">{{ simRunning ? '⏸ 정지' : '▶ 재배치' }}</button>
        </div>
      </div>
    </div>

    <div v-if="errMsg" class="err-banner" style="margin-bottom:10px">⚠ {{ errMsg }}</div>

    <!-- 메인 -->
    <div v-if="nodes.length" class="main-layout">
      <!-- Canvas -->
      <div class="graph-card card">
        <div class="graph-info-bar">
          <div style="display:flex;gap:12px;align-items:center">
            <span class="leg-item"><span class="leg-dot root-c"></span>독립</span>
            <span class="leg-item"><span class="leg-dot mid-c"></span>중간</span>
            <span class="leg-item"><span class="leg-dot leaf-c"></span>최하위</span>
          </div>
          <span style="font-size:11px;color:var(--text-tertiary)">스크롤 확대/축소 · 드래그 이동 · 노드 클릭 상세</span>
        </div>
        <div class="canvas-wrap" ref="canvasWrap">
          <canvas ref="cvs"
            @mousedown="onMD" @mousemove="onMM" @mouseup="onMU"
            @mouseleave="onMU" @wheel.prevent="onWheel"
            style="display:block"></canvas>
          <div v-if="tip.vis" class="tip-box" :style="{left:tip.x+'px',top:tip.y+'px'}">
            <div class="tip-name">{{ tip.node }}</div>
            <div class="tip-row"><span>rows</span><span>{{ tip.rows }}</span></div>
            <div class="tip-row"><span>FK</span><span>{{ tip.fks }}개</span></div>
            <div class="tip-row"><span>이관순서</span><span>#{{ tip.order }}</span></div>
          </div>
        </div>
      </div>

      <!-- 사이드 -->
      <div class="side-col">
        <div class="card side-card" v-if="selNode">
          <div class="side-title">📋 {{ selNode.id }}</div>
          <div class="dg">
            <div class="dg-item"><span class="dg-l">rows</span><span class="dg-v">{{ (selNode.rows||0).toLocaleString() }}</span></div>
            <div class="dg-item"><span class="dg-l">이관순서</span><span class="dg-v">#{{ selNode.order }}</span></div>
            <div class="dg-item"><span class="dg-l">FK</span><span class="dg-v">{{ selNode.fks.length }}개</span></div>
            <div class="dg-item"><span class="dg-l">참조됨</span><span class="dg-v">{{ refBy(selNode.id).length }}개</span></div>
          </div>
          <template v-if="selNode.fks.length">
            <div class="fk-hdr">외래키</div>
            <div v-for="fk in selNode.fks" :key="fk.col" class="fk-chip" @click="selectNode(fk.refTable)">
              <span class="fk-col">{{ fk.col }}</span><span class="fk-arr">→</span>
              <span class="fk-ref">{{ fk.refTable }}.{{ fk.refCol }}</span>
              <span class="fk-rule">{{ fk.onDelete }}</span>
            </div>
          </template>
          <template v-if="refBy(selNode.id).length">
            <div class="fk-hdr" style="margin-top:8px">이 테이블을 참조</div>
            <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:4px">
              <span v-for="t in refBy(selNode.id)" :key="t" class="ref-chip" @click="selectNode(t)">{{ t }}</span>
            </div>
          </template>
        </div>

        <div class="card side-card" style="flex:1;overflow:hidden;display:flex;flex-direction:column">
          <div class="side-title">⬇ 권장 이관 순서</div>
          <div class="order-list">
            <div v-for="(t,i) in orderList" :key="t.name"
                 class="order-row" :class="{active:selNode?.id===t.name}"
                 @click="selectNode(t.name)">
              <div class="o-num" :class="numCls(i)">{{ i+1 }}</div>
              <div style="flex:1;min-width:0">
                <div class="o-name">{{ t.name }}</div>
                <div class="o-reason">{{ t.reason }}</div>
              </div>
              <span class="o-rows">{{ fmtRows(t.rows) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 빈 상태 -->
    <div v-else class="card empty-hero">
      <svg viewBox="0 0 80 80" fill="none" stroke="currentColor" stroke-width="1.2" style="width:56px;height:56px;opacity:.4">
        <circle cx="20" cy="20" r="8"/><circle cx="60" cy="20" r="8"/><circle cx="40" cy="60" r="8"/>
        <line x1="27" y1="22" x2="53" y2="22" stroke-dasharray="4 3"/>
        <line x1="24" y1="26" x2="37" y2="54" stroke-dasharray="4 3"/>
        <line x1="56" y1="26" x2="43" y2="54" stroke-dasharray="4 3"/>
      </svg>
      <div style="font-size:14px;font-weight:500;color:var(--text-secondary)">의존성 맵이 없습니다</div>
      <div style="font-size:12px;color:var(--text-tertiary)">소스 DB를 연결하고 분석 실행 버튼을 클릭하세요</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useConnectorStore } from '@/store/connectorStore.js'
import axios from 'axios'

const connector = useConnectorStore()
const loading   = ref(false)
const errMsg    = ref('')
const cvs       = ref(null)
const canvasWrap= ref(null)
const selNode   = ref(null)
const orderList = ref([])
const simRunning= ref(false)
const nodes     = ref([])
const edges     = ref([])
const tip       = ref({ vis:false, x:0, y:0, node:'', rows:'', fks:0, order:0 })

let ctx = null, animId = null
let vp  = { scale:1, tx:0, ty:0 }
let isDragging=false, dragNode=null, lastMX=0, lastMY=0
let simTick=0

// ── API ───────────────────────────────────────────────
async function loadDeps(){
  const c = connector.source
  if(!c.host||!c.database){ errMsg.value='소스 DB 연결 정보가 없습니다.'; return }
  loading.value=true; errMsg.value=''
  try{
    const {data} = await axios.get('/api/v1/schema/dependencies',{
      params:{db_type:c.dbType||c.db_type,host:c.host,port:c.port,username:c.username,password:c.password,database:c.database}
    })
    buildGraph(data)
  }catch(e){ errMsg.value='분석 실패: '+(e.response?.data?.detail||e.message) }
  finally{ loading.value=false }
}

function buildGraph(data){
  orderList.value = data.order||[]
  const orderMap={}
  ;(data.order||[]).forEach((o,i)=>{ orderMap[o.name]=i+1 })
  
  nodes.value = (data.tables||[]).map((t,i)=>{
    const angle=(i/(data.tables.length||1))*Math.PI*2
    const r=180
    return { id:t.name, x:350+Math.cos(angle)*r+(Math.random()-.5)*30, y:280+Math.sin(angle)*r+(Math.random()-.5)*30,
             vx:0, vy:0, rows:t.rows||0, fks:t.fks||[], order:orderMap[t.name]||99, pinned:false }
  })
  edges.value=[]
  const edgeSet=new Set()
  ;(data.tables||[]).forEach(t=>{
    ;(t.fks||[]).forEach(fk=>{
      const key=t.name+'→'+fk.refTable
      if(!edgeSet.has(key)){ edgeSet.add(key); edges.value.push({src:t.name,tgt:fk.refTable,onDelete:fk.onDelete||'',col:fk.col}) }
    })
  })
  vp={scale:1,tx:0,ty:0}; selNode.value=null
  nextTick(()=>{ initCanvas(); simTick=0; simRunning.value=true; startLoop() })
}

// ── Canvas ────────────────────────────────────────────
function initCanvas(){
  if(!cvs.value||!canvasWrap.value) return
  const wrap=canvasWrap.value, dpr=window.devicePixelRatio||1
  const W=wrap.clientWidth, H=wrap.clientHeight
  cvs.value.width=W*dpr; cvs.value.height=H*dpr
  cvs.value.style.width=W+'px'; cvs.value.style.height=H+'px'
  ctx=cvs.value.getContext('2d'); ctx.scale(dpr,dpr)
}

function nr(n){ return Math.min(30,Math.max(16,12+Math.log1p(n.rows||0)*1.4)) }

function nColor(n){
  const isRoot=n.fks.length===0
  const isLeaf=!edges.value.some(e=>e.tgt===n.id)
  if(isRoot)  return {fill:'#d1fae5',stroke:'#10b981'}
  if(isLeaf)  return {fill:'#fef3c7',stroke:'#f59e0b'}
  return {fill:'#dbeafe',stroke:'#3b82f6'}
}

function draw(){
  if(!ctx||!canvasWrap.value) return
  const W=canvasWrap.value.clientWidth, H=canvasWrap.value.clientHeight
  ctx.clearRect(0,0,W,H)
  
  const dark=document.documentElement.getAttribute('data-theme')==='dark'
  ctx.fillStyle=dark?'#1a1d2e':'#f8fafc'; ctx.fillRect(0,0,W,H)
  ctx.save(); ctx.translate(vp.tx,vp.ty); ctx.scale(vp.scale,vp.scale)
  
  const nm={}; nodes.value.forEach(n=>{nm[n.id]=n})
  
  // 엣지
  edges.value.forEach(e=>{
    const s=nm[e.src],t=nm[e.tgt]; if(!s||!t) return
    const isSel=selNode.value&&(e.src===selNode.value.id||e.tgt===selNode.value.id)
    const isOut=selNode.value&&e.src===selNode.value.id
    
    ctx.globalAlpha=selNode.value&&!isSel?.15:.65
    const mx=(s.x+t.x)/2+(t.y-s.y)*.12, my=(s.y+t.y)/2-(t.x-s.x)*.12
    ctx.beginPath(); ctx.moveTo(s.x,s.y); ctx.quadraticCurveTo(mx,my,t.x,t.y)
    ctx.strokeStyle=isOut?'#3b82f6':(dark?'#334155':'#cbd5e1')
    ctx.lineWidth=isOut?2:1; ctx.stroke()
    
    // 화살표
    const tx2=2*.9*(mx-s.x)+2*.1*(t.x-mx), ty2=2*.9*(my-s.y)+2*.1*(t.y-my)
    const ang=Math.atan2(ty2,tx2), tr=nr(t)+3
    const ex=t.x-Math.cos(ang)*tr, ey=t.y-Math.sin(ang)*tr
    ctx.beginPath()
    ctx.moveTo(ex,ey)
    ctx.lineTo(ex-8*Math.cos(ang-.4),ey-8*Math.sin(ang-.4))
    ctx.lineTo(ex-8*Math.cos(ang+.4),ey-8*Math.sin(ang+.4))
    ctx.closePath()
    ctx.fillStyle=isOut?'#3b82f6':(dark?'#475569':'#94a3b8'); ctx.fill()
    ctx.globalAlpha=1
    
    // 컬럼 라벨 (선택 시)
    if(isSel&&vp.scale>.7){
      ctx.font=`${9/vp.scale}px monospace`; ctx.fillStyle=dark?'#94a3b8':'#64748b'
      ctx.textAlign='center'; ctx.globalAlpha=.8
      ctx.fillText(e.col,mx,my-5); ctx.globalAlpha=1
    }
  })
  
  // 노드
  nodes.value.forEach(n=>{
    const r=nr(n), col=nColor(n), isSel=selNode.value?.id===n.id
    const isDim=selNode.value&&!isSel&&!edges.value.some(e=>(e.src===selNode.value.id&&e.tgt===n.id)||(e.tgt===selNode.value.id&&e.src===n.id))
    ctx.globalAlpha=isDim?.2:1
    ctx.shadowColor=col.stroke+'44'; ctx.shadowBlur=isSel?14:5; ctx.shadowOffsetX=0; ctx.shadowOffsetY=1
    ctx.beginPath(); ctx.arc(n.x,n.y,r,0,Math.PI*2)
    ctx.fillStyle=isSel?col.stroke:(dark?dkFill(col.fill):col.fill); ctx.fill()
    ctx.strokeStyle=col.stroke; ctx.lineWidth=isSel?2.5:1.5; ctx.stroke()
    ctx.shadowBlur=0
    
    const fs=Math.min(10.5,Math.max(8,r*.52))
    ctx.font=(isSel?'600 ':'')+fs+'px Consolas,monospace'
    ctx.fillStyle=isSel?'#fff':(dark?'#e2e8f0':'#1e293b')
    ctx.textAlign='center'; ctx.textBaseline='middle'
    const lbl=n.id.length>13?n.id.slice(0,11)+'…':n.id
    ctx.fillText(lbl,n.x,n.y)
    
    if(n.rows>0&&vp.scale>.55){
      ctx.font=(Math.max(7,fs*.75))+'px sans-serif'
      ctx.fillStyle=dark?'#64748b':'#94a3b8'
      ctx.fillText(fmtRows(n.rows),n.x,n.y+r+10)
    }
    ctx.globalAlpha=1
  })
  ctx.restore()
}

function dkFill(h){ return h.replace('#d1fae5','#064e3b').replace('#dbeafe','#1e3a5f').replace('#fef3c7','#451a03') }

// ── 포스 시뮬레이션 ───────────────────────────────────
function simStep(){
  const ns=nodes.value, es=edges.value
  const nm={}; ns.forEach(n=>{nm[n.id]=n})
  const W=canvasWrap.value?.clientWidth||700, H=canvasWrap.value?.clientHeight||500
  
  for(let i=0;i<ns.length;i++) for(let j=i+1;j<ns.length;j++){
    const a=ns[i],b=ns[j]
    const dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)||1
    const min=nr(a)+nr(b)+28
    if(d<min*2.8){ const f=Math.min(.6,(min*2.8-d)/(min*2.8))*3
      const fx=dx/d*f,fy=dy/d*f
      if(!a.pinned){a.vx-=fx;a.vy-=fy} if(!b.pinned){b.vx+=fx;b.vy+=fy}
    }
  }
  es.forEach(e=>{ const s=nm[e.src],t=nm[e.tgt]; if(!s||!t) return
    const dx=t.x-s.x,dy=t.y-s.y,d=Math.sqrt(dx*dx+dy*dy)||1,tgt=100
    const f=(d-tgt)/d*.09,fx=dx*f,fy=dy*f
    if(!s.pinned){s.vx+=fx;s.vy+=fy} if(!t.pinned){t.vx-=fx;t.vy-=fy}
  })
  ns.forEach(n=>{ if(n.pinned) return
    n.vx+=(W/2-n.x)*.003; n.vy+=(H/2-n.y)*.003
    n.vx*=.85; n.vy*=.85; n.x+=n.vx; n.y+=n.vy
    n.x=Math.max(nr(n),Math.min(W-nr(n),n.x)); n.y=Math.max(nr(n),Math.min(H-nr(n),n.y))
  })
}

function startLoop(){
  if(animId) cancelAnimationFrame(animId)
  function loop(){
    if(simRunning.value&&simTick<250){ simStep(); simTick++; if(simTick>=200) simRunning.value=false }
    draw(); animId=requestAnimationFrame(loop)
  }
  loop()
}

function toggleSim(){ simRunning.value=!simRunning.value; if(simRunning.value){simTick=0;simRunning.value=true} }
function resetView(){ vp={scale:1,tx:0,ty:0}; selNode.value=null; simTick=0; simRunning.value=true }

// ── 마우스 ────────────────────────────────────────────
function cpos(e){ const r=cvs.value.getBoundingClientRect(); return {x:(e.clientX-r.left-vp.tx)/vp.scale,y:(e.clientY-r.top-vp.ty)/vp.scale} }
function hit(x,y){ for(const n of nodes.value){const r=nr(n),dx=n.x-x,dy=n.y-y;if(dx*dx+dy*dy<r*r)return n} return null }

function onMD(e){ if(e.button!==0) return
  const p=cpos(e),h=hit(p.x,p.y)
  if(h){dragNode=h;h.pinned=true}
  else{isDragging=true;lastMX=e.clientX;lastMY=e.clientY}
}
function onMM(e){
  const r=cvs.value.getBoundingClientRect(), p=cpos(e), h=hit(p.x,p.y)
  if(h){ tip.value={vis:true,x:e.clientX-r.left+12,y:e.clientY-r.top-10,node:h.id,rows:(h.rows||0).toLocaleString(),fks:h.fks.length,order:h.order}; cvs.value.style.cursor='pointer' }
  else{ tip.value.vis=false; cvs.value.style.cursor=isDragging?'grabbing':'grab' }
  if(dragNode){dragNode.x=p.x;dragNode.y=p.y;dragNode.vx=0;dragNode.vy=0}
  else if(isDragging){vp.tx+=e.clientX-lastMX;vp.ty+=e.clientY-lastMY;lastMX=e.clientX;lastMY=e.clientY}
}
function onMU(e){
  if(dragNode){ dragNode.pinned=false; selectNode(dragNode.id); dragNode=null }
  isDragging=false
}
function onWheel(e){
  const r=cvs.value.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top
  const d=e.deltaY>0?.9:1.1, ns=Math.min(4,Math.max(.2,vp.scale*d))
  vp.tx=mx-(mx-vp.tx)*(ns/vp.scale); vp.ty=my-(my-vp.ty)*(ns/vp.scale); vp.scale=ns
}

function selectNode(name){ const n=nodes.value.find(nd=>nd.id===name); if(n) selNode.value=n }
function refBy(name){ return nodes.value.filter(n=>n.fks.some(f=>f.refTable===name)).map(n=>n.id) }
function fmtRows(n){ if(!n) return ''; if(n>=1e6) return(n/1e6).toFixed(1)+'M'; if(n>=1e3) return Math.round(n/1e3)+'K'; return String(n) }
function numCls(i){ const l=orderList.value.length; if(orderList.value[i]?.deps?.length===0) return 'n-root'; if(i<l*.35) return 'n-early'; if(i<l*.7) return 'n-mid'; return 'n-late' }

let ro=null
onMounted(()=>{
  if(window.ResizeObserver&&canvasWrap.value){
    ro=new ResizeObserver(()=>{if(nodes.value.length){initCanvas()}})
    ro.observe(canvasWrap.value)
  }
})
onUnmounted(()=>{ if(animId) cancelAnimationFrame(animId); if(ro) ro.disconnect() })
</script>

<style scoped>
.toolbar-card{padding:10px 16px;margin-bottom:12px}
.conn-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.conn-dot.on{background:#4ade80;box-shadow:0 0 6px #4ade8066}
.conn-dot.off{background:var(--border-mid)}
.stat-chip{font-size:10.5px;padding:2px 8px;border-radius:10px;font-weight:500}
.stat-chip.info{background:var(--bg-info);color:var(--text-info)}
.stat-chip.warn{background:var(--bg-warning);color:var(--text-warning)}

.main-layout{display:grid;grid-template-columns:1fr 290px;gap:12px;min-height:580px}

.graph-card{padding:0;overflow:hidden;display:flex;flex-direction:column}
.graph-info-bar{display:flex;align-items:center;justify-content:space-between;padding:7px 14px;border-bottom:0.5px solid var(--border-light);flex-shrink:0;flex-wrap:wrap;gap:6px}
.canvas-wrap{flex:1;position:relative;min-height:500px;overflow:hidden}
.canvas-wrap canvas{position:absolute;top:0;left:0}

.leg-item{display:flex;align-items:center;gap:4px;font-size:10.5px;color:var(--text-tertiary)}
.leg-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.leg-dot.root-c{background:#d1fae5;border:1.5px solid #10b981}
.leg-dot.mid-c{background:#dbeafe;border:1.5px solid #3b82f6}
.leg-dot.leaf-c{background:#fef3c7;border:1.5px solid #f59e0b}

.tip-box{position:absolute;pointer-events:none;background:var(--bg-primary);border:0.5px solid var(--border-mid);border-radius:var(--radius-md);padding:8px 12px;min-width:150px;box-shadow:0 4px 16px rgba(0,0,0,.12);z-index:100}
.tip-name{font-size:12px;font-weight:600;color:var(--text-primary);font-family:'Consolas','SF Mono',monospace;margin-bottom:5px;border-bottom:0.5px solid var(--border-light);padding-bottom:4px}
.tip-row{display:flex;justify-content:space-between;font-size:11px;padding:1.5px 0;color:var(--text-secondary)}
.tip-row span:first-child{color:var(--text-tertiary)}

.side-col{display:flex;flex-direction:column;gap:10px}
.side-card{padding:12px 14px}
.side-title{font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:8px}
.dg{display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-bottom:8px}
.dg-item{display:flex;align-items:center;gap:4px;padding:3px 6px;background:var(--bg-secondary);border-radius:var(--radius-sm);font-size:11px}
.dg-l{color:var(--text-tertiary);min-width:40px}
.dg-v{color:var(--text-primary);font-weight:500}

.fk-hdr{font-size:10px;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px}
.fk-chip{display:flex;align-items:center;gap:4px;padding:4px 7px;background:var(--bg-secondary);border-radius:var(--radius-sm);font-size:11px;margin-bottom:3px;cursor:pointer;transition:background .12s}
.fk-chip:hover{background:var(--bg-hover)}
.fk-col{font-family:'Consolas','SF Mono',monospace;color:var(--text-info);font-weight:500}
.fk-arr{color:var(--text-tertiary);font-size:10px}
.fk-ref{font-family:'Consolas','SF Mono',monospace;color:var(--text-success);flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fk-rule{font-size:9.5px;background:var(--bg-tertiary);color:var(--text-tertiary);padding:1px 5px;border-radius:3px;flex-shrink:0}
.ref-chip{padding:2px 8px;background:var(--bg-info);color:var(--text-info);border-radius:10px;font-size:10.5px;font-family:'Consolas','SF Mono',monospace;cursor:pointer;transition:all .12s}
.ref-chip:hover{background:var(--accent-blue);color:#fff}

.order-list{overflow-y:auto;max-height:360px}
.order-row{display:flex;align-items:center;gap:8px;padding:5px 3px;border-radius:var(--radius-sm);cursor:pointer;transition:background .12s}
.order-row:hover{background:var(--bg-hover)}
.order-row.active{background:var(--bg-info)}
.o-num{width:20px;height:20px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:9.5px;font-weight:600;flex-shrink:0}
.n-root{background:#d1fae5;color:#059669}
.n-early{background:#dbeafe;color:#2563eb}
.n-mid{background:#fef3c7;color:#d97706}
.n-late{background:#fee2e2;color:#dc2626}
.o-name{font-size:11.5px;font-weight:500;font-family:'Consolas','SF Mono',monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.o-reason{font-size:10px;color:var(--text-tertiary)}
.o-rows{font-size:10.5px;color:var(--text-tertiary);white-space:nowrap;flex-shrink:0}

.empty-hero{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;min-height:300px;text-align:center}
</style>