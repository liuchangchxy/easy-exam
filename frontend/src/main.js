import { createApp } from 'vue'
import App from './App.vue'
import './style.css'
import { initializeLocale } from './composables/useLocale.js'

initializeLocale()

const app = createApp(App)
app.mount('#app')
