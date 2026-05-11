/**
 * conversionStatus.js — DataBridge 변환 상태 도출 유틸 (hotfix_022)
 * ================================================================
 *
 * 본부장님 본질 통찰 (2026-05-11):
 *   "AI 로 성공 된게 빨간 색으로 되 있어서 이걸 성공이라고 해야 되는건지
 *    아니면 재이관을 해야 되는건지도 헛깔려"
 *
 * 처방: item.status('done'/'error') 만으로는 부족. conversion_path 까지 보고
 *       5단계 의미 상태 도출 → 색/라벨/통계 모두 이 기준으로 통일.
 *
 * 5단계 의미 상태 (CONVERSION_STATE):
 *   kb_hit              🟢 KB 즉시 매칭 — 본부장님 KB 자산 진가
 *   ai_learned          🔵 KB 미스 → AI 신규 변환 → KB 등록 (다음에 재사용)
 *   kb_broken_recovered 🟡 KB 깨짐 발견 → AI 복구 (결과 OK, KB 자산 정화 필요)
 *   running             🟦 진행중
 *   pending             ⚪ 대기
 *   failed              🔴 완전 실패 — 본부장님 개입 필요
 *
 * 본부장님 모토 #1 (utils 표준) 정면 충실 — JobMonitor.vue 등 모든 곳에서 import.
 */

// ─── 상태 상수 ───
export const STATE = {
  KB_HIT:               'kb_hit',
  RULE_TVF:             'rule_tvf',         // v95_p107 hotfix_023: TVF Rule Engine 결정적 변환
  AI_LEARNED:           'ai_learned',
  KB_BROKEN_RECOVERED:  'kb_broken_recovered',
  RUNNING:              'running',
  PENDING:              'pending',
  FAILED:               'failed',
  COMPLETED:            'completed',   // path 없는 단순 완료 (rule_ok 등)
}

// ─── 표시 메타데이터 (라벨, 색상 클래스, 설명) ───
export const STATE_META = {
  [STATE.KB_HIT]: {
    label:     'KB 즉시 매칭',
    shortLabel:'KB 매칭',
    cssClass:  'cs-kb-hit',        // CSS 클래스 prefix: cs- (conversionState)
    color:     '#1a7f37',          // 녹색
    bg:        'rgba(26,127,55,.10)',
    border:    'rgba(26,127,55,.25)',
    icon:      '⚡',
    desc:      'KB 자산 즉시 매칭 — AI 호출 0회',
    severity:  0,                  // 좋음
    isSuccess: true,
    needsReview: false,
  },
  [STATE.RULE_TVF]: {
    label:     'Rule Engine',
    shortLabel:'Rule Engine',
    cssClass:  'cs-rule-tvf',
    color:     '#6d28d9',          // 보라색 (특별한 본질 성공)
    bg:        'rgba(109,40,217,.10)',
    border:    'rgba(109,40,217,.25)',
    icon:      '⚙',
    desc:      'TVF Rule Engine 결정적 변환 — AI 호출 0회, 0.05초',
    severity:  0,                  // 가장 좋은 단계
    isSuccess: true,
    needsReview: false,
  },
  [STATE.AI_LEARNED]: {
    label:     'AI 신규 학습',
    shortLabel:'신규 학습',
    cssClass:  'cs-ai-learned',
    color:     '#0969da',          // 파랑
    bg:        'rgba(9,105,218,.10)',
    border:    'rgba(9,105,218,.25)',
    icon:      '📘',
    desc:      'KB 미스 → AI 변환 → KB 등록 (다음 이관 시 재사용)',
    severity:  1,
    isSuccess: true,
    needsReview: false,
  },
  [STATE.KB_BROKEN_RECOVERED]: {
    label:     '재시도 성공',
    shortLabel:'재시도 성공',
    cssClass:  'cs-kb-broken',
    color:     '#9a6700',          // 노랑/주황
    bg:        'rgba(154,103,0,.10)',
    border:    'rgba(154,103,0,.25)',
    icon:      '⚠',
    desc:      'KB 안의 SQL 이 실행 실패 → AI 복구. 결과는 정상, 그러나 KB 자산 정화 필요',
    severity:  2,                  // 주의
    isSuccess: true,
    needsReview: true,             // ⭐ 본부장님 주목 포인트
  },
  [STATE.RUNNING]: {
    label:     '진행중',
    shortLabel:'진행중',
    cssClass:  'cs-running',
    color:     '#1d4ed8',
    bg:        'rgba(59,130,246,.10)',
    border:    'rgba(59,130,246,.25)',
    icon:      '⏳',
    desc:      '이관 진행중',
    severity:  -1,
    isSuccess: false,
    needsReview: false,
  },
  [STATE.PENDING]: {
    label:     '대기',
    shortLabel:'대기',
    cssClass:  'cs-pending',
    color:     '#6e7781',
    bg:        'rgba(110,119,129,.10)',
    border:    'rgba(110,119,129,.20)',
    icon:      '⏸',
    desc:      '아직 시작 안 됨',
    severity:  -2,
    isSuccess: false,
    needsReview: false,
  },
  [STATE.FAILED]: {
    label:     '실패',
    shortLabel:'실패',
    cssClass:  'cs-failed',
    color:     '#cf222e',           // 빨강
    bg:        'rgba(207,34,46,.10)',
    border:    'rgba(207,34,46,.30)',
    icon:      '✕',
    desc:      '이관 실패 — 데이터 미반영, 본부장님 개입 필요',
    severity:  10,                  // 가장 심각
    isSuccess: false,
    needsReview: true,
  },
  [STATE.COMPLETED]: {
    label:     '완료',
    shortLabel:'완료',
    cssClass:  'cs-completed',
    color:     '#15803d',
    bg:        'rgba(22,163,74,.10)',
    border:    'rgba(22,163,74,.20)',
    icon:      '✓',
    desc:      '정상 완료',
    severity:  0,
    isSuccess: true,
    needsReview: false,
  },
}

