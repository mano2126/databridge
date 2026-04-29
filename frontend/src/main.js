import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router/index.js'
import { loadSupportTiers } from './constants/dbMeta.js'
import './assets/styles/variables.css'
import './assets/styles/global.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)

// 백엔드 SSOT에서 지원 DB tier 동기화 (실패해도 앱은 정상 기동)
loadSupportTiers().catch(() => {})

app.mount('#app')
