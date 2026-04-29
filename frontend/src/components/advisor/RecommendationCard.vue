<!--
  RecommendationCard.vue — 단일 권고 카드
  ========================================
  v88 P2 (2026-04-23)

  Props:
    - rec:      Recommendation 객체 (base_advisor.py Recommendation 스키마와 동일)
    - decision: 'pending' | 'applied' | 'skipped' | 'edited'
    - editedSql: 사용자 수정 SQL (decision == 'edited' 시)

  Emits:
    - update:decision — 결정 변경 시
    - update:edited-sql — 수동 편집 저장 시
-->
<template>
  <div class="rec-card" :class="['sev-' + rec.severity, 'dec-' + decision]">
    <!-- 카드 헤더 (항상 보임) -->
    <div class="rc-header" @click="expanded = !expanded">
      <span class="rc-sev-badge" :class="'sev-' + rec.severity">
        <span class="rc-sev-dot"></span>
        {{ sevLabel }}
      </span>
      <div class="rc-header-body">
        <div class="rc-title">{{ rec.title }}</div>
        <div class="rc-target">
          <span class="rc-target-label">대상:</span>
          <span class="rc-target-value">{{ rec.target }}</span>
        </div>
      </div>
      <div class="rc-header-right">
        <!-- 결정 상태 배지 -->
        <span v-if="decision !== 'pending'" class="rc-decision-badge" :class="'dec-' + decision">
          {{ decisionLabel }}
        </span>
        <!-- 펼침 화살표 -->
        <svg class="rc-chev" :class="{open: expanded}"
             viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
          <polyline points="3,4 6,8 9,4"/>
        </svg>
      </div>
    </div>

    <!-- 카드 상세 (펼쳤을 때만) -->
    <div v-if="expanded" class="rc-body">
      <!-- 예상 개선 -->
      <div v-if="rec.estimated_impact" class="rc-impact">
        <span class="rc-impact-ico">📊</span>
        <span class="rc-impact-text">{{ rec.estimated_impact }}</span>
      </div>

      <!-- Before / After -->
      <div v-if="rec.before || rec.after" class="rc-diff-row">
        <div class="rc-diff-col rc-diff-before">
          <div class="rc-diff-label">Before (현재)</div>
          <pre class="rc-diff-code">{{ rec.before || '(설정 없음)' }}</pre>
        </div>
        <div class="rc-diff-arrow">→</div>
        <div class="rc-diff-col rc-diff-after">
          <div class="rc-diff-label">After (권고)</div>
          <pre class="rc-diff-code" v-if="decision !== 'edited'">{{ rec.after }}</pre>
          <!-- 편집 모드 -->
          <textarea
            v-else
            v-model="editedDraft"
            class="rc-diff-edit"
            spellcheck="false"
            rows="6"
            @blur="saveEdit"
          ></textarea>
        </div>
      </div>

      <!-- 근거 (reason) -->
      <div class="rc-reason">
        <div class="rc-reason-label">근거</div>
        <div class="rc-reason-text">{{ rec.reason }}</div>
      </div>

      <!-- 메타 -->
      <div class="rc-meta">
        <span class="rc-meta-item">
          <span class="rc-meta-label">source</span>
          <span class="rc-meta-value">{{ sourceLabel }}</span>
        </span>
        <span class="rc-meta-item">
          <span class="rc-meta-label">confidence</span>
          <span class="rc-meta-value">{{ (rec.confidence * 100).toFixed(0) }}%</span>
        </span>
        <span v-if="rec.auto_applicable" class="rc-meta-item rc-auto">
          <span class="rc-auto-ico">⚙</span> 자동 적용 가능
        </span>
        <span v-else class="rc-meta-item rc-manual">
          <span class="rc-manual-ico">✋</span> 수동 적용 필요
        </span>
      </div>

      <!-- hotfix 2026-04-23: 적용 방법 명시 — 버튼이 실제로 뭘 하는지 설명 -->
      <div class="rc-how-applied" :class="{ 'is-auto': rec.auto_applicable }">
        <div class="rc-how-label">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5"
               style="width:11px;height:11px">
            <circle cx="7" cy="7" r="5.5"/>
            <line x1="7" y1="4" x2="7" y2="7.5"/>
            <circle cx="7" cy="9.5" r=".6" fill="currentColor"/>
          </svg>
          <span>"적용" 버튼이 하는 일</span>
        </div>
        <div class="rc-how-text">
          <template v-if="rec.auto_applicable">
            <b>자동 실행 가능</b> —
            <span class="rc-how-when">이관 완료 후</span> DataBridge 가 이 권고를 자동 실행합니다.
            <span v-if="needsDbaAction" class="rc-how-caveat">
              ⚠ 단, 서버 설정(my.cnf 등) 변경은 재시작이 필요해 DBA 가 직접 반영해야 합니다.
            </span>
          </template>
          <template v-else>
            <b>DBA 수동 작업</b> — 이 권고는 DataBridge 가 자동으로 실행하지 않습니다.
            "적용" 버튼은 <span class="rc-how-note">"이 권고를 채택한다"는 기록</span>만 남깁니다.
            실제 반영은 <b>DBA 가 권고 내용을 보고 직접 실행</b>해야 합니다
            ({{ manualHint }}).
          </template>
        </div>
      </div>

      <!-- 액션 버튼 -->
      <div class="rc-actions">
        <button
          class="rc-btn rc-btn-apply"
          :class="{ active: decision === 'applied' || decision === 'edited' }"
          @click="setDecision('applied')"
        >
          <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2"
               style="width:11px;height:11px">
            <polyline points="2,6 5,9 10,3"/>
          </svg>
          적용
        </button>
        <button
          class="rc-btn rc-btn-skip"
          :class="{ active: decision === 'skipped' }"
          @click="setDecision('skipped')"
        >
          <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2"
               style="width:11px;height:11px">
            <line x1="3" y1="3" x2="9" y2="9"/>
            <line x1="9" y1="3" x2="3" y2="9"/>
          </svg>
          건너뜀
        </button>
        <button
          class="rc-btn rc-btn-edit"
          :class="{ active: decision === 'edited' }"
          @click="startEdit"
        >
          <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"
               style="width:11px;height:11px">
            <path d="M2,10 L2,8 L8,2 L10,4 L4,10 Z"/>
          </svg>
          수동 편집
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  rec:       { type: Object, required: true },
  decision:  { type: String, default: 'pending' },
  editedSql: { type: String, default: '' },
})

