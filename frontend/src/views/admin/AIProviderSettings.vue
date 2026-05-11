<!--
  AI Provider 관리자 설정 페이지
  ================================
  
  본부장님 결정 (2026-05-10):
    "AI 를 다양하게 선택할 수 있게 관리자 화면에서 구현"
    "올라마보다 더 나은 모델이 있을 수 있으니 그것도 관리자 선택"
    "수행, 재수행 시 쉽게 변경해서 사용 가능하도록"
  
  골격 상태 (2026-05-10):
    - 레이아웃 + 분기 + API 호출 정의
    - Phase 3 (다음 세션) 에서 Provider 별 form + 연결 테스트 구현
-->
<template>
  <div class="ai-provider-settings">
    <h1>🤖 AI Provider 설정</h1>
    <p class="subtitle">
      변환 엔진 Layer 4 의 AI Provider 와 모델을 선택합니다.
      Layer 1 (KB), Layer 2 (Rule), Layer 3 (SQLGlot) 모두 거친 후 fallback 으로 사용됩니다.
    </p>

    <!-- 1. 기본 Provider 설정 -->
    <section class="section">
      <h2>기본 Provider</h2>
      <p class="hint">
        모든 변환에 기본으로 사용되는 Provider 입니다.
        객체 타입별 다른 모델이 필요하면 아래 [객체 타입별 매핑] 섹션 사용.
      </p>

      <div class="form-group">
        <label>Provider</label>
        <select v-model="defaultConfig.provider" @change="onProviderChange">
          <option v-for="(p, id) in providers" :key="id" :value="id">
            {{ p.name }}
            <span v-if="p.air_gapped">(air-gapped 가능)</span>
          </option>
        </select>
      </div>

      <div class="form-group" v-if="currentProviderInfo">
        <label>모델</label>
        <select v-model="defaultConfig.model">
          <option v-for="m in currentProviderInfo.models" :key="m.id" :value="m.id">
            {{ m.label }}
          </option>
          <option v-if="defaultConfig.provider === 'custom'" value="">
            (사용자 정의 — 아래에 직접 입력)
          </option>
        </select>
      </div>

      <!-- Provider 별 추가 설정 -->
      <div v-if="currentProviderInfo">
        <div v-for="key in currentProviderInfo.requires" :key="key" class="form-group">
          <label>{{ formatRequireLabel(key) }}</label>
          <input :type="key === 'api_key' ? 'password' : 'text'"
                 v-model="defaultConfig[key]"
                 :placeholder="placeholderFor(key)" />
        </div>
      </div>

      <div class="actions">
        <button class="btn-test" @click="testConnection">🔌 연결 테스트</button>
        <button class="btn-save" @click="saveDefault">💾 저장</button>
      </div>

      <div v-if="testResult" :class="['test-result', testResult.ok ? 'ok' : 'fail']">
        {{ testResult.message }}
        <span v-if="testResult.elapsed_ms"> ({{ testResult.elapsed_ms }}ms)</span>
      </div>
    </section>

    <!-- 2. 객체 타입별 모델 매핑 (선택) -->
    <section class="section">
      <h2>객체 타입별 모델 매핑 (고급)</h2>
      <p class="hint">
        본부장님 통찰: SP/FN 은 코드 특화 모델 (Qwen Coder), VIEW 는 간단한 모델 (Gemma) 등
        객체 타입에 따라 다른 모델 사용 가능.
      </p>

      <table class="obj-type-table">
        <thead>
          <tr>
            <th>객체 타입</th>
            <th>Provider</th>
            <th>모델</th>
            <th>적용</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="objType in objectTypes" :key="objType">
            <td>{{ objType }}</td>
            <td>
              <select v-model="byObjType[objType].provider">
                <option value="">기본 사용</option>
                <option v-for="(p, id) in providers" :key="id" :value="id">
                  {{ p.name }}
                </option>
              </select>
            </td>
            <td>
              <select v-model="byObjType[objType].model" v-if="byObjType[objType].provider">
                <option v-for="m in providers[byObjType[objType].provider]?.models || []"
                        :key="m.id" :value="m.id">
                  {{ m.label }}
                </option>
              </select>
              <span v-else>—</span>
            </td>
            <td>
              <input type="checkbox" v-model="byObjType[objType].enabled" />
            </td>
          </tr>
        </tbody>
      </table>

      <div class="actions">
        <button class="btn-save" @click="saveByObjType">💾 객체별 매핑 저장</button>
      </div>
    </section>

    <!-- 3. 재실행 시 모델 변경 안내 -->
    <section class="section info-section">
      <h2>💡 재실행 시 모델 변경</h2>
      <p>
        Job 관리 화면에서 [재실행] 클릭 시 — 이 페이지에서 설정한 Provider/모델이 즉시 적용됩니다.
      </p>
      <p>
        모든 변환 결과는 KB 에 모델명과 함께 저장되어,
        <strong>변환 엔진 활용 현황</strong> 페이지에서 모델별 성공률을 비교할 수 있습니다.
      </p>
    </section>
  </div>
</template>

<script>
import axios from 'axios'

