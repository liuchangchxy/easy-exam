export const THEME_STORAGE_KEY = 'easyexam-theme'
export const THEME_PALETTE_STORAGE_KEY = 'easyexam-theme-palette'
export const THEME_MODE_STORAGE_KEY = 'easyexam-theme-mode'

/**
 * Storage key written by the retired custom-accent feature. Nothing reads it any
 * more — `clearLegacyAccentPreference` deletes it so a stale pick cannot come
 * back. The accent is a property of the palette family (see style.css
 * `--brand`), not a separate user preference.
 */
export const LEGACY_ACCENT_STORAGE_KEY = 'easyexam-theme-accent'

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

/* Colour maths. Pure utilities: the theme tests use them as the contrast
   oracle for the tokens declared in style.css. */
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

/**
 * One-time migration: drop the storage entry the retired accent picker wrote.
 * Safe to call on every boot.
 */
export function clearLegacyAccentPreference(storage) {
  try {
    storage?.removeItem?.(LEGACY_ACCENT_STORAGE_KEY)
  } catch {
    // Storage unavailable — nothing to clean.
  }
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
 * `mode` and `palette` are the whole appearance contract: the palette family
 * owns its own accent, so switching family is the only way to change it.
 */
export function applyFullTheme({ root, mode, palette, isSystemDark = false }) {
  const effectiveTheme = resolveEffectiveTheme(mode, isSystemDark)
  applyThemePreference(root, effectiveTheme)
  const normPalette = applyPalettePreference(root, palette)
  return {
    effectiveTheme,
    palette: normPalette,
  }
}