const emit = defineEmits(['update:decision', 'update:edited-sql'])

const expanded    = ref(props.rec.severity === 'high')   // HIGH 는 기본 펼침
const editedDraft = ref(props.editedSql || props.rec.after || '')

// 편집 모드에서 사용자가 prop 을 바꿀 때 sync
watch(() => props.editedSql, (v) => { editedDraft.value = v || props.rec.after || '' })

const sevLabel = computed(() => ({
  high: 'HIGH',
  med:  'MED',
  low:  'LOW',
})[props.rec.severity] || props.rec.severity)

const decisionLabel = computed(() => ({
  applied: '✓ 적용',
  skipped: '× 건너뜀',
  edited:  '✎ 수정됨',
  pending: '',
})[props.decision] || '')

const sourceLabel = computed(() => ({
  rule:   '규칙 기반',
  ai:     'AI 분석',
  hybrid: '규칙 + AI',
})[props.rec.source] || props.rec.source)

// hotfix 2026-04-23: 적용 방법 안내 박스용 computed
// 카테고리별로 "실제 반영은 어떻게 되는가" 안내 문구 분기.
const needsDbaAction = computed(() => {
  // server 카테고리는 auto_applicable=true 여도 my.cnf 쪽은 DBA 작업 필요
  const cat = props.rec.category
  const target = (props.rec.target || '').toLowerCase()
  if (cat === 'server') return true
  if (target.includes('my.cnf') || target.includes('postgresql.conf')) return true
  return false
})

const manualHint = computed(() => {
  const cat = props.rec.category
  const target = props.rec.target || ''
  if (target.toLowerCase().includes('my.cnf') || target.toLowerCase().includes('postgresql.conf')) {
    return 'my.cnf 수정 → DB 서버 재시작'
  }
  if (cat === 'table') {
    const t = props.rec.title || ''
    if (t.includes('파티셔닝')) return '이관 전 타겟 DDL 에 반영 또는 이관 후 ALTER TABLE'
    if (t.includes('오버스펙')) return '실사용 길이 측정 후 ALTER TABLE MODIFY COLUMN'
    if (t.includes('BINARY') || t.includes('GUID')) return '이관 DDL 수정 + 앱 코드 수정 필요'
    return '타겟 DB 에서 ALTER TABLE 수동 실행'
  }
  if (cat === 'index') {
    const t = props.rec.title || ''
    if (t.includes('중복')) return '타겟 DB 에서 DROP INDEX 실행'
    if (t.includes('누락') || t.includes('필수')) return '이관 완료 후 CREATE INDEX 실행'
    if (t.includes('과다')) return '사용량 측정 후 불필요 인덱스 DROP'
    return '타겟 DB 에서 인덱스 DDL 수동 실행'
  }
  if (cat === 'object') {
    return 'SP/View DDL 을 재작성 후 타겟 DB 에 재배포'
  }
  if (cat === 'server') {
    return '타겟 DB 설정 파일 수정 또는 SET GLOBAL 실행'
  }
  return '권고 내용을 타겟 DB 에 수동 반영'
})

