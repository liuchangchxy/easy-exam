export const THEME_STORAGE_KEY = 'easyexam-theme'
export const THEME_PALETTE_STORAGE_KEY = 'easyexam-theme-palette'
export const THEME_MODE_STORAGE_KEY = 'easyexam-theme-mode'
export const THEME_ACCENT_STORAGE_KEY = 'easyexam-theme-accent'

/**
 * Canonical palette families. A family supplies one semantic token contract;
 * `mode` (light/dark/system) selects the light or dark value set inside it.
 * Keeping the palette and the mode in separate preferences is what lets a user
 * change "Gruvbox + dark" to "Catppuccin + dark" without touching the mode.
 */
export const THEME_PALETTES = Object.freeze([
  'editorial',
  'gruvbox',
  'everforest',
  'catppuccin',
])

export const PALETTE_LABELS = Object.freeze({
  editorial: 'Editorial',
  gruvbox: 'Gruvbox',
  everforest: 'Everforest',
  catppuccin: 'Catppuccin',
})

/**
 * Palette ids persisted by the pre-PR-90 multi-theme system. They are still
 * accepted and resolved to the nearest current family so an existing user
 * configuration keeps working after the upgrade instead of silently resetting.
 */
export const LEGACY_PALETTE_ALIASES = Object.freeze({
  'blue-grey': 'editorial',
  'mist': 'editorial',
  'ocean': 'catppuccin',
  'amethyst': 'catppuccin',
  'rose': 'gruvbox',
  'amber': 'gruvbox',
  'forest': 'everforest',
  'mocha': 'catppuccin',
})

export const THEME_MODES = Object.freeze(['light', 'dark', 'system'])

export const DEFAULT_PALETTE = 'editorial'
export const DEFAULT_MODE = 'light'

export function normalizeThemePreference(value) {
  return value === 'dark' ? 'dark' : 'light'
}

export function normalizeModePreference(value) {
  if (value === 'dark' || value === 'system') return value
  return 'light'
}