/**
 * item 의 conversion_path + status 로부터 의미 상태 도출.
 *
 * 입력: item = { status, conversion_path, via_ai_remig, had_error, ... }
 * 출력: STATE 중 하나
 */
export function deriveConversionState(item) {
  if (!item) return STATE.PENDING

  const status = item.status || ''
  const path = Array.isArray(item.conversion_path) ? item.conversion_path : []

  // ─── 분명한 케이스 먼저 ───
  if (status === 'error')   return STATE.FAILED
  if (status === 'running') return STATE.RUNNING
  if (status === 'pending' || status === 'idle' || status === 'waiting')
    return STATE.PENDING

  // status === 'done' / 'completed' 인 경우 — 본질 분류
  if (!path.length) {
    // path 정보 없으면 기존 휴리스틱
    if (item.via_ai_remig) return STATE.AI_LEARNED
    if (item.had_error)    return STATE.KB_BROKEN_RECOVERED
    return STATE.COMPLETED
  }

  const first = path[0]
  const last  = path[path.length - 1]

  // ⭐ v95_p107 hotfix_023: Rule Engine TVF 변환 (가장 본질적 성공)
  //    backend 의 path_marker: "rule_tvf" 또는 conversion_path 에 'rule_tvf' 포함
  if (first === 'rule_tvf' || last === 'rule_tvf' ||
      path.includes('rule_tvf') || path.includes('rule_engine_tvf')) {
    return STATE.RULE_TVF
  }

  // 1) KB 즉시 매칭 (한 단계만, KB-HIT 으로 끝)
  //    예: ["kb_match"] / ["kb_match_first"]
  if (path.length === 1 &&
      (first === 'kb_match' || first === 'kb_match_first')) {
    return STATE.KB_HIT
  }

  // 2) KB 매칭 → 실패 → AI 복구
  //    예: ["kb_match_first","rule_fail","ai_ollama_ok"]
  //        ["kb_match","ai_ollama_fail","ai_ollama_ok"]
  if (first === 'kb_match' || first === 'kb_match_first') {
    // KB 가 첫 단계인데 마지막이 ai_*_ok 면 KB 가 깨졌고 AI 가 복구
    if (last.match(/^ai_.*_ok$/) || last === 'ai_initial') {
      return STATE.KB_BROKEN_RECOVERED
    }
    // KB 후에 fail 만 있고 결국 성공 못 했으면 — status 가 error 였을 텐데 여기 안 옴
    // 안전 fallback
    return STATE.KB_BROKEN_RECOVERED
  }

  // 3) KB 미스 → AI 신규 학습
  //    예: ["kb_miss","ai_ollama_ok"]
  //        ["kb_miss","ai_ollama_ok"]  (단순 신규)
  //        ["ai_initial","ai_ollama_ok"]
  if (first === 'kb_miss' ||
      first === 'ai_initial' ||
      first.startsWith('ai_')) {
    if (last.match(/^ai_.*_ok$/) || last === 'ai_initial') {
      return STATE.AI_LEARNED
    }
  }

  // 4) Rule 만으로 성공
  if (path.length === 1 && first === 'rule_ok') return STATE.COMPLETED

  // 5) 그 외 — 일반 완료로 처리
  return STATE.COMPLETED
}