function setDecision(val) {
  emit('update:decision', val)
  if (val !== 'edited') {
    // 적용/건너뜀 으로 바꾸면 편집 초안을 원본으로 리셋 (의도치 않은 저장 방지)
    editedDraft.value = props.rec.after || ''
    emit('update:edited-sql', '')
  }
}

function startEdit() {
  emit('update:decision', 'edited')
  expanded.value = true
  editedDraft.value = props.editedSql || props.rec.after || ''
}

function saveEdit() {
  if (props.decision === 'edited') {
    emit('update:edited-sql', editedDraft.value)
  }
}
</script>

<style scoped>
.rec-card {
  border-radius: 8px;
  border: 1px solid var(--border-light, #e2e8f0);
  background: var(--bg-primary, #fff);
  overflow: hidden;
  transition: all 0.15s;
}
.rec-card:hover {
  border-color: var(--border-medium, #cbd5e1);
}
.rec-card.sev-high {
  border-left: 3px solid #dc2626;
}
.rec-card.sev-med {
  border-left: 3px solid #f59e0b;
}
.rec-card.sev-low {
  border-left: 3px solid #3b82f6;
}
.rec-card.dec-applied {
  background: rgba(22, 163, 74, 0.03);
}
.rec-card.dec-skipped {
  opacity: 0.6;
}
.rec-card.dec-edited {
  background: rgba(109, 40, 217, 0.03);
}

/* ── 헤더 ── */
.rc-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
}
.rc-sev-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 10px;
  letter-spacing: 0.04em;
  flex-shrink: 0;
}
.rc-sev-badge.sev-high {
  background: rgba(220, 38, 38, 0.1);
  color: #991b1b;
}
.rc-sev-badge.sev-med {
  background: rgba(245, 158, 11, 0.1);
  color: #b45309;
}
.rc-sev-badge.sev-low {
  background: rgba(59, 130, 246, 0.1);
  color: #1d4ed8;
}
.rc-sev-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}

