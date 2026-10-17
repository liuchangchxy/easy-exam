import { createApp } from 'vue'
import App from './App.vue'
import './style.css'
import router from './router/index.js'
import { initializeLocale } from './composables/useLocale.js'
import { initializeTheme } from './composables/useTheme.js'

initializeLocale()
initializeTheme()

const app = createApp(App)
app.use(router)
app.mount('#app')
