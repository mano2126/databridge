<template>
  <div class="license-page">
    <div class="page-header">
      <div>
        <h2>라이선스 관리</h2>
        <p class="muted">현재 edition 확인 및 라이선스 파일 교체. admin 전용.</p>
      </div>
      <button class="btn-ghost" @click="load">새로고침</button>
    </div>

    <div v-if="loading" class="loading">불러오는 중...</div>

    <div v-else-if="lic">
      <!-- 현재 라이선스 카드 -->
      <div class="lic-card" :class="'edition-' + lic.edition">
        <div class="lic-header">
          <div>
            <div class="lic-edition">{{ lic.edition.toUpperCase() }}</div>
            <div class="lic-customer">{{ lic.customer }}</div>
          </div>
          <div class="lic-status">
            <span v-if="lic.expired" class="badge-danger">만료됨</span>
            <span v-else-if="lic.warning" class="badge-warn">경고</span>
            <span v-else class="badge-ok">활성</span>
          </div>
        </div>

        <div v-if="lic.warning" class="warning">⚠ {{ lic.warning }}</div>

        <div class="lic-grid">
          <div>
            <div class="lbl">라이선스 ID</div>
            <div class="val">{{ lic.license_id || '—' }}</div>
          </div>
          <div>
            <div class="lbl">발급일</div>
            <div class="val">{{ lic.issued_at || '—' }}</div>
          </div>
          <div>
            <div class="lbl">만료일</div>
            <div class="val">
              {{ lic.expires_at || '무제한' }}
              <span v-if="lic.days_remaining != null" class="days-left"
                    :class="{ 'danger': lic.days_remaining <= 7, 'warn': lic.days_remaining <= 30 }">
                ({{ lic.days_remaining > 0 ? `${lic.days_remaining}일 남음` : '만료됨' }})
              </span>
            </div>
          </div>
          <div>
            <div class="lbl">서명 검증</div>
            <div class="val">
              <span v-if="lic.valid" class="badge-ok-sm">✓ 유효</span>
              <span v-else class="badge-danger-sm">✗ 실패</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 기능 매트릭스 -->
      <h3 class="section-title">활성 기능</h3>
      <div class="feature-grid">
        <div class="feature-card">
          <div class="feat-label">동시 실행 Job 수</div>
          <div class="feat-value">{{ fmt(lic.features.max_concurrent_jobs) }}</div>
        </div>
        <div class="feature-card">
          <div class="feat-label">테이블 최대 크기</div>
          <div class="feat-value">{{ lic.features.max_table_size_gb == null ? '무제한' : lic.features.max_table_size_gb + ' GB' }}</div>
        </div>
        <div class="feature-card">
          <div class="feat-label">감사 로그 보관</div>
          <div class="feat-value">{{ lic.features.audit_retention_days }} 일</div>
        </div>
        <div class="feature-card" :class="{ disabled: !lic.features.tier2_tier3_dbs }">
          <div class="feat-label">Tier 2/3 DB 접근</div>
          <div class="feat-value">{{ lic.features.tier2_tier3_dbs ? '허용' : '비허용' }}</div>
        </div>
        <div class="feature-card" :class="{ disabled: !lic.features.custom_sql_rules }">
          <div class="feat-label">커스텀 SQL 규칙</div>
          <div class="feat-value">{{ lic.features.custom_sql_rules ? '허용' : '비허용' }}</div>
        </div>
        <div class="feature-card" :class="{ disabled: !lic.features.websocket_monitor }">
          <div class="feat-label">실시간 모니터</div>
          <div class="feat-value">{{ lic.features.websocket_monitor ? '허용' : '비허용' }}</div>
        </div>
      </div>

      <!-- 라이선스 교체 -->
      <h3 class="section-title">라이선스 교체</h3>
      <div class="upload-box">
        <p class="muted">
          새 라이선스 파일(.key)을 업로드하거나 JSON을 직접 붙여넣으세요.
          업로드 즉시 서명 검증 후 적용됩니다.
        </p>

        <div class="upload-options">
          <label class="file-input">
            <input type="file" accept=".key,.json,.txt" @change="onFileSelect"/>
            <span>파일 선택</span>
          </label>
          <span class="muted or">또는</span>
        </div>

        <textarea v-model="licenseText" placeholder='{"payload": {...}, "signature": "..."}'
                  rows="8"></textarea>

        <div v-if="uploadMsg" :class="uploadOk ? 'succ' : 'err'">{{ uploadMsg }}</div>

        <div class="upload-actions">
          <button class="btn-ghost" @click="onReload">파일 재로드</button>
          <button class="btn-primary" @click="onUpload" :disabled="!licenseText.trim() || uploading">
            {{ uploading ? '업로드 중...' : '업로드 및 검증' }}
          </button>
        </div>
      </div>

      <!-- 도움말 -->
      <div class="help">
        <h4>라이선스 파일 위치 우선순위</h4>
        <ol>
          <li>환경변수 <code>DATABRIDGE_LICENSE_PATH</code></li>
          <li>프로젝트 루트 <code>license.key</code></li>
          <li>backend 디렉토리 <code>license.key</code></li>
          <li>backend/data/<code>license.key</code></li>
        </ol>
        <p class="muted">
          라이선스가 없으면 community 모드로 동작합니다 (동시 1개 Job, Tier 1 DB만 지원).
          판매사에 연락하여 라이선스를 발급받으세요.
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const lic = ref(null)
const loading = ref(false)
const licenseText = ref('')
const uploading = ref(false)
const uploadMsg = ref('')
const uploadOk = ref(false)

