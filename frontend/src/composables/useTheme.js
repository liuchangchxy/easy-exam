import { ref } from 'vue'
import {
  DEFAULT_MODE,
  DEFAULT_PALETTE,
  THEME_PALETTES,
  applyFullTheme,
  applyThemePreference,
  readAccentPreference,
  readModePreference,
  readPalettePreference,
  readThemePreference,
  resolveEffectiveTheme,
  writeAccentPreference,
  writeModePreference,
  writePalettePreference,
  writeThemePreference,
} from '../design/themePreference.js'

const theme = ref('light')
const mode = ref(DEFAULT_MODE)
const palette = ref(DEFAULT_PALETTE)
const customAccent = ref('')
let initialized = false
let mediaListenerAttached = false

function browserStorage() {
  try {
    return globalThis.localStorage
  } catch {
    return null
  }
}

function getSystemDark() {
  try {
    return Boolean(globalThis.matchMedia?.('(prefers-color-scheme: dark)')?.matches)
  } catch {
    return false
  }
}

function syncRoot() {
  const root = globalThis.document?.documentElement
  if (!root) return
  const effectiveTheme = resolveEffectiveTheme(mode.value, getSystemDark())
  theme.value = effectiveTheme
  applyFullTheme({
    root,
    mode: mode.value,
    palette: palette.value,
    customAccent: customAccent.value,
    isSystemDark: getSystemDark(),
  })
}

function setupMediaListener() {
  if (mediaListenerAttached || typeof globalThis.matchMedia !== 'function') return
  try {
    const mq = globalThis.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => {
      if (mode.value === 'system') {
        syncRoot()
      }
    }
    if (mq.addEventListener) {
      mq.addEventListener('change', handler)
    } else if (mq.addListener) {
      mq.addListener(handler)
    }
    mediaListenerAttached = true
  } catch {}
}

export function initializeTheme() {
  if (initialized) {
    syncRoot()
    return theme.value
  }

  const storage = browserStorage()
  mode.value = readModePreference(storage)
  palette.value = readPalettePreference(storage)
  customAccent.value = readAccentPreference(storage)

  syncRoot()
  setupMediaListener()
  initialized = true
  return theme.value
}

function setTheme(value) {
  // Support both mode ('light'|'dark'|'system') and legacy direct toggle ('light'|'dark')
  const storage = browserStorage()
  if (value === 'system') {
    mode.value = 'system'
    writeModePreference(storage, 'system')
  } else {
    const next = value === 'dark' ? 'dark' : 'light'
    mode.value = next
    writeModePreference(storage, next)
    writeThemePreference(storage, next)
  }
  syncRoot()
  return theme.value
}

function setPalette(value) {
  const storage = browserStorage()
  const next = writePalettePreference(storage, value)
  palette.value = next
  syncRoot()
  return next
}

function setCustomAccent(hex) {
  const storage = browserStorage()
  const next = writeAccentPreference(storage, hex)
  customAccent.value = next
  syncRoot()
  return next
}

function resetCustomAccent() {
  return setCustomAccent('')
}

function toggleTheme() {
  // If in system mode, toggle to opposite of currently resolved theme
  const current = theme.value
  const target = current === 'dark' ? 'light' : 'dark'
  return setTheme(target)
}

export function useTheme() {
  initializeTheme()
  return {
    theme,
    mode,
    palette,
    customAccent,
    palettes: THEME_PALETTES,
    setTheme,
    setMode: setTheme,
    setPalette,
    setCustomAccent,
    resetCustomAccent,
    toggleTheme,
  }
}
