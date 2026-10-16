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

export function calculateContrastRatio(color1, color2) {
  const l1 = calculateRelativeLuminance(color1)
  const l2 = calculateRelativeLuminance(color2)
  const lighter = Math.max(l1, l2)
  const darker = Math.min(l1, l2)
  return (lighter + 0.05) / (darker + 0.05)
}

export function getContrastTextColor(hexColor) {
  if (!isValidHexColor(hexColor)) return '#ffffff'
  const contrastWithWhite = calculateContrastRatio(hexColor, '#ffffff')
  const contrastWithDark = calculateContrastRatio(hexColor, '#0f172a')

  // If pure white meets WCAG AA (>= 4.5:1) and offers better or equal contrast than dark text, choose white
  if (contrastWithWhite >= 4.5 && contrastWithWhite >= contrastWithDark) {
    return '#ffffff'
  }
  // If modern deep slate text (#0f172a) meets WCAG AA, choose #0f172a
  if (contrastWithDark >= 4.5) {
    return '#0f172a'
  }
  // For edge-case midtones where #0f172a gives 4.2:1-4.49:1, pure black (#000000)
  // mathematically guarantees contrast ratio >= 4.58:1 across the entire spectrum
  const contrastWithBlack = calculateContrastRatio(hexColor, '#000000')
  if (contrastWithBlack >= contrastWithWhite) {
    return '#000000'
  }
  return '#ffffff'
}

export function mixHex(hex1, hex2, weight = 0.5) {
  const c1 = normalizeHexColor(hex1) || '#000000'
  const c2 = normalizeHexColor(hex2) || '#000000'
  const r1 = parseInt(c1.slice(1, 3), 16)
  const g1 = parseInt(c1.slice(3, 5), 16)
  const b1 = parseInt(c1.slice(5, 7), 16)
  const r2 = parseInt(c2.slice(1, 3), 16)
  const g2 = parseInt(c2.slice(3, 5), 16)
  const b2 = parseInt(c2.slice(5, 7), 16)
  const w = Math.max(0, Math.min(1, weight))
  const r = Math.round(r1 * (1 - w) + r2 * w)
  const g = Math.round(g1 * (1 - w) + g2 * w)
  const b = Math.round(b1 * (1 - w) + b2 * w)
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`.toLowerCase()
}

export const PALETTE_SURFACES = Object.freeze({
  'blue-grey': { light: '#ffffff', lightSubtle: '#f1f5f9', dark: '#131b2e', darkSubtle: '#1e293b' },
  'mist': { light: '#ffffff', lightSubtle: '#eaeff4', dark: '#18222a', darkSubtle: '#22303c' },
  'ocean': { light: '#ffffff', lightSubtle: '#e1f3f5', dark: '#10242b', darkSubtle: '#18353f' },
  'amethyst': { light: '#ffffff', lightSubtle: '#f3e8ff', dark: '#1d1433', darkSubtle: '#2b1d4a' },
  'rose': { light: '#ffffff', lightSubtle: '#ffe4e6', dark: '#2c121a', darkSubtle: '#3f1b26' },
  'amber': { light: '#ffffff', lightSubtle: '#fef3c7', dark: '#281a06', darkSubtle: '#3a270b' },
  'forest': { light: '#ffffff', lightSubtle: '#eaf5f0', dark: '#12251e', darkSubtle: '#1c382d' },
  'mocha': { light: '#ffffff', lightSubtle: '#f5eee9', dark: '#241a15', darkSubtle: '#34261f' },
})

export function getAccessibleForeground(hexColor, isDarkTheme = false, palette = DEFAULT_PALETTE) {
  const norm = normalizeHexColor(hexColor)
  if (!norm) return isDarkTheme ? '#f8fafc' : '#0f172a'
  const normPalette = normalizePalettePreference(palette)
  const surfaces = PALETTE_SURFACES[normPalette] || PALETTE_SURFACES['blue-grey']
  const card = isDarkTheme ? surfaces.dark : surfaces.light
  const subtle = isDarkTheme ? surfaces.darkSubtle : surfaces.lightSubtle
  const trans = mixHex(card, norm, isDarkTheme ? 0.16 : 0.14)
  const targetSurfaces = [card, subtle, trans]

  if (targetSurfaces.every(s => calculateContrastRatio(norm, s) >= 4.5)) {
    return norm
  }

  // If contrast is insufficient (e.g. #ffffff on white surface or #000000 on dark surface),
  // progressively adjust luminance while preserving the hue/tone as closely as possible.
  const target = isDarkTheme ? '#ffffff' : (norm === '#ffffff' ? '#0f172a' : '#000000')
  for (let step = 1; step <= 20; step++) {
    const candidate = mixHex(norm, target, step * 0.05)
    if (targetSurfaces.every(s => calculateContrastRatio(candidate, s) >= 4.5)) {
      return candidate
    }
  }
  return isDarkTheme ? '#f8fafc' : '#0f172a'
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

export function applyAccentPreference(root, hexColor, effectiveTheme = 'light', palette = '') {
  const hex = normalizeHexColor(hexColor)
  if (!root?.style) return ''

  if (hex) {
    const isDark = effectiveTheme === 'dark' || root?.getAttribute?.('data-theme') === 'dark'
    const curPalette = palette || root?.getAttribute?.('data-theme-palette') || DEFAULT_PALETTE
    const onPrimary = getContrastTextColor(hex)
    const hoverTarget = hex === '#000000' ? '#ffffff' : '#000000'
    const primaryHover = mixHex(hex, hoverTarget, 0.12)
    const primaryActive = mixHex(hex, hoverTarget, 0.24)
    const onPrimaryHover = getContrastTextColor(primaryHover)
    const onPrimaryActive = getContrastTextColor(primaryActive)
    const primaryFg = getAccessibleForeground(hex, isDark, curPalette)

    root.style.setProperty('--primary', hex)
    root.style.setProperty('--primary-fg', primaryFg)
    root.style.setProperty('--on-primary', onPrimary)
    root.style.setProperty('--on-primary-hover', onPrimaryHover)
    root.style.setProperty('--on-primary-active', onPrimaryActive)
    root.style.setProperty('--primary-hover', primaryHover)
    root.style.setProperty('--primary-active', primaryActive)
    root.style.setProperty('--primary-light', `color-mix(in srgb, ${hex} 14%, transparent)`)
    root.style.setProperty('--primary-border', `color-mix(in srgb, ${primaryFg} 36%, transparent)`)
    return hex
  }

  root.style.removeProperty('--primary')
  root.style.removeProperty('--primary-fg')
  root.style.removeProperty('--on-primary')
  root.style.removeProperty('--on-primary-hover')
  root.style.removeProperty('--on-primary-active')
  root.style.removeProperty('--primary-hover')
  root.style.removeProperty('--primary-active')
  root.style.removeProperty('--primary-light')
  root.style.removeProperty('--primary-border')
  return ''
}

export function applyFullTheme({ root, mode, palette, customAccent, isSystemDark = false }) {
  const effectiveTheme = resolveEffectiveTheme(mode, isSystemDark)
  applyThemePreference(root, effectiveTheme)
  const normPalette = applyPalettePreference(root, palette)
  applyAccentPreference(root, customAccent, effectiveTheme, normPalette)
  return {
    effectiveTheme,
    palette: normPalette,
    customAccent: normalizeHexColor(customAccent) || '',
  }
}