.rc-header-body {
  flex: 1;
  min-width: 0;
}
.rc-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-primary, #1e293b);
  line-height: 1.4;
}
.rc-target {
  font-size: 11px;
  color: var(--text-tertiary, #94a3b8);
  margin-top: 2px;
}
.rc-target-label {
  margin-right: 4px;
}
.rc-target-value {
  color: var(--text-secondary, #64748b);
  font-weight: 500;
}

.rc-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.rc-decision-badge {
  font-size: 10.5px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 10px;
}
.rc-decision-badge.dec-applied {
  background: rgba(22, 163, 74, 0.12);
  color: #15803d;
}
.rc-decision-badge.dec-skipped {
  background: rgba(100, 116, 139, 0.12);
  color: #475569;
}
.rc-decision-badge.dec-edited {
  background: rgba(109, 40, 217, 0.12);
  color: #6d28d9;
}
.rc-chev {
  width: 11px;
  height: 11px;
  opacity: 0.5;
  transition: transform 0.18s;
}
.rc-chev.open {
  transform: rotate(180deg);
}

/* ── 상세 바디 ── */
.rc-body {
  padding: 12px 14px 14px;
  border-top: 1px solid var(--border-light, #e2e8f0);
  background: var(--bg-secondary, #f8fafc);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rc-impact {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  background: linear-gradient(135deg, rgba(22, 163, 74, 0.06), rgba(59, 130, 246, 0.04));
  border: 1px solid rgba(22, 163, 74, 0.2);
  font-size: 11.5px;
  font-weight: 500;
  color: #15803d;
}
.rc-impact-ico {
  font-size: 14px;
}

/* ── Before / After diff ── */
.rc-diff-row {
  display: flex;
  gap: 8px;
  align-items: stretch;
}
.rc-diff-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.rc-diff-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-tertiary, #94a3b8);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 4px;
}
.rc-diff-code {
  margin: 0;
  padding: 8px 10px;
  background: var(--bg-primary, #fff);
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 5px;
  font-family: 'JetBrains Mono', 'Menlo', monospace;
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-primary, #1e293b);
  white-space: pre-wrap;
  word-break: break-all;
  min-height: 40px;
  flex: 1;
}
.rc-diff-before .rc-diff-code {
  color: var(--text-tertiary, #94a3b8);
  text-decoration-color: rgba(220, 38, 38, 0.3);
}
.rc-diff-after .rc-diff-code {
  border-color: rgba(22, 163, 74, 0.4);
  background: rgba(22, 163, 74, 0.03);
}
.rc-diff-edit {
  width: 100%;
  padding: 8px 10px;
  background: rgba(109, 40, 217, 0.03);
  border: 1px solid rgba(109, 40, 217, 0.4);
  border-radius: 5px;
  font-family: 'JetBrains Mono', 'Menlo', monospace;
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-primary);
  resize: vertical;
  outline: none;
}
.rc-diff-edit:focus {
  border-color: #6d28d9;
  box-shadow: 0 0 0 2px rgba(109, 40, 217, 0.15);
}
.rc-diff-arrow {
  display: flex;
  align-items: center;
  font-size: 18px;
  color: var(--text-tertiary, #94a3b8);
  padding-top: 20px;
}

/* ── Reason ── */
.rc-reason {
  padding: 10px 12px;
  background: var(--bg-primary, #fff);
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 6px;
}
.rc-reason-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-tertiary, #94a3b8);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 5px;
}
.rc-reason-text {
  font-size: 11.5px;
  color: var(--text-secondary, #64748b);
  line-height: 1.65;
  white-space: pre-line;
}

/* ── Meta ── */
.rc-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 6px 10px;
  background: var(--bg-primary, #fff);
  border-radius: 6px;
  font-size: 10.5px;
}
.rc-meta-item {
  display: flex;
  align-items: center;
  gap: 5px;
}
.rc-meta-label {
  color: var(--text-tertiary, #94a3b8);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-size: 9.5px;
}
.rc-meta-value {
  color: var(--text-secondary, #64748b);
  font-weight: 500;
}
.rc-auto {
  color: #15803d;
}
.rc-manual {
  color: #b45309;
}

/* hotfix 2026-04-23: "적용 버튼이 하는 일" 안내 박스 */
.rc-how-applied {
  padding: 10px 12px;
  border-radius: 6px;
  background: rgba(245, 158, 11, 0.06);
  border: 1px solid rgba(245, 158, 11, 0.28);
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.rc-how-applied.is-auto {
  background: rgba(22, 163, 74, 0.05);
  border-color: rgba(22, 163, 74, 0.25);
}
.rc-how-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10.5px;
  font-weight: 700;
  color: #b45309;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.rc-how-applied.is-auto .rc-how-label {
  color: #15803d;
}
.rc-how-text {
  font-size: 11.5px;
  color: var(--text-secondary, #64748b);
  line-height: 1.65;
}
.rc-how-text b {
  color: var(--text-primary, #1e293b);
  font-weight: 700;
}
.rc-how-when {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 9px;
  background: rgba(22, 163, 74, 0.15);
  color: #15803d;
  font-weight: 600;
  font-size: 10.5px;
}
.rc-how-note {
  background: rgba(245, 158, 11, 0.18);
  color: #92400e;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
}
.rc-how-caveat {
  display: block;
  margin-top: 4px;
  padding: 5px 9px;
  border-radius: 5px;
  background: rgba(245, 158, 11, 0.12);
  color: #92400e;
  font-size: 11px;
  font-weight: 500;
}

/* ── Actions ── */
.rc-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}
.rc-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: 5px;
  border: 1px solid var(--border-medium, #cbd5e1);
  background: var(--bg-primary, #fff);
  font-size: 11.5px;
  font-weight: 500;
  color: var(--text-secondary, #64748b);
  cursor: pointer;
  transition: all 0.12s;
}
.rc-btn:hover {
  border-color: var(--text-secondary, #64748b);
  color: var(--text-primary, #1e293b);
}
.rc-btn-apply.active {
  background: #15803d;
  border-color: #15803d;
  color: #fff;
}
.rc-btn-skip.active {
  background: #64748b;
  border-color: #64748b;
  color: #fff;
}
.rc-btn-edit.active {
  background: #6d28d9;
  border-color: #6d28d9;
  color: #fff;
}
</style>