export default {
  name: 'AIProviderSettings',
  data() {
    return {
      providers: {},
      defaultConfig: {
        provider: 'anthropic',
        model: '',
        api_key: '',
        ollama_url: 'http://localhost:11434',
        base_url: '',
      },
      byObjType: {
        PROCEDURE: { provider: '', model: '', enabled: false },
        FUNCTION: { provider: '', model: '', enabled: false },
        TRIGGER: { provider: '', model: '', enabled: false },
        VIEW: { provider: '', model: '', enabled: false },
        TABLE: { provider: '', model: '', enabled: false },
      },
      objectTypes: ['PROCEDURE', 'FUNCTION', 'TRIGGER', 'VIEW', 'TABLE'],
      testResult: null,
    }
  },
  computed: {
    currentProviderInfo() {
      return this.providers[this.defaultConfig.provider]
    },
  },
  async mounted() {
    await this.loadProviders()
    await this.loadCurrent()
  },
  methods: {
    async loadProviders() {
      const res = await axios.get('/api/v1/ai-providers/list')
      this.providers = res.data.providers
    },
    async loadCurrent() {
      const res = await axios.get('/api/v1/ai-providers/current')
      Object.assign(this.defaultConfig, res.data.default || {})
      // by_obj_type 도 로드
      for (const [k, v] of Object.entries(res.data.by_obj_type || {})) {
        if (this.byObjType[k]) {
          Object.assign(this.byObjType[k], v, { enabled: true })
        }
      }
    },
    onProviderChange() {
      // Provider 변경 시 첫 모델 자동 선택
      const info = this.providers[this.defaultConfig.provider]
      if (info?.models?.length) {
        this.defaultConfig.model = info.models[0].id
      }
      this.testResult = null
    },
    formatRequireLabel(key) {
      const map = {
        api_key: 'API Key',
        ollama_url: 'Ollama URL',
        base_url: 'Base URL',
        model: 'Model 이름',
      }
      return map[key] || key
    },
    placeholderFor(key) {
      const map = {
        api_key: 'sk-ant-api03-... 또는 sk-...',
        ollama_url: 'http://localhost:11434',
        base_url: 'https://your-endpoint/v1',
        model: 'gpt-4 또는 사용자 모델명',
      }
      return map[key] || ''
    },
    async testConnection() {
      this.testResult = { ok: false, message: '테스트 중...' }
      try {
        const res = await axios.post('/api/v1/ai-providers/test-connection', {
          provider: this.defaultConfig.provider,
          config: this.defaultConfig,
        })
        this.testResult = res.data.ok
          ? { ok: true, message: '✅ 연결 성공', elapsed_ms: res.data.elapsed_ms }
          : { ok: false, message: '❌ 연결 실패: ' + (res.data.error || '알 수 없음') }
      } catch (e) {
        this.testResult = { ok: false, message: '❌ ' + e.message }
      }
    },
    async saveDefault() {
      try {
        await axios.post('/api/v1/ai-providers/set-default', this.defaultConfig)
        alert('기본 Provider 저장 완료')
      } catch (e) {
        alert('저장 실패: ' + e.message)
      }
    },
    async saveByObjType() {
      const payload = {}
      for (const [k, v] of Object.entries(this.byObjType)) {
        if (v.enabled && v.provider && v.model) {
          payload[k] = { provider: v.provider, model: v.model }
        }
      }
      try {
        await axios.post('/api/v1/ai-providers/set-by-obj-type', payload)
        alert('객체별 매핑 저장 완료')
      } catch (e) {
        alert('저장 실패: ' + e.message)
      }
    },
  },
}
</script>

<style scoped>
.ai-provider-settings { padding: 24px; max-width: 900px; margin: 0 auto; }
h1 { font-size: 26px; margin-bottom: 8px; }
.subtitle { color: #666; margin-bottom: 24px; line-height: 1.5; }

.section {
  background: #fff;
  border: 1px solid #d0d7de;
  border-radius: 8px;
  padding: 24px;
  margin-bottom: 20px;
}
.section h2 { font-size: 18px; margin-bottom: 12px; }
.hint { color: #666; font-size: 13px; margin-bottom: 16px; line-height: 1.5; }

.form-group { margin-bottom: 14px; }
.form-group label {
  display: block;
  font-weight: 500;
  margin-bottom: 6px;
  font-size: 13px;
}
.form-group select,
.form-group input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d0d7de;
  border-radius: 6px;
  font-size: 14px;
}

.actions { display: flex; gap: 8px; margin-top: 16px; }
.btn-test, .btn-save {
  padding: 8px 18px;
  border: 1px solid #d0d7de;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}
.btn-save { background: #0969da; color: #fff; border-color: #0969da; }
.btn-test { background: #fff; }

.test-result {
  margin-top: 12px;
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 14px;
}
.test-result.ok { background: #dafbe1; color: #1a7f37; }
.test-result.fail { background: #ffeef0; color: #cf222e; }

.obj-type-table {
  width: 100%;
  border-collapse: collapse;
}
.obj-type-table th, .obj-type-table td {
  padding: 10px;
  border-bottom: 1px solid #e1e4e8;
  text-align: left;
  font-size: 13px;
}
.obj-type-table th { background: #f6f8fa; }
.obj-type-table select { width: 100%; padding: 6px; }

.info-section { background: #ddf4ff; border-color: #0969da; }
.info-section p { margin-bottom: 8px; line-height: 1.6; }
</style>
