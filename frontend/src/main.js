import { createApp } from 'vue'
import App from './App.vue'
import './style.css'
import router from './router/index.js'
import { initializeLocale } from './composables/useLocale.js'
import { initializeTheme } from './composables/useTheme.js'
import {
  DENSITY_STORAGE_KEY,
  normalizeDensityPreference,
  readDensityPreference,
  restoreDensityPreference,
} from './composables/density.js'

// Restore the saved density before mounting so every route starts in the
// preference owned by SettingsView.
export { DENSITY_STORAGE_KEY, normalizeDensityPreference, readDensityPreference, restoreDensityPreference }

initializeLocale()
initializeTheme()
restoreDensityPreference()

const app = createApp(App)
app.use(router)
app.mount('#app')
