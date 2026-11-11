import { createApp } from 'vue'
import App from './App.vue'
import './style.css'
import router from './router/index.js'
import { initializeLocale } from './composables/useLocale.js'
import { initializeTheme } from './composables/useTheme.js'

// Mirrors the preference owned by SettingsView: it persists 'dense' or
// 'balanced' under `easyexam-density` and renders it as `data-density` on the
// document root. Restoring it at boot keeps the saved density on every route,
// not only on the settings page that writes it.
const DENSITY_STORAGE_KEY = 'easyexam-density'

export function normalizeDensityPreference(value) {
  return value === 'dense' ? 'dense' : 'balanced'
}

export function restoreDensityPreference(root = globalThis.document?.documentElement) {
  let saved = ''
  try {
    saved = globalThis.localStorage?.getItem(DENSITY_STORAGE_KEY) || ''
  } catch {
    saved = ''
  }
  const density = normalizeDensityPreference(saved)
  if (root) root.setAttribute('data-density', density)
  return density
}

initializeLocale()
initializeTheme()
restoreDensityPreference()

const app = createApp(App)
app.use(router)
app.mount('#app')
