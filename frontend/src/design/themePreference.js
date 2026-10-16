export const THEME_STORAGE_KEY = 'easyexam-theme'
export const THEME_PALETTE_STORAGE_KEY = 'easyexam-theme-palette'
export const THEME_MODE_STORAGE_KEY = 'easyexam-theme-mode'
export const THEME_ACCENT_STORAGE_KEY = 'easyexam-theme-accent'

export const THEME_PALETTES = Object.freeze([
  'blue-grey',
  'mist',
  'ocean',
  'amethyst',
  'rose',
  'amber',
  'forest',
  'mocha',
])

export const THEME_MODES = Object.freeze(['light', 'dark', 'system'])

export const DEFAULT_PALETTE = 'blue-grey'
export const DEFAULT_MODE = 'light'

export function normalizeThemePreference(value) {
  return value === 'dark' ? 'dark' : 'light'
}

export function normalizeModePreference(value) {
  if (value === 'dark' || value === 'system') return value
  return 'light'
}

export function normalizePalettePreference(value) {
  if (typeof value === 'string' && THEME_PALETTES.includes(value.trim().toLowerCase())) {
    return value.trim().toLowerCase()
  }
  return DEFAULT_PALETTE
}

export function isValidHexColor(value) {
  if (typeof value !== 'string') return false
  const trimmed = value.trim()
  return /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(trimmed)
}

export function normalizeHexColor(value) {
  if (!isValidHexColor(value)) return null
  const hex = value.trim()
  if (hex.length === 4) {
    return `#${hex[1]}${hex[1]}${hex[2]}${hex[2]}${hex[3]}${hex[3]}`.toLowerCase()
  }
  return hex.toLowerCase()
}

export function calculateRelativeLuminance(hexColor) {
  const hex = normalizeHexColor(hexColor)
  if (!hex) return 0.5
  const r = parseInt(hex.slice(1, 3), 16) / 255
  const g = parseInt(hex.slice(3, 5), 16) / 255
  const b = parseInt(hex.slice(5, 7), 16) / 255

  const linear = c => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4))
  return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)
}

export function getContrastTextColor(hexColor) {
  const lum = calculateRelativeLuminance(hexColor)
  return lum > 0.45 ? '#0f172a' : '#ffffff'
}

export function readThemePreference(storage, key = THEME_STORAGE_KEY) {
  try {
    const raw = storage?.getItem(key)
    if (raw) return normalizeThemePreference(raw)
    const mode = storage?.getItem(THEME_MODE_STORAGE_KEY)
    if (mode === 'dark') return 'dark'
    return 'light'
  } catch {
    return 'light'
  }
}

export function writeThemePreference(storage, value, key = THEME_STORAGE_KEY) {
  const theme = normalizeThemePreference(value)
  try {
    storage?.setItem(key, theme)
    storage?.setItem(THEME_MODE_STORAGE_KEY, theme)
  } catch {
    // Keep page usable when storage is disabled.
  }
  return theme
}

export function readPalettePreference(storage, key = THEME_PALETTE_STORAGE_KEY) {
  try {
    return normalizePalettePreference(storage?.getItem(key))
  } catch {
    return DEFAULT_PALETTE
  }
}

export function writePalettePreference(storage, value, key = THEME_PALETTE_STORAGE_KEY) {
  const palette = normalizePalettePreference(value)
  try {
    storage?.setItem(key, palette)
  } catch {}
  return palette
}

export function readModePreference(storage, key = THEME_MODE_STORAGE_KEY) {
  try {
    const rawMode = storage?.getItem(key)
    if (rawMode) return normalizeModePreference(rawMode)
    const legacy = storage?.getItem(THEME_STORAGE_KEY)
    if (legacy === 'dark') return 'dark'
    return DEFAULT_MODE
  } catch {
    return DEFAULT_MODE
  }
}

export function writeModePreference(storage, value, key = THEME_MODE_STORAGE_KEY) {
  const mode = normalizeModePreference(value)
  try {
    storage?.setItem(key, mode)
    if (mode === 'dark' || mode === 'light') {
      storage?.setItem(THEME_STORAGE_KEY, mode)
    }
  } catch {}
  return mode
}

export function readAccentPreference(storage, key = THEME_ACCENT_STORAGE_KEY) {
  try {
    const raw = storage?.getItem(key)
    return isValidHexColor(raw) ? normalizeHexColor(raw) : ''
  } catch {
    return ''
  }
}

export function writeAccentPreference(storage, value, key = THEME_ACCENT_STORAGE_KEY) {
  const hex = normalizeHexColor(value)
  try {
    if (hex) {
      storage?.setItem(key, hex)
    } else {
      storage?.removeItem(key)
    }
  } catch {}
  return hex || ''
}

export function resolveEffectiveTheme(mode, isSystemDark = false) {
  if (mode === 'system') {
    return isSystemDark ? 'dark' : 'light'
  }
  return mode === 'dark' ? 'dark' : 'light'
}

export function applyThemePreference(root, value) {
  const theme = normalizeThemePreference(value)
  root?.setAttribute?.('data-theme', theme)
  if (root?.style) root.style.colorScheme = theme
  return theme
}

export function applyPalettePreference(root, palette) {
  const norm = normalizePalettePreference(palette)
  root?.setAttribute?.('data-theme-palette', norm)
  return norm
}

export function applyAccentPreference(root, hexColor) {
  const hex = normalizeHexColor(hexColor)
  if (!root?.style) return ''

  if (hex) {
    const onPrimary = getContrastTextColor(hex)
    root.style.setProperty('--primary', hex)
    root.style.setProperty('--on-primary', onPrimary)
    root.style.setProperty('--primary-hover', `color-mix(in srgb, ${hex} 86%, ${onPrimary === '#0f172a' ? '#000000' : '#ffffff'})`)
    root.style.setProperty('--primary-active', `color-mix(in srgb, ${hex} 72%, #000000)`)
    root.style.setProperty('--primary-light', `color-mix(in srgb, ${hex} 14%, transparent)`)
    root.style.setProperty('--primary-border', `color-mix(in srgb, ${hex} 36%, transparent)`)
    return hex
  }

  root.style.removeProperty('--primary')
  root.style.removeProperty('--on-primary')
  root.style.removeProperty('--primary-hover')
  root.style.removeProperty('--primary-active')
  root.style.removeProperty('--primary-light')
  root.style.removeProperty('--primary-border')
  return ''
}

export function applyFullTheme({ root, mode, palette, customAccent, isSystemDark = false }) {
  const effectiveTheme = resolveEffectiveTheme(mode, isSystemDark)
  applyThemePreference(root, effectiveTheme)
  applyPalettePreference(root, palette)
  applyAccentPreference(root, customAccent)
  return {
    effectiveTheme,
    palette: normalizePalettePreference(palette),
    customAccent: normalizeHexColor(customAccent) || '',
  }
}