/**
 * 의미 상태 → 메타데이터 직접 가져오기.
 */
export function getStateMeta(state) {
  return STATE_META[state] || STATE_META[STATE.COMPLETED]
}

/**
 * item → 메타데이터 한 번에.
 */
export function getItemMeta(item) {
  return getStateMeta(deriveConversionState(item))
}

/**
 * 의미 상태 분포 집계 — items 배열 → { kb_hit: N, ai_learned: M, ... }
 */
export function summarizeStates(items) {
  const out = {
    [STATE.KB_HIT]: 0,
    [STATE.RULE_TVF]: 0,
    [STATE.AI_LEARNED]: 0,
    [STATE.KB_BROKEN_RECOVERED]: 0,
    [STATE.RUNNING]: 0,
    [STATE.PENDING]: 0,
    [STATE.FAILED]: 0,
    [STATE.COMPLETED]: 0,
    _total: 0,
    _needsReview: 0,
    _allSuccess: 0,
  }
  for (const it of items || []) {
    const s = deriveConversionState(it)
    out[s] = (out[s] || 0) + 1
    out._total++
    const meta = STATE_META[s]
    if (meta?.needsReview) out._needsReview++
    if (meta?.isSuccess)   out._allSuccess++
  }
  return out
}

/**
 * 상세 라벨 — "KB 매칭 → SQL 1064 → AI(Gemma) 복구" 식의 사람 친화적 흐름 텍스트.
 * tooltip 용. 기존 conversion_path 보다 보기 좋게.
 */
export function describePath(item) {
  const path = item?.conversion_path || []
  if (!path.length) return ''

  const provLabel = {
    anthropic: 'Claude',
    ollama: 'Gemma',
    gemma: 'Gemma',
    claude: 'Claude',
    openai: 'OpenAI',
  }

  const steps = path.map(step => {
    if (step === 'kb_match' || step === 'kb_match_first') return '🟢 KB 즉시 매칭'
    if (step === 'kb_miss')   return '🔵 KB 미스'
    if (step === 'rule_tvf' || step === 'rule_engine_tvf')
                              return '⚙ Rule Engine (TVF 결정적)'
    if (step === 'rule')      return '⚙ Rule 변환'
    if (step === 'rule_ok')   return '⚙ Rule 성공'
    if (step === 'rule_fail') return '⚠ 실행 실패 (1064 등)'
    if (step === 'ai_initial')return '🤖 AI 변환 시작'
    const m = step.match(/^ai_([a-z0-9]+?)(_ok|_fail)?$/)
    if (m) {
      const prov = provLabel[m[1]] || m[1]
      if (m[2] === '_ok')   return `🤖 AI(${prov}) 성공`
      if (m[2] === '_fail') return `🤖 AI(${prov}) 실패`
      return `🤖 AI(${prov})`
    }
    return step
  })
  return steps.join('  →  ')
}

/**
 * 짧은 인라인 라벨 (배지 안에 들어갈 한두 단어).
 */
export function shortBadgeLabel(item) {
  const state = deriveConversionState(item)
  return getStateMeta(state).shortLabel
}