async function apiGet(path) {
  const token = localStorage.getItem('databridge_auth_token') || ''
  const r = await fetch(`/api/v1${path}`, { headers: { 'X-Auth-Token': token } })
  if (!r.ok) throw new Error(String(r.status))
  return r.json()
}

async function apiPost(path, body, asJson = true) {
  const token = localStorage.getItem('databridge_auth_token') || ''
  const headers = { 'X-Auth-Token': token }
  if (asJson) headers['Content-Type'] = 'application/json'
  const r = await fetch(`/api/v1${path}`, {
    method: 'POST', headers,
    body: typeof body === 'string' ? body : JSON.stringify(body),
  })
  const txt = await r.text()
  if (!r.ok) throw new Error(txt || String(r.status))
  return txt ? JSON.parse(txt) : {}
}

async function load() {
  loading.value = true
  try {
    lic.value = await apiGet('/license/')
  } catch (e) {
    console.error(e)
  } finally { loading.value = false }
}

function onFileSelect(ev) {
  const file = ev.target.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    licenseText.value = String(reader.result || '')
  }
  reader.readAsText(file)
}

async function onUpload() {
  uploading.value = true
  uploadMsg.value = ''
  try {
    // JSON 유효성 선제 확인
    JSON.parse(licenseText.value)
    const r = await apiPost('/license/upload', licenseText.value, true)
    lic.value = r
    uploadOk.value = true
    uploadMsg.value = `✓ 라이선스 적용 완료 — ${r.edition} (${r.customer})`
    licenseText.value = ''
  } catch (e) {
    uploadOk.value = false
    const msg = e.message || '업로드 실패'
    try {
      const parsed = JSON.parse(msg)
      uploadMsg.value = parsed.detail || msg
    } catch {
      uploadMsg.value = msg.length > 300 ? msg.substring(0, 300) + '...' : msg
    }
  } finally { uploading.value = false }
}

async function onReload() {
  try {
    const r = await apiPost('/license/reload', {})
    lic.value = r
    uploadOk.value = true
    uploadMsg.value = `✓ 라이선스 재로드 — ${r.edition}`
  } catch (e) {
    uploadOk.value = false
    uploadMsg.value = '재로드 실패'
  }
}

function fmt(v) {
  if (v == null) return '무제한'
  return String(v)
}

onMounted(load)
</script>