export function normalizePalettePreference(value) {
  if (typeof value !== 'string') return DEFAULT_PALETTE
  const key = value.trim().toLowerCase()
  if (THEME_PALETTES.includes(key)) return key
  const legacy = LEGACY_PALETTE_ALIASES[key]
  if (legacy) return legacy
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

// Page/card/subtle surfaces for each palette family. These mirror the
// `--paper`, `--surface` and `--surface-2` values in style.css and are used to
// derive an accessible foreground for user-supplied accent colors.
export const PALETTE_SURFACES = Object.freeze({
  editorial: { lightPage: '#f5f2ea', light: '#fbf9f4', lightSubtle: '#f1ede4', darkPage: '#121512', dark: '#191d19', darkSubtle: '#1f241f' },
  gruvbox: { lightPage: '#fbf1c7', light: '#fff9e4', lightSubtle: '#f2e5bc', darkPage: '#282828', dark: '#3c3836', darkSubtle: '#504945' },
  everforest: { lightPage: '#fdf6e3', light: '#fffcf0', lightSubtle: '#efebd4', darkPage: '#2d353b', dark: '#343f44', darkSubtle: '#3d484d' },
  catppuccin: { lightPage: '#eff1f5', light: '#f7f8fb', lightSubtle: '#e6e9ef', darkPage: '#1e1e2e', dark: '#252537', darkSubtle: '#313244' },
})

export function getPaletteSurface(palette, isDark = false) {
  const norm = normalizePalettePreference(palette)
  return PALETTE_SURFACES[norm] || PALETTE_SURFACES[DEFAULT_PALETTE]
}

export function getAccessibleForeground(hexColor, isDarkTheme = false, palette = DEFAULT_PALETTE) {
  const norm = normalizeHexColor(hexColor)
  if (!norm) return isDarkTheme ? '#f8fafc' : '#0f172a'
  const normPalette = normalizePalettePreference(palette)
  const surfaces = getPaletteSurface(normPalette, isDarkTheme)
  const page = isDarkTheme ? surfaces.darkPage : surfaces.lightPage
  const card = isDarkTheme ? surfaces.dark : surfaces.light
  const subtle = isDarkTheme ? surfaces.darkSubtle : surfaces.lightSubtle
  const alpha = isDarkTheme ? 0.16 : 0.14
  const transCard = mixHex(card, norm, alpha)
  const transSubtle = mixHex(subtle, norm, alpha)
  const transPage = mixHex(page, norm, alpha)
  const targetSurfaces = [page, card, subtle, transPage, transCard, transSubtle]

  if (targetSurfaces.every(s => calculateContrastRatio(norm, s) >= 4.5)) {
    return norm
  }

  // If contrast is insufficient (e.g. #ffffff on white surface or #000000 on dark surface),
  // progressively adjust luminance while preserving the hue/tone as closely as possible.
  const target = isDarkTheme ? '#ffffff' : (norm === '#ffffff' ? '#0f172a' : '#000000')
  for (let step = 1; step <= 50; step++) {
    const candidate = mixHex(norm, target, step * 0.02)
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

/**
 * Shift an accent shade while keeping its foreground readable. Dark bases move
 * away from white on hover/active; light bases move away from the dark ink.
 * Pure black/white hits the clamp, so the shift reverses direction there to
 * keep the interaction state visible without dropping below AA.
 */
function shiftBrandState(base, weight) {
  const text = getContrastTextColor(base)
  const toward = text === '#ffffff' ? '#000000' : '#ffffff'
  const shifted = mixHex(base, toward, weight)
  if (shifted === base) {
    return mixHex(base, toward === '#000000' ? '#ffffff' : '#000000', weight)
  }
  return shifted
}

export function applyAccentPreference(root, hexColor, effectiveTheme = 'light', palette = '') {
  const hex = normalizeHexColor(hexColor)
  if (!root?.style) return ''

  if (hex) {
    const isDark = effectiveTheme === 'dark' || root?.getAttribute?.('data-theme') === 'dark'
    const curPalette = normalizePalettePreference(
      palette || root?.getAttribute?.('data-theme-palette') || DEFAULT_PALETTE
    )

    // Raw accent: legacy filled surfaces (--primary / --on-primary).
    const onPrimary = getContrastTextColor(hex)
    const rawHoverTarget = hex === '#000000' ? '#ffffff' : '#000000'
    const rawHover = mixHex(hex, rawHoverTarget, 0.12)
    const rawActive = mixHex(hex, rawHoverTarget, 0.24)
    const onPrimaryHover = getContrastTextColor(rawHover)
    const onPrimaryActive = getContrastTextColor(rawActive)

    // Accessible accent: text and filled brand surfaces. The base is adjusted
    // until legible on every palette surface, then every state carries the
    // foreground computed for that exact shade. Reusing the base foreground for
    // hover/active was the cause of dark-on-dark or light-on-light controls.
    const brandBase = getAccessibleForeground(hex, isDark, curPalette)
    const brandHover = shiftBrandState(brandBase, 0.12)
    const brandActive = shiftBrandState(brandBase, 0.24)
    const brandContrast = getContrastTextColor(brandBase)
    const onBrandHover = getContrastTextColor(brandHover)
    const onBrandActive = getContrastTextColor(brandActive)

    root.style.setProperty('--primary', hex)
    root.style.setProperty('--primary-fg', brandBase)
    root.style.setProperty('--on-primary', onPrimary)
    root.style.setProperty('--on-primary-hover', onPrimaryHover)
    root.style.setProperty('--on-primary-active', onPrimaryActive)
    root.style.setProperty('--primary-hover', rawHover)
    root.style.setProperty('--primary-active', rawActive)
    root.style.setProperty('--primary-light', `color-mix(in srgb, ${hex} 14%, transparent)`)
    root.style.setProperty('--primary-border', `color-mix(in srgb, ${brandBase} 36%, transparent)`)

    root.style.setProperty('--brand', brandBase)
    root.style.setProperty('--brand-hover', brandHover)
    root.style.setProperty('--brand-active', brandActive)
    root.style.setProperty('--brand-ink', brandBase)
    root.style.setProperty('--brand-soft', `color-mix(in srgb, ${hex} 10%, var(--surface))`)
    root.style.setProperty('--brand-line', `color-mix(in srgb, ${brandBase} 36%, transparent)`)
    root.style.setProperty('--brand-contrast', brandContrast)
    root.style.setProperty('--on-brand-hover', onBrandHover)
    root.style.setProperty('--on-brand-active', onBrandActive)
    return hex
  }

  for (const prop of [
    '--primary',
    '--primary-fg',
    '--on-primary',
    '--on-primary-hover',
    '--on-primary-active',
    '--primary-hover',
    '--primary-active',
    '--primary-light',
    '--primary-border',
    '--brand',
    '--brand-hover',
    '--brand-active',
    '--brand-ink',
    '--brand-soft',
    '--brand-line',
    '--brand-contrast',
    '--on-brand-hover',
    '--on-brand-active',
  ]) {
    root.style.removeProperty(prop)
  }
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
