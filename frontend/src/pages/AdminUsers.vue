<template>
  <div class="admin-users">
    <div class="page-header">
      <div>
        <h2>사용자 관리</h2>
        <p class="muted">계정과 역할을 관리합니다. admin 권한이 필요합니다.</p>
      </div>
      <button class="btn-primary" @click="openCreateDialog">+ 새 사용자</button>
    </div>

    <div v-if="loading" class="loading">불러오는 중...</div>

    <table v-else class="user-table">
      <thead>
        <tr>
          <th>사용자명</th>
          <th>역할</th>
          <th>상태</th>
          <th>마지막 로그인</th>
          <th>생성일</th>
          <th class="right">작업</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in users" :key="u.username" :class="{ disabled: u.disabled }">
          <td><code>{{ u.username }}</code></td>
          <td>
            <select v-model="u._newRole" @change="onRoleChange(u)" :disabled="u.username === me?.username">
              <option value="admin">admin</option>
              <option value="operator">operator</option>
              <option value="viewer">viewer</option>
            </select>
          </td>
          <td>
            <span v-if="u.disabled" class="badge-muted">비활성</span>
            <span v-else class="badge-ok">활성</span>
          </td>
          <td class="small">{{ u.last_login ? fmt(u.last_login) : '—' }}</td>
          <td class="small">{{ fmt(u.created_at) }}</td>
          <td class="right">
            <button class="btn-sm" @click="openResetDialog(u)">비번 리셋</button>
            <button v-if="!u.disabled" class="btn-sm" @click="toggleDisabled(u, true)"
                    :disabled="u.username === me?.username">비활성화</button>
            <button v-else class="btn-sm" @click="toggleDisabled(u, false)">활성화</button>
            <button class="btn-sm-danger" @click="deleteUser(u)"
                    :disabled="u.username === me?.username">삭제</button>
          </td>
        </tr>
        <tr v-if="!users.length">
          <td colspan="6" class="empty">등록된 사용자가 없습니다.</td>
        </tr>
      </tbody>
    </table>

    <!-- 신규 사용자 다이얼로그 -->
    <div v-if="showCreate" class="modal-backdrop" @click.self="showCreate=false">
      <div class="modal">
        <h3>신규 사용자</h3>
        <label>사용자명<input v-model="form.username" autofocus/></label>
        <label>비밀번호<input v-model="form.password" type="password"/></label>
        <label>역할
          <select v-model="form.role">
            <option value="viewer">viewer — 조회만</option>
            <option value="operator">operator — 이관 실행/편집</option>
            <option value="admin">admin — 전체 권한</option>
          </select>
        </label>
        <div v-if="formErr" class="err">{{ formErr }}</div>
        <div class="modal-actions">
          <button class="btn-ghost" @click="showCreate=false">취소</button>
          <button class="btn-primary" @click="submitCreate" :disabled="submitting">
            {{ submitting ? '생성 중...' : '생성' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 비번 리셋 다이얼로그 -->
    <div v-if="showReset" class="modal-backdrop" @click.self="showReset=false">
      <div class="modal">
        <h3>비밀번호 리셋 — {{ resetUser?.username }}</h3>
        <p class="muted">리셋하면 해당 사용자의 모든 세션이 즉시 무효화됩니다.</p>
        <label>새 비밀번호<input v-model="resetForm.newPw" type="password" autofocus/></label>
        <div v-if="resetErr" class="err">{{ resetErr }}</div>
        <div class="modal-actions">
          <button class="btn-ghost" @click="showReset=false">취소</button>
          <button class="btn-primary" @click="submitReset" :disabled="submitting">
            {{ submitting ? '리셋 중...' : '리셋' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { authApi } from '@/api/index.js'
import { useAuthStore } from '@/store/authStore.js'

const auth  = useAuthStore()
const me    = computed(() => auth.user)
const users = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const list = await authApi.listUsers()
    list.forEach(u => u._newRole = u.role)
    users.value = list
  } catch (e) {
    // 인터셉터에서 토스트 처리됨
  } finally { loading.value = false }
}

// ── 신규 사용자 ─────────────────────────────────────
const showCreate = ref(false)
const form = ref({ username:'', password:'', role:'viewer' })
const formErr = ref('')
const submitting = ref(false)

function openCreateDialog() {
  form.value = { username:'', password:'', role:'viewer' }
  formErr.value = ''
  showCreate.value = true
}
async function submitCreate() {
  if (!form.value.username || !form.value.password) {
    formErr.value = '사용자명과 비밀번호는 필수'
    return
  }
  if (form.value.password.length < 8) {
    formErr.value = '비밀번호는 8자 이상'
    return
  }
  submitting.value = true
  try {
    await authApi.createUser(form.value)
    showCreate.value = false
    await load()
  } catch (e) {
    formErr.value = e.response?.data?.detail || '생성 실패'
  } finally { submitting.value = false }
}

// ── 역할 변경 ──────────────────────────────────────
async function onRoleChange(u) {
  if (u._newRole === u.role) return
  if (!confirm(`${u.username} 의 역할을 ${u.role} → ${u._newRole} 로 변경합니다.`)) {
    u._newRole = u.role
    return
  }
  try {
    await authApi.updateUser(u.username, { role: u._newRole })
    await load()
  } catch {
    u._newRole = u.role
  }
}

// ── 활성/비활성 ─────────────────────────────────────
async function toggleDisabled(u, disable) {
  const label = disable ? '비활성화' : '활성화'
  if (!confirm(`${u.username} 을(를) ${label} 하시겠습니까?`)) return
  try {
    await authApi.updateUser(u.username, { disabled: disable })
    await load()
  } catch {}
}

// ── 삭제 ───────────────────────────────────────────
async function deleteUser(u) {
  if (!confirm(`${u.username} 을(를) 영구 삭제합니다. 되돌릴 수 없습니다. 계속하시겠습니까?`)) return
  try {
    await authApi.deleteUser(u.username)
    await load()
  } catch {}
}

// ── 비번 리셋 ──────────────────────────────────────
const showReset = ref(false)
const resetUser = ref(null)
const resetForm = ref({ newPw:'' })
const resetErr  = ref('')

function openResetDialog(u) {
  resetUser.value = u
  resetForm.value = { newPw:'' }
  resetErr.value = ''
  showReset.value = true
}
async function submitReset() {
  if (resetForm.value.newPw.length < 8) {
    resetErr.value = '비밀번호는 8자 이상'
    return
  }
  submitting.value = true
  try {
    await authApi.resetPassword(resetUser.value.username, { new_password: resetForm.value.newPw })
    showReset.value = false
    alert(`${resetUser.value.username} 비번이 리셋됐습니다. 해당 사용자는 재로그인이 필요합니다.`)
  } catch (e) {
    resetErr.value = e.response?.data?.detail || '리셋 실패'
  } finally { submitting.value = false }
}

function fmt(iso) {
  if (!iso) return ''
  return iso.substring(0, 19).replace('T', ' ')
}

onMounted(load)
</script>

<style scoped>
.admin-users { padding: 24px; }
.page-header {
  display: flex; justify-content: space-between; align-items: flex-end;
  margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid #e5e7eb;
}
.page-header h2 { margin: 0; color: #1f2937; }
.muted { color: #6b7280; font-size: 13px; margin: 4px 0 0; }

.loading { padding: 40px; text-align: center; color: #6b7280; }

.user-table { width: 100%; border-collapse: collapse; font-size: 14px; background: #fff; }
.user-table th, .user-table td {
  padding: 10px 12px; text-align: left; border-bottom: 1px solid #f3f4f6;
}
.user-table th { background: #f9fafb; font-weight: 600; color: #374151; font-size: 13px; }
.user-table tr.disabled { opacity: 0.55; background: #fafafa; }
.user-table .right { text-align: right; }
.user-table .small { color: #6b7280; font-size: 12px; }
.empty { text-align: center; padding: 40px; color: #9ca3af; }

.badge-ok    { display:inline-block; padding: 2px 8px; border-radius: 4px; background: #dcfce7; color: #166534; font-size:12px; font-weight: 600; }
.badge-muted { display:inline-block; padding: 2px 8px; border-radius: 4px; background: #f3f4f6; color: #6b7280; font-size:12px; }

code { background: #f3f4f6; padding: 2px 6px; border-radius: 3px; font-size: 13px; }
select { padding: 4px 8px; border: 1px solid #d1d5db; border-radius: 4px; font-size: 13px; }

.btn-primary {
  background: #1f6feb; color: #fff; border: none; padding: 8px 16px;
  border-radius: 6px; font-size: 14px; cursor: pointer;
}
.btn-primary:hover:not(:disabled) { background: #1a5fcc; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-ghost { background: transparent; color: #6b7280; border: 1px solid #d1d5db; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
.btn-sm { padding: 4px 8px; font-size: 12px; border: 1px solid #d1d5db; background: #fff; border-radius: 4px; cursor: pointer; margin-left: 4px; }
.btn-sm:hover:not(:disabled) { background: #f3f4f6; }
.btn-sm:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-sm-danger { padding: 4px 8px; font-size: 12px; background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; border-radius: 4px; cursor: pointer; margin-left: 4px; }
.btn-sm-danger:hover:not(:disabled) { background: #fecaca; }
.btn-sm-danger:disabled { opacity: 0.5; cursor: not-allowed; }

.modal-backdrop {
  position: fixed; inset: 0; background: rgba(0,0,0,.5);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.modal {
  background: #fff; padding: 28px; border-radius: 12px; width: 400px;
  box-shadow: 0 20px 60px rgba(0,0,0,.25);
}
.modal h3 { margin: 0 0 16px; color: #1f2937; }
.modal label { display: block; margin-bottom: 12px; font-size: 13px; color: #374151; }
.modal input, .modal select {
  width: 100%; padding: 8px 10px; margin-top: 4px;
  border: 1px solid #d1d5db; border-radius: 4px; font-size: 14px;
  box-sizing: border-box;
}
.modal .err { background: #fef2f2; color: #991b1b; padding: 8px 12px; border-radius: 4px; font-size: 13px; margin-top: 12px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }
</style>
