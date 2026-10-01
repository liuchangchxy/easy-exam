import { ref } from 'vue'
import {
  applyThemePreference,
  readThemePreference,
  writeThemePreference,
} from '../design/themePreference.js'

const theme = ref('light')
let initialized = false

function browserStorage() {
  try {
    return globalThis.localStorage
  } catch {
    return null
  }
}

function initializeTheme() {
  if (initialized) return theme.value
  theme.value = readThemePreference(browserStorage())
  applyThemePreference(globalThis.document?.documentElement, theme.value)
  initialized = true
  return theme.value
}

function setTheme(value) {
  const next = writeThemePreference(browserStorage(), value)
  theme.value = next
  applyThemePreference(globalThis.document?.documentElement, next)
  initialized = true
  return next
}

function toggleTheme() {
  return setTheme(theme.value === 'light' ? 'dark' : 'light')
}

export function useTheme() {
  initializeTheme()
  return { theme, setTheme, toggleTheme }
}