<style scoped>
.license-page { padding: 24px; max-width: 1000px; }
.page-header {
  display: flex; justify-content: space-between; align-items: flex-end;
  margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid #e5e7eb;
}
.page-header h2 { margin: 0; color: #1f2937; }
.muted { color: #6b7280; font-size: 13px; margin: 4px 0 0; }
.loading { padding: 40px; text-align: center; color: #6b7280; }

.lic-card {
  background: #fff; border: 1px solid #e5e7eb; border-left-width: 4px;
  border-radius: 8px; padding: 24px; margin-bottom: 24px;
}
.lic-card.edition-community  { border-left-color: #6b7280; }
.lic-card.edition-standard   { border-left-color: #3b82f6; }
.lic-card.edition-enterprise { border-left-color: #8b5cf6; background: linear-gradient(to right, #fff, #faf5ff); }

.lic-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.lic-edition { font-size: 22px; font-weight: 700; color: #1f2937; letter-spacing: .5px; }
.lic-customer { font-size: 14px; color: #6b7280; margin-top: 4px; }

.lic-grid {
  display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px 24px;
  margin-top: 16px; padding-top: 16px; border-top: 1px solid #f3f4f6;
}
.lbl { font-size: 11px; color: #9ca3af; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 4px; }
.val { font-size: 14px; color: #1f2937; font-weight: 500; }
.days-left { font-size: 12px; color: #6b7280; margin-left: 6px; }
.days-left.warn   { color: #d97706; }
.days-left.danger { color: #dc2626; font-weight: 600; }

.warning { background: #fef3c7; color: #92400e; padding: 8px 12px; border-radius: 4px; font-size: 13px; margin-bottom: 12px; }

.badge-ok     { background: #dcfce7; color: #166534; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: 600; }
.badge-warn   { background: #fef3c7; color: #92400e; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: 600; }
.badge-danger { background: #fee2e2; color: #991b1b; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: 600; }
.badge-ok-sm     { background: #dcfce7; color: #166534; padding: 2px 8px; border-radius: 3px; font-size: 11px; }
.badge-danger-sm { background: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 3px; font-size: 11px; }

.section-title { margin: 32px 0 16px; font-size: 16px; color: #1f2937; }

.feature-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 24px;
}
.feature-card {
  background: #fff; border: 1px solid #e5e7eb; padding: 14px; border-radius: 6px;
}
.feature-card.disabled { opacity: 0.4; background: #fafafa; }
.feat-label { font-size: 11px; color: #6b7280; margin-bottom: 6px; }
.feat-value { font-size: 16px; font-weight: 600; color: #1f2937; }

.upload-box {
  background: #f9fafb; padding: 20px; border-radius: 8px; border: 1px solid #e5e7eb;
}
.upload-options { display: flex; align-items: center; gap: 12px; margin: 12px 0; }
.file-input {
  display: inline-block; padding: 6px 14px; background: #fff;
  border: 1px solid #d1d5db; border-radius: 4px; cursor: pointer; font-size: 13px;
}
.file-input input { display: none; }
.file-input:hover { background: #f3f4f6; }
.or { font-size: 12px; }

textarea {
  width: 100%; padding: 10px; font-family: monospace; font-size: 12px;
  border: 1px solid #d1d5db; border-radius: 4px; resize: vertical;
  box-sizing: border-box;
}

.succ { background: #dcfce7; color: #166534; padding: 8px 12px; border-radius: 4px; font-size: 13px; margin-top: 12px; }
.err  { background: #fee2e2; color: #991b1b; padding: 8px 12px; border-radius: 4px; font-size: 13px; margin-top: 12px; }

.upload-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }

.btn-primary { background: #1f6feb; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-primary:hover:not(:disabled) { background: #1a5fcc; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-ghost { background: #fff; color: #6b7280; border: 1px solid #d1d5db; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-ghost:hover { background: #f3f4f6; }

.help {
  margin-top: 32px; padding: 16px; background: #f9fafb; border-radius: 6px;
  border-left: 3px solid #60a5fa;
}
.help h4 { margin: 0 0 8px; color: #1f2937; font-size: 14px; }
.help ol { margin: 0 0 12px; padding-left: 20px; font-size: 13px; color: #374151; }
.help li { margin-bottom: 4px; }
.help code { background: #e5e7eb; padding: 1px 6px; border-radius: 3px; font-size: 12px; }
</style>
